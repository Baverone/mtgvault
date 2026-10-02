"""O ESTADO DAS CARTAS: a escala do Cardmarket, o preço e o critério que APRENDE.

André, 2026-10-03, à letra: *"procuras como são avaliadas as cartas, depois com
base nas minhas próprias fotos, vais melhorando o teu critério"*.

O BURACO QUE ISTO TAPA
----------------------
As 737 linhas da `copies` diziam **todas `NM`** — as 1 678 cartas, duais de
Revised de 1994 incluídas. Não era uma medição: era o valor por omissão do
`add_copy` que nunca ninguém mexeu. E era pior do que parecia, porque a cadeia
de preços **não tinha dimensão de estado nenhuma** (a `price_latest` tem
`low`/`trend`/`avg30` e mais nada): mesmo que o estado se registasse, não havia
onde ele entrasse no cálculo, e os 136 492 € da colecção estavam somados como se
trinta anos de cartão estivessem impecáveis.

A ESCALA É A DO CARDMARKET, porque é lá que ele vende
----------------------------------------------------
`MT NM EX GD LP PL PO`, com as definições de
<https://help.cardmarket.com/en/CardCondition> transcritas **da fonte** para
`data/estado-criterio.md` (ver `criterio`). Duas notas que custaram uma leitura:

* a página escreve **«Mint (M)»**, mas o código que o Cardmarket usa nas
  exportações de stock e na API é **`MT`**. Aqui o canónico é o `MT` (é o que ele
  pediu e o que o `venda-stock.csv` escreve) e o `M` é um ALIAS;
* a página não diz «mais 10 %, menos 20 %» em sítio nenhum. **O Cardmarket não
  publica factor de estado** — o price guide tem um preço por produto, ponto. Mas
  publica, no texto de cada escalão, a **equivalência ao sistema americano**, e é
  essa a ponte que vale ouro (ver `PONTE_AMERICANA`).

DE ONDE VEM O FACTOR DE PREÇO — MEDIDO, NÃO INVENTADO
-----------------------------------------------------
A ordem era explícita: *"não inventes percentagens tuas: procura o que a fonte já
dá por estado e usa isso"*. A fonte dá, e dá muito bem:

* o **CardTrader** traz o estado em **cada oferta** (`properties_hash.condition`)
  e usa a escala **americana** — sondado a 2026-10-03 em 23 edições reais da
  colecção dele: `Near Mint` 402 886 ofertas, `Slightly Played` 245 246,
  `Moderately Played` 135 137, `Played` 66 647, `Poor` 15 625 (`Mint` e
  `Heavily Played`: **zero**);
* o **Cardmarket** diz, no seu próprio texto, que EX ≡ *Slightly Played*,
  GD ≡ *Moderately Played*, LP ≡ *Played*, PL ≡ *Heavily Played*, PO ≡ *Poor*.

Logo o factor é a **razão medida entre a mediana das ofertas de um escalão e a
mediana das ofertas Near Mint da MESMA impressão**, sobre 10 004 pares
(impressão × acabamento). Está no config (`precos.estado`), com a data, a
amostra e a origem, e é alterável à mão.

E DEPENDE DO PREÇO — foi medido e é a parte que interessa
--------------------------------------------------------
Numa carta de 0,40 € a razão é quase 1 (há pisos de preço e portes a dominar);
numa de 100 € ou mais, um *Slightly Played* vale **0,776** do Near Mint. Por isso
a tabela tem **bandas** (<1, 1-5, 5-20, 20-100, ≥100 €), e não um número só: um
número só errava por 20 pontos exactamente no sítio onde está o dinheiro dele —
a Reserved List e as duais.

O QUE **NÃO** MUDA, e é a propriedade que torna isto seguro
----------------------------------------------------------
**NM vale 1,000 em todas as bandas**, por construção: é a âncora da medição. Como
hoje a colecção inteira está `NM`, ligar isto **não mexe um único cêntimo** — tem
teste. O valor só muda no dia em que um escalão for mesmo atribuído, e aí muda
porque a carta é o que é.

Duas aproximações, ditas em voz alta em vez de escondidas:

1. o preço de referência de hoje é a mediana das ofertas em `Mint`/`NM`/
   `Slightly Played`/`Moderately Played` (o crivo `precos.ESTADOS_OK`, do
   riftvault), e não um preço só de NM. Tratá-lo como o preço NM deixa o NM
   ligeiramente SUBavaliado — que é o lado conservador, e é melhor do que
   inventar uma majoração;
2. **PL não tem amostra**: o CardTrader não tem `Heavily Played`. O factor dele é
   a interpolação entre LP e PO e vai marcado `interpolado` — a página e o
   relatório dizem-no.

«POR OMISSÃO» DEIXA DE PODER PASSAR POR MEDIDO
----------------------------------------------
O `NM` que lá está **não se apaga nem se muda de valor** (regra dele de 09/09):
ganha `condition_origem = 'omissao'` e, com ela, a frase *«por omissão, nunca
verificado»*. Quem decide se um juízo conta é `medido()`, num sítio só.

O CRITÉRIO APRENDE, E É O CRITÉRIO DELE
---------------------------------------
Cada escalão atribuído fica gravado com a FOTO, o escalão e os MOTIVOS escritos.
Quando ele corrige, a correcção fica como **exemplo rotulado** (o que eu disse, o
que ele disse, o que me escapou) na tabela `condition_log`, **a correcção dele
ganha sempre** (`corrigir` > `propor`, e um juízo posterior meu nunca a
sobrepõe — tem teste), e o `data/estado-criterio.md` cresce com uma secção
«aprendido com o André», datada, **só** com o que veio de correcções dele. O
passo que avalia lê o ficheiro MAIS os exemplos recentes MAIS os padrões de erro
repetidos (`para_avaliar`), e a taxa de acerto diz se está a melhorar
(`acerto`).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from . import db

# ---------------------------------------------------------------------------
# A ESCALA (Cardmarket), do melhor para o pior
# ---------------------------------------------------------------------------
ESCALA = ("MT", "NM", "EX", "GD", "LP", "PL", "PO")
OMISSAO = "NM"                      # o que o `add_copy` sempre escreveu

NOMES = {"MT": "Mint", "NM": "Near Mint", "EX": "Excellent", "GD": "Good",
         "LP": "Light Played", "PL": "Played", "PO": "Poor"}

# A EQUIVALÊNCIA AO SISTEMA AMERICANO, nas palavras do próprio Cardmarket (a
# página de cada escalão, lida a 2026-10-03). É a ponte para as ofertas do
# CardTrader, que usa essa escala. O americano «Good» fica DE FORA de propósito:
# o Cardmarket usa-o para LP *e* para PL («Note that 'Good' is a bit of a
# misnomer») — adivinhar qual era inventar.
PONTE_AMERICANA = {
    "mint": "MT",
    "near mint": "NM", "nm/m": "NM", "nm": "NM",
    "slightly played": "EX", "lightly played": "EX", "sp": "EX",
    "moderately played": "GD", "very good": "GD", "mp": "GD",
    "played": "LP",
    "heavily played": "PL", "hp": "PL",
    "poor": "PO",
}

# Como se escreve um escalão em texto livre (o CSV das fotos, o CLI, o config).
# O `M` é o que a página de ajuda do Cardmarket mostra; o `MT` é o código da API
# e das exportações de stock. Valem os dois.
_ALIAS = {
    **{c.lower(): c for c in ESCALA},
    **{n.lower(): c for c, n in NOMES.items()},
    "m": "MT", "mint": "MT",
    "nearmint": "NM", "near-mint": "NM",
    "ex+": "EX", "ex-": "EX", "nm-": "NM", "nm+": "NM",   # «partial grades»
    "excelente": "EX", "bom": "GD", "pobre": "PO",
}


def normalizar(v) -> str | None:
    """`"near mint"`, `"NM-"`, `"Slightly Played"` → o código do Cardmarket.

    Um valor que não se reconhece devolve `None` — nunca um palpite.

    **A ARMADILHA DA PALAVRA «PLAYED», e é real.** O escalão `PL` do Cardmarket
    chama-se *«Played»*; e o escalão AMERICANO *«Played»* é o que o Cardmarket
    mapeia para o seu `LP` (*«The American equivalent usually is 'Played' or
    'Good'»*). A mesma palavra, dois escalões. Aqui **ganha o nome do
    Cardmarket** — é esta a escala do vault e é ela que vai no CSV de stock —, e
    quem traduz uma oferta de marketplace usa o `do_cardtrader`, que é explícito.
    Resolver isto «pelo contexto» era deixar uma carta a mudar de escalão
    conforme o caminho por que entrou.
    """
    s = re.sub(r"[\s_]+", " ", str(v or "")).strip()
    if not s:
        return None
    low = s.lower()
    return _ALIAS.get(low) or PONTE_AMERICANA.get(low)


def do_cardtrader(cond) -> str | None:
    """O estado de uma OFERTA do CardTrader (escala americana) → código do
    Cardmarket, pela equivalência que o próprio Cardmarket publica.

    Existe à parte do `normalizar` por causa do *«Played»*: ali a palavra vale o
    `PL` do Cardmarket, aqui vale o `LP`. É a tradução explícita, e é a que a
    medição do factor usa — ver `PONTE_AMERICANA`.
    """
    s = re.sub(r"[\s_]+", " ", str(cond or "")).strip().lower()
    return PONTE_AMERICANA.get(s)


def pior(a: str | None, b: str | None) -> str | None:
    """O pior dos dois escalões (o que vale menos). `None` é «não sei»."""
    a, b = normalizar(a), normalizar(b)
    if a is None:
        return b
    if b is None:
        return a
    return a if ESCALA.index(a) >= ESCALA.index(b) else b


# ---------------------------------------------------------------------------
# A ORIGEM DO JUÍZO — e o que passa por MEDIDO
# ---------------------------------------------------------------------------
ORIGEM_FOTO = "foto"            # saiu de uma foto (normalmente do VERSO)
ORIGEM_MAO = "mao"              # o André escreveu-o à mão; ganha sempre
ORIGEM_OMISSAO = "omissao"      # nunca ninguém o verificou

ORIGENS = (ORIGEM_FOTO, ORIGEM_MAO, ORIGEM_OMISSAO)
MEDIDAS = (ORIGEM_FOTO, ORIGEM_MAO)

ROTULO_ORIGEM = {
    ORIGEM_FOTO: "avaliado por foto",
    ORIGEM_MAO: "escrito à mão pelo André",
    ORIGEM_OMISSAO: "por omissão, nunca verificado",
}

POR_VERIFICAR = "por verificar"
MOTIVO_SEM_VERSO = ("sem foto do verso — o estado fica por verificar e não se "
                    "inventa um escalão")


def medido(origem: str | None) -> bool:
    """Este juízo conta como medido? Num sítio só.

    O `NM` por omissão **não** conta: é o valor com que a cópia nasceu, e deixá-lo
    passar por medido era dar por avaliada uma colecção que nunca ninguém olhou.
    """
    return (origem or ORIGEM_OMISSAO) in MEDIDAS


def normalizar_origem(v) -> str:
    """A origem de um juízo, com `omissao` como omissão.

    Um valor desconhecido vale `omissao` e não levanta: isto é chamado pelo
    `add_copy`, e uma gralha num CSV não pode travar a entrada de uma carta — o
    que ela faz é não passar por medido, que é o lado seguro.
    """
    s = str(v or "").strip().lower()
    return s if s in ORIGENS else ORIGEM_OMISSAO


def origem_de(r) -> str:
    """A origem do juízo de uma linha da `copies` (uma linha antiga vale
    `omissao` — é o que ela é)."""
    try:
        v = r["condition_origem"]
    except (KeyError, IndexError, TypeError):
        v = (r or {}).get("condition_origem") if isinstance(r, dict) else None
    v = (v or "").strip().lower()
    return v if v in ORIGENS else ORIGEM_OMISSAO


def texto_do_estado(grade: str | None, origem: str | None) -> str:
    """*«EX · avaliado por foto»* / *«NM · por omissão, nunca verificado»*."""
    g = normalizar(grade) or "?"
    nome = NOMES.get(g, g)
    return f"{g} ({nome}) · {ROTULO_ORIGEM.get(origem or ORIGEM_OMISSAO)}"


# ---------------------------------------------------------------------------
# O FACTOR DE PREÇO: medido nas ofertas do CardTrader, por banda
# ---------------------------------------------------------------------------
# Medido a 2026-10-03 (`_revisao/sondar_estado_ct2.py` + `tabela_final_estado.py`)
# em 23 edições da colecção dele, 10 004 pares (impressão × acabamento),
# 865 541 ofertas utilizáveis: a razão entre a mediana de cada escalão e a
# mediana do Near Mint da MESMA impressão, exigindo 2+ ofertas em cada lado.
#
# Isto é o OMISSÃO: quem manda é o `colecao_config.json → precos.estado`. Está
# aqui pela razão do `precos.MODO_OMISSAO` — um config sem o bloco não pode
# deixar o site sem preços.
BANDAS_OMISSAO = (1.0, 5.0, 20.0, 100.0)
FACTORES_OMISSAO = {
    "MT": [1.0, 1.0, 1.0, 1.0, 1.0],
    "NM": [1.0, 1.0, 1.0, 1.0, 1.0],
    "EX": [0.983, 0.828, 0.837, 0.813, 0.776],
    "GD": [0.791, 0.648, 0.629, 0.642, 0.593],
    "LP": [0.676, 0.559, 0.546, 0.524, 0.540],
    "PL": [0.675, 0.543, 0.512, 0.504, 0.504],      # interpolado: ver abaixo
    "PO": [0.674, 0.527, 0.477, 0.484, 0.468],
}
# Os escalões cujo factor NÃO foi medido e porquê. O `PL` é o único: o
# Cardmarket mapeia-o para o americano «Heavily Played» e o CardTrader não tem
# uma única oferta nesse estado — o factor é a interpolação entre LP e PO, e
# **diz-se**. Um número aproximado com cara de número medido é a mentira que
# esta secção inteira existe para não contar.
APROXIMADOS = {
    "PL": "interpolado entre LP e PO: o CardTrader não tem «Heavily Played», "
          "que é o escalão americano a que o Cardmarket mapeia o PL",
}
ORIGEM_FACTOR = "cardtrader-ofertas"
ROTULO_FACTOR = {
    ORIGEM_FACTOR: "medido nas ofertas do CardTrader, por estado, contra o "
                   "Near Mint da mesma impressão",
}


def bloco(cfg: dict | None = None) -> dict:
    """O bloco `precos.estado` do config (vazio se não existir).

    Lê pelo `precos.bloco`, que já usa a cache do `sources.config()` — isto é
    chamado por cópia e abrir o ficheiro a cada chamada punha o relatório em
    minutos (a lição do `precos.bloco`, 2026-09-25).
    """
    from . import precos                                    # noqa: PLC0415
    b = precos.bloco(cfg).get("estado")
    return b if isinstance(b, dict) else {}


def bandas(cfg: dict | None = None) -> tuple[float, ...]:
    v = bloco(cfg).get("bandas_eur")
    if isinstance(v, list) and v:
        try:
            fs = tuple(sorted(float(x) for x in v))
        except (TypeError, ValueError):
            return BANDAS_OMISSAO
        return fs
    return BANDAS_OMISSAO


# A TABELA JÁ RESOLVIDA, por bloco de config (2026-10-03). O `factor()` é chamado
# uma vez por cópia e por cenário — 1 700 a 5 000 vezes por página —, e reconstruir
# sete listas de cinco floats a cada chamada eram 3,1 s medidos com o cProfile. A
# chave é a IDENTIDADE do bloco que o `sources.config()` devolve: ele devolve
# sempre o mesmo objecto enquanto o ficheiro não mudar, e um ficheiro novo é um
# objecto novo — por isso a cache acerta-se sozinha e nunca serve a tabela antiga.
_TABELA_CACHE: dict = {}


def _tabela(cfg: dict | None = None) -> dict[str, list[float]]:
    """`{escalão: [factor por banda]}`. O config ganha; o que faltar vem do
    omissão — um escalão esquecido à mão não pode valer zero euros."""
    b = bloco(cfg)
    chave = id(b) if b else 0
    pronta = _TABELA_CACHE.get(chave)
    if pronta is not None and _TABELA_CACHE.get("_bloco") is b:
        return pronta
    fora = _tabela_crua(cfg)
    _TABELA_CACHE.clear()
    _TABELA_CACHE[chave] = fora
    _TABELA_CACHE["_bloco"] = b           # segura a referência: o `id` só vale com ela
    return fora


def _tabela_crua(cfg: dict | None = None) -> dict[str, list[float]]:
    bs = bandas(cfg)
    fora: dict[str, list[float]] = {}
    do_cfg = bloco(cfg).get("factores")
    do_cfg = do_cfg if isinstance(do_cfg, dict) else {}
    for g in ESCALA:
        v = do_cfg.get(g)
        if isinstance(v, (int, float)):
            v = [float(v)] * (len(bs) + 1)
        if isinstance(v, list) and len(v) == len(bs) + 1:
            try:
                fora[g] = [float(x) for x in v]
                continue
            except (TypeError, ValueError):
                pass
        fora[g] = list(FACTORES_OMISSAO[g])
    return fora


def banda_de(preco, cfg: dict | None = None) -> int:
    """Em que banda de preço cai este preço de referência (índice)."""
    p = float(preco or 0)
    for i, lim in enumerate(bandas(cfg)):
        if p < lim:
            return i
    return len(bandas(cfg))


def etiquetas_das_bandas(cfg: dict | None = None) -> list[str]:
    bs = bandas(cfg)
    fora = [f"< {bs[0]:g} €"]
    fora += [f"{bs[i]:g}–{bs[i + 1]:g} €" for i in range(len(bs) - 1)]
    fora.append(f"≥ {bs[-1]:g} €")
    return fora


def factor(grade: str | None, preco=None, cfg: dict | None = None) -> dict:
    """`{factor, grade, banda, banda_nome, aproximado, nota, origem}`.

    Sem escalão reconhecido o factor é **1,0** e não um palpite: *«não sei»* não
    pode custar dinheiro a ninguém, nem num sentido nem no outro.
    """
    g = normalizar(grade)
    b = banda_de(preco, cfg)
    etq = etiquetas_das_bandas(cfg)
    if g is None:
        return {"factor": 1.0, "grade": None, "banda": b,
                "banda_nome": etq[b], "aproximado": False, "nota": "",
                "origem": None}
    f = _tabela(cfg)[g][b]
    return {"factor": f, "grade": g, "banda": b, "banda_nome": etq[b],
            "aproximado": g in APROXIMADOS, "nota": APROXIMADOS.get(g, ""),
            "origem": bloco(cfg).get("origem") or ORIGEM_FACTOR}


def aplicar(unit, grade: str | None, *, origem: str | None = None,
            cfg: dict | None = None) -> dict:
    """O preço de uma cópia DEPOIS do estado.

    `{unit, unit_nm, factor, grade, origem, aproximado, nota, desconto}` — e
    `unit = None` continua a ser `None`: *«sem preço»* nunca é 0 € (a regra de
    2026-09-25).

    O factor aplica-se ao escalão que está GRAVADO, seja qual for a origem dele:
    se diz EX, a carta é EX e o dinheiro tem de o dizer. Quem separa um juízo
    medido de um `NM` por omissão é o `medido()`, e essa separação mostra-se ao
    lado do número — não se desconta duas vezes pela mesma dúvida.
    """
    d = factor(grade, unit, cfg)
    if unit is None:
        return {"unit": None, "unit_nm": None, "desconto": None,
                "origem_estado": origem or ORIGEM_OMISSAO, "medido": medido(origem),
                **{k: d[k] for k in ("factor", "grade", "banda", "banda_nome",
                                     "aproximado", "nota")}}
    base = float(unit)
    # SEM FACTOR, SEM ARREDONDAMENTO. Com `factor == 1.0` devolve-se o número tal
    # e qual: arredondá-lo a 2 casas mudava o cenário `media` (que é
    # `(low+trend)/2` e pode ter três casas) em cêntimos, e a colecção dele
    # mexia **0,29 €** sem uma única carta ter mudado de estado. Medido lado a
    # lado com o `main` a 2026-10-03 — era a única diferença das 30 que se
    # compararam, e uma diferença que não se explica não se aceita.
    novo = base if d["factor"] == 1.0 else round(base * d["factor"], 2)
    return {"unit": novo, "unit_nm": round(base, 2),
            "desconto": round(base - novo, 2),
            "origem_estado": origem or ORIGEM_OMISSAO, "medido": medido(origem),
            **{k: d[k] for k in ("factor", "grade", "banda", "banda_nome",
                                 "aproximado", "nota")}}


def nota_do_factor(cfg: dict | None = None) -> str:
    """A frase que vai em cada página onde um preço com estado aparece.

    É a parte do *«diz no relatório que é uma aproximação e de onde veio»* que
    não pode viver só no relatório: quem olha para o número tem de ver a régua.
    """
    b = bloco(cfg)
    org = b.get("origem") or ORIGEM_FACTOR
    quando = b.get("medido_em") or "2026-10-03"
    am = b.get("amostra") or {}
    peca = ROTULO_FACTOR.get(org, org)
    extra = ""
    if am:
        extra = (f" — amostra de {am.get('pares', '?')} impressões em "
                 f"{am.get('edicoes', '?')} edições")
    return (f"O desconto por estado é {peca}, medido em {quando}{extra}. "
            f"O Near Mint vale 1,00 (é a âncora). O PL é interpolado: a fonte "
            f"não tem ofertas nesse estado.")


# ---------------------------------------------------------------------------
# O VERSO: para que serve, e quem precisa dele
# ---------------------------------------------------------------------------
# **O VERSO NÃO IDENTIFICA A CARTA.** Todos os versos de Magic são iguais — não
# há nada no verso que diga que carta é. Serve para UMA coisa: ver o desgaste que
# a frente não mostra (branqueamento das bordas e dos cantos visto do outro lado,
# vincos, manchas, danos de água). É por isso que o escalão sai do verso quando
# ele existe, e é por isso que uma cópia sem verso fica `por verificar` em vez de
# receber um escalão: não se inventa o que não se viu.
PORQUE_VERSO = ("Todos os versos de Magic são iguais: o verso não serve para "
                "identificar a carta, serve para ver o desgaste — bordas, "
                "cantos, vincos e manchas que a frente não mostra. Por isso o "
                "escalão sai do verso; sem verso, o estado fica «por verificar».")

# Quem precisa de verso FORA dos decks. Dentro de um deck é sempre.
MOTIVOS_VERSO = {
    "rl": "Reserved List",
    "dual": "dual original (as dez)",
    "shock": "shockland",
    "fetch": "fetchland",
    "venda": "vai à venda",
}


def exige_verso_no_deck() -> bool:
    """Dentro de um deck o verso é SEMPRE (ordem dele). Existe como função para
    o teste poder afirmá-lo e para ninguém o escrever à mão no meio de uma
    página."""
    return True


def motivos_fora_dos_decks(lot: dict, *, rl=None, duais=None, shocks=None,
                           fetches=None, venda=None) -> list[str]:
    """Porque é que ESTA cópia, fora dos decks, precisa de verso.

    Devolve as etiquetas de `MOTIVOS_VERSO` que se aplicam — vazio = frente só.
    As listas vêm de `fases` (que as DERIVA do catálogo) e dos candidatos da
    venda; não se escreve aqui nenhuma carta à mão.
    """
    nm = (lot.get("nm") or "").split(" // ", 1)[0]
    fora = []
    if rl is not None and (lot.get("rl") or nm in rl):
        fora.append("rl")
    elif lot.get("rl"):
        fora.append("rl")
    for etq, conj in (("dual", duais), ("shock", shocks), ("fetch", fetches)):
        if conj and nm in conj:
            fora.append(etq)
    if venda and lot.get("copy_id") in venda:
        fora.append("venda")
    return fora


# ---------------------------------------------------------------------------
# O REGISTO: cada juízo com a foto e os motivos; a correcção dele GANHA
# ---------------------------------------------------------------------------
AUTOR_CLAUDE = "claude"
AUTOR_ANDRE = "andre"

LOG = "estado.log"


def ficheiro_log() -> Path:
    """`data/estado.log` — o rasto em texto, escrito ANTES da base.

    Pela razão do `foto-manda.log` e do `revalidacao.log`: um escalão muda o
    valor de uma cópia, e o que se perde quando se escreve por cima é a única
    coisa que não se reconstrói. Sai de `db.pasta_dados()` e não de `db.ROOT`.
    """
    return db.pasta_dados() / LOG


def _log(accao: str, detalhe: str, log_path: Path | None = None) -> Path:
    p = Path(log_path) if log_path else ficheiro_log()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}\t{accao}\t{detalhe}\n")
    return p


class EstadoInvalido(ValueError):
    """Um escalão que não é da escala do Cardmarket.

    `ValueError` como a `VendaDesligada` e a `AlocacaoDupla`, para o `do_POST` o
    traduzir num 409 com a frase em português.
    """


def _hoje(dia: str | None = None) -> str:
    return dia or dt.date.today().isoformat()


def actual(con, copy_id: int) -> dict:
    """O estado de uma cópia hoje: `{grade, origem, em, motivos, foto, verso}`."""
    r = con.execute(
        "SELECT condition, condition_origem, condition_em, condition_motivos, "
        "       photo_path, verso_path FROM copies WHERE id = ?",
        (int(copy_id),)).fetchone()
    if r is None:
        raise LookupError(f"cópia {copy_id} não existe")
    return {"grade": normalizar(r[0]) or OMISSAO, "origem": origem_de(
        {"condition_origem": r[1]}), "em": r[2] or "", "motivos": r[3] or "",
        "foto": r[4] or "", "verso": r[5] or ""}


def e_basica(con, copy_id: int) -> bool:
    """Esta cópia é um terreno básico? — a pergunta num sítio só.

    Lê o NOME do catálogo e compara com o `loadout.BASICS`, que é a única lista
    de básicas que conta (ver `fotos.so_basicas`). Uma cópia que o catálogo não
    conheça **não** é básica: não se inventa.
    """
    from . import loadout                                    # noqa: PLC0415
    r = con.execute(
        """SELECT c.name nm FROM copies cp
             LEFT JOIN cards c ON c.scryfall_id = cp.scryfall_id
            WHERE cp.id = ?""", (int(copy_id),)).fetchone()
    nm = (r["nm"] if r else None) or ""
    return nm.split(" // ", 1)[0] in loadout.BASICS


def registar(con, copy_id: int, grade: str, *, origem: str,
             motivos: str = "", photo_path: str | None = None,
             autor: str | None = None, dia: str | None = None,
             log_path: Path | None = None) -> dict:
    """Grava um juízo de estado. Devolve `{aplicado, antes, grade, porque}`.

    **A CORRECÇÃO DELE GANHA SEMPRE.** Um juízo `foto` nunca sobrepõe um juízo
    `mao`: fica no `condition_log` como proposta recusada (`aplicado = 0`) e a
    cópia não se toca. É a ordem dele, à letra — *"a correcção dele GANHA sempre
    e nunca é sobreposta por uma avaliação posterior minha"* —, e é também a
    razão por que o log guarda o que NÃO se aplicou: sem isso a taxa de acerto
    não existia.
    """
    g = normalizar(grade)
    if g is None:
        raise EstadoInvalido(
            f"estado {grade!r} desconhecido — a escala do Cardmarket é "
            + ", ".join(f"{c} ({NOMES[c]})" for c in ESCALA))
    if origem not in ORIGENS:
        raise EstadoInvalido(f"origem {origem!r} — usa {', '.join(ORIGENS)}")
    # AS BÁSICAS NÃO LEVAM ESCALÃO NEM VERSO (André, 2026-10-02). Entram por
    # CONTAGEM DECLARADA (`loadout.basicas_declaradas`) e nunca por foto, logo
    # não há foto de onde tirar um escalão; e a pilha de Unhinged é a granel —
    # julgar o estado de uma terra que vale cêntimos e que ele tem às dezenas é
    # trabalho sem nada do outro lado. Recusa-se ALTO em vez de se ignorar em
    # silêncio: um `aplicado = 0` aqui parecia a regra da correcção dele.
    if e_basica(con, copy_id):
        raise EstadoInvalido(
            "os terrenos básicos não levam escalão de estado nem verso: "
            "entram por contagem declarada (basicas.declaradas no config)")
    antes = actual(con, copy_id)
    hoje = _hoje(dia)
    autor = autor or (AUTOR_ANDRE if origem == ORIGEM_MAO else AUTOR_CLAUDE)
    manda_ele = antes["origem"] == ORIGEM_MAO and origem != ORIGEM_MAO
    aplicado = 0 if manda_ele else 1
    porque = ("" if aplicado else
              f"o André já tinha escrito {antes['grade']} à mão em "
              f"{antes['em'] or 'data desconhecida'} — a correcção dele ganha")
    _log("juizo" if aplicado else "juizo-recusado",
         f"cópia {copy_id}: {antes['grade']}({antes['origem']}) → {g}({origem}) "
         f"por {autor}; {motivos or 'sem motivos escritos'}"
         + (f"; NÃO aplicado: {porque}" if porque else ""), log_path)
    con.execute(
        """INSERT INTO condition_log (copy_id, at, grade, antes, antes_origem,
                                      origem, autor, photo_path, motivos, aplicado)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (int(copy_id), f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}", g,
         antes["grade"], antes["origem"], origem, autor,
         photo_path or antes["foto"] or None, motivos or None, aplicado))
    if aplicado:
        con.execute(
            "UPDATE copies SET condition = ?, condition_origem = ?, "
            "condition_em = ?, condition_motivos = ? WHERE id = ?",
            (g, origem, hoje, motivos or None, int(copy_id)))
    con.commit()
    return {"aplicado": bool(aplicado), "antes": antes["grade"], "grade": g,
            "origem": origem, "porque": porque}


