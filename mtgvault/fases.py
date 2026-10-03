"""AS FASES DA ARRUMAÇÃO, E AS REGRAS DA VENDA (André, 2026-10-01 e 2026-10-02).

Ele vai arrumar a colecção por FASES. A 2026-10-01 ditou quatro protecções; a
2026-10-02 **fechou a lista dos 16 decks que ficam** e reescreveu as regras das
cartas. As palavras dele, que é por elas que isto se mede:

  R1  DUAIS   *"quer ter 4 de cada em colecção FORA dos decks; o que passar
      disso vende-se ou troca-se."* São as dez duais originais, DERIVADAS do
      catálogo (ver `duais`). **A R1 manda sobre a R4**: as duais são Reserved
      List, e ele foi explícito — *"para elas manda a R1, que é mais
      específica"*. Uma quinta dual fora dos decks vai à venda apesar de ser RL.
  R2  SHOCKLANDS  *"todas as cópias protegidas, como já está"* — todos os
      acabamentos, todas as línguas, todas as repetidas, dentro ou fora de um
      deck. Sem excepções.
  R3  FETCHLANDS  idem.
  R4  RESERVED LIST  protege-se *"o RL que ele joga; o que não joga vai à
      venda"*. O resto da RL continua a passar pela regra dos 5 % de 2026-09-08,
      com o carimbo da régua de preço.
  R5  A RESERVA  *"protege-se toda a carta que tenha sido jogada NO ÚLTIMO MÊS
      (30 dias a rolar) nos decks acima, mesmo que esteja hoje fora da lista.
      «Jogada no deck» = aparece numa lista do arquétipo desse deck nos últimos
      30 dias, main ou side."* **Isto SUBSTITUIU o limiar de 20 %** de
      2026-10-01, que foi apagado.
  R5b STAPLES DE SIDEBOARD, SÓ PREMODERN  *"depois de a decklist fechar o
      Premodern não mexe muito, mas convém ter no sideboard as cartas que são
      staples."* Pela taxa de presença em sideboards de TODAS as listas de
      Premodern dos últimos 30 dias, com o corte no config e a CURVA medida.
  RD  O DECK  nenhuma cópia dentro de um deck cujo `estado` protege vai à venda.

  *"TUDO O QUE NÃO SE ENQUADRAR NESTAS REGRAS vai para uma lista única chamada
  VENDER."*

AS LISTAS DE TERRAS DERIVAM-SE DO CATÁLOGO — É A PARTE QUE NÃO PODE SER DE
MEMÓRIA
-------------------------------------------------------------------------------
Ordem dele, à letra: *"as listas de shocklands e fetchlands NÃO podem ser
escritas à mão a partir da tua memória: deriva-as do catálogo (tipos, oracle
text, edições) e grava a regra usada. Se não der exactamente 10 e 10, PARA e diz
quais achaste — não arredondes a conta."*

Para isso **o catálogo passou a guardar o `oracle_text`** (2026-10-01, nos três
sítios: `catalog_schema.sql`, `db._migrate` e `scryfall._row`/`INSERT`). Sem ele
não dava: o filtro que as outras colunas permitiam — `type_line = 'Land'` com a
1.ª impressão em ONS/ZEN — devolve **19** nomes e não 10 (leva o Riptide
Laboratory, o Grand Coliseum, o Valakut, o Emeria). Medido a 2026-10-01. O
`scryfall.has_card_meta` passou a perguntar pela coluna, senão o
`daily._catalog` — que salta o `sync` quando o catálogo tem linhas — deixava-a a
NULL para sempre, que é o padrão do `event_tier`.

As duas regras não usam a EDIÇÃO, e isso é melhor do que parecia: distinguem-se
pelo texto, por isso uma reimpressão futura entra sozinha e um ciclo novo com o
mesmo `type_line` fica fora sem ninguém mexer na lista. Medido no catálogo de
2026-10-01 (112 754 impressões, 1 059 terras distintas em papel):

  * **shocklands → 10**: dois sub-tipos de terra básica no `type_line` **e** o
    texto a dizer que se pode pagar 2 de vida para não entrar virada. A primeira
    metade sozinha dá **66** nomes (as duais originais, as de BFZ, as de surveil
    de MKM, as de cycling de AKH, as «Turbulent» de SOC…); é a segunda que
    corta. Controlo no `test_fases.py`.
  * **fetchlands → 10**: o texto a pagar 1 de vida, sacrificar-se e procurar na
    biblioteca uma carta que ele põe em jogo, nomeando **exactamente dois** tipos
    básicos. O «exactamente dois» é o que deixa de fora a Prismatic Vista e a
    Elven Passage, que procuram uma básica qualquer e por isso não são deste
    ciclo. **Armadilha que custou uma passagem:** o texto da Polluted Delta e da
    Scalding Tarn diz *"for **an** Island"* — um padrão com `for a ` perdia duas
    das dez e dava oito, sem erro nenhum.

Se a conta não der 10 e 10, `shocklands`/`fetchlands` **levantam**
`TerrasNaoDerivadas` com os nomes que acharam. Não devolvem uma lista curta de
propósito: uma protecção vazia em silêncio manda shocklands para a venda, e é
exactamente isso que a ordem proíbe. Quem desenha página apanha a excepção e
di-lo em português.

O ESTADO DA CAIXA É QUE DECIDE — E O SEGUNDO CAMPO FOI APAGADO (2026-10-02)
-------------------------------------------------------------------------------
A 2026-10-01 isto tinha um campo PRÓPRIO (`caixas[].decisao`:
`montado`/`guardado`/`dissolvido`) ao lado do `estado` que as caixas já tinham
desde a v6 (`candidata`/`permanente`/`montada`, com `congelada` CALCULADA). Eram
**duas verdades para a mesma pergunta** — exactamente o padrão que a v6 veio
fechar (*"temos decks vigiados e deckbox que é a mesma coisa"*) — e ele decidiu
ficar com a antiga. O campo `decisao` **saiu**, com tudo o que o lia: o endpoint
`/api/fase-decisao`, o `fases decisao` do CLI e os botões da Fase 1.

O mapeamento é o dele, à letra:

    montada     protege   (está sleevada na estante)
    congelada   protege   (= montada; é calculada, ver `caixas.estado_de`)
    permanente  protege   (é um deck que fica)
    candidata   NÃO protege por si  (só recebe o que sobra)

**A OMISSÃO PROTEGE**, e isso não é um acaso deste módulo: o
`caixas.estado_de` já devolvia `permanente` a uma caixa sem a chave — *"era o
que as catorze do loadout eram antes de a distinção existir, e um default a
`False` esvaziava a alocação de quem não a escrevesse"*. Aqui vale o dobro:
**um deck sem estado escrito não manda uma única carta para a venda**. Tem caso
de teste (`caso_uma_caixa_sem_estado_protege`).

Onde é que o estado se MUDA: na **Deckboxes**, que é onde esse gesto já vive
(«Tornar permanente», «Montar», «Desmontar», «Subir/Descer») e onde ele tem a
caixa na mão. A Fase 1 mostra-o e não o reescreve — dois caminhos para o mesmo
gesto discordam um dia qualquer, em silêncio.

A RESERVA É O QUE FOI JOGADO NOS ÚLTIMOS 30 DIAS (R5)
-------------------------------------------------------------------------------
A reserva não pode ser trabalho manual. Sai das listas do ARQUÉTIPO de cada deck
nos últimos `JANELA_DIAS` (30) dias — todas as cartas, main **ou** side, mesmo
as que hoje estão fora das 75 —, mais o que ele acrescentar à mão
(`caixas[].reserva`), menos o que ele tirar no botão *«não é necessária»*
(`caixas[].reserva_fora`). Para o deck de Duel Commander o arquétipo é o
**comandante** (`mtgvault/consenso.py`, 2026-10-01).

O **limiar de 20 %** que aqui esteve a 2026-10-01 foi APAGADO por ordem dele:
*"esta substitui o limiar de 20 % que eu pus ontem — APAGA o limiar"*. A janela
de 30 dias é o travão novo, e é um travão a sério porque a base só guarda 30
dias de listas (`daily.prune_decklists`) — o que lá está é, por construção, o
mês que passou.

**O universo de listas da R5 é TODAS as listas da base**, e não o
`sources.counting_sql`. É uma excepção deliberada e documentada: ver
`sources.ids_por_assinatura`. Resumo — sub-contar aqui é vender uma carta que
ele precisa, e no Pauper e no cEDH o filtro dá ZERO de propósito
(`metagame_fontes.*.tiers = []`), o que deixava dois decks sem protecção
nenhuma, em silêncio.

A reserva **protege só o que ele TEM**. O que não tem não se protege: alimenta a
lista de compras que o loadout já faz.

ONDE É QUE AS PROTECÇÕES MORDEM
-------------------------------------------------------------------------------
Em DOIS sítios, de propósito, e com a mesma resposta nos dois (a lição do
`event_tier`: duas listas para a mesma pergunta divergem em silêncio):

  1. `candidatos()` — a **Fase 3** e a lista **VENDER**: o que PODE ir à venda
     depois das regras, com o motivo e a regra por cópia excluída. É só
     leitura, varre a colecção inteira e é ela que responde à pergunta dele.
  2. `filtrar_venda()` — o MOTOR. Entra no `loadout.sell_list`, no fim, como o
     filtro da reserva das caixas de 2026-09-20 já entrava: uma cópia protegida
     sai de `venda`/`venda_rl` para a saída **`protegidas`**, com o motivo.
     Uma protecção que só valesse numa página não era uma protecção.

**Cada cópia excluída guarda o MOTIVO em português e qual das regras a
apanhou.** Sem motivo não há exclusão silenciosa — é a regra dele. E a R1 obriga
os dois a saber PARTIR uma linha: um lote de 5 duais fora dos decks tem 4 cópias
protegidas e 1 candidata, e dar o lote inteiro a um dos lados era mentir por
quatro ou por uma.

A TRAVA: O RC GHENT É A 9-11/10
-------------------------------------------------------------------------------
`venda.congelado_ate` (**2026-10-12**). Qualquer geração de saída de venda ou
exportação RECUSA-SE a correr antes dessa data, com a razão escrita
(`VendaCongelada`, subclasse de `ValueError` como a `webapp.VendaDesligada`, para
o `do_POST` a traduzir em 409). Ele joga Modern em Ghent a 9-11/10 e não pode
dar-se o caso de uma carta do deck sair numa lista de stock na véspera.
"""
from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from datetime import date

from . import caixas as _caixas
from . import collection as _col
from . import nomes, sources

# ---------------------------------------------------------------------------
# AS REGRAS: a chave, o rótulo e a ordem por que se perguntam
# ---------------------------------------------------------------------------
# A ordem conta para o MOTIVO: a razão que se escreve na cópia é a que
# SOBREVIVE. Uma shockland dentro de um deck montado é apanhada pela R2 e não
# pela RD, porque a R2 protege-a *"sem excepções"* — se amanhã o deck se
# desmontar, continua protegida, e o motivo tem de dizer isso.
R1 = "r1-duais"
R2 = "r2-shocklands"
R3 = "r3-fetchlands"
R4 = "r4-rl-joga"
R5 = "r5-reserva-30d"
R5B = "r5b-staples-premodern"
RD = "rd-deck"
PROTECCOES = (R1, R2, R3, R4, RD, R5, R5B)
ROTULOS = {
    R1: "R1 · dual original (4 fora dos decks)",
    R2: "R2 · shockland",
    R3: "R3 · fetchland",
    R4: "R4 · Reserved List que jogas",
    RD: "RD · está num deck que fica",
    R5: "R5 · jogada nos últimos 30 dias",
    R5B: "R5b · staple de sideboard de Premodern",
}

# ---------------------------------------------------------------------------
# O ESTADO DE CADA CAIXA É QUE DECIDE (André, 2026-10-02)
# ---------------------------------------------------------------------------
# Não há um segundo campo: é o `caixas[].estado` da v6. Ver o cabeçalho — o
# `decisao` de 2026-10-01 foi apagado por ordem dele, com tudo o que o lia.
#
# A OMISSÃO PROTEGE. O `caixas.estado_de` devolve `permanente` a uma caixa sem
# a chave, e `montada` a uma que diga `congelada`. Um deck sem estado escrito
# não manda uma única carta para a venda.
ESTADOS_PROTEGEM = (_caixas.PERMANENTE, _caixas.MONTADA)
ESTADO_OMISSAO = _caixas.PERMANENTE
TEXTO_ESTADO = {
    _caixas.CANDIDATA: "candidata — só recebe o que sobra, e as cópias dela não "
                       "ficam protegidas por estarem aqui",
    _caixas.PERMANENTE: "permanente — é um deck que fica; as cópias lá dentro "
                        "não vão à venda",
    _caixas.MONTADA: "montada — está sleevada na estante; as cópias lá dentro "
                     "não vão à venda",
}


def estado_de(caixa: dict) -> str:
    """O estado desta caixa, pela MESMA função que o motor de alocação usa.

    Não há uma segunda leitura: é o `caixas.estado_de`, que já aceita a forma v5
    e v6 e já mapeia `congelada` em `montada`.
    """
    return _caixas.estado_de(caixa)


def protege(estado: str | None) -> bool:
    """Se uma cópia dentro de uma caixa neste estado está protegida (RD)."""
    return (estado or ESTADO_OMISSAO) in ESTADOS_PROTEGEM


