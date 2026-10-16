"""Prova que o `test_painel_decks` chumba sem as duas correcções (corre-se à mão).

Cada alvo carrega o módulo com UMA peça neutralizada e exige que o caso
correspondente levante AssertionError. Um processo por alvo não é preciso: as
substituições são feitas em módulos novos, nunca nos importados."""
import importlib.util
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))


def _modulo(nome, caminho, de, para):
    src = caminho.read_text(encoding="utf-8")
    assert de in src, f"o alvo já não existe em {caminho.name}: {de[:60]!r}"
    m = types.ModuleType(nome)
    m.__file__ = str(caminho)
    exec(compile(src.replace(de, para, 1), str(caminho), "exec"), m.__dict__)
    return m


def alvo(nome, troca):
    import test_painel_decks as t  # noqa: PLC0415
    from mtgvault import db, sources  # noqa: PLC0415
    orig = dict(sources=sys.modules["mtgvault.sources"], my=sys.modules.get("my_decks"))
    try:
        troca(t)
        tmp = Path(tempfile.mkdtemp())
        with db.session(tmp / "v.db", tmp / "c.db") as con:
            did = t.caso_a_gravacao_soma_as_entradas_repetidas(con)
            t.caso_reler_acerta_a_lista_curta_e_funde_a_duplicada(con, did)
            t.caso_a_troca_fica_no_historico_e_o_painel_escreve_os_ficheiros(con, tmp / "p")
    except AssertionError as e:
        print(f"CHUMBA  {nome}: {str(e)[:90]}")
        return True
    finally:
        t.sources = orig["sources"]
        if orig["my"]:
            t.my_decks = orig["my"]
    print(f"PASSA (mau)  {nome}")
    return False


def sem_historico(t):
    t.my_decks = _modulo("my_decks_x", RAIZ / "my_decks.py",
                         "    if antes or de:\n", "    if False:\n")
    import mtgvault.painel as p  # noqa: PLC0415
    sys.modules["my_decks"] = t.my_decks
    p  # o painel importa my_decks em tempo de chamada


def sem_soma(t):
    s = _modulo("sources_x", RAIZ / "mtgvault" / "sources.py",
                "    cards = somar_cartas(cards)\n    if not cards:", "    if not cards:")
    s.__name__ = "mtgvault.sources_x"
    t.sources = s


ok = all([alvo("sem_historico", sem_historico), alvo("sem_soma", sem_soma)])
print("\nTODOS CHUMBAM" if ok else "\nHÁ ALVOS QUE NÃO TRANCAM")
sys.exit(0 if ok else 1)
