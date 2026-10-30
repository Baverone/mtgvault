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
  preços que o histórico ainda guarda — só os dias com a cobertura de preços
  de hoje (R15, ver `serie`). Um dia gravado não se recalcula: o inventário
  desse dia já foi outro. (R18) O último ponto é o valor de HOJE ao vivo, e
  um dia gravado sem cópias não entra (nem se grava).
- **A variação do mês** (R18, `variacao_mes`) compara o inventário de hoje
  consigo próprio: aos preços de hoje e aos de há 30 dias. Não usa os dias
  gravados — esses mediram outro inventário, e no primeiro dia dele davam
  «−100 %» contra um dia gravado antes de marcar a primeira carta.

- **O valor tem três partes** (R8, 2026-10-30): `decks_eur` (o `n_posse`),
  `a_mais_eur` (o `n_a_mais` e o `n_saida`, o que está em Vender) e
  `colecoes_eur` (as cartas das coleções com `tenho > 0`); `total_eur` é a
  soma. Uma carta de coleção tem língua: em `pt` o preço é o `n_preco_pt` mais
  recente até esse dia (nunca o inglês — sem ele a cópia conta em `sem_preco`);
  nas outras é o preço de sempre, com o histórico vigiado
  (`cotacoes.preco_em`). Sem coleções, os números são os de antes.

Só escreve nas tabelas `n_*`; as funções que escrevem abrem e fecham a sua
transação.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from . import posse

# (R18) a variação do Painel é «num mês»
DIAS_DA_VARIACAO = 30


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
    """`(scryfall_id, acabamento, qtd)` de tudo o que é dele nos decks e em
    Vender: `n_posse` (todos os âmbitos), `n_a_mais` e `n_saida`, somado por
    impressão e acabamento e por ordem. As coleções ficam de fora (têm língua e
    o seu próprio preço; ver `_partes`)."""
    return [(r[0], r[1], r[2]) for r in con.execute(
        "SELECT scryfall_id, acabamento, SUM(qtd) FROM ("
        " SELECT scryfall_id, acabamento, qtd FROM n_posse"
        " UNION ALL SELECT scryfall_id, acabamento, qtd FROM n_a_mais"
        " UNION ALL SELECT scryfall_id, acabamento, qtd FROM n_saida)"
        " GROUP BY scryfall_id, acabamento HAVING SUM(qtd) > 0"
        " ORDER BY scryfall_id, acabamento")]


def _partes(con: sqlite3.Connection) -> dict:
    """O inventário de hoje em três partes: `decks` e `a_mais` como
    `(scryfall_id, acabamento, qtd)`, `colecoes` como `(scryfall_id,
    acabamento, lingua, qtd)` (a língua decide o preço). Cada cópia física está
    numa só parte: o `n_posse` é dos decks, o `n_a_mais` e o `n_saida` são o que
    está em Vender, e as coleções têm as suas próprias linhas."""
    def tres(sql):
        return [(r[0], r[1], r[2]) for r in con.execute(sql)]
    return {
        "decks": tres(
            "SELECT scryfall_id, acabamento, SUM(qtd) FROM n_posse"
            " GROUP BY scryfall_id, acabamento HAVING SUM(qtd) > 0"
            " ORDER BY scryfall_id, acabamento"),
        "a_mais": tres(
            "SELECT scryfall_id, acabamento, SUM(qtd) FROM ("
            " SELECT scryfall_id, acabamento, qtd FROM n_a_mais"
            " UNION ALL SELECT scryfall_id, acabamento, qtd FROM n_saida)"
            " GROUP BY scryfall_id, acabamento HAVING SUM(qtd) > 0"
            " ORDER BY scryfall_id, acabamento"),
        "colecoes": _cartas_das_colecoes(con),
    }


