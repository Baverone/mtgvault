"""Que listas contam para o metagame (regra do André, 2026-09-07).

À letra: "no mtgvault não quero listas de league; quero challenge, showcase, e
presenciais com 64 ou mais jogadores — menos Duel Commander, que pode ter menos
jogadores e pode ser ligas."

A regra vive num sítio só (`sources.lista_conta` / `counting_sql`, configurada em
colecao_config.json -> metagame_fontes) precisamente para não voltar a acontecer
o do `event_tier`: cada página a filtrar à sua maneira e a discordar em silêncio.
Este teste tranca as quatro pontas que custaram a acertar — formato normal, Duel
Commander, presencial sem contagem de jogadores, e os eventos do MTGO que o
mtgtop8 re-hospeda. Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# O config tem de estar em vigor ANTES de o sources ser importado a valer — é
# ele que decide a regra. Escreve-se um igual ao que vai no repositório, para o
# teste não passar a depender de o André não lhe mexer.
CFG = {
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "duel-commander": {"min_jogadores_presencial": 0, "ligas": True},
    }
}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")

from mtgvault import analysis, db, sources  # noqa: E402

BOLT = [("main", "Lightning Bolt", 4), ("main", "Mountain", 20)]


def _linha(tier, players=None, source="mtgo"):
    return {"event_tier": tier, "event_players": players, "source": source}


def _conta_por_sql(con, fmt, did):
    """A mesma pergunta, mas feita à base de dados — o SQL e o Python têm de
    responder o mesmo, senão as páginas divergem da análise."""
    sql, params = sources.counting_sql(fmt, "d")
    return bool(con.execute(f"SELECT 1 FROM decklists d WHERE d.id = ? AND {sql}",
                            (did, *params)).fetchone())


def caso_formato_normal():
    conta = lambda **kw: sources.lista_conta(_linha(**kw), "modern")  # noqa: E731
    assert conta(tier="Challenge")
    assert conta(tier="Showcase")
    assert conta(tier="Presencial", players=131)
    assert conta(tier="Presencial", players=64), "64 é o limite, e conta"
    assert not conta(tier="Presencial", players=63)
    assert not conta(tier="League"), "as ligas ficam de fora"
    assert not conta(tier="Preliminary")
    assert not conta(tier="Qualifier")
    # Um presencial SEM contagem não conta — não se assume o mínimo.
    assert not conta(tier="Presencial", players=None)
    print("modern: challenge/showcase/presencial 64+ contam; liga e sem-contagem não")


def caso_duel_commander():
    conta = lambda **kw: sources.lista_conta(_linha(**kw), "duel-commander")  # noqa: E731
    assert conta(tier="League"), "no Duel Commander as ligas contam"
    assert conta(tier="Presencial", players=9), "e os presenciais pequenos também"
    assert conta(tier="Presencial", players=None), "sem mínimo, sem contagem serve"
    assert not conta(tier="Preliminary"), "a exceção é só às ligas"
    print("duel-commander: ligas e presenciais pequenos contam")


def caso_rehost_mtgo():
    # O mtgtop8 re-hospeda o MTGO. Classificar pela FONTE punha-os em Presencial
    # e metia ligas online no meio dos torneios de papel.
    assert sources.event_tier("mtgtop8", "Premodern event - MTGO League") == "League"
    assert sources.event_tier("mtgtop8", "Modern event - MTGO Challenge 32") == "Challenge"
    assert sources.event_tier("mtgtop8", "Standard event - MTGO Showcase Challenge") == "Showcase"
    # …mas um torneio de papel com "Qualifier" no nome continua a ser presencial:
    # quem decide é o nº de jogadores, não a palavra.
    papel = "Standard event - BIG MAGIC Open - Champions Cup Premium Qualifier"
    assert sources.event_tier("mtgtop8", papel) == "Presencial"
    assert sources.lista_conta(_linha("Presencial", 131, "mtgtop8"), "standard")
    print("re-hosts do MTGO reclassificados; presencial com 'Qualifier' no nome fica presencial")


def caso_excecao_por_formato():
    """A porta que fica aberta para o André: uma linha no config e o Premodern
    (que sem exceção fica sem listas nenhumas) volta a ter metagame."""
    assert not sources.lista_conta(_linha("League"), "premodern")
    cfg = json.loads(json.dumps(CFG))
    cfg["metagame_fontes"]["premodern"] = {"min_jogadores_presencial": 0, "ligas": True}
    p = _TMP / "cfg2.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    os.environ["MTGVAULT_CONFIG"] = str(p)
    try:
        assert sources.lista_conta(_linha("League"), "premodern")
        assert sources.lista_conta(_linha("Presencial", 10), "premodern")
        assert not sources.lista_conta(_linha("League"), "modern"), "só o premodern muda"
    finally:
        os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
    print("exceção por formato no config liga o Premodern de volta")


def caso_base_de_dados():
    tmp = Path(tempfile.mkdtemp()) / "d.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        # --- ligas nem se guardam (menos no Duel Commander) -----------------
        assert sources.store_decklist(
            con, source="mtgo", source_key="l1", fmt="modern", cards=BOLT,
            event_name="Modern League 2026-09-01", event_date="2026-09-01",
            player="a") is None, "liga de modern não se guarda"
        dc = sources.store_decklist(
            con, source="mtgo", source_key="l2", fmt="duel-commander",
            cards=[("main", "Sol Ring", 1)], event_name="Duel Commander League",
            event_date="2026-09-01", player="b")
        assert dc is not None, "liga de duel-commander guarda-se"

        ch = sources.store_decklist(
            con, source="mtgo", source_key="c1", fmt="modern", cards=BOLT,
            event_name="Modern Challenge 64", event_date="2026-09-01", player="c")
        pres_s = sources.store_decklist(
            con, source="mtgtop8", source_key="p1", fmt="modern", cards=BOLT,
            event_name="Modern event - Torneio da Terra", event_date="2026-09-01",
            player="d")
        pres_n = sources.store_decklist(
            con, source="mtgtop8", source_key="p2", fmt="modern", cards=BOLT,
            event_name="Modern event - Outro Torneio", event_date="2026-09-02",
            player="e", event_players=200)
        assert _conta_por_sql(con, "modern", ch)
        assert not _conta_por_sql(con, "modern", pres_s), "presencial sem contagem"
        assert _conta_por_sql(con, "modern", pres_n)
        assert _conta_por_sql(con, "duel-commander", dc)
        print("store_decklist deixa as ligas fora e o counting_sql concorda com o Python")

        # --- backfill idempotente reclassifica um re-host antigo ------------
        con.execute("""INSERT INTO decklists (source, source_key, format, event_name,
                                              event_date, player, event_tier)
                       VALUES ('mtgtop8','velha','premodern',
                               'Premodern event - MTGO League','2026-09-01','f','Presencial')""")
        con.commit()
        assert sources.backfill_event_tiers(con) == 1
        assert sources.backfill_event_tiers(con) == 0, "idempotente"
        t = con.execute("SELECT event_tier t FROM decklists WHERE source_key='velha'").fetchone()["t"]
        assert t == "League", t
        print("backfill reclassifica os re-hosts que estavam a Presencial")

        # --- podar-ligas apaga só as que não contam -------------------------
        assert analysis.prune_leagues(con) == 1, "a de premodern sai, a de DC fica"
        restantes = {r["source_key"] for r in con.execute("SELECT source_key FROM decklists")}
        assert "velha" not in restantes and "l2" in restantes, restantes
        assert analysis.prune_leagues(con) == 0
        print("prune_leagues apaga a liga de premodern e poupa a de duel-commander")


def caso_analise_so_ve_o_que_conta():
    """O core é calculado sobre as listas que contam — uma liga não pode fazer
    parte do consenso de um arquétipo."""
    tmp = Path(tempfile.mkdtemp()) / "a.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        for i in range(6):
            sources.store_decklist(
                con, source="mtgo", source_key=f"ch{i}", fmt="modern",
                cards=[("main", "Lightning Bolt", 4), ("main", "Lava Spike", 4),
                       ("main", "Mountain", 20)],
                event_name="Modern Challenge 64", event_date="2026-09-01",
                player=f"j{i}")
        # Uma lista de liga metida à mão (a recolha já não a guardaria) com um
        # deck completamente diferente: se contasse, aparecia um 2.º arquétipo.
        con.execute("""INSERT INTO decklists (source, source_key, format, event_name,
                                              event_date, player, event_tier)
                       VALUES ('mtgo','liga','modern','Modern League','2026-09-01','z','League')""")
        did = con.execute("SELECT id FROM decklists WHERE source_key='liga'").fetchone()["id"]
        con.executemany("INSERT INTO decklist_cards (decklist_id, card_name, quantity, board) "
                        "VALUES (?,?,?,'main')",
                        [(did, "Karn Liberated", 4), (did, "Urza's Tower", 4),
                         (did, "Expedition Map", 4), (did, "Forest", 20)])
        con.commit()

        assert analysis.rebuild_archetypes(con, "modern") == 1, "a liga não faz arquétipo"
        analysis.rebuild_roles(con, "modern")
        cartas = {r["card_name"] for r in con.execute("SELECT card_name FROM card_roles")}
        assert "Lightning Bolt" in cartas
        assert "Karn Liberated" not in cartas, "carta só de liga não entra no core"
        print("rebuild_archetypes/rebuild_roles ignoram as listas de liga")


def run():
    caso_formato_normal()
    caso_duel_commander()
    caso_rehost_mtgo()
    caso_excecao_por_formato()
    caso_base_de_dados()
    caso_analise_so_ve_o_que_conta()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
