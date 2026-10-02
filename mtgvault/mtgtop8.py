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

from . import consenso, sources

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
# O NOME DO ARQUÉTIPO (2026-10-02). A página do evento serve-o como TEXTO do link
# de cada deck: `<a href=?e=91451&d=894542&f=PREM>Landstill</a>`. Só casa quando o
# conteúdo do `<a>` não tem etiquetas lá dentro (`[^<]*`), e é isso que deixa de
# fora os outros links para o mesmo deck: o da miniatura (que leva um `<img>`) e o
# da seta do topo (que é `&rarr;`, filtrado pelo `_NAO_NOME`). Verificado contra a
# página real do evento 91451 — a amostra está em `tests/fixtures`.
RE_DECK_NOME = re.compile(r"[?&](?:amp;)?d=(\d+)&(?:amp;)?f=[A-Za-z]*>([^<]*)</a>")
# O que não é nome de arquétipo: a seta do deck aberto e um link vazio.
_NAO_NOME = {"", "&rarr;", "→", "&nbsp;"}

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


def parse_deck_archetypes(html: str) -> dict[int, str]:
    """`{deck_id: nome do arquétipo}` da página de um evento.

    É a correcção de 2026-10-02, e o defeito que ela fecha está escrito em dois
    sítios: o `meta_coverage._name_for` dizia *"a fonte não nos dá o nome do
    arquétipo — o mtgtop8 tem `.dec` de cartas e não de rótulos"*, e era falso. A
    página do evento dá o nome ao lado de cada deck; o que não o dava era o
    `.dec`, que é o único ficheiro que a recolha abria por deck. Por isso o nome
    vem da página do EVENTO — uma por evento, não uma por deck.

    Um nome só se aceita à PRIMEIRA vez que aparece (o mesmo deck tem vários links
    por linha) e nunca se inventa: um link sem texto, ou com a seta do deck que
    está aberto, não conta. Os `&amp;` do mtgtop8 estão cobertos, como no
    `RE_DECK`.
    """
    import html as _html                                        # noqa: PLC0415
    out: dict[int, str] = {}
    for m in RE_DECK_NOME.finditer(html):
        did, cru = int(m.group(1)), m.group(2).strip()
        if did in out or cru in _NAO_NOME:
            continue
        nome = _html.unescape(cru).strip()
        if nome and nome not in _NAO_NOME:
            out[did] = nome
    return out


def parse_event_meta(html: str) -> dict:
    """Nome e data do evento a partir da página do evento."""
    nome = None
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        nome = m.group(1).split("@")[0].strip() or None
    dia = None
    for m in RE_DATE.finditer(html):
        d, mth, y = (int(x) for x in m.groups())
        try:
            dia = date(2000 + y, mth, d).isoformat()
        except ValueError:
            # dd/mm/yy é o formato do mtgtop8, mas o regex apanha qualquer
            # nn/nn/nn da página. Um número que não é data rebentava aqui, e
            # como o harvest só protege os pedidos HTTP, a exceção subia e
            # matava a recolha do FORMATO inteiro por causa de um evento.
            continue
        break
    players = None
    # Peso do evento. O mtgtop8 é de origem francesa e algumas páginas dizem
    # "joueurs" em vez de "players"; sem contagem fica None (e uma lista
    # presencial sem contagem NÃO conta para o metagame — não se assume nada).
    m = re.search(r"(\d+)\s*(?:players|joueurs)", html, re.I)
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


