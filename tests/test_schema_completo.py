"""Uma base NOVA tem de ter todas as tabelas que a base do André tem.

O defeito (2026-09-09): a `deck_collection` e a `deck_meta` foram criadas à mão
no `vault.db` dele e nunca entraram no `schema.sql` nem no `db._migrate()`.
Numa base criada de raiz — a do GitHub Actions, a de outro PC, a de qualquer
teste — o `colecao_cor.build` rebentava com *"no such table: deck_collection"*.
É o irmão do `event_tier` (uma coluna que só existia num sítio), mas a estoirar
em vez de mentir: o `daily.py` dizia `[erro]` no passo e mais nada.

O que aqui se tranca:

  1. as duas tabelas existem numa base acabada de criar, e com as MESMAS colunas
     que a base dele tem (uma tabela "quase igual" volta a pôr as duas bases a
     discordar);
  2. o `colecao_cor.build` e o `webapp.regenerar` fecham nessa base;
  3. a PROVA DO DEFEITO: com as duas tabelas apagadas, o `colecao_cor` volta a
     rebentar. Sem este caso o teste passava mesmo que o `schema.sql` voltasse
     atrás, desde que outra coisa qualquer criasse a tabela.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps({
    "loadout": [], "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_colecao": {}, "spml_formatos": {},
}, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db  # noqa: E402

import colecao_cor  # noqa: E402

# A forma que as duas tabelas têm no `vault.db` do André (lido a 2026-09-09 com
# `SELECT sql FROM sqlite_master`). O teste compara COLUNAS, não o texto do SQL:
# o que tem de bater certo é o que as consultas vêem.
ESPERADO = {
    "deck_collection": ["watched_id", "sub_collection"],
    "deck_meta": ["sub_collection", "format", "pool", "priority", "active"],
}

_ABERTAS = []


def base():
    """Uma base criada SÓ pelo `db.session` — schema.sql + _migrate, nada à mão."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    return cm.__enter__()


def caso_as_tabelas_existem_numa_base_nova():
    con = base()
    for tabela, colunas in ESPERADO.items():
        tem = [r["name"] for r in con.execute(f"PRAGMA table_info({tabela})")]
        assert tem == colunas, (tabela, tem, colunas)
    print("base nova: deck_collection e deck_meta com as colunas da base dele")


def caso_o_migrate_e_idempotente():
    """A base dele JÁ tem as duas tabelas (com dados lá dentro): correr o
    `_migrate` por cima não pode apagar nem falhar. Corre duas vezes de propósito
    — o `daily.py` chama o `init` a cada passo."""
    con = base()
    con.execute("INSERT INTO deck_collection (watched_id, sub_collection) "
                "VALUES (7, 'Pauper Affinity')")
    con.commit()
    db._migrate(con)
    db._migrate(con)
    linhas = con.execute("SELECT * FROM deck_collection").fetchall()
    assert [tuple(r) for r in linhas] == [(7, "Pauper Affinity")], linhas
    print("_migrate e idempotente e nao mexe no que la esta")


def caso_o_colecao_cor_fecha_numa_base_nova():
    """Era isto que rebentava. A página não precisa de ter conteúdo — precisa de
    se escrever sem excepção, que é o que o passo `colecao-cor` do `daily` faz."""
    con = base()
    out = Path(tempfile.mkdtemp()) / "colecao_cor.html"
    colecao_cor.build(con, out)
    assert out.exists() and out.stat().st_size > 0, out
    print("colecao_cor.build fecha numa base acabada de criar")


def caso_o_webapp_fecha_numa_base_nova():
    """O modo edição reescreve as duas páginas a cada clique (`regenerar`). Numa
    base nova isso tinha de fechar também — é o mesmo passo, noutra porta."""
    import webapp
    con = base()
    antigo = webapp.ROOT
    try:
        webapp.ROOT = Path(tempfile.mkdtemp())
        webapp.regenerar(con)
        assert (webapp.ROOT / "deckboxes.html").exists()
        assert (webapp.ROOT / "metagame.html").exists()
    finally:
        webapp.ROOT = antigo
    print("webapp.regenerar fecha numa base acabada de criar")


def caso_prova_do_defeito():
    """Sem as tabelas, o `colecao_cor` volta a rebentar — é a razão de elas
    estarem no schema. Se este caso deixar de falhar, o teste de cima passou a
    provar outra coisa qualquer."""
    con = base()
    for tabela in ESPERADO:
        con.execute(f"DROP TABLE {tabela}")
    con.commit()
    out = Path(tempfile.mkdtemp()) / "colecao_cor.html"
    try:
        colecao_cor.build(con, out)
    except sqlite3.OperationalError as e:
        assert "deck_collection" in str(e), e
        print("prova do defeito: sem a tabela, o colecao_cor rebenta")
        return
    raise AssertionError("o colecao_cor devia rebentar sem a deck_collection")


def run():
    for fn in (caso_as_tabelas_existem_numa_base_nova,
               caso_o_migrate_e_idempotente,
               caso_o_colecao_cor_fecha_numa_base_nova,
               caso_o_webapp_fecha_numa_base_nova,
               caso_prova_do_defeito):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
