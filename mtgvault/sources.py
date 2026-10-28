"""Recolha diária de decklists.

COBERTURA POR FORMATO
    Standard, Pioneer, Modern, Legacy, Vintage, Pauper -> mtgo.com  ✔
    Duel Commander, Premodern                          -> mtgo.com  ✔
    cEDH                                               -> só mtgtop8

    O mtgo.com tem mesmo Duel CMDR e Premodern no filtro de formatos. Para
    apanhar também os torneios de papel (que no Duel Commander são a maioria),
    ver o módulo `mtgtop8`.

    O Pauper continua a ser lido, mas só se GUARDA a lista dos jogadores
    vigiados — ver `so_jogadores_vigiados`.

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
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

MTGO_BASE = "https://www.mtgo.com/decklists"
UA = {"User-Agent": "Mozilla/5.0 (compatible; mtgvault/0.1)"}

#: Pausa entre pedidos ao mtgo.com, em segundos. O mtgtop8 sempre teve o ritmo de
#: 1 pedido/s (`mtgtop8._get`) e o mtgo.com **não tinha nenhum** — era um
#: descuido que passou despercebido enquanto a recolha pedia poucas páginas por
#: formato. Passou a contar a 2026-10-05, quando as ligas entraram no Modern: a
#: página de liga publica-se todos os dias e tem 45 a 58 listas, por isso a
#: recolha passou a abrir mais páginas por noite. O mtgo.com **não tem
#: `robots.txt`** (404, sondado nesse dia), logo não há regra escrita a respeitar
#: além do ritmo — e ele já deu dois `read timeout` numa sondagem de 15 pedidos
#: seguidos, o que diz que não gosta de pressa. Zero desliga a pausa (é o que os
#: testes fazem: sem rede não há a quem ser mal-educado).
PAUSA_MTGO = 1.0

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


def _get_mtgo(url: str, tentativas: int = 2) -> requests.Response:
    """Um pedido ao mtgo.com, com a pausa de `PAUSA_MTGO` à frente.

    Dá **uma segunda tentativa** a um erro de rede, e só a esse: o mtgo.com
    responde entre 1 e 31 s e deu `read timeout` em 2 de 15 pedidos na sondagem
    de 2026-10-05. Uma página de liga perdida por um timeout de um segundo
    ficava perdida **para sempre** — a recolha só volta 3 dias atrás
    (`daily.MTGO_DAYS`), e ao quarto dia aquele dia já não se pede. Um erro de
    HTTP (404, 500) não se repete: não é azar, é a página.
    """
    ultimo: requests.RequestException | None = None
    for n in range(max(1, tentativas)):
        if PAUSA_MTGO:
            time.sleep(PAUSA_MTGO * (1 + n))      # a 2.ª espera mais
        try:
            return requests.get(url, headers=UA, timeout=30)
        except requests.RequestException as e:
            ultimo = e
    raise ultimo                                   # type: ignore[misc]


class IndiceFalhou(RuntimeError):
    """O índice de uma fonte (mtgo.com ou mtgtop8) não respondeu — rede ou HTTP.

    NÃO É UM DIA SEM TORNEIOS (2026-10-28). O `harvest-mtgo` ficou «ok, 0
    novas» a 22, 24 e 27/10 (a 27/10 em ~0 s): o erro do índice era engolido e
    devolvia-se `[]`, que é a mesma resposta de um dia sem eventos. O passo
    ficava verde no `job_runs`, a tarefa `ai-pc/tasks/mtgvault-daily` (que só
    chumba com um passo ≠ `ok`) não tinha nada que ver, e ao fim de
    `daily.MTGO_DAYS` noites o dia perdia-se. Agora o índice que não responde
    LEVANTA isto, o `daily._step` grava-o como `erro` e a tarefa fica vermelha.
    O índice que responde sem nada daquele dia continua a ser `[]`, verde."""


def fetch_mtgo_index(day: date) -> list[str]:
    """URLs dos eventos publicados num dia.

    O mtgo.com serve o índice por ano/mês. Tentamos duas formas de URL porque
    o site já mudou de estrutura no passado; a primeira que responder ganha.
    As páginas de evento têm a data no próprio caminho
    (ex.: /decklist/duel-commander-league-2026-07-2210716), por isso filtramos
    por ela.

    Se NENHUMA das duas formas responder (rede ou HTTP), levanta `IndiceFalhou`
    (2026-10-28): basta uma responder para o índice existir, e aí um dia vazio
    é um dia vazio.
    """
    stamp = day.strftime("%Y-%m-%d")
    candidatos = [f"{MTGO_BASE}/{day:%Y/%m}", f"{MTGO_BASE}?year={day:%Y}&month={day:%m}"]
    respondeu, erros = False, []
    for url in candidatos:
        try:
            r = _get_mtgo(url)
            r.raise_for_status()
        except requests.RequestException as e:
            erros.append(f"{url}: {e!r}"[:300])
            continue
        respondeu = True
        hrefs = set(re.findall(r'href="(/decklists?/[^"]+)"', r.text))
        achados = sorted(f"https://www.mtgo.com{h}" for h in hrefs if stamp in h)
        if achados:
            return achados
    if not respondeu:
        raise IndiceFalhou(f"indice do mtgo.com de {day:%Y-%m} sem resposta "
                           f"(dia {stamp}): " + " | ".join(erros))
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
    # As Challenges trazem `player_count` (validado contra o site a 2026-09-18:
    # "Pauper Challenge 32" → 32); as ligas não trazem nada. Guarda-se porque é
    # de graça — o peso do MTGO continua a vir do tier, não daqui.
    try:
        jogadores = int(blob.get("player_count") or 0) or None
    except (TypeError, ValueError):
        jogadores = None

    new = 0
    for deck in blob.get("decklists") or []:
        key = str(deck.get("loginid") or deck.get("player") or "") + "|" + url
        main = _cards(deck, "main")
        side = _cards(deck, "side")
        # O COMANDANTE (2026-10-01): lê-se do sideboard ANTES de ele ser fundido
        # no main, que é onde a informação se perdia. Ver `mtgvault/consenso.py`.
        comandante = (_consenso().nome_do_comandante(con, [n for n, _q in side])
                      if fmt in COMMANDER_FORMATS else None)
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
                          placement=str(deck.get("rank") or ""), url=url,
                          event_players=jogadores, commander=comandante):
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
                 formats: set[str] | None = None,
                 incluir_hoje: bool = False) -> int:
    """Recolhe as decklists dos últimos N dias. Isto é o trabalho diário.

    `incluir_hoje=False` (omissão) é o comportamento de sempre: começa em
    ONTEM. É a omissão de propósito — o `daily` corre às 03:30, quando a página
    de hoje ainda não tem nada, e mudá-la punha um pedido a mais por formato
    todas as noites a não trazer nada.

    `incluir_hoje=True` acrescenta o dia de HOJE à frente, e serve a recolha
    pedida à mão: a página de liga do mtgo.com publica os 5-0 ao longo do dia,
    por isso a de hoje já tem listas às 23h e esperar pela corrida da madrugada
    deixava um buraco de um dia na janela. Não é um segundo caminho — é o mesmo
    ciclo, com um dia a mais na lista.
    """
    formats = {f.lower() for f in (formats or MTGO_FORMATS)} & MTGO_FORMATS
    total = 0
    dias = ([date.today()] if incluir_hoje else []) + [
        date.today() - timedelta(days=d + 1) for d in range(days_back)]
    # Um dia sem índice não pára os outros: colhem-se e a falha diz-se no FIM
    # (2026-10-28, ver `IndiceFalhou`). O que entrou fica — o `store_event` já
    # fez commit —, mas o passo não pode ficar «ok» com um dia por ver.
    falhas: list[str] = []
    for day in dias:
        try:
            urls = fetch_mtgo_index(day)
        except IndiceFalhou as e:
            falhas.append(str(e))
            continue
        for url in urls:
            if formats and not any(f in url.lower() for f in formats):
                continue
            # Liga que não conta para aquele formato: nem se descarrega a página
            # (o slug do mtgo já diz "…-league-…"). Poupa pedidos e BD.
            #
            # EXCEPÇÃO — A VIGIA DE CARTAS (André, 2026-09-26). Num formato com
            # cartas vigiadas a página DESCARREGA-SE: a primeira aparição de um
            # combo novo é exactamente um 5-0 de liga, e sem abrir a página não há
            # maneira de saber o que ela tem lá dentro. Quem filtra é o
            # `store_decklist`, que só guarda as listas COM carta vigiada — a base
            # não cresce com as outras. Sem cartas vigiadas salta como sempre
            # saltou, e é isso que faz ligar isto não mudar nada no daily.
            #
            # E A BUSCA (André, 2026-10-13): num formato com `ligas: "busca"` a
            # página também se descarrega quando há um ALVO NOMEADO que a
            # justifique — um deck seguido com amostra baixa, ou um jogador
            # vigiado. Sem alvo, salta como as outras. Ver `busca_ligas`.
            fmt_url = _guess_format(url)
            if ("league" in url.lower()
                    and "League" not in metagame_rules(fmt_url)["tiers"]
                    and not _vigia().ha_vigia(fmt_url)
                    and not _busca().ha_alvo(con, fmt_url)):
                continue
            try:
                html = _get_mtgo(url).text
            except requests.RequestException:
                continue
            blob = parse_mtgo_page(html)
            if blob:
                total += store_event(con, blob, url)
    if falhas:
        raise IndiceFalhou(f"{len(falhas)} de {len(dias)} dia(s) sem indice do "
                           f"mtgo.com ({total} novas nos outros): " + " || ".join(falhas))
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
                 day: str, player: str = "", key: str | None = None,
                 arquetipo: str | None = None) -> int:
    """Entrada à mão. `arquetipo` é o nome do deck, se quem a mete o souber —
    quem escreve uma lista à mão sabe que deck é, e deitar fora essa palavra era
    repetir aqui o defeito que o `arquetipo_fonte` veio corrigir (2026-10-02)."""
    parsed = parse_text_decklist(text)
    key = key or f"{fmt}|{event}|{player}|{day}"
    cur = con.execute(
        """INSERT OR IGNORE INTO decklists
           (source, source_key, format, event_name, event_date, player, event_tier,
            arquetipo_fonte, arquetipo_fonte_de)
           VALUES ('manual',?,?,?,?,?,?,?,?)""",
        (key, fmt.lower(), event, day, player, event_tier("manual", event),
         (arquetipo or "").strip() or None,
         "manual" if (arquetipo or "").strip() else None),
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
    # Pauper não tem metagame (André, 2026-09-07): ele só segue a lista do Luffy.
    "pauper": {"tiers": [], "ligas": False},
}

# Formatos em que SÓ se guardam as listas dos jogadores vigiados (`watched` com
# kind='mtgo_player'). Ver `_jogador_vigiado`.
DEFAULT_SO_JOGADORES_VIGIADOS = ["pauper"]

_CFG_CACHE: dict = {}

# O caminho do config por omissão, resolvido UMA vez no import (2026-10-03).
#
# Era `Path(__file__).resolve().parents[1] / "colecao_config.json"` DENTRO do
# `_config()`, e o `_config()` é chamado milhares de vezes por relatório (o
# `precos.bloco`, o `precos.modo`, o `precos.fontes`, o `estado.factor` — todos
# por cópia). Cada `resolve()` são duas chamadas ao `nt._getfinalpathname`:
# **medido a 2026-10-03 com o cProfile, 23 798 chamadas e 5,7 s** no bloco do
# estado da página das fases, com o trabalho a sério a custar menos de 1 s.
# O `__file__` não muda a meio de um processo; o `MTGVAULT_CONFIG` continua a
# ler-se a cada chamada, porque os testes trocam-no em memória.
_RAIZ_CFG = Path(__file__).resolve().parents[1] / "colecao_config.json"


# O QUE CORREU MAL NA ÚLTIMA LEITURA DO CONFIG (2026-10-02), para quem o queira
# dizer em português. `{}` quer dizer que está bom — ver `config_estragado`.
_CFG_ERRO: dict = {}


def config_estragado() -> dict:
    """`{caminho, erro}` se o `colecao_config.json` não faz parse, senão `{}`.

    Existe para a avaria poder ser DITA. Ver o porquê em `_config`.
    """
    return dict(_CFG_ERRO)


def _config() -> dict:
    """colecao_config.json (na raiz do repositório, ou MTGVAULT_CONFIG).

    UM CONFIG ILEGÍVEL NÃO É UM CONFIG VAZIO (2026-10-02). Isto apanhava o
    `JSONDecodeError` e devolvia `{}`, calado. E este é o ficheiro que o André
    **edita à mão** — o CLAUDE.md di-lo: *"é um ficheiro para ser LIDO por uma
    pessoa"*. Medido no config a sério com uma vírgula a mais no fim:

        caixas            17  ->  0      (o loadout inteiro desaparece)
        venda congelada   até 12/10 -> NÃO   (a trava do RC Ghent levanta-se)
        cadeia de preços  cardtrader->cardmarket  ->  só cardmarket
        revalidacao.foto_manda  True -> None

    Sem um erro, sem um passo vermelho, sem uma palavra numa página. É o padrão
    do `event_tier` sobre o ficheiro que guarda todas as decisões dele.

    Duas coisas mudam, e nenhuma delas com o ficheiro bom:

      1. **o último bom FICA**. Enquanto o processo viver, um ficheiro que se
         partiu a meio não apaga o que já estava lido — o `webapp.py` está de pé
         o dia todo e não pode ficar sem caixas porque ele estava a editar o
         JSON. Só vale para o MESMO caminho: trocar de ficheiro não herda nada;
      2. **diz-se**, uma vez por alteração (o `_config` é chamado milhares de
         vezes por relatório; um aviso por chamada era um log que se deixa de
         ler) e com o erro do JSON, que traz a linha e a coluna.

    Um ficheiro AUSENTE continua a ser `{}` e calado: isso não é uma avaria, é
    um vault sem config (um checkout limpo, metade dos testes).
    """
    p = Path(os.environ.get("MTGVAULT_CONFIG") or _RAIZ_CFG)
    try:
        stamp = p.stat().st_mtime
    except OSError:
        _CFG_ERRO.clear()
        return {}
    if _CFG_CACHE.get("path") != str(p) or _CFG_CACHE.get("stamp") != stamp:
        mesmo = _CFG_CACHE.get("path") == str(p)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            _CFG_ERRO.update(caminho=str(p), erro=str(e))
            print(f"[mtgvault] o {p.name} não faz parse e FICOU O ÚLTIMO QUE "
                  f"deu certo: {e}\n           ficheiro: {p}", file=sys.stderr)
            # Marca-se o `stamp` para não voltar a avisar a cada leitura, e
            # NÃO se toca no `data`: o último bom é o que vale até ele corrigir.
            _CFG_CACHE.update(path=str(p), stamp=stamp,
                              data=(_CFG_CACHE.get("data") if mesmo else None))
            return _CFG_CACHE.get("data") or {}
        _CFG_ERRO.clear()
        _CFG_CACHE.update(path=str(p), stamp=stamp, data=data)
    return _CFG_CACHE.get("data") or {}


def config() -> dict:
    """O colecao_config.json inteiro (em cache, recarregado quando o ficheiro muda).
    As páginas que precisam de uma chave qualquer do config leem-no por aqui, em
    vez de cada uma abrir o ficheiro à sua maneira."""
    return _config()


def esquecer_config() -> None:
    """Esquece o config em cache — quem o REESCREVEU tem de chamar isto.

    **A LIMPEZA DA CACHE VIVE NUM SÍTIO SÓ (2026-10-06).** Treze ficheiros de
    teste exercitam um INTERRUPTOR do config reescrevendo o ficheiro, e os treze
    tinham a mesma linha copiada à mão: `sources._CONFIG_CACHE = None` — um nome
    que **não existe** (a cache é a `_CFG_CACHE`, acima). A linha criava um
    atributo que ninguém lê e não limpava nada; o `escreve_cfg` de cada um
    prometia-o na docstring. É o padrão do `event_tier` dentro de um helper de
    teste: uma linha com a cara de fazer uma coisa, a não fazer nada.

    O que os fazia passar quase sempre era o OUTRO mecanismo — o `_config()`
    compara o `st_mtime`. Quando duas escritas caem no **mesmo tique** do relógio
    do sistema de ficheiros, a cache responde com o config ANTERIOR e o
    interruptor deixa de morder. Apanhado na bateria de 2026-10-06 pelo
    `test_foto_manda.caso_a_frase_honesta_diz_x_de_y`, que ficou vermelho uma vez
    e passou **10 de 10** vezes corrido sozinho — a definição de uma mina.
    Reproduz-se sempre empatando o mtime com `os.utime`.

    **Não é só dos testes.** Quem escrever o config em código e quiser ler o novo
    valor na mesma passagem (o `webapp` depois de um POST, uma ordem do CLI que
    grave e confirme) passa por aqui. Com o mtime a mudar não é preciso; o ponto
    é que não se pode CONTAR com ele.
    """
    _CFG_CACHE.clear()
    _CFG_ERRO.clear()


def _sem_comentarios(d) -> dict:
    """As chaves "_xxx" do colecao_config.json são ajuda para o André, não regra."""
    return {k: v for k, v in (d or {}).items() if not str(k).startswith("_")}


def _vigia():
    """O módulo da VIGIA DE CARTAS, importado TARDE.

    O `mtgvault.vigia` lê o config por aqui (`sources.config()`), por isso um
    `import` no topo deste ficheiro fechava um ciclo. É o mesmo padrão do
    `daily._fotos_caixas` e do `deckboxes` com as `encomendas`.
    """
    from mtgvault import vigia                               # noqa: PLC0415
    return vigia


def _busca():
    """A BUSCA POR LIGAS (2026-10-13), importada tarde pela razão do `_vigia`:
    o `busca_ligas` lê o config e as caixas por aqui."""
    from mtgvault import busca_ligas                         # noqa: PLC0415
    return busca_ligas


def _consenso():
    """O módulo do CONSENSO POR COMANDANTE, importado TARDE — ele lê o config por
    aqui (`sources.config()`), e um `import` no topo fechava um ciclo. É o mesmo
    padrão do `_vigia()`."""
    from mtgvault import consenso                            # noqa: PLC0415
    return consenso


def metagame_rules(fmt: str | None) -> dict:
    """A regra em vigor para um formato: {tiers, min_jogadores_presencial, ligas}."""
    fmt = (fmt or "").lower()
    sec = _config().get("metagame_fontes") or {}
    r = dict(DEFAULT_METAGAME_RULES)
    r.update(_sem_comentarios(DEFAULT_METAGAME_BY_FORMAT.get(fmt)))
    r.update(_sem_comentarios(sec.get("_default")))
    r.update(_sem_comentarios(sec.get(fmt)))
    tiers = list(r.get("tiers") or [])
    # `is True` e não «truthy» (2026-10-13): o `"ligas": "busca"` é uma string,
    # e uma string não vazia é verdadeira — a liga de busca entrava na contagem
    # pela porta que existe precisamente para a manter fora. Ver
    # `mtgvault.busca_ligas`.
    if r.get("ligas") is True and "League" not in tiers:
        tiers.append("League")
    r["tiers"] = tiers
    return r


def _campo(row, chave):
    """Valor de uma coluna, venha a linha em dict ou em sqlite3.Row."""
    try:
        return row[chave]
    except (KeyError, IndexError):
        return None


def lista_conta(row, fmt: str | None = None, consenso: bool = True) -> bool:
    """Esta decklist conta para o metagame? `row` precisa de `event_tier` e
    `event_players` (e de `format`/`source` se não vierem por argumento).

    As listas `manual` contam sempre: foi o André que as meteu à mão, e é por aí
    que entram os formatos que os scrapers não cobrem.

    `consenso=True` (omissão) aplica também o corte da JANELA DO CONSENSO — a
    mesma resposta que o `counting_sql` dá em SQL. Precisa do `event_date`; sem
    essa coluna não se inventa um corte, deixa-se passar (é o que faz um `row`
    de uma recolha, que ainda não tem data gravada).
    """
    fmt_efectivo = fmt if fmt is not None else _campo(row, "format")
    if consenso:
        desde = consenso_desde(fmt_efectivo)
        data = _campo(row, "event_date")
        if desde and data and str(data) < desde:
            return False
    if _campo(row, "source") == "manual":
        return True
    r = metagame_rules(fmt_efectivo)
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


def presenciais_sem_numero(con: sqlite3.Connection,
                           fmt: str | None = None) -> list[dict]:
    """Os presenciais que NÃO CONTAM só porque não se sabe quantos jogadores
    tiveram — num formato que exige um mínimo (2026-10-13).

    A REGRA NÃO MUDOU: *o que não se sabe não conta* (o `lista_conta` e o
    `counting_sql` recusam `event_players` NULL ou 0 desde 2026-09-07). O que
    mudou é que deixaram de cair EM SILÊNCIO: com a porta a 31 jogadores no
    Pioneer e no Legacy, um presencial de 40 sem número ficava de fora sem uma
    linha a dizê-lo. Esta é essa linha, por evento, com o nº de listas e — se
    houver um evento com o MESMO nome e a MESMA data que tenha número — a pista
    de que é uma re-publicação (medido a 13/10: as 8 listas de Legacy sem
    número são a «Law League #2» de 04/10 publicada DUAS vezes no mtgtop8, a
    91608 com 35 jogadores e a 91650 sem contagem). Não se copia o número de
    um para o outro: é ele que decide.
    """
    formatos = [fmt.lower()] if fmt else [r[0] for r in con.execute(
        "SELECT DISTINCT format FROM decklists WHERE event_tier = 'Presencial'")]
    out = []
    for f in formatos:
        if int(metagame_rules(f).get("min_jogadores_presencial") or 0) <= 0:
            continue
        if "Presencial" not in metagame_rules(f)["tiers"]:
            continue
        for r in con.execute(
                """SELECT event_name, event_date, source, COUNT(*) n,
                          MIN(url) url
                     FROM decklists
                    WHERE format = ? AND event_tier = 'Presencial'
                      AND COALESCE(event_players, 0) = 0
                    GROUP BY event_name, event_date, source
                    ORDER BY event_date DESC, event_name""", (f,)):
            gemeo = con.execute(
                """SELECT MAX(event_players) p, MIN(url) url FROM decklists
                    WHERE format = ? AND event_name = ? AND event_date = ?
                      AND event_tier = 'Presencial' AND event_players > 0""",
                (f, r["event_name"], r["event_date"])).fetchone()
            out.append({"formato": f, "evento": r["event_name"],
                        "data": r["event_date"], "fonte": r["source"],
                        "listas": r["n"], "url": r["url"],
                        "gemeo_jogadores": gemeo["p"] if gemeo else None,
                        "gemeo_url": gemeo["url"] if gemeo else None})
    return out


def texto_sem_numero(con: sqlite3.Connection) -> str:
    """Uma linha para o daily (2026-10-16): os presenciais que não contam por
    falta de número, por formato, com a pista do gémeo. Até aqui a lista só
    saía do CLI (`presenciais-sem-numero`), e o passo `jogadores-eventos` dizia
    «1 eventos vistos (0 com contagem)» sem dizer que essas eram ligas do MTGO
    (que nunca trazem contagem) nem quantos presenciais ficavam de fora."""
    rows = presenciais_sem_numero(con)
    if not rows:
        return "nenhum presencial fica de fora por falta de número"
    por: dict[str, list] = {}
    for x in rows:
        por.setdefault(x["formato"], []).append(x)
    partes = []
    for f, xs in sorted(por.items()):
        gem = sum(1 for x in xs if x["gemeo_jogadores"])
        partes.append(f"{f} {len(xs)} ev/{sum(x['listas'] for x in xs)} listas"
                      + (f" ({gem} com gémeo numerado)" if gem else ""))
    return "presenciais que NÃO contam por falta de número: " + "; ".join(partes)


def counting_sql(fmt: str, alias: str = "d",
                 consenso: bool = True) -> tuple[str, list]:
    """A mesma regra que `lista_conta`, como pedaço de SQL para pôr num WHERE.
    Devolve (condição, parâmetros) — a condição já vem entre parênteses.

    `consenso=True` (omissão) acrescenta o CORTE DA JANELA DO CONSENSO
    (`consenso_desde`, 2026-10-03). A omissão é o corte de propósito: quem
    escrever uma consulta nova de consenso e não pensar nisto fica com a janela
    certa. Os dois sítios que NÃO são consenso passam `consenso=False` e dizem
    porquê — ver `consenso_desde`.
    """
    r = metagame_rules(fmt)
    a = f"{alias}." if alias else ""
    janela, jp = (consenso_sql(fmt, alias) if consenso else ("", []))
    tiers = r["tiers"]
    if not tiers:
        return f"({a}source = 'manual'{janela})", list(jp)
    marcas = ",".join("?" for _ in tiers)
    sql = f"{a}event_tier IN ({marcas})"
    params = list(tiers)
    minimo = int(r.get("min_jogadores_presencial") or 0)
    if minimo > 0 and "Presencial" in tiers:
        sql += (f" AND ({a}event_tier <> 'Presencial' OR ({a}event_players IS NOT NULL "
                f"AND {a}event_players >= ?))")
        params.append(minimo)
    # O corte da janela fica FORA do `source = 'manual'`: uma lista manual conta
    # sempre (é ele que a meteu), mas não pode ser mais antiga do que a janela —
    # senão a excepção das manuais era um buraco por onde entrava Setembro.
    return (f"(({a}source = 'manual' OR ({sql})){janela})",
            params + list(jp))


# ---------------------------------------------------------------------------
# AS LIGAS CONTAM-SE À PARTE (André, 2026-10-05)
# ---------------------------------------------------------------------------
# À letra: *"para modern, apenas os decks de Mox Opal, procura todos os torneios !
# incluindo ligas, torneios presenciais"*. As ligas entraram no Modern — e uma
# liga **não é um torneio como os outros**: é um 5-0 publicado sem classificação
# e sem tamanho de campo. Misturada no mesmo bolo de uma Challenge, a
# percentagem do formato passa a somar duas coisas diferentes e o número fica
# PIOR, não melhor.
#
# Por isso a percentagem mostra-se SEMPRE nas duas contas, lado a lado — é a
# disciplina dos «dois números» de 2026-10-04 (*«a somar»* vs *«a rodar»*) e da
# `curva_staples`: quem lê tem de poder ver se o número subiu por o deck se
# jogar mais ou só por a fonte ter mudado. Medido no dia em que isto entrou: as
# ligas trazem 5,1 % de Mox Opal contra 7,3 % no resto, ou seja a percentagem do
# formato **DESCE** com elas — exactamente o contrário do que se esperava, e a
# razão para o número não andar sozinho.
#
# A PERGUNTA VIVE AQUI, num sítio só, pela razão de sempre: o `event_tier =
# 'League'` escrito à mão numa segunda consulta discordava desta num dia
# qualquer, em silêncio (é a lição do `e_foil`, do `precos.sql()` e do
# `venda.mostrar`).
TIER_LIGA = "League"


def sql_sem_ligas(alias: str = "d") -> tuple[str, list]:
    """O predicado *«esta lista NÃO é de uma liga»*, para pôr num WHERE.

    `event_tier` pode ser NULL numa lista antiga (a coluna andou anos a ser lida
    sem ser escrita — ver `backfill_event_tiers`), e `NULL <> 'League'` em SQL
    não é verdadeiro: é NULL, e a linha caía fora da conta dos dois lados. Daí o
    `IS NULL OR`.
    """
    a = f"{alias}." if alias else ""
    return f"({a}event_tier IS NULL OR {a}event_tier <> ?)", [TIER_LIGA]


def conta_ligas(fmt: str | None) -> bool:
    """Este formato conta ligas? É o mesmo interruptor que abre as quatro portas
    (a colheita, o `store_decklist`, o `counting_sql` e o `prune_leagues`)."""
    return TIER_LIGA in metagame_rules(fmt)["tiers"]


# ---------------------------------------------------------------------------
# A JANELA DO CONSENSO (André, 2026-10-03)
# ---------------------------------------------------------------------------
# À letra: *"faz a pesquisa de decks só a partir do dia que reality fracture
# ficou disponível"*. A data é **2026-09-29** — a terça em que o Reality Fracture
# entrou na loja do Magic Online (10:00 PT / 17:00 UTC), e não a data de papel
# (02/10): o metagame que o vault recolhe é quase todo de MTGO. Confirmado nos
# dados dele: em Modern, 0 % das listas até 28/09 jogam uma carta que estreia no
# `fra`, 5,0 % a 29/09 (só os eventos depois daquela hora) e 21,1 % a 30/09.
#
# ESTA É A PERGUNTA *"a partir de quando é que uma lista conta para o
# consenso?"*, e vive NUM SÍTIO SÓ, pela razão de sempre: o corte escrito à mão
# numa segunda consulta discordava do primeiro num dia qualquer, em silêncio.
# Quem quiser o corte em SQL usa o `consenso_sql`; quem tem a linha na mão usa o
# `lista_conta`. Há um teste que varre o código à procura de quem leia a chave
# `consenso.desde` por fora daqui.
#
# DUAS COISAS QUE O CORTE **NÃO** APANHA, e as duas são decisões com medida:
#
#   1. **A RESERVA DA R5 continua nos 30 dias dela** (`reserva.janela_dias`).
#      São duas janelas e servem duas perguntas: o consenso pergunta *"como é
#      que este deck se joga agora"* e a reserva pergunta *"que carta é que eu
#      joguei no último mês e por isso não devo vender"*. A segunda é sobre o
#      PASSADO dele e encurtá-la a cinco dias desprotegia carta que ele usou há
#      duas semanas. Medido a 2026-10-03 — ver o relatório: com o corte a
#      reserva deixaria de proteger centenas de cópias. A R5 não passa por aqui
#      por construção (`ids_por_assinatura(so_que_contam=False)` nem chama o
#      `counting_sql`), e há teste que o tranca.
#   2. **Seguir UMA lista não é consenso** (`my_decks`): ali já se pede *"a mais
#      recente"*, e o corte não a torna mais recente — só pode fazê-la
#      desaparecer e deixar a caixa sem lista. `consenso=False`, com o porquê
#      escrito lá.
CONSENSO_DESDE = ""        # sem chave no config = sem corte (bases novas, testes)


def regras_consenso(cfg: dict | None = None) -> dict:
    """`colecao_config.json → consenso`, com os valores por omissão."""
    c = _sem_comentarios((cfg if cfg is not None else _config()).get("consenso"))
    r = {"desde": CONSENSO_DESDE, "excepcoes": [], "motivo": "", "fonte": ""}
    r.update(c)
    return r


def consenso_desde(fmt: str | None = None, cfg: dict | None = None) -> str:
    """A data (`AAAA-MM-DD`) a partir da qual uma lista conta para o consenso.

    `""` quer dizer *sem corte* — é o que vale num config sem a chave.

    `excepcoes` são os formatos que o corte NÃO apanha, e hoje é o **premodern**:
    o Reality Fracture não é legal lá (o formato acaba no Scourge, 2003) e o
    corte não responderia a pergunta nenhuma — só apagava o consenso. Medido na
    base de 2026-10-03: das **978** listas de premodern, **zero** jogam uma
    única carta do set, contra 21 % em Modern no dia seguinte ao lançamento. Sem
    a excepção, três caixas de Premodern dele ficavam sem lista (Elves 23→0
    listas, Oath 30→4, Ill-Gotten Gains 3→0) na véspera do RC de Ghent. É uma
    linha no config a tirar, se ele preferir o corte cego.
    """
    r = regras_consenso(cfg)
    desde = str(r.get("desde") or "").strip()
    if not desde:
        return ""
    f = (fmt or "").lower()
    excepcoes = {str(x).lower() for x in (r.get("excepcoes") or [])}
    return "" if f and f in excepcoes else desde


def consenso_sql(fmt: str, alias: str = "d") -> tuple[str, list]:
    """O corte da janela do consenso como pedaço de SQL (` AND ...`, params).

    Vem com o ` AND` à cabeça e vazio quando não há corte, para quem o
    concatena não ter de testar nada.
    """
    desde = consenso_desde(fmt)
    if not desde:
        return "", []
    a = f"{alias}." if alias else ""
    return f" AND {a}event_date >= ?", [desde]


def frase_janela_rodape() -> str:
    """A frase da JANELA para o rodapé de uma página, em HTML. `""` sem corte.

    Escrita num sítio só e composta do config: duas páginas a escreverem a data
    à mão discordavam no dia em que ele a mudasse, e uma página que diz uma data
    diferente da que o motor usou é pior do que página nenhuma.
    """
    r = regras_consenso()
    desde = str(r.get("desde") or "").strip()
    if not desde:
        return ""
    motivo = str(r.get("motivo") or "").strip()
    excepcoes = [str(x) for x in (r.get("excepcoes") or [])]
    txt = (f" <b>A janela:</b> conta-se <b>só o que foi jogado de {desde} em "
           f"diante</b>"
           + (f" — {motivo}" if motivo else "")
           + ". Foi o pedido dele a 3 de outubro de 2026: <i>«faz a pesquisa de "
             "decks só a partir do dia que reality fracture ficou "
             "disponível»</i>; por isso há muito menos listas por deck do que "
             "no mês inteiro, e quem ficar abaixo do mínimo aparece como "
             "<b>amostra insuficiente</b> em vez de dar percentagens.")
    if excepcoes:
        txt += (" Fora do corte: <b>" + ", ".join(excepcoes) + "</b> — o set "
                "não é legal lá, por isso o corte só apagava o consenso.")
    return txt + (" Muda-se em <code>colecao_config.json → consenso.desde</code>.")


AMOSTRA_INSUFICIENTE = "amostra insuficiente"


def texto_amostra(listas: int, minimo: int, fmt: str | None = None) -> str:
    """*"Não dá para dizer"*, em português e NUM SÍTIO SÓ (2026-10-03).

    Ordem dele, à letra: *"escreve isso em letra grande em vez de me dares
    percentagens de uma amostra de duas — com 2 listas uma carta aparece a 50 %
    ou a 100 % sem isso querer dizer nada. Prefiro «não dá para dizer» a um
    número bonito e falso."*

    Devolve `""` quando a amostra chega — é o que torna isto um `if` só.
    """
    if listas >= minimo:
        return ""
    quantas = "nenhuma lista" if not listas else (
        "1 lista" if listas == 1 else f"{listas} listas")
    janela = texto_janela_consenso(fmt)
    txt = (f"{AMOSTRA_INSUFICIENTE}: {quantas} (o mínimo para se chamar "
           f"consenso a isto é {minimo})")
    return f"{txt} — {janela}" if janela else txt


def texto_janela_consenso(fmt: str | None = None) -> str:
    """O que a PÁGINA diz sobre a janela, em português. `""` sem corte.

    Uma janela que a página não diz é uma página a mentir em silêncio: o número
    de listas cai para um quinto e quem olha não tem como saber porquê.
    """
    desde = consenso_desde(fmt)
    if not desde:
        return ""
    motivo = str(regras_consenso().get("motivo") or "").strip()
    txt = f"só listas de {desde} em diante"
    return f"{txt} — {motivo}" if motivo else txt


# ---------------------------------------------------------------------------
# A IDENTIDADE DE UM DECK É UMA CARTA-ASSINATURA (André, 2026-10-02)
# ---------------------------------------------------------------------------
# Palavras dele: *"a identidade de um deck é uma CARTA-ASSINATURA, NUNCA a
# etiqueta do clustering"* — e já se provou duas vezes nesta semana: os clusters
# chamam-se *"Rotlung Reanimator / Priest of Gix / Oath of Druids"* e há dezenas
# vazios com o mesmo nome (medido no `consenso.py` para o Duel Commander: 870
# etiquetas, 808 sem uma única lista).
#
# A pergunta *"que listas são deste deck?"* é feita em DOIS sítios — a lista da
# caixa (`loadout._cards_from_consensus`) e a reserva dos últimos 30 dias
# (`fases`) — e por isso vive aqui, numa função só. Dois selectores ao lado
# discordavam um dia qualquer, em silêncio: é a lição do `event_tier`.
def ids_por_assinatura(con, fmt: str, assinatura, todas: bool = False,
                       desde: str | None = None,
                       so_que_contam: bool = True,
                       sem=None) -> list[int]:
    """Os ids das listas de `fmt` que casam com esta assinatura.

    `todas=False` (omissão) é **basta uma** (`IN`) — é o que serve o *"Greasefang,
    as várias versões"* dele: uma carta só apanha todas as variantes do deck.
    `todas=True` é **em conjunção**: o *Engineer Welder Cam* precisa de
    `Goblin Welder` **e** `Sewer-veillance Cam`, porque cada uma sozinha
    apanha outros decks de Legacy (medido a 2026-10-02: Welder 50, Cam 54,
    as duas juntas 50 — a Cam traz 4 listas que não jogam Welder).

    `sem` é a NEGAÇÃO: nenhuma destas cartas pode estar na lista. Entrou a
    2026-10-02 à tarde e tem um caso real que a obriga, o mais caro desta semana:
    **todas as 124 listas de Enchantress de Premodern jogam `Replenish`**, por isso
    `assinatura: ["Replenish"]` apanhava 186 listas — dois decks diferentes
    (62 são o combo azul-branco: Attunement, Frantic Search, Opalescence, Decree
    of Silence, Intuition; as outras 124 são verde-brancas: Wild Growth, Mirri's
    Guile, Serra's Sanctum, Sterling Grove, Solitary Confinement) — e o consenso
    que saía dali não era de deck nenhum. É o mesmo operador `none` que o
    `archetype_rules.json` já tinha, pela mesma razão: *"o `_known_name` chamava
    «Replenish» à Enchantress E ao UW Replenish, porque bate na primeira carta que
    encontra. O `none` separa-os."*

    `so_que_contam` decide o universo, e os dois valores servem perguntas
    diferentes:
      * **True** (o `counting_sql` de sempre) para a LISTA do deck — é o filtro
        de todo o site e não se abre uma excepção para uma página;
      * **False** (todas as listas da base) para a PROTECÇÃO dos últimos 30
        dias. Aqui sub-contar é vender uma carta que ele precisa, e há formatos
        em que o filtro dá ZERO de propósito (`metagame_fontes.pauper.tiers =
        []`, porque ele só segue o Luffy): uma protecção vazia em silêncio é o
        padrão do `event_tier` aplicado a dinheiro. É a mesma razão por que a
        VIGIA DE CARTAS de 2026-09-26 abriu o filtro de tier — *"a primeira
        aparição de um combo novo É um 5-0 de league"*.
    """
    ass = [str(x) for x in (assinatura or []) if str(x).strip()]
    if not ass:
        return []
    fora = [str(x) for x in (sem or []) if str(x).strip()]
    cond, cp = ("(1=1)", []) if not so_que_contam else counting_sql(fmt, "d")
    extra, ep = ("", [])
    if desde:
        extra, ep = " AND d.event_date >= ?", [desde]
    # A NEGAÇÃO é um NOT EXISTS por carta, do mesmo lado da conjunção: tanto o
    # ramo do `IN` como o do `EXISTS` a levam, para os dois darem a mesma resposta
    # à mesma pergunta.
    nao = " ".join(
        "AND NOT EXISTS(SELECT 1 FROM decklist_cards y WHERE y.decklist_id = d.id "
        "AND y.card_name = ?)" for _ in fora)
    if todas:
        # Uma subconsulta EXISTS por carta: a conjunção não se faz com `IN`.
        ex = " ".join(
            "AND EXISTS(SELECT 1 FROM decklist_cards x WHERE x.decklist_id = d.id "
            "AND x.card_name = ?)" for _ in ass)
        return [r[0] for r in con.execute(
            f"SELECT d.id FROM decklists d WHERE d.format = ? AND {cond}{extra} "
            f"{ex} {nao}", (fmt, *cp, *ep, *ass, *fora))]
    marcas = ",".join("?" for _ in ass)
    return [r[0] for r in con.execute(
        f"""SELECT DISTINCT d.id FROM decklists d
              JOIN decklist_cards dc ON dc.decklist_id = d.id
             WHERE d.format = ? AND dc.card_name IN ({marcas}) AND {cond}{extra}
                   {nao}""",
        (fmt, *ass, *cp, *ep, *fora))]


def texto_assinatura(assinatura, todas: bool = False, sem=None) -> str:
    """Como se escreve a assinatura numa página ("A e B" / "A ou B" / "A sem C")."""
    ass = [str(x) for x in (assinatura or []) if str(x).strip()]
    if not ass:
        return ""
    liga = " e " if todas else " ou "
    txt = ass[0] if len(ass) == 1 else liga.join(ass)
    fora = [str(x) for x in (sem or []) if str(x).strip()]
    if fora:
        txt += " sem " + " nem ".join(fora)
    return txt


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


# ---------------------------------------------------------------------------
# Formatos sem metagame, seguidos só por jogador  (André, 2026-09-07)
# ---------------------------------------------------------------------------
# "Pauper também não precisa [de metagame], pois só sigo a lista Pauper do
# jogador específico (Luffy)."
#
# Tirar o Pauper do harvest resolvia o metagame mas MATAVA a vigilância: o
# `watchlist.check_mtgo_player` não vai à rede — lê a lista mais recente do
# jogador das decklists que o harvest já trouxe. Sem harvest de Pauper, a lista
# do Luffy congelava no último snapshot e nunca mais mexia, sem dar erro nenhum.
#
# Por isso o filtro é aqui, à entrada: as páginas do evento continuam a ser
# lidas (é de lá que vem a lista do Luffy), mas só se GUARDA a de quem está
# vigiado. Fica o que serve para alguma coisa e o vault.db não engorda com
# ~600 listas por formato que nenhuma página conta.
def so_jogadores_vigiados() -> set[str]:
    """Formatos onde só se guardam as listas dos jogadores vigiados."""
    v = config().get("so_jogadores_vigiados")
    if v is None:
        v = DEFAULT_SO_JOGADORES_VIGIADOS
    return {str(f).strip().lower() for f in v}


def _jogador_vigiado(con: sqlite3.Connection, fmt: str, player: str) -> bool:
    jogador = (player or "").strip().lower()
    if not jogador:
        return False
    try:
        return con.execute(
            """SELECT 1 FROM watched WHERE active = 1 AND kind = 'mtgo_player'
                AND lower(format) = ? AND lower(key) = ? LIMIT 1""",
            (fmt, jogador)).fetchone() is not None
    except sqlite3.OperationalError:
        return True     # base sem tabela `watched`: não se filtra nada


def somar_cartas(cards: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    """Junta as entradas repetidas da mesma carta no mesmo board, SOMANDO.

    **O mtgo.com parte a mesma carta em várias entradas** — uma por impressão
    (medido a 2026-10-16 na Modern Challenge 64 de 15/10: o howa traz
    `Tamiyo, Inquisitive Student` 3 + 1 e `Consign to Memory` 3 + 1; o DJK3V1N
    `Island` 1 + 1 e `Tormod's Crypt` 2 + 2). A chave da `decklist_cards` é
    (lista, carta, board) e a gravação era `INSERT OR REPLACE`: a ÚLTIMA entrada
    apagava as outras, sem um único erro. Nesse dia eram **2 050 das 5 060
    listas do MTGO** curtas (o mtgtop8, que escreve uma linha por carta, zero).
    A ordem da primeira aparição fica — a do `rowid`, de que o `consenso`
    deriva o comandante pela ÚLTIMA linha."""
    tot: dict[tuple[str, str], int] = {}
    for b, n, q in cards:
        tot[(b, n)] = tot.get((b, n), 0) + int(q)
    return [(b, n, q) for (b, n), q in tot.items() if q > 0]


def reler_mtgo(con: sqlite3.Connection, *, limite: int | None = None,
               urls: list[str] | None = None) -> dict:
    """RELÊ as páginas do mtgo.com das listas que a gravação antiga encurtou
    (ver `somar_cartas`) e acerta-as no sítio: as cartas, o `content_hash` e —
    porque com o hash certo a lista passa a coincidir com a re-hospedagem do
    mtgtop8 — a deduplicação de sempre (`SOURCE_PRIORITY`: fica a do mtgo, e
    herda o nome do arquétipo, os jogadores e a classificação que a outra
    trouxesse). Uma página que já não responde não mexe em nada.

    Escolhe as páginas com pelo menos uma lista de um formato construído com o
    main abaixo de 60 ou o sideboard entre 1 e 14, ou de comandante com menos de
    100 cartas — um sideboard curto também pode ser a fonte (o ruin000 de 15/10
    tem 13 na página), e é por isso que se relê e não se adivinha: uma segunda
    corrida volta a pedir essas páginas e não muda nada. Um pedido por página,
    com o ritmo do `_get_mtgo`."""
    if urls is None:
        cmd = sorted(COMMANDER_FORMATS)
        ph = ",".join("?" * len(cmd))
        soma = ("(SELECT COALESCE(SUM(quantity), 0) FROM decklist_cards "
                "WHERE decklist_id = dl.id{})")
        urls = [r[0] for r in con.execute(
            f"""SELECT DISTINCT dl.url FROM decklists dl
                 WHERE dl.source = 'mtgo' AND dl.url LIKE 'https://www.mtgo.com/%'
                   AND ((dl.format IN ({ph}) AND {soma.format('')} < 100)
                     OR (dl.format NOT IN ({ph})
                         AND ({soma.format(" AND board = 'main'")} < 60
                              OR {soma.format(" AND board = 'side'")} BETWEEN 1 AND 14)))
                 ORDER BY dl.url""", cmd + cmd)]
    if limite is not None:
        urls = urls[:limite]
    res = {"paginas": 0, "falhadas": 0, "acertadas": 0, "fundidas": 0,
           "copias": 0, "ids": []}
    for url in urls:
        try:
            r = _get_mtgo(url)
            r.raise_for_status()
            blob = parse_mtgo_page(r.text)
        except requests.RequestException:
            blob = None
        if not blob:
            res["falhadas"] += 1
            continue
        res["paginas"] += 1
        for deck in blob.get("decklists") or []:
            key = str(deck.get("loginid") or deck.get("player") or "") + "|" + url
            row = con.execute("SELECT id, format, event_date, player, content_hash "
                              "FROM decklists WHERE source = 'mtgo' AND source_key = ?",
                              (key,)).fetchone()
            if not row:
                continue
            if row["format"] in COMMANDER_FORMATS:
                # o comandante vem no sideboard e vai para o main, como no
                # `store_event` — senão o hash nunca batia com o do mtgtop8
                cartas = somar_cartas([("main", n, q) for n, q in
                                       _cards(deck, "main") + _cards(deck, "side")])
            else:
                cartas = somar_cartas([("main", n, q) for n, q in _cards(deck, "main")]
                                      + [("side", n, q) for n, q in _cards(deck, "side")])
            h = content_hash(row["format"], cartas)
            if h == row["content_hash"]:
                continue
            antes = con.execute("SELECT COALESCE(SUM(quantity), 0) FROM decklist_cards "
                                "WHERE decklist_id = ?", (row["id"],)).fetchone()[0]
            con.execute("DELETE FROM decklist_cards WHERE decklist_id = ?", (row["id"],))
            con.executemany("INSERT INTO decklist_cards (decklist_id, card_name, quantity, "
                            "board) VALUES (?,?,?,?)",
                            [(row["id"], n, q, b) for b, n, q in cartas])
            con.execute("UPDATE decklists SET content_hash = ? WHERE id = ?", (h, row["id"]))
            res["acertadas"] += 1
            res["copias"] += sum(q for _b, _n, q in cartas) - antes
            res["ids"].append(row["id"])
            res["fundidas"] += _fundir_duplicada(con, row["id"], row["format"], h,
                                                 row["event_date"], row["player"])
        con.commit()
    return res


def _fundir_duplicada(con: sqlite3.Connection, did: int, fmt: str, h: str,
                      dia: str, jogador: str) -> int:
    """Depois de uma lista do mtgo ficar com o hash certo, a re-hospedagem do
    mtgtop8 (prioridade mais baixa) passa a ser a mesma lista — é a regra do
    `store_decklist`, aplicada a posteriori. O que a outra sabia e a do mtgo
    não (o nome do arquétipo, os jogadores, a classificação) passa para esta
    antes de ela sair."""
    meu = (jogador or "").strip().lower()
    n = 0
    for o in con.execute("SELECT * FROM decklists WHERE format = ? AND content_hash = ? "
                         "AND event_date = ? AND id <> ?", (fmt, h, dia, did)).fetchall():
        outro = (o["player"] or "").strip().lower()
        if meu and outro and meu != outro:
            continue
        if SOURCE_PRIORITY.get(o["source"], 0) >= SOURCE_PRIORITY.get("mtgo", 0):
            continue
        con.execute("""UPDATE decklists SET
                         arquetipo_fonte = COALESCE(arquetipo_fonte, ?),
                         arquetipo_fonte_de = COALESCE(arquetipo_fonte_de, ?),
                         event_players = COALESCE(event_players, ?),
                         placement = CASE WHEN COALESCE(placement, '') = '' THEN ?
                                          ELSE placement END
                       WHERE id = ?""",
                    (o["arquetipo_fonte"], o["arquetipo_fonte_de"], o["event_players"],
                     o["placement"], did))
        con.execute("DELETE FROM decklists WHERE id = ?", (o["id"],))
        n += 1
    return n


def content_hash(fmt: str, cards: list[tuple[str, str, int]]) -> str:
    """Impressão digital do conteúdo da lista, independente da fonte."""
    payload = fmt.lower() + "|" + "|".join(
        f"{b}:{n}:{q}" for b, n, q in sorted(cards))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def store_decklist(con: sqlite3.Connection, *, source: str, source_key: str,
                   fmt: str, cards: list[tuple[str, str, int]],
                   event_name: str = "", event_date: str = "",
                   player: str = "", placement: str = "",
                   url: str = "", event_players: int | None = None,
                   commander: str | None = None,
                   arquetipo: str | None = None,
                   arquetipo_de: str = "evento") -> int | None:
    """Grava uma decklist, a não ser que já lá esteja por outra via.

    `arquetipo` é o nome que a FONTE dá ao deck (2026-10-02) — o mtgtop8 escreve-o
    na página do evento. Guarda-se tal e qual, com `arquetipo_fonte_de` a dizer
    por onde veio; ver `mtgvault/nomes.py`, que é quem decide o que o André lê.

    `commander` é o comandante nos formatos de comandante (2026-10-01). Quem o
    passa já o leu da FONTE — o `SB:` do .dec do mtgtop8, o `sideboard_deck` do
    mtgo.com —, antes de essas cartas serem fundidas no mainboard; é por isso que
    fica com `commander_fonte = 'sideboard'` e nunca é reescrito por um palpite.
    Ver `mtgvault/consenso.py`.

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
    cards = somar_cartas(cards)
    if not cards:
        return None
    fmt = fmt.lower()
    tier = event_tier(source, event_name)
    # A VIGIA DE CARTAS PASSA À FRENTE DOS DOIS FILTROS (André, 2026-09-26).
    # Uma lista com uma carta vigiada guarda-se venha de onde vier — é o sinal
    # que ele pediu, e as PRIMEIRAS aparições de um combo novo são precisamente
    # as que os dois filtros abaixo deitam fora (um 5-0 de liga, um torneio de 20
    # pessoas, a lista de um jogador que ele não segue). Só estas: a liga sem
    # carta vigiada continua a não se guardar, e o metagame não vê uma lista a
    # mais. Sem cartas vigiadas isto é sempre `[]` e nada muda.
    vigiadas = _vigia().nomes_na_lista(fmt, cards)
    # Ligas fora (regra 2026-09-07): nem se guardam, para o vault.db não crescer
    # com listas que nenhuma página conta. O Duel Commander é a exceção — lá as
    # ligas contam (colecao_config.json -> metagame_fontes["duel-commander"]).
    # A BUSCA (2026-10-13): num formato de busca, a liga guarda-se se servir um
    # alvo NOMEADO (um deck seguido com amostra baixa, um jogador vigiado) — e
    # continua a NÃO contar, porque o `League` não entra nos tiers. Só se
    # pergunta quando é mesmo uma liga que ia ser recusada.
    if (tier == "League" and "League" not in metagame_rules(fmt)["tiers"]
            and not vigiadas
            and not _busca().alvos_na_lista(con, fmt, cards, player)):
        return None
    # Formato sem metagame, seguido só por jogador (Pauper): guarda-se a lista de
    # quem está vigiado e mais nada. As `manual` passam sempre.
    if (source != "manual" and fmt in so_jogadores_vigiados()
            and not _jogador_vigiado(con, fmt, player) and not vigiadas):
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
            placement, url, content_hash, event_players, event_tier,
            commander, commander_fonte, arquetipo_fonte, arquetipo_fonte_de)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (source, source_key, fmt, event_name, event_date, player, placement,
         url, h, event_players, tier,
         commander or None, "sideboard" if commander else None,
         (arquetipo or "").strip() or None,
         arquetipo_de if (arquetipo or "").strip() else None),
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
