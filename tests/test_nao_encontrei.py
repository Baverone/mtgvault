"""«SE NÃO MARQUEI, É PORQUE NÃO A TENHO»: o botão «Não encontrei estas».

André, 2026-09-09, à letra: *"no mtgvault, se eu não seleccionar no deck que meti
a carta, com checkmark, é porque eu não a tenho e estás a fazer confusão. Por
exemplo, no Cloud cEDH, dizes que tenho Chromatic Star mas eu não tenho, dizes
que tenho Grinding Station, mas também não tenho."*

As duas cópias estão na base porque foram fotografadas há meses e não estão dentro
de caixa nenhuma. O vault não tinha maneira de saber que já não estão na estante —
e enquanto não tivesse, a caixa ficava eternamente a dizer *"tens"* sobre uma carta
que ele não encontra. É o padrão do `event_tier`: nenhum passo dá erro.

O que aqui se tranca:

  1. **marcar tira a cópia da colecção** — a carta volta a ser COMPRA, a
     percentagem da caixa desce e nada é apagado (a linha fica, com a foto);
  2. **as linhas de «comprar» nunca entram** — não têm cópia nenhuma na base, e
     um `copy_id` que o painel desta caixa não ofereceu é recusado;
  3. **sai de TODAS as contas**: venda, valor, posse e galeria. O filtro vive num
     sítio só (`collection.jogaveis`) e há um caso que varre o código à procura
     do literal que ele substituiu;
  4. **«afinal encontrei» devolve tudo ao estado inicial** — medido antes/depois;
  5. **duas marcas da mesma cópia são uma só linha** (a segunda é um no-op);
  6. **o «já a tenho» e o «não encontrei» coexistem** — são inversos e não se
     pisam: a cópia que ele declarou fica dentro da caixa, a da gaveta sai;
  7. **a foto seguinte não ressuscita uma cópia não encontrada** — entra como
     cópia nova, que é a verdade;
  8. o botão **só se desenha enquanto sobram linhas por marcar**, e o pedido
     passa pelo mesmo handler HTTP (sem token, 403).

Não abre socket nenhum nem toca na rede.
"""
import csv as _csv
import io
import json
import os
import re
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
    # Um grupo só, sem regras de material: o que este ficheiro mede é a POSSE,
    # e uma regra de língua a recusar cópias só tornava as contas mais difíceis
    # de ler sem trancar nada de novo.
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil", "dedicado": False},
    ],
    "caixas": [
        {"slot": "cedh", "nome": "Cloud cEDH", "formato": "cedh",
         "fonte": "deck", "ref": "CLOUD", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, loadout, sources  # noqa: E402

import collection_gallery  # noqa: E402
import deckboxes  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

# As duas cartas que ele nomeou, mais uma para o caso do lote partido.
CATALOGO = [
    ("Chromatic Star", "5dn", "2004-06-04", ["nonfoil"]),
    ("Grinding Station", "5dn", "2004-06-04", ["nonfoil", "foil"]),
    ("Sol Ring", "c14", "2014-11-07", ["nonfoil"]),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fin) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               image_uri)
               VALUES (?,?,?,?,?,?,'en','rare','Artifact',1,'',?,?,?,0,0,?)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i),
             json.dumps(fin), rel, json.dumps({"cedh": "legal"}),
             f"http://exemplo/{i}.jpg"))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend) VALUES (?, 'cardmarket', 'nonfoil', "
                    "'2026-09-09', 3.0)", (f"id-{i}",))
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


def montavel(cartas=(("Chromatic Star", 1), ("Grinding Station", 1)),
             tenho=("Chromatic Star", "Grinding Station"), foto=True):
    """Uma caixa de cEDH com a lista pedida e as cópias que `tenho` diz.

    As cópias entram com `photo_path` porque foi assim que as duas cartas que
    motivaram isto entraram — e é a foto que a lista mostra.
    """
    con = base()
    deck(con, "CLOUD", "cedh", [(nm, q, "main") for nm, q in cartas])
    fotos = _TMP / "fotos"
    fotos.mkdir(exist_ok=True)
    for nm in tenho:
        f = fotos / f"{nm.replace(' ', '_')}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0jpeg de mentira")
        collection.add_copy(con, nm, set_code="5dn", quantity=1,
                            sub_collection="Colecção",
                            photo_path=str(f) if foto else None)
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def caixa(con, slot="cedh", editable=True):
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=editable)
    return next(c for c in d["caixas"] if c["slot"] == slot), rep, d


