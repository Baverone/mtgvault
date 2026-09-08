"""Premodern: o que montar a seguir com o que SOBRA, e o que vender.

Ordem do André (2026-09-08, à letra):

    *"O que não estiver a ser usado em Premodern e se encaixe na regra do
    Premodern deve ser sugerido para venda. Antes disso, procura decklists do
    formato; se o deck for top-10 de representação ou top-5 decks combo do
    formato, sugere a lista para montar o deck caso eu tenha pelo menos 50 % das
    cartas (sem contar com as básicas para a %); se não, envia para vender."*

Três perguntas, por esta ordem — e a ordem é o que faz a resposta ser honesta:

  1. **o que é que o formato joga?** Os arquétipos mais representados nas listas
     que CONTAM (`sources.counting_sql`, a mesma regra do resto do vault) e, à
     parte, os que são **combo**;
  2. **do que sobra, quanto é que ele já tem?** A cobertura de cada candidato
     mede-se sobre as cópias que a alocação NÃO deu a nenhuma caixa — nem às seis
     de Premodern nem a uma que ele já tenha escolhido. Medi-la sobre a colecção
     inteira dava percentagens altas e falsas: as cartas estão dentro de decks
     montados, e uma sugestão que conta com elas está a mandá-lo desmontar um
     deck para montar outro;
  3. **e o resto?** Uma cópia PT da era Premodern que nenhuma caixa usa não serve
     mais nada — a regra 1 do André tranca-a ao Premodern (*"essas cartas NÃO
     entram para outros formatos!!"*). Se também não está reservada para uma
     sugestão, é peso morto e vai para a venda, com um motivo próprio.

O QUE É "COBERTURA COM O QUE SOBRA"
-----------------------------------
`loadout.foil_report(..., res=...)` já responde a isto para os outros formatos: o
`pct_livre` é a percentagem de cartas não-básicas que ele tem **livres** depois
da alocação toda. Aqui é a mesma função e o mesmo número — não se escreve um
segundo cálculo de posse, que é o defeito que este vault já pagou caro no
`event_tier` e no filtro de listas.

Consequência a assumir, e é grande: com seis caixas de Premodern a alocar
primeiro, sobra pouco. Uma sugestão a 40 % não é uma sugestão má — é a verdade
sobre o que resta na gaveta depois de os decks dele estarem servidos.

O QUE CONTA COMO COMBO
----------------------
A fonte não nos dá o rótulo: o mtgtop8 exporta `.dec` de cartas, não nomes de
arquétipo, e o clustering gera rótulos a partir das cartas distintivas. Por isso
o combo decide-se por REGRA sobre a lista de consenso — as mesmas três chaves do
`archetype_rules.json` (`all`, `any`, `none`) e o mesmo motor
(`tagging._matches`), em `colecao_config.json → premodern.combo_arquetipos`. A
lista de omissão saiu do relatório `work/revisao/premodern-combo.md`, que
classificou os arquétipos do formato sobre 441 listas reais, com o critério
escrito: *um deck é combo quando o plano de vitória depende de uma interacção
concreta entre cartas*.

A ordem das regras é a prioridade (a primeira que bate ganha), e não é
decoração: o Full English Breakfast joga Survival of the Fittest e, escrito
depois do Elves/Survival, chamava-se Elves/Survival.

As regras servem também de NOME. O `meta_coverage._name_for` chamava
*"Replenish"* aos dois — à Enchantress (que joga 96 % de Replenish) e ao UW
Replenish — porque a `KNOWN` bate na primeira carta que encontra. A regra com
`none` separa-os, que é exactamente o que o `archetype_rules.json` já faz para os
alvos de consenso.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date

from . import loadout, sources, tagging

FMT = "premodern"

# Os valores de omissão. Vivem aqui e no `colecao_config.json → premodern`, como
# as `regras_por_formato`: o config manda, o código continua a correr sem ele.
TOP_REPRESENTADOS = 10          # "top-10 de representação"
TOP_COMBO = 5                   # "top-5 decks combo"
SUGERIR_A_PARTIR_DE = 50        # "caso eu tenha pelo menos 50 % das cartas"
MIN_LISTAS = 5                  # o mesmo mínimo do `analysis.rebuild_roles`

# O motivo da venda nova. É uma constante porque a página, o CLI e o teste têm de
# a reconhecer — e porque é a chave por que ela se separa do "excedente (mais de
# 4)": são duas decisões diferentes sobre a mesma cópia.
RAZAO_VENDA = "Premodern: não usada por nenhum deck"

# COMBO EM PREMODERN — critério e lista, do relatório de 2026-09-07
# (`work/revisao/premodern-combo.md`, 441 listas). Graus:
#   `puro`    a interacção mata no turno em que resolve (Dreadnought + Stifle);
#   `prisao`  não mata: tranca o jogo e mata depois (Confinement + Enchantress);
#   `hibrido` tem plano de combo E um plano autónomo que ganha sozinho.
# A ORDEM é a prioridade: a primeira regra que bate dá o nome e o grau.
COMBO_DEFAULT = [
    {"nome": "Full English Breakfast", "grau": "puro",
     "all": ["Volrath's Shapeshifter"]},
    {"nome": "UW Replenish", "grau": "puro", "all": ["Replenish", "Opalescence"],
     "none": ["Argothian Enchantress", "Enchantress's Presence"]},
    {"nome": "Enchantress", "grau": "prisao",
     "any": ["Argothian Enchantress", "Enchantress's Presence"]},
    {"nome": "Stiflenought", "grau": "puro", "all": ["Phyrexian Dreadnought"]},
    {"nome": "Ill-Gotten Gains", "grau": "puro", "all": ["Ill-Gotten Gains"]},
    {"nome": "Oath of Druids", "grau": "puro", "all": ["Oath of Druids"]},
    {"nome": "Stasis", "grau": "prisao", "all": ["Stasis"]},
    {"nome": "Dream Halls", "grau": "puro", "all": ["Dream Halls"]},
    {"nome": "Aluren", "grau": "puro", "all": ["Aluren"]},
    {"nome": "Doomsday", "grau": "puro", "all": ["Doomsday"]},
    {"nome": "Academy Rector", "grau": "puro", "all": ["Academy Rector"]},
    {"nome": "Life / Test of Endurance", "grau": "puro",
     "any": ["Test of Endurance"]},
    {"nome": "Tinker / Academy", "grau": "puro",
     "any": ["Tinker", "Tolarian Academy"]},
    {"nome": "Reanimator", "grau": "puro", "any": ["Exhume", "Reanimate"]},
    {"nome": "Terrageddon", "grau": "hibrido", "all": ["Terravore", "Armageddon"]},
    {"nome": "Elves / Survival", "grau": "hibrido",
     "all": ["Survival of the Fittest"]},
]
GRAUS = {"puro": "combo puro", "prisao": "combo-prisão", "hibrido": "híbrido"}


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
def config() -> dict:
    v = sources.config().get("premodern")
    return v if isinstance(v, dict) else {}


def _num(chave: str, omissao: int) -> int:
    try:
        v = config().get(chave)
        return omissao if v is None else int(v)
    except (TypeError, ValueError):
        return omissao


def top_representados() -> int:
    return max(0, _num("top_representados", TOP_REPRESENTADOS))


def top_combo() -> int:
    return max(0, _num("top_combo", TOP_COMBO))


def limiar() -> int:
    """A partir de que percentagem uma lista deixa de ser um candidato e passa a
    ser uma SUGESTÃO. *"Caso eu tenha pelo menos 50 % das cartas."*"""
    return max(0, min(100, _num("sugerir_a_partir_de_pct", SUGERIR_A_PARTIR_DE)))


def min_listas() -> int:
    return max(1, _num("min_listas", MIN_LISTAS))


def combo_regras() -> list[dict]:
    v = config().get("combo_arquetipos")
    if not isinstance(v, list) or not v:
        return COMBO_DEFAULT
    return [{k: r[k] for k in r if not str(k).startswith("_")} for r in v]


def recusadas() -> dict[str, str]:
    """As sugestões que ele já disse que não quer, e o dia em que o disse.

    Uma recusa não é o mesmo que "não passa dos 50 %": as cartas dela **libertam-
    se para a venda** (é o que o botão *"não quero este"* existe para fazer), e
    por isso tem de ficar escrita e datada em vez de se perder no browser.
    """
    v = config().get("sugestoes_recusadas")
    return {str(k): str(x) for k, x in v.items()} if isinstance(v, dict) else {}


# ---------------------------------------------------------------------------
# Nomes e combo
# ---------------------------------------------------------------------------
def chave_nome(nome: str) -> str:
    """Um nome de arquétipo reduzido ao que se pode comparar.

    É por aqui que uma sugestão se reconhece como sendo já uma caixa: a caixa
    chama-se *"Elves / Survival"* e a lista da tabela `decks` chama-se
    *"Enchantress (consenso)"*. Sem normalizar, o vault propunha-lhe montar um
    deck que já está na estante.
    """
    s = unicodedata.normalize("NFKD", (nome or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\((consenso|luffy|primer|cedh)\)", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def slug(nome: str) -> str:
    """O id de uma caixa nova criada a partir de uma sugestão."""
    s = unicodedata.normalize("NFKD", (nome or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "premodern-" + (re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "sugestao")


def classificar(cartas: set[str], regras: list[dict] | None = None
                ) -> tuple[str | None, str | None]:
    """(nome, grau) da primeira regra de combo que bate na lista. (None, None) se
    não for combo — e não ser combo não tira ninguém do top-10."""
    for r in (regras if regras is not None else combo_regras()):
        if tagging._matches(cartas, r):
            return r.get("nome"), r.get("grau")
    return None, None


def _nome_do_cluster(con, aid: int, cache: dict) -> str:
    """O nome legível de um arquétipo que não bate em regra de combo nenhuma.

    Importa-se o `meta_coverage` aqui dentro, e não no topo: ele é um script da
    raiz e este é um módulo do pacote — num contexto onde a raiz não esteja no
    `sys.path` o import falharia à carga e levava consigo o `loadout.report`
    inteiro. Sem ele, o rótulo do clustering serve: é feio, mas é verdade.
    """
    try:
        import meta_coverage as mc                       # noqa: PLC0415
    except ImportError:                                  # pragma: no cover
        return ""
    if "df" not in cache:
        cache["df"] = mc._format_df(con, FMT)
        cache["t"] = {}
    return mc._name_for(con, aid, cache["df"], cache["t"])


def _subtitulo(con, aid: int, cache: dict) -> str:
    try:
        import meta_coverage as mc                       # noqa: PLC0415
    except ImportError:                                  # pragma: no cover
        return ""
    if "df" not in cache:
        cache["df"] = mc._format_df(con, FMT)
        cache["t"] = {}
    return mc._distinctive_name(con, aid, cache["df"], cache["t"])


# ---------------------------------------------------------------------------
# Candidatos
# ---------------------------------------------------------------------------
def caixas_do_formato(res: dict) -> list[dict]:
    return [s for s in res["slots"] if s.get("formato") == FMT]


def _caixa_de(cand: dict, caixas: list[dict]) -> dict | None:
    """A caixa que já É este arquétipo, se existir.

    Duas maneiras, e as duas são precisas: pelo `archetype_id` (é o que fica
    escrito quando ele carrega em *"vou montar este"*) e pelo NOME normalizado
    (as seis caixas de hoje vieram do config à mão e não têm arquétipo nenhum
    associado). Uma regra de combo pode ainda apontar a caixa à mão (`caixa`),
    para o dia em que ele lhe mudar o nome.
    """
    alvo = chave_nome(cand["nome"])
    for s in caixas:
        if cand.get("archetype_id") and s.get("archetype_id") == cand["archetype_id"]:
            return s
        if cand.get("caixa") and s.get("slot") == cand["caixa"]:
            return s
        for k in (s.get("nome"), s.get("ref"), s.get("slot")):
            if k and chave_nome(k) == alvo:
                return s
    return None


def candidatos(con: sqlite3.Connection, res: dict) -> list[dict]:
    """Os arquétipos de Premodern a considerar, com a cobertura do que SOBRA.

    Devolve TODOS os que passam o mínimo de listas, já ordenados por
    representação; quem corta o top-10 / top-5 combo é o `ranking`. Cada entrada:

      `nome`/`subtitulo`  o nome da regra de combo, ou o do clustering;
      `combo`/`grau`      se é combo e de que tipo;
      `n_lists`           listas que CONTAM (`sources.counting_sql`);
      `pct`               a cobertura com o que sobra (sem básicas) — é esta que
                          decide a sugestão;
      `pct_total`         a cobertura contando também as cópias que estão dentro
                          de outra caixa. Não decide nada: está aqui para ele ver
                          *porque* é que a primeira é baixa;
      `estado`            caixa | sugerida | recusada | abaixo.
    """
    regras = combo_regras()
    caixas = caixas_do_formato(res)
    fora = recusadas()
    corte = limiar()
    cache: dict = {}
    por_combo: dict[str, dict] = {}
    out: list[dict] = []
    for r in loadout.foil_report(con, FMT, top=10 ** 6,
                                 min_lists=min_listas(), res=res):
        cartas = {m["nm"] for m in r["linhas"]}
        nome, grau = classificar(cartas, regras)
        # Duas entradas com o MESMO nome de combo são o mesmo baralho partido em
        # dois clusters (o Stasis aparece duas vezes na base de 2026-09-08): somam
        # as listas em vez de ocuparem dois lugares do top-5. Só se juntam pelo
        # nome de uma REGRA — juntar pelo nome gerado pelo clustering fundia dois
        # decks diferentes só porque a heurística lhes chamou o mesmo.
        if nome and nome in por_combo:
            velho = por_combo[nome]
            velho["n_lists"] += r["n_lists"]
            velho["ids"] += r["ids"]
            continue
        c = {
            "archetype_id": r["archetype_id"], "ids": list(r["ids"]),
            "nome": nome or _nome_do_cluster(con, r["archetype_id"], cache)
                    or r["label"],
            "subtitulo": _subtitulo(con, r["archetype_id"], cache) or r["label"],
            "combo": bool(nome), "grau": GRAUS.get(grau or "", ""),
            "n_lists": r["n_lists"], "linhas": r["linhas"],
            "need": r["need"], "got": r["got"],
            "pct": r["pct_livre"], "pct_total": r["pct"],
            "comprar": r["comprar"], "custo": r["custo"],
        }
        if nome:
            por_combo[nome] = c
        out.append(c)
    for c in out:
        caixa = _caixa_de(c, caixas)
        c["slot"] = (caixa or {}).get("slot")
        c["caixa_nome"] = (caixa or {}).get("nome")
        c["recusada_em"] = fora.get(c["nome"])
        c["estado"] = ("caixa" if caixa else
                       "recusada" if c["recusada_em"] else
                       "sugerida" if c["pct"] >= corte else "abaixo")
    out.sort(key=lambda c: (-c["n_lists"], c["nome"]))
    return out


def ranking(con: sqlite3.Connection, res: dict,
            cands: list[dict] | None = None) -> dict:
    """O top-10 de representação e o top-5 de combo, com a marca de cada um.

    São duas listas e não uma soma: *"se o deck for top-10 de representação **ou**
    top-5 decks combo"*. Um deck pode estar nas duas (o Enchantress está), e a
    marca `top`/`top_combo` diz em qual — misturá-las escondia o critério por que
    cada um entrou.
    """
    cands = cands if cands is not None else candidatos(con, res)
    top = cands[:top_representados()]
    combo = [c for c in cands if c["combo"]][:top_combo()]
    ids_top, ids_combo = {id(c) for c in top}, {id(c) for c in combo}
    for c in cands:
        c["top"] = id(c) in ids_top
        c["top_combo"] = id(c) in ids_combo
        c["elegivel"] = c["top"] or c["top_combo"]
    return {"todos": cands, "top": top, "combo": combo,
            "elegiveis": [c for c in cands if c["elegivel"]]}


# ---------------------------------------------------------------------------
# Sugestões e reservas
# ---------------------------------------------------------------------------
def sugestoes(rank: dict) -> list[dict]:
    """Os candidatos elegíveis que passam o limiar e ainda não são caixa."""
    return [c for c in rank["elegiveis"] if c["estado"] == "sugerida"]


def reservas(sugs: list[dict]) -> dict[str, int]:
    """`carta -> cópias a NÃO vender`, por causa das sugestões abertas.

    É o **máximo** entre as sugestões e não a soma, pela mesma razão que as
    compras se partilham (`loadout.partilhar_compras`): as sugestões são
    alternativas entre si, e o Premodern tem tecto de playset — guardar 4 Swords
    por cada sugestão dava 16 cópias reservadas de uma carta que nunca chega a
    ter mais do que 4.

    Reserva-se o que a lista PEDE, e não o que ainda lhe falta: as cópias que a
    sugestão já "tem" são exactamente as cópias livres que se estavam a pensar
    vender. Descontá-las aqui era mandar vender a metade do deck que ele tem.
    """
    tecto = None
    for r in loadout.regras_por_formato():
        if FMT in (r.get("formatos") or []):
            tecto = r.get("playset_maximo")
    out: dict[str, int] = {}
    for c in sugs:
        for m in c["linhas"]:
            if m.get("basica"):
                continue
            q = m["need"]
            if tecto:
                q = min(q, int(tecto))
            if q > out.get(m["nm"], 0):
                out[m["nm"]] = q
    return out


def quem_reserva(sugs: list[dict], nm: str) -> str:
    """A sugestão que segura esta carta, para a linha dizer *porquê*."""
    quem = [c["nome"] for c in sugs
            if any(m["nm"] == nm and not m.get("basica") for m in c["linhas"])]
    return ", ".join(sorted(quem))


def contexto(con: sqlite3.Connection, res: dict) -> dict:
    """Tudo o que o Premodern acrescenta ao relatório do loadout.

    Corre DEPOIS do `allocate` (precisa de saber o que sobrou) e ANTES do
    `sell_list` (que precisa de saber o que fica reservado). É essa ordem que faz
    a cobertura e a venda concordarem: as duas olham para as mesmas cópias
    livres, uma para dizer *"tens 41 %"* e a outra para dizer *"o resto vende-se"*.
    """
    if not caixas_do_formato(res):
        # Sem uma única caixa de Premodern, *"não usada por nenhum deck"* não
        # quer dizer nada — e a regra da venda mandava embora a colecção inteira
        # de Premodern por não haver deck nenhum configurado. Ver `sell_list`.
        return {"activo": False, "todos": [], "top": [], "combo": [],
                "elegiveis": [], "sugestoes": [], "reservas": {},
                "recusadas": recusadas(), "limiar": limiar()}
    rank = ranking(con, res)
    sugs = sugestoes(rank)
    return {"activo": True, **rank, "sugestoes": sugs,
            "reservas": reservas(sugs), "recusadas": recusadas(),
            "limiar": limiar()}


# ---------------------------------------------------------------------------
# Escrita no config (o modo edição)
# ---------------------------------------------------------------------------
def recusar(cfg: dict, nome: str, quando: str | None = None) -> str:
    """*"Não quero este"*: a sugestão sai, e as cartas dela vão para a venda."""
    bloco = cfg.setdefault("premodern", {})
    bloco.setdefault("sugestoes_recusadas", {})[nome] = (
        quando or date.today().isoformat())
    return f"{nome}: sugestão recusada — as cartas dela libertam-se para a venda"


def aceitar(cfg: dict, nome: str) -> str:
    """Desfaz o *"não quero este"*."""
    bloco = cfg.get("premodern") or {}
    fora = bloco.get("sugestoes_recusadas") or {}
    if nome not in fora:
        return f"{nome} não estava recusado"
    fora.pop(nome)
    if not fora:
        bloco.pop("sugestoes_recusadas", None)
    return f"{nome}: volta a ser sugestão"
