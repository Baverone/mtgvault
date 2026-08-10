# Instalar o mtgvault no PC principal (sempre ligado)

Objetivo: pôr este projeto a correr no PC que está sempre ligado, para teres
**sempre disponível o remote-control** (Claude no telemóvel) e para **processar
fotos da coleção a qualquer hora**.

## O que muda (e o que NÃO muda)

- A **recolha diária do metagame já corre na cloud** (GitHub Actions, 06:00 UTC),
  e **os preços também**: o job reconstrói o catálogo e tira os preços do *bulk*
  gratuito da Scryfall, sem cookie nem token. Isso **não depende de nenhum PC**.
- O PC sempre-ligado serve apenas para: **(1)** remote-control sempre acessível
  do telemóvel; **(2)** processar as fotos da coleção quando quiseres.

## Pré-requisitos no PC novo

- **Git**, **Python 3.12+**, e o **Claude Code**.
- Para poder enviar alterações: **GitHub CLI** (`gh`) autenticado na conta Baverone.

## Passos

1. **Clonar** o repositório (o nome da pasta pode ser o que quiseres):

   ```
   git clone https://github.com/Baverone/mtgvault.git "Servidor MTG Coleçao"
   cd "Servidor MTG Coleçao"
   ```

2. **Bootstrap** — instala dependências e constrói o catálogo Scryfall (~119 MB,
   precisa de rede; o `catalog.db` NÃO vem no clone porque é grande de mais para o Git):

   ```
   powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
   ```

   (à mão seria: `pip install -r requirements.txt` e depois
   `python -m mtgvault.cli ensure-catalog`)

3. **Autenticar** para poder enviar alterações:

   ```
   gh auth login
   ```

4. **Claude Code + remote-control**: faz `claude /login` com a **mesma conta** do
   telemóvel e liga o remote-control (para aparecer sempre no telemóvel). Como o
   PC está sempre ligado, a sessão fica sempre acessível.

## Disciplina de sincronização (importante)

O `vault.db` é binário e é commitado pelo bot diário. Para não haver conflitos:

- Faz **sempre `git pull`** antes de começares a trabalhar neste PC.
- Usa este PC como o **único** PC de trabalho local. Se também mexeres no portátil
  antigo, faz `git pull` antes e não deixes edições por commitar (dois sítios a
  editar o `vault.db` ao mesmo tempo = conflito binário chato).

## Opcional: preços mais ricos neste PC

A cloud já refresca preços de graça (*bulk* da Scryfall). Se um dia quiseres os
dados mais detalhados do Cardmarket (low/trend/avg30), esses precisam do cookie
de sessão — e aí podes agendar `python daily.py` neste PC com `CARDMARKET_COOKIE`
definido. **Atenção:** se agendares aqui **E** mantiveres o GitHub Action, ambos
commitam o `vault.db` e podem colidir. Escolhe **um**: ou deixas a cloud a mandar
(mais simples), ou passas tudo para este PC e desligas o Action. Pede-me ajuda
antes de mudar isto.
