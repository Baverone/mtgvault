# mtgvault

Gestor da coleção de Magic: coleção, decks, wantlist, metagame e preços.
Python + SQLite, corre no teu PC, sem servidores nem serviços pagos.

---

## Instalação

```bat
cd C:\
git clone <o teu repo>  mtgvault      ::  ou copiar a pasta para C:\mtgvault
cd C:\mtgvault
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m mtgvault.cli init
python -m mtgvault.cli sync-cards
```

`sync-cards` descarrega o catálogo completo da Scryfall (~500 MB, uns minutos).
Chega correr uma vez por semana. Tudo o resto depende dele: é ele que traz o
`cardmarket_id` de cada impressão, que é a ponte para os preços.

**São duas bases de dados, de propósito:**

| Ficheiro | Conteúdo | Vai para o Git? |
|---|---|---|
| `vault.db` | coleção, decks, decklists, preços, watchlist | sim |
| `catalog.db` | catálogo Scryfall (~500 mil impressões) | não |

O catálogo passa dos 100 MB por ficheiro que o GitHub aceita, e é reconstruível
a qualquer momento — por isso fica de fora e vive na cache do Actions.
Caminhos: `MTGVAULT_DB`, `MTGVAULT_CATALOG`, ou `--db` / `--catalog`.

---

## Entrada de cartas

### Uma a uma

```bat
python -m mtgvault.cli add "Ragavan, Nimble Pilferer" --set mh2 -q 2
python -m mtgvault.cli add "Lightning Bolt" --set 2ed --collector --sub "Unlimited"
python -m mtgvault.cli add "Force of Will" --set all --foil --condition EX
```

`--collector` marca o exemplar como **coleção de colecionador**: fica registado
e avaliado, mas **não conta** para decks nem para a wantlist. Sem essa flag, é
coleção de jogador.

### Em lote, por CSV (é assim que as fotos entram)

O fluxo com fotos é este:

