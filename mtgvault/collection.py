"""Coleção: entrada de cartas, sub-coleções, e o que tenho vs. o que falta."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from . import scryfall


def ensure_sub_collection(con, name: str, purpose: str = "player") -> int:
    con.execute(
        "INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?,?)",
        (name, purpose),
    )
    con.commit()
    return con.execute(
        "SELECT id FROM sub_collections WHERE name = ?", (name,)
    ).fetchone()["id"]


def add_copy(
    con: sqlite3.Connection,
    name: str,
    *,
    set_code: str | None = None,
    collector_number: str | None = None,
    quantity: int = 1,
    finish: str = "nonfoil",
    language: str = "en",
    condition: str = "NM",
    purpose: str = "player",
    sub_collection: str | None = None,
    photo_path: str | None = None,
    acquired_price: float | None = None,
    notes: str | None = None,
) -> int:
    """Adiciona exemplares. Devolve o id da linha criada."""
    card = scryfall.find_printing(con, name, set_code, collector_number)
    if card is None:
        oracle = scryfall.resolve_name(con, name)
        if oracle:
            card = scryfall.find_printing(con, oracle, set_code, collector_number)
    if card is None:
        raise LookupError(f"Carta não encontrada no catálogo: {name!r} ({set_code})")

    sub_id = (
        ensure_sub_collection(con, sub_collection, purpose) if sub_collection else None
    )
    cur = con.execute(
        """INSERT INTO copies (scryfall_id, quantity, finish, language, condition,
                               purpose, sub_collection_id, photo_path,
                               acquired_at, acquired_price, notes)
           VALUES (?,?,?,?,?,?,?,?,date('now'),?,?)""",
        (card["scryfall_id"], quantity, finish, language, condition, purpose,
         sub_id, photo_path, acquired_price, notes),
    )
    con.commit()
    return cur.lastrowid


# Colunas aceites no CSV de importação (as fotos entram por aqui:
# a coluna `photo_path` guarda o caminho do ficheiro no teu disco).
CSV_FIELDS = [
    "name", "set_code", "collector_number", "quantity", "finish", "language",
    "condition", "purpose", "sub_collection", "photo_path", "acquired_price", "notes",
]


def import_csv(con: sqlite3.Connection, path: str | Path) -> tuple[int, list[str]]:
    """Importa um CSV. Devolve (n_importadas, erros)."""
    ok, errors = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            row = {k: (v.strip() if isinstance(v, str) else v)
                   for k, v in row.items() if k in CSV_FIELDS}
            if not row.get("name"):
                continue
            try:
                add_copy(
                    con,
                    row.pop("name"),
                    set_code=row.get("set_code") or None,
                    collector_number=row.get("collector_number") or None,
                    quantity=int(row.get("quantity") or 1),
                    finish=row.get("finish") or "nonfoil",
                    language=row.get("language") or "en",
                    condition=row.get("condition") or "NM",
                    purpose=row.get("purpose") or "player",
                    sub_collection=row.get("sub_collection") or None,
                    photo_path=row.get("photo_path") or None,
                    acquired_price=float(row["acquired_price"])
                    if row.get("acquired_price") else None,
                    notes=row.get("notes") or None,
                )
                ok += 1
            except Exception as e:                       # noqa: BLE001
                errors.append(f"linha {i}: {e}")
    return ok, errors


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def owned_playable(con: sqlite3.Connection,
                   for_deck_id: int | None = None) -> dict[str, int]:
    """Quantidade disponível para jogar, por nome de carta.

    Fica de fora:
      - a coleção de colecionador (purpose='collector')
      - exemplares reservados a OUTRO deck

    `for_deck_id` diz para que deck estamos a contar: as reservas desse deck
    contam, as dos outros não. Sem argumento, só conta o que está livre.
    """
    rows = con.execute(
        """SELECT c.name AS name, SUM(cp.quantity) AS qty
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            WHERE cp.purpose = 'player'
              AND (cp.reserved_deck_id IS NULL OR cp.reserved_deck_id = ?)
            GROUP BY c.name""",
        (for_deck_id,),
    ).fetchall()
    return {r["name"]: r["qty"] for r in rows}


def reserve_for_deck(con: sqlite3.Connection, deck_id: int) -> dict:
    """Reserva ao deck os exemplares livres que ele precisa.

    Não toca em nada que já esteja reservado a outro deck, e não mexe na
    coleção de colecionador. Devolve o que reservou e o que não conseguiu.
    """
    need: dict[str, int] = {}
    for r in con.execute(
        "SELECT card_name, SUM(quantity) q FROM deck_cards "
        "WHERE deck_id = ? GROUP BY card_name", (deck_id,)
    ):
        need[r["card_name"]] = r["q"]

    reservado: dict[str, int] = {}
    for name, qty in need.items():
        falta = qty - (con.execute(
            """SELECT COALESCE(SUM(cp.quantity),0) q FROM copies cp
                 JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.reserved_deck_id = ?""",
            (name, deck_id)).fetchone()["q"])
        if falta <= 0:
            continue
        livres = con.execute(
            """SELECT cp.id, cp.quantity FROM copies cp
                 JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.purpose = 'player'
                  AND cp.reserved_deck_id IS NULL
                ORDER BY cp.quantity ASC""", (name,)).fetchall()
        for lote in livres:
            if falta <= 0:
                break
            if lote["quantity"] <= falta:
                con.execute("UPDATE copies SET reserved_deck_id = ? WHERE id = ?",
                            (deck_id, lote["id"]))
                reservado[name] = reservado.get(name, 0) + lote["quantity"]
                falta -= lote["quantity"]
            else:
                # partir o lote: parte fica reservada, parte fica livre
                con.execute("UPDATE copies SET quantity = quantity - ? WHERE id = ?",
                            (falta, lote["id"]))
                orig = con.execute("SELECT * FROM copies WHERE id = ?",
                                   (lote["id"],)).fetchone()
                con.execute(
                    """INSERT INTO copies (scryfall_id, quantity, finish, language,
                       condition, purpose, sub_collection_id, photo_path,
                       acquired_at, acquired_price, notes, reserved_deck_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (orig["scryfall_id"], falta, orig["finish"], orig["language"],
                     orig["condition"], orig["purpose"], orig["sub_collection_id"],
                     orig["photo_path"], orig["acquired_at"], orig["acquired_price"],
                     orig["notes"], deck_id))
                reservado[name] = reservado.get(name, 0) + falta
                falta = 0
    con.commit()

    em_falta = {n: q - reservado.get(n, 0) for n, q in need.items()
                if q - (con.execute(
                    """SELECT COALESCE(SUM(cp.quantity),0) q FROM copies cp
                         JOIN cards c ON c.scryfall_id = cp.scryfall_id
                        WHERE c.name = ? AND cp.reserved_deck_id = ?""",
                    (n, deck_id)).fetchone()["q"]) > 0}
    return {"reserved": reservado, "still_missing": em_falta}


