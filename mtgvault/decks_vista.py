"""A ABA DECKS: formato -> deck -> cartas (André, 2026-10-04, à letra).

    *"Fazemos como no riftvault, fazes uma aba ou botao para decks:
      Dentro dos decks, formato,
      Dentro do formato, o nome do deck
      ordena por tipo de carta"*

E as duas metades que mudam o modelo de 02/10:

    *"CDEH, sao 2 decks, ambos tem link, cada deck tem as suas proprias cartas,
      fazes a imagem de cada carta, com + e - para eu marcar se tenho a carta"*
    *"Premodern, vou sleevar os decks tudo com sleeves iguais, nos decks ficam
      apenas as cartas que sao proprias do deck e cartas usadas em varios decks
      ficam de fora, vou imprimir proxie, e so meto as verdadeiras no deck quando
      for jogar com esse deck"*
    *"SPML a mesma coisa de Premodern"*

A CONTRADIÇÃO, E PORQUE É QUE ELA VIVE NO CONFIG
================================================
A 02/10 ele fixou *"cada deck tem as suas próprias cartas, ponto"* — e daí veio
a SOMA: três decks que pedem 4 Swords pedem 12. A 04/10 à tarde ele disse o
CONTRÁRIO para Premodern e SPML: a carta usada em vários decks **fica de fora**,
leva proxy, e a cópia verdadeira entra só quando ele joga aquele deck. Nesses
dois formatos uma cópia serve TODOS os decks e a necessidade é o **MÁXIMO**.

As duas regras estão certas, cada uma no seu formato. Por isso não se escolhe uma
delas no código: a resposta é uma chave de config, `regras_por_formato[].
cartas_partilhadas` — `rotativas` (máximo) ou `dedicadas` (soma) —, e o código lê
o config.

**É UM EIXO NOVO E NÃO O `dedicado` QUE JÁ LÁ ESTAVA.** O `dedicado` dos cinco
grupos quer dizer outra coisa (a caixa não empresta nem vai buscar cópias a
outra caixa — ver `loadout`), e desde 2026-09-19 vale `True` em toda a parte, à
força, no `resolve_slots`. Deduzir um do outro era amarrar duas perguntas
diferentes à mesma chave, que é exactamente como o `event_tier` começou.

**OS DOIS NÚMEROS MOSTRAM-SE SEMPRE**, lado a lado e com etiqueta — *«a somar:
12»* / *«a rodar: 4»* — mesmo o que a regra do formato não usa. É a diferença
entre eles que lhe diz quanto custa a decisão, e esconder o outro era
responder-lhe sem lhe dar a conta.

PRÓPRIAS E PARTILHADAS
======================
Num formato `rotativas`, as cartas de cada deck partem-se em duas listas
CONTADAS À PARTE:

  - **próprias** — entra só NESTE deck, entre os que ele marcou. Fica sleevada
    para sempre.
  - **partilhadas** — entra em 2 ou mais decks marcados. Fica de fora; o deck
    leva proxy; a verdadeira entra à hora de jogar.

**NÃO É UMA ETIQUETA DA CARTA: depende de QUAIS decks ele marcou.** Marcar mais
um deck pode passar uma carta de própria a partilhada, e desmarcar faz o
caminho de volta. Recalcula-se sempre; tem teste nas duas direcções.

Daí saem, de graça, duas listas que ele vai ter em cima da mesa e não pediu: os
**proxies a imprimir** de cada deck (= as partilhadas desse deck) e quantas
cartas ficam **sleevadas a sério** no formato (= as próprias de todos os decks
marcados).
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from . import caixas, loadout, marcas, nomes, padrao, sources, stock

# ---------------------------------------------------------------------------
# Os tipos de carta: DUAS listas, e são duas perguntas diferentes
# ---------------------------------------------------------------------------
#: A ORDEM DE APRESENTAÇÃO, à letra como ele a escreveu: *"ordena por tipo de
#: carta: Creature, Sorcery, Instant; Artifact, Enchantment, Planeswalker, Land,
#: Outras"*.
#:
#: É DELIBERADAMENTE outra que a do `paginas.TIPOS` (Creature, Planeswalker,
#: Sorcery, …, pedido dele de 2026-08-31, que é a ordem por que se LÊ uma
#: decklist). Duas ordens porque são duas perguntas; a do `paginas` não se tocou,
#: senão mudava o agrupamento da Deckboxes e do Showcase sem ninguém pedir.
#:
#: O COMANDANTE vem à cabeça, num grupo próprio (correcção aplicada a pedido do
#: supervisor, 2026-10-04): é a carta que identifica o deck, e enterrada no meio
#: dos Creature não se encontra. Só existe nos formatos de comandante.
COMANDANTE = "Commander"
ORDEM_TIPOS = [COMANDANTE, "Creature", "Sorcery", "Instant", "Artifact",
               "Enchantment", "Planeswalker", "Land", "Outras"]

#: A PRECEDÊNCIA DE CLASSIFICAÇÃO — em que grupo cai uma carta de vários tipos.
#: *"pelo mais ESPECÍFICO: um Artifact Creature conta como Creature (não como
#: Artifact), um Enchantment Creature como Creature, uma Artifact Land como
#: Land"*.
#:
#: Não é a `ORDEM_TIPOS` lida de cima para baixo, e a diferença morde: ali o
#: `Artifact` vem antes do `Land`, e por essa ordem uma Ancient Den (Artifact
#: Land) caía em Artifact — que é precisamente o que ele mandou corrigir. É
#: também onde esta lista se afasta do `paginas.tipo_de`, que responde Artifact
#: a essa carta (e continua a responder, para a Deckboxes não mudar).
#:
#: Dryad Arbor (Land Creature) cai em **Creature**: o Creature está à cabeça
#: porque é ele que ganha ao Artifact e ao Enchantment por ordem dele, e partir
#: a regra só para as terras-criatura era inventar uma excepção que ele não deu.
PRECEDENCIA = ["Creature", "Planeswalker", "Land", "Artifact", "Enchantment",
               "Instant", "Sorcery"]

#: Os formatos em que a primeira carta da lista é o COMANDANTE.
FORMATOS_COMANDANTE = {"cedh", "duel-commander", "commander"}

#: `cartas_partilhadas`: as duas respostas possíveis.
ROTATIVAS = "rotativas"    # uma cópia serve todos os decks -> MÁXIMO
DEDICADAS = "dedicadas"    # cada deck as suas              -> SOMA
#: Sem a chave escrita, SOMA. É o modelo de 02/10 (*"cada deck tem as suas
#: próprias cartas"*), e é o lado conservador: pedir a mais faz uma lista de
#: compras grande, pedir a menos faz-lhe faltar a carta à hora de jogar.
PARTILHA_OMISSAO = DEDICADAS


def tipo_da_carta(type_line: str | None, *, comandante: bool = False) -> str:
    """O grupo de uma carta nesta página, pelo tipo mais específico.

    `comandante` força o grupo do comandante — isso não sai do `type_line`
    (qualquer lendária pode ser comandante), sai da posição na lista.
    """
    if comandante:
        return COMANDANTE
    tl = (type_line or "").split(" // ")[0]
    for t in PRECEDENCIA:
        if re.search(rf"\b{t}\b", tl):
            return t
    return "Outras"


def ordenar_grupos(grupos) -> list[str]:
    """Os grupos presentes, pela ordem dele; o que não conhece vai para o fim."""
    tem = set(grupos)
    out = [t for t in ORDEM_TIPOS if t in tem]
    return out + sorted(tem - set(out))


# ---------------------------------------------------------------------------
# A regra do formato: soma ou máximo
# ---------------------------------------------------------------------------
def partilha_do_formato(fmt: str | None, regras: list[dict] | None = None) -> str:
    """`rotativas` | `dedicadas` para este formato, do config.

    Lê `regras_por_formato[].cartas_partilhadas` pelo `loadout.regra_do_formato`,
    que é quem já funde a excepção `por_formato` de um grupo — não se abre aqui
    um segundo leitor do mesmo bloco de config.
    """
    _pos, regra = loadout.regra_do_formato(fmt, regras)
    v = str(regra.get("cartas_partilhadas") or "").strip().lower()
    return v if v in (ROTATIVAS, DEDICADAS) else PARTILHA_OMISSAO


def e_rotativo(fmt: str | None, regras: list[dict] | None = None) -> bool:
    return partilha_do_formato(fmt, regras) == ROTATIVAS


TEXTO_PARTILHA = {
    ROTATIVAS: ("as cartas rodam entre os decks: a que entra em mais do que um "
                "fica de fora, leva proxy, e a verdadeira entra à hora de jogar "
                "— a necessidade do formato é o MÁXIMO"),
    DEDICADAS: ("cada deck tem as suas próprias cartas: a mesma carta em dois "
                "decks pede duas cópias — a necessidade do formato é a SOMA"),
}


# ---------------------------------------------------------------------------
# «Quero montar este» — a marca por deck, no config
# ---------------------------------------------------------------------------
#: `colecao_config.json -> decks_montar`: `{<id do deck>: "<data>"}`.
#:
#: Vive no CONFIG e não na base porque é uma PREFERÊNCIA dele (a mesma razão do
#: `caixas`, do `feira.nao_levo` e do `sugestoes_recusadas`), e porque o config
#: vai no Git — a decisão fica com data e com diff. A posse (`+`/`−`) é o
#: contrário: é um FACTO sobre a estante e vive na base.
CHAVE_MARCAR = "decks_montar"


def marcados(cfg: dict | None = None) -> dict[str, str]:
    cfg = sources.config() if cfg is None else cfg
    v = cfg.get(CHAVE_MARCAR)
    return {str(k): str(x) for k, x in v.items()} if isinstance(v, dict) else {}


def marcar(cfg: dict, deck_id: str, quero: bool, quando: str | None = None) -> dict:
    """Marca (ou desmarca) um deck. Reversível e datado."""
    from datetime import date
    if not deck_id:
        raise ValueError("sem deck")
    m = dict(marcados(cfg))
    if quero:
        m[deck_id] = quando or date.today().isoformat()
    else:
        m.pop(deck_id, None)
    cfg[CHAVE_MARCAR] = dict(sorted(m.items()))
    return cfg[CHAVE_MARCAR]


# ---------------------------------------------------------------------------
# O registo: que decks existem em cada formato
# ---------------------------------------------------------------------------
def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "sem-nome"


def id_da_caixa(slot: str) -> str:
    return f"caixa:{slot}"


def id_meta(fmt: str, nome: str) -> str:
    return f"meta:{fmt}:{_slug(nome)}"


def _link_da_caixa(con, s: dict) -> str:
    """O LINK de um deck, quando a fonte dele é um deck vigiado.

    Ele disse *"ambos tem link"* dos dois de cEDH, e os links existem: estão nas
    `notes`/`key` da tabela `watched`, que é de onde a vigia já traz a lista. Não
    se escreve nenhum à mão nem se vai buscar outro — o que a página mostra é o
    link da MESMA entrada de onde as cartas vieram.
    """
    if (s.get("fonte") or "").lower() != "vigiado" or not s.get("ref"):
        return ""
    r = con.execute("SELECT kind, key, notes FROM watched WHERE label = ?",
                    (s["ref"],)).fetchone()
    if r is None:
        return ""
    if (r["kind"] or "") == "moxfield" and r["key"]:
        return f"https://moxfield.com/decks/{r['key']}"
    m = re.search(r"https?://\S+", r["notes"] or "")
    return m.group(0).rstrip(".,;") if m else ""


def _link_do_escolhido(slot: str) -> str:
    rec = loadout.listas_escolhidas().get(slot) or {}
    m = re.search(r"https?://\S+", str(rec.get("origem") or ""))
    return m.group(0).rstrip(".,;") if m else ""


def decks_das_caixas(con: sqlite3.Connection, cfg: dict | None = None) -> list[dict]:
    """Um deck por CAIXA do config — os decks que são dele.

    A lista de cada caixa vem do `loadout._slot_cards`, que é o DESPACHO único
    de *"de onde vem a lista deste slot"* (deck seguido, vigiado, consenso por
    assinatura, lista escolhida). Reimplementá-lo aqui era abrir uma segunda
    resposta à mesma pergunta — e a segunda discorda da primeira num dia
    qualquer, em silêncio.
    """
    cfg = sources.config() if cfg is None else cfg
    out = []
    for s in caixas.slots(cfg):
        slot = s.get("slot")
        cards, nota = loadout._slot_cards(con, s)              # noqa: SLF001
        link = _link_da_caixa(con, s) or _link_do_escolhido(slot)
        out.append({
            "id": id_da_caixa(slot), "slot": slot,
            "nome": s.get("nome") or slot, "formato": s.get("formato"),
            "fonte": "caixa", "origem": s.get("fonte"), "nota": nota,
            "link": link, "estado": s.get("estado"), "cards": cards,
            "listas": None,
        })
    return out


def _consenso_das_listas(con, fmt: str, ids: list[int]) -> list[tuple[str, str, int]]:
    """A lista de consenso de um conjunto de decklists.

    O MESMO cálculo de todo o vault (`stock.stock_from_lists`), como o
    `loadout._cards_from_consensus` faz: um segundo consenso ao lado discordava
    do resto do site sem um único erro.
    """
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    main: dict[int, dict[str, int]] = defaultdict(dict)
    side: dict[int, dict[str, int]] = defaultdict(dict)
    for r in con.execute(
            f"""SELECT decklist_id i, card_name nm, quantity q, board b
                  FROM decklist_cards WHERE decklist_id IN ({ph})""", ids):
        alvo = side if r["b"] == "side" else main
        alvo[r["i"]][r["nm"].split(" // ")[0]] = r["q"]
    sl = stock.stock_from_lists(fmt, [main[i] for i in ids if main.get(i)],
                                [side[i] for i in ids if side.get(i)])
    return ([("main", c["card_name"], c["quantity"]) for c in sl["main"]]
            + [("side", c["card_name"], c["quantity"]) for c in sl["side"]])


def arquetipos_meta(con: sqlite3.Connection, fmt: str,
                    min_listas: int | None = None,
                    so_contar: bool = False) -> list[dict]:
    """Os arquétipos META do formato, **pelo NOME DA FONTE do mtgtop8**.

    Nunca pela etiqueta do clustering: medido na base de 02/10, são 7 499
    etiquetas com 91 % sem uma única lista, e chamam-se *"Solitary Confinement /
    Argothian Enchantress / Sterling Grove"*. O nome da fonte é o que a página do
    evento escreve ao lado de cada deck, está gravado em
    `decklists.arquetipo_fonte` desde 2026-10-02, e é ESTÁVEL — é por isso que
    serve de identidade a uma marca dele que tem de sobreviver às corridas.

    Que listas contam é o `sources.counting_sql` de sempre (as regras de
    `metagame_fontes`, com a regra própria de cada formato: o cEDH e o Pauper são
    dele).

    **SÃO DUAS PERGUNTAS E DOIS FILTROS, e isso foi medido antes de se escolher.**
    *"Que decks existem no meta"* é o REGISTO e vê **todas** as listas que contam
    (`consenso=False`); *"como é que este deck se joga agora"* é a LISTA e vê a
    JANELA DO CONSENSO de 2026-10-03 (`consenso.desde`, hoje 2026-09-29).
    Juntá-las esvaziava a página: medido na base de 04/10, com a janela aplicada
    ao registo o SPML ficava com **modern 2, standard 0, pioneer 0, legacy 0**
    arquétipos — e a pergunta que ele fez (*"quero que me perguntes para cada
    formato se eu quero montar ou não o deck"*) ficava sem nada para responder. É
    a mesma separação que a reserva da venda já tinha (CLAUDE.md, «A JANELA DO
    CONSENSO»): a janela é sobre o que se joga HOJE, e um registo de arquétipos
    não é uma afirmação sobre hoje.

    Um arquétipo cuja janela não chega ao mínimo fica com a lista das listas
    TODAS e **di-lo** (`fora_da_janela`), nas palavras de sempre
    (`sources.texto_amostra`) — um consenso vazio não é uma resposta.
    """
    minimo = loadout.stock_min_lists() if min_listas is None else min_listas
    # QUEM AGRUPA PELO NOME DA FONTE É O `mtgvault.nomes`, e não este módulo: a
    # coluna `decklists.arquetipo_fonte` tem UM leitor, e há um teste que varre o
    # código à procura de um segundo (`test_nomes_arquetipo.
    # caso_a_pergunta_do_nome_vive_num_sitio_so`). Dois agrupadores ao lado
    # respondem de maneira diferente num dia qualquer, em silêncio.
    sql_t, par_t = sources.counting_sql(fmt, "d", consenso=False)
    sql_j, par_j = sources.counting_sql(fmt, "d")
    todas = nomes.listas_por_nome(con, fmt, sql_t, par_t)
    na_janela = nomes.listas_por_nome(con, fmt, sql_j, par_j)

    if so_contar:
        # Só o NÚMERO (é o `meta_fora` dos formatos dedicados). Construir a
        # lista de consenso dos 56 arquétipos para depois só os contar custava
        # a maior parte dos 15,2 s que a página media a frio.
        return [{"nome": nm, "listas": len(ids)}
                for nm, ids in todas.items() if len(ids) >= minimo]

    out = []
    for nm, ids in todas.items():
        if len(ids) < minimo:
            continue
        jan = na_janela.get(nm) or []
        fora = len(jan) < minimo
        usadas = ids if fora else jan
        nota = f"mtgtop8 · {len(ids)} listas"
        if fora:
            nota += (f" · lista do consenso de todas elas — "
                     f"{sources.texto_amostra(len(jan), minimo, fmt)}")
        else:
            nota += f" · consenso das {len(jan)} na janela"
        out.append({"id": id_meta(fmt, nm), "slot": None, "nome": nm,
                    "formato": fmt, "fonte": "meta", "origem": "mtgtop8",
                    "nota": nota, "link": "", "estado": None,
                    "listas": len(ids), "listas_janela": len(jan),
                    "fora_da_janela": fora,
                    "cards": _consenso_das_listas(con, fmt, usadas)})
    out.sort(key=lambda d: (-(d["listas"] or 0), d["nome"]))
    return out


def formatos(cfg: dict | None = None) -> list[str]:
    """Os formatos que têm decks, pela ordem dos grupos do config (que é a ordem
    da alocação) e depois pelo nome."""
    cfg = sources.config() if cfg is None else cfg
    regras = loadout.regras_por_formato()
    vistos = [s.get("formato") for s in caixas.slots(cfg) if s.get("formato")]
    return sorted(dict.fromkeys(vistos),
                  key=lambda f: (loadout.regra_do_formato(f, regras)[0], f))


def registo(con: sqlite3.Connection, cfg: dict | None = None) -> dict[str, list[dict]]:
    """`formato -> [decks]`: as caixas dele mais, onde faz sentido, o meta.

    **O meta só se OFERECE nos formatos `rotativas`**, e isso é uma decisão minha
    com a razão dele por trás: a pergunta *"queres montar este?"* foi pedida
    **para o Premodern e o SPML** e só lá ela tem resposta — nos outros três ele
    enumerou os decks que tem (*"CDEH, sao 2 decks"*, *"Duel Commander, 1 deck"*)
    e oferecer-lhe doze comandantes de Duel Commander era contradizê-lo. Os
    arquétipos meta dos formatos dedicados CONTAM-SE e dizem-se (está no
    `meta_fora`), para a decisão ficar à vista em vez de escondida.
    """
    cfg = sources.config() if cfg is None else cfg
    por_fmt: dict[str, list[dict]] = defaultdict(list)
    for d in decks_das_caixas(con, cfg):
        por_fmt[d["formato"]].append(d)
    for fmt in list(por_fmt):
        if not e_rotativo(fmt):
            continue
        ja = {(d["nome"] or "").strip().lower() for d in por_fmt[fmt]}
        ja |= {_nome_do_consenso(d).lower() for d in por_fmt[fmt]}
        for m in arquetipos_meta(con, fmt):
            if m["nome"].strip().lower() in ja:
                m = dict(m, ja_e_caixa=True)
            por_fmt[fmt].append(m)
    return dict(por_fmt)


def _nome_do_consenso(d: dict) -> str:
    """O nome que a FONTE dá à lista escolhida de uma caixa, para não oferecer o
    mesmo deck duas vezes (a caixa e o meta). Vazio quando não há."""
    rec = loadout.listas_escolhidas().get(d.get("slot") or "") or {}
    return str(rec.get("arquetipo") or rec.get("label") or "").strip()


# ---------------------------------------------------------------------------
# Quanto é que ele tem de cada deck
# ---------------------------------------------------------------------------
def _cartas_do_deck(d: dict) -> list[tuple[str, str, int]]:
    return d.get("cards") or []


def conta_do_deck(d: dict, pos: dict[str, dict]) -> dict:
    """`{total, tem, pct, main, side}` — o *"tens X de Y — Z %"*.

    Conta CÓPIAS e não nomes, e a posse de cada carta trava no que o deck pede
    (ter 8 Swords não faz um deck que pede 4 ficar a 200 %). O **sideboard conta
    à parte do main** e os dois somam o total: ele tem de o montar à parte, e um
    número que os misture não lhe diz se já pode ir jogar.

    **Não há alocação aqui, de propósito.** Esta página responde *"quanto deste
    deck é que eu tenho"*; quem reparte a colecção entre caixas montadas é o
    `loadout`, e refazer essa conta aqui era abrir uma segunda opinião.
    """
    out = {"main": {"total": 0, "tem": 0}, "side": {"total": 0, "tem": 0}}
    for board, nm, q in _cartas_do_deck(d):
        k = "side" if board == "side" else "main"
        out[k]["total"] += q
        out[k]["tem"] += min(q, pos.get(nm, {}).get("q", 0))
    total = out["main"]["total"] + out["side"]["total"]
    tem = out["main"]["tem"] + out["side"]["tem"]
    return {"total": total, "tem": tem,
            "pct": round(100 * tem / total) if total else 0, **out}


# ---------------------------------------------------------------------------
# A necessidade do formato: a soma E o máximo, sempre as duas
# ---------------------------------------------------------------------------
def necessidade(decks: list[dict], pos: dict[str, dict] | None = None) -> dict:
    """A necessidade das cartas dos decks dados: `{nm: {soma, maximo, decks}}`.

    As duas contas fazem-se SEMPRE. Qual delas vale é a regra do formato, e quem
    mostra mostra as duas — é a diferença entre elas que lhe diz o que a decisão
    custa.
    """
    por_carta: dict[str, dict] = {}
    for d in decks:
        pedido: dict[str, int] = defaultdict(int)
        for _b, nm, q in _cartas_do_deck(d):
            pedido[nm] += q
        for nm, q in pedido.items():
            x = por_carta.setdefault(nm, {"soma": 0, "maximo": 0, "decks": []})
            x["soma"] += q
            x["maximo"] = max(x["maximo"], q)
            x["decks"].append({"id": d["id"], "nome": d["nome"], "q": q})
    if pos is not None:
        for nm, x in por_carta.items():
            x["tenho"] = pos.get(nm, {}).get("q", 0)
            x["origem"] = pos.get(nm, {}).get("origem", marcas.INVENTARIO)
    return por_carta


def faltas(nec: dict, pos: dict[str, dict], modo: str) -> dict[str, int]:
    """O que falta COMPRAR, pela regra do formato: `{nm: quantas}`."""
    chave = "maximo" if modo == ROTATIVAS else "soma"
    out = {}
    for nm, x in nec.items():
        f = x[chave] - pos.get(nm, {}).get("q", 0)
        if f > 0:
            out[nm] = f
    return out


def totais_da_necessidade(nec: dict, pos: dict[str, dict]) -> dict:
    """Os dois totais lado a lado, com as faltas de cada um."""
    def falta(chave):
        return sum(max(0, x[chave] - pos.get(nm, {}).get("q", 0))
                   for nm, x in nec.items())
    return {"soma": sum(x["soma"] for x in nec.values()),
            "maximo": sum(x["maximo"] for x in nec.values()),
            "faltam_a_somar": falta("soma"),
            "faltam_a_rodar": falta("maximo"),
            "cartas": len(nec)}


# ---------------------------------------------------------------------------
# Próprias e partilhadas (só nos formatos rotativos)
# ---------------------------------------------------------------------------
def reparticao(decks: list[dict]) -> dict[str, set[str]]:
    """`nm -> {ids dos decks marcados que a usam}`. É isto que decide própria vs
    partilhada, e muda quando ele marca ou desmarca um deck."""
    out: dict[str, set[str]] = defaultdict(set)
    for d in decks:
        for _b, nm, _q in _cartas_do_deck(d):
            out[nm].add(d["id"])
    return out


def e_partilhada(nm: str, rep: dict[str, set[str]]) -> bool:
    return len(rep.get(nm, ())) >= 2


def proprias_e_partilhadas(d: dict, rep: dict[str, set[str]]) -> dict:
    """As cartas DESTE deck partidas em duas listas, contadas à parte.

    `{proprias: [(board, nm, q)], partilhadas: [...], n_proprias, n_partilhadas,
      com_quem: {nm: [ids]}}`
    """
    pr, pa, com = [], [], {}
    for board, nm, q in _cartas_do_deck(d):
        if e_partilhada(nm, rep):
            pa.append((board, nm, q))
            com[nm] = sorted(rep[nm] - {d["id"]})
        else:
            pr.append((board, nm, q))
    return {"proprias": pr, "partilhadas": pa,
            "n_proprias": sum(q for _b, _n, q in pr),
            "n_partilhadas": sum(q for _b, _n, q in pa),
            "com_quem": com}


def proxies_do_deck(d: dict, rep: dict[str, set[str]]) -> list[dict]:
    """A LISTA DE PROXIES A IMPRIMIR deste deck = exactamente as partilhadas.

    Sai de graça depois do cálculo feito, e é o que ele vai ter na mão: *"vou
    imprimir proxie, e só meto as verdadeiras no deck quando for jogar"*.
    """
    p = proprias_e_partilhadas(d, rep)
    agg: dict[str, int] = defaultdict(int)
    for _b, nm, q in p["partilhadas"]:
        agg[nm] += q
    return [{"nm": nm, "q": q, "com": p["com_quem"].get(nm, [])}
            for nm, q in sorted(agg.items())]


def sleeves_do_formato(decks: list[dict], rep: dict[str, set[str]]) -> dict:
    """Quantas cartas ficam SLEEVADAS no formato, e quantos proxies.

    Nos formatos rotativos o deck fica sleevado com as PRÓPRIAS (verdadeiras) e
    com um proxy por cada partilhada — o `total` é o que ele enfia em sleeves ao
    todo, e as duas metades dizem com o quê.
    """
    reais = proxies = 0
    for d in decks:
        p = proprias_e_partilhadas(d, rep)
        reais += p["n_proprias"]
        proxies += p["n_partilhadas"]
    return {"reais": reais, "proxies": proxies, "total": reais + proxies,
            "decks": len(decks)}


# ---------------------------------------------------------------------------
# O relatório que a página desenha
# ---------------------------------------------------------------------------
def relatorio(con: sqlite3.Connection, cfg: dict | None = None) -> dict:
    """Tudo o que a página precisa, por formato e por deck.

    Os três níveis: `formatos` (o índice), `decks` de cada um (com `tem/total` e
    a marca) e, por deck, as cartas agrupadas por tipo. O que é pesado — as
    cartas — vai numa parte por deck (decisão de 2026-09-15).
    """
    cfg = sources.config() if cfg is None else cfg
    reg = registo(con, cfg)
    mks = marcados(cfg)
    inv = marcas.inventario(con)
    marcadas_ = marcas.marcadas(con)
    pos = marcas.posse(con, inv, marcadas_)

    fmts = []
    por_deck: dict[str, dict] = {}
    for fmt in sorted(reg, key=lambda f: (
            loadout.regra_do_formato(f)[0], f)):
        modo = partilha_do_formato(fmt)
        decks = reg[fmt]
        escolhidos = [d for d in decks if d["id"] in mks]
        rep = reparticao(escolhidos) if modo == ROTATIVAS else {}
        nec = necessidade(escolhidos, pos)
        tot = totais_da_necessidade(nec, pos)
        linhas = []
        for d in decks:
            c = conta_do_deck(d, pos)
            linhas.append({
                "id": d["id"], "nome": d["nome"], "fonte": d["fonte"],
                "origem": d.get("origem"), "nota": d.get("nota") or "",
                "link": d.get("link") or "", "estado": d.get("estado"),
                "listas": d.get("listas"), "ja_e_caixa": d.get("ja_e_caixa", False),
                "quero": d["id"] in mks, "marcado_em": mks.get(d["id"]),
                "tem": c["tem"], "total": c["total"], "pct": c["pct"],
                "main": c["main"], "side": c["side"],
                "sem_lista": not d.get("cards"),
            })
            por_deck[d["id"]] = d
        # «depois de escolher, ordenamos»: a percentagem que ele JÁ tem, maior
        # primeiro — é a resposta a *"qual é o mais barato de fechar"*. Os sem
        # lista vão para o fim (não há nada a ordenar neles).
        linhas.sort(key=lambda r: (r["sem_lista"], -r["pct"], -r["tem"], r["nome"]))
        fmts.append({
            "formato": fmt, "modo": modo, "texto_modo": TEXTO_PARTILHA[modo],
            "decks": linhas, "n_decks": len(linhas),
            "n_marcados": len(escolhidos),
            "meta_fora": (0 if modo == ROTATIVAS
                          else len(arquetipos_meta(con, fmt, so_contar=True))),
            "necessidade": tot,
            "sleeves": (sleeves_do_formato(escolhidos, rep)
                        if modo == ROTATIVAS else None),
        })
    return {"formatos": fmts, "decks": por_deck,
            "marcas": marcas.resumo(con),
            "frase_marcas": marcas.frase(con),
            "pos": pos}


def cache_nova() -> dict:
    """A cache PARTILHADA pelos decks todos de uma passagem.

    Sem ela, cada deck pagava um `paginas.img_map` — e esse começa por varrer a
    colecção INTEIRA para preferir a impressão que ele TEM. Com 83 decks eram 83
    varreduras da `copies` por página: a maior parte dos 15,2 s que a aba media
    a frio a 2026-10-04.
    """
    return {"tl": {}, "img": {}}


def deck_para_pagina(con: sqlite3.Connection, d: dict, pos: dict[str, dict],
                     modo: str, rep: dict[str, set[str]],
                     cmdr: str | None = None, cache: dict | None = None) -> dict:
    """Um deck pronto a desenhar: as cartas por tipo, main e side à parte.

    Cada carta leva o `sid` da impressão (para a imagem), quantas o deck pede,
    quantas ele tem, de onde vem esse número (inventário ou marcado por ele) e,
    nos formatos rotativos, se é própria ou partilhada.
    """
    from . import paginas
    cards = _cartas_do_deck(d)
    nms = [nm for _b, nm, _q in cards]
    if cache is None:
        tl = paginas._meta_cartas(con, nms)                    # noqa: SLF001
        imgs = paginas.img_map(con, nms)
    else:
        faltam = [n for n in dict.fromkeys(nms) if n not in cache["tl"]]
        if faltam:
            cache["tl"].update(paginas._meta_cartas(con, faltam))   # noqa: SLF001
            # O que o catálogo não conhece fica marcado para não voltar a ser
            # pedido deck a deck — senão a cache não poupava nada nesses nomes.
            for n in faltam:
                cache["tl"].setdefault(n, ("", ""))
        faltam = [n for n in dict.fromkeys(nms) if n not in cache["img"]]
        if faltam:
            cache["img"].update(paginas.img_map(con, faltam))
            for n in faltam:
                cache["img"].setdefault(n, "")
        tl = cache["tl"]
        imgs = cache["img"]
    p = proprias_e_partilhadas(d, rep) if modo == ROTATIVAS else None
    partilhadas = {nm for _b, nm, _q in (p["partilhadas"] if p else [])}

    blocos: dict[str, dict[str, list]] = {"main": defaultdict(list),
                                          "side": defaultdict(list)}
    for board, nm, q in cards:
        k = "side" if board == "side" else "main"
        e_cmdr = bool(cmdr) and nm == cmdr and k == "main"
        grupo = tipo_da_carta((tl.get(nm) or ("", ""))[0], comandante=e_cmdr)
        tenho = pos.get(nm, {})
        blocos[k][grupo].append({
            "nm": nm, "q": q, "tenho": tenho.get("q", 0),
            "origem": tenho.get("origem", marcas.INVENTARIO),
            "em": tenho.get("em"),
            "sid": imgs.get(nm) or "",
            "partilhada": nm in partilhadas,
            "com": (p["com_quem"].get(nm, []) if p else []),
        })

    def ordena(b):
        return [{"tipo": t, "q": sum(c["q"] for c in b[t]),
                 "cartas": sorted(b[t], key=lambda c: c["nm"])}
                for t in ordenar_grupos(b)]

    conta = conta_do_deck(d, pos)
    out = {
        "id": d["id"], "nome": d["nome"], "formato": d["formato"],
        "fonte": d["fonte"], "origem": d.get("origem"),
        "nota": d.get("nota") or "", "link": d.get("link") or "",
        "estado": d.get("estado"), "listas": d.get("listas"),
        "comandante": cmdr or "",
        "modo": modo, "texto_modo": TEXTO_PARTILHA[modo],
        "conta": conta,
        "main": ordena(blocos["main"]), "side": ordena(blocos["side"]),
    }
    if p is not None:
        out["reparticao"] = {
            "n_proprias": p["n_proprias"], "n_partilhadas": p["n_partilhadas"],
            "proxies": proxies_do_deck(d, rep),
        }
    return out


def comandante_do_deck(con: sqlite3.Connection, d: dict) -> str | None:
    """Qual das cartas é o COMANDANTE, nos formatos de comandante.

    A base já sabe responder desde 2026-10-01 (`decklists.commander`, lido do
    sideboard da fonte ou derivado pela ordem de inserção) e para um ARQUÉTIPO de
    Duel Commander o nome da fonte É o comandante. Para uma caixa, o nome está no
    config (`caixas[].comandante`) ou vem do consenso por comandante — e nunca se
    adivinha pelas cartas: medido a 2026-10-01, o crivo pela identidade de cor
    deixava 0 ou mais do que um candidato em 409 das 652 listas.
    """
    if d.get("formato") not in FORMATOS_COMANDANTE:
        return None
    nomes_ = {nm for _b, nm, _q in _cartas_do_deck(d)}
    if d["fonte"] == "meta" and d["nome"] in nomes_:
        return d["nome"]
    cfg_slot = next((s for s in caixas.slots()
                     if s.get("slot") == d.get("slot")), {})
    escrito = (cfg_slot.get("comandante") or "").strip()
    if escrito and escrito in nomes_:
        return escrito
    rec = loadout.listas_escolhidas().get(d.get("slot") or "") or {}
    cand = str(rec.get("comandante") or "").strip()
    if cand and cand in nomes_:
        return cand
    return None


def nome_da_fonte(con: sqlite3.Connection, fmt: str, ids) -> dict | None:
    """O nome que a fonte dá a um conjunto de listas — a MESMA votação de todo o
    vault (`nomes.nome_das_listas`), nunca uma segunda contagem ao lado."""
    return nomes.nome_das_listas(con, ids)


def validar_nome(con: sqlite3.Connection, nome: str) -> str | None:
    """O nome oracle desta carta, pelo mesmo leitor do `padrao` (num sítio só)."""
    return padrao.nome_no_catalogo(con, nome)
