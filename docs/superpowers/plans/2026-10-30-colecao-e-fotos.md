# Coleção e fotos — plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: usar superpowers:subagent-driven-development
> (recomendado) ou superpowers:executing-plans para executar este plano tarefa a
> tarefa. Os passos usam caixas (`- [ ]`) para seguir o progresso.

**Objetivo:** uma secção Coleção no site do núcleo (4 coleções, preços que não
se apagam, «a subir», «quero vender») e a validação por foto das cópias dos
decks e das coleções, com o recorte da cópia dele no lugar da imagem da Scryfall.

**Arquitetura:** módulos novos em `mtgvault/nucleo/` (`colecoes`, `cotacoes`,
`jogada`, `fotos`), uma página nova `nucleo_colecoes.py` → `colecoes.html`,
tabelas `n_*` novas por migração, passos novos no `_main_nucleo` do `daily.py`,
um subcomando `nucleo` no CLI (é por ele que o Claude extrai, recorta e valida
as fotos na conversa), rotas novas no `webapp.py`.

**Tecnologia:** Python 3.14 + SQLite, OpenCV (`opencv-python-headless`, já
instalado a 30/10/2026) + numpy para o recorte, HTML/CSS/JS sem frameworks.

**Spec:** `docs/superpowers/specs/2026-10-30-colecao-e-fotos-design.md` (e as
regras do núcleo em `2026-10-28-site-mtg-nucleo-design.md`).

**Interfaces atuais** (levantadas a 30/10, com ficheiro:linha):
`scratchpad/interfaces-nucleo.md` da sessão a6661d25 — lê-o se precisares de uma
assinatura que não esteja aqui.

## Global Constraints

- Raiz: `C:\Users\Catarina\Desktop\Claude\01-Projetos\Servidor MTG Coleçao\Servidor MTG Coleçao`. Correr scripts com `PYTHONPATH=. PYTHONUTF8=1 py …`.
- Regras do `CLAUDE.md` do projeto: comentários e mensagens em português de Portugal; os nomes do núcleo (tabelas, colunas, funções) em português; os testes **nunca** abrem a base real (`db.session(tmp/"v.db", tmp/"c.db")`, ou as quatro variáveis `MTGVAULT_*` fixadas ANTES do import); sem rede nos testes; `colecao_config.json` nunca se reescreve.
- Tabela/coluna nova entra nos três sítios: `mtgvault/schema.sql`, `db._migrate()` e quem a escreve. Índice sobre coluna acrescentada por `ALTER` vai só no `_migrate`.
- O núcleo escreve só em tabelas `n_*`. A `n_posse` dos decks **não muda de chave**.
- Página nova: `colecoes.html` (não `colecao.html`, que é a Galeria do site antigo).
- Coleções: Duals de Revised (`3ed`, en, nonfoil), Zendikar Expeditions (shocks + fetches de `zne`, en, foil), Shocks originais em português (`rav`/`gpt`/`dis`, pt, nonfoil), meta 4 de cada; Reserved List aberta, sem meta.
- Preço PT: só ofertas `mtg_language == "pt"` do CardTrader com `precos.oferta_utilizavel(o, frozenset({"pt"}))`; o preço é a mais barata do último dia com ofertas PT; nunca cair no inglês.
- «A subir»: Reserved List (`reserved = 1 AND digital = 0`) + impressões das famílias (10 duals, 10 shocks, 10 fetches) + o set `zne`, só com trend ≥ 20 €.
- «Joga»: versão atual de um deck dele, ou `n_jogada` dos últimos 3 meses (qualquer formato).
- Recortes: `assets/cartas/<foto_id>-<n>.jpg`, 488 px de largura, JPEG qualidade 82; vão para o Git.
- Commits: uma linha ASCII + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Sem push.
- Bateria antes de dar uma tarefa por fechada: `py tests\_bateria.py`. Já falham antes deste trabalho, e continuam a poder falhar pelos mesmos motivos: `test_casca` (ícones da barra no `index.html` antigo), `test_paginas` (links do site antigo), `test_so_cardtrader` («Cardmarket» nas páginas do núcleo). Nenhum teste novo pode falhar.

## Review Focus

1. **Um −1 abaixo das validadas** (deck ou coleção): a validação mais recente fica `desfeita_em`, nunca apagada, e as validadas nunca passam a posse. Testes nas Tarefas 2 e 6.
2. **Preço PT nunca cai no inglês**, nem quando não há ofertas PT há semanas (mostra «visto há N dias» ou «sem preço»). Teste na Tarefa 3.
3. **Fotos repetidas:** extrair a mesma imagem do registo duas vezes não cria duas fotos (chave sessão + linha + índice). Teste na Tarefa 6.
4. **Recorte que não encontra as cartas todas** devolve as que encontrou e diz quantas, nunca inventa recortes. Teste na Tarefa 6.
5. **Página publicada sem os recortes no Git** dava imagens partidas: `assets/cartas` entra no `publicaveis()` e no `git add`. Teste na Tarefa 12.

