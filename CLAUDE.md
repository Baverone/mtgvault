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
  `cd tests && for f in test_*.py; do python "$f"; done`
- **Não inventes dados.** Se não conseguires aceder a uma fonte, diz que não
  conseguiste. Nunca preenchas uma decklist ou um preço a partir de memória.
- Comentários explicam *porquê*, não *o quê*. Vários dos comentários atuais
  existem para registar decisões que custaram a descobrir — não os apagues.

## Arquitetura

```
mtgvault/
  db.py           ligação, ATTACH do catálogo, migrações
  schema.sql      vault.db (coleção, decks, decklists, preços, watchlist)
  catalog_schema.sql   catalog.db (só a tabela cards)
  scryfall.py     catálogo via bulk data
  collection.py   exemplares, sub-coleções, reservas, valor, movimentos
  wantlist.py     o que falta, para decks e para arquétipos
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
meta_coverage.py    cobertura.html — top-10 ponderado + staples + emergentes. NB (2026-09-07): quem decide que listas contam é `sources.lista_conta`/`counting_sql` (ver "Que listas contam"), e o peso vem de `sources.tier_weight_sql`; janela 30 dias; expõe COLLECTION_BALDES={"SPML","Premodern (geral)"}, owned_available(con) (=coleção MENOS cartas comprometidas com decks vigiados) e counting_lists(con,fmt,aid) — a base de "tenho" do metagame/decksfaziveis/cobertura
decks_faziveis.py   decksfaziveis.html — "Decks fazíveis": por formato, decks do top-10 já a ≥ min% (colecao_config.json→decks_faziveis_min_pct, default 50). Cor=tenho/cinza=falta + wantlist. Reusa metagame._grid e meta_coverage._rank/owned_available
buildability.py     (DORMENTE) o "Montar" foi tirado do menu p/ o André refazer; já NÃO corre no daily nem vai ao git-add. Continua importado por meusdecks.py (FMT_LABEL/FMT_ORDER/BASICS)
classify.py         classificação Deck/Coleção/Vender (alimenta colecao_cor.html)
colecao_cor.py      colecao_cor.html — "Binders": coleção INTEIRA por cor→CMC; cartas em uso a escuro + rótulo (classify rep["deck"]/used_by); + secção "Decks vigiados" (Blue Farm/Cloud cEDH/Cloud/Pauper): o deck por inteiro + cartas "extra" que saíram da lista (retidas até 6 meses da última utilização — `_watched_deck_pools`)
collection_gallery.py  colecao.html — galeria por sub-coleção
core_decks.py       (coredecks.html APAGADO 2026-08-26, a redefinir; NÃO vai ao git-add) — mas core_decks.py continua a correr no daily p/ calcular card_price/posse
alertas.py          alertas.html — vender/comprar por movimento de preço (fora do menu atual)
meusdecks.py        meusdecks.html — "Decks vigiados": agora SÓ os 5 fixos de colecao_config.json→decks_vigiados (Pauper-Luffy, Premodern-Luffy/Stiflenought, Blue Farm, Cloud cEDH, Cloud Duel Commander — este ÚLTIMO agora INCLUÍDO). Lista 75 verde/vermelho, % e evolução; checkmark "atualizado" (localStorage)
metagame.py         metagame.html — "Metagame" (página principal): top-10 por formato (só Challenges/Showcases, 30 dias), cartas a cor=tenho / cinza=falta, wantlist por deck, e "Staples que faltam" por formato ordenadas por preço. Usa meta_coverage.owned_available
(prioridade.py + metafaltas.py APAGADOS 2026-08-26, a redefinir)
reservedlist.py     reservedlist.html — Reserved List (Scryfall) x coleção, por edição, preço/evolução, e 'VENDER' as que não jogam em formato nenhum
caixarl.py          caixarl.html — "Caixa Reserved List": a RL que está fora da coleção jogável
showcase.py         showcase.html — "Decks Showcase Challenger": eventos competitivos recentes (MTGO + presenciais do mtgtop8) agrupados por arquétipo. Tinha filtro e pesos PRÓPRIOS (fonte + showcase_min_players + lista de nomes casuais) — era por isso que continuava a dar listas enquanto o metagame vinha vazio. Desde 2026-09-07 usa `sources.counting_sql`/`tier_weight` como toda a gente; a chave `showcase_min_players` do config deixou de existir
my_decks.py         segue decks-alvo (por assinatura e por jogador de MTGO) -> tabela decks
commander_decks.py  decks de comandante por consenso EM CAMADAS: núcleo>=50% (=deck, deck_cards) / flex 25-50% / tech 15-25%; FILTRA pela cor do comandante. `tiers()` reusado pelo colecao_cor
refresh_collection.py  collection_owned p/ o index.html
colecao_config.json    config: spml_formatos, premodern_decks_completos, banimentos_manuais, regras_colecao, metagame_fontes
```
Cada `.html` gerado tem de estar na lista do `git add` do workflow (`daily.yml`,
passo "Guardar HTML") e, se for página nova, com link no `index.html`.

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

**Classificação Deck / Coleção / Vender (`classify.py`, 2026-08-13).** É a
regra do André já implementada, que alimenta a página `colecao_cor.html`:
- **Só os baldes `SPML` e `Premodern (geral)` são coleção.** Todo o resto
  (`Blue Farm`, `Cloud`, `Cloud cEDH`, `Pauper Affinity`) são decks montados →
  ficam FORA da coleção. (Palavras dele: "só premodern e SPML são coleções, o
  resto é tudo decks".)
- Dentro desses dois baldes, cada carta é **Deck** (cópias que um deck pede),
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
`meusdecks` (secção dos vigiados + a lista de nomes) juntam-se por ela. Atenção:
tal como `deck_meta` (lida pelo `webapp.py`), a tabela não está no `schema.sql`
nem no `db._migrate()` — só existe no `vault.db`, por isso numa base nova estas
páginas rebentam. Ver o relatório de revisão de 2026-09-06.

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
  `my_decks`, `meusdecks._cloud_consensus`, `commander_decks._inclusion`,
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
- Interface web local (FastAPI + uma página) para ver coleção, fotos e
  gráficos de preço no browser. É o passo que também justifica migrar do
  GitHub Actions para um VPS.
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