def corrigir(con, copy_id: int, grade: str, *, motivos: str = "",
             escapou: str = "", dia: str | None = None,
             log_path: Path | None = None) -> dict:
    """O André corrige um escalão. É a porta do `ORIGEM_MAO` — e é a que ensina.

    `escapou` é a linha do que me passou ao lado («estava optimista com o
    branqueamento das bordas»). Guarda-se no `condition_log` porque é ela que faz
    do par (foto, escalão) um **exemplo rotulado** em vez de uma simples
    diferença de opinião — e é ela que o `para_avaliar` lê antes de julgar outra
    vez.
    """
    antes = actual(con, copy_id)
    r = registar(con, copy_id, grade, origem=ORIGEM_MAO, motivos=motivos,
                 autor=AUTOR_ANDRE, dia=dia, log_path=log_path)
    if escapou or antes["grade"] != r["grade"]:
        con.execute(
            "UPDATE condition_log SET escapou = ?, eu_disse = ?, eu_motivos = ? "
            "WHERE id = (SELECT MAX(id) FROM condition_log WHERE copy_id = ?)",
            (escapou or None, antes["grade"], antes["motivos"] or None,
             int(copy_id)))
        con.commit()
    r["escapou"] = escapou
    r["eu_disse"] = antes["grade"]
    return r


