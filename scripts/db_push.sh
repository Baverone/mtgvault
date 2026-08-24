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

# Localiza o gh: PATH primeiro; senão o local onde o winget o instala (o PATH
# só atualiza em shells novos, por isso na mesma sessão pode não lá estar).
GH="$(command -v gh 2>/dev/null || true)"
if [ -z "$GH" ]; then
  for cand in \
    "${LOCALAPPDATA:-}/Microsoft/WinGet/Packages/GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe/bin/gh.exe" \
    "/c/Program Files/GitHub CLI/gh.exe"; do
    if [ -n "$cand" ] && [ -x "$cand" ]; then GH="$cand"; break; fi
  done
fi
if [ -z "$GH" ]; then
  echo "ERRO: 'gh' não encontrado. Instala com: winget install --id GitHub.cli --silent" >&2
  echo "      e autentica com: gh auth login" >&2
  exit 1
fi

"$GH" release view data >/dev/null 2>&1 || "$GH" release create data \
  --title "Base de dados (vault.db)" \
  --notes "vault.db — fonte de verdade da coleção. Não editar à mão."
"$GH" release upload data data/vault.db --clobber
echo "vault.db publicado no Release 'data'."
