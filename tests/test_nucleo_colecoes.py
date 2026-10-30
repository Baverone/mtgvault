"""As tabelas novas do núcleo: a Coleção (`n_colecao`, `n_colecao_carta`,
`n_colecao_log`), as fotos (`n_foto`, `n_recorte`, `n_validacao`), o preço PT e o
preço vigiado (`n_preco_pt`, `n_preco_vigiado`), as jogadas (`n_jogada`) e a
coluna `n_valor.colecoes_eur`.

Nada aqui abre a base do André: cada caso constrói a sua base temporária
(`db.session(tmp/"v.db", tmp/"c.db")`).
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db  # noqa: E402

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


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
