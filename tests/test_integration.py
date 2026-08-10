"""Teste end-to-end com catálogo e preços falsos — não toca na rede."""
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import analysis, collection, db, prices, sources, wantlist  # noqa: E402

BURN = {"Lightning Bolt": 4, "Monastery Swiftspear": 4, "Lava Spike": 4,
        "Boros Charm": 4, "Skewer the Critics": 4, "Eidolon of the Great Revel": 4,
        "Inspiring Vantage": 4, "Sacred Foundry": 4, "Mountain": 8, "Fury": 2}
TRON = {"Karn Liberated": 4, "Urza's Tower": 4, "Urza's Mine": 4, "Wurmcoil Engine": 2,
        "Urza's Power Plant": 4, "Ancient Stirrings": 4, "Expedition Map": 4,
        "Chromatic Star": 4, "Forest": 2, "Oblivion Stone": 3}


def seed_catalog(con, names):
    for i, n in enumerate(sorted(names)):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
               set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,'tst','Test Set',?,'en','rare','Instant',1,'R',?,
               '2020-01-01',?,0)""",
            (f"id-{i}", f"or-{i}", n, str(i), json.dumps(["nonfoil", "foil"]), 1000 + i),
        )
    con.commit()


def seed_prices(con, names, day=None, factor=1.0):
    day = day or date.today().isoformat()
    rows = [(f"id-{i}", "cardmarket", day, "nonfoil", 1.0 + i,
             round((2.0 + i) * factor, 2), 2.0 + i, None, "EUR")
            for i, n in enumerate(sorted(names))]
    prices.write_prices(con, rows)


def run():
    random.seed(7)
    names = sorted(set(BURN) | set(TRON))
    tmp = Path(tempfile.mkdtemp()) / "t.db"

    with db.session(tmp, tmp.with_name("cat.db")) as con:
        seed_catalog(con, names)

        # --- 1. decklists sintéticas: 20 burn + 15 tron, com variação -------
        today = date.today()
        for i in range(20):
            deck = dict(BURN)
            deck["Fury"] = 2 if i < 12 else 0          # flex
            if i < 4:
                deck["Smash to Smithereens"] = 1       # tech esporádica
            deck = {k: v for k, v in deck.items() if v}
            text = "\n".join(f"{q} {n}" for n, q in deck.items())
            sources.store_manual(con, text, "modern", "League", 
                                 (today - timedelta(days=i % 20)).isoformat(),
                                 f"burn{i}", key=f"b{i}")
        for i in range(15):
            deck = dict(TRON)
            deck["Wurmcoil Engine"] = 2 if i < 13 else 3
            text = "\n".join(f"{q} {n}" for n, q in deck.items())
            sources.store_manual(con, text, "modern", "League",
                                 (today - timedelta(days=i % 20)).isoformat(),
                                 f"tron{i}", key=f"t{i}")

        n_lists = con.execute("SELECT COUNT(*) c FROM decklists").fetchone()["c"]
        assert n_lists == 35, n_lists

        # --- 2. análise -----------------------------------------------------
        k = analysis.rebuild_archetypes(con, "modern")
        assert k == 2, f"esperava 2 arquétipos, obtive {k}"
        analysis.rebuild_roles(con, "modern")

        archs = con.execute(
            "SELECT a.id, a.label, COUNT(d.id) n FROM archetypes a "
            "JOIN decklists d ON d.archetype_id = a.id GROUP BY a.id ORDER BY n DESC"
        ).fetchall()
        print("\nArquétipos detetados:")
        for a in archs:
            print(f"  [{a['id']}] {a['label']}  ({a['n']} listas)")

        burn_id = archs[0]["id"]
        roles = {r["card_name"]: dict(r) for r in con.execute(
            "SELECT * FROM card_roles WHERE archetype_id = ? AND board='main'",
            (burn_id,))}
        assert roles["Lightning Bolt"]["role"] == "core"
        assert roles["Lightning Bolt"]["core_copies"] == 4
        assert roles["Fury"]["role"] == "flex", roles["Fury"]
        assert roles["Smash to Smithereens"]["role"] == "tech"
        print("\nNúcleo do arquétipo principal:")
        for n, r in sorted(roles.items(), key=lambda x: -x[1]["inclusion_rate"])[:6]:
            print(f"  {n:32} {r['role']:5} core={r['core_copies']} "
                  f"incl={r['inclusion_rate']:.0%} dist={r['dist']}")

        # --- 3. coleção: tenho parte do burn, e um Bolt só de colecionador ---
        collection.add_copy(con, "Lightning Bolt", set_code="tst", quantity=3)
        collection.add_copy(con, "Lightning Bolt", set_code="tst", quantity=1,
                            purpose="collector", sub_collection="Beta",
                            photo_path="C:/fotos/bolt_beta.jpg")
        collection.add_copy(con, "Monastery Swiftspear", set_code="tst", quantity=4)
        collection.add_copy(con, "Mountain", set_code="tst", quantity=8)

        owned = collection.owned_playable(con)
        assert owned["Lightning Bolt"] == 3, owned["Lightning Bolt"]  # o 4.º não conta

        # --- 4. deck meu e wantlist -----------------------------------------
        text = "\n".join(f"{q} {n}" for n, q in BURN.items() if n != "Fury")
        con.execute("INSERT INTO decks (name, format) VALUES ('Meu Burn','modern')")
        did = con.execute("SELECT id FROM decks").fetchone()["id"]
        parsed = sources.parse_text_decklist(text)
        con.executemany(
            "INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
            "VALUES (?,?,?,?)",
            [(did, n, q, "main") for n, q in parsed["main"]])
        con.commit()

        # O "antes" fica com margem (9 dias) para caber sempre na janela de
        # movers (days=7), que usa date('now') em UTC: se a data local já virou
        # mas a UTC ainda não, um "antes" a 7 dias exatos cairia fora por 1 dia.
        seed_prices(con, names, (today - timedelta(days=9)).isoformat(), 1.0)
        seed_prices(con, names, today.isoformat(), 1.25)

        st = wantlist.deck_status(con, did)
        miss = {m["card_name"]: m["missing"] for m in st["missing"]}
        assert miss["Lightning Bolt"] == 1, miss
        assert "Monastery Swiftspear" not in miss
        assert "Mountain" not in miss
        print(f"\nDeck 'Meu Burn': faltam {st['missing_cards']} cartas, "
              f"{st['missing_cost']:.2f} EUR")

        # --- 5. valor e movimentos ------------------------------------------
        vals = collection.collection_value(con)
        player = sum(v["total"] for v in vals if v["purpose"] == "player")
        coll = sum(v["total"] for v in vals if v["purpose"] == "collector")
        assert player > 0 and coll > 0
        print(f"Valor: jogar {player:.2f} EUR | colecionador {coll:.2f} EUR")

        mv = collection.movers(con, days=7)
        assert mv["up"], "devia detetar subidas"
        assert all(abs(r["pct"] - 25.0) < 0.5 for r in mv["up"]), mv["up"][:2]
        print(f"Movimentos: {len(mv['up'])} cartas, todas +25% (como esperado)")

        # --- 6. gap para o arquétipo ----------------------------------------
        gap = wantlist.archetype_gap(con, burn_id)
        gapd = {g["card_name"]: g["missing"] for g in gap}
        assert gapd.get("Lightning Bolt") == 1, gapd
        assert "Monastery Swiftspear" not in gapd
        print(f"Gap para o arquétipo: {len(gap)} cartas em falta")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
