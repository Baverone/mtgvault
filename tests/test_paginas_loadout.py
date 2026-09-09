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
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from datetime import date  # noqa: E402

from mtgvault import db, loadout, paginas, sources  # noqa: E402

import deckboxes  # noqa: E402
import meta_coverage as mc  # noqa: E402
import metagame  # noqa: E402
import meusdecks  # noqa: E402
import webapp  # noqa: E402

CATALOGO = [
    ("Utrom Monitor", "tmnt", "2025-09-26"),
    ("Frogmite", "mrd", "2003-10-02"),
    ("Thoughtcast", "mrd", "2003-10-02"),
    ("Island", "4bb", "1995-04-01"),
    # Não está em deck nenhum: serve só para a tabela de venda ter uma linha
    # FOIL a par de uma nonfoil (ver `caso_aba_vender_nao_marca_nonfoil`).
    ("Chromatic Star", "shm", "2008-05-02"),
    # Da era Premodern (até ao Scourge, 2003-05-26): é a carta dos casos do
    # tecto de playset e da ordem por % completo.
    ("Swords to Plowshares", "4bb", "1995-04-01"),
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
def _caixas_de(con, cfg_slots=None):
    """As caixas do payload da Deckboxes, por slot. É onde a posse vive na v6:
    a página *Decks permanentes* desapareceu (fazia a mesma pergunta e respondia
    outro número), e estes casos passaram a interrogar a página que ficou."""
    rep = loadout.report(con, cfg_slots)
    return {c["slot"]: c for c in deckboxes.payload(con, rep)["caixas"]}


def caso_utrom_monitor():
    """O bug, à letra. Os 4 Utrom Monitor estão no SPML e o deck Pauper leva-os:
    a caixa do Pauper é quem os aloca, por isso a página tem de os dar como tidos."""
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Utrom Monitor", 4), ("main", "Frogmite", 4)])
    add(con, "Utrom Monitor", 4, sub="SPML")            # <- noutro balde
    add(con, "Frogmite", 4, sub="Pauper Affinity")

    caixa = _caixas_de(con)["pauper"]
    c = _por_nome(caixa["cartas"])["Utrom Monitor"]
    assert c["got"] == 4 and c["est"] == "have", c
    assert c["comprar"] == 0 and c["noutra"] == {}, c
    assert c["lotes"][0]["local"] == "SPML", c["lotes"]
    assert not caixa["wantlist"], "não falta nada nesta caixa"
    print("Utrom Monitor no SPML conta para a caixa do Pauper")

    # A carta a tirar da gaveta certa: o painel Montar diz "de SPML", que é o
    # gesto que ele faz. Era esta a metade que faltava — a página antiga sabia
    # que tinha a carta e não dizia onde ela estava.
    tirar = {m["nm"]: m for m in caixa["montar"]["tirar"]}
    assert tirar["Utrom Monitor"]["de"] == "SPML", tirar
    assert caixa["montar"]["por_gaveta"].get("SPML") == 4, caixa["montar"]
    print("e o painel Montar manda tirá-los do SPML")


def caso_noutra_caixa_e_o_terceiro_estado():
    """Duas caixas querem a mesma carta e só há um playset: a de prioridade mais
    baixa mostra 'em <caixa>' e NÃO a mete na wantlist. Somar `missing` mandava-o
    comprar 4 Frogmite que estão na caixa do lado.

    A caixa que empresta é aqui o Pauper com `dedicado: false` — desde
    2026-09-07 (19:00) o "ir buscar" só existe fora dos grupos dedicados
    (Duel Commander e SPML), e o outro lado está no fim do caso.
    """
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Frogmite", 4)])
    deck(con, "UW Oswald", "modern", [("Frogmite", 4), ("Thoughtcast", 4)])
    add(con, "Frogmite", 4, finish="foil", sub="SPML")

    empresta = [dict(s, dedicado=False) for s in CFG["loadout"]]
    modern = _caixas_de(con, empresta)["modern"]
    cards = _por_nome(modern["cartas"])
    fg = cards["Frogmite"]
    assert fg["est"] == "sub" and fg["missing"] == 4 and fg["got"] == 0, fg
    assert fg["noutra"] == {"Pauper (Luffy)": 4}, fg["noutra"]
    assert fg["comprar"] == 0, fg

    tc = cards["Thoughtcast"]
    assert tc["est"] == "miss" and tc["comprar"] == 4, tc

    assert [w["nm"] for w in modern["wantlist"]] == ["Thoughtcast"], modern["wantlist"]
    print("carta noutra caixa: terceiro estado, e fora da wantlist")

    # E com a caixa do Pauper DEDICADA (o default de 2026-09-07 às 19:00) a
    # mesma carta deixa de ser "em <caixa>" e passa a compra: *"cada deck montado
    # deixa de partilhar cartas com outros decks"*.
    modern = _caixas_de(con)["modern"]
    fg = _por_nome(modern["cartas"])["Frogmite"]
    assert fg["est"] == "miss" and fg["comprar"] == 4 and fg["noutra"] == {}, fg
    assert {w["nm"] for w in modern["wantlist"]} == {"Frogmite", "Thoughtcast"}
    print("com a caixa dedicada, a mesma carta e compra e nao 'ir buscar'")


def caso_coleccao_inteira_e_informacao_secundaria():
    """"Quantas tenho ao todo" era a única coisa que a página dos decks dizia e
    esta não. Na v6 entra como informação SECUNDÁRIA de cada carta: o número que
    manda continua a ser o da alocação, senão volta a haver duas respostas para a
    mesma pergunta — que era o defeito a corrigir."""
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Frogmite", 2)])
    add(con, "Frogmite", 4, sub="SPML")        # tem 4 na colecção, a caixa usa 2
    caixa = _caixas_de(con)["pauper"]
    fg = _por_nome(caixa["cartas"])["Frogmite"]
    assert fg["need"] == 2 and fg["got"] == 2, fg
    assert fg["col"] == 4, ("a colecção inteira tem 4", fg)
    print("colecção inteira: informação secundária, a alocação é que manda")


def caso_meusdecks_reencaminha():
    """A *Decks permanentes* foi fundida na Deckboxes; o ficheiro fica como
    reencaminhamento porque o telemóvel dele tem o link no histórico."""
    out = Path(tempfile.mkdtemp()) / "meusdecks.html"
    meusdecks.build(None, out)
    txt = out.read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in txt and "deckboxes.html" in txt, txt[:400]
    assert "Decks permanentes" not in paginas.nav("deckboxes.html"), \
        "a página fundida não pode continuar no menu"
    assert 'href="meusdecks.html"' not in paginas.nav("index.html", extra=True)
    print("meusdecks.html reencaminha para as Deckboxes, e saiu do menu")


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

    # A caixa que empresta tem de ser não-dedicada: um arquétipo candidato não
    # conta com uma cópia que está sleevada dentro de uma caixa dedicada (regra
    # de 2026-09-07, 19:00 — verificada logo a seguir).
    res = loadout.allocate(con, [dict(s, dedicado=False) for s in CFG["loadout"]])
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

    # Com a caixa do Pauper dedicada (o default), os 4 Frogmite deixam de contar
    # para o candidato: quem quiser este arquétipo compra os seus.
    d = loadout.foil_report(con, "modern", top=3, min_lists=5,
                            res=loadout.allocate(con))[0]
    assert d["noutra_q"] == 0 and d["comprar"] == 8 and d["pct"] == 0, d
    print("uma caixa dedicada nao empresta ao ranking de arquetipos")


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


import contextlib  # noqa: E402


@contextlib.contextmanager
def config(**extra):
    """Corre com um `colecao_config.json` alterado, e repõe o do teste no fim."""
    from mtgvault import sources
    antigo = os.environ["MTGVAULT_CONFIG"]
    novo = Path(tempfile.mkdtemp()) / "cfg.json"
    novo.write_text(json.dumps({**CFG, **extra}, ensure_ascii=False),
                    encoding="utf-8")
    os.environ["MTGVAULT_CONFIG"] = str(novo)
    sources._CFG_CACHE.clear()
    try:
        yield novo
    finally:
        os.environ["MTGVAULT_CONFIG"] = antigo
        sources._CFG_CACHE.clear()


def _base_legacy():
    """Um arquétipo de Legacy com lista de consenso e uma caixa por escolher."""
    con = base()
    con.execute("INSERT INTO archetypes (format, label) VALUES "
                "('legacy','Frogmite / Thoughtcast')")
    aid = con.execute("SELECT id FROM archetypes").fetchone()["id"]
    for nm, inc in (("Frogmite", 1.0), ("Thoughtcast", 0.9)):
        con.execute("""INSERT INTO card_roles (archetype_id, window_end, window_days,
                       card_name, board, n_lists, n_with_card, inclusion_rate,
                       avg_copies, core_copies, flex_copies, dist, role)
                       VALUES (?, '2026-09-07', 30, ?, 'main', 10, 10, ?,
                               4, 4, 0, ?, 'core')""",
                    (aid, nm, inc, json.dumps({"4": 1.0})))
    for i in range(10):
        con.execute("""INSERT INTO decklists (source, source_key, format, event_date,
                       event_tier, archetype_id)
                       VALUES ('mtgo', ?, 'legacy', '2026-09-01', 'Challenge', ?)""",
                    (f"k{i}", aid))
    con.commit()
    return con, aid


def caso_nome_de_arquetipo_e_legivel():
    """*"Os nomes dos arquétipos por pares de cartas são fracos"* (André,
    2026-09-07, 19:00). Sem nome próprio, o nome passa a ser **cores +
    carta-chave** e o par fica como subtítulo — nunca um nome com `/`."""
    con, aid = _base_legacy()
    df, tc = mc._format_df(con, "legacy"), {}
    nome = mc._name_for(con, aid, df, tc)
    # As cartas do fixture são todas azuis (`color_identity` = 'U').
    assert nome == "Mono-Azul Frogmite", nome
    assert "/" not in nome, nome
    assert mc._distinctive_name(con, aid, df, tc) == "Frogmite / Thoughtcast"
    # E um arquétipo com carta-assinatura mantém o nome próprio, sem cores.
    assert mc._known_name(con, aid) is None
    print("nome de arquetipo: cores + carta-chave, e o par como subtitulo")


def caso_vou_montar_este_escolhe_e_desmarca():
    """*"Cada deck do top-3 tem um botão «vou montar este»"* (André, 2026-09-07,
    19:00): escreve a lista de consenso CONGELADA COM A DATA no config, marca a
    caixa como permanente, e o "já não vou montar este" devolve o que lá estava.
    """
    con, aid = _base_legacy()
    caixa = {"slot": "legacy", "nome": "Legacy", "formato": "legacy",
             "fonte": "deck", "ref": None, "balde": "SPML", "prioridade": 3,
             "por_confirmar": True, "permanente": False}
    with config(loadout=CFG["loadout"] + [caixa]) as caminho:
        cfg = webapp.ler_config()
        msg = webapp.escolher_lista(con, cfg, "legacy", aid)
        assert "Mono-Azul Frogmite" in msg, msg
        webapp.escrever_config(cfg, caminho)
        sources._CFG_CACHE.clear()

        s = next(x for x in loadout.resolve_slots(con) if x["slot"] == "legacy")
        assert s["fonte"] == "escolhido" and s["ref"] == "legacy", s
        assert s["permanente"] is True and not s["vazio"], s
        assert s["escolhido_em"] == date.today().isoformat(), s
        assert s["nome"] == "Legacy — Mono-Azul Frogmite", s["nome"]
        assert ("Frogmite", 4) in [(n, q) for _b, n, q in s["cards"]], s["cards"]

        # A lista fica congelada: mudar o consenso não lhe toca.
        con.execute("UPDATE card_roles SET core_copies = 1 WHERE card_name='Frogmite'")
        con.commit()
        s = next(x for x in loadout.resolve_slots(con) if x["slot"] == "legacy")
        assert ("Frogmite", 4) in [(n, q) for _b, n, q in s["cards"]], \
            "a lista escolhida nao pode mudar debaixo dos pes"

        # O botão só existe no modo edição, e o publicado diz a data.
        ed, pub = (metagame.html_page(con, editable=True),
                   metagame.html_page(con))
        assert 'data-act="escolher"' in ed or 'data-act="desmarcar"' in ed, "sem botao"
        assert "data-act=" not in pub, "o site publicado nao pode ter botoes"
        assert "escolhido em" in pub, "o publicado tem de dizer quando escolheste"

        cfg = webapp.ler_config()
        webapp.desmarcar_lista(cfg, "legacy")
        webapp.escrever_config(cfg, caminho)
        sources._CFG_CACHE.clear()
        volta = json.loads(caminho.read_text(encoding="utf-8"))
        assert "listas_escolhidas" not in volta, volta.get("listas_escolhidas")
        s = next(x for x in loadout.resolve_slots(con) if x["slot"] == "legacy")
        assert s["fonte"] == "deck" and s["ref"] is None and s["vazio"], s
        assert s["permanente"] is False and s.get("por_confirmar") is True, s
    print("'vou montar este' congela a lista com a data, e desmarcar devolve tudo")


# ---------------------------------------------------------------------------
# Deckboxes: o payload e o JavaScript que o desenha
# ---------------------------------------------------------------------------
def _base_deckboxes():
    con = base()
    vigiado(con, "Luffy — Pauper", "pauper", "Pauper Affinity",
            [("main", "Utrom Monitor", 4), ("main", "Frogmite", 4)])
    deck(con, "UW Oswald", "modern", [("Frogmite", 4), ("Thoughtcast", 4)])
    add(con, "Utrom Monitor", 4, sub="SPML")
    add(con, "Frogmite", 4, finish="foil", sub="SPML")
    # Excedente para a aba Vender ter as duas metades do caso: 2 Utrom Monitor
    # NONFOIL a mais (o playset são 4) e 1 Chromatic Star FOIL a mais.
    add(con, "Utrom Monitor", 2, sub="SPML")
    add(con, "Chromatic Star", 5, finish="foil", sub="SPML")
    return con


def _pagina_deckboxes(con=None):
    con = con if con is not None else _base_deckboxes()
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out)
    return out


