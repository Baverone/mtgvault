"""Vigiar fontes específicas: jogadores do MTGO e decks do Moxfield.

A diferença face à recolha geral: aqui não queremos agregados do metagame,
queremos ESTE baralho, e queremos saber **o que mudou** desde a última vez.
Cada versão fica guardada em `watched_snapshots`, o que permite `diff`.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date

from . import moxfield


def list_hash(cards: list[tuple[str, str, int]]) -> str:
    """Impressão digital de uma lista (board, nome, qty)."""
    payload = "|".join(f"{b}:{n}:{q}" for b, n, q in sorted(cards))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def add(con: sqlite3.Connection, kind: str, key: str, label: str, fmt: str,
        notes: str = "") -> int:
    con.execute(
        """INSERT OR IGNORE INTO watched (kind, key, label, format, notes)
           VALUES (?,?,?,?,?)""",
        (kind, key, label, fmt.lower(), notes),
    )
    con.commit()
    return con.execute(
        "SELECT id FROM watched WHERE kind=? AND key=? AND format=?",
        (kind, key, fmt.lower()),
    ).fetchone()["id"]


def _save_snapshot(con, wid: int, cards, url: str = "") -> bool:
    """Grava se for diferente da última. Devolve True se mudou."""
    h = list_hash(cards)
    prev = con.execute("SELECT last_hash FROM watched WHERE id = ?", (wid,)).fetchone()
    changed = prev["last_hash"] != h
    con.execute(
        """INSERT OR IGNORE INTO watched_snapshots
           (watched_id, taken_at, list_hash, source_url, cards)
           VALUES (?,?,?,?,?)""",
        (wid, date.today().isoformat(), h, url, json.dumps(cards)),
    )
    con.execute(
        "UPDATE watched SET last_checked = date('now'), last_hash = ? WHERE id = ?",
        (h, wid),
    )
    con.commit()
    return changed


# ---------------------------------------------------------------------------
# Verificação
# ---------------------------------------------------------------------------
def check_mtgo_player(con: sqlite3.Connection, wid: int) -> dict:
    """Última lista publicada por um jogador, das decklists já recolhidas.

    Não vai à rede: aproveita o que `harvest_mtgo` já trouxe. Basta correr o
    harvest primeiro (é o que o daily.py faz).
    """
    w = con.execute("SELECT * FROM watched WHERE id = ?", (wid,)).fetchone()
    row = con.execute(
        """SELECT id, event_date, event_name, url FROM decklists
            WHERE lower(player) = lower(?) AND format = ?
            ORDER BY event_date DESC, id DESC LIMIT 1""",
        (w["key"], w["format"]),
    ).fetchone()
    if row is None:
        return {"watched": dict(w), "found": False}

    cards = [
        (r["board"], r["card_name"], r["quantity"])
        for r in con.execute(
            "SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id = ?",
            (row["id"],),
        )
    ]
    changed = _save_snapshot(con, wid, cards, row["url"] or "")
    return {"watched": dict(w), "found": True, "changed": changed,
            "event": row["event_name"], "date": row["event_date"], "cards": cards}


def check_moxfield(con: sqlite3.Connection, wid: int) -> dict:
    """Vai ao Moxfield ver se a lista foi atualizada."""
    w = con.execute("SELECT * FROM watched WHERE id = ?", (wid,)).fetchone()
    deck = moxfield.fetch_deck(w["key"])
    changed = _save_snapshot(con, wid, deck["cards"], deck["url"])
    return {"watched": dict(w), "found": True, "changed": changed,
            "updated_at": deck.get("updated_at"), "name": deck.get("name"),
            "cards": deck["cards"]}


def check_all(con: sqlite3.Connection) -> list[dict]:
    out = []
    for w in con.execute("SELECT * FROM watched WHERE active = 1 ORDER BY id"):
        try:
            if w["kind"] == "mtgo_player":
                out.append(check_mtgo_player(con, w["id"]))
            elif w["kind"] == "moxfield":
                out.append(check_moxfield(con, w["id"]))
        except Exception as e:  # noqa: BLE001
            out.append({"watched": dict(w), "found": False, "error": str(e)})
    return out


# ---------------------------------------------------------------------------
# Diff entre versões
# ---------------------------------------------------------------------------
def diff(con: sqlite3.Connection, wid: int, n: int = 2) -> dict:
    """Compara as duas versões mais recentes de um baralho vigiado."""
    snaps = con.execute(
        """SELECT taken_at, cards FROM watched_snapshots
            WHERE watched_id = ? ORDER BY taken_at DESC, id DESC LIMIT ?""",
        (wid, n),
    ).fetchall()
    if len(snaps) < 2:
        return {"changes": [], "note": "só existe uma versão guardada"}

    def as_map(s):
        return {(b, nm): q for b, nm, q in json.loads(s["cards"])}

    new, old = as_map(snaps[0]), as_map(snaps[1])
    changes = []
    for k in sorted(set(new) | set(old)):
        before, after = old.get(k, 0), new.get(k, 0)
        if before != after:
            changes.append({"board": k[0], "card_name": k[1],
                            "before": before, "after": after,
                            "delta": after - before})
    return {"from": snaps[1]["taken_at"], "to": snaps[0]["taken_at"],
            "changes": sorted(changes, key=lambda c: -abs(c["delta"]))}


def latest_cards(con: sqlite3.Connection, wid: int) -> list[tuple[str, str, int]]:
    row = con.execute(
        "SELECT cards FROM watched_snapshots WHERE watched_id = ? "
        "ORDER BY taken_at DESC, id DESC LIMIT 1", (wid,)
    ).fetchone()
    return [tuple(c) for c in json.loads(row["cards"])] if row else []
