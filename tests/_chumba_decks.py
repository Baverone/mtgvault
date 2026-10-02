"""Corre UM caso do `test_decks_finais` com a funcionalidade desligada.

`py tests/_chumba_decks.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o
`test_decks_finais` fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o
`MTGVAULT_DB` no import, e partilhá-los com outro teste era pôr um a mexer no
ambiente do outro.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  assinatura   — a CARTA-ASSINATURA deixa de identificar o deck: a selecção
                 passa a ser «todas as listas do formato», que é o que uma
                 etiqueta de clustering vaga dava;
  conjuncao    — o `assinatura_todas` é ignorado e volta a bastar UMA carta: o
                 Engineer Welder Cam passa a apanhar os decks que só jogam
                 Goblin Welder ou só Sewer-veillance Cam;
  so_que_contam — a R5 volta a usar o filtro de eventos do site: no Pauper e no
                 cEDH (com `tiers: []`) a reserva fica VAZIA, em silêncio;
  fora         — o botão «não é necessária» deixa de ser lido: a carta que ele
                 dispensou volta à reserva na corrida seguinte;
  sem_assinatura — uma caixa sem carta-assinatura volta a receber consenso (pela
                 assinatura DERIVADA da lista), que é o que a ordem proíbe para
                 o Artifacts Blue.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_decks_finais as T                                 # noqa: E402
from mtgvault import fases, sources                           # noqa: E402

if alvo == "assinatura":
    # A identidade deixa de ser a carta: apanha-se tudo o que é do formato.
    def _tudo(con, fmt, assinatura, todas=False, desde=None,
              so_que_contam=True, sem=None):
        cond, cp = (("(1=1)", []) if not so_que_contam
                    else sources.counting_sql(fmt, "d"))
        extra, ep = ("", [])
        if desde:
            extra, ep = " AND d.event_date >= ?", [desde]
        return [r[0] for r in con.execute(
            f"SELECT d.id FROM decklists d WHERE d.format = ? AND {cond}{extra}",
            (fmt, *cp, *ep))]

    sources.ids_por_assinatura = _tudo
elif alvo == "conjuncao":
    _ids = sources.ids_por_assinatura
    sources.ids_por_assinatura = (
        lambda con, fmt, assinatura, todas=False, desde=None, so_que_contam=True,
        sem=None: _ids(con, fmt, assinatura, False, desde, so_que_contam, sem))
elif alvo == "so_que_contam":
    _ids = sources.ids_por_assinatura
    sources.ids_por_assinatura = (
        lambda con, fmt, assinatura, todas=False, desde=None, so_que_contam=True,
        sem=None: _ids(con, fmt, assinatura, todas, desde, True, sem))
elif alvo == "fora":
    fases._retiradas = lambda s: {}
elif alvo == "sem_assinatura":
    # Sem carta escrita, volta-se a adivinhar pela lista — e uma caixa sem lista
    # passa a apanhar as listas mais parecidas que houver.
    _ld = fases._listas_do_deck

    def _adivinha(con, s, cache=None, desde=None):
        ids, nota, origem = _ld(con, s, cache, desde)
        if ids:
            return ids, nota, origem
        fmt = (s.get("formato") or "").lower()
        todos = [r[0] for r in con.execute(
            "SELECT id FROM decklists WHERE format = ?", (fmt,))]
        return todos, f"{len(todos)} listas do formato (adivinhado)", "adivinhada"

    fases._listas_do_deck = _adivinha
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

T.escreve_cfg()
getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
