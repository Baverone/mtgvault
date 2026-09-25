"""Corre UM caso do `test_venda_interruptor` com a funcionalidade desligada.

`py tests/_chumba_venda.py <mostrar|seccoes> <nome_do_caso>` — sai a 0 se o caso
passar (o que é mau: quer dizer que passa sem a funcionalidade) e ≠ 0 se chumbar
(o que é bom). Quem o chama é o `_provar_chumba.py`; está num processo próprio
porque o `test_venda_interruptor` fixa o `MTGVAULT_CONFIG` e o `MTGVAULT_DB` no
import, e partilhá-los com outro teste era pôr um a mexer no ambiente do outro.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_venda_interruptor as T                          # noqa: E402
from mtgvault import site_shell as shell                    # noqa: E402
from mtgvault import venda                                  # noqa: E402

if alvo == "mostrar":
    # O mtgvault de ontem: a venda está sempre à vista.
    venda.mostrar = lambda cfg=None: True
elif alvo == "seccoes":
    # A barra lateral a ignorar o interruptor (a lista inteira, como antes).
    shell.seccoes = lambda: shell.SECCOES
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
