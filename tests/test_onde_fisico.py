"""Onde a carta ESTÁ fisicamente vs a quem está DESTINADA.

André, 2026-09-08, à letra: *"De todas as cartas, só o Stiflenought está em
deckbox; o resto ainda nada está em deckbox — e ainda estás a assumir que há
cartas que já estão nas deckboxes dos decks."*

A alocação atribui cópias a caixas por PRIORIDADE (é um plano), e a página
mostrava *"em &lt;caixa&gt;"* / *"ir buscar a outra caixa"* como se a cópia lá
estivesse. Com a `copy_allocation` vazia — que era o estado da base nesse dia —
as 70 cópias do *"ir buscar"* estavam todas na `Colecção`, na prateleira. É o
padrão do `event_tier`: um número certo a responder a outra pergunta.

O que aqui se tranca:

  1. **destino ≠ físico** — uma cópia que a alocação deu a outra caixa, e que não
     tem linha na `copy_allocation`, sai como `noutra_reservada` (*"na Colecção —
     destinada a X"*) e nunca como `noutra_montada` (*"em X"*);
  2. **a `copy_allocation` muda a frase** — assim que a cópia é registada dentro
     da caixa, a outra passa a dizer *"em X"*, que aí é verdade;
  3. **montar fora de ordem** — o painel *Montar* de uma caixa mostra, num bloco
     próprio, as cópias que estão na gaveta destinadas a outra caixa por montar;
     o que ele marcar fica registado NESTA, e a alocação segue a realidade
     física (a outra caixa passa a vir buscá-las aqui);
  4. **Arrumar sem caixas fantasma** — com a `copy_allocation` vazia, todos os
     movimentos saem de uma gaveta, nunca de uma caixa;
  5. **a página não diz "em &lt;caixa&gt;"** quando a caixa não tem nada lá
     dentro (verificado no HTML que o browser desenha, se houver `node`).

Não abre socket nenhum e não toca na rede.
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
# Duas caixas do MESMO grupo, que PARTILHA (não é dedicado): é a única forma de
# uma dizer onde a outra tem a carta. A ordem é a do `prioridade`.
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "regras_por_formato": [
        {"grupo": "duo", "formatos": ["legacy"], "dedicado": False},
    ],
    "caixas": [
        {"slot": "a", "nome": "Caixa A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "estado": "permanente", "prioridade": 1},
        {"slot": "b", "nome": "Caixa B", "formato": "legacy", "fonte": "deck",
         "ref": "B", "balde": "Colecção", "estado": "permanente", "prioridade": 2},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

CATALOGO = [("Wrath of God", "4ed", "W"), ("Ancestral Vision", "tsp", "U")]
# As duas caixas querem a MESMA carta e só há uma cópia: a A (prioridade 1)
# fica com ela, e a B tem de dizer onde ela está. A `Ancestral Vision` existe
# para a B ter alguma coisa própria e não ser uma caixa vazia.
LISTAS = {"A": [("main", "Wrath of God", 1)],
          "B": [("main", "Wrath of God", 1), ("main", "Ancestral Vision", 1)]}
POSSE = {"Wrath of God": 1, "Ancestral Vision": 1}
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, ci) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Sorcery',2,?,?,'2005-01-01',?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), ci,
             json.dumps(["nonfoil"]), json.dumps({"legacy": "legal"})))
        con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date,
                       trend) VALUES (?,'cardmarket','nonfoil','2026-09-08',?)""",
                    (f"id-{i}", 3.0))
    for deck, cartas in LISTAS.items():
        con.execute("INSERT INTO decks (name, format) VALUES (?,'legacy')", (deck,))
        did = con.execute("SELECT id FROM decks WHERE name=?", (deck,)).fetchone()["id"]
        for board, nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,?)", (did, nm, q, board))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    for i, (nm, *_r) in enumerate(CATALOGO):
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                       purpose, sub_collection_id) VALUES (?,?,'nonfoil','en',
                       'player',?)""", (f"id-{i}", POSSE[nm], sub))
    con.commit()
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def _slot(rep, slot_id):
    return next(s for s in rep["slots"] if s["slot"] == slot_id)


def _linha(rep, slot_id, nm):
    s = _slot(rep, slot_id)
    return next(m for m in s["have"] + s["missing"] if m["nm"] == nm)


def _copy_id(con, nm):
    i = [x[0] for x in CATALOGO].index(nm)
    return con.execute("SELECT id FROM copies WHERE scryfall_id = ?",
                       (f"id-{i}",)).fetchone()["id"]


def _abas(con, editable=False):
    """`{aba: HTML}` — o que o browser mostraria. `None` sem `node`."""
    if not shutil.which("node"):
        return None
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    out.write_text(deckboxes.html_page(con, editable=editable), encoding="utf-8")
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(out), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
def caso_destinada_a_outra_caixa_nao_e_estar_la_dentro():
    """A cópia é da Caixa A por prioridade, mas está na `Colecção`. A Caixa B
    tem de o dizer assim — *"na Colecção — destinada a Caixa A"*. Dizer *"em
    Caixa A"* mandava-o procurar dentro de uma caixa que não existe."""
    repor()
    con = base()
    rep = loadout.report(con)
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation").fetchone()["c"] == 0
    m = _linha(rep, "b", "Wrath of God")
    assert m["noutra"] == {"Caixa A": 1}, m["noutra"]
    assert m["noutra_montada"] == {}, "não está dentro de caixa nenhuma"
    assert m["noutra_reservada"] == {"Caixa A": 1}, m["noutra_reservada"]
    assert m["noutra_onde"] == {"Caixa A": {"Colecção": 1}}, m["noutra_onde"]
    assert m["comprar"] == 0, "continua a não se comprar: a cópia existe"
    assert loadout.onde_esta(m) == [
        "1× na Colecção — destinada a Caixa A (prioridade)"], loadout.onde_esta(m)
    b = _slot(rep, "b")
    assert (b["noutra"], b["noutra_montada"], b["noutra_reservada"]) == (1, 0, 1)
    assert rep["noutra_total"] == 1 and rep["noutra_montada_total"] == 0
    assert rep["noutra_reservada_total"] == 1
    print("destino != físico: 'na Colecção — destinada a Caixa A', e não 'em Caixa A'")


