# Catalogar cartas a partir de fotos (guia para o Claude)

Este guia é para **qualquer Claude** (incluindo o claude.ai/code aberto no
telemóvel, apontado a `Baverone/mtgvault`) catalogar cartas das fotos, mesmo
sem o André estar ao PC.

## Fluxo

1. O André larga fotos novas na pasta **`pendentes/`** (app do GitHub no
   telemóvel, ou no PC).
2. **Tu (Claude) olhas para cada foto de `pendentes/`**, reconheces as cartas e
   escreves um **CSV** (formato abaixo). Guarda-o, ex.: `pendentes/recat.csv`.
3. Corres:
   ```bash
   py processar_fotos.py pendentes/recat.csv
   ```
   O script garante o catálogo, importa para `data/vault.db`, **arruma as
   fotos** para `pendentes/fotos processadas/<AAAA-MM>/` (nunca as apaga) e
   publica a BD. O site atualiza-se sozinho.

   Ao lado do teu CSV fica um `<nome>-resultado.csv` com o que aconteceu a cada
   linha. **As linhas que pararam vêm lá com o motivo** — a foto delas fica em
   `pendentes/` à espera de ser recatalogada.

O reconhecimento (passo 2) és sempre **tu a olhar para as fotos** — o script só
faz a parte mecânica.

## Formato do CSV

Cabeçalho (esta ordem de colunas):

```
name,set_code,collector_number,quantity,finish,language,condition,purpose,sub_collection,photo_path,acquired_price,notes
```

- **name** — nome REAL da carta impressa. Se for um *reskin* (ex.: cartas de
  Universes Beyond com nome de personagem), usa o nome real da carta de Magic.
  Cartas de dupla-face: o nome completo `Frente // Verso`.
- **set_code** — código do set (ex.: `mh3`, `fin`). Podes pôr como aparece — o
  script baixa para minúsculas. **Obrigatório: uma linha sem `set_code` NÃO
  entra** — para com `motivo: edicao em falta` e a foto fica em `pendentes/`.
  Até 2026-09-08 uma edição em branco não dava erro: dava a impressão *mais
  antiga* da carta, que para as básicas é sempre Alpha (foi assim que 5 Plains
  do Cloud cEDH ficaram `lea #287`, 309,50 € de valor fantasma). Se não
  conseguires ler a edição, confirma-a no catálogo (`catalogo.py "<nome>"`) ou
  deixa a linha de fora e escreve a dúvida em `notes` — mais vale uma carta por
  catalogar do que uma carta catalogada errada.
- **collector_number** — número da carta (canto inferior). Deixa como está (ex.:
  The List = `UGL-84`). Vazio se não der para ler.
- **quantity** — quantas cópias iguais (mesma edição/finish/língua) nessa foto.
- **finish** — `nonfoil` (por omissão) ou `foil`.
- **language** — `en` (por omissão) ou `pt` (se a carta estiver em português).
- **condition** — `NM` por omissão.
- **purpose** — `player` (por omissão) ou `collector` (se for de coleção, não
  para jogar — essas nunca contam para decks).
- **sub_collection** — o BALDE onde a carta fica. Valores atuais:
  `SPML` (Standard/Pioneer/Modern/Legacy), `Premodern (geral)`, `Blue Farm`,
  `Cloud`, `Cloud cEDH`, `Pauper Affinity`. Se a foto não disser, pergunta ao
  André ou põe o mais provável e regista em `notes`.
- **photo_path** — o nome do ficheiro da foto. **Põe-no sempre**: é o que liga
  a cópia à foto que lhe deu origem (a foto é arrumada, nunca apagada, e o
  caminho novo fica na cópia). Sem ele, uma suspeita de edição errada não tem
  como ser relida.
- **acquired_price** — opcional (€).
- **notes** — dúvidas ("edição a confirmar"), etc.

## Regras que não podem partir

- **Não inventes.** Se não consegues ler uma carta ou a edição, deixa o campo
  vazio e regista em `notes`; não adivinhes uma edição ao calhar.
- **set_code em minúsculas** (o script trata disto, mas se editares à mão, mete
  minúsculas). **collector_number NÃO se baixa** (mantém como impresso).
- **Terras básicas** contam à mesma (quantidade certa).
- Uma foto pode ter várias cartas — uma linha por carta distinta
  (nome+edição+finish+língua), com a `quantity` das repetidas.

Contexto do projeto: ver `CLAUDE.md`. Regras da coleção/decks: idem.
