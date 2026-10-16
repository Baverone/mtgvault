"""Mantém atualizadas as listas dos decks que o André segue.

Todos os dias (no job diário) procura a decklist mais recente do metagame para
cada deck seguido — identificada pelas cartas-assinatura — e substitui a lista
guardada em `deck_cards`. Assim a % que ele já tem e a wantlist acompanham
sempre a versão atual do deck. NÃO inventa nada: usa só as decklists reais que
o harvest já recolheu (mtgo/mtgtop8).

Só reescreve quando a decklist de origem muda (compara o id na nota) ou quando
a MESMA lista foi relida com outro conteúdo, para não sujar o `vault.db` com
diffs todos os dias sem necessidade.

**Cada troca fica gravada em `deck_lista_trocas` (2026-10-16)**, com as duas
listas inteiras: *"todos os dias quero que mostres aqui ao lado as alterações
ocorridas nos decks"* (André). Até aí as `deck_cards` eram substituídas e o que
entrou e saiu perdia-se — o `job_runs` só dizia *"atualizado -> <data>
<jogador>"*. Quem lê o histórico é o `mtgvault/painel.py`.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date

from mtgvault import sources

# (nome do deck, formato, cartas-assinatura que a lista TEM de conter)
FOLLOWED = [
    ("Izzet Affinity (Kappa Cannoneer)", "modern", ["Mox Opal", "Kappa Cannoneer"]),
    # Grinding Station: Mox Opal + Grinding Station apanha DOIS decks (medido a
    # 2026-10-16, listas de Modern desde 01/10 com as duas cartas): o de Emry +
    # Sewer-veillance Cam (10 listas — CesarMerjan 05/10, Comrac 11/10,
    # bbotonline 12/10, howa 15/10) e uma variante com Kethis, Malevolent Rumble
    # e Starting Town (3). A 14/10 a mais recente era a do Kethis (Cachorrowo,
    # 12/10) e a lista de referência saltou de deck; a 16/10 voltou — 84 cartas
    # trocadas de cada vez. O "!" fixa o deck que ele seguia; tirá-lo é uma linha.
    ("Grinding Station", "modern", ["Mox Opal", "Grinding Station", "!Kethis, the Hidden Hand"]),
    ("Cori-Steel Cutter", "modern", ["Mox Opal", "Cori-Steel Cutter"]),
    # Pioneer: o André segue o arquétipo Greasefang (não um jogador).
    ("Greasefang", "pioneer", ["Greasefang, Okiba Boss"]),
]

# Decks que DEIXARAM de se seguir. Não se apagam: as linhas na `decks` ficam
# (com a última lista e a nota), só não voltam a ser atualizadas nem aparecem no
# painel. Repor é devolver a entrada ao `FOLLOWED`.
SAIU = {
    # Standard (André, 13/10/2026): "Standard vou ficar sem deck, pois em Janeiro
    # ha rotacao no formato ... logo podemos eliminar esse deck". A ordem desse
    # dia tirou a caixa `standard` (Bant Airbend) e esqueceu estes dois, que
    # continuaram a ser seguidos até 16/10 (Jeskai Lessons = WUR com Lessons e
    # Revelation, SEM preto; 4c Control = o mesmo shell com Blood Crypt).
    "Jeskai Lessons": ("standard", ["Firebending Lesson", "Jeskai Revelation", "!Blood Crypt"],
                       "2026-10-16", "Standard eliminado a 13/10 (rotacao de Janeiro)"),
    "4c Control": ("standard", ["Jeskai Revelation", "Blood Crypt"],
                   "2026-10-16", "Standard eliminado a 13/10 (rotacao de Janeiro)"),
}

# Decks seguidos por JOGADOR + COMANDANTE: a lista mais recente desse jogador no
# formato que CONTÉM aquele comandante. Ex.: Cloud DC = a lista de Cloud mais
# recente do McWinSauce ("mantém a do McWinSauce, com o mesmo comandante, vai
# atualizando" — André, 2026-08-31).
FOLLOWED_PLAYER_DECK = [
    ("Cloud (Duel Commander)", "duel-commander", "McWinSauce", ["Cloud, Midgar Mercenary"]),
]

# Decks seguidos por JOGADOR de MTGO (a lista mais recente dele nesse formato),
# em vez de por assinatura. O André escolheu estes jogadores como referência:
# (nome do deck, formato, jogador)
FOLLOWED_PLAYERS = [
    # Legacy esquecido por agora (André, 2026-08-31) — Harry1232 fora do harvest.
    ("Stiflenought (Luffy)", "premodern", "LuffyDoChapeuDePalha"),
    ("Stiflenought (Spock)", "premodern", "SpockVidaLoka"),
]

MIN_MAIN = 55  # ignora listas truncadas/incompletas

# A nota que o `_store` escreve na `decks`: "auto: <fonte> <jogador> <data> (#id)".
# O jogador pode ter espaços (o mtgtop8 traz nomes reais).
RE_NOTA = re.compile(r"^auto: (\S+) (.*) (\d{4}-\d{2}-\d{2}) \(#(\d+)\)$")


def _conta(fmt):
    """Só se segue uma lista que CONTE para o metagame (regra do André,
    2026-09-07): não faz sentido copiar para `deck_cards` um 5-0 de liga que o
    top-10 e a cobertura não reconhecem. Devolve (SQL, params) para o WHERE.

    **`consenso=False`: SEGUIR UMA LISTA NÃO É UM CONSENSO** (2026-10-03). A
    janela do consenso (`sources.consenso_desde`) existe para *"como é que este
    arquétipo se joga agora"*, e aqui já se pede a lista MAIS RECENTE — o corte
    não a torna mais recente, só pode fazê-la desaparecer. Medido no dia em que
    a janela entrou: com o corte a 29/09, o *Grinding Station* (lista de 28/09) e
    o *Jeskai Lessons* (27/09) ficavam sem lista nenhuma, e o `refresh` dizia
    *"sem lista"* deixando a de ontem na base — ou seja, o corte não trazia um
    número novo e tirava a resposta a duas perguntas. Os decks que ALIMENTAM
    caixas sobrevivem aos dois lados (Greasefang 01/10, Stiflenought do Luffy
    01/10), por isso isto não é o que protege as caixas: é só honestidade sobre
    o que esta função faz.
    """
    return sources.counting_sql(fmt, "dl", consenso=False)


def _latest(con: sqlite3.Connection, fmt: str, cards: list[str]):
    """Decklist mais recente do formato que contém TODAS as cartas-assinatura
    (e NENHUMA das prefixadas com "!") e tem um mainboard completo. As exclusões
    servem para separar variantes que partilham o núcleo (ex.: Jeskai Lessons vs
    4c Control, que só difere por ter Blood Crypt/preto)."""
    inc = [c for c in cards if not c.startswith("!")]
    exc = [c[1:] for c in cards if c.startswith("!")]
    ph = ",".join("?" * len(inc))
    conta, cp = _conta(fmt)
    q = (f"""SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
              WHERE dl.format = ? AND {conta}
                AND (SELECT COUNT(DISTINCT dc.card_name) FROM decklist_cards dc
                       WHERE dc.decklist_id = dl.id AND dc.card_name IN ({ph})) = ?
                AND (SELECT COALESCE(SUM(dc2.quantity), 0) FROM decklist_cards dc2
                       WHERE dc2.decklist_id = dl.id AND dc2.board = 'main') >= ?""")
    params = [fmt] + cp + inc + [len(inc), MIN_MAIN]
    if exc:
        eph = ",".join("?" * len(exc))
        q += (f" AND NOT EXISTS (SELECT 1 FROM decklist_cards de "
              f"WHERE de.decklist_id = dl.id AND de.card_name IN ({eph}))")
        params += exc
    q += " ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1"
    return con.execute(q, params).fetchone()


def _latest_player(con: sqlite3.Connection, fmt: str, player: str):
    """Decklist mais recente de um jogador específico nesse formato."""
    conta, cp = _conta(fmt)
    return con.execute(
        f"""SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
             WHERE dl.format = ? AND dl.player = ? AND {conta}
               AND (SELECT COALESCE(SUM(dc.quantity), 0) FROM decklist_cards dc
                      WHERE dc.decklist_id = dl.id AND dc.board = 'main') >= ?
             ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1""",
        [fmt, player] + cp + [MIN_MAIN]).fetchone()


def _latest_player_deck(con: sqlite3.Connection, fmt: str, player: str, cards: list[str]):
    """Lista mais recente de `player` nesse formato que CONTÉM todas as `cards`
    (ex.: o comandante) — para seguir um deck específico de um jogador."""
    ph = ",".join("?" * len(cards))
    conta, cp = _conta(fmt)
    return con.execute(
        f"""SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
              WHERE dl.format = ? AND dl.player = ? AND {conta}
                AND (SELECT COUNT(DISTINCT dc.card_name) FROM decklist_cards dc
                       WHERE dc.decklist_id = dl.id AND dc.card_name IN ({ph})) = ?
              ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1""",
        [fmt, player] + cp + cards + [len(cards)]).fetchone()


def seguidos() -> list[dict]:
    """Os decks seguidos, numa lista só: nome, formato, como se escolhe a lista
    e as cartas que lhe dão o nome (a assinatura sem as exclusões). É o que o
    `refresh` percorre e o que o painel mostra — uma lista só, para os dois não
    discordarem sobre quem é seguido."""
    out = []
    for name, fmt, cards in FOLLOWED:
        out.append({"deck": name, "formato": fmt, "como": "assinatura",
                    "assinatura": [c for c in cards if not c.startswith("!")],
                    "procura": lambda con, f=fmt, c=cards: _latest(con, f, c),
                    "falta": "sem lista"})
    for name, fmt, player in FOLLOWED_PLAYERS:
        out.append({"deck": name, "formato": fmt, "como": "jogador", "assinatura": [],
                    "procura": lambda con, f=fmt, p=player: _latest_player(con, f, p),
                    "falta": f"sem lista de {player}"})
    for name, fmt, player, cards in FOLLOWED_PLAYER_DECK:
        out.append({"deck": name, "formato": fmt, "como": "jogador+cartas",
                    "assinatura": list(cards),
                    "procura": lambda con, f=fmt, p=player, c=cards: _latest_player_deck(con, f, p, c),
                    "falta": f"sem lista de {player} com {cards}"})
    return out


def ler_nota(nota: str | None) -> dict:
    """{fonte, jogador, data, decklist_id} da nota de um deck, ou {} se não for
    uma nota do `_store`."""
    m = RE_NOTA.match(nota or "")
    if not m:
        return {}
    return {"fonte": m.group(1), "jogador": m.group(2), "data": m.group(3),
            "decklist_id": int(m.group(4))}


def _cartas_do_deck(con, did) -> list[list]:
    return [[r["board"], r["card_name"], r["quantity"]] for r in con.execute(
        "SELECT board, card_name, quantity FROM deck_cards WHERE deck_id = ? "
        "ORDER BY board, card_name", (did,))]


def _cartas_da_lista(con, lid) -> list[list]:
    return [[r["board"], r["card_name"], r["quantity"]] for r in con.execute(
        "SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id = ? "
        "ORDER BY board, card_name", (lid,))]


def _store(con: sqlite3.Connection, name: str, fmt: str, dl, out: list,
           hoje: str | None = None):
    """Grava/atualiza a decklist `dl` como deck `name`, só se a origem mudou ou
    se a mesma origem foi relida com outro conteúdo (`sources.reler_mtgo`). Em
    qualquer dos dois casos, a troca fica em `deck_lista_trocas` ANTES de as
    `deck_cards` serem substituídas — é a lista de ontem que se perderia."""
    con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?, ?)", (name, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ? AND format = ?",
                      (name, fmt)).fetchone()["id"]
    note = f"auto: {dl['source']} {dl['player'] or '?'} {dl['event_date']} (#{dl['id']})"
    cur = con.execute("SELECT notes FROM decks WHERE id = ?", (did,)).fetchone()["notes"]
    antes = _cartas_do_deck(con, did)
    depois = _cartas_da_lista(con, dl["id"])
    if cur == note and antes == depois:
        out.append(f"{name}: já atual ({dl['event_date']})")
        return
    motivo = "releitura" if cur == note else "troca"
    de = ler_nota(cur)
    if antes or de:
        con.execute(
            """INSERT INTO deck_lista_trocas
                 (deck_id, deck, formato, corrida, motivo,
                  de_decklist_id, de_jogador, de_data, de_cartas,
                  para_decklist_id, para_jogador, para_data, para_cartas)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (did, name, fmt, hoje or date.today().isoformat(), motivo,
             de.get("decklist_id"), de.get("jogador"), de.get("data"),
             json.dumps(antes, ensure_ascii=False),
             dl["id"], dl["player"] or "?", dl["event_date"],
             json.dumps(depois, ensure_ascii=False)))
    con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
    con.executemany("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, ?, ?, ?)", [(did, n, q, b) for b, n, q in depois])
    con.execute("UPDATE decks SET notes = ? WHERE id = ?", (note, did))
    if motivo == "releitura":
        out.append(f"{name}: relida ({dl['event_date']} {dl['player'] or '?'})")
    else:
        out.append(f"{name}: atualizado -> {dl['event_date']} {dl['player'] or '?'}")


