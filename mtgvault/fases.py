"""AS FASES DA ARRUMAÇÃO, E AS QUATRO PROTECÇÕES DA VENDA (André, 2026-10-01).

Ele vai arrumar a colecção por FASES e ditou as regras neste dia. As palavras
dele estão aqui porque é por elas que isto se mede:

  P1  *"shocklands e fetchlands: **todas as cópias** ficam protegidas — todos os
      acabamentos, todas as línguas, todas as repetidas, estejam ou não num
      deck. Sem excepções."*
  P2  Reserved List: protege-se *"o RL que ele joga"*, e **joga** = alocado a um
      deck montado OU presente no consenso de um formato que ele joga. O resto
      da RL **não** é protegido por aqui: continua a passar pela regra dos 5 %
      de 2026-09-08, com o carimbo da régua de preço.
  P3  *"nenhuma cópia alocada a um deck no estado «montado» ou «guardado» vai à
      venda."*
  P4  *"pede também, para cada deck, os maybe porque é preciso ter reserva
      dessas cartas para não estar a vender agora e ter que comprar mais
      tarde."*

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

OS TRÊS ESTADOS DE CADA DECK — E PORQUE É QUE NÃO SÃO O `estado` DA CAIXA
-------------------------------------------------------------------------------
A `caixas[].estado` (`candidata`/`permanente`/`montada`, v6 de 2026-09-08) é a
escala da ALOCAÇÃO: diz quem escolhe cartas primeiro e o que está sleevado. A
decisão desta arrumação é outro eixo — *"o que faço com este deck"* — e
escrevê-la na mesma chave era mudar a alocação com um botão que ele carrega para
arrumar. Por isso vive em **`caixas[].decisao`**:

    montado     fica montado, cartas protegidas (P3)
    guardado    desmonta-se, as cartas continuam protegidas e NÃO vão à venda
    dissolvido  desmonta-se e as cartas passam a candidatas, menos as que
                P1, P2 ou P4 apanhem

**A OMISSÃO É `montado`.** Nunca o contrário: um deck sem decisão não manda uma
única carta para a venda, e isso tem caso de teste
(`caso_um_deck_sem_decisao_nao_manda_nada_para_a_venda`). Um default a
`dissolvido` punha a colecção inteira à venda no dia em que alguém
acrescentasse uma caixa ao config.

A RESERVA ENCHE-SE SOZINHA, COM UM LIMIAR — E O LIMIAR É DELE
-------------------------------------------------------------------------------
A reserva não pode ser trabalho manual: sai do consenso do arquétipo (as cartas
de banda flex e o resto do sideboard que o consenso mostra e que não estão nas
75 de hoje), mais o que ele acrescentar à mão. Para o deck de Duel Commander é o
**consenso por comandante** de 2026-10-01 (`mtgvault/consenso.py`).

**O EFEITO PERVERSO, que a ordem nomeia e que é real:** se a reserva apanhar
tudo o que alguma vez apareceu numa lista, não sobra nada para vender. Por isso
há `reserva.limiar_pct` (omissão **20 %**): entra na reserva o que aparece em
pelo menos essa percentagem das listas do consenso. A CURVA (10/20/30/40/50 %)
mede-se com `curva_do_limiar` e está no relatório — ele escolhe o número com os
euros à frente.

A reserva **protege só o que ele TEM**. O que não tem não se protege: alimenta a
lista de compras que o loadout já faz.

ONDE É QUE AS PROTECÇÕES MORDEM
-------------------------------------------------------------------------------
Em DOIS sítios, de propósito, e com a mesma resposta nos dois (a lição do
`event_tier`: duas listas para a mesma pergunta divergem em silêncio):

  1. `candidatos()` — a **Fase 3**: a lista do que PODE ir à venda depois das
     quatro protecções, com o motivo e a protecção por cópia excluída. É só
     leitura, varre a colecção inteira e é ela que responde à pergunta dele.
  2. `filtrar_venda()` — o MOTOR. Entra no `loadout.sell_list`, no fim, como o
     filtro da reserva das caixas de 2026-09-20 já entrava: uma cópia protegida
     sai de `venda`/`venda_rl` para a saída nova **`protegidas`**, com o motivo.
     Uma protecção que só valesse numa página não era uma protecção.

**Cada cópia excluída guarda o MOTIVO em português e qual das quatro protecções
a apanhou.** Sem motivo não há exclusão silenciosa — é a regra dele.

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
from . import sources

# ---------------------------------------------------------------------------
# As quatro protecções: a chave, o rótulo e a ordem por que se perguntam
# ---------------------------------------------------------------------------
P1, P2, P3, P4 = "p1-terras", "p2-rl-joga", "p3-deck", "p4-reserva"
PROTECCOES = (P1, P2, P3, P4)
ROTULOS = {
    P1: "P1 · shocklands e fetchlands",
    P2: "P2 · Reserved List que ele joga",
    P3: "P3 · deck montado ou guardado",
    P4: "P4 · reserva («maybe») de um deck",
}

# ---------------------------------------------------------------------------
# OS TRÊS ESTADOS DE CADA DECK
# ---------------------------------------------------------------------------
MONTADO, GUARDADO, DISSOLVIDO = "montado", "guardado", "dissolvido"
DECISOES = (MONTADO, GUARDADO, DISSOLVIDO)
# A OMISSÃO É `montado`, e nunca o contrário (ver o cabeçalho). Tem teste.
DECISAO_OMISSAO = MONTADO
TEXTO_DECISAO = {
    MONTADO: "fica montado — as cartas ficam protegidas",
    GUARDADO: "desmonta-se, mas as cartas continuam protegidas (não vão à venda)",
    DISSOLVIDO: "desmonta-se e as cartas passam a candidatas (menos P1/P2/P4)",
}
# As decisões que PROTEGEM as cópias do deck (P3). O `dissolvido` é a única que
# as liberta — é para isso que ele existe.
DECISOES_PROTEGEM = (MONTADO, GUARDADO)


def decisao_de(caixa: dict) -> str:
    """A decisão desta caixa. Sem a chave (ou com um valor que não é dos três),
    é `montado` — ver o cabeçalho."""
    d = str(caixa.get("decisao") or "").strip().lower()
    return d if d in DECISOES else DECISAO_OMISSAO


def decisoes(cfg: dict | None = None) -> dict[str, str]:
    """`slot -> decisão` de todas as caixas do config."""
    return {c["slot"]: decisao_de(c) for c in _caixas.do_config(cfg)
            if c.get("slot")}


def gravar_decisao(slot: str, decisao: str, path=None) -> dict:
    """Escreve `caixas[<slot>].decisao`. Devolve `{antes, decisao, nome}`.

    Escreve-se com o `configio.escrever`, que preserva a forma UMA_LINHA do
    ficheiro — um `json.dump(indent=2)` dava um diff de centenas de linhas (já
    aconteceu: o commit `ac1f776`). **Reversível**: mudar de estado não apaga
    nada, nem a reserva nem a lista.
    """
    if decisao not in DECISOES:
        raise ValueError(f"decisão {decisao!r} não é uma de {', '.join(DECISOES)}")
    from . import configio                                  # noqa: PLC0415
    cfg = configio.ler(path)
    c = _caixas.caixa_do_cfg(cfg, slot)
    antes = decisao_de(c)
    c["decisao"] = decisao
    configio.escrever(cfg, path)
    sources._CFG_CACHE.clear()
    return {"antes": antes, "decisao": decisao, "mudou": antes != decisao,
            "nome": c.get("nome") or slot}


# ---------------------------------------------------------------------------
# P1: as duas listas de terras, DERIVADAS do catálogo
# ---------------------------------------------------------------------------
BASICOS = ("Plains", "Island", "Swamp", "Mountain", "Forest")
N_SHOCK = N_FETCH = 10

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


def verificar(con) -> dict:
    """A VERIFICAÇÃO explícita das duas listas: exige as dez de cada, sempre.

    É esta que o `cli fases` e a página chamam, para a conta que não dá dez ser
    um erro à vista e não um número pequeno que passa. A derivação usada em
    cada relatório é a mesma; o que muda é quem insiste.
    """
    cache: dict = {}
    return {"shocklands": shocklands(con, cache, exigir=True),
            "fetchlands": fetchlands(con, cache, exigir=True),
            "catalogo_completo": catalogo_completo(con)}


def terras_protegidas(con, cache: dict | None = None) -> dict[str, str]:
    """`nome -> "shockland" | "fetchland"`. É a P1, e não tem excepções:
    **todas** as cópias de cada um destes nomes ficam protegidas — todos os
    acabamentos, todas as línguas, todas as repetidas, dentro ou fora de um
    deck. Palavras dele: *"Todas as cópias"*."""
    cache = {} if cache is None else cache
    if "_terras_prot" in cache:
        return cache["_terras_prot"]
    out = {nm: "shockland" for nm in shocklands(con, cache)["nomes"]}
    out.update({nm: "fetchland" for nm in fetchlands(con, cache)["nomes"]})
    cache["_terras_prot"] = out
    return out


# ---------------------------------------------------------------------------
# P2: a Reserved List que ele JOGA
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


def rl_que_joga(con, res: dict, cfg: dict | None = None) -> dict[str, str]:
    """`nome -> porque é que ele joga esta carta de RL`.

    *"«joga» é alocado a um deck montado OU presente no consenso de um formato
    que ele joga"*. São quatro caminhos, e cada nome guarda o PRIMEIRO que o
    apanhou — é o que aparece no motivo da exclusão:

      (a) está dentro de um deck (`copy_allocation`) cuja decisão protege;
      (b) uma caixa do loadout pede-a (é a lista do deck, montado ou por montar);
      (c) está numa lista da tabela `decks`/`deck_cards` (os consensos de
          Premodern e o Cloud de Duel Commander escrevem-se lá);
      (d) está no consenso por comandante (núcleo + flex) de um comandante que
          ele tem em caixa.

    Medido a 2026-10-01: a união dá 502 nomes, e deles 26 cartas / 128 cópias
    são RL que ele tem. Não há consenso de cEDH nem de Pauper para cruzar — o
    cEDH não tem metagame no vault (os dois decks seguem links directos) e o
    Pauper só guarda as listas do Luffy; as duas chegam por (b)/(c).
    """
    dec = decisoes(cfg)
    fmts = set(formatos_que_joga(cfg))
    out: dict[str, str] = {}

    # (a) dentro de um deck cuja decisão protege
    nomes_caixa = {s["slot"]: s.get("nome") or s["slot"] for s in res["slots"]}
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            slot = lot.get("caixa")
            if slot and dec.get(slot, DECISAO_OMISSAO) in DECISOES_PROTEGEM:
                out.setdefault(nm, f"está no deck {nomes_caixa.get(slot, slot)}")
                break

    # (b) pedida por uma caixa do loadout
    for s in res["slots"]:
        if (s.get("formato") or "").lower() not in fmts:
            continue
        for _b, nm, _q in (s.get("cards") or []):
            out.setdefault(nm, f"está na lista de {s.get('nome') or s['slot']}")

    # (c) numa lista da tabela `decks`
    for r in con.execute("""SELECT DISTINCT dc.card_name nm, d.name dn, d.format f
                              FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id"""):
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
    return out


# ---------------------------------------------------------------------------
# O consenso de cada deck — a matéria-prima da reserva (P4)
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


def _listas_por_assinatura(con, fmt: str, assinatura: list[str]) -> list[int]:
    """Os ids das listas que CONTAM e jogam uma destas cartas.

    A consulta é a mesma do `loadout._cards_from_consensus` — o mesmo universo
    de listas de todo o site (`sources.counting_sql`). Um segundo filtro ao lado
    discorda do primeiro em silêncio, que é a lição do `event_tier`.
    """
    if not assinatura:
        return []
    conta, cp = sources.counting_sql(fmt, "d")
    marks = ",".join("?" * len(assinatura))
    return [r[0] for r in con.execute(
        f"""SELECT DISTINCT d.id FROM decklists d
              JOIN decklist_cards dc ON dc.decklist_id = d.id
             WHERE d.format = ? AND dc.card_name IN ({marks}) AND {conta}""",
        (fmt, *assinatura, *cp))]


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
        conta, cp = sources.counting_sql(fmt, "d")
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


def _listas_do_deck(con, s: dict, cache: dict | None = None
                    ) -> tuple[list[int], str, str]:
    """`(ids, nota, origem)` — as listas que formam o consenso DESTA caixa.

    Dois caminhos, por esta ordem: a assinatura ESCRITA (a excepção explícita,
    `reserva_assinatura` ou o `assinatura` que a caixa de consenso já tem) e,
    não havendo, a DERIVADA da própria lista. Quando nem isso dá, diz-se que não
    há consenso em vez de se inventar um.
    """
    fmt = (s.get("formato") or "").lower()
    escrita = [str(x) for x in (s.get("reserva_assinatura")
                                or s.get("assinatura") or [])]
    if escrita:
        ids = _listas_por_assinatura(con, fmt, escrita)
        return (ids, f"{len(ids)} listas por assinatura ({', '.join(escrita)})",
                "assinatura")
    derivada = assinatura_derivada(con, s, cache)
    if derivada:
        ids = _listas_por_assinatura(con, fmt, derivada)
        return (ids, f"{len(ids)} listas pelas cartas mais distintivas da lista "
                     f"({', '.join(derivada)})", "derivada")
    return [], "sem assinatura nem comandante — a reserva fica só manual", ""


def consenso_do_deck(con, s: dict, cache: dict | None = None) -> dict:
    """`{fonte, listas, cartas: [{nm, pct, copias, board}], nota}` para uma caixa.

    Duas fontes, e a primeira é a que a ordem manda para o Duel Commander:

      * **por COMANDANTE** (`mtgvault/consenso.py`, 2026-10-01) quando a caixa
        tem um comandante derivável — é o deck de Duel Commander dele;
      * **por ASSINATURA** (as mesmas listas do `loadout._cards_from_consensus`)
        para as caixas de consenso, com a percentagem por carta em vez da lista
        padrão.

    Sem nenhuma das duas devolve-se `cartas: []` e a nota a dizer porquê. É uma
    resposta: a reserva daquele deck passa a ser só o que ele escrever à mão.
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
    ids, nota, origem = _listas_do_deck(con, s, cache)
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
    return {"fonte": origem, "listas": n, "cartas": cartas,
            "suficiente": n >= MIN_LISTAS_RESERVA, "nota": nota}


