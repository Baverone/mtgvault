"""«MONTADA» NÃO QUER DIZER QUE A CÓPIA PODIA LÁ ESTAR.

André, 2026-09-09: *"dizes que tenho Chromatic Star mas eu não tenho"* e *"essa
Chromatic Star fotografada é foil, tal como a Grinding Station"*.

As duas cópias (694 e 403) estavam na base como **nonfoil** — a 403 até com a
nota *"parece non-foil (sem holo); confirmar foil"*. Sendo nonfoil EN serviam o
Cloud cEDH (*"só inglês non-foil"*), foram alocadas, e ao registar a caixa
ficaram com linha na `copy_allocation`. Nesse dia corrigiu-se o acabamento para
**foil** — e a caixa continuou a dizer que as tinha, porque *"uma cópia que está
dentro da caixa deste deck escapa às regras de material"*.

Ou seja: a linha da `copy_allocation` **lavava** a correcção. Padrão do
`event_tier` — nenhum passo dá erro e a caixa mente para sempre sobre duas
cartas.

O que aqui se tranca:

  1. uma cópia registada numa caixa que a regra de material dela RECUSA não
     conta como estando lá: `local` volta a ser o balde e a carta volta a ser
     **compra** naquela caixa;
  2. a mesma cópia, quando CUMPRE a regra, continua dentro da caixa — a excepção
     de material que protege um deck montado não morreu;
  3. a cópia libertada fica disponível para a caixa que a aceita (a Grinding
     Station foil vai para o slot de foil);
  4. **uma caixa CONGELADA não é excepção** — a do André é uma;
  5. os **terrenos básicos** são isentos, como já eram na alocação;
  6. o *"já arrumei tudo"* deita fora o registo contraditório, mesmo numa caixa
     congelada (senão a lista nunca se limpava);
  7. a página DIZ quais são e porquê (corrido no harness de node).

Não abre socket nenhum nem toca na rede.
"""
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
    # A ordem desta lista é a ordem da alocação: o cEDH escolhe antes do Modern.
    # É o que faz o caso 3 valer alguma coisa — a foil só chega ao Modern porque
    # o cEDH, que corre primeiro, deixou de a poder usar.
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil", "dedicado": True},
        {"grupo": "spml", "formatos": ["modern"], "lingua": "en",
         "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "cedh", "nome": "Cloud cEDH", "formato": "cedh",
         "fonte": "deck", "ref": "CLOUD", "balde": "Colecção",
         "estado": "montada", "prioridade": 1},
        {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
         "fonte": "deck", "ref": "OSWALD", "balde": "Colecção",
         "estado": "permanente", "prioridade": 2},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402

CATALOGO = [
    ("Chromatic Star", "2xm", "2020-08-07", ["nonfoil", "foil"]),
    ("Grinding Station", "5dn", "2004-06-04", ["nonfoil", "foil"]),
    ("Sol Ring", "c14", "2014-11-07", ["nonfoil", "foil"]),
    ("Island", "unh", "2004-11-19", ["nonfoil", "foil"]),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fin) in enumerate(CATALOGO):
        tipo = "Basic Land" if nm == "Island" else "Artifact"
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               image_uri)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'',?,?,?,0,0,?)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(fin), rel, json.dumps({"cedh": "legal", "modern": "legal"}),
             f"http://exemplo/{i}.jpg"))
        for f in ("nonfoil", "foil"):
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source,"
                        " finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-09', 3.0)", (f"id-{i}", f))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    return con


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def add(con, nm, q=1, finish="nonfoil", sub="Colecção"):
    sc = next(c[1] for c in CATALOGO if c[0] == nm)
    return collection.add_copy(con, nm, set_code=sc, quantity=q, finish=finish,
                               sub_collection=sub)


def registar(con, slot, copy_id, q=1):
    """A linha que o «sleevado e na caixa» escreve. É a única prova de sítio."""
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at)"
                " VALUES (?,?,?,'2026-09-09 10:39:55')", (copy_id, slot, q))
    con.commit()


