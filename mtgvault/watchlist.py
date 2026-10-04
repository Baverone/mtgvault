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
    if changed:
        # Uma lista que VOLTA a uma versão já guardada colide com o UNIQUE
        # (watched_id, list_hash), e o INSERT OR IGNORE deixava a linha antiga
        # com a data ANTIGA. Como toda a gente lê a lista atual com
        # `ORDER BY taken_at DESC, id DESC` (latest_cards, diff, meusdecks,
        # core_decks, colecao_cor), o site passava a mostrar a versão que já
        # tinha sido abandonada como se fosse a atual, e o diff vinha ao
        # contrário. Apaga-se a linha repetida para ela voltar a entrar com a
        # data (e o id) de hoje. Se nada mudou, não se mexe — evita reescrever
        # o vault.db todos os dias sem motivo.
        con.execute(
            "DELETE FROM watched_snapshots WHERE watched_id = ? AND list_hash = ?",
            (wid, h),
        )
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


def check_mtgtop8_archetype(con: sqlite3.Connection, wid: int) -> dict:
    """A página de um arquétipo do mtgtop8: lista NOVA e troca da MELHOR lista.

    A VIGIA DO ARQUÉTIPO (André, 2026-10-04): *"ele quer o deck de Duel Commander
    seguido todos os dias"* — `archetype?a=2629` (Cloud, Midgar Mercenary).

    Duas perguntas, e são diferentes:

      * **lista nova** — um `deck_id` que a página serve e que não estava no
        último snapshot. É o sinal de que alguém registou mais uma lista do
        arquétipo.
      * **a melhor classificada mudou** — a página é cronológica, não ordenada
        por resultado; a «melhor» calcula-se (`_melhor`) pela POSIÇÃO, com a data
        mais recente a desempatar. É ela que interessa seguir: a 04/10 é a do
        Liwei Luo, primeiro lugar em três presenciais seguidos com as mesmas 100
        cartas.

    **Um pedido por corrida.** O snapshot guarda o ÍNDICE da página (uma linha
    por lista) e não as cartas de cada deck: as cartas custariam um `.dec` por
    lista — 16 pedidos na primeira corrida, e nenhum deles responde à pergunta
    *"mudou?"*. Quem quiser as cartas de uma lista tem o `mtgtop8.fetch_deck`, e
    quem as guarda na base é a recolha (`harvest`), não a vigia.

    O `list_hash` reaproveita-se com a forma `(board, nome, qty)` que ele já usa
    — aqui `("deck", "<id> <jogador> @ <evento>", posição ordinal) —, para o
    `_save_snapshot` e o `diff` continuarem a funcionar sem um segundo formato.
    """
    from . import mtgtop8                                       # noqa: PLC0415
    w = con.execute("SELECT * FROM watched WHERE id = ?", (wid,)).fetchone()
    antes = {c[1] for c in latest_cards(con, wid)}
    melhor_antes = _melhor_do_snapshot(latest_cards(con, wid))

    linhas = mtgtop8.archetype_listas(int(w["key"]), w["format"])
    cards = [_linha_para_card(x) for x in linhas]
    novas = [x for x in linhas if _chave_da_linha(x) not in antes] if antes else []
    melhor = _melhor(linhas)
    url = f"{mtgtop8.BASE}/archetype?a={w['key']}&f={mtgtop8.FORMAT_CODES[w['format']]}"
    changed = _save_snapshot(con, wid, cards, url)
    return {"watched": dict(w), "found": bool(linhas), "changed": changed,
            "listas": len(linhas), "novas": novas,
            "primeira_vez": not antes,
            "melhor": melhor, "melhor_antes": melhor_antes,
            "melhor_mudou": bool(antes) and melhor is not None
            and _chave_da_linha(melhor) != melhor_antes,
            "cards": cards, "url": url}


def _chave_da_linha(x: dict) -> str:
    return f"{x['deck_id']} {x['jogador']} @ {x['evento']}"


def _linha_para_card(x: dict) -> tuple[str, str, int]:
    """Uma linha da página como `(board, nome, qty)`, a forma do `list_hash`.

    A `qty` é a posição em ORDINAL (`1`, `3-4` -> 3) para o snapshot ser
    comparável; o `0` é *"a página não disse"*. A posição entra no hash de
    propósito: uma lista que SOBE de 3-4 para 1 é uma mudança que ele quer ver.
    """
    pos = x.get("posicao") or ""
    try:
        q = int(str(pos).split("-")[0])
    except ValueError:
        q = 0
    return ("deck", _chave_da_linha(x), q)


def _melhor(linhas: list[dict]) -> dict | None:
    """A melhor lista: menor posição, e entre iguais a mais RECENTE.

    A posição vem como `1`, `3-4`, `5-8`; vale o início do bracket. Uma linha sem
    posição vai para o fim (nunca é «a melhor» por falta de dado).
    """
    def chave(x):
        pos = str(x.get("posicao") or "")
        try:
            p = int(pos.split("-")[0])
        except ValueError:
            p = 9999
        return (p, [-int(n) for n in (x.get("data") or "0-0-0").split("-")])
    return sorted(linhas, key=chave)[0] if linhas else None


def _melhor_do_snapshot(cards: list[tuple[str, str, int]]) -> str | None:
    """A chave da melhor lista do snapshot anterior, pela `qty` (a posição)."""
    uteis = [c for c in cards if c[2] > 0] or list(cards)
    return sorted(uteis, key=lambda c: c[2])[0][1] if uteis else None


# Que função trata cada `kind`. É um mapa e não uma cadeia de `elif` porque o
# `check_all` passou a EXIGIR que todo o kind activo tenha quem o trate — ver lá.
VERIFICADORES = {
    "mtgo_player": check_mtgo_player,
    "moxfield": check_moxfield,
    "mtgtop8_archetype": check_mtgtop8_archetype,
}


def check_all(con: sqlite3.Connection) -> list[dict]:
    """Corre a vigia de tudo o que está activo.

    UMA VIGIA QUE NÃO VIGIA É PIOR DO QUE NENHUMA (André, 2026-10-04, à letra:
    *"não deixes uma vigia inscrita que nunca corre — ele fica a pensar que está
    coberta"*). Até aqui isto era `if mtgo_player / elif moxfield` e mais nada: o
    `kind` **`archetype`**, que o CHECK da tabela aceita desde o primeiro dia e
    que nunca teve implementação, era saltado **sem uma linha de saída e sem
    erro** — o padrão do `event_tier`, aplicado a uma vigia. Agora um kind sem
    verificador sai com `error` e `nao_implementado`, que é o que o põe à vista
    no log do `watch-check` e na página.
    """
    out = []
    for w in con.execute("SELECT * FROM watched WHERE active = 1 ORDER BY id"):
        fn = VERIFICADORES.get(w["kind"])
        if fn is None:
            out.append({"watched": dict(w), "found": False,
                        "nao_implementado": True,
                        "error": f"kind '{w['kind']}' nao tem verificador: esta "
                                 f"vigia esta INSCRITA e NAO corre"})
            continue
        try:
            out.append(fn(con, w["id"]))
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