def copias(con):
    return [dict(r) for r in con.execute(
        """SELECT cp.id, cp.quantity, cp.nao_encontrada_em, cp.nao_encontrada_slot,
                  cp.photo_path, cp.notes, c.name
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            ORDER BY cp.id""")]


def log(caminho):
    if not Path(caminho).exists():
        return []
    with Path(caminho).open(encoding="utf-8", newline="") as fh:
        return list(_csv.DictReader(fh))


# ---------------------------------------------------------------------------
def caso_marcar_tira_a_copia_da_coleccao():
    """O caso dele: a Chromatic Star está na base, a caixa diz que ele a tem, e
    ele não a encontra. Depois de marcar, a caixa volta a pedi-la em COMPRAR — e
    a cópia continua na base, com a data, a caixa e a foto."""
    repor()
    con = montavel()
    reg = _TMP / "ne1.csv"
    c, rep, _d = caixa(con)
    assert c["pct"] == 100 and c["comprar"] == 0, (c["pct"], c["comprar"])
    star = next(x for x in copias(con) if x["name"] == "Chromatic Star")

    r = loadout.marcar_nao_encontradas(con, rep, "cedh", [star["id"]],
                                       csv_path=reg)
    assert r["copias"] == 1 and not r["saltadas"], r
    assert r["backup"] and Path(r["backup"]).exists(), r["backup"]

    depois = {x["id"]: x for x in copias(con)}
    assert len(depois) == 2, ("nada foi apagado", depois)
    assert depois[star["id"]]["nao_encontrada_em"], depois[star["id"]]
    assert depois[star["id"]]["nao_encontrada_slot"] == "cedh"
    assert depois[star["id"]]["photo_path"], "a foto de origem fica"

    c, _rep, d = caixa(con)
    assert c["pct"] == 50, c["pct"]
    assert [w["nm"] for w in c["wantlist"]] == ["Chromatic Star"], c["wantlist"]
    assert c["comprar"] == 1, c["comprar"]
    assert [m["nm"] for m in d["nao_encontradas"]] == ["Chromatic Star"]
    assert d["nao_encontradas"][0]["caixa"] == "Cloud cEDH"
    assert d["nao_encontradas"][0]["tem_foto"] is True

    linhas = log(reg)
    assert len(linhas) == 1 and linhas[0]["accao"] == "nao encontrada", linhas
    assert linhas[0]["carta"] == "Chromatic Star", linhas[0]
    assert linhas[0]["caixa"] == "Cloud cEDH" and linhas[0]["foto"], linhas[0]
    print("marcar: a carta volta a ser compra, a copia fica na base com a foto")


def caso_as_por_comprar_nunca_entram():
    """*"nunca as «por comprar»"*. Uma linha da wantlist não tem cópia nenhuma na
    base — não há nada para marcar — e um `copy_id` que o painel desta caixa não
    ofereceu é recusado, mesmo existindo na colecção."""
    repor()
    con = montavel(cartas=(("Chromatic Star", 1), ("Sol Ring", 1)),
                   tenho=("Chromatic Star", "Grinding Station"))
    c, rep, _d = caixa(con)
    assert [w["nm"] for w in c["wantlist"]] == ["Sol Ring"], c["wantlist"]

    s = next(x for x in rep["slots"] if x["slot"] == "cedh")
    oferta = {m["nm"] for m in
              loadout.copias_por_encontrar(s, loadout.caixas_de_deck(rep["slots"]))}
    assert oferta == {"Chromatic Star"}, ("o Sol Ring é compra", oferta)

    # A Grinding Station existe na colecção mas esta caixa não a pede: um pedido
    # cru com o id dela não pode tirá-la de circulação.
    gs = next(x for x in copias(con) if x["name"] == "Grinding Station")
    r = loadout.marcar_nao_encontradas(con, rep, "cedh", [gs["id"]],
                                       csv_path=_TMP / "ne2.csv")
    assert r["copias"] == 0 and r["saltadas"], r
    assert "não estava nesta caixa" in r["saltadas"][0]["porque"], r
    assert not any(x["nao_encontrada_em"] for x in copias(con)), copias(con)
    assert r["backup"] is None, "não se faz backup para não fazer nada"
    print("por comprar: fora da oferta, e um id de outra caixa e recusado")


