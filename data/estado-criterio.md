# Como se avalia o estado de uma carta

**Fonte:** <https://help.cardmarket.com/en/CardCondition>, lida a **2026-10-03**.
**A escala que conta é a do Cardmarket**, porque é lá que o André vende e é de lá
que vem o preço com que o vault soma a colecção.

Este ficheiro é para ser **LIDO antes de cada avaliação** — pelo Claude que lê as
fotos (o `pendentes/esperadas.md` traz-lhe isto à frente) e por quem corra
`py -m mtgvault.cli estado criterio`. Não vive na cabeça de ninguém.

> Palavras do Cardmarket, à cabeça da página: *«The grading of trading cards
> sometimes leads to conflict among buyers and sellers, mainly because grading is
> not an exact science. One person might consider a card to be still Near Mint
> while the next one thinks it is in Excellent condition.»*

## Como se olha

- **À luz natural.** O Cardmarket di-lo no texto do Near Mint: *«When the card is
  inspected under bright daylight, the surface must generally appear clean.»*
- **Cinco zonas:** a **frente**, o **verso**, as **bordas**, os **cantos** e a
  **planura** (se a carta assenta na mesa).
- **A idade não desculpa nada** (*«Old cards»*): *«A 20 years old card has to
  adhere to the same criteria as a 2 days old card.»*
- **Os erros de fabrico não contam** (*«Production Errors»*): arte desalinhada ou
  texto torto não baixam o escalão — mas dizem-se no comentário.
- **Nas foils olha-se duas vezes** para vincos e *clouding*: *«On nonfoil cards
  these damages make the card appear uglier, but the effect is compounded for
  foils.»*
- **Sem escala parcial.** *«We don't support this kind of grading»* (NM-, EX+): se
  escreves NM tem de se poder defender como Near Mint.

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

## As regras avulsas que decidem casos concretos

Também da mesma página, e cada uma já resolveu uma dúvida:

- **Clouding** — *«Visible clouding precludes a card from being Near Mint.»*
- **Scratched** — *«If a card has scratches on the surface, this makes the card
  GOOD at best.»* (e nas foils pesa mais)
- **Planarity** — côncava ou convexa é aceitável em tudo o que não seja Mint; *«if
  the card has been deformed so strongly and lastingly that it might not be
  tournament legal any more, then it has to be graded Played»*
- **Bend** — *«A card is bent if the structure of the paper has been damaged due to
  excessive bending.»*
- **Inked / Blackened Borders** — *«always considered to be in Poor condition»*
- **Altered** — não é um escalão: é outra coisa, e vende-se com foto da alteração

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
ensina. Escreve-se o quê e **onde**:

- *«EX: pontos brancos no canto inferior esquerdo e na borda de cima; superfície
  limpa»*
- *«GD: branco em todas as bordas, dois riscos visíveis junto à arte, sem
  vincos»*

E, quando não se consegue decidir, diz-se — *«não consigo ver as bordas: a foto
está com flash de frente»* — em vez de escolher um escalão a adivinhar.

## Aprendido com o André

*Gerado de 0 correcções dele, em 2026-10-06. Só entra aqui o que veio de uma correcção — nunca um palpite meu.*

Ainda não há nenhuma correcção dele. O critério em vigor é o do Cardmarket, acima, e mais nada.