def _cartas_das_colecoes(con: sqlite3.Connection, slug: str | None = None
                         ) -> list[tuple[str, str, str, int]]:
    """`(scryfall_id, acabamento, lingua, tenho)` das cartas de coleção que ele
    tem (`tenho > 0`), de uma coleção ou de todas (somando a mesma carta que
    esteja em mais do que uma)."""
    filtro, args = ("WHERE colecao = ? AND tenho > 0", (slug,)) if slug else (
        "WHERE tenho > 0", ())
    return [(r[0], r[1], r[2], r[3]) for r in con.execute(
        "SELECT scryfall_id, acabamento, lingua, SUM(tenho) FROM n_colecao_carta"
        f" {filtro} GROUP BY scryfall_id, acabamento, lingua"
        " ORDER BY scryfall_id, acabamento, lingua", args)]


def _preco_colecao(con: sqlite3.Connection, scryfall_id: str, acabamento: str,
                   lingua: str, dia: str | None) -> float | None:
    """O preço de uma cópia de coleção. Em `pt`, o `n_preco_pt` mais recente até
    `dia` (sem dia, o mais recente que houver) e NUNCA o inglês: um shock em
    português vale mais, e o trend inglês seria um número bonito e falso. Nas
    outras línguas, o preço de `dia` com o histórico vigiado
    (`cotacoes.preco_em`) e, sem dia, o de hoje (`preco`)."""
    from . import cotacoes                                 # noqa: PLC0415
    if lingua == "pt":
        if dia is None:
            p = cotacoes.preco_pt(con, scryfall_id, acabamento)[0]
        else:
            r = cotacoes._pt_em(con, scryfall_id, acabamento, dia)
            p = r["preco_eur"] if r is not None else None
        return p if p is not None and p > 0 else None
    if dia is None:
        return preco(con, scryfall_id, acabamento)
    return cotacoes.preco_em(con, scryfall_id, acabamento, dia)


def _somar(itens, preco_de) -> tuple[float, int, int]:
    """`(total, cópias, cópias sem preço)` de `itens` = `(*chave, qtd)`. O que
    não tem preço fica fora do total e conta em `sem_preco`, nunca como 0."""
    total, copias, sem = 0.0, 0, 0
    for *chave, qtd in itens:
        copias += qtd
        p = preco_de(*chave)
        if p is None:
            sem += qtd
        else:
            total += p * qtd
    return total, copias, sem


def _valor_de(con: sqlite3.Connection, partes: dict, dia: str | None) -> dict:
    d_tot, d_cop, d_sem = _somar(
        partes["decks"], lambda sid, acab: preco(con, sid, acab, dia))
    a_tot, a_cop, a_sem = _somar(
        partes["a_mais"], lambda sid, acab: preco(con, sid, acab, dia))
    preco_de = lambda sid, acab, ling: _preco_colecao(con, sid, acab, ling, dia)
    c_tot, c_cop, c_sem = _somar(partes["colecoes"], preco_de)
    # (R9) a cobertura que a R15 compara não conta as cópias `pt`: o preço PT só
    # existe desde que a recolha começou, e contá-las deitava fora todo o
    # histórico no dia em que ele marcasse a primeira
    _, _, c_sem_pt = _somar([i for i in partes["colecoes"] if i[2] == "pt"],
                            preco_de)
    return {"total_eur": round(d_tot + a_tot + c_tot, 2),
            "copias": d_cop + a_cop + c_cop, "sem_preco": d_sem + a_sem + c_sem,
            "decks_eur": round(d_tot, 2), "a_mais_eur": round(a_tot, 2),
            "colecoes_eur": round(c_tot, 2),
            "sem_preco_cobertura": d_sem + a_sem + c_sem - c_sem_pt}


def valor_em(con: sqlite3.Connection, dia: str | None = None) -> dict:
    """O valor do inventário de hoje aos preços de `dia` (sem dia: aos de hoje,
    do `price_latest`) → `{total_eur, copias, sem_preco, decks_eur, a_mais_eur,
    colecoes_eur}`; `total_eur` é a soma das três partes."""
    v = _valor_de(con, _partes(con), dia)
    del v["sem_preco_cobertura"]            # só serve à R15 (`serie`, `variacao_mes`)
    return v


