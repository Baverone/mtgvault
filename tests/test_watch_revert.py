"""Um baralho vigiado que VOLTA a uma lista anterior tem de continuar certo.

`watched_snapshots` tem UNIQUE (watched_id, list_hash), e a gravação era
`INSERT OR IGNORE`: quando o jogador voltava atrás numa alteração, a linha da
lista antiga era ignorada e ficava com a data ANTIGA. Como a lista "atual" é
sempre lida com `ORDER BY taken_at DESC, id DESC`, o site passava a mostrar a
versão abandonada como se fosse a de hoje — e o `diff` vinha ao contrário.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, watchlist  # noqa: E402

A = [("main", "Lightning Bolt", 4), ("main", "Lava Spike", 4)]
B = [("main", "Lightning Bolt", 4), ("main", "Chain Lightning", 4)]


def nomes(cards):
    return {c[1] for c in cards}


def run():
    tmp = Path(tempfile.mkdtemp()) / "d.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        wid = watchlist.add(con, "mtgo_player", "Luffy", "Burn do Luffy", "modern")

        assert watchlist._save_snapshot(con, wid, A) is True
        assert watchlist._save_snapshot(con, wid, B) is True
        # volta atrás: o conteúdo já existe em snapshot
        assert watchlist._save_snapshot(con, wid, A) is True, "a reversão é uma mudança"

        n = con.execute("SELECT COUNT(*) c FROM watched_snapshots "
                        "WHERE watched_id = ?", (wid,)).fetchone()["c"]
        assert n == 2, f"duas versões distintas, não {n}"

        atual = nomes(watchlist.latest_cards(con, wid))
        assert atual == nomes(A), f"a lista atual devia ser a A, veio {atual}"
        print("depois de reverter, latest_cards devolve a lista em vigor")

        d = watchlist.diff(con, wid)
        mudou = {c["card_name"]: c["delta"] for c in d["changes"]}
        assert mudou == {"Lava Spike": 4, "Chain Lightning": -4}, mudou
        print("o diff mostra a reversão no sentido certo (B -> A)")

        # gravar a mesma lista outra vez não cria linhas nem mexe no vault.db
        assert watchlist._save_snapshot(con, wid, A) is False
        assert con.execute("SELECT COUNT(*) c FROM watched_snapshots "
                           "WHERE watched_id = ?", (wid,)).fetchone()["c"] == 2
        print("lista igual à anterior não acrescenta nada")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
