"""Decks de comandante seguidos por CONSENSO, em CAMADAS.

Ao contrário dos de Modern (my_decks.py, que copiam uma decklist específica),
estes reconstroem a referência a partir das listas do formato já recolhidas,
por inclusão (em quantas listas do comandante cada carta aparece):

  • NÚCLEO  (>= 50%)  -> é o deck; grava em decks/deck_cards (board 'main').
  • FLEX    (25–50%)  -> opções para as vagas restantes (só para mostrar).
  • TECH    (15–25%)  -> tech (só para mostrar).

Singleton (Duel Commander). Não inventa nada: usa só as decklists reais.
"""
from __future__ import annotations

import os
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

# (nome do deck, formato, comandante)
# O Cloud (Duel Commander) deixou de ser gerado por consenso: o André escolheu a
# lista do McWinSauce (1º no MTGO DC Challenge 2026-08-24) como referência, gravada
# à mão em decks/deck_cards. O consenso continua calculado por `tiers()` (secção de
# camadas em colecao_cor), mas `refresh()` já NÃO sobrescreve o deck_cards do Cloud.
CONSENSUS = []
MIN_LISTS = 10           # não construir um "consenso" de meia dúzia de listas
CORE, FLEX, TECH = 0.50, 0.25, 0.15   # limiares das três camadas


def _inclusion(con, fmt, commander):
    """(Counter carta->nº de listas, nº de listas do comandante)."""
    ids = [r[0] for r in con.execute(
        """SELECT DISTINCT dl.id FROM decklists dl
             JOIN decklist_cards dc ON dc.decklist_id = dl.id
            WHERE dl.format = ? AND dc.card_name = ?""", (fmt, commander))]
    if len(ids) < MIN_LISTS:
        return None, len(ids)
    marks = ",".join("?" for _ in ids)
    inc = Counter()
    for r in con.execute(
        f"""SELECT card_name nm, COUNT(DISTINCT decklist_id) c FROM decklist_cards
             WHERE decklist_id IN ({marks}) GROUP BY card_name""", ids):
        inc[r["nm"]] = r["c"]
    return inc, len(ids)


def _color_map(con, names):
    """nome -> conjunto de cores da identidade (WUBRG)."""
    out = {}
    names = list(names)
    for i in range(0, len(names), 400):
        ch = names[i:i + 400]
        ph = ",".join("?" for _ in ch)
        for r in con.execute(f"SELECT name nm, color_identity ci FROM cards "
                             f"WHERE name IN ({ph}) AND digital = 0 GROUP BY name", ch):
            out[r["nm"]] = set(r["ci"] or "")
    return out


def tiers(con, fmt, commander):
    """{'core':[(nm,pct)], 'flex':[...], 'tech':[...], 'n':N, 'ci':str} ou (None, n).
    Cada camada ordenada por inclusão. FILTRA pela identidade de cor do comandante
    (regra de Commander): uma carta só entra se a cor dela couber na do comandante —
    tira as off-color que vêm das versões com partner misturadas nas listas."""
    inc, n = _inclusion(con, fmt, commander)
    if not inc:
        return None, n
    row = con.execute("SELECT color_identity ci FROM cards WHERE name = ? AND digital = 0 "
                      "LIMIT 1", (commander,)).fetchone()
    cci = set(row["ci"] or "") if row else set()
    cmap = _color_map(con, inc)

    def legal(nm):
        return cmap.get(nm.split(" // ")[0], set()) <= cci

    def band(lo, hi):
        return sorted(((nm, round(100 * c / n)) for nm, c in inc.items()
                       if lo <= c / n < hi and legal(nm)), key=lambda x: -x[1])
    core = sorted(((nm, round(100 * c / n)) for nm, c in inc.items()
                   if c / n >= CORE and legal(nm)), key=lambda x: -x[1])
    return {"core": core, "flex": band(FLEX, CORE), "tech": band(TECH, FLEX),
            "n": n, "ci": "".join(sorted(cci))}, n


def refresh(con: sqlite3.Connection) -> str:
    out = []
    for name, fmt, commander in CONSENSUS:
        t, n = tiers(con, fmt, commander)
        if not t:
            out.append(f"{name}: listas insuficientes ({n})")
            continue
        con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?, ?)", (name, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ? AND format = ?",
                          (name, fmt)).fetchone()["id"]
        con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
        # O deck = o NÚCLEO (board 'main'). Flex/tech não se gravam — são opções
        # calculadas na vista (commander_decks.tiers) quando é preciso mostrá-las.
        for nm, _pct in t["core"]:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?, ?, 1, 'main')", (did, nm))
        con.execute("UPDATE decks SET notes = ? WHERE id = ?",
                    (f"consenso de {n} listas ({commander}) — "
                     f"núcleo {len(t['core'])}, flex {len(t['flex'])}, tech {len(t['tech'])}", did))
        out.append(f"{name}: núcleo {len(t['core'])} · flex {len(t['flex'])} · "
                   f"tech {len(t['tech'])} (de {n} listas)")
    return "; ".join(out)


def main():
    from mtgvault import db
    with db.session() as con:
        print(refresh(con))


if __name__ == "__main__":
    main()
