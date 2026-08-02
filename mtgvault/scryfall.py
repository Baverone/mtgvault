"""Catálogo de cartas via Scryfall bulk data.

A Scryfall é a espinha dorsal: dá-nos o ID de cada impressão, o nome oracle,
as legalidades e — crucialmente — o `cardmarket_id`, que é a ponte para os
preços do Cardmarket.

Usamos o ficheiro "default_cards" (todas as impressões, todas as línguas
inglesas por omissão). É grande (~500 MB); lemos em streaming com ijson.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import requests

BULK_INDEX = "https://api.scryfall.com/bulk-data"
UA = {"User-Agent": "mtgvault/0.1", "Accept": "application/json"}
_LAST_CALL = 0.0


def _polite_get(url: str, **kw) -> requests.Response:
    """A Scryfall pede 50-100ms entre pedidos. Respeitamos."""
    global _LAST_CALL
    wait = 0.1 - (time.time() - _LAST_CALL)
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, headers=UA, timeout=60, **kw)
    _LAST_CALL = time.time()
    r.raise_for_status()
    return r


def download_bulk(kind: str = "default_cards", dest: Path | None = None) -> Path:
    """Descarrega o ficheiro bulk mais recente. Devolve o caminho local."""
    index = _polite_get(BULK_INDEX).json()
    entry = next(d for d in index["data"] if d["type"] == kind)
    dest = dest or Path.home() / "mtgvault" / "cache" / f"{kind}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)

    with _polite_get(entry["download_uri"], stream=True) as r, dest.open("wb") as fh:
        for chunk in r.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
    return dest


def _row(c: dict) -> tuple | None:
    if c.get("layout") in ("art_series", "token", "double_faced_token", "emblem"):
        return None
    img = (c.get("image_uris") or {}).get("normal")
    if not img and c.get("card_faces"):
        img = (c["card_faces"][0].get("image_uris") or {}).get("normal")
    return (
        c["id"],
        c.get("oracle_id") or c["id"],
        c["name"],
        c["set"],
        c.get("set_name"),
        c.get("collector_number"),
        c.get("lang"),
        c.get("rarity"),
        c.get("type_line"),
        c.get("mana_cost"),
        c.get("cmc"),
        "".join(c.get("color_identity") or []),
        json.dumps(c.get("finishes") or []),
        c.get("released_at"),
        c.get("cardmarket_id"),
        c.get("tcgplayer_id"),
        img,
        json.dumps(c.get("legalities") or {}),
        int(bool(c.get("digital"))),
        int(bool(c.get("reprint"))),
    )


INSERT = """INSERT OR REPLACE INTO catalog.cards (
    scryfall_id, oracle_id, name, set_code, set_name, collector_number, lang,
    rarity, type_line, mana_cost, cmc, color_identity, finishes, released_at,
    cardmarket_id, tcgplayer_id, image_uri, legalities, digital, reprint
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


def load_bulk(con: sqlite3.Connection, path: Path, batch: int = 5000) -> int:
    """Carrega o ficheiro bulk para a tabela `cards`."""
    import ijson  # importado aqui para não pesar no arranque

    n, buf = 0, []
    with path.open("rb") as fh:
        for card in ijson.items(fh, "item"):
            row = _row(card)
            if row is None:
                continue
            buf.append(row)
            if len(buf) >= batch:
                con.executemany(INSERT, buf)
                con.commit()
                n += len(buf)
                buf.clear()
    if buf:
        con.executemany(INSERT, buf)
        con.commit()
        n += len(buf)
    return n


def sync(con: sqlite3.Connection) -> int:
    """Atualiza o catálogo completo. Correr uma vez por semana chega."""
    return load_bulk(con, download_bulk())


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------
def find_printing(
    con: sqlite3.Connection,
    name: str,
    set_code: str | None = None,
    collector_number: str | None = None,
) -> sqlite3.Row | None:
    """Encontra uma impressão específica. Sem set, devolve a mais barata/antiga."""
    q = "SELECT * FROM cards WHERE lower(name) = lower(?) AND digital = 0"
    args: list = [name]
    if set_code:
        q += " AND lower(set_code) = lower(?)"
        args.append(set_code)
    if collector_number:
        q += " AND collector_number = ?"
        args.append(collector_number)
    q += " ORDER BY released_at ASC LIMIT 1"
    return con.execute(q, args).fetchone()


def resolve_name(con: sqlite3.Connection, name: str) -> str | None:
    """Normaliza um nome escrito à mão para o nome oracle exato.

    Tolera falta de acentos, apóstrofos diferentes e só a primeira face
    de cartas duplas ("Fable of the Mirror-Breaker" -> nome completo).
    """
    name = name.strip()
    row = con.execute(
        "SELECT name FROM cards WHERE lower(name) = lower(?) LIMIT 1", (name,)
    ).fetchone()
    if row:
        return row["name"]
    row = con.execute(
        "SELECT name FROM cards WHERE name LIKE ? || ' //%' LIMIT 1", (name,)
    ).fetchone()
    if row:
        return row["name"]
    row = con.execute(
        "SELECT name FROM cards WHERE lower(replace(name, '’', '''')) = lower(?) LIMIT 1",
        (name.replace("’", "'"),),
    ).fetchone()
    return row["name"] if row else None
