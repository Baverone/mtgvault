"""REVALIDAÇÃO POR FOTO de toda a colecção (André, 2026-09-20).

À letra: *"quero que quando se clique, ele mostre as cartas, como está a fazer,
e que depois peça a foto das cartas. Quero revalidar todas as fotos agora que
vamos colocar tudo em decks para que nada falhe ou escape; assim o que eu for
vender também vai com foto e vamos pouco a pouco arrumando tudo no devido lugar
e bem feito."*

O que aqui se tranca — e cada caso CHUMBA se o código não fizer nada:

  1. uma cópia por revalidar recebe a foto NOVA sem duplicar (`validado_em`,
     `foto_anterior`; a foto antiga fica; o `aplicado.csv` regista a troca);
  2. prefere a caixa que está a ser fotografada (o alvo); a cópia igual à foto
     noutra caixa não é tocada;
  3. a DISCREPÂNCIA corrige a cópia da caixa com linha no `revalidacao.log`,
     e tira-a da `copy_allocation` quando a regra da caixa manda — e não a
     tira quando a correcção continua a cumprir;
  4. uma `quantity` maior do que a cópia parte-se; o que sobra segue a ordem;
  5. a ordem de conciliação com os CINCO caminhos numa linha só:
     (0) revalidação, (0b) discrepância, (i) edição por confirmar,
     (ii) encomenda pendente, (iv) entrada normal «nova nesta campanha»;
  6. a exportação da venda marca `foto`, e o «só validadas» filtra por cópia;
  7. o progresso conta certo (as parcelas somam a colecção) e NÃO muda um
     número da alocação/venda; com a campanha desligada não há nada disto;
  8. a página nos dois modos (botão só no 8771), o endpoint com/sem token, o
     `esperadas.md` com a secção da caixa, e a CLI.

Não abre socket para fora nem toca na `vault.db` a sério.
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "edicoes": "premodern", "estrita": True},
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "pm", "nome": "UW Replenish", "formato": "premodern",
         "fonte": "deck", "ref": "PM", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1},
        {"slot": "pm2", "nome": "Enchantress", "formato": "premodern",
         "fonte": "deck", "ref": "PM2", "balde": "Colecção",
         "estado": "permanente", "prioridade": 2},
        {"slot": "lg", "nome": "Legacy — Doomsday", "formato": "legacy",
         "fonte": "deck", "ref": "LG", "balde": "Colecção",
         "estado": "permanente", "prioridade": 3},
    ],
    "revalidacao": {"desde": "2026-09-20", "alvo": None},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, configio, db, encomendas, loadout,  # noqa: E402
                      revalidacao, sources, venda)

import deckboxes  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"], 1.50),
    ("Swords to Plowshares", "ody", "2001-09-24", ["nonfoil", "foil"], 2.00),
    ("Swords to Plowshares", "2x2", "2022-07-08", ["nonfoil", "foil"], 3.00),
    ("Force of Will", "all", "1996-06-10", ["nonfoil"], 60.0),
    ("Force of Will", "2xm", "2020-08-07", ["nonfoil", "foil"], 50.0),
    ("Brainstorm", "ice", "1995-06-03", ["nonfoil"], 0.50),
    ("Null Rod", "wth", "1997-06-09", ["nonfoil"], 40.0),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fin, preco) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,?,?,?,?,0,?)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i),
             "Artifact" if nm == "Null Rod" else "Instant",
             "" if nm == "Null Rod" else ("U" if nm in ("Brainstorm", "Force of Will") else "W"),
             json.dumps(fin), rel,
             json.dumps({"legacy": "legal", "premodern": "legal"}),
             1 if nm == "Null Rod" else 0))
        for f in fin:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-20', ?)", (f"id-{i}", f, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    return con


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q, board in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,?)", (did, nm, q, board))
    con.commit()
    return did


def mundo():
    """Três caixas: PM pede 2 Swords, PM2 1 Swords, LG 1 FoW."""
    con = base()
    deck(con, "PM", "premodern", [("Swords to Plowshares", 2, "main")])
    deck(con, "PM2", "premodern", [("Swords to Plowshares", 1, "main")])
    deck(con, "LG", "legacy", [("Force of Will", 1, "main")])
    return con


def repor(alvo=None, campanha=True):
    cfg = json.loads(json.dumps(CFG))
    if not campanha:
        cfg.pop("revalidacao")
    elif alvo:
        cfg["revalidacao"]["alvo"] = alvo
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def copia(con, nm, sc, q=1, lang="pt", finish="nonfoil", foto=None, sub="Colecção",
          slot=None, validado=None):
    """Uma cópia 'antiga': entra sem foto de campanha (a menos que se diga)."""
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language=lang,
                              finish=finish, sub_collection=sub)
    con.execute("UPDATE copies SET photo_path = ?, validado_em = ? WHERE id = ?",
                (foto, validado, cid))
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,?)",
                    (cid, slot, q))
    con.commit()
    return cid


def copias(con):
    return [dict(r) for r in con.execute(
        """SELECT cp.id, cp.quantity, cp.finish, cp.language, cp.notes,
                  cp.photo_path, cp.validado_em, cp.foto_anterior, c.name, c.set_code
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            ORDER BY cp.id""")]


def alocacao(con, slot=None):
    q = "SELECT copy_id, slot, quantity FROM copy_allocation"
    args = ()
    if slot:
        q += " WHERE slot = ?"
        args = (slot,)
    return [dict(r) for r in con.execute(q + " ORDER BY copy_id", args)]


def foto_csv(texto, nome="foto.csv"):
    p = _TMP / nome
    p.write_text("name,set_code,collector_number,quantity,finish,language,"
                 "sub_collection,photo_path\n" + texto, encoding="utf-8")
    return p


def importar(con, linha, nome="foto.csv"):
    res = []
    ok, erros = collection.import_csv(con, foto_csv(linha, nome), resultados=res)
    assert not erros, erros
    return res


def log_de(p):
    return [l.split("\t") for l in Path(p).read_text(encoding="utf-8").splitlines()]


def numeros(rep):
    return (rep["custo_total"], rep["comprar_total"], rep["arrumacao"]["copias"],
            rep["copias"], rep["total"], rep["copias_rl"], rep["total_rl"],
            [(s["slot"], s["pct"], s["tenho"], s["comprar"]) for s in rep["slots"]])


# ---------------------------------------------------------------------------
def caso_a_foto_nova_liga_se_sem_duplicar():
    """A cópia existe, tem foto antiga, e está por revalidar. A foto NOVA da
    mesma impressão exacta liga-se a ela: `photo_path` novo, `foto_anterior`
    com a antiga, `validado_em` = hoje — e a base continua com as mesmas
    cópias. O `arrumar_fotos` escreve a troca no `aplicado.csv`."""
    repor()
    con = mundo()
    cid = copia(con, "Swords to Plowshares", "4ed", q=2, foto="velha.jpg", slot="pm")
    assert revalidacao.activa() and revalidacao.desde() == "2026-09-20"
    pend = _TMP / "pend1"
    pend.mkdir(exist_ok=True)
    (pend / "IMG_1.jpg").write_bytes(b"\xff\xd8x")
    res = importar(con, "Swords to Plowshares,4ed,0,2,nonfoil,pt,Colecção,IMG_1.jpg")
    assert res[0]["motivo"] == "2 revalidadas: foto nova", res[0]
    assert res[0]["copy_id"] == cid, res[0]
    cps = copias(con)
    assert len(cps) == 1 and cps[0]["quantity"] == 2, ("não duplicou", cps)
    assert cps[0]["photo_path"] == "IMG_1.jpg" and cps[0]["foto_anterior"] == "velha.jpg"
    assert cps[0]["validado_em"] == revalidacao.hoje(), cps[0]
    assert alocacao(con) == [{"copy_id": cid, "slot": "pm", "quantity": 2}]
    f = collection.arrumar_fotos(con, res, pendentes=pend)
    assert f["ligadas"] == 1, f
    rows = list(csv.DictReader((pend / "fotos processadas" / "aplicado.csv")
                               .open(encoding="utf-8")))
    assert rows[-1]["foto_anterior"] == "velha.jpg" and rows[-1]["copy_id"] == str(cid), rows[-1]
    assert copias(con)[0]["photo_path"].endswith("IMG_1.jpg")
    # A segunda foto da mesma impressão já não tem a quem se ligar: entra
    # como nova (marcada) — é o que a foto prova.
    res = importar(con, "Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_1b.jpg", "f1b.csv")
    cps = copias(con)
    assert len(cps) == 2 and revalidacao.MARCA_NOVA in (cps[1]["notes"] or ""), cps
    assert cps[1]["validado_em"] == revalidacao.hoje(), "nasce validada: tem foto"
    print("foto nova: liga-se a copia por revalidar, guarda a antiga, nao duplica")


def caso_prefere_a_caixa_do_alvo():
    """Duas cópias iguais por revalidar, uma na caixa PM (o alvo) e outra na
    Enchantress. A foto de UMA valida a do alvo; a outra não é tocada."""
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-09-20"})
    con = mundo()
    outra = copia(con, "Swords to Plowshares", "4ed", foto="a.jpg", slot="pm2")
    minha = copia(con, "Swords to Plowshares", "4ed", foto="b.jpg", slot="pm")
    assert revalidacao.alvo()["slot"] == "pm"
    res = importar(con, "Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_2.jpg")
    assert res[0]["copy_id"] == minha, res[0]
    por = {c["id"]: c for c in copias(con)}
    assert por[minha]["validado_em"] and por[minha]["photo_path"] == "IMG_2.jpg"
    assert not por[outra]["validado_em"] and por[outra]["photo_path"] == "a.jpg", por[outra]
    # Sem alvo, a ordem é a de sempre: a cópia com a MESMA quantidade da foto,
    # depois o id mais baixo — determinista.
    repor()
    res = importar(con, "Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_3.jpg", "f3.csv")
    assert res[0]["copy_id"] == outra, res[0]
    print("alvo: a foto valida a copia da caixa que esta a ser fotografada")


def caso_discrepancia_corrige_e_tira_da_caixa_se_a_regra_mandar():
    """A caixa PM (Premodern: PT e ≤ Scourge) tem 4 Swords ODY PT por revalidar.
    A foto traz Swords 2X2 PT (2022) e não há cópia igual à foto: é uma
    CORRECÇÃO da cópia da caixa — passa a 2X2, com linha no `revalidacao.log`
    — e, como 2X2 não cumpre a regra da caixa, sai da `copy_allocation` com o
    porquê nas `notes`. A quantidade parte-se: 1 corrigida, 3 ficam."""
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-09-20"})
    con = mundo()
    cid = copia(con, "Swords to Plowshares", "ody", q=4, foto="o.jpg", slot="pm")
    rep0 = loadout.report(con)
    res = importar(con, "Swords to Plowshares,2x2,2,1,nonfoil,pt,Colecção,IMG_4.jpg")
    m = res[0]["motivo"]
    assert "1 corrigida pela foto: ODY #1 nonfoil pt → 2X2 #2 nonfoil pt" in m, m
    assert "saiu da caixa UW Replenish" in m, m
    cps = copias(con)
    assert len(cps) == 2 and sum(c["quantity"] for c in cps) == 4, cps
    nova = next(c for c in cps if c["id"] != cid)
    assert nova["set_code"] == "2x2" and nova["quantity"] == 1, nova
    assert nova["validado_em"] and nova["photo_path"] == "IMG_4.jpg" and nova["foto_anterior"] == "o.jpg"
    assert revalidacao.MARCA_CORRIGIDA in nova["notes"] and revalidacao.MARCA_SAIU in nova["notes"], nova["notes"]
    velha = next(c for c in cps if c["id"] == cid)
    assert velha["quantity"] == 3 and velha["set_code"] == "ody" and not velha["validado_em"]
    assert alocacao(con) == [{"copy_id": cid, "slot": "pm", "quantity": 3}], alocacao(con)
    acs = [(l[1], l[2]) for l in log_de(revalidacao.ficheiro_log())]
    assert acs[-2][0] == "corrigida" and f"cópia {cid}: ODY #1 nonfoil pt → 2X2 #2 nonfoil pt" in acs[-2][1], acs
    assert acs[-1][0] == "saiu-da-caixa" and "UW Replenish" in acs[-1][1], acs
    # A caixa passou a contar 3 (a 2X2 não serve) — a correcção não se lava.
    rep = loadout.report(con)
    pm = next(s for s in rep["slots"] if s["slot"] == "pm")
    assert pm["tenho"] == 2 and pm["comprar"] == 0, (pm["tenho"], pm["comprar"])
    prog = revalidacao.progresso(con, rep)
    assert prog["total"]["corrigidas"] == 1 and prog["corrigidas"][0]["copy_id"] == nova["id"]
    assert "2X2" in prog["corrigidas"][0]["nota"], prog["corrigidas"][0]
    # E uma correcção que CONTINUA a cumprir (ODY → 4ED, ambas da era, PT)
    # fica na caixa.
    res = importar(con, "Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_5.jpg", "f5.csv")
    assert "corrigida pela foto: ODY #1 nonfoil pt → 4ED #0 nonfoil pt" in res[0]["motivo"]
    assert "saiu da caixa" not in res[0]["motivo"], res[0]
    assert sorted(a["quantity"] for a in alocacao(con, "pm")) == [1, 2], alocacao(con)
    # A caixa pede 2 e tinha 4 ODY: antes e depois fecha com 2 — a 2X2 corrigida
    # saiu, sobram 3 que servem. A campanha sozinha não mexe em nada (caso 7).
    assert next(s for s in rep0["slots"] if s["slot"] == "pm")["tenho"] == 2
    print("discrepancia: corrige a copia da caixa, log, e sai da caixa so quando a regra manda")


def caso_a_copia_igual_a_foto_ganha_a_discrepancia():
    """Há uma cópia IGUAL à foto noutro sítio e a caixa-alvo tem a carta noutra
    edição: a foto liga-se à igual (passo 0, «depois qualquer») e não se
    corrige nada — a discrepância só existe quando não há cópia igual à foto."""
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-09-20"})
    con = mundo()
    na_caixa = copia(con, "Swords to Plowshares", "ody", foto="o.jpg", slot="pm")
    solta = copia(con, "Swords to Plowshares", "4ed", foto="s.jpg")
    res = importar(con, "Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_6.jpg")
    assert res[0]["copy_id"] == solta and "revalidada" in res[0]["motivo"], res[0]
    por = {c["id"]: c for c in copias(con)}
    assert por[na_caixa]["set_code"] == "ody" and not por[na_caixa]["validado_em"]
    assert revalidacao.MARCA_CORRIGIDA not in (por[na_caixa]["notes"] or "")
    print("copia igual a foto noutro sitio: liga-se; a da caixa nao e corrigida")


def caso_quantidade_maior_parte_e_o_resto_segue():
    """Foto de 3; há 2 por revalidar (uma linha de 2): 2 revalidam, 1 entra
    como nova. E uma linha de 4 com foto de 1: parte-se em 1 + 3."""
    repor()
    con = mundo()
    cid = copia(con, "Brainstorm", "ice", q=2, lang="en", foto="b.jpg")
    res = importar(con, "Brainstorm,ice,5,3,nonfoil,en,Colecção,IMG_7.jpg")
    assert res[0]["motivo"] == "2 revalidadas: foto nova", res[0]
    cps = copias(con)
    assert [(c["quantity"], bool(c["validado_em"])) for c in cps] == [(2, True), (1, True)], cps
    assert revalidacao.MARCA_NOVA in cps[1]["notes"]
    cid4 = copia(con, "Force of Will", "all", q=4, lang="en", foto="f.jpg")
    res = importar(con, "Force of Will,all,3,1,nonfoil,en,Colecção,IMG_8.jpg", "f8.csv")
    assert res[0]["motivo"] == "1 revalidada: foto nova", res[0]
    fow = [c for c in copias(con) if c["name"] == "Force of Will"]
    assert sorted((c["quantity"], bool(c["validado_em"])) for c in fow) == [(1, True), (3, False)], fow
    assert next(c for c in fow if c["id"] == cid4)["quantity"] == 3
    print("quantidade: parte-se; o que sobra entra como nova nesta campanha")


def caso_os_cinco_caminhos_numa_linha():
    """Uma foto de 5 Swords 4ED PT: (0) 1 revalida a cópia igual da caixa-alvo,
    (0b) 1 corrige a ODY da mesma caixa, (i) 1 acerta a «edição por
    confirmar», (ii) 1 fecha a encomenda pendente da Enchantress, (iv) 1 entra
    como nova. Cinco cópias, cinco `copy_id`, todas validadas."""
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-09-20"})
    con = mundo()
    a = copia(con, "Swords to Plowshares", "4ed", foto="a.jpg", slot="pm")
    b = copia(con, "Swords to Plowshares", "ody", foto="b.jpg", slot="pm")
    rep = loadout.report(con)
    c_ = loadout.registar_falta(con, rep, "pm2", "Swords to Plowshares",
                                quantidade=1, csv_path=_TMP / "f9.csv")["copy_id"]
    encomendas.adicionar(con, "pm2", "Swords to Plowshares", 1,
                         estado=encomendas.PENDENTE, log_path=_TMP / "e9.log")
    res = importar(con, "Swords to Plowshares,4ed,0,5,nonfoil,pt,Colecção,IMG_9.jpg")
    m = res[0]["motivo"]
    assert "1 revalidada" in m and "1 corrigida pela foto: ODY" in m, m
    assert "1 de «já a tenho»" in m and "1 fecha encomenda" in m, m
    ids = [int(x) for x in str(res[0]["copy_id"]).split(",")]
    assert len(ids) == 5 and a in ids and b in ids and c_ in ids, (ids, a, b, c_)
    cps = copias(con)
    assert len(cps) == 5 and sum(c["quantity"] for c in cps) == 5, cps
    assert all(c["validado_em"] and c["set_code"] == "4ed" for c in cps), cps
    assert sum(1 for c in cps if revalidacao.MARCA_NOVA in (c["notes"] or "")) == 1
    assert sum(1 for c in cps if revalidacao.MARCA_CORRIGIDA in (c["notes"] or "")) == 1
    print("os cinco caminhos: revalida > corrige > acerta > encomenda > nova")


def caso_a_exportacao_da_venda_marca_foto():
    """8 Brainstorm (nenhuma caixa os pede): 4 ficam, 4 vão à venda — os de
    pior estado, duas linhas de 2 EX. Uma revalidada, outra não: cada linha do
    CSV diz `validada <data>` / `por revalidar`, a estante marca 📷, o
    `csv_validadas` só tem as 2, e o `exportar(so_validadas=True)` escreve só
    essas."""
    repor()
    con = mundo()
    v1 = copia(con, "Brainstorm", "ice", q=2, lang="en", foto="x.jpg")
    v2 = copia(con, "Brainstorm", "ice", q=2, lang="en", foto="y.jpg",
               validado="2026-09-21")
    ok = copia(con, "Brainstorm", "ice", q=4, lang="en", foto="z.jpg")
    con.execute("UPDATE copies SET condition = 'EX' WHERE id IN (?, ?)", (v1, v2))
    con.commit()
    rep = loadout.report(con)
    vend = [c for r in rep["venda"] for c in r["copias"]]
    assert sorted(int(c) for c, _q in vend) == sorted([v1, v2]), (vend, v1, v2, ok)
    r = venda.relatorio(con, rep)
    assert r["copias"] == 4 and r["copias_validadas"] == 2 and r["copias_por_revalidar"] == 2, r["copias"]
    rows = list(csv.reader(io.StringIO(r["csv"])))
    assert rows[0][-1] == "Foto"
    fotos = {int(row[8].split("#")[1].split(" ")[0]): row[-1] for row in rows[1:]}
    assert fotos == {v1: "por revalidar", v2: "validada 2026-09-21"}, fotos
    rv = list(csv.reader(io.StringIO(r["csv_validadas"])))
    assert len(rv) == 2 and rv[1][-1] == "validada 2026-09-21", rv
    assert "📷 por revalidar" in r["texto_estante"] and "📷" not in r["texto_estante_validadas"]
    pasta = _TMP / "exp"
    e = venda.exportar(con, rep, pasta=pasta, so_validadas=True)
    assert e["copias"] == 2 and e["so_validadas"] and "só validadas" in e["resumo"], e
    assert (pasta / venda.FICHEIRO_STOCK).read_text(encoding="utf-8").count("\n") == 2
    e = venda.exportar(con, rep, pasta=pasta)
    assert e["copias"] == 4 and "2 por revalidar" in e["resumo"], e
    # A página: a linha de venda diz {ok: 2, falta: 2} e o bloco soma.
    d = deckboxes.payload(con, rep)
    n = d["venda"]["normal"]
    assert n["validadas"] == 2 and n["por_revalidar"] == 2, n
    assert n["linhas"][0]["foto"] == {"ok": 2, "falta": 2}, n["linhas"][0]
    print("venda: coluna Foto por copia, csv_validadas, estante com 📷, exportar --so-validadas")


def caso_o_progresso_conta_certo_e_nao_muda_numeros():
    """As parcelas (caixas + venda + RL + resto) somam a colecção inteira; a
    campanha não muda um número do relatório; sem campanha, nada disto existe."""
    repor()
    con = mundo()
    copia(con, "Swords to Plowshares", "4ed", q=2, foto="a.jpg", slot="pm")   # caixa pm
    copia(con, "Swords to Plowshares", "ody", q=1, foto="b.jpg")             # a alocação dá ao pm2
    copia(con, "Swords to Plowshares", "4ed", q=6, foto="c.jpg")             # 4 ficam, alguma vai à venda
    copia(con, "Null Rod", "wth", q=1, lang="en", foto="n.jpg", sub="Caixa Reserved List")
    copia(con, "Brainstorm", "ice", q=3, lang="en", foto="d.jpg", validado="2026-09-20")
    rep = loadout.report(con)
    prog = revalidacao.progresso(con, rep)
    T = prog["total"]
    assert T["q"] == 13 and T["validadas"] == 3 and T["por_revalidar"] == 10, T
    soma = sum(c["q"] for c in prog["caixas"]) + prog["venda"]["q"] + prog["rl"]["q"] + prog["resto"]["q"]
    assert soma == T["q"], (soma, T)
    por = {c["slot"]: c for c in prog["caixas"]}
    assert por["pm"]["q"] == 2 and por["pm2"]["q"] == 1 and por["lg"]["q"] == 0, por
    assert prog["rl"]["q"] == 1 and prog["rl"]["linhas"][0]["nm"] == "Null Rod"
    assert prog["venda"]["q"] == rep["copias"] + rep["copias_rl"], (prog["venda"]["q"], rep["copias"])
    assert prog["resto"]["q"] == 13 - 3 - prog["venda"]["q"] - 1
    assert prog["hoje_entradas"] == [] or prog["hoje_entradas"][0]["nm"] == "Brainstorm"
    # A lista de uma caixa vem por COR: o Swords (branco) antes de nada.
    assert por["pm"]["linhas"][0]["cor"] == "W" and por["pm"]["linhas"][0]["estado"] == "foto"
    # A campanha não mexe nos números.
    antes = numeros(rep)
    repor(campanha=False)
    rep2 = loadout.report(con)
    assert numeros(rep2) == antes, "a campanha mudou a alocação/venda?!"
    assert not revalidacao.activa() and revalidacao.desde() is None
    d = deckboxes.payload(con, rep2)
    assert d["revalidacao"] is None and all(c["rev"] is None for c in d["caixas"])
    assert "foto" in d["venda"]["normal"]["linhas"][0]   # a chave fica, a aba não
    # E uma cópia que nasça com foto sem campanha NÃO fica validada.
    cid = collection.add_copy(con, "Brainstorm", set_code="ice", quantity=1,
                              language="en", sub_collection="Colecção", photo_path="e.jpg")
    assert con.execute("SELECT validado_em FROM copies WHERE id = ?", (cid,)).fetchone()[0] is None
    repor()
    print("progresso: as parcelas somam, os numeros do relatorio nao mexem, sem campanha nada existe")


# ---------------------------------------------------------------------------
# HTTP, esperadas.md, CLI, página
# ---------------------------------------------------------------------------
class Pedido(webapp.Handler):
    def __init__(self, path, corpo=None, token=None, ip="192.168.1.99"):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO((corpo or "").encode("utf-8"))
        self.headers = {"Content-Length": str(len(corpo or "")) or "0"}
        if token:
            self.headers[webapp.CABECALHO_TOKEN] = token
        self.codigo, self.corpo = None, ""

    def send_response(self, code, *_a):
        self.codigo = code

    def send_header(self, *_a):
        pass

    def end_headers(self):
        pass

    @property
    def wfile(self):
        self_ = self

        class Escritor:
            def write(self, b):
                self_.corpo = b.decode("utf-8", "replace")
        return Escritor()


def _post(caminho, dados, ip="127.0.0.1"):
    p = Pedido(caminho, json.dumps(dados), ip=ip)
    p.do_POST()
    return p.codigo, (json.loads(p.corpo) if p.corpo.startswith("{") else p.corpo)


def caso_endpoint_e_esperadas_md():
    """«Fotografar esta caixa» escreve o alvo no config (403 sem token, 409 numa
    caixa que não existe) e o `esperadas.md` ganha a secção da caixa com as
    cópias por revalidar; «parar» tira o alvo e a secção."""
    repor()
    con = mundo()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    copia(con, "Swords to Plowshares", "4ed", q=2, foto="a.jpg", slot="pm")
    copia(con, "Swords to Plowshares", "ody", q=1, foto="b.jpg", slot="pm", validado="2026-09-21")
    encomendas.adicionar(con, "lg", "Force of Will", 1, estado=encomendas.PENDENTE,
                         log_path=_TMP / "e10.log")
    pend = webapp.ROOT / "pendentes"
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "caixa", "slot": "pm"},
                   ip="192.168.1.99")
    assert cod == 403 and revalidacao.alvo() is None, (cod, j)
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "caixa", "slot": "nao-ha"})
    assert cod == 409 and "não existe" in j["erro"], (cod, j)
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "caixa", "slot": "pm"})
    assert cod == 200 and j["por_revalidar"] == 2 and "UW Replenish" in j["msg"], (cod, j)
    assert configio.ler()["revalidacao"]["alvo"]["slot"] == "pm"
    assert revalidacao.alvo() == {"tipo": "caixa", "slot": "pm", "em": revalidacao.hoje()}
    txt = (pend / "esperadas.md").read_text(encoding="utf-8")
    assert "## Caixa UW Replenish — por revalidar (2 cópias)" in txt, txt
    assert "- 2× **Swords to Plowshares** — 4ED #0 · pt · nonfoil · cópia #" in txt, txt
    assert "ODY" not in txt.split("## Encomendas")[0], "a validada não se pede"
    assert "## Encomendas pendentes" in txt and "Force of Will" in txt, txt
    assert txt.index("por revalidar") < txt.index("Encomendas pendentes")
    # A página do modo edição sabe o alvo: a caixa diz «A fotografar».
    idx, partes = webapp.dados_deckboxes(True, "t")
    assert idx["revalidacao"]["alvo"]["slot"] == "pm"
    assert partes["caixa-pm"]["rev"]["alvo"] is True and partes["caixa-pm"]["rev"]["por_revalidar"] == 2
    webapp._CACHE.clear()
    cod, j = _post("/api/revalidacao", {"act": "parar"})
    assert cod == 200 and revalidacao.alvo() is None, (cod, j)
    txt = (pend / "esperadas.md").read_text(encoding="utf-8")
    assert "por revalidar" not in txt and "Force of Will" in txt, txt
    # Outros alvos: a venda e a colecção; e um tipo desconhecido é 409.
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "coleccao"})
    assert cod == 200 and j["nome"].startswith("Colecção"), (cod, j)
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "xpto"})
    assert cod == 409, (cod, j)
    _post("/api/revalidacao", {"act": "parar"})
    webapp._CACHE.clear()
    repor()
    print("endpoint: alvo/parar com token, config escrito, esperadas.md com a seccao da caixa")


def caso_cli_progresso_e_esperadas():
    repor()
    con = mundo()
    copia(con, "Swords to Plowshares", "4ed", q=2, foto="a.jpg", slot="pm")
    copia(con, "Brainstorm", "ice", q=1, lang="en", foto="b.jpg", validado="2026-09-20")
    dbs = con.execute("PRAGMA database_list").fetchall()
    base_, cat = dbs[0]["file"], dbs[1]["file"]
    pend = _TMP / "pend-cli"
    pend.mkdir(exist_ok=True)

    def cli(*args):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        p = subprocess.run([sys.executable, "-c",
                            "import sys; from mtgvault import collection, cli; "
                            f"collection.PENDENTES = __import__('pathlib').Path({str(pend)!r}); "
                            "cli.main(sys.argv[1:])",
                            "--db", base_, "--catalog", cat, "revalidacao", *args],
                           cwd=str(RAIZ), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180, env=env)
        return p.returncode, p.stdout, p.stderr

    cod, out, err = cli("--json")
    assert cod == 0, (cod, out, err)
    j = json.loads(out)
    assert j["total"] == {"q": 3, "validadas": 1, "por_revalidar": 2, "corrigidas": 0,
                          "novas": 0, "pct": 33}, j["total"]
    cod, out, err = cli()
    assert cod == 0 and "1/3 validadas" in out and "UW Replenish" in out, (out, err)
    cod, out, err = cli("--caixa", "pm")
    assert cod == 0 and "📷 por fotografar" in out and "Swords" in out, (out, err)
    cod, out, err = cli("esperadas", "--caixa", "pm")
    assert cod == 0 and "2 por fotografar" in out, (out, err)
    assert configio.ler()["revalidacao"]["alvo"]["slot"] == "pm"
    assert "## Caixa UW Replenish — por revalidar" in (pend / "esperadas.md").read_text(encoding="utf-8")
    cod, out, err = cli("esperadas", "--caixa", "nao-ha")
    assert cod == 2, (out, err)
    cod, out, err = cli("parar")
    assert cod == 0 and "alvo tirado" in out, (out, err)
    sources._CFG_CACHE.clear()
    assert configio.ler()["revalidacao"]["alvo"] is None
    repor()
    print("CLI: revalidacao [--json] [--caixa], esperadas --caixa, parar")


def _abas(con, editable):
    if not shutil.which("node"):
        return None
    pasta = Path(tempfile.mkdtemp())
    pagina = pasta / "deckboxes.html"
    pagina.write_text(deckboxes.html_page(con, editable=editable), encoding="utf-8")
    dump = pasta / "abas.json"
    p = subprocess.run(["node", str(Path(__file__).with_name("render_deckboxes.js")),
                        str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_a_pagina_nos_dois_modos():
    """A aba «📷 Revalidação», a barra e a lista «Na caixa» nos dois modos; o
    botão «Fotografar» só no modo edição; a venda com 📷/✓ e o filtro."""
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-09-20"})
    con = mundo()
    copia(con, "Swords to Plowshares", "4ed", q=2, foto="a.jpg", slot="pm")
    copia(con, "Swords to Plowshares", "ody", q=1, foto="b.jpg", slot="pm", validado="2026-09-21")
    con.execute("UPDATE copies SET notes = ? WHERE photo_path = 'b.jpg'",
                (f"{revalidacao.MARCA_CORRIGIDA} em 2026-09-21: ODY → 4ED",))
    con.commit()
    copia(con, "Swords to Plowshares", "4ed", q=6, foto="c.jpg")   # 1 p/ pm2, 5 à venda
    copia(con, "Null Rod", "wth", q=1, lang="en", foto="n.jpg", sub="Caixa Reserved List")
    abas = _abas(con, True)
    if abas is None:
        print("pagina: sem `node`, saltado")
        return
    fila = abas["__fila"]
    assert "📷 Revalidação" in fila and "por fotografar" in fila, fila
    r = abas["revalidacao"]
    assert "A fotografar: Caixa UW Replenish" in r and 'data-rev-parar="1"' in r, r[:2000]
    assert 'data-rev="venda"' in r and 'data-rev="rl"' in r, r[:3000]
    assert 'data-rev="caixa" data-slot="pm2"' in r, "a Enchantress tem o botão"
    assert "⚠ Corrigidas pela foto" in r and "ODY → 4ED" in r, r
    c = abas["pm"]
    assert "📷 Na caixa — fotografar" in c and "validadas <b>1/3</b>" in c, c[-4000:]
    assert 'data-rev-parar="1"' in c and "A fotografar UW Replenish" in c, c[-4000:]
    # EM IMAGEM (2026-09-20): um tile por cópia, com o estado na moldura
    # (`tl rev` = 📷 por fotografar, `tl corr` = ⚠ corrigida) e a grelha com
    # «📷 2 por fotografar» no chip; em «Lista» é a linha `.mv.rv` de sempre.
    assert 'class="tl rev"' in c and 'class="tl corr"' in c, c[-4000:]
    assert "📷 por fotografar" in c and "⚠ corrigida pela foto" in c, c[-4000:]
    assert '"tlr">📷 2 por fotografar' in c, "o estado da grelha"
    cl = abas["lista:pm"]
    assert 'class="mv rv foto"' in cl and 'class="mv rv corr"' in cl, cl[-4000:]
    v = abas["vender"]
    assert "📷 Só validadas" in v and 'class="tl rev"' in v, v[:3000]
    assert 'class="rvfoto"' in abas["lista:vender"], abas["lista:vender"][:3000]
    # A caixa da Enchantress (sem alvo) tem o botão «Fotografar esta caixa»;
    # a barra da fila diz «validadas».
    pub = _abas(con, False)
    assert "📷 Na caixa — fotografar" in pub["pm"] and "validadas <b>1/3</b>" in pub["pm"]
    for marca in ("data-rev=", "data-rev-parar"):
        assert marca not in pub["pm"] and marca not in pub["revalidacao"], marca
    assert "📷 Revalidação" in pub["__fila"]
    assert 'class="tl rev"' in pub["vender"], "a venda marca 📷 também no publicado"
    assert 'class="rvfoto"' in pub["lista:vender"]
    repor()
    print("pagina: aba, barra, lista Na caixa e venda com 📷 nos dois modos; botoes so no 8771")


def run():
    for fn in (caso_a_foto_nova_liga_se_sem_duplicar,
               caso_prefere_a_caixa_do_alvo,
               caso_discrepancia_corrige_e_tira_da_caixa_se_a_regra_mandar,
               caso_a_copia_igual_a_foto_ganha_a_discrepancia,
               caso_quantidade_maior_parte_e_o_resto_segue,
               caso_os_cinco_caminhos_numa_linha,
               caso_a_exportacao_da_venda_marca_foto,
               caso_o_progresso_conta_certo_e_nao_muda_numeros,
               caso_endpoint_e_esperadas_md,
               caso_cli_progresso_e_esperadas,
               caso_a_pagina_nos_dois_modos):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
