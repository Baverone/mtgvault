# Catalogar cartas a partir de fotos (guia para o Claude)

Este guia é para **qualquer Claude** (incluindo o claude.ai/code aberto no
telemóvel, apontado a `Baverone/mtgvault`) catalogar cartas das fotos, mesmo
sem o André estar ao PC.

## Fluxo

1. O André larga fotos novas na pasta **`pendentes/`** (app do GitHub no
   telemóvel, ou no PC).
2. **Tu (Claude) olhas para cada foto de `pendentes/`**, reconheces as cartas e
   escreves um **CSV** (formato abaixo). Guarda-o, ex.: `pendentes/recat.csv`.
3. Corres:
   ```bash
   py processar_fotos.py pendentes/recat.csv
   ```
   O script garante o catálogo, importa para `data/vault.db`, **arruma as
   fotos** para **`Decks Processados/<deck>/<carta (N)>/`** — a MESMA pasta de
   onde ele as largou em `Decks Por Processar/`, cuja pasta da carta se APAGA
   quando a foto entra; uma foto sem pasta de origem vai para
   `Decks Processados/<deck do alvo>/` (sem alvo, `sem-alvo/<AAAA-MM>/`) — e
   **nunca as apaga**. Depois publica a BD. O site atualiza-se sozinho.
   (As duas árvores são de 2026-10-13; até aí o destino era `data/fotos/<slot>/`
   e, antes de 2026-10-01, `pendentes/fotos processadas/<AAAA-MM>/`.)

   Ao lado do teu CSV fica um `<nome>-resultado.csv` com o que aconteceu a cada
   linha. **As linhas que pararam vêm lá com o motivo** — a foto delas fica em
   `pendentes/` à espera de ser recatalogada (ou, se veio de uma pasta de
   carta, VOLTA a essa pasta com o mesmo nome e um `_porque_parou.txt`).

O reconhecimento (passo 2) és sempre **tu a olhar para as fotos** — o script só
faz a parte mecânica.

**A subpasta `pendentes/deckboxes/` NÃO é tua** (2026-09-21): são fotos das
DECKBOXES físicas (as caixas de plástico, uma por `slot`), que o `daily` e o
modo edição recolhem sozinhos (`mtgvault/fotocaixa.py`). Não as cataloguas,
não as metes no CSV, não as moves. Só as fotos na **raiz** de `pendentes/`
são cartas.

**As fotos `site-…` vieram do TELEMÓVEL, pela própria Deckboxes** (2026-09-21,
André: *"tirar as fotos directamente do site"*). O nome diz de onde:
`site-<slot>-<AAAAMMDD-HHMMSS>-<n>.jpg` é a CAIXA `<slot>` que ele estava a
fotografar (`site-duel-commander-…`, `site-modern-…`); `site-venda-…`,
`site-rl-…` e `site-colecao-…` são a lista de venda, a Caixa Reserved List e o
resto da Colecção; e `…-c<copy_id>.jpg` diz a CÓPIA esperada nessa foto (o
André carregou no 📷 dessa carta). **Desde 2026-10-01 um nome `site-<slot>-…`
pode também vir da PASTA DO DECK** — ele larga as fotos em `Decks Por
Processar/<nome do deck>/<carta (N)>/` (até 13/10 a pasta chamava-se «Colocar
fotos da coleção aqui») e o `mtgvault.fotos.recolher_das_pastas` move-as
para a raiz de `pendentes/` com este mesmo nome, de propósito: para ti e para o
import são a mesma coisa, e por isso não há nada de diferente a fazer com elas.
**E desde 2026-10-02 um `site-colecao-…` pode vir da pasta `Decks Por
Processar/Extras (fora dos decks)/`** — é a pasta do que NÃO está em deck
nenhum (repetidas, cartas soltas, o que sobra das caixas), e o alvo dela é o
resto da Colecção: nada do que vier de lá fica alocado a um deck.
**É uma pista, não uma resposta**: escreve o
que VÊS na foto, como sempre, com o `photo_path` — o import prefere as cópias
dessa caixa (e essa cópia) ao ligar a foto, e trata uma edição/acabamento
diferente como correcção da cópia. O `esperadas.md` lista estas fotos com a
caixa e a cópia por extenso (secção «Fotos tiradas no site»).

