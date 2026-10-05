# CLAUDE.md

Contexto do projeto para o Claude Code. Lê isto antes de mexer em código.

## O que é

Gestor pessoal de coleção de Magic, do André. Python + SQLite, corre no PC dele
(Windows) e também como job diário no GitHub Actions. Sem servidor, sem frameworks.

Faz quatro coisas: gere a coleção física, segue decks, analisa o metagame para
descobrir o núcleo de cada arquétipo, e acompanha preços.

## OS ENDEREÇOS QUE SE DÃO AO ANDRÉ (2026-10-01)

- **Modo de edição:** <https://editar-mtg.baverone.com/> — é o `webapp.py` deste
  PC, por HTTPS e atrás do Cloudflare Access.
- **Site publicado (só leitura):** <https://mtg.baverone.com/>; o centro é o
  <https://baverone.com>, que tem lá o link *«Editar mtgvault»*.
- **O IP da rede local NÃO se usa nem se lhe dá** (`http://192.168.x.y:8771/…`).
  O **porto 8771 continua a ser o porto**, por dentro e nas tarefas do ai-pc
  (`mtgvault-serve`, `_reiniciar_webapp.py`) — porto não é endereço. Os dois
  URLs vivem num sítio só, `site_shell.URL_EDICAO`/`URL_PUBLICO`, e o
  `webapp.py` aceita `MTGVAULT_URL_EDICAO` para quem corra isto sem o túnel.

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
- **O `colecao_config.json` edita-se CIRURGICAMENTE — nunca se reformata.** É um
  ficheiro para ser LIDO por uma pessoa: cada regra tem a explicação em português
  ao lado, e as listas de objectos (`caixas`, `regras_por_formato`,
  `cartas_vigiadas`, …) estão escritas **uma linha por objecto**. Muda as linhas
  que tens de mudar (Edit, ou substituição de texto); se tiveres de o escrever
  por código, usa **`mtgvault.configio.escrever`**, que preserva esta forma
  (`UMA_LINHA`/`CARTAS_UMA_LINHA`) — nunca `json.dump(..., indent=2)`. Já
  aconteceu: o commit `ac1f776` (2026-09-30) acrescentou `pioneer` a duas cartas
  vigiadas e saiu com **861 inserções e 136 remoções**, porque o ficheiro foi
  lido e reescrito com `indent=2`. O conteúdo estava certo e o diff ficou
  ilegível — e um diff ilegível neste ficheiro é a revisão a deixar de existir.
- Comentários explicam *porquê*, não *o quê*. Vários dos comentários atuais
  existem para registar decisões que custaram a descobrir — não os apagues.

## Arquitetura

```
mtgvault/
  db.py           ligação, ATTACH do catálogo, migrações
  schema.sql      vault.db (coleção, decks, decklists, preços, watchlist, copy_allocation)
  catalog_schema.sql   catalog.db (só a tabela cards)
  scryfall.py     catálogo via bulk data. E, desde 2026-10-04 ao fim do dia, O
                  CRUZAMENTO NOME-DE-LISTA ↔ CATÁLOGO NUM SÍTIO SÓ: as listas
                  trazem a FRENTE de uma carta de duas faces (`Witch Enchanter`)
                  e o catálogo o nome inteiro — `canonizar`/`chave` (a chave dos
                  dicionários, que normaliza também o separador `Wear/Tear`),
                  `MapaDeCartas` (o `dict` que canoniza a chave sozinho, para
                  nenhum dos vinte `mapa.get(nm)` se esquecer), `sql_nome`/
                  `params_nome` (o predicado de quatro ramos, `MULTI-INDEX OR`
                  pelo `ix_cards_name`), `resolver`/`resolver_muitos` (quando o
                  nome está do lado longe de um JOIN grande) e `desconhecidas`
                  (o que o catálogo não tem fica DITO, nunca «não tenho»). Ver
                  «O CRUZAMENTO NOME-DE-LISTA ↔ CATÁLOGO VIVE NUMA FUNÇÃO SÓ»
  site_shell.py   A CASCA DE TODO O SITE (2026-09-24): a paleta (`TEMA`), os
                  tipos de letra, os ÍCONES (`_SVG`/`icone`/`js_icones` — um
                  conjunto só, partilhado com o JavaScript da Deckboxes), a
                  BARRA LATERAL agrupada em secções
                  (`SECCOES`), o cabeçalho com migalhas e o rodapé —
                  `head()`/`abrir()`/`fechar()`. Uma secção nova é uma linha
                  numa lista. Ver «Uma casca só para o site inteiro»
  paginas.py      os ajudantes que as páginas partilham e NÃO são casca (cor,
                  tipo, posse total, faltas, euros em português) + os DADOS À
                  PARTE. O `TEMA`/`META` reencaminham para o `site_shell`.
                  E, desde 2026-10-04 à noite, a `<img>` DE UMA CARTA NUM SÍTIO
                  SÓ (`img_carta`/`IMG_W`/`IMG_H`): `loading=lazy`,
                  `decoding=async` e o tamanho ESCRITO, para o ecrã não saltar.
                  Estava à mão em quatro sítios e nenhum tinha o tamanho — 1 288
                  imagens a mover o conteúdo por baixo do dedo dele
  publicar.py     PUBLICAR O SITE SEM ESPERAR PELAS 03:30 (2026-10-04, à noite):
                  gera as 13 páginas (`PAGINAS`, a MESMA lista do `git add` do
                  `daily.yml`) para uma pasta de PROVA, compara com o disco
                  IGNORANDO o `_gerado_em` (`normalizar`/`comparar`) e só escreve
                  se mudou — sem isso o relógio sozinho dava um commit a cada
                  meia hora, para sempre. **Não escreve na colecção**
                  (`SO_LEITURA`: a Galeria é o único gerador que escrevia, o
                  ponto do dia no `value_history`), porque o sossego da tarefa é
                  o mtime do `vault.db` e ela envenenava-se a si própria. Quem
                  commita e faz o push é a tarefa `ai-pc/tasks/mtgvault-publicar`
                  (30 min). Ver «PUBLICAR SEM ESPERAR PELAS 03:30»
  decks_vista.py  A ABA DECKS (2026-10-04): formato → deck → cartas. O REGISTO
                  (as caixas dele + os arquétipos meta pelo NOME DA FONTE), a
                  regra `cartas_partilhadas` (`rotativas` = MÁXIMO vs
                  `dedicadas` = SOMA, do config — é a contradição de 02/10 vs
                  04/10 resolvida FORA do código), as PRÓPRIAS e as PARTILHADAS
                  (que dependem de quais decks ele marcou), os PROXIES e os
                  SLEEVES, as DUAS listas de tipos (`ORDEM_TIPOS` de
                  apresentação ≠ `PRECEDENCIA` de classificação) e o
                  «quero montar este» (`decks_montar`). Ver «A ABA DECKS».
                  E, desde 2026-10-05, OS DECKS PRINCIPAIS FICAM SEMPRE MONTADOS:
                  `principal`/`sempre_montado` (o eixo por CAIXA, que GANHA ao
                  `cartas_partilhadas` do grupo), `reparte_verdadeiras` (quem
                  fica com a cópia a sério e quem leva proxy, pela `prioridade`),
                  `disputadas`, `proxies_das_faltas` (os proxies passam a ser
                  TUDO o que falta) e `da_pilha`/`tenho_para` (a pilha de básicas
                  nunca é proxy — eram 44 das 272 cópias). Ver «SEMPRE MONTADOS,
                  MESMO COM PROXIES»
  eventos.py      A LISTA DE UM DECK É UMA LISTA QUE ALGUÉM JOGOU (2026-10-04,
                  ao fim do dia): *"as outras quero que esquecas as decklists e
                  vamos focar nas decklists baseadas em eventos reais"*. A
                  pergunta «qual é a melhor lista REAL deste deck?» num sítio só
                  — a REGRA de escolha (que vive no config, `listas_de_evento.
                  regra`, com a razão de cada critério: a `janela` como filtro, o
                  `tier`, o `campo`, a `repetida`, a `classificacao`, a `data` e
                  o `jogador`), a PROVENIÊNCIA (`proveniencia`/`texto_prov` —
                  jogador, evento, data, jogadores, classificação, URL), as
                  `candidatas`, o `escolher` (com a ALTERNATIVA fora da janela) e
                  o `fixar`, que GRAVA as cartas e a ficha no config porque o
                  `prune_decklists(30)` apaga as decklists ao fim de um mês. O
                  motor do consenso NÃO se apaga: o meta fica para consulta e
                  di-lo. Ver «A LISTA DE UM DECK É UMA LISTA QUE ALGUÉM JOGOU»
  faltas_vista.py A LISTA DE FALTAS, PARA PROCURAR EM GHENT (2026-10-05): *"a
                  lista de faltas desses decks para poder procurar em Ghent"*.
                  Uma linha por carta com o SUBTOTAL POR DECK, saída do `comprar`
                  da alocação (nunca do `missing`: já desconta o que ele tem, o
                  que está noutra caixa e o que encomendou), os DOIS preços lado
                  a lado (`unit` do motor vs `unit_serve` da impressão que a caixa
                  aceita) e o formato sem deck escolhido à parte, FORA do total
                  (`sem_deck_escolhido`, derivado do modelo «um deck por
                  formato»). A VISTA é o `faltas.py` da raiz. Ver «A LISTA DE
                  FALTAS PARA GHENT»
  marcas.py       A POSSE QUE ELE MARCA À MÃO (2026-10-04): o `+` e o `−`.
                  O inventário PRÉ-PREENCHE (`posse_marcada` nasce vazia) e a
                  marca dele GANHA, com data; `inventario`/`marcado` são dois
                  estados visíveis e distintos. Deltas com `request_id`, como no
                  riftvault. Substitui o `confirmado` como resposta a «tenho
                  esta carta?»
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
  confirmado.py   A FOTO É A VERDADE E A BASE É O REGISTO DELA (2026-10-02):
                  *"se não tiver foto, não tem carta"* — `manda()` (o
                  interruptor `revalidacao.foto_manda`), `sql()`/`confirmada()`
                  (a pergunta *"esta cópia conta?"*, num sítio só),
                  `metades()`/`frase()`/`euros()` (as DUAS METADES de cada
                  número, que LEVANTAM se não somarem o total),
                  `filtrar_sem_foto` (a oitava saída da venda),
                  `alvo_da_pasta`/`alocar_por_foto` (a PASTA da foto decide o
                  deck, e é exclusiva — `data/foto-manda.log`),
                  `exige_alocacao_unica`/`conflitos` (cada deck as suas cartas)
                  e `progresso`/`texto` (o ecrã de todos os dias). Ver «A FOTO É
                  A VERDADE»
  estado.py       O ESTADO DAS CARTAS (2026-10-03): *"procuras como são avaliadas
                  as cartas, depois com base nas minhas próprias fotos, vais
                  melhorando o teu critério"*. A escala do Cardmarket
                  (`ESCALA`/`NOMES`/`normalizar`, com a `PONTE_AMERICANA` e o
                  `do_cardtrader` para as ofertas), a ORIGEM do juízo
                  (`medido()` — o `NM` de fábrica é `omissao` e não passa por
                  medido), o FACTOR de preço MEDIDO nas ofertas por estado e por
                  BANDA de preço (`factor`/`aplicar`, no config `precos.estado`;
                  o NM vale 1,000 e o PL é interpolado e di-lo), o VERSO (quem
                  precisa dele, e `da_foto` — sem verso não há escalão), o ciclo
                  que APRENDE (`registar`/`corrigir`/`exemplos`/`padroes`/
                  `acerto`/`escrever_aprendido`/`para_avaliar`, com a correcção
                  dele a ganhar sempre), a LISTA CURTA dos extras
                  (`lista_curta`) e o `impacto` (quanto está em jogo). Ver «O
                  ESTADO DAS CARTAS E OS VERSOS»
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
  fotos.py        AS FOTOS: a regra das QUATRO CARTAS (2026-10-01) e o «onde
                  está a foto», num sítio só — `MAX_CARTAS`/`valida` (o tecto,
                  que vale para a fila e para a trava do import, e que desde
                  2026-10-02 NÃO vale para uma foto só de básicas —
                  `so_basicas`/`valida(isenta=)`), `agrupar`
                  (as fotos de até 4 cartas, por TIPO), `barra` (o progresso em
                  FOTOS, com as cartas e as linhas ao lado), `resolver` (procura
                  na pasta de trabalho E no arquivo, a de trabalho a ganhar),
                  `arquivar` (move `pendentes/fotos processadas/` para
                  `data/fotos/anteriores/` — nunca apaga), `pasta_do_alvo` (as
                  fotos novas por DECK) e `texto_do_plano`. E, desde 2026-10-01
                  à tarde, A PASTA POR DECK COMO ALVO: `mapa_pastas`/
                  `slot_da_pasta` (pasta → slot, DERIVADO do `caixas` do
                  config), `fotos_nas_pastas`, `recolher_das_pastas` (move para
                  `pendentes/` com o nome `site-<slot>-…`) e `escrever_planos`
                  (os `_plano.txt`, reescritos pelo daily). E, desde 2026-10-02,
                  O QUE FAZ O CANO AGUENTAR A CAMPANHA: `alvo_da_pasta` (a
                  pergunta «de quem é esta pasta» num sítio só — caixa, ou o
                  `coleccao` dos `Extras (fora dos decks)`),
                  `PASTAS_FORA_DOS_DECKS`, `consumidas`/`ja_e_prova` (a mesma
                  foto não é prova de duas cartas), `garantir_pastas` (uma pasta
                  por deck do config) e `TEXTO_ORFA`/`_pastas_do_slot` (o plano
                  de uma pasta renomeada deixa de mentir). Ver «UMA FOTO LEVA
                  NO MÁXIMO QUATRO CARTAS», «A PASTA POR DECK VALE COMO ALVO» e
                  «O CANO DAS FOTOS AGUENTA A CAMPANHA»
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
  venda.py        O INTERRUPTOR (2026-09-25): `venda.mostrar` — *"para já tira o
                  «vender»"*, hoje `false`. Tira a venda da VISTA em nove
                  superfícies e NÃO toca no motor (as sete saídas, a regra da
                  RL e o `vendas.csv` continuam). Ver «Para já tira o vender».
                  E a SAÍDA da lista de venda (2026-09-18): o CSV de stock p/ o
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
  mtgtop8.py      duel-commander, premodern, cedh, e papel. E, desde 2026-10-04,
                  NUNCA PERDER UM TORNEIO DE PAPEL GRANDE: o índice passou a dar
                  NOME e DATA (`parse_event_rows`/`parse_paginas_indice` — a
                  página de Modern tem 375 `event?e=` e só 20 são eventos), a
                  LIGA salta-se pelo nome ANTES de se pedir a página do evento
                  (`candidatos_do_indice`), um torneio grande entra esteja onde
                  estiver no índice e com o tecto de 64 listas que a página serve
                  (`regras_grandes`/`e_grande`/`tecto_do_evento`, config
                  `mtgtop8`), e a MEMÓRIA (`mtgtop8_eventos`,
                  `semear_memoria`/`memoria_dos_eventos`/`por_fazer`) é o que
                  torna barato descer no índice. `grandes_de_hoje` alimenta o
                  aviso. Ver «NUNCA PERDER UM TORNEIO DE PAPEL GRANDE»
  moxfield.py     decks do Moxfield
  watchlist.py    vigiar jogadores e decks, snapshots e diffs. E, desde
                  2026-10-04 ao fim do dia, A VIGIA DE UM ARQUÉTIPO DO MTGTOP8:
                  `check_mtgtop8_archetype` (lista NOVA e troca da MELHOR
                  classificada, um pedido por corrida — o snapshot é o ÍNDICE da
                  página e não as cartas), `_melhor` (menor posição, a mais
                  recente a desempatar) e o mapa `VERIFICADORES`, que fez o
                  `check_all` FALHAR ALTO num kind que não sabe tratar — o
                  `archetype` estava no CHECK desde sempre e nunca teve
                  implementação: era saltado sem erro. Ver «O SIDEBOARD
                  APLICADO, A RESERVA A 20 % E A VIGIA DO ARQUÉTIPO»
  vigia.py        A VIGIA DE CARTAS (2026-09-26): «vai conferindo» — que cartas
                  ele espera ver numa decklist (`cartas_vigiadas`), e o aviso no
                  dia em que aparecem. Abre o filtro de tier SÓ para essas listas
                  (um 5-0 de league é o sinal), guarda o que já viu em
                  `data/vigia-cartas.json` e diz o que falta para montar. Ver
                  «A VIGIA DE CARTAS»
  fases.py        A ARRUMAÇÃO POR FASES E AS QUATRO PROTECÇÕES (2026-10-01): as
                  listas de shock/fetchlands DERIVADAS do catálogo
                  (`shocklands`/`fetchlands`/`verificar`, que levanta se não der
                  10+10), os TRÊS ESTADOS de cada deck (`caixas[].decisao` —
                  `montado`/`guardado`/`dissolvido`, omissão **montado**), a
                  RESERVA («maybe») que se enche do consenso com um LIMIAR
                  (`reserva.limiar_pct`, 20 %) e a `curva_do_limiar`, a lista de
                  CANDIDATOS (`candidatos`) e o filtro que entra no motor
                  (`filtrar_venda` → saída `protegidas`), as FILAS de fotos por
                  CÓPIA FÍSICA e a TRAVA da venda (`venda.congelada`, MANUAL
                  desde 2026-10-04 — era a data `congelado_ate`, do RC Ghent).
                  Ver «A ARRUMAÇÃO POR FASES»
  nomes.py        O NOME DE UM ARQUÉTIPO (2026-10-02): a página do EVENTO do
                  mtgtop8 dá o nome ao lado de cada deck e a recolha deitava-o
                  fora (2 635 listas, nenhuma coluna) — hoje está em
                  `decklists.arquetipo_fonte`. O nome da FONTE ganha; onde não
                  houver, o grupo HERDA o mais votado entre as listas dele que
                  tenham nome (é assim que as 5 173 listas de `mtgo` ficam com
                  nome); sem nenhum dos dois, o nome gerado das cartas vai
                  marcado PROVISÓRIO. `nome_das_listas` é a votação, e é a MESMA
                  nos três sítios que a fazem (o cluster do `archetypes`, o
                  cluster do `showcase`, o arquétipo de uma CAIXA). Ver «O NOME
                  DO ARQUÉTIPO VEM DA FONTE»
  sources.py      … e, desde 2026-10-03, A JANELA DO CONSENSO: `consenso_desde`/
                  `consenso_sql`/`regras_consenso` (`colecao_config.json →
                  consenso.desde`, hoje 2026-09-29 — o dia em que o Reality
                  Fracture entrou no MTGO), que o `counting_sql`/`lista_conta`
                  levam POR OMISSÃO, mais o `texto_amostra` («não dá para
                  dizer») e o `frase_janela_rodape`. Ver «A JANELA DO CONSENSO».
                  E, desde 2026-10-05 ao fim do dia, AS LIGAS EM MODERN:
                  `TIER_LIGA`/`sql_sem_ligas`/`conta_ligas` (a pergunta «isto é
                  uma liga?» num sítio só, para a percentagem do formato se
                  poder dizer COM e SEM elas — uma liga é um 5-0 sem
                  classificação e sem campo, e medido ela DILUI: 5,7 % contra
                  6,9 %), o `PAUSA_MTGO`/`_get_mtgo` (o mtgo.com era o único
                  scraper sem ritmo, e não tem `robots.txt` — 404; segunda
                  tentativa só a erro de REDE) e o `harvest_mtgo(...,
                  incluir_hoje=)`, opt-in, porque a página de liga publica os
                  5-0 ao longo do dia. Ver «TODOS OS TORNEIOS EM MODERN»
  consenso.py     O CONSENSO POR COMANDANTE (2026-10-01): em Duel Commander a
                  identidade de um deck é o COMANDANTE e nunca a etiqueta do
                  clustering (870 etiquetas, 808 sem listas). O comandante de
                  cada lista fica GRAVADO em `decklists.commander`, lido do
                  SIDEBOARD da fonte (`commander_fonte='sideboard'`) ou derivado
                  pela ordem de inserção (`'ordem'`); daqui saem os
                  `comandantes()` e o `consenso()` por carta (percentagem,
                  moda de cópias, papel). Ver «O CONSENSO É POR COMANDANTE»
  aviso.py        o TOAST do Windows (BurntToast se existir, senão o balão do
                  NotifyIcon), por `-EncodedCommand`; nunca levanta e diz sempre
                  o que aconteceu
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
arrumacao.py        arrumacao.html — "Arrumação por fases" (2026-10-01): o sítio que diz SEMPRE onde ele está e o que vem a seguir. Casca + dados à parte; a **Fase 1 vai INTEIRA no índice** (é o ecrã da decisão: não pode esperar por um segundo pedido) e cada fase pesada é uma parte (`fase2`, `candidatos`, `fase4`, `inventario`). Botões só no 8771 (`/api/fase-decisao`, `/api/fase-reserva` e — desde 2026-10-01 — o `/api/revalidacao` do ALVO das fotos, ver «A FILA DA FASE 2 E O BOTÃO DO ALVO»); no site publicado é a mesma informação, só de leitura. Motor em `mtgvault/fases.py`
decks.py            decks.html — "Decks" (2026-10-04): a aba de TRÊS NÍVEIS com URL própria cada (`decks.html`, `#f=<formato>`, `#f=<formato>&d=<id>`), as cartas com imagem e `+`/`−`, agrupadas pelos tipos NA ORDEM DELE (o comandante à cabeça, o sideboard em bloco separado), os dois números «a somar»/«a rodar» lado a lado e, nos formatos rotativos, as próprias vs partilhadas com a lista de proxies. Casca de 50 KB + uma parte por deck (83). Motor em `mtgvault/decks_vista.py` + `mtgvault/marcas.py`
faltas.py           faltas.html — "Faltas para procurar" (2026-10-05): o que comprar, por deck, com o SUBTOTAL de cada um, para ele procurar nas bancas do RC Ghent. Desenhada para o telemóvel **de pé num pavilhão**: o NOME manda (17 px, nunca cortado) e a imagem é um APOIO — é o contrário da aba Decks, e as duas estão certas. Ordenável por valor ou por deck, filtrável por formato, alvos de 44 px, zero rolamento horizontal. 40 imagens no primeiro ecrã e o resto ao rolar (`paginas.IMG_LOTE` + `IntersectionObserver`). Os dados vão TODOS no índice (84 KB): ordenar e filtrar do lado do browser não pode ficar à espera de um `fetch`. Motor em `mtgvault/faltas_vista.py`
comandantes.py      comandantes.html — "Consenso por comandante" (2026-10-01): o consenso de Duel Commander por COMANDANTE, abrindo no Cloud. Casca + dados à parte (`data/paginas/comandantes.json` + uma parte por comandante, 40); cada carta diz a percentagem de listas, a moda de cópias, o papel (núcleo ≥90 % / flex 40–90 % / raro <40 %) e quantas ele TEM / FALTAM (`paginas.posse_total`). Motor em `mtgvault/consenso.py`
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
colecao_config.json    config: spml_formatos, premodern_decks_completos, banimentos_manuais, regras_colecao, loadout, regras_por_formato, metagame_fontes, formatos_metagame, premodern_arquetipos_alvo, so_jogadores_vigiados, venda (a regra dos 5 % da RL, o `mostrar` de 2026-09-25 **e** a TRAVA — `congelado_ate` a 2026-10-01, hoje `congelada`, MANUAL desde 2026-10-04, com a data antiga arquivada em `_congelado_ate_historico`; mais o `_reservar_rl_formatos`, a razão por que o duel-commander fica fora), cartas_vigiadas (a VIGIA DE CARTAS de 2026-09-26), reserva (o LIMIAR da reserva «maybe», 2026-10-01), caixas[].decisao / reserva / reserva_fora / comandante / reserva_assinatura (AS FASES, 2026-10-01), revalidacao.foto_manda (A FOTO É A VERDADE, 2026-10-02 — e o `playset_maximo` SAIU do `regras_por_formato` nesse dia; **a `false` e com `desde: null` desde 2026-10-04**, o dia em que as fotos foram apagadas), regras_por_formato: lingua/acabamento dos TRÊS grupos trocados a 2026-10-02 (`_regras_2026_10_02`: duel-commander e pauper `en` + `prefere_foil`, premodern `nonfoil`), basicas.declaradas / declaradas_em (A CONTAGEM DECLARADA, 2026-10-02), mtgtop8 (A RECOLHA e o NUNCA PERDER UM TORNEIO DE PAPEL GRANDE, 2026-10-04: `paginas_indice`, `revisitas_por_corrida` e `grandes.padroes`/`listas_por_evento`/`min_jogadores`), e as TRÊS DECISÕES de 2026-10-04 à tarde: a 14.ª terra da lista de qualificação (`listas_escolhidas.modern` com 1 Island, sem `por_confirmar`) + a `proposta_sideboard` NÃO APLICADA ao lado dela, e a caixa `modern-affinity` DESACTIVADA (`estado: candidata`, sem `assinatura`, o antigo em `_antes`). E, ao FIM do dia de 2026-10-04: **`listas_de_evento`** (a REGRA de escolha da lista real, com a razão de cada critério e a data — ver «A LISTA DE UM DECK É UMA LISTA QUE ALGUÉM JOGOU»), **`decks_de_evento`** (os 11 decks dele que não são caixa: 10 de Modern e o Flow State `por_confirmar`, uma linha por deck), `listas_escolhidas[<id>].evento` (a PROVENIÊNCIA gravada — jogador, evento, data, jogadores, classificação, URL) + `.alternativa`/`.porque`/`.escolhida_por`/`.regra_diria`/`._consenso_anterior` (a média que a caixa mostrava, que NÃO se apaga), `decks_montar` com os **17 marcados**, e `caixas[]._ambito` no standard e nas três de legacy (as palavras dele a pô-los fora da prioridade). E, a **2026-10-05**: `caixas[].principal` + `principal_em` nas **12 caixas que têm lista** (os decks que ficam SEMPRE MONTADOS, com proxy no que falta), a razão e a interpretação em `_sempre_montado`, o `caixas[].sempre_montado` como eixo por caixa (existe e não está escrito em nenhuma), a caixa `premodern-stiflenought` de volta a `fonte: vigiado` / `ref: "Luffy — Premodern"` (com o `_antes_1004`) e a lista do Simone Fierro arquivada em `listas_escolhidas._premodern-stiflenought-anterior`. E, ao FIM de 2026-10-05: **`metagame_fontes.modern`** (`ligas: true` + `min_jogadores_presencial: 0`, com a razão e a data ao lado — SÓ o modern, e SEM repetir a lista de `tiers`, que herda do `_default`: é o interruptor que abre as quatro portas das ligas, ver «TODOS OS TORNEIOS EM MODERN») e `decks_por_formato.modern.versoes[izzet-pinnacle].arquetipo_id` **7614 → 5100** com o antigo em `_arquetipo_id_antes` (as ligas fundiram a divisão do cluster e a anotação do deck principal tinha de a acompanhar)
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

**O 502 NO TELEMÓVEL: NENHUM PEDIDO DO WEBAPP FICA PENDURADO (2026-10-01).** Ele
abriu `https://editar-mtg.baverone.com/` no telemóvel; a casca da Deckboxes
carregou e a secção do deck deu *«não consegui ir buscar
deckboxes/caixa-premodern-stiflenought.json: o servidor respondeu 502»*. Do lado
do PC o pedido não estava lento, estava **a correr**, e ninguém lhe punha um fim.
Motor em `webapp.py` (`em_cache`/`_Calculo`/`DadosAindaNaoProntos`/`escrita`/
`aquecer`), `mtgvault/scryfall.py` (`frente_de_dupla_face`) e `mtgvault/db.py`
(`BUSY_TIMEOUT_MS`); testes em `tests/test_webapp_prazo.py` (11 casos, por HTTP)
e a prova de que chumbam em `tests/_chumba_prazo.py` (9 alvos, **um processo por
caso** — metade do que ali se desliga PENDURA, e num processo só o primeiro que
pendurasse envenenava os seguintes em silêncio).

- **A CAUSA, com a pilha de chamadas e não com um palpite** (`faulthandler` não
  chegava no Windows, por isso a prova foi subir o MESMO `webapp.Handler` num
  porto à parte e imprimir `sys._current_frames()` de 5 em 5 s): o fio parado
  estava sempre em `scryfall.impressoes_foil`, chamado por `loadout.foil_info` ←
  `lots()` ← `allocate` ← `report`. A consulta de recurso para a frente de uma
  carta de dupla face era `name LIKE ? || ' // %'`, e o `EXPLAIN QUERY PLAN`
  dava-a como **`SCAN cards`** — a optimização do LIKE do SQLite não se aplica a
  um padrão que é uma EXPRESSÃO (`? || '…'`) nem a uma coluna de colação BINARY.
  Corre uma vez por carta que nunca saiu em foil, que nos anos 90 são quase
  todas. **E o que a tornou intolerável foi o `oracle_text`**, que entrou no
  catálogo nesse mesmo dia (as quatro protecções da venda): o `catalog.db` passou
  a 143 MB / 112 754 impressões, e cada varredura passou a ler muito mais página.
  Medido na base dele: **276 ms por nome, 550 nomes, 57 s dos 74,5 s** do
  `loadout.report`.
- **A correcção é um INTERVALO DE PREFIXO** (`scryfall.frente_de_dupla_face` +
  `limites_dupla_face`, num sítio só): `name >= 'X // ' AND name < 'X // ' ||
  U+10FFFF` entra pelo `ix_cards_name` que já existia. Medido nos **550 nomes
  reais** dele: **276 ms → 0,29 ms** cada (950×) e **0 diferenças** no resultado,
  comparadas uma a uma. O `U+10FFFF` é seguro porque o SQLite compara TEXT byte a
  byte em UTF-8 e não há ponto de código mais alto. O `conhecida` tinha o mesmo
  padrão e levou a mesma correcção.
- **O `foil_cache` passou a ser partilhado pelas DUAS passagens do `lots()`.** O
  `resolve_slots` corre a sua (`_pcts_da_coleccao`, para os grupos com
  `prioridade_por: "pct"`) **sem cache nenhuma** — o `foil_info` com `cache=None`
  nunca guarda — e o `allocate` corria outra com cache própria: 1 683 consultas
  ao catálogo onde 946 bastam. O `foil_cache` nasce agora ANTES do
  `resolve_slots`.
- **Resultado medido na base dele**: `loadout.report` **74,5 s → 1,97 s** (e
  41,5 s → 2,5 s na comparação lado a lado das duas árvores), e **o motor não
  mexeu um número** — fechar tudo 8 928,35 €, 240 a comprar, 15 caixas, venda
  247c/4 539,39 €, protegidas 24c/2 949,39 €, `rl_sem_historico` 102c/24 393,12 €,
  reservadas 1c/496,52 €, candidatos 1 029c/31 150,15 €, caixa a caixa iguais.
- **O `-wal` VAZIO SAIU DO `_versao()`, e era isto que matava a cache.** O
  `vault.db-wal` **aparece e desaparece** ao ritmo de quem abre e fecha a base — o
  webapp, o `daily` das 03:30, as ordens do runner —, e a versão saltava entre
  `(mtime, 0)` e `(None, None)` **sem uma única carta ter mudado**. A cache era
  atirada fora quase a cada pedido e cada pedido voltava a pagar o relatório
  inteiro. Um `-wal` de zero bytes não tem frames: vale o mesmo que não existir.
  Com dados dentro, continua a contar. Tem caso próprio.
- **O TECTO VIVE NO `do_GET`/`do_POST`, e não em cada rota** — a primeira rota
  nova que se esquecesse dele voltava a pendurar um pedido. Acima de
  `webapp.ESPERA_DADOS` (**25 s**, generoso de propósito: o custo honesto a frio
  é 6–8 s) o servidor responde **503** com `Retry-After` e a frase em português
  (*«estou a gerar os dados das Deckboxes … o cálculo continua e o próximo pedido
  já o encontra feito»*). **503 e não 500**: isto não é uma avaria, é um «ainda
  não». A página já sabia mostrar erros (`paginas.erroDados`); o que nunca lhe
  chegava era um.
- **O CÁLCULO NÃO MORRE COM O PEDIDO.** Corre num fio próprio (`_Calculo`), um só
  por chave (`_EM_CURSO`); quem bate no tecto desiste, o cálculo continua, e o
  pedido seguinte encontra-o feito. Matá-lo era garantir que ninguém chegava ao
  fim. Um cálculo que acabe com a versão já mudada **não escreve** por cima de um
  mais novo.
- **O LOCK DA CACHE JÁ NÃO SE SEGURA DURANTE O CÁLCULO.** Segurava: um
  `GET /metagame.html` ficava doze segundos atrás de um cálculo da Deckboxes que
  não lhe diz nada. Agora o lock só guarda o dicionário. Tem caso próprio.
- **O `with ESCRITA:` passou a `with escrita()`, com prazo** (`ESPERA_ESCRITA`,
  60 s): um `acquire()` sem prazo pendurava um botão do telemóvel para sempre
  atrás de uma regeneração em fundo encalhada. Ao esgotar, 503 a dizer que está a
  gravar outra coisa. A regeneração em fundo leva prazo largo (não há pedido à
  espera dela), mas leva.
- **`PRAGMA busy_timeout = 15 000`** em toda a ligação (`db.connect`, e por isso
  também no `catalog` anexado). O `timeout` do `sqlite3.connect` são 5 s por
  omissão e só vale para o `main`: uma ordem do runner a escrever durante seis
  segundos dava *«database is locked»* a uma página — foi o que ele apanhou às
  15:30 desse dia. **Fica ABAIXO do tecto do pedido de propósito**: primeiro
  espera-se por quem escreve, e só depois se responde. Tem caso que exige as duas
  pontas.
- **O AQUECEDOR é o que torna verdade o «sai em milissegundos»**
  (`vigia_versao`/`aquecer`): um fio vigia o `_versao()` e recalcula sozinho, mas
  só quando a versão está **estável há uma passagem** (começar um cálculo de 12 s
  sobre uma base que está a ser escrita era pedir um resultado a meio) e nunca
  mais do que um por `INTERVALO_AQUECER` (30 s). Arranca **com** o servidor e não
  antes — aquecer primeiro deixava o porto doze segundos sem atender e a tarefa
  `mtgvault-serve` relançava o processo.
- **UM RELATÓRIO SÓ PARA AS DUAS VISTAS** (`webapp.relatorio`): a Deckboxes e a
  Arrumação por fases pediam cada uma o seu. É a decisão de 2026-09-24 sobre o
  Início e a Deckboxes — *"dois relatórios eram duas respostas à mesma
  pergunta"*. **Abre a sua PRÓPRIA ligação** e não recebe a de quem chama: o
  cálculo corre num fio próprio e dava *«SQLite objects created in a thread can
  only be used in that same thread»*. O que atravessa o fio é o `dict`.
  Consequência que vale a pena saber: o primeiro relatório do dia
  **invalida-se a si próprio uma vez** (escreve `ultima = hoje` no
  `arquetipos.json`, que está no `_versao()` — de propósito, porque o `daily`
  também o escreve). É o aquecedor que paga isso, nunca um pedido dele.
- **AS 22 SECÇÕES, medidas por HTTP antes e depois** (o mesmo `vault.db`): o
  índice da Deckboxes **45 240 → 37 ms**, a Arrumação **37 249 → 11 ms**, o
  `metagame.html` **39 717 → 25 ms**, e a pior das 27 partes **57 ms** (era 1–5 ms
  só porque vinham atrás do índice que pagou tudo). **Não era «o
  Stiflenought»**: pedida a frio como PRIMEIRO pedido do servidor, a secção do
  Modern dava **46 911 ms** — era a primeira secção que fosse pedida, qualquer
  que fosse. Com a correcção, o mesmo pedido a frio dá **7,5 s**, e com o
  aquecedor **12 ms**.
- **As outras páginas com dados à parte não tinham o defeito, e foi VERIFICADO e
  não assumido**: o `showcase`, o `reservedlist`, o `cobertura` e o
  `comandantes` só têm regex de rota para `deckboxes` e `arrumacao` — os deles
  caem no servidor de ficheiros estáticos e respondem do disco. Medidos: **1 ms**
  cada, antes e depois.

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
  carta — o mínimo entre impressões do mesmo nome — que é outra pergunta), as
  colunas *hoje* / *há 1 mês* / o gráfico da Reserved List (o MERCADO de uma
  impressão, em nonfoil nas duas pontas da percentagem) e o
  `meta_coverage._visual` (o preço do que FALTA).
  **[CORRIGIDO A 2026-09-25]** esta linha dizia também que o `card_price` era
  *"o que a venda, a regra dos 5 % da RL e a feira usam"* — e era verdade, e era
  esse o defeito. Um mínimo entre impressões a responder a *"quanto vale a cópia
  dele"* punha a Tundra de Revised dele a valer os **0,25 €** de uma impressão
  de Summer Magic. Hoje quem responde é o `loadout.preco_da_copia`, e o
  `card_price` ficou só com a pergunta da COMPRA — ver «O PREÇO DE REFERÊNCIA É
  O DA IMPRESSÃO QUE ELE TEM», abaixo.
  O `refresh_collection` continua com o seu modelo de três camadas: a
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
- **A FONTE passou ao config** (`precos.fonte`; **desde 2026-09-25 é uma CADEIA
  e a principal é o `cardtrader`** — ver a secção a seguir). Estava fixa
  no código pela razão certa — um `MIN` por cima de todas as fontes mudava o
  valor da colecção no dia em que o CardTrader entrasse —, e continua a não ser
  um `MIN`: é uma ORDEM. O `reservedlist.price_maps`
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
    **[RESOLVIDO no MESMO DIA]** a escolha era falsa: ver a secção a seguir —
    a fonte é uma CADEIA, e as 606 sem cotação no CardTrader são respondidas
    pelo Cardmarket, com a linha a dizer de onde veio. Zero sem preço por
    causa da troca.

**O PREÇO DE REFERÊNCIA É O DA IMPRESSÃO QUE ELE TEM, E A FONTE É UMA CADEIA
(André, 2026-09-25, à letra).** *"o que tinha pedido era alterar o preço
REFERÊNCIA para Market Price ou Best Deal, ao invés de MÍNIMO"*. A secção de
cima deu-lhe a RÉGUA (os três modos) e mediu que, com a fonte em `cardmarket`,
**os três davam o mesmo ao cêntimo** — o interruptor existia e não mudava um
número. Esta fecha o pedido: tira os DOIS mínimos e liga a régua a sério.
Motor em `mtgvault/precos.py` (`fontes`, `sql_impressao`, `regua_desde`,
`gravar_fonte`, `fonte_serie`) e `loadout.preco_da_copia`; testes em
`tests/test_preco_referencia.py` (14 casos) + `tests/_chumba_preco_ref.py`;
relatório em `ai-pc/work/revisao/mtgvault-preco-referencia-0925.md`.

- **HAVIA DOIS MÍNIMOS, e só um tinha sido tratado.**
  1. **O mínimo entre OFERTAS** — fechado a 25/09 pelo `precos.oferta_utilizavel`
     (o crivo do riftvault). **Medido agora**, na puxada às 145 edições dele:
     das **53 113** linhas (impressão × acabamento), o filtro muda o preço em
     **43 003** — 81 % —, e só **10 110** ficam iguais. Não é um caso de bordo:
     é a regra. Exemplo real desse dia, um Mountain de 10E com 209 ofertas, 117
     utilizáveis: sem filtro 0,11 € / 0,33 €, com filtro 0,14 € / 0,43 €.
  2. **O mínimo entre IMPRESSÕES** — o `loadout.card_price` faz `MIN` sobre as
     impressões do mesmo NOME. Para o que FALTA está certo (compra-se a mais
     barata) e **fica**. Aplicado a uma cópia dele era a resposta errada à
     pergunta errada, e **era o que a venda, a feira e a regra dos 5 % da RL
     usavam**: a **Tundra de Revised** dele (354,80 €) valia **0,25 €**, o
     preço de uma impressão de Summer Magic; a Mox Opal valia 234,05 € em vez
     de 1 166,58 €; a Gaea's Cradle 272,71 € em vez de 1 066,30 €.
- **A REGRA NOVA, por esta ordem** (`loadout.preco_da_copia`): (1) o preço da
  IMPRESSÃO dela, na cadeia de fontes — é a mesma conta única do valor da
  colecção (`collection.preco_impressao_detalhe`, 24/09), com a tolerância de
  acabamento de sempre; (2) só se nenhuma fonte cotar aquela impressão, o mínimo
  entre impressões, marcado `origem = min-impressoes` — é uma ESTIMATIVA e é
  dita, porque um preço de outra carta somado calado é a mentira que isto veio
  corrigir; (3) nem isso, `None` — *"sem preço"*, nunca 0 €. A linha da venda
  leva `preco_fonte` e `preco_origem`.
- **A FONTE É UMA CADEIA: `cardtrader` → `cardmarket`** (`precos.fontes`,
  `precos.fonte_recurso`). O `market`/`best` só querem dizer coisas diferentes
  com as ofertas de um marketplace por trás, por isso a principal passou a ser
  o CardTrader. O buraco medido a 25/09 — **606 cópias (36 %) que ele não cota**
  — resolve-se por IMPRESSÃO: a primeira fonte da cadeia que a cote ganha e a
  cópia diz de qual veio. **Não é um `MIN` entre fontes**: isso somava a mediana
  das ofertas de uma carta com o Trend de outra, que é exactamente o que a
  `receita` existe para impedir. Tem caso próprio.
- **A CADEIA É MAIS UMA RÉGUA, e trava a Reserved List como o modo.** Três
  defesas, e as três são precisas:
  - **`precos.fonte_desde`** carimba a troca e o **`precos.regua_desde()`** é a
    mais recente entre ela e o `modo_desde`. O `avaliar_rl` encurta a janela até
    lá: enquanto não houver `venda.rl_janela_minima_dias` (25) dias medidos com
    a régua nova, a resposta é **`rl_sem_historico`** — nunca *"não subiu"*.
  - **O preço de hoje e o histórico têm de ser da MESMA fonte.** O histórico
    (`loadout._historico`) lê-se **só da fonte principal**; uma cópia cujo preço
    de hoje veio da fonte de recurso responde `rl_sem_historico` e diz porquê.
    Uma percentagem entre um ponto do CardTrader e outro do Cardmarket é uma
    subida que nunca aconteceu.
  - **As duas pontas medem a MESMA impressão.** O preço de hoje passou a ser o
    da impressão dele; o `_cotacao_em` fazia `min` sobre as impressões do nome.
    Comparar o Revised de hoje com a reimpressão mais barata de há 90 dias dava
    uma percentagem que não é de carta nenhuma — e num sentido mandava vender
    uma carta que valorizou. Tem caso próprio.
- **AS COLUNAS DE EVOLUÇÃO DA RESERVED LIST ficam na `precos.fonte_serie`** (por
  omissão a ÚLTIMA da cadeia, o price guide). Não é incoerência: o *valor* de
  uma cópia é uma cadeia porque a pergunta é *"quanto vale"*; uma *série* é uma
  percentagem e mede-se de ponta a ponta na mesma fonte — e a fonte com série é
  a que tem história. Por isso a página pode mostrar uma evolução enquanto a
  regra dos 5 % responde *"não sei"*: são duas perguntas.
- **AS EDIÇÕES DO CARDTRADER SAEM DA COLECÇÃO** (`prices.edicoes_da_coleccao`,
  hoje **145**, ~3 min). Com a fonte em `cardtrader`, um `CARDTRADER_SETS`
  esquecido era o site inteiro a cair na fonte de recurso sem um único erro — o
  padrão do `event_tier` sobre o número que ele vê todos os dias. A variável
  continua a ganhar quando está escrita.
- **O HISTÓRICO DO MARKETPLACE PODA-SE** (`daily._prune_marketplace`). A
  primeira corrida do CardTrader escreveu **53 113 linhas de histórico, 27 MB**
  (a base passou de 88,2 a 115,3 MB), contra as ~5 400/dia do price guide — e
  o `vault.db` é descarregado e republicado INTEIRO a cada corrida. Dessas,
  **1 025** são de cartas que ele tem ou da Reserved List; as outras 52 088 não
  alimentam página nenhuma (o que a lista de compras usa é o `price_latest`, que
  fica inteiro). Guardam-se essas.
- **A CADEIA EM SQL É UMA SUBCONSULTA CORRELACIONADA** (`precos.sql_impressao`),
  e isso é uma decisão de desempenho tomada duas vezes. A primeira versão era
  uma tabela derivada com `ROW_NUMBER` por cima da `price_latest` inteira: o
  `card_price` é chamado milhares de vezes por relatório e varrer 86 480 linhas
  por chamada punha-o em dezenas de minutos. **Materializá-la numa temporária
  indexada resolvia o tempo e criava dois problemas piores:** (a) o esquema
  `temp` passa a aparecer no `PRAGMA database_list`, e há **quinze ficheiros de
  teste** a apanhar o catálogo pelo ÍNDICE 1 dessa lista — o `webapp.py`
  respondia *"unable to open database: ."* a um POST; (b) qualquer carimbo de
  validade que se guardasse numa tabela contava como escrita e punha a
  temporária a refazer-se a cada chamada. A correlacionada entra pela chave
  primária `(scryfall_id, source, finish)`, lê duas linhas, e **não há cache
  nenhuma que possa responder com um preço de antes**. Tem teste que lê o
  `EXPLAIN QUERY PLAN` e exige que não haja `SCAN` da `price_latest`. Medido: o
  relatório inteiro sobre a base dele com as duas fontes, **32 s**.
- **Onde se troca:** o interruptor **market · best · média** do cabeçalho da
  Deckboxes (agora com a CADEIA ao lado, `cardtrader → cardmarket`, e não só a
  primeira), `py -m mtgvault.cli precos fonte <nome> [--recurso ...]` e
  `precos modo <...>`. O `precos` do CLI mostra a cadeia, a receita de cada
  fonte e as três datas (modo, fonte, régua).
- **MEDIDO na cópia da base de 2026-09-25** (o mesmo `vault.db` nos quatro
  lados, com o CardTrader puxado às 145 edições dele):

  | | A: `main` cardmarket | B: ramo, cardmarket | C: ramo, cadeia, market | D: ramo, cadeia, best |
  |---|---|---|---|---|
  | **preço de referência das 1 678 cópias** | 44 578,72 € | **97 954,17 €** | **134 280,67 €** | 100 134,87 € |
  | valor da colecção (Galeria/Binders/Início) | 97 913,68 € | 97 913,68 € | **134 237,47 €** | **100 094,14 €** |
  | fechar tudo | 6 978,93 € | 6 978,93 € | 9 020,89 € | 7 341,37 € |
  | a comprar / a arrumar | 253 / 225c | 253 / 225c | 253 / 225c | 253 / 225c |

  - **A→B é o mínimo entre impressões a cair** (mesma fonte, mesmo modo): o
    preço de referência das cópias **mais do que duplica**, 509 cópias sobem, 2
    descem, 226 ficam iguais. **A alocação não mexe** — fechar tudo, a comprar
    e a arrumar ao cêntimo e caixa a caixa —, porque a COMPRA continua a ser o
    mínimo entre impressões: é a prova de que as duas perguntas ficaram
    separadas. O valor da colecção também não mexe: essa conta já era por
    impressão desde 24/09.
  - **B→C é a cadeia a entrar**: 454 cópias sobem, 6 descem, 277 iguais;
    **1 072 avaliadas pelo CardTrader, 602 pelo Cardmarket, 4 sem preço** — as
    mesmas 4 de sempre, ou seja **a troca de fonte não deixou uma única cópia
    nova sem cotação**, que era a dúvida de 25/09 de manhã.
  - **C vs D é o interruptor**, e agora vê-se: **34 143,33 €** entre `market` e
    `best` no valor da colecção (117 165,80 € na média), e 1 679,52 € no
    *fechar tudo*. Com a fonte em `cardmarket` os três davam o MESMO ao cêntimo.
  - **A Reserved List: as 102 cópias caem todas em `rl_sem_historico`**, nos
    dois modos — **é a regra a proteger-se**, não uma avaria: a régua mudou hoje
    (`precos.fonte_desde`) e o histórico do CardTrader começa hoje. Voltam a
    decidir-se quando houver 25 dias medidos nesta régua, ou no dia em que ele
    puser a fonte de volta em `cardmarket`.
  - Consequência na VENDA (que está fora da vista, `venda.mostrar: false`, e
    que esta ordem não tocou): o motor continua a escolher **as mesmas 268
    cópias** nos quatro cenários — o que muda é o euro que valem
    (1 566,55 € → 6 033,90 € só pela correcção do mínimo, e 7 491,44 € com o
    CardTrader em `market`).

**SÓ CARDTRADER: A CADEIA PASSOU A UMA FONTE (André, 2026-10-04, à letra).**
*"faz a tua pesquisa dos precos apenas no cardtrader, esquece o cardmarket"* e
*"refaz o meu site com essas alteracoes"*. Fecha a dúvida que 25/09 deixou em
aberto (*"ligar o `cardtrader` hoje era trocar 32 % de valor por 36 % da
colecção sem cotação"*): ele escolheu o CardTrader e aceita o buraco. Só config
e texto de página — **o motor de preços não mudou uma linha**: a cadeia já
sabia ter um elemento só. Testes em `tests/test_so_cardtrader.py` (12 casos) e
a prova de que chumbam em `tests/_chumba_so_cardtrader.py` (9 de 9 pares, um
processo por par); relatório em
`ai-pc/work/revisao/mtgvault-so-cardtrader-1004.md`.

- **`precos.fonte_recurso` ficou VAZIA e `precos.fonte_serie` passou a
  `cardtrader`**, com `fonte_desde: 2026-10-04`. O **modo não se tocou**
  (`market`). O `fonte_serie` escreve-se à mão mesmo sendo hoje redundante (a
  omissão é a ÚLTIMA da cadeia, que agora é a única): no dia em que alguém
  acrescentar uma fonte de recurso, a série não pode mudar de sítio sozinha.
- **«Sem preço» passou de 1 cópia para 390, e isso não é uma carta a
  desvalorizar — é o Cardmarket a sair como recurso.** Medido na cópia da base
  de 2026-10-04, o mesmo `vault.db` dos dois lados
  (`_revisao/medir_cadeia.py`, um processo por cenário):

  | | cardtrader → cardmarket | **só cardtrader** |
  |---|---|---|
  | colecção (market) | 145 567,15 € | **133 354,51 €** |
  | colecção (best) | 102 492,18 € | **90 240,06 €** |
  | cópias sem preço | **1** de 1 678 | **390** de 1 678 |
  | por fonte | 1 282 ct + 395 cm | **1 288 ct** |
  | fechar tudo | 8 300,03 € | **5 802,47 €** |
  | a comprar | 237 | **237** |
  | venda / protegidas / guardar | 113c · 162c · 1c | **iguais** |
  | `rl_sem_historico` | 103 c | **103 c** |

  Das 395 cópias que o Cardmarket avaliava, **6** passaram a ser estimadas pelo
  CardTrader (o mínimo entre impressões, marcado `min-impressoes` e DITO) e
  **389** ficaram sem preço. **Nenhuma cópia muda de lado**: a alocação não
  mexe e as nove saídas da venda têm exactamente as mesmas cópias. Os preços do
  Cardmarket continuam todos na base — o que mudou foi a RÉGUA.
- **O «fechar tudo» caiu 2 497,56 € e quase tudo é UMA carta: a Mishra's
  Workshop** do `cedh-cloud`, que o CardTrader não cota. As compras sem preço
  passaram de **3 para 16 cópias** (13 linhas). **Isto já era assim antes desta
  ordem** — uma falta sem preço entra no total a zero, e o `loadout` conta-a em
  `sem_preco` para a página poder dizer *"no mínimo — N sem preço"*. O que esta
  ordem faz é tornar esse número grande: o *fechar tudo* é hoje um **mínimo** e
  não a conta toda. Se um dia deixar de o dizer, é aqui que se olha.
- **A SÉRIE DA RESERVED LIST FICOU SEM O «HÁ ~1 MÊS», E A PÁGINA DI-LO.**
  Medido (`_revisao/medir_rl_serie.py`): o price guide tem história de
  **2026-08-10** (203 910 linhas) e dá *hoje* 20 084 impressões e *há ~1 mês*
  **8 788**; o CardTrader tem história de **2026-09-25** (14 487 linhas) e dá
  *hoje* **32 370** — mais — e *há ~1 mês* **ZERO**. O `avg30`, que era o
  recurso, está a **0 nas duas fontes**: ninguém o escreve. Logo a coluna e a
  variação ficam vazias em TODAS as cartas durante 21 dias. Um branco sem razão
  ao lado é o defeito que isto fecha: `reservedlist.frase_serie` põe no rodapé
  *«A série de preços é do cardtrader, desde 2026-09-25 — 9 dias. Ainda não
  chega para comparar com há um mês … Não é uma avaria: é a régua a ser
  nova.»*, e a frase **calcula-se** (não se escreve com uma data à mão), por
  isso desaparece sozinha quando a série fizer 30 dias.
- **AS LEGENDAS DE PREÇO DEIXARAM DE TER NOMES DE LOJA ESCRITOS À MÃO.** Eram
  **28** ocorrências visíveis de «Cardmarket» (inventário em
  `_revisao/ver_visivel.py`: o texto visível das 11 páginas, sem `<script>`,
  mais os `data/paginas/**.json` e o código vivo do `deckboxes.js`); ficaram
  **3**. Onde havia um nome escrito, passou a sair da **cadeia em vigor** — se
  ele voltar a ligar o Cardmarket, as páginas dizem-no sozinhas: o **Início**
  (que ainda por cima contava a `price_latest` INTEIRA, 86 818 impressões de
  fontes que não alimentam número nenhum — passou a contar só as da cadeia), a
  **Galeria**, os **Binders**, a **Cobertura**, a **Reserved List** e a
  **Feira**. Os botões *«copiar p/ Cardmarket»* / *«copiar lista Cardmarket»*
  ficaram **«copiar lista»**: o formato não mudou (`N Nome`, com `// Sideboard`
  e `// Basicas`) — o que saiu foi o nome da loja.
- **DUAS EXCEPÇÕES DELIBERADAS, e as duas têm caso de teste** (é o padrão da
  maçaneta do `venda.mostrar`):
  1. **A escala do estado** (MT · NM · EX · GD · LP · PL · PO) continua a dizer
     que é a do Cardmarket, na Arrumação. **Não é um preço**: é o vocabulário
     com que se diz o ESTADO de uma carta, transcrito à letra de
     `help.cardmarket.com/en/CardCondition` para o `data/estado-criterio.md` —
     que é o ficheiro que o passo que avalia LÊ. Tirar-lhe o nome era deixar a
     página sem poder dizer de onde vem a régua. A frase foi reescrita para
     separar as duas coisas (*"a escala … transcrita da fonte; os factores de
     preço por escalão são medidos nas ofertas do CardTrader"*) e saiu-lhe o
     *«porque é lá que vendes»*.
  2. **A saída de stock da venda** — o CSV leva o `idProduct` do Cardmarket e o
     formato aprende-se de `data/cardmarket-stock-exemplo.csv`. Chamar-lhe
     CardTrader era inventar uma integração que não existe. Está atrás do
     `venda.mostrar` (hoje `false`) e da trava manual, **por isso não se vê**
     — são as 3 ocorrências que restam no `deckboxes.js`, e o teste chumba se
     aparecer uma quarta que não seja dali.
- **A RECOLHA DO CARDMARKET NÃO SE DESLIGOU**, e isso é uma decisão. É grátis,
  não se vê, e é o único histórico longo que existe. Há caso de teste a exigir
  que o `load_cardmarket_file` e o passo do `daily` continuem de pé: quem os
  apagar por limpeza tem de decidir em vez de descobrir daqui a um mês que não
  há com que comparar. Voltar atrás é uma linha:
  `py -m mtgvault.cli precos fonte cardtrader --recurso cardmarket`.
- **O `--recurso` VAZIO já funcionava** (`nargs="*"`), e `gravar_fonte` carimba
  a régua na mesma — tem caso próprio, mais o de que repetir é um **no-op** (não
  se reinicia a janela da RL por um clique sem efeito). O que se acrescentou foi
  a prova: o par `recurso_ignorado` do `_chumba` mostra que um
  `if recurso:` em vez de `if recurso is not None:` deixava a cadeia como estava.
- **O campo do vendor da Feira passou de `cardmarket` a `loja`** (é o utilizador
  do VENDOR na loja dele, não a fonte de preço do vault), e **a forma antiga
  continua a ler-se** no config e no endpoint — uma página aberta ontem no
  telemóvel ainda manda o nome velho. O `--cardmarket` do CLI ficou como alias.
  O `feira.texto_cardmarket` passou a `texto_lista`.
- **OS LINKS «VER NO CARDMARKET» NÃO EXISTIAM, e por isso não se converteu
  nada.** Verificado por varrimento de todos os `.py`/`.js` e do HTML gerado:
  **zero** `href` para o cardmarket.com em todo o site; o `cardmarket_id` só se
  usa na ponte do price guide e na coluna `idProduct` do CSV de stock. Não se
  inventaram nove superfícies de links novas. O que ficou apurado, para o dia em
  que ele os queira: o `cardtrader_map` tem **33 833** linhas
  (`scryfall_id → blueprint_id`, de hoje) e
  `https://www.cardtrader.com/en/cards/<blueprint_id>` **responde 200** (sondado
  a 04/10: redirige para `/en-EU/cards/21889-forest-383-tenth-edition`) — mas o
  URL de PESQUISA por nome que parecia óbvio,
  `https://www.cardtrader.com/en/magic/cards?name=…`, dá **404**, e não se
  escreveu um recurso a adivinhar outro formato.
- **UMA ARMADILHA QUE ISTO REPETIU, para não a repetir outra vez:** o
  `_chumba_so_cardtrader.py` escrevia o `colecao_config.json` de volta com
  `json.dumps` e o ficheiro ficou **numa linha só** — 1 inserção, 657 remoções.
  O conteúdo estava certo e a forma morreu: é o commit `ac1f776` outra vez,
  disparado pela ferramenta que devia ser inofensiva. Hoje guarda e repõe o
  **TEXTO** (byte a byte) e escreve a versão alterada com o `configio.escrever`.
  O diff final do config são **4 inserções e 3 remoções**, e um round-trip pelo
  `configio.escrever` devolve-o igual byte a byte.

**«PARA JÁ TIRA O VENDER»: UM INTERRUPTOR, NÃO UMA AMPUTAÇÃO (André,
2026-09-25, à letra).** *"para já tira o «vender»"*. O **«para já» é literal** —
por isso não se apagou uma linha de código: é `colecao_config.json →
venda.mostrar`, hoje **`false`**, e pô-lo a `true` (ou
`py -m mtgvault.cli vender --mostrar on`) devolve tudo exactamente como estava.
Motor do interruptor em `mtgvault/venda.py` (`mostrar()`, `gravar_mostrar()`,
`MOTIVO_DESLIGADO`); testes em `tests/test_venda_interruptor.py` (8 casos) e a
prova de que chumbam sem a funcionalidade em `tests/_provar_chumba.py`
(+ `tests/_chumba_venda.py`, que corre um caso com o interruptor neutralizado).

- **O QUE ELE DEIXA DE VER**, e onde estava cada coisa: a **aba Vender** da
  Deckboxes (`#vender`) com as sete saídas e o bloco **📤 Saída** (o CSV de
  stock, a lista da estante e o «fica de fora»); os botões **«vendida»**
  (`data-vend`) e **«💾 gravar em data/»** (`data-saida`); o item **Vender** da
  barra lateral — e a secção passou de *«Compras e venda»* a **«Compras»**, que
  é o que ela é agora (`site_shell.seccoes()`); no **Início**, o cartão **«Para
  vender»** (era 1 566,55 € a negrito, o terceiro de seis) e o atalho *Vender*,
  que deu o lugar a **Encomendas** para a grelha continuar 3×2; o **chip «a
  vender»** do cabeçalho da Deckboxes e o bloco *«Depois de montar: vender o
  excesso»* do **Plano**; na **Reserved List**, o selo **VENDER** e a caixa **💸
  A vender** (a linha *"não joga em formato nenhum"* FICA — é um facto sobre a
  carta, não um conselho, e é metade da razão por que a página existe); no
  **Metagame**, a frase que mandava o que sobra para a venda e a etiqueta do
  «não quero este»; e a metade **«levar»** da **Feira**. A **Cobertura**, a
  **Caixa RL**, a **Galeria** e o **Showcase** só tinham a barra lateral —
  varridas as nove páginas, no HTML e nos `data/paginas/*.json`.
- **A FEIRA fica, com meia cara, e foi uma decisão.** A ordem dele não nomeou a
  Feira; mas a metade «levar» É a lista de venda, carta a carta e com preço —
  mantê-la era tirar a aba Vender e deixá-la ali com outro nome. Desliga-se com
  o mesmo interruptor (`feira.levar` devolve zeros e `desligado: True`, num
  sítio só, e daí saem o saldo, os textos e o subtítulo) e o **«trazer»** —
  que é uma lista de COMPRAS — fica inteiro. Se ele preferir a Feira inteira ou
  nenhuma, é uma linha.
- **A REVALIDAÇÃO NÃO PODE PERDER CÓPIAS.** O `revalidacao.particao` tinha um
  grupo `venda` com **334 cópias**; esconder o grupo levava-as com ele, e a
  campanha é fotografar a colecção INTEIRA. Agora, com o interruptor desligado,
  essas cópias caem no sítio onde ESTÃO (Caixa RL ou Coleção) e a soma dos
  grupos continua a ser a colecção — medido: 1 678 dos dois lados (caixas 636 ·
  venda 0 · RL 148 · resto 894). Tem teste.
- **NADA SE APAGOU, e é a metade que interessa quando ele voltar a ligar.** O
  `mtgvault/venda.py` está intacto; o `loadout.sell_list` corre a cada relatório
  e continua a calcular as **sete saídas** — é ele que segura a regra dos 5 % da
  Reserved List, o `guardar`, as `reservadas` e os `retidos`, e desligá-lo era
  deixar de saber o que NÃO se vende; o `data/vendas.csv` fica; os
  `data/venda-stock.csv` e `data/venda-estante.txt` que já existem **não se
  apagam** — deixam só de ser reescritos, com a data da última vez que valeram.
  O **CLI continua a imprimir a lista** (`py -m mtgvault.cli vender [--tudo]`),
  com uma linha à cabeça a dizer que não está no site: é por aí que ele e o
  Claude na nuvem vêem o que o motor continua a decidir.
- **O `daily` SALTA o passo `venda-export` e DIZ porquê** (`daily.venda_export`,
  numa função para poder ser chamada por um teste): `[ok] venda-export:
  saltado: a venda está desligada (…)`. Saltar em silêncio deixava o log igual
  a um dia em que o passo corre, e é aí que se perde a diferença entre «está
  desligado» e «avariou».
- **OS DOIS ENDPOINTS DE ESCRITA RECUSAM-SE EM CONDIÇÕES.** Uma página aberta no
  telemóvel antes de hoje ainda pode mandar `POST /api/vender` (o botão que
  APAGA cartas da base) e `POST /api/venda-export`. `webapp.VendaDesligada` é
  subclasse de `ValueError`, por isso o `do_POST` traduz num **409 com a frase
  em português** e o `_exige_venda()` corre **antes** do `migracao.backup` —
  uma chamada recusada não deixa um ficheiro de backup atrás dela.
- **A PERGUNTA VIVE NUM SÍTIO SÓ** (`venda.mostrar`). São nove superfícies a
  fazê-la; a segunda que a respondesse por si própria deixava um item da barra a
  apontar para uma aba que já não existe — a lição do `e_foil`, do `vistoId` e do
  `precos.sql()`. Tem teste que varre o código à procura de quem volte a ler a
  chave à mão. Do lado do browser a pergunta é **uma só** (`VENDA_ON()`, = o
  payload trazer `venda: null`), e daí saem a aba, o chip, o Plano, as
  `abasFixas()` (que tiram o `#vender` de um favorito velho e a aba `vender`
  guardada ontem no `localStorage`) e os botões.
- **UMA EXCEPÇÃO deliberada ao «nem uma palavra»**: o **nome da chave**
  (`venda.mostrar`) aparece onde a página explica uma ausência — a metade
  «levar» da Feira. É a maçaneta da porta que acabou de fechar; sem ela, a
  explicação mandava-o procurar. O teste desconta-a, e só a ela.
- **OS MOLDES PASSARAM A SER FUNÇÕES** (`_tmpl()` no `deckboxes`, `inicio`,
  `reservedlist` e `metagame`). Eram constantes de módulo com a barra lateral e
  o rodapé já lá dentro, calculados no instante do `import`: o molde ficava com
  a resposta que o config deu a quem importasse primeiro. É concatenação de
  strings, corre uma vez por página.
- **MEDIDO na cópia da base de 2026-09-25**, com o interruptor nos DOIS estados
  e o mesmo `vault.db`: o `loadout.report` é **igual ao cêntimo e caixa a
  caixa** — fechar tudo **6 978,93 €**, 253 a comprar, 225 a arrumar (129
  linhas), venda 268c/1 566,55 €, venda_rl 66c/4 915,91 €, rl_segurar
  36c/3 618,39 €, rl_sem_historico 0, guardar 2c/14,71 €, reservadas
  1c/100,00 €, retidos 0, as 15 caixas; e a saída para o Cardmarket continua a
  produzir-se a pedido (334 cópias / 6 482,46 € em 158 linhas). Nas nove páginas
  geradas: **zero** palavras de venda no texto visível, **zero** `#vender`,
  **zero** botões.

**A VIGIA DE CARTAS: «VAI CONFERINDO» (André, 2026-09-26, à letra).** Ele comprou
**4× «Kasmina, Enigma Sage»** e **2× «Enter the Infinite»** por causa de um combo
novo e quer saber quando aparecerem decklists com ele — *"vai conferindo"*. O que
interessa é o **Modern**. A segunda peça é o **«Jace's Machinations»**, do
*Reality Fracture*, que só sai a **02/10/2026**: hoje **não pode existir** uma
única lista de torneio com o combo, e é precisamente por isso que isto é uma
funcionalidade e não uma resposta — o valor está em ele ser avisado **no dia** em
que a primeira aparecer, sem pedir a ninguém. Motor em `mtgvault/vigia.py` (só
config + um ficheiro de estado; nada de esquema novo) e `mtgvault/aviso.py` (o
toast); config em `colecao_config.json → cartas_vigiadas`; passo `vigia-cartas`
do `daily`; bloco no topo do `metagame.html`; testes em `test_vigia_cartas.py`
(6 casos) e a prova de que chumbam sem a funcionalidade em `tests/_provar_chumba.py`
(+ `tests/_chumba_vigia.py`).

- **O FILTRO DE TIER TINHA DE SER ABERTO — E SÓ PARA AS CARTAS VIGIADAS.** É a
  parte que, sem ela, estragava isto em silêncio. A regra dele de 2026-09-07
  (*"não quero listas de league; quero challenge, showcase, e presenciais com 64
  ou mais jogadores"*) está certa para o metagame e é **exactamente ao contrário**
  do que serve aqui: a primeira aparição de um combo novo **é** um 5-0 de league
  ou um torneio de 20 pessoas. Com o filtro ligado, a lista que ele quer ver era
  recusada à entrada (`store_decklist` devolve `None` a uma liga) e, se tivesse
  escapado, o `analysis.prune_leagues` apagava-a **na mesma corrida**, minutos
  depois. O aviso nunca chegava e **nenhum passo dava erro** — o padrão do
  `event_tier` sobre a única pergunta que ele fez. São **três portas**, e as três
  só se abrem para uma lista que TENHA uma carta vigiada
  (`vigia.nomes_na_lista`, num sítio só): (1) `sources.harvest_mtgo` deixa de
  saltar as páginas de liga dos formatos vigiados — sem descarregar a página não
  há como saber o que ela tem; (2) `sources.store_decklist` guarda-a, e passa
  também à frente do `so_jogadores_vigiados` (o Pauper); (3)
  `analysis.prune_leagues` não a apaga. **Para tudo o resto o filtro fica como
  estava**: a liga sem carta vigiada continua a não se guardar, e a vigiada
  **continua a não contar para o metagame** (`lista_conta` e `counting_sql`
  recusam-na — tem caso de teste). Uma primeira aparição num 5-0 não é um dado de
  metagame; é um aviso.
- **O CUSTO, MEDIDO CONTRA O MTGO.COM A SÉRIO** (`_revisao/medir_vigia.py`, duas
  corridas a 2026-09-26): com o Modern vigiado são **3 páginas a mais** por
  corrida (uma página de liga por dia, `MTGO_DAYS = 3`), **87–153 listas lidas**
  e **+41 s a +69 s** no `harvest-mtgo` (o mtgo.com varia muito: 1,2 s a 31 s por
  página, e uma das corridas devolveu a página truncada — o `daily` já tolera
  isso e continua). **Guardadas: ZERO.** Não é um acidente da medição — é o que
  tem de ser hoje: nenhuma lista de Modern joga estas cartas, e uma delas ainda
  não existe. Cada carta vigiada num formato NOVO acrescenta as páginas de liga
  desse formato; vigiar uma carta de Duel Commander é grátis (lá as ligas já
  contavam).
- **O AVISO CHEGA-LHE POR QUATRO CAMINHOS**, e é de propósito — *"sem ele ter de
  ir procurar"*: (a) o **stdout** do passo (uma linha por carta vigiada, e o que
  apareceu com `[NOVA]`, o link e o que falta para montar — o pormenor é impresso
  pela função, como no `_watch`; o `_step` só guarda o resumo de uma linha em
  `job_runs`); (b) o **ficheiro de estado** `data/vigia-cartas.json`, com carta,
  formato, evento, data, jogador, colocação, link, tier e fonte; (c) o **bloco no
  `metagame.html`**, com o tier À VISTA (*"League"* é o sinal mais valioso aqui, e
  escondê-lo dava a impressão de ser um Challenge); (d) um **toast do Windows**,
  `mtgvault/aviso.py`. O padrão do toast é o que o `ai-pc` descreve
  (`prompts/baiakidle-coach.md`: *"BurntToast se existir; senão msg/balloon
  stdlib"*) — mas a tarefa que o faria (`baiak-relogio`) **não existe**, e
  varrido o `ai-pc` não havia uma linha de código que emitisse um toast: reusou-se
  a RECEITA, não código que não há. Vai por `-EncodedCommand` (base64 UTF-16LE)
  para não ter de escapar apóstrofos nem passar pelo code page da consola, **nunca
  levanta** (devolve `"toast (balloon)"` / `"sem toast: …"`, e é essa string que
  fica no estado) e é **injectável**, que é como o teste prova que o segundo dia
  não avisa. Testado neste PC a 2026-09-26: **`toast (balloon)`** — o BurntToast
  não está instalado.
- **UM TOAST POR LISTA NOVA, E MAIS NENHUM.** A identidade de um avistamento é
  `formato|carta|data|jogador|evento` (`vigia.chave`) e **não o `decklist_id`**:
  a deduplicação entre fontes apaga e reinsere a mesma lista, e com o id na chave
  o aviso repetia-se sem nada de novo ter acontecido. Tem caso próprio (muda-se o
  id à mão e exige-se silêncio). Uma lista com as **duas** cartas vigiadas são
  dois avistamentos e **um** toast.
- **O ESTADO É CUMULATIVO, e guarda a LISTA.** O `prune_decklists(30)` apaga as
  decklists ao fim de um mês: sem isto o combo aparecia em Outubro e desaparecia
  da página em Novembro. Por isso cada avistamento leva a decklist inteira
  (`[[board, nome, qty], …]`). **O que NÃO se guarda é a lista de faltas** — essa
  calcula-se sempre da base, porque ele vai fotografar as cartas e uma falta
  congelada passava a mentir no dia seguinte.
- **AS FALTAS SAEM DA BASE, E A PÁGINA DI-LO.** Ele diz ter 4 Kasmina e 2 Enter
  the Infinite; a base tem **0 de cada** — as cópias novas só entram quando ele
  as fotografar (*"só a foto cria cópias"*, 19/09). Não se inventa que as tem: a
  posse é a `paginas.posse_total` (a colecção inteira) e a nota fixa
  (`vigia.NOTA_FALTAS`) diz que uma cópia só entra com a foto. E é **sem regra de
  material**, de propósito: uma lista de metagame não é uma caixa — não tem grupo
  de formato, e aplicar-lhe o *tudo foil e inglês* do SPML era inventar uma
  exigência que ele não pôs a um deck que ainda não decidiu montar.
- **O ficheiro de estado vai no `git add` do `daily.yml` e no `EXTRA_COMMIT` da
  tarefa `mtgvault-daily`**, pela razão do `arquetipos.json`: se só existisse
  numa das corridas, a outra dava tudo por novo e avisava outra vez. No
  `daily.yml` vai **à parte e com `-f`** — o ficheiro só existe quando há cartas
  vigiadas, e um `git add` a um caminho que não existe falhava e levava o commit
  das páginas atrás dele.
- **SEM CARTAS VIGIADAS NADA MUDA**, e isso tem caso de teste: a liga volta a ser
  recusada à entrada, a poda volta a apagá-la, o `harvest` volta a saltar a
  página, o passo do daily diz *"sem cartas vigiadas — nada a fazer"* em vez de
  saltar calado, a secção do Metagame **não existe** e **não se escreve ficheiro
  de estado nenhum** (nem um commit por causa dele). Esvaziar a lista é o
  interruptor, como no `venda.mostrar`.
- **MEDIDO na cópia da base de 2026-09-26** (7 970 listas, 2 279 de Modern):
  `vigia.achados` **0 avistamentos em 0,14 s**, `verificar` **0,14 s**,
  `prune_leagues` **0 apagadas** (igual — a base já não tem ligas), e o estado
  escrito com as duas cartas a *"ainda sem listas"*. O `loadout.report`, a venda
  e as páginas **não foram tocados**: esta funcionalidade não lê a alocação.
- **Por fazer, e é uma linha:** o **«Enter the Infinite»** não está vigiado (a
  ordem dele pedia só as duas), e a vigia não sabe que as três cartas são **um
  combo** — avisa por carta. Se quiser *"avisa-me só quando aparecerem as três na
  mesma lista"*, é uma chave nova (`combo: [...]`) no mesmo sítio.

**O CONSENSO É POR COMANDANTE, NUNCA PELA ETIQUETA DO CLUSTERING (André,
2026-10-01).** *"Quero consenso de Duel Commander do deck dele (comandante CLOUD)
sempre actualizado, da mesma forma que já tem para os arquétipos de Modern"* — e
*"tem de passar a correr no mtgvault-daily das 03:30, não é um relatório de uma
vez"*. Motor em `mtgvault/consenso.py`, página `comandantes.py` →
`comandantes.html`, passo `consenso-comandante` do `daily`, config em
`colecao_config.json → consenso_comandante`; testes em
`tests/test_consenso_comandante.py` (12 casos, com ponta a ponta por HTTP).

- **A IDENTIDADE DE UM DECK DE COMANDANTE É O COMANDANTE**, e a etiqueta do
  clustering não serve aqui: medido na base de 01/10, a tabela `archetypes` tinha
  **870** etiquetas de `duel-commander` e **808 delas sem uma única lista**; as
  que tinham chamavam-se *"Aragorn, King of Gondor / Sulfur Falls / Stormcarved
  Coast"* — três cartas distintivas que mudam de corrida para corrida. É o mesmo
  defeito que o `mtgvault/arquetipos.py` fechou para o Premodern (ver «A IDENTIDADE
  DE UM ARQUÉTIPO É O NÚCLEO»), mas numa pergunta em que a resposta certa está
  escrita na própria carta. Tem teste: a MESMA etiqueta com comandantes diferentes
  dá dois decks, etiquetas diferentes com o mesmo comandante dão um.
- **A BASE NÃO GUARDAVA O COMANDANTE, e isso não era descuido.** O
  `decklist_cards.board` tem `CHECK (board IN ('main','side'))` e nas 652 listas de
  `duel-commander` **só havia `main`** — as duas fontes servem o comandante no
  SIDEBOARD (o `SB:` do `.dec` do mtgtop8, o `sideboard_deck` do mtgo.com) e o
  `store_event`/`harvest` reencaminham-no para o mainboard, porque é lá que conta
  para as 100 cartas e porque é isso que faz o `content_hash` das duas fontes
  coincidir (sem isso a deduplicação entre elas não funciona). A informação de
  *qual* das 100 era o comandante era deitada fora no momento da recolha.
- **E NÃO SE PODE ADIVINHAR pelas cartas.** As listas de DC trazem em média **6
  lendárias de quantidade 1** (até 30 numa só), e o crivo pela identidade de cor
  (o comandante tem de conter a CI de todo o deck) deixava **0 ou mais do que um**
  candidato em **409 das 652** listas — porque **609** delas têm cartas que o
  catálogo ainda não conhece (o formato joga sets do mês).
- **A REGRA, em duas metades, e as duas são honestas:**
  1. **Daqui para a frente a FONTE diz qual é** (`commander_fonte = 'sideboard'`).
     O `mtgtop8.comandantes_do_dec` e o `sources.store_event` lêem o sideboard
     ANTES de o fundirem no main e passam o nome ao `store_decklist`. Não é um
     palpite: é o dado que estava a ser perdido.
  2. **Para as listas que já cá estavam, deriva-se pela ORDEM DE INSERÇÃO**
     (`'ordem'`): o comandante vem no FIM do `.dec` e o `store_event` faz
     `main += side`, por isso a ÚLTIMA linha de `decklist_cards` de uma lista de
     comandante é o comandante — e a `decklist_cards` é uma tabela com `rowid`, por
     isso essa ordem sobreviveu. **Medido** nas 652 listas: a última linha é uma
     lendária criatura/planeswalker de quantidade 1 em **554**, está fora do
     catálogo (sets recentes: *Brigid, Clachan's Heart*, *Terra, Magical Adept*,
     *Aang, Swift Savior* — todos comandantes) em **97**, e há **1** caso real a
     mais (um `Legendary Enchantment — Background`, que é mesmo uma segunda carta
     de comandante). **Controlo:** a PRIMEIRA linha só é lendária de quantidade 1
     em **29** das 652 — o sinal é posicional, não um acidente de haver muitas
     lendárias.
- **GRAVA-SE, NÃO SE RECALCULA** (ordem dele, à letra). `decklists.commander` +
  `decklists.commander_fonte`, nos **três sítios** (`schema.sql`, `db._migrate()` e
  quem as escreve). O `derivar` é **idempotente** e só toca nas linhas a NULL: um
  palpite nunca pisa o que a fonte disse. **O ÍNDICE do `commander` NÃO vive no
  `schema.sql`** — esse ficheiro corre inteiro antes do `_migrate`, e numa base já
  criada a coluna ainda não existe nesse momento: o `CREATE INDEX` rebentava o
  `db.init` com *"no such column: commander"* em todas as páginas e no `daily`.
  Aconteceu nesta mesma ordem, e é a armadilha de 2026-09-09 (o
  `ix_copies_validado`) outra vez. Tem teste.
- **QUE LISTAS CONTAM — medido, não adivinhado, e é a parte que podia ter dado em
  nada.** A regra do Modern (sem ligas, presencial com 64+ jogadores) **deixa o
  formato sem amostra**. Sobre as 652 listas de 01/10 (`_scratch/medir_filtro.py`):

  | listas | do Cloud | comandantes com ≥10 listas | hipótese |
  |---|---|---|---|
  | **652** | **41** | 19 | ligas + presencial sem mínimo ← **escolhida** |
  | 518 | 37 | 14 | sem ligas, presencial sem mínimo |
  | 425 | 26 | 11 | com ligas, presencial 16+ |
  | 291 | 22 | 8 | sem ligas, presencial 16+ |
  | 182 | 4 | 2 | com ligas, presencial 64+ |
  | **48** | **0** | 0 | **sem ligas, presencial 64+ (a regra do Modern)** |

  Escolheu-se a primeira — que é, por acaso, exactamente a regra que ele já tinha
  dado para o Duel Commander a 2026-09-07 (*"menos Duel Commander, que pode ter
  menos jogadores e pode ser ligas"*). **Por isso o filtro desta página é o
  `sources.lista_conta`/`counting_sql` de sempre e NÃO um segundo filtro ao lado**:
  a lição do `event_tier` é que o segundo filtro discorda do primeiro em silêncio.
  Ajusta-se em `metagame_fontes → duel-commander`, e há teste que prova as três
  pontas (com ligas 7, sem ligas 3, com mínimo de 64 → 0).
- **O que é DESTA página está em `consenso_comandante`**: `formato`,
  `comandante` (o que abre — hoje o Cloud), `min_listas` (8), `nucleo_pct` (90),
  `flex_pct` (40) e `max_comandantes` (40). Os papéis são por **percentagem** e
  não por número de cópias: o formato é **singleton**, a moda de cópias é 1 em
  praticamente tudo, e o que separa uma carta obrigatória de uma opção é em
  quantas listas ela aparece. (São mais apertados do que os do
  `commander_decks.tiers` — 50/25/15 — de propósito: aquele CONSTRÓI uma lista de
  100 cartas a partir do consenso, este diz de cada carta quão obrigatória é. São
  duas perguntas.)
- **O comandante que abre é SEMPRE o do config, mesmo sem listas.** Abrir no mais
  jogado quando o dele não tem listas era responder a outra pergunta sem avisar;
  a página diz *"ainda não há nenhuma lista deste"*, que é uma resposta. Tem caso
  próprio (e com um nome que nem está no catálogo também não rebenta).
- **A PÁGINA segue a decisão de 2026-09-15**: casca de **34 KB** + índice de
  **30 KB** + **uma parte por comandante** (40 ficheiros, 904 KB no total, ~22 KB
  cada, ida buscar ao toque); o que ABRE vem também no índice, para o primeiro
  ecrã não precisar de um segundo pedido; um `fetch` que falhe diz-lho em
  português (`paginas.erroDados`). As imagens são da impressão que ele TEM
  (`paginas.img_map`), com `loading="lazy"`, `decoding="async"` e o tamanho
  escrito. A pasta `data/paginas` subiu de 3,5 para **4,4 MB** — a escala do
  `showcase/` (1,5 MB).
- **MEDIDO na base de 2026-10-01:** 652 listas de `duel-commander` (01/09 a
  29/09), **652 comandantes derivados** (`sideboard` 0 — as listas novas é que
  virão por aí), **113 comandantes** com listas que contam, **533** listas nos 40
  que a página mostra. O **Cloud, Midgar Mercenary** tem **41 listas**: núcleo
  **36**, flex **39**, raro **105** (180 cartas), e ele tem **2 cópias** do
  comandante. As 12 cartas a 100 %: Benevolent Bodyguard, Mother of Runes, Ocelot
  Pride, On Thin Ice, Phelia, Skrelv, Skullclamp, Snow-Covered Plains, Solitude,
  Stoneforge Mystic, Swords to Plowshares, Umezawa's Jitte — **tem todas**. A
  seguir vêm Phelia (37), Brigid (35), Slimefoot and Squee (32), Aragorn (30).
- **Nada da alocação, da venda ou dos preços foi tocado**: este módulo não lê a
  `copy_allocation` nem o `loadout`. A bateria inteira (63 ficheiros) ficou verde.

**O NOME DO ARQUÉTIPO VEM DA FONTE (André, 2026-10-02, à tarde, à letra).**
*"Procura no mtgtop8, lá tem os nomes, e a partir daí já tens ideia do que são as
listas."* Tinha razão, e o nome estava a ser deitado fora **na recolha**. Motor em
**`mtgvault/nomes.py`** (a votação, num sítio só), `mtgtop8.parse_deck_archetypes`
+ `backfill_archetype_names`, colunas `decklists.arquetipo_fonte` /
`arquetipo_fonte_de`, passo `nomes-arquetipos` do `daily`, CLI
`py -m mtgvault.cli nomes [estado|clusters|recuperar]`. Testes em
`tests/test_nomes_arquetipo.py` (12 casos) e a prova de que chumbam em
`tests/_chumba_nomes.py` (6 alvos / 9 casos).

- **ONDE É QUE O NOME ESTAVA A SER DEITADO FORA.** A página do EVENTO do mtgtop8
  traz o nome ao lado de cada deck — `<a href=?e=91451&d=894542&f=PREM>Landstill
  </a>`, e o título diz *"#2 Landstill - Vittorio Piatti"* — e a recolha abria
  essa página (é de lá que saem os ids dos decks, o jogador e o nº de jogadores) e
  **só lia o `.dec`**, que tem cartas e não rótulos. Havia **2 635** listas de
  `mtgtop8` na base e **nenhuma coluna** onde o nome estivesse. É a MESMA falha do
  comandante, fechada no dia anterior: *a fonte dá a informação e a recolha
  perde-a*. E estava escrita no código como se fosse um facto do mundo — o
  `meta_coverage._name_for` dizia *"a fonte não nos dá o nome do arquétipo — o
  mtgtop8 tem `.dec` de cartas e não de rótulos"*.
- **O QUE HAVIA EM VEZ DISSO, medido:** o `archetypes.label`, que se chama
  *"Solitary Confinement / Argothian Enchantress / Sterling Grove"*. São **7 499**
  etiquetas, **6 845 sem uma única lista** (91 %), contra **684** nomes a sério
  que a fonte dá. O agrupamento **funciona** — esse cluster de 108 listas É a
  Enchantress — e é por isso que não se apagou: o que lhe faltava era o nome.
- **A REGRA, em duas metades, e as duas num sítio só (`mtgvault/nomes.py`):**
  1. **o nome da FONTE ganha sempre**;
  2. **onde não houver, o grupo HERDA** o mais votado entre as listas dele que
     TENHAM nome. É isto que dá nome às listas de `mtgo`, que não trazem nenhum.
  Sem nenhuma das duas, fica o nome GERADO de sempre (cores + carta-chave) e vai
  marcado **provisório**, com a etiqueta ao lado. Um nome inventado com o mesmo
  aspecto de um nome verdadeiro é o que custou três erros nesta semana.
- **A PERGUNTA É UMA VOTAÇÃO SOBRE UM CONJUNTO DE IDS** (`nomes.nome_das_listas`),
  e é a mesma primitiva nos TRÊS sítios que a fazem: o cluster da tabela
  `archetypes` (metagame, cobertura, sugestões, deckboxes), o cluster do
  **showcase** (que tem agrupamento próprio) e o arquétipo de uma **CAIXA** (a
  arrumação por fases). Dois contadores ao lado discordavam um dia qualquer, em
  silêncio — a lição do `event_tier`, do `e_foil` e do `precos.sql()`. **O
  desempate é ALFABÉTICO** e nunca a ordem em que as linhas saem da base: um nome
  que muda de um dia para o outro sem nada ter mudado é o defeito que isto veio
  corrigir (foi o que aconteceu ao *"Dimir Psychatog"*, que passou a *"Dimir
  Polluted Delta"* na corrida seguinte). Tem teste que varre o código.
- **O HERDADO NÃO SE GRAVA, e é deliberadamente o CONTRÁRIO do `commander`** (que
  ele mandou gravar a 01/10). O que a fonte disse É um dado e está gravado; o
  herdado é uma CONTA sobre esse dado, e acerta-se sozinha no dia em que entrar
  uma lista nomeada a mais ou o agrupamento mudar. Gravá-lo era criar uma segunda
  verdade que envelhece em silêncio.
- **UMA PÁGINA POR EVENTO, NUNCA UMA POR DECK.** As 2 635 listas vivem em **413
  eventos** e a página do evento traz os nomes de todos de uma vez. Medido:
  **413 páginas em 682 s** (1 pedido/s, o `_get` de sempre), **2 617 listas com
  nome, 18 sem** (a página do mtgtop8 não nomeou aquele deck). **O progresso é a
  PRÓPRIA BASE e não um ficheiro:** `arquetipo_fonte_de` vale `evento` (lida na
  recolha), `recuperado` (lida pelo backfill) ou **`sem-nome`** com o nome a NULL
  — o mesmo truque do `event_players` a gravar 0. Daí sai a retomabilidade de
  graça: um evento feito não volta a ser pedido, e **um evento que FALHA não se
  marca** (perder o nome para sempre por causa de uma falha de rede de um segundo
  era o preço de simplificar aqui). Tem dois casos de teste.
- **A COLUNA NOVA NOS TRÊS SÍTIOS, E O ÍNDICE NO `_migrate`.** `schema.sql`,
  `db._migrate()` e quem a escreve (`sources.store_decklist` +
  `sources.store_manual`); o `CREATE INDEX ix_dl_arquetipo` nasce **depois do
  ALTER** e nunca no `schema.sql` — esse corre inteiro antes do `_migrate` e numa
  base já criada a coluna ainda não existe nesse momento. É a armadilha de
  2026-09-09 (`ix_copies_validado`) e de 2026-10-01 (`ix_dl_commander`), que
  rebentava o `db.init` com *"no such column"* em todas as páginas e no `daily`.
  Tem caso que reconstrói a `decklists` sem as colunas e manda abrir.
- **A NEGAÇÃO DA ASSINATURA (`assinatura_sem` / `reserva_assinatura_sem`), e é a
  correcção mais cara do dia.** A ordem da manhã deu à **UW Replenish** a
  assinatura `["Replenish"]` sozinha, com 186 listas — e **TODAS as 124 listas de
  Enchantress jogam `Replenish`**. Eram dois decks num consenso que não é de
  nenhum: as 124 são verde-brancas (Wild Growth, Mirri's Guile, Serra's Sanctum,
  Sterling Grove, Solitary Confinement) e as outras **62** são o combo
  azul-branco (Attunement, Frantic Search, Opalescence, Decree of Silence,
  Intuition). O operador novo é o mesmo `none` que o `archetype_rules.json` já
  usava para os separar, e pela mesma razão escrita lá: *"o `_known_name` chamava
  «Replenish» à Enchantress E ao UW Replenish, porque bate na primeira carta que
  encontra"*. Entra nos DOIS ramos do `ids_por_assinatura` (o `IN` e o `EXISTS` da
  conjunção): num só, a mesma pergunta tinha duas respostas conforme o `todas`.
- **E A FONTE CONFIRMA A SEPARAÇÃO, que é a prova que a ordem pediu.** Das 124
  listas com Argothian Enchantress, as que têm nome dizem **Enchantress 35** (+1
  *"Enchanters"*, variante de escrita) e **zero** dizem Replenish; das 62 sem
  Argothian, **Replenish 30** + *"Uw Replenish"* 5, e **zero** dizem Enchantress.
  Os números dele batem ao exemplar. Ficou `["Argothian Enchantress",
  "Enchantress's Presence"]` na negação (as mesmas duas do `archetype_rules.json`,
  por coerência), o que dá **61** e não 62: a lista a mais joga
  `Enchantress's Presence` sem Argothian, ou seja é Enchantress.
- **A ENCHANTRESS FOI REPOSTA.** A ordem da manhã mandou dissolvê-la e isso foi
  um erro dela: ele repôs o deck. Voltou a `caixas` com `prioridade` 7 e a
  `premodern_arquetipos_alvo`; a caixa estava **vazia** (0 cópias alocadas), por
  isso não houve cartas a mover. Quem se dissolveu foi **só a Jeskai Control**.
  Dois testes que afirmavam o contrário foram corrigidos
  (`test_caixas.caso_o_config_a_serio_ja_esta_na_forma_nova`, 16 → **17 caixas**,
  e `test_pioneer_jeskai`).
- **O QUE O ANDRÉ VÊ, trocado em cinco superfícies.** O `_name_for` do
  `meta_coverage` passou a ter o `_nome` à frente (que devolve
  `{nome, origem, provisorio}`), e por aí entram a **Cobertura**, o **Metagame**,
  as **Deckboxes** (candidatos e sugestões) e o `webapp`. O **Showcase** tinha
  nome próprio (o par de cartas distintivas) e passa pela mesma votação. A
  **Arrumação por fases** ganhou, ao lado da carta-assinatura de cada deck, o
  nome que a fonte dá às listas que ela apanhou — **é a conferência da assinatura,
  à vista**: se o mtgtop8 chama dois nomes àquelas listas, a assinatura está a
  juntar dois decks. Os **Comandantes** não mudaram, de propósito: lá a identidade
  é o COMANDANTE (01/10) e não há etiqueta nenhuma à vista.
- **ANTES E DEPOIS, na Cobertura de Modern** (o mesmo `vault.db`): *"Mono-Verde
  Soul-Guide Lantern"*, *"Izzet Lava Dart"*, *"Esper Flickerwisp"*, *"Boros
  Wrenn's Resolve"*, *"Izzet Welding Jar"* passaram a **Broodscale Bloodchief,
  UR Cutter Prowess, Esper Blink, Boros Ponza, Pinnacle Affinity** — cada um com
  *"mtgtop8 · N de M listas"* por baixo, que é uma afirmação que se confere. No
  Pioneer, *"Golgari Professor Dellian Fel"* → **The Rock**; no Standard,
  *"4 cores Nowhere to Run"* → **4/5C Control**.
- **COBERTURA DOS NOMES, medida:** das **7 808** listas, **2 617** têm nome da
  fonte, **3 909 herdam-no** do grupo e **1 282** ficam sem (214 dessas não têm
  grupo nenhum). Das **5 173 listas de `mtgo`**, que não trazem nome nenhum,
  **3 894 passam a ter** e 1 279 não — e as que não têm concentram-se onde não há
  mtgtop8 para as nomear: **Vintage 468** e **Pauper 137** são ZERO nomes (o
  Pauper só guarda as listas do Luffy, do mtgo), e o resto são listas sem grupo.
- **O MOTOR NÃO MEXEU UM NÚMERO, e foi medido lado a lado com o MESMO `vault.db`**
  (worktree em `_revisao/main-nomes`): **o código do ramo com o config do `main`
  dá tudo igual ao cêntimo e caixa a caixa** — fechar tudo 14 812,56 €, 348 a
  comprar, 294 a arrumar em 159 linhas, venda 115c/1 824,28 €, `rl_sem_historico`
  104c/25 332,29 €, `guardar` 11c/1 475,37 €, `protegidas` 157c/4 989,13 €,
  candidatos 673c/21 053,81 €, as 16 caixas. **O que mexe é só a correcção do
  config**, e explica-se ao cêntimo: a caixa Enchantress volta com **37 % · 22 a
  comprar · 212,27 €**, e o *fechar tudo* passa a **15 024,83 €** = +212,27 € —
  **as outras 16 caixas iguais ao cêntimo e à percentagem**, a UW Replenish
  incluída (92 %, 5 a comprar, 14,10 €: a assinatura é a IDENTIDADE e não a
  lista, e a lista dela vem do `decks`).
- **E UMA CONSEQUÊNCIA QUE NÃO SE ESCONDE: +5 cópias na lista VENDER.** Candidatos
  673 → **678** (21 053,81 € → 21 251,82 €). Entraram **2 Argothian Enchantress
  (USG, 167,62 €)**, **2 Enchantress's Presence (ONS, 28,66 €)** e **2 Choke
  (TMP, 5,16 €)**, e saiu 1 Frantic Search. Porquê: até agora eram a reserva R5 da
  **UW Replenish** — porque a assinatura dela apanhava as listas de Enchantress —
  e essa protecção era um ACIDENTE. Agora a Enchantress é que as devia proteger, e
  **não as protege**, pela razão da secção a seguir. São cartas que ele
  provavelmente quer guardar: a venda está fora de vista (`venda.mostrar: false`)
  e congelada (trava manual), por isso há tempo para decidir.
- **O BURACO DA RD, QUE ISTO PÔS À VISTA E NÃO CRIOU — e é o primeiro ponto da
  próxima ordem.** A **RD** protege o que está **FISICAMENTE** na caixa
  (`lot["caixa"]`, da `copy_allocation`), e não o que a ALOCAÇÃO lhe dá. Logo, um
  deck que ele diz que fica mas ainda **não montou** não protege uma única cópia
  — e cinco das caixas são novas de 02/10. Medido no `main`, **antes desta
  ordem**: das 673 cópias da lista VENDER, **174 / 5 317,11 €** são cópias que a
  alocação dá a um deck que FICA e que nenhuma regra protege — Cloud (DC) 71c/
  2 432,45 €, Cloud cEDH 17c/2 016,41 €, Blue Farm 7c/1 246,21 €, Modern —
  Affinity 30c/975,38 €, Engineer Welder Cam 17c/942,74 €, Modern 13c/748,01 €,
  Aluren 18c/681,20 €, Bant Airbend 30c/483,60 €, Oath 18c/389,42 €. As mais
  caras: 1 Ranger-Captain of Eos 673,14 €, 1 Urza's Saga 600,63 €, 1 Tropical
  Island 550,64 €, 4 Engineered Explosives 396,52 €, 3 Claws of Gix 325,77 €, 1
  Cavern of Souls 288,40 €, 24 Snow-Covered Plains 189,36 €. **No ramo são 181 /
  5 560,97 €** — as 7 cópias / 243,86 € a mais são as da Enchantress. Não se
  tocou: a ordem dizia para não mexer nas protecções, e a correcção (fazer a RD
  ler a caixa que a ALOCAÇÃO dá, e não só a registada) muda a lista de venda em
  cinco mil euros — é decisão dele.
- **TRÊS AVISOS QUE A CONFERÊNCIA DA ASSINATURA DEU LOGO**, e são para ele ver:
  (a) o **Modern — UW Oswald** tem a assinatura `Oswald Fiddlebender` e o mtgtop8
  chama àquelas 13 listas **«Pinnacle Affinity»** — a assinatura está a apanhar
  listas de Affinity e não de um deck de Oswald, logo a reserva daquela caixa sai
  do deck errado; (b) o **Oath of Druids** tem 51 listas e o nome mais votado é
  **«Oath Ponza» (9)** à frente de *«Oath of Druids» (7)*; (c) o **Engineer Welder
  Cam** tem 50 listas, 9 chamadas assim, 3 *«Painter»* e 2 *«Artifacts Blue»*.
- **E A RESPOSTA PARA O ARTIFACTS BLUE, que a ordem da manhã deixou pendente:** o
  mtgtop8 tem **«Artifacts Blue» com 6 listas de Legacy**. A caixa continua *à
  espera da carta-assinatura* porque isso é uma decisão dele, mas o nome existe na
  fonte — e abre a porta a identificar uma caixa pelo NOME em vez de por uma carta
  (`nomes` já sabe responder; falta a chave no config). Fica para a ordem seguinte.
- **POR FAZER, e vale a pena saber:** os nomes do mtgtop8 têm variantes de escrita
  (*«Replenish»* / *«Uw Replenish»*, *«Welder Cam»* / *«Weldercam»*) e **não se
  normalizam** — *acredita na fonte*; a votação resolve-o na prática (o mais
  votado ganha) e o segundo lugar vai no payload para o caso ficar à vista. E o
  top-10 pode mostrar **o mesmo nome duas vezes** (*«UR Aggro»*, *«Boros Control»*
  no Pioneer): é o agrupamento a ter partido um deck em dois clusters, e antes
  isso estava escondido atrás de dois nomes inventados diferentes.

**NUNCA PERDER UM TORNEIO DE PAPEL GRANDE (André, 2026-10-04, à letra).** *"o
mtgtop8 acaba por publicar esses torneios"* — e tinha razão: publica. O que não os
apanhava era a RECOLHA. Ele joga o RC Ghent de Modern a 9-11/10 e o dado que lhe
falta são os torneios de papel grandes. Motor em **`mtgvault/mtgtop8.py`**
(`parse_event_rows`/`parse_paginas_indice`, `regras_grandes`/`e_grande`/
`tecto_do_evento`, `candidatos_do_indice`, `semear_memoria`/`memoria_dos_eventos`/
`por_fazer`/`_registar_evento`, `grandes_de_hoje`), tabela
**`mtgtop8_eventos`**, passo **`papel-grande`** do `daily`, config em
`colecao_config.json → mtgtop8`. Testes em `tests/test_papel_grande.py` (19
casos) e a prova de que chumbam em `tests/_chumba_papel.py` (**17 de 17 pares**,
um processo por par). **A alocação, a venda e os preços não foram tocados**: este
módulo não lê a `copy_allocation` nem o `loadout`.

- **O DEFEITO: o índice nunca voltava atrás.** `harvest` fazia
  `parse_event_ids(_get("/format"))[:max_events]` com `max_events` 8 (6 nos
  formatos de papel) e mais nada. Em Modern entram várias ligas e challenges de
  MTGO por dia: um RC publicado hoje ficava **fora para sempre** se oito eventos
  mais novos aparecessem nas horas seguintes. Não havia segunda oportunidade.
- **O QUE O ÍNDICE JÁ DAVA E A RECOLHA DEITAVA FORA.** Cada linha da tabela «LAST
  20 EVENTS» traz o **nome** (`<a href=event?e=91582&f=MO>Win-A-Box</a>`), a
  **loja**, a **data** (`class=S12>03/10/26`), o ícone de **papel vs. MTGO**
  (`title="Paper"` / `"MTG Online"`) e a **classificação em estrelas** do próprio
  mtgtop8 (1 a 2 nas duas semanas medidas). O `parse_event_ids` extraía só os ids
  — é o mesmo padrão do comandante (01/10) e do nome do arquétipo (02/10): *a
  fonte dá a informação e a recolha perde-a*. **E o `parse_event_ids` é pior do
  que parecia:** numa página de Modern devolve **375 ids** de que só **20** são
  eventos do índice (os outros vêm do «METAGAME BREAKDOWN» e dos «RELATED
  LINKS»). Com `[:8]` isso nunca se notou, e era exactamente o que tornava
  perigoso ir mais fundo. O `parse_event_rows` exige as DUAS coisas que um evento
  do índice tem — link de evento **e** data — e dá 20. O `parse_event_ids` **fica
  como estava**, para quem o chama.
- **FILTRAR ANTES DE PEDIR, e é isto que paga a mudança.** A liga era saltada
  **depois** de se pedir a página do evento (`if sources.event_tier(...) ==
  "League"`), por isso cada liga gastava um dos lugares **e** um pedido. Com o
  nome vindo do índice custa **zero**. Medido nas 3 páginas reais de Modern de
  04/10: **58 eventos, 11 ligas** — e, dos 6 primeiros que a recolha via, **3
  eram ligas**. O tier lê-se do nome do índice e dá sempre o mesmo que o `<title>`
  da página (o prefixo «Modern event - » não contém nenhuma palavra-chave); tem
  caso de teste, e um «3City League (FRA) #1» de papel continua `Presencial`.
- **A PAGINAÇÃO DO ÍNDICE É REAL** (`?f=MO&cp=2`, `cp=3`): 58 eventos em Modern
  contra os 20 da primeira página, e o `meta=54` que o mtgtop8 põe no link **não
  é preciso** (verificado: `cp=2` com e sem ele devolve a mesma página). Lêem-se
  `paginas_indice` (3) e **nunca mais do que a página 1 declara** — e isso custou
  um defeito: com um `for pag in range(1, n+1)`, encurtar o `n` lá dentro não
  encurta o `range` já criado, e pediam-se páginas que não existem. É um `while`.
- **OS PADRÕES DO «TORNEIO GRANDE» SAEM DA BASE DELE, NÃO DA MINHA MEMÓRIA.**
  Medidos a 04/10 nos presenciais de mtgtop8 com 64+ jogadores: *Regional
  Championship* (1 486 j), *Magic Spotlight: The Hobbit* (921), *$uper $unday
  ReCQ* (344), *MTGO RC Qualifier* (221), *European Championship 2026* (218),
  *RC Super Qualifier* (212), *Czech Nationals 2026* (191), *Champions Cup
  Premium Qualifier* (168), *RC Hangzhou Side Event* (70). São **regex** e não
  texto simples por causa dos curtos — `rc` como substring casa em «Arc»,
  «Circuit» e «Marché», e há caso de teste com os três. Um padrão que não compile
  **não mata a recolha**: vale como texto literal e fica em
  `padroes_estragados`. **Um evento que case entra esteja onde estiver no
  índice** — e à FRENTE dos outros: um RC de há dez dias vale mais do que um
  torneio de loja de ontem.
- **O TECTO DE 64 NÃO É UM NÚMERO À SORTE: É O QUE A PÁGINA SERVE.** Medido nas
  páginas reais — o **RC de Modern (1 486 jogadores) tem 64 links de deck e a
  base dele tinha 16 listas**; o Magic Spotlight (921 j) o mesmo; o ReCQ (344 j)
  tem 31 e tinha 16. Eram **48 listas do maior torneio de papel de Modern** a
  ficar de fora por causa de `max_decks_per_event=16`. E 64 é o fim da escala que
  o `_bracket` já conhecia («33-64»).
- **MAS SÓ COM A PÁGINA A CONFIRMAR O TAMANHO** (`grandes.min_jogadores`, 64). O
  tecto alto pendurado só no NOME punha 64 pedidos `.dec` num «Store
  Championship» de 25 jogadores — e um presencial com menos de 64 jogadores **não
  conta para o metagame** (regra de 2026-09-07), por isso essas listas não
  alimentavam página nenhuma. O nº de jogadores vem da página do evento, que já
  foi pedida ANTES do primeiro `.dec`: a decisão não custa um pedido. Medido no
  índice real, dos 3 «grandes» pelo nome os três eram pequenos (Qualifiers do
  Japão e um Nacional português de 16 jogadores) e ficaram com o tecto de 16.
- **A MEMÓRIA É UMA TABELA E NÃO A `decklists`, e a razão é precisa.** Descer no
  índice sem memória custava um pedido por evento já feito, **todas as noites**
  (58 em vez de 8). O progresso não podia ser a `decklists`, como no
  `arquetipo_fonte_de` (02/10): o mtgtop8 re-hospeda o mtgo.com e um evento cujas
  listas são **todas deduplicadas** não deixa lá uma única linha — e é
  precisamente esse o que se voltaria a pedir sempre. Tem caso próprio.
  `mtgtop8_eventos` nos **três sítios** (`schema.sql`, `db._migrate()`, quem a
  escreve), com o índice `ix_mt8_grande` no `_migrate` pela armadilha de sempre.
- **O `tecto` GRAVADO É O QUE TORNA ISTO AUTO-CORRIGÍVEL.** Um evento visto com o
  tecto antigo (16) que hoje é reconhecido como grande (64) volta a ser visitado
  **uma vez** e fica completo — é assim que as 48 listas que faltam ao RC entram
  **sem um único passo à mão**. Quem semeia é o `semear_memoria` (uma vez, a
  partir das listas que já cá estão), com `tecto = TECTO_ANTIGO` e `completo = 0`:
  a verdade é que não se sabe quantos decks a página tinha.
- **AS REVISITAS SAEM DA MEMÓRIA E NÃO DO ÍNDICE, e isto foi o defeito mais
  consequente da ordem — apanhado por um ENSAIO de ponta a ponta, não por
  raciocínio.** A primeira versão escolhia as revisitas entre os candidatos do
  índice, e o ensaio sobre o índice real mostrou que o RC **não entrava**: ele é de
  **12/09** e as três páginas do índice cobrem **20/09 a 03/10**. O evento que mais
  interessa recuperar **já não está no índice**, e a secção estava escrita como se
  as 48 listas viessem. Hoje é o `revisitas_pendentes` a lê-las da tabela
  (`grande = 1 AND completo = 0`, pela ordem do nº de jogadores) e o RC entra na
  primeira noite. **Consequência:** o `grande` da semente tem de ser calculado (é
  ele que decide), e não 0 como a primeira versão escrevia.
- **TRÊS DEFEITOS MEUS APANHADOS PELOS TESTES, e é melhor estarem escritos:**
  1. **o `por_fazer` decidia com um tecto OPTIMISTA.** Usava 64 porque o nome era
     grande, e gravava 16 porque os jogadores eram poucos: `16 < 64` e o «Store
     Championship» de 25 era pedido **todas as noites, para sempre**. Decide-se
     com os jogadores **lembrados** (a coluna `players`, que o
     `backfill_event_players` também preenche), e a conta é a mesma dos dois
     lados;
  2. **o evento era marcado ANTES de se lerem os `.dec`** — uma regressão face ao
     código antigo, que não lembrava nada e por isso voltava a pedir os `.dec` que
     faltassem. Com a marca à cabeça, um `.dec` que falhasse deixava a lista a
     faltar **para sempre**. Um evento meio lido **não se marca**, como o evento
     cuja página falha;
  3. **a guarda da semente não podia ser «a tabela está vazia»**: um evento que
     não se marcou (por (2)) era deduzido das listas que deixou e marcado na
     corrida seguinte — a semente **tapava a repetição** que a não-marcação existe
     para garantir. A marca é explícita (`MARCA_SEMEADO`, uma linha
     `event_id = 0` num formato que não existe; o `memoria_dos_eventos` filtra por
     formato e nunca a vê).
- **AS REVISITAS TÊM TRAVÃO, por respeito e com o número medido.** Semeada a base
  dele (**401 eventos** de mtgtop8: duel-commander 105, legacy 76, premodern 71,
  standard 64, modern 61, pioneer 24), são **11** os que valem uma revisita — e
  fazê-los de uma vez eram **até 564 pedidos `.dec` numa noite**, o que num site
  pequeno e gratuito não se faz. `revisitas_por_corrida` = **1 por formato**,
  **pela ordem do nº de jogadores**: o RC entra na primeira noite (que é o que
  interessa para Ghent) e o backlog esgota-se em quatro. Os eventos **novos** não
  levam travão — esses são o trabalho de sempre. É a disciplina do
  `backfill_event_players(max_events=40)` e do `backfill_archetype_names(60)`.
- **O AVISO É UM POR DIA E LÊ-SE DA BASE** (`grandes_de_hoje` + o passo
  `papel-grande`, logo depois dos seis `harvest`). **Não se criou tarefa agendada
  nenhuma** — ele pediu a 15/09 menos vigilância — e o caminho já existia: o toast
  do `mtgvault/aviso.py` (2026-09-26) e a linha do resumo diário, mais uma linha
  por torneio no stdout do passo. Lê-se da tabela e nunca de uma variável a
  atravessar seis passos: um aviso por formato eram seis toasts na mesma noite. Só
  conta quem passa o `min_jogadores` — um «Store Championship» de 25 não é
  notícia. É injectável, que é como o teste prova que dispara uma vez.
- **O ORÇAMENTO DE PEDIDOS DESCE, e o número está medido** (as 3 páginas reais do
  índice de Modern de 04/10 contra a base a sério, `_scratch/medir_offline.py`):

  | | /format | /event | total |
  |---|---|---|---|
  | **antes** (1 página, `max_events=6`) | 1 | **6** | **7** |
  | **depois** (3 páginas, memória semeada) | 3 | **3** | **6** |

  **E os pedidos mudam de natureza, que é o que interessa:** dos 6 de antes, **3
  eram ligas** (desperdício puro) e os outros 3 eram eventos que a base já tinha
  por inteiro — **zero listas novas**. Os 3 de depois são **3 eventos que a
  recolha nunca tinha visto**, dois deles invisíveis ao código antigo (estão nas
  posições **34, 47 e 50** do índice). Em regime, com nada de novo, a corrida
  passa a **3 pedidos** (só as páginas do índice) contra os 7 de sempre.
  **Honestamente: só o Modern foi medido assim.** O que se sabe dos seis formatos
  do `daily` é a parte determinista — **+2 pedidos de índice por formato** (+12 na
  corrida), menos um pedido por cada liga que estivesse nos primeiros `max_events`
  (3 de 6 em Modern), menos um por cada evento já lembrado. Mais os `.dec` dos
  eventos novos, que são listas novas e não desperdício, e a revisita (1 por
  formato) enquanto o backlog dos 11 não esgotar.
- **UM TESTE DE 02/10 TEVE DE SER CORRIGIDO, e não mascarado.** O
  `test_nomes_arquetipo.caso_a_recolha_grava_o_nome_da_fonte` usava
  `"<a href=event?e=91451>x</a>"` como índice de mentira — uma forma que a página
  **nunca teve**. A asserção não mudou (2 listas, os nomes gravados); o que se
  corrigiu foi o fixture, que passou a ter a `<tr class=hover_tr>` com nome e data
  do índice real.
- **O ENSAIO DE PONTA A PONTA, e é o que mede a RECUPERAÇÃO**
  (`_scratch/ensaio_real.py` e `ensaio_drenar.py`: o índice REAL de Modern + uma
  cópia da base a sério, com as páginas dos eventos fabricadas com o nº de decks e
  de jogadores MEDIDOS a 04/10 nos que se chegou a pedir). A semente lembra os
  **401** eventos; a recolha de Modern abre **3 eventos novos** (os que estão nas
  posições 34, 47 e 50) e **24 listas novas** entram; o RC entra na mesma noite
  com as **64** e o aviso dispara só por ele. Drenando os seis formatos do `daily`
  noite a noite:

  | noite | pedidos | eventos abertos | listas novas | por recuperar |
  |---|---|---|---|---|
  | 1 | 160 | 8 | 144 | 6 |
  | 2 | 110 | 4 | 98 | 2 |
  | 3 | 40 | 1 | 31 | 1 |
  | 4 | 25 | 1 | 16 | 0 |

  **4 noites, ~335 pedidos, 289 listas novas de 11 torneios de papel grandes** — e
  **todos os `.dec` pedidos produziram uma lista**, nenhum foi desperdício. A
  partir da 5.ª noite a recolha de um formato sem nada de novo são **as páginas do
  índice e mais nada**. (Nota honesta: o `/format` do ensaio dá 8 e não 18 porque
  cinco dos formatos levaram um índice VAZIO de propósito — o que ali se queria
  medir era a recuperação, que vem da memória. Em produção são até 3 por formato.)
- **O QUE FICOU POR FAZER, e vale a pena saber:** (a) as **estrelas** do mtgtop8
  guardam-se (`parse_event_rows → estrelas`) e **nada decide por elas** — quem
  manda no peso continua a ser o `event_tier` + `event_players`; se um dia
  servirem, estão lá; (b) **não houve corrida ao vivo contra o mtgtop8** nesta
  ordem — ver o ponto a seguir; (c) o padrão `qualifier` é o mais largo dos doze
  e traz 3 eventos pequenos do índice de hoje: custam 1 pedido cada, **uma vez**
  (a memória fecha-os), e o tecto deles fica em 16.
- **A CORRIDA AO VIVO NÃO SE CONSEGUIU FAZER, e não se inventou um resultado.** O
  mtgtop8 **deixou de responder a meio da ordem** (`ConnectTimeout` e depois
  `ReadTimeout` de 51 s), enquanto `scryfall.com` e `github.com` ligavam em 0,0 s
  — logo não é a rede do PC. Antes disso o site respondeu a **~18 pedidos** a
  1/s, de onde saíram as medições todas desta secção (as 3 páginas do índice e as
  8 páginas de evento dos torneios grandes). Não se insistiu: o ritmo é 1
  pedido/s e o site é pequeno. **Tudo o que está aqui medido foi medido contra
  páginas reais**; o que falta é ver a recolha nova a correr de ponta a ponta, e é
  o primeiro passo da próxima vez que o site responder.

**A 14.ª TERRA, A SEGUNDA CAIXA DE AFFINITY E OS DEDICADOS (André, 2026-10-04,
à tarde).** Três decisões pequenas sobre o deck do RC Ghent. Só config — **o
motor não mudou uma linha**; medido com o mesmo `vault.db` dos dois lados
(`_revisao/medir_decisoes.py`, `diff_protegidas.py`, `provar_desactivar.py`).

- **A 14.ª terra é 1 ISLAND.** A lista de qualificação de 04/10 ficou gravada
  com **59** cartas no main e a 14.ª terra marcada `por_confirmar` — não se leu
  na imagem e não se inventou. Ele decidiu: entra **1 Island** (que era, aliás,
  a pista que a base dava: as duas únicas listas com exactamente as 13 terras
  dele jogam 1 Island como 14.ª). O main fecha em **60** e o side em **15**; as
  marcas `main_incompleto` e `por_confirmar` saíram. A manabase é 4 Fiery Islet,
  4 Spirebluff Canal, 4 Urza's Saga, 1 Steam Vents, 1 Island. **Não custa um
  cêntimo**: a Island vem da pilha de básicas, que são isentas das regras de
  material e entram por contagem declarada — a caixa `modern` passa de 69 para
  **70** cópias e continua a comprar as mesmas 5 (24,32 €), a 93 %.
- **A PROPOSTA DE SIDEBOARD FICOU REGISTADA E NÃO APLICADA**, que é a parte que
  interessa: `listas_escolhidas.modern.proposta_sideboard`, com
  `estado: "PROPOSTA NÃO APLICADA"`, a data e a razão (ele joga 4 Consign to
  Memory e o consenso de 90 listas joga 3; não tem um único Whipflare contra
  76 % das listas do consenso). **A lista que vale continua a ser a de
  qualificação, tal e qual** — o `cards` não se tocou, e o que está gravado é o
  par `tirar`/`meter` para ele aplicar quando quiser. Uma proposta minha não
  entra numa lista com que ele se qualificou.
- **A SEGUNDA CAIXA DE AFFINITY FICOU DESACTIVADA, E O ESTADO SOZINHO NÃO
  CHEGAVA.** A `modern-affinity` (criada a 02/10, antes de ele dar a lista)
  pedia **57 cópias / 1 985,44 €** — 4 Mox Opal a 300,12 € — para montar uma
  segunda cópia do mesmo deck que está na caixa `modern`. **Conferido primeiro
  que não estavam trocadas**: a lista de qualificação está mesmo na `modern`
  (`listas_escolhidas.modern`, `padrao: true`, origem «lista de qualificacao,
  dada pelo André a 04/10/2026»), e a `modern-affinity` era consenso por
  assinatura. **Medido: pôr-lhe `estado: "candidata"` não tira um único euro** —
  fechar tudo 10 281,35 € e as mesmas 57 cópias, porque desde 2026-09-19 cada
  caixa compra as suas e o `permanente`/`candidata` só manda na ORDEM da
  alocação dentro do grupo (`loadout.py:1658`). Quem tira é a **FONTE DA
  LISTA**: sem `assinatura`, uma caixa de `fonte: "consenso"` não tem lista
  nenhuma — é o que o `_caixas` já dizia e o que a `legacy-artifacts-blue` faz.
  Ficou com as duas coisas (`candidata` + sem assinatura) e **nada se apagou**:
  a `fonte`, o `ref`, a `assinatura` e o `estado` antigos estão em
  `caixas[].\_antes`, a chave que o motor não vê (`config_slots`) — o mesmo
  padrão do «já não vou montar este». Repor é devolver o `_antes`.
  - **Medido:** fechar tudo **10 281,35 € → 8 295,91 €** (**−1 985,44 €**), a
    comprar **294 → 237** (**−57**). **As outras 15 caixas ficam iguais ao
    cêntimo e à percentagem**; só a `modern` sobe uma cópia (a Island).
  - **Não libertou cópia nenhuma para a venda, e isso foi verificado linha a
    linha**: a caixa estava **VAZIA** (zero linhas na `copy_allocation`). A
    saída `venda` fica nas mesmas **113** cópias; o que muda é `protegidas`
    **158 → 162**, porque as 4 cópias que a caixa desactivada já não aloca
    (1 Urza's Saga e +3 Consign to Memory) passam a ser apanhadas pela **R5**
    (jogada nos últimos 30 dias). Nenhuma saída nova, nenhuma cópia perdida.
- **OS DEDICADOS JÁ ESTAVAM, e diz-se em vez de se fingir uma mudança.** A
  ordem era *"no `regras_por_formato`, os grupos `duel-commander` e `spml`
  ficam com `dedicado`: true, como já estão o premodern, o cedh e o pauper"*.
  **Os cinco grupos já tinham a chave desde 2026-09-19** (*"cada deck deverá ter
  as suas próprias cartas dentro"*) e o `loadout.resolve_slots` força
  `dedicado = True` em toda a caixa de qualquer modo. Medido: **«ir buscar a
  outra caixa» é ZERO nas 17 caixas**, antes e depois; e escrever
  `dedicado: false` nos dois grupos dá **exactamente os mesmos números** (8
  295,91 €, 237 a comprar, as 17 caixas iguais) — é o código a mandar, não o
  ficheiro. Logo **zero cópias passaram de «ir buscar» a COMPRA e zero euros de
  diferença**, em todas as caixas. O que se fez foi registar a confirmação dele,
  com a data e as palavras, no `_regras_por_formato`.
- **O diff do config são 14 inserções e 7 remoções**, escrito com o
  `configio.escrever` — a lição do commit `ac1f776`.

**A ABA DECKS: FORMATO → DECK → CARTAS, COM O `+` E O `−` (André, 2026-10-04, à
tarde, à letra).** *"Fazemos como no riftvault, fazes uma aba ou botao para
decks: Dentro dos decks, formato, Dentro do formato, o nome do deck, ordena por
tipo de carta"*; *"CDEH, sao 2 decks, ambos tem link, cada deck tem as suas
proprias cartas, fazes a imagem de cada carta, com + e - para eu marcar se tenho
a carta"*; *"Premodern, vou sleevar os decks tudo com sleeves iguais, nos decks
ficam apenas as cartas que sao proprias do deck e cartas usadas em varios decks
ficam de fora, vou imprimir proxie, e so meto as verdadeiras no deck quando for
jogar com esse deck"*; *"SPML a mesma coisa de Premodern"*; *"para Premodern e
SPML, quero que me perguntes para cada formato se eu quero montar ou nao o deck,
depois de escolher, ordenamos"*.
**[A PARTE ROTATIVA FOI SUBSTITUÍDA a 2026-10-05 para os DECKS PRINCIPAIS:
*"esses quero ter sempre montados, mesmo que com proxies"* — a carta partilhada
já não fica de fora à espera da hora de jogar, cada deck principal está montado
em permanência e os proxies passam a ser TODAS as faltas. O `cartas_partilhadas`
continua inteiro e vale para quem não for principal; ver «SEMPRE MONTADOS, MESMO
COM PROXIES».]**
**SUBSTITUI A CAMPANHA DAS FOTOS como resposta a *"tenho esta carta?"*** — ver a
secção a seguir: a precisão da foto servia para VENDER, e para MONTAR decks o
gesto certo é um toque no telemóvel à frente da estante. Motor em
`mtgvault/decks_vista.py` e `mtgvault/marcas.py`, página `decks.py` →
`decks.html`, passo `decks` do `daily`, endpoints `POST /api/marca` e
`POST /api/deck-montar`, config em `regras_por_formato[].cartas_partilhadas` e
`decks_montar`, tabelas `posse_marcada`/`posse_marcada_log`. Testes em
`tests/test_decks_vista.py` (30 casos) e a prova de que chumbam em
`tests/_chumba_decks_vista.py` (**14 de 14 alvos**, um processo por alvo).

- **A CONTRADIÇÃO QUE ISTO RESOLVE, e é o ponto todo.** A 02/10 ele fixou *"cada
  deck tem as suas próprias cartas, ponto"* — daí a SOMA (três decks que pedem 4
  Swords pedem 12). A 04/10 à tarde disse o CONTRÁRIO para Premodern e SPML: a
  carta usada em vários decks **fica de fora**, leva proxy, e a verdadeira entra
  só à hora de jogar. Nesses dois formatos uma cópia serve TODOS os decks e a
  necessidade é o **MÁXIMO**. As duas regras estão certas, cada uma no seu
  formato — por isso **não se escolheu uma delas no código**: a resposta é
  `regras_por_formato[].cartas_partilhadas` (`rotativas` = máximo, `dedicadas` =
  soma), e o código lê o config. Hoje: premodern e spml `rotativas`; cedh,
  duel-commander e pauper `dedicadas`. Sem a chave vale **`dedicadas`**, que é o
  lado conservador (pedir a mais faz uma lista grande; pedir a menos faz-lhe
  faltar a carta à hora de jogar).
- **É UM EIXO NOVO E NÃO O `dedicado` QUE JÁ LÁ ESTAVA**, e isso foi verificado
  em vez de assumido: o `dedicado` dos cinco grupos responde a *"esta CAIXA
  empresta cópias a outra caixa?"* e desde 2026-09-19 vale `True` à força no
  `loadout.resolve_slots` (um `dedicado: false` escrito no config não tem
  efeito). O `cartas_partilhadas` responde a *"os DECKS dentro deste formato
  repartem cópias entre si?"*. **Onde é que a decisão soma-vs-máximo vivia
  antes:** no `loadout.partilhar_compras`, e não no `dedicado` — essa função é
  hoje um **no-op** (devolve sempre `[]` desde 19/09, e o
  `loadout.playset_maximo` devolve sempre `None` desde 02/10). Ou seja o motor
  da alocação já só sabia somar, e não havia nenhum sítio a ler o `dedicado`
  para esta pergunta: a chave nova não tirou trabalho a ninguém. **O
  `loadout` não se tocou** — a aba Decks não lê a alocação.
- **OS DOIS NÚMEROS MOSTRAM-SE SEMPRE OS DOIS**, com etiqueta — *«a somar»* /
  *«a rodar»*, e o que a regra usa fica em dourado. É a diferença entre eles que
  lhe diz quanto custa a decisão, e esconder o outro era responder-lhe sem lhe
  dar a conta. Tem caso de teste (`caso_os_dois_numeros_mostram_se_sempre_os_dois`).
- **PRÓPRIAS E PARTILHADAS NÃO SÃO UMA ETIQUETA DA CARTA: dependem de QUAIS
  decks ele marcou.** Num formato rotativo, as cartas de cada deck partem-se em
  duas listas contadas à parte — **própria** (entra só neste deck, fica sleevada
  para sempre) e **partilhada** (entra em 2+, fica de fora, o deck leva proxy).
  Marcar mais um deck pode passar uma carta de própria a partilhada, e desmarcar
  faz o caminho de volta; tem teste nas duas direcções. Daí saem de graça duas
  listas que ele vai ter em cima da mesa e não pediu: os **proxies a imprimir**
  de cada deck (= exactamente as partilhadas desse deck, com teste a exigir a
  igualdade) e quantas cartas ficam **sleevadas** no formato (verdadeiras +
  proxies).
- **A POSSE: O INVENTÁRIO PRÉ-PREENCHE AS MARCAS, E NÃO SE ESCREVEM 737 LINHAS
  PARA ISSO.** A tabela `posse_marcada` nasce VAZIA e guarda só o que ele TOCOU;
  quem não tem linha responde com a contagem da `copies` (`paginas.posse_total`,
  a conta única de sempre). Daí os **dois estados**, visíveis e distintos no
  ecrã: *«do inventário»* e *«marcaste tu»* (com a data), e **a marca dele ganha
  sempre**. A marca é ABSOLUTA e não um delta sobre o inventário, de propósito:
  uma cópia que entre por foto ou por CSV não pode mexer num número que ele já
  confirmou com a carta na mão. E **nada se apaga** — a `copies` não se toca, e o
  `esquecer` devolve a carta ao inventário.
- **AS ESCRITAS SÃO DELTAS COM `request_id`**, copiado do riftvault
  (`riftvault/collection.py`, `adjust`): o cliente nunca manda um valor
  absoluto, o servidor soma dentro de uma transacção e trava no zero e em
  `MAX_POR_CARTA` (99). É isso que dá as duas coisas ao mesmo tempo — cliques
  rápidos seguidos não se perdem (não há debounce onde dois colapsem num) e um
  retry de rede não conta a dobrar. Tem caso próprio.
- **AS MARCAS SOBREVIVEM AO DAILY** porque vivem na BASE e não numa página: o
  `daily` reescreve o HTML e os `data/paginas/**` e nunca toca nesta tabela. O
  `POST /api/marca` **não passa pelo `regenerar`** (um toque num `+` é um gesto
  por carta, e recalcular o `loadout.report` inteiro punha dois segundos entre o
  dedo e o número): limpa a cache, e o `_versao()` já apanha o `vault.db`. O
  «quero montar este» **regenera**, porque muda a necessidade do formato e quem
  leva proxy.
- **O QUE SE REAPROVEITOU DO RIFTVAULT** (`Desktop\Riftbound\riftvault` — e o
  caminho da ordem, `C:\Users\Catarina\riftvault`, **não existe**): o **tile** de
  `web/app.js: tileHTML` (`.art` com `aspect-ratio`, a `<img>` com
  `loading=lazy`/`decoding=async`, os crachás por cima e os dois botões por
  baixo com 40 px de altura mínima, `web/style.css: .step`); a **cor a dizer se
  ele tem** (`filter: grayscale(1) brightness(.42)` — a mesma foto, sem uma
  segunda imagem e sem um segundo pedido ao CDN); o **optimismo com contador em
  voo** (`app.js: adjust` + `state.pending`: o ecrã anda já e só a última
  resposta manda, senão uma resposta atrasada punha o contador para trás); **um
  só `addEventListener` delegado**; e o `body.readonly` a esconder os controlos
  no site publicado. **O que NÃO se copiou, e é decisão:** no riftvault o tile de
  DECK **não tem** `+`/`−` (revogados a 2026-10-01, *"no deck nao precisa + e -
  / ele ja indica se tem ou nao tem"*). Aqui tem, porque é o que ele pediu em
  palavras para o mtgvault e porque aqui o `+`/`−` é a ÚNICA porta da posse.
- **TRÊS NÍVEIS, CADA UM COM URL PRÓPRIA**, para ele guardar qualquer um nos
  favoritos do telemóvel: `decks.html` (os formatos) · `decks.html#f=premodern`
  (os decks desse formato) · `decks.html#f=premodern&d=caixa:premodern-oath` (as
  cartas). `replaceState` e não um salto, pela razão da Deckboxes de 24/09.
- **TRÊS CORRECÇÕES MINHAS, aplicadas e ditas:** (1) o **COMANDANTE** vem num
  grupo próprio **acima dos Creature** nos formatos de comandante — é a carta que
  identifica o deck, e enterrada no meio dos Creature não se encontra; qual é ela
  sai do config/`listas_escolhidas` ou, num arquétipo de Duel Commander, do
  próprio nome da fonte, e **nunca se adivinha pelas cartas** (medido a 01/10: o
  crivo pela identidade de cor deixava 0 ou mais do que um candidato em 409 das
  652 listas). (2) **O TIPO SAI DO `type_line` PELO MAIS ESPECÍFICO** — e por
  isso há **DUAS listas**: a `ORDEM_TIPOS` de apresentação é a dele à letra
  (Commander, Creature, Sorcery, Instant, Artifact, Enchantment, Planeswalker,
  Land, Outras) e a `PRECEDENCIA` de classificação é outra (Creature,
  Planeswalker, **Land**, Artifact, Enchantment, Instant, Sorcery). A diferença
  morde: pela ordem de apresentação o `Artifact` vem antes do `Land` e uma
  Ancient Den caía em Artifact, que é o que ele mandou corrigir. **O
  `paginas.tipo_de` NÃO se tocou** (continua a responder `Artifact` à Ancient
  Den), senão mudava o agrupamento da Deckboxes e do Showcase sem ninguém pedir —
  e há caso de teste a trancar a divergência nos dois sentidos, com cartas DA
  BASE (Memnite → Creature, Ancient Den → Land, Urza's Saga → Land). Dryad Arbor
  (Land Creature) cai em **Creature**, e fica dito. (3) O **SIDEBOARD** é um
  bloco separado depois do main, com os mesmos grupos por dentro, e conta à parte
  no *«tens X de Y»* — as duas metades somam sempre o total.
- **A PERGUNTA «QUERO MONTAR ESTE?» FAZ-SE PELO SÍTIO, não por um diálogo.** Em
  Premodern são mais de vinte decks e vinte caixas de diálogo não são uma
  pergunta, são um interrogatório: a lista do formato leva **uma caixa por
  deck**, ordenada pela percentagem que ele já tem (maior primeiro — é o *"depois
  de escolher, ordenamos"* dele e a resposta a *"qual é o mais barato de
  fechar"*), para a resposta ser um toque por deck. É interpretação minha e está
  dita.
- **O REGISTO: O META É PELO NOME DA FONTE, E SÓ SE OFERECE ONDE ELE O PEDIU.**
  Os arquétipos saem de `decklists.arquetipo_fonte` (o nome que a página do
  evento do mtgtop8 escreve, gravado desde 02/10) e **nunca da etiqueta do
  clustering** — é o único id estável, e uma marca dele tem de sobreviver às
  corridas. **Quem agrupa pela coluna é o `mtgvault.nomes`** e não este módulo:
  `nomes.listas_por_nome` é a pergunta inversa do `nome_das_listas`, e vive no
  mesmo sítio porque é a mesma coluna — o
  `test_nomes_arquetipo.caso_a_pergunta_do_nome_vive_num_sitio_so` varre o código
  à procura de um segundo leitor e **apanhou-me** a lê-la à mão no
  `decks_vista`. O meta **só se oferece nos formatos `rotativas`**: a pergunta
  *"queres montar este?"* foi pedida para o Premodern e o SPML, e nos outros três
  ele ENUMEROU os decks (*"CDEH, sao 2 decks"*, *"Duel Commander, 1 deck"*) —
  oferecer-lhe doze comandantes de Duel Commander era contradizê-lo. Os meta dos
  formatos dedicados **contam-se e dizem-se** (`meta_fora`), para a decisão ficar
  à vista.
- **DOIS FILTROS, PORQUE SÃO DUAS PERGUNTAS, e isto mediu-se antes de se
  escolher.** O REGISTO (*"que decks existem no meta"*) vê **todas** as listas
  que contam; a LISTA de cada um (*"como é que se joga agora"*) vê a **janela do
  consenso** de 03/10. Juntá-las esvaziava a página: com a janela aplicada ao
  registo o SPML ficava com **modern 2, standard 0, pioneer 0, legacy 0**
  arquétipos. É a mesma separação que a reserva da venda já tinha. Um arquétipo
  cuja janela não chega ao mínimo fica com a lista de todas as suas e **di-lo**,
  nas palavras de sempre (`sources.texto_amostra`).
- **ARQUÉTIPOS META, MEDIDOS na base de 2026-10-04** (nome da fonte, ≥5 listas
  que contam): **modern 19** (Broodscale Bloodchief 73, Devoted Combo 30, Esper
  Blink 29, Pinnacle Affinity 25, Ruby Storm 25), **standard 18** (Izzet
  Spellementals 45, Dimir Aggro 31, Jund Sacrifice 20), **legacy 10** (Boros
  Aggro 14, Doomsday 12, Dimir Tempo 10), **premodern 10** (Enchantress 20,
  Terrageddon 15, Psychatog 12, Landstill 11, Sligh (RDW) 10), **pioneer 9** (The
  Rock 26, UR Aggro 22, Boros Control 12), **duel-commander 20** (contados, não
  oferecidos), **vintage 0, pauper 0, cedh 0** — os dois últimos por construção
  (o Pauper só segue o Luffy, `tiers: []`, e o cEDH não tem uma única decklist na
  base: as listas dos dois decks vêm do `watched_snapshots`, do Moxfield).
  Com as 17 caixas dele, **83 decks** no total.
- **OS DOIS LINKS DE cEDH saem da tabela `watched`**, que é de onde a vigia já
  traz a lista — não se escreveu nenhum à mão: `cedh-blue-farm` → Blue Farm
  (watched 1, `https://moxfield.com/decks/7O1sCuIti0igU6Us_Jhadg`) e `cedh-cloud`
  → Cloud cEDH (watched 4,
  `https://moxfield.com/decks/k6f2yED7oUGPtK2_rN_xwg`). O link mostra-se na
  página do deck.
- **O PESO, medido**: casca **50 293 bytes** (tecto **80 KB**, justificado no
  `decks.TECTO_CASCA`), índice 50 588 bytes, **83 partes / 440 KB** (a maior
  15 299 bytes, ida buscar ao toque). **Zero imagens embutidas**: as artes são
  remotas (`cards.scryfall.io`, pelo `paginas.art`), com `loading="lazy"`,
  `decoding="async"`, `width`/`height` escritos e `aspect-ratio` na moldura — e
  há caso de teste para cada uma dessas quatro coisas.
- **15,2 s → 1,8 s a frio, e as duas causas eram minhas.** (a) o `meta_fora` dos
  formatos dedicados construía a lista de consenso dos 56 arquétipos **só para
  os contar** (`arquetipos_meta(so_contar=True)`); (b) cada um dos 83 decks pagava
  um `paginas.img_map`, e esse começa por varrer a `copies` INTEIRA para preferir
  a impressão que ele tem — 83 varreduras por página (`decks_vista.cache_nova`,
  partilhada pela passagem). A aba entrou também no **aquecedor**
  (`webapp._AQUECER`), pela razão das outras duas.
- **O DECK DE DUEL COMMANDER PASSOU A SER O DO LIWEI LUO** (ordem dele: a melhor
  classificada em challenges ou presenciais). As **100 cartas saíram da base**
  (`decklist_cards` do `decklist_id` **22794**) e nunca de memória, e a premissa
  confirma-se ao exemplar: o Liwei Luo ganhou **TRÊS** presenciais com a MESMA
  lista — 08/09 (16 jogadores), 22/09 (21) e 29/09 (18), Watermelon Champion Cup
  Nights — e o `content_hash` é **o mesmo nos três** (`d3ec9a051f72e1e4`), ou
  seja não mudou uma vírgula. Fixou-se pelo mecanismo que já existia (a LISTA
  PADRÃO de 20/09, `padrao.fixar` → `listas_escolhidas["duel-commander"]`), com a
  origem, o link e a nota dos três primeiros lugares.
  - **A lista de 20/09 NÃO se perdeu**: o `padrao.fixar` só guarda o `_antes` na
    primeira vez, e por isso ela foi para `_lista_anterior` à mão — nada se apaga
    (regra de 09/09), e o motor não lê chaves com `_`.
  - **MEDIDO lado a lado, o mesmo `vault.db` dos dois lados**: fechar tudo
    **5 802,47 € → 5 895,14 €** (+92,67 €), a comprar **237 → 244** (+7), e **só
    a caixa do Cloud mexe** — 82 % → **75 %**, a comprar 18 → 25, 188,61 € →
    281,28 €, 81 → 75 cópias, 99 → 100 pedidas. **As outras 16 caixas ficam
    iguais ao cêntimo e à percentagem**, e a **venda não mexe uma cópia**
    (113 c / 1 588,89 €).
  - **`protegidas` 162 → 160 cópias (−728,71 €), e NADA foi para a venda**: as
    duas que saíram são **1 Flooded Strand e 1 Windswept Heath**, que a lista
    nova ALOCA ao Cloud (ela joga fetchlands e a de 20/09 não) — passaram de
    «candidata protegida pela R3» a «dentro de um deck». As outras cópias dessas
    duas cartas continuam protegidas pela R3.
  - **E a lista nova corrige um defeito conhecido**: a padrão de 20/09 **não
    incluía o próprio comandante** (a Cloud aparecia como carta de reserva, a
    89 % — está escrito na secção «LISTA PADRÃO E RESERVA POR CAIXA»); a do Liwei
    Luo inclui-o, e por isso a caixa passa a pedir 100 cartas e não 99.
  - **A FICHA, medida com a cadeia e o modo em vigor** (`cardtrader`, `market`):
    ele tem **81 das 100** cópias (**81 %**) e faltam **19 nomes / 19 cópias** —
    **171,43 €** em nonfoil ou **206,77 €** com foil onde existe foil. **A ordem
    dizia «80 das 100, faltam 20 nomes, ~104 € / ~181 €» e os números medidos são
    estes**: a diferença no euro é a cadeia só-CardTrader de 04/10 (cinco das 19
    não têm preço nenhum, ver o furo abaixo) e no nome é uma unidade.

**O SIDEBOARD APLICADO, A RESERVA A 20 % E A VIGIA DO ARQUÉTIPO (André,
2026-10-04, ao fim do dia).** Três decisões pequenas. Motor: `loadout`
(`compras_urgentes`/`urgencia_da_compra`/`EXCEPCAO_PENDENTE`), `mtgtop8`
(`parse_archetype_rows`/`archetype_listas`), `watchlist`
(`check_mtgtop8_archetype`/`VERIFICADORES`), config `compras_urgentes` +
`reserva.staples_premodern_pct`. Testes em
`tests/test_decisoes_1004_noite.py` (10 casos) e a prova de que chumbam em
`tests/_chumba_decisoes_noite.py` (**17 de 17 pares**, um processo por par).
Backup em `data/backups/vault-2026-10-04-tres-decisoes.db` (98,7 MB,
`integrity_check ok`).

- **1) O SIDEBOARD DO MODERN FOI APLICADO:** −1 Consign to Memory (fica em **3**)
  e +1 **Whipflare** (entra; não tinha nenhum). O side continua em **15** e o
  main em 60. O `proposta_sideboard` passou de `PROPOSTA NÃO APLICADA` a
  **`APLICADA`** e **o registo da proposta fica inteiro** — `tirar`/`meter`/
  `razao`/`em`/`quem`, mais `estado_anterior` e `como_voltar_atras`: ele pode
  querer voltar atrás antes de 9/10, e o caminho de volta está escrito em vez de
  ter de ser reconstruído. O **`test_caixas.caso_a_lista_de_qualificacao_fecha_em_60`**
  (escrito às 14h do mesmo dia, a afirmar que a proposta NÃO estava aplicada)
  teve a asserção **corrigida e não mascarada**, com as duas datas no docstring.
- **A FALTA PASSOU A PODER DIZER *QUANDO*, e não havia campo nenhum.** As 237
  compras valiam todas o mesmo e a que tem de estar na mão em cinco dias ficava a
  meio de uma lista por nome. A chave nova é **`compras_urgentes`** (uma entrada
  por carta × caixa: `prioridade`, `ate`, `porque`), lida **num sítio só**
  (`loadout.compras_urgentes`, UMA vez por relatório — o config lê-se milhares de
  vezes por corrida, é o defeito do `Path.resolve()` de 03/10), e a linha de falta
  ganha `urgencia`. O **`dias` é CALCULADO** de hoje para o `ate` e nunca escrito:
  uma data-limite gravada como «faltam 5 dias» mente no dia seguinte. **Uma
  data-limite que PASSOU continua a dizer-se** (`passou: True`) em vez de
  desaparecer calada no dia em que mais importava. Hoje: Whipflare, caixa
  `modern`, prioridade **alta**, até **2026-10-09** (o primeiro dia do RC Ghent).
- **A EXCEPÇÃO AO FOIL FICOU PENDENTE, E NÃO SE DECIDIU POR ELE.** A caixa
  `modern` está no grupo `spml` (`acabamento: foil`) e o **Whipflare só existe em
  foil em New Phyrexia**: **20,20 €** contra **0,21 €** do nonfoil mais barato
  (C14) — 96× por uma carta de sideboard em cópia única. Fica
  `material_pendente.estado: "PENDENTE DE DECISÃO DO ANDRÉ"`
  **[DECIDIDO ao fim do mesmo dia: hoje é `DECIDIDA` + `aplicado: true` +
  `provisoria: "trocar por foil"`, e o `se_comprar_o_nonfoil` passou a
  `_aplicada_quer_dizer` — ver a secção do fecho]**, com os dois preços
  à vista, e **entretanto a lista de compras sugere o nonfoil**
  (`loadout.EXCEPCAO_PENDENTE`, irmão do `SEM_FOIL` de 19/09: vale como *«nonfoil,
  e diz-se porquê»* — a linha mostra *«EN · nonfoil — decisão do material
  PENDENTE»*).
  - **A excepção pendente vale para a SUGESTÃO DE COMPRA e NÃO para a alocação**,
    e a diferença é deliberada: mexer no `_porque_nao` era decidir a excepção —
    um Whipflare nonfoil passava a fechar o slot sem ele ter dito nada. Enquanto
    estiver pendente a caixa continua a exigir foil, **e a ficha di-lo**
    (`se_comprar_o_nonfoil`): se ele comprar o nonfoil, a cópia entra como
    substituto e o slot só fecha quando ele puser `aplicado: true` — que é uma
    linha no config e aí vale **também** na alocação (`resolve_slots` anota as
    APLICADAS em `s["excepcoes_material"]`; as pendentes não entram lá). Dizê-lo
    agora é melhor do que ele descobrir quando a carta chegar.
  - **A RESSALVA QUE IMPORTA, e é medida:** os 20,20 €/0,21 € são do **price guide
    do Cardmarket**, que saiu da cadeia a 04/10 de manhã. Na régua em vigor
    (`cardtrader` sozinho) o **Whipflare não tem preço nenhum** — `card_price`
    devolve `None` nos dois acabamentos —, por isso entra na lista de compras a
    **0,00 €** e conta em `sem_preco` (**16 → 17** cópias). O «fechar tudo» não
    sobe um cêntimo por causa dela, e é por isso que esse número é hoje um
    **mínimo**.
- **O CURSED TOTEM FOI CONFERIDO E NÃO ENTROU NA LISTA** (era um ajuste
  condicional, não decidido): **não está no sideboard** — tem caso de teste a
  exigi-lo — e ele não tem nenhuma cópia (0 na base, verificado). Dois números da
  ordem precisam de correcção, e são a favor dele: em Modern a caixa pede **foil**,
  logo o Cursed Totem custaria o foil de MH2 (**6,83 €** no Cardmarket, **9,09 €**
  no CardTrader) e não os 1,16 € do nonfoil; e a 20 % **deixa de ser staple de
  sideboard de Premodern** (era uma das 25 a 10 %), o que não muda nada hoje
  porque ele não tem cópias para proteger.
- **2) A RESERVA PASSOU A 20 %, e os números são estes** (medidos na base dele com
  dois configs temporários, só a chave trocada, `_scratch/medir_staples.py`):

  | | corte 10 % | corte 20 % |
  |---|---|---|
  | cartas staple | 25 | **7** |
  | candidatas a venda | 606 c / 17 917,10 € | **609 c / 17 919,83 €** |

  **ENTRAM +3 cópias / +2,73 €** — as **3 Essence Flare (PT)** — e **saem zero**.
  **18 cartas deixam de ser staple** e só uma muda de lado: as outras 17 já
  estavam protegidas pela **R5** (jogadas nos últimos 30 dias), que é a razão
  escrita na `curva_staples` desde 02/10 (*«uma staple de sideboard é, por
  definição, uma carta que apareceu numa lista do mês»*). Na venda vê-se o espelho
  disto: `venda` **113 → 116 c** (1 588,89 € → 1 591,62 €) e `protegidas`
  **162 → 159 c**. A **alocação não mexe** e a venda continua **escondida**
  (`venda.mostrar: false`) e **congelada** (trava manual) — medir não é destrancar.
  - **A RAZÃO ESTÁ ESCRITA NO CONFIG** (`reserva._staples_premodern_pct`), com os
    números, porque daqui a um mês ninguém se lembra porque é que 10 virou 20:
    com `cartas_partilhadas: rotativas` as cartas que entram em vários decks
    marcados ficam guardadas por definição, o limiar passa a cobrir só as staples
    que não estão em deck nenhum, e por isso pode ser mais largo. **A regra que
    sustenta isto entrou no MESMO DIA, depois disto.** Quando a razão foi
    escrita a chave `cartas_partilhadas` não existia no config e ficou dito;
    horas depois a ordem das abas de decks fundiu no `main` e pôs-lhe
    `cartas_partilhadas: "rotativas"` no **premodern** e no **spml** (e
    `dedicadas` no cEDH, Duel Commander e Pauper) — exactamente o pressuposto da
    subida. **A nota foi corrigida nos dois sítios** (config e aqui) em vez de
    ficar a dizer que a regra não existe: uma nota que mente é pior do que nota
    nenhuma, e esta ia passar a mentir no dia seguinte.
- **3) A VIGIA DO ARQUÉTIPO DO CLOUD CORRE A SÉRIO** (`archetype?a=2629`), e não
  ficou pendente. `watched` `kind = 'mtgtop8_archetype'`, `key = 2629`,
  `format = duel-commander` — **id 6, inscrita e verificada contra o site**: 16
  listas, melhor = **Liwei Luo, 1.º @ Watermelon Champion Cup Nights (29/09, deck
  894185)**, que é exactamente o contexto que a ordem deu. A 2.ª corrida dá
  `changed: False` — não há sinal falso.
  - **O `kind` NOVO OBRIGOU À PRIMEIRA RECONSTRUÇÃO DE TABELA do `db._migrate`**,
    e não havia outra saída: o que muda é um **CHECK** e o SQLite não tem
    `ALTER TABLE … ALTER CONSTRAINT` — sem isto o `watchlist.add` dava
    `IntegrityError` e a vigia não se inscrevia. **Duas armadilhas, e as duas
    mordem:** as FK estão **LIGADAS** (`connect` faz `PRAGMA foreign_keys = ON`) e
    a `watched_snapshots` referencia a `watched` com **ON DELETE CASCADE** — um
    `DROP TABLE` apagava o histórico todo das listas vigiadas (15 snapshots na
    base dele); e **o PRAGMA é um no-op dentro de uma transacção**, por isso o
    `commit` antes. A contagem é conferida antes e depois e **levanta** se perder
    uma linha. Medido na base dele: **5 vigias e 15 snapshots preservados**,
    `foreign_key_check` limpo, e correr outra vez é um no-op. Dois casos de teste
    e dois alvos no `_chumba`.
  - **O PARSER REAPROVEITA O QUE JÁ HAVIA**, como a ordem mandou: a página do
    arquétipo usa a MESMA `<tr class=hover_tr>` do índice de eventos, e as peças
    são o `RE_LINHA_INDICE`, o `RE_DECK` (cujo comentário já dizia *«continua a
    valer para as páginas de arquétipo»*), o `RE_PLAYER`, o `RE_LINHA_EVENTO` e o
    `RE_DATE`. O que o `parse_archetype_rows` acrescenta é a **COLOCAÇÃO** — que
    nenhum parser lia e é precisamente o que decide qual é «a melhor lista». Uma
    linha **sem deck e sem data** não é uma lista (é o «METAGAME BREAKDOWN»), o
    mesmo crivo do `parse_event_rows`. Validado contra a página REAL de 04/10, que
    ficou como fixture no teste.
  - **UM PEDIDO POR CORRIDA, e o snapshot é o ÍNDICE da página** — uma linha por
    lista, não as cartas de cada deck: as cartas custariam um `.dec` por lista (16
    pedidos na primeira corrida) e **nenhum deles responde à pergunta «mudou?»**.
    Quem guarda cartas na base é a recolha (`harvest`), não a vigia. O
    `list_hash`/`diff` de sempre continuam a funcionar porque a linha entra na
    forma `(board, nome, qty)` que eles já usam, com a **posição** como `qty` — e
    é isso que faz uma lista que SOBE de 3-4 para 1 contar como mudança.
  - **A «MELHOR» CALCULA-SE** (`_melhor`): menor posição, e entre iguais a mais
    recente. A página é cronológica e não ordenada por resultado; sem isto «a
    melhor» era «a última».
  - **E O `check_all` PASSOU A FALHAR ALTO EM QUEM NÃO SABE TRATAR.** Isto não
    estava na ordem e apareceu a ler o código: o CHECK da `watched` aceita
    **`archetype`** desde o primeiro dia e **nunca teve implementação** — era
    saltado **sem uma linha de saída e sem erro**, o padrão do `event_tier`
    aplicado a uma vigia. Era exactamente o risco que ele nomeou (*«uma vigia que
    não vigia é pior do que nenhuma, porque ele fica a pensar que está
    coberta»*), já materializado. Os verificadores passaram a um **mapa**
    (`VERIFICADORES`) e um kind sem verificador sai com `nao_implementado` e a
    frase *«esta vigia está INSCRITA e NÃO corre»*. **Nada se apagou**: o
    `archetype` fica no CHECK.
  - **O `_watch` do daily ganhou saída própria para este kind**: lista NOVA com
    `[NOVA]` e a troca da melhor com `[MELHOR MUDOU]` + a anterior. O `diff`
    genérico imprimia as listas como se fossem cartas (`deck +1 894562 ambroiseb1
    @ MTGO League (0->5)`), que não diz nada a ninguém.
  - **O DECK NÃO SE REGISTOU**, de propósito: isso é da ordem
    `mtg-decks-estrutura`, que a 04/10 ainda **não tinha corrido** (confirmado na
    inbox do runner). Aqui só a vigia.
- **UM DEFEITO MEU, MEDIDO E CORRIGIDO ANTES DE IR AO `main`** — e é a razão
  para medir caixa a caixa em vez de olhar só para o total. Ao fazer o preço da
  linha seguir o acabamento da REGRA escrevi
  `in ("foil", "prefere_foil")`; numa caixa **`prefere_foil`** (Duel Commander,
  Pauper) a compra pode ser **nonfoil**, que é a mais barata que serve, e o
  «fechar tudo» do Cloud subia de **188,61 € para 228,99 €** (**+40,38 €**) **sem
  uma única carta mudar de lado**. O total batia com o delta e parecia uma
  consequência das decisões; era um `in`. Hoje o teste é `== "foil"` e há caso
  próprio (`caso_uma_caixa_prefere_foil_orcamenta_o_nonfoil`) e alvo no `_chumba`.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados** (worktree em
  `_revisao/main-0410b`; `_scratch/medir_efeito.py` nas duas árvores):

  | | main | ramo |
  |---|---|---|
  | fechar tudo | 5 802,47 € | **5 802,47 €** |
  | a comprar | 237 | **238** |
  | sem preço | 16 | **17** |
  | caixa `modern` | 93 % · 70/75 · comprar 5 · 28,44 € | **92 % · 69/75 · comprar 6 · 28,44 €** |
  | venda | 113 c / 1 588,89 € | **116 c / 1 591,62 €** |
  | protegidas | 162 c / 6 940,22 € | **159 c / 6 937,49 €** |
  | candidatas | 606 c / 17 917,10 € | **609 c / 17 919,83 €** |
  | `rl_sem_historico` / `guardar` | 103 c / 1 c | **iguais** |

  **O «fechar tudo» fica IGUAL ao cêntimo** e **as 16 caixas que ele não mandou
  tocar ficam iguais à percentagem e ao cêntimo**. Só a `modern` muda, e
  explica-se à carta: −1 Consign to Memory (uma cópia que ele TEM deixa de ser
  pedida: `tenho` 70 → 69) e +1 Whipflare a comprar, **a zero euros porque o
  CardTrader não o cota**. As 3 cópias que passam de `protegidas` a `venda` são as
  3 Essence Flare do limiar novo, ao cêntimo e sem uma cópia perdida pelo caminho.
- **POR DECIDIR POR ELE:** (a) **a excepção ao foil do Whipflare** — 20,20 € foil
  contra 0,21 € nonfoil, hoje PENDENTE e com o nonfoil sugerido; aplicar é
  `material_pendente.aplicado: true`; (b) o Whipflare **sem preço na régua em
  vigor**, o que faz a compra entrar a 0,00 € (se quiser o preço do Cardmarket de
  volta, é `precos fonte cardtrader --recurso cardmarket`); (c) o **Cursed Totem**
  continua fora da lista, como ajuste não decidido; (d) a razão do 20 % **pressupõe
  a regra `cartas_partilhadas`**, que ainda não existe no config.
  **[A (d) FECHOU-SE no mesmo dia, mais tarde]**: o `cartas_partilhadas` entrou
  no `regras_por_formato` com a aba Decks (`rotativas` no premodern e no spml,
  `dedicadas` nos outros três) — ver «A ABA DECKS». A chave é lida pelo
  `decks_vista.partilha_do_formato` e **não mexe no motor da venda nem no limiar
  da reserva**: o 20 % fica como está, e a sua razão passa de pressuposto a
  facto escrito no config.
  **[A (a) FECHOU-SE no mesmo dia, ao fim do dia]**: ele decidiu o **nonfoil
  agora, foil depois** — ver a secção a seguir.

**A TRAVA DA VENDA DEIXA DE TER DATA, A RL DE DUEL COMMANDER FICA VENDÁVEL, E O
WHIPFLARE É NONFOIL PROVISÓRIO (André, 2026-10-04, ao fim do dia).** Três
decisões pequenas que FECHAM as três que a ordem anterior deixou abertas. Motor
em `mtgvault/fases.py` (`congelada`/`gravar_congelada`/`COMO_DESTRANCAR`/
`data_sem_efeito`) e `mtgvault/watchlist.py` (`check_preco_impressao`/
`vigiar_preco`/`chave_preco`), config em `venda.congelada` +
`venda._reservar_rl_formatos` + `compras_urgentes[].material_pendente`, kind novo
`preco_impressao` na `watched`. Testes em `tests/test_decisoes_1004_fecho.py`
(11 casos) e a prova de que chumbam em `tests/_chumba_decisoes_fecho.py`
(**20 de 20 alvos**, um processo por par). Backup em
`data/backups/vault-2026-10-04-decisoes-noite.db` (103,5 MB, `integrity ok`).

- **1) A TRAVA É MANUAL E JÁ NÃO SE LEVANTA SOZINHA.** Era
  `venda.congelado_ate: "2026-10-12"` — uma DATA, que caía no dia 12 por si. Ele
  decidiu que não: *"a venda passa a destrancar só quando eu disser"*, porque o
  **estado das cartas está por avaliar** (a escala entrou a 03/10 e as 737 linhas
  da `copies` continuam todas com o `NM` de omissão, `condition_origem =
  'omissao'`). Hoje é `venda.congelada: true`.
  **O COMPORTAMENTO NÃO MUDOU** — o `venda.exportar`, o passo `venda-export` do
  `daily` e os dois endpoints de escrita do 8771 continuam a levantar
  `fases.VendaCongelada` e o `webapp` continua a traduzi-la num **409** com a
  frase em português. O que mudou é a CONDIÇÃO.
  - **COMO SE DESTRANCA, e é a pergunta que ele vai fazer dentro de um mês:**
    **`py -m mtgvault.cli vender --congelada off`** (ou `venda.congelada: false`
    no config). A frase vive **num sítio só** (`fases.COMO_DESTRANCAR`) e sai nos
    TRÊS lados onde ele bate: a mensagem do 409, a linha do `daily`/CLI e a
    **Fase 4 da `arrumacao.html`**, num bloco destacado. Escrita em cada
    superfície, a segunda ficava desactualizada.
  - **A OMISSÃO É «DESTRAVADO»** (`CONGELADA_OMISSAO = False`), que é o que a
    ausência da chave já valia — por isso uma base nova e os testes continuam a
    poder exportar. Quem trava é a chave escrita.
  - **A CHAVE ANTIGA NÃO SE APAGOU: foi para o histórico**
    (`venda._congelado_ate_historico`), com a data, o `substituida_em`, a razão
    e o **texto explicativo original** — é memória do projecto. E **deixou de ter
    efeito**, como o `playset_maximo` e o `dedicado: false`: se alguém a voltar a
    escrever no bloco `venda`, o `fases.data_sem_efeito()` **avisa-o** em vez de
    a deixar mentir em silêncio. Tem caso de teste nos dois sentidos — uma data
    no futuro não trava, uma data passada não destranca.
  - **O `venda.mostrar` não se tocou** (continua `false`): são duas chaves
    diferentes e ele não pediu para voltar a ver a venda.
  - **A `arrumacao.html` TEVE DE SER REGERADA, e é a parte que quase passou.** O
    código estava certo e o HTML em disco **mentia**: continuava a prometer
    *«A partir de 2026-10-12 aparece aqui o mesmo botão da Fase 2»*, que a partir
    de hoje é falso. É o padrão do `event_tier` na porta de entrada, e é o mesmo
    que aconteceu ao `index.html` quando as fotos foram desligadas nesta manhã.
- **2) A RL QUE SÓ JOGA EM DUEL COMMANDER: a razão passou a estar ESCRITA.**
  Isto **já funcionava** — `venda.reservar_rl_formatos` é `["legacy"]` e o
  duel-commander nunca lá esteve —, mas funcionava **por acidente de
  configuração**. O que entrou foi o `_reservar_rl_formatos`: *«RL que jogue» são
  as que ELE joga nos decks DELE, e não as que o formato joga*. Acrescentar
  `duel-commander` àquela lista punha o vault a segurar Reserved List por causa
  de decks que ele não joga.
  - **CONFERIDO ao exemplar**, e é a premissa da decisão: os **7 nomes** de RL
    que só aparecem em listas de `duel-commander` — Memory Jar, Metalworker,
    Rofellos Llanowar Emissary, Time Spiral, Treachery, Yavimaya Hollow,
    Yawgmoth's Bargain — e **NENHUM deles entra na lista do deck de Duel
    Commander que ele escolheu** (o `decklist 22794`, a lista do Liwei Luo, 80
    nomes). Os 7 são `reserved = 1` e nenhum aparece numa lista de outro formato.
  - **UMA CORRECÇÃO AO APURAMENTO, e é a favor dele: são SEIS e não sete.** O
    **Metalworker** continua protegido — mas pela **R4** e por outra razão: *está
    na lista do Cloud cEDH*, que é um deck dele. Os outros seis estão na lista de
    candidatas: **9 cópias / 640,98 €** (e não 453,26 €, que é o número da ordem
    — a diferença é a régua só-CardTrader de 04/10).
  - **E o «Radiant Archangel» dos outros seis não existe: é «Radiant,
    Archangel»**, com vírgula (ULG #20, `reserved = 1`). Com o nome certo, os
    seis que não aparecem em lista meta nenhuma são **11 cópias / 470,04 €** —
    todos na lista de candidatas, como a ordem esperava.
- **3) O WHIPFLARE: NONFOIL AGORA, FOIL DEPOIS.** A excepção ao `acabamento:
  foil` do grupo `spml` passou de **PENDENTE** a **DECIDIDA e `aplicado: true`**,
  com a data, as palavras dele e os dois preços. A caixa `modern` passa a
  ACEITAR o nonfoil nesta carta: quando a cópia entrar **fecha o slot** em vez de
  ficar substituto, e a lista de compras fica satisfeita. A linha de compra
  deixou de dizer *«decisão do material PENDENTE»* e passou a dizer só
  *«EN · nonfoil»*.
  - **E FICA MARCADA PROVISÓRIA** (`material_pendente.provisoria: "trocar por
    foil"`): chip **«🔄 provisória · trocar por foil»** na wantlist da caixa e na
    aba Comprar. Sem ele a linha ficava igual a uma compra definitiva e a troca
    caía no esquecimento — que é precisamente o que a vigia existe para impedir.
  - **A VIGIA DO FOIL REAPROVEITA A `watched`**, com o kind novo
    `preco_impressao` — a mecânica de vigiar (inscrever, snapshot, «mudou?», o
    `watch-check` do daily, o toast) já vivia lá, e escrever uma segunda era ter
    duas respostas para *"o que é que eu estou a vigiar"*. **Não vai à rede**:
    lê a `price_latest` que o `daily` já preenche. Inscrita na base dele, **id 7**
    (`Whipflare (NPH #102) foil`), e verificada: 20,20 €, 2.ª corrida
    `changed: False` (sem sinal falso), e a descer a 9,50 € **avisa**.
  - **O LIMIAR SÃO 10,00 €, e a razão é MEDIDA.** (1) É o **p90 das compras foil
    dele**: das 33 linhas de compra em foil com preço, a mediana é **1,10 €**, a
    média 3,28 € e o p90 **10,10 €** — abaixo de 10 € o Whipflare deixa de ser um
    outlier (hoje é a 2.ª mais cara de todas, só atrás do Overlord of the
    Balemurk a 22,61 €) e passa a ser uma compra foil como as outras 90 %. (2) É
    **metade** do preço de hoje (20,20 €), logo uma descida inequívoca e não
    ruído de cotação. (3) É um valor **ABSOLUTO e não uma percentagem**, porque o
    histórico do foil de NPH tem **UM ÚNICO PONTO** (20,20 € a 2026-09-29): uma
    percentagem sobre um ponto não é medição nenhuma e não se finge que é.
  - **A FONTE DA VIGIA É FIXA NA INSCRIÇÃO (`cardmarket`), e sem isso ela não
    vigiava nada.** A cadeia em vigor é só `cardtrader`, que **não cota uma única
    impressão de Whipflare** — pela cadeia, esta vigia nunca teria preço e nunca
    avisaria. E uma vigia que trocasse de fonte entre corridas comparava duas
    escalas de preço (a lição da `precos.receita`): um salto de fonte parecia uma
    descida e disparava um aviso falso. Logo mede-se sempre na mesma régua, e sem
    cotação a resposta é *"sem preço"* — **nunca 0 €**, que seria o aviso mais
    alto possível por falta de dado. Tem caso de teste para cada uma das três.
  - **O `_migrate` PASSOU A PERGUNTAR «FALTA ALGUM KIND?»** e não «falta o último
    que eu acrescentei» (era `"mtgtop8_archetype" not in sql`). Na base dele, que
    já tinha esse kind desde esta mesma noite, a reconstrução não corria e o
    `preco_impressao` ficava **fora do CHECK** — `IntegrityError` no
    `watchlist.add`, a vigia a não se inscrever. A lista vive num sítio
    (`db.KINDS_VIGIA`), o CHECK da tabela reconstruída sai dela, e há teste que
    exige que o `schema.sql` diga o mesmo. **Medido na base dele: 7 vigias e 17
    snapshots, nada perdido, `foreign_key_check` limpo.**
  - **O teste deste ponto tinha um PONTO CEGO que o `_chumba` mostrou:** só
    construía a tabela de *antes* de 04/10, e por isso passava com o defeito
    posto. Hoje mede os **dois** pontos de partida, e o segundo é o da base dele.
- **AS OUTRAS CARTAS NO MESMO CASO: só há uma, e é esta.** Medido nas **34**
  linhas de compra das caixas que pedem foil: **1 de 34** tem o foil a ≥10× o
  nonfoil — o Whipflare, a **96,2×**. A segunda pior é o **Thoughtcast a 8,4×**
  (4,97 € contra 0,59 €), e depois Witherbloom Command 6,1×, Parhelion II 4,3× e
  Greasefang 4,1×. **Não se repete em dez cartas: a regra do grupo não está mal**
  — é esta carta que é um caso isolado, e por isso abre-se excepção a ela e não
  se mexe na regra.
  - **O primeiro medidor disto respondeu «0 linhas» e não media nada**, e vale
    registá-lo: exigia preço na cadeia em vigor (só CardTrader, que deixa 18 das
    154 compras sem preço) e lia o acabamento da STRING `req_compra` — que, por
    causa da excepção, já dizia *«nonfoil»*. Excluía o próprio Whipflare, o caso
    conhecido. O medidor certo lê o **acabamento da regra do grupo** e o preço da
    fonte **que cota**, e usa o Whipflare como controlo positivo: se ele não
    aparecer, o medidor está mal, não a regra.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados** (worktree em
  `_revisao/main-0410c-noite`): **fechar tudo 5 895,14 € nos dois**, 245 a
  comprar, 21 sem preço, candidatas **611 c / 17 888,30 €**, protegidas
  **1 067 c / 126 575,57 €**, as nove saídas da venda, a arrumação e **as 17
  caixas iguais à percentagem e ao cêntimo**. As **14** diferenças do payload são
  todas desta ordem: a data que saiu do bloco `venda`, e o `material_pendente` do
  Whipflare (`aplicado` false→true, `estado` PENDENTE→DECIDIDA, a `provisoria`, e
  o `req_compra` que deixou de dizer «PENDENTE»). **A alocação não mexeu um
  número.**
- **POR DECIDIR POR ELE:** (a) o **Whipflare continua sem preço na régua em
  vigor** e entra na lista de compras a 0,00 € (conta em `sem_preco`) — se quiser
  o preço de volta é `precos fonte cardtrader --recurso cardmarket`; (b) o
  **limiar de 10 €** é escolha minha a partir da curva medida, e muda-se no
  `watched.notes`; (c) o **Metalworker** fica protegido pela R4 enquanto estiver
  na lista do Cloud cEDH — se ele o quiser vender, é tirá-lo dessa lista; (d) o
  **Cursed Totem** continua fora da lista, como ajuste não decidido.

**AS DECKLISTS NO SITE, PARA ELE SLEEVAR (André, 2026-10-04, ao fim do dia, à
letra).** *"Quero que atualizes as decklists no site, para eu aceder e comecar a
sleevar as coisas"*; *"falta escolher decks, falta depois eu organizar os decks,
guardar as que sao staples"*; *"vi que nao leste o RC Qualifier nas decklists"*;
*"esquece venda, eu trato da venda"*. **Uma lista errada custa-lhe uma tarde de
sleeves**, e é essa a régua desta ordem. Motor em `mtgvault/mtgtop8.py`
(`ESCALA_TECTO`/`escala_do_tecto`, `e_pagina_de_evento`, `_abrir_evento`,
`revisitar`), `mtgvault/loadout.py` (as notas de `_cards_from_consensus` e
`_cards_from_watched`), `mtgvault/decks_vista.py` (`sem_lista_porque`,
`staples_do_formato`), `decks.py` e `premodern_decks.py`; CLI
`py -m mtgvault.cli revisitar [formato] [--evento N] [--limite N] [--fila]`.
Testes em `tests/test_decklists_no_site.py` (9 casos) e a prova de que chumbam em
`tests/_provar_decklists.py` (**14 de 14 pares**, um processo por par). Backup em
`data/backups/vault-2026-10-04-decklists-no-site.db` (98,2 MB, `integrity ok`).
**A VENDA NÃO SE TOCOU**, por ordem dele.

- **O RC QUALIFIER ESTAVA LÁ; o que estava truncado era o REGIONAL
  CHAMPIONSHIP.** O `Modern RC Super Qualifier` de 03/10 tinha as suas 31 listas
  e as 31 classificadas — isso estava bem e não se mexeu. O que estava mal: o
  `Modern event - Regional Championship` de 12/09, **1 486 jogadores e 16 listas
  na base**, porque o `max_decks_per_event` cortava em 16 e a página serve 64.
  O maior torneio de papel de Modern contribuía **metade** de uma Challenge 64.
- **O TECTO PASSOU A DEPENDER DO TAMANHO DO CAMPO, não do nome** (`ESCALA_TECTO`,
  config `mtgtop8.grandes.escala_jogadores`). A regra: **metade do campo, na
  escala de classificação que o próprio mtgtop8 usa** (`_bracket`: 9-16, 17-32,
  33-64) — **128+ jogadores → 64 listas, 64-127 → 32, abaixo de 64 fica o tecto
  normal de 16**. Metade do campo porque é a proporção que o vault já pratica no
  online (uma Challenge 64 traz 32 de 64 jogadores) e aplicá-la ao papel põe os
  dois na mesma régua. O topo é 64 porque **é o que a página serve**: medido nas
  duas páginas de 921 e 1 486 jogadores, **64 links de deck exactamente**.
  - **PORQUE O NOME NÃO SERVE, medido:** dos **9** eventos da base truncados nos
    16 com 64+ jogadores, **4 têm nomes que nenhum padrão reconhece** — e um
    deles era precisamente o que tinha listas a mais para dar (o «Buckeye Brawl
    II - Retromancers», 125 jogadores, 32 na página). O ramo do NOME **fica como
    piso** (o tecto é o `max` dos três): o «RC Hangzhou Side Event» tem 70
    jogadores e nome reconhecido, e com a escala sozinha descia de 64 para 32.
  - **A ESCALA É SÓ PARA O PAPEL** (`sources.event_tier`), e sem isso não valia
    nada: semeada a memória, a fila de revisitas dava **54 eventos e 28 eram
    Challenges de MTGO de Modern** — listas que o vault já tem pela fonte directa
    e que a deduplicação descarta. Eram ~28 noites de pedidos a produzir zero.
    Com o crivo, a fila são **22**.
  - **O GANHO HONESTO SÃO +16 LISTAS, não as 127.** A regra de 04/10 de manhã já
    recuperava **111** das 127; a escala acrescenta **16**, que são o Buckeye
    Brawl II. Dizer que a regra nova trouxe 127 era dar-lhe crédito pelo trabalho
    da ordem anterior.
- **A MEMÓRIA ESTAVA VAZIA — a recuperação nunca tinha arrancado.** A
  `mtgtop8_eventos` tinha **0 linhas**: o `semear_memoria` corre dentro do
  `harvest`, e o `harvest` não corria desde que o código entrou (08:37 contra o
  `daily` das 03:30). Ou seja o diagnóstico de que «a memória impede a revisita»
  era ao contrário: **sem semente não havia fila nenhuma**. Semeada: **401
  eventos**.
- **FORÇAR A REVISITA: `py -m mtgvault.cli revisitar`** (semeia primeiro, é
  idempotente). Sem travão, por id (`--evento`, repetível) ou a fila inteira, com
  `--fila` para ver sem pedir nada. **Resultado medido**, 21 eventos revisitados e
  **127 listas novas**, todas com nome da fonte:

  | evento | jogad. | na página | listas | ganho |
  |---|---|---|---|---|
  | Regional Championship (MO) | 1 486 | 64 | 16 → **64** | **+48** |
  | Magic Spotlight: The Hobbit (MO) | 921 | 64 | 16 → **64** | **+48** |
  | $uper $unday ReCQ (MO) | 344 | 31 | 16 → **31** | **+15** |
  | Buckeye Brawl II (PREM) | 125 | 32 | 16 → **32** | **+16** ← só a regra nova |
  | European Championship (PREM) | 218 | — | 16 | página morta |
  | Czech Nationals (PREM) | 191 | 8 | 8 | +0 (não estava truncado) |
  | Bogardan War II (PREM) | 139 | 16 | 16 | +0 (idem) |
  | + 14 outros | | | | +0 |

  **Duas correcções à premissa, e as duas a favor dele:** as Czech Nationals e a
  Bogardan War II **não estavam truncadas** — as páginas delas só servem 8 e 16
  listas; revisitá-las custa 1 pedido e fecha-as. Efeito no registo: Modern
  **19 → 21** arquétipos (Broodscale 73 → 87, Esper Blink 29 → 41, Pinnacle
  Affinity 25 → 35), Premodern 10 (Enchantress 21, Landstill 13, Sligh 13).
  **São de 05/09 a 27/09, logo FORA da janela do consenso (29/09)** — entram no
  registo e na escolha de decks, e a janela não se tocou.
- **PEDIDOS AO MTGTOP8: 161 nesta ordem**, todos a 1/s pelo `_get` de sempre (1
  ao `robots.txt`, 9 a medir páginas de evento, 24 páginas de evento nas
  revisitas, 127 `.dec`). **O `robots.txt` do mtgtop8 responde 404** — não existe,
  por isso não há regra a respeitar além do ritmo.
- **UMA PÁGINA DE EVENTO QUE JÁ NÃO EXISTE RESPONDE 200**, e isso era um buraco:
  o 90532 devolve a página genérica (*«MTG Decks Database»*, 12 KB, zero datas) com
  **`d=0`** nos links do menu. Sem crivo, revisitá-lo pedia o `.dec` do deck 0 e
  dava um evento de 218 jogadores por **COMPLETO com uma lista**. Hoje o
  `parse_deck_ids` descarta `d <= 0` e o `e_pagina_de_evento` exige DATA e DECK —
  e o evento **não se marca**, como uma falha de rede.
- **E ISSO ENTUPIA A FILA PELA CABEÇA.** A fila ordena por nº de jogadores e o
  evento morto (218) era o primeiro de Premodern: não se marca, logo ficava lá
  **todas as noites** e os outros 5 nunca eram vistos. O travão das revisitas
  passou a contar **vezes GASTAS** e não tentativas (`_abrir_evento` devolve
  `(novas, marcou)`), com um tecto de tentativas (`2×limite+2`) para a noite não
  ficar presa numa cauda de páginas mortas. Tem caso próprio.
- **O `players` DA REVISITA É O MÁXIMO ENTRE A PÁGINA E O LEMBRADO.** Há páginas
  antigas que já não dizem a contagem; com `players = None` o tecto caía para 16,
  o `por_fazer` continuava a dizer «vale a pena» (decide com a coluna `players`)
  e o evento era pedido para sempre. É o defeito do tecto optimista de 04/10 de
  manhã pelo outro lado.
- **O NOME DA CAIXA `modern` ESTAVA ERRADO, e ele ia sleevar por ele.**
  Chamava-se **«Modern — UW Oswald»** e a lista lá dentro é a de QUALIFICAÇÃO
  dele, que é **Izzet Affinity**: 4 Kappa Cannoneer, 4 Pinnacle Emissary, 4
  Weapons Manufacturing, 2 Arcbound Ravager, 4 Mox Opal — **zero cartas brancas e
  zero Oswald Fiddlebender**. Passou a **«Modern — Pinnacle Affinity»**, que é o
  nome que a FONTE dá a estas listas (mtgtop8: 17 votos de 19 nomeadas em 94
  listas; segundo lugar «Affinity»), pela regra de 02/10. **A lista não se
  tocou** — é dele e é a certa.
  - **HAVIA DOIS DECKS A DISPUTAR A CAIXA, e nenhum se apagou:** o **deck 12 «UW
    Oswald»** da tabela `decks` (34 linhas, 4 Oswald Fiddlebender, Hallowed
    Fountain, Portable Hole — um deck a sério, com o nome certo) era o ANTERIOR
    desta caixa, e a lista de qualificação é a que ficou (`fonte: escolhido`,
    `ref: modern`). O `_antes` repõe o antigo.
  - **O `listas_escolhidas.modern` ganhou `arquetipo: "Pinnacle Affinity"`**, e é
    isso que faz o meta com o mesmo nome dizer *«já é uma caixa tua»* em vez de
    aparecer como um segundo deck — o mecanismo (`_nome_do_consenso`) já existia e
    faltava-lhe a chave.
  - **A PASTA DE FOTOS tratou-se sozinha**: nasceu `Colocar fotos da coleção
    aqui\Modern — Pinnacle Affinity\` com o plano (16 fotos, 52 cartas) e a antiga
    ficou com o `fotos.TEXTO_ORFA`. **Zero imagens em qualquer das duas** (as
    fotos foram apagadas nesta manhã), por isso não se perdeu nada.
  - **POR DECIDIR POR ELE, e NÃO se tocou:** a `reserva_assinatura` continua
    `["Oswald Fiddlebender"]` — o deck que ele já não monta. Mexer nisso muda a
    reserva, que é a lista de candidatas à venda, e **a venda está fora desta
    ordem**. Fica mais VISÍVEL do que estava: a Arrumação mostra «Modern —
    Pinnacle Affinity … 12 listas com Oswald Fiddlebender», que é a conferência
    da assinatura à vista. O mesmo para o **deck 12 em `decks_vigiados`**, que
    continua a reservar as suas cópias na cobertura.
- **UMA CAIXA DESACTIVADA DEIXOU DE SER UM DECK DE 0 %.** A `modern-affinity`,
  que ele mandou desactivar nesse dia, aparecia na lista de Modern ao lado dos
  decks que vai montar, com o estado `candidata` — que é um estado normal da
  escala e não quer dizer «desactivada». A pergunta vive num sítio
  (`decks_vista.sem_lista_porque`) e distingue **três** coisas: **desactivada**
  (`fonte: consenso` sem `assinatura` — é o gesto do «já não vou montar este»),
  **por escolher** (a `legacy-artifacts-blue`, que espera a carta-assinatura dele)
  e **sem amostra** (a nota do `_slot_cards` já o dizia). **Escolheu-se MARCAR e
  não esconder**: ele tem o `_antes` no config para a repor, e uma caixa que
  desaparecesse da página deixava-o sem por onde a reaver. Fica no **fim** da
  lista, apagada, com o rótulo, sem a caixa «quero montar», e fora do
  `n_decks` (o cartão do formato diz «… · 1 desactivada»).
- **CADA UMA DAS 17 CAIXAS DIZ A LISTA, A FONTE E A DATA.** Faltava a DATA em
  nove: as de `consenso` diziam só *«consenso de N listas»* e as de `deck`-com-
  consenso não diziam nada. Hoje: o consenso leva **as datas das listas que
  entraram e a janela** (*«consenso de 32 listas de 2026-09-04 a 2026-10-03»*), o
  `premodern_decks` escreve *«recalculado a …»*, e a **lista vigiada diz as DUAS
  datas** — *«lista vigiada de 2026-09-04 — sem mudar desde então, conferida a
  2026-10-04»*. Essa última era a pior: o Blue Farm parecia informação de há um
  mês, quando a vigia o tinha lido de manhã e confirmado que não mudou. A coluna
  `watched.last_checked` já existia e ninguém a mostrava.
- **UMA CORRECÇÃO À PREMISSA: o mínimo de listas é 5, não 8.** A `premodern-igg`
  tem 4 listas e a página **já dizia** *«amostra insuficiente: 4 listas (o mínimo
  para se chamar consenso a isto é 5)»* — o `stock_min_lists()` é 5; o 8 é o
  `consenso.MIN_LISTAS` dos comandantes. Não havia nada a corrigir, e há caso de
  teste a trancá-lo.
- **A SEQUÊNCIA DELE, no sítio onde ela acontece.** Num formato rotativo sem nada
  marcado a página mostrava dois zeros e mais nada; hoje mostra **«Por onde
  começar»** com os três passos (marcar → ver próprias e partilhadas → as
  partilhadas são as staples). E, depois de ele marcar, **as STAPLES DO FORMATO
  agregadas** (`staples_do_formato`) — a pilha que ele guarda à parte, com em
  quantos decks cada carta entra, quantas precisa (o MÁXIMO, que é a regra
  rotativa) e quantas tem. **Não é uma conta nova**: é o mesmo `rep` que decide
  própria vs partilhada em cada deck, visto pelo formato. Medido com 3 decks de
  Premodern marcados: necessidade 225 a somar / **199 a rodar**, sleeves 168
  reais + 57 proxies, e **8 staples** (5 Plains e 4 Swords to Plowshares em 3
  decks; 6 Forest, 4 Brushland, 4 Windswept Heath, 3 Naturalize, 3 Warmth, 2
  Glowrider em 2).
- **MARCAR RECALCULA — foi medido, não assumido.** 0 marcados → tudo a zero; 3
  marcados → os números acima; desmarcar um devolve as staples a zero. As
  partilhadas de cada deck **são** exactamente os proxies dele, nos três.
- **DOIS DEFEITOS DE LAYOUT QUE NUNCA TINHAM SIDO MEDIDOS.** A lista do
  `tests/medir_layout.py` era a de 24/09 e **três páginas nascidas depois nunca
  foram medidas a 390 px** — a `decks.html`, a `arrumacao.html` e a
  `comandantes.html`. Entraram lá. A `decks.html` e a `comandantes.html` estavam
  bem; a **`arrumacao.html` tinha scroll horizontal** (corpo a **453 px** numa
  janela de 390), por causa da tabela de sete colunas das duais. As tabelas `.cd`
  passaram para um `.tw{overflow-x:auto}`: a tabela rola dentro dela e a página
  fica quieta. Esconder mais colunas era esconder informação.
- **UM TESTE DE 04/10 DE MANHÃ TEVE DE SER CORRIGIDO, e não mascarado.** O
  `test_papel_grande.caso_o_tecto_alto_exige_que_a_pagina_confirme_o_tamanho`
  afirmava que um evento que o nome não reconhece fica com 16 listas mesmo com
  1 486 jogadores — e é isso que esta ordem muda. A asserção passou a afirmar a
  regra nova, com as duas datas no docstring, e o que a função continua a trancar
  é a outra metade (um nome grande com o campo pequeno **não** sobe de tecto). E
  o `caso_um_dec_que_falha_nao_marca_o_evento_como_feito` passou de 70 para **30
  jogadores**: com 70 havia dois mecanismos a recuperar o evento (a não-marcação e
  a escala) e o caso deixava de isolar o primeiro — apanhado pelo
  `_chumba_papel semente_vazia`, que tinha deixado de trancar. **Os 11 alvos do
  `_chumba_papel` continuam todos a trancar**, verificado um a um.
- **MEDIDO COM O SERVIDOR A CORRER E O JS A SÉRIO** (o `webapp.py` relançado com
  o código final): as **13 páginas a 200**, os **248 ficheiros de dados a 200**,
  **zero** mensagens de erro de dados, e a aba Decks percorrida até ao **nível do
  deck em três formatos** (Premodern 23 tiles, cEDH 100, Duel Commander 80). A
  segunda passagem de cada página em **1–27 ms**; a mais lenta das 248 partes,
  27 ms. A 1440 e a 390 px, **nenhuma página com scroll horizontal**.
- **POR FAZER, e vale a pena saber:** (a) o **European Championship de Premodern
  (218 jogadores)** continua na fila — a página dele desapareceu do mtgtop8, e por
  isso custa **1 pedido por noite** até voltar (ou até alguém decidir marcá-lo à
  mão); não se marcou de propósito, pela regra de nunca perder um evento por uma
  falha; (b) a `reserva_assinatura` da caixa `modern` e o deck 12 em
  `decks_vigiados`, acima; (c) os restantes **14 eventos** da fila foram todos
  drenados nesta ordem e deram **0 listas novas** — as páginas deles só servem
  3–16 listas; (d) a aba Decks mostra as staples **por formato**; uma carta que
  seja staple em DOIS formatos (as Swords to Plowshares são-no em Premodern e em
  Legacy) aparece nas duas listas e não há uma vista que as junte.

**A LISTA DE UM DECK É UMA LISTA QUE ALGUÉM JOGOU (André, 2026-10-04, ao fim do
dia, à letra).** *"as listas especificas e que quero fixas"* e *"as outras quero
que esquecas as decklists e vamos focar nas decklists baseadas em eventos
reais"*. **ACABA O CONSENSO COMO LISTA DE DECK:** uma média de muitas listas é um
deck que ninguém jogou. O caso que o provou foi o do Cloud, no mesmo dia — as 40
listas que a assinatura apanhava eram **dois decks diferentes** e a média dava um
terceiro que não fazia nenhuma das duas coisas; ele generalizou a lição. **O
motor do consenso NÃO se apaga** (regra dele de 09/09): continua a medir o
metagame, a dar os nomes e a alimentar a reserva da venda — o que muda é QUAL a
lista que a caixa mostra. Motor em **`mtgvault/eventos.py`**, config em
`listas_de_evento` (a regra) + `decks_de_evento` (os decks dele) +
`listas_escolhidas[<id>].evento` (a proveniência gravada); testes em
`tests/test_listas_de_eventos.py` (19 casos) e a prova de que chumbam em
`tests/_chumba_listas_eventos.py` (**13 de 13 alvos**, um processo por alvo).
Backup em `data/backups/vault-2026-10-04-listas-de-eventos.db` (99,5 MB,
`integrity ok`). **A VENDA NÃO SE TOCOU** (ordem dele) — ver a ressalva no fim.

- **A PROVENIÊNCIA GRAVA-SE, e é a decisão que torna o resto possível.** O
  `daily.prune_decklists(30)` apaga as decklists ao fim de um mês: uma caixa que
  fosse um PONTEIRO para um `decklist_id` ficava **vazia em Novembro**, sem um
  único passo a falhar — o padrão do `event_tier` aplicado à lista por que ele vai
  sleevar. Por isso as cartas **e** a proveniência (jogador, evento, data,
  jogadores, classificação, URL, `content_hash`, repetições) são lidas da base no
  momento de fixar e gravadas no config. **Reutiliza o `listas_escolhidas` + a
  `fonte: "escolhido"`** da LISTA PADRÃO de 20/09 e não um quinto `fonte` ao lado:
  esse caminho já é lido pelo motor, pela página e pelo CLI. O `decklist_id` fica
  guardado para se poder **conferir**, nunca para ler a lista em tempo de página.
  Tem caso próprio, que apaga a decklist à mão e exige que a caixa continue com as
  cartas E com a ficha.
- **A REGRA DE ESCOLHA VIVE NO CONFIG** (`listas_de_evento.regra`), com os
  critérios pela ordem e **a razão de cada um em português** — está lá e não no
  código para não ser *a minha opinião de hoje*. Por esta ordem: a **janela** (um
  FILTRO, primeiro), o **tier**, o **campo**, a **repetida**, a **classificação**,
  a **data** e o **jogador** (alfabético, o desempate determinista de 02/10).
- **A JANELA FILTRA PRIMEIRO, e isso foi o caso do Greasefang a obrigar.** A
  melhor presencial dele é de **22/09** (Sakamoto, 3-4 de 65) e a janela começa a
  29/09: sem o filtro à cabeça, o vault escolhia a lista **pré-Reality Fracture** e
  contradizia a escolha dele (a Challenge de 01/10). A melhor presencial que a
  janela corta **não se esconde**: fica ao lado, com a data à vista e a frase a
  dizer que é anterior ao set — é a regra 5 dele, à letra.
- **O TIER ENTROU PORQUE A FONTE ESTAVA A DECIDIR, e o número é este:** o `Modern
  RC Super Qualifier` de 03/10 vem do **mtgo.com** e tem **31 listas, ZERO
  classificações e ZERO contagens de jogadores**; a mesma Challenge re-hospedada
  pelo mtgtop8 traz `100 jogadores` e `3-4`. Sem o critério do tier a regra
  preferia a Challenge — por uma razão de DADOS e não de mérito. Com ele, acerta o
  **evento em 9 de 9** dos decks de Modern que ele nomeou. **É UM critério e não
  dois:** o «presenciais antes de online» dele é o primeiro degrau do tier
  (`Presencial` 0 < `Qualifier` 1 < `Challenge` 2 < `League` 4), e houve uma
  passagem com os dois separados em que o «presencial» **nunca mudava nada** — a
  armadilha do `playset_maximo`. Foi o `_chumba` que a apanhou, a tentar prová-la.
- **«GANHAR» É VENCER, e a distinção vale uma escolha.** A regra da lista repetida
  conta só as aparições com **1.º lugar** (`_vitorias`), não os resultados
  (`_repeticoes`, que a ficha mostra). Medido: com resultados, **três 9-16 do mesmo
  jogador ganhavam a um 5-8** e o Esper Blink afastava-se da escolha dele; o caso
  que originou a regra são os **três primeiros lugares** do Cloud. E a contagem é
  na BASE e não só entre as candidatas — duas contagens da mesma coisa punham o
  desempate a dizer «1» e a ficha ao lado «3», no mesmo ecrã.
- **A REGRA REPRODUZ AS ESCOLHAS DELE: 7/7 nas caixas.** Stiflenought (Simone
  Fierro, **1.º de 218**), UW Replenish (Kuznetsov, 5-8 de 218), Enchantress
  (Schnurr, 3-4 de 218), Elves (Deschamps, 2.º de 125), Oath (Shroomboy, **1.º de
  125**), Ill-Gotten Gains (Vlalutscher, Challenge 16 de 03/10) e Greasefang
  (Martin_Dominguez, Challenge 32 de 01/10). **O 1.º lugar do European Championship
  já estava colhido** (id 16900) — a página morta do evento não escondia nada, e a
  revisita dos eventos grandes da ordem anterior não acrescentou nenhuma escolha.
- **ONDE A REGRA NÃO CHEGA, O JOGADOR QUE ELE NOMEOU GANHA.** Dentro do RC Super
  Qualifier não há classificação nem campo: entre cinco listas do mesmo arquétipo
  **não existe critério objectivo**, e o desempate alfabético dava outra pessoa em
  5 de 10. Ele nomeou-a; eu não a derivo. O registo guarda `escolhida_por` e, onde
  divergem, o `regra_diria` — é a hierarquia do resto do vault (a correcção dele
  ganha sempre). **As percentagens confirmam que são as listas certas**: Esper
  Blink 89 %, Goryo's 85 %, Rakdos Moonshadow 48 %, Devoted Combo 35 % — exactas;
  as outras a 1–4 pontos; e as seis de Premodern batem todas (78/89/60/60/68/68).
- **OS DECKS DELE NÃO SÃO CAIXAS NEM META** (`decks_de_evento`, 11 entradas): não
  têm deckbox e já não são o meta. E **tinham de ser um tipo próprio**: o meta
  agrupa pelo NOME DA FONTE e **três dos dez não têm nome nenhum** (o
  `arquetipo_fonte` daquelas listas está a NULL, porque vêm do mtgo.com) — o UR
  Prowess, o Goryo's Reanimator e o Hammer Time nunca apareciam lá; e em quatro
  outros o nome que ele usa não é o da fonte (*"Boros Energy"* contra *"Boros
  Aggro"*). **A identidade é o slug escrito no config**, nunca o `archetype_id` (o
  cluster é refeito a cada corrida) nem o nome votado; o `archetype_id` fica como
  a pista de onde a escolha veio. O arquétipo meta com o mesmo nome marca-se
  `ja_e_caixa` e não aparece a dobrar.
- **O CONSENSO QUE SAI DE CADA CAIXA FICA GUARDADO** (`_consenso_anterior`: as
  cartas, a data, a razão e a nota), *nada se apaga* — e **custou duas passagens
  acertar**: o `padrao.fixar` substitui o registo inteiro por um dicionário novo,
  por isso o bloco desaparecia e a segunda corrida gravava lá a lista de evento que
  a primeira acabara de fixar. A média que ele quer poder comparar ficava
  substituída por uma cópia dela. Hoje o `fixar` lê o bloco ANTES e repõe-no, e
  `consenso_antes = []` (não havia consenso) grava-se como tal — senão a passagem
  seguinte lia-o como ausente. **O script é idempotente, provado em três
  passagens** (sha igual).
- **A `premodern-igg` DESTRANCOU.** Estava com **4 listas** e o mínimo para se
  chamar consenso a algo é 5: ficava sem lista nenhuma. Com a regra nova não
  precisa de 5 — precisa de **UMA lista real**. Passou de 0 % a **33 %**, com 32
  cartas. A razão por que estava trancada fica no `_consenso_anterior`.
- **A `legacy-artifacts-blue` CONTINUA VAZIA e a pedir a carta-assinatura dele**
  (nunca disse qual é, e não se adivinha a partir do nome), e a `modern-affinity`
  continua desactivada. As duas têm caso de teste.
- **O STANDARD E O LEGACY FICAM COMO ESTAVAM, por ordem dele** (*"Standard nao
  preciso preocupar me ate Janeiro, ja estou qualificado para jogar em Fevereiro"*
  e *"esquecemos legacy para ja tambem"*): não receberam lista de evento, ficaram
  com a nota de âmbito (`caixas[]._ambito`, com as palavras e a data) e **não se
  apagaram nem se desactivaram**. Consequência a saber: as três estão hoje **sem
  lista**, porque o consenso delas tem 1, 2 e 3 listas contra um mínimo de 5 —
  trocá-las para evento real resolvia (as listas estão apuradas: Gones Fire 2026,
  94 jogadores), e é decisão dele.
- **UM CONSENSO DIZ QUE É UM CONSENSO.** O meta fica para CONSULTA (*"ficam no
  meta para consulta"*) e continua a mostrar a média — o que não pode é ter a
  mesma cara de uma lista real na página por onde ele vai sleevar: leva
  `e_consenso` e o rótulo *«consenso de várias listas — ninguém jogou esta lista
  assim»*. Tem caso de teste.
- **OS PROXIES PASSARAM A SER CONTADOS COMO ELE OS CONTA**, e isto mediu-se contra
  o papel dele: por **aparições** (um proxy por carta diferente em cada deck) dá
  **147** em Modern e **69** em Premodern, contra os **149** e **63** que ele
  trouxe; por CÓPIAS dava 334 e 201. Ele imprime um proxy por carta diferente —
  serve de marcador de *"esta vem da pilha"* — e não quatro de um playset. As
  cópias ficam ao lado com etiqueta (a regra dos «dois números» de 04/10 à tarde).
  **O «79 verdadeiras» dele bate ao exemplar** com os nomes próprios do maindeck de
  Premodern. **Ressalva honesta: os ficheiros que ele tem na mão NÃO estão neste
  PC** (o mais recente em `ai-pc/work/saidas/` é de 03/10) — não há como reconciliar
  ao exemplar, e as staples dão 55 contra os 50 dele.
- **O HAMMER TIME LEVA O AVISO, e não escondido num rodapé** (`amostra_fina`, num
  bloco antes da lista): **1 lista** em toda a colheita contra 53 do Broodscale, 32
  do Ruby Storm e 20 do Affinity; o Colossus Hammer aparece em 3 listas de Modern
  e duas são do mesmo jogador; os três arquétipos são DIFERENTES entre si. O deck
  entra porque ele o pediu e o peso dele fica dito — aparecer com o mesmo peso dos
  outros nove era mentir-lhe por omissão.
- **O FLOW STATE FICA À ESPERA DO OK DELE** (`por_confirmar`, com a carta-chave à
  vista e a frase a dizer o que falta), e **não** marcado como deck a montar — ele
  disse *"poe-no a espera"*. Em **Pioneer não há staples nem proxies**: medido, o
  Greasefang e o Flow State não partilham uma única carta, e a página **di-lo** em
  vez de mostrar uma tabela vazia (*"uma tabela vazia parece uma avaria"*).
- **A VENDA: não se tocou no motor, e MEXEU por consequência — o número é 43,65 €.**
  Não se mexeu no `venda.py`, nas candidatas nem nos preços. Mas trocar a lista de
  uma caixa muda o que ela ALOCA, e o que está alocado não vai à venda: medido lado
  a lado com o MESMO `vault.db`, **entraram 10 cópias / 43,65 €** na lista de venda
  (4 Fatal Push 8,32 €, 5 Wall of Blossoms 30,65 €, 1 Quirion Ranger 4,68 €, todas
  por a lista nova não as jogar) e **saíram 12**, 8 delas alocadas às caixas (4
  Ill-Gotten Gains, 3 Arcane Denial, 1 Cunning Wish). O total das saídas desceu de
  **376 para 358 cópias**; `venda` 116 c/1 591,62 € → **114 c/1 563,32 €**. A venda
  está **fora de vista** (`venda.mostrar: false`) e **congelada** (trava manual),
  por isso nada sai — e há tempo para ele decidir.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados:** fechar tudo
  **5 972,79 € → 11 122,58 €** e a comprar **245 → 295**. **As dez caixas que ele
  não mandou tocar ficam IGUAIS à percentagem** (as cinco fixas, as três de legacy,
  o standard e a `modern-affinity`); as sete que trocaram mudam porque a lista é
  outra — Stiflenought 100→99 %, UW Replenish 92→93 %, Elves 40→53 %, Oath 71→53 %,
  Enchantress 37→36 %, **IGG 0→33 %**, Pioneer 17→23 %. O salto do *fechar tudo* é
  sobretudo a `premodern-igg` a passar a pedir 75 cartas que antes não pedia.
  **E as cinco caixas fixas estão byte a byte iguais** — a caixa e a lista —,
  comparadas com o HEAD do git num caso de teste.
- **MEDIDO COM O SERVIDOR A CORRER E O JS A SÉRIO:** 12 páginas a 200, **259
  ficheiros de dados a 200, zero falhas**, a aba Decks percorrida até ao **nível do
  deck nas 17 caixas e nos 11 decks dele** — **96 partes, 0 falhas, a mais lenta 3
  ms**; a casca em **62 151 bytes** (tecto 80 KB) e o índice em 114 KB. A 1440 e a
  390 px, **nenhuma página com scroll horizontal**.
- **UM TESTE DE 04/10 À TARDE TEVE A ASSERÇÃO CORRIGIDA, e não mascarada**
  (`test_decks_vista.caso_os_sleeves_contam_as_verdadeiras_e_os_proxies`): afirmava
  `proxies == 8` (cópias) e hoje são **2** a imprimir e 8 cópias, com as duas datas
  no docstring. E o `test_nomes_arquetipo.caso_a_pergunta_do_nome_vive_num_sitio_so`
  **apanhou-me** a ler o `arquetipo_fonte` à mão no `eventos.py`: a coluna tem um
  leitor só (a votação do `nomes`), e o nome que a fonte dá a UMA lista ao lado do
  deck era um segundo nome a discordar do votado. Saiu da proveniência.
- **POR DECIDIR POR ELE, e é o que vale a pena ler primeiro:** (a) as **5 listas
  de Modern** em que o jogador dele difere do que a regra escolheria (`regra_diria`
  no config) — se preferir as da regra, é uma linha; (b) o **Flow State** espera o
  OK dele, e com ele o Pioneer passa a 2 decks marcados; (c) o **standard e o
  legacy** estão sem lista por falta de amostra, e a troca para evento real
  resolvia; (d) as **10 cópias / 43,65 €** que entraram na lista de venda; (e) o
  **7614 (Affinity)** entrou com a lista do Tree42o e a caixa `modern` ficou
  intacta e NÃO marcada — é a única leitura que dá os **10 decks** que ele mediu,
  e é interpretação minha; (f) as **staples** dão 55 contra os 50 dele, e os
  ficheiros dele não estão neste PC para reconciliar.

**UM DECK POR FORMATO, COM VERSÕES POR DENTRO (André, 2026-10-04, à noite, à
letra).** *"vamos fazer uma coisa diferente, a ver como fica"*; *"quero apenas
manter decks que usem Mox Opal, tudo o resto e para vender (em modern)"*;
*"quero ficar com 1 deck e versoes do deck (como opcoes)"*; *"De Modern quero
apenas decks de Mox Opal / De Pioneer quero Apenas decks de Greasefang / de
Standard apenas decks de Bant Airbend / Legacy ainda nao sei"*. **SUBSTITUI O
MODELO DE 18 DECKS** da mesma tarde. Motor em **`mtgvault/versoes.py`**, as duas
regras novas em `mtgvault/fases.py` (`RE`/`RLG`), o registo e o `deck_unico` em
`mtgvault/decks_vista.py`, a página em `decks.py`, o endpoint `POST /api/versao`,
config em `colecao_config.json → decks_por_formato`. Testes em
`tests/test_modelo_versoes.py` (15 casos) e a prova de que chumbam em
`tests/_chumba_versoes.py` (**11 de 11 alvos**, um processo por alvo).

- **A ESTRUTURA:** `modern` → UM deck «Affinity (Mox Opal)» com **4 versões**;
  `pioneer` → UM deck «Greasefang» com **3**; `standard` → «Bant Airbend»
  (ele revê em Janeiro); `legacy` → **POR DECIDIR**, e nada se escolheu nem se
  libertou; **`premodern` fica como está, 6 decks** — ele não lhe tocou, e por
  isso nem aparece no bloco. Um formato que não esteja no `decks_por_formato`
  continua exactamente como estava: é o interruptor, e tem caso de teste.
- **UMA VERSÃO É UM CLUSTER MAIS UMA LISTA QUE ALGUÉM JOGOU, nunca um consenso.**
  É a decisão dele de 04/10 ao fim do dia (*"vamos focar nas decklists baseadas
  em eventos reais"*), e fazer o consenso de cada cluster era ressuscitar a média
  que ele acabava de enterrar nessa mesma noite. Onde a lista já existia,
  **aponta-se para ela** (`deck`) em vez de a duplicar: a versão `izzet-pinnacle`
  **é** a caixa `modern` (a lista de qualificação dele) e a `broodwagon` **é** a
  caixa `pioneer` (Martin_Dominguez, Challenge 32 de 01/10 — conferido: a lista
  dessa caixa é mesmo a `decklist 23333`, do cluster 7583). As outras cinco
  ganharam lista pelo `eventos.escolher`/`fixar`, com a proveniência gravada.
- **AS VERSÕES, medidas** (listas que contam, a 2026-10-04):

  | formato | versão | cluster | listas | lista real |
  |---|---|---|---|---|
  | modern | **Izzet Pinnacle** ← escolhida | 7614 | 20 (20 na janela) | a tua, de qualificação |
  | modern | Weapons Manufacturing | 4380 | 88 (0) | Benny Zeoli · 9-16 · RC · 12/09 · 1 486 j |
  | modern | Cranial Plating | 7525 | 5 (0) | Arcbound_Papi · 5-8 · Challenge 32 · 27/09 |
  | modern | Seachrome | 7527 | 3 (0) | Chris Nguyen · 5-8 · ReCQ · 13/09 · 344 j |
  | pioneer | **Broodwagon** ← escolhida | 7583 | 2 (2) | Martin_Dominguez · Challenge 32 · 01/10 |
  | pioneer | Parhelion | 7309 | 15 (0) | Sakamoto Masaaki · 3-4 · 22/09 · 65 j |
  | pioneer | Mycosynth Gardens | 6482 | 6 (0) | LaceiSuaEsposa · Challenge 32 · 26/09 |

  Escolheu-se a que está **dentro da janela do consenso** nos dois formatos — e
  nos dois ela é a lista que ele já tinha na caixa. O **4380 e o 7614 são a mesma
  deck partida pelo bug dos arquétipos** que a ordem `mtg-top8-por-edicao` vai
  corrigir (88 listas com 0 na janela contra 20 com 20): quando a identidade
  estável existir, as duas versões colapsam numa.
- **O CRITÉRIO DA ORDEM DÁ SETE VERSÕES E NÃO QUATRO — medido, e dito.** *"Nem
  todo o deck que joga Mox Opal é uma versão da Affinity"* está certo e o teste
  (Kappa Cannoneer + Pinnacle Emissary) está certo; o que a ordem não viu é que
  ele passa em **sete** clusters e não em quatro. Medido na base: **20 clusters**
  de Modern jogam Mox Opal (164 listas, mais 17 sem cluster), e passam o teste os
  quatro que ele nomeou **e mais 7400 (2 listas), 7010 (2) e 6491 (1)**, os três
  com Kappa e Pinnacle em **100 %** das listas. Ficaram **fora da escolha e à
  vista**, marcados `passa_criterio`: a leitura dele é que manda, e três clusters
  de uma a duas listas não se metem num deck dele por iniciativa própria.
  Os cinco que a ordem nomeou como «não ficam» confirmam-se todos — o 7394 tem
  Kappa em 1 de 9 listas e Pinnacle em **zero**.
- **E DUAS CORRECÇÕES À PREMISSA, as duas a favor dele:** (a) *"25 listas, 6,9 %
  do formato, repartidas por NOVE arquétipos"* mistura dois universos — **na
  janela são 24 listas** (6,9 % de 350, a percentagem bate) **em 4 clusters**; os
  nove só aparecem olhando para **todas** as listas que contam; (b) dos sete
  nomes que a ordem dá como libertados e perigosos, **quatro já estavam
  protegidos pela R5** (Undercity Sewers, Thundering Falls, Quantum Riddler,
  Meticulous Archive — jogados no último mês) e um pela RD (Solitude). As
  percentagens de Legacy da ordem são da **janela do consenso** (135 listas), e
  é esse o universo que se usou — Wrath of the Skies 16,3 %, Thundering Falls
  12,6 %, Quantum Riddler 11,1 % batem ao décimo.
- **«OUTROS DECKS QUE JOGAM MOX OPAL» É DERIVADO DA BASE, nunca escrito à mão**
  (`versoes.outros_que_jogam`). *"NAO decidas por ele incluir nem excluir
  definitivamente"*: a lista sai a cada corrida, cada entrada diz quantas listas
  tem e a percentagem de cada carta do critério, e as que passam ficam à cabeça.
  Escrita à mão ficava desactualizada no dia em que aparecesse um deck novo — e é
  precisamente o deck novo que interessa ver. Tem caso de teste que semeia um
  cluster novo e exige que ele apareça sozinho.
- **NADA SE APAGA.** Os nove decks de Modern que saem e o UR Aggro de Pioneer
  ficam no config com `_saiu` (data + razão), aparecem no registo com o rótulo
  **«meta, não escolhido»** e **mantêm a lista, a proveniência e as cartas**.
  Repor é tirar-lhes o `_saiu`. Tem caso próprio, que exige que o deck continue
  a contar `tens X de Y` depois de sair.
- **AS DUAS REGRAS NOVAS DA VENDA, e porque é que eram precisas.** Os dez decks
  de Modern de 04/10 à tarde **não protegiam uma única cópia**: não são caixas,
  não têm `copy_allocation`, e por isso a RD nunca os via. Sem mecanismo, *"quero
  apenas manter decks que usem Mox Opal"* não queria dizer nada.
  - **RE · está num deck que escolheste** — o nome está na lista de um deck que
    o modelo guarda. **Todas as versões protegem, não só a escolhida**: são
    opções do mesmo deck, e vendê-las por ele ter hoje a versão B escolhida era
    desfazer a opção. O que a escolha muda é o que ele MONTA (a necessidade, as
    compras, as próprias) — e isso é outra pergunta.
  - **RLG · formato por decidir** — enquanto o Legacy estiver `por_decidir`, uma
    carta que se jogue em ≥ 5 % das listas da janela desse formato **não vai à
    venda**. *"Tudo o resto é para vender"* não pode querer dizer vender as
    staples de Legacy antes de ele escolher o deck de Legacy. **É GLOBAL e não só
    sobre o que este modelo liberta**, e é uma decisão: uma regra que só valesse
    para «os nomes que estavam no modelo de 18 decks» precisava desse conjunto
    congelado no config para sempre, e um conjunto congelado é o que apodrece.
    Assim é sem estado, retém mais, e **desliga-se sozinha** no dia em que ele
    decidir — tem caso de teste nos dois sentidos.
  - **A RLG é a ÚLTIMA de todas as regras, e isso é deliberado.** Posta à frente
    da R5 ficava com o crédito de **203 cópias** que a R5 já segurava de qualquer
    maneira (medido), e o número que ele lê — *"isto fica retido só porque não
    decidi o Legacy"* — vinha inflacionado três vezes. No fim, diz exactamente o
    que se desbloqueia quando ele decidir: **96 cópias / 3 159,19 €**.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados** (`main` contra o
  ramo, `_revisao/medir/comparar.py`, um processo por árvore):

  | | main | ramo |
  |---|---|---|
  | fechar tudo | 11 122,58 € | **11 122,58 €** |
  | a comprar | 295 | **295** |
  | valor da colecção / cartas | 133 354,51 € / 1 678 | **iguais** |
  | as 17 caixas | — | **iguais à percentagem e ao cêntimo** |
  | VENDER | 625 c / 17 963,58 € | **477 c / 13 426,09 €** |
  | protegidas | 1 053 c / 126 804,62 € | **1 201 c / 131 342,11 €** |
  | R5 (30 dias) | 458 c / 11 884,75 € | 381 c / 9 703,84 € |
  | **RE** | — | **129 c / 3 559,21 € / 40 cartas** |
  | **RLG** | — | **96 c / 3 159,19 € / 28 cartas** |

  **A alocação não mexe um número** — o modelo não toca nas `caixas`. Da lista
  VENDER **saem 148 cópias e não entra nenhuma**; a R5 desce 77 porque a RE e a
  RLG apanham essas cópias primeiro (129 + 96 − 77 = 148, ao exemplar).
- **O QUE O MODELO LIBERTA, e a divisão que ele pediu.** O modelo de 18 decks
  cobria **370 nomes**; as 14 versões (8 do modelo + as 6 caixas de Premodern,
  que ele não mexeu) cobrem **233**. Dos 176 nomes que saem, **48 têm cópias
  livres hoje** — 158 cópias. Divididas:
  - **A) joga em Legacy (≥ 5 % da janela) — 13 nomes / 50 cópias — RETIDO** até
    ele decidir o Legacy. Os piores: Orcish Bowmasters 23,0 % (7 cópias), Flow
    State 18,5 % (3), Wrath of the Skies 16,3 % (8), Ocelot Pride 11,1 % (5),
    Guide of Souls, Phelia e Ajani 11,1 % (4 cada).
  - **B) não joga em Legacy — 35 nomes / 108 cópias — candidata sem dúvida.**

  (Os números da ordem — 365/266 nomes, 73 libertados, 26 em Legacy — **não
  reproduzem**: o conjunto dos 18 decks dá 370 e o das versões 233, e 4 dos 7
  nomes que ela nomeia já estavam protegidos pela R5. Os medidos são estes.)
- **A VENDA CONTINUA TRAVADA E ESCONDIDA** (`venda.mostrar: false`, trava
  manual): isto prepara a lista, não a destranca. Nada saiu da base.
- **POR DECIDIR POR ELE:** (a) os **três clusters que passam o critério** (7400,
  7010, 6491) e ficaram fora — incluir é uma linha em `versoes`; (b) o **Standard
  continua sem lista** (o consenso tem 1 lista contra um mínimo de 5) e ele revê
  em Janeiro — trocar para uma lista de evento real resolvia; (c) o corte da
  **RLG** são 5 % e é escolha minha a partir das 135 listas da janela
  (`decks_por_formato._corte_pct`); (d) as **50 cópias de A** ficam retidas até
  ele escolher o deck de Legacy.

**SEMPRE MONTADOS, MESMO COM PROXIES — E O STIFLENOUGHT VOLTA AO LUFFY (André,
2026-10-05, à letra).** *"no Premodern, o Stiflenought e lista do Luffy tambem, o
UW Replenish e que e para procurar"* e *"Esses sao os meus decks principais,
esses quero ter sempre montados, mesmo que com proxies"*. **DESFAZ a parte
rotativa do modelo de 2026-10-04 à tarde para os decks principais** (ver «A ABA
DECKS»): a carta partilhada já não fica FORA do deck à espera da hora de jogar —
cada deck principal está montado em permanência e o que falta leva PROXY. Motor
em `mtgvault/decks_vista.py` (`e_principal`/`sempre_montado`/`marcar_principal`,
`da_pilha`/`tenho_para`, `modo_do_deck`/`modo_efectivo`,
`ordem_das_verdadeiras`/`reparte_verdadeiras`/`disputadas`/`proxies_das_faltas`),
página `decks.py`, endpoint `POST /api/deck-principal`, config em
`caixas[].principal`/`sempre_montado` + `_sempre_montado`. Testes em
`tests/test_sempre_montado.py` (18 casos) e a prova de que chumbam em
`tests/_chumba_sempre_montado.py` (**16 de 16 alvos**, um processo por alvo).
Backup em `data/backups/colecao_config-20261005-2018-antes-sempre-montados.json`
(o `vault.db` não se escreve nesta ordem — a cópia de hoje é a das 06:35 da
ordem anterior). **A venda continua escondida e travada.**

- **O STIFLENOUGHT ERA UM ERRO MEU, E A LISTA DO LUFFY É A MESMA QUE A VIGIA JÁ
  TINHA.** A ordem `mtg-listas-de-eventos` de 04/10 trocou a lista do Luffy pela
  do **Simone Fierro** (1.º do European Championship, 218 jogadores) porque eu
  mandei a regra preferir presenciais com campo grande — e o Stiflenought dele
  vem do jogador que ele SEGUE. A caixa voltou a **`fonte: vigiado`**, `ref:
  "Luffy — Premodern"`, o MESMO caminho do pauper, por isso **acompanha sozinha**
  quando ele mudar a lista.
  - **Conferido antes de usar, e é melhor do que a ordem pedia:** o Luffy tem
    **13 listas** de Premodern na base, **todas com Phyrexian Dreadnought** e
    **todas com o mesmo `content_hash` `ad229680848eaf0e`** — não mudou uma carta
    desde 2026-09-08. A mais recente é mesmo a **23605** (Premodern Challenge 16
    de 2026-10-03), e o **snapshot da vigia (2026-08-02) é IDÊNTICO a ela: zero
    diferenças**. Ou seja o `fonte: vigiado` dá exactamente a decklist que a ordem
    nomeou, e a nota da caixa di-lo com as DUAS datas (*«lista vigiada de
    2026-08-02 — sem mudar desde então, conferida a 2026-10-05»*).
  - **A lista do Fierro não se apagou — e TEVE de mudar de chave.** Ficou em
    `listas_escolhidas._premodern-stiflenought-anterior`, com `_substituida_em`,
    `_substituida_por`, `_razao` e as 10 linhas em que as duas diferem. Deixá-la
    na chave do SLOT era pior do que apagá-la: o `decks_vista._com_proveniencia`
    lê `listas_escolhidas[<slot>].evento` **independentemente da `fonte`**, e a
    ficha da página mostrava *«Simone Fierro · 1.º · 218 jogadores»* por cima das
    cartas do Luffy — a página a mentir sobre a lista por que ele vai sleevar, que
    é o pior resultado possível. Uma chave com `_` nunca é um `ref` de caixa. Tem
    caso próprio e dois alvos no `_chumba`.
  - O **`premodern-replenish` fica a procurar lista pelo meta**, como ele mandou:
    continua com a do **Alexey Kuznetsov** (5-8 de 218, European Championship,
    05/09), escolhida pela regra entre 64 candidatas, e é ainda a melhor.
- **A REGRA NOVA, e as três consequências.** `caixas[].principal` quer dizer
  *"fica sempre montado"*: (a) os proxies de um deck deixam de ser as partilhadas
  e passam a ser **tudo o que falta**; (b) a **cópia verdadeira já não roda** —
  dois decks que pedem 4 Swords com 4 em casa dão um deck com as verdadeiras e
  outro com 4 proxies, e a página diz **qual é qual**; (c) a necessidade destes
  decks é a **SOMA**, porque têm de estar completos ao mesmo tempo.
- **O `cartas_partilhadas` NÃO se apagou, nem o código das próprias e
  partilhadas** (ordem dele). O eixo novo é por CAIXA e **ganha ao modo do
  grupo**; tirar a marca `principal` devolve o formato ao modelo de 04/10, e a
  página **diz qual era o modo do grupo** e que a regra não se perdeu — senão
  parecia o config a ter mudado. Tem caso de teste nas duas direcções.
- **QUEM DECIDE É UMA CHAVE SÓ: `principal`.** O `sempre_montado` existe por
  caixa e, escrito, ganha — mas **não se escreveu em caixa nenhuma**: sem ele,
  vale o que o `principal` disser. Duas chaves com o mesmo valor em doze caixas
  eram duas verdades para a mesma pergunta, que é exactamente o campo `decisao`
  que ele mandou apagar a 02/10 (*"São duas verdades para a mesma pergunta"*). A
  razão fica escrita no config (`_sempre_montado`), que é um ficheiro para ser
  lido por uma pessoa.
- **QUAIS SÃO OS PRINCIPAIS É INTERPRETAÇÃO MINHA, E ESTÁ DITO.** Ele disse
  *"esses"* depois de eu lhe listar as **12 caixas que TÊM LISTA**; ficaram de
  fora as quatro a 0 % (`standard`, `legacy-aluren`, `legacy-welder`,
  `legacy-artifacts-blue`) e a `modern-affinity` desactivada. Por isso a marca é
  **EDITÁVEL na página** (um visto por caixa, `POST /api/deck-principal`, só no
  8771) e a interpretação está escrita no `_sempre_montado` — se estiver errada,
  vê-se de onde veio e corrige-se num toque. Uma caixa **desactivada** ou **sem
  lista** não entra como escolhida mesmo que a marca lá esteja: não há nada para
  montar nem para imprimir.
- **UM DECK PRINCIPAL CONTA COMO ESCOLHIDO, mesmo sem o «quero montar este».** As
  quatro caixas que ele tem **fisicamente montadas** — os dois de cEDH, o Duel
  Commander e o Pauper — nunca foram marcadas em `decks_montar` (ele marcou as de
  Premodern e o Pioneer a 04/10), e a página dizia *«0 decks que queres montar»*
  sobre decks sleevados na estante. `principal: true` é uma afirmação mais forte
  do que aquela marca; a lista de escolhidos é **uma só** e sai do `relatorio`.
  Consequência: o cEDH, o Duel Commander e o Pauper **passam a ter sleeves e
  proxies**, que nunca tinham tido (`sleeves` era `None` nos formatos de cartas
  dedicadas).
- **44 DAS 272 CÓPIAS EM PROXY ERAM TERRENOS BÁSICOS, e isto é o achado do dia.**
  A pilha de Unhinged **nunca foi uma linha da `copies`** — entra por contagem
  declarada (02/10) — e por isso a `marcas.posse` responde **zero** a um Island.
  Enquanto isso só alimentava uma percentagem era inofensivo; no momento em que
  os proxies passam a ser as FALTAS, mandava-o imprimir **17 Island** para o
  Stiflenought, que o `loadout` dá a **100 %** exactamente por esta isenção. A
  pergunta responde-se com a **MESMA função do motor**
  (`loadout.basicas_a_granel`, via `decks_vista.da_pilha`) e não com uma lista
  nova: as **Snow-Covered** não existem em Unhinged, logo essas continuam a ser
  falta a sério e levam proxy. Depois: **zero proxies de básicas**. E a aba Decks
  deixou de contradizer o motor — Stiflenought **79 % → 100 %** e Pauper **→
  100 %**, que é o que o `loadout` já dizia. A posse desta página vive agora numa
  primitiva só (`tenho_para`), usada pela conta do deck, pelas faltas, pelas
  staples e pela repartição: a quarta era a que se esquecia das básicas. O tile de
  uma básica diz **«da pilha de básicas»** e **não tem `+`/`−`** — ali o botão não
  mudava número nenhum, e um botão que não faz nada é pior do que botão nenhum.
- **QUEM FICA COM AS VERDADEIRAS: a `prioridade` da caixa**, que é a ordem que ele
  já escreveu no config (critério dele; muda-se lá, não no código), com o nome e o
  id a desempatar — determinista, pela razão do desempate alfabético dos nomes de
  02/10: a lista que ele imprime não pode trocar de deck de um dia para o outro
  sem nada ter mudado. **Não é a alocação do `loadout`**, e a diferença é
  deliberada: aqui reparte-se por NOME sobre a posse que ele marcou, sem regras de
  material, para responder a *"qual destes decks fica com a carta a sério"*; o
  `loadout` reparte cópias FÍSICAS por caixas com regras de língua, acabamento e
  edição, para dizer o que **comprar**. As **staples a guardar à parte** deram
  lugar às **cartas disputadas** nos formatos sempre montados: a pilha à parte
  deixou de existir (cada deck tem a carta dentro), mas *"em quantos decks entra"*
  continua a valer e é ali que ele vê o custo em papel.
- **OS PROXIES POR DECK, ANTES E DEPOIS** (medido na base de 2026-10-05, o mesmo
  `vault.db`; «cartas a imprimir / cópias»):

  | deck | antes (rotativo) | depois (sempre montado) | % |
  |---|---|---|---|
  | Pioneer — Greasefang | 0 / 0 | **27 / 56** | 24 → 25 % |
  | Cloud cEDH | — | **20 / 20** | 83 % |
  | Cloud (Duel Commander) | — | **19 / 19** | 81 % |
  | Ill-Gotten Gains | 13 / 33 | **18 / 35** | 68 → 73 % |
  | Oath of Druids | 14 / 30 | **18 / 33** | 68 → 71 % |
  | Enchantress | 14 / 35 | **16 / 33** | 60 → 67 % |
  | Elves | 5 / 19 | **12 / 23** | 60 → 71 % |
  | Blue Farm | — | **3 / 3** | 97 % |
  | Modern — Pinnacle Affinity | 0 / 0 | **2 / 3** | 95 → 96 % |
  | UW Replenish | 14 / 52 | **2 / 3** | 89 → 96 % |
  | Stiflenought | 9 / 32 | **0 / 0** | 79 → **100 %** |
  | Affinity (Luffy) | — | **0 / 0** | **100 %** |
  | **TOTAL** | **69 / 201** | **137 / 228** | |

  **São +68 cartas a imprimir e +27 cópias** — o número de FOLHAS quase duplica, e
  é isso que a decisão custa. Os quatro decks que não tinham conta nenhuma (os
  dois de cEDH, o Duel Commander e o Pauper) são 42 das 68. Em sentido contrário,
  o **UW Replenish cai de 14 para 2** e o **Stiflenought de 9 para 0**: no modelo
  rotativo uma carta partilhada levava proxy mesmo quando ele a tinha, e agora só
  leva o que falta mesmo.
- **MEDIDO LADO A LADO, em QUATRO passagens, para separar as duas metades da
  mudança** (o mesmo `vault.db` em todas; `_revisao/_rev_medir.py`,
  `_rev_isolar.py`):
  - **A (main) → B (código novo, config intacto): IDÊNTICO**, byte a byte no JSON
    de medição — fechar tudo 11 075,43 €, 295 a comprar, as 17 caixas. O
    interruptor está **desligado por omissão**: sem uma marca `principal`, nada
    muda.
  - **A → D (as marcas `principal`, a lista ANTIGA): IDÊNTICO ao cêntimo e caixa
    a caixa.** É a prova de que a marca **não toca no motor** — nem o `loadout`
    nem o `fases` lêem `principal` ou `decks_montar`.
  - **A → C (o depois a sério):** fechar tudo **11 075,43 € → 11 043,88 €**
    (**−31,55 €**), a comprar **295 → 293**, e **só DUAS caixas mexem** —
    `premodern-stiflenought` (99 % → **100 %**, comprar 1 → 0, 20,35 € → 0) e
    `premodern-enchantress` (36 % → **37 %**, comprar 48 → 47, 1 037,39 € →
    1 026,19 €). **As outras 15 ficam iguais ao cêntimo e à percentagem.** Tudo
    isto é a troca da LISTA do Stiflenought (as duas diferem em 10 linhas) e não
    a regra dos proxies — e o salto da Enchantress é o `prioridade_por: "pct"` do
    grupo de Premodern a reordenar a alocação, porque a percentagem da caixa
    mudou.
- **MEDIDO COM O SERVIDOR A CORRER E O JS A SÉRIO** (`publicar.gerar` para uma
  pasta de prova — que chama a Galeria com `historico=False` e por isso **não
  escreve na colecção** —, servida por HTTP, com `tests/abrir_pagina.js` a fazer
  os `fetch` ao servidor): as **14 páginas a 200**, os **273 ficheiros de dados a
  200**, o `deckboxes.js` a 200, **zero** mensagens de erro de dados; a aba Decks
  percorrida **formato a formato e até ao nível do deck nos oito formatos**, com
  os blocos novos conferidos no HTML que o JS desenhou (*«Sempre montados»*,
  *«Cartas em mais do que um deck»*, *«Proxies a imprimir»*, *«★ principal»*, *«da
  pilha de básicas»*); e a 1440 e a 390 px **nenhuma página com rolamento
  horizontal**. Ler o HTML desenhado é a única forma de ver isto — a Fase 3 esteve
  quatro dias a dizer *«não consegui carregar os dados»* com a página a responder
  200.
- **DOIS TESTES DE 04/10 TIVERAM A ASSERÇÃO CORRIGIDA, e não mascarada**
  (`test_listas_de_eventos`): o `caso_as_cinco_caixas_fixas_ficaram_intactas`
  comparava a caixa INTEIRA, chave a chave, com o HEAD do git — e por isso
  chumbava no dia em que uma caixa fixa ganhasse uma marca que **não mexe na
  lista**; passou a trancar o que a ordem de 04/10 queria proteger (`fonte`,
  `ref`, `assinatura`, `balde` e a lista, essa byte a byte). E o
  `caso_as_caixas_trocadas_tem_todas_proveniencia_completa` passou de **sete para
  seis** caixas, porque o Stiflenought saiu desse conjunto — com uma asserção
  nova a exigir que ele esteja mesmo a seguir o Luffy, senão a correcção deixava
  de trancar nada. As duas datas ficaram nos docstrings.
- **POR DECIDIR POR ELE:** (a) **quais são os principais** — são as 12 com lista,
  por interpretação minha, e corrige-se com um visto; (b) o **Pioneer passa a 27
  cartas / 56 cópias em proxy** (está a 25 %), que é mais de metade do deck em
  papel — se preferir esperar pelas compras, é tirar-lhe a marca; (c) as **quatro
  caixas a 0 %** não são principais e por isso continuam sem proxies e sem
  sleeves; (d) o **`sempre_montado`** por caixa existe e não está escrito em
  nenhuma — é a porta para um deck principal que ainda rode.

**MONTAR E PROTEGER SÃO DUAS PERGUNTAS: O CRITÉRIO DO MOX OPAL É INCLUSIVO
(André, 2026-10-05, à letra).** *"quando digo as decklists que jogam Mox Opal, e
porque assim ficamos com uma lista de cartas que eu gostaria de nao vender, tudo
o resto e «seguro» vender"* e *"aplica o mesmo para Legacy, assim jogo Mox Opal
nos 2 formatos"*. **CORRIGE A LEITURA DE 04/10 À NOITE**, que escolheu as quatro
versões da Affinity a assumir que a lista de decks de Mox Opal era um conjunto a
**MONTAR**. É para **PROTEGER**, e isso inverte o critério: passa a ser
**INCLUSIVO e não selectivo**. Motor em `mtgvault/versoes.py`
(`limiar_listas`/`protege_todas`/`formatos_inclusivos`/`listas_da_carta`/
`contagem_por_carta`/`nomes_protegidos`/`listas_do_formato`/`texto_rp`) e a
regra **RP** em `mtgvault/fases.py` (`curva_limiar`/`resumo_mox`); config em
`decks_por_formato` (`_limiar_listas` + `criterio.protege_todas`). Testes em
`tests/test_mox_proteger.py` (12 casos) e a prova de que chumbam em
`tests/_chumba_mox.py` (**10 de 10 alvos**, um processo por alvo). Backup em
`data/backups/vault-2026-10-05-mox-proteger.db` (104,3 MB, `integrity ok`).
**A VENDA CONTINUA ESCONDIDA E TRAVADA** — isto prepara a lista, não a destranca.

- **AS DUAS PERGUNTAS, e nunca se juntam.** **MONTAR** é a versão escolhida (em
  Modern continuam a ser as quatro da Affinity: *"o deck principal é Affinity
  sem dúvida"*), e quem decide quais os clusters que são versões é o
  `criterio.exige` (Kappa Cannoneer + Pinnacle Emissary). **PROTEGER** é
  **todas** as listas que jogam a carta-chave, de qualquer arquétipo. Juntá-las
  custa caro nos dois sentidos — ou monta decks que não quer, ou vende cartas
  que quer —, por isso são dois conjuntos distintos **e dizem-no no ecrã**: a
  aba Decks leva o bloco *«Proteger ≠ montar»* e os «outros decks que jogam Mox
  Opal» passaram a dizer *«· protege»* ao lado do *«não é versão»*.
- **Os cinco que tinham ficado de fora VOLTAM a contar** (Scrabbling Claws,
  Jace/Song of Creation, Flame of Anor, Hammer Time, Erayo) — para a protecção,
  não para a montagem. Tem caso de teste nos dois sentidos.
- **O LEGACY ENTRA e DEIXOU DE ESTAR `por_decidir`**, com o mesmo critério. A
  consequência directa é que a **RLG deixou de disparar** — e isso não é uma
  perda: era exactamente para isto que ela foi escrita para se desligar sozinha.
  Fica no código e volta no dia em que houver outro formato por decidir (tem
  caso de teste nos dois sentidos). O `por_decidir` antigo ficou arquivado em
  `legacy._por_decidir_antes`, com a data e como se repõe.
- **O UNIVERSO DAS LISTAS É O MAIS LARGO: a janela do consenso, SEM o filtro de
  tier.** É a mesma excepção — e a mesma razão — da R5: *sub-contar numa regra
  de protecção é VENDER uma carta que ele precisa*; um 5-0 de league que jogue
  Mox Opal é precisamente o sinal que interessa. **E é o universo em que os
  números que ele mediu batem ao exemplar**: **modern 25 de 364 (6,9 %)**,
  **legacy 23 de 171 (13,5 %)**, **vintage 18 de 64 (28,1 %)**. Com o filtro de
  tier dariam 24 e 17 — foi assim que se descobriu qual era o universo dele.
  Tem caso de teste (uma liga que joga a carta-chave tem de contar).
- **O LIMIAR É DELE E NÃO MEU** (`_limiar_listas`, hoje **1**, que é a letra do
  que ele pediu). A página mostra a curva entre 1 e 2 com os DOIS números da
  `curva_staples` — `a_mais` (o que a RP protege por cima de tudo o resto) e
  `sozinha` (o que protegeria se a R5 e a R5b não existissem) —, porque uma
  coluna só lia-se como *"o limiar não importa"* quando o que se passa é que
  outra regra chegou primeiro. **Medido:** passar de 1 para 2 liberta **37
  cópias / 1 820,63 €**, que são exactamente as protegidas por **uma única**
  lista (15 linhas). Não se escolheu por ele.
- **O limiar conta a SOMA entre formatos e não o máximo**: as 25 de Modern e as
  23 de Legacy são 48 listas de Mox Opal, e uma carta que esteja numa de cada
  está em duas delas. É a leitura literal de *"em quantas listas"* e é a mais
  conservadora. **Este caso não existia e foi o `_chumba` que o apanhou** — eu
  afirmava a regra na docstring e não havia teste que a trancasse.
- **A ORDEM DA RP, e as duas decisões que ela carrega.** Vem **depois da R2 e da
  R3**, por ordem dele (*"as ShockLands e FetchLands continuam fora por regra e
  nao por este criterio"*): uma fetchland que apareça numa lista de Mox Opal
  continua a dizer «R3 · fetchland», e se amanhã o critério mudar ela continua
  protegida. Vem **antes da R5**, ao contrário da RLG — ali o fim existia para o
  número não vir inflacionado, aqui é o oposto do que serve, porque é o critério
  que ele acabou de definir e o que ele quer ler é *«o que é que a regra do Mox
  Opal protege»*. A inflação não fica escondida: a página mostra as duas
  colunas. **Consequência a saber: as 5 Bayou que ele deu como «protegidas por
  uma lista só» não aparecem na RP** — as duais saem pela **R1**, que é a
  primeira e é exclusiva, e era isso que a ordem dele pedia.
- **O QUE O LEGACY ARRASTOU, medido:** **36 cartas / 102 cópias / 4 555,25 €**
  protegidas **só** por listas de Legacy — Cabal Therapy 1 374,66 €, The One
  Ring 804,25 €, Orcish Bowmasters 420,56 €, Chrome Mox, Lotus Petal, Seat of
  the Synod. **As duais e a Reserved List caras que os decks de artefactos de
  Legacy jogam já estavam protegidas pela R1 e pela R4**, que vêm à frente — por
  isso aparecem com esse motivo e não com este, e o número da RP é mais pequeno
  do que a ordem previa. A página di-lo, em vez de o deixar parecer uma omissão.
- **O VINTAGE NÃO ENTROU, e é decisão dele.** Tem **18 das 64 listas da janela
  (28,1 %)** a jogar Mox Opal — a percentagem mais alta dos três formatos — e
  ele não o pediu. Não está no `decks_por_formato`, logo não protege nada;
  acrescentá-lo é uma entrada no config.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados** (worktree em
  `_revisao/main-1005`):

  | | main | ramo |
  |---|---|---|
  | fechar tudo · a comprar | 11 122,58 € · 295 | **iguais** |
  | as 17 caixas | — | **iguais à percentagem e ao cêntimo** |
  | VENDER | 209 l / 477 c / 13 426,09 € | **217 l / 507 c / 13 911,99 €** |
  | NÃO VENDER | 573 l / 1 201 c / 131 342,11 € | **565 l / 1 171 c / 130 856,21 €** |
  | R5 (30 dias) | 381 c / 9 703,84 € | 271 c / 6 243,72 € |
  | RLG | 96 c / 3 159,19 € | **0 — desligou-se sozinha** |
  | **RP** | — | **176 c / 6 133,41 € / 63 cartas** |
  | R1 · R2 · R3 · R4 · RD · RE · R5b | — | **iguais** |

  **A alocação não mexe um número.** O delta explica-se à cópia e ao cêntimo: a
  RLG (96 c) e a R5 (110 c) libertam 206 cópias, a RP apanha 176, e as **30**
  que sobram são exactamente o que a lista VENDER cresce (+485,90 €, que é
  6 619,31 − 6 133,41). **Correcção à previsão da ordem:** ela dizia que isto
  *«NÃO libertou mais para vender, trocou o que está protegido»* — trocou quase
  tudo, e libertou 30 cópias / 485,90 € líquidos.
- **OS NÚMEROS DE CÓPIAS E EUROS DA ORDEM NÃO REPRODUZEM, e as contagens de
  listas reproduzem.** As três contagens de listas batem ao exemplar (25 / 23 ·
  13,5 % / 18 · 28,1 %); os totais — *«regra 87 c / 11 317,46 €»*, *«não vender
  222 l / 568 c / 40 869,17 €»*, *«seguro vender 270 l / 579 c / 14 019,45 €»* —
  não saem de nenhum recorte do motor. Procurou-se: o **87** é exactamente as
  cópias de shock/fetchlands **fora das caixas**, o que diz que o universo era
  esse, mas nenhuma régua de preço (nem `preco_da_copia`, nem `card_price`) dá
  11 317,46 € para essas 87, e nenhuma partição dá 568/579. Os do motor são os
  da tabela acima, e o *seguro vender* fica a **107,46 €** do que ela previa.
- **Medido com o servidor a correr e o JS a sério:** as **14 páginas** e os
  **264 ficheiros de dados a 200**, zero erros de dados; o JS desenhou nas três
  páginas com JS (Arrumação 6 contentores, Decks 4, Deckboxes 16); a 1440 e a
  390 px **nenhuma página com scroll horizontal**. Bateria toda verde (91
  ficheiros). O round-trip do config pelo `configio.escrever` devolve-o **igual
  byte a byte** — e apanhou uma linha minha escrita à mão fora da forma canónica.
- **POR DECIDIR POR ELE:** (a) o **limiar** — a 1 cumpre-se a letra, a 2
  libertam-se 37 cópias / 1 820,63 €; (b) o **Vintage**, que tem a percentagem
  mais alta e ficou fora; (c) os **três clusters** que passam o critério de
  montagem e ficaram fora das versões (7400, 7010, 6491) — continuam a
  **proteger** na mesma, que era a dúvida que esta ordem fechou; (d) o
  **Standard continua sem lista** (consenso com 1 lista contra um mínimo de 5).
  **[A (c) FECHOU-SE a 2026-10-05, ao fim do dia: ele respondeu que entram
  TODOS, e o conjunto deixou de ser uma lista de ids — ver a secção a
  seguir.]**

**O MODERN SÃO TODOS OS DECKS DE MOX OPAL, E O CRITÉRIO É PERMANENTE (André,
2026-10-05, ao fim do dia, à letra).** *"no Modern, a unica coisa e que quero os
decks que joguem Mox Opal, seja affinity, seja grinding station, seja outra
coisa qualquer"*. **FECHA a dúvida que eu tinha deixado aberta** na ordem de
05/10 de manhã, onde separei quatro versões da Affinity pelo `criterio.exige`
(Kappa Cannoneer + Pinnacle Emissary) e pus cinco arquétipos *«de fora, à
espera de confirmação»*: **ele confirmou o CONTRÁRIO do que lhe propus.** Em
Modern a escolha passou a ser a MESMA pergunta que a protecção — um critério
só, *joga Mox Opal*. Motor em `mtgvault/versoes.py`
(`versoes_todas`/`versoes_derivadas`/`clusters_da_carta`/`principal`/
`id_derivado`, o `escolher(..., validas=)` e o `outros_que_jogam` vazio num
formato derivado), vista em `decks_vista.deck_unico`, página em `decks.py`,
endpoint `POST /api/versao`; config em `decks_por_formato.modern.criterio.
versoes_todas`. Testes em `tests/test_opal_todos.py` (13 casos) e a prova de que
chumbam em `tests/_chumba_opal_todos.py` (**12 de 12 alvos**, um processo por
alvo). **A venda não se tocou.**

- **O CONJUNTO DEIXOU DE SER UMA LISTA DE `archetype_id` A MARTELO**, e era este
  o defeito que a ordem nomeia: *"se o criterio estiver implementado como uma
  lista de archetype_id a martelo, muda-o para a condicao «tem Mox Opal na
  lista», senao daqui a uma semana ha um deck de Mox Opal de fora e ninguem
  repara."* Estava mesmo assim — as quatro versões eram quatro ids escritos no
  config. Hoje o conjunto sai da BASE (`versoes_derivadas`): é versão **todo** o
  cluster que jogue a carta-chave na janela, e um arquétipo novo **entra sozinho
  na corrida em que aparecer**. O config ficou com as **anotações** — o nome, o
  ponteiro para o deck que guarda a lista, a marca `principal` e a memória das
  conhecidas. Tem caso próprio, que semeia um cluster novo e exige que ele
  apareça sem se tocar no config.
- **OS NÚMEROS DELE REPRODUZEM AO EXEMPLAR**, medidos na base com a janela de
  29/09 e **sem o filtro de tier** (o mesmo universo da RP — é o *"um critério
  só"* dele à letra): **30 das 412 listas de Modern jogam Mox Opal (7,3 %)**,
  em **7614 com 25** (a Affinity dele), **7697 com 2**, **7622 com 1**, **7456
  com 1** e **1 lista sem arquétipo**. Uma correcção de vocabulário, e importa:
  ele diz *"em 5 arquetipos"* e são **4 clusters e uma lista que o agrupamento
  ainda não identificou** — essa conta-se e diz-se e **nunca vira versão**,
  porque uma versão precisa de um id estável. A fonte dá-lhe nome
  (*«Song of Creation»*, mtgtop8, Thiago Meneghin, 01/10) e a página mostra-o.
- **A `exige` NÃO SE APAGOU: foi para `_exige_antes`**, com a data e a razão (a
  regra de 09/09). Deixou de decidir quem é versão e **não se deixou lá uma
  chave a mentir** — repor é devolvê-la ao `criterio` e tirar o `versoes_todas`.
  O que ficou dela foi a noção de deck **PRINCIPAL**, que passou a ser uma
  **marca explícita** (`versoes[].principal`, na Affinity: *"o deck principal e
  Affinity sem duvida"*) em vez de um teste sobre as cartas. **É um eixo
  distinto da versão ESCOLHIDA** — a escolhida muda com um toque, a principal é
  a identidade do deck — e tem caso de teste a exigir que trocar uma não troque
  a outra.
- **O `versoes_todas` É CHAVE PRÓPRIA E NÃO O `protege_todas`**, e isso é
  deliberado: o **Legacy** é inclusivo para a protecção e tem `versoes: []`
  porque ele disse que *nada se escolheu para MONTAR em Legacy*. Pendurar isto
  no `protege_todas` dava-lhe **oito** versões que não pediu. Verificado na
  página: o Legacy e o Pioneer ficaram exactamente como estavam, a caixa dos
  «outros» incluída. Tem caso de teste nos dois sentidos.
- **A CAIXA DOS «OUTROS DECKS QUE JOGAM MOX OPAL» DESAPARECEU do Modern** — era
  ela que guardava os cinco «à espera de confirmação», e num formato derivado
  não há «outros»: quem joga a carta É uma versão. **Fica inteira para o
  Pioneer**, onde ele nomeou as três à mão. Deixá-la nos dois punha o mesmo
  arquétipo a aparecer como versão **e** como *«não é versão»*, no mesmo ecrã.
- **O GRINDING STATION: ele deu-o como exemplo e TEM ZERO LISTAS desde 29/09**,
  em qualquer formato (medido). Entra como **versão CONHECIDA** e não como
  actual: a página tem **dois grupos** — *«A jogar-se agora — 4»* e
  *«Conhecidas, sem listas na janela — 4»* —, e a linha dele diz **«zero listas
  na janela · 9 antes dela»** a amarelo. Nem se esconde (era mentir por
  omissão), nem aparece ao lado das actuais (era mentir por igualdade). **E os
  dois grupos não são um remendo para ele**: as **três** versões que já lá
  estavam (Weapons 85 listas, Cranial 5, Seachrome 3) estão na MESMA situação —
  zero na janela — e isso nunca tinha sido dito.
- **O NOME «Grinding Station» É DELE E CONFERE-SE NA BASE.** As 14 listas de
  Modern com Grinding Station jogam **todas** Mox Opal, e repartem-se por
  **7394 (9), 7527 (2), 7341 (1)** e 2 sem cluster (que o mtgtop8 chama *«Emry
  Grinding Cam»*). O maior é o **7394**, e **era um dos cinco que a minha
  leitura de 04/10 punha de fora** (a etiqueta dele é *«Scrabbling Claws /
  Minamo / Sewer-veillance Cam»*): as 9 listas dele jogam a carta a **100 %**.
  A correcção dele está certa e prova-se. **E há uma coisa que vale a pena
  saber: o deck registado que ele lembra** (`decks` 2, *«auto: mtgo Tree42o
  2026-09-28»*) é a lista **22659**, que cai no **7527** — ou seja o Grinding
  Station **já era meia versão**, debaixo do nome *«Seachrome»*, que não diz
  isso. Não se renomeou por iniciativa própria; ficou dito no config.
- **NÃO SE FIXOU LISTA AO GRINDING STATION, de propósito**: a mais recente é de
  28/09, **um dia antes** da janela. Fixá-la era apresentar como deck a montar
  uma lista que o formato de hoje já não viu — e é o oposto do que ele mandou
  (*"nao o inventes como actual"*).
- **AS TRÊS VERSÕES NOVAS DA JANELA NÃO LEVARAM NOME INVENTADO.** O 7697, o
  7622 e o 7456 **não têm nome da fonte nenhum** (zero votos no
  `arquetipo_fonte`): mostram a **etiqueta do agrupamento**, com um chip
  *«etiqueta»* ao lado a dizer o que é. *"Um nome inventado com o mesmo aspecto
  de um nome verdadeiro"* é o que custou três erros na semana de 02/10. Tem
  caso de teste: o nome do config ganha, depois o da fonte, e a etiqueta é a
  última e di-lo.
- **QUEM RESPONDE PELO NOME CONTINUA A SER O `mtgvault.nomes`, e foi um teste
  que me apanhou.** Escrevi a consulta do nome das listas sem cluster a ler o
  `decklists.arquetipo_fonte` à mão, e o
  `test_nomes_arquetipo.caso_a_pergunta_do_nome_vive_num_sitio_so` chumbou com
  `versoes.py:477` — exactamente como apanhou o `eventos.py` a 04/10. Hoje a
  pergunta passa pelo `nomes.nome_das_listas`, que é a votação de 02/10.
- **O `escolher` PASSOU A ACEITAR AS VERSÕES DERIVADAS** (`validas=`), e sem
  isso a funcionalidade não servia de nada: a maior parte delas não está escrita
  no config, e validar só contra o config recusava com **409** um clique numa
  versão que a página acabou de desenhar. Quem passa a lista é o `webapp` (que
  tem ligação à base); **sem ela vale o config**, que é o que os formatos de
  lista fixa querem — e há caso de teste para as duas pontas, mais uma versão
  inventada que continua a ser recusada.
- **O MOTOR NÃO MEXEU UM NÚMERO, e foi medido lado a lado com o MESMO
  `vault.db`** (worktree em `_revisao/main-opal`): fechar tudo **11 043,88 €**,
  **293** a comprar, as **17 caixas** iguais à percentagem e ao cêntimo, as nove
  saídas da venda iguais (venda 366 c, protegidas 148 c, `rl_sem_historico`
  98 c, `guardar` 1 c), candidatos e protegidas iguais, **RE e RP com os mesmos
  nomes**. A **única** diferença no relatório inteiro é o `ids_que_ficam` a
  ganhar `versao:modern:grinding-station` — e esse id **não tem lista fixada**,
  por isso não acrescenta um único nome à RE. Tem caso de teste a trancá-lo:
  *uma versão derivada não entra na RE*; quem a protege em Modern é a RP.
- **DOIS DEFEITOS APANHADOS A LER O HTML QUE O JS DESENHOU**, e não a
  raciocinar — é a lição da Fase 3, que esteve quatro dias a dizer *«não
  consegui carregar os dados»* com tudo a responder 200: (a) o Grinding Station
  vinha com o botão **«ver ▶»** a apontar para um deck que **não existe** no
  registo (não tem lista), e um botão que não leva a nada é pior do que botão
  nenhum — o `deck` só sai quando o registo o tem; (b) uma versão sem lista
  fixada aparecia no registo como **deck de 0 %**, que é a lição da
  `modern-affinity` de 04/10 (lê-se como um deck que lhe falta tudo, quando o
  que se passa é que não há lista nenhuma). Aparece no selector de versões, que
  é onde a decisão se toma.
- **O TECTO DA CASCA SUBIU DE 80 PARA 88 KB, com a medida escrita** — e é a
  primeira vez, porque a folga de 60 % de 04/10 durou um dia e meio. Medido com
  o mesmo gerador dos dois lados: **80 186 → 84 379 bytes** em disco e
  **24 422 → 25 829 em gzip**, ou seja **+1,4 KB no telemóvel dele** (é o gzip
  que mede o que ele descarrega; o Pages serve comprimido). Apertou-se o texto
  primeiro (268 bytes), e o resto é o que a ordem pede. **A folga encolheu de
  60 % para 7 %, e isso é o aviso que ficou escrito no `decks.TECTO_CASCA`: a
  próxima ordem que acrescente JavaScript aqui tira-o para um `decks.js` com
  hash no `?v=`**, como a Deckboxes fez a 18/09, em vez de subir o tecto outra
  vez. Subi-lo três vezes é não ter tecto.
- **O `configio` ganhou um `texto(cfg)`**, extraído do `escrever`, para a forma
  do `colecao_config.json` se poder **conferir** sem tocar no disco — e o caso
  novo compara-o com o ficheiro, byte a byte, pelo próprio `escrever` (é ele que
  faz a tradução de fim de linha do Windows; comparar com o `texto` cru dava
  vermelho em todas as linhas por causa do `\r`). O diff do config são **29
  inserções e 11 remoções**.
- **Medido com as páginas servidas por HTTP e o JS a sério** (`publicar.gerar`
  para uma pasta de prova, que chama a Galeria com `historico=False` e por isso
  **não escreve na colecção**): as **14 páginas** geradas, **zero** mensagens de
  erro de dados, e a aba Decks percorrida até ao nível do formato em Modern,
  Pioneer e Legacy com os blocos novos conferidos no HTML desenhado — *«Um
  critério só: joga Mox Opal»*, *«A jogar-se agora — 4»*, *«Conhecidas, sem
  listas na janela — 4»*, quatro *«zero listas na janela»*, o chip **principal**,
  três chips **etiqueta** e a linha *«Mais: 1 lista que o agrupamento ainda não
  identificou (a fonte: «Song of Creation») … 11 arquétipos (17 listas) jogaram
  Mox Opal antes da janela»*. Bateria toda verde.
- **POR DECIDIR POR ELE:** (a) os **11 arquétipos / 17 listas** que jogaram Mox
  Opal **antes** da janela ficam contados e **não listados** — quinze clusters
  de uma lista cada, de antes do Reality Fracture, não são quinze versões do
  deck dele; um que volte a aparecer entra sozinho, e se quiser vê-los é uma
  linha; (b) o **7527 continua a chamar-se «Seachrome»** e é ele que tem o deck
  registado do Grinding Station — renomeá-lo é decisão dele; (c) o **Grinding
  Station fica sem lista fixada** (a mais recente é de um dia antes da janela);
  (d) as três versões da janela **mostram a etiqueta** porque a fonte não lhes
  dá nome — se quiser nomeá-las, é o `nome` da anotação.

**TODOS OS TORNEIOS EM MODERN: AS LIGAS E OS PRESENCIAIS PEQUENOS (André,
2026-10-05, ao fim do dia, à letra).** *"para modern, apenas os decks de Mox
Opal, procura todos os torneios ! incluindo ligas, torneios presenciais"*. A
primeira metade é a secção de cima; esta é a SEGUNDA — abrir as FONTES de
Modern. Motor em `mtgvault/sources.py` (`PAUSA_MTGO`/`_get_mtgo`,
`harvest_mtgo(..., incluir_hoje=)`, `TIER_LIGA`/`sql_sem_ligas`/`conta_ligas`),
`mtgvault/versoes.py` (`listas_do_formato` com `sem_ligas`/`ligas`, e
`_orfas`/`anotacoes_orfas`), config em `metagame_fontes.modern`; CLI
`py -m mtgvault.cli harvest --days N --format modern [--hoje]`. Testes em
`tests/test_ligas_modern.py` (19 casos) e a prova de que chumbam em
`tests/_chumba_ligas.py` (**12 de 12 alvos**, um processo por alvo). Backup em
`data/backups/vault-2026-10-05-ligas-modern.db` (96,6 MB, `integrity ok`).
**A venda continua escondida e travada.**

- **AS LIGAS NÃO EXISTIAM DE TODO EM MODERN**, e por isso isto não se resolvia a
  consultar a base: **zero** listas com tier `League` em toda a história, contra
  **125** em `duel-commander` — o único formato cujo config as contava. A
  colheita **salta a página de liga ANTES de a pedir** (`harvest_mtgo`, a
  alteração de 04/10: *«a liga salta sem pedido»*), logo tinha de se **ligar e
  colher**. Os presenciais, ao contrário, estavam lá e eram **excluídos**: na
  janela havia **14** listas de presenciais de Modern, **todas** de eventos com
  menos de 64 jogadores (12 e 17) e **uma** delas joga Mox Opal (Thiago
  Meneghin, 2.º de 17, 4.ª Etapa CLM, 01/10).
- **O INTERRUPTOR É UM SÓ E ABRE QUATRO PORTAS**, porque as quatro lêem o mesmo
  `sources.metagame_rules()["tiers"]`: a **colheita** deixa de saltar a página
  (`harvest_mtgo`), o **`store_decklist`** guarda-a, o
  **`lista_conta`/`counting_sql`** conta-a e o **`analysis.prune_leagues`**
  deixa de a apagar. A quarta é a que mais faltava: sem ela a liga entrava às
  03:30 e a poda apagava-a na **mesma corrida**, minutos depois. Um caso de
  teste por porta.
- **SÓ O MODERN MUDOU, e a secção dele NÃO repete a lista de tiers.** Sem a
  chave `tiers`, `metagame_fontes.modern` herda-a do `_default` (Challenge,
  Showcase, Presencial, Qualifier) e o `ligas: true` acrescenta-lhe `League` —
  uma segunda cópia da lista divergia da primeira no dia em que ele mexesse numa
  delas. O `_default` e os outros formatos ficaram intactos: a regra de
  2026-09-07 (sem ligas, presencial com 64+) continua inteira onde ele não lhe
  tocou, e há caso de teste a varrer os cinco. **Uma armadilha que o teste me
  apanhou:** o `_default` do **config** ganha ao
  `sources.DEFAULT_METAGAME_BY_FORMAT` do **código** — é mais específico que os
  valores de arranque e menos que a secção do formato. Por isso o
  `duel-commander` precisa da secção dele no config (tem-na) e o fixture do
  teste também.
- **A PERCENTAGEM DESCEU, não subiu — e era este o aviso.** Uma liga é um **5-0
  publicado sem classificação e sem tamanho de campo**: somada a uma Challenge,
  a percentagem do formato passa a medir duas coisas ao mesmo tempo. Medido:

  | Mox Opal em Modern | listas | de | % |
  |---|---|---|---|
  | **antes** | 30 | 412 | **7,3 %** |
  | **depois, com ligas** | 54 | 842 | **6,4 %** |
  | **depois, sem ligas** | 33 | 476 | **6,9 %** |
  | **só as ligas** | 21 | 366 | **5,7 %** |

  As ligas **diluem**: jogam Mox Opal menos do que os torneios. Por isso a
  página mostra **as duas contas lado a lado** (`listas_do_formato` →
  `sem_ligas`/`ligas`, e o `ligasHTML` da `decks.py`), com a frase a dizer em
  que SENTIDO elas mexeram — é a disciplina dos «dois números» de 04/10 (*«a
  somar»* vs *«a rodar»*) e da `curva_staples`. Sem isso ele olhava para um
  número que pode ter mexido só porque a fonte mudou. **A soma fecha sempre**
  (33 + 21 = 54, 476 + 366 = 842), como no `confirmado.metades`. Num formato que
  não conte ligas as duas contas são **iguais** e não se desenha nada — é assim
  que isto não muda nada no Legacy.
- **O «sem ligas» também subiu (30/412 → 33/476), e não é da regra:** a colheita
  foi **8 dias** atrás e o `daily` só faz 3 (`MTGO_DAYS`), por isso entraram
  **64 Challenges** de Modern que faltavam. São duas mudanças no mesmo número e
  ficam separadas de propósito.
- **O GRINDING STATION VOLTOU — 3 listas, todas de liga, todas com Mox Opal**
  (04/10 ×2 e 05/10). Era o caso que a ordem mandava verificar: ele deu-o como
  exemplo e tinha **zero** listas desde 29/09. **MAS o agrupamento pô-las em
  dois clusters NOVOS** (7722 com 2, 7727 com 1) e **não** no 7394, que é o
  anotado e continua com zero na janela — e a fonte **não lhes dá nome**. Por
  isso **não se re-apontou a anotação**: a ordem de 04/10 foi explícita (*«não o
  inventes como actual»*), e dois clusters de uma e duas listas não são o deck
  dele. Fica dito; a decisão é dele.
- **AS LIGAS FUNDIRAM UMA DIVISÃO, E ISSO QUASE PÔS O DECK DE GHENT A APARECER
  MORTO.** O `archetype_id` é refeito **todas as noites** e é estável **só
  enquanto a etiqueta do cluster for** (`rebuild_archetypes` faz
  `ON CONFLICT(format, label)`); as anotações do config são por `arquetipo_id`.
  Com as 430 listas novas, o cluster **7614** — nascido a 04/10, 25 listas —
  ficou com **ZERO** e a Affinity passou para o **5100**, que é de **03/09** e
  tem **41**. A anotação do deck **principal**, a que aponta para a caixa com a
  lista de qualificação dele, ficava a apontar para o cluster vazio: a página
  mostrava-o no grupo das *«conhecidas, sem listas na janela»* e a Affinity a
  sério aparecia por baixo como uma versão nova, sem nome e sem a marca.
  **Nada dava erro** — é o padrão do `event_tier` sobre a página por onde ele
  vai sleevar.
  - **Não é um remendo: é a fusão que a ordem anterior tinha previsto à letra**
    (*«o 4380 e o 7614 são a mesma deck partida pelo bug dos arquétipos —
    quando a identidade estável existir, as duas versões colapsam numa»*).
  - **CONFERIDO antes de se mexer:** as 41 listas do 5100 jogam **todas** Mox
    Opal, a fonte chama-lhe **«Pinnacle Affinity»** (4 votos de 5 nomeadas,
    segundo «Affinity») — que é o nome que a caixa dele tem desde 04/10 — e as
    22 cartas do maindeck da lista de qualificação aparecem em **85 %** das 41
    listas, **8 delas em 41/41** (Engineered Explosives, Fiery Islet, Island,
    Kappa Cannoneer, Mishra's Bauble, Mox Opal, Pinnacle Emissary, Spirebluff
    Canal). O `arquetipo_id` passou a 5100 e o **7614 não se apagou**: ficou em
    `_arquetipo_id_antes`, com a data, a razão e como se repõe.
  - **E PASSOU A DIZER-SE, em vez de voltar a acontecer em silêncio**
    (`versoes._orfas`/`anotacoes_orfas` → o bloco `ficha aviso` da `decks.py`):
    uma versão que esteja marcada **principal** ou **escolhida** e tenha zero
    listas na janela leva aviso em DESTAQUE, com o **candidato** ao lado (o
    maior cluster sem anotação, que é quase sempre para onde o deck foi). **O
    crivo é estreito de propósito** — as quatro conhecidas (Weapons, Cranial,
    Seachrome, Grinding Station) têm legitimamente zero e marcá-las era um aviso
    permanente a piscar, que é um aviso que se deixa de ler. A correcção de
    fundo é a identidade estável por NÚCLEO que o `mtgvault/arquetipos.py` já
    faz para as sugestões de Premodern, aplicada à tabela `archetypes` — é a
    ordem `mtg-top8-por-edicao`.
- **O VOLUME, medido antes de se escrever na base** (`_revisao/medir_ligas.py`,
  sem gravar nada): as páginas de liga de Modern servem **45 a 58 listas cada**,
  uma por dia. **Pedidos desta ordem: 24 em duas sondagens** (o `robots.txt`, 7
  dias de índice e a medição das 8 páginas de liga, 2 das quais deram *read
  timeout*) **+ ~37 na colheita** (8 páginas de índice e as 29 páginas de evento
  de Modern/Premodern desses 8 dias). **Resultado: 540 listas novas** em **13
  páginas** — 423 de liga de Modern (9 páginas), 64 de Challenge de Modern (2) e
  53 de Premodern (2). A base passou de **7 761 para 8 295** listas e o
  `vault.db` de **96,6 para 100,1 MB**. Em regime são ~50 listas novas por
  noite, que o `prune_decklists(30)` limita a ~1 500.
- **ENTRARAM LISTAS DE PREMODERN, e a razão é uma substring.** O filtro de URL
  do `harvest_mtgo` é `any(f in url.lower() for f in formats)` e
  **`"modern" in "premodern-challenge-…"`** — por isso pedir `modern` abre
  também as páginas de Premodern. Não é defeito novo nem faz mal (quem
  classifica é o `_guess_format`, que ordena por comprimento decrescente
  exactamente por isto, e o `daily` colhe Premodern todas as noites de qualquer
  maneira): entraram **53 listas de Challenge**, e **zero ligas de Premodern** —
  o `store_decklist` recusa-as, porque esse formato não as conta. Corri-lhe o
  agrupamento também, para o estado publicado ficar coerente.
- **O MTGO.COM PASSOU A TER RITMO** (`PAUSA_MTGO`, 1 s). O mtgtop8 sempre teve 1
  pedido/s (`mtgtop8._get`) e o mtgo.com **não tinha nenhum** — um descuido que
  passava despercebido enquanto a recolha pedia poucas páginas por formato, e
  que esta ordem torna relevante (a página de liga publica-se todos os dias). O
  **`robots.txt` do mtgo.com responde 404** (sondado nesse dia): não existe,
  logo não há regra escrita a respeitar além do ritmo. E o `_get_mtgo` dá uma
  **segunda tentativa a um erro de REDE** e só a esse — uma página de liga
  perdida por um timeout de um segundo ficava perdida **para sempre** (a recolha
  só volta 3 dias atrás); um 404 não se repete, porque não é azar, é a página.
- **`harvest --hoje`**: a página de liga publica os 5-0 **ao longo do dia**, e a
  recolha começava sempre em ONTEM. A omissão **não mudou** — o `daily` corre às
  03:30, quando a página de hoje está vazia, e pedi-la era um pedido por formato
  a não trazer nada. Com `incluir_hoje=True` acrescenta-se um dia à frente, e é
  isso que fechou o buraco de um dia na janela.
- **O JAVASCRIPT DA ABA DECKS SAIU DA CASCA**, e isto não foi escolha: era a
  instrução que a ordem de 04/10 deixou escrita no `TECTO_CASCA` (*«a próxima
  ordem que acrescente JavaScript aqui tira-o para um `decks.js` … Subi-lo três
  vezes é não ter tecto»*). Com as duas contas e o aviso da órfã a casca ia a
  **89 393** de 90 112 bytes — **719** de folga. Medido depois: casca
  **89 393 → 42 762** bytes (**12 257** em gzip, era ~27 700) e **`decks.js`
  46 661** bytes (15 506 em gzip), cacheável `immutable` — o telemóvel dele
  baixa-o **uma vez** em vez de o rebaixar a cada toque no menu. O tecto
  **desceu de 88 para 48 KB**: agora que o JavaScript está fora, ele mede HTML e
  CSS, que é o que um tecto de casca deve medir. O caminho é o do
  `deckboxes.js` de 18/09, com as **três coisas que andam com ele**: o `build`
  escreve o `.js` **antes** da casca, o `webapp.py` serve-o **da memória**
  (`/decks.js`, nunca do disco), e vai no **`git add` do `daily.yml`**, no
  **`EXTRA_COMMIT` da tarefa `mtgvault-daily`** e no **`publicar.PUBLICAVEIS`**
  — sem ele nas três, o site abre a casca e **não desenha nada**.
- **O MOTOR NÃO MEXEU UM NÚMERO**: fechar tudo **11 043,88 €** nos dois lados,
  **293** a comprar, as **17 caixas iguais à percentagem, à cópia e ao
  cêntimo**, `guardar` 1 c, `rl_sem_historico` 98 c, `reservadas`/`retidos`/
  `rl_segurar`/`sem_foto` a zero.
- **E MEXEU POR CONSEQUÊNCIA, 3 cópias para o lado SEGURO:** a RP passou a
  proteger **252 → 278 nomes** (as ligas trazem mais variedade às listas de Mox
  Opal), e por isso **3 cópias / 6,18 €** saíram de `venda` (366 → 363) para
  `protegidas` (148 → 151). Hoje a RP segura 9 linhas / 23 cópias: 3 Cabal
  Therapy, 4 Carpet of Flowers, 5 Lightning Bolt, 2 Lotus Petal, 3 Orcish
  Bowmasters, 3 Spell Snare, 1 The One Ring, 2 Unholy Heat. **Nada sai**: a
  venda está escondida (`venda.mostrar: false`) e travada à mão.
- **AS VERSÕES DE MODERN: 8 → 12.** Entraram o **5100** (41 listas, a Affinity),
  o 7724 (3), o 7748 (2), o 7722 (2), o 7763 (1), o 7726 (*«Song of Creation»*,
  o único com nome da fonte) e o 7727 (1); saíram o 7614 (para o 5100), o 7622 e
  o 7697 (fundidos). As listas **sem cluster** passaram de 1 a **0**.
- **Medido com as páginas servidas por HTTP e o JavaScript a sério**: as **14
  páginas, o `decks.js` e o `deckboxes.js` a 200**, os **280 ficheiros de dados
  a 200**, **zero** mensagens de erro de dados, e a aba Decks percorrida nos
  quatro formatos com os blocos novos conferidos no HTML **desenhado** (*«Com as
  ligas e sem elas: sem ligas 33 de 476 (6,9 %) · só as ligas 21 de 366
  (5,7 %) … Aqui as ligas diluem a percentagem»*). A 1440 e a 390 px **nenhuma
  página com rolamento horizontal**. Imagens: **1 321** no total (eram 1 288),
  todas com `loading="lazy"` e o tamanho escrito; nenhuma página passa dos
  250 KB. Bateria toda verde (92 ficheiros).
- **UM TESTE DE 04/10 TEVE A ASSERÇÃO CORRIGIDA, e não mascarada**
  (`test_decks_vista.caso_a_pagina_nao_embebe_imagens_e_cabe_no_tecto`):
  procurava o CDN das artes **na casca**, e o JavaScript que desenha as `<img>`
  mudou de ficheiro. A intenção não mudou — o tecto mede a CASCA e as imagens
  medem-se na **página inteira** (casca + `.js`), que é o que o browser acaba
  por ter. Mascará-lo era deixar de verificar as imagens no dia em que elas
  mudaram de sítio.
- **POR DECIDIR POR ELE:** (a) o **Grinding Station** voltou à janela mas em
  dois clusters novos e sem nome da fonte — re-apontar a anotação (hoje no
  7394, que tem zero) é decisão dele, e **muda o que ele monta**; (b) as **3
  cópias / 6,18 €** que saíram da lista de venda para protegidas; (c) os
  presenciais pequenos passaram a contar em Modern e **só em Modern** — se
  quiser o mesmo no Legacy ou no Premodern, é uma secção no `metagame_fontes`;
  (d) as **ligas de Modern passam a entrar todas as noites** (~50 listas), e
  desligá-las é `ligas: false` nessa secção.

**A LISTA DE FALTAS PARA GHENT, E AS IMAGENS NAS LISTAS DE CARTAS (André,
2026-10-05, à letra).** *"quero as coisas publicadas no mtgvault, com imagem das
cartas para eu me organizar"* e *"preciso tambem da lista de faltas desses decks
para poder procurar em Ghent"*. Ele joga o RC Ghent a 9-11/10. Motor em
**`mtgvault/faltas_vista.py`**, página **`faltas.py` → `faltas.html`**, a imagem
partilhada em `paginas.IMG_LOTE`/`CSS_IMAGENS`/`js_imagens`, a pergunta do preço
em `loadout.preco_fora_da_regra`/`mais_barata_que_serve`, passo `faltas` do
`daily`, CLI `py -m mtgvault.faltas_vista [--json]`. Testes em
`tests/test_faltas_imagens.py` (7 casos) e a prova de que chumbam em
`tests/_chumba_faltas.py` (**8 de 8 alvos**, um processo por alvo). Backup em
`data/backups/vault-2026-10-05-faltas-ghent.db` (92,2 MB, `integrity ok`). **A
venda continua escondida e travada** — nada aqui a destranca.

- **A FASE 3 DA ARRUMAÇÃO NUNCA DESENHOU NADA, e foi isto o achado do dia.** As
  duas listas que ele mandou pôr com imagem — a de **NÃO VENDER** (as protegidas)
  e a de **SEGURO VENDER** (os candidatos) — mostravam *«não consegui carregar os
  dados desta secção»* **desde 2026-10-01**, o dia em que a página nasceu
  (`39d83d7`): o `fase3(p)` lia `p.candidatos` e a parte **é** o candidatos (o
  `dados()` sempre escreveu `partes["candidatos"] = _magra(...)`). O `c.linhas`
  rebentava, o `catch` do `render` chamava o `erroDados`, e **nada dava erro**: a
  página respondia 200, os 273 ficheiros de dados respondiam 200, e **nenhum teste
  lia o HTML daquela aba**. É o padrão do `event_tier` do lado do browser. O bloco
  do Mox Opal de 04-05/10 entrou para DENTRO dessa função e também nunca apareceu
  — e a **CURVA DO LIMIAR** era composta num `curva` e **deitada fora no
  `return`**, por isso o relatório de 05/10 (*"a página mostra a curva com os dois
  números"*) estava a descrever uma coisa que não se via. As duas corrigidas, com
  caso próprio: foi a contar as imagens com o `tests/avaliar_js.js` que isto
  apareceu — ler o HTML que o JavaScript desenhou é a única forma de o ver.
- **O NOME MANDA E A IMAGEM É UM APOIO**, e é a decisão que distingue esta página
  da aba Decks. Ali a arte é o conteúdo (ele está sentado a ordenar cartas); aqui
  ele está **de pé, num pavilhão, com o telemóvel numa mão** e a outra a segurar
  cartas, e o que diz ao vendedor é o NOME: 17 px, a negrito, e **nunca cortado**
  (`overflow-wrap:anywhere`) — uma «Swords to Plow…» ao balcão não é um nome.
- **40 IMAGENS NO PRIMEIRO ECRÃ, e não é o `loading=lazy`.** As linhas acima do
  lote nascem com o lugar RESERVADO (`aspect-ratio`) e **sem `<img>`**, e um
  `IntersectionObserver` (`rootMargin: 300px`) põe a arte quando a moldura se
  aproxima. Duas razões para o número ser nosso: o `lazy` é uma sugestão que cada
  browser cumpre como quer, e **um número nosso TRANCA-SE num teste**. Medido na
  base dele: a lista de faltas são **186 linhas** e a Fase 3 **845** (574 não
  vender + 271 seguro vender) — pedir tudo era mandar o pavilhão descarregar 845
  imagens por uma rede partilhada por mil pessoas. Medido **no site publicado**,
  num Chrome a sério a 390 px: **43 imagens em 187 linhas** nas faltas e **83 em
  847** na Fase 3 (40 e 80 do lote, mais as três que o observador alcança).
- **A peça da imagem vive no `paginas`** (`IMG_LOTE`, `CSS_IMAGENS`,
  `js_imagens()` com `contaArtes`/`arteHTML`/`observaArtes`), partilhada pelas
  duas páginas. Escrita duas vezes, a segunda esquecia-se de uma das quatro coisas
  que fazem uma `<img>` comportar-se — é exactamente o que aconteceu às 1 288
  imagens desenhadas no servidor a 2026-10-04. E o `_JS` da Arrumação era montado
  em TRÊS sítios (`casca`, `build`, `html_page`): passou a `_js()`, senão a peça
  nova entrava em dois e a terceira desenhava molduras que nunca ganhavam arte.
- **O `sid` ENTROU nas linhas da Fase 3** (`_CAMPOS_TABELA`): é a impressão
  EXACTA da cópia. Custa ~38 KB nas 845 linhas (a parte `candidatos.json` passou
  de 189 para 227 KB), que é a escala das que já lá estão (`fase4` 177 KB,
  `encomendas` 234 KB).
- **A VISTA DE FALTAS É UMA LINHA POR CARTA, com SUBTOTAL POR DECK**, ordenável
  por valor ou por deck, filtrável por formato, alvos de 44 px, zero rolamento
  horizontal (não há tabela: é uma lista, e cada linha é uma grelha que encolhe).
  **O que ele já tem não aparece**, por construção: a falta é o `comprar` da
  alocação, que já desconta o que ele tem, o que está noutra caixa e **o que já
  encomendou** (2026-09-19) — tem caso de teste com uma encomenda, que é o que
  separa o `comprar` do `missing`. E as **CARTAS contam-se por NOME sem repetir
  entre decks**: a mesma carta a faltar em três caixas é UMA carta para procurar e
  TRÊS cópias para comprar; somar os `cartas` de cada deck dava o nº de linhas.
- **MEDIDO na base de 2026-10-05**: **11 decks · 157 cartas · 295 cópias ·
  11 075,43 €**, 17 cópias sem preço, **60 linhas com o preço fora da regra**. O
  `loadout.report` passou de **0,71 s para 0,74 s** (+4 %) e **não mexeu um
  número** — fechar tudo 11 075,43 €, 295 a comprar.
- **O FORMATO SEM DECK ESCOLHIDO FICA À PARTE E FORA DO TOTAL** (ordem dele). Quem
  decide não é uma lista de nomes: é o `faltas_vista.sem_deck_escolhido` — o
  formato está no modelo «um deck por formato» e **não tem versão nenhuma**. Hoje é
  só o `legacy`, e no dia em que ele escolher o deck a secção desaparece sozinha
  (tem caso de teste nos dois sentidos). **Não se pergunta pelo `por_decidir`**:
  essa chave foi arquivada a 05/10 de manhã, quando o Legacy entrou no critério do
  Mox Opal — deixou de estar «por decidir» para a PROTECÇÃO e continua sem deck
  escolhido para MONTAR. São duas perguntas. (Hoje as três caixas de Legacy têm
  **zero** faltas, por isso a secção está vazia na prática.)

**O PREÇO DE UMA FALTA PODE NÃO SER DO MATERIAL QUE A REGRA PEDE, E A LINHA
DI-LO (André, 2026-10-05).** *"quando o preco mostrado nao e da lingua ou do
acabamento que a regra pede, a PAGINA TEM DE O DIZER NA LINHA. Um preco de outra
lingua apresentado como se fosse o certo e o mesmo erro das duas verdades."*
Motor em `loadout.preco_fora_da_regra` + `mais_barata_que_serve`, ao lado do
defeito; a linha de falta leva `preco_aviso`, por isso a vista de faltas **e** a
aba Comprar lêem a mesma resposta.

- **A PREMISSA DA ORDEM NÃO SE PODE VERIFICAR NOS TERMOS DELA, e isso é o
  primeiro facto.** Ela diz *"46 cartas de Premodern não têm preço em PORTUGUÊS na
  base"* — e **não há dimensão de língua nenhuma nos preços**: a chave da
  `price_latest` é `(scryfall_id, source, finish)` e mais nada. O que o preço do
  CardTrader é, de verdade, é a **mediana das ofertas em `precos.linguas`** (hoje
  {pt, en}) **daquela impressão** — pode ser uma oferta inglesa, e a base não
  guarda qual foi. E a pergunta *"esta carta existe em português?"* **não se
  responde do catálogo**, ao contrário do que a ordem supõe: o `catalog.db` é o
  bulk `default_cards` e tem **110 148 impressões `en` contra 3 `pt`** em 112 758
  (o Scryfall só traz as outras línguas no `all_cards`, que o vault não
  descarrega, por decisão de 2026-09-18). Não se inventou: diz-se.
- **O QUE A BASE SABE RESPONDER, e é pior do que a ordem previa — no sentido
  CONTRÁRIO.** O `card_price` é um MÍNIMO ENTRE IMPRESSÕES e **não filtra pela
  regra da caixa**: nem pela língua, nem pela EDIÇÃO. Para o SPML é inofensivo
  (não há limite de edição); para o **Premodern**, que é *"apenas português,
  non-foil, nas edições indicadas"*, o preço vem de uma reimpressão que a caixa
  recusa — e é sempre **mais barata** do que a legal. Das **121 cartas distintas**
  das seis caixas de Premodern:

  | | cartas |
  |---|---|
  | (a) sem nenhuma impressão ≤SCG no catálogo | **0** |
  | (b) com impressões ≤SCG mas **nenhuma cotada** | **1** (Tormod's Crypt, 3 impressões) |
  | (c) o preço mostrado vem de **fora** do limite | **67** |
  | o preço mostrado já é de uma impressão que serve | 53 |

  A causa (a) da ordem **não existe aqui** — e faz sentido: um deck de Premodern
  só joga cartas Premodern-legais. A (b) é um furo na recolha, e é **uma** carta.
  A (c) é a grande, e é a que custa dinheiro: a **Polluted Delta** mostra 26,41 €
  (MH3, 2024) e a mais barata que serve são **156,84 €** (ONS); a Flooded Strand
  20,35 € → 129,17 €; o Squee 0,55 € → 38,28 €. Das 14 cartas que a ordem nomeia,
  **8 estão na (c)** (Exploration, Sterling Grove, Brushland, Deep Analysis,
  Cursed Totem, Anger, Call of the Herd, Defense Grid) e **6 já tinham o preço
  certo** (Argothian Enchantress, Cabal Ritual, Dark Ritual, Cataclysm, Caller of
  the Claw, Crumble).
- **OS DOIS PREÇOS VÃO LADO A LADO**, que é a disciplina de 2026-10-04 («a somar»
  vs «a rodar»): `unit`/`total` do motor e `unit_serve`/`total_serve` da impressão
  que **esta caixa aceita**. Medido: as faltas passam de **11 075,43 € para
  12 898,32 € (+1 822,89 €)**, todo em Premodern — IGG 3 450,35→3 729,66,
  Elves 2 110,46→2 420,74, Oath 1 430,95→1 832,10, Enchantress 1 037,39→1 666,75,
  UW Replenish 30,71→124,68, **Stiflenought 20,35→129,17** (6×). Esconder o
  segundo número era deixá-lo escolher onde caçar por uma conta errada.
- **DOIS GRAUS, e é o que torna isto utilizável num pavilhão.** «**aviso**» é um
  número demonstravelmente errado e com o certo ao lado (a edição que a caixa
  recusa, ou nenhuma impressão que serve estar cotada); «**nota**» é o que não se
  pode verificar (a língua). Com um grau só, **173 das 186 linhas** ficavam a
  piscar — toda a caixa com regra de língua — e ele deixava de olhar para as **60**
  que importam. É o princípio do 503-contra-500 do `webapp`: *«ainda não sei»* não
  é uma avaria. A regra dele cumpre-se nas duas: a linha di-lo sempre.
- **A REGRA DO PREMODERN NÃO SE TOCOU** (ordem dele). O que mudou é o que a página
  DIZ, e o `loadout.report` não mexeu um número.
- **POR DECIDIR POR ELE:** (a) a regra `lingua: pt` + `estrita: true` do Premodern
  — hoje não há como confirmar que um preço é de uma oferta portuguesa, e saber-lo
  exigia o bulk `all_cards` do Scryfall (~2 GB, que o vault recusa desde 18/09);
  (b) o **Tormod's Crypt**, cujas três impressões ≤SCG não estão cotadas — é um
  furo na recolha do CardTrader, não uma carta sem preço;
  (c) se quiser que o *fechar tudo* e a aba Comprar passem a usar o preço da
  impressão que a caixa aceita (e não só a lista de faltas a dizê-lo), é uma
  decisão dele: muda o número que ele vê todos os dias em **+1 822,89 €**.

**PUBLICAR SEM ESPERAR PELAS 03:30, E A BARRA PELOS QUATRO TRABALHOS (André,
2026-10-04, à noite, à letra).** *"podes refazer novamente a seccao do MTG
completamente com estas novas regras?"* e *"Organiza tudo de forma profissional
e clara"*. Motor em **`mtgvault/publicar.py`** + a tarefa
**`ai-pc/tasks/mtgvault-publicar`**; a barra em `site_shell.SECCOES`; os tokens
em `site_shell.TEMA`; a `<img>` em `paginas.img_carta`. Testes em
`tests/test_publicar.py` (8 casos) e `tests/test_tokens.py` (5), com a prova de
que chumbam em `tests/_chumba_redesenho.py` (**14 de 14 pares**, um processo por
par). Etiqueta de recuo: **`antes-redesenho-2026-10-04`**.

- **O FURO QUE ISTO FECHA, e não era teórico: o site publicado podia estar um
  DIA atrasado.** O `webapp.regenerar` reescreve as páginas em disco no instante
  em que ele carrega num botão do modo edição — e **ninguém as commitava** até à
  corrida das 03:30. A 04/10 havia `riftvault-publicar` e `baiakvault-publicar`
  de 30 em 30 minutos e **nenhuma `mtgvault-publicar`**: é a avaria de
  08/09/2026 no riftvault (*"129 alterações ficaram no PC o dia inteiro"*), que
  lá foi fechada e **aqui nunca tinha sido**.
  **Medido nesse dia, com a árvore LIMPA:** o `index.html`, o `deckboxes.html` e
  o `metagame.html` em disco eram de **20:14** e o `colecao_config.json` de
  **21:10** — a ordem anterior trocou a lista de sete caixas e regenerou **só** o
  `decks.html`. O site publicado estava a dizer números diferentes em páginas
  diferentes, e foi assim que isto se descobriu.
- **O RELÓGIO SOZINHO NÃO É UM COMMIT.** `publicar.estado()` gera as 13 páginas
  para uma pasta de PROVA e compara com o disco **sem o carimbo de geração**.
  Medido (`_revisao/medir_estabilidade.py`): duas passagens seguidas sobre a
  mesma base dão **todo o HTML byte a byte igual** e **7 índices diferentes — só
  no `_gerado_em`**. Sem a normalização, a tarefa dava um commit e uma build do
  Pages **a cada meia hora, para sempre**. Tem caso próprio e alvo no `_chumba`.
- **UM `set` PELO MEIO IA DAR 48 COMMITS POR DIA, PARA SEMPRE — e só se vê em
  DOIS PROCESSOS.** O `data/paginas/cobertura/prints.json` saía com as **mesmas
  chaves e o mesmo conteúdo noutra ORDEM** a cada corrida: o
  `meta_coverage.build` fazia `names = {…}` (um `set`) e o Python **aleatoriza o
  hash das strings a cada arranque**. Dentro do mesmo processo era estável — que
  é precisamente por que ninguém deu por isso enquanto só o `daily` o escrevia
  uma vez por dia. Com o `publicar` de 30 em 30 minutos a decidir «há algo para
  commitar?» por essa diferença, eram **48 commits e 48 builds do Pages por dia,
  em 77 854 bytes que não mudaram**. Hoje é `sorted(...)`, e quem o tranca é o
  `tests/medir_determinismo.py` — que corre a geração em **subprocessos**, e
  vive em `tests/` e não num scratch pela razão do `medir_layout.py`: uma
  ferramenta fora do repositório fazia o caso **saltar em todas as outras
  máquinas**. Varridos os **273 ficheiros**, era o único.
- **PUBLICAR NÃO ESCREVE NA COLECÇÃO, e isto quase passou.** Dos treze
  geradores, **um** escrevia: a Galeria grava o ponto do dia no `value_history`
  (`INSERT OR REPLACE`, **8 272 bytes no `-wal`**, medido). Como o SOSSEGO da
  tarefa é *«o `vault.db` foi escrito há menos de 10 min?»*, ela
  **envenenava-se a si própria**: publicava uma vez e dizia «ele está a editar»
  para sempre, sem uma única carta ter mudado. Hoje o `publicar` chama-a com
  `historico=False` (`publicar.SO_LEITURA`) e o `daily` continua a gravar o
  ponto — há caso de teste para **cada um dos dois lados**.
  **A primeira medição disto deu «ninguém escreve» e era FALSA**: segurava uma
  ligação aberta durante os treze builds, e em WAL a escrita só chega ao
  ficheiro principal quando a última ligação fecha. O que denuncia a escrita é o
  **`-wal` a crescer**.
- **DUAS DIFERENÇAS FACE AO RIFTVAULT, e as duas são deliberadas:** (a) o
  **`data/vault.db` NÃO se commita** — está no `.gitignore` desde 2026-08 e vive
  no Release `data` (**99,5 MB** medidos; commitá-lo de 30 em 30 min era ~5 GB
  por dia). O que faz o site mostrar as marcas dele são as PÁGINAS, e são essas
  que vão; quem republica a base é o `mtgvault-daily`. (b) o **sossego não se
  pendura no `git status`** (lá a base está no Git; aqui o status nunca a vê):
  é o **mtime do `vault.db`**, e **nunca o do `-wal`**, que aparece e desaparece
  ao ritmo do aquecedor do 8771 e está a zero bytes — a lição do
  `webapp._versao()`. Medido: uma LEITURA não lhe toca no mtime.
- **«OUTRO RAMO» NÃO É UMA AVARIA, É UM «AINDA NÃO».** A tarefa recusa publicar
  de um ramo que não seja o `main` — mas com `exit 0` e estado próprio, não
  vermelho: uma ordem do Claude deixa o repositório num ramo durante HORAS, e
  com `falhar()` esta tarefa ficava vermelha de 30 em 30 minutos todo esse tempo
  — e um vermelho que é normal deixa de se ler (é a distinção 503/500 do
  `webapp`). O teste confirma **por fora** que o ramo é mesmo outro, senão era a
  desculpa perfeita para nunca publicar.
- **A BARRA PASSOU A SER OS QUATRO TRABALHOS DELE** (*"reagrupa pelo que ele
  FAZ, nao pelo que o codigo tem"*): **Montar decks · Ver a colecção · Seguir o
  metagame · Arrumar e vender**. Eram cinco secções nomeadas pelo que o código
  tinha, e a de «Decks» juntava SETE itens, cinco deles a mesma página
  (`deckboxes.html`) com âncoras diferentes — a fila de botões de 2026-09-24
  outra vez, movida para dentro da barra. **Três coisas NÃO mudaram, e são
  decisões:** o «Decks montados» e o «Decks para montar» FICAM (pedido dele à
  letra, 2026-09-08 — encurtar um menu não é razão para tirar uma vista que ele
  pediu pelo nome); a «Arrumação por fases» continua no topo, fora de secção (a
  decisão de 01/10, e é o ecrã que ele abre todos os dias); e **nenhuma página
  saiu do menu**, por isso o número de itens **não desce** — o que muda é
  estarem agrupadas pela pergunta que respondem.
  **Duas premissas da ordem precisavam de correcção:** o `meusdecks` e o
  `decksfaziveis` **já não estavam no menu** (são reencaminhamentos desde a v6 e
  2026-09-07), por isso «a aba nova ao lado das quatro antigas» eram duas, não
  quatro; e **a casca partilhada já existia** desde 2026-09-24 — o que faltava
  era o conjunto de tokens estar COMPLETO.
- **OS TOKENS DE ESTADO, e porque é que o tecto não é zero.** Medidos a 04/10:
  **297 valores de cor escritos à mão** em 9 ficheiros, **136 distintos** —
  quatro cinzentos de painel quase iguais, três laranjas de aviso, dois azuis de
  «está noutra caixa». Entraram no `TEMA` os trios de estado (`-soft` fundo,
  `-line` borda, o nome sozinho é o texto) para `ok`/`info`/`warn`/`bad`, mais o
  `--sunken`, e converteram-se **142 ocorrências (41 valores) em 14 tokens**,
  por uma lista **explícita e conferida** — ficam **155**, com tecto no
  `test_tokens`.
  **A troca automática do resto foi MEDIDA e REJEITADA** (`_revisao/tokens_mapa.py`),
  e os quatro modos de falhar ficam escritos porque qualquer um deles estragava
  o site em silêncio: (a) `#000d`/`#0009`/`#000b` são hex com **ALFA** (sombras,
  véus) e um token opaco tapava a página; (b) a **matiz de uma cor quase negra é
  instável** — o `#0c0f14`, uma superfície neutra, classifica-se como azul e
  arrastava 24 valores para um tom de «informação»; (c) o dominante de uma
  família **redefinia tokens que já existem** (o `--line2` passava de `#2c3243`
  a `#5a6472` e mudava todas as bordas do site); (d) a banda de «texto» vai do
  `#fff` ao `#79c9c4` e o branco caía em `--ink2`.
- **UM `var()` POR UM TOKEN QUE NÃO EXISTE NÃO DÁ ERRO, e havia um.** O
  `test_tokens.caso_todo_o_var_usado_esta_definido` apanhou `color:var(--text)`
  na **Arrumação** — um token que **nunca existiu**. A propriedade é ignorada em
  silêncio e a cor vem do que estiver por trás: ou seja a linha que ele mandou
  deixar ÓBVIA (*«e agora como destranco a venda?»*) estava a ser desenhada no
  cinzento de nota de pé de página. Hoje é `--ink`.
  **E o que o deixou passar foi uma lista escrita à mão**: o `GERADORES` do
  `test_paginas` tinha **dez** nomes acrescentados a mão e faltavam-lhe a
  `arrumacao.py` (01/10) e a `decks.py` (04/10) — exactamente o defeito que o
  docstring desse caso descreve (*"por isso a Galeria escapou"*), repetido com
  as duas páginas nascidas depois. Passou a ser **DERIVADO** do
  `publicar.PAGINAS`, que é a lista que o site publica.
- **1 288 IMAGENS DEIXARAM DE FAZER A PÁGINA SALTAR.** A `<img>` estava escrita
  à mão em quatro sítios — `colecao_cor` (×2), `metagame` e `caixarl` — e as
  quatro tinham o `loading="lazy"` e **nenhuma** tinha o tamanho: 743 imagens
  nos Binders, 474 no Metagame e 71 na Caixa RL a mover o conteúdo por baixo do
  dedo dele enquanto carregavam. Hoje saem do `paginas.img_carta`, com
  `decoding="async"` e `width`/`height`. **Custa 30 KB em disco e ~2 KB na rede**
  (medido: o `colecao_cor.html` vai a 239,8 KB em disco e **43,3 KB em gzip**,
  5,5×, que é o que o telemóvel dele descarrega).
- **O «2026-09-09» DO INÍCIO ESTAVA CERTO — o que estava errado era o sítio.**
  A linha é *«Cartas dentro das caixas»* e sai de `MAX(copy_allocation.placed_at)`:
  conferido na base, **260 linhas / 411 cópias, a última às 12:30 de 09/09**, e
  desde então ele não arrumou mais nenhuma caixa. Não é um carimbo que deixou de
  ser alimentado. O defeito era estar debaixo de *«Últimas atualizações dos
  dados»*, ao lado de quatro linhas que o `daily` ALIMENTA — onde uma data velha
  é uma avaria. Partiu-se em duas listas: **«O que o vault vai buscar»** (preços,
  decklists, arquétipos, decks vigiados) e **«O que confirmaste à mão»**, cada
  uma com a sua frase a dizer o que uma data velha quer dizer ali.
- **MEDIDO, com o servidor a correr e o JS a sério:** as **14 páginas a 200** e
  os **259 ficheiros de dados a 200, zero erros**; a 1440 e a 390 px **nenhuma
  página com scroll horizontal**; nenhuma página acima dos **250 KB** de casca
  (a maior é 239,8 KB em disco / 44,9 KB em gzip). A aba Decks percorrida de
  ponta a ponta — **8 formatos, 96 partes, 96/96 a 200** —, com o `+` a escrever
  na `posse_marcada`, a marca a **sobreviver ao recarregamento** (está na base,
  não no browser), um retry do mesmo `request_id` a **não contar a dobrar** e o
  `−` a travar no zero. **Dois pedidos passam dos 2 s do orçamento e são
  anteriores a esta ordem**: o `deckboxes.json` a frio (4,4 s) e o
  `arrumacao.json` (1,1 s) — é o `webapp` a CALCULAR, abaixo do tecto de 25 s do
  `ESPERA_DADOS` e pago pelo aquecedor antes de ele abrir a página.
- **POR FAZER, e é o que vale a pena ler primeiro:** (a) o **modo claro** não se
  fez — o site é escuro e ele usa-o no escuro; os tokens já estão num sítio, por
  isso é um segundo `:root` e não uma reescrita, mas é uma ordem própria com
  capturas dos dois lados; (b) as **155 cores** que ficam, pelas quatro razões
  acima; (c) a **fusão do `deckboxes.html` na aba Decks** não se fez e **é uma
  decisão**: são 6 621 linhas com oito sub-vistas e todos os botões do modo
  edição, e fundi-las na véspera do RC de Ghent era arriscar o ecrã que ele usa
  todos os dias — as duas respondem a perguntas diferentes (o deck vs. a
  logística da caixa) e hoje dizem-no; (d) o Release `data` só é republicado
  pelo `mtgvault-daily` das 03:30, por isso um `workflow_dispatch` manual do
  `daily.yml` entre uma edição dele e as 03:30 regeneraria as páginas a partir
  de uma base sem as marcas desse dia — hoje é manual e não tem horário, mas
  está dito.

**AS FOTOS FORAM APAGADAS E A CAMPANHA ESTÁ DESLIGADA (André, 2026-10-04, à
letra).** *"podes apagar todas as fotos, A MINHA RESPONSABILIDADE, se for para
ter fotos, vou tirar as fotos todas novamente"*.
**[E A REGRA FOI SUBSTITUÍDA, não só desligada (04/10, à tarde).]** O *"se não
tiver foto, não tem carta"* de 02/10 era a resposta a *"tenho esta carta?"*; a
partir de hoje a resposta é o `+`/`−` da **aba Decks** (ver a secção de cima).
A razão, nas palavras dele: *"SEM FOTOS DAS CARTAS! mais facil para mim e para
ti!"* — e a razão técnica: a precisão de uma foto serve para **vender** (é dela
que sai o escalão de estado, 03/10), não para **montar** um deck, e com o
interruptor ligado e zero fotos a colecção inteira lia-se como vazia. O
interruptor continua a ser `revalidacao.foto_manda` (**`false`**, com `desde:
null`), **o código das fotos fica todo no sítio**, e há caso de teste que o volta
a ligar e exige que a regra morda outra vez
(`test_decks_vista.caso_o_codigo_das_fotos_continua_todo_no_sitio`). **A secção a seguir (02/10)
continua a descrever o motor, que não se tocou — mas o INTERRUPTOR está hoje a
`false` e a campanha a `null`.** Testes em `tests/test_fotos_apagadas.py` (16
casos) e a prova de que chumbam em `tests/_chumba_fotos_apagadas.py` (4 alvos).

- **O QUE SE APAGOU, e só isto:** as **322 imagens** de
  `data/fotos/anteriores/` (**96,4 MB**) e os **723 `photo_path`** da `copies`.
  É um levantamento **PONTUAL** da regra de 09/09 (*nada se apaga*), dado por
  ele, **só para as fotos de cartas**. A regra continua inteira para tudo o
  resto: as **737 linhas / 1 678 cartas** da `copies` ficam todas, a base, o
  config e os registos ficam.
- **A ORDEM DOS PASSOS É O QUE TORNA ISTO REVERSÍVEL NO QUE PODE SER:** backup
  (`data/backups/vault-2026-10-04-antes-de-apagar-fotos.db`, 90,7 MB,
  `integrity_check ok`) → **registo** → só depois o disco. O registo é
  **`data/fotos-apagadas-2026-10-04.csv`** (723 linhas: `copy_id`, carta,
  edição, número, acabamento, língua, quantidade e o `photo_path` que tinha) e
  **vai no Git** — é a única memória do que cada cópia tinha, e um registo que
  só existisse neste PC não era registo. **Não se apaga.**
- **APAGAR AS FOTOS NÃO MEXEU UM ÚNICO NÚMERO, e foi medido lado a lado** com o
  mesmo código e as duas bases (`_revisao/apagar_fotos_5_comparar.py`): fechar
  tudo **10 281,35 €**, 294 a comprar, valor **136 379,11 €**, 1 678 cartas, as
  nove saídas da venda e as 17 caixas **iguais**. A razão está na base: as 723
  fotos eram **todas anteriores a 20/09** e o `validado_em` estava a **NULL nas
  737 linhas** — nenhuma delas era prova desta campanha. O `foto_anterior`, o
  `verso_path`, o `condition_em`/`condition_motivos` e a tabela `condition_log`
  estavam **vazios**: não se perdeu um juízo de estado nem um verso.
- **A CAMPANHA FICOU DESLIGADA, e isso não é cosmética.** Com `foto_manda: true`
  e zero fotos, a regra *"se não tiver foto, não tem carta"* recusava a colecção
  INTEIRA: o Início dizia *«0 de 1 678 cartas confirmadas por foto»*, o Blue Farm
  **0 %** com 96 % na gaveta, o Oswald 0 % com 93 %, e as 113 cópias da venda
  caíam todas em `sem_foto`. A regra existe para o obrigar a fotografar, não para
  lhe esconder a colecção enquanto não o faz. `revalidacao.desde: null` +
  `foto_manda: false` devolvem o vault ao que era — Stiflenought 100 %, Blue Farm
  96 %, Affinity (Luffy) 100 %, Oswald 93 %.
- **O `index.html` E O `arrumacao.html` TIVERAM DE SER REGERADOS, e é a parte que
  quase passou.** O `inicio.py` e o `arrumacao.py` já liam o interruptor
  (`if confirmado.manda() else None`) — **o código estava certo**. O que mentia
  era o **HTML em disco**, escrito pelo `daily` das 03:30 com a regra ainda
  ligada: o Início continuava a afirmar *«uma cópia só conta para as decisões
  quando tem foto desta campanha»*, que a partir de hoje é **falso**. Um
  interruptor que se desliga sem regerar as páginas é o padrão do `event_tier`
  na porta de entrada do site. Verificado no texto **VISÍVEL** das páginas
  (`_revisao/apagar_fotos_7_frases.py`, que descarta os `<script>`: a frase do
  bloco «📷 A foto é a verdade» vive num template string do JavaScript da
  Arrumação e **está sempre no ficheiro**, desenhe-se ou não — quem decide é o
  payload, e ele diz `foto: {manda: false}`).
- **O CAMINHO DAS FOTOS NÃO SE APAGOU**, e é a metade que interessa quando ele
  voltar a fotografar: `fotosite.py`, `revalidacao.py`, `fotocaixa.py`,
  `fotos.py` e `confirmado.py` estão intactos, a **pasta** `data/fotos/anteriores/`
  fica (vazia — é o destino do `fotos.arquivar`), e há caso de teste que põe
  `foto_manda: true` outra vez e exige que a regra volte a morder (0 % com a
  caixa cheia). Voltar a ligar são duas linhas no config.
- **O QUE FICA A SABER, e é para a ordem seguinte:** (a) o `fotografar` (589) e o
  `collection.copias_sem_foto` (737) **continuam a contar**, com o interruptor
  ligado ou desligado — é a metade informativa (`got - got_conf`), sempre foi
  assim, e as DECISÕES ignoram-na; o `esperadas.md` passa a listar as 737 como
  *«na base, sem foto»*; (b) o item **«Revalidação por foto»** da barra lateral
  (`site_shell.SECCOES`) continua a apontar para `deckboxes.html#revalidacao`,
  uma aba que com a campanha desligada **não existe** — é a única ponta solta, e
  não se mexeu nela porque tirar um item da barra muda as onze páginas;
  (c) `fases.fotos_perdidas` passou de **33 fotos / 165 cópias / 12 639 €** para
  **zero**, e é o certo: «foto perdida» é `photo_path` cheio **e** ficheiro fora,
  e já não há promessa de foto nenhuma.
- **ENCONTRARAM-SE 106 IMAGENS NOUTRO SÍTIO E NÃO SE TOCOU NELAS:**
  `scratchpad_crops/` (64,4 MB, PNG, todas de **25/08/2026 entre as 19:47 e as
  23:51** — `p1_volrath`, `pm17_bayou_full`, `p21c_harm_text`). São recortes de
  trabalho de uma sessão de leitura, não fotos da colecção, e a ordem mandava
  listá-las em vez de as apagar. As pastas `pendentes/`, `Colocar fotos da
  coleção aqui/` e `assets/deckboxes/` tinham **zero** imagens (só `_plano.txt`,
  `.gitkeep` e `LEIA-ME`).

**A FOTO É A VERDADE, E A BASE É O REGISTO DELA (André, 2026-10-02, à letra).**
*"cada deck tem as suas cartas"*; *"o que eu colocar de fotos no deck, é daquele
deck, ponto"*; *"se não tiver foto, não tem carta"*; *"assim fico responsável por
cada vez que comprar cartas, ter que tirar a foto para atualizar"*. **INVERTE o
modelo de 2026-09-20** (a «REVALIDAÇÃO POR FOTO», que segue abaixo e fica como
histórico): até hoje a BASE era a verdade e a foto servia para *revalidar* — o
`validado_em` era um 📷/✓ que a página mostrava e que, por decisão explícita,
**não mexia um único número**. A partir de hoje é ao contrário: **uma cópia só
CONTA quando tem foto desta campanha**, e a **pasta** onde ele larga a foto
decide a que deck a carta pertence. **No mesmo dia ele mandou ESQUECER o tecto de
playset do Premodern** de 2026-09-08 — ver o fim desta secção.
Motor em **`mtgvault/confirmado.py`**; interruptor em `colecao_config.json →
revalidacao.foto_manda`; CLI `py -m mtgvault.cli foto [mostrar|conflitos|manda
on|off]`; testes em `tests/test_foto_manda.py` (26 casos) e a prova de que
chumbam em `tests/_chumba_foto_manda.py` (9 alvos, 16 pares medidos).

- **O QUE ISTO NÃO É: apagar.** As **737 linhas / 1 678 cartas** ficam na base,
  marcadas «sem foto». A regra dele de 2026-09-09 mantém-se — *nada se apaga* —
  e por isso o **`collection.jogaveis()` NÃO se tocou**: uma cópia sem foto
  continua a ser uma cópia da colecção, continua a aparecer na Galeria e nos
  Binders e **continua a valer dinheiro no total**. *Sem foto* quer dizer *ainda
  não conta*, nunca *não existe*. O que ela não faz é fechar um slot, descontar
  uma compra ou ir à venda. Tem caso próprio.
- **O PERIGO, e o que se faz contra ele.** Ligar isto a bruto punha a colecção
  dele a valer zero até acabar de fotografar 1 678 cartas, e a app ficava inútil
  durante os dias de trabalho. Por isso **todo o número tem DUAS METADES, lado a
  lado** — «confirmado por foto» e «por confirmar» —, e quem as compõe é o
  **`confirmado.metades()`, num sítio só**: duas somas ao lado davam duas
  respostas à mesma pergunta (a lição do `event_tier`, do `e_foil` e do
  `precos.sql()`). O `metades()` **levanta** (`MetadesQueNaoSomam`,
  `AssertionError`) se as duas não somarem o total — uma metade perdida pelo
  caminho é meia verdade com cara de verdade. E cada página leva a **linha
  honesta** (`confirmado.frase`): *«0 de 1 678 cartas confirmadas por foto»*,
  que é o que ela diz hoje.
- **A DECISÃO é «o deck está completo?», e essa usa só o confirmado.**
  `s["pct"]`/`s["tenho"]` passaram a ser a metade confirmada; o físico fica em
  **`pct_fisico`/`tenho_fisico`**, e as duas vão sempre juntas ao payload. Medido
  na base de 02/10: Stiflenought **100 % → 23 %**, Pauper 100 % → 1 %, Blue Farm
  96 % → 0 %. É duro de propósito, e é por isso que a barra de cada caixa leva
  *«17 de 75 confirmadas por foto · 75 na gaveta — faltam 58 fotos»* por baixo.
- **A FALTA PARTE-SE EM DUAS, E ESTA É A DECISÃO MAIS CONSEQUENTE QUE É MINHA.**
  `comprar` continua a ser o que ele **não tem** — tapa-se com a CARTEIRA — e a
  metade nova é **`fotografar`**, o que ele tem na caixa e ainda não provou —
  tapa-se com a CÂMARA. A leitura literal de *"as decisões usam só o
  confirmado"* punha as duas no `comprar`, e a lista de compras passava a mandar
  comprar **687 cópias que estão em casa**: 1 678 cartas por fotografar contra
  370 compras a sério. Isso é o contrário do que ele pediu ao dizer *"ter que
  tirar a foto para atualizar"* — a foto é o gesto que falta, não a compra.
  Desfaz-se numa linha (`_totais_do_slot`), e fica dito.
- **A FOTO MANDA NA ALOCAÇÃO, e é EXCLUSIVA** (`confirmado.alocar_por_foto`). A
  pasta da foto decide o deck: `Colocar fotos da coleção aqui\<deck>\` → aquele
  deck; `Extras (fora dos decks)\` → **sem deck** (a alocação sai). O que estava
  registado noutro deck **sai**, com linha em **`data/foto-manda.log`**. É a
  inversão do ponto 5 de 2026-09-09 (*"um registo não lava uma correcção"*):
  hoje é a FOTO que ganha ao registo, e o algoritmo de alocação passa a
  **SUGERIR** — continua a dizer onde a carta devia estar e já não decide onde
  está. Entra no `collection._import_csv` **no fim da cadeia**, de propósito: só
  ali se sabe que cópias a linha tocou, e por isso o *"comprar = fotografar"*
  não é um caminho novo — é esta linha a tratar o passo (iv) como trata os
  outros.
- **QUEM LÊ A PASTA É O `fotosite.origem`, pelo NOME do ficheiro**
  (`site-<slot>-…`, `site-colecao-…`) — e é o `fotos.recolher_das_pastas` de
  01/10 que renomeia a foto da pasta do deck para esse nome. Não se escreveu um
  segundo leitor: *um caminho só, e é o que já estava testado*. **O alvo GLOBAL
  do config NÃO serve aqui**, de propósito: ele é *"a caixa que estou a
  fotografar"* e vale para PREFERIR cópias no passo (0); usá-lo para REESCREVER
  alocações fazia uma foto largada à mão em `pendentes/` mudar o deck de uma
  carta por causa de um botão carregado ontem. Tem caso próprio.
- **NADA SE VENDE SEM FOTO, e é uma OITAVA saída** (`sem_foto`), não um motivo a
  mais dentro das `protegidas` — ordem dele: *"separa os dois motivos na saída,
  que são coisas diferentes"*. «Protegida» é uma decisão **tomada** («não vendas
  isto»); «sem foto» é uma decisão por **tomar** («ainda não sei o que isto é»).
  Corre **depois** das protecções, para que uma shockland sem foto saia com o
  motivo que lhe vale para sempre, e o que cai aqui é a lista accionável:
  *fotografa estas e aparecem na corrida seguinte*. Vai à **cabeça** do «fica de
  fora» da exportação (`venda.FORA`), porque é a única das seis que ele resolve
  com um gesto. Medido: **114 cópias / 1 820,85 €** passam de `venda` para
  `sem_foto` — a lista de venda fica **vazia**, ao cêntimo e sem uma cópia
  perdida pelo caminho.
- **CADA DECK AS SUAS CARTAS: nenhuma alocação dupla nova**
  (`confirmado.exige_alocacao_unica`, `AlocacaoDupla(ValueError)` → 409 com a
  frase em português, como a `VendaDesligada` e a `VendaCongelada`). São **duas
  asserções**: (1) a mesma cópia em dois decks — só morde com a foto a mandar, e
  **nunca** nas que já estavam assim; (2) **mais alocado do que o lote tem** —
  morde SEMPRE, com a regra ligada ou desligada: era já hoje impossível e **nada
  o travava**. A verificação é PRÉ-VOO, antes de uma linha ser escrita, porque
  validar depois obrigava a desfazer um `commit` já feito. Está nos **quatro**
  escritores (`registar_marcadas`, `guardar_arrumacao`, `actualizar_caixa`,
  `encomendas.conciliar` + o `registar_falta`), e há caso que exige que cada um
  PERGUNTE — sem isso o primeiro caminho novo que se esquecesse voltava a criar
  a segunda alocação em silêncio. **Fora da trava, de propósito:** o
  `restaurar_alocacao` (é o inverso de uma escrita de há segundos) e a
  `migracao` (foi ela que criou as duas que existem).
- **OS DOIS CONFLITOS DA BASE DELE FICAM À VISTA E NÃO SE TOCAM** (ordem dele).
  Medidos e confirmados ao exemplar: **cópia 293** (2× Sewer-veillance Cam TMT EN
  foil — Modern 1, Pauper 1) e **cópia 543** (4× Hydroblast ICE PT nonfoil — UW
  Replenish 2, Stiflenought 2). **A premissa da ordem precisa de uma correcção,
  e é a favor dele:** as quantidades **SOMAM** a do lote, por isso hoje **nenhuma
  carta física está em dois sítios** — o que está em dois sítios é a LINHA da
  `copies`, que é um **lote** e não uma carta. São **lotes partidos**, e o
  `conflitos()` di-lo com essas palavras (e separa-os da `sobrealocada`, que
  seria o caso a sério). Continuam a ser um conflito a resolver, e por uma razão
  nova: a partir de hoje é a foto que diz de quem é cada carta, e um lote
  partido precisa de **uma foto em cada pasta** para continuar como está.
- **O PROGRESSO é o ecrã que ele abre todos os dias** (`confirmado.progresso`):
  por deck e no total, cartas confirmadas, por confirmar, e **quanto falta em
  valor**. **Não conta nada por si** — a contagem é a `revalidacao.progresso` de
  20/09, que já parte a colecção por caixa/venda/RL/resto; o que se acrescentou
  foi o EURO de cada metade, pela conta única de 24/09
  (`collection.mapa_precos` + `preco_impressao`). Uma segunda contagem ao lado
  era o `event_tier` outra vez. Abre a `arrumacao.html` (bloco «📷 A foto é a
  verdade», antes da Fase 1, com os conflitos), vai no cabeçalho da Deckboxes e
  no cartão «Cartas na coleção» do Início.
- **AS BÁSICAS FICAM FORA DA REGRA DA FOTO**, e é uma decisão minha. É a mesma
  isenção que já têm das regras de material (2026-09-08): a pilha de Unhinged é
  a granel, nunca foi uma linha da `copies`, e não há nada para fotografar.
  Exigir-lhes foto punha todo o deck permanentemente incompleto por 24
  Snow-Covered Plains que ele tem ali ao lado. É por isso que o
  `tenho_conf_total` de hoje é **95** e não 0: são as básicas dos sete decks que
  as jogam. Desfaz-se numa linha no `allocate`.
  **[CORRIGIDO A 2026-10-02, à tarde]** essas 95 somavam ao `tenho_conf_total`, e
  isso punha o vault a dizer *«95 cartas confirmadas por foto»* num dia em que
  não há **uma única** foto desta campanha — o número certo a responder à
  pergunta errada. Hoje vão numa **terceira parcela** (`tenho_decl`, *contagem
  declarada*) e o `tenho_conf_total` é **0**, que é a verdade; o deck continua a
  fechar, porque o `tenho` soma as duas. Ver «AS REGRAS DE MATERIAL DOS TRÊS
  GRUPOS, E AS DUAS EXCEPÇÕES DAS BÁSICAS».
- **O INTERRUPTOR é `revalidacao.foto_manda`** (**hoje `false`, desde
  2026-10-04** — ver a secção «AS FOTOS FORAM APAGADAS»), na MESMA campanha
  de 20/09 — não se inventou uma segunda. `false` devolve o vault exactamente ao
  que era, e tem caso próprio. É o padrão do `venda.mostrar`.
- **O TECTO DE PLAYSET DO PREMODERN FOI-SE** (ordem dele, no mesmo dia: *"esquece
  a regra do máximo um playset em Premodern: já não vale"*). A chave
  `playset_maximo` saiu do `colecao_config.json` e o `loadout.playset_maximo`
  devolve **sempre `None`** — um `playset_maximo: 4` esquecido num config
  **deixa de ter efeito**, como o `dedicado: false` desde 19/09, em vez de se
  apagar a função e deixar quem a tivesse escrita sem saber porque é que parou.
  Bate-se de frente com *"cada deck tem as suas cartas"*: um tecto contado sobre
  o GRUPO INTEIRO é a última peça da partilha entre caixas, e seis decks que não
  partilham nada não têm por onde dividir quatro cópias. **E obrigou a trocar um
  SINAL:** o `fases.de_conversao` derivava-se desta chave (*"o tecto só existe
  porque as caixas trocam a carta entre si"*) e sem ela responderia «nenhuma
  caixa é de conversão», **em silêncio**, perdendo a ordem de trabalho da Fase 2.
  Passou a ler o `prioridade_por: "pct"` do grupo — que o CLAUDE.md já dava como
  confirmação do outro — e **apanha as mesmas 6 caixas de Premodern**, medido,
  com caso de teste.
- **MEDIDO LADO A LADO, o MESMO `vault.db` nos dois lados** (worktree em
  `_revisao/foto-manda`, cópia da base pela API de backup do sqlite3;
  `_revisao/medir_foto_manda.py`). Preço de referência: modo `market`, cadeia
  `cardtrader → cardmarket`.

  | | main | ramo, `foto_manda: false` | ramo, **a foto manda** |
  |---|---|---|---|
  | `loadout.report` | 1,70 s | 1,67 s | **1,70 s** |
  | fechar tudo | 15 024,83 € | 15 391,58 € | 15 391,58 € |
  | a comprar | 370 | 414 | 414 |
  | a arrumar | 171 | 171 | **171** |
  | confirmadas por foto | — | 95 | **95** (as básicas) |
  | nas caixas (físico) | — | 782 | 782 |
  | **a fotografar** | — | 687 | **687** |
  | venda | 114 c / 1 820,85 € | 114 c / 1 820,85 € | **0** |
  | **sem foto** | — | 0 | **114 c / 1 820,85 €** |
  | protegidas | 144 c / 4 568,57 € | igual | igual |
  | rl_sem_historico | 100 c | 100 c | 100 c |
  | guardar | 10 c / 1 432,95 € | igual | igual |
  | playset bloqueado | **44** | **0** | **0** |
  | conflitos de alocação dupla | (não media) | 2 | **2** |

  **AS TRÊS COLUNAS SEPARAM AS DUAS MUDANÇAS, e é isso que as torna legíveis:**
  - **main → ramo com a regra DESLIGADA** é SÓ o tecto de playset a cair: +44 a
    comprar e **+366,75 €**, e explica-se caixa a caixa (Enchantress +25 /
    +312,21 €, Elves +14 / +47,91 €, Oath +4 / +4,24 €, Replenish +1 / +2,39 €).
    **As outras 13 caixas ficam iguais ao cêntimo**, e a venda, as protegidas, a
    RL e o `guardar` **não mexem um número**. É a prova de que o interruptor
    desligado devolve o vault ao que era.
  - **desligada → ligada** é SÓ a regra da foto: a venda move-se **inteira** de
    `venda` para `sem_foto` (114 c / 1 820,85 €, ao cêntimo e sem uma cópia
    perdida pelo caminho), e aparecem as duas metades. **A alocação não mexe** —
    a arrumar 171 nas três colunas: a foto manda em quem CONTA, não em quem é
    escolhido.
- **O CUSTO DE TEMPO É PEQUENO E MEDIDO.** O `loadout.report` **não mudou**
  (1,70 s contra 1,70 s do `main`): a regra lê o `validado_em` que o `lots()` já
  trazia. O que custa é o PROGRESSO, e só nas duas páginas que o pedem —
  `confirmado.progresso` **0,42 s**, dos quais 0,23 s são o
  `revalidacao.progresso` de 20/09 que já existia; o acréscimo é **0,19 s**
  (o `mapa_precos` e a soma por grupo). O `conflitos` é **0,00 s**.
- **AS PÁGINAS, medidas com o `webapp.py` a correr e o JS a sério**
  (`_revisao/medir_paginas.py`: levanta o servidor num porto livre sobre a cópia
  da base, pede cada página e cada ficheiro de dados, e corre
  `node tests/abrir_pagina.js` com os `fetch` a ir mesmo ao servidor):

  | | código | 1.º ms | 2.º ms | bytes |
  |---|---|---|---|---|
  | `index.html` | 200 | 10 | 5 | 43 653 |
  | `deckboxes.html` | 200 | 5 | 9 | 70 176 |
  | `arrumacao.html` | 200 | 12 | 5 | 72 621 |
  | `metagame.html` | 200 | 8 617 | 5 | 209 201 |
  | `deckboxes.js` | 200 | 41 | 6 | 259 186 |

  **31 ficheiros de dados, todos 200**, nenhum erro. A segunda passagem está
  toda em **1–29 ms**; na primeira só duas pagam o cálculo a frio —
  `arrumacao/candidatos.json` **9 645 ms** e `deckboxes/arrumar.json` 5 866 ms —,
  e o `metagame.html` a frio **8,6 s**. São os mesmos pedidos que o aquecedor de
  01/10 (`webapp.aquecer`) paga antes de ele abrir a página, e ficam abaixo do
  tecto de 25 s do `webapp.ESPERA_DADOS`. **O JS desenhou nas quatro**, sem uma
  única mensagem de `paginas.erroDados`: Deckboxes 16 contentores, Arrumação 6.
  O Início e o Metagame são desenhados no servidor e por isso o harness não tem
  contentores para contar neles — estão nos 200 com o HTML completo.
- **DUAS COISAS DE 2026-09-20 FICARAM DEGENERADAS, e é melhor estar escrito:**
  (a) o filtro **«📷 Só validadas»** da aba Vender e da Feira, e (b) a coluna
  **`Foto`** do CSV de stock (`csv_validadas`, `exportar --so-validadas`).
  Deixaram de cortar o que quer que seja — nada chega à venda sem foto, logo a
  coluna diz sempre `validada` e o `copias_por_revalidar` é sempre 0. **Não se
  apagaram**: são elas que mantêm o CSV honesto no dia em que o `foto_manda` for
  desligado. Os dois casos de teste passaram a afirmar isso, com a data.
- **E O GRUPO «VENDA» DA ABA REVALIDAÇÃO DESAPARECEU**, pela mesma lógica: nada
  na lista de venda precisa de foto, porque sem foto não chega lá. As cópias que
  ele vai vender fotografam-se **onde estão** (Caixa RL e Colecção, que
  continuam na aba) e entram na venda depois. Consequência a saber: o botão
  «Tirar fotos» do alvo `venda` — e, com ele, o plano da **Fase 4** de 01/10 que
  «se abriria sozinho a 12/10» (hoje só abre quando ele destrancar a trava à
  mão) — não tem nada para abrir enquanto a colecção não estiver fotografada.
  Tem dois casos de teste a dizê-lo.
- **A VENDA OFERECE PRIMEIRO O QUE JÁ TEM PROVA, e sem isto a regra não
  funcionava.** O excedente escolhia-se pelo pior estado e podia cair TODO nas
  cópias sem foto: fotografar 3 de 7 Get Lost não desbloqueava uma única venda.
  A chave nova é a PRIMEIRA do `sorted` do `sell_list`, e apareceu a medir — foi
  o `test_feira.caso_so_validadas` a apanhá-la. É também o que ele pediu a
  2026-09-20: *"o que eu for vender também vai com foto"*.
- **POR DECIDIR POR ELE, e é a parte que vale a pena ler primeiro:** (a) a
  separação `comprar` / `fotografar` é minha e é a mais consequente — com a
  leitura literal, o `comprar` passava de 414 para ~1 100 e o *fechar tudo* para
  dezenas de milhares de euros em cartas que ele tem em casa; (b) as **básicas**
  isentas da foto (são os 95 «confirmados» de hoje); (c) os dois **conflitos**
  esperam a foto dele — e são **lotes partidos**, não cartas em dois sítios;
  (d) o tecto de playset levou **44 cópias / 366,75 €** à lista de compras — se
  não era isso que ele queria, é uma linha no config.

**O ESTADO DAS CARTAS E OS VERSOS (André, 2026-10-03, à letra).** *"procuras como
são avaliadas as cartas, depois com base nas minhas próprias fotos, vais
melhorando o teu critério"* e *"verso as dos decks e as que são para guardar, para
já"*. Motor em **`mtgvault/estado.py`**; critério em **`data/estado-criterio.md`**;
colunas `copies.condition_origem`/`condition_em`/`condition_motivos`/`verso_path`
e tabela `condition_log`; config em `precos.estado`; passo `estado-cartas` do
`daily`; endpoint `POST /api/estado`; bloco na `arrumacao.html`; CLI
`py -m mtgvault.cli estado [mostrar|definir|corrigir|lista|impacto|criterio|
factores|exemplos]`. Testes em `tests/test_estado_versos.py` (27 casos) e a prova
de que chumbam em `tests/_chumba_estado.py` (9 alvos / 14 pares medidos).

- **O BURACO: as 737 linhas diziam TODAS `NM`** — as 1 678 cartas, duais de
  Revised de 1994 incluídas. **Não era uma medição**: era o valor por omissão do
  `add_copy` que nunca ninguém mexeu. E era pior do que parecia, porque a cadeia
  de preços **não tinha dimensão de estado nenhuma** (a `price_latest` tem
  `low`/`trend`/`avg30` e mais nada): mesmo que o estado se registasse, não havia
  onde ele entrasse no cálculo, e os **136 168,42 €** da colecção estavam somados
  como se trinta anos de cartão estivessem impecáveis.
- **A ESCALA É A DO CARDMARKET, porque é lá que ele vende**: `MT NM EX GD LP PL
  PO`. As definições estão transcritas **da fonte** para o
  `data/estado-criterio.md` — e a página oficial não as serve em texto: a tabela
  de comparação é um **SVG** e os sete escalões vêm num **acordeão** cujo corpo
  está no payload do Nuxt. Leram-se de lá, à letra, a 2026-10-03. Duas notas que
  custaram a leitura: a página escreve **«Mint (M)»** e o código da API e das
  exportações de stock é **`MT`** (aqui o canónico é o `MT`, que é o que ele pediu
  e o que o `venda-stock.csv` escreve, e o `M` é um alias); e **a palavra
  «Played» é dois escalões** — o `PL` do Cardmarket chama-se *Played* e o
  americano *Played* é o `LP` deles. Por isso há **duas portas**:
  `estado.normalizar` (ganha o nome do Cardmarket, que é a escala do vault) e
  `estado.do_cardtrader` (a escala americana das ofertas). Tem caso de teste.
- **O FACTOR DE PREÇO É MEDIDO, NÃO INVENTADO — e a fonte dá-o.** A ordem era
  explícita (*"não inventes percentagens tuas: procura o que a fonte já dá por
  estado e usa isso"*), e dá:
  - o **CardTrader traz o estado em CADA oferta** (`properties_hash.condition`) e
    usa a escala **americana**. Sondado a 2026-10-03 em 23 edições reais da
    colecção dele: `Near Mint` **402 886** ofertas, `Slightly Played` 245 246,
    `Moderately Played` 135 137, `Played` 66 647, `Poor` 15 625 (`Mint` e
    `Heavily Played`: **zero**);
  - o **Cardmarket publica a equivalência**, no texto de cada escalão: EX ≡
    *Slightly Played*, GD ≡ *Moderately Played*, LP ≡ *Played*, PL ≡ *Heavily
    Played*, PO ≡ *Poor*. **É esta a ponte**, e não um palpite meu.

  Logo o factor é a **razão entre a mediana das ofertas de um escalão e a mediana
  das ofertas Near Mint da MESMA impressão**, sobre **10 004 pares** (impressão ×
  acabamento) e 865 541 ofertas. Está no config (`precos.estado`), com a data, a
  amostra e a origem, e altera-se à mão.
- **E DEPENDE DO PREÇO — foi medido, e é a parte que decide o dinheiro.** Numa
  carta de 0,40 € um *Slightly Played* vale **0,98** do NM (há pisos de preço e
  portes a dominar); numa de 100 € ou mais vale **0,776**. Por isso a tabela tem
  **bandas** (<1, 1–5, 5–20, 20–100, ≥100 €): um número só errava por **20
  pontos** exactamente onde está o dinheiro dele — a Reserved List e as duais. A
  tabela é **monótona em todas as bandas** (um escalão pior nunca vale mais), e
  há teste que o exige.

  | | <1 € | 1–5 € | 5–20 € | 20–100 € | ≥100 € |
  |---|---|---|---|---|---|
  | EX | 0,983 | 0,828 | 0,837 | 0,813 | **0,776** |
  | GD | 0,791 | 0,648 | 0,629 | 0,642 | 0,593 |
  | LP | 0,676 | 0,559 | 0,546 | 0,524 | 0,540 |
  | PL\* | 0,675 | 0,543 | 0,512 | 0,504 | 0,504 |
  | PO | 0,674 | 0,527 | 0,477 | 0,484 | 0,468 |

  \* **o PL é o único interpolado**, e diz-se (`estado.APROXIMADOS`, na página e
  no relatório): o Cardmarket mapeia-o para o americano *Heavily Played* e o
  CardTrader **não tem uma única oferta nesse estado**. Um número aproximado com
  cara de número medido é a mentira que esta secção existe para não contar.
- **O NEAR MINT VALE 1,000, E É ISSO QUE TORNA ISTO SEGURO.** É a âncora da
  medição, e por isso **ligar isto não mexeu um cêntimo**: medido lado a lado com
  o `main` e o MESMO `vault.db` (worktree em `_revisao/main-estado`) — fechar tudo
  **15 391,58 €**, 414 a comprar, 316 a arrumar, valor **136 168,42 €** (low
  100 721,39 €, média 118 444,90 €), 1 678 cartas, 4 sem preço, as **nove saídas
  da venda** e as **17 caixas** iguais ao cêntimo e à percentagem. O valor só
  muda no dia em que um escalão for mesmo atribuído.
  - **Uma diferença de 0,29 € apareceu e foi corrigida**, em vez de explicada: o
    `aplicar` arredondava a 2 casas mesmo com factor 1,0, e o cenário `media`
    (que é `(low+trend)/2` e pode ter três casas) mexia em cêntimos. **Sem
    factor, sem arredondamento.**
- **DUAS APROXIMAÇÕES, ditas em voz alta:** (1) o preço de referência de hoje é a
  mediana das ofertas em `Mint`/`NM`/`Slightly`/`Moderately` (o crivo
  `precos.ESTADOS_OK`, do riftvault) e **não** um preço só de NM — tratá-lo como
  o preço NM deixa o NM ligeiramente SUBavaliado, que é o lado conservador e é
  melhor do que inventar uma majoração; (2) o PL, acima.
- **«POR OMISSÃO» DEIXOU DE PODER PASSAR POR MEDIDO.** O `NM` que lá está **não
  se apagou nem se mudou de valor** (a regra dele de 09/09): ganhou
  `condition_origem = 'omissao'` e, com ela, a frase *«por omissão, nunca
  verificado»*. Quem decide se um juízo conta é **`estado.medido()`, num sítio
  só** — e há teste que varre o código à procura de quem compare a origem à mão
  (o `db._migrate` é a única excepção declarada: é ele que a escreve).
- **O QUE ESTÁ EM JOGO: 21 416,82 € (15,7 %).** `py -m mtgvault.cli estado
  impacto`, na base de 2026-10-03: se a Reserved List, as duais, as shocklands e
  as fetchlands caíssem **um escalão**, a colecção passava de 136 168,42 € para
  **114 751,60 €** — 305 cartas em 119 linhas. As piores: Gaea's Cradle (JGP)
  −1 276,94 €, 3 Gaea's Cradle (USG) −1 260,21 €, 4 Volcanic Island (3ED)
  −962,52 €, 3 Mox Diamond (STH) −928,74 €, 7 Grim Monolith (ULG) −841,47 €.
- **OS VERSOS: o emparelhamento é o NOME DO FICHEIRO, e o par é o RADICAL.** A
  ordem dele é sobre o gesto — *"põe as até 4 cartas, fotografa, VIRA-AS NO SÍTIO
  sem mexer na disposição, fotografa outra vez. Mesma ordem, mesmas posições. O
  emparelhamento faz-se por isso, não por ele escrever nada"* —, e por isso o par
  tem de ser **deduzível** e **conferível**. É
  `site-<slot>-<data>-<n>[-c<id>]`**`-v`**`.<ext>`, e o par é a MESMA string sem o
  `-v` (`fotosite.par_da_frente`/`nome_do_verso`, inversos, com teste). O `-v` vai
  depois do `-c<id>` para o radical da frente ser prefixo exacto do do verso.
  **Três escritores, e nenhum adivinha o que não sabe:**
  1. o botão **📷 Frente e verso** da página (`POST /api/foto?pares=1`): os
     ficheiros vêm aos pares pela ordem de captura e o segundo herda o `n` do
     primeiro — o par **nasce feito**. Um número ímpar é recusado (409), nos dois
     lados (o JS trava-o antes de enviar, o servidor trava-o antes de escrever):
     metade de um par não é prova de nada.
     **Numa caixa são DOIS botões e não um** (`deckboxes.tirarFotosHTML`): o dos
     pares em destaque e **📷 Só a frente** ao lado, para uma frente avulsa. Nos
     alvos que não são deck (`venda`/`rl`/`coleccao`) só aparece o segundo — ali
     é frente só, por decisão dele. **Isto faltava e foi apanhado na revisão
     final:** o botão único de 21/09 mandava sempre frentes, e por isso uma foto
     tirada no site **nunca ganhava verso** — o estado dela ficava «por
     verificar» para sempre, sem um único erro. Tem caso de teste nas duas
     pontas (o `data-pares` no HTML e o `?pares=1` lido pelo endpoint);
  2. a **recolha da pasta do deck** (`fotos.recolher_das_pastas`): empareilha pela
     **ordem de captura** (mtime, depois nome), que é exactamente o gesto físico.
     Três decisões que a tornam segura — o grupo é a **pasta** onde o ficheiro
     está (uma subpasta `lote1` empareilha sozinha); **se UMA foto do grupo ainda
     está no sossego, o grupo INTEIRO espera** (emparelhar metade de um lote a ser
     copiado trocava todos os pares a partir do que faltava); e um lote **ímpar**
     deixa a última sem verso e **di-lo** (`sem_verso`), em vez de inventar um par;
  3. **o leitor confere, e a leitura ganha ao nome.** Todos os versos de Magic são
     iguais, por isso *«isto é um verso?»* é a pergunta mais fiável que se lhe
     pode fazer: o CSV ganhou `verso_ok` e **sem esse `sim` não se grava escalão
     nenhum**. E uma foto `-v` em que o leitor VIU CARTAS é um par que não bateu:
     **as cartas entram** e o escalão não se grava. Perder cartas por causa de um
     sufixo era o pior resultado possível. Tem caso de teste.
- **O VERSO SERVE PARA O ESTADO, NÃO PARA IDENTIFICAR** — e isso está escrito no
  código (`estado.PORQUE_VERSO`), no critério, no `esperadas.md` e na página:
  *todos os versos de Magic são iguais*. **Com verso, o escalão sai de lá; sem
  verso, o estado fica «por verificar» e não se inventa.** Uma linha que traga
  `condition` sem verso confirmado **não é aplicada**: fica no `condition_log` com
  `aplicado = 0` e o motivo — não se perde, e não mexe num cêntimo. E uma linha
  que venha de uma FOTO entra com `NM` no `add_copy`, nunca com o `condition` do
  CSV; num CSV **à mão** (sem foto) a coluna continua a valer, porque aí quem a
  escreveu foi ele.
- **OS EXTRAS: FRENTE SÓ, E A LISTA CURTA DEPOIS.** Decisão dele, e a razão é a
  dele: *"ele NÃO pode decidir a verso-ou-não com a carta na mão, porque no
  momento em que fotografa os extras ainda não sabe o que vai guardar nem o que
  vai vender"*. Logo a pasta `Extras (fora dos decks)` **não empareilha** — cada
  foto é uma frente — e **o sistema decide depois**: a `estado.lista_curta` marca
  quem precisa de verso (Reserved List, as dez duais, shocklands, fetchlands, as
  quatro listas **derivadas do catálogo** pelo `fases`) e dá-lhe uma lista para
  voltar lá **uma vez**. Medida a 2026-10-03: **80 fotos / 255 cartas /
  82 043,96 €**. A venda entra pelo MESMO caminho no dia em que ele a voltar a
  ligar (`inclui_venda` segue o `venda.mostrar`, hoje `false`) — é o *"e mais
  tarde o que for para venda"* dele, e não é uma linha nova.
- **O CRITÉRIO APRENDE, E É O DELE.** Cada escalão fica gravado com a FOTO, o
  escalão e os MOTIVOS escritos (com a ZONA: *«branco no canto inferior
  esquerdo»*). Quando ele corrige, a correcção fica como **exemplo rotulado** no
  `condition_log` — a foto, o que eu disse, o que ele disse e **o que me
  escapou** —, **a correcção dele GANHA sempre** (um juízo meu posterior é
  recusado e fica registado com `aplicado = 0`, que é o que torna a taxa de acerto
  calculável), e o `data/estado-criterio.md` cresce com a secção **«Aprendido com
  o André»**, datada, **só** com o que veio de correcções dele. O passo que avalia
  lê `estado.para_avaliar` — o critério + os **erros repetidos** (contáveis:
  `sentido` × `zona`, pelas palavras do Cardmarket; *«já fui corrigido 3× por
  estar optimista com as bordas»*) + as últimas correcções —, e esse texto vai
  dentro do `pendentes/esperadas.md`, que é o que o Claude das fotos já lê. A
  **taxa de acerto** (`estado.acerto`) é como se sabe se está a melhorar.
- **O FICHEIRO DO CRITÉRIO VAI NO `git add` do `daily.yml` E NO `EXTRA_COMMIT` da
  tarefa `mtgvault-daily`**, pela razão do `arquetipos.json`: se as correcções
  dele só existissem no PC, a corrida do GitHub avaliava com um critério de ontem.
- **O ESCALÃO VALIDA-SE ANTES DO BACKUP** (`webapp._estado`), e é a regra do
  `_exige_venda` de 01/10: *«um pedido recusado não deixa um ficheiro de backup
  atrás dele»*. Um `.db` deste vault são **96 MB**, e uma página aberta ontem no
  telemóvel pode mandar um escalão que já não existe — um por toque enchia o
  `data/backups/`. **Medido contra o 8771 a sério** (e não assumido,
  `_revisao/provar_409_sem_backup.py`): cinco pedidos recusados — `Mint+`, `9.5`,
  vazio, texto livre e um sem `copy_id` — dão **409 com a frase em português** (a
  escala inteira por extenso) e deixam **zero** backups novos.
- **O QUE SE DIZ AO ANDRÉ, na página e no guia das fotos**, para ele não contar
  com o que não vai ter: numa foto de telemóvel **vê-se** vincos, branqueamento de
  bordas e cantos, riscos visíveis e desgaste de jogo — e dá para um escalão
  defensável entre **NM, EX, GD e LP** com a razão à frente; **não se distingue NM
  de Mint** (por isso o `MT` não se atribui por foto) e riscos finos de superfície
  não aparecem; **a luz pesa mais do que a resolução** (o flash de frente
  *esconde* o desgaste das bordas, a luz difusa num ângulo ligeiro *mostra-o*); e
  o escalão é **sempre uma estimativa com motivo escrito**, nunca uma
  classificação certificada.
- **UM DEFEITO DE DESEMPENHO ANTERIOR A ISTO, apanhado com o cProfile e
  corrigido:** o `sources._config()` fazia `Path(__file__).resolve()` a CADA
  leitura do config — e o config lê-se milhares de vezes por relatório (o
  `precos.modo`, o `precos.fontes`, o `estado.factor`, todos por cópia). Contado
  (é determinista, ao contrário dos segundos nesta máquina): **3 111
  `Path.resolve()` = 6 222 chamadas ao `nt._getfinalpathname` por
  `loadout.report`**, e **zero** depois. O caminho resolve-se uma vez no import
  (`_RAIZ_CFG`); o `MTGVAULT_CONFIG` continua a ler-se a cada chamada, porque os
  testes trocam-no em memória. Com isto e com a cache da tabela de factores
  (`_TABELA_CACHE`, pela identidade do bloco do config) o bloco do estado da
  página das fases passou de **11,18 s a 1,63 s**; e o `fases.relatorio` passou a
  aceitar a cache de fora, para o mapa de preços (86 480 linhas da
  `price_latest`) e as listas de terras não serem construídos duas vezes na mesma
  página.
- **AS PÁGINAS, medidas com o `webapp.py` a correr e o JS a sério**
  (`node tests/abrir_pagina.js` com os `fetch` a ir ao servidor): **as 11 páginas
  e o `deckboxes.js` a 200**, **222 ficheiros de dados todos a 200**, nenhum erro
  de dados. A parte nova (`arrumacao/estado.json`, 31 KB) responde em **14 ms**; a
  pior de todas é o `arrumacao/candidatos.json` a frio, **12,0 s**, abaixo do
  tecto de 25 s do `webapp.ESPERA_DADOS`. O JS desenhou nas duas páginas com JS
  (Deckboxes 16 contentores, Arrumação 6) e o bloco do estado está lá com as
  quatro frases que têm de estar.
  **Nota sobre os tempos**: o `webapp.py` vivo no 8771 tem um aquecedor que
  recalcula quando o config muda, e a medição levanta um SEGUNDO servidor — por
  isso os segundos variam entre 1,6 s e 12 s na mesma árvore. Os números que não
  dependem disso (as contagens de chamadas, os euros, as cópias) são os que se
  usaram para decidir.
- **POR DECIDIR POR ELE, e é o que vale a pena ler primeiro:** (a) **o factor
  aplica-se ao escalão que está gravado, seja qual for a origem** — se diz EX, a
  carta é EX e o dinheiro di-lo; a provenance mostra-se ao lado, e não se desconta
  duas vezes pela mesma dúvida; (b) o **`MT` não se atribui por foto** (não se
  distingue de NM numa foto de telemóvel) — só à mão, por ele; (c) as **bandas de
  preço** são cinco e foram escolhidas por mim a partir da curva medida: se
  preferir um número só por escalão, é uma linha no config; (d) a lista curta
  inclui **todas as cópias** de uma carta que precise de verso, não só as caras.

**A JANELA DO CONSENSO: A PESQUISA DE DECKS COMEÇA NO DIA DO SET (André,
2026-10-03, à letra).** *"faz a pesquisa de decks só a partir do dia que reality
fracture ficou disponível"*. Motor em **`mtgvault/sources.py`**
(`regras_consenso`/`consenso_desde`/`consenso_sql`/`texto_amostra`/
`frase_janela_rodape`, e o `counting_sql`/`lista_conta` a levarem o corte **por
omissão**); config em `colecao_config.json → consenso`; passo `janela-consenso`
do `daily`. Testes em `tests/test_janela_consenso.py` (15 casos) e a prova de que
chumbam em `tests/_provar_janela.py` (**16 de 16 pares**, um processo por par);
relatório em `ai-pc/work/saidas/decks-desde-fra-2026-10-03.txt`.

- **A DATA É A DO MTGO E NÃO A DO PAPEL: 2026-09-29.** O Reality Fracture entrou
  na loja do Magic Online nessa terça (10:00 PT / 17:00 UTC,
  <https://www.mtgo.com/news/mtgo092226>); em papel só saiu a **02/10**. O
  metagame que o vault recolhe é quase todo de MTGO, e os dados dele confirmam a
  régua: em Modern, **0 %** das listas até 28/09 jogam uma carta que estreia no
  `fra`, **5,0 %** a 29/09 (só os eventos depois daquela hora) e **21,1 %** a
  30/09.
- **AS LISTAS DE 26 E 27/09 NÃO SÃO FALSOS POSITIVOS DA DETECÇÃO — SÃO PAPEL.**
  Três listas de Modern (1 a 26/09, 2 a 27/09) trazem cartas do set: *Seasoned
  Cryomancer*, *Roiling Canopy*, *Ajani's Anguish*. Verificado impressão a
  impressão: as três **estreiam mesmo** no `fra` e não existem em nenhum set
  anterior. São do fim-de-semana de **pré-lançamento**, e dois eventos desse
  fim-de-semana dizem-no no nome — *"Legacy event - SideEvent FRA Prerelease"*
  (26/09) e *"Duel Commander event - Watermelon Cup Win a FRA box!"* (27/09). As
  **37** listas anteriores ao corte com carta do set são **todas** `mtgtop8` /
  `Presencial`. O corte deixa essas três de fora, e é o preço de a regra ser uma
  data que se lê e se confere em vez de *"depende da fonte"*.
- **A PERGUNTA VIVE NUM SÍTIO SÓ, e a omissão é o corte.** `counting_sql(fmt,
  alias, consenso=True)` — a omissão é `True` de propósito: a primeira consulta
  nova de consenso que não pense nisto fica com a janela certa. Por aí passam, sem
  uma linha nova em cada um, o agrupamento de Modern (`analysis._fetch_lists` →
  `rebuild_archetypes`/`rebuild_roles`), o consenso por comandante, a lista de
  cada caixa de `fonte: consenso`, o top-N do Metagame, a Cobertura, o Showcase e
  os nomes. Tem teste que varre o código à procura de quem volte a ler a chave
  `consenso` por fora do `sources`.
- **A EXCEPÇÃO DO PREMODERN É UMA DECISÃO MINHA, com a medida por trás.** O
  Reality Fracture **não é legal em Premodern** (o formato acaba no Scourge,
  2003): das **978** listas de premodern da base, **ZERO** jogam uma única carta
  do set, contra 21 % em Modern no dia seguinte ao lançamento. Sem a excepção o
  corte não respondia a pergunta nenhuma e **três caixas dele ficavam sem lista**
  na véspera do RC de Ghent — Elves 23→0 listas, Oath of Druids 30→4,
  Ill-Gotten Gains 3→0. Tirar `premodern` do `consenso.excepcoes` é o corte cego.
- **A RESERVA DA VENDA FICOU NA JANELA DELA (30 dias), e o conflito mediu-se em
  vez de se resolver** (ordem dele: *"deixa a reserva como está e assinala o
  conflito"*). São duas perguntas: o consenso pergunta *"como é que este deck se
  joga agora"* e a reserva *"que carta é que EU joguei no último mês e por isso
  não devo vender"* — a segunda é sobre o PASSADO dele. **Medido** com a mesma
  base e `reserva.janela_dias` = 4: a lista VENDER crescia **+426 cópias /
  +11 796,69 €** e a R5 sozinha caía de 487c/13 059,78 € para **27c/816,30 €**. A
  R5 não passa pelo corte **por construção** (`ids_por_assinatura(so_que_contam=
  False)` nem chama o `counting_sql`), e a `fases.assinatura_derivada` leva
  `consenso=False` explícito — com o corte, as frequências caíam abaixo do
  `ASSINATURA_MIN` (3) e a assinatura derivada de uma caixa desaparecia em
  silêncio. Dois casos de teste e dois alvos no `_chumba_janela`.
- **SEGUIR UMA LISTA NÃO É CONSENSO**: o `my_decks._conta` leva `consenso=False`,
  com o porquê escrito. Ali já se pede *"a mais recente"*, e o corte não a torna
  mais recente — só pode fazê-la desaparecer. Medido: com o corte, o *Grinding
  Station* (28/09) e o *Jeskai Lessons* (27/09) ficavam sem lista nenhuma, sem um
  número novo a trocar. Os decks que ALIMENTAM caixas sobrevivem aos dois lados
  (Greasefang 01/10, Stiflenought do Luffy 01/10).
- **«NÃO DÁ PARA DIZER» EM VEZ DE UM NÚMERO BONITO E FALSO** (ordem dele, à
  letra). Abaixo do mínimo de listas a **percentagem não sai do motor**
  (`consenso.consenso` põe `pct: None` e `papel: ""`): fica o NÚMERO DE LISTAS,
  que é um facto, e a frase do `sources.texto_amostra` — a mesma em todas as
  superfícies. A página dos Comandantes mostra-a em **letra grande**
  (`.aviso.grande`), desenha as cartas por nº de listas e **não atribui papéis**
  (núcleo/flex/raro são cortes por percentagem, e sem percentagem fiável não há
  papel). O `loadout._cards_from_consensus` passou a usar as mesmas palavras.
- **A JANELA APARECE ONDE ELE A LÊ**: chip *«desde 2026-09-29»* no cabeçalho dos
  Comandantes, parágrafo no rodapé dos Comandantes, da Cobertura e do Showcase
  (uma função só, `sources.frase_janela_rodape`, para duas páginas não
  discordarem da data), e o passo `janela-consenso` no `daily` — um log de um dia
  com corte era igual ao de um dia sem. **O `_TMPL` da Cobertura e do Showcase
  passou a FUNÇÃO** (`_tmpl()`), pela razão de 2026-09-25: uma constante de módulo
  ficava com a resposta que o config deu a quem importasse primeiro.
- **MEDIDO LADO A LADO, o MESMO `vault.db` em quatro passagens** (A: sem janela =
  o `main`; B: com a janela; C: com a janela também na reserva; D: sem janela e
  sem as três caixas que ficam sem lista — para separar as causas):

  | | A: sem janela | B: com a janela |
  |---|---|---|
  | fechar tudo | 14 714,05 € | **10 004,12 €** |
  | a comprar | 412 | **272** |
  | a arrumar | 318 c / 173 linhas | **238 c / 134 linhas** |
  | protegidas | 1 000 c / 115 580,17 € | **1 086 c / 117 829,76 €** |
  | VENDER | 678 c / 21 307,38 € | **592 c / 19 057,79 €** |

  **TRÊS CAIXAS FICAM SEM LISTA**, e é o corte a dizer a verdade (ainda não há
  consenso pós-set delas): **Bant Airbend** (6→0 listas), **Engineer Welder Cam**
  (35→2) e **Aluren** (29→0). O **Modern — Affinity** fica com 14 listas em vez
  de 89 e a lista com uma carta a menos (32→31). **As outras 13 caixas ficam
  iguais ao cêntimo e à percentagem**, as cinco de Premodern incluídas.
  **O delta explica-se ao cêntimo**: −4 695,14 € são as três caixas a ficarem sem
  lista e −14,79 € o consenso do Weapons a encurtar. E o **Pioneer passa de 66 a
  62 a comprar (−29,84 €) e NÃO é a janela** — é a Bant Airbend a deixar de
  alocar primeiro dentro do grupo SPML: provado na passagem D, onde o Pioneer dá
  exactamente os mesmos números que em B.
  **A lista de venda ENCOLHE** (as cartas das três caixas passam de *"está na
  lista"* para *"está na reserva"*: a R5 sobe de 400c para 487c). A **única**
  protecção que o corte reduz é a do Cloud (Duel Commander), por via do consenso
  por comandante ficar em 7 listas: a reserva automática dessa caixa cai de 106
  para 13 cartas — **12 cópias / 115,08 €** —, e a página di-lo.
- **O QUE ISTO RESPONDE PARA GHENT (9-11/10):** o **Weapons NÃO mudou com o
  set** — **zero** cartas do Reality Fracture nas 89 listas e zero nas 14 de
  29/09 em diante; o maindeck de consenso é **idêntico** nas duas janelas e mexem
  quatro lugares de sideboard (sai 1 Cursed Totem; Blood Moon 1→2, Galvanic Blast
  3→2, Mystical Dispute 1→2). O nome da fonte muda de *"Pinnacle Affinity"* para
  **"Affinity"**. O **Oswald fica com ZERO listas** (tinha 12) e o **Cloud com 7**
  (tinha 41): nos dois a resposta é *«não dá para dizer»*. Em Modern, quem subiu
  foi o **Ruby Storm** (+4,0 pontos, 4,1 % → 8,0 %, 25 listas), o único dos que
  subiram que joga carta nova — o **Twinned Vision**, a carta do set mais jogada
  no formato (15 das 311 listas, até 4 cópias); a seguir Boros Aggro +1,9, Amulet
  Titan +1,9 (Roiling Canopy) e 4/5c Aggro +1,9. Desceram o Broodscale
  Bloodchief −4,9 (continua o nº 1, 17,1 % → 12,2 %), UR Cutter Prowess −3,9,
  Eldrazi Ramp −2,9, Boros Ponza −2,7, UrzaTron −2,6 e Pinnacle Affinity −2,2.
  **Ressalva honesta:** das 311 listas de Modern desde o corte, **82 ainda não
  têm nome** (61 porque o agrupamento, que corre no daily, ainda não as apanhou;
  21 porque o grupo delas não tem uma única lista nomeada pela fonte) — a linha
  *«(sem nome)»* da tabela é isso e não um arquétipo.
- **A VIGIA continua a ZERO e NÃO foi aberta ao Duel Commander:** «Kasmina,
  Enigma Sage» tem **0** listas em Modern ou Pioneer — e 0 na base inteira, sem
  filtro; «Jace's Machinations» tem **0** nesses dois formatos e 3 avistamentos,
  todos em `duel-commander` (30/09, 01/10, 02/10) e nunca com a Kasmina. O
  `cartas_vigiadas` continua `["modern", "pioneer"]`.
- **UM TESTE ANTIGO TEVE DE SER CORRIGIDO, e não mascarado.** O
  `test_integration.py` lia o config **a sério** e semeia decklists espalhadas por
  20 dias de propósito (para exercitar a janela de 30 dias do agrupamento): com o
  corte, as 35 listas passavam a 10, os dois arquétipos trocavam de ordem e o
  `Lightning Bolt` desaparecia do núcleo. Passou a correr com a janela
  **desligada**, com o porquê escrito lá — quem tranca a janela é o
  `test_janela_consenso`.
- **POR DECIDIR POR ELE:** (a) as **duas janelas** — juntá-las punha +426 cópias
  e +11 796,69 € na venda, e é `reserva.janela_dias`; (b) a **excepção do
  Premodern**, que é minha; (c) as **três caixas sem lista** — se preferir que uma
  caixa sem amostra fique com a lista da janela longa em vez de ficar vazia, é uma
  decisão dele e não se tomou; (d) o **Oswald com zero listas** é o deck de
  Ghent, e a assinatura dele continua a apanhar listas que o mtgtop8 chama
  *"Pinnacle Affinity"* (o aviso de 02/10, ainda de pé); (e) o **`my_decks`** fora
  do corte.

**AS REGRAS DE MATERIAL DOS TRÊS GRUPOS, E AS DUAS EXCEPÇÕES DAS BÁSICAS
(André, 2026-10-02, à letra).** *"Duel Commander, so ingles, e so Foil (se nao
houver, pode ser non-foil)"*; *"pauper so ingles tambem Foil (se nao houver,
pode ser non-foil)"*; *"o premodern e apenas portugues, non-foil, nas edicoes
indicadas"*; *"para as basicas, nos decks, tens que permitir tirar foto com mais
cartas e nao apenas 4"*; *"depois indico quantas basicas tenho de cada"*; *"em
todos os decks, as basicas sao todas de Unhinged"*. Recorta as regras de
2026-09-07 em três grupos; o cEDH e o SPML ficam como estavam. Config em
`regras_por_formato` + `basicas.declaradas`/`declaradas_em`, motor em
`loadout.requisito_basicas`/`basicas_declaradas`, `confirmado.metades`,
`fotos.so_basicas`/`valida`/`agrupar`, `revalidacao.declarar_lote`,
`collection._isentas_do_tecto` e `estado.e_basica`; textos em
`colecao_config.json → _regras_2026_10_02` e `_basicas`. Testes em
`tests/test_regras_material_1002.py` (10 casos) e a prova de que chumbam em
`tests/_chumba_regras_1002.py` (9 alvos / 10 pares, **10 de 10 chumbam**).

- **O SENTIDO NÃO É O MESMO NOS TRÊS, e é a armadilha desta ordem.** O **Duel
  Commander** APERTA a língua (ganhou `lingua: "en"`, que não tinha) e **AFROUXA
  o acabamento** (`foil` obrigatório → `prefere_foil`); o **Pauper** só aperta a
  língua (o `prefere_foil` já lá estava); o **Premodern** APERTA o acabamento,
  que **nunca tinha tido chave nenhuma** — o foil nunca estava proibido e agora
  está (`acabamento: "nonfoil"`). Quem lesse «três regras novas, todas mais
  apertadas» punha o Duel Commander em `foil` + `en` e tirava-lhe três cartas.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados** (worktree em
  `_revisao/regras-material`, cópia da base pela API de backup do sqlite3;
  `_revisao/medir_regras.py` + `comparar.py`). Preço de referência: modo
  `market`, cadeia `cardtrader → cardmarket`.

  | | antes | depois |
  |---|---|---|
  | fechar tudo | 15 391,58 € | **14 695,25 €** |
  | a comprar | 414 | **412** |
  | premodern (6 caixas) | 219 c · 118 · 2 097,00 € | **218 c** · 119 · 2 097,12 € |
  | duel-commander (1) | 78 c · 21 · 792,52 € | **81 c · 18 · 96,07 €** |
  | pauper (1) | 72 c · 0 · 0,00 € | **igual** |
  | cedh (2) | 161 c · 32 · 5 966,27 € | **igual** |
  | spml (7) | 193 c · 243 · 6 535,79 € | **igual** |

  **As 13 caixas que ele não mandou tocar ficam IGUAIS ao cêntimo**, e o delta do
  *fechar tudo* explica-se à vírgula: **−696,45 €** no Cloud **+0,12 €** no Elves.
- **UMA SÓ CÓPIA É DESALOJADA em todo o vault, e tem nome: a Nantuko Vigilante
  (LGN) PT FOIL, cópia #578**, que a alocação dava ao **Elves** e que o
  acabamento novo recusa. A premissa da ordem precisa de uma correcção de
  vocabulário, e é a favor dela: *"nenhuma está alocada"* é verdade no sentido
  FÍSICO (a `copy_allocation` não tem uma única linha de PT foil) e falso no
  sentido da ALOCAÇÃO, que é a que as páginas mostram — é a distinção de
  2026-09-08 («onde a carta ESTÁ ≠ a quem está destinada»). A conclusão dela
  estava certa: é a única carta que esta regra tira. A outra PT foil da colecção
  — **Phyrexian Arena (CN2)** — já estava fora pela regra das edições. Medido: só
  existem **2 cópias PT foil** em 1 678 (824 EN foil, 515 PT nonfoil, 334 EN
  nonfoil, 3 EN etched — os números dele batem todos).
- **E TRÊS CÓPIAS PASSAM A SERVIR, que é o outro lado do `prefere_foil`:**
  **Parallax Wave (NEM)**, **Reverent Mantra (MMQ)** e **Talon Gates of Madara
  (M3C)**, todas EN non-foil, que ele já tem. O Cloud deixa de comprar três
  cartas: **21 → 18** a comprar e **792,52 € → 96,07 €** (a Parallax Wave foil
  sozinha valia 388,96 € na medição de 20/09). A Parallax Wave sai de `guardar`
  — já não é um substituto a proteger, é uma carta alocada.
- **A LÍNGUA NÃO DESALOJA NADA, e isso é a medição e não um palpite:** as 78
  cópias do Duel Commander e as 72 do Pauper **já eram todas inglesas**. A conta
  dele para o Pauper era «59 EN foil e 15 EN nonfoil»; na base são **59 foil +
  13 nonfoil = 72** — 13 e não 15.
- **A `estrita` FICOU A `false` nos dois grupos, e é uma decisão por ele.** Com
  ela a `true` — como no Premodern — uma cópia na língua errada fica **fora de
  vista**: aparece como falta a comprar em vez de *"tenho mas não serve"*. **Hoje
  não mudava um único número**, porque não há uma única cópia não-inglesa
  alocável a estes dois grupos; o que muda é o dia em que houver. Fica para ele.
- **AS NOVE SAÍDAS DA VENDA quase não mexem:** `guardar` 10 c/1 432,95 € →
  **9 c/1 390,53 €** (a Parallax Wave, que passou a servir) e `sem_foto` 114
  c/1 820,85 € → **115 c/1 871,42 €** (a Nantuko Vigilante, que ficou livre).
  `venda` e `venda_rl` continuam a **zero**, `protegidas` 144 c/4 568,57 €,
  `rl_sem_historico` 100 c e `reservadas`/`retidos`/`rl_segurar` a zero —
  **iguais**. A cópia desalojada **não vai à venda**: cai em `sem_foto`, e a
  venda está fora de vista (`venda.mostrar: false`) e congelada (trava manual).
- **A ISENÇÃO DAS BÁSICAS TINHA DUAS PERNAS E PRECISAVA DE TRÊS.** O texto da
  isenção dizia *"escapam às regras de língua e edição"* e **não falava de
  acabamento** — e o `_serve_basica` já era generoso (com a isenção ligada
  devolve sempre `True`), por isso o MOTOR estava certo. O que estava errado era
  o **`requisito_basicas`**, que devolvia `"non-foil"` e `"foil"` a seco: a
  partir do dia em que o Premodern ganhou `acabamento: "nonfoil"`, a linha de
  básicas dessas caixas passava a **exibir «non-foil» como requisito** enquanto a
  alocação aceitava a Unhinged foil — a página a pedir-lhe que fosse trocar 24
  terras que tem ali ao lado. Hoje diz *"non-foil se houver"* / *"foil se
  houver"* enquanto a isenção estiver ligada, e volta às palavras secas se
  alguém a desligar. Tem caso por grupo: uma Unhinged **EN foil** serve uma caixa
  de Premodern `nonfoil`, e uma Unhinged serve o Duel Commander e o Pauper.
- **ZERO BÁSICAS APARECEM COMO COMPRA**, antes e depois — e as alocadas são as
  mesmas, à cópia: 24 Snow-Covered Plains **MH1 EN foil** no Duel Commander
  (`prefere_foil`), 3 Plains ODY EN nonfoil no Cloud cEDH, e as 9 Plains ODY EN
  nonfoil espalhadas pelas quatro caixas de Premodern — as **5 do UW Replenish**
  que a ordem nomeou incluídas. Confirmado que continuam a servir.
- **UMA FOTO DE BÁSICAS NÃO TEM TECTO** (`fotos.so_basicas` + `valida(…,
  isenta=)`). A regra das quatro cartas de 01/10 existe para cada carta ficar **à
  vista e avaliável**, e numa pilha de 27 terras idênticas isso não quer dizer
  nada — por isso 27 Snow-Covered Plains são **1 foto** e não sete. A excepção é
  **só para fotos que sejam SÓ de básicas**: uma que misture básicas com outra
  carta volta a ter tecto, e uma carta normal de 29 cópias continua a partir-se
  em 8 fotos `partida`. A pergunta *"isto é só básicas?"* vive **num sítio só** e
  a lista de básicas é a do `loadout.BASICS` (já havia cinco cópias dela pelo
  repositório; não se fez a sexta). Morde nos **quatro** sítios que aplicavam o
  tecto — `fotos.agrupar`, a trava do `collection.import_csv`
  (`_isentas_do_tecto`), o `revalidacao.valida_esta_foto` (pelo lote declarado) e
  o `revalidacao.fotos_que_nao_validam` (que lê a base e passou a ler também os
  NOMES das cartas de cada foto). O `test_fotos_ate_4.caso_nenhuma_foto_passa_de_
  quatro_cartas` estava escrito com as Snow-Covered Plains e **foi reescrito com
  uma carta não-básica**: a regra geral continua trancada, com a razão no
  docstring.
- **AS BÁSICAS ENTRAM POR CONTAGEM DECLARADA, E ISSO NÃO É «CONFIRMADO POR
  FOTO».** `basicas.declaradas` = `{nome: {acabamento: quantas}}` (um número a
  seco vale `nonfoil`), com `declaradas_em` a datar a contagem. É a excepção
  EXPLÍCITA à regra da foto do mesmo dia — sem ela todos os decks apareciam
  incompletos por causa das terras — e já era o comportamento (as básicas contam
  como tidas desde 08/09). **O que mudou é o NÚMERO que ele vê:** até hoje as
  básicas somavam ao `usadas_conf` e o vault dizia **«95 cartas confirmadas por
  foto»** num dia em que não há **uma única** foto desta campanha. Era o padrão
  do `event_tier` outra vez: o número certo a responder à pergunta errada. Agora
  há uma **terceira parcela** (`loadout` → `tenho_decl`/`tenho_decl_total`,
  `confirmado.metades(…, declarado=)`) e as três somam o total por construção —
  o `MetadesQueNaoSomam` continua a levantar se não somarem. Medido na base:
  **0 de 784 cópias confirmadas por foto · 95 por contagem declarada (básicas)**,
  e 689 por confirmar; antes dizia 95 confirmadas. O `declarado` é **0 por
  omissão**, por isso nenhum dos outros chamadores do `metades` mudou.
- **A chave `declaradas` entra VAZIA, de propósito.** A pilha de Unhinged **nunca
  foi uma linha da `copies`** e ninguém a contou — preenchê-la de memória era
  inventar dados, que é a regra dele. Vazia, nada muda: as básicas continuam a
  contar como tidas, marcadas `contagem declarada`. **E a declaração NÃO é um
  tecto** (decisão minha, e é a que vale a pena rever): se ele declarar 29
  Snow-Covered Plains e os decks pedirem 31, as 31 continuam a contar e o vault
  não se queixa. Fazê-la morder era pôr decks incompletos por causa de terras,
  que é o contrário do que esta excepção existe para evitar; mas é uma linha no
  `_aloca_basica` no dia em que ele quiser o aviso.
- **UMA BÁSICA NÃO LEVA ESCALÃO DE ESTADO NEM VERSO** (`estado.e_basica` →
  `estado.registar` levanta `EstadoInvalido`). Entram por contagem e nunca por
  foto, logo não há foto de onde tirar um escalão; e recusar em **silêncio**
  parecia a regra da correcção dele (`aplicado = 0`), que é outra coisa. A
  `estado.lista_curta` já não as podia apanhar (uma básica nunca é Reserved List,
  dual, shockland nem fetchland) — foi **verificado e não assumido**.
- **O DIFF DO CONFIG SÃO 8 INSERÇÕES E 5 REMOÇÕES** (3 linhas de regras + 2
  chaves de básicas + 3 textos de ajuda), e o ficheiro está na forma canónica: um
  round-trip pelo **`configio.escrever`** devolve-o **igual byte a byte**
  (`_revisao/provar_configio.py`), o que é a prova de que uma escrita futura por
  código não o reformata — a lição do commit `ac1f776`.
- **POR DECIDIR POR ELE:** (a) a **`estrita`** dos dois grupos, que hoje não
  mudava um número; (b) a **`declaradas`** por preencher, e se quer que a
  contagem seja um tecto; (c) a declaração não cobre as básicas **registadas na
  `copies`** (as 24 Snow-Covered MH1 e as 12 Plains ODY) — essas continuam a
  contar pela base, como qualquer cópia, e a declaração é para a pilha a granel.

**OS 16 DECKS QUE FICAM, E AS REGRAS DAS CARTAS (André, 2026-10-02).** Ele
fechou a lista dos decks que ficam e reescreveu as regras que decidem o que vai
à venda. **Substitui, no que se cruza, a secção «A ARRUMAÇÃO POR FASES» de
2026-10-01** (que segue abaixo e fica como histórico): as quatro protecções
P1–P4 passaram a sete regras R1–R5b + RD, o campo `caixas[].decisao` foi
APAGADO e o limiar de 20 % da reserva foi APAGADO. Motor em
`mtgvault/fases.py` e `mtgvault/sources.py` (`ids_por_assinatura`); página
`arrumacao.py`; CLI `py -m mtgvault.cli fases [--curva] | fases terras | fases
duais | fases staples`; endpoint `/api/fase-reserva` (com a acção `devolver`
nova); config em `caixas[].assinatura`/`assinatura_todas`/`reserva_assinatura`/
`reserva_fora` e `reserva.janela_dias`/`staples_premodern_pct`. Testes em
`tests/test_decks_finais.py` (11 casos) e `tests/test_fases.py` (33, reescritos),
com a prova de que chumbam em `tests/_chumba_decks.py` (5 alvos) e
`tests/_chumba_fases.py` (13).

- **A REGRA DE OURO: a identidade de um deck é uma CARTA-ASSINATURA, nunca a
  etiqueta do clustering.** Palavras dele, e já se provou duas vezes nesta
  semana: as etiquetas chamam-se *"Rotlung Reanimator / Priest of Gix / Oath of
  Druids"* e há dezenas vazias com o mesmo nome (medido no `consenso.py`: 870
  etiquetas de `duel-commander`, 808 sem uma única lista). Quem escolhe as
  listas é **`sources.ids_por_assinatura`, num sítio só**, partilhado pela LISTA
  da caixa (`loadout._cards_from_consensus`) e pela RESERVA (`fases`) — dois
  selectores ao lado discordavam um dia qualquer, em silêncio.
  `assinatura_todas: true` pede a **conjunção** (o *Engineer Welder Cam* precisa
  de `Goblin Welder` **e** `Sewer-veillance Cam`); a omissão é *basta uma*, que é
  o que serve o *"Greasefang, as várias versões"*. Uma caixa cuja LISTA vem de
  outra fonte (a do Luffy, um link, uma lista padrão fixada) escreve a identidade
  em `reserva_assinatura`: **a assinatura é a identidade, não a lista.**
- **OS NÚMEROS DELE BATEM TODOS — e sobre TODAS as listas, não sobre as que
  contam.** Verificadas as 13 contagens uma a uma na base de 2026-10-02:
  Stiflenought 114, UW Replenish 186, Oath 51, Elves (Wirewood Symbiote) 28, IGG
  3, Pauper (Myr Enforcer) 23, Modern Affinity (Weapons Manufacturing) 88, Oswald
  13, Greasefang 37, Bant Airbend 9, Goblin Welder 50, Sewer-veillance Cam 54,
  Aluren 46. Com o `sources.counting_sql` do site davam 85/144/29/23/3/**0**/85/
  13/26/6/35/39/30 — e o Pauper dava **zero**, porque `metagame_fontes.pauper.
  tiers = []` (ele só segue o Luffy). **Welder E Cam em conjunção: 50 listas** —
  a Cam traz 4 que não jogam Welder, e é por isso que ele mandou usar as duas.
- **O UNIVERSO DE LISTAS DA R5 É TODAS AS LISTAS**, e é uma excepção deliberada
  ao filtro do site (`so_que_contam=False`). Sub-contar aqui é VENDER uma carta
  que ele precisa; e no Pauper e no cEDH o filtro dá zero de propósito, o que
  deixava dois dos 16 decks sem protecção nenhuma, em silêncio — o padrão do
  `event_tier`. É a mesma razão por que a VIGIA DE CARTAS de 2026-09-26 abriu o
  filtro de tier (*"a primeira aparição de um combo novo É um 5-0 de league"*).
  A LISTA da caixa continua com o `counting_sql` de sempre: são duas perguntas.
- **O CAMPO `decisao` FOI APAGADO, com tudo o que o lia.** Ordem dele: *"ontem
  acrescentei um segundo campo de estado ao lado do que as caixas já tinham. São
  duas verdades para a mesma pergunta e eu concordo em ficar com a antiga."*
  Saíram o `caixas[].decisao`, o `fases.decisao_de`/`decisoes`/`gravar_decisao`/
  `DECISOES`/`TEXTO_DECISAO`, o endpoint **`/api/fase-decisao`**, o `fases
  decisao` do CLI e os botões da Fase 1. Quem decide é o `estado` da v6:
  `montada`/`congelada`/`permanente` **protegem**, `candidata` não protege por
  si, e **a OMISSÃO (sem a chave) vale `permanente` e por isso PROTEGE** — o
  `caixas.estado_de` já o fazia desde 2026-09-08, e aqui vale o dobro: um deck
  sem estado escrito não manda uma única carta para a venda. Tem dois casos de
  teste e dois alvos no `_chumba_fases`. **O estado muda-se na Deckboxes**, que é
  onde esse gesto já vive («Tornar permanente», «Montar», «Desmontar») e onde ele
  tem a caixa na mão; a Fase 1 mostra-o e não o reescreve. Há um caso que tranca
  que o campo não volta: um `decisao: dissolvido` escrito à mão no config **não**
  liberta carta nenhuma.
- **R1 — AS DEZ DUAIS ORIGINAIS: quatro de cada FORA dos decks.** *"O que passar
  disso vende-se ou troca-se."* Derivadas do catálogo como as outras duas listas,
  e a regra custou uma passagem: *dois sub-tipos de terra básica* dá **69** nomes
  e *`oracle_text` vazio* dá **ZERO** — as originais trazem o lembrete
  `({T}: Add {U} or {B}.)`, entre parênteses, que é como a Scryfall escreve texto
  que não é regra nova. A regra que dá dez é **dois sub-tipos básicos E um
  `oracle_text` que é SÓ esse lembrete**. **A R1 MANDA SOBRE A R4**, e é o ponto
  da regra: uma dual é Reserved List, e se a R4 a salvasse a R1 nunca mordia —
  *"para elas manda a R1, que é mais específica"*. Logo, numa dual só a RD (está
  num deck) e a R1 (está dentro das quatro de fora) protegem.
  **AS CONTAS DELE BATEM AO EXEMPLAR**: 45 cópias, 6 em decks (as seis do Blue
  Farm), 39 fora → **vender 6** (Taiga 2, Bayou 1, Scrubland 1, Tropical Island
  1, Tundra 1 — 3 001,26 €) e **faltam 7** (Savannah 3, Badlands 2, Plateau 1,
  Underground Sea 1 — 822,62 € ao preço mínimo). **Ficam as QUATRO DE MAIOR
  VALOR** e vende-se o resto (edição e `copy_id` a desempatar): ele quer ter
  quatro de cada, e ficar com as melhores é o que um colecionador faz — e a ordem
  tem de ser determinista, senão a lista de venda troca de cópia de um dia para o
  outro.
- **A R1 OBRIGA A PARTIR UMA LINHA, e isso é desenho e não detalhe.** Um lote de
  cinco duais fora dos decks tem **quatro** protegidas e **uma** candidata, e dar
  o lote inteiro a um dos lados era mentir por quatro ou por uma. Por isso o
  `quem_protege` devolve uma QUANTIDADE (não um sim/não) e os dois consumidores
  — a Fase 3 e o `loadout.sell_list` — partem a linha com o mesmo `_partir`. E o
  que se gasta é um **orçamento de cópias LIVRES por sub-lote**, fresco a cada
  chamada: o motor da venda recebe uma linha que é um PEDAÇO do sub-lote (o
  excedente que o playset já cortou), e dizer-lhe *"deste sub-lote há quatro
  protegidas"* protegia exactamente a cópia que ele estava a oferecer.
- **R5 — A RESERVA É O QUE FOI JOGADO NOS ÚLTIMOS 30 DIAS, e o limiar de 20 %
  foi APAGADO.** *"Protege-se toda a carta que tenha sido jogada no último mês
  nos decks acima, mesmo que esteja hoje fora da lista — main ou side."* O travão
  passou a ser a JANELA, e é um travão a sério porque a base só guarda 30 dias de
  listas (`daily.prune_decklists`): o que lá está é, por construção, o mês que
  passou. Não se deixou uma chave morta no config a dizer que existe um limiar
  que não existe. **Abaixo de oito listas não se chama consenso a nada**
  (`MIN_LISTAS_RESERVA`, o mesmo do `consenso.MIN_LISTAS`): é a ordem dele sobre
  o *Ill-Gotten Gains* — *"só 3 listas, abaixo do mínimo de 8; marca-o como SEM
  CONSENSO SUFICIENTE e não inventes consenso com 3 listas"*.
- **R5b — AS STAPLES DE SIDEBOARD DO PREMODERN, e a curva é que decide o corte.**
  Pela presença em sideboards de TODAS as listas de Premodern da janela, com o
  denominador a ser as listas que TÊM sideboard (hoje são as 987, mas a conta tem
  de estar certa no dia em que não forem). O corte está em
  `reserva.staples_premodern_pct` = **10 %, PROVISÓRIO** — a ordem é explícita
  (*"não fixes o corte sem lhe mostrar a curva"*), por isso o valor é o que
  protege MAIS e a página e o CLI dizem que é provisório. A curva, medida:

  | corte | cartas staple | a mais (cóp./€) | sozinha (cóp./€) | só PT da era |
  |---|---|---|---|---|
  | 10 % | 25 | 4 / 6,60 € | 41 / 458,35 € | 37 cóp. |
  | 20 % | 7 | 1 / 3,96 € | 11 / 61,75 € | 8 cóp. |
  | 30 % | 1 | 0 / 0,00 € | 3 / 5,40 € | 0 |
  | 40 % | 1 | 0 / 0,00 € | 3 / 5,40 € | 0 |
  | 50 % | 0 | 0 / 0,00 € | 0 / 0,00 € | 0 |

  **A CURVA DÁ DOIS NÚMEROS, e sem o segundo era ilegível.** «A mais» é o efeito
  real de mexer no corte hoje — e é quase zero, porque a **R5 já apanha
  praticamente todas as staples**: uma staple de sideboard é, por definição, uma
  carta que apareceu numa lista do mês. «Sozinha» é o que o corte protegeria se a
  R5 não existisse, e é isso que diz quanto a regra VALE. Com uma coluna só, uma
  curva plana lia-se como *"as staples não importam"*, quando o que se passa é
  que outra regra chegou lá primeiro. As 25 cartas a 10 %: Tormod's Crypt 46,2 %,
  Hydroblast 27,4 %, Naturalize 25,1 %, Annul 23,9 %, Red Elemental Blast 22,3 %,
  Aura of Silence 22,0 %, Pyroblast 21,2 %, Blue Elemental Blast, Tsabo's Web,
  Engineered Plague, Tranquil Domain, Gaea's Blessing, Xantid Swarm, Warmth,
  Pyroclasm, Ray of Revelation, Overload, Brain Freeze, Meddling Mage, Seal of
  Cleansing, Sacred Ground, Cursed Totem, Essence Flare, Exalted Angel, Circle of
  Protection: Red.
- **A R4 DEIXOU DE PROTEGER O QUE NÃO É DECK DELE, e era um defeito a sério.**
  O caminho (c) varria a tabela `decks` INTEIRA e filtrava pelo FORMATO: na base
  de 2026-10-02 isso protegia Reserved List por aparecer no *Jeskai Lessons*, no
  *4c Control*, no *Cori-Steel Cutter*, no *Legacy (Harry1232)*, no *Stiflenought
  (Spock)* ou no *Enchantress (consenso)* — listas de metagame e de jogadores
  vigiados que **não são decks dele**. A pergunta é *"o RL que ELE joga"*, e quem
  responde é a lista de caixas (`caixas[].ref`): um deck que saiu do config deixa
  de proteger no mesmo dia, sem ninguém ter de limpar uma linha da base. Medido:
  a R4 passou de **89 cópias / 17 cartas** para **85 / 17**, 47 933,60 € →
  45 039,07 €.
- **O BOTÃO «NÃO É NECESSÁRIA»**, em cada carta da reserva: tira-a da reserva
  daquele deck e passa-a a candidata a venda. **PERSISTENTE** —
  `caixas[].reserva_fora`, no config, que o `daily` não reescreve —, **com a
  DATA e o deck** (`{nm, em}`; a forma antiga, a lista de nomes de 2026-10-01,
  continua a valer sem data) e **REVERSÍVEL** no *«voltar a pôr»*. O inverso é a
  acção **`devolver`** do `/api/fase-reserva` e **não um `add` disfarçado**: um
  `add` punha a carta na lista MANUAL, que fica lá mesmo que ninguém a jogue.
  Guarda-se o que ele TIROU e não a lista final, para a reserva continuar a
  crescer com as listas novas sem lhe devolver o que ele já recusou — tem caso
  que corre uma «corrida do daily» por cima. Escreve-se com o
  `configio.escrever`, e o teste mede que o ficheiro **não cresce** (a lição do
  commit `ac1f776`, 861 inserções por um `indent=2`).
- **AS 16 CAIXAS, e o que mudou em cada uma.** Dissolvidas: **Enchantress**
  (`premodern-enchantress`) e **Jeskai Control** (`pioneer-jeskai`) — as duas
  estavam VAZIAS (0 cópias alocadas), por isso não libertaram carta nenhuma. A
  lista padrão da Jeskai **não se apagou** (`listas_escolhidas`): é o registo de
  uma decisão dele, com data e origem, e nada a lê sem a caixa. O
  `premodern_arquetipos_alvo` perdeu a Enchantress. Caixas NOVAS: **Modern —
  Affinity** (`Weapons Manufacturing`), **Engineer Welder Cam** (`Goblin Welder`
  **e** `Sewer-veillance Cam`, no slot `legacy` que estava vazio e sem nome, hoje
  `legacy-welder`), **Aluren** e **Artifacts Blue**. O `standard` passou a
  chamar-se **Bant Airbend**.
- **TRÊS DECISÕES QUE SÃO MINHAS E SE DESFAZEM NUMA LINHA**, e é melhor estarem
  escritas do que descobertas daqui a um mês:
  1. **as caixas novas e as duas promovidas (`standard`, `legacy-welder`) ficaram
     `permanente` e não `candidata`.** São decks que ele disse que ficam, e um
     `candidata` não protege as cópias que receba — deixá-las candidatas era
     contradizer a regra da omissão. O custo é a alocação: quatro caixas
     permanentes novas competem por cartas;
  2. **a LISTA de três caixas NÃO se trocou pelo consenso da assinatura, só a
     identidade.** O `modern` (UW Oswald) tem hoje *"maindeck dele por foto +
     sideboard das 28 listas de MTGO"* e é **o deck do RC Ghent de 9-11/10**;
     trocá-lo por um consenso de 13 listas na véspera do torneio era estragar
     trabalho dele por uma regra que serve outra pergunta. O mesmo no
     `premodern-stiflenought` (a lista do Luffy, que ele mandou manter), no
     `premodern-replenish` e no `pioneer`. Para passar qualquer uma a consenso
     basta trocar `reserva_assinatura` por `assinatura` e `fonte` por
     `"consenso"`;
  3. **a R5b protege TODAS as cópias de uma staple, não só as PT da era.** A
     ordem não qualifica, e sobre-proteger só adia uma venda enquanto
     sub-proteger perde uma carta. A curva dá a coluna «só PT da era» ao lado
     para ele ver a diferença (37 das 41 cópias, a 10 %).
- **MEDIDO na base de 2026-10-02** (`py -m mtgvault.cli fases --curva`; o mesmo
  `vault.db` dos dois lados, backup em
  `data/backups/vault-2026-10-02-decks-finais.db`). Preço de referência: modo
  `market`, cadeia `cardtrader → cardmarket`.

  | regra | cópias | cartas | valor |
  |---|---|---|---|
  | R1 duais (4 fora dos decks) | 33 | 10 | 21 913,64 € |
  | R2 shocklands | 40 | 10 | 2 726,00 € |
  | R3 fetchlands | 66 | 10 | 11 235,15 € |
  | R4 RL que ele joga | 85 | 17 | 45 039,07 € |
  | RD está num deck que fica | 367 | 195 | 20 287,44 € |
  | R5 jogada nos últimos 30 dias | 402 | 154 | 13 835,42 € |
  | R5b staple de sideboard de Premodern | 4 | 2 | 6,60 € |
  | **protegidas (sem sobreposição)** | **997** | | **115 043,32 €** |
  | **VENDER** | **681** | **257** | **21 126,51 €** |

  Comparado com 2026-10-01 (quando eram quatro protecções e um limiar de 20 %):
  protegidas 649 → **997**, candidatos 1 029 c/31 150,15 € → **681 c/
  21 126,51 €**. A diferença é a R5 sem limiar (402 cópias, contra as 54 da
  reserva de ontem) e a R1 a proteger 33 duais que antes caíam na RL.
  Filas: Fase 2 **124 fotos / 411 cartas** em 6 decks (iguais), Fase 4 **207
  fotos / 681 cartas**, inventário 93 fotos / 305 cópias / 96 914,19 €, fotos
  perdidas 33 / 165 cópias / 12 637,94 €.
- **A ALOCAÇÃO MEXEU, e era inevitável:** ele acrescentou quatro decks e
  dissolveu dois. Medido lado a lado (um worktree em `_revisao/main-1002`, o
  MESMO `vault.db` dos dois lados, `_scratch/comparar.py`):

  | | main (15 caixas) | ramo (16 caixas) |
  |---|---|---|
  | `loadout.report` | 2,32 s | **1,96 s** |
  | fechar tudo | 8 944,98 € | **14 812,56 €** |
  | a comprar | 246 | **348** |
  | venda (motor) | 249 c / 4 525,62 € | 115 c / 1 824,28 € |
  | protegidas (motor) | 23 c / 2 921,62 € | 157 c / 4 989,13 € |
  | rl_sem_historico | 101 c / 23 590,82 € | 104 c / 25 332,29 € |
  | guardar | 2 c / 47,01 € | 11 c / 1 475,37 € |

  **O DELTA DO «FECHAR TUDO» EXPLICA-SE AO CÊNTIMO**, e isso é o que faz dele uma
  consequência e não um acidente: +5 867,58 € = as quatro caixas novas (Aluren
  1 819,13 € · Engineer Welder Cam 2 599,71 € · Modern — Affinity 1 577,53 € ·
  Bant Airbend 166,78 €) **menos** as duas dissolvidas (Jeskai 113,14 € ·
  Enchantress 212,27 €) **mais** 29,84 € que o Pioneer passou a precisar. **As
  dez caixas que ele não mandou tocar ficam IGUAIS ao cêntimo e à percentagem.**
- **E UMA CONSEQUÊNCIA A SABER: o Pioneer — Greasefang piorou, de 17 % para
  12 %** (62 → 66 a comprar). Não é a Jeskai a sair: é o **Bant Airbend**, que
  tem `prioridade` 11 e por isso aloca **antes** do Greasefang (13) dentro do
  mesmo grupo SPML, e leva foil EN que antes sobrava para ele. É o custo de ter
  quatro decks novos no mesmo grupo; desfaz-se trocando as `prioridade`, que é
  uma linha no config e uma decisão dele.
- **POR FAZER, e é uma linha cada:** o **Artifacts Blue** espera a
  carta-assinatura dele (escreve-se em `caixas[].assinatura` + `fonte:
  "consenso"`); o **corte das staples** espera a escolha dele na curva; o
  **Ill-Gotten Gains** e os dois de **cEDH** ficam com a reserva só manual (o
  primeiro por ter 3 listas, os dois últimos porque o cEDH não tem metagame no
  vault, por decisão dele de 2026-09-07).

**A ARRUMAÇÃO POR FASES, E AS QUATRO PROTECÇÕES DA VENDA (André, 2026-10-01).**
**[Os ESTADOS e o LIMIAR desta secção foram SUPERSEDED a 2026-10-02 — ver a
secção de cima. O que fica inteiro é a estrutura das quatro fases, as filas de
fotos, a trava do RC Ghent e a derivação das shock/fetchlands.]**
Ele vai arrumar a colecção por FASES e ditou as regras neste dia. Motor em
`mtgvault/fases.py`, página `arrumacao.py` → `arrumacao.html`, passo `arrumacao`
do `daily`, CLI `py -m mtgvault.cli fases [--curva] | fases terras`, endpoint
`/api/fase-reserva`; config em `venda.congelada` (era `congelado_ate`), `reserva`
e `caixas[].reserva`/`reserva_fora`/`comandante`/`reserva_assinatura`.
Testes em `tests/test_fases.py` (24 casos) e a prova de que chumbam sem a
funcionalidade em `tests/_provar_chumba.py` (+ `tests/_chumba_fases.py`, 10
alvos / 16 casos). As palavras dele:

- **P1 shocklands e fetchlands:** *"**Todas as cópias** ficam protegidas — todos
  os acabamentos, todas as línguas, todas as repetidas, estejam ou não num deck.
  Sem excepções."*
- **P2 Reserved List:** protege-se *"o RL que ele joga"*, e **joga** é alocado a
  um deck montado OU presente no consenso de um formato que ele joga. O resto da
  RL **não** é protegido por aqui: segue a regra dos 5 % de 2026-09-08, com o
  carimbo da régua de preço.
- **P3 decks:** *"nenhuma cópia alocada a um deck no estado «montado» ou
  «guardado» vai à venda."*
- **P4 reserva:** *"pede também, para cada deck, os maybe porque é preciso ter
  reserva dessas cartas para não estar a vender agora e ter que comprar mais
  tarde."*

- **AS LISTAS DE TERRAS DERIVAM-SE DO CATÁLOGO, e para isso o catálogo mudou.**
  Ordem dele: *"as listas de shocklands e fetchlands NÃO podem ser escritas à
  mão a partir da tua memória: deriva-as do catálogo (tipos, oracle text,
  edições) e grava a regra usada. Se não der exactamente 10 e 10, PARA e diz
  quais achaste — não arredondes a conta."* O `catalog.db` **não tinha oracle
  text** (o inventário de 01/10 de manhã deu por isso e teve de se ficar por uma
  lista nomeada): a coluna `oracle_text` entrou nos **três sítios**
  (`catalog_schema.sql`, `db._migrate()` e `scryfall._row`/`INSERT`) e o
  catálogo foi sincronizado — 112 754 impressões, **111 390 com texto**, 13 s. O
  **`scryfall.has_card_meta` passou a perguntar pela coluna**, senão o
  `daily._catalog` — que salta o `sync` quando o catálogo tem linhas — deixava-a
  a NULL para sempre, que é o padrão do `event_tier`.
  - **shocklands → 10**: dois sub-tipos de terra básica no `type_line` **e** o
    texto a dizer que se pode pagar 2 de vida para não entrar virada. A primeira
    metade sozinha dá **66** nomes (as duais originais, as de BFZ, as surveil de
    MKM, as de cycling de AKH, as «Turbulent» de SOC); é a segunda que corta.
  - **fetchlands → 10**: pagar 1 de vida, sacrificar-se e procurar na biblioteca
    uma carta que põe em jogo, nomeando **exactamente dois** tipos básicos. O
    «exactamente dois» exclui a Prismatic Vista e a Elven Passage, que procuram
    uma básica qualquer. **A armadilha que custou uma passagem:** o texto da
    Polluted Delta e da Scalding Tarn diz *"for **an** Island"* — um padrão com
    `for a ` dava **oito** das dez, sem um único erro.
  - As duas regras **não usam a edição**, e isso é melhor do que parecia: uma
    reimpressão futura entra sozinha e um ciclo novo com o mesmo `type_line`
    fica fora sem ninguém mexer na lista. O filtro que as outras colunas
    permitiam (`type_line = 'Land'`, 1.ª impressão em ONS/ZEN, rare) dava **19**.
  - **A CONTA TEM DE DAR DEZ *NUM CATÁLOGO COMPLETO*, e esta distinção é
    precisa.** Há dois motivos para não dar dez: o catálogo a sério sem
    `oracle_text` (por sincronizar — aí a protecção ficava vazia e mandava
    shocklands para a venda sem um passo a falhar, e é aqui que se PARA, alto) e
    um catálogo PEQUENO que simplesmente não contém aquelas cartas (as bases dos
    testes têm trinta cartas; aí «zero» é a resposta certa, o mesmo princípio do
    `foil_info`). Separa-os o TAMANHO (`fases.CATALOGO_COMPLETO = 1000`, o mesmo
    limiar do `daily._catalog`). Sem esta distinção, acrescentar a P1 ao
    `sell_list` rebentava o `report` em **vinte ficheiros de teste** e em
    qualquer base nova. O `fases.verificar` (e o `cli fases terras`) exige
    sempre, e é por aí que a conta curta é um erro à vista.
- **OS TRÊS ESTADOS VIVEM EM `caixas[].decisao` E NUNCA NO `estado`.** O
  `estado` (`candidata`/`permanente`/`montada`, v6 de 2026-09-08) é a escala da
  ALOCAÇÃO — diz quem escolhe cartas primeiro e o que está sleevado. A decisão
  desta arrumação é outro eixo (*"o que faço com este deck"*), e escrevê-la na
  mesma chave era mudar a alocação com um botão que ele carrega para arrumar.
  `montado` fica montado e as cartas ficam protegidas; `guardado` desmonta-se e
  as cartas continuam protegidas; `dissolvido` desmonta-se e as cartas passam a
  candidatas, menos as que P1, P2 ou P4 apanhem.
  **A OMISSÃO É `montado`, nunca o contrário**: um deck sem decisão não manda uma
  única carta para a venda. Um default a `dissolvido` punha o conteúdo de uma
  caixa à venda no dia em que alguém a acrescentasse ao config. Tem dois casos de
  teste e dois alvos no `_chumba_fases`.
- **A RESERVA ENCHE-SE SOZINHA, E O LIMIAR É QUE A TORNA UTILIZÁVEL.** Sai do
  consenso do arquétipo — a banda flex e o resto do sideboard que não estão nas
  75 de hoje — mais o que ele acrescentar à mão (`caixas[].reserva`, a chave de
  2026-09-20, que já queria dizer isto). Para o Duel Commander é o **consenso
  por comandante** de 2026-10-01, como a ordem manda. O que ele TIRA guarda-se em
  `caixas[].reserva_fora` — guarda-se o que ele tirou e não a lista final, para a
  reserva continuar a crescer com o consenso sem lhe devolver o que ele já
  recusou. A reserva **protege só o que ele TEM**; o que não tem alimenta a lista
  de compras que o loadout já faz.
  - **O EFEITO PERVERSO é real e mede-se**: a 10 % a reserva segura **217
    cópias / 12 679,10 €**, a 20 % **77 / 4 095,87 €**, a 30 % **47 / 829,98 €**,
    a 40 % **25 / 595,98 €**, a 50 % **21 / 544,98 €**. Ficou em **20 %**
    (`reserva.limiar_pct`) e a curva mede-se com `cli fases --curva`.
  - **ABAIXO DE OITO LISTAS NÃO HÁ RESERVA AUTOMÁTICA** (`MIN_LISTAS_RESERVA`,
    o mesmo mínimo do `consenso.MIN_LISTAS`), e não é um requinte: a caixa
    *Ill-Gotten Gains* (que nem tem lista — 0/0) casava **3** listas pela
    assinatura, uma carta que aparece numa só valia 33 %, passava folgadamente o
    limiar de 20 %, e a reserva dela sozinha segurava **52 cópias / 6 879 €** —
    96 % de tudo o que a P4 protegia. Não era o limiar que estava mal: era a
    amostra. O que ele escreveu à mão **fica**, haja ou não amostra: isso é uma
    decisão, não uma inferência.
  - **A ASSINATURA DERIVA-SE quando não está escrita** (`assinatura_derivada`):
    as cartas da própria lista da caixa que são mais RARAS no formato. Muitas
    caixas não têm `assinatura` — a do Modern e a do Pioneer vêm de uma lista
    seguida, não de um arquétipo —, e pedir-lhe uma lista à mão era escrevê-la de
    memória, que é o que a ordem proíbe. Resultado medido: Modern 18 listas,
    Jeskai 21, Greasefang 18, Enchantress 111, UW Replenish 39, Stiflenought 99.
    O cEDH, o Pauper, o Legacy e o Standard ficam sem consenso e **dizem-no** (o
    cEDH não tem metagame no vault, o Pauper só guarda as listas do Luffy, e os
    outros dois não têm lista).
  - **O COMANDANTE DA CAIXA SAI DO CONFIG ANTES DE SE ADIVINHAR, e é um defeito
    que foi apanhado a medir.** A caixa *Cloud (Duel Commander)* resolvia para
    **Phelia, Exuberant Shepherd**: a lista padrão dela (fixada a 2026-09-20)
    **não inclui o próprio comandante** — a Cloud aparece como carta de reserva,
    a 89 % — e a Phelia está na lista e é ela própria um comandante com 37
    listas; o desempate por «mais listas» escolhia-a, e a reserva do deck de
    Duel Commander dele saía do consenso de outro deck, sem um único erro.
    Agora a ordem é `caixas[].comandante` → `consenso_comandante.comandante` (a
    escolha dele, que já estava escrita) → intersecção com os comandantes que a
    base conhece, desempatada primeiro pelo NOME da caixa. Hoje dá **Cloud,
    Midgar Mercenary, 41 listas, 180 cartas de consenso, 22 na reserva**.
- **AS PROTECÇÕES MORDEM EM DOIS SÍTIOS, com a mesma resposta.** `candidatos()`
  é a Fase 3 (varre a colecção inteira, só leitura) e `filtrar_venda()` entra no
  **`loadout.sell_list`**, no fim, como o filtro da reserva das caixas de
  2026-09-20 já entrava — uma cópia protegida sai de `venda`/`venda_rl` para a
  saída nova **`protegidas`**. Uma protecção que valesse só na página das Fases
  deixava a aba Vender e a exportação a oferecer a mesma carta, que é o padrão do
  `event_tier` aplicado à decisão que vale mais dinheiro. **Cada cópia excluída
  guarda o MOTIVO em português e QUAL das quatro a apanhou** — sem motivo não há
  exclusão silenciosa —, e a saída entra à cabeça do «fica de fora» da
  exportação (`venda.FORA`).
  - **A P3 lê a caixa do SUB-LOTE e nunca do `copy_id`**, e isto custou uma
    correcção: um lote de 4 com 3 na caixa e 1 na gaveta são dois sub-lotes com o
    mesmo `copies.id`, e perguntar pelo id protegia a parte que está na gaveta —
    uma cópia a desaparecer da venda sem motivo. O `linha_de` carimba a caixa na
    linha. Apanhado pelo `test_paginas_loadout`.
- **A TRAVA: `venda.congelado_ate` = 2026-10-12.**
  **[SUPERSEDED a 2026-10-04 ao fim do dia: a trava passou a MANUAL
  (`venda.congelada`) e já NÃO tem data — ver «A TRAVA DA VENDA DEIXA DE TER
  DATA». O que segue fica como histórico; o mecanismo é o mesmo, muda a
  condição.]** Ele joga o RC Ghent de Modern
  a 9-11/10. Qualquer geração de saída de venda ou exportação **recusa-se** antes
  dessa data (`fases.VendaCongelada`, subclasse de `ValueError` como a
  `webapp.VendaDesligada`, por isso o `do_POST` traduz num 409 com a frase em
  português). A pergunta vive no `_exige_venda()` — um sítio só, as duas portas
  de escrita (o `/api/vender`, que **apaga cópias da base**, e o
  `/api/venda-export`) — e corre **antes** do `migracao.backup`: um pedido
  recusado não deixa ficheiro atrás dele. O `daily` **salta o passo e DIZ
  porquê** (deixar a excepção subir punha o passo a vermelho todos os dias por
  uma decisão que foi tomada, e um vermelho que é normal deixa de se ler). Não é
  o mesmo que o `venda.mostrar`: aquele tira a venda da VISTA, este impede a
  SAÍDA — e o `mostrar` fica como estava (`false`).
- **A FILA DE FOTOS MEDE FOTOS DE ATÉ 4 CARTAS.**
  **[CORRIGIDO A 2026-10-01, no mesmo dia]** esta linha dizia *"a fila conta
  CÓPIAS FÍSICAS, não nomes: um lote de 4 dá quatro linhas na fila"* (o
  `_explode`), e dava **quatro fotos a um playset** — quatro vezes o trabalho
  dele. A regra verdadeira é *"até 4 cartas por foto"*: ver «UMA FOTO LEVA NO
  MÁXIMO QUATRO CARTAS», abaixo. A Fase 4 é **por carta, da mais cara para a
  mais barata** (escolha dele, não por caixa), em lotes de 50 FOTOS; a Fase 2 é
  por deck e **por TIPO de carta** (era por COR — a ordem do painel Montar; ali
  ele procura num binder arrumado por cor, aqui dispõe na mesa o que já tem na
  mão). O **inventário** (RL + shock/fetchlands) é a via paralela: *"nunca
  bloqueia nada e aparece como tal na página"*. Reaproveita o fluxo de fotos que
  já existe (`pendentes/`, a conciliação do `import_csv`): esta página **só
  ordena a fila e mostra o progresso**.
- **A PÁGINA NÃO MEXE EM ALOCAÇÕES NEM NA BASE** (ordem dele, à letra): lê a
  colecção e escreve o estado do deck e a reserva no `colecao_config.json`, com o
  `configio.escrever`. Tem teste que mede que o ficheiro **não cresce** (a lição
  do commit `ac1f776`, 861 inserções por um `indent=2`), e que mudar de estado é
  **reversível** e não apaga a lista nem a reserva. A página vai no `git add` do
  `daily.yml` e no `HTML` da tarefa `mtgvault-daily`.
- **MEDIDO na base de 2026-10-01** (`py -m mtgvault.cli fases --curva`; o
  inventário de leitura da manhã está em
  `ai-pc/work/saidas/venda-inventario-2026-10-01.txt`). Preço de referência:
  modo `market`, cadeia `cardtrader → cardmarket`.

  | protecção | cópias | cartas | valor |
  |---|---|---|---|
  | P1 shock/fetchlands | 106 | 20 | 13 969,42 € |
  | P2 RL que ele joga | 128 | 26 | 74 861,33 € |
  | P3 deck montado/guardado | 361 | 189 | 15 826,36 € |
  | P4 reserva («maybe») | 54 | 27 | 729,58 € |
  | **protegidas (sem sobreposição)** | **649** | | **105 386,69 €** |
  | **candidato a venda** | **1 029** | **382** | **31 150,15 €** |

  Os **15 decks**, todos sem decisão escrita (logo `montado`): Blue Farm
  10 272,95 € · Modern — UW Oswald 9 079,59 € · UW Replenish 4 369,31 € · Cloud
  cEDH 4 210,84 € · Stiflenought 1 952,80 € · Pauper (Luffy) 918,03 €; os outros
  nove ainda não têm nada na caixa. Filas: **Fase 2 = 411 cópias** em 6 decks,
  **Fase 4 = 1 029 cópias** em 21 lotes de 50, inventário 305 cópias /
  97 249,84 €. No MOTOR, com as protecções ligadas: `venda` **271c/7 488,78 € →
  217c/3 647,73 €** e `protegidas` **54c/3 841,05 €**; a alocação **não mexe**
  (fechar tudo 8 928,35 €, 240 a comprar, 225 a arrumar, `rl_sem_historico`
  102c/24 393,12 €, `guardar` 2c/46,76 €, `reservadas` 1c/496,52 €).
  A diferença para o inventário da manhã (1 022 cópias / 30 282,24 €) é
  esperada e é uma melhoria: a protecção dele levava a cópia INTEIRA de um lote
  partido, e a P3 leva só a parte que está dentro da caixa.
- **POR FAZER, e é uma linha cada:** os **quatro decks sem consenso** (cEDH,
  Pauper, Legacy, Standard) ficam com a reserva só manual — basta escrever-lhes
  `reserva_assinatura` no config; e o `fases.formatos_que_joga` sai das caixas
  por omissão, o que é o que ele quer hoje, mas aceita `fases.formatos_jogados`
  no config se um dia quiser recortá-lo.

**A FILA DA FASE 2 E O BOTÃO DO ALVO NO MESMO SÍTIO (André, 2026-10-01, no mesmo
dia).** Ele perguntou **onde é que punha as fotos** — e a pergunta é a avaria. A
fila das fotos dos decks montados estava na página das Fases e o botão que diz
*"é esta caixa que estou a fotografar"* só na Deckboxes: o caminho existia desde
2026-09-20 (ver «REVALIDAÇÃO POR FOTO») e não estava à vista de onde ele
trabalha. Testes em `tests/test_fases_fotos.py` (7 casos; 6 deles chumbam com a
funcionalidade neutralizada, medido). **O motor não mudou uma linha** — isto é
página e leitura.
- **O botão da Fase 2 é o MESMO endpoint da Deckboxes** (`POST /api/revalidacao`,
  `act: "alvo"`, `tipo: "caixa"`), logo o mesmo `revalidacao.definir_alvo`, o
  mesmo `escrever_config` e o mesmo `regenerar` que reescreve o
  `pendentes/esperadas.md`. **Não se escreveu um segundo caminho ao lado**: dois
  caminhos para o mesmo gesto discordam um dia em silêncio, que é a lição do
  `e_foil`, do `vistoId` e do `venda.mostrar`.
- **O ALVO ACTUAL vai em destaque nas duas fases de fotos**, com quantas cópias
  faltam fotografar nele, e **sem alvo di-lo em voz alta** (*"Não há alvo de
  revalidação"*). Sem isso ele fotografa uma caixa a pensar que está a
  fotografar outra e a corrida da noite liga as fotos às cópias erradas — sem um
  único erro. O número sai do **mesmo `revalidacao.progresso`** que a Deckboxes
  mostra (`arrumacao.alvo_actual`), nunca de uma contagem própria; e **só se
  calcula quando há alvo**, porque o progresso percorre a colecção inteira.
- **A página diz ONDE largar as fotos, e onde NÃO** — na própria página e no
  rodapé, não só no `LEIA-ME`.
  **[CORRIGIDO A 2026-10-01, à tarde]** esta linha dizia *"soltas na raiz de
  `pendentes\`; nunca em `Colocar fotos da coleção aqui\`, que é para cartas
  novas"* — e ele decidiu o contrário (*"o melhor é criar pasta"*). São **duas
  portas**: o botão «Tirar fotos» da página (a foto guarda-se sozinha) ou a
  **pasta do deck**, `Colocar fotos da coleção aqui\<Nome do deck>\`, que
  **vale como alvo** — ver «A PASTA POR DECK VALE COMO ALVO». O que fica
  igual: o que não é de um deck (a venda, o inventário) vai solto na raiz de
  `pendentes\` com o alvo no botão; `pendentes\deckboxes\` **nunca** é para
  cartas (é a foto da caixa de plástico, ponto 13); e estas cópias já estão no
  inventário — o que a foto faz é **ligar-se à cópia que já existe**.
- **A TRAVA DA VENDA NÃO APANHA AS FOTOS, e foi verificado em vez de assumido.**
  `fases.exige_descongelado` vive em três sítios e só nesses — `venda.exportar`,
  `webapp._exige_venda` (as duas portas de escrita da venda) e
  `daily.venda_export`. Nem o `/api/revalidacao`, nem o `fila_decks`, nem a
  página são gatilhados por ela (a página só a LÊ, para o 🔒 do cabeçalho).
  Estava certo: **não havia nada a corrigir**. Tem caso de teste que o tranca com
  a trava LIGADA, no mesmo pedido: a exportação é 409 e o alvo é 200.
- **A FASE 4 É A MESMA MECÂNICA, com o alvo `venda`** — o caminho está feito e
  abre-se quando a trava se levantar, sem ninguém mexer no código: até lá a
  página mostra o que vai aparecer e porque é que ainda não aparece. Abri-lo com
  a trava posta era começar o passo que a trava existe para adiar.
  **[2026-10-04, ao fim do dia: a trava deixou de ter data, por isso a página
  deixou de dizer «a partir de 12/10» — que passaria a ser uma promessa falsa —
  e passou a dizer COMO se destranca.]**

**UMA FOTO LEVA NO MÁXIMO QUATRO CARTAS, E AS ANTIGAS ARQUIVAM-SE (André,
2026-10-01, à letra).** *"organiza o Blue farm e CDEH por tipo de carta e ate 4
cartas por foto"* e *"se sao 4 fotos, e 1 foto com as 4 cartas"*. Motor em
**`mtgvault/fotos.py`** (a regra, o agrupamento, o resolvedor e o arquivo, tudo
num sítio só); testes em `tests/test_fotos_ate_4.py` (12 casos) e a prova de que
chumbam sem a funcionalidade em `tests/_provar_chumba.py`
(+ `tests/_chumba_fotos.py`, 7 alvos / 14 casos). CLI `py -m mtgvault.cli fotos
[estado|arquivar|perdidas]`.

- **DUAS REGRAS ERRADAS ESTIVERAM AQUI ESCRITAS NO MESMO DIA, e as duas pela
  mesma razão: a UNIDADE da fila.** A primeira — *"a fila conta CÓPIAS FÍSICAS:
  um playset dá quatro linhas"* (o `fases._explode`) — dava **quatro fotos a um
  playset**, quatro vezes o trabalho dele. A segunda — *"uma foto por linha, e
  uma foto só valida cópias da MESMA carta"* — também não: **uma foto PODE
  validar cartas diferentes**, até quatro. O que distingue estas fotos das de
  grupo antigas **não é serem da mesma carta**: é serem no máximo quatro,
  dispostas e agrupadas, com cada carta à vista e avaliável.
- **A REGRA, e é uma só:** (1) as cópias da **mesma carta** vão sempre juntas na
  mesma foto (4× Mox Opal = **1** foto); (2) num deck **singleton** (os dois de
  cEDH) juntam-se até 4 cartas **diferentes**, agrupadas **por tipo** —
  planeswalkers, criaturas, artefactos, encantamentos, instantâneos, feitiços,
  terras — e **uma foto nunca atravessa dois tipos**; (3) uma linha da `copies`
  não se parte entre duas fotos, **excepto** a que sozinha passa das quatro (as
  29 Snow-Covered Plains): essa enche fotos inteiras só dela, marcadas
  `partida`, porque não há outra forma de respeitar o tecto — e fica dito em vez
  de resolvido em silêncio.
  **[CORRIGIDO A 2026-10-02]** o ponto (3) deixou de valer para os TERRENOS
  BÁSICOS — *"para as basicas, nos decks, tens que permitir tirar foto com mais
  cartas e nao apenas 4"*: as 29 Snow-Covered Plains são **uma** foto (marcada
  `isenta`) e não oito, porque o tecto existe para cada carta ficar à vista e
  avaliável e numa pilha de terras idênticas isso não quer dizer nada. A
  excepção é só para fotos que sejam **só** de básicas (`fotos.so_basicas`);
  uma carta normal de 29 cópias continua a dar 8 fotos `partida`. Ver «AS
  REGRAS DE MATERIAL DOS TRÊS GRUPOS, E AS DUAS EXCEPÇÕES DAS BÁSICAS».
- **A ORDEM é a dele e é DELIBERADAMENTE outra que a do `paginas.TIPOS`**
  (Creature primeiro, pedido dele de 2026-08-31, que é a ordem por que se LÊ uma
  decklist). O que **não** se duplicou foi a PRECEDÊNCIA: em que tipo cai uma
  carta de vários tipos continua a responder o `paginas.tipo_de` — Artifact Land
  → Artifact (Ancient Den), Enchantment Land → Enchantment (Urza's Saga),
  Artifact Creature → Creature (Memnite, Walking Ballista). Duas perguntas, duas
  ordens, uma precedência.
- **A BARRA DE PROGRESSO CONTA FOTOS**, com as **cartas** e as **linhas** ao
  lado (`fotos.barra`). A foto é o gesto; e uma foto de 4 e uma de 1 não dão o
  mesmo trabalho, por isso os dois números vão ao lado em vez de um substituir o
  outro. O número do **alvo** continua a contar CÓPIAS (*"quantas faltam
  revalidar"*) — é outra pergunta, e sai do mesmo `revalidacao.progresso`.
- **A TRAVA, e vale para os dois lados** (`fotos.valida`): uma foto valida **no
  máximo 4 cartas**. Uma foto **NOVA** com mais do que quatro é **recusada
  inteira** (`collection.import_csv`, com o motivo em português), e a foto fica
  em `pendentes/` — é por aí que ela aparece em «fotos por resolver» e ele a
  volta a tirar. **Recusar só o passo (0) não bastava**: a linha caía na entrada
  normal (iv) e criava cópias NOVAS de cartas que já estão na base — uma
  duplicação em silêncio, o padrão do `event_tier`. A conta é **por FOTO e não
  por linha** (uma foto traz várias linhas de CSV), e por isso o CSV lê-se
  inteiro ANTES de se escrever uma linha: saber-se-ia o total só na última, com
  as primeiras já na base. Uma foto **ANTIGA** com mais de quatro **não conta
  como validação** (`revalidacao.fotos_que_nao_validam`) e as cópias dela
  continuam por revalidar.
- **MEDIDO na base de 2026-10-01** (contra os números do supervisor, que
  batiam quase todos): **348** `photo_path` distintos ✓, **322** ficheiros em
  `pendentes/fotos processadas` (**96,4 MiB**; ele disse 98 MB) ✓, **33** já sem
  ficheiro no disco ✓, **723** das 737 linhas com foto e **14** sem ✓,
  `validado_em` e `foto_anterior` a **zero** nas 737 ✓. Dois números a corrigir:
  a *"média de 2,1 cópias por foto e máximo 12"* é a média de **LINHAS** por
  foto — em **CARTAS** a média é **4,77** e o máximo **33**, e é essa que conta
  para a trava (**172 das 348** fotos antigas têm mais de 4 cartas, 1 171 cartas
  nelas); e as fotos **sem** alocação são **242** e não 282 (348 − 106).
  A lista de por-revalidar diz **727** linhas e não 737: as outras **10** estão
  «edição por confirmar» e saem de propósito (são do `acertar_edicao`, que
  também as valida).
- **O PLANO DELE E O MEU DÃO O MESMO**, carta a carta: **47 fotos para 161
  cartas** — Blue Farm **28** fotos / 96 cartas (96 linhas), Cloud cEDH **19** /
  65 (63 linhas). Comparados foto a foto (`_revisao/comparar_plano.py`), a única
  diferença é cosmética: o plano dele imprime o nome inteiro de uma carta de
  dupla face (*"Birgi, God of Storytelling // Harn"*) e o meu só a frente, que é
  a chave por que o `loadout` indexa. Fase 2 inteira: **124 fotos, 411 cartas,
  261 linhas** (as 411 cópias que o CLAUDE.md de hoje já media); Fase 4 **315
  fotos / 1 029 cartas**; inventário **92 / 305**. (A Fase 4 e o inventário
  agrupam as **fotos perdidas à cabeça**, e é isso que lhes muda a contagem face
  a uma medição sem essa ordem — 308 e 94: a foto perdida à frente parte um
  grupo de quatro ao meio. É o custo de a prioridade dele mandar na fila, e é
  deliberado.)
- **A ORDEM DE TRABALHO: primeiro os decks de LISTA ÚNICA** (ordem dele: *"começa
  pelos decks que são lista única e não são «de conversão» — os dois de cEDH, que
  têm cartas dedicadas e uma lista cada. A família de Premodern partilha o mesmo
  conjunto de cartas e monta-se por conversão de uma noutra: fica para depois"*).
  A base não tem coluna «de conversão» e não se inventou uma: **DERIVA-SE**, e a
  regra é — *o grupo de formato da caixa tem um tecto de playset contado sobre o
  **grupo inteiro** (`regras_por_formato[].playset_maximo`) e há 2+ caixas nesse
  grupo*. Esse tecto só existe porque as caixas trocam a carta entre si (decisão
  de 2026-09-08), e o `prioridade_por: "pct"` do mesmo grupo confirma-o. Está
  **escrito no config**. Hoje apanha exactamente as 6 caixas de Premodern e mais
  nenhuma. **O que NÃO serve para derivar isto, e foi medido antes de se
  escolher: a SOBREPOSIÇÃO das listas** — o Blue Farm e o Cloud cEDH partilham
  **24 nomes (26 % do menor)**, *mais* do que a maior sobreposição entre duas
  caixas de Premodern (Oath × Enchantress, 32 %, com a média do grupo em ~20 %):
  pela sobreposição o cEDH era «de conversão» e parte do Premodern não, ao
  contrário do que ele disse. A fila ordena lista-única primeiro e **escreve a
  razão em cada deck** (`fases.NOTA_CONVERSAO`), porque uma ordem sem razão à
  vista é uma ordem que se desfaz no dia seguinte.
- **ARQUIVAR, NÃO APAGAR.** Ele propôs **apagar** as fotos antigas e tirar tudo
  de novo; concordou-se com o refotografar (é a campanha de 20/09) e discordou-se
  do apagar, e ele aceitou. **Não se apagou um único ficheiro**: o
  `fotos.arquivar` (CLI `fotos arquivar`) **move** `pendentes/fotos processadas/`
  para **`data/fotos/anteriores/`**, para a pasta de trabalho dele ficar limpa
  sem se perder prova. As razões, porque é a parte que se esquece: **98 MB não
  custam nada**; enquanto a campanha não acabar as antigas são a **única prova de
  723 das 737 linhas**; o **`foto_anterior`** existe para a correcção (0b) ser
  confiável, e sem a foto antiga no disco não há como confirmar uma correcção; e
  **33 já estavam perdidas**, que é exactamente a razão para não perder o resto.
  Um ficheiro que já exista no destino **não se pisa** — fica e diz-se.
- **E NÃO SE REESCREVEU UMA ÚNICA DAS 723 LINHAS.** Os `photo_path` da base dele
  são **nomes simples** (`<uuid>.jpg`; medido: **zero** com separador de pasta) e
  valiam por estar numa pasta só — mover sem mais nada quebrava-os todos. Quem
  passa a procurar nas DUAS é o **`fotos.resolver`**, num sítio só, com a pasta
  de **trabalho a ganhar** quando a foto existe nas duas. **E encontrou um
  defeito anterior a isto:** o `loadout.foto_da_copia` resolvia
  `ROOT / photo_path`, logo `<repo>/<uuid>.jpg`, que **não existe** — as 723
  linhas com foto davam **todas `None`** e o `/foto?copy=` do 8771 (a miniatura
  de uma cópia «não encontrada», a única prova de que a carta existiu) respondia
  **404**. Hoje responde.
- **AS FOTOS NOVAS ARRUMAM-SE POR DECK, sozinhas** (ordem dele): o `arrumar_fotos`
  passou a guardar em **`data/fotos/<slot>/`** quando a foto traz um alvo de
  caixa, `data/fotos/venda|rl|coleccao/` nos outros tipos de alvo, e
  `data/fotos/sem-alvo/<AAAA-MM>/` quando não há alvo — **o slot vem do ALVO da
  revalidação** (do nome da foto, `site-<slot>-…`, que é o botão «Fotografar» a
  escrevê-lo, e na falta dele do `revalidacao.alvo` do config), **nunca de
  adivinhar pela carta**. A árvore:

  ```
  data/fotos/
    anteriores/            as 322 antigas (arquivo; eram pendentes/fotos processadas/)
    <slot>/                uma pasta por deck: cedh-blue-farm/, cedh-cloud/, …
    venda/  rl/  coleccao/ os outros três tipos de alvo
    sem-alvo/<AAAA-MM>/    foto sem alvo nenhum — à vista, não escondida num deck
  ```

  A pasta fica **fora do Git** (`.gitignore`: `data/fotos/`) — são imagens, e a
  única excepção consciente continua a ser a reduzida da deckbox física em
  `assets/deckboxes/`. Quem as guarda é o `backup-offsite` do ai-pc.
- **AS 33 FOTOS PERDIDAS SÃO AS PRIMEIRAS** (`fases.fotos_perdidas`,
  `revalidacao.progresso → perdidas`): o `photo_path` está preenchido e o
  ficheiro já não está no disco. **Não se inventa a foto nem se limpa o campo** —
  o campo é a prova de que ela existiu. São as únicas cópias **sem prova
  nenhuma**, por isso abrem a Fase 2 num bloco próprio, vêm à cabeça de cada
  grupo da lista de por-revalidar e à cabeça da Fase 4. Medido: **33 fotos, 155
  linhas da `copies`, 165 cópias, 12 639,42 €** — e **92 das 96** cartas do Blue
  Farm e **56 das 65** do Cloud cEDH estão entre elas, que é outra razão para
  começar por esses dois.
- **A CAMPANHA ESTÁ LIGADA E COERENTE**: `revalidacao.desde = 2026-09-20` (≤ hoje),
  `alvo = null`. As 737 linhas / 1 678 cópias estão todas por revalidar
  (`validado_em` = 0), e o fluxo ponta a ponta está trancado por teste: uma foto
  nova de 4 cartas diferentes **não cria cópia nova**, grava `validado_em`, grava
  `foto_anterior` com a foto antiga, a antiga **continua no disco**, e as quatro
  ficam validadas **de uma vez**.
- **O PLANO DE CADA DECK TAMBÉM EM TEXTO, e por uma razão de segurança**
  (`fotos.texto_do_plano`, CLI `fotos plano`). Apareceram no repositório, feitas
  à mão, **uma pasta por deck dentro de `Colocar fotos da coleção aqui\`** com um
  `_plano.txt` que prometia o plano **e mandava largar as fotos nessa pasta** —
  e **nada no vault processa essa pasta** (o `mtg-fotos-novas` e o
  `processar_fotos.py` lêem a RAIZ de `pendentes/`): as fotos ficavam lá para
  sempre, sem um único erro. O `fotos plano` reescreve esses ficheiros com o
  plano a sério — **das MESMAS fotos que a página desenha**, nunca de uma
  segunda contagem. Só escreve onde a pasta JÁ existe: não se criam pastas por
  iniciativa própria.
  **[CORRIGIDO A 2026-10-01, à tarde]** esta linha dizia que a instrução certa
  era «`pendentes\`, e fixar o alvo primeiro» — e a decisão dele foi a outra:
  *"o melhor é criar pasta"*. A pasta **passou a valer como alvo**, o
  `_plano.txt` manda largar as fotos ali, e o motor saiu do CLI para o
  `fotos.escrever_planos`, que o **daily reescreve todas as noites**. Ver a
  secção a seguir.
- **O `backup-offsite` do ai-pc teve de aprender as duas pastas**
  (`plano.FOTOS_DIRS`). Lia só `pendentes/fotos processadas/`: a partir do dia
  em que as fotos passaram para `data/fotos/` dizia *«0 novas»* e guardava
  nada, verde, para sempre — o MESMO defeito que o `iterdir()` teve a 08/09, e
  as 322 fotos arquivadas são a prova de 723 linhas da base. E a entrada do
  índice **muda de chave** quando a foto só mudou de pasta (mesmo nome, mesmo
  `sha256`), senão subiam 96 MB outra vez sem necessidade. Verificado com
  `work/revisao/_verificar_backup_fotos.py` (três corridas: vê as duas pastas,
  não reenvia a arquivada, 0 novas à terceira).
- **O MOTOR NÃO MEXEU.** Medido na base de 2026-10-01, antes e depois: candidatos
  **1 029 cópias / 31 150,15 €**, Fase 2 **411 cartas**, inventário **305
  cópias / 97 249,84 €** — os mesmos números da secção «A ARRUMAÇÃO POR FASES».
  O que mudou foi a UNIDADE da fila (411 cartas em **124 fotos**), o resolvedor,
  o arquivo e a ordem dos decks.

**O CANO DAS FOTOS AGUENTA A CAMPANHA (2026-10-02).** Ele vai fotografar a
colecção INTEIRA — 1 678 cartas em fotos de até quatro, ~500 fotos, deck a deck,
e o que não está em deck nenhum numa pasta nova `Extras (fora dos decks)\`. São
dias de trabalho dele, e por isso o que se fez foi **provar o cano antes de ele
começar**, com o fluxo REAL das 02:30 (o `run.py` da tarefa `mtg-fotos-novas`)
sobre uma cópia da base dele e com imagens fabricadas — só o `claude -p` (cujo
único produto é o `recat.csv`) e o `gh release upload` (que publicaria a base de
teste) ficaram em esboço. Testes em `tests/test_cano_fotos.py` (13 casos) e a
prova de que chumbam em `tests/_chumba_cano.py` (11 alvos).

- **A TAREFA NUNCA PROCESSOU UMA FOTO EM PRODUÇÃO: 202 corridas, 202 × «sem
  fotos novas».** É o número que enquadra tudo o que segue — o cano em que ele ia
  assentar dias de trabalho nunca levou uma foto de ponta a ponta, e por isso
  nenhum destes defeitos tinha aparecido.
- **A PASTA `Extras (fora dos decks)\` NÃO ESTAVA LIGADA A NADA.** Ele criou-a às
  13:13 desse dia com um `_plano.txt` escrito à mão; o `mapa_pastas` deriva do
  `caixas` e aquela não é uma caixa, por isso a recolha deixava-a em `ignorados`
  — **a foto ficava lá para sempre e a tarefa dizia «sem fotos novas», VERDE**.
  Ligou-se ao alvo **`coleccao`** que já existia desde 2026-09-21
  (`fotosite.TIPOS`) e é exactamente isto — *"estou a fotografar a colecção, não
  um deck"*: a foto passa a chamar-se `site-colecao-…`, e daí para a frente é o
  caminho de sempre, sem uma linha nova. `fotos.PASTAS_FORA_DOS_DECKS`. As
  QUATRO pastas de grupo **não** se ligaram, e é decisão: já tinham um
  significado dele antes disto.
- **A MESMA FOTO ERA PROVA DE DUAS CARTAS.** Uma foto cujas linhas não entraram
  todas **fica** em `pendentes/` (regra do `arrumar_fotos`, e está certa: *"arrumá-
  la escondia trabalho por fazer"*). Só que a corrida seguinte relê a MESMA foto,
  com o MESMO nome: a cópia já está validada (o passo (0) não a apanha), já tem
  `photo_path` (o (iii) também não) e cai no (iv), que **cria uma cópia nova**.
  Medido no ensaio: duas linhas da `copies` com o mesmo `photo_path`, e **uma por
  noite** enquanto a linha falhada não fosse resolvida. Numa campanha de 500
  fotos basta uma edição que não se consiga fixar para a colecção inflacionar
  sozinha. A trava é `fotos.consumidas`/`ja_e_prova`, pela identidade da FOTO (o
  **nome** do ficheiro, que é o que sobrevive ao `arrumar_fotos` reescrever o
  `photo_path` com a pasta do deck à frente) e **não pela carta** — travar pela
  carta perdia a segunda cópia a sério de uma carta que ele tem duas, e tem caso
  de teste. A linha repetida sai com resultado **`repetida`**, que não é erro:
  não há nada para ele fazer, e pôr a tarefa a vermelho todas as noites era um
  vermelho que se deixa de ler.
- **O ALVO DA COLECÇÃO NÃO TINHA CÓPIAS NENHUMAS.** O alvo chama-se `coleccao` e
  o grupo da `particao` chama-se `resto`; **três** sítios traduziam isso à mão e
  o `revalidacao._chave` esqueceu-se, devolvendo `("coleccao",)` para um grupo
  que nunca existe. Consequência: o passo (0) ficava sem preferência e a
  correcção por discrepância (0b) — que EXIGE `alvo["copias"]` — **nunca
  disparava fora dos decks**: uma carta dos Extras fotografada noutra edição
  criava uma cópia nova em vez de corrigir a que lá está. A tradução vive agora
  em `revalidacao.GRUPO_DO_TIPO`, e os três sítios lêem de lá.
- **500 FOTOS NÃO CABEM NUMA CORRIDA, E A TAREFA MANDAVA-AS TODAS NUM
  `claude -p`** com `--max-turns 80` e 25 min de tecto. **Medido nas 65 corridas
  da tarefa irmã `mtg-fotos` (a que lê fotos de cartas com o Claude há 1 119
  corridas): 44 s por foto de mediana, 119 s no pior caso, e o maior lote que
  alguma vez se tentou foram 5 fotos.** Logo o tecto real era **~30 fotos**; com
  500 o processo era morto aos 25 min, o `recat.csv` não aparecia, **não se
  importava nada** — e repetia-se o mesmo falhanço todas as noites, sem nunca
  progredir. Agora são **lotes de `LOTE` (10) fotos**, um `claude -p` por lote
  (contexto fresco, que é o que o faz caber), tantos quantos couberem no
  `ORCAMENTO_S` (1 400 s, abaixo do `timeout` de 1 800 da tarefa **e** da ordem
  encadeada), com `--max-turns` proporcional ao lote. **A RETOMA NÃO PRECISA DE
  FICHEIRO DE ESTADO: o progresso é a PRÓPRIA PASTA** — uma foto processada é
  movida pelo `arrumar_fotos`, e uma que fica é porque tem trabalho por fazer
  (o mesmo princípio do `arquetipo_fonte_de`). As TRAVADAS vão para o FIM da
  fila: entrando sempre no primeiro lote, eram elas a comer o orçamento todas as
  corridas e a campanha nunca avançava. Sobrando fotos **e** tendo a corrida
  andado, pede-se outra pelo MESMO caminho do «⚡ Processar agora»
  (`fotosite.pedir_processamento`) — sem isso, 500 fotos a 10 por corrida e uma
  corrida por noite eram **cinquenta noites**. **Medido**: 40 fotos → 4 lotes de
  10, 40 cópias, 0 por fazer, 67 s de trabalho Python; e com o custo real de 44 s
  por foto, 3 lotes em 1 331 s e 10 fotos a ficar para a corrida seguinte, com o
  `parou_por` a dizer porquê. O chão é o Claude a ler: **500 fotos são ~6 h**,
  façam-se os lotes que se fizerem.
- **DOIS LOTES NO MESMO MINUTO MATAVAM A TAREFA.** O CSV guardado chamava-se
  `recat-<AAAAMMDD-HHMM>.csv` e o `Path.rename` do Windows levanta
  `FileExistsError`: a segunda corrida do mesmo minuto rebentava **depois** de a
  base estar escrita e as fotos arrumadas, com **stdout VAZIO** e sem publicar o
  Release — trabalho feito e não relatado. O nome passou a ser livre, e o `main`
  ganhou uma rede (`main_guardado`) para o JSON sair sempre.
- **O TESTE DA TAREFA IA A VERMELHO NA PRIMEIRA NOITE EM QUE ELA FUNCIONASSE.**
  Procurava as fotos em `pendentes/fotos processadas/` (desde 01/10 vão para
  `data/fotos/<slot>/`) e comparava o `photo_path` com o nome CRU (o
  `arrumar_fotos` põe-lhe a pasta do deck à frente): **dois erros falsos por
  foto**, a dizer *«a foto perdeu-se»* e *«o import não escreveu»* sobre um
  import que escreveu. Nunca se tinha visto porque nunca houve uma foto. Hoje
  olha para as duas pastas e compara pelo NOME; e as asserções passaram a ser
  sobre as fotos que a corrida **tentou** (com lotes, o `photos` é a fila
  inteira). Tem cenário novo: se a tarefa diz que sobram fotos e a pasta está
  vazia, a retoma perdeu-as. Os três cenários de «verde a fingir» continuam a
  chumbar.
- **SETE DOS 17 DECKS NÃO TINHAM PASTA, E QUATRO PASTAS DELE NÃO MAPEAVAM PARA
  NADA.** Medido nesse dia: sem pasta a `Affinity (Luffy)`, `Elves`,
  `Modern — Affinity`, `Bant Airbend`, `Engineer Welder Cam`, `Aluren` e
  `Artifacts Blue` (as novas de 02/10 e as renomeadas) — e uma foto largada em
  `Elves - Survival\`, `Pauper (Luffy)\`, `Jeskai Control\` ou `Legacy\` ficava
  lá, calada. O `fotos.garantir_pastas` cria a pasta de cada deck do config (o
  nome sai do `caixas`, a MESMA regra que a reconhece) com um `.gitkeep`; **não
  se apaga nem se move nada** (a regra dele de 09/09) — o que se troca é o TEXTO
  do `_plano.txt` das órfãs (`fotos.TEXTO_ORFA`), porque um ficheiro NOSSO a
  dizer *«LARGA AS FOTOS NESTA PASTA»* numa pasta que o vault já não reconhece é
  pior do que ficheiro nenhum. E uma pasta órfã **com fotos dentro** passou a ser
  ERRO na tarefa (as de grupo continuam caladas): um lote dele perdido de vista
  sem ninguém notar era o pior resultado possível.
- **O `_pastas_do_slot` escreve o plano em TODAS as pastas que apontam para o
  deck.** São duas quando o nome antigo é o próprio `slot` — o `Standard\` do
  slot `standard`, hoje «Bant Airbend»: essa continua a valer como alvo (o mapa
  indexa o slot), por isso não é órfã, mas o `pasta_do_deck` não a encontrava e
  ficava com o plano congelado do dia do rename. E as pastas acabadas de criar
  ficavam com um `.gitkeep` e mais nada: a guarda era *«só onde já existe um
  `_plano.txt`»*.
- **A PERGUNTA «DE QUEM É ESTA PASTA» VIVE NUM SÍTIO SÓ — e não vivia.** Escrevi
  o `alvo_da_pasta` com a docstring a dizer isso e dupliquei a conta dentro do
  `fotos_nas_pastas`, que é por onde passa TODA a produção (`webapp`, `daily`,
  `cli`); a função ficava a ser chamada só pelos testes. Ligar uma pasta nova
  mexendo nela não teria efeito nenhum — o defeito dos `Extras` recriado. Tem
  caso que troca a função e exige que a recolha mude com ela.
- **A CONTA DAS CARTAS POR FOTO É PELO NOME DO FICHEIRO.** O
  `revalidacao.fotos_que_nao_validam` agrupava pelo `photo_path` inteiro, e o
  `arrumar_fotos` só o reescreve para as cópias da corrida em que a foto SAI de
  `pendentes/`: a mesma foto ficava com duas chaves e uma foto de 6 cartas
  lia-se como 3 + 3 — as duas dentro do tecto de 4. Os outros três sítios que
  fazem esta conta já usavam o nome.
- **O `processar_fotos.py` ESCREVIA NA BASE SEM BACKUP.** É o caminho que o
  `PROCESSAR_FOTOS.md` manda correr à mão, e o import não é só acrescentar:
  desde 20/09 o `revalidacao.corrigir` **reescreve** a impressão de cópias que já
  cá estavam, o `_sai_da_caixa_se_nao_cumpre` apaga linhas da `copy_allocation`,
  e a seguir o `db_push` publica isto por cima da base do Release. A tarefa das
  02:30 e os botões do 8771 fazem `migracao.backup` primeiro; este era o único
  sem rede.
- **A FILA DE «À ESPERA» TEM TECTO** (`deckboxes.MAX_FILA`, 25): com centenas de
  fotos largadas de uma vez, uma lista de 300 `<li>` num telemóvel é uma página
  que não se usa. O total continua no cabeçalho, e o resto é *«… e mais N na
  fila»*. A PROGRESSÃO a sério — quantas fotos faltam, por deck — é a barra da
  Fase 2 em `arrumacao.html`, que sai da base (validado vs. por revalidar).
- **O QUE SE MEDIU E NÃO SE MEXEU, de propósito:** o `scryfall.find_printing` e
  o `resolve_name` **são mesmo varredura** do catálogo (`EXPLAIN` → `SCAN cards`
  sobre 112 754 impressões) e correm por linha de CSV — mas o caminho rápido
  (`name = ?`, pelo `ix_cards_name`) apanha o caso normal: **5,0 ms e 1,8 ms** por
  nome, e **38–70 ms** no pior caso (um nome que não existe, um erro de leitura).
  2 000 linhas são 4–10 s, e 100 nomes mal lidos 4–7 s. Ao lado das ~6 h de
  leitura não é defeito, e trocar consultas quentes na véspera da campanha dele
  era o risco errado a correr. As consultas do passo (0)
  (`revalidacao._sel_copias`) varrem a `copies` (737 linhas) e vão ao catálogo
  pela chave primária: **3,7 ms**.

**A PASTA POR DECK VALE COMO ALVO (André, 2026-10-01, à tarde, à letra: «o
melhor é criar pasta»).** Ele perguntou de manhã onde é que punha as fotos, e a
resposta foi mandá-lo para a raiz de `pendentes/` depois de fixar o alvo no
botão. **Ele decidiu outra coisa, e a decisão dele é que vale**: quer uma pasta
por deck em `Colocar fotos da coleção aqui\<Nome do deck>\` e largar as fotos
lá. Motor em `mtgvault/fotos.py` (`mapa_pastas`, `slot_da_pasta`,
`fotos_nas_pastas`, `recolher_das_pastas`, `escrever_planos`); CLI
`py -m mtgvault.cli fotos pastas|recolher|plano`; passos `fotos-pastas` e
`fotos-plano` do `daily`; testes em `tests/test_pasta_por_deck.py` (13 casos) e
a prova de que chumbam sem a funcionalidade em `tests/_provar_chumba.py`
(+ `tests/_chumba_pasta.py`, 9 alvos / 11 casos). **O motor de alocação não
mudou uma linha** — isto é pasta, nome de ficheiro e texto.

- **UM CAMINHO SÓ, e é o que já estava testado.** A foto da pasta é **movida**
  para a raiz de `pendentes/` com o nome `site-<slot>-<data>-<n>.<ext>`, que é
  exactamente o nome que o botão «Tirar fotos» escreve (`fotosite.nome_ficheiro`,
  2026-09-21). Daí para a frente não há uma linha nova: o
  `revalidacao.alvo_da_foto` prefere as cópias daquela caixa, o `esperadas.md`
  lista-a na secção «Fotos tiradas no site», o `arrumar_fotos`/`pasta_do_alvo`
  arruma-a em `data/fotos/<slot>/`, e o Claude que cataloga vê a mesma coisa que
  sempre viu. Escrever um segundo caminho ao lado era deixar os dois discordarem
  um dia qualquer, em silêncio — a lição do `e_foil`, do `vistoId` e do
  `venda.mostrar`. O nome ORIGINAL dele vai no relatório da recolha e no
  `webapp.log`: não se perde em silêncio.
- **O MAPA pasta → slot É DERIVADO DO `caixas` DO CONFIG, nunca escrito à mão.**
  No dia em que ele renomear um deck, a pasta que o vault reconhece muda com ele
  — uma lista à mão funcionava até esse dia e falhava calada. Aceita o NOME nas
  duas formas (a «Elves / Survival» não cabe num caminho: a pasta tem ` - `, e é
  o `fotos.nome_de_pasta`, a MESMA regra por que o `_plano.txt` se escreve) e o
  próprio `slot`, com o nome a ganhar sempre. O `_norm` reduz `-`, `/`, `—`, `–`,
  `_`, `(`, `)` e espaços a um espaço só: o «Modern — UW Oswald» não depende de
  ele acertar no travessão. Medido no config dele: **28 chaves, as 15 caixas**.
- **ONDE É QUE O MAPA ESTAVA ANTES: EM LADO NENHUM.** Procurado no vault e na
  tarefa — o `mtg-fotos-novas` faz `PEND.iterdir()` e o `processar_fotos.py`
  também: os dois só olham para a RAIZ de `pendentes/`. A correspondência
  pasta → deck só existia em prosa, no `LEIA-ME.txt`, para eu a ler a pedido
  dele. Ficou no mtgvault, com teste, e a tarefa **chama-o** (`fotos recolher
  --json`) em vez de o reimplementar.
- **AS SUBPASTAS DE LOTE CONTAM PARA O MESMO DECK** (`Blue Farm\lote1\`): o
  `LEIA-ME` sempre disse que se podiam fazer, e perdê-las aqui era mudar-lhe a
  rotina sem o avisar. O que manda é a **primeira** pasta abaixo da pasta-mãe —
  um ficheiro largado na pasta-mãe não tem deck e não se adivinha.
- **AS PASTAS DE GRUPO FICAM COMO SEMPRE FORAM.** `Premodern (geral)`,
  `SPML (…)`, `Coleção Pessoal` e `Vender` não são um deck: ninguém as processa
  sozinho, e era assim antes disto. A foto fica lá — e **diz-se porquê**, que é a
  diferença entre «decidido» e «esquecido». O `_nomes antigos\` (onde o
  supervisor pôs duas pastas renomeadas, sem apagar nada) fica fora: uma pasta
  que começa por `_` não é um deck. Adivinhar o deck pelo nome da pasta é
  exactamente o que o `fotocaixa.recolher` já tinha aprendido a não fazer.
- **O SOSSEGO DE 20 s.** Uma foto acabada de largar pode estar a meio da cópia;
  movê-la era parti-la. Espera-se, e vem na passagem seguinte. O `shutil.move`
  **preserva o mtime** dentro do mesmo volume, por isso a regra dos 2 minutos do
  `mtg-fotos-novas` continua a valer do outro lado — e o nome novo leva o mtime
  da foto (quando ela foi tirada), não a hora da recolha.
- **TRÊS CHAMADORES, e é de propósito**: o **`mtg-fotos-novas`** das 02:30 (antes
  de olhar para `pendentes/`), o **modo de edição** a cada pedido do índice (para
  a foto aparecer em «📸 fotos enviadas, à espera» e o «⚡ Processar agora» a
  apanhar, sem esperar pela noite — e num GET um lock ocupado não rebenta a
  página: a recolha pode esperar pelo pedido seguinte) e o **`daily`**
  (`fotos-pastas`, rede de segurança, imediatamente antes do `esperadas.md`). Uma
  foto parada numa pasta de grupo **não põe a tarefa a vermelho** (sai em
  `das_pastas_deixadas`, não em `errors`): um vermelho que é normal deixa de se
  ler.
- **O `_plano.txt` É REESCRITO PELO DAILY** (passo `fotos-plano`), das MESMAS
  fotos da Fase 2 que a página acabou de desenhar — **a pasta e a página têm de
  dizer o mesmo número**. Por isso o motor saiu do CLI para o
  `fotos.escrever_planos`: duas escritas do mesmo ficheiro divergiam no dia em
  que uma mudasse. A pasta entrou no **`git add` do `daily.yml`** e no
  **`EXTRA_COMMIT` da tarefa `mtgvault-daily`** (é uma pasta, como
  `data/paginas`); as imagens continuam fora pelo `.gitignore`, que ganhou o
  `.heif` que lhe faltava nas duas listas. A pasta de um deck **sem cartas na
  caixa** fica com a nota a dizê-lo: um plano que promete fotos de um deck vazio
  é um ficheiro a mentir.
- **MEDIDO na base de 2026-10-01**, antes e depois: `loadout.report` **igual** —
  fechar tudo **8 928,35 €**, **240** a comprar, **225** a arrumar; Fase 2
  **124 fotos / 411 cartas** em 6 decks (Blue Farm 28/96, Pauper 22/74, Cloud
  cEDH 19/65, Modern 16/52, UW Replenish 20/66 ⏸, Stiflenought 19/58 ⏸), os
  mesmos números das duas secções de cima. **15 pastas de deck reconhecidas**,
  15 `_plano.txt` escritos (6 com plano, 9 com a nota de «sem cartas na caixa»),
  4 pastas de grupo intocadas. Ponta a ponta no repositório a sério: uma foto
  largada em `Blue Farm\` saiu com
  `site-cedh-blue-farm-<data>-1.jpg`, o `fotosite.origem` leu-lhe a caixa e o
  `alvo_da_foto` deu as cópias do `cedh-blue-farm` (a foto de prova foi apagada
  — era minha, de mentira, e não é prova de nada).

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

Coluna nova do CATÁLOGO de 2026-10-01: **`catalog.cards.oracle_text`** (nos três
sítios: `catalog_schema.sql`, `db._migrate()` e `scryfall._row`/`INSERT`). Entrou
para as quatro protecções da venda poderem DERIVAR do catálogo as listas de
shocklands e fetchlands em vez de as terem escritas à mão (ver «A ARRUMAÇÃO POR
FASES»). **Uma coluna do catálogo não se preenche sozinha**: o `daily._catalog`
salta o `sync` quando o catálogo tem linhas, por isso teve de entrar também no
**`scryfall.has_card_meta`** — é essa a pergunta que faz o catálogo recarregar,
e foi por aí que o `reserved` e o `set_type` se preencheram. Sem ela, a coluna
ficava a NULL para sempre e o `fases.fetchlands` levantava.

Colunas novas de 2026-10-02 (à tarde, nos três sítios):
**`decklists.arquetipo_fonte`** e **`decklists.arquetipo_fonte_de`** — o nome que
a FONTE dá ao deck (o mtgtop8 escreve-o na página do evento) e COMO se chegou a
ele (`evento` na recolha, `recuperado` pelo backfill, `sem-nome` quando a página
foi lida e não trazia nome). A segunda é também o marcador de PROGRESSO do
backfill, o que o torna retomável sem ficheiro de estado — é o mesmo truque do
`event_players` a gravar 0. O **índice `ix_dl_arquetipo` nasce no `_migrate`** e
nunca no `schema.sql`, pela armadilha de sempre. Ver «O NOME DO ARQUÉTIPO VEM DA
FONTE».

Colunas e tabela novas de 2026-10-03 (nos três sítios): **`copies.condition_origem`**
(`foto` | `mao` | `omissao`), **`copies.condition_em`**,
**`copies.condition_motivos`** e **`copies.verso_path`**, mais a tabela
**`condition_log`** (o histórico dos juízos de estado e os EXEMPLOS ROTULADOS das
correcções dele — com `eu_disse`, `eu_motivos`, `escapou` e `aplicado`). A coluna
`condition` já existia e dizia `NM` nas 737 linhas; o que faltava era **de onde
veio o juízo**. O `NM` não se mudou nem se apagou: o que se escreve é a ORIGEM
`omissao`, e é ela que o faz deixar de poder passar por medido. O índice
`ix_copies_cond_origem` nasce no **`_migrate`**, depois do ALTER, pela armadilha de
sempre — e o `UPDATE` que marca o `omissao` só corre **quando há linhas a marcar**
(um `UPDATE` incondicional a cada `init` era uma escrita por pedido do
`webapp.py`, e uma escrita muda o `_versao()` e atira a cache fora). Ver «O ESTADO
DAS CARTAS E OS VERSOS».

Tabela nova de 2026-10-04 (nos três sítios): **`mtgtop8_eventos`** — a MEMÓRIA dos
eventos do mtgtop8 que a recolha já processou, por formato, com o `tecto` de listas
que se lhes aplicou e se ficaram `completo`s. Nasceu com o «nunca perder um torneio
de papel grande»: a recolha passou a ler **três páginas** do índice (58 eventos em
Modern contra 20) e, sem memória, descer no índice custava um pedido por evento já
feito **todas as noites**. **O progresso não podia ser a `decklists`**, como no
`arquetipo_fonte_de`: um evento cujas listas foram todas deduplicadas contra o
mtgo.com não deixa lá uma única linha, e era precisamente esse que se voltaria a
pedir sempre. O `tecto` gravado é o que torna isto auto-corrigível — um evento visto
com o tecto antigo (16) que hoje é grande (64) revisita-se **uma vez**. O índice
`ix_mt8_grande` nasce no **`_migrate`**, e quem a SEMEIA é o
`mtgtop8.semear_memoria` e não o `db` (a semente precisa do `e_grande` e do
`TECTO_ANTIGO`, e importar o `mtgtop8` no `db` fechava um ciclo). Ver «NUNCA PERDER
UM TORNEIO DE PAPEL GRANDE».

Tabelas novas de 2026-10-04 à TARDE (nos dois sítios — `schema.sql` e
`db._migrate()`): **`posse_marcada`** e **`posse_marcada_log`**, a POSSE que ele
marca à mão com o `+` e o `−` da aba Decks. **Nascem VAZIAS de propósito**, e é
isso que faz o inventário PRÉ-PREENCHER as marcas sem escrever 737 linhas: quem
não tem linha responde com a contagem da `copies` (`paginas.posse_total`); com
linha, ela GANHA. O `qty` é ABSOLUTO e não um delta sobre o inventário — uma
cópia nova que entre por foto ou por CSV não pode mexer num número que ele já
confirmou com a carta na mão. O `request_id` do log é **ÚNICO**: é ele que faz um
retry de rede não contar a dobrar. Os índices podem viver no `schema.sql` porque
as tabelas nascem lá inteiras (a regra de 2026-09-09 é para índices sobre COLUNAS
NOVAS de tabelas que já existem). Ver «A ABA DECKS».

**O CRUZAMENTO NOME-DE-LISTA ↔ CATÁLOGO VIVE NUMA FUNÇÃO SÓ (André, 2026-10-04,
ao fim do dia).** Fecha o furo da secção a seguir, que estava apurado e não
emendado. Motor em **`mtgvault/scryfall.py`** (`canonizar`/`chave`/`MapaDeCartas`
/`sql_nome`/`params_nome`/`resolver`/`resolver_muitos`/`desconhecidas`); CLI
`py -m mtgvault.cli cartas-desconhecidas [--onde todas|decks|listas]`. Testes em
`tests/test_nomes_duas_faces.py` (20 casos) e a prova de que chumbam em
`tests/_chumba_nomes_duas_faces.py` (**9 de 9 alvos**, um processo por alvo).

- **O TAMANHO, reproduzido ao exemplar antes de se tocar em código:** dos nomes
  de `decklist_cards`, **240** não casavam com o catálogo, em **7 983 linhas** e
  **4 258 das 7 724 listas (55 %)**. Por VIA: **181 nomes / 7 034 linhas** são a
  FRENTE de uma dupla face; **33 / 701** são o SEPARADOR escrito de outra
  maneira (`Wear/Tear`, `Bedeck / Bedazzle`, `Breaking/Entering` — o catálogo usa
  sempre ` // `); e **26** ficam desconhecidos. Depois: **4 695 de 4 721** nomes
  resolvem (**+214**), e os 26 são **1** variante de pontuação
  (`With Great Power...` ↔ `With Great Power . . .`) e **25 que nem a Scryfall
  tem** — sondada a 04/10, responde **404** a `Ademi of the Silkchutes` e a
  `Zora, Spider Fancier`. O catálogo **não está atrasado** (tem o `spm` de 2025 e
  o bulk do próprio dia); por isso não se inventou a carta.
- **A PREMISSA DA ORDEM ESTAVA MEIO ERRADA, e vale a pena saber qual metade.** A
  ordem dizia que a carta fica *«CONTADA COMO NÃO TIDA»* e que a aplicação mandava
  comprar cartas que ele já tem *«em pelo menos seis decks»*. **A posse já estava
  certa**: o `paginas.posse_total` indexa pela frente (`.split(" // ")[0]`) desde
  sempre. Verificadas as sete afirmações dele uma a uma — Sink into Stupor 5,
  Tamiyo 4 (em quatro decks), Witch Enchanter 5 — **todas já contavam bem**; o
  único mal contado era o **`Wear/Tear` do Grinding Station** (0 → 1), pela via
  (b). E **zero linhas saíram da lista de compras**: ele não estava a ser mandado
  comprar nada que tivesse.
- **O QUE ESTAVA MESMO AVARIADO ERA O PREÇO, O TIPO E A IMAGEM.** O
  `loadout.card_price` devolvia `(None, None)` a **toda** a carta de dupla face.
  Medido: nomes de lista sem preço **843 → 661** (+182 com preço); as cópias sem
  preço da lista de compras **21 → 18**; e **3 linhas** passaram de 0,00 € a ter
  preço — Agadeem's Awakening 33,56 €, Jennifer Walters 15,21 €, Razorgrass
  Ambush 0,45 € —, o que explica ao cêntimo o *fechar tudo* **5 895,14 € →
  5 974,04 € (+78,90 €)**.
- **A REGRA TEM QUATRO RAMOS E A ORDEM DELES É SEGURANÇA, não estética.** O nome
  TAL E QUAL vem primeiro porque há cartas a sério com barras no nome que **não**
  são separador: **`SP//dr, Piloted by Peni`** e **`Summon: Choco/Mog`**.
  Canonizar às cegas partia-as em faces que não existem. Verificado no catálogo
  inteiro: **zero** nomes reais cuja canonização seja outro nome real, e as duas
  armadilhas canonizam para algo inexistente. O teste tranca a ordem com um par
  SINTÉTICO (e dito que é sintético), senão a regra não era falsificável.
- **O `MapaDeCartas` é o que torna «uma função só» verdade do lado dos
  dicionários.** A posse, os tipos, as cores e as imagens são mapas
  `nome -> coisa` e há **mais de vinte sítios** a fazer `mapa.get(nm)` com o nome
  que a LISTA deu. Pedir a cada um que se lembrasse de canonizar era deixar o
  primeiro que se esquecesse a responder *"não tenho"*. A regra vive no próprio
  mapa. **E 25 `.split(" // ")[0]` escritos à mão passaram ao `scryfall.chave`**;
  ficam **exactamente três**, e são `type_line` (`Instant // Land` → `Instant`),
  que não é um nome de carta — o teste exige esse número e chumba se subir.
- **O PREDICADO É UM INTERVALO DE PREFIXO E NUNCA UM `LIKE`.** `EXPLAIN QUERY
  PLAN` dá `MULTI-INDEX OR` com os quatro ramos em `SEARCH cards USING INDEX
  ix_cards_name`; medido nos 4 721 nomes reais, **0,0077 → 0,0097 ms** por nome.
  O `LIKE ? || ' // %'` dá `SCAN cards` — e **estava escrito no `collection`, no
  `marcas`, no `paginas`, no `import_owned`, no `revalidacao` e no `padrao`**, por
  isso esta correcção torna esses seis mais RÁPIDOS.
- **QUANDO É QUE O PREDICADO NÃO SE USA — e custou 135 s a descobrir.** Serve a
  consulta em que a `cards` é a tabela que MANDA. Quando o nome está do lado
  LONGE de um JOIN com uma tabela grande, o `MULTI-INDEX OR` tira à `cards` o
  papel de condutor e o SQLite varre a outra. Mordeu em **três** sítios, os três
  medidos e corrigidos com o `resolver()` antes da consulta: o
  `loadout._historico` (0,1 → **21,7 ms**, e o `report` de 0,7 → **12,9 s**), o
  `wantlist.cheapest_price` e — o pior — o `meta_coverage._visual`, que pôs a
  `meta_coverage.build` em **0,3 s → 135,8 s** (227 chamadas a 0,59 s). **A regra
  está escrita no `scryfall.sql_nome`: se o `EXPLAIN QUERY PLAN` deixar de dizer
  `SEARCH … USING INDEX ix_cards_name`, usa o `resolver()`.** Há um auditor
  (`_revisao/auditar_planos.py`) que mede as onze consultas que levam o predicado
  e chumba acima de 60 ms.
- **UMA CARTA DESCONHECIDA É UM PROBLEMA À VISTA, NUNCA UM «NÃO TENHO».** A carta
  leva chip `?` no tile, a linha *«DESCONHECIDA — o catálogo não tem esta carta»*
  e um chip no cabeçalho do deck (`conta.desconhecidas`). **Conta no total** (o
  deck pede-a) e **nunca em `tem`**: sem o número à parte, o *«faltam-te N»*
  misturava compras a sério com nomes que não existem.
  **E HOJE NÃO MARCA NADA NO SITE, o que é melhor dizer do que deixar
  descobrir.** A única desconhecida nos decks dele é a `Ademi of the Silkchutes`,
  e ela vive na linha **`decks[4]` da tabela `decks`** («Cloud (Duel
  Commander)»); a aba Decks desenha a **CAIXA** com esse nome, cuja lista vem do
  `listas_escolhidas` (a do Liwei Luo, fixada a 04/10) e **não** tem a carta.
  Medido: **0 de 393** nomes das caixas são desconhecidos. Onde ele as vê hoje é
  no CLI — `py -m mtgvault.cli cartas-desconhecidas` —, com o deck ou o número de
  linhas ao lado: **1 de 298** em `deck_cards` e **26 de 4 721** nas listas do
  metagame (248 linhas). A marca fica para o dia em que uma entre numa lista que
  a página desenhe, e tem caso de teste a provar que entra.
- **MEDIDO LADO A LADO, o MESMO `vault.db` dos dois lados** (worktree em
  `_revisao/main-nomes`): **as 17 caixas ficam IGUAIS à percentagem e à cópia**, a
  **venda não mexe uma cópia** (116 c / 1 591,62 €, `protegidas` 157,
  `rl_sem_historico` 103, `guardar` 1), o **valor da colecção não mexe**
  (133 354,51 €, 1 678 cartas, 390 sem preço — essa conta é por `scryfall_id`) e
  **a comprar continua em 245**. Mexem só os três números de cima. O `tens X de
  Y` dos 13 decks da tabela `decks` é igual em doze e **59 → 60** no Grinding
  Station.
- **TEMPOS, e nenhuma página ficou mais lenta.** `loadout.report` **700 → 719 ms**
  (+2,7 %: são os 47 `resolver` do histórico e os quatro ramos do `card_price`),
  `valor_da_coleccao` 241 → 244 ms, `meta_coverage.build` 0,3 s nos dois lados. As
  **14 páginas e os 246 ficheiros de dados respondem 200**, zero erros; as duas
  que o webapp CALCULA ficaram mais rápidas a frio (`arrumacao.json` 4 194 →
  **1 031 ms**, `deckboxes.json` 4 071 → **894 ms**). Os 31 ficheiros que a
  primeira passagem deu como «mais lentos» são **ruído de I/O** e está provado:
  numa segunda corrida do MESMO código só 6 aparecem e **1** nas duas, e a soma
  dos estáticos cai 7 369 → 5 448 → 3 036 ms à medida que a cache do SO aquece.
- **O `vigia.achados` VARRE a `decklist_cards` (274 720 linhas) e isso é anterior
  a esta ordem** — compara em `lower()`, que não entra em índice nenhum. Os dois
  ramos a mais punham-no de 51 em 110 ms, por isso **os ramos do canonizado só
  entram se o nome tiver barra**: nenhuma carta vigiada tem, logo o caminho normal
  ficou exactamente como estava (48–50 ms).
- **O `wantlist.cheapest_price` custa 200 ms com QUALQUER nome, e não fui eu.**
  Medido com `c.name = ?` simples: o SQLite conduz pela `price_latest` filtrada
  só pelo `source`. É pré-existente e **não se tocou** (está fora do âmbito desta
  ordem); fica dito para quem lá chegar.
- **UMA SOBREPOSIÇÃO COM O `main`, resolvida a favor do `main`.** Enquanto isto
  corria, o commit `5de6032` tirou a prosa do config do payload com uma função
  própria (`loadout._sem_prosa`) — eu tinha escrito o mesmo corte à mão. **Ficou o
  dele**: tem nome, tem testes (`test_decisoes_1004_fecho`) e já estava publicado.

**UM FURO NA CADEIA DE PREÇOS, APURADO E NÃO EMENDADO (2026-10-04).**
**[FECHADO ao fim do mesmo dia — ver a secção de cima. O que segue é o
apuramento que levou lá, e fica porque os números dele continuam a valer.]** O
`loadout.card_price` procurava `WHERE c.name = ?` — um casamento EXACTO — e o
catálogo guarda as cartas de dupla face como **`"frente // verso"`**, enquanto as
decklists guardam só a frente (`_front`). Logo **toda a carta de dupla face numa
lista não tinha preço em todo o vault**, e a cadeia TEM o preço: medido na base
dele, dos **4 721** nomes distintos que aparecem em listas, **185 são de dupla
face e os 185 estavam sem preço** — Bonecrusher Giant, Brazen Borrower, as
Pathway, Agadeem's Awakening, Birgi… — e perguntados pelo nome COMPLETO somam
**741,88 €** numa cópia de cada. A correcção certa era o INTERVALO
DE PREFIXO de 2026-10-01 (`scryfall.frente_de_dupla_face`/`limites_dupla_face`,
que já existia) e **nunca um `LIKE ? || ' // %'`** — esse é o `SCAN cards` que deu
o 502 no telemóvel, e o `card_price` é chamado milhares de vezes por relatório.
**As três cartas que ele nomeou têm TRÊS causas diferentes**, e vale a pena não
as confundir: **Razorgrass Ambush** e **Witch Enchanter** são `X // Y` do MH3 —
é este furo, e o CardTrader cota-as (0,45 € e 5,90 € nonfoil); **Shining Shoal**
não tem uma única linha de preço em sítio nenhum (a sua única impressão é `bok`,
de 2005, fora das 173 edições que a recolha do CardTrader cobre, e o price guide
também nunca a teve); e **Kíli the Resourceful**, **Mistveil Plains** e **Surge
of Salvation** têm preço só do `cardmarket` e a cadeia é `cardtrader` desde
04/10 — essas são a **régua**, não um defeito.

Alteração de 2026-10-04 ao fim do dia (nos dois sítios — `schema.sql` e
`db._migrate()`): o CHECK da **`watched`** passou a aceitar
**`mtgtop8_archetype`**, e isso obrigou à **PRIMEIRA RECONSTRUÇÃO DE TABELA**
deste ficheiro — um CHECK não se altera com `ALTER TABLE`. Duas armadilhas, as
duas medidas: as FK estão **ligadas** (`connect` faz `PRAGMA foreign_keys = ON`)
e a `watched_snapshots` tem **ON DELETE CASCADE**, por isso um `DROP TABLE
watched` apagava o histórico das listas vigiadas; e o `PRAGMA` é um **no-op
dentro de uma transacção**, por isso há um `commit` antes. A contagem confere-se
antes e depois e **levanta** se perder uma linha, e o `foreign_key_check` corre
no fim. O kind antigo `archetype` **fica** no CHECK (nada se apaga) mas não tem
verificador — quem o denuncia é o `watchlist.check_all`, que passou a falhar
alto. Ver «O SIDEBOARD APLICADO, A RESERVA A 20 % E A VIGIA DO ARQUÉTIPO».

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
  default `true`) — **língua, edição E acabamento**: a pilha dele é toda Unhinged
  EN, e trancar o Premodern ao PT mandava comprar 17 Island que estão ali ao
  lado. Nas caixas de foil a foil vai à frente (`_ordem_basica`), mas é
  **preferência e não requisito** — uma Island non-foil fecha o slot na mesma, e
  desde 2026-10-02 uma Island **foil** fecha o slot de uma caixa de Premodern,
  que passou a `acabamento: "nonfoil"`. O `requisito_basicas` diz *"se houver"*
  por isso mesmo — ver a secção das regras de material de 02/10. O que NÃO é material continua a valer: cópia
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

**O TELEMÓVEL E O TOKEN (2026-09-08; o QR saiu a 2026-10-01).** *"Ele vai estar à
frente da estante com o telemóvel."* O `webapp.py` ouve em `MTGVAULT_BIND` (por
omissão `127.0.0.1`; a tarefa `mtgvault-serve` põe `0.0.0.0`). **Ler é livre;
escrever exige o token** (`data/webapp.token`, gerado uma vez, fora do Git): sem
ele, `403`. E a página só leva o token dentro dela quando o pedido que a foi
buscar já o trazia — senão bastava abri-la de qualquer telemóvel da rede para o
descobrir. Pedidos de `127.0.0.1` são de confiança sem token (quem está no PC já
tem os ficheiros). **O painel do QR e a rota `/qr.svg` deixaram de existir** —
ver «FORA O QR DA PORTA DA FRENTE», a seguir.
O `test_qr.py` continua a verificar o desenhador (`mtgvault/qr.py`, Python puro,
modo byte, nível M, versões 1–10) de três maneiras — lê-se a si próprio, é igual
ao da biblioteca de referência nas oito máscaras, e a estrutura está lá. **O
módulo ficou e já não é chamado por ninguém**: apagá-lo é decisão dele, e o
teste é barato.
**A firewall do Windows pode estar a tapar o 8771** — uma vez, em consola de
Administrador: `netsh advfirewall firewall add rule name="mtgvault 8771" dir=in
action=allow protocol=TCP localport=8771 profile=private` (só rede privada; o
comando também é impresso no arranque do `webapp.py`).

**FORA O QR DA PORTA DA FRENTE (André, 2026-10-01, à letra).** *"não quero QR
Codes, quero editar logo e pronto"*. Saíram: o painel da aba *Plano*
(`deckboxes.ligacaoHTML`, um QR de 150 px + *«sem ele a página é só de
leitura»*), a chave `ligacao` do payload, o CSS `.lig`, a rota **`/qr.svg`** e o
QR em ASCII do arranque na consola.

- **A razão não é estética, é que o painel dizia o contrário do que se passava.**
  Ele só se desenhava com `D.editable` verdadeiro — ou seja, **só aparecia a quem
  JÁ podia escrever** — e a frase que lhe passava era *«sem ele a página é só de
  leitura»*. Quem entra por `https://editar-mtg.baverone.com/` já passou pelo
  Cloudflare Access e já está autenticado; mandá-lo apontar a câmara a um QR para
  obter uma permissão que ele tem é atrito a fingir que é segurança.
- **A rota foi atrás do painel** porque era o seu único consumidor, e servia um
  URL com o token lá dentro. O `mtgvault/qr.py` fica (é só o desenhador, em
  Python puro, com teste próprio); o que deixou de existir é a porta HTTP.
- **O MODELO DE AUTORIZAÇÃO NÃO SE TOCOU, e isso foi uma decisão.**
  `_pode_escrever()` continua a ser *«loopback é de confiança; da rede exige-se o
  token»*. **Não se passou a confiar nos cabeçalhos do Access**
  (`Cf-Access-Authenticated-User-Email`, `Cf-Access-Jwt-Assertion`): com o
  `MTGVAULT_BIND` em `0.0.0.0`, qualquer máquina da rede de casa os pode
  **inventar** num pedido directo ao 8771, e aí o cabeçalho não prova nada. Fazê-
  lo em condições é validar o JWT contra as chaves públicas do Access, e **isso
  precisa de uma dependência que este PC não tem** — não há `PyJWT`, `cryptography`,
  `pyOpenSSL` nem `pycryptodome` instalados, e escrever à mão a verificação RSA
  de uma fechadura de ESCRITA é exactamente o atalho que não se dá.
  O que ficou apurado, para quem pegue nisto (sondado a 2026-10-01):
  team domain **`spring-cake-2060.cloudflareaccess.com`**, JWKS em
  `/cdn-cgi/access/certs` (200, RS256, duas chaves), e o **AUD** da aplicação é o
  `kid=` do redireccionamento de login,
  `b045551a6b5d8b08fef75c6f1d4cc401ce0cfac1f5bc8387882f6601d6d88a75`. Com
  `pip install "PyJWT[crypto]"` é meia hora de trabalho — validar assinatura,
  `iss`, `aud` e `exp`, e **só então** dar escrita.
- **E é provável que não seja preciso nada disso.** O `cloudflared` corre NESTE
  PC; se o túnel aponta para `http://localhost:8771` (a configuração normal), os
  pedidos dele chegam como `127.0.0.1` e **já** são de confiança — era o que o
  próprio painel provava, porque só se desenha em modo edição e foi isso que ele
  viu no telemóvel. **Não se conseguiu confirmar daqui**: o túnel é gerido
  remotamente (em `C:\ProgramData\cloudflared` só está o `token`, não há regras
  de ingress em disco) e o Access responde `403`/`1010` a um pedido automático,
  por isso não há como fazer um pedido autenticado a partir do PC. Se ele abrir o
  modo de edição e os botões **não** aparecerem, a correcção certa é apontar o
  ingress para `localhost` no painel da Cloudflare — não é código, e é mais
  seguro do que confiar num cabeçalho.

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
letra).** **[O TECTO DE PLAYSET FOI-SE a 2026-10-02 — ordem
dele: *«esquece a regra do máximo um playset em Premodern: já não vale»*. O
`loadout.playset_maximo` devolve sempre `None`, a chave saiu do config, e o
`fases.de_conversao` passou a derivar-se do `prioridade_por: "pct"`. O que segue
fica como histórico; medido: +44 cópias e +366,75 € na lista de compras.]** **[SUPERSEDED 19/09/2026 na PARTILHA: as caixas de Premodern voltaram a
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
  40 · tech 39, **igual antes e depois da mudança**. **Desde 2026-10-01** há uma
  PÁGINA para este formato — o `comandantes.html`, o consenso por COMANDANTE — e
  ela também não lê os `archetypes`: lê o `decklists.commander`, que é a razão de
  ser dela (ver «O CONSENSO É POR COMANDANTE»).
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
