"""Recolha de decklists do mtgtop8.

Isto preenche o buraco que o MTGO não cobre. O mtgtop8 indexa torneios de
papel e de MTGO, e tem os três formatos que faltavam:

    duel-commander -> f=EDH
    premodern      -> f=PREM
    cedh           -> f=cEDH

FLUXO
    /format?f=EDH          -> ids de eventos recentes   (event?e=NNNNN)
    /event?e=NNNNN&f=EDH   -> ids das decklists         (d=NNNNNN)
    /dec?d=NNNNNN          -> a lista em formato .dec, texto limpo

O último passo é o truque: existe um export .dec, por isso não é preciso
parsear o HTML das listas — só o das páginas de índice.

COMANDANTES
    O mtgtop8 exporta o comandante na linha SB do .dec (a página mostra
    "MD 99 SB 1"). Nos formatos de comandante tratamos essa carta como o
    comandante e mandamo-la para o mainboard, que é onde ela conta para os
    100 cartões.
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import date

import requests

from . import sources

BASE = "https://mtgtop8.com"
UA = {"User-Agent": "mtgvault/0.1 (colecção pessoal)"}

FORMAT_CODES = {
    "standard": "ST", "pioneer": "PI", "modern": "MO", "legacy": "LE",
    "vintage": "VI", "pauper": "PAU",
    "duel-commander": "EDH", "premodern": "PREM", "cedh": "cEDH",
}
# Fonte única em sources: o mtgo e o mtgtop8 têm de tratar o comandante da
# mesma maneira, senão a mesma lista teria content_hash diferente e a dedup
# entre as fontes deixaria de funcionar.
COMMANDER_FORMATS = sources.COMMANDER_FORMATS

# Apanha o id do evento venha ele sozinho (páginas de formato) ou
# dentro de um link de deck (páginas de arquétipo).
RE_EVENT = re.compile(r"event\?e=(\d+)")
# Links de deck. O mtgtop8 passou a servi-los RELATIVOS (?e=..&d=..&f=..) em vez
# de event?e=.., e nem sempre escapa o & como &amp;. Ancorar em "&d=..&f=" apanha
# as duas formas e continua a valer para as páginas de arquétipo (?d=..&f=..).
RE_DECK = re.compile(r"[?&](?:amp;)?d=(\d+)&(?:amp;)?f=")
RE_PLAYER = re.compile(r"search\?player=([^\"'&>]+)")
# Deck-link e player-link deixaram de vir coladinhos: no layout novo há divs de
# permeio. Em vez de um regex frágil que salte o markup, percorre-se a página
# pela ordem do documento (ver parse_deck_entries), associando cada jogador ao
# deck-link mais recente.
RE_DECK_OR_PLAYER = re.compile(
    r"[?&](?:amp;)?d=(\d+)&(?:amp;)?f=|search\?player=([^\"'&>]+)")
RE_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2})")

_LAST = 0.0


def _get(path: str, **params) -> str:
    """Um pedido por segundo. Não há pressa e o site é de graça."""
    global _LAST
    wait = 1.0 - (time.time() - _LAST)
    if wait > 0:
        time.sleep(wait)
    r = requests.get(f"{BASE}{path}", params=params, headers=UA, timeout=30)
    _LAST = time.time()
    r.raise_for_status()
    r.encoding = r.encoding or "ISO-8859-1"
    return r.text


# ---------------------------------------------------------------------------
# Parsers (isolados para poderem ser testados sem rede)
# ---------------------------------------------------------------------------
def parse_event_ids(html: str) -> list[int]:
    """Ids de evento de uma página de formato, sem repetições e por ordem."""
    vistos, out = set(), []
    for m in RE_EVENT.finditer(html):
        eid = int(m.group(1))
        if eid not in vistos:
            vistos.add(eid)
            out.append(eid)
    return out


def parse_deck_ids(html: str) -> list[int]:
    vistos, out = set(), []
    for m in RE_DECK.finditer(html):
        did = int(m.group(1))
        if did not in vistos:
            vistos.add(did)
            out.append(did)
    return out


def parse_deck_entries(html: str) -> dict[int, str]:
    """{deck_id: jogador} percorrendo a página pela ordem do documento.

    Cada jogador é atribuído ao deck-link mais recente, e só à primeira vez: o
    mesmo deck surge em vários links por linha (miniatura, nome, "visual"), e o
    link do jogador aparece a seguir ao do deck. Assim funciona tanto no layout
    antigo (deck e jogador coladinhos) como no novo (com divs de permeio).
    """
    out: dict[int, str] = {}
    atual: int | None = None
    for m in RE_DECK_OR_PLAYER.finditer(html):
        if m.group(1):                       # é um link de deck
            atual = int(m.group(1))
        elif atual is not None and atual not in out:
            out[atual] = m.group(2).replace("+", " ").strip()
    return out


def parse_event_meta(html: str) -> dict:
    """Nome e data do evento a partir da página do evento."""
    nome = None
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        nome = m.group(1).split("@")[0].strip() or None
    dia = None
    m = RE_DATE.search(html)
    if m:
        d, mth, y = (int(x) for x in m.groups())
        dia = date(2000 + y, mth, d).isoformat()
    players = None
    m = re.search(r"(\d+)\s*players", html, re.I)   # peso do evento (mtgtop8 mostra-o)
    if m:
        players = int(m.group(1))
    return {"event_name": nome, "event_date": dia, "players": players}


DEC_LINE = re.compile(r"^(SB:\s*)?(\d+)\s+(.+?)\s*$")
# O export .dec do mtgtop8 prefixa cada carta com o código de edição entre
# parênteses retos — "4 [AVR] Griselbrand", "2 [] Koma, World-Eater" (vazio
# quando é edição recente/promo). O modelo guarda as cartas por nome (qualquer
# impressão joga), por isso o set é removido. Sem isto os nomes ("[AVR] Grisel-
# brand") não batiam com o catálogo nem com as listas do mtgo, e a dedup entre
# fontes nunca disparava — o content_hash é calculado sobre os nomes.
DEC_SET_PREFIX = re.compile(r"^\[[^\]]*\]\s*")


def parse_dec(text: str, commander_format: bool = False) -> list[tuple[str, str, int]]:
    """Lê o formato .dec. Devolve [(board, nome, qty), ...].

    Num formato de comandante, o que vem em SB é o comandante e vai para o
    mainboard — é lá que conta para as 100 cartas.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = DEC_LINE.match(line)
        if not m:
            continue
        is_sb = bool(m.group(1))
        qty = int(m.group(2))
        name = DEC_SET_PREFIX.sub("", m.group(3)).strip()
        board = "main" if (not is_sb or commander_format) else "side"
        out.append((board, name, qty))
    return out


