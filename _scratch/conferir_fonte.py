"""Confere as quatro listas (e as de sideboard curto) contra a página do mtgo.com.

Para cada lista: as entradas CRUAS da página (antes da soma), o que a gravação
antiga (INSERT OR REPLACE = fica a última entrada) teria guardado, o que a soma
dá, e o que está na base. Um pedido por página, com o ritmo do `_get_mtgo`.
Uso: py _scratch/conferir_fonte.py [--curtas]
"""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from mtgvault import sources  # noqa: E402

con = sqlite3.connect(AQUI / "vault-copia.db")
con.row_factory = sqlite3.Row

ids = [27447, 27439, 27500, 27495]
if "--curtas" in sys.argv:
    ids = [23659, 25210, 26671, 22893, 22934, 23548, 27195, 27174, 27606, 25903,
           23208, 23694, 25295, 27627, 27639]

por_url = defaultdict(list)
for i in ids:
    r = con.execute("SELECT id, player, url FROM decklists WHERE id=?", (i,)).fetchone()
    por_url[r["url"]].append(r)

for url, linhas in por_url.items():
    blob = sources.parse_mtgo_page(sources._get_mtgo(url).text)
    decks = {str(d.get("player") or "").lower(): d for d in blob.get("decklists") or []}
    for r in linhas:
        d = decks.get(r["player"].lower())
        if d is None:
            print(f"#{r['id']} {r['player']}: NAO ESTA NA PAGINA"); continue
        print(f"\n#{r['id']} {r['player']}  {url}")
        for board in ("main", "side"):
            crus = sources._cards(d, board)
            ultima = {}
            for n, q in crus:
                ultima[n] = q          # a regra antiga: a última entrada ganha
            soma = defaultdict(int)
            for n, q in crus:
                soma[n] += q
            base = dict(con.execute("SELECT card_name, quantity FROM decklist_cards "
                                    "WHERE decklist_id=? AND board=?", (r["id"], board)).fetchall())
            rep = sorted((n, [q for m, q in crus if m == n]) for n in soma
                         if sum(1 for m, _ in crus if m == n) > 1)
            print(f"  {board}: entradas na pagina {len(crus)}, soma {sum(soma.values())}, "
                  f"gravacao antiga {sum(ultima.values())}, base {sum(base.values())}")
            for n, qs in rep:
                print(f"     repetida: {n} {qs} -> antiga ficava {ultima[n]}, soma {sum(qs)}")
            dif = {n: (soma.get(n, 0), base.get(n, 0)) for n in set(soma) | set(base)
                   if soma.get(n, 0) != base.get(n, 0)}
            if dif:
                print("     DIFERE da base (pagina, base):", dif)
