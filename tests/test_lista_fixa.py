"""A lista FIXA de um deck seguido, e o «aceite» da lista que o deck já tem
(André, 2026-10-21): *"fica a do Alakai 17/10 … tem de ficar fixa: a escolha
automática não pode voltar a trocá-la amanhã"* e *"fica a da Cudibunda, que já é
a actual: marca-a como aceite por ele"*. Bases temporárias com caminho explícito.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, painel  # noqa: E402
import my_decks  # noqa: E402
from test_bugs_ronda_1021 import _guardar, _lista  # noqa: E402

BASE = {"Grinding Station": 4, "Mox Opal": 4, "Emry, Lurker of the Loch": 4,
        "Sewer-veillance Cam": 4}


def _nota(con):
    return con.execute("SELECT notes FROM decks WHERE name = 'Grinding Station'").fetchone()[0]


def caso_a_fixada_nao_sai_com_listas_novas(con):
    gs = [s for s in my_decks.seguidos() if s["deck"] == "Grinding Station"][0]
    alakai = _guardar(con, "a", _lista(BASE, 4, "Ornithopter"), "2026-10-17", "Alakai")
    howa = _guardar(con, "h", _lista(BASE), "2026-10-19", "howa")
    con.commit()
    my_decks.refresh(con, hoje="2026-10-20")
    assert _nota(con).endswith(f"(#{howa})")
    r = my_decks.fixar(con, "Grinding Station", alakai, hoje="2026-10-21")
    assert "fixado" in r and _nota(con).endswith(f"(#{alakai})"), r
    assert "rejeitada" in my_decks.rejeitar(con, "Grinding Station", howa, hoje="2026-10-21")
    # uma lista nova que passaria o avaliar_troca (4 cópias de diferença)
    _guardar(con, "n", _lista(BASE, 4, "Memnite"), "2026-10-22", "outro")
    con.commit()
    assert gs["procura"](con)["id"] == alakai
    assert "já atual" in my_decks.refresh(con, hoje="2026-10-22")
    assert _nota(con).endswith(f"(#{alakai})"), "a escolha automática trocou a fixada"
    avisos = painel.construir(con, hoje="2026-11-30",
                              raiz=Path(tempfile.mkdtemp()))["avisos.json"]
    assert not any(a["deck"] == "Grinding Station" for a in avisos), avisos
    # no próprio dia do fixar: a troca é a decisão dele, sem «trocou de
    # arquétipo» nem «voltou a uma lista»
    avisos = painel.construir(con, hoje="2026-10-21",
                              raiz=Path(tempfile.mkdtemp()))["avisos.json"]
    assert not any(a["deck"] == "Grinding Station" and
                   ("trocadas de uma vez" in a["aviso"] or "voltou" in a["aviso"])
                   for a in avisos), avisos
    assert "ja estava fixado" in my_decks.fixar(con, "Grinding Station", alakai)
    # aceitar outra lista com a fixação de pé é recusado; soltar devolve a procura
    try:
        my_decks.aceitar(con, "Grinding Station", howa)
        raise AssertionError("aceitar outra lista devia recusar com a fixação de pé")
    except ValueError:
        pass
    assert "levantada" in my_decks.soltar(con, "Grinding Station", hoje="2026-10-23")
    assert my_decks.fixada(con, "Grinding Station", "modern") is None
    assert gs["procura"](con)["id"] != alakai
    print("fixada: listas novas não a trocam; soltar devolve a procura automática")


def caso_aceitar_a_lista_actual_fica_escrito(con):
    gs = [s for s in my_decks.seguidos() if s["deck"] == "Grinding Station"][0]
    actual = gs["procura"](con)["id"]
    my_decks.refresh(con, hoje="2026-10-24")
    r = my_decks.aceitar(con, "Grinding Station", actual, hoje="2026-10-24")
    assert "aceite" in r, r
    t = con.execute("SELECT motivo, para_decklist_id FROM deck_lista_trocas "
                    "ORDER BY id DESC LIMIT 1").fetchone()
    assert tuple(t) == ("aceite", actual), tuple(t)
    print("aceitar a lista que o deck já tem grava motivo = 'aceite'")


def run():
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        caso_a_fixada_nao_sai_com_listas_novas(con)
        caso_aceitar_a_lista_actual_fica_escrito(con)
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
