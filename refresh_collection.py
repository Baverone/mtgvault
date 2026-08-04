"""Recalcula a posse do site (valor 💶 + faltas 🛒) de TODOS os decks.

Faz duas coisas:
  1. Reconstrói `collection_owned` a partir das cópias reais (tabela `copies`),
     com o preço da Scryfall de cada impressão — para todas as sub-coleções.
  2. Aplica os overrides manuais de `price_overrides.csv` — os preços que
     escreves à mão (ou que eu busco na Scryfall) para as cartas que o bulk não
     cobre bem (versões de coleção foil, promos, etc.). Aplicam-se por nome.

Corre isto sempre que editares o `price_overrides.csv`, importes cartas novas ou
associes um deck (ver deck_collection), e faz commit do `data/vault.db`. O site
lê daqui, por nome, sem precisar do catálogo. Uso:  python refresh_collection.py
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

    # 1. reconstruir TODAS as sub-coleções a partir das cópias, com preço Scryfall
    con.execute("DELETE FROM collection_owned")
    for r in con.execute(
        """SELECT s.name AS sub, cat.name AS nm, SUM(cp.quantity) AS q,
                  MAX((SELECT trend FROM price_latest p
                        WHERE p.scryfall_id = cp.scryfall_id
                          AND p.source = 'cardmarket' AND p.finish = cp.finish)) AS price
             FROM copies cp
             JOIN catalog.cards cat ON cat.scryfall_id = cp.scryfall_id
             JOIN sub_collections s ON s.id = cp.sub_collection_id
            GROUP BY s.name, cat.name"""):
        con.execute("INSERT OR REPLACE INTO collection_owned VALUES (?,?,?,?)",
                    (r["sub"], r["nm"], r["q"], r["price"]))

    # 2. overrides manuais (nome, preço) — aplicados por nome a todas as sub-coleções
    n = 0
    if OVERRIDES.exists():
        por_face: dict[str, list[tuple[str, str]]] = {}
        for r in con.execute("SELECT sub_collection, card_name FROM collection_owned"):
            por_face.setdefault(_front(r["card_name"]), []).append(
                (r["sub_collection"], r["card_name"]))
        for row in csv.DictReader(open(OVERRIDES, encoding="utf-8-sig")):
            nome = (row.get("card_name") or "").strip()
            valor = (row.get("unit_price") or "").strip()
            if not nome or not valor:
                continue
            try:
                preco = float(valor.replace(",", "."))
            except ValueError:
                continue
            for sub, alvo in por_face.get(_front(nome), []):
                con.execute("UPDATE collection_owned SET unit_price = ? "
                            "WHERE sub_collection = ? AND card_name = ?", (preco, sub, alvo))
                n += 1

    # 3. fallback: preço mais barato por nome (card_price) para o que ficou sem
    #    preço — cobre cartas antigas que o price_latest (por impressão) não tem.
    price_by_name: dict[str, float] = {}
    try:
        for r in con.execute("SELECT card_name, eur FROM card_price"):
            if r["eur"] is not None:
                price_by_name[r["card_name"].lower()] = r["eur"]
    except sqlite3.OperationalError:
        price_by_name = {}
    for r in con.execute("SELECT sub_collection, card_name FROM collection_owned "
                         "WHERE unit_price IS NULL").fetchall():
        eur = price_by_name.get(r["card_name"].lower()) or price_by_name.get(_front(r["card_name"]))
        if eur is not None:
            con.execute("UPDATE collection_owned SET unit_price = ? "
                        "WHERE sub_collection = ? AND card_name = ?",
                        (eur, r["sub_collection"], r["card_name"]))

    con.commit()
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    subs = [r["sub_collection"] for r in con.execute(
        "SELECT DISTINCT sub_collection FROM collection_owned ORDER BY sub_collection")]
    print(f"{n} overrides aplicados. Sub-coleções:")
    for sub in subs:
        tot = con.execute("SELECT SUM(COALESCE(unit_price,0)*quantity) FROM collection_owned "
                          "WHERE sub_collection = ?", (sub,)).fetchone()[0] or 0
        sem = [r["card_name"] for r in con.execute(
            "SELECT card_name FROM collection_owned WHERE sub_collection = ? "
            "AND unit_price IS NULL ORDER BY card_name", (sub,))]
        print(f"  {sub}: valor {tot:.2f} EUR" + (f" | sem preço: {', '.join(sem)}" if sem else ""))


if __name__ == "__main__":
    main()
