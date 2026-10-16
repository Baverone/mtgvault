"""Mede o caso Grinding Station 26604 -> 27439 na copia da base (so leitura)."""
import json
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{(RAIZ / '_scratch' / 'vault.db').as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
out = sys.stdout


def p(*a):
    print(*a, file=out)


cols = [r[1] for r in con.execute("PRAGMA table_info(decklists)")]
p("decklists cols:", cols)
for lid in (26604, 27439):
    r = con.execute("SELECT * FROM decklists WHERE id=?", (lid,)).fetchone()
    p(lid, dict(r) if r else None)
    if r:
        gs = con.execute("SELECT board, quantity FROM decklist_cards WHERE decklist_id=? AND card_name='Grinding Station'", (lid,)).fetchall()
        ke = con.execute("SELECT board, quantity FROM decklist_cards WHERE decklist_id=? AND card_name IN ('Kethis, the Hidden Hand','Loki, God of Mischief','Emry, Lurker of the Loch','Sewer-veillance Cam')", (lid,)).fetchall()
        p("  GS:", [tuple(x) for x in gs], " outros:", [tuple(x) for x in ke])
        p("  main/side:", con.execute("SELECT board, SUM(quantity) FROM decklist_cards WHERE decklist_id=? GROUP BY board", (lid,)).fetchall() and [tuple(x) for x in con.execute("SELECT board, SUM(quantity) FROM decklist_cards WHERE decklist_id=? GROUP BY board", (lid,))])

p("\n--- deck_lista_trocas ---")
tc = [r[1] for r in con.execute("PRAGMA table_info(deck_lista_trocas)")]
p(tc)
for t in con.execute("SELECT * FROM deck_lista_trocas ORDER BY id"):
    a = {}
    for b, n, q in json.loads(t["de_cartas"] or "[]"):
        a[(b, n)] = a.get((b, n), 0) + q
    bb = {}
    for b, n, q in json.loads(t["para_cartas"] or "[]"):
        bb[(b, n)] = bb.get((b, n), 0) + q
    d = sum(abs(bb.get(k, 0) - a.get(k, 0)) for k in set(a) | set(bb))
    p(t["id"], t["corrida"], t["deck"], t["motivo"], t["de_decklist_id"], "->", t["para_decklist_id"], "delta", d,
      "GS", sum(q for (b, n), q in a.items() if n == "Grinding Station"), "->", sum(q for (b, n), q in bb.items() if n == "Grinding Station"))

p("\n--- decks Grinding Station ---")
for r in con.execute("SELECT id, name, notes FROM decks WHERE name LIKE '%Grinding%'"):
    p(dict(r))
    p("  GS na deck_cards:", [tuple(x) for x in con.execute("SELECT board, quantity FROM deck_cards WHERE deck_id=? AND card_name='Grinding Station'", (r["id"],))])

p("\n--- job_runs meus-decks ---")
jc = [r[1] for r in con.execute("PRAGMA table_info(job_runs)")]
p(jc)
for r in con.execute("SELECT * FROM job_runs WHERE step LIKE 'meus%' ORDER BY rowid DESC LIMIT 60"):
    p(dict(r))
