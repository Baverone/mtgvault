"""Que decks do metagame consigo montar com a minha coleção?

Para cada formato (por defeito Pioneer, Modern, Legacy) percorre os arquétipos
do metagame (clusters em `archetypes`), constrói a **lista-padrão** de cada um
**só com eventos premier** (Challenge/Qualifier/Showcase/… — exclui as Leagues,
que diluem o sinal; ver coluna `decklists.event_tier`) e cruza com o que tenho
em posse (`collection_owned`). Mostra os que consigo montar em **>= limiar%**
(por defeito 75% do maindeck), ordenados, com as cartas em falta e o custo.

Só precisa da posse — corre isto depois de fotografares/inventariares a coleção.
Uso:  python buildable.py                 (pioneer, modern, legacy, 75%)
      python buildable.py modern 0.60     (só modern, >=60%)
"""
from __future__ import annotations

import os
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("MTGVAULT_HOME", ROOT / "data"))
DB = HOME / "vault.db"

# tiers que NÃO contam para o consenso (ver event_tier); tudo o resto é premier
NON_PREMIER = ("League", "Curated", "outro")
MIN_LISTS = 5          # arquétipos com menos listas premier do que isto são ignorados
DEFAULT_THRESHOLD = 0.75


def front(n: str) -> str:
    return n.split(" // ")[0].strip().lower()


def consensus_main(con: sqlite3.Connection, ids: list[int]) -> dict[str, int]:
    """Lista-padrão do maindeck: cartas em >=50% das listas, quantidade mediana."""
    incl: dict[str, int] = defaultdict(int)
    qty: dict[str, list[int]] = defaultdict(list)
    for i in ids:
        seen: dict[str, int] = defaultdict(int)
        for cn, q in con.execute(
            "SELECT card_name, quantity FROM decklist_cards WHERE decklist_id=? AND board='main'", (i,)):
            seen[cn] += q
        for c, q in seen.items():
            incl[c] += 1
            qty[c].append(q)
    n = len(ids)
    return {c: int(statistics.median(qty[c])) for c, k in incl.items() if n and k >= n * 0.5}


def run(formats: list[str], threshold: float) -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # posse: nome-da-frente -> quantidade (somada em todas as sub-coleções)
    owned: dict[str, int] = defaultdict(int)
    for r in con.execute("SELECT card_name, SUM(quantity) q FROM collection_owned GROUP BY card_name"):
        owned[front(r["card_name"])] += r["q"] or 0
    if not owned:
        print("[!] A coleção ainda não tem cartas em posse (collection_owned vazio).")
        print("    Fotografa/inventaria a coleção primeiro — depois este relatório acende.\n")

    price = {r["card_name"]: r["eur"] for r in con.execute("SELECT card_name, eur FROM card_price")}
    ph = ",".join("?" * len(NON_PREMIER))

    for fmt in formats:
        clusters = con.execute(
            f"""SELECT d.archetype_id aid, a.label, COUNT(*) n
                  FROM decklists d JOIN archetypes a ON a.id = d.archetype_id
                 WHERE d.format = ? AND d.archetype_id IS NOT NULL
                   AND d.event_tier NOT IN ({ph})
                 GROUP BY d.archetype_id HAVING n >= ?
                 ORDER BY n DESC""",
            (fmt, *NON_PREMIER, MIN_LISTS)).fetchall()

        results = []
        for c in clusters:
            ids = [r["id"] for r in con.execute(
                f"""SELECT id FROM decklists WHERE format=? AND archetype_id=?
                       AND event_tier NOT IN ({ph})""", (fmt, c["aid"], *NON_PREMIER))]
            cons = consensus_main(con, ids)
            total = sum(cons.values())
            if not total:
                continue
            have = 0
            miss = []
            for name, need in cons.items():
                h = min(need, owned.get(front(name), 0))
                have += h
                if need - h > 0:
                    miss.append((name, need - h, (need - h) * price.get(name, 0)))
            pct = have / total
            if pct >= threshold:
                cost = sum(m[2] for m in miss)
                results.append((pct, c["label"], c["n"], total, miss, cost))

        results.sort(key=lambda x: -x[0])
        print(f"\n===== {fmt.upper()} — consigo montar >= {threshold:.0%} ({len(results)}) =====")
        if not results:
            print("   (nenhum arquétipo acima do limiar — ou coleção ainda por inventariar)")
        for pct, label, n, total, miss, cost in results:
            print(f"\n  {pct:5.0%}  {label}   [{n} listas premier]")
            faltam = sum(m[1] for m in miss)
            print(f"         faltam {faltam} cartas p/ 100% do main ({total}) · custo {cost:,.2f} EUR")
            for name, q, c in sorted(miss, key=lambda m: -m[2])[:12]:
                print(f"            {q}x {name}  ({c:,.2f} EUR)")
    con.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    fmts = [a for a in args if not a.replace(".", "").isdigit()] or ["pioneer", "modern", "legacy"]
    thr = next((float(a) for a in args if a.replace(".", "").isdigit()), DEFAULT_THRESHOLD)
    run(fmts, thr)
