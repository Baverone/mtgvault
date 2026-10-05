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

from . import nomes as _nomes
from . import scryfall, sources

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


def versoes(fmt: str, cfg: dict | None = None) -> list[dict]:
    d = do_formato(fmt, cfg) or {}
    v = d.get("versoes")
    return [x for x in (v if isinstance(v, list) else []) if isinstance(x, dict)]


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


def escolher(cfg: dict, fmt: str, vid: str, hoje: str | None = None) -> dict:
    """Grava a versão escolhida. Devolve o `cfg` (que é alterado no sítio).

    **Trocar para a que já lá está é um no-op** e não reescreve a data: um
    clique sem efeito não pode parecer uma decisão nova no histórico, que é a
    mesma regra do `precos.gravar_fonte` e do `fases.gravar_congelada`.
    """
    fmt = (fmt or "").lower()
    d = (cfg.get(CHAVE) or {}).get(fmt)
    if not isinstance(d, dict):
        raise VersaoDesconhecida(f"o formato {fmt} não tem deck único neste modelo")
    if not any(v.get("id") == vid for v in versoes(fmt, cfg)):
        tem = ", ".join(str(v.get("id")) for v in versoes(fmt, cfg)) or "nenhuma"
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
    return [deck_da_versao(v) for v in versoes(fmt, cfg) if deck_da_versao(v)]


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


def outros_que_jogam(con: sqlite3.Connection, fmt: str,
                     cfg: dict | None = None,
                     min_listas: int = 1) -> list[dict]:
    """Os clusters que jogam a carta-chave e **não** são versões deste deck.

    Derivado da base a cada corrida. Cada um diz quantas listas tem, se passa o
    critério (`passa_criterio`) e porquê — para ele poder incluir um com um
    toque, que é exactamente o que a ordem pede (*"NAO decidas por ele incluir
    nem excluir definitivamente"*).
    """
    carta, exige, pct_min = _criterio(fmt, cfg)
    if not carta:
        return []
    ja = {v.get("arquetipo_id") for v in versoes(fmt, cfg)
          if v.get("arquetipo_id") is not None}
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
    cache_nomes: dict = {}
    for r in rows:
        aid = r["aid"]
        if aid is None:
            sem_cluster += r["n"]
            continue
        if aid in ja or r["n"] < min_listas:
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
    return out


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
    """
    cfg = sources.config() if cfg is None else cfg
    desde = sources.consenso_desde()
    out: dict[str, dict] = {}
    for fmt in formatos_inclusivos(cfg):
        carta = carta_chave(fmt, cfg)
        n = len(listas_da_carta(con, fmt, carta, desde))
        tot = con.execute(
            "SELECT COUNT(*) c FROM decklists WHERE format = ? AND event_date >= ?",
            [fmt, desde]).fetchone()["c"]
        out[fmt] = {"carta": carta, "listas": n, "total": tot,
                    "pct": round(100.0 * n / tot, 1) if tot else 0.0,
                    "desde": desde}
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
