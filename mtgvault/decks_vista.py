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

from . import (caixas, eventos, loadout, marcas, nomes, padrao, scryfall,
               sources, stock, versoes)

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

#: O rótulo de um deck cuja lista é um CONSENSO e não uma lista que alguém jogou.
#: André, 2026-10-04 ao fim do dia: *"as outras quero que esquecas as decklists e
#: vamos focar nas decklists baseadas em eventos reais"*. O consenso continua a
#: existir — mede o metagame, dá os nomes, alimenta a reserva da venda — e por
#: isso o meta fica para CONSULTA; o que não pode é ter a mesma cara de uma lista
#: real na página por onde ele vai sleevar.
TEXTO_CONSENSO = "consenso de várias listas — ninguém jogou esta lista assim"


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


def id_deck(fmt: str, slug: str) -> str:
    """O id de um DECK DELE que não é caixa (2026-10-04, ao fim do dia).

    São os decks que ele nomeou em Modern e Pioneer: não têm deckbox (não são
    `caixa:`) e já não são o meta (não são `meta:`), porque a lista deles está
    FIXADA numa lista de evento real e o nome é o DELE.

    **A identidade é o slug escrito no config, nunca o `archetype_id` nem o nome
    da fonte.** Os dois mudam: o cluster é refeito a cada corrida do
    `rebuild_archetypes` (medido a 02/10: 7 499 etiquetas, 91 % sem uma única
    lista) e três dos dez decks que ele escolheu **não têm nome da fonte
    nenhum** — o `arquetipo_fonte` daquelas listas está a NULL, por isso nunca
    apareceriam no `arquetipos_meta`. Uma marca dele tem de sobreviver às
    corridas; o `archetype_id` fica guardado ao lado como a PISTA de onde a
    escolha veio, não como identidade.
    """
    return f"deck:{fmt}:{_slug(slug)}"


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


def sem_lista_porque(s: dict) -> tuple[str, str]:
    """`(tipo, rótulo)` para uma caixa que não tem lista. `("", "")` se tem.

    São TRÊS situações diferentes, e misturá-las era o defeito (2026-10-04 ao fim
    do dia): a `Modern — Affinity`, que ele mandou DESACTIVAR nesse dia, aparecia
    na lista de Modern como um deck de 0 % ao lado dos que ele vai montar, com o
    estado `candidata` — que é um estado normal da escala e não quer dizer
    «desactivada».

    - **desactivada**: uma caixa de `fonte: consenso` **sem `assinatura`** não tem
      como ter lista, hoje nem nunca — é exactamente o gesto do «já não vou montar
      este» (o que ela tinha fica em `caixas[].\\_antes`, que o motor não vê). Não
      se esconde da lista: ele tem lá o `_antes` para a repor, e uma caixa que
      desaparecesse da página deixava-o sem por onde a reaver.
    - **por escolher**: nunca teve lista e ainda não tem fonte — a
      `legacy-artifacts-blue`, que espera a carta-assinatura dele.
    - o resto fica com a nota que o `loadout._slot_cards` já dá (amostra
      insuficiente, deck sem snapshot, …), que é uma resposta e não um buraco.
    """
    fonte = (s.get("fonte") or "").lower()
    if fonte == "consenso" and not (s.get("assinatura") or []):
        return "desactivada", "desactivada — sem carta-assinatura"
    if not s.get("ref") and fonte != "consenso":
        return "por_escolher", "por escolher — ainda sem lista"
    return "", ""


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
        tipo, rotulo = sem_lista_porque(s)
        d = {
            "id": id_da_caixa(slot), "slot": slot,
            "nome": s.get("nome") or slot, "formato": s.get("formato"),
            "fonte": "caixa", "origem": s.get("fonte"), "nota": nota,
            "link": link, "estado": s.get("estado"), "cards": cards,
            "listas": None,
            "desactivada": tipo == "desactivada", "rotulo_estado": rotulo,
        }
        # Uma caixa que AINDA mostre consenso di-lo. Hoje são a `standard` e as
        # duas de `legacy`, que ele mandou deixar como estavam («esquecemos
        # legacy para já», «Standard não preciso preocupar-me até Janeiro») — e
        # as três estão sem amostra, por isso não mostram lista nenhuma. No dia
        # em que tiverem, a página tem de dizer que é uma média.
        if (s.get("fonte") or "").lower() == "consenso" and cards:
            d["e_consenso"] = True
            d["rotulo_estado"] = rotulo or TEXTO_CONSENSO
        out.append(_com_proveniencia(d, cfg, slot))
    return out