def caso_sai_da_venda_do_valor_e_da_galeria():
    """*"sai da colecção para todos os efeitos"*. O que aqui se mede são as
    quatro contas que não passam pela caixa: a lista de venda, o valor da
    colecção, a posse total e a galeria."""
    repor()
    from mtgvault import paginas                            # noqa: PLC0415

    # Duas Chromatic Star para uma caixa que só pede uma: a segunda é excedente
    # e está na lista de venda. Ele vai buscar a que a caixa quer e não a acha.
    con = montavel(cartas=(("Chromatic Star", 1),), tenho=("Chromatic Star",))
    collection.add_copy(con, "Chromatic Star", set_code="5dn", quantity=1,
                        sub_collection="Colecção")
    rep = loadout.report(con)
    assert [v["nm"] for v in rep["venda"]] == ["Chromatic Star"], rep["venda"]
    assert rep["total"] == 3.0, rep["total"]
    valor_antes = sum(x["total"] for x in collection.collection_value(con))
    assert paginas.posse_total(con)["Chromatic Star"] == 2
    galeria_antes = len(collection_gallery._cards(con))

    s = next(x for x in rep["slots"] if x["slot"] == "cedh")
    ids = [m["copy_id"] for m in
           loadout.copias_por_encontrar(s, loadout.caixas_de_deck(rep["slots"]))]
    r = loadout.marcar_nao_encontradas(con, rep, "cedh", ids,
                                       csv_path=_TMP / "ne3.csv")
    assert r["copias"] == 1, r

    # A cópia que sobra passa a servir a caixa: já não há excedente nenhum, e o
    # valor, a posse e a galeria contam menos uma. O excedente de ontem era
    # exactamente a carta que ele não tem.
    rep = loadout.report(con)
    assert rep["venda"] == [] and rep["total"] == 0.0, rep["venda"]
    valor = sum(x["total"] for x in collection.collection_value(con))
    assert valor == valor_antes - 3.0, (valor, valor_antes)
    assert paginas.posse_total(con)["Chromatic Star"] == 1
    assert len(collection_gallery._cards(con)) == galeria_antes - 1
    print("venda, valor, posse e galeria: deixam de a contar")


def caso_afinal_encontrei_devolve_tudo():
    """A reversão põe o vault exactamente como estava — é o que permite carregar
    no botão sem medo, e é a razão de nada ser apagado."""
    repor()
    con = montavel()
    reg = _TMP / "ne4.csv"
    c0, rep, d0 = caixa(con)
    antes = (c0["pct"], c0["comprar"], c0["tenho"], d0["resumo"]["custo"],
             d0["resumo"]["venda"])
    star = next(x for x in copias(con) if x["name"] == "Chromatic Star")
    loadout.marcar_nao_encontradas(con, rep, "cedh", [star["id"]], csv_path=reg)
    c1, _rep, _d1 = caixa(con)
    assert c1["pct"] != antes[0], "a marca mexeu mesmo nos números"

    r = loadout.devolver_a_coleccao(con, [star["id"]], csv_path=reg)
    assert r["copias"] == 1 and r["linhas"][0]["nm"] == "Chromatic Star", r
    c2, _rep, d2 = caixa(con)
    assert (c2["pct"], c2["comprar"], c2["tenho"], d2["resumo"]["custo"],
            d2["resumo"]["venda"]) == antes, (c2["pct"], antes)
    assert not any(x["nao_encontrada_em"] for x in copias(con)), copias(con)
    assert [l["accao"] for l in log(reg)] == ["nao encontrada", "encontrada"]

    # E um `copy_id` de uma cópia normal não faz nada: este botão só devolve o
    # que ele próprio tirou.
    assert loadout.devolver_a_coleccao(con, [star["id"]], csv_path=reg)["copias"] == 0
    print("afinal encontrei: tudo volta ao estado inicial, e so o que saiu volta")


