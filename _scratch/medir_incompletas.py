"""Mede as listas de Challenge com main != 60 ou sb != 15 (desde 2026-09-29).

Lê uma CÓPIA da base (feita pela API de backup do sqlite3, em só-leitura sobre a
original) para não tocar no data/vault.db do main.
Uso: py _scratch/medir_incompletas.py [--copiar]
"""
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ORIG = Path(r"C:\Users\Catarina\Desktop\Servidor MTG Coleçao\Servidor MTG Coleçao\data\vault.db")
COPIA = AQUI / "vault-copia.db"

if "--copiar" in sys.argv or not COPIA.exists():
    src = sqlite3.connect(f"file:{ORIG.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(COPIA)
    src.backup(dst)
    dst.close()
    src.close()

con = sqlite3.connect(COPIA)
con.row_factory = sqlite3.Row

FMTS = ("modern", "pioneer", "legacy", "standard")
rows = con.execute(f"""
  SELECT d.id, d.source, d.format, d.event_date, d.event_name, d.player, d.url,
         COALESCE((SELECT SUM(quantity) FROM decklist_cards WHERE decklist_id=d.id AND board='main'),0) m,
         COALESCE((SELECT SUM(quantity) FROM decklist_cards WHERE decklist_id=d.id AND board='side'),0) s
    FROM decklists d
   WHERE d.format IN ({','.join('?'*len(FMTS))}) AND d.event_tier='Challenge'
     AND d.event_date >= '2026-09-29'""", FMTS).fetchall()

tot = Counter(); mau = Counter(); pordia = defaultdict(lambda: [0, 0])
formas = Counter()
for r in rows:
    k = (r["format"], r["source"])
    tot[k] += 1
    ruim = r["m"] != 60 or r["s"] != 15
    pordia[r["event_date"]][0] += 1
    if ruim:
        mau[k] += 1
        pordia[r["event_date"]][1] += 1
        formas[(r["m"], r["s"])] += 1

print(f"listas de Challenge desde 2026-09-29: {len(rows)}, com main!=60 ou sb!=15: {sum(mau.values())}")
print("\npor formato e fonte (mas/total):")
for k in sorted(tot):
    print(f"  {k[0]:9} {k[1]:8} {mau[k]:4} / {tot[k]}")
print("\npor dia (mas/total):")
for d in sorted(pordia):
    print(f"  {d} {pordia[d][1]:4} / {pordia[d][0]}")
print("\nformas (main, sb) mais comuns entre as mas:", formas.most_common(12))

print("\nas quatro:")
for i in (27447, 27439, 27500, 27495):
    r = con.execute("SELECT id, source, format, event_date, event_name, player, url, content_hash "
                    "FROM decklists WHERE id=?", (i,)).fetchone()
    if not r:
        print(f"  {i}: JA NAO EXISTE na base")
        continue
    m = con.execute("SELECT board, SUM(quantity) FROM decklist_cards WHERE decklist_id=? GROUP BY board", (i,)).fetchall()
    print(f"  {i} {r['source']} {r['format']} {r['event_date']} {r['player']} {dict(m)} {r['url']}")

print("\nreferencias dos decks seguidos (tabela decks, notas com 15/10):")
for r in con.execute("SELECT id, name, format, notes FROM decks WHERE notes LIKE '%2026-10-15%'"):
    print(" ", dict(r))
try:
    print("\ndeck_lista_trocas de hoje:")
    for r in con.execute("SELECT * FROM deck_lista_trocas WHERE em >= '2026-10-16' ORDER BY rowid"):
        d = dict(r); d.pop("de_cartas", None); d.pop("para_cartas", None)
        print(" ", d)
except sqlite3.OperationalError as e:
    print("  ", e)
