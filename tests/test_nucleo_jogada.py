"""Onde uma carta se joga (`mtgvault/nucleo/jogada.py`): as jogadas por mês que
sobrevivem à poda das listas (`n_jogada`) e os rótulos «deck X» / «Legacy» que a
Coleção e o «a subir» mostram ao lado de cada carta.

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários (`db.session(tmp/"v.db", tmp/"c.db")`) e escreve as `decklists` à mão.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db  # noqa: E402
from mtgvault.nucleo import colecoes, cotacoes, jogada, listas, modelo  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

HOJE = "2026-10-30"
CARTAS = ("Mox Opal", "Sol Ring", "Ragavan, Nimble Pilferer", "Wear // Tear")


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def semear(con):
    """O catálogo mínimo e os decks do núcleo (para gravar uma versão)."""
    for i, nome in enumerate(CARTAS):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,'tst','Test Set',?,'en','rare','Artifact',0,'',?,
               '1993-08-05',?,0)""",
            (f"id-{i}", f"or-{i}", nome, str(i), json.dumps(["nonfoil"]),
             1000 + i))
    con.commit()
    modelo.garantir_decks(con)


def lista(con, formato, data, cartas, chave):
    """Uma decklist como a recolha a deixa. `cartas`: (nome, qtd, board)."""
    cur = con.execute(
        "INSERT INTO decklists (source, source_key, format, event_name,"
        " event_date, player) VALUES ('mtgo',?,?,'Evento',?,'Jogador')",
        (chave, formato, data))
    for nome, qtd, board in cartas:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                    " quantity, board) VALUES (?,?,?,?)",
                    (cur.lastrowid, nome, qtd, board))
    con.commit()
    return cur.lastrowid


def linhas(con):
    return [tuple(r) for r in con.execute(
        "SELECT formato, mes, nome, listas FROM n_jogada"
        " ORDER BY formato, mes, nome")]


def gravada(con, formato, mes, nome, n):
    """Uma linha de `n_jogada` já gravada (as listas dela podem ter sido podadas)."""
    con.execute("INSERT OR REPLACE INTO n_jogada (formato, mes, nome, listas)"
                " VALUES (?,?,?,?)", (formato, mes, nome, n))
    con.commit()


# ---------------------------------------------------------------------------
def caso_registar_por_mes():
    """Duas listas de legacy em outubro com a mesma carta → `listas == 2`; uma
    carta no main e no side da MESMA lista conta uma vez; meses e formatos ficam
    em linhas separadas; de uma carta de duas faces só fica a frente."""
    with sessao() as con:
        lista(con, "legacy", "2026-10-03", [("Mox Opal", 4, "main")], "a")
        lista(con, "legacy", "2026-10-20",
              [("Mox Opal", 2, "main"), ("Mox Opal", 1, "side"),
               ("Wear // Tear", 1, "main")], "b")
        lista(con, "legacy", "2026-09-28", [("Mox Opal", 4, "main")], "c")
        lista(con, "modern", "2026-10-05", [("Mox Opal", 4, "main")], "d")
        n = jogada.registar(con)
        assert linhas(con) == [
            ("legacy", "2026-09", "Mox Opal", 1),
            ("legacy", "2026-10", "Mox Opal", 2),        # main+side da «b» = 1
            ("legacy", "2026-10", "Wear", 1),
            ("modern", "2026-10", "Mox Opal", 1)], linhas(con)
        assert n == 4, n


