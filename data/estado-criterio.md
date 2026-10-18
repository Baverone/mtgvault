# Como se avalia o estado de uma carta

**Fonte:** <https://help.cardmarket.com/en/CardCondition>, lida a **2026-10-03**.
**A escala que conta é a do Cardmarket**, porque é lá que o André vende e é de lá
que vem o preço com que o vault soma a colecção.

**O método** (os três critérios, os limiares e as verificações próprias da
colecção dele) vem da pesquisa de **2026-10-13**, `data/grading-pesquisa-2026-10-13.txt`,
que leu as normas do PSA e do BGS (cardgrading.app), pregradecards.com e
scanyourmtg.com. A régua continua a ser a do Cardmarket: do PSA/BGS tirou-se a
**decomposição** do juízo, não a escala.

Este ficheiro é para ser **LIDO antes de cada avaliação** — pelo Claude que lê as
fotos (o `pendentes/esperadas.md` traz-lhe isto à frente) e por quem corra
`py -m mtgvault.cli estado criterio`. Não vive na cabeça de ninguém.

> Palavras do Cardmarket, à cabeça da página: *«The grading of trading cards
> sometimes leads to conflict among buyers and sellers, mainly because grading is
> not an exact science. One person might consider a card to be still Near Mint
> while the next one thinks it is in Excellent condition.»*

## Como se olha

- **Tapete PRETO — é REQUISITO das fotos, não sugestão** (2026-10-13). Dois
  motivos: (1) a borda preta do Magic **não esconde branco** — contra preto
  qualquer ponto branco salta, contra branco desaparece; (2) contra preto
  distingue-se uma borda **lascada** (branco à mostra) de uma borda **pintada com
  marcador** (alguém passou tinta por cima do branco). O segundo é **detecção de
  fraude** e serve sobretudo para o que ele COMPRA. Uma foto em fundo claro
  di-lo nos motivos e não leva NM.
- **Luz forte e UNIFORME** — a luz natural de janela serve bem. O Cardmarket di-lo
  no texto do Near Mint: *«When the card is inspected under bright daylight, the
  surface must generally appear clean.»* Luz fraca **esconde** e faz
  sobre-avaliar.
- **Limpa com microfibra primeiro**: pó e dedadas confundem-se com desgaste.
- **Por esta ordem:** (1) **bordas e cantos** — é onde está a maioria do desgaste
  e é o que separa NM de EX; (2) **superfície**, inclinando a carta contra a luz —
  os riscos só aparecem em certos ângulos, e nos foils olha-se mais; (3)
  **planura**, olhando ao longo da carta (faz parte da superfície, abaixo).
- **A idade não desculpa nada** (*«Old cards»*): *«A 20 years old card has to
  adhere to the same criteria as a 2 days old card.»* — **e julga-se ERA CONTRA
  ERA** (2026-10-13). As duas regras não se contradizem: os critérios de
  DESGASTE (branco nas bordas, cantos, riscos, vincos) são os mesmos para uma
  carta de 1994 e uma de ontem; o que se compara com cartas da MESMA era é o
  **material** — o cartão velho é outro (outra cor de verso, outro brilho, outra
  textura de impressão), e isso não é desgaste. Uma Revised não é «EX porque não
  brilha como uma carta de 2024».
- **Sem escala parcial.** *«We don't support this kind of grading»* (NM-, EX+): se
  escreves NM tem de se poder defender como Near Mint.
- **Na dúvida, desce um escalão.** Quem compra fica contente por receber melhor do
  que esperava; o contrário gera disputa.

## O método: três critérios — cantos, bordas, superfície

O PSA e o BGS partem o juízo em quatro critérios. É essa decomposição que se
usa, porque transforma *«parece EX»* num juízo com razões que se conferem. Para
o André são **TRÊS**: **cantos**, **bordas** e **superfície**.

**Cada juízo leva um sub-juízo por critério, com a ZONA**, no `condition_notes`,
sempre nesta forma e com estas três palavras:

```
cantos: <o que se vê e onde> | bordas: <…> | superfície: <…>
```

*«cantos: inferior esquerdo amolecido | bordas: branco na de cima, a toda a
largura | superfície: limpa, sem vincos»*. Um critério que não se consegue ver
diz-se assim mesmo (*«bordas: não se vêem — flash de frente»*). O escalão sai do
PIOR dos três.

### A centragem NÃO conta — está excluída

A centragem (as margens iguais à volta da arte) é o quarto critério do PSA e do
BGS, e **aqui não se mede nem se menciona**: é uma propriedade de **fabrico**, não
de **desgaste**. Uma carta mal centrada de origem continua **NM** no Cardmarket. O
PSA mede-a com tolerâncias — o **10 exige 55/45** à frente, o **9 exige 65/35**, o
**8 exige 70/30** —; o Cardmarket ignora-a. Só interessaria se ele algum dia
mandasse **selar** uma carta.

É o mesmo princípio que o Cardmarket escreve para todos os defeitos de fabrico
(*«Production Errors»*): arte desalinhada, texto torto ou linhas de impressão
**não baixam o escalão** — mas dizem-se no comentário.