def _com_proveniencia(d: dict, cfg: dict, chave: str) -> dict:
    """Mete no deck a PROVENIÊNCIA da lista de evento, quando ela existe.

    *"Na página de cada deck fica SEMPRE, à vista: jogador, evento, data, número
    de jogadores, classificação e o URL da fonte"* (André, 2026-10-04 ao fim do
    dia) — ele vai sleevar a partir disto e tem de poder ver de onde veio.

    Sai do registo gravado (`listas_escolhidas[<chave>].evento`) e **nunca de uma
    consulta à base**: o `prune_decklists(30)` apaga as decklists ao fim de um
    mês e a página tem de continuar a dizer de onde a lista veio.
    """
    rec = eventos.registo_de_evento(cfg, chave) or {}
    if not rec:
        return d
    d["evento"] = rec.get("evento")
    d["link"] = d.get("link") or (rec["evento"] or {}).get("url") or ""
    for k in ("alternativa", "porque", "escolhida_por", "regra_diria",
              "amostra_fina"):
        if rec.get(k):
            d[k] = rec[k]
    return d


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
        alvo[r["i"]][scryfall.chave(r["nm"])] = r["q"]
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
                    # UM CONSENSO DIZ QUE É UM CONSENSO (2026-10-04, ao fim do
                    # dia). Ele acabou com o consenso como lista de DECK — *"uma
                    # media de muitas listas: ninguem jogou aquele deck"* —, e o
                    # meta fica só para CONSULTA. Sem esta marca a página
                    # desenhava a média com a mesma cara de uma lista que alguém
                    # jogou, que é exactamente o que ele mandou acabar.
                    "e_consenso": True,
                    "rotulo_estado": TEXTO_CONSENSO,
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
    # OS DECKS DELE QUE NÃO SÃO CAIXA (2026-10-04, ao fim do dia): os dez de
    # Modern e o de Pioneer que ele nomeou. Entram ANTES do meta, para o meta se
    # poder reconhecer neles (`ja_e_caixa`) e não oferecer o mesmo deck duas vezes.
    for d in decks_de_evento(con, cfg):
        por_fmt[d["formato"]].append(d)
    # AS VERSÕES QUE TÊM LISTA PRÓPRIA (2026-10-04, à noite). Uma versão cuja
    # lista já vive noutro deck aponta para lá (`deck`) e não se duplica; as
    # outras têm a lista de evento em `listas_escolhidas[<id da versão>]` e são
    # um deck por direito, para a página poder mostrar as cartas e o `tem/total`.
    ja_ha = {d["id"] for ds in por_fmt.values() for d in ds}
    for d in decks_de_versoes(con, cfg):
        if d["id"] not in ja_ha:
            por_fmt[d["formato"]].append(d)
    for fmt in list(por_fmt):
        if not e_rotativo(fmt):
            continue
        ja = {(d["nome"] or "").strip().lower() for d in por_fmt[fmt]}
        ja |= {_nome_do_consenso(d).lower() for d in por_fmt[fmt]}
        ja |= {str(d.get("arquetipo_fonte") or "").strip().lower()
               for d in por_fmt[fmt]}
        ja.discard("")
        for m in arquetipos_meta(con, fmt):
            if m["nome"].strip().lower() in ja:
                m = dict(m, ja_e_caixa=True)
            por_fmt[fmt].append(m)
    # QUEM SAIU DA ESCOLHA CONTINUA AQUI (2026-10-04, à noite). O modelo de um
    # deck por formato deixou nove decks de Modern e o UR Aggro de Pioneer fora
    # da escolha — e **nada se apaga**: ficam no registo, consultáveis, com a
    # lista e a proveniência, marcados `saiu`. Tirá-los daqui era perdê-los sem
    # ninguém decidir isso.
    for fmt in por_fmt:
        for i, d in enumerate(por_fmt[fmt]):
            s = versoes.saiu(d["id"], cfg)
            if s:
                por_fmt[fmt][i] = dict(d, saiu=s,
                                       rotulo_estado=versoes.TEXTO_SAIU)
    return dict(por_fmt)


