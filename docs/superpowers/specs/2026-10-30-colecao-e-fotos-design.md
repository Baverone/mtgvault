# Site do MTG: Coleção e fotos (desenho)

30/10/2026. Combinado com o André na conversa de 29–30/10. Continua o núcleo
(`2026-10-28-site-mtg-nucleo-design.md`): as regras de lá valem aqui, e onde
este desenho diz outra coisa, ganha este.

## Para que serve

Duas coisas novas:

1. **Coleção.** Cartas que ele guarda para acompanhar o preço, e não para
   jogar: o que tem, o que falta, quanto vale e como evolui; o que anda a subir
   e pode valer a pena juntar; o que marcou para vender.
2. **Fotos.** Ele marca no site (+1 / −1) e as fotos dão a prova: uma cópia é
   **por validar** até uma foto a confirmar, e uma carta validada mostra no site
   a foto **da cópia dele** em vez da imagem da Scryfall. Vale para os decks e
   para as coleções.

## As coleções

| Coleção | Tipo | Cartas | Edição · língua · acabamento | Meta |
|---|---|---|---|---|
| Duals de Revised | fechada | as 10 duals | Revised (`3ed`) · inglês · normal | 4 de cada |
| Zendikar Expeditions | fechada | as 10 shocks e as 10 fetches | `zne` · inglês · foil | 4 de cada |
| Shocks originais em português | fechada | as 10 shocks | Ravnica (`rav`: Watery Grave, Temple Garden, Sacred Foundry, Overgrown Tomb), Guildpact (`gpt`: Stomping Ground, Steam Vents, Godless Shrine), Dissension (`dis`: Hallowed Fountain, Breeding Pool, Blood Crypt) · português · normal | 4 de cada |
| Reserved List | aberta | as que ele juntar | a que ele escolher | sem meta |

- **Fechada:** lista fixa de cartas, cada uma com meta (4 por omissão, muda-se
  carta a carta no modo de edição). Mostra «tenho X de Y» e quanto falta em €.
- **Aberta:** sem meta nem faltas; é o que ele juntar («juntar carta»: procura
  pelo nome, escolhe edição e acabamento).
- Nas Duals contam só as de Revised; as Foreign Black Border **não** contam.
- As coleções **não** entram no progresso nem nas faltas dos decks, mas entram
  no **valor** do Painel.

## O que se vê

**Menu:** Painel · Decks · **Coleção** · Vender.

**`colecoes.html`** (uma página só, como o `deck.html`; sem `#` mostra os botões). O nome não é `colecao.html` porque esse ficheiro é a Galeria do site antigo, ainda ligada à publicação dele:

- Um botão grande por coleção, com a arte de uma carta: nome, «tenho X de Y»
  (aberta: «N cartas»), valor de hoje e variação a 30 e a 90 dias.
- **Dentro de uma coleção** (`colecoes.html#<slug>`): valor, gráfico
  (1 mês · 3 meses · tudo), progresso e quanto falta (fechadas); as cartas em
  imagem, a cores as que tem e a cinzento as que faltam, cada uma com o nome,
  «tenho / meta», preço, variação a 30 e a 90 dias, a etiqueta **«joga»** (onde:
  «deck Oswald», «Legacy»…) e **«quero vender»** se a marcou.
- **«A subir»** (`colecoes.html#subir`): a Reserved List inteira e todas as
  edições das famílias das coleções (duals, shocks, fetches, Expeditions), só
  acima de 20 €; ordenada pela variação a 30 dias, com a de 90 ao lado; cada
  linha diz se ele a tem e se joga. São números, não recomendações.

**Modo de edição:** +1 / −1, mudar a meta, ligar/desligar «quero vender»,
«juntar carta» na aberta.

**Vender:** secção nova **«Das coleções»** com as cartas marcadas «quero
vender», preço e total.

**Painel:** o valor total inclui as coleções, separado em decks · coleções ·
a mais.

**Decks e coleções, com fotos:** cada carta mostra se está validada (ícone de
câmara) e o progresso tem as duas contas: «60 de 75 · 45 validadas». Uma
carta validada mostra o recorte da cópia dele; um toque continua a mostrar a
imagem oficial e a escolha da edição. Uma por validar fica com a imagem da
Scryfall.

## Regras

- **Por validar conta.** Uma cópia marcada no site conta para «tenho», faltas e
  valor, e aparece como por validar.
- **−1 tira primeiro uma por validar.** Só quando não há nenhuma é que sai uma
  validada; a validação fica marcada como desfeita (`n_validacao.desfeita_em`)
  e a ligação à foto não se perde.
- **Uma foto que não bate certo** (outra edição, menos cópias, foil em vez de
  normal) não corrige nada sozinha: o Claude mostra a diferença e pergunta.
- **Nada se grava sem o «sim» dele** na conversa.
- **«Joga»:** a carta está na versão atual de um deck dele, ou aparece em
  listas de torneio (MTGO e mtgtop8, qualquer formato) nos últimos 90 dias.
- **«Quero vender»** é marcado por ele. Não há regra automática de venda: quando
  tiver as cartas todas registadas, procura-se o padrão nas marcações dele
  (variação, «joga») e só então se propõe uma regra.

## Preços

- **Regra geral:** como nos decks, o trend do Cardmarket da edição e do
  acabamento.
