"""`movers` não pode pôr cartas que subiram na lista "A DESCER".

As duas listas eram as duas PONTAS da mesma ordenação (`rows[:limit]` e
`rows[-limit:]`). Com menos cartas do que o limite (25) as pontas sobrepõem-se:
uma coleção com três cartas, todas a subir, aparecia inteira em "A DESCER" —
com o pct positivo à frente.
"""
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import collection, db, prices  # noqa: E402

CARTAS = ["Black Lotus", "Underground Sea", "Bazaar of Baghdad"]


def seed_catalog(con, names):
    for i, n in enumerate(sorted(names)):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,'tst','Test Set',?,'en','rare','Land',0,'',?,
               '1993-08-05',?,0)""",
            (f"id-{i}", f"or-{i}", n, str(i), json.dumps(["nonfoil"]), 1000 + i))
    con.commit()


def preco(con, sid, dia, valor):
    prices.write_prices(con, [(sid, "cardmarket", dia, "nonfoil", valor, valor,
                               valor, None, "EUR")])


def run():
    tmp = Path(tempfile.mkdtemp()) / "d.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        seed_catalog(con, CARTAS)
        for n in CARTAS:
            collection.add_copy(con, n, set_code="tst", quantity=1)

        antes = (date.today() - timedelta(days=9)).isoformat()
        hoje = date.today().isoformat()
        # id-0 Bazaar sobe, id-1 Black Lotus sobe, id-2 Underground Sea desce
        for sid, v0, v1 in (("id-0", 100.0, 120.0), ("id-1", 200.0, 260.0),
                            ("id-2", 300.0, 240.0)):
            preco(con, sid, antes, v0)
            preco(con, sid, hoje, v1)

        mv = collection.movers(con, days=7)
        up = {r["name"] for r in mv["up"]}
        down = {r["name"] for r in mv["down"]}
        assert up == {"Bazaar of Baghdad", "Black Lotus"}, up
        assert down == {"Underground Sea"}, down
        assert not (up & down), f"a mesma carta nas duas listas: {up & down}"
        assert all((r["pct"] or 0) < 0 for r in mv["down"]), mv["down"]
        print(f"subiram {len(up)}, desceram {len(down)}, sem sobreposição")

        # a que mais desceu vem primeiro
        preco(con, "id-0", hoje, 50.0)
        mv = collection.movers(con, days=7)
        assert [r["name"] for r in mv["down"]] == ["Bazaar of Baghdad",
                                                   "Underground Sea"], mv["down"]
        print("a lista de descidas vem da maior queda para a menor")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
