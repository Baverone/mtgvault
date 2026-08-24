#!/usr/bin/env bash
# Publica o vault.db LOCAL no Release 'data' (torna-o a fonte de verdade).
# Corre isto DEPOIS de importares fotos/alterar a coleção localmente.
#
# Precisa do GitHub CLI autenticado (uma vez só):
#   winget install --id GitHub.cli --silent
#   gh auth login          # GitHub.com -> HTTPS -> login no browser
#
# Nota: last-write-wins. Puxa sempre primeiro (db_pull.sh) para não apagares
# o harvest/preços que o job diário juntou entretanto.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v gh >/dev/null 2>&1; then
  echo "ERRO: 'gh' não está instalado. Instala com: winget install --id GitHub.cli" >&2
  exit 1
fi
gh release view data >/dev/null 2>&1 || gh release create data \
  --title "Base de dados (vault.db)" \
  --notes "vault.db — fonte de verdade da coleção. Não editar à mão."
gh release upload data data/vault.db --clobber
echo "vault.db publicado no Release 'data'."
