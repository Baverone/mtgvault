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


def run_scryfall_bulk():
    """O carregador grátis: preços tirados do bulk da Scryfall (campo prices.eur).

    É a fonte que a cloud usa sem credenciais — o daily.py liga-a antes do price
    guide oficial. Aqui confirma-se, sem rede, que só grava o que interessa.
    """
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "p.db", tmp / "cat.db") as con:
        seed_catalog(con, NAMES)
        collection.add_copy(con, "Black Lotus", set_code="tst", quantity=1)  # id-1
        bulk = tmp / "default_cards.jsonl"
        bulk.write_text(
            '{"id":"id-1","prices":{"eur":"100.00","eur_foil":"250.00"}}\n'
            '{"id":"id-4","prices":{"eur":"5.00","eur_foil":null}}\n',
            encoding="utf-8")
        n = prices.load_scryfall_prices(con, bulk)
        assert n == 2, n  # Black Lotus nonfoil+foil; Ragavan (id-4) fora do interesse
        got = {(r["scryfall_id"], r["finish"]): r["trend"] for r in
               con.execute("SELECT scryfall_id, finish, trend FROM price_latest")}
        assert got[("id-1", "nonfoil")] == 100.0, got
        assert got[("id-1", "foil")] == 250.0, got
        assert ("id-4", "nonfoil") not in got, "Ragavan não devia ter preço"
        print("Bulk da Scryfall: preços grátis só para as cartas de interesse")
    print("\nTUDO OK (scryfall bulk)")


# Trecho REAL do price guide público do Cardmarket (2026-09-18, `createdAt` e
# valores tal e qual; só o `idProduct` do 1.º foi posto a 1001 para bater com o
# `cardmarket_id` do Black Lotus do `seed_catalog`). É a forma que o
# `load_cardmarket_file` tem de continuar a ler.
PRICE_GUIDE_TRECHO = (
    '{"version":1,"createdAt":"2026-09-18T02:49:26+0200","priceGuides":['
    '{"idProduct":1001,"idCategory":1,"avg":0.09,"low":0.02,"trend":0.09,"avg1":0.02,'
    '"avg7":0.06,"avg30":0.09,"avg-foil":0.26,"low-foil":0.05,"trend-foil":0.36,'
    '"avg1-foil":0.35,"avg7-foil":0.33,"avg30-foil":0.34},'
    '{"idProduct":2,"idCategory":1,"avg":0.05,"low":0.02,"trend":0.05,"avg1":0.02,'
    '"avg7":0.03,"avg30":0.04,"avg-foil":null,"low-foil":null,"trend-foil":null,'
    '"avg1-foil":null,"avg7-foil":null,"avg30-foil":null}]}')


class _Resposta:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def run_priceguide_publico():
    """O price guide público é OPT-IN: sem `CARDMARKET_PRICEGUIDE_PUBLICO` o
    passo continua a saltar (ligá-lo muda os números — ver o docstring do
    `download_cardmarket_priceguide`); com ele, vai ao URL público e o ficheiro
    lê-se com low/trend/avg30 e as variantes foil."""
    import os
    pedidos = []

    def get_falso(url, headers=None, timeout=None):
        pedidos.append((url, dict(headers or {})))
        return _Resposta(PRICE_GUIDE_TRECHO.encode("utf-8"))

    tmp = Path(tempfile.mkdtemp())
    for k in ("CARDMARKET_PRICEGUIDE_PUBLICO", "CARDMARKET_COOKIE",
              "CARDMARKET_PRICEGUIDE_URL"):
        os.environ.pop(k, None)
    assert prices.download_cardmarket_priceguide(tmp / "pg.json", _get=get_falso) is None
    assert pedidos == [], "sem opt-in não se faz um único pedido"

    os.environ["CARDMARKET_PRICEGUIDE_PUBLICO"] = "1"
    p = prices.download_cardmarket_priceguide(tmp / "pg.json", _get=get_falso)
    assert p == tmp / "pg.json" and p.exists(), p
    assert pedidos and pedidos[0][0] == prices.CM_PRICEGUIDE_PUBLICO, pedidos
    assert "Cookie" not in pedidos[0][1], "o público não leva cookie"
    os.environ.pop("CARDMARKET_PRICEGUIDE_PUBLICO", None)

    with db.session(tmp / "p.db", tmp / "cat.db") as con:
        seed_catalog(con, NAMES)
        collection.add_copy(con, "Black Lotus", set_code="tst", quantity=1)  # id-1
        n = prices.load_cardmarket_file(con, p)
        assert n == 2, n                     # nonfoil + foil do Black Lotus
        got = {(r["scryfall_id"], r["finish"]): (r["low"], r["trend"], r["avg30"])
               for r in con.execute("SELECT scryfall_id, finish, low, trend, avg30 "
                                    "FROM price_latest WHERE source='cardmarket'")}
        assert got[("id-1", "nonfoil")] == (0.02, 0.09, 0.09), got
        assert got[("id-1", "foil")] == (0.05, 0.36, 0.34), got
        assert len(got) == 2, got            # o idProduct 2 não é de ninguém
    print("Price guide público: opt-in, sem cookie, e o ficheiro real lê-se com low/trend/avg30")
    print("\nTUDO OK (price guide publico)")


if __name__ == "__main__":
    run()
    run_scryfall_bulk()
    run_priceguide_publico()
