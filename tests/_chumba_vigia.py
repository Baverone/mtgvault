"""Corre UM caso do `test_vigia_cartas` com a funcionalidade desligada.

`py tests/_chumba_vigia.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o
`test_vigia_cartas` fixa o `MTGVAULT_CONFIG` e o `MTGVAULT_DB` no import, e
partilhá-los com outro teste era pôr um a mexer no ambiente do outro.

Cada `alvo` é o mtgvault de ONTEM numa peça só:
  nomes_na_lista  — o `store_decklist` volta a não conhecer cartas vigiadas
                    (a liga é recusada à entrada, como em 2026-09-07);
  achados         — a poda volta a não saber o que poupar;
  chave           — o avistamento volta a identificar-se pelo `decklist_id`
                    (e o aviso repete-se quando a deduplicação o muda);
  nota_faltas     — o relatório de faltas deixa de dizer de onde vem o número.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_vigia_cartas as T                                 # noqa: E402
from mtgvault import vigia                                    # noqa: E402

if alvo == "nomes_na_lista":
    vigia.nomes_na_lista = lambda fmt, cards: []
elif alvo == "achados":
    vigia.achados = lambda con: []
elif alvo == "chave":
    vigia.chave = lambda a: str(a.get("decklist_id"))
elif alvo == "nota_faltas":
    vigia.NOTA_FALTAS = ""
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
