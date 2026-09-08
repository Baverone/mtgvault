# As cópias de uma linha incompleta também se tiram da gaveta

2026-09-08. Fecha o buraco que ficou escrito na nota *"arrumar 345 → 347"* do
`mtgvault-faltas-check.md`.

## O que estava mal

Uma linha que pede 4 e a que a alocação só deu 2 vive em `s["missing"]`, com os
seus `lotes` — as duas cópias existem, são daquela caixa e estão na `Colecção`.
Mas **tudo** o que percorria a alocação de uma caixa percorria só o `s["have"]`:

| onde | o que deixava de fora |
|---|---|
| `loadout.movimentos_de_entrada` | o painel *Montar*, a aba *Arrumar*, o CLI `arrumar`, o `moves-<data>.csv` e a barra «N de M» |
| `loadout._linhas_da_caixa` | o que o *"já arrumei tudo"* e o *"actualizei"* GRAVAM |
| `webapp.marcar_na_caixa` | o mesmo, reescrito à mão (e por isso com o mesmo defeito) |
| o `origens` do `report` | o chip *"tirar de:"* de cada caixa |
| `loadout.copias_por_confirmar` | o bloco *«já na caixa (disseste que tinhas)»* |
| `colecao_cor._de_outro_balde` | as cartas *"de &lt;balde&gt;"* da secção dos decks |

Na prática: ele montava a caixa, o painel não lhe dizia para tirar as 2 Argothian
Enchantress que tem na gaveta, ficavam na prateleira — e a aba *Comprar* pedia as
outras 2. **Nenhum passo dava erro.** É o padrão do `event_tier`: a folha que ele
leva para a estante está a menos duas cartas e nada o diz.

Pior do que não mostrar: se ele as tirasse à mão, o registo não as gravava
(`linhas_da_caixa` também as ignorava), e no dia seguinte o painel mandava-o
procurá-las outra vez.

## O que se fez

**`loadout.linhas_alocadas(s)`** = `have` + as de `missing` **com lotes**. Uma
função só, pela razão de sempre: eram cinco sítios a escrever `for m in
s["have"]`, e o primeiro que se esquecesse voltava a pôr a base e o painel a
discordar em silêncio. As seis linhas da tabela acima passaram a lê-la.

O `webapp.marcar_na_caixa` tinha o `linhas_da_caixa` **reescrito à mão** e por
isso ficava de fora da correcção: passou a chamá-lo — e é por isso que o
`_linhas_da_caixa` deixou de ser privado.

**Uma linha em falta sem NENHUMA cópia continua a não entrar.** Não há nada para
tirar da gaveta, e inventar-lhe um movimento era mandá-lo procurar uma carta que
não existe em casa. É compra, e vive na aba *Comprar*.

**A linha diz porque é que vem a menos**: `loadout.nota_parcial` →
*«2 de 4 — 2 em Comprar»*, *«1 de 3 — 2 noutra caixa»*, com moldura âmbar — a
mesma do *"está noutra caixa"*, porque a pergunta é a mesma: esta linha não fecha
com o que está aqui. O texto é composto no Python e não no browser, pela razão de
sempre: quem sabe partir a falta em *comprar* e *ir buscar* é a alocação, não a
página (ver `e_foil`). Aparece na grelha do painel *Montar* e no `arrumar` do CLI.

## Medido (base de 2026-09-08, a mesma cópia dos dois lados)

A alocação **não mexe**, que é o que tinha de acontecer: isto é o que se VÊ, não
o que se compra.

| | antes | depois |
|---|---|---|
| fechar tudo | 8 426,34 € | **8 426,34 €** |
| a comprar | 232 | **232** |
| destinadas a outra caixa | 70 | **70** |
| venda | 230 cópias | **230 cópias** |
| **arrumar** | 345 cópias / 202 linhas | **385 / 226** |

As +40 cópias são exactamente as parciais, e o «N de M» da barra sobe o mesmo:

| caixa | tirar (antes → depois) | das quais parciais |
|---|---|---|
| UW Replenish | 59 → **66** | 7 |
| Oath of Druids | 36 → **49** | 13 |
| Enchantress | 17 → **23** | 6 |
| Ill-Gotten Gains | 17 → **24** | 7 |
| Elves / Survival | 22 → **24** | 2 |
| Modern — UW Oswald | 49 → **50** | 1 |
| Pioneer — Greasefang | 10 → **14** | 4 |

As restantes cinco caixas (Stiflenought, Blue Farm, Cloud cEDH, Cloud DC, Pauper)
não têm linhas incompletas com cópias e não mexem.

No CLI, `arrumar` passa a ter **48 linhas com nota**:

```
    2× Argothian Enchantress [USG]   -> Enchantress        (2 de 4 — 2 em Comprar)
    1× Parallax Wave [NEM]           -> Enchantress        (1 de 3 — 2 noutra caixa)
    3× Mishra's Factory [4BB]        -> Oath of Druids     (3 de 4 — 1 em Comprar)
```

Na página, o harness de node desenha as 23 abas sem um erro e conta **24 linhas
`mv parc`** em 7 caixas (uma linha por lote — a mesma carta em dois lotes vem em
duas linhas, que são duas idas à gaveta).

## Testes

`tests/test_incompletos.py`, 7 casos, sem rede: a linha incompleta gera
movimento com a nota certa; a linha a zero **não** gera; a barra conta-as (o
`marcar_q` e as checkboxes que a grelha desenhou dão o mesmo número); o registo
grava-as na `copy_allocation` e no dia seguinte já não as manda tirar; o plano de
arrumação, o CSV e o *"já arrumei tudo"* levam-nas; a alocação e as compras não
mexem; e o harness de node confirma que a nota e a moldura chegam ao HTML.

Bateria toda verde (35 ficheiros).
