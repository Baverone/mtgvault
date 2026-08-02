PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------
-- COLEÇÃO
-- ---------------------------------------------------------------
-- Coleções dentro da coleção. purpose define se conta para jogar.
CREATE TABLE IF NOT EXISTS sub_collections (
    id      INTEGER PRIMARY KEY,
    name    TEXT UNIQUE NOT NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('player', 'collector', 'mixed')),
    notes   TEXT
);

-- Cada linha = um lote de exemplares físicos idênticos.
CREATE TABLE IF NOT EXISTS copies (
    id                INTEGER PRIMARY KEY,
    scryfall_id       TEXT NOT NULL,   -- -> catalog.cards
    quantity          INTEGER NOT NULL DEFAULT 1,
    finish            TEXT NOT NULL DEFAULT 'nonfoil',   -- nonfoil|foil|etched
    language          TEXT NOT NULL DEFAULT 'en',
    condition         TEXT DEFAULT 'NM',                 -- MT|NM|EX|GD|LP|PL|PO
    -- 'collector' NÃO conta para decks nem wantlist. 'player' conta.
    purpose           TEXT NOT NULL CHECK (purpose IN ('player', 'collector')),
    sub_collection_id INTEGER REFERENCES sub_collections(id),
    photo_path        TEXT,                              -- caminho local da foto
    -- Exemplares dedicados a UM deck: ficam indisponíveis para todos os
    -- outros, mesmo estando marcados como 'player'.
    reserved_deck_id  INTEGER REFERENCES decks(id) ON DELETE SET NULL,
    acquired_at       TEXT,
    acquired_price    REAL,
    notes             TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_copies_card    ON copies(scryfall_id);
CREATE INDEX IF NOT EXISTS ix_copies_purpose ON copies(purpose);

-- ---------------------------------------------------------------
-- OS MEUS DECKS
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decks (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    format     TEXT NOT NULL,
    notes      TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, format)
);

CREATE TABLE IF NOT EXISTS deck_cards (
    deck_id   INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_name TEXT NOT NULL,                          -- nome oracle
    quantity  INTEGER NOT NULL,
    board     TEXT NOT NULL DEFAULT 'main' CHECK (board IN ('main','side','maybe')),
    PRIMARY KEY (deck_id, card_name, board)
);

-- ---------------------------------------------------------------
-- DECKLISTS RECOLHIDAS (metagame)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decklists (
    id           INTEGER PRIMARY KEY,
    source       TEXT NOT NULL,          -- mtgo | mtgtop8 | topdeck | manual
    source_key   TEXT NOT NULL,          -- id único no site (evita duplicados)
    format       TEXT NOT NULL,
    event_name   TEXT,
    event_date   TEXT NOT NULL,          -- ISO YYYY-MM-DD
    player       TEXT,
    placement    TEXT,
    archetype_id INTEGER REFERENCES archetypes(id),
    url          TEXT,
    content_hash TEXT,
    fetched_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, source_key)
);
CREATE INDEX IF NOT EXISTS ix_dl_fmt_date ON decklists(format, event_date);

CREATE TABLE IF NOT EXISTS decklist_cards (
    decklist_id INTEGER NOT NULL REFERENCES decklists(id) ON DELETE CASCADE,
    card_name   TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    board       TEXT NOT NULL DEFAULT 'main' CHECK (board IN ('main','side')),
    PRIMARY KEY (decklist_id, card_name, board)
);
CREATE INDEX IF NOT EXISTS ix_dlc_name ON decklist_cards(card_name);

-- ---------------------------------------------------------------
-- ARQUÉTIPOS (clusters detetados a partir das decklists)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS archetypes (
    id         INTEGER PRIMARY KEY,
    format     TEXT NOT NULL,
    label      TEXT NOT NULL,
    signature  TEXT,                     -- JSON: cartas que definem o cluster
    first_seen TEXT,
    last_seen  TEXT,
    UNIQUE (format, label)
);

