"""As páginas contam a posse pela ALOCAÇÃO do loadout, não à sua maneira.

O erro que obrigou a isto, nas palavras do André (2026-09-07): *"Meti 4 fotos,
estavam lá 4 Utrom Monitor, mas no deck Pauper não aparecem como se eu tivesse a
carta."* O `meusdecks` contava só as cópias do balde ligado ao deck
(`deck_collection` → `Pauper Affinity`) e os quatro Utrom Monitor estão no
`SPML`: existiam, serviam a caixa, e a página dizia que faltavam.

O que aqui se tranca:

  1. o deck vigiado que é uma caixa do loadout conta o que a ALOCAÇÃO lhe deu —
     venha do balde que vier (o caso Utrom Monitor);
  2. uma carta que está NOUTRA caixa é o terceiro estado, e as faltas desta
     página somam `comprar`, não `missing` (senão volta a pedir cópias que ele
     já tem — foi por isso que a regra nasceu);
  3. um deck que NÃO é caixa do loadout mantém a contagem antiga (a coleção
     inteira), que é o que se pode dizer sem inventar;
  4. o `foil_report` (o top-N do `metagame.html`) ordena pelo que ele está mais
     perto de concluir, conta a regra do foil e o "está noutra caixa", e o custo
     é só sobre o que é mesmo compra;
  5. `metagame_top_n` sai do colecao_config.json e vale 3 por omissão.

Não toca na rede.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Config próprio: o teste não pode passar a depender de o André não mexer no dele.
CFG = {
    "loadout": [
        {"slot": "pauper", "nome": "Pauper (Luffy)", "formato": "pauper",
         "fonte": "vigiado", "ref": "Luffy — Pauper", "balde": "Pauper Affinity",
         "prioridade": 1, "montado": True},
        {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
         "fonte": "deck", "ref": "UW Oswald", "balde": "SPML",
         "acabamento": "foil", "prioridade": 2},
    ],
    "decks_vigiados": ["UW Oswald"],
    "premodern_arquetipos_alvo": [],
    "regras_colecao": {},
}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import db, loadout  # noqa: E402

import deckboxes  # noqa: E402
import meusdecks  # noqa: E402
import metagame  # noqa: E402

CATALOGO = [
    ("Utrom Monitor", "tmnt", "2025-09-26"),
    ("Frogmite", "mrd", "2003-10-02"),
    ("Thoughtcast", "mrd", "2003-10-02"),
    ("Island", "4bb", "1995-04-01"),
]

_ABERTAS = []      # segura os context managers: sem isto o GC fecha a ligação


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','common','Artifact Creature',2,'U',?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]),
             rel, json.dumps({"pauper": "legal", "modern": "legal",
                              "legacy": "legal", "commander": "legal"})))
    # O `deck_collection` só existe no vault.db do André — não está no schema.sql
    # nem no db._migrate() (ver CLAUDE.md). Numa base nova cria-se aqui.
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub=None):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = None
    if sub:
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
        sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                             (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub_id))
    con.commit()


def vigiado(con, label, fmt, balde, cards):
    con.execute("INSERT INTO watched (kind, key, label, format) "
                "VALUES ('mtgo_player', ?, ?, ?)", (label, label, fmt))
    wid = con.execute("SELECT id FROM watched WHERE label = ?", (label,)).fetchone()["id"]
    con.execute("""INSERT INTO watched_snapshots (watched_id, taken_at, list_hash, cards)
                   VALUES (?, '2026-09-07', 'h1', ?)""",
                (wid, json.dumps([[b, n, q] for b, n, q in cards])))
    con.execute("INSERT INTO deck_collection (watched_id, sub_collection) VALUES (?,?)",
                (wid, balde))
    con.commit()
    return wid


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def _por_nome(cards):
    return {c["nm"]: c for c in cards}


# ---------------------------------------------------------------------------
def caso_utrom_monitor():
    """O bug, à letra. Os 4 Utrom Monitor estão no SPML e o deck Pauper leva-os:
    a caixa do Pauper é quem os aloca, por isso a página tem de os dar como tidos."""
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Utrom Monitor", 4), ("main", "Frogmite", 4)])
    add(con, "Utrom Monitor", 4, sub="SPML")            # <- noutro balde
    add(con, "Frogmite", 4, sub="Pauper Affinity")

    por_lista = loadout.slots_por_lista(loadout.allocate(con))
    d = meusdecks._watched_decks(con, {}, {}, set(), por_lista)[0]
    c = _por_nome(d["main"])["Utrom Monitor"]
    assert c["hq"] == 4 and c["state"] == "have", c
    assert c["comprar"] == 0 and c["oq"] == 0, c
    assert not meusdecks._faltas(d["main"] + d["side"]), "não falta nada"
    print("Utrom Monitor no SPML conta para a caixa do Pauper")

    # E sem o loadout (o deck deixa de ser caixa) volta o comportamento antigo:
    # só o balde ligado ao deck, que é onde o bug vivia.
    velho = meusdecks._watched_decks(con, {}, {}, set(), {})[0]
    assert _por_nome(velho["main"])["Utrom Monitor"]["state"] == "miss"
    print("sem loadout, a contagem antiga (só o balde) — era aqui o erro")


def caso_noutra_caixa_e_o_terceiro_estado():
    """Duas caixas querem a mesma carta e só há um playset: a de prioridade mais
    baixa mostra 'em <caixa>' e NÃO a mete nas faltas. Somar `missing` mandava-o
    comprar 4 Frogmite que estão na caixa do lado."""
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Frogmite", 4)])
    deck(con, "UW Oswald", "modern", [("Frogmite", 4), ("Thoughtcast", 4)])
    add(con, "Frogmite", 4, finish="foil", sub="SPML")

    por_lista = loadout.slots_por_lista(loadout.allocate(con))
    linhas = loadout.linhas_por_carta(por_lista["UW Oswald"])
    cards = meusdecks._cards([("Frogmite", 4), ("Thoughtcast", 4)],
                            {}, {}, {}, linhas, "main")
    fg = _por_nome(cards)["Frogmite"]
    assert fg["state"] == "noutra" and fg["oq"] == 4 and fg["hq"] == 0, fg
    assert fg["onde"] == {"Pauper (Luffy)": 4}, fg["onde"]
    assert fg["comprar"] == 0, fg

    tc = _por_nome(cards)["Thoughtcast"]
    assert tc["state"] == "miss" and tc["comprar"] == 4, tc

    faltas = meusdecks._faltas(cards)
    assert faltas == {"Thoughtcast": 4}, faltas
    print("carta noutra caixa: terceiro estado, e fora das faltas")


def caso_deck_fora_do_loadout_conta_a_colecao_toda():
    """Um deck que não é caixa nenhuma continua a contar a coleção inteira — é o
    que se pode dizer sem inventar uma alocação que não existe."""
    cards = meusdecks._cards([("Frogmite", 4), ("Island", 8)], {}, {},
                            {"Frogmite": 2}, None, "main")
    fg = _por_nome(cards)["Frogmite"]
    assert fg["hq"] == 2 and fg["oq"] == 0 and fg["state"] == "part", fg
    assert meusdecks._faltas(cards) == {"Frogmite": 2}
    # Básicas: assume-se que as tem sempre.
    assert _por_nome(cards)["Island"]["state"] == "have"
    print("deck fora do loadout: contagem antiga, coleção inteira")


def caso_pagina_meusdecks_fecha():
    """A página tem de se escrever ponta a ponta com a alocação lá dentro."""
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Utrom Monitor", 4)])
    deck(con, "UW Oswald", "modern", [("Frogmite", 4)])
    add(con, "Utrom Monitor", 4, sub="SPML")
    out = Path(tempfile.mkdtemp()) / "meusdecks.html"
    meusdecks.build(con, out)
    txt = out.read_text(encoding="utf-8")
    assert "Utrom Monitor" in txt and "Luffy — Pauper" in txt
    print("meusdecks.html escreve-se com a alocação do loadout")


# ---------------------------------------------------------------------------
def caso_top_n_do_config():
    assert metagame.top_n() == 3, "o default do André é 3 (top-3), não 2"
    print("metagame_top_n: 3 por omissão")


def caso_foil_report_ve_as_outras_caixas():
    """O ranking do `metagame.html`: conta a regra do foil, dá como TIDA a carta
    que está noutra caixa (vai-se buscar) e só cobra o que é mesmo compra."""
    con = base()
    con.execute("INSERT INTO archetypes (format, label) VALUES ('modern','Affinity')")
    aid = con.execute("SELECT id FROM archetypes").fetchone()["id"]
    for nm in ("Frogmite", "Thoughtcast"):
        con.execute("""INSERT INTO card_roles (archetype_id, window_end, window_days,
                       card_name, board, n_lists, n_with_card, inclusion_rate,
                       avg_copies, core_copies, flex_copies, dist, role)
                       VALUES (?, '2026-09-07', 30, ?, 'main', 10, 10, 1.0,
                               4, 4, 0, ?, 'core')""",
                    (aid, nm, json.dumps({"4": 1.0})))
    for i in range(10):
        con.execute("""INSERT INTO decklists (source, source_key, format, event_date,
                       event_tier, archetype_id)
                       VALUES ('mtgo', ?, 'modern', '2026-09-01', 'Challenge', ?)""",
                    (f"k{i}", aid))
    # Ligas não contam: se contassem, o `n_lists` da página vinha inflacionado por
    # listas que o ranking do metagame nem vê (é a regra de `sources.counting_sql`).
    for i in range(50):
        con.execute("""INSERT INTO decklists (source, source_key, format, event_date,
                       event_tier, archetype_id)
                       VALUES ('mtgo', ?, 'modern', '2026-09-01', 'League', ?)""",
                    (f"liga{i}", aid))
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name='Thoughtcast'"
                      ).fetchone()["scryfall_id"]
    con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date, trend)
                   VALUES (?, 'cardmarket', 'foil', '2026-09-07', 5.0)""", (sid,))
    con.commit()

    # 4 Frogmite foil, mas a caixa do Pauper (prioridade 1) leva-as.
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Frogmite", 4)])
    add(con, "Frogmite", 4, finish="foil", sub="SPML")
    add(con, "Thoughtcast", 4, finish="nonfoil", sub="SPML")   # nonfoil: não serve

    res = loadout.allocate(con)
    r = loadout.foil_report(con, "modern", top=3, min_lists=5, res=res)[0]
    assert r["n_lists"] == 10, ("só as 10 Challenges contam; as 50 ligas não",
                                r["n_lists"])
    assert r["got"] == 0 and r["noutra_q"] == 4, r
    ln = {m["nm"]: m for m in r["linhas"]}
    assert ln["Frogmite"]["noutra"] == {"Pauper (Luffy)": 4}, ln["Frogmite"]
    assert ln["Frogmite"]["comprar"] == 0 and ln["Frogmite"]["cost"] == 0
    # A nonfoil não fecha o slot: é compra, e ao preço FOIL.
    assert ln["Thoughtcast"]["comprar"] == 4, ln["Thoughtcast"]
    assert r["custo"] == 20.0, r["custo"]
    assert r["comprar"] == 4 and r["tenho"] == 4 and r["pct"] == 50, r
    print("foil_report: 'noutra caixa' é posse, e o custo é só do que se compra")


