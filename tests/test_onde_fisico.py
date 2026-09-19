"""Onde a carta ESTÁ fisicamente vs a quem está DESTINADA — e, desde 2026-09-19,
nem uma nem outra é fonte para outra caixa.

André, 2026-09-08, à letra: *"De todas as cartas, só o Stiflenought está em
deckbox; o resto ainda nada está em deckbox — e ainda estás a assumir que há
cartas que já estão nas deckboxes dos decks."* Daí o `noutra` ter sido partido
em `montada` (está lá dentro) e `reservada` (está na gaveta, prometida).

André, 2026-09-19, à letra: *"cada deck deverá ter as suas próprias cartas
dentro, não repetindo com outros decks!"* SUPERSEDE a partilha: uma cópia que a
alocação deu a outra caixa é dessa caixa, esteja sleevada ou na gaveta, e esta
caixa COMPRA a sua. O `noutra` e as suas metades são ZERO por regra; o que fica
é uma NOTA (*"tens 1 no Caixa A"*, `noutra_nota`/`nota_onde`) para ele saber
que a carta existe em casa — nunca como fonte, substituto nem desconto.

O que aqui se tranca (reescrito a 2026-09-19; os casos antigos fixavam o "ir
buscar" e o "montar fora de ordem", que deixaram de existir):

  1. **é compra, com nota** — com a `copy_allocation` vazia a Caixa B compra a
     Wrath e diz *"tens 1 no Caixa A"*; nada em `noutra_*`;
  2. **registar a Caixa A não muda nada para a B** — antes mudava a frase para
     *"em Caixa A"*; agora continua a ser compra com a mesma nota;
  3. **não há montar fora de ordem** — o bloco `de_outra` do painel Montar é
     vazio, e um `copy_id` de outra caixa passado como `de_outra` não entra;
  4. **Arrumar sem caixas fantasma** — tudo sai de uma gaveta;
  5. **a página** diz *"tens 1 no Caixa A"* e nunca *"em Caixa A"* nem
     *"destinada a"* (verificado no HTML desenhado, se houver `node`);
  6. **`_estado_carta`** (o ranking) dá o mesmo: `noutra` vazio, nota cheia.

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
# Duas caixas do MESMO grupo. O `dedicado: False` fica escrito de propósito: desde
# 2026-09-19 não tem efeito nenhum (o `resolve_slots` força `True`), e é isso
# que estes casos também trancam.
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

CATALOGO = [("Wrath of God", "4ed", "W"), ("Ancestral Vision", "tsp", "U")]
# As duas caixas querem a MESMA carta e só há uma cópia: a A (prioridade 1)
# fica com ela, e a B compra a sua. A `Ancestral Vision` existe para a B ter
# alguma coisa própria e não ser uma caixa vazia.
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


def _regista(con, slot_id, de_outra=()):
    """O *"sleevado e na caixa"* com TUDO marcado, que é o que estes casos dizem.

    Desde 2026-09-09 o registo grava só as cópias marcadas (ver
    `test_registo_marcadas.py`), por isso marcar-se-lhe a lista inteira aqui é
    dizer que ele encontrou tudo o que a caixa lhe pedia."""
    rep = loadout.report(con)
    s = _slot(rep, slot_id)
    marcadas = [m["copy_id"] for m in loadout.movimentos_de_entrada(
        s, loadout.caixas_de_deck(rep["slots"]))]
    return loadout.registar_marcadas(con, rep, slot_id, marcadas, de_outra)


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


def _sem_noutra(m):
    assert m["noutra"] == {} and m["noutra_q"] == 0, m["noutra"]
    assert m["noutra_montada"] == {} and m["noutra_reservada"] == {}, m
    assert m["noutra_onde"] == {} and m["noutra_lotes"] == [], m
    assert loadout.onde_esta(m) == [], loadout.onde_esta(m)


# ---------------------------------------------------------------------------
def caso_destinada_a_outra_caixa_e_compra_com_nota():
    """A cópia é da Caixa A por prioridade e está na `Colecção`. Até 2026-09-19
    a Caixa B dizia *"na Colecção — destinada a Caixa A"* e não a comprava.
    Agora COMPRA-A — e a nota diz-lhe que tem uma na A."""
    repor()
    con = base()
    rep = loadout.report(con)
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation").fetchone()["c"] == 0
    m = _linha(rep, "b", "Wrath of God")
    _sem_noutra(m)
    assert m["comprar"] == 1 and m["cost"] == 3.0, m
    assert m["noutra_nota"] == {"Caixa A": 1}, m["noutra_nota"]
    assert loadout.nota_onde(m) == "tens 1 no Caixa A", loadout.nota_onde(m)
    b = _slot(rep, "b")
    assert (b["noutra"], b["noutra_montada"], b["noutra_reservada"]) == (0, 0, 0)
    assert b["comprar"] == 1 and [x["nm"] for x in b["noutra_notas"]] == ["Wrath of God"]
    assert rep["noutra_total"] == 0 and rep["noutra_montada_total"] == 0
    assert rep["noutra_reservada_total"] == 0 and rep["comprar_total"] == 1
    # E o `dedicado: False` do config não devolveu a partilha.
    assert all(s["dedicado"] for s in rep["slots"]), "dedicado: false nao tem efeito"
    print("destinada a outra caixa: e compra, com a nota 'tens 1 no Caixa A'")


def caso_com_a_caixa_montada_nada_muda_para_a_outra():
    """Depois do *"sleevado e na caixa"* da Caixa A, a Caixa B continua a
    comprar a sua — antes passava a dizer *"em Caixa A"* e a ir lá buscá-la."""
    repor()
    con = base()
    assert _regista(con, "a")["copias"] == 1
    rep = loadout.report(con)
    m = _linha(rep, "b", "Wrath of God")
    _sem_noutra(m)
    assert m["comprar"] == 1 and m["noutra_nota"] == {"Caixa A": 1}, m
    b = _slot(rep, "b")
    assert b["buscar_montada"] == [] and b["buscar_reservada"] == []
    assert _linha(rep, "a", "Wrath of God")["got"] == 1
    print("com a caixa A montada: a B continua a comprar a sua, com a mesma nota")


def caso_nao_ha_montar_fora_de_ordem():
    """O bloco «destinadas a outra caixa» do painel Montar era a porta para tirar
    da gaveta uma cópia que a alocação deu a outra caixa. Com cartas próprias
    por caixa a porta fechou: o bloco é vazio e um `copy_id` que esta caixa não
    pediu passado como `de_outra` não entra na `copy_allocation`."""
    repor()
    con = base()
    rep = loadout.report(con)
    plano = loadout.plano_montar(rep, "b")
    assert [m["nm"] for m in plano["tirar"]] == ["Ancestral Vision"], plano["tirar"]
    assert plano["de_outra"] == [] and plano["copias_de_outra"] == 0, plano["de_outra"]
    assert loadout.movimentos_reservados(_slot(rep, "b")) == []

    cid = _copy_id(con, "Wrath of God")
    n = _regista(con, "b", de_outra=[cid])["copias"]
    assert n == 1, f"so a Ancestral Vision dela: {n}"
    linhas = {r["slot"]: r["quantity"] for r in con.execute(
        "SELECT slot, quantity FROM copy_allocation WHERE copy_id = ?", (cid,))}
    assert linhas == {}, linhas
    # A Caixa A continua com a Wrath, e a B continua a comprar a sua.
    rep2 = loadout.report(con)
    assert _linha(rep2, "a", "Wrath of God")["got"] == 1
    assert _linha(rep2, "b", "Wrath of God")["comprar"] == 1
    print("nao ha montar fora de ordem: o bloco e vazio e o de_outra nao entra")


def caso_marcar_so_regista_o_que_o_painel_oferecia():
    """Um `copy_id` que esta caixa não pediu não entra. Registar uma carta que a
    caixa nem quer era escrever na `copy_allocation` uma coisa que não está lá
    dentro — e a `copy_allocation` é a única prova em que tudo o resto assenta."""
    repor()
    con = base()
    intrusa = _copy_id(con, "Ancestral Vision")
    n = _regista(con, "a", de_outra=[intrusa])["copias"]
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
    assert set(plano["por_origem"]) == {"Colecção"}, plano["por_origem"]
    print("arrumar: tudo sai da Colecção, nenhuma caixa fantasma")


def caso_a_pagina_diz_tens_noutra_caixa_e_compra():
    """O verificador do lado do browser: a página da Caixa B diz *"tens 1 no
    Caixa A"* (a nota), pede a Wrath na lista de compras, e não tem *"em Caixa
    A"* nem *"destinada a"* em lado nenhum — nem o bloco «Destinadas a outra
    caixa» do painel Montar."""
    repor()
    con = base()
    abas = _abas(con)
    if abas is None:
        print("HTML: sem `node`, saltado")
        return
    html = abas["b"]
    assert "tens 1 no Caixa A" in html, html[-2500:]
    assert "em Caixa A" not in html, "diz que a carta esta noutra caixa como fonte"
    assert "destinada a" not in html, "o 'destinada a' desapareceu com a partilha"
    assert "Destinadas a outra caixa" not in html, "o bloco do painel Montar e vazio"
    assert "1 Wrath of God" in html, "a Wrath tem de estar na wantlist da B"
    assert "tens noutra caixa" in html, "o bloco da nota"
    print("a pagina diz 'tens 1 no Caixa A' e compra a Wrath na mesma")


def caso_estado_carta_parte_o_mesmo(pool=None):
    """O `_estado_carta` (o ranking do `foil_report`, que é outro caminho) tem de
    dar o mesmo: `noutra` vazio e a nota cheia. Dois caminhos com a mesma
    pergunta e respostas diferentes é o defeito que este vault já pagou três
    vezes."""
    repor()
    con = base()
    rep = loadout.report(con)
    s = _slot(rep, "b")
    e = loadout._estado_carta(rep["pool"], s, "Wrath of God", 1,
                              {x["balde"] for x in rep["slots"] if x.get("balde")})
    assert e["noutra"] == {} and e["noutra_montada"] == {} and e["noutra_q"] == 0, e
    assert e["noutra_reservada"] == {} and e["noutra_onde"] == {}, e
    assert e["noutra_nota"] == {"Caixa A": 1} and e["comprar"] == 1, e
    print("_estado_carta da o mesmo que o allocate: compra, com a nota")


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
