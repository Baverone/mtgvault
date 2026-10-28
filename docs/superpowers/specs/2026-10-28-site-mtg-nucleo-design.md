# Site do MTG: o núcleo novo (desenho)

28/10/2026. Combinado com o André na conversa desse dia (esboços em
`scratchpad/mtg-redesign`). Opção **A**: um núcleo novo e pequeno dentro do
mtgvault; se ele não gostar do resultado, refaz-se de raiz.

## Para que serve

O site responde a quatro perguntas e a mais nada:

1. Que decks tenho?
2. O que falta a cada um?
3. O que tenho a mais e posso vender?
4. Como evolui o valor do que tenho?

Tem de ser bonito e simples, e funcionar bem no telemóvel à frente das caixas.

## Os decks (14)

| Modo | Formato · deck | Lista |
|---|---|---|
| Sempre montado | Pauper · Affinity | vigiada: LuffydoChapeuDePalha (MTGO) |
| Sempre montado | Premodern · Stifflenough | vigiada: LuffydoChapeuDePalha (MTGO) |
| Sempre montado | Premodern · UW Replenish, Enchantress, Elves, Ill-Gotten Gains, Oath of Druids | fixa |
| Sempre montado | cEDH · Blue Farm | vigiada: moxfield.com/decks/7O1sCuIti0igU6Us_Jhadg |
| Sempre montado | cEDH · Cloud | vigiada: moxfield.com/decks/k6f2yED7oUGPtK2_rN_xwg |
| Sempre montado | Duel Commander · Cloud | fixa |
| Rotativo | Pioneer · Greasefang | fixa |
| Rotativo | Modern · Affinity (Kappa), Oswald | fixa |
| Rotativo | Legacy · Welder Cam | fixa |

- Não se aproveitam listas antigas. As fixas nascem vazias («à espera da tua
  lista»). As vigiadas vão buscar a lista atual à fonte no primeiro dia.
- Os formatos dos modos: Premodern, cEDH, Pauper e Duel Commander são sempre
  montados; Standard, Pioneer, Modern e Legacy são rotativos. Um deck novo
  destes formatos herda o modo.

## Regras

- **Uma carta é uma edição e um acabamento** (normal ou foil). Só conta como
  «tenho» a edição escolhida. Sem escolha, vale a edição normal mais barata
  com preço. A língua não entra nas contas.
- **Uma escolha por carta e por deck:** quando o André escolhe a edição de uma
  carta, todas as cópias dessa carta nesse deck passam a ser dessa edição e
  desse acabamento (não há 2 de uma edição e 2 de outra). Outro deck pode ter
  outra edição da mesma carta. Mudar a escolha não apaga o que estava
  marcado: as cópias da edição antiga passam para «Vender» em «trocaste de
  edição», para ele decidir.
- **Completo inclui o sideboard** (e o comandante, no Commander).
- **Sempre montados:** cada deck tem as suas cópias. Falta = o que o deck pede
  menos o que esse deck tem.
- **Rotativos:** só um montado de cada vez, no total dos quatro formatos.
  - Uma carta (pelo nome) é **partilhada** se aparece em dois ou mais decks
    rotativos; senão é **fixa** desse deck.
  - As fixas vivem na caixa do deck; as partilhadas formam um monte e andam
    com o deck montado.
  - Precisas, de cada partilhada, do máximo que um deck rotativo pede.
  - A edição de uma partilhada escolhe-se uma vez para todos os rotativos
    (são as mesmas cópias físicas a andar de caixa em caixa); as fixas
    escolhem-se deck a deck, como nos sempre montados.
  - Falta = fixas em falta desse deck + partilhadas abaixo do que esse deck pede.
  - «Montar este deck» diz o que trazer de que caixa (as partilhadas que
    estão na caixa do deck montado antes).
- **Versões das listas (todos os decks):** cada lista guardada é uma versão
  com data, fonte (link, conta de Twitter, evento…) e o que entrou e saiu em
  relação à anterior. Nas fixas a fonte é perguntada ao André (no modo de
  edição, campo «de onde veio»; na conversa, o Claude pergunta). Nas vigiadas
  a fonte é o evento do MTGO ou o link do Moxfield.