**Se existir `pendentes/esperadas.md`, lê-o antes de escrever o CSV.** Tem
até quatro secções:

1. **«<Caixa> — por revalidar»** (desde 2026-09-20 — a REVALIDAÇÃO POR FOTO):
   o André está a fotografar de novo TODA a colecção, caixa a caixa, e a
   secção diz que cópias ele está a fotografar agora (impressão esperada e
   quantidade, com o `copy_id`). Uma foto destas **liga-se à cópia que já
   existe** — não cria outra. **Escreve a impressão que VÊS na foto** (edição,
   número, língua, acabamento), não a esperada; se for diferente do esperado,
   escreve o que vês na mesma e diz em `notes` o que esperavas (ex.:
   «esperava NEM nonfoil, é foil») — o import trata isso como uma correcção
   da cópia da caixa. A `quantity` é o que está NA FOTO.
1b. **«Fotos tiradas no site»** (desde 2026-09-21): cada foto `site-…` que está
   em `pendentes/`, com a caixa que o nome indica e, quando há `-c<copy_id>`,
   a cópia esperada (nome e impressão). Mesma regra: escreve o que vês.
2. **«Encomendas pendentes»**: o que o André disse que comprou / que já tem e
   ainda não fotografou («pendente de foto»), por caixa, com a língua e o
   acabamento esperados. Desde 2026-09-19 **só a foto cria cópias**: uma foto
   de uma carta pendente **fecha a encomenda e mete a cópia na caixa** a que
   ela pertencia. Para isso a linha do CSV tem de trazer a **mesma língua e
   acabamento** da encomenda (e a mesma edição, se a encomenda a fixar). Se a
   foto mostrar outra coisa (uma edição posterior ao Scourge para uma caixa de
   Premodern, por exemplo), escreve o que vês na mesma — a cópia entra na
   Colecção sem caixa e a encomenda fica aberta com um aviso; o que não se faz
   é inventar a edição para bater com a lista.
3. **«Na base, sem foto»**: cópias que já existem na base sem foto — uma foto
   de uma destas **liga-se a essa cópia** (não cria outra).

Em todos os casos a regra é a mesma: **escreve o que a foto MOSTRA**, com o
`photo_path`. Quem decide a que cópia a linha se liga é o import, pela ordem
que está no `CLAUDE.md` (revalidação → edição por confirmar → encomenda →
cópia sem foto → entrada normal).

## Formato do CSV

Cabeçalho (esta ordem de colunas):

```
name,set_code,collector_number,quantity,finish,language,condition,purpose,sub_collection,photo_path,acquired_price,notes,condition_notes,verso_path,verso_ok
```

- **name** — nome REAL da carta impressa. Se for um *reskin* (ex.: cartas de
  Universes Beyond com nome de personagem), usa o nome real da carta de Magic.
  Cartas de dupla-face: o nome completo `Frente // Verso`.
- **set_code** — código do set (ex.: `mh3`, `fin`). Podes pôr como aparece — o
  script baixa para minúsculas. **Obrigatório: uma linha sem `set_code` NÃO
  entra** — para com `motivo: edicao em falta` e a foto fica em `pendentes/`.
  Até 2026-09-08 uma edição em branco não dava erro: dava a impressão *mais
  antiga* da carta, que para as básicas é sempre Alpha (foi assim que 5 Plains
  do Cloud cEDH ficaram `lea #287`, 309,50 € de valor fantasma). Se não
  conseguires ler a edição, confirma-a no catálogo (`catalogo.py "<nome>"`) ou
  deixa a linha de fora e escreve a dúvida em `notes` — mais vale uma carta por
  catalogar do que uma carta catalogada errada.
