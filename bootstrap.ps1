# Bootstrap do mtgvault num PC novo.
# Corre isto DENTRO da pasta do projeto, depois de 'git clone'. E idempotente
# (podes correr vezes sem conta). Sem acentos de proposito, para nao dar chatice
# de encoding no Windows PowerShell.
$ErrorActionPreference = "Stop"

Write-Host "== 1/3 Dependencias Python =="
python -m pip install -r requirements.txt

Write-Host "== 2/3 Catalogo Scryfall (constroi so se estiver vazio; ~119 MB, precisa de rede) =="
python -m mtgvault.cli ensure-catalog

Write-Host "== 3/3 Estado da base de dados =="
python -m mtgvault.cli status

Write-Host ""
Write-Host "Pronto. Regra de ouro: faz 'git pull' antes de cada sessao de trabalho neste PC."
