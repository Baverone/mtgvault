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
    -- MODELO DE COLECÇÃO ÚNICA (André, 2026-09-07): a colecção passou a ser um
    -- balde só (`Colecção`) mais a `Caixa Reserved List`. Esta coluna guarda o
    -- balde de ONDE a cópia veio, para a aba "Arrumar" saber dizer de que
    -- gaveta a tirar hoje. Sem ela, a migração apagava a única pista física que
    -- existe. Ver `mtgvault.migracao`.
    balde_origem      TEXT,
    -- «SE NÃO MARQUEI, É PORQUE NÃO A TENHO» (André, 2026-09-09): a data em que
    -- ele procurou esta cópia para montar uma caixa e não a encontrou. Não é
    -- NULL => a cópia está FORA da colecção para todos os efeitos (loadout,
    -- cobertura, venda, valor, sugestões, galeria) e a carta volta a ser compra.
    -- Nada se apaga: a linha fica, com a foto de origem, e o «afinal encontrei»
    -- põe as duas colunas a NULL outra vez. Ver `loadout.marcar_nao_encontradas`.
    --
    -- Porque é que não é um terceiro valor do `purpose`: o CHECK dessa coluna só
    -- aceita 'player'/'collector' e mudá-lo obrigava a reconstruir a `copies`
    -- inteira numa base já feita — e a cópia não deixa de ser 'player', ela é
    -- que não está lá. Quem garante que ninguém se esquece de a filtrar é o
    -- `collection.jogaveis()`, que é o único sítio onde este WHERE se escreve.
    nao_encontrada_em   TEXT,
    -- O `slot` da caixa que ele estava a montar quando faltou. É a única pista
    -- de ONDE ela devia estar, e não se deriva de mais nada.
    nao_encontrada_slot TEXT,
    -- REVALIDAÇÃO POR FOTO (André, 2026-09-20): *"quero revalidar todas as
    -- fotos agora que vamos colocar tudo em decks para que nada falhe ou
    -- escape"*. A partir de `revalidacao.desde` (config) NENHUMA cópia está
    -- validada até uma foto NOVA lhe ser ligada. `validado_em` é a data em que
    -- isso aconteceu (NULL = por revalidar); `foto_anterior` é o `photo_path`
    -- que a foto nova substituiu — a foto antiga NÃO se apaga, fica em «fotos
    -- processadas» como sempre. Não muda um único número da alocação/venda: é
    -- só o estado 📷/✓ que a página mostra. Ver `mtgvault.revalidacao`.
    validado_em       TEXT,
    foto_anterior     TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_copies_card    ON copies(scryfall_id);
CREATE INDEX IF NOT EXISTS ix_copies_purpose ON copies(purpose);
-- NÃO se declara aqui um índice sobre a `nao_encontrada_em` (2026-09-09). Este
-- ficheiro corre INTEIRO antes do `db._migrate()`, e numa base já criada a
-- coluna ainda não existe nesse momento: um `CREATE INDEX` sobre ela rebentava
-- o `db.init` com *"no such column"* — em TODAS as páginas e no `daily`. O
-- `CREATE TABLE IF NOT EXISTS` é indiferente à ordem, um índice sobre uma coluna
-- nova não é. (E o índice não faz falta: quem filtra é o `collection.jogaveis`,
-- que já traz o `purpose` e usa o `ix_copies_purpose`.) Se algum dia for
-- preciso, tem de nascer no `_migrate`, depois do ALTER.
-- O mesmo para o `ix_copies_validado` sobre a `validado_em` (2026-09-20): vive
-- no `db._migrate`, depois do ALTER — aqui rebentava a base dele.

-- ONDE A CÓPIA ESTÁ FISICAMENTE, quando está dentro de uma deckbox.
--
-- Desde 2026-09-07 as deckboxes deixaram de ser `sub_collections`: a colecção é
-- um balde só e a caixa de um deck é a ALOCAÇÃO do loadout. Esta tabela é a
-- alocação CONFIRMADA — o que o André já sleevou e arrumou. O loadout continua
-- a recalcular todos os dias onde cada carta DEVE estar; a diferença entre as
-- duas é exactamente a lista de arrumação (`loadout.plano_arrumacao`).
--
-- Uma linha por (lote, caixa): um lote de 4 pode ter 3 numa caixa e 1 solto.
CREATE TABLE IF NOT EXISTS copy_allocation (
    copy_id    INTEGER NOT NULL REFERENCES copies(id) ON DELETE CASCADE,
    slot       TEXT NOT NULL,          -- `slot` do colecao_config.json -> loadout
    quantity   INTEGER NOT NULL,
    placed_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (copy_id, slot)
);
CREATE INDEX IF NOT EXISTS ix_alloc_slot ON copy_allocation(slot);