# ---------------------------------------------------------------------------
# P4: a reserva («maybe») de cada deck
# ---------------------------------------------------------------------------
LIMIAR_OMISSAO = 20
CURVA_OMISSAO = (10, 20, 30, 40, 50)
# ABAIXO DISTO NÃO SE CHAMA CONSENSO A NADA, e não é um requinte: medido a
# 2026-10-01, a caixa *Ill-Gotten Gains* (que nem tem lista — 0/0) casava 3
# listas pela assinatura, e com 3 listas uma carta que aparece numa só vale
# 33 %. Passava folgadamente o limiar de 20 % e a reserva dela sozinha segurava
# **52 cópias / 6 879 €** — 96 % de tudo o que a P4 protegia. É exactamente o
# efeito perverso que a ordem nomeia, por outra porta: não é o limiar que está
# mal, é a amostra. É o mesmo mínimo do `consenso.MIN_LISTAS`.
MIN_LISTAS_RESERVA = 8


def regras_reserva(cfg: dict | None = None) -> dict:
    """`colecao_config.json → reserva`, com as omissões."""
    v = (sources.config() if cfg is None else cfg).get("reserva") or {}
    r = {"limiar_pct": LIMIAR_OMISSAO, "curva": list(CURVA_OMISSAO)}
    r.update({k: x for k, x in v.items() if not str(k).startswith("_")})
    return r


