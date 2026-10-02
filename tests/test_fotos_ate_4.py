"""UMA FOTO LEVA NO MÁXIMO QUATRO CARTAS (André, 2026-10-01).

À letra: *"organiza o Blue farm e CDEH por tipo de carta e ate 4 cartas por
foto"* e *"se sao 4 fotos, e 1 foto com as 4 cartas"*.

Isto substitui DUAS regras erradas que estiveram escritas no mesmo dia — *"a
fila conta cópias físicas: um playset dá quatro linhas"* e *"uma foto por linha,
e uma foto só valida cópias da MESMA carta"*. O que aqui se tranca, e cada caso
CHUMBA se a funcionalidade for retirada:

  1. um playset é **UMA** foto de quatro cartas, não quatro fotos;
  2. num deck singleton juntam-se até quatro cartas DIFERENTES, agrupadas **por
     tipo** (planeswalkers, criaturas, artefactos, encantamentos, instantâneos,
     feitiços, terras) e sem uma foto atravessar dois tipos;
  3. nenhuma foto passa das quatro cartas, e a linha que sozinha passa (as 29
     Snow-Covered Plains) enche fotos inteiras só dela e **di-lo**;
  4. uma foto NOVA com até quatro cartas valida **essas cartas todas de uma
     vez**, sejam cópias da mesma carta ou cartas diferentes agrupadas por tipo
     — e NÃO cria cópia nova, grava o `validado_em`, grava o `foto_anterior`, e
     a foto antiga continua no disco;
  5. uma foto NOVA com mais de quatro é **recusada inteira** e não escreve nada
     na base (saltar só a revalidação deixava-a criar cópias duplicadas);
  6. uma foto ANTIGA com mais de quatro cartas **não conta como validação**;
  7. uma foto no ARQUIVO (`data/fotos/anteriores/`) continua a ser encontrada, e
     a pasta de trabalho ganha quando a foto existe nas duas;
  8. arquivar MOVE e nunca apaga, e não pisa um ficheiro que já esteja lá;
  9. as fotos NOVAS arrumam-se por DECK (`data/fotos/<slot>/`), com o slot a vir
     do ALVO e nunca de adivinhar;
 10. as fotos PERDIDAS (sem ficheiro no disco) ficam marcadas e à cabeça;
 11. a ORDEM DE TRABALHO: os decks de lista única primeiro, os «de conversão»
     no fim e com a razão escrita.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        # O grupo com TECTO DE PLAYSET sobre o grupo inteiro é o que faz as
        # caixas competirem pelas mesmas cartas — é daqui que sai o «de
        # conversão» (ver `fases.de_conversao`).
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
         "playset_maximo": 4, "prioridade_por": "pct"},
        {"grupo": "cedh", "formatos": ["cedh"], "dedicado": True},
    ],
    "caixas": [
        {"slot": "cedh-a", "nome": "Blue Farm", "formato": "cedh",
         "fonte": "deck", "ref": "CEDH", "balde": "Colecção",
         "estado": "montada", "prioridade": 1},
        {"slot": "pm-a", "nome": "UW Replenish", "formato": "premodern",
         "fonte": "deck", "ref": "PM1", "balde": "Colecção",
         "estado": "montada", "prioridade": 2},
        {"slot": "pm-b", "nome": "Enchantress", "formato": "premodern",
         "fonte": "deck", "ref": "PM2", "balde": "Colecção",
         "estado": "montada", "prioridade": 3},
    ],
    "revalidacao": {"desde": "2026-09-01", "alvo": None},
    "reserva": {"limiar_pct": 20},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, db, fases, fotos,  # noqa: E402
                      loadout, revalidacao, sources)

# As pastas de fotos vão para a área temporária: nenhum caso toca na
# `pendentes/` a sério nem no `data/` dele.
PEND = _TMP / "pendentes"
PEND.mkdir(exist_ok=True)
collection.PENDENTES = PEND
collection.FOTOS_PROCESSADAS = PEND / "fotos processadas"
collection.APLICADO = collection.FOTOS_PROCESSADAS / "aplicado.csv"

HOJE = revalidacao.hoje()

# (nome, edição, data, acabamentos, preço, type_line)
CATALOGO = [
    ("Teferi, Hero of Dominaria", "dom", "2018-04-27", ["nonfoil"], 12.0,
     "Legendary Planeswalker — Teferi"),
    ("Esper Sentinel", "mh2", "2021-06-18", ["nonfoil"], 20.0,
     "Artifact Creature — Human Soldier"),
    ("Grand Abolisher", "big", "2024-04-19", ["nonfoil"], 15.0,
     "Creature — Human Cleric"),
    ("Mox Opal", "mbs", "2011-02-04", ["nonfoil"], 200.0,
     "Legendary Artifact"),
    ("Ancient Den", "mrd", "2003-10-02", ["nonfoil"], 3.0, "Artifact Land"),
    ("Urza's Saga", "mh2", "2021-06-18", ["nonfoil"], 40.0,
     "Enchantment Land — Urza's Saga"),
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"], 2.0, "Instant"),
    ("Demonic Tutor", "cmm", "2023-08-04", ["nonfoil"], 6.0, "Sorcery"),
    ("Ancient Tomb", "ltc", "2023-06-23", ["nonfoil"], 50.0, "Land"),
    ("Snow-Covered Plains", "mh1", "2019-06-14", ["nonfoil"], 1.0,
     "Basic Snow Land — Plains"),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fin, preco, tl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i + 1), tl,
             json.dumps(fin), rel,
             json.dumps({"legacy": "legal", "premodern": "legal",
                         "commander": "legal"})))
        for f in fin:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-20', ?)", (f"id-{i}", f, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    for nome, fmt, cartas in (
            ("CEDH", "cedh", [(nm, 1) for nm, *_r in CATALOGO]),
            ("PM1", "premodern", [("Swords to Plowshares", 4)]),
            ("PM2", "premodern", [("Swords to Plowshares", 4)])):
        con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?",
                          (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?, 'main')", (did, nm, q))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1, slot=None, foto=None, validado=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção")
    con.execute("UPDATE copies SET photo_path = ?, validado_em = ? WHERE id = ?",
                (foto, validado, cid))
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.commit()
    return cid


def repor(alvo=None, campanha=True):
    cfg = json.loads(json.dumps(CFG))
    if not campanha:
        cfg.pop("revalidacao")
    elif alvo is not None:
        cfg["revalidacao"]["alvo"] = alvo
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    fotos._CACHE.clear()
    return cfg


def jpg(pasta: Path, nome: str, dados: bytes = b"\xff\xd8\xffimagem") -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    p = pasta / nome
    p.write_bytes(dados)
    fotos._CACHE.clear()
    return p


def csv_de(linhas, path: Path) -> Path:
    cab = "name,set_code,collector_number,quantity,finish,language,photo_path"
    path.write_text("\n".join([cab] + [",".join(str(x) for x in l)
                                       for l in linhas]) + "\n",
                    encoding="utf-8")
    return path


# ===========================================================================
# 1-3. O AGRUPAMENTO: até 4 cartas, por tipo, sem partir uma linha
# ===========================================================================
def caso_um_playset_e_uma_foto_de_quatro_cartas():
    """*"se são 4 fotos, é 1 foto com as 4 cartas"* — as cópias da MESMA carta
    vão sempre juntas. A regra errada que aqui esteve dava QUATRO fotos."""
    fs = fotos.agrupar([{"nm": "Mox Opal", "copy_id": 1, "q": 4, "unit": 200.0}],
                       tipos={"Mox Opal": "Artifact"})
    assert len(fs) == 1, [f["itens"] for f in fs]
    assert fs[0]["cartas"] == 4 and fs[0]["linhas"] == 1, fs[0]
    assert fs[0]["valor"] == 800.0 and fs[0]["preco_max"] == 200.0
    assert not fs[0]["partida"]
    print("um playset e UMA foto de 4 cartas")


def caso_quatro_cartas_diferentes_na_mesma_foto_agrupadas_por_tipo():
    """Num deck singleton juntam-se até 4 cartas DIFERENTES, pela ordem dele:
    planeswalkers, criaturas, artefactos, encantamentos, instantâneos,
    feitiços, terras. E **uma foto nunca atravessa dois tipos**."""
    linhas = [{"nm": nm, "copy_id": i, "q": 1, "unit": 1.0}
              for i, (nm, *_r) in enumerate(CATALOGO[:9], 1)]
    tipos = {"Teferi, Hero of Dominaria": "Planeswalker",
             "Esper Sentinel": "Creature", "Grand Abolisher": "Creature",
             "Mox Opal": "Artifact", "Ancient Den": "Artifact",
             "Urza's Saga": "Enchantment", "Swords to Plowshares": "Instant",
             "Demonic Tutor": "Sorcery", "Ancient Tomb": "Land"}
    fs = fotos.agrupar(linhas, tipos=tipos)
    assert [f["tipo"] for f in fs] == ["Planeswalker", "Creature", "Artifact",
                                       "Enchantment", "Instant", "Sorcery",
                                       "Land"], [f["tipo"] for f in fs]
    # A foto das criaturas leva as DUAS (cartas diferentes, mesmo tipo).
    cri = next(f for f in fs if f["tipo"] == "Creature")
    assert cri["cartas"] == 2 and {i["nm"] for i in cri["itens"]} == {
        "Esper Sentinel", "Grand Abolisher"}, cri["itens"]
    # Nenhuma foto mistura tipos, e a numeração é seguida.
    assert [f["n"] for f in fs] == list(range(1, len(fs) + 1))
    assert len({f["foto_id"] for f in fs}) == len(fs)
    print("ate 4 cartas DIFERENTES por foto, agrupadas por tipo e sem as misturar")


def caso_nenhuma_foto_passa_de_quatro_cartas():
    """E a linha que SOZINHA passa das quatro (as 29 Snow-Covered Plains) enche
    fotos inteiras só dela — e a foto di-lo (`partida`), em vez de o esconder."""
    linhas = [{"nm": "Snow-Covered Plains", "copy_id": 1, "q": 29, "unit": 1.0},
              {"nm": "Ancient Tomb", "copy_id": 2, "q": 2, "unit": 50.0}]
    fs = fotos.agrupar(linhas, tipos={"Snow-Covered Plains": "Land",
                                      "Ancient Tomb": "Land"})
    assert all(f["cartas"] <= 4 for f in fs), [f["cartas"] for f in fs]
    sc = [f for f in fs if any(i["nm"] == "Snow-Covered Plains" for i in f["itens"])]
    assert len(sc) == 8 and sum(f["cartas"] for f in sc) == 29, \
        [f["cartas"] for f in sc]
    assert all(f["partida"] and f["linhas"] == 1 for f in sc)
    # A linha de 2 não se juntou ao resto da partida: fica na sua foto.
    at = [f for f in fs if any(i["nm"] == "Ancient Tomb" for i in f["itens"])]
    assert len(at) == 1 and at[0]["cartas"] == 2 and not at[0]["partida"]
    # Uma linha de 4 e outra de 1 do mesmo tipo são DUAS fotos: 4 + 1 > 4.
    # (Dentro do tipo a ordem é por NOME, logo a Ancient Den vem primeiro.)
    fs2 = fotos.agrupar(
        [{"nm": "Mox Opal", "copy_id": 1, "q": 4, "unit": 1.0},
         {"nm": "Ancient Den", "copy_id": 2, "q": 1, "unit": 1.0}],
        tipos={"Mox Opal": "Artifact", "Ancient Den": "Artifact"})
    assert [f["cartas"] for f in fs2] == [1, 4], [f["cartas"] for f in fs2]
    assert [f["itens"][0]["nm"] for f in fs2] == ["Ancient Den", "Mox Opal"]
    print("nenhuma foto passa de 4 cartas; a linha que sozinha passa di-lo")


def caso_a_barra_mede_fotos_e_diz_as_cartas_e_as_linhas():
    """A barra conta FOTOS (é a foto que é o gesto) e põe as cartas e as linhas
    ao lado — uma foto de 4 e uma de 1 não dão o mesmo trabalho."""
    fs = fotos.agrupar(
        [{"nm": "Mox Opal", "copy_id": 1, "q": 4, "unit": 10.0,
          "validado": HOJE},
         {"nm": "Ancient Den", "copy_id": 2, "q": 1, "unit": 1.0}],
        tipos={"Mox Opal": "Artifact", "Ancient Den": "Artifact"})
    b = fotos.barra(fs)
    assert b["fotos"] == 2 and b["cartas"] == 5 and b["linhas"] == 2, b
    assert b["feitas"] == 1 and b["falta"] == 1 and b["pct"] == 50.0, b
    assert b["cartas_feitas"] == 4, b
    print("a barra mede FOTOS e diz as cartas e as linhas ao lado")


# ===========================================================================
# 4-5. A TRAVA: uma foto valida no máximo 4 cartas
# ===========================================================================
def caso_uma_foto_de_quatro_cartas_diferentes_valida_as_quatro():
    """*"UMA FOTO COM ATÉ 4 CARTAS VALIDA ESSAS CARTAS TODAS DE UMA VEZ, sejam
    cópias da mesma carta ou cartas diferentes agrupadas por tipo."*

    E prova o fluxo ponta a ponta: (a) NÃO cria cópia nova; (b) grava o
    `validado_em`; (c) grava o `foto_anterior` com a foto antiga; (d) a antiga
    continua no disco.
    """
    repor(alvo={"tipo": "caixa", "slot": "cedh-a", "em": HOJE})
    con = base()
    velhas = {}
    for nm, sc in (("Esper Sentinel", "mh2"), ("Grand Abolisher", "big"),
                   ("Mox Opal", "mbs"), ("Ancient Den", "mrd")):
        v = f"velha-{sc}.jpg"
        jpg(collection.FOTOS_PROCESSADAS, v)
        velhas[nm] = v
        copia(con, nm, sc, q=1, slot="cedh-a", foto=v)
    antes = con.execute("SELECT COUNT(*) n, SUM(quantity) q FROM copies").fetchone()
    nova = "nova-4.jpg"
    jpg(PEND, nova)
    csv_path = csv_de([
        ("Esper Sentinel", "mh2", 2, 1, "nonfoil", "en", nova),
        ("Grand Abolisher", "big", 3, 1, "nonfoil", "en", nova),
        ("Mox Opal", "mbs", 4, 1, "nonfoil", "en", nova),
        ("Ancient Den", "mrd", 5, 1, "nonfoil", "en", nova),
    ], _TMP / "quatro.csv")
    res: list = []
    ok, erros = collection.import_csv(con, csv_path, resultados=res)
    assert not erros, erros
    assert ok == 4, ok
    # (a) NÃO cria cópia nova
    dep = con.execute("SELECT COUNT(*) n, SUM(quantity) q FROM copies").fetchone()
    assert (dep["n"], dep["q"]) == (antes["n"], antes["q"]), (dict(antes), dict(dep))
    assert all("revalidada" in r["motivo"] for r in res), [r["motivo"] for r in res]
    # (b) e (c) o `validado_em` e o `foto_anterior`
    for r in con.execute("""SELECT cp.validado_em v, cp.foto_anterior fa,
                                   cp.photo_path pp, c.name nm
                              FROM copies cp JOIN cards c
                                ON c.scryfall_id = cp.scryfall_id"""):
        assert r["v"] == HOJE, dict(r)
        assert r["fa"] == velhas[r["nm"]], dict(r)
        assert Path(r["pp"]).name == nova, dict(r)
    # (d) a antiga continua no disco
    for v in velhas.values():
        assert (collection.FOTOS_PROCESSADAS / v).is_file(), v
    # ... e a MESMA foto validou as quatro de uma vez.
    assert len({r["copy_id"] for r in res}) == 4
    repor()
    print("uma foto de 4 cartas diferentes valida as quatro, sem criar copias")


def caso_uma_foto_nova_com_mais_de_quatro_cartas_e_recusada_inteira():
    """A trava. E recusa-se INTEIRA: saltar só a revalidação deixava a linha cair
    na entrada normal e criar cópias NOVAS de cartas que já estão na base — uma
    duplicação em silêncio."""
    repor(alvo={"tipo": "caixa", "slot": "cedh-a", "em": HOJE})
    con = base()
    for nm, sc in (("Esper Sentinel", "mh2"), ("Grand Abolisher", "big"),
                   ("Mox Opal", "mbs"), ("Ancient Den", "mrd"),
                   ("Urza's Saga", "mh2")):
        copia(con, nm, sc, q=1, slot="cedh-a", foto=jpg(
            collection.FOTOS_PROCESSADAS, f"v-{nm[:4]}.jpg").name)
    antes = con.execute("SELECT COUNT(*) n, SUM(quantity) q FROM copies").fetchone()
    monte = "monte-5.jpg"
    jpg(PEND, monte)
    csv_path = csv_de([
        ("Esper Sentinel", "mh2", 2, 1, "nonfoil", "en", monte),
        ("Grand Abolisher", "big", 3, 1, "nonfoil", "en", monte),
        ("Mox Opal", "mbs", 4, 1, "nonfoil", "en", monte),
        ("Ancient Den", "mrd", 5, 1, "nonfoil", "en", monte),
        ("Urza's Saga", "mh2", 6, 1, "nonfoil", "en", monte),
    ], _TMP / "cinco.csv")
    res: list = []
    ok, erros = collection.import_csv(con, csv_path, resultados=res)
    assert ok == 0, f"{ok} linhas entraram com uma foto de 5 cartas"
    assert len(erros) == 5 and all("máximo 4" in e for e in erros), erros
    assert all(r["resultado"] == "erro" for r in res), res
    assert all("4 cartas" in r["motivo"] or "máximo 4" in r["motivo"] for r in res)
    # NADA se escreveu: nem cópia nova, nem um único `validado_em`.
    dep = con.execute("SELECT COUNT(*) n, SUM(quantity) q FROM copies").fetchone()
    assert (dep["n"], dep["q"]) == (antes["n"], antes["q"]), (dict(antes), dict(dep))
    assert con.execute("SELECT COUNT(*) n FROM copies WHERE validado_em IS NOT "
                       "NULL").fetchone()["n"] == 0
    # E a foto FICA em `pendentes/` (o `arrumar_fotos` só arruma as que entraram
    # todas) — é por aí que ele a vê em «fotos por resolver» e a volta a tirar.
    r = collection.arrumar_fotos(con, res, pendentes=PEND)
    assert monte in r["ficaram"], r
    assert (PEND / monte).is_file(), "a foto recusada saiu de pendentes/"
    # Uma linha de 4 cópias da MESMA carta continua a passar: são 4 cartas.
    assert fotos.valida(4) and not fotos.valida(5) and not fotos.valida(0)
    repor()
    print("uma foto nova com 5 cartas e recusada inteira e nao escreve nada")


def caso_uma_carta_nova_numa_foto_grande_entra_mas_nao_fica_validada():
    """A trava recusa a linha que **duplicaria** (há cópia por revalidar daquela
    impressão). Uma carta que a base NÃO tem é outra coisa: é uma compra a
    catalogar, e continua a entrar — **sem `validado_em`**, porque a foto não
    serve de prova. Recusar também essa era deixá-lo sem caminho para catalogar
    uma compra enquanto a campanha durasse."""
    repor()
    con = base()
    monte = "monte-novas.jpg"
    jpg(PEND, monte)
    csv_path = csv_de([
        ("Mox Opal", "mbs", 4, 2, "nonfoil", "en", monte),
        ("Ancient Den", "mrd", 5, 2, "nonfoil", "en", monte),
        ("Urza's Saga", "mh2", 6, 1, "nonfoil", "en", monte),
    ], _TMP / "novas5.csv")
    res: list = []
    ok, erros = collection.import_csv(con, csv_path, resultados=res)
    assert ok == 3 and not erros, (ok, erros)
    n = con.execute("SELECT COUNT(*) n, SUM(quantity) q FROM copies").fetchone()
    assert (n["n"], n["q"]) == (3, 5), dict(n)
    # Nada validado: a foto tem 5 cartas.
    assert con.execute("SELECT COUNT(*) n FROM copies WHERE validado_em IS NOT "
                       "NULL").fetchone()["n"] == 0
    assert len(revalidacao.copias_por_revalidar(con)) == 3
    # E o lote NÃO fica declarado depois da importação (era estado global).
    assert revalidacao.valida_esta_foto(monte) is True
    print("uma carta nova numa foto grande entra, mas nao fica validada")


def caso_uma_foto_antiga_com_mais_de_quatro_nao_conta_como_validacao():
    """As antigas de grupo têm média de quase cinco cartas e chegam a 33 num
    monte sem ordem: nelas não se consegue julgar o estado de cada carta, por
    isso não contam — as cópias delas continuam por revalidar."""
    repor()
    con = base()
    monte, par = "monte-antigo.jpg", "par-antigo.jpg"
    jpg(collection.FOTOS_PROCESSADAS, monte)
    jpg(collection.FOTOS_PROCESSADAS, par)
    copia(con, "Esper Sentinel", "mh2", q=4, foto=monte)
    copia(con, "Grand Abolisher", "big", q=2, foto=monte)   # 4 + 2 = 6 cartas
    copia(con, "Mox Opal", "mbs", q=4, foto=par)            # 4 cartas: valida
    maus = revalidacao.fotos_que_nao_validam(con)
    assert maus == {monte: 6}, maus
    # E nenhuma delas está validada: a campanha só valida com foto NOVA.
    assert con.execute("SELECT COUNT(*) n FROM copies WHERE validado_em IS NOT "
                       "NULL").fetchone()["n"] == 0
    assert len(revalidacao.copias_por_revalidar(con)) == 3
    print("uma foto antiga com mais de 4 cartas nao conta como validacao")


# ===========================================================================
# 7-9. ONDE ESTÁ A FOTO: arquivo, resolvedor e organização por deck
# ===========================================================================
def caso_uma_foto_no_arquivo_continua_a_ser_encontrada():
    """*"Não reescrevas as 723 linhas — faz o RESOLVEDOR procurar também no
    arquivo, com a pasta de trabalho a ganhar quando a foto existe nas duas."*

    Os `photo_path` da base dele são NOMES SIMPLES (`<uuid>.jpg`, zero com
    separador de pasta): valiam por estar numa pasta só.
    """
    repor()
    con = base()
    nome = "uuid-1.jpg"
    cid = copia(con, "Mox Opal", "mbs", q=1, foto=nome)
    # (a) na pasta de trabalho
    p = jpg(collection.FOTOS_PROCESSADAS, nome, b"\xff\xd8\xfftrabalho")
    assert fotos.resolver(nome) == p
    assert loadout.foto_da_copia(con, cid) == p, "o /foto do 8771 não a acha"
    # (b) arquivada: MOVE-SE e continua a ser encontrada, sem tocar na base.
    # (A contagem não se mede aqui: os casos partilham a pasta temporária, e o
    # que importa é ESTA foto. A contagem tem caso próprio.)
    r = fotos.arquivar(pendentes=PEND)
    assert nome in r["lista"] and r["bytes"] > 0, r
    assert not p.exists(), "a foto ficou na pasta de trabalho"
    arq = fotos.pasta_arquivo() / nome
    assert arq.is_file(), "a foto não chegou ao arquivo"
    assert fotos.resolver(nome) == arq
    assert loadout.foto_da_copia(con, cid) == arq
    assert con.execute("SELECT photo_path p FROM copies WHERE id = ?",
                       (cid,)).fetchone()["p"] == nome, \
        "reescreveu a linha da copies — era exactamente o que não se podia fazer"
    # (c) nas DUAS, a de trabalho ganha
    p2 = jpg(collection.FOTOS_PROCESSADAS, nome, b"\xff\xd8\xffnova")
    assert fotos.resolver(nome) == p2, "o arquivo ganhou à pasta de trabalho"
    print("a foto arquivada continua a ser encontrada; a de trabalho ganha")


def caso_arquivar_move_e_nunca_apaga_nem_pisa():
    """*"Mover normal ou git mv, nunca apagar; se o destino já tiver o ficheiro,
    não o pises — deixa-o e diz."*"""
    repor()
    base()
    # Numa pasta de trabalho PRÓPRIA, para a contagem ser exacta (os outros
    # casos partilham a temporária e deixam fotos lá).
    pend = _TMP / "arq-pend"
    proc = pend / "fotos processadas"
    arq = fotos.pasta_arquivo()
    jpg(arq, "ja-la.jpg", b"\xff\xd8\xffarquivo")
    jpg(proc, "ja-la.jpg", b"\xff\xd8\xfftrabalho")
    jpg(proc, "nova.jpg")
    # Um ficheiro que NÃO é imagem (o `aplicado.csv`) fica onde está.
    (proc / "aplicado.csv").write_text("at\n", encoding="utf-8")
    r = fotos.arquivar(pendentes=pend)
    assert r["movidas"] == 1 and r["ja_la"] == 1 and r["outros"] == 1, r
    assert r["lista_ja_la"] == ["ja-la.jpg"], r
    # a que já lá estava NÃO foi pisada, e a de trabalho também não desapareceu
    assert (arq / "ja-la.jpg").read_bytes() == b"\xff\xd8\xffarquivo"
    assert (proc / "ja-la.jpg").is_file()
    assert (arq / "nova.jpg").is_file()
    assert (proc / "aplicado.csv").is_file()
    print("arquivar move, nao apaga e nao pisa o que ja la esta")


