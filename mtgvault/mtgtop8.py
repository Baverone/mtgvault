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
# O caminho de volta (`MO` -> `modern`): a `mtgtop8_eventos` guarda o FORMATO e o
# url de uma lista guarda o CÓDIGO.
_FORMATO_DO_CODIGO = {c: f for f, c in FORMAT_CODES.items()}
# Fonte única em sources: o mtgo e o mtgtop8 têm de tratar o comandante da
# mesma maneira, senão a mesma lista teria content_hash diferente e a dedup
# entre as fontes deixaria de funcionar.
COMMANDER_FORMATS = sources.COMMANDER_FORMATS

# Apanha o id do evento venha ele sozinho (páginas de formato) ou
# dentro de um link de deck (páginas de arquétipo).
RE_EVENT = re.compile(r"event\?e=(\d+)")
# AS LINHAS DO ÍNDICE (2026-10-04). A página de formato traz uma tabela
# «LAST 20 EVENTS» em que cada linha diz MUITO mais do que o id — e a recolha
# lia só o id:
#
#   <tr class=hover_tr>
#     <td ...><img src=/graph/online/paper.png ... title="Paper"></td>
#     <td ...><a href=event?e=91582&f=MO>Win-A-Box</a> @ <a class=und
#         href=event?e=91582&f=MO>Infinity Hobbies (Las Pinas, Philippines)</a></td>
#     <td ...><img src=/graph/star.png></td>
#     <td ... class=S12>03/10/26</td>
#   </tr>
#
# É o mesmo padrão do comandante (01/10) e do nome do arquétipo (02/10): a fonte
# dá a informação e a recolha perde-a. Com o NOME na mão, uma liga salta-se SEM
# se pedir a página do evento — ver `harvest`.
RE_LINHA_INDICE = re.compile(r"<tr class=hover_tr>(.*?)</tr>", re.S)
RE_LINHA_EVENTO = re.compile(r"event\?e=(\d+)&(?:amp;)?f=[A-Za-z]*>([^<]*)</a>")
RE_LINHA_LOJA = re.compile(
    r"class=und\s+href=event\?e=\d+&(?:amp;)?f=[A-Za-z]*>([^<]*)</a>")
# A data da linha (dd/mm/yy) e a paginação do índice (`?f=MO&cp=2`). Uma linha
# SEM data não é um evento do índice: a mesma página traz 348 `event?e=` dentro
# do «METAGAME BREAKDOWN», e esses não são uma lista cronológica de eventos.
RE_LINHA_DATA = re.compile(r"class=S12>\s*(\d{2})/(\d{2})/(\d{2})")
RE_PAGINA_INDICE = re.compile(r"[?&]cp=(\d+)")
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


def parse_event_rows(html: str) -> list[dict]:
    """As LINHAS do índice de um formato: id, nome, data, papel/online, estrelas.

    O `parse_event_ids` continua a existir e a devolver só ids (há código e testes
    que o chamam) — mas devolve **375 ids** numa página de Modern, dos quais só
    **20** são eventos do índice: os outros vêm dos links do «METAGAME BREAKDOWN».
    Com `[:max_events]` isso nunca se notou, e é precisamente o que torna frágil ir
    mais fundo. Aqui uma linha só conta se tiver as DUAS coisas que um evento do
    índice tem: um link `event?e=…>nome</a>` **e** uma data `dd/mm/yy`.

    `nome` é o nome CRU do mtgtop8 («Regional Championship»), sem o prefixo
    «Modern event - » que a página do evento põe no `<title>`. Os padrões de
    `e_grande` casam nos dois, porque são procuras por dentro do nome.
    """
    import html as _html                                        # noqa: PLC0415
    out: list[dict] = []
    for bloco in RE_LINHA_INDICE.findall(html):
        m = RE_LINHA_EVENTO.search(bloco)
        d = RE_LINHA_DATA.search(bloco)
        if not m or not d:
            continue
        dia, mes, ano = (int(x) for x in d.groups())
        try:
            data = date(2000 + ano, mes, dia).isoformat()
        except ValueError:
            data = None
        loja = RE_LINHA_LOJA.search(bloco)
        out.append({
            "id": int(m.group(1)),
            "nome": _html.unescape(m.group(2)).strip(),
            "data": data,
            "loja": _html.unescape(loja.group(1)).strip() if loja else None,
            # O ícone da 1.ª célula diz se o evento é de PAPEL ou do MTGO. É a
            # informação de que o `event_tier` anda à procura no nome.
            "online": "mtgo.png" in bloco,
            # A classificação do próprio mtgtop8 (1 a 4 estrelas). Guarda-se por
            # ser informação da fonte; hoje nada decide por ela — quem decide o
            # peso continua a ser o `event_tier` + `event_players`.
            "estrelas": bloco.count("star.png"),
        })
    return out