MOTIVO_PAR_NAO_BATEU = (
    "o leitor não confirmou que a foto «-v» é um verso — o emparelhamento "
    "frente/verso não bateu, por isso não se grava escalão nenhum")
MOTIVO_SEM_ESCALAO = "o leitor não propôs escalão nenhum"


def da_foto(con, ids, *, grade: str | None, motivos: str = "",
            foto: str | None = None, verso: str | None = None,
            verso_ok=None, dia: str | None = None,
            log_path: Path | None = None) -> dict:
    """O juízo que vem de uma foto, aplicado às cópias que a linha tocou.

    `{grade, aplicado, copias, porque, verso}`. São TRÊS portas fechadas, e
    nenhuma delas se abre por omissão:

    1. **sem verso não há escalão.** *«Quando houver verso, o juízo do estado sai
       dele; sem verso, o estado fica "por verificar" e NÃO se inventa»* — ordem
       dele. Uma cópia fotografada só de frente fica `por verificar` e vai à
       LISTA CURTA;
    2. **o leitor tem de CONFIRMAR que a foto do verso é um verso** (`verso_ok`).
       O nome `-v` é só a hipótese do emparelhamento; como todos os versos de
       Magic são iguais, confirmá-lo é trivial — e sem a confirmação o par pode
       estar desalinhado, e um escalão gravado sobre um par trocado é pior do que
       escalão nenhum;
    3. **sem escalão proposto não se adivinha um.**
    Em qualquer dos três casos a proposta **não se perde**: fica no
    `condition_log` com `aplicado = 0` e o motivo, que é por onde ela aparece na
    página. E a correcção à mão do André continua a ganhar sempre (`registar`).
    """
    cids = [int(c) for c in dict.fromkeys(ids or ()) if c]
    g = normalizar(grade)
    confirmado_ok = str(verso_ok or "").strip().lower() in (
        "1", "sim", "s", "true", "yes", "y", "ok", "verso")
    if not verso:
        porque = MOTIVO_SEM_VERSO
    elif not confirmado_ok:
        porque = MOTIVO_PAR_NAO_BATEU
    elif g is None:
        porque = MOTIVO_SEM_ESCALAO
    else:
        porque = ""
    fora = {"grade": g, "aplicado": [], "recusado": [], "porque": porque,
            "verso": verso if (verso and confirmado_ok) else None}
    for cid in cids:
        if porque:
            # A proposta fica registada mesmo sem se aplicar: é o que faz a
            # página poder dizer «esta tem verso mas o par não bateu».
            if g is not None:
                con.execute(
                    """INSERT INTO condition_log (copy_id, at, grade, antes,
                           antes_origem, origem, autor, photo_path, motivos,
                           aplicado)
                       VALUES (?,?,?,?,?,?,?,?,?,0)""",
                    (cid, f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}", g,
                     actual(con, cid)["grade"], actual(con, cid)["origem"],
                     ORIGEM_FOTO, AUTOR_CLAUDE, foto,
                     f"{motivos} | NÃO aplicado: {porque}".strip(" |")))
            fora["recusado"].append(cid)
            continue
        if verso:
            con.execute("UPDATE copies SET verso_path = ? WHERE id = ?",
                        (verso, cid))
        r = registar(con, cid, g, origem=ORIGEM_FOTO, motivos=motivos,
                     photo_path=foto, dia=dia, log_path=log_path)
        (fora["aplicado"] if r["aplicado"] else fora["recusado"]).append(cid)
        if not r["aplicado"] and not fora["porque"]:
            fora["porque"] = r["porque"]
    con.commit()
    return fora