### 1. Cantos

- **Um único canto amolecido** (redondo, fiado, com a ponta branca) **chega para a
  carta deixar de ser NM — passa a EX.** A pesquisa escreve *«de NM para LP»*
  porque usa a escala AMERICANA, onde o *Lightly Played* é o **EX** do Cardmarket
  (a ponte que o próprio Cardmarket dá, `estado.PONTE_AMERICANA`). O **LP** do
  Cardmarket é o americano *Played*, dois escalões abaixo.
- Cantos dobrados ou com a camada a levantar contam também como superfície (é um
  vinco).

### 2. Bordas

- **Branco visível na borda a olho nu = já não é NM.** É o limiar do PSA (*«se
  consegues ver branco na borda à vista desarmada, é PSA 8 no máximo»*) traduzido
  para esta escala. O NM do Cardmarket admite *«small white spots, but they must
  be very few and very small»* — pontinhos que se procuram, não uma linha que se
  vê.
- **Várias bordas branqueadas** empurram para **GD** (o americano *Moderately
  Played*).
- **Bordas pintadas** — *«Inked / Blackened Borders — always considered to be in
  Poor condition»*. É por elas que o tapete preto é requisito: contra preto o
  marcador vê-se (brilho diferente, cor que não bate com a borda impressa).

### 3. Superfície (riscos, vincos, manchas, brilho, planura)

- **Riscos** — *«If a card has scratches on the surface, this makes the card GOOD
  at best.»* E nas foils pesa mais.
- **Nas foils olha-se duas vezes** para vincos e *clouding*: *«On nonfoil cards
  these damages make the card appear uglier, but the effect is compounded for
  foils.»*
- **Clouding** — *«Visible clouding precludes a card from being Near Mint.»*
  **VERIFICAÇÃO PRÓPRIA (2026-10-13): os foils da era Urza's e da 7.ª edição** —
  um véu LEITOSO, de humidade ao longo de ~20 anos, às vezes sai com microfibra. É
  exactamente a era do Premodern dele, por isso em cada foil dessa era a
  superfície diz SEMPRE se há véu ou não (*«superfície: sem véu»*), mesmo quando
  não há.
- **Vinco de baralhar** — marca em forma de unha na **borda de cima**, de baralhar
  em *riffle*. **Não tem conserto.** No PSA é 6 automático; nesta escala puxa para
  **LP ou PL** conforme a profundidade (pela ponte, o *Played* e o *Heavily
  Played* americanos).
- **Planura** — côncava ou convexa é aceitável em tudo o que não seja Mint; uma
  curva ligeira de humidade é normal. *«If the card has been deformed so strongly
  and lastingly that it might not be tournament legal any more, then it has to be
  graded Played»*. Um vinco que **QUEBRA** a superfície é grave.
- **Bend** — *«A card is bent if the structure of the paper has been damaged due to
  excessive bending.»*
- **Sujidade** — pó e dedadas não são dano (limpa-se primeiro); sujidade
  acumulada que não sai é desgaste de jogo (é o texto do GD).
- **Linhas de impressão nas duais de Revised** — **VERIFICAÇÃO PRÓPRIA
  (2026-10-13)**: linhas VERTICAIS de rolo, comuns nas duais de Revised, que o PSA
  passou a penalizar mais do que penalizava em 2020. Ele tem **45 duais**, quase
  todas Revised. São **defeito de fabrico**, por isso pela regra do Cardmarket
  **não baixam o escalão** — mas **dizem-se sempre** (*«superfície: linhas de rolo
  verticais na arte»*), porque mudam o valor de venda a um comprador exigente e
  decidem se vale a pena selar.

### O teste dos dois metros (para o escalão de baixo)

Se o desgaste é **óbvio a dois metros**, é o americano *Heavily Played* — o **PL**
do Cardmarket. Se é preciso **aproximar-se** para o encontrar, é *Moderately
Played* — o **GD**. Numa foto, é a pergunta do recorte a tamanho reduzido contra o
recorte ampliado.

### E duas regras de bom senso que decidem muitos casos

- **Uma carta que andou num deck sem sleeve praticamente nunca é NM.**
- **Altered** não é um escalão: é outra coisa, e vende-se com foto da alteração.

## Os sete escalões, nas palavras da fonte

### MT — Mint
O Cardmarket não dá ao Mint um texto próprio: remete para o Near Mint e diz que
**o Mint quase não se usa** — *«As the Mint grade is often not used for cards of
newer expansions, Near Mint usually means Near Mint or better (equivalent to the
American NM/M grade).»* E sobre o *Gem Mint*: *«Advertising a card as Mint
basically means that it satisfies collectors' criteria.»*

A imagem oficial do Mint diz: *«Front and Back of a Magic: The Gathering Card in
Mint condition. Both are in perfect condition.»*

**Numa foto de telemóvel não se distingue Mint de Near Mint.** Por isso o MT não
se atribui por foto — só à mão, por ele.