def montado(cedh=(("Chromatic Star", 1), ("Grinding Station", 1)),
            modern=(("Grinding Station", 1),)):
    con = base()
    deck(con, "CLOUD", "cedh", list(cedh))
    deck(con, "OSWALD", "modern", list(modern))
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def linha(s, nm):
    return next(m for m in s["have"] + s["missing"] if m["nm"] == nm)


def caixa(rep, slot):
    return next(s for s in rep["slots"] if s["slot"] == slot)


# ---------------------------------------------------------------------------
def caso_uma_foil_registada_numa_caixa_nonfoil_nao_esta_la():
    """O caso dele, à letra. A caixa está `montada` (e por isso CONGELADA: é
    dedicada e tem conteúdo confirmado), a cópia tem linha na `copy_allocation`
    — e é foil numa caixa que só aceita nonfoil. O registo não a põe lá dentro."""
    repor()
    con = montado()
    star = add(con, "Chromatic Star", 1, finish="foil")
    registar(con, "cedh", star)

    rep = loadout.report(con)
    s = caixa(rep, "cedh")
    assert s["congelada"] is True, "o caso dele é numa caixa congelada"

    m = linha(s, "Chromatic Star")
    assert m["got"] == 0 and m["lotes"] == [], m
    assert m["comprar"] == 1, m
    assert m["alt"] == {"não é nonfoil": 1}, ("fica como substituto", m["alt"])

    # O lote não diz que está na caixa: diz onde está mesmo.
    lote = loadout.lots(con)["Chromatic Star"][0]
    assert lote["caixa"] is None and lote["local"] == "Colecção", lote
    assert lote["caixa_registada"] == "cedh", lote
    assert lote["contradiz"] == "não é nonfoil", lote

    # E o vault DI-LO, em vez de deixar a percentagem descer sozinha.
    assert rep["contradicoes_total"] == 1
    c = rep["contradicoes"][0]
    assert (c["nm"], c["caixa"], c["porque"], c["onde"]) == (
        "Chromatic Star", "Cloud cEDH", "não é nonfoil", "Colecção"), c
    assert s["contradicoes"] == [c], "a caixa também a traz"
    print("uma foil registada numa caixa nonfoil nao conta como estando la")


def caso_a_copia_que_cumpre_continua_dentro_da_caixa():
    """A excepção não morreu: uma cópia que a regra ACEITA e está registada
    continua dentro da caixa — é o que impede que uma regra nova desmonte no
    papel um deck que está sleevado na estante."""
    repor()
    con = montado()
    star = add(con, "Chromatic Star", 1, finish="nonfoil")
    registar(con, "cedh", star)

    rep = loadout.report(con)
    s = caixa(rep, "cedh")
    m = linha(s, "Chromatic Star")
    assert m["got"] == 1 and m["lotes"][0]["local"] == "Cloud cEDH", m
    assert rep["contradicoes"] == [], rep["contradicoes"]
    print("a copia que cumpre a regra continua dentro da caixa")


def caso_a_foil_libertada_serve_a_caixa_que_a_quer():
    """*"a Grinding Station foil deve ir para o Modern UW Oswald"*. Enquanto o
    registo a prendia ao cEDH ela era `noutra caixa` para o Modern; libertada,
    o Modern — que pede foil — fica com ela."""
    repor()
    con = montado()
    gs = add(con, "Grinding Station", 1, finish="foil")
    registar(con, "cedh", gs)

    rep = loadout.report(con)
    mo = linha(caixa(rep, "modern"), "Grinding Station")
    assert mo["got"] == 1, ("o Modern fica com a foil", mo)
    assert mo["lotes"][0]["local"] == "Colecção", mo["lotes"]
    ce = linha(caixa(rep, "cedh"), "Grinding Station")
    assert ce["comprar"] == 1 and ce["noutra"] == {}, ce
    print("a foil libertada vai para a caixa de foil que a pede")


