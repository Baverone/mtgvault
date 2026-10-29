# Site do MTG: núcleo novo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pôr mtg.baverone.com a responder só a «que decks tenho, o que falta, o que vender, quanto vale», com 14 decks em dois modos (sempre montados / rotativos), edição e acabamento escolhidos por carta, versões das listas com fonte, e modo de edição no telemóvel.

**Architecture:** Um pacote novo `mtgvault/nucleo/` com tabelas `n_*` no `vault.db`, que aproveita o catálogo Scryfall, o `price_history` da Cardmarket, as listas MTGO já recolhidas e a casca do site. Três páginas na raiz (`index.html`, `deck.html`, `vender.html`) geradas por módulos de raiz; o modo de edição são as mesmas páginas servidas pelo `webapp.py` com controlos. O antigo desliga-se pelo interruptor `nucleo.ligado` no `colecao_config.json`; nada se apaga.

**Tech Stack:** Python 3.14 só biblioteca padrão, SQLite, HTML/CSS/JS sem frameworks; testes como scripts `caso_*` corridos pelo `tests/_bateria.py`.

**Spec:** `docs/superpowers/specs/2026-10-28-site-mtg-nucleo-design.md`

## Global Constraints

- Só biblioteca padrão; nenhuma dependência nova (REGRAS.md do ai-pc).
- Testes nunca abrem a base real: correr com `MTGVAULT_BASES_PROIBIDAS` armado (o `_bateria.py` arma-o); bases temporárias por `db.session(tmp_vault, tmp_catalog)`.
- O núcleo **nunca escreve** em `copies`, `copy_allocation`, `posse_marcada`, `decks`, `deck_cards`, `watched*` — só em tabelas `n_*`.
- `colecao_config.json` só se escreve por `configio.escrever(cfg)` e depois `sources.esquecer_config()`.
- Textos visíveis e comentários em português de Portugal; nomes no estilo do repositório (português, `snake_case`).
- Preços: `price_history`/`price_latest`, `source='cardmarket'`, coluna `trend`, `finish` `'nonfoil'`/`'foil'`. Nunca inventar preço: sem preço → «sem preço», fora dos totais, e conta-se quantas.
- Páginas só na raiz com nome `[a-z_]+\.html`; geradores são módulos de raiz `<mod>.py` com `build(con, out_path, rep=None)`.
- Commits: uma linha ASCII + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Moxfield: nunca pedidos HTTP diretos nem User-Agent falso; só o ficheiro escrito pela tarefa `mtg-moxfield-chrome`.

## Review Focus

