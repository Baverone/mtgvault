"""Corre a bateria toda, um teste por processo, e resume.

Um processo por ficheiro de propósito: vários deles mexem em variáveis de
ambiente (`MTGVAULT_CONFIG`, `MTGVAULT_HOME`) no import, e partilhá-las num
processo só fazia um teste passar por causa do outro.
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
