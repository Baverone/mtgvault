"""Os preços do núcleo: o trend do Cardmarket por impressão e acabamento, o valor
de cada dia, a série para trás e a lista de Vender.

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários (`db.session(vault_tmp, catalog_tmp)`), semeia o `catalog.cards` à
mão e escreve preços com o `prices.write_prices` (o mesmo caminho do daily, que
só guarda no histórico as MUDANÇAS).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, prices  # noqa: E402
from mtgvault.nucleo import listas, modelo, posse, valor  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

# (scryfall_id, nome, set, data, finishes)
IMPRESSOES = [
    ("fow-a", "Force of Will", "all", "1996-06-10", ["nonfoil"]),
    ("fow-b", "Force of Will", "ema", "2016-06-10", ["nonfoil", "foil"]),
    ("saga-a", "Urza's Saga", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("tm-a", "Thought Monitor", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("weld-a", "Goblin Welder", "ulg", "1999-02-15", ["nonfoil"]),
    ("wild-a", "Wild Card", "tst", "2020-01-01", ["nonfoil"]),
]

MOD = "modern_affinity"
OSW = "modern_oswald"
LEG = "legacy_welder_cam"
REP = "premodern_replenish"
OATH = "premodern_oath"


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def semear(con):
    for i, (sid, nome, sc, data, fins) in enumerate(IMPRESSOES):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital,
               set_type)
               VALUES (?,?,?,?,'Test Set',?,'en','rare','Artifact',0,'',?,?,?,?,
               'expansion')""",
            (sid, "or-" + nome, nome, sc, str(i), json.dumps(fins), data,
             1000 + i, 0))
    con.commit()
    modelo.garantir_decks(con)


def preco_em(con, sid, acab, dia, trend):
    """Um preço do Cardmarket em `dia` (cronologicamente: o write_prices deixa
    o `price_latest` com a última linha escrita)."""
    prices.write_prices(con, [(sid, "cardmarket", dia, acab, trend, trend,
                               trend, None, "EUR")])


def versao(con, slug, linhas):
    return listas.gravar_versao(con, slug, [Linha(*l) for l in linhas],
                                fonte="teste", origem="andre")


def posse_directa(con, ambito, sid, acab, qtd):
    con.execute("INSERT INTO n_posse (ambito, scryfall_id, acabamento, qtd)"
                " VALUES (?,?,?,?)", (ambito, sid, acab, qtd))
    con.commit()


def tres(v):
    """Os três números de sempre de um `valor_em`/`gravar_valor_do_dia`, sem as
    partes (`decks_eur`, `a_mais_eur`, `colecoes_eur`) que a Tarefa 4 acrescentou."""
    return {k: v[k] for k in ("total_eur", "copias", "sem_preco")}


def esperar_valueerror(f, *args, **kw):
    try:
        f(*args, **kw)
    except ValueError:
        return
    raise AssertionError(f"devia levantar ValueError: {f.__name__}{args}")


# ---------------------------------------------------------------------------
def caso_preco_pelo_dia():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-09-26", 10.0)
        preco_em(con, "fow-a", "nonfoil", "2026-09-30", 12.0)
        assert valor.preco(con, "fow-a", "nonfoil", "2026-09-28") == 10.0
        assert valor.preco(con, "fow-a", "nonfoil", "2026-09-26") == 10.0
        assert valor.preco(con, "fow-a", "nonfoil", "2026-09-30") == 12.0
        assert valor.preco(con, "fow-a", "nonfoil", "2026-12-01") == 12.0
        # antes do primeiro registo não há preço (nunca 0)
        assert valor.preco(con, "fow-a", "nonfoil", "2026-09-25") is None
        # sem dia: o `price_latest`
        assert valor.preco(con, "fow-a", "nonfoil") == 12.0
        # sem linha nenhuma
        assert valor.preco(con, "fow-b", "nonfoil") is None
        assert valor.preco(con, "fow-b", "nonfoil", "2026-09-28") is None
        # só o Cardmarket conta
        prices.write_prices(con, [("weld-a", "cardtrader", "2026-09-28",
                                   "nonfoil", 9.0, 9.0, None, None, "EUR")])
        assert valor.preco(con, "weld-a", "nonfoil") is None
        assert valor.preco(con, "weld-a", "nonfoil", "2026-09-28") is None


def so_no_latest(con, sid, acab, trend, dia="2026-10-28"):
    """Um preço que só existe no `price_latest`: estável desde antes da janela
    que o daily poda, por isso sem nenhuma linha em `price_history`."""
    con.execute(
        "INSERT INTO price_latest (scryfall_id, source, finish, date, low, trend)"
        " VALUES (?, 'cardmarket', ?, ?, ?, ?)", (sid, acab, dia, trend, trend))
    con.commit()


