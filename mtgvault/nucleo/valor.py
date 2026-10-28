"""Os preços do núcleo: o trend do Cardmarket por impressão e acabamento, o
valor do que ele tem (hoje e dia a dia) e a lista de Vender.

As regras (spec «Regras: Valor, Preços», 2026-10-28):

- **O preço é o `trend` do Cardmarket** da impressão e do acabamento exactos.
  Sem dia, o `price_latest`; com dia, a linha mais recente do `price_history`
  com `date <= dia` (o histórico só guarda MUDANÇAS: «não há linha nova»
  quer dizer «o preço manteve-se»). O daily poda o histórico com mais de 30
  dias, por isso um preço estável pode já não ter linha nenhuma: sem linha até
  `dia` E sem nenhuma depois, vale o `price_latest` (R13); com linhas só
  depois de `dia`, o preço ainda não existia. Sem preço, ou com `trend <= 0`, é `None`
  — «sem preço», nunca 0 €: um 0 numa soma tira uma carta do total sem nenhuma
  linha dizer que faltou.
- **O inventário é tudo o que é dele**: o `n_posse` de todos os âmbitos, o
  `n_a_mais` e o `n_saida`. Uma cópia que saiu de uma lista continua a ser dele
  até ele a resolver (`saida_resolver`: «tenho a mais» ou «descartar», que quer
  dizer vendida/foi-se). Uma linha de `ROT` é UM monte de cópias, por mais
  decks que o usem — cada cópia física conta uma vez.
- **O valor é só o que tem preço**; o que não tem fica fora do total e conta em
  `sem_preco`. Tanto `copias` como `sem_preco` contam CÓPIAS (quantidades, não
  linhas), por isso `copias - sem_preco` é o que entrou no total.
- **A série** usa o valor GRAVADO de cada dia (`n_valor`, nunca podada) e, para
  os dias antes do primeiro registo, calcula o valor do que ele tem hoje aos
  preços que o histórico ainda guarda. Um dia gravado não se recalcula: o
  inventário desse dia já foi outro.

Só escreve nas tabelas `n_*`; as funções que escrevem abrem e fecham a sua
transação.
"""
from __future__ import annotations

import sqlite3

from . import posse


# ---------------------------------------------------------------------------
# Preço
# ---------------------------------------------------------------------------
def preco(con: sqlite3.Connection, scryfall_id: str, acabamento: str,
          dia: str | None = None) -> float | None:
    """O `trend` do Cardmarket desta impressão e acabamento, ou `None`.

    `dia=None` lê o `price_latest`; com um dia (`AAAA-MM-DD`), a linha mais
    recente do `price_history` com `date <= dia`. A linha mais recente manda
    mesmo que seja 0: um trend a 0 depois de um preço é o Cardmarket sem
    vendas, e voltar ao preço de antes era inventar um preço de hoje.
    """
    chave = (scryfall_id, acabamento)
    r = None
    if dia is not None:
        r = con.execute(
            "SELECT trend FROM price_history WHERE scryfall_id = ?"
            " AND source = 'cardmarket' AND finish = ? AND date <= ?"
            " ORDER BY date DESC LIMIT 1", (*chave, dia)).fetchone()
        if r is None and con.execute(
                "SELECT 1 FROM price_history WHERE scryfall_id = ?"
                " AND source = 'cardmarket' AND finish = ? AND date > ?"
                " LIMIT 1", (*chave, dia)).fetchone():
            return None     # o primeiro preço é posterior a este dia
    if r is None:
        # `dia=None`, ou (R13) um preço sem linha de histórico até `dia` e sem
        # nenhuma depois: manteve-se igual desde antes da janela que o daily
        # poda (`_prune_prices`), e quem o tem é o `price_latest`
        r = con.execute(
            "SELECT trend FROM price_latest WHERE scryfall_id = ?"
            " AND source = 'cardmarket' AND finish = ?", chave).fetchone()
    if r is None or r[0] is None or r[0] <= 0:
        return None
    return float(r[0])