- **collector_number** — número da carta (canto inferior). Deixa como está (ex.:
  The List = `UGL-84`). Vazio se não der para ler.
- **quantity** — quantas cópias iguais (mesma edição/finish/língua) nessa foto.
- **finish** — `nonfoil` (por omissão) ou `foil`.
- **language** — `en` (por omissão) ou `pt` (se a carta estiver em português).
- **condition** — o ESTADO, na escala do **Cardmarket**: `MT` `NM` `EX` `GD`
  `LP` `PL` `PO`. **Só o preenches se tiveres visto o VERSO** (ver a secção «O
  estado e os versos», abaixo). Sem verso deixa-o VAZIO: o estado fica «por
  verificar» e não se inventa. Um `condition` escrito sem verso confirmado **não
  é aplicado** — fica registado como proposta recusada, com o motivo.
- **condition_notes** — os MOTIVOS do escalão, **um sub-juízo por critério, com
  a ZONA** (desde 2026-10-13, vocabulário fixo): `cantos: … | bordas: … |
  superfície: …` — «cantos: inferior esquerdo com ponta branca | bordas: branco
  na de cima | superfície: limpa, sem vincos». A **centragem não conta** (é
  fabrico, não desgaste). Um escalão sem motivos não se confere nem se corrige,
  e é esta linha que ensina quando o André o corrige.
- **verso_ok** — `sim` quando **viste o verso** na foto `…-v.<ext>` desta frente.
  É a CONFERÊNCIA do emparelhamento: o `-v` do nome é só a hipótese. Sem este
  `sim` não se grava escalão nenhum.
- **verso_path** — opcional. O import deduz o nome do verso da frente (o mesmo
  nome com `-v`) e procura-o no disco; só o escreves se quiseres dizê-lo à letra.
- **purpose** — `player` (por omissão) ou `collector` (se for de coleção, não
  para jogar — essas nunca contam para decks).
- **sub_collection** — a GAVETA onde a carta fica. Desde o modelo de colecção
  única (2026-09-07; a base migrou nesse dia) há só duas: **`Colecção`** (tudo o
  que joga) e **`Caixa Reserved List`** (só o que o André disser que é da caixa
  RL). Os nomes antigos (`SPML`, `Premodern (geral)`, `Blue Farm`, `Cloud`,
  `Cloud cEDH`, `Pauper Affinity`) continuam a aceitar-se — o `add_copy` mete a
  cópia na `Colecção` e guarda esse nome em `balde_origem` (é o que a migração
  fazia), por isso se a foto disser claramente de que deck é, podes escrevê-lo.
  Onde a carta está DENTRO de uma deckbox é a alocação (`copy_allocation`), não
  este campo. Em dúvida, `Colecção`.
- **photo_path** — o nome do ficheiro da foto. **Põe-no sempre**: é o que liga
  a cópia à foto que lhe deu origem (a foto é arrumada, nunca apagada, e o
  caminho novo fica na cópia). Sem ele, uma suspeita de edição errada não tem
  como ser relida.
- **acquired_price** — opcional (€).
- **notes** — dúvidas ("edição a confirmar"), etc.

## Regras que não podem partir