def _abas_desenhadas(pagina):
    """`{aba: HTML}` — o que o browser mostraria, corrido pelo harness de node.
    `None` quando não há `node` (a bateria tem de correr num PC sem ele)."""
    if not shutil.which("node"):
        return None
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_payload_do_deckboxes():
    """A página nova é JSON + JavaScript: se o payload não fechar, a página
    aparece em branco sem um único erro no gerador."""
    con = _base_deckboxes()
    txt = _pagina_deckboxes(con).read_text(encoding="utf-8")
    bruto = re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                      txt, re.S).group(1)
    d = json.loads(bruto.replace("<\\/", "</"))
    assert d["editable"] is False, "o site publicado NÃO pode vir editável"
    caixas = {c["slot"]: c for c in d["caixas"]}
    assert set(caixas) == {"pauper", "modern"}, list(caixas)
    assert caixas["pauper"]["permanente"] is True
    assert caixas["pauper"]["dedicado"] is True, caixas["pauper"]
    # O caso Utrom Monitor, agora pelo lado da página nova.
    um = next(c for c in caixas["pauper"]["cartas"] if c["nm"] == "Utrom Monitor")
    assert um["est"] == "have" and um["lotes"][0]["local"] == "SPML", um
    # O Frogmite que o Pauper levou: a caixa do Pauper é DEDICADA e não empresta,
    # por isso ao Modern a carta é compra e vai à wantlist dele (2026-09-07, 19:00).
    fg = next(c for c in caixas["modern"]["cartas"] if c["nm"] == "Frogmite")
    assert fg["est"] == "miss" and fg["comprar"] == 4 and fg["noutra"] == {}, fg
    assert any(w["nm"] == "Frogmite" for w in caixas["modern"]["wantlist"])

    # E, com o mesmo material mas sem a regra `dedicado`, o terceiro estado
    # (âmbar, "em <caixa>") continua a desenhar-se: é o que vale no Duel
    # Commander e no SPML.
    rep = loadout.report(con, [dict(s, dedicado=False) for s in CFG["loadout"]])
    p = deckboxes.payload(con, rep)
    mo = next(c for c in p["caixas"] if c["slot"] == "modern")
    fg = next(c for c in mo["cartas"] if c["nm"] == "Frogmite")
    assert fg["est"] == "sub" and fg["noutra"] == {"Pauper (Luffy)": 4}, fg
    assert fg["comprar"] == 0
    assert not any(w["nm"] == "Frogmite" for w in mo["wantlist"])
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


