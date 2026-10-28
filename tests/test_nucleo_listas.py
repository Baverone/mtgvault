"""As listas coladas e as versões do núcleo: ler o texto, resolver os nomes no
catálogo, gravar uma versão com fonte e dizer o que entrou e o que saiu.

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários (`db.session(vault_tmp, catalog_tmp)`) e semeia o `catalog.cards`
com `INSERT`s à mão, como o `test_movers`.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db  # noqa: E402
from mtgvault.nucleo import listas, posse  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

# (nome no catálogo, digital)
CATALOGO = [
    ("Kraum, Ludevic's Opus", 0),
    ("Force of Will", 0),
    ("Lightning Bolt", 0),
    ("Fling", 0),
    ("Galvanic Blast", 0),
    ("Island", 0),
    ("Delver of Secrets // Insectile Aberration", 0),
    ("Fire // Ice", 0),
    # só existe em digital: não conta (a coleção dele é de papel)
    ("Alchemy Only Card", 1),
    # uma carta de papel e uma versão digital com o mesmo nome
    ("Brainstorm", 1),
    ("Brainstorm", 0),
]


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def semear(con):
    for i, (nome, digital) in enumerate(CATALOGO):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,'tst','Test Set',?,'en','rare','Land',0,'',?,
               '1993-08-05',?,?)""",
            (f"id-{i}", f"or-{i}", nome, str(i), json.dumps(["nonfoil"]),
             1000 + i, digital))
    con.commit()


def n_versoes(con):
    return con.execute("SELECT count(*) FROM n_versao").fetchone()[0]


def caso_ler_moxfield_export():
    texto = (
        "Commander\n"
        "1 Kraum, Ludevic's Opus (CMR) 89\n"
        "\n"
        "Deck\n"
        "1 Force of Will (ALL) 54a *F*\n"
        "1 Lightning Bolt (2XM) 123 *E*\n"
        "2 Island (UNF) 5\n"
        "\n"
        "Sideboard\n"
        "1 Fling (MH2) 1\n"
        "\n"
        "Maybeboard\n"
        "1 Galvanic Blast (M10) 2\n"
    )
    assert listas.ler_texto(texto) == [
        Linha("comandante", "Kraum, Ludevic's Opus", 1),
        Linha("main", "Force of Will", 1),
        Linha("main", "Lightning Bolt", 1),
        Linha("main", "Island", 2),
        Linha("side", "Fling", 1),
    ], listas.ler_texto(texto)
    print("export do Moxfield lido (com Commander, marcadores e Maybeboard)")


def caso_ler_formatos_simples():
    texto = (
        "// um comentário\n"
        "4 Fling\n"
        "4x Galvanic Blast\n"
        "2 Fire // Ice\n"
        "2 Fling\n"                 # repetido: junta
        "SB: 3 Island\n"
        "COMPANION\n"
        "1 Brainstorm\n"
        "SIDEBOARD:\n"
        "1 Lightning Bolt\n"
        "Comandante\n"
        "1 Kraum, Ludevic's Opus\n"
    )
    assert listas.ler_texto(texto) == [
        Linha("main", "Fling", 6),
        Linha("main", "Galvanic Blast", 4),
        Linha("main", "Fire // Ice", 2),
        Linha("side", "Island", 3),
        Linha("side", "Brainstorm", 1),
        Linha("side", "Lightning Bolt", 1),
        Linha("comandante", "Kraum, Ludevic's Opus", 1),
    ], listas.ler_texto(texto)
    print("4 Nome, 4x Nome, SB:, cabeçalhos e repetidos")


def caso_ler_linha_vazia_e_sideboard():
    texto = "4 Fling\n4 Galvanic Blast\n\n3 Island\n2 Brainstorm\n"
    assert listas.ler_texto(texto) == [
        Linha("main", "Fling", 4),
        Linha("main", "Galvanic Blast", 4),
        Linha("side", "Island", 3),
        Linha("side", "Brainstorm", 2),
    ]
    # linhas vazias no início, e várias seguidas, não criam sideboard
    texto = "\n\n4 Fling\n\n\n3 Island\n"
    assert listas.ler_texto(texto) == [
        Linha("main", "Fling", 4), Linha("side", "Island", 3)]
    # uma linha vazia depois do comandante volta ao main, não vai para o side
    texto = "Commander\n1 Kraum, Ludevic's Opus\n\n1 Fling\n"
    assert listas.ler_texto(texto) == [
        Linha("comandante", "Kraum, Ludevic's Opus", 1),
        Linha("main", "Fling", 1)]
    print("linha vazia depois do main = sideboard")