def marcar_omissao(con) -> int:
    """Marca como `omissao` todas as cópias que nunca tiveram juízo nenhum.

    **Não muda um único valor de `condition`** (regra dele de 09/09: nada se
    apaga): escreve só a ORIGEM, que é o que faz o `NM` de fábrica deixar de
    poder passar por medido. Idempotente — corre-se no `_migrate` e no `daily`.
    """
    cur = con.execute(
        "UPDATE copies SET condition_origem = ? "
        "WHERE condition_origem IS NULL OR TRIM(condition_origem) = ''",
        (ORIGEM_OMISSAO,))
    con.commit()
    return cur.rowcount or 0


# ---------------------------------------------------------------------------
# O CICLO QUE APRENDE
# ---------------------------------------------------------------------------
# As ZONAS do vocabulário do Cardmarket. Servem para CONTAR erros repetidos: sem
# uma chave contável, «dar mais peso aos erros repetidos» era uma intenção. As
# palavras são as da fonte (bordas/cantos, superfície/riscos, vinco, sujidade,
# planura) mais as duas que ele escreve em português.
ZONAS = {
    "bordas": ("borda", "border", "edge", "branque", "whiten", "white spot",
               "branco"),
    "cantos": ("canto", "corner"),
    "superficie": ("superf", "surface", "risco", "scratch", "clouding", "nuvem"),
    "vinco": ("vinco", "dobra", "bend", "crease"),
    "sujidade": ("sujid", "dirt", "mancha", "stain", "agua", "water"),
    "planura": ("planura", "planar", "empenad", "warp", "flat"),
    "verso": ("verso", "back"),
}