def parse_paginas_indice(html: str) -> int:
    """Quantas páginas tem o índice, lido da própria paginação da página 1.

    O mtgtop8 serve-a como `<a href=?f=MO&meta=54&cp=2>2</a> … cp=3`. O `meta=` é
    o período do metagame e **não é preciso** (verificado a 2026-10-04: `cp=2` com
    e sem `meta` devolve byte por byte a mesma página).
    """
    return max([1, *(int(m.group(1)) for m in RE_PAGINA_INDICE.finditer(html))])


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
# NUNCA PERDER UM TORNEIO DE PAPEL GRANDE  (André, 2026-10-04)
# ---------------------------------------------------------------------------
# Ele joga o RC Ghent de Modern a 9-11/10 e o que lhe falta são os torneios de
# PAPEL grandes. O mtgtop8 publica-os — o problema era a recolha: `harvest` lia
# os `max_events` PRIMEIROS ids do índice e nunca voltava atrás. Em Modern entram
# várias ligas e challenges de MTGO por dia; um RC publicado hoje ficava fora
# para sempre se oito eventos mais novos aparecessem nas horas seguintes.
#
# OS PADRÕES SAEM DA BASE DELE, NÃO DA MINHA MEMÓRIA (medido a 2026-10-04 nos
# presenciais de mtgtop8 com 64+ jogadores):
#   1 486 j  'Modern event - Regional Championship'          <- o que ele precisa
#     921 j  'Modern event - Magic Spotlight: The Hobbit'
#     344 j  'Modern event - $uper $unday ReCQ 10:00am'
#     218 j  'Premodern event - European Championship 2026'
#     191 j  'Premodern event - Czech Nationals 2026'
#     168 j  'Standard event - Champions Cup Premium Qualifier'
#     221 j  'Modern event - MTGO RC Qualifier'
# São REGEX e não substrings por causa dos curtos: `rc` como substring casa em
# «Arc», «Circuit», «Marché». Um padrão que não compile não mata a recolha —
# trata-se como texto literal e diz-se (`padroes_estragados`).
PADROES_GRANDES = [
    r"championship",        # Regional / European / National / Store Championship
    r"\bnationals?\b",      # 'Czech Nationals 2026' não diz "championship"
    r"champions cup",
    r"pro tour",
    r"\bworlds?\b",
    r"magic spotlight",
    r"grand prix",
    r"eternal weekend",
    r"qualifier",
    r"\brecq\b",            # '$uper $unday ReCQ' = Regional Championship Qualifier
    r"\brcq?\b",            # 'MTGO RC Qualifier', 'RC Hangzhou Side Event'
    r"last sun",
]
# O TECTO DE LISTAS de um torneio grande. **64 não é um número à sorte: é o que a
# página serve.** Medido a 2026-10-04 nas páginas reais — o RC de Modern (1 486
# jogadores) tem **64** links de deck e a base dele tinha **16**; o Magic
# Spotlight (921 j) o mesmo. Eram 48 listas do maior torneio de papel de Modern a
# ficar de fora por causa do tecto. E 64 é o fim da escala que o `_bracket` já
# conhecia («33-64»).
LISTAS_GRANDES = 64
# ... mas só quando o evento é mesmo grande. O tecto alto pendurado só no NOME
# punha 64 pedidos `.dec` num «Store Championship» de 25 jogadores — e um
# presencial com menos de 64 jogadores **não conta para o metagame** (regra do
# André, 2026-09-07), por isso essas listas não alimentavam página nenhuma. O nº
# de jogadores vem da página do evento, que já foi pedida ANTES do primeiro
# `.dec`: a decisão não custa um pedido.
MIN_JOGADORES_GRANDE = 64
# Quantas páginas do índice se lêem. A paginação existe (`?f=MO&cp=2`, `cp=3`) e
# dá 58 eventos em Modern, contra os 20 da primeira. São +2 pedidos por formato e
# por corrida, e é o que torna possível apanhar um RC que já não está no topo.
PAGINAS_INDICE = 3
# O tecto que a recolha usava antes disto. Serve para a MEMÓRIA saber que um
# evento já visto foi visto com o tecto antigo e por isso vale a pena voltar lá
# quando ele é grande — é assim que as 48 listas do RC que já está na base são
# recuperadas sem um único passo à mão.
TECTO_ANTIGO = 16
# Quantos eventos JÁ VISTOS se revisitam por corrida e por formato. O travão é
# por respeito e está medido: semeada a base dele (401 eventos de mtgtop8), são
# **11** os que valem uma revisita — o RC de Modern (1 486 jogadores, 16 das 64
# listas na base), o Magic Spotlight (921), o ReCQ (344), o MTGO RC Qualifier
# (221), a European Championship de Premodern (218), o RC Super Qualifier de
# Pioneer (212), as Czech Nationals (191), a Champions Cup (168) e mais três.
# Fazê-los todos de uma vez eram **até 564 pedidos `.dec` numa noite**, e isso
# num site pequeno e gratuito não se faz. Um por formato e por corrida: o backlog
# esgota-se em quatro noites, pela ordem do nº de jogadores — o RC entra na
# primeira, que é o que interessa para Ghent. É a mesma disciplina do
# `backfill_event_players(max_events=40)` e do `backfill_archetype_names(60)`.
REVISITAS_POR_CORRIDA = 1