def caso_uma_caixa_congelada_nao_e_excepcao():
    """`congelada` promete que as cópias lá dentro não voltam à gaveta *mesmo
    que a LISTA de hoje já não as peça*. Uma contradição não é a lista a mudar —
    é a cópia a não poder ali estar, hoje como ontem. E o que está sleevado e
    CUMPRE continua preso: só a contradição é que sai."""
    repor()
    con = montado(cedh=(("Chromatic Star", 1),))
    star = add(con, "Chromatic Star", 1, finish="foil")
    sol = add(con, "Sol Ring", 1, finish="nonfoil")     # já não está na lista
    registar(con, "cedh", star)
    registar(con, "cedh", sol)

    rep = loadout.report(con)
    s = caixa(rep, "cedh")
    assert s["congelada"] is True, s["estado"]
    assert [c["nm"] for c in rep["contradicoes"]] == ["Chromatic Star"]
    # O Sol Ring cumpre a regra e a lista já não o pede: continua PRESO.
    assert [p["nm"] for p in s["presos"]] == ["Sol Ring"], s["presos"]
    print("uma caixa congelada nao lava uma contradicao, mas continua a prender")


def caso_as_basicas_sao_isentas():
    """A pilha dele é toda Unhinged EN e as caixas não a recusam — a isenção que
    a alocação já lhes dá vale também para julgar um registo."""
    repor()
    con = montado(cedh=(("Island", 4),), modern=(("Sol Ring", 1),))
    ilha = add(con, "Island", 4, finish="foil")          # foil numa caixa nonfoil
    registar(con, "cedh", ilha, 4)

    rep = loadout.report(con)
    assert rep["contradicoes"] == [], rep["contradicoes"]
    lote = loadout.lots(con)["Island"][0]
    assert lote["caixa"] == "cedh" and lote["contradiz"] is None, lote
    print("as basicas sao isentas: um registo delas nunca e contradicao")


def caso_o_ja_arrumei_tudo_deita_fora_o_registo_errado():
    """A linha fica na base todos os dias se ninguém a tirar — e numa caixa
    congelada o botão geral preserva as linhas de propósito. A contradição é a
    excepção: é a *"linha órfã que mentia para sempre"* de que essa função se
    defende, e sem isto a lista nunca se limpava."""
    repor()
    con = montado(cedh=(("Chromatic Star", 1),))
    star = add(con, "Chromatic Star", 1, finish="foil")
    sol = add(con, "Sol Ring", 1, finish="nonfoil")
    registar(con, "cedh", star)
    registar(con, "cedh", sol)

    rep = loadout.report(con)
    loadout.guardar_arrumacao(con, rep)
    ficou = {r["copy_id"] for r in con.execute(
        "SELECT copy_id FROM copy_allocation WHERE slot = 'cedh'")}
    assert star not in ficou, "o registo contraditório sai"
    assert sol in ficou, "o que está lá dentro e cumpre fica (caixa congelada)"
    assert loadout.report(con)["contradicoes"] == []
    print("o «ja arrumei tudo» deita fora o registo contraditorio")


def caso_a_pagina_diz_quais_sao():
    """Um número que desce sozinho não é uma explicação. O bloco vem no payload
    e desenha-se na aba da caixa — corrido no JavaScript a sério."""
    repor()
    con = montado()
    star = add(con, "Chromatic Star", 1, finish="foil")
    registar(con, "cedh", star)

    rep = loadout.report(con)
    d = deckboxes.payload(con, rep)
    c = next(x for x in d["caixas"] if x["slot"] == "cedh")
    assert c["contradicoes"] == [{
        "nm": "Chromatic Star", "q": 1, "porque": "não é nonfoil",
        "onde": "Colecção", "foil": True, "lang": "en", "set_code": "2xm"}], \
        c["contradicoes"]

    if not shutil.which("node"):
        print("a pagina diz quais sao: sem `node`, so o payload verificado")
        return
    out = Path(tempfile.mkdtemp())
    pagina = out / "deckboxes.html"
    deckboxes.build(con, pagina)
    dump = out / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    abas = json.loads(dump.read_text(encoding="utf-8"))
    html = abas.get("cedh") or ""
    assert "registada nesta caixa e não pode lá estar" in html, html[:2000]
    assert "não é nonfoil" in html and "Chromatic Star" in html
    print("a pagina diz quais sao e porque")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for f in CASOS:
        f()
    print(f"\n{len(CASOS)} casos ok")