def _zonas(texto: str) -> list[str]:
    t = (texto or "").lower()
    return [z for z, chaves in ZONAS.items() if any(k in t for k in chaves)]


def sentido(eu: str | None, ele: str | None) -> str | None:
    """`optimista` (eu dei melhor do que ele), `pessimista`, ou `None` se igual."""
    a, b = normalizar(eu), normalizar(ele)
    if a is None or b is None or a == b:
        return None
    return "optimista" if ESCALA.index(a) < ESCALA.index(b) else "pessimista"


def exemplos(con, limite: int = 12) -> list[dict]:
    """Os EXEMPLOS ROTULADOS: as correcções dele, as mais recentes à frente.

    Cada um é `{copy_id, carta, foto, verso, eu_disse, ele_disse, escapou,
    motivos, sentido, zonas, em}` — a foto, o que eu disse, o que ele disse e o
    que me escapou. É isto que o passo que avalia lê antes de julgar.
    """
    try:
        rows = con.execute(
            """SELECT l.*, c.name nm, cp.photo_path foto, cp.verso_path verso
                 FROM condition_log l
                 LEFT JOIN copies cp ON cp.id = l.copy_id
                 LEFT JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE l.origem = ? AND l.eu_disse IS NOT NULL
                  AND l.eu_disse <> l.grade
                ORDER BY l.id DESC LIMIT ?""",
            (ORIGEM_MAO, int(limite))).fetchall()
    except sqlite3.Error:
        return []
    fora = []
    for r in rows:
        txt = " ".join(x for x in (r["escapou"], r["motivos"], r["eu_motivos"])
                       if x)
        fora.append({
            "copy_id": r["copy_id"],
            "carta": (r["nm"] or "").split(" // ", 1)[0],
            "foto": r["photo_path"] or r["foto"] or "",
            "verso": r["verso"] or "",
            "eu_disse": r["eu_disse"], "ele_disse": r["grade"],
            "escapou": r["escapou"] or "", "motivos": r["motivos"] or "",
            "sentido": sentido(r["eu_disse"], r["grade"]),
            "zonas": _zonas(txt), "em": (r["at"] or "")[:10],
        })
    return fora


