# CLAUDE.md

Contexto do projeto para o Claude Code. Lê isto antes de mexer em código.

## O que é

Gestor pessoal de coleção de Magic, do André. Python + SQLite, corre no PC dele
(Windows) e também como job diário no GitHub Actions. Sem servidor, sem frameworks.

Faz quatro coisas: gere a coleção física, segue decks, analisa o metagame para
descobrir o núcleo de cada arquétipo, e acompanha preços.

## Regras de trabalho

- **Comentários e mensagens em português (de Portugal).** Nomes de funções,
  variáveis e tabelas em inglês. É a convenção já estabelecida no código.
- **Todos os testes correm sem rede.** Se precisares de HTML de um site,
  captura um trecho real e mete-o como fixture no teste. Não faças `mock` de
  bibliotecas inteiras.
- **Corre a bateria toda antes de dares uma tarefa por fechada:**
  `cd tests && py _bateria.py` (um processo por ficheiro, e resume no fim).
  **Todo o teste que fixe o `MTGVAULT_HOME` tem de fixar também o
  `MTGVAULT_DB`** — os ficheiros que acompanham a base (`arquetipos.json`,
  `vendas.csv`, `registos-faltas.csv`) saem de `db.pasta_dados()`, que é a pasta
  da `MTGVAULT_DB`, e neste PC essa variável aponta para o `data/` a sério.
  Correr a bateria **esvaziava o `data/arquetipos.json`** dele (24 arquétipos,
  333 linhas) sem um único teste falhar. Tem teste
  (`test_paginas.caso_a_bateria_nao_escreve_no_data_a_serio`).
- **Não inventes dados.** Se não conseguires aceder a uma fonte, diz que não
  conseguiste. Nunca preenchas uma decklist ou um preço a partir de memória.
- Comentários explicam *porquê*, não *o quê*. Vários dos comentários atuais
  existem para registar decisões que custaram a descobrir — não os apagues.

## Arquitetura

```
mtgvault/
  db.py           ligação, ATTACH do catálogo, migrações
  schema.sql      vault.db (coleção, decks, decklists, preços, watchlist, copy_allocation)
  catalog_schema.sql   catalog.db (só a tabela cards)
  scryfall.py     catálogo via bulk data
  paginas.py      o MENU e o TEMA de todas as páginas (uma lista só) + os
                  ajudantes que elas partilham (cor, tipo, posse total, faltas)
  caixas.py       AS CAIXAS: a única noção de deck (v6, 2026-09-08) — lê/migra o
                  `colecao_config.json → caixas`, e `para_slot` dá a forma
                  interna que o loadout consome (aceita a v5 e a v6)
  configio.py     ler/gravar o `colecao_config.json` sem lhe estragar a forma
  qr.py           códigos QR em Python puro (o link do modo edição no telemóvel)
  migracao.py     modelo de colecção única: funde os baldes na `Colecção`
  collection.py   exemplares, sub-coleções, reservas, valor, movimentos
  wantlist.py     o que falta, para decks e para arquétipos
  loadout.py      os decks montados ao mesmo tempo: aloca a coleção às caixas
                  (uma cópia serve uma só), conflitos, substitutos e venda
  premodern.py    o que montar A SEGUIR (top-10 + top-5 combo, cobertura COMO SE
                  fosse a caixa nº1 do grupo — v8, 2026-09-08) e o que vai à venda
  arquetipos.py   a IDENTIDADE de um arquétipo pelo NÚCLEO de cartas (id estável,
                  herdado acima de 70 %), e o registo `data/arquetipos.json` —
                  o nome é só apresentação (v9, 2026-09-08)
  analysis.py     clustering de arquétipos + core/flex/tech + prune
  stock.py        listas padrão e cobertura
  sources.py      mtgo.com + parser de texto + store_decklist (deduplicação)
  mtgtop8.py      duel-commander, premodern, cedh, e papel
  moxfield.py     decks do Moxfield
  watchlist.py    vigiar jogadores e decks, snapshots e diffs
  prices.py       Scryfall bulk (grátis) + Cardmarket (ficheiro) + CardTrader (API)
  cli.py          interface de linha de comandos
daily.py          o job diário (encadeia tudo o que está abaixo)
.github/workflows/daily.yml
```

**Geradores do site (scripts na raiz, corridos pelo `daily.py`, HTML no GitHub Pages):**
```
meta_coverage.py    cobertura.html — top-10 ponderado + staples + emergentes. NB (2026-09-07): quem decide que listas contam é `sources.lista_conta`/`counting_sql` (ver "Que listas contam"), e o peso vem de `sources.tier_weight_sql`; janela 30 dias; expõe COLLECTION_BALDES={"SPML","Premodern (geral)"}, owned_available(con) (=coleção MENOS cartas comprometidas com decks vigiados) e counting_lists(con,fmt,aid). NB (2026-09-07): `FORMATS` deixou de ser fixo — filtra `_FORMATS` por `colecao_config.json`→`formatos_metagame` (hoje standard/pioneer/modern; o Premodern saiu). Só a COBERTURA lê essa lista: o `metagame.py` deixou de a ler (ver abaixo)
decks_faziveis.py   RETIRADO 2026-09-07 — fundido no `metagame.py`, que faz a mesma pergunta com as regras de material e o "onde está a carta". O módulo ficou como lápide (levanta RuntimeError), o `decksfaziveis.html` reencaminha para o metagame, saiu do `daily.py` e do `git add` do workflow. Podem ser apagados os dois
buildability.py     (DORMENTE) o "Montar" foi tirado do menu p/ o André refazer; já NÃO corre no daily nem vai ao git-add. já NÃO é importado por ninguém desde a v6 (o `meusdecks.py` ficou só com o reencaminhamento)
classify.py         classificação Deck/Coleção/Vender (alimenta colecao_cor.html)
colecao_cor.py      colecao_cor.html — "Binders": coleção INTEIRA por cor→CMC; cartas em uso a escuro + rótulo (classify rep["deck"]/used_by); + secção "Decks vigiados" (Blue Farm/Cloud cEDH/Cloud/Pauper): o deck por inteiro + cartas "extra" que saíram da lista (retidas até 6 meses da última utilização — `_watched_deck_pools`). NB (2026-09-07): `_de_outro_balde` acrescenta as cartas que o LOADOUT dá a essa caixa mas que estão arrumadas noutro balde, marcadas "de &lt;balde&gt;" (era aqui que os Utrom Monitor do SPML desapareciam do Pauper)
collection_gallery.py  colecao.html — galeria por sub-coleção
core_decks.py       (coredecks.html APAGADO 2026-08-26, a redefinir; NÃO vai ao git-add) — mas core_decks.py continua a correr no daily p/ calcular card_price/posse
alertas.py          alertas.html — vender/comprar por movimento de preço (fora do menu atual)
meusdecks.py        FUNDIDO NO deckboxes.py (2026-09-08, v6) — a "Decks permanentes" fazia a MESMA pergunta ("quanto tenho deste deck?") e respondia outro número, porque contava a colecção inteira por deck em vez da alocação. Saiu do MENU e do `index.html`; o módulo continua a correr no daily mas só escreve um REENCAMINHAMENTO (`deckboxes.redireccionamento`), porque o link vive no telemóvel dele e no site publicado. O que ela tinha e a Deckboxes não tinha passou para a aba da caixa: lista por TIPO, imagens grandes, "copiar a lista" e "quantas tenho na colecção inteira" (informação secundária). Os ajudantes que outras páginas usavam (`_type_map`, `_group_by_type`, `_faltas`, `_faltas_html`, `_art`) estão agora em `mtgvault/paginas.py` — o `showcase.py` lê-os de lá
deckboxes.py        deckboxes.html — "Deckboxes": o LOADOUT (colecao_config.json→loadout), os decks montados ao mesmo tempo com a coleção REPARTIDA entre eles (uma cópia física serve uma caixa só). NB (2026-09-07): a página foi reescrita com **uma ABA POR DECK** (o pedido dele: *"faz como no riftvault — no botão, cada deck tem uma aba própria"*), mais as abas **Todas**, **✅ Decks montados** / **🔧 Decks para montar** (2026-09-08, ver a secção própria), **Arrumar**, **Partilhadas**, **Comprar**, **Vender** e — desde 2026-09-08 — **Sugestões** (as caixas candidatas de Premodern; só existe se houver caixas desse formato). Os dados vão em JSON dentro do HTML (`<script id="dados">`) e o render é JavaScript — o MESMO ficheiro serve o site publicado (`editable:false`) e o modo edição do `webapp.py` (`editable:true`, com botões). Por caixa: barra, dois números ("faltam comprar" e "ir buscar a outra caixa"), grelha de cartas com três estados, "tirar de:" (`slot["origens"]`), substitutos, wantlist Cardmarket (SÓ o que é mesmo compra). Na aba **Comprar**, cada linha diz para que caixa é a compra (`para`) e em que material (`loadout.requisito_material`), há selector por caixa (o "copiar" copia só o filtro activo) e as cartas ≥100 €/cópia levam chip «cara» e total à parte — Mishra's Workshop sozinha vale mais do que o resto da lista. Motor em mtgvault/loadout.py
webapp.py           MODO EDIÇÃO local, **porto 8771** (o 8770 é do `riftvault serve` — não trocar). Serve o `deckboxes.html`/`metagame.html` com os botões: painel *Montar* (*Sleevado e na caixa*), *Já arrumei tudo*, *Actualizei*, *Vendida*, *Tornar permanente*, *Subir/Descer* e *Vou montar este*. As PREFERÊNCIAS vão para o `colecao_config.json` (as `caixas` vão no Git); o que é FÍSICO vai para a `copy_allocation` e, na venda, sai da `copies` + `data/vendas.csv`. NB (2026-09-08): **ouve em `MTGVAULT_BIND`, por omissão `127.0.0.1`** (a tarefa `mtgvault-serve` põe `0.0.0.0` para o telemóvel), e as ESCRITAS exigem o token de `data/webapp.token` — ver "O telemóvel e o token". Mantido de pé pela tarefa `ai-pc/tasks/mtgvault-serve` (verifica de 5 em 5 min, relança destacado)
metagame.py         metagame.html — "Metagame": desde 2026-09-07 já NÃO é o top-10 de cada formato; é o **top-N que ele está mais perto de concluir** (`colecao_config.json`→`metagame_top_n`, default 3). `SECOES` decide o modo por formato: `top` (Standard/Pioneer/Legacy — as caixas do loadout por escolher, via `loadout.foil_report`), `caixas` (Modern — o deck já escolhido, do próprio loadout) e `premodern` (o ranking de sugestões — top-10 de representação + top-5 combo, cobertura **como principal** + a do que sobra ao lado, e os botões «vou montar este» / «não quero este»; era `alvos`, só o `premodern_arquetipos_alvo`, até 2026-09-08). Posse pela alocação do loadout, três estados, wantlist Cardmarket. NÃO lê `formatos_metagame` (o Legacy tinha de entrar e não está lá)
(prioridade.py + metafaltas.py APAGADOS 2026-08-26, a redefinir)
reservedlist.py     reservedlist.html — Reserved List (Scryfall) x coleção, por edição, preço/evolução, e 'VENDER' as que não jogam em formato nenhum
caixarl.py          caixarl.html — "Caixa Reserved List": a RL que está fora da coleção jogável
showcase.py         showcase.html — "Decks Showcase Challenger": eventos competitivos recentes (MTGO + presenciais do mtgtop8) agrupados por arquétipo. Tinha filtro e pesos PRÓPRIOS (fonte + showcase_min_players + lista de nomes casuais) — era por isso que continuava a dar listas enquanto o metagame vinha vazio. Desde 2026-09-07 usa `sources.counting_sql`/`tier_weight` como toda a gente; a chave `showcase_min_players` do config deixou de existir. NB (2026-09-09): cada arquétipo vai DOBRADO num `<details>` (o primeiro de cada formato aberto) — eram 4 320 `<img>` numa parede só e o browser tratava-as todas; agora trata **141**. As imagens continuam a ter `src` a sério e `loading="lazy"`: dentro de um `<details>` fechado o browser não as descarrega, e um `data-src` preenchido por JavaScript dava o mesmo ganho mas deixava a página vazia com o JS desligado. Tem teste (`test_showcase_dobrado.py`)
my_decks.py         segue decks-alvo (por assinatura e por jogador de MTGO) -> tabela decks
commander_decks.py  decks de comandante por consenso EM CAMADAS: núcleo>=50% (=deck, deck_cards) / flex 25-50% / tech 15-25%; FILTRA pela cor do comandante. `tiers()` reusado pelo colecao_cor
premodern_decks.py  consenso dos arquétipos-alvo de Premodern (`colecao_config.json`→`premodern_arquetipos_alvo`: UW Replenish, Enchantress) -> decks/deck_cards com o sufixo " (consenso)". Agrupa pelas etiquetas do `tagging` (o clustering não os separa) e usa `stock.stock_from_lists`. Mostrado nas `deckboxes` (era o `meusdecks`)
refresh_collection.py  collection_owned p/ o index.html
colecao_config.json    config: spml_formatos, premodern_decks_completos, banimentos_manuais, regras_colecao, loadout, regras_por_formato, metagame_fontes, formatos_metagame, premodern_arquetipos_alvo, so_jogadores_vigiados
```
Cada `.html` gerado tem de estar na lista do `git add` do workflow (`daily.yml`,
passo "Guardar HTML") **e na lista `HTML` da tarefa `ai-pc/tasks/mtgvault-daily`**
(o job que corre no PC) — o `deckboxes.html` esteve semanas só na primeira e
nunca era publicado pelo PC. E, se for página nova, com link no `index.html`.

**O menu e a paleta vivem num sítio só: `mtgvault/paginas.py`** (2026-09-07).
Antes cada gerador escrevia o seu `<nav class="tabs">` à mão, e o `cobertura.html`
ficou meses com um menu de Agosto — sem Deckboxes nem Metagame. Uma página órfã
não dá erro: só deixa de se lá chegar. Acrescentar uma aba é acrescentar uma
linha ao `paginas.MENU`; os templates trazem `%META%`, `%TEMA%` e `%TABS%`, e o
`build()` de cada página substitui-os. O `test_paginas.py` tranca as duas coisas
(o menu completo e o `git add` do workflow).
**A EXCEPÇÃO É O `index.html`** (2026-09-09): é estático, escrito à mão, e é a
única página cujo menu não sai do `paginas.nav()`. Gerá-lo por código era trazer
um gerador novo para a porta de entrada do site, por isso o que fica é o TESTE —
`test_paginas.caso_o_indice_tem_o_mesmo_menu_que_o_paginas` compara ficheiros e
ícones do `<nav class="tabs">` com o `MENU` (sem o próprio índice) e do
`<div class="subnav">` com o `EXTRA`, **nos dois sentidos e pela ordem**. Os
rótulos podem ser mais compridos no índice (*"Decks & Deckboxes"* onde a barra de
cima só diz *"Deckboxes"*), mas o do menu tem de estar lá dentro.

### Duas bases de dados

`catalog.db` (Scryfall, centenas de MB) é ATTACHed como schema `catalog`.
Está separada porque passa dos 100 MB por ficheiro que o GitHub aceita, e é
reconstruível. O SQLite resolve nomes não qualificados nas bases anexadas, por
isso `SELECT ... FROM cards` funciona na mesma.

**Consequência:** o SQLite não suporta chaves estrangeiras entre bases de dados.
`copies.scryfall_id` não tem FK declarada — a integridade é garantida no código
(`collection.add_copy` valida contra o catálogo antes de inserir).

**Migrações:** `CREATE TABLE IF NOT EXISTS` não acrescenta colunas a tabelas já
criadas. Toda a coluna nova tem de entrar também em `db._migrate()`.

Colunas/tabelas novas de 2026-09-07 (todas nos três sítios): `copies.balde_origem`
(o balde de ONDE a cópia veio, escrito pela `migracao`) e a tabela
`copy_allocation` (que cartas estão dentro de que deckbox — escrita pelo
`loadout.guardar_arrumacao` e pelo botão "Sleevado e na caixa").

Já custou caro uma vez: `decklists.event_tier` foi acrescentada só ao `vault.db`
(commit 56ffa3f, 2026-08-03), nunca ao `schema.sql` nem ao `_migrate()`, e nada
a preenchia. As listas novas ficavam a NULL, o top-10 do metagame vinha vazio —
e o `daily.py` dizia `[ok]` na mesma, porque o passo corria sem erro. **Uma
coluna que ninguém escreve não dá erro: dá páginas vazias.** Se acrescentares
uma coluna à mão, mete-a nos três sítios e escreve-a algures.

## Regras de domínio que não podem partir

**Coleção de colecionador vs de jogador.** `copies.purpose` é `player` ou
`collector`. As de colecionador são avaliadas mas **nunca** contam para decks,
wantlists ou cobertura.

**Cartas reservadas.** `copies.reserved_deck_id` prende exemplares a um deck.
`owned_playable(con, for_deck_id)` exclui as reservadas a *outros* decks. Se
acrescentares uma consulta nova de disponibilidade, tem de respeitar isto.

**Extras dos decks vs venda (REGRA A AFINAR).** As cópias a mais de uma carta
que está num deck são "cartas extra dos decks" (backup — guardar) até um LIMITE;
**acima do limite, o excedente é para vender**. O limite depende da coleção/pasta
(cada pasta é uma coleção com a sua regra):
- **Construído** (SPML, Premodern, Pauper Affinity): **4 por carta** (playset).
  Mais de 4 → o que passa de 4 é para vender.
- **Commander** (Blue Farm, Cloud, Cloud cEDH): **1 por deck** que a usa
  (singleton). O que passa disso é para vender.
Cartas que não estão em deck nenhum: excedente de venda normal.
`collection.deck_extras` é a versão SIMPLES (owned − o que a decklist pede) —
ainda **não** aplica os limites por coleção nem o "acima do limite = vender".
Quem JÁ aplica os limites é `mtgvault/loadout.py` (ver abaixo), e com uma
correção que importa: o playset de 4 conta a **coleção inteira**, não 4 por
balde — 4 Intuition no `Premodern (geral)` mais 4 na `Caixa Reserved List` são
8 cópias da mesma carta, e contar 4 por balde deixava passar o dobro.