---

### Tarefa 1: tabelas novas

**Ficheiros:** `mtgvault/schema.sql`, `mtgvault/db.py` (`_migrate`), teste novo `tests/test_nucleo_colecoes.py`.

**Produz** (DDL exato):
```sql
CREATE TABLE IF NOT EXISTS n_colecao (
    slug  TEXT PRIMARY KEY, nome TEXT NOT NULL,
    tipo  TEXT NOT NULL CHECK (tipo IN ('fechada','aberta')),
    arte_nome TEXT, ordem INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS n_colecao_carta (
    id INTEGER PRIMARY KEY, colecao TEXT NOT NULL, nome TEXT NOT NULL,
    scryfall_id TEXT NOT NULL,
    acabamento TEXT NOT NULL CHECK (acabamento IN ('nonfoil','foil')),
    lingua TEXT NOT NULL DEFAULT 'en', meta INTEGER,
    tenho INTEGER NOT NULL DEFAULT 0 CHECK (tenho >= 0),
    vender INTEGER NOT NULL DEFAULT 0,
    UNIQUE (colecao, scryfall_id, acabamento, lingua));
CREATE TABLE IF NOT EXISTS n_colecao_log (
    request_id TEXT UNIQUE, carta_id INTEGER NOT NULL,
    delta INTEGER NOT NULL, em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS n_foto (
    id INTEGER PRIMARY KEY, caminho TEXT NOT NULL, dia TEXT NOT NULL,
    sessao TEXT NOT NULL, linha INTEGER NOT NULL, indice INTEGER NOT NULL,
    para TEXT, UNIQUE (sessao, linha, indice));
CREATE TABLE IF NOT EXISTS n_recorte (
    id INTEGER PRIMARY KEY, foto_id INTEGER NOT NULL, numero INTEGER NOT NULL,
    caminho TEXT NOT NULL, UNIQUE (foto_id, numero));
CREATE TABLE IF NOT EXISTS n_validacao (
    id INTEGER PRIMARY KEY, recorte_id INTEGER NOT NULL, ambito TEXT NOT NULL,
    scryfall_id TEXT NOT NULL, acabamento TEXT NOT NULL,
    lingua TEXT NOT NULL DEFAULT 'en', qtd INTEGER NOT NULL CHECK (qtd > 0),
    em TEXT NOT NULL, desfeita_em TEXT);
CREATE INDEX IF NOT EXISTS ix_n_validacao ON n_validacao(ambito, scryfall_id, acabamento, lingua);
CREATE TABLE IF NOT EXISTS n_preco_pt (
    scryfall_id TEXT NOT NULL, acabamento TEXT NOT NULL, dia TEXT NOT NULL,
    preco_eur REAL NOT NULL, ofertas INTEGER NOT NULL,
    PRIMARY KEY (scryfall_id, acabamento, dia));
CREATE TABLE IF NOT EXISTS n_preco_vigiado (
    scryfall_id TEXT NOT NULL, acabamento TEXT NOT NULL, dia TEXT NOT NULL,
    preco_eur REAL NOT NULL, PRIMARY KEY (scryfall_id, acabamento, dia));
CREATE TABLE IF NOT EXISTS n_jogada (
    formato TEXT NOT NULL, mes TEXT NOT NULL, nome TEXT NOT NULL,
    listas INTEGER NOT NULL, PRIMARY KEY (formato, mes, nome));
```
mais `n_valor.colecoes_eur REAL` por `ALTER TABLE` (padrão `PRAGMA table_info` do `_migrate`; no `schema.sql` a coluna entra no `CREATE TABLE n_valor`).

- [ ] **Passo 1 — teste a chumbar** `caso_tabelas_novas`: `with sessao() as con:` cada uma das 10 tabelas existe em `sqlite_master` e `"colecoes_eur" in {r["name"] for r in con.execute("PRAGMA table_info(n_valor)")}`; `caso_migra_base_antiga`: criar um `v.db` com o `n_valor` antigo (4 colunas, uma linha), abrir com `db.session` e confirmar a coluna nova e a linha intacta.
- [ ] **Passo 2 — correr e ver chumbar:** `cd tests && py test_nucleo_colecoes.py` → `AssertionError`.
- [ ] **Passo 3 — DDL** no `schema.sql` (junto das `n_*`) e no `_migrate` (o mesmo texto + o `ALTER`).
- [ ] **Passo 4 — verde:** o mesmo comando dá `TUDO OK`; `py test_nucleo_valor.py` continua verde.
- [ ] **Passo 5 — commit:** `nucleo: tables for collections, photos, PT and watched prices`.