def padroes(con) -> list[dict]:
    """Os ERROS REPETIDOS, do mais repetido para o menos: `[{sentido, zona, n,
    frase}]`.

    É a metade do *"dar mais peso aos erros repetidos"* que tem de ser contável:
    se ele me corrigiu três vezes por eu ser optimista com o branqueamento das
    bordas, isso fica escrito com um 3 à frente e é a primeira coisa que o
    `para_avaliar` manda ler.
    """
    c: Counter = Counter()
    for e in exemplos(con, limite=200):
        if not e["sentido"]:
            continue
        for z in e["zonas"] or ["(sem zona escrita)"]:
            c[(e["sentido"], z)] += 1
    fora = []
    for (snt, zona), n in c.most_common():
        fora.append({"sentido": snt, "zona": zona, "n": n,
                     "frase": f"já fui corrigido {n}× por estar {snt} "
                              f"com «{zona}» — olha duas vezes para isso"})
    return fora


def acerto(con) -> dict:
    """A TAXA DE ACERTO: de N escalões propostos, quantos ele aceitou sem mexer.

    `{propostos, corrigidos, aceites, pct, por_escalao}`. É assim que se sabe se
    o critério está a melhorar — sem este número, «vais melhorando o teu
    critério» não se podia confirmar nem desmentir.

    **Proposto** é um juízo meu que foi APLICADO (`origem = foto`); **corrigido**
    é um que ele veio mudar depois. Um juízo meu recusado à entrada (porque ele
    já tinha escrito à mão) não conta para nenhum dos dois: nunca chegou a estar
    em vigor.
    """
    try:
        props = con.execute(
            "SELECT copy_id, grade, id FROM condition_log "
            "WHERE origem = ? AND aplicado = 1 ORDER BY id", (ORIGEM_FOTO,)
        ).fetchall()
        corr = con.execute(
            "SELECT copy_id, grade, eu_disse, id FROM condition_log "
            "WHERE origem = ? AND aplicado = 1 ORDER BY id", (ORIGEM_MAO,)
        ).fetchall()
    except sqlite3.Error:
        return {"propostos": 0, "corrigidos": 0, "aceites": 0, "pct": None,
                "por_escalao": {}}
    # Um proposto diz-se CORRIGIDO quando existe uma correcção à mão DEPOIS dele
    # para a mesma cópia e com outro escalão.
    por_copia: dict[int, list] = {}
    for r in corr:
        por_copia.setdefault(r["copy_id"], []).append(r)
    corrigidos, por_escalao = 0, {}
    for p in props:
        d = por_escalao.setdefault(p["grade"], {"n": 0, "corrigidos": 0})
        d["n"] += 1
        depois = [r for r in por_copia.get(p["copy_id"], []) if r["id"] > p["id"]]
        if any(normalizar(r["grade"]) != normalizar(p["grade"]) for r in depois):
            corrigidos += 1
            d["corrigidos"] += 1
    n = len(props)
    return {"propostos": n, "corrigidos": corrigidos, "aceites": n - corrigidos,
            "pct": (round(100 * (n - corrigidos) / n) if n else None),
            "por_escalao": por_escalao}


# ---------------------------------------------------------------------------
# O CRITÉRIO EM FICHEIRO — para ser LIDO, não para viver na minha cabeça
# ---------------------------------------------------------------------------
CRITERIO = "estado-criterio.md"
MARCA_APRENDIDO = "## Aprendido com o André"


def ficheiro_criterio() -> Path:
    return db.pasta_dados() / CRITERIO


def criterio() -> str:
    """O texto do critério, tal como está no disco. Vazio se o ficheiro não
    existir — e quem avalia tem de dizer isso em voz alta em vez de julgar de
    cabeça."""
    p = ficheiro_criterio()
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def escrever_aprendido(con, path: Path | None = None) -> Path | None:
    """Reescreve a secção «Aprendido com o André» do critério, datada.

    **Só com o que veio de correcções dele** — nunca com palpites meus: é o que
    separa um critério que aprende de um critério que deriva. A secção é
    substituída de cada vez (é uma vista das correcções, não um histórico; o
    histórico é o `condition_log`).
    """
    p = Path(path) if path else ficheiro_criterio()
    if not p.is_file():
        return None
    texto = p.read_text(encoding="utf-8")
    base = texto.split(MARCA_APRENDIDO, 1)[0].rstrip()
    linhas = [base, "", MARCA_APRENDIDO, "",
              f"*Gerado de {len(exemplos(con, 200))} correcções dele, em "
              f"{_hoje()}. Só entra aqui o que veio de uma correcção — nunca um "
              f"palpite meu.*", ""]
    pd = padroes(con)
    if pd:
        linhas += ["### Erros repetidos (olhar duas vezes)", ""]
        linhas += [f"- **{d['n']}×** {d['sentido']} com «{d['zona']}»" for d in pd]
        linhas.append("")
    ex = exemplos(con, 20)
    if ex:
        linhas += ["### As correcções, uma a uma", ""]
        for e in ex:
            quem = e["carta"] or f"cópia {e['copy_id']}"
            linhas.append(
                f"- `{e['em']}` **{quem}** — "
                f"eu disse **{e['eu_disse']}**, ele disse **{e['ele_disse']}**"
                + (f". Escapou-me: {e['escapou']}" if e["escapou"] else "")
                + (f" (foto `{Path(e['foto']).name}`)" if e["foto"] else ""))
        linhas.append("")
    if not pd and not ex:
        linhas += ["Ainda não há nenhuma correcção dele. O critério em vigor é o "
                   "do Cardmarket, acima, e mais nada.", ""]
    a = acerto(con)
    if a["propostos"]:
        linhas += [f"**Taxa de acerto:** {a['aceites']} de {a['propostos']} "
                   f"escalões propostos ficaram como eu disse ({a['pct']} %).", ""]
    p.write_text("\n".join(linhas), encoding="utf-8")
    return p


def para_avaliar(con) -> str:
    """O TEXTO QUE O PASSO QUE AVALIA LÊ ANTES DE JULGAR.

    Critério + erros repetidos + as correcções recentes, nesta ordem. Vai para o
    `pendentes/esperadas.md` (que o Claude das fotos lê) e para o CLI. Existe
    como função para haver **um** texto: dois sítios a montar isto davam dois
    critérios, que é a lição do `event_tier`.
    """
    fora = [criterio() or
            "(FALTA O data/estado-criterio.md — sem ele não se atribui escalão "
            "nenhum: diz que não o encontraste.)"]
    pd = padroes(con)
    if pd:
        fora += ["", "## Erros repetidos meus (peso extra)", ""]
        fora += [f"- {d['frase']}" for d in pd]
    ex = exemplos(con, 8)
    if ex:
        fora += ["", "## As últimas correcções dele (exemplos rotulados)", ""]
        for e in ex:
            quem = e["carta"] or f"cópia {e['copy_id']}"
            fora.append(
                f"- {quem}: eu disse {e['eu_disse']}, ele disse {e['ele_disse']}"
                + (f" — {e['escapou']}" if e["escapou"] else ""))
    return "\n".join(fora)