def estados(cfg: dict | None = None) -> dict[str, str]:
    """`slot -> estado` de todas as caixas do config."""
    return {c["slot"]: estado_de(c) for c in _caixas.do_config(cfg)
            if c.get("slot")}


# ---------------------------------------------------------------------------
# R1/R2/R3: as TRÊS listas de terras, DERIVADAS do catálogo
# ---------------------------------------------------------------------------
BASICOS = ("Plains", "Island", "Swamp", "Mountain", "Forest")
N_SHOCK = N_FETCH = N_DUAL = 10
# A R1: *"quer ter 4 de cada em colecção FORA dos decks"*.
DUAIS_ALVO_FORA = 4

# A DUAL ORIGINAL é a que tem dois sub-tipos de terra básica e **mais nada**: o
# `oracle_text` dela é só o lembrete da habilidade de mana. Medido no catálogo de
# 2026-10-02: das 1 059 terras em papel, **69** têm dois sub-tipos básicos (as
# dez originais, as dez shocklands, as de BFZ, as de surveil de MKM, as de
# cycling de AKH, as «Turbulent» de SOC…) e **só as dez** não têm uma segunda
# linha de texto. Não se usa a EDIÇÃO nem a cor — pela mesma razão das outras
# duas listas: uma reimpressão futura entra sozinha.
#
# ARMADILHA, e custou uma passagem: `oracle_text` VAZIO dá **zero**. As originais
# trazem o lembrete `({T}: Add {U} or {B}.)` — entre parênteses, que é como a
# Scryfall escreve texto que não é regra nova. Filtrar por «sem texto» parecia
# óbvio e dava uma protecção vazia, em silêncio.
RE_LEMBRETE_MANA = re.compile(r"^\(\s*\{T\}\s*:\s*Add\s*\{.\}\s*or\s*\{.\}\s*\.?\s*\)$",
                              re.I)
REGRA_DUAL = (
    "type_line com DOIS sub-tipos de terra básica E um oracle_text que é SÓ o "
    "lembrete da habilidade de mana (/^\\({T}: Add {X} or {Y}.\\)$/i) — ou seja, "
    "sem nenhuma linha de regras a seguir: é isso que separa as dez originais "
    "das outras 59 terras de dois sub-tipos (shocklands, BFZ, surveil, cycling)")

# A shockland diz que se pode pagar 2 de vida para não entrar virada. O `it`/`~`/
# `this land` cobre as três formas por que a Scryfall escreve o sujeito em
# impressões de épocas diferentes.
RE_SHOCK = re.compile(
    r"you may pay 2 life\.\s*if you don't,\s*(it|~|this land) enters tapped",
    re.I | re.S)
# A fetchland paga 1 de vida, sacrifica-se, e procura uma carta que PÕE EM JOGO.
# `an?` e não `a `: a Polluted Delta e a Scalding Tarn dizem *"for an Island"* —
# com `for a ` a conta dava OITO e nenhum passo dava erro.
RE_FETCH = re.compile(
    r"pay 1 life.*?sacrifice.*?search your library for an? .*?"
    r"card,? put it onto the battlefield", re.I | re.S)

REGRA_SHOCK = (
    "type_line com DOIS sub-tipos de terra básica E o texto a dizer que se pode "
    "pagar 2 pontos de vida para não entrar virada "
    "(/you may pay 2 life\\. if you don't, it enters tapped/i)")
REGRA_FETCH = (
    "o texto a pagar 1 ponto de vida, sacrificar-se e procurar na biblioteca uma "
    "carta que põe em jogo, nomeando EXACTAMENTE dois tipos de terra básica "
    "(/pay 1 life … sacrifice … search your library for an? … card, put it onto "
    "the battlefield/i) — o «exactamente dois» exclui a Prismatic Vista e a "
    "Elven Passage, que procuram uma básica qualquer")


# QUANDO É QUE A CONTA TEM DE DAR DEZ — e esta distinção é precisa.
#
# A ordem é clara: *"se não der exactamente 10 e 10, PARA"*. Mas há dois motivos
# diferentes para não dar dez, e tratá-los igual não serve:
#
#   * **o catálogo A SÉRIO sem `oracle_text`** (por sincronizar): as cartas estão
#     lá e a derivação não as vê. Aqui a protecção ficaria vazia e mandava
#     shocklands para a venda sem um único passo a falhar — é o padrão do
#     `event_tier`, e é aqui que se PARA, alto;
#   * **um catálogo PEQUENO** que simplesmente não contém aquelas cartas (as
#     bases dos testes têm trinta cartas). Aí «zero shocklands» é a resposta
#     certa, não uma avaria — é o mesmo princípio do `foil_info`: uma carta que o
#     catálogo não conhece não é uma carta «sem foil».
#
# O que os separa é o TAMANHO do catálogo, com o mesmo limiar que o
# `daily._catalog` já usa para decidir se vale a pena sincronizar.
CATALOGO_COMPLETO = 1000


def catalogo_completo(con) -> bool:
    """Se isto é um catálogo a sério (e não a base de trinta cartas de um teste).

    É o mesmo limiar do `daily._catalog`, de propósito: a pergunta é a mesma.
    """
    from . import db                                         # noqa: PLC0415
    try:
        return db.catalog_size(con) >= CATALOGO_COMPLETO
    except sqlite3.Error:
        return False


class TerrasNaoDerivadas(RuntimeError):
    """A derivação não deu exactamente dez nomes NUM CATÁLOGO COMPLETO.

    Levanta-se em vez de se devolver a lista que houver, porque uma protecção
    curta é pior do que um erro: manda shocklands para a lista de venda sem um
    único passo a falhar. A causa provável é o catálogo sem `oracle_text` — o
    `sync-cards` resolve (`scryfall.has_card_meta` passou a notá-lo).
    """

    def __init__(self, qual: str, nomes: list[str], esperado: int, regra: str):
        self.qual, self.nomes, self.esperado, self.regra = qual, nomes, esperado, regra
        achou = ", ".join(nomes) if nomes else "nenhuma"
        super().__init__(
            f"{qual}: a derivação do catálogo deu {len(nomes)} nomes e tinham de "
            f"ser {esperado}. Achei: {achou}. A regra usada foi: {regra}. "
            "Se o catálogo não tiver `oracle_text` preenchido, corre "
            "`py -m mtgvault.cli sync-cards`.")


def _subtipos_basicos(type_line: str | None) -> list[str]:
    sub = (type_line or "").split("—", 1)
    if len(sub) < 2:
        return []
    return [t for t in sub[1].replace("//", " ").split() if t in BASICOS]


def _terras_do_catalogo(con, cache: dict | None = None) -> dict[str, dict]:
    """`nome -> primeira impressão em papel` de todas as terras.

    Uma consulta só, guardada na cache da corrida: as duas derivações partem da
    mesma varredura e isto é chamado por relatório, não por cópia.
    """
    cache = {} if cache is None else cache
    if "_terras" in cache:
        return cache["_terras"]
    out: dict[str, dict] = {}
    for r in con.execute(
            "SELECT name, set_code, released_at, type_line, oracle_text "
            "  FROM cards WHERE digital = 0 AND type_line LIKE 'Land%' "
            " ORDER BY released_at, set_code"):
        out.setdefault(r["name"], dict(r))
    cache["_terras"] = out
    return out


def _exigir(con, exigir: bool | None) -> bool:
    return catalogo_completo(con) if exigir is None else bool(exigir)


def shocklands(con, cache: dict | None = None,
               exigir: bool | None = None) -> dict:
    """`{nomes, regra, n}` — as dez shocklands, derivadas do catálogo.

    `exigir` decide se a conta TEM de dar dez: por omissão, só num catálogo
    completo (ver `CATALOGO_COMPLETO`). `verificar` força-o.
    """
    cache = {} if cache is None else cache
    if "_shock" in cache:
        return cache["_shock"]
    nomes = sorted(nm for nm, d in _terras_do_catalogo(con, cache).items()
                   if len(_subtipos_basicos(d["type_line"])) == 2
                   and RE_SHOCK.search(d["oracle_text"] or ""))
    if len(nomes) != N_SHOCK and _exigir(con, exigir):
        raise TerrasNaoDerivadas("shocklands", nomes, N_SHOCK, REGRA_SHOCK)
    cache["_shock"] = {"nomes": nomes, "regra": REGRA_SHOCK, "n": len(nomes)}
    return cache["_shock"]


def fetchlands(con, cache: dict | None = None,
               exigir: bool | None = None) -> dict:
    """`{nomes, regra, n}` — as dez fetchlands, derivadas. Ver `shocklands`."""
    cache = {} if cache is None else cache
    if "_fetch" in cache:
        return cache["_fetch"]
    nomes = []
    for nm, d in _terras_do_catalogo(con, cache).items():
        m = RE_FETCH.search(d["oracle_text"] or "")
        if not m:
            continue
        alvo = m.group(0)
        # Quantos tipos básicos a PROCURA nomeia. O ciclo das dez nomeia dois;
        # a Prismatic Vista e a Elven Passage não nomeiam nenhum (procuram uma
        # básica qualquer) e por isso não são deste ciclo.
        if len([b for b in BASICOS if re.search(rf"\b{b}\b", alvo)]) == 2:
            nomes.append(nm)
    nomes.sort()
    if len(nomes) != N_FETCH and _exigir(con, exigir):
        raise TerrasNaoDerivadas("fetchlands", nomes, N_FETCH, REGRA_FETCH)
    cache["_fetch"] = {"nomes": nomes, "regra": REGRA_FETCH, "n": len(nomes)}
    return cache["_fetch"]


def duais(con, cache: dict | None = None,
          exigir: bool | None = None) -> dict:
    """`{nomes, regra, n}` — as dez duais originais, derivadas. Ver `RE_LEMBRETE_MANA`."""
    cache = {} if cache is None else cache
    if "_duais" in cache:
        return cache["_duais"]
    nomes = sorted(nm for nm, d in _terras_do_catalogo(con, cache).items()
                   if len(_subtipos_basicos(d["type_line"])) == 2
                   and RE_LEMBRETE_MANA.match((d["oracle_text"] or "").strip()))
    if len(nomes) != N_DUAL and _exigir(con, exigir):
        raise TerrasNaoDerivadas("duais originais", nomes, N_DUAL, REGRA_DUAL)
    cache["_duais"] = {"nomes": nomes, "regra": REGRA_DUAL, "n": len(nomes),
                       "alvo_fora": DUAIS_ALVO_FORA}
    return cache["_duais"]


def verificar(con) -> dict:
    """A VERIFICAÇÃO explícita das três listas: exige as dez de cada, sempre.

    É esta que o `cli fases` e a página chamam, para a conta que não dá dez ser
    um erro à vista e não um número pequeno que passa. A derivação usada em
    cada relatório é a mesma; o que muda é quem insiste.
    """
    cache: dict = {}
    return {"duais": duais(con, cache, exigir=True),
            "shocklands": shocklands(con, cache, exigir=True),
            "fetchlands": fetchlands(con, cache, exigir=True),
            "catalogo_completo": catalogo_completo(con)}


def terras_protegidas(con, cache: dict | None = None) -> dict[str, str]:
    """`nome -> "shockland" | "fetchland"`. São a R2 e a R3, e não têm
    excepções: **todas** as cópias de cada um destes nomes ficam protegidas —
    todos os acabamentos, todas as línguas, todas as repetidas, dentro ou fora
    de um deck. Palavras dele: *"Todas as cópias"*.

    As DUAIS originais **não estão aqui**: a regra delas é a R1 (quota de quatro
    fora dos decks) e vive no `plano_duais`."""
    cache = {} if cache is None else cache
    if "_terras_prot" in cache:
        return cache["_terras_prot"]
    out = {nm: "shockland" for nm in shocklands(con, cache)["nomes"]}
    out.update({nm: "fetchland" for nm in fetchlands(con, cache)["nomes"]})
    cache["_terras_prot"] = out
    return out


# ---------------------------------------------------------------------------
# R1: a QUOTA das duais originais
# ---------------------------------------------------------------------------
# O PREÇO DE COMPRA DE UMA DUAL TEM DE SER DE UMA CARTA QUE SE POSSA JOGAR, e
# isto apanhou dois defeitos ANTERIORES a esta ordem, os dois no
# `loadout.card_price` (o mínimo entre impressões, que é a pergunta certa para
# uma compra). Medido a 2026-10-02:
#
#   1. **a memorabilia entra**: o `card_price` não filtra `set_type` nem
#      `digital`, por isso o mínimo pode ser de `30a` (as proxies do 30.º
#      aniversário) ou de `ced`/`cei` (a Collectors' Edition) — cartas que não
#      são legais em torneio nenhum. **181 nomes** mudam de preço se saírem, e
#      as diferenças são enormes: Black Lotus 2 277,81 € → **16 000,64 €**, Mox
#      Jet 25,00 € → **6 232,72 €**, Volcanic Island 221,19 € → 1 074,23 €;
#   2. **há preços absurdos na Summer Magic** (`sum`, que é `core` e por isso a
#      memorabilia não apanha): Badlands a **0,02 €** e Tundra a **0,25 €** no
#      price guide do Cardmarket. É exactamente o caso que a decisão de
#      2026-09-25 nomeia — *"a Tundra de Revised dele valia 0,25 €, o preço de
#      uma impressão de Summer Magic"* —, que foi corrigido para o que ele TEM
#      (`preco_da_copia`) e ficou de pé para a COMPRA.
#
# **Não se tocou no `card_price`**: ele alimenta o *"fechar tudo"* e o «a
# comprar» de TODAS as caixas, e mudá-lo às cegas na semana do RC Ghent era
# trocar o número por que ele decide sem o medir caixa a caixa. Aqui dá-se o
# `unit` do site (para não haver dois números em silêncio) **e** o `unit_jogavel`
# ao lado, com a edição de onde vem, e a página e o relatório dizem a diferença.
# A correcção a sério é no `loadout.card_price` e fica para ele decidir.
def _preco_jogavel(con, nm: str, cache: dict | None = None):
    """`(preço, edição)` da impressão em PAPEL e não-memorabilia mais barata."""
    from . import loadout, precos                            # noqa: PLC0415
    cache = {} if cache is None else cache
    k = f"_pjog_{nm}"
    if k in cache:
        return cache[k]
    expr = precos.sql_impressao(fontes_=precos.fontes())
    r = con.execute(
        f"""SELECT c.set_code sc, {expr} p
              FROM cards c JOIN {precos.sql_acabamentos(('nonfoil',))} f
             WHERE c.name = ? AND c.digital = 0 AND c.set_type <> 'memorabilia'
               AND {expr} IS NOT NULL
             ORDER BY p LIMIT 1""", ("nonfoil", nm)).fetchone()
    cache[k] = ((r["p"], (r["sc"] or "").upper()) if r else (None, ""))
    _ = loadout  # o import serve de nota: a correcção a sério é lá
    return cache[k]



