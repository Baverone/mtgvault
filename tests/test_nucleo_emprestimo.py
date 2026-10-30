"""O empréstimo das coleções aos decks rotativos (André, 30/10/2026): *«os
únicos decks que podem usar cartas da coleção são os de Standard, Pioneer,
Modern e Legacy»*.

O deck usa primeiro as cópias dele; o que faltar vem emprestado de uma coleção,
só cópias em inglês. A carta continua na coleção (o `tenho` dela, a meta e o
valor não mexem): é um empréstimo, não uma transferência.

Usa a base e o catálogo temporários do `test_nucleo_posse`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault.nucleo import posse, valor  # noqa: E402
from test_nucleo_posse import (LEG, MOD, REP, carta, marcar, semear,  # noqa: E402
                               sessao, versao)

_COLECOES = (("duals", "Duals de Revised", 1), ("rl", "Reserved List", 2),
             ("pt", "Shocks em português", 3))


def colecao(con, slug, nome, sid, tenho, *, acab="nonfoil", lingua="en"):
    for s, n, ordem in _COLECOES:
        con.execute("INSERT OR IGNORE INTO n_colecao (slug, nome, tipo, ordem)"
                    " VALUES (?,?,'fechada',?)", (s, n, ordem))
    cur = con.execute(
        "INSERT INTO n_colecao_carta (colecao, nome, scryfall_id, acabamento,"
        " lingua, meta, tenho) VALUES (?,?,?,?,?,4,?)",
        (slug, nome, sid, acab, lingua, tenho))
    con.commit()
    return cur.lastrowid


def tenhos_da_colecao(con):
    return [tuple(r) for r in con.execute(
        "SELECT colecao, scryfall_id, tenho FROM n_colecao_carta ORDER BY id")]


# ---------------------------------------------------------------------------
def caso_rotativo_usa_a_colecao_no_que_falta():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        marcar(con, MOD, "Urza's Saga", 1)
        colecao(con, "rl", "Urza's Saga", "saga-a", 2)
        e = posse.estado_deck(con, MOD)
        c = carta(e, "Urza's Saga")
        assert c["tenho"] == 3 and c["falta"] == 1, c
        assert c["da_colecao"] == 2, c
        assert c["colecoes"] == ["Reserved List"], c
        assert e["tenho"] == 3 and e["da_colecao"] == 2, e
        # o custo do que falta é só da que falta mesmo
        assert e["custo_falta"] == round(1 * c["preco_un"], 2), e


def caso_as_proprias_servem_primeiro():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        marcar(con, MOD, "Urza's Saga", 4)
        colecao(con, "rl", "Urza's Saga", "saga-a", 4)
        c = carta(posse.estado_deck(con, MOD), "Urza's Saga")
        assert c["tenho"] == 4 and c["da_colecao"] == 0 and c["colecoes"] == []


def caso_portugues_fica_na_colecao():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        colecao(con, "pt", "Urza's Saga", "saga-a", 4, lingua="pt")
        c = carta(posse.estado_deck(con, MOD), "Urza's Saga")
        assert c["tenho"] == 0 and c["falta"] == 4 and c["da_colecao"] == 0, c


def caso_qualquer_edicao_e_acabamento_em_ingles():
    """A edição da coleção não tem de ser a escolhida no deck: uma Saga de
    outra impressão ou em foil, em inglês, também serve."""
    with sessao() as con:
        semear(con)
        versao(con, LEG, [("main", "Urza's Saga", 4)])
        colecao(con, "duals", "Urza's Saga", "saga-b", 1)
        colecao(con, "rl", "Urza's Saga", "saga-a", 2, acab="foil")
        c = carta(posse.estado_deck(con, LEG), "Urza's Saga")
        assert c["tenho"] == 3 and c["da_colecao"] == 3, c
        # pela ordem das coleções
        assert c["colecoes"] == ["Duals de Revised", "Reserved List"], c


def caso_sempre_montados_nunca_veem_a_colecao():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        colecao(con, "rl", "Force of Will", "fow-a", 4)
        c = carta(posse.estado_deck(con, REP), "Force of Will")
        assert c["tenho"] == 0 and c["da_colecao"] == 0, c
        assert posse.da_colecao_para(con, REP) == []


def caso_emprestimo_nao_tira_nada_da_colecao():
    """Dois rotativos contam com as mesmas cópias (só um está montado de cada
    vez), e a coleção fica exatamente como estava."""
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        versao(con, LEG, [("main", "Urza's Saga", 2)])
        colecao(con, "rl", "Urza's Saga", "saga-a", 3)
        antes = tenhos_da_colecao(con)
        valor_antes = valor.valor_em(con)
        assert carta(posse.estado_deck(con, MOD), "Urza's Saga")["tenho"] == 3
        assert carta(posse.estado_deck(con, LEG), "Urza's Saga")["tenho"] == 2
        assert tenhos_da_colecao(con) == antes
        assert con.execute("SELECT count(*) FROM n_posse").fetchone()[0] == 0
        # o valor não conta a carta duas vezes: os decks não ganham nada
        assert valor.valor_em(con) == valor_antes


def caso_main_e_side_repartem_o_emprestimo():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 2), ("side", "Urza's Saga", 2)])
        colecao(con, "rl", "Urza's Saga", "saga-a", 3)
        e = posse.estado_deck(con, MOD)
        assert carta(e, "Urza's Saga")["da_colecao"] == 2
        s = carta(e, "Urza's Saga", "side")
        assert s["da_colecao"] == 1 and s["falta"] == 1, s


def caso_validadas_na_colecao_contam_no_deck():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        colecao(con, "rl", "Urza's Saga", "saga-a", 2)
        con.execute("INSERT INTO n_foto (id, caminho, dia, sessao, linha, indice)"
                    " VALUES (1, 'f.jpg', '2026-10-30', 's', 1, 0)")
        con.execute("INSERT INTO n_recorte (id, foto_id, numero, caminho)"
                    " VALUES (1, 1, 1, 'assets/cartas/1-1.jpg')")
        con.execute("INSERT INTO n_validacao (recorte_id, ambito, scryfall_id,"
                    " acabamento, lingua, qtd, em) VALUES (1, 'rl', 'saga-a',"
                    " 'nonfoil', 'en', 1, '2026-10-30T10:00:00')")
        con.commit()
        c = carta(posse.estado_deck(con, MOD), "Urza's Saga")
        assert c["validadas"] == 1, c
        assert c["recorte"] == "assets/cartas/1-1.jpg", c


def caso_o_que_trazer_das_colecoes():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4), ("side", "Urza's Saga", 1),
                          ("main", "Ancient Tomb", 2)])
        marcar(con, MOD, "Urza's Saga", 1)
        colecao(con, "duals", "Urza's Saga", "saga-b", 1)
        colecao(con, "rl", "Urza's Saga", "saga-a", 5)
        colecao(con, "rl", "Ancient Tomb", "tomb-a", 1)
        assert posse.da_colecao_para(con, MOD) == [
            {"nome": "Ancient Tomb", "qtd": 1, "colecao": "rl",
             "colecao_nome": "Reserved List"},
            {"nome": "Urza's Saga", "qtd": 1, "colecao": "duals",
             "colecao_nome": "Duals de Revised"},
            {"nome": "Urza's Saga", "qtd": 3, "colecao": "rl",
             "colecao_nome": "Reserved List"}]


def caso_a_pagina_diz_da_colecao():
    import nucleo_decks                                         # noqa: PLC0415
    from mtgvault.nucleo import visual                          # noqa: PLC0415
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        colecao(con, "rl", "Urza's Saga", "saga-a", 2)
        e = posse.estado_deck(con, MOD)
        html = visual.carta(carta(e, "Urza's Saga"), slug=MOD)
        assert "2 da coleção" in html and "Reserved List" in html, html
        mv = nucleo_decks._montar(con, e, {})
        assert "Das coleções: 2 Urza&#x27;s Saga (Reserved List)" in mv \
            or "Das coleções: 2 Urza's Saga (Reserved List)" in mv, mv
        # sem empréstimo, a carta não leva a etiqueta
        versao(con, LEG, [("main", "Force of Will", 1)])
        sem = visual.carta(carta(posse.estado_deck(con, LEG), "Force of Will"),
                           slug=LEG)
        assert "da coleção" not in sem


def caso_formatos_que_emprestam():
    assert posse.FORMATOS_COM_COLECAO == frozenset(
        {"standard", "pioneer", "modern", "legacy"})


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
