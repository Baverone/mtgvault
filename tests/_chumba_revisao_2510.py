"""Corre cada caso do `test_revisao_2510` à parte e diz quais chumbam.

Com as correcções postas têm de passar todos; com o código de antes (`git
stash` das alterações rastreadas) têm de chumbar todos — é a prova de que cada
caso reproduz o bug. Corre-se à mão.
"""
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_revisao_2510 as t  # noqa: E402
from mtgvault import db  # noqa: E402

SEM_BASE = ["caso_o_caminho_com_ponto_ponto_nao_sai_de_data_paginas",
            "caso_entradas_invalidas_dao_400_e_nao_penduram",
            "caso_um_post_de_outro_site_e_recusado",
            "caso_o_numero_com_estrela_le_se_inteiro",
            "caso_o_get_nao_espera_um_minuto_pelo_lock",
            "caso_o_js_dos_decks_guarda_a_ordem_das_respostas"]
COM_BASE = ["caso_fixar_com_id_errado_nao_solta_a_fixacao",
            "caso_as_pecas_do_combo_nao_se_partem_na_virgula",
            "caso_os_avisos_das_staples_de_outro_dia_nao_passam_por_hoje"]

res = {}
for nome in SEM_BASE + COM_BASE:
    try:
        if nome in COM_BASE:
            tmp = Path(tempfile.mkdtemp())
            with db.session(tmp / "v.db", tmp / "c.db") as con:
                getattr(t, nome)(con)
        else:
            getattr(t, nome)()
        res[nome] = "passa"
    except Exception as e:  # noqa: BLE001
        res[nome] = "CHUMBA: " + (str(e).splitlines() or [type(e).__name__])[0][:120]
        traceback.print_exc(limit=1)
print()
for k, v in res.items():
    print(f"{v[:7]:8} {k}  {v[8:]}")