- **Português (as Shocks PT): só preço português.** Vem das ofertas em
  português do CardTrader, com o filtro de ofertas de sempre
  (`precos.oferta_utilizavel`, com a língua `pt`). Cada oferta PT aceite que
  aparece fica guardada; o preço é a mais barata do **último dia em que houve
  ofertas PT**, mostrada com «visto há N dias». Nunca vista = sem preço. Nunca
  se usa o preço em inglês.
  - Medido a 30/10/2026 (antes do filtro): só 5 das 10 tinham ofertas PT, 1 ou
    2 cada (Sacred Foundry 10,15 €; Stomping Ground 7,14 € e 124,14 €; Godless
    Shrine 21,80 €; Breeding Pool 12,31 €; Blood Crypt 110,63 €).
- **Preços que não se apagam:** o `n_preco_vigiado` guarda o preço do dia das
  cartas das coleções, da Reserved List inteira e das famílias acima de 20 €,
  fora da poda de 30 dias do `price_history`. Daqui saem as variações e os
  gráficos. Nos dias antes do primeiro registo usa-se o `price_history` que
  houver (a Reserved List tem desde 10/08/2026).

## Fotos

- **Entrada:** ele manda a foto no chat (pode ser pelo Remote Control). As
  imagens ficam no registo da sessão neste PC (`~/.claude/projects/…/<sessão>.jsonl`,
  em base64; testado a 30/10: 1932 × 1932 px). O Claude tira-a de lá e guarda o
  **original** em `data/fotos/originais/AAAA-MM-DD/` (fora do Git).
- **Recorte:** `mtgvault/nucleo/fotos.py` encontra o retângulo de cada carta
  (OpenCV, `opencv-python-headless`, instalado a 30/10), endireita-o e grava o
  recorte em `assets/cartas/<foto>-<n>.jpg` (488 px de largura, ~30 KB), **no
  Git**, porque o site público também os mostra. Se não encontrar as cartas
  todas, diz e pede outra foto; não adivinha.
- **Validar** («valida o Oswald»): o Claude pede as cartas por validar aos
  lotes (até 9 por foto, 4 nas caras), lê cada foto contra o lote e mostra a
  tabela; com o «sim» dele, as cópias passam a validadas e ligadas ao recorte.
- **Registar por foto:** igual, e as cópias entram já validadas.
- **Que recorte aparece:** com várias cópias validadas da mesma carta no mesmo
  deck ou coleção, mostra-se o recorte da validação mais recente.
- Os passos que o Claude corre são comandos do CLI (`py -m mtgvault.cli nucleo
  fotos …`: extrair, recortar, validar), para não depender de scripts soltos.

## Dados

Tabelas novas e mudanças no `data/vault.db`, por migração (`schema.sql` +
`db._migrate()`):

- `n_colecao` — slug, nome, tipo (`fechada`/`aberta`), arte, ordem.
- `n_colecao_carta` — id, coleção, nome, scryfall_id, acabamento, língua,
  meta (vazia na aberta), **tenho** (a posse da coleção), vender (0/1). Cada
  linha já é uma edição, um acabamento e uma língua, por isso a posse vive
  aqui e a `n_posse` dos decks não muda.
- `n_colecao_log` — request_id, carta, delta, quando (o +1/−1 é idempotente,
  como nos decks).
- `n_foto` — id, caminho do original, dia, sessão e linha do registo de onde
  veio, para que deck ou coleção era.
- `n_recorte` — foto, número, caminho em `assets/cartas/`.
- `n_validacao` — recorte, âmbito (slug do deck, `rotativos` ou slug da
  coleção), scryfall_id, acabamento, língua, quantidade, quando, desfeita_em.
  As validadas de uma carta = soma das não desfeitas (nunca mais do que a
  posse); um −1 que desça abaixo delas desfaz a mais recente e a linha fica.
- `n_preco_pt` — scryfall_id, acabamento, dia, preço da oferta PT mais barata
  aceite, número de ofertas PT.
- `n_preco_vigiado` — dia, scryfall_id, acabamento, preço (€). Só se escreve
  quando o preço muda (como o `price_history`); nunca podada.
- `n_jogada` — formato, mês (`AAAA-MM`), nome da carta, em quantas listas.
  Nunca podada.
- `n_valor` ganha `colecoes_eur`.

## Recolha diária (03:30, tarefa `mtgvault-daily`)

Depois dos preços: preço do dia das vigiadas → ofertas PT do CardTrader (as
edições `rav`, `gpt`, `dis`) → recolha das listas de torneio (religada **só**
para encher o `n_jogada`, antes da poda de 30 dias; o metagame antigo continua
desligado) → valor do dia com as coleções → páginas. Uma fonte que falha deixa
a tarefa vermelha e a página diz-o.

## Testes e publicação

- Na bateria de sempre (`py tests\_bateria.py`), sem rede e sem a base real:
  coleções fechada e aberta, meta e língua; preço só PT com «último visto» e
  sem cair no inglês; validação, o −1 a tirar primeiro as por validar e a foto
  que não bate certo; o recorte numa imagem sintética (cartas desenhadas num
  fundo); «joga» e «a subir»; as páginas (Coleção, Vender com «Das coleções»,
  Painel com as três partes, o recorte no lugar da imagem).
- `colecoes.html` e `assets/cartas/` entram no `publicar.publicaveis()`, no
  `git add` do `daily.yml` e na tarefa `mtgvault-daily`. Menu com 4 entradas
  no `site_shell` e nos passos do `e2e-sites`.
- Antes de dar por feito: ver no browser (computador e telemóvel) a Coleção,
  uma coleção, «a subir», Vender e um deck com recortes, já publicado.

## Fora deste trabalho

- Marcar as cartas e tirar as fotos (o André).
- A regra automática de venda (depois das marcações dele).
- Os três testes da bateria que falham por ainda verificarem o site antigo
  (`test_casca`, `test_paginas`, `test_so_cardtrader`): ficam como estavam.
