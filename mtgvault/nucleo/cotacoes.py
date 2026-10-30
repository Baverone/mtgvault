"""As cotações do núcleo: o preço português, os preços vigiados, a variação e a
lista «a subir» (secção «Coleção»).

Decisões que não se leem do código:

- **O preço PT sai só de ofertas `mtg_language == "pt"` do CardTrader**, com o
  mesmo crivo do resto do projeto (`precos.oferta_utilizavel`, aqui com a única
  língua `pt`), e é a oferta mais barata do ÚLTIMO dia em que houve ofertas
  portuguesas. **Nunca cai no inglês**: um shock em português vale mais do que o
  inglês, e emprestar-lhe o trend do Cardmarket dava um número bonito e falso.
  Sem ofertas PT há semanas, a carta mostra o último preço visto e o dia dele
  (a página diz «visto há N dias»); nunca visto, mostra «sem preço».
- **Os preços vigiados guardam-se para sempre** (`n_preco_vigiado`), mas só
  quando mudam: o `price_history` é podado pelo daily e a variação a 90 dias
  não pode depender do que a poda deixou. Como o histórico (como o
  `write_prices`) só regista mudanças, «sem linha nova» quer dizer «manteve-se».
- **A variação é de hoje contra há N dias** e `None` quando falta um dos dois
  pontos: nunca 0 % por falta de dados. Para uma carta `pt` a variação vem só do
  `n_preco_pt` (`variacao_pt`), por isso nunca mistura um preço inglês.
- **«A subir» é o universo vigiado sem as cartas só-de-coleção** (a Reserved
  List, as impressões de papel das três famílias e o set `exp`) e só com preço
  de hoje ≥ `MINIMO_SUBIR`: abaixo disso uma subida de 100 % são cêntimos.

Só escreve nas tabelas `n_*`. As funções que escrevem abrem e fecham a sua
transação (a de `posse._transacao`).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

from .. import precos
from . import posse, valor

# as edições originais dos shocks em português: Ravnica, Guildpact, Dissension
SETS_PT = ("rav", "gpt", "dis")
# o preço de hoje abaixo do qual uma carta não entra em «a subir»
MINIMO_SUBIR = 20.0

_SO_PT = frozenset({"pt"})


# ---------------------------------------------------------------------------
# O preço português
# ---------------------------------------------------------------------------
def gravar_ofertas_pt(con: sqlite3.Connection, sid: str, ofertas: list[dict],
                      dia: str) -> int:
    """Grava em `n_preco_pt` a oferta PT mais barata de cada acabamento e quantas
    ofertas PT aceites havia. Devolve as linhas escritas (0 se nenhuma oferta
    passa o crivo: nesse dia a carta não tem preço PT e não se escreve nada)."""
    uteis = [o for o in ofertas if precos.oferta_utilizavel(o, _SO_PT)]
    n = 0
    with posse._transacao(con):
        for acab, foil in (("nonfoil", False), ("foil", True)):
            sel = [o for o in uteis
                   if bool((o.get("properties_hash") or {}).get("mtg_foil")) == foil]
            if not sel:
                continue
            minimo = min(o["price_cents"] for o in sel) / 100
            con.execute(
                "INSERT OR REPLACE INTO n_preco_pt (scryfall_id, acabamento, dia,"
                " preco_eur, ofertas) VALUES (?,?,?,?,?)",
                (sid, acab, dia, minimo, len(sel)))
            n += 1
    return n


def recolher_pt(con: sqlite3.Connection, ct, dia: str) -> int:
    """Pede ao CardTrader as ofertas das edições de `SETS_PT` e grava as das
    cartas `lingua = 'pt'` das coleções. Devolve as linhas escritas.

    Corre antes o mapa scryfall → blueprint dessas três edições. Uma carta de
    fora das coleções PT não se grava: o preço PT só interessa a quem o pede.
    """
    from .. import prices                                  # noqa: PLC0415
    prices.sync_cardtrader_map(con, ct, list(SETS_PT))
    alvo = {r["scryfall_id"] for r in con.execute(
        "SELECT DISTINCT scryfall_id FROM n_colecao_carta WHERE lingua = 'pt'")}
    bp_para_sid = {r["blueprint_id"]: r["scryfall_id"] for r in con.execute(
        "SELECT blueprint_id, scryfall_id FROM cardtrader_map")
        if r["scryfall_id"] in alvo}
    exps = prices.expansoes_mtg(ct)
    n = 0
    for code in SETS_PT:
        eid = exps.get(code)
        if not eid:
            continue
        for bp_id, ofertas in ct.marketplace(eid).items():
            sid = bp_para_sid.get(int(bp_id))
            if sid and ofertas:
                n += gravar_ofertas_pt(con, sid, ofertas, dia)
    return n


def preco_pt(con: sqlite3.Connection, sid: str,
             acabamento: str) -> tuple[float | None, str | None]:
    """`(preço, dia)` da linha PT mais recente, ou `(None, None)` se nunca houve."""
    r = con.execute(
        "SELECT preco_eur, dia FROM n_preco_pt WHERE scryfall_id = ?"
        " AND acabamento = ? ORDER BY dia DESC LIMIT 1",
        (sid, acabamento)).fetchone()
    return (r["preco_eur"], r["dia"]) if r else (None, None)


# ---------------------------------------------------------------------------
# Os preços vigiados
# ---------------------------------------------------------------------------
def _universo(con: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str]]:
    """`{(sid, acabamento): (nome, set_code)}` da Reserved List, das impressões
    de papel das três famílias e do set `exp`, só nos acabamentos que cada
    impressão tem (o núcleo só conhece `nonfoil` e `foil`)."""
    from . import colecoes                                 # noqa: PLC0415
    familias = colecoes.DUALS + colecoes.SHOCKS + colecoes.FETCHES
    marcas = ",".join("?" * len(familias))
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for r in con.execute(
            "SELECT scryfall_id, name, set_code, finishes FROM cards"
            " WHERE COALESCE(digital, 0) = 0 AND (reserved = 1"
            f" OR lower(set_code) = 'exp' OR name IN ({marcas}))", familias):
        try:
            acabamentos = json.loads(r["finishes"] or "[]")
        except (TypeError, ValueError):
            acabamentos = []
        for acab in posse.ACABAMENTOS:
            if acab in acabamentos:
                out[(r["scryfall_id"], acab)] = (r["name"], r["set_code"])
    return out


def vigiadas(con: sqlite3.Connection) -> list[tuple[str, str]]:
    """`(sid, acabamento)` das cartas das coleções, da Reserved List e das
    famílias, por ordem fixa. É a lista a que se guarda o preço para sempre e
    que o `prices.cards_of_interest` manda recolher."""
    v = set(_universo(con))
    v |= {(r["scryfall_id"], r["acabamento"]) for r in con.execute(
        "SELECT scryfall_id, acabamento FROM n_colecao_carta")}
    return sorted(v)


def gravar_vigiadas(con: sqlite3.Connection, dia: str) -> int:
    """Copia o trend do Cardmarket (`price_latest`, > 0) das vigiadas para
    `n_preco_vigiado`, só quando difere da última linha da carta. Devolve as
    linhas escritas."""
    atuais = {(r["scryfall_id"], r["finish"]): r["trend"] for r in con.execute(
        "SELECT scryfall_id, finish, trend FROM price_latest"
        " WHERE source = 'cardmarket' AND trend > 0")}
    n = 0
    with posse._transacao(con):
        for sid, acab in vigiadas(con):
            trend = atuais.get((sid, acab))
            if trend is None:
                continue
            ultima = con.execute(
                "SELECT preco_eur FROM n_preco_vigiado WHERE scryfall_id = ?"
                " AND acabamento = ? ORDER BY dia DESC LIMIT 1",
                (sid, acab)).fetchone()
            if ultima is not None and ultima["preco_eur"] == trend:
                continue
            con.execute(
                "INSERT OR REPLACE INTO n_preco_vigiado (scryfall_id, acabamento,"
                " dia, preco_eur) VALUES (?,?,?,?)", (sid, acab, dia, trend))
            n += 1
    return n


def preco_em(con: sqlite3.Connection, sid: str, acabamento: str,
             dia: str) -> float | None:
    """O preço vigiado desta carta em `dia` (a linha mais recente com
    `dia <= dia`). Sem nenhuma, o histórico que a poda deixou
    (`valor.preco`)."""
    r = con.execute(
        "SELECT preco_eur FROM n_preco_vigiado WHERE scryfall_id = ?"
        " AND acabamento = ? AND dia <= ? ORDER BY dia DESC LIMIT 1",
        (sid, acabamento, dia)).fetchone()
    if r is not None:
        return r["preco_eur"]
    return valor.preco(con, sid, acabamento, dia)


def _percentagem(agora: float | None, antes: float | None) -> float | None:
    if not agora or not antes:
        return None
    return round((agora / antes - 1) * 100, 1)


def _ha(hoje: str, dias: int) -> str:
    return (date.fromisoformat(hoje) - timedelta(days=dias)).isoformat()


def variacao(con: sqlite3.Connection, sid: str, acabamento: str, dias: int,
             hoje: str | None = None) -> float | None:
    """`(hoje / há N dias − 1) × 100` com uma casa, ou `None` sem um dos dois
    preços."""
    hoje = hoje or date.today().isoformat()
    return _percentagem(preco_em(con, sid, acabamento, hoje),
                        preco_em(con, sid, acabamento, _ha(hoje, dias)))


def _pt_em(con: sqlite3.Connection, sid: str, acabamento: str,
           dia: str) -> float | None:
    r = con.execute(
        "SELECT preco_eur FROM n_preco_pt WHERE scryfall_id = ? AND acabamento"
        " = ? AND dia <= ? ORDER BY dia DESC LIMIT 1",
        (sid, acabamento, dia)).fetchone()
    return r["preco_eur"] if r else None


def variacao_pt(con: sqlite3.Connection, sid: str, acabamento: str, dias: int,
                hoje: str | None = None) -> float | None:
    """A variação de uma carta em português, só com o `n_preco_pt`: «hoje» é o
    último preço PT visto até hoje. Nunca usa os preços vigiados nem o
    Cardmarket, que são ingleses."""
    hoje = hoje or date.today().isoformat()
    return _percentagem(_pt_em(con, sid, acabamento, hoje),
                        _pt_em(con, sid, acabamento, _ha(hoje, dias)))


# ---------------------------------------------------------------------------
# A subir
# ---------------------------------------------------------------------------
def a_subir(con: sqlite3.Connection, hoje: str | None = None) -> list[dict]:
    """As cartas vigiadas (Reserved List, famílias, `exp`) com preço de hoje
    `>= MINIMO_SUBIR`, por `var30` decrescente (`None` no fim, por nome).

    `tenho` soma o que ele tem nas coleções e o `n_posse` (qualquer âmbito) da
    mesma impressão e acabamento. `joga` fica vazio: quem o preenche é a lista
    de jogadas (Tarefa 5).
    """
    hoje = hoje or date.today().isoformat()
    tenho: dict[tuple[str, str], int] = {}
    for tabela, col in (("n_colecao_carta", "tenho"), ("n_posse", "qtd")):
        for r in con.execute(f"SELECT scryfall_id, acabamento, SUM({col}) q"
                             f" FROM {tabela} GROUP BY scryfall_id, acabamento"):
            k = (r["scryfall_id"], r["acabamento"])
            tenho[k] = tenho.get(k, 0) + (r["q"] or 0)
    linhas = []
    for (sid, acab), (nome, set_code) in _universo(con).items():
        preco = preco_em(con, sid, acab, hoje)
        if preco is None or preco < MINIMO_SUBIR:
            continue
        linhas.append({
            "nome": nome, "set_code": set_code, "scryfall_id": sid,
            "acabamento": acab, "preco": preco,
            "var30": variacao(con, sid, acab, 30, hoje),
            "var90": variacao(con, sid, acab, 90, hoje),
            "tenho": tenho.get((sid, acab), 0), "joga": []})
    linhas.sort(key=lambda l: (l["var30"] is None, -(l["var30"] or 0),
                               l["nome"], l["scryfall_id"], l["acabamento"]))
    return linhas
