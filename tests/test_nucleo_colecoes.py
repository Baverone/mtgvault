"""As tabelas novas do núcleo: a Coleção (`n_colecao`, `n_colecao_carta`,
`n_colecao_log`), as fotos (`n_foto`, `n_recorte`, `n_validacao`), o preço PT e o
preço vigiado (`n_preco_pt`, `n_preco_vigiado`), as jogadas (`n_jogada`) e a
coluna `n_valor.colecoes_eur`.

Nada aqui abre a base do André: cada caso constrói a sua base temporária
(`db.session(tmp/"v.db", tmp/"c.db")`).
"""
import contextlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, prices  # noqa: E402
from mtgvault.nucleo import colecoes  # noqa: E402

TABELAS = [
    "n_colecao",
    "n_colecao_carta",
    "n_colecao_log",
    "n_foto",
    "n_recorte",
    "n_validacao",
    "n_preco_pt",
    "n_preco_vigiado",
    "n_jogada",
]


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def existe(con, tipo, nome):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?",
        (tipo, nome)).fetchone() is not None


def caso_tabelas_novas():
    """Numa base nova, as nove tabelas existem, o índice de `n_validacao` também,
    e `n_valor` ganhou `colecoes_eur`."""
    with sessao() as con:
        for tabela in TABELAS:
            assert existe(con, "table", tabela), f"falta a tabela {tabela}"
        assert existe(con, "index", "ix_n_validacao"), "falta o ix_n_validacao"
        colunas = {r["name"] for r in con.execute("PRAGMA table_info(n_valor)")}
        assert "colecoes_eur" in colunas, f"n_valor sem colecoes_eur: {colunas}"


def caso_migra_base_antiga():
    """Uma base criada ANTES destas tabelas, com o `n_valor` de quatro colunas e
    uma linha, ganha a coluna nova ao abrir-se com `db.session`, e a linha fica
    como estava."""
    tmp = Path(tempfile.mkdtemp())
    v = tmp / "v.db"
    antiga = sqlite3.connect(str(v))
    antiga.execute("""CREATE TABLE n_valor (
        dia       TEXT PRIMARY KEY,
        total_eur REAL,
        copias    INTEGER,
        sem_preco INTEGER)""")
    antiga.execute("INSERT INTO n_valor (dia, total_eur, copias, sem_preco) "
                   "VALUES ('2026-10-29', 1234.5, 10, 2)")
    antiga.commit()
    antiga.close()

    with db.session(v, tmp / "c.db") as con:
        colunas = {r["name"] for r in con.execute("PRAGMA table_info(n_valor)")}
        assert "colecoes_eur" in colunas, f"a migração não acrescentou a coluna: {colunas}"
        linha = con.execute(
            "SELECT dia, total_eur, copias, sem_preco, colecoes_eur "
            "FROM n_valor WHERE dia = '2026-10-29'").fetchone()
        assert linha is not None, "a linha antiga desapareceu"
        assert (linha["total_eur"], linha["copias"], linha["sem_preco"]) == (1234.5, 10, 2), \
            f"a linha antiga mudou: {tuple(linha)}"
        assert linha["colecoes_eur"] is None, "a coluna nova devia nascer vazia"


# ---------------------------------------------------------------------------
# Tarefa 2: as coleções (`mtgvault/nucleo/colecoes.py`)
# ---------------------------------------------------------------------------
DIA = "2026-10-28"
RL_SID = "rl-moat"          # uma carta da Reserved List, para a coleção aberta


def _sid(nome, set_code):
    return f"{set_code}-{nome.lower().replace(' ', '-')}"


def _imprimir(con, sid, nome, set_code, finishes, numero="1", reserved=0):
    con.execute(
        """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
           set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, cardmarket_id, digital,
           reserved, set_type)
           VALUES (?,?,?,?,'Test Set',?,'en','rare','Land',0,'',?,
           '1993-08-05',?,0,?,'expansion')""",
        (sid, "or-" + nome, nome, set_code, numero, json.dumps(finishes),
         sum(map(ord, sid)), reserved))


PT_SHOCKS = (("rav", ("Overgrown Tomb", "Sacred Foundry", "Temple Garden",
                      "Watery Grave")),
             ("gpt", ("Godless Shrine", "Steam Vents", "Stomping Ground")),
             ("dis", ("Blood Crypt", "Breeding Pool", "Hallowed Fountain")))