def caso_aba_arrumar_separa_a_actualizacao_do_deck_montado():
    """A caixa DEDICADA e MONTADA não se arruma, actualiza-se (André, 2026-09-07,
    19:00: *"apenas mexer para actualizar"*). A carta que saiu da lista continua
    lá dentro, aparece como *"tirar"* na secção própria — e o botão que aplica o
    delta só existe no modo edição."""
    con = _base_deckboxes()
    # Ontem o Pauper foi arrumado com um Chromatic Star que a lista já não pede.
    cid = con.execute("SELECT cp.id FROM copies cp JOIN cards c "
                      "ON c.scryfall_id = cp.scryfall_id "
                      "WHERE c.name = 'Chromatic Star'").fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                "VALUES (?, 'pauper', 1)", (cid,))
    con.commit()
    slots = [dict(s, montado=True) if s["slot"] == "pauper" else dict(s)
             for s in CFG["loadout"]]
    rep = loadout.report(con, slots)
    d = deckboxes.payload(con, rep, editable=True)
    acts = d["arrumar"]["actualizacoes"]
    assert len(acts) == 1 and acts[0]["slot"] == "pauper", acts
    assert [m["nm"] for m in acts[0]["sai"]] == ["Chromatic Star"], acts[0]
    # A cópia presa não conta para a venda: das 5 que ele tem, 1 está dentro do
    # deck montado e as outras 4 são o playset — sobra 1, não 2.
    cs = [r for r in rep["venda"] if r["nm"] == "Chromatic Star"]
    assert sum(r["q"] for r in cs) == 1, cs

    if not shutil.which("node"):
        print("aba Arrumar: sem `node`, so o payload verificado")
        return
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    out.write_text(deckboxes.html_page(con, editable=True, rep=rep),
                   encoding="utf-8")
    html = _abas_desenhadas(out)["arrumar"]
    assert "Actualizar decks montados" in html, html[:400]
    assert 'data-act="actualizar"' in html, "falta o botao no modo edicao"
    publicado = _abas_desenhadas(_pagina_deckboxes(con))["arrumar"]
    assert 'data-act="actualizar"' not in publicado, "o publicado nao pode ter botao"
    print("aba Arrumar: a caixa montada actualiza-se, e o botao so no modo edicao")


