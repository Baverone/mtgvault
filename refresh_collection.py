"""Recalcula a posse do site (valor 💶 + faltas 🛒) de TODOS os decks.

Modelo de preço da posse:
  1.  Base = preço da impressão em `price_latest` (foil-aware) — bom para os decks
      premium (Cloud, Blue Farm) que são versões foil/especiais caras.
  1b. Para os decks NÃO-premium (staples baratos, ex.: premodern), substitui pelo
      `card_price` (verdadeiro mais barato por nome, Scryfall) — porque a impressão
      resolvida pode ser cara (o price_latest só cobre bem as versões caras).
  2.  Overrides manuais de `price_overrides.csv` — versões especiais que o André
      tem. Se a linha tiver `sub_collection`, aplica-se SÓ a esse deck (não
      contamina os outros que têm a versão barata da mesma carta).

Corre isto sempre que importes cartas (`import_owned.py`) ou edites os overrides,
e faz commit do `data/vault.db`. Uso:  python refresh_collection.py
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

# Decks de versões foil/premium: o valor vem do price_latest (foil) + overrides,
# NÃO do "mais barato por nome" (senão sub-avaliava as foils).
PREMIUM_SUBS = {"Cloud", "Blue Farm", "Cloud cEDH"}


def _front(n: str) -> str:
    return n.split(" // ")[0].strip().lower()


def refresh(con) -> str:
    """Reconstrói `collection_owned` a partir dos `copies` (+ card_price + overrides).
    Recebe uma conexão já com o catálogo ATTACHed (para correr dentro do job diário)."""
    con.execute("""CREATE TABLE IF NOT EXISTS collection_owned(
        sub_collection TEXT NOT NULL, card_name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1, unit_price REAL,
        PRIMARY KEY (sub_collection, card_name))""")

    # 1. quantidades por sub+nome, com preço-base do price_latest da impressão
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

    # 1b. decks NÃO-premium: base = card_price (verdadeiro mais barato por nome)
    cp_map: dict[str, float] = {}
    try:
        for r in con.execute("SELECT card_name, eur FROM card_price"):
            if r["eur"] is not None:
                cp_map[r["card_name"].lower()] = r["eur"]
    except sqlite3.OperationalError:
        cp_map = {}
    for r in con.execute("SELECT sub_collection, card_name FROM collection_owned").fetchall():
        if r["sub_collection"] in PREMIUM_SUBS:
            continue
        eur = cp_map.get(r["card_name"].lower()) or cp_map.get(_front(r["card_name"]))
        if eur is not None:
            con.execute("UPDATE collection_owned SET unit_price = ? "
                        "WHERE sub_collection = ? AND card_name = ?",
                        (eur, r["sub_collection"], r["card_name"]))

    # 2. overrides manuais (nome[, sub_collection]) — versões especiais do André
    n = 0
    if OVERRIDES.exists():
        por_face: dict[str, list[tuple[str, str]]] = {}
        for r in con.execute("SELECT sub_collection, card_name FROM collection_owned"):
            por_face.setdefault(_front(r["card_name"]), []).append(
                (r["sub_collection"], r["card_name"]))
        for row in csv.DictReader(open(OVERRIDES, encoding="utf-8-sig")):
            nome = (row.get("card_name") or "").strip()
            valor = (row.get("unit_price") or "").strip()
            only_sub = (row.get("sub_collection") or "").strip()
            if not nome or not valor:
                continue
            try:
                preco = float(valor.replace(",", "."))
            except ValueError:
                continue
            for sub, alvo in por_face.get(_front(nome), []):
                if only_sub and sub != only_sub:
                    continue
                con.execute("UPDATE collection_owned SET unit_price = ? "
                            "WHERE sub_collection = ? AND card_name = ?", (preco, sub, alvo))
                n += 1

    con.commit()
    subs = [r["sub_collection"] for r in con.execute(
        "SELECT DISTINCT sub_collection FROM collection_owned ORDER BY sub_collection")]
    return f"{n} overrides, {len(subs)} sub-coleções"


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("ATTACH DATABASE ? AS catalog", (str(CAT),))
    print(refresh(con) + " — detalhe:")
    for sub in [r["sub_collection"] for r in con.execute(
            "SELECT DISTINCT sub_collection FROM collection_owned ORDER BY sub_collection")]:
        tot = con.execute("SELECT SUM(COALESCE(unit_price,0)*quantity) FROM collection_owned "
                          "WHERE sub_collection = ?", (sub,)).fetchone()[0] or 0
        sem = [r["card_name"] for r in con.execute(
            "SELECT card_name FROM collection_owned WHERE sub_collection = ? "
            "AND unit_price IS NULL ORDER BY card_name", (sub,))]
        print(f"  {sub}: valor {tot:.2f} EUR" + (f" | sem preço: {', '.join(sem)}" if sem else ""))
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.close()


if __name__ == "__main__":
    main()
