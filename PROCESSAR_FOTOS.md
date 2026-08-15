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
   O script garante o catálogo, importa para `data/vault.db`, **limpa as fotos**
   de `pendentes/` e faz **commit + push**. O site atualiza-se sozinho.

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
  script baixa para minúsculas. Se não tiveres a certeza, deixa vazio e mete a
  edição provável em `notes` ("a confirmar").
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
- **photo_path** — o nome do ficheiro da foto (só como registo; a imagem é
  removida depois). Opcional.
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
