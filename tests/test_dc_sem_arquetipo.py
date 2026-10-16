"""O Duel Commander não tem `archetype_id`, e o deck seguido não depende dele
(2026-10-16).

Medido nesse dia: 285 de 285 listas de Duel Commander desde 01/10 sem
`archetype_id`. Não é avaria: o formato saiu do `daily.ANALYSE_FORMATS` a
2026-09-07, e a identidade de um deck de comandante é o COMANDANTE. O aviso
diário *"sem lista de McWinSauce com ['Cloud, Midgar Mercenary']"* também não
vinha daí: a última lista dele é de 2026-08-31 e a poda de 30 dias apagou-a a
2026-10-02, que é exactamente o primeiro dia do aviso no `job_runs`.

Este ficheiro tranca as duas coisas: (1) a procura do deck seguido por
jogador + comandante encontra uma lista SEM arquétipo; (2) quando não há lista,
o aviso diz qual é a que fica e de quando, em vez de parecer uma avaria.
Tudo numa base temporária com caminho explícito.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, sources  # noqa: E402
import my_decks  # noqa: E402

DECK = "Cloud (Duel Commander)"
CLOUD = "Cloud, Midgar Mercenary"


def _lista(n_extra=99):
    return [("main", CLOUD, 1)] + [("main", f"Carta {i}", 1) for i in range(n_extra)]


def _cloud():
    return [s for s in my_decks.seguidos() if s["deck"] == DECK][0]


def caso_a_procura_nao_depende_do_arquetipo(con):
    did = sources.store_decklist(
        con, source="mtgo", source_key="dc1", fmt="duel-commander", cards=_lista(),
        event_name="Duel Commander League", event_date="2026-10-10",
        player="McWinSauce", commander=CLOUD)
    assert did, "a liga de Duel Commander tem de se guardar (o formato conta ligas)"
    con.commit()
    aid = con.execute("SELECT archetype_id FROM decklists WHERE id = ?", (did,)).fetchone()[0]
    assert aid is None, "o Duel Commander não se agrupa: a lista nasce sem arquétipo"
    achada = _cloud()["procura"](con)
    assert achada is not None and achada["id"] == did, \
        "o deck seguido por jogador + comandante não pode depender do archetype_id"
    out = my_decks.refresh(con, hoje="2026-10-10")
    assert f"{DECK}: atualizado -> 2026-10-10 McWinSauce" in out, out
    print("procura por jogador + comandante encontra a lista sem arquétipo")
    return did


def caso_sem_lista_diz_qual_fica(con, did):
    # a poda leva a lista; a `decks` fica com ela e com a nota
    con.execute("DELETE FROM decklist_cards WHERE decklist_id = ?", (did,))
    con.execute("DELETE FROM decklists WHERE id = ?", (did,))
    con.commit()
    out = my_decks.refresh(con, hoje="2026-11-12")
    linha = [p for p in out.split("; ") if p.startswith(DECK)][0]
    assert "sem lista de McWinSauce" in linha, linha
    # o texto é o do `main` (a7a48a5): o ramo do mesmo dia escreveu a mesma
    # linha com outra forma, e no merge ficou a que já estava publicada.
    assert f"(fica a de 2026-10-10, McWinSauce #{did})" in linha, linha
    print("sem lista: o aviso diz a que fica e de quando —", linha)


def run():
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        did = caso_a_procura_nao_depende_do_arquetipo(con)
        caso_sem_lista_diz_qual_fica(con, did)
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
