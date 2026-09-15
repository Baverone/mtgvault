"""AS PÁGINAS PESADAS TÊM OS DADOS À PARTE (André, 2026-09-15).

*"As páginas pesadas passam a ter os dados à parte, carregados a pedido. Ele
abdicou de as abrir offline a partir do disco; têm é de funcionar bem servidas
por HTTP — no GitHub Pages e no modo de edição (porto 8771), do telemóvel."*

Medido nesse dia, na base dele: `showcase.html` 1 266 KB (4 319 `<img>`),
`deckboxes.html` 694 KB (668 KB de JSON dentro do `<script>`), `reservedlist.html`
459 KB, `cobertura.html` 274 KB (123 KB de `var PRINT`/`var WANT`).

O que aqui se tranca — e cada caso tem de CHUMBAR se a tarefa não fizer nada:

  1. o `build` de cada página escreve a casca (sem dados) + `data/paginas/
     <pagina>.json` + `data/paginas/<pagina>/<parte>.json`, com `_gerado_em`
     de HOJE — e as partes velhas (uma caixa que saiu) desaparecem;
  2. o HTML encolheu MESMO: mede-se a casca contra a página inteira (a mesma
     base, os mesmos dados) e exige-se uma fracção;
  3. o payload da Deckboxes sobrevive à ida e volta (`partir` → ficheiros →
     `juntar`) sem perder uma chave;
  4. PONTA A PONTA: serve-se a pasta por HTTP, abre-se cada página com `node`
     (o `fetch` vai MESMO ao servidor) e confirma-se que a secção principal
     aparece depois do fetch; e, se o JSON não estiver lá, a página diz-lho em
     português em vez de ficar em branco;
  5. o `git add` do `daily.yml` e a lista da tarefa do ai-pc levam a pasta, e o
     `.gitignore` não a apanha.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CFG = {
    "caixas": [
        {"slot": "stifle", "nome": "Stiflenought", "formato": "premodern",
         "fonte": "deck", "ref": "Stiflenought", "balde": "Premodern (geral)",
         "estado": "permanente", "prioridade": 1},
        {"slot": "dc", "nome": "Cloud (Duel Commander)", "formato": "duel-commander",
         "fonte": "deck", "ref": "Cloud", "balde": "Cloud",
         "estado": "permanente", "prioridade": 2},
    ],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": False,
         "lingua": "pt", "edicoes": "premodern", "estrita": True,
         "baldes": ["Colecção", "Premodern (geral)", "SPML"]},
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "acabamento": "foil"},
    ],
    "loadout": [], "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_colecao": {}, "spml_formatos": {},
}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, paginas  # noqa: E402

import deckboxes  # noqa: E402
import meta_coverage  # noqa: E402
import reservedlist  # noqa: E402
import showcase  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
_ABERTAS = []

CATALOGO = [("Island", "unh", "2004-11-19", "Land", 0),
            ("Stifle", "scg", "2003-05-26", "Instant", 0),
            ("Sol Ring", "unh", "2004-11-19", "Artifact", 0),
            ("Cranial Plating", "mrd", "2003-10-02", "Artifact", 0),
            ("Frogmite", "mrd", "2003-10-02", "Artifact Creature", 0),
            ("Living End", "arb", "2009-04-30", "Sorcery", 0),
            ("Grief", "mh2", "2021-06-18", "Creature", 0),
            ("Mox Diamond", "sth", "1998-03-02", "Artifact", 1),
            ("Gaea's Cradle", "usg", "1998-10-12", "Land", 1)]


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, tl, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               set_type)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'',?,?,?,0,?,'expansion')""",
            (f"id-{i}", f"or-{i}", nm, sc, f"Set {sc}", str(i), tl,
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"premodern": "legal", "legacy": "legal", "modern": "legal",
                         "commander": "legal"}), rl))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    # Os decks das duas caixas.
    for nome, fmt, cartas in (("Stiflenought", "premodern", [("Stifle", 4), ("Island", 17)]),
                              ("Cloud", "duel-commander", [("Sol Ring", 1)])):
        con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?,?,?,'main')", (did, nm, q))
    # Uma cópia de cada coisa, para haver posse e RL.
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'").fetchone()["id"]
    for nm in ("Stifle", "Mox Diamond", "Sol Ring"):
        sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name=?", (nm,)).fetchone()[0]
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                       sub_collection_id) VALUES (?,1,'nonfoil','pt','player',?)""", (sid, sub))
    # Listas para o Showcase e a Cobertura (4 Challenges por arquétipo).
    n = 0
    for cartas in (["Cranial Plating", "Frogmite", "Sol Ring", "Stifle"],
                   ["Living End", "Grief", "Mox Diamond", "Gaea's Cradle"]):
        for _ in range(4):
            n += 1
            con.execute("""INSERT INTO decklists (source, source_key, format, player,
                           event_name, event_date, event_tier, placement)
                           VALUES ('mtgo', ?, 'modern', 'jogador', 'Challenge',
                                   ?, 'Challenge', '')""", (f"k{n}", date.today().isoformat()))
            did = con.execute("SELECT id FROM decklists WHERE source_key=?", (f"k{n}",)).fetchone()["id"]
            for c in cartas:
                con.execute("INSERT INTO decklist_cards (decklist_id, card_name, quantity, board) "
                            "VALUES (?,?,4,'main')", (did, c))
    con.commit()
    return con


_SITE = None


def site():
    """A pasta com as quatro páginas geradas + `data/paginas/` (uma vez)."""
    global _SITE
    if _SITE is None:
        con = base()
        d = Path(tempfile.mkdtemp())
        deckboxes.build(con, d / "deckboxes.html")
        showcase.build(con, d / "showcase.html")
        reservedlist.build(con, d / "reservedlist.html")
        meta_coverage.build(con, d / "cobertura.html")
        # A versão INTEIRA da Deckboxes, para medir o que se poupou.
        (d / "_inteira.html").write_text(deckboxes.html_page(con), encoding="utf-8")
        _SITE = (d, con)
    return _SITE


def caso_os_json_sao_escritos_ao_lado_e_de_hoje():
    d, _con = site()
    hoje = date.today().isoformat()
    for pagina in ("deckboxes", "showcase", "reservedlist", "cobertura"):
        idx = d / "data" / "paginas" / f"{pagina}.json"
        assert idx.is_file(), f"{pagina}: sem índice em data/paginas/"
        j = json.loads(idx.read_text(encoding="utf-8"))
        assert j["_gerado_em"].startswith(hoje), (pagina, j["_gerado_em"])
        assert j["_partes"], f"{pagina}: sem partes"
        for p in j["_partes"]:
            f = d / "data" / "paginas" / pagina / f"{p}.json"
            assert f.is_file(), f"{pagina}/{p}.json em falta"
            json.loads(f.read_text(encoding="utf-8"))     # é JSON válido
        casca = (d / f"{pagina}.html").read_text(encoding="utf-8")
        assert '<script id="dados"' not in casca, f"{pagina}: a casca leva dados"
        assert "carregaDados(" in casca and "erroDados(" in casca, pagina
    print("as quatro paginas escrevem indice + partes em data/paginas/, com a data de hoje")


def caso_as_partes_velhas_desaparecem():
    d, _con = site()
    pasta = d / "data" / "paginas" / "deckboxes"
    velha = pasta / "caixa-que-ja-nao-existe.json"
    velha.write_text("{}", encoding="utf-8")
    idx, partes = paginas.ler_dados(d / "deckboxes.html", "deckboxes")
    paginas.escrever_dados(d / "deckboxes.html", "deckboxes", idx, partes)
    assert not velha.exists(), "uma parte de uma caixa que saiu ficava a responder para sempre"
    print("as partes que deixaram de existir sao apagadas")


def caso_o_html_encolheu_mesmo():
    d, _con = site()
    inteira = (d / "_inteira.html").stat().st_size
    casca = (d / "deckboxes.html").stat().st_size
    # O que saiu da página é EXACTAMENTE o payload: numa base pequena são
    # poucos KB, na dele 670 KB — a medida certa é a diferença contra o JSON.
    dados = sum(f.stat().st_size for f in (d / "data" / "paginas" / "deckboxes").glob("*.json"))
    assert casca < inteira and inteira - casca >= 0.8 * dados, \
        ("a casca da Deckboxes tem de perder o payload inteiro", casca, inteira, dados)
    # As outras três: a casca fica sem as grelhas — cabe em poucas dezenas de KB
    # mesmo com a base dele (medido: showcase 12 KB, reservedlist 14 KB,
    # cobertura 27 KB, contra 1 266 / 459 / 274 KB).
    for pagina, tecto in (("showcase", 60_000), ("reservedlist", 60_000),
                          ("cobertura", 80_000)):
        tam = (d / f"{pagina}.html").stat().st_size
        assert tam < tecto, (pagina, tam)
    print(f"deckboxes: {inteira} -> {casca} bytes; as outras cascas cabem no tecto")


def caso_o_payload_sobrevive_a_ida_e_volta():
    d, con = site()
    original = json.loads(json.dumps(deckboxes.payload(con, __import__("mtgvault.loadout").loadout.report(con)),
                                     ensure_ascii=False))
    idx, partes = deckboxes.partir(original)
    assert all(k not in idx for k in ("compras", "partilhadas", "basicas"))
    assert "cartas" not in idx["caixas"][0] and idx["caixas"][0]["parte"] == "caixa-stifle"
    assert idx["n_partilhadas"] == len(original["partilhadas"])
    assert deckboxes.juntar(idx, partes) == original, "perdeu-se uma chave na ida e volta"
    assert deckboxes.ler_dados(d / "deckboxes.html")["caixas"][0]["slot"] == "stifle"
    print("partir -> ficheiros -> juntar: o payload volta igual")


class _Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _servir(pasta):
    s = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Silencioso, directory=str(pasta)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


def _abrir(url):
    saida = Path(tempfile.mkdtemp()) / "dom.json"
    p = subprocess.run(["node", str(Path(__file__).with_name("abrir_pagina.js")),
                        url, str(saida)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(saida.read_text(encoding="utf-8"))


def caso_ponta_a_ponta_servida_por_http():
    if not shutil.which("node"):
        print("ponta a ponta: sem `node`, saltado")
        return
    d, _con = site()
    srv, url = _servir(d)
    try:
        dom = _abrir(f"{url}/deckboxes.html")
        vista = dom["#vista"]
        assert "Por onde começar" in vista, vista[:400]          # o Plano, a aba inicial
        assert "Stiflenought" in dom["#decktabs"], dom["#decktabs"][:300]
        assert "carregando" not in vista and "erro-dados" not in vista, vista[:400]

        dom = _abrir(f"{url}/showcase.html")
        painel = dom['.fpanel[data-f="modern"]']
        assert painel.count("<details") == 2 and "Affinity" in painel, painel[:400]
        assert 'class="cards"' in painel, "o primeiro arquétipo vem aberto, com a grelha"

        dom = _abrir(f"{url}/reservedlist.html")
        grelhas = {k: v for k, v in dom.items() if k.startswith("grid:ed:")}
        assert len(grelhas) == 2, list(dom)
        assert any("Mox Diamond" in v for v in grelhas.values()), grelhas
        assert all('class="c ' in v for v in grelhas.values()), "cada edição desenha as cartas"

        dom = _abrir(f"{url}/cobertura.html")
        # (Sem `archetypes` na base de teste as secções vêm vazias — o que se
        # tranca é que cada uma foi buscar a sua parte sem erro.)
        grelhas = {k: v for k, v in dom.items() if k.startswith("grid:fmt:")}
        assert "grid:fmt:modern" in grelhas, list(dom)
        assert all("erro-dados" not in v and "carregando" not in v
                   for v in grelhas.values()), grelhas
        print("ponta a ponta: as quatro paginas desenham a seccao principal depois do fetch")

        # SEM os dados: a mensagem, em português, em vez de um ecrã em branco.
        shutil.rmtree(d / "data" / "paginas" / "deckboxes")
        (d / "data" / "paginas" / "deckboxes.json").unlink()
        dom = _abrir(f"{url}/deckboxes.html")
        assert "Não consegui carregar" in dom["#vista"] and "404" in dom["#vista"], dom["#vista"]
        print("sem o JSON, a pagina diz-lhe em portugues o que falhou")
    finally:
        srv.shutdown()
        global _SITE
        _SITE = None


def caso_a_pasta_vai_ao_git_e_nao_esta_ignorada():
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert "data/paginas" in linha.split(), "o daily.yml não faz `git add data/paginas`"
    tarefa = Path(r"C:\Users\Catarina\Desktop\ai-pc\tasks\mtgvault-daily\run.py")
    if tarefa.exists():
        assert "data/paginas" in tarefa.read_text(encoding="utf-8"), \
            "a tarefa mtgvault-daily do ai-pc não publica data/paginas"
    # O `.gitignore` não pode apanhar a pasta por engano.
    p = subprocess.run(["git", "-C", str(RAIZ), "check-ignore", "-q",
                        "data/paginas/deckboxes.json"], capture_output=True)
    assert p.returncode == 1, "data/paginas/ está a ser ignorada pelo .gitignore"
    print("data/paginas vai ao git add do workflow e da tarefa, e nao esta no .gitignore")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for f in CASOS:
        f()
    print(f"\n{len(CASOS)} casos ok")