### Tarefa 2: as coleções

**Ficheiros:** novo `mtgvault/nucleo/colecoes.py`; `tests/test_nucleo_colecoes.py`.

**Interfaces — produz:**
- `COLECOES: tuple[dict, ...]` — `{"slug","nome","tipo","arte_nome","cartas": ((nome, set_code, acabamento, lingua), ...)}` com os slugs `duals_revised`, `expeditions`, `shocks_pt`, `reserved_list` (esta sem cartas).
- `DUALS`, `SHOCKS`, `FETCHES: tuple[str, ...]` (10 nomes cada; são também as «famílias» da Tarefa 3).
- `garantir_colecoes(con) -> int` — insere as que faltam e as suas cartas com `meta = 4`, resolvendo o `scryfall_id` por `name` + `set_code` no catálogo; idempotente; carta que o catálogo não tem → `ValueError` com o nome e o set.
- `colecoes(con) -> list[sqlite3.Row]` por `ordem`.
- `estado_colecao(con, slug) -> dict` — `{"slug","nome","tipo","cartas","tenho","total","custo_falta","valor_eur","sem_preco","validadas"}`; cada carta `{"id","nome","scryfall_id","acabamento","lingua","meta","tenho","falta","vender","preco_un","preco_visto_em","var30","var90","joga","validadas","recorte"}` (`total`/`falta` só nas fechadas; `preco_*`, `var*` e `joga` vêm das Tarefas 3 e 5 — até lá `None`/`[]`).
- `ajustar(con, carta_id, delta, *, request_id) -> int` — idempotente por `n_colecao_log`, nunca abaixo de 0; depois de descer chama `fotos.aparar_validadas(con, ambito, sid, acab, lingua, tenho)` (Tarefa 6; até lá, uma função local que não faz nada).
- `definir_meta(con, carta_id, meta: int) -> None` (≥ 0; `ValueError` na aberta), `marcar_vender(con, carta_id, vender: bool) -> None`.
- `juntar(con, slug, scryfall_id, acabamento, lingua="en") -> int` — só na aberta (`ValueError` na fechada); devolve o `id` (a carta que já lá está devolve o mesmo id).

- [ ] **Passo 1 — testes a chumbar** (semear no catálogo de teste as impressões necessárias: as 10 duals em `3ed`, 2 shocks e 2 fetches em `zne` com `finishes ["foil"]`, 1 shock em `rav`, e uma carta RL):
  - `caso_garantir_e_idempotente`: `garantir_colecoes` duas vezes → 4 coleções; `duals_revised` com 10 cartas `meta == 4`, `lingua == "en"`; `shocks_pt` com `lingua == "pt"`; `expeditions` com `acabamento == "foil"`.
  - `caso_estado_fechada`: marcar 2 Underground Sea → `tenho == 2`, `total == 40`, a carta com `falta == 2`.
  - `caso_ajustar_idempotente_e_sem_negativos`: o mesmo `request_id` duas vezes soma uma; −5 com 2 → 0.
  - `caso_aberta`: `juntar(con, "reserved_list", rl_sid, "nonfoil")` → aparece em `estado_colecao` sem `meta` nem `falta`; `juntar` numa fechada → `ValueError`; `definir_meta` na aberta → `ValueError`.
  - `caso_vender`: `marcar_vender(True)` → `vender == 1` no estado.
  - `caso_catalogo_sem_carta`: sem uma das duals no catálogo → `ValueError` com «Volcanic Island» e «3ed» na mensagem.
- [ ] **Passo 2 — ver chumbar.**
- [ ] **Passo 3 — implementar `colecoes.py`.** Transação com `posse._transacao(con)`; preço por enquanto `valor.preco(con, sid, acab)` nas `en`.
- [ ] **Passo 4 — verde.**
- [ ] **Passo 5 — commit:** `nucleo: collections model (closed and open), goals, sell mark`.

### Tarefa 3: cotações (PT, vigiadas, variação, «a subir»)

**Ficheiros:** novo `mtgvault/nucleo/cotacoes.py`; `mtgvault/prices.py` (`cards_of_interest`); `mtgvault/nucleo/colecoes.py` (preço PT e variações no estado); teste novo `tests/test_nucleo_cotacoes.py`.