def caso_registar_idempotente():
    """Correr duas vezes dá as mesmas linhas; um mês cujas listas a poda já
    apagou mantém as suas (a razão de ser da tabela); e uma lista a mais sobe a
    contagem do mês, não a soma por cima."""
    with sessao() as con:
        lista(con, "legacy", "2026-10-03", [("Mox Opal", 4, "main")], "a")
        lista(con, "legacy", "2026-10-04", [("Mox Opal", 4, "main")], "b")
        assert jogada.registar(con) == 1
        antes = linhas(con)
        assert jogada.registar(con) == 1
        assert linhas(con) == antes == [("legacy", "2026-10", "Mox Opal", 2)]
        # um mês antigo cujas listas já não existem: fica
        gravada(con, "legacy", "2026-07", "Sol Ring", 5)
        lista(con, "legacy", "2026-10-09", [("Mox Opal", 4, "main")], "c")
        jogada.registar(con)
        assert linhas(con) == [("legacy", "2026-07", "Sol Ring", 5),
                               ("legacy", "2026-10", "Mox Opal", 3)], linhas(con)
        # uma carta que deixou de estar nas listas desse mês FICA, com a
        # contagem antiga (a poda deslizante não pode apagar a memória)
        con.execute("DELETE FROM decklist_cards WHERE card_name = 'Mox Opal'")
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name, quantity,"
                    " board) SELECT id, 'Sol Ring', 1, 'main' FROM decklists"
                    " WHERE source_key = 'a'")
        con.commit()
        jogada.registar(con)
        assert linhas(con) == [("legacy", "2026-07", "Sol Ring", 5),
                               ("legacy", "2026-10", "Mox Opal", 3),
                               ("legacy", "2026-10", "Sol Ring", 1)], linhas(con)


def caso_poda_nao_apaga():
    """A poda deslizante apaga listas de um mês a meio: a contagem e as cartas
    que só se jogaram nessas listas ficam. Duas listas com X: registar → 2; apaga
    uma → continua 2; apaga as duas → X continua lá."""
    with sessao() as con:
        a = lista(con, "legacy", "2026-10-03", [("Mox Opal", 4, "main")], "a")
        b = lista(con, "legacy", "2026-10-04", [("Mox Opal", 4, "main")], "b")
        lista(con, "legacy", "2026-10-05", [("Sol Ring", 1, "main")], "c")
        jogada.registar(con)
        assert linhas(con) == [("legacy", "2026-10", "Mox Opal", 2),
                               ("legacy", "2026-10", "Sol Ring", 1)]

        def podar(i):
            con.execute("DELETE FROM decklist_cards WHERE decklist_id = ?", (i,))
            con.execute("DELETE FROM decklists WHERE id = ?", (i,))
            con.commit()
        podar(a)
        jogada.registar(con)
        assert ("legacy", "2026-10", "Mox Opal", 2) in linhas(con), linhas(con)
        podar(b)
        jogada.registar(con)
        assert linhas(con) == [("legacy", "2026-10", "Mox Opal", 2),
                               ("legacy", "2026-10", "Sol Ring", 1)], linhas(con)
        # e com a carta de volta numa lista nova, a contagem só sobe se passar
        lista(con, "legacy", "2026-10-09", [("Mox Opal", 4, "main")], "d")
        jogada.registar(con)
        assert ("legacy", "2026-10", "Mox Opal", 2) in linhas(con)
        lista(con, "legacy", "2026-10-10", [("Mox Opal", 4, "main")], "e")
        lista(con, "legacy", "2026-10-11", [("Mox Opal", 4, "main")], "f")
        jogada.registar(con)
        assert ("legacy", "2026-10", "Mox Opal", 3) in linhas(con), linhas(con)


def caso_frente_com_espacos():
    """O mesmo nome com espaços à volta dá a mesma chave no SQL e no Python."""
    with sessao() as con:
        lista(con, "legacy", "2026-10-03", [("  Sol Ring ", 1, "main")], "a")
        jogada.registar(con)
        assert linhas(con) == [("legacy", "2026-10", "Sol Ring", 1)], linhas(con)
        assert jogada.onde_joga(con, " Sol Ring", HOJE) == ["Legacy"]


