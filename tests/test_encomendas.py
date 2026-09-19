"""ENCOMENDAS: «só a foto cria cópias» (André, 2026-09-19).

À letra: *"consegues, para o magic, criar algo igual ao que criaste para o
Riftbound, mas ao invés de "coleção" colocas para os decks? (...) dizia-te o
que ia comprando, e tu só ias pedindo as fotos das cartas; cada vez que eu
adiciono que tenho a carta, fica pendente de foto; quando coloco a foto,
adicionas à coleção"*.

O que aqui se tranca — e cada caso CHUMBA se o código não fizer nada:

  1. o `+`/`−` NÃO criam cópias nem linhas na `copy_allocation`, e o `−` nunca
     vai abaixo de zero (a zero, a linha apaga-se); tudo com rasto no
     `encomendas.log`;
  2. «Chegou» move a quantidade para pendente de foto e «desfazer» volta;
  3. o `missing` fica, mas o «comprar», o «fechar tudo por», a wantlist, o Plano
     e a aba Comprar DESCONTAM o que está a caminho ou pendente de foto;
  4. a regra de material da caixa manda no `+` (edição, língua, acabamento);
  5. a FOTO fecha a encomenda: cria a cópia com `photo_path`, aloca-a à caixa;
  6. uma foto que não cumpre a regra deixa a encomenda aberta com aviso, e a
     cópia entra na Colecção sem caixa;
  7. a encomenda serve a caixa de MAIOR prioridade;
  8. a foto de uma cópia da base SEM foto liga-se a ela — não duplica;
  9. uma foto sem correspondência entra como hoje; a «edição por confirmar»
     continua a acertar-se primeiro;
 10. as quantidades partem-se (3 na foto = 2 fecham + 1 entra);
 11. os endpoints com/sem token; a CLI `add`/`chegou`/`listar --json`;
 12. o separador desenha nos dois modos (botões só no modo edição) e a linha de
     compra diz «N a caminho»; o `pendentes/esperadas.md`.

Não abre socket para fora nem toca na `vault.db` a sério.
"""
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
         "edicoes": "premodern", "dedicado": False},
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
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, encomendas, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"           # nunca o repositório (ver test_montar_barra)
webapp.ROOT.mkdir(exist_ok=True)

# (nome, edição, data, acabamentos, preço). Duas da era e uma de 2022, como no
# test_faltas_check: a de 2022 é a que a caixa de Premodern recusa.
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"], 1.50),
    ("Swords to Plowshares", "ody", "2001-09-24", ["nonfoil", "foil"], 2.00),
    ("Swords to Plowshares", "2x2", "2022-07-08", ["nonfoil", "foil"], 3.00),
    ("Force of Will", "all", "1996-06-10", ["nonfoil"], 60.0),
    ("Force of Will", "2xm", "2020-08-07", ["nonfoil", "foil"], 50.0),
    ("Brainstorm", "ice", "1995-06-03", ["nonfoil"], 0.50),
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
               VALUES (?,?,?,?,?,?,'en','rare','Instant',1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i),
             json.dumps(fin), rel,
             json.dumps({"legacy": "legal", "premodern": "legal"})))
        for f in fin:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-19', ?)", (f"id-{i}", f, preco))
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


def montavel():
    """Três caixas sem uma única cópia na colecção: tudo é falta a comprar."""
    con = base()
    deck(con, "PM", "premodern", [("Swords to Plowshares", 2, "main")])
    deck(con, "PM2", "premodern", [("Swords to Plowshares", 1, "main")])
    deck(con, "LG", "legacy", [("Force of Will", 1, "main")])
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def caixa(con, slot="pm", editable=True):
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=editable)
    return next(c for c in d["caixas"] if c["slot"] == slot), rep, d


def copias(con):
    return [dict(r) for r in con.execute(
        """SELECT cp.id, cp.quantity, cp.finish, cp.language, cp.notes,
                  cp.photo_path, c.name, c.set_code
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            ORDER BY cp.id""")]


def alocacao(con, slot=None):
    q = "SELECT copy_id, slot, quantity FROM copy_allocation"
    args = ()
    if slot:
        q += " WHERE slot = ?"
        args = (slot,)
    return [dict(r) for r in con.execute(q, args)]


def linhas(con):
    return [dict(r) for r in con.execute(
        "SELECT id, card_name, slot, set_code, lang, finish, qty_a_caminho, "
        "qty_pendente_foto, qty_fechada, copy_ids, aviso FROM encomendas ORDER BY id")]


def log_de(p):
    return [l.split("\t") for l in Path(p).read_text(encoding="utf-8").splitlines()]