def caso_pagina_metagame_fecha():
    """A página escreve-se ponta a ponta: uma secção 'top' com o arquétipo, uma
    secção 'caixas' com o deck já escolhido, e as que não têm listas dizem-no em
    vez de ficarem em branco."""
    con = base()
    con.execute("INSERT INTO archetypes (format, label) VALUES ('legacy','Affinity')")
    aid = con.execute("SELECT id FROM archetypes").fetchone()["id"]
    con.execute("""INSERT INTO card_roles (archetype_id, window_end, window_days,
                   card_name, board, n_lists, n_with_card, inclusion_rate,
                   avg_copies, core_copies, flex_copies, dist, role)
                   VALUES (?, '2026-09-07', 30, 'Frogmite', 'main', 10, 10, 1.0,
                           4, 4, 0, ?, 'core')""", (aid, json.dumps({"4": 1.0})))
    for i in range(10):
        con.execute("""INSERT INTO decklists (source, source_key, format, event_date,
                       event_tier, archetype_id)
                       VALUES ('mtgo', ?, 'legacy', '2026-09-01', 'Challenge', ?)""",
                    (f"k{i}", aid))
    con.commit()
    deck(con, "UW Oswald", "modern", [("Thoughtcast", 4)])
    add(con, "Frogmite", 4, finish="foil", sub="SPML")

    out = Path(tempfile.mkdtemp()) / "metagame.html"
    metagame.build(con, out)
    txt = out.read_text(encoding="utf-8")
    assert "Frogmite" in txt, "o top-N de Legacy tem de aparecer"
    assert "UW Oswald" in txt, "a caixa escolhida de Modern tem de aparecer"
    assert "Sem listas que contem" in txt, "os formatos vazios dizem-no"
    print("metagame.html escreve-se: top-N, caixa escolhida e formatos vazios")


