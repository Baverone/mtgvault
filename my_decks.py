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

**UMA TROCA GRANDE NÃO ENTRA EM SILÊNCIO (2026-10-16, à tarde).** A escolha é
*"a lista mais recente que tem as cartas-assinatura"* — não olha para o
`archetype_id` nem para o nome da fonte —, e quando dois decks partilham a
assinatura a referência salta entre eles: o Grinding Station passou de Emry +
Cam para Kethis a 14/10 (84 cartas) e de volta a 16/10 (82). Agora uma troca de
mais de `painel.TROCA_DE_ARQUETIPO` cartas, ou para uma lista que deixe de
jogar a carta que dá nome ao deck, é RECUSADA (`avaliar_troca`): fica em
`deck_lista_trocas` com `motivo = 'recusada'`, o deck mantém a lista anterior,
o painel avisa (alta) todos os dias, e só entra com `aceitar` — que é ele a
decidir: `py my_decks.py aceitar "<deck>" [decklist_id]`.

**E A RECUSA PODE SER DELE, PARA SEMPRE (2026-10-19).** A recusada fica a avisar
todas as noites enquanto for a lista mais recente; quando ele a viu e disse que
NÃO, o aviso deixa de servir. `py my_decks.py rejeitar "<deck>" <decklist_id>`
grava `motivo = 'rejeitada'` (com a data e a lista que fica) e a procura desse
deck passa a SALTAR essa lista — o deck fica na que tem e uma lista mais nova
volta a ser avaliada como sempre. Só aquela lista, só aquele deck. O caso: a
28571 (Chay Chay Hii, Regional Championship SEA de 17/10, que a fonte chama
«Pinnacle Affinity») apanhada pela assinatura do Grinding Station; ele mantém a
27439 (howa, 15/10). Desfazer é apagar a linha `rejeitada`.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date

from mtgvault import sources
from mtgvault.painel import TROCA_DE_ARQUETIPO, cartas_do_nome, diferencas

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


def _fora_sql(fora) -> tuple[str, list]:
    """O pedaço de WHERE que salta as listas que ele rejeitou para o deck."""
    fora = list(fora or [])
    if not fora:
        return "", []
    return f" AND dl.id NOT IN ({','.join('?' * len(fora))})", fora


def rejeitadas(con: sqlite3.Connection, deck: str, fmt: str) -> list[int]:
    """As decklists que ele rejeitou para este deck (`motivo = 'rejeitada'`)."""
    return [r[0] for r in con.execute(
        "SELECT DISTINCT para_decklist_id FROM deck_lista_trocas WHERE deck = ? "
        "AND formato = ? AND motivo = 'rejeitada' AND para_decklist_id IS NOT NULL",
        (deck, fmt))]


def _latest(con: sqlite3.Connection, fmt: str, cards: list[str], fora=None):
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
    fq, fp = _fora_sql(fora)
    q += fq + " ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1"
    params += fp
    return con.execute(q, params).fetchone()


def _latest_player(con: sqlite3.Connection, fmt: str, player: str, fora=None):
    """Decklist mais recente de um jogador específico nesse formato."""
    conta, cp = _conta(fmt)
    fq, fp = _fora_sql(fora)
    return con.execute(
        f"""SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
             WHERE dl.format = ? AND dl.player = ? AND {conta}
               AND (SELECT COALESCE(SUM(dc.quantity), 0) FROM decklist_cards dc
                      WHERE dc.decklist_id = dl.id AND dc.board = 'main') >= ?{fq}
             ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1""",
        [fmt, player] + cp + [MIN_MAIN] + fp).fetchone()


def _latest_player_deck(con: sqlite3.Connection, fmt: str, player: str, cards: list[str],
                        fora=None):
    """Lista mais recente de `player` nesse formato que CONTÉM todas as `cards`
    (ex.: o comandante) — para seguir um deck específico de um jogador."""
    ph = ",".join("?" * len(cards))
    conta, cp = _conta(fmt)
    fq, fp = _fora_sql(fora)
    return con.execute(
        f"""SELECT dl.id, dl.source, dl.player, dl.event_date FROM decklists dl
              WHERE dl.format = ? AND dl.player = ? AND {conta}
                AND (SELECT COUNT(DISTINCT dc.card_name) FROM decklist_cards dc
                       WHERE dc.decklist_id = dl.id AND dc.card_name IN ({ph})) = ?{fq}
              ORDER BY dl.event_date DESC, dl.id DESC LIMIT 1""",
        [fmt, player] + cp + cards + [len(cards)] + fp).fetchone()


