"""Prova que os casos do `test_janela_consenso` CHUMBAM sem a funcionalidade.

`py tests/_provar_janela.py` — um processo por par (alvo, caso), porque metade
do que o `_chumba_janela` desliga é global e num processo só o primeiro que
pendurasse envenenava os seguintes em silêncio.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

PARES = [
    ("corte", "caso_o_consenso_nao_conta_listas_anteriores_ao_corte"),
    ("corte", "caso_o_consenso_por_comandante_leva_o_mesmo_corte"),
    ("corte", "caso_uma_lista_manual_tambem_respeita_o_corte"),
    ("sql", "caso_o_consenso_nao_conta_listas_anteriores_ao_corte"),
    ("sql", "caso_o_consenso_por_comandante_leva_o_mesmo_corte"),
    ("python", "caso_o_consenso_nao_conta_listas_anteriores_ao_corte"),
    ("python", "caso_uma_lista_manual_tambem_respeita_o_corte"),
    ("amostra", "caso_abaixo_do_minimo_diz_amostra_insuficiente_e_nao_da_percentagens"),
    ("frase", "caso_abaixo_do_minimo_diz_amostra_insuficiente_e_nao_da_percentagens"),
    ("frase", "caso_a_caixa_sem_amostra_diz_amostra_insuficiente_na_nota"),
    ("reserva", "caso_a_reserva_continua_na_janela_dela"),
    ("derivada", "caso_a_assinatura_derivada_tambem_fica_fora_do_corte"),
    ("seguir", "caso_seguir_uma_lista_fica_fora_do_corte"),
    ("excepcoes", "caso_o_premodern_fica_fora_do_corte"),
    ("paginas", "caso_a_janela_aparece_nas_paginas"),
    ("daily", "caso_o_daily_diz_a_janela_com_que_calculou"),
]


def main() -> None:
    maus = []
    for alvo, caso in PARES:
        r = subprocess.run([sys.executable, str(AQUI / "_chumba_janela.py"),
                            alvo, caso], capture_output=True, text=True)
        if r.returncode == 0:
            maus.append((alvo, caso))
            print(f"  [MAU ] {alvo:10s} {caso}  -- passou sem a funcionalidade")
        else:
            motivo = (r.stderr or "").strip().splitlines()
            print(f"  [bom ] {alvo:10s} {caso}")
            if motivo:
                print(f"           {motivo[-1][:150]}")
    print(f"\n{len(PARES) - len(maus)} de {len(PARES)} chumbam sem a "
          f"funcionalidade")
    if maus:
        raise SystemExit(f"{len(maus)} caso(s) passam sem a funcionalidade: "
                         + ", ".join(f"{a}/{c}" for a, c in maus))


if __name__ == "__main__":
    main()