**UMA SÓ NOÇÃO DE DECK: A CAIXA (`mtgvault/caixas.py`, v6, 2026-09-08).** Palavras
do André: *"No mtgvault já começamos a ter informação duplicada. Temos decks
vigiados e deckbox que é a mesma coisa. Tenta revisar isso e implementar
melhorias. Espero começar a montar os decks em deckbox o mais cedo possível para
começar a comprar as faltas e livrar-me dos excessos de cartas."*

Havia **duas** estruturas para o mesmo objecto: a `watchlist`/`decks_vigiados`
(que alimentava a *Decks permanentes*, onde cada deck contava a **colecção
inteira**) e o `loadout` (as caixas, onde a colecção é **repartida**). Duas
páginas, dois números para a pergunta *"quanto tenho deste deck?"*, e o rodapé de
cada uma a explicar que a outra também estava certa. É o padrão do `event_tier`.

- **`colecao_config.json → caixas`** substitui o `loadout`. Uma caixa = um deck.
  Chaves: `slot` (o id, é a chave da `copy_allocation` — não mudar), `nome`,
  `formato`, `fonte` (`vigiado` | `deck` | `consenso` | `escolhido` | `manual`),
  `ref`, `balde`, `estado`, `prioridade`, `variantes`, `notas`, e as regras de
  material só quando abrem excepção ao grupo.
- **`estado` é uma ESCALA, não três bandeiras**: `candidata` < `permanente` <
  `montada`, e `congelada` **calcula-se** (montada + dedicada + há linhas na
  `copy_allocation`). Antes eram `permanente`/`montado`/`por_confirmar` soltas, e
  nada impedia "montado mas candidato" — um deck sleevado na estante não é um
  candidato a nada. Escrever `congelada` no config vale `montada`; guardá-la a
  sério era a terceira cópia da mesma verdade. `por_confirmar` deixou de ser uma
  chave (é `fonte` sem `ref`): escrita à mão, ficava a mentir sempre que ele
  escolhia um deck.
- **A watchlist não desapareceu — passou a ser a FONTE de uma caixa.** O
  `watch-check` do daily continua a seguir a lista do Luffy e do Blue Farm, e o
  que ele traz é a lista da caixa (o delta *"actualizar deck"* é o resultado
  disso). O `decks_vigiados` fica: já não define decks, só marca quais têm
  prioridade dentro do grupo (`resolve_slots`) e o que o `meta_coverage` desconta.
- **O motor por baixo não mudou uma linha.** `caixas.para_slot` aceita as duas
  formas (v5 e v6) e devolve sempre a interna, com `permanente`/`montado` em
  booleano. Medido na base de 2026-09-08: 9 195,01 € para fechar, 287 a comprar,
  4 a ir buscar, venda 91c/702,95 € + 39 RL/5 736,16 €, arrumar 307 — **iguais**
  antes e depois. Se mexeres nisto, é o número a repetir.
- **Migração**: `python -m mtgvault.cli migrar-caixas` (tem `--dry-run`, faz
  backup do JSON ao lado e é idempotente). Já correu no config do repositório. O
  `webapp.ler_config` migra em memória, por isso um config da v5 continua a
  funcionar e o primeiro clique deixa o ficheiro no formato novo.
- **A Deckboxes é a página dos decks.** A *Decks permanentes* saiu do menu e o
  `meusdecks.html` é só um reencaminhamento (o `test_paginas` tranca as duas
  coisas: fora do menu **e** dentro do `git add`, senão o link antigo dá 404).

**O FLUXO «MONTAR» (v6).** Na aba de cada caixa, três passos por esta ordem:
1. **Tirar da colecção** — `loadout.plano_montar(res, slot)`: as cópias exactas
   (nome, edição, língua, acabamento, quantidade), **ordenadas por COR e depois
   por nome**, que é como as cartas estão no binder (`colecao_cor`: cor → CMC).
   Ordená-las por nome, como a arrumação geral faz, obrigava-o a percorrer o
   binder de trás para a frente por cada carta. Checkboxes no aparelho, e no fim
   *"sleevado e na caixa"* grava a `copy_allocation` e põe a caixa em `montada`.
   O cálculo é o mesmo da aba *Arrumar* (`loadout.movimentos_de_entrada`) — duas
   listas para o mesmo gesto era a segunda oportunidade de discordarem.
2. **Comprar** — a wantlist só desta caixa, em **dois formatos**: *"copiar p/
   Cardmarket"* (`N Nome`, uma linha por versão quando a carta se compra em dois
   materiais — somar as duas dava uma quantidade que nenhuma precisa) e *"copiar
   com material"* (`N Nome [PT]`). As ≥100 €/cópia levam chip «cara».
3. **Quando as compras chegarem** — fotos em `pendentes/`, a caixa recalcula-se
   na corrida seguinte. Não há nada para marcar à mão.

**A BARRA DE MONTAGEM: MARCAR AS CARTAS TODAS É DIZER QUE O DECK ESTÁ MONTADO
(André, 2026-09-08, à letra).** *"Não é mais fácil confirmares que eu seleccionei
todas as cartas do deck, e assim eu confirmo que montei o deck?"* Ele estava à
frente da estante, com o telemóvel, a marcar cartas — e não encontrou o «Sim,
está montada assim»: fica no **fim de 58 linhas**. Um botão que só existe depois
de um ecrã inteiro de scroll é, na prática, um botão que não existe.
- **A barra é FIXA no fundo do ecrã** enquanto a aba de uma caixa está aberta, e
  **só no modo edição** (no site publicado o endpoint não existe, e uma barra que
  conta cópias e não regista nada é pior do que barra nenhuma — a mesma razão dos
  botões). Traz *«Montar <caixa>: N de M cópias marcadas»*, a barra de progresso,
  o botão de registar e os atalhos **marcar tudo** / **limpar**. Motor em
  `deckboxes.barraHTML`/`renderBarra`; config em `colecao_config.json → montar`.
- **Marcar a ÚLTIMA cópia regista a caixa sozinha** (`montar.auto_registar`,
  omissão `true`), com um aviso de `montar.anular_segundos` (6) e o **anular** ao
  lado. Só quando ele ACABA de marcar: abrir a aba com tudo já marcado de ontem
  não escreve nada, e o *marcar tudo* também não — é um atalho para depois
  desmarcar duas ou três, não uma afirmação sobre a estante.
- **O «anular» repõe a `copy_allocation` e o estado exactamente como estavam**
  (`webapp.anular_registo` + `loadout.restaurar_alocacao`, sobre uma fotografia
  em memória, uma por caixa). **Sem backup, de propósito**: não apaga nada, é o
  inverso de uma escrita de há segundos. Quem apaga o que ele confirmou à mão é
  o **Desmontar**, e é por isso que esse tem backup e uma linha no
  `data/desmontar.log`. Os *vistos* das checkboxes voltam com ele — desfazer o
  registo e deixá-lo com a grelha limpa era pedir-lhe que marcasse 58 cartas
  outra vez.
- **REGISTO PARCIAL** (`loadout.registar_marcadas`, act `registar`): com algumas
  marcadas o botão diz *«Registar as N marcadas»* e grava **só essas** — as
  outras continuam em *"tirar da colecção"* — e a caixa **sobe a `permanente`,
  nunca a `montada`**, com o crachá *«N de M na caixa»*. Uma caixa monta-se aos
  poucos; até aqui só havia tudo-ou-nada, e ele ou dizia que estava montada (a
  mentir sobre as outras 40 cartas) ou no dia seguinte procurava as dez outra vez.
- **Quem decide que está completa é a BASE, não o browser.** `falta` sai de
  `movimentos_de_entrada` menos o que ele marcou; os `feitos` vivem no aparelho e
  podem ser de uma alocação de ontem. E o **`registo` sobe, nunca desce**: uma
  caixa que já se diz montada não usa o `montado` (esse **alterna** — alterná-lo
  aqui desmontava-a), usa o `registar`.
- **O que é de OUTRA caixa não conta para o M.** As cópias do bloco «destinadas a
  outra caixa» continuam a marcar-se e a registar-se, mas esperá-las era impedir
  esta caixa de fechar por causa de cartas que são de outra. Pela mesma razão as
  básicas **a granel** ficam fora: não têm cópia registada, não têm nada para
  marcar. O M é `plano_montar["marcar_q"]` = main + sideboard + básicas da base.
- **O id de um "visto" está num sítio só** (`deckboxes.vistoId`; era escrito à
  mão em três). A grelha desenha-o, a barra conta por ele e o registo manda os
  `copy_id` que ele traz — bastava mudar uma barra vertical num dos três para a
  barra dizer *"0 de 58"* com 58 cartas por baixo, sem um único erro. É o padrão
  do `event_tier` do lado do browser, e tem teste dos dois lados
  (`test_montar_barra.py`, que semeia os ids no `localStorage` do harness de node
  e lê o «N de M» que a barra desenhou).
