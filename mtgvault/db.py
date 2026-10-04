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
# Quanto tempo uma ligação espera por quem está a escrever antes de dizer
# «database is locked». Ver o comentário no `connect`.
BUSY_TIMEOUT_MS = int(os.environ.get("MTGVAULT_BUSY_TIMEOUT_MS") or 15000)
DEFAULT_CATALOG = Path(os.environ.get("MTGVAULT_CATALOG", ROOT / "catalog.db"))


def pasta_dados() -> Path:
    """A pasta AO LADO DA BASE, onde vivem os ficheiros que a acompanham
    (`vendas.csv`, `arquetipos.json`).

    Não é o `ROOT`, e a diferença morde: neste PC o `MTGVAULT_HOME` **não está
    definido** — só o `MTGVAULT_DB`, que aponta para o `data/` do repositório.
    Pelo `ROOT` esses ficheiros iam parar a `~/mtgvault`, fora do repositório: o
    `git add data/arquetipos.json` do `daily.yml` não encontrava nada, o registo
    nunca era publicado e os nomes voltavam a mudar de um dia para o outro. Sem
    um único erro — é o padrão do `event_tier`. O `.gitignore` já dizia qual era
    a intenção (tem lá `data/vendas.csv`).

    Com o `MTGVAULT_HOME` definido e sem `MTGVAULT_DB`, dá exactamente o mesmo
    que dava: `DEFAULT_DB` é `ROOT/vault.db` e o pai é o `ROOT`.
    """
    return Path(DEFAULT_DB).parent