# ---------------------------------------------------------------------------
# O PROGRESSO E O IMPACTO
# ---------------------------------------------------------------------------
def _mapa(con, cache: dict | None) -> dict:
    """O mapa de preços da corrida, UMA vez (`collection.mapa_precos`).

    **A CHAVE É A MESMA DO `fases` E DO `loadout.preco_da_copia`** —
    `cache["_precos"]["_mapa"]` —, de propósito: passando a esta função a cache do
    `fases.relatorio`, o mapa já está construído e não se varre a `price_latest`
    (86 480 linhas) outra vez. Medido a 2026-10-03 na página das fases: o bloco do
    estado custava **10,72 s** com uma cache por função, **3,34 s** com uma cache
    partilhada entre as três, e **~1 s** quando reusa a do `fases`. Os 10,7 s
    somavam-se ao relatório e empurravam o `arrumacao/candidatos.json` acima do
    tecto de 25 s do `webapp.ESPERA_DADOS` — um 503 na primeira vez que ele
    abrisse a página.
    """
    from . import collection                                 # noqa: PLC0415
    if cache is None:
        return collection.mapa_precos(con)
    pc = cache.setdefault("_precos", {})
    if pc.get("_mapa") is None:
        pc["_mapa"] = collection.mapa_precos(con)
    return pc["_mapa"]


def _terras(con, cache: dict | None) -> dict[str, set]:
    """As três listas DERIVADAS do catálogo, uma vez: duais, shock e fetchlands.

    Passa a cache DIRECTA ao `fases`, que é quem as deriva e quem as guarda
    (`_duais`/`_shock`/`_fetch`): com a cache do `fases.relatorio` já estão lá e
    não se varre o catálogo das terras outra vez.
    """
    from . import fases                                      # noqa: PLC0415
    if cache is not None and "_terras_estado" in cache:
        return cache["_terras_estado"]
    c = cache if cache is not None else {}
    fora = {"duais": set(fases.duais(con, c)["nomes"]),
            "shocks": set(fases.shocklands(con, c)["nomes"]),
            "fetches": set(fases.fetchlands(con, c)["nomes"])}
    if cache is not None:
        cache["_terras_estado"] = fora
    return fora


def frase_do_progresso(medidas: int, total: int) -> str:
    """*«0 de 1 678 cartas com estado medido»* — a linha honesta deste módulo.

    O separador de milhares é o mesmo do resto do site (`confirmado._n`): a lição
    de 2026-09-24 é que *"a conta estava certa nas seis páginas; o que mudava era
    o separador"*.
    """
    from . import confirmado                                  # noqa: PLC0415
    nome = "carta" if total == 1 else "cartas"
    if total and medidas == total:
        return f"as {confirmado._n(total)} {nome} têm estado medido"
    return (f"{confirmado._n(medidas)} de {confirmado._n(total)} {nome} "
            f"com estado medido")


def progresso(con, cache: dict | None = None) -> dict:
    """Quanto da colecção tem estado MEDIDO, em cartas e em euros.

    Usa a conta única do valor (2026-09-24: `collection.mapa_precos` +
    `preco_impressao`) e as duas metades do `confirmado.metades` — não se
    inventou uma terceira contagem. O `cache` partilha o mapa de preços com a
    `lista_curta` e o `impacto` (ver `_mapa`).
    """
    from . import collection, confirmado                     # noqa: PLC0415
    mapa = _mapa(con, cache)
    por_origem: dict[str, dict] = {}
    por_grade: dict[str, dict] = {}
    # As CARTAS contam-se em inteiros e os EUROS em float: com o `q_tot` a nascer
    # `0.0` a frase saía *«0 de 1678.0 cartas»*, que é o defeito dos separadores
    # de 2026-09-24 outra vez, com um ponto decimal em vez de uma vírgula.
    q_tot = q_med = com_verso = 0
    v_tot = v_med = 0.0
    for r in con.execute(
            f"""SELECT cp.id, cp.scryfall_id sid, cp.finish fin, cp.quantity q,
                       cp.condition cond, cp.condition_origem org,
                       cp.verso_path verso
                  FROM copies cp WHERE {collection.na_estante()}"""):
        p, _f = collection.preco_impressao(mapa, r["sid"], r["fin"])
        org = origem_de({"condition_origem": r["org"]})
        g = normalizar(r["cond"]) or OMISSAO
        q = int(r["q"] or 0)
        d = aplicar(p, g, origem=org)
        v = (d["unit"] or 0) * q
        for alvo, chave in ((por_origem, org), (por_grade, g)):
            e = alvo.setdefault(chave, {"q": 0, "valor": 0.0, "linhas": 0})
            e["q"] += q
            e["valor"] = round(e["valor"] + v, 2)
            e["linhas"] += 1
        q_tot += q
        v_tot += v
        if medido(org):
            q_med += q
            v_med += v
        if r["verso"]:
            com_verso += q
    return {
        "cartas": confirmado.metades(q_med, q_tot),
        "valor": confirmado.euros(v_med, v_tot),
        # A FRASE É DESTA PERGUNTA, e não da do `confirmado`. As duas metades
        # saem do mesmo `metades()` (não se fez uma segunda contagem), mas a
        # `frase` dele diz *«confirmadas por foto»*, que é a campanha de 20/09 e
        # é outra coisa: uma cópia pode ter foto da FRENTE e continuar sem
        # estado medido. Pôr aqui a frase dele era a página a prometer uma coisa
        # e a medir outra.
        "frase": frase_do_progresso(q_med, q_tot),
        "com_verso": com_verso,
        "por_origem": {k: dict(v, rotulo=ROTULO_ORIGEM[k])
                       for k, v in sorted(por_origem.items())},
        "por_grade": {k: por_grade[k] for k in ESCALA if k in por_grade},
        "acerto": acerto(con),
        "padroes": padroes(con),
        "nota_factor": nota_do_factor(),
        "nota_verso": PORQUE_VERSO,
    }