def semear(con, sem=None):
    """O catálogo mínimo das três coleções fechadas (todas as cartas, senão o
    `garantir_colecoes` levanta) e uma carta da Reserved List. `sem` é um
    (nome, set) a deixar de fora."""
    for nome in colecoes.DUALS:
        if (nome, "3ed") != sem:
            _imprimir(con, _sid(nome, "3ed"), nome, "3ed", ["nonfoil"])
    for nome in colecoes.SHOCKS + colecoes.FETCHES:
        if (nome, "exp") != sem:
            _imprimir(con, _sid(nome, "exp"), nome, "exp", ["foil"])
    for set_code, nomes in PT_SHOCKS:
        for nome in nomes:
            _imprimir(con, _sid(nome, set_code), nome, set_code, ["nonfoil"])
    _imprimir(con, RL_SID, "Moat", "leg", ["nonfoil"], reserved=1)
    con.commit()


def _preco(con, sid, acab, trend):
    prices.write_prices(con, [(sid, "cardmarket", DIA, acab, trend, trend,
                               trend, None, "EUR")])


@contextlib.contextmanager
def _pronta():
    """Sessão com o catálogo semeado e as coleções garantidas."""
    with sessao() as con:
        semear(con)
        colecoes.garantir_colecoes(con)
        yield con


def _carta(con, slug, nome):
    return next(c for c in colecoes.estado_colecao(con, slug)["cartas"]
                if c["nome"] == nome)


_n = [0]


def _marcar(con, carta_id, delta):
    _n[0] += 1
    return colecoes.ajustar(con, carta_id, delta, request_id=f"c{_n[0]}")


def _levanta(chamar):
    try:
        chamar()
    except ValueError as e:
        return str(e)
    raise AssertionError("devia levantar ValueError")


def caso_garantir_e_idempotente():
    """Duas chamadas dão as mesmas quatro coleções, pela ordem, com as cartas
    e a meta 4; o que ele já marcou (e uma meta que mudou) não se repõe."""
    with sessao() as con:
        semear(con)
        assert colecoes.garantir_colecoes(con) == 4
        assert colecoes.garantir_colecoes(con) == 0, "a segunda não cria nada"
        cs = colecoes.colecoes(con)
        assert [c["slug"] for c in cs] == ["duals_revised", "expeditions",
                                           "shocks_pt", "reserved_list"], cs
        assert [c["ordem"] for c in cs] == [1, 2, 3, 4]
        assert [c["tipo"] for c in cs] == ["fechada"] * 3 + ["aberta"]
        duals = con.execute("SELECT * FROM n_colecao_carta WHERE colecao ="
                            " 'duals_revised'").fetchall()
        assert len(duals) == 10
        assert {c["meta"] for c in duals} == {4}
        assert {c["lingua"] for c in duals} == {"en"}
        assert {c["acabamento"] for c in duals} == {"nonfoil"}
        pt = con.execute("SELECT * FROM n_colecao_carta WHERE colecao ="
                         " 'shocks_pt'").fetchall()
        assert len(pt) == 10 and {c["lingua"] for c in pt} == {"pt"}
        assert {c["meta"] for c in pt} == {4}
        exp = con.execute("SELECT * FROM n_colecao_carta WHERE colecao ="
                          " 'expeditions'").fetchall()
        assert len(exp) == 20 and {c["acabamento"] for c in exp} == {"foil"}
        assert con.execute("SELECT COUNT(*) FROM n_colecao_carta WHERE colecao"
                           " = 'reserved_list'").fetchone()[0] == 0
        # o scryfall_id é o da impressão do set pedido
        assert {c["scryfall_id"] for c in duals} == {
            _sid(n, "3ed") for n in colecoes.DUALS}
        # voltar a garantir não pisa o que ele fez
        us = _carta(con, "duals_revised", "Underground Sea")
        _marcar(con, us["id"], 3)
        colecoes.definir_meta(con, us["id"], 2)
        assert colecoes.garantir_colecoes(con) == 0
        us = _carta(con, "duals_revised", "Underground Sea")
        assert (us["tenho"], us["meta"]) == (3, 2), us