def caso_onde_joga():
    """«deck Oswald» primeiro; só n_jogada de há 4 meses → []; de há 1 mês →
    [«Legacy»]; a janela vai de há 3 meses até hoje, inclusive."""
    with sessao() as con:
        semear(con)
        listas.gravar_versao(con, "modern_oswald",
                             [Linha("main", "Mox Opal", 4)],
                             fonte="t", origem="andre")
        gravada(con, "legacy", "2026-09", "Mox Opal", 3)
        assert jogada.onde_joga(con, "Mox Opal", HOJE) == ["deck Oswald", "Legacy"]
        assert jogada.onde_joga(con, "Sol Ring", HOJE) == []     # ninguém a joga
        # há 4 meses: fora da janela
        gravada(con, "legacy", "2026-06", "Sol Ring", 9)
        assert jogada.onde_joga(con, "Sol Ring", HOJE) == []
        # há 3 meses (inclusive) e há 1 mês
        gravada(con, "modern", "2026-07", "Sol Ring", 1)
        assert jogada.onde_joga(con, "Sol Ring", HOJE) == ["Modern"]
        gravada(con, "legacy", "2026-09", "Sol Ring", 2)
        assert jogada.onde_joga(con, "Sol Ring", HOJE) == ["Legacy", "Modern"]


def caso_onde_joga_usa_o_indice_por_nome():
    """(R25) O `n_jogada` só cresce (R10) e a chave primária começa pelo
    formato: o `onde_joga` filtra pelo NOME e varria a tabela inteira (medido:
    0,65 s → 4,27 s com um ano de linhas). O índice `(nome, mes)` existe numa
    base nova e numa migrada, e a consulta entra por ele."""
    with sessao() as con:
        assert con.execute("SELECT 1 FROM sqlite_master WHERE type = 'index'"
                           " AND name = 'ix_n_jogada_nome'").fetchone(),             "falta o índice ix_n_jogada_nome"
        cols = [r[2] for r in con.execute("PRAGMA index_info(ix_n_jogada_nome)")]
        assert cols == ["nome", "mes"], cols
        for formato in ("legacy", "modern", "pauper", "vintage"):
            for mes in range(1, 13):
                for k in range(20):
                    gravada(con, formato, f"2026-{mes:02d}", f"Carta {k}", 1)
        con.execute("ANALYZE")
        ini, fim = jogada._janela(HOJE)
        plano = " | ".join(r[3] for r in con.execute(
            "EXPLAIN QUERY PLAN SELECT formato, SUM(listas) FROM n_jogada"
            " WHERE nome = ? AND mes >= ? AND mes <= ? GROUP BY formato",
            ("Carta 1", ini, fim)))
        assert "ix_n_jogada_nome" in plano, plano
        assert jogada.onde_joga(con, "Carta 1", HOJE) == [
            "Legacy", "Modern", "Pauper", "Vintage"]


def caso_todos_os_formatos_recolhidos_tem_rotulo():
    """O «joga» nunca mostra um código cru («vintage»): cada formato que a
    recolha guarda tem o seu rótulo em `visual.FORMATOS`."""
    from mtgvault import mtgtop8, sources                     # noqa: PLC0415
    from mtgvault.nucleo import visual                        # noqa: PLC0415
    codigos = (set(sources.MTGO_FORMATS) | set(sources.NON_MTGO_FORMATS)
               | set(mtgtop8.FORMAT_CODES))
    faltam = sorted(codigos - set(visual.FORMATOS))
    assert not faltam, faltam
    assert visual.formato("vintage") == "Vintage"


def caso_onde_joga_janela_na_viragem_do_ano():
    """Em janeiro a janela atravessa o ano: há 3 meses é outubro do ano anterior."""
    with sessao() as con:
        gravada(con, "legacy", "2025-10", "Sol Ring", 1)
        gravada(con, "modern", "2025-09", "Sol Ring", 1)
        assert jogada.onde_joga(con, "Sol Ring", "2026-01-15") == ["Legacy"]


