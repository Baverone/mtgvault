# A base de dados vive num Release, não no Git

O `data/vault.db` (~76 MB e a crescer) **não** é versionado no Git — inchava o
repositório e aproximava-se do limite de 100 MB do GitHub. Em vez disso, é um
**asset de um Release** com a tag `data`:

    https://github.com/Baverone/mtgvault/releases/download/data/vault.db

Esse URL é estável e público (download sem autenticação).

## Quem escreve na BD

- **Job diário (GitHub Actions):** puxa o asset → corre `daily.py` (harvest,
  preços, páginas) → republica o asset → commita **só o HTML**.
- **Tu/Claude no PC (importar fotos):** puxas o asset → importas → republicas.

É *last-write-wins* (sem merge de binário). Por isso **puxa sempre primeiro**.

## Fluxo local (importar fotos)

    bash scripts/db_pull.sh          # 1. buscar a versão mais recente
    # ... catalogar + importar as fotos para data/vault.db ...
    bash scripts/db_push.sh          # 2. republicar no Release

`db_push.sh` precisa do GitHub CLI autenticado, uma só vez:

    winget install --id GitHub.cli --silent
    gh auth login                    # GitHub.com -> HTTPS -> browser

O catálogo (`data/catalog.db`, da Scryfall) continua fora do Git e reconstrói-se
sozinho quando falta.