- **Medido na base de 2026-09-08:** a alocação **não mexe** — 8 426,34 € para
  fechar, 232 a comprar, 70 a ir buscar, 345 a arrumar, venda 230c/1 315,68 € +
  40 RL/3 221,01 €, iguais antes e depois. O que a barra passa a dizer, por
  caixa: Cloud (DC) **75**, Cloud cEDH **60**, UW Replenish **59**, Modern — UW
  Oswald **49**, Oath of Druids **36**, Elves/Survival **22**, Enchantress
  **17**, Ill-Gotten Gains **17**, Pioneer — Greasefang **10**. (Estes números
  são os DESSE dia: subiram todos com a correcção das linhas incompletas — a
  lista nova está em *"as cópias de uma linha incompleta também se tiram da
  gaveta"*.) Sem barra: o
  Stiflenought, o Blue Farm e o Pauper (já não há nada por marcar neles — os
  dois últimos foram registados por ele na mesma tarde, no modo edição) e o
  Standard e o Legacy (ainda sem deck escolhido).

**OS TERRENOS BÁSICOS TÊM BLOCO PRÓPRIO (André, 2026-09-08, à letra).** *"Faltou
marcares, para completar o deck, os terrenos básicos necessários!"* e, na mesma
tarde, *"todas as minhas lands básicas são de Unhinged, em inglês, foil ou não
foil."* Até aqui uma básica entrava na alocação com `got == need` e `lotes == []`:
contava como tida e **não aparecia em lado nenhum** — o Stiflenought montava-se,
no painel Montar, sem uma única das suas 17 Island. É o padrão do `event_tier`
outra vez: nenhum passo dá erro, e a folha que ele leva para a estante está a
menos 17 cartas. Motor em `loadout._aloca_basica`/`_basicas_do_slot`/
`plano_basicas`, config em `colecao_config.json → basicas`.
- **As básicas são ISENTAS das regras de material** (`basicas.isentas_de_regras`,
  default `true`): a pilha dele é toda Unhinged EN, e trancar o Premodern ao PT
  mandava comprar 17 Island que estão ali ao lado. Nas caixas de foil a foil vai
  à frente (`_ordem_basica`), mas é **preferência e não requisito** — uma Island
  non-foil fecha o slot na mesma. O que NÃO é material continua a valer: cópia
  livre, não reservada a outro deck, e nunca uma que esteja sleevada noutra caixa.
- **As cópias registadas alocam-se como qualquer carta**: têm `lotes`, dizem de
  que gaveta sair e entram na arrumação (na base de 2026-09-08 são 12 Plains ODY
  e 23 Snow-Covered Plains MH1 foil — as únicas básicas na `copies`). O que a
  colecção não tem sai como *"N Island (Unhinged) — das tuas básicas"*, sem
  `copy_id` e sem nada para marcar.
- **Nunca se compram básicas**, excepto as que a pilha não cobre — as
  Snow-Covered, que não existem em Unhinged (`basicas.compram_se_faltarem` +
  `comprar_se_material_especial`). Essas vão para a aba Comprar num **bloco
  próprio**, marcado *«confirma se já tens»*: ele pode tê-las e não as ter
  registado, e uma linha a confirmar é mais barata do que um deck que não se monta
  à hora de sair.
- **O bloco vive numa chave própria (`s["basicas"]`) e nunca no `missing`**, e o
  `basicas_comprar_total`/`basicas_custo_total` ficam **fora** do
  `comprar_total`/`custo_total`. As básicas não contam para a percentagem nem para
  as compras — a regra é dele e não mudou — e somá-las fazia o *"fechar tudo por
  X €"* mudar por causa de cartas que ele já pode ter em casa, que é exactamente
  o número por que ele decide. `requisito_basicas(s)` é só o ACABAMENTO: dizer
  *"PT · ≤SCG"* numa linha de Island era pedir-lhe o que a alocação não exige.
- **No texto copiado o bloco vai COMENTADO** (`// Basicas`, `// 17 Island (na
  coleccao)`): o Cardmarket ignora as linhas com `//`, e mandá-las como linhas a
  sério era comprar 17 Island que estão em casa. Só o que é mesmo compra vai em
  linha normal.
- **Efeito medido na base de 2026-09-08:** a alocação **não mexe** — 8 426,34 €
  para fechar, 232 a comprar, 70 a ir buscar, venda 118c/1 621,76 € + 19 RL/
  3 442,20 €, iguais antes e depois. O único número que muda é a arrumação:
  **535 → 570** (+35), que são as básicas registadas a passarem a ter caixa. E
  **zero básicas a comprar**: ele tem 29 Snow-Covered Plains foil para as 23 que o
  Duel Commander pede.
- **O bloco vem DEPOIS do sideboard**, e as básicas não se partem por board: uma
  básica é uma pilha, e *"12 Island no main + 2 no side"* é a mesma ida à gaveta.

**O SIDEBOARD FICA SEPARADO DENTRO DA CAIXA (André, 2026-09-08, à letra:
*"Preciso também de saber o que é sideboard nos decks, para ficar separado dentro
da mesma caixa."*)** Uma caixa é um deck e um deck são duas pilhas — 60 (ou 100)
e 15. Quem parte é `loadout.blocos_de_board(movs, totais)`, num sítio só: o
painel *Montar*, a aba *Arrumar* (dos dois lados, gaveta e caixa) e o
`python -m mtgvault.cli arrumar` mostram os mesmos dois blocos, com o «N de M» de
cada um (o M é `loadout.totais_por_board`, a MESMA lista por que a percentagem da
caixa é calculada). A página não volta a decidir o que é sideboard em JavaScript,
pela mesma razão que não decide o que é foil (ver `e_foil`).
- **A carta que joga nos dois vem em DUAS linhas.** São duas cópias físicas em
  duas pilhas; uma linha só (`2×`) não dizia qual ia para onde, que é
  exactamente a pergunta. O `board` vem da linha da alocação (`movimentos_de_
  entrada` passou a levá-lo), não se recalcula.
- **O texto copiado da wantlist leva `// Sideboard`** entre os dois blocos — o
  Cardmarket ignora a linha de comentário sem dar erro. Só na wantlist DA CAIXA:
  a aba *Comprar* junta compras de várias caixas e aí a linha não tem bloco.
- Um movimento **sem** bloco (o que SAI de uma caixa: vem do lote, não da lista)
  fica num bloco próprio no fim. Chamar-lhe "main" era inventar uma resposta.

**«DESMONTAR»: o inverso do «sleevado e na caixa» (2026-09-08).** Botão por caixa,
só no modo edição: esvazia a `copy_allocation` daquela caixa, **com backup da
base** (`backups/vault-<data>-desmontar.db`, VACUUM INTO) e **uma linha em
`data/desmontar.log`** escrita ANTES de a base mexer — o que a caixa tinha lá
dentro é a única coisa que se perde. Motor em `loadout.desmontar_caixa`; o
*"tirar da caixa"* de uma caixa montada passa pelo mesmo motor (dois caminhos
para o mesmo gesto era o que a escala de estados da v6 veio evitar).
- **Aparece também numa caixa que NÃO se diz montada mas tem cartas registadas lá
  dentro** (`slot["arrumada"]`, de `caixas_arrumadas`). Era o caso das quatro
  caixas de 2026-09-08 (Blue Farm, Cloud cEDH, Cloud DC, Pauper): tinham alocação
  herdada da migração e as cartas estavam na `Colecção`. Sem o botão, isso
  fez-se em SQL à mão — sem backup e sem rasto.
- **Só desce de `montada` para `permanente`** (`webapp.despromover`). Uma
  candidata fica candidata: ele carregou para arrumar cartas, não para escolher
  prioridades.

E uma aba **Plano** (`loadout.ordem_de_montagem`, a mesma no CLI): por onde
começar — permanentes por prioridade, depois as candidatas mais perto de fechar —
com *"tirar N · comprar N (X €) · estado"*, e por baixo a **venda**, que só entra
depois de as caixas estarem servidas (uma cópia que serve uma caixa nunca aparece
na venda: vai para `guardar`).

**«DECKS MONTADOS» E «DECKS PARA MONTAR»: dois botões (André, 2026-09-08, à
letra).** *"No mtgvault, quero decks montados num botão específico, e um botão a
dizer «decks para montar», para poder separar as coisas."* São duas perguntas
diferentes e ele está à frente da estante quando faz cada uma: num caso já tem a
caixa na mão (o que lá está, e desmontá-la); no outro ainda a vai montar (o que
tirar da colecção, o que comprar). A aba *Todas* junta-as por prioridade de
alocação, que é a resposta a **outra** pergunta.
- **A linha que separa é o `estado`**: `montada`/`congelada` de um lado, tudo o
  resto do outro (`c.montado` no payload). Cada caixa está numa vista **e só
  numa**, e o cabeçalho diz *«N montados · M para montar»* — os dois números
  vêm do Python (`resumo.montados`/`por_montar`) e **somam sempre o total de
  caixas**. Uma caixa que caísse fora das duas desaparecia da página sem um
  único erro, que é o padrão do `event_tier` do lado do browser.
- **O cartão é o MESMO da vista Todas** (`caixaHTML(c, true)`): a caixa não pode
  dizer 61 % num sítio e outra coisa no do lado. O que muda é a barra por baixo
  — *«montada em <data>»* + **Desmontar** (modo edição) de um lado, **Montar**
  (que abre o painel Montar da caixa) do outro. Os botões ficam **fora** do
  `<button class="mini">`: um botão dentro de outro não é HTML válido e o clique
  de dentro disparava também a navegação de fora.
- **A data sai da `copy_allocation`** (`loadout.datas_de_arrumacao`, o
  `MAX(placed_at)` — quem grava substitui as linhas da caixa inteira, por isso a
  data que se pode afirmar é a da última vez que ele disse o que lá está). **Uma
  caixa que se diz montada e de que o vault não sabe o conteúdo não ganha data
  nenhuma**: diz que falta confirmar. É o Stiflenought, hoje o único montado —
  e dar-lhe o dia de hoje era assinar por ele uma confirmação que ele nunca fez.
- **A ordem da vista de montar é a do Plano** (`ordem_de_montagem`): permanentes
  primeiro, depois as candidatas pela percentagem. Reordená-la aqui dava duas
  respostas a *"por onde começo?"*. As caixas **sem deck escolhido** não estão no
  `montagem` (não há o que montar até ele escolher): vêm no fim, no grupo
  **Por escolher**. Pela mesma razão o subtítulo da aba *Plano* deixou de trazer
  contagem — *"N por montar"* ali e *"M por montar"* no botão do lado eram as
  mesmas palavras com dois números.
- **As abas individuais de cada deck mantêm-se**, agrupadas: montadas primeiro,
  com o **ponto verde** (`pin done`, com anel para não se confundir com o verde
  de *"90 % ou mais"*), e um separador entre os dois grupos. Antes vinham pela
  ordem da alocação e a caixa que está na estante aparecia no meio das que ainda
  não existem.
- **Nada mudou no motor**: medido na base de 2026-09-08, fechar tudo 8 426,34 €,
  232 a comprar, 70 a ir buscar, 570 a arrumar — iguais antes e depois.

**«VENDIDA»: a cópia sai mesmo (`loadout.registar_venda`, 2026-09-08).** Botão
por linha, só no modo edição. Duas decisões que valem estar escritas: (1) a cópia
**sai da base** (a quantidade desce, a linha desaparece a zero) em vez de ficar
marcada — o vault conta cópias físicas, e deixá-la lá com uma bandeira era pedir
a toda a consulta futura que se lembrasse da bandeira; (2) o registo fica em
**`data/vendas.csv`** (data, carta, edição, língua, acabamento, quantidade, preço
de referência, onde estava, motivo), fora do Git, porque a `vault.db` é
descarregada e republicada inteira a cada corrida. Escreve-se o CSV **antes** de
mexer na base: sobrar uma linha a mais é visível, perder a venda não é. A linha
identifica-se por `loadout.chave_venda` — a mesma chave por que o `_fecha` junta
os lotes — e o servidor **recalcula** o relatório antes de tirar nada, para uma
página aberta há duas horas não mandar vender uma cópia que já está numa caixa.

**O TELEMÓVEL E O TOKEN (2026-09-08).** *"Ele vai estar à frente da estante com o
telemóvel."* O `webapp.py` ouve em `MTGVAULT_BIND` (por omissão `127.0.0.1`; a
tarefa `mtgvault-serve` põe `0.0.0.0`) e a página mostra um **QR** com o link já
com o token — o QR é desenhado por `mtgvault/qr.py`, em Python puro (modo byte,
nível M, versões 1–10), porque uma dependência nova para um quadrado preto e
branco paga-se todos os dias em instalações. **Ler é livre; escrever exige o
token** (`data/webapp.token`, gerado uma vez, fora do Git): sem ele, `403`. E a
página só leva o token dentro dela quando o pedido que a foi buscar já o trazia —
senão bastava abri-la de qualquer telemóvel da rede para o descobrir. **O
`/qr.svg` exige-o pela mesma razão**: um QR é um URL legível, e servi-lo a quem
não o tem era dar o token pela porta do lado (a página pede-o com `?t=`).
Pedidos de `127.0.0.1` são de confiança sem token (quem está no PC já tem os
ficheiros).
O `test_qr.py` verifica o QR de três maneiras (lê-se a si próprio, é igual ao da
biblioteca de referência nas oito máscaras, e a estrutura está lá): um QR "quase
certo" não dá erro, dá um quadrado que o telemóvel não lê e não diz porquê.
**A firewall do Windows pode estar a tapar o 8771** — uma vez, em consola de
Administrador: `netsh advfirewall firewall add rule name="mtgvault 8771" dir=in
action=allow protocol=TCP localport=8771 profile=private` (só rede privada; o
comando também é impresso no arranque do `webapp.py`).

**Loadout: os decks montados em simultâneo (`mtgvault/loadout.py`, 2026-09-07).**
Palavras do André: *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."* A lista de caixas está em
`colecao_config.json → caixas` (v6; era `loadout`) — slot, formato, fonte da
lista, balde, estado, prioridade, regras de material. Gera `deckboxes.html` e os comandos
`loadout` / `loadout <deck>` / `vender`.

A diferença para tudo o resto do vault: aqui a coleção é **repartida**. Uma
cópia física entra numa caixa e **só numa**, a alocação é global e por ordem de
`prioridade`, e é daí que saem quatro coisas que uma cobertura por deck não dá —
**noutra caixa** (a carta existe e serve, mas está alocada a outra caixa),
**cartas partilhadas** (2+ caixas querem a carta, não chegam para todas — era o
"conflito"), **substituto** (tem a carta mas não serve àquela caixa) e
**venda**.

**Decks PERMANENTES e candidatos (André, 2026-09-07, à letra).** *"Os decks que
eu pedi para serem permanentes são a minha prioridade máxima!"* e *"os decks que
eu estiver quase a concluir, tenho que ter uma opção que os marque como
permanentes para começarem a receber alocação de cartas."*
- `colecao_config.json → loadout[].permanente` (`true`/`false`). **Sem a chave, o
  slot é permanente** — era o que as catorze caixas eram antes de a distinção
  existir, e um default a `false` esvaziava a alocação de quem não a escrevesse.
- `permanente` é a **primeira chave da ordem de alocação**, à frente do grupo de
  formato: um permanente de SPML escolhe antes de um candidato de Premodern.
  Dentro de cada metade a ordem é a de sempre (grupo > deck vigiado > prioridade).
- Um **candidato** não deixa de ver as cartas: fica com o que sobrar e, para o
  resto, diz *"em &lt;caixa&gt;"* em vez de mandar comprar.
- Hoje só os três slots `por_confirmar` (Standard, Pioneer, Legacy) são
  candidatos — uma caixa sem deck escolhido não pode ser permanente.
- Marca-se e desmarca-se no **modo edição** (`python webapp.py`, porto 8771).

**ARRUMAÇÃO FÍSICA: onde a carta ESTÁ vs. onde DEVE estar (2026-09-07).**
*"Quero que me ajudem a ser mais organizado com as cartas."* O loadout continua a
recalcular todos os dias onde cada carta deve estar; a `copy_allocation` diz onde
ela está. **A diferença entre as duas é a lista de arrumação**
(`loadout.plano_arrumacao`), com dois sentidos que contam os dois: **entra** (a
alocação deu-a a uma caixa e ela ainda não lá está) e **sai** (está na caixa e a
alocação já não a usa lá; volta à gaveta). Agrupa-se por **origem** (a gaveta que
se abre) e por **destino** (a caixa que se monta) — são dois gestos diferentes.
- Na página é a aba **Arrumar**, com checkboxes no browser e um CSV
  `moves-<data>.csv`; no CLI é `python -m mtgvault.cli arrumar [--csv]
  [--confirmar]`.
- **"Já arrumei tudo" grava** (`loadout.guardar_arrumacao`, com backup no modo
  edição). É idempotente e substitui a tabela inteira: uma linha órfã de uma
  caixa que já não existe mentia para sempre.
- **Um lote sai do `lots()` PARTIDO por sítio** (`caixa` + `key`): um lote de 4
  com 3 na caixa e 1 na gaveta vale por metade, não por inteiro. Se mexeres no
  `lots()`, é aqui que a armadilha está.
- **Uma cópia já arrumada na caixa deste deck escapa às regras de material** — é
  a versão nova da excepção do balde, e é o que impede que uma regra nova
  desmonte no papel um deck que está na estante. A antiga (pelo balde) fica, para
  o mesmo código estar certo antes e depois da migração.
- **`_ordem` gasta primeiro a cópia que já está nesta caixa.** Sem isso a corrida
  do dia seguinte trocava duas cópias equivalentes de caixa e mandava-o desmontar
  dois decks para não mudar nada.

**Posse: quem conta o quê (2026-09-07; desde a v6 há uma página só).** Até esta data cada página
contava a posse à sua maneira e discordavam em silêncio, que é o mesmo padrão do
`event_tier` e do filtro de listas. O erro que obrigou a mudar, à letra: *"Meti 4
fotos, estavam lá 4 Utrom Monitor, mas no deck Pauper não aparecem como se eu
tivesse a carta."* O `meusdecks._watched_decks` contava só as cópias do balde
ligado ao deck (`deck_collection` → `Pauper Affinity`) e as quatro Utrom Monitor
estão no `SPML`: existiam, serviam a caixa, e a página dizia que faltavam.
**Agora a alocação do loadout é a única fonte de "tenho / está noutra caixa /
falta" em todo o site.** A ponte são `loadout.slots_por_lista(res)` (indexa os
slots pelo `ref`, que é exactamente o nome do deck na tabela `decks` ou a
etiqueta do `watched`) e `loadout.linhas_por_carta(slot)`. Já a usam:
o `deckboxes`/`metagame`, `colecao_cor` (secção "Decks montados", com as
cartas que vêm de outro balde marcadas *"de &lt;balde&gt;"*) e `metagame`.
Consequências a saber:
- as percentagens do `meusdecks.html` e do `deckboxes.html` **passaram a bater
  certo** — antes o `meusdecks` dava mais alto porque cada deck contava a coleção
  inteira. Já não é "a pergunta a ser outra": é a mesma pergunta. **E, desde a v6
  (2026-09-08), é a mesma PÁGINA** — ver "Uma só noção de deck": duas páginas com
  a mesma resposta são duas oportunidades de divergirem;
- um deck que **não** seja caixa do loadout mantém a contagem antiga (a coleção
  inteira) — não se inventa uma alocação que não existe;
- **toda a vista nova que some faltas soma `comprar`**, nunca `missing` (é a
  regra de cima, e o `paginas.faltas_de` já a segue).

**Onde está a carta: 'noutra caixa' não é falta (André, 2026-09-07, à letra).**
*"Vamos fazer como no riftvault: indicas onde está a carta, para, se eu quiser ir
jogar, saber onde ir buscar e não ter que comprar múltiplos para todos. Caso eu
compre, depois indico (meto foto) e vais ajustando."*
- Quando uma caixa pede uma carta e a(s) cópia(s) que a SERVEM foram alocadas a
  outra caixa, a linha traz `noutra` = `{caixa: quantas}` e `noutra_q`, em vez de
  ser tratada como falta. Na página é o **terceiro estado** (moldura âmbar, o
  mesmo dos substitutos) com o texto *"em &lt;caixa&gt;"*, mais o bloco
  *"📦 ir buscar a outra caixa"*; no CLI é a secção `IR BUSCAR A OUTRA CAIXA`.
- **A wantlist e o custo de fechar EXCLUEM essas cartas.** A quantidade de compra
  é `comprar` (= `missing - noutra_q`), nunca `missing`, e `cost` é sobre
  `comprar`. Só é compra o que não existe em lado nenhum, ou o que existe mas não
  serve na língua/acabamento exigidos (esse continua a ser substituto e continua
  a comprar-se). Cada caixa mostra dois números: `comprar` e `noutra`; o relatório
  inteiro traz `comprar_total`/`noutra_total`. **Se acrescentares uma vista nova
  que some faltas, soma `comprar` — somar `missing` volta a pedir 8 Swords to
  Plowshares para tapar um buraco que não existe.**
- **Uma cópia que a caixa não VÊ nunca é "noutra caixa".** A regra 1b (Premodern
  x Caixa RL) e o `_porque_nao` continuam a ganhar: para essas, a carta é compra.
- **A ordem da alocação é o que torna isto correcto.** Um lote que serve o
  slot S e ainda está livre quando S corre é sempre gasto por S; logo, tudo o que
  falta a S e servia S foi levado por um slot que corre ANTES. Não é preciso
  uma segunda passagem — mas se mudares a ordem da alocação, isto deixa de valer.
  (Desde 2026-09-07 essa ordem é a de `regras_por_formato`, não a dos números do
  config — ver "As regras de material são por GRUPO DE FORMATO" abaixo.)
- **A venda não muda:** uma carta pedida por qualquer caixa já estava alocada, e
  o que está alocado nunca entra na venda. E as `retidos`/`guardar` continuam iguais.
- **Como se ajusta depois de comprar:** o André mete as fotos das cartas novas em
  `pendentes/` (repo `mtg-fotos-novas` / app do GitHub — ver `PROCESSAR_FOTOS.md`
  e `processar_fotos.py`), daí sai o CSV para a coleção, e a **alocação recalcula
  sozinha na corrida seguinte do `daily.py`** (passo `deckboxes`). Não há estado
  guardado: o "onde está a carta" é sempre recalculado da coleção do dia.

**ONDE A CARTA ESTÁ ≠ A QUEM ESTÁ DESTINADA (André, 2026-09-08, 14:30, à letra).**
*"De todas as cartas, só o Stiflenought está em deckbox; o resto ainda nada está
em deckbox — e ainda estás a assumir que há cartas que já estão nas deckboxes dos
decks."* Recorta a regra de cima, que ficou meio certa: o `noutra` responde
*"de que caixa é esta cópia"*, que é uma pergunta de ALOCAÇÃO, e a página lia-o
como *"onde é que ela está"*. Com a `copy_allocation` **vazia** — que era o
estado da base nesse dia — as **70** cópias do *"ir buscar a outra caixa"*
estavam todas na `Colecção`, na prateleira. É o padrão do `event_tier`: um número
certo a responder a outra pergunta, sem um único erro.
- **A prova de que a carta está numa caixa é a `copy_allocation`, e só ela.** O
  `noutra` de cada linha parte-se em três, e as três somam-no sempre:
  `noutra_montada` (há linha na `copy_allocation` daquela caixa para aquela
  cópia — *"em UW Replenish"*), `noutra_reservada` (a alocação prometeu-a por
  prioridade e ela continua na gaveta — *"na Colecção — destinada a UW Replenish
  (prioridade)"*, com `noutra_onde` a dizer que gaveta) e `noutra_futura` (a que
  já lá estava: ninguém a tem ainda, é uma compra partilhada de outra caixa).
- **A frase escreve-se num sítio só: `loadout.onde_esta(linha, so=None)`.** Cada
  página compunha o seu *"em X"* a partir do `noutra`, e por isso todas mentiam
  ao mesmo tempo. O `deckboxes` recebe a frase pronta no payload e o
  `metagame`/CLI chamam-na — a página não volta a recompor isto em JavaScript,
  pela mesma razão que não decide o que é foil (ver `e_foil`).
- **Um bloco passou a três**, na página e no CLI (`buscar_montada` /
  `buscar_reservada` / `buscar_futura`, e os totais `noutra_montada` /
  `noutra_reservada` / `noutra_futura` por caixa e `*_total` no relatório). Só o
  primeiro é uma ida a outra caixa; o segundo tira-se da mesma gaveta que tudo o
  resto. Um bloco só mandava-o abrir caixas que não existem na estante.
- **MONTAR FORA DE ORDEM.** Se ele abre a Enchantress antes do UW Replenish, as
  cartas que o Replenish há-de levar estão ali ao lado. O painel *Montar* mostra-
  as num bloco próprio — **⚠️ destinadas a outra caixa**, `loadout.
  movimentos_reservados` → `plano_montar()["de_outra"]` — e **por marcar**: tirá-
  las é uma decisão dele (a outra caixa passa a vir buscá-las aqui), não uma
  consequência de abrir a aba. Só o que ele marca é que vai no *"sleevado e na
  caixa"* (`webapp.marcar_na_caixa(..., de_outra=[copy_id])`, que só aceita
  `copy_id` que o painel oferecia). A partir daí **a `copy_allocation` manda
  sobre a prioridade**: a corrida seguinte vê a cópia dentro desta caixa
  (`_noutra_caixa`) e a outra passa a dizer *"em Enchantress"* — que aí é verdade.
- **A arrumação nunca teve este defeito e não pode ganhá-lo:** o `de` de um
  movimento é `lot["local"]`, que já é físico. O `de_outra` fica FORA do
  `plano_arrumacao` e do `copias` do painel — são duas listas para dois gestos
  diferentes, e somá-las contava a mesma cópia duas vezes.
- **Efeito medido na base de 2026-09-08 (`copy_allocation` vazia):** a alocação
  **não mexe** — 8 426,34 € para fechar, 232 a comprar, 70 destinadas a outra
  caixa, 570 a arrumar, venda 243c/1 621,76 € + 41 RL/3 442,20 €, iguais antes e
  depois. O que muda é a leitura: das 70, **0 estão numa caixa**, 56 estão na
  gaveta destinadas a uma caixa por montar e 14 ainda ninguém as comprou. As 56
  aparecem agora no painel *Montar* da caixa que as quer (Enchantress 20,
  IGG 16, Elves 12, Oath 4, Modern 3, UW Replenish 1).

**«VOU MONTAR ESTE»: escolher o deck de uma caixa a partir do top-N (André,
2026-09-07, 19:00).** Ele vê os três que está mais perto de concluir e marca
qual vai montar. O botão está no `metagame.html` **e** na aba da caixa do
`deckboxes.html` (é onde ele está quando decide), só em **modo edição**
(`python webapp.py`, porto 8771 — que passou a servir as duas páginas geradas,
ver `PAGINAS_EDITAVEIS`).
- Escolher escreve `colecao_config.json → listas_escolhidas[<slot>]` — nome,
  subtítulo, arquétipo, nº de listas, **`escolhido_em`** e a lista de cartas — e
  põe o slot em `fonte: "escolhido"`, `ref: "<slot>"`, `permanente: true`. A
  lista fica **congelada com a data**: se o consenso mudar amanhã, a caixa (e a
  lista de compras dela) não muda debaixo dos pés.