def decks_de_evento(con: sqlite3.Connection,
                    cfg: dict | None = None) -> list[dict]:
    """Os decks DELE que não são caixa — `colecao_config.json -> decks_de_evento`.

    *"as listas especificas e que quero fixas"* (André, 2026-10-04, ao fim do
    dia). São os dez de Modern e o de Pioneer que ele nomeou: não têm deckbox e a
    lista deles está FIXADA numa lista de evento real, gravada em
    `listas_escolhidas[<id>]` com a proveniência.

    **Porque é que não são arquétipos meta:** o meta agrupa pelo NOME DA FONTE
    (`decklists.arquetipo_fonte`) e **três dos dez não têm nome nenhum** — o
    `arquetipo_fonte` daquelas listas está a NULL, por isso o UR Prowess, o
    Goryo's Reanimator e o Hammer Time nunca apareciam lá. E em quatro outros o
    nome que ele usa não é o da fonte (ele diz *"Boros Energy"*, a fonte diz
    *"Boros Aggro"*). O nome é o DELE.
    """
    cfg = sources.config() if cfg is None else cfg
    v = cfg.get("decks_de_evento")
    out = []
    for n in (v if isinstance(v, list) else []):
        chave = n.get("id") or id_deck(n.get("formato") or "", n.get("slug") or "")
        rec = (cfg.get("listas_escolhidas") or {}).get(chave) or {}
        cards = [(("side" if b == "side" else "main"), scryfall.chave(c), int(q))
                 for b, c, q in (rec.get("cards") or [])]
        d = {
            "id": chave, "slot": None,
            "nome": n.get("nome") or chave, "formato": n.get("formato"),
            "fonte": "dele", "origem": "evento",
            "nota": _nota_do_evento(rec),
            "link": (rec.get("evento") or {}).get("url") or "",
            "estado": None, "cards": cards, "listas": None,
            "arquetipo_id": n.get("arquetipo_id"),
            "arquetipo_fonte": n.get("arquetipo_fonte"),
            "desactivada": False, "rotulo_estado": "",
        }
        if n.get("por_confirmar"):
            d["por_confirmar"] = True
            d["carta_chave"] = n.get("carta_chave")
            d["rotulo_estado"] = "à espera do teu OK"
        if n.get("amostra_fina"):
            d["amostra_fina"] = n["amostra_fina"]
        out.append(_com_proveniencia(d, cfg, chave))
    return out


def decks_de_versoes(con: sqlite3.Connection,
                     cfg: dict | None = None) -> list[dict]:
    """As versões cuja lista NÃO vive já noutro deck, como decks do registo.

    A lista é uma lista de evento REAL, fixada em `listas_escolhidas[<id>]` pelo
    `eventos.fixar` — a mesma mecânica dos `decks_de_evento`, e pela mesma razão
    de 2026-10-04 ao fim do dia: *"vamos focar nas decklists baseadas em eventos
    reais"*. Não é o consenso do cluster: isso era ressuscitar a média que ele
    acabava de enterrar.
    """
    cfg = sources.config() if cfg is None else cfg
    out = []
    for fmt in versoes.formatos(cfg):
        nome_fmt = (versoes.do_formato(fmt, cfg) or {}).get("nome") or fmt
        for v in versoes.versoes(fmt, cfg):
            chave = versoes.deck_da_versao(v)
            if chave != v.get("id"):
                continue                      # a lista vive noutro deck
            rec = (cfg.get("listas_escolhidas") or {}).get(chave) or {}
            cards = [(("side" if b == "side" else "main"), scryfall.chave(c), int(q))
                     for b, c, q in (rec.get("cards") or [])]
            d = {
                "id": chave, "slot": None,
                "nome": f"{nome_fmt} · {v.get('nome') or chave}",
                "formato": fmt, "fonte": "versao", "origem": "evento",
                "nota": _nota_do_evento(rec),
                "link": (rec.get("evento") or {}).get("url") or "",
                "estado": None, "cards": cards, "listas": v.get("listas"),
                "arquetipo_id": v.get("arquetipo_id"),
                "desactivada": False, "rotulo_estado": "",
                "versao_de": fmt,
            }
            out.append(_com_proveniencia(d, cfg, chave))
    return out