def caso_as_fotos_novas_arrumam_se_por_deck():
    """*"Quando uma foto é importada com um ALVO definido, guarda-se em
    `data/fotos/<slot>/` e não num saco único. O slot vem do alvo da
    revalidação, não de adivinhar."*"""
    repor(alvo={"tipo": "caixa", "slot": "cedh-a", "em": HOJE})
    con = base()
    f = "da-caixa.jpg"
    jpg(PEND, f)
    copia(con, "Mox Opal", "mbs", q=1, slot="cedh-a",
          foto=jpg(collection.FOTOS_PROCESSADAS, "antiga.jpg").name)
    res: list = []
    collection.import_csv(con, csv_de(
        [("Mox Opal", "mbs", 4, 1, "nonfoil", "en", f)], _TMP / "deck.csv"),
        resultados=res)
    r = collection.arrumar_fotos(con, res, pendentes=PEND)
    assert r["destinos"] == ["fotos/cedh-a"], r
    assert (fotos.pasta_fotos() / "cedh-a" / f).is_file(), r
    pp = con.execute("SELECT photo_path p FROM copies").fetchone()["p"]
    assert pp == f"fotos/cedh-a/{f}", pp
    assert fotos.resolver(pp) is not None, "o caminho novo não se resolve"
    # O TIPO do alvo, quando não é uma caixa.
    assert fotos.pasta_do_alvo({"tipo": "venda"}).name == "venda"
    assert fotos.pasta_do_alvo({"tipo": "rl"}).name == "rl"
    assert fotos.pasta_do_alvo({"tipo": "coleccao"}).name == "coleccao"
    # SEM alvo não se adivinha o deck: vai para `sem-alvo/`, à vista.
    assert fotos.pasta_do_alvo(None).name == fotos.SEM_ALVO
    repor()
    print("as fotos novas arrumam-se em data/fotos/<slot>/, pelo ALVO")