-- Resultado da análise core/tech, recalculado por janela temporal.
CREATE TABLE IF NOT EXISTS card_roles (
    archetype_id   INTEGER NOT NULL REFERENCES archetypes(id) ON DELETE CASCADE,
    window_end     TEXT NOT NULL,        -- data final da janela analisada
    window_days    INTEGER NOT NULL,
    card_name      TEXT NOT NULL,
    board          TEXT NOT NULL,
    n_lists        INTEGER NOT NULL,     -- listas na janela
    n_with_card    INTEGER NOT NULL,
    inclusion_rate REAL NOT NULL,
    avg_copies     REAL NOT NULL,        -- média entre listas que a jogam
    core_copies    INTEGER NOT NULL,     -- cópias "sempre presentes"
    flex_copies    REAL NOT NULL,        -- cópias marginais (tech)
    dist           TEXT NOT NULL,        -- JSON {"1":0.0,"2":0.0,"3":0.8,"4":0.2}
    role           TEXT NOT NULL,        -- core | flex | tech
    PRIMARY KEY (archetype_id, window_end, window_days, card_name, board)
);

-- ---------------------------------------------------------------
-- PREÇOS
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_history (
    scryfall_id TEXT NOT NULL,          -- -> catalog.cards
    source      TEXT NOT NULL,           -- cardmarket | cardtrader
    date        TEXT NOT NULL,           -- ISO YYYY-MM-DD
    finish      TEXT NOT NULL,           -- nonfoil | foil
    low         REAL,
    trend       REAL,
    avg30       REAL,
    available   INTEGER,
    currency    TEXT DEFAULT 'EUR',
    PRIMARY KEY (scryfall_id, source, date, finish)
);
CREATE INDEX IF NOT EXISTS ix_price_date ON price_history(date);

-- Mapeamento scryfall <-> cardtrader (o blueprint id não vem da Scryfall)
CREATE TABLE IF NOT EXISTS cardtrader_map (
    scryfall_id  TEXT PRIMARY KEY,      -- -> catalog.cards
    blueprint_id INTEGER NOT NULL,
    checked_at   TEXT
);

-- Registo das execuções diárias, para saber se algo falhou.
CREATE TABLE IF NOT EXISTS job_runs (
    id       INTEGER PRIMARY KEY,
    job      TEXT NOT NULL,
    started  TEXT,
    finished TEXT,
    status   TEXT,
    detail   TEXT
);

-- ---------------------------------------------------------------
-- WATCHLIST: fontes específicas a vigiar
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watched (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('mtgo_player','moxfield','archetype')),
    key          TEXT NOT NULL,      -- login MTGO | publicId Moxfield | archetype_id
    label        TEXT NOT NULL,      -- nome que dou ao baralho
    format       TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    last_checked TEXT,
    last_hash    TEXT,
    notes        TEXT,
    UNIQUE (kind, key, format)
);

-- Cada versão da lista, para poder comparar ao longo do tempo.
CREATE TABLE IF NOT EXISTS watched_snapshots (
    id         INTEGER PRIMARY KEY,
    watched_id INTEGER NOT NULL REFERENCES watched(id) ON DELETE CASCADE,
    taken_at   TEXT NOT NULL,
    list_hash  TEXT NOT NULL,
    source_url TEXT,
    cards      TEXT NOT NULL,        -- JSON [[board, nome, qty], ...]
    UNIQUE (watched_id, list_hash)
);
CREATE INDEX IF NOT EXISTS ix_snap_watch ON watched_snapshots(watched_id, taken_at);

-- Último preço conhecido de cada carta/fonte/acabamento.
-- O price_history só guarda MUDANÇAS (ver prices.write_prices), por isso esta
-- tabela é que responde a "quanto vale hoje" sem varrer o histórico.
CREATE TABLE IF NOT EXISTS price_latest (
    scryfall_id TEXT NOT NULL,
    source      TEXT NOT NULL,
    finish      TEXT NOT NULL,
    date        TEXT NOT NULL,
    low         REAL,
    trend       REAL,
    avg30       REAL,
    available   INTEGER,
    currency    TEXT DEFAULT 'EUR',
    PRIMARY KEY (scryfall_id, source, finish)
);

-- Impressão digital do conteúdo da lista, para apanhar a MESMA decklist
-- vinda de fontes diferentes (ver sources.store_decklist).
CREATE INDEX IF NOT EXISTS ix_dl_dedupe ON decklists(format, content_hash, event_date);