def _nota_do_evento(rec: dict) -> str:
    """A nota de um deck com lista de evento: quem a jogou e onde, numa linha."""
    prov = rec.get("evento") or {}
    if not prov:
        return "sem lista de evento fixada"
    return "lista de evento real · " + eventos.texto_prov(prov)


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


def conta_do_deck(d: dict, pos: dict[str, dict],
                  desc: dict[str, bool] | None = None) -> dict:
    """`{total, tem, pct, main, side}` — o *"tens X de Y — Z %"*.

    Conta CÓPIAS e não nomes, e a posse de cada carta trava no que o deck pede
    (ter 8 Swords não faz um deck que pede 4 ficar a 200 %). O **sideboard conta
    à parte do main** e os dois somam o total: ele tem de o montar à parte, e um
    número que os misture não lhe diz se já pode ir jogar.

    **Não há alocação aqui, de propósito.** Esta página responde *"quanto deste
    deck é que eu tenho"*; quem reparte a colecção entre caixas montadas é o
    `loadout`, e refazer essa conta aqui era abrir uma segunda opinião.

    O `desc` (`nome -> é desconhecida`) conta à parte, em `desconhecidas`: uma
    carta que o catálogo não conhece **continua a contar no total** (o deck
    pede-a) e nunca entra em `tem`, mas o número tem de dizer quantas são, senão
    o *"faltam-te 13"* mistura cartas a comprar com nomes que não existem.
    """
    out = {"main": {"total": 0, "tem": 0}, "side": {"total": 0, "tem": 0}}
    desc = desc or {}
    ndesc = 0
    for board, nm, q in _cartas_do_deck(d):
        k = "side" if board == "side" else "main"
        out[k]["total"] += q
        out[k]["tem"] += min(q, pos.get(nm, {}).get("q", 0))
        if desc.get(nm):
            ndesc += q
    total = out["main"]["total"] + out["side"]["total"]
    tem = out["main"]["tem"] + out["side"]["tem"]
    return {"total": total, "tem": tem, "desconhecidas": ndesc,
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


def staples_do_formato(decks: list[dict], rep: dict[str, set[str]],
                       pos: dict[str, dict] | None = None) -> list[dict]:
    """AS CARTAS QUE ENTRAM EM 2+ DECKS MARCADOS, agregadas e por nome.

    É a resposta a *"guardar as que sao staples"* (André, 2026-10-04 ao fim do
    dia) — e não é uma conta nova: é o MESMO `rep` que decide própria vs
    partilhada em cada deck (`proprias_e_partilhadas`), visto pelo formato em vez
    de deck a deck. Deck a deck ele já as via; o que lhe faltava era a lista
    agregada, que é a pilha que vai guardar à parte e de que imprime os proxies.

    `precisa` é o MÁXIMO entre os decks e não a soma: num formato rotativo uma
    cópia serve todos — é essa a regra do formato (`cartas_partilhadas`).
    """
    por_nome: dict[str, dict] = {}
    for d in decks:
        pedido: dict[str, int] = defaultdict(int)
        for _b, nm, q in _cartas_do_deck(d):
            pedido[nm] += q
        for nm, q in pedido.items():
            if not e_partilhada(nm, rep):
                continue
            x = por_nome.setdefault(nm, {"nm": nm, "precisa": 0, "decks": []})
            x["precisa"] = max(x["precisa"], q)
            x["decks"].append({"id": d["id"], "nome": d["nome"], "q": q})
    out = list(por_nome.values())
    for x in out:
        x["n_decks"] = len(x["decks"])
        if pos is not None:
            x["tenho"] = pos.get(x["nm"], {}).get("q", 0)
            x["falta"] = max(0, x["precisa"] - x["tenho"])
    # Em mais decks primeiro: é a que mais vale a pena ter sleevada à parte.
    out.sort(key=lambda x: (-x["n_decks"], -x["precisa"], x["nm"]))
    return out


def sleeves_do_formato(decks: list[dict], rep: dict[str, set[str]]) -> dict:
    """Quantas cartas ficam SLEEVADAS no formato, e quantos proxies.

    Nos formatos rotativos o deck fica sleevado com as PRÓPRIAS (verdadeiras) e
    com um proxy por cada partilhada — o `total` é o que ele enfia em sleeves ao
    todo, e as duas metades dizem com o quê.
    """
    reais = copias = imprimir = 0
    nomes_proxy: set[str] = set()
    for d in decks:
        p = proprias_e_partilhadas(d, rep)
        reais += p["n_proprias"]
        copias += p["n_partilhadas"]
        deste = {nm for _b, nm, _q in p["partilhadas"]}
        # UM PROXY POR CARTA DIFERENTE, EM CADA DECK — e este número é o DELE.
        # Medido a 2026-10-04 contra a conta que ele trouxe da mesa: por
        # aparições dá 147 em Modern e 69 em Premodern, contra os 149 e 63 que
        # ele mediu; por CÓPIAS dava 334 e 201. Ou seja ele imprime um proxy por
        # carta diferente (serve de marcador de *"esta vem da pilha"*) e não
        # quatro proxies de um playset. A pergunta que o número responde é
        # *"quantos proxies imprimo"*, e a resposta é esta; as cópias ficam ao
        # lado porque são o que de facto sai dos decks.
        imprimir += len(deste)
        nomes_proxy.update(deste)
    return {"reais": reais, "proxies": imprimir, "proxies_copias": copias,
            "total": reais + copias, "proxies_nomes": len(nomes_proxy),
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
        # QUEM CONTA COMO «ESCOLHIDO» NESTE FORMATO.
        #
        # Nos formatos do modelo de versões (2026-10-04, à noite) é a **versão
        # escolhida e só ela** — ele sleeva UMA. As outras versões continuam
        # PROTEGIDAS da venda (a regra RE do `fases` guarda todas: são opções do
        # mesmo deck, e vendê-las por ele ter hoje a versão B escolhida era
        # desfazer a opção), mas não entram na necessidade nem nas compras: isso
        # é quanto ele tem de comprar para montar, e ele monta uma.
        #
        # Nos outros formatos é o que ele marcou à mão, como desde 04/10 à tarde.
        unico = versoes.do_formato(fmt, cfg)
        if unico:
            dos = set(versoes.decks_das_versoes(fmt, cfg))
            vd = versoes.deck_da_versao(versoes.versao(fmt, cfg=cfg) or {})
            escolhidos = [d for d in decks if d["id"] == vd]
        else:
            dos = set()
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
                # Num formato do modelo quem decide é a VERSÃO ESCOLHIDA — UMA —
                # e não a marca à mão: duas respostas a *"vou montar este?"* no
                # mesmo ecrã era o defeito que o modelo veio fechar. As outras
                # versões dizem-no pelo `e_versao` (e continuam protegidas da
                # venda), mas ele monta uma.
                "quero": (d["id"] == vd if unico else d["id"] in mks),
                "marcado_em": mks.get(d["id"]),
                "e_versao": d["id"] in dos,
                "saiu": d.get("saiu"),
                "tem": c["tem"], "total": c["total"], "pct": c["pct"],
                "main": c["main"], "side": c["side"],
                "sem_lista": not d.get("cards"),
                "desactivada": d.get("desactivada", False),
                "rotulo_estado": d.get("rotulo_estado") or "",
                # A PROVENIÊNCIA vai no índice e não só na parte do deck: é o que
                # ele lê ANTES de abrir um deck para decidir por onde começa, e
                # pô-la só lá dentro obrigava-o a abrir os onze para comparar.
                "evento": d.get("evento"),
                "alternativa": d.get("alternativa"),
                "porque": d.get("porque") or "",
                "escolhida_por": d.get("escolhida_por") or "",
                "e_consenso": d.get("e_consenso", False),
                "por_confirmar": d.get("por_confirmar", False),
                "carta_chave": d.get("carta_chave") or "",
                "amostra_fina": d.get("amostra_fina") or "",
                "arquetipo_fonte": d.get("arquetipo_fonte") or "",
            })
            por_deck[d["id"]] = d
        # «depois de escolher, ordenamos»: a percentagem que ele JÁ tem, maior
        # primeiro — é a resposta a *"qual é o mais barato de fechar"*. Os sem
        # lista vão para o fim (não há nada a ordenar neles), e as DESACTIVADAS
        # depois deles: são decisões tomadas, não trabalho por fazer.
        linhas.sort(key=lambda r: (r["desactivada"], r["sem_lista"],
                                   -r["pct"], -r["tem"], r["nome"]))
        n_desact = sum(1 for r in linhas if r["desactivada"])
        fmts.append({
            "formato": fmt, "modo": modo, "texto_modo": TEXTO_PARTILHA[modo],
            # `n_decks` conta os que CONTAM: uma caixa desactivada não é um deck
            # deste formato, e somá-la fazia o cartão dizer «21 decks» a quem tem
            # 20 para escolher.
            "decks": linhas, "n_decks": len(linhas) - n_desact,
            "n_desactivadas": n_desact,
            "n_marcados": len(escolhidos),
            # QUEM CONTA COMO ESCOLHIDO, DITO UMA VEZ. O `decks.dados`
            # recalculava-o das marcas à mão (`decks_montar`) e, num formato do
            # modelo de versões, isso dava-lhe OUTRA resposta — a repartição das
            # próprias/partilhadas da página saía dos dez decks antigos enquanto
            # o cabeçalho já falava de uma versão. É o defeito do `event_tier`:
            # dois contadores ao lado, nenhum erro, e a página a discordar de si
            # própria. Agora há uma lista só, e ela sai daqui.
            "ids_escolhidos": [d["id"] for d in escolhidos],
            "meta_fora": (0 if modo == ROTATIVAS
                          else len(arquetipos_meta(con, fmt, so_contar=True))),
            "necessidade": tot,
            "sleeves": (sleeves_do_formato(escolhidos, rep)
                        if modo == ROTATIVAS else None),
            # AS STAPLES do formato (as partilhadas, agregadas). Só nos rotativos
            # e só depois de ele marcar: sem decks marcados não há partilha
            # nenhuma, e uma lista vazia com título era prometer o que não há.
            "staples": (staples_do_formato(escolhidos, rep, pos)
                        if modo == ROTATIVAS and escolhidos else []),
            # UM DECK POR FORMATO, COM VERSÕES (2026-10-04, à noite). `None`
            # nos formatos que ele não mexeu — o Premodern fica com os seus
            # seis decks e com a pergunta «queres montar este?» de sempre.
            "deck_unico": deck_unico(con, fmt, decks, pos, cfg),
        })
    return {"formatos": fmts, "decks": por_deck,
            "marcas": marcas.resumo(con),
            "frase_marcas": marcas.frase(con),
            "pos": pos}