def caso_aba_vender_nao_marca_nonfoil():
    """A tabela de venda punha ✨ em cópias `nonfoil`: o teste era
    `/foil|etched/.test(r.fin)` e a palavra *"nonfoil"* contém *"foil"*.
    Aparecia em Lotus Petal e Mirri's Guile, que são as duas nonfoil, e mandava
    listá-las como foil — um erro que só se apanha a olhar para a página.

    Lê o HTML que a aba DESENHOU: a linha da cópia nonfoil não pode ter ✨, e a
    da foil tem de a ter (senão o teste passava com a marca desligada)."""
    abas = _abas_desenhadas(_pagina_deckboxes())
    if abas is None:
        print("aba Vender: sem `node`, saltado")
        return
    html = abas["vender"]
    linhas = {re.sub("<[^>]+>", " ", tr): tr
              for tr in re.findall(r"<tr>.*?</tr>", html, re.S)}
    nf = [tr for txt, tr in linhas.items() if "Utrom Monitor" in txt]
    fo = [tr for txt, tr in linhas.items() if "Chromatic Star" in txt]
    assert nf and fo, ("faltam as duas linhas na tabela de venda", list(linhas))
    assert "✨" not in nf[0], ("uma cópia nonfoil não leva ✨", nf[0])
    assert "✨" in fo[0], ("uma cópia foil leva ✨", fo[0])
    print("aba Vender: ✨ so nas foil, nunca nas nonfoil")