padroes_estragados: list[str] = []


def regras_grandes(cfg: dict | None = None) -> dict:
    """As regras do «torneio de papel grande», num sítio só.

    Omissões no código (para os testes e uma base nova funcionarem sem ficheiro) e
    o `colecao_config.json → mtgtop8` a ganhar, como no `metagame_rules`.
    """
    # O `_sem_comentarios` é o do `sources` e não uma cópia: as chaves `_…` do
    # config são a explicação em português ao lado de cada regra, e descartá-las
    # de duas maneiras diferentes era arranjar um sítio para divergirem.
    sec = sources._sem_comentarios(
        (cfg if cfg is not None else sources.config()).get("mtgtop8"))
    grandes = sources._sem_comentarios(sec.get("grandes"))

    # `is None` e nunca `or`: uma lista VAZIA de padrões tem de querer dizer
    # «nenhum», e com `grandes.get("padroes") or PADROES_GRANDES` uma lista vazia
    # cai nas omissões — ou seja, esvaziá-la no config não desligava nada. O
    # interruptor é esvaziar a lista (como o `cartas_vigiadas`), por isso tem de
    # ser respeitado à letra. Apanhado pelo
    # `caso_sem_padroes_a_recolha_volta_ao_que_era`.
    def _ou(chave, omissao, de=sec):
        v = de.get(chave)
        return omissao if v is None else v

    return {
        "paginas_indice": int(_ou("paginas_indice", PAGINAS_INDICE)),
        "revisitas_por_corrida": int(_ou("revisitas_por_corrida",
                                         REVISITAS_POR_CORRIDA)),
        "padroes": list(_ou("padroes", PADROES_GRANDES, grandes)),
        "listas_por_evento": int(_ou("listas_por_evento", LISTAS_GRANDES, grandes)),
        "min_jogadores": int(_ou("min_jogadores", MIN_JOGADORES_GRANDE, grandes)),
    }


def _compilar(padroes) -> list[re.Pattern]:
    out = []
    for p in padroes:
        try:
            out.append(re.compile(p, re.I))
        except re.error:
            if p not in padroes_estragados:
                padroes_estragados.append(p)
            out.append(re.compile(re.escape(p), re.I))
    return out


