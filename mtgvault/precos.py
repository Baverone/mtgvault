"""O MODO DE PREÇO: market, best ou a média dos dois (André, 2026-09-25).

Palavras dele, à letra: *"tal como no riftvault, o preço da colecção pode ser
pelo market value do cardtrader, ou o best value, ou a média dos 2"*.

O QUE O RIFTVAULT FAZ MESMO
    Foi lido antes de se escrever uma linha (`riftvault/prices.py`, `oferta()`).
    Ele guarda **um só** preço por impressão: `min(price_cents)` das ofertas
    utilizáveis (sem graded, sem vendedor de férias, sem altered/signed, estado
    em `OK_CONDITIONS`, língua em `precos.linguas`, EUR, > 0). Isso é o **best
    value** — não há market value nem média no riftvault. O desenho dos três
    modos é novo; o que se copiou de lá foi o **filtro das ofertas** e o **sítio
    da configuração** (`precos.linguas`), para ele não ter de se lembrar de duas
    linguagens. Os nomes `market` / `best` / `media` e a chave `precos.modo`
    caem no `riftvault_config.json` sem mudar uma letra no dia em que ele quiser
    lá os três (hoje o riftvault é sempre `best`).

O QUE O CARDTRADER DÁ MESMO (sonda à API a 2026-09-25, `/blueprints/export` e
`/marketplace/products` da expansão `ody`)
    **Não há campo nenhum de "market value".** Os blueprints não trazem preço
    nenhum (`id, name, version, game_id, category_id, expansion_id, image,
    scryfall_id, tcg_player_id, card_market_ids, fixed_properties,
    editable_properties`) e cada oferta traz só o seu `price_cents`. Portanto:

      best value   = a oferta mais barata das utilizáveis   (o que ele paga)
      market value = a MEDIANA das ofertas utilizáveis      (o que o mercado pede)

    A mediana e não a média: a cauda de cópias raras/estrangeiras a 300 € puxa
    uma média que ninguém pratica. Medido nesse dia em `ody`: Tainted Pact best
    20,27 € contra mediana 34,27 € (28 ofertas) — a diferença é o ponto todo.

AS DUAS COLUNAS JÁ EXISTIAM E QUEREM DIZER ISTO
    `price_latest`/`price_history` têm `low` e `trend` desde sempre. O modo não
    inventa colunas: `best` lê `low`, `market` lê `trend`, `media` lê os dois. É
    também o que o `collection.CENARIOS` já dizia.

A RECEITA — E PORQUE É QUE ELA É O QUE SALVA A REGRA DA RESERVED LIST
    O perigo não é o modo: é a MESMA coluna ter querido dizer coisas
    diferentes em dias diferentes. Até hoje o `fetch_cardtrader_prices` escrevia
    `low = trend = min(ofertas)`; a partir de hoje escreve `trend` = mediana.
    Comparar a mediana de hoje com o mínimo de há 90 dias é inventar uma subida
    de dezenas por cento que nunca aconteceu — e é essa percentagem que decide
    se uma carta da Reserved List, que não se volta a imprimir, vai à venda.

    Por isso cada linha de preço passa a dizer a RECEITA que a produziu
    (`price_latest.receita` / `price_history.receita`), e a regra dos 5 % só
    compara pontos da MESMA receita. Mudou a receita → a janela encolhe para o
    que existe desde a mudança → abaixo do mínimo a resposta é
    `rl_sem_historico`, a terceira resposta que já existia. Nunca "não subiu".

    E o mesmo vale para o MODO: trocá-lo muda o número que ele anda a ver, por
    isso `precos.modo_desde` trava a janela da RL até haver `rl_janela_minima_dias`
    dias medidos no modo novo. Uma RL vendida não volta.

O PREÇO DE REFERÊNCIA É O DA IMPRESSÃO QUE ELE TEM (André, 2026-09-25, à letra:
*"o que tinha pedido era alterar o preço REFERÊNCIA para Market Price ou Best
Deal, ao invés de MÍNIMO"*)
    Havia DOIS mínimos, e só um tinha sido tratado:

      1. o mínimo entre OFERTAS — o preço de um Mountain de Odyssey eram os
         0,28 € de uma cópia italiana «Poor» com o verso escrito à mão. Fechado
         a 2026-09-25 pelo `oferta_utilizavel`.
      2. o mínimo entre IMPRESSÕES — o `loadout.card_price` faz `MIN` sobre
         todas as impressões do mesmo NOME. Para o que FALTA está certo (é
         quanto custa comprá-la, e compra-se a mais barata); aplicado a uma
         cópia QUE ELE TEM é avaliar a Underground Sea de Revised pela
         reimpressão mais barata que exista. Desde hoje o preço de REFERÊNCIA de
         uma cópia é o da IMPRESSÃO DELA (`loadout.preco_da_copia`), e o mínimo
         entre impressões só entra como ÚLTIMO RECURSO, dito na `origem`: um
         preço e uma estimativa não se somam calados.

A FONTE É UMA CADEIA, NÃO UMA SÓ (2026-09-25)
    `market` e `best` só querem dizer coisas diferentes com as ofertas de um
    marketplace por trás, por isso a fonte principal passou a `cardtrader`. Mas o
    CardTrader não cota 36 % das cópias dele (as PT, as edições antigas, as foil
    que ninguém tem à venda hoje) — e um terço da colecção «sem preço» é pior do
    que o mínimo que isto veio corrigir. Por isso `fontes()` é uma CADEIA: por
    IMPRESSÃO, a primeira fonte que a cote ganha, e a linha diz de qual veio
    (`fonte`). **Nunca é um `MIN` por cima de todas** — isso era misturar duas
    escalas, que é precisamente o que a receita existe para impedir.

    A cadeia é mais uma RÉGUA: trocá-la carimba `precos.fonte_desde`, e o
    `regua_desde()` trava a janela da Reserved List exactamente como o
    `modo_desde` já fazia. E o histórico continua a ler-se **só da fonte
    principal** (`loadout._historico`): uma percentagem medida entre um ponto do
    CardTrader e um do Cardmarket é uma subida que nunca aconteceu.
"""
from __future__ import annotations

