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
  site_shell.py   A CASCA DE TODO O SITE (2026-09-24): a paleta (`TEMA`), os
                  tipos de letra, os ÍCONES (`_SVG`/`icone`/`js_icones` — um
                  conjunto só, partilhado com o JavaScript da Deckboxes), a
                  BARRA LATERAL agrupada em secções
                  (`SECCOES`), o cabeçalho com migalhas e o rodapé —
                  `head()`/`abrir()`/`fechar()`. Uma secção nova é uma linha
                  numa lista. Ver «Uma casca só para o site inteiro»
  paginas.py      os ajudantes que as páginas partilham e NÃO são casca (cor,
                  tipo, posse total, faltas, euros em português) + os DADOS À
                  PARTE. O `TEMA`/`META` reencaminham para o `site_shell`
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
  encomendas.py   o que ele COMPROU e ainda não fotografou (2026-09-19): a
                  tabela `encomendas`, o `+`/`−`/«Chegou»/«desfazer», o
                  DESCONTO no «a comprar» das caixas e a CONCILIAÇÃO pela foto
                  (chamada pelo `collection.import_csv`) — «só a foto cria
                  cópias»
  revalidacao.py  a REVALIDAÇÃO POR FOTO de toda a colecção (2026-09-20): a
                  campanha (`revalidacao.desde`), o ALVO (a caixa que ele está
                  a fotografar), o passo (0) da conciliação (a foto nova liga-se
                  à cópia por revalidar; a discrepância corrige a cópia da
                  caixa, `data/revalidacao.log`), o progresso da aba «📷
                  Revalidação» e a secção do `pendentes/esperadas.md`
  padrao.py       a LISTA PADRÃO e a RESERVA por caixa (2026-09-20): a lista
                  fixa (com data e origem) em `listas_escolhidas[slot]` +
                  `padrao: true`, que o daily nunca pisa, e `caixas[].reserva`
                  — as cartas «que poderão entrar», que nunca vão à venda
                  (saída `guardar`, «reserva da caixa X»). Só config; CLI
                  `padrao`/`reserva`, endpoint `/api/padrao`
  feira.py        A FEIRA (2026-09-20): o que LEVAR como moeda de troca (a
                  venda, com Trend, 📷 e duas taxas de banca — estimativas
                  dele) contra o que TRAZER (o «a comprar» das caixas + a
                  wantlist manual + os vendors), o saldo e as listas p/ o
                  telemóvel. Só config (`feira`); CLI `feira`, `/api/feira`
  fotocaixa.py    A FOTO DA DECKBOX FÍSICA de cada caixa (2026-09-21): o
                  original em `data/deckboxes/<slot>.<ext>` (fora do Git, a
                  anterior em `anteriores/`), a reduzida em
                  `assets/deckboxes/<slot>.jpg` (NO Git — a excepção ao «não
                  guardar imagens»), a data em `caixas[].foto`. Entra pelo
                  `POST /api/foto-caixa` (8771) ou por
                  `pendentes/deckboxes/<slot>.jpg` (daily/8771 recolhem). Ponto 13
  fotosite.py     AS FOTOS DAS CARTAS TIRADAS DO SITE, no telemóvel (2026-09-21):
                  a câmara a partir da Deckboxes (8771), `POST /api/foto`
                  (multipart, várias), a foto INTEIRA na RAIZ de `pendentes/`
                  com o nome a dizer a origem (`site-<slot>-<data>-<n>[-c<copy_id>]
                  .jpg`, `site-venda-/rl-/colecao-`), que o `import_csv` prefere
                  (`revalidacao.alvo_da_foto`); o «⚡ Processar agora» = uma
                  ordem `command` na inbox do runner do ai-pc (`mtg-fotos-novas`,
                  `nao_antes` = foto + 2 min, uma por 5 min); as fotos por
                  resolver (`recat-*-resultado.csv`). Ponto 14
  venda.py        a SAÍDA da lista de venda (2026-09-18): o CSV de stock p/ o
                  Cardmarket (formato predefinido NÃO confirmado, ou aprendido
                  de `data/cardmarket-stock-exemplo.csv`), a lista da estante
                  por onde a cópia está, e o que fica de fora com o porquê
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
  precos.py       O MODO DE PREÇO (2026-09-25): `market` (o que o mercado pede)
                  / `best` (a oferta mais barata) / `media`, em
                  `colecao_config.json → precos`. `sql()` é a EXPRESSÃO do preço
                  num sítio só (era `MIN(p.trend)` em oito consultas), `fonte()`
                  a fonte fixa, `modo_desde` o carimbo que trava a regra da RL, e
                  as RECEITAS (`unico`/`cm-guide`/`ct-ofertas`) dizem como é que
                  cada linha de preço foi produzida — é o que impede comparar
                  duas escalas diferentes. Ver «O PREÇO TEM TRÊS MODOS»
  prices.py       Scryfall bulk (grátis) + Cardmarket (ficheiro) + CardTrader (API,
                  agora com OS DOIS valores: `low` = melhor oferta, `trend` =
                  mediana das ofertas utilizáveis)
  cli.py          interface de linha de comandos
daily.py          o job diário (encadeia tudo o que está abaixo)
.github/workflows/daily.yml
```

**Geradores do site (scripts na raiz, corridos pelo `daily.py`, HTML no GitHub Pages):**
```
inicio.py           index.html — o INÍCIO (2026-09-24): o painel com os números de hoje (decks montados/por montar, o que falta comprar aos permanentes, cartas e valor da coleção, venda, arrumação, «fechar tudo», encomendas e revalidação), os atalhos e as «últimas atualizações dos dados». Corre por ÚLTIMO e com o MESMO `loadout.report` do `deckboxes` — dois relatórios eram duas respostas à mesma pergunta na porta de entrada do site. O valor da coleção e o número de cartas saem os DOIS da `collection.valor_da_coleccao` — a conta única (2026-09-24); a primeira versão tinha consulta própria e dava 97 761,26 € contra os 97 772,93 € da outra página. Era um HTML estático escrito à mão. Ver «Uma casca só para o site inteiro» e «O VALOR DE UMA CÓPIA É UMA CONTA SÓ»
meta_coverage.py    cobertura.html — top-10 ponderado + staples + emergentes. NB (2026-09-07): quem decide que listas contam é `sources.lista_conta`/`counting_sql` (ver "Que listas contam"), e o peso vem de `sources.tier_weight_sql`; janela 30 dias; expõe COLLECTION_BALDES={"SPML","Premodern (geral)"}, owned_available(con) (=coleção MENOS cartas comprometidas com decks vigiados) e counting_lists(con,fmt,aid). NB (2026-09-07): `FORMATS` deixou de ser fixo — filtra `_FORMATS` por `colecao_config.json`→`formatos_metagame` (hoje standard/pioneer/modern; o Premodern saiu). Só a COBERTURA lê essa lista: o `metagame.py` deixou de a ler (ver abaixo)
decks_faziveis.py   RETIRADO 2026-09-07 — fundido no `metagame.py`, que faz a mesma pergunta com as regras de material e o "onde está a carta". O módulo ficou como lápide (levanta RuntimeError), o `decksfaziveis.html` reencaminha para o metagame, saiu do `daily.py` e do `git add` do workflow. Podem ser apagados os dois
buildability.py     APAGADO 2026-09-15 (decisão do André), com o `buildability.html`. Era o "Montar" (dormente desde a v6: fora do menu, fora do daily, sem um único import). O que respondia — que deck montar a seguir e o que lhe falta — passou para o **Metagame** (`metagame.py`, o top-N mais perto de fechar) e para a aba de cada caixa da Deckboxes. O `test_paginas.caso_as_paginas_orfas_foram_mesmo_apagadas` tranca que não voltam nem ficam referidas
classify.py         classificação Deck/Coleção/Vender (alimenta colecao_cor.html)
colecao_cor.py      colecao_cor.html — "Binders": coleção INTEIRA por cor→CMC; cartas em uso a escuro + rótulo (classify rep["deck"]/used_by); + secção "Decks vigiados" (Blue Farm/Cloud cEDH/Cloud/Pauper): o deck por inteiro + cartas "extra" que saíram da lista (guardadas SEM PRAZO desde 2026-09-15 — `_watched_deck_pools`; era "até 6 meses da última utilização"). NB (2026-09-07): `_de_outro_balde` acrescenta as cartas que o LOADOUT dá a essa caixa mas que estão arrumadas noutro balde, marcadas "de &lt;balde&gt;" (era aqui que os Utrom Monitor do SPML desapareciam do Pauper)
collection_gallery.py  colecao.html — galeria por sub-coleção
core_decks.py       (coredecks.html APAGADO 2026-08-26, a redefinir; NÃO vai ao git-add) — mas core_decks.py continua a correr no daily p/ calcular card_price/posse
alertas.py          alertas.html — vender/comprar por movimento de preço (fora do menu atual)
meusdecks.py        FUNDIDO NO deckboxes.py (2026-09-08, v6) — a "Decks permanentes" fazia a MESMA pergunta ("quanto tenho deste deck?") e respondia outro número, porque contava a colecção inteira por deck em vez da alocação. Saiu do MENU e do `index.html`; o módulo continua a correr no daily mas só escreve um REENCAMINHAMENTO (`deckboxes.redireccionamento`), porque o link vive no telemóvel dele e no site publicado. O que ela tinha e a Deckboxes não tinha passou para a aba da caixa: lista por TIPO, imagens grandes, "copiar a lista" e "quantas tenho na colecção inteira" (informação secundária). Os ajudantes que outras páginas usavam (`_type_map`, `_group_by_type`, `_faltas`, `_faltas_html`, `_art`) estão agora em `mtgvault/paginas.py` — o `showcase.py` lê-os de lá
deckboxes.py        deckboxes.html — "Deckboxes": o LOADOUT (colecao_config.json→loadout), os decks montados ao mesmo tempo com a coleção REPARTIDA entre eles (uma cópia física serve uma caixa só). NB (2026-09-07): a página foi reescrita com **uma ABA POR DECK** (o pedido dele: *"faz como no riftvault — no botão, cada deck tem uma aba própria"*), mais as abas **Todas**, **✅ Decks montados** / **🔧 Decks para montar** (2026-09-08, ver a secção própria), **Arrumar**, **Partilhadas**, **Comprar**, **Vender** e — desde 2026-09-08 — **Sugestões** (as caixas candidatas de Premodern; só existe se houver caixas desse formato). Os dados vão em JSON dentro do HTML (`<script id="dados">`) e o render é JavaScript — o MESMO ficheiro serve o site publicado (`editable:false`) e o modo edição do `webapp.py` (`editable:true`, com botões). Por caixa: barra, dois números ("faltam comprar" e "ir buscar a outra caixa"), grelha de cartas com três estados, "tirar de:" (`slot["origens"]`), substitutos, wantlist Cardmarket (SÓ o que é mesmo compra). Na aba **Comprar**, cada linha diz para que caixa é a compra (`para`) e em que material (`loadout.requisito_material`), há selector por caixa (o "copiar" copia só o filtro activo) e as cartas ≥100 €/cópia levam chip «cara» e total à parte — Mishra's Workshop sozinha vale mais do que o resto da lista. Motor em mtgvault/loadout.py
webapp.py           MODO EDIÇÃO local, **porto 8771** (o 8770 é do `riftvault serve` — não trocar). Serve o `deckboxes.html`/`metagame.html` com os botões: painel *Montar* (*Sleevado e na caixa*), *Já arrumei tudo*, *Actualizei*, *Vendida*, *Tornar permanente*, *Subir/Descer* e *Vou montar este*. As PREFERÊNCIAS vão para o `colecao_config.json` (as `caixas` vão no Git); o que é FÍSICO vai para a `copy_allocation` e, na venda, sai da `copies` + `data/vendas.csv`. NB (2026-09-08): **ouve em `MTGVAULT_BIND`, por omissão `127.0.0.1`** (a tarefa `mtgvault-serve` põe `0.0.0.0` para o telemóvel), e as ESCRITAS exigem o token de `data/webapp.token` — ver "O telemóvel e o token". Mantido de pé pela tarefa `ai-pc/tasks/mtgvault-serve` (verifica de 5 em 5 min, relança destacado)
metagame.py         metagame.html — "Metagame": desde 2026-09-07 já NÃO é o top-10 de cada formato; é o **top-N que ele está mais perto de concluir** (`colecao_config.json`→`metagame_top_n`, default 3). `SECOES` decide o modo por formato: `top` (Standard/Pioneer/Legacy — as caixas do loadout por escolher, via `loadout.foil_report`), `caixas` (Modern — o deck já escolhido, do próprio loadout) e `premodern` (o ranking de sugestões — top-10 de representação + top-5 combo, cobertura **como principal** + a do que sobra ao lado, e os botões «vou montar este» / «não quero este»; era `alvos`, só o `premodern_arquetipos_alvo`, até 2026-09-08). Posse pela alocação do loadout, três estados, wantlist Cardmarket. NÃO lê `formatos_metagame` (o Legacy tinha de entrar e não está lá). NB (2026-09-21): `colecao_config.json → formatos_decididos` (hoje `["pioneer"]`) passa um formato de `top` a `caixas` — `metagame.secoes()` é o modo efectivo, `formatos_top()` lê de lá (e a Deckboxes e o `/api/escolher` também); ver o ponto 12
_reiniciar_webapp.py  mata o `webapp.py` que OUVE no 8771 (por porto, nunca por nome de processo — o 8770 é do riftvault e o 8773 do Treinador) para a tarefa `mtgvault-serve` o relançar com o código novo. É o único caminho na allowlist do Claude local (`taskkill`/`netstat` não estão lá). Tem teste (`test_reiniciar_webapp.py`, com um trecho real de `netstat -ano`)
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

**AS PÁGINAS PESADAS TÊM OS DADOS À PARTE (André, 2026-09-15).** *"As páginas
pesadas passam a ter os dados à parte, carregados a pedido. Abdico de as abrir
offline a partir do disco; têm é de funcionar bem servidas por HTTP — no GitHub
Pages e no modo edição, que abro do telemóvel pela rede de casa."* Medido nesse
dia: `showcase.html` **1 266 KB** (4 319 `<img>`), `deckboxes.html` **694 KB**
(668 KB eram o JSON dentro do `<script id="dados">`), `reservedlist.html`
**459 KB**, `cobertura.html` **274 KB**. Depois: **12 / 150 / 14 / 27 KB**.
- **O HTML é a CASCA** (menu, separadores, CSS, JS) e os dados vivem em
  `data/paginas/<pagina>.json` (o índice) + `data/paginas/<pagina>/<parte>.json`
  (cada secção, ida buscar quando ele a abre). Quem escreve é
  `paginas.escrever_dados` (atómico, apaga as partes que deixaram de existir,
  põe `_gerado_em`); quem lê é o `paginas.JS_DADOS`, o mesmo em todas — e **um
  `fetch` que falha diz-lho em português** (`erroDados`), nunca um ecrã vazio.
- **Deckboxes**: o índice leva o resumo, a fila de abas e cada caixa SEM as
  listas (`deckboxes.CAIXA_PESADO`; o `montar` fica só com os números do crachá
  «N de M»); uma parte por caixa (`caixa-<slot>`) e uma por aba pesada
  (`arrumar`, `venda`, `compras` = compras+partilhadas+básicas, `premodern`).
  `partir`/`juntar` são inversos e há teste. **O `html_page` continua a
  embutir tudo** — é o que os testes e o `render_deckboxes.js` lêem, e o JS
  detecta o `script#dados` e não faz um único `fetch` nesse caso.
- **Showcase**: um JSON por formato com o cabeçalho de cada arquétipo; o corpo
  (a grelha) num ficheiro por arquétipo, ido buscar no `toggle` do `<details>`
  — só o primeiro (aberto) vai dentro do JSON do formato. As `<img>` levam
  `decoding="async"` e `width`/`height`. **Reserved List**: uma parte por
  edição, carregada quando a secção se aproxima do ecrã (IntersectionObserver;
  sem ele, todas por ordem). **Cobertura**: uma parte por formato + `prints` e
  `want` (o selector de edições aplica-se quando chegam).
- **O `webapp.py` deixou de gerar a Deckboxes a cada pedido.** Um `GET /`
  demorava **4,4–5 s** do PC (>10 s do telemóvel, ligação em CLOSE_WAIT): corria
  o `loadout.report` inteiro por pedido, e a sonda da `mtgvault-serve` fazia-o
  de 5 em 5 min. Agora `/` e `/deckboxes.html` servem a casca (**0,02 s**) e os
  dados saem de `/data/paginas/deckboxes.json` + partes, calculados **uma vez**
  e guardados em memória até a base, o config ou o `arquetipos.json` mudarem
  (`webapp.em_cache`/`_versao`; um POST limpa tudo). O `?t=` desse pedido é o
  que decide se o índice leva os botões e o token. O `metagame.html` fica na
  mesma cache (1,6 s → 0,5 s na primeira, 0 depois). **Os outros `.json` só se
  servem de `data/paginas/`** — o resto de `data/` é a base e o token.
- **A pasta vai no `git add` do `daily.yml` e no `EXTRA_COMMIT` da tarefa
  `mtgvault-daily`** (é uma pasta: o `git add` leva o que lá estiver), e o
  `.gitignore` não a apanha. Sem ela no commit, o site publicado abre e diz *"não
  consegui carregar os dados"* — que é exactamente o que o teste de ponta a
  ponta (`test_paginas_leves.py` + `tests/abrir_pagina.js`, que serve a pasta
  por HTTP e corre o JS com `fetch` a sério) tranca.

**O JAVASCRIPT DA DECKBOXES ESTÁ À PARTE, E A PÁGINA FOI AFINADA PARA O TELEMÓVEL
(2026-09-18).** O uso real é o André à frente da estante, com o telemóvel, no
modo edição — e a casca tinha **150 KB, 123 deles JavaScript**, baixados outra
vez a cada toque no menu (o `webapp.py` serve tudo com `no-store`). Auditoria e
medidas em `ai-pc/work/revisao/mtgvault-telemovel-0918.md`; testes em
`test_telemovel.py` (13 casos) e o harness `tests/avaliar_js.js`, que corre um
script do teste DENTRO do contexto da página (é assim que se testa o que não
desenha HTML: a procura, o `gravar`, o `recarregar`, o «vendida»).
- **`deckboxes.js`** é o texto de `deckboxes.JS` (+ `paginas.JS_DADOS`), escrito
  pelo `build` ao lado da página e apontado pela casca com **um hash do conteúdo
  no `?v=`** (`js_versao`) — cacheável `immutable`, e muda de URL quando muda de
  texto. Casca medida na base dele: **150 375 → 32 377 bytes**. O **`webapp.py`
  serve-o DA MEMÓRIA** (`/deckboxes.js`, `cache=` só com `?v=`), nunca do disco:
  o ficheiro em `ROOT` pode ser de uma corrida antiga do `daily`, e servi-lo era
  dar ao telemóvel um `.js` velho com um URL novo, guardado para sempre. O
  `html_page` **continua a embutir** o mesmo texto (é o que os testes lêem de
  um ficheiro solto); os dois harness de node seguem `<script src>` na mesma.
  **Vai no `git add` do `daily.yml` e no `EXTRA_COMMIT` da tarefa
  `mtgvault-daily`** — sem ele no commit o site abre a casca e não desenha nada
  (o `test_paginas_leves` de ponta a ponta apanha-o: o `abrir_pagina.js` vai
  buscar o `.js` ao servidor).
