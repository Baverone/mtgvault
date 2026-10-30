"""As coleções do núcleo (secção «Coleção»): conjuntos de cartas que ele quer
juntar, fechadas (uma lista fixa com meta por carta) ou abertas (cartas que ele
vai acrescentando, sem meta).

Quatro, por esta ordem (`COLECOES`): Duals de Revised, Zendikar Expeditions,
Shocks originais em português (as três fechadas, meta 4 de cada) e a Reserved
List (aberta, vazia até ele a encher).

Decisões que não se leem do código:

- **Uma carta de coleção é uma impressão, um acabamento e uma língua** (a chave
  da `n_colecao_carta`). A língua pesa porque os Shocks em português só valem
  em `pt`: ter o mesmo shock em inglês não os cumpre.
- **O `scryfall_id` resolve-se pelo nome e pelo set** e, se houver várias
  impressões (promos, números alternativos), ganha a de menor número do
  colecionador, para o resultado não depender da ordem do catálogo.
- **Uma carta que o catálogo não tem levanta `ValueError` e não grava nada**:
  semear uma coleção a meio era mostrar «0 de 36» como se fosse um facto.
- **O progresso (`tenho`/`total`) não conta o que passa da meta**: cinco de uma
  meta de quatro é quatro de quatro, senão uma carta a mais escondia uma que
  falta. O valor em euros conta tudo o que ele tem.
- **«Sem preço» nunca é 0 €** (como no `valor.preco`): o custo do que falta
  soma só as cartas com preço e conta as restantes em `sem_preco`.

Só escreve nas tabelas `n_*`. As funções que escrevem abrem e fecham a sua
transação (a de `posse._transacao`).
"""
from __future__ import annotations

import sqlite3
from datetime import date

from . import cotacoes, fotos, jogada, posse, valor

DUALS = ("Badlands", "Bayou", "Plateau", "Savannah", "Scrubland", "Taiga",
         "Tropical Island", "Tundra", "Underground Sea", "Volcanic Island")
SHOCKS = ("Blood Crypt", "Breeding Pool", "Godless Shrine", "Hallowed Fountain",
          "Overgrown Tomb", "Sacred Foundry", "Steam Vents", "Stomping Ground",
          "Temple Garden", "Watery Grave")
FETCHES = ("Arid Mesa", "Bloodstained Mire", "Flooded Strand", "Marsh Flats",
           "Misty Rainforest", "Polluted Delta", "Scalding Tarn",
           "Verdant Catacombs", "Windswept Heath", "Wooded Foothills")

# a edição original em português de cada shock: Ravnica, Guildpact, Dissension
_SHOCKS_PT = (
    ("rav", ("Overgrown Tomb", "Sacred Foundry", "Temple Garden", "Watery Grave")),
    ("gpt", ("Godless Shrine", "Steam Vents", "Stomping Ground")),
    ("dis", ("Blood Crypt", "Breeding Pool", "Hallowed Fountain")),
)

META = 4

COLECOES: tuple[dict, ...] = (
    {"slug": "duals_revised", "nome": "Duals de Revised", "tipo": "fechada",
     "arte_nome": "Underground Sea",
     "cartas": tuple((n, "3ed", "nonfoil", "en") for n in DUALS)},
    {"slug": "expeditions", "nome": "Zendikar Expeditions", "tipo": "fechada",
     "arte_nome": "Scalding Tarn",
     "cartas": tuple((n, "exp", "foil", "en") for n in SHOCKS + FETCHES)},
    {"slug": "shocks_pt", "nome": "Shocks originais em português",
     "tipo": "fechada", "arte_nome": "Steam Vents",
     "cartas": tuple((n, s, "nonfoil", "pt")
                     for s, nomes in _SHOCKS_PT for n in nomes)},
    {"slug": "reserved_list", "nome": "Reserved List", "tipo": "aberta",
     "arte_nome": None, "cartas": ()},
)


