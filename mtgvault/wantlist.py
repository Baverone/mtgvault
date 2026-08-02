"""O que tenho, o que me falta, e quanto custa fechar a diferença."""
from __future__ import annotations

import sqlite3

from .collection import owned_playable


def cheapest_price(con, card_name: str, source: str = "cardmarket") -> float | None:
    """Preço da impressão não-foil mais barata com preço conhecido."""
    row = con.execute(
        """SELECT MIN(p.trend) AS price
             FROM cards c
             JOIN price_latest p ON p.scryfall_id = c.scryfall_id
            WHERE c.name = ? AND p.source = ? AND p.finish = 'nonfoil'""",
        (card_name, source),
    ).fetchone()
    return row["price"] if row else None


def deck_status(con: sqlite3.Connection, deck_id: int) -> dict:
    """Para um deck meu: que cartas tenho, quais faltam, e o custo do que falta.

    A contagem é por NOME (qualquer impressão serve para jogar) e só usa
    exemplares marcados como 'player'.
    """
    deck = con.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
    if deck is None:
        raise LookupError(f"Deck {deck_id} não existe")

    rows = con.execute(
        "SELECT card_name, quantity, board FROM deck_cards WHERE deck_id = ?",
        (deck_id,),
    ).fetchall()

    owned = owned_playable(con, for_deck_id=deck_id)
    used: dict[str, int] = {}
    have, missing = [], []

    # main primeiro: se uma carta está no main e no side, o main tem prioridade
    for r in sorted(rows, key=lambda r: r["board"] != "main"):
        name, need, board = r["card_name"], r["quantity"], r["board"]
        available = owned.get(name, 0) - used.get(name, 0)
        got = max(0, min(need, available))
        used[name] = used.get(name, 0) + got
        entry = {"card_name": name, "board": board, "need": need, "have": got,
                 "missing": need - got}
        (have if got == need else missing).append(entry)

    for m in missing:
        unit = cheapest_price(con, m["card_name"])
        m["unit_price"] = unit
        m["cost"] = round((unit or 0) * m["missing"], 2)

    return {
        "deck": dict(deck),
        "complete": not missing,
        "have": have,
        "missing": sorted(missing, key=lambda m: -(m["cost"] or 0)),
        "missing_cards": sum(m["missing"] for m in missing),
        "missing_cost": round(sum(m["cost"] or 0 for m in missing), 2),
    }


def wantlist(con: sqlite3.Connection, deck_ids: list[int] | None = None) -> list[dict]:
    """Wantlist agregada. Sem argumentos, cobre todos os decks.

    Agrega por carta: se três decks precisam de 4 Fatal Push, a wantlist pede
    4 (partilhadas), não 12 — muda `shared=False` se quiseres cópias dedicadas.
    """
    if deck_ids is None:
        deck_ids = [r["id"] for r in con.execute("SELECT id FROM decks").fetchall()]

    peak: dict[str, int] = {}
    for did in deck_ids:
        st = deck_status(con, did)
        per_deck: dict[str, int] = {}
        for m in st["missing"]:
            per_deck[m["card_name"]] = per_deck.get(m["card_name"], 0) + m["missing"]
        for name, qty in per_deck.items():
            peak[name] = max(peak.get(name, 0), qty)

    out = []
    for name, qty in peak.items():
        unit = cheapest_price(con, name)
        out.append({
            "card_name": name, "quantity": qty, "unit_price": unit,
            "cost": round((unit or 0) * qty, 2),
        })
    return sorted(out, key=lambda w: -w["cost"])


def archetype_gap(
    con: sqlite3.Connection, archetype_id: int, include_flex: bool = False
) -> list[dict]:
    """O que me falta para montar o CORE de um arquétipo do metagame.

    É a ponte entre a análise do metagame e a coleção: pega no núcleo
    calculado (as cartas que se levam sempre) e diz o que ainda não tenho.
    """
    roles = con.execute(
        """SELECT card_name, board, core_copies, flex_copies, inclusion_rate, role
             FROM card_roles
            WHERE archetype_id = ?
              AND window_end = (SELECT MAX(window_end) FROM card_roles
                                 WHERE archetype_id = ?)
            ORDER BY board, inclusion_rate DESC""",
        (archetype_id, archetype_id),
    ).fetchall()

    owned = owned_playable(con)
    out = []
    for r in roles:
        need = r["core_copies"]
        if include_flex and r["role"] in ("core", "flex"):
            need = max(need, round(r["core_copies"] + r["flex_copies"]))
        if need < 1:
            continue
        have = owned.get(r["card_name"], 0)
        if have >= need:
            continue
        unit = cheapest_price(con, r["card_name"])
        out.append({
            "card_name": r["card_name"], "board": r["board"], "role": r["role"],
            "need": need, "have": have, "missing": need - have,
            "inclusion_rate": r["inclusion_rate"],
            "unit_price": unit, "cost": round((unit or 0) * (need - have), 2),
        })
    return sorted(out, key=lambda x: -(x["cost"] or 0))
