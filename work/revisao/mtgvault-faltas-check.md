# «Já a tenho, está no deck»: dar check nas faltas (2026-09-08)

Pedido do André, à letra, com a imagem do painel *Montar Blue Farm* aberto no
passo 2 («Comprar o que falta», 7 cartas):

> *"Arranja forma de eu poder dar check nas cartas das faltas, para dizer que já
> as tenho e já coloquei no deck."*

Metade do que está na lista de compras dele é coisa que já tem em casa e que o
vault nunca catalogou. Até aqui só havia um caminho para lá chegar — tirar foto,
esperar pela importação — e enquanto isso a caixa continuava a dizer que a carta
faltava e a somá-la ao *"fechar tudo por X €"*, que é o número por que ele decide.

## O que passou a existir

**Um check por linha da wantlist da caixa** (passo 2 do painel *Montar*), só no
modo edição. Marcar grava **duas** coisas, e as duas são precisas:

* a **cópia** na `copies` — é uma carta que existe em casa e o vault não sabia;
* o **lugar** dela na `copy_allocation` daquela caixa — é onde ela está, que foi
  o que ele disse.

Uma sem a outra deixava o vault a discordar dele: a cópia sem caixa manda-o à
gaveta onde ela não está; a caixa sem cópia volta a pedir a carta amanhã.

**A edição é a parte que ele não sabe de cabeça**, e não se finge que sabe. A
linha traz um selector com as impressões que **cumprem a regra daquela caixa** —
o palpite (`find_printing(adivinhar=True)`, a mais recente e, dentro dessa data,
a mais barata) vem escolhido. Se ele não lhe tocar, a cópia fica com a nota
`registada a partir das faltas em <data>; edicao por confirmar` e aparece no
**passo 1** num bloco próprio, *«✓ Já na caixa (disseste que tinhas)»*, com o
aviso **📷 edição por confirmar**. Sem esse bloco o palpite virava facto por
ninguém voltar a abrir a `notes` de uma cópia — é o padrão do `event_tier`.

**A foto que chegar depois ACERTA essa cópia em vez de criar outra**
(`collection.acertar_edicao`, ligada por nome + a marca da nota). Criar uma
segunda era ficar com o dobro das cartas na base por ele ter sido diligente — a
caixa passava a "ter" 4 Meddling Mage que na estante são 2. Se a foto trouxer
menos cópias do que as que estavam por confirmar, a linha **parte-se**: a
confirmada leva consigo o seu lugar dentro da caixa e o resto continua à espera.
O que a foto trouxer **a mais** entra como sempre entrou.

**O anular** (os mesmos segundos do registo de montagem, `montar.anular_segundos`)
apaga a cópia que acabou de nascer. Só essa: o `anular_falta` recusa qualquer
`copy_id` sem a marca. Passada a janela é uma cópia normal, e o que a tira é o
**«vendida»**, que é o caminho com rasto — um desfazer sem prazo era um segundo
caminho para apagar cartas, e esse já existe com backup.

**O rasto fica em `data/registos-faltas.csv`** (data, acção, caixa, carta, bloco,
quantidade, edição, número, língua, acabamento, palpite, `copy_id`), fora do Git
como o `vendas.csv` e pela mesma razão: a `vault.db` é descarregada e republicada
inteira a cada corrida. É a contrapartida de um botão que **cria** cartas — sem
ele, daqui a um mês não há como saber donde veio uma cópia sem foto. Escreve-se
**antes** da alocação (e depois da cópia, que é quem dá o `copy_id`): sobrar uma
cópia fora da caixa é visível, não registar a criação não é.

## A regra de material da caixa manda

O material da cópia é a leitura em positivo do `_porque_nao`: o que ele acabou de
dizer que tem é, por definição, material que a caixa aceita — senão não fechava o
slot. `loadout.material_da_caixa` → *(acabamento, língua)*; `edicao_limite` → a
data-limite (`≤ Scourge` no Premodern).

Medido na base de 2026-09-08:

| caixa | regra | cópia criada |
|---|---|---|
| UW Replenish | `PT · ≤SCG` | `pt`, `nonfoil`, **PLS** (Planeshift) |
| Cloud (Duel Commander) | `foil` | `en`, `foil` |

