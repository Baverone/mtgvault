"""Mantém atualizadas as listas dos decks que o André segue.

Todos os dias (no job diário) procura a decklist mais recente do metagame para
cada deck seguido — identificada pelas cartas-assinatura — e substitui a lista
guardada em `deck_cards`. Assim a % que ele já tem e a wantlist acompanham
sempre a versão atual do deck. NÃO inventa nada: usa só as decklists reais que
o harvest já recolheu (mtgo/mtgtop8).

Só reescreve quando a decklist de origem muda (compara o id na nota), para não
sujar o `vault.db` com diffs todos os dias sem necessidade.
"""
from __future__ import annotations

import sqlite3

# (nome do deck, formato, cartas-assinatura que a lista TEM de conter)
FOLLOWED = [
    ("Izzet Affinity (Kappa Cannoneer)", "modern", ["Mox Opal", "Kappa Cannoneer"]),
    ("Grinding Station", "modern", ["Mox Opal", "Grinding Station"]),
    ("Cori-Steel Cutter", "modern", ["Mox Opal", "Cori-Steel Cutter"]),
    # Standard. Jeskai Lessons = "Lesson" + a revelação branca que o separa do
    # Izzet Lessons. (4c Control ainda não sai limpo do harvest — segue-se por
    # lista de referência quando o André der uma, ou quando houver mais dados.)
    ("Jeskai Lessons", "standard", ["Firebending Lesson", "Jeskai Revelation"]),
]

# Decks seguidos por JOGADOR de MTGO (a lista mais recente dele nesse formato),
# em vez de por assinatura. O André escolheu estes jogadores como referência:
# (nome do deck, formato, jogador)
FOLLOWED_PLAYERS = [
    ("Legacy (Harry1232)", "legacy", "Harry1232"),
    ("Stiflenought (Luffy)", "premodern", "LuffyDoChapeuDePalha"),
    ("Pioneer (Luffy)", "pioneer", "LuffyDoChapeuDePalha"),
]

MIN_MAIN = 55  # ignora listas truncadas/incompletas


def _latest(con: sqlite3.Connection, fmt: str, cards: list[str]):
    """Decklist mais recente do formato que contém TODAS as cartas-assinatura e
    tem um mainboard completo."""
    ph = ",".join("?" * len(cards))
    return con.execute(
        f"""SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
              WHERE dl.format = ?
                AND (SELECT COUNT(DISTINCT dc.card_name) FROM decklist_cards dc
                       WHERE dc.decklist_id = dl.id AND dc.card_name IN ({ph})) = ?
                AND (SELECT COALESCE(SUM(dc2.quantity), 0) FROM decklist_cards dc2
                       WHERE dc2.decklist_id = dl.id AND dc2.board = 'main') >= ?
              ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1""",
        [fmt] + cards + [len(cards), MIN_MAIN]).fetchone()


def _latest_player(con: sqlite3.Connection, fmt: str, player: str):
    """Decklist mais recente de um jogador específico nesse formato."""
    return con.execute(
        """SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
             WHERE dl.format = ? AND dl.player = ?
               AND (SELECT COALESCE(SUM(dc.quantity), 0) FROM decklist_cards dc
                      WHERE dc.decklist_id = dl.id AND dc.board = 'main') >= ?
             ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1""",
        (fmt, player, MIN_MAIN)).fetchone()


def _store(con: sqlite3.Connection, name: str, fmt: str, dl, out: list):
    """Grava/atualiza a decklist `dl` como deck `name`, só se a origem mudou."""
    con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?, ?)", (name, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ? AND format = ?",
                      (name, fmt)).fetchone()["id"]
    note = f"auto: {dl['source']} {dl['player'] or '?'} {dl['event_date']} (#{dl['id']})"
    cur = con.execute("SELECT notes FROM decks WHERE id = ?", (did,)).fetchone()["notes"]
    if cur == note:
        out.append(f"{name}: já atual ({dl['event_date']})")
        return
    con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
    for r in con.execute("SELECT card_name, quantity, board FROM decklist_cards "
                         "WHERE decklist_id = ?", (dl["id"],)):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, ?, ?, ?)", (did, r["card_name"], r["quantity"], r["board"]))
    con.execute("UPDATE decks SET notes = ? WHERE id = ?", (note, did))
    out.append(f"{name}: atualizado -> {dl['event_date']} {dl['player'] or '?'}")


def refresh(con: sqlite3.Connection) -> str:
    out = []
    for name, fmt, cards in FOLLOWED:
        dl = _latest(con, fmt, cards)
        if dl:
            _store(con, name, fmt, dl, out)
        else:
            out.append(f"{name}: sem lista")
    for name, fmt, player in FOLLOWED_PLAYERS:
        dl = _latest_player(con, fmt, player)
        if dl:
            _store(con, name, fmt, dl, out)
        else:
            out.append(f"{name}: sem lista de {player}")
    con.commit()
    return "; ".join(out)


if __name__ == "__main__":
    import os
    from pathlib import Path
    os.environ.setdefault("MTGVAULT_HOME", str(Path(__file__).resolve().parent / "data"))
    from mtgvault import db
    with db.session() as con:
        print(refresh(con))