# ---------------------------------------------------------------------------
# Deckboxes: o payload e o JavaScript que o desenha
# ---------------------------------------------------------------------------
def _pagina_deckboxes():
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Utrom Monitor", 4), ("main", "Frogmite", 4)])
    deck(con, "UW Oswald", "modern", [("Frogmite", 4), ("Thoughtcast", 4)])
    add(con, "Utrom Monitor", 4, sub="SPML")
    add(con, "Frogmite", 4, finish="foil", sub="SPML")
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out)
    return out


def caso_payload_do_deckboxes():
    """A página nova é JSON + JavaScript: se o payload não fechar, a página
    aparece em branco sem um único erro no gerador."""
    txt = _pagina_deckboxes().read_text(encoding="utf-8")
    bruto = re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                      txt, re.S).group(1)
    d = json.loads(bruto.replace("<\\/", "</"))
    assert d["editable"] is False, "o site publicado NÃO pode vir editável"
    caixas = {c["slot"]: c for c in d["caixas"]}
    assert set(caixas) == {"pauper", "modern"}, list(caixas)
    assert caixas["pauper"]["permanente"] is True
    # O caso Utrom Monitor, agora pelo lado da página nova.
    um = next(c for c in caixas["pauper"]["cartas"] if c["nm"] == "Utrom Monitor")
    assert um["est"] == "have" and um["lotes"][0]["local"] == "SPML", um
    # E o Frogmite que o Pauper levou aparece ao Modern como "noutra caixa".
    fg = next(c for c in caixas["modern"]["cartas"] if c["nm"] == "Frogmite")
    assert fg["est"] == "sub" and fg["noutra"] == {"Pauper (Luffy)": 4}, fg
    assert fg["comprar"] == 0
    assert not any(w["nm"] == "Frogmite" for w in caixas["modern"]["wantlist"])
    print("o payload do deckboxes fecha, e o publicado nao traz botoes")