def plano_duais(con, res: dict, cfg: dict | None = None,
                cache: dict | None = None) -> dict:
    """A R1 resolvida: por nome, quantas tem, quantas estão em decks, quantas
    estão FORA, quantas se protegem, quantas VENDER e quantas COMPRAR.

    *"Quer ter 4 de cada em colecção FORA dos decks; o que passar disso vende-se
    ou troca-se."* Logo: as que estão dentro de um deck que fica são da RD; das
    que estão fora, protegem-se **quatro** e o resto é candidato — apesar de
    serem Reserved List, porque *"para elas manda a R1, que é mais específica"*.

    **Quais das quatro é que ficam:** as de MAIOR valor de referência, com a
    edição e o `copy_id` a desempatar. Ele quer ter quatro de cada; ficar com as
    melhores é o que um colecionador faz, e a ordem tem de ser determinista
    senão a lista de venda troca de cópia de um dia para o outro.

    Devolve também `por_sublote`: `{(copy_id, caixa) -> {prot, q}}` para cada
    sub-lote FORA dos decks. É por aqui que a Fase 3 **e** o motor da venda dão
    a mesma resposta e partem a mesma linha ao meio — um lote de cinco fora dos
    decks tem quatro protegidas e uma candidata.

    Guarda-se o `q` do sub-lote e não só as protegidas, e isso é preciso: o
    motor da venda recebe uma linha que é um PEDAÇO do sub-lote (o excedente que
    o playset já cortou), e dizer-lhe «deste sub-lote há quatro protegidas»
    protegia a cópia que ele estava mesmo a oferecer. O que se gasta é o
    ORÇAMENTO de cópias LIVRES — ver `contexto`/`quem_protege`.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    if "_duais_plano" in cache:
        return cache["_duais_plano"]
    nomes = duais(con, cache)["nomes"]
    est = estados(cfg)
    pc: dict = cache.setdefault("_precos", {})
    por_sublote: dict[tuple, int] = {}
    linhas, vender, comprar = [], [], []
    tot = {"copias": 0, "em_decks": 0, "fora": 0, "protegidas": 0,
           "vender": 0, "comprar": 0, "valor_vender": 0.0}
    for nm in nomes:
        lotes = [l for l in (res.get("pool") or {}).get(nm) or [] if l["q"] > 0]
        dentro = [l for l in lotes if l.get("caixa") and protege(est.get(
            l["caixa"], ESTADO_OMISSAO))]
        fora = [l for l in lotes if l not in dentro]
        n_dentro = sum(l["q"] for l in dentro)
        n_fora = sum(l["q"] for l in fora)
        # A ordem da quota: valor desc, edição, copy_id. Determinista.
        fora = sorted(fora, key=lambda l: (
            -(loadout.preco_da_copia(con, l["sid"], l["finish"], nm, pc, lot=l)["unit"] or 0),
            (l["set_code"] or ""), l["id"]))
        resto = DUAIS_ALVO_FORA
        n_prot = n_vend = 0
        val_vend = 0.0
        for l in fora:
            k = (l["id"], l.get("caixa") or "")
            fica = min(resto, l["q"])
            resto -= fica
            v = por_sublote.setdefault(k, {"prot": 0, "q": 0})
            v["prot"] += fica
            v["q"] += l["q"]
            n_prot += fica
            sobra = l["q"] - fica
            if sobra:
                u = loadout.preco_da_copia(con, l["sid"], l["finish"], nm, pc, lot=l)["unit"]
                n_vend += sobra
                val_vend += (u or 0) * sobra
                vender.append({"nm": nm, "q": sobra, "copy_id": l["id"],
                               "set": (l["set_code"] or "").upper(),
                               "lang": l["lang"] or "en", "finish": l["finish"],
                               "local": l["local"], "unit": u,
                               "total": round((u or 0) * sobra, 2)})
        falta = max(0, DUAIS_ALVO_FORA - n_fora)
        if falta:
            # O preço de COMPRA é o `card_price` — o mínimo entre impressões do
            # mesmo nome. É a pergunta certa aqui (*"quanto custa arranjar
            # mais uma?"*) e não o `preco_da_copia`, que responde *"quanto vale
            # a que ele tem"*. Ver a decisão de 2026-09-25.
            u, _fin = loadout.card_price(con, nm)
            jog, onde = _preco_jogavel(con, nm, cache)
            comprar.append({"nm": nm, "q": falta, "unit": u,
                            "unit_jogavel": jog, "set_jogavel": onde})
        linhas.append({"nm": nm, "copias": n_dentro + n_fora,
                       "em_decks": n_dentro, "fora": n_fora,
                       "protegidas": n_prot, "vender": n_vend,
                       "comprar": falta, "alvo": DUAIS_ALVO_FORA})
        tot["copias"] += n_dentro + n_fora
        tot["em_decks"] += n_dentro
        tot["fora"] += n_fora
        tot["protegidas"] += n_prot
        tot["vender"] += n_vend
        tot["comprar"] += falta
        tot["valor_vender"] += val_vend
    tot["valor_vender"] = round(tot["valor_vender"], 2)
    tot["custo_comprar"] = round(sum((c["unit"] or 0) * c["q"] for c in comprar), 2)
    tot["custo_comprar_jogavel"] = round(
        sum(((c["unit_jogavel"] if c["unit_jogavel"] is not None else c["unit"])
             or 0) * c["q"] for c in comprar), 2)
    vender.sort(key=lambda x: (-(x["total"] or 0), x["nm"]))
    comprar.sort(key=lambda x: (-x["q"], x["nm"]))
    cache["_duais_plano"] = {
        "nomes": nomes, "regra": REGRA_DUAL, "alvo_fora": DUAIS_ALVO_FORA,
        "linhas": linhas, "vender": vender, "comprar": comprar,
        "por_sublote": por_sublote, "totais": tot}
    return cache["_duais_plano"]


# ---------------------------------------------------------------------------
# R4: a Reserved List que ele JOGA
# ---------------------------------------------------------------------------
# Os formatos que ele joga, nas palavras dele. Vive no config para não ser uma
# lista de código a discordar das caixas que ele tem.
FORMATOS_QUE_JOGA = ("premodern", "cedh", "duel-commander", "pauper",
                     "standard", "pioneer", "modern", "legacy")


def formatos_que_joga(cfg: dict | None = None) -> tuple[str, ...]:
    """`fases.formatos_jogados` do config, ou os formatos das próprias caixas.

    A omissão é o que as CAIXAS dizem — ele joga o que tem em caixa — e não uma
    lista escrita no código: uma caixa nova de um formato novo passava a ter a
    RL dela desprotegida sem ninguém dar por isso.
    """
    v = (sources.config() if cfg is None else cfg).get("fases") or {}
    lista = v.get("formatos_jogados")
    if isinstance(lista, list) and lista:
        return tuple(str(x).lower() for x in lista)
    das_caixas = tuple(dict.fromkeys(
        (c.get("formato") or "").lower() for c in _caixas.do_config(cfg)
        if c.get("formato")))
    return das_caixas or FORMATOS_QUE_JOGA


def rl_que_joga(con, res: dict, cfg: dict | None = None,
                cache: dict | None = None) -> dict[str, str]:
    """`nome -> porque é que ele joga esta carta de RL`. É a R4.

    *"Protege-se o RL que ele joga; o que não joga vai à venda."* São quatro
    caminhos, e cada nome guarda o PRIMEIRO que o apanhou — é o que aparece no
    motivo da exclusão:

      (a) está dentro de um deck (`copy_allocation`) cujo `estado` protege;
      (b) uma caixa do loadout pede-a (é a lista do deck, montado ou por montar);
      (c) está numa lista da tabela `decks`/`deck_cards` que uma CAIXA DELE
          referencia (`caixas[].ref`);
      (d) está no consenso por comandante (núcleo + flex) de um comandante que
          ele tem em caixa.

    **O (c) passou a olhar só para as listas que uma caixa dele referencia
    (2026-10-02), e isto era um defeito a sério.** Varria a tabela `decks`
    inteira e filtrava pelo FORMATO: na base desse dia isso protegia Reserved
    List por aparecer no *Jeskai Lessons*, no *4c Control*, no *Cori-Steel
    Cutter*, no *Legacy (Harry1232)* ou no *Enchantress (consenso)* — listas de
    metagame e de jogadores vigiados que **não são decks dele**. A pergunta é
    *"o RL que ELE joga"*, e quem responde é a lista de caixas: um deck que
    saiu do config deixa de proteger no mesmo dia, sem ninguém ter de limpar
    uma linha da base.
    """
    cache = {} if cache is None else cache
    if "_rl_joga" in cache:
        return cache["_rl_joga"]
    est = estados(cfg)
    fmts = set(formatos_que_joga(cfg))
    out: dict[str, str] = {}

    # (a) dentro de um deck cujo estado protege
    nomes_caixa = {s["slot"]: s.get("nome") or s["slot"] for s in res["slots"]}
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            slot = lot.get("caixa")
            if slot and protege(est.get(slot, ESTADO_OMISSAO)):
                out.setdefault(nm, f"está no deck {nomes_caixa.get(slot, slot)}")
                break

    # (b) pedida por uma caixa do loadout
    for s in res["slots"]:
        if (s.get("formato") or "").lower() not in fmts:
            continue
        for _b, nm, _q in (s.get("cards") or []):
            out.setdefault(nm, f"está na lista de {s.get('nome') or s['slot']}")

    # (c) numa lista da tabela `decks` QUE UMA CAIXA DELE REFERENCIA
    refs = {str(s.get("ref")) for s in res["slots"] if s.get("ref")}
    if refs:
        marks = ",".join("?" for _ in refs)
        for r in con.execute(
                f"""SELECT DISTINCT dc.card_name nm, d.name dn, d.format f
                      FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id
                     WHERE d.name IN ({marks})""", sorted(refs)):
            if (r["f"] or "").lower() in fmts:
                out.setdefault(r["nm"].split(" // ")[0],
                               f"está no consenso de {r['dn']}")

    # (d) o consenso por COMANDANTE (2026-10-01). Só núcleo + flex: o `raro`
    # (<40 %) é uma carta que apareceu numa lista, e proteger por isso era a
    # mesma avalanche que o limiar da reserva existe para travar.
    for cmd, quem in _comandantes_das_caixas(con, res, cfg).items():
        try:
            c = _consenso_comandante(con, cmd)
        except sqlite3.Error:
            continue
        for carta in c.get("cartas") or []:
            if carta["papel"] in ("nucleo", "flex"):
                out.setdefault(carta["nm"],
                               f"está no consenso de {cmd} ({quem})")
    cache["_rl_joga"] = out
    return out


# ---------------------------------------------------------------------------
# O consenso de cada deck — a matéria-prima da reserva (R5)
# ---------------------------------------------------------------------------
def _consenso_comandante(con, comandante: str, fmt: str | None = None) -> dict:
    from . import consenso as _cons                          # noqa: PLC0415
    return _cons.consenso(con, comandante, fmt)


def _comandantes_conhecidos(con, fmt: str, cache: dict | None = None) -> set[str]:
    """Os comandantes que a base conhece naquele formato (`decklists.commander`).

    É por aqui que se DERIVA o comandante de uma caixa, em vez de o escrever à
    mão: cruza-se a lista da caixa com este conjunto.
    """
    cache = {} if cache is None else cache
    k = f"_cmds_{fmt}"
    if k not in cache:
        cache[k] = {r["c"] for r in con.execute(
            "SELECT DISTINCT commander c FROM decklists "
            " WHERE format = ? AND commander IS NOT NULL", (fmt,))}
    return cache[k]


def comandante_do_deck(con, s: dict, cache: dict | None = None) -> str | None:
    """Qual é o comandante desta caixa.

    Por esta ordem, e a ordem é o que torna isto correcto:

      1. **`caixas[].comandante`** — a excepção explícita;
      2. **`consenso_comandante.comandante`** do config, quando o formato da
         caixa é o daquele bloco. É o comandante que ELE pediu
         (*"comandante CLOUD"*, 2026-10-01) e é o que a página do consenso já
         abre: não é uma inferência, é uma escolha dele que já estava escrita;
      3. só então a INTERSECÇÃO da lista da caixa com os comandantes que a base
         conhece naquele formato (`decklists.commander`), desempatada primeiro
         por o nome aparecer no NOME da caixa e só depois por nº de listas.

    **Porque é que o (2) teve de passar à frente do (3):** medido a 2026-10-01, a
    caixa *Cloud (Duel Commander)* resolvia para **Phelia, Exuberant Shepherd**.
    A lista padrão dela (fixada a 2026-09-20) **não inclui o próprio
    comandante** — a Cloud aparece como carta de RESERVA, a 89 % —, e a Phelia
    está na lista e é ela própria um comandante com 37 listas. O desempate por
    «mais listas» escolhia-a, e a reserva do deck de Duel Commander dele saía do
    consenso de outro deck. Nenhum passo dava erro: é o padrão do `event_tier`
    sobre a única parte da ordem que nomeia um deck.
    """
    if s.get("comandante"):
        return str(s["comandante"])
    fmt = (s.get("formato") or "").lower()
    from . import consenso as _cons                          # noqa: PLC0415
    r = _cons.regras()
    if fmt and fmt == str(r.get("formato") or "").lower() and r.get("comandante"):
        return str(r["comandante"])
    conhecidos = _comandantes_conhecidos(con, fmt, cache)
    if not conhecidos:
        return None
    nomes = [nm for _b, nm, _q in (s.get("cards") or [])]
    candidatos = [n for n in nomes if n in conhecidos]
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]
    nome_caixa = (s.get("nome") or "").lower()
    marks = ",".join("?" for _ in candidatos)
    quantas = {x["c"]: x["n"] for x in con.execute(
        f"""SELECT commander c, COUNT(*) n FROM decklists
             WHERE format = ? AND commander IN ({marks}) GROUP BY commander""",
        (fmt, *candidatos))}
    candidatos.sort(key=lambda n: (
        # Primeiro quem se chama como a caixa: *"Cloud (Duel Commander)"* é a
        # Cloud, mesmo que a Phelia tenha mais listas no formato.
        0 if n.split(",")[0].lower() in nome_caixa else 1,
        -quantas.get(n, 0), n))
    return candidatos[0]


def _comandantes_das_caixas(con, res: dict, cfg: dict | None = None
                            ) -> dict[str, str]:
    """`comandante -> nome da caixa`, para as caixas de formato de comandante."""
    cache: dict = {}
    out: dict[str, str] = {}
    for s in res["slots"]:
        cmd = comandante_do_deck(con, s, cache)
        if cmd:
            out.setdefault(cmd, s.get("nome") or s["slot"])
    return out


# A JANELA DA R5: *"30 dias a rolar"*. A base só guarda ~30 dias de listas
# (`daily.prune_decklists`), por isso na prática a janela é tudo o que lá está —
# mas escreve-se de propósito: no dia em que a poda mudar, a regra não muda.
JANELA_DIAS = 30


def desde_de(dias: int | None = None, hoje: str | None = None) -> str:
    """A data a partir da qual uma lista conta para a R5 (`AAAA-MM-DD`)."""
    from datetime import timedelta                           # noqa: PLC0415
    d = JANELA_DIAS if dias is None else int(dias)
    base = date.fromisoformat(hoje) if hoje else date.today()
    return (base - timedelta(days=d)).isoformat()


def _listas_por_assinatura(con, fmt: str, assinatura: list[str],
                           todas: bool = False,
                           desde: str | None = None,
                           sem: list[str] | None = None) -> list[int]:
    """Os ids das listas deste arquétipo na janela da R5.

    Quem escolhe é o `sources.ids_por_assinatura`, partilhado com a lista da
    caixa (`loadout._cards_from_consensus`) — a pergunta *"que listas são deste
    deck?"* é a mesma, e dois selectores ao lado discordam em silêncio.

    **`so_que_contam=False`**, e é uma excepção deliberada ao filtro do site:
    ver o cabeçalho e o `sources.ids_por_assinatura`. Aqui sub-contar é vender
    uma carta que ele precisa, e no Pauper e no cEDH o filtro dá ZERO de
    propósito (`metagame_fontes.*.tiers = []`).
    """
    return sources.ids_por_assinatura(con, fmt, assinatura, todas=todas,
                                      desde=desde, so_que_contam=False, sem=sem)


# Quantas cartas distintivas entram numa assinatura derivada, e o mínimo de
# listas em que cada uma tem de aparecer para não ser ruído de uma lista só.
ASSINATURA_N = 3
ASSINATURA_MIN = 3


def assinatura_derivada(con, s: dict, cache: dict | None = None) -> list[str]:
    """A assinatura DERIVADA da própria lista da caixa: as cartas dela que são
    mais raras no formato.

    Muitas caixas não têm `assinatura` escrita — a do Modern e a do Pioneer vêm
    de uma lista seguida, não de um arquétipo. Em vez de lhes pedir uma lista à
    mão (e de a escrever de memória, que é o que a ordem proíbe), deriva-se:
    conta-se em quantas listas do formato aparece cada carta DELA e ficam as
    mais RARAS que ainda assim apareçam em pelo menos `ASSINATURA_MIN` listas.
    Uma carta rara é distintiva; uma Lightning Bolt não diz nada sobre o deck.

    É a mesma ideia do `assinatura` escrito à mão, calculada em vez de ditada —
    e tem a mesma semântica (`IN`: basta uma) do `_cards_from_consensus`. As
    básicas ficam fora: não distinguem nada.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    fmt = (s.get("formato") or "").lower()
    nomes = [nm for b, nm, _q in (s.get("cards") or [])
             if b == "main" and nm not in loadout.BASICS]
    if not nomes:
        return []
    k = f"_freq_{fmt}"
    if k not in cache:
        # `consenso=False`: ESTA FREQUÊNCIA SERVE A RESERVA, que tem a janela
        # dela (2026-10-03). A pergunta aqui é *"quão rara é esta carta no
        # formato"*, e é com ela que se deriva a assinatura de uma caixa que não
        # tem uma escrita. Com o corte do consenso (cinco dias) as contagens
        # caíam abaixo do `ASSINATURA_MIN` (3) e a assinatura derivada
        # desaparecia — a caixa ficava com a reserva só manual, sem um único
        # erro e sem ninguém mexer na R5. É o mesmo princípio do
        # `so_que_contam=False` do `_listas_por_assinatura`: sub-contar aqui é
        # vender uma carta que ele precisa.
        conta, cp = sources.counting_sql(fmt, "d", consenso=False)
        freq: dict[str, int] = {}
        for r in con.execute(
                f"""SELECT dc.card_name nm, COUNT(DISTINCT d.id) n
                      FROM decklists d JOIN decklist_cards dc
                        ON dc.decklist_id = d.id
                     WHERE d.format = ? AND {conta} GROUP BY dc.card_name""",
                (fmt, *cp)):
            freq[r["nm"].split(" // ")[0]] = r["n"]
        cache[k] = freq
    freq = cache[k]
    candidatas = [(freq.get(nm, 0), nm) for nm in nomes
                  if freq.get(nm, 0) >= ASSINATURA_MIN]
    candidatas.sort()
    return [nm for _n, nm in candidatas[:ASSINATURA_N]]