def caso_nome_desconhecido_nada_grava():
    with sessao() as con:
        semear(con)
        linhas = listas.ler_texto(
            "1 Forse of Will\n4 Fling\n1 Nao Existe\n1 Forse of Will\n")
        try:
            listas.gravar_versao(con, "cedh_cloud", linhas, fonte="teste",
                                 origem="andre")
            raise AssertionError("devia ter levantado NomesDesconhecidos")
        except listas.NomesDesconhecidos as e:
            # todos, pela ordem de entrada, como foram escritos, sem repetir
            assert e.nomes == ["Forse of Will", "Nao Existe"], e.nomes
            assert isinstance(e, ValueError)
        assert n_versoes(con) == 0
        assert con.execute(
            "SELECT count(*) FROM n_versao_carta").fetchone()[0] == 0
    print("gralha: NomesDesconhecidos e nada gravado")


def caso_gralha_isolada():
    with sessao() as con:
        semear(con)
        try:
            listas.gravar_versao(con, "cedh_cloud",
                                 [Linha("main", "Forse of Will", 1)],
                                 fonte="teste", origem="andre")
        except listas.NomesDesconhecidos as e:
            assert e.nomes == ["Forse of Will"], e.nomes
        else:
            raise AssertionError("devia ter levantado")
        assert n_versoes(con) == 0
    print("NomesDesconhecidos.nomes == ['Forse of Will']")


def caso_normalizar_sem_caixa_e_digital():
    with sessao() as con:
        semear(con)
        out = listas.normalizar(con, [
            Linha("main", "force of will", 1),
            Linha("main", "FORCE OF WILL", 2),      # mesma carta: junta
            Linha("side", "force of will", 1),      # outra secção: separado
            Linha("main", "brainstorm", 4),
        ])
        assert out == [Linha("main", "Force of Will", 3),
                       Linha("side", "Force of Will", 1),
                       Linha("main", "Brainstorm", 4)], out
        # uma carta que só existe em digital é desconhecida
        try:
            listas.normalizar(con, [Linha("main", "Alchemy Only Card", 1)])
        except listas.NomesDesconhecidos as e:
            assert e.nomes == ["Alchemy Only Card"]
        else:
            raise AssertionError("o digital não conta")
    print("normalizar: sem caixa, junta, ignora o digital")


def caso_frente_de_duas_faces():
    with sessao() as con:
        semear(con)
        out = listas.normalizar(con, [
            Linha("main", "Delver of Secrets", 4),
            Linha("main", "delver of secrets", 1),
            Linha("main", "Fire // Ice", 1),
            Linha("main", "fire // ice", 1),
            Linha("main", "Fire/Ice", 1),
            Linha("main", "Fire", 1),
        ])
        assert out == [
            Linha("main", "Delver of Secrets // Insectile Aberration", 5),
            Linha("main", "Fire // Ice", 4),
        ], out
    print("a frente de uma dupla face resolve para o nome completo")


def caso_mesma_lista_nao_cria_versao():
    with sessao() as con:
        semear(con)
        linhas = listas.ler_texto("4 Fling\n2 Island\n\n1 Brainstorm\n")
        r1 = listas.gravar_versao(con, "cedh_cloud", linhas, fonte="teste",
                                  origem="andre")
        assert r1 is not None and r1["numero"] == 1, r1
        # a mesma lista, por outra ordem e com um repetido: não é versão nova
        outra = [Linha("side", "Brainstorm", 1), Linha("main", "Island", 1),
                 Linha("main", "Island", 1), Linha("main", "Fling", 4)]
        assert listas.gravar_versao(con, "cedh_cloud", outra, fonte="teste",
                                    origem="andre") is None
        assert n_versoes(con) == 1
        atual = listas.versao_atual(con, "cedh_cloud")
        assert atual["numero"] == 1
        # mesmo nome noutra secção já é outra lista
        diferente = [Linha("main", "Brainstorm", 1), Linha("main", "Island", 2),
                     Linha("main", "Fling", 4)]
        r2 = listas.gravar_versao(con, "cedh_cloud", diferente, fonte="teste",
                                  origem="andre")
        assert r2["numero"] == 2, r2
    print("a mesma lista (por outra ordem) devolve None")


