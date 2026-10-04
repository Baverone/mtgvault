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
    -- O ESTADO DAS CARTAS (André, 2026-10-03): *"procuras como são avaliadas as
    -- cartas, depois com base nas minhas próprias fotos, vais melhorando o teu
    -- critério"*. A coluna `condition` já existia e dizia **NM em todas as 737
    -- linhas** — não era uma medição, era o valor por omissão do `add_copy` que
    -- nunca ninguém mexeu. Estas três dizem o que lhe faltava:
    --   `condition_origem`  foto | mao | omissao — de onde veio o juízo. É o que
    --                       faz o `NM` de fábrica deixar de poder passar por
    --                       medido (`estado.medido`). O valor NÃO se mudou nem
    --                       se apagou (regra dele de 09/09): só ganhou a origem.
    --   `condition_em`      o dia do juízo.
    --   `condition_motivos` os motivos ESCRITOS («branco visível no canto
    --                       inferior esquerdo») — um escalão sem motivo não se
    --                       pode conferir nem corrigir.
    -- O histórico (e os exemplos rotulados das correcções dele) vive na
    -- `condition_log`, abaixo. Ver `mtgvault.estado`.
    condition_origem  TEXT,
    condition_em      TEXT,
    condition_motivos TEXT,
    -- OS VERSOS (André, 2026-10-03): *"verso as dos decks e as que são para
    -- guardar, para já"*. A foto do VERSO desta cópia. **O verso não identifica
    -- a carta** — todos os versos de Magic são iguais —, serve para ver o
    -- desgaste que a frente não mostra; é de lá que sai o escalão, e sem ele o
    -- estado fica «por verificar». O emparelhamento frente/verso faz-se pelo
    -- NOME do ficheiro (o mesmo radical, com `-v`), nunca por ele escrever
    -- nada — ver `mtgvault.fotosite.par_da_frente`.
    verso_path        TEXT,
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
-- no `db._migrate`, depois do ALTER — aqui rebentava a base dele. E o mesmo para
-- o `ix_copies_cond_origem` (2026-10-03).

-- O HISTÓRICO DOS JUÍZOS DE ESTADO, e os EXEMPLOS ROTULADOS (2026-10-03).
--
-- É a metade de *"com base nas minhas próprias fotos, vais melhorando o teu
-- critério"* que não cabe numa coluna da `copies`: a `copies` guarda o estado de
-- HOJE, e isto guarda **como se chegou lá** e **o que me escapou**.
--
-- Uma linha por juízo, incluindo os que NÃO se aplicaram (`aplicado = 0`): um
-- juízo meu sobre uma cópia que o André já tinha corrigido à mão é recusado — a
-- correcção dele ganha sempre — e tem de ficar registado, senão a taxa de acerto
-- (`estado.acerto`) não se podia calcular.
--
-- Quando o André corrige, a linha leva também o `eu_disse`/`eu_motivos` (o que
-- eu tinha dito) e o `escapou` (a linha do que me passou ao lado). É esse trio —
-- foto + o meu escalão + o dele + o porquê — que faz dela um EXEMPLO ROTULADO, e
-- é o que o `estado.para_avaliar` lê antes de julgar outra vez.
CREATE TABLE IF NOT EXISTS condition_log (
    id           INTEGER PRIMARY KEY,
    copy_id      INTEGER NOT NULL REFERENCES copies(id) ON DELETE CASCADE,
    at           TEXT NOT NULL,
    grade        TEXT NOT NULL,          -- MT|NM|EX|GD|LP|PL|PO
    antes        TEXT,                   -- o escalão que lá estava
    antes_origem TEXT,                   -- foto|mao|omissao
    origem       TEXT NOT NULL,          -- foto|mao|omissao
    autor        TEXT,                   -- claude|andre
    photo_path   TEXT,                   -- a foto em que o juízo se baseou
    motivos      TEXT,                   -- os motivos ESCRITOS deste juízo
    eu_disse     TEXT,                   -- (numa correcção) o meu escalão
    eu_motivos   TEXT,                   -- (numa correcção) os meus motivos
    escapou      TEXT,                   -- (numa correcção) o que me escapou
    aplicado     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_cond_log_copia ON condition_log(copy_id);
CREATE INDEX IF NOT EXISTS ix_cond_log_origem ON condition_log(origem, aplicado);

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
    -- O COMANDANTE da lista, nos formatos de comandante (2026-10-01). Em Duel
    -- Commander a identidade de um deck é o COMANDANTE e nunca a etiqueta do
    -- clustering: na base de 01/10 havia 870 etiquetas de duel-commander, 808
    -- delas sem uma única lista. Guarda-se em vez de se recalcular a cada
    -- corrida, e o `commander_fonte` diz COMO foi obtido — `sideboard` (a fonte
    -- serve o comandante no sideboard: é o `SB:` do .dec do mtgtop8 e o
    -- `sideboard_deck` do mtgo.com) ou `ordem` (derivado pela ordem de inserção
    -- das cartas, para as listas que já estavam na base — ver mtgvault/consenso.py).
    commander       TEXT,
    commander_fonte TEXT,
    -- O NOME DO ARQUÉTIPO QUE A FONTE DÁ (2026-10-02). O mtgtop8 escreve-o na
    -- página do evento, ao lado de cada deck ("#2 Landstill - Vittorio Piatti",
    -- e o link <a ...>Landstill</a>), e a recolha deitava-o fora: havia 2 635
    -- listas de `mtgtop8` na base e nenhuma coluna onde o nome estivesse. O que
    -- sobrava era o `archetypes.label` do clustering — *"Solitary Confinement /
    -- Argothian Enchantress / Sterling Grove"* —, com dezenas de etiquetas
    -- parecidas e vazias. É a MESMA falha do `commander`, corrigida a
    -- 2026-10-01: a fonte dá a informação e a recolha perde-a.
    --
    -- `arquetipo_fonte_de` diz COMO se chegou ao nome, e é também o marcador de
    -- progresso do backfill: `evento` (lido na recolha, da página do evento),
    -- `recuperado` (lido depois, pelo `mtgtop8.backfill_archetype_names`) ou
    -- `sem-nome` (a página do evento foi lida e não trazia nome para este deck —
    -- com o nome a NULL, para não se voltar a pedir a mesma página todos os dias;
    -- é o mesmo truque do `event_players` a gravar 0).
    arquetipo_fonte     TEXT,
    arquetipo_fonte_de  TEXT,
    fetched_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, source_key)
);
CREATE INDEX IF NOT EXISTS ix_dl_fmt_date ON decklists(format, event_date);
-- O índice do `commander` NÃO vive aqui, e a tentativa custou uma corrida: este
-- ficheiro corre INTEIRO antes do `db._migrate()`, e numa base já criada a
-- coluna ainda não existe neste momento — o `CREATE INDEX` rebentava o `db.init`
-- com *"no such column: commander"*, em todas as páginas e no `daily`. O
-- `CREATE TABLE IF NOT EXISTS` é indiferente à ordem; um índice não é. É a mesma
-- armadilha de 2026-09-09 (o `ix_copies_validado`), e está no `_migrate`.
-- O mesmo vale para o índice do `arquetipo_fonte` (2026-10-02).

