"""Prova que o test_emparelhador chumba sem a recusa (corre-se a mao):
neutraliza o `my_decks.avaliar_troca` e o `painel.TROCA_DE_ARQUETIPO` (um
processo por alvo, para um nao envenenar o outro)."""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ALVOS = {
    "sem_avaliar": "import my_decks; my_decks.avaliar_troca = lambda a, b, c: None",
    "sem_tecto": "import my_decks; my_decks.TROCA_DE_ARQUETIPO = 10**6",
    "sem_carta_nome": ("import my_decks; my_decks.cartas_do_nome = lambda d, a: []"),
}
falhou = 0
for nome, patch in ALVOS.items():
    cod = (f"import sys; sys.path.insert(0, r'{AQUI.parent}'); sys.path.insert(0, r'{AQUI}');"
           f"{patch}; import test_emparelhador as t; t.run()")
    p = subprocess.run([sys.executable, "-c", cod], cwd=AQUI, capture_output=True, text=True)
    chumbou = p.returncode != 0
    falhou += not chumbou
    print(f"{nome:16s} {'CHUMBA (bom)' if chumbou else 'PASSA (mau: o teste nao tranca)'}")
sys.exit(1 if falhou else 0)