def assinatura_do_deck(s: dict) -> tuple[list[str], bool, list[str]]:
    """`(cartas, em conjunção?, cartas que NÃO podem estar)` — a CARTA-ASSINATURA
    escrita desta caixa.

    `reserva_assinatura` ganha ao `assinatura` de propósito: uma caixa cuja
    LISTA vem de outra fonte (a do Luffy, a lista padrão fixada, o link do
    cEDH) continua a ter identidade de arquétipo para a R5 sem lhe mexer na
    lista. É a separação que a ordem de 2026-10-02 pede: a assinatura é a
    IDENTIDADE, não a lista.

    A terceira metade é a NEGAÇÃO (`assinatura_sem` / `reserva_assinatura_sem`),
    e é o que separa o UW Replenish da Enchantress: as 124 listas dela jogam
    todas `Replenish`. Ver `sources.ids_por_assinatura`.
    """
    usa_reserva = bool(s.get("reserva_assinatura"))
    cartas = [str(x) for x in (s.get("reserva_assinatura")
                               or s.get("assinatura") or [])]
    todas = bool(s.get("reserva_assinatura_todas") if usa_reserva
                 else s.get("assinatura_todas"))
    sem = [str(x) for x in ((s.get("reserva_assinatura_sem") if usa_reserva
                             else s.get("assinatura_sem")) or [])]
    return cartas, todas, sem


def _listas_do_deck(con, s: dict, cache: dict | None = None,
                    desde: str | None = None) -> tuple[list[int], str, str]:
    """`(ids, nota, origem)` — as listas que formam o consenso DESTA caixa.

    Dois caminhos, por esta ordem: a CARTA-ASSINATURA escrita (a identidade do
    deck — `reserva_assinatura` ou o `assinatura` da caixa de consenso) e, não
    havendo, a DERIVADA da própria lista. Quando nem isso dá, diz-se que não há
    consenso em vez de se inventar um — é o caso do *Artifacts Blue*, que ainda
    está **à espera da carta-assinatura** que ele vai dizer.
    """
    fmt = (s.get("formato") or "").lower()
    escrita, todas, sem = assinatura_do_deck(s)
    if escrita:
        ids = _listas_por_assinatura(con, fmt, escrita, todas, desde, sem)
        return (ids, f"{len(ids)} listas com "
                     f"{sources.texto_assinatura(escrita, todas, sem)}", "assinatura")
    derivada = assinatura_derivada(con, s, cache)
    if derivada:
        ids = _listas_por_assinatura(con, fmt, derivada, False, desde)
        return (ids, f"{len(ids)} listas pelas cartas mais distintivas da lista "
                     f"({', '.join(derivada)})", "derivada")
    return [], ("à espera da carta-assinatura — sem ela não há consenso e a "
                "reserva fica só manual"), ""


