"""`deck-add` sobre um deck que já existe tem de escrever NESSE deck.

O comando decidia o id com `cur.lastrowid or <SELECT>` depois de um
`INSERT OR IGNORE`. Quando o insert é ignorado, o SQLite não devolve zero:
devolve o rowid do último insert bem sucedido da LIGAÇÃO. Hoje o erro está
mascarado — a CLI abre uma ligação nova por comando, e nessa ligação ainda não
houve inserção nenhuma, por isso o lastrowid sai 0 e o `or` salva o dia. Basta
alguém chamar isto de dentro de um processo mais longo (a app web local, por
exemplo) para as cartas irem parar ao deck errado.

Este teste pina as duas pontas: a semântica do sqlite3 que torna o `or` errado,
e o comportamento do comando visto de fora.
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import cli, db  # noqa: E402

LISTA_A = "4 Lightning Bolt\n4 Lava Spike\n"
LISTA_A2 = "4 Lightning Bolt\n4 Chain Lightning\n"
LISTA_B = "4 Brainstorm\n4 Ponder\n"


def _escreve(pasta, nome, texto):
    p = pasta / nome
    p.write_text(texto, encoding="utf-8")
    return str(p)


def cartas(con, deck):
    return {r["card_name"] for r in con.execute(
        "SELECT dc.card_name FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id "
        "WHERE d.name = ?", (deck,))}


def semantica_do_sqlite():
    """Um INSERT OR IGNORE ignorado deixa lastrowid a apontar para a linha
    ANTERIOR. Só o rowcount distingue 'inseri' de 'não inseri'."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, n TEXT UNIQUE)")
    con.execute("INSERT OR IGNORE INTO t (n) VALUES ('a')")
    con.execute("INSERT OR IGNORE INTO t (n) VALUES ('b')")
    cur = con.execute("INSERT OR IGNORE INTO t (n) VALUES ('a')")
    assert cur.rowcount == 0, cur.rowcount
    assert cur.lastrowid == 2, cur.lastrowid   # o 'b', não o 'a' e muito menos 0
    print("sqlite: INSERT OR IGNORE ignorado -> rowcount 0 mas lastrowid da linha anterior")


def run():
    semantica_do_sqlite()

    pasta = Path(tempfile.mkdtemp())
    vault, cat = pasta / "d.db", pasta / "cat.db"
    argv = ["--db", str(vault), "--catalog", str(cat)]

    cli.main(argv + ["deck-add", "Burn", "modern", _escreve(pasta, "a.txt", LISTA_A)])
    cli.main(argv + ["deck-add", "Delver", "legacy", _escreve(pasta, "b.txt", LISTA_B)])
    cli.main(argv + ["deck-add", "Burn", "modern", _escreve(pasta, "a2.txt", LISTA_A2)])

    with db.session(vault, cat) as con:
        burn, delver = cartas(con, "Burn"), cartas(con, "Delver")
        assert delver == {"Brainstorm", "Ponder"}, f"Delver contaminado: {delver}"
        assert "Chain Lightning" in burn, f"a lista nova não chegou ao Burn: {burn}"
        assert con.execute("SELECT COUNT(*) c FROM decks").fetchone()["c"] == 2
        print(f"deck-add repetido escreve no proprio deck (Burn={len(burn)} cartas)")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
