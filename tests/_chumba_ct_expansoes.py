"""Corre UM caso do `test_cardtrader_expansoes` com o codigo ANTIGO no lugar.

`py tests/_chumba_ct_expansoes.py <alvo> <nome_do_caso>` — sai a 0 se o caso
PASSAR (o que e mau: passava sem a correccao) e != 0 se chumbar (o que e bom).
Num processo proprio porque o teste fixa o `MTGVAULT_CONFIG`, o
`MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Alvos:

  dict_antigo — o `expansoes_mtg` volta a ser EXACTAMENTE o que estava nos dois
                sitios antes de 2026-10-04:
                    {e["code"].lower(): e["id"] for e in ct.expansions()
                     if e.get("code")}
                sem filtro de jogo, e com o ultimo a ganhar. E este o bug;
  sem_filtro  — ha `expansoes_mtg`, mas nao olha para o `game_id` (o erro que
                se faria ao «simplificar» a funcao a seguir);
  ultimo      — ha filtro de Magic, mas o desempate dentro do Magic volta a ser
                «o ultimo que a API serviu» em vez do id mais baixo;
  sem_aviso   — o desempate esta certo e escolhe em SILENCIO. Escolher sem
                dizer e como isto comecou.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_cardtrader_expansoes as T                         # noqa: E402

from mtgvault import prices                                   # noqa: E402

if alvo == "dict_antigo":
    prices.expansoes_mtg = (
        lambda ct: {e["code"].lower(): e["id"]
                    for e in ct.expansions() if e.get("code")})
elif alvo == "sem_filtro":
    def _sem_filtro(ct):
        exps = {}
        for e in ct.expansions():
            code = (e.get("code") or "").lower()
            if code:
                exps[code] = min(exps.get(code, e["id"]), e["id"])
        return exps

    prices.expansoes_mtg = _sem_filtro
elif alvo == "ultimo":
    def _ultimo(ct):
        return {e["code"].lower(): e["id"] for e in ct.expansions()
                if e.get("game_id") == 1 and e.get("code")}

    prices.expansoes_mtg = _ultimo
elif alvo == "sem_aviso":
    def _calado(ct):
        exps = {}
        for e in ct.expansions():
            if e.get("game_id") != 1:
                continue
            code = (e.get("code") or "").lower()
            if code:
                exps[code] = min(exps.get(code, e["id"]), e["id"])
        return exps

    prices.expansoes_mtg = _calado
else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

getattr(T, caso)()
print(f"PASSOU SEM A CORRECCAO (alvo={alvo}): {caso}")