def limiar_pct(cfg: dict | None = None) -> int:
    return int(regras_reserva(cfg)["limiar_pct"])


def reserva_do_deck(con, s: dict, limiar: int | None = None,
                    cache: dict | None = None) -> dict:
    """A reserva («maybe») de uma caixa: o que o consenso mostra e não está nas 75.

    `{automatica, manual, retiradas, final, nota, listas, fonte, limiar}` —
    cada carta com `pct` e quantas ele TEM. A reserva protege **só o que ele
    tem**; o que não tem fica marcado `tem: 0` e alimenta a lista de compras que
    o loadout já faz, como a ordem diz.

    Três partes, e as três se vêem na página:
      * `automatica` — do consenso, acima do limiar, e que NÃO está na lista de
        hoje (as 75). É a banda flex e o resto do sideboard;
      * `manual` — `caixas[].reserva`, o que ele acrescentou à mão (a chave já
        existia desde 2026-09-20 e continua a querer dizer o mesmo);
      * `retiradas` — `caixas[].reserva_fora`: o que ele TIROU da automática.
        Guarda-se o que ele tirou, e não a lista final, para a reserva continuar
        a crescer com o consenso sem lhe devolver o que ele já recusou.
    """
    cache = {} if cache is None else cache
    lim = limiar_pct() if limiar is None else int(limiar)
    c = consenso_do_deck(con, s, cache)
    nas_75 = {nm for _b, nm, _q in (s.get("cards") or [])}
    fora = {str(x) for x in (s.get("reserva_fora") or [])}
    manual = [str(x) for x in (s.get("reserva") or [])]
    # SEM AMOSTRA NÃO HÁ RESERVA AUTOMÁTICA (ver `MIN_LISTAS_RESERVA`). Com 3
    # listas, uma carta que apareça numa só vale 33 % e passa qualquer limiar —
    # a percentagem está certa e não quer dizer nada. O que ele escreveu à mão
    # fica: isso é uma decisão dele, não uma inferência.
    # As BÁSICAS ficam fora da reserva: nunca vão à venda (o `sell_list` salta-as
    # à cabeça), por isso protegê-las não protege nada e só enchia a lista que ele
    # tem de ler — o consenso do Modern punha lá *"Plains, 27,8 %"*.
    from . import loadout                                    # noqa: PLC0415
    automatica = ([x for x in c["cartas"]
                   if x["pct"] >= lim and x["nm"] not in nas_75
                   and x["nm"] not in fora and x["nm"] not in loadout.BASICS]
                  if c["suficiente"] else [])
    pct = {x["nm"]: x["pct"] for x in c["cartas"]}
    posse = _posse(con, cache)
    nomes_finais = list(dict.fromkeys([x["nm"] for x in automatica]
                                      + [m for m in manual if m not in nas_75]))
    final = [{"nm": nm, "pct": pct.get(nm),
              "manual": nm in manual, "tem": posse.get(nm, 0)}
             for nm in nomes_finais]
    final.sort(key=lambda x: (-(x["pct"] or 0), x["nm"]))
    return {"slot": s.get("slot"), "nome": s.get("nome") or s.get("slot"),
            "automatica": automatica, "manual": manual,
            "retiradas": sorted(fora), "final": final,
            "limiar": lim, "listas": c["listas"], "fonte": c["fonte"],
            "suficiente": c["suficiente"],
            "nota": (c["nota"] if c["suficiente"] or not c["listas"] else
                     f"{c['nota']} — poucas para consenso (precisa de "
                     f"{MIN_LISTAS_RESERVA}), por isso a reserva automática "
                     f"desta caixa está vazia"),
            "tem": sum(1 for x in final if x["tem"]),
            "sem": sum(1 for x in final if not x["tem"])}


