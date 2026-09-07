"""Recolha diária de decklists.

COBERTURA POR FORMATO
    Standard, Pioneer, Modern, Legacy, Vintage, Pauper -> mtgo.com  ✔
    Duel Commander, Premodern                          -> mtgo.com  ✔
    cEDH                                               -> só mtgtop8

    O mtgo.com tem mesmo Duel CMDR e Premodern no filtro de formatos. Para
    apanhar também os torneios de papel (que no Duel Commander são a maioria),
    ver o módulo `mtgtop8`.

FRAGILIDADE
    Isto é scraping. O mtgo.com serve as listas num blob JSON embebido na
    página. Se a Wizards mudar a estrutura, `parse_mtgo_page` é o único sítio
    a corrigir — está isolado de propósito.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import requests

MTGO_BASE = "https://www.mtgo.com/decklists"
UA = {"User-Agent": "Mozilla/5.0 (compatible; mtgvault/0.1)"}

# Confirmado no filtro de formatos do mtgo.com: além dos habituais, há
# Duel CMDR e Premodern. Só o cEDH é que não existe em MTGO — esse vem
# todo do mtgtop8.
MTGO_FORMATS = {"standard", "pioneer", "modern", "legacy", "vintage", "pauper",
                "duel-commander", "premodern"}
NON_MTGO_FORMATS = {"cedh"}

# Formatos onde o comandante conta para o main. Definido aqui (a camada mais
# baixa) para o mtgo e o mtgtop8 partilharem a mesma lista e não divergirem —
# se divergissem, a mesma lista teria content_hash diferente e a dedup falhava.
COMMANDER_FORMATS = {"duel-commander", "cedh"}

_BLOB = re.compile(
    r"window\.MTGO\.decklists\.data\s*=\s*(\{.*?\});", re.S
)


def fetch_mtgo_index(day: date) -> list[str]:
    """URLs dos eventos publicados num dia.

    O mtgo.com serve o índice por ano/mês. Tentamos duas formas de URL porque
    o site já mudou de estrutura no passado; a primeira que responder ganha.
    As páginas de evento têm a data no próprio caminho
    (ex.: /decklist/duel-commander-league-2026-07-2210716), por isso filtramos
    por ela.
    """
    stamp = day.strftime("%Y-%m-%d")
    candidatos = [f"{MTGO_BASE}/{day:%Y/%m}", f"{MTGO_BASE}?year={day:%Y}&month={day:%m}"]
    for url in candidatos:
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
        except requests.RequestException:
            continue
        hrefs = set(re.findall(r'href="(/decklists?/[^"]+)"', r.text))
        achados = sorted(f"https://www.mtgo.com{h}" for h in hrefs if stamp in h)
        if achados:
            return achados
    return []


def parse_mtgo_page(html: str) -> dict | None:
    """Extrai o blob JSON com o evento e as decklists."""
    m = _BLOB.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _cards(deck: dict, board: str) -> list[tuple[str, int]]:
    key = "main_deck" if board == "main" else "sideboard_deck"
    out = []
    for item in deck.get(key) or []:
        attrs = item.get("card_attributes") or item
        name = attrs.get("card_name") or attrs.get("name")
        qty = item.get("quantity") or item.get("qty") or 0
        if name and qty:
            out.append((name, int(qty)))
    return out


def store_event(con: sqlite3.Connection, blob: dict, url: str) -> int:
    """Grava um evento e as suas decklists. Devolve nº de listas novas."""
    # O mtgo.com serve dois formatos de página com chaves diferentes:
    #   Liga     -> {name, publish_date, ...}          sem `format`
    #   Challenge-> {description, starttime, format, standings, ...}
    # Por isso o nome, a data e o formato têm de ser lidos de várias chaves.
    event = (blob.get("description") or blob.get("event_name")
             or blob.get("name") or "MTGO Event")
    # O slug do URL é a fonte fiável do formato: vem limpo em ambas as páginas
    # (modern-league-..., modern-challenge-64-..., duel-commander-league-...).
    # O campo `format` do blob só existe nas challenges e vem sujo ("CMODERN",
    # "CLEGACY", ...) — guardá-lo tal e qual fragmentava o mesmo formato em dois
    # (modern vs cmodern) e partia a dedup e a análise. Só se recorre a ele
    # quando o slug não chega para adivinhar.
    fmt = _guess_format(url)
    if fmt == "unknown" and blob.get("format"):
        fmt = blob["format"].lower().lstrip("c")
    day = (blob.get("starttime") or blob.get("publish_date")
           or blob.get("date") or "")[:10] or date.today().isoformat()

    new = 0
    for deck in blob.get("decklists") or []:
        key = str(deck.get("loginid") or deck.get("player") or "") + "|" + url
        main = _cards(deck, "main")
        side = _cards(deck, "side")
        if fmt in COMMANDER_FORMATS:
            # Nos formatos de comandante, o MTGO serve o comandante no
            # sideboard_deck (o mtgtop8 faz o mesmo no .dec). Reencaminha-se
            # para o main — é lá que conta para as 100 cartas e para o core —
            # e assim o content_hash coincide com o do mtgtop8, deixando a
            # deduplicação entre as duas fontes funcionar de verdade.
            main += side
            side = []
        cartas = [("main", n, q) for n, q in main]
        cartas += [("side", n, q) for n, q in side]
        if store_decklist(con, source="mtgo", source_key=key, fmt=fmt,
                          cards=cartas, event_name=event, event_date=day,
                          player=deck.get("player") or "",
                          placement=str(deck.get("rank") or ""), url=url):
            new += 1
    con.commit()
    return new


def _guess_format(url: str) -> str:
    # Por comprimento decrescente de propósito: "premodern" contém "modern",
    # por isso sem esta ordem um evento de Premodern era classificado como
    # Modern. E o resultado tem de ser determinístico (MTGO_FORMATS é um set).
    low = url.lower()
    for f in sorted(MTGO_FORMATS, key=len, reverse=True):
        if f in low:
            return f
    return "unknown"


def harvest_mtgo(con: sqlite3.Connection, days_back: int = 1,
                 formats: set[str] | None = None) -> int:
    """Recolhe as decklists dos últimos N dias. Isto é o trabalho diário."""
    formats = {f.lower() for f in (formats or MTGO_FORMATS)} & MTGO_FORMATS
    total = 0
    for delta in range(days_back):
        day = date.today() - timedelta(days=delta + 1)
        try:
            urls = fetch_mtgo_index(day)
        except requests.RequestException:
            continue
        for url in urls:
            if formats and not any(f in url.lower() for f in formats):
                continue
            # Liga que não conta para aquele formato: nem se descarrega a página
            # (o slug do mtgo já diz "…-league-…"). Poupa pedidos e BD.
            if ("league" in url.lower()
                    and "League" not in metagame_rules(_guess_format(url))["tiers"]):
                continue
            try:
                html = requests.get(url, headers=UA, timeout=30).text
            except requests.RequestException:
                continue
            blob = parse_mtgo_page(html)
            if blob:
                total += store_event(con, blob, url)
    return total


# ---------------------------------------------------------------------------
# Entrada manual — funciona para QUALQUER formato, incluindo Premodern,
# Duel Commander e cEDH enquanto não houver scraper próprio.
# ---------------------------------------------------------------------------
LINE = re.compile(r"^\s*(\d+)\s*x?\s+(.+?)\s*(?:\([A-Za-z0-9]{2,5}\)\s*[\w-]*)?\s*$")


def parse_text_decklist(text: str) -> dict[str, list[tuple[str, int]]]:
    """Lê uma decklist em texto (formato MTGO/Arena). 'Sideboard' separa boards."""
    out = {"main": [], "side": []}
    board = "main"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        if line.lower().startswith(("sideboard", "sb:")):
            board = "side"
            continue
        if line.lower().startswith(("deck", "maindeck", "commander")):
            board = "main"
            continue
        m = LINE.match(line)
        if m:
            out[board].append((m.group(2).strip(), int(m.group(1))))
    return out


def store_manual(con: sqlite3.Connection, text: str, fmt: str, event: str,
                 day: str, player: str = "", key: str | None = None) -> int:
    parsed = parse_text_decklist(text)
    key = key or f"{fmt}|{event}|{player}|{day}"
    cur = con.execute(
        """INSERT OR IGNORE INTO decklists
           (source, source_key, format, event_name, event_date, player, event_tier)
           VALUES ('manual',?,?,?,?,?,?)""",
        (key, fmt.lower(), event, day, player, event_tier("manual", event)),
    )
    if not cur.rowcount:
        return 0
    did = cur.lastrowid
    con.executemany(
        "INSERT OR REPLACE INTO decklist_cards "
        "(decklist_id, card_name, quantity, board) VALUES (?,?,?,?)",
        [(did, n, q, b) for b in ("main", "side") for n, q in parsed[b]],
    )
    con.commit()
    return did


# ---------------------------------------------------------------------------
# Armazenamento com deduplicação entre fontes
# ---------------------------------------------------------------------------
# Quem ganha quando a MESMA lista chega por caminhos diferentes.
# O mtgo.com é a origem: publica primeiro e sem intermediário. O mtgtop8
# re-hospeda listas do MTGO (as páginas dele dizem "Source: mtgo.com"), e o
# mtgdecks agrega o mtgtop8. Guardar as três seria contar o mesmo deck 3 vezes.
SOURCE_PRIORITY = {"manual": 4, "mtgo": 3, "mtgtop8": 2, "mtggoldfish": 1}


# Importância do evento, gravada em `decklists.event_tier`. Fica aqui, na camada
# mais baixa, para o mtgo e o mtgtop8 a escreverem da mesma maneira.
# Ordem: "Showcase Qualifier" é Showcase, não Qualifier.
# O mtgtop8 RE-HOSPEDA o MTGO ("Premodern event - MTGO League", "Modern event -
# MTGO Challenge 32"). Classificar pela FONTE punha-os todos em `Presencial` e
# metia ligas online no meio dos torneios de papel. Só se reclassifica um evento
# do mtgtop8 quando o NOME diz MTGO: um "BIG MAGIC Open - Champions Cup Premium
# Qualifier" de 131 jogadores é papel a sério e tem de continuar `Presencial`
# (aí quem manda é o nº de jogadores, não a palavra "Qualifier" no nome).
_MTGO_MARK = re.compile(r"\bmtgo\b|magic\s*online", re.I)


def _tier_from_name(en: str) -> str:
    if "showcase" in en:
        return "Showcase"
    if "challenge" in en:
        return "Challenge"
    if "qualifier" in en:
        return "Qualifier"
    if "prelim" in en:
        return "Preliminary"
    if "league" in en:
        return "League"
    return "outro"


def event_tier(source: str, event_name: str = "") -> str:
    en = (event_name or "").lower()
    if source == "mtgtop8" and not _MTGO_MARK.search(en):
        return "Presencial"      # torneio de papel — o peso vem de event_players
    return _tier_from_name(en)


def backfill_event_tiers(con: sqlite3.Connection) -> int:
    """(Re)classifica o `event_tier` de todas as listas. Devolve quantas MUDARAM.

    Existe porque a coluna andou anos a ser lida sem nunca ser escrita: as
    páginas do metagame apareciam vazias sem que nada acusasse erro. É
    IDEMPOTENTE sobre tudo (não só sobre os NULL) de propósito: quando a regra
    de classificação muda — como em 2026-09-07, com os re-hosts do MTGO a saírem
    de `Presencial` — as listas antigas acertam-se sozinhas na corrida seguinte.
    """
    mudou = [
        (t, r["id"])
        for r in con.execute("SELECT id, source, event_name, event_tier FROM decklists")
        for t in (event_tier(r["source"], r["event_name"]),)
        if t != r["event_tier"]
    ]
    if mudou:
        con.executemany("UPDATE decklists SET event_tier = ? WHERE id = ?", mudou)
        con.commit()
    return len(mudou)


# ---------------------------------------------------------------------------
# Que listas contam para o metagame  (regra do André, 2026-09-07)
# ---------------------------------------------------------------------------
# À letra: "no mtgvault não quero listas de league; quero challenge, showcase, e
# presenciais com 64 ou mais jogadores — menos Duel Commander, que pode ter
# menos jogadores e pode ser ligas."
#
# A regra é por formato e ajusta-se em colecao_config.json -> `metagame_fontes`.
# Está AQUI, na camada mais baixa, e todos os consumidores (metagame, cobertura,
# decks fazíveis, showcase, clustering/core, decks seguidos) passam por
# `lista_conta()` / `counting_sql()`. Se cada página filtrasse à sua maneira
# voltávamos ao problema do `event_tier`: páginas a discordar em silêncio.
DEFAULT_METAGAME_RULES = {
    "tiers": ["Challenge", "Showcase", "Presencial"],
    "min_jogadores_presencial": 64,
    "ligas": False,
}
# Exceções por formato — espelham o colecao_config.json, para o código funcionar
# na mesma sem ficheiro de configuração (tests, base nova). O config manda.
DEFAULT_METAGAME_BY_FORMAT = {
    "duel-commander": {"min_jogadores_presencial": 0, "ligas": True},
}

_CFG_CACHE: dict = {}


def _config() -> dict:
    """colecao_config.json (na raiz do repositório, ou MTGVAULT_CONFIG)."""
    p = Path(os.environ.get("MTGVAULT_CONFIG")
             or Path(__file__).resolve().parents[1] / "colecao_config.json")
    try:
        stamp = p.stat().st_mtime
    except OSError:
        return {}
    if _CFG_CACHE.get("path") != str(p) or _CFG_CACHE.get("stamp") != stamp:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        _CFG_CACHE.update(path=str(p), stamp=stamp, data=data)
    return _CFG_CACHE.get("data") or {}


def _sem_comentarios(d) -> dict:
    """As chaves "_xxx" do colecao_config.json são ajuda para o André, não regra."""
    return {k: v for k, v in (d or {}).items() if not str(k).startswith("_")}


def metagame_rules(fmt: str | None) -> dict:
    """A regra em vigor para um formato: {tiers, min_jogadores_presencial, ligas}."""
    fmt = (fmt or "").lower()
    sec = _config().get("metagame_fontes") or {}
    r = dict(DEFAULT_METAGAME_RULES)
    r.update(_sem_comentarios(DEFAULT_METAGAME_BY_FORMAT.get(fmt)))
    r.update(_sem_comentarios(sec.get("_default")))
    r.update(_sem_comentarios(sec.get(fmt)))
    tiers = list(r.get("tiers") or [])
    if r.get("ligas") and "League" not in tiers:
        tiers.append("League")
    r["tiers"] = tiers
    return r


def _campo(row, chave):
    """Valor de uma coluna, venha a linha em dict ou em sqlite3.Row."""
    try:
        return row[chave]
    except (KeyError, IndexError):
        return None


def lista_conta(row, fmt: str | None = None) -> bool:
    """Esta decklist conta para o metagame? `row` precisa de `event_tier` e
    `event_players` (e de `format`/`source` se não vierem por argumento).

    As listas `manual` contam sempre: foi o André que as meteu à mão, e é por aí
    que entram os formatos que os scrapers não cobrem.
    """
    if _campo(row, "source") == "manual":
        return True
    r = metagame_rules(fmt if fmt is not None else _campo(row, "format"))
    tier = _campo(row, "event_tier")
    if tier not in r["tiers"]:
        return False
    if tier == "Presencial":
        minimo = int(r.get("min_jogadores_presencial") or 0)
        if minimo > 0:
            # Sem contagem de jogadores NÃO conta — não se assume o mínimo.
            jogadores = _campo(row, "event_players")
            return jogadores is not None and jogadores >= minimo
    return True


def counting_sql(fmt: str, alias: str = "d") -> tuple[str, list]:
    """A mesma regra que `lista_conta`, como pedaço de SQL para pôr num WHERE.
    Devolve (condição, parâmetros) — a condição já vem entre parênteses."""
    r = metagame_rules(fmt)
    a = f"{alias}." if alias else ""
    tiers = r["tiers"]
    if not tiers:
        return f"({a}source = 'manual')", []
    marcas = ",".join("?" for _ in tiers)
    sql = f"{a}event_tier IN ({marcas})"
    params = list(tiers)
    minimo = int(r.get("min_jogadores_presencial") or 0)
    if minimo > 0 and "Presencial" in tiers:
        sql += (f" AND ({a}event_tier <> 'Presencial' OR ({a}event_players IS NOT NULL "
                f"AND {a}event_players >= ?))")
        params.append(minimo)
    return f"({a}source = 'manual' OR ({sql}))", params


# Quanto vale cada lista no ranking do metagame. Os pesos do online são os que o
# André confirmou em 2026-08-14 (Showcase 3, Challenge 1); o presencial entrou em
# 2026-09-07 e vale pela dimensão — um torneio de 128+ jogadores pesa mais que um
# Showcase online. As Leagues só chegam aqui no Duel Commander.
TIER_WEIGHT = {"Showcase": 3.0, "Challenge": 1.0, "Qualifier": 1.0,
               "Preliminary": 0.5, "League": 0.5}
PRESENCIAL_WEIGHT = ((128, 4.0), (64, 3.0), (0, 2.0))


def tier_weight(tier: str | None, players: int | None = None) -> float:
    if tier == "Presencial":
        p = players or 0
        return next(w for lim, w in PRESENCIAL_WEIGHT if p >= lim)
    return TIER_WEIGHT.get(tier or "", 0.0)


def tier_weight_sql(alias: str = "d") -> str:
    """`tier_weight` em SQL, para o ranking poder ser somado pela base de dados."""
    a = f"{alias}." if alias else ""
    presencial = " ".join(
        f"WHEN COALESCE({a}event_players, 0) >= {lim} THEN {w}"
        for lim, w in PRESENCIAL_WEIGHT)
    resto = " ".join(f"WHEN {a}event_tier = '{t}' THEN {w}"
                     for t, w in TIER_WEIGHT.items())
    return (f"CASE WHEN {a}event_tier = 'Presencial' THEN (CASE {presencial} ELSE 0 END) "
            f"{resto} ELSE 0 END")


def content_hash(fmt: str, cards: list[tuple[str, str, int]]) -> str:
    """Impressão digital do conteúdo da lista, independente da fonte."""
    payload = fmt.lower() + "|" + "|".join(
        f"{b}:{n}:{q}" for b, n, q in sorted(cards))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def store_decklist(con: sqlite3.Connection, *, source: str, source_key: str,
                   fmt: str, cards: list[tuple[str, str, int]],
                   event_name: str = "", event_date: str = "",
                   player: str = "", placement: str = "",
                   url: str = "", event_players: int | None = None) -> int | None:
    """Grava uma decklist, a não ser que já lá esteja por outra via.

    Duas listas são a mesma se tiverem o mesmo conteúdo, o mesmo formato, o
    mesmo dia e o mesmo jogador. Quando isso acontece, fica a da fonte com
    maior prioridade e a outra é descartada.

    Porque é que isto importa para a análise: se as listas do MTGO chegassem
    em triplicado (mtgo + mtgtop8 + mtgdecks) e as de papel só em duplicado,
    o metagame ficava enviesado para o online — e o `n` das estatísticas de
    core/tech ficava inflacionado, fazendo o limiar dos 90% parecer mais bem
    sustentado do que está.

    Devolve o id da decklist, ou None se foi descartada por duplicação.
    """
    if not cards:
        return None
    fmt = fmt.lower()
    tier = event_tier(source, event_name)
    # Ligas fora (regra 2026-09-07): nem se guardam, para o vault.db não crescer
    # com listas que nenhuma página conta. O Duel Commander é a exceção — lá as
    # ligas contam (colecao_config.json -> metagame_fontes["duel-commander"]).
    if tier == "League" and "League" not in metagame_rules(fmt)["tiers"]:
        return None
    h = content_hash(fmt, cards)
    event_date = event_date or date.today().isoformat()
    jogador = (player or "").strip().lower()

    existente = con.execute(
        """SELECT id, source, player FROM decklists
            WHERE format = ? AND content_hash = ? AND event_date = ?""",
        (fmt, h, event_date),
    ).fetchall()
    for row in existente:
        outro = (row["player"] or "").strip().lower()
        # Sem jogador conhecido de um dos lados, o conteúdo+data já chega.
        if jogador and outro and jogador != outro:
            continue
        if SOURCE_PRIORITY.get(source, 0) <= SOURCE_PRIORITY.get(row["source"], 0):
            return None                      # já temos uma versão igual ou melhor
        con.execute("DELETE FROM decklists WHERE id = ?", (row["id"],))

    cur = con.execute(
        """INSERT OR IGNORE INTO decklists
           (source, source_key, format, event_name, event_date, player,
            placement, url, content_hash, event_players, event_tier)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (source, source_key, fmt, event_name, event_date, player, placement,
         url, h, event_players, tier),
    )
    if not cur.rowcount:
        return None
    did = cur.lastrowid
    con.executemany(
        "INSERT OR REPLACE INTO decklist_cards "
        "(decklist_id, card_name, quantity, board) VALUES (?,?,?,?)",
        [(did, n, q, b) for b, n, q in cards],
    )
    con.commit()
    return did