def caso_duas_marcas_sao_uma_so_linha():
    """*"Se a mesma cópia for marcada «não encontrada» duas vezes em caixas
    diferentes, é uma só linha."* Uma página aberta há duas horas pode mandar a
    mesma cópia outra vez: a segunda é um no-op — sem linha nova no CSV e sem
    backup, que é o que mostra que não se escreveu nada."""
    repor()
    con = montavel()
    reg = _TMP / "ne5.csv"
    rep = loadout.report(con)
    star = next(x for x in copias(con) if x["name"] == "Chromatic Star")
    loadout.marcar_nao_encontradas(con, rep, "cedh", [star["id"]], csv_path=reg)
    # O `rep` velho ainda a oferece — é exactamente a página desactualizada.
    r = loadout.marcar_nao_encontradas(con, rep, "cedh", [star["id"]], csv_path=reg)
    assert r["copias"] == 0 and r["backup"] is None, r
    assert "já estava marcada" in r["saltadas"][0]["porque"], r
    assert len(log(reg)) == 1, log(reg)
    assert len([x for x in copias(con) if x["nao_encontrada_em"]]) == 1
    print("duas marcas: uma so linha, sem backup nem CSV a segunda vez")


def caso_o_lote_parte_se_quando_metade_ja_esta_na_caixa():
    """A armadilha do `lots()`: um lote de 2 com 1 já sleevado na caixa e 1 na
    gaveta são duas linhas com o MESMO `copies.id`. Marcar a linha inteira tirava
    da caixa uma cópia que está lá dentro — parte-se o lote."""
    repor()
    con = montavel(cartas=(("Chromatic Star", 2),), tenho=())
    collection.add_copy(con, "Chromatic Star", set_code="5dn", quantity=2,
                        sub_collection="Colecção")
    lote = copias(con)[0]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at) "
                "VALUES (?, 'cedh', 1, datetime('now'))", (lote["id"],))
    con.commit()
    rep = loadout.report(con)
    r = loadout.marcar_nao_encontradas(con, rep, "cedh", [lote["id"]],
                                       csv_path=_TMP / "ne6.csv")
    assert r["copias"] == 1, ("só a que estava na gaveta", r)
    cps = {x["id"]: x for x in copias(con)}
    assert len(cps) == 2, cps
    assert cps[lote["id"]]["quantity"] == 1 and not cps[lote["id"]]["nao_encontrada_em"]
    nova = next(x for x in cps.values() if x["id"] != lote["id"])
    assert nova["quantity"] == 1 and nova["nao_encontrada_em"], nova
    assert nova["photo_path"] == cps[lote["id"]]["photo_path"], "herda a foto"
    # A cópia que está dentro da caixa continua lá.
    assert con.execute("SELECT SUM(quantity) q FROM copy_allocation "
                       "WHERE slot = 'cedh'").fetchone()["q"] == 1
    print("lote partido: sai a da gaveta, fica a que esta sleevada")


def caso_o_ja_a_tenho_e_o_nao_encontrei_coexistem():
    """Os dois botões são inversos e não se pisam. A sequência dele: a caixa pede
    2, ele tem 1 na gaveta, dá check em «já a tenho» na que falta (cria cópia
    dentro da caixa), depois não encontra a da gaveta, e por fim encontra-a.

    A cópia declarada NUNCA é oferecida ao «não encontrei»: está dentro da caixa,
    não é uma ida à gaveta."""
    repor()
    con = montavel(cartas=(("Chromatic Star", 2),), tenho=("Chromatic Star",))
    gaveta = copias(con)[0]
    rep = loadout.report(con)
    f = loadout.registar_falta(con, rep, "cedh", "Chromatic Star", quantidade=1,
                               csv_path=_TMP / "ne7-faltas.csv")
    c, rep, _d = caixa(con)
    assert c["pct"] == 100 and c["comprar"] == 0, (c["pct"], c["comprar"])

    s = next(x for x in rep["slots"] if x["slot"] == "cedh")
    oferta = [m["copy_id"] for m in
              loadout.copias_por_encontrar(s, loadout.caixas_de_deck(rep["slots"]))]
    assert oferta == [gaveta["id"]], ("a declarada está na caixa", oferta)

    r = loadout.marcar_nao_encontradas(con, rep, "cedh", oferta,
                                       csv_path=_TMP / "ne7.csv")
    assert r["copias"] == 1, r
    c, _rep, _d = caixa(con)
    assert c["comprar"] == 1 and c["pct"] == 50, (c["comprar"], c["pct"])
    # A cópia do «já a tenho» ficou como estava: dentro da caixa e à espera da foto.
    cps = {x["id"]: x for x in copias(con)}
    assert not cps[f["copy_id"]]["nao_encontrada_em"], cps[f["copy_id"]]
    assert collection.MARCA_POR_CONFIRMAR in cps[f["copy_id"]]["notes"]
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation WHERE copy_id = ?",
                       (f["copy_id"],)).fetchone()["c"] == 1

    loadout.devolver_a_coleccao(con, [gaveta["id"]], csv_path=_TMP / "ne7.csv")
    c, _rep, _d = caixa(con)
    assert c["comprar"] == 0 and c["pct"] == 100, (c["comprar"], c["pct"])
    print("ja a tenho + nao encontrei: inversos, e nao se pisam")