def caso_versao_atual_e_numeracao():
    with sessao() as con:
        semear(con)
        assert listas.versao_atual(con, "cedh_cloud") is None
        v1 = listas.gravar_versao(
            con, "cedh_cloud",
            listas.ler_texto("Commander\n1 Kraum, Ludevic's Opus\n\n"
                             "Deck\n4 Fling\n\nSideboard\n1 Island\n"),
            fonte="moxfield", origem="vigia", quando="2026-10-28T10:00:00")
        assert v1["numero"] == 1
        assert v1["entrou"] == [("Fling", 4), ("Island", 1),
                                ("Kraum, Ludevic's Opus", 1)], v1["entrou"]
        assert v1["saiu"] == []
        a = listas.versao_atual(con, "cedh_cloud")
        assert a["id"] == v1["versao_id"] and a["numero"] == 1
        assert a["criada_em"] == "2026-10-28T10:00:00"
        assert a["fonte"] == "moxfield" and a["origem"] == "vigia"
        assert sorted(a["linhas"]) == sorted([
            Linha("comandante", "Kraum, Ludevic's Opus", 1),
            Linha("main", "Fling", 4), Linha("side", "Island", 1)]), a
        assert all(isinstance(x, Linha) for x in a["linhas"])
        # outro deck tem a sua própria numeração
        v = listas.gravar_versao(con, "dc_cloud", [Linha("main", "Fling", 1)],
                                 fonte="a mão", origem="andre")
        assert v["numero"] == 1
        assert listas.versao_atual(con, "dc_cloud")["numero"] == 1
        assert listas.versao_atual(con, "cedh_cloud")["numero"] == 1
        # sem `quando`, a hora é a de agora, em ISO sem fuso
        criada = listas.versao_atual(con, "dc_cloud")["criada_em"]
        assert len(criada) == 19 and criada[10] == "T", criada
    print("versao_atual e numeração por deck")


def caso_sem_duplicados_na_base():
    with sessao() as con:
        semear(con)
        # repetidos e caixas diferentes têm de acabar numa linha só por carta
        listas.gravar_versao(con, "cedh_cloud", [
            Linha("main", "fling", 2), Linha("main", "Fling", 2),
            Linha("main", "FLING", 1)], fonte="teste", origem="andre")
        rows = con.execute(
            "SELECT seccao, nome, qtd FROM n_versao_carta").fetchall()
        assert [tuple(r) for r in rows] == [("main", "Fling", 5)], rows
    print("n_versao_carta sem duplicados")


def caso_diferenca():
    with sessao() as con:
        semear(con)
        v1 = listas.gravar_versao(con, "pauper_affinity",
                                  [Linha("main", "Fling", 4)],
                                  fonte="teste", origem="andre")
        assert v1["entrou"] == [("Fling", 4)] and v1["saiu"] == []
        v2 = listas.gravar_versao(con, "pauper_affinity",
                                  [Linha("main", "Galvanic Blast", 2)],
                                  fonte="teste", origem="andre")
        assert v2["numero"] == 2
        assert v2["entrou"] == [("Galvanic Blast", 2)], v2
        assert v2["saiu"] == [("Fling", 4)], v2

    # a função pura: soma as secções por nome, e trata mudanças de quantidade
    antes = [Linha("main", "Fling", 3), Linha("side", "Fling", 1),
             Linha("main", "Island", 2)]
    depois = [Linha("main", "Fling", 4), Linha("main", "Island", 1),
              Linha("side", "Brainstorm", 2)]
    d = listas.diferenca(antes, depois)
    assert d == {"entrou": [("Brainstorm", 2)], "saiu": [("Island", 1)]}, d
    # mudar uma carta de secção não é entrar nem sair
    d = listas.diferenca([Linha("main", "Fling", 2)],
                         [Linha("side", "Fling", 2)])
    assert d == {"entrou": [], "saiu": []}, d
    print("diferença: entrou/saiu por nome, somando as secções")