import contextlib
import re
import sqlite3
import statistics

from . import configio

# Os três modos. Os nomes são os dele, à letra, e são os que hão-de entrar no
# `riftvault_config.json` quando lá forem precisos.
MARKET, BEST, MEDIA = "market", "best", "media"
MODOS = (MARKET, BEST, MEDIA)
MODO_OMISSAO = MARKET

ROTULOS = {
    MARKET: "market value (o que o mercado pede)",
    BEST: "best value (a oferta mais barata)",
    MEDIA: "média dos dois",
}

# As receitas: como é que os números de uma linha foram produzidos.
#   `unico`      um só valor da fonte, copiado para `low` e `trend` (o bulk da
#                Scryfall, que é o Trend do Cardmarket; e o CardTrader antigo).
#                Aqui os três modos dão o MESMO número, de propósito.
#   `cm-guide`   low/trend/avg30 do price guide do Cardmarket.
#   `ct-ofertas` low = oferta mais barata, trend = mediana das ofertas.
RECEITA_UNICA = "unico"
RECEITA_CM_GUIDE = "cm-guide"
RECEITA_CT_OFERTAS = "ct-ofertas"

# O filtro de ofertas é o do riftvault (`prices._usable`), palavra por palavra:
# uma carta assinada, alterada, graded, de um vendedor de férias ou em estado
# «Played»/«Poor» não é o preço que ele paga nem o que o mercado pede.
ESTADOS_OK = frozenset({"Mint", "Near Mint", "Slightly Played", "Moderately Played"})
LINGUAS_OMISSAO = ("en", "pt")


# ---------------------------------------------------------------------------
# A configuração: `colecao_config.json → precos`
# ---------------------------------------------------------------------------
def bloco(cfg: dict | None = None) -> dict:
    """O bloco `precos` do config (vazio se não existir).

    Sem um `cfg` na mão lê-se pelo **`sources.config()`**, que é a leitura EM
    CACHE (recarrega quando o ficheiro muda) e a mesma que todo o motor usa. Ler
    pelo `configio.ler()` era abrir e fazer parse do `colecao_config.json` a
    cada chamada — e o `card_price` chama isto milhares de vezes por relatório,
    com o config a levar as listas escolhidas inteiras. Medido: o
    `precos comparar` na base dele passou de dezenas de minutos a segundos.
    """
    if cfg is None:
        from . import sources                              # noqa: PLC0415
        cfg = sources.config()
    b = cfg.get("precos")
    return b if isinstance(b, dict) else {}