def caso_a_foto_nao_ressuscita_uma_copia_nao_encontrada():
    """Uma cópia do «já a tenho» que ele depois não encontra sai de circulação —
    e a foto que chegue a seguir **não** a acerta: acertá-la era ressuscitar em
    silêncio a cópia que ele disse que não tem. Entra como cópia nova, que é o que
    a foto prova."""
    repor()
    con = montavel(cartas=(("Chromatic Star", 1),), tenho=())
    rep = loadout.report(con)
    f = loadout.registar_falta(con, rep, "cedh", "Chromatic Star", quantidade=1,
                               csv_path=_TMP / "ne8-faltas.csv")
    # Ele desmonta a caixa: a cópia declarada volta a ser uma ida à gaveta.
    loadout.desmontar_caixa(con, "cedh", "Cloud cEDH",
                            log_path=_TMP / "desmontar.log")
    rep = loadout.report(con)
    r = loadout.marcar_nao_encontradas(con, rep, "cedh", [f["copy_id"]],
                                       csv_path=_TMP / "ne8.csv")
    assert r["copias"] == 1, r
    assert not collection.copias_por_confirmar(con), "já não espera foto nenhuma"

    csvf = _TMP / "foto-ne.csv"
    csvf.write_text("name,set_code,quantity,sub_collection\n"
                    "Chromatic Star,5dn,1,Colecção\n", encoding="utf-8")
    ok, erros = collection.import_csv(con, csvf)
    assert (ok, erros) == (1, []), (ok, erros)
    cps = copias(con)
    assert len(cps) == 2, ("uma cópia NOVA, não a que estava marcada", cps)
    assert cps[0]["nao_encontrada_em"] and not cps[1]["nao_encontrada_em"], cps
    c, _rep, _d = caixa(con)
    assert c["pct"] == 100 and c["comprar"] == 0, (c["pct"], c["comprar"])
    print("foto: entra como copia nova, nao ressuscita a nao encontrada")


def caso_a_base_do_andre_abre_na_mesma():
    """A base dele foi criada ANTES destas colunas, e o `db.init` tem de a abrir.

    O defeito, apanhado ao medir contra a cópia da `vault.db` a sério: o
    `schema.sql` corre INTEIRO antes do `_migrate()`, e um `CREATE INDEX` sobre a
    coluna nova rebentava com *"no such column: nao_encontrada_em"* — em todas as
    páginas e no `daily`. Um `CREATE TABLE IF NOT EXISTS` é indiferente à ordem;
    um índice sobre uma coluna nova não é. Os testes não o apanhavam porque criam
    sempre bases de raiz, onde a coluna já vem do `CREATE TABLE`.
    """
    repor()
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    con.execute("ALTER TABLE copies DROP COLUMN nao_encontrada_em")
    con.execute("ALTER TABLE copies DROP COLUMN nao_encontrada_slot")
    con.commit()
    cols = {r["name"] for r in con.execute("PRAGMA table_info(copies)")}
    assert "nao_encontrada_em" not in cols, "a base ficou como a dele"

    db.init(con)                          # é isto que rebentava
    cols = {r["name"] for r in con.execute("PRAGMA table_info(copies)")}
    assert {"nao_encontrada_em", "nao_encontrada_slot"} <= cols, cols
    assert con.execute("SELECT COUNT(*) c FROM copies cp WHERE "
                       + collection.jogaveis()).fetchone()["c"] == 0
    print("base antiga: o _migrate acrescenta as colunas e o init nao rebenta")