**Interfaces — produz:**
- `SETS_PT = ("rav", "gpt", "dis")`, `MINIMO_SUBIR = 20.0`.
- `gravar_ofertas_pt(con, sid: str, ofertas: list[dict], dia: str) -> int` — filtra com `precos.oferta_utilizavel(o, frozenset({"pt"}))`, separa por `properties_hash.mtg_foil`, grava em `n_preco_pt` a mais barata e o nº de ofertas; sem ofertas aceites não escreve nada; devolve linhas escritas.
- `recolher_pt(con, ct: prices.CardTrader, dia: str) -> int` — para cada edição de `SETS_PT`, `ct.marketplace(eid)` e `gravar_ofertas_pt` para as cartas `lingua = 'pt'` das coleções (blueprint pelo `cardtrader_map`; corre `prices.sync_cardtrader_map(con, ct, list(SETS_PT))` antes).
- `preco_pt(con, sid, acabamento) -> tuple[float | None, str | None]` — `(preço, dia)` da linha mais recente; `(None, None)` se nunca houve.
- `vigiadas(con) -> list[tuple[str, str]]` — `(sid, acabamento)` das cartas das coleções + RL + famílias (`colecoes.DUALS/SHOCKS/FETCHES` em todas as impressões de papel, e o set `zne`).
- `gravar_vigiadas(con, dia: str) -> int` — do `price_latest` (cardmarket, `trend > 0`) para `n_preco_vigiado`, **só quando difere** da última linha dessa carta.
- `preco_em(con, sid, acabamento, dia) -> float | None` — `n_preco_vigiado` com `dia <= dia`; sem linha → `valor.preco(con, sid, acabamento, dia)` (o histórico que a poda deixou).
- `variacao(con, sid, acabamento, dias: int, hoje: str | None = None) -> float | None` — `(hoje / há N dias − 1) × 100`, `None` sem um dos dois.
- `a_subir(con, hoje=None) -> list[dict]` — `{"nome","set_code","scryfall_id","acabamento","preco","var30","var90","tenho","joga"}` com `preco >= MINIMO_SUBIR`, por `var30` decrescente (`None` no fim).
- `prices.cards_of_interest` passa a incluir os `scryfall_id` de `vigiadas(con)`.

- [ ] **Passo 1 — testes a chumbar** (ofertas falsas como dicts com `price_cents`, `price_currency="EUR"`, `quantity`, `graded=False`, `on_vacation=False`, `properties_hash={"condition":"Near Mint","mtg_language":…,"mtg_foil":False}`):
  - `caso_pt_so_portugues`: ofertas `en` 5,00 € e `pt` 12,00 € e 15,00 € → `n_preco_pt` 12,00 com 2 ofertas.
  - `caso_pt_ultimo_visto`: ofertas PT no dia 20, nenhuma no dia 25 → `preco_pt` dá `(preço do dia 20, "…-20")`; **com um trend `en` no `price_latest` dessa carta, continua a não o usar**; carta nunca vista → `(None, None)`.
  - `caso_pt_filtro`: oferta PT `altered=True` ou `condition="Poor"` é ignorada.
  - `caso_vigiadas_so_na_mudanca`: o mesmo trend em dois dias → uma linha; muda → duas.
  - `caso_variacao`: 100 € há 30 dias e 120 € hoje → `20.0`; sem ponto antigo → `None`.
  - `caso_a_subir`: uma RL de 25 € a subir entra; uma de 10 € não; ordem por `var30`.
- [ ] **Passo 2 — ver chumbar.**
- [ ] **Passo 3 — implementar** `cotacoes.py`; no `colecoes.estado_colecao`, carta `pt` → `preco_pt`, `en` → `valor.preco`; `var30/var90` de `variacao`.
- [ ] **Passo 4 — verde** (`test_nucleo_cotacoes.py` e `test_nucleo_colecoes.py`).
- [ ] **Passo 5 — commit:** `nucleo: PT-only prices, watched prices kept forever, rising list`.

### Tarefa 4: valor com as coleções

**Ficheiros:** `mtgvault/nucleo/valor.py`; `tests/test_nucleo_valor.py`.

**Interfaces — consome:** `colecoes.estado_colecao`, `cotacoes.preco_pt`. **Produz:**
- `valor_colecoes(con, dia: str | None = None) -> dict` — `{"total_eur","copias","sem_preco"}` das `n_colecao_carta` com `tenho > 0` (PT pelo `preco_pt`, o resto por `valor.preco`).
- `serie_colecao(con, slug, hoje: str | None = None) -> list[tuple[str, float, int]]` — `(dia, total_eur, sem_preco)` da coleção nos últimos 90 dias e no ponto de hoje, com o `tenho` de hoje a preços de `cotacoes.preco_em` (PT: o `n_preco_pt` mais recente até esse dia); é o que alimenta o gráfico e a variação a 30 dias do mosaico.
- `valor_em` passa a devolver também `"decks_eur"`, `"colecoes_eur"`, `"a_mais_eur"` (`total_eur` = soma); `gravar_valor_do_dia` escreve `colecoes_eur`; `serie` soma as coleções nos dias de trás.

