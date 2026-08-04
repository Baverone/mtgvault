"""Importa a posse fotografada para `copies`.

Lê `owned.csv` (sub_collection, card_name, quantity) — cada carta que fotografo
da coleção — e reconstrói as `copies` dessas sub-coleções, resolvendo cada nome
à **impressão mais barata** (o preço exato da versão é secundário: são staples
antigos e as versões são ilustrativas). Não toca em sub-coleções que não estão
no CSV (Blue Farm, Cloud, etc. mantêm as suas cópias importadas à parte).

Fluxo por lote: acrescento/edito linhas no owned.csv → `python import_owned.py`
→ `python refresh_collection.py` → commit. Idempotente (apaga e reinsere por sub).
"""
from __future__ import annotations

import csv
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("MTGVAULT_HOME", ROOT / "data"))
DB, CAT = HOME / "vault.db", HOME / "catalog.db"
CSV_PATH = ROOT / "owned.csv"


def resolve(con: sqlite3.Connection, name: str) -> str | None:
    """scryfall_id da impressão nonfoil mais barata (com preço); senão qualquer EN."""
    like = name + " // %"
    r = con.execute(
        """SELECT c.scryfall_id FROM catalog.cards c
             JOIN price_latest p ON p.scryfall_id = c.scryfall_id AND p.finish = 'nonfoil'
            WHERE (c.name = ? OR c.name LIKE ?) AND p.trend IS NOT NULL
            ORDER BY p.trend ASC LIMIT 1""", (name, like)).fetchone()
    if r:
        return r[0]
    r = con.execute(
        """SELECT scryfall_id FROM catalog.cards
            WHERE (name = ? OR name LIKE ?) AND lang = 'en'
            ORDER BY released_at LIMIT 1""", (name, like)).fetchone()
    return r[0] if r else None


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("ATTACH DATABASE ? AS catalog", (str(CAT),))

    decks: dict[str, dict[str, int]] = defaultdict(dict)
    for row in csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")):
        sub = (row.get("sub_collection") or "").strip()
        name = (row.get("card_name") or "").strip()
        qty = (row.get("quantity") or "").strip()
        if sub and name and qty:
            decks[sub][name] = decks[sub].get(name, 0) + int(qty)

    miss = []
    for sub, cards in decks.items():
        con.execute("INSERT OR IGNORE INTO sub_collections(name, purpose) VALUES (?, 'player')", (sub,))
        sid = con.execute("SELECT id FROM sub_collections WHERE name = ?", (sub,)).fetchone()["id"]
        con.execute("DELETE FROM copies WHERE sub_collection_id = ?", (sid,))
        for name, q in cards.items():
            sfid = resolve(con, name)
            if sfid:
                con.execute(
                    "INSERT INTO copies(scryfall_id, quantity, finish, language, purpose, sub_collection_id) "
                    "VALUES (?,?,?,?,?,?)", (sfid, q, "nonfoil", "pt", "player", sid))
            else:
                miss.append((sub, name))
    con.commit()
    print("importado:", {s: sum(c.values()) for s, c in decks.items()})
    if miss:
        print("NÃO resolvidos (verificar nome EN):", miss)


if __name__ == "__main__":
    main()