def caso_escolhe_a_impressao_de_menor_numero():
    """Com duas impressões do mesmo nome e set, ganha a de menor número (e a
    escolha não depende da ordem de inserção)."""
    with sessao() as con:
        semear(con)
        # sai a impressão da fixture e entram três: "10" < "9" como texto, mas
        # o número 9 é o menor
        con.execute("DELETE FROM catalog.cards WHERE scryfall_id ="
                    " '3ed-underground-sea'")
        _imprimir(con, "3ed-underground-sea-b", "Underground Sea", "3ed",
                  ["nonfoil"], numero="300")
        _imprimir(con, "3ed-underground-sea-0", "Underground Sea", "3ed",
                  ["nonfoil"], numero="9")
        _imprimir(con, "3ed-underground-sea-c", "Underground Sea", "3ed",
                  ["nonfoil"], numero="10")
        con.commit()
        colecoes.garantir_colecoes(con)
        us = _carta(con, "duals_revised", "Underground Sea")
        assert us["scryfall_id"] == "3ed-underground-sea-0", us["scryfall_id"]


def caso_estado_fechada():
    """Duas Underground Sea marcadas: tenho 2 de 40, a carta com falta 2; o
    que passa da meta não conta para o progresso."""
    with _pronta() as con:
        us = _carta(con, "duals_revised", "Underground Sea")
        _marcar(con, us["id"], 2)
        est = colecoes.estado_colecao(con, "duals_revised")
        assert set(est) >= {"slug", "nome", "tipo", "cartas", "tenho", "total",
                            "custo_falta", "valor_eur", "sem_preco",
                            "validadas"}, set(est)
        assert (est["tenho"], est["total"]) == (2, 40), est
        assert est["nome"] == "Duals de Revised" and est["tipo"] == "fechada"
        us = _carta(con, "duals_revised", "Underground Sea")
        assert (us["tenho"], us["meta"], us["falta"]) == (2, 4, 2), us
        assert set(us) >= {"id", "nome", "scryfall_id", "acabamento", "lingua",
                           "meta", "tenho", "falta", "vender", "preco_un",
                           "preco_visto_em", "var30", "var90", "joga",
                           "validadas", "recorte"}, set(us)
        assert us["joga"] == [] and us["validadas"] == 0 and us["recorte"] is None
        assert (us["var30"], us["var90"], us["preco_visto_em"]) == (None,) * 3
        _marcar(con, us["id"], 5)              # 7 de uma meta de 4
        est = colecoes.estado_colecao(con, "duals_revised")
        assert est["tenho"] == 4, "a sobra não conta para o progresso"
        assert _carta(con, "duals_revised", "Underground Sea")["falta"] == 0
        _levanta(lambda: colecoes.estado_colecao(con, "nao_existe"))


def caso_precos_do_estado():
    """O custo do que falta soma só onde há preço e conta o resto em
    `sem_preco`; o valor é tenho × preço; o PT não tem preço até à Tarefa 3."""
    with _pronta() as con:
        us = _carta(con, "duals_revised", "Underground Sea")
        _preco(con, us["scryfall_id"], "nonfoil", 100.0)
        _marcar(con, us["id"], 1)
        est = colecoes.estado_colecao(con, "duals_revised")
        us = _carta(con, "duals_revised", "Underground Sea")
        assert us["preco_un"] == 100.0
        assert _carta(con, "duals_revised", "Badlands")["preco_un"] is None
        assert est["custo_falta"] == 300.0, est["custo_falta"]   # 3 × 100
        assert est["valor_eur"] == 100.0, est["valor_eur"]
        assert est["sem_preco"] == 9, "as outras 9 faltam e não têm preço"
        pt = colecoes.estado_colecao(con, "shocks_pt")
        assert all(c["preco_un"] is None for c in pt["cartas"])
        assert pt["custo_falta"] == 0.0 and pt["sem_preco"] == 10, pt


def caso_ajustar_idempotente_e_sem_negativos():
    """O mesmo `request_id` duas vezes soma uma; nunca abaixo de 0."""
    with _pronta() as con:
        cid = _carta(con, "duals_revised", "Taiga")["id"]
        assert colecoes.ajustar(con, cid, 1, request_id="abc") == 1
        assert colecoes.ajustar(con, cid, 1, request_id="abc") == 1
        assert colecoes.ajustar(con, cid, 1, request_id="def") == 2
        assert colecoes.ajustar(con, cid, -5, request_id="ghi") == 0
        assert _carta(con, "duals_revised", "Taiga")["tenho"] == 0
        # o corte no zero fica visível no log: o delta é o que se aplicou
        d = con.execute("SELECT delta FROM n_colecao_log WHERE request_id ="
                        " 'ghi'").fetchone()[0]
        assert d == -2, d
        _levanta(lambda: colecoes.ajustar(con, cid, 1, request_id=""))
        _levanta(lambda: colecoes.ajustar(con, 99999, 1, request_id="zzz"))


