#!/usr/bin/env bash
# Descarrega o vault.db mais recente do Release 'data' (a fonte de verdade da BD).
# O repositório é público, por isso o download NÃO precisa de autenticação.
#
# Corre isto ANTES de trabalhar na coleção (importar fotos), para partires da
# versão mais recente (com o harvest/preços que o job diário já juntou).
set -euo pipefail
cd "$(dirname "$0")/.."
URL="https://github.com/Baverone/mtgvault/releases/download/data/vault.db"
echo "A descarregar vault.db do Release 'data'..."
mkdir -p data
curl -fL --retry 3 "$URL" -o data/vault.db
echo "Feito: data/vault.db ($(du -h data/vault.db | cut -f1))"