def e_grande(nome: str, cfg: dict | None = None) -> bool:
    """«Isto parece um torneio de papel importante?» — A PERGUNTA VIVE AQUI.

    Dois consumidores fazem-na (o filtro da recolha e o tecto de listas) e um
    terceiro lê-lhe o resultado da base (o aviso do daily). Espalhá-la era a lição
    do `event_tier`, do `e_foil` e do `precos.sql()`: dois sítios a responder à
    mesma pergunta discordam um dia qualquer, em silêncio.
    """
    return any(r.search(nome or "") for r in _compilar(regras_grandes(cfg)["padroes"]))


def tecto_do_evento(grande: bool, players: int | None, tecto_normal: int,
                    cfg: dict | None = None) -> int:
    """Quantas listas se lêem deste evento. `players` vem da página do evento."""
    r = regras_grandes(cfg)
    if grande and (players or 0) >= r["min_jogadores"]:
        return max(tecto_normal, r["listas_por_evento"])
    return tecto_normal


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


# A MARCA de que a semente já correu. É uma linha com `event_id = 0` num formato
# que não existe — o `memoria_dos_eventos` filtra por formato e nunca a vê.
#
# A guarda NÃO pode ser «a tabela está vazia», e isso foi apanhado por um teste: um
# evento cujo `.dec` falhou não se marca (de propósito), e se ele for o único
# evento da base a tabela fica vazia — a semente voltava a correr na corrida
# seguinte, deduzia esse evento das listas que ele já deixou e marcava-o com o
# tecto antigo, ou seja **tapava a repetição que a não-marcação existe para
# garantir**. A semente é um acontecimento único da migração, e tem de o dizer.
MARCA_SEMEADO = (0, "_semeado")


def semear_memoria(con: sqlite3.Connection) -> int:
    """Semeia a `mtgtop8_eventos` com os eventos que as listas da base já provam.

    Corre UMA VEZ (ver `MARCA_SEMEADO`). Sem isto, a primeira corrida com a
    memória voltava a pedir a página de cada um dos ~401 eventos que já estão na
    base só para os registar.

    Semeia com o **`TECTO_ANTIGO`** e `completo = 0`, que é a verdade: não se sabe
    quantos links de deck a página tinha. A consequência é exactamente a desejada —
    um evento normal (tecto 16 também hoje) não se revisita, e um evento GRANDE
    (tecto 64) revisita-se **uma vez** e completa-se. É por aqui que as 48 listas
    que faltam ao `Modern event - Regional Championship` entram sozinhas.

    O `grande` semeia-se com o `e_grande` do NOME GRAVADO, e isso é essencial: as
    revisitas saem da MEMÓRIA e não do índice (ver `revisitas_pendentes`), por isso
    é esta coluna que decide se se volta lá. Um ensaio de ponta a ponta apanhou-o —
    com o `grande` a 0 o RC nunca era revisitado e as 48 listas não vinham.
    """
    if con.execute("SELECT 1 FROM mtgtop8_eventos WHERE event_id = ? AND format = ?",
                   MARCA_SEMEADO).fetchone():
        return 0
    con.execute("INSERT OR IGNORE INTO mtgtop8_eventos (event_id, format, visto_em) "
                "VALUES (?,?,?)", (*MARCA_SEMEADO, date.today().isoformat()))
    vistos: dict[tuple[int, str], dict] = {}
    for r in con.execute(
        """SELECT url, event_name, event_date, event_players FROM decklists
            WHERE source = 'mtgtop8' AND url IS NOT NULL"""):
        m = RE_URL_EVENT.search(r["url"])
        if not m:
            continue
        fmt = _FORMATO_DO_CODIGO.get(m.group(2), m.group(2))
        vistos.setdefault((int(m.group(1)), fmt), {
            "nome": r["event_name"], "data": r["event_date"],
            "players": r["event_players"]})
    if not vistos:
        con.commit()
        return 0
    con.executemany(
        """INSERT OR IGNORE INTO mtgtop8_eventos
            (event_id, format, event_name, event_date, grande, players,
             na_pagina, tecto, completo, visto_em)
            VALUES (?,?,?,?,?,?,NULL,?,0,?)""",
        [(eid, f, d["nome"], d["data"], int(e_grande(d["nome"] or "")),
          d["players"], TECTO_ANTIGO, d["data"])
         for (eid, f), d in vistos.items()])
    con.commit()
    return len(vistos)