def foto_csv(texto, nome="foto.csv"):
    p = _TMP / nome
    p.write_text("name,set_code,collector_number,quantity,finish,language,"
                 "sub_collection,photo_path\n" + texto, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
def caso_mais_e_menos_nao_criam_copias():
    """O `+` e o `−` mexem SÓ na tabela `encomendas`. Nada na `copies`, nada na
    `copy_allocation` — é a regra. O `−` nunca vai abaixo de zero e, a zero, a
    linha apaga-se. Cada gesto deixa uma linha no `encomendas.log`."""
    repor()
    con = montavel()
    lg = _TMP / "enc1.log"
    r = encomendas.adicionar(con, "pm", "Swords to Plowshares", 2,
                             origem="Cardmarket", log_path=lg)
    assert r["qty_a_caminho"] == 2 and r["qty_pendente_foto"] == 0, r
    assert r["lang"] == "pt" and r["finish"] == "nonfoil", ("material da caixa", r)
    assert r["set_code"] is None, ("qualquer edição por omissão", r)
    assert not copias(con) and not alocacao(con), "o + criou uma cópia?!"
    # O mesmo `+` outra vez SOMA na mesma linha, não cria outra.
    r2 = encomendas.adicionar(con, "pm", "Swords to Plowshares", 1, log_path=lg)
    assert r2["id"] == r["id"] and r2["qty_a_caminho"] == 3, r2
    assert len(linhas(con)) == 1
    # O `−`: 3 → 1 → 0 (linha apagada), e mais um `−` não tira nada.
    assert encomendas.remover(con, r["id"], qty=2, log_path=lg)["tirado"] == 2
    assert linhas(con)[0]["qty_a_caminho"] == 1
    saiu = encomendas.remover(con, r["id"], qty=5, log_path=lg)
    assert saiu["tirado"] == 1 and saiu["apagadas"] == [r["id"]], saiu
    assert not linhas(con), "a zero, a linha apaga-se"
    assert encomendas.remover(con, r["id"], log_path=lg)["tirado"] == 0
    assert not copias(con) and not alocacao(con)
    acs = [l[1] for l in log_de(lg)]
    assert acs == ["+", "+", "-", "-"], acs
    assert log_de(lg)[0][2:7] == ["Swords to Plowshares", "qualquer edição · pt · nonfoil",
                                  "2", "UW Replenish", "Cardmarket"], log_de(lg)[0]
    print("+/-: so a tabela encomendas mexe; nunca abaixo de zero; log por gesto")


def caso_chegou_move_e_desfazer_volta():
    """«Chegou (N)»: a caminho → pendente de foto. «desfazer»: o inverso. E o
    «já a tenho» entra directamente em pendente. Continua sem cópia."""
    repor()
    con = montavel()
    lg = _TMP / "enc2.log"
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 2, log_path=lg)
    r = encomendas.chegou(con, slot="pm", nm="Swords to Plowshares", qty=1, log_path=lg)
    assert r["movido"] == 1
    l = linhas(con)[0]
    assert (l["qty_a_caminho"], l["qty_pendente_foto"]) == (1, 1), l
    r = encomendas.chegou(con, slot="pm", nm="Swords to Plowshares", log_path=lg)
    assert r["movido"] == 1 and linhas(con)[0]["qty_pendente_foto"] == 2
    assert encomendas.chegou(con, slot="pm", nm="Swords to Plowshares")["movido"] == 0
    r = encomendas.desfazer_chegou(con, slot="pm", nm="Swords to Plowshares",
                                   qty=1, log_path=lg)
    assert r["movido"] == 1
    l = linhas(con)[0]
    assert (l["qty_a_caminho"], l["qty_pendente_foto"]) == (1, 1), l
    # O «já a tenho»: pendente logo, sem cópia.
    j = encomendas.adicionar(con, "lg", "Force of Will", 1, estado=encomendas.PENDENTE,
                             origem=encomendas.ORIGEM_JA_TENHO, log_path=lg)
    assert (j["qty_a_caminho"], j["qty_pendente_foto"]) == (0, 1), j
    assert j["lang"] == "en" and j["finish"] == "foil", ("material do Legacy", j)
    # O `−` num pendente tira do pendente (é o anular do «já a tenho»).
    assert encomendas.remover(con, j["id"], estado=encomendas.PENDENTE)["tirado"] == 1
    assert not copias(con) and not alocacao(con)
    assert [l[1] for l in log_de(lg)] == ["+", "chegou", "chegou", "desfazer", "pendente"]
    print("chegou/desfazer movem entre os dois estados; ja-a-tenho nasce pendente")