1. Fotografas as cartas e guardas numa pasta, ex.: `C:\mtg\fotos\`
2. Envias-me as fotos aqui no chat
3. Eu devolvo-te as linhas CSV já preenchidas (nome, edição, número, foil, idioma, estado)
4. Colas num ficheiro e corres o import

```bat
python -m mtgvault.cli import C:\mtg\lote_2026-08-02.csv
```

Colunas aceites:

```csv
name,set_code,collector_number,quantity,finish,language,condition,purpose,sub_collection,photo_path,acquired_price,notes
Ragavan, Nimble Pilferer,mh2,138,1,nonfoil,en,NM,player,Modern,C:\mtg\fotos\IMG_0412.jpg,,
Black Lotus,lea,232,1,nonfoil,en,GD,collector,Alpha,C:\mtg\fotos\IMG_0413.jpg,,
```

**As fotos ficam no teu disco.** A base de dados guarda o caminho (`photo_path`),
não a imagem. Assim a BD fica leve e as fotos continuam a ser tuas, em ficheiros
normais que podes abrir, mover para o NAS ou copiar para a cloud.

---

## Os meus decks

```bat
python -m mtgvault.cli deck-add "Burn" modern C:\mtg\decks\burn.txt
python -m mtgvault.cli deck-status 1
python -m mtgvault.cli wantlist
```

O ficheiro de deck é texto normal, formato MTGO/Arena, com `Sideboard` a separar.

`deck-status` diz, carta a carta, quantas tens e quantas faltam, e quanto custa
fechar. Conta por **nome** — qualquer impressão serve para jogar — e ignora os
exemplares marcados como colecionador.

`wantlist` agrega todos os decks. Se três decks precisam de 4 Fatal Push, pede 4,
não 12 (assume que as partilhas entre decks).

### Cartas dedicadas a um deck

Por omissão, uma carta na coleção está disponível para todos os decks — se
tens 4 Fatal Push, os três decks que os querem "veem" os mesmos 4. Isso é o
correto para decks que não estão montados ao mesmo tempo.

Mas há decks que estão montados a sério, com as cartas fisicamente dentro
deles. Para esses:

```bat
python -m mtgvault.cli deck-reserve 3
python -m mtgvault.cli reservations
python -m mtgvault.cli deck-release 3
```

`deck-reserve` pega nos exemplares livres que o deck precisa e prende-os a ele.
A partir daí:

- os outros decks deixam de os contar (aparecem na wantlist deles)
- as listas padrão e o `report` também não os contam
- o próprio deck continua a vê-los, claro
- lotes são partidos quando preciso: se tens 4 Bolt e reservas 2, ficam 2 livres

Não mexe na coleção de colecionador, nem rouba cartas já dedicadas a outro deck.

---

## Metagame: cores e tech

```bat
python -m mtgvault.cli harvest --days 7 --format modern
python -m mtgvault.cli analyse modern --window 30
python -m mtgvault.cli archetypes modern
python -m mtgvault.cli cores 3
python -m mtgvault.cli gap 3
```

### Como é calculado o núcleo

Para cada carta dentro de um arquétipo:

```
core_copies = maior k tal que P(cópias >= k) >= 90%
```

O teu exemplo: carta em 100% das listas, 80% com 3 cópias e 20% com 4.

| | valor |
|---|---|
| P(>=3) | 100% → core |
| P(>=4) | 20% → não core |
| **core_copies** | **3** |
| **flex_copies** | 3.2 − 3 = **0.2** (a 4.ª é tech) |

Classificação final: `core` se core_copies >= 1; `flex` se aparece em >= 40% das
listas mas sem cópias garantidas; `tech` para o resto.

O core é sempre relativo à janela de tempo. Como cada execução grava a janela em
`card_roles`, ao fim de umas semanas consegues ver o núcleo a mexer — uma carta
que era tech a virar core é um sinal precoce de que o metagame mudou.

`gap 3` diz-te o que te falta para montar o núcleo desse arquétipo.
Com `--flex` inclui também as cópias flexíveis.

### Deteção de arquétipos

Clustering por semelhança de Jaccard sobre o mainboard (sem terrenos básicos),
limiar 0.55. Os nomes são gerados a partir das cartas mais distintivas — vais ver
`Skewer the Critics / Sacred Foundry / Monastery Swiftspear` em vez de `Burn`.
Podes renomear à mão na tabela `archetypes`.

### Cobertura por formato — lê isto

| Formato | mtgo.com | mtgtop8 |
|---|---|---|
| Standard, Pioneer, Modern, Legacy | sim | sim |
| Duel Commander | sim (Duel CMDR) | sim (`f=EDH`) |
| Premodern | sim | sim (`f=PREM`) |
| cEDH | não | sim (`f=cEDH`) |

As duas fontes são complementares e correm ambas no `daily.py`: o MTGO dá
volume online, o mtgtop8 dá os torneios de papel — que no Duel Commander e no
Premodern são a maioria — e é a única fonte para cEDH.

```bat
python -m mtgvault.cli harvest --days 2
python -m mtgvault.cli harvest-mtgtop8 duel-commander --events 8
```

### Porque é que não há mais fontes

O mtggoldfish e o mtgdecks são acessíveis, mas **não valem a pena**, e a razão
não é técnica.

São agregadores da mesma origem. As páginas do mtgtop8 dizem, à letra,
`Source: mtgo.com/decklist/...` nas listas de MTGO. O mtgdecks declara que
recolhe do MTGO, mtgtop8, mtgmelee e topdeck. Acrescentá-los traz sobretudo
**a mesma lista outra vez**.

E isso não é apenas inútil — é ativamente mau para a análise. Se as listas do
MTGO chegassem em triplicado e as de papel só em duplicado, o metagame ficava
enviesado para o online, e o `n` das estatísticas ficava inflacionado: o limiar
dos 90% do core pareceria muito mais bem sustentado do que estaria.

(O mtggoldfish tem ainda uma condição de utilização explícita a dizer que o
conteúdo original não pode ser reproduzido sem consentimento.)

### Deduplicação

Como o MTGO e o mtgtop8 se sobrepõem, cada lista é identificada pelo seu
**conteúdo**, não pela fonte:

    mesma lista = mesmo formato + mesmas cartas + mesmo dia + mesmo jogador

Quando há colisão, fica a fonte com maior prioridade:

| Prioridade | Fonte | Porquê |
|---|---|---|
| 4 | manual | foste tu que a meteste |
| 3 | mtgo.com | é a origem, publica primeiro e sem intermediário |
| 2 | mtgtop8 | re-hospeda MTGO, mas acrescenta o papel |
| 1 | mtggoldfish | agregador puro |

A ordem de chegada não importa: se o mtgtop8 entrar primeiro e o mtgo.com
depois, a versão do mtgtop8 é substituída.


O mtgtop8 tem export `.dec`, por isso não é preciso parsear o HTML das listas —
só o das páginas de índice. Nos formatos de comandante, o comandante vem na
linha `SB:` do `.dec` e é reencaminhado para o mainboard, que é onde conta
para as 100 cartas.

Os limites (8 eventos, 16 listas por evento) são por respeito: o mtgtop8 é um
site pequeno e gratuito, e há um segundo de espera entre pedidos.

**O mtgdecks.net não dá.** Bloqueia acesso automatizado com deteção de bots —
testado. Para uma lista de lá, copiar e usar `watch-paste`.

Para os três de baixo, `sources.store_manual()` aceita qualquer decklist em texto
e alimenta a mesma análise. O próximo passo natural é um scraper do mtgtop8
(Premodern e Duel Commander) e do topdeck.gg/EDHTop16 (cEDH).

---

## Baralhos vigiados (watchlist)

Há três tipos de baralho no sistema, e tratam-se de maneiras diferentes:

| Tipo | Fonte | Comando |
|---|---|---|
| Jogador específico do MTGO | as decklists já recolhidas | `watch-player` |
| Deck do Moxfield | api2.moxfield.com | `watch-moxfield` |
| Todos os outros | lista padrão calculada do metagame | `report` / `stock` |

```bat
python -m mtgvault.cli watch-player "NomeDoJogador" "Burn do Fulano" modern
python -m mtgvault.cli watch-moxfield https://moxfield.com/decks/aBc123 "O meu Legacy" legacy
python -m mtgvault.cli watch-list
python -m mtgvault.cli watch-check
python -m mtgvault.cli watch-diff 2
python -m mtgvault.cli watch-coverage 2
```

`watch-check` corre também no `daily.py`. Cada versão da lista fica guardada,
por isso `watch-diff` mostra exatamente o que entrou e o que saiu:

```
  2026-07-28  ->  2026-08-02
  board  card_name             before  after  delta
  main   Fury                       2      4      2
  main   Lava Spike                 4      2     -2
  side   Boil                       0      2      2
