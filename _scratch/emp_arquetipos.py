"""Os archetype_id das duas listas e o que ha dentro deles; e qual variante era
cada lista de referencia do Grinding Station. So leitura."""
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{(RAIZ / '_scratch' / 'vault.db').as_posix()}?mode=ro", uri=True)

MARCAS = ["Grinding Station", "Kethis, the Hidden Hand", "Loki, God of Mischief",
          "Emry, Lurker of the Loch", "Sewer-veillance Cam", "Malevolent Rumble", "Mox Opal"]


def tem(lid, c):
    r = con.execute("SELECT SUM(quantity) FROM decklist_cards WHERE decklist_id=? AND card_name=?", (lid, c)).fetchone()[0]
    return r or 0


for aid in (8088, 8215):
    a = con.execute("SELECT id, format, label FROM archetypes WHERE id=?", (aid,)).fetchone()
    ids = [r[0] for r in con.execute("SELECT id FROM decklists WHERE archetype_id=?", (aid,))]
    print(f"\narquetipo {aid}: {a} -> {len(ids)} listas")
    for c in MARCAS:
        print(f"   {c:28s} {sum(1 for i in ids if tem(i, c))}/{len(ids)}")

print("\nlistas de referencia do Grinding Station:")
for lid in (20645, 22659, 24182, 25579, 26635, 26604, 27439):
    r = con.execute("SELECT player, event_date, archetype_id FROM decklists WHERE id=?", (lid,)).fetchone()
    print(lid, r, {c.split(",")[0]: tem(lid, c) for c in MARCAS})

print("\nModern desde 2026-09-15 com Mox Opal + Grinding Station:")
rows = con.execute("""SELECT dl.id, dl.event_date, dl.player, dl.archetype_id, dl.event_tier FROM decklists dl
    WHERE dl.format='modern' AND dl.event_date >= '2026-09-15'
      AND EXISTS (SELECT 1 FROM decklist_cards c WHERE c.decklist_id=dl.id AND c.card_name='Grinding Station')
      AND EXISTS (SELECT 1 FROM decklist_cards c WHERE c.decklist_id=dl.id AND c.card_name='Mox Opal')
    ORDER BY dl.event_date""").fetchall()
for r in rows:
    print(r, {c.split(",")[0]: tem(r[0], c) for c in MARCAS[1:6]})