def caso_onde_joga_ordem_dos_formatos():
    """Mais listas na janela primeiro (somando os meses); empate pelo rótulo."""
    with sessao() as con:
        gravada(con, "legacy", "2026-10", "Sol Ring", 2)
        gravada(con, "modern", "2026-08", "Sol Ring", 2)
        gravada(con, "modern", "2026-10", "Sol Ring", 1)
        gravada(con, "pauper", "2026-10", "Sol Ring", 4)
        gravada(con, "cedh", "2026-10", "Sol Ring", 2)
        assert jogada.onde_joga(con, "Sol Ring", HOJE) == [
            "Pauper", "Modern", "Legacy", "cEDH"]       # 4, 3, 2 e 2 (empate: Legacy < cEDH)


def caso_so_a_versao_atual_e_cada_deck_uma_vez():
    """Uma versão antiga não conta; uma carta em duas secções do mesmo deck dá
    um rótulo só; a ordem dos decks é a do `modelo.decks`."""
    with sessao() as con:
        semear(con)
        listas.gravar_versao(con, "modern_oswald", [Linha("main", "Sol Ring", 1)],
                             fonte="t", origem="andre")
        listas.gravar_versao(con, "modern_oswald", [Linha("main", "Mox Opal", 1)],
                             fonte="t", origem="andre")
        assert jogada.onde_joga(con, "Sol Ring", HOJE) == []    # só na antiga
        listas.gravar_versao(con, "cedh_cloud",
                             [Linha("main", "Mox Opal", 1),
                              Linha("side", "Mox Opal", 1)],
                             fonte="t", origem="andre")
        esperado = [f"deck {d['nome']}" for d in modelo.decks(con)
                    if d["slug"] in ("modern_oswald", "cedh_cloud")]
        assert len(esperado) == 2
        assert jogada.onde_joga(con, "Mox Opal", HOJE) == esperado


def caso_face_da_frente():
    """O catálogo diz «Wear // Tear», as listas só «Wear»: casa pela frente, nos
    dois sentidos (decks e torneios)."""
    with sessao() as con:
        semear(con)
        listas.gravar_versao(con, "modern_oswald", [Linha("main", "Wear // Tear", 1)],
                             fonte="t", origem="andre")
        assert jogada.onde_joga(con, "Wear // Tear", HOJE) == ["deck Oswald"]
        assert jogada.onde_joga(con, "Wear", HOJE) == ["deck Oswald"]
        lista(con, "legacy", "2026-10-12", [("Wear", 1, "main")], "c")
        jogada.registar(con)
        assert jogada.onde_joga(con, "Wear // Tear", HOJE) == [
            "deck Oswald", "Legacy"]
        assert jogada.onde_joga(con, "Wear", HOJE) == ["deck Oswald", "Legacy"]


def caso_hoje_por_omissao():
    """Sem `hoje`, usa o dia de hoje: não rebenta e devolve uma lista."""
    with sessao() as con:
        assert jogada.onde_joga(con, "Sol Ring") == []


def caso_ligado_a_colecao_e_ao_a_subir():
    """O `joga` das cartas da Coleção e das linhas do «a subir» vem de cá."""
    from test_nucleo_colecoes import RL_SID, _carta, _pronta   # noqa: PLC0415
    from test_nucleo_cotacoes import trend_hoje                 # noqa: PLC0415
    with _pronta() as con:
        gravada(con, "legacy", "2026-10", "Underground Sea", 2)
        est = colecoes.estado_colecao(con, "duals_revised", HOJE)
        us = next(c for c in est["cartas"] if c["nome"] == "Underground Sea")
        tundra = next(c for c in est["cartas"] if c["nome"] == "Tundra")
        assert us["joga"] == ["Legacy"] and tundra["joga"] == [], (us, tundra)
        # a Moat (Reserved List) a 25 €: entra no «a subir» e joga em Legacy
        trend_hoje(con, RL_SID, "nonfoil", 25.0)
        gravada(con, "legacy", "2026-10", "Moat", 4)
        moat = next(l for l in cotacoes.a_subir(con, HOJE)
                    if l["scryfall_id"] == RL_SID)
        assert moat["joga"] == ["Legacy"], moat


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
