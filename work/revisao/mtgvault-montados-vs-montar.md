# Deckboxes: «Decks montados» e «Decks para montar» — 2026-09-08

Ramo `ai-pc/montados-vs-montar-2026-09-08`, worktree
`C:\Users\Catarina\_revisao\mtgvault-montados`. Bateria toda verde (31
ficheiros, um novo), preview refeito e `_ver_montados.py` a passar sobre a base
a sério.

> *"No mtgvault, quero decks montados num botão específico, e um botão a dizer
> «decks para montar», para poder separar as coisas."* — André, 2026-09-08

## Porque é que são dois botões e não um filtro

São duas perguntas diferentes, e ele está à frente da estante quando faz cada
uma. Com a caixa na mão pergunta *o que está aqui dentro* e *quando é que a
montei* — e às vezes quer desmontá-la. Com a caixa por montar pergunta *o que
tiro da colecção* e *o que compro*. A aba *Todas* junta as catorze por
prioridade de alocação, que é a resposta a uma terceira pergunta.

## O que passou a haver

**A linha que separa é o `estado`** — `montada`/`congelada` de um lado, tudo o
resto do outro. Cada caixa está numa vista **e só numa**, e o cabeçalho abre com
os dois números:

    1 montados · 13 para montar · 14 caixas (5 permanentes · 9 candidatas) · …

Os dois vêm do Python (`resumo.montados` / `por_montar`, novo) e **somam sempre
o total de caixas**. É a parte que vale um teste: uma caixa que caísse fora das
duas vistas desaparecia da página sem um único erro — o padrão do `event_tier`,
do lado do browser.

**O cartão é o mesmo da vista Todas** (`caixaHTML(c, true)`). A caixa não pode
dizer 61 % num sítio e outra coisa no do lado. O que muda é a barra por baixo:

| vista | por baixo do cartão |
|---|---|
| ✅ Decks montados | *«📅 montada em 2026-09-05»* + **🧹 Desmontar** (só em modo edição) |
| 🔧 Decks para montar | **🧱 Montar** (abre o painel Montar da caixa) + *tirar N · comprar N · X €* |

Os botões ficam **fora** do `<button class="mini">` que é o cartão: um botão
dentro de outro não é HTML válido, e o clique de dentro disparava também a
navegação de fora.

**A data sai da `copy_allocation`** — `loadout.datas_de_arrumacao`, novo, o
`MAX(placed_at)`. É o máximo e não o mínimo porque quem grava
(`guardar_arrumacao`, `actualizar_caixa`) substitui as linhas da caixa inteira
de uma vez: a data que se pode afirmar é a da última vez que ele disse o que lá
está, não a de uma cópia em particular.

**E uma caixa que se diz montada e de que o vault não sabe o conteúdo não ganha
data nenhuma.** É exactamente o caso de hoje — o **Stiflenought** é o único
montado e tem zero linhas na `copy_allocation`. A vista diz-lho:

> ❓ montada, mas ainda não me disseste o que lá está — abre a caixa e confirma

Inventar-lhe o dia de hoje era assinar por ele uma confirmação que ele nunca
fez, que é o mesmo defeito do `event_tier`: um valor plausível onde devia estar
um *"não sei"*.

**A ordem da vista de montar é a do Plano** (`ordem_de_montagem`): permanentes
primeiro, depois as candidatas pela percentagem que já têm. Reordená-la aqui
dava duas respostas a *"por onde começo?"*. As caixas **sem deck escolhido**
(Standard e Legacy) não estão no `montagem` — não há o que montar até ele
escolher — e vêm no fim, no grupo **Por escolher**, com a etiqueta a dizer
porquê.

**As abas individuais de cada deck mantêm-se**, agrupadas: as montadas à cabeça
com o **ponto verde**, um separador, e depois as que faltam. O ponto verde tem
anel para não se confundir com o verde de *"90 % ou mais"* de uma caixa que
ainda falta montar — a percentagem continua no subtítulo, que é onde ela ainda
quer dizer alguma coisa. Antes as abas vinham pela ordem da alocação e a caixa
que está na estante aparecia no meio das que ainda não existem.

## Duas coisas pequenas que vinham no caminho

- **O subtítulo da aba *Plano* deixou de trazer contagem** (é *"por onde
  começar"*). O `D.montagem` só tem as caixas com lista: *"11 por montar"* ali e
  *"13 por montar"* no botão do lado eram as mesmas palavras com dois números —
  o defeito que os dois botões vêm corrigir.
- **A aba *Sugestões* faltava na lista de abas válidas do arranque.** Quem
  deixasse a página aberta nela e recarregasse caía no *Plano*, sem erro.
  Uma palavra na mesma lista que já estava a ser editada.

## Medido (a mesma `vault.db` de 2026-09-08, antes e depois)

| | antes | depois |
|---|---|---|
| fechar tudo | 8 426,34 € | **8 426,34 €** |
| a comprar | 232 | **232** |
| a ir buscar | 70 | **70** |
| a arrumar | 570 | **570** |

**Nada no motor mexeu** — só se acrescentou uma leitura (`datas_de_arrumacao`) e
duas vistas. Os números são os que a tarefa dos terrenos básicos deixou.

O que a página passa a dizer:

- **montados (1):** Stiflenought — sem data, a pedir confirmação do conteúdo;
- **para montar (13):** UW Replenish · Oath of Druids · Enchantress ·
  Ill-Gotten Gains · Elves / Survival · Blue Farm · Cloud cEDH ·
  Cloud (Duel Commander) · Pauper (Luffy) · Modern — UW Oswald ·
  Pioneer — Greasefang, e depois **Por escolher:** Standard · Legacy.

## Testes

`tests/test_montados.py` (novo, 5 casos, quatro caixas de mentira — uma montada
com conteúdo, uma montada por confirmar, uma permanente e uma candidata):

1. cada caixa numa vista e só numa, e `montados + por_montar == nº de caixas`;
2. **mudar o estado move a caixa de lado** (montar e desmontar), com os
   contadores a acompanhar — sem isto os dois botões diziam a verdade no dia em
   que foram escritos e mentiam a partir do primeiro clique;
3. a data vem da `copy_allocation`, e a caixa sem linhas lá dentro diz que falta
   confirmar em vez de mostrar um dia;
4. **Desmontar** só no modo edição (o publicado não desenha nenhum `data-act`),
   **Montar** nos dois — é navegação, não escrita;
5. a fila de abas mantém uma aba por caixa, agrupadas, com o ponto verde nas
   montadas e os dois separadores.

O harness `tests/render_deckboxes.js` passou a desenhar também as duas abas
novas e a guardar a **fila de abas** em `__fila`: a fila é a primeira coisa que
ele vê e não aparecia em nada do que se desenhava, por isso a ordem e os grupos
não se podiam verificar.

Bateria completa: **31/31 verde**.

## Preview e verificador

`work/revisao/preview/deckboxes.html` e `-edicao.html` refeitos a partir de uma
**cópia** da `vault.db` a sério (o relatório grava ficheiros ao lado da base;
uma revisão não escreve no `vault.db` que o `daily` publica). O
`_ver_montados.py` confere sobre eles: os dois botões na fila a seguir a
Plano/Todas, a soma dos contadores, a ordem do Plano na vista de montar e o
grupo *Por escolher* no fim, o *«montada em»* / *«falta confirmar»*, **0 botões
de escrita no publicado e 1 Desmontar + 11 Montar no modo edição**, a fila
agrupada com o ponto verde, e o que a v6 já trancava (painel Montar nas 12
caixas com lista, QR só em modo edição).