def deck_unico(con: sqlite3.Connection, fmt: str, decks: list[dict],
               pos: dict[str, dict], cfg: dict | None = None) -> dict | None:
    """O deck ÚNICO deste formato com as versões por dentro, ou `None`.

    `None` quer dizer *"este formato fica como estava"* — o Premodern, que ele
    não mexeu, e todos os que não nomeou.

    Cada versão traz o que ele já tem dela (`tem`/`total`/`pct`), para a escolha
    ser informada: a pergunta a seguir à de qual versão jogar é sempre *"e qual
    é a que estou mais perto de fechar"*.
    """
    cfg = sources.config() if cfg is None else cfg
    d = versoes.do_formato(fmt, cfg)
    if not d:
        return None
    por_id = {x["id"]: x for x in decks}
    esc = versoes.versao_escolhida(fmt, cfg)
    vs = []
    for v in versoes.versoes(fmt, cfg):
        did = versoes.deck_da_versao(v)
        alvo = por_id.get(did) or {}
        c = conta_do_deck(alvo, pos) if alvo else {"tem": 0, "total": 0, "pct": 0}
        vs.append({
            "id": v.get("id"), "nome": v.get("nome") or v.get("id"),
            "arquetipo_id": v.get("arquetipo_id"), "listas": v.get("listas"),
            "deck": did, "escolhida": v.get("id") == esc,
            "tem": c["tem"], "total": c["total"], "pct": c["pct"],
            "sem_lista": not (alvo.get("cards") if alvo else None),
            "nota": (alvo.get("nota") or "") if alvo else "",
            "evento": alvo.get("evento") if alvo else None,
        })
    # MONTAR vs PROTEGER (2026-10-05). São duas perguntas e a página tem de as
    # separar: se as juntar, ou ele monta decks que não quer, ou vende cartas
    # que quer. `versoes` é o que ele MONTA; `protege` é o critério inclusivo.
    prot = None
    if versoes.protege_todas(fmt, cfg):
        prot = (versoes.listas_do_formato(con, cfg) or {}).get(fmt)
    return {
        "formato": fmt, "nome": d.get("nome") or fmt,
        "porque": d.get("porque") or "", "em": d.get("em") or "",
        "nota": d.get("_nota") or "",
        "por_decidir": bool(d.get("por_decidir")),
        "versao": esc, "versoes": vs,
        "carta_chave": versoes.carta_chave(fmt, cfg),
        "protege": prot, "limiar": versoes.limiar_listas(cfg),
        "outros": versoes.outros_que_jogam(con, fmt, cfg),
        "saidos": [{"id": i, **s} for i, s in sorted(versoes.saidos(cfg).items())
                   if (por_id.get(i) or {}).get("formato") == fmt],
    }