def caso_o_filtro_vive_num_sitio_so():
    """O `cp.purpose = 'player'` estava escrito à mão em catorze consultas. Com
    uma coluna nova a decidir o mesmo, a primeira que se esquecesse voltava a
    dizer-lhe que tem a carta — sem um único erro. Este caso varre o código.

    A `migracao` é a excepção assumida: uma cópia não encontrada continua a viver
    numa gaveta e muda de gaveta com todas as outras (o que ela NÃO faz é entrar
    na `copy_allocation`, e isso tem a sua própria linha).
    """
    excepcoes = {"mtgvault/collection.py", "mtgvault/migracao.py"}
    maus = []
    for f in sorted(RAIZ.glob("*.py")) + sorted((RAIZ / "mtgvault").glob("*.py")):
        rel = f.relative_to(RAIZ).as_posix()
        if rel in excepcoes:
            continue
        for i, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"purpose\s*=\s*'player'", linha):
                maus.append(f"{rel}:{i}")
    assert not maus, ("estas consultas contam a colecção sem passar pelo "
                      "collection.jogaveis(): " + ", ".join(maus))
    print(f"filtro: num sitio so ({len(excepcoes)} excepcoes assumidas)")


# ---------------------------------------------------------------------------
# O que o BROWSER desenha
# ---------------------------------------------------------------------------
def _abas(con, editable, feitos=None):
    """`{aba: html}` + `barra:<aba>`, corrido no harness de node."""
    if not shutil.which("node"):
        return None
    pasta = Path(tempfile.mkdtemp())
    pagina = pasta / "deckboxes.html"
    pagina.write_text(deckboxes.html_page(con, editable=editable), encoding="utf-8")
    dump = pasta / "abas.json"
    args = ["node", str(Path(__file__).with_name("render_deckboxes.js")),
            str(pagina), str(dump)]
    if feitos is not None:
        semente = pasta / "feitos.json"
        semente.write_text(json.dumps(feitos), encoding="utf-8")
        args.append(str(semente))
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def _ids_dos_vistos(con, slot="cedh"):
    """Os ids que a grelha desenha, pela MESMA regra do `vistoId` do browser."""
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=True)
    c = next(x for x in d["caixas"] if x["slot"] == slot)
    return [f'mt|{slot}|{m["copy_id"]}|{m["nm"]}|{m["board"]}'
            for b in c["montar"]["blocos"] for m in b["movs"]]


def caso_o_botao_so_aparece_com_linhas_por_marcar():
    """*"o botão só aparece quando há linhas por marcar e o deck não está todo
    marcado"*. Com tudo marcado não há nada que ele não tenha encontrado, e um
    botão que aí não faz nada seria ruído fixo no fundo do ecrã."""
    repor()
    con = montavel()
    abas = _abas(con, True)
    if abas is None:
        print("botão «não encontrei»: sem `node`, saltado")
        return
    barra = abas["barra:cedh"]
    assert 'id="b-nenc"' in barra, barra
    assert "Não encontrei" in barra, barra

    todos = {i: 1 for i in _ids_dos_vistos(con)}
    assert len(todos) == 2, todos
    cheia = _abas(con, True, feitos=todos)["barra:cedh"]
    assert "2 de 2 cópias marcadas" in cheia, cheia
    assert 'id="b-nenc"' not in cheia, ("com tudo marcado não há botão", cheia)

    # E no site publicado a barra não existe de todo (não há endpoint).
    assert 'id="b-nenc"' not in _abas(con, False)["barra:cedh"]
    print("barra: botao com linhas por marcar, e nada com tudo marcado")


