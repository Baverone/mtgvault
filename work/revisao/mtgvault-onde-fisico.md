# Onde a carta ESTÁ vs a quem está DESTINADA

*2026-09-08 · ramo `ai-pc/onde-fisico-2026-09-08` · worktree
`C:\Users\Catarina\_revisao\mtgvault-fisico`*

> «De todas as cartas, só o Stiflenought está em deckbox; o resto ainda nada está
> em deckbox — e ainda estás a assumir que há cartas que já estão nas deckboxes
> dos decks.» — André, 14:30

## O defeito

O `noutra` de uma linha responde *"de que caixa é esta cópia"* — uma pergunta de
**alocação**, decidida por prioridade. A página lia-o como *"onde é que ela
está"*. Com a `copy_allocation` **vazia** (o estado da base nesse dia), as **70**
cópias que a Deckboxes chamava *"ir buscar a outra caixa"* estavam **todas na
`Colecção`**, na prateleira, e a página mandava-o procurá-las dentro de caixas
que ainda não existem na estante.

É o padrão do `event_tier`: um número certo a responder a outra pergunta, sem um
único erro em passo nenhum.

## O que mudou

**1. O `noutra` parte-se em três, e as três somam-no sempre** (`loadout`):

| chave | quer dizer | frase |
|---|---|---|
| `noutra_montada` | há linha na `copy_allocation` daquela caixa para aquela cópia | *"1× em UW Replenish"* |
| `noutra_reservada` | a alocação prometeu-a por prioridade; está na gaveta (`noutra_onde` diz qual) | *"3× na Colecção — destinada a UW Replenish (prioridade)"* |
| `noutra_futura` | ninguém a tem: é uma compra partilhada de outra caixa | *"1× depois de Enchantress comprar"* |

A frase escreve-se **num sítio só** — `loadout.onde_esta(linha, so=None)`. Cada
página compunha a sua a partir do `noutra`, e por isso todas mentiam ao mesmo
tempo. O `deckboxes.html` recebe-a pronta no payload (não a recompõe em
JavaScript, pela mesma razão que não decide o que é foil); o `metagame.py` e o
CLI chamam-na.

**2. Um bloco passou a três.** Na página, no `metagame.html` e no `loadout <deck>`
do CLI: *ir buscar a outra caixa* / *na gaveta, destinadas a outra caixa* /
*outra caixa vai comprá-las*. Os contadores do cabeçalho e do resumo idem
(`nmont` / `nres` / `nfut`, e `noutra_*_total` no relatório). Só o primeiro é uma
ida a outra caixa.

**3. Montar fora de ordem.** Se ele abre a Enchantress antes do UW Replenish, as
cartas que o Replenish há-de levar estão ali ao lado. O painel *Montar* mostra-as
num bloco próprio — **⚠️ destinadas a outra caixa** — e **por marcar**: tirá-las
é uma decisão (a outra caixa passa a vir buscá-las aqui), não uma consequência de
abrir a aba. Só o que ele marca vai no *"sleevado e na caixa"*, e a partir daí a
**`copy_allocation` manda sobre a prioridade**: a corrida seguinte vê a cópia
dentro desta caixa e a outra passa a dizer *"em Enchantress"* — que aí é verdade.

**4. Arrumar.** Nunca teve este defeito (o `de` de um movimento já era
`lot["local"]`, que é físico) e agora tem teste. O `de_outra` fica **fora** do
`plano_arrumacao` e do `copias` do painel: duas listas para dois gestos, e
somá-las contava a mesma cópia duas vezes.

## Medido (mesma `vault.db`, antes e depois)

A alocação **não mexe**:

| | antes | depois |
|---|---|---|
| fechar tudo | 8 426,34 € | **8 426,34 €** |
| a comprar | 232 | **232** |
| destinadas a outra caixa | 70 | **70** |
| a arrumar | 570 | **570** |
| venda | 243c / 1 621,76 € + 41 RL / 3 442,20 € | **igual** |

O que muda é a **leitura** das 70:

* **0** estão dentro de uma caixa (a `copy_allocation` está vazia);
* **56** estão na gaveta, destinadas a uma caixa por montar;
* **14** ainda ninguém as comprou.

As 56 aparecem agora no painel *Montar* da caixa que as quer — Enchantress 20,
Ill-Gotten Gains 16, Elves / Survival 12, Oath of Druids 4, Modern 3, UW
Replenish 1 — e ele pode tirá-las já.

Exemplos reais do payload:

```
Enchantress  · Replenish            3× na Caixa RL (PT) — destinada a UW Replenish (prioridade)
Enchantress  · Opalescence          1× na Caixa RL (PT) + 2× na Colecção — destinada a UW Replenish (prioridade)
Oath of Druids · Swords to Plowshares  1× depois de UW Replenish comprar
```

## Verificação

* `tests/test_onde_fisico.py` — 7 casos: destino ≠ físico; a `copy_allocation`
  muda a frase; montar fora de ordem (ele tira a carta para a Caixa B e a Caixa A
  passa a *"em Caixa B"*); marcar só regista o que o painel oferecia; Arrumar sem
  caixas fantasma; o HTML desenhado pelo browser não diz *"em Caixa A"*; e o
  `_estado_carta` (o outro caminho, o do `foil_report`) parte o `noutra` da mesma
  maneira.
* **Bateria 31/31 verde.**
* Preview regenerado em `C:\Users\Catarina\_revisao\_site-fisico`; as 21 abas
  desenham sem erro no `node` (42 renders).
* Verificadores em `ai-pc\work\revisao\_fis_ver.py` e `_fis_preview.py`: com a
  `copy_allocation` como está, **nenhuma página diz "em &lt;caixa&gt;"** e o
  painel *Montar* só manda tirar de `Colecção` / `Caixa RL (PT)` / `Caixa RL (EN)`.

## O que fica por fazer

Quando o André carregar em **«✅ Sim, está montada assim»** no Stiflenought, a
`copy_allocation` passa a ter as cartas dele e o *"em Stiflenought"* passa a ser
verdade — hoje, uma das linhas do UW Replenish já diz *"1× na Colecção —
destinada a Stiflenought"*, que é o estado certo até esse clique.
