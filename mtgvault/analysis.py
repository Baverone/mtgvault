"""Deteção de arquétipos e cálculo de núcleo (core) vs tech.

REGRA DO CORE
-------------
Para cada carta dentro de um arquétipo, olhamos para a distribuição do número
de cópias entre as listas que a jogam, e para a taxa de inclusão.

    core_copies = maior k tal que P(cópias >= k) >= core_threshold

Exemplo do enunciado: uma carta que aparece em 100% das listas, 80% com 3
cópias e 20% com 4.
    P(>=1)=1.0  P(>=2)=1.0  P(>=3)=1.0  P(>=4)=0.2
    Com threshold 0.90 -> core_copies = 3.
    A 4.ª cópia tem probabilidade 0.2 -> é tech.
    flex_copies = média_de_cópias_por_lista - core_copies = 3.2 - 3 = 0.2

CLASSIFICAÇÃO
    core  -> core_copies >= 1        (leva-se sempre pelo menos k)
    flex  -> inclusão >= flex_threshold mas core_copies == 0
    tech  -> o resto (aparece esporadicamente)

Nota: o "core" é sempre relativo à janela temporal. É por isso que guardamos
window_end/window_days — é o que permite ver o metagame a mexer.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta

BASIC_LANDS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
    "Snow-Covered Mountain", "Snow-Covered Forest",
}


# ---------------------------------------------------------------------------
# 1. Clustering de arquétipos
# ---------------------------------------------------------------------------
def _signature(cards: set[str]) -> set[str]:
    return {c for c in cards if c not in BASIC_LANDS}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster_decklists(
    lists: dict[int, set[str]], threshold: float = 0.55
) -> dict[int, list[int]]:
    """Agrupa decklists por semelhança de cartas (Jaccard sobre o mainboard).

    `lists` = {decklist_id: {nomes de cartas do main}}
    Devolve {cluster_index: [decklist_ids]}.

    Guloso e determinístico: processa por ordem decrescente de tamanho e
    compara com o centróide (cartas presentes em >= 60% do cluster).
    """
    sigs = {i: _signature(c) for i, c in lists.items()}
    order = sorted(sigs, key=lambda i: (-len(sigs[i]), i))

    clusters: dict[int, list[int]] = {}
    centroids: dict[int, set[str]] = {}

    for did in order:
        sig = sigs[did]
        best, best_score = None, 0.0
        for cid, cent in centroids.items():
            s = jaccard(sig, cent)
            if s > best_score:
                best, best_score = cid, s
        if best is not None and best_score >= threshold:
            clusters[best].append(did)
        else:
            cid = len(clusters)
            clusters[cid] = [did]
            best = cid
        # recalcular centróide
        members = clusters[best]
        counts = Counter(c for m in members for c in sigs[m])
        centroids[best] = {
            c for c, n in counts.items() if n >= max(1, int(0.6 * len(members)))
        }
    return clusters


def label_cluster(
    member_sigs: list[set[str]], global_freq: dict[str, float], top: int = 3
) -> str:
    """Nomeia o cluster pelas cartas mais distintivas (frequência local / global)."""
    n = len(member_sigs)
    local = Counter(c for s in member_sigs for c in s)
    scored = []
    for card, cnt in local.items():
        rate = cnt / n
        if rate < 0.6:
            continue
        distinctiveness = rate / max(global_freq.get(card, 0.001), 0.001)
        scored.append((distinctiveness, rate, card))
    scored.sort(reverse=True)
    if not scored:
        return "Unclassified"
    return " / ".join(c for _, _, c in scored[:top])


# ---------------------------------------------------------------------------
# 2. Core vs tech
# ---------------------------------------------------------------------------
def card_roles(
    lists: list[dict[str, int]],
    core_threshold: float = 0.90,
    flex_threshold: float = 0.40,
) -> dict[str, dict]:
    """Calcula o papel de cada carta a partir de N listas.

    `lists` = [{card_name: quantidade}, ...] (um dicionário por decklist)
    """
    n = len(lists)
    if n == 0:
        return {}

    per_card: dict[str, list[int]] = defaultdict(list)
    for lst in lists:
        for card, qty in lst.items():
            per_card[card].append(qty)

    out: dict[str, dict] = {}
    for card, quantities in per_card.items():
        n_with = len(quantities)
        inclusion = n_with / n
        counts = Counter(quantities)
        max_q = max(quantities)

        # P(cópias >= k) medido sobre TODAS as listas, não só as que a jogam.
        core_copies = 0
        for k in range(1, max_q + 1):
            p_at_least_k = sum(c for q, c in counts.items() if q >= k) / n
            if p_at_least_k >= core_threshold:
                core_copies = k
            else:
                break

        avg_all = sum(quantities) / n          # média sobre todas as listas
        avg_played = sum(quantities) / n_with  # média onde é jogada
        flex = round(avg_all - core_copies, 3)

        if core_copies >= 1:
            role = "core"
        elif inclusion >= flex_threshold:
            role = "flex"
        else:
            role = "tech"

        out[card] = {
            "n_lists": n,
            "n_with_card": n_with,
            "inclusion_rate": round(inclusion, 4),
            "avg_copies": round(avg_played, 3),
            "avg_copies_all": round(avg_all, 3),
            "core_copies": core_copies,
            "flex_copies": flex,
            "dist": {
                str(q): round(counts.get(q, 0) / n_with, 4) for q in sorted(counts)
            },
            "role": role,
        }
    return out


# ---------------------------------------------------------------------------
# 3. Orquestração sobre a base de dados
# ---------------------------------------------------------------------------
def _fetch_lists(con, fmt: str, since: str, until: str, board: str):
    rows = con.execute(
        """SELECT d.id, d.archetype_id, c.card_name, c.quantity
             FROM decklists d
             JOIN decklist_cards c ON c.decklist_id = d.id
            WHERE d.format = ? AND d.event_date BETWEEN ? AND ? AND c.board = ?""",
        (fmt, since, until, board),
    ).fetchall()
    by_deck: dict[int, dict[str, int]] = defaultdict(dict)
    arch: dict[int, int | None] = {}
    for r in rows:
        by_deck[r["id"]][r["card_name"]] = r["quantity"]
        arch[r["id"]] = r["archetype_id"]
    return by_deck, arch


def rebuild_archetypes(con: sqlite3.Connection, fmt: str, window_days: int = 30) -> int:
    """Re-agrupa as decklists recentes de um formato em arquétipos."""
    until = date.today()
    since = until - timedelta(days=window_days)
    by_deck, _ = _fetch_lists(con, fmt, since.isoformat(), until.isoformat(), "main")
    if not by_deck:
        return 0

    sets = {did: set(cards) for did, cards in by_deck.items()}
    clusters = cluster_decklists(sets)

    total = len(sets)
    global_freq = {
        c: n / total
        for c, n in Counter(c for s in sets.values() for c in _signature(s)).items()
    }

    for members in clusters.values():
        label = label_cluster([_signature(sets[m]) for m in members], global_freq)
        con.execute(
            """INSERT INTO archetypes (format, label, signature, first_seen, last_seen)
               VALUES (?,?,?,date('now'),date('now'))
               ON CONFLICT(format, label) DO UPDATE SET last_seen = date('now')""",
            (fmt, label, json.dumps(sorted(_signature(sets[members[0]]))[:15])),
        )
        aid = con.execute(
            "SELECT id FROM archetypes WHERE format = ? AND label = ?", (fmt, label)
        ).fetchone()["id"]
        con.executemany(
            "UPDATE decklists SET archetype_id = ? WHERE id = ?",
            [(aid, m) for m in members],
        )
    con.commit()
    return len(clusters)


def rebuild_roles(con: sqlite3.Connection, fmt: str, window_days: int = 30) -> int:
    """Recalcula core/flex/tech para cada arquétipo do formato."""
    until = date.today()
    since = until - timedelta(days=window_days)
    written = 0

    for board in ("main", "side"):
        by_deck, arch = _fetch_lists(
            con, fmt, since.isoformat(), until.isoformat(), board
        )
        groups: dict[int, list[dict[str, int]]] = defaultdict(list)
        for did, cards in by_deck.items():
            if arch.get(did):
                groups[arch[did]].append(cards)

        for aid, lists in groups.items():
            if len(lists) < 5:      # amostra pequena de mais para tirar conclusões
                continue
            for card, info in card_roles(lists).items():
                con.execute(
                    """INSERT OR REPLACE INTO card_roles (
                        archetype_id, window_end, window_days, card_name, board,
                        n_lists, n_with_card, inclusion_rate, avg_copies,
                        core_copies, flex_copies, dist, role)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        aid, until.isoformat(), window_days, card, board,
                        info["n_lists"], info["n_with_card"],
                        info["inclusion_rate"], info["avg_copies"],
                        info["core_copies"], info["flex_copies"],
                        json.dumps(info["dist"]), info["role"],
                    ),
                )
                written += 1
    con.commit()
    return written


