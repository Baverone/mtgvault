"""Prova de que o `test_foto_ate_playset` CHUMBA com cada peça desligada (um
processo por alvo). E a outra direcção da regra 3: sem a trava do caso 5, o caso
5 (o deste ficheiro e o do `test_foto_manda`) chumba — e o caso das DUAS cópias
continua verde, porque não depende dela. Corre-se à mão:
`py _chumba_foto_ate_playset.py`."""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

SEM_TRAVA = ("from mtgvault import confirmado as K\n"
             "K.exige_uma_so = lambda *a, **k: None\n")

# (nome, ficheiro de teste, patch, caso, tem de chumbar?)
ALVOS = [
    # Regra 1: o deck volta a levar o lote inteiro (o comportamento até 13/10).
    ("aloca_o_lote_inteiro", "test_foto_ate_playset",
     "from mtgvault import confirmado as K\n"
     "K.quantas_leva_o_deck = lambda *a, **k: None\n",
     "caso_pasta_2_foto_com_4_entram_4_e_o_deck_leva_2", True),
    # Regra 2: a pasta volta enquanto a conta não bater com o (N).
    ("gerador_pela_conta", "test_foto_ate_playset",
     "from mtgvault import fotos as F\n"
     "F.carta_feita = lambda tem, q: int(tem or 0) >= int(q or 0)\n",
     "caso_pasta_4_foto_com_2_o_deck_fica_a_dever_2_e_a_pasta_nao_volta", True),
    # Regra 3: a prova passa a ser por CARTA e não por foto — a segunda pasta
    # da mesma carta fica «repetida» e não cria cópia.
    ("funde_por_carta", "test_foto_ate_playset",
     "from mtgvault import fotos as F\n"
     "_vistas = set()\n"
     "def _por_carta(ind, foto, nm, *a, **k):\n"
     "    if nm in _vistas: return True\n"
     "    _vistas.add(nm); return False\n"
     "F.ja_e_prova = _por_carta\n",
     "caso_a_mesma_carta_em_duas_pastas_sao_duas_copias", True),
    # Regra 4: um tecto abaixo do playset recusa a foto de 4.
    ("tecto_abaixo_do_playset", "test_foto_ate_playset",
     "from mtgvault import fotos as F\n"
     "F.valida = lambda n, *a, **k: 1 <= int(n) <= 2\n",
     "caso_o_playset_cabe_na_foto_e_a_pasta_2_nao_recusa_4", True),
    # A trava do caso 5 desligada: os dois casos 5 chumbam...
    ("sem_trava_caso5_aqui", "test_foto_ate_playset", SEM_TRAVA,
     "caso_o_caso_5_continua_a_defender_uma_copia_em_dois_decks", True),
    ("sem_trava_caso5_foto_manda", "test_foto_manda", SEM_TRAVA,
     "caso_uma_segunda_alocacao_da_mesma_copia_e_recusada", True),
    # ...e o das duas cópias continua verde: não aciona a trava nem depende dela.
    ("sem_trava_duas_copias_passa", "test_foto_ate_playset", SEM_TRAVA,
     "caso_a_mesma_carta_em_duas_pastas_sao_duas_copias", False),
]


def main():
    erradas = 0
    for nome, mod, patch, caso, deve_chumbar in ALVOS:
        codigo = ("import sys; sys.path.insert(0, r'%s')\n" % AQUI
                  + f"import {mod} as T\n" + patch + f"T.{caso}()\n")
        p = subprocess.run([sys.executable, "-c", codigo], cwd=str(AQUI),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        chumbou = p.returncode != 0
        certo = chumbou == deve_chumbar
        print(f"{'CHUMBA' if chumbou else 'PASSA '}  "
              f"{'ok' if certo else 'ERRADO'}  {nome}  ({mod}.{caso})")
        if not certo:
            erradas += 1
            print((p.stdout or "")[-800:], (p.stderr or "")[-1200:])
    print(f"\n{len(ALVOS) - erradas} de {len(ALVOS)} alvos como esperado")
    sys.exit(1 if erradas else 0)


if __name__ == "__main__":
    main()
