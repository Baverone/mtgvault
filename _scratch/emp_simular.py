"""Corre o my_decks.avaliar_troca sobre as trocas reconstruidas do job_runs
(desde 2026-09-16), com a semantica nova: a lista recusada NAO entra, por isso
a candidata seguinte compara-se com a lista que ficou. So leitura."""
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import my_decks  # noqa: E402
from mtgvault import painel  # noqa: E402

DESDE = "2026-09-16"
con = sqlite3.connect(f"file:{(RAIZ / '_scratch' / 'vault.db').as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
SIG = {n: (f, c) for n, f, c in my_decks.FOLLOWED}
SIG.update({n: (v[0], v[1]) for n, v in my_decks.SAIU.items()})
RE = re.compile(r"^(.+?): atualizado -> (\d{4}-\d{2}-\d{2}) (.+)$")


def achar(deck, dia, jog):
    fmt, cards = SIG[deck]
    inc = [c for c in cards if not c.startswith("!")]
    for (lid,) in con.execute("SELECT id FROM decklists WHERE format=? AND event_date=? AND player=? "
                              "ORDER BY id DESC", (fmt, dia, jog)):
        nomes = {x[0] for x in con.execute("SELECT card_name FROM decklist_cards WHERE decklist_id=?", (lid,))}
        if all(c in nomes for c in inc):
            return lid
    return None


def cartas(lid):
    return [[b, n, q] for b, n, q in con.execute(
        "SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id=?", (lid,))]


ev = []
for r in con.execute("SELECT started, detail FROM job_runs WHERE job LIKE 'meus%' ORDER BY id"):
    for parte in (r["detail"] or "").split("; "):
        m = RE.match(parte.strip())
        if m and m.group(1) in SIG:
            ev.append((r["started"][:10], m.group(1), m.group(2), m.group(3)))

# a lista que cada deck tinha ANTES da janela (a ultima aceite antes de DESDE)
held, ultimo_sem = {}, {}
recusas, aceites = [], 0
for corrida, deck, dia, jog in ev:
    lid = achar(deck, dia, jog)
    if corrida < DESDE:
        held[deck] = (lid, dia, jog)
        continue
    h = held.get(deck)
    if h is None or h[0] is None or lid is None:
        held[deck] = (lid, dia, jog)
        continue
    nome = painel.cartas_do_nome(deck, [c for c in SIG[deck][1] if not c.startswith("!")])
    porque = my_decks.avaliar_troca(cartas(h[0]), cartas(lid), nome)
    sem = my_decks.avaliar_troca(cartas(ultimo_sem.get(deck, h)[0]), cartas(lid), nome)
    ultimo_sem[deck] = (lid, dia, jog)
    if porque:
        recusas.append((corrida, deck, h, (lid, dia, jog), porque))
    else:
        held[deck] = (lid, dia, jog)
        aceites += 1

print(f"trocas avaliadas desde {DESDE}: {aceites + len(recusas)} -> aceites {aceites}, recusadas {len(recusas)}")
for corrida, deck, h, c, porque in recusas:
    print(f"  {corrida} {deck:32s} fica #{h[0]} {h[2]} {h[1]}  | recusa #{c[0]} {c[2]} {c[1]}: {porque}")
print("\nreferencia final com a regra:")
for d, h in held.items():
    print(f"  {d:32s} #{h[0]} {h[2]} {h[1]}")
