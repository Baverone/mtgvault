"""LISTA PADRÃO e RESERVA por caixa (André, 2026-09-20, à letra).

*"quero que olhes também com muita atenção para a lista de Duel-Commander de
Cloud; preciso urgentemente de estabelecer uma lista padrão para completar, e
ver algumas cartas que poderão ser possível entrar; não quero ter que vender
cartas que depois me poderão fazer falta."*

São duas coisas, e as duas vivem no `colecao_config.json` (é uma preferência
dele, vai no Git, e edita-se à mão quando o 8771 não está de pé):

LISTA PADRÃO
------------
Uma caixa com lista padrão tem uma lista FIXA — congelada com a data e a origem
— em vez da que a fonte (`deck`, `vigiado`, `consenso`) recalcula todos os dias.
O Cloud (DC) seguia a lista mais recente do McWinSauce (`my_decks.
FOLLOWED_PLAYER_DECK`): cada vez que ele jogava outra versão, a caixa, a lista
de compras e a alocação mudavam debaixo dos pés. Uma lista padrão não muda até
ele lhe mexer.

**Reutiliza o mecanismo do «vou montar este»** (v5, 2026-09-07): a lista fica em
`listas_escolhidas[slot]` com `padrao: true`, `origem` e `escolhido_em`, e a
caixa passa a `fonte: "escolhido"`, `ref: <slot>`, com o que lá estava em
`_antes` — o motor (`loadout._cards_from_escolhido`) e a página já sabem ler
isto, e o `daily` NUNCA escreve em `listas_escolhidas` (só o `webapp.py` e a
CLI). O «voltar ao consenso» é o mesmo desfazer do «já não vou montar este». A
diferença para o botão do top-N: aqui o nome da caixa não muda (ela já tem
identidade própria) e a lista vem dele, não do clustering.

O que muda por baixo: a alocação, o `missing`, as encomendas, a wantlist e as
percentagens lêem `s["cards"]`, e `s["cards"]` passa a ser a lista padrão. Nada
mais é preciso mexer — é o que torna isto barato.

RESERVA
-------
`caixas[].reserva`: os nomes das cartas *"que poderão entrar"* nessa caixa. As
cópias dessas cartas — cumpram ou não a regra de material da caixa: ele quer
guardá-las de qualquer forma — saem da lista de venda para `guardar`, com o
motivo *"reserva da caixa <nome>"* (`loadout.RAZAO_RESERVA`), e por isso nunca
vão para o CSV de stock nem para a estante (`venda.fora_da_exportacao` já
deixa o `guardar` de fora). A aba da caixa mostra-as num bloco «Reserva (N)»
com onde cada cópia está e se serve a caixa tal como está.

O que a reserva NÃO faz: não aloca, não conta para a percentagem, não compra.
É só *"não vendas isto"*, com o porquê ao lado.
"""
from __future__ import annotations

import re
from datetime import date

from . import caixas

# As chaves da caixa que uma escolha (ou uma lista padrão) substitui, e que o
# desfazer repõe. Vivem aqui porque o `webapp.py` e este módulo fazem o mesmo
# gesto — escritas em dois sítios, bastava acrescentar uma para os dois
# desfazeres discordarem.
CHAVES_DA_ESCOLHA = ("fonte", "ref", "nome", "estado")
BOARDS = ("main", "side")


# ---------------------------------------------------------------------------
# Ler
# ---------------------------------------------------------------------------
def registo(cfg: dict, slot_id: str) -> dict | None:
    """A lista padrão da caixa (o registo em `listas_escolhidas`), ou None."""
    rec = (cfg.get("listas_escolhidas") or {}).get(slot_id)
    return rec if rec and rec.get("padrao") else None


def tem_padrao(cfg: dict, slot_id: str) -> bool:
    return registo(cfg, slot_id) is not None


def _front(nome: str) -> str:
    return nome.split(" // ")[0].strip()