def caso_preco_podado_vale_o_latest():
    with sessao() as con:
        semear(con)
        # (R13) só no `price_latest`, histórico vazio: vale em qualquer dia
        so_no_latest(con, "fow-a", "nonfoil", 80.0)
        assert con.execute("SELECT count(*) FROM price_history"
                           " WHERE scryfall_id = 'fow-a'").fetchone()[0] == 0
        assert valor.preco(con, "fow-a", "nonfoil", "2026-08-01") == 80.0
        assert valor.preco(con, "fow-a", "nonfoil", "2026-10-15") == 80.0
        assert valor.preco(con, "fow-a", "nonfoil") == 80.0
        posse_directa(con, MOD, "fow-a", "nonfoil", 2)
        r = valor.gravar_valor_do_dia(con, "2026-10-15")
        assert tres(r) == {"total_eur": 160.0, "copias": 2, "sem_preco": 0}, r
        # (R18) o dia gravado e, no fim, o valor de hoje ao vivo
        assert valor.serie(con, hoje="2026-10-16") == [
            ("2026-10-15", 160.0, 0), ("2026-10-16", 160.0, 0)]
        # histórico SÓ depois do dia (+ latest): o preço ainda não existia
        so_no_latest(con, "saga-a", "nonfoil", 30.0)
        con.execute("INSERT INTO price_history (scryfall_id, source, date,"
                    " finish, low, trend) VALUES ('saga-a', 'cardmarket',"
                    " '2026-10-20', 'nonfoil', 30.0, 30.0)")
        con.commit()
        assert valor.preco(con, "saga-a", "nonfoil", "2026-10-19") is None
        assert valor.preco(con, "saga-a", "nonfoil", "2026-10-20") == 30.0
        # uma linha de histórico antes do dia ganha ao latest
        so_no_latest(con, "weld-a", "nonfoil", 9.0)
        con.execute("INSERT INTO price_history (scryfall_id, source, date,"
                    " finish, low, trend) VALUES ('weld-a', 'cardmarket',"
                    " '2026-10-01', 'nonfoil', 5.0, 5.0)")
        con.commit()
        assert valor.preco(con, "weld-a", "nonfoil", "2026-10-10") == 5.0
        assert valor.preco(con, "weld-a", "nonfoil") == 9.0
        # trend <= 0 no latest não é preço
        so_no_latest(con, "tm-a", "nonfoil", 0.0)
        assert valor.preco(con, "tm-a", "nonfoil", "2026-10-10") is None


def caso_acabamento_sem_preco_conta_como_sem_preco():
    """Só existe o preço do outro acabamento: não se empresta (nonfoil sem
    preço não vale o do foil, nem ao contrário)."""
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-b", "foil", "2026-10-01", 150.0)       # só o foil
        preco_em(con, "saga-a", "nonfoil", "2026-10-01", 30.0)    # só o nonfoil
        posse_directa(con, MOD, "fow-b", "nonfoil", 1)
        posse_directa(con, MOD, "saga-a", "foil", 2)
        posse_directa(con, MOD, "tm-a", "nonfoil", 1)              # sem nada
        assert valor.preco(con, "fow-b", "nonfoil") is None
        assert valor.preco(con, "saga-a", "foil", "2026-10-01") is None
        v = valor.valor_em(con)
        assert tres(v) == {"total_eur": 0.0, "copias": 4, "sem_preco": 4}, v
        valor.a_mais_ajustar(con, "fow-b", "nonfoil", 1)
        valor.a_mais_ajustar(con, "saga-a", "foil", 1)
        preco_em(con, "tm-a", "nonfoil", "2026-10-01", 2.0)
        valor.a_mais_ajustar(con, "tm-a", "nonfoil", 3)
        r = valor.a_vender(con)
        assert r["sem_preco"] == 2 and r["total_eur"] == 6.0, r
        assert {l["preco_un"] for l in r["a_mais"]} == {None, 2.0}


def caso_trend_zero_nao_e_preco():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-09-26", 10.0)
        preco_em(con, "fow-a", "nonfoil", "2026-10-05", 0.0)
        # a linha mais recente manda: um 0 depois de um preço não volta ao 10
        assert valor.preco(con, "fow-a", "nonfoil", "2026-10-06") is None
        assert valor.preco(con, "fow-a", "nonfoil") is None
        assert valor.preco(con, "fow-a", "nonfoil", "2026-10-01") == 10.0


def caso_foil_separado():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-b", "nonfoil", "2026-10-01", 1.0)
        preco_em(con, "fow-b", "foil", "2026-10-01", 5.0)
        assert valor.preco(con, "fow-b", "nonfoil") == 1.0
        assert valor.preco(con, "fow-b", "foil") == 5.0
        assert valor.preco(con, "fow-b", "nonfoil", "2026-10-01") == 1.0
        assert valor.preco(con, "fow-b", "foil", "2026-10-01") == 5.0
        posse_directa(con, "x", "fow-b", "nonfoil", 1)
        posse_directa(con, "x", "fow-b", "foil", 1)
        # as duas impressões somam cada uma ao seu preço
        v = valor.valor_em(con)
        assert tres(v) == {"total_eur": 6.0, "copias": 2, "sem_preco": 0}, v


def caso_sem_preco_fora_do_total():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 80.0)
        posse_directa(con, MOD, "fow-a", "nonfoil", 1)
        posse_directa(con, MOD, "weld-a", "nonfoil", 1)       # sem preço
        v = valor.valor_em(con)
        assert v["total_eur"] == 80.0, v                      # o sem preço não soma 0
        assert v["sem_preco"] == 1 and v["copias"] == 2, v
        # num dia em que ainda não havia preço de nenhuma, tudo é «sem preço»
        v0 = valor.valor_em(con, "2026-09-01")
        assert tres(v0) == {"total_eur": 0.0, "copias": 2, "sem_preco": 2}, v0