```

### Moxfield — lê isto antes de esperar que funcione à primeira

Os endpoints do Moxfield estão atrás da Cloudflare. A política deles é que
aplicações externas peçam ao suporte um **User-Agent autorizado**; sem isso
apanhas 403 mais cedo ou mais tarde. Disfarçar o User-Agent de browser é
precisamente o que eles estão a tentar travar, por isso não vou por aí.

```bat
set MOXFIELD_USER_AGENT=o-que-o-suporte-te-der
```

Entretanto, para meia dúzia de decks o modo manual resolve e não perde nada —
histórico e diff funcionam na mesma. No Moxfield: **Export → Text**, e depois:

```bat
python -m mtgvault.cli watch-paste 2 C:\mtg\decks\legacy.txt
```

### Jogadores do MTGO

`watch-player` não vai à rede: aproveita as decklists que o `harvest` já trouxe
e apanha a lista mais recente daquele login. Basta o harvest correr primeiro —
é o que o `daily.py` faz. Se o jogador não publicar nada há semanas, o
`watch-check` diz `sem listas ainda` em vez de inventar.

---

## Os outros decks: listas padrão e % que tenho

Para tudo o que não vigias explicitamente, o sistema constrói a lista de
consenso a partir do que o metagame anda mesmo a jogar.

```bat
python -m mtgvault.cli report modern
python -m mtgvault.cli stock 3 --coverage
```

`report` dá-te o ranking de todos os arquétipos do formato pela percentagem que
já tens na coleção:

```
  archetype_id  label                          n_lists  pct   have  missing  cost
  3             Ragavan / Urza's Saga / ...     41      78.7   59    16       142.30
  7             Karn Liberated / Urza's Tower   28      45.3   34    41       389.10