-- ENCOMENDAS (André, 2026-09-19): «SÓ A FOTO CRIA CÓPIAS».
--
-- *"dizia-te o que ia comprando, e tu só ias pedindo as fotos das cartas; cada
-- vez que eu adiciono que tenho a carta, fica pendente de foto; quando coloco
-- a foto, adicionas à coleção."* Uma encomenda NÃO é uma cópia: não conta para
-- o valor, para a venda, para a galeria nem para nada que conte cartas. O que
-- faz é DESCONTAR o «a comprar» da caixa a que pertence — o que está
-- encomendado já não é para comprar. O caminho: `qty_a_caminho` (o `+`) →
-- `qty_pendente_foto` (o «Chegou», ou o «já a tenho» directo) → a foto entra
-- em `pendentes/`, o import cria a cópia, fecha a encomenda (`qty_fechada`,
-- `copy_ids`) e aloca a cópia à caixa. Ver `mtgvault.encomendas`.
--
-- Sem `set_code` = qualquer impressão que cumpra a regra da caixa. `slot` a
-- NULL = para a colecção, sem caixa. Uma linha por (carta, impressão, língua,
-- acabamento, caixa); o `+` de uma linha igual soma em vez de criar outra.
CREATE TABLE IF NOT EXISTS encomendas (
    id                INTEGER PRIMARY KEY,
    card_name         TEXT NOT NULL,          -- nome oracle (a frente, como as listas)
    set_code          TEXT,
    collector_number  TEXT,
    lang              TEXT NOT NULL DEFAULT 'en',
    finish            TEXT NOT NULL DEFAULT 'nonfoil',
    slot              TEXT,                   -- `slot` da caixa (chave da copy_allocation)
    qty_a_caminho     INTEGER NOT NULL DEFAULT 0,
    qty_pendente_foto INTEGER NOT NULL DEFAULT 0,
    qty_fechada       INTEGER NOT NULL DEFAULT 0,  -- o que a foto já transformou em cópia
    copy_ids          TEXT,                   -- JSON: as cópias que a fecharam
    origem            TEXT,                   -- texto livre: a loja
    preco_unit        REAL,
    notas             TEXT,
    aviso             TEXT,                   -- ex.: a foto trouxe uma impressão que a caixa recusa
    criado_em         TEXT DEFAULT CURRENT_TIMESTAMP,
    actualizado_em    TEXT DEFAULT CURRENT_TIMESTAMP
);
-- A tabela NASCE aqui inteira, e por isso o índice pode viver neste ficheiro
-- (a regra de 2026-09-09 é para índices sobre COLUNAS NOVAS de tabelas que
-- já existem — essas só no `_migrate`, depois do ALTER).
CREATE INDEX IF NOT EXISTS ix_encomendas_slot ON encomendas(slot);
CREATE INDEX IF NOT EXISTS ix_encomendas_card ON encomendas(card_name);

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
    event_players INTEGER,                 -- nº de jogadores (peso do evento)
    -- Importância do evento: Showcase | Challenge | Qualifier | Preliminary |
    -- League | Presencial | outro. É por esta coluna que o metagame conta só
    -- Challenges/Showcases (meta_coverage) e que o consenso exclui as Leagues
    -- (buildable). Preenchida em sources.store_decklist / backfill_event_tiers.
    event_tier   TEXT,
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

-- Liga uma lista vigiada ao balde onde as cartas desse deck vivem.
-- (2026-09-09) Esta tabela e a `deck_meta` existiam SÓ no vault.db do André:
-- foram criadas à mão e nunca entraram aqui nem no `db._migrate()`. Numa base
-- nova o `colecao_cor._watched_deck_pools` rebentava com "no such table:
-- deck_collection" — o padrão do `event_tier`, mas a estoirar em vez de mentir.
-- A definição é copiada TAL E QUAL da base dele (sem FK sobre `watched`), para
-- uma base nova e a dele terem o mesmo esquema.
CREATE TABLE IF NOT EXISTS deck_collection (
    watched_id     INTEGER PRIMARY KEY,
    sub_collection TEXT NOT NULL
);

-- Metadados por balde, do tempo em que as preferências dos decks viviam na base.
-- HOJE NÃO É LIDA POR NINGUÉM: a decisão de 2026-09-07 foi que o que é
-- preferência vive no `colecao_config.json` e o que é físico na
-- `copy_allocation` (ver o cabeçalho do `webapp.py`). Fica declarada porque
-- existe na base dele e o `schema.sql` tem de a descrever — não porque alguma
-- página dependa dela.
CREATE TABLE IF NOT EXISTS deck_meta (
    sub_collection TEXT PRIMARY KEY,
    format         TEXT,
    pool           TEXT,
    priority       INTEGER,
    active         INTEGER DEFAULT 1
);

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