def caso_desconta_no_comprar_e_no_fechar_tudo():
    """A falta fica (`missing`), a posse não mexe (`got`/`pct`), mas o «comprar»,
    o custo, o «fechar tudo», a wantlist, o Plano e a aba Comprar descontam o
    que está a caminho ou pendente de foto."""
    repor()
    con = montavel()
    c0, rep0, d0 = caixa(con)
    assert c0["comprar"] == 2 and c0["custo"] == 3.0, (c0["comprar"], c0["custo"])
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 1, log_path=_TMP / "e3.log")
    c, rep, d = caixa(con)
    m = next(x for x in rep["slots"] if x["slot"] == "pm")["missing"][0]
    assert m["missing"] == 2 and m["got"] == 0, ("a falta fica", m)
    assert m["comprar"] == 1 and m["a_caminho"] == 1 and m["cost"] == 1.5, m
    assert c["comprar"] == 1 and c["custo"] == 1.5 and c["pct"] == 0, c
    assert c["a_caminho"] == 1 and c["pfoto"] == 0 if "pfoto" in c else True
    assert rep["comprar_total"] == rep0["comprar_total"] - 1
    assert rep["custo_total"] == round(rep0["custo_total"] - 1.5, 2)
    assert rep["a_caminho_total"] == 1 and rep["pendente_foto_total"] == 0
    # A wantlist da caixa diz «1 a caminho» e mantém a linha com q=1.
    w = next(x for x in c["wantlist"] if x["nm"] == "Swords to Plowshares")
    assert w["q"] == 1 and w["acam"] == 1, w
    # O Plano (ordem de montagem) e a aba Comprar lêem o mesmo número.
    pl = next(x for x in rep["montagem"] if x["slot"] == "pm")
    assert pl["comprar"] == 1 and pl["custo"] == 1.5, pl
    # A aba Comprar: desde 2026-09-19 cada caixa compra as suas (o pm 1, o pm2
    # a sua 1 — até aí a partilha dava a compra ao pm e o pm2 ia lá buscar), e a
    # linha diz «1 a caminho» ao lado das 2 que ainda são compra.
    g = next(x for x in d["compras"] if x["nm"] == "Swords to Plowshares")
    assert g["q"] == 2 and g["acam"] == 1, g
    assert not [p for p in g["para"] if p.get("serve")], ("ninguém é servido", g)
    assert sorted((p["caixa"], p["q"]) for p in g["para"]) == \
        [("Enchantress", 1), ("UW Replenish", 1)], g["para"]
    assert d["resumo"]["a_caminho"] == 1 and d["resumo"]["custo"] == rep["custo_total"]
    # Pendente de foto desconta exactamente da mesma maneira.
    encomendas.chegou(con, slot="pm", nm="Swords to Plowshares", log_path=_TMP / "e3.log")
    c, rep, _d = caixa(con)
    assert c["comprar"] == 1 and rep["pendente_foto_total"] == 1 and rep["a_caminho_total"] == 0
    # E com tudo encomendado a linha FICA na wantlist com q=0 (é lá que vivem
    # o «−» e o «Chegou»), mas sai do total e do texto copiado.
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 1, log_path=_TMP / "e3.log")
    c, rep, _d = caixa(con)
    assert c["comprar"] == 0 and c["custo"] == 0, c
    w = next(x for x in c["wantlist"] if x["nm"] == "Swords to Plowshares")
    assert w["q"] == 0 and w["acam"] == 1 and w["pfoto"] == 1, w
    assert c["pct"] == 0 and c["tenho"] == 0, ("uma encomenda não é posse", c)
    print("desconto: comprar/custo/fechar tudo/wantlist/plano/comprar descontam; pct nao")


def caso_a_regra_de_material_da_caixa_manda():
    """O `+` valida contra a caixa e o catálogo, e recusa com o motivo."""
    repor()
    con = montavel()
    for kw, pedaco in (
            ({"set_code": "2x2"}, "2X2"),                  # depois do Scourge
            ({"lang": "en"}, "só usa PT"),                 # Premodern é PT
            ({"set_code": "xxx"}, "não existe no catálogo"),
    ):
        try:
            encomendas.adicionar(con, "pm", "Swords to Plowshares", 1, **kw)
            raise AssertionError(f"devia ter recusado {kw}")
        except ValueError as e:
            assert pedaco in str(e), (kw, str(e))
    try:
        encomendas.adicionar(con, "lg", "Force of Will", 1, finish="nonfoil")
        raise AssertionError("o Legacy é foil")
    except ValueError as e:
        assert "foil" in str(e), str(e)
    try:
        encomendas.adicionar(con, "pm", "Carta Que Nao Existe", 1)
        raise AssertionError("carta desconhecida")
    except ValueError as e:
        assert "catálogo" in str(e), str(e)
    try:
        encomendas.adicionar(con, "nao-ha", "Swords to Plowshares", 1)
        raise AssertionError("caixa desconhecida")
    except KeyError:
        pass
    # Uma edição da era, escrita, passa; e sem caixa vale en/nonfoil.
    r = encomendas.adicionar(con, "pm", "Swords to Plowshares", 1, set_code="ODY")
    assert r["set_code"] == "ody" and r["impressao"].startswith("ODY"), r
    r = encomendas.adicionar(con, None, "Brainstorm", 4, origem="loja")
    assert r["slot"] is None and (r["lang"], r["finish"]) == ("en", "nonfoil"), r
    assert not copias(con)
    print("material: a regra da caixa recusa 2x2/EN no Premodern, nonfoil no Legacy")