- [ ] **Passo 1 — testes a chumbar:** `caso_valor_com_colecoes` (decks 10 €, coleção 2 duals a 300 € → `total_eur == 610`, `colecoes_eur == 600`); `caso_valor_colecao_pt_sem_ingles` (shock PT sem ofertas PT, com trend `en` → conta em `sem_preco`, 0 € no total); `caso_gravar_valor_colecoes_eur` (linha do `n_valor` com `colecoes_eur`); `caso_serie_colecao` (2 duals a 100 € há 30 dias e a 120 € hoje → primeiro ponto 200, último 240).
- [ ] **Passo 2 — ver chumbar.** **Passo 3 — implementar.** **Passo 4 — verde** (todo o `test_nucleo_valor.py`).
- [ ] **Passo 5 — commit:** `nucleo: collection value in the daily total`.

### Tarefa 5: «joga»

**Ficheiros:** novo `mtgvault/nucleo/jogada.py`; `mtgvault/nucleo/colecoes.py`, `cotacoes.a_subir` (preencher `joga`); teste novo `tests/test_nucleo_jogada.py`.

**Interfaces — produz:**
- `registar(con) -> int` — para cada `(format, strftime('%Y-%m', event_date), card_name)` nas `decklists`/`decklist_cards`, `INSERT OR REPLACE INTO n_jogada` com o nº de listas distintas; devolve linhas escritas. Corre antes da poda das listas (Tarefa 13).
- `onde_joga(con, nome: str, hoje: str | None = None) -> list[str]` — rótulos: `"deck <Nome>"` para cada deck cuja versão atual tem a carta, depois os formatos (`visual.formato(f)`) com listas nos meses de há 3 meses até hoje; vazio = não joga.

- [ ] **Passo 1 — testes a chumbar:** `caso_registar_por_mes` (2 listas de legacy em outubro com a mesma carta → `listas == 2`); `caso_onde_joga` (carta num deck → `"deck Oswald"` primeiro; carta só em `n_jogada` de há 4 meses → `[]`; há 1 mês → `["Legacy"]`); `caso_registar_idempotente`.
- [ ] **Passo 2–4 — chumbar, implementar, verde.**
- [ ] **Passo 5 — commit:** `nucleo: where a card is played (my decks and tournaments)`.

### Tarefa 6: fotos — extrair, recortar, validar

**Ficheiros:** novo `mtgvault/nucleo/fotos.py`; `mtgvault/nucleo/posse.py` (`ajustar` chama `aparar_validadas` depois de descer); teste novo `tests/test_nucleo_fotos.py`.

**Interfaces — produz:**
- `PASTA_ORIGINAIS = "data/fotos/originais"`, `PASTA_RECORTES = "assets/cartas"`, `LARGURA = 488`, `ALTURA = 680`.
- `sessao_mais_recente(raiz_projetos: Path) -> Path` — o `.jsonl` modificado mais recentemente em `~/.claude/projects/*/`.
- `imagens_da_sessao(jsonl: Path) -> list[dict]` — só mensagens `type == "user"`; `{"linha","indice","media_type","dados": bytes,"quando"}`.
- `extrair(con, jsonl: Path, raiz: Path, *, ultimas: int = 1, para: str | None = None) -> list[dict]` — as `ultimas` imagens ainda não extraídas (chave `sessao` = nome do ficheiro, `linha`, `indice`), gravadas em `raiz/PASTA_ORIGINAIS/AAAA-MM-DD/<id>.<ext>`; devolve `{"foto_id","caminho"}`.
- `recortar(con, foto_id: int, raiz: Path) -> dict` — OpenCV: cinzento → desfoque → limiar/Canny → `findContours` → `approxPolyDP` com 4 vértices, área ≥ 1,5 % da imagem, razão lado curto/longo entre 0,62 e 0,80 → `warpPerspective` para 488×680 → ordem por filas (centro y) e dentro da fila por x; grava `raiz/PASTA_RECORTES/<foto_id>-<n>.jpg` (qualidade 82) e `n_recorte`; devolve `{"recortes": [{"numero","caminho"}], "encontradas": n}`. Não inventa recortes.
- `validar(con, recorte_id, ambito, scryfall_id, acabamento, lingua="en", qtd=1, *, registar=False) -> dict` — `registar=True` soma primeiro a posse (deck: `posse.ajustar` com `request_id` derivado do recorte; coleção: `colecoes.ajustar`); depois grava `n_validacao` sem passar a posse (`ValueError` «só tens N»).
- `validadas(con, ambito, scryfall_id, acabamento, lingua="en") -> int` e `recorte_de(con, ambito, scryfall_id, acabamento, lingua="en") -> str | None` (caminho relativo `assets/cartas/…` da validação ativa mais recente).
- `aparar_validadas(con, ambito, scryfall_id, acabamento, lingua, posse_atual: int) -> int` — enquanto `validadas > posse_atual`, marca `desfeita_em` na mais recente; devolve quantas desfez.

