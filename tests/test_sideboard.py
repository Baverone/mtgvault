"""O sideboard separado dentro da caixa, e a desmontagem registada.

André, 2026-09-08, à letra: *"Preciso também de saber o que é sideboard nos
decks, para ficar separado dentro da mesma caixa."* Uma caixa é um deck e um deck
são duas pilhas — 60 (ou 100) e 15. A lista corrida de 75 linhas obrigava-o a
separá-las de cabeça à frente da estante.

O que aqui se tranca:

  1. o painel **Montar** parte a lista em **Main** e **Sideboard**, com o "N de M"
     de cada bloco, e a carta que joga nos DOIS vem em duas linhas — são duas
     cópias físicas, em duas pilhas (uma linha só dizia "2×" e escondia qual ia
     para onde);
  2. o texto copiado da wantlist leva **`// Sideboard`** entre os dois blocos (o
     Cardmarket ignora a linha de comentário sem dar erro);
  3. **desmontar** esvazia a `copy_allocation` daquela caixa, com backup da base
     e uma linha no `data/desmontar.log` — e o botão existe também numa caixa que
     NÃO se diz montada mas tem cartas registadas lá dentro, que era o caso das
     quatro de 2026-09-08. Sem o botão, isto fazia-se em SQL à mão.

Não abre socket nenhum e não toca na rede. O HTML desenhado só se verifica se
houver `node` (a bateria tem de correr num PC sem ele).
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
    "regras_por_formato": [
        {"grupo": "legacy", "formatos": ["legacy"], "dedicado": True},
    ],
    "caixas": [
        {"slot": "a", "nome": "Caixa A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "estado": "permanente", "prioridade": 1},
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

# (nome, edição, cor). A cor decide a ordem DENTRO de cada bloco.
CATALOGO = [
    ("Wrath of God", "4ed", "W"),
    ("Ancestral Vision", "tsp", "U"),
    ("Swamp Dweller", "leg", "B"),
    ("Chromatic Star", "shm", ""),
]
# A lista da caixa: a Wrath joga no main E no side (é o caso que obriga a duas
# linhas), e a Chromatic Star só existe no side e não está em casa — é a compra
# que tem de sair do outro lado do `// Sideboard`.
LISTA = [("main", "Wrath of God", 1), ("main", "Ancestral Vision", 1),
         ("main", "Swamp Dweller", 1), ("side", "Wrath of God", 1),
         ("side", "Chromatic Star", 2)]
POSSE = {"Wrath of God": 2, "Ancestral Vision": 1, "Swamp Dweller": 1}
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
    con.execute("INSERT INTO decks (name, format) VALUES ('A','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name='A'").fetchone()["id"]
    for board, nm, q in LISTA:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,?)", (did, nm, q, board))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    for i, (nm, *_r) in enumerate(CATALOGO):
        if nm not in POSSE:
            continue
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                       purpose, sub_collection_id) VALUES (?,?,'nonfoil','en',
                       'player',?)""", (f"id-{i}", POSSE[nm], sub))
    con.commit()
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def _caixa(con):
    rep = loadout.report(con)
    return deckboxes.payload(con, rep)["caixas"][0], rep


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
def caso_montar_separa_main_do_sideboard():
    """Dois blocos, com o "N de M" de cada um — e a Wrath, que joga nos dois, em
    DUAS linhas. Uma linha só (`2×`) não dizia qual das cópias ia para que
    pilha, que é exactamente a pergunta dele."""
    repor()
    con = base()
    c, _rep = _caixa(con)
    m = c["montar"]
    assert m["totais"] == {"main": 3, "side": 3}, m["totais"]
    blocos = {b["board"]: b for b in m["blocos"]}
    assert list(blocos) == ["main", "side"], m["blocos"]
    # Main: 3 de 3, por cor (W, U, B) — é como o binder está arrumado.
    assert (blocos["main"]["q"], blocos["main"]["de"]) == (3, 3), blocos["main"]
    assert [x["nm"] for x in blocos["main"]["movs"]] == [
        "Wrath of God", "Ancestral Vision", "Swamp Dweller"], blocos["main"]
    # Sideboard: 1 de 3 (a Chromatic Star não está em casa — é compra).
    assert (blocos["side"]["q"], blocos["side"]["de"]) == (1, 3), blocos["side"]
    assert [x["nm"] for x in blocos["side"]["movs"]] == ["Wrath of God"]
    # A MESMA cópia física serve as duas linhas: é o mesmo lote, partido em dois.
    assert (blocos["main"]["movs"][0]["copy_id"]
            == blocos["side"]["movs"][0]["copy_id"]), "as duas Wrath são o mesmo lote"
    assert m["copias"] == 4 and m["por_gaveta"] == {"Colecção": 4}, m
    print("montar: bloco Main 3 de 3 e bloco Sideboard 1 de 3, com a carta dos dois")