def caso_com_a_caixa_montada_a_frase_muda():
    """A `copy_allocation` é a única prova de que a carta está lá dentro. Depois
    do *"sleevado e na caixa"* da Caixa A, a Caixa B passa a dizer *"em Caixa
    A"* — e aí é verdade, é mesmo lá que ela está."""
    repor()
    con = base()
    assert webapp.marcar_na_caixa(con, "a", True) == 1
    rep = loadout.report(con)
    m = _linha(rep, "b", "Wrath of God")
    assert m["noutra_montada"] == {"Caixa A": 1}, m["noutra_montada"]
    assert m["noutra_reservada"] == {} and m["noutra_onde"] == {}
    assert loadout.onde_esta(m) == ["1× em Caixa A"], loadout.onde_esta(m)
    b = _slot(rep, "b")
    assert (b["noutra_montada"], b["noutra_reservada"]) == (1, 0)
    assert [x["nm"] for x in b["buscar_montada"]] == ["Wrath of God"]
    assert b["buscar_reservada"] == []
    print("com a caixa montada: 'em Caixa A' — e o bloco passa para 'ir buscar'")


def caso_montar_fora_de_ordem():
    """Ele abre a Caixa B antes da Caixa A. A Wrath está na `Colecção`, ali à
    mão: o painel Montar da B mostra-a num bloco próprio, por marcar. O que ele
    marcar fica registado na B — e a partir daí é a ARRUMAÇÃO que manda sobre a
    prioridade: a Caixa A passa a dizer *"em Caixa B"*."""
    repor()
    con = base()
    rep = loadout.report(con)
    plano = loadout.plano_montar(rep, "b")
    # O que a alocação lhe dá é só a Ancestral Vision; a Wrath vem à parte.
    assert [m["nm"] for m in plano["tirar"]] == ["Ancestral Vision"], plano["tirar"]
    assert [(m["nm"], m["de"], m["destino"]) for m in plano["de_outra"]] == [
        ("Wrath of God", "Colecção", "Caixa A")], plano["de_outra"]
    assert plano["copias_de_outra"] == 1
    # E a Caixa A (que É a dona) não tem bloco nenhum destes: o que ela quer é
    # dela. Um bloco "destinadas a outra caixa" na caixa de destino não quer
    # dizer nada.
    assert loadout.plano_montar(rep, "a")["de_outra"] == []

    cid = _copy_id(con, "Wrath of God")
    n = webapp.marcar_na_caixa(con, "b", True, [cid])
    assert n == 2, f"a Ancestral Vision dela mais a Wrath que ele tirou: {n}"
    linhas = {r["slot"]: r["quantity"] for r in con.execute(
        "SELECT slot, quantity FROM copy_allocation WHERE copy_id = ?", (cid,))}
    assert linhas == {"b": 1}, linhas

    rep2 = loadout.report(con)
    a = _slot(rep2, "a")
    m = _linha(rep2, "a", "Wrath of God")
    assert m["noutra_montada"] == {"Caixa B": 1}, (
        "a arrumação manda sobre a prioridade: a A tem de ir buscá-la à B")
    assert m["comprar"] == 0, "não se compra o que está na caixa do lado"
    assert (a["noutra_montada"], a["noutra_reservada"]) == (1, 0)
    assert loadout.onde_esta(m) == ["1× em Caixa B"]
    # E a Caixa B deixou de a ter em falta: está lá dentro.
    assert _linha(rep2, "b", "Wrath of God")["got"] == 1
    print("montar fora de ordem: ele tira-a para a B, e a A passa a 'em Caixa B'")