- [ ] **Passo 1 — testes a chumbar:**
  - `caso_imagens_da_sessao`: um `.jsonl` de teste com uma mensagem `user` com 2 imagens base64 (PNG criados com `cv2.imencode`) e uma `assistant` com outra → 2 imagens.
  - `caso_extrair_idempotente`: `extrair(..., ultimas=2)` duas vezes → 2 fotos na `n_foto`, os ficheiros existem.
  - `caso_recortar_sintetico`: imagem 1600×1200 de fundo escuro com 3 retângulos claros 300×420 (um rodado 5°) em duas filas → `encontradas == 3`, cada JPEG 488×680, ordem: os dois de cima por x, depois o de baixo.
  - `caso_recortar_falha_diz`: imagem só com fundo → `encontradas == 0`, `recortes == []`.
  - `caso_validar_nao_passa_posse`: posse 2, validar 3 → `ValueError`; validar 2 → `validadas == 2`.
  - `caso_menos_um_desfaz_a_mais_recente`: 2 validadas (recortes A e B), `posse.ajustar(..., -1)` → `validadas == 1`, a de B com `desfeita_em`, `recorte_de` dá A; a linha de B **continua** na tabela.
  - `caso_menos_um_tira_primeiro_por_validar`: posse 3, validadas 2, −1 → `validadas == 2`.
  - `caso_registar_por_foto_coleccao`: `validar(..., registar=True)` numa coleção → `tenho` sobe e `validadas` também.
- [ ] **Passo 2–4 — chumbar, implementar, verde** (e `test_nucleo_posse.py` continua verde).
- [ ] **Passo 5 — commit:** `nucleo: photos from the chat session, card crops, validation`.

### Tarefa 7: CLI `nucleo`

**Ficheiros:** `mtgvault/cli.py`; teste novo `tests/test_nucleo_cli.py`.

**Interfaces — produz** (`sub.add_parser("nucleo")`, posicional `accao` com `choices`, como o `precos`):
- `nucleo colecoes` — garante as coleções e imprime `slug · tenho/total · valor`.
- `nucleo extrair [--sessao PATH] [--ultimas N] [--para SLUG]` — imprime `foto <id>: <caminho>`.
- `nucleo recortar FOTO_ID` — imprime `N recortes` e um caminho por linha.
- `nucleo validar --lote FICHEIRO.json` — lista de `{"recorte_id","ambito","scryfall_id","acabamento","lingua","qtd","registar"}`; tudo numa transação (uma falha → nada gravado, e diz qual linha).
- `nucleo validadas AMBITO` — imprime, por carta, `tenho · validadas`.

- [ ] **Passo 1 — testes a chumbar** chamando `cli.main([...,"--db", v, "--catalog", c])` com `contextlib.redirect_stdout`: `caso_colecoes`, `caso_extrair_recortar_validar` (sessão de teste + imagem sintética da Tarefa 6), `caso_lote_falha_nao_grava`.
- [ ] **Passo 2–4 — chumbar, implementar, verde.**
- [ ] **Passo 5 — commit:** `cli: nucleo collections and photo commands`.

### Tarefa 8: recortes e validadas nos decks

**Ficheiros:** `mtgvault/site_shell.py` (`_SVG["camara"]`), `mtgvault/nucleo/posse.py` (`estado_deck`), `mtgvault/nucleo/visual.py` (`carta`, novo `img_recorte`, CSS), `nucleo_decks.py` (`_progresso`); `tests/test_nucleo_paginas.py`.

**Interfaces — produz:**
- `estado_deck`: cada carta ganha `"validadas"` (min(tenho, validadas do âmbito)) e `"recorte"` (`fotos.recorte_de` ou `None`); o dict ganha `"validadas"` (soma).
- `visual.img_recorte(caminho: str, alt: str) -> str` — `<img src="{caminho}" … width=146 height=204 loading=lazy decoding=async>`.
- `visual.carta`: com `c["recorte"]` usa `img_recorte` e acrescenta `data-oficial="{url_carta(sid,'normal')}"`; `c["validadas"] > 0` → classe `validada` e o ícone `camara` no canto; sem recorte, igual a hoje.
- `_progresso` mostra `· N validadas` quando `N > 0`.

- [ ] **Passo 1 — testes a chumbar:** `caso_carta_com_recorte` (validar 1 Thought Monitor com um recorte de teste → a `<figure>` tem `src="assets/cartas/…"`, a classe `validada` e `data-oficial`); `caso_progresso_com_validadas` (1 → «· 1 validada»; 2 → «· 2 validadas»); `caso_sem_validacao_igual` (sem validações, nenhuma `validada` na página).
- [ ] **Passo 2–4 — chumbar, implementar, verde** (`test_nucleo_paginas.py` e `test_tokens.py`: sem cores hexadecimais no CSS novo).
- [ ] **Passo 5 — commit:** `decks: show the photo crop and validated count`.