1. Lista colada com um nome que não existe no catálogo (gralha, carta de duas faces escrita só com a frente, «Fire // Ice») → nada se grava, erro com os nomes em falta; a frente de uma carta de duas faces resolve-se para a carta. Teste na Tarefa 2.
2. A mesma lista colada duas vezes, ou o vigia a ler a mesma lista → não nasce versão nova. Teste na Tarefa 2.
3. Uma lista de um rotativo muda e uma carta passa de fixa a partilhada (ou o contrário) → as cópias marcadas mudam de âmbito com ela e o valor total não muda. Teste na Tarefa 3.
4. Carta sem preço Cardmarket (ou só foil) → «sem preço» na página, fora dos totais com contagem, nunca 0 € silencioso. Teste na Tarefa 4.
5. Duplo toque no «Tenho +1» (o telemóvel repete o pedido) → conta uma vez (`request_id`). Teste na Tarefa 8.

---

### Task 1: Tabelas, decks e interruptor

**Files:**
- Modify: `mtgvault/schema.sql` (fim do ficheiro), `mtgvault/db.py` (`_migrate`, depois do bloco de `posse_marcada` ~:395)
- Create: `mtgvault/nucleo/__init__.py`, `mtgvault/nucleo/modelo.py`
- Test: `tests/test_nucleo_modelo.py`

**Interfaces:**
- Produces:
  - Tabelas (iguais em `schema.sql` e `_migrate`, `CREATE TABLE IF NOT EXISTS`):
    - `n_deck(slug TEXT PK, nome, formato, modo CHECK IN ('sempre','rotativo'), vigia TEXT NULL, arte_nome TEXT NULL, ordem INT, vigia_ok_em TEXT NULL, vigia_erro TEXT NULL)`
    - `n_versao(id INTEGER PK, slug, numero INT, criada_em TEXT, fonte TEXT, origem CHECK IN ('andre','vigia'), UNIQUE(slug, numero))`
    - `n_versao_carta(versao_id, seccao CHECK IN ('main','side','comandante'), nome, qtd INT)`
    - `n_edicao(ambito, nome, scryfall_id, acabamento CHECK IN ('nonfoil','foil'), PRIMARY KEY(ambito, nome))`
    - `n_posse(ambito, scryfall_id, acabamento, qtd INT CHECK (qtd>=0), PRIMARY KEY(ambito, scryfall_id, acabamento))`
    - `n_posse_log(request_id TEXT UNIQUE, ambito, scryfall_id, acabamento, delta INT, em TEXT)`
    - `n_montado(id INTEGER PK CHECK(id=1), slug)`
    - `n_a_mais(scryfall_id, acabamento, qtd INT, nota TEXT, PRIMARY KEY(scryfall_id, acabamento))`
    - `n_saida(id INTEGER PK, slug, motivo CHECK IN ('saiu_da_lista','trocou_edicao'), versao_id NULL, scryfall_id, acabamento, qtd INT, em TEXT)`
    - `n_valor(dia TEXT PK, total_eur REAL, copias INT, sem_preco INT)`
  - `modelo.DECKS: tuple[dict]` — os 14 do spec, com `slug` (`[a-z_]+`), `nome`, `formato`, `modo`, `vigia`, `arte_nome`. Slugs fixos: `pauper_affinity`, `premodern_stifflenough`, `premodern_replenish`, `premodern_enchantress`, `premodern_elves`, `premodern_igg`, `premodern_oath`, `cedh_blue_farm`, `cedh_cloud`, `dc_cloud`, `pioneer_greasefang`, `modern_affinity`, `modern_oswald`, `legacy_welder_cam`. Vigias: `mtgo:LuffyDoChapeuDePalha:pauper`, `mtgo:LuffyDoChapeuDePalha:premodern`, `moxfield:7O1sCuIti0igU6Us_Jhadg`, `moxfield:k6f2yED7oUGPtK2_rN_xwg`.
  - `modelo.MODO_DO_FORMATO = {"premodern":"sempre","cedh":"sempre","pauper":"sempre","duel-commander":"sempre","standard":"rotativo","pioneer":"rotativo","modern":"rotativo","legacy":"rotativo"}`
  - `modelo.garantir_decks(con) -> int` (insere os que faltam, não mexe nos existentes; devolve quantos inseriu)
  - `modelo.ligado(cfg=None) -> bool` (lê `nucleo.ligado` por `configio.ler`, omissão `False`)
  - `modelo.decks(con, modo=None) -> list[sqlite3.Row]` por `ordem`

- [ ] **Step 1: Escrever `tests/test_nucleo_modelo.py`** com `caso_tabelas_criadas` (todas as `n_*` existem depois de `db.session`), `caso_garantir_decks_idempotente` (1.ª chamada → 14, 2.ª → 0, `count(*)` = 14), `caso_modos` (4 rotativos: greasefang, modern_affinity, modern_oswald, legacy_welder_cam; 4 vigiados), `caso_ligado_omissao_false` (config temporária sem a chave → `False`).
- [ ] **Step 2:** `py tests\test_nucleo_modelo.py` → falha (`ModuleNotFoundError: mtgvault.nucleo`).
- [ ] **Step 3:** Tabelas em `schema.sql` + `_migrate`; `nucleo/__init__.py` vazio; `modelo.py` com o acima.
- [ ] **Step 4:** `py tests\test_nucleo_modelo.py` → `TUDO OK`.
- [ ] **Step 5:** Commit `nucleo: n_* tables, the 14 decks and the nucleo.ligado switch`.

### Task 2: Listas e versões

**Files:**
- Create: `mtgvault/nucleo/listas.py`
- Test: `tests/test_nucleo_listas.py`

**Interfaces:**
- Consumes: `n_versao`, `n_versao_carta`, `n_deck` (Task 1); `catalog.cards` para validar nomes.
- Produces:
  - `Linha = NamedTuple(seccao: str, nome: str, qtd: int)`
  - `ler_texto(texto: str) -> list[Linha]` — aceita `4 Nome`, `4x Nome`, Moxfield export `1 Nome (SET) 123` e `*F*`, cabeçalhos `Commander`/`Comandante`, `Sideboard`/`SB:`; linha vazia depois do main = sideboard; junta repetidos; ignora comentários `//` no início da linha.
  - `NomesDesconhecidos(ValueError)` com `.nomes: list[str]`
  - `normalizar(con, linhas) -> list[Linha]` — resolve para o `name` do catálogo (sem caixa, frente de duas faces → nome completo); levanta `NomesDesconhecidos`.
  - `versao_atual(con, slug) -> dict | None` → `{id, numero, criada_em, fonte, origem, linhas: list[Linha]}`
  - `diferenca(antes: list[Linha], depois: list[Linha]) -> dict` → `{"entrou": [(nome, qtd)], "saiu": [(nome, qtd)]}` por nome somando secções
  - `gravar_versao(con, slug, linhas, *, fonte: str, origem: str, quando: str | None = None) -> dict | None` — normaliza, devolve `None` se igual à atual; senão grava `numero+1` e devolve `{versao_id, numero, entrou, saiu}`. **Fonte obrigatória** (vazia → `ValueError("de onde veio a lista?")`). Chama `posse.depois_de_versao(con, slug, antes, depois, versao_id, origem)` (Task 3) na mesma transação.

- [ ] **Step 1: Testes** — `caso_ler_moxfield_export` (texto com `Commander`, `1 Kraum, Ludevic's Opus (CMR) 89`, `1 Force of Will (ALL) 54a *F*` → secções e nomes certos), `caso_ler_linha_vazia_e_sideboard`, `caso_nome_desconhecido_nada_grava` (gralha → `NomesDesconhecidos.nomes == ["Forse of Will"]`, `count(n_versao)` = 0), `caso_frente_de_duas_faces` (`Delver of Secrets` resolve para o nome completo semeado no catálogo de teste), `caso_mesma_lista_nao_cria_versao` (2.ª chamada → `None`, numero continua 1), `caso_diferenca` (v1 4 Fling → v2 2 Galvanic Blast: `entrou == [("Galvanic Blast", 2)]`, `saiu == [("Fling", 4)]`), `caso_fonte_obrigatoria`.
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar `listas.py` (com um `posse.depois_de_versao` mínimo que não faz nada até à Task 3, em `nucleo/posse.py`).
- [ ] **Step 4:** correr → `TUDO OK`.
- [ ] **Step 5:** Commit `nucleo: paste and version deck lists with source and diff`.

### Task 3: Edição, posse, partilha e montagem

**Files:**
- Create/complete: `mtgvault/nucleo/posse.py`
- Test: `tests/test_nucleo_posse.py`

**Interfaces:**
- Consumes: Tasks 1–2; `scryfall.impressoes(con, nome, limite=None)` para as edições em papel; preço por `valor.preco` (Task 4 — aqui só para a omissão «mais barata»; até lá usar `price_latest` direto numa função privada `_trend_hoje(con, sid, acab)`).
- Produces:
  - `ROT = "rotativos"` (âmbito das partilhadas)
  - `partilhadas(con) -> set[str]` — nomes em ≥2 decks rotativos (versão atual, todas as secções)
  - `ambito(con, slug, nome) -> str` — `ROT` se o deck é rotativo e o nome é partilhado; senão `slug`
  - `edicao(con, slug, nome) -> tuple[str, str] | None` — escolha gravada no âmbito; sem escolha: a impressão `nonfoil` com menor trend > 0; sem nenhuma com preço: a primeira de `scryfall.impressoes`; `None` se o nome não tem impressões em papel
  - `escolher_edicao(con, slug, nome, scryfall_id, acabamento) -> None` — valida que a impressão é desse nome e tem esse acabamento em `finishes` (`ValueError` senão); se havia posse da edição anterior no âmbito, move-a para `n_saida(motivo='trocou_edicao')` e zera-a
  - `ajustar(con, slug, nome, delta: int, *, request_id: str) -> int` — na edição atual do âmbito; idempotente por `request_id` em `n_posse_log`; nunca abaixo de 0; devolve a quantidade nova
  - `depois_de_versao(con, slug, antes, depois, versao_id, origem) -> None` — (a) nomes que deixaram de estar no deck com posse no âmbito do deck → `n_saida(motivo='saiu_da_lista')` (só se `origem=='vigia'`; numa lista do André também, é o mesmo caso); (b) rotativos: para cada nome cujo âmbito mudou (fixa↔partilhada), mover `n_posse` e `n_edicao` de âmbito (somando se já houver)
  - `estado_deck(con, slug) -> dict` → `{slug, nome, formato, modo, versao, cartas: [ {nome, seccao, qtd, scryfall_id, acabamento, tenho, falta, grupo: 'fixa'|'partilhada'|None, onde: 'aqui'|<nome do deck montado>|None, preco_un: float|None} ], total, tenho, custo_falta: float, sem_preco: int, montado: bool}` — `tenho = min(qtd, posse no âmbito)`; nos rotativos as partilhadas usam a posse de `ROT`
  - `definir_montado(con, slug) -> list[dict]` — só rotativos (`ValueError` senão); devolve os movimentos `{nome, qtd, de: <slug montado antes>, para: slug}` das partilhadas que o novo deck usa; grava `n_montado`
  - `movimentos_para(con, slug) -> list[dict]` — o mesmo cálculo sem gravar (para a caixa «para montar este»)

- [ ] **Step 1: Testes** — `caso_sempre_montados_nao_partilham` (2 premodern com 4 Force of Will cada; marcar 4 num → o outro continua com falta 4), `caso_rotativos_partilham_pelo_maximo` (modern 4 Urza's Saga, legacy 2 → marcar 4 em `ROT` dá falta 0 nos dois; marcar 3 dá falta 1 no modern e 0 no legacy), `caso_fixa_vira_partilhada_leva_posse` (Review Focus 3: legacy ganha uma carta que só o modern tinha, com 2 marcadas no âmbito `modern_affinity` → passam para `ROT`; soma de `n_posse.qtd` igual antes e depois), `caso_edicao_estrita` (posse na edição A, escolher B → `tenho` 0, `n_saida` com motivo `trocou_edicao` e qtd certa), `caso_foil_so_se_existir` (escolher foil numa impressão só `["nonfoil"]` → `ValueError`), `caso_saiu_da_lista_vai_para_saida`, `caso_ajustar_idempotente` (mesmo `request_id` duas vezes → qtd 1), `caso_nunca_negativo`, `caso_montar` (montado legacy; montar modern → movimentos com as partilhadas e `de == "legacy_welder_cam"`), `caso_montar_sempre_montado_recusa`.
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar `posse.py`.
- [ ] **Step 4:** correr → `TUDO OK`; e `py tests\test_nucleo_listas.py` continua `TUDO OK`.
- [ ] **Step 5:** Commit `nucleo: per-deck ownership, strict edition and finish, shared rotating pool, assemble moves`.

### Task 4: Preços, valor e Vender

**Files:**
- Create: `mtgvault/nucleo/valor.py`
- Modify: `mtgvault/prices.py:164` (`cards_of_interest`)
- Test: `tests/test_nucleo_valor.py`

**Interfaces:**
- Consumes: Tasks 1–3; `prices.write_prices` (para semear testes).
- Produces:
  - `preco(con, scryfall_id, acabamento, dia: str | None = None) -> float | None` — `trend` do `price_history` (`source='cardmarket'`, `finish=acabamento`, `date<=dia`, mais recente); com `dia=None` usa `price_latest`; `None` se não houver ou `trend<=0`
  - `inventario(con) -> list[tuple[str, str, int]]` — `(scryfall_id, acabamento, qtd)` somando `n_posse` (todos os âmbitos) e `n_a_mais`
  - `valor_em(con, dia: str | None = None) -> dict` → `{total_eur, copias, sem_preco}`
  - `gravar_valor_do_dia(con, dia: str) -> dict` — `INSERT OR REPLACE` em `n_valor`
  - `serie(con) -> list[tuple[str, float]]` — os dias de `n_valor`; antes do primeiro, os dias com `price_history` da Cardmarket (`SELECT DISTINCT date`) calculados com `valor_em(con, dia)`; ordenada
  - `a_vender(con) -> dict` → `{a_mais: [linha], saidas: [linha], total_eur, sem_preco}`, `linha = {nome, set_code, scryfall_id, acabamento, qtd, preco_un, motivo, deck}`
  - `a_mais_ajustar(con, scryfall_id, acabamento, delta, *, nota="") -> int`
  - `saida_resolver(con, saida_id: int, destino: str) -> None` — `destino` `'a_mais'` (passa para `n_a_mais`) ou `'descartar'` (apaga a linha de `n_saida`)
  - `cards_of_interest` passa a incluir: todos os `scryfall_id` de `n_posse`, `n_a_mais`, `n_saida`, `n_edicao`, e todas as impressões em papel dos nomes nas versões atuais (`n_versao_carta`)

- [ ] **Step 1: Testes** — `caso_preco_pelo_dia` (histórico 26/09 = 10, 30/09 = 12 → `preco(...,"2026-09-28") == 10`), `caso_foil_separado` (nonfoil 1 €, foil 5 € → cada acabamento o seu), `caso_sem_preco_fora_do_total` (Review Focus 4: 2 cartas, uma sem preço → `total_eur` só da outra, `sem_preco == 1`), `caso_cada_copia_uma_vez` (a mesma impressão em `ROT` não conta duas vezes por estar em dois decks), `caso_serie_preenche_para_tras` (preços em 3 dias, `n_valor` só no 3.º → 3 pontos), `caso_cards_of_interest_inclui_nucleo` (nome numa versão → todas as impressões semeadas aparecem), `caso_saida_para_a_mais`.
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar `valor.py` e o acrescento a `cards_of_interest`.
- [ ] **Step 4:** correr → `TUDO OK`; `py tests\test_movers.py` continua `TUDO OK`.
- [ ] **Step 5:** Commit `nucleo: Cardmarket trend per edition, daily value series and the sell list`.

### Task 5: Vigias (MTGO e ficheiro do Moxfield)

**Files:**
- Create: `mtgvault/nucleo/vigia.py`
- Test: `tests/test_nucleo_vigia.py`

**Interfaces:**
- Consumes: `decklists`/`decklist_cards` (já recolhidos pelo `harvest-mtgo`); `listas.gravar_versao`.
- Produces:
  - `PASTA_MOXFIELD = Path(os.environ.get("MTGVAULT_MOXFIELD_DIR", <repo>/data/moxfield))` — formato do ficheiro `AAAA-MM-DD.json`: `{"lido_em": iso, "decks": {"<moxfield_id>": {"texto": "<export>", "titulo": str} | {"erro": str}}}`
  - `vigiar_mtgo(con, slug) -> dict` — última `decklists` com `source` do MTGO, `lower(player)=lower(jogador)`, `format=formato`, por `event_date DESC, id DESC`; fonte `"MTGO · <event_name> · <event_date> · <url>"`; `{"estado": "nova"|"igual"|"sem_lista", ...}`
  - `vigiar_moxfield(con, slug, pasta=PASTA_MOXFIELD) -> dict` — ficheiro mais recente; fonte `"Moxfield · https://moxfield.com/decks/<id> · lido a <data>"`; `"sem_ficheiro"`/`"erro"` quando é o caso
  - `vigiar_todos(con) -> dict[slug, dict]` — grava `n_deck.vigia_ok_em` ou `vigia_erro`; um vigiado com estado `sem_lista`/`sem_ficheiro`/`erro` conta como falha
  - `class VigiaFalhou(RuntimeError)` levantada no fim por `vigiar_todos(..., levantar=True)` se houve falhas (depois de gravar as que correram bem)
- `.gitignore`: acrescentar `data/moxfield/`.

- [ ] **Step 1: Testes** — `caso_mtgo_ultima_do_jogador` (duas listas do Luffy em datas diferentes → versão da mais recente; jogador com caixa diferente também casa), `caso_mtgo_igual_nao_cria_versao`, `caso_moxfield_ficheiro_mais_recente` (pasta temporária com dois dias), `caso_moxfield_erro_no_ficheiro` (estado `erro`, `vigia_erro` preenchido, nenhuma versão), `caso_falha_levanta_no_fim` (um vigia bom e um sem lista → a versão boa fica gravada e `VigiaFalhou` levanta).
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** correr → `TUDO OK`.
- [ ] **Step 5:** Commit `nucleo: watched decks from harvested MTGO lists and the Moxfield file`.

### Task 6: As três páginas

**Files:**
- Create: `nucleo_painel.py`, `nucleo_decks.py`, `nucleo_vender.py` (raiz do repo), `mtgvault/nucleo/visual.py` (CSS e peças partilhadas: grelha de cartas, barra de progresso, imagem por `scryfall_id`)
- Test: `tests/test_nucleo_paginas.py`

**Interfaces:**
- Consumes: Tasks 1–5; `site_shell.head/abrir/fechar`, `paginas.eur`, `paginas.art(sid)` (URL `normal`/`small`; arte do mosaico: substituir `small` por `art_crop` no mesmo URL — confirmar no Step 4 que responde 200).
- Produces (cada módulo):
  - `html_page(con, *, editable: bool = False, token: str = "") -> str`
  - `build(con, out_path=None, rep=None) -> Path` (escreve `html_page(con)` em `index.html` / `deck.html` / `vender.html`)
- Conteúdo (do spec, Páginas): Painel = valor + variação de 30 dias + gráfico SVG inline (1 mês / 3 meses / tudo, só uma linha) + mosaico «Sempre montados» / «Rotativos» com `arte_nome` e barra + caixa Vender com total; Deck = todos os decks em `<section id="<slug>">`, JS mostra o do `location.hash` (sem hash: grelha dos decks), cabeçalho com progresso, `custo_falta`, versão/fonte/diferença da última, «ver versões» (lista de todas as versões com entrou/saiu), cartas em imagens (`tenho` a cores, falta a cinzento com `filter:grayscale`, foil com brilho), rotativos em «Fixas deste deck» e «Partilhadas» com `onde`, caixa «para montar este» com `movimentos_para`; deck fixo sem versão → «à espera da tua lista»; vigia com erro → «não consegui ver a lista desde <vigia_ok_em>»; Vender = três blocos (Tenho a mais, Saíram dos decks, Trocaste de edição) com preço e total.
- Com `editable=True` as cartas levam `data-deck`, `data-nome`, `data-sid`, `data-acab`; o JS de edição é da Task 8.

- [ ] **Step 1: Testes** — semear catálogo, 2 decks (um sempre, dois rotativos), preços e posse; `caso_painel_tem_valor_e_decks` (o total formatado por `paginas.eur` aparece; 14 mosaicos com `garantir_decks`), `caso_deck_cinzento_e_cor` (carta com falta tem a classe `falta`; carta completa não), `caso_rotativo_duas_partes` («Fixas deste deck» antes de «Partilhadas», `onde` com o nome do deck montado), `caso_espera_lista`, `caso_vigia_com_erro_diz`, `caso_vender_total`, `caso_sem_rede` (nenhum `<script src=` externo; imagens só de `cards.scryfall.io`), `caso_casca` (cada página tem `shell.abrir` com o ficheiro certo e o `h1` igual a `site_shell.titulo_de(ficheiro)`).
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar (mobile primeiro: grelha de 4 colunas a 390 px, 8 a 1440 px).
- [ ] **Step 4:** correr → `TUDO OK`; gerar numa pasta temporária a partir de uma **cópia** do `data/vault.db` real e abrir no browser do painel a 390 e 1440 px; confirmar que um URL `art_crop` responde.
- [ ] **Step 5:** Commit `nucleo: dashboard, deck and sell pages`.

### Task 7: Ligar o núcleo ao site e à recolha (interruptor)

**Files:**
- Modify: `mtgvault/site_shell.py` (`SECCOES`/`seccoes()`/`PAGINAS_DO_MENU`/`titulo_de`), `mtgvault/publicar.py` (`PAGINAS`, `PUBLICAVEIS`), `mtgvault/paginas.py` (`MENU`), `daily.py` (`main`), `.github/workflows/daily.yml` (linha `git add`), `colecao_config.json` (`"nucleo": {"ligado": true}` via `configio.escrever`)
- Modify tests: `tests/test_casca.py` (o mínimo de 15 ícones passa a valer só com o núcleo desligado), `tests/test_paginas.py` (secções do menu novo), `tests/test_publicar.py` (o conjunto de `PAGINAS` com o núcleo ligado)
- Test: `tests/test_nucleo_ligado.py`

**Interfaces:**
- Consumes: `modelo.ligado()`; geradores da Task 6; `vigia.vigiar_todos`; `valor.gravar_valor_do_dia`.
- Produces:
  - Com `nucleo.ligado`: `SECCOES` = uma secção «MTG» com `("index.html","", "casa","Painel",…)`, `("deck.html","", "cartas","Decks",…)`, `("vender.html","", "venda","Vender",…)` (ícones existentes do `site_shell`); `publicar.PAGINAS = [("nucleo_painel","index.html",False), ("nucleo_decks","deck.html",False), ("nucleo_vender","vender.html",False)]`; `PUBLICAVEIS` = essas três
  - `daily.main()` com `nucleo.ligado` corre só: `catalogo`, `harvest-mtgo` com `formats={"pauper","premodern"}`, `precos-scryfall`, `precos-cardmarket`, `podar-precos`, `podar-ligas`, `prune`, `nucleo-decks` (`garantir_decks`), `nucleo-vigias` (`vigiar_todos(levantar=True)`), `nucleo-valor` (`gravar_valor_do_dia(hoje)`), `nucleo-paginas` (`publicar.gerar`), `checkpoint`; com o interruptor desligado, exatamente o `main()` de antes
  - `.github/workflows/daily.yml`: `git add index.html deck.html vender.html` (o `test_publicar` confere-o)

- [ ] **Step 1: Testes** — `caso_menu_tres_entradas` (com config temporária ligada), `caso_menu_antigo_com_interruptor_desligado` (igual ao de antes), `caso_daily_passos_ligado` (substituir os passos por funções falsas e conferir a ordem e que nenhum dos desligados corre), `caso_vigia_falhada_fica_vermelha` (o passo `nucleo-vigias` regista `job_runs` com `erro`), `caso_publicar_tres_paginas`.
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar; ligar `nucleo.ligado` no `colecao_config.json` por `configio.escrever`.
- [ ] **Step 4:** `py tests\_bateria.py` → tudo verde (corrigir os testes antigos que contavam com o menu de 23 entradas, sem os enfraquecer quando o interruptor está desligado).
- [ ] **Step 5:** Commit `nucleo: switch the site, publishing and the daily job to the new core`.

### Task 8: Modo de edição

**Files:**
- Modify: `webapp.py` (rotas GET das três páginas com `editable=True` e o token; POSTs abaixo; `com_token` já aceita `[a-z_]+\.html`)
- Create: `mtgvault/nucleo/edicao_js.py` (o JS do modo de edição como texto, injetado por `html_page(..., editable=True)`)
- Test: `tests/test_nucleo_webapp.py`

**Interfaces:**
- Consumes: `posse.ajustar/escolher_edicao/definir_montado`, `listas.gravar_versao`, `valor.a_mais_ajustar/saida_resolver`, `scryfall.impressoes`, `valor.preco`; `_pode_escrever()` e `escrita()` existentes.
- Produces (JSON; erros como os existentes: `ValueError`→409, `NomesDesconhecidos`→422 com `{"nomes": [...]}`):
  - `GET /api/n/edicoes?nome=<n>&deck=<slug>` → `[{scryfall_id, set_code, set_name, collector_number, finishes, imagem, preco_nonfoil, preco_foil, escolhida: bool}]` (todas as impressões em papel, sem limite de 12)
  - `POST /api/n/marca {deck, nome, delta, request_id}` → `{qtd}`
  - `POST /api/n/edicao {deck, nome, scryfall_id, acabamento}` → `{ok: true}`
  - `POST /api/n/lista {deck, texto, fonte}` → `{numero, entrou, saiu}` ou `{"igual": true}`
  - `POST /api/n/montar {deck}` → `{movimentos}`
  - `POST /api/n/a_mais {scryfall_id, acabamento, delta}` → `{qtd}`; `GET /api/n/procurar?q=` → até 20 nomes do catálogo
  - `POST /api/n/saida {id, destino}` → `{ok: true}`
- JS: tocar numa carta abre a folha da carta (imagem grande, interruptor Normal/Foil só com os acabamentos que existem, edições lado a lado com preço, «Tenho +1»/«−1» com `request_id = crypto.randomUUID()`); no deck, «Colar lista nova» com textarea e campo obrigatório «De onde veio?»; nos rotativos «Montar este deck» mostra os movimentos; em Vender, procurar carta + edição + acabamento + quantidade. Depois de cada POST bom, recarrega a secção.

- [ ] **Step 1: Testes** (servidor num porto livre, base temporária) — `caso_marca_idempotente` (Review Focus 5: dois POST com o mesmo `request_id` → `qtd` 1), `caso_sem_token_recusa` (pedido não-loopback sem token → 403), `caso_lista_sem_fonte_409`, `caso_lista_nome_errado_422_com_nomes`, `caso_edicoes_todas` (nome com 15 impressões semeadas → 15), `caso_montar_sempre_montado_409`, `caso_pagina_editavel_tem_token_e_js`.
- [ ] **Step 2:** correr → falha.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** correr → `TUDO OK`; arrancar o webapp numa cópia (`MTGVAULT_DB` para uma cópia, outro porto) e, no browser do painel a 390 px, marcar uma carta, trocar de edição, pôr foil, colar uma lista com fonte e montar um rotativo.
- [ ] **Step 5:** Commit `nucleo: edit mode for marks, editions, finishes, lists, assembling and selling`.

### Task 9: ai-pc — Moxfield no Chrome, recolha, publicação e e2e

**Files (repo `ai-pc`, ramo próprio):**
- Create: `tasks/mtg-moxfield-chrome/{task.json,run.py,test.py}`, `prompts/mtg-moxfield.md`
- Modify: `tasks/mtgvault-daily/run.py:34` e `test.py:40` (`HTML` = `index.html`, `deck.html`, `vender.html`), `tasks/mtgvault-publicar/run.py:79` e `test.py:64` (lista de reserva), `tasks/e2e-sites/cenarios.py` (`mtg_abre`: `.n-valor` com um algarismo; `mtg_links`: exatamente 3 entradas no menu; novo `mtg_deck`: `deck.html#pauper_affinity` mostra a secção e imagens; retirar `mtg_faltas`, `mtg_arrumacao`, `mtg_deckboxes`, `mtg_procurar`, `mtg_urgencias`, `mtg_imagens` e `_mtg_alvo` do `PASSOS`/`FUNCOES` e do `test.py`), `tests/test_tarefas.py` (cenários da tarefa nova), `CLAUDE.md` (linha da tarefa nova)

**Interfaces:**
- `mtg-moxfield-chrome` copia o desenho da `tibia-xp-chrome`: `at 10:45`, entra com `"enabled": false` (regra do ai-pc para tarefas `at` novas) e liga-se depois de o runner reiniciar; Claude local com `--chrome`, ferramentas Read/Write + Chrome; abre os dois links num separador próprio, usa o «Export» de texto; máx. 2 páginas/dia; desafio do Cloudflare → pára (`desafio`); Chrome fechado → `sem_chrome`; escreve `<mtgvault>\data\moxfield\AAAA-MM-DD.json` no formato da Task 5.
- `test.py`: o ficheiro de hoje foi escrito nesta corrida, tem os dois ids, cada um com `texto` de ≥ 60 linhas de carta ou `erro`; vermelho em `sem_chrome`/`desafio`/erro.

- [ ] **Step 1:** cenários em `tests/test_tarefas.py` para a tarefa nova (ficheiro em falta; ficheiro de ontem; só um deck) → `py tests\test_tarefas.py` falha.
- [ ] **Step 2:** implementar a tarefa, o prompt e as mudanças às outras tarefas.
- [ ] **Step 3:** todos os `py tests\test_*.py` do ai-pc verdes.
- [ ] **Step 4:** Commit `mtgvault: new core pages in daily/publish/e2e and the Moxfield Chrome task`.

### Task 10: Pôr no ar e confirmar

- [ ] **Step 1:** `py tests\_bateria.py` no mtgvault → verde; ai-pc → verde.
- [ ] **Step 2:** Merge `mtg-nucleo` no `main` do mtgvault (`work/juntar-ramo.py` se existir para o mtgvault, senão `git merge --no-ff`) e o ramo do ai-pc no `master`; push.
- [ ] **Step 3:** Na base real: `garantir_decks`, `vigiar_todos` (MTGO; o Moxfield na primeira corrida da `mtg-moxfield-chrome`, corrida à mão uma vez com `py runner.py run mtg-moxfield-chrome` depois de a ligar), `gravar_valor_do_dia`, e publicar por `py runner.py run mtgvault-publicar`.
- [ ] **Step 4:** Reiniciar o webapp (`_reiniciar_webapp.py`) e confirmar o modo de edição em `http://localhost:8771/` e `editar-mtg.baverone.com`.
- [ ] **Step 5:** Ver no Chrome (desktop e iPhone pelo Playwright do e2e) o painel, um sempre montado, um rotativo e Vender em mtg.baverone.com; `py runner.py run e2e-sites` verde no mtg.
- [ ] **Step 6:** Mensagem ao André: o que está no ar, o que fazer a seguir (dar as listas dos 10 fixos com a fonte; marcar o que tem), e o que ficou desligado.
