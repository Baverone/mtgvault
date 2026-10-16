"""Imprime as decklists 26604 e 27439 como listas Python [(board, carta, qty)],
para fixture do teste. So leitura."""
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{(RAIZ / '_scratch' / 'vault.db').as_posix()}?mode=ro", uri=True)
for lid in (26604, 27439):
    rows = con.execute("SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id=? "
                       "ORDER BY board, card_name", (lid,)).fetchall()
    print(f"L{lid} = [")
    for b, n, q in rows:
        print(f"    ({b!r}, {n!r}, {q}),")
    print("]")