- **Procura na aba da caixa** (`#procura`, barra `sticky` com os atalhos «⬇
  Montar / ⬇ Comprar»): filtra o que está desenhado por `data-nm` — grelha,
  passo 1, básicas, compras — sem `render()`, sem acentos, sem maiúsculas, sem
  apóstrofos e por palavras em qualquer ordem (`normProcura`/`casaProcura`).
  **Só compara o nome oracle, em inglês**: o nome impresso em português não está
  no catálogo (o Scryfall só o traz no bulk `all_cards`, que o vault não
  descarrega). Existe também na página publicada — só lê.
- **Toque numa miniatura = o `title`** num toast de 5 s (`tocarCarta`): no
  telemóvel não há hover, e "tens 2/4 · em UW Replenish" não existia lá.
- **«vendida» em DOIS toques** (`armar`): o primeiro escreve no botão «✓ vender
  1× Lotus Petal?», o segundo grava; desarma-se em 5 s. Era um `confirm()` num
  botão de 22 px, numa coluna de 246. O «limpar» da barra pergunta. **O «Limpar
  os vistos» do Arrumar fazia `P.feitos = {}`** — apagava as marcas do passo 1
  de todas as caixas; agora só limpa as da arrumação (`limparVistosArrumar`).
- **Rede**: `gravar()` tem prazo (25 s) e, sem resposta, diz **em português**
  que *"não sei se gravou"* (era `Failed to fetch` num toast de 2,6 s; os erros
  duram 7 s, `erro()`). **`recarregar()` substituiu o `location.reload()`**
  depois de cada escrita: vai buscar o índice de novo e redesenha no mesmo
  sítio; se a rede falhar aí, diz e a página fica. Com o payload embutido
  (testes) continua a ser `reload`.
- **CSS a 640 px**: `.btn/.cpbtn/.seg button` ≥ 40 px, `.btn.sm` ≥ 36 (eram 22),
  `.mv` ≥ 44, o nome da carta a partir linha em vez de «Swords to Plow…», a aba
  Plano em duas linhas, `.mvs` sem scroll próprio, `[hidden]{display:none
  !important}` (senão um `.mv` em `display:flex` não se escondia).
- **O motor não mexeu**: medido na base de 2026-09-18, fechar tudo 7 057,57 €,
  199 a comprar, 53 a ir buscar, 185 a arrumar, venda 246c/1 499,70 € + 58 RL/
  3 702,99 € — iguais.

**UMA CASCA SÓ PARA O SITE INTEIRO (André, 2026-09-24, à letra).** *"no
mtgvault quero uma organização diferente, acho tudo muito confuso, ter que andar
a correr os botões para os lados. Faz toda uma reestruturação para um site
profissional, bem organizado, bem estruturado!"* Substitui a decisão de
2026-09-07 (*"o menu e a paleta vivem num sítio só: `mtgvault/paginas.py`"*),
que estava certa e era pequena de mais: partilhava-se a LISTA do menu e as
CORES, mas não a estrutura — cada gerador escrevia o seu `<header>`, a sua
`.wrap` e o seu `body{}`, e cada página tinha a sua própria barra de
separadores. Motor em `mtgvault/site_shell.py`; inventário e mapa antigo → novo
em `ai-pc/Claude outputs/reestruturacao/mapa.md`, relatório em `RESUMO.md`;
testes em `tests/test_casca.py` (7 casos) e o medidor `tests/medir_layout.py` +
`medir_layout.js`.
- **O que estava mal, medido**: SEIS barras de navegação diferentes
  (`nav.tabs`, `.decktabs`, `.ftabs`, `.subnav`, `.filter`, as `.tabs` da
  Galeria), a da Deckboxes com **`overflow-x:auto` e até 27 botões** — a
  390 px viam-se 2; SETE larguras de `.wrap` (1000 a 1180 px), por isso o
  conteúdo mudava de sítio ao passar de página; a Galeria em tema CLARO e todas
  as outras escuras; e o `index.html` sem um único número da coleção.
- **A casca**: barra lateral fixa à esquerda (≥ 900 px) agrupada em cinco
  secções — **Início · Decks · Coleção · Metagame · Compras e venda**, a
  arquitetura que ele pediu — e, no telemóvel, a MESMA `<aside>` num painel que
  abre pelo botão ☰ (não há duas listas: é CSS a movê-la). À direita, o
  cabeçalho da página com migalhas *«Início › Secção › Página»*, título,
  subtítulo e a área de ações. Uma secção nova é **uma linha** no
  `site_shell.SECCOES`.
- **A ORDEM DO CSS é `TEMA → CSS da página → CSS da casca`** (`shell.head`).
  Ao contrário, o `.tabs a.cur` de cada página pintava por cima da barra
  lateral. Tem teste.
- **A paleta é a do baverone.com** (valores dele): fundo `#07080d`, painéis
  `#0e1018`/`#12151f`, texto `#eef0f6`, destaque **dourado `#f5c451`**; Space
  Grotesk nos títulos e Inter no texto, via Google Fonts com pilha de sistema
  por trás (sem rede, a página lê-se na mesma). **O `--accent` passou a ser o
  dourado**; o azul que ele era continua em `--info`/`--ob`/`--pt`, porque nesta
  página o azul QUER DIZER uma coisa — *"a carta está noutra caixa"* — e dar-lhe
  a cor da marca punha dois significados na mesma cor. Quem escreve por cima do
  dourado usa `--accent-ink` (escuro): branco sobre `#f5c451` é 1,9:1.
- **As sub-vistas passaram a ter URL.** A Deckboxes lê o `location.hash` e abre
  a aba certa (`abaDoHash`; o `ir()` escreve-o com `replaceState`), e é isso que
  torna possível a secção *Compras e venda* da barra lateral apontar para dentro
  da página — `deckboxes.html#comprar`, `#vender`, `#encomendas`, `#feira`,
  `#revalidacao` — sem duplicar página nenhuma. O Showcase faz o mesmo com o
  formato. **O `webapp.com_token` teve de aprender a âncora**: o `?t=` entra
  ANTES do `#` (`deckboxes.html#comprar?t=…` fazia o browser ler o token como
  parte da âncora e o servidor nunca o via).
- **A fila de abas da Deckboxes é agora um ÍNDICE VERTICAL** (`.vidx`), à
  esquerda do conteúdo; no telemóvel vira um `<select>` com os mesmos grupos
  (`<optgroup>`), que abre a lista inteira de uma vez. As duas saem da MESMA
  lista (`_filaDeAbas`). As setas do teclado passaram a ↑/↓. **Na 2.ª passagem
  do mesmo dia ficou só com as CAIXAS** — ver a secção a seguir.
- **Os números do dia são CHIPS** no cabeçalho, não uma frase de cinco linhas, e
  cada um leva à vista que o explica.