def caso_cada_copia_uma_vez():
    with sessao() as con:
        semear(con)
        preco_em(con, "saga-a", "nonfoil", "2026-10-01", 30.0)
        # a mesma carta nos dois rotativos: as cópias são um monte só (ROT)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        versao(con, OSW, [("main", "Urza's Saga", 2)])
        assert posse.partilhadas(con) == {"Urza's Saga"}
        posse.ajustar(con, MOD, "Urza's Saga", 3, request_id="r1")
        inv = valor.inventario(con)
        assert inv == [("saga-a", "nonfoil", 3)], inv
        v = valor.valor_em(con)
        assert tres(v) == {"total_eur": 90.0, "copias": 3, "sem_preco": 0}, v


def caso_inventario_soma_tudo():
    """n_posse (todos os âmbitos) + n_a_mais + n_saida: uma cópia é uma cópia
    até ele a resolver."""
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        posse_directa(con, REP, "fow-b", "nonfoil", 2)
        posse_directa(con, OATH, "fow-b", "nonfoil", 1)
        posse_directa(con, "rotativos", "saga-a", "foil", 2)
        con.execute("INSERT INTO n_a_mais (scryfall_id, acabamento, qtd, nota)"
                    " VALUES ('fow-b', 'nonfoil', 3, '')")
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'saiu_da_lista', NULL,"
                    " 'fow-b', 'nonfoil', 4, '2026-10-28T10:00:00')", (REP,))
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'trocou_edicao', NULL,"
                    " 'tm-a', 'foil', 1, '2026-10-28T10:00:00')", (REP,))
        con.commit()
        inv = valor.inventario(con)
        assert inv == [("fow-b", "nonfoil", 2 + 1 + 3 + 4),
                       ("saga-a", "foil", 2),
                       ("tm-a", "foil", 1)], inv


def caso_serie_preenche_para_tras():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 10.0)
        preco_em(con, "fow-a", "nonfoil", "2026-10-02", 20.0)
        preco_em(con, "fow-a", "nonfoil", "2026-10-03", 30.0)
        posse_directa(con, MOD, "fow-a", "nonfoil", 2)
        # sem n_valor nenhum: os dias de trás com preço, calculados, e (R18)
        # o valor de hoje ao vivo no fim
        assert valor.serie(con, hoje="2026-10-04") == [
            ("2026-10-01", 20.0, 0), ("2026-10-02", 40.0, 0),
            ("2026-10-03", 60.0, 0), ("2026-10-04", 60.0, 0)]
        # o dia do histórico que é HOJE não se repete: vale o ao vivo
        assert valor.serie(con, hoje="2026-10-03") == [
            ("2026-10-01", 20.0, 0), ("2026-10-02", 40.0, 0),
            ("2026-10-03", 60.0, 0)]
        r = valor.gravar_valor_do_dia(con, "2026-10-03")
        assert tres(r) == {"total_eur": 60.0, "copias": 2, "sem_preco": 0}, r
        # um dia gravado vale o que foi gravado (o valor desse dia, por mais
        # que o preço de hoje mude depois), e não se recalcula
        preco_em(con, "fow-a", "nonfoil", "2026-10-04", 100.0)
        s = valor.serie(con, hoje="2026-10-05")
        assert s == [("2026-10-01", 20.0, 0), ("2026-10-02", 40.0, 0),
                     ("2026-10-03", 60.0, 0), ("2026-10-05", 200.0, 0)], s
        valor.gravar_valor_do_dia(con, "2026-10-04")
        s = valor.serie(con, hoje="2026-10-05")
        assert s == [("2026-10-01", 20.0, 0), ("2026-10-02", 40.0, 0),
                     ("2026-10-03", 60.0, 0), ("2026-10-04", 200.0, 0),
                     ("2026-10-05", 200.0, 0)], s
        # o dia gravado de HOJE é trocado pelo valor ao vivo (o preço mudou
        # depois do daily): o último ponto é sempre o número do topo do Painel
        preco_em(con, "fow-a", "nonfoil", "2026-10-05", 50.0)
        s = valor.serie(con, hoje="2026-10-04")
        assert s[-1] == ("2026-10-04", 100.0, 0) and len(s) == 4, s
        assert s[-1][1] == valor.valor_em(con)["total_eur"]
        # nunca duas vezes o mesmo dia, e sempre por ordem
        assert [d for d, _v, _s in s] == sorted({d for d, _v, _s in s})