def connect(path=None, catalog=None) -> sqlite3.Connection:
    path = Path(path) if path else DEFAULT_DB
    catalog = Path(catalog) if catalog else DEFAULT_CATALOG
    path.parent.mkdir(parents=True, exist_ok=True)
    catalog.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    # ESPERAR POR QUEM ESTÁ A ESCREVER, EM VEZ DE DESISTIR (2026-10-01). O
    # `vault.db` tem três escritores: o `webapp.py` (os botões dele), o `daily`
    # das 03:30 e as ordens do runner. O `timeout` do `sqlite3.connect` são 5 s
    # por omissão e só vale para a ligação `main`; o `PRAGMA busy_timeout`
    # aplica-se à ligação INTEIRA, o `catalog` anexado incluído. Sem isto, uma
    # ordem a escrever durante seis segundos dava *"database is locked"* a uma
    # página — um erro a sério por uma coisa que só precisava de esperar.
    #
    # O tecto do pedido HTTP está ACIMA deste de propósito (`webapp.ESPERA_DADOS`):
    # primeiro espera-se por quem escreve, e só se mesmo assim não der é que se
    # responde. Um `busy_timeout` maior do que o tecto do pedido punha o pedido a
    # desistir sempre antes de a base ter a oportunidade de responder.
    con.execute(f"PRAGMA busy_timeout = {int(BUSY_TIMEOUT_MS)}")
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
    # Modelo de colecção única (2026-09-07): o balde de onde a cópia veio, para a
    # aba "Arrumar" saber de que gaveta a tirar. Uma coluna nova tem de entrar
    # nos três sítios (schema.sql, aqui, e alguém que a escreva) — ver CLAUDE.md.
    if "balde_origem" not in cols:
        con.execute("ALTER TABLE copies ADD COLUMN balde_origem TEXT")
        con.commit()
    # «Não encontrei estas» (André, 2026-09-09): a cópia está na base, tem foto,
    # e não está na estante. Duas colunas — quando faltou e a que caixa. Quem as
    # LÊ é o `collection.jogaveis()`, num sítio só; sem esse filtro a cópia
    # continuava a contar e a página voltava a dizer-lhe que tem a carta.
    if "nao_encontrada_em" not in cols:
        con.execute("ALTER TABLE copies ADD COLUMN nao_encontrada_em TEXT")
        con.execute("ALTER TABLE copies ADD COLUMN nao_encontrada_slot TEXT")
        con.commit()
    # REVALIDAÇÃO POR FOTO (André, 2026-09-20): a data em que uma foto NOVA se
    # ligou à cópia (NULL = por revalidar) e a foto que ela substituiu. O índice
    # nasce AQUI, depois do ALTER, e nunca no `schema.sql` — esse corre inteiro
    # antes disto, e numa base já criada a coluna ainda não existe nesse momento
    # (é a armadilha de 2026-09-09, que rebentava o `db.init` em todas as
    # páginas). Quem escreve é o `mtgvault.revalidacao` + `collection.add_copy`.
    if "validado_em" not in cols:
        con.execute("ALTER TABLE copies ADD COLUMN validado_em TEXT")
        con.execute("ALTER TABLE copies ADD COLUMN foto_anterior TEXT")
        con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS ix_copies_validado "
                "ON copies(validado_em)")
    con.commit()
    # O ESTADO DAS CARTAS (André, 2026-10-03). A coluna `condition` já existia e
    # dizia `NM` nas 737 linhas — o valor por omissão do `add_copy`, nunca
    # verificado. Estas quatro dizem o que faltava: de onde veio o juízo, quando,
    # com que motivos, e a foto do VERSO. **O `NM` não se muda nem se apaga**
    # (regra dele de 09/09): o que se escreve é a ORIGEM `omissao`, que é o que o
    # faz deixar de poder passar por medido (`estado.medido`). O índice nasce
    # AQUI, depois do ALTER — a armadilha de 2026-09-09.
    if "condition_origem" not in cols:
        con.execute("ALTER TABLE copies ADD COLUMN condition_origem TEXT")
        con.execute("ALTER TABLE copies ADD COLUMN condition_em TEXT")
        con.execute("ALTER TABLE copies ADD COLUMN condition_motivos TEXT")
        con.execute("ALTER TABLE copies ADD COLUMN verso_path TEXT")
        con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS ix_copies_cond_origem "
                "ON copies(condition_origem)")
    con.commit()
    # O `omissao` escreve-se aqui, mas **só quando há mesmo linhas a marcar**: um
    # `UPDATE` incondicional a cada `init` era uma escrita por pedido do
    # `webapp.py`, e uma escrita muda o `_versao()` e atira a cache fora — foi
    # exactamente o que o `-wal` vazio fez a 2026-10-01. O `SELECT` entra pelo
    # índice que acabou de nascer.
    if con.execute("SELECT 1 FROM copies WHERE condition_origem IS NULL "
                   "OR TRIM(condition_origem) = '' LIMIT 1").fetchone():
        con.execute("UPDATE copies SET condition_origem = 'omissao' "
                    "WHERE condition_origem IS NULL "
                    "OR TRIM(condition_origem) = ''")
        con.commit()

    # O MODO DE PREÇO (2026-09-25): a `receita` diz como é que o `low` e o
    # `trend` desta linha foram produzidos. As linhas que já lá estão ficam a
    # NULL e valem `unico` (ver `precos.receita_em_vigor`) — que é o que elas
    # SÃO: o bulk da Scryfall escreve o mesmo número nas duas colunas. Marcá-las
    # com uma receita que nunca tiveram era inventar histórico.
    for tabela in ("price_latest", "price_history"):
        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({tabela})")}
        if cols and "receita" not in cols:
            con.execute(f"ALTER TABLE {tabela} ADD COLUMN receita TEXT")
            con.commit()

    cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
    if "content_hash" not in cols:
        con.execute("ALTER TABLE decklists ADD COLUMN content_hash TEXT")
        con.commit()
    if "event_players" not in cols:   # nº de jogadores do evento (peso), do mtgtop8
        con.execute("ALTER TABLE decklists ADD COLUMN event_players INTEGER")
        con.commit()
    # A coluna foi acrescentada à mão ao vault.db em 2026-08-03 e nunca entrou
    # aqui nem no schema.sql. Resultado: numa base nova as páginas do metagame
    # rebentavam, e nas antigas as listas novas ficavam com event_tier a NULL —
    # o top-10 vinha vazio e o passo diário na mesma dizia "ok".
    if "event_tier" not in cols:
        con.execute("ALTER TABLE decklists ADD COLUMN event_tier TEXT")
        con.commit()
    # O COMANDANTE da lista (2026-10-01). Em Duel Commander a identidade do deck
    # é o comandante, e a etiqueta do clustering não serve para nada aqui (870
    # etiquetas, 808 sem listas). As duas colunas andam juntas: o nome e a FONTE
    # do nome (`sideboard` = veio do sideboard da fonte; `ordem` = derivado).
    # O índice nasce AQUI, depois do ALTER, e nunca no `schema.sql`: esse corre
    # inteiro antes disto e numa base já criada a coluna ainda não existe — é a
    # armadilha de 2026-09-09, que rebentava o `db.init` em todas as páginas.
    if "commander" not in cols:
        con.execute("ALTER TABLE decklists ADD COLUMN commander TEXT")
        con.execute("ALTER TABLE decklists ADD COLUMN commander_fonte TEXT")
        con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS ix_dl_commander "
                "ON decklists(format, commander)")
    con.commit()
    # O NOME DO ARQUÉTIPO QUE A FONTE DÁ (2026-10-02). As duas colunas andam
    # juntas, como as do comandante: o nome e COMO se chegou a ele (`evento` /
    # `recuperado` / `sem-nome`). O índice nasce AQUI, depois do ALTER, e nunca
    # no `schema.sql` — esse corre inteiro antes disto e numa base já criada a
    # coluna ainda não existe nesse momento; é a armadilha de 2026-09-09, que
    # rebentava o `db.init` com *"no such column"* em todas as páginas e no
    # `daily`. Aconteceu com o `ix_copies_validado` e com o `ix_dl_commander`.
    if "arquetipo_fonte" not in cols:
        con.execute("ALTER TABLE decklists ADD COLUMN arquetipo_fonte TEXT")
        con.execute("ALTER TABLE decklists ADD COLUMN arquetipo_fonte_de TEXT")
        con.commit()
    con.execute("CREATE INDEX IF NOT EXISTS ix_dl_arquetipo "
                "ON decklists(format, arquetipo_fonte)")
    con.commit()

    # Tabelas que existiam SÓ na vault.db do André (criadas à mão, nunca no
    # schema.sql). Numa base nova o colecao_cor rebentava com "no such table:
    # deck_collection". Aqui é para as bases JÁ criadas — o schema.sql trata das
    # novas, e as duas definições têm de ser iguais.
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
        watched_id     INTEGER PRIMARY KEY,
        sub_collection TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS deck_meta (
        sub_collection TEXT PRIMARY KEY,
        format         TEXT,
        pool           TEXT,
        priority       INTEGER,
        active         INTEGER DEFAULT 1
    )""")
    con.commit()

    # A MEMÓRIA DOS EVENTOS DO MTGTOP8 (2026-10-04). O `schema.sql` cria-a numa
    # base nova; isto é para a base dele, que já existe. As duas definições têm de
    # ser iguais — é a regra do `deck_collection`.
    con.execute("""CREATE TABLE IF NOT EXISTS mtgtop8_eventos (
        event_id   INTEGER NOT NULL,
        format     TEXT NOT NULL,
        event_name TEXT,
        event_date TEXT,
        grande     INTEGER NOT NULL DEFAULT 0,
        players    INTEGER,
        na_pagina  INTEGER,
        tecto      INTEGER NOT NULL DEFAULT 0,
        completo   INTEGER NOT NULL DEFAULT 0,
        visto_em   TEXT,
        PRIMARY KEY (event_id, format)
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_mt8_grande "
                "ON mtgtop8_eventos(grande, visto_em)")
    con.commit()
    # Quem a SEMEIA a partir das listas que já cá estão é o
    # `mtgtop8.semear_memoria`, e não este ficheiro: a semente precisa do
    # `e_grande` e do `TECTO_ANTIGO`, e importar o `mtgtop8` aqui fechava um ciclo
    # (`mtgtop8` → `sources`/`consenso` → `db`). O `_migrate` trata do esquema; a
    # recolha trata do que a recolha sabe.

    # ENCOMENDAS (2026-09-19). O `schema.sql` cria a tabela numa base nova e
    # numa antiga (é `IF NOT EXISTS`); isto é para as colunas que lhe venham a
    # ser acrescentadas DEPOIS de existir na base dele — a mesma regra de
    # sempre: uma coluna nova entra nos três sítios. Hoje não há nenhuma; a
    # lista fica escrita para o primeiro `ALTER` ter onde cair.
    cols = {r["name"] for r in con.execute("PRAGMA table_info(encomendas)")}
    for coluna, tipo in ():
        if coluna not in cols:
            con.execute(f"ALTER TABLE encomendas ADD COLUMN {coluna} {tipo}")
            con.commit()

    # A VIGIA DE UM ARQUÉTIPO DO MTGTOP8 (André, 2026-10-04): o `kind`
    # `mtgtop8_archetype`. É a PRIMEIRA reconstrução de tabela deste ficheiro, e
    # é por uma razão que não tem outra saída: o que muda é um **CHECK**, e o
    # SQLite não tem `ALTER TABLE ... ALTER CONSTRAINT`. Um `kind` novo sem isto
    # dava `IntegrityError: CHECK constraint failed` no `watchlist.add` — a vigia
    # não se inscrevia, e inscrever-se a meio era pior (ver o `check_all`).
    #
    # DUAS ARMADILHAS, e as duas mordem:
    #   1. **as FK estão LIGADAS** (`connect` faz `PRAGMA foreign_keys = ON`) e a
    #      `watched_snapshots` referencia a `watched` com **ON DELETE CASCADE**:
    #      um `DROP TABLE watched` apagava o histórico todo das listas vigiadas
    #      (15 snapshots na base dele). Desliga-se durante a troca e volta-se a
    #      ligar no fim, com `foreign_key_check` a confirmar.
    #   2. **o PRAGMA é um no-op dentro de uma transacção** — por isso o `commit`
    #      antes. Sem ele o `PRAGMA` passava sem efeito e o CASCADE disparava.
    #
    # A contagem é conferida antes e depois: uma migração que perca uma linha
    # levanta aqui, em vez de deixar o André sem a lista que vigiava.
    sql_watched = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='watched'"
    ).fetchone()
    if sql_watched and "mtgtop8_archetype" not in (sql_watched["sql"] or ""):
        antes = con.execute("SELECT COUNT(*) c FROM watched").fetchone()["c"]
        snaps = con.execute("SELECT COUNT(*) c FROM watched_snapshots").fetchone()["c"]
        con.commit()                       # o PRAGMA não vale em transacção
        con.execute("PRAGMA foreign_keys = OFF")
        con.executescript("""
            CREATE TABLE watched_nova (
                id           INTEGER PRIMARY KEY,
                kind         TEXT NOT NULL CHECK (kind IN ('mtgo_player','moxfield','archetype','mtgtop8_archetype')),
                key          TEXT NOT NULL,
                label        TEXT NOT NULL,
                format       TEXT NOT NULL,
                active       INTEGER NOT NULL DEFAULT 1,
                last_checked TEXT,
                last_hash    TEXT,
                notes        TEXT,
                UNIQUE (kind, key, format)
            );
            INSERT INTO watched_nova (id, kind, key, label, format, active,
                                      last_checked, last_hash, notes)
                SELECT id, kind, key, label, format, active,
                       last_checked, last_hash, notes FROM watched;
            DROP TABLE watched;
            ALTER TABLE watched_nova RENAME TO watched;
        """)
        con.commit()
        con.execute("PRAGMA foreign_keys = ON")
        depois = con.execute("SELECT COUNT(*) c FROM watched").fetchone()["c"]
        snaps2 = con.execute("SELECT COUNT(*) c FROM watched_snapshots").fetchone()["c"]
        if (antes, snaps) != (depois, snaps2):
            raise RuntimeError(
                f"migração da `watched` perdeu linhas: {antes}->{depois} vigias, "
                f"{snaps}->{snaps2} snapshots — a base está no backup")
        orfaos = list(con.execute("PRAGMA foreign_key_check"))
        if orfaos:
            raise RuntimeError(f"migração da `watched` deixou órfãos: {orfaos[:3]}")

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
    # O TEXTO DA CARTA (2026-10-01). Entra para as quatro protecções da venda
    # poderem DERIVAR do catálogo as shocklands e as fetchlands, em vez de as
    # terem escritas à mão (ver `mtgvault/fases.py`). Num catálogo já criado a
    # coluna nasce a NULL e o preenchimento vem do bulk (`scryfall.load_bulk`) —
    # como aconteceu com o `reserved` e o `set_type`. Por isso é que o
    # `fases.fetchlands` **levanta** quando não encontra as dez em vez de
    # devolver uma lista curta: um catálogo por sincronizar tem de dar erro alto,
    # não uma protecção vazia em silêncio (o padrão do `event_tier`).
    if cols and "oracle_text" not in cols:
        con.execute("ALTER TABLE catalog.cards ADD COLUMN oracle_text TEXT")
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
