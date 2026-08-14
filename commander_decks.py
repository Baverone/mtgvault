"""Decks de comandante seguidos por CONSENSO.

Ao contrário dos de Modern (my_decks.py, que copiam uma decklist específica),
estes reconstroem a lista de referência a partir das listas do formato já
recolhidas: cada carta que aparece em >= LIMIAR das listas do comandante entra
(singleton, 1 cópia). Grava em decks/deck_cards para persistir e alimentar a
cobertura/wantlist. Corre no job diário, por isso acompanha o metagame.

Não inventa nada: usa só as decklists reais recolhidas (mtgtop8/MTGO).
"""
from __future__ import annotations

import os
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

# (nome do deck, formato, comandante, limiar de inclusão para entrar no consenso)
CONSENSUS = [
    ("Cloud (Duel Commander)", "duel-commander", "Cloud, Midgar Mercenary", 0.40),
]
MIN_LISTS = 10   # não construir um "consenso" de meia dúzia de listas


def _consensus(con, fmt, commander, threshold):
    """Cartas que aparecem em >= threshold das listas do comandante, ordenadas
    por inclusão (mais consensual primeiro). Singleton (Duel Commander)."""
    ids = [r[0] for r in con.execute(
        """SELECT DISTINCT dl.id FROM decklists dl
             JOIN decklist_cards dc ON dc.decklist_id = dl.id
            WHERE dl.format = ? AND dc.card_name = ?""", (fmt, commander))]
    if len(ids) < MIN_LISTS:
        return None, len(ids)
    marks = ",".join("?" for _ in ids)
    n = len(ids)
    inc = Counter()
    for r in con.execute(
        f"""SELECT card_name nm, COUNT(DISTINCT decklist_id) c FROM decklist_cards
             WHERE decklist_id IN ({marks}) GROUP BY card_name""", ids):
        inc[r["nm"]] = r["c"]
    cards = sorted((nm for nm, c in inc.items() if c / n >= threshold),
                   key=lambda nm: -inc[nm])
    return cards, n


def refresh(con: sqlite3.Connection) -> str:
    out = []
    for name, fmt, commander, threshold in CONSENSUS:
        cards, n = _consensus(con, fmt, commander, threshold)
        if not cards:
            out.append(f"{name}: listas insuficientes ({n})")
            continue
        con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?, ?)", (name, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ? AND format = ?",
                          (name, fmt)).fetchone()["id"]
        con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
        for nm in cards:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?, ?, 1, 'main')", (did, nm))
        con.execute("UPDATE decks SET notes = ? WHERE id = ?",
                    (f"consenso de {n} listas ({commander})", did))
        out.append(f"{name}: {len(cards)} cartas (consenso de {n} listas)")
    return "; ".join(out)


def main():
    from mtgvault import db
    with db.session() as con:
        print(refresh(con))


if __name__ == "__main__":
    main()