# ===========================================================================
# 10-11. AS FOTOS PERDIDAS E A ORDEM DE TRABALHO
# ===========================================================================
def caso_as_fotos_perdidas_ficam_marcadas_e_a_cabeca():
    """*"Não as inventes nem limpes o campo. Marca essas linhas como «foto
    perdida», visível e no topo da prioridade da lista de por-revalidar: são as
    únicas que hoje não têm prova nenhuma."*"""
    repor()
    con = base()
    jpg(collection.FOTOS_PROCESSADAS, "existe.jpg")
    cid_ok = copia(con, "Ancient Tomb", "ltc", q=1, slot="cedh-a",
                   foto="existe.jpg")
    cid_mau = copia(con, "Mox Opal", "mbs", q=2, slot="cedh-a",
                    foto="desapareceu.jpg")
    perd = fotos.copias_sem_foto_no_disco(con)
    assert perd == {cid_mau: "desapareceu.jpg"}, perd
    # O campo NÃO se limpa: é a prova de que a foto existiu.
    assert con.execute("SELECT photo_path p FROM copies WHERE id = ?",
                       (cid_mau,)).fetchone()["p"] == "desapareceu.jpg"
    rep = loadout.report(con)
    r = fases.relatorio(con, rep)
    p = r["perdidas"]
    assert p["n_fotos"] == 1 and p["copias"] == 2, p
    assert [l["copy_id"] for l in p["linhas"]] == [cid_mau], p["linhas"]
    assert "sem prova nenhuma" in p["nota"]
    # Na fila da Fase 2 a foto que as leva fica MARCADA.
    f2 = next(f for f in r["fase2"]["filas"] if f["slot"] == "cedh-a")
    assert f2["barra"]["perdidas"] == 2, f2["barra"]
    marcada = [x for x in f2["fotos"] if x["perdidas"]]
    assert len(marcada) == 1 and marcada[0]["itens"][0]["copy_id"] == cid_mau
    # E na lista de por-revalidar vêm À CABEÇA do grupo.
    prog = revalidacao.progresso(con, rep)
    grp = next(c for c in prog["caixas"] if c["slot"] == "cedh-a")
    assert grp["linhas"][0]["copy_id"] == cid_mau, \
        [(l["copy_id"], l["foto_perdida"]) for l in grp["linhas"]]
    assert grp["perdidas"] == 2 and prog["total"]["perdidas"] == 2
    assert [l["copy_id"] for l in prog["perdidas"]] == [cid_mau]
    assert cid_ok != cid_mau
    print("as fotos perdidas ficam marcadas, com numero, e vem a cabeca")