def refresh(con: sqlite3.Connection, hoje: str | None = None) -> str:
    out = []
    for s in seguidos():
        dl = s["procura"](con)
        if dl:
            _store(con, s["deck"], s["formato"], dl, out, hoje)
        else:
            # DIZ QUE LISTA FICA (2026-10-16). "Cloud (Duel Commander): sem lista
            # de McWinSauce" aparecia todos os dias desde 12/10 e lia-se como uma
            # avaria — a causa é ele não ter publicado uma lista de Duel Commander
            # desde 31/08, e a poda de 30 dias já a levou da `decklists`. A lista
            # de 31/08 continua na `decks`; a linha passa a dizê-lo.
            row = con.execute("SELECT notes FROM decks WHERE name = ? AND format = ?",
                              (s["deck"], s["formato"])).fetchone()
            n = ler_nota(row["notes"] if row else None)
            fica = (f" (fica a de {n['data']}, {n['jogador']} #{n['decklist_id']})"
                    if n else "")
            out.append(f"{s['deck']}: {s['falta']}{fica}")
    con.commit()
    return "; ".join(out)


if __name__ == "__main__":
    import os
    from pathlib import Path
    os.environ.setdefault("MTGVAULT_HOME", str(Path(__file__).resolve().parent / "data"))
    from mtgvault import db
    with db.session() as con:
        print(refresh(con))