-- A MEMÓRIA DOS EVENTOS DO MTGTOP8 (2026-10-04). Nasceu com o «nunca perder um
-- torneio de papel grande»: a recolha passou a ler VÁRIAS páginas do índice
-- (`?f=MO&cp=2`, 58 eventos em Modern contra 20), e sem memória descer no índice
-- custava um pedido por evento já feito, todas as noites.
--
-- O progresso de um evento NÃO podia ser a tabela `decklists`, como no
-- `arquetipo_fonte_de`: um evento cujas listas foram todas deduplicadas contra o
-- mtgo.com não deixa lá uma única linha, e é precisamente esse que se voltaria a
-- pedir sempre.
--
-- `tecto` é o nº máximo de listas que se leu deste evento, e é o que torna isto
-- auto-corrigível: um evento visto com o tecto antigo (16) e que hoje é
-- reconhecido como grande (64) volta a ser visitado **uma vez** e fica completo.
-- Sem essa coluna, as 48 listas que faltam ao RC que já está na base precisavam
-- de um passo à mão.
CREATE TABLE IF NOT EXISTS mtgtop8_eventos (
    event_id   INTEGER NOT NULL,
    format     TEXT NOT NULL,
    event_name TEXT,
    event_date TEXT,
    -- 1 = o nome casou um padrão de torneio de papel grande (mtgtop8.e_grande).
    grande     INTEGER NOT NULL DEFAULT 0,
    players    INTEGER,
    -- Quantos links de deck a página tinha, e quantos se leram (o tecto aplicado).
    na_pagina  INTEGER,
    tecto      INTEGER NOT NULL DEFAULT 0,
    -- 1 = a página não tinha mais decks do que o tecto, logo não falta nada.
    completo   INTEGER NOT NULL DEFAULT 0,
    visto_em   TEXT,
    PRIMARY KEY (event_id, format)
);
CREATE INDEX IF NOT EXISTS ix_mt8_grande
    ON mtgtop8_eventos(grande, visto_em);

-- A POSSE QUE ELE MARCA À MÃO, com o `+` e o `−` (André, 2026-10-04).
--
-- NASCE VAZIA de propósito, e é isso que faz o inventário PRÉ-PREENCHER as
-- marcas sem escrever 737 linhas: quem não tem linha aqui responde com a
-- contagem da `copies` (`paginas.posse_total`). Com linha, ela GANHA — é a
-- carta na mão dele contra o registo. Ver `mtgvault/marcas.py`.
--
-- O `qty` é ABSOLUTO e não um delta sobre o inventário: uma cópia nova que entre
-- por foto ou por CSV não pode mexer num número que ele já confirmou.
CREATE TABLE IF NOT EXISTS posse_marcada (
    card_name  TEXT PRIMARY KEY,       -- nome oracle, a FRENTE (como as listas)
    qty        INTEGER NOT NULL,
    marcado_em TEXT NOT NULL
);

