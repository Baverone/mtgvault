"""Recalcula a posse do site (valor 💶 + faltas 🛒) do Blue Farm.

Faz duas coisas:
  1. Reconstrói `collection_owned` a partir das cópias reais (tabela `copies`),
     com o preço da Scryfall de cada impressão.
  2. Aplica os overrides manuais de `price_overrides.csv` — os preços que
     escreves à mão para as cartas que a Scryfall não cobre bem (versões FF de
     coleção, promos sem preço, etc.).

Corre isto sempre que editares o `price_overrides.csv` (ou compres cartas novas)
e faz commit do `data/vault.db`. O site lê daqui, por nome, sem precisar do
catálogo. Uso:  python refresh_collection.py
"""
from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("MTGVAULT_HOME", ROOT / "data"))
DB, CAT = HOME / "vault.db", HOME / "catalog.db"
OVERRIDES = ROOT / "price_overrides.csv"
SUB = "Blue Farm"


def _front(n: str) -> str:
    return n.split(" // ")[0].strip().lower()


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("ATTACH DATABASE ? AS catalog", (str(CAT),))
    con.execute("""CREATE TABLE IF NOT EXISTS collection_owned(
        sub_collection TEXT NOT NULL, card_name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1, unit_price REAL,
        PRIMARY KEY (sub_collection, card_name))""")

    # 1. reconstruir a partir das cópias reais, com preço da Scryfall
    con.execute("DELETE FROM collection_owned WHERE sub_collection = ?", (SUB,))
    for r in con.execute(
        """SELECT cat.name AS nm, SUM(cp.quantity) AS q,
                  MAX((SELECT trend FROM price_latest p
                        WHERE p.scryfall_id = cp.scryfall_id
                          AND p.source = 'cardmarket' AND p.finish = cp.finish)) AS price
             FROM copies cp
             JOIN catalog.cards cat ON cat.scryfall_id = cp.scryfall_id
             JOIN sub_collections s ON s.id = cp.sub_collection_id
            WHERE s.name = ? GROUP BY cat.name""", (SUB,)):
        con.execute("INSERT OR REPLACE INTO collection_owned VALUES (?,?,?,?)",
                    (SUB, r["nm"], r["q"], r["price"]))

    # 2. overrides manuais (nome, preço) do price_overrides.csv
    n = 0
    if OVERRIDES.exists():
        existentes = {_front(r["card_name"]): r["card_name"] for r in con.execute(
            "SELECT card_name FROM collection_owned WHERE sub_collection = ?", (SUB,))}
        for row in csv.DictReader(open(OVERRIDES, encoding="utf-8-sig")):
            nome = (row.get("card_name") or "").strip()
            valor = (row.get("unit_price") or "").strip()
            if not nome or not valor:
                continue
            try:
                preco = float(valor.replace(",", "."))
            except ValueError:
                continue
            alvo = existentes.get(_front(nome))
            if alvo:
                con.execute("UPDATE collection_owned SET unit_price = ? "
                            "WHERE sub_collection = ? AND card_name = ?", (preco, SUB, alvo))
                n += 1

    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    tot = con.execute("SELECT SUM(COALESCE(unit_price,0)*quantity) FROM collection_owned "
                      "WHERE sub_collection = ?", (SUB,)).fetchone()[0] or 0
    sem = [r["card_name"] for r in con.execute(
        "SELECT card_name FROM collection_owned WHERE sub_collection = ? "
        "AND unit_price IS NULL ORDER BY card_name", (SUB,))]
    total = con.execute("SELECT COUNT(*) FROM collection_owned WHERE sub_collection = ?",
                        (SUB,)).fetchone()[0]
    print(f"{total} cartas | {n} overrides aplicados | valor {tot:.2f} EUR")
    if sem:
        print(f"{len(sem)} ainda sem preço: " + ", ".join(sem))


if __name__ == "__main__":
    main()