def _posse(con, cache: dict | None = None) -> dict[str, int]:
    cache = {} if cache is None else cache
    if "_posse" not in cache:
        from . import paginas                                # noqa: PLC0415
        cache["_posse"] = paginas.posse_total(con)
    return cache["_posse"]


def reservas(con, res: dict, limiar: int | None = None,
             cache: dict | None = None) -> dict[str, list[str]]:
    """`nome de carta -> [caixas que a reservam]`. É a P4, pronta a proteger.

    Só os nomes que ele TEM entram: a reserva protege o que está na estante, e
    uma carta que ele não tem não precisa de protecção nenhuma.
    """
    cache = {} if cache is None else cache
    posse = _posse(con, cache)
    out: dict[str, list[str]] = defaultdict(list)
    for s in res["slots"]:
        r = reserva_do_deck(con, s, limiar, cache)
        for x in r["final"]:
            if posse.get(x["nm"]):
                out[x["nm"]].append(r["nome"])
    return dict(out)


def curva_do_limiar(con, res: dict, limiares=None,
                    cache: dict | None = None) -> list[dict]:
    """A CURVA que ele pediu: para cada limiar, quantas cópias e quanto valor é
    que a reserva protege — no total e deck a deck.

    *"MEDE A CURVA e põe no relatório: para os limiares 10, 20, 30, 40 e 50 %,
    quantas cópias e quanto valor é que a reserva protege em cada deck. Ele
    escolhe o limiar com os números à frente."*

    Conta **só o que a reserva protege a MAIS**: uma cópia que P1, P2 ou P3 já
    seguram não é mérito do limiar, e somá-la fazia a curva parecer plana.
    """
    cache = {} if cache is None else cache
    limiares = list(limiares or regras_reserva()["curva"])
    base = _protegidas_sem_p4(con, res, cache)
    valores = _valor_por_nome(con, res, cache)
    out = []
    for lim in limiares:
        por_deck: dict[str, dict] = {}
        tot_c = tot_v = 0
        for s in res["slots"]:
            r = reserva_do_deck(con, s, lim, cache)
            cop = val = 0
            for x in r["final"]:
                v = valores.get(x["nm"])
                if not v:
                    continue
                cop += v["copias_livres"]
                val += v["valor_livre"]
            por_deck[r["nome"]] = {"cartas": len(r["final"]), "copias": cop,
                                   "valor": round(val, 2)}
            tot_c += cop
            tot_v += val
        out.append({"limiar": lim, "copias": tot_c, "valor": round(tot_v, 2),
                    "decks": por_deck, "ja_protegidas": base["copias"]})
    return out