def comandantes_do_dec(text: str) -> list[str]:
    """Os nomes que vinham em `SB:` — nos formatos de comandante, o COMANDANTE.

    O `parse_dec` manda-os para o mainboard (é lá que contam para as 100 cartas e
    é isso que faz o `content_hash` coincidir com o do mtgo.com), e com isso a
    informação de QUAL das 100 é o comandante era deitada fora. Lê-se aqui, do
    mesmo texto, para `decklists.commander` a poder guardar — ver
    `mtgvault/consenso.py`.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        m = DEC_LINE.match(line)
        if m and m.group(1):
            out.append(DEC_SET_PREFIX.sub("", m.group(3)).strip())
    return out


def fetch_deck(deck_id: int,
               commander_format: bool) -> tuple[list[tuple[str, str, int]], list[str]]:
    """`(cartas, nomes do SB)`. O segundo só interessa num formato de comandante
    — é de lá que sai o `decklists.commander` (2026-10-01)."""
    texto = _get("/dec", d=deck_id)
    return parse_dec(texto, commander_format), comandantes_do_dec(texto)


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
        # Liga que não conta naquele formato (regra 2026-09-07): salta o evento
        # inteiro ANTES de pedir os .dec — são até 16 pedidos poupados por evento.
        # O mtgtop8 re-hospeda as ligas do MTGO ("Premodern event - MTGO League").
        if (sources.event_tier("mtgtop8", meta["event_name"] or "") == "League"
                and "League" not in sources.metagame_rules(fmt)["tiers"]):
            continue
        jogadores = parse_deck_entries(pagina)
        # O NOME DO ARQUÉTIPO (2026-10-02): está nesta mesma página, que já foi
        # pedida. Não custa um pedido a mais e é a informação que a recolha andava
        # a deitar fora — ver `parse_deck_archetypes`.
        arquetipos = parse_deck_archetypes(pagina)
        for pos, did in enumerate(parse_deck_ids(pagina)[:max_decks_per_event], 1):
            if con.execute("SELECT 1 FROM decklists WHERE source = 'mtgtop8' "
                           "AND source_key = ?", (str(did),)).fetchone():
                continue
            try:
                cartas, do_sb = fetch_deck(did, is_cmd)
            except requests.RequestException:
                continue
            # O comandante, nos formatos de comandante: o `SB:` do .dec. Vai para
            # a coluna `decklists.commander` ANTES de se perder no main.
            comandante = (consenso.nome_do_comandante(con, do_sb) if is_cmd else None)
            # store_decklist descarta se esta lista já cá estiver vinda do
            # mtgo.com — o mtgtop8 re-hospeda muitos eventos de MTGO. O placement
            # vem da posição (a página lista por classificação).
            if sources.store_decklist(
                con, source="mtgtop8", source_key=str(did), fmt=fmt,
                cards=cartas, event_name=meta["event_name"] or "",
                event_date=meta["event_date"] or date.today().isoformat(),
                player=jogadores.get(did, ""), placement=_bracket(pos),
                event_players=meta.get("players"), commander=comandante,
                arquetipo=arquetipos.get(did), arquetipo_de="evento",
                url=f"{BASE}/event?e={eid}&d={did}&f={code}",
            ):
                novas += 1
        con.commit()
    return novas


# O url guardado em cada lista é ".../event?e=<evento>&d=<deck>&f=<código>".
RE_URL_EVENT = re.compile(r"[?&]e=(\d+).*?[?&]f=([A-Za-z]+)")


def backfill_event_players(con: sqlite3.Connection, max_events: int = 40) -> str:
    """Preenche `event_players` nos presenciais do mtgtop8 que ficaram sem ele.

    Faz falta porque uma lista presencial SEM contagem não conta para o metagame
    (regra do André, 2026-09-07: presenciais só a partir de 64 jogadores) — e
    dois terços das listas do mtgtop8 estavam a NULL, muitas delas de antes de a
    coluna existir. Vai à página do evento, que é onde o nº aparece.

    Poucos eventos por corrida (`max_events`) e com o 1 pedido/s que o `_get` já
    respeita, para não martelar um site pequeno. Quando a página não mostra
    contagem nenhuma grava-se **0**: não conta na mesma (0 < 64) e a corrida do
    dia seguinte não volta a pedir a mesma página para nada.
    """
    porevento: dict[tuple[int, str], list[int]] = {}
    for r in con.execute(
        """SELECT id, url, event_date FROM decklists
            WHERE source = 'mtgtop8' AND event_players IS NULL AND url IS NOT NULL
            ORDER BY event_date DESC, id DESC"""):
        m = RE_URL_EVENT.search(r["url"])
        if m:
            porevento.setdefault((int(m.group(1)), m.group(2)), []).append(r["id"])
    if not porevento:
        return "nada por preencher"

    feitos = achados = 0
    for (eid, code), ids in list(porevento.items())[:max_events]:
        try:
            players = parse_event_meta(_get("/event", e=eid, f=code))["players"]
        except requests.RequestException:
            continue
        feitos += 1
        if players:
            achados += 1
        marcas = ",".join("?" * len(ids))
        con.execute(f"UPDATE decklists SET event_players = ? WHERE id IN ({marcas})",
                    [players or 0, *ids])
        con.commit()
    return (f"{feitos} eventos vistos ({achados} com contagem), "
            f"{len(porevento) - feitos} por fazer")


def eventos_por_recuperar(con: sqlite3.Connection) -> dict[tuple[int, str], list[int]]:
    """`{(evento, código): [deck_id, ...]}` das listas do mtgtop8 ainda sem nome.

    O que decide que uma lista está «por recuperar» é as DUAS colunas estarem a
    NULL: logo que a página do evento for lida, cada lista fica com nome ou com
    `arquetipo_fonte_de = 'sem-nome'`, e nunca mais entra aqui. É por isso que
    isto é retomável sem ficheiro de progresso nenhum — o progresso é a própria
    base, como no `backfill_event_players`, que grava `0` quando a página não
    mostra contagem.
    """
    out: dict[tuple[int, str], list[int]] = {}
    for r in con.execute(
        """SELECT source_key, url FROM decklists
            WHERE source = 'mtgtop8' AND url IS NOT NULL
              AND arquetipo_fonte IS NULL AND arquetipo_fonte_de IS NULL
            ORDER BY event_date DESC, id DESC"""):
        m = RE_URL_EVENT.search(r["url"])
        if m and (r["source_key"] or "").isdigit():
            out.setdefault((int(m.group(1)), m.group(2)), []).append(int(r["source_key"]))
    return out


def backfill_archetype_names(con: sqlite3.Connection,
                             max_events: int | None = None) -> str:
    """Recupera o nome do arquétipo das listas de mtgtop8 que já estão na base.

    **UMA PÁGINA POR EVENTO, nunca uma por deck.** As 2 635 listas de mtgtop8 da
    base de 2026-10-02 vivem em 413 eventos, e a página do evento traz os nomes de
    todos os decks dele de uma vez: 413 pedidos em vez de 2 635. Com o 1 pedido/s
    que o `_get` já respeita, são ~7 minutos.

    É IDEMPOTENTE e RETOMÁVEL: `commit` por evento, e um evento feito não volta a
    ser pedido (ver `eventos_por_recuperar`). Um evento cuja página não responda
    fica para a corrida seguinte — não se marca `sem-nome` a quem não foi lido.

    A lista casa-se pelo `source_key`, que para o mtgtop8 **é** o `deck_id` — a
    mesma chave que o nome traz na página. Pelo `url` dava o mesmo trabalho com
    mais uma coisa a poder desalinhar-se.
    """
    porevento = eventos_por_recuperar(con)
    if not porevento:
        return "nada por recuperar"

    alvos = list(porevento.items())
    if max_events:
        alvos = alvos[:max_events]
    eventos = nomeadas = sem_nome = falhados = 0
    for (eid, code), decks in alvos:
        try:
            nomes = parse_deck_archetypes(_get("/event", e=eid, f=code))
        except requests.RequestException:
            falhados += 1
            continue
        eventos += 1
        for did in decks:
            nome = nomes.get(did)
            con.execute(
                """UPDATE decklists SET arquetipo_fonte = ?, arquetipo_fonte_de = ?
                    WHERE source = 'mtgtop8' AND source_key = ?""",
                (nome, "recuperado" if nome else "sem-nome", str(did)))
            if nome:
                nomeadas += 1
            else:
                sem_nome += 1
        con.commit()
    falta = len(porevento) - eventos
    return (f"{eventos} eventos lidos, {nomeadas} listas com nome, "
            f"{sem_nome} sem nome na pagina, {falhados} eventos a falhar, "
            f"{falta} por fazer")


def archetype_decks(archetype_id: int, fmt: str = "duel-commander") -> list[int]:
    """Ids das listas de um arquétipo específico (ex.: Cloud = 2629)."""
    code = FORMAT_CODES[fmt.lower()]
    return parse_deck_ids(_get("/archetype", a=archetype_id, f=code))