def valor_colecoes(con: sqlite3.Connection, dia: str | None = None) -> dict:
    """Só as coleções (as cartas com `tenho > 0`), aos preços de `dia` (sem dia:
    aos de hoje) → `{total_eur, copias, sem_preco}`."""
    total, copias, sem = _somar(
        _cartas_das_colecoes(con),
        lambda sid, acab, ling: _preco_colecao(con, sid, acab, ling, dia))
    return {"total_eur": round(total, 2), "copias": copias, "sem_preco": sem}


def gravar_valor_do_dia(con: sqlite3.Connection, dia: str) -> dict:
    """Calcula o valor de `dia` e grava-o em `n_valor` (substitui o do mesmo
    dia, com o `colecoes_eur`). Devolve o que calculou.

    (R18, 2026-10-29) Sem nenhuma cópia marcada NÃO grava: um dia gravado não
    se recalcula, e um 0 € de antes de ele marcar a primeira carta ficava no
    gráfico para sempre, como uma queda que nunca aconteceu. As cópias das
    coleções contam como marcadas."""
    with posse._transacao(con):
        v = valor_em(con, dia)
        if v["copias"] > 0:
            con.execute(
                "INSERT OR REPLACE INTO n_valor (dia, total_eur, copias,"
                " sem_preco, colecoes_eur) VALUES (?,?,?,?,?)",
                (dia, v["total_eur"], v["copias"], v["sem_preco"],
                 v["colecoes_eur"]))
    return v


def _hoje(hoje: str | None) -> str:
    return hoje or date.today().isoformat()


def serie(con: sqlite3.Connection,
          hoje: str | None = None) -> list[tuple[str, float, int]]:
    """`[(dia, total_eur, sem_preco)]` por ordem: os dias de `n_valor` com
    cópias (o que foi gravado, com o `sem_preco` que tinha), antes do primeiro
    cada dia com preço do Cardmarket no histórico, calculado com o inventário
    de hoje (`valor_em`, com as coleções incluídas), e no fim o valor de `hoje`
    ao vivo. Sem `n_valor` nenhum, são todos os dias do histórico antes de hoje.

    (R18, 2026-10-29) **O último ponto é o número do topo do Painel**: o
    `valor_em()` de agora, no lugar do dia gravado de hoje (o daily grava às
    03:30 e ele marca cartas durante o dia). Um dia gravado com `copias = 0`
    sai: é o daily a correr antes de ele marcar a primeira carta, e no gráfico
    era uma queda a 0 € que nunca aconteceu.

    (R15, 2026-10-28) **Um dia de trás só entra se for comparável com hoje:**
    sai se tiver MAIS cópias sem preço do que hoje (`valor_em()["sem_preco"]`)
    — uma carta que hoje tem preço e nesse dia ainda não tinha. (R9) Só se
    comparam as cópias que não são de coleções em português: o preço PT só
    existe desde que a recolha começou, e sem esta exceção o primeiro Shock PT
    marcado apagava todo o histórico. Uma cópia `pt` só soma nos dias com
    `n_preco_pt` até esse dia e, nos outros, não soma nem conta na comparação.
    O Cardmarket só
    tem histórico (fora a RL) desde ~26/09; sem isto, os dias de agosto valiam
    uma fração do que valem por falta de preços, e o Painel dizia «+261 % num
    mês» com a coleção parada. Os dias gravados ficam sempre: são o que foi
    medido nesse dia.
    """
    hoje = _hoje(hoje)
    gravados = [(r[0], float(r[1] or 0.0), int(r[2] or 0)) for r in con.execute(
        "SELECT dia, total_eur, sem_preco FROM n_valor WHERE copias > 0"
        " AND dia < ? ORDER BY dia", (hoje,))]
    primeiro = gravados[0][0] if gravados else hoje
    dias = [r[0] for r in con.execute(
        "SELECT DISTINCT date FROM price_history WHERE source = 'cardmarket'"
        " AND date < ? ORDER BY date", (primeiro,))]
    inv = _partes(con)
    agora = _valor_de(con, inv, None)
    atras = []
    for d in dias:
        v = _valor_de(con, inv, d)
        if v["sem_preco_cobertura"] <= agora["sem_preco_cobertura"]:
            atras.append((d, v["total_eur"], v["sem_preco"]))
    return atras + gravados + [(hoje, agora["total_eur"], agora["sem_preco"])]