- **Há desmarcar.** O que lá estava fica em `loadout[].\_antes` (a chave começa
  por `_`, por isso o motor não a vê — `config_slots`), e o *"já não vou montar
  este"* repõe-o. É o que garante que, no Pioneer, **sem ele carregar fica o
  Greasefang**.
- A lista vive numa chave própria e não dentro do slot para o `loadout`
  continuar a ser catorze linhas legíveis.
- **Nomes de arquétipo.** Os pares de cartas (*"Doc Aurlock / Appa"*) eram
  fracos. A fonte não nos dá o nome do arquétipo (o mtgtop8 exporta `.dec` de
  cartas, não rótulos, e não se inventa um que não veio de lado nenhum), por
  isso `meta_coverage._name_for` passou a devolver o **nome próprio** (a lista
  `KNOWN`) ou, na falta dele, **cores + carta-chave**: *"Bant Doc Aurlock"*,
  *"Jeskai Thor"*. O par continua à vista como **subtítulo**
  (`_distinctive_name`). Cores = as do núcleo, cada uma com pelo menos duas
  cartas (`MIN_CARTAS_POR_COR`) — um splash de uma carta punha um Izzet a
  chamar-se Jeskai.

**O PREMODERN VOLTOU A PARTILHAR, COM TECTO DE PLAYSET (André, 2026-09-08, à
letra).** *"No Premodern, afinal só vou ter até playset de cada carta. E
ordenamos os decks por prioridade; os que vêm depois na prioridade indicam onde
estão as cartas em falta. Para já a prioridade vem por ordem de % completo."*
Recorta a regra das CAIXAS DEDICADAS abaixo **só para o Premodern** — o cEDH e o
Pauper continuam dedicados. São três chaves no grupo `premodern` do
`regras_por_formato`, e as três andam juntas: sem o tecto, a partilha ainda
comprava 4 quando 2 já estão em casa e nenhuma caixa lhes chega; sem a partilha,
seis caixas dedicadas com playset de 4 são 24 cópias, que é o que ele recusou.
- **`dedicado: false`** — as seis caixas de Premodern voltam a emprestar e a ir
  buscar (*"em &lt;caixa&gt;"* em vez de comprar), e a partilha de compras volta
  a ser o **máximo** de uma caixa e não a soma.
- **`playset_maximo: 4`** — por cima da partilha, um tecto:
  `comprar = max(0, min(4, o que a caixa que mais precisa pede) − as que o grupo
  já vê)`. Quem faz a conta é `loadout.partilhar_compras`, com o `_ja_visto` a
  ler a resposta que a ALOCAÇÃO já deu (`got + noutra_q`) em vez de recontar a
  colecção — uma segunda contagem era uma segunda opinião. **As básicas ficam de
  fora** (nunca entram na compra). O que o tecto corta **não desaparece dentro da
  subtracção**: fica em `playset_bloqueado` na linha, sai em `res["limites"]`, e
  a página/CLI dizem *"limite de playset: falta 1 que não se compra"*. Uma falta
  que ele decidiu não tapar não é o mesmo que uma falta tapada.
- **O tecto é por GRUPO DE PARTILHA, não por pool de material.** *"O Premodern
  nunca chega a ter mais do que 4"* só é verdade porque as caixas trocam a carta
  entre si; uma caixa `dedicado`/`compras_dedicadas` disse o contrário e é o seu
  próprio grupo, com o seu próprio tecto.
- **`prioridade_por: "pct"`** — a ordem DENTRO do grupo deixa de ser o
  `prioridade` do config e passa a ser a percentagem de cada caixa, medida na
  **colecção inteira e ANTES de alocar** (`loadout.pct_na_coleccao`, escrita em
  `pct_coleccao`); empate pelo nome. Com a percentagem de DEPOIS a ordem
  oscilava: alocar mudava o pct, o pct mudava a ordem e a ordem mudava a
  alocação. A página põe o crachá **«#N por % completo»** e o **subir/descer do
  modo edição fica desactivado** e diz porquê (`webapp.mover`) — escrever o
  número na mesma era mudar o ficheiro sem mudar a ordem.
- **Consequência a saber:** `congelada` exige ser dedicada, por isso **nenhuma
  caixa de Premodern congela**. O que as protege continua a valer: uma cópia
  dentro de uma caixa não é realocada a outra (`_noutra_caixa`), o `_ordem` gasta
  primeiro a que já lá está, e o que está alocado nunca entra na venda.
- **Efeito medido na base de 2026-09-08:** fechar tudo passou de **9 293,41 €**
  para **7 905,72 €** (289 → **221** a comprar, 4 → **71** a ir buscar). A venda
  **não mexeu** (91c/701,62 € + 39 RL/5 696,37 €), nem a arrumação (302/36). Do
  desconto, 1 386,59 € vêm da partilha e 1,10 € do tecto (hoje só corta uma cópia:
  o 5.º Swords to Plowshares do Enchantress, que joga 4 no main e 1 no side). A
  nova ordem é Stiflenought 100% · UW Replenish 95% · Oath of Druids 73% ·
  Enchantress 67% · Ill-Gotten Gains 65% · Elves / Survival 61%.