def _protegidas_sem_p4(con, res: dict, cache: dict | None = None) -> dict:
    """Quantas cópias as três primeiras protecções já seguram (para a curva)."""
    cache = {} if cache is None else cache
    if "_sem_p4" not in cache:
        c = candidatos(con, res, cache=cache, com_p4=False)
        cache["_sem_p4"] = {"copias": c["protegidas_copias"]}
    return cache["_sem_p4"]


def _valor_por_nome(con, res: dict, cache: dict | None = None) -> dict[str, dict]:
    """`nome -> {copias_livres, valor_livre}`: as cópias que NÃO estão dentro de
    um deck protegido, com o preço de referência de cada uma.

    É isto que a reserva «protege a mais»: uma cópia que está sleevada já está
    segura pela P3.
    """
    cache = {} if cache is None else cache
    if "_valnm" in cache:
        return cache["_valnm"]
    from . import loadout                                    # noqa: PLC0415
    dec = decisoes()
    pc: dict = cache.setdefault("_precos", {})
    out: dict[str, dict] = defaultdict(lambda: {"copias_livres": 0,
                                                "valor_livre": 0.0})
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            slot = lot.get("caixa")
            if slot and dec.get(slot, DECISAO_OMISSAO) in DECISOES_PROTEGEM:
                continue
            p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc)
            out[nm]["copias_livres"] += lot["q"]
            out[nm]["valor_livre"] += (p["unit"] or 0) * lot["q"]
    cache["_valnm"] = dict(out)
    return cache["_valnm"]


