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
  2. **e se este deck escolhesse primeiro, quanto é que ele já tem?** A cobertura
     de cada candidato mede-se como se ele fosse a caixa nº 1 do grupo de
     Premodern — as cópias livres MAIS as que estão nas outras caixas do grupo,
     que lhas emprestam. Não conta as que estão dentro de caixas de outros
     formatos: essas são dedicadas, não emprestam, e montar com elas era
     desmontar um deck para montar outro;
  3. **e o resto?** Uma cópia PT da era Premodern que nenhuma caixa usa não serve
     mais nada — a regra 1 do André tranca-a ao Premodern (*"essas cartas NÃO
     entram para outros formatos!!"*). Se também não está reservada para uma
     sugestão, é peso morto e vai para a venda, com um motivo próprio.

DUAS COBERTURAS, E QUAL DELAS DECIDE (André, 2026-09-08)
-------------------------------------------------------
*"Como as cartas em Premodern são partilhadas, tens que ver se a % desses decks
aumentaria se eles fossem o principal; mantém a 50 % visto com esta regra de
agora."*

A primeira versão media a cobertura só sobre o que SOBRA — as cópias que a
alocação não deu a nenhuma caixa (`loadout.foil_report`, `pct_livre`). Era a
leitura certa enquanto as caixas de Premodern eram dedicadas; deixou de o ser no
dia em que elas voltaram a partilhar (`regras_por_formato.premodern.dedicado =
false`). Com seis caixas a alocar primeiro, NENHUM candidato chegava aos 50 % —
o melhor ficava em 41 % —, e o que a percentagem media já não era "quanto deste
deck eu tenho" mas "quanto sobrou depois dos outros".

Por isso o limiar corre agora sobre `pct_principal`: as cópias livres MAIS as
que estão nas outras caixas do grupo, que lhas emprestariam se este deck fosse a
caixa nº 1. As duas percentagens continuam à vista nas páginas e no CLI —
*"81 % como principal · 36 % com o que sobra"* — porque a diferença entre elas é
a resposta a *"quantas cartas viriam emprestadas?"*, e essa é a pergunta seguinte.

Nem uma nem outra é um segundo cálculo de posse: as duas saem das mesmas linhas
do `foil_report` (`got`, `onde`), que é a alocação a sério. Escrever aqui uma
contagem própria era o defeito que este vault já pagou caro no `event_tier`.

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

E porque a regra nomeia, há regras que **só** nomeiam: `"combo": false` (o
Psychatog, o Landstill, os Goblins, o Sligh). Sem essa chave, acrescentar o
Landstill à lista para lhe dar um nome estável punha-o a disputar o top-5 de
combo com o Stiflenought — dar nome e dizer que é combo são duas coisas
diferentes. Uma regra pode ainda pedir `"cor": true`, e aí o nome leva as cores
do núcleo à frente (*"Orzhov Exalted Angel"*): é para os nomes que não implicam
a cor, e evita chamar Orzhov a um deck mono-branco.

E QUEM MUDA DE NOME NÃO MUDA DE IDENTIDADE
------------------------------------------
Quem não bate em regra nenhuma fica com o rótulo do clustering, e esse MUDA entre
corridas (o *"Dimir Psychatog"* passou a *"Dimir Polluted Delta"*). Como uma
sugestão, uma recusa e uma escolha se reconhecem pelo arquétipo, isso fazia a
recusa de ontem deixar de bater hoje. Por isso cada candidato traz um `id`
estável, derivado do núcleo de cartas e herdado quando o núcleo mexe pouco — ver
`mtgvault/arquetipos.py`. **O nome é apresentação; quem liga as decisões é o
`id`.**
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import date

from . import arquetipos, loadout, sources, tagging

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
    # ANTES DO STIFLENOUGHT (2026-10-16): as listas de Hermit Druid (o «Angry
    # Ghoul» da fonte) e as de Academy Rector («Great Combo») jogam também o
    # Dreadnought e caíam em Stiflenought — medido, 4 listas de Hermit Druid. O
    # Aluren sobe com o Rector porque as duas listas de Aluren que contam jogam
    # Academy Rector: com o Rector à frente passavam a chamar-se Rector.
    {"nome": "Angry Ghoul (Hermit Druid)", "grau": "puro", "all": ["Hermit Druid"]},
    {"nome": "Aluren", "grau": "puro", "all": ["Aluren"]},
    {"nome": "Academy Rector", "grau": "puro", "all": ["Academy Rector"]},
    {"nome": "Stiflenought", "grau": "puro", "all": ["Phyrexian Dreadnought"]},
    {"nome": "Ill-Gotten Gains", "grau": "puro", "all": ["Ill-Gotten Gains"]},
    # Terrageddon ANTES do Oath (2026-10-16): o deck dele passou a ser o shell
    # Terravore + Mox Diamond, e o ramo desse shell que joga Oath of Druids (13 das
    # 61 listas que contam) é Terrageddon. Era `Terravore + Armageddon`, escrito
    # depois do Oath — e um Terrageddon com Oath chamava-se Oath of Druids.
    {"nome": "Terrageddon", "grau": "hibrido", "all": ["Terravore", "Mox Diamond"]},
    {"nome": "Oath of Druids", "grau": "puro", "all": ["Oath of Druids"]},
    {"nome": "Stasis", "grau": "prisao", "all": ["Stasis"]},
    {"nome": "Dream Halls", "grau": "puro", "all": ["Dream Halls"]},
    # 2026-10-16: 8 listas de Frantic Search + Brain Freeze sem nome nenhum (a
    # fonte chama «Mono Blue Storm» a duas) e 2 de Balancing Act — combos que
    # nunca podiam entrar no top-5 por não terem regra. Vêm DEPOIS do Dream Halls,
    # que joga as mesmas duas cartas.
    {"nome": "Frantic Storm", "grau": "puro",
     "all": ["Frantic Search", "Brain Freeze"]},
    {"nome": "Balancing Tings", "grau": "prisao", "all": ["Balancing Act"]},
    {"nome": "Doomsday", "grau": "puro", "all": ["Doomsday"]},
    # O en-Kor Life joga Daru Spiritualist + Worthy Cause em vez do Test of
    # Endurance, e escapava à regra (2026-10-16).
    {"nome": "Life / Test of Endurance", "grau": "puro",
     "any": ["Test of Endurance", "Daru Spiritualist"]},
    {"nome": "Tinker / Academy", "grau": "puro",
     "any": ["Tinker", "Tolarian Academy"]},
    # SEM Psychatog (2026-10-16): um Psychatog com 1 Reanimate chamava-se
    # Reanimator. Pô-lo depois do Psychatog partia a regra de as regras que só
    # nomeiam virem no fim (test_arquetipos); o `none` dá o mesmo resultado.
    {"nome": "Reanimator", "grau": "puro", "any": ["Exhume", "Reanimate"],
     "none": ["Psychatog"]},
    {"nome": "Elves / Survival", "grau": "hibrido",
     "all": ["Survival of the Fittest"]},
    # SÓ PARA NOMEAR (`combo: false`) — os clássicos do formato que o ranking já
    # mostrou e que, sem regra, ficavam com o rótulo do clustering e trocavam de
    # nome de corrida para corrida. Não entram no top-5 de combo: dar nome e
    # dizer que é combo são duas decisões diferentes.
    # A ordem continua a mandar: o Pyrostatic Pillar joga Fireblast e, escrito
    # depois do Sligh, chamava-se Sligh.
    {"nome": "Psychatog", "combo": False, "all": ["Psychatog"]},
    {"nome": "Landstill", "combo": False,
     "all": ["Standstill", "Mishra's Factory"]},
    {"nome": "The Rack", "combo": False, "all": ["The Rack"]},
    {"nome": "Exalted Angel", "combo": False, "cor": True,
     "all": ["Exalted Angel"]},
    {"nome": "Graveborn Muse", "combo": False, "cor": True,
     "all": ["Graveborn Muse"]},
    {"nome": "Goblins", "combo": False,
     "any": ["Goblin Lackey", "Goblin Piledriver", "Goblin Warchief"]},
    {"nome": "Pyrostatic Pillar", "combo": False, "all": ["Pyrostatic Pillar"]},
    {"nome": "Sligh", "combo": False, "all": ["Fireblast"]},
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


def recusadas() -> dict[str, dict]:
    """As sugestões que ele já disse que não quer, e o dia em que o disse.

    Uma recusa não é o mesmo que "não passa dos 50 %": as cartas dela **libertam-
    se para a venda** (é o que o botão *"não quero este"* existe para fazer), e
    por isso tem de ficar escrita e datada em vez de se perder no browser.

    A CHAVE é o `id` estável do arquétipo (2026-09-08). Era o NOME, e o nome do
    clustering muda entre corridas: a recusa deixava de bater e a sugestão que
    ele já tinha mandado embora voltava sozinha, com as cartas dela a sair outra
    vez da lista de venda. A forma antiga — `{"<nome>": "<data>"}` — continua a
    ler-se aqui e a bater pelo nome, para uma recusa escrita antes disto não se
    perder; a `migrar_config` passa-a para a nova.
    """
    v = config().get("sugestoes_recusadas")
    out: dict[str, dict] = {}
    for k, x in (v.items() if isinstance(v, dict) else ()):
        if isinstance(x, dict):
            out[str(k)] = {"nome": str(x.get("nome") or k),
                           "em": str(x.get("em") or "")}
        else:
            out[str(k)] = {"nome": str(k), "em": str(x)}
    return out


def recusa_de(rec: dict[str, dict], ident: str | None, nome: str) -> str | None:
    """O dia em que ele recusou este arquétipo, ou `None`.

    Pelo `id` primeiro (é a chave a sério) e pelo NOME a seguir — o segundo
    caminho é o que faz uma recusa da forma antiga continuar a valer sem ter de
    correr migração nenhuma.
    """
    r = rec.get(ident or "")
    if r:
        return r["em"]
    alvo = chave_nome(nome)
    for k, v in rec.items():
        if alvo and chave_nome(v.get("nome") or k) == alvo:
            return v["em"]
    return None


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


def classificar_regra(cartas: set[str], regras: list[dict] | None = None
                      ) -> dict | None:
    """A primeira regra que bate na lista — a que a NOMEIA. `None` se nenhuma bate.

    Uma regra pode nomear sem dizer que o deck é combo (`"combo": false`): é como
    o Landstill e os Goblins ganham um nome estável sem passarem a disputar o
    top-5 de combo com o Stiflenought.
    """
    for r in (regras if regras is not None else combo_regras()):
        if tagging._matches(cartas, r):
            return r
    return None


def e_combo(regra: dict | None) -> bool:
    """Uma regra é de combo a menos que diga que não. O default é `True` porque
    todas as que existiam antes de 2026-09-08 eram de combo — mudá-lo tirava-as
    todas do top-5 de uma vez."""
    return bool(regra) and regra.get("combo", True)


def classificar(cartas: set[str], regras: list[dict] | None = None
                ) -> tuple[str | None, str | None]:
    """(nome, grau) da primeira regra de COMBO que bate na lista. (None, None) se
    não for combo — e não ser combo não tira ninguém do top-10."""
    r = classificar_regra(cartas, regras)
    return (r.get("nome"), r.get("grau")) if e_combo(r) else (None, None)


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


def _distintivas(con, aid: int, cache: dict) -> list[str]:
    """As cartas do núcleo por ordem de distintividade — a matéria-prima do `id`.

    Quem sabe medir distintividade é o `meta_coverage` (tem o `card_roles` à
    frente). Sem ele, cai-se para as cartas da própria lista de consenso: um
    núcleo pior, mas verdadeiro, e a herança por semelhança absorve a diferença.
    """
    try:
        import meta_coverage as mc                       # noqa: PLC0415
    except ImportError:                                  # pragma: no cover
        return []
    if "df" not in cache:
        cache["df"] = mc._format_df(con, FMT)
        cache["t"] = {}
    return mc._distinctivas(con, aid, cache["df"], cache["t"])


def _cores(con, aid: int) -> str:
    try:
        import meta_coverage as mc                       # noqa: PLC0415
    except ImportError:                                  # pragma: no cover
        return ""
    return mc._cores_do_nucleo(con, aid)


def nome_da_regra(con, aid: int, regra: dict) -> str:
    """O nome que a regra dá, com as cores à frente quando ela o pede.

    *"A cor entra só quando o nome próprio não a implica"*: um Psychatog é Dimir
    por definição e um Exalted Angel não diz cor nenhuma. Calcular a cor em vez
    de a escrever na regra evita chamar *"Orzhov"* a um Exalted Angel mono-branco.
    """
    nome = regra.get("nome") or ""
    if not regra.get("cor"):
        return nome
    return f"{_cores(con, aid)} {nome}".strip()


# ---------------------------------------------------------------------------
# Candidatos
# ---------------------------------------------------------------------------
def caixas_do_formato(res: dict) -> list[dict]:
    return [s for s in res["slots"] if s.get("formato") == FMT]


def caixas_que_partilham(res: dict) -> set[str]:
    """Os NOMES das caixas de Premodern que emprestam cartas a uma caixa nova.

    Desde 2026-09-08 o grupo `premodern` é `dedicado: false` — as caixas trocam
    cartas entre si e há um tecto de playset por cima. Uma caixa que ele marque
    como dedicada fica de fora: não empresta, e por isso as cópias dela não
    contam para a cobertura de mais ninguém.
    """
    return {s["nome"] for s in caixas_do_formato(res)
            if s.get("nome") and not s.get("dedicado")}


def pct_principal(linhas: list[dict], grupo: set[str]) -> tuple[int, int]:
    """(cobertura, cópias) COMO SE este deck fosse a caixa nº 1 do grupo.

    André, 2026-09-08, à letra: *"como as cartas em Premodern são partilhadas,
    tens que ver se a % desses decks aumentaria se eles fossem o principal;
    mantém a 50 % visto com esta regra de agora."*

    A cobertura do que SOBRA (`pct`) responde a *"o que é que eu monto sem tocar
    em nada?"* — e com seis caixas de Premodern a alocar primeiro a resposta é
    quase sempre "pouco": nenhum candidato chegava aos 50 %. Mas as caixas de
    Premodern **partilham** (`dedicado: false`), e por isso a pergunta certa é
    outra: *"e se este deck escolhesse primeiro?"*. Aí conta tudo o que a regra
    do Premodern VÊ — as cópias livres mais as que estão nas outras caixas do
    grupo, que lhe seriam emprestadas —, com o tecto do que a lista pede.

    O que NÃO conta: as cópias dentro de caixas dedicadas de outros formatos (o
    cEDH, o Pauper), que já não entram no `onde` porque não emprestam. Montar com
    elas era desmontar um deck de outro formato para montar este, e nenhuma
    partilha as devolve.
    """
    need = tenho = 0
    for m in linhas:
        if m.get("basica"):
            continue
        need += m["need"]
        do_grupo = sum(q for caixa, q in (m.get("onde") or {}).items()
                       if caixa in grupo)
        tenho += min(m["need"], m["got"] + do_grupo)
    return (round(100 * tenho / need) if need else 0), tenho


def _caixa_de(cand: dict, caixas: list[dict]) -> dict | None:
    """A caixa que já É este arquétipo, se existir.

    Três maneiras, e as três são precisas: pelo `id` ESTÁVEL do arquétipo (o que
    o *"vou montar este"* congela em `listas_escolhidas`, e o único que sobrevive
    a uma mudança de rótulo), pelo `archetype_id` do clustering (que muda quando o
    `rebuild_archetypes` corre, mas ainda é o que está escrito nas escolhas
    antigas) e pelo NOME normalizado (as seis caixas de hoje vieram do config à
    mão e não têm arquétipo nenhum associado). Uma regra pode ainda apontar a
    caixa (`caixa`), para o dia em que ele lhe mudar o nome.
    """
    alvo = chave_nome(cand["nome"])
    for s in caixas:
        if cand.get("id") and s.get("arquetipo") == cand["id"]:
            return s
        if cand.get("archetype_id") and s.get("archetype_id") == cand["archetype_id"]:
            return s
        if cand.get("caixa") and s.get("slot") == cand["caixa"]:
            return s
        for k in (s.get("nome"), s.get("ref"), s.get("slot")):
            if k and chave_nome(k) == alvo:
                return s
    return None


def candidatos(con: sqlite3.Connection, res: dict,
               registo: "arquetipos.Registo | None" = None) -> list[dict]:
    """Os arquétipos de Premodern a considerar, com a cobertura do que SOBRA.

    Devolve TODOS os que passam o mínimo de listas, já ordenados por
    representação; quem corta o top-10 / top-5 combo é o `ranking`. Cada entrada:

      `id`                a IDENTIDADE estável, do núcleo de cartas
                          (`mtgvault.arquetipos`). É por ela que uma sugestão,
                          uma recusa e uma escolha se reconhecem de um dia para o
                          outro — o `nome` é apresentação e pode mudar;
      `nucleo`            as cartas de que o `id` saiu (é o que o registo guarda);
      `nome`/`subtitulo`  o nome da regra, ou o herdado, ou o do clustering;
      `combo`/`grau`      se é combo e de que tipo;
      `n_lists`           listas que CONTAM (`sources.counting_sql`);
      `pct_principal`     a cobertura COMO SE ele fosse a caixa nº 1 do grupo de
                          Premodern (as caixas partilham) — é esta que decide a
                          sugestão desde 2026-09-08;
      `pct`               a cobertura só com o que SOBRA depois de as caixas
                          estarem servidas. Já não decide nada, mas continua à
                          vista: a diferença entre as duas é quantas cartas
                          viriam emprestadas das outras caixas;
      `pct_total`         a cobertura contando qualquer caixa que empreste, do
                          formato que for. Serve de contexto;
      `estado`            caixa | sugerida | recusada | abaixo.
    """
    regras = combo_regras()
    caixas = caixas_do_formato(res)
    grupo = caixas_que_partilham(res)
    fora = recusadas()
    corte = limiar()
    registo = registo or arquetipos.Registo.carregar()
    cache: dict = {}
    por_combo: dict[str, dict] = {}
    out: list[dict] = []
    for r in loadout.foil_report(con, FMT, top=10 ** 6,
                                 min_lists=min_listas(), res=res):
        cartas = {m["nm"] for m in r["linhas"]}
        regra = classificar_regra(cartas, regras)
        combo = e_combo(regra)
        nome = nome_da_regra(con, r["archetype_id"], regra) if regra else None
        grau = (regra or {}).get("grau") if combo else None
        # Duas entradas com o MESMO nome de regra são o mesmo baralho partido em
        # dois clusters (o Stasis aparece duas vezes na base de 2026-09-08): somam
        # as listas em vez de ocuparem dois lugares do top-5. Só se juntam pelo
        # nome de uma REGRA — juntar pelo nome gerado pelo clustering fundia dois
        # decks diferentes só porque a heurística lhes chamou o mesmo.
        if nome and nome in por_combo:
            velho = por_combo[nome]
            velho["n_lists"] += r["n_lists"]
            velho["ids"] += r["ids"]
            continue
        # A IDENTIDADE sai do núcleo, e o nome é o que a regra diz (autoritário,
        # é uma decisão dele) ou o que o registo já tinha para este núcleo. Só
        # quando o arquétipo é novo é que o rótulo do clustering serve de nome —
        # e a partir daí fica registado, para não mudar amanhã.
        # A lista de consenso entra como `resto`: a distintividade dá às vezes
        # duas ou três cartas, e um punhado de cartas não é uma identidade.
        nucleo = arquetipos.nucleo(_distintivas(con, r["archetype_id"], cache),
                                   resto=sorted(cartas))
        gerado = (_nome_do_cluster(con, r["archetype_id"], cache) or r["label"])
        ident = registo.resolver(FMT, nucleo, nome or gerado,
                                 por_regra=bool(nome))
        c = {
            "id": ident["id"], "nucleo": nucleo, "id_novo": ident["novo"],
            "archetype_id": r["archetype_id"], "ids": list(r["ids"]),
            "nome": ident["nome"],
            "subtitulo": _subtitulo(con, r["archetype_id"], cache) or r["label"],
            "combo": combo, "grau": GRAUS.get(grau or "", ""),
            "n_lists": r["n_lists"], "linhas": r["linhas"],
            "need": r["need"], "got": r["got"],
            "pct": r["pct_livre"], "pct_total": r["pct"],
            "comprar": r["comprar"], "custo": r["custo"],
        }
        c["pct_principal"], c["tenho_principal"] = pct_principal(r["linhas"], grupo)
        if nome:
            por_combo[nome] = c
        out.append(c)
    for c in out:
        caixa = _caixa_de(c, caixas)
        c["slot"] = (caixa or {}).get("slot")
        c["caixa_nome"] = (caixa or {}).get("nome")
        c["recusada_em"] = recusa_de(fora, c["id"], c["nome"])
        # O limiar corre sobre a cobertura COMO PRINCIPAL (André, 2026-09-08:
        # *"tens que ver se a % desses decks aumentaria se eles fossem o
        # principal; mantém a 50 % visto com esta regra de agora"*). Com o `pct`
        # do que sobra, seis caixas de Premodern a alocar primeiro deixavam o
        # melhor candidato a 41 % e nunca havia sugestão nenhuma.
        c["estado"] = ("caixa" if caixa else
                       "recusada" if c["recusada_em"] else
                       "sugerida" if c["pct_principal"] >= corte else "abaixo")
    out.sort(key=lambda c: (-c["n_lists"], c["nome"]))
    return out


def ranking(con: sqlite3.Connection, res: dict,
            cands: list[dict] | None = None,
            registo: "arquetipos.Registo | None" = None) -> dict:
    """O top-10 de representação e o top-5 de combo, com a marca de cada um.

    São duas listas e não uma soma: *"se o deck for top-10 de representação **ou**
    top-5 decks combo"*. Um deck pode estar nas duas (o Enchantress está), e a
    marca `top`/`top_combo` diz em qual — misturá-las escondia o critério por que
    cada um entrou.
    """
    cands = cands if cands is not None else candidatos(con, res, registo)
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
    registo = arquetipos.Registo.carregar()
    rank = ranking(con, res, registo=registo)
    # O registo grava-se AQUI, uma vez por relatório, e só se mudou. É o que faz
    # o nome de hoje valer amanhã — sem isto a identidade só duraria o tempo do
    # processo, que é o mesmo que não existir. Os ids que o config refere ficam
    # protegidos da poda: apagar a entrada de uma recusa fazia-a deixar de bater.
    registo.podar(proteger=list(recusadas()) + ids_escolhidos())
    registo.gravar()
    sugs = sugestoes(rank)
    return {"activo": True, **rank, "sugestoes": sugs,
            "reservas": reservas(sugs), "recusadas": recusadas(),
            "limiar": limiar(), "registo": len(registo.arquetipos)}


# ---------------------------------------------------------------------------
# «OUTROS (JOGAM PREMODERN)»: as cartas dos arquétipos que ele NÃO monta
# (André, 2026-10-16)
# ---------------------------------------------------------------------------
# *"Um género de pasta «outros» com cartas que jogam premodern, estão em decks
# que eu não estou a montar, mas caso eu tenha essas cartas coloco lá as
# fotografias e já sabes que eu as tenho."* É a ENTRADA da regra de 08/09 deste
# módulo: a cobertura `pct_principal` conta cópias, e sem saber que cartas de
# Premodern ele tem fora dos seis decks a sugestão dos 50 % nunca teve dados.
#
# O CRITÉRIO é a união dos NÚCLEOS dos arquétipos elegíveis (top-10 de
# representação ou top-5 de combo) que não são uma caixa dele — e os elegíveis
# saem do `ranking` de cima, o mesmo que decide a sugestão. Um limiar de
# popularidade por carta (5 %) foi medido e recusado: a popularidade é dominada
# pelos decks DELE (Stiflenought, Enchantress e Terrageddon são um terço das
# listas) e só cobria um terço do núcleo dos Goblins. E um classificador ao lado
# do `ranking` era uma segunda resposta a «qual é o top-10» — a lição do
# `event_tier`.
NUCLEO_PCT = 50


def outros_config() -> dict:
    v = config().get("outros")
    return v if isinstance(v, dict) else {}


def nucleo_pct() -> int:
    try:
        v = outros_config().get("nucleo_pct")
        return NUCLEO_PCT if v is None else max(1, min(100, int(v)))
    except (TypeError, ValueError):
        return NUCLEO_PCT


# A COLECÇÃO DE STAPLES (André, 2026-10-17, à letra): *"os decks que quero
# montados de premodern são Stiflenought (lista do Luffy) e UW Replenish
# (consenso), o resto quero apenas ter as cartas; premodern é uma colecção que eu
# tenho e quero manter, em português, nas edições legais do formato, então quero
# ter o máximo de staples possível, associadas aos decks que jogam no formato"* —
# e escolheu: staples = **núcleo dos arquétipos do top**. A pasta «Outros» de
# 16/10 era o embrião disto e passou a ser a colecção.
#
# O QUE MUDOU FACE A 16/10, e porquê: os alvos deixaram de ser «os elegíveis
# (top-10 + top-5 combo) que não são caixa» e passaram a ser **os `top` (15)
# primeiros por nº de listas que contam**, sejam ou não caixa. Os dois decks
# montados ENTRAM: o núcleo deles também é staple — é isso que permite as duas
# contas que ele pediu (a carta que já está num deck conta como «tenho», ou a
# colecção precisa das suas próprias cópias). A PASTA continua a levar só o que
# nenhum deck dele pede (a conta (a)), que é o comportamento de 16/10.
# Medido a 17/10 com o mínimo 31 (passo 1): mediana e moda das cópias dão quase
# o mesmo (596 contra 598 cópias), o máximo dá 704 — fica a mediana de sempre.
TOP_STAPLES = 15


def top_staples() -> int:
    try:
        v = outros_config().get("top")
        return TOP_STAPLES if v is None else max(1, int(v))
    except (TypeError, ValueError):
        return TOP_STAPLES


def alvos_outros(rank: dict) -> list[dict]:
    """Os arquétipos cujo núcleo são staples: os `top` (15) primeiros do
    `ranking` por nº de listas — caixas incluídas desde 2026-10-17 —, mais os que
    ele `incluir` à mão, menos os que `excluir` (por nome, normalizado). Pela
    ordem do ranking (que é a de `n_lists`)."""
    cfg = outros_config()
    inc = {chave_nome(n) for n in cfg.get("incluir") or []}
    exc = {chave_nome(n) for n in cfg.get("excluir") or []}
    topo = {id(c) for c in (rank.get("todos") or [])[:top_staples()]}
    return [c for c in rank.get("todos") or []
            if chave_nome(c["nome"]) not in exc
            and (id(c) in topo or chave_nome(c["nome"]) in inc)]


def nucleo_das_listas(listas: list[dict[str, int]], pct: int | None = None
                      ) -> dict[str, tuple[float, int]]:
    """`carta -> (fracção das listas, cópias)` das cartas em `pct` % ou mais das
    listas (main + side somados em cada lista; básicas fora). As cópias são a
    MEDIANA entre as listas que jogam a carta, arredondada para cima e com o
    tecto do playset — é o que um deck dessas listas pede."""
    import math                                             # noqa: PLC0415
    import statistics                                       # noqa: PLC0415
    pct = nucleo_pct() if pct is None else pct
    n = len(listas)
    if not n:
        return {}
    pres: dict[str, list[int]] = {}
    for lst in listas:
        for nm, q in lst.items():
            if nm in loadout.BASICS or q <= 0:
                continue
            pres.setdefault(nm, []).append(int(q))
    return {nm: (len(qs) / n, min(4, math.ceil(statistics.median(qs))))
            for nm, qs in pres.items() if 100 * len(qs) >= pct * n}


def listas_do_arquetipo(con: sqlite3.Connection, aids: list[int]
                        ) -> list[dict[str, int]]:
    """As listas que CONTAM destes `archetypes` (o mesmo `counting_sql` do
    `foil_report`), cada uma como `carta -> cópias` (main + side)."""
    if not aids:
        return []
    conta, cp = sources.counting_sql(FMT, "d")
    q = ",".join("?" * len(aids))
    out: dict[int, dict[str, int]] = {}
    for did, nm, qt in con.execute(
            f"""SELECT d.id, dc.card_name, dc.quantity FROM decklists d
                  JOIN decklist_cards dc ON dc.decklist_id = d.id
                 WHERE d.archetype_id IN ({q}) AND {conta}""", (*aids, *cp)):
        lst = out.setdefault(did, {})
        lst[nm] = lst.get(nm, 0) + int(qt or 0)
    return list(out.values())


def cartas_dos_meus_decks(res: dict) -> dict[str, str]:
    """`chave da carta -> o deck de Premodern que a pede`: as listas das caixas
    de Premodern e das VERSÕES vivas do formato (`decks_por_formato`)."""
    from . import scryfall                                   # noqa: PLC0415
    out: dict[str, str] = {}
    for s in caixas_do_formato(res):
        for m in list(s.get("have") or []) + list(s.get("missing") or []):
            out.setdefault(scryfall.chave(m["nm"]), s.get("nome") or s["slot"])
    cfg = sources.config()
    le = cfg.get("listas_escolhidas") or {}
    for v in ((cfg.get("decks_por_formato") or {}).get(FMT) or {}).get("versoes") or []:
        if isinstance(v, dict) and not v.get("_saiu") and isinstance(le.get(v.get("id")), dict):
            for c in le[v["id"]].get("cards") or []:
                if isinstance(c, (list, tuple)) and len(c) >= 3:
                    out.setdefault(scryfall.chave(c[1]), str(v.get("nome") or v["id"]))
    return out


def uniao_dos_nucleos(nucleos: list[tuple[str, dict]], dos_decks: dict[str, str]
                      ) -> dict[str, dict]:
    """`carta -> {q, arquetipos, pct}`: a união dos núcleos, sem o que um deck
    dele pede (passa `{}` para a união inteira). A quantidade é o MÁXIMO entre
    os arquétipos (são alternativas, e o playset é o tecto) — a mesma regra das
    `reservas`."""
    from . import scryfall                                   # noqa: PLC0415
    out: dict[str, dict] = {}
    for nome, nu in nucleos:
        for nm, (fr, q) in nu.items():
            if dos_decks and scryfall.chave(nm) in dos_decks:
                continue
            e = out.setdefault(nm, {"q": 0, "arquetipos": [], "pct": 0})
            e["q"] = max(e["q"], q)
            e["pct"] = max(e["pct"], round(100 * fr))
            if nome not in e["arquetipos"]:
                e["arquetipos"].append(nome)
    return dict(sorted(out.items()))


def outros(con: sqlite3.Connection, res: dict) -> dict:
    """O que vai para a pasta «Outros (jogam Premodern)», e o porquê de cada um.

    `{alvos: [{nome, n_lists, combo, nucleo, nos_meus_decks, pct_nos_meus_decks,
    faltam, pct_principal}], cartas: {carta: {q, arquetipos, pct}}, nucleo_pct}`.
    `pct_nos_meus_decks` é a fracção do núcleo (em CARTAS) que um deck dele já
    pede; `pct_principal` é a regra dos 50 % a sério (cópias, como principal) —
    as duas ficam lado a lado porque a primeira diz quão perto o deck está e a
    segunda o que ele já TEM.
    """
    from . import scryfall                                   # noqa: PLC0415
    ctx = res.get("premodern") or {}
    rank = ctx if ctx.get("todos") else ranking(con, res)
    pct = nucleo_pct()
    dos_decks = cartas_dos_meus_decks(res)
    alvos, nucleos = [], []
    for c in alvos_outros(rank):
        nu = nucleo_das_listas(listas_do_arquetipo(con, c.get("ids") or []), pct)
        ja = sorted(nm for nm in nu if scryfall.chave(nm) in dos_decks)
        alvos.append({"nome": c["nome"], "n_lists": c["n_lists"],
                      "caixa": c.get("estado") == "caixa",
                      "combo": bool(c.get("combo")), "nucleo": len(nu),
                      "nos_meus_decks": len(ja),
                      "pct_nos_meus_decks": round(100 * len(ja) / len(nu)) if nu else 0,
                      "faltam": sorted((nm, q) for nm, (_f, q) in nu.items()
                                       if nm not in ja),
                      "pct_principal": c.get("pct_principal", 0),
                      "top": bool(c.get("top")), "top_combo": bool(c.get("top_combo"))})
        nucleos.append((c["nome"], nu))
    todas = uniao_dos_nucleos(nucleos, {})
    return {"alvos": alvos, "cartas": uniao_dos_nucleos(nucleos, dos_decks),
            # A união INTEIRA (2026-10-17), com o deck dele ao lado de cada carta
            # que um deck pede — é a conta (b), a de a colecção precisar das suas
            # próprias cópias fora dos decks. `cartas` é a (a), e é a da pasta.
            "cartas_todas": todas,
            "nos_decks": {nm: dos_decks[scryfall.chave(nm)] for nm in todas
                          if scryfall.chave(nm) in dos_decks},
            "top": top_staples(), "nucleo_pct": pct, "limiar": limiar()}


def contas_staples(o: dict, valores: dict[str, dict]) -> dict:
    """AS DUAS CONTAS que ele pediu a 17/10 (*"a decisão seguinte é dele"*):

    * (a) `nos_decks_contam`: uma carta que já está num dos dois decks conta como
      «tenho» — ficam as staples que nenhum deck pede (é o que a pasta leva);
    * (b) `copias_proprias`: a colecção precisa das suas próprias cópias, fora
      dos decks — todas as staples, com a quantidade inteira.

    `valores` é `carta -> {unit}` (o `valores_outros`, que cobre as duas).
    Uma carta sem preço conta nas cartas e nas cópias e fica a zero no euro, e
    diz-se quantas são — nunca 0 € calado."""
    def conta(cartas):
        eur = sem = 0.0
        for nm, e in cartas.items():
            u = (valores.get(nm) or {}).get("unit")
            if u is None:
                sem += 1
            else:
                eur += u * e["q"]
        return {"cartas": len(cartas), "copias": sum(e["q"] for e in cartas.values()),
                "eur": round(eur, 2), "sem_preco": int(sem)}
    return {"a": conta(o.get("cartas") or {}),
            "b": conta(o.get("cartas_todas") or o.get("cartas") or {})}


def valores_outros(con: sqlite3.Connection, res: dict, o: dict,
                   rl: set[str] | list[str] = ()) -> dict[str, dict]:
    """`carta -> {unit, set, sid, rl}`: o preço de REFERÊNCIA de cada carta da
    pasta, numa impressão CONCRETA (`sid`) — a mais barata que uma caixa de
    Premodern aceita, que é a mesma régua do `unit_serve` da lista de faltas.

    Não é o valor de uma cópia dele, e diz-se: ele ainda não tem nenhuma destas
    (a colecção esvaziou-se a 13/10), e sem cópia não há impressão exacta. Quando
    a foto entrar, o valor da cópia passa a ser o da impressão DELA, pela conta
    de sempre (`collection.valor_da_coleccao`)."""
    caixa = next(iter(caixas_do_formato(res)), None)
    out: dict[str, dict] = {}
    rl = set(rl)
    cache: dict = {}
    # Desde 2026-10-17 é o 1.º anúncio PT de um vendedor profissional na
    # impressão ≤SCG mais barata (`loadout.preco_pro`, a mesma régua das faltas):
    # *"só PT"* — sem anúncio PT, a staple fica sem preço e diz porquê.
    from . import precos                                     # noqa: PLC0415
    regua = loadout.preco_pro if precos.ha_pro(con) else (
        lambda con_, s, nm_, fin, c: loadout.mais_barata_que_serve(con_, s, nm_, fin, c))
    for nm in o.get("cartas_todas") or o.get("cartas") or {}:
        v = (regua(con, caixa, nm, "nonfoil", cache)
             if caixa else {"unit": None, "set": None, "sid": None, "motivo": None})
        out[nm] = {"unit": v.get("unit"), "set": v.get("set"), "sid": v.get("sid"),
                   "rl": nm in rl, "motivo": v.get("motivo"),
                   "cm_url": loadout.link_cardmarket(nm)}
    return out


# ---------------------------------------------------------------------------
# Escrita no config (o modo edição)
# ---------------------------------------------------------------------------
def ids_escolhidos() -> list[str]:
    """Os `id` estáveis das listas que ele já mandou montar (`listas_escolhidas`)."""
    v = sources.config().get("listas_escolhidas")
    return [str(r["id"]) for r in (v or {}).values()
            if isinstance(r, dict) and r.get("id")]


def recusar(cfg: dict, nome: str, quando: str | None = None,
            ident: str | None = None) -> str:
    """*"Não quero este"*: a sugestão sai, e as cartas dela vão para a venda.

    Escreve-se pelo `id` estável, com o NOME ao lado — o nome é para ele
    reconhecer a linha quando abrir o config, e o `id` é o que faz a recusa
    continuar a bater depois de o clustering trocar o rótulo.
    """
    bloco = cfg.setdefault("premodern", {})
    fora = bloco.setdefault("sugestoes_recusadas", {})
    _limpar(fora, nome, ident)
    fora[ident or nome] = {"nome": nome,
                           "em": quando or date.today().isoformat()}
    return f"{nome}: sugestão recusada — as cartas dela libertam-se para a venda"


def _limpar(fora: dict, nome: str, ident: str | None) -> bool:
    """Tira as entradas que são este arquétipo — pela chave ou pelo nome.

    Pelo nome também, e não só pela chave: senão o *"volta a considerar"* não
    conseguia desfazer uma recusa escrita na forma antiga, e a sugestão ficava
    recusada para sempre sem nada na página a dizer porquê.
    """
    alvo = chave_nome(nome)
    velhas = [k for k, v in fora.items()
              if k == ident or k == nome
              or (alvo and chave_nome((v or {}).get("nome") if isinstance(v, dict)
                                      else k) == alvo)]
    for k in velhas:
        fora.pop(k)
    return bool(velhas)


def aceitar(cfg: dict, nome: str, ident: str | None = None) -> str:
    """Desfaz o *"não quero este"*."""
    bloco = cfg.get("premodern") or {}
    fora = bloco.get("sugestoes_recusadas") or {}
    if not _limpar(fora, nome, ident):
        return f"{nome} não estava recusado"
    if not fora:
        bloco.pop("sugestoes_recusadas", None)
    return f"{nome}: volta a ser sugestão"


# ---------------------------------------------------------------------------
# Migração: das chaves por NOME para as chaves por `id`
# ---------------------------------------------------------------------------
def migrar_config(cfg: dict, mapa: dict[str, str]) -> tuple[dict, int]:
    """Passa as recusas e as escolhas de chave-nome para chave-`id`.

    `mapa` é `chave_nome -> id`, e sai do ranking do dia (é lá que os dois se
    veem ao mesmo tempo). O que não aparecer no mapa **fica como está**: um
    arquétipo que hoje não tem listas volta a ter daqui a um mês, e apagar-lhe a
    recusa era decidir por ele. Idempotente, e devolve quantas linhas mexeu.
    """
    n = 0
    fora = (cfg.get("premodern") or {}).get("sugestoes_recusadas")
    if isinstance(fora, dict):
        for k in list(fora):
            v = fora[k]
            if isinstance(v, dict) and v.get("nome"):
                continue                       # já está na forma nova
            ident = mapa.get(chave_nome(k))
            if not ident:
                continue
            fora.pop(k)
            fora[ident] = {"nome": k, "em": str(v)}
            n += 1
    for rec in (cfg.get("listas_escolhidas") or {}).values():
        if isinstance(rec, dict) and not rec.get("id"):
            ident = mapa.get(chave_nome(rec.get("nome") or ""))
            if ident:
                rec["id"] = ident
                n += 1
    return cfg, n


def mapa_de_ids(cands: list[dict]) -> dict[str, str]:
    """`chave_nome -> id`, para a `migrar_config`."""
    return {chave_nome(c["nome"]): c["id"] for c in cands if c.get("id")}
