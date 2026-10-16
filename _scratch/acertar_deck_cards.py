"""Acerta as `deck_cards` de um deck cuja decklist de referência foi RELIDA pelo
`sources.reler_mtgo` (16/10) e que o `my_decks.refresh` já não volta a gravar.

Medido a 2026-10-16 na base do main: é UM deck — o «4c Control» (Standard, em
`my_decks.SAIU` desde 16/10), congelado com a leitura antiga da lista #27495
(MCScards): main 59, Blood Crypt 3 em vez de 4. Os seguidos acertaram-se sozinhos
na corrida das 08:00 (motivo `releitura` na `deck_lista_trocas`).

Faz o mesmo que o `my_decks._store` faria (linha `releitura` no histórico ANTES
de substituir as `deck_cards`), com backup antes. Por omissão só mostra.
Uso: py _scratch/acertar_deck_cards.py <caminho do vault.db> [--aplicar]
"""
import re
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import my_decks  # noqa: E402

base = Path(sys.argv[1])
aplicar = "--aplicar" in sys.argv
con = sqlite3.connect(base)
con.row_factory = sqlite3.Row

alvos = []
for d in con.execute("SELECT id, name, format, notes FROM decks"):
    nota = my_decks.ler_nota(d["notes"])
    if not nota:
        continue
    lid = nota["decklist_id"]
    lista = my_decks._cartas_da_lista(con, lid)
    if not lista:
        continue                       # a decklist já foi podada: nada a reler
    if my_decks._cartas_do_deck(con, d["id"]) != lista:
        alvos.append((d, lid))

for d, lid in alvos:
    a = sum(q for b, _n, q in my_decks._cartas_do_deck(con, d["id"]) if b == "main")
    b = sum(q for bb, _n, q in my_decks._cartas_da_lista(con, lid) if bb == "main")
    print(f"{d['id']} {d['name']} ({d['format']}) #{lid}: main {a} -> {b}")
if not alvos:
    print("nada a acertar")
    sys.exit(0)
if not aplicar:
    print("(só a mostrar; --aplicar para escrever, com backup)")
    sys.exit(0)

copia = base.parent / "backups" / f"vault-{datetime.now():%Y-%m-%d-%H%M%S}-acertar-deck-cards.db"
copia.parent.mkdir(parents=True, exist_ok=True)
con.execute("VACUUM INTO ?", (str(copia),))
print("backup:", copia)
hoje = date.today().isoformat()
for d, lid in alvos:
    dl = con.execute("SELECT id, source, player, event_date FROM decklists WHERE id = ?",
                     (lid,)).fetchone()
    out = []
    my_decks._store(con, d["name"], d["format"], dl, out, hoje)
    print("  ", "; ".join(out))
con.commit()