def memoria_dos_eventos(con: sqlite3.Connection, fmt: str) -> dict[int, dict]:
    """`{event_id: linha}` do que já se processou naquele formato."""
    return {r["event_id"]: dict(r) for r in con.execute(
        "SELECT * FROM mtgtop8_eventos WHERE format = ? AND event_id > 0", (fmt,))}


def revisitas_pendentes(con: sqlite3.Connection, fmt: str, tecto_normal: int,
                        cfg: dict | None = None) -> list[dict]:
    """Os eventos GRANDES a que falta voltar, **lidos da MEMÓRIA e não do índice**.

    Um ensaio de ponta a ponta sobre o índice real apanhou o defeito que esta
    função corrige: o `Modern event - Regional Championship` é de **12/09** e o
    índice de hoje cobre **20/09 a 03/10** — ou seja, o evento que mais interessa
    recuperar **já não está no índice**, e uma revisita escolhida entre os
    candidatos do índice nunca lhe chegava. As 48 listas que faltam não vinham.

    Daqui saem só os `grande = 1` (um evento normal não teve o tecto mudado, logo
    não há nada a recuperar) e pela ordem do nº de jogadores — o RC de 1 486 vem
    primeiro. O travão é do chamador.
    """
    out = [dict(r) for r in con.execute(
        "SELECT * FROM mtgtop8_eventos WHERE format = ? AND event_id > 0 "
        "AND grande = 1 AND completo = 0", (fmt,))]
    out = [r for r in out if por_fazer(r, True, tecto_normal, cfg)]
    out.sort(key=lambda r: -(r.get("players") or 0))
    return out


def por_fazer(linha: dict | None, grande: bool, tecto_normal: int,
              cfg: dict | None = None) -> bool:
    """Vale a pena (re)visitar este evento?

    Nunca visto -> sim. Completo -> não. Senão, só se o tecto de HOJE for maior do
    que o que se aplicou na última vez: é o caso do evento visto com o tecto antigo
    (16) que entretanto passou a ser reconhecido como grande (64).

    **O tecto de hoje calcula-se com os jogadores LEMBRADOS, não com um palpite
    optimista.** A primeira versão usava o tecto grande para decidir e o tecto real
    para gravar, e um evento com nome de torneio grande e poucos jogadores — um
    «Store Championship» de 25 — ficava com `tecto = 16` gravado contra um `64`
    esperado e era revisitado **todas as noites, para sempre**. Com o número de
    jogadores à mão (a coluna `players`, que o `backfill_event_players` também
    preenche) a conta é a mesma dos dois lados e a revisita acontece uma vez só.
    """
    if linha is None:
        return True
    if linha.get("completo"):
        return False
    tecto_hoje = tecto_do_evento(grande, linha.get("players"), tecto_normal, cfg)
    return int(linha.get("tecto") or 0) < tecto_hoje


def _registar_evento(con: sqlite3.Connection, eid: int, fmt: str, *, nome: str,
                     data: str | None, grande: bool, players: int | None,
                     na_pagina: int, tecto: int) -> None:
    con.execute(
        """INSERT INTO mtgtop8_eventos
            (event_id, format, event_name, event_date, grande, players,
             na_pagina, tecto, completo, visto_em)
            VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(event_id, format) DO UPDATE SET
            event_name = excluded.event_name, event_date = excluded.event_date,
            grande = excluded.grande, players = excluded.players,
            na_pagina = excluded.na_pagina,
            tecto = MAX(tecto, excluded.tecto),
            completo = excluded.completo, visto_em = excluded.visto_em""",
        (eid, fmt, nome, data, int(grande), players, na_pagina, tecto,
         int(na_pagina <= tecto), date.today().isoformat()))


