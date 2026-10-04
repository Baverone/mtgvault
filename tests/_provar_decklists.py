"""A PROVA: cada caso do `test_decklists_no_site` CHUMBA sem a funcionalidade.

`py tests/_provar_decklists.py` — um processo por par (alvo, caso), porque o teste
fixa variáveis de ambiente no import e meia dúzia dos alvos trocam funções de
módulo. Sai ≠ 0 se algum par PASSAR: um caso que passa com a peça desligada não
está a trancar nada.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

PARES = [
    ("escala", "caso_um_torneio_de_mil_jogadores_traz_mais_listas_que_uma_challenge"),
    ("escala_online", "caso_a_escala_nao_se_aplica_a_uma_challenge_de_mtgo"),
    ("revisitar", "caso_a_revisita_forcada_de_um_evento_ja_processado_funciona"),
    # O `fila_grande` NÃO se prova com o caso da revisita forçada, e isso não é um
    # descuido: o evento desse caso é o «Regional Championship», que CASA no padrão
    # do nome e por isso tem `grande = 1` — o filtro antigo não o excluía. Quem o
    # tranca é o caso a seguir, onde o segundo evento é o «Bogardan War II»: 139
    # jogadores e um nome que nenhum padrão reconhece, logo `grande = 0`. É esse o
    # caso que a regra nova veio apanhar.
    ("fila_grande", "caso_uma_pagina_que_ja_nao_e_do_evento_nao_se_marca_nem_entope_a_fila"),
    ("d_zero", "caso_uma_pagina_que_ja_nao_e_do_evento_nao_se_marca_nem_entope_a_fila"),
    ("pagina_morta", "caso_uma_pagina_que_ja_nao_e_do_evento_nao_se_marca_nem_entope_a_fila"),
    ("vez_gasta", "caso_uma_pagina_que_ja_nao_e_do_evento_nao_se_marca_nem_entope_a_fila"),
    ("nome_caixa", "caso_o_nome_da_caixa_modern_corresponde_a_lista_que_tem_dentro"),
    ("arquetipo", "caso_o_nome_da_caixa_modern_corresponde_a_lista_que_tem_dentro"),
    ("desactivada", "caso_uma_caixa_desactivada_nao_aparece_como_deck_de_zero_por_cento"),
    ("data_consenso", "caso_cada_caixa_diz_a_lista_a_fonte_e_a_data"),
    ("data_vigia", "caso_cada_caixa_diz_a_lista_a_fonte_e_a_data"),
    ("amostra", "caso_um_consenso_abaixo_do_minimo_diz_se_na_pagina"),
    ("staples", "caso_marcar_um_deck_recalcula_proprias_partilhadas_e_staples"),
]

maus = []
for alvo, caso in PARES:
    p = subprocess.run([sys.executable, str(AQUI / "_chumba_decklists.py"), alvo, caso],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=AQUI, timeout=600)
    chumbou = p.returncode != 0
    print(f"{'chumba OK' if chumbou else 'PASSOU (MAU)'}  {alvo:14s} {caso}")
    if not chumbou:
        maus.append((alvo, caso))
        print((p.stdout or "")[-400:])

print()
if maus:
    print("ALVOS QUE NÃO TRANCAM NADA: "
          + ", ".join(f"{a}/{c}" for a, c in maus))
else:
    print(f"TODOS CHUMBAM ({len(PARES)} pares)")
sys.exit(1 if maus else 0)