# Um modo imposto em memória, para o `precos comparar` do CLI pôr os três lado
# a lado sem escrever no config (e para os testes). NUNCA é o caminho normal:
# quem decide é o ficheiro.
_FORCADO: str | None = None


def modo(cfg: dict | None = None) -> str:
    """O modo em vigor. Um valor desconhecido vale o de omissão — o config é
    editável à mão e uma gralha não pode deixar o site sem preços."""
    if _FORCADO:
        return _FORCADO
    v = str(bloco(cfg).get("modo") or "").strip().lower()
    return v if v in MODOS else MODO_OMISSAO


@contextlib.contextmanager
def forcar(qual: str):
    """Corre o bloco como se o modo fosse `qual`, sem tocar no config."""
    global _FORCADO                                        # noqa: PLW0603
    if qual not in MODOS:
        raise ValueError(f"modo {qual!r} — usa {', '.join(MODOS)}")
    antes, _FORCADO = _FORCADO, qual
    try:
        yield qual
    finally:
        _FORCADO = antes


def fonte(cfg: dict | None = None) -> str:
    """A fonte PRINCIPAL dos preços — a primeira da cadeia (ver `fontes`).

    Fica no config pela mesma razão que o `collection.mapa_precos` a tinha fixa
    no código: ligar uma fonte nova mudava o valor da colecção sem ninguém mexer
    numa carta. O que ela responde é *"qual é a régua"*, e por isso é ela — e só
    ela — que o histórico da Reserved List lê.
    """
    return fontes(cfg)[0]


# O nome de uma fonte entra em SQL como LITERAL (a cadeia é uma cláusula `CASE`,
# e um `?` não serve para ordenar). Vem do config, que ele edita à mão: sem esta
# tranca uma gralha com uma plica era uma injecção na consulta do valor da
# colecção.
_NOME_FONTE = re.compile(r"[a-z0-9_-]{1,32}")


def _fonte_limpa(f) -> str | None:
    f = str(f or "").strip().lower()
    return f if _NOME_FONTE.fullmatch(f) else None


def fontes(cfg: dict | None = None) -> tuple[str, ...]:
    """A CADEIA de fontes, por ordem: a principal e as de recurso.

    Por IMPRESSÃO, a primeira que a cote ganha. Não é um `MIN` por cima de todas
    (isso misturava duas escalas de preço na mesma soma, que é o defeito que a
    receita existe para impedir): é *"pergunta ao CardTrader; se ele não a tem à
    venda, pergunta ao Cardmarket, e diz que foi de lá"*.

    `precos.fonte` é a principal e `precos.fonte_recurso` as seguintes (uma
    string ou uma lista). Uma fonte repetida conta uma vez, e a ordem é a do
    config.
    """
    b = bloco(cfg)
    rec = b.get("fonte_recurso")
    if isinstance(rec, str):
        rec = [rec]
    elif not isinstance(rec, list):
        rec = []
    fora: list[str] = []
    for f in [b.get("fonte") or "cardmarket", *rec]:
        limpa = _fonte_limpa(f)
        if limpa and limpa not in fora:
            fora.append(limpa)
    return tuple(fora) or ("cardmarket",)


def modo_desde(cfg: dict | None = None) -> str | None:
    """A data (ISO) em que o modo passou a ser este. Escrita por quem o troca."""
    v = bloco(cfg).get("modo_desde")
    return str(v) if v else None


def fonte_serie(cfg: dict | None = None) -> str:
    """A fonte das SÉRIES de preço — as colunas *hoje* / *há 1 mês* e o gráfico
    da Reserved List, que são o MERCADO de uma impressão ao longo do tempo.

    Uma percentagem mede-se de ponta a ponta na MESMA fonte; ao contrário do
    VALOR de uma cópia, aqui não há cadeia que valha — um ponto do CardTrader e
    outro do Cardmarket dão uma subida que não aconteceu. E a fonte certa para
    uma série é a que TEM série: por omissão a ÚLTIMA da cadeia, que é o price
    guide (o CardTrader é o mercado ao vivo e a sua história começa no dia em
    que entrou). `precos.fonte_serie` no config troca-a.

    Não confundir com a régua da regra dos 5 %: essa é a fonte PRINCIPAL, e é
    por isso que ela pode responder *"não sei"* enquanto esta coluna já mostra
    uma evolução — são duas perguntas, uma sobre as cópias dele e outra sobre o
    mercado de uma impressão.
    """
    return _fonte_limpa(bloco(cfg).get("fonte_serie")) or fontes(cfg)[-1]