- **`index.html` deixou de ser estático**: é o `inicio.py`, o painel com os
  números de hoje. A decisão de 2026-09-09 (*"gerá-lo por código era trazer um
  gerador novo para a porta de entrada"*) caiu porque ele pediu números — e um
  número escrito à mão numa página estática é a definição de um número que vai
  ficar errado. Foi para o `git add` do `daily.yml` e para o `HTML` da tarefa
  `mtgvault-daily`; o `test_paginas.caso_o_indice_tem_o_mesmo_menu_que_o_paginas`
  deu lugar ao `caso_todas_as_paginas_geradas_levam_a_barra_lateral`, que
  verifica o HTML publicado das nove.
- **A Galeria passou ao tema partilhado.** Era a única clara, e por isso
  escapava ao teste do tema: usava `--add`/`--rem` sem os definir.
- **Nada de funcionalidade se perdeu.** As ações do modo edição são as mesmas,
  com os mesmos `data-*` e os mesmos endpoints; os dados continuam à parte
  (decisão de 15/09); as tiles com imagem (20/09) ficam. Medido na base de
  2026-09-24, com o mesmo `vault.db`: fechar tudo **7 017,06 €**, 239 a comprar,
  225 a arrumar, venda 268c/1 555,06 € + 68 RL/3 941,08 €, 5 montados e 10 por
  montar — **iguais antes e depois**.
- **O que se mede, mede-se num browser a sério.** `tests/medir_layout.py` serve
  o site, abre-o num Chrome headless por CDP e mede, a 1440 e a 390 px: o
  `scrollWidth` do corpo (e QUEM o excede), os alvos de toque abaixo de 36 px,
  os links internos partidos e as páginas que ficaram vazias. **O
  `chrome --headless --screenshot --window-size=390,…` não serve**: no Windows
  a janela tem largura mínima (~500 px) e o flag é ignorado em silêncio — a
  captura saía com 390 px de uma página desenhada a 500 e parecia haver scroll
  horizontal que não existia.
- **A casca cresceu 17 KB por página** (46 692 → 64 045 bytes na Deckboxes): o
  CSS do layout (11 KB), a barra (3,5 KB) e o JavaScript do menu (2 KB). O tecto
  do `test_telemovel` subiu de 60 para 70 KB. O JavaScript continua fora e
  cacheável (`deckboxes.js`, 243 KB), que é o que aquele tecto defende. Se
  voltar a subir, o passo seguinte é tirar o CSS partilhado para um `.css` com
  hash no `?v=` — com o custo de mais um ficheiro nas duas listas de `git add` e
  o site inteiro sem estilo se faltar lá.

**A 2.ª PASSAGEM, depois de ele rever as capturas (2026-09-24, mesmo dia).**
Ordem em `ai-pc/work/mtg-reestruturar-2.md`; relatório e medições na secção
«2.ª passagem» de `ai-pc/Claude outputs/reestruturacao/RESUMO.md`; capturas em
`capturas/depois-2/`; cinco casos novos em `tests/test_casca.py`. **O motor não
mexeu**: medido na cópia da base de 24/09, o mesmo `vault.db` dos dois lados —
fechar tudo **7 017,06 €**, 239 a comprar, 225 a arrumar (129 linhas), venda
268c/1 555,06 €, venda_rl 68c/3 941,08 €, rl_segurar 34c/4 756,11 €, reservadas
1c/100,00 €, guardar 2c/14,26 €, as 15 caixas — **iguais**.
- **UM SÓ MENU.** A barra lateral do site e o índice interno da Deckboxes
  estavam lado a lado com **os mesmos itens** (Plano, Montados, Para montar,
  Arrumar, Comprar, Encomendas, Vender, Feira, Revalidação). O índice interno
  (`deckboxes._filaDeAbas`) ficou só com **as caixas** — nos dois grupos de
  2026-09-08, com a percentagem —, mais «Todas as caixas» à cabeça e um grupo
  **«Mais vistas»** com as três CONDICIONAIS (Sugestões, Partilhadas, Não
  encontradas): aparecem e desaparecem conforme os dados, e por isso não podem
  viver numa barra escrita em Python, igual em todas as páginas — tirá-las daqui
  sem as pôr em lado nenhum era perdê-las. A coluna encolheu de 238 para 216 px.
  No `<select>` do telemóvel, estando ele numa VISTA nenhuma caixa fica
  seleccionada e o selector mostrava a primeira opção, a mentir sobre onde ele
  estava; passou a levar uma opção desactivada com o nome da vista aberta. Tem
  teste (`caso_o_indice_da_deckboxes_nao_repete_a_barra_lateral`): nenhuma
  âncora que a barra leve pode voltar a ser item do índice, e as quatro que a
  barra NÃO leva têm de continuar a ter entrada.
- **UM CONJUNTO ÚNICO DE ÍCONES SVG** (`site_shell._SVG`, 32 ícones `outline`,
  traço 1.8, `currentColor`; geometria do Feather, MIT, em `path`s soltos para
  não trazer dependência nem um segundo ficheiro). `shell.icone(nome, tam)` no
  Python e `shell.js_icones()` para o JavaScript da Deckboxes (`const ICO` /
  `ico(n)`, injectado pelo `js_texto`) — **um conjunto só**, pela razão do
  `e_foil` e do `vistoId`. Um emoji é desenhado pelo SISTEMA: o mesmo item tinha
  um peso no telemóvel dele e outro no Chrome do PC, o 🗺️/🛡️ levam `FE0F` e
  saíam a preto-e-branco no meio de ícones a cor, e um emoji não acende a
  dourado quando o item da barra fica activo. **Os emojis DENTRO dos dados
  ficam** (ordem dele, à letra: *"podem ficar se forem informação"*) — o ✅/🛒/📷
  de uma carta diz o ESTADO dela. **O `<svg>` está magro de propósito**: `fill`,
  `stroke`, a espessura e as pontas do traço vivem no CSS e não em cada ícone —
  escritos em cada um eram **190 bytes de repetição por ícone**, e a casca ia a
  71 336 bytes, acima do tecto de 70 KB do `test_telemovel`. Ficou em **68 842**
  (era 64 045) e o tecto subiu para **74 KB**.
- **Os rótulos da barra dizem o que são à primeira leitura**, sem notas
  redundantes: «Binders por cor», «Galeria de cartas», «Reserved List · caixa» e
  «Reserved List · preços» (estava «Caixa Reserved List» logo por cima de
  «Reserved List»), «Cobertura do metagame», «Decks Showcase», «Plano de
  montagem», «Arrumar cartas», «Revalidação por foto». A nota por baixo só fica
  onde ACRESCENTA. **E o TÍTULO de cada página é o MESMO rótulo**: clicar em
  «Binders por cor» e aterrar numa página chamada «Coleção por cor» é a página a
  discordar do menu que lá levou (o mesmo com a Galeria e as duas de Reserved
  List). Só o `<h1>` mudou — o balde `Caixa Reserved List` da base não se tocou.
  Tem teste: zero emojis dentro do `<nav class="sidenav">`, nenhum rótulo
  repetido, nenhuma nota a repetir o rótulo e o `<h1>` igual ao rótulo.
- **A GRELHA DO INÍCIO É 3 × 2.** Era `auto-fit` com mínimo de 262 px: a 1440
  cabiam quatro e os seis cartões saíam 4 + 2, com um buraco. São três colunas
  fixas em desktop, duas no telemóvel (uma abaixo dos 360 px), com
  `align-items:stretch` e o cartão em `flex` — as alturas de cada linha são
  iguais mesmo com detalhes de uma ou de três linhas.
- **ORTOGRAFIA DO ACORDO no texto visível** (45 correções: *colecção → coleção*,
  *actualizar/Actualizei → atualizar/Atualizei*, *acção → ação*, *correcção*,
  *projecção*). **Três coisas NÃO mudaram, e são a armadilha**: os nomes de
  funções e as chaves do relatório (`actualizacoes`, `copias_actualizar`,
  `activa`); o **`data-act="actualizar"`**, que é o nome de uma AÇÃO que o
  `webapp.py` compara literalmente — uma página aberta ontem no telemóvel ainda
  manda o nome antigo; e o balde **`Colecção`**, que é um VALOR da base
  (`sub_collections.name`) e é hoje **a única palavra fora do Acordo à vista no
  site** — mudá-lo é uma migração (a coluna é lida por dezenas de consultas,
  pelo `venda-stock.csv` e pelo `venda-estante.txt`), não uma correção de texto,
  e fica para ele decidir. O `caso_a_ortografia_e_a_do_acordo` lê o TEXTO das
  nove páginas publicadas, fora das etiquetas, e desconta esse balde.
- **OS RODAPÉS LONGOS FICAM RECOLHIDOS**: `shell.fechar()` embrulha o rodapé num
  `<details class="comoler">` — *«Como ler esta página»*, fechado por omissão —
  acima de `shell.RODAPE_LONGO` (320 caracteres). **Quem decide é o tamanho e
  não cada gerador a lembrar-se**, que é como o `cobertura.html` ficava para
  trás. Recolhem-se seis (Deckboxes 1 365 caracteres, Metagame 1 466, Reserved
  List 859, Cobertura 746, Coleção por cor 656, Início 343); os três curtos
  (Galeria 132, Caixa RL 196, Showcase 192) ficam abertos — um rodapé de duas
  linhas escondido atrás de um botão é pior do que rodapé nenhum.
- **As três dúvidas da 1.ª passagem, decididas por ele:** o CSS **fica
  embutido** (robustez > 11 KB); os selectores de 34 px da Cobertura **ficam**;
  a diferença de valor entre a Galeria e os Binders por cor **não se tocou** —
  **e foi corrigida no mesmo dia**, na secção a seguir.

**O VALOR DE UMA CÓPIA É UMA CONTA SÓ (André, 2026-09-24, à letra: *"corrige
tudo o que achares que é erro"*).** Sobre a dúvida nº 1 da reestruturação: a
Galeria dizia **97 761,26 €** e os Binders por cor **97 772,93 €** para o mesmo
dinheiro. Havia **seis** contas para *"quanto vale esta cópia?"* e nenhum passo
dava erro — o padrão do `event_tier` aplicado ao número que ele vê todos os
dias. Motor em **`mtgvault/collection.py`** (`mapa_precos` + `preco_impressao` +
`valor_da_coleccao`); testes em `tests/test_valor_unificado.py` (9 casos);
relatório em `ai-pc/work/revisao/mtgvault-valor-0924.md`.
- **A REGRA, por esta ordem**: o preço da impressão **exacta** no acabamento da
  cópia; senão, o mesmo cenário noutro acabamento da mesma **família** (foil ↔
  etched, a `loadout.FOIL_FINISHES`); senão, a outra família; e só no fim o
  outro cenário (trend ↔ low). É a tolerância do `loadout.card_price`, que
  devolve o nonfoil quando não há foil **e diz que é nonfoil** — por isso daqui
  sai também o acabamento a que o preço corresponde, e a Galeria marca essas
  cópias com **`~`** e a razão no `title`. A **fonte está fixa no `cardmarket`**:
  a conta dos Binders fazia `MIN` sobre a `price_latest` inteira, e ligar a
  CardTrader mudava o valor da coleção sem ninguém mexer numa carta.
- **O conjunto de cópias é o `na_estante()`** — o colecionador **entra** (*"são
  avaliadas mas nunca contam para decks, wantlists ou cobertura"*) e o que ele
  deu como não encontrado **não**. Os Binders usavam o `jogaveis()`, que o deixa
  de fora: hoje não há uma única cópia de colecionador, e por isso eram duas
  respostas à espera de discordarem. Vai numa **parte própria**
  (`partes.colecionador`), e a linha só aparece na tabela quando não é zero.
- **O NÚMERO DE CARTAS sai da MESMA chamada que o valor.** O Início contava com
  o `jogaveis()` e valorizava com o `na_estante()`: bastava entrar uma cópia de
  colecionador para o cartão dizer *"N cartas valem X"* com o X a contar cartas
  que o N não conta.
- **Quem lê de lá**: `collection_gallery` (tinha o `_price_map`, apagado),
  `colecao_cor._value` (ficou só a dar a forma que a página já lia),
  `inicio._valor_coleccao`, `collection.collection_value` (o `cli value`, que
  passou a `LEFT JOIN cards` — uma cópia sem impressão conhecida vale 0 € mas
  não desaparece da lista), `caixarl` (tinha o `_price_maps`, apagado),
  `reservedlist` (só o *valor da tua RL*) e `loadout.nao_encontradas`. **O que
  NÃO mudou, de propósito:** o `loadout.card_price` (o preço de COMPRA de uma
  carta — o mínimo entre impressões do mesmo nome — que é outra pergunta e é o
  que a venda, a regra dos 5 % da RL e a feira usam), as colunas *hoje* / *há 1
  mês* / o gráfico da Reserved List (o MERCADO de uma impressão, em nonfoil nas
  duas pontas da percentagem) e o `meta_coverage._visual` (o preço do que
  FALTA). O `refresh_collection` continua com o seu modelo de três camadas: a
  `collection_owned` já não alimenta página nenhuma.
- **Três defeitos apanhados pelo caminho**, todos da mesma família: (a) uma
  **etched** caía para o preço do **nonfoil** porque o «outro acabamento» estava
  escrito à mão como `"foil" if fin == "nonfoil" else "nonfoil"` — hoje são 3
  Blood Moon (SLD) que o Cardmarket não cota de todo, por isso não move um
  número, mas a próxima move; (b) a **Caixa RL** agregava por `(carta, idioma,
  acabamento)` e dava a uma linha a edição e o preço de UMA impressão com a
  quantidade de TODAS — 6 Taiga e 5 Tropical Island (Unlimited + Revised) ao
  preço da outra edição: **1 391,77 € a mais**. Passou a **uma linha por
  impressão** (e o «N cartas» dos cabeçalhos conta nomes distintos, não linhas);
  (c) os Binders mostravam o total com `casas=0` — *«97 773 €»* onde as outras
  duas páginas diziam *«97 772,93 €»*, com a conta certa por trás.
- **Medido na cópia da base de 2026-09-24** (o mesmo `vault.db` dos dois lados):
  valor **97 761,26 € → 97 772,93 €** nas quatro superfícies (Galeria, Binders,
  Início, `cli value`); a diferença são **3 cópias** foil sem cotação foil —
  Ethersworn Canonist (SLD) 10,67 €, Cid (FIC) 0,75 €, Helitrooper (FIC) 0,25 €.
  Cartas **1 678** nas três. Partes: coleção 31 295,53 € · decks 23 597,84 € ·
  Caixa RL 42 879,56 € · colecionador 0,00 €. Caixa RL (página) **48 429,13 € →
  47 037,36 €**, que é exactamente o que a conta única dá para as suas 181
  cópias (a fatia dos Binders é menor — 16 já estão dentro de deckboxes e contam
  como *decks*). `reservedlist` **47 885 € igual** (as 6 cópias de RL não-nonfoil
  são de impressões fora do âmbito da página). E o **`loadout.report` não mexe
  ao cêntimo e caixa a caixa**: fechar tudo 7 017,06 €, 239 a comprar, 225 a
  arrumar (129 linhas), venda 268c/1 555,06 €, venda_rl 68c/3 941,08 €,
  rl_segurar 34c/4 756,11 €, reservadas 1c/100,00 €, guardar 2c/14,26 €, as 15
  caixas.
- **O GRÁFICO DA EVOLUÇÃO DIZ ONDE A REGRA MUDOU.** O `value_history` da Galeria
  tem um ponto por dia; o de hoje recalcula-se sozinho (o `build` faz `INSERT OR
  REPLACE`), os anteriores **ficam como foram medidos** — reescrever um
  histórico que ninguém mediu era inventá-lo. O que se faz é marcar a costura:
  `collection_gallery.REGRA_NOVA` (`2026-09-24`) e `_costura()` dão a linha
  tracejada no primeiro ponto da regra nova, com a nota por baixo a dizer que o
  degrau de ~11,67 € **não é o mercado**.

**O PREÇO TEM TRÊS MODOS: market, best e a média dos dois (André, 2026-09-25, à
letra).** *"tal como no riftvault, o preço da colecção pode ser pelo market value
do cardtrader, ou o best value, ou a média dos 2"*. Continua a decisão de
2026-09-24 (*"o valor de uma cópia é uma conta só"*): aquela unificou a CONTA,
esta dá-lhe a RÉGUA. Motor em **`mtgvault/precos.py`**; testes em
`tests/test_preco_modo.py` (13 casos) e a prova de que chumbam sem a
funcionalidade em `tests/_provar_chumba.py` (corre-se à mão).

- **O QUE O RIFTVAULT FAZ MESMO — foi lido antes de se escrever uma linha, e a
  premissa dele estava meio errada.** O riftvault (`riftvault/prices.py`,
  `oferta()`) guarda **um só** preço por impressão: `min(price_cents)` das
  ofertas utilizáveis. Isso é o **best value** — **não há market value nem média
  no riftvault**, e os três modos são desenho novo. O que se copiou de lá foi o
  **filtro das ofertas** (sem graded, sem vendedor de férias, sem altered/signed,
  estado em Mint/NM/SP/MP, língua em `precos.linguas`, EUR, > 0) e o **sítio da
  configuração**: `precos.linguas` é a mesma chave nos dois, e `precos.modo` com
  os nomes `market`/`best`/`media` cai no `riftvault_config.json` sem mudar uma
  letra no dia em que ele lá os quiser.
- **O CARDTRADER NÃO PUBLICA "MARKET VALUE" NENHUM** (sondado contra a API a
  2026-09-25, `/blueprints/export` e `/marketplace/products` da `ody`): os
  blueprints não trazem campo de preço nenhum e cada oferta traz só o seu
  `price_cents`. Por isso calcula-se, e está escrito o que é cada um:
  **best = a oferta mais barata**, **market = a MEDIANA das utilizáveis**. A
  mediana e não a média porque a cauda de cópias raras e estrangeiras puxa uma
  média que ninguém pratica: nessa sonda, Tainted Pact best 20,27 € contra
  mediana 34,27 € (28 ofertas).
- **O `fetch_cardtrader_prices` guardava UM valor, copiado para as duas colunas**
  (`low = trend = min(ofertas)`) — por isso os três modos dariam todos o mesmo
  número, e por isso **não se conseguia ver a diferença**. Agora escreve os dois,
  e **filtra as ofertas**: sem o filtro, o preço de um Mountain de Odyssey eram
  os 0,28 € de uma cópia italiana «Poor» com o verso escrito à mão — e esse
  número entrava no valor da colecção e na lista de compras.
- **A EXPRESSÃO DO PREÇO VIVE NUM SÍTIO SÓ: `precos.sql()`** (`market` → `trend`,
  `best` → `low`, `media` → a média, `NULL` só quando faltam os dois). Era
  `MIN(p.trend)` escrito à mão em **oito** consultas — `loadout.card_price`,
  `impressao_mais_barata`, `_historico`, `collection.mapa_precos`,
  `wantlist.cheapest_price`, `meta_coverage` (×4), `core_decks`, `scryfall`,
  `reservedlist`, `refresh_collection`, `import_owned` —, e a primeira que se
  esquecesse do modo punha duas páginas a dizer dois números para o mesmo
  dinheiro, que é exactamente o defeito que 24/09 fechou. Tem teste que varre o
  código à procura do literal (`caso_o_sql_do_preco_vive_num_sitio_so`).
- **A FONTE passou ao config** (`precos.fonte`, hoje `cardmarket`). Estava fixa
  no código pela razão certa — um `MIN` por cima de todas as fontes mudava o
  valor da colecção no dia em que o CardTrader entrasse —, e continua a ser uma
  fonte de cada vez; só que agora é ele que escolhe. O `reservedlist.price_maps`
  fazia esse `MIN` sobre a `price_latest` INTEIRA e com o `low` escolhido à mão:
  passou pela mesma régua.
- **«SEM PREÇO» NÃO É ZERO EUROS.** Uma impressão que a fonte escolhida não cota
  devolve `None` e conta em `sem_preco`. Zero numa soma tira uma carta de 900 €
  do total sem nenhuma linha dizer que faltou.
- **A REGRA DA RESERVED LIST — a parte que mais podia custar dinheiro.** A regra
  de 2026-09-08 compara o preço de hoje com o de há N dias, e é ela que decide se
  uma carta que não se volta a imprimir vai à venda. **Duas defesas, e as duas
  são precisas:**
  - **A RECEITA.** Cada linha de `price_latest`/`price_history` passou a dizer
    COMO foi produzida (`price_*.receita`: `unico` = um valor copiado para as
    duas colunas — o bulk da Scryfall e o CardTrader antigo; `cm-guide` = o price
    guide do Cardmarket; `ct-ofertas` = melhor oferta + mediana). O
    `loadout._historico` **só traz pontos da receita em vigor**. Sem isto, no dia
    em que o `trend` deixasse de ser «o único preço da Scryfall» e passasse a ser
    «a mediana das ofertas», a regra comparava as duas escalas e inventava
    subidas de dezenas por cento — sem um único erro, o padrão do `event_tier`
    sobre a decisão de venda que vale mais dinheiro. Coluna nova = os três
    sítios: `schema.sql`, `db._migrate()` e quem a escreve (`prices.write_prices`,
    onde ela **entra também na comparação** — os mesmos números com outra receita
    são uma linha nova de histórico).
  - **O CARIMBO DO MODO.** `precos.modo_desde` guarda a data da última troca, e o
    `avaliar_rl` encurta a janela até lá. Trocar de modo troca a régua com que
    ele anda a olhar para os números: até haver `venda.rl_janela_minima_dias`
    (25) dias medidos no modo novo a resposta é **`rl_sem_historico`** — a
    terceira resposta que existe desde 08/09 —, nunca *"não subiu"*. **Trocar
    para o modo que já lá está é um no-op** e não reinicia janela nenhuma.
    É o caso que ele mandou forçar e tem teste próprio
    (`caso_trocar_de_modo_nao_manda_nenhuma_rl_para_a_venda`), que chumba em cima
    de um `avaliar_rl` sem o carimbo.
- **Onde se troca:** o interruptor **market · best · média** no cabeçalho da
  Deckboxes, só no modo edição (`POST /api/preco-modo`; um valor fora dos três é
  409, como a `vista`), e `py -m mtgvault.cli precos modo <market|best|media>`.
  A troca **regenera** — muda todos os números da página ao mesmo tempo — e a
  resposta diz, em português, que a regra da RL fica em suspenso. O modo viaja no
  payload (`D.preco`) e os Binders dizem-no debaixo do total: um total sem a
  régua ao lado é um número que muda sozinho de um dia para o outro.
- **`py -m mtgvault.cli precos comparar`** põe os três lado a lado — valor da
  colecção, fechar tudo, as sete saídas da venda e **quantas cartas mudam de
  lado**. Vive no código e não num script de medição que se perde: é a pergunta
  com que ele escolhe.
- **MEDIDO NA CÓPIA DA BASE DE 2026-09-25** (`py -m mtgvault.cli precos comparar`
  sobre uma cópia do `vault.db`, o mesmo nos três modos):
  - **Com a fonte de hoje (`cardmarket`, receita `unico`) os três modos são
    IGUAIS ao cêntimo**: colecção **97 913,68 €** (1 678 cartas, 4 sem preço),
    fechar tudo **6 978,93 €** (253 a comprar), venda 268c/1 566,55 €, venda_rl
    66c/4 915,91 €, rl_segurar 36c/3 618,39 €, reservadas 1c/100,00 €, guardar
    2c/14,71 €, **0 cartas mudam de lado**. Ligar isto hoje não mexe um número —
    de propósito: `low` e `trend` são o mesmo valor da Scryfall.
  - **Com o CardTrader puxado para as 145 edições dele** (30 162 impressões no
    mapa, **53 113 linhas de preço** — 29 365 nonfoil + 23 748 foil —, **todas
    com os dois valores** e só **312** com `low == trend`, que são as de oferta
    única), os três modos separam-se mesmo:

    | | market | best | média |
    |---|---|---|---|
    | colecção | **108 368,46 €** | **74 125,29 €** | **91 246,88 €** |
    | fechar tudo | 6 406,16 € | 4 191,18 € | 5 302,01 € |
    | venda (268 c) | 2 857,20 € | 1 921,79 € | 2 399,03 € |

    São **34 243 € entre a ponta de cima e a de baixo** — 32 % do valor da
    colecção. As maiores diferenças por cópia são as caras: Gaea's Cradle (USG)
    best 1 100,64 € / market 1 765,86 €, Mox Diamond (STH) 850,64 / 1 487,64,
    Underground Sea (3ED) 630,64 / 1 127,96.
  - **E MUDAM DE LADO ZERO CARTAS, nos três modos.** As 268 cópias da venda
    normal são as mesmas; o que muda é o euro que valem. A Reserved List —
    **102 cópias** — cai INTEIRA em `rl_sem_historico` assim que a fonte passa a
    `cardtrader`, porque o histórico dessa fonte começa hoje: é a regra a
    proteger-se, não um efeito do modo.
  - **A DECISÃO QUE FICA PARA ELE, e o número que a manda:** dos **1 678**
    exemplares, o Cardmarket deixa **7** sem preço na impressão exacta e o
    CardTrader deixa **606** (36 %) — são as PT, as edições antigas e as foil
    que o marketplace não tem à venda hoje. Ligar `precos.fonte: "cardtrader"`
    hoje era trocar 32 % de valor por 36 % da colecção sem cotação. Por isso a
    fonte ficou em `cardmarket` e o modo em `market`, que é onde ela já estava:
    **nada mudou de número no dia em que isto entrou** (ver a linha de cima).

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

**DUAS REGRAS NOVAS (André, 2026-09-19, à letra) — SUPERSEDEM A PARTILHA ENTRE
CAIXAS.** As palavras dele, no chat desse dia:
1. *"quando escreves que a carta não serve porque devia ser foil e não é foil,
   confirma se há foil"*
2. *"cada deck deverá ter as suas próprias cartas dentro, não repetindo com
   outros decks!"*

Relatório e medições em `ai-pc/work/revisao/mtgvault-regras-0919.md`; testes em
`test_foil_existe.py` e `test_caixas_dedicadas.py`; os casos antigos que
fixavam a partilha (v4 de 2026-09-07, Premodern de 2026-09-08) foram
reescritos um a um, com o porquê no docstring.

- **Regra 1 — «só foil» só quando a carta EXISTE em foil.** O catálogo diz por
  impressão (`cards.finishes`) e a resposta por carta é `scryfall.impressoes_foil`
  → `loadout.foil_info` (uma consulta por nome, pelo `ix_cards_name`, guardada
  por corrida em `foil_cache`; os lotes saem do `lots()` anotados com
  `foil_existe`/`foil_edicoes`). **Só papel**: as impressões `digital` (MTGO —
  a Swift Reconfiguration só tem foil na `prm` de MTGO) e a memorabilia não
  contam, como no `scryfall.impressoes`. Uma carta que o catálogo **não
  conhece** não é "sem foil": a regra da caixa fica (não se inventa).
  **A verdade vive em `loadout.acabamento_efectivo(s, existe)`**: numa caixa que
  quer foil (`foil` no SPML/Duel Commander, `prefere_foil` no Pauper) e numa
  carta que nunca saiu em foil o acabamento efectivo é `SEM_FOIL` — a nonfoil
  **serve** (aloca, fecha o slot, não é substituto, não vai à venda), e a compra
  pede-a nonfoil, ao preço do nonfoil (`req_compra` *"nonfoil — nunca saiu em
  foil"*, `marca_compra` `nonfoil`). O `_porque_nao`, o `requisito_material`, o
  `marca_compra`, o `finishes_aceites`, o `material_da_caixa`, o
  `impressoes_da_falta`, o `registar_falta` e o `encomendas.validar`/
  `cumpre_regra` lêem de lá (via `regra_da_carta(con, s, nm)`). O `nonfoil` do
  cEDH não muda. Quando a carta existe em foil, a recusa passou a dizer **em
  que edições** (`razao_nao_foil` → *"não é foil (existe em foil: MMQ 1999, EXP
  2016, OTP 2024, EOS 2025)"*, as 3–4 primeiras por data, EN à frente), e a
  frase viaja com o `alt`/`substituto` para os substitutos, a aba Vender, a
  exportação e o CLI. Medido na cópia da base de 2026-09-19: Glimmer Lens (ONC)
  e Swift Reconfiguration (NEC; foil só digital) passam a fechar o slot do Duel
  Commander (73→75 de 97); a Ademi of the Silkchutes não está no catálogo e a
  wantlist continua a pedi-la foil.
- **Regra 2 — cada deck box com as suas cartas, sem repetir.** Vale para
  **todos os formatos** e substitui o *"ir buscar a outra caixa"* (`noutra`,
  2026-09-07/08), a partilha de compras da v4 (Duel Commander e SPML) e a
  partilha entre caixas de Premodern de 2026-09-08. `resolve_slots` força
  `dedicado = True` em toda a caixa (o config também o diz em todos os grupos;
  um `dedicado: false` **deixou de ter efeito**), `dedicadas()` devolve todas,
  `_empresta` é sempre `False`. Uma cópia alocada a uma caixa é dessa caixa;
  outra caixa que peça a mesma carta **compra-a** — o `missing` conta-a, o
  "fechar tudo" soma-a, a wantlist pede-a. O `noutra` e as suas metades
  (`noutra_montada`/`_reservada`/`_futura`, `noutra_lotes`) ficam a **zero**;
  `conflitos` e `partilhas` são `[]`; `partilhar_compras` deixou de partilhar
  (ficou só com o tecto). O que fica do "onde está" é a **NOTA** — `noutra_nota`
  → `loadout.nota_onde(m)` = *"tens 2 no Blue Farm"* —, na carta, na wantlist e
  num bloco «tens noutra caixa» da aba da caixa, nunca como fonte, substituto
  nem desconto. A aba **Partilhadas** só aparece na fila se um dia voltar a ter
  linhas; o bloco «destinadas a outra caixa» do painel Montar é vazio
  (`movimentos_reservados` → `[]`); o CLI só imprime o "destinadas a outra caixa"
  se deixar de ser zero. As funções da partilha (`pool_compra`, `pools_de_compra`,
  `_parte_noutra`, `onde_esta`, `movimentos_reservados`, o `de_outra` do
  `registar_marcadas`) **ficam no código** sem efeito — apagar é decisão dele.
- **A EXCEPÇÃO mantida: o tecto de playset do Premodern** (2026-09-08, *"afinal
  só vou ter até playset de cada carta"*) continua, e agora conta o **grupo
  inteiro** (`partilhar_compras`, grupo por `s["grupo"]`): `comprar do grupo =
  max(0, 4 − o que as caixas do grupo já têm)`, distribuído por prioridade; o
  que não cabe fica em `playset_bloqueado` com `playset_onde` (*"está 4 no UW
  Replenish"* — conta também o que o grupo vai comprar) e sai **fora** do
  `comprar`/"fechar tudo". A frase é `loadout.texto_playset(m)` (*"4 não se
  compra (limite de 4 no total; está 4 no UW Replenish)"*), na página, no
  `nota_parcial`, no CLI e no aviso das encomendas. É onde as duas regras dele
  se tocam e escolheu-se o que menos compra: na base de 2026-09-19 são **47
  cópias** por tapar sem se comprarem (Enchantress 25, Elves 14, Oath 8).
- **Consequências a saber:** (a) as caixas de Premodern montadas e com
  conteúdo confirmado passam a **congelar** (`congelada` exige `dedicado`, que
  agora todas têm) — Stiflenought e UW Replenish; (b) as **sugestões de
  Premodern** medem-se só com o que está **livre** (`pct_principal` ==
  `pct_livre`, porque nenhuma caixa empresta) — na base de 2026-09-19 nenhuma
  chega aos 50 % e as 30 cópias que o Psychatog/Landstill reservavam voltam à
  venda; (c) a ordem por % do Premodern (`pct_na_coleccao`) deixa de contar o
  que está dentro de outras caixas — Elves (41 %) passou à frente da
  Enchantress (39 %).
- **Medido na cópia da base de 2026-09-19** (`_revisao/medir_loadout.py`, o
  mesmo `vault.db` dos dois lados): fechar tudo **7 098,03 € → 7 133,62 €**,
  comprar **203 → 207**, ir buscar **52 (25/16/11) → 0**, arrumar 180 (102 →
  103 linhas), venda **244c/1 505,78 € → 273c/1 565,57 €**, venda_rl 63c/
  4 152,94 € → 65c/4 347,64 €, rl_segurar 37c/4 316,39 € igual, reservadas
  **32c/354,49 € → 1c/100,00 €**, guardar 2c/14,82 € igual. Por caixa: Duel
  Commander 75→77 % (comprar 22, 727,39→737,17 €), Modern comprar 17→19
  (117,57→123,83 €), Elves 40→41 % (29→30 a comprar), Enchantress 40→39 %
  (20→21), Oath igual (17), as outras iguais.

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

**A SAÍDA DA LISTA DE VENDA (`mtgvault/venda.py`, 2026-09-18).** A aba Vender
mostrava a lista e tinha o «vendida» por linha, mas nada a tirava do ecrã para o
sítio onde as cartas se vendem — 230 cópias em `venda` e 55 em `venda_rl`, cerca
de 4 300 € parados numa página só de leitura. Agora a aba (bloco **📤 Saída**, no
topo), o CLI (`python -m mtgvault.cli vender --exportar`) e o `daily` (passo
`venda-export`, logo a seguir ao `deckboxes` e com o MESMO `loadout.report`)
produzem três coisas, todas do `mtgvault.venda`:
- **`data/venda-stock.csv`** — o ficheiro para carregar stock: uma linha por
  CÓPIA (não por linha da página — o estado NM/EX é da cópia, e dois lotes da
  mesma impressão em estados diferentes são duas linhas), com nome em inglês,
  edição (código), número, língua, acabamento (`foil`/`nonfoil`), estado,
  quantidade, preço de referência e um comentário (`mtgvault #<copy_id> ·
  <onde estava>` — **no Cardmarket o comentário de um artigo é público**; se não
  o quiser à vista, apaga a coluna antes de carregar). **O formato predefinido
  (`Name,Set,Number,Language,Foil,Condition,Quantity,Price,Comment`, vírgula)
  NÃO foi confirmado contra uma conta real do Cardmarket** — não se conseguiu
  ver de fora o que o site aceita hoje, e não se inventou um para o dar por
  certo: a página, o CLI e o `daily` dizem-no. **O exportador APRENDE com o
  ficheiro dele**: se existir **`data/cardmarket-stock-exemplo.csv`** (uma
  exportação de stock que o André descarregue uma vez da conta), lê-se o
  cabeçalho, o delimitador (`;`/`,`/TAB), o BOM, o fim de linha e — havendo
  linhas — o VOCABULÁRIO (foil como `1`/`0`, `Yes`/`No` ou `true`/`false`;
  língua por nome, por código ou pelos ids da API; decimal com vírgula), e a
  exportação sai exactamente nessa forma, com as colunas que se reconhecem
  preenchidas (`venda.mapear_coluna`: nome, edição, expansão, número, língua,
  foil, estado, quantidade, preço, comentário, `idProduct` do catálogo) e as
  outras **vazias, na posição delas**. Um teste para cada caminho
  (`test_venda_export.py`). O exemplo fica fora do Git (é o stock dele, com
  preços).
- **`data/venda-estante.txt`** — a lista para ir buscar as cartas, agrupada por
  ONDE a cópia está (`loadout.local`: caixa, Colecção, Caixa RL PT/EN), por COR
  dentro de cada sítio (como o binder; o painel Montar já fazia o mesmo), com o
  total de cópias e de euros por grupo. Na página é uma linha por cópia, sem
  tabela — para o telemóvel à frente da estante — e imprime-se (`@media print`
  esconde menus, botões e textareas).
- **O que NÃO se vende fica visivelmente de fora** (`venda.fora_da_exportacao`):
  `rl_segurar`, `rl_sem_historico`, `guardar`, `reservadas` e `retidos` não
  entram no CSV nem na estante e aparecem no bloco **3. Fica de fora** com o
  motivo por linha — na RL a percentagem e a janela (`rl_nota`) e o *"ia por:"*.
  A decisão foi tomada, não esquecida.
- Os dois ficheiros **reescrevem-se** a cada corrida (são "a lista de hoje", sem
  data no nome; o histórico do que ele VENDEU continua a ser o `vendas.csv`), com
  escrita atómica (o `daily` e o `webapp.py` escrevem os dois), e estão no
  `.gitignore` — levam preços por cópia, a mesma regra do `vendas.csv`. Na
  página há **copiar** e **⬇ descarregar** (site publicado e modo edição) e, só
  no modo edição, **💾 gravar em data/** (`POST /api/venda-export`, exige o
  token; recalcula o relatório antes de escrever).
- **A venda passou a escolher o lote em PIOR ESTADO** (`loadout.ordem_estado`,
  MT→PO; o `lots()` traz `cond`): entre lotes iguais desempatava pelo `id`, e a
  lista de stock dizia NM de uma cópia que era a EX que ele ia vender. Só mexe no
  desempate — os totais e as contagens da venda não mudam.

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
**[SUPERSEDED 19/09/2026 — *"cada deck deverá ter as suas próprias cartas
dentro, não repetindo com outros decks!"*: o `noutra` é zero em todos os
formatos e a carta que está noutra caixa é COMPRA, com a nota «tens N no X».
Ver "DUAS REGRAS NOVAS" no topo desta secção. O que segue fica como histórico.]**
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
**[SUPERSEDED 19/09/2026: as três metades do `noutra` (`montada`/`reservada`/
`futura`) e o bloco «destinadas a outra caixa» do painel Montar são zero/vazios
por regra — cada caixa compra as suas. Histórico.]**
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
  caixa"* (`webapp.registar_parcial(..., de_outra=[copy_id])`, que só aceita
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
letra).** **[SUPERSEDED 19/09/2026 na PARTILHA: as caixas de Premodern voltaram a
ser dedicadas como todas as outras (*"cada deck deverá ter as suas próprias
cartas dentro"*). O que FICA desta secção é o `playset_maximo: 4`, agora contado
sobre o grupo inteiro — se ele já tem 4, a caixa de menor prioridade mostra
*"não se compra (limite de 4 no total; está no &lt;deck&gt;)"* — e o
`prioridade_por: "pct"`. As caixas de Premodern montadas passam a congelar.]**
*"No Premodern, afinal só vou ter até playset de cada carta. E
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
  segunda ordem do dia, à letra):** **[SUPERSEDED 19/09/2026: nenhuma caixa
  empresta, por isso `pct_principal` é igual à cobertura do que está LIVRE — a
  página mostra uma percentagem só. Na base desse dia nenhum candidato chega aos
  50 % e não há sugestões; ver a dúvida no relatório `mtgvault-regras-0919.md`.]** *"Como as cartas em Premodern são
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
  **E aparece "modificado" no `git status` todas as manhãs, de propósito**
  (verificado a 2026-09-15): o `resolver` escreve `ultima = hoje` em cada
  arquétipo que o relatório vê, e o primeiro relatório do dia é o do `webapp.py`
  (a sonda do `mtgvault-serve` pede a página de 5 em 5 min), horas antes do
  `mtgvault-daily` das 08:00, que é quem o commita (`dados <hoje>`). Um diff que
  seja só `ultima: ontem → hoje` é este ritmo, não uma bateria a estragá-lo — a
  bateria apagava-o inteiro, e é isso que o `caso_a_bateria_nao_escreve_no_data_a_serio`
  tranca.
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
partilhar — ver acima).** **[SUPERSEDED 19/09/2026: desde então TODAS as caixas
são dedicadas, em todos os formatos, e o `dedicado: false` deixou de ter
efeito. Histórico.]** *"Cada deck montado deixa de partilhar
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

**COMPRAS PARTILHADAS: compra-se o MÁXIMO, não a soma (2026-09-07).**
**[SUPERSEDED 19/09/2026: agora é a SOMA — cada caixa compra as suas; o
`partilhar_compras` devolve sempre `[]` e só aplica o tecto do Premodern; o
`compras_dedicadas` do config deixou de fazer diferença. Histórico.]** É a segunda
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
`reter_extras` — os extras dos decks vigiados, **guardados sem prazo** desde
2026-09-15; ver "Regras por coleção" abaixo. Até aí era `reter_extras_meses` e
um prazo de 6 meses que nunca chegou a correr), **`reservadas`** (cópias
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
  está a NULL). Medida na cópia da BD, é **neutra nos números**: 7 891,50 € para
  fechar, 230 a comprar, 61 a ir buscar, venda 91c/702,95 €, classify
  {deck 152, coleção 938, vender 97} — iguais antes e depois.
  **CORREU NA BASE DO ANDRÉ A 2026-09-07** (727 cópias, no lançamento da v2 —
  `ai-pc/work/revisao/mtgvault-lancamento-0907.md` §6; o CLAUDE.md ficou onze
  dias a dizer o contrário). **E outra vez a 2026-09-18**, porque a base tinha
  voltado a ter duas gavetas de deck: **10 cópias** (729–738, criadas pelo botão
  *"já a tenho"* a 09/09) viviam em `Blue Farm` (3) e `Cloud cEDH` (7) — o
  `registar_falta` escrevia no `balde` da caixa, que é o nome do modelo antigo.
  Medido nesse dia com backup de hora
  (`data/backups/vault-2026-09-18-234209-antes-coleccao-unica.db`) e o relatório
  inteiro de cada lado: **neutra ao cêntimo e linha a linha** — fechar tudo
  7 057,57 €, 199 a comprar, 53 a ir buscar (26/16/11), 185 a arrumar em 103
  linhas, venda 246c/1 499,70 € · venda_rl 58c/3 702,99 € · rl_segurar
  42c/4 768,21 € · rl_sem_historico 0 · retidos 0 · reservadas 32c/353,04 € ·
  guardar 1c/14,75 €, classify {deck 127, coleção 902, vender 73}, as 14 caixas e
  a `copy_allocation` (411 cópias em 6 caixas) iguais. Só os baldes mudam:
  {Colecção 1 487, RL 181, Cloud cEDH 7, Blue Farm 3} → {Colecção **1 497**, RL 181}.
- **A REGRA DA MIGRAÇÃO PASSOU A SER A REGRA DE ENTRADA (2026-09-18).** Sem
  isto a base desfazia a migração ao ritmo das compras dele, sem um único erro.
  `collection.gaveta_de_entrada`: numa base já migrada (tem o balde `Colecção`),
  um `sub_collection` dos baldes fundidos (`migracao.BALDES_A_FUNDIR` — `SPML`,
  `Blue Farm`, `Cloud cEDH`…) já não é uma gaveta: a cópia entra na `Colecção`
  com esse nome em `balde_origem`, que é exactamente o que a migração lhe faria,
  e continua a valer como *"veio do balde deste deck"* para o
  `contradiz_a_caixa`. Vale para o `add_copy` inteiro (fotos, CSV, *"já a
  tenho"*); a `Caixa Reserved List` e o colecionador ficam como estão; numa base
  por migrar não muda nada (os testes). O `PROCESSAR_FOTOS.md` passou a dizer
  `Colecção`. Três casos em `test_migracao.py`, e o `--dry-run` a zero depois de
  uma entrada é o que os tranca.
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
`reter_extras: true` para os decks de Commander/cEDH/Duel Commander/Pauper —
`Blue Farm`, `Cloud cEDH`, `Cloud`, `Pauper Affinity`. Estes são "coleção
própria + lista vigiada": as cartas EXTRA (as do balde que a lista do deck já
não usa) ficam **GUARDADAS SEM PRAZO** — saída `retidos` da venda, com o motivo
`loadout.RAZAO_RETIDO` e, ao lado, `porque_venderia` (o motivo por que iriam à
venda, como nas RL a segurar) — e só saem quando o André o disser, carta a
carta, com o botão «vendida». Premodern NÃO usa isto (tranca por completude).

**DECISÃO DE 2026-09-15: a regra dos 6 meses foi DESLIGADA.** Desde 2026-08-14
a chave era `reter_extras_meses: 6` (*"guardam-se até 6 meses da última
utilização; passado isso sem uso → Vender"*) e havia um segundo prazo no
`classify.py` (`SELL_STALE_DAYS = 180`, *"6 meses sem ser jogada em torneio →
vender"*). **Nenhum dos dois alguma vez correu**: o do loadout esperava por uma
fonte de "última utilização" que nunca foi decidida (o `colecao_cor` chegou a
datá-la pelos `watched_snapshots`, só para a mostrar), e o do classify não podia
morder porque o `daily` só guarda ~30 dias de listas — nenhuma "última aparição"
chegava aos 180 dias. Dois prazos escritos, nenhum a correr, e a página a dizer
*"retidas até 6 meses"*: é o padrão do `event_tier`, uma regra que a página diz
e não existe. Ele decidiu que não quer prazo nenhum: o que sai dos decks
vigiados sai quando ele o disser. Consequências:
- **A fonte de "última utilização" deixou de ser precisa** — saiu do "por
  decidir" e do código (`classify._last_played`, o `last`/`expired` do
  `colecao_cor._watched_deck_pools`, que passou a ler só o snapshot mais
  recente). Não se volta a datar o que já não tem prazo.
- **A chave antiga `reter_extras_meses` continua a ler-se e vale o mesmo**
  (`loadout._retencao`: qualquer valor truthy = guardar). Um config que ainda a
  tenha não pode passar a vender de um dia para o outro o que ontem guardava.
- **Medido na base de 2026-09-15** (o mesmo `vault.db` no `main` e no ramo): as
  sete saídas da venda **iguais ao cêntimo e linha a linha** — venda 230c/
  1 345,89 €, venda_rl 55c/2 935,31 €, rl_segurar 43c/4 432,19 €,
  rl_sem_historico 0, **retidos 0** (hoje não há extras nos quatro baldes),
  reservadas 30c/168,20 €, guardar 1c/14,75 €; fechar tudo 8 131,37 €, 227 a
  comprar, 71 a ir buscar, 209 a arrumar; classify deck 131/coleção 898/vender
  73, só por *"excesso (mais de 4)"*. O caso com extras a sério está nos testes
  (`test_loadout.caso_backup_e_venda` e
  `caso_a_chave_antiga_reter_extras_meses_continua_a_guardar`; `test_sem_prazo.py`
  tranca que o prazo não volta por outro nome e que o texto vivo diz "sem prazo").

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
  `_played_names` do classify (o `_last_played` saiu a 2026-09-15 com a regra
  dos 6 meses) é a rede de segurança contra
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

**5. UM REGISTO NÃO LAVA UMA CORRECÇÃO: a `copy_allocation` deixou de ser
excepção às regras de material (André, 2026-09-09, à letra).** *"Essa Chromatic
Star fotografada é foil, tal como a Grinding Station"*, no mesmo dia em que disse
que não as tem no Cloud cEDH. As duas cópias (694, 403) estavam na base como
**nonfoil** — a 403 com a nota *"parece non-foil (sem holo); confirmar foil"*.
Sendo nonfoil EN serviam o Cloud cEDH (*"só inglês non-foil"*), foram alocadas, e
ao registar a caixa (65 linhas de uma vez, às 10:39 de 09/09) ficaram com linha
na `copy_allocation`. Nessa tarde corrigiu-se o acabamento para **foil** — e a
caixa continuou a dizer que as tinha, porque *"uma cópia que está DENTRO da caixa
deste deck escapa às regras de material"*. **A linha da `copy_allocation` lavava
a correcção**: padrão do `event_tier`, nenhum passo dá erro, e uma foil fechava um
slot que só aceita nonfoil. Motor em `loadout.contradiz_a_caixa` +
`loadout.contradicoes`.
- **A alocação é uma afirmação sobre o SÍTIO, escrita com os dados de então.**
  Corrigir os dados da cópia tem de poder corrigir a caixa. Uma cópia registada
  numa caixa que a regra de material DELA recusa é uma **contradição**: trata-se
  como estando na gaveta (`lots()` põe-lhe `caixa=None`, guarda
  `caixa_registada`/`contradiz`), a carta volta a ser **compra** naquela caixa, a
  cópia fica **substituto** visível (não vai à venda) e **liberta-se** para as
  caixas que a aceitam — a Grinding Station foil passou a servir o Modern.
- **A `key` do sub-lote continua a sair do REGISTO**, não do sítio calculado:
  duas partes da mesma cópia com a mesma chave faziam o `reclamado` e o
  `_reparte_por_sitio` contá-la duas vezes.
- **O que continua protegido é o que a excepção existia para proteger:** a cópia
  que já vivia no BALDE desta caixa. Antes da migração responde o `_porque_nao`
  (`lot["sub"] == s["balde"]`); depois dela responde o **`copies.balde_origem`**,
  que a migração escreve exactamente para isto. É o Tarnished Citadel PT foil do
  Blue Farm — nunca saiu de dentro do deck. Medido: das 60 cópias registadas no
  Cloud cEDH, **58 vieram do balde `Cloud cEDH`** (ficam) e as **duas** que ele
  nomeou vieram do `SPML`, varridas para lá por um registo em bloco.
- **Uma caixa CONGELADA não é excepção** — e a dele é uma (`montada` + dedicada +
  com conteúdo). O que o `congelada` promete é outra coisa: *"as cópias lá dentro
  ficam presas mesmo que a LISTA de hoje já não as peça"*. Uma contradição não é a
  lista a mudar; é a cópia a não poder ali estar, hoje como ontem. O que CUMPRE e
  a lista já não pede continua preso (tem caso de teste).
- **O «já arrumei tudo» deita fora o registo contraditório**, inclusive numa
  caixa congelada (onde ele preserva as linhas de propósito). É a *"linha órfã que
  mentia para sempre"* de que o `guardar_arrumacao` se defende — e sem isso a
  lista de contradições nunca se limpava, por muito que ele arrumasse.
- **Os terrenos básicos são isentos**, a mesma isenção que a alocação já lhes dá.
- **Diz-se em voz alta**, senão a percentagem descia sozinha e sem explicação:
  `res["contradicoes"]` (mais `s["contradicoes"]` por caixa e
  `contradicoes_total`), um bloco na aba da caixa da Deckboxes e duas secções no
  `python -m mtgvault.cli loadout`. E o crachá **«N de M na caixa»** passou a
  aparecer também numa caixa que se DIZ montada e tem cópias por lá meter — antes
  só aparecia nas que não se diziam montadas, e a caixa parecia fechada com o
  painel Montar por baixo a dizer o contrário.
- **Efeito medido na base de 2026-09-09** (o mesmo `vault.db` dos dois lados, com
  o config vivo): fechar tudo **8 245,37 € → 8 250,26 €**, comprar **220 → 222**,
  Cloud cEDH **74 % → 72 %** (comprar 26 → 28). Tudo o resto **igual**: ir buscar
  71 (37/20/14), arrumar 211 cópias em 118 linhas, venda 229 c/1 338,71 € + 40
  RL/3 154,55 €, guardar 1, reservadas 31, e as outras 13 caixas ao cêntimo.
  Contradições: **2**, as duas que ele nomeou. Ver
  `work/revisao/mtgvault-montada-alocacao.md`.

**6. O REGISTO GRAVA SÓ O QUE ELE MARCOU, CÓPIA A CÓPIA (2026-09-09).** A regra
dele é a mesma do ponto 4 — *"se eu não seleccionar no deck que meti a carta, com
checkmark, é porque eu não a tenho"* —, aplicada agora ao **outro lado**: não ao
que fazer com as que sobram, mas ao que se grava. A 09/09 às **10:39:55** o Cloud
cEDH ganhou **65 linhas** na `copy_allocation` de uma vez, e duas delas eram
cartas que ele não tem lá dentro. A defesa das contradições
(`contradiz_a_caixa`) é *posterior ao facto*: apanha-as no dia seguinte, e só
quando os dados da cópia a denunciam. A defesa a sério é esta.
- **Um só caminho para meter cartas numa caixa: `webapp.registar_parcial` →
  `loadout.registar_marcadas`.** O *"sleevado e na caixa"* e o *"sim, está
  montada assim"* eram um segundo, e esse gravava a **alocação calculada** — o
  que o vault acha, não o que ele viu. O `webapp.marcar_na_caixa` foi-se; os
  actos `montado` (a ligar) e `confirmar` chegam ao mesmo sítio e exigem o mesmo,
  porque uma página aberta no telemóvel antes de hoje ainda manda esses nomes.
  O botão do fim do painel passou a `data-reg` (o `registar()` da barra) em vez
  de `data-act`: dois botões para o mesmo gesto era o que isto veio fechar.
- **Sem lista explícita é 400** (`webapp.SemLista`, apanhado ANTES do `ValueError`
  que dá 409), com a razão escrita para ele ler. Um pedido em branco tem de
  falhar alto: ficar a valer *"então grava tudo"* é exactamente como as duas
  cartas lá foram parar. O motor recusa pela raiz (`ValueError`), para nenhum
  caminho futuro poder gravar uma caixa inteira sem ninguém ter marcado nada.
  Lista vazia e lista ausente são a mesma coisa — as duas querem dizer que não há
  nada confirmado.
- **O «marcar tudo» fica, mas é só um atalho de ECRÃ**: marca as checkboxes
  (visível, reversível, e não dispara o auto-registo). O registo continua a ler
  o `P.feitos` uma a uma.
- **O RESUMO ANTES DE GRAVAR** (`deckboxes.perguntaRegisto`): com cartas por
  marcar, *«Registar N em X — ficam M por marcar. O que lhes faço?»* e três
  saídas: **deixá-las por ir buscar**, **não as tenho** (o *«não encontrei
  estas»*, que corre a seguir ao registo — as marcadas já entraram e o servidor
  recalcula antes de tirar nada) ou **cancelar**, que não escreve. Um `confirm()`
  do browser não chega: são três, e a do meio muda a colecção inteira. O
  auto-registo dos 6 s não vê o resumo, porque só dispara com **M = 0**.
- **O RASTO: `data/registos-caixas.csv`** (fora do Git, como o `vendas.csv`),
  escrito **antes** da base, uma linha por cópia que ENTRA, com *quando, origem
  do clique (`manual`/`auto`/`actualizar`/`arrumar`), caixa, carta, edição,
  língua, acabamento, quantidade, copy_id*. Só o **delta** — repetir a cada
  gravação o que já lá estava fazia o ficheiro deixar de se poder ler. Escrevem
  lá os **três** caminhos que acrescentam à `copy_allocation` (`registar_marcadas`,
  `actualizar_caixa`, `guardar_arrumacao`) e não só o do botão: o que isto serve
  para apanhar é precisamente a escrita que ninguém está à espera. **Se um dia
  uma cópia aparecer dentro de uma caixa sem linha neste ficheiro, é bug.**
- **A correcção de dados de 09/09**: `loadout.corrigir_alocacao` (CLI
  `python -m mtgvault.cli corrigir-alocacao --slot ... --copias ... --motivo ...`)
  tira da `copy_allocation` de uma caixa cópias que ele diz não estar lá, com
  backup (`data/backups/vault-<data>-<etiqueta>.db`) e uma linha em
  `data/correcoes.log` escrita ANTES de a base mexer, como o *Desmontar*. **Não
  mexe nas cópias** — quem as tira de circulação é o *«não encontrei estas»* e
  quem as apaga é o *«vendida»*. É **idempotente**: sem nada para tirar não faz
  backup nem escreve linha.
- **O que fica de fora, e é a saber:** o *"já arrumei tudo"* continua a gravar a
  alocação calculada de todas as caixas. É outro gesto — ele diz que fez o plano
  inteiro, não que confirmou carta a carta — e agora **deixa rasto**; se voltar a
  morder, é aqui.
- Tem teste (`test_registo_marcadas.py`, 7 casos).

**7. ENCOMENDAS: «SÓ A FOTO CRIA CÓPIAS» (André, 2026-09-19, à letra).**
*"consegues, para o magic, criar algo igual ao que criaste para o Riftbound,
mas ao invés de "coleção" colocas para os decks? assim fica mais fácil eu
conseguir organizar-me; até porque assim até conseguia, ao invés de atualizar
sempre a coleção, dizia-te o que ia comprando, e tu só ias pedindo as fotos das
cartas; cada vez que eu adiciono que tenho a carta, fica pendente de foto;
quando coloco a foto, adicionas à coleção"*. Motor em `mtgvault/encomendas.py`,
aba **📦 Encomendas** na Deckboxes, `+`/`−`/«Chegou» nas linhas de compra de
cada caixa, CLI `py -m mtgvault.cli encomendas`, endpoints
`/api/encomenda`, `/api/encomenda-chegou`, `/api/encomenda-desfazer`.
- **A REGRA: o caminho de uma carta é** *a comprar* → `+` **a caminho** →
  «Chegou» **pendente de foto** → a foto entra em `pendentes/` → o import cria
  a cópia, fecha a encomenda e **aloca a cópia à caixa** da encomenda. Nem o
  `+` nem o «Chegou» escrevem em `copies` nem em `copy_allocation`: **uma
  encomenda não é uma cópia** — não conta para o valor, para a venda, para a
  galeria, para a percentagem nem para nada que conte cartas. O que faz é
  **descontar o «a comprar» da caixa** (`encomendas.descontar`, no
  `loadout.allocate`, depois da partilha de compras): `a comprar = falta − a
  caminho − pendente de foto`, nunca abaixo de 0, linha a linha (main primeiro),
  e daí para o «comprar N», o «fechar tudo por X €», as wantlists, o Plano e a
  aba Comprar. `missing`/`got`/`pct` não mexem. Uma encomenda para uma caixa que
  já não pede a carta (a lista mudou, a caixa saiu do config) fica visível com
  o aviso *«a caixa já não a pede»* e **não desconta noutra caixa** — sem regra
  de redistribuição, de propósito.
- **A tabela `encomendas`** (`schema.sql` + `db._migrate`): carta (nome oracle,
  a frente), `set_code`/`collector_number` opcionais (**sem edição = qualquer
  impressão que cumpra a regra da caixa**, que é a omissão do selector — ele
  raramente sabe a edição antes de a carta chegar), `lang`, `finish`, `slot`
  (NULL = colecção), `qty_a_caminho`, `qty_pendente_foto`, `qty_fechada`,
  `copy_ids` (JSON: as cópias que a fecharam), `origem` (a loja), `preco_unit`,
  `notas`, `aviso`. Uma linha por (carta, impressão, língua, acabamento, caixa);
  o `+` de uma linha igual soma. O **material é o da caixa**
  (`loadout.material_da_caixa`: Premodern → PT e ≤ Scourge; SPML/Legacy → EN
  foil; cEDH → EN nonfoil; Duel Commander → foil; Pauper → qualquer; básicas
  isentas) e o `+` **valida** contra ela e contra o catálogo
  (`encomendas.validar`; 409 na página, código 2 na CLI, sempre com o motivo).
- **O rasto é `data/encomendas.log`** (fora do Git, como o `vendas.csv`),
  escrito ANTES da base, uma linha por acção (`+`, `-`, `chegou`, `desfazer`,
  `pendente`, `foto->copia`, `foto-recusada`) com data, carta, impressão,
  quantidade, caixa, origem.
- **O «já a tenho, está no deck» do passo 2 passou a entrar aqui**, directamente
  em pendente de foto (`webapp.registar_falta` → `encomendas.adicionar(…,
  estado=PENDENTE)`; o «anular» é o `−`). É o *"cada vez que eu adiciono que
  tenho a carta, fica pendente de foto"*. O motor antigo
  (`loadout.registar_falta`/`anular_falta`, cópia com «edição por confirmar» +
  linha na `copy_allocation`) **fica no código como caminho antigo**, sem botão
  — apagar é decisão dele; os testes dele continuam verdes. As cópias «edição
  por confirmar» que já existem ficam como estão e aparecem na lista de
  pendentes como *«na base, sem foto»* (`collection.copias_sem_foto`: as sem
  `photo_path` ou com a marca; a 2026-09-19 são 18 cópias — 5 Duress PT, uma
  Underground Sea 3ED…).
- **A CONCILIAÇÃO PELA FOTO vive no `collection.import_csv`** (é comum ao
  `processar_fotos.py` e à tarefa `mtg-fotos-novas`), por esta ordem e de forma
  determinista (desde 2026-09-20 com o passo **(0)** da REVALIDAÇÃO à frente —
  ver o ponto 8): **(i)** cópia «edição por confirmar» da mesma carta →
  `acertar_edicao`, como desde 09/08; **(ii)** encomenda **pendente de foto**
  com o mesmo nome + língua + acabamento (e edição, se a encomenda a tiver),
  **a caixa de maior prioridade primeiro** → `encomendas.conciliar` cria a
  cópia (com `photo_path`, o preço da encomenda se o CSV não o trouxer, a nota
  `encomenda #N`), baixa o pendente, guarda o `copy_id` e **aloca à caixa** se
  a impressão cumprir a regra de material dela — se não cumprir, **não se toca
  na encomenda** (fica aberta, com o aviso *«a foto trouxe X, que não cumpre a
  regra da caixa»*, e continua a descontar: é a carta certa que ainda falta) e a
  linha segue o caminho normal, a cópia entra na Colecção sem caixa. Nunca se
  lava a regra com um registo (ponto 5); **(iii)** cópia da base **sem
  `photo_path`** da mesma impressão exacta (nome + edição + número + língua +
  acabamento), fora as não encontradas e as por confirmar →
  `collection.ligar_foto`: a foto liga-se a ela em vez de a duplicar (com menos
  cópias na foto do que no lote, o lote parte-se e só a parte fotografada ganha
  a foto, levando o seu lugar na `copy_allocation` — `_partir_copia`, o mesmo
  do `acertar_edicao`); **(iv)** senão, entrada normal. Uma linha com
  `quantity` 3 pode acertar 1, fechar 1 e entrar 1: o `copy_id` do resultado
  traz as três (`12,13,14`) e o `arrumar_fotos` liga-as todas à foto arrumada.
  Tudo com linha no `encomendas.log` e no `aplicado.csv`.
- **`pendentes/esperadas.md`** (`encomendas.escrever_esperadas`, escrito pelo
  passo `deckboxes` do `daily` e pelo `webapp.regenerar`; apaga-se quando não
  há nada; fora do Git): o que está pendente de foto, por caixa, com o material
  esperado, mais as «na base, sem foto». O `PROCESSAR_FOTOS.md` manda lê-lo se
  existir — e manda escrever o que a foto MOSTRA, não o que a lista espera.
- **A aba 📦 Encomendas** (parte própria, `data/paginas/deckboxes/
  encomendas.json`; o índice leva só os `totais`): (a) **📷 Pendentes de foto**
  por caixa, com a instrução *«tira a foto e larga-a em `pendentes/` — entra na
  colecção na corrida das 02:30 (`mtg-fotos-novas`)»*, tiles com a imagem da
  carta e «↩ desfazer»/`−`; as «na base, sem foto» sem botões; (b) **🚚 A
  caminho** por caixa e origem, com o preço da linha da caixa (o mesmo
  `card_price`) e os totais; (c) **🛒 Falta encomendar** por caixa = o «a
  comprar» depois do desconto, com o `+` ao lado de cada carta e o «copiar» da
  wantlist de sempre; (d) os totais e os avisos. Botões só no modo edição; a
  informação é a mesma no site publicado (`render_deckboxes.js` tranca-o —
  passou a contar `data-enc`/`data-chegou`/`data-desfazer`/`data-falta` como
  escrita). Na linha de compra de uma caixa: *«a comprar 2 · 📦 1 a caminho ·
  1 pendente de foto»* e os `+`/`−`/«Chegou (N)» (alvos ≥ 40 px). **Uma linha
  toda encomendada fica na wantlist com `0×`** — é lá que vivem o `−` e o
  «Chegou» — e sai do texto copiado e do «N cartas». Na aba Comprar os botões
  só aparecem com UMA caixa escolhida no selector (com todas, a linha junta
  várias caixas e não há a quem encomendar).
- **A CLI é por onde o Claude na nuvem regista o que ele diz no chat**
  («comprei 4 Brainstorm PT para o Stiflenought»): `encomendas listar
  [--json] [--todas]`, `add "<nome>" --caixa <slot> [--qty N] [--set X] [--num
  N] [--lang pt|en] [--finish foil|nonfoil] [--origem "…"] [--preco 1.23]
  [--pendente]`, `chegou "<nome>" --caixa <slot> [--qty N]` (ou `--id`),
  `remover …`, `desfazer-chegou …`.
- **Medido na cópia da base de 2026-09-19** (`_revisao/dbcopy`, o mesmo
  `vault.db` dos dois lados): com zero encomendas o relatório é **igual ao
  cêntimo e linha a linha** — fechar tudo 7 098,03 €, 203 a comprar, 52 a ir
  buscar (25/16/11), 180 a arrumar, venda 244c/1 505,78 €, venda_rl
  63c/4 152,94 €, rl_segurar 37c/4 316,39 €, reservadas 32c/354,49 €, guardar
  2c/14,82 €, as 14 caixas. Um `+` de 2 Meddling Mage no UW Replenish: a caixa
  comprar **4 → 2**, fechar por **8,89 → 5,35 €**, fechar tudo **7 098,03 →
  7 094,49 €**, 203 → **201** a comprar; **95 % fica 95 %**, `copies` e
  `copy_allocation` iguais, venda igual. O «Chegou» não muda um número (só o
  estado). A foto (`Meddling Mage,pls,116,2,nonfoil,pt`) cria a cópia 739 com
  `photo_path`, alocada a `premodern-replenish`, fecha a encomenda
  (`qty_fechada 2`, `copy_ids [739]`): a caixa **95 → 97 %**, 71 → 73 na caixa,
  comprar 2, arrumar igual (já está na caixa). Ver
  `ai-pc/work/revisao/mtgvault-encomendas.md`.

**8. REVALIDAÇÃO POR FOTO DE TODA A COLECÇÃO (André, 2026-09-20, à letra).**
*"quero que quando se clique, ele mostre as cartas, como está a fazer, e que
depois peça a foto das cartas. Quero revalidar todas as fotos agora que vamos
colocar tudo em decks para que nada falhe ou escape; assim o que eu for vender
também vai com foto e vamos pouco a pouco arrumando tudo no devido lugar e bem
feito."* Motor em `mtgvault/revalidacao.py`, config em `colecao_config.json →
revalidacao` (`desde`, `alvo`), aba **📷 Revalidação** e bloco **«📷 Na caixa
— fotografar»** em cada aba de caixa da Deckboxes, CLI `py -m mtgvault.cli
revalidacao [--caixa slot] [--json]` / `revalidacao esperadas --caixa slot` /
`revalidacao parar`, endpoint `POST /api/revalidacao` (`act: alvo|parar`).
Relatório e medições em `ai-pc/work/revisao/mtgvault-revalidacao-0920.md`;
testes em `test_revalidacao.py` (11 casos).
- **É uma CAMPANHA: a partir de `revalidacao.desde` (2026-09-20) NENHUMA cópia
  está validada até uma foto NOVA lhe ser ligada.** O estado vive em duas
  colunas da `copies` — `validado_em` (a data; NULL = por revalidar) e
  `foto_anterior` (o `photo_path` que a foto nova substituiu; a foto antiga
  NÃO se apaga, fica em «fotos processadas» como sempre, e o `aplicado.csv`
  ganhou a coluna `foto_anterior`). Coluna nova = os três sítios; o índice
  `ix_copies_validado` nasce no `_migrate`, depois do ALTER (a armadilha de
  09/09). Uma cópia que NASÇA com foto durante a campanha nasce validada
  (`collection.add_copy`); as que uma foto acerta/liga (`acertar_edicao`,
  `ligar_foto`) ficam validadas por ela. Apagar `desde` desliga tudo (a aba
  desaparece, `rev` é `None`, os `.json` levam `null`).
- **O ESTADO NÃO MUDA UM NÚMERO.** Medido na cópia da base de 2026-09-20, o
  mesmo `vault.db` com o código do `main` e do ramo: fechar tudo **7 157,16 €**,
  **209** a comprar, 0 a ir buscar, **181** a arrumar (104 linhas), venda
  **272c/1 570,73 €**, venda_rl 70c/4 373,90 €, rl_segurar 32c/4 204,76 €,
  reservadas 1c/100,00 €, guardar 2c/14,81 €, as 14 caixas ao cêntimo —
  **iguais**. O progresso (`revalidacao.progresso`, 0,7 s) parte as 1 678
  cópias em caixas **592** (Blue Farm 96, DC 75, Pauper 74, Replenish 66,
  cEDH 65, Stiflenought 58, Modern 53, Oath 49, Elves 24, Enchantress 23,
  Pioneer 9), venda **342**, Caixa RL **78**, resto **666** — a soma É a
  colecção (tem teste). Uma cópia parcialmente numa caixa conta a parte de
  dentro na caixa e o resto onde está.
- **O ALVO (`revalidacao.alvo` = `{tipo: caixa|venda|rl|coleccao, slot, em}`)
  é o que ele está a fotografar AGORA**, escrito pelo botão **«📷 Fotografar
  esta caixa»** (só no 8771) ou pela CLI. Vive no config porque é uma
  preferência e três processos têm de o ler: o `daily` das 08:00 e o
  `webapp.regenerar` escrevem o mesmo `pendentes/esperadas.md` (secção
  **«## Caixa <nome> — por revalidar (N cópias)»** à cabeça, com a impressão
  esperada, a quantidade e o `copy_id`; depois «## Encomendas pendentes» e
  «## Na base, sem foto»), e o import das 02:30 (`mtg-fotos-novas`, que NÃO
  mudou) lê-o para dar preferência às cópias dessa caixa. O
  `PROCESSAR_FOTOS.md` manda o Claude das fotos **escrever a impressão que VÊ,
  não a esperada**, e assinalar em `notes` quando difere. «parar» tira o alvo.
- **A CONCILIAÇÃO ganhou o passo (0), à frente das quatro de 19/09
  (`collection.import_csv`):** a linha casa com uma cópia POR REVALIDAR da
  mesma impressão exacta (nome + edição + número + língua + acabamento) →
  `revalidacao.revalidar`: liga a foto (`photo_path` novo, `foto_anterior`,
  `validado_em`), **não cria cópia**; prefere as cópias do alvo, depois a da
  mesma quantidade, depois qualquer (determinista); com `quantity` maior do
  que o que há por revalidar, o resto segue (i)→(iv). As «edição por
  confirmar» ficam para o (i), que também as valida. O que entrar por (iv)
  com a campanha ligada fica marcado **«nova nesta campanha (<data>)»** nas
  `notes` — é a lista do que apareceu nas fotos sem cópia na base.
- **DISCREPÂNCIA (0b): não há cópia igual à foto, mas o alvo tem uma cópia por
  revalidar da MESMA CARTA noutra edição/acabamento/língua → é uma correcção,
  não uma carta nova** (`revalidacao.corrigir`). A cópia da caixa passa a ser
  o que a foto prova, com a marca **«corrigida pela foto em <data>: NEM #17
  nonfoil en → NEM #17 foil en»** nas `notes` e a linha em
  **`data/revalidacao.log`** (fora do Git), escrita ANTES da base; o backup é
  o que o `mtg-fotos-novas` já faz antes de cada import. Se depois disso a
  cópia deixar de cumprir a regra de material da caixa
  (`loadout.lots(ids=[…])` → `contradiz`), **sai da `copy_allocation`** com
  «saiu da caixa X: <porquê>» nas `notes` — nunca se lava a regra com um
  registo (ponto 5). A decisão de 09/09 mantém-se: **nada se apaga**; uma
  cópia que nunca receba foto continua por revalidar e visível.
  **Consequência a saber:** a cópia igual à foto ganha sempre, esteja onde
  estiver — se a caixa-alvo tem a carta noutra edição e a Colecção tem a
  edição da foto, liga-se a da Colecção e a da caixa fica por revalidar (é o
  que a ordem diz; a alocação não se move). Simulado na cópia da base com
  4 fotos: Abeyance WTH igual → cópia 461 validada; Abeyance «WC97» → cópia
  712 partida, a nova corrigida e fica na caixa; Exalted Angel «G06» → cópia
  517 partida, a nova corrigida e **sai** da caixa (pós-Scourge); Llanowar
  Elves LEA → nova, marcada. `copies` 737→740 linhas (1 678→1 679), alocação
  411→410, Replenish 66→65 cópias (2 validadas, 1 corrigida), venda
  1 570,73→1 569,10 € (só porque a cópia mudou).
- **A PÁGINA:** em cada aba de caixa, a lista **«📷 Na caixa — fotografar»**
  (uma cópia por linha, por COR como o binder, com 📷 «por fotografar» / ✓
  «validada <data>» / ⚠ «corrigida pela foto», a barra «validadas N/M» e o
  botão); o selo **📷N** na miniatura da grelha e no `title`; o chip
  «validadas N/M» no cartão da fila. Na aba **Vender**, a coluna 📷/✓ por linha
  (uma linha junta lotes: «📷 2/4»), «📷 N/M validadas» por bloco, o filtro
  **«📷 Só validadas»** (troca a tabela, o CSV e a estante para a versão por
  cópia com foto — `venda.relatorio` traz `csv_validadas`/
  `texto_estante_validadas`), e o CSV de stock com a coluna **`Foto`**
  (`validada <data>` / `por revalidar`) no formato predefinido; no formato
  aprendido do ficheiro dele não se acrescenta coluna (o site tem de o
  aceitar tal e qual) e a informação vai no comentário. `vender --exportar
  --so-validadas` e `POST /api/venda-export {so_validadas}` escrevem só essas.
  A aba **📷 Revalidação**: o total, o alvo com a instrução, cada caixa (barra
  + botão), a Venda / Caixa RL / Colecção (listas por cor, com o botão), «entrou
  hoje», «corrigidas pela foto» e «novas nesta campanha». Site publicado só
  leitura (o `render_deckboxes.js` conta `data-rev`/`data-rev-parar` como
  escrita). Dados na parte `deckboxes/revalidacao.json`; o índice leva os totais.
- **CORRIGIDO DE CAMINHO:** o «afinal encontrei» da aba Não encontradas usava
  `data-enc`, o mesmo atributo dos `+`/`−` das encomendas, e o `ligar()` deixava
  o segundo `onclick` ganhar — o `+` de uma encomenda chamava o `encontrei`.
  Passou a `data-encontrei` (o `test_nao_encontrei` tranca-o).

**9. LISTA PADRÃO E RESERVA POR CAIXA; O CLOUD (DUEL COMMANDER) TEM AS DUAS
(André, 2026-09-20, à letra).** *"quero que olhes também com muita atenção para
a lista de Duel-Commander de Cloud; preciso urgentemente de estabelecer uma
lista padrão para completar, e ver algumas cartas que poderão ser possível
entrar; não quero ter que vender cartas que depois me poderão fazer falta."*
Motor em `mtgvault/padrao.py` (só config) + o que o `loadout` lê dele; aba da
caixa na Deckboxes (blocos **📌 Lista padrão** e **🛡️ Reserva (N)**), endpoint
`POST /api/padrao`, CLI `py -m mtgvault.cli padrao <slot> listar|fixar|add|
tirar|voltar` e `reserva <slot> listar|add|remover`. Relatório e medições em
`ai-pc/work/revisao/mtgvault-cloud-padrao-0920.md`; testes em
`test_padrao_reserva.py` (5 casos).
- **A LISTA PADRÃO reutiliza o «vou montar este»** (v5): fica em
  `listas_escolhidas[slot]` com `padrao: true`, `origem` e `escolhido_em`, e a
  caixa passa a `fonte: "escolhido"`, `ref: <slot>`, com o que tinha em
  `_antes`. O motor não ganhou um caminho novo — `_cards_from_escolhido` já
  lia isto — e o **`daily` nunca escreve em `listas_escolhidas`** (só o
  `webapp.py` e a CLI): o `my_decks.refresh` continua a reescrever o deck
  «Cloud (Duel Commander)» na tabela `decks` todas as noites, e a caixa deixou
  de o ler. A diferença para o botão do top-N: o **nome da caixa não muda** e
  a lista vem dele. `resolve_slots` põe `s["padrao"] = {desde, origem}` e a
  nota diz *"lista padrão fixada em <data> · <origem>"*. **«Voltar ao
  consenso»** é o mesmo desfazer do «já não vou montar este» (`_antes`), e no
  8771 é em dois toques — perde a lista fixada. Fixar por cima de uma padrão
  já fixada **não esquece o `_antes`**. `configio.escrever` passou a escrever
  as `listas_escolhidas` com **cada carta numa linha** (`CARTAS_UMA_LINHA`):
  eram cinco linhas por carta, 380 por caixa.
- **A RESERVA é `caixas[].reserva`** (nomes oracle, a frente). As cópias
  dessas cartas — **cumpram ou não a regra de material** da caixa, foi assim
  que ele o pediu — saem de `venda`/`venda_rl` para **`guardar`**, com o motivo
  `loadout.RAZAO_RESERVA` + o nome da caixa (*"reserva da caixa Cloud (Duel
  Commander)"*) e o `porque_venderia` ao lado, **antes** do filtro da RL (uma
  carta reservada não se vende, subisse ou não). O `guardar` já ficava fora do
  CSV de stock e da estante (`venda.fora_da_exportacao`). **O que a reserva
  NÃO faz:** não aloca, não conta para a %, não compra — é só *"não vendas
  isto"*. O bloco da caixa (`loadout.reserva_da_caixa` → `s["reserva_linhas"]`,
  parte pesada `reserva` no JSON) diz, por carta, quantas tem, **onde** cada
  cópia está (gaveta, ou a caixa a que a alocação a deu) e se **serve** a caixa
  tal como está (`_porque_nao`, a mesma régua da alocação — *"não serve: não é
  foil (existe em foil: NEM 2000)"*).
- **Os nomes VALIDAM-SE no catálogo** antes de se escrever (`padrao.
  nome_no_catalogo`: `name = ?` primeiro, `LIKE 'x // %'` para as duas faces,
  `lower()` como recurso) — no 8771 é 409 com o motivo, na CLI código 2. Um
  nome mal escrito na lista era uma falta que nunca fechava.
- **O CLOUD, aplicado neste dia pela CLI**: lista padrão de **75 não-básicas +
  24 Snow-Covered Plains** (99 cartas) tirada das **83 listas mono-brancas com
  Cloud, Midgar Mercenary** que contam (mtgtop8, 22/08–19/09; as outras 100
  com a carta são GW/Jeskai/Boros, fora por identidade de cor), regra *≥ 50 %
  entram; 40–50 % as que ele tem em foil* — **verificada contra a base carta a
  carta, desvio máximo 1 ponto**. Reserva de **20**: as 12 da ordem (Extraction
  Specialist, Path to Exile, Lay Down Arms, Helitrooper, Cid, Get Lost, Thalia
  HC, Armageddon, Mirrex, Lavaspur Boots, Touch the Spirit Realm, Burrenton
  Forge-Tender), a Sunpearl Kirin (*"ficam na reserva as que ele tem"*) e as 7
  nonfoil EN da lista padrão (Parallax Wave, Enlightened Tutor, Reverent
  Mantra, Crystal Vein, Talon Gates, Starfield Shepherd, Helping Hand).
- **Medido na cópia da base de 2026-09-20** (o mesmo `vault.db` dos dois
  lados): o Cloud passa de **77 % (75/97, comprar 22, 736,26 €)** a **79 %
  (78/99, comprar 21, 656,17 €)**; fechar tudo **7 157,16 → 7 077,07 €**, 209
  → **208** a comprar, arrumar 181 → **184** (as 3 cópias novas que o Cloud
  tira), **venda igual** (272c/1 570,73 € + 70 RL/4 373,90 €, guardar
  2c/14,81 €) — **a reserva não tira hoje nenhuma cópia da venda**: nenhuma
  das 20 estava lá (são singletons dentro do playset). As outras 13 caixas ao
  cêntimo. Dos 21 a comprar: **8 que não tem** (Flagstones, Abandoned Air
  Temple, Erode, Mana Tithe, Disruptor Flute, Reprieve, Static Prison,
  Razorgrass Ambush — 38,91 € a preço mínimo, a Razorgrass sem preço), **7 só
  nonfoil EN** (3 livres como substituto, 4 dentro das caixas de cEDH), **4 PT
  da era** (Rishadan Port, Tangle Wire, Cataclysm, Mishra's Factory — *"PT da
  era Premodern (trancada ao Premodern)"*: o motor já os dava como falta e a
  wantlist pede-os **foil**, confirmado) e **2 foil dentro da caixa do Modern**
  (Shadowspear, Skateboard — regra de 19/09, *"tens 2 no Modern"*). A Parallax
  Wave foil (388,96 €) e a Talon Gates foil (101,83 €) são 75 % do custo. A
  **Witch Enchanter** vinha na ordem como *falta* e ele tem 4× MH3 foil — a
  base ganha. **Pioneer (só verificação):** o Izzet Prowess (4362, 81 listas)
  é o **4.º** a 39 % (28/72 cópias, 44 a comprar, 73,64 €), atrás de Jeskai
  Revelation 51 %, Izzet Pop Quiz 44 % e Izzet Vivi 41 % — a página mostra
  `metagame_top_n: 3`, e a % é por CÓPIAS em material certo (foil EN) depois
  da alocação, não por cartas distintas. A regra não se mexeu; `metagame_top_n:
  4` no config mostrava-o.
- **Consequências a saber:** (a) o `ref` do Cloud passou a `duel-commander`,
  por isso `s["vigiado"]` (que lê `decks_vigiados` pelo `ref`) fica falso —
  sem efeito, é a única caixa do grupo; (b) o `meta_coverage.owned_available`
  continua a descontar o deck «Cloud (Duel Commander)» da tabela `decks` (a
  lista do McWinSauce), não a padrão — é a cobertura, não a caixa; (c) a
  secção em camadas do `colecao_cor` (`commander_decks.tiers`) é o consenso e
  não a caixa, e não mudou.

**10. A FEIRA: MOEDA DE TROCA vs. O QUE QUERO TRAZER (André, 2026-09-20, à
letra).** *"como vou ter um objetivo de ir ao RC "trocar" cartas nas bancas,
fazemos logo uma projeção do que vou levar como moeda de troca para o que quero
trazer; indico-te a wantlist e prováveis vendors que lá estarão, que poderão
ter os preços das cartas no market, e avaliamos; será sobretudo cartas que eu
preciso para completar decks."* Motor em `mtgvault/feira.py` (só config — nada
toca na base), aba **🎒 Feira** na Deckboxes (parte própria
`deckboxes/feira.json`; o índice leva os totais e o saldo, que é o subtítulo
da aba), endpoint `POST /api/feira`, CLI `py -m mtgvault.cli feira [--json]`
+ `feira wantlist add|remover|listar` / `vendor add|remover|listar` / `taxas`
/ `levo|nao-levo <chave>` / `pode-ter <carta> <vendor> [--nao]`. Config em
`colecao_config.json → feira`. Relatório e medições em
`ai-pc/work/revisao/mtgvault-feira-0920.md`; testes em `test_feira.py` (8
casos). **A wantlist e os vendors dele ainda não chegaram** — a estrutura está
pronta com o que a base já sabe.
- **LEVAR (a moeda de troca) é a lista de venda de hoje** (`venda` +
  `venda_rl`, as duas saídas que se vendem; as outras cinco são decisões
  tomadas ou por tomar), lida das MESMAS linhas por cópia da exportação
  (`venda.linhas_export`) — o Trend por cópia é o `card_price` da aba Vender e
  o 📷 é o da revalidação, não uma segunda conta. Uma linha por impressão e
  sítio, por COR (como o binder). **Duas taxas**, `feira.taxa_dinheiro`
  (omissão **0,55**) e `feira.taxa_troca` (omissão **0,70**): o que uma banca
  costuma dar pelo Trend em dinheiro e em crédito de troca. **São estimativas
  dele, não dados** — nenhuma banca publicou nada; a página di-lo ao lado dos
  campos e ele afina-as no 8771 (`act: taxas`, aceita `55` ou `0.55`).
- **«levo / não levo» fica no CONFIG, não no browser** (`feira.nao_levo`, uma
  lista de chaves `nome|EDIÇÃO|língua|acabamento` — `feira.chave`): a decisão
  toma-se no PC e vai no telemóvel. A chave é a IMPRESSÃO e não a
  `chave_venda` (que leva o sítio e o motivo, que mudam de um dia para o outro
  e apagavam a marca sem ninguém lhe tocar). Uma linha marcada fica à vista,
  riscada, com `leva_q: 0`, e sai dos totais.
- **«só validadas» é o filtro predefinido** (`feira.so_validadas: true`):
  com a campanha de revalidação ligada só vão as cópias com foto desta
  campanha — *"o que eu for vender também vai com foto"* —, e o que fica de
  fora está DITO (`fora_foto`/`fora_foto_trend`, na página, no texto e na
  CLI). Sem campanha o filtro não corta nada. **Consequência a saber: na base
  de 2026-09-20 a moeda de troca é ZERO** — as 342 cópias da venda
  (5 944,63 €) estão todas por fotografar; a página avisa e manda fotografar
  ou passar a «Tudo».
- **TRAZER = o «a comprar» das caixas DEPOIS das encomendas** (`s["missing"]
  [].comprar`, a lista padrão do Cloud incluída — a mesma lista da aba
  Comprar, com `m["unit"]`, o preço mínimo no acabamento da caixa, e o
  material `req_compra`/`marca_compra`) **+ a wantlist manual**
  (`feira.wantlist`: nome, `q`, `lang`, `finish`, `max` = preço máximo por
  cópia, `slot`, `notas`). **Sem duplicar:** uma manual para a MESMA carta e a
  MESMA caixa funde-se na linha automática (`origem: "caixa+manual"`, `q` =
  o máximo das duas, o `max`/`notas` da manual); uma manual sem caixa é uma
  compra para a Colecção, na sua linha, ao preço da língua/acabamento que
  disser (omissão nonfoil). `wantlist_add` SUBSTITUI a entrada (carta, caixa)
  em vez de somar — escrever «2 Brainstorm» duas vezes quer dizer 2. Os
  nomes validam-se no catálogo (`padrao.nome_no_catalogo`; 409 no 8771,
  código 2 na CLI). **Nenhuma consulta ao Cardmarket parte do código**: os
  preços são os do `card_price`/`price_latest` que a base já tem.
- **VENDORS** (`feira.vendors`: nome, notas, utilizador Cardmarket, site) e,
  por CARTA, a marca *"o vendor X pode ter"* (`feira.pode_ter`: `{carta:
  [vendor, …]}`) — por carta e não por linha, porque vale para a linha
  automática e para a manual. É tudo manual: só ele sabe quem lá vai estar, e
  os preços dos vendors vê-os ele. Tirar um vendor tira as marcas dele.
- **A PROJECÇÃO**: total a levar (Trend, dinheiro, troca), total a trazer
  (mínimo e, com preço máximo escrito, *"com os teus máximos"* — onde não há
  máximo vale o mínimo), o **saldo** nas duas taxas (`saldo.dinheiro`/`troca`
  = levar − trazer mínimo; `*_max` contra os máximos), e por caixa (mínimo,
  máximo, saldo em troca e % da troca que a caixa come). Os dois textos para o
  telemóvel — «Levar» por cor com preço e 📷, «Trazer» por caixa com material
  e preço — e o `texto_cardmarket` (`// caixa` entre blocos) saem do Python
  (`feira.texto_levar`/`texto_trazer`), os mesmos na página e na CLI. Site
  publicado só leitura (o `render_deckboxes.js` conta `data-feira` como
  escrita).
- **Medido na cópia da base de 2026-09-20** (o mesmo `vault.db` dos dois
  lados): a alocação e a venda **não mexem** — fechar tudo 7 077,07 €, 208 a
  comprar, 184 a arrumar, venda 272c/1 570,73 € + RL 70c/4 373,90 €, iguais
  com e sem o bloco `feira`. A projecção de hoje: **trazer 208 cópias /
  7 077,07 €** (3 sem preço; por caixa: Cloud cEDH 4 477,97 €, Oath 907,57 €,
  Cloud DC 656,17 €, Blue Farm 547,70 €, Pioneer 185,71 €, Modern 124,04 €,
  Enchantress 119,25 €, Elves 45,58 €, Replenish 13,08 €), **levar 0** com o
  filtro da foto (342 cópias / 5 944,63 € por fotografar; com «Tudo»: 141
  linhas, Trend 5 944,63 € → dinheiro 3 269,59 € · troca 4 161,21 €, RL
  70c/4 373,90 €, o Lion's Eye Diamond MIR ×2 a 486,75 € à cabeça), saldo em
  troca **−7 077,07 €** hoje (−2 915,86 € se fotografar tudo; sem o Cloud
  cEDH, que sozinho come 107,6 % da troca, sobrava +1 562 €). A Mox Diamond
  PT do Oath (847,76 €) e o Cloud cEDH são o grosso do trazer.
  `feira.projeccao` custa 0,03 s por cima do `report`.

**11. AS CARTAS EM IMAGEM, NÃO SÓ O NOME (André, 2026-09-20, à letra).** *"cada
deck poderia ter as cartas visualmente ao invés de só o nome?"* — e a regra
geral dele, de 16/09: *"gosto de ter em imagem da carta e não apenas texto, faz
algo visualmente apelativo"*. Relatório e medições em
`ai-pc/work/revisao/mtgvault-visual-0920.md`; testes em `tests/test_visual.py`
(12 casos) e o `render_deckboxes.js` passou a desenhar cada aba nos DOIS modos
(`lista:<aba>` no dump). Só a página mudou: **nenhum número da alocação, da
venda ou da feira mexe** (medido na cópia da base de 2026-09-20: fechar tudo
7 077,07 €, 208 a comprar, venda 272c/1 570,73 € + RL 70c/4 373,90 €, iguais).
- **O que já era imagem** antes: a grelha de três estados da aba da caixa, os
  tiles das Encomendas (19/09) e a grelha das Sugestões. **O que era texto**:
  o passo 1 e 2 do painel Montar, as básicas, as destinadas a outra caixa, o
  «já na caixa», a Reserva e a lista «Na caixa» da Revalidação (20/09), a aba
  Comprar, a aba Vender (tabela) e a estante da saída, a Feira, o Arrumar e o
  «actualizar decks montados», a aba Revalidação (Venda/RL/Colecção). **Agora
  é tudo a MESMA componente**: `deckboxes.tileHTML` (JS), com `grelhaHTML`
  (uma grelha) e `grelhaPorCor` (com o cabeçalho de cor, como o binder). A
  informação vai EM CIMA da imagem e não escondida no `title`: o chip do
  estado (`.tlr`: ✓ tens · tens, não serve · 🛒 comprar N · 🚚 a caminho · 📷
  pendente de foto · 📷 por fotografar · ✓ validada · ⚠ corrigida · 🛡️
  reserva · ✕ não levo · tirar/→ caixa), a quantidade (`.tlq`), o material
  (`.tlm`: edição, ✨, língua), o preço quando é compra ou venda (`.tlx`), e
  os botões que a lista tinha no rodapé (`.tla`) — a checkbox do passo 1
  (28 px, canto superior direito, com o MESMO `data-id` de `vistoId`, por isso
  a barra «N de M» conta na mesma), o «já a tenho», os `+`/`−`/«Chegou», o
  «vendida» (dois toques), o «levo», o ✕ da reserva, o selector de vendor.
  O `ligar()` não sabe se está a olhar para uma linha ou para um tile: os
  `data-*` são os mesmos, e os pedidos aos endpoints também (tem teste).
  Toque na imagem = os detalhes de sempre (`tocarCarta`).
- **A imagem é a da IMPRESSÃO EXACTA** que ele tem: o `sid` da cópia, que
  passou a viajar no payload em todo o lado (`lots()` já o tinha; o
  `reserva_da_caixa`, o `copias_por_confirmar`, o `venda._detalhe_copias`/
  `linhas_export`, o `feira.levar` e o `plano_arrumacao` ganharam-no). Numa
  carta que FALTA não há cópia, e a imagem honesta é a da **impressão mais
  barata no acabamento da compra** — `loadout.impressao_mais_barata`, a
  mesma consulta do `card_price` com `ORDER BY` em vez de `MIN`, para o preço
  ao lado e a imagem serem da mesma impressão. Só nas cartas que a base cota;
  sem preço fica a impressão de sempre do nome (`paginas.img_map`). **Sem
  `sid` nenhum** (a carta não está no catálogo) fica o NOME no quadrado
  (`.tlnm`), nunca um buraco; e cada `<img>` leva `onerror="this.remove()"`
  — a imagem que falhe na rede deixa o nome à vista.
- **O interruptor «Imagens / Lista»** está no topo de cada aba com cartas (na
  aba da caixa, na barra de filtros). «Lista» é exactamente a página de antes
  de 20/09 (as linhas `.mv`, os `<li>` da wantlist, a tabela da venda), com
  os mesmos `data-id`. A omissão é **imagens**; o valor vive em
  `colecao_config.json → deckboxes.vista` (`deckboxes.vista_config`, escrito
  pelo `POST /api/vista` do 8771 — `webapp.gravar_vista`, 409 fora de
  `imagens`/`lista`) e, por cima dele, no aparelho (`P.imagens`, o
  `localStorage`; no site publicado é só aí). No config porque é uma
  preferência dele e o PC e o telemóvel têm de dizer o mesmo.
- **Desempenho**: `loading="lazy"`, `decoding="async"`, o tamanho `small` do
  Scryfall (146×204) escrito no `<img>` e `aspect-ratio:.716` no quadrado —
  a grelha não salta enquanto as imagens chegam. 3 colunas a 640 px
  (`repeat(3,minmax(0,1fr))` — com `1fr` a grelha saía do ecrã: um `<select>`
  não encolhe abaixo da opção mais comprida; medido a 400 px numa captura do
  Chrome headless), `minmax(120px,1fr)` em ecrã largo, `.big` para as imagens
  grandes. **As grelhas grandes vêm aos poucos** (`MAX_TILES = 60` por grelha
  ou por lista de cores, com um botão «⬇ mostrar as outras N» —
  `GRELHAS_ABERTAS`), só nas abas SEM procura (Vender, Feira, Revalidação,
  Arrumar, Encomendas, Sugestões, Comprar não): na aba da caixa a procura
  filtra o que está desenhado e um tile por desenhar era uma carta que ela
  não achava. A decisão de 15/09 (os dados à parte, por secção) não mudou:
  o JSON de cada parte só ganhou o `sid` (a maior, `revalidacao.json`,
  fica em 278 KB; a `caixa-duel-commander` 104 → 115 KB); o `deckboxes.js`
  passou de 198 a 224 KB, cacheável pelo `?v=`.
- **Medido na cópia da base de 2026-09-20** (Chrome headless a 400 px,
  `render()` + layout, o melhor de 3): a caixa maior (Cloud DC, 227 tiles)
  **10,7 → 17,0 ms**, Vender 34,7 → 33,7 ms (211 tiles, com o tecto), Feira
  26,1 → 20,7 ms, Encomendas 9,6 → 14,5 ms, Todas 2,6 → 2,7 ms (não tem
  cartas) — tudo muito abaixo dos 300 ms a partir dos quais se virtualizava.
  O `payload` no modo edição custa o mesmo (3,3 s, dominado pelas edições do
  «já a tenho»); no publicado 0,63 s. Os `sid` estão todos preenchidos: 0
  cartas sem imagem nas 11 caixas, na venda (121 linhas), na feira (141 +
  132) e nas compras (124).
- **Consequências a saber:** (a) os testes que liam a tabela da venda ou as
  linhas `.mv` (`test_paginas_loadout`, `test_revalidacao`, `test_incompletos`,
  `test_encomendas`, `test_telemovel`) passaram a lê-las em `lista:<aba>` e a
  verificar o tile no modo de omissão; (b) o `❓ deck por escolher`, o Plano,
  Todas/Montados/Para montar e as Não encontradas ficaram como estavam (não
  têm lista de cartas, ou já têm a foto); (c) o `title` continua a existir
  em cada tile — é o que o `tocarCarta` mostra ao toque.

**12. PIONEER: SÓ O GREASEFANG E O JESKAI CONTROL (André, 2026-09-21, à
letra).** *"Pioneer apenas Greasefang e jeskai control
https://mtgtop8.com/event?e=90797&d=889461&f=PI"*. Recorta, só para o
Pioneer, a decisão de 2026-09-07 (*"dás-me só o top-3 decks que estou mais
perto de concluir para os formatos Standard, Pioneer, Legacy"*) — para o
Standard e o Legacy essa continua inteira. Relatório e medições em
`ai-pc/work/revisao/mtgvault-pioneer-0921.md`; testes em
`test_pioneer_jeskai.py` (5 casos). Só config e a leitura dele: **o motor não
mudou uma linha.**
- **A segunda caixa é `pioneer-jeskai`** («Jeskai Control», formato pioneer,
  grupo SPML — EN foil, RL pode ser nonfoil, «só foil se existir» —, dedicada
  e permanente como todas), a seguir ao Greasefang no config e na ordem da
  alocação (Greasefang é a mais antiga; `prioridade` 13 → 14, o Legacy passou
  a 15 — está vazio, não muda nada). **A lista é FIXA pelo mecanismo da lista
  padrão** (ponto 9, `padrao.py`): `listas_escolhidas["pioneer-jeskai"]` com
  `padrao: true`, `escolhido_em: 2026-09-21` e `origem` = o URL dele — é a
  `decklists.id 18876` (McWinSauce, «Pioneer event - MTGO RC Qualifier»
  13/09/2026, 5–8.º), **60 main + 15 side, 37 linhas, confirmada linha a
  linha contra o export `.dec` do mtgtop8** nesse dia. O side vai separado
  como em todas as caixas (decisão de 08/09: o Thor joga 2 no main + 1 no
  side e são duas linhas). Aplicada pela CLI (`padrao pioneer-jeskai fixar
  --ficheiro … --origem …`), nunca à mão no JSON; o `daily` não a pisa (não
  escreve em `listas_escolhidas`).
- **A reserva da caixa** (`caixas[].reserva`, 8 cartas) são as **nonfoil EN
  que ele já tem das cartas da lista**, para não irem à venda até ele ter as
  foil: Thor, God of Thunder (3× MSH), Jeskai Revelation (4× TDM), Tablet of
  Discovery (4× SOS), Great Hall of the Biblioplex (4× SOS), Combustion
  Technique (2× TLA nonfoil), It'll Quench Ya! (1× TLA nonfoil) — as seis da
  ordem, verificadas na base — **mais duas que a ordem não nomeou e cabem na
  mesma regra**: Price of Freedom (4× TLA nonfoil) e Soul-Guide Lantern (2×
  SLD nonfoil). Hoje nenhuma ia à venda (cabem no playset; as que a lista
  pede são substitutos — `guardar`, *"serve Jeskai Control"*): a reserva é
  para o dia em que as foil chegarem e as nonfoil passarem a excedente.
- **`colecao_config.json → formatos_decididos: ["pioneer"]`** é o que tira o
  top-N ao Pioneer. `metagame.formatos_decididos()` lê-o e `metagame.secoes()`
  dá o modo EFECTIVO de cada secção (`top` → `caixas` para um formato
  decidido); o `SECOES` fica como ele o deu em 2026-09-07. Lêem de lá os
  três sítios onde havia candidatos: a **secção do Metagame** (mostra as duas
  caixas, com o `lead` a dizer porquê e o rodapé a listar quem é top-N e quem
  mostra caixas — sai da mesma lista, escrito à mão dizia *"Standard,
  Pioneer e Legacy"*), a **Deckboxes** (`_candidatos` percorre
  `metagame.formatos_top()`, logo as duas abas do Pioneer ficam sem o bloco
  «o que estás mais perto de concluir» e sem «vou montar este») e o
  **`/api/escolher`** (recusa `escolher` para uma caixa de um formato
  decidido — uma página aberta ontem no telemóvel ainda tem o botão). **O
  código do top-N não se apagou**: tirar o formato da lista devolve-lhe os
  candidatos (tem caso de teste). O Standard e o Legacy continuam com 3.
- **Medido na cópia da base de 2026-09-21** (o mesmo `vault.db` dos dois
  lados): a caixa nova **49 % · 37/75 · comprar 38 · 84,67 €** (3 Riverglide
  Pathway sem preço); fechar tudo **7 028,04 → 7 112,71 €** (+84,67 = a
  caixa), comprar **201 → 239** (+38), arrumar **190 → 224** (+34 = as cópias
  que a Jeskai tira da gaveta; as 3 Island são da pilha de básicas), venda
  **273c/1 563,40 € igual**, venda_rl 74c/5 485,87 € igual, rl_segurar
  28c/3 081,19 € igual, reservadas 1c/100 € igual, guardar 1c/14,75 € igual,
  **as outras 14 caixas ao cêntimo**. Dos 38 a comprar: 3 Hallowed Fountain
  (os 4 EXP foil estão na caixa do Modern — regra de 19/09, *"tens 4 no
  Modern"*), 2 Thor, 4 Jeskai Revelation, 4 Tablet, 3 Great Hall, 1
  Combustion Technique + 1 no side, 1 It'll Quench Ya!, 1 Price of Freedom,
  1 Soul-Guide Lantern (todas *"não é foil (existe em foil: …)"*), 1 Annul
  (os 4 USG são PT da era, trancados ao Premodern), 4 Divide by Zero, 3
  Riverglide Pathway, 1 Deserted Beach, 1 Pop Quiz e 6 cartas de side que não
  tem. Já EN foil: Abandon Attachments, Accumulate Wisdom, Firebending
  Lesson, Gran-Gran, Iroh's Demonstration, Spell Pierce, Spirebluff Canal,
  Steam Vents, Stock Up, Riverpyre Verge, Ghost Vacuum, Improvisation
  Capstone.

**13. A FOTO DA DECKBOX FÍSICA DE CADA CAIXA (André, 2026-09-21, à letra).**
*"quero poder tirar foto à deckbox onde vai ficar cada deck, para ser
referência também"*. Uma foto por caixa (`slot`) — a caixa de plástico na
estante, não as cartas. Motor em `mtgvault/fotocaixa.py` (a única escrita é
`guardar`), endpoint `POST /api/foto-caixa?slot=…` (a foto vai tal e qual no
corpo, com o token), passo `fotos-caixas` do `daily` (antes do `deckboxes`),
`recolher_fotos_de_caixas` no `webapp.py` (a cada pedido do índice). Relatório
em `ai-pc/work/revisao/mtgvault-foto-caixa-0921.md`; testes em
`test_foto_caixa.py` (5 casos). **O motor de alocação não mudou uma linha.**
- **DOIS CAMINHOS DE ENTRADA, UM DESTINO.** (a) No 8771, na aba da caixa, o
  botão **«📦 Foto da deckbox»** — um `<input type="file" accept="image/*"
  capture="environment">`, que no telemóvel abre a câmara — envia o ficheiro
  em bytes (não JSON: o `do_POST` lê o corpo em bytes ANTES de tentar
  decifrá-lo, e um corpo acima de `fotocaixa.MAX_BYTES` (25 MB) é 413 sem se
  ler). (b) Largar **`pendentes/deckboxes/<slot>.jpg`**: o `daily` e o modo
  edição recolhem-na (`fotocaixa.recolher`); o ficheiro MOVE-SE (é o próprio
  original), um nome que não é slot fica lá e diz-se porquê (no `webapp.log`
  uma vez — `_FOTOS_IGNORADAS` memoriza nome+tamanho+mtime — e no `[ok]
  fotos-caixas` do daily). **É uma SUBPASTA de propósito**: o
  `mtg-fotos-novas` (`PEND.iterdir()` + `is_file()`) e o
  `collection.arrumar_fotos` (`pend / nome`) só olham para ficheiros na RAIZ
  de `pendentes/` — uma foto de uma caixa de plástico nunca chega ao Claude
  que cataloga cartas. O teste prova-o **com os próprios programas** (importa
  o `run.py` da tarefa com só a subpasta cheia e espera *"sem fotos novas"*),
  e o `PROCESSAR_FOTOS.md` e os dois `LEIA-ME` dizem-no.
- **ONDE FICA, E PORQUÊ EM TRÊS SÍTIOS.** O ORIGINAL em
  `data/deckboxes/<slot>.<ext>` (pelo `db.pasta_dados()`, como o
  `arquetipos.json`; fora do Git — `data/deckboxes/` está no `.gitignore`); a
  VERSÃO REDUZIDA (≤ 800 px, JPEG, ~60–150 KB, orientação EXIF respeitada) em
  **`assets/deckboxes/<slot>.jpg`, DENTRO do repositório** — é a **excepção
  consciente** à regra «não guardar imagens» do *Não fazer* (essa regra é para
  a BASE DE DADOS; quinze ficheiros de 100 KB no Git são aceitáveis, e sem
  eles o site publicado não tinha a foto); e a DATA em `colecao_config.json →
  caixas[].foto` (`{em, ficheiro}`). **A verdade para a página é o ficheiro
  em `assets/`** (`fotocaixa.info`): uma data sem ficheiro (um clone antes do
  commit) é «sem foto», um ficheiro sem data mostra-se sem data. O URL leva
  `?v=<hash do conteúdo>` — cacheável, muda quando a foto muda. **Substituir
  guarda a anterior** em `data/deckboxes/anteriores/<slot>-<data>.<ext>`.
  **Nunca se apaga nada.** A validação é pelos PRIMEIROS BYTES (JPEG, PNG,
  WebP, HEIC), nunca pelo nome, e vem — com a redução — ANTES do primeiro
  ficheiro tocado: uma recusa (409) não escreve nada. A redução precisa do
  **Pillow** (entrou no `requirements.txt`; neste PC já estava, 12.2.0); sem
  ele o original copia-se tal e qual para `assets/` e a resposta di-lo
  (`aviso`), excepto HEIC, que os browsers não abrem — aí é recusa. Medido:
  uma "foto" de 4000×3000 / 9 MB → 63 KB em 0,11 s.
- **A PASTA VAI NO `git add` DO `daily.yml` E NO `EXTRA_COMMIT` DA TAREFA
  `mtgvault-daily`** (é uma pasta, como `data/paginas`; o `LEIA-ME.md` lá
  dentro é o que garante que o caminho existe no checkout da cloud — um
  `git add` a uma pasta que não existe falha). Sem isto no commit o site
  publicado mostra «sem foto» numa caixa que a tem.
- **ONDE APARECE.** A MINIATURA (44 px, `fotoThumbHTML`) ao lado do nome no
  cartão da fila (Todas / Montados / Para montar — dentro do `<button
  class="mini">`, por isso é só uma `<img>`) e na aba **📷 Revalidação** ao
  lado do progresso de cada caixa; no CABEÇALHO da aba da caixa a foto maior
  (`fotoCaixaHTML`, ≤ 200 px de altura) com a data e **toque para ampliar**
  (`ampliarFoto`: um véu com a foto inteira, toque ou Esc fecha — só leitura,
  existe também no site publicado). Sem foto, o quadrado **«📦 sem foto da
  deckbox»** — que **só no 8771 é botão** (um `<label>` com o `<input
  type="file">` escondido; no site publicado não há onde a mandar). As
  imagens levam `loading="lazy"`, `decoding="async"` e `onerror`. O
  `gravar()` ganhou um terceiro parâmetro (`ficheiro`: o corpo é o ficheiro
  com o tipo dele e o prazo sobe de 25 s para 90 s — 8 MB pela rede de casa).
  O `render_deckboxes.js` conta `data-foto-caixa` como escrita. O
  `test_montados._cartoes` passou a ler o nome depois do `<span
  class="btit">`.
- **Medido na cópia da base de 2026-09-21** (o mesmo `vault.db` nos dois
  lados, `_revisao/_medir_foto_caixa.py`): main, ramo, e ramo com `foto` em
  TODAS as caixas — **iguais ao cêntimo e caixa a caixa**: fechar tudo
  7 112,71 €, 239 a comprar, 224 a arrumar (124 linhas), venda 273c/1 563,40 €,
  venda_rl 74c/5 485,87 €, rl_segurar 28c/3 081,19 €, reservadas 1c/100,00 €,
  guardar 1c/14,75 €, as 15 caixas. O índice da Deckboxes ganha `foto` por
  caixa (`{em, url}` ou `null`); nenhuma parte cresce.

**14. TIRAR AS FOTOS DAS CARTAS DIRECTAMENTE DO SITE, NO TELEMÓVEL (André,
2026-09-21, à letra).** *"é possível ter o site preparado para eu abrir no
telefone e tirar as fotos directamente do site?"* — e, no mesmo dia, *"e
guardares as fotos, claro"*. Fecha o passo que faltava à revalidação (ponto
8): até aqui ele carregava em «Fotografar esta caixa», fotografava com a app
da câmara e levava as fotos à mão para `pendentes/` (app do GitHub ou o PC).
Motor em `mtgvault/fotosite.py`, endpoint `POST /api/foto` (multipart, uma ou
várias fotos, token) e `POST /api/processar-fotos`, botões na aba de cada
caixa (bloco «📷 Na caixa — fotografar») e na aba «📷 Revalidação» (Venda,
Caixa RL, Colecção). Relatório em
`ai-pc/work/revisao/mtgvault-foto-site-0921.md`; testes em
`test_foto_site.py` (8 casos). **Só no 8771** — o site publicado é estático e
não tem onde receber uma foto. **O `mtg-fotos-novas` NÃO se alterou.**
- **A CÂMARA A PARTIR DA PÁGINA.** O botão **«📷 Tirar fotos»** é um `<label>`
  com `<input type="file" accept="image/*" capture="environment" multiple>`
  (no telemóvel abre a câmara, várias seguidas; no PC o selector) — o mesmo
  gesto da foto da deckbox (ponto 13). E **um 📷 por cópia** por fotografar
  no tile/linha da lista «Na caixa» e nos grupos da Revalidação: a foto vai
  com a cópia esperada no nome. O «📷 Fotografar esta caixa» de 20/09 fica
  com o nome de sempre (fixa o ALVO e escreve o `esperadas.md`); o «Tirar
  fotos» está à frente dele, nos dois estados (com e sem alvo). O `gravar()`
  aceita um `FormData` **sem `Content-Type` escrito à mão** (é o browser que
  põe a fronteira do multipart; escrevê-lo dava um corpo que o servidor não
  partia) e o prazo sobe 20 s por MB (5 fotos de 4 MB pela rede de casa não
  cabem em 90 s).
- **A FOTO GUARDA-SE TAL COMO VEIO, INTEIRA, NA RAIZ DE `pendentes/`** —
  onde o `mtg-fotos-novas` (`PEND.iterdir()`) as vai buscar. Nunca se reduz
  nem se apaga: é ela que fica ligada à cópia (`copies.photo_path`) e vai
  para «fotos processadas». O multipart lê-se com o `email` da biblioteca-
  padrão (`fotosite.ler_multipart`; o `cgi` saiu do Python), valida-se cada
  ficheiro pelos PRIMEIROS BYTES (`fotocaixa.tipo_da_imagem`) e **recusa-se o
  pedido inteiro ANTES do primeiro ficheiro tocado** (409): «3 guardadas, 1
  recusada» obrigava a adivinhar qual. Escrita atómica (tmp + `os.replace`).
  Tectos: `MAX_FICHEIROS` 30 por pedido, `fotocaixa.MAX_BYTES` (25 MB) por
  foto, `MAX_PEDIDO` (150 MB) por corpo — o `do_POST` passou a escolher o
  tecto pelo caminho, sem ler. Se um dia a leitura pelo Claude local ficar
  pesada com fotos de 3–5 MB, faz-se uma cópia reduzida temporária SÓ para a
  leitura (fora de `pendentes\`, apagada no fim), nunca em vez do original —
  hoje não se fez: as fotos que ele largava pela app do GitHub tinham o mesmo
  tamanho.
- **O NOME DIZ A ORIGEM**: `site-<slot>-<AAAAMMDD-HHMMSS>-<n>.jpg` para a
  caixa, `site-venda-…`, `site-rl-…`, `site-colecao-…` para os outros três
  alvos, e `…-c<copy_id>.jpg` quando a foto foi pedida pelo 📷 de uma carta.
  `nome_ficheiro` ↔ `origem` são inversos (tem teste; um slot com hífenes —
  `duel-commander`, `pioneer-jeskai` — não confunde porque a data tem forma
  fixa; um slot chamado `venda`/`rl`/`colecao` é recusado). Dois pedidos no
  mesmo segundo não se pisam (`n` salta o que já lá está).
- **O IMPORT PREFERE A CAIXA E A CÓPIA DO NOME** (`revalidacao.alvo_da_foto`,
  chamado pelo `collection.import_csv` linha a linha): o passo (0) e a
  discrepância (0b) usam como alvo a caixa do prefixo — e a cópia do
  `-c<id>` primeiro (`_ordem(..., primeiro)`) — **mesmo que o alvo do config
  seja outro ou não haja nenhum**: o nome da foto é uma afirmação mais
  recente e mais precisa do que o botão de ontem. Uma foto sem prefixo
  (largada à mão) fica com o alvo global, como até aqui. A partição das
  cópias calcula-se uma vez por importação (`cache["particao"]`, a mesma do
  `alvo_da_importacao`). Uma caixa que já não existe no nome deixa só a cópia.
- **O `esperadas.md` ganhou a secção «Fotos tiradas no site»**
  (`fotosite.seccao_esperadas`, via `encomendas.esperadas_md(..., pasta=)`):
  cada `site-…` presente com a caixa por extenso e, com `-c<id>`, a cópia
  esperada (nome + impressão). O `PROCESSAR_FOTOS.md` diz ao Claude das fotos
  que o prefixo é a caixa e o `c<id>` a cópia — **uma pista, não uma
  resposta**: escreve o que VÊ, como sempre. É por isso que o `POST /api/foto`
  regenera (a secção tem de estar escrita antes das 02:30, e nada mais escreve
  o ficheiro entretanto) — mas **EM FUNDO** (`webapp.regenerar_em_fundo`, uma
  thread por pedido, com o mesmo lock `ESCRITA`): medido no 8771 a sério nesse
  dia, o `POST` que regenerava antes de responder demorava **109–112 s**
  (`loadout.report` + duas páginas + `esperadas.md` neste PC), mais do que o
  prazo do `gravar()`, e a página dizia *"não sei se gravou"* com a foto já em
  `pendentes/`. Agora responde no instante em que os ficheiros fecham (~0,1 s)
  e o `esperadas.md` chega a seguir; `esperar_fundo()` é para os testes.
- **«⚡ PROCESSAR AGORA»** (`fotosite.pedir_processamento`) escreve uma ordem
  `command` na inbox do runner do ai-pc — `inbox/mtgvault-fotos-<AAAAMMDD-
  HHMMSS>.json`, `{"kind":"command","command":["py","runner.py","run",
  "mtg-fotos-novas"],"cwd":"C:\\Users\\Catarina\\Desktop\\ai-pc"}`, atómica —
  que corre o MESMO programa das 02:30. Com **`nao_antes` = a foto mais
  recente + 2 min + 15 s**: sem isso o runner apanhava a ordem em 30 s, a
  tarefa dizia *«fotos a chegar — espera»* (só pega em fotos com mais de 2
  min) e não fazia nada, com a página a prometer processar. **Uma por 5 min**
  no máximo (lê `inbox/`, `inbox/done/` e `inbox/cancelados/` pelo nome); com
  uma já na inbox diz «já está a processar» e a página mostra-o em vez do
  botão. Não se corre o Claude local de nenhuma outra forma a partir do 8771.
  O resultado vê-se quando as cópias ficarem ✓ (o `recarregar()` ao toque).
- **O QUE FICOU POR RESOLVER** (`fotosite.por_resolver`): as linhas paradas
  (`resultado != importada`) dos `recat-*-resultado.csv` cuja foto AINDA está
  em `pendentes/` (a foto que não entrou toda fica lá — regra do
  `arrumar_fotos`), com o motivo do resultado mais recente. Aba Revalidação,
  bloco «⚠ Fotos por resolver», para ele voltar a fotografar em vez de esperar
  por uma corrida que dá o mesmo.
- **A PÁGINA.** O bloco «📸 Fotos enviadas, à espera» (na aba da caixa só as
  dela; na Revalidação todas, com a origem — «largada à mão» para as sem
  prefixo) lista nome, tamanho, hora, cópia, e *«a chegar (menos de 2 min)»*;
  diz que estão *«à espera das 02:30 ou de Processar agora»*. Vai no payload
  em `revalidacao.site` (`{enviadas, n, prontas, por_resolver, espera_s,
  processar: {pendente, ultima}}`; o índice leva os escalares, a parte
  `revalidacao` as listas) e em `caixa.rev.site` (as dessa caixa). A
  informação vai nos DOIS modos; os botões (`data-foto-site`, `data-processar`)
  só no 8771 — o `render_deckboxes.js` conta-os como escrita. **A pasta
  `pendentes/` entrou no `webapp._versao()`** pelo mtime da pasta (o NTFS
  actualiza-o quando um ficheiro entra ou sai): a foto acabada de chegar e a
  que o `mtg-fotos-novas` arrumou às 02:30 aparecem/desaparecem sem ninguém
  carregar em nada.
- **Medido na cópia da base de 2026-09-21** (`_revisao/_medir_foto_site.py`,
  o mesmo `vault.db` nos dois lados; o ramo com duas fotos `site-*` em
  `pendentes/` e uma ordem pendente): **iguais ao cêntimo e caixa a caixa** —
  fechar tudo 7 112,71 €, 239 a comprar, 224 a arrumar (124 linhas), venda
  273c/1 563,40 €, venda_rl 74c/5 485,87 €, rl_segurar 28c/3 081,19 €,
  reservadas 1c/100,00 €, guardar 1c/14,75 €, as 15 caixas. O
  `fotosite.estado` custa 0,04 s; o índice fica em 44 KB e a parte
  `revalidacao` em 270 KB (+2 fotos); a caixa leva as suas duas em `rev.site`.

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
  (Essa função **desapareceu** a 2026-09-09 — ver *"o registo grava só o que ele
  marcou"*: gravava a alocação calculada, e era esse o segundo caminho.)
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
| Cardmarket | não se raspa; usa o price guide oficial. O cookie de sessão expira. **O price guide de Magic está PÚBLICO** (`prices.CM_PRICEGUIDE_PUBLICO`, S3, sem sessão — 2026-09-18), mas ligá-lo é opt-in (ver abaixo) |
| CardTrader | API v2, token no perfil, 200 pedidos/10s. O token existe neste PC (`CARDTRADER_TOKEN`); o `daily` só corre com `CARDTRADER_SETS`. **NÃO publica «market value» nenhum** (sondado a 2026-09-25): os blueprints não trazem preço e cada oferta traz só o `price_cents` — o market value é a MEDIANA das ofertas, calculada por nós. As 145 edições dele são **450 s** e **53 113 linhas** |

## As cinco superfícies, validadas contra os sites reais (2026-09-18)

Estiveram um mês e meio nesta secção como *"nunca correram contra a rede"* —
e as três primeiras corriam **todas as noites** no `mtgvault-daily` (a base tem
7 741 listas de `mtgo` + `mtgtop8` até 2026-09-17). A 2026-09-18 correu-se cada
uma, sozinha, contra o site, com as escritas numa CÓPIA da base
(`_scratch/superficies.py` do ramo desse dia):

1. `sources.fetch_mtgo_index` — **funciona.** As duas formas de URL respondem
   (200, 219 KB, 253 hrefs); a primeira ganha. Dado mais recente: **2026-09-18**
   (10 eventos do próprio dia; 14 a 17/09).
2. `sources.parse_mtgo_page` — **funciona.** Liga: `{name, publish_date,
   decklists…}`; Challenge: `{description, starttime, format, player_count,
   standings…}`. O `store_event` guardou as duas (e o filtro do Pauper deixou
   passar só o Luffy: 1 de 32). **Remendo:** o `player_count` das Challenges
   passou a ir para `event_players` — era de graça e ficava no chão; o peso do
   MTGO continua a vir do tier. Dado mais recente: **2026-09-18** («Pauper
   Challenge 32», 32 jogadores).
3. `mtgtop8.harvest` — **funciona.** Página de formato → 23 eventos, página
   de evento → nome/data/**125 jogadores**/32 decks/32 jogadores, `.dec` →
   37 linhas com o prefixo `[SET]` limpo; `harvest` 0 novas porque o `daily`
   das 02:30 já as tinha. Dado mais recente: **2026-09-17** (Premodern
   Challenge do MTGO re-hospedada) e **2026-09-12** em papel («Buckeye Brawl II
   — Retromancers», 125 jogadores).
4. `prices.load_cardmarket_file` — **funciona, e o ficheiro é público.**
   `https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json`
   (26 MB, 127 216 produtos, `createdAt` **2026-09-18 02:49**) lê-se tal e qual:
   29 170 preços gravados na cópia, com low/trend/avg30 e as variantes foil.
   **NÃO ficou ligado**, de propósito: por cima dos preços da Scryfall (que
   são o `trend` do Cardmarket — 78 % iguais ao cêntimo) o guide traz **8 202
   impressões** que a Scryfall não cota, e como o `card_price` é o MÍNIMO entre
   impressões do mesmo nome a venda passa de 1 499,70 € para **665,60 €** (as
   mesmas 246 cópias), o *fechar tudo* de 7 057,57 € para **5 164,65 €**, e a
   regra dos 5 % da RL passa **22 cópias / 3 583 €** de *segurar* para *vender*
   sem o mercado ter mexido (o mínimo de hoje tem impressões que o de há 90
   dias não tinha). É decisão do André: `CARDMARKET_PRICEGUIDE_PUBLICO=1` no
   ambiente do `daily` liga-o (`prices.priceguide_publico_ligado`, com teste
   sobre um trecho real), e nesse dia a janela da RL recomeça.
5. `prices.sync_cardtrader_map` — **funciona, e voltou a correr a 2026-09-25**
   para as **145 edições** da colecção dele, numa cópia da base: 30 162
   impressões no mapa (70 s) e **53 113 preços** (450 s), agora com os DOIS
   valores. Deixou de ser uma superfície por validar. O texto de 18/09 fica:
   `/expansions` 3 859; ODY →
   374 blueprints, **350 com `scryfall_id`** (o resto são variantes sem par
   pelo nome), 350 pares no mapa; `fetch_cardtrader_prices` 699 linhas (ex.:
   Mountain 0,14 €, 343 à venda). Dado mais recente: **2026-09-18** (é o
   marketplace ao vivo). Sem `CARDTRADER_SETS` o `daily` continua a saltar —
   com `set_codes=None` o `sync` percorria as 3 859 expansões.

## Por fazer

- ~~Validar as cinco superfícies contra os sites reais~~ — feito a 2026-09-18,
  ver a secção acima. Por decidir (André): ligar o price guide público.
- ~~Abrir o porto 8771 na firewall privada~~ — feito a 2026-09-15 (regra
  `mtgvault 8771`, TCP 8771, perfil privado).
- ~~Correr a migração `migrar-coleccao-unica` na base a sério~~ — correu a
  2026-09-07 (727 cópias) e a 2026-09-18 (as 10 que as entradas tinham voltado
  a pôr nos baldes de deck); neutra ao cêntimo — ver *"Modelo de colecção
  única"*. A entrada de cartas passou a escrever no modelo novo.
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
  `copies.photo_path` guarda o caminho. **A única excepção, consciente
  (2026-09-21):** a versão reduzida (~100 KB) da foto da DECKBOX física de
  cada caixa vai no Git, em `assets/deckboxes/<slot>.jpg`, porque o site
  publicado só vê o Git — ver o ponto 13 e `mtgvault/fotocaixa.py`. O
  original continua fora (`data/deckboxes/`).
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
