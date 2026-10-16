"""A mesma bateria (mesmo ambiente com a trava), so para os ficheiros a partir de
um nome — a corrida inteira passa dos 10 min do tecto da ferramenta."""
import os
import subprocess
import sys
import time
from pathlib import Path

T = Path(__file__).resolve().parent.parent / "tests"
sys.path.insert(0, str(T.parent))
from mtgvault import db as _db  # noqa: E402

DESDE = sys.argv[1] if len(sys.argv) > 1 else "test_showcase"
amb = dict(os.environ)
amb[_db.VAR_PROIBIDAS] = os.pathsep.join(str(Path(p).resolve()) for p in (_db.DEFAULT_DB, _db.DEFAULT_CATALOG))
maus = []
for f in sorted(T.glob("test_*.py")):
    if f.name < DESDE:
        continue
    t = time.perf_counter()
    p = subprocess.run([sys.executable, f.name], cwd=T, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600, env=amb)
    ok = p.returncode == 0
    print(f"{'ok  ' if ok else 'ERRO'} {f.name}  {time.perf_counter() - t:.1f}s", flush=True)
    if not ok:
        maus.append(f.name)
        print((p.stdout or "")[-1500:])
        print((p.stderr or "")[-2500:])
print("TUDO OK" if not maus else "FALHARAM: " + ", ".join(maus))