def caso_a_wantlist_da_caixa_separa_o_sideboard():
    """A compra do sideboard vem depois de `// Sideboard` — o Cardmarket ignora a
    linha de comentário sem erro, e sem ela a lista colada era 75 linhas seguidas
    e ele voltava a ter de descobrir onde acabava o main."""
    repor()
    con = base()
    c, _rep = _caixa(con)
    w = c["wantlist"]
    assert [(x["nm"], x["q"], x["board"]) for x in w] == [
        ("Chromatic Star", 2, "side")], w
    abas = _abas(con)
    if abas is None:
        print("wantlist com sideboard: sem `node`, so o payload verificado")
        return
    html = abas["a"]
    assert "// Sideboard\n2 Chromatic Star" in html, html[-1500:]
    print("wantlist: o que e do sideboard sai depois de `// Sideboard`")


def caso_a_pagina_desenha_os_dois_blocos():
    """O que o browser mostra: os cabeçalhos dos dois blocos, com o "N de M". Um
    bloco que o payload traz e a página não desenha é uma página em branco sem
    erro nenhum — é o mesmo padrão do `event_tier`, do lado do browser."""
    repor()
    con = base()
    abas = _abas(con)
    if abas is None:
        print("blocos no HTML: sem `node`, saltado")
        return
    html = abas["a"]
    assert '<div class="bhdr">Main<span>3 de 3</span></div>' in html, html[:2000]
    assert '<div class="bhdr">Sideboard<span>1 de 3</span></div>' in html, html[:2000]
    print("a pagina desenha os dois blocos, com o N de M de cada um")


def caso_desmontar_limpa_e_regista():
    """O inverso do *"sleevado e na caixa"*: a `copy_allocation` desta caixa
    esvazia-se, a base é copiada antes e fica uma linha no `desmontar.log`.
    A 2026-09-08 isto fez-se em SQL à mão nas quatro caixas que herdaram alocação
    da migração — sem backup e sem rasto."""
    repor()
    con = base()
    assert webapp.marcar_na_caixa(con, "a", True) == 4
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation"
                       ).fetchone()["c"] == 3, "três lotes, quatro cópias"

    log = _TMP / "desmontar.log"
    r = loadout.desmontar_caixa(con, "a", "Caixa A", log_path=log)
    assert (r["linhas"], r["copias"]) == (3, 4), r
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation"
                       ).fetchone()["c"] == 0, "a caixa tem de ficar vazia"
    assert Path(r["backup"]).exists(), r["backup"]
    linha = log.read_text(encoding="utf-8").strip()
    assert "desmontar 'a'" in linha and "caixa='Caixa A'" in linha, linha
    assert "linhas=3 copias=4" in linha and "-desmontar.db" in linha, linha
    # Idempotente: uma caixa já vazia não escreve backup nem linha nenhuma.
    assert loadout.desmontar_caixa(con, "a", "Caixa A", log_path=log) == {
        "linhas": 0, "copias": 0, "backup": None}
    assert log.read_text(encoding="utf-8").strip() == linha, "não repete a linha"
    print("desmontar: alocacao limpa, backup da base e uma linha no desmontar.log")


def caso_o_botao_desmontar_esta_na_caixa_com_cartas_dentro():
    """A caixa NÃO se diz montada e tem cartas registadas lá dentro (o caso das
    quatro de 2026-09-08). É a ela que o botão faz falta — e desmontá-la não a
    promove a permanente: ele carregou para arrumar cartas, não para escolher
    prioridades."""
    repor()
    con = base()
    c, _rep = _caixa(con)
    assert c["arrumada"] is False and c["montado"] is False
    webapp.marcar_na_caixa(con, "a", True)
    c, _rep = _caixa(con)
    assert c["arrumada"] is True, "tem linhas na copy_allocation"

    abas = _abas(con, editable=True)
    if abas is not None:
        assert 'data-act="desmontar"' in abas["a"], abas["a"][-2000:]
        # E a página publicada não desenha botão nenhum (o harness já falha se
        # desenhar): confirma-se que o de desmontar também lá não está.
        assert 'data-act="desmontar"' not in _abas(con)["a"]

    cfg = webapp.ler_config()
    assert webapp.despromover(cfg, "a") == "Caixa A"
    r = webapp.desmontar(con, "a", "Caixa A")
    assert r["copias"] == 4, r
    assert loadout.caixas_arrumadas(con) == set()
    repor()
    print("o botao esta na caixa que tem cartas dentro, montada ou nao")


def run():
    for fn in (caso_montar_separa_main_do_sideboard,
               caso_a_wantlist_da_caixa_separa_o_sideboard,
               caso_a_pagina_desenha_os_dois_blocos,
               caso_desmontar_limpa_e_regista,
               caso_o_botao_desmontar_esta_na_caixa_com_cartas_dentro):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
