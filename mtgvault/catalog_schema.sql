-- Catálogo Scryfall. Vive numa base de dados SEPARADA (catalog.db) porque
-- passa dos 100 MB por ficheiro que o GitHub aceita. É reconstruível a
-- qualquer momento com `sync-cards`, por isso nunca vai para o repositório —
-- fica na cache do Actions.
CREATE TABLE IF NOT EXISTS catalog.cards (
    scryfall_id      TEXT PRIMARY KEY,
    oracle_id        TEXT NOT NULL,
    name             TEXT NOT NULL,          -- nome oracle (inglês)
    set_code         TEXT NOT NULL,
    set_name         TEXT,
    collector_number TEXT,
    lang             TEXT,
    rarity           TEXT,
    type_line        TEXT,
    mana_cost        TEXT,
    cmc              REAL,
    color_identity   TEXT,
    finishes         TEXT,                   -- JSON: ["nonfoil","foil"]
    released_at      TEXT,
    cardmarket_id    INTEGER,                -- idProduct do Cardmarket
    tcgplayer_id     INTEGER,
    image_uri        TEXT,
    legalities       TEXT,                   -- JSON
    digital          INTEGER DEFAULT 0,
    reprint          INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS catalog.ix_cards_name   ON cards(name);
CREATE INDEX IF NOT EXISTS catalog.ix_cards_oracle ON cards(oracle_id);
CREATE INDEX IF NOT EXISTS catalog.ix_cards_cm     ON cards(cardmarket_id);
CREATE INDEX IF NOT EXISTS catalog.ix_cards_set    ON cards(set_code, collector_number);