# ---------------------------------------------------------------------------
# Criar as coleções
# ---------------------------------------------------------------------------
def _resolver(con: sqlite3.Connection, nome: str, set_code: str) -> str:
    r = con.execute(
        "SELECT scryfall_id FROM cards WHERE name = ? AND set_code = ?"
        " ORDER BY CAST(collector_number AS INTEGER), collector_number,"
        " scryfall_id LIMIT 1", (nome, set_code)).fetchone()
    if r is None:
        raise ValueError(f"o catálogo não tem {nome!r} no set {set_code!r}")
    return r[0]


def garantir_colecoes(con: sqlite3.Connection) -> int:
    """Insere as coleções que faltam e as cartas que faltam a cada uma (meta 4),
    e devolve quantas COLEÇÕES criou (0 na segunda chamada). Não mexe no que já
    lá está: nem no que ele marcou nem numa meta que mudou.

    Resolve tudo antes de abrir a transação: uma carta que falta no catálogo
    levanta `ValueError` (nome e set) e a base fica como estava.
    """
    resolvidas = [(c, [(n, _resolver(con, n, s), a, l) for n, s, a, l in c["cartas"]])
                  for c in COLECOES]
    criadas = 0
    with posse._transacao(con):
        for c, cartas in resolvidas:
            existia = con.execute("SELECT 1 FROM n_colecao WHERE slug = ?",
                                  (c["slug"],)).fetchone()
            if not existia:
                con.execute(
                    "INSERT INTO n_colecao (slug, nome, tipo, arte_nome, ordem)"
                    " VALUES (?,?,?,?,?)",
                    (c["slug"], c["nome"], c["tipo"], c["arte_nome"],
                     COLECOES.index(c) + 1))
                criadas += 1
            for nome, sid, acab, lingua in cartas:
                con.execute(
                    "INSERT OR IGNORE INTO n_colecao_carta (colecao, nome,"
                    " scryfall_id, acabamento, lingua, meta) VALUES (?,?,?,?,?,?)",
                    (c["slug"], nome, sid, acab, lingua, META))
    return criadas


