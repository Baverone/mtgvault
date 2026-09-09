"""Corre a bateria toda, um teste por processo, e resume.

Um processo por ficheiro de propósito: vários deles mexem em variáveis de
ambiente (`MTGVAULT_CONFIG`, `MTGVAULT_HOME`) no import, e partilhá-las num
processo só fazia um teste passar por causa do outro.

CADA TESTE TEM DE PÔR O `MTGVAULT_DB` NUM SÍTIO TEMPORÁRIO (2026-09-09)
-----------------------------------------------------------------------
Os ficheiros que acompanham a base — `arquetipos.json`, `vendas.csv`,
`registos-faltas.csv` — saem de `db.pasta_dados()`, que é a **pasta da
`MTGVAULT_DB`** e não a do `MTGVAULT_HOME` (é a nota de 2026-09-08 no
`mtgvault/db.py`, e há um teste a trancá-la). Neste PC o `MTGVAULT_DB` está
definido no ambiente e aponta para o `data/` a sério; pôr só o `MTGVAULT_HOME`
não chega.

Resultado, medido a 2026-09-09: correr a bateria no repositório **esvaziava o
`data/arquetipos.json` do André** — 24 arquétipos, 333 linhas, apagados. Nenhum
teste falhava (é para isso que o `arquetipos.carregar` responde com um registo
vazio: um `daily` não pode parar por causa disto), e a corrida seguinte
reescrevia os nomes todos do zero. É exactamente o defeito que o registo veio
corrigir, disparado pela ferramenta que devia ser inofensiva.

Por isso cada teste põe também o `MTGVAULT_DB`, ao lado do `MTGVAULT_HOME`, e o
`test_paginas.caso_a_bateria_nao_escreve_no_data_a_serio` tranca-o: um teste
novo que se esqueça volta a apagar o ficheiro dele em silêncio.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
maus = []
for f in sorted(AQUI.glob("test_*.py")):
    p = subprocess.run([sys.executable, f.name], cwd=AQUI, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    ok = p.returncode == 0
    print(f"{'ok  ' if ok else 'ERRO'} {f.name}")
    if not ok:
        maus.append(f.name)
        print((p.stdout or "")[-1500:])
        print((p.stderr or "")[-2500:])
print(f"\n{'TUDO OK' if not maus else 'FALHARAM: ' + ', '.join(maus)}")
sys.exit(1 if maus else 0)