def trend(con: sqlite3.Connection, archetype_id: int, card_name: str) -> list[dict]:
    """Evolução da inclusão de uma carta ao longo das janelas já calculadas."""
    rows = con.execute(
        """SELECT window_end, inclusion_rate, core_copies, avg_copies
             FROM card_roles
            WHERE archetype_id = ? AND card_name = ? AND board = 'main'
            ORDER BY window_end""",
        (archetype_id, card_name),
    ).fetchall()
    return [dict(r) for r in rows]


def prune_decklists(con: sqlite3.Connection, keep_days: int = 180) -> int:
    """Apaga decklists antigas, mantendo a análise já calculada.

    Isto existe por causa do Git: cada commit diário guarda uma cópia inteira
    do vault.db, por isso o histórico do repositório cresce com o tamanho do
    ficheiro. As decklists em bruto são o que mais pesa — e depois de
    processadas já não são precisas: o que interessa a longo prazo é a tabela
    `card_roles`, que guarda uma fotografia por janela e é minúscula.

    Ou seja: perdes a lista do jogador X em março, mantens a evolução do
    metagame em março.
    """
    n = con.execute(
        "SELECT COUNT(*) c FROM decklists WHERE event_date < date('now', ?)",
        (f"-{keep_days} days",),
    ).fetchone()["c"]
    con.execute(
        "DELETE FROM decklist_cards WHERE decklist_id IN "
        "(SELECT id FROM decklists WHERE event_date < date('now', ?))",
        (f"-{keep_days} days",),
    )
    con.execute("DELETE FROM decklists WHERE event_date < date('now', ?)",
                (f"-{keep_days} days",))
    con.commit()
    con.execute("VACUUM")
    return n