- **Lista vigiada que muda:** a versão nova entra sozinha; as cartas novas
  aparecem a cinzento; as cartas que saíram e estavam marcadas passam para
  «Vender» em «saíram do deck X».
- **Tenho a mais:** carta, edição, acabamento e quantidade, escritos pelo André.
- **Valor:** soma de tudo o que tens (decks + tenho a mais), cada cópia uma
  vez, ao preço da sua edição em cada dia.
- **Preços:** Cardmarket trend por edição (Scryfall), em euros, `finish`
  `nonfoil`/`foil`. Correção de 28/10: fora a Reserved List, o `price_history`
  só tem a Cardmarket desde ~26/09 e o `podar-precos` apaga o que passa de 30
  dias. Por isso o núcleo guarda o **valor de cada dia** numa tabela própria
  (`n_valor`, nunca podada); para os dias antes do primeiro registo, o gráfico
  calcula o valor do que tens hoje aos preços que ainda houver (~1 mês).

## Dados

Tabelas novas no `data/vault.db`, prefixo `n_`, criadas por migração:

- `n_deck` — slug, nome, formato, modo (`sempre`/`rotativo`), vigiado (fonte
  `mtgo:<jogador>:<formato>` ou `moxfield:<id>`, ou nada), arte.
- `n_versao` — deck, número, data, fonte (texto livre), origem
  (`andre`/`vigia`), e as linhas da lista (`n_versao_carta`: secção
  main/side/comandante, nome, quantidade).
- `n_edicao` — a edição escolhida: (âmbito, nome) → scryfall_id + acabamento.
  Âmbito = slug do deck nos sempre montados; `rotativos` nas partilhadas.
- `n_posse` — o que tens: (âmbito, scryfall_id, acabamento) → quantidade.
  Âmbito = slug do deck nos sempre montados e nas fixas dos rotativos;
  `rotativos` nas partilhadas.
- `n_montado` — o deck rotativo montado agora (uma linha).
- `n_a_mais` — scryfall_id, acabamento, quantidade, nota.
- `n_saida` — cópias marcadas que deixaram de servir um deck: saíram de uma
  lista vigiada, ou ficaram de uma edição que o André trocou (deck, motivo
  `saiu_da_lista`/`trocou_edicao`, versão, scryfall_id, acabamento,
  quantidade).

Quando uma carta passa de fixa a partilhada (ou o contrário) porque mudou uma
lista, a posse muda de âmbito com ela, no mesmo passo que grava a versão.

## O que se aproveita e o que se desliga

- **Aproveita-se (sem mexer):** o catálogo da Scryfall (cartas e edições,
  imagens por URL), o `price_history`/`price_latest` da Cardmarket, a leitura
  de listas do MTGO por jogador e o `moxfield.fetch_deck`, e a casca do site
  (`site_shell`: cores, letra, ícones).
- **Desliga-se por interruptor (o código fica):** as páginas antigas saem da
  publicação e do menu (deckboxes, arrumação, metagame, cobertura, showcase,
  binders, galeria, Reserved List, comandantes, faltas); a recolha das listas
  de torneio que só servia o metagame; as «caixas» antigas.

## Páginas

Menu com três entradas: **Painel · Decks · Vender**.

1. **Painel** (`index.html`): valor do que tens, variação do mês, gráfico
   (1 mês · 3 meses · tudo; só uma linha, o que tens); os decks em «Sempre
   montados» e «Rotativos», com a arte (Scryfall `art_crop`) e a barra de
   progresso; a caixa «Vender» com o total.
2. **Deck** (`deck.html#<slug>`, 14 numa página só — a casca e os testes só
   aceitam páginas na raiz; sem `#` mostra a lista dos decks): cabeçalho (progresso, quanto falta em €,
   versão, fonte, o que mudou na última versão, «ver versões»); as cartas em
   imagens, a cores as que tens e a cinzento as que faltam, com a quantidade;
   nos rotativos em duas partes, **Fixas deste deck** e **Partilhadas** (cada
   uma diz onde está: aqui / no deck X / falta N) e a caixa «para montar
   este». Um deck fixo sem lista mostra «à espera da tua lista».