def lista_curta(con, *, inclui_venda: bool | None = None,
                max_fotos: int | None = None, cache: dict | None = None) -> dict:
    """A LISTA CURTA: as cópias FORA dos decks a que ainda falta o verso.

    É a resposta à decisão dele de 2026-10-03: *"ele NÃO pode decidir a
    verso-ou-não com a carta na mão, porque no momento em que fotografa os extras
    ainda não sabe o que vai guardar nem o que vai vender — essa decisão só
    existe depois de tudo fotografado. Por isso o SISTEMA decide (…) e dá-lhe uma
    LISTA CURTA para ele voltar lá uma vez. Não o ponhas a decidir 400 vezes."*

    Logo: nos Extras ele fotografa **só a frente**, de uma ponta à outra, sem
    parar para pensar. Depois **o sistema** marca quem precisa de verso —
    Reserved List, as dez duais originais, shocklands, fetchlands — e isto é a
    lista para ele voltar lá uma vez. As quatro listas DERIVAM do catálogo
    (`fases`) e não há uma única carta escrita à mão.

    `inclui_venda` acrescenta o que vai à venda. Por omissão segue o
    **`venda.mostrar`** — hoje `false`, por isso hoje **não entra**: é o *"e mais
    tarde o que for para venda"* dele, e fica a funcionar sozinho no dia em que
    ele voltar a ligar a venda, sem ninguém mexer aqui.

    As fotos agrupam-se em **até 4 cartas**, pela mesma `fotos.agrupar` da Fase 2
    e da Fase 4 — a regra das quatro cartas é a mesma em todo o lado —, da mais
    cara para a mais barata, que é a ordem que ele escolheu a 2026-10-01.
    """
    from . import collection, fotos as fm, loadout, paginas, venda
    t = _terras(con, cache)
    duais, shocks, fetches = t["duais"], t["shocks"], t["fetches"]
    inclui_venda = venda.mostrar() if inclui_venda is None else bool(inclui_venda)
    mapa = _mapa(con, cache)
    linhas, tipos = [], {}
    for r in con.execute(f"""
            SELECT cp.id, cp.scryfall_id sid, cp.quantity q, cp.finish,
                   cp.language lang, COALESCE(cp.condition,'NM') cond,
                   cp.condition_origem cond_origem, cp.verso_path verso,
                   c.name nm, c.set_code, c.type_line,
                   COALESCE(c.reserved, 0) rl,
                   COALESCE((SELECT SUM(a.quantity) FROM copy_allocation a
                              WHERE a.copy_id = cp.id), 0) na_caixa
              FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
             WHERE {collection.jogaveis()}"""):
        fora = int(r["q"]) - min(int(r["na_caixa"] or 0), int(r["q"]))
        if fora <= 0 or r["verso"]:
            continue                       # está num deck, ou já tem verso
        nm = (r["nm"] or "").split(" // ", 1)[0]
        motivos = motivos_fora_dos_decks(
            {"nm": nm, "rl": bool(r["rl"]), "copy_id": r["id"]},
            duais=duais, shocks=shocks, fetches=fetches,
            venda=None if not inclui_venda else _copias_da_venda(con))
        if not motivos:
            continue
        p, _f = collection.preco_impressao(mapa, r["sid"], r["finish"])
        unit = aplicar(p, r["cond"],
                       origem=origem_de({"condition_origem": r["cond_origem"]})
                       )["unit"]
        tipos[nm] = paginas.tipo_de(r["type_line"] or "")
        linhas.append({
            "nm": nm, "copy_id": r["id"], "q": fora,
            "set": (r["set_code"] or "").upper(),
            "lang": (r["lang"] or "en").upper(), "finish": r["finish"],
            "foil": loadout.e_foil(r["finish"]), "cond": r["cond"],
            "unit": unit, "rl": bool(r["rl"]),
            "porque": [MOTIVOS_VERSO[m] for m in motivos],
        })
    # Da mais cara para a mais barata: é o que ele pediu para a Fase 4, e a razão
    # é a mesma — se parar a meio, parou nas baratas.
    linhas.sort(key=lambda l: (-((l["unit"] or 0) * l["q"]), l["nm"], l["copy_id"]))
    fotos_ = fm.agrupar(linhas, tipos=tipos, por_tipo=False, prefixo="lc-")
    cortadas = 0
    if max_fotos and len(fotos_) > max_fotos:
        cortadas = len(fotos_) - max_fotos
        fotos_ = fotos_[:max_fotos]
    return {
        "fotos": fotos_, "linhas": linhas,
        "cartas": sum(l["q"] for l in linhas),
        "valor": round(sum((l["unit"] or 0) * l["q"] for l in linhas), 2),
        "cortadas": cortadas, "inclui_venda": inclui_venda,
        "barra": fm.barra(fotos_),
        "porque": PORQUE_VERSO,
        "nota": ("Nos Extras fotografa só a FRENTE, de uma ponta à outra. Esta "
                 "lista é o que precisa de verso, e sai sozinha depois de o "
                 "sistema saber que carta é cada uma — não é uma decisão para "
                 "tomares com a carta na mão."),
    }


def _copias_da_venda(con) -> set[int]:
    """Os `copy_id` que a venda de hoje ofereceria. Só se chama quando a venda
    está à vista — o relatório é caro e hoje a resposta não é precisa."""
    from . import loadout                                    # noqa: PLC0415
    try:
        rep = loadout.report(con)
    except Exception:                                        # noqa: BLE001
        return set()
    fora = set()
    for k in ("venda", "venda_rl"):
        for l in rep.get(k) or ():
            for cid, _q in l.get("copias") or ():
                fora.add(int(cid))
    return fora


def impacto(con, descer: int = 1, cache: dict | None = None) -> dict:
    """QUANTO ESTÁ EM JOGO: o valor de hoje contra o valor se a Reserved List e
    as duais caírem `descer` escalão.

    É a pergunta do André — *"quero o número para ele perceber o que está em
    jogo"* — e vive no código (como o `precos comparar`) e não num script de
    medição que se perde.
    """
    from . import collection                                 # noqa: PLC0415
    mapa = _mapa(con, cache)
    # As três listas DERIVAM do catálogo (`fases`, 2026-10-01) e partilham a
    # mesma varredura pela cache — não se escreve aqui o nome de uma só carta.
    t = _terras(con, cache)
    duais, shocks, fetches = t["duais"], t["shocks"], t["fetches"]
    hoje = depois = 0.0
    n_mexe = q_mexe = 0
    linhas = []
    for r in con.execute(
            f"""SELECT cp.id, cp.scryfall_id sid, cp.finish fin, cp.quantity q,
                       cp.condition cond, c.name nm, c.set_code,
                       COALESCE(c.reserved, 0) rl
                  FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                 WHERE {collection.na_estante()}"""):
        p, _f = collection.preco_impressao(mapa, r["sid"], r["fin"])
        g = normalizar(r["cond"]) or OMISSAO
        q = int(r["q"] or 0)
        agora = (aplicar(p, g)["unit"] or 0) * q
        hoje += agora
        nm = (r["nm"] or "").split(" // ", 1)[0]
        alvo = bool(r["rl"]) or nm in duais or nm in shocks or nm in fetches
        if alvo:
            i = min(ESCALA.index(g) + max(int(descer), 0), len(ESCALA) - 1)
            g2 = ESCALA[i]
            novo = (aplicar(p, g2)["unit"] or 0) * q
            depois += novo
            if round(novo, 2) != round(agora, 2):
                n_mexe += 1
                q_mexe += q
                linhas.append({
                    "copy_id": r["id"], "nm": nm,
                    "set": (r["set_code"] or "").upper(), "q": q,
                    "de": g, "para": g2,
                    "antes": round(agora, 2), "depois": round(novo, 2),
                    "perde": round(agora - novo, 2),
                    "porque": ("Reserved List" if r["rl"] else
                               "dual original" if nm in duais else
                               "shockland" if nm in shocks else "fetchland"),
                })
        else:
            depois += agora
    linhas.sort(key=lambda l: -l["perde"])
    return {"hoje": round(hoje, 2), "depois": round(depois, 2),
            "perde": round(hoje - depois, 2),
            "pct": (round(100 * (hoje - depois) / hoje, 1) if hoje else 0),
            "descer": descer, "linhas_afectadas": n_mexe, "cartas": q_mexe,
            "piores": linhas[:20], "nota": nota_do_factor()}


def texto(con) -> str:
    """O relatório curto, para o `cli estado` e para o log do `daily`."""
    p = progresso(con)
    out = ["ESTADO DAS CARTAS (escala do Cardmarket)",
           f"  {p['frase']}  ·  valor medido {p['valor']['texto_confirmado']} "
           f"de {p['valor']['texto_total']}",
           f"  com foto do verso: {p['com_verso']}", ""]
    for k, v in p["por_origem"].items():
        out.append(f"  {v['rotulo'][:40]:<40} {v['q']:>5} cartas  "
                   f"{v['valor']:>12.2f} EUR")
    out.append("")
    for g, v in p["por_grade"].items():
        out.append(f"  {g} {NOMES[g][:20]:<20} {v['q']:>5} cartas  "
                   f"{v['valor']:>12.2f} EUR")
    a = p["acerto"]
    if a["propostos"]:
        out += ["", f"  taxa de acerto: {a['aceites']}/{a['propostos']} "
                    f"({a['pct']} %)"]
    if p["padroes"]:
        out.append("")
        out += [f"  ! {d['frase']}" for d in p["padroes"]]
    out += ["", "  " + p["nota_factor"]]
    return "\n".join(out)