def release_deck(con: sqlite3.Connection, deck_id: int) -> int:
    n = con.execute("SELECT COUNT(*) c FROM copies WHERE reserved_deck_id = ?",
                    (deck_id,)).fetchone()["c"]
    con.execute("UPDATE copies SET reserved_deck_id = NULL WHERE reserved_deck_id = ?",
                (deck_id,))
    con.commit()
    return n


def reservations(con: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in con.execute(
        """SELECT d.id AS deck_id, d.name AS deck, c.name AS card_name,
                  SUM(cp.quantity) AS quantity
             FROM copies cp
             JOIN decks d ON d.id = cp.reserved_deck_id
             JOIN cards c ON c.scryfall_id = cp.scryfall_id
            GROUP BY d.id, c.name ORDER BY d.name, c.name""")]


def deck_card_needs(con: sqlite3.Connection) -> dict[str, int]:
    """Quantas cópias de cada carta os decks pedem — o máximo que UM único deck
    usa (main+side). É o que precisa de ficar guardado para os decks."""
    needs: dict[str, int] = {}
    for r in con.execute("SELECT deck_id, card_name, SUM(quantity) q FROM deck_cards "
                         "GROUP BY deck_id, card_name"):
        needs[r["card_name"]] = max(needs.get(r["card_name"], 0), r["q"])
    return needs


def deck_extras(con: sqlite3.Connection) -> list[dict]:
    """Regra do André: as cópias a MAIS das cartas que estão em decks são
    "cartas extra dos decks" (backup — guardar), NUNCA excedente para venda. Só
    cartas que não estão em deck nenhum é que podem ser excedente de venda.

    Devolve, por carta que está em decks e de que ele tem mais do que o deck usa,
    quantas cópias são extra dos decks. Só conta exemplares 'player' (owned_playable).
    """
    needs = deck_card_needs(con)
    owned = owned_playable(con)
    out = []
    for name, need in needs.items():
        have = owned.get(name, 0)
        if have > need:
            out.append({"card_name": name, "owned": have, "deck_need": need,
                        "extra": have - need})
    return sorted(out, key=lambda x: -x["extra"])


def collection_value(con: sqlite3.Connection, source: str = "cardmarket") -> list[dict]:
    """Valor atual de cada lote, com o preço mais recente disponível."""
    rows = con.execute(
        """SELECT cp.id, c.name, c.set_code, cp.quantity, cp.finish, cp.purpose,
                  cp.acquired_price,
                  (SELECT trend FROM price_latest p
                    WHERE p.scryfall_id = cp.scryfall_id AND p.source = ?
                      AND p.finish = cp.finish) AS unit_price,
                  (SELECT date FROM price_latest p
                    WHERE p.scryfall_id = cp.scryfall_id AND p.source = ?
                      AND p.finish = cp.finish) AS price_date
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id""",
        (source, source),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["total"] = round((d["unit_price"] or 0) * d["quantity"], 2)
        out.append(d)
    return out


def movers(con: sqlite3.Connection, days: int = 7, source: str = "cardmarket",
           limit: int = 25) -> dict[str, list[dict]]:
    """Cartas da coleção que mais subiram e mais desceram na janela."""
    rows = con.execute(
        """WITH mine AS (
              SELECT DISTINCT scryfall_id, finish FROM copies
           )
           SELECT c.name, c.set_code, m.finish,
                  t.trend AS before, l.trend AS after,
                  (l.trend - t.trend) AS delta,
                  round(100.0 * (l.trend - t.trend) / t.trend, 1) AS pct
             FROM mine m
             JOIN price_latest l
               ON l.scryfall_id = m.scryfall_id AND l.finish = m.finish
              AND l.source = :src
             JOIN cards c ON c.scryfall_id = m.scryfall_id
             JOIN (SELECT m2.scryfall_id, m2.finish,
                    (SELECT h.trend FROM price_history h
                      WHERE h.scryfall_id = m2.scryfall_id AND h.finish = m2.finish
                        AND h.source = :src
                        AND h.date <= date('now', '-' || :days || ' days')
                      ORDER BY h.date DESC LIMIT 1) AS trend
                     FROM mine m2) t
               ON t.scryfall_id = m.scryfall_id AND t.finish = m.finish
            WHERE t.trend > 0.10 AND l.trend IS NOT NULL
            ORDER BY pct DESC""",
        {"src": source, "days": days},
    ).fetchall()
    rows = [dict(r) for r in rows]
    return {"up": rows[:limit], "down": list(reversed(rows[-limit:]))}
