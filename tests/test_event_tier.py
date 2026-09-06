"""`decklists.event_tier` — a coluna de que o metagame depende.

Andou a ser LIDA (meta_coverage._rank, buildable) sem nunca ser escrita: não
estava no schema.sql nem no db._migrate(), e nada a preenchia. Numa base nova as
páginas rebentavam; numa base antiga o top-10 vinha vazio e o passo diário dizia
"ok" na mesma. Este teste tranca as três pontas: a coluna existe, é escrita na
gravação, e o backfill apanha as listas antigas.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, sources  # noqa: E402

CARTAS = [("main", "Lightning Bolt", 4), ("main", "Mountain", 20)]


def run():
    tmp = Path(tempfile.mkdtemp()) / "d.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        # --- a coluna tem de existir numa base criada do zero --------------
        cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
        assert "event_tier" in cols, cols
        print("schema novo já traz event_tier")

        # --- classificação por nome de evento ------------------------------
        casos = [
            ("mtgo", "Modern Showcase Challenge 2026-09-01", "Showcase"),
            ("mtgo", "Modern Challenge 32 2026-09-01", "Challenge"),
            ("mtgo", "Modern Preliminary 2026-09-01", "Preliminary"),
            ("mtgo", "Modern League 2026-09-01", "League"),
            ("mtgo", "Modern Super Qualifier 2026-09-01", "Qualifier"),
            ("mtgo", "", "outro"),
            ("mtgtop8", "Magic Spotlight Series", "Presencial"),
        ]
        for src, nome, esperado in casos:
            got = sources.event_tier(src, nome)
            assert got == esperado, f"{nome!r} -> {got}, esperava {esperado}"
        # "Showcase Qualifier" é Showcase (o Showcase é testado primeiro)
        assert sources.event_tier("mtgo", "Pioneer Showcase Qualifier") == "Showcase"
        print(f"{len(casos) + 1} nomes de evento classificados como esperado")

        # --- a gravação escreve a coluna ----------------------------------
        did = sources.store_decklist(
            con, source="mtgo", source_key="k1", fmt="modern", cards=CARTAS,
            event_name="Modern Challenge 64 2026-09-01", event_date="2026-09-01",
            player="alguem")
        tier = con.execute("SELECT event_tier FROM decklists WHERE id = ?",
                           (did,)).fetchone()["event_tier"]
        assert tier == "Challenge", tier
        print("store_decklist grava o tier da lista nova")

        # --- backfill das listas que ficaram a NULL ------------------------
        con.execute(
            """INSERT INTO decklists (source, source_key, format, event_name,
                                      event_date, player)
               VALUES ('mtgo','antiga','modern','Modern Showcase Challenge',
                       '2026-08-30','outro')""")
        con.commit()
        assert sources.backfill_event_tiers(con) == 1
        assert sources.backfill_event_tiers(con) == 0, "não devia reescrever"
        tiers = {r["source_key"]: r["event_tier"] for r in con.execute(
            "SELECT source_key, event_tier FROM decklists")}
        assert tiers == {"k1": "Challenge", "antiga": "Showcase"}, tiers
        print("backfill classifica as listas antigas e não repete trabalho")

        # --- é isto que o metagame pergunta (meta_coverage._rank) ----------
        n = con.execute("SELECT COUNT(*) c FROM decklists "
                        "WHERE event_tier IN ('Challenge','Showcase')").fetchone()["c"]
        assert n == 2, n
        print("o filtro Challenge/Showcase do metagame já encontra listas")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
