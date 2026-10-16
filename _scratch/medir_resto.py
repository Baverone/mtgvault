"""O que ainda está curto na base (todas as datas, o critério do reler_mtgo) e os
decks seguidos cujas deck_cards já não batem com a decklist de referência."""
import re
import sqlite3
from pathlib import Path

AQUI = Path(__file__).resolve().parent
con = sqlite3.connect(AQUI / "vault-copia.db")
con.row_factory = sqlite3.Row
CMD = ("duel-commander", "cedh", "commander")
S = "(SELECT COALESCE(SUM(quantity),0) FROM decklist_cards WHERE decklist_id=dl.id{})"
rows = con.execute(f"""SELECT dl.id, dl.source, dl.format, dl.event_date, dl.player, dl.url,
        {S.format(" AND board='main'")} m, {S.format(" AND board='side'")} s, {S.format('')} t
   FROM decklists dl""").fetchall()
curtas = [r for r in rows if (r["format"] in CMD and r["t"] < 100)
          or (r["format"] not in CMD and r["m"] < 60)]
print("listas na base:", len(rows))
print("ainda curtas (main<60 / comandante<100):", len(curtas))
for r in curtas[:30]:
    print(" ", dict(r))

print("\ndecks com nota '(#id)': deck_cards vs decklist")
for d in con.execute("SELECT id, name, format, notes FROM decks WHERE notes LIKE '%(#%'"):
    m = re.search(r"\(#(\d+)\)", d["notes"] or "")
    did = int(m.group(1))
    lista = {(r[0], r[1]): r[2] for r in con.execute(
        "SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id=?", (did,))}
    cols = [c[1] for c in con.execute("PRAGMA table_info(deck_cards)")]
    q = "qty" if "qty" in cols else "quantity"
    deck = {(r[0], r[1]): r[2] for r in con.execute(
        f"SELECT board, card_name, {q} FROM deck_cards WHERE deck_id=?", (d["id"],))}
    if not lista:
        print(f"  {d['id']} {d['name']}: decklist #{did} ja nao existe na base"); continue
    dif = {k: (deck.get(k, 0), lista.get(k, 0)) for k in set(lista) | set(deck)
           if deck.get(k, 0) != lista.get(k, 0)}
    tm = lambda x, b: sum(v for (bb, _), v in x.items() if bb == b)
    print(f"  {d['id']:3} {d['name'][:34]:34} #{did} deck {tm(deck,'main')}+{tm(deck,'side')} "
          f"lista {tm(lista,'main')}+{tm(lista,'side')} {'IGUAL' if not dif else dif}")