def caso_aba_comprar_diz_para_que_caixa_e_em_que_material():
    """*"Para que caixa é esta compra, e em que língua/acabamento?"* — sem isso
    a lista mandava comprar 4 Thoughtcast sem dizer que a caixa de Modern as
    quer em EN foil, e comprar a versão errada é comprar duas vezes."""
    pagina = _pagina_deckboxes()
    d = json.loads(re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                             pagina.read_text(encoding="utf-8"), re.S)
                   .group(1).replace("<\\/", "</"))
    tc = next(m for m in d["compras"] if m["nm"] == "Thoughtcast")
    assert tc["req"] == "EN · foil", tc
    assert tc["mat"] == "EN foil", tc
    assert tc["para"] == [{"caixa": "Modern — UW Oswald", "slot": "modern",
                           "q": 4, "cost": tc["cost"], "unit": tc["unit"],
                           "req": "EN · foil", "mat": "EN foil"}], tc["para"]

    abas = _abas_desenhadas(pagina)
    if abas is None:
        print("aba Comprar: sem `node`, saltado")
        return
    html = abas["comprar"]
    assert "para: Modern — UW Oswald 4×" in html, html[:800]
    assert "EN · foil" in html, "o material de cada compra tem de estar à vista"
    assert 'id="compra-caixa"' in html, "falta o selector de caixa"
    # E o filtro por caixa só mostra (e só copia) as compras dessa caixa.
    print("aba Comprar: para que caixa, em que material, e com selector")

    # A lista COPIADA leva o material em cada linha: sem isso o texto que ele
    # cola no Cardmarket não distingue a PT do Premodern da EN foil do Modern.
    if abas:
        assert "4 Thoughtcast [EN foil]" in abas["comprar"], "falta o material na linha"
        print("a lista copiada leva o material em cada linha")