def seguidos() -> list[dict]:
    """Os decks seguidos, numa lista só: nome, formato, como se escolhe a lista
    e as cartas que lhe dão o nome (a assinatura sem as exclusões). É o que o
    `refresh` percorre e o que o painel mostra — uma lista só, para os dois não
    discordarem sobre quem é seguido."""
    out = []
    for name, fmt, cards in FOLLOWED:
        out.append({"deck": name, "formato": fmt, "como": "assinatura",
                    "assinatura": [c for c in cards if not c.startswith("!")],
                    "procura": lambda con, n=name, f=fmt, c=cards: _latest(
                        con, f, c, rejeitadas(con, n, f)),
                    "falta": "sem lista"})
    for name, fmt, player in FOLLOWED_PLAYERS:
        out.append({"deck": name, "formato": fmt, "como": "jogador", "assinatura": [],
                    "procura": lambda con, n=name, f=fmt, p=player: _latest_player(
                        con, f, p, rejeitadas(con, n, f)),
                    "falta": f"sem lista de {player}"})
    for name, fmt, player, cards in FOLLOWED_PLAYER_DECK:
        out.append({"deck": name, "formato": fmt, "como": "jogador+cartas",
                    "assinatura": list(cards),
                    "procura": lambda con, n=name, f=fmt, p=player, c=cards: _latest_player_deck(
                        con, f, p, c, rejeitadas(con, n, f)),
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


def avaliar_troca(antes: list, depois: list, nome: list[str]) -> str | None:
    """`None` se a troca de `antes` para `depois` pode entrar sozinha; senão o
    motivo da recusa, em português. Duas regras, por esta ordem:

    1. a lista nova deixa de jogar uma carta que dá nome ao deck
       (`painel.cartas_do_nome`) — recusa-se SEMPRE, seja qual for o tamanho:
       um deck chamado Grinding Station sem Grinding Station não é o deck;
    2. mudam mais de `painel.TROCA_DE_ARQUETIPO` cartas (cada carta conta nos
       dois sentidos, a mesma conta do painel) — não é a lista a evoluir, é o
       emparelhador a agarrar outro deck que partilha a assinatura.

    Numa procura por assinatura a regra 1 é quase sempre redundante (a lista só
    é candidata se tiver as cartas), e é de propósito: é a rede para o dia em
    que a assinatura deixar de incluir a carta do nome."""
    for c in nome:
        if not any(n == c and int(q) > 0 for _b, n, q in depois):
            return f"a lista nova nao joga {c}"
    n = sum(abs(d) for _b, _n, d in diferencas(antes, depois))
    if n > TROCA_DE_ARQUETIPO:
        return f"{n} cartas trocadas (mais de {TROCA_DE_ARQUETIPO})"
    return None


def _gravar_troca(con, did, name, fmt, hoje, motivo, de, antes, dl, depois):
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


def _store(con: sqlite3.Connection, name: str, fmt: str, dl, out: list,
           hoje: str | None = None, assinatura: list[str] | None = None,
           forcar: bool = False):
    """Grava/atualiza a decklist `dl` como deck `name`, só se a origem mudou ou
    se a mesma origem foi relida com outro conteúdo (`sources.reler_mtgo`). Em
    qualquer dos dois casos, a troca fica em `deck_lista_trocas` ANTES de as
    `deck_cards` serem substituídas — é a lista de ontem que se perderia.

    Uma troca para OUTRA lista passa primeiro pelo `avaliar_troca` (salvo
    `forcar`, que é o `aceitar` dele); recusada, grava-se UMA vez como
    `motivo = 'recusada'` e o deck não mexe. A releitura (a mesma lista, relida)
    não se avalia: é a leitura a ser corrigida, não o deck a mudar."""
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
    if motivo == "troca" and antes and not forcar:
        porque = avaliar_troca(antes, depois, cartas_do_nome(name, assinatura or []))
        if porque:
            ja = con.execute(
                "SELECT 1 FROM deck_lista_trocas WHERE deck = ? AND formato = ? "
                "AND motivo = 'recusada' AND para_decklist_id = ? AND de_decklist_id IS ?",
                (name, fmt, dl["id"], de.get("decklist_id"))).fetchone()
            if not ja:
                _gravar_troca(con, did, name, fmt, hoje, "recusada", de, antes, dl, depois)
            fica = f"{de.get('data')} {de.get('jogador')}" if de else "a anterior"
            out.append(f"{name}: troca RECUSADA -> {dl['event_date']} {dl['player'] or '?'} "
                       f"({porque}); fica {fica}")
            return
    if antes or de:
        _gravar_troca(con, did, name, fmt, hoje, motivo, de, antes, dl, depois)
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
            _store(con, s["deck"], s["formato"], dl, out, hoje, s["assinatura"])
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


def aceitar(con: sqlite3.Connection, deck: str, decklist_id: int | None = None,
            hoje: str | None = None) -> str:
    """Ele decide: a lista `decklist_id` (por omissão a mais recente que a
    procura do deck devolve — a recusada) passa a ser a referência, sem passar
    pelo `avaliar_troca`. Fica gravada como troca normal; a linha `recusada`
    fica no histórico."""
    s = next((x for x in seguidos() if x["deck"] == deck), None)
    if s is None:
        raise ValueError(f"deck nao seguido: {deck!r}")
    if decklist_id is None:
        dl = s["procura"](con)
        if dl is None:
            raise ValueError(f"{deck}: {s['falta']}")
    else:
        dl = con.execute("SELECT id, source, player, event_date, format FROM decklists "
                         "WHERE id = ?", (decklist_id,)).fetchone()
        if dl is None:
            raise ValueError(f"decklist #{decklist_id} nao existe")
        if dl["format"] != s["formato"]:
            raise ValueError(f"decklist #{decklist_id} e de {dl['format']}, nao {s['formato']}")
    out: list = []
    _store(con, deck, s["formato"], dl, out, hoje, s["assinatura"], forcar=True)
    con.commit()
    return "; ".join(out)


def rejeitar(con: sqlite3.Connection, deck: str, decklist_id: int,
             hoje: str | None = None) -> str:
    """Ele decide que `decklist_id` NÃO é este deck: grava `motivo = 'rejeitada'`
    (com a lista que o deck tem agora como `de`) e a procura passa a saltá-la.
    O deck não mexe. Repetir é um no-op."""
    s = next((x for x in seguidos() if x["deck"] == deck), None)
    if s is None:
        raise ValueError(f"deck nao seguido: {deck!r}")
    dl = con.execute("SELECT id, source, player, event_date, format FROM decklists "
                     "WHERE id = ?", (decklist_id,)).fetchone()
    if dl is None:
        raise ValueError(f"decklist #{decklist_id} nao existe")
    if dl["format"] != s["formato"]:
        raise ValueError(f"decklist #{decklist_id} e de {dl['format']}, nao {s['formato']}")
    row = con.execute("SELECT id, notes FROM decks WHERE name = ? AND format = ?",
                      (deck, s["formato"])).fetchone()
    de = ler_nota(row["notes"] if row else None)
    if de.get("decklist_id") == decklist_id:
        raise ValueError(f"#{decklist_id} e a lista que o deck {deck} tem agora; "
                         "rejeitar a lista em uso deixava o deck sem referencia")
    if decklist_id in rejeitadas(con, deck, s["formato"]):
        return f"{deck}: #{decklist_id} ja estava rejeitada"
    antes = _cartas_do_deck(con, row["id"]) if row else []
    _gravar_troca(con, row["id"] if row else None, deck, s["formato"], hoje, "rejeitada",
                  de, antes, dl, _cartas_da_lista(con, decklist_id))
    con.commit()
    fica = f"{de.get('data')} {de.get('jogador')} #{de.get('decklist_id')}" if de else "a anterior"
    return (f"{deck}: #{decklist_id} ({dl['event_date']} {dl['player'] or '?'}) rejeitada; "
            f"fica {fica}")


if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path
    os.environ.setdefault("MTGVAULT_HOME", str(Path(__file__).resolve().parent / "data"))
    from mtgvault import db
    with db.session() as con:
        if len(sys.argv) >= 3 and sys.argv[1] == "aceitar":
            print(aceitar(con, sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None))
        elif len(sys.argv) == 4 and sys.argv[1] == "rejeitar":
            print(rejeitar(con, sys.argv[2], int(sys.argv[3])))
        else:
            print(refresh(con))
