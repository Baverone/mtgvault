"""Prova de que o `test_busca_ligas` CHUMBA sem a funcionalidade (corre-se à mão).

Um processo por alvo: desliga uma peça e exige vermelho no caso que a tranca.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

ALVOS = [
    ("o `ligas` lido como «truthy» (a string 'busca' abria o League)",
     "import re\n"
     "_o = sources.metagame_rules\n"
     "def _m(fmt):\n"
     "    r = _o(fmt)\n"
     "    if busca_ligas.e_busca(fmt) and 'League' not in r['tiers']:\n"
     "        r['tiers'] = r['tiers'] + ['League']\n"
     "    return r\n"
     "sources.metagame_rules = _m",
     "caso_a_liga_de_busca_nunca_conta"),
    ("o store_decklist sem a pergunta da busca",
     "busca_ligas.alvos_na_lista = lambda *a, **k: []",
     "caso_a_liga_guarda_se_so_com_um_alvo_nomeado"),
    ("a colheita sem a pergunta da busca",
     "busca_ligas.ha_alvo = lambda *a, **k: False",
     "caso_a_colheita_so_abre_a_liga_quando_ha_alvo"),
    ("a poda a apagar as ligas de busca",
     "busca_ligas.e_busca = lambda f: False",
     "caso_a_poda_nao_apaga_as_ligas_de_um_formato_de_busca"),
    ("o limiar sobre o universo e não por deck seguido",
     "busca_ligas.seguidos = lambda fmt, cfg=None: [{'id': f'x{i}', 'nome': str(i), "
     "'origem': 'x', 'cartas': [f'Carta {i}'], 'todas': True, 'sem': []} for i in range(20)]",
     "caso_o_limiar_e_por_deck_seguido_e_nao_pelo_universo"),
    ("um presencial sem número a contar",
     "_o = sources.lista_conta\n"
     "def _l(row, fmt=None, consenso=True):\n"
     "    if row['event_tier'] == 'Presencial' and not row['event_players']:\n"
     "        return True\n"
     "    return _o(row, fmt, consenso)\n"
     "sources.lista_conta = _l",
     "caso_um_presencial_sem_numero_nao_conta_e_fica_dito"),
]

maus = 0
for desc, patch, caso in ALVOS:
    prog = ("import sys; sys.argv=['x']\n"
            f"sys.path.insert(0, r'{AQUI}')\n"
            "import test_busca_ligas as T\n"
            "from mtgvault import sources, busca_ligas\n"
            f"{patch}\n"
            f"T.{caso}()\n")
    r = subprocess.run([sys.executable, "-c", prog], capture_output=True, text=True)
    chumbou = r.returncode != 0
    maus += not chumbou
    print(f"{'CHUMBA' if chumbou else 'PASSA!'}  {desc}")
print(f"{len(ALVOS) - maus} de {len(ALVOS)} alvos chumbam")
sys.exit(1 if maus else 0)
