# mtgvault — sideboard separado na caixa, e desmontagem registada

2026-09-08 · ramo `ai-pc/montar-sideboard-2026-09-08`

Pedido do André, à letra: *"Preciso também de saber o que é sideboard nos decks,
para ficar separado dentro da mesma caixa."*

## O que mudou

**1. Dois blocos, Main e Sideboard.** `loadout.blocos_de_board(movs, totais)`
parte qualquer lista de movimentos nos dois blocos da caixa; `loadout.
totais_por_board(s)` dá o «de M» do cabeçalho, a partir da MESMA lista por que a
percentagem da caixa é calculada. Usam-no os três sítios onde a lista aparece:

- o painel **Montar** de cada caixa (`deckboxes._montar_payload` → `blocos`), com
  a ordem de sempre dentro de cada bloco — cor e depois nome, que é como o binder
  está arrumado;
- a aba **Arrumar**, dos dois lados (por gaveta e por caixa), mais um `SB` em
  cada linha de sideboard;
- o `python -m mtgvault.cli arrumar`.

A página **não** volta a decidir o que é sideboard em JavaScript: recebe os
blocos já partidos, pela mesma razão que recebe o `foil` já decidido (ver
`loadout.e_foil` — `"nonfoil"` contém `"foil"`).

A carta que joga no main **e** no side vem em **duas linhas**, uma em cada bloco.
São duas cópias físicas em duas pilhas; uma linha só (`2×`) não dizia qual ia
para onde. O `board` viaja no movimento desde a linha da alocação
(`movimentos_de_entrada`), não se recalcula em lado nenhum.

Um movimento **sem** bloco — o que SAI de uma caixa, que vem do lote e não da
lista — fica num bloco próprio no fim (*"A devolver à gaveta"*). Chamar-lhe
"main" era inventar uma resposta.

**2. `// Sideboard` no texto copiado.** A wantlist da caixa sai com as compras do
main, a linha `// Sideboard`, e depois as do side — nos dois formatos (*"copiar
p/ Cardmarket"* e *"copiar com material"*). O Cardmarket ignora a linha de
comentário sem erro. O separador só aparece quando há sideboard, e só na wantlist
DA CAIXA: a aba *Comprar* junta compras de várias caixas e aí a linha não tem
bloco.

**3. Botão «Desmontar».** `loadout.desmontar_caixa(con, slot, nome)`: backup da
base (`data/backups/vault-<data>-desmontar.db`, `VACUUM main INTO`), linha em
`data/desmontar.log` escrita **antes** de a base mexer, e a `copy_allocation`
daquela caixa esvazia-se. O `webapp` põe a caixa em `permanente` — mas **só se
estava `montada`**: uma candidata fica candidata, porque ele carregou no botão
para arrumar cartas e não para escolher prioridades.

O botão aparece quando a caixa está montada **ou** tem cartas registadas lá
dentro (`slot["arrumada"]`, novo, de `caixas_arrumadas`) — que era exactamente o
caso das quatro caixas de hoje. O *"tirar da caixa"* de uma caixa montada passa
agora pelo mesmo motor: dois caminhos para o mesmo gesto era o que a escala de
estados da v6 veio evitar. Tem confirmação no browser, como a venda.

## Medido na base a sério (2026-09-08, config actual)

```
fechar 8 426,34 € | comprar 232 | ir buscar 70 | arrumar 535
venda 243c/1 621,76 € | RL 41c/3 442,20 €
```

Os blocos por caixa, e de que gaveta sai cada uma:

| caixa | estado | tirar | blocos | gavetas |
|---|---|---|---|---|
| Stiflenought | montada | 58 | Main 43/60 · SB 15/15 | Colecção 53, Caixa RL (PT) 5 |
| UW Replenish | permanente | 54 | Main 46/60 · SB 8/15 | Colecção 45, Caixa RL (PT) 9 |
| Oath of Druids | permanente | 35 | Main 29/60 · SB 6/15 | Colecção 35 |
| Enchantress | permanente | 15 | Main 10/60 · SB 5/15 | Colecção 11, Caixa RL (PT) 4 |
| Ill-Gotten Gains | permanente | 17 | Main 14/60 · SB 3/15 | Colecção 16, Caixa RL (PT) 1 |
| Elves / Survival | permanente | 21 | Main 17/60 · SB 4/15 | Colecção 11, Caixa RL (PT) 10 |
| Blue Farm | permanente | 93 | Main 93/100 | Colecção 92, Caixa RL (EN) 1 |
| Cloud cEDH | permanente | 57 | Main 57/100 | Colecção 56, Caixa RL (EN) 1 |
| Cloud (Duel Commander) | permanente | 52 | Main 52/97 | Colecção 52 |
| Pauper (Luffy) | permanente | 74 | Main 59/60 · SB 15/15 | Colecção 74 |
| Modern — UW Oswald | permanente | 49 | Main 37/60 · SB 12/14 | Colecção 49 |
| Pioneer — Greasefang | permanente | 10 | Main 8/60 · SB 2/15 | Colecção 10 |
| Standard / Legacy | candidata | 0 | — | — |

## A limpeza de hoje: está coerente

O supervisor limpou à mão a `copy_allocation` das quatro caixas que não estão
fisicamente montadas (backup `data/backups/vault-20260908-1352-desmontar.db`,
log `data/desmontar.log`) e pôs `estado: permanente` no config. Verificado na
base:

- `copy_allocation` = **0 linhas**. O Stiflenought já não tinha nenhuma (é o caso
  documentado de 2026-09-07: `montada` com a tabela vazia), por isso continua a
  mostrar o painel **✅ Confirmar** em vez de mandar montá-lo outra vez — que é o
  correcto, porque é o único que está mesmo montado;
- as outras quatro aparecem em **«🔧 a montar»**, com a lista *"tirar da
  Colecção"* completa (93, 57, 52 e 74 cópias);
- **`balde_origem` não ficou incoerente**: as gavetas só dizem `Colecção` e
  `Caixa RL (PT)`/`(EN)`, que são as duas que existem depois da migração de
  colecção única. Está preenchido em 656 dos 727 lotes — os 71 que faltam são
  exactamente os da `Caixa Reserved List`, que nunca se moveram e por isso nunca
  tiveram origem para registar;
- a **arrumação subiu de ~307 para 535 cópias**, que é o esperado: as 225 linhas
  que a limpeza tirou passaram a ser cartas a ir buscar à `Colecção`. Não é
  incoerência, é a mesma verdade dita ao contrário.

## Testes

`tests/test_sideboard.py`, novo (5 casos): os dois blocos com o «N de M» e a
carta que joga nos dois em duas linhas; o `// Sideboard` no texto copiado; os
cabeçalhos no HTML que a aba desenhou (harness de `node`, salta sem ele); o
`desmontar` a limpar, a copiar a base e a escrever a linha do log (e idempotente
— uma caixa vazia não repete a linha nem escreve backup); e o botão a aparecer
numa caixa com cartas dentro que não se diz montada, sem a promover.

Bateria toda verde: **29 ficheiros, TUDO OK**.