def fonte_desde(cfg: dict | None = None) -> str | None:
    """A data (ISO) em que a CADEIA de fontes passou a ser esta."""
    v = bloco(cfg).get("fonte_desde")
    return str(v) if v else None


def regua_desde(cfg: dict | None = None) -> str | None:
    """Desde quando é que os números que ele vê são medidos com ESTA régua.

    A régua é o par (cadeia de fontes, modo): mudar qualquer um deles muda o
    número sem o mercado ter mexido. É a data mais RECENTE das duas — a regra
    dos 5 % da Reserved List encurta a janela até aqui, e enquanto não houver
    `venda.rl_janela_minima_dias` dias medidos assim a resposta é
    `rl_sem_historico`, nunca *"não subiu"*. Uma RL vendida não volta.
    """
    datas = [d for d in (modo_desde(cfg), fonte_desde(cfg)) if d]
    return max(datas) if datas else None


def linguas(cfg: dict | None = None) -> frozenset[str]:
    """As línguas cujas ofertas contam para o preço (`precos.linguas`) — a mesma
    chave do riftvault. Ele compra EN e, no Premodern, PT."""
    v = bloco(cfg).get("linguas")
    lista = [str(x).strip().lower() for x in v if str(x).strip()] if isinstance(v, list) else []
    return frozenset(lista or LINGUAS_OMISSAO)


# ---------------------------------------------------------------------------
# O preço, a partir das duas colunas
# ---------------------------------------------------------------------------
def de_valores(low, trend, qual: str | None = None) -> float | None:
    """O preço destas duas colunas no modo pedido, ou `None` — **nunca 0 €**.

    Uma carta que a fonte escolhida não cota é *"sem preço"*: devolver zero
    punha-a a valer nada numa soma, que é a mentira mais cara que uma página de
    preços pode contar.

    Na média, quando só existe um dos dois, o preço é esse. Com a receita
    `unico` os dois são iguais e não há caso; com `ct-ofertas` nascem sempre
    juntos; sobra o price guide do Cardmarket, onde uma impressão pode ter `low`
    e não ter `trend` — e aí a média do que existe é a única resposta honesta
    que não é inventar o outro lado.
    """
    qual = qual if qual in MODOS else modo()
    if qual == BEST:
        return low if low is not None else None
    if qual == MARKET:
        return trend if trend is not None else None
    valores = [v for v in (low, trend) if v is not None]
    return sum(valores) / len(valores) if valores else None


def sql(qual: str | None = None, alias: str = "p") -> str:
    """A EXPRESSÃO SQL do preço, para quem soma dentro da consulta.

    Existe para haver um sítio só: o `MIN(p.trend)` estava escrito à mão em oito
    consultas, e a primeira que se esquecesse do modo punha duas páginas a dizer
    dois números para o mesmo dinheiro — que é o defeito que a conta única do
    valor (2026-09-24) veio corrigir.
    """
    qual = qual if qual in MODOS else modo()
    a = f"{alias}." if alias else ""
    if qual == BEST:
        return f"{a}low"
    if qual == MARKET:
        return f"{a}trend"
    # NULL só quando os dois faltam; com um só, vale esse (ver `de_valores`).
    return (f"(COALESCE({a}trend, {a}low) + COALESCE({a}low, {a}trend)) / 2.0")