**PREMODERN: O QUE MONTAR A SEGUIR, E VENDER O RESTO (André,
2026-09-08, à letra; a cobertura passou de *"o que sobra"* a *"como se fosse o
principal"* no mesmo dia — ver o segundo ponto).** *"O que não estiver a ser usado em Premodern e se encaixe
na regra do Premodern deve ser sugerido para venda. Antes disso, procura
decklists do formato; se o deck for top-10 de representação ou top-5 decks combo
do formato, sugere a lista para montar o deck caso eu tenha pelo menos 50 % das
cartas (sem contar com as básicas para a %); se não, envia para vender."*
Motor em `mtgvault/premodern.py`, config em `colecao_config.json → premodern`,
CLI `python -m mtgvault.cli premodern`.

- **A ordem das três regras é o que torna isto honesto**, e é a ordem por que
  correm dentro do `loadout.report`: alocar → calcular as sugestões → vender.
  Ao contrário, a lista de venda mandava vender exactamente o deck que a página
  do lado estava a sugerir montar.
- **A cobertura mede-se COMO SE O CANDIDATO FOSSE O PRINCIPAL (André, 2026-09-08,
  segunda ordem do dia, à letra):** *"Como as cartas em Premodern são
  partilhadas, tens que ver se a % desses decks aumentaria se eles fossem o
  principal; mantém a 50 % visto com esta regra de agora."* A primeira versão
  media só o que SOBRA (`foil_report(..., res=...)` → `pct_livre`) — certo
  enquanto as caixas de Premodern eram dedicadas, errado no dia em que voltaram a
  partilhar (`regras_por_formato.premodern.dedicado = false`). Com seis caixas a
  alocar primeiro **nenhum candidato chegava aos 50 %** (o melhor era o
  Mono-Preto The Rack com 41 %), e o que a percentagem media já não era *"quanto
  deste deck eu tenho"* mas *"quanto sobrou depois dos outros"*.
  Agora quem decide o limiar é `premodern.pct_principal`: as cópias PT (≤ Scourge)
  **livres** mais as que estão nas **outras caixas do grupo de Premodern**, que
  lhas emprestariam. As de caixas dedicadas de outros formatos (cEDH, Pauper) não
  contam — não emprestam, e montar com elas era desmontar um deck de outro
  formato. As páginas e o CLI mostram **as duas** (*"80 % como principal · 36 %
  com o que sobra"*), porque a diferença entre elas é quantas cartas vinham
  emprestadas. **Consequência medida na base de 2026-09-08: duas sugestões** —
  Dimir Psychatog (80 % / 36 %) e Landstill (68 % / 27 %); a alocação **não
  mexe** (7 905,72 €, 221 a comprar, 71 a ir buscar, 302 a arrumar) e as duas
  reservam 30 cópias / 70,95 € que saem da lista de venda.
  Nem uma percentagem nem a outra é uma contagem própria de posse: as duas saem
  das mesmas linhas do `foil_report` (`got` e a chave nova `onde`, que é o
  `noutra` **antes** de ser cortado pelo que falta — filtrá-lo depois do corte
  dava a soma a menos).
- **O top-10 e o top-5 combo são DUAS listas, não uma soma** (*"ou"*), e cada
  candidato diz por qual entrou. O combo decide-se — e o deck NOMEIA-se — por
  REGRA sobre a lista de consenso (`premodern.combo_arquetipos`, as mesmas
  chaves `all`/`any`/`none` do `archetype_rules.json`, o mesmo motor do
  `tagging`). A ORDEM das regras é a prioridade: o Full English Breakfast joga
  Survival of the Fittest e, escrito depois do Elves/Survival, chamava-se
  Elves/Survival. O critério de "combo" e a lista saíram do relatório
  `work/revisao/premodern-combo.md` (441 listas reais).
- **A regra serve também de nome**: o `meta_coverage.KNOWN` chamava *"Replenish"*
  à Enchantress (que joga 96 % de Replenish) **e** ao UW Replenish, porque bate na
  primeira carta que encontra. O `none` separa-os. **E é o que dá nomes ESTÁVEIS**:
  quem não bate em regra nenhuma fica com o rótulo do clustering, que muda de
  corrida para corrida (o *"Dimir Psychatog"* passou a *"Dimir Polluted Delta"* na
  corrida seguinte). Como é pelo nome que uma sugestão se reconhece como sendo já
  uma caixa (`premodern._caixa_de`), os arquétipos que são caixas TÊM de estar
  no `combo_arquetipos` — mesmo os que não são combo.
- **Uma sugestão aberta RESERVA as cartas dela** (`res["reservadas"]`, com o
  motivo *"reservada para X"*): não entram na venda. Reserva-se o **máximo** entre
  as sugestões e não a soma — são alternativas entre si, e o Premodern tem tecto
  de playset. O *"não quero este"* escreve `premodern.sugestoes_recusadas`
  (nome → data) e liberta-as no mesmo dia; guardá-lo no browser fazia a sugestão
  voltar amanhã e as cartas saírem outra vez da lista.
- **A venda nova tem MOTIVO PRÓPRIO**: `Premodern: não usada por nenhum deck`
  (`loadout.RAZAO_PREMODERN`), à parte do `excedente (mais de 4)`. São decisões
  diferentes — *"tens cópias a mais"* e *"não tens onde a jogar"* — e um total que
  as some não se pode usar. A Reserved List continua a sair pela `venda_rl`, para
  se confirmar uma a uma. **Nada sai da base sem o botão «vendida»** (v6).
- **Uma cópia que serve uma caixa de OUTRO formato no material que ela aceita
  nunca vai para a venda** (`loadout._serve_outra_caixa` → `guardar`, com o motivo
  *"serve o duel-commander (Cloud)"*). O caso é raro e existe: uma PT **foil** da
  era serve o Duel Commander, que é *"apenas foil"* e não exige língua. Na base de
  2026-09-08 não tira nenhuma da lista — as outras caixas querem EN.
- **Sem uma única caixa de Premodern a regra NÃO corre.** *"Não usada por nenhum
  deck"* não quer dizer nada quando não há deck nenhum, e a alternativa era vender
  a colecção de Premodern inteira por o config estar vazio.
- **Efeito medido na base de 2026-09-08:** a alocação **não mexe** (7 905,72 €
  para fechar, 221 a comprar, 71 a ir buscar, 302 a arrumar). A venda passa de
  91c/701,62 € + 39 RL/5 696,37 € para **253c/1 250,45 € + 101 RL/8 106,54 €**:
  são **+224 cópias e +2 959,00 €** pelo motivo novo (162 normais/548,83 € e
  62 RL/2 410,17 €). **O grosso do valor é Reserved List em PT** — Null Rod,
  Gilded Drake, Grim Monolith, Tolarian Academy — que nenhum deck de Premodern
  dele joga e que os outros formatos recusam por serem PT. É a regra 1 dele a
  morder; vale a pena olhar para essa lista antes de confirmar.
- **O `metagame.html` mudou de secção**: o Premodern deixou de mostrar só os dois
  alvos de consenso (`SECOES` passou de `alvos` a `premodern`) e passa a mostrar o
  ranking, com os botões. Os dois alvos continuam lá, marcados *"já é uma caixa
  tua"*. A `deckboxes.html` ganhou a aba **💡 Sugestões** e, na aba *Vender*, o
  bloco **Reservadas**.
- **«Vou montar este» numa sugestão CRIA a caixa** (`webapp.caixa_para_sugestao`),
  ao contrário do botão do top-N, onde a caixa já existe e está vazia. O nome da
  caixa é o do arquétipo e mais nada: é por ele que ela se reconhece como sendo
  aquela sugestão na corrida seguinte (`premodern._caixa_de`), e o *"Legacy —
  Doomsday"* do outro botão fazia a sugestão reaparecer ao lado da caixa que ela
  própria criou. Medido: escolher o Dimir Psychatog (a 36 %) abre a caixa, dá-lhe
  a posição **#3 por % completo** e 51 % de alocação. **Desde 2026-09-08 quem a
  faz reconhecer-se é o `id` estável** (ver a secção a seguir): o nome mudava.

**A IDENTIDADE DE UM ARQUÉTIPO É O NÚCLEO, NÃO O RÓTULO (`mtgvault/arquetipos.py`,
2026-09-08).** Medido na base do próprio dia: o *"Dimir Psychatog"* do ranking
passou a **"Dimir Polluted Delta"** e o *"Mono-Preto Graveborn Muse"* a
*"Mono-Preto Withered Wretch"*. Não é falha do clustering — o nome sai das cartas
mais distintivas do núcleo e o núcleo mexe todos os dias, porque a janela de 30
dias entra e sai listas. Enquanto o nome era só um rótulo isso era feio; deixou
de o ser no dia em que três decisões dele passaram a reconhecer-se **pelo nome**:
a sugestão que já é uma caixa (`premodern._caixa_de`), a **recusa**
(`sugestoes_recusadas`) e a **escolha** (`listas_escolhidas`). Com o rótulo a
mudar, a recusa de ontem deixava de bater, a sugestão voltava sozinha e as cartas
dela saíam outra vez da lista de venda — sem ninguém carregar em nada e **sem um
único erro**. É o padrão do `event_tier`.
- **O `id` sai do CONTEÚDO**: as 8–12 cartas mais distintivas do consenso, sem
  básicas, ordenadas por nome, com um hash curto do (formato + núcleo). O formato
  entra no hash porque um Doomsday de Legacy e um de Premodern são decisões
  diferentes.
- **E herda-se**, que é a metade que resolve o caso real: com **≥ 70 %** de
  cartas em comum com um arquétipo que o registo já conhece, é o mesmo arquétipo
  e fica com o `id` **e com o nome** que já tinha. O hash sozinho só resolveria o
  caso em que nada muda — que é precisamente o caso que não dá problema. Dois
  clusters da mesma corrida não podem herdar a mesma entrada.
- **O núcleo tem um MÍNIMO, e ele conta.** O `NUCLEO_MIN = 8` esteve escrito e
  documentado sem nunca ser aplicado, e a primeira corrida a sério mostrou o
  preço: entradas de **duas** e três cartas (um *"Mono-Azul Frogmite"* de 2),
  porque a distintividade do `card_roles` às vezes só devolve um punhado. Um `id`
  de duas cartas é frágil, e dois baralhos que partilhem essas duas passavam a ser
  o **mesmo** arquétipo — a recusa de um apagava a sugestão do outro. E como um
  núcleo de 3 nunca chega aos 70 % do de 12 do mesmo deck, o mesmo baralho ficava
  com duas entradas de nome igual. O `nucleo()` completa pelo `resto` (a lista de
  consenso) **só abaixo do mínimo**: o `resto` é um remendo, não uma fonte — quem
  já tem o mínimo não se enche, senão o núcleo passava a depender da lista
  inteira, que muda todos os dias.
- **O registo é `data/arquetipos.json`** (id → nome, núcleo, primeira/última vez
  visto), gravado uma vez por relatório, **só se mudou** e **atomicamente**
  (temporário + `os.replace`, como o `configio.escrever`). A atomicidade não é
  higiene: o `daily` e o `webapp.py` — que fica de pé o dia todo, mantido pela
  tarefa `mtgvault-serve` — escrevem os dois este ficheiro, e com um `write_text`
  cru **24 arquétipos passaram a 7** numa tarde. O ficheiro fica truncado entre o
  `open` e o `write`, quem o apanhe assim lê JSON inválido, o `carregar` responde
  com um registo vazio (de propósito: um `daily` não pode parar por causa disto) e
  a gravação seguinte escreve por cima. Um ficheiro mesmo corrompido guarda-se ao
  lado (`arquetipos-mau-<data>.json`) antes de se começar do zero. **Se mexeres no
  `webapp.py`, o que está de pé tem de ser reiniciado** — o antigo continua a
  escrever pelo modo antigo. Vai ao `git add` do
  `daily.yml` **e ao `EXTRA_COMMIT` da tarefa `ai-pc/tasks/mtgvault-daily`** — um
  registo que só existisse num dos dois punha as duas corridas a discordar sobre
  o nome, que é o defeito que isto vem corrigir. O `test_paginas.py` tranca-o. A
  poda esquece o que não aparece há um ano, **menos** o que o config refere.
- **O `id` vai no BOTÃO** (`data-id`), nas duas páginas onde ele decide. Se
  ficasse só no Python, o servidor continuava a receber o nome e a guardar a
  recusa por nome: motor certo, vault errado na mesma.
- **`sugestoes_recusadas` passou a `{<id>: {nome, em}}`.** A forma antiga
  (`{<nome>: <data>}`) continua a ler-se e a bater pelo nome, para uma recusa
  escrita antes disto não se perder; a `python -m mtgvault.cli migrar-arquetipos`
  (com `--dry-run`) passa-a para a nova, e o que hoje não tem listas **fica como
  está** — um arquétipo volta ao metagame daqui a um mês e apagar-lhe a recusa
  era decidir por ele. No config dele as duas chaves estavam vazias: não havia
  nada a migrar.
- **NOMES CONHECIDOS POR REGRA, e nomear não é ser combo.** Oito clássicos do
  formato ganharam regra (Psychatog, Landstill = Standstill + Mishra's Factory,
  The Rack, Exalted Angel, Graveborn Muse, Goblins, Pyrostatic Pillar, Sligh =
  Fireblast) com **`"combo": false`** — sem essa chave o Landstill passava a
  disputar o top-5 de combo com o Stiflenought. E **`"cor": true`** põe as cores
  do núcleo à frente (*"Orzhov Exalted Angel"*), só para os nomes que não
  implicam a cor; calcula-se em vez de se escrever, senão chamava-se Orzhov a um
  Exalted Angel mono-branco. Estão **no fim** da lista: a primeira que bate ganha
  e um deck que também é combo tem de ficar com o nome do combo (as listas de UW
  Replenish jogam Exalted Angel).
- **A armadilha que isto quase repetiu, e que vale a pena não repetir:
  `combo_regras()` devolve a lista do `colecao_config.json` EM VEZ da do código,
  não a par dela.** As oito regras ficaram escritas no `premodern.COMBO_DEFAULT`,
  os testes passavam (constroem o seu próprio config) e na base a sério não
  nomeavam nada — o Sligh continuava a chamar-se *"Mono-Vermelho Bloodstained
  Mire"*. Tiveram de entrar **também** no config. Tem teste
  (`test_arquetipos.caso_as_regras_do_codigo_estao_TAMBEM_no_config`).
- **Os ficheiros que acompanham a base saem de `db.pasta_dados()`, não de
  `db.ROOT`** — e a diferença mordia: neste PC o `MTGVAULT_HOME` **não está
  definido**, só o `MTGVAULT_DB`. Pelo `ROOT`, o `arquetipos.json` (e o
  `vendas.csv`, que já tinha o mesmo defeito) iam parar a `~/mtgvault`, fora do
  repositório: o `git add data/arquetipos.json` não encontrava nada e o registo
  nunca era publicado. O `.gitignore` já dizia qual era a intenção (tem lá
  `data/vendas.csv`).
- **Efeito medido na base de 2026-09-08 (o mesmo `vault.db` nos dois lados):** a
  alocação **não mexe** — 7 901,85 € para fechar, 220 a comprar, 71 a ir buscar,
  127 a arrumar, venda 223c/1 176,56 € + 100 RL/8 099,55 € retida, 30 reservadas,
  iguais antes e depois. O que muda são os nomes: **17/17 arquétipos ficam com o
  mesmo `id` e o mesmo nome** depois de correr o `rebuild_archetypes` (que é o
  que o `daily` faz todos os dias e era de onde vinha o rótulo novo), e o top-10
  deixou de ter um único rótulo do clustering — *"Dimir Polluted Delta"* →
  **Psychatog**, *"Mono-Vermelho Bloodstained Mire"* → **Sligh**,
  *"Mono-Preto Withered Wretch"* → **Mono-Preto Graveborn Muse**. As duas
  sugestões são **Psychatog** (79 % / 35 %) e **Landstill** (68 % / 27 %).

**CAIXAS DEDICADAS: o "ir buscar" e a partilha ficam só para o DC e o SPML
(André, 2026-09-07 às 19:00, à letra; desde 2026-09-08 o Premodern voltou a
partilhar — ver acima).** *"Cada deck montado deixa de partilhar
cartas com outros decks nos formatos: pauper, CDEH e premodern"* e *"o que eu
quero é conseguir organizar os decks dentro das caixas e apenas mexer para
actualizar, logo vou precisar de múltiplos para os decks de premodern."* Isto
recorta as duas regras acima: continuam a valer, mas só onde ele as quer.
- `colecao_config.json → regras_por_formato[].dedicado` (hoje `premodern`, `cedh`
  e `pauper`), com override por caixa (`loadout[].dedicado`). Uma caixa dedicada
  **não vai buscar** (nunca diz *"em &lt;caixa&gt;"*: o que não alocou é compra),
  **não empresta** (as cópias que levou não são o `noutra` de mais ninguém) e
  **compra sozinha** (implica `compras_dedicadas`). Quem responde é
  `loadout.dedicadas`/`_empresta`.
- **O que NÃO muda:** a alocação. As cópias que ele tem continuam repartidas pela
  ordem de sempre e a `Caixa RL (PT)` continua a alimentar o Premodern — uma
  cópia da colecção que uma caixa leve não se compra outra vez. Isso é a colecção
  a ser repartida, não uma partilha entre caixas.
- **Efeito medido na base de 2026-09-07:** fechar tudo passou de **7 276,75 €**
  para **9 195,01 €** (213 → **287** a comprar, 78 → **4** a ir buscar). O
  Enchantress passou a comprar os 3 Brushland, o IGG os seus Tormod's Crypt e o
  Cloud cEDH o seu Lion's Eye Diamond. A venda **não mexeu**.

**CAIXA CONGELADA: montada é para ficar montada (2026-09-07, 19:00).** Uma caixa
dedicada **e** `montado: true` está congelada (`loadout.congelada`): as cópias
que estão lá dentro (`copy_allocation`) ficam **presas** — não voltam à gaveta,
não são realocadas e não entram na venda — mesmo que a lista de hoje já não as
peça. Se o Luffy actualizar o Pauper, a caixa continua montada com a lista antiga.
- A diferença sai como **delta de actualização**: `res["actualizacoes"][slot]`
  = *"tirar X, meter Y"*. Na página é a secção **🔄 Actualizar decks montados**
  (dentro da aba *Arrumar*); no CLI vem à cabeça do `arrumar`.
- **O "já arrumei tudo" NÃO lhe toca** (`guardar_arrumacao` preserva as linhas
  das caixas congeladas). Quem aplica o delta é o botão *"actualizei"* daquela
  caixa (`loadout.actualizar_caixa`, `act: "actualizar"` no `webapp.py`).
- Se a caixa ainda não tem linhas na `copy_allocation`, congelá-la não prende
  nada — a regra opera sobre a arrumação confirmada, não sobre uma intenção.

**COMPRAS PARTILHADAS: compra-se o MÁXIMO, não a soma (2026-09-07).** É a segunda
metade da regra de cima — *"não ter que comprar múltiplos para todos"*. O `noutra`
tratava as cópias que ele TEM; a lista de compras continuava a **somar as faltas
caixa a caixa**, o que contradiz a partilha. Na base de 2026-09-07 isso pedia 5
Swords to Plowshares PT quando 2 chegam, 9 Brushland quando 3 chegam e o Lion's
Eye Diamond duas vezes (535 € a mais numa carta só): **18 cópias e 608,75 €** a
mais no total (7 891,50 € → **7 282,75 €**; 230 → **212** a comprar, 61 → **79** a
ir buscar).
- Quem faz a conta é `loadout.partilhar_compras(slots)`, DEPOIS da alocação toda
  (precisa das faltas de todas as caixas). Agrupa por **(carta, pool de
  material)** e faz `comprar = max_caixa(o que a caixa compra)` — que é o mesmo
  que `max(0, max_caixa(precisa) − o que já existe no pool)`, porque cada caixa
  já desconta o que vê. Como mexe nas linhas depois de escritas, os totais de
  cada caixa recalculam-se em `_totais_do_slot` (não os inlines no ciclo).
- **As faltas DENTRO da mesma caixa (main + side) continuam a somar** — essas
  estão na mesa ao mesmo tempo. É entre caixas que não somam.
- **O pool** (`loadout.pool_compra`) é `(edições, acabamento, língua)`: uma cópia
  só se partilha se servir as duas caixas. Os pools que **se tocam** fundem-se:
  o Duel Commander é *"apenas foil"* sem exigir língua e o SPML é *"tudo foil e
  inglês"* — uma **EN foil** serve os dois, e o material da compra passa a ser o
  do pool (o mais exigente), senão a partilha mandava comprar uma foil PT que a
  caixa de Modern depois recusa. A fusão só se faz quando há **uma** língua
  exigida naquele acabamento; com duas não se escolhe por ele.
- As cópias compradas ficam da caixa de **maior prioridade** que as pediu e as
  outras passam a `noutra` — com a parte que ainda não está em casa em
  **`noutra_futura`**, que a página e o CLI dizem (*"3 depois de Enchantress
  comprar"*). Sem isso mandava-o à caixa do lado buscar uma carta que ninguém
  comprou ainda, que é o mesmo tipo de mentira que o "noutra caixa" veio corrigir.
- **`pct`/`tenho`/`missing` não mexem**: a caixa continua a ter a falta até a
  compra chegar. O que muda é de quem é a compra.
- **`colecao_config.json → loadout[].compras_dedicadas`** (default `false`): a
  caixa que ele queira fechar sem depender de trocas fica fora da partilha —
  compra as suas e ninguém conta com elas. Só manda nas COMPRAS; as cópias que
  ele já tem continuam repartidas pela alocação normal.
- Na página é a aba **Comprar**: `q` é o número real a comprar, o chip
  **«🔁 partilhada por N caixas»** (que conta as caixas da PARTILHA, não todas as
  que pedem a carta — o LED compra-se 2 em PT para o Premodern e 1 em EN nonfoil
  para as duas caixas de cEDH) e, em `para`, as caixas *servidas* vêm com
  `serve: true`. **Uma caixa servida não tem a carta na wantlist dela** — pô-la lá
  era comprá-la duas vezes, que é o defeito que isto veio corrigir.
- **O texto que o botão «copiar» copia leva o material em cada linha**
  (`2 Swords to Plowshares [PT]`, `1 Lion's Eye Diamond [EN nonfoil]`), de
  `loadout.marca_compra` — e vem da LINHA, não da caixa, porque numa compra
  partilhada é o do pool. O mesmo no `loadout <deck>` do CLI.

**As regras de material são por GRUPO DE FORMATO, e a ordem sai delas (André,
2026-09-07, à letra).** As duas regras abaixo foram as duas primeiras de cinco;
no mesmo dia ele completou-as e deu a ordem da alocação:

> *"Para Pauper, utilizas as cartas que forem necessárias do SPML e agregas ao
> Pauper."* · *"Os decks vigiados têm prioridade para ficarem com as cartas,
> desde que respeitem as regras."* · *"Língua/acabamento por formato: **Premodern**
> apenas as edições da era Premodern e em Português; **cEDH** apenas inglês
> non-foil; **Duel Commander** apenas foil; **SPML** tudo foil e inglês (RL pode
> ser non-foil); **Pauper** tudo foil se houver disponível, senão pode ser
> non-foil."* · *"**Ordem de prioridade na alocação: Premodern > cEDH > Duel
> Commander > Pauper > SPML.**"*

Vive tudo em `colecao_config.json → regras_por_formato` (com o mesmo default em
`loadout.REGRAS_FORMATO`), uma LISTA cuja **ordem é a ordem da alocação**.
Chaves: `formatos`, `lingua`, `acabamento` (`foil` | `nonfoil` |
`prefere_foil` = aceita as duas e gasta a foil primeiro), `edicoes`
(`"premodern"` = só até ao Scourge), `baldes` (os únicos que a caixa vê) e
`estrita` (a `lingua`/`baldes` põem a cópia **fora de vista** em vez de
substituto). O que estiver escrito no próprio slot do `loadout` ganha à regra do
grupo — uma excepção é uma linha de config, não uma linha de código.

- **O `prioridade` do slot deixou de mandar.** `resolve_slots` ordena por
  (grupo, deck vigiado primeiro, `prioridade`) e **reescreve `prioridade` com a
  posição global** que daí sai; o número do config fica em `prioridade_config`.
  Quem lê `s["prioridade"]` (página, CLI, `conflitos`) lê a ordem verdadeira.
  "Deck vigiado" = `fonte: "vigiado"` ou `ref` em `decks_vigiados`.
- **Uma cópia que está DENTRO da caixa do próprio deck escapa a todas as regras
  de material.** É a irmã da excepção do balde da regra 1: o cEDH passou a ser
  "só inglês non-foil" e o Blue Farm/Cloud cEDH têm PT e foil lá dentro — sem
  esta excepção o vault desmontava no papel dois decks que estão montados na
  estante. **Só vale para os baldes que SÃO a caixa de um deck**
  (`loadout.caixas_de_deck`): o `SPML` e o `Premodern (geral)` são colecção
  partilhada por vários slots, e aí a regra manda.
- **O Pauper não tem regra de `baldes`, de propósito** — é o *"utilizas as
  cartas que forem necessárias do SPML"*. O que mudou para ele foi passar a
  gastar as foil primeiro.
- **Toda a página que mostre uma caixa mostra as regras dela** via
  `loadout.rotulo_material(s)` → `(ícone, texto, classe)`, mais
  `loadout.requisito_material(s)` (a versão curta — `"PT · ≤SCG"`, `"EN · foil"`
  — que a aba *Comprar* põe em cada linha da wantlist) e
  `loadout.marca_wantlist(s)`. Escrito à mão em cada página, ficou lá um *"sem
  Caixa RL"* depois de a regra já ver a metade PT da Caixa RL — uma regra que a
  página não diz é a página a mentir em silêncio. A **classe** também vem daqui:
  cada página decidia-a com `"foil" in texto` e pintava de dourado o chip *"só
  nonfoil"* do cEDH.
- **`"nonfoil"` CONTÉM `"foil"` (2026-09-07).** Um teste de substring ou
  `/foil/` sobre o acabamento dá toda a cópia nonfoil como foil: a tabela de
  venda do `deckboxes.html` marcava com ✨ **41 das 62 linhas** (Lotus Petal,
  Mirri's Guile…) e mandava listá-las como foil. Quem responde é
  `loadout.e_foil(finish)` (= `finish in FOIL_FINISHES`), do lado do Python; a
  página recebe um booleano no payload e nunca reconstitui o teste em
  JavaScript. Tem teste nos dois lados (`test_loadout.caso_nonfoil_nunca_e_foil`
  e `test_paginas_loadout.caso_aba_vender_nao_marca_nonfoil`, que lê o HTML que
  a aba desenhou).
- **O chip das fontes diz duas gavetas, não quatro** (`loadout.fontes_material`).
  Era `"só de Colecção · Premodern (geral) · SPML · Caixa RL"` — quatro nomes que
  no modelo de colecção única são **um só** (os nomes antigos estão na regra para
  o código estar certo antes e depois da migração). Agora é *"fontes: Colecção +
  Caixa RL (PT)"*, e omite-se quando não restringe nada.
- **Efeito medido na base de 2026-09-07:** fechar tudo passou de **7 700,35 €**
  para **7 891,50 €** (230 a comprar, 61 a ir buscar). Só duas caixas mexeram —
  Cloud cEDH 76 %→72 % (perdeu 4 foil para o Duel Commander, que agora escolhe
  antes do Pauper) e Cloud (Duel Commander) 79 %→81 % / 104 €→294 € (ganhou-as,
  mas as nonfoil deixaram de fechar slot). A venda **não mexeu** (91 cópias /
  702,95 € + 39 RL / 5 736,16 €, `guardar` a 0).

1. *"Para Premodern as cartas são das edições que tínhamos visto e em Português;
   essas cartas NÃO entram para outros formatos!!"* (recortada a 2026-09-08 para
   a **Reserved List**, que passou a servir também o Legacy — ver *"A RESERVED
   LIST EM PT SERVE O LEGACY"* acima; para tudo o resto continua inteira) → um
   slot com `"lingua":"pt"`
   só fecha com cópias PT, e uma cópia PT de impressão até ao **Scourge
   (2003-05-26)** fica trancada ao Premodern. **Excepção que os dados obrigam a
   ter:** cópias que vivem no `balde` de outro slot do loadout já são desse deck
   — o Blue Farm tem um Lotus Petal (tmp) e um Tarnished Citadel (ody) PT dentro
   da caixa, e trancá-los ao Premodern desmontava um deck que está montado.
   **1b. O outro lado da mesma regra (André, 2026-09-07, à letra):** *"O
   Premodern só usa em PT, mesmo eu tendo a carta em inglês"* e *"na Caixa RL, as
   PT e as ENG estão separadas"* (esta segunda corrigiu, no mesmo dia, um *"o
   Premodern não é para olhar para a minha Caixa RL, na Caixa RL só estão cartas
   RL em inglês"* — a premissa é que era falsa; o commit 7acc52f, que excluía a
   Caixa RL inteira, foi ajustado). → `loadout._fora_de_vista`: um slot de
   `formato: "premodern"` só VÊ cópias `language='pt'`, e só nos baldes
   `Premodern (geral)`, `SPML` e `Caixa Reserved List` (mais o seu próprio) — o
   resto da colecção está dentro da caixa de outro deck montado. Não aloca uma
   EN, não a conta como **substituto** e não lhe desconta no custo: para uma
   caixa de Premodern, uma carta que só existe em EN é **falta** (compra-se em
   PT), não "tenho mas não serve". É mais forte que a regra da língua do
   `_porque_nao` e é de propósito: um substituto diz *"decide se abres
   excepção"*, e nisto ele já decidiu que não abre.
   **A Caixa RL é uma no config e duas na estante**, e a diferença decide tudo:
   as PT de lá servem o Premodern (na base de 2026-09-07 dão 30 cartas às cinco
   caixas: Stiflenought 5, UW Replenish 9, Enchantress 4, Elves 10, IGG 2), as EN
   não. Por isso `loadout.local(lot)` mostra **`Caixa RL (PT)`** ou **`Caixa RL
   (EN)`** em todo o lado onde antes aparecia o balde — página, `loadout <deck>`
   ("tirar de:"), `vender`, CSV. Consequência a assumir: nenhuma EN é protegida
   pela saída `guardar` do lado do Premodern (as 4 Opalescence EN, os 2 Mox
   Diamond EN, as 4 Intuition EN) — passam por `venda`/`venda_rl`, a confirmar
   uma a uma. As EN continuam disponíveis para as outras caixas: o Legacy aceita
   Reserved List nonfoil.
2. *"Standard, Pioneer, Modern e Legacy: as cartas são todas Foil (menos as
   Reserved List)"* → `"acabamento":"foil"` nesses slots: só `foil`/`etched`, e
   as cartas com `catalog.cards.reserved` podem ser nonfoil. Uma nonfoil de uma
   carta não-RL **não fecha o slot**; a wantlist pede foil. O custo desses decks
   usa o **preço foil** (`loadout.card_price`) — o `wantlist.cheapest_price` só
   olha para nonfoil e dava um custo sistematicamente por baixo.

**A venda tem sete saídas, não uma** (eram quatro até 2026-09-08). Misturá-las
dava um total que não se
podia usar: `venda` (excedente normal), `venda_rl` (Reserved List — não se
volta a imprimir, confirma-se uma a uma, e desde 2026-09-08 só entra aqui a que
passa a regra dos 5 % abaixo), **`rl_segurar`** e **`rl_sem_historico`** (a RL
que a regra travou: *"subiu"* e *"não sei"*, ver a seguir), `retidos` (baldes com
`reter_extras_meses`; a regra dos 6 meses continua inerte por falta de data de
"última utilização", por isso guardam-se e dizem-no), **`reservadas`** (cópias
que uma SUGESTÃO de Premodern usaria — ver a secção do Premodern abaixo: não são
excedente nenhum, são o deck que ele ainda não disse se quer, e o botão *"não
quero este"* liberta-as no mesmo dia) e **`guardar`**: os
SUBSTITUTOS. Este último não é um requinte — foi um erro real da primeira
versão: o playset de 4 dava as cópias a mais como excedente e a lista mandava
vender exactamente as cartas que faltam a um deck do loadout. **Uma cópia que
serve um deck do loadout e só falha no acabamento nunca vai para a venda.** O
caso que a motivou eram as 4 Opalescence EN da Caixa RL; desde a regra 1b acima
nenhuma EN é vista pelas caixas de Premodern e essas vão mesmo para `venda_rl` —
a saída `guardar` ficou só para as **nonfoil dos slots de foil**, que é onde ele
não fechou a porta (na base de 2026-09-07 dá 0 cópias: as nonfoil que servem
esses slots ainda cabem todas no playset).

**RESERVED LIST: SÓ SE VENDE O QUE NÃO VALORIZOU (André, 2026-09-08, à letra).**
*"Cartas de RL só vão para venda se não tiverem subido 5 % de valor nos últimos
3 meses."* Motor em `loadout.avaliar_rl` + `loadout.card_price_em`, config em
`colecao_config.json → venda` (`rl_subida_minima_pct: 5`, `rl_janela_dias: 90`,
`rl_janela_minima_dias: 25`, `rl_tolerancia_dias: 10`, `rl_limiar_fixo: false`).
Corre no fim do `sell_list`, sobre a lista de venda já
formada: a regra é sobre a **cópia**, não sobre o motivo por que ela lá foi parar
(excedente ou *"não usada por nenhum deck"*), e espalhá-la pelos dois ciclos era
escrever a mesma decisão em dois sítios.
- **Três respostas, não duas.** `hoje < antes × (1 + limiar)` → vende-se;
  `hoje ≥ antes × (1 + limiar)` → **`rl_segurar`**, com o motivo *"RL em
  valorização: +X % em N d"*; **histórico mais curto do que a janela mínima** →
  **`rl_sem_historico`**, com *"(desde &lt;data&gt;: N d, precisa de 25)"* (o
  `limiar` é os 5 % ajustados à janela — ver o ponto da janela, abaixo).
  A terceira é a que importa: uma RL é a decisão menos
  reversível de todas, e dar *"não subiu"* como resposta a *"não sei"* era o
  padrão do `event_tier` outra vez, mas sobre dinheiro que não volta. As duas
  saídas ficam separadas porque *"subiu"* é uma decisão tomada e *"não sei"* é
  uma decisão por tomar — só a segunda é que ele pode querer forçar.
- **O preço de há 90 dias é a ÚLTIMA cotação ATÉ esse dia**, e não uma linha
  datada nesse dia: o `price_history` só guarda MUDANÇAS
  (`prices.write_prices` — *"não há linha nova quer dizer que o preço
  manteve-se"*). Procurar só dentro de uma janela estreita dava *"não sei"* a
  toda a carta estável, que é precisamente a que não subiu — a regra ficava a
  segurar exactamente o que existe para deixar vender. A `rl_tolerancia_dias`
  (±10) cobre o caso em que o histórico **começa a meio** da janela: aí usa-se a
  cotação mais antiga que lá esteja.
- **As duas pontas da conta são a MESMA conta** (`card_price_em` espelha o
  `card_price`: MIN(trend) sobre as impressões do mesmo nome, na mesma família de
  acabamento, na mesma fonte). Com uma conta diferente em cada ponta, a
  percentagem media a diferença entre as duas contas e não a do mercado.
- **A PODA DIÁRIA TEM DE GUARDAR A RL O TEMPO DA JANELA** — e não guardava. O
  `daily._prune_prices(con, 30)` apagava **tudo** o que tivesse mais de 30 dias,
  todos os dias: com a janela a 90 **nunca** haveria um preço de há três meses
  para comparar. A regra respondia *"não sei"* a tudo, para sempre, a lista de RL
  ficava vazia e **nenhum passo dava erro** — o padrão do `event_tier`, desta vez
  sobre a decisão de venda que vale mais dinheiro. Agora a poda guarda
  `rl_janela_dias + rl_tolerancia_dias + 7` dias **só para as cartas da Reserved
  List** e continua a podar o resto aos 30. Cabe bem: medido em 2026-09-08, a RL
  são **2,5 %** das linhas (6 758 em 28 dias, ~240/dia) — 100 dias delas são
  ~24 000 linhas contra as ~984 000 de guardar tudo. Tem teste
  (`test_venda_rl.caso_a_poda_diaria_nao_pode_matar_a_regra`).
- **A JANELA CRESCE SOZINHA, E O LIMIAR ACOMPANHA-A (André, 2026-09-08, à letra:
  *"podemos começar já com 25 e vamos vendo como avança o histórico"*).** O
  parágrafo anterior descrevia o problema: com a janela fixa nos 90 e um
  `price_history` de 29 dias, **nenhuma** RL passava o teste, as 100 cópias /
  8 099,55 € saíam todas por `rl_sem_historico` e a lista de RL ficava vazia até
  2026-11-08. Baixar o `rl_janela_dias` à mão resolvia hoje e criava a tarefa de
  o voltar a subir — que ninguém ia lembrar-se de fazer. Agora:
  - **`rl_janela_dias` (90) é o MÁXIMO, não a janela.** A efectiva é
    `min(máximo, histórico da carta − 2)` (`loadout.rl_janela_efectiva`); os dois
    dias de folga são para o dia-alvo cair DEPOIS da primeira cotação e não em
    cima dela. Abaixo de **`rl_janela_minima_dias` (25)** não se decide de todo —
    é o *"não sei"* de sempre, com a fronteira num número dele em vez de no
    máximo. Hoje mede em **27 dias**; em Novembro está nos 90 sem ninguém tocar
    no config, e sem uma janela a saltar de 25 para 90 num dia.
  - **O limiar é PROPORCIONAL**: `rl_subida_minima_pct × janela / máximo` — 5 % a
    90 dias, **1,4 % a 25**. Os 5 % dele são *"nos últimos 3 meses"*; exigi-los
    numa janela de 27 dias é exigir ~17 %/90 d, ou seja **vender em Setembro
    exactamente o que a regra dos 3 meses seguraria**. A alternativa é dele e
    está no config: **`venda.rl_limiar_fixo: true`** aplica os 5 % à letra —
    medido, isso passa **13 cópias / 2 905,09 €** de *"a segurar"* para a venda
    (os 2 Mox Diamond a +4,9 % em 27 d, que são +16,3 % ao ritmo de 90).
  - **Cada linha diz em que janela foi medida** (`+4.9 % em 27 d ≈ +16.3 %/90 d`,
    `loadout._texto_janela` → `rl_nota`), na página e no CLI, e nas linhas que
    **se vendem** também: *"não subiu"* medido em 27 dias e medido em 90 não são
    a mesma afirmação. O sinal vem do `:+` e não de um `+` escrito à mão — metade
    destas linhas desceu, e a tabela mostrava `+-3.2 %`.
  - **Efeito medido na base de 2026-09-08** (a mesma cópia dos dois lados): a
    lista de RL deixa de estar vazia. **Vender 40c / 3 221,01 €** (Intuition EN
    −3,2 %, Taiga, Tolarian Academy −9,4 %), **segurar 23c / 3 999,99 €** (2 Mox
    Diamond +4,9 % = 1 670,94 €, 5 Null Rod +2,9 %, 3 Gilded Drake +4,4 %,
    Serra's Sanctum +5,0 %, 4 Deranged Hermit +9,6 %) e **35c / 778,30 € ficam
    por medir** — são as cartas cujo histórico só começa a **2026-08-17** (20 d).
    A alocação **não mexe** (7 901,85 €, 220 a comprar, 70 a ir buscar, 309 a
    arrumar) e a venda normal também não (221c / 1 152,19 €).
  - A `rl_tolerancia_dias` fica, mas passou a ser quase inerte: com a janela a
    encolher para o histórico da carta, o dia-alvo cai sempre depois da primeira
    cotação e o ramo da tolerância deixa de ser preciso. Continua a valer para a
    poda diária (que guarda `janela + tolerância + 7` = **107 dias** de RL) e
    para o dia em que alguém volte a fixar a janela.
- A linha retida guarda o motivo por que ia à venda em **`porque_venderia`**, e a
  página e o CLI dizem-no (*"ia por: excedente (mais de 4)"*): *"subiu 7 %"* é
  uma resposta, e sem a pergunta ao lado não se percebe o que a regra impediu.
- **A regra é só para a Reserved List** (`lot["rl"]`, de `catalog.cards.reserved`)
  e **não tem botão «vendida»** — o que a liberta é o config, não um clique.

**A RESERVED LIST EM PT SERVE O LEGACY (André, 2026-09-08, à letra).** *"RL em PT
pode servir para Legacy e Premodern, mas não para cEDH nem outro formato."* É um
recorte na tranca de 2026-09-07 (*"as cartas PT da era Premodern NÃO entram para
outros formatos!!"*, ver a regra 1 mais abaixo), e **só nela**: para tudo o que
não seja Reserved List a tranca continua inteira.
- **A excepção é do FORMATO, não do grupo.** O Legacy é SPML — *"tudo foil e
  inglês"* — e continua a sê-lo: a chave nova é
  `regras_por_formato[].por_formato` (`{"legacy": {"rl_lingua": ["pt","en"]}}`),
  fundida pelo `loadout.regra_do_formato`, e o `rl_lingua` ganha à `lingua` **e**
  à tranca do PT, mas só quando `lot["rl"]`. Parti-lo num grupo próprio era
  inventar um sexto grupo que ele nunca ditou e mexer em duas coisas que ninguém
  pediu: a **ordem da alocação** (a ordem desta lista É a ordem) e o **grupo da
  partilha de compras**. O Standard, o Pioneer e o Modern — o mesmo grupo — não
  aceitam a carta; o cEDH e o Duel Commander também não.
- **E a lista de venda tem de saber disto, senão a regra não vale nada.** A caixa
  de Legacy dele está `candidata` e **vazia**: a alocação não lhe dá nada, e a
  Mox Diamond que ela passou a aceitar ia à venda na mesma. Enquanto não há deck
  escolhido, quem diz o que a caixa vai pedir é o **top-N do metagame** — o mesmo
  `foil_report` que a página mostra —, e as cópias de **Reserved List** que
  qualquer um desses candidatos usaria ficam em `reservadas`, com o motivo
  *"serve Legacy: &lt;arquétipo&gt;"*. Motor em `loadout.reservas_rl` +
  `_reserva_para`, config em `venda.reservar_rl_formatos: ["legacy"]`.
  **Assim que a caixa tem lista, a reserva encolhe para o que falta a esse deck**
  — reserva-se o que a caixa pede menos o que a alocação já lhe deu; com
  candidatos reserva-se o que a lista PEDE, pela mesma razão que as sugestões de
  Premodern (as cópias que o candidato já "tem" são exactamente as que se estava
  a pensar vender). É o **máximo** entre candidatos, nunca a soma: são
  alternativas entre si.
- **Só a Reserved List.** Uma carta normal que um candidato use continua a
  vender-se: compra-se outra vez, e segurar a colecção por causa de três listas
  de metagame era o contrário do que ele pediu ao mandar vender os excessos.
- **Efeito medido na base de 2026-09-08:** a alocação **não mexe** (7 901,85 €,
  220 a comprar, 70 a ir buscar, 309 a arrumar) — a caixa de Legacy está vazia.
  O que muda é o que o formato VÊ: **0 → 73 cópias / 3 474,79 €** de RL em PT
  deixam de estar invisíveis para o Legacy (Null Rod, Gilded Drake, Serra's
  Sanctum, Tolarian Academy, Deranged Hermit…). Na venda, a reserva tira hoje
  **2 cópias / 100,25 €** (Scrubland 3ed EN, para o *Mardu Voice of Victory*, e
  Tundra 3ed EN, para o *Azorius Stifle*) — poucas porque o top-3 de Legacy de
  hoje são listas modernas cujas RL são duais, que ele tem em EN. As PT caras
  (Mox Diamond, Gilded Drake, City of Traitors) não vão à venda por outra razão:
  a regra dos 5 % está a segurá-las.
- **O bloco «Reservadas» passou a ter duas origens** — as sugestões de Premodern
  e a RL do Legacy. O título mudou (*"decks por decidir"*) na página e no CLI:
  um bloco que diz *"sugestões de Premodern"* e traz uma Scrubland de Legacy é
  uma página a mentir em silêncio.

**MODELO DE COLECÇÃO ÚNICA (André, 2026-09-07, à letra).** *"Põe a colecção toda
em uma coisa só, com excepção da RL, e assim vais buscar as cartas ao mesmo
sítio, mas aplicando as regras."* Substitui a regra de 2026-08-13 (*"só premodern
e SPML são coleções, o resto é tudo decks"*), que era a mesma ideia com o
vocabulário errado.

Até aqui um `sub_collection` era ao mesmo tempo duas coisas: uma **gaveta**
(`SPML`, `Premodern (geral)`) e uma **deckbox** (`Blue Farm`, `Cloud cEDH`).
Misturá-las fez o vault mentir mais do que uma vez — a mais cara foi *"meti 4
fotos, estavam lá 4 Utrom Monitor, mas no deck Pauper não aparecem"*: estavam no
`SPML` e a página do Pauper só olhava para o balde do Pauper.

Depois da migração há **duas gavetas e nada mais**:
- `Colecção` — tudo o que não está numa deckbox;
- `Caixa Reserved List` — a excepção que ele pediu (e que na estante são duas,
  as PT e as EN separadas: ver `loadout.balde_local`).

E **a deckbox deixa de ser um balde**: onde uma cópia está é a ALOCAÇÃO do
loadout, gravada em **`copy_allocation`** quando ele carrega no *"já arrumei"*.
A gaveta de onde veio fica em `copies.balde_origem`, para a aba *Arrumar* poder
dizer de que prateleira a tirar hoje.
- **"Colecção" = está num balde de colecção E não está dentro de nenhuma caixa.**
  Quem decide os baldes é `colecao_config.json → baldes_coleccao`
  (`loadout.baldes_coleccao()`), que tem os nomes novos E os antigos de propósito
  — o mesmo código tem de estar certo na base de antes e na de depois da
  migração. Já lêem daí: `meta_coverage.COLLECTION_BALDES`, `classify`,
  `colecao_cor`, `loadout.caixas_de_deck`.
- **"Deck" = alocado a uma caixa.** `collection.owned_playable(...,
  fora_das_caixas=True)` desconta a `copy_allocation` — é o gémeo, no modelo
  novo, de "não olhar para os baldes dos decks". O `owned_available` usa-o.
- **Um balde de colecção nunca é caixa de deck**, mesmo que um slot de Commander
  o aponte como o seu (`caixas_de_deck`). Sem essa linha, depois da migração a
  colecção inteira passava a "estar dentro de um deck" e escapava às regras de
  material.
- **A migração**: `python -m mtgvault.cli migrar-coleccao-unica` (tem `--dry-run`
  e faz backup sozinha; é idempotente e o `balde_origem` só se escreve quando
  está a NULL). **Ainda NÃO correu na base do André** — corre-se quando isto
  entrar no main. Medida na cópia da BD, é **neutra nos números**: 7 891,50 € para
  fechar, 230 a comprar, 61 a ir buscar, venda 91c/702,95 €, classify
  {deck 152, coleção 938, vender 97} — iguais antes e depois.
- **A migração TEM de semear a `copy_allocation`** com as cartas que viviam nos
  baldes dos decks. Sem isso desmontava no papel quatro decks que estão na
  estante (as regras de material voltavam a aplicar-se a cartas já sleevadas) e o
  vault mandava comprar cartas que estão em casa. Tem teste.
- O `classify.py` deixou de decidir o "pool" pelo balde: decide-o pela CARTA
  (PT + impressão até ao Scourge = Premodern, o resto SPML), que é a mesma tranca
  do `loadout._porque_nao`. Duas respostas diferentes à mesma pergunta era
  exactamente o erro a evitar.
**Classificação Deck / Coleção / Vender (`classify.py`, 2026-08-13; adaptada ao
modelo acima em 2026-09-07).** É a regra do André já implementada, que alimenta a
página `colecao_cor.html`:
- Dentro da colecção, cada carta é **Deck** (cópias que um deck pede),
  **Coleção** (jogável, backup até 4) ou **Vender**.
- **SPML é DINÂMICO, Premodern é ESTÁVEL** (`colecao_config.json`):
  - **SPML** → `spml_formatos` {formato: estado}. O André joga vários formatos
    ao mesmo tempo. Estados: `a jogar`/`a treinar` = ATIVO (os decks desse
    formato, na tabela `decks`, reservam cartas → Deck); `a preparar` = só
    wantlist, não reserva; `ignorar` = fora. `ACTIVE_STATUSES` define quais
    reservam. Formato ativo sem decks na tabela `decks` não reserva nada ainda.
  - **Premodern** → completude DETETADA automaticamente por `premodern_status()`:
    um deck está completo quando o André tem 100% do consenso do arquétipo
    (`PREMODERN_DECKS`, assinatura → ≥40%). Completo → cartas trancam-se no deck
    (saem da coleção, como o Commander — Premodern roda pouco/nada) e ficam lá
    até desmontar. `premodern_decks_completos` no config é a tranca STICKY: se a
    lista mudar depois de completo, as cartas NÃO voltam à coleção — só se dá a
    wantlist do delta. `premodern_status()` devolve %/em-falta por deck (é, na
    prática, a wantlist de cada deck de Premodern).
- **Vender** = cópias acima de 4 (construído), OU cartas não legais em NENHUM
  formato real (`legalities` da Scryfall — rede de segurança para nunca sugerir
  vender uma carta jogável por falta de dados nas minhas listas). **Básicas
  nunca se vendem.** Apresentado como *sugestão a confirmar*.
- **Falta afinar (decisão futura do André):** cartas jogáveis num formato mas
  que ele **não vai usar** acabam por ir para Vender — por agora ficam em
  Coleção. Também: regras por deck (foil-only, PT, Premodern old-border) e o
  *loadout* de decks montáveis em simultâneo. Qualquer sugestão de "vender"
  tem de respeitar isto.

**Alinhamento deck ↔ lista vigiada ↔ balde (2026-08-14).** Cada deck real do
André = um balde (`sub_collections`) + uma lista vigiada (`watched`), ligados na
tabela `deck_collection`. Já ligados: Blue Farm [Primer]→`Blue Farm`, Cloud
[cEDH]→`Cloud cEDH` (distinto do Cloud de Duel Commander, balde `Cloud`), Luffy —
Pauper→`Pauper Affinity`. Por ligar: Luffy — Premodern (Stiflenought), Harry1232
— Legacy. `deck_collection` JÁ é lido: `colecao_cor._watched_deck_pools` e
`colecao_cor._watched_deck_pools` junta-se por ela.
**CORRIGIDO a 2026-09-09:** a `deck_collection` e a `deck_meta` só existiam no
`vault.db` dele (criadas à mão) e numa base nova o `colecao_cor.build` rebentava
com *"no such table: deck_collection"* — o irmão do `event_tier`, a estoirar em
vez de mentir. Estão agora nos dois sítios (`schema.sql` **e** `db._migrate()`),
com as colunas copiadas tal e qual da base dele, e o `test_schema_completo.py`
tranca-o (com um caso que apaga as tabelas para provar que continuam a fazer
falta). A `deck_meta` **não é lida por ninguém** — a decisão de 2026-09-07 pôs as
preferências no `colecao_config.json` (ver o cabeçalho do `webapp.py`); fica
declarada porque existe na base dele, não porque alguma página dependa dela.

**Regras por coleção (`colecao_config.json` → `regras_colecao`).**
`reter_extras_meses` = **6** (formalizado 2026-08-14) para os decks de
Commander/cEDH/Duel Commander/Pauper — `Blue Farm`, `Cloud cEDH`, `Cloud`,
`Pauper Affinity`. Estes são "coleção própria + lista vigiada": as cartas EXTRA
(as do balde que a lista do deck já não usa) guardam-se até 6 meses da última
utilização; passado isso sem uso → Vender. Premodern NÃO usa isto (tranca por
completude). **Por decidir/implementar:** fonte de "última utilização" (última
vez na lista vigiada) — ainda não em `classify.py`; inerte até haver histórico.

**Decks de comandante por consenso (`commander_decks.py`).** Alguns decks de
comandante não copiam UMA decklist (como `my_decks.py` faz no Modern) — são
seguidos por CONSENSO, em **TRÊS CAMADAS** por inclusão nas listas do comandante
(singleton): **núcleo ≥50%** (= o deck, gravado em `decks`/`deck_cards`), **flex
25–50%** e **tech 15–25%** (só opções, calculadas em `tiers()`, não gravadas).
**Filtra pela identidade de cor do comandante** (regra do André, 2026-08-20: as
listas misturam versões com partner que trazem cartas off-color; só entram as que
cabem na cor). `tiers(con, fmt, commander)` devolve {core, flex, tech, n, ci} e é
reusado por `colecao_cor` (secção "Decks vigiados": Cloud em camadas, verde=tem/
cinza=falta, com % das listas). Cloud (Duel Commander) = Cloud, Midgar Mercenary,
mono-branco: núcleo 44 · flex 43 · tech 30 (de 102 listas) → 117 cartas legais,
dá para as 100. Job diário: passo `decks-comandante`.

**Core vs tech.** `core_copies` = maior k tal que P(cópias >= k) >= 0.90,
medido sobre *todas* as listas do arquétipo, não só as que jogam a carta.
Exemplo canónico (está em `test_analysis.py`): 80% joga 3 cópias, 20% joga 4
→ core = 3, flex = 0.2. Não mudes o cálculo sem atualizar esse teste.

**Deduplicação entre fontes.** Uma lista é identificada pelo conteúdo:
formato + cartas + dia + jogador. Prioridade: manual 4, mtgo 3, mtgtop8 2,
mtggoldfish 1. O mtgtop8 re-hospeda listas do MTGO (as páginas dele dizem
`Source: mtgo.com/...`), por isso guardar as duas contaria o mesmo deck duas
vezes e enviesaria as estatísticas para o online. Toda a escrita de decklists
passa por `sources.store_decklist`.

**Comandantes.** No `.dec` do mtgtop8, o comandante vem na linha `SB:`. Nos
formatos de comandante é reencaminhado para o mainboard, senão ficava fora da
análise de core.

**Que listas contam para o metagame (2026-09-07).** Palavras do André: *"no
mtgvault não quero listas de league; quero challenge, showcase, e presenciais
com 64 ou mais jogadores — menos Duel Commander, que pode ter menos jogadores e
pode ser ligas."*

- A regra está **num sítio só**: `sources.lista_conta(row, fmt)` (Python) e
  `sources.counting_sql(fmt, alias)` (pedaço de SQL para o WHERE), configuradas
  em `colecao_config.json → metagame_fontes` (`tiers`,
  `min_jogadores_presencial`, `ligas`, com `_default` + exceções por formato).
  O peso de cada lista no ranking é `sources.tier_weight`/`tier_weight_sql`.
  **Toda a consulta nova que leia `decklists` para análise tem de passar por
  ali** — antes cada página filtrava à sua maneira (o showcase pela fonte, o
  metagame pelo tier, o buildable por uma lista NON_PREMIER) e discordavam em
  silêncio. Já usam: `meta_coverage._rank`/`emerging_decks`/`_n_lists`/
  `counting_lists`, `metagame._latest_list`, `decks_faziveis`, `showcase._lists`,
  `analysis._fetch_lists` (logo `rebuild_archetypes`/`rebuild_roles`),
  `my_decks`, `commander_decks._inclusion`,
  `buildable`.
- **`classify.py` e `core_decks.py` NÃO usam a regra, de propósito.** O
  `_played_names`/`_last_played` do classify é a rede de segurança contra
  sugerir vender uma carta jogável, e a tranca de completude do Premodern
  precisa de todas as listas do arquétipo — filtrar aí faria a página sugerir
  vendas a mais, que é o erro caro.
- **Um presencial sem `event_players` NÃO conta** — não se assume o mínimo. Daí
  o passo diário `jogadores-eventos` (`mtgtop8.backfill_event_players`, ≤40
  eventos por corrida, 1 pedido/s), que grava `0` quando a página do mtgtop8 não
  mostra contagem, para não voltar a pedir a mesma página todos os dias.
- **Listas `manual` contam sempre** (foste tu que as meteste; é a porta de
  entrada dos formatos que os scrapers não cobrem).
- **`event_tier` deixou de ser decidido pela fonte.** O mtgtop8 re-hospeda o
  MTGO ("Premodern event - MTGO League", "Modern event - MTGO Challenge 32") e
  esses 521 registos estavam todos em `Presencial`. Agora o nome manda **quando
  diz MTGO**; sem essa marca continua `Presencial`, porque um "BIG MAGIC Open —
  Champions Cup Premium Qualifier" de 131 jogadores é papel a sério e quem o
  julga é o nº de jogadores, não a palavra "Qualifier". O `backfill_event_tiers`
  passou a ser idempotente sobre TUDO (não só sobre os NULL), para uma mudança
  de regra acertar o passado sozinha.
- **Ligas nem se guardam** (`store_decklist` recusa-as, e o `harvest` salta o
  evento antes de pedir os `.dec`), e o passo diário `podar-ligas`
  (`analysis.prune_leagues`) apaga as que ficaram do passado — ~3.500 listas,
  cerca de um terço do `vault.db`, que não alimentavam página nenhuma. Faz **um**
  backup antes da primeira poda (`data/backups/vault-antes-filtro-<data>.db`) e
  nunca mais. Só mexe no tier `League`: presenciais pequenos e Preliminary ficam
  na base (não contam, mas são histórico barato e ainda podes dar-lhes exceção).
- **Consequência medida:** o Premodern **não** fica sem listas (441 contam — as
  Premodern Challenges do MTGO, incluindo as re-hospedadas). Quem fica sem
  metagame é o **cEDH**: só 16 das 564 listas contam, porque é todo presencial e
  quase nenhum evento traz contagem de jogadores. Uma linha no config resolve:
  `"cedh": { "min_jogadores_presencial": 0 }`.

## A ENTRADA DE CARTAS: sem edição não se inventa, e a foto fica (2026-09-08)

Duas decisões que vêm da auditoria `work/revisao/mtgvault-edicoes-suspeitas.md`
(5 Plains do Cloud cEDH gravadas como Alpha, 309,50 € de valor fantasma) e do
relatório `work/revisao/mtgvault-lookup-fotos.md`.

**1. `find_printing` sem `set_code` levanta `scryfall.EdicaoEmFalta`.** Antes
terminava em `ORDER BY released_at ASC LIMIT 1` e devolvia a impressão **mais
antiga** — para as básicas, sempre Alpha. Uma linha de CSV com a edição em
branco não dava erro: dava a edição errada, em silêncio. É o padrão do
`event_tier`, outra vez: um passo que corre sem erro e produz um valor falso.
- `EdicaoEmFalta` é subclasse de `LookupError` **de propósito** — quem já o
  apanhava não muda de comportamento, mudou só a mensagem
  (`"edicao em falta: <nome>"`).
- **A excepção explícita é `adivinhar=True`** (CLI `--adivinhar`): devolve a
  impressão **mais recente e, dentro dessa data, a mais barata** — o contrário
  do que fazia. Quem não sabe a edição de um Plains tem o Plains barato de um
  set recente, não o de Alpha. O palpite fica DITO na cópia:
  `add_copy` escreve `edicao adivinhada em <data>: <set> #<nº>` na
  `copies.notes`. É por essa nota que uma auditoria futura as encontra — a
  assinatura "a edição é a mais antiga da carta" dá falsos positivos (metade das
  cartas caras só tem uma impressão; ver a coluna *impressões* no `duvidas.md`).
- **`collection.import_csv` devolve uma linha por linha** (`resultados=[...]`,
  `RESULT_FIELDS`) com `resultado`, `motivo` e o `copy_id` criado. A linha sem
  edição **para** com `motivo: edicao em falta`; as outras continuam — não se
  perde o lote por causa de uma linha. O `processar_fotos.py` grava esse CSV ao
  lado do de entrada; o `mtgvault.cli import` aceita `--resultado`.
- O `PROCESSAR_FOTOS.md` (o guia que o Claude que cataloga as fotos lê) passou a
  dizer que `set_code` é **obrigatório**. Mais vale uma carta por catalogar do
  que uma carta catalogada errada.

**2. As fotos nunca se apagam, e ficam ligadas à cópia.** As 33 fotos das cópias
1-156 (10 042 €) já não existem: o fluxo antigo movia-as e nada guardava a que
cópia deram origem, por isso quando apareceu a primeira suspeita não houve nada
para reler. Quem arruma é `collection.arrumar_fotos`, partilhada pelos dois
importadores (`processar_fotos.py` e a tarefa `mtg-fotos-novas` do ai-pc, via
`import --arrumar-fotos`).
- Destino: **`pendentes/fotos processadas/<AAAA-MM>/`**, com o nome original. A
  pasta é por mês porque a única ia em milhares de ficheiros.
- A ligação fica em **dois** sítios: `copies.photo_path` (o caminho novo) e o
  `pendentes/fotos processadas/aplicado.csv` (data, foto, `copy_id`, carta,
  edição, quantidade, balde). Não confundir com o `aplicado.csv` do
  `ai-pc/work/mtg-fotos`, que é o registo da *revisão* de fotos.
- **Uma foto cujas linhas não entraram todas FICA em `pendentes/`.** A linha
  ainda está por catalogar; arrumá-la escondia trabalho por fazer.
- No `processar_fotos.py` as fotos arrumam-se **antes** do `db_push`: a
  evidência do que foi importado não pode depender de uma publicação que falha.
- **Quem lê essa pasta tem de a ler em profundidade.** O `backup-offsite` do
  ai-pc lia-a com `iterdir()`: a partir do dia da primeira pasta por mês teria
  dito `"0 novas"` e guardado nada, verde, para sempre. Passou a `rglob`, com o
  índice por caminho relativo (para as fotos antigas, na raiz, o relativo é o
  nome — o índice de ontem continua a valer). O `common.all_photos()` da revisão
  de fotos tinha o mesmo defeito e a mesma correcção.

**3. «JÁ A TENHO, ESTÁ NO DECK»: dar check numa falta (André, 2026-09-08, à
letra).** *"Arranja forma de eu poder dar check nas cartas das faltas, para dizer
que já as tenho e já coloquei no deck."* Metade da lista de compras dele é coisa
que já tem em casa e que o vault nunca catalogou; até aqui o único caminho era
tirar foto e esperar, e entretanto a caixa continuava a somar a carta ao *"fechar
tudo por X €"*, que é o número por que ele decide. Motor em
`loadout.registar_falta`/`anular_falta`, botão no **passo 2** do painel *Montar*
(`deckboxes.jaTenhoHTML`), acções `falta`/`falta-anular` no `webapp.py`.
- **Um check faz DUAS escritas, e as duas são precisas**: a cópia (`copies`) e o
  lugar dela (`copy_allocation` daquela caixa). Uma sem a outra deixava o vault a
  discordar dele — a cópia sem caixa manda-o à gaveta onde ela não está, a caixa
  sem cópia volta a pedir a carta amanhã. Não passa pelo config: nada disto é uma
  preferência, é a estante.
- **O MATERIAL sai da caixa** (`loadout.material_da_caixa`, `edicao_limite`,
  `finishes_aceites`): o que ele acabou de dizer que tem é, por definição,
  material que a caixa aceita — senão não fechava o slot. Premodern → `pt` e
  impressão ≤ Scourge; SPML/Legacy → `en foil`; cEDH → `en nonfoil`.
- **A EDIÇÃO é a parte incerta e não se finge que não é.** O selector da linha
  mostra as impressões que cumprem a regra DAQUELA caixa
  (`loadout.impressoes_da_falta` → `scryfall.impressoes`), com o palpite de
  sempre à cabeça (`find_printing(adivinhar=True)`, agora com `ate`/`finishes` —
  a impressão mais recente de Swords to Plowshares é de 2022 e é a que um palpite
  sem regras escolhia, para uma caixa que a recusa). Uma edição escrita à mão que
  não esteja na lista é **recusada** (409 com a razão).
- **A cópia fica marcada `edicao por confirmar`** (`collection.MARCA_POR_CONFIRMAR`,
  na `notes`) e aparece no **passo 1** num bloco próprio — *«✓ Já na caixa
  (disseste que tinhas)»*, com **📷 edição por confirmar**. Sem esse bloco o
  palpite virava facto por ninguém voltar a abrir a `notes` de uma cópia.
- **A foto seguinte ACERTA essa cópia, não cria outra**
  (`collection.acertar_edicao`, chamada do `import_csv` e por isso comum aos dois
  importadores). Criar uma segunda era ficar com o dobro das cartas na base por
  ele ter sido diligente. Com menos cópias do que as que esperavam, a linha
  parte-se e a confirmada **leva consigo o lugar dentro da caixa**; o que a foto
  trouxer a mais entra como sempre.
- **O anular apaga a cópia que acabou de nascer, e só essa**: o `anular_falta`
  recusa um `copy_id` sem a marca. Passada a janela (`montar.anular_segundos`) é
  uma cópia normal e quem a tira é o **«vendida»** — um desfazer sem prazo era um
  segundo caminho para apagar cartas, e esse já existe com backup.
- **O rasto é `data/registos-faltas.csv`** (fora do Git, como o `vendas.csv`), e
  escreve-se ANTES da alocação: é a contrapartida de um botão que CRIA cartas.
- **Só no modo edição, e por duas razões.** No site publicado não há endpoint que
  grave (a razão de sempre) — e o selector é uma consulta ao catálogo por carta
  em falta. Aí morava uma armadilha de desempenho: o `lower(name) = lower(?)` do
  `scryfall` **não usa o índice `ix_cards_name`** e varria as ~500 mil impressões;
  o payload do modo edição demorava **10,7 s**, e ele corre a cada clique.
  Passou a tentar `name = ?` primeiro (1,2 s), com o `lower()` como recurso.
- **Medido na base de 2026-09-08:** a alocação não mexe (8 426,34 €, 232 a
  comprar, 70 a ir buscar, 345 a arrumar). Um check de 2 Meddling Mage no UW
  Replenish: 95 %→97 %, comprar 3→1, a caixa 4,42 €→1,10 €, fechar tudo
  8 426,34 €→8 423,02 €, venda igual — e a arrumação 345→**347**, porque uma
  linha INCOMPLETA vive em `missing` e o `movimentos_de_entrada` só percorre o
  `have`: as 2 cópias que ele já tinha dessa carta só aparecem no plano quando a
  linha fecha. Era um buraco anterior a isto e ficou por corrigir nesse dia (ver
  a secção a seguir, que o fecha). Ver `work/revisao/mtgvault-faltas-check.md`.

**4. «SE NÃO MARQUEI, É PORQUE NÃO A TENHO»: o botão «Não encontrei estas»
(André, 2026-09-09, à letra).** *"No mtgvault, se eu não seleccionar no deck que
meti a carta, com checkmark, é porque eu não a tenho e estás a fazer confusão.
Por exemplo, no Cloud cEDH, dizes que tenho Chromatic Star mas eu não tenho,
dizes que tenho Grinding Station, mas também não tenho."* As duas cópias estão na
base porque foram FOTOGRAFADAS há meses (`copies` 694 e 403, com `photo_path`,
balde `SPML`), não estão dentro de caixa nenhuma, e já não estão na estante. O
vault não tinha maneira nenhuma de saber isso: a caixa ficava eternamente a dizer
*"tens"* sobre uma carta que ele não encontra, e a lista de compras ficava a menos
duas cartas que ele precisa mesmo de comprar. Padrão do `event_tier` — nenhum
passo dá erro. É o **inverso** do *"já a tenho, está no deck"*: aquele cria uma
cópia, este tira uma de circulação. Motor em `loadout.marcar_nao_encontradas` /
`devolver_a_coleccao` / `nao_encontradas`, botão na barra fixa do painel *Montar*,
aba **🔍 Não encontradas** na Deckboxes.
- **O botão leva o que SOBROU por marcar** (`loadout.copias_por_encontrar`, a
  MESMA lista que desenhou as checkboxes e por que a barra conta) e só aparece
  enquanto há linhas por marcar. As linhas de **comprar** nunca entram — não têm
  cópia nenhuma na base, e é isso mesmo que ele quer dizer com *"não a tenho"*. O
  bloco «destinadas a outra caixa» também não: dá-las como perdidas a partir daqui
  era decidir pela caixa do lado. Um `copy_id` que o painel desta caixa não
  ofereceu é recusado.
- **Uma cópia não encontrada sai da colecção para TODOS os efeitos** — loadout,
  cobertura, venda, valor, sugestões, galeria — e a carta volta a ser **compra**,
  nesta caixa e nas outras que a pediam. **Nada é apagado**: a linha fica na base
  com a data e a caixa onde faltou, e o *«afinal encontrei»* põe tudo como estava
  (medido: os números voltam ao cêntimo).
- **A marca é uma COLUNA (`copies.nao_encontrada_em` + `nao_encontrada_slot`), não
  um `purpose` novo.** O CHECK do `purpose` só aceita `player`/`collector` e
  mudá-lo obrigava a reconstruir a `copies` inteira numa base já feita — e a cópia
  não deixa de ser 'player': ela é que não está lá.
- **O filtro escreve-se NUM SÍTIO SÓ: `collection.jogaveis()`** (= `purpose =
  'player' AND nao_encontrada_em IS NULL`), mais o `na_estante()` para as vistas
  que também mostram o colecionador (galeria, valor, Reserved List). Era
  `cp.purpose = 'player'` escrito à mão em **catorze** consultas; a primeira que
  se esquecesse da coluna nova voltava a dizer-lhe que tem a carta, sem um único
  erro. O `test_nao_encontrei.caso_o_filtro_vive_num_sitio_so` varre o código à
  procura do literal (só a `migracao` é excepção: uma cópia não encontrada
  continua a viver numa gaveta e muda de gaveta com todas — o que ela não faz é
  entrar na `copy_allocation`).
- **UM ÍNDICE SOBRE UMA COLUNA NOVA NÃO PODE VIVER NO `schema.sql`** (apanhado ao
  medir contra a cópia da base a sério). O ficheiro corre INTEIRO antes do
  `db._migrate()`, e numa base já criada a coluna ainda não existe: o
  `CREATE INDEX` rebentava o `db.init` com *"no such column"* — em todas as
  páginas e no `daily`. O `CREATE TABLE IF NOT EXISTS` é indiferente à ordem, um
  índice não é. Os testes não o apanhavam porque criam sempre bases de raiz. Tem
  caso próprio (`caso_a_base_do_andre_abre_na_mesma`, que apaga as colunas para
  reproduzir a base dele).
- **O lote parte-se.** Um lote de 4 com 1 já sleevado na caixa e 3 na gaveta são
  duas linhas do `lots()` com o mesmo `copies.id` — marcar a linha inteira tirava
  da caixa uma cópia que está lá dentro. Marca-se a quantidade do MOVIMENTO, e a
  linha nova herda tudo (a foto inclusive). Consequência a saber: se ele tiver 3
  cópias registadas de uma carta que a caixa pede 1 vez, marcar tira uma e a caixa
  passa a usar a seguinte — que aparece no painel na corrida a seguir.
- **A foto que chegue depois NÃO ressuscita a cópia** (`copias_por_confirmar`
  ignora as não encontradas): entra como cópia nova, que é o que a foto prova.
- **Rasto e backup**: `data/nao-encontradas.csv` (fora do Git, como o
  `vendas.csv`), escrito ANTES da base; backup em
  `backups/vault-<data>-nao-encontradas.db`, como o *Desmontar*. Marcar a mesma
  cópia duas vezes é um **no-op** — sem linha nova e sem backup.
- **A lista mostra a MINIATURA da foto de origem** (`/foto?copy=<id>` do modo
  edição, com token; o caminho sai da base e nunca do pedido). É a única forma de
  ele perceber se a carta existiu e se sumiu — sem ela a linha é um nome sem prova
  nenhuma. No site publicado a lista aparece na mesma, sem foto e sem botão.
- **Efeito medido na base de 2026-09-09:** a alocação **não mexe** — 8 426,34 €
  para fechar, 232 a comprar, 70 a ir buscar, 385 a arrumar, venda 230c/1 315,68 €
  + 40 RL/3 221,01 €, iguais antes e depois (a coluna nasce vazia). Marcar as duas
  cartas dele: Cloud cEDH 67 %→66 %, comprar 33→34, fechar tudo 8 426,34 €→
  8 426,51 €, arrumar 385→384 — e o *«afinal encontrei»* devolve os quatro números
  ao que eram. Ver `work/revisao/mtgvault-nao-encontrei.md`.

**AS CÓPIAS DE UMA LINHA INCOMPLETA TAMBÉM SE TIRAM DA GAVETA (2026-09-08).**
Uma linha que pede 4 e a que a alocação só deu 2 vive em `missing` — e **tudo**
o que percorria a alocação de uma caixa percorria só o `have`. As duas cópias
existiam, eram daquela caixa e estavam na gaveta, e não apareciam em lado
nenhum: nem no painel *Montar*, nem na aba *Arrumar*, nem no CSV, nem na
`copy_allocation` do *"já arrumei tudo"*. Ele montava a caixa, ficavam as duas
na prateleira, e a aba *Comprar* pedia as outras duas. Padrão do `event_tier`:
nenhum passo dá erro, e a folha que ele leva para a estante está a menos duas
cartas.
- **Quem responde é `loadout.linhas_alocadas(s)`** = `have` + as de `missing`
  **com lotes**. Era `for m in s["have"]` escrito em cinco sítios, e o primeiro
  que se esquecesse voltava a pôr a base e o painel a discordar. Já lêem de lá:
  `movimentos_de_entrada` (logo o painel *Montar*, a aba *Arrumar*, o CLI
  `arrumar`, o CSV e a barra «N de M»), `linhas_da_caixa` (o que se GRAVA — sem
  isso ele tirava-as da gaveta e o vault não as registava), o `origens` do
  *"tirar de:"*, o `copias_por_confirmar` e o `_de_outro_balde` do `colecao_cor`.
  O `webapp.marcar_na_caixa` tinha o `linhas_da_caixa` **reescrito à mão** e por
  isso ficava de fora: passou a chamá-lo (por isso deixou de ser `_privado`).
- **Uma linha em falta SEM nenhuma cópia continua a não entrar**: não há nada
  para tirar, é compra.
- **A linha diz porque é que vem a menos** — *«2 de 4 — 2 em Comprar»*,
  `loadout.nota_parcial`, com moldura âmbar (a mesma do *"está noutra caixa"*: a
  pergunta é a mesma — esta linha não fecha com o que está aqui). O texto é
  composto no Python e não no browser, pela razão de sempre: quem sabe partir a
  falta em *comprar* e *ir buscar* é a alocação (ver `e_foil`).
- **Efeito medido na base de 2026-09-08:** a alocação **não mexe** — 8 426,34 €
  para fechar, 232 a comprar, 70 a ir buscar, venda 230 cópias, iguais antes e
  depois. O que muda é a arrumação: **345 → 385** (+40 cópias, 202 → 226 linhas),
  que são as parciais a passarem a ter caixa. Por caixa (tirar, antes→depois):
  UW Replenish 59→66, Oath of Druids 36→49, Enchantress 17→23, Ill-Gotten Gains
  17→24, Elves/Survival 22→24, Modern — UW Oswald 49→50, Pioneer — Greasefang
  10→14. O «N de M» da barra sobe exactamente o mesmo. Relatório em
  `work/revisao/mtgvault-movimentos-incompletos.md`.

## Restrições externas (já testadas, não voltes a tentar)

| Fonte | Estado |
|---|---|
| mtgo.com | fonte primária, gratuita |
| mtgtop8 | acessível, tem export `.dec`; 1 pedido/s, limites baixos por respeito |
| Scryfall | bulk data, gratuito |
| **mtgdecks.net** | PÁGINAS abrem com `requests` + User-Agent de browser (a deteção reage ao UA, não ao IP) — `mtgvault/mtgdecks.py` tira daí o ÍNDICE de torneios (jogadores/peso/data/nome). MAS as CARTAS das listas são anti-scraped (JS/base64, export a 403): para as cartas usa-se o mtgtop8 (.dec) |
| **mtggoldfish** | acessível, mas é agregador — duplicaria dados. Termos proíbem reprodução |
| Moxfield | precisa de User-Agent autorizado pelo suporte; sem isso, 403 |
| Cardmarket | não se raspa; usa o price guide oficial. O cookie de sessão expira |
| CardTrader | API v2, token no perfil, 200 pedidos/10s |

## Superfícies ainda não validadas contra os sites reais

Foram escritas a partir da estrutura observada, mas nunca correram contra a
rede. Se algo vier vazio, é aqui:

1. `sources.fetch_mtgo_index` — a forma do URL do índice do mtgo.com.
   Tenta duas variantes; pode ser preciso uma terceira.
2. `sources.parse_mtgo_page` — o blob JSON embebido na página do evento.
3. `mtgtop8.harvest` — os parsers estão testados com fixtures reais, mas o
   ciclo completo nunca correu.
4. `prices.load_cardmarket_file` — aceita JSON e CSV; o formato exato do
   ficheiro não foi confirmado.
5. `prices.sync_cardtrader_map` — se o blueprint traz `scryfall_id` ou se é
   preciso cair para correspondência por nome.

## Por fazer

- Validar as cinco superfícies acima contra os sites reais e corrigir.
- **Abrir o porto 8771 na firewall privada** (o comando está acima e no arranque
  do `webapp.py`) — precisa de consola de Administrador, por isso não correu.
- **Correr a migração `migrar-coleccao-unica` na base a sério.** Está feita,
  testada e medida (é neutra nos números), mas ainda só correu em cópias.
- ~~Interface web local~~ — feita em 2026-09-07: `webapp.py`, porto **8771**,
  biblioteca-padrão (sem FastAPI, para não trazer uma dependência para uma coisa
  que são 200 linhas de `http.server`). Falta-lhe: ver fotos e gráficos de preço.
- Nomes de arquétipos: o clustering gera rótulos a partir das cartas mais
  distintivas (`Skewer the Critics / Sacred Foundry / ...`). Funciona mas é
  feio. Permitir renomear à mão sem que o `rebuild_archetypes` desfaça.
- Reconhecimento das cartas nas fotos. Hoje o fluxo é: o André manda as fotos
  ao Claude no chat, recebe linhas CSV, importa.

## Não fazer

- Não acrescentes agregadores de decklists (ver deduplicação acima).
- Não guardes imagens na base de dados. As fotos ficam no disco;
  `copies.photo_path` guarda o caminho.
- Não gravar preços de todas as cartas do mercado — só as de interesse
  (`prices.cards_of_interest`), e só quando o valor muda. O `vault.db` já NÃO
  vai para o Git (está no `.gitignore` desde 2026-08; vive no Release `data`,
  ver `scripts/`), mas continua a ter de ficar leve: é descarregado e
  republicado inteiro a cada execução.


**cEDH e Duel Commander Trials (Andre, 2026-09-07).** O cEDH nao tem metagame: os dois decks de cEDH dele seguem listas por link directo (watched), por isso `metagame_fontes.cedh.tiers = []` e o cEDH saiu de `MTGTOP8_FORMATS`/`ANALYSE_FORMATS` no `daily.py`. No Duel Commander contam tambem os `Duel Commander Trial` (tier `outro`), alem das ligas e dos presenciais sem minimo.

## Âmbito do metagame por formato (André, 2026-09-07)

Nem todos os formatos precisam de metagame. Palavras dele: *"Duel Commander: só
quero listas do comandante que tinha pedido (Cloud). Pauper também não precisa,
pois só sigo a lista Pauper do jogador específico (Luffy). Premodern: o deck de
Stiflenought não preciso de listas, sigo a lista do jogador específico (Luffy).
Preciso de consenso para lista de alguns decks de Premodern: Replenish,
Enchantress."*

Há três níveis, e cada um tem a sua chave no `colecao_config.json`:

**Atualização de 2026-09-07 (o metagame passou a ser "o que monto a seguir").**
Palavras dele: *"Para os decks 'metagame', em vez de me dares todas as listas,
dás-me só o top-3 decks que estou mais perto de concluir para os formatos
Standard, Pioneer, Legacy."* A coluna "tem página de metagame" abaixo continua a
valer para o **`cobertura.html`** (o top-10 ponderado). O **`metagame.html`**
deixou de a ler: as suas secções são `metagame.SECOES` — top-N em Standard,
Pioneer e **Legacy** (que não está em `formatos_metagame` e tinha de entrar), a
caixa escolhida em Modern, e os alvos de consenso em Premodern. O quanto é
`colecao_config.json → metagame_top_n` (3).

| | recolhe listas? | conta p/ metagame (`metagame_fontes`) | agrupa em arquétipos (`ANALYSE_FORMATS`) | tem página de metagame (`formatos_metagame`) |
|---|---|---|---|---|
| Standard/Pioneer/Modern | sim | sim | sim | **sim** |
| Legacy, Vintage | sim | sim | sim | não (Legacy fora desde 2026-08-31) |
| **Premodern** | sim | sim (441 Challenges) | sim | **não** — só o consenso dos alvos |
| **Duel Commander** | sim (para o Cloud) | sim | **não** | não |
| **Pauper** | só o Luffy | **não** (`tiers: []`) | **não** | não |
| cEDH | não (saiu do harvest) | não | não | não |

- **Pauper — `so_jogadores_vigiados` (a armadilha).** Tirar o Pauper do harvest
  parecia óbvio e **matava a vigilância do Luffy em silêncio**:
  `watchlist.check_mtgo_player` não vai à rede, lê a lista mais recente do
  jogador *das decklists que o harvest já guardou*. Sem harvest, a lista dele
  congelava no último snapshot e o `daily.py` continuava a dizer `[ok]` — o
  mesmo padrão do `event_tier`. Por isso o filtro está em
  `sources.store_decklist`: as páginas do evento continuam a ser lidas (é de lá
  que sai a lista do Luffy) mas **só se guarda a de quem está em `watched` com
  `kind='mtgo_player'` naquele formato**. As `manual` passam sempre. Para pôr
  outro formato neste regime basta acrescentá-lo a `so_jogadores_vigiados`.
- **Duel Commander.** Sai só de `ANALYSE_FORMATS` (o clustering e o
  `card_roles` do formato inteiro não serviam ninguém). O harvest FICA — o
  `commander_decks.tiers()` precisa das listas do comandante, e lê as
  `decklist_cards` directamente, nunca precisou dos `archetypes`. Confirmado
  antes/depois: Cloud = 167 listas, núcleo 44 · flex 43 · tech 30 na altura em
  que ficou escrito acima; na base de 2026-09-07, 167 listas, núcleo 40 · flex
  40 · tech 39, **igual antes e depois da mudança**.
- **Premodern — `formatos_metagame` + `premodern_arquetipos_alvo`.** Continua a
  recolher-se e a analisar-se (as listas são precisas para o consenso), mas saiu
  das páginas de metagame/cobertura/decks-fazíveis: `meta_coverage.FORMATS`
  passou a ser filtrado pelo config, e o `metagame.py`/`decks_faziveis.py` leem
  essa mesma lista (não têm cópia própria). Em vez do top-10, o
  `premodern_decks.py` calcula a lista de consenso dos arquétipos que ele pediu
  e grava-a em `decks`/`deck_cards` com o sufixo `" (consenso)"`; aparece no
  `deckboxes.html` com % e wantlist.
  - **O sufixo não é cosmética:** os alvos são decks POR MONTAR e **não podem**
    entrar em `decks_vigiados` — essa lista é a dos decks montados, e o
    `meta_coverage.owned_available` desconta-lhe as cartas à coleção
    disponível. Um alvo lá dentro fazia a coleção parecer mais pobre do que é.
  - **O clustering não separa estes dois arquétipos**: 96% das listas de
    Enchantress jogam Replenish. Por isso o agrupamento é por REGRA
    (`archetype_rules.json` → `premodern`), com o operador novo `none` (não pode
    ter nenhuma destas cartas) — é o equivalente do `"!"` do `my_decks`. Se
    mudares o nome de uma regra, muda também em `premodern_arquetipos_alvo`
    (o `test_ambito.py` tranca isso).
  - **O Stiflenought não é um alvo de propósito**: segue a lista do Luffy
    (`my_decks.FOLLOWED_PLAYERS` + `decks_vigiados`).
- **`stock.stock_from_lists`** é o mesmo cálculo da lista padrão do `stock_list`
  (partilham o `_slots`/`_fill`), mas a partir de decklists em memória — os
  alvos de Premodern não passam pelo clustering e por isso não têm linhas em
  `card_roles`.

**Nota sobre a amostra (2026-09-07).** O `daily.py` corre
`prune_decklists(con, 30)`: o `vault.db` só tem ~30 dias de listas. Não há
janela de 90 dias para comparar, nem tendência de mais de um mês — o histórico
longo vive no `card_roles`, por janela.