3. **Vender** (`vender.html`): Tenho a mais + saíram dos decks vigiados +
   trocaste de edição, preço de cada carta e o total.

**Modo de edição** (o servidor do porto 8771, também em editar-mtg.baverone.com
atrás do Cloudflare Access): as mesmas páginas com controlos — tocar numa
carta abre a escolha da edição: as edições lado a lado com imagem e preço, e
um interruptor **Normal / Foil** (só aparecem as opções que existem nessa
edição; o preço muda para o trend foil da Cardmarket quando é foil, e a carta
foil leva um brilho na página do deck) — e «Tenho +1 / −1»; colar uma lista nova com «de onde veio»;
«montar este deck» nos rotativos; acrescentar e tirar cartas em Vender.

## Recolha diária (03:30, tarefa `mtgvault-daily` do ai-pc)

Preços (Scryfall bulk, Cardmarket trend) → listas vigiadas (MTGO do Luffy:
Pauper e Premodern; Moxfield: o ficheiro mais recente da `mtg-moxfield-chrome`)
→ versões novas se mudaram →
valor do dia → páginas. Sem as listas de torneio, deve passar de ~20 min para
poucos minutos.

- Uma fonte que falha deixa a tarefa vermelha no ai-pc e a página do deck diz
  «não consegui ver a lista desde dia X». Nunca em silêncio.
- **Moxfield:** o Moxfield recusa pedidos automáticos (403) e não se contorna
  isso (nada de `MOXFIELD_USER_AGENT` a fingir um browser). Lê-se como o
  guildstats do Tibia: uma tarefa nova do ai-pc, `mtg-moxfield-chrome`, abre
  os dois links **no Chrome do André** pela extensão Claude in Chrome, uma vez
  por dia (10:45, depois das tarefas do Tibia), lê a lista (de preferência o
  «Export» de texto do Moxfield, porque a página esconde cartas atrás de
  «+ N other») e escreve `work/moxfield/<data>.json` com as duas listas.
  Máximo 2 páginas por dia; pára em qualquer desafio do Cloudflare sem clicar;
  Chrome fechado = `sem_chrome` sem o abrir. A recolha das 03:30 do dia
  seguinte (ou um `mtgvault nucleo moxfield` à mão) lê esse ficheiro e grava
  versão nova se a lista mudou. Provado a 28/10: o Blue Farm abre e lê-se
  inteiro num browser normal.
- Sempre que um vigiado não se conseguir ler, o André pode colar a lista à
  mão no modo de edição (fica como versão de origem `andre`, com a fonte).

## Testes e publicação

- Testes novos na bateria do mtgvault (`py tests\_bateria.py`, com o
  `VAR_PROIBIDAS` armado; nunca a base real): regras dos dois modos, partilha
  e âmbitos, edição estrita, versões e diferenças, saídas para Vender, valor
  para trás com preços de exemplo, geração das páginas e o modo de edição
  (marcar, escolher edição, colar lista com fonte, montar).
- As guardas existentes da casca (`test_casca`, `test_tokens`) continuam a
  valer para as páginas novas; os testes das páginas desligadas passam a
  confirmar que estão fora da publicação.
- Publicação pelo caminho de sempre (`mtgvault-publicar`/`mtgvault-daily`).
  Mudam também, no ai-pc: a lista de páginas do `mtgvault-daily` e os passos
  do mtgvault no `e2e-sites` (painel com números, menu com 3 entradas, uma
  página de deck).
- Antes de dar por feito: ver no Chrome (desktop e iPhone) o painel, um deck
  sempre montado, um rotativo e Vender, publicado em mtg.baverone.com.

## Fora deste trabalho

- Registar a coleção (é o André, a marcar no modo de edição).
- Dar as listas dos decks fixos (o André, quando quiser; o Claude pergunta a
  fonte).
- Apagar código antigo.
