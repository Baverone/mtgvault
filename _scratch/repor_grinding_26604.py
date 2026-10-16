"""Repoe a decklist 26604 (Cachorrowo, Modern Challenge 16 de 12/10 — a variante
de KETHIS) como lista de referencia do deck seguido «Grinding Station».

PARA A ORDEM DE MERGE — e a minha recomendacao e NAO o aplicar:
- a 26604 foi o SALTO (a 14/10, 84 cartas a partir da bbotonline 26635) e nao a
  lista do deck: das 7 referencias do Grinding Station desde 21/09, 6 sao o
  shell Emry + Sewer-veillance Cam SEM Kethis, e a regra nova (recusa > 60)
  simulada sobre o historico RECUSA a 26604 e ACEITA a 27439;
- o `my_decks.FOLLOWED` do `main` ja exclui o Kethis (`!Kethis, the Hidden
  Hand`, commit c144860 de 16/10): reposta, a 26604 deixa de ser candidata, a
  corrida seguinte propoe a howa 27439 (82 cartas) e — com a regra nova — e
  RECUSADA: o deck fica parado na de Kethis com um aviso ALTA todos os dias.

Se o André disser que o deck dele E o de Kethis, entao aplica-se E tira-se o
`!Kethis` do FOLLOWED (senao fica parado). Usa o `my_decks.aceitar`, que grava a
troca no historico (`deck_lista_trocas`).

Uso (a base por omissao e a do main; sem --aplicar so mostra):
    py _scratch/repor_grinding_26604.py [caminho/vault.db] [--aplicar]
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
LISTA = 26604
DECK = "Grinding Station"

args = [a for a in sys.argv[1:] if not a.startswith("--")]
aplicar = "--aplicar" in sys.argv
base = Path(args[0]) if args else RAIZ / "data" / "vault.db"
if not base.exists():
    sys.exit(f"base nao encontrada: {base}")

con = sqlite3.connect(base)
con.row_factory = sqlite3.Row
dl = con.execute("SELECT id, player, event_date, format FROM decklists WHERE id = ?", (LISTA,)).fetchone()
if dl is None:
    sys.exit(f"a decklist #{LISTA} ja nao existe (poda de 30 dias?) — nada a repor")
nota = con.execute("SELECT notes FROM decks WHERE name = ? AND format = 'modern'", (DECK,)).fetchone()
print(f"{DECK}: hoje {nota['notes'] if nota else '(sem deck)'}")
print(f"repor: #{dl['id']} {dl['player']} {dl['event_date']}")
if not aplicar:
    print("modo seco: nada escrito (--aplicar para escrever)")
    sys.exit(0)

dest = base.parent / "backups" / f"vault-{datetime.now():%Y-%m-%d-%H%M%S}-repor-grinding.db"
dest.parent.mkdir(parents=True, exist_ok=True)
con.execute("VACUUM INTO ?", (str(dest),))
print("backup:", dest)
import my_decks  # noqa: E402
print(my_decks.aceitar(con, DECK, LISTA))
