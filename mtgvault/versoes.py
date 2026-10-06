"""UM DECK POR FORMATO, COM VERSÕES POR DENTRO (André, 2026-10-04, à noite).

As palavras dele, à letra:

    *"vamos fazer uma coisa diferente, a ver como fica"*
    *"quero apenas manter decks que usem Mox Opal, tudo o resto e para vender
    (em modern)"*
    *"quero ficar com 1 deck e versoes do deck (como opcoes)"*
    *"De Modern quero apenas decks de Mox Opal / De Pioneer quero Apenas decks
    de Greasefang / de Standard apenas decks de Bant Airbend / Legacy ainda nao
    sei"*

**SUBSTITUI O MODELO DE 18 DECKS** de 2026-10-04 à tarde (as `decks_de_evento`,
dez de Modern e um de Pioneer, cada um um deck por direito). A estrutura passa a
ser: **um deck por formato**, e as variantes desse deck são **versões por
dentro**, como opções entre as quais ele escolhe uma. Não é um deck por versão —
é essa a diferença, e é toda a ordem.

    modern     -> UM deck «Affinity (Mox Opal)»  com 4 versões
    pioneer    -> UM deck «Greasefang»           com 3 versões
    standard   -> UM deck «Bant Airbend»         (revê em Janeiro)
    premodern  -> FICA COMO ESTÁ, 6 decks        (ele não lhe tocou)
    legacy     -> POR DECIDIR                    (não se escolhe nada)

NADA SE APAGA (a regra dele de 2026-09-09). Os nove decks de Modern que saem e o
UR Aggro de Pioneer **continuam no config e continuam consultáveis** — passam a
*«meta, não escolhido»* (`saiu`), com a data e a razão. Repor é tirar-lhes a
marca: a lista deles, a proveniência e as cartas ficam onde estavam.

O QUE UMA VERSÃO É
------------------
Uma versão é uma IDENTIDADE (o cluster `archetypes.id`) mais **uma lista REAL
que alguém jogou** — nunca um consenso. É a decisão dele de 2026-10-04 ao fim do
dia (*"as outras quero que esquecas as decklists e vamos focar nas decklists
baseadas em eventos reais"*): a lista de cada versão sai do `mtgvault.eventos`,
com a proveniência gravada em `listas_escolhidas`, exactamente como os
`decks_de_evento`. Fazer o consenso de cada cluster era ressuscitar o que ele
tinha acabado de enterrar nessa mesma noite.

Onde a lista já existe, **aponta-se para ela em vez de a duplicar**: a versão
`izzet-pinnacle` é a lista de qualificação dele (a caixa `modern`) e a versão
`broodwagon` é a lista do Martin_Dominguez (a caixa `pioneer`). Duas cópias da
mesma lista eram duas verdades à espera de discordarem.

A VERSÃO ESCOLHIDA E AS OUTRAS
------------------------------
`versao` é a que ele escolheu; as outras ficam ao lado como opções. **Todas as
versões protegem** — são o mesmo deck, e ele troca de versão sem ir comprar
tudo outra vez. O que a escolha muda é qual delas a página abre e qual conta
para as próprias/partilhadas.

«OUTROS DECKS QUE JOGAM <carta>» — DERIVADO, NUNCA ESCRITO À MÃO
----------------------------------------------------------------
*"Poe os cinco de fora MAS deixa-os visiveis numa lista 'outros decks que jogam
Mox Opal' … NAO decidas por ele incluir nem excluir definitivamente."* A lista
sai da BASE a cada corrida (`outros_que_jogam`): todos os clusters que jogam a
carta-chave e não são versões. Escrita à mão, ficava desactualizada no dia em
que aparecesse um deck novo — e é precisamente o deck novo que interessa ver.

Cada um diz se **passa o critério** (`criterio.exige`, hoje *Kappa Cannoneer* e
*Pinnacle Emissary* em pelo menos metade das listas do cluster), para a decisão
ficar à vista em vez de escondida numa escolha minha.

**O CRITÉRIO DA ORDEM DÁ SETE VERSÕES E NÃO QUATRO — medido, e dito.** Sobre a
base de 2026-10-04, os clusters de Modern que jogam Mox Opal e passam o teste
são **sete**: os quatro que ele nomeou (4380, 7614, 7525, 7527) e mais **7400,
7010 e 6491**, com 2, 2 e 1 listas. Ficaram **fora da escolha e à vista na lista
dos outros**, marcados `passa_criterio` — a leitura dele é que manda, e três
clusters de uma a duas listas não se metem num deck dele por iniciativa própria.

O LEGACY ESTÁ POR DECIDIR, E ISSO RETÉM CARTAS
----------------------------------------------
*"Legacy ainda nao sei"*. Enquanto um formato estiver `por_decidir`, uma carta
que se jogue nele acima de `corte_pct` das listas da janela **não vai à venda**:
é a regra **RLG** do `mtgvault.fases`. *"Tudo o resto é para vender (em modern)"*
não pode querer dizer vender staples de Legacy antes de ele escolher o deck de
Legacy — isso era obedecer à letra e desobedecer à intenção.

**A regra é GLOBAL e não só sobre o que este modelo liberta**, e é uma decisão:
uma regra que só valesse para «os nomes que estavam no modelo de 18 decks»
precisava desse conjunto congelado no config para sempre, e um conjunto
congelado é exactamente o que apodrece. Assim é sem estado, mais conservadora
(retém mais, vende menos) e desliga-se sozinha no dia em que ele escolher o
deck de Legacy.

MONTAR E PROTEGER SÃO DUAS PERGUNTAS (André, 2026-10-05, à letra)
-----------------------------------------------------------------
    *"quando digo as decklists que jogam Mox Opal, e porque assim ficamos com
    uma lista de cartas que eu gostaria de nao vender, tudo o resto e «seguro»
    vender"*
    *"aplica o mesmo para Legacy, assim jogo Mox Opal nos 2 formatos"*

**CORRIGE A LEITURA DE 04/10 À NOITE.** As quatro versões da Affinity foram
escolhidas a assumir que a lista de decks de Mox Opal era para **MONTAR**; é
para **PROTEGER**. Isso inverte o critério — passa a ser **INCLUSIVO e não
selectivo**:

* **MONTAR** continua a ser a versão escolhida (*"o deck principal é Affinity
  sem dúvida"*): é o `versoes`/`versao`, e é o `criterio.exige` (Kappa Cannoneer
  + Pinnacle Emissary) que decide quais os clusters que são versões.
* **PROTEGER** passa a ser **todas as listas que jogam a carta-chave**, sejam
  de que arquétipo forem — a regra **RP** do `fases`. Os cinco arquétipos que
  tinham ficado de fora (Scrabbling Claws, Jace/Song of Creation, Flame of Anor,
  Hammer Time, Erayo) **voltam a contar para a protecção**, e continuam fora das
  versões.

Juntar as duas ou ele montava decks que não quer, ou vendia cartas que quer —
por isso são dois conjuntos distintos e **dizem-no no ecrã**.

**O LEGACY ENTRA, com o mesmo critério**, e por isso **deixou de estar
`por_decidir`**: a consequência directa é que a RLG se desliga sozinha (é o que
ela foi escrita para fazer). Quem decide que um formato é inclusivo é
`criterio.protege_todas` no config — o Pioneer tem carta-chave e **não** o é, de
propósito: ali ele nomeou as três versões.

O UNIVERSO DE LISTAS É O MAIS LARGO, E ISSO É DELIBERADO
---------------------------------------------------------
As listas da carta-chave contam-se na **janela do consenso** e **SEM o filtro de
tier** do `sources.counting_sql`. É a mesma excepção — e a mesma razão — da R5:
*sub-contar aqui é VENDER uma carta que ele precisa*. É também o universo em que
os números que ele mediu batem ao exemplar: **modern 25 de 364 (6,9 %)**,
**legacy 23 de 171 (13,5 %)**. Com o filtro de tier dava 24 e 17.

O LIMIAR É DELE E NÃO MEU
--------------------------
`_limiar_listas` (omissão **1**, que é a letra do que ele pediu): em quantas das
listas da carta-chave uma carta tem de aparecer para ficar protegida. A **1**,
34 linhas ficam protegidas por aparecerem numa **única** lista. A página mostra
a curva entre 1 e 2 — a escolha é dele.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from . import eventos
from . import nomes as _nomes
from . import scryfall, sources

#: Quantas alternativas do meta se desenham por versão. A da Affinity tem 45
#: listas na janela: uma parede de 45 linhas onde ele procura uma alternativa é
#: o contrário de a mostrar. O TOTAL diz-se sempre ao lado.
ALT_MAX = 6


def _data_inversa(d) -> str:
    """Para ordenar por data DESCENDENTE numa chave crescente (o mesmo truque do
    `eventos._data_inversa`, que é privado àquele módulo)."""
    s = str(d or "")
    return "".join(chr(ord("9") - (ord(c) - ord("0"))) if c.isdigit() else c
                   for c in s)

#: `colecao_config.json -> decks_por_formato`.
CHAVE = "decks_por_formato"

#: A percentagem de listas de um formato por decidir acima da qual uma carta
#: fica retida. 5 % das 135 listas de Legacy da janela são 7 listas — abaixo
#: disso é uma carta avulsa, não uma staple do formato.
CORTE_PCT = 5.0

#: Que fracção das listas de um cluster tem de jogar cada carta de
#: `criterio.exige` para o cluster ser uma versão. Metade: num cluster de duas
#: listas uma carta que apareça numa só não é a identidade do deck.
#:
#: **Serve o MONTAR e nunca o PROTEGER** (2026-10-05): é isto que decide quais
#: os clusters que são versões do deck que ele monta. A protecção é inclusiva e
#: não passa por aqui.
PCT_CRITERIO = 50.0

#: Em quantas listas da carta-chave uma carta tem de aparecer para ficar
#: protegida pela **RP**. Um é a letra do que ele pediu (*"as decklists que
#: jogam Mox Opal"*, sem qualificação); a página mostra a curva e a escolha
#: é dele.
LIMIAR_LISTAS = 1

TEXTO_SAIU = "meta, não escolhido"
TEXTO_RETIDO = ("não vai à venda enquanto não escolheres o deck de "
                "{formato} — joga em {pct:.0f} % das listas desse formato")


# ---------------------------------------------------------------------------
# O bloco do config
# ---------------------------------------------------------------------------
def bloco(cfg: dict | None = None) -> dict:
    """`decks_por_formato`, ou `{}` quando o modelo não está ligado.

    Vazio, **nada muda**: o registo volta a ser o de 2026-10-04 à tarde, um deck
    por entrada. É o interruptor, como o `venda.mostrar` e o `cartas_vigiadas`.
    """
    cfg = sources.config() if cfg is None else cfg
    v = cfg.get(CHAVE)
    return {k: x for k, x in v.items()
            if not k.startswith("_") and isinstance(x, dict)} if isinstance(v, dict) else {}


def do_formato(fmt: str, cfg: dict | None = None) -> dict | None:
    """O deck único deste formato, ou `None` se o formato não entra no modelo.

    `None` quer dizer *"este formato fica como estava"* — é o caso do Premodern,
    que ele não mexeu, e de todos os outros que não nomeou.
    """
    return bloco(cfg).get((fmt or "").lower())


def formatos(cfg: dict | None = None) -> list[str]:
    return sorted(bloco(cfg))


def por_decidir(fmt: str, cfg: dict | None = None) -> bool:
    """*"Legacy ainda nao sei"*: o formato está no modelo e sem deck escolhido."""
    d = do_formato(fmt, cfg)
    return bool(d and d.get("por_decidir"))


def formatos_por_decidir(cfg: dict | None = None) -> list[str]:
    return [f for f in formatos(cfg) if por_decidir(f, cfg)]


def _versoes_escritas(fmt: str, cfg: dict | None = None) -> list[dict]:
    d = do_formato(fmt, cfg) or {}
    v = d.get("versoes")
    return [x for x in (v if isinstance(v, list) else []) if isinstance(x, dict)]


def versoes(fmt: str, cfg: dict | None = None) -> list[dict]:
    """As versões ESCRITAS no config que continuam na escolha.

    Num formato de versões derivadas (`versoes_todas`) esta lista deixou de ser
    o conjunto: é o conjunto das **anotações** (nome, `deck`, `principal`) e das
    versões CONHECIDAS que hoje não têm listas na janela. Quem responde «quais
    são as versões» nesse caso é o `versoes_derivadas`, que precisa da base.

    Continua a ser esta a lista que o motor da venda vê (`ids_que_ficam` →
    `nomes_que_ficam`, a regra RE) e a que o registo da página transforma em
    decks — as duas perguntam por versões **com lista fixada**, e uma versão
    derivada não tem nenhuma. Ver a nota em `versoes_derivadas`.

    **As que têm `_saiu` ficam de FORA** (2026-10-06): uma versão que saiu da
    escolha continua no config com a lista e a proveniência — *nada se apaga* —
    e é consultável pelo `versoes_saidas`, mas já não é um deck para montar. A
    marca tem a mesma forma do `_saiu` de um deck (`decks_de_evento`), de
    propósito: duas formas de dizer *«isto saiu»* discordavam no dia em que
    alguém repusesse uma só num dos sítios.
    """
    return [x for x in _versoes_escritas(fmt, cfg) if not x.get("_saiu")]


def versoes_saidas(fmt: str, cfg: dict | None = None) -> list[dict]:
    """As versões que SAÍRAM da escolha, com a lista e a razão intactas.

    *"as versoes que saem da escolha … ficam consultaveis como «meta, nao
    escolhido»"* (André, 2026-10-06). Repor uma é tirar-lhe o `_saiu`.
    """
    return [x for x in _versoes_escritas(fmt, cfg) if x.get("_saiu")]


def versoes_todas(fmt: str, cfg: dict | None = None) -> bool:
    """As versões deste formato DERIVAM do critério, em vez de ser lista fixa?

    *"no Modern, a unica coisa e que quero os decks que joguem Mox Opal, seja
    affinity, seja grinding station, seja outra coisa qualquer"* (André,
    2026-10-05). Em Modern a escolha passou a ser a MESMA pergunta que a
    protecção — um critério só, *joga Mox Opal* —, e por isso o conjunto não
    pode ser uma lista de `archetype_id` escrita à mão: daqui a uma semana havia
    um deck de Mox Opal de fora e ninguém reparava.

    **É chave PRÓPRIA e não o `protege_todas`**, de propósito: o Legacy é
    inclusivo para a protecção e tem `versoes: []` porque ele disse *"NADA se
    escolheu para MONTAR em Legacy"*. Pendurar isto no `protege_todas` dava-lhe
    oito versões que ele não pediu.
    """
    c = (do_formato(fmt, cfg) or {}).get("criterio") or {}
    return bool(c.get("versoes_todas"))


def id_derivado(fmt: str, aid: int) -> str:
    """O id de uma versão que a base trouxe e o config não anota.

    Sai do `archetype_id`, que é a única identidade estável que há (o
    `mtgvault.arquetipos` herda o id acima de 70 % de núcleo em comum) — nunca
    do nome, que muda de corrida para corrida.
    """
    return f"versao:{fmt}:a{int(aid)}"


def versao_escolhida(fmt: str, cfg: dict | None = None) -> str:
    """O `id` da versão que ele escolheu.

    Sem escolha escrita, é a PRIMEIRA da lista — e a lista está ordenada por ele.
    Devolver vazio punha a página sem nada para abrir num formato que tem decks.
    """
    d = do_formato(fmt, cfg) or {}
    vs = versoes(fmt, cfg)
    esc = str(d.get("versao") or "")
    if esc and any(v.get("id") == esc for v in vs):
        return esc
    return str(vs[0].get("id")) if vs else ""


def versao(fmt: str, vid: str | None = None, cfg: dict | None = None) -> dict | None:
    vid = vid or versao_escolhida(fmt, cfg)
    for v in versoes(fmt, cfg):
        if v.get("id") == vid:
            return v
    return None


class VersaoDesconhecida(ValueError):
    """Pediram uma versão que este formato não tem. É 409 no `webapp`, como a
    `VendaDesligada` e a `AlocacaoDupla` — nunca um 500: não é avaria, é um
    pedido de uma página aberta ontem no telemóvel."""


def escolher(cfg: dict, fmt: str, vid: str, hoje: str | None = None,
             validas=None) -> dict:
    """Grava a versão escolhida. Devolve o `cfg` (que é alterado no sítio).

    **Trocar para a que já lá está é um no-op** e não reescreve a data: um
    clique sem efeito não pode parecer uma decisão nova no histórico, que é a
    mesma regra do `precos.gravar_fonte` e do `fases.gravar_congelada`.

    `validas` são os ids que a página ofereceu, e serve as versões DERIVADAS:
    num formato `versoes_todas` a maior parte delas não está escrita no config,
    e validar só contra o config recusava um clique numa versão que a página
    acabou de desenhar. Quem o passa é quem tem ligação à base (o `webapp`);
    sem ele vale o config, que é o que os formatos de lista fixa querem.
    """
    fmt = (fmt or "").lower()
    d = (cfg.get(CHAVE) or {}).get(fmt)
    if not isinstance(d, dict):
        raise VersaoDesconhecida(f"o formato {fmt} não tem deck único neste modelo")
    ids = ([str(x) for x in validas] if validas is not None
           else [str(v.get("id")) for v in versoes(fmt, cfg)])
    if vid not in ids:
        tem = ", ".join(ids) or "nenhuma"
        raise VersaoDesconhecida(
            f"«{vid}» não é uma versão de {fmt}. As que há: {tem}")
    if d.get("versao") == vid:
        return cfg
    d["versao"] = vid
    d["versao_em"] = hoje or date.today().isoformat()
    return cfg


# ---------------------------------------------------------------------------
# Que decks ficam, e quais saíram
# ---------------------------------------------------------------------------
def deck_da_versao(v: dict) -> str:
    """O id do deck que guarda as cartas desta versão.

    Onde a lista já existia noutro deck (a caixa `modern` é a versão
    `izzet-pinnacle`), a versão aponta para lá — `deck` — em vez de ter uma
    segunda cópia da mesma lista. Onde não existia, a lista está em
    `listas_escolhidas[<id da versão>]` e o deck é a própria versão.
    """
    return str(v.get("deck") or v.get("id") or "")


def decks_das_versoes(fmt: str, cfg: dict | None = None) -> list[str]:
    """Os decks das versões DESTE formato: o de cada versão e os das alternativas.

    **AS ALTERNATIVAS CONTAM** (2026-10-06), e isto não é um detalhe: a lista de
    qualificação dele — o deck do RC de Ghent, a caixa `modern` — passou a ser a
    alternativa *«a tua lista»* da versão da Affinity, e sem esta linha perdia a
    protecção **RE** três dias antes do torneio. É a mesma razão por que *todas
    as versões protegem* (ver o cabeçalho): uma alternativa é uma lista para a
    qual ele pode trocar, e vender-lhe as cartas dela era desfazer a opção.

    Só as alternativas que apontam para um DECK; as do meta são listas de outras
    pessoas e não têm deck nenhum para guardar.
    """
    out = []
    for v in versoes(fmt, cfg):
        d = deck_da_versao(v)
        if d:
            out.append(d)
        for a in (v.get("alternativas") or []):
            if isinstance(a, dict) and str(a.get("deck") or "").strip():
                out.append(str(a["deck"]))
    return out


def ids_que_ficam(cfg: dict | None = None) -> set[str]:
    """Os ids de deck que o modelo GUARDA, em todos os formatos que ele nomeou.

    Os formatos fora do modelo (o Premodern) não entram aqui: lá continuam a
    mandar as caixas, como sempre.
    """
    return {d for f in formatos(cfg) for d in decks_das_versoes(f, cfg)}


def saiu(deck_id: str, cfg: dict | None = None) -> dict | None:
    """`{em, porque}` se este deck saiu da escolha, senão `None`.

    A marca é do DECK e vive no `decks_de_evento`/`caixas` dele (`_saiu`), não
    numa lista à parte: uma segunda lista de «quem saiu» discordava da primeira
    no dia em que alguém repusesse um deck só num dos sítios.
    """
    cfg = sources.config() if cfg is None else cfg
    for n in (cfg.get("decks_de_evento") or []):
        if isinstance(n, dict) and n.get("id") == deck_id:
            s = n.get("_saiu")
            return dict(s) if isinstance(s, dict) else None
    return None


def saidos(cfg: dict | None = None) -> dict[str, dict]:
    cfg = sources.config() if cfg is None else cfg
    out = {}
    for n in (cfg.get("decks_de_evento") or []):
        if isinstance(n, dict) and isinstance(n.get("_saiu"), dict):
            out[str(n.get("id"))] = dict(n["_saiu"])
    return out


# ---------------------------------------------------------------------------
# Os «outros decks que jogam a carta-chave» — DERIVADOS DA BASE
# ---------------------------------------------------------------------------
def carta_chave(fmt: str, cfg: dict | None = None) -> str:
    return str(((do_formato(fmt, cfg) or {}).get("criterio") or {}).get("carta") or "")


def _criterio(fmt: str, cfg: dict | None = None) -> tuple[str, list[str], float]:
    c = (do_formato(fmt, cfg) or {}).get("criterio") or {}
    exige = [str(x) for x in (c.get("exige") or []) if str(x).strip()]
    try:
        pct = float(c.get("pct_minima", PCT_CRITERIO))
    except (TypeError, ValueError):
        pct = PCT_CRITERIO
    return str(c.get("carta") or ""), exige, pct


def _pct_no_cluster(con, aid: int, nm: str) -> float:
    tot = con.execute("SELECT COUNT(*) c FROM decklists WHERE archetype_id=?",
                      [aid]).fetchone()["c"]
    if not tot:
        return 0.0
    n = con.execute(
        f"""SELECT COUNT(DISTINCT c.decklist_id) c FROM decklist_cards c
              JOIN decklists d ON d.id = c.decklist_id
             WHERE d.archetype_id = ? AND {scryfall.sql_nome('c.card_name')}""",
        [aid] + list(scryfall.params_nome(nm))).fetchone()["c"]
    return 100.0 * n / tot


def clusters_da_carta(con: sqlite3.Connection, fmt: str, carta: str,
                      desde: str | None = None) -> dict:
    """`archetype_id -> nº de listas` do formato que jogam a carta.

    `desde=None` é a história toda; com data é a janela. A chave `None` são as
    listas a que o agrupamento ainda não deu identidade — **contam-se e
    dizem-se, nunca viram versão**: uma versão precisa de um id estável, e uma
    lista sem cluster não tem nenhum.

    **Sem o filtro de tier do `sources.counting_sql`**, e é o mesmo universo —
    e a mesma razão — da RP: *"em Modern a escolha e a mesma coisa que a
    proteccao -- um criterio so"*. Dois universos para o mesmo critério davam
    um deck protegido que não era versão de nada.
    """
    cond = "AND d.event_date >= ?" if desde else ""
    par = [fmt] + ([desde] if desde else []) + list(scryfall.params_nome(carta))
    return {r["aid"]: r["n"] for r in con.execute(
        f"""SELECT d.archetype_id aid, COUNT(DISTINCT d.id) n FROM decklists d
             WHERE d.format = ? {cond}
               AND EXISTS (SELECT 1 FROM decklist_cards k
                            WHERE k.decklist_id = d.id
                              AND {scryfall.sql_nome('k.card_name')})
             GROUP BY d.archetype_id""", par)}


# ---------------------------------------------------------------------------
# AS FAMÍLIAS: SEIS DECKS DE MOX OPAL NÃO SE LEEM NUMA LISTA PLANA (2026-10-06)
# ---------------------------------------------------------------------------
# *"O MOX OPAL DE MODERN TEM SEIS FAMILIAS, nao uma. Mostra-as."* Com o critério
# inclusivo de 05/10 (*"seja affinity, seja grinding station, seja outra coisa
# qualquer"*) a lista de versões passou a ser tudo o que joga a carta-chave — e
# medido na base a 06/10 isso é **oito clusters** em Modern, de arquétipos que
# não têm nada a ver uns com os outros. Uma lista plana de oito linhas com nomes
# como *«Loki, God of Mischief / Waterlogged Grove / Sewer-veillance Cam»* não
# diz qual é qual.
#
# A FAMÍLIA DERIVA-SE DAS CARTAS, nunca do cluster — e essa é a decisão toda.
# O `archetype_id` é refeito todas as noites e **muda**: medido a 06/10, as
# CINCO anotações de `arquetipo_id` do config ficaram com zero listas na janela
# (ver o relatório desta ordem), o segundo dia seguido em que isso acontece. Uma
# família ancorada no cluster herdava essa instabilidade; ancorada numa carta
# distintiva (*Grinding Station*, *Colossus Hammer*, *Song of Creation*) é
# estável porque é a carta que faz o deck ser aquele deck.
#
# As famílias vivem no CONFIG, não aqui: são a leitura dele sobre o formato dele,
# e cada uma leva a razão ao lado. Sem a chave, **não há agrupamento** e a lista
# fica plana como estava — é o interruptor, como o `venda.mostrar`.
FAMILIA_OUTRA = "Outra"


def familias(fmt: str, cfg: dict | None = None) -> list[dict]:
    """As famílias deste deck único, pela ordem do config. Vazio = sem agrupar.

    Cada uma é `{nome, cartas, porque}`: as `cartas` são as DISTINTIVAS, e basta
    uma delas para a lista cair na família. A ORDEM manda — a primeira que casa
    ganha —, porque há listas que jogam cartas de duas famílias (um Grinding
    Station com Cranial Plating), e sem uma ordem a mesma lista caía numa
    família ou noutra conforme a passagem.
    """
    c = (do_formato(fmt, cfg) or {}).get("criterio") or {}
    fs = c.get("familias")
    out = []
    for f in (fs if isinstance(fs, list) else []):
        if not isinstance(f, dict) or not str(f.get("nome") or "").strip():
            continue
        cs = [str(x) for x in (f.get("cartas") or []) if str(x).strip()]
        if cs:
            out.append({"nome": str(f["nome"]).strip(), "cartas": cs,
                        "porque": str(f.get("_porque") or "")})
    return out


def familia_das_cartas(nms, fams: list[dict]) -> str:
    """A família de UMA lista, pelas cartas que ela joga.

    `nms` são os nomes da lista (já canonizados ou não — canoniza-se aqui, que é
    a regra de 2026-10-04: a lista traz a frente de uma dupla face e o catálogo
    o nome inteiro). Sem família que case, `FAMILIA_OUTRA` — dito e não
    escondido numa das outras.
    """
    tem = {scryfall.chave(n) for n in nms}
    for f in fams:
        if any(scryfall.chave(c) in tem for c in f["cartas"]):
            return f["nome"]
    return FAMILIA_OUTRA


def _cartas_das_listas(con: sqlite3.Connection, ids) -> dict[int, list[str]]:
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    out: dict[int, list[str]] = {}
    for r in con.execute(
            f"SELECT decklist_id d, card_name nm FROM decklist_cards "
            f"WHERE decklist_id IN ({ph})", ids):
        out.setdefault(r["d"], []).append(r["nm"])
    return out


def cartas_fixadas(deck_id: str, cfg: dict | None = None) -> list[str]:
    """Os nomes da lista FIXADA de um deck, do `listas_escolhidas`. `[]` sem ela.

    **Uma CAIXA está lá pelo SLOT e não pelo id do deck**, e isto custou uma
    passagem: a versão `izzet-pinnacle` aponta para `caixa:modern` e a lista de
    qualificação vive em `listas_escolhidas["modern"]`, porque é o
    `padrao.fixar` que a escreve e ele indexa pelo slot. Sem os dois nomes, a
    família do deck principal saía *«Outra»* com a lista dele ali ao lado.
    """
    cfg = sources.config() if cfg is None else cfg
    le = cfg.get("listas_escolhidas") or {}
    chaves = [deck_id]
    if deck_id.startswith("caixa:"):
        chaves.append(deck_id.split(":", 1)[1])
    for k in chaves:
        cs = (le.get(k) or {}).get("cards") or []
        if cs:
            return [c[1] for c in cs if len(c) >= 2]
    return []


def familia_do_cluster(con: sqlite3.Connection, fmt: str, aid: int,
                       cfg: dict | None = None, desde: str | None = None,
                       cache: dict | None = None) -> dict:
    """A família de um cluster: `{nome, n, de}` — a da MAIORIA das listas dele.

    A pluralidade e não uma regra de percentagem mínima: com um mínimo de 50 %
    um cluster que não chegasse lá caía em *«Outra»* e perdia-se a informação
    que ele pediu. Empate desfaz-se pela ORDEM do config, que é determinista —
    a lição do desempate alfabético dos nomes de 2026-10-02: uma família que
    mude de um dia para o outro sem nada ter mudado é o defeito, não o dado.

    Conta as listas da JANELA; um cluster que hoje não tenha nenhuma (as versões
    *conhecidas*) conta a história toda, senão ficava sem família nenhuma por
    não se jogar esta semana.
    """
    cfg = sources.config() if cfg is None else cfg
    cache = {} if cache is None else cache
    fams = familias(fmt, cfg)
    if not fams:
        return {"nome": "", "n": 0, "de": 0}
    chave = ("_fam", fmt, int(aid))
    if chave in cache:
        return cache[chave]
    desde = sources.consenso_desde() if desde is None else desde
    ids = [r["id"] for r in con.execute(
        "SELECT id FROM decklists WHERE format = ? AND archetype_id = ? "
        "AND event_date >= ?", [fmt, int(aid), desde])]
    if not ids:
        ids = [r["id"] for r in con.execute(
            "SELECT id FROM decklists WHERE format = ? AND archetype_id = ?",
            [fmt, int(aid)])]
    cont: dict[str, int] = {}
    for nms in _cartas_das_listas(con, ids).values():
        f = familia_das_cartas(nms, fams)
        cont[f] = cont.get(f, 0) + 1
    ordem = {f["nome"]: i for i, f in enumerate(fams)}
    ordem[FAMILIA_OUTRA] = len(fams)
    melhor = min(cont.items(), key=lambda kv: (-kv[1], ordem.get(kv[0], 99)),
                 default=(FAMILIA_OUTRA, 0))
    out = {"nome": melhor[0], "n": melhor[1], "de": len(ids)}
    cache[chave] = out
    return out


def _familia_da_versao(con: sqlite3.Connection, fmt: str, aid: int, v: dict,
                       cfg: dict | None, desde: str | None,
                       cache: dict | None) -> str:
    """A família de uma versão de CLUSTER, com a lista do deck como recurso.

    A ordem é: o agrupamento (é ele que sabe o que se joga) e, só quando o
    cluster não tem uma única lista, as cartas da lista FIXADA do deck que a
    versão aponta. Nunca ao contrário: a lista fixada é de um dia, o cluster é o
    deck a jogar-se.
    """
    f = familia_do_cluster(con, fmt, aid, cfg, desde, cache)
    if f["de"]:
        return f["nome"]
    nms = cartas_fixadas(deck_da_versao(v), cfg) if v else []
    return familia_das_cartas(nms, familias(fmt, cfg)) if nms else f["nome"]


def contagem_de_familias(vs: list[dict], fams: list[dict]) -> list[dict]:
    """`[{nome, versoes, listas}]` pela ordem do config, só as que têm versões.

    É a CONTAGEM que ele pediu ao lado de cada família. `versoes` é quantas
    versões caem lá e `listas` quantas listas da janela elas somam — os dois,
    porque uma família com uma versão de 53 listas e outra com três de uma lista
    cada não são a mesma coisa, e um número só escondia isso.
    """
    ordem = [f["nome"] for f in fams] + [FAMILIA_OUTRA]
    cont: dict[str, dict] = {}
    for v in vs:
        nm = v.get("familia") or FAMILIA_OUTRA
        d = cont.setdefault(nm, {"nome": nm, "versoes": 0, "listas": 0})
        d["versoes"] += 1
        d["listas"] += int(v.get("listas") or 0)
    return [cont[n] for n in ordem if n in cont]


def familias_que_protegem(con: sqlite3.Connection, fmt: str,
                          cfg: dict | None = None,
                          desde: str | None = None) -> list[dict]:
    """As famílias do universo que a **RP** protege: `[{nome, listas, porque}]`.

    AS FAMÍLIAS MUDARAM DE SÍTIO E NÃO SE PERDERAM (2026-10-06). Nasceram a
    06/10 de manhã para tornar legível a lista de **versões** derivadas (oito
    clusters de Mox Opal numa lista plana não se lê). Com o Modern a fechar em
    três versões nomeadas ao fim do dia, as versões deixaram de precisar de
    agrupamento — mas o universo da PROTECÇÃO continua a ter as mesmas seis
    famílias, e é lá que a informação vale agora: é a resposta a *«o que é que
    o critério do Mox Opal me está a guardar»*.

    Deixá-las cair com o `versoes_todas` era apagar em silêncio um bloco que ele
    viu ontem — o padrão que este vault passa o tempo a evitar. Conta LISTAS (e
    não versões, que já não as há aqui): é o número que diz o peso de cada
    família no formato.
    """
    cfg = sources.config() if cfg is None else cfg
    fams = familias(fmt, cfg)
    carta = carta_chave(fmt, cfg)
    if not (fams and carta and protege_todas(fmt, cfg)):
        return []
    desde = desde or sources.consenso_desde()
    ids = listas_da_carta(con, fmt, carta, desde)
    cont: dict[str, int] = {}
    for nms in _cartas_das_listas(con, ids).values():
        f = familia_das_cartas(nms, fams)
        cont[f] = cont.get(f, 0) + 1
    ordem = {f["nome"]: (i, f.get("porque") or "") for i, f in enumerate(fams)}
    ordem[FAMILIA_OUTRA] = (len(fams), "")
    return [{"nome": n, "listas": cont[n], "porque": ordem.get(n, (99, ""))[1]}
            for n in sorted(cont, key=lambda x: ordem.get(x, (99, ""))[0])]


# ---------------------------------------------------------------------------
# UMA VERSÃO PODE ESTAR ANCORADA NUMA LISTA, E NÃO NUM CLUSTER (2026-10-06)
# ---------------------------------------------------------------------------
# As duas listas do CesarMerjan não podiam ser versões derivadas, e a razão é
# medida: a do Grinding Station (05/10) está num cluster que nasceu ontem e a do
# Song of Creation (28/09) **não tem cluster nenhum** (`archetype_id` a NULL) e
# é de um dia ANTES da janela do consenso. Pela regra de 05/10 — *"uma lista sem
# cluster conta-se e diz-se e NUNCA vira versão, porque uma versão precisa de um
# id estável"* — nenhuma delas entrava.
#
# A saída é a que o resto do vault já usa para os decks DELE desde 2026-10-04:
# a identidade é a **LISTA FIXADA** (`listas_escolhidas[<id>]`, com as cartas e a
# proveniência gravadas pelo `eventos.fixar`), e o id é o do config. Isso dá-lhe
# duas coisas que um ponteiro para o cluster não dava: sobrevive ao
# `rebuild_archetypes` de cada noite **e** ao `prune_decklists(30)`, que apaga a
# decklist #24603 por volta de 28/10.
#
# Uma versão fixa tem `arquetipo_id` a `None` — é por aí que se distingue — e
# **nunca é órfã**: não tem cluster para perder.
def versoes_fixas(fmt: str, cfg: dict | None = None) -> list[dict]:
    """As versões ancoradas numa LISTA FIXADA e não num cluster do agrupamento."""
    return [v for v in versoes(fmt, cfg) if v.get("arquetipo_id") is None]


def jogadores(fmt: str, cfg: dict | None = None) -> list[str]:
    """Os jogadores cujas listas são versões deste deck, por ordem alfabética.

    *"Marca-os como «do CesarMerjan» para ele os distinguir dos outros"* (André,
    2026-10-06). A marca é do CONFIG (`versoes[].jogador`) e não derivada da
    proveniência da lista: é ele que diz que segue aquele jogador, e a
    proveniência diz só quem jogou aquela lista — são duas coisas, e a segunda
    não implica a primeira (metade das listas do meta têm jogador e nenhum é
    seguido).
    """
    return sorted({str(v["jogador"]).strip() for v in versoes(fmt, cfg)
                   if str(v.get("jogador") or "").strip()})


def principal(fmt: str, cfg: dict | None = None) -> str:
    """O `id` da versão que é o deck PRINCIPAL, ou vazio.

    *"o deck principal e Affinity sem duvida"* (André, 2026-10-04). Não é a
    versão ESCOLHIDA nem o mesmo eixo: a escolhida é a que ele vai montar
    agora e muda com um toque; a principal é a identidade do deck e está
    escrita no config. Hoje coincidem, e podem deixar de coincidir.
    """
    for v in versoes(fmt, cfg):
        if v.get("principal"):
            return str(v.get("id") or "")
    return ""


# ---------------------------------------------------------------------------
# O UNIVERSO DE UMA VERSÃO SAI DAS CARTAS, NUNCA DO CLUSTER (2026-10-06)
# ---------------------------------------------------------------------------
# *"vou tentar ter correspondencia de decks em papel com os decks no MTGO …
# entao modern sera o Izzet Affinity (Weapons) + Oswald + Versao com Cori-Steel
# Cutter"*. O Modern fechou em TRÊS versões nomeadas, e cada uma tem de saber
# dizer quantas listas do meta são dela — para ele ver quais têm dados e quais
# são uma aposta.
#
# PORQUE É PELA CARTA E NÃO PELO `archetype_id`: o cluster é refeito todas as
# noites e muda. Medido nos três dias seguidos antes desta ordem, as anotações
# de `arquetipo_id` deste bloco ficaram com ZERO listas na janela — a 05/10 o
# 7614 do deck de Ghent fundiu-se no 5100, a 06/10 o 5100 passou a 7844. Uma
# carta como *Weapons Manufacturing* não muda.
#
# E O NÚMERO DELE SÓ FECHA ASSIM: a ordem diz *"45 listas desde 29/09"* para a
# Affinity e o cluster 7844 tem **53**. As 45 são exactamente as listas que
# jogam **Weapons Manufacturing** — as outras 8 do cluster não a jogam. O
# universo da carta é o que ele mediu, e é o estável.
#
# CONSEQUÊNCIA BOA: uma versão sem `arquetipo_id` **nunca é órfã** (não há
# cluster para perder), e por isso o aviso de 05/10 deixa de poder disparar
# falso no deck principal. O `_orfas` continua de pé para quem use clusters.
def cartas_do_meta(v: dict) -> list[str]:
    """As cartas que identificam as listas do meta desta versão. `[]` = nenhuma.

    `versoes[].meta.cartas`, e são **todas exigidas** (conjunção): o Cori-Steel
    Cutter com Mox Opal são 4 listas e o Cori-Steel sozinho 104 — e a diferença
    é precisamente a decisão que ele tem de tomar.
    """
    m = v.get("meta") if isinstance(v.get("meta"), dict) else {}
    return [str(x) for x in (m.get("cartas") or []) if str(x).strip()]


def _sql_tem_cartas(cartas: list[str], alias: str = "d") -> tuple[str, list]:
    cond, par = [], []
    for i, c in enumerate(cartas):
        cond.append(f"""EXISTS (SELECT 1 FROM decklist_cards km{i}
                                 WHERE km{i}.decklist_id = {alias}.id
                                   AND {scryfall.sql_nome(f'km{i}.card_name')})""")
        par += list(scryfall.params_nome(c))
    return (" AND ".join(cond) or "1=1"), par


def listas_do_meta(con: sqlite3.Connection, fmt: str, cartas: list[str],
                   desde: str | None = None) -> list[dict]:
    """As listas da janela que jogam TODAS as `cartas`, com a proveniência.

    **Sem o filtro de tier**, pela razão de sempre neste bloco (a RP, a R5): o
    Oswald só volta a existir no meta porque as ligas entraram a 05/10 — as
    duas listas dele são 5-0 de liga, e com o filtro não havia alternativa
    nenhuma para lhe mostrar.
    """
    if not cartas:
        return []
    desde = desde or sources.consenso_desde()
    cond, par = _sql_tem_cartas(cartas)
    return [dict(r) for r in con.execute(
        f"""SELECT d.id, d.player, d.event_name, d.event_date, d.event_tier,
                   d.event_players, d.placement, d.source, d.archetype_id
              FROM decklists d
             WHERE d.format = ? AND d.event_date >= ? AND {cond}
             ORDER BY d.event_date DESC, d.id""", [fmt, desde] + par)]


def ambiguidade_da_versao(con: sqlite3.Connection, fmt: str, v: dict,
                          cfg: dict | None = None,
                          desde: str | None = None) -> dict | None:
    """«Esta carta tem outro deck muito mais jogado» — com os DOIS números.

    *"CUIDADO COM A AMBIGUIDADE, e diz-lha no relatorio: ha 104 listas de Modern
    com Cori-Steel Cutter desde 29/09, mas SO 4 com Mox Opal. As outras 100 sao
    UR Prowess … Poe a alternativa a vista com os dois numeros (4 contra 100) e
    deixa-o decidir -- NAO escolhas por ele."*

    Os dois números saem da BASE e nunca do config — escritos à mão, ficavam
    desactualizados no dia seguinte, que é precisamente o dia em que a decisão
    dele dependeria deles. O config só diz QUAL é a carta ambígua e porquê.

    `None` quando a versão não declara ambiguidade nenhuma.
    """
    cfg = sources.config() if cfg is None else cfg
    m = v.get("meta") if isinstance(v.get("meta"), dict) else {}
    amb = m.get("ambiguidade") if isinstance(m.get("ambiguidade"), dict) else None
    carta = str((amb or {}).get("carta") or "").strip()
    cartas = cartas_do_meta(v)
    if not (carta and cartas):
        return None
    desde = desde or sources.consenso_desde()
    minhas = {r["id"] for r in listas_do_meta(con, fmt, cartas, desde)}
    todas = listas_do_meta(con, fmt, [carta], desde)
    outras = [r for r in todas if r["id"] not in minhas]
    # O OUTRO DECK sai do agrupamento das listas que ficam de fora, e o nome do
    # `mtgvault.nomes` (a votação de 2026-10-02) com a etiqueta como recurso —
    # nunca de um nome escrito à mão nesta ordem.
    cont: dict = {}
    for r in outras:
        cont[r["archetype_id"]] = cont.get(r["archetype_id"], 0) + 1
    maior = max(cont.items(), key=lambda kv: (kv[1], kv[0] or 0), default=None)
    outro = None
    if maior and maior[0] is not None:
        aid = maior[0]
        rot = _nomes.nome_do_cluster(con, aid, fmt) or {}
        lab = con.execute("SELECT label FROM archetypes WHERE id=?",
                          [aid]).fetchone()
        outro = {"arquetipo_id": aid, "listas": maior[1],
                 "nome": (rot.get("nome") or ""),
                 "label": ((lab["label"] if lab else "") or "")}
    return {
        "carta": carta, "cartas": cartas,
        "com": len(minhas), "so_a_carta": len(todas), "outras": len(outras),
        "outro": outro, "porque": str((amb or {}).get("_porque") or ""),
        "desde": desde,
    }


def alternativas_da_versao(con: sqlite3.Connection, fmt: str, v: dict,
                           cfg: dict | None = None,
                           desde: str | None = None) -> list[dict]:
    """As listas que ele pode querer VER ao lado da desta versão.

    Duas origens, e cada uma diz de onde vem:

    * **`alternativas` do config** — um DECK do registo (a lista dele, p.ex.):
      *"Mostra-as como alternativas ao lado da dele, nao em vez dela"*;
    * **o META** — as listas da janela que jogam as `meta.cartas`, menos a que
      esta versão já usa. Derivadas da base: uma lista nova aparece sozinha.

    Cada alternativa do meta traz o que ela tem **a mais** do que a lista desta
    versão — é a pergunta dele à letra (*"A do jinavie tem o combo Thopter
    Foundry + Sword of the Meek + Urza Lord High Artificer, que a dele nao tem:
    vale a pena ele ver"*). Sem isso, duas listas do mesmo arquétipo lêem-se
    como a mesma coisa.
    """
    cfg = sources.config() if cfg is None else cfg
    desde = desde or sources.consenso_desde()
    out: list[dict] = []
    for a in (v.get("alternativas") or []):
        if not isinstance(a, dict) or not str(a.get("deck") or "").strip():
            continue
        out.append({"origem": "deck", "deck": str(a["deck"]),
                    "rotulo": str(a.get("rotulo") or ""),
                    "porque": str(a.get("_porque") or "")})
    cartas = cartas_do_meta(v)
    if not cartas:
        return out
    minha = cartas_fixadas(deck_da_versao(v), cfg)
    tenho_nm = {scryfall.chave(n) for n in minha}
    meu_dl = ((cfg.get("listas_escolhidas") or {})
              .get(deck_da_versao(v)) or {}).get("fonte_decklist")
    rs = [r for r in listas_do_meta(con, fmt, cartas, desde)
          if not (meu_dl and int(r["id"]) == int(meu_dl))]
    # AS MELHORES PRIMEIRO, E UM TECTO. A versão da Affinity tem **45** listas na
    # janela: desenhá-las todas era uma parede de 45 linhas onde ele procura uma
    # alternativa — o contrário de a mostrar. A ordem é a mesma régua do
    # `mtgvault.eventos` (presencial antes de online, campo maior, melhor
    # classificação, mais recente), por isso as que ficam à vista são as que
    # valem; o TOTAL vai ao lado, para o tecto não esconder que há mais.
    rs.sort(key=lambda r: (eventos.peso_tier(r["event_tier"]),
                           -int(r["event_players"] or 0),
                           eventos.valor_classificacao(r["placement"]),
                           _data_inversa(r["event_date"]), r["id"]))
    for r in rs[:ALT_MAX]:
        nms = [x["card_name"] for x in con.execute(
            "SELECT DISTINCT card_name FROM decklist_cards WHERE decklist_id=?",
            [r["id"]])]
        extra = sorted({n for n in nms if scryfall.chave(n) not in tenho_nm})
        out.append({
            "origem": "meta", "decklist_id": r["id"],
            "jogador": r["player"] or "", "evento": r["event_name"] or "",
            "data": r["event_date"] or "", "tier": r["event_tier"] or "",
            "jogadores": r["event_players"], "classificacao": r["placement"] or "",
            "fonte": r["source"] or "", "extra": extra,
            "extra_n": len(extra),
        })
    if len(rs) > ALT_MAX:
        out.append({"origem": "mais", "n": len(rs) - ALT_MAX, "total": len(rs)})
    return out


def versoes_derivadas(con: sqlite3.Connection, fmt: str,
                      cfg: dict | None = None, cache: dict | None = None
                      ) -> dict:
    """As versões como a BASE as diz, mais as ANOTAÇÕES do config.

    O conjunto é **derivado** (`versoes_todas`) e por isso um arquétipo novo
    com a carta-chave entra sozinho na corrida em que aparecer — era isso que
    uma lista de `archetype_id` a martelo não fazia.

    Três grupos, e cada versão diz em qual está:

    * **`na_janela`** — joga a carta-chave na janela do consenso: é um deck que
      se está a jogar agora. Entram todos, anotados ou não.
    * **conhecida, `listas = 0`** — está anotada no config e hoje não tem
      listas na janela. **Não desaparece e não se inventa como actual**: é o
      caso do Grinding Station, que ele deu como exemplo e que tem zero listas
      desde 29/09 em qualquer formato. Esconder era mentir-lhe por omissão;
      mostrá-la ao lado das outras era mentir-lhe por igualdade.
    * o resto fica em `fora_da_janela` — **contado e dito, não listado**:
      quinze clusters de uma lista cada, de antes da janela, não são quinze
      versões do deck dele. Um que volte a aparecer entra pelo primeiro grupo.

    O NOME sai, por esta ordem: do config (é dele), do `mtgvault.nomes` (o nome
    que a FONTE dá às listas do cluster, a votação de 2026-10-02) e, em último,
    da etiqueta do agrupamento — marcada `etiqueta`, porque um nome gerado com
    a cara de um nome verdadeiro já custou três erros.
    """
    cfg = sources.config() if cfg is None else cfg
    cache = {} if cache is None else cache
    carta = carta_chave(fmt, cfg)
    anot = {str(v.get("arquetipo_id")): v for v in versoes(fmt, cfg)
            if v.get("arquetipo_id") is not None}
    esc = versao_escolhida(fmt, cfg)
    prin = principal(fmt, cfg)
    if not (versoes_todas(fmt, cfg) and carta):
        return {"derivado": False, "versoes": [], "sem_cluster": 0,
                "fora_da_janela": {"clusters": 0, "listas": 0}, "carta": carta}

    desde = sources.consenso_desde()
    jan = clusters_da_carta(con, fmt, carta, desde)
    tod = clusters_da_carta(con, fmt, carta)
    sem_cluster = int(jan.get(None, 0) or 0)
    # Uma lista sem cluster não é uma versão — mas a FONTE pode dar-lhe nome, e
    # «1 lista sem arquétipo» sem o nome ao lado é informação a menos sobre uma
    # lista que existe mesmo.
    #
    # QUEM RESPONDE É O `mtgvault.nomes`, e nunca uma leitura do
    # `arquetipo_fonte` aqui: essa coluna tem UM leitor só, e o
    # `test_nomes_arquetipo.caso_a_pergunta_do_nome_vive_num_sitio_so`
    # apanhou-me a lê-la à mão — com razão, porque um segundo leitor vota de
    # outra maneira num dia qualquer, em silêncio. Aqui a pergunta é a do
    # `nome_das_listas` (*"como se chama este conjunto de listas"*) aplicada a
    # cada lista sozinha, porque é isso que elas são: avulsas.
    sem_nomes: list[str] = []
    if sem_cluster:
        ids = [r["id"] for r in con.execute(
            f"""SELECT d.id FROM decklists d
                 WHERE d.format = ? AND d.event_date >= ?
                   AND d.archetype_id IS NULL
                   AND EXISTS (SELECT 1 FROM decklist_cards k
                                WHERE k.decklist_id = d.id
                                  AND {scryfall.sql_nome('k.card_name')})
                 ORDER BY d.id""",
            [fmt, desde] + list(scryfall.params_nome(carta)))]
        for i in ids:
            rot = _nomes.nome_das_listas(con, [i])
            nm = (rot or {}).get("nome")
            if nm and nm not in sem_nomes:
                sem_nomes.append(nm)
        sem_nomes.sort()

    def _nome(aid: int, v: dict | None) -> tuple[str, str]:
        if v and v.get("nome"):
            return str(v["nome"]), "config"
        rot = _nomes.nome_do_cluster(con, aid, fmt, cache=cache) or {}
        if rot.get("nome"):
            return str(rot["nome"]), str(rot.get("origem") or "fonte")
        r = con.execute("SELECT label FROM archetypes WHERE id=?", [aid]).fetchone()
        return ((r["label"] if r else "") or f"arquétipo {aid}"), "etiqueta"

    fams = familias(fmt, cfg)
    vs = []
    vistos = set()
    # (1) o que se joga AGORA, e (2) as conhecidas sem listas na janela.
    alvos = [(a, True) for a in jan if a is not None]
    alvos += [(int(a), False) for a in anot
              if int(a) not in jan and int(a) in tod]
    # Uma anotada que o agrupamento já não conhece de todo não se deita fora:
    # o cluster pode ter sido refeito, e a anotação é uma decisão dele.
    alvos += [(int(a), False) for a in anot if int(a) not in tod]
    for aid, na_janela in alvos:
        if aid in vistos:
            continue
        vistos.add(aid)
        v = anot.get(str(aid)) or {}
        nm, origem = _nome(aid, v)
        vid = str(v.get("id") or id_derivado(fmt, aid))
        vs.append({
            "id": vid, "arquetipo_id": aid, "nome": nm, "origem_nome": origem,
            "deck": deck_da_versao(v) if v.get("deck") or v.get("id") else "",
            "listas": int(jan.get(aid, 0) or 0),
            "listas_total": int(tod.get(aid, 0) or 0),
            "na_janela": bool(na_janela),
            "anotada": bool(v),
            "fixa": False, "jogador": str(v.get("jogador") or ""),
            # A FAMÍLIA DE UM CLUSTER VAZIO SAI DA LISTA DO PRÓPRIO DECK, e isto
            # não é um caso de bordo: medido a 06/10, o cluster do deck
            # PRINCIPAL (a lista de qualificação do RC de Ghent) ficou com zero
            # listas e a família dele saía *«Outra»* — o deck dele, sem família,
            # na página por onde ele vai sleevar. Quando o agrupamento não tem
            # cartas para dar, a lista fixada da caixa tem.
            "familia": (_familia_da_versao(con, fmt, aid, v, cfg, desde, cache)
                        if fams else ""),
            "principal": vid == prin,
            "escolhida": vid == esc,
            "porque": str(v.get("_porque") or ""),
        })
    # (3) AS VERSÕES ANCORADAS NUMA LISTA FIXADA. Entram sempre, anotadas ou
    # não — são decks DELE, não um achado do agrupamento —, e a família sai das
    # cartas da própria lista. `na_janela` é a DATA da lista contra a janela do
    # consenso: a do Song of Creation é de 28/09, um dia antes de ela abrir, e
    # isso tem de ser DITO (é o caso do Greasefang de 04/10) em vez de a pôr
    # entre as que se jogam agora.
    le = cfg.get("listas_escolhidas") or {}
    for v in versoes_fixas(fmt, cfg):
        vid = str(v.get("id") or "")
        if not vid:
            continue
        rec = le.get(deck_da_versao(v)) or {}
        prov = rec.get("evento") or {}
        data = str(prov.get("data") or "")
        cs = [c[1] for c in (rec.get("cards") or []) if len(c) >= 2]
        vs.append({
            "id": vid, "arquetipo_id": None,
            "nome": str(v.get("nome") or vid), "origem_nome": "config",
            "deck": deck_da_versao(v),
            "listas": 0, "listas_total": 0,
            "na_janela": bool(data and data >= desde),
            "anotada": True, "fixa": True,
            "jogador": str(v.get("jogador") or ""),
            "data": data, "evento": str(prov.get("evento") or ""),
            "familia": familia_das_cartas(cs, fams) if fams and cs else "",
            "principal": vid == prin, "escolhida": vid == esc,
            "porque": str(v.get("_porque") or ""),
        })
    vs.sort(key=lambda d: (not d["na_janela"], -d["listas"], -d["listas_total"],
                           d["nome"]))
    fora = {a: n for a, n in tod.items()
            if a is not None and a not in jan and a not in vistos}
    return {
        "derivado": True, "carta": carta, "versoes": vs,
        "sem_cluster": sem_cluster, "sem_cluster_nomes": sem_nomes,
        "desde": desde,
        "familias": contagem_de_familias(vs, fams) if fams else [],
        "jogadores": jogadores(fmt, cfg),
        "fora_da_janela": {"clusters": len(fora), "listas": sum(fora.values())},
        "orfas": _orfas(vs),
    }


# ---------------------------------------------------------------------------
# A ANOTAÇÃO QUE PERDEU O CLUSTER (2026-10-05)
# ---------------------------------------------------------------------------
# O `archetype_id` é refeito **todas as noites** (`analysis.rebuild_archetypes`)
# e é estável só enquanto a ETIQUETA do cluster for — a tabela faz
# `ON CONFLICT(format, label)`, por isso um cluster que mude de composição muda
# de etiqueta e **ganha um id novo**. As anotações do config são por
# `arquetipo_id`.
#
# Aconteceu no dia em que isto foi escrito, e é por isso que existe: as 430
# listas que as ligas trouxeram à janela de Modern fundiram o cluster 7614 (25
# listas, nascido no dia anterior) no 5100 (41 listas, de 03/09). A anotação do
# deck **principal** — o deck com que ele vai ao RC de Ghent — ficou a apontar
# para um cluster com ZERO listas, e a página mostrava-o no grupo das
# *«conhecidas, sem listas na janela»* enquanto a Affinity a sério aparecia por
# baixo como uma versão nova, sem nome e sem a marca. **Nada dava erro.** É o
# padrão do `event_tier` outra vez, sobre a página por onde ele vai sleevar.
#
# A correcção de fundo é a identidade estável por NÚCLEO que o
# `mtgvault/arquetipos.py` já faz para as sugestões de Premodern (id do núcleo,
# herdado acima de 70 %), aplicada à tabela `archetypes` — é a ordem
# `mtg-top8-por-edicao`. Até lá, isto **diz-o** em vez de o deixar passar: a
# alternativa a um aviso não é um vault certo, é um vault errado em silêncio.
#
# O CRIVO É ESTREITO DE PROPÓSITO: só a versão **principal** ou a **escolhida**.
# As outras quatro conhecidas (Weapons, Cranial, Seachrome, Grinding Station)
# têm legitimamente zero listas na janela — é o estado que a ordem de 04/10
# escolheu mostrar — e marcá-las era pôr um aviso permanente a piscar, que é um
# aviso que se deixa de ler.
def _orfas(vs: list[dict]) -> list[dict]:
    """As versões que CLAMAM ser o deck e não têm uma lista na janela.

    `candidato` é a maior versão sem anotação: é quase sempre o cluster para
    onde o deck foi, e é o que se põe no `arquetipo_id` da anotação.
    """
    candidatos = [v for v in vs if v["na_janela"] and not v["anotada"]]
    cand = max(candidatos, key=lambda d: d["listas"], default=None)
    out = []
    for v in vs:
        if v["listas"] or not (v["principal"] or v["escolhida"]):
            continue
        # UMA VERSÃO FIXA NUNCA É ÓRFÃ (2026-10-06): a identidade dela é a lista
        # gravada, não um cluster, por isso não há cluster para perder. Sem esta
        # guarda, a versão do CesarMerjan que ele escolhesse aparecia todos os
        # dias com o aviso de «o agrupamento mudou de baixo dela» — um aviso
        # permanente a piscar, que é um aviso que se deixa de ler.
        if v.get("fixa"):
            continue
        out.append({
            "id": v["id"], "nome": v["nome"],
            "arquetipo_id": v["arquetipo_id"],
            "principal": v["principal"], "escolhida": v["escolhida"],
            "candidato": ({"arquetipo_id": cand["arquetipo_id"],
                           "nome": cand["nome"], "listas": cand["listas"]}
                          if cand else None),
        })
    return out


def anotacoes_orfas(con: sqlite3.Connection, fmt: str,
                    cfg: dict | None = None, cache: dict | None = None
                    ) -> list[dict]:
    """O mesmo que `versoes_derivadas(...)["orfas"]`, para quem só quer isto."""
    return versoes_derivadas(con, fmt, cfg, cache).get("orfas") or []


def outros_que_jogam(con: sqlite3.Connection, fmt: str,
                     cfg: dict | None = None,
                     min_listas: int = 1) -> list[dict]:
    """Os clusters que jogam a carta-chave e **não** são versões deste deck.

    Derivado da base a cada corrida. Cada um diz quantas listas tem, se passa o
    critério (`passa_criterio`) e porquê — para ele poder incluir um com um
    toque, que é exactamente o que a ordem pede (*"NAO decidas por ele incluir
    nem excluir definitivamente"*).

    **Vazio num formato de versões derivadas** (2026-10-05): ali não há
    «outros» — quem joga a carta-chave É uma versão, e era precisamente esta
    caixa que guardava os cinco arquétipos *«de fora, à espera de
    confirmação»* que ele respondeu. Fica inteira para o Pioneer, onde ele
    nomeou as três versões à mão.
    """
    carta, exige, pct_min = _criterio(fmt, cfg)
    if not carta or versoes_todas(fmt, cfg):
        return []
    # As SAÍDAS também não são «outros»: têm bloco próprio («meta, não
    # escolhido»), e aparecer nos dois lugares dava o mesmo deck duas vezes no
    # mesmo ecrã — foi o que a caixa dos «outros» fez ao Grinding Station a
    # 05/10, e por isso ela desaparecia nos formatos derivados.
    ja = {v.get("arquetipo_id")
          for v in versoes(fmt, cfg) + versoes_saidas(fmt, cfg)
          if v.get("arquetipo_id") is not None}
    # UM CLUSTER QUE JÁ É UMA VERSÃO NÃO É UM «OUTRO» (2026-10-06). Com as
    # versões ancoradas em CARTAS e não em `archetype_id`, a Affinity dele —
    # 53 listas — aparecia ao mesmo tempo como versão 1 e como «outro deck que
    # joga Mox Opal», no mesmo ecrã. Quem decide é a MAIORIA das listas do
    # cluster: um cluster cuja maior parte das listas cai no universo de uma
    # versão É essa versão. A maioria e não «uma lista basta», senão um deck
    # diferente que partilhasse uma lista desaparecia da caixa dos outros, que
    # é precisamente a caixa onde ele decide incluí-lo.
    das_versoes = _ids_das_versoes(con, fmt, cfg)
    sql, par = sources.counting_sql(fmt, "d", consenso=False)
    rows = con.execute(
        f"""SELECT d.archetype_id aid, COUNT(DISTINCT d.id) n
              FROM decklists d
             WHERE d.format = ? AND {sql}
               AND EXISTS (SELECT 1 FROM decklist_cards c
                            WHERE c.decklist_id = d.id
                              AND {scryfall.sql_nome('c.card_name')})
             GROUP BY d.archetype_id""",
        [fmt] + list(par) + list(scryfall.params_nome(carta))).fetchall()
    out = []
    sem_cluster = 0
    ja_versao = 0
    cache_nomes: dict = {}
    for r in rows:
        aid = r["aid"]
        if aid is None:
            sem_cluster += r["n"]
            continue
        if aid in ja or r["n"] < min_listas:
            continue
        if das_versoes and _e_de_uma_versao(con, fmt, aid, das_versoes):
            ja_versao += 1
            continue
        pcts = {c: _pct_no_cluster(con, aid, c) for c in exige}
        passa = bool(exige) and all(p >= pct_min for p in pcts.values())
        lab = con.execute("SELECT label FROM archetypes WHERE id=?",
                          [aid]).fetchone()
        # O NOME sai do `mtgvault.nomes`, que é o ÚNICO leitor do
        # `decklists.arquetipo_fonte` (há teste que varre o código à procura de
        # um segundo). A etiqueta do clustering fica ao lado, porque metade
        # destes clusters não tem nome da fonte nenhum.
        rot = _nomes.nome_do_cluster(con, aid, fmt, cache=cache_nomes)
        out.append({
            "arquetipo_id": aid, "listas": r["n"],
            "label": (lab["label"] if lab else "") or "",
            "nome": (rot or {}).get("nome") or "",
            "passa_criterio": passa,
            "exige": [{"carta": c, "pct": round(p, 1)} for c, p in pcts.items()],
        })
    out.sort(key=lambda d: (not d["passa_criterio"], -d["listas"], d["label"]))
    if sem_cluster:
        out.append({"arquetipo_id": None, "listas": sem_cluster, "label": "",
                    "passa_criterio": False, "exige": [], "sem_cluster": True})
    if ja_versao:
        out.append({"arquetipo_id": None, "listas": 0, "label": "",
                    "passa_criterio": False, "exige": [],
                    "ja_e_versao": ja_versao})
    return out


def _ids_das_versoes(con: sqlite3.Connection, fmt: str,
                     cfg: dict | None = None) -> set[int]:
    """Os ids de decklist que caem no universo (por CARTAS) de alguma versão."""
    desde = sources.consenso_desde()
    out: set[int] = set()
    for v in versoes(fmt, cfg):
        cs = cartas_do_meta(v)
        if cs:
            out |= {int(r["id"]) for r in listas_do_meta(con, fmt, cs, desde)}
    return out


def _e_de_uma_versao(con: sqlite3.Connection, fmt: str, aid: int,
                     das_versoes: set[int]) -> bool:
    ids = [r["id"] for r in con.execute(
        "SELECT id FROM decklists WHERE format=? AND archetype_id=? "
        "AND event_date >= ?", [fmt, int(aid), sources.consenso_desde()])]
    if not ids:
        return False
    return sum(1 for i in ids if int(i) in das_versoes) * 2 >= len(ids)


# ---------------------------------------------------------------------------
# A PROTECÇÃO: os nomes dos decks que ficam
# ---------------------------------------------------------------------------
def _cards_do_registo(cfg: dict, chave: str) -> list:
    rec = (cfg.get("listas_escolhidas") or {}).get(chave) or {}
    return rec.get("cards") or []


def nomes_que_ficam(res: dict, cfg: dict | None = None) -> dict[str, set[str]]:
    """`nome da carta -> {decks que a jogam}`, sobre os decks que o modelo guarda.

    É a regra **RE** do `fases`: uma carta que está num deck que ele escolheu
    não vai à venda. Sem ela, *"quero apenas manter decks que usem Mox Opal"*
    não tinha mecanismo nenhum — os decks que não são caixa (as versões) não têm
    `copy_allocation` e por isso a RD nunca os via.

    Lê as caixas do `res` do `loadout` (que já está calculado) e as listas de
    evento do config. **Não chama o `decks_vista`**: este módulo é lido pelo
    motor da venda, e o registo da página custa os arquétipos meta todos.
    """
    cfg = sources.config() if cfg is None else cfg
    fica = ids_que_ficam(cfg)
    # Os formatos FORA do modelo continuam como estavam: as caixas deles
    # protegem pela RD/R5 de sempre, e não entram aqui.
    por_slot = {s["slot"]: s for s in (res.get("slots") or [])}
    out: dict[str, set[str]] = {}
    for did in sorted(fica):
        nms: set[str] = set()
        if did.startswith("caixa:"):
            s = por_slot.get(did.split(":", 1)[1])
            if s:
                for l in list(s.get("have") or []) + list(s.get("missing") or []):
                    nms.add(scryfall.chave(l["nm"]))
        for _b, nm, _q in _cards_do_registo(cfg, did):
            nms.add(scryfall.chave(nm))
        for nm in nms:
            out.setdefault(nm, set()).add(did)
    return out


def nome_do_deck(deck_id: str, cfg: dict | None = None) -> str:
    """O nome por extenso de um deck que fica, para o motivo da protecção."""
    cfg = sources.config() if cfg is None else cfg
    for f in formatos(cfg):
        d = do_formato(f, cfg) or {}
        for v in versoes(f, cfg):
            if deck_da_versao(v) == deck_id:
                return f"{d.get('nome') or f} · {v.get('nome') or v.get('id')}"
    return deck_id


# ---------------------------------------------------------------------------
# A PROTECÇÃO INCLUSIVA: todas as listas que jogam a carta-chave
# ---------------------------------------------------------------------------
def limiar_listas(cfg: dict | None = None) -> int:
    """Em quantas listas da carta-chave uma carta tem de estar para proteger.

    **Nunca abaixo de 1**: zero protegia a colecção inteira (uma carta em zero
    listas passaria o teste), que é o contrário do que o limiar existe para
    fazer.
    """
    cfg = sources.config() if cfg is None else cfg
    b = cfg.get(CHAVE)
    v = b.get("_limiar_listas") if isinstance(b, dict) else None
    try:
        return max(1, int(v))
    except (TypeError, ValueError):
        return LIMIAR_LISTAS


def protege_todas(fmt: str, cfg: dict | None = None) -> bool:
    """O formato protege **todas** as listas da carta-chave, ou só as versões?

    *"Entram TODAS as listas que jogam Mox Opal, nao so as da Affinity"* — mas
    só onde ele o disse. O Pioneer tem carta-chave e fica de fora: ali ele
    nomeou as três versões, e alargá-lo por simetria era decidir por ele.
    """
    c = (do_formato(fmt, cfg) or {}).get("criterio") or {}
    return bool(c.get("protege_todas"))


def formatos_inclusivos(cfg: dict | None = None) -> list[str]:
    return [f for f in formatos(cfg)
            if protege_todas(f, cfg) and carta_chave(f, cfg)]


def listas_da_carta(con: sqlite3.Connection, fmt: str, carta: str,
                    desde: str | None = None) -> list[int]:
    """Os ids das listas do formato, **na janela**, que jogam a carta.

    **Sem o filtro de tier** (`sources.counting_sql`), e isso é deliberado: é a
    mesma excepção da R5, pela mesma razão — sub-contar numa regra de protecção
    é vender uma carta que ele precisa. Um 5-0 de league que jogue Mox Opal é
    exactamente o sinal que interessa aqui.
    """
    desde = desde or sources.consenso_desde()
    return [r["id"] for r in con.execute(
        f"""SELECT d.id FROM decklists d
             WHERE d.format = ? AND d.event_date >= ?
               AND EXISTS (SELECT 1 FROM decklist_cards k
                            WHERE k.decklist_id = d.id
                              AND {scryfall.sql_nome('k.card_name')})""",
        [fmt, desde] + list(scryfall.params_nome(carta)))]


def contagem_por_carta(con: sqlite3.Connection, cfg: dict | None = None,
                       cache: dict | None = None) -> dict[str, dict]:
    """`chave do nome -> {listas, formatos: {fmt: n}, cartas_chave: {fmt: carta}}`.

    Conta, para cada carta, em quantas das listas da carta-chave ela aparece.
    O total é a **SOMA** entre formatos e não o máximo: as 25 de Modern e as 23
    de Legacy são 48 listas de Mox Opal, e uma carta que esteja numa de cada
    está em duas delas. É a leitura literal de *"em quantas listas"*.

    Independente do limiar — é ele que corta, depois. Guardada na cache da
    passagem: o `contexto` corre uma vez por relatório, mas a página pede-lhe a
    curva para vários limiares e seria a mesma consulta três vezes.
    """
    cache = {} if cache is None else cache
    if "_rp_conta" in cache:
        return cache["_rp_conta"]
    cfg = sources.config() if cfg is None else cfg
    out: dict[str, dict] = {}
    for fmt in formatos_inclusivos(cfg):
        carta = carta_chave(fmt, cfg)
        ids = listas_da_carta(con, fmt, carta)
        if not ids:
            continue
        ph = ",".join("?" * len(ids))
        for r in con.execute(
                f"""SELECT card_name nm, COUNT(DISTINCT decklist_id) n
                      FROM decklist_cards WHERE decklist_id IN ({ph})
                     GROUP BY card_name""", ids):
            d = out.setdefault(scryfall.chave(r["nm"]),
                               {"listas": 0, "formatos": {}, "cartas_chave": {}})
            d["listas"] += r["n"]
            d["formatos"][fmt] = d["formatos"].get(fmt, 0) + r["n"]
            d["cartas_chave"][fmt] = carta
    cache["_rp_conta"] = out
    return out


def nomes_protegidos(con: sqlite3.Connection, cfg: dict | None = None,
                     limiar: int | None = None,
                     cache: dict | None = None) -> dict[str, dict]:
    """O conjunto da **RP**: as cartas que não vão à venda por se jogarem num
    deck da carta-chave.

    Vazio quando nenhum formato é inclusivo — e é assim que isto se desliga,
    como o `venda.mostrar` e o `cartas_vigiadas`.
    """
    cfg = sources.config() if cfg is None else cfg
    lim = limiar_listas(cfg) if limiar is None else max(1, int(limiar))
    return {k: v for k, v in contagem_por_carta(con, cfg, cache).items()
            if v["listas"] >= lim}


def texto_rp(info: dict) -> str:
    """O motivo em português de uma cópia apanhada pela RP."""
    fs = info.get("formatos") or {}
    cartas = sorted({c for c in (info.get("cartas_chave") or {}).values()})
    onde = ", ".join(f"{f} {n}" for f, n in sorted(fs.items()))
    n = info.get("listas") or 0
    return (f"joga-se em {n} lista{'' if n == 1 else 's'} de "
            f"{' / '.join(cartas) or 'deck que guardas'} ({onde}) — "
            f"é uma carta que não queres vender")


def listas_do_formato(con: sqlite3.Connection, cfg: dict | None = None
                      ) -> dict[str, dict]:
    """Quantas listas da carta-chave há por formato, e de quantas no total.

    Para a página poder dizer *«23 de 171 listas de Legacy, 13,5 %»* sem
    recontar — e para a conta ficar conferível contra o site.

    **E, desde 2026-10-05, a MESMA conta SEM as ligas ao lado** (`sem_ligas`,
    mais `ligas` com a fatia delas). É a decisão da secção «AS LIGAS CONTAM-SE À
    PARTE» do `sources`: uma liga é um 5-0 sem classificação e sem tamanho de
    campo, e somada a uma Challenge faz a percentagem do formato medir duas
    coisas ao mesmo tempo. As duas contas vão sempre as duas, nunca uma —
    esconder a de baixo deixava-o a olhar para um número que pode ter subido só
    porque a fonte mudou. Num formato que não conte ligas as duas são **iguais**
    (não há nenhuma para tirar), e é isso que faz isto não mudar nada no Legacy.
    """
    cfg = sources.config() if cfg is None else cfg
    desde = sources.consenso_desde()
    sem_liga, par_liga = sources.sql_sem_ligas("d")
    out: dict[str, dict] = {}
    for fmt in formatos_inclusivos(cfg):
        carta = carta_chave(fmt, cfg)
        n = len(listas_da_carta(con, fmt, carta, desde))
        tot = con.execute(
            "SELECT COUNT(*) c FROM decklists d WHERE d.format = ? "
            "AND d.event_date >= ?", [fmt, desde]).fetchone()["c"]
        n_sem = con.execute(
            f"""SELECT COUNT(*) c FROM decklists d
                 WHERE d.format = ? AND d.event_date >= ? AND {sem_liga}
                   AND EXISTS (SELECT 1 FROM decklist_cards k
                                WHERE k.decklist_id = d.id
                                  AND {scryfall.sql_nome('k.card_name')})""",
            [fmt, desde] + list(par_liga)
            + list(scryfall.params_nome(carta))).fetchone()["c"]
        tot_sem = con.execute(
            f"""SELECT COUNT(*) c FROM decklists d
                 WHERE d.format = ? AND d.event_date >= ? AND {sem_liga}""",
            [fmt, desde] + list(par_liga)).fetchone()["c"]

        def _p(a, b):
            return round(100.0 * a / b, 1) if b else 0.0

        out[fmt] = {
            "carta": carta, "listas": n, "total": tot, "pct": _p(n, tot),
            "desde": desde,
            # Esta é a conta de ANTES de as ligas entrarem: é com ela que se
            # compara, e é ela que diz se o número andou por mérito do deck.
            "sem_ligas": {"listas": n_sem, "total": tot_sem,
                          "pct": _p(n_sem, tot_sem)},
            "ligas": {"listas": n - n_sem, "total": tot - tot_sem,
                      "pct": _p(n - n_sem, tot - tot_sem),
                      # `conta` é o interruptor do config, não «há ligas na
                      # base»: um formato pode ter ligas antigas por apagar.
                      "conta": sources.conta_ligas(fmt)},
        }
    return out


# ---------------------------------------------------------------------------
# A RETENÇÃO pelos formatos por decidir
# ---------------------------------------------------------------------------
def corte_pct(cfg: dict | None = None) -> float:
    cfg = sources.config() if cfg is None else cfg
    v = (cfg.get(CHAVE) or {}).get("_corte_pct") if isinstance(cfg.get(CHAVE), dict) else None
    try:
        return float(v)
    except (TypeError, ValueError):
        return CORTE_PCT


def pct_por_formato(con: sqlite3.Connection, fmt: str,
                    nms) -> tuple[dict[str, float], int]:
    """`nome -> % das listas da JANELA deste formato que a jogam`, e o total.

    A janela do consenso e não a história toda: a pergunta é *"isto joga-se no
    formato HOJE"*, que é a mesma pergunta do resto do site desde 2026-10-03.
    """
    sql, par = sources.counting_sql(fmt, "d")
    tot = con.execute(
        f"SELECT COUNT(*) c FROM decklists d WHERE d.format = ? AND {sql}",
        [fmt] + list(par)).fetchone()["c"]
    out: dict[str, float] = {}
    if not tot:
        return out, 0
    for nm in sorted(set(nms)):
        n = con.execute(
            f"""SELECT COUNT(DISTINCT d.id) c FROM decklists d
                  JOIN decklist_cards k ON k.decklist_id = d.id
                 WHERE d.format = ? AND {sql} AND {scryfall.sql_nome('k.card_name')}""",
            [fmt] + list(par) + list(scryfall.params_nome(nm))).fetchone()["c"]
        if n:
            out[nm] = 100.0 * n / tot
    return out, tot


def retidos(con: sqlite3.Connection, nms, cfg: dict | None = None
            ) -> dict[str, tuple[str, float]]:
    """`nome -> (formato, pct)` do que fica retido por um formato POR DECIDIR.

    Vazio quando não há formato nenhum por decidir — e é assim que esta regra se
    desliga sozinha no dia em que ele escolher o deck de Legacy, sem ninguém
    mexer no código.
    """
    cfg = sources.config() if cfg is None else cfg
    corte = corte_pct(cfg)
    out: dict[str, tuple[str, float]] = {}
    for fmt in formatos_por_decidir(cfg):
        pcts, _tot = pct_por_formato(con, fmt, nms)
        for nm, p in pcts.items():
            if p >= corte and p > out.get(nm, ("", 0.0))[1]:
                out[nm] = (fmt, p)
    return out