- **UMA PASTA DE CARTA VAZIA ALTERA-SE; COM UMA IMAGEM, NADA LHE TOCA** (André,
  2026-10-16, à letra: *"como ainda nao fotografei nada, altera as pastas que
  tens que alterar"*). Enquanto uma pasta `<carta (N)>` em `Decks Por
  Processar\` estiver vazia, o vault apaga-a, renomeia-a ou move-a sem pedir e
  sem corredor de espera: é um pedido de foto, regenerável pela base. **No
  momento em que tem uma imagem dentro, não se apaga, não se move e não se
  renomeia** — é a metade da regra de 09/09 que continua inteira. Quem apaga é
  só o `fotos.apagar_pasta_feita`, que recusa uma pasta com imagens.
- **Não inventes.** Se não consegues ler uma carta ou a edição, deixa o campo
  vazio e regista em `notes`; não adivinhes uma edição ao calhar.
- **set_code em minúsculas** (o script trata disto, mas se editares à mão, mete
  minúsculas). **collector_number NÃO se baixa** (mantém como impresso).
- **Terras básicas** contam à mesma (quantidade certa).
- Uma foto pode ter várias cartas — uma linha por carta distinta
  (nome+edição+finish+língua), com a `quantity` das repetidas.
- **ATÉ 4 CARTAS POR FOTO** (André, 2026-10-01: *"organiza o Blue farm e CDEH
  por tipo de carta e ate 4 cartas por foto"*, *"se sao 4 fotos, e 1 foto com as
  4 cartas"*). Com a campanha de revalidação ligada, uma foto com **mais de 4
  cartas não valida nada**: se já existe na base uma cópia por revalidar daquela
  impressão, a linha é **recusada** com o motivo em português e a foto fica em
  `pendentes/` para ser tirada outra vez em grupos de quatro. Isto é sobre o
  número de **cartas** (um `4× Mox Opal` são quatro), não sobre o número de
  linhas. **Não somes cartas a mais numa linha para «caber»**: escreve o que
  vês — se a foto tem seis cartas, a resposta certa é dizer que tem seis.
- **O `(N)` DA PASTA É O QUE O DECK PEDE; A `quantity` É A DA FOTO** (André,
  2026-10-13, à letra):
  > *"vou sempre fotografar as cartas até ao playset / caso peça apenas 2x e eu
  > tenho playset, eu vou fotografar playset / caso peça playset e eu so
  > fotografar 2x, é porque só tenho 2x / caso vários decks peçam a mesma
  > carta, e eu coloque em diferentes pastas a mesma carta, é porque tenho
  > multiplos da carta"*

  É a «foto manda» de 02/10 estendida à QUANTIDADE. Na prática, para ti:
  1. pasta `Mox Opal (2)` e foto com **4** → escreves `quantity = 4`. Não é um
     erro, não se recusa, e não «corriges» para 2: entram quatro cópias, o deck
     leva as duas que pede e as outras duas ficam cópias sem deck (excedente,
     que passa pela regra guardar/vender como qualquer outra — a venda está
     congelada);
  2. pasta `Mox Opal (4)` e foto com **2** → `quantity = 2`. O deck fica a
     dever 2, e nada presume as outras duas. Nunca é motivo para deixar a linha
     de fora nem para deixar a foto em `pendentes/`;
  3. a **mesma carta em pastas de decks diferentes** são cópias DIFERENTES:
     uma linha por foto, cada uma com o seu `photo_path`. Nunca as juntes numa
     linha só nem escrevas o `photo_path` de uma na outra — o import cria uma
     cópia por foto, e é a foto (o nome dela) que impede que a mesma prova
     conte duas vezes;
  4. **até ao playset**: ele nunca põe mais de 4 da mesma carta na mesma pasta,
     por isso uma pasta de carta cabe sempre numa foto de até 4 cartas (os
     terrenos básicos continuam isentos do tecto).

  A pasta da carta em `Decks Por Processar/` apaga-se quando a foto **entra**,
  não quando a quantidade bate com o `(N)`; e só volta quando a carta deixar de
  ter foto nenhuma naquele deck (uma correcção).

## O estado e os versos (André, 2026-10-03)

> **SUSPENSO A 2026-10-20 — vale isto e não o resto da secção.** As palavras
> dele: *«vamos esquecer o estado então, vou só tirar fotos de frentes, para já
> é inconcebível fazer tudo isso»*. Enquanto `estado_cartas.adiado` estiver a
> `true` no `colecao_config.json`: **não escrevas `condition` nem
> `condition_notes`** (ficam vazios — «por verificar» — em todas as linhas; o
> import ignora um escalão que venha); as fotos são **frentes** e a recolha já
> não põe `-v` por ordem de captura. Um `-v` só existe se o NOME original o
> trouxer: aí é o verso da frente com o mesmo nome e não leva linhas (se vires
> cartas nele, escreve-as como numa frente). Não há lista curta de versos.
> O método abaixo fica guardado, dormente — **suspenso, não revogado**.

As palavras dele: *«verso as dos decks e as que são para guardar, para já»* e
*«procuras como são avaliadas as cartas, depois com base nas minhas próprias
fotos, vais melhorando o teu critério»*.

**Lê primeiro `data/estado-criterio.md`.** Tem as definições dos sete escalões
transcritas **da fonte** (<https://help.cardmarket.com/en/CardCondition>), o
**método** de 2026-10-13 — três critérios (**cantos, bordas, superfície**; a
centragem fica de fora), os limiares, o tapete preto como requisito, e as duas
verificações próprias da colecção dele (clouding nos foils da era Urza's/7.ª e
linhas de rolo nas duais de Revised) — e a secção **«Aprendido com o André»**, que cresce com as correcções
dele. O `pendentes/esperadas.md` traz-te esse texto à frente, já com os **erros
repetidos meus** e as **últimas correcções dele** — lê-os antes de julgar.

### O verso não identifica a carta

**Todos os versos de Magic são iguais.** O verso serve para ver o **desgaste** —
branqueamento das bordas e dos cantos visto do outro lado, vincos, manchas,
danos de água. É de lá que sai o escalão.

### Como reconheces um verso

Uma foto `…-v.<ext>` é **o verso da foto com o mesmo nome sem o `-v`**:

```
site-cedh-blue-farm-20261003-101500-3.jpg       <- a FRENTE
site-cedh-blue-farm-20261003-101500-3-v.jpg     <- o VERSO dela
```

O par é **o mesmo radical** e mais nada. Quem lhe pôs o `-v` foi o botão «frente
e verso» da página (que recebe as duas de uma vez) ou a recolha da pasta do deck
(que emparelha pela ordem de captura, que é o gesto físico: põe, fotografa,
vira no sítio, fotografa). **O nome é uma hipótese; tu és a conferência.**

### O que escreves

- **vês um verso na foto `-v`** → escreve `verso_ok = sim`, o `condition` e o
  `condition_notes` **nas linhas da FRENTE**. A foto do verso não leva linhas
  próprias: ela não tem cartas para identificar;
- **vês CARTAS numa foto `-v`** → o emparelhamento não bateu (ele largou um
  número ímpar, ou saltou um verso). Escreve as cartas normalmente, com o
  `photo_path` dessa foto, e **deixa o `condition` vazio**. As cartas ganham
  sempre ao nome do ficheiro: perder uma carta por causa de um sufixo era o pior
  resultado possível;
- **não há foto `-v`** (é o caso dos Extras, onde ele fotografa só a frente) →
  `condition` vazio. O estado fica «por verificar», e o vault dá-lhe depois uma
  **lista curta** das que precisam de verso (Reserved List, duais, shocklands,
  fetchlands) para ele voltar lá uma vez;
- **não consegues decidir** → di-lo no `condition_notes` («não consigo ver as
  bordas: flash de frente») em vez de escolheres um escalão a adivinhar.

### O que se consegue ver numa foto de telemóvel

- **vê-se:** vincos, branqueamento de bordas e cantos, riscos visíveis, desgaste
  de jogo, sujidade → dá para um escalão defensável entre **NM, EX, GD e LP**;
- **não se vê:** a diferença entre **NM e Mint** (por isso o `MT` não se atribui
  por foto), e riscos finos de superfície;
- **a luz pesa mais do que a resolução:** o flash de frente *esconde* o desgaste
  das bordas; luz difusa num ângulo ligeiro *mostra-o*. Se a foto estiver com
  flash de frente, di-lo nos motivos.

O escalão é **sempre uma estimativa com motivo escrito**, nunca uma classificação
certificada. **E a correcção do André ganha sempre:** uma cópia que ele corrigiu à
mão não volta a ser mudada por uma avaliação tua posterior.

Contexto do projeto: ver `CLAUDE.md`. Regras da coleção/decks: idem.