def caso_marcar_so_regista_o_que_o_painel_oferecia():
    """Um `copy_id` que esta caixa não pediu não entra. Registar uma carta que a
    caixa nem quer era escrever na `copy_allocation` uma coisa que não está lá
    dentro — e a `copy_allocation` é a única prova em que tudo o resto assenta."""
    repor()
    con = base()
    intrusa = _copy_id(con, "Ancestral Vision")
    # A Caixa A não joga Ancestral Vision: mesmo marcada, não pode entrar.
    n = webapp.marcar_na_caixa(con, "a", True, [intrusa])
    assert n == 1, f"só a Wrath, que é a que a alocação lhe dá: {n}"
    slots = [r["slot"] for r in con.execute(
        "SELECT slot FROM copy_allocation WHERE copy_id = ?", (intrusa,))]
    assert slots == [], slots
    print("marcar so regista o que o painel oferecia")


def caso_arrumar_nao_inventa_caixas():
    """Os movimentos «X → Y» só existem entre sítios FÍSICOS. Com a
    `copy_allocation` vazia, tudo sai da `Colecção` — nunca *"tirar de Caixa A"*
    de uma caixa que não está montada."""
    repor()
    con = base()
    rep = loadout.report(con)
    plano = rep["arrumacao"]
    caixas = {s["nome"] for s in rep["slots"]}
    origens = {m["de"] for m in plano["movimentos"]}
    assert origens == {"Colecção"}, origens
    assert not (origens & caixas), f"caixa fantasma na origem: {origens & caixas}"
    # Pelo outro lado: o que ENTRA vem sempre de uma gaveta.
    assert set(plano["por_origem"]) == {"Colecção"}, plano["por_origem"]
    print("arrumar: tudo sai da Colecção, nenhuma caixa fantasma")


def caso_a_pagina_nao_diz_que_a_carta_esta_numa_caixa_vazia():
    """O verificador do lado do browser: com a `copy_allocation` vazia, o HTML
    desenhado não pode ter *"em Caixa A"* em lado nenhum — e tem de ter a frase
    honesta. Um payload certo com uma página que o recompõe à sua maneira era
    exactamente o defeito a corrigir (ver `e_foil`)."""
    repor()
    con = base()
    abas = _abas(con)
    if abas is None:
        print("HTML: sem `node`, saltado")
        return
    html = abas["b"]
    assert "na Colecção — destinada a Caixa A" in html, html[-2500:]
    assert "em Caixa A" not in html, "diz que a carta está numa caixa vazia"
    assert "Destinadas a outra caixa" in html, "falta o bloco do painel Montar"
    print("a pagina diz 'na Coleccao — destinada a Caixa A', nunca 'em Caixa A'")


def caso_estado_carta_parte_o_mesmo(pool=None):
    """O `_estado_carta` (o ranking do `foil_report`, que é outro caminho) tem de
    partir o *"noutra"* da mesma maneira. Dois caminhos com a mesma pergunta e
    respostas diferentes é o defeito que este vault já pagou três vezes."""
    repor()
    con = base()
    rep = loadout.report(con)
    s = _slot(rep, "b")
    e = loadout._estado_carta(rep["pool"], s, "Wrath of God", 1,
                              {x["balde"] for x in rep["slots"] if x.get("balde")})
    assert e["noutra"] == {"Caixa A": 1} and e["noutra_montada"] == {}
    assert e["noutra_reservada"] == {"Caixa A": 1}
    assert e["noutra_onde"] == {"Caixa A": {"Colecção": 1}}, e["noutra_onde"]
    print("_estado_carta parte o 'noutra' da mesma maneira que o allocate")


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("caso_"):
            fn()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass
    shutil.rmtree(_TMP, ignore_errors=True)
    print("\nOK")