def caso_a_foto_fecha_a_encomenda_e_aloca():
    """A foto de uma carta pendente cria a cópia (com `photo_path`), fecha a
    encomenda, guarda o `copy_id` nela e ALOCA a cópia à caixa. A caixa passa a
    ter a carta — antes não tinha."""
    repor()
    con = montavel()
    lg = _TMP / "e5.log"
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 2, origem="Cardmarket",
                         preco=1.2, log_path=lg)
    encomendas.chegou(con, slot="pm", nm="Swords to Plowshares", log_path=lg)
    c, _rep, _d = caixa(con)
    assert c["pct"] == 0 and c["comprar"] == 0
    res = []
    ok, erros = collection.import_csv(
        con, foto_csv("Swords to Plowshares,4ed,0,2,nonfoil,pt,Colecção,IMG_1.jpg"),
        resultados=res)
    assert (ok, erros) == (1, []), (ok, erros)
    assert "fecham encomenda" in res[0]["motivo"] and "UW Replenish" in res[0]["motivo"], res
    cps = copias(con)
    assert len(cps) == 1 and cps[0]["quantity"] == 2, cps
    assert cps[0]["photo_path"] == "IMG_1.jpg" and cps[0]["set_code"] == "4ed", cps[0]
    assert "encomenda #" in cps[0]["notes"], cps[0]["notes"]
    assert alocacao(con) == [{"copy_id": cps[0]["id"], "slot": "pm", "quantity": 2}]
    l = linhas(con)[0]
    assert (l["qty_a_caminho"], l["qty_pendente_foto"], l["qty_fechada"]) == (0, 0, 2), l
    assert json.loads(l["copy_ids"]) == [cps[0]["id"]], l
    assert res[0]["copy_id"] == cps[0]["id"], res[0]
    c, _rep, _d = caixa(con)
    assert c["pct"] == 100 and c["comprar"] == 0, ("agora TEM a carta", c)
    assert c["montar"]["tirar"] == [], "já está na caixa: nada para tirar"
    assert not encomendas.listar(con), "fechada: já não está aberta"
    assert [l[1] for l in log_de(lg)] == ["+", "chegou"]
    # O import escreve no log AO LADO DA BASE (`db.pasta_dados()`), como o
    # `vendas.csv` — e este teste fixou o `MTGVAULT_DB` numa pasta temporária.
    ult = log_de(encomendas.ficheiro_log())[-1]
    assert ult[1] == "foto->copia" and ult[2] == "Swords to Plowshares", ult
    assert "alocada à caixa" in ult[-1] and f"copy_id {cps[0]['id']}" in ult[-1], ult
    # O preço pago vem da encomenda quando o CSV não o traz.
    assert con.execute("SELECT acquired_price FROM copies").fetchone()[0] == 1.2
    print("foto: cria a copia com photo_path, fecha a encomenda e aloca a caixa")


def caso_a_foto_que_nao_cumpre_deixa_a_encomenda_aberta():
    """A encomenda é PT para o Premodern e a foto trouxe uma impressão de 2022:
    a cópia entra na Colecção sem caixa, a encomenda fica aberta com o aviso, e
    a caixa continua a descontá-la (é a carta certa que ainda falta chegar).
    Nunca se lava a regra de material com um registo."""
    repor()
    con = montavel()
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 1,
                         estado=encomendas.PENDENTE, log_path=_TMP / "e6.log")
    res = []
    ok, erros = collection.import_csv(
        con, foto_csv("Swords to Plowshares,2x2,2,1,nonfoil,pt,Colecção,IMG_2.jpg"),
        resultados=res)
    assert (ok, erros) == (1, []), (ok, erros)
    assert "não cumpre a regra da caixa" in res[0]["motivo"], res[0]
    cps = copias(con)
    assert len(cps) == 1 and cps[0]["set_code"] == "2x2", cps
    assert alocacao(con) == [], "não se aloca o que a caixa recusa"
    l = linhas(con)[0]
    assert l["qty_pendente_foto"] == 1 and l["qty_fechada"] == 0, l
    assert l["aviso"] and "2X2" in l["aviso"], l["aviso"]
    c, rep, d = caixa(con)
    assert c["pct"] == 0, ("a 2x2 não serve a caixa", c["pct"])
    assert c["comprar"] == 1, ("2 em falta, 1 ainda pendente", c["comprar"])
    t = next(x for x in d["encomendas"]["pendentes"] if not x["na_base"])
    assert "2X2" in t["aviso"], t
    print("foto que nao cumpre: copia na Coleccao sem caixa, encomenda aberta com aviso")