# ---------------------------------------------------------------------------
# Inventário e valor
# ---------------------------------------------------------------------------
def inventario(con: sqlite3.Connection) -> list[tuple[str, str, int]]:
    """`(scryfall_id, acabamento, qtd)` de tudo o que é dele: `n_posse` (todos
    os âmbitos), `n_a_mais` e `n_saida`, somado por impressão e acabamento e
    por ordem."""
    return [(r[0], r[1], r[2]) for r in con.execute(
        "SELECT scryfall_id, acabamento, SUM(qtd) FROM ("
        " SELECT scryfall_id, acabamento, qtd FROM n_posse"
        " UNION ALL SELECT scryfall_id, acabamento, qtd FROM n_a_mais"
        " UNION ALL SELECT scryfall_id, acabamento, qtd FROM n_saida)"
        " GROUP BY scryfall_id, acabamento HAVING SUM(qtd) > 0"
        " ORDER BY scryfall_id, acabamento")]


def _valor_de(con: sqlite3.Connection, inv: list[tuple[str, str, int]],
              dia: str | None) -> dict:
    total, copias, sem = 0.0, 0, 0
    for sid, acab, qtd in inv:
        copias += qtd
        p = preco(con, sid, acab, dia)
        if p is None:
            sem += qtd
        else:
            total += p * qtd
    return {"total_eur": round(total, 2), "copias": copias, "sem_preco": sem}


def valor_em(con: sqlite3.Connection, dia: str | None = None) -> dict:
    """O valor do inventário de hoje aos preços de `dia` (sem dia: aos de hoje,
    do `price_latest`) → `{total_eur, copias, sem_preco}`."""
    return _valor_de(con, inventario(con), dia)


def gravar_valor_do_dia(con: sqlite3.Connection, dia: str) -> dict:
    """Calcula o valor de `dia` e grava-o em `n_valor` (substitui o do mesmo
    dia). Devolve o que gravou."""
    with posse._transacao(con):
        v = valor_em(con, dia)
        con.execute(
            "INSERT OR REPLACE INTO n_valor (dia, total_eur, copias, sem_preco)"
            " VALUES (?,?,?,?)",
            (dia, v["total_eur"], v["copias"], v["sem_preco"]))
    return v


def serie(con: sqlite3.Connection) -> list[tuple[str, float]]:
    """`[(dia, total_eur)]` por ordem: os dias de `n_valor` (o que foi gravado)
    e, antes do primeiro, cada dia com preço do Cardmarket no histórico,
    calculado com o inventário de hoje (`valor_em`). Sem `n_valor` nenhum, são
    todos os dias do histórico."""
    gravados = [(r[0], float(r[1] or 0.0)) for r in con.execute(
        "SELECT dia, total_eur FROM n_valor ORDER BY dia")]
    primeiro = gravados[0][0] if gravados else None
    if primeiro is None:
        dias = [r[0] for r in con.execute(
            "SELECT DISTINCT date FROM price_history WHERE source = 'cardmarket'"
            " ORDER BY date")]
    else:
        dias = [r[0] for r in con.execute(
            "SELECT DISTINCT date FROM price_history WHERE source = 'cardmarket'"
            " AND date < ? ORDER BY date", (primeiro,))]
    inv = inventario(con)
    atras = [(d, _valor_de(con, inv, d)["total_eur"]) for d in dias]
    return atras + gravados


# ---------------------------------------------------------------------------
# Vender
# ---------------------------------------------------------------------------
def _linha(nome, set_code, sid, acab, qtd, preco_un, motivo, deck) -> dict:
    return {"nome": nome, "set_code": set_code, "scryfall_id": sid,
            "acabamento": acab, "qtd": qtd, "preco_un": preco_un,
            "motivo": motivo, "deck": deck}