def candidatos_do_indice(linhas: list[dict], fmt: str, max_events: int,
                         cfg: dict | None = None) -> tuple[list[dict], int]:
    """Que eventos do índice vale a pena abrir. Devolve `(candidatos, ligas)`.

    **FILTRA ANTES DE PEDIR**, e é aqui que a mudança se paga. Até 2026-10-04 a
    liga era saltada DEPOIS de se pedir a página do evento
    (`if sources.event_tier(...) == "League"`), por isso cada liga gastava um dos
    `max_events` lugares **e** um pedido. Com o nome vindo do índice, uma liga
    custa zero — e os lugares rendem o dobro, porque em Modern metade dos eventos
    recentes são ligas de MTGO.

    Um evento GRANDE entra **esteja onde estiver** no índice, mesmo em 20.º lugar:
    é a razão de ser desta função. Os outros entram pela ordem do índice, até
    `max_events`.
    """
    conta_ligas = "League" in sources.metagame_rules(fmt)["tiers"]
    normais, grandes, ligas = [], [], 0
    for li in linhas:
        # O `event_tier` é o de sempre e lê-se do NOME — a mesma função que o
        # `store_decklist` usa, para a recolha e a base não discordarem.
        if sources.event_tier("mtgtop8", li["nome"]) == "League" and not conta_ligas:
            ligas += 1
            continue
        li = {**li, "grande": e_grande(li["nome"], cfg)}
        (grandes if li["grande"] else normais).append(li)
    # Os grandes à frente: num índice com 58 eventos, um RC publicado há dez dias
    # tem de ser aberto antes de um torneio de loja de ontem.
    escolhidos = grandes + normais[:max_events]
    vistos, out = set(), []
    for li in escolhidos:
        if li["id"] not in vistos:
            vistos.add(li["id"])
            out.append(li)
    return out, ligas


