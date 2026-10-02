"""Corre UM caso do `test_regras_material_1002` com uma peça desligada.

`py tests/_chumba_regras_1002.py <alvo> <nome_do_caso>` — sai a 0 se o caso
passar (o que é MAU: passa sem a funcionalidade) e != 0 se chumbar (o que é bom).
Está num processo próprio porque o `test_regras_material_1002` fixa o
`MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  dc_lingua   — o Duel Commander volta a não exigir língua: uma PT fecha o slot;
  dc_foil     — o Duel Commander volta a `acabamento: foil` obrigatório: uma EN
                non-foil de uma carta que existe em foil deixa de servir;
  pauper_ling — o Pauper volta a não exigir língua;
  pm_acab     — o Premodern volta a não ter chave de acabamento: a PT FOIL volta
                a fechar o slot (era o estado de até 2026-10-02);
  basicas4    — a excepção das básicas ao tecto de 4 desaparece: 27
                Snow-Covered Plains voltam a dar sete fotos;
  declarada   — a contagem declarada volta a somar ao «confirmado por foto»:
                as básicas voltam a inflacionar o número da campanha;
  req_basicas — o `requisito_basicas` volta a dizer o acabamento a seco, ou seja
                a pedir numa linha de básicas o que o motor não exige;
  isencao     — a isenção das básicas deixa de cobrir o ACABAMENTO: uma Unhinged
                EN foil deixa de servir uma caixa de Premodern non-foil;
  estado_bas  — o `estado.registar` volta a aceitar um escalão numa básica.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_regras_material_1002 as T                         # noqa: E402
from mtgvault import estado, fotos, loadout, revalidacao      # noqa: E402
from mtgvault import confirmado as _conf                      # noqa: E402


def _sem(grupo: str, chave: str) -> None:
    """Tira uma chave de um grupo das `regras_por_formato` — o config de ontem."""
    cfg = json.loads(T.CFG_PATH.read_text(encoding="utf-8"))
    for g in cfg["regras_por_formato"]:
        if g["grupo"] == grupo:
            g.pop(chave, None)
    T.CFG_PATH.write_text(json.dumps(cfg), encoding="utf-8")


def _poe(grupo: str, chave: str, valor) -> None:
    cfg = json.loads(T.CFG_PATH.read_text(encoding="utf-8"))
    for g in cfg["regras_por_formato"]:
        if g["grupo"] == grupo:
            g[chave] = valor
    T.CFG_PATH.write_text(json.dumps(cfg), encoding="utf-8")


if alvo == "dc_lingua":
    _sem("duel-commander", "lingua")
    T.CFG["regras_por_formato"][1].pop("lingua", None)
elif alvo == "dc_foil":
    _poe("duel-commander", "acabamento", "foil")
    T.CFG["regras_por_formato"][1]["acabamento"] = "foil"
elif alvo == "pauper_ling":
    _sem("pauper", "lingua")
    T.CFG["regras_por_formato"][2].pop("lingua", None)
elif alvo == "pm_acab":
    _sem("premodern", "acabamento")
    T.CFG["regras_por_formato"][0].pop("acabamento", None)
elif alvo == "basicas4":
    # A isenção desaparece: tudo volta a ter tecto.
    fotos.so_basicas = lambda nomes: False
    _antigo = lambda cartas, max_cartas=fotos.MAX_CARTAS, *, isenta=False: (  # noqa: E731
        0 < int(cartas or 0) <= max_cartas)
    fotos.valida = _antigo
    revalidacao.foto_valida = _antigo
elif alvo == "declarada":
    # As básicas voltam a contar como «confirmadas por foto» (o estado de ontem):
    # o `metades` deixa de ter parcela própria e soma tudo em cima.
    _m = _conf.metades

    def _junta(confirmado, total, *, unidade="cartas", casas=0, declarado=0):
        d = _m(confirmado + declarado, total, unidade=unidade, casas=casas)
        d["declarado"] = 0
        return d

    _conf.metades = _junta
    loadout._conf.metades = _junta
elif alvo == "req_basicas":
    loadout.requisito_basicas = lambda s: {
        "foil": "foil", "nonfoil": "non-foil",
        "prefere_foil": "foil se houver"}.get(s.get("acabamento") or "", "")
elif alvo == "isencao":
    # A isenção passa a cobrir só língua e edição — o acabamento volta a valer.
    _serve = loadout._serve_basica

    def _meia(lot, s, did, baldes, caixas):
        if not _serve(lot, s, did, baldes, caixas):
            return False
        ac = s.get("acabamento")
        foil = loadout.e_foil(lot["finish"])
        if ac == "nonfoil" and foil:
            return False
        if ac == "foil" and not foil:
            return False
        return True

    loadout._serve_basica = _meia
elif alvo == "estado_bas":
    estado.e_basica = lambda con, copy_id: False
else:
    print(f"alvo desconhecido: {alvo}")
    sys.exit(2)

getattr(T, caso)()
print(f"PASSOU SEM A FUNCIONALIDADE (alvo={alvo}, caso={caso})")