def caso_os_decks_de_lista_unica_vem_primeiro():
    """*"Começa pelos decks que são LISTA ÚNICA e não são «de conversão» — os
    dois de cEDH. A família de Premodern monta-se por conversão: fica para
    depois."*

    A regra DERIVADA (não há coluna na base): o grupo de formato da caixa ordena
    as caixas por % completo (`prioridade_por: "pct"`) e há 2+ caixas nesse grupo
    — ordenar pela percentagem só faz sentido quando elas competem pelas MESMAS
    cartas. Tirar esse sinal do config devolve-as à frente, e tem de devolver.

    **O SINAL MUDOU a 2026-10-02 e a resposta é a mesma.** Era o `playset_maximo`
    do grupo (*"o tecto só existe porque as caixas trocam a carta entre si"*), e
    nesse dia ele mandou esquecer o tecto de playset do Premodern — o que deixava
    esta derivação a ler uma chave que já não existe e a responder «nenhuma caixa
    é de conversão», em silêncio, perdendo a ordem de trabalho da Fase 2.
    """
    repor()
    con = base()
    copia(con, "Mox Opal", "mbs", q=1, slot="cedh-a")
    copia(con, "Swords to Plowshares", "4ed", q=4, slot="pm-a")
    copia(con, "Swords to Plowshares", "4ed", q=4, slot="pm-b")
    rep = loadout.report(con)
    f2 = fases.fila_decks(con, rep)
    nomes = [f["nome"] for f in f2["filas"]]
    assert nomes[0] == "Blue Farm", nomes
    assert nomes[-2:] == ["UW Replenish", "Enchantress"] or \
        set(nomes[-2:]) == {"UW Replenish", "Enchantress"}, nomes
    conv = {f["nome"]: f["conversao"] for f in f2["filas"]}
    assert conv == {"Blue Farm": False, "UW Replenish": True,
                    "Enchantress": True}, conv
    assert f2["conversao"] == 2
    # E a razão fica ESCRITA em cada fila, não só na ordem.
    bf = next(f for f in f2["filas"] if f["nome"] == "Blue Farm")
    pm = next(f for f in f2["filas"] if f["nome"] == "UW Replenish")
    assert "lista única" in bf["nota"].lower(), bf["nota"]
    assert "conversão" in pm["nota"] and "depois" in pm["nota"], pm["nota"]
    # Sem a ordem por % no grupo, o Premodern deixa de ser «de conversão».
    cfg = json.loads(json.dumps(CFG))
    for r in cfg["regras_por_formato"]:
        r.pop("prioridade_por", None)
    assert set(fases.de_conversao(rep, cfg).values()) == {False}, \
        "a regra não está a sair do `prioridade_por: pct` do grupo"
    # E o tecto de playset JÁ NÃO é o sinal: um config com ele e sem a ordem por
    # % não devolve nenhuma caixa «de conversão». Sem esta linha, trocar o sinal
    # de volta passava sem ninguém dar por isso.
    cfg2 = json.loads(json.dumps(CFG))
    for r in cfg2["regras_por_formato"]:
        r.pop("prioridade_por", None)
        if r.get("grupo") == "premodern":
            r["playset_maximo"] = 4
    assert set(fases.de_conversao(rep, cfg2).values()) == {False}, \
        "o tecto de playset deixou de ser o sinal de «de conversão» (02/10/2026)"
    print("os decks de lista unica vem primeiro; os de conversao no fim, com razao")


# ===========================================================================
def main():
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for f in casos:
        try:
            f()
            print(f"  ok   {f.__name__}")
        except Exception as e:                               # noqa: BLE001
            falhas += 1
            print(f"  FAIL {f.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001, S110
            pass
    print(f"\n{len(casos) - falhas}/{len(casos)} casos ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