def sql_impressao(qual: str | None = None, fontes_: tuple[str, ...] | None = None,
                  sid: str = "c.scryfall_id", fin: str = "f.finish",
                  base: str = "price_latest") -> str:
    """O preço de UMA impressão e acabamento, na CADEIA: uma subconsulta escalar.

    A cadeia num sítio só, como o `sql()` fez ao `MIN(p.trend)`. O `ORDER BY
    CASE source ... LIMIT 1` é que faz *"a primeira da cadeia que a cote"* — um
    `MIN` sobre as fontes seria comparar a mediana das ofertas do CardTrader com
    o Trend do Cardmarket e ficar com a mais barata, que é somar duas escalas
    diferentes.

    **É correlacionada de propósito.** A primeira versão era uma tabela derivada
    com `ROW_NUMBER` por cima da `price_latest` inteira, e o `card_price` é
    chamado milhares de vezes por relatório: 86 480 linhas varridas por chamada
    punham o relatório em dezenas de minutos. Assim, o SQLite entra pela chave
    primária `(scryfall_id, source, finish)` e lê as duas linhas que interessam.
    (Materializá-la numa temporária resolvia o tempo e criava outro problema: o
    esquema `temp` passa a aparecer no `PRAGMA database_list`, e há quinze
    ficheiros de teste a apanhar o catálogo pelo ÍNDICE 1 dessa lista.)
    """
    qual = qual if qual in MODOS else modo()
    fs = tuple(fontes_) if fontes_ else fontes()
    expr = sql(qual, alias="q")
    casos = " ".join(f"WHEN '{f}' THEN {i}" for i, f in enumerate(fs))
    lista = ", ".join(f"'{f}'" for f in fs)
    return (f"(SELECT {expr} FROM {base} q "
            f"WHERE q.scryfall_id = {sid} AND q.finish = {fin} "
            f"AND q.source IN ({lista}) AND {expr} IS NOT NULL "
            f"ORDER BY CASE q.source {casos} ELSE 99 END LIMIT 1)")


def sql_acabamentos(fins: tuple[str, ...]) -> str:
    """Os acabamentos aceites como tabela derivada `f(finish)`, com um `?` cada.

    Existe para o `sql_impressao` poder correlacionar-se com o acabamento sem
    que cada chamador invente o seu `UNION ALL`.
    """
    return "(" + " UNION ALL ".join(["SELECT ? AS finish"] * len(fins)) + ")"


# ---------------------------------------------------------------------------
# A receita em vigor
# ---------------------------------------------------------------------------
def receita_em_vigor(con: sqlite3.Connection, qual_fonte: str | None = None) -> str:
    """A receita com que os preços de HOJE desta fonte foram escritos.

    Lê-se da base e não do config: o que interessa é como os números foram
    mesmo produzidos, não o que o config diz que se pretende. Uma base sem
    linhas (ou anterior à coluna) vale `unico` — que é o que ela era.
    """
    f = qual_fonte or fonte()
    try:
        r = con.execute(
            "SELECT receita, COUNT(*) n FROM price_latest WHERE source = ? "
            "AND date = (SELECT MAX(date) FROM price_latest WHERE source = ?) "
            "GROUP BY receita ORDER BY n DESC LIMIT 1", (f, f)).fetchone()
    except sqlite3.Error:
        return RECEITA_UNICA
    return (r["receita"] if r and r["receita"] else RECEITA_UNICA)


def receitas_em_vigor(con: sqlite3.Connection,
                      fontes_: tuple[str, ...] | None = None) -> dict:
    """`{fonte: receita}` para a cadeia inteira. Cada fonte tem a sua."""
    return {f: receita_em_vigor(con, f) for f in (fontes_ or fontes())}


# DE ONDE VEIO O PREÇO DE REFERÊNCIA DE UMA CÓPIA (2026-09-25). Não é cosmética:
# `min-impressoes` é uma ESTIMATIVA — o preço da reimpressão mais barata, porque
# a impressão que ele tem não está cotada em fonte nenhuma — e quem a soma tem de
# a poder separar de um preço a sério.
ORIGEM_IMPRESSAO = "impressao"
ORIGEM_MIN_IMPRESSOES = "min-impressoes"
ORIGEM_SEM_PRECO = "sem-preco"

ROTULOS_ORIGEM = {
    ORIGEM_IMPRESSAO: "o preço desta impressão",
    ORIGEM_MIN_IMPRESSOES: "estimativa: a impressão mais barata desta carta "
                           "(esta não está cotada)",
    ORIGEM_SEM_PRECO: "sem preço em nenhuma fonte",
}


# ---------------------------------------------------------------------------
# As ofertas do CardTrader -> os dois valores
# ---------------------------------------------------------------------------
def oferta_utilizavel(o: dict, aceites: frozenset[str] | None = None) -> bool:
    """O filtro do riftvault (`prices._usable`), com a língua deste projecto."""
    h = o.get("properties_hash") or {}
    return bool(
        not o.get("graded")
        and not o.get("on_vacation")
        and not h.get("altered")
        and not h.get("signed")
        and h.get("condition") in ESTADOS_OK
        and h.get("mtg_language") in (aceites if aceites is not None else linguas())
        and o.get("price_currency") == "EUR"
        and (o.get("price_cents") or 0) > 0)


