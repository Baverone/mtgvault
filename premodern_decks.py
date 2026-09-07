"""Listas de CONSENSO dos arquétipos de Premodern que o André pediu.

O Premodern não tem página de metagame (saiu de `formatos_metagame` em
2026-09-07): o André não quer um top-10 de Premodern, quer o consenso de dois
arquétipos concretos — "Preciso de consenso para lista de alguns decks de
Premodern: Replenish, Enchantress". O Stiflenought fica de fora de propósito:
esse segue a lista do Luffy (`my_decks.FOLLOWED_PLAYERS`).

Como se agrupa: NÃO pelo clustering (`analysis.rebuild_archetypes`), que junta o
que se parece — e em Premodern a Enchantress joga 96% de Replenish, por isso o
clustering colava os dois. Agrupa-se pelas regras de `archetype_rules.json`
(`tagging`), que separam por EXCLUSÃO. A lista sai do `stock.stock_from_lists`,
o mesmo cálculo da lista padrão de qualquer outro arquétipo.

O deck vai para `decks`/`deck_cards` com o sufixo "(consenso)" no nome, para
nunca se confundir com um deck montado: os alvos são decks POR MONTAR e não
podem reservar cartas da coleção (ver `meta_coverage.owned_available`).
"""
from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import sources, stock, tagging  # noqa: E402

FMT = "premodern"
SUFIXO = " (consenso)"
ALVOS_DEFAULT = ["UW Replenish", "Enchantress"]
MIN_LISTS = 5      # o mesmo mínimo do analysis.rebuild_roles


def alvos() -> list[str]:
    """Arquétipos-alvo, de colecao_config.json -> premodern_arquetipos_alvo."""
    v = sources.config().get("premodern_arquetipos_alvo")
    return list(ALVOS_DEFAULT if v is None else v)


def _list_ids(con: sqlite3.Connection, tag: str) -> list[int]:
    """Listas de Premodern com esta etiqueta que CONTAM para o metagame."""
    con.execute(tagging.DDL)
    conta, cp = sources.counting_sql(FMT, "d")
    return [r[0] for r in con.execute(
        f"""SELECT d.id FROM decklists d JOIN decklist_tags t ON t.decklist_id = d.id
             WHERE d.format = ? AND t.name = ? AND {conta}""", (FMT, tag, *cp))]


def _boards(con: sqlite3.Connection, ids: list[int]) -> tuple[list[dict], list[dict]]:
    """As listas em memória: ([{carta: qty} do main], [... do side])."""
    main: dict[int, dict[str, int]] = defaultdict(dict)
    side: dict[int, dict[str, int]] = defaultdict(dict)
    ph = ",".join("?" * len(ids))
    for r in con.execute(
            f"""SELECT decklist_id i, card_name nm, quantity q, board b
                  FROM decklist_cards WHERE decklist_id IN ({ph})""", ids):
        (side if r["b"] == "side" else main)[r["i"]][r["nm"]] = r["q"]
    return ([main[i] for i in ids if main.get(i)],
            [side[i] for i in ids if side.get(i)])


def consensus(con: sqlite3.Connection, tag: str) -> dict | None:
    """Lista de consenso de um arquétipo-alvo, ou None se a amostra for pequena.
    Acrescenta `players` (jogadores distintos) — com 20 listas de 8 jogadores o
    "consenso" é mais a lista de meia dúzia de pessoas do que a do formato."""
    ids = _list_ids(con, tag)
    if len(ids) < MIN_LISTS:
        return None
    sl = stock.stock_from_lists(FMT, *_boards(con, ids))
    ph = ",".join("?" * len(ids))
    sl["players"] = con.execute(
        f"SELECT COUNT(DISTINCT lower(player)) c FROM decklists WHERE id IN ({ph})",
        ids).fetchone()["c"]
    sl["tag"] = tag
    return sl


def refresh(con: sqlite3.Connection) -> str:
    out = []
    for tag in alvos():
        sl = consensus(con, tag)
        if not sl:
            out.append(f"{tag}: listas insuficientes")
            continue
        name = tag + SUFIXO
        con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?, ?)", (name, FMT))
        did = con.execute("SELECT id FROM decks WHERE name = ? AND format = ?",
                          (name, FMT)).fetchone()["id"]
        con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
        for board in ("main", "side"):
            for c in sl[board]:
                con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                            "VALUES (?,?,?,?)", (did, c["card_name"], c["quantity"], board))
        con.execute("UPDATE decks SET notes = ? WHERE id = ?",
                    (f"consenso de {sl['n']} listas ({sl['players']} jogadores) "
                     f"— main {sl['main_count']}/{sl['main_target']}, "
                     f"side {sl['side_count']}/{sl['side_target']}", did))
        out.append(f"{name}: {sl['main_count']}+{sl['side_count']} cartas "
                   f"de {sl['n']} listas ({sl['players']} jogadores)")
    con.commit()
    return "; ".join(out) or "sem alvos configurados"


def main():
    from mtgvault import db
    with db.session() as con:
        print(refresh(con))


if __name__ == "__main__":
    main()