def a_vender(con: sqlite3.Connection) -> dict:
    """A lista de Vender: o que ele tem a mais (`a_mais`) e o que saiu dos
    decks (`saidas`: `saiu_da_lista` ou `trocou_edicao`), com o preço de hoje
    de cada impressão e acabamento.

    Cada linha de `saidas` leva o `id` do `n_saida` (é com ele que a página
    chama `saida_resolver`) e o nome do deck de onde saiu. Os totais só somam o
    que tem preço; o que não tem conta em `sem_preco` (em cópias).
    """
    a_mais, saidas = [], []
    for r in con.execute(
            "SELECT m.scryfall_id, m.acabamento, m.qtd, c.name, c.set_code"
            " FROM n_a_mais m LEFT JOIN cards c ON c.scryfall_id = m.scryfall_id"
            " WHERE m.qtd > 0 ORDER BY lower(COALESCE(c.name, m.scryfall_id)),"
            " m.scryfall_id, m.acabamento").fetchall():
        a_mais.append(_linha(r[3] or r[0], r[4], r[0], r[1], r[2],
                             preco(con, r[0], r[1]), "a_mais", None))
    for r in con.execute(
            "SELECT s.id, s.slug, s.motivo, s.scryfall_id, s.acabamento, s.qtd,"
            " c.name, c.set_code, d.nome FROM n_saida s"
            " LEFT JOIN cards c ON c.scryfall_id = s.scryfall_id"
            " LEFT JOIN n_deck d ON d.slug = s.slug"
            " WHERE s.qtd > 0 ORDER BY s.id").fetchall():
        l = _linha(r[6] or r[3], r[7], r[3], r[4], r[5], preco(con, r[3], r[4]),
                   r[2], r[8] or r[1])
        l["id"] = r[0]
        saidas.append(l)
    total, sem = 0.0, 0
    for l in a_mais + saidas:
        if l["preco_un"] is None:
            sem += l["qtd"]
        else:
            total += l["preco_un"] * l["qtd"]
    return {"a_mais": a_mais, "saidas": saidas, "total_eur": round(total, 2),
            "sem_preco": sem}


def a_mais_ajustar(con: sqlite3.Connection, scryfall_id: str, acabamento: str,
                   delta: int, *, nota: str = "") -> int:
    """Soma `delta` ao «tenho a mais» desta impressão e acabamento e devolve a
    quantidade nova. Nunca abaixo de 0; a linha desaparece no 0.

    A impressão tem de existir no catálogo e ter esse acabamento
    (`ValueError` se não). Uma `nota` não vazia substitui a que lá estava; sem
    nota, fica a que havia.
    """
    if acabamento not in posse.ACABAMENTOS:
        raise ValueError(f"acabamento inválido: {acabamento!r} (nonfoil | foil)")
    with posse._transacao(con):
        r = con.execute("SELECT finishes FROM cards WHERE scryfall_id = ?",
                        (scryfall_id,)).fetchone()
        if r is None:
            raise ValueError(f"impressão desconhecida: {scryfall_id!r}")
        if acabamento not in posse._finishes(r):
            raise ValueError(f"{scryfall_id!r} não existe em {acabamento}")
        atual = con.execute(
            "SELECT qtd, nota FROM n_a_mais WHERE scryfall_id = ?"
            " AND acabamento = ?", (scryfall_id, acabamento)).fetchone()
        antes = atual[0] if atual else 0
        nova = max(0, antes + int(delta))
        if nova > 0:
            con.execute(
                "INSERT OR REPLACE INTO n_a_mais (scryfall_id, acabamento, qtd,"
                " nota) VALUES (?,?,?,?)",
                (scryfall_id, acabamento, nova,
                 nota or (atual[1] if atual else "") or ""))
        else:
            con.execute("DELETE FROM n_a_mais WHERE scryfall_id = ?"
                        " AND acabamento = ?", (scryfall_id, acabamento))
    return nova


def saida_resolver(con: sqlite3.Connection, saida_id: int, destino: str) -> None:
    """Decide o que fazer a uma saída: `'a_mais'` passa as cópias para «tenho a
    mais» (somando ao que lá houver; continuam dele) e `'descartar'` apaga a
    linha (vendidas ou foram-se). `ValueError` se o id ou o destino não
    existirem."""
    if destino not in ("a_mais", "descartar"):
        raise ValueError(f"destino inválido: {destino!r} (a_mais | descartar)")
    with posse._transacao(con):
        r = con.execute("SELECT scryfall_id, acabamento, qtd FROM n_saida"
                        " WHERE id = ?", (saida_id,)).fetchone()
        if r is None:
            raise ValueError(f"saída desconhecida: {saida_id!r}")
        if destino == "a_mais":
            con.execute(
                "INSERT INTO n_a_mais (scryfall_id, acabamento, qtd, nota)"
                " VALUES (?,?,?,'') ON CONFLICT (scryfall_id, acabamento)"
                " DO UPDATE SET qtd = qtd + excluded.qtd", (r[0], r[1], r[2]))
        con.execute("DELETE FROM n_saida WHERE id = ?", (saida_id,))
