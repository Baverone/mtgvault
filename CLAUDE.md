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
deckboxes.py        deckboxes.html — "Deckboxes": o LOADOUT (colecao_config.json→loadout), os decks montados ao mesmo tempo com a coleção REPARTIDA entre eles (uma cópia física serve uma caixa só). NB (2026-09-07): a página foi reescrita com **uma ABA POR DECK** (o pedido dele: *"faz como no riftvault — no botão, cada deck tem uma aba própria"*), mais as abas **Todas**, **Arrumar**, **Partilhadas**, **Comprar** e **Vender**. Os dados vão em JSON dentro do HTML (`<script id="dados">`) e o render é JavaScript — o MESMO ficheiro serve o site publicado (`editable:false`) e o modo edição do `webapp.py` (`editable:true`, com botões). Por caixa: barra, dois números ("faltam comprar" e "ir buscar a outra caixa"), grelha de cartas com três estados, "tirar de:" (`slot["origens"]`), substitutos, wantlist Cardmarket (SÓ o que é mesmo compra). Na aba **Comprar**, cada linha diz para que caixa é a compra (`para`) e em que material (`loadout.requisito_material`), há selector por caixa (o "copiar" copia só o filtro activo) e as cartas ≥100 €/cópia levam chip «cara» e total à parte — Mishra's Workshop sozinha vale mais do que o resto da lista. Motor em mtgvault/loadout.py
webapp.py           MODO EDIÇÃO local, **porto 8771** (o 8770 é do `riftvault serve` — não trocar). Serve o `deckboxes.html`/`metagame.html` com os botões: painel *Montar* (*Sleevado e na caixa*), *Já arrumei tudo*, *Actualizei*, *Vendida*, *Tornar permanente*, *Subir/Descer* e *Vou montar este*. As PREFERÊNCIAS vão para o `colecao_config.json` (as `caixas` vão no Git); o que é FÍSICO vai para a `copy_allocation` e, na venda, sai da `copies` + `data/vendas.csv`. NB (2026-09-08): **ouve em `MTGVAULT_BIND`, por omissão `127.0.0.1`** (a tarefa `mtgvault-serve` põe `0.0.0.0` para o telemóvel), e as ESCRITAS exigem o token de `data/webapp.token` — ver "O telemóvel e o token". Mantido de pé pela tarefa `ai-pc/tasks/mtgvault-serve` (verifica de 5 em 5 min, relança destacado)
metagame.py         metagame.html — "Metagame": desde 2026-09-07 já NÃO é o top-10 de cada formato; é o **top-N que ele está mais perto de concluir** (`colecao_config.json`→`metagame_top_n`, default 3). `SECOES` decide o modo por formato: `top` (Standard/Pioneer/Legacy — as caixas do loadout por escolher, via `loadout.foil_report`), `caixas` (Modern — o deck já escolhido, do próprio loadout) e `alvos` (Premodern — só o `premodern_arquetipos_alvo`). Posse pela alocação do loadout, três estados, wantlist Cardmarket. NÃO lê `formatos_metagame` (o Legacy tinha de entrar e não está lá)
(prioridade.py + metafaltas.py APAGADOS 2026-08-26, a redefinir)
reservedlist.py     reservedlist.html — Reserved List (Scryfall) x coleção, por edição, preço/evolução, e 'VENDER' as que não jogam em formato nenhum
caixarl.py          caixarl.html — "Caixa Reserved List": a RL que está fora da coleção jogável
showcase.py         showcase.html — "Decks Showcase Challenger": eventos competitivos recentes (MTGO + presenciais do mtgtop8) agrupados por arquétipo. Tinha filtro e pesos PRÓPRIOS (fonte + showcase_min_players + lista de nomes casuais) — era por isso que continuava a dar listas enquanto o metagame vinha vazio. Desde 2026-09-07 usa `sources.counting_sql`/`tier_weight` como toda a gente; a chave `showcase_min_players` do config deixou de existir
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
E uma aba **Plano** (`loadout.ordem_de_montagem`, a mesma no CLI): por onde
começar — permanentes por prioridade, depois as candidatas mais perto de fechar —
com *"tirar N · comprar N (X €) · estado"*, e por baixo a **venda**, que só entra
depois de as caixas estarem servidas (uma cópia que serve uma caixa nunca aparece
na venda: vai para `guardar`).

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

**CAIXAS DEDICADAS: o "ir buscar" e a partilha ficam só para o DC e o SPML
(André, 2026-09-07 às 19:00, à letra).** *"Cada deck montado deixa de partilhar
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
   essas cartas NÃO entram para outros formatos!!"* → um slot com `"lingua":"pt"`
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

**A venda tem quatro saídas, não uma.** Misturá-las dava um total que não se
podia usar: `venda` (excedente normal), `venda_rl` (Reserved List — não se
volta a imprimir, confirma-se uma a uma), `retidos` (baldes com
`reter_extras_meses`; a regra dos 6 meses continua inerte por falta de data de
"última utilização", por isso guardam-se e dizem-no) e **`guardar`**: os
SUBSTITUTOS. Este último não é um requinte — foi um erro real da primeira
versão: o playset de 4 dava as cópias a mais como excedente e a lista mandava
vender exactamente as cartas que faltam a um deck do loadout. **Uma cópia que
serve um deck do loadout e só falha no acabamento nunca vai para a venda.** O
caso que a motivou eram as 4 Opalescence EN da Caixa RL; desde a regra 1b acima
nenhuma EN é vista pelas caixas de Premodern e essas vão mesmo para `venda_rl` —
a saída `guardar` ficou só para as **nonfoil dos slots de foil**, que é onde ele
não fechou a porta (na base de 2026-09-07 dá 0 cópias: as nonfoil que servem
esses slots ainda cabem todas no playset).

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
`colecao_cor._watched_deck_pools` junta-se por ela. Atenção:
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