def caso_a_prioridade_decide_quem_fecha():
    """Duas caixas do mesmo grupo com a mesma carta pendente: a foto de UMA cópia
    fecha a da caixa de maior prioridade (pm, #1), e a outra continua pendente."""
    repor()
    con = montavel()
    lg = _TMP / "e7.log"
    encomendas.adicionar(con, "pm2", "Swords to Plowshares", 1,
                         estado=encomendas.PENDENTE, log_path=lg)
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 1,
                         estado=encomendas.PENDENTE, log_path=lg)
    collection.import_csv(
        con, foto_csv("Swords to Plowshares,ody,1,1,nonfoil,pt,Colecção,IMG_3.jpg"))
    por_slot = {l["slot"]: l for l in linhas(con)}
    assert por_slot["pm"]["qty_fechada"] == 1 and por_slot["pm"]["qty_pendente_foto"] == 0
    assert por_slot["pm2"]["qty_fechada"] == 0 and por_slot["pm2"]["qty_pendente_foto"] == 1
    assert [a["slot"] for a in alocacao(con)] == ["pm"], alocacao(con)
    print("prioridade: a foto fecha a caixa #1 primeiro")


def caso_a_foto_de_uma_copia_sem_foto_liga_se():
    """Uma cópia que já existe SEM foto (entrou por CSV à mão) e a foto da MESMA
    impressão exacta: liga-se, não duplica. Com menos cópias na foto do que no
    lote, o lote parte-se e só a parte fotografada ganha a foto."""
    repor()
    con = montavel()
    cid = collection.add_copy(con, "Swords to Plowshares", set_code="4ed",
                              quantity=2, language="pt", sub_collection="Colecção")
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,?)",
                (cid, "pm", 2))
    con.commit()
    assert collection.copias_sem_foto(con)[0]["id"] == cid
    res = []
    collection.import_csv(
        con, foto_csv("Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_4.jpg"),
        resultados=res)
    assert "foto ligada" in res[0]["motivo"], res[0]
    cps = copias(con)
    assert len(cps) == 2 and sum(c["quantity"] for c in cps) == 2, ("partiu, não duplicou", cps)
    com = [c for c in cps if c["photo_path"] == "IMG_4.jpg"]
    assert len(com) == 1 and com[0]["quantity"] == 1, com
    # O lugar na caixa acompanha a parte fotografada.
    assert sorted(a["quantity"] for a in alocacao(con, "pm")) == [1, 1], alocacao(con)
    # A segunda foto liga-se ao que sobrou, e não há mais nada sem foto.
    collection.import_csv(
        con, foto_csv("Swords to Plowshares,4ed,0,1,nonfoil,pt,Colecção,IMG_5.jpg"))
    assert sum(c["quantity"] for c in copias(con)) == 2
    assert all(c["photo_path"] for c in copias(con)), copias(con)
    assert not collection.copias_sem_foto(con)
    # Uma foto de OUTRA impressão não se liga: entra como cópia nova.
    collection.import_csv(
        con, foto_csv("Swords to Plowshares,ody,1,1,nonfoil,pt,Colecção,IMG_6.jpg"))
    assert sum(c["quantity"] for c in copias(con)) == 3
    print("foto de copia sem foto: liga-se (partindo o lote), nao duplica")


def caso_ordem_e_quantidades_da_conciliacao():
    """(i) «edição por confirmar» acerta-se primeiro, (ii) depois a encomenda
    pendente, (iv) o resto entra normal. Uma foto de 4: 1 acerta, 2 fecham, 1
    entra — e o `copy_id` da linha traz as três cópias, que o `arrumar_fotos`
    liga todas à foto arrumada."""
    repor()
    con = montavel()
    rep = loadout.report(con)
    velha = loadout.registar_falta(con, rep, "pm", "Swords to Plowshares",
                                   quantidade=1, csv_path=_TMP / "f8.csv")
    encomendas.adicionar(con, "pm2", "Swords to Plowshares", 2,
                         estado=encomendas.PENDENTE, log_path=_TMP / "e8.log")
    pend = _TMP / "pend8"
    pend.mkdir(exist_ok=True)
    (pend / "IMG_8.jpg").write_bytes(b"\xff\xd8x")
    res = []
    ok, erros = collection.import_csv(
        con, foto_csv("Swords to Plowshares,4ed,0,4,nonfoil,pt,Colecção,IMG_8.jpg"),
        resultados=res)
    assert (ok, erros) == (1, []), (ok, erros)
    m = res[0]["motivo"]
    assert "1 de «já a tenho»" in m and "2 fecham encomenda" in m, m
    cps = copias(con)
    assert sum(c["quantity"] for c in cps) == 4, cps
    assert len(cps) == 3, ("acertada + encomenda + normal", cps)
    ids = [int(x) for x in str(res[0]["copy_id"]).split(",")]
    assert sorted(ids) == sorted(c["id"] for c in cps), (ids, cps)
    assert velha["copy_id"] in ids
    assert linhas(con)[0]["qty_fechada"] == 2
    f = collection.arrumar_fotos(con, res, pendentes=pend)
    assert f["ligadas"] == 3, f
    assert all(c["photo_path"] and c["photo_path"].endswith("IMG_8.jpg")
               for c in copias(con)), copias(con)
    print("conciliacao: por confirmar > encomenda > normal; as 3 copias ficam com a foto")