def variacao_mes(con: sqlite3.Connection, hoje: str | None = None) -> dict | None:
    """(R18, 2026-10-29) A variação do topo do Painel: o inventário de HOJE aos
    preços de hoje (`valor_em()`) contra o mesmo inventário aos preços de há
    30 dias (`valor_em(dia)`) → `{delta, pct, desde, hoje}`.

    Se nesse dia havia mais cópias sem preço do que hoje (uma carta que hoje
    tem preço ainda não tinha — o espírito do R15, sem as cópias `pt`: ver
    `serie`), vale o primeiro dia dos
    últimos 30 com a cobertura de hoje (só muda num dia com linha no
    histórico, por isso só esses se perguntam). Sem nenhum, ou sem nada
    marcado, `None` (a página escreve «—»). `pct` é `None` se o ponto de
    partida valia 0.
    """
    hoje = _hoje(hoje)
    inv = _partes(con)
    agora = _valor_de(con, inv, None)
    if not agora["copias"]:
        return None
    alvo = (date.fromisoformat(hoje) - timedelta(days=DIAS_DA_VARIACAO)).isoformat()
    desde, ref = alvo, _valor_de(con, inv, alvo)
    if ref["sem_preco_cobertura"] > agora["sem_preco_cobertura"]:
        desde, ref = None, None
        for (d,) in con.execute(
                "SELECT DISTINCT date FROM price_history WHERE source = 'cardmarket'"
                " AND date > ? AND date < ? ORDER BY date", (alvo, hoje)).fetchall():
            v = _valor_de(con, inv, d)
            if v["sem_preco_cobertura"] <= agora["sem_preco_cobertura"]:
                desde, ref = d, v
                break
        if ref is None:
            return None
    delta = round(agora["total_eur"] - ref["total_eur"], 2)
    pct = round(100 * delta / ref["total_eur"], 1) if ref["total_eur"] else None
    return {"delta": delta, "pct": pct, "desde": desde, "hoje": hoje}


# A janela da série de uma coleção: 100 dias e não 90. A variação a 90 dias do
# mosaico compara hoje com o último ponto ATÉ hoje−90, e a série só tem pontos
# nos dias com dados; com a janela a acabar em hoje−90 esse ponto quase nunca
# existia e a variação saía sempre «sem histórico». (O gráfico continua a mostrar
# 1 mês, 3 meses ou tudo: os 3 meses cortam-se no `visual.grafico`.)
DIAS_DA_SERIE_COLECAO = 100