### Tarefa 9: a página Coleção

**Ficheiros:** novo `nucleo_colecoes.py` (raiz, igual aos outros `nucleo_*`: `FICHEIRO = "colecoes.html"`, `TITULO = "Coleção"`, `html_page(con, *, editable=False, token="")`, `build(con, out_path=None, rep=None)`); `mtgvault/nucleo/visual.py` (mosaico de coleção); teste novo `tests/test_nucleo_colecoes_pagina.py`.

**O que desenha:** `<div id="todos">` com um mosaico por coleção (arte, nome, «tenho X de Y» ou «N cartas», valor, `variacao_html` a 30 dias) e um para «A subir»; uma `<section class="dk" id="<slug>">` por coleção (cabeçalho com valor, `visual.grafico` da série da coleção, `visual.barra`, «falta X €»; grelha com nome, «tenho / meta», preço — nas PT com «visto há N dias» —, «+N % 30 d · +N % 90 d», etiqueta `joga`, etiqueta «quero vender»); `<section class="dk" id="subir">` com a tabela de `cotacoes.a_subir`. O mesmo JS de hash do `nucleo_decks`.

- [ ] **Passo 1 — testes a chumbar:** `caso_mosaicos` (4 coleções + «A subir», `href="#duals_revised"`); `caso_colecao_fechada` («2 de 40», carta em falta a cinzento, «quero vender» quando marcada); `caso_pt_visto_ha` (shock PT com preço de há 5 dias → «visto há 5 dias»; sem nenhum → «sem preço»); `caso_subir` (a RL a subir aparece com `var30`); `caso_aberta_sem_meta` (sem «de Y»); `caso_casca` (`<h1>` = «Coleção», item do menu `cur`).
- [ ] **Passo 2–4 — chumbar, implementar, verde.**
- [ ] **Passo 5 — commit:** `site: Colecao page with collections and rising cards`.

### Tarefa 10: Vender e Painel

**Ficheiros:** `nucleo_vender.py`, `mtgvault/nucleo/valor.py` (`a_vender` com `"colecoes"`), `nucleo_painel.py` (`_valor`); `tests/test_nucleo_paginas.py`.

- `valor.a_vender` ganha `"colecoes": [linha]` (`{nome,set_code,scryfall_id,acabamento,lingua,qtd = tenho,preco_un,motivo:"colecao",colecao}` das cartas `vender = 1 AND tenho > 0`) e entra no `total_eur`.
- Vender: bloco novo «Das coleções» depois dos três atuais.
- Painel: por baixo do valor, «decks X € · coleções Y € · a mais Z €».

- [ ] **Passo 1 — testes a chumbar:** `caso_vender_das_colecoes` (carta marcada aparece com o preço e soma no total); `caso_painel_tres_partes`.
- [ ] **Passo 2–4 — chumbar, implementar, verde.** **Passo 5 — commit:** `site: collections in Vender and the Painel total`.

### Tarefa 11: modo de edição

**Ficheiros:** `webapp.py` (`PAGINAS_NUCLEO["/colecoes.html"]`, rota estática `/assets/cartas/<n>.jpg` igual à `_FOTO_CAIXA`, POST novos no `_N_POST`), `mtgvault/nucleo/edicao_js.py`, `nucleo_colecoes.py` (botões em edição); `tests/test_nucleo_webapp.py`.

**Endpoints** (`(con, dados) -> dict`, `ValueError` → 409):
- `/api/n/colecao/marca` `{"carta": id, "delta", "request_id"}` → `{"tenho"}`
- `/api/n/colecao/meta` `{"carta", "meta"}` → `{"ok": True}`
- `/api/n/colecao/vender` `{"carta", "vender": bool}` → `{"ok": True}`
- `/api/n/colecao/juntar` `{"colecao", "scryfall_id", "acabamento", "lingua"}` → `{"carta": id}`

**JS:** botões com `data-acao="cmarca"|"cmeta"|"cvender"|"cjuntar"` e `data-carta`; «juntar carta» reutiliza a procura de Vender (`/api/n/procurar`, `/api/n/edicoes`); depois de cada POST, `recarrega()`. Numa carta com recorte, o toque abre também a imagem oficial (`data-oficial`).

- [ ] **Passo 1 — testes a chumbar** (por HTTP, como os existentes): `caso_colecoes_pagina_200`; `caso_marca_colecao` (+1 duas vezes com o mesmo `request_id` → `tenho == 1`); `caso_meta_e_vender`; `caso_juntar_so_na_aberta` (fechada → 409); `caso_recorte_servido` (um `assets/cartas/1-1.jpg` em `webapp.ROOT` → 200 `image/jpeg`; `../` → 404); `caso_sem_token_403`.
- [ ] **Passo 2–4 — chumbar, implementar, verde.** **Passo 5 — commit:** `webapp: edit collections, serve card crops`.