def caso_a_lista_mostra_a_foto_e_o_afinal_encontrei():
    """A aba «Não encontradas»: a miniatura da foto de origem (é a única prova de
    que a carta existiu) e o botão que a devolve. O botão só no modo edição."""
    repor()
    con = montavel()
    rep = loadout.report(con)
    star = next(x for x in copias(con) if x["name"] == "Chromatic Star")
    loadout.marcar_nao_encontradas(con, rep, "cedh", [star["id"]],
                                   csv_path=_TMP / "ne9.csv")
    abas = _abas(con, True)
    if abas is None:
        print("aba «Não encontradas»: sem `node`, saltado")
        return
    html = abas["naoenc"]
    assert "Não encontradas" in html and "Chromatic Star" in html, html[:900]
    assert f'src="foto?copy={star["id"]}' in html, html[:1500]
    assert f'data-enc="{star["id"]}"' in html, html[:1500]
    assert "Cloud cEDH" in html, html[:1500]
    assert "🔍 Não encontradas" in abas["__fila"], abas["__fila"][:600]

    pub = _abas(con, False)
    assert "Chromatic Star" in pub["naoenc"], "a lista vê-se no site publicado"
    assert "data-enc" not in pub["naoenc"], "mas o botão não"
    assert "foto?copy=" not in pub["naoenc"], "nem a foto, que vive no PC"
    print("aba: foto + «afinal encontrei» no modo edicao, so a lista no publicado")


def caso_o_pedido_passa_pelo_handler():
    """O caminho todo, pelo mesmo handler HTTP que o telemóvel usa. Sem token é
    403 — e nesse caso nada pode ter saído da colecção."""
    repor()
    con = montavel()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    star = next(x for x in copias(con) if x["name"] == "Chromatic Star")
    corpo = json.dumps({"act": "nao-encontrei", "slot": "cedh",
                        "copias": [star["id"]]})

    p = Pedido("/api/caixa", corpo)
    p.do_POST()
    assert p.codigo == 403, (p.codigo, p.corpo)
    assert not any(x["nao_encontrada_em"] for x in copias(con)), "nada saiu"

    p = Pedido("/api/caixa", corpo, ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo[:400])
    j = json.loads(p.corpo)
    assert j["copias"] == [star["id"]], j
    assert "Chromatic Star" in j["msg"], j
    assert any(x["nao_encontrada_em"] for x in copias(con)), copias(con)

    # E o `/foto` serve a imagem que a lista mostra — mas só a quem tem token.
    f = Pedido(f'/foto?copy={star["id"]}')
    f.do_GET()
    assert f.codigo == 403, (f.codigo, f.corpo[:200])
    f = Pedido(f'/foto?copy={star["id"]}', ip="127.0.0.1")
    f.do_GET()
    assert f.codigo == 200 and "jpeg de mentira" in f.corpo, (f.codigo, f.corpo[:80])

    p = Pedido("/api/caixa", json.dumps({"act": "encontrei",
                                         "copias": [star["id"]]}), ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo[:400])
    assert not any(x["nao_encontrada_em"] for x in copias(con)), "voltou"
    # Segunda vez: não há nada para devolver, e diz-se em vez de fingir.
    p = Pedido("/api/caixa", json.dumps({"act": "encontrei",
                                         "copias": [star["id"]]}), ip="127.0.0.1")
    p.do_POST()
    assert "erro" in json.loads(p.corpo), p.corpo[:300]
    print("handler: 403 sem token, marca, serve a foto e devolve")


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


def run():
    for fn in (caso_marcar_tira_a_copia_da_coleccao,
               caso_as_por_comprar_nunca_entram,
               caso_sai_da_venda_do_valor_e_da_galeria,
               caso_afinal_encontrei_devolve_tudo,
               caso_duas_marcas_sao_uma_so_linha,
               caso_o_lote_parte_se_quando_metade_ja_esta_na_caixa,
               caso_o_ja_a_tenho_e_o_nao_encontrei_coexistem,
               caso_a_foto_nao_ressuscita_uma_copia_nao_encontrada,
               caso_a_base_do_andre_abre_na_mesma,
               caso_o_filtro_vive_num_sitio_so,
               caso_o_botao_so_aparece_com_linhas_por_marcar,
               caso_a_lista_mostra_a_foto_e_o_afinal_encontrei,
               caso_o_pedido_passa_pelo_handler):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