def colecoes(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """As coleções, pela `ordem`."""
    return con.execute("SELECT slug, nome, tipo, arte_nome, ordem FROM n_colecao"
                       " ORDER BY ordem").fetchall()


# ---------------------------------------------------------------------------
# O estado
# ---------------------------------------------------------------------------
def _preco_un(con: sqlite3.Connection, scryfall_id: str, acabamento: str,
              lingua: str) -> tuple[float | None, str | None]:
    """`(preço de uma unidade, dia em que foi visto)`. Em `en` é o trend do
    Cardmarket (sem dia: é o de hoje); em `pt` é o último preço português do
    CardTrader e o dia dele. Nunca se empresta o inglês a uma carta `pt`: um
    shock em português vale mais do que o inglês."""
    if lingua == "en":
        return valor.preco(con, scryfall_id, acabamento), None
    if lingua == "pt":
        return cotacoes.preco_pt(con, scryfall_id, acabamento)
    return None, None


def _variacao(con: sqlite3.Connection, scryfall_id: str, acabamento: str,
              lingua: str, dias: int, hoje: str) -> float | None:
    # em `pt` só o `n_preco_pt`: a variação inglesa não é a da carta portuguesa
    if lingua == "pt":
        return cotacoes.variacao_pt(con, scryfall_id, acabamento, dias, hoje)
    return cotacoes.variacao(con, scryfall_id, acabamento, dias, hoje)


def estado_colecao(con: sqlite3.Connection, slug: str,
                   hoje: str | None = None) -> dict:
    """A coleção e as suas cartas, com o que falta e o que vale.

    `total` e `falta` só existem nas fechadas (nas abertas ficam `None`).
    `preco_visto_em` só existe nas cartas `pt` (o dia do último preço português
    visto) e `var30`/`var90` vêm das cotações (`hoje` é para os testes). Os
    `joga` vem de `jogada.onde_joga`; `validadas` (no máximo `tenho`) e `recorte`
    vêm das fotos, e a coleção soma as validadas (numa fechada, cada carta corta
    na meta, como o `tenho`).
    """
    hoje = hoje or date.today().isoformat()
    col = con.execute("SELECT slug, nome, tipo FROM n_colecao WHERE slug = ?",
                      (slug,)).fetchone()
    if col is None:
        raise ValueError(f"coleção desconhecida: {slug!r}")
    fechada = col["tipo"] == "fechada"
    cartas = []
    tenho = total = validadas = 0
    custo_falta = valor_eur = 0.0
    sem_preco = 0
    for r in con.execute(
            "SELECT id, nome, scryfall_id, acabamento, lingua, meta, tenho,"
            " vender FROM n_colecao_carta WHERE colecao = ? ORDER BY id",
            (slug,)).fetchall():
        preco, visto_em = _preco_un(con, r["scryfall_id"], r["acabamento"],
                                    r["lingua"])
        validadas_ = min(r["tenho"], fotos.validadas(
            con, slug, r["scryfall_id"], r["acabamento"], r["lingua"]))
        meta = r["meta"] if fechada else None
        falta = max(0, (meta or 0) - r["tenho"]) if fechada else None
        if fechada:
            total += meta or 0
            tenho += min(r["tenho"], meta or 0)
            # a soma das validadas corta na meta como o `tenho`: senão a página
            # dizia «4 de 40 · 6 validadas». A carta continua a dizer as suas.
            validadas += min(validadas_, meta or 0)
        else:
            tenho += r["tenho"]
            validadas += validadas_
        if falta or r["tenho"]:
            if preco is None:
                sem_preco += 1
        if preco is not None:
            custo_falta += (falta or 0) * preco
            valor_eur += r["tenho"] * preco
        cartas.append({
            "id": r["id"], "nome": r["nome"], "scryfall_id": r["scryfall_id"],
            "acabamento": r["acabamento"], "lingua": r["lingua"],
            "meta": meta, "tenho": r["tenho"], "falta": falta,
            "vender": r["vender"], "preco_un": preco, "preco_visto_em": visto_em,
            "var30": _variacao(con, r["scryfall_id"], r["acabamento"],
                               r["lingua"], 30, hoje),
            "var90": _variacao(con, r["scryfall_id"], r["acabamento"],
                               r["lingua"], 90, hoje),
            "joga": jogada.onde_joga(con, r["nome"], hoje),
            # nunca mais validadas do que cópias (o −1 já apara, mas a conta
            # não depende de ninguém se ter lembrado)
            "validadas": validadas_,
            "recorte": (fotos.recorte_de(con, slug, r["scryfall_id"],
                                         r["acabamento"], r["lingua"])
                        if validadas_ else None)})
    return {"slug": col["slug"], "nome": col["nome"], "tipo": col["tipo"],
            "cartas": cartas, "tenho": tenho,
            "total": total if fechada else None,
            "custo_falta": round(custo_falta, 2),
            "valor_eur": round(valor_eur, 2), "sem_preco": sem_preco,
            "validadas": validadas}


# ---------------------------------------------------------------------------
# Escrever
# ---------------------------------------------------------------------------
def _carta(con: sqlite3.Connection, carta_id: int) -> sqlite3.Row:
    r = con.execute(
        "SELECT c.id, c.colecao, c.scryfall_id, c.acabamento, c.lingua,"
        " c.tenho, n.tipo FROM n_colecao_carta c"
        " JOIN n_colecao n ON n.slug = c.colecao WHERE c.id = ?",
        (carta_id,)).fetchone()
    if r is None:
        raise ValueError(f"carta de coleção desconhecida: {carta_id!r}")
    return r


def ajustar(con: sqlite3.Connection, carta_id: int, delta: int, *,
            request_id: str) -> int:
    """Soma `delta` ao que ele tem desta carta e devolve a quantidade nova.

    Idempotente por `request_id` (o telemóvel a repetir um toque conta uma vez
    e devolve a quantidade de agora). Nunca abaixo de 0: o que passaria do zero
    é cortado, e o `delta` registado é o que se aplicou. Se a quantidade
    desceu, aparam-se as fotos validadas que já não cabem.
    """
    if not request_id:
        raise ValueError("falta o request_id")
    with posse._transacao(con):
        c = _carta(con, carta_id)
        if con.execute("SELECT 1 FROM n_colecao_log WHERE request_id = ?",
                       (request_id,)).fetchone():
            return c["tenho"]
        nova = max(0, c["tenho"] + int(delta))
        con.execute("UPDATE n_colecao_carta SET tenho = ? WHERE id = ?",
                    (nova, carta_id))
        con.execute("INSERT INTO n_colecao_log (request_id, carta_id, delta, em)"
                    " VALUES (?,?,?,?)",
                    (request_id, carta_id, nova - c["tenho"], posse._agora()))
        if nova < c["tenho"]:
            # o âmbito de uma carta de coleção é o slug da coleção
            fotos.aparar_validadas(con, c["colecao"], c["scryfall_id"],
                                   c["acabamento"], c["lingua"], nova)
    return nova


def definir_meta(con: sqlite3.Connection, carta_id: int, meta: int) -> None:
    """A meta desta carta (≥ 0). Só numa coleção fechada: a aberta não tem meta."""
    meta = int(meta)
    if meta < 0:
        raise ValueError(f"a meta não pode ser negativa: {meta}")
    with posse._transacao(con):
        if _carta(con, carta_id)["tipo"] != "fechada":
            raise ValueError("uma coleção aberta não tem meta")
        con.execute("UPDATE n_colecao_carta SET meta = ? WHERE id = ?",
                    (meta, carta_id))


def marcar_vender(con: sqlite3.Connection, carta_id: int, vender: bool) -> None:
    """Liga ou desliga a marca «para vender» desta carta."""
    with posse._transacao(con):
        _carta(con, carta_id)
        con.execute("UPDATE n_colecao_carta SET vender = ? WHERE id = ?",
                    (1 if vender else 0, carta_id))


def juntar(con: sqlite3.Connection, slug: str, scryfall_id: str,
           acabamento: str, lingua: str = "en") -> int:
    """Acrescenta uma carta a uma coleção ABERTA e devolve o `id`; se já lá
    está, devolve o mesmo `id`. Numa fechada levanta `ValueError`: a lista dela
    é fixa. A língua é `en` ou `pt`: são as duas que têm preço (a `pt` vem do
    CardTrader), e outra qualquer ficava para sempre «sem preço». E `pt` só
    numa edição de `cotacoes.SETS_PT`: o `recolher_pt` só pede ao CardTrader
    as ofertas dessas, por isso uma carta `pt` de outra edição também nunca
    teria preço (e o inglês nunca se lhe empresta)."""
    if lingua not in ("en", "pt"):
        raise ValueError(f"língua inválida: {lingua!r} (en | pt)")
    if acabamento not in posse.ACABAMENTOS:
        raise ValueError(f"acabamento inválido: {acabamento!r} (nonfoil | foil)")
    with posse._transacao(con):
        col = con.execute("SELECT tipo FROM n_colecao WHERE slug = ?",
                          (slug,)).fetchone()
        if col is None:
            raise ValueError(f"coleção desconhecida: {slug!r}")
        if col["tipo"] != "aberta":
            raise ValueError(f"{slug!r} é uma coleção fechada: a lista é fixa")
        r = con.execute("SELECT name, finishes, digital, set_code FROM cards"
                        " WHERE scryfall_id = ?", (scryfall_id,)).fetchone()
        if r is None or r["digital"]:
            raise ValueError(f"{scryfall_id!r} não é uma impressão em papel")
        if lingua == "pt" and r["set_code"] not in cotacoes.SETS_PT:
            raise ValueError(
                f"{r['name']!r} ({r['set_code']}) não pode entrar em português:"
                f" só se recolhem preços portugueses das edições"
                f" {', '.join(cotacoes.SETS_PT)}, e noutra a carta ficava"
                " «sem preço» para sempre")
        if acabamento not in posse._finishes(r):
            raise ValueError(f"{r['name']!r} ({scryfall_id}) não existe em"
                             f" {acabamento}")
        con.execute(
            "INSERT OR IGNORE INTO n_colecao_carta (colecao, nome, scryfall_id,"
            " acabamento, lingua) VALUES (?,?,?,?,?)",
            (slug, r["name"], scryfall_id, acabamento, lingua))
        return con.execute(
            "SELECT id FROM n_colecao_carta WHERE colecao = ? AND scryfall_id"
            " = ? AND acabamento = ? AND lingua = ?",
            (slug, scryfall_id, acabamento, lingua)).fetchone()[0]