def _pagina_partilhada():
    """Duas caixas do MESMO material a pedir a mesma carta que ele não tem."""
    con = base()
    deck(con, "UW Oswald", "modern", [("Thoughtcast", 4)])
    deck(con, "UR Murktide", "modern", [("Thoughtcast", 4)])
    slots = [{"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
              "fonte": "deck", "ref": "UW Oswald", "balde": "SPML", "prioridade": 1},
             {"slot": "modern2", "nome": "Modern — UR Murktide", "formato": "modern",
              "fonte": "deck", "ref": "UR Murktide", "balde": "SPML", "prioridade": 2}]
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out, rep=loadout.report(con, slots))
    return out


def caso_aba_comprar_nao_soma_a_mesma_compra_por_caixa():
    """A regra do André — *"não ter que comprar múltiplos para todos"* — aplicada
    às COMPRAS e não só às cópias que ele tem. Duas caixas de Modern pedem 4
    Thoughtcast cada: a lista pede 4, não 8, e diz que a compra é partilhada."""
    pagina = _pagina_partilhada()
    d = json.loads(re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                             pagina.read_text(encoding="utf-8"), re.S)
                   .group(1).replace("<\\/", "</"))
    tc = next(m for m in d["compras"] if m["nm"] == "Thoughtcast")
    assert tc["q"] == 4, ("comprar o máximo de uma caixa, não a soma", tc)
    assert tc["partilhada"] == 2, tc
    assert [(p["caixa"], p["q"], bool(p.get("serve"))) for p in tc["para"]] == [
        ("Modern — UW Oswald", 4, False), ("Modern — UR Murktide", 4, True)], tc["para"]
    assert d["resumo"]["comprar"] == 4 and d["resumo"]["poupado"] == 4, d["resumo"]
    # A posse de cada caixa NÃO mexe: a falta continua lá até a compra chegar.
    assert all(c["pct"] == 0 and c["faltam"] == 4 for c in d["caixas"]), d["caixas"]

    abas = _abas_desenhadas(pagina)
    if abas is None:
        print("aba Comprar partilhada: sem `node`, saltado")
        return
    assert "partilhada por 2 caixas" in abas["comprar"], abas["comprar"][:900]
    assert "serve também: Modern — UR Murktide" in abas["comprar"]
    assert "4 Thoughtcast [EN foil]" in abas["comprar"]
    # E a caixa servida não tem a carta na wantlist dela — comprá-la ali era
    # comprá-la duas vezes, que é o defeito que a partilha veio corrigir.
    assert "depois de Modern — UW Oswald comprar" in abas["modern2"], abas["modern2"][:900]
    print("aba Comprar: uma compra partilhada por duas caixas, não duas compras")