def serie_colecao(con: sqlite3.Connection, slug: str,
                  hoje: str | None = None) -> list[tuple[str, float, int]]:
    """`[(dia, total_eur, sem_preco)]` de uma coleção nos últimos 100 dias e hoje,
    com o `tenho` de HOJE a preços de cada dia (o que ele tinha em cada dia não
    se guarda; é o gráfico do valor do que tem agora).

    Há um ponto por cada dia com dados de preço das cartas que ele tem: o
    `n_preco_vigiado` e o `price_history` para as inglesas, o `n_preco_pt` para
    as portuguesas (um preço inglês não cria um ponto numa carta `pt`). O preço
    de cada dia é o de `_preco_colecao`; o ponto de `hoje` é o ao vivo. Um dia
    em que NENHUMA cópia tem preço sai: um 0 € seria uma queda que não houve. Sem
    cópias, a lista é vazia."""
    hoje = _hoje(hoje)
    desde = (date.fromisoformat(hoje)
             - timedelta(days=DIAS_DA_SERIE_COLECAO)).isoformat()
    cartas = _cartas_das_colecoes(con, slug)
    dias: set[str] = set()
    for sid, acab, lingua, _ in cartas:
        if lingua == "pt":
            consultas = (("SELECT dia FROM n_preco_pt WHERE scryfall_id = ?"
                          " AND acabamento = ?", (sid, acab)),)
        else:
            consultas = (
                ("SELECT dia FROM n_preco_vigiado WHERE scryfall_id = ?"
                 " AND acabamento = ?", (sid, acab)),
                ("SELECT date FROM price_history WHERE scryfall_id = ? AND"
                 " finish = ? AND source = 'cardmarket'", (sid, acab)))
        for sql, args in consultas:
            dias.update(r[0] for r in con.execute(sql, args)
                        if desde <= r[0] < hoje)
    pontos = []
    for d in sorted(dias) + [hoje]:
        dia = None if d == hoje else d
        total, copias, sem = _somar(
            cartas, lambda sid, acab, ling: _preco_colecao(con, sid, acab, ling, dia))
        if copias > sem:
            pontos.append((d, round(total, 2), sem))
    return pontos


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
    chama `saida_resolver`), o nome e o `slug` do deck de onde saiu e
    `pode_voltar` (se `saida_resolver(..., 'devolver')` a aceitaria). Os totais só somam o
    que tem preço; o que não tem conta em `sem_preco` (em cópias).

    `colecoes` são as cartas de coleção marcadas para vender (`vender = 1` e
    `tenho > 0`), uma linha por carta com a língua, o nome e o `slug` da coleção
    e o preço de `_preco_colecao` (em `pt` o `n_preco_pt`, nunca o inglês), o
    `carta_id` (é com ele que a página tira a marca de vender) e, nas `pt`, o dia
    do último preço visto (`preco_visto_em`). Entram no total e no `sem_preco`
    como as outras.
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
        l["slug"] = r[1]
        # (M5) o botão «Voltar ao deck» só aparece onde a volta é possível
        try:
            _plano_de_volta(con, r[1], r[3], r[4], r[5])
            l["pode_voltar"] = True
        except ValueError:
            l["pode_voltar"] = False
        saidas.append(l)
    from . import cotacoes                                 # noqa: PLC0415
    colecoes = []
    for r in con.execute(
            "SELECT k.scryfall_id, k.acabamento, k.lingua, k.tenho, k.colecao,"
            " o.nome, c.name, c.set_code, k.nome, k.id FROM n_colecao_carta k"
            " JOIN n_colecao o ON o.slug = k.colecao"
            " LEFT JOIN cards c ON c.scryfall_id = k.scryfall_id"
            " WHERE k.vender = 1 AND k.tenho > 0"
            " ORDER BY lower(COALESCE(c.name, k.nome)), k.scryfall_id,"
            " k.acabamento, k.lingua, o.ordem").fetchall():
        l = _linha(r[6] or r[8], r[7], r[0], r[1], r[3],
                   _preco_colecao(con, r[0], r[1], r[2], None), "colecao", None)
        l["lingua"] = r[2]
        l["colecao"] = r[5]
        l["slug"] = r[4]
        l["carta_id"] = r[9]
        # o dia do último preço português visto: a página diz «visto há N dias»
        l["preco_visto_em"] = (cotacoes.preco_pt(con, r[0], r[1])[1]
                               if r[2] == "pt" else None)
        colecoes.append(l)
    total, sem = 0.0, 0
    for l in a_mais + saidas + colecoes:
        if l["preco_un"] is None:
            sem += l["qtd"]
        else:
            total += l["preco_un"] * l["qtd"]
    return {"a_mais": a_mais, "saidas": saidas, "colecoes": colecoes,
            "total_eur": round(total, 2), "sem_preco": sem}


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