Isto não é cosmética: a impressão **mais recente** de Swords to Plowshares é de
2022 e é a que um `--adivinhar` sem regras escolheria — a caixa de Premodern
recusá-la-ia no dia seguinte e a carta voltava à lista de compras sem ninguém
perceber porquê. Por isso o `ate`/`finishes` desceram até ao
`scryfall.find_printing`, e uma edição escrita à mão que a caixa não aceite é
**recusada** (`ValueError` → 409, com a razão): o selector nunca a ofereceu, e um
pedido cru não pode meter um 2X2 numa caixa de Premodern.

## Medido na base a sério (numa cópia da `vault.db` de 2026-09-08)

A alocação **não mexe** enquanto ninguém carrega em nada — 8 426,34 € para
fechar, 232 a comprar, 70 a ir buscar, 345 a arrumar, venda 1 315,68 € +
3 221,01 € de RL, iguais antes e depois.

Um check a sério (a carta mais cara em falta da primeira caixa de Premodern):

```
caixa : UW Replenish (PT · ≤SCG)   95 % · comprar 3 · 4,42 €
check : 2× Meddling Mage  PLS  pt  nonfoil   (palpite)
depois: UW Replenish       97 % · comprar 1 · 1,10 €
        fechar tudo 8 426,34 € -> 8 423,02 €   ·   comprar 232 -> 230
        venda e "ir buscar" iguais
foto  : 728 cópias -> 728 (a MESMA linha passou a ter a edição da foto)
        por confirmar 2 -> 0
```

**A arrumação sobe 345 → 347**, e é honesto: a linha do sideboard tinha 2 cópias
já alocadas e 2 em falta, e uma linha **incompleta vive em `missing`** — o
`movimentos_de_entrada` só percorre o `have`, por isso as 2 cópias que ele já
tinha nunca apareciam no plano. Ao fechar a linha, elas passam a aparecer.
**É um buraco anterior a este trabalho** (uma caixa nunca é mandada ir buscar as
cópias que tem de uma carta de que está curta) e ficou por corrigir de propósito:
mexer nele mudava o 345 de todas as caixas, que é um número que o CLAUDE.md
publica.

## Custo da página

O selector é uma consulta ao catálogo por carta em falta (148 de 149 linhas têm
edições — a excepção é o *Ademi of the Silkchutes*, que não está no catálogo, e
aí não se desenha check nenhum: um check que só pode falhar é pior do que check
nenhum). Duas decisões para isso não pesar:

* **só no modo edição** — o site publicado não tem endpoint que grave, e um
  selector que não grava é ruído (a mesma razão dos botões e da barra). O
  `deckboxes.html` publicado fica igual: 758 KB, zero `eds`;
* **`name = ?` em vez de `lower(name) = lower(?)`** no `scryfall.impressoes`. O
  `lower()` não usa o índice `ix_cards_name` e varria as ~500 mil impressões do
  catálogo: o payload do modo edição demorava **10,7 s** e passou a **1,2 s** — e
  isso corre a **cada clique** (o `regenerar` refaz as duas páginas). O caminho
  tolerante fica como recurso para os nomes escritos à mão.

A página do modo edição passou de 758 KB para **797 KB** (+39 KB de edições).

O `set_type = 'memorabilia'` fica de fora das candidatas: uma carta *oversized*
de 15×23 cm não entra numa deckbox. Os **promos ficam** (ele pode ter um), e por
isso o palpite pode calhar num — quando o promo é a impressão mais recente antes
do corte. É para isso que o selector está ali, e é para isso que a cópia fica
marcada por confirmar.

## Testes

`tests/test_faltas_check.py` (9 casos, sem rede, com o harness de node para o
lado do browser): o check cria a cópia **e** a alocação **e** a linha do registo;
a regra de material manda (PT/`ody` no Premodern, EN foil/`2xm` no Legacy, e o
`2x2` recusado); a linha sai do passo 2 e entra no passo 1; o anular apaga a
cópia nova e **não** toca numa cópia normal; a foto acerta a edição em vez de
duplicar (incluindo o caso em que traz menos e o caso em que traz mais); o pedido
passa pelo handler HTTP e sem token é 403; e a página desenha o check e o
selector no modo edição e **nada disso** no site publicado.

Bateria toda verde (34 ficheiros).
