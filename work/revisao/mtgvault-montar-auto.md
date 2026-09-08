# Barra de montagem: marcar as cartas todas é dizer que o deck está montado

2026-09-08 · ramo `ai-pc/montar-auto-2026-09-08`

## O pedido

> *"Não é mais fácil confirmares que eu seleccionei todas as cartas do deck, e
> assim eu confirmo que montei o deck?"*

Ele estava à frente da estante, com o telemóvel, a marcar cartas — e não
encontrou o **«Sim, está montada assim»**. O botão existia; ficava no **fim de
58 linhas** do passo 1. Um botão que só aparece depois de um ecrã inteiro de
scroll é, na prática, um botão que não existe.

## O que passou a haver

**1. Uma barra fixa no fundo do ecrã** (`deckboxes.barraHTML`/`renderBarra`),
enquanto a aba de uma caixa está aberta e **só no modo edição**: *«Montar
<caixa>: N de M cópias marcadas»*, barra de progresso, o botão de registar e os
atalhos **marcar tudo** / **limpar**. No telemóvel a barra passa a duas linhas e
o botão ocupa a largura toda (`@media(max-width:640px)`), e o `.wrap` ganha
`padding-bottom` para as últimas cartas não ficarem por baixo dela.

No site publicado a barra **não se desenha**: lá o endpoint não existe, e uma
barra que conta cópias e não regista nada é pior do que barra nenhuma. É a mesma
regra dos botões, e o harness de node prova-a.

**2. Marcar a última = montada.** Quando a última checkbox do passo 1 fica
marcada (main + sideboard + as básicas que estão registadas na base), a barra
fica verde e o registo faz-se sozinho — `montar.auto_registar`, omissão `true` —
com um aviso de `montar.anular_segundos` (6) e o **anular** ao lado. Com
`auto_registar: false` a barra fica verde e mostra só o botão grande.

Só quando ele **acaba de marcar**: abrir a aba com tudo já marcado de ontem não
escreve nada, e o *marcar tudo* também não — é um atalho para depois desmarcar
duas ou três, não uma afirmação sobre a estante.

**3. Registo parcial** (`loadout.registar_marcadas`, acção `registar`). Com
algumas marcadas o botão diz *«Registar as N marcadas»* e grava só essas; as
outras continuam em *"tirar da colecção"*. A caixa **sobe a `permanente`, nunca
a `montada`**, e ganha o crachá *«N de M na caixa»*. Uma caixa monta-se aos
poucos — ele tira dez cartas, o telefone toca, volta amanhã. Até aqui só havia
tudo-ou-nada: ou dizia que estava montada (a mentir sobre as outras 40) ou não
dizia nada e no dia seguinte procurava as dez outra vez.

**4. Os vistos continuam no aparelho**, e ao registar limpam-se **só os daquela
caixa** — a partir daí quem diz o que está lá dentro é a `copy_allocation`.
Voltam com o *anular*: desfazer o registo e deixá-lo com a grelha limpa era
pedir-lhe que marcasse 58 cartas outra vez.

## Duas decisões que vale a pena não repetir

**O `anular` não é um `desmontar`.** Repõe a `copy_allocation` e o `estado`
exactamente como estavam, de uma fotografia tirada antes da escrita
(`webapp._ULTIMO_REGISTO`, uma por caixa, em memória) — **sem backup**, porque
não apaga nada: é o inverso de uma escrita de há segundos. Quem apaga o que ele
confirmou à mão é o **Desmontar**, e é por isso que esse tem backup e uma linha
no `data/desmontar.log`. O servidor aceita o anular durante 120 s (o botão só
está à vista 6): um clique ao segundo 5,9 num telemóvel na rede de casa não pode
falhar por causa da latência.

**Quem decide que a caixa está completa é a base, nunca o browser.** O `falta`
sai de `movimentos_de_entrada` menos o que ele marcou; os `feitos` vivem no
`localStorage` e podem ser de uma alocação de ontem. E o registo **sobe, nunca
desce**: uma caixa que já se diz montada não usa o `montado` (esse **alterna**, e
alterná-lo aqui **desmontava-a** — que é o contrário do que o botão diz), usa o
`registar`.

