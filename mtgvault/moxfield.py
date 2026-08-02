"""Leitura de decks públicos do Moxfield.

ATENÇÃO — LÊ ISTO ANTES DE ESPERAR QUE FUNCIONE À PRIMEIRA
-----------------------------------------------------------
O Moxfield tem endpoints públicos (api2.moxfield.com) mas estão atrás da
Cloudflare. A política deles é que aplicações externas peçam ao suporte um
**User-Agent autorizado**, e só esse passa de forma fiável. Sem isso vais
apanhar 403 mais cedo ou mais tarde, e disfarçar o User-Agent de browser é
exatamente o que eles estão a tentar travar.

O caminho limpo:
    1. escreve ao suporte do Moxfield a pedir um User-Agent para uso pessoal
    2. mete-o na variável de ambiente MOXFIELD_USER_AGENT
    3. este módulo passa a funcionar

Enquanto não tiveres isso, há a alternativa manual, que serve perfeitamente
para meia dúzia de decks: no Moxfield, Export -> Text, e depois
    python -m mtgvault.cli watch-paste <id> ficheiro.txt
A lista fica guardada com a mesma estrutura, incluindo o histórico e o diff.
"""
from __future__ import annotations

import os
import re
import time

import requests

API = "https://api2.moxfield.com/v3/decks/all/{}"
_LAST = 0.0

ID_RE = re.compile(r"moxfield\.com/decks/([A-Za-z0-9_-]+)")


def deck_id(url_or_id: str) -> str:
    m = ID_RE.search(url_or_id)
    return m.group(1) if m else url_or_id.strip()


def _headers() -> dict:
    ua = os.environ.get("MOXFIELD_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "Falta MOXFIELD_USER_AGENT. Pede um User-Agent autorizado ao suporte "
            "do Moxfield, ou usa o modo manual (Export -> Text + watch-paste)."
        )
    return {"User-Agent": ua, "Accept": "application/json"}


def fetch_deck(url_or_id: str) -> dict:
    """Devolve {name, url, updated_at, cards:[(board, nome, qty), ...]}."""
    global _LAST
    wait = 1.0 - (time.time() - _LAST)      # 1 pedido/s, sem pressas
    if wait > 0:
        time.sleep(wait)
    did = deck_id(url_or_id)
    r = requests.get(API.format(did), headers=_headers(), timeout=30)
    _LAST = time.time()
    if r.status_code == 403:
        raise RuntimeError(
            "Moxfield devolveu 403 (Cloudflare). O User-Agent não está autorizado."
        )
    r.raise_for_status()
    return parse_deck_payload(r.json(), did)


BOARD_MAP = {
    "mainboard": "main", "sideboard": "side", "commanders": "main",
    "companions": "side", "maybeboard": None, "considering": None,
}


def parse_deck_payload(data: dict, did: str) -> dict:
    """Isola a estrutura do JSON do Moxfield. Se mudarem o formato, é aqui."""
    cards: list[tuple[str, str, int]] = []
    boards = data.get("boards") or {}
    for key, board in boards.items():
        target = BOARD_MAP.get(key)
        if target is None:
            continue
        for entry in (board.get("cards") or {}).values():
            name = ((entry.get("card") or {}).get("name")) or entry.get("name")
            qty = entry.get("quantity") or 0
            if name and qty:
                cards.append((target, name, int(qty)))
    return {
        "name": data.get("name"),
        "url": f"https://moxfield.com/decks/{did}",
        "updated_at": data.get("lastUpdatedAtUtc"),
        "format": (data.get("format") or "").lower(),
        "cards": cards,
    }