# ---------------------------------------------------------------------------
# Recolha
# ---------------------------------------------------------------------------
def _bracket(pos: int) -> str:
    """Classificação padrão do mtgtop8 pela POSIÇÃO na página (as listas vêm por
    ordem de classificação): 1, 2, 3-4, 5-8, 9-16, 17-32, 33-64."""
    for lim, lbl in ((1, "1"), (2, "2"), (4, "3-4"), (8, "5-8"),
                     (16, "9-16"), (32, "17-32"), (64, "33-64")):
        if pos <= lim:
            return lbl
    return str(pos)


def fetch_deck(deck_id: int, commander_format: bool) -> list[tuple[str, str, int]]:
    return parse_dec(_get("/dec", d=deck_id), commander_format)


def harvest(con: sqlite3.Connection, fmt: str, max_events: int = 8,
            max_decks_per_event: int = 16) -> int:
    """Recolhe as decklists mais recentes de um formato. Devolve nº de novas.

    Os limites existem por respeito: o mtgtop8 é um site pequeno e gratuito.
    Com 8 eventos por dia por formato, ao fim de um mês tens amostra que chegue
    para a análise de core/tech.
    """
    fmt = fmt.lower()
    code = FORMAT_CODES.get(fmt)
    if not code:
        raise ValueError(f"Formato sem equivalente no mtgtop8: {fmt}")
    is_cmd = fmt in COMMANDER_FORMATS

    novas = 0
    for eid in parse_event_ids(_get("/format", f=code))[:max_events]:
        try:
            pagina = _get("/event", e=eid, f=code)
        except requests.RequestException:
            continue
        meta = parse_event_meta(pagina)
        jogadores = parse_deck_entries(pagina)
        for pos, did in enumerate(parse_deck_ids(pagina)[:max_decks_per_event], 1):
            if con.execute("SELECT 1 FROM decklists WHERE source = 'mtgtop8' "
                           "AND source_key = ?", (str(did),)).fetchone():
                continue
            try:
                cartas = fetch_deck(did, is_cmd)
            except requests.RequestException:
                continue
            # store_decklist descarta se esta lista já cá estiver vinda do
            # mtgo.com — o mtgtop8 re-hospeda muitos eventos de MTGO. O placement
            # vem da posição (a página lista por classificação).
            if sources.store_decklist(
                con, source="mtgtop8", source_key=str(did), fmt=fmt,
                cards=cartas, event_name=meta["event_name"] or "",
                event_date=meta["event_date"] or date.today().isoformat(),
                player=jogadores.get(did, ""), placement=_bracket(pos),
                event_players=meta.get("players"),
                url=f"{BASE}/event?e={eid}&d={did}&f={code}",
            ):
                novas += 1
        con.commit()
    return novas


def archetype_decks(archetype_id: int, fmt: str = "duel-commander") -> list[int]:
    """Ids das listas de um arquétipo específico (ex.: Cloud = 2629)."""
    code = FORMAT_CODES[fmt.lower()]
    return parse_deck_ids(_get("/archetype", a=archetype_id, f=code))