## O id de um "visto" passou a estar num sítio só

Era escrito à mão em três (`mt|`, `bs|`, `mo|`), e agora é o `deckboxes.vistoId`.
A grelha desenha-o, a barra conta por ele e o registo manda os `copy_id` que ele
traz: bastava mudar uma barra vertical num dos três para a barra passar a dizer
*"0 de 58"* com 58 cartas por baixo, **sem um único erro**. É o padrão do
`event_tier` do lado do browser.

Pela mesma razão o que é de **outra caixa** não conta para o M: o bloco
«destinadas a outra caixa» continua a marcar-se e a registar-se, mas esperá-lo
era impedir esta caixa de fechar por causa de cartas que são de outra. As básicas
**a granel** ficam fora pelo mesmo motivo — não têm cópia registada, não têm nada
para marcar.

## Ficheiros

| | |
|---|---|
| `mtgvault/loadout.py` | `registar_marcadas`, `linhas_parciais`, `restaurar_alocacao`, `alocacao_da_caixa`; `regras_montar`/`montar_auto_registar`/`montar_anular_segundos`; `plano_montar` ganhou `marcar_q` e `dentro` |
| `webapp.py` | acções `registar` e `anular`; `registar_parcial`, `anular_registo`, `_ULTIMO_REGISTO` |
| `deckboxes.py` | `vistoId`, `montarItens`, `montarEstado`, `deOutraMarcadas`, `barraHTML`, `renderBarra`, `ligarBarra`, `registar`, `avisoRegisto`, `anularRegisto`, `limparFeitos`, `autoRegistar`, `actoDeRegisto`; crachá *«N de M na caixa»*; CSS `.barra`/`.toast.aviso` |
| `colecao_config.json` | chave `montar` (+ `_montar` a explicar porquê) |
| `tests/render_deckboxes.js` | um elemento por selector (o dump passa a ler o `#vista`, e a barra em `barra:<aba>`); semeia os *vistos* no `localStorage` |
| `tests/test_montar_barra.py` | 9 casos |

## Medido (a mesma `vault.db`, antes e depois)

A alocação **não mexe**:

| | antes | depois |
|---|---|---|
| fechar tudo | 8 426,34 € | **8 426,34 €** |
| comprar | 232 | **232** |
| ir buscar a outra caixa | 70 | **70** |
| arrumar | 438 | **438** |
| venda | 239 c / 1 586,67 € | **239 c / 1 586,67 €** |
| venda RL | 41 c / 3 442,20 € | **41 c / 3 442,20 €** |

O que a barra passa a dizer, por caixa (verificado no HTML que ela desenhou,
`_preview_montar.py` sobre a base a sério): Blue Farm **93**, Cloud (DC) **75**,
Cloud cEDH **60**, UW Replenish **59**, Modern — UW Oswald **49**, Oath of Druids
**36**, Elves / Survival **22**, Enchantress **17**, Ill-Gotten Gains **17**,
Pioneer — Greasefang **10**. O **Stiflenought** e o **Pauper** não têm barra: já
não há nada por marcar neles. O Standard e o Legacy também não — ainda não têm
deck escolhido.

Com tudo marcado no Blue Farm, a barra diz *«93 de 93 cópias marcadas · tudo
marcado»*, `data-estado="cheia"` e o botão **✅ Registar como montada**.

## Testes

`tests/test_montar_barra.py` (novo): a contagem da barra é a das checkboxes que a
grelha desenhou; o registo parcial grava só o marcado e sobe a `permanente`;
marcar tudo passa a `montada`; o *anular* repõe a alocação e o estado do gesto
anterior **e só uma vez**; o que é de outra caixa não tranca o «N de M»; o
`auto_registar` sai do config; a barra desenha `0 de 6 → 3 de 6 → 6 de 6` (a
marca do meio é o **lote de 3 Island**, para uma contagem por linhas não passar);
a barra não existe no site publicado; e o caminho todo pelo handler HTTP, com
403 sem token.

Bateria completa: **32 ficheiros, TUDO OK**.
