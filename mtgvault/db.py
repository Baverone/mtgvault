"""Ligação às bases de dados.

DUAS BASES, DE PROPÓSITO
    vault.db    -> coleção, decks, decklists, preços, watchlist.  Pequena.
                   É esta que vai para o repositório Git.
    catalog.db  -> catálogo Scryfall (~500 mil impressões, centenas de MB).
                   Reconstruível com `sync-cards`, fica fora do repositório.

O catálogo é ATTACHed como schema `catalog`. O SQLite resolve nomes de tabela
não qualificados procurando em `main` e depois nas bases anexadas, por isso
`SELECT ... FROM cards` continua a funcionar em todo o código sem alterações.

Nota: o SQLite não suporta chaves estrangeiras entre bases de dados. As
referências de `copies.scryfall_id` para `cards` deixaram de ser FKs
declaradas — passam a ser garantidas pelo código, que valida a carta contra o
catálogo antes de inserir (ver collection.add_copy).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")
CATALOG_SCHEMA = Path(__file__).with_name("catalog_schema.sql")

ROOT = Path(os.environ.get("MTGVAULT_HOME", Path.home() / "mtgvault"))
DEFAULT_DB = Path(os.environ.get("MTGVAULT_DB", ROOT / "vault.db"))
DEFAULT_CATALOG = Path(os.environ.get("MTGVAULT_CATALOG", ROOT / "catalog.db"))


def connect(path=None, catalog=None) -> sqlite3.Connection:
    path = Path(path) if path else DEFAULT_DB
    catalog = Path(catalog) if catalog else DEFAULT_CATALOG
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("ATTACH DATABASE ? AS catalog", (str(catalog),))
    return con


def init(con: sqlite3.Connection) -> None:
    con.executescript(CATALOG_SCHEMA.read_text(encoding="utf-8"))
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    _migrate(con)
    con.executemany(
        "INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, ?)",
        [("Jogar", "player"), ("Colecionador", "collector")],
    )
    con.commit()


def _migrate(con: sqlite3.Connection) -> None:
    """Alterações de esquema em bases já criadas.

    O CREATE TABLE IF NOT EXISTS não acrescenta colunas a tabelas que já
    existem, por isso cada coluna nova precisa de entrar aqui também.
    """
    cols = {r["name"] for r in con.execute("PRAGMA table_info(copies)")}
    if "reserved_deck_id" not in cols:
        con.execute("ALTER TABLE copies ADD COLUMN reserved_deck_id INTEGER")
        con.commit()

    cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
    if "content_hash" not in cols:
        con.execute("ALTER TABLE decklists ADD COLUMN content_hash TEXT")
        con.commit()

    # Catálogo (BD anexada): a flag reserved da Reserved List. Em catálogos já
    # criados a coluna não existe — acrescenta-se aqui a 0 (o preenchimento vem
    # do bulk, via scryfall.load_bulk/backfill_reserved).
    cols = {r["name"] for r in con.execute("PRAGMA catalog.table_info(cards)")}
    if cols and "reserved" not in cols:
        con.execute("ALTER TABLE catalog.cards ADD COLUMN reserved INTEGER DEFAULT 0")
        con.commit()
    if cols and "set_type" not in cols:
        con.execute("ALTER TABLE catalog.cards ADD COLUMN set_type TEXT")
        con.commit()


def catalog_size(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COUNT(*) c FROM catalog.cards").fetchone()["c"]


@contextmanager
def session(path=None, catalog=None):
    con = connect(path, catalog)
    try:
        init(con)
        yield con
        con.commit()
    finally:
        con.close()


def log_job(con: sqlite3.Connection, job: str, status: str, detail: str = "") -> None:
    con.execute(
        "INSERT INTO job_runs (job, started, finished, status, detail) "
        "VALUES (?, datetime('now'), datetime('now'), ?, ?)",
        (job, status, detail[:2000]),
    )
    con.commit()