def caso_serie_larga_dias_sem_a_cobertura_de_hoje():
    """(R15) Um dia calculado para trás em que uma carta que HOJE tem preço
    ainda não tinha não é comparável: valia menos só porque faltava uma carta
    na soma. Sai da série. Os dias gravados (`n_valor`) com cópias ficam
    sempre, com o `sem_preco` que tinham."""
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-09-01", 10.0)
        preco_em(con, "fow-a", "nonfoil", "2026-09-20", 11.0)
        # a Saga só tem preço a partir de 26/09 (o Cardmarket sem histórico)
        preco_em(con, "saga-a", "nonfoil", "2026-09-26", 30.0)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 12.0)
        posse_directa(con, MOD, "fow-a", "nonfoil", 1)
        posse_directa(con, MOD, "saga-a", "nonfoil", 1)
        # o Goblin Welder nunca teve preço: falta hoje e faltava antes
        posse_directa(con, LEG, "weld-a", "nonfoil", 1)
        assert valor.valor_em(con)["sem_preco"] == 1
        s = valor.serie(con, hoje="2026-10-02")
        # 01/09 e 20/09 tinham a Saga sem preço (2 > 1): saem
        assert s == [("2026-09-26", 41.0, 1), ("2026-10-01", 42.0, 1),
                     ("2026-10-02", 42.0, 1)], s
        # um dia gravado fica, mesmo com mais cartas sem preço do que hoje
        con.execute("INSERT INTO n_valor (dia, total_eur, copias, sem_preco)"
                    " VALUES ('2026-10-02', 12.0, 3, 2)")
        con.commit()
        s = valor.serie(con, hoje="2026-10-03")
        assert s[-2:] == [("2026-10-02", 12.0, 2), ("2026-10-03", 42.0, 1)], s
        assert [d for d, *_ in s] == ["2026-09-26", "2026-10-01", "2026-10-02",
                                      "2026-10-03"], s


def caso_serie_larga_dias_gravados_vazios():
    """(R18, C1) Um dia gravado sem cópias nenhumas (o daily antes de ele
    marcar a primeira carta) não é um valor de 0 €: sai da série. Era ele que
    fazia o Painel dizer «−100 %» e o gráfico cair a 0 no primeiro dia."""
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 10.0)
        con.execute("INSERT INTO n_valor (dia, total_eur, copias, sem_preco)"
                    " VALUES ('2026-10-02', 0.0, 0, 0)")
        con.commit()
        posse_directa(con, MOD, "fow-a", "nonfoil", 3)
        s = valor.serie(con, hoje="2026-10-03")
        assert s == [("2026-10-01", 30.0, 0), ("2026-10-03", 30.0, 0)], s
        assert all(t > 0 for _d, t, _s in s), s


def caso_gravar_valor_dia_vazio_nao_grava():
    """(R18) Sem nada marcado não se grava o dia: um 0 € gravado ficava na
    série para sempre (um dia gravado não se recalcula)."""
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 10.0)
        r = valor.gravar_valor_do_dia(con, "2026-10-01")
        assert tres(r) == {"total_eur": 0.0, "copias": 0, "sem_preco": 0}, r
        assert con.execute("SELECT count(*) FROM n_valor").fetchone()[0] == 0
        posse_directa(con, MOD, "fow-a", "nonfoil", 1)
        valor.gravar_valor_do_dia(con, "2026-10-02")
        assert [tuple(x) for x in con.execute(
            "SELECT dia, total_eur, copias FROM n_valor")] == [
            ("2026-10-02", 10.0, 1)]


def caso_variacao_do_mes_ao_inventario_de_hoje():
    """(R18) A variação do topo do Painel: o que ele tem HOJE aos preços de
    hoje contra o MESMO inventário aos preços de há 30 dias — nunca contra um
    dia gravado com outro inventário. Se nesse dia faltavam preços a cartas que
    hoje os têm, o primeiro dia dos últimos 30 com a cobertura de hoje (R15);
    sem nenhum, «—» (`None`)."""
    hoje = "2026-10-29"
    with sessao() as con:
        semear(con)
        assert valor.variacao_mes(con, hoje=hoje) is None      # nada marcado
        preco_em(con, "fow-a", "nonfoil", "2026-09-01", 10.0)
        preco_em(con, "fow-a", "nonfoil", "2026-10-20", 12.0)
        posse_directa(con, MOD, "fow-a", "nonfoil", 2)
        # um dia gravado com outro inventário não entra na conta
        con.execute("INSERT INTO n_valor (dia, total_eur, copias, sem_preco)"
                    " VALUES ('2026-09-29', 1.0, 1, 0)")
        con.commit()
        v = valor.variacao_mes(con, hoje=hoje)
        assert v == {"delta": 4.0, "pct": 20.0, "desde": "2026-09-29",
                     "hoje": hoje}, v
        # a Saga só tem preço desde 10/10: a 29/09 não é comparável
        preco_em(con, "saga-a", "nonfoil", "2026-10-10", 30.0)
        posse_directa(con, MOD, "saga-a", "nonfoil", 1)
        v = valor.variacao_mes(con, hoje=hoje)
        assert v == {"delta": 4.0, "pct": 8.0, "desde": "2026-10-10",
                     "hoje": hoje}, v
        # uma carta com preço só de hoje: nenhum dia dos últimos 30 é
        # comparável, e não há variação
        preco_em(con, "tm-a", "nonfoil", hoje, 2.0)
        posse_directa(con, MOD, "tm-a", "nonfoil", 1)
        assert valor.variacao_mes(con, hoje=hoje) is None


def caso_gravar_valor_substitui_o_dia():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 10.0)
        posse_directa(con, MOD, "fow-a", "nonfoil", 1)
        posse_directa(con, MOD, "weld-a", "nonfoil", 1)
        r1 = valor.gravar_valor_do_dia(con, "2026-10-01")
        assert tres(r1) == {"total_eur": 10.0, "copias": 2, "sem_preco": 1}, r1
        posse_directa(con, OATH, "fow-a", "nonfoil", 1)
        valor.gravar_valor_do_dia(con, "2026-10-01")
        linhas = [tuple(r) for r in con.execute(
            "SELECT dia, total_eur, copias, sem_preco FROM n_valor")]
        assert linhas == [("2026-10-01", 20.0, 3, 1)], linhas