def caso_fonte_obrigatoria():
    with sessao() as con:
        semear(con)
        for mau in ("", "   ", None):
            try:
                listas.gravar_versao(con, "cedh_cloud",
                                     [Linha("main", "Fling", 1)],
                                     fonte=mau, origem="andre")
            except ValueError as e:
                assert str(e) == "de onde veio a lista?", str(e)
            else:
                raise AssertionError(f"fonte {mau!r} devia ser recusada")
        assert n_versoes(con) == 0
        try:
            listas.gravar_versao(con, "cedh_cloud", [Linha("main", "Fling", 1)],
                                 fonte="teste", origem="outro")
        except ValueError:
            pass
        else:
            raise AssertionError("origem inválida devia ser recusada")
        assert n_versoes(con) == 0
    print("fonte (e origem) obrigatórias")


def caso_lista_vazia_recusada():
    with sessao() as con:
        semear(con)
        try:
            listas.gravar_versao(con, "cedh_cloud", [], fonte="teste",
                                 origem="andre")
        except ValueError:
            pass
        else:
            raise AssertionError("uma lista vazia não é uma versão")
        assert n_versoes(con) == 0
    print("lista vazia recusada")


def caso_posse_chamada_na_mesma_transacao():
    original = posse.depois_de_versao
    chamadas = []
    try:
        with sessao() as con:
            semear(con)

            def espia(con_, slug, antes, depois, versao_id, origem):
                # a versão já está lá dentro (mesma transação)...
                n = con_.execute("SELECT count(*) FROM n_versao WHERE id=?",
                                 (versao_id,)).fetchone()[0]
                chamadas.append((slug, list(antes), list(depois), versao_id,
                                 origem, n, con_.in_transaction))
            posse.depois_de_versao = espia
            listas.gravar_versao(con, "cedh_cloud", [Linha("main", "Fling", 1)],
                                 fonte="teste", origem="vigia")
            listas.gravar_versao(con, "cedh_cloud", [Linha("main", "Island", 1)],
                                 fonte="teste", origem="andre")
            assert len(chamadas) == 2
            slug, antes, depois, vid, origem, n, em_transacao = chamadas[0]
            assert (slug, antes, depois, origem) == (
                "cedh_cloud", [], [Linha("main", "Fling", 1)], "vigia")
            assert n == 1 and em_transacao is True
            assert chamadas[1][1] == [Linha("main", "Fling", 1)]
            assert chamadas[1][2] == [Linha("main", "Island", 1)]

            # uma lista igual não chama a posse
            listas.gravar_versao(con, "cedh_cloud", [Linha("main", "Island", 1)],
                                 fonte="teste", origem="andre")
            assert len(chamadas) == 2

            # se a posse falha, nada fica: nem a versão nem as cartas
            def parte(*a, **k):
                raise RuntimeError("avaria na posse")
            posse.depois_de_versao = parte
            try:
                listas.gravar_versao(con, "cedh_cloud",
                                     [Linha("main", "Brainstorm", 1)],
                                     fonte="teste", origem="andre")
            except RuntimeError:
                pass
            else:
                raise AssertionError("o erro da posse devia subir")
            assert n_versoes(con) == 2, n_versoes(con)
            assert listas.versao_atual(con, "cedh_cloud")["numero"] == 2
            assert con.execute("SELECT count(*) FROM n_versao_carta WHERE "
                               "nome = 'Brainstorm'").fetchone()[0] == 0
    finally:
        posse.depois_de_versao = original
    print("posse.depois_de_versao na mesma transação (e rollback)")


def caso_so_escreve_tabelas_n():
    with sessao() as con:
        semear(con)
        antes = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                 for t in ("copies", "copy_allocation", "posse_marcada",
                           "decks", "deck_cards")}
        listas.gravar_versao(con, "cedh_cloud", [Linha("main", "Fling", 1)],
                             fonte="teste", origem="andre")
        depois = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in antes}
        assert antes == depois, (antes, depois)
    print("só escreve nas tabelas n_*")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
    print("TUDO OK")