### Tarefa 12: menu e publicação

**Ficheiros:** `mtgvault/site_shell.py` (`SECCOES_NUCLEO`: `("colecoes.html", "", "colecao", "Coleção", "o que guardas, com preço")` entre Decks e Vender), `mtgvault/publicar.py` (`PAGINAS_NUCLEO` + `("nucleo_colecoes","colecoes.html",False)`; `publicaveis()` acrescenta `"assets/cartas"` com o núcleo ligado), `.github/workflows/daily.yml` (linha 131: `git add index.html deck.html colecoes.html vender.html assets/cartas`), `tests/test_publicar.py`, `tests/test_casca.py`, `tests/test_nucleo_ligado.py`.

- [ ] **Passo 1 — atualizar os testes para a verdade nova** (`NUCLEO` com `colecoes.html` e `assets/cartas`; menu de 4 entradas; `paginas == 4`) e ver chumbar.
- [ ] **Passo 2 — implementar.** A pasta `assets/cartas` tem de existir no repositório: um `.gitkeep`.
- [ ] **Passo 3 — verde** nos três (com as falhas antigas do `test_casca` e do `test_paginas` iguais às de antes — comparar a saída com a do commit anterior).
- [ ] **Passo 4 — commit:** `site: Colecao in the menu and in publishing`.

### Tarefa 13: recolha diária

**Ficheiros:** `daily.py` (`_main_nucleo`), `tests/test_nucleo_ligado.py`.

**Ordem nova dos passos** (os novos a negrito):
1. `catalogo`
2. `harvest-mtgo` → `sources.harvest_mtgo(con, MTGO_DAYS, formats=None)` (todos os formatos)
3. **`harvest-mtgtop8:<fmt>`** → `mtgtop8.harvest(con, fmt, max_events=8)` para `MTGTOP8_FORMATS + MTGTOP8_PAPER`
4. `precos-scryfall`, `precos-cardmarket`
5. **`nucleo-colecoes`** → `colecoes.garantir_colecoes(con)`
6. **`precos-pt`** → `cotacoes.recolher_pt(con, prices.CardTrader(), hoje)`; sem `CARDTRADER_TOKEN` → erro dito no passo (vermelho), nunca em silêncio
7. **`nucleo-vigiados`** → `cotacoes.gravar_vigiadas(con, hoje)`
8. **`nucleo-jogada`** → `jogada.registar(con)` (**antes** do `prune`)
9. `podar-precos`, `podar-ligas`, `prune`
10. `nucleo-decks`, `nucleo-vigias`, `nucleo-valor`, `nucleo-paginas`, `checkpoint`

- [ ] **Passo 1 — teste a chumbar:** `caso_ordem_dos_passos` (com `_step` substituído por um registo dos nomes e as funções de rede trocadas por falsas: a ordem acima, e `nucleo-jogada` antes de `prune`).
- [ ] **Passo 2–4 — chumbar, implementar, verde.**
- [ ] **Passo 5 — commit:** `daily: collections, PT prices, watched prices and played cards`.

### Tarefa 14: verificação e documentação

- [ ] **Passo 1:** `py tests\_bateria.py` — só as três falhas antigas.
- [ ] **Passo 2:** na base real (sem correr o `daily.py` inteiro), `py -m mtgvault.cli nucleo colecoes` (cria as 4 coleções) e os três passos novos à mão, pelas funções: `cotacoes.recolher_pt`, `cotacoes.gravar_vigiadas`, `jogada.registar` (sobre as listas que ainda houver). Dizer ao André o que saiu (quantas Shocks PT com preço, quantas vigiadas).
- [ ] **Passo 3:** reiniciar o 8771 (`py _reiniciar_webapp.py` + `py C:\Users\Catarina\Desktop\ai-pc\runner.py run mtgvault-serve`) **avisando-o**; ver no browser (desktop e telemóvel) `colecoes.html`, uma coleção, `#subir`, Vender e um deck.
- [ ] **Passo 4:** no ai-pc, os passos do mtgvault no `e2e-sites` passam a esperar 4 entradas no menu e a página Coleção.
- [ ] **Passo 5:** secção nova no `CLAUDE.md` do projeto: «Coleção e fotos (30/10/2026)» — as tabelas, o fluxo das fotos pelo CLI (`nucleo extrair/recortar/validar`) e as três decisões (nome da página, posse na `n_colecao_carta`, vigiadas só na mudança).
- [ ] **Passo 6 — commit:** `docs: Colecao and photo validation in CLAUDE.md`. Publicar só com autorização dele.