def caso_a_mais_ajustar():
    with sessao() as con:
        semear(con)
        assert valor.a_mais_ajustar(con, "fow-b", "foil", 2, nota="troca") == 2
        assert valor.a_mais_ajustar(con, "fow-b", "foil", 1) == 3
        r = con.execute("SELECT qtd, nota FROM n_a_mais").fetchall()
        assert [tuple(x) for x in r] == [(3, "troca")]        # a nota fica
        assert valor.a_mais_ajustar(con, "fow-b", "foil", 0, nota="outra") == 3
        assert con.execute("SELECT nota FROM n_a_mais").fetchone()[0] == "outra"
        # nunca abaixo de 0, e a linha desaparece no 0
        assert valor.a_mais_ajustar(con, "fow-b", "foil", -10) == 0
        assert con.execute("SELECT count(*) FROM n_a_mais").fetchone()[0] == 0
        assert valor.a_mais_ajustar(con, "fow-b", "foil", -1) == 0
        assert con.execute("SELECT count(*) FROM n_a_mais").fetchone()[0] == 0
        # a impressão tem de existir e ter esse acabamento
        esperar_valueerror(valor.a_mais_ajustar, con, "nao-existe", "nonfoil", 1)
        esperar_valueerror(valor.a_mais_ajustar, con, "fow-a", "foil", 1)
        esperar_valueerror(valor.a_mais_ajustar, con, "fow-a", "etched", 1)
        assert con.execute("SELECT count(*) FROM n_a_mais").fetchone()[0] == 0


def caso_saida_para_a_mais():
    with sessao() as con:
        semear(con)
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'saiu_da_lista', NULL,"
                    " 'fow-b', 'nonfoil', 2, '2026-10-28T10:00:00')", (REP,))
        sid1 = con.execute("SELECT max(id) FROM n_saida").fetchone()[0]
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'trocou_edicao', NULL,"
                    " 'fow-b', 'nonfoil', 1, '2026-10-28T10:00:00')", (OATH,))
        sid2 = con.execute("SELECT max(id) FROM n_saida").fetchone()[0]
        con.commit()
        valor.a_mais_ajustar(con, "fow-b", "nonfoil", 1, nota="minha")
        antes = valor.inventario(con)
        assert antes == [("fow-b", "nonfoil", 4)], antes
        # para «tenho a mais»: soma ao que lá estava, e a saída desaparece
        valor.saida_resolver(con, sid1, "a_mais")
        assert [r[0] for r in con.execute("SELECT id FROM n_saida")] == [sid2]
        r = con.execute("SELECT qtd, nota FROM n_a_mais"
                        " WHERE scryfall_id = 'fow-b'").fetchone()
        assert r[0] == 3 and r[1] == "minha", tuple(r)
        # a cópia continua dele: o inventário não mexeu
        assert valor.inventario(con) == antes
        # descartar = vendida/foi-se: sai da base e do inventário
        valor.saida_resolver(con, sid2, "descartar")
        assert con.execute("SELECT count(*) FROM n_saida").fetchone()[0] == 0
        assert valor.inventario(con) == [("fow-b", "nonfoil", 3)]
        # ids e destinos desconhecidos
        esperar_valueerror(valor.saida_resolver, con, 9999, "a_mais")
        esperar_valueerror(valor.saida_resolver, con, 9999, "descartar")
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'saiu_da_lista', NULL,"
                    " 'fow-b', 'nonfoil', 1, '2026-10-28T10:00:00')", (REP,))
        novo = con.execute("SELECT max(id) FROM n_saida").fetchone()[0]
        con.commit()
        esperar_valueerror(valor.saida_resolver, con, novo, "vender")
        assert con.execute("SELECT count(*) FROM n_saida").fetchone()[0] == 1


def caso_a_vender():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-b", "nonfoil", "2026-10-01", 70.0)
        preco_em(con, "fow-b", "foil", "2026-10-01", 150.0)
        preco_em(con, "saga-a", "nonfoil", "2026-10-01", 30.0)
        valor.a_mais_ajustar(con, "saga-a", "nonfoil", 2)
        valor.a_mais_ajustar(con, "weld-a", "nonfoil", 1)      # sem preço
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'saiu_da_lista', NULL,"
                    " 'fow-b', 'foil', 1, '2026-10-28T10:00:00')", (MOD,))
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'trocou_edicao', NULL,"
                    " 'fow-b', 'nonfoil', 2, '2026-10-28T10:00:00')", (REP,))
        con.commit()
        r = valor.a_vender(con)
        assert set(r) == {"a_mais", "saidas", "total_eur", "sem_preco"}, r
        mais = {l["scryfall_id"]: l for l in r["a_mais"]}
        assert mais["saga-a"]["nome"] == "Urza's Saga"
        assert mais["saga-a"]["set_code"] == "mh2"
        assert mais["saga-a"]["motivo"] == "a_mais"
        assert mais["saga-a"]["deck"] is None
        assert mais["saga-a"]["preco_un"] == 30.0 and mais["saga-a"]["qtd"] == 2
        assert mais["weld-a"]["preco_un"] is None
        assert len(r["saidas"]) == 2
        por_motivo = {l["motivo"]: l for l in r["saidas"]}
        a = por_motivo["saiu_da_lista"]
        assert a["acabamento"] == "foil" and a["preco_un"] == 150.0
        assert a["deck"] == con.execute("SELECT nome FROM n_deck WHERE slug = ?",
                                        (MOD,)).fetchone()[0]
        assert isinstance(a["id"], int)
        b = por_motivo["trocou_edicao"]
        assert b["qtd"] == 2 and b["preco_un"] == 70.0
        assert b["deck"] == con.execute("SELECT nome FROM n_deck WHERE slug = ?",
                                        (REP,)).fetchone()[0]
        # 2×30 + 1×150 + 2×70; a Goblin Welder sem preço fica de fora e conta
        assert r["total_eur"] == 350.0, r
        assert r["sem_preco"] == 1, r
        # a lista de Vender não mexe no que é dele
        assert sum(q for _s, _a, q in valor.inventario(con)) == 6