def caso_foto_sem_correspondencia_entra_como_hoje():
    repor()
    con = montavel()
    res = []
    ok, erros = collection.import_csv(
        con, foto_csv("Brainstorm,ice,5,4,nonfoil,en,Colecção,IMG_9.jpg"),
        resultados=res)
    assert (ok, erros) == (1, []) and res[0]["motivo"] == "", res
    cps = copias(con)
    assert len(cps) == 1 and cps[0]["quantity"] == 4 and cps[0]["photo_path"] == "IMG_9.jpg"
    assert not linhas(con) and not alocacao(con)
    print("sem correspondencia: entra como sempre")


def caso_avisos_quando_a_caixa_ja_nao_pede():
    """Uma encomenda de uma carta que a caixa não pede (ou a mais do que pede)
    fica visível com o aviso e não desconta noutra caixa."""
    repor()
    con = montavel()
    encomendas.adicionar(con, "lg", "Brainstorm", 2, log_path=_TMP / "e10.log")
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 3, log_path=_TMP / "e10.log")
    # Até 2026-09-19 o pm2 era SERVIDO pela compra partilhada do pm e uma
    # encomenda dele dava aviso ("compra partilhada"). Desde então cada caixa
    # compra as suas: a encomenda do pm2 desconta na compra DELE, sem aviso.
    encomendas.adicionar(con, "pm2", "Swords to Plowshares", 1, log_path=_TMP / "e10.log")
    c, rep, d = caixa(con, "lg")
    assert c["comprar"] == 1, ("o Brainstorm não desconta o Force of Will", c)
    pm = next(x for x in rep["slots"] if x["slot"] == "pm")
    assert pm["comprar"] == 0 and pm["a_caminho"] == 2, ("desconta só o que pede", pm)
    pm2 = next(x for x in rep["slots"] if x["slot"] == "pm2")
    assert pm2["comprar"] == 0 and pm2["a_caminho"] == 1, ("a do pm2 é dele", pm2)
    av = {(a["slot"], a["nm"]): a for a in rep["encomendas_avisos"]}
    assert av[("lg", "Brainstorm")]["porque"] == "a caixa já não a pede"
    assert av[("lg", "Brainstorm")]["q"] == 2
    assert av[("pm", "Swords to Plowshares")]["q"] == 1, av
    assert "a mais" in av[("pm", "Swords to Plowshares")]["porque"]
    assert ("pm2", "Swords to Plowshares") not in av, av
    assert len(d["encomendas"]["avisos"]) == 2
    print("avisos: a caixa ja nao pede / a mais do que pede, sem descontar noutra")


def caso_o_esperadas_md():
    """`pendentes/esperadas.md`: o que está pendente de foto, com o material
    esperado — e apaga-se quando não há nada."""
    repor()
    con = montavel()
    pasta = _TMP / "pend11"
    assert encomendas.escrever_esperadas(con, pasta) is None
    assert not (pasta / "esperadas.md").exists()
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 1,
                         estado=encomendas.PENDENTE, log_path=_TMP / "e11.log")
    p = encomendas.escrever_esperadas(con, pasta)
    txt = p.read_text(encoding="utf-8")
    assert "## UW Replenish — PT · ≤SCG" in txt, txt
    assert "1× **Swords to Plowshares** — qualquer edição · pt · nonfoil" in txt, txt
    encomendas.remover(con, slot="pm", nm="Swords to Plowshares", log_path=_TMP / "e11.log")
    assert encomendas.escrever_esperadas(con, pasta) is None
    assert not (pasta / "esperadas.md").exists(), "apaga-se quando fica vazio"
    print("esperadas.md: escreve o que espera e apaga-se quando nao ha nada")


# ---------------------------------------------------------------------------
# HTTP e CLI
# ---------------------------------------------------------------------------
class Pedido(webapp.Handler):
    """Um pedido de mentira: o mesmo handler, sem rede por baixo."""

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


