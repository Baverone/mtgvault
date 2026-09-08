"""Loadout: os decks que ficam montados em deckboxes, e o que sobra para vender.

O André (2026-09-07): *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."*

O LOADOUT é a lista de decks que estão montados AO MESMO TEMPO. Está em
`colecao_config.json -> caixas` (era `loadout` até à v6, 2026-09-08 — ver
`mtgvault.caixas`): uma caixa por deck, cada uma com a fonte da sua lista
(`vigiado` / `deck` / `consenso` / `escolhido` / `manual`), o balde onde as
cartas vivem, o `estado`, a prioridade e as restrições de material. Desde a v6 a
CAIXA é a única noção de deck do vault — *"temos decks vigiados e deckbox que é a
mesma coisa"* —, e o `caixas.para_slot` traduz as duas formas (v5 e v6) para a
interna, que é a que este módulo consome. Por isso a unificação não mexeu num
único número da alocação.

O que este módulo faz é ALOCAR exemplares físicos aos slots. Não é uma soma de
coberturas independentes: uma cópia física só entra numa caixa de cada vez, por
isso a alocação é global e por ordem de prioridade. Daí saírem quatro coisas que
uma cobertura por deck nunca dá:

  * **noutra caixa** — a carta existe e serve, mas está alocada a outra caixa.
    Não é falta: é ir buscá-la;
  * **cartas partilhadas** — duas caixas querem a mesma carta e não há cópias
    para as duas (era o que se chamava "conflito");
  * **substituto** — a cópia existe mas não serve àquela caixa (é EN num deck de
    Premodern, é nonfoil num deck que ele quer todo em foil);
  * **venda** — o que sobra depois de alocar tudo e de guardar o backup.

ONDE ESTÁ A CARTA (André, 2026-09-07)
-------------------------------------
*"Vamos fazer como no riftvault: indicas onde está a carta, para, se eu quiser ir
jogar, saber onde ir buscar e não ter que comprar múltiplos para todos. Caso eu
compre, depois indico (meto foto) e vais ajustando."*

Por isso uma carta que a alocação deu a OUTRA caixa não conta como falta: fica em
`noutra` ({caixa: quantas}) e **não entra na wantlist nem no custo de fechar**.
Só é compra o que não existe em lado nenhum, ou o que existe mas não serve na
língua/acabamento exigidos. Cada caixa passa a ter dois números: `comprar` (o que
falta comprar) e `noutra` (o que é ir buscar a outra caixa). O que se compra
entra pelas fotos (`pendentes/`) e a alocação recalcula-se no `daily.py`.

E a segunda metade da mesma regra: as cartas que ele AINDA VAI COMPRAR partilham-
se exactamente da mesma maneira. Somar as faltas caixa a caixa pedia 5 Swords to
Plowshares PT quando 2 chegam e o Lion's Eye Diamond duas vezes. Quem faz essa
conta é o `partilhar_compras`, depois da alocação toda.

DUAS REGRAS DE MATERIAL, ditadas pelo André no mesmo dia
--------------------------------------------------------
1. *"Para Premodern as cartas são das edições que tínhamos visto e em Português;
   essas cartas NÃO entram para outros formatos!!"* — uma cópia PT de uma
   impressão da era Premodern (até ao Scourge, 2003-05-26) fica TRANCADA ao
   Premodern. E, do outro lado, um slot de Premodern só fecha com cópias PT: uma
   EN aparece como substituto ("serve mas não é PT"), não como slot fechado.
2. *"Standard, Pioneer, Modern e Legacy: as cartas são todas Foil (menos as
   Reserved List)"* — nesses slots só contam `foil`/`etched`; uma carta da
   Reserved List (`catalog.cards.reserved`) pode ser nonfoil. Uma nonfoil de uma
   carta não-RL NÃO fecha o slot: fica como substituto ("tenho em nonfoil").

A tranca de PT tem uma excepção que os dados obrigam a ter: as cópias que vivem
no BALDE de outro slot do loadout já são desse deck (o Blue Farm tem um Lotus
Petal e um Tarnished Citadel PT de 1997/2001 dentro da caixa dele). Trancá-las
ao Premodern desmontaria um deck que está montado — por isso o balde manda.

E o outro lado da mesma regra, em duas versões — a segunda corrigiu a primeira
no mesmo dia. Começou por ser *"O Premodern não é para olhar para a minha Caixa
RL, pois o Premodern só vai usar as cartas em Português; na Caixa RL só estão
cartas RL em inglês"*, e passou a *"na Caixa RL, as PT e as ENG estão
separadas"*. Ou seja: a Caixa Reserved List são, fisicamente, DUAS caixas, e a
premissa "só estão lá cartas em inglês" já não vale. O que fica:

  * uma caixa de Premodern VÊ os baldes `Premodern (geral)`, `SPML` e
    `Caixa Reserved List` (mais o seu próprio) — o resto da colecção está dentro
    da caixa de outro deck montado, e de lá não se tira;
  * e, em qualquer deles, só vê as cópias **PT**. *"O Premodern só usa em PT,
    mesmo eu tendo a carta em inglês."* Uma EN não fecha o slot, não aparece como
    substituto e não é protegida pela saída `guardar`: para uma caixa de
    Premodern a carta é FALTA, compra-se em PT.

É mais forte do que a regra da língua do `_porque_nao`, e é de propósito: um
substituto diz "tens a carta, decide se abres excepção", e aqui ele já decidiu
que não abre. `local()` mostra por isso `Caixa RL (PT)` / `Caixa RL (EN)` — a
mesma prateleira do config, as duas caixas que ele tem à frente.

AS REGRAS PASSARAM A SER POR GRUPO DE FORMATO (André, 2026-09-07, mais tarde)
----------------------------------------------------------------------------
As duas regras acima eram as duas primeiras de cinco. Ele completou-as no mesmo
dia, e com elas veio a ordem da alocação:

  *"Premodern apenas as edições da era Premodern e em Português; cEDH apenas
  inglês non-foil; Duel Commander apenas foil; SPML (Standard/Pioneer/Modern/
  Legacy) tudo foil e inglês (RL pode ser non-foil); Pauper tudo foil se houver
  disponível, senão pode ser non-foil."*
  *"Ordem de prioridade na alocação: Premodern > cEDH > Duel Commander > Pauper
  > SPML."*
  *"Os decks vigiados têm prioridade para ficarem com as cartas, desde que
  respeitem as regras."*
  *"Para Pauper, utilizas as cartas que forem necessárias do SPML e agregas ao
  Pauper."*

Está tudo em `REGRAS_FORMATO` (ou `colecao_config.json -> regras_por_formato`),
uma lista cuja ORDEM é a ordem da alocação. O `prioridade` de cada slot deixou de
ser o número que manda: manda o grupo, depois "é deck vigiado?", e só então o
`prioridade` do config, como desempate DENTRO do grupo. O `resolve_slots`
reescreve `prioridade` com a posição global que daí sai (o config fica em
`prioridade_config`), para quem lê o campo continuar a ler a ordem verdadeira.

Uma consequência que os dados obrigam a ter, gémea da excepção do balde acima:
uma cópia que está DENTRO da caixa deste deck escapa às regras de material.
Sem isso, o "cEDH só inglês non-foil" desmontava no papel o Blue Farm e o Cloud
cEDH, que estão montados na estante. Só vale para os baldes que SÃO a caixa de um
deck (`caixas_de_deck`): o `SPML` e o `Premodern (geral)` são colecção partilhada
por vários slots, e aí a regra manda.

O Pauper não tem regra de baldes: já via o `SPML` e é de lá que vêm os quatro
Utrom Monitor. O que mudou para ele foi passar a gastar as foil primeiro.

CAIXAS DEDICADAS (André, 2026-09-07 às 19:00, à letra)
------------------------------------------------------
  *"Cada deck montado deixa de partilhar cartas com outros decks nos formatos:
  pauper, CDEH e premodern."*
  *"O que eu quero é conseguir organizar os decks dentro das caixas e apenas
  mexer para actualizar, logo vou precisar de múltiplos para os decks de
  premodern."*

`regras_por_formato[].dedicado` (com override por caixa, como todas as outras
chaves de material). Uma caixa DEDICADA:

  * **não vai buscar** — nunca mostra `noutra` a apontar para outra caixa de
    deck: o que não conseguiu alocar da `Colecção`/`Caixa RL (PT)` é COMPRA;
  * **não empresta** — as cópias que ela alocou nunca aparecem como `noutra` de
    mais ninguém: quem as queria compra as suas;
  * **compra sozinha** — implica o `compras_dedicadas`, por isso fica fora da
    partilha de compras (`partilhar_compras`). É o *"vou precisar de múltiplos"*.

O que NÃO muda: a alocação em si. As cópias que ele tem continuam a ser
repartidas pela ordem de sempre (grupo > permanente > vigiado > prioridade), e a
`Caixa RL (PT)` continua a alimentar o Premodern. Uma cópia da colecção que uma
caixa dedicada leve não se compra outra vez — isso é a colecção a ser repartida,
não uma partilha entre caixas.

Ficam com a partilha (o `noutra` e as compras partilhadas da v4) só o **Duel
Commander** e o **SPML** (Standard, Pioneer, Modern, Legacy).

CAIXA CONGELADA: montada é para ficar montada
---------------------------------------------
*"Apenas mexer para actualizar."* Uma caixa dedicada e `montado: true` está
CONGELADA (`congelada`): as cópias que estão lá dentro (`copy_allocation`) ficam
presas, ninguém as realoca e a venda não lhes toca — mesmo que a lista de hoje já
não as peça. Se a lista vigiada mudar (o Luffy actualiza o Pauper), a caixa
continua montada com a lista antiga e a diferença aparece à parte, como um
**delta de actualização** (`res["actualizacoes"][slot]` = o que sai e o que
entra). Só se aplica quando ele carregar em *"actualizei"* no modo edição
(`actualizar_caixa`); o *"já arrumei tudo"* geral deixa as caixas congeladas
exactamente como estão.

MONTAR, E VENDER O QUE SOBRA (v6, 2026-09-08)
---------------------------------------------
*"Espero começar a montar os decks em deckbox o mais cedo possível para começar a
comprar as faltas e livrar-me dos excessos de cartas."* Daí três funções que são
o gesto e não a conta:

  * `plano_montar(res, slot)` — as cópias a tirar das gavetas para montar UMA
    caixa (o painel *Montar*), pelo mesmo cálculo da arrumação geral
    (`movimentos_de_entrada`) para as duas listas não poderem discordar;
  * `ordem_de_montagem(res)` — por onde começar: permanentes por prioridade,
    depois as candidatas mais perto de fechar;
  * `registar_venda(con, linha)` — o *"vendida"*: a cópia sai da `copies` e a
    venda fica no `data/vendas.csv`. É a única função deste módulo que ESCREVE
    fora da `copy_allocation`, e por isso é a única que tira coisas de casa.

Fora dessas (e do `guardar_arrumacao`/`actualizar_caixa`), sem rede e sem efeitos
colaterais: lê o `vault.db` e devolve números.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

from . import caixas as _caixas
from . import sources, stock

# Última edição legal em Premodern (Scourge). É por aqui que se decide se uma
# impressão é "da era" — a alternativa (a legalidade `premodern` da Scryfall) é
# por carta e não por impressão, e o que o André descreveu foram as EDIÇÕES.
PREMODERN_END = "2003-05-26"
# O balde da Reserved List. É UM no config e DOIS na estante: "na Caixa RL, as PT
# e as ENG estão separadas" (André, 2026-09-07) — as PT servem o Premodern, as EN
# nunca. Ver `local` e `_fora_de_vista`.
BALDE_RL = "Caixa Reserved List"
# O balde único da colecção (André, 2026-09-07: *"põe a colecção toda em uma
# coisa só, com excepção da RL"*). Os outros nomes são os baldes de colecção de
# ANTES da migração — ficam aqui porque o mesmo código tem de estar certo nas
# duas bases: a do André antes de correr a migração e depois dela.
BALDE_COLECCAO = "Colecção"
BALDES_COLECCAO = (BALDE_COLECCAO, "SPML", "Premodern (geral)", "Jogar", BALDE_RL)
CONSTRUCTED_LIMIT = 4                      # playset: acima disto é excedente
FOIL_FINISHES = ("foil", "etched")
COMMANDER_FORMATS = {"duel-commander", "cedh", "commander", "edh"}
# Se uma carta não é legal em nenhum destes, não joga em lado nenhum. É a mesma
# rede de segurança do classify.py: nunca sugerir vender uma carta jogável.
REAL_FORMATS = ("standard", "pioneer", "modern", "legacy", "premodern",
                "vintage", "pauper", "commander")

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
          "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
          "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes"}

# REGRAS POR GRUPO DE FORMATO (André, 2026-09-07, à letra)
# ------------------------------------------------------------------
# *"Língua/acabamento por formato: Premodern apenas as edições da era Premodern e
# em Português; cEDH apenas inglês non-foil; Duel Commander apenas foil; SPML
# (Standard/Pioneer/Modern/Legacy) tudo foil e inglês (RL pode ser non-foil);
# Pauper tudo foil se houver disponível, senão pode ser non-foil."*
# *"Ordem de prioridade na alocação: Premodern > cEDH > Duel Commander > Pauper
# > SPML."*
#
# A ORDEM desta lista É a ordem da alocação — quem vem primeiro escolhe primeiro.
# Antes isto vivia em números soltos no `prioridade` de cada slot do config e em
# casos especiais no código (o `formato == "premodern"` espalhado por três
# funções); um grupo mal numerado à mão mudava a alocação inteira sem ninguém dar
# por isso. O `colecao_config.json -> regras_por_formato` substitui esta lista
# toda, se lá estiver.
#
# Chaves de cada regra:
#   `formatos`    — os `formato` dos slots que caem neste grupo;
#   `lingua`      — a cópia tem de ser desta língua;
#   `acabamento`  — "foil" (só foil/etched, menos Reserved List), "nonfoil" (só
#                   nonfoil) ou "prefere_foil" (aceita as duas, gasta a foil
#                   primeiro — é o Pauper: *"tudo foil se houver disponível"*);
#   `edicoes`     — "premodern": só impressões até ao Scourge;
#   `baldes`      — os únicos baldes que estas caixas VÊEM (mais o seu);
#   `estrita`     — a `lingua` e os `baldes` deste grupo põem a cópia FORA DE
#                   VISTA (falta a comprar) em vez de substituto. É a diferença
#                   entre "decide se abres excepção" e "já decidi que não abro":
#                   *"O Premodern só usa em PT, mesmo eu tendo a carta em inglês."*
#   `dedicado`    — a caixa NÃO EMPRESTA nem VAI BUSCAR cópias a outras caixas de
#                   deck (ver `dedicadas` e `congelada`). André, 2026-09-07,
#                   19:00: *"cada deck montado deixa de partilhar cartas com
#                   outros decks nos formatos: pauper, CDEH e premodern"*.
REGRAS_FORMATO = [
    {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
     "lingua": "pt", "edicoes": "premodern", "estrita": True,
     # A `Colecção` é o balde único de depois da migração; os outros dois são os
     # de antes dela. A lista tem os três para o mesmo código estar certo nas
     # duas bases — o que decide o que a caixa NÃO vê é agora, sobretudo, estar
     # dentro de outra deckbox (`_fora_de_vista`).
     "baldes": [BALDE_COLECCAO, "Premodern (geral)", "SPML", BALDE_RL]},
    {"grupo": "cedh", "formatos": ["cedh"], "dedicado": True,
     "lingua": "en", "acabamento": "nonfoil"},
    {"grupo": "duel-commander", "formatos": ["duel-commander"],
     "acabamento": "foil"},
    {"grupo": "pauper", "formatos": ["pauper"], "dedicado": True,
     "acabamento": "prefere_foil"},
    {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
     "lingua": "en", "acabamento": "foil"},
]
# As chaves de uma regra que se copiam para o slot (as outras são só arrumação).
CHAVES_REGRA = ("lingua", "acabamento", "edicoes", "baldes", "estrita", "dedicado")


def _front(name: str) -> str:
    """Nome da frente de uma carta de dupla face — é assim que as listas a escrevem."""
    return (name or "").split(" // ")[0]


def balde_local(lot: dict) -> str:
    """O BALDE onde a cópia está arrumada (a gaveta), ignorando deckboxes.

    Na estante a Caixa Reserved List são duas — *"na Caixa RL, as PT e as ENG
    estão separadas"* (André, 2026-09-07) — e a diferença importa: as PT servem o
    Premodern, as EN não. O balde na base de dados continua a ser um só.
    """
    if lot["sub"] == BALDE_RL:
        return f"Caixa RL ({'PT' if lot['lang'] == 'pt' else 'EN'})"
    return lot["sub"]


def local(lot: dict) -> str:
    """Onde a cópia está fisicamente, para ele saber onde ir buscá-la.

    Desde o modelo de colecção única (André, 2026-09-07: *"põe a colecção toda em
    uma coisa só, com excepção da RL"*) há dois sítios possíveis: dentro de uma
    **deckbox** (a alocação já confirmada, tabela `copy_allocation`) ou no
    **balde** onde está arrumada. A deckbox ganha — é onde a carta está mesmo.
    """
    return lot.get("caixa_nome") or balde_local(lot)


# ---------------------------------------------------------------------------
# Preços
# ---------------------------------------------------------------------------
def card_price(con, name: str, finish: str = "nonfoil",
               source: str = "cardmarket") -> tuple[float | None, str | None]:
    """(preço da impressão mais barata, acabamento a que esse preço corresponde).

    O `wantlist.cheapest_price` só olha para nonfoil, e metade do loadout tem de
    ser comprada em FOIL — com o preço nonfoil o custo de fechar esses decks vinha
    sistematicamente abaixo do real. Quando não há preço foil, devolve o nonfoil e
    diz que é nonfoil, para quem mostra poder marcar a estimativa como incerta.
    """
    fins = FOIL_FINISHES if finish in FOIL_FINISHES else ("nonfoil",)
    marks = ",".join("?" * len(fins))
    row = con.execute(
        f"""SELECT MIN(p.trend) preco FROM cards c
              JOIN price_latest p ON p.scryfall_id = c.scryfall_id
             WHERE c.name = ? AND p.source = ? AND p.finish IN ({marks})""",
        (name, source, *fins)).fetchone()
    if row and row["preco"] is not None:
        return row["preco"], fins[0]
    if fins[0] == "nonfoil":
        return None, None
    row = con.execute(
        """SELECT MIN(p.trend) preco FROM cards c
             JOIN price_latest p ON p.scryfall_id = c.scryfall_id
            WHERE c.name = ? AND p.source = ? AND p.finish = 'nonfoil'""",
        (name, source)).fetchone()
    return ((row["preco"], "nonfoil") if row and row["preco"] is not None
            else (None, None))


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
def config_slots() -> list[dict]:
    """As caixas do config, na forma interna (ver `mtgvault.caixas`).

    Desde a v6 a chave é `caixas` e não `loadout` — uma estrutura só para o que
    eram duas (*"temos decks vigiados e deckbox que é a mesma coisa"*, André,
    2026-09-08). Um config da v5 continua a servir: o `caixas.do_config` migra-o
    em memória, e o `para_slot` devolve exactamente os mesmos campos de sempre.
    É por isso que a unificação não mexe num único número da alocação.
    """
    return _caixas.slots()


def baldes_coleccao() -> tuple[str, ...]:
    """Os baldes que são COLECÇÃO (gavetas), e não a caixa de um deck montado.

    `colecao_config.json -> baldes_coleccao` manda. Desde o modelo de colecção
    única são dois — `Colecção` e `Caixa Reserved List` — mas os nomes antigos
    continuam na lista para o mesmo código estar certo antes e depois da
    migração (`mtgvault.migracao`).
    """
    v = sources.config().get("baldes_coleccao")
    return tuple(v) if isinstance(v, list) and v else BALDES_COLECCAO


def regras_por_formato() -> list[dict]:
    """As regras de material por grupo de formato, pela ORDEM da alocação.

    `colecao_config.json -> regras_por_formato` manda; sem ela vale a
    `REGRAS_FORMATO` deste módulo, que é a ordem que o André ditou.
    """
    v = sources.config().get("regras_por_formato")
    if not isinstance(v, list) or not v:
        return REGRAS_FORMATO
    return [{k: x[k] for k in x if not str(k).startswith("_")} for x in v]


def regra_do_formato(fmt: str | None,
                     regras: list[dict] | None = None) -> tuple[int, dict]:
    """(posição do grupo na ordem de alocação, regra) do formato de um slot.

    Um formato que não esteja em grupo nenhum fica no fim e sem regra de
    material — não se inventa uma restrição que ele não ditou.
    """
    regras = regras if regras is not None else regras_por_formato()
    for i, r in enumerate(regras):
        if fmt in (r.get("formatos") or []):
            return i, r
    return len(regras), {}


def dedicadas(slots) -> set[str]:
    """Os NOMES das caixas dedicadas — as que não emprestam nem vão buscar.

    Por nome e não por slot porque é o nome que viaja no `noutra` ({caixa:
    quantas}) e no `lot["caixa_nome"]`, que é o que as páginas mostram.
    """
    return {s["nome"] for s in slots if s.get("dedicado") and s.get("nome")}


def congelada(s: dict, arrumadas: set[str] | frozenset | None = None) -> bool:
    """A caixa está montada e é dedicada: não se lhe mexe sem ser para actualizar.

    André, 2026-09-07: *"o que eu quero é conseguir organizar os decks dentro das
    caixas e apenas mexer para actualizar"*. As cópias que estão lá dentro ficam
    presas mesmo que a lista de hoje já não as peça — a caixa continua montada
    com a lista antiga, e a diferença sai como delta de actualização.

    `arrumadas` = as caixas que TÊM linhas na `copy_allocation`. Uma caixa que se
    diz montada mas de que o vault não sabe o conteúdo não está congelada — não
    há nada para prender, e apresentar a lista inteira como um delta de
    *"actualização"* era mentir sobre o que ele tem de fazer (é montá-la, não
    actualizá-la). É o caso do Stiflenought na base de 2026-09-07: `montado:
    true` no config e zero linhas na tabela, porque a migração só semeou as
    caixas que eram um balde.
    """
    if not (s.get("dedicado") and s.get("montado")):
        return False
    return arrumadas is None or s.get("slot") in arrumadas


def caixas_arrumadas(con) -> set[str]:
    """As caixas que têm conteúdo confirmado na `copy_allocation`."""
    try:
        return {r["slot"] for r in con.execute(
            "SELECT DISTINCT slot FROM copy_allocation WHERE quantity > 0")}
    except sqlite3.OperationalError:
        return set()                  # base antiga, ainda sem a tabela


def e_foil(finish: str | None) -> bool:
    """A cópia é foil? É `finish in FOIL_FINISHES` e mais nada — existe como
    função porque as páginas escreviam este teste à mão com `"foil" in finish`,
    e `"nonfoil"` CONTÉM `"foil"`: a tabela de venda punha ✨ em cópias nonfoil.
    Um teste de substring nunca serve para isto."""
    return finish in FOIL_FINISHES


def fontes_material(s: dict) -> str | None:
    """As gavetas que esta caixa VÊ, em nome de gente ("Colecção + Caixa RL (PT)").

    Antes era `"só de " + " · ".join(s["baldes"])`, o que dava *"só de Colecção ·
    Premodern (geral) · SPML · Caixa RL"* — quatro nomes que no modelo de
    colecção única são **duas gavetas**: os três primeiros são a mesma
    (`baldes_coleccao`), e a lista tem-nos todos só para o código estar certo
    antes e depois da migração. Além de transbordar o cartão, dizia ao André que
    há três sítios onde só há um.

    `None` quando é o padrão (só a Colecção): uma regra que não restringe nada
    não é uma regra para mostrar.
    """
    baldes = s.get("baldes")
    if not baldes:
        return None
    coleccao = set(baldes_coleccao()) - {BALDE_RL}
    fora, out = set(), []
    for b in list(baldes) + ([s["balde"]] if s.get("balde") else []):
        if b in coleccao:
            nome = BALDE_COLECCAO
        elif b == BALDE_RL:
            # A Caixa RL é uma no config e duas na estante; um slot que exija PT
            # só vê a metade PT (ver `_fora_de_vista`), e é isso que se mostra.
            nome = f"Caixa RL ({s['lingua'].upper()})" if s.get("lingua") else "Caixa RL"
        else:
            nome = b
        if nome not in fora:
            fora.add(nome)
            out.append(nome)
    if out == [BALDE_COLECCAO]:
        return None
    return "fontes: " + " + ".join(out)


def rotulo_material(s: dict) -> list[tuple[str, str, str]]:
    """As regras de material desta caixa como (ícone, texto, classe), para a
    página e o CLI.

    Vive aqui e não em cada página porque já aconteceu o contrário: o
    `deckboxes` dizia *"sem Caixa RL"* a todas as caixas de Premodern depois de a
    regra ter mudado para *"vê a metade PT da Caixa RL"*. Uma regra nova que
    ninguém mostre é uma página a mentir em silêncio.

    A CLASSE vem daqui pela mesma razão. Cada página decidia-a com
    `"foil" in texto`, e `"só nonfoil"` contém `"foil"`: a caixa do cEDH — a
    única *"só nonfoil"* — vinha pintada de dourado como se fosse de foil.
    """
    out = []
    if s.get("lingua"):
        out.append(("🇵🇹" if s["lingua"] == "pt" else "🔤",
                    f'só {s["lingua"].upper()}', "pt"))
    ac = s.get("acabamento")
    if ac == "foil":
        out.append(("✨", "só foil (a Reserved List pode ser nonfoil)", "fo"))
    elif ac == "nonfoil":
        out.append(("◻", "só nonfoil", ""))
    elif ac == "prefere_foil":
        out.append(("✨", "foil quando há, senão nonfoil", "fo"))
    if s.get("edicoes") == "premodern":
        out.append(("🕰", "só edições até ao Scourge", ""))
    if s.get("dedicado"):
        # Uma regra que a página não diz é a página a mentir em silêncio — e esta
        # muda o preço de fechar a caixa, por isso tem de estar à vista.
        out.append(("🔒", "caixa dedicada: não empresta nem vai buscar"
                    + (" · montada, só mexe para actualizar"
                       if s.get("congelada") else ""), "ded"))
    if s.get("montado_por_confirmar"):
        out.append(("❔", "dizes que está montada, mas ainda não me disseste o que "
                    "lá está — carrega em «Sleevado e na caixa»", "wt"))
    fontes = fontes_material(s)
    if fontes:
        out.append(("🗂️", fontes, ""))
    return out


def requisito_material(s: dict) -> str:
    """As regras desta caixa em três palavras, para uma linha de wantlist:
    `"PT · ≤SCG"`, `"EN · nonfoil"`, `"EN · foil"`. Vazio = sem exigência.

    O `rotulo_material` é para o cartão da caixa (uma frase por regra); isto é
    para a aba **Comprar**, onde cada linha tem de dizer em que língua e
    acabamento é que aquela compra serve — comprar a versão errada é comprar
    duas vezes.
    """
    partes = []
    if s.get("lingua"):
        partes.append(s["lingua"].upper())
    ac = s.get("acabamento")
    if ac == "foil":
        partes.append("foil")
    elif ac == "nonfoil":
        partes.append("nonfoil")
    elif ac == "prefere_foil":
        partes.append("foil (ou nonfoil)")
    if s.get("edicoes") == "premodern":
        partes.append("≤SCG")
    return " · ".join(partes)


def marca_wantlist(s: dict) -> str:
    """A etiqueta que a wantlist do Cardmarket leva ("FOIL" / "PT" / ""),
    para ele não comprar material que a caixa depois recusa."""
    if s.get("acabamento") in ("foil", "prefere_foil"):
        return "FOIL"
    return s["lingua"].upper() if s.get("lingua") == "pt" else ""


def marca_compra(s: dict) -> str:
    """O material de UMA LINHA da wantlist copiada: `PT`, `EN nonfoil`, `EN foil`.

    O `marca_wantlist` é uma etiqueta para a lista toda (uma caixa, um material)
    e o `requisito_material` é a frase para a página. Isto é o que vai **dentro
    do texto que ele copia** para o Cardmarket, linha a linha:

        2 Swords to Plowshares [PT]
        1 Lion's Eye Diamond [EN nonfoil]

    Desde que as compras se partilham entre caixas (ver `partilhar_compras`) uma
    linha da aba *Comprar* já não pertence a uma caixa só, e a lista copiada
    perdia a única pista do material. Sem a edição (`≤SCG`), que é uma condição
    a verificar na oferta e não um filtro que se escreva na wantlist.
    """
    partes = []
    if s.get("lingua"):
        partes.append(s["lingua"].upper())
    ac = s.get("acabamento")
    if ac == "foil":
        partes.append("foil")
    elif ac == "nonfoil":
        partes.append("nonfoil")
    elif ac == "prefere_foil":
        partes.append("foil ou nonfoil")
    return " ".join(partes)


def _retencao() -> dict[str, int]:
    """Baldes com `reter_extras_meses` (regras_colecao). Enquanto não houver fonte
    de "última utilização" (ver CLAUDE.md), estes extras RETÊM-SE — nunca entram
    na venda; a página di-lo em vez de fingir que a regra já corre."""
    regras = sources.config().get("regras_colecao") or {}
    return {b: r["reter_extras_meses"] for b, r in regras.items()
            if isinstance(r, dict) and r.get("reter_extras_meses")}


# ---------------------------------------------------------------------------
# De onde vem a lista de cada slot
# ---------------------------------------------------------------------------
def _cards_from_deck(con, name: str) -> tuple[list[tuple[str, str, int]], str]:
    row = con.execute("SELECT id, notes FROM decks WHERE name = ?", (name,)).fetchone()
    if row is None:
        return [], f"deck {name!r} não existe na tabela `decks`"
    cards = [(("side" if r["board"] == "side" else "main"), _front(r["nm"]), r["q"])
             for r in con.execute(
                 """SELECT card_name nm, board, SUM(quantity) q FROM deck_cards
                     WHERE deck_id = ? GROUP BY card_name, board""", (row["id"],))]
    return cards, (row["notes"] or "")


def _cards_from_watched(con, label: str) -> tuple[list[tuple[str, str, int]], str]:
    row = con.execute(
        """SELECT ws.cards, ws.taken_at FROM watched w
             JOIN watched_snapshots ws ON ws.watched_id = w.id
            WHERE w.label = ? ORDER BY ws.taken_at DESC LIMIT 1""", (label,)).fetchone()
    if row is None:
        return [], f"vigiado {label!r} ainda sem snapshot"
    agg: dict[tuple[str, str], int] = defaultdict(int)
    for board, nm, q in json.loads(row["cards"]):
        agg[("side" if board == "side" else "main", _front(nm))] += q
    return ([(b, n, q) for (b, n), q in agg.items()],
            f"lista vigiada de {row['taken_at']}")


def _cards_from_consensus(con, fmt: str, assinatura: list[str]
                          ) -> tuple[list[tuple[str, str, int]], str]:
    """Consenso de um arquétipo identificado por carta-assinatura.

    Só listas que CONTAM (`sources.counting_sql`) e o mesmo cálculo de lista
    padrão de toda a gente (`stock.stock_from_lists`) — não se inventa aqui um
    segundo consenso que discordasse do resto do vault em silêncio.
    """
    if not assinatura:
        return [], "sem assinatura configurada"
    conta, cp = sources.counting_sql(fmt, "d")
    marks = ",".join("?" * len(assinatura))
    ids = [r[0] for r in con.execute(
        f"""SELECT DISTINCT d.id FROM decklists d
              JOIN decklist_cards dc ON dc.decklist_id = d.id
             WHERE d.format = ? AND dc.card_name IN ({marks}) AND {conta}""",
        (fmt, *assinatura, *cp))]
    if len(ids) < stock_min_lists():
        return [], f"só {len(ids)} listas contam — poucas para consenso"
    ph = ",".join("?" * len(ids))
    main: dict[int, dict[str, int]] = defaultdict(dict)
    side: dict[int, dict[str, int]] = defaultdict(dict)
    for r in con.execute(
            f"""SELECT decklist_id i, card_name nm, quantity q, board b
                  FROM decklist_cards WHERE decklist_id IN ({ph})""", ids):
        (side if r["b"] == "side" else main)[r["i"]][_front(r["nm"])] = r["q"]
    sl = stock.stock_from_lists(fmt, [main[i] for i in ids if main.get(i)],
                                [side[i] for i in ids if side.get(i)])
    cards = [("main", c["card_name"], c["quantity"]) for c in sl["main"]]
    cards += [("side", c["card_name"], c["quantity"]) for c in sl["side"]]
    return cards, f"consenso de {len(ids)} listas"


def listas_escolhidas() -> dict[str, dict]:
    """`colecao_config.json -> listas_escolhidas`: as listas que ele ESCOLHEU.

    André, 2026-09-07 (19:00): *"vou montar este"* — o botão do top-3 do
    `metagame.html`. A lista fica **congelada com a data**, e não recalculada
    todos os dias: se o consenso do arquétipo mudar amanhã, a caixa que ele
    mandou montar não muda debaixo dos pés (nem a lista de compras).

    Vive numa chave própria e não dentro do slot para o `loadout` continuar a ser
    catorze linhas legíveis — uma lista de 75 cartas numa delas não se lê.
    """
    v = sources.config().get("listas_escolhidas")
    return v if isinstance(v, dict) else {}


def _cards_from_escolhido(ref: str) -> tuple[list[tuple[str, str, int]], str]:
    rec = listas_escolhidas().get(ref)
    if not rec or not rec.get("cards"):
        return [], f"escolha {ref!r} sem lista guardada em `listas_escolhidas`"
    cards = [(("side" if b == "side" else "main"), _front(n), int(q))
             for b, n, q in rec["cards"]]
    quando = rec.get("escolhido_em") or "?"
    fonte = rec.get("subtitulo") or rec.get("label") or ""
    nota = f"escolhido por ti em {quando}"
    if rec.get("n_listas"):
        nota += f" · consenso de {rec['n_listas']} listas"
    return cards, (f"{nota} · {fonte}" if fonte else nota)


def stock_min_lists() -> int:
    return 5      # o mesmo mínimo do analysis.rebuild_roles / premodern_decks


def _slot_cards(con, s: dict) -> tuple[list[tuple[str, str, int]], str]:
    fonte = (s.get("fonte") or "").lower()
    ref = s.get("ref")
    if not ref and fonte != "consenso":
        return [], "slot por confirmar — sem lista escolhida"
    if fonte == "deck":
        return _cards_from_deck(con, ref)
    if fonte == "escolhido":
        return _cards_from_escolhido(ref)
    if fonte == "vigiado":
        return _cards_from_watched(con, ref)
    if fonte == "consenso":
        return _cards_from_consensus(con, s["formato"], s.get("assinatura") or [])
    return [], f"fonte {fonte!r} desconhecida"


def resolve_slots(con, cfg_slots: list[dict] | None = None) -> list[dict]:
    """Os slots do loadout com a lista de cada um já resolvida.

    `variantes`: um slot pode juntar mais do que um deck (o André: *"1 deck de
    Modern (+ possíveis variantes desse deck — as variantes partilham a caixa")*.
    A caixa leva a UNIÃO das cartas, cada uma na quantidade máxima que alguma
    variante pede, e as que não são comuns a todas ficam marcadas — é o que se
    quer ver ao montar: o que sai e entra para trocar de variante.

    A ORDEM da alocação sai daqui (André, 2026-09-07): primeiro o grupo de
    formato (*"Premodern > cEDH > Duel Commander > Pauper > SPML"*), depois os
    decks vigiados (*"os decks vigiados têm prioridade para ficarem com as
    cartas, desde que respeitem as regras"*) e só então o `prioridade` que o
    config dá a cada slot. O `prioridade` de cada slot passa a ser a posição
    GLOBAL resultante (1, 2, 3, …) — é o número que a página e o CLI mostram — e
    o do config fica em `prioridade_config`. As regras de material do grupo
    também se colam aqui ao slot; o que o config escrever no slot ganha, para
    uma excepção continuar a ser uma linha de config e não uma linha de código.
    """
    out = []
    regras = regras_por_formato()
    arrumadas = caixas_arrumadas(con)
    vigiados = set(sources.config().get("decks_vigiados") or [])
    for s in (cfg_slots if cfg_slots is not None else config_slots()):
        # Aceita as duas formas — a caixa da v6 e a linha do `loadout` da v5 —
        # e devolve sempre a interna. Uma função só, e idempotente.
        s = _caixas.para_slot(s)
        ordem_grupo, regra = regra_do_formato(s.get("formato"), regras)
        for k in CHAVES_REGRA:
            if k in regra and k not in s:
                s[k] = regra[k]
        s["grupo"] = regra.get("grupo") or s.get("formato")
        s["grupo_ordem"] = ordem_grupo
        s["vigiado"] = (s.get("fonte") == "vigiado"
                        or bool(s.get("ref")) and s["ref"] in vigiados)
        # `dedicado` chega aqui pela regra do grupo (ver `CHAVES_REGRA`) ou
        # escrito na própria caixa. Normaliza-se para as páginas não terem de
        # distinguir `False` de "a chave não existe".
        s["dedicado"] = bool(s.get("dedicado"))
        s["congelada"] = congelada(s, arrumadas)
        # O `estado` que as páginas mostram é o EFECTIVO: `congelada` calcula-se
        # (montada + dedicada + o vault sabe o que lá está), nunca se grava.
        if s["congelada"]:
            s["estado"] = _caixas.CONGELADA
        # Diz-se montada e o vault não sabe o que lá está dentro. Não é um erro —
        # é o estado normal de quem ainda não carregou em "Sleevado e na caixa" —
        # mas a página tem de o dizer, senão o "delta de actualização" mostra a
        # lista inteira como se ele tivesse de a trocar.
        s["montado_por_confirmar"] = (s["montado"] and s["dedicado"]
                                      and not s["congelada"])
        cards, nota = _slot_cards(con, s)
        so_de: dict[str, set[str]] = defaultdict(set)
        variantes = list(s.get("variantes") or [])
        if variantes:
            base = {(b, n): q for b, n, q in cards}
            for v in variantes:
                vc, _ = _cards_from_deck(con, v)
                for b, n, q in vc:
                    base[(b, n)] = max(base.get((b, n), 0), q)
                    so_de[n].add(v)
            for _b, n, _q in cards:
                so_de.pop(n, None)          # está na base: não é exclusiva
            cards = [(b, n, q) for (b, n), q in base.items()]
        s["cards"] = sorted(cards, key=lambda c: (c[0] != "main", c[1]))
        s["nota"] = nota
        s["so_de_variante"] = {n: sorted(v) for n, v in so_de.items()}
        s["vazio"] = not cards
        # A escolha dele ("vou montar este") e o dia em que a fez — a página
        # mostra-a, e é ela que distingue um deck escolhido de uma alternativa.
        esc = (listas_escolhidas().get(s.get("ref") or "")
               if s.get("fonte") == "escolhido" else None)
        s["escolhido_em"] = (esc or {}).get("escolhido_em")
        s["archetype_id"] = (esc or {}).get("archetype_id")
        s.setdefault("prioridade", 99)
        s.setdefault("nome", s.get("ref") or s.get("slot"))
        out.append(s)
    # PERMANENTES PRIMEIRO, e só depois os candidatos. É a ordem que ele pediu:
    # *"os decks que eu pedi para serem permanentes são a minha prioridade
    # máxima"* e *"os decks que eu estiver quase a concluir, tenho que ter uma
    # opção que os marque como permanentes para começarem a receber alocação"*.
    # Um candidato fica com o que sobrar e mostra "em <caixa>" para o resto —
    # não deixa de ver as cartas, só não as tira a quem está montado.
    out.sort(key=lambda x: (not x["permanente"], x["grupo_ordem"],
                            not x["vigiado"], x["prioridade"], x["nome"]))
    for i, s in enumerate(out, 1):
        s["prioridade_config"] = s["prioridade"]
        s["prioridade"] = i
    return out


# ---------------------------------------------------------------------------
# Exemplares
# ---------------------------------------------------------------------------
def _legal_em(leg_json, formatos) -> bool:
    try:
        leg = json.loads(leg_json) if leg_json else {}
    except (TypeError, ValueError):
        return True                     # na dúvida, não sugerir venda
    return any(leg.get(f) in ("legal", "restricted") for f in formatos)


def alocacao_confirmada(con) -> dict[int, dict[str, int]]:
    """`copy_id -> {slot: quantas cópias desse lote já estão nessa deckbox}`.

    É a arrumação CONFIRMADA — o que o André já sleevou e meteu na caixa (botão
    *"já arrumei"*). O loadout continua a recalcular todos os dias onde cada
    carta DEVE estar; esta tabela diz onde ela ESTÁ, e a diferença entre as duas
    é a lista de arrumação (`plano_arrumacao`).
    """
    out: dict[int, dict[str, int]] = defaultdict(dict)
    try:
        rows = con.execute("SELECT copy_id, slot, quantity FROM copy_allocation")
    except sqlite3.OperationalError:
        return {}                     # base antiga, ainda sem a tabela
    for r in rows:
        if (r["quantity"] or 0) > 0:
            out[r["copy_id"]][r["slot"]] = r["quantity"]
    return dict(out)


def nomes_das_caixas(cfg_slots: list[dict] | None = None) -> dict[str, str]:
    """`slot -> nome da caixa`, para dizer onde a carta está em vez do id."""
    return {s["slot"]: (s.get("nome") or s["slot"])
            for s in (cfg_slots if cfg_slots is not None else config_slots())
            if s.get("slot")}


def lots(con, cfg_slots: list[dict] | None = None) -> dict[str, list[dict]]:
    """Exemplares 'player' por nome de carta. A coleção de colecionador nunca
    entra (regra de domínio: é avaliada, não é jogada).

    Um lote de 4 pode estar meio dentro de uma deckbox e meio na gaveta — por
    isso um lote da `copies` sai daqui PARTIDO em sub-lotes, um por sítio onde
    está (`caixa`), mais o que sobrou solto. Sem isso, a excepção *"o que está
    dentro da caixa do próprio deck escapa às regras de material"* teria de
    valer para o lote inteiro, e um lote parcialmente arrumado passava a valer
    por inteiro. Cada sub-lote tem `key` própria (o `id` repete-se).
    """
    conf = alocacao_confirmada(con)
    nomes = nomes_das_caixas(cfg_slots)
    out: dict[str, list[dict]] = defaultdict(list)
    for r in con.execute(
        """SELECT cp.id, cp.quantity q, cp.finish, cp.language lang,
                  cp.reserved_deck_id rdid, s.name sub, cp.balde_origem borigem,
                  c.name nm, c.scryfall_id sid, c.set_code, c.set_name,
                  c.released_at rel, COALESCE(c.reserved, 0) rl, c.legalities leg
             FROM copies cp
             JOIN cards c ON c.scryfall_id = cp.scryfall_id
             LEFT JOIN sub_collections s ON s.id = cp.sub_collection_id
            WHERE cp.purpose = 'player'"""):
        d = dict(r)
        d["nm"] = _front(d["nm"])
        d["sub"] = d["sub"] or "(sem balde)"
        d["era_pm"] = bool(d["rel"]) and d["rel"] <= PREMODERN_END
        d["rl"] = bool(d["rl"])
        # Uma linha de `copy_allocation` para uma caixa que já não está no
        # loadout é órfã: ignora-se. Tratá-la como uma caixa a sério tirava as
        # cópias de circulação para sempre e mostrava o `slot` cru ("legacy") no
        # lugar do nome da caixa — sem erro nenhum e sem maneira de desfazer.
        dentro = {k: v for k, v in (conf.get(d["id"]) or {}).items()
                  if v > 0 and k in nomes}
        solto = d["q"] - sum(dentro.values())
        partes = sorted(dentro.items())
        if solto > 0 or not partes:
            partes.append((None, max(solto, 0)))
        for caixa, q in partes:
            e = dict(d)
            e["caixa"] = caixa                # slot da deckbox, ou None
            e["caixa_nome"] = nomes.get(caixa) or caixa
            e["q"] = q
            e["livre"] = q
            e["key"] = (d["id"], caixa or "")
            e["balde"] = balde_local(e)       # a gaveta, mesmo estando na caixa
            e["local"] = local(e)
            e["substituto"] = {}      # slot -> porque é que não fecha o slot
            e["alocado"] = {}         # slot -> quantas cópias deste lote levou
            out[e["nm"]].append(e)
    return out


def _deck_ids(con, slots) -> dict[str, int | None]:
    """slot -> id na tabela `decks` (para respeitar `copies.reserved_deck_id`)."""
    out = {}
    for s in slots:
        row = (con.execute("SELECT id FROM decks WHERE name = ?", (s["ref"],)).fetchone()
               if s.get("fonte") == "deck" and s.get("ref") else None)
        out[s["slot"]] = row["id"] if row else None
    return out


def _noutra_caixa(lot: dict, s: dict) -> bool:
    """A cópia está DENTRO da caixa de outro deck, já montada.

    Não se aloca (de um deck montado não se tira nada para montar outro), mas
    também **não é falta**: é ir buscá-la, e é isso que a torna diferente do
    `_fora_de_vista`. É a versão nova da regra que os baldes dos decks faziam —
    a caixa deixou de ser um balde e passou a ser a arrumação confirmada.

    A ordem da alocação não chega para isto. O argumento que valia até aqui ("o
    que falta a S foi levado por um slot que corre ANTES") deixa de valer quando
    uma cópia já está numa caixa que corre DEPOIS: sem esta regra, um slot de
    Premodern — que corre primeiro — tirava-a de dentro de um deck montado.
    """
    return bool(lot.get("caixa")) and lot["caixa"] != s.get("slot")


def _fora_de_vista(lot: dict, s: dict) -> bool:
    """Cópias que este slot nem VÊ — nem para alocar, nem como substituto.

    É diferente do `_porque_nao`: ali a cópia existe e não serve, e fica como
    substituto ("decide se abres excepção"); aqui ele já decidiu que não abre, e
    a carta é FALTA a comprar. Vale só para os grupos marcados `estrita` nas
    `regras_por_formato` — hoje só o Premodern, por duas ordens do André de
    2026-09-07:
      * *"O Premodern só usa em PT, mesmo eu tendo a carta em inglês"* — uma EN
        nunca fecha um slot de Premodern nem lhe serve de substituto;
      * *"na Caixa RL, as PT e as ENG estão separadas"* — a Caixa RL não está
        fora, está lá metade: as PT de lá servem, as EN não (é o mesmo teste da
        língua, e por isso não precisa de caso próprio). O que fica de fora são
        os baldes que são a CAIXA de outro deck montado (Blue Farm, Cloud, ...):
        essas cartas estão dentro de um deck, não se tiram de lá para montar
        outro.
    """
    if not s.get("estrita"):
        return False
    if s.get("lingua") and lot["lang"] != s["lingua"]:
        return True
    baldes = s.get("baldes")
    return bool(baldes) and lot["sub"] not in set(baldes) | {s.get("balde")}


def _porque_nao(lot: dict, s: dict, baldes_de_deck: set[str],
                caixas: set[str] | frozenset = frozenset()) -> str | None:
    """Porque é que este exemplar NÃO serve este slot (None = serve)."""
    # Uma cópia que está DENTRO da caixa deste deck já é deste deck: o deck está
    # fisicamente montado. É a mesma excepção que a tranca do PT sempre teve (o
    # Lotus Petal PT dentro do Blue Farm), alargada às regras de material novas
    # de 2026-09-07 — sem ela, o "cEDH só inglês non-foil" desmontava no papel
    # dois decks que estão montados na estante. Só vale para os baldes que SÃO a
    # caixa de um deck: o `SPML` e o `Premodern (geral)` são colecção partilhada
    # por vários slots, e aí a regra manda.
    #
    # No modelo de colecção única a caixa deixou de ser um balde: o que diz que a
    # cópia está dentro DESTA caixa é a arrumação confirmada (`copy_allocation`).
    # Esta linha é a mesma excepção, na versão nova — e é a que impede que uma
    # regra de material nova desmonte no papel um deck que está na estante.
    if lot.get("caixa") and lot["caixa"] == s.get("slot"):
        return None
    if s.get("balde") and lot["sub"] == s["balde"] and s["balde"] in caixas:
        return None
    # Tranca do Premodern: PT + impressão da era. Excepção: se a cópia vive no
    # balde de OUTRO slot do loadout, é desse deck (está fisicamente na caixa
    # dele) e não se lhe mexe. Vem antes da língua de propósito: é a razão mais
    # informativa das duas ("está trancada ao Premodern" > "não é EN").
    if (lot["lang"] == "pt" and lot["era_pm"] and s["formato"] != "premodern"
            and lot["sub"] not in baldes_de_deck):
        return "PT da era Premodern (trancada ao Premodern)"
    if s.get("lingua") and lot["lang"] != s["lingua"]:
        return f"não é {s['lingua'].upper()}"
    ac = s.get("acabamento")
    if ac == "foil" and lot["finish"] not in FOIL_FINISHES and not lot["rl"]:
        return "não é foil"
    if ac == "nonfoil" and lot["finish"] in FOIL_FINISHES:
        return "não é nonfoil"
    if s.get("edicoes") == "premodern" and not lot["era_pm"]:
        return "edição posterior ao Scourge"
    return None


def _ordem(lot: dict, s: dict) -> tuple:
    """Que exemplar gastar primeiro: o da própria caixa, depois o menos versátil
    (uma nonfoil não serve os decks de foil — gasta-se essa antes da foil).

    Excepto onde ele pediu o contrário: no Pauper é *"tudo foil se houver
    disponível, senão pode ser non-foil"* (`acabamento: "prefere_foil"`), e aí a
    foil vai primeiro.

    O primeiro critério passou a ser a cópia que JÁ ESTÁ nesta caixa (arrumação
    confirmada). Sem ele, a corrida do dia seguinte podia trocar de caixa duas
    cópias equivalentes e mandá-lo desmontar dois decks para não mudar nada.
    """
    foil = lot["finish"] in FOIL_FINISHES
    return (lot.get("caixa") != s.get("slot"),
            lot["sub"] != s.get("balde"),
            not foil if s.get("acabamento") == "prefere_foil" else foil,
            not lot["rl"],
            lot["set_code"] or "", lot["key"])


def _linha_cheia(linha: dict) -> dict:
    """Uma linha TIDA com as mesmas chaves de uma em falta.

    As páginas que mostram uma caixa carta a carta (`deckboxes`, `meusdecks`,
    `metagame`) percorrem `have` e `missing` juntos; sem isto tinham de saber de
    cor quais as chaves que só existem de um dos lados, e a primeira que se
    esquecesse rebentava com KeyError em produção e não nos testes.
    """
    linha.setdefault("missing", 0)
    linha.setdefault("comprar", 0)
    linha.setdefault("noutra", {})
    linha.setdefault("noutra_q", 0)
    # A parte do `noutra` que ainda não está em casa: vem de uma compra
    # PARTILHADA com outra caixa (ver `partilhar_compras`). A página tem de o
    # dizer — "em Blue Farm" numa carta que ninguém comprou ainda era mentira.
    linha.setdefault("noutra_futura", {})
    linha.setdefault("unit", None)
    linha.setdefault("price_finish", None)
    linha.setdefault("cost", 0.0)
    linha.setdefault("alt", {})
    linha.setdefault("alt_onde", {})
    return linha


def _empresta(s: dict, outra: str, ded: set[str] | frozenset) -> bool:
    """A caixa `outra` pode emprestar a cópia ao slot `s`? (o "ir buscar")

    Duas metades da mesma regra de 2026-09-07 (*"cada deck montado deixa de
    partilhar cartas com outros decks"*): uma caixa dedicada **não vai buscar**
    (é `s`) e **não empresta** (é `outra`). Quando não empresta, a carta volta a
    ser o que era antes do `noutra`: uma FALTA a comprar.
    """
    return not (s.get("dedicado") or outra in ded)


def _estado_carta(pool: dict, s: dict, nm: str, need: int, baldes: set[str],
                  did: int | None = None,
                  caixas: set[str] | frozenset = frozenset(),
                  ded: set[str] | frozenset = frozenset()) -> dict:
    """Quantas cópias que SERVEM este slot estão livres, e quantas estão noutra caixa.

    É a versão que NÃO consome: serve quem faz a pergunta "e se fosse este
    deck?" — o ranking de arquétipos do `foil_report`, onde as opções são
    alternativas entre si e não caixas montadas ao mesmo tempo. A alocação a
    sério continua a ser o `allocate`, que gasta cada cópia uma só vez.

    Devolve {got, noutra, noutra_q, comprar} com a mesma leitura de sempre: o que
    está noutra caixa vai-se buscar e **não se compra** (André, 2026-09-07).
    """
    livre = 0
    onde: dict[str, int] = defaultdict(int)
    for lot in pool.get(nm, []):
        if lot["rdid"] is not None and lot["rdid"] != did:
            continue
        if _fora_de_vista(lot, s) or _porque_nao(lot, s, baldes, caixas):
            continue
        if _noutra_caixa(lot, s):
            if _empresta(s, lot["caixa_nome"], ded):
                onde[lot["caixa_nome"]] += lot["q"]  # está sleevada noutra caixa
            continue
        livre += lot["livre"]
        for caixa, q in lot["alocado"].items():
            if caixa != s.get("nome") and _empresta(s, caixa, ded):
                onde[caixa] += q
    got = min(need, livre)
    resta = need - got
    noutra: dict[str, int] = {}
    for caixa, q in sorted(onde.items(), key=lambda kv: (-kv[1], kv[0])):
        if resta <= 0:
            break
        noutra[caixa] = min(q, resta)
        resta -= noutra[caixa]
    nq = sum(noutra.values())
    return {"got": got, "noutra": noutra, "noutra_q": nq,
            "comprar": need - got - nq}


def slots_por_lista(res: dict) -> dict[str, dict]:
    """Os slots do loadout indexados pela LISTA de onde saíram (`ref`).

    É a ponte entre o loadout e as páginas que mostram decks um a um. O
    `meusdecks` conhece cada deck pelo nome na tabela `decks` ou pela etiqueta do
    `watched` — e esse nome é exactamente o `ref` do slot. Sem esta ponte, cada
    página contava a posse à sua maneira: o `meusdecks` só via o balde ligado ao
    deck (`deck_collection`) e, por isso, quatro Utrom Monitor que estão no SPML
    não apareciam no Pauper, que é a caixa que as leva (André, 2026-09-07).

    O nome da caixa e o id do slot também entram, para quem os tiver à mão.
    """
    out: dict[str, dict] = {}
    for s in res["slots"]:
        for k in (s.get("ref"), s.get("nome"), s.get("slot")):
            if k:
                out.setdefault(k, s)
    return out


def linhas_por_carta(s: dict) -> dict[tuple[str, str], dict]:
    """(board, carta) -> a linha da alocação desta caixa, tida ou em falta."""
    return {(m["board"], m["nm"]): m for m in s["have"] + s["missing"]}


# ---------------------------------------------------------------------------
# Compras partilhadas: comprar o MÁXIMO, não a soma
# ---------------------------------------------------------------------------
# André, 2026-09-07: *"indicas onde está a carta, para (...) não ter que comprar
# múltiplos para todos."* O `noutra` já dizia isso das cópias que ELE TEM. Faltava
# o outro lado: as que ainda vai comprar servem as caixas todas exactamente da
# mesma maneira — uma cópia de cada vez, indo buscá-la à caixa onde está.
#
# Somar as faltas caixa a caixa contradiz a regra dele. Na base de 2026-09-07,
# quatro caixas de Premodern pediam 5 Swords to Plowshares PT ao todo quando 2
# chegam (ficam 5 no total e cada caixa fecha, uma de cada vez); Brushland pedia
# 9 e chegam 3; e o Lion's Eye Diamond do cEDH aparecia duas vezes, uma por caixa
# — 535 € a mais numa carta só.
#
# A conta é `max`, não `soma`: `comprar = max(0, max_caixa(precisa) - o que já
# tem)`, que é o mesmo que `max_caixa(comprar_da_caixa)` porque cada caixa já
# desconta o que vê. O resto das caixas passa a "ir buscar" — que é o que vai
# mesmo acontecer assim que a carta chegar a casa.
def pool_compra(s: dict) -> tuple[str, str, str]:
    """A chave do POOL DE MATERIAL de uma caixa: o que ela aceita comprar.

    Duas caixas só partilham uma compra se a MESMA cópia servir as duas. Uma
    Swords to Plowshares PT da era não serve o Cloud (que só usa foil), e uma EN
    non-foil do cEDH não serve o Modern (que a quer foil).
    """
    return (s.get("edicoes") or "", s.get("acabamento") or "", s.get("lingua") or "")


def pools_de_compra(slots) -> dict[str, tuple[str, str, str]]:
    """`slot -> chave do pool`, já com os pools que SE TOCAM fundidos.

    O Duel Commander é *"apenas foil"* e não exige língua; o SPML é *"tudo foil e
    inglês"*. Uma cópia **EN foil** serve os dois, por isso são um pool só — e o
    material do pool é o mais exigente (EN foil), senão a partilha mandava-o
    comprar uma foil PT que a caixa de Modern depois recusa.

    A fusão só se faz quando não há dúvida: um grupo sem língua junta-se ao grupo
    com o mesmo acabamento/edições **se houver exactamente uma** língua exigida
    nesse acabamento. Com duas (uma caixa de foil PT e outra de foil EN) não se
    escolhe por ele — cada uma compra a sua.
    """
    base = {s["slot"]: pool_compra(s) for s in slots if s.get("slot")}
    linguas: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ed, ac, ln in base.values():
        if ln:
            linguas[(ed, ac)].add(ln)
    out = {}
    for slot, (ed, ac, ln) in base.items():
        if not ln and len(linguas.get((ed, ac), ())) == 1:
            ln = next(iter(linguas[(ed, ac)]))
        out[slot] = (ed, ac, ln)
    return out


def _slot_do_pool(chave: tuple[str, str, str]) -> dict:
    """Um slot de mentira com as regras do pool, para reusar os rótulos."""
    ed, ac, ln = chave
    return {"edicoes": ed or None, "acabamento": ac or None, "lingua": ln or None}


def partilhar_compras(slots: list[dict]) -> list[dict]:
    """Funde as compras da mesma carta e do mesmo material feitas por caixas
    diferentes. Muda as linhas de `missing` no sítio; devolve o que fundiu.

    Regras (André, 2026-09-07):
      * compra-se o **máximo** que uma caixa precisa, não a soma das caixas;
      * as cópias compradas ficam atribuídas à caixa de **maior prioridade** que
        as pediu, e as outras passam a **ir buscar** (`noutra`) — a mesma leitura
        de sempre, com a diferença de a cópia ainda não estar em casa. Fica em
        `noutra_futura` para a página o poder dizer;
      * as faltas **dentro da mesma caixa** (main + side) continuam a somar: são
        cópias que estão na mesa ao mesmo tempo;
      * uma caixa com `compras_dedicadas: true` no `colecao_config.json` fica de
        fora — compra as suas e não conta com trocas.

    O que NÃO muda: `got`/`tenho`/`pct`/`missing`. A caixa continua a ter a falta
    até a compra chegar; o que muda é de quem é a compra.
    """
    pools = pools_de_compra(slots)
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for s in slots:
        chave = pools.get(s["slot"])
        # Uma caixa de compras dedicadas é o seu próprio grupo: nunca chega aos
        # dois membros que a partilha exige, e por isso sai daqui intacta. Uma
        # caixa `dedicado` implica-o — *"vou precisar de múltiplos para os decks
        # de premodern"* (André, 2026-09-07, 19:00): se não empresta nem vai
        # buscar, também não pode contar com uma compra de outra caixa.
        dedicada = ((s["slot"],)
                    if s.get("compras_dedicadas") or s.get("dedicado") else ())
        por_carta: dict[str, list[dict]] = defaultdict(list)
        for m in s.get("missing") or []:
            if m["comprar"] > 0:
                por_carta[m["nm"]].append(m)
        for nm, linhas in por_carta.items():
            grupos[(nm, chave) + dedicada].append(
                {"s": s, "linhas": linhas, "q": sum(m["comprar"] for m in linhas)})

    partilhas = []
    for (nm, chave, *_), quem in sorted(grupos.items(), key=lambda kv: kv[0][:2]):
        if len(quem) < 2:
            continue
        quem.sort(key=lambda x: x["s"]["prioridade"])
        alvo = max(x["q"] for x in quem)
        restante = alvo
        for x in quem:                    # a compra é de quem aloca primeiro
            x["dar"] = min(x["q"], restante)
            restante -= x["dar"]
        doadores = [(x["s"]["nome"], x["dar"]) for x in quem if x["dar"]]
        req, mat = requisito_material(_slot_do_pool(chave)), marca_compra(_slot_do_pool(chave))
        for x in quem:
            # Cada caixa vai buscar a quem COMPROU, e nunca a si própria: as
            # cópias que ela paga já contam para o que tem.
            disp = [[n, q] for n, q in doadores if n != x["s"]["nome"]]
            resta = x["dar"]
            for m in sorted(x["linhas"], key=lambda m: (m["board"] != "main", m["nm"])):
                fica = min(m["comprar"], resta)
                resta -= fica
                move = m["comprar"] - fica
                m["comprar"] = fica
                m["cost"] = round((m["unit"] or 0) * fica, 2)
                m["req_compra"], m["marca_compra"] = req, mat
                for par in disp:
                    if move <= 0:
                        break
                    pega = min(par[1], move)
                    if pega <= 0:
                        continue
                    par[1] -= pega
                    move -= pega
                    m["noutra"][par[0]] = m["noutra"].get(par[0], 0) + pega
                    m["noutra_futura"][par[0]] = m["noutra_futura"].get(par[0], 0) + pega
                m["noutra_q"] = sum(m["noutra"].values())
        partilhas.append({
            "nm": nm, "req": req, "marca": mat, "comprar": alvo,
            "soma": sum(x["q"] for x in quem), "poupado": sum(x["q"] for x in quem) - alvo,
            "caixas": [{"slot": x["s"]["slot"], "caixa": x["s"]["nome"],
                        "prioridade": x["s"]["prioridade"], "pediu": x["q"],
                        "compra": x["dar"]} for x in quem]})
    partilhas.sort(key=lambda p: (-p["poupado"], p["nm"]))
    return partilhas


def _totais_do_slot(s: dict) -> None:
    """Os números de uma caixa que dependem das linhas em falta.

    Vive à parte porque a partilha de compras (`partilhar_compras`) mexe nas
    linhas DEPOIS de a alocação as ter escrito — e um total calculado antes disso
    ficava a dizer que se compram cópias que já ninguém compra.
    """
    missing = s["missing"]
    s["missing"] = sorted(missing, key=lambda r: -(r["cost"] or 0))
    s["custo"] = round(sum(m["cost"] or 0 for m in missing), 2)
    s["faltam"] = sum(m["missing"] for m in missing)
    s["comprar"] = sum(m["comprar"] for m in missing)
    s["noutra"] = sum(m["noutra_q"] for m in missing)
    # Cópias a comprar SEM preço na base. O `cost` delas é 0 e some no total —
    # o "fechar por X €" fica sistematicamente abaixo do real e ninguém dá por
    # isso. É a mesma família do `event_tier`: um valor em falta que não dá erro,
    # dá um número errado. Contar aqui deixa a página dizer que o custo é um
    # mínimo, em vez de o apresentar como se fosse a conta toda.
    s["sem_preco"] = sum(m["comprar"] for m in missing
                         if m["comprar"] > 0 and m["unit"] is None)
    # As que estão noutra caixa: é "ir buscar", não "comprar". Ficam à parte
    # para a página e o CLI poderem dizer as duas coisas sem as somar.
    s["noutra_caixa"] = sorted((m for m in missing if m["noutra_q"]),
                               key=lambda m: (-m["noutra_q"], m["nm"]))


# ---------------------------------------------------------------------------
# Alocação
# ---------------------------------------------------------------------------
def allocate(con, cfg_slots: list[dict] | None = None) -> dict:
    """Aloca a colecção aos slots do loadout, por ordem de prioridade.

    Devolve {"slots": [...], "conflitos": [...], "pedido": {...}, "lots": {...}}.
    Cada slot traz `have`/`missing`/`subs` (substitutos: existe mas não serve) e
    o custo de fechar. Uma cópia física entra numa caixa e só numa.
    """
    slots = resolve_slots(con, cfg_slots)
    pool = lots(con, slots)
    dids = _deck_ids(con, slots)
    baldes = {s["balde"] for s in slots if s.get("balde")}
    # As caixas que SÃO um deck montado: só nessas é que a cópia lá dentro
    # escapa às regras de material (ver `_porque_nao`).
    caixas = caixas_de_deck(slots)
    # As caixas que não emprestam nem vão buscar (Pauper, cEDH, Premodern).
    ded = dedicadas(slots)
    pedido: dict[str, int] = defaultdict(int)
    # carta -> [(slot, quanto pediu, quanto levou)], para o detalhe do conflito
    disputa: dict[str, list[dict]] = defaultdict(list)

    for s in slots:
        did = dids.get(s["slot"])
        foil = s.get("acabamento") == "foil"
        have, missing, subs = [], [], []
        usadas = 0
        precisa = 0
        pediu_slot: dict[str, int] = defaultdict(int)
        levou_slot: dict[str, int] = defaultdict(int)
        # (lote, outra caixa) -> quantas cópias já foram prometidas a uma linha
        # ANTERIOR deste slot. Sem isto, uma carta que está no main E no side
        # reclamava a mesma cópia física duas vezes: 4 Seal of Cleansing na caixa
        # do lado davam 3 "ir buscar" ao main mais 1 ao side de um deck que só
        # tem 4 para dar. É a mesma armadilha do `livre`, um nível acima.
        reclamado: dict[tuple[tuple, str], int] = defaultdict(int)
        for board, nm, need in s["cards"]:
            pedido[nm] += need
            pediu_slot[nm] += need
            basica = nm in BASICS
            precisa += need
            if basica:                     # básicas: assume-se que as tem sempre
                usadas += need
                have.append(_linha_cheia({"board": board, "nm": nm, "need": need,
                                          "got": need, "basica": True, "lotes": []}))
                continue
            falta = need
            gastos = []
            cands = sorted(pool.get(nm, []), key=lambda l: _ordem(l, s))
            for lot in cands:
                if falta <= 0:
                    break
                if lot["livre"] <= 0:
                    continue
                if lot["rdid"] is not None and lot["rdid"] != did:
                    continue              # dedicada a outro deck (regra de domínio)
                if _noutra_caixa(lot, s):
                    continue              # está sleevada dentro de outra caixa
                if _fora_de_vista(lot, s) or _porque_nao(lot, s, baldes, caixas):
                    continue
                take = min(lot["livre"], falta)
                lot["livre"] -= take
                falta -= take
                lot["alocado"][s["nome"]] = lot["alocado"].get(s["nome"], 0) + take
                gastos.append({"id": lot["id"], "q": take, "sub": lot["sub"],
                               "local": lot["local"], "balde": lot["balde"],
                               "caixa": lot["caixa"],
                               "borigem": lot["borigem"],
                               "finish": lot["finish"], "lang": lot["lang"],
                               "set_code": lot["set_code"], "sid": lot["sid"]})
            got = need - falta
            usadas += got
            levou_slot[nm] += got
            linha = {"board": board, "nm": nm, "need": need, "got": got,
                     "basica": False, "lotes": gastos}
            if falta:
                # ONDE ESTÁ A CARTA (André, 2026-09-07): antes de dizer "falta",
                # ver se a cópia que servia esta caixa foi para OUTRA. Se foi, não
                # se compra — vai-se buscar. Só conta a cópia que SERVE mesmo este
                # slot: uma que a caixa nem vê (Caixa RL no Premodern) ou que não
                # serve na língua/acabamento continua a ser compra.
                noutra: dict[str, int] = defaultdict(int)
                resta = falta
                for lot in cands:
                    if resta <= 0:
                        break
                    if lot["rdid"] is not None and lot["rdid"] != did:
                        continue
                    if _fora_de_vista(lot, s) or _porque_nao(lot, s, baldes, caixas):
                        continue
                    # Uma cópia já SLEEVADA noutra caixa é dessa caixa por
                    # inteiro, tenha essa caixa corrido antes ou depois desta —
                    # é a razão de o `alocado` não chegar aqui.
                    donos = ([(lot["caixa_nome"], lot["q"])] if _noutra_caixa(lot, s)
                             else list(lot["alocado"].items()))
                    for outro, q in donos:
                        if outro == s["nome"] or resta <= 0:
                            continue
                        # CAIXAS DEDICADAS (2026-09-07, 19:00): uma caixa
                        # dedicada não vai buscar nem empresta. Sem esta linha o
                        # Enchantress continuava a dizer "vai buscar os 3
                        # Brushland ao UW Replenish" — e ele quer os decks
                        # montados ao mesmo tempo, não emprestados.
                        if not _empresta(s, outro, ded):
                            continue
                        disponivel = q - reclamado[(lot["key"], outro)]
                        if disponivel <= 0:
                            continue
                        pega = min(disponivel, resta)
                        reclamado[(lot["key"], outro)] += pega
                        noutra[outro] += pega
                        resta -= pega
                # Existe mas não serve: é a diferença entre "não tenho" e "tenho
                # a carta errada". São coisas diferentes na hora de comprar.
                alt = defaultdict(int)
                alt_onde: dict[str, int] = defaultdict(int)   # onde estão essas
                for lot in cands:
                    if lot["livre"] <= 0 or (lot["rdid"] is not None and lot["rdid"] != did):
                        continue
                    if _fora_de_vista(lot, s) or _noutra_caixa(lot, s):
                        continue      # a Caixa RL não existe para o Premodern; e
                                      # o que está noutra caixa é "ir buscar",
                                      # não "tenho a carta errada"
                    razao = _porque_nao(lot, s, baldes, caixas)
                    if razao:
                        alt[razao] += lot["livre"]
                        alt_onde[lot["local"]] += lot["livre"]
                        # Marca o exemplar como SUBSTITUTO: serve este slot, só não
                        # na língua/acabamento que ele pediu. Sem esta marca a
                        # venda mandava-o embora. O caso que obrigou a inventá-la
                        # foram as 4 Opalescence EN — que desde 2026-09-07 já nem
                        # chegam aqui: nenhuma EN é substituto de um slot de
                        # Premodern (ver `_fora_de_vista`), e por decisão dele
                        # essas vão mesmo para a venda a confirmar. A marca
                        # continua a valer para as nonfoil dos slots de foil.
                        lot["substituto"][s["nome"]] = razao
                unit, pfin = card_price(con, nm, "foil" if foil else "nonfoil")
                noutra_q = sum(noutra.values())
                comprar = falta - noutra_q
                linha.update(missing=falta, comprar=comprar,
                             noutra=dict(noutra), noutra_q=noutra_q,
                             noutra_futura={},
                             req_compra=requisito_material(s),
                             marca_compra=marca_compra(s),
                             unit=unit, price_finish=pfin,
                             cost=round((unit or 0) * comprar, 2),
                             alt={k: v for k, v in alt.items()},
                             alt_onde={k: v for k, v in alt_onde.items()})
                missing.append(linha)
                if alt:
                    subs.append(linha)
            else:
                have.append(_linha_cheia(linha))
        # CAIXA CONGELADA (André, 2026-09-07: *"apenas mexer para actualizar"*).
        # As cópias que estão fisicamente nesta caixa e que a lista de HOJE já
        # não pede ficam PRESAS: não voltam à gaveta, não são realocadas e não
        # entram na venda. É o que faz a caixa continuar montada com a lista
        # antiga quando o Luffy troca duas cartas — a diferença sai depois como
        # delta de actualização (`plano_arrumacao`), e só se aplica no botão
        # "actualizei". Sem isto, uma corrida do dia seguinte desmontava no papel
        # um deck que está sleevado na estante.
        presos = []
        if s["congelada"]:
            for lotes in pool.values():
                for lot in lotes:
                    if lot.get("caixa") != s["slot"] or lot["livre"] <= 0:
                        continue
                    presos.append({"nm": lot["nm"], "q": lot["livre"],
                                   "de": s["nome"], "para": lot["balde"],
                                   "slot": s["slot"], "copy_id": lot["id"],
                                   "sid": lot["sid"], "finish": lot["finish"],
                                   "lang": lot["lang"],
                                   "set_code": lot["set_code"],
                                   "sentido": "sai"})
                    lot["livre"] = 0
        s["presos"] = sorted(presos, key=lambda m: m["nm"])
        for nm, q in pediu_slot.items():
            disputa[nm].append({"slot": s["nome"], "prioridade": s["prioridade"],
                                "pediu": q, "levou": levou_slot.get(nm, 0),
                                "dedicado": s["dedicado"]})
        s["have"] = sorted(have, key=lambda r: (r["board"] != "main", r["nm"]))
        s["missing"] = missing
        s["subs"] = subs
        s["precisa"] = precisa
        s["tenho"] = usadas
        s["pct"] = round(100 * usadas / precisa) if precisa else 0
        _totais_do_slot(s)
        # De onde saem as cartas desta caixa. É a outra metade do "onde está a
        # carta": as que faltam dizem em que caixa estão, e estas dizem de que
        # prateleira as tirar para montar. Daqui vem o `Caixa RL (PT)`/`(EN)`.
        origens: dict[str, int] = defaultdict(int)
        for m in have:
            for g in m["lotes"]:
                origens[g["local"]] += g["q"]
        s["origens"] = dict(sorted(origens.items(), key=lambda kv: (-kv[1], kv[0])))

    # COMPRAS PARTILHADAS: duas caixas que querem a mesma carta no mesmo material
    # não pedem duas compras — pedem uma, e a segunda vai lá buscá-la. Corre
    # DEPOIS da alocação toda, porque precisa das faltas de todas as caixas, e
    # obriga a refazer os totais de cada uma.
    partilhas = partilhar_compras(slots)
    for s in slots:
        _totais_do_slot(s)

    # CARTAS PARTILHADAS ENTRE CAIXAS (chamava-se "conflito" até 2026-09-07; a
    # chave `conflitos` fica, para não partir quem já a lê): duas ou mais caixas
    # querem a mesma carta e não há cópias para todas. A leitura mudou com a regra
    # do André — `ficam_com` é QUEM A TEM e `ficam_sem` é quem a VAI BUSCAR ali,
    # não quem tem de a comprar. Uma caixa sozinha a que falta uma carta continua
    # a não entrar aqui: é falta, e resolve-se a comprar.
    conflitos = []
    for nm, quem in disputa.items():
        if len(quem) < 2 or nm in BASICS:
            continue
        if all(q["levou"] >= q["pediu"] for q in quem):
            continue                     # chegou para todos: não há disputa
        if not sum(l["q"] for l in pool.get(nm, [])):
            continue                     # não tem nenhuma: é falta, não disputa
        conflitos.append({
            "nm": nm, "pedido": pedido[nm],
            "tenho": sum(l["q"] for l in pool.get(nm, [])),
            "por_slot": sorted(quem, key=lambda q: q["prioridade"]),
            "ficam_com": sorted({q["slot"] for q in quem if q["levou"]}),
            "ficam_sem": sorted({q["slot"] for q in quem if q["levou"] < q["pediu"]}),
        })
    conflitos.sort(key=lambda c: (-(c["pedido"] - c["tenho"]), c["nm"]))
    return {"slots": slots, "conflitos": conflitos, "pedido": dict(pedido),
            "partilhas": partilhas, "pool": pool}


# ---------------------------------------------------------------------------
# Venda
# ---------------------------------------------------------------------------
def caixas_de_deck(slots) -> set[str]:
    """Baldes que são a CAIXA de um deck, e não colecção.

    São os que o `colecao_config.json -> regras_colecao` já nomeia — o CLAUDE.md
    diz-lhes "coleção própria + lista vigiada" (Blue Farm, Cloud, Cloud cEDH,
    Pauper Affinity) — mais o balde de qualquer slot de Commander do loadout, que
    é uma caixa de deck por definição mesmo que ainda não tenha regra escrita.

    Tudo o resto (a `Colecção` e a `Caixa Reserved List` — antes da migração, o
    SPML e o Premodern (geral)) é COLECÇÃO e partilha um único limite de playset.
    Contar 4 por balde deixava passar o dobro: 4 Intuition no Premodern mais 4 na
    Caixa RL são 8 da mesma carta.

    Um balde de COLECÇÃO nunca é caixa de deck, mesmo que um slot de Commander o
    aponte como o seu — depois da migração todas as caixas apontam para a
    `Colecção`, e sem esta linha a colecção inteira passava a "estar dentro de um
    deck" e escapava às regras de material.
    """
    caixas = set(_retencao()) - set(baldes_coleccao())
    for s in slots:
        if (s.get("balde") and s.get("formato") in COMMANDER_FORMATS
                and s["balde"] not in baldes_coleccao()):
            caixas.add(s["balde"])
    return caixas


def sell_list(con, res: dict) -> dict:
    """O que sobra depois de alocar e de guardar o backup permitido.

    A regra é por COLECÇÃO, como o CLAUDE.md diz ("cada pasta é uma coleção com a
    sua regra"), mas o limite de playset é sobre a colecção INTEIRA, não por
    balde: quatro Intuition no balde Premodern mais quatro na Caixa Reserved List
    são oito cópias da mesma carta, e o playset são 4 — contar 4 por balde deixava
    passar o dobro.

      * caixas de deck de Commander -> 1 por deck que a usa (singleton);
      * o resto da colecção          -> 4 por carta (playset), a somar todos os
                                        baldes de colecção;
      * básicas                      -> nunca;
      * não legal em formato nenhum  -> vender tudo o que não foi alocado.

    Três saídas separadas, porque têm riscos diferentes e misturá-las dava um
    total que não se pode usar:
      `venda`     — o excedente normal;
      `venda_rl`  — Reserved List: cartas que não se voltam a imprimir. É a maior
                    fatia do valor e a decisão menos reversível — vai à parte
                    para ser confirmada uma a uma;
      `guardar`   — SUBSTITUTOS: cópias que servem um deck do loadout e só não
                    fecham o slot por causa da língua ou do acabamento (as
                    nonfoil dos slots de foil). Nenhuma EN entra aqui pelo lado
                    do Premodern: desde 2026-09-07 essas caixas só vêem PT, e o
                    que sobrar do playset em EN vai para `venda`/`venda_rl` a
                    confirmar;
      `retidos`   — baldes com `reter_extras_meses`. A regra dos 6 meses precisa
                    de uma data de última utilização que ainda não existe (ver
                    CLAUDE.md), por isso estes extras GUARDAM-SE e dizem-no, em
                    vez de entrarem na venda como se a regra já corresse.
    """
    pool = res["pool"]
    retidos_baldes = _retencao()
    caixas = caixas_de_deck(res["slots"])
    # Quantas cópias cada caixa de Commander pede de cada carta. A chave é o
    # GRUPO (ver abaixo): o `slot` da caixa no modelo novo, e o balde no antigo —
    # os dois, para a mesma regra valer antes e depois da migração.
    cmd_need: dict[tuple[str, str], int] = defaultdict(int)
    # `grupo -> meses de retenção`, pela mesma dupla chave.
    reter_grupo: dict[str, int] = {}
    # As caixas que contam como um GRUPO à parte no playset — as de deck, as
    # mesmas que os baldes `caixas_de_deck` sempre foram. Uma caixa de Premodern
    # ou de Modern NÃO entra aqui: essas cartas são colecção arrumada num deck e
    # partilham o limite de 4 com tudo o resto. Sem esta distinção, confirmar a
    # arrumação dava a cada caixa um playset próprio e a lista de venda encolhia
    # de 91 cópias para 54 sem ninguém pedir — é a mesma armadilha do "4 por
    # balde" que o playset da colecção inteira veio corrigir.
    grupos_proprios = {s["slot"] for s in res["slots"]
                       if s.get("balde") and s["balde"] in caixas}
    for s in res["slots"]:
        if s.get("balde") and s["balde"] in retidos_baldes:
            reter_grupo[s["slot"]] = retidos_baldes[s["balde"]]
        if s["formato"] not in COMMANDER_FORMATS:
            continue
        for chave in (s.get("slot"), s.get("balde")):
            if not chave:
                continue
            for _b, nm, q in s["cards"]:
                cmd_need[(chave, nm)] = max(cmd_need[(chave, nm)], q)

    venda, venda_rl, retidos, guardar = [], [], [], []
    for nm, ls in pool.items():
        if nm in BASICS:
            continue
        legal = _legal_em(ls[0]["leg"], REAL_FORMATS)
        # Grupos: cada caixa de deck é o seu grupo; toda a colecção é UM grupo.
        # No modelo de colecção única a caixa já não é um balde — é a arrumação
        # confirmada (`lot["caixa"]`). Sem esta linha, as cópias a mais de um
        # deck de Commander passavam a caber no playset de 4 em vez de 1 por
        # deck, e a lista de venda encolhia sem ninguém pedir.
        grupos: dict[str, list[dict]] = defaultdict(list)
        for lot in ls:
            caixa = lot.get("caixa")
            grupos[caixa if caixa in grupos_proprios
                   else (lot["sub"] if lot["sub"] in caixas else "")].append(lot)
        for grupo, lotes in grupos.items():
            if sum(l["livre"] for l in lotes) <= 0:
                continue
            alocado = sum(l["q"] - l["livre"] for l in lotes)
            if grupo and (grupo, nm) in cmd_need:
                limite = max(alocado, cmd_need[(grupo, nm)])
                razao = "excedente (Commander: 1 por deck)"
            elif legal:
                limite = max(alocado, CONSTRUCTED_LIMIT)
                razao = f"excedente (mais de {CONSTRUCTED_LIMIT})"
            else:
                limite = alocado
                razao = "não joga em formato nenhum"
            resto = sum(l["q"] for l in lotes) - limite
            if resto <= 0:
                continue
            # Vender primeiro o que menos falta faz: os substitutos por último
            # (servem um deck), depois as que não são Reserved List, depois as
            # nonfoil, e as PT no fim — são as que servem o Premodern, o único
            # formato onde ele exige a língua.
            for lot in sorted(lotes, key=lambda l: (bool(l["substituto"]), l["rl"],
                                                    l["finish"] in FOIL_FINISHES,
                                                    l["lang"] == "pt", l["key"])):
                if resto <= 0:
                    break
                take = min(lot["livre"], resto)
                if take <= 0:
                    continue
                resto -= take
                unit, pfin = card_price(con, nm, lot["finish"])
                linha = {"nm": nm, "sub": lot["sub"], "local": lot["local"],
                         "q": take,
                         # Que exemplares são, para o botão "vendida" do modo
                         # edição os poder tirar da base. Sem isto a linha era
                         # só texto e a única maneira de registar uma venda era
                         # editar a `copies` à mão.
                         "copias": [[lot["id"], take]],
                         "finish": lot["finish"], "lang": lot["lang"],
                         "set_code": lot["set_code"], "set_name": lot["set_name"],
                         "sid": lot["sid"], "rl": lot["rl"], "unit": unit,
                         "price_finish": pfin,
                         "total": round((unit or 0) * take, 2), "reason": razao,
                         "reter": (reter_grupo.get(grupo)
                                   or retidos_baldes.get(lot["sub"])),
                         "substituto": dict(lot["substituto"])}
                if linha["substituto"]:
                    quem = ", ".join(sorted(linha["substituto"]))
                    linha["reason"] = f"serve {quem} ({'; '.join(sorted(set(linha['substituto'].values())))})"
                    guardar.append(linha)
                elif linha["reter"]:
                    retidos.append(linha)
                else:
                    (venda_rl if lot["rl"] else venda).append(linha)

    def _fecha(rows):
        # Junta lotes iguais: dois lotes da mesma impressão são a mesma linha na
        # lista de venda, e apareciam duas vezes só porque entraram em alturas
        # diferentes.
        junto: dict[tuple, dict] = {}
        for r in rows:
            k = (r["nm"], r["local"], r["finish"], r["lang"], r["set_code"],
                 r["reason"])
            if k in junto:
                junto[k]["q"] += r["q"]
                junto[k]["copias"] = junto[k]["copias"] + r["copias"]
                junto[k]["total"] = round((junto[k]["unit"] or 0) * junto[k]["q"], 2)
            else:
                junto[k] = dict(r)
        out = sorted(junto.values(), key=lambda r: (-(r["total"] or 0), r["nm"]))
        return {"linhas": out, "total": round(sum(r["total"] or 0 for r in out), 2),
                "copias": sum(r["q"] for r in out)}

    v, vrl, ret, gd = (_fecha(venda), _fecha(venda_rl), _fecha(retidos),
                       _fecha(guardar))
    return {"venda": v["linhas"], "venda_rl": vrl["linhas"],
            "retidos": ret["linhas"], "guardar": gd["linhas"],
            "total": v["total"], "copias": v["copias"],
            "total_rl": vrl["total"], "copias_rl": vrl["copias"],
            "total_retido": ret["total"], "copias_retidas": ret["copias"],
            "total_guardar": gd["total"], "copias_guardar": gd["copias"]}


def ficheiro_vendas() -> Path:
    """`data/vendas.csv` — o registo do que saiu da colecção.

    Vive ao lado da base (`MTGVAULT_HOME`) e não dentro dela: a `vault.db` é
    descarregada e republicada inteira a cada corrida, e um registo de vendas
    que se pode perder numa publicação não é um registo. É um CSV para ele o
    poder abrir no Excel e conferir contra o extracto do Cardmarket.
    """
    # Importa-se aqui e não no topo porque o `db` fixa o `MTGVAULT_HOME` no
    # momento do import, e este módulo é importado por páginas que definem essa
    # variável logo antes. Lê-se quando se usa, não quando se carrega.
    from . import db                      # noqa: PLC0415
    return Path(db.ROOT) / "vendas.csv"


CABECALHO_VENDAS = ("data,carta,edicao,lingua,acabamento,quantidade,"
                    "preco_referencia,onde_estava,motivo")


def chave_venda(r: dict) -> str:
    """A identidade de uma LINHA da lista de venda, para o botão "vendida".

    É exactamente a chave por que o `_fecha` junta os lotes iguais. Vive aqui
    para a página e o servidor concordarem: se a página inventasse a sua, um
    botão passava a apontar para outra linha e ele vendia a carta errada.
    """
    return "|".join([r["nm"], r["local"], r["finish"] or "", r["lang"] or "",
                     (r["set_code"] or "").upper(), r["reason"] or ""])


def registar_venda(con, linha: dict, quantidade: int | None = None,
                   csv_path: Path | None = None) -> dict:
    """"Vendida": tira as cópias da colecção e escreve-o no `vendas.csv`.

    É a última metade do que o André pediu para hoje (2026-09-08): *"começar a
    comprar as faltas e livrar-me dos excessos de cartas."* Até aqui a lista de
    venda era só uma sugestão a ler; tirar a carta da base era editar a `copies`
    à mão, e por isso a lista repetia todos os dias as cartas que ele já tinha
    vendido.

    Duas decisões que valem a pena estar escritas:
      * a cópia **sai da base** (a quantidade desce; a linha desaparece quando
        chega a zero) em vez de ficar marcada como vendida. O vault conta cópias
        físicas e uma cópia vendida já não está em casa — deixá-la lá com uma
        bandeira era pedir a toda a consulta futura que se lembrasse da bandeira;
      * o **registo fica no CSV**, com o preço de referência do dia. É o que
        permite conferir depois quanto rendeu, sem guardar histórico na base.

    A escrita é atómica no sentido que importa: primeiro a linha do CSV, depois a
    base. Se a base falhar a meio, sobra uma linha no CSV que ele vê e corrige —
    o contrário (tirar a carta e não registar) é uma perda silenciosa.
    """
    pedidos = [[int(c), int(q)] for c, q in (linha.get("copias") or [])]
    total = quantidade if quantidade is not None else sum(q for _c, q in pedidos)
    total = max(0, min(total, sum(q for _c, q in pedidos)))
    if not total:
        return {"copias": 0, "linhas": 0}
    alvo = csv_path or ficheiro_vendas()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    novo = not alvo.exists()
    campos = [linha.get("nm") or "", (linha.get("set_code") or "").upper(),
              linha.get("lang") or "", linha.get("finish") or "", str(total),
              ("" if linha.get("unit") in (None, "") else f'{linha["unit"]:.2f}'),
              linha.get("local") or "", linha.get("reason") or ""]
    with alvo.open("a", encoding="utf-8", newline="") as fh:
        if novo:
            fh.write(CABECALHO_VENDAS + "\n")
        fh.write(date.today().isoformat() + ","
                 + ",".join('"' + str(c).replace('"', "'") + '"' for c in campos)
                 + "\n")
    resta, tocadas = total, 0
    for cid, q in pedidos:
        if resta <= 0:
            break
        leva = min(q, resta)
        row = con.execute("SELECT quantity FROM copies WHERE id = ?", (cid,)).fetchone()
        if row is None:
            continue
        leva = min(leva, row["quantity"] or 0)
        if leva <= 0:
            continue
        resta -= leva
        tocadas += 1
        if (row["quantity"] or 0) - leva <= 0:
            con.execute("DELETE FROM copies WHERE id = ?", (cid,))
        else:
            con.execute("UPDATE copies SET quantity = quantity - ? WHERE id = ?",
                        (leva, cid))
        # Uma cópia vendida não podia estar dentro de uma caixa (o que está
        # alocado nunca entra na venda), mas se estivesse ficava uma linha órfã
        # a mentir para sempre — a `copy_allocation` não tem FK entre bases.
        try:
            con.execute("DELETE FROM copy_allocation WHERE copy_id = ?", (cid,))
        except sqlite3.OperationalError:
            pass                          # base antiga, ainda sem a tabela
    con.commit()
    return {"copias": total - resta, "linhas": tocadas, "csv": str(alvo)}


# ---------------------------------------------------------------------------
# Arrumação física: pôr a estante igual à alocação
# ---------------------------------------------------------------------------
def movimentos_de_entrada(s: dict, caixas: set[str] | frozenset) -> list[dict]:
    """As cópias que a alocação deu a esta caixa e que ainda não estão lá dentro.

    É o mesmo cálculo para os dois gestos que o André faz: **montar** a caixa
    pela primeira vez (o painel Montar, v6) e **arrumar** a estante toda depois
    de a alocação mudar. Vive numa função só de propósito — a v5 tinha-o inline
    no `plano_arrumacao`, e o painel Montar era a segunda oportunidade de as
    duas listas discordarem em silêncio.

    `caixas` = os baldes que SÃO a caixa de um deck. Antes da migração para a
    colecção única a caixa de um deck ainda é um balde (`Pauper Affinity`,
    `Cloud`, ...): uma cópia que já vive lá já está dentro da caixa, mesmo que o
    balde e a caixa tenham nomes diferentes. Sem isso o plano mandava-o
    "arrumar" 54 cartas que já estão sleevadas.
    """
    ja_la = s.get("balde") if s.get("balde") in caixas else None
    out = []
    for m in s["have"]:
        for g in m["lotes"]:
            if g["local"] == s["nome"]:
                continue                  # já lá está
            if g["caixa"] is None and ja_la and g["sub"] == ja_la:
                continue                  # está no balde que É esta caixa
            out.append({"nm": m["nm"], "q": g["q"], "de": g["local"],
                        "para": s["nome"], "slot": s["slot"],
                        "copy_id": g["id"], "sid": g["sid"],
                        "finish": g["finish"], "lang": g["lang"],
                        "set_code": g["set_code"], "sentido": "entra"})
    return out


def plano_montar(res: dict, slot_id: str) -> dict:
    """MONTAR uma caixa: o que se tira das gavetas e o que se devolve a elas.

    André, 2026-09-08: *"Espero começar a montar os decks em deckbox o mais cedo
    possível para começar a comprar as faltas e livrar-me dos excessos de
    cartas."* O painel **Montar** da aba de cada caixa é isto, mais a wantlist
    dela — os dois passos, por esta ordem.

    `tirar` são as cópias exactas (com edição, língua e acabamento: dois lotes
    do mesmo nome não são a mesma pilha), `devolver` são as que estão lá dentro
    e a lista de hoje já não pede — nas caixas congeladas é o delta de
    actualização, nas outras já saiu na arrumação geral. `ja` são as que já lá
    estão: uma caixa a meio montar tem de dizer o que falta, não a lista toda.
    """
    s = next((x for x in res["slots"] if x["slot"] == slot_id), None)
    if s is None:
        return {}
    tirar = movimentos_de_entrada(s, caixas_de_deck(res["slots"]))
    devolver = list(s.get("presos") or [])
    dentro = sum(g["q"] for m in s["have"] for g in m["lotes"])
    por_gaveta: dict[str, int] = defaultdict(int)
    for m in tirar:
        por_gaveta[m["de"]] += m["q"]
    return {"slot": s["slot"], "caixa": s["nome"], "tirar": tirar,
            "devolver": sorted(devolver, key=lambda m: m["nm"]),
            "copias": sum(m["q"] for m in tirar),
            "ja": dentro - sum(m["q"] for m in tirar),
            "por_gaveta": dict(sorted(por_gaveta.items(),
                                      key=lambda kv: (-kv[1], kv[0])))}


def ordem_de_montagem(res: dict) -> list[dict]:
    """Por que ordem montar as caixas, e quanto custa cada uma.

    André, 2026-09-08: *"Espero começar a montar os decks em deckbox o mais cedo
    possível."* A ordem é a que faz sentido à frente da estante e não a da
    alocação: primeiro os **permanentes** por prioridade (são os que já ficaram
    com as cartas), e depois as **candidatas** pela percentagem que já têm —
    começa-se pelo que está mais perto de fechar.

    As que já estão montadas ficam no fim: não há nada a fazer nelas hoje (as
    congeladas trazem o delta de actualização à parte, na aba Arrumar).
    """
    caixas = caixas_de_deck(res["slots"])
    out = []
    for s in res["slots"]:
        if s.get("vazio"):
            continue                     # caixa por escolher: não se monta nada
        tirar = movimentos_de_entrada(s, caixas)
        out.append({
            "slot": s["slot"], "caixa": s["nome"], "formato": s.get("formato"),
            "estado": s.get("estado"), "pct": s["pct"],
            "tenho": s["tenho"], "precisa": s["precisa"],
            "tirar": sum(m["q"] for m in tirar),
            "gavetas": len({m["de"] for m in tirar}),
            "comprar": s["comprar"], "noutra": s["noutra"], "custo": s["custo"],
            "prioridade": s["prioridade"], "permanente": s["permanente"],
            "montado": bool(s.get("montado")), "congelada": bool(s.get("congelada")),
            "req": requisito_material(s)})
    out.sort(key=lambda x: (x["montado"], not x["permanente"],
                            x["prioridade"] if x["permanente"] else -x["pct"]))
    return out


def plano_arrumacao(res: dict) -> dict:
    """As cartas a MOVER para a estante ficar igual à alocação de hoje.

    O André (2026-09-07): *"quero que me ajudem a ser mais organizado com as
    cartas."* O vault sabe onde cada carta DEVE estar (a alocação) e onde ESTÁ (a
    `copy_allocation`, mais o balde de quem ainda não entrou em caixa nenhuma). A
    diferença entre as duas é isto: uma lista de movimentos, agrupada de duas
    maneiras porque são dois gestos diferentes —

      * por **origem** (a gaveta que se abre: `Colecção`, `Caixa RL (PT)`,
        `Caixa RL (EN)`, ou outra deckbox): o que sai de lá e para onde vai;
      * por **destino** (a caixa que se monta): o que entra nela e de onde vem.

    Há dois sentidos de movimento, e os dois contam:
      * **entra** — a alocação deu a cópia a uma caixa e ela ainda não lá está;
      * **sai**  — a cópia está numa caixa mas a alocação de hoje já não a usa
        lá; volta ao balde de onde veio.

    E há um terceiro grupo, desde as CAIXAS CONGELADAS de 2026-09-07 (19:00): uma
    caixa dedicada e montada não se arruma, **actualiza-se**. Os movimentos dela
    saem do plano geral e vão para `actualizacoes[slot]` — *"tirar X, meter Y"* —
    que só se aplicam quando ele carrega em "actualizei" nessa caixa. É a ordem
    dele: *"apenas mexer para actualizar"*.

    Não escreve nada: quem confirma é `guardar_arrumacao` / `actualizar_caixa`.
    """
    # Antes da migração para a colecção única, a caixa de um deck AINDA é um
    # balde (`Pauper Affinity`, `Cloud`, ...). Uma cópia que já vive lá já está
    # dentro da caixa, mesmo que o balde e a caixa tenham nomes diferentes —
    # sem isto o plano mandava-o "arrumar" 54 cartas que já estão sleevadas.
    caixas = caixas_de_deck(res["slots"])
    actualizacoes: dict[str, dict] = {}
    entra: list[dict] = []
    for s in res["slots"]:
        meter = movimentos_de_entrada(s, caixas)
        if not s.get("congelada"):
            entra.extend(meter)
        if s.get("congelada"):
            tirar = list(s.get("presos") or [])
            if meter or tirar:
                actualizacoes[s["slot"]] = {
                    "slot": s["slot"], "caixa": s["nome"],
                    "entra": sorted(meter, key=lambda m: m["nm"]),
                    "sai": tirar,
                    "copias": sum(m["q"] for m in meter + tirar)}
    sai: list[dict] = []
    for lotes in res["pool"].values():
        for lot in lotes:
            if not lot.get("caixa") or lot["livre"] <= 0:
                continue
            # Está na caixa e a alocação de hoje não a usa lá: volta à gaveta.
            sai.append({"nm": lot["nm"], "q": lot["livre"],
                        "de": lot["caixa_nome"], "para": lot["balde"],
                        "slot": lot["caixa"], "copy_id": lot["id"],
                        "sid": lot["sid"], "finish": lot["finish"],
                        "lang": lot["lang"], "set_code": lot["set_code"],
                        "sentido": "sai"})
    movs = sorted(entra + sai, key=lambda m: (m["de"], m["para"], m["nm"]))
    por_origem: dict[str, list[dict]] = defaultdict(list)
    por_destino: dict[str, list[dict]] = defaultdict(list)
    for m in movs:
        por_origem[m["de"]].append(m)
        por_destino[m["para"]].append(m)
    ordena = lambda d: dict(sorted(          # noqa: E731 — só arrumação
        d.items(), key=lambda kv: (-sum(x["q"] for x in kv[1]), kv[0])))
    acts = dict(sorted(actualizacoes.items(),
                       key=lambda kv: (-kv[1]["copias"], kv[1]["caixa"])))
    return {"movimentos": movs, "por_origem": ordena(por_origem),
            "por_destino": ordena(por_destino),
            "copias": sum(m["q"] for m in movs), "linhas": len(movs),
            "actualizacoes": acts,
            "copias_actualizar": sum(a["copias"] for a in acts.values())}


def csv_arrumacao(plano: dict) -> str:
    """O plano em CSV (`moves-<data>.csv`), para ele levar para a mesa.

    Leva também as actualizações das caixas congeladas, com um `sentido` próprio
    (`actualizar-sai` / `actualizar-entra`): são movimentos de outra natureza —
    desmontam e remontam um deck que está na estante — e misturá-los com a
    arrumação normal dava uma lista que ele não podia seguir de cima a baixo.
    """
    linhas = ["sentido,quantidade,carta,de,para,edicao,acabamento,lingua,copy_id"]
    extra = [dict(m, sentido=f'actualizar-{m["sentido"]}')
             for a in plano.get("actualizacoes", {}).values()
             for m in a["sai"] + a["entra"]]
    for m in plano["movimentos"] + extra:
        nm = m["nm"].replace('"', "'")
        linhas.append(f'{m["sentido"]},{m["q"]},"{nm}","{m["de"]}","{m["para"]}",'
                      f'{(m["set_code"] or "").upper()},{m["finish"]},{m["lang"]},'
                      f'{m["copy_id"]}')
    return "\n".join(linhas) + "\n"


def _linhas_da_caixa(s: dict) -> dict[int, int]:
    """`copy_id -> quantas`, a alocação de HOJE de uma caixa. É o que se grava."""
    linhas: dict[int, int] = defaultdict(int)
    for m in s["have"]:
        for g in m["lotes"]:
            linhas[g["id"]] += g["q"]
    return {cid: q for cid, q in linhas.items() if q > 0}


def guardar_arrumacao(con, res: dict, actualizar: set[str] | frozenset = frozenset()
                      ) -> int:
    """Grava a alocação de hoje como a arrumação REAL ("já arrumei tudo").

    A partir daqui, `local()` diz *"está na caixa X"* em vez do balde, e o
    `plano_arrumacao` fica vazio até a alocação mudar. Substitui a tabela
    inteira: a alocação é global, e uma linha órfã de uma caixa que já não
    existe mentia para sempre.

    **As caixas CONGELADAS ficam como estão** (a não ser que venham em
    `actualizar`). É a ordem do André de 2026-09-07 às 19:00 — *"apenas mexer
    para actualizar"*: o botão geral arruma a colecção, não desmonta um deck que
    está sleevado. Para aplicar o delta de uma caixa congelada há o botão
    "actualizei" dela (`actualizar_caixa`).

    Não mexe nas `sub_collections` de propósito — no modelo de colecção única a
    gaveta de onde a carta veio continua a ser a mesma, e é dela que a aba
    *Arrumar* precisa para dizer para onde a devolver.
    """
    congeladas = {s["slot"] for s in res["slots"]
                  if s.get("congelada") and s["slot"] not in actualizar}
    manter = [(r["copy_id"], r["slot"], r["quantity"]) for r in con.execute(
        "SELECT copy_id, slot, quantity FROM copy_allocation")
        if r["slot"] in congeladas and (r["quantity"] or 0) > 0]
    novas = [(cid, s["slot"], q) for s in res["slots"]
             if s["slot"] not in congeladas
             for cid, q in sorted(_linhas_da_caixa(s).items())]
    con.execute("DELETE FROM copy_allocation")
    con.executemany(
        "INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at) "
        "VALUES (?,?,?,datetime('now'))", sorted(manter + novas))
    con.commit()
    return sum(q for _c, _s, q in manter + novas)


def actualizar_caixa(con, res: dict, slot_id: str) -> int:
    """"Actualizei": aplica o delta de UMA caixa congelada e mais nada.

    O gesto que o André descreveu — *"apenas mexer para actualizar"* — é abrir a
    caixa, tirar o que saiu da lista, meter o que entrou, e voltar a fechá-la.
    Isto é o registo desse gesto: a caixa passa a conter a alocação de hoje, as
    outras não se tocam.
    """
    alvo = next((s for s in res["slots"] if s["slot"] == slot_id), None)
    if alvo is None:
        return 0
    linhas = _linhas_da_caixa(alvo)
    con.execute("DELETE FROM copy_allocation WHERE slot = ?", (slot_id,))
    con.executemany(
        "INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at) "
        "VALUES (?,?,?,datetime('now'))",
        [(cid, slot_id, q) for cid, q in sorted(linhas.items())])
    con.commit()
    return sum(linhas.values())


def report(con, cfg_slots: list[dict] | None = None) -> dict:
    """Alocação + venda + arrumação, de uma vez. É o que as páginas e o CLI consomem."""
    res = allocate(con, cfg_slots)
    res.update(sell_list(con, res))
    res["custo_total"] = round(sum(s["custo"] for s in res["slots"]), 2)
    res["comprar_total"] = sum(s["comprar"] for s in res["slots"])
    res["noutra_total"] = sum(s["noutra"] for s in res["slots"])
    res["sem_preco_total"] = sum(s["sem_preco"] for s in res["slots"])
    # Quantas cópias a partilha poupou — é a diferença entre somar as faltas
    # caixa a caixa (o que a v3 fazia) e comprar o máximo de uma delas.
    res["poupado_total"] = sum(p["poupado"] for p in res["partilhas"])
    res["arrumacao"] = plano_arrumacao(res)
    # A ORDEM de montagem (v6): é a pergunta dele de 2026-09-08 — *"por onde
    # começo?"*. Vive no relatório e não na página para o CLI dar a mesma.
    res["montagem"] = ordem_de_montagem(res)
    # As caixas congeladas que têm delta por aplicar ("tirar X, meter Y"). À
    # cabeça do relatório porque é o único movimento que o botão geral NÃO faz.
    res["actualizacoes"] = res["arrumacao"]["actualizacoes"]
    return res


# ---------------------------------------------------------------------------
# Ranking de arquétipos por material (para escolher os slots por confirmar)
# ---------------------------------------------------------------------------
def foil_report(con: sqlite3.Connection, fmt: str, top: int = 5,
                min_lists: int = 8, res: dict | None = None) -> list[dict]:
    """Arquétipos de um formato ordenados por quanto o André JÁ TEM para os montar.

    Responde à pergunta dele de 2026-09-07: *"para os decks 'metagame', em vez de
    me dares todas as listas, dás-me só o top-3 decks que estou mais perto de
    concluir"*. A lista de cada arquétipo é a lista padrão de sempre
    (`stock.stock_list` — o mesmo consenso do resto do vault), mas a posse passa
    pelas regras de material do loadout: nesses formatos as cartas são todas foil
    menos as da Reserved List, e uma PT da era Premodern está trancada ao
    Premodern. Sem isso o ranking dizia que ele tem cartas que não pode pôr no
    deck.

    Com `res` (o resultado de um `allocate`), a posse é lida DEPOIS das caixas
    montadas: `got` são as cópias que ficaram livres e `noutra` as que já estão
    numa caixa — que se vão buscar, não se compram. O custo é sobre `comprar`, a
    mesma regra do resto do loadout. Sem `res`, tudo está livre (é o que faz
    sentido para quem só quer o ranking).

    As básicas contam como tidas mas ficam FORA da percentagem: com elas dentro,
    um deck com 20 terras começava em 33% e os arquétipos deixavam de se
    distinguir uns dos outros, que é exactamente o que ele quer ver aqui.
    """
    pool = res["pool"] if res else lots(con)
    baldes = ({s["balde"] for s in res["slots"] if s.get("balde")} if res
              else {s.get("balde") for s in config_slots() if s.get("balde")})
    # As caixas dedicadas não emprestam: um arquétipo candidato a esta caixa não
    # pode contar com uma cópia que está sleevada dentro do Pauper ou do cEDH.
    ded = dedicadas(res["slots"]) if res else frozenset()
    # Slot de mentira: só o que decide se uma cópia serve. As regras de material
    # saem das `regras_por_formato`, as mesmas das caixas a sério — escritas à
    # mão aqui, este ranking dizia-lhe que tem cartas que não pode pôr no deck.
    ps = {k: v for k, v in regra_do_formato(fmt)[1].items() if k in CHAVES_REGRA}
    ps.update({"formato": fmt, "nome": None})
    fin = "foil" if ps.get("acabamento") in ("foil", "prefere_foil") else "nonfoil"

    # Só listas que CONTAM (`sources.counting_sql`) — é a regra que vive num sítio
    # só desde 2026-09-07. Sem ela o `n_lists` vinha inflacionado pelas listas
    # antigas que ainda têm etiqueta de arquétipo mas que o metagame já não vê, e
    # o `min_lists` deixava entrar arquétipos que são ruído de duas ligas.
    conta, cp = sources.counting_sql(fmt, "d")
    rows = con.execute(
        f"""SELECT a.id, a.label, COUNT(d.id) n FROM archetypes a
              JOIN decklists d ON d.archetype_id = a.id
             WHERE a.format = ? AND {conta} GROUP BY a.id HAVING n >= ?
             ORDER BY n DESC LIMIT 40""", (fmt, *cp, min_lists)).fetchall()
    out = []
    vistos: dict[tuple, dict] = {}
    for r in rows:
        try:
            sl = stock.stock_list(con, r["id"])
        except LookupError:
            continue
        cards = [(b, c["card_name"], c["quantity"])
                 for b in ("main", "side") for c in sl.get(b, [])]
        if not cards:
            continue
        # O clustering parte o mesmo deck em vários `archetypes` (rótulos
        # diferentes, lista igual). Duas entradas com a MESMA lista padrão são o
        # mesmo baralho: junta-se o nº de listas em vez de aparecer duas vezes.
        chave = tuple(sorted(cards))
        if chave in vistos:
            vistos[chave]["n_lists"] += r["n"]
            vistos[chave]["ids"].append(r["id"])
            continue
        need = got = nq = comprar = 0
        custo = 0.0
        linhas = []
        for b, nm, q in cards:
            if nm in BASICS:
                linhas.append(_linha_cheia({"board": b, "nm": nm, "need": q,
                                            "got": q, "basica": True, "lotes": []}))
                continue
            e = _estado_carta(pool, ps, nm, q, baldes, ded=ded)
            unit, pfin = card_price(con, nm, fin)
            linha = _linha_cheia({
                "board": b, "nm": nm, "need": q, "got": e["got"], "basica": False,
                "lotes": [], "missing": q - e["got"], "comprar": e["comprar"],
                "noutra": e["noutra"], "noutra_q": e["noutra_q"],
                "unit": unit, "price_finish": pfin,
                "cost": round((unit or 0) * e["comprar"], 2)})
            need += q
            got += e["got"]
            nq += e["noutra_q"]
            comprar += e["comprar"]
            custo += linha["cost"]
            linhas.append(linha)
        if not need:
            continue
        linha = {"archetype_id": r["id"], "ids": [r["id"]], "label": r["label"],
                 "n_lists": r["n"], "need": need, "got": got, "noutra_q": nq,
                 "comprar": comprar, "custo": round(custo, 2),
                 # "perto de concluir" = o que ele TEM, esteja livre ou noutra
                 # caixa: a que está noutra caixa vai-se buscar, não se compra.
                 "tenho": got + nq, "pct": round(100 * (got + nq) / need),
                 "pct_livre": round(100 * got / need),
                 "linhas": linhas,
                 "faltam": sorted((m for m in linhas if m["comprar"]),
                                  key=lambda x: -(x["cost"] or 0))}
        vistos[chave] = linha
        out.append(linha)
    return sorted(out, key=lambda x: (-x["pct"], x["custo"], x["label"]))[:top]
