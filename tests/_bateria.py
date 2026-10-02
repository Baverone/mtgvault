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
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
# TECTO POR FICHEIRO (2026-10-02). Não havia nenhum, e um teste pendurado
# pendurava a bateria **para sempre** — sem uma linha de saída, porque o resumo
# só se imprime no fim. Aconteceu nesse dia: vinte minutos a olhar para um
# ficheiro de zero bytes sem saber se estava lento ou morto. Agora o ficheiro que
# estoura o tecto é NOMEADO e a bateria continua. 600 s é generoso de propósito
# (o mais lento mede ~55 s, e o `test_paginas_leves` levanta um servidor e corre
# o node); afina-se com `MTGVAULT_TESTE_TECTO_S`.
TECTO_S = int(os.environ.get("MTGVAULT_TESTE_TECTO_S", "600"))
maus, pendurados, lentos = [], [], []
for f in sorted(AQUI.glob("test_*.py")):
    t = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, f.name], cwd=AQUI, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=TECTO_S)
    except subprocess.TimeoutExpired:
        pendurados.append(f.name)
        print(f"PENDURA {f.name} (passou dos {TECTO_S}s)", flush=True)
        continue
    s = time.perf_counter() - t
    ok = p.returncode == 0
    print(f"{'ok  ' if ok else 'ERRO'} {f.name}  {s:.1f}s", flush=True)
    if s > 60:
        lentos.append((s, f.name))
    if not ok:
        maus.append(f.name)
        print((p.stdout or "")[-1500:])
        print((p.stderr or "")[-2500:])
if lentos:
    print("\nacima de 60s: " + ", ".join("%s (%.0fs)" % (n, s)
                                        for s, n in sorted(lentos, reverse=True)))
if pendurados:
    print("PENDURARAM: " + ", ".join(pendurados))
print(f"\n{'TUDO OK' if not maus and not pendurados else 'FALHARAM: ' + ', '.join(maus + pendurados)}")
sys.exit(1 if maus or pendurados else 0)