def caso_cards_of_interest_inclui_nucleo():
    with sessao() as con:
        semear(con)
        # mais uma impressão digital: essa não interessa
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
               set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital,
               set_type)
               VALUES ('fow-dig','or-Force of Will','Force of Will','vma','V','9',
               'en','rare','Instant',0,'','["nonfoil"]','2014-06-16',2000,1,
               'masters')""")
        con.commit()
        antes = prices.cards_of_interest(con)
        assert not antes & {"fow-a", "fow-b", "saga-a", "tm-a", "weld-a"}, antes
        # uma carta numa versão atual: todas as impressões em papel entram
        versao(con, MOD, [("main", "Force of Will", 4)])
        ids = prices.cards_of_interest(con)
        assert {"fow-a", "fow-b"} <= ids and "fow-dig" not in ids, ids
        # só a versão ATUAL conta
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        ids = prices.cards_of_interest(con)
        assert {"saga-a"} <= ids and not ids & {"fow-a", "fow-b"}, ids
        # a posse, o «a mais», as saídas e as edições escolhidas, tal e qual
        posse_directa(con, "x", "weld-a", "nonfoil", 1)
        con.execute("INSERT INTO n_a_mais (scryfall_id, acabamento, qtd, nota)"
                    " VALUES ('tm-a', 'foil', 1, '')")
        con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                    " acabamento, qtd, em) VALUES (?, 'saiu_da_lista', NULL,"
                    " 'wild-a', 'nonfoil', 1, '2026-10-28T10:00:00')", (MOD,))
        con.execute("INSERT INTO n_edicao (ambito, nome, scryfall_id, acabamento)"
                    " VALUES ('x', 'Force of Will', 'fow-dig', 'nonfoil')")
        con.commit()
        ids = prices.cards_of_interest(con)
        assert {"weld-a", "tm-a", "wild-a", "fow-dig"} <= ids, ids


def caso_so_escreve_tabelas_n():
    with sessao() as con:
        semear(con)
        preco_em(con, "fow-a", "nonfoil", "2026-10-01", 10.0)
        tabelas = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'n\\_%' ESCAPE '\\' AND name NOT LIKE 'sqlite%'")]
        antes = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                 for t in tabelas}
        valor.a_mais_ajustar(con, "fow-a", "nonfoil", 2)
        valor.gravar_valor_do_dia(con, "2026-10-01")
        valor.serie(con)
        valor.a_vender(con)
        depois = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in tabelas}
        assert antes == depois


def caso_saida_voltar_ao_deck():
    """(M5) `destino='devolver'`: a cópia que saiu volta ao âmbito de onde
    veio quando a carta está na versão atual desse deck (ValueError se não).
    Só volta o que o deck precisa; o resto fica na saída."""
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        assert posse.ajustar(con, REP, "Force of Will", 4, request_id="v1") == 4
        ed = posse.edicao(con, REP, "Force of Will")
        versao(con, REP, [("main", "Goblin Welder", 4)])            # a FoW sai
        s1 = con.execute("SELECT id, qtd FROM n_saida").fetchall()
        assert [tuple(x)[1:] for x in s1] == [(4,)], [tuple(x) for x in s1]
        sid = s1[0][0]
        # fora da lista: não há para onde voltar
        esperar_valueerror(valor.saida_resolver, con, sid, "devolver")
        assert [l["pode_voltar"] for l in valor.a_vender(con)["saidas"]] == [False]
        versao(con, REP, [("main", "Force of Will", 4), ("main", "Goblin Welder", 4)])
        assert posse.ajustar(con, REP, "Force of Will", 3, request_id="v2") == 3
        assert valor.a_vender(con)["saidas"][0]["pode_voltar"] is True
        assert valor.a_vender(con)["saidas"][0]["slug"] == REP
        # cabe 1 (o deck pede 4, tem 3): volta 1, ficam 3 na saída
        antes = valor.inventario(con)
        valor.saida_resolver(con, sid, "devolver")
        assert posse.estado_deck(con, REP)["cartas"][0]["tenho"] == 4
        assert con.execute("SELECT qtd FROM n_saida WHERE id = ?", (sid,)).fetchone()[0] == 3
        assert valor.inventario(con) == antes                # a cópia continua dele
        # o deck já está completo: não volta mais nenhuma
        esperar_valueerror(valor.saida_resolver, con, sid, "devolver")
        assert valor.a_vender(con)["saidas"][0]["pode_voltar"] is False
        # outra edição escolhida no deck: a cópia não entra numa que não conta
        outra = "fow-b" if ed[0] == "fow-a" else "fow-a"
        posse.escolher_edicao(con, REP, "Force of Will", outra, "nonfoil")
        esperar_valueerror(valor.saida_resolver, con, sid, "devolver")
    print("saída: voltar ao deck")


# ---------------------------------------------------------------------------
# Tarefa 4: o valor com as coleções
# ---------------------------------------------------------------------------
from test_nucleo_colecoes import _sid, semear as semear_colecoes  # noqa: E402
from mtgvault.nucleo import colecoes  # noqa: E402

HOJE = "2026-10-30"


def ha(n):
    from datetime import date, timedelta
    return (date.fromisoformat(HOJE) - timedelta(days=n)).isoformat()


_rid = [0]


def com_colecoes(con):
    """O catálogo dos decks (valor) mais o das três coleções fechadas, e as
    coleções criadas."""
    semear(con)
    semear_colecoes(con)
    colecoes.garantir_colecoes(con)


def marcar(con, slug, nome, qtd):
    """Põe `qtd` cópias na carta `nome` da coleção `slug`."""
    _rid[0] += 1
    carta = con.execute("SELECT id FROM n_colecao_carta WHERE colecao = ? AND"
                        " nome = ?", (slug, nome)).fetchone()["id"]
    return colecoes.ajustar(con, carta, qtd, request_id=f"v4-{_rid[0]}")


def pt_em(con, sid, acab, dia, eur):
    con.execute("INSERT OR REPLACE INTO n_preco_pt (scryfall_id, acabamento, dia,"
                " preco_eur, ofertas) VALUES (?,?,?,?,1)", (sid, acab, dia, eur))
    con.commit()


def vigiado_em(con, sid, acab, dia, eur):
    con.execute("INSERT OR REPLACE INTO n_preco_vigiado (scryfall_id, acabamento,"
                " dia, preco_eur) VALUES (?,?,?,?)", (sid, acab, dia, eur))
    con.commit()


def caso_valor_com_colecoes():
    """Decks 10 €, coleção 2 duals a 300 € → total 610, colecoes_eur 600; as
    três partes somam o total e as cópias da coleção contam em `copias`."""
    with sessao() as con:
        com_colecoes(con)
        preco_em(con, "tm-a", "nonfoil", HOJE, 10.0)
        posse_directa(con, MOD, "tm-a", "nonfoil", 1)
        tundra = _sid("Tundra", "3ed")
        preco_em(con, tundra, "nonfoil", HOJE, 300.0)
        assert marcar(con, "duals_revised", "Tundra", 2) == 2
        v = valor.valor_em(con)
        assert v["total_eur"] == 610.0, v
        assert v["colecoes_eur"] == 600.0, v
        assert v["decks_eur"] == 10.0 and v["a_mais_eur"] == 0.0, v
        assert v["copias"] == 3 and v["sem_preco"] == 0, v
        assert valor.valor_colecoes(con) == {
            "total_eur": 600.0, "copias": 2, "sem_preco": 0}
        # o «tenho a mais» e a saída são a parte a_mais
        con.execute("INSERT INTO n_a_mais (scryfall_id, acabamento, qtd, nota)"
                    " VALUES ('tm-a','nonfoil',2,'')")
        con.commit()
        v = valor.valor_em(con)
        assert (v["decks_eur"], v["a_mais_eur"], v["colecoes_eur"]) == (10.0, 20.0, 600.0), v
        assert v["total_eur"] == 630.0 and v["copias"] == 5, v


def caso_valor_sem_colecoes_igual_a_antes():
    """Sem nada nas coleções, o total, as cópias e o sem_preco são os de sempre."""
    with sessao() as con:
        com_colecoes(con)
        preco_em(con, "tm-a", "nonfoil", HOJE, 10.0)
        posse_directa(con, MOD, "tm-a", "nonfoil", 2)
        posse_directa(con, OSW, "weld-a", "nonfoil", 1)         # sem preço
        v = valor.valor_em(con)
        assert (v["total_eur"], v["copias"], v["sem_preco"]) == (20.0, 3, 1), v
        assert v["colecoes_eur"] == 0.0 and v["decks_eur"] == 20.0, v
        assert valor.valor_colecoes(con) == {
            "total_eur": 0.0, "copias": 0, "sem_preco": 0}


def caso_valor_colecao_pt_sem_ingles():
    """Um shock PT sem ofertas PT, com trend inglês: conta em `sem_preco` e vale
    0 € no total (nunca o preço inglês). Com um preço PT, conta; e a um dia
    anterior ao primeiro avistamento PT volta a ser «sem preço»."""
    with sessao() as con:
        com_colecoes(con)
        vents = _sid("Steam Vents", "gpt")
        preco_em(con, vents, "nonfoil", HOJE, 50.0)             # o trend `en`
        marcar(con, "shocks_pt", "Steam Vents", 1)
        v = valor.valor_em(con)
        assert v["colecoes_eur"] == 0.0 and v["total_eur"] == 0.0, v
        assert v["copias"] == 1 and v["sem_preco"] == 1, v
        pt_em(con, vents, "nonfoil", ha(5), 80.0)
        v = valor.valor_em(con)
        assert (v["colecoes_eur"], v["total_eur"], v["sem_preco"]) == (80.0, 80.0, 0), v
        # o preço PT de um dia: o mais recente até esse dia; antes, nenhum
        assert valor.valor_colecoes(con, ha(2)) == {
            "total_eur": 80.0, "copias": 1, "sem_preco": 0}
        assert valor.valor_colecoes(con, ha(10)) == {
            "total_eur": 0.0, "copias": 1, "sem_preco": 1}


def caso_gravar_valor_colecoes_eur():
    with sessao() as con:
        com_colecoes(con)
        preco_em(con, "tm-a", "nonfoil", ha(1), 10.0)
        posse_directa(con, MOD, "tm-a", "nonfoil", 1)
        tundra = _sid("Tundra", "3ed")
        preco_em(con, tundra, "nonfoil", ha(1), 300.0)
        marcar(con, "duals_revised", "Tundra", 2)
        r = valor.gravar_valor_do_dia(con, ha(1))
        assert r["total_eur"] == 610.0 and r["colecoes_eur"] == 600.0, r
        linha = con.execute("SELECT total_eur, copias, sem_preco, colecoes_eur"
                            " FROM n_valor WHERE dia = ?", (ha(1),)).fetchone()
        assert tuple(linha) == (610.0, 3, 0, 600.0), tuple(linha)


def caso_gravar_valor_so_colecoes():
    """Só coleções (sem decks) já tem cópias: grava; sem nada, não grava."""
    with sessao() as con:
        com_colecoes(con)
        assert valor.gravar_valor_do_dia(con, ha(2))["copias"] == 0
        assert con.execute("SELECT COUNT(*) FROM n_valor").fetchone()[0] == 0
        tundra = _sid("Tundra", "3ed")
        preco_em(con, tundra, "nonfoil", ha(1), 300.0)
        marcar(con, "duals_revised", "Tundra", 1)
        valor.gravar_valor_do_dia(con, ha(1))
        assert tuple(con.execute("SELECT total_eur, copias, colecoes_eur FROM"
                                 " n_valor").fetchone()) == (300.0, 1, 300.0)


def caso_serie_inclui_colecoes_atras():
    """Os dias de trás da série somam as coleções aos preços desse dia."""
    with sessao() as con:
        com_colecoes(con)
        tundra = _sid("Tundra", "3ed")
        preco_em(con, tundra, "nonfoil", ha(3), 100.0)
        preco_em(con, tundra, "nonfoil", ha(1), 120.0)
        preco_em(con, "tm-a", "nonfoil", ha(3), 10.0)
        posse_directa(con, MOD, "tm-a", "nonfoil", 1)
        marcar(con, "duals_revised", "Tundra", 2)
        assert valor.serie(con, HOJE) == [
            (ha(3), 210.0, 0), (ha(1), 250.0, 0), (HOJE, 250.0, 0)]


def caso_serie_colecao():
    """2 duals a 100 € há 30 dias e a 120 € hoje → primeiro ponto 200, último
    240; os dias sem preço nenhum não entram e o PT só olha para o `n_preco_pt`."""
    with sessao() as con:
        com_colecoes(con)
        tundra = _sid("Tundra", "3ed")
        marcar(con, "duals_revised", "Tundra", 2)
        vigiado_em(con, tundra, "nonfoil", ha(30), 100.0)
        preco_em(con, tundra, "nonfoil", HOJE, 120.0)
        s = valor.serie_colecao(con, "duals_revised", HOJE)
        assert s == [(ha(30), 200.0, 0), (HOJE, 240.0, 0)], s
        # um dia a meio, de uma carta que ele não tem: nada muda
        outra = _sid("Bayou", "3ed")
        vigiado_em(con, outra, "nonfoil", ha(10), 50.0)
        s = valor.serie_colecao(con, "duals_revised", HOJE)
        assert s == [(ha(30), 200.0, 0), (HOJE, 240.0, 0)], s
        # a janela são 100 dias (a variação a 90 dias precisa de um ponto até
        # hoje−90): há 95 dias entra, há 120 fica de fora
        vigiado_em(con, tundra, "nonfoil", ha(120), 90.0)
        assert valor.serie_colecao(con, "duals_revised", HOJE)[0][0] == ha(30)
        vigiado_em(con, tundra, "nonfoil", ha(95), 80.0)
        s = valor.serie_colecao(con, "duals_revised", HOJE)
        assert s[0] == (ha(95), 160.0, 0), s
        # sem cópias nenhumas, sem pontos
        assert valor.serie_colecao(con, "expeditions", HOJE) == []


def caso_serie_colecao_pt_e_sem_preco():
    with sessao() as con:
        com_colecoes(con)
        vents = _sid("Steam Vents", "gpt")
        marcar(con, "shocks_pt", "Steam Vents", 3)
        # só trend inglês: nenhuma cópia tem preço, a série fica vazia
        preco_em(con, vents, "nonfoil", ha(5), 50.0)
        assert valor.serie_colecao(con, "shocks_pt", HOJE) == []
        pt_em(con, vents, "nonfoil", ha(20), 60.0)
        pt_em(con, vents, "nonfoil", ha(2), 90.0)
        s = valor.serie_colecao(con, "shocks_pt", HOJE)
        assert s == [(ha(20), 180.0, 0), (ha(2), 270.0, 0), (HOJE, 270.0, 0)], s


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
