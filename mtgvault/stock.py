"""Listas padrão ("stock lists") e quanto de cada deck tenho na coleção.

Para os baralhos que não indicaste explicitamente, construímos a lista de
consenso a partir do que o metagame anda mesmo a jogar.

COMO SE CONSTRÓI A LISTA PADRÃO
    1. cada carta entra com as suas `core_copies` (o que se leva sempre)
    2. os lugares que sobram são preenchidos por ordem de probabilidade:
       a k-ésima cópia de uma carta vale P(cópias >= k) sobre TODAS as listas
    3. pára quando o deck estiver cheio (60 + 15, ou 100 em Commander)

É literalmente "a lista mais provável", não uma média inventada — cada slot é
ocupado pela cópia com maior probabilidade de estar lá.
"""
from __future__ import annotations

import json
import sqlite3

from .collection import owned_playable
from .wantlist import cheapest_price

SINGLETON_FORMATS = {"duel-commander", "cedh", "commander", "edh"}


def deck_size(fmt: str) -> tuple[int, int]:
    """(mainboard, sideboard) esperados para o formato."""
    if fmt.lower() in SINGLETON_FORMATS:
        return 100, 0
    return 60, 15


def _candidates(con, archetype_id: int, board: str):
    """Cada cópia possível com a sua probabilidade, já ordenada."""
    rows = con.execute(
        """SELECT card_name, core_copies, inclusion_rate, dist
             FROM card_roles
            WHERE archetype_id = ? AND board = ?
              AND window_end = (SELECT MAX(window_end) FROM card_roles
                                 WHERE archetype_id = ?)""",
        (archetype_id, board, archetype_id),
    ).fetchall()

    slots = []
    for r in rows:
        dist = {int(k): v for k, v in json.loads(r["dist"]).items()}
        incl = r["inclusion_rate"]
        for k in range(1, max(dist) + 1 if dist else 1):
            # P(cópias >= k) sobre todas as listas do arquétipo
            p = incl * sum(v for q, v in dist.items() if q >= k)
            slots.append({"card_name": r["card_name"], "copy": k, "p": p,
                          "core": k <= r["core_copies"]})
    slots.sort(key=lambda s: (-s["p"], s["card_name"], s["copy"]))
    return slots


def stock_list(con: sqlite3.Connection, archetype_id: int) -> dict:
    """Constrói a lista padrão de um arquétipo."""
    arch = con.execute(
        "SELECT * FROM archetypes WHERE id = ?", (archetype_id,)
    ).fetchone()
    if arch is None:
        raise LookupError(f"Arquétipo {archetype_id} não existe")

    main_target, side_target = deck_size(arch["format"])
    out = {"archetype": dict(arch), "main": [], "side": []}

    for board, target in (("main", main_target), ("side", side_target)):
        if target == 0:
            continue
        counted: dict[str, int] = {}
        total = 0
        for slot in _candidates(con, archetype_id, board):
            if total >= target:
                break
            if slot["p"] < 0.20:          # abaixo disto já não é a lista padrão
                break
            counted[slot["card_name"]] = counted.get(slot["card_name"], 0) + 1
            total += 1
        out[board] = [
            {"card_name": n, "quantity": q}
            for n, q in sorted(counted.items(), key=lambda x: (-x[1], x[0]))
        ]
        out[f"{board}_count"] = total
        out[f"{board}_target"] = target
    return out


# ---------------------------------------------------------------------------
# Cobertura
# ---------------------------------------------------------------------------
def coverage(con: sqlite3.Connection, cards: list[tuple[str, str, int]],
             price: bool = True) -> dict:
    """Quanto de uma lista tenho na coleção.

    `cards` = [(board, nome, quantidade), ...]
    Só conta exemplares 'player'. Uma carta partilhada entre main e side
    é atribuída primeiro ao main.
    """
    owned = owned_playable(con)
    used: dict[str, int] = {}
    have_rows, missing_rows = [], []
    total_needed = total_have = 0

    for board, name, need in sorted(cards, key=lambda c: c[0] != "main"):
        avail = owned.get(name, 0) - used.get(name, 0)
        got = max(0, min(need, avail))
        used[name] = used.get(name, 0) + got
        total_needed += need
        total_have += got
        row = {"board": board, "card_name": name, "need": need,
               "have": got, "missing": need - got}
        if got >= need:
            have_rows.append(row)
        else:
            if price:
                unit = cheapest_price(con, name)
                row["unit_price"] = unit
                row["cost"] = round((unit or 0) * row["missing"], 2)
            missing_rows.append(row)

    distinct = {(b, n) for b, n, _ in cards}
    distinct_have = len({(r["board"], r["card_name"]) for r in have_rows})

    return {
        "cards_needed": total_needed,
        "cards_have": total_have,
        "cards_missing": total_needed - total_have,
        # % sobre o total de cartas do deck (contando cópias)
        "pct": round(100.0 * total_have / total_needed, 1) if total_needed else 0.0,
        # % sobre cartas distintas (playsets completos)
        "pct_distinct": round(100.0 * distinct_have / len(distinct), 1) if distinct else 0.0,
        "cost": round(sum(r.get("cost") or 0 for r in missing_rows), 2),
        "have": have_rows,
        "missing": sorted(missing_rows, key=lambda r: -(r.get("cost") or 0)),
    }


def coverage_of_archetype(con: sqlite3.Connection, archetype_id: int) -> dict:
    sl = stock_list(con, archetype_id)
    cards = [("main", c["card_name"], c["quantity"]) for c in sl["main"]]
    cards += [("side", c["card_name"], c["quantity"]) for c in sl["side"]]
    cov = coverage(con, cards)
    cov["archetype"] = sl["archetype"]
    cov["stock_list"] = sl
    return cov


def format_report(con: sqlite3.Connection, fmt: str, min_lists: int = 5,
                  exclude_watched: bool = True) -> list[dict]:
    """Ranking de todos os arquétipos do formato pela % que já tenho.

    Por omissão salta os arquétipos que já estás a vigiar explicitamente —
    esses tens a lista real, não precisas da lista padrão.
    """
    watched_ids = set()
    if exclude_watched:
        watched_ids = {
            int(r["key"]) for r in con.execute(
                "SELECT key FROM watched WHERE kind = 'archetype' AND active = 1")
            if str(r["key"]).isdigit()
        }

    rows = con.execute(
        """SELECT a.id, a.label, COUNT(d.id) AS n_lists
             FROM archetypes a JOIN decklists d ON d.archetype_id = a.id
            WHERE a.format = ?
            GROUP BY a.id HAVING n_lists >= ?
            ORDER BY n_lists DESC""",
        (fmt.lower(), min_lists),
    ).fetchall()

    out = []
    for r in rows:
        if r["id"] in watched_ids:
            continue
        try:
            cov = coverage_of_archetype(con, r["id"])
        except LookupError:
            continue
        out.append({
            "archetype_id": r["id"], "label": r["label"], "n_lists": r["n_lists"],
            "pct": cov["pct"], "have": cov["cards_have"],
            "missing": cov["cards_missing"], "cost": cov["cost"],
        })
    return sorted(out, key=lambda x: -x["pct"])
