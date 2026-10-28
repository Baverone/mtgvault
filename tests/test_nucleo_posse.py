"""A posse do núcleo: que edição e acabamento contam, o que ele tem, o que falta,
as partilhadas dos decks rotativos e os movimentos para montar um deck.

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários (`db.session(vault_tmp, catalog_tmp)`), semeia o `catalog.cards` e o
`price_latest` à mão e cria as versões com `listas.gravar_versao`.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db  # noqa: E402
from mtgvault.nucleo import listas, modelo, posse  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

# (scryfall_id, nome, set, data, finishes)
IMPRESSOES = [
    ("fow-a", "Force of Will", "all", "1996-06-10", ["nonfoil"]),
    ("fow-b", "Force of Will", "ema", "2016-06-10", ["nonfoil", "foil"]),
    ("saga-a", "Urza's Saga", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("saga-b", "Urza's Saga", "plst", "2021-06-18", ["nonfoil"]),
    ("tm-a", "Thought Monitor", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("tm-b", "Thought Monitor", "pmh2", "2021-06-18", ["nonfoil", "foil"]),
    ("tomb-a", "Ancient Tomb", "tmp", "1997-10-14", ["nonfoil"]),
    ("tomb-b", "Ancient Tomb", "uma", "2018-12-07", ["nonfoil", "foil"]),
    ("chal-a", "Chalice of the Void", "mrd", "2003-10-02", ["nonfoil"]),
    ("chal-b", "Chalice of the Void", "a25", "2018-03-16", ["nonfoil", "foil"]),
    ("weld-a", "Goblin Welder", "ulg", "1999-02-15", ["nonfoil"]),
    # sem preço nenhum: vale a primeira do `scryfall.impressoes` (a mais recente)
    ("isl-a", "Island", "lea", "1993-08-05", ["nonfoil"]),
    ("isl-b", "Island", "unf", "2023-12-08", ["nonfoil"]),
    # só existe em foil
    ("shiny-a", "Shiny Only", "sld", "2022-01-01", ["foil"]),
    # só existe na Summer Magic, que não conta como impressão a sério
    # (`scryfall.SETS_SEM_PRECO`): o `impressoes` não dá nenhuma
    ("sum-a", "Summer Only", "sum", "1994-06-01", ["nonfoil"]),
]

# (scryfall_id, acabamento, trend)
PRECOS = [
    ("fow-a", "nonfoil", 90.0),
    ("fow-b", "nonfoil", 70.0),
    ("fow-b", "foil", 150.0),
    ("saga-a", "nonfoil", 30.0),
    ("saga-b", "nonfoil", 25.0),
    ("tm-a", "nonfoil", 0.5),
    ("tm-b", "nonfoil", 2.0),
    ("tomb-a", "nonfoil", 60.0),
    ("tomb-b", "nonfoil", 40.0),
    # o trend 0 não é preço: a mais barata «com preço» é a chal-b
    ("chal-a", "nonfoil", 0.0),
    ("chal-b", "nonfoil", 10.0),
    ("weld-a", "nonfoil", 5.0),
]

ROT = "rotativos"
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
    for sid, acab, trend in PRECOS:
        con.execute(
            "INSERT INTO price_latest (scryfall_id, source, finish, date, low,"
            " trend) VALUES (?, 'cardmarket', ?, '2026-10-28', ?, ?)",
            (sid, acab, trend, trend))
    con.commit()
    modelo.garantir_decks(con)


def versao(con, slug, linhas, origem="andre"):
    return listas.gravar_versao(con, slug, [Linha(*l) for l in linhas],
                                fonte="teste", origem=origem)


_req = [0]


def marcar(con, slug, nome, delta):
    _req[0] += 1
    return posse.ajustar(con, slug, nome, delta, request_id=f"req-{_req[0]}")


def carta(estado, nome, seccao="main"):
    achadas = [c for c in estado["cartas"]
               if c["nome"] == nome and c["seccao"] == seccao]
    assert len(achadas) == 1, (nome, seccao, estado["cartas"])
    return achadas[0]


def soma_posse(con):
    return con.execute("SELECT COALESCE(SUM(qtd),0) FROM n_posse").fetchone()[0]


def saidas(con):
    return [tuple(r) for r in con.execute(
        "SELECT slug, motivo, versao_id, scryfall_id, acabamento, qtd"
        " FROM n_saida ORDER BY id")]


def esperar_valueerror(f, *args, **kw):
    try:
        f(*args, **kw)
    except ValueError:
        return
    raise AssertionError(f"devia levantar ValueError: {f.__name__}{args}")


# ---------------------------------------------------------------------------
def caso_sempre_montados_nao_partilham():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        versao(con, OATH, [("main", "Force of Will", 4)])
        assert posse.partilhadas(con) == set()
        assert posse.ambito(con, REP, "Force of Will") == REP
        assert marcar(con, REP, "Force of Will", 4) == 4
        rep = posse.estado_deck(con, REP)
        oath = posse.estado_deck(con, OATH)
        assert carta(rep, "Force of Will")["tenho"] == 4
        assert carta(rep, "Force of Will")["falta"] == 0
        assert carta(oath, "Force of Will")["tenho"] == 0
        assert carta(oath, "Force of Will")["falta"] == 4
        # nos sempre montados não há grupo nem «onde»
        assert carta(rep, "Force of Will")["grupo"] is None
        assert carta(rep, "Force of Will")["onde"] is None
        assert rep["montado"] is True and rep["modo"] == "sempre"


def caso_rotativos_partilham_pelo_maximo():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4),
                          ("main", "Thought Monitor", 4)])
        versao(con, LEG, [("main", "Urza's Saga", 2),
                          ("main", "Goblin Welder", 4)])
        # uma lista de um sempre montado não entra nas partilhadas
        versao(con, REP, [("main", "Goblin Welder", 4)])
        assert posse.partilhadas(con) == {"Urza's Saga"}
        assert posse.ambito(con, MOD, "Urza's Saga") == ROT
        assert posse.ambito(con, LEG, "Urza's Saga") == ROT
        assert posse.ambito(con, MOD, "Thought Monitor") == MOD
        assert posse.ambito(con, LEG, "Goblin Welder") == LEG
        assert marcar(con, MOD, "Urza's Saga", 4) == 4
        m, l = posse.estado_deck(con, MOD), posse.estado_deck(con, LEG)
        assert carta(m, "Urza's Saga")["falta"] == 0
        assert carta(l, "Urza's Saga")["falta"] == 0
        assert carta(l, "Urza's Saga")["tenho"] == 2
        assert carta(m, "Urza's Saga")["grupo"] == "partilhada"
        assert carta(m, "Thought Monitor")["grupo"] == "fixa"
        # marcar do outro deck mexe no mesmo monte
        assert marcar(con, LEG, "Urza's Saga", -1) == 3
        m, l = posse.estado_deck(con, MOD), posse.estado_deck(con, LEG)
        assert carta(m, "Urza's Saga")["falta"] == 1
        assert carta(l, "Urza's Saga")["falta"] == 0
        # a edição de uma partilhada é uma só para os rotativos
        assert posse.edicao(con, MOD, "Urza's Saga") == \
            posse.edicao(con, LEG, "Urza's Saga")


def caso_fixa_vira_partilhada_leva_posse():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Thought Monitor", 4),
                          ("main", "Urza's Saga", 4)])
        versao(con, LEG, [("main", "Goblin Welder", 4)])
        posse.escolher_edicao(con, MOD, "Thought Monitor", "tm-b", "foil")
        assert marcar(con, MOD, "Thought Monitor", 2) == 2
        antes = soma_posse(con)
        assert antes == 2
        # o legacy ganha uma carta que só o modern tinha
        versao(con, LEG, [("main", "Goblin Welder", 4),
                          ("side", "Thought Monitor", 1)])
        assert "Thought Monitor" in posse.partilhadas(con)
        assert soma_posse(con) == antes
        linhas = [tuple(r) for r in con.execute(
            "SELECT ambito, scryfall_id, acabamento, qtd FROM n_posse")]
        assert linhas == [(ROT, "tm-b", "foil", 2)], linhas
        # a escolha de edição foi com ela
        assert posse.edicao(con, LEG, "Thought Monitor") == ("tm-b", "foil")
        assert con.execute("SELECT count(*) FROM n_edicao WHERE ambito = ?",
                           (MOD,)).fetchone()[0] == 0
        assert carta(posse.estado_deck(con, MOD), "Thought Monitor")["tenho"] == 2
        assert carta(posse.estado_deck(con, LEG), "Thought Monitor",
                     "side")["tenho"] == 1
        assert saidas(con) == []


def caso_partilhada_volta_a_fixa():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        versao(con, LEG, [("main", "Urza's Saga", 2),
                          ("main", "Goblin Welder", 4)])
        posse.escolher_edicao(con, LEG, "Urza's Saga", "saga-a", "foil")
        marcar(con, LEG, "Urza's Saga", 3)
        # o legacy deixa de a jogar: volta a ser fixa do modern, com as cópias
        versao(con, LEG, [("main", "Goblin Welder", 4)])
        assert posse.partilhadas(con) == set()
        linhas = [tuple(r) for r in con.execute(
            "SELECT ambito, scryfall_id, acabamento, qtd FROM n_posse")]
        assert linhas == [(MOD, "saga-a", "foil", 3)], linhas
        assert posse.edicao(con, MOD, "Urza's Saga") == ("saga-a", "foil")
        assert carta(posse.estado_deck(con, MOD), "Urza's Saga")["tenho"] == 3
        # não saíram do monte, só mudaram de caixa
        assert saidas(con) == []


def caso_edicao_omissao():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4),
                          ("main", "Chalice of the Void", 2),
                          ("main", "Island", 10),
                          ("main", "Shiny Only", 1),
                          ("main", "Summer Only", 1)])
        # a nonfoil com menor trend > 0
        assert posse.edicao(con, REP, "Force of Will") == ("fow-b", "nonfoil")
        # trend 0 não é preço
        assert posse.edicao(con, REP, "Chalice of the Void") == \
            ("chal-b", "nonfoil")
        # sem preço nenhum: a primeira do scryfall.impressoes (a mais recente)
        assert posse.edicao(con, REP, "Island") == ("isl-b", "nonfoil")
        # só há foil: é essa
        assert posse.edicao(con, REP, "Shiny Only") == ("shiny-a", "foil")
        # sem impressões a sério
        assert posse.edicao(con, REP, "Summer Only") is None
        # a escolha gravada ganha à omissão
        posse.escolher_edicao(con, REP, "Force of Will", "fow-a", "nonfoil")
        assert posse.edicao(con, REP, "Force of Will") == ("fow-a", "nonfoil")


def caso_edicao_estrita():
    with sessao() as con:
        semear(con)
        v = versao(con, REP, [("main", "Chalice of the Void", 4)])
        assert posse.edicao(con, REP, "Chalice of the Void") == \
            ("chal-b", "nonfoil")
        assert marcar(con, REP, "Chalice of the Void", 3) == 3
        posse.escolher_edicao(con, REP, "Chalice of the Void", "chal-a",
                              "nonfoil")
        c = carta(posse.estado_deck(con, REP), "Chalice of the Void")
        assert c["tenho"] == 0 and c["falta"] == 4
        assert (c["scryfall_id"], c["acabamento"]) == ("chal-a", "nonfoil")
        assert saidas(con) == [(REP, "trocou_edicao", v["versao_id"], "chal-b",
                                "nonfoil", 3)], saidas(con)
        assert soma_posse(con) == 0
        # o acabamento também é estrito: a mesma impressão em foil é outra
        marcar(con, REP, "Chalice of the Void", 2)
        posse.escolher_edicao(con, REP, "Chalice of the Void", "chal-b", "foil")
        assert carta(posse.estado_deck(con, REP),
                     "Chalice of the Void")["tenho"] == 0
        assert saidas(con)[-1][1:] == ("trocou_edicao", v["versao_id"],
                                       "chal-a", "nonfoil", 2)
        # escolher a mesma outra vez não mexe em nada
        marcar(con, REP, "Chalice of the Void", 1)
        posse.escolher_edicao(con, REP, "Chalice of the Void", "chal-b", "foil")
        assert carta(posse.estado_deck(con, REP),
                     "Chalice of the Void")["tenho"] == 1
        assert len(saidas(con)) == 2


def caso_foil_so_se_existir():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Chalice of the Void", 4)])
        esperar_valueerror(posse.escolher_edicao, con, REP,
                           "Chalice of the Void", "chal-a", "foil")
        # uma impressão de outra carta
        esperar_valueerror(posse.escolher_edicao, con, REP,
                           "Chalice of the Void", "fow-b", "nonfoil")
        # uma impressão que não existe
        esperar_valueerror(posse.escolher_edicao, con, REP,
                           "Chalice of the Void", "nada", "nonfoil")
        # um acabamento que não é nonfoil nem foil
        esperar_valueerror(posse.escolher_edicao, con, REP,
                           "Chalice of the Void", "chal-b", "etched")
        assert con.execute("SELECT count(*) FROM n_edicao").fetchone()[0] == 0


def caso_saiu_da_lista_vai_para_saida():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4),
                          ("main", "Goblin Welder", 2)], origem="vigia")
        marcar(con, REP, "Force of Will", 3)
        v2 = versao(con, REP, [("main", "Goblin Welder", 2)], origem="vigia")
        assert saidas(con) == [(REP, "saiu_da_lista", v2["versao_id"], "fow-b",
                                "nonfoil", 3)], saidas(con)
        assert soma_posse(con) == 0
        # numa lista do André é o mesmo caso; e uma fixa de um rotativo também
        versao(con, MOD, [("main", "Thought Monitor", 4),
                          ("main", "Urza's Saga", 4)])
        marcar(con, MOD, "Thought Monitor", 4)
        v3 = versao(con, MOD, [("main", "Urza's Saga", 4)], origem="andre")
        assert saidas(con)[-1] == (MOD, "saiu_da_lista", v3["versao_id"],
                                   "tm-a", "nonfoil", 4), saidas(con)
        assert soma_posse(con) == 0
        # baixar a quantidade não é sair da lista
        marcar(con, MOD, "Urza's Saga", 4)
        versao(con, MOD, [("main", "Urza's Saga", 2)])
        assert len(saidas(con)) == 2
        assert soma_posse(con) == 4


def caso_ajustar_idempotente():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        assert posse.ajustar(con, REP, "Force of Will", 1,
                             request_id="abc") == 1
        assert posse.ajustar(con, REP, "Force of Will", 1,
                             request_id="abc") == 1
        assert carta(posse.estado_deck(con, REP), "Force of Will")["tenho"] == 1
        assert con.execute("SELECT count(*) FROM n_posse_log").fetchone()[0] == 1
        # a primeira marcação fixa a edição da omissão (o preço de amanhã não
        # a muda debaixo das cópias que ele já marcou)
        assert con.execute("SELECT scryfall_id, acabamento FROM n_edicao"
                           " WHERE ambito = ? AND nome = ?",
                           (REP, "Force of Will")).fetchone()[:] == \
            ("fow-b", "nonfoil")


def caso_nunca_negativo():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        assert posse.ajustar(con, REP, "Force of Will", -5,
                             request_id="n1") == 0
        assert posse.ajustar(con, REP, "Force of Will", 2,
                             request_id="n2") == 2
        assert posse.ajustar(con, REP, "Force of Will", -5,
                             request_id="n3") == 0
        # o pedido fica registado mesmo cortado no zero (idempotente)
        assert posse.ajustar(con, REP, "Force of Will", -5,
                             request_id="n3") == 0
        assert posse.ajustar(con, REP, "Force of Will", 1,
                             request_id="n4") == 1
        assert con.execute("SELECT count(*) FROM n_posse_log").fetchone()[0] == 4
        assert con.execute("SELECT min(qtd) FROM n_posse").fetchone()[0] >= 0


def caso_main_e_side_um_so_monte():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 3),
                          ("side", "Force of Will", 2)])
        marcar(con, REP, "Force of Will", 4)
        e = posse.estado_deck(con, REP)
        assert (carta(e, "Force of Will")["tenho"],
                carta(e, "Force of Will")["falta"]) == (3, 0)
        assert (carta(e, "Force of Will", "side")["tenho"],
                carta(e, "Force of Will", "side")["falta"]) == (1, 1)
        assert e["total"] == 5 and e["tenho"] == 4


def caso_estado_deck_campos():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4),
                          ("main", "Island", 2),
                          ("side", "Goblin Welder", 1)])
        marcar(con, REP, "Force of Will", 1)
        e = posse.estado_deck(con, REP)
        assert (e["slug"], e["nome"], e["formato"], e["modo"]) == \
            (REP, "UW Replenish", "premodern", "sempre")
        assert e["versao"]["numero"] == 1
        fow = carta(e, "Force of Will")
        assert (fow["scryfall_id"], fow["acabamento"], fow["qtd"]) == \
            ("fow-b", "nonfoil", 4)
        assert fow["preco_un"] == 70.0
        assert carta(e, "Island")["preco_un"] is None
        # 3 FoW a 70 + 1 Welder a 5; as 2 Island não têm preço
        assert abs(e["custo_falta"] - 215.0) < 1e-9, e["custo_falta"]
        assert e["sem_preco"] == 1
        assert e["total"] == 7 and e["tenho"] == 1
        # um deck sem versão
        vazio = posse.estado_deck(con, OATH)
        assert vazio["versao"] is None and vazio["cartas"] == []
        assert vazio["total"] == 0 and vazio["custo_falta"] == 0


def caso_slug_e_nome_validados():
    with sessao() as con:
        semear(con)
        versao(con, REP, [("main", "Force of Will", 4)])
        for f, args in ((posse.ambito, ("Force of Will",)),
                        (posse.edicao, ("Force of Will",)),
                        (posse.estado_deck, ()),
                        (posse.definir_montado, ()),
                        (posse.movimentos_para, ())):
            esperar_valueerror(f, con, "nao_existe", *args)
        esperar_valueerror(posse.ajustar, con, "nao_existe", "Force of Will",
                           1, request_id="x")
        # a carta tem de estar na versão atual do deck
        esperar_valueerror(posse.ambito, con, REP, "Goblin Welder")
        esperar_valueerror(posse.edicao, con, REP, "Goblin Welder")
        esperar_valueerror(posse.ajustar, con, REP, "Goblin Welder", 1,
                           request_id="y")
        esperar_valueerror(posse.escolher_edicao, con, REP, "Goblin Welder",
                           "weld-a", "nonfoil")
        esperar_valueerror(posse.ajustar, con, OATH, "Force of Will", 1,
                           request_id="z")
        assert con.execute("SELECT count(*) FROM n_posse_log").fetchone()[0] == 0


def caso_montar():
    with sessao() as con:
        semear(con)
        versao(con, MOD, [("main", "Urza's Saga", 4),
                          ("main", "Thought Monitor", 4)])
        versao(con, LEG, [("main", "Urza's Saga", 2),
                          ("main", "Ancient Tomb", 4)])
        versao(con, OSW, [("main", "Ancient Tomb", 2)])
        assert posse.partilhadas(con) == {"Urza's Saga", "Ancient Tomb"}
        marcar(con, MOD, "Urza's Saga", 3)
        marcar(con, LEG, "Ancient Tomb", 4)
        # nada montado: não há de onde trazer
        assert carta(posse.estado_deck(con, MOD), "Urza's Saga")["onde"] is None
        assert posse.definir_montado(con, LEG) == []
        assert con.execute("SELECT slug FROM n_montado").fetchone()[0] == LEG
        assert carta(posse.estado_deck(con, LEG), "Urza's Saga")["onde"] == "aqui"
        assert posse.estado_deck(con, LEG)["montado"] is True
        m = posse.estado_deck(con, MOD)
        assert m["montado"] is False
        assert carta(m, "Urza's Saga")["onde"] == "Welder Cam"
        assert carta(m, "Thought Monitor")["onde"] is None
        esperado = [{"nome": "Urza's Saga", "qtd": 3, "de": LEG, "para": MOD}]
        assert posse.movimentos_para(con, MOD) == esperado
        # o movimentos_para não grava
        assert con.execute("SELECT slug FROM n_montado").fetchone()[0] == LEG
        mov = posse.definir_montado(con, MOD)
        assert mov == esperado, mov
        assert mov[0]["de"] == "legacy_welder_cam"
        assert con.execute("SELECT slug FROM n_montado").fetchone()[0] == MOD
        # montar o que já está montado não move nada
        assert posse.definir_montado(con, MOD) == []
        # o Oswald só usa o Ancient Tomb (2 dos 4 que há)
        assert posse.movimentos_para(con, OSW) == [
            {"nome": "Ancient Tomb", "qtd": 2, "de": MOD, "para": OSW}]


def caso_montar_sempre_montado_recusa():
    with sessao() as con:
        semear(con)
        versao(con, OATH, [("main", "Force of Will", 4)])
        esperar_valueerror(posse.definir_montado, con, OATH)
        esperar_valueerror(posse.movimentos_para, con, OATH)
        assert con.execute("SELECT count(*) FROM n_montado").fetchone()[0] == 0


def caso_so_escreve_tabelas_n():
    with sessao() as con:
        semear(con)
        tabelas = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'n\\_%' ESCAPE '\\' AND name NOT LIKE 'sqlite%'")]
        antes = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                 for t in tabelas}
        versao(con, MOD, [("main", "Urza's Saga", 4)])
        versao(con, LEG, [("main", "Urza's Saga", 2)])
        marcar(con, MOD, "Urza's Saga", 2)
        posse.escolher_edicao(con, MOD, "Urza's Saga", "saga-a", "foil")
        posse.definir_montado(con, MOD)
        posse.estado_deck(con, MOD)
        depois = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in tabelas}
        assert antes == depois


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