def consenso_do_deck(con, s: dict, cache: dict | None = None,
                     desde: str | None = None) -> dict:
    """`{fonte, listas, cartas: [{nm, pct, copias, board}], nota}` para uma caixa.

    Duas fontes, e a primeira é a que a ordem manda para o Duel Commander:

      * **por COMANDANTE** (`mtgvault/consenso.py`, 2026-10-01) quando a caixa
        tem um comandante derivável — é o deck de Duel Commander dele;
      * **por CARTA-ASSINATURA** para as outras, com a percentagem por carta.

    Sem nenhuma das duas devolve-se `cartas: []` e a nota a dizer porquê. É uma
    resposta: a reserva daquele deck passa a ser só o que ele escrever à mão.

    `desde` é a janela da R5 (30 dias). O caminho do COMANDANTE não a aplica: o
    `consenso.consenso` tem o seu próprio universo (o `counting_sql` do Duel
    Commander, que já conta ligas e presenciais sem mínimo) e é a página de
    consenso por comandante que manda nele — *"fica como está"*, ordem dele.
    """
    cache = {} if cache is None else cache
    cmd = comandante_do_deck(con, s, cache)
    if cmd:
        c = _consenso_comandante(con, cmd, (s.get("formato") or "").lower())
        cartas = [{"nm": x["nm"], "pct": x["pct"], "copias": x["copias"],
                   "board": "main"} for x in c["cartas"]]
        return {"fonte": "comandante", "comandante": cmd,
                "listas": c["listas"], "cartas": cartas,
                "suficiente": c["suficiente"],
                "nota": (f"consenso de {c['listas']} listas de {cmd}"
                         if c["listas"] else f"{cmd}: ainda sem listas")}
    ids, nota, origem = _listas_do_deck(con, s, cache, desde)
    if not ids:
        return {"fonte": None, "listas": 0, "cartas": [], "suficiente": False,
                "nota": nota}
    em: dict[tuple[str, str], int] = defaultdict(int)
    qts: dict[tuple[str, str], dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for i in range(0, len(ids), 400):
        ch = ids[i:i + 400]
        ph = ",".join("?" for _ in ch)
        for r in con.execute(
                f"""SELECT card_name nm, quantity q, board b
                      FROM decklist_cards WHERE decklist_id IN ({ph})""", ch):
            k = ("side" if r["b"] == "side" else "main", r["nm"].split(" // ")[0])
            em[k] += 1
            qts[k][r["q"]] += 1
    n = len(ids)
    cartas = [{"nm": nm, "board": b, "pct": round(100 * c / n, 1),
               "copias": max(qts[(b, nm)].items(), key=lambda x: (x[1], x[0]))[0]}
              for (b, nm), c in em.items()]
    cartas.sort(key=lambda x: (-x["pct"], x["nm"]))
    # COMO É QUE A FONTE CHAMA A ESTE DECK (2026-10-02). A identidade continua a
    # ser a CARTA-ASSINATURA — é a regra de ouro dele e é ela que escolheu estas
    # listas —, mas o nome que o mtgtop8 lhes dá é a maneira de CONFERIR que a
    # assinatura apanhou o deck certo e não dois decks a fingir que são um. Foi
    # exactamente o que aconteceu com o «Replenish»: a assinatura apanhava 186
    # listas, das quais 124 são Enchantress. Sai na página da arrumação.
    votado = nomes.nome_das_listas(con, ids)
    return {"fonte": origem, "listas": n, "cartas": cartas,
            "suficiente": n >= MIN_LISTAS_RESERVA, "nota": nota,
            "nome_fonte": (votado or {}).get("nome"),
            "nome_votos": (votado or {}).get("votos", 0),
            "nome_segundo": (votado or {}).get("segundo")}


# ---------------------------------------------------------------------------
# R5: a reserva («maybe») de cada deck — o que foi JOGADO nos últimos 30 dias
# ---------------------------------------------------------------------------
# O LIMIAR DE 20 % FOI APAGADO (André, 2026-10-02, à letra: *"esta substitui o
# limiar de 20 % que eu pus ontem — APAGA o limiar"*). O travão passou a ser a
# JANELA: só conta o que foi jogado no último mês. Se voltar a fazer falta um
# limiar, o sítio é este — mas não se deixa uma chave morta no config a dizer
# que existe uma regra que não existe (é o padrão do `event_tier`).
CURVA_OMISSAO = (10, 20, 30, 40, 50)
# ABAIXO DISTO NÃO SE CHAMA CONSENSO A NADA, e não é um requinte: é a ordem
# dele sobre o *Ill-Gotten Gains* — *"SÓ 3 listas, abaixo do mínimo de 8. Marca-o
# como SEM CONSENSO SUFICIENTE e deixa a lista manual; não inventes consenso com
# 3 listas."* Medido a 2026-10-01, com 3 listas uma carta que aparece numa só
# vale 33 %, e a reserva dessa caixa sozinha segurava 52 cópias / 6 879 €. É o
# mesmo mínimo do `consenso.MIN_LISTAS`.
MIN_LISTAS_RESERVA = 8
NOTA_SEM_CONSENSO = "SEM CONSENSO SUFICIENTE"


def regras_reserva(cfg: dict | None = None) -> dict:
    """`colecao_config.json → reserva`, com as omissões."""
    v = (sources.config() if cfg is None else cfg).get("reserva") or {}
    r = {"janela_dias": JANELA_DIAS, "curva": list(CURVA_OMISSAO),
         "staples_premodern_pct": STAPLES_CORTE_OMISSAO}
    r.update({k: x for k, x in v.items() if not str(k).startswith("_")})
    return r


def janela_dias(cfg: dict | None = None) -> int:
    return int(regras_reserva(cfg)["janela_dias"])


def _retiradas(s: dict) -> dict[str, str]:
    """`carta -> data em que ele carregou em «não é necessária»`.

    `caixas[].reserva_fora` aceita as DUAS formas: a lista de nomes de
    2026-10-01 e a lista de objectos `{nm, em}` de 2026-10-02 (que leva a DATA,
    como ele pediu). A antiga continua a valer sem data — um ficheiro escrito
    ontem não pode perder a recusa por causa de um campo novo.
    """
    out: dict[str, str] = {}
    for x in s.get("reserva_fora") or []:
        if isinstance(x, dict):
            if x.get("nm"):
                out[str(x["nm"])] = str(x.get("em") or "")
        elif str(x).strip():
            out[str(x)] = ""
    return out


def reserva_do_deck(con, s: dict, _ignorado=None,
                    cache: dict | None = None,
                    desde: str | None = None) -> dict:
    """A reserva («maybe») de uma caixa: o que foi JOGADO no último mês e não
    está nas 75 de hoje.

    `{automatica, manual, retiradas, final, nota, listas, fonte, desde}` — cada
    carta com `pct` (em quantas listas da janela apareceu) e quantas ele TEM. A
    reserva protege **só o que ele tem**; o que não tem fica marcado `tem: 0` e
    alimenta a lista de compras que o loadout já faz, como a ordem diz.

    Três partes, e as três se vêem na página:
      * `automatica` — TODA a carta que apareceu numa lista do arquétipo nos
        últimos 30 dias (main **ou** side) e que não está na lista de hoje.
        *"Mesmo que esteja hoje fora da lista"* — é a ordem dele, e é por isso
        que não há limiar nenhum;
      * `manual` — `caixas[].reserva`, o que ele acrescentou à mão (a chave já
        existia desde 2026-09-20 e continua a querer dizer o mesmo);
      * `retiradas` — `caixas[].reserva_fora`: o que ele tirou no botão **«não é
        necessária»**, com a DATA. Guarda-se o que ele tirou, e não a lista
        final, para a reserva continuar a crescer com as listas novas sem lhe
        devolver o que ele já recusou.
    """
    cache = {} if cache is None else cache
    desde = desde or desde_de(janela_dias())
    c = consenso_do_deck(con, s, cache, desde)
    nas_75 = {nm for _b, nm, _q in (s.get("cards") or [])}
    fora = _retiradas(s)
    manual = [str(x) for x in (s.get("reserva") or [])]
    # SEM AMOSTRA NÃO HÁ RESERVA AUTOMÁTICA (ver `MIN_LISTAS_RESERVA`). O que
    # ele escreveu à mão fica: isso é uma decisão dele, não uma inferência.
    # As BÁSICAS ficam fora da reserva: nunca vão à venda (o `sell_list` salta-as
    # à cabeça), por isso protegê-las não protege nada e só enchia a lista que ele
    # tem de ler — o consenso do Modern punha lá *"Plains, 27,8 %"*.
    from . import loadout                                    # noqa: PLC0415
    automatica = ([x for x in c["cartas"]
                   if x["nm"] not in nas_75 and x["nm"] not in fora
                   and x["nm"] not in loadout.BASICS]
                  if c["suficiente"] else [])
    pct = {x["nm"]: x["pct"] for x in c["cartas"]}
    posse = _posse(con, cache)
    nomes_finais = list(dict.fromkeys([x["nm"] for x in automatica]
                                      + [m for m in manual if m not in nas_75]))
    final = [{"nm": nm, "pct": pct.get(nm),
              "manual": nm in manual, "tem": posse.get(nm, 0)}
             for nm in nomes_finais]
    final.sort(key=lambda x: (-(x["pct"] or 0), x["nm"]))
    nota = c["nota"]
    # *"À espera da carta-assinatura"* só se ele não tiver dado NENHUMA
    # identidade. Uma caixa que segue um LINK (os dois de cEDH, ordem dele:
    # *"como já está, não mudes"*) não está à espera de nada — o que lhe falta é
    # metagame no vault, e isso é uma decisão de 2026-09-07
    # (`metagame_fontes.cedh.tiers = []`), não um campo em branco. Dizer-lhe o
    # contrário era marcar como incompleto o que está decidido.
    if not c["listas"] and not assinatura_do_deck(s)[0] and \
            (s.get("fonte") or "") in ("vigiado", "escolhido"):
        nota = (f"a lista vem de fora ({s.get('fonte')}: {s.get('ref') or '—'}) "
                f"e o formato {s.get('formato')} não tem metagame no vault — a "
                f"reserva fica só o que escreveres à mão.")
    if c["listas"] and not c["suficiente"]:
        nota = (f"{NOTA_SEM_CONSENSO}: {c['nota']} — são menos de "
                f"{MIN_LISTAS_RESERVA}, por isso a reserva automática desta "
                f"caixa está vazia e fica só o que escreveres à mão.")
    return {"slot": s.get("slot"), "nome": s.get("nome") or s.get("slot"),
            "automatica": automatica, "manual": manual,
            "retiradas": [{"nm": nm, "em": em} for nm, em in sorted(fora.items())],
            "final": final, "desde": desde, "janela_dias": janela_dias(),
            "listas": c["listas"], "fonte": c["fonte"],
            "suficiente": c["suficiente"], "nota": nota,
            "comandante": c.get("comandante") or "",
            "assinatura": sources.texto_assinatura(*assinatura_do_deck(s)),
            # Como é que a FONTE chama a estas listas (2026-10-02) — ver
            # `consenso_do_deck`. É a conferência da assinatura, à vista.
            "nome_fonte": c.get("nome_fonte"),
            "nome_votos": c.get("nome_votos", 0),
            "nome_segundo": c.get("nome_segundo"),
            "tem": sum(1 for x in final if x["tem"]),
            "sem": sum(1 for x in final if not x["tem"])}


def _posse(con, cache: dict | None = None) -> dict[str, int]:
    cache = {} if cache is None else cache
    if "_posse" not in cache:
        from . import paginas                                # noqa: PLC0415
        cache["_posse"] = paginas.posse_total(con)
    return cache["_posse"]


def reservas(con, res: dict, _ignorado=None,
             cache: dict | None = None) -> dict[str, list[str]]:
    """`nome de carta -> [caixas que a reservam]`. É a R5, pronta a proteger.

    Só os nomes que ele TEM entram: a reserva protege o que está na estante, e
    uma carta que ele não tem não precisa de protecção nenhuma.
    """
    cache = {} if cache is None else cache
    if "_reservas" in cache:
        return cache["_reservas"]
    posse = _posse(con, cache)
    out: dict[str, list[str]] = defaultdict(list)
    for s in res["slots"]:
        r = reserva_do_deck(con, s, None, cache)
        for x in r["final"]:
            if posse.get(x["nm"]):
                out[x["nm"]].append(r["nome"])
    cache["_reservas"] = dict(out)
    return cache["_reservas"]


# ---------------------------------------------------------------------------
# R5b: as STAPLES DE SIDEBOARD do Premodern (só deste formato)
# ---------------------------------------------------------------------------
# Palavras dele: *"SÓ PARA PREMODERN: além disso, protege as STAPLES DE
# SIDEBOARD DO FORMATO — depois de a decklist fechar o Premodern não mexe muito,
# mas convém ter no sideboard as cartas que são staples. Define-as pela taxa de
# presença em sideboards de TODAS as listas de Premodern dos últimos 30 dias,
# põe o corte num sítio configurável, e MEDE A CURVA."*
#
# O CORTE É PROVISÓRIO ATÉ ELE ESCOLHER. A ordem é explícita — *"não fixes o
# corte sem lhe mostrar a curva"* —, por isso o valor que aqui está é o que
# PROTEGE MAIS (o mais baixo da curva) e a página/relatório dizem-no. Medido a
# 2026-10-02 sobre as 987 listas de Premodern da janela (todas com sideboard):
# corte 10 % -> 25 cartas, 20 % -> 7, 30 % -> 1 (Tormod's Crypt), 50 % -> 0.
# Acima dos 20 % isto deixa de proteger coisa nenhuma, e um corte que não
# protege nada é uma regra a fingir.
STAPLES_CORTE_OMISSAO = 10
STAPLES_FORMATO = "premodern"


def staples_corte(cfg: dict | None = None) -> float:
    return float(regras_reserva(cfg)["staples_premodern_pct"])


def staples_sideboard(con, fmt: str = STAPLES_FORMATO, corte: float | None = None,
                      desde: str | None = None, cache: dict | None = None) -> dict:
    """`{nomes: {carta: pct}, corte, listas, todas: [(pct, nm)], …}`.

    A taxa é sobre as listas do formato **que têm sideboard** na janela, e não
    sobre todas: dividir por listas sem sideboard dava uma percentagem a doer
    por um dado que não existe. Na base de 2026-10-02 as 987 listas de Premodern
    têm todas sideboard, por isso hoje dá o mesmo — mas a conta tem de estar
    certa no dia em que não der.
    """
    cache = {} if cache is None else cache
    corte = staples_corte() if corte is None else float(corte)
    desde = desde or desde_de(janela_dias())
    k = f"_staples_{fmt}_{desde}"
    if k not in cache:
        ids = [r[0] for r in con.execute(
            "SELECT id FROM decklists WHERE format = ? AND event_date >= ?",
            (fmt, desde))]
        com_side: set[int] = set()
        cnt: dict[str, int] = defaultdict(int)
        for i in range(0, len(ids), 400):
            ch = ids[i:i + 400]
            ph = ",".join("?" for _ in ch)
            for r in con.execute(
                    f"""SELECT decklist_id d, card_name nm FROM decklist_cards
                         WHERE decklist_id IN ({ph}) AND board = 'side'""", ch):
                com_side.add(r["d"])
                cnt[r["nm"].split(" // ")[0]] += 1
        n = len(com_side)
        todas = sorted(((round(100.0 * c / n, 1), nm) for nm, c in cnt.items()
                        ), reverse=True) if n else []
        cache[k] = {"listas": len(ids), "com_sideboard": n, "todas": todas}
    base = cache[k]
    nomes = {nm: pct for pct, nm in base["todas"] if pct >= corte}
    return {"formato": fmt, "corte": corte, "desde": desde,
            "listas": base["listas"], "com_sideboard": base["com_sideboard"],
            "todas": base["todas"], "nomes": nomes, "n": len(nomes),
            "provisorio": corte == STAPLES_CORTE_OMISSAO,
            "regra": (f"presença em sideboards de TODAS as listas de {fmt} desde "
                      f"{desde} (denominador: as que têm sideboard), corte em "
                      f"{corte:g} % — `reserva.staples_premodern_pct`")}


def curva_staples(con, res: dict, cortes=None,
                  cache: dict | None = None) -> list[dict]:
    """A CURVA que ele pediu para o corte das staples de Premodern.

    *"MEDE A CURVA (10/20/30/40/50 %) em cópias e valor para ele escolher com
    números à frente."*

    Dá DOIS números por corte, e os dois são precisos para ele escolher:

      * **`a_mais`** — o que a R5b protege por cima de tudo o resto. É o efeito
        REAL de mexer no corte hoje, e medido a 2026-10-02 é quase zero (3
        cópias / 2,64 €): a R5 (jogada nos últimos 30 dias) já apanha
        praticamente todas as staples de sideboard do formato, porque uma staple
        de sideboard é, por definição, uma carta que apareceu numa lista.
      * **`sozinha`** — o que o corte protegeria se a R5 não existisse. É o que
        diz quanto a regra VALE, e é por isso que não se mostra só o primeiro
        número: uma curva plana podia ser lida como *"as staples não importam"*,
        quando o que se passa é que outra regra chegou lá primeiro.

    Em cada um sai também `so_premodern`: as cópias **PT da era** (o material
    que as caixas de Premodern dele aceitam) — é o sub-conjunto que serve mesmo
    para pôr num sideboard de Premodern.
    """
    cache = {} if cache is None else cache
    cortes = list(cortes or regras_reserva()["curva"])
    base = candidatos(con, res, cache=cache, com_r5b=False)
    so = candidatos(con, res, cache=cache, com_r5=False, com_r5b=False)

    def _idx(c):
        d: dict[str, list[dict]] = defaultdict(list)
        for l in c["linhas"]:
            d[l["nm"]].append(l)
        return d

    livres, livres_so = _idx(base), _idx(so)

    def _conta(nomes, idx):
        cop = val = cop_pm = val_pm = 0
        cartas = 0
        for nm in nomes:
            ls = idx.get(nm) or []
            if ls:
                cartas += 1
            for l in ls:
                cop += l["q"]
                val += l["total"] or 0
                if l["lang"] == "pt" and l.get("era_premodern"):
                    cop_pm += l["q"]
                    val_pm += l["total"] or 0
        return {"cartas": cartas, "copias": cop, "valor": round(val, 2),
                "so_premodern": {"copias": cop_pm, "valor": round(val_pm, 2)}}

    out = []
    for corte in cortes:
        st = staples_sideboard(con, corte=corte, cache=cache)
        out.append({"corte": corte, "cartas_staple": st["n"],
                    "a_mais": _conta(st["nomes"], livres),
                    "sozinha": _conta(st["nomes"], livres_so),
                    "candidatos_antes": base["copias"],
                    "valor_antes": base["valor"]})
    return out


# ---------------------------------------------------------------------------
# AS REGRAS APLICADAS: a Fase 3 e a lista VENDER
# ---------------------------------------------------------------------------
def _motivo(prot: str, detalhe: str) -> str:
    """O motivo em português, com a regra à frente. Sem isto havia exclusão
    silenciosa — e a regra dele é explícita: *"cada cópia excluída da venda
    guarda o MOTIVO em português, e qual das regras a apanhou"*."""
    return f"{ROTULOS[prot]}: {detalhe}"


def contexto(con, res: dict, cfg: dict | None = None,
             cache: dict | None = None, com_r5: bool = True,
             com_r5b: bool = True) -> dict:
    """Tudo o que o `quem_protege` precisa de saber, calculado UMA vez.

    É o mesmo dicionário para a Fase 3 e para o motor da venda: duas montagens
    ao lado davam duas respostas à mesma pergunta, que é o defeito que as duas
    moradas desta regra existem para não ter.
    """
    cache = {} if cache is None else cache
    dp = plano_duais(con, res, cfg, cache)
    return {
        "duais": set(dp["nomes"]),
        "duais_sublote": dp["por_sublote"],
        # O ORÇAMENTO de cópias LIVRES por sub-lote, FRESCO a cada chamada: o
        # `quem_protege` gasta-o à medida que as linhas passam, e partilhá-lo
        # entre a Fase 3 e o motor da venda deixava o segundo a ver o orçamento
        # já gasto pelo primeiro.
        "duais_livre": {k: v["q"] - v["prot"] for k, v in dp["por_sublote"].items()},
        "duais_alvo": dp["alvo_fora"],
        "terras": terras_protegidas(con, cache),
        "rl_joga": rl_que_joga(con, res, cfg, cache),
        "estados": estados(cfg),
        "nomes": {s["slot"]: s.get("nome") or s["slot"] for s in res["slots"]},
        "reservas": reservas(con, res, None, cache) if com_r5 else {},
        "staples": (staples_sideboard(con, cache=cache)["nomes"]
                    if com_r5b else {}),
        "fmt_staples": {s["slot"]: (s.get("formato") or "").lower()
                        for s in res["slots"]},
    }


def quem_protege(con, res: dict, nm: str, lot: dict, ctx: dict) -> tuple | None:
    """`(regra, motivo, quantas cópias)` se esta cópia está protegida, senão
    `None`. O terceiro valor é quantas das `lot["q"]` ficam protegidas — só a R1
    devolve menos do que todas.

    A ORDEM conta para o motivo: a razão que se escreve é a que SOBREVIVE. Uma
    shockland dentro de um deck montado é apanhada pela R2, porque é a R2 que a
    protege *"sem excepções"* — se amanhã o deck se desmontar, continua
    protegida.

    **A R1 é a primeira e é exclusiva** para as dez duais: ele disse *"para elas
    manda a R1, que é mais específica"*. Logo, numa dual, só a RD (está num
    deck) e a R1 (está dentro das quatro de fora) protegem — a R4 não a salva
    por ser Reserved List, e é esse o ponto da regra.
    """
    q = int(lot.get("q") or 0)
    if nm in ctx["duais"]:
        slot = lot.get("caixa")
        if slot and protege(ctx["estados"].get(slot, ESTADO_OMISSAO)):
            return RD, _motivo(RD, f"dual original dentro do deck "
                                   f"{ctx['nomes'].get(slot, slot)}"), q
        # O ORÇAMENTO: desta linha ficam à venda, no máximo, as cópias livres que
        # ainda sobram do sub-lote; o resto está dentro das quatro e protege-se.
        k = (lot.get("id"), slot or "")
        if k not in ctx["duais_sublote"]:
            return None
        livre = ctx["duais_livre"].get(k, 0)
        n = max(0, q - livre)
        ctx["duais_livre"][k] = max(0, livre - (q - n))
        if n <= 0:
            return None
        return R1, _motivo(R1, f"queres ter {ctx['duais_alvo']} de cada fora dos "
                               f"decks — esta está dentro dessas "
                               f"{ctx['duais_alvo']}"), n
    terra = ctx["terras"].get(nm)
    if terra:
        regra = R2 if terra == "shockland" else R3
        return regra, _motivo(regra, f"{terra} — todas as cópias ficam "
                                     f"protegidas, sem excepções"), q
    if lot.get("rl") and nm in ctx["rl_joga"]:
        return R4, _motivo(R4, f"Reserved List que jogas — {ctx['rl_joga'][nm]}"), q
    slot = lot.get("caixa")
    if slot:
        e = ctx["estados"].get(slot, ESTADO_OMISSAO)
        if protege(e):
            nome = ctx["nomes"].get(slot, slot)
            return RD, _motivo(RD, f"está no deck {nome}, que está {e}"), q
    if ctx.get("reservas") and nm in ctx["reservas"]:
        quem = ", ".join(ctx["reservas"][nm])
        return R5, _motivo(R5, f"jogada nos últimos {janela_dias()} dias em "
                               f"{quem} — podes precisar dela a seguir"), q
    pct = (ctx.get("staples") or {}).get(nm)
    if pct is not None:
        return R5B, _motivo(R5B, f"staple de sideboard de Premodern — está em "
                                 f"{pct:g} % dos sideboards do último mês"), q
    return None


def _partir(linha: dict, n: int) -> tuple[dict, dict | None]:
    """A linha com `n` cópias e o que sobra. É o que a R1 obriga a saber fazer:
    um lote de cinco duais fora dos decks tem quatro protegidas e uma candidata,
    e dar o lote inteiro a um dos lados era mentir por quatro ou por uma.

    O `copias` (os `copy_id` que o botão «vendida» usa) parte-se com a
    quantidade; o `total` recalcula-se do `unit`, nunca por regra de três.
    """
    def com(q):
        d = dict(linha, q=q)
        if "total" in linha:
            d["total"] = round((linha.get("unit") or 0) * q, 2)
        if isinstance(linha.get("copias"), list):
            d["copias"] = [[linha["copias"][0][0], q]] if linha["copias"] else []
        return d
    q = int(linha.get("q") or 0)
    if n >= q:
        return com(q), None
    return com(n), com(q - n)


def candidatos(con, res: dict, cfg: dict | None = None,
               cache: dict | None = None, _ignorado=None,
               com_r5: bool = True, com_r5b: bool = True) -> dict:
    """A FASE 3 e a lista **VENDER**: o que sobra depois das regras.

    Varre a colecção INTEIRA (o `pool` do relatório, uma linha por sub-lote) e
    devolve `{linhas, protegidas, por_proteccao, copias, valor, …}`. Cada linha
    é uma cópia física com o preço de referência; cada exclusão traz
    `proteccao` e `motivo`. *"Tudo o que não se enquadrar nestas regras vai para
    uma lista única chamada VENDER."*

    **Só leitura**: não toca na base, nas alocações nem no config.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    ctx = contexto(con, res, cfg, cache, com_r5=com_r5, com_r5b=com_r5b)
    pc: dict = cache.setdefault("_precos", {})
    linhas, protegidas = [], []
    por: dict[str, dict] = {p: {"copias": 0, "valor": 0.0, "cartas": set()}
                            for p in PROTECCOES}
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            if lot["q"] <= 0:
                continue
            p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc, lot=lot)
            linha = {
                "nm": nm, "copy_id": lot["id"], "q": lot["q"],
                "sid": lot["sid"], "set": (lot["set_code"] or "").upper(),
                "set_name": lot["set_name"], "lang": (lot["lang"] or "en"),
                "finish": lot["finish"], "foil": loadout.e_foil(lot["finish"]),
                "cond": lot.get("cond") or "NM", "rl": bool(lot["rl"]),
                "local": lot["local"], "caixa": lot.get("caixa"),
                "validado": lot.get("validado") or "",
                # Serve a curva da R5b: uma staple só entra num sideboard de
                # Premodern se for PT e da era. O `era_pm` vem do `lots()` — não
                # se recalcula aqui a data do Scourge, que é a mesma pergunta.
                "era_premodern": bool(lot.get("era_pm")),
                "unit": p["unit"], "preco_fonte": p["fonte"],
                "preco_origem": p["origem"],
                "total": round((p["unit"] or 0) * lot["q"], 2),
            }
            qp = quem_protege(con, res, nm, lot, ctx)
            if qp is None:
                linhas.append(linha)
                continue
            prot, motivo, n = qp
            prote, resto = _partir(linha, n)
            protegidas.append(dict(prote, proteccao=prot, motivo=motivo))
            por[prot]["copias"] += prote["q"]
            por[prot]["valor"] += prote["total"]
            por[prot]["cartas"].add(nm)
            if resto:
                linhas.append(resto)
    linhas.sort(key=lambda l: (-(l["total"] or 0), l["nm"], l["copy_id"]))
    protegidas.sort(key=lambda l: (-(l["total"] or 0), l["nm"], l["copy_id"]))
    return {
        "linhas": linhas,
        "copias": sum(l["q"] for l in linhas),
        "cartas": len({l["nm"] for l in linhas}),
        "valor": round(sum(l["total"] or 0 for l in linhas), 2),
        "sem_preco": sum(l["q"] for l in linhas if l["unit"] is None),
        "protegidas": protegidas,
        "protegidas_copias": sum(l["q"] for l in protegidas),
        "protegidas_valor": round(sum(l["total"] or 0 for l in protegidas), 2),
        "por_proteccao": {p: {"copias": v["copias"],
                              "valor": round(v["valor"], 2),
                              "cartas": len(v["cartas"]),
                              "rotulo": ROTULOS[p]}
                          for p, v in por.items()},
        "janela_dias": janela_dias(cfg),
        "staples_corte": staples_corte(cfg),
        "com_r5": com_r5, "com_r5b": com_r5b,
    }


def filtrar_venda(con, res: dict, venda: list[dict], venda_rl: list[dict],
                  cfg: dict | None = None, cache: dict | None = None
                  ) -> tuple[list[dict], list[dict], list[dict]]:
    """O MOTOR: tira de `venda`/`venda_rl` o que as regras seguram.

    Devolve `(venda, venda_rl, protegidas)`. Entra no `loadout.sell_list` no
    fim, como o filtro da reserva das caixas de 2026-09-20 — e pela mesma razão
    de desenho: a regra é sobre a CÓPIA, não sobre o motivo por que ela foi
    parar à lista. Uma protecção que só valesse na página das Fases não era uma
    protecção: a aba Vender e a exportação continuariam a oferecer a carta.

    Aqui não se varre a colecção: trabalha-se sobre as linhas já formadas, e
    cada linha traz as `copias` (os `copy_id`) de que é feita. A R1 pode PARTIR
    uma linha — quatro cópias protegidas, as outras à venda —, e é por isso que
    o `quem_protege` devolve uma quantidade e não um sim/não.
    """
    cache = {} if cache is None else cache
    ctx = contexto(con, res, cfg, cache)
    protegidas: list[dict] = []

    def passa(rows):
        ficam = []
        for r in rows:
            # A caixa vem da LINHA (`linha_de` carimba-a do sub-lote). Não se
            # procura pelo `copy_id`: um lote de 4 com 3 na caixa e 1 na gaveta
            # são dois sub-lotes com o mesmo `copies.id`, e pelo id a parte da
            # gaveta ficava protegida pela RD — uma cópia a desaparecer da venda
            # sem motivo. Apanhado pelo `test_paginas_loadout`.
            lot = {"rl": r.get("rl"), "caixa": r.get("caixa"), "q": r.get("q"),
                   "id": (r["copias"][0][0] if r.get("copias") else None)}
            qp = quem_protege(con, res, r["nm"], lot, ctx)
            if qp is None:
                ficam.append(r)
                continue
            prot, motivo, n = qp
            prote, resto = _partir(r, n)
            protegidas.append(dict(prote, proteccao=prot, motivo=motivo,
                                   porque_venderia=r.get("reason") or "",
                                   reason=motivo))
            if resto:
                ficam.append(resto)
        return ficam

    return passa(venda), passa(venda_rl), protegidas


# ---------------------------------------------------------------------------
# A TRAVA: o RC Ghent é a 9-11/10 (André, 2026-10-01)
# ---------------------------------------------------------------------------
CONGELADO_ATE_OMISSAO = "2026-10-12"


class VendaCongelada(ValueError):
    """Pediu-se uma saída de venda antes de `venda.congelado_ate`.

    É `ValueError` como a `webapp.VendaDesligada`, para o `do_POST` a traduzir
    num 409 com a frase em português — e para quem já apanhava `ValueError` não
    mudar de comportamento.
    """

    def __init__(self, ate: str, hoje: str):
        self.ate, self.hoje = ate, hoje
        super().__init__(motivo_congelado(ate, hoje))


def congelado_ate(cfg: dict | None = None) -> str:
    """`colecao_config.json → venda.congelado_ate`. Vazio/ausente = sem trava."""
    from . import loadout                                    # noqa: PLC0415
    b = loadout.regras_venda() if cfg is None else (cfg.get("venda") or {})
    v = b.get("congelado_ate") if isinstance(b, dict) else None
    return "" if v in (None, "", False) else str(v)


def motivo_congelado(ate: str, hoje: str) -> str:
    return (f"a venda está CONGELADA até {ate} (colecao_config.json → "
            f"venda.congelado_ate; hoje é {hoje}). Ele joga o RC Ghent de "
            "Modern a 9-11/10 e nenhuma carta pode sair numa lista de stock "
            "antes disso. Nada se perdeu: a lista volta a gerar-se sozinha a "
            f"partir de {ate}.")


def venda_congelada(cfg: dict | None = None, hoje: str | None = None) -> bool:
    ate = congelado_ate(cfg)
    if not ate:
        return False
    return (hoje or date.today().isoformat()) < ate


def exige_descongelado(cfg: dict | None = None, hoje: str | None = None) -> None:
    """Levanta `VendaCongelada` se ainda não chegou a data. Chamam-na as DUAS
    portas de saída: o `venda.exportar` (logo o `daily` e o CLI) e os endpoints
    de escrita do `webapp.py`."""
    ate = congelado_ate(cfg)
    hoje = hoje or date.today().isoformat()
    if ate and hoje < ate:
        raise VendaCongelada(ate, hoje)


# ---------------------------------------------------------------------------
# AS FILAS DE FOTOS (Fase 2 e Fase 4)
# ---------------------------------------------------------------------------
# A UNIDADE DA FILA É A FOTO, e uma foto leva no máximo QUATRO CARTAS (André,
# 2026-10-01, à letra: *"organiza o Blue farm e CDEH por tipo de carta e ate 4
# cartas por foto"*, *"se sao 4 fotos, e 1 foto com as 4 cartas"*).
#
# Esteve aqui escrito o contrário — *"a fila conta CÓPIAS FÍSICAS: um playset dá
# quatro linhas"* (o `_explode`) —, e dava **quatro fotos** a um playset. A regra
# e o agrupamento vivem num sítio só, o `mtgvault/fotos.py`, porque a mesma
# pergunta («quantas cartas cabem numa foto?») é feita também pela conciliação
# do import, que recusa a foto que traga mais do que quatro.
LOTE = 50                                  # fotos por lote na Fase 4


def _filas_por_lotes(fotos_: list[dict], lote: int = LOTE) -> list[dict]:
    """Parte a fila em lotes de `lote` FOTOS, com a barra de cada um."""
    out = []
    for i in range(0, len(fotos_), lote):
        ch = fotos_[i:i + lote]
        out.append({
            "n": i // lote + 1, "de": i + 1, "ate": i + len(ch),
            "fotos": len(ch), "cartas": sum(f["cartas"] for f in ch),
            "valor": round(sum(f["valor"] for f in ch), 2),
            "feitas": sum(1 for f in ch if f["feita"]),
            "linhas": ch,
        })
    return out


# ---------------------------------------------------------------------------
# A ORDEM DE TRABALHO: primeiro os decks de LISTA ÚNICA (André, 2026-10-01)
# ---------------------------------------------------------------------------
# *"Começa pelos decks que são LISTA ÚNICA e não são «de conversão» — os dois de
# cEDH (Blue Farm e Cloud cEDH), que têm cartas dedicadas e uma lista cada. A
# família de Premodern partilha o mesmo conjunto de cartas e monta-se por
# conversão de uma noutra: fica para depois."*
#
# A base não tem uma coluna «de conversão», e não se inventa uma: DERIVA-SE,
# e a regra é esta — **o grupo de formato da caixa tem um tecto de playset
# contado sobre o GRUPO INTEIRO (`regras_por_formato[].playset_maximo`) e há
# duas ou mais caixas nesse grupo**. Esse tecto só existe porque as caixas
# trocam a carta entre si: é a decisão de 2026-09-08 (*"afinal só vou ter até
# playset de cada carta"*), e o `prioridade_por: "pct"` do mesmo grupo
# confirma-o (a ordem entre elas é pela percentagem, o que só faz sentido quando
# competem). Está ESCRITO no config — não é um palpite.
#
# O que NÃO serve para derivar isto, e foi medido antes de se escolher: a
# SOBREPOSIÇÃO das listas. Na base de 2026-10-01 o Blue Farm e o Cloud cEDH
# partilham 24 nomes (26 % do menor), **mais** do que a maior sobreposição entre
# duas caixas de Premodern (Oath × Enchantress, 32 %, e a média é ~20 %). Pela
# sobreposição, o cEDH era «de conversão» e parte do Premodern não — ao
# contrário do que ele disse.
NOTA_CONVERSAO = (
    "Fica para depois: estas caixas são do mesmo grupo de formato e ordenam-se "
    "por % completo — partilham o mesmo conjunto de cartas e montam-se por "
    "conversão de uma noutra. Primeiro os decks de lista única.")
NOTA_LISTA_UNICA = ("Lista única e cartas dedicadas: é por aqui que se começa.")


def de_conversao(res: dict, cfg: dict | None = None) -> dict[str, bool]:
    """`slot -> é «de conversão»?` Ver a nota acima para a regra derivada.

    **O SINAL MUDOU A 2026-10-02 e a resposta é a mesma.** Era o `playset_maximo`
    do grupo (*"o tecto só existe porque as caixas trocam a carta entre si"*) — e
    nesse dia o André mandou esquecer o tecto de playset do Premodern, o que
    deixava esta derivação a ler uma chave que já não existe e a responder
    «nenhuma caixa é de conversão», em silêncio. O sinal passou a ser o
    `prioridade_por: "pct"` do mesmo grupo, que o CLAUDE.md já dava como
    confirmação do outro: ordenar as caixas pela percentagem só faz sentido
    quando elas competem pelas MESMAS cartas. Hoje apanha exactamente as 6
    caixas de Premodern, como antes — medido.
    """
    from . import loadout                                    # noqa: PLC0415
    regras = (cfg or {}).get("regras_por_formato")
    if not isinstance(regras, list) or not regras:
        regras = loadout.regras_por_formato()
    partilham = {r.get("grupo") or "" for r in regras
                 if str(r.get("prioridade_por") or "").lower() == "pct"}
    quantas: dict[str, int] = defaultdict(int)
    for s in res.get("slots") or []:
        quantas[s.get("grupo") or s.get("formato") or ""] += 1
    return {s["slot"]: bool((s.get("grupo") or "") in partilham
                            and quantas[s.get("grupo") or ""] > 1)
            for s in res.get("slots") or []}


def _linha_de_lote(con, nm: str, lot: dict, pc: dict, perdidas: dict) -> dict:
    from . import loadout                                    # noqa: PLC0415
    p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc, lot=lot)
    return {"nm": nm, "copy_id": lot["id"], "q": lot["q"],
            "set": (lot["set_code"] or "").upper(),
            "lang": (lot["lang"] or "en"), "finish": lot["finish"],
            "foil": loadout.e_foil(lot["finish"]),
            "cond": lot.get("cond") or "NM",
            "validado": lot.get("validado") or "",
            "foto_perdida": lot["id"] in perdidas,
            "local": lot.get("local") or "", "unit": p["unit"],
            "total": round((p["unit"] or 0) * lot["q"], 2)}


def fila_decks(con, res: dict, cfg: dict | None = None,
               cache: dict | None = None) -> dict:
    """A FASE 2: as cartas dos decks em `montado`, em FOTOS de até 4 cartas.

    Uma fila POR DECK (é assim que ele vai à estante: tira a caixa, fotografa o
    que lá está), **agrupada por TIPO de carta** — a ordem que ele deu hoje
    («planeswalkers, criaturas, artefactos, encantamentos, instantâneos,
    feitiços, terras»), e não a ordem por COR do painel Montar: ali ele procura
    cartas num binder arrumado por cor, aqui dispõe na mesa o que já tem na mão.

    Os decks de LISTA ÚNICA vêm primeiro e os «de conversão» no fim, com a
    razão escrita (`de_conversao`).
    """
    from . import fotos as fotos_mod, paginas                # noqa: PLC0415
    cache = {} if cache is None else cache
    est = estados(cfg)
    pc: dict = cache.setdefault("_precos", {})
    perdidas = _perdidas(con, cache)
    por_slot: dict[str, list[dict]] = defaultdict(list)
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            slot = lot.get("caixa")
            # As caixas cujo ESTADO protege (`permanente`/`montada`/`congelada`)
            # — são os decks que ficam, e é deles que ele tem de confirmar o
            # conteúdo antes de Ghent. Uma `candidata` não entra: não é um deck
            # que ele vá levar.
            if not slot or not protege(est.get(slot, ESTADO_OMISSAO)):
                continue
            por_slot[slot].append(_linha_de_lote(con, nm, lot, pc, perdidas))
    nomes = {s["slot"]: s.get("nome") or s["slot"] for s in res["slots"]}
    conv = de_conversao(res, cfg)
    tipos = paginas.tipos(con, [l["nm"] for ls in por_slot.values() for l in ls])
    filas = []
    for slot, ls in por_slot.items():
        fs = fotos_mod.agrupar(ls, tipos=tipos, prefixo=f"{slot}-")
        filas.append({"slot": slot, "nome": nomes.get(slot, slot),
                      "conversao": bool(conv.get(slot)),
                      "nota": (NOTA_CONVERSAO if conv.get(slot)
                               else NOTA_LISTA_UNICA),
                      "barra": fotos_mod.barra(fs), "fotos": fs,
                      "lotes": _filas_por_lotes(fs)})
    # Lista única primeiro; depois a que tem mais fotos por tirar; o nome
    # desempata. A ordem de TRABALHO é a ordem dele, não a do alfabeto.
    filas.sort(key=lambda f: (f["conversao"], -f["barra"]["falta"], f["nome"]))
    todas = [x for f in filas for x in f["fotos"]]
    return {"filas": filas, "barra": fotos_mod.barra(todas),
            "decks": len(filas),
            "conversao": sum(1 for f in filas if f["conversao"]),
            "max_cartas": fotos_mod.MAX_CARTAS}


def fila_candidatos(con, res: dict, cfg: dict | None = None,
                    cache: dict | None = None, cands: dict | None = None) -> dict:
    """A FASE 4: as fotos dos candidatos, **por CARTA, da mais cara para a mais
    barata** — escolha dele, e não por caixa.

    Também em fotos de até 4 cartas, mas sem agrupar por tipo: aqui a ordem é o
    preço, e agrupar por tipo era trocar a ordem que ele pediu. As cópias da
    mesma carta continuam juntas (a ordenação é por valor e depois por nome, e o
    lote inteiro é uma linha só). As que **não têm foto no disco** vêm à cabeça.
    """
    from . import fotos as fotos_mod                         # noqa: PLC0415
    cache = {} if cache is None else cache
    c = cands if cands is not None else candidatos(con, res, cfg, cache)
    perdidas = _perdidas(con, cache)
    linhas = [dict(l, foto_perdida=l["copy_id"] in perdidas) for l in c["linhas"]]
    # A foto perdida primeiro (é a única cópia sem prova nenhuma), depois pelo
    # preço DA CÓPIA, decrescente — *"por carta, da mais cara para a mais
    # barata"*. É o `unit` e não o `total` da linha: um lote de 6 Dark Ritual a
    # 37 € soma mais do que uma Taiga de 84 €, e ordenar pelo total punha o
    # barato à frente do caro, que é o contrário do que ele pediu.
    linhas.sort(key=lambda l: (not l["foto_perdida"], -(l["unit"] or 0),
                               l["nm"], l["copy_id"]))
    fs = fotos_mod.agrupar(linhas, por_tipo=False, prefixo="f4-")
    return {"fotos": fs, "barra": fotos_mod.barra(fs),
            "lotes": _filas_por_lotes(fs), "lote": LOTE,
            "max_cartas": fotos_mod.MAX_CARTAS}


def fila_inventario(con, res: dict, cfg: dict | None = None,
                    cache: dict | None = None) -> dict:
    """A VIA PARALELA: fotos da RL, das shocklands e das fetchlands.

    *"Nunca bloqueia nada e aparece como tal na página — é inventário, não é
    passo da venda."* Por isso vive à parte das quatro fases e não entra em
    percentagem nenhuma delas.
    """
    from . import fotos as fotos_mod                         # noqa: PLC0415
    cache = {} if cache is None else cache
    terras = terras_protegidas(con, cache)
    pc: dict = cache.setdefault("_precos", {})
    perdidas = _perdidas(con, cache)
    grupos: dict[str, list[dict]] = {"rl": [], "shockland": [], "fetchland": []}
    for nm, lotes in (res.get("pool") or {}).items():
        qual = terras.get(nm) or ("rl" if any(l["rl"] for l in lotes) else None)
        if not qual:
            continue
        for lot in lotes:
            grupos[qual].append(_linha_de_lote(con, nm, lot, pc, perdidas))
    out = []
    for chave, titulo in (("rl", "Reserved List"), ("shockland", "ShockLands"),
                          ("fetchland", "FetchLands")):
        ls = sorted(grupos[chave],
                    key=lambda l: (not l["foto_perdida"], -(l["unit"] or 0),
                                   l["nm"], l["copy_id"]))
        fs = fotos_mod.agrupar(ls, por_tipo=False, prefixo=f"inv-{chave}-")
        out.append({"chave": chave, "titulo": titulo,
                    "barra": fotos_mod.barra(fs), "fotos": fs,
                    "lotes": _filas_por_lotes(fs)})
    todas = [x for g in out for x in g["fotos"]]
    return {"grupos": out, "barra": fotos_mod.barra(todas),
            "max_cartas": fotos_mod.MAX_CARTAS,
            "nota": ("É inventário, não é um passo da venda: nunca bloqueia "
                     "nenhuma fase.")}


# ---------------------------------------------------------------------------
# AS FOTOS PERDIDAS: as únicas cópias sem prova nenhuma
# ---------------------------------------------------------------------------
def _fotos_mod():
    from . import fotos as fotos_mod                         # noqa: PLC0415
    return fotos_mod


def _perdidas(con, cache: dict | None = None) -> dict[int, str]:
    from . import fotos as fotos_mod                         # noqa: PLC0415
    cache = {} if cache is None else cache
    if "_perdidas" not in cache:
        cache["_perdidas"] = fotos_mod.copias_sem_foto_no_disco(con)
    return cache["_perdidas"]


def fotos_perdidas(con, res: dict, cfg: dict | None = None,
                   cache: dict | None = None) -> dict:
    """As cópias cujo `photo_path` já não tem ficheiro no disco.

    Medido na base de 2026-10-01: **33 fotos, 155 linhas da `copies`**. Não se
    inventa a foto nem se limpa o campo — o campo é a prova de que ela existiu.
    São as únicas cópias que hoje não têm prova nenhuma, e por isso vão à cabeça
    da fila de revalidação e têm bloco próprio na página.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    perdidas = _perdidas(con, cache)
    pc: dict = cache.setdefault("_precos", {})
    # A lista sai da `copies` e NÃO do `res["pool"]`: um lote sai do `lots()`
    # PARTIDO por sítio (um lote de 4 com 3 na caixa e 1 na gaveta são duas
    # linhas com o mesmo `copies.id`) e contá-lo pelo pool dava a mesma cópia
    # duas vezes. Aqui a pergunta é sobre a LINHA da base, não sobre a caixa.
    linhas = []
    if perdidas:
        marks = ",".join("?" * len(perdidas))
        for r in con.execute(
                f"""SELECT cp.id, cp.quantity q, cp.photo_path, cp.language lang,
                           cp.finish, COALESCE(cp.condition,'NM') cond,
                           cp.condition_origem cond_origem, cp.verso_path verso,
                           c.name nm, c.scryfall_id sid, c.set_code,
                           c.collector_number num,
                           (SELECT slot FROM copy_allocation a WHERE a.copy_id = cp.id
                             ORDER BY quantity DESC LIMIT 1) slot
                      FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                     WHERE cp.id IN ({marks})""", sorted(perdidas)):
            nm = (r["nm"] or "").split(" // ", 1)[0]
            p = loadout.preco_da_copia(con, r["sid"], r["finish"], nm, pc, lot=dict(r))
            linhas.append({
                "nm": nm, "copy_id": r["id"], "q": r["q"],
                "set": (r["set_code"] or "").upper(), "num": r["num"] or "",
                "lang": r["lang"] or "en", "finish": r["finish"],
                "foil": loadout.e_foil(r["finish"]), "cond": r["cond"],
                "caixa": r["slot"] or "", "foto": r["photo_path"],
                "unit": p["unit"], "total": round((p["unit"] or 0) * r["q"], 2)})
    linhas.sort(key=lambda l: (-(l["total"] or 0), l["nm"], l["copy_id"]))
    return {"fotos": sorted({l["foto"] for l in linhas}),
            "n_fotos": len({l["foto"] for l in linhas}),
            "copias": sum(l["q"] for l in linhas), "linhas": linhas,
            "valor": round(sum(l["total"] or 0 for l in linhas), 2),
            "nota": ("A foto destas cópias já não está no disco. Não se "
                     "inventa nem se limpa o campo: são as únicas cópias sem "
                     "prova nenhuma, e por isso são as primeiras a fotografar.")}


# ---------------------------------------------------------------------------
# O pacote que a página e o CLI consomem
# ---------------------------------------------------------------------------
def decks_para_decidir(con, res: dict, cfg: dict | None = None,
                       cache: dict | None = None) -> list[dict]:
    """A FASE 1: os 16 decks que ficam, o ESTADO de cada um, a CARTA-ASSINATURA
    por que se identifica, e o que se libertava se ele o passasse a candidato.

    `liberta` é quantas cópias e quanto valor deixariam de estar protegidas pela
    RD — contado com as outras regras a valer, que é a única conta honesta: uma
    shockland dentro do deck continua protegida pela R2 e não se liberta.

    **Não há botões aqui** (2026-10-02): o estado muda-se na Deckboxes, que é
    onde esse gesto já vive e onde ele tem a caixa na mão. Dois caminhos para o
    mesmo gesto discordam um dia qualquer, em silêncio.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    est = estados(cfg)
    terras = terras_protegidas(con, cache)
    duais_nm = set(duais(con, cache)["nomes"])
    rl_joga = rl_que_joga(con, res, cfg, cache)
    pc: dict = cache.setdefault("_precos", {})
    datas = loadout.datas_de_arrumacao(con)
    por_slot: dict[str, dict] = {}
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            slot = lot.get("caixa")
            if not slot:
                continue
            d = por_slot.setdefault(slot, {"copias": 0, "valor": 0.0,
                                           "liberta_copias": 0,
                                           "liberta_valor": 0.0})
            p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc, lot=lot)
            v = (p["unit"] or 0) * lot["q"]
            d["copias"] += lot["q"]
            d["valor"] += v
            # O que SE LIBERTA: o que as outras regras não seguram. As duais
            # ficam de fora da conta porque a regra delas é a quota de quatro
            # FORA dos decks — tirá-las do deck não as põe à venda, põe-nas na
            # fila da quota.
            if nm in terras or nm in duais_nm or (lot["rl"] and nm in rl_joga):
                continue
            d["liberta_copias"] += lot["q"]
            d["liberta_valor"] += v
    out = []
    for s in res["slots"]:
        slot = s["slot"]
        d = por_slot.get(slot) or {"copias": 0, "valor": 0.0,
                                   "liberta_copias": 0, "liberta_valor": 0.0}
        r = reserva_do_deck(con, s, None, cache)
        e = est.get(slot, ESTADO_OMISSAO)
        ass, todas, sem = assinatura_do_deck(s)
        # A IDENTIDADE de um deck, e as três formas honestas de a ter. Isto é
        # apresentação, mas é apresentação que não pode mentir: dizer *"à espera
        # da carta-assinatura"* aos dois decks de cEDH (que seguem um LINK, por
        # ordem dele — *"como já está, não mudes"*) e ao de Duel Commander (cuja
        # identidade é o COMANDANTE, 2026-10-01) era marcar como incompleto o que
        # está decidido. *"À espera"* é só quem não tem nenhuma das três — hoje o
        # Artifacts Blue, e é exactamente o que a ordem manda assinalar.
        ident, tipo = sources.texto_assinatura(ass, todas, sem), "carta"
        if not ident and r.get("fonte") == "comandante":
            ident, tipo = str(r.get("comandante") or ""), "comandante"
        if not ident and (s.get("fonte") or "") in ("vigiado", "escolhido"):
            ident = f"lista fixa ({s.get('fonte')}: {s.get('ref') or '—'})"
            tipo = "lista"
        out.append({
            "slot": slot, "nome": s.get("nome") or slot,
            "formato": s.get("formato"), "estado": e,
            "estado_explicito": bool(_caixa_tem_estado(cfg, slot)),
            "protege": protege(e), "texto_estado": TEXTO_ESTADO.get(e, ""),
            "fonte": s.get("fonte"), "ref": s.get("ref"),
            "identidade": ident, "identidade_tipo": tipo if ident else "",
            "sem_assinatura": not ident,
            "assinatura": sources.texto_assinatura(ass, todas, sem),
            "assinatura_cartas": ass, "assinatura_todas": todas,
            "assinatura_sem": sem,
            # O nome que o mtgtop8 dá às listas que esta assinatura apanhou
            # (2026-10-02): é como se confere que ela apanhou UM deck e não dois.
            "nome_fonte": r.get("nome_fonte"),
            "nome_votos": r.get("nome_votos", 0),
            "nome_segundo": r.get("nome_segundo"),
            "lista": {"main": sum(q for b, _n, q in (s.get("cards") or [])
                                  if b == "main"),
                      "side": sum(q for b, _n, q in (s.get("cards") or [])
                                  if b == "side"),
                      "nota": s.get("nota_lista") or s.get("lista_nota") or ""},
            "pct": s.get("pct"), "tem": s.get("tem"), "pede": s.get("pede"),
            "na_caixa": d["copias"],
            "valor": round(d["valor"], 2),
            "montada_em": datas.get(slot),
            "liberta": {"copias": d["liberta_copias"],
                        "valor": round(d["liberta_valor"], 2)},
            "reserva": r,
        })
    out.sort(key=lambda x: (-x["valor"], x["nome"]))
    return out


def _caixa_tem_estado(cfg: dict | None, slot: str) -> bool:
    """Se o `estado` está ESCRITO no config (e não só assumido).

    A página mostra a diferença: *«sem estado escrito (vale permanente, e por
    isso protege)»* não é o mesmo que ele ter escolhido — e esconder isso era
    dar por tomada uma decisão que ninguém tomou.
    """
    for c in _caixas.do_config(cfg):
        if c.get("slot") == slot:
            return str(c.get("estado") or "").strip().lower() in _caixas.ESTADOS
    return False


def relatorio(con, res: dict, cfg: dict | None = None,
              hoje: str | None = None, curva: bool = False,
              cache: dict | None = None) -> dict:
    """Tudo o que a página das Fases e o `cli fases` mostram, numa chamada.

    O `cache` é o da CORRIDA e pode vir de fora (2026-10-03): o bloco do ESTADO da
    mesma página precisa do mesmo mapa de preços e das mesmas listas de terras, e
    construí-los outra vez custava 3,3 s — ver `estado._mapa`. Quem não o passa
    continua a ter um fresco, como sempre.
    """
    cache = {} if cache is None else cache
    hoje = hoje or date.today().isoformat()
    cands = candidatos(con, res, cfg, cache)
    out = {
        "hoje": hoje,
        "congelado_ate": congelado_ate(cfg),
        "congelada": venda_congelada(cfg, hoje),
        "motivo_congelado": (motivo_congelado(congelado_ate(cfg), hoje)
                             if venda_congelada(cfg, hoje) else ""),
        "janela_dias": janela_dias(cfg),
        "desde": desde_de(janela_dias(cfg), hoje),
        "terras": {"duais": duais(con, cache),
                   "shocklands": shocklands(con, cache),
                   "fetchlands": fetchlands(con, cache)},
        "duais": plano_duais(con, res, cfg, cache),
        "staples": staples_sideboard(con, cache=cache),
        "decks": decks_para_decidir(con, res, cfg, cache),
        "fase2": fila_decks(con, res, cfg, cache),
        "candidatos": cands,
        "fase4": fila_candidatos(con, res, cfg, cache, cands),
        "inventario": fila_inventario(con, res, cfg, cache),
        # As únicas cópias sem prova nenhuma: vêm à cabeça de tudo.
        "perdidas": fotos_perdidas(con, res, cfg, cache),
        "max_cartas_foto": _fotos_mod().MAX_CARTAS,
        "estados": {"valores": list(_caixas.ESTADOS),
                    "protegem": list(ESTADOS_PROTEGEM),
                    "omissao": ESTADO_OMISSAO, "texto": dict(TEXTO_ESTADO)},
        "regras": {k: ROTULOS[k] for k in PROTECCOES},
    }
    if curva:
        out["curva_staples"] = curva_staples(con, res, None, cache)
    return out
