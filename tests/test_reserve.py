"""Reservas por deck: o que "ainda falta" tem de contar o que já está reservado.

`reserve_for_deck` devolvia `still_missing` calculado sobre as cartas
reservadas NAQUELA passagem. Numa segunda corrida — o deck já tinha cartas
dedicadas — só se reserva o que falta, e o que sobrava era anunciado como em
falta mesmo já estando lá.

Também tranca a regra do CLAUDE.md: a coleção de colecionador nunca é reservada.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import collection, db  # noqa: E402

CARTAS = ["Lightning Bolt", "Force of Will"]


def seed_catalog(con, names):
    for i, n in enumerate(sorted(names)):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,'tst','Test Set',?,'en','rare','Instant',1,'R',?,
               '2020-01-01',?,0)""",
            (f"id-{i}", f"or-{i}", n, str(i), json.dumps(["nonfoil"]), 1000 + i))
    con.commit()


def run():
    tmp = Path(tempfile.mkdtemp()) / "d.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        seed_catalog(con, CARTAS)

        con.execute("INSERT INTO decks (name, format) VALUES ('Burn','modern')")
        did = con.execute("SELECT id FROM decks").fetchone()["id"]
        con.executemany(
            "INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
            "VALUES (?,?,?,'main')",
            [(did, "Lightning Bolt", 4), (did, "Force of Will", 2)])

        # Tem 2 Bolt jogáveis + 1 de colecionador; nenhum Force of Will.
        collection.add_copy(con, "Lightning Bolt", set_code="tst", quantity=2)
        collection.add_copy(con, "Lightning Bolt", set_code="tst", quantity=1,
                            purpose="collector")
        con.commit()

        r1 = collection.reserve_for_deck(con, did)
        assert r1["reserved"] == {"Lightning Bolt": 2}, r1["reserved"]
        assert r1["still_missing"] == {"Lightning Bolt": 2, "Force of Will": 2}, \
            r1["still_missing"]
        print("1ª reserva: reserva o que há e diz certo o que falta")

        # a de colecionador não pode ter sido tocada (regra do CLAUDE.md)
        col = con.execute("SELECT reserved_deck_id FROM copies "
                          "WHERE purpose = 'collector'").fetchone()
        assert col["reserved_deck_id"] is None, "reservou a coleção de colecionador"
        print("a coleção de colecionador continua fora das reservas")

        # chega mais 1 Bolt; segunda passagem só reserva o novo
        collection.add_copy(con, "Lightning Bolt", set_code="tst", quantity=1)
        r2 = collection.reserve_for_deck(con, did)
        assert r2["reserved"] == {"Lightning Bolt": 1}, r2["reserved"]
        assert r2["still_missing"] == {"Lightning Bolt": 1, "Force of Will": 2}, \
            r2["still_missing"]
        print("2ª reserva: o que falta conta as cartas já dedicadas ao deck")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