# ---------------------------------------------------------------------------
# AS QUATRO PROTECÇÕES APLICADAS: a Fase 3 (lista de candidatos)
# ---------------------------------------------------------------------------
def _motivo(prot: str, detalhe: str) -> str:
    """O motivo em português, com a protecção à frente. Sem isto havia exclusão
    silenciosa — e a regra dele é explícita: *"cada cópia excluída da venda
    guarda o MOTIVO em português, e qual das quatro protecções a apanhou"*."""
    return f"{ROTULOS[prot]}: {detalhe}"


def quem_protege(con, res: dict, nm: str, lot: dict, ctx: dict) -> tuple | None:
    """`(protecção, motivo)` se esta cópia está protegida, senão `None`.

    A ORDEM é a das quatro protecções dele, e conta para o motivo: uma
    shockland que está num deck montado é apanhada pela P1, porque é a P1 que a
    protege *"sem excepções"* — se amanhã o deck se dissolver, continua
    protegida, e o motivo tem de dizer a razão que SOBREVIVE.
    """
    terra = ctx["terras"].get(nm)
    if terra:
        return P1, _motivo(P1, f"{terra} — todas as cópias ficam protegidas")
    if lot.get("rl") and nm in ctx["rl_joga"]:
        return P2, _motivo(P2, f"Reserved List que jogas — {ctx['rl_joga'][nm]}")
    slot = lot.get("caixa")
    if slot:
        d = ctx["decisoes"].get(slot, DECISAO_OMISSAO)
        if d in DECISOES_PROTEGEM:
            nome = ctx["nomes"].get(slot, slot)
            return P3, _motivo(P3, f"está no deck {nome}, que decidiste "
                                   f"{'manter montado' if d == MONTADO else 'guardar'}")
    if ctx.get("reservas") and nm in ctx["reservas"]:
        quem = ", ".join(ctx["reservas"][nm])
        return P4, _motivo(P4, f"está na reserva de {quem} — podes precisar dela "
                               f"a seguir")
    return None