def caso_descer_chama_o_aparar():
    """Só uma descida chama `_aparar_validadas` (a Tarefa 6 liga-o às fotos),
    com o âmbito = o slug da coleção e a quantidade nova."""
    with _pronta() as con:
        chamadas = []
        original = colecoes._aparar_validadas
        colecoes._aparar_validadas = lambda *a: chamadas.append(a)
        try:
            c = _carta(con, "duals_revised", "Plateau")
            _marcar(con, c["id"], 3)
            assert chamadas == [], "subir não apara"
            _marcar(con, c["id"], -1)
            assert chamadas == [(con, "duals_revised", c["scryfall_id"],
                                 "nonfoil", "en", 2)], chamadas
            # repetir o pedido não volta a aparar
            colecoes.ajustar(con, c["id"], -1, request_id=f"c{_n[0]}")
            assert len(chamadas) == 1
        finally:
            colecoes._aparar_validadas = original


def caso_aberta():
    """Na aberta juntam-se cartas, sem meta nem falta; `juntar` é idempotente
    e só vale na aberta; `definir_meta` também."""
    with _pronta() as con:
        cid = colecoes.juntar(con, "reserved_list", RL_SID, "nonfoil")
        assert colecoes.juntar(con, "reserved_list", RL_SID, "nonfoil") == cid
        _marcar(con, cid, 2)
        est = colecoes.estado_colecao(con, "reserved_list")
        assert est["tipo"] == "aberta" and len(est["cartas"]) == 1
        c = est["cartas"][0]
        assert c["id"] == cid and c["nome"] == "Moat" and c["tenho"] == 2
        assert c["meta"] is None and c["falta"] is None, c
        assert est["total"] is None and est["tenho"] == 2
        assert est["custo_falta"] == 0.0
        _levanta(lambda: colecoes.juntar(con, "duals_revised", RL_SID, "nonfoil"))
        _levanta(lambda: colecoes.definir_meta(con, cid, 4))
        _levanta(lambda: colecoes.juntar(con, "reserved_list", "nao-existe",
                                         "nonfoil"))
        _levanta(lambda: colecoes.juntar(con, "reserved_list", RL_SID, "foil"))
        _levanta(lambda: colecoes.juntar(con, "nao_existe", RL_SID, "nonfoil"))


def caso_meta():
    """`definir_meta` muda o total; negativa levanta."""
    with _pronta() as con:
        c = _carta(con, "duals_revised", "Bayou")
        colecoes.definir_meta(con, c["id"], 0)
        est = colecoes.estado_colecao(con, "duals_revised")
        assert est["total"] == 36, est["total"]
        assert _carta(con, "duals_revised", "Bayou")["falta"] == 0
        _levanta(lambda: colecoes.definir_meta(con, c["id"], -1))


def caso_vender():
    """`marcar_vender` liga e desliga a marca."""
    with _pronta() as con:
        cid = _carta(con, "duals_revised", "Savannah")["id"]
        assert _carta(con, "duals_revised", "Savannah")["vender"] == 0
        colecoes.marcar_vender(con, cid, True)
        assert _carta(con, "duals_revised", "Savannah")["vender"] == 1
        colecoes.marcar_vender(con, cid, False)
        assert _carta(con, "duals_revised", "Savannah")["vender"] == 0


def caso_catalogo_sem_carta():
    """Uma carta que o catálogo não tem: `ValueError` com o nome e o set, e
    nada fica gravado a meio."""
    with sessao() as con:
        semear(con, sem=("Volcanic Island", "3ed"))
        msg = _levanta(lambda: colecoes.garantir_colecoes(con))
        assert "Volcanic Island" in msg and "3ed" in msg, msg
        assert con.execute("SELECT COUNT(*) FROM n_colecao").fetchone()[0] == 0
        assert con.execute(
            "SELECT COUNT(*) FROM n_colecao_carta").fetchone()[0] == 0


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