def _plano_de_volta(con: sqlite3.Connection, slug: str, scryfall_id: str,
                    acabamento: str, qtd: int) -> tuple[str, str, int]:
    """`(âmbito, nome, quantas cabem)` para devolver uma saída ao deck de onde
    saiu, ou `ValueError` com a razão em português.

    A carta tem de estar na versão ATUAL desse deck; vai para o âmbito dela
    (o deck, ou o monte das partilhadas). A cópia é desta edição: se o âmbito
    já escolheu OUTRA, não entra (ficava marcada numa edição que não conta).
    Só volta o que cabe no que o deck precisa — o resto fica em Vender.
    """
    deck = posse._deck(con, slug)
    r = con.execute("SELECT name FROM cards WHERE scryfall_id = ?",
                    (scryfall_id,)).fetchone()
    if r is None:
        raise ValueError(f"impressão desconhecida: {scryfall_id!r}")
    nome = r[0]
    v = posse._versao(con, slug)
    if v is None or nome not in {l.nome for l in v["linhas"]}:
        raise ValueError(f"{nome} não está na lista atual do {deck['nome']}:"
                         " não há para onde voltar")
    amb = posse.ambito(con, slug, nome)
    escolha = posse._escolha(con, amb, nome)
    if escolha is not None and escolha != (scryfall_id, acabamento):
        raise ValueError(f"o {deck['nome']} conta outra edição de {nome}: escolhe"
                         " esta na carta antes de a devolver")
    if amb == posse.ROT:
        precisa = max(m.get(nome, 0) for m in posse._nomes_rotativos(con).values())
    else:
        precisa = posse._por_nome(v["linhas"])[nome]
    cabe = min(int(qtd), precisa - posse._qtd(con, amb, (scryfall_id, acabamento)))
    if cabe <= 0:
        raise ValueError(f"o {deck['nome']} já tem as {precisa} cópias de {nome}"
                         " marcadas")
    return amb, nome, cabe


def saida_resolver(con: sqlite3.Connection, saida_id: int, destino: str) -> None:
    """Decide o que fazer a uma saída: `'a_mais'` passa as cópias para «tenho a
    mais» (somando ao que lá houver; continuam dele), `'descartar'` apaga a
    linha (vendidas ou foram-se) e `'devolver'` (M5, 2026-10-29) volta a
    pô-las no deck de onde saíram, se a carta estiver na lista atual dele (ver
    `_plano_de_volta`; o que não couber fica na saída). `ValueError` se o id ou
    o destino não existirem, ou se a volta não for possível."""
    if destino not in ("a_mais", "descartar", "devolver"):
        raise ValueError(f"destino inválido: {destino!r} (a_mais | descartar"
                         " | devolver)")
    with posse._transacao(con):
        r = con.execute("SELECT scryfall_id, acabamento, qtd, slug FROM n_saida"
                        " WHERE id = ?", (saida_id,)).fetchone()
        if r is None:
            raise ValueError(f"saída desconhecida: {saida_id!r}")
        if destino == "devolver":
            amb, nome, cabe = _plano_de_volta(con, r[3], r[0], r[1], r[2])
            if posse._escolha(con, amb, nome) is None:
                # sem escolha ainda não há nada marcado: a edição desta cópia
                # passa a ser a que conta (é a que ele tem na mão)
                con.execute("INSERT INTO n_edicao (ambito, nome, scryfall_id,"
                            " acabamento) VALUES (?,?,?,?)", (amb, nome, r[0], r[1]))
            posse._por_qtd(con, amb, r[0], r[1],
                           posse._qtd(con, amb, (r[0], r[1])) + cabe)
            if cabe < r[2]:
                con.execute("UPDATE n_saida SET qtd = qtd - ? WHERE id = ?",
                            (cabe, saida_id))
            else:
                con.execute("DELETE FROM n_saida WHERE id = ?", (saida_id,))
            return
        if destino == "a_mais":
            con.execute(
                "INSERT INTO n_a_mais (scryfall_id, acabamento, qtd, nota)"
                " VALUES (?,?,?,'') ON CONFLICT (scryfall_id, acabamento)"
                " DO UPDATE SET qtd = qtd + excluded.qtd", (r[0], r[1], r[2]))
        con.execute("DELETE FROM n_saida WHERE id = ?", (saida_id,))