def caso_endpoints_com_e_sem_token():
    repor()
    con = montavel()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    mais = {"delta": 1, "slot": "pm", "nm": "Swords to Plowshares", "set": "", "num": ""}
    cod, j = _post("/api/encomenda", mais, ip="192.168.1.99")
    assert cod == 403 and not linhas(con), (cod, j)
    cod, j = _post("/api/encomenda", mais)
    assert cod == 200 and "a caminho" in j["msg"], (cod, j)
    cod, j = _post("/api/encomenda", mais)
    assert cod == 200 and linhas(con)[0]["qty_a_caminho"] == 2, (cod, j)
    # Uma edição que a caixa recusa é 409 com o motivo, e não grava.
    cod, j = _post("/api/encomenda", {**mais, "set": "2x2"})
    assert cod == 409 and "2X2" in j["erro"], (cod, j)
    assert linhas(con)[0]["qty_a_caminho"] == 2
    cod, j = _post("/api/encomenda-chegou", {"slot": "pm", "nm": "Swords to Plowshares"})
    assert cod == 200 and linhas(con)[0]["qty_pendente_foto"] == 2, (cod, j)
    cod, j = _post("/api/encomenda-desfazer", {"id": linhas(con)[0]["id"], "q": 1})
    assert cod == 200 and linhas(con)[0]["qty_a_caminho"] == 1, (cod, j)
    cod, j = _post("/api/encomenda", {"delta": -1, "id": linhas(con)[0]["id"]})
    assert cod == 200 and linhas(con)[0]["qty_a_caminho"] == 0, (cod, j)
    cod, j = _post("/api/encomenda-chegou", {"slot": "pm", "nm": "Swords to Plowshares"})
    assert cod == 409, ("nada a caminho", cod, j)
    assert not copias(con) and not alocacao(con)
    # E o modo edição serve o separador com os dados (o índice e a parte).
    idx, partes = webapp.dados_deckboxes(True, "t")
    assert idx["encomendas"]["totais"]["pendente_foto"] == 1, idx["encomendas"]
    assert partes["encomendas"]["pendentes"][0]["nm"] == "Swords to Plowshares"
    webapp._CACHE.clear()
    print("endpoints: 403 sem token; +/chegou/desfazer/- gravam; 409 com o motivo")


