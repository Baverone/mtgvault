"""A POSSE QUE ELE MARCA À MÃO: o `+` e o `−` de cada carta (André, 2026-10-04).

*"fazes a imagem de cada carta, com + e - para eu marcar se tenho a carta"*.

Substitui, para a pergunta *"tenho esta carta?"*, a campanha das fotos de
2026-10-02 (*"se não tiver foto, não tem carta"*), que ele desligou no mesmo dia
em que a mandou: a precisão da foto servia para VENDER, e para MONTAR decks o
gesto certo é um toque no telemóvel à frente da estante.

**O INVENTÁRIO PRÉ-PREENCHE AS MARCAS, E NÃO SE ESCREVEM 737 LINHAS PARA ISSO.**
Ele tem 737 linhas na `copies` e 1 678 cartas já registadas; pô-lo a marcar tudo
de novo a partir do zero era deitar fora meses de trabalho dele. Por isso a
tabela `posse_marcada` nasce VAZIA e guarda só o que ele TOCOU: quem não tem
linha responde com a contagem da colecção. Daí saem os **dois estados**, que
nunca se confundem no ecrã:

  - **`inventario`** — *"vem do inventário"*: ninguém tocou nesta carta; o número
    é o que a `copies` diz (`paginas.posse_total`, a contagem única de sempre).
  - **`marcado`** — *"marcaste tu"*, com a data: há linha na `posse_marcada`, e
    **ela ganha**, esteja acima ou abaixo do inventário.

A marca é **absoluta** e não um delta guardado em cima do inventário, de
propósito: uma cópia nova que entre por foto ou por CSV não pode mexer num número
que ele já confirmou com a carta na mão.

**AS ESCRITAS SÃO DELTAS COM `request_id`**, copiado do riftvault
(`riftvault/collection.py`, `adjust`): o cliente nunca manda um valor absoluto, o
servidor soma dentro de uma transacção e trava no zero. É isso que dá as duas
coisas ao mesmo tempo — cliques rápidos seguidos não se perdem (não há janela de
debounce onde dois colapsem num) e um retry de rede não conta a dobrar (o
`request_id` já está no log e a operação não se repete).

**AS MARCAS SOBREVIVEM AO DAILY** porque vivem na BASE e não numa página: o
`daily` reescreve `data/paginas/**` e o HTML, e nunca toca nesta tabela. Tem
teste.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from . import paginas, padrao, scryfall

#: Os dois estados de um número, e são visíveis e distintos no ecrã.
INVENTARIO = "inventario"
MARCADO = "marcado"

#: Tecto por carta. Não é uma regra de jogo (um Commander leva 1, um deck de 60
#: leva 4): é uma defesa contra o toque repetido e o dedo preso — e contra um
#: cliente estragado a mandar um delta absurdo. 99 é largo o suficiente para a
#: pilha de básicas dele (29 Snow-Covered Plains) e aperta o suficiente para um
#: engano se ver.
MAX_POR_CARTA = 99


class CartaDesconhecida(ValueError):
    """O catálogo não conhece esta carta — não se marca o que não existe."""


def _hoje() -> str:
    return date.today().isoformat()


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def inventario(con: sqlite3.Connection) -> dict[str, int]:
    """`nome (frente) -> cópias jogáveis na colecção`, do inventário.

    É o `paginas.posse_total` e nunca uma segunda contagem: a pergunta *"quantas
    tenho"* já tem resposta neste vault, e duas somas ao lado discordam um dia
    qualquer em silêncio — a lição do `event_tier`, do `e_foil` e do
    `precos.sql()`.
    """
    return paginas.posse_total(con)


def marcadas(con: sqlite3.Connection) -> dict[str, dict]:
    """Só o que ele TOCOU: `nome -> {q, em}`."""
    return {r["card_name"]: {"q": r["qty"], "em": r["marcado_em"]}
            for r in con.execute("SELECT card_name, qty, marcado_em "
                                 "FROM posse_marcada")}


def posse(con: sqlite3.Connection, inv: dict[str, int] | None = None,
          mks: dict[str, dict] | None = None) -> dict[str, dict]:
    """A POSSE EFECTIVA de cada carta: `nome -> {q, origem, em}`.

    A marca dele ganha sempre; onde não há marca, vale o inventário. Os dois
    mapas podem vir de fora (uma página pede isto uma vez e usa-o em vinte
    decks).
    """
    inv = inventario(con) if inv is None else inv
    mks = marcadas(con) if mks is None else mks
    # `MapaDeCartas` e não um `dict`: é a ele que o `conta_do_deck` pergunta
    # `pos.get(nm)` com o nome que a LISTA deu, e é o mapa que canoniza a chave.
    # Num `dict` cru, uma lista que pede `Wear/Tear` não achava as 2 cópias de
    # `Wear // Tear` e o deck aparecia a faltar uma carta que ele tem.
    out = scryfall.MapaDeCartas(
        {nm: {"q": q, "origem": INVENTARIO, "em": None}
         for nm, q in inv.items()})
    for nm, m in mks.items():
        out[nm] = {"q": m["q"], "origem": MARCADO, "em": m["em"]}
    return out


def de(con: sqlite3.Connection, nome: str) -> dict:
    """A posse de UMA carta, sem construir o mapa inteiro."""
    nm = _front(nome)
    r = con.execute("SELECT qty, marcado_em FROM posse_marcada WHERE card_name = ?",
                    (nm,)).fetchone()
    if r is not None:
        return {"q": r["qty"], "origem": MARCADO, "em": r["marcado_em"]}
    q = con.execute(
        f"""SELECT COALESCE(SUM(cp.quantity), 0) q FROM copies cp
              JOIN cards c ON c.scryfall_id = cp.scryfall_id
             WHERE {_jogaveis()} AND {scryfall.sql_nome("c.name")}""",
        scryfall.params_nome(nm)).fetchone()["q"]
    return {"q": q, "origem": INVENTARIO, "em": None}


def _front(nome: str) -> str:
    """A frente do nome. É o `scryfall.chave` e nunca um `split` próprio: o
    `posse_marcada.card_name` tem de ser a MESMA chave que a `posse_total`
    guarda, senão um `+` escrito sobre `Wear/Tear` cria uma linha que a lista
    nunca mais encontra."""
    return scryfall.chave(nome)


def _jogaveis() -> str:
    from . import collection
    return collection.jogaveis()


def ajustar(con: sqlite3.Connection, nome: str, delta: int,
            request_id: str | None = None, origem: str = "cli") -> dict:
    """Soma `delta` à posse desta carta. Trava no zero e no `MAX_POR_CARTA`.

    Devolve `{nome, q, origem, em, aplicado, base, repetido}`. O `base` diz de
    onde partiu a conta — `inventario` na primeira vez que ele toca numa carta,
    `marcado` daí em diante —, e é isso que torna o pré-preenchimento visível em
    vez de mágico.
    """
    nm = padrao.nome_no_catalogo(con, nome)
    if nm is None:
        raise CartaDesconhecida(
            f"o catálogo não conhece {nome!r} — confirma o nome em inglês")
    delta = int(delta)

    if request_id:
        prev = con.execute(
            "SELECT delta, qty_depois FROM posse_marcada_log WHERE request_id = ?",
            (request_id,)).fetchone()
        if prev is not None:
            # Já aplicámos este pedido: devolve o mesmo resultado, sem repetir.
            est = de(con, nm)
            return {"nome": nm, **est, "aplicado": prev["delta"],
                    "base": MARCADO, "repetido": True}

    con.execute("BEGIN IMMEDIATE")
    try:
        antes = de(con, nm)
        novo = max(0, min(MAX_POR_CARTA, antes["q"] + delta))
        aplicado = novo - antes["q"]
        if aplicado == 0 and antes["origem"] == MARCADO:
            con.execute("COMMIT")
            return {"nome": nm, **antes, "aplicado": 0, "base": MARCADO,
                    "repetido": False}
        con.execute(
            "INSERT INTO posse_marcada (card_name, qty, marcado_em) VALUES (?,?,?) "
            "ON CONFLICT(card_name) DO UPDATE SET qty = excluded.qty, "
            "marcado_em = excluded.marcado_em",
            (nm, novo, _hoje()))
        con.execute(
            "INSERT INTO posse_marcada_log (at, card_name, delta, qty_antes, "
            "qty_depois, base, origem, request_id) VALUES (?,?,?,?,?,?,?,?)",
            (_agora(), nm, aplicado, antes["q"], novo, antes["origem"],
             origem, request_id))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"nome": nm, "q": novo, "origem": MARCADO, "em": _hoje(),
            "aplicado": aplicado, "base": antes["origem"], "repetido": False}


def esquecer(con: sqlite3.Connection, nome: str, origem: str = "cli") -> dict:
    """Apaga a MARCA desta carta — volta a valer o inventário.

    Não é um `−` até zero: é *"esquece o que eu disse"*. **Nada se apaga da
    colecção** — a `copies` não se toca; o que sai é a opinião dele por cima
    dela. A linha fica no log, que é o rasto de sempre.
    """
    nm = _front(nome)
    r = con.execute("SELECT qty FROM posse_marcada WHERE card_name = ?",
                    (nm,)).fetchone()
    if r is None:
        return {"nome": nm, **de(con, nm), "aplicado": 0, "esqueceu": False}
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute("DELETE FROM posse_marcada WHERE card_name = ?", (nm,))
        depois = de(con, nm)
        con.execute(
            "INSERT INTO posse_marcada_log (at, card_name, delta, qty_antes, "
            "qty_depois, base, origem, request_id) VALUES (?,?,?,?,?,?,?,?)",
            (_agora(), nm, depois["q"] - r["qty"], r["qty"], depois["q"],
             MARCADO, origem + ":esquecer", None))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"nome": nm, **de(con, nm), "aplicado": depois["q"] - r["qty"],
            "esqueceu": True}


def historico(con: sqlite3.Connection, limite: int = 30) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT * FROM posse_marcada_log ORDER BY id DESC LIMIT ?", (limite,))]


def resumo(con: sqlite3.Connection) -> dict:
    """Quantas cartas vêm do inventário e quantas ele marcou — é a linha honesta
    que cada página leva, como a `confirmado.frase` fazia para as fotos."""
    inv = inventario(con)
    mks = marcadas(con)
    p = posse(con, inv, mks)
    return {"nomes": len(p), "copias": sum(x["q"] for x in p.values()),
            "do_inventario": sum(1 for x in p.values() if x["origem"] == INVENTARIO),
            "marcados_por_ti": len(mks),
            "copias_do_inventario": sum(q for nm, q in inv.items() if nm not in mks),
            "copias_marcadas": sum(m["q"] for m in mks.values())}


def frase(con: sqlite3.Connection, r: dict | None = None) -> str:
    r = resumo(con) if r is None else r
    if not r["marcados_por_ti"]:
        return (f"{r['copias']} cópias, todas do inventário — ainda não marcaste "
                f"nenhuma carta à mão")
    return (f"{r['copias']} cópias: {r['copias_do_inventario']} do inventário e "
            f"{r['copias_marcadas']} em {r['marcados_por_ti']} cartas que marcaste tu")
