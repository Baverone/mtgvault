"""Testes de watchlist, listas padrão e cobertura — sem rede."""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import analysis, collection, db, moxfield, sources, stock, watchlist  # noqa: E402
from test_integration import seed_catalog  # noqa: E402

# Deck de 60 cartas a sério (58 fixas + 2 Fury), para a lista padrão poder encher.
BURN = {
    "Lightning Bolt": 4, "Monastery Swiftspear": 4, "Lava Spike": 4,
    "Boros Charm": 4, "Skewer the Critics": 4, "Eidolon of the Great Revel": 4,
    "Goblin Guide": 4, "Rift Bolt": 4, "Light Up the Stage": 4,
    "Inspiring Vantage": 4, "Sacred Foundry": 4, "Sunbaked Canyon": 4,
    "Arid Mesa": 2, "Mountain": 8, "Fury": 2,
}
assert sum(BURN.values()) == 60


def build(con):
    seed_catalog(con, sorted(set(BURN) | {"Smash to Smithereens", "Fury"}))
    today = date.today()
    for i in range(20):
        deck = dict(BURN)
        deck["Fury"] = 2 if i < 12 else 0
        if i < 4:
            deck["Smash to Smithereens"] = 1
        deck = {k: v for k, v in deck.items() if v}
        text = "\n".join(f"{q} {n}" for n, q in deck.items())
        text += "\nSideboard\n3 Smash to Smithereens"
        sources.store_manual(con, text, "modern", "League",
                             (today - timedelta(days=i % 15)).isoformat(),
                             f"AndreP" if i == 0 else f"p{i}", key=f"b{i}")
    analysis.rebuild_archetypes(con, "modern")
    analysis.rebuild_roles(con, "modern")


def run():
    tmp = Path(tempfile.mkdtemp()) / "w.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        build(con)
        aid = con.execute("SELECT id FROM archetypes LIMIT 1").fetchone()["id"]

        # --- lista padrão -----------------------------------------------
        sl = stock.stock_list(con, aid)
        main = {c["card_name"]: c["quantity"] for c in sl["main"]}
        assert sl["main_count"] == 60, sl["main_count"]
        assert main["Lightning Bolt"] == 4, main
        # Fury está em 60% das listas com 2 cópias -> entra na lista padrão
        assert main.get("Fury") == 2, main
        # Smash está em 20% -> não entra no main
        assert "Smash to Smithereens" not in main, main
        assert sl["side"], "sideboard devia ter cartas"
        print(f"Lista padrão: {sl['main_count']} main, {sl['side_count']} side")

        # --- cobertura ---------------------------------------------------
        collection.add_copy(con, "Lightning Bolt", set_code="tst", quantity=4)
        collection.add_copy(con, "Mountain", set_code="tst", quantity=8)
        collection.add_copy(con, "Boros Charm", set_code="tst", quantity=2)
        collection.add_copy(con, "Lava Spike", set_code="tst", quantity=4,
                            purpose="collector")   # colecionador: não conta

        cov = stock.coverage_of_archetype(con, aid)
        miss = {m["card_name"]: m["missing"] for m in cov["missing"]}
        assert miss["Boros Charm"] == 2, miss
        assert miss["Lava Spike"] == 4, "cartas de colecionador não podem contar"
        assert "Lightning Bolt" not in miss
        assert 0 < cov["pct"] < 100
        print(f"Cobertura: {cov['cards_have']}/{cov['cards_needed']} = {cov['pct']}%")

        # --- relatório do formato ---------------------------------------
        rep = stock.format_report(con, "modern")
        assert rep and rep[0]["pct"] == cov["pct"]
        print(f"Relatório: {len(rep)} arquétipos, o melhor a {rep[0]['pct']}%")

        # --- vigiar jogador MTGO ----------------------------------------
        wid = watchlist.add(con, "mtgo_player", "AndreP", "Burn do AndreP", "modern")
        res = watchlist.check_mtgo_player(con, wid)
        assert res["found"] and res["changed"]
        assert watchlist.check_mtgo_player(con, wid)["changed"] is False
        print(f"Vigiado MTGO: {len(res['cards'])} entradas capturadas")

        # --- diff entre versões -----------------------------------------
        nova = [(b, n, q) for b, n, q in res["cards"] if n != "Fury"]
        nova.append(("main", "Fury", 4))
        watchlist._save_snapshot(con, wid, nova, "teste")
        d = watchlist.diff(con, wid)
        ch = {c["card_name"]: c["delta"] for c in d["changes"]}
        assert ch["Fury"] == 2, ch
        print(f"Diff detetou {len(d['changes'])} alterações")

        # --- cobertura de um vigiado ------------------------------------
        cov2 = stock.coverage(con, watchlist.latest_cards(con, wid))
        assert cov2["cards_needed"] > 0
        print(f"Cobertura do vigiado: {cov2['pct']}%")

        # --- parsing do payload Moxfield (sem rede) ---------------------
        payload = {
            "name": "Meu Burn", "lastUpdatedAtUtc": "2026-08-01T10:00:00Z",
            "format": "modern",
            "boards": {
                "mainboard": {"cards": {
                    "a": {"quantity": 4, "card": {"name": "Lightning Bolt"}},
                    "b": {"quantity": 8, "card": {"name": "Mountain"}}}},
                "sideboard": {"cards": {
                    "c": {"quantity": 3, "card": {"name": "Smash to Smithereens"}}}},
                "maybeboard": {"cards": {
                    "d": {"quantity": 1, "card": {"name": "Karn Liberated"}}}},
            },
        }
        deck = moxfield.parse_deck_payload(payload, "abc123")
        assert ("main", "Lightning Bolt", 4) in deck["cards"]
        assert ("side", "Smash to Smithereens", 3) in deck["cards"]
        assert all(n != "Karn Liberated" for _, n, _ in deck["cards"]), "maybeboard fora"
        assert moxfield.deck_id("https://moxfield.com/decks/abc123") == "abc123"
        print("Parser Moxfield ok (maybeboard ignorado)")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
