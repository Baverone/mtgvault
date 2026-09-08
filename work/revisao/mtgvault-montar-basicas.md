# Terrenos básicos no painel Montar — 2026-09-08

> *"Faltou marcares, para completar o deck, os terrenos básicos necessários!"*
> — André, 2026-09-08
>
> *"Todas as minhas lands básicas são de Unhinged, em inglês, foil ou não foil."*
> — André, 2026-09-08, 13:58

## O que estava mal

Uma básica entrava na alocação com `got == need` e `lotes == []`: contava-se como
tida e **não aparecia em lado nenhum**. O Stiflenought montava-se, no painel
Montar, sem uma única terra — e o painel é a folha que ele leva para a frente da
estante. Não dava erro: dava um deck a menos 17 cartas.

## O que passou a haver

**`mtgvault/loadout.py`**

* `_aloca_basica` — as cópias de básicas que ESTÃO na `copies` entram na alocação
  como qualquer outra carta (`lotes`), por isso dizem de que gaveta sair e entram
  na arrumação. O que a colecção não tem fica em `granel` (a pilha de Unhinged) ou
  em `por_comprar` (só as Snow-Covered).
* `_serve_basica` / `_ordem_basica` — **isenção das regras de material**
  (`basicas.isentas_de_regras`, default `true`): a pilha dele é toda Unhinged EN,
  e trancar o Premodern ao PT mandava comprar 17 Island que estão ali ao lado. Nas
  caixas de foil a foil vai à frente, mas é **preferência e não requisito** — uma
  Island non-foil fecha o slot na mesma. Continua a valer o que não é material:
  cópia livre, não reservada a outro deck, e não sleevada dentro de outra caixa.
* `_basicas_do_slot` → `s["basicas"]` e `plano_basicas` → o bloco pronto a mostrar.
  Fica em chave **própria**, nunca no `missing`: enfiá-lo lá mexia no `comprar`, no
  `custo` e na partilha de compras de todas as caixas.
* `requisito_basicas(s)` — o material de uma básica é **só o acabamento**. Dizer
  *"PT · ≤SCG"* numa linha de Island era pedir-lhe o que a alocação não exige.
* `plano_montar` devolve `basicas` à parte de `tirar`: a grelha do passo 1 está
  ordenada por COR, que é como o binder está arrumado — a pilha de básicas não vive
  lá.
* `res["basicas_comprar_total"]` / `res["basicas_custo_total"]`, **fora** do
  `comprar_total`/`custo_total`. Somá-los fazia o *"fechar tudo por X €"* mudar por
  causa de cartas que ele já pode ter em casa — e é esse o número por que decide.

**`deckboxes.py`** — bloco **🌱 Terrenos básicos** no passo 1 do painel Montar,
depois das cores, com três estados por linha: as que a colecção tem e ainda não
estão na caixa (checkbox, como as outras), as que já lá estão, e as que vêm da
pilha (sem `copy_id`, nada para marcar). Na aba **Comprar**, bloco próprio para as
básicas a comprar, marcado *confirma se já tens*, com o selector por caixa a
funcionar. No texto copiado, um bloco `// Basicas` **comentado** — o Cardmarket
ignora as linhas com `//`, e 17 Island a sério no carrinho era comprar terras que
ele tem em casa; o que é mesmo compra vai em linha normal.

**`mtgvault/cli.py`** — secção `TERRENOS BÁSICOS` no `loadout <deck>` e o mesmo
bloco `// Basicas` no fim da wantlist. Sai do MESMO `plano_basicas` da página.

**`colecao_config.json`** — chave `basicas` (`isentas_de_regras`,
`comprar_se_material_especial`, `edicao`, `compram_se_faltarem`) com o `_basicas`
a explicar porquê. Os defaults do código são iguais aos do config.

## Medido (mesma `vault.db`, antes e depois)

|  | antes | depois |
|---|---|---|
| fechar tudo | 8 426,34 € | **8 426,34 €** |
| a comprar | 232 | **232** |
| a ir buscar | 70 | **70** |
| venda | 118 c / 1 621,76 € | **118 c / 1 621,76 €** |
| venda RL | 19 c / 3 442,20 € | **19 c / 3 442,20 €** |
| guardar / reservadas | 4 / 17 | **4 / 17** |
| a arrumar | 535 | **570** |
| básicas a comprar | — | **0 c / 0,00 €** |

O **único** número que mexe é a arrumação: **+35 cópias**, que são exactamente as
básicas registadas na base a passarem a ter caixa — 12 Plains (ODY, EN, nonfoil) e
23 Snow-Covered Plains (MH1, EN, foil).

O que o painel passa a dizer, por caixa:

| caixa | básicas | de onde |
|---|---|---|
| Stiflenought | 17 Island | 17 da pilha (Unhinged) |
| UW Replenish | 5 Island · 5 Plains | 5 Plains da Colecção, 5 Island da pilha |
| Oath of Druids | 2 Forest · 1 Plains | 1 Plains da Colecção |
| Enchantress | 6 Forest · 2 Plains | 2 Plains da Colecção |
| Ill-Gotten Gains | 5 Island · 3 Swamp | da pilha |
| Elves / Survival | 6 Forest · 1 Mountain · 1 Plains | 1 Plains da Colecção |
| Cloud cEDH | 10 Plains (non-foil) | 3 da Colecção, 7 da pilha |
| **Cloud (Duel Commander)** | **23 Snow-Covered Plains (foil)** | **23 da Colecção [MH1 ✨]** |
| Pauper (Luffy) | 1 Mountain (foil se houver) | da pilha |
| Modern / Pioneer | 2 Island · 1 Forest/Plains/Swamp (foil) | da pilha |

**Nada vai à lista de compras.** A única básica que se compraria são as
Snow-Covered — e ele tem 29 registadas em MH1 foil, mais do que as 23 que o Duel
Commander pede. O caminho da compra está testado, não está a disparar.

## Testes

`tests/test_basicas.py` (novo, 8 casos): o bloco com as quantidades dele
(Stiflenought 17 Island, DC 23 Snow-Covered Plains foil); as básicas registadas a
alocarem-se e a dizerem a gaveta; a isenção das regras (uma Island de Unhinged EN
numa caixa `estrita` de Premodern) **e** a tranca a continuar inteira para o que não
é básica; a foil primeiro mas a non-foil a fechar o slot; o material especial a ir
para Comprar e **nunca** ao `comprar_total`; a percentagem intocada; 40 Island a
mais a darem zero linhas de venda. Mais o HTML que o browser **desenha** (harness
de `node`), incluindo o `// 17 Island (na coleccao)` do texto copiado.

Bateria completa: **29/29 verde**.