def cache_nova() -> dict:
    """A cache PARTILHADA pelos decks todos de uma passagem.

    Sem ela, cada deck pagava um `paginas.img_map` — e esse começa por varrer a
    colecção INTEIRA para preferir a impressão que ele TEM. Com 83 decks eram 83
    varreduras da `copies` por página: a maior parte dos 15,2 s que a aba media
    a frio a 2026-10-04.
    """
    return {"tl": {}, "img": {}, "desc": {}}


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
    # AS DESCONHECIDAS, À VISTA (2026-10-04). Uma carta que o catálogo não
    # conhece não pode passar por *"não tenho"*: assim ia para a lista de
    # compras ao lado de cartas a sério, e um nome que não casa é um PROBLEMA, e
    # dito. Hoje é uma nos decks dele — a `Ademi of the Silkchutes` do Cloud —, e
    # nem o catálogo nem a própria Scryfall a têm (sondado a 04/10: 404).
    if cache is None:
        tl = paginas._meta_cartas(con, nms)                    # noqa: SLF001
        imgs = paginas.img_map(con, nms)
        desc = {n: a is None
                for n, a in scryfall.resolver_muitos(con, nms).items()}
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
        faltam = [n for n in dict.fromkeys(nms) if n not in cache["desc"]]
        if faltam:
            cache["desc"].update(
                {n: a is None
                 for n, a in scryfall.resolver_muitos(con, faltam).items()})
        tl = cache["tl"]
        imgs = cache["img"]
        desc = cache["desc"]
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
            "desconhecida": bool(desc.get(nm)),
        })

    def ordena(b):
        return [{"tipo": t, "q": sum(c["q"] for c in b[t]),
                 "cartas": sorted(b[t], key=lambda c: c["nm"])}
                for t in ordenar_grupos(b)]

    conta = conta_do_deck(d, pos, desc)
    out = {
        "id": d["id"], "nome": d["nome"], "formato": d["formato"],
        "fonte": d["fonte"], "origem": d.get("origem"),
        "nota": d.get("nota") or "", "link": d.get("link") or "",
        "estado": d.get("estado"), "listas": d.get("listas"),
        "comandante": cmdr or "",
        "modo": modo, "texto_modo": TEXTO_PARTILHA[modo],
        "conta": conta,
        "main": ordena(blocos["main"]), "side": ordena(blocos["side"]),
        # A FICHA DA LISTA — *"na página de cada deck fica SEMPRE, à vista:
        # jogador, evento, data, número de jogadores, classificação e o URL da
        # fonte"* (André, 2026-10-04 ao fim do dia).
        "evento": d.get("evento"),
        "alternativa": d.get("alternativa"),
        "porque": d.get("porque") or "",
        "escolhida_por": d.get("escolhida_por") or "",
        "e_consenso": d.get("e_consenso", False),
        "por_confirmar": d.get("por_confirmar", False),
        "carta_chave": d.get("carta_chave") or "",
        "amostra_fina": d.get("amostra_fina") or "",
        "arquetipo_fonte": d.get("arquetipo_fonte") or "",
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
