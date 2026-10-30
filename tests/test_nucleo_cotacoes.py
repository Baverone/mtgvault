"""As cotações do núcleo (`mtgvault/nucleo/cotacoes.py`): o preço português
(só ofertas `pt` do CardTrader, nunca o inglês), os preços vigiados (guardados
sem poda, só quando mudam), a variação a 30/90 dias e a lista «a subir».

Nada aqui abre a base do André nem faz rede: cada caso constrói a sua base
temporária e o CardTrader é um objeto falso com `expansions`/`blueprints`/
`marketplace`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import prices  # noqa: E402
from mtgvault.nucleo import colecoes, cotacoes  # noqa: E402

from test_nucleo_colecoes import (  # noqa: E402
    RL_SID, _carta, _imprimir, _levanta, _pronta, _sid, sessao, semear)

HOJE = "2026-10-30"
HA30 = "2026-09-30"          # HOJE - 30 dias
HA90 = "2026-08-01"          # HOJE - 90 dias
VENTS_PT = _sid("Steam Vents", "gpt")          # um shock em português


def oferta(cents, lingua="pt", foil=False, **extra):
    """Uma oferta do CardTrader como a API a devolve, já utilizável."""
    o = {"price_cents": cents, "price_currency": "EUR", "quantity": 1,
         "graded": False, "on_vacation": False,
         "properties_hash": {"condition": "Near Mint", "mtg_language": lingua,
                             "mtg_foil": foil}}
    for k, v in extra.items():
        if k == "poor":
            o["properties_hash"]["condition"] = "Poor"
        else:
            o["properties_hash"][k] = v
    return o


def linhas_pt(con):
    return [tuple(r) for r in con.execute(
        "SELECT scryfall_id, acabamento, dia, preco_eur, ofertas FROM n_preco_pt"
        " ORDER BY scryfall_id, acabamento, dia")]


def vigiado(con, sid, acab, dia, eur):
    con.execute("INSERT OR REPLACE INTO n_preco_vigiado (scryfall_id, acabamento,"
                " dia, preco_eur) VALUES (?,?,?,?)", (sid, acab, dia, eur))
    con.commit()


def trend_hoje(con, sid, acab, trend, fonte="cardmarket", dia=HOJE):
    prices.write_prices(con, [(sid, fonte, dia, acab, trend, trend, trend,
                               None, "EUR")])


# ---------------------------------------------------------------------------
# O preço português
# ---------------------------------------------------------------------------
def caso_pt_so_portugues():
    """Ofertas `en` a 5 € e `pt` a 12 € e 15 €: fica a mais barata PT (12 €)
    com 2 ofertas; o inglês nunca entra."""
    with sessao() as con:
        n = cotacoes.gravar_ofertas_pt(
            con, "s1", [oferta(500, "en"), oferta(1200), oferta(1500)], "2026-10-20")
        assert n == 1, n
        assert linhas_pt(con) == [("s1", "nonfoil", "2026-10-20", 12.0, 2)], \
            linhas_pt(con)


def caso_pt_separa_o_foil():
    """O foil e o nonfoil têm cada um a sua linha e o seu mínimo."""
    with sessao() as con:
        n = cotacoes.gravar_ofertas_pt(
            con, "s1", [oferta(1000), oferta(3000, foil=True),
                        oferta(2500, foil=True)], "2026-10-20")
        assert n == 2, n
        assert linhas_pt(con) == [("s1", "foil", "2026-10-20", 25.0, 2),
                                  ("s1", "nonfoil", "2026-10-20", 10.0, 1)], \
            linhas_pt(con)


def caso_pt_filtro():
    """Uma oferta PT `altered` ou em estado `Poor` é ignorada; sem nenhuma
    aceite, não escreve nada."""
    with sessao() as con:
        n = cotacoes.gravar_ofertas_pt(
            con, "s1", [oferta(100, altered=True), oferta(200, poor=True),
                        oferta(900), oferta(300, signed=True)], "2026-10-20")
        assert n == 1 and linhas_pt(con) == [
            ("s1", "nonfoil", "2026-10-20", 9.0, 1)], linhas_pt(con)
        n = cotacoes.gravar_ofertas_pt(
            con, "s2", [oferta(100, altered=True), oferta(200, poor=True),
                        oferta(300, "en")], "2026-10-20")
        assert n == 0, "sem ofertas aceites não escreve"
        assert not [l for l in linhas_pt(con) if l[0] == "s2"]


def caso_pt_ultimo_visto():
    """Ofertas PT no dia 20 e nenhuma no 25: `preco_pt` dá o do dia 20, mesmo
    com um trend `en` no `price_latest` (nunca cai no inglês); uma carta nunca
    vista dá `(None, None)`."""
    with sessao() as con:
        cotacoes.gravar_ofertas_pt(con, VENTS_PT, [oferta(1200)], "2026-10-20")
        cotacoes.gravar_ofertas_pt(con, VENTS_PT, [oferta(1500)], "2026-10-10")
        trend_hoje(con, VENTS_PT, "nonfoil", 2.0, dia="2026-10-25")
        trend_hoje(con, VENTS_PT, "nonfoil", 2.0, fonte="cardtrader",
                   dia="2026-10-25")
        assert cotacoes.preco_pt(con, VENTS_PT, "nonfoil") == (12.0, "2026-10-20")
        assert cotacoes.preco_pt(con, "nunca-vista", "nonfoil") == (None, None)
        # o foil desta carta nunca foi visto em PT
        assert cotacoes.preco_pt(con, VENTS_PT, "foil") == (None, None)


# ---------------------------------------------------------------------------
# Os preços vigiados
# ---------------------------------------------------------------------------
def caso_vigiadas_so_na_mudanca():
    """O mesmo trend em dois dias dá uma linha; se muda, duas."""
    with sessao() as con:
        semear(con)
        colecoes.garantir_colecoes(con)
        trend_hoje(con, RL_SID, "nonfoil", 25.0)
        assert cotacoes.gravar_vigiadas(con, "2026-10-28") >= 1
        assert cotacoes.gravar_vigiadas(con, "2026-10-29") == 0, \
            "o mesmo trend não grava outra vez"
        n = con.execute("SELECT COUNT(*) FROM n_preco_vigiado WHERE scryfall_id"
                        " = ?", (RL_SID,)).fetchone()[0]
        assert n == 1, n
        trend_hoje(con, RL_SID, "nonfoil", 27.5)
        assert cotacoes.gravar_vigiadas(con, "2026-10-30") == 1
        assert [tuple(r) for r in con.execute(
            "SELECT dia, preco_eur FROM n_preco_vigiado WHERE scryfall_id = ?"
            " ORDER BY dia", (RL_SID,))] == [("2026-10-28", 25.0),
                                            ("2026-10-30", 27.5)]
        # só vigia o cardmarket e só com trend > 0
        trend_hoje(con, _sid("Badlands", "3ed"), "nonfoil", 0.0)
        trend_hoje(con, _sid("Bayou", "3ed"), "nonfoil", 9.0, fonte="cardtrader")
        cotacoes.gravar_vigiadas(con, "2026-10-30")
        assert not con.execute(
            "SELECT 1 FROM n_preco_vigiado WHERE scryfall_id IN (?,?)",
            (_sid("Badlands", "3ed"), _sid("Bayou", "3ed"))).fetchone()


def caso_vigiadas_lista():
    """As vigiadas: as cartas das coleções, a Reserved List e as impressões de
    papel das famílias e do set `exp`, só nos acabamentos que cada impressão
    tem; as digitais ficam de fora; a ordem é fixa."""
    with sessao() as con:
        semear(con)
        _imprimir(con, "bad-leb", "Badlands", "leb", ["nonfoil", "foil"])
        _imprimir(con, "bad-dig", "Badlands", "vma", ["nonfoil"])
        con.execute("UPDATE catalog.cards SET digital = 1 WHERE scryfall_id ="
                    " 'bad-dig'")
        _imprimir(con, "rl-b", "Mox X", "lea", ["nonfoil"], reserved=1)
        _imprimir(con, "rl-dig", "Mox Y", "vma", ["nonfoil"], reserved=1)
        con.execute("UPDATE catalog.cards SET digital = 1 WHERE scryfall_id ="
                    " 'rl-dig'")
        _imprimir(con, "exp-outra", "Carta Qualquer", "exp", ["foil"])
        _imprimir(con, "banal", "Carta Banal", "m21", ["nonfoil"])
        con.commit()
        colecoes.garantir_colecoes(con)
        v = cotacoes.vigiadas(con)
        assert v == sorted(v) and len(v) == len(set(v)), "ordem fixa, sem repetidos"
        assert ("bad-leb", "nonfoil") in v and ("bad-leb", "foil") in v
        assert ("bad-dig", "nonfoil") not in v and ("rl-dig", "nonfoil") not in v
        assert ("rl-b", "nonfoil") in v and ("rl-b", "foil") not in v
        assert (RL_SID, "nonfoil") in v
        assert ("exp-outra", "foil") in v
        assert ("banal", "nonfoil") not in v
        # as cartas das coleções (duals de Revised só em nonfoil)
        assert (_sid("Underground Sea", "3ed"), "nonfoil") in v
        assert (_sid("Underground Sea", "3ed"), "foil") not in v
        assert (VENTS_PT, "nonfoil") in v
        # uma carta de coleção aberta entra mesmo fora das famílias
        colecoes.juntar(con, "reserved_list", "banal", "nonfoil")
        assert ("banal", "nonfoil") in cotacoes.vigiadas(con)


def caso_cards_of_interest_inclui_vigiadas():
    """`prices.cards_of_interest` passa a incluir as vigiadas."""
    with sessao() as con:
        semear(con)
        _imprimir(con, "bad-leb", "Badlands", "leb", ["nonfoil"])
        _imprimir(con, "banal", "Carta Banal", "m21", ["nonfoil"])
        con.commit()
        ids = prices.cards_of_interest(con)
        assert {"bad-leb", RL_SID} <= ids
        assert _sid("Scalding Tarn", "exp") in ids, "o set exp inteiro"
        assert "banal" not in ids


# ---------------------------------------------------------------------------
# Variação e «a subir»
# ---------------------------------------------------------------------------
def caso_variacao():
    """100 € há 30 dias e 120 € hoje dá 20,0; sem ponto antigo, `None`;
    arredonda a uma casa."""
    with sessao() as con:
        vigiado(con, "a", "nonfoil", HA30, 100.0)
        vigiado(con, "a", "nonfoil", HOJE, 120.0)
        assert cotacoes.variacao(con, "a", "nonfoil", 30, HOJE) == 20.0
        # sem nada há 90 dias (o primeiro ponto é de há 30)
        assert cotacoes.variacao(con, "a", "nonfoil", 90, HOJE) is None
        # sem ponto de hoje, só um antigo: o preço de hoje é o antigo (a linha
        # mais recente), e o de há 30 dias não existe
        vigiado(con, "b", "nonfoil", HA90, 100.0)
        assert cotacoes.variacao(con, "b", "nonfoil", 30, HOJE) == 0.0
        assert cotacoes.variacao(con, "b", "nonfoil", 30, "2026-07-01") is None
        # 1 decimal
        vigiado(con, "c", "nonfoil", HA30, 30.0)
        vigiado(con, "c", "nonfoil", HOJE, 40.0)
        assert cotacoes.variacao(con, "c", "nonfoil", 30, HOJE) == 33.3
        # uma carta que nunca se viu
        assert cotacoes.variacao(con, "z", "nonfoil", 30, HOJE) is None
        # sem a linha de n_preco_vigiado, vale o histórico que a poda deixou
        prices.write_prices(con, [("h", "cardmarket", "2026-09-20", "nonfoil",
                                   50.0, 50.0, 50.0, None, "EUR"),
                                  ("h", "cardmarket", "2026-10-20", "nonfoil",
                                   60.0, 60.0, 60.0, None, "EUR")])
        assert cotacoes.preco_em(con, "h", "nonfoil", HA30) == 50.0
        assert cotacoes.variacao(con, "h", "nonfoil", 30, HOJE) == 20.0
        # o vigiado manda sobre o histórico
        vigiado(con, "h", "nonfoil", "2026-10-25", 90.0)
        assert cotacoes.preco_em(con, "h", "nonfoil", HOJE) == 90.0


def caso_a_subir():
    """Uma RL de 25 € a subir entra; uma de 10 € não; ordem por `var30`
    decrescente, com `None` no fim; `tenho` soma coleção e posse."""
    with sessao() as con:
        semear(con)
        _imprimir(con, "rl-b", "Mox X", "lea", ["nonfoil"], reserved=1)
        _imprimir(con, "rl-c", "Mox Y", "lea", ["nonfoil"], reserved=1)
        _imprimir(con, "rl-d", "Mox Z", "lea", ["nonfoil"], reserved=1)
        _imprimir(con, "banal", "Carta Banal", "m21", ["nonfoil"])
        con.commit()
        colecoes.garantir_colecoes(con)
        vigiado(con, RL_SID, "nonfoil", HA30, 20.0)          # +25 %
        vigiado(con, RL_SID, "nonfoil", HOJE, 25.0)
        vigiado(con, "rl-b", "nonfoil", HA30, 5.0)           # 10 €: abaixo do mínimo
        vigiado(con, "rl-b", "nonfoil", HOJE, 10.0)
        vigiado(con, "rl-c", "nonfoil", HA30, 20.0)          # +100 %
        vigiado(con, "rl-c", "nonfoil", HOJE, 40.0)
        vigiado(con, "rl-d", "nonfoil", HOJE, 30.0)          # sem ponto antigo
        vigiado(con, "banal", "nonfoil", HOJE, 99.0)         # nem RL nem família
        # 20,00 € é "≥ 20": entra; um dual de Revised a 19,99 € não
        vigiado(con, _sid("Tundra", "3ed"), "nonfoil", HOJE, 20.0)
        vigiado(con, _sid("Taiga", "3ed"), "nonfoil", HOJE, 19.99)
        # ele tem 1 na coleção e 2 num deck
        colecoes.juntar(con, "reserved_list", RL_SID, "nonfoil")
        con.execute("UPDATE n_colecao_carta SET tenho = 1 WHERE colecao ="
                    " 'reserved_list'")
        con.execute("INSERT INTO n_posse (ambito, scryfall_id, acabamento, qtd)"
                    " VALUES ('x', ?, 'nonfoil', 2)", (RL_SID,))
        con.commit()
        r = cotacoes.a_subir(con, HOJE)
        ids = [(l["scryfall_id"], l["acabamento"]) for l in r]
        # os sem variação ficam no fim, por nome (Mox Z, Tundra)
        assert ids == [("rl-c", "nonfoil"), (RL_SID, "nonfoil"),
                       ("rl-d", "nonfoil"), (_sid("Tundra", "3ed"), "nonfoil")], ids
        assert ("rl-b", "nonfoil") not in ids and ("banal", "nonfoil") not in ids
        assert (_sid("Taiga", "3ed"), "nonfoil") not in ids
        # os sem variação (None) vão para o fim
        sem = [l for l in r if l["var30"] is None]
        assert r[-len(sem):] == sem and len(sem) == 2, r
        moat = next(l for l in r if l["scryfall_id"] == RL_SID)
        assert set(moat) == {"nome", "set_code", "scryfall_id", "acabamento",
                             "preco", "var30", "var90", "tenho", "joga"}, moat
        assert moat["nome"] == "Moat" and moat["set_code"] == "leg"
        assert moat["preco"] == 25.0 and moat["var30"] == 25.0
        assert moat["var90"] is None and moat["tenho"] == 3 and moat["joga"] == []
        assert next(l for l in r if l["scryfall_id"] == "rl-c")["tenho"] == 0


# ---------------------------------------------------------------------------
# No estado da coleção
# ---------------------------------------------------------------------------
def caso_estado_precos_pt_e_en():
    """Uma carta `pt` mostra o preço português e o dia em que foi visto; uma
    `en` o trend do Cardmarket. A variação de uma `pt` vem só do `n_preco_pt`,
    nunca do inglês."""
    with _pronta() as con:
        # PT: 10 € há mais de 30 dias, 13 € a 27 de Outubro (o último visto, e
        # recente: com mais de 7 dias não há variação)
        cotacoes.gravar_ofertas_pt(con, VENTS_PT, [oferta(1000)], "2026-09-25")
        cotacoes.gravar_ofertas_pt(con, VENTS_PT, [oferta(1300)], "2026-10-27")
        # um inglês muito diferente, no trend e nos vigiados: não pode aparecer
        trend_hoje(con, VENTS_PT, "nonfoil", 2.0)
        vigiado(con, VENTS_PT, "nonfoil", HA30, 1.0)
        vigiado(con, VENTS_PT, "nonfoil", HOJE, 2.0)
        # EN: trend de 50 €, vigiado 40 € há 30 dias
        us = _sid("Underground Sea", "3ed")
        trend_hoje(con, us, "nonfoil", 50.0)
        vigiado(con, us, "nonfoil", HA30, 40.0)
        vigiado(con, us, "nonfoil", HOJE, 50.0)
        pt = _carta_pt(con)
        assert pt["preco_un"] == 13.0 and pt["preco_visto_em"] == "2026-10-27", pt
        assert pt["var30"] == 30.0, pt
        assert pt["var90"] is None, "não há ponto PT de há 90 dias"
        en = _carta_en(con)
        assert en["preco_un"] == 50.0 and en["preco_visto_em"] is None, en
        assert en["var30"] == 25.0 and en["var90"] is None, en
        # uma carta PT nunca vista: sem preço e sem variação (nunca o inglês)
        outra = _carta(con, "shocks_pt", "Overgrown Tomb")
        trend_hoje(con, outra["scryfall_id"], "nonfoil", 3.0)
        outra = _carta(con, "shocks_pt", "Overgrown Tomb")
        assert outra["preco_un"] is None and outra["preco_visto_em"] is None
        assert outra["var30"] is None and outra["var90"] is None


def _carta_pt(con):
    return next(c for c in colecoes.estado_colecao(con, "shocks_pt", HOJE)["cartas"]
                if c["scryfall_id"] == VENTS_PT)


def _carta_en(con):
    return next(c for c in colecoes.estado_colecao(con, "duals_revised", HOJE)["cartas"]
                if c["nome"] == "Underground Sea")


def _pt(con, dia, cents, sid=VENTS_PT):
    cotacoes.gravar_ofertas_pt(con, sid, [oferta(cents)], dia)


def caso_variacao_pt_so_com_avistamento_recente():
    """Um único avistamento PT há 40 dias não é uma variação: nada de 0,0 %
    inventado (a ausência de linha PT é «não observado»); o preço em si
    continua a ver-se com o dia (`preco_pt`)."""
    with sessao() as con:
        _pt(con, "2026-09-20", 1000)                       # há 40 dias
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 30, HOJE) is None
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 90, HOJE) is None
        assert cotacoes.preco_pt(con, VENTS_PT, "nonfoil") == (10.0, "2026-09-20")
        # dois avistamentos, mas ambos velhos (há 40 e há 100 dias): também None
        _pt(con, "2026-07-22", 800)
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 30, HOJE) is None
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 90, HOJE) is None
        # nunca visto
        assert cotacoes.variacao_pt(con, "nunca", "nonfoil", 30, HOJE) is None


def caso_variacao_pt_com_dois_avistamentos():
    """Visto há 2 dias e há 35 dias: a variação a 30 dias sai desses dois
    pontos; a 90 dias não há ponto antigo, `None`."""
    with sessao() as con:
        _pt(con, "2026-09-25", 1000)                       # há 35 dias
        _pt(con, "2026-10-28", 1300)                       # há 2 dias
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 30, HOJE) == 30.0
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 90, HOJE) is None
        # o foil desta carta nunca foi visto: não herda nada do nonfoil
        assert cotacoes.variacao_pt(con, VENTS_PT, "foil", 30, HOJE) is None


def caso_variacao_pt_ponto_antigo_distante():
    """Visto hoje e há 100 dias: a linha de «há 30 dias» e a de «há 90 dias» são
    a mesma linha antiga (o último preço observado até essa data), diferente
    da de hoje, por isso as duas variações calculam-se."""
    with sessao() as con:
        _pt(con, "2026-07-22", 1000)                       # há 100 dias
        _pt(con, HOJE, 2000)
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 30, HOJE) == 100.0
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 90, HOJE) == 100.0


def caso_variacao_pt_limite_de_sete_dias():
    """Sete dias ainda é «recente»; oito já não."""
    with sessao() as con:
        _pt(con, "2026-09-01", 1000)
        _pt(con, "2026-10-23", 1100)                       # há 7 dias
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 30, HOJE) == 10.0
        assert cotacoes.variacao_pt(con, VENTS_PT, "nonfoil", 30,
                                    "2026-10-31") is None  # há 8 dias


def caso_variacao_en_sem_historico_e_zero():
    """DE PROPÓSITO (R13): uma carta `en` que só tem `price_latest`, sem nenhuma
    linha de histórico, dá variação 0,0 — o histórico do Cardmarket só regista
    mudanças, por isso «sem linha» quer dizer «manteve-se desde antes da janela
    que a poda guarda». Não vale para o `n_preco_pt`, que se escreve todos os
    dias com ofertas (ver `variacao_pt`).

    (R23) Só é legítimo porque o histórico do Cardmarket (de OUTRA carta) já
    existia antes de há 90 dias: a ausência de linhas desta quer mesmo dizer
    «manteve-se»."""
    with sessao() as con:
        trend_hoje(con, "so-latest", "nonfoil", 50.0)
        con.execute("DELETE FROM price_history WHERE scryfall_id = 'so-latest'")
        con.commit()
        trend_hoje(con, "outra", "nonfoil", 7.0, dia="2026-07-01")
        assert cotacoes.variacao(con, "so-latest", "nonfoil", 30, HOJE) == 0.0
        assert cotacoes.variacao(con, "so-latest", "nonfoil", 90, HOJE) == 0.0


def caso_variacao_sem_prova_no_ponto_de_partida_e_none():
    """(R23) O ponto de há N dias precisa de prova: uma linha vigiada ou de
    histórico desta carta até lá, ou o histórico do Cardmarket (de qualquer
    carta) já a existir nesse dia. Sem nenhuma, a R13 devolvia o preço de HOJE
    para um dia de antes de haver histórico e a variação saía 0,0 % — medido:
    59 linhas de «A subir» com 0,0 % a 90 dias e o histórico a começar a 10/08."""
    with sessao() as con:
        trend_hoje(con, "so-latest", "nonfoil", 50.0)
        con.execute("DELETE FROM price_history WHERE scryfall_id = 'so-latest'")
        con.commit()
        # o histórico mais antigo da tabela é de 2026-09-01 (outra carta)
        trend_hoje(con, "outra", "nonfoil", 7.0, dia="2026-09-01")
        # há 30 dias (09-30) já havia histórico: sem linha = manteve-se
        assert cotacoes.variacao(con, "so-latest", "nonfoil", 30, HOJE) == 0.0
        # há 90 dias (08-01) ainda não havia histórico nenhum: «sem histórico»
        assert cotacoes.variacao(con, "so-latest", "nonfoil", 90, HOJE) is None
        # sem histórico nenhum na tabela, também não
        con.execute("DELETE FROM price_history")
        con.commit()
        assert cotacoes.variacao(con, "so-latest", "nonfoil", 30, HOJE) is None
        # uma linha vigiada desta carta antes do ponto de partida é prova
        vigiado(con, "so-latest", "nonfoil", "2026-07-15", 40.0)
        vigiado(con, "so-latest", "nonfoil", HOJE, 50.0)
        assert cotacoes.variacao(con, "so-latest", "nonfoil", 90, HOJE) == 25.0
        # e uma linha de histórico desta carta antes do ponto também (que é,
        # por definição, histórico do Cardmarket a existir nesse dia)
        trend_hoje(con, "tem-hist", "nonfoil", 20.0, dia="2026-07-20")
        trend_hoje(con, "tem-hist", "nonfoil", 30.0)
        con.execute("DELETE FROM price_history WHERE scryfall_id <> 'tem-hist'")
        con.commit()
        assert cotacoes.variacao(con, "tem-hist", "nonfoil", 90, HOJE) == 50.0


def caso_juntar_so_en_ou_pt():
    """Uma língua que não seja `en` nem `pt` é rejeitada ao juntar."""
    with _pronta() as con:
        msg = _levanta(lambda: colecoes.juntar(
            con, "reserved_list", RL_SID, "nonfoil", "de"))
        assert "de" in msg, msg
        assert colecoes.juntar(con, "reserved_list", RL_SID, "nonfoil", "pt")
        assert con.execute("SELECT COUNT(*) FROM n_colecao_carta WHERE colecao ="
                           " 'reserved_list'").fetchone()[0] == 1


# ---------------------------------------------------------------------------
# A recolha (com um CardTrader falso: sem rede)
# ---------------------------------------------------------------------------
class CTFalso:
    """Só o que `expansoes_mtg`, `sync_cardtrader_map` e `recolher_pt` pedem."""

    def __init__(self, mercado):
        self.mercado = mercado            # {expansion_id: {blueprint_id: [ofertas]}}
        self.pedidos = []

    def expansions(self):
        return [{"id": 10, "code": "RAV", "game_id": prices.GAME_ID_MTG},
                {"id": 11, "code": "GPT", "game_id": prices.GAME_ID_MTG},
                {"id": 12, "code": "DIS", "game_id": prices.GAME_ID_MTG},
                {"id": 99, "code": "3ED", "game_id": prices.GAME_ID_MTG}]

    def blueprints(self, eid):
        self.pedidos.append(("blueprints", eid))
        return [{"id": 1000 + eid, "scryfall_id": s}
                for s in self.sids.get(eid, [])]

    def marketplace(self, eid):
        self.pedidos.append(("marketplace", eid))
        return self.mercado.get(eid, {})

    sids = {}


def caso_recolher_pt():
    """`recolher_pt` só pede as três edições PT, grava as ofertas PT das cartas
    `pt` das coleções (o inglês e as cartas de fora ignorados) e devolve as
    linhas escritas."""
    with _pronta() as con:
        sid_gpt = VENTS_PT                         # blueprint 1011
        sid_rav = _sid("Overgrown Tomb", "rav")    # blueprint 1010
        ct = CTFalso({
            11: {"1011": [oferta(1200), oferta(500, "en"), oferta(1400)],
                 "1999": [oferta(100)]},           # blueprint fora do mapa
            10: {"1010": [oferta(800, foil=False), oferta(2000, foil=True)]},
            99: {"1099": [oferta(1)]},
        })
        CTFalso.sids = {10: [sid_rav], 11: [sid_gpt],
                        12: [_sid("Blood Crypt", "dis")], 99: [_sid("Tundra", "3ed")]}
        n = cotacoes.recolher_pt(con, ct, "2026-10-30")
        pedidos = {p for p in ct.pedidos if p[0] == "marketplace"}
        assert pedidos == {("marketplace", 10), ("marketplace", 11),
                           ("marketplace", 12)}, pedidos
        assert n == 3, n          # vents nonfoil, tomb nonfoil, tomb foil
        assert linhas_pt(con) == [
            (sid_gpt, "nonfoil", "2026-10-30", 12.0, 2),     # ordem por scryfall_id
            (sid_rav, "foil", "2026-10-30", 20.0, 1),
            (sid_rav, "nonfoil", "2026-10-30", 8.0, 1)], linhas_pt(con)


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