def harvest(con: sqlite3.Connection, fmt: str, max_events: int = 8,
            max_decks_per_event: int = 16, paginas: int | None = None,
            cfg: dict | None = None) -> int:
    """Recolhe as decklists mais recentes de um formato. Devolve nº de novas.

    Os limites existem por respeito: o mtgtop8 é um site pequeno e gratuito.
    Com 8 eventos por dia por formato, ao fim de um mês tens amostra que chegue
    para a análise de core/tech.

    DESDE 2026-10-04 (André: *"o mtgtop8 acaba por publicar esses torneios"*) são
    três coisas a mais, e as três POUPAM pedidos em vez de os gastar:
      1. lê-se o índice INTEIRO (`PAGINAS_INDICE` páginas, 58 eventos em Modern
         contra 20) — +2 pedidos por formato;
      2. a LIGA salta-se pelo nome, do índice, **sem se pedir a página do evento**
         — eram até 1 + 16 pedidos por liga, e em Modern há uma por dia;
      3. um evento já processado não se volta a pedir (`mtgtop8_eventos`), que é o
         que torna (1) barato em vez de caro.
    E um torneio de papel grande entra **esteja onde estiver no índice**, com o
    tecto de listas do `tecto_do_evento` em vez dos 16 de sempre.
    """
    fmt = fmt.lower()
    code = FORMAT_CODES.get(fmt)
    if not code:
        raise ValueError(f"Formato sem equivalente no mtgtop8: {fmt}")
    is_cmd = fmt in COMMANDER_FORMATS
    semear_memoria(con)
    regras = regras_grandes(cfg)
    n_paginas = max(1, int(paginas if paginas is not None else regras["paginas_indice"]))

    # Um `while` e não um `for`: a página 1 diz quantas páginas o índice tem e o
    # tecto encurta a meio. Com um `for range(1, n+1)`, mexer no `n` lá dentro não
    # encurta o `range` que já foi criado — e pediam-se páginas que não existem
    # (apanhado pelo `caso_o_indice_le_mais_do_que_uma_pagina`).
    linhas: list[dict] = []
    pag = 1
    while pag <= n_paginas:
        try:
            html = (_get("/format", f=code) if pag == 1
                    else _get("/format", f=code, cp=pag))
        except requests.RequestException:
            break
        linhas.extend(parse_event_rows(html))
        if pag == 1:
            n_paginas = min(n_paginas, parse_paginas_indice(html))
        pag += 1

    candidatos, _ligas = candidatos_do_indice(linhas, fmt, max_events, cfg)
    memoria = memoria_dos_eventos(con, fmt)
    # O QUE SE ABRE VEM DE DUAS FONTES DIFERENTES, e isso é o desenho:
    #  - os NOVOS saem do ÍNDICE (é lá que está o que apareceu hoje) e fazem-se
    #    todos — é o trabalho de sempre;
    #  - as REVISITAS saem da MEMÓRIA e **não do índice**, porque o evento que mais
    #    interessa recuperar já não está lá: o RC de Modern é de 12/09 e o índice
    #    de hoje começa a 20/09. Levam travão (`revisitas_por_corrida`), pela ordem
    #    do nº de jogadores — sem ele a primeira corrida pedia até 564 `.dec`.
    por_abrir = [li for li in candidatos if li["id"] not in memoria]
    # Um evento do índice que JÁ esteja na memória e precise de revisita entra
    # também por aqui — é uma lista só, com um travão só. O nome do índice ganha
    # quando existe (é mais curto e mais fresco do que o `<title>` gravado).
    do_indice = {li["id"]: li for li in candidatos}
    for r in revisitas_pendentes(con, fmt, max_decks_per_event,
                                 cfg)[:max(0, regras["revisitas_por_corrida"])]:
        li = do_indice.get(r["event_id"])
        por_abrir.append({"id": r["event_id"], "grande": True,
                          "nome": (li or {}).get("nome") or r["event_name"] or "",
                          "data": (li or {}).get("data") or r["event_date"]})

    novas = 0
    for li in por_abrir:
        eid = li["id"]
        try:
            pagina = _get("/event", e=eid, f=code)
        except requests.RequestException:
            # Um evento que falha NÃO se marca — perder um RC para sempre por uma
            # falha de rede de um segundo era o preço de simplificar aqui (é a
            # regra do `backfill_archetype_names`).
            continue
        meta = parse_event_meta(pagina)
        players = meta.get("players")
        tecto = tecto_do_evento(li["grande"], players, max_decks_per_event, cfg)
        jogadores = parse_deck_entries(pagina)
        # O NOME DO ARQUÉTIPO (2026-10-02): está nesta mesma página, que já foi
        # pedida. Não custa um pedido a mais e é a informação que a recolha andava
        # a deitar fora — ver `parse_deck_archetypes`.
        arquetipos = parse_deck_archetypes(pagina)
        todos = parse_deck_ids(pagina)
        falhou_um_dec = False
        for pos, did in enumerate(todos[:tecto], 1):
            if con.execute("SELECT 1 FROM decklists WHERE source = 'mtgtop8' "
                           "AND source_key = ?", (str(did),)).fetchone():
                continue
            try:
                cartas, do_sb = fetch_deck(did, is_cmd)
            except requests.RequestException:
                falhou_um_dec = True
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
                event_players=players, commander=comandante,
                arquetipo=arquetipos.get(did), arquetipo_de="evento",
                url=f"{BASE}/event?e={eid}&d={did}&f={code}",
            ):
                novas += 1
        # O REGISTO VEM NO FIM, E SÓ SE NENHUM `.dec` FALHOU. Registá-lo antes do
        # ciclo era uma regressão face ao código antigo: esse não tinha memória e
        # por isso voltava a pedir os `.dec` que faltassem na corrida seguinte (o
        # crivo é por deck, contra a `decklists`). Com a memória escrita à cabeça,
        # um `.dec` que falhasse deixava a lista a faltar **para sempre**. Um
        # evento meio lido não se marca — é a mesma regra do evento cuja página
        # falha, e do `backfill_archetype_names`.
        if not falhou_um_dec:
            _registar_evento(con, eid, fmt, nome=meta["event_name"] or li["nome"],
                             data=meta["event_date"] or li["data"],
                             grande=li["grande"], players=players,
                             na_pagina=len(todos), tecto=tecto)
        con.commit()
    return novas


def grandes_de_hoje(con: sqlite3.Connection, dia: str | None = None) -> list[dict]:
    """Os torneios de papel GRANDES que entraram hoje, para o aviso do daily.

    Lê-se da BASE e não de uma variável que atravesse os seis `harvest`: o aviso é
    UM por dia e não um por formato, e quem lhe responde é a mesma tabela que a
    recolha escreveu. Só conta quem passa o `min_jogadores` — um «Store
    Championship» de 25 jogadores não é notícia (e não conta para o metagame).
    """
    dia = dia or date.today().isoformat()
    minimo = regras_grandes()["min_jogadores"]
    return [dict(r) for r in con.execute(
        """SELECT * FROM mtgtop8_eventos
            WHERE grande = 1 AND visto_em = ? AND COALESCE(players, 0) >= ?
            ORDER BY players DESC""", (dia, minimo))]


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