def _pagina_premodern():
    """Duas caixas de Premodern, uma quase fechada e outra longe, e uma carta
    pedida acima do playset (5 num deck, tecto do grupo 4)."""
    con = base()
    deck(con, "Perto", "premodern", [("Swords to Plowshares", 2)])
    deck(con, "Longe", "premodern", [("Swords to Plowshares", 5), ("Frogmite", 4)])
    add(con, "Swords to Plowshares", 2, lang="pt", sub="Colecção")
    # O `prioridade` do config está ao contrário da % de propósito: quem tem de
    # mandar é a percentagem.
    slots = [{"slot": "pm-longe", "nome": "PM Longe", "formato": "premodern",
              "fonte": "deck", "ref": "Longe", "balde": "Colecção", "prioridade": 1},
             {"slot": "pm-perto", "nome": "PM Perto", "formato": "premodern",
              "fonte": "deck", "ref": "Perto", "balde": "Colecção", "prioridade": 2}]
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out, rep=loadout.report(con, slots))
    return out


def caso_pagina_diz_a_ordem_automatica_e_o_limite_de_playset():
    """As duas decisões de 2026-09-08 têm de estar NA PÁGINA.

      * a ordem do grupo é automática (*"a prioridade vem por ordem de % completo"*)
        — sem o dizer, o *"#1 na alocação"* parecia um número escolhido por ele;
      * o que o tecto de playset corta (*"limite de playset: falta 1 que não se
        compra"*) — se saísse só da conta das compras, a caixa ficava à espera de
        uma carta que ninguém vai comprar.
    """
    pagina = _pagina_premodern()
    d = json.loads(re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                             pagina.read_text(encoding="utf-8"), re.S)
                   .group(1).replace("<\\/", "</"))
    caixas = {c["slot"]: c for c in d["caixas"]}
    perto, longe = caixas["pm-perto"], caixas["pm-longe"]
    assert perto["prioridade"] == 1 and perto["posicao_grupo"] == 1, perto
    assert perto["prioridade_por"] == "pct" and perto["pct_coleccao"] == 100, perto
    assert longe["posicao_grupo"] == 2, longe
    # O tecto: pede 5, tem 2, compra 2 (=4 no total) e uma fica por comprar.
    assert longe["playset"] == 4 and longe["bloqueado"] == 1, longe
    assert longe["playset_faltas"] == [{"nm": "Swords to Plowshares",
                                        "board": "main", "q": 1}], longe
    stp = next(c for c in longe["cartas"] if c["nm"] == "Swords to Plowshares")
    assert stp["comprar"] == 2 and stp["bloq"] == 1, stp
    assert sum(w["q"] for w in longe["wantlist"]
               if w["nm"] == "Swords to Plowshares") == 2, longe["wantlist"]

    abas = _abas_desenhadas(pagina)
    if abas is None:
        print("ordem automatica e limite de playset: sem `node`, saltado")
        return
    assert "#1 por % completo" in abas["pm-perto"], abas["pm-perto"][:900]
    assert "#2 por % completo" in abas["pm-longe"], abas["pm-longe"][:900]
    assert "limite de playset" in abas["pm-longe"], abas["pm-longe"][:1500]
    assert "falta 1</b> que não se compra" in abas["pm-longe"], abas["pm-longe"][:1500]
    # E as caixas que não estão num grupo automático não ganham o crachá.
    outra = _abas_desenhadas(_pagina_deckboxes())
    assert "por % completo" not in outra["modern"], outra["modern"][:900]
    print("a pagina diz a ordem automatica e o que o tecto de playset corta")


def run():
    for fn in (caso_utrom_monitor, caso_noutra_caixa_e_o_terceiro_estado,
               caso_coleccao_inteira_e_informacao_secundaria,
               caso_meusdecks_reencaminha, caso_top_n_do_config,
               caso_foil_report_ve_as_outras_caixas, caso_pagina_metagame_fecha,
               caso_payload_do_deckboxes,
               caso_javascript_do_deckboxes_desenha_todas_as_abas,
               caso_nome_de_arquetipo_e_legivel,
               caso_vou_montar_este_escolhe_e_desmarca,
               caso_aba_arrumar_separa_a_actualizacao_do_deck_montado,
               caso_aba_vender_nao_marca_nonfoil,
               caso_aba_comprar_diz_para_que_caixa_e_em_que_material,
               caso_aba_comprar_nao_soma_a_mesma_compra_por_caixa,
               caso_pagina_diz_a_ordem_automatica_e_o_limite_de_playset):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