def gravar_modo(novo: str, path=None, hoje: str | None = None) -> dict:
    """Troca o modo no config e CARIMBA A DATA. Devolve `{antes, modo, desde}`.

    O carimbo (`precos.modo_desde`) é a metade que protege a Reserved List: o
    `loadout.avaliar_rl` usa-o para encurtar a janela, de modo que uma RL só
    volta a poder ir à venda quando houver `rl_janela_minima_dias` dias
    medidos e olhados no modo NOVO. Trocar de modo é, por uns dias, deixar de
    saber — e "não sei" tem resposta própria desde 2026-09-08.

    Trocar para o modo que já lá está é um no-op: não se carimba nada, porque
    nada mudou e reiniciar a janela por um clique sem efeito era castigá-lo.
    """
    from datetime import date                              # noqa: PLC0415
    novo = str(novo or "").strip().lower()
    if novo not in MODOS:
        raise ValueError(f"modo {novo!r} — usa {', '.join(MODOS)}")
    cfg = configio.ler(path)
    antes = modo(cfg)
    b = cfg.get("precos")
    if not isinstance(b, dict):
        b = cfg["precos"] = {}
    b["modo"] = novo
    if novo != antes:
        b["modo_desde"] = hoje or date.today().isoformat()
    configio.escrever(cfg, path)
    # A cache do config é partilhada com todo o motor: sem a esquecer aqui, o
    # `card_price` da mesma corrida continuava no modo antigo e quem falhasse
    # este passo tinha um botão que "não faz nada" sem erro nenhum.
    from . import sources                                   # noqa: PLC0415
    sources._CFG_CACHE.clear()
    return {"antes": antes, "modo": novo, "desde": b.get("modo_desde"),
            "mudou": novo != antes, "rotulo": ROTULOS[novo]}


def gravar_fonte(nova: str, recurso=None, path=None,
                 hoje: str | None = None) -> dict:
    """Troca a CADEIA de fontes e CARIMBA A DATA (`precos.fonte_desde`).

    O gémeo do `gravar_modo`, e pela mesma razão: a cadeia é uma régua, e trocar
    de régua é, por uns dias, deixar de saber. Sem o carimbo, passar de
    `cardmarket` para `cardtrader` punha a regra dos 5 % a comparar a mediana
    das ofertas de hoje com o Trend de há 90 dias — e a decidir, com essa
    percentagem inventada, se uma carta que não se volta a imprimir vai à venda.

    Trocar para a cadeia que já lá está é um no-op: não se carimba nada.
    """
    from datetime import date                              # noqa: PLC0415
    limpa = _fonte_limpa(nova)
    if not limpa:
        raise ValueError(f"fonte {nova!r} — só letras, dígitos, '-' e '_'")
    if isinstance(recurso, str):
        recurso = [recurso]
    cfg = configio.ler(path)
    antes = fontes(cfg)
    b = cfg.get("precos")
    if not isinstance(b, dict):
        b = cfg["precos"] = {}
    b["fonte"] = limpa
    if recurso is not None:
        limpas = [f for f in (_fonte_limpa(r) for r in recurso) if f]
        if len(limpas) != len(list(recurso)):
            raise ValueError("fonte de recurso inválida")
        b["fonte_recurso"] = limpas
    depois = fontes(cfg)
    if depois != antes:
        b["fonte_desde"] = hoje or date.today().isoformat()
    configio.escrever(cfg, path)
    from . import sources                                   # noqa: PLC0415
    sources._CFG_CACHE.clear()
    return {"antes": list(antes), "fontes": list(depois),
            "desde": b.get("fonte_desde"), "mudou": depois != antes}


def dois_valores(ofertas: list[dict]) -> dict:
    """`{low, trend, copias, n}` a partir das ofertas de um blueprint.

    `low` é a mais barata (best value) e `trend` a MEDIANA (market value) — ver
    o cabeçalho. As duas nascem da MESMA lista de ofertas, no mesmo instante:
    é isso que faz a média entre elas querer dizer alguma coisa, e é isso que
    permite trocar de modo sem trocar de dia.
    """
    if not ofertas:
        return {"low": None, "trend": None, "copias": 0, "n": 0}
    p = sorted(o["price_cents"] / 100 for o in ofertas)
    return {
        "low": round(p[0], 2),
        "trend": round(float(statistics.median(p)), 2),
        "copias": sum(int(o.get("quantity") or 1) for o in ofertas),
        "n": len(p),
    }