def caso_cli_add_chegou_listar_json():
    """É por aqui que o Claude na nuvem regista o que ele diz no chat."""
    repor()
    con = montavel()
    dbs = con.execute("PRAGMA database_list").fetchall()
    base_, cat = dbs[0]["file"], dbs[1]["file"]

    def cli(*args):
        p = subprocess.run([sys.executable, "-m", "mtgvault.cli", "--db", base_,
                            "--catalog", cat, "encomendas", *args],
                           cwd=str(RAIZ), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return p.returncode, p.stdout, p.stderr

    cod, out, err = cli("add", "Swords to Plowshares", "--caixa", "pm", "--qty", "4",
                        "--origem", "Cardmarket", "--preco", "1.1", "--json")
    assert cod == 0, (cod, out, err)
    j = json.loads(out)
    assert j["qty_a_caminho"] == 4 and j["caixa"] == "UW Replenish", j
    cod, out, err = cli("add", "Swords to Plowshares", "--caixa", "pm", "--set", "2x2")
    assert cod == 2 and "2X2" in out, (cod, out, err)
    cod, out, err = cli("chegou", "Swords to Plowshares", "--caixa", "pm", "--qty", "1")
    assert cod == 0 and "pendente de foto" in out, (cod, out, err)
    cod, out, err = cli("listar", "--json")
    assert cod == 0, (cod, out, err)
    j = json.loads(out)
    assert j["a_caminho"] == 3 and j["pendente_foto"] == 1, j
    assert j["encomendas"][0]["origem"] == "Cardmarket"
    cod, out, err = cli("remover", "Swords to Plowshares", "--caixa", "pm", "--qty", "3")
    assert cod == 0 and "3×" in out, (cod, out, err)
    cod, out, err = cli("desfazer-chegou", "--id", str(j["encomendas"][0]["id"]))
    assert cod == 0 and "a caminho" in out, (cod, out, err)
    cod, out, err = cli("listar")
    assert cod == 0 and "1 a caminho · 0 pendentes" in out, (cod, out, err)
    assert not copias(con)
    print("CLI: add/chegou/remover/desfazer-chegou/listar --json")


# ---------------------------------------------------------------------------
# O que o BROWSER desenha
# ---------------------------------------------------------------------------
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
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8")), pagina


def caso_o_separador_desenha_nos_dois_modos():
    """A aba «📦 Encomendas» e a linha de compra: no modo edição com os `+`/`−`,
    «Chegou» e «desfazer»; no site publicado a MESMA informação sem um único
    botão. As cópias sem foto aparecem como «na base, sem foto»."""
    repor()
    con = montavel()
    encomendas.adicionar(con, "pm", "Swords to Plowshares", 2, origem="Cardmarket",
                         log_path=_TMP / "e14.log")
    encomendas.adicionar(con, "lg", "Force of Will", 1, estado=encomendas.PENDENTE,
                         log_path=_TMP / "e14.log")
    collection.add_copy(con, "Brainstorm", set_code="ice", quantity=3,
                        sub_collection="Colecção")
    r = _abas(con, True)
    if r is None:
        print("separador: sem `node`, saltado")
        return
    abas, _pag = r
    fila = abas["__fila"]
    assert "📦 Encomendas" in fila and "2 a caminho · 1 p/ foto" in fila, fila
    h = abas["encomendas"]
    assert "📷 Pendentes de foto" in h and "🚚 A caminho" in h and "Falta encomendar" in h
    assert "Force of Will" in h and "Swords to Plowshares" in h
    assert "na base, sem foto" in h and "Brainstorm" in h, h
    assert 'data-chegou="1"' in h and "Chegou (2)" in h, h
    assert 'data-desfazer="1"' in h, h
    assert 'data-enc="1"' in h and 'data-enc="-1"' in h
    assert "pendentes\\" in h, "diz onde largar a foto"
    # A linha de compra da caixa: «2 a caminho», 0×, botões.
    c = abas["pm"]
    assert "📦 2 a caminho" in c and "<b>0×</b>" in c and "Chegou (2)" in c, c[-3000:]
    # Toda encomendada: não há «já a tenho» a dar (o selector vive nele), mas o
    # `+`/`−` ficam — é por eles que se volta atrás.
    assert 'data-falta="1"' not in c and 'data-enc="-1"' in c
    # O texto copiado não leva a linha toda encomendada.
    cm = c.split('data-cmk="cm" readonly>')[1].split("</textarea>")[0]
    assert "Swords" not in cm, cm
    # Publicado: a informação fica, os botões não.
    pub, _p = _abas(con, False)
    hp = pub["encomendas"]
    assert "Swords to Plowshares" in hp and "2 cópias" in hp, hp
    for marca in ("data-enc=", "data-chegou", "data-desfazer", "data-falta"):
        assert marca not in hp and marca not in pub["pm"], marca
    assert "📦 2 a caminho" in pub["pm"]
    print("separador: tiles e botoes no modo edicao; so informacao no publicado")


def caso_o_mais_manda_o_pedido_certo():
    """No harness de node: o `+` de uma linha manda (slot, nm, delta, a edição do
    selector) para `api/encomenda`; o «Chegou» vai a `api/encomenda-chegou`."""
    if not shutil.which("node"):
        print("pedido do +: sem `node`, saltado")
        return
    repor()
    con = montavel()
    pag = Path(tempfile.mkdtemp()) / "deckboxes.html"
    pag.write_text(deckboxes.html_page(con, editable=True), encoding="utf-8")
    js = r"""
const pedidos = [];
fetch = async (url, o) => { pedidos.push([url, JSON.parse(o.body)]);
  return { ok: true, status: 200, json: async () => ({ ok: true, msg: 'ok' }) }; };
recarregar = async () => {};
const sel = { value: 'ody|1' };
const btn = { dataset: { enc: '1', slot: 'pm', nm: 'Swords to Plowshares', board: 'main' },
  closest: () => ({ querySelector: () => sel }), disabled: false };
const menos = { dataset: { enc: '-1', id: '7', nm: 'Swords to Plowshares' },
  closest: () => null, disabled: false };
const chg = { dataset: { slot: 'pm', nm: 'Swords to Plowshares' }, disabled: false };
resultado = (async () => {
  await encAjustar(btn); await encAjustar(menos); await encChegou(chg, false);
  await encChegou(chg, true);
  return pedidos;
})();
"""
    t = _TMP / "teste14.js"
    t.write_text(js, encoding="utf-8")
    p = subprocess.run(["node", str(Path(__file__).with_name("avaliar_js.js")),
                        str(pag), str(t)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
    pedidos = json.loads(p.stdout)
    assert pedidos[0] == ["api/encomenda", {"delta": 1, "slot": "pm",
                                            "nm": "Swords to Plowshares", "id": None,
                                            "set": "ody", "num": "1"}], pedidos[0]
    assert pedidos[1] == ["api/encomenda", {"delta": -1, "slot": None,
                                            "nm": "Swords to Plowshares", "id": 7,
                                            "set": "", "num": ""}], pedidos[1]
    assert pedidos[2][0] == "api/encomenda-chegou" and pedidos[2][1]["slot"] == "pm"
    assert pedidos[3][0] == "api/encomenda-desfazer"
    print("o + manda slot/nm/delta/edicao; o Chegou e o desfazer vao aos seus endpoints")


def run():
    for fn in (caso_mais_e_menos_nao_criam_copias,
               caso_chegou_move_e_desfazer_volta,
               caso_desconta_no_comprar_e_no_fechar_tudo,
               caso_a_regra_de_material_da_caixa_manda,
               caso_a_foto_fecha_a_encomenda_e_aloca,
               caso_a_foto_que_nao_cumpre_deixa_a_encomenda_aberta,
               caso_a_prioridade_decide_quem_fecha,
               caso_a_foto_de_uma_copia_sem_foto_liga_se,
               caso_ordem_e_quantidades_da_conciliacao,
               caso_foto_sem_correspondencia_entra_como_hoje,
               caso_avisos_quando_a_caixa_ja_nao_pede,
               caso_o_esperadas_md,
               caso_endpoints_com_e_sem_token,
               caso_cli_add_chegou_listar_json,
               caso_o_separador_desenha_nos_dois_modos,
               caso_o_mais_manda_o_pedido_certo):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
