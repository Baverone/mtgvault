"""CONSENSO POR COMANDANTE (André, 2026-10-01).

*"Quero consenso de Duel Commander do deck dele (comandante CLOUD) sempre
actualizado, da mesma forma que já tem para os arquétipos de Modern."*

A DECISÃO QUE MANDA AQUI: **em Duel Commander a identidade de um deck é o
COMANDANTE, nunca a etiqueta do clustering.** Medido na base de 2026-10-01: a
tabela `archetypes` tinha **870** etiquetas de `duel-commander` e **808** delas
sem uma única lista — e as que tinham chamavam-se *"Aragorn, King of Gondor /
Sulfur Falls / Stormcarved Coast"*, três cartas distintivas que mudam de corrida
para corrida. Agrupar por aí era voltar ao problema que o `mtgvault/arquetipos.py`
resolveu para o Premodern, mas numa pergunta em que a resposta certa está escrita
na própria carta: um deck de Commander É o seu comandante.

COMO É QUE A BASE GUARDAVA O COMANDANTE — e a resposta é que não guardava
---------------------------------------------------------------------------
O `decklist_cards.board` tem um `CHECK (board IN ('main','side'))` e nas 652
listas de `duel-commander` da base de 01/10 **só havia `main`**. Não é descuido:
é a decisão de `sources.store_event` e de `mtgtop8.harvest` — as duas fontes
servem o comandante no SIDEBOARD (o `SB:` do `.dec` do mtgtop8, o
`sideboard_deck` do mtgo.com) e o vault reencaminha-o para o mainboard, porque é
lá que ele conta para as 100 cartas e porque é isso que faz o `content_hash` das
duas fontes coincidir (sem isso a deduplicação entre elas não funcionava).

Resultado: a informação *"qual destas 100 cartas é o comandante"* era deitada
fora no momento da recolha. E não se pode adivinhar: as listas de DC trazem em
média **6 lendárias de quantidade 1** (até 30 numa só), e o crivo pela
identidade de cor deixava **0 ou mais do que um** candidato em 409 das 652
listas, porque 609 delas têm cartas que o catálogo ainda não conhece.

A REGRA USADA, e porque é que é honesta
---------------------------------------
Duas metades:

1. **Daqui para a frente a fonte diz qual é** (`commander_fonte = 'sideboard'`).
   O `store_event`/`harvest` passaram a guardar o nome das cartas que vinham do
   sideboard antes de as fundir no main. Não é um palpite: é o dado que estava a
   ser deitado fora.

2. **Para as listas que já estavam na base, deriva-se pela ORDEM DE INSERÇÃO**
   (`commander_fonte = 'ordem'`). O comandante vem no FIM do `.dec` e o
   `store_event` faz `main += side`: a última linha de `decklist_cards` de uma
   lista de comandante é o comandante. A `decklist_cards` é uma tabela com
   `rowid`, por isso essa ordem sobreviveu.
   **Medido** na base de 2026-10-01, nas 652 listas: a última linha é uma
   lendária criatura/planeswalker de quantidade 1 em **554**, está fora do
   catálogo (sets recentes: *Brigid*, *Terra, Magical Adept*, *Aang*) em **97**,
   e há **1** caso real a mais (um `Legendary Enchantment — Background`, que é
   mesmo uma segunda carta de comandante). Controlo: a PRIMEIRA linha só é
   lendária de quantidade 1 em 29 das 652 — o sinal é posicional, não um
   acidente de haver muitas lendárias.

Grava-se, não se recalcula (é o pedido dele, à letra). As duas colunas vivem na
`decklists` — nos três sítios, como manda o CLAUDE.md: `schema.sql`,
`db._migrate()` e quem as escreve (este módulo e o `sources`).

QUE LISTAS CONTAM — medido, não adivinhado
------------------------------------------
A regra do Modern (sem ligas, presencial com 64+ jogadores) **não deixava nada**:
mede-se em `_scratch/medir_filtro.py` e está na secção do CLAUDE.md. Sobre as 652
listas de 01/10, por hipótese:

    652  Cloud  41   ligas + presencial sem mínimo   <- escolhida
    518  Cloud  37   sem ligas, presencial sem mínimo
    425  Cloud  26   com ligas, presencial 16+
    291  Cloud  22   sem ligas, presencial 16+
    182  Cloud   4   com ligas, presencial 64+
     48  Cloud   0   SEM LIGAS, PRESENCIAL 64+  (a regra do Modern)

Escolheu-se a primeira — que é, por acaso, exactamente a regra que ele já tinha
dado para o Duel Commander a 2026-09-07 (*"menos Duel Commander, que pode ter
menos jogadores e pode ser ligas"*, `metagame_fontes["duel-commander"]`). Por
isso o filtro desta página **é o `sources.lista_conta`** e não um segundo filtro
a viver ao lado: a lição do `event_tier` é que o segundo filtro discorda do
primeiro em silêncio. O que é configurável à parte está em
`colecao_config.json → consenso_comandante` e é só o que é DESTA página (o
formato, o mínimo de listas, os limiares dos papéis e o comandante que abre).
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict

from . import sources

# O formato por omissão e o comandante que a página abre. Os dois estão no
# config (`consenso_comandante`), porque são escolhas dele e não regras.
FORMATO = "duel-commander"
COMANDANTE = "Cloud, Midgar Mercenary"

# Os papéis, em percentagem de listas que jogam a carta. Duel Commander é
# SINGLETON: a moda de cópias é quase sempre 1, por isso o que vale é a
# percentagem — é ela que separa *"esta carta é o deck"* de *"esta carta é uma
# opção"*. Os limiares são os que ele pediu (>=90 núcleo, 40–90 flex, <40 raro)
# e são mais apertados do que os do `commander_decks.tiers` (50/25/15), que
# responde a outra pergunta: aquele constrói uma lista de 100 cartas a partir do
# consenso; esta diz, de cada carta, quão obrigatória ela é.
NUCLEO, FLEX = 0.90, 0.40
# Abaixo disto não se chama "consenso" a nada.
MIN_LISTAS = 8

PAPEIS = ("nucleo", "flex", "raro")
ROTULOS = {"nucleo": "Núcleo", "flex": "Flex", "raro": "Raro"}

FONTE_SIDEBOARD = "sideboard"
FONTE_ORDEM = "ordem"


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
def regras() -> dict:
    """`colecao_config.json → consenso_comandante`, com os valores por omissão.

    Só leva o que é DESTA página. O filtro de eventos não está aqui de propósito:
    é o `sources.lista_conta`/`counting_sql`, o mesmo de todo o site (ver o
    cabeçalho). `min_jogadores_presencial` e `ligas` do Duel Commander ajustam-se
    em `metagame_fontes`, onde já estavam.
    """
    cfg = sources.config().get("consenso_comandante") or {}
    r = {"formato": FORMATO, "comandante": COMANDANTE, "min_listas": MIN_LISTAS,
         "nucleo_pct": int(NUCLEO * 100), "flex_pct": int(FLEX * 100),
         "max_comandantes": 40}
    r.update({k: v for k, v in cfg.items() if not str(k).startswith("_")})
    return r


# ---------------------------------------------------------------------------
# O comandante de cada lista
# ---------------------------------------------------------------------------
def nome_do_comandante(con, nomes) -> str | None:
    """De uma lista de cartas do SIDEBOARD, qual é o comandante.

    Preferem-se as lendárias criatura/planeswalker do catálogo; com várias (as
    duplas de *partner*, um *Background*) fica a PRIMEIRA pela ordem da fonte —
    é a que o site mostra à cabeça. Uma carta que o catálogo ainda não conhece
    continua a valer: o Duel Commander joga sets do mês, e recusá-la era perder
    exactamente os comandantes novos.
    """
    nomes = [n for n in (nomes or []) if n]
    if not nomes:
        return None
    marcas = ",".join("?" for _ in nomes)
    cmd = {r["nm"] for r in con.execute(
        f"""SELECT name nm FROM cards WHERE name IN ({marcas}) AND digital = 0
             AND type_line LIKE '%Legendary%'
             AND (type_line LIKE '%Creature%' OR type_line LIKE '%Planeswalker%')
            GROUP BY name""", nomes)}
    for n in nomes:
        if n in cmd:
            return n
    return nomes[0]


def derivar(con: sqlite3.Connection, fmt: str | None = None) -> dict:
    """Preenche o `decklists.commander` das listas que ainda o não têm, pela
    ORDEM DE INSERÇÃO das cartas (ver o cabeçalho). Devolve o que fez.

    É IDEMPOTENTE e só toca nas linhas a NULL: uma lista que a fonte já marcou
    (`commander_fonte = 'sideboard'`) nunca é reescrita por um palpite, e uma
    segunda corrida no mesmo dia não faz nada.
    """
    fmt = (fmt or regras()["formato"]).lower()
    faltam = [r["id"] for r in con.execute(
        "SELECT id FROM decklists WHERE format = ? AND commander IS NULL", (fmt,))]
    if not faltam:
        return {"derivadas": 0, "por_derivar": 0, "formato": fmt}
    ultima: dict[int, str] = {}
    for r in con.execute(
            """SELECT dc.decklist_id id, dc.card_name nm FROM decklist_cards dc
                 JOIN decklists dl ON dl.id = dc.decklist_id
                WHERE dl.format = ? AND dl.commander IS NULL
                ORDER BY dc.rowid""", (fmt,)):
        ultima[r["id"]] = r["nm"]
    escritas = [(nm, FONTE_ORDEM, lid) for lid, nm in ultima.items()]
    if escritas:
        con.executemany("UPDATE decklists SET commander = ?, commander_fonte = ? "
                        "WHERE id = ?", escritas)
        con.commit()
    return {"derivadas": len(escritas), "formato": fmt,
            "por_derivar": len(faltam) - len(escritas)}


# ---------------------------------------------------------------------------
# Os comandantes e o consenso de cada um
# ---------------------------------------------------------------------------
def _listas(con, fmt: str):
    """`(ids por comandante, janela de datas)` — só as listas que CONTAM."""
    conta, cp = sources.counting_sql(fmt, "dl")
    por: dict[str, list[int]] = defaultdict(list)
    de = ate = ""
    for r in con.execute(
            f"""SELECT dl.id, dl.commander c, dl.event_date d FROM decklists dl
                 WHERE dl.format = ? AND dl.commander IS NOT NULL AND {conta}""",
            (fmt, *cp)):
        por[r["c"]].append(r["id"])
        d = r["d"] or ""
        de = d if (not de or d < de) else de
        ate = d if d > ate else ate
    return por, (de, ate)


def comandantes(con: sqlite3.Connection, fmt: str | None = None) -> list[dict]:
    """`[{nome, listas}]` por ordem de nº de listas (desempate pelo nome)."""
    fmt = (fmt or regras()["formato"]).lower()
    por, _janela = _listas(con, fmt)
    return sorted(({"nome": nm, "listas": len(ids)} for nm, ids in por.items()),
                  key=lambda x: (-x["listas"], x["nome"]))


def papel(pct: float, r: dict | None = None) -> str:
    r = r or regras()
    if pct >= r["nucleo_pct"]:
        return "nucleo"
    return "flex" if pct >= r["flex_pct"] else "raro"


def consenso(con: sqlite3.Connection, comandante: str,
             fmt: str | None = None) -> dict:
    """O consenso de UM comandante.

    `{comandante, formato, listas, janela, cartas: [...], papeis: {...},
      suficiente: bool}` — e com `listas` abaixo do mínimo devolve-se a mesma
    forma com `suficiente: False` e as cartas que houver. Um comandante sem
    listas nenhumas não é um erro: é uma resposta ("não sei"), e a página tem de
    a poder mostrar sem rebentar.

    Cada carta leva `pct` (percentagem das listas que a jogam), `copias` (a
    quantidade MAIS FREQUENTE — em singleton é 1, e di-lo em vez de o esconder) e
    `papel`. O COMANDANTE sai da lista das cartas e vai à parte: ele não é uma
    escolha do deck, é a identidade dele.
    """
    r = regras()
    fmt = (fmt or r["formato"]).lower()
    por, janela = _listas(con, fmt)
    ids = por.get(comandante) or []
    out = {"comandante": comandante, "formato": fmt, "listas": len(ids),
           "janela": list(janela), "cartas": [], "papeis": {p: 0 for p in PAPEIS},
           "min_listas": r["min_listas"], "nucleo_pct": r["nucleo_pct"],
           "flex_pct": r["flex_pct"],
           "suficiente": len(ids) >= r["min_listas"]}
    if not ids:
        return out
    em = Counter()
    qts: dict[str, Counter] = defaultdict(Counter)
    for i in range(0, len(ids), 400):
        ch = ids[i:i + 400]
        marcas = ",".join("?" for _ in ch)
        for row in con.execute(
                f"""SELECT card_name nm, quantity q, decklist_id d
                      FROM decklist_cards WHERE decklist_id IN ({marcas})""", ch):
            em[row["nm"]] += 1
            qts[row["nm"]][row["q"]] += 1
    n = len(ids)
    cartas = []
    for nm, c in em.items():
        if nm == comandante:
            continue
        pct = round(100 * c / n, 1)
        cartas.append({"nm": nm, "listas": c, "pct": pct,
                       "copias": qts[nm].most_common(1)[0][0],
                       "papel": papel(pct, r)})
    cartas.sort(key=lambda x: (-x["pct"], x["nm"]))
    out["cartas"] = cartas
    for c in cartas:
        out["papeis"][c["papel"]] += 1
    return out


def fontes(con: sqlite3.Connection, fmt: str | None = None) -> dict:
    """Quantas listas sabem o comandante, e por que caminho. É o que a página
    diz em letra pequena: um número que vem de um palpite tem de o dizer."""
    fmt = (fmt or regras()["formato"]).lower()
    out = {"total": 0, FONTE_SIDEBOARD: 0, FONTE_ORDEM: 0, "sem": 0}
    for r in con.execute("""SELECT commander_fonte f, COUNT(*) n FROM decklists
                             WHERE format = ? GROUP BY commander_fonte""", (fmt,)):
        out["total"] += r["n"]
        out[r["f"] or "sem"] = out.get(r["f"] or "sem", 0) + r["n"]
    return out