```

`stock <id> --coverage` mostra a lista completa e, a seguir, carta a carta o que
te falta e quanto custa.

### Como a lista padrão é construída

1. cada carta entra com as suas `core_copies` (o que se leva sempre)
2. os lugares que sobram são preenchidos por ordem de probabilidade — a k-ésima
   cópia de uma carta vale `P(cópias >= k)` sobre todas as listas do arquétipo
3. pára aos 60 (+15 de sideboard), ou aos 100 em Duel Commander e cEDH

Não é uma média inventada: cada slot é ocupado pela cópia com maior
probabilidade de lá estar. Uma carta que aparece em 60% das listas com 2 cópias
entra com 2; uma que aparece em 20% não entra de todo.

### Duas percentagens, não uma

- `pct` — sobre o total de cartas, contando cópias. É a que interessa para saber
  quanto falta comprar.
- `pct_distinct` — sobre cartas diferentes com playset completo. Costuma ser mais
  baixa, e é a que diz se estás a "quase lá" ou se tens 40 terrenos e mais nada.

Em ambas, os exemplares marcados como colecionador ficam de fora.

---

## Preços

### Cardmarket

O Cardmarket **não se raspa** — bloqueia e é contra os termos. Em vez disso
publica um price guide oficial, atualizado uma vez por dia:

<https://www.cardmarket.com/en/Magic/Data/File-Exports>

Descarregas o ficheiro (ou automatizas o download com a tua sessão) e carregas:

```bat
python -m mtgvault.cli prices-cardmarket C:\mtg\priceguide.json
```

### CardTrader

API oficial. O token obtém-se nas definições do teu perfil CardTrader.

```bat
set CARDTRADER_TOKEN=xxxxx
python -m mtgvault.cli prices-cardtrader mh3 otj blb
```

### Valor e movimentos

```bat
python -m mtgvault.cli value
python -m mtgvault.cli movers --days 7
```

`value` separa o valor da coleção de jogador do da coleção de colecionador.
`movers` mostra o que subiu e o que desceu na janela, em % — só cartas que tens.

---

## Automatizar (o "todos os dias")

`daily.py` faz tudo de uma vez. Cada passo é independente: se um falhar, os
outros continuam e o erro fica registado na tabela `job_runs`.

Agendador de Tarefas do Windows → Criar Tarefa Básica → Diariamente às 08:00:

- Programa: `C:\mtgvault\.venv\Scripts\python.exe`
- Argumentos: `C:\mtgvault\daily.py`
- Iniciar em: `C:\mtgvault`

Variáveis opcionais: `CARDTRADER_TOKEN`, `CARDTRADER_SETS` (ex. `mh3,otj,blb`),
`CARDMARKET_PRICEGUIDE` (caminho do ficheiro), `MTGVAULT_DB`.

---

## Correr online (GitHub Actions)

O `.github/workflows/daily.yml` corre tudo às 06:00 UTC sem precisares do PC
ligado. <cite>No plano Free, repositórios privados têm 2.000 minutos Linux por mês</cite>;
um job de ~5 minutos por dia gasta cerca de 150.

**Repositório privado.** A tua coleção e o que ela vale não têm de ser públicos.

### Configuração

Em Settings → Secrets and variables → Actions:

| Nome | Tipo | Para quê |
|---|---|---|
| `CARDTRADER_TOKEN` | secret | API do CardTrader |
| `MOXFIELD_USER_AGENT` | secret | decks do Moxfield |
| `CARDMARKET_COOKIE` | secret | descarregar o price guide |
| `CARDMARKET_PRICEGUIDE_URL` | secret | link exato do ficheiro |
| `CARDTRADER_SETS` | variable | ex. `mh3,otj,blb` |

Todos são opcionais: o que faltar é saltado e registado, o resto corre na mesma.

### O que corre e o que não corre

O primeiro `push` constrói o catálogo (uns minutos). Depois fica em cache com
chave semanal, por isso só se reconstrói uma vez por semana.

Podes correr à mão em Actions → Recolha diária → Run workflow.
O resumo de cada execução mostra o estado da base de dados e as falhas
dos últimos dois dias.

### Três coisas que vão correr mal, e o que já está feito quanto a elas

**1. O cron do GitHub atrasa e às vezes salta execuções.** É best-effort, não é
garantido. Mitigação: o harvest recolhe sempre 2 dias para trás, e o histórico
de preços só grava mudanças — um dia perdido não deixa buraco, deixa apenas uma
mudança registada um dia mais tarde.

**2. O cookie do Cardmarket vai expirar.** A página de exports exige sessão
iniciada e num runner sem browser a única forma é o cookie num secret. Quando
expirar, o passo falha, aparece no resumo, e tu geras um cookie novo. Falha em
silêncio de propósito: é melhor ficar um dia sem preços do que perder a recolha
de decklists.

**3. O repositório cresce.** Cada commit diário guarda uma cópia inteira do
`vault.db` — o Git não faz deltas úteis em ficheiros binários. Sem cuidado, um
`vault.db` de 5 MB dá quase 2 GB de histórico ao fim de um ano.

Duas defesas já implementadas:

- **Preços só das cartas que interessam** (coleção, decks, vigiados, cores dos
  arquétipos), em vez do mercado inteiro.
- **`prune` diário**: apaga decklists com mais de 180 dias, mantendo a tabela
  `card_roles`. Perdes a lista do jogador X em março; mantens a evolução do
  metagame em março, que é o que realmente querias.

```bat
python -m mtgvault.cli prune --days 365      :: se quiseres guardar mais
python -m mtgvault.cli status
```

Se ainda assim o histórico incomodar daqui a uns anos, um `git checkout --orphan`
recomeça o histórico sem perder os dados atuais.

---

## Testes

```bat
cd tests
python test_analysis.py      :: matemática do core/tech (inclui o exemplo 80/20)
python test_integration.py   :: coleção + metagame falsos, sistema todo
python test_prices.py        :: recolha seletiva e gravação só de mudanças
python test_watchlist.py     :: vigiados, diffs, listas padrão, cobertura
```

Nenhum deles toca na rede.

---

## O que ainda não está feito

- **Scrapers de Premodern / Duel Commander / cEDH** — a análise já os suporta,
  falta a recolha automática.
- **Interface gráfica.** Por agora é linha de comandos. O passo seguinte natural
  é uma pequena app web local (FastAPI + uma página) para ver a coleção, as
  fotos e os gráficos de preço no browser.
- **Reconhecimento automático das cartas nas fotos.** Hoje sou eu que leio as
  fotos e devolvo o CSV. Dá para automatizar mais tarde.
- **O scraper do MTGO não pôde ser testado contra o site real** (o ambiente onde
  o escrevi não tem acesso ao mtgo.com). A lógica de parsing está isolada em
  `parse_mtgo_page` — se a primeira execução vier vazia, é aí que se corrige, e
  eu ajusto contigo a partir do HTML que me mandares.