-- O rasto de cada toque. O `request_id` é ÚNICO: é ele que faz um retry de rede
-- não contar a dobrar (o padrão do `riftvault/collection.adjust`).
CREATE TABLE IF NOT EXISTS posse_marcada_log (
    id         INTEGER PRIMARY KEY,
    at         TEXT NOT NULL,
    card_name  TEXT NOT NULL,
    delta      INTEGER NOT NULL,
    qty_antes  INTEGER NOT NULL,
    qty_depois INTEGER NOT NULL,
    base       TEXT NOT NULL,          -- inventario | marcado: de onde partiu
    origem     TEXT,                   -- 8771 | cli
    request_id TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_posse_log_carta ON posse_marcada_log(card_name);

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
-- `low` e `trend` são as duas pontas do MODO DE PREÇO (2026-09-25):
--   `best`   = a oferta mais barata      -> low
--   `market` = o que o mercado pede      -> trend
--   `media`  = a média das duas
-- e a `receita` diz COMO é que os números desta linha foram produzidos
-- (`unico` | `cm-guide` | `ct-ofertas`, em `mtgvault.precos`). Sem ela, a regra
-- dos 5 % da Reserved List comparava a mediana de hoje com o mínimo de há 90
-- dias e inventava uma subida que nunca houve — ver `precos.py`.
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
    receita     TEXT,
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
-- O `mtgtop8_archetype` entrou a 2026-10-04 (André: *"quero o deck de Duel
-- Commander seguido todos os dias"*, archetype?a=2629). Numa base já criada o
-- CHECK não se altera com um ALTER: a tabela reconstrói-se no `db._migrate()`,
-- e é lá que está a explicação.
--
-- O `archetype` é mais antigo e NUNCA foi implementado (o `watchlist.check_all`
-- não o conhece): não se apaga — nada se apaga —, mas uma vigia inscrita nele
-- nunca correria, e por isso o `check_all` passou a FALHAR ALTO em qualquer
-- kind que não saiba tratar, em vez de o saltar calado.
-- O `preco_impressao` (2026-10-04) é a VIGIA DE PREÇO de UMA impressão: nasceu
-- para o foil de New Phyrexia do Whipflare, que ele quer trocar «quando aparecer
-- mais barato». Reaproveita esta tabela de propósito — a mecânica de vigiar
-- (inscrever, snapshot, «mudou?», aviso) já está aqui e escrever uma segunda era
-- ter duas respostas para «o que é que estou a vigiar». O que muda é o
-- verificador (`watchlist.check_preco_impressao`).
CREATE TABLE IF NOT EXISTS watched (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('mtgo_player','moxfield','archetype','mtgtop8_archetype','preco_impressao')),
    key          TEXT NOT NULL,      -- login MTGO | publicId Moxfield | archetype_id | id do arquetipo no mtgtop8 | '<scryfall_id>|<finish>'
    label        TEXT NOT NULL,      -- nome que dou ao baralho (ou à impressão vigiada)
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
    receita     TEXT,                    -- ver price_history e mtgvault/precos.py
    PRIMARY KEY (scryfall_id, source, finish)
);
-- A RECEITA EM VIGOR DE UMA FONTE, SEM VARRER A TABELA (2026-10-02).
-- A chave primária acima é `(scryfall_id, source, finish)`, e por isso o
-- `source` não é prefixo de índice nenhum: o `precos.receita_em_vigor` —
-- *"com que receita foram escritos os preços de hoje desta fonte"* — fazia um
-- `SCAN price_latest` por chamada. Medido na base do André a 2026-10-02
-- (86 782 linhas): **46 chamadas por `loadout.report`, 0,87 s dos 1,68 s — 52 %
-- do relatório**, ~4 milhões de linhas lidas para responder 46 vezes à mesma
-- pergunta. Com o índice e a memória por relatório (`loadout.avaliar_rl`):
-- 1 chamada e 0,83 s, com os nove resultados da venda iguais ao cêntimo.
--
-- É um índice e não uma cache de propósito: uma cache precisava de ser
-- invalidada quando o `write_prices` muda a receita, e este repositório tem
-- três cicatrizes dessa família (o `-wal` vazio no `_versao`, o `foil_cache`
-- das duas passagens, o `_TABELA_CACHE` do estado). Um índice não se invalida.
--
-- E fica AQUI, depois do `CREATE TABLE`: o `schema.sql` corre de cima a baixo
-- e um índice escrito antes da tabela rebenta o `db.init` com *"no such table"*
-- — é a irmã da armadilha de 2026-09-09, e aconteceu ao escrever isto.
CREATE INDEX IF NOT EXISTS ix_price_latest_fonte ON price_latest(source, date);

-- Impressão digital do conteúdo da lista, para apanhar a MESMA decklist
-- vinda de fontes diferentes (ver sources.store_decklist).
CREATE INDEX IF NOT EXISTS ix_dl_dedupe ON decklists(format, content_hash, event_date);