def parse_lista(texto: str) -> list[list]:
    """`N Nome` por linha → `[[board, nome, q], ...]`.

    Aceita o que ele cola de qualquer sítio: linhas em branco, `#` e `//`
    como comentário (o `// Sideboard` do Cardmarket e o `Sideboard` sozinho
    mudam de bloco), `Nx Nome` e `N Nome`. Uma linha sem quantidade vale 1 —
    é o caso normal numa lista de Commander.
    """
    out: list[list] = []
    board = "main"
    for ln in (texto or "").splitlines():
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        if ln.startswith("//"):
            if "side" in ln.lower():
                board = "side"
            continue
        if ln.lower() in ("sideboard", "side", "main", "mainboard", "deck"):
            board = "side" if ln.lower().startswith("side") else "main"
            continue
        m = re.match(r"^(\d+)\s*[xX]?\s+(.+)$", ln)
        if m:
            q, nome = int(m.group(1)), m.group(2).strip()
        else:
            q, nome = 1, ln
        if q <= 0 or not nome:
            continue
        out.append([board, nome, q])
    return juntar(out)


def juntar(cards) -> list[list]:
    """Soma as linhas repetidas (mesmo bloco, mesma carta) e ordena: main
    primeiro, depois por nome — a mesma ordem por que o `resolve_slots` guarda
    a lista da caixa."""
    agg: dict[tuple[str, str], int] = {}
    for b, nome, q in cards:
        b = "side" if b == "side" else "main"
        k = (b, nome)
        agg[k] = agg.get(k, 0) + int(q)
    return [[b, n, q] for (b, n), q in sorted(agg.items(), key=lambda kv: (kv[0][0] != "main",
                                                                             kv[0][1]))
            if q > 0]


def texto(cards) -> str:
    """A lista em texto (`1 Nome`), com `// Sideboard` entre os blocos."""
    main = [f"{q} {n}" for b, n, q in cards if b != "side"]
    side = [f"{q} {n}" for b, n, q in cards if b == "side"]
    return "\n".join(main + (["", "// Sideboard"] + side if side else []))


# ---------------------------------------------------------------------------
# Escrever: a lista padrão
# ---------------------------------------------------------------------------
def fixar(cfg: dict, slot_id: str, cards, origem: str, quando: str | None = None,
          nome: str | None = None) -> dict:
    """Fixa a lista padrão de uma caixa. Devolve o registo escrito.

    `cards` é `[[board, nome, q], ...]` (o que `parse_lista` devolve). O que a
    caixa tinha (`fonte`/`ref`/`nome`/`estado`) fica em `_antes` — só na
    primeira vez: fixar por cima de uma lista padrão já fixada não pode
    esquecer a fonte original, senão o «voltar ao consenso» devolvia a caixa
    a... uma lista padrão.
    """
    cards = juntar(cards)
    if not cards:
        raise ValueError("a lista está vazia — nada para fixar")
    s = caixas.caixa_do_cfg(cfg, slot_id)
    antigo = registo(cfg, slot_id) or {}
    rec = {
        "nome": nome or antigo.get("nome") or s.get("nome") or slot_id,
        "padrao": True,
        "origem": (origem or "").strip() or antigo.get("origem") or "fixada à mão",
        "formato": s.get("formato"),
        "escolhido_em": quando or date.today().isoformat(),
        "cards": cards,
    }
    cfg.setdefault("listas_escolhidas", {})[slot_id] = rec
    # Só as chaves que EXISTIAM (a mesma regra do `escolher_lista`): o desfazer
    # tem de distinguir "estava a null" de "não estava lá".
    if s.get("fonte") != "escolhido" or s.get("ref") != slot_id:
        s.setdefault("_antes", {k: s[k] for k in CHAVES_DA_ESCOLHA if k in s})
    s["fonte"] = "escolhido"
    s["ref"] = slot_id
    # Uma lista fixada é para montar: uma candidata sobe a permanente (a mesma
    # regra do «vou montar este»); uma montada fica montada.
    if caixas.estado_de(s) == caixas.CANDIDATA:
        s["estado"] = caixas.PERMANENTE
    return rec


def acrescentar(cfg: dict, slot_id: str, nome: str, q: int = 1,
                board: str = "main") -> dict:
    """Mete (ou soma) uma carta na lista padrão. Exige que exista uma."""
    rec = registo(cfg, slot_id)
    if rec is None:
        raise ValueError(f"a caixa {slot_id!r} não tem lista padrão — fixa-a primeiro")
    if q <= 0:
        raise ValueError("quantidade tem de ser 1 ou mais")
    board = "side" if board == "side" else "main"
    rec["cards"] = juntar(rec["cards"] + [[board, nome, q]])
    return rec


