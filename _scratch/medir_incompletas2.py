"""Segunda passagem: as formas que sobram, os deck_cards dos quatro decks e o
painel. Lê a cópia feita por medir_incompletas.py."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

AQUI = Path(__file__).resolve().parent
con = sqlite3.connect(AQUI / "vault-copia.db")
con.row_factory = sqlite3.Row

SOMA = ("COALESCE((SELECT SUM(quantity) FROM decklist_cards WHERE decklist_id=d.id AND board='{}'),0)")
rows = con.execute(f"""SELECT d.id, d.source, d.format, d.event_date, d.player, d.url,
         {SOMA.format('main')} m, {SOMA.format('side')} s FROM decklists d
   WHERE d.format IN ('modern','pioneer','legacy','standard') AND d.event_tier='Challenge'
     AND d.event_date >= '2026-09-29'""").fetchall()
mas = [r for r in rows if r["m"] != 60 or r["s"] != 15]
print("abaixo de 60 no main:", sum(1 for r in mas if r["m"] < 60))
print("sb entre 1 e 14:", sum(1 for r in mas if 0 < r["s"] < 15))
print("sb a 0:", sum(1 for r in mas if r["s"] == 0))
print("main > 60:", sum(1 for r in mas if r["m"] > 60))
f = Counter((r["format"], r["m"], r["s"]) for r in mas)
print(sorted(f.items()))
print("\nas com sb curto ou main<60:")
for r in mas:
    if r["m"] < 60 or 0 < r["s"] < 15 or r["s"] == 0:
        print(" ", r["id"], r["source"], r["format"], r["event_date"], r["player"], r["m"], r["s"], r["url"])

print("\nmain 80: cartas-companheiro / Yorion?")
for r in mas:
    if r["m"] >= 79:
        y = con.execute("SELECT card_name FROM decklist_cards WHERE decklist_id=? AND card_name LIKE 'Yorion%'", (r["id"],)).fetchone()
        print(" ", r["id"], r["format"], r["m"], "Yorion" if y else "-")
        break
print("main>=79 com Yorion:", sum(1 for r in mas if r["m"] >= 79 and con.execute(
    "SELECT 1 FROM decklist_cards WHERE decklist_id=? AND card_name LIKE 'Yorion%'", (r["id"],)).fetchone()))

print("\ndeck_cards dos quatro decks seguidos:")
for i in (1, 2, 7, 11):
    t = con.execute("SELECT board, SUM(qty) FROM deck_cards WHERE deck_id=? GROUP BY board", (i,)).fetchall() \
        if "qty" in [c[1] for c in con.execute("PRAGMA table_info(deck_cards)")] else \
        con.execute("SELECT board, SUM(quantity) FROM deck_cards WHERE deck_id=? GROUP BY board", (i,)).fetchall()
    print(" ", i, [tuple(x) for x in t])

print("\ndeck_lista_trocas colunas:", [c[1] for c in con.execute("PRAGMA table_info(deck_lista_trocas)")])
for r in con.execute("SELECT * FROM deck_lista_trocas ORDER BY rowid DESC LIMIT 8"):
    d = dict(r)
    for k in ("de_cartas", "para_cartas"):
        if d.get(k):
            cs = json.loads(d[k])
            d[k] = f"{len(cs)} linhas"
    print(" ", d)