def caso_javascript_do_deckboxes_desenha_todas_as_abas():
    """Corre o JavaScript da página num DOM de mentira e manda desenhar TODAS as
    abas, nos dois filtros. Um erro de render numa aba que não é a inicial só
    aparecia ao clicar — e a página ficava em branco, sem o gerador dar erro
    nenhum. É o mesmo padrão do `event_tier`, mas do lado do browser.

    O harness também confirma que a página publicada **não desenha** nenhum
    botão de escrita (os endpoints não existem no GitHub Pages).

    Salta em silêncio se não houver `node`: a bateria tem de correr num PC sem
    ele (é a regra dos testes sem rede e sem dependências)."""
    if not shutil.which("node"):
        print("javascript do deckboxes: sem `node`, saltado")
        return
    pagina = _pagina_deckboxes()
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    assert "renders sem erro" in p.stdout, p.stdout
    print("javascript do deckboxes: " + p.stdout.strip())


def run():
    for fn in (caso_utrom_monitor, caso_noutra_caixa_e_o_terceiro_estado,
               caso_deck_fora_do_loadout_conta_a_colecao_toda,
               caso_pagina_meusdecks_fecha, caso_top_n_do_config,
               caso_foil_report_ve_as_outras_caixas, caso_pagina_metagame_fecha,
               caso_payload_do_deckboxes,
               caso_javascript_do_deckboxes_desenha_todas_as_abas):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