def tirar(cfg: dict, slot_id: str, nome: str, q: int | None = None,
          board: str | None = None) -> dict:
    """Tira uma carta da lista padrão (toda, ou `q` cópias). Exige que lá esteja."""
    rec = registo(cfg, slot_id)
    if rec is None:
        raise ValueError(f"a caixa {slot_id!r} não tem lista padrão")
    alvo = _front(nome).lower()
    novo, tirou = [], 0
    for b, n, quant in rec["cards"]:
        if _front(n).lower() == alvo and (board is None or b == board):
            take = quant if q is None else min(quant, q - tirou)
            tirou += take
            quant -= take
        if quant > 0:
            novo.append([b, n, quant])
    if not tirou:
        raise ValueError(f"{nome!r} não está na lista padrão de {slot_id!r}")
    if not novo:
        raise ValueError("isso deixava a lista padrão vazia — usa «voltar» para a tirar")
    rec["cards"] = novo
    return rec


def voltar(cfg: dict, slot_id: str) -> str:
    """«Voltar ao consenso»: tira a lista padrão e repõe a fonte que a caixa
    tinha (o `_antes`). É o mesmo desfazer do «já não vou montar este»."""
    s = caixas.caixa_do_cfg(cfg, slot_id)
    if registo(cfg, slot_id) is None:
        raise ValueError(f"a caixa {slot_id!r} não tem lista padrão para desfazer")
    antes = s.pop("_antes", None)
    cfg["listas_escolhidas"].pop(slot_id, None)
    if not cfg.get("listas_escolhidas"):
        cfg.pop("listas_escolhidas", None)
    if antes is not None:
        for k in CHAVES_DA_ESCOLHA:
            if k in antes:
                s[k] = antes[k]
            else:
                s.pop(k, None)
    return f'{s.get("nome") or slot_id}: lista padrão desfeita — volta à fonte {s.get("fonte")!r}'


# ---------------------------------------------------------------------------
# Escrever: a reserva
# ---------------------------------------------------------------------------
def reserva(cfg: dict, slot_id: str) -> list[str]:
    s = caixas.caixa_do_cfg(cfg, slot_id)
    return [str(n) for n in (s.get("reserva") or [])]


def reserva_add(cfg: dict, slot_id: str, nome: str) -> list[str]:
    s = caixas.caixa_do_cfg(cfg, slot_id)
    nome = _front(nome)
    if not nome:
        raise ValueError("sem nome de carta")
    lista = [str(n) for n in (s.get("reserva") or [])]
    if any(_front(n).lower() == nome.lower() for n in lista):
        raise ValueError(f"{nome!r} já está na reserva de {s.get('nome') or slot_id}")
    lista.append(nome)
    s["reserva"] = sorted(lista, key=str.lower)
    return s["reserva"]


def reserva_tirar(cfg: dict, slot_id: str, nome: str) -> list[str]:
    s = caixas.caixa_do_cfg(cfg, slot_id)
    alvo = _front(nome).lower()
    lista = [str(n) for n in (s.get("reserva") or [])]
    novo = [n for n in lista if _front(n).lower() != alvo]
    if len(novo) == len(lista):
        raise ValueError(f"{nome!r} não está na reserva de {s.get('nome') or slot_id}")
    if novo:
        s["reserva"] = novo
    else:
        s.pop("reserva", None)
    return novo


# ---------------------------------------------------------------------------
# O catálogo
# ---------------------------------------------------------------------------
def nome_no_catalogo(con, nome: str) -> str | None:
    """O nome ORACLE (a frente, em inglês) desta carta, ou None se o catálogo
    não a conhece. Tenta `name = ?` primeiro (usa o `ix_cards_name`; o
    `lower()` varre as ~500 mil impressões — é o recurso, não a regra)."""
    nome = (nome or "").strip()
    if not nome:
        return None
    for sql, arg in (("name = ?", nome), ("name LIKE ?", nome + " // %"),
                     ("lower(name) = lower(?)", nome),
                     ("lower(name) LIKE lower(?)", nome + " // %")):
        r = con.execute(f"SELECT name FROM cards WHERE {sql} LIMIT 1", (arg,)).fetchone()
        if r is not None:
            return _front(r[0])
    return None


def validar_lista(con, cards) -> list[str]:
    """Os nomes de `cards` que o catálogo não conhece (vazio = todos ok)."""
    return [n for _b, n, _q in cards if nome_no_catalogo(con, n) is None]
