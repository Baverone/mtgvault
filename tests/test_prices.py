"""Testes do armazenamento de preços: só mudanças, e só cartas de interesse."""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import collection, db, prices  # noqa: E402
from test_integration import seed_catalog  # noqa: E402

NAMES = ["Arid Mesa", "Black Lotus", "Lightning Bolt", "Mountain", "Ragavan"]


def rows_for(day, trend_by_id):
    return [(sid, "cardmarket", day, "nonfoil", None, t, None, None, "EUR")
            for sid, t in trend_by_id.items()]


def run():
    tmp = Path(tempfile.mkdtemp()) / "p.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        seed_catalog(con, NAMES)
        d0 = date.today() - timedelta(days=10)
        d1 = date.today() - timedelta(days=5)
        d2 = date.today()

        # --- só grava mudanças -------------------------------------------
        base = {"id-0": 5.0, "id-1": 100.0, "id-2": 1.0}
        n = prices.write_prices(con, rows_for(d0.isoformat(), base))
        assert n == 3, n

        n = prices.write_prices(con, rows_for(d1.isoformat(), base))
        assert n == 0, "preços iguais não deviam gerar linhas novas"

        hist = con.execute("SELECT COUNT(*) c FROM price_history").fetchone()["c"]
        assert hist == 3, hist

        # o price_latest tem de ficar com a data mais recente na mesma
        row = con.execute(
            "SELECT date FROM price_latest WHERE scryfall_id='id-0'").fetchone()
        assert row["date"] == d1.isoformat(), row["date"]
        print(f"Sem mudanças: histórico continua com {hist} linhas, latest atualizado")

        # --- uma mudança gera uma linha ----------------------------------
        mudou = dict(base, **{"id-1": 125.0})
        n = prices.write_prices(con, rows_for(d2.isoformat(), mudou))
        assert n == 1, n
        hist = con.execute("SELECT COUNT(*) c FROM price_history").fetchone()["c"]
        assert hist == 4, hist
        print("Uma subida -> uma linha nova (não três)")

        # --- movers funciona com histórico esparso ------------------------
        collection.add_copy(con, "Black Lotus", set_code="tst", quantity=1)
        collection.add_copy(con, "Arid Mesa", set_code="tst", quantity=4)
        mv = collection.movers(con, days=7)
        up = {r["name"]: r["pct"] for r in mv["up"]}
        assert up.get("Black Lotus") == 25.0, up
        assert up.get("Arid Mesa") == 0.0, up
        print(f"Movers com histórico esparso: Black Lotus {up['Black Lotus']}%")

        # --- filtro de interesse -----------------------------------------
        interesse = prices.cards_of_interest(con)
        assert "id-1" in interesse          # Black Lotus: tenho-a
        assert "id-0" in interesse          # Arid Mesa: tenho-a
        assert "id-4" not in interesse      # Ragavan: não tenho nem preciso

        con.execute("INSERT INTO decks (name, format) VALUES ('X','modern')")
        did = con.execute("SELECT id FROM decks").fetchone()["id"]
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,'Ragavan',4,'main')", (did,))
        con.commit()
        interesse = prices.cards_of_interest(con)
        assert "id-4" in interesse, "carta de um deck meu tem de entrar"
        print(f"Interesse: {len(interesse)} cartas de {len(NAMES)} no catálogo")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