def candidatos(con, res: dict, cfg: dict | None = None,
               cache: dict | None = None, limiar: int | None = None,
               com_p4: bool = True) -> dict:
    """A FASE 3: o que sobra para venda depois das quatro protecções.

    Varre a colecção INTEIRA (o `pool` do relatório, uma linha por sub-lote) e
    devolve `{linhas, protegidas, por_proteccao, copias, valor, …}`. Cada linha
    é uma cópia física com o preço de referência; cada exclusão traz
    `proteccao` e `motivo`.

    **Só leitura**: não toca na base, nas alocações nem no config.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    ctx = {
        "terras": terras_protegidas(con, cache),
        "rl_joga": rl_que_joga(con, res, cfg),
        "decisoes": decisoes(cfg),
        "nomes": {s["slot"]: s.get("nome") or s["slot"] for s in res["slots"]},
        "reservas": reservas(con, res, limiar, cache) if com_p4 else {},
    }
    pc: dict = cache.setdefault("_precos", {})
    linhas, protegidas = [], []
    por: dict[str, dict] = {p: {"copias": 0, "valor": 0.0, "cartas": set()}
                            for p in PROTECCOES}
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            if lot["q"] <= 0:
                continue
            p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc)
            linha = {
                "nm": nm, "copy_id": lot["id"], "q": lot["q"],
                "sid": lot["sid"], "set": (lot["set_code"] or "").upper(),
                "set_name": lot["set_name"], "lang": (lot["lang"] or "en"),
                "finish": lot["finish"], "foil": loadout.e_foil(lot["finish"]),
                "cond": lot.get("cond") or "NM", "rl": bool(lot["rl"]),
                "local": lot["local"], "caixa": lot.get("caixa"),
                "validado": lot.get("validado") or "",
                "unit": p["unit"], "preco_fonte": p["fonte"],
                "preco_origem": p["origem"],
                "total": round((p["unit"] or 0) * lot["q"], 2),
            }
            qp = quem_protege(con, res, nm, lot, ctx)
            if qp is None:
                linhas.append(linha)
                continue
            prot, motivo = qp
            protegidas.append(dict(linha, proteccao=prot, motivo=motivo))
            por[prot]["copias"] += lot["q"]
            por[prot]["valor"] += linha["total"]
            por[prot]["cartas"].add(nm)
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
        "limiar": limiar_pct(cfg) if limiar is None else int(limiar),
        "com_p4": com_p4,
    }


def filtrar_venda(con, res: dict, venda: list[dict], venda_rl: list[dict],
                  cfg: dict | None = None, cache: dict | None = None
                  ) -> tuple[list[dict], list[dict], list[dict]]:
    """O MOTOR: tira de `venda`/`venda_rl` o que as quatro protecções seguram.

    Devolve `(venda, venda_rl, protegidas)`. Entra no `loadout.sell_list` no
    fim, como o filtro da reserva das caixas de 2026-09-20 — e pela mesma razão
    de desenho: a regra é sobre a CÓPIA, não sobre o motivo por que ela foi
    parar à lista. Uma protecção que só valesse na página das Fases não era uma
    protecção: a aba Vender e a exportação continuariam a oferecer a carta.

    Aqui não se varre a colecção: trabalha-se sobre as linhas já formadas, e
    cada linha traz as `copias` (os `copy_id`) de que é feita.
    """
    cache = {} if cache is None else cache
    ctx = {
        "terras": terras_protegidas(con, cache),
        "rl_joga": rl_que_joga(con, res, cfg),
        "decisoes": decisoes(cfg),
        "nomes": {s["slot"]: s.get("nome") or s["slot"] for s in res["slots"]},
        "reservas": reservas(con, res, None, cache),
    }
    protegidas: list[dict] = []

    def passa(rows):
        ficam = []
        for r in rows:
            # A caixa vem da LINHA (`linha_de` carimba-a do sub-lote). Não se
            # procura pelo `copy_id`: um lote de 4 com 3 na caixa e 1 na gaveta
            # são dois sub-lotes com o mesmo `copies.id`, e pelo id a parte da
            # gaveta ficava protegida pela P3 — uma cópia a desaparecer da venda
            # sem motivo. Apanhado pelo `test_paginas_loadout`.
            qp = quem_protege(con, res, r["nm"],
                              {"rl": r.get("rl"), "caixa": r.get("caixa")}, ctx)
            if qp is None:
                ficam.append(r)
                continue
            prot, motivo = qp
            protegidas.append(dict(r, proteccao=prot, motivo=motivo,
                                   porque_venderia=r.get("reason") or "",
                                   reason=motivo))
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
    "Fica para depois: estas caixas são do mesmo grupo de formato, com tecto de "
    "playset contado sobre o grupo — partilham o mesmo conjunto de cartas e "
    "montam-se por conversão de uma noutra. Primeiro os decks de lista única.")
NOTA_LISTA_UNICA = ("Lista única e cartas dedicadas: é por aqui que se começa.")


def de_conversao(res: dict, cfg: dict | None = None) -> dict[str, bool]:
    """`slot -> é «de conversão»?` Ver a nota acima para a regra derivada."""
    from . import loadout                                    # noqa: PLC0415
    regras = (cfg or {}).get("regras_por_formato")
    if not isinstance(regras, list) or not regras:
        regras = loadout.regras_por_formato()
    tecto: dict[str, int] = {}
    for r in regras:
        if r.get("playset_maximo"):
            tecto[r.get("grupo") or ""] = int(r["playset_maximo"])
    quantas: dict[str, int] = defaultdict(int)
    for s in res.get("slots") or []:
        quantas[s.get("grupo") or s.get("formato") or ""] += 1
    return {s["slot"]: bool(tecto.get(s.get("grupo") or "")
                            and quantas[s.get("grupo") or ""] > 1)
            for s in res.get("slots") or []}


def _linha_de_lote(con, nm: str, lot: dict, pc: dict, perdidas: dict) -> dict:
    from . import loadout                                    # noqa: PLC0415
    p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc)
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
    dec = decisoes(cfg)
    pc: dict = cache.setdefault("_precos", {})
    perdidas = _perdidas(con, cache)
    por_slot: dict[str, list[dict]] = defaultdict(list)
    for nm, lotes in (res.get("pool") or {}).items():
        for lot in lotes:
            slot = lot.get("caixa")
            if not slot or dec.get(slot, DECISAO_OMISSAO) != MONTADO:
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
                           c.name nm, c.scryfall_id sid, c.set_code,
                           c.collector_number num,
                           (SELECT slot FROM copy_allocation a WHERE a.copy_id = cp.id
                             ORDER BY quantity DESC LIMIT 1) slot
                      FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                     WHERE cp.id IN ({marks})""", sorted(perdidas)):
            nm = (r["nm"] or "").split(" // ", 1)[0]
            p = loadout.preco_da_copia(con, r["sid"], r["finish"], nm, pc)
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
    """A FASE 1: cada deck, a decisão de hoje, e o que cada decisão LIBERTA.

    `liberta` é quantas cópias e quanto valor passariam a candidatas se ele
    dissolvesse este deck — contado com as outras três protecções a valer, que é
    a única conta honesta: uma shockland dentro do deck continua protegida pela
    P1 e não se liberta ao dissolvê-lo.
    """
    from . import loadout                                    # noqa: PLC0415
    cache = {} if cache is None else cache
    dec = decisoes(cfg)
    terras = terras_protegidas(con, cache)
    rl_joga = rl_que_joga(con, res, cfg)
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
            p = loadout.preco_da_copia(con, lot["sid"], lot["finish"], nm, pc)
            v = (p["unit"] or 0) * lot["q"]
            d["copias"] += lot["q"]
            d["valor"] += v
            # O que SE LIBERTA: o que as outras protecções não seguram.
            if nm in terras or (lot["rl"] and nm in rl_joga):
                continue
            d["liberta_copias"] += lot["q"]
            d["liberta_valor"] += v
    out = []
    for s in res["slots"]:
        slot = s["slot"]
        d = por_slot.get(slot) or {"copias": 0, "valor": 0.0,
                                   "liberta_copias": 0, "liberta_valor": 0.0}
        r = reserva_do_deck(con, s, None, cache)
        out.append({
            "slot": slot, "nome": s.get("nome") or slot,
            "formato": s.get("formato"), "estado": s.get("estado"),
            "decisao": dec.get(slot, DECISAO_OMISSAO),
            "decisao_explicita": bool(_caixa_tem_decisao(cfg, slot)),
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


def _caixa_tem_decisao(cfg: dict | None, slot: str) -> bool:
    """Se a decisão está ESCRITA no config (e não só assumida).

    A página mostra a diferença: *«por decidir (conta como montado)»* não é o
    mesmo que ele ter carregado em «montado», e esconder isso era dar por
    tomada uma decisão que ninguém tomou.
    """
    for c in _caixas.do_config(cfg):
        if c.get("slot") == slot:
            return str(c.get("decisao") or "").strip().lower() in DECISOES
    return False


def relatorio(con, res: dict, cfg: dict | None = None,
              hoje: str | None = None, curva: bool = False) -> dict:
    """Tudo o que a página das Fases e o `cli fases` mostram, numa chamada."""
    cache: dict = {}
    hoje = hoje or date.today().isoformat()
    cands = candidatos(con, res, cfg, cache)
    out = {
        "hoje": hoje,
        "congelado_ate": congelado_ate(cfg),
        "congelada": venda_congelada(cfg, hoje),
        "motivo_congelado": (motivo_congelado(congelado_ate(cfg), hoje)
                             if venda_congelada(cfg, hoje) else ""),
        "limiar": limiar_pct(cfg),
        "terras": {"shocklands": shocklands(con, cache),
                   "fetchlands": fetchlands(con, cache)},
        "decks": decks_para_decidir(con, res, cfg, cache),
        "fase2": fila_decks(con, res, cfg, cache),
        "candidatos": cands,
        "fase4": fila_candidatos(con, res, cfg, cache, cands),
        "inventario": fila_inventario(con, res, cfg, cache),
        # As únicas cópias sem prova nenhuma: vêm à cabeça de tudo.
        "perdidas": fotos_perdidas(con, res, cfg, cache),
        "max_cartas_foto": _fotos_mod().MAX_CARTAS,
        "decisoes": {"valores": list(DECISOES), "omissao": DECISAO_OMISSAO,
                     "texto": dict(TEXTO_DECISAO)},
    }
    if curva:
        out["curva"] = curva_do_limiar(con, res, None, cache)
    return out
