"""Reconstroi as trocas de lista de referencia dos ultimos 30+ dias a partir do
job_runs (meus-decks: "Deck: atualizado -> AAAA-MM-DD jogador") e mede o tamanho
de cada troca (cartas, nos dois sentidos) e a carta do nome. So leitura."""
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import my_decks  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{(RAIZ / '_scratch' / 'vault.db').as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

SIG = {n: (f, c) for n, f, c in my_decks.FOLLOWED}
SIG.update({n: (v[0], v[1]) for n, v in my_decks.SAIU.items()})
RE = re.compile(r"^(.+?): atualizado -> (\d{4}-\d{2}-\d{2}) (.+)$")

runs = con.execute("SELECT id, job, started, status, detail FROM job_runs "
                   "WHERE job LIKE 'meus%' ORDER BY id").fetchall()
print("corridas meus-decks:", len(runs), "de", runs[0]["started"] if runs else "-",
      "a", runs[-1]["started"] if runs else "-")


def achar(deck, dia, jogador):
    if deck not in SIG:
        return None
    fmt, cards = SIG[deck]
    inc = [c for c in cards if not c.startswith("!")]
    rows = con.execute("SELECT id FROM decklists WHERE format=? AND event_date=? AND player=? "
                       "ORDER BY id DESC", (fmt, dia, jogador)).fetchall()
    for r in rows:
        nomes = {x[0] for x in con.execute("SELECT card_name FROM decklist_cards WHERE decklist_id=?", (r["id"],))}
        if all(c in nomes for c in inc):
            return r["id"]
    return None


def cartas(lid):
    d = {}
    for b, n, q in con.execute("SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id=?", (lid,)):
        d[(b, n)] = d.get((b, n), 0) + q
    return d


def nome_card(deck, cards):
    low = deck.lower()
    return [c for c in cards if not c.startswith("!") and c.split(",")[0].strip().lower() in low]


eventos = []  # (dia_corrida, deck, dia_lista, jogador)
for r in runs:
    for parte in (r["detail"] or "").split("; "):
        m = RE.match(parte.strip())
        if m:
            eventos.append((r["started"][:10], m.group(1), m.group(2), m.group(3)))
print("trocas no job_runs:", len(eventos))

ultimo = {}
linhas = []
for corrida, deck, dia, jog in eventos:
    lid = achar(deck, dia, jog)
    prev = ultimo.get(deck)
    ultimo[deck] = (lid, dia, jog)
    if prev is None:
        linhas.append((corrida, deck, None, lid, None, None))
        continue
    if prev[0] is None or lid is None:
        linhas.append((corrida, deck, prev, lid, None, "lista podada"))
        continue
    a, b = cartas(prev[0]), cartas(lid)
    delta = sum(abs(b.get(k, 0) - a.get(k, 0)) for k in set(a) | set(b))
    fmt, cards = SIG[deck]
    nc = nome_card(deck, cards)
    nome_info = ", ".join(f"{c} {sum(q for (_, n), q in a.items() if n == c)}->{sum(q for (_, n), q in b.items() if n == c)}" for c in nc)
    linhas.append((corrida, deck, prev, lid, delta, nome_info))

for corrida, deck, prev, lid, delta, info in linhas:
    pv = f"#{prev[0]} {prev[2]} {prev[1]}" if prev else "(primeira)"
    print(f"{corrida} | {deck:32s} | {pv:40s} -> #{lid} | delta={delta} | {info or ''}")

ds = sorted(x[4] for x in linhas if isinstance(x[4], int))
print("\ndeltas medidos:", ds)