### NM — Near Mint
> *«A Near Mint card looks like it has never been played without sleeves. Small
> allowances can be made, but the card generally shows no wear.*
>
> *The border of NM card can have small white spots, but they must be very few and
> very small. When the card is inspected under bright daylight, the surface must
> generally appear clean. It can have a few minor spots, but scratches can never
> be allowed for NM cards.*
>
> *Generally a Near Mint card is in a condition that would make it considered
> unmarked if played in an unsleeved deck.»*

**Equivalente americano:** NM/M.

### EX — Excellent
> *«An Excellent card look like it was used for a few games without sleeves. For
> Excellent cards it is almost always clearly visible upon first inspection that
> the card is not in perfect condition. However, although the damage is clearly
> visible it is only of minor severity.*
>
> *Excellent cards usually have a couple of white spots at the corners or around
> the border. The surface may have minor scratches, that are visible upon closer
> inspection. However, the card cannot be graded Excellent if the creases are so
> deep that they are visible upon first sight.*
>
> *An Excellent card is usually in a condition where it is not quite clear if the
> card would be considered marked or unmarked if it would be played in a
> tournament without sleeves.»*

**Equivalente americano:** *Slightly Played* ou *Lightly Played* — e a fonte avisa:
*«not to be confused with the European Light Played»*.

### GD — Good
> *«A Good card looks like it might have been used for a long tournament without
> sleeves.*
>
> *Cards in Good condition usually show strong wear all around the card. The edges
> and corners have many white spots, the surface usually has scratches and the
> card usually has accumulated some dirt on its surface. However, the card still
> only has damage that stems from regular play. The card has no water damage or
> bends whatsoever.*
>
> *A Good card (and all cards in worse condition) are clearly in a condition that
> would make them ineligible for play without sleeves as they would be considered
> marked.»*

**Equivalente americano:** *Moderately Played* ou *Very Good*. E a fonte diz o que
é preciso dizer: *«Note that 'Good' is a bit of a misnomer. A Good card doesn't
really look good. In fact it looks pretty beat up.»*

### LP — Light Played
> *«A Light Played card looks as if it has been used without sleeves for an
> extended period of time.*
>
> *A Light Played card is clearly legal for play in a sleeved deck. It has also not
> been tampered with (inked border, random scribblings on the card etc.). If both
> of these criteria apply the card may look very bad, but it can be graded Light
> Played.»*

**Equivalente americano:** *Played* ou *Good*.

### PL — Played
> *«A Played card looks as bad as you can get a card through regular use without
> sleeves.*
>
> *A Played card looks extremely bad, and it is doubtful if the card is tournament
> legal even in a sleeved deck. However, the card has not been tampered with
> otherwise (inked border, random scribblings on the card etc.).»*

**Equivalente americano:** *Heavily Played* ou *Good*.

### PO — Poor
> *«A Poor card has damage that cannot normally have stemmed from regular use of
> the card.*
>
> *A card in Poor condition is literally destroyed. It is either obviously illegal
> for tournament play or has been tampered with in ways that destroy its worth
> almost completely (inked border, random scribblings on the card etc.).»*

**Equivalente americano:** *Poor*.

## O que o verso serve para dizer

**Todos os versos de Magic são iguais.** O verso **não serve para identificar a
carta** — serve para ver o desgaste que a frente não mostra: o branqueamento das
bordas e dos cantos visto do outro lado, vincos, manchas, danos de água. É por
isso que:

- **o escalão sai do verso** quando ele existe;
- **sem verso o estado fica «por verificar»** e não se inventa um escalão.

## O que se consegue mesmo ver numa foto de telemóvel

Isto é para o André não contar com o que não vai ter:

- **vê-se:** vincos, branqueamento de bordas e cantos, riscos visíveis, desgaste
  de jogo, sujidade. Dá para um escalão defensável entre **NM, EX, GD e LP**, com
  a razão à frente;
- **não se vê:** a diferença entre **NM e Mint**, e riscos finos de superfície;
- **a luz pesa mais do que a resolução:** o flash de frente **esconde** o desgaste
  das bordas; luz difusa num ângulo ligeiro **mostra-o**;
- **o escalão é sempre uma estimativa com motivo escrito**, nunca uma
  classificação certificada. Ele pode corrigi-lo à mão — e **a correcção dele
  ganha sempre**.

## Como se escreve um juízo

Um escalão **sem motivos escritos não conta**: é ele que se confere e é ele que
ensina. Escreve-se o quê e **onde**, um sub-juízo por critério:

- *«EX — cantos: inferior esquerdo com ponta branca | bordas: pontos brancos na de
  cima | superfície: limpa»*
- *«GD — cantos: os quatro com branco | bordas: branco em todas | superfície: dois
  riscos visíveis junto à arte, sem vincos»*

E, quando não se consegue decidir, diz-se — *«bordas: não consigo ver — a foto
está com flash de frente»* — em vez de escolher um escalão a adivinhar.

## Aprendido com o André

*Gerado de 0 correcções dele, em 2026-10-18. Só entra aqui o que veio de uma correcção — nunca um palpite meu.*

Ainda não há nenhuma correcção dele. O critério em vigor é o do Cardmarket, acima, e mais nada.
