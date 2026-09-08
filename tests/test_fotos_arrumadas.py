"""As fotos nunca se apagam depois de importar, e ficam ligadas à cópia.

As fotos de origem das cópias 1-156 (10 042 €) já não existem: o fluxo antigo
movia-as para uma pasta única e nada guardava a que cópia cada uma deu origem.
Quando apareceu a primeira suspeita de edição errada não houve nada para reler.

Agora: a foto vai para `pendentes/fotos processadas/<AAAA-MM>/` com o nome
original, a `copies.photo_path` passa a apontar para lá, e a ligação repete-se
no `aplicado.csv`. Uma foto cujas linhas não entraram todas fica em `pendentes/`
— arrumá-la escondia trabalho por fazer.
"""
import csv
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import collection, db  # noqa: E402


def seed(con):
    for i, (nome, s, cn) in enumerate([("Lightning Bolt", "tst", "1"),
                                       ("Sol Ring", "tst", "2")]):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,?,'Test Set',?,'en','rare','Instant',1,'R',?,
               '2020-01-01',?,0)""",
            (f"id-{i}", f"or-{i}", nome, s, cn, json.dumps(["nonfoil"]), 500 + i))
    con.commit()


def escrever_csv(path, linhas):
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=collection.CSV_FIELDS)
        w.writeheader()
        w.writerows(linhas)


def run():
    tmp = Path(tempfile.mkdtemp())
    pend = tmp / "pendentes"
    pend.mkdir()
    boa, mista = pend / "IMG_0001.jpg", pend / "IMG_0002.jpg"
    boa.write_bytes(b"\xff\xd8foto1")
    mista.write_bytes(b"\xff\xd8foto2")

    csv_path = tmp / "recat.csv"
    escrever_csv(csv_path, [
        # IMG_0001: as duas linhas entram -> a foto arruma-se
        {"name": "Lightning Bolt", "set_code": "tst", "quantity": 4,
         "sub_collection": "Colecção", "photo_path": "IMG_0001.jpg"},
        {"name": "Sol Ring", "set_code": "tst", "quantity": 1,
         "sub_collection": "Colecção", "photo_path": "IMG_0001.jpg"},
        # IMG_0002: uma das linhas não traz edição -> a foto FICA em pendentes/
        {"name": "Sol Ring", "set_code": "tst", "quantity": 1,
         "sub_collection": "Colecção", "photo_path": "IMG_0002.jpg"},
        {"name": "Lightning Bolt", "set_code": "", "quantity": 2,
         "sub_collection": "Colecção", "photo_path": "IMG_0002.jpg"},
    ])

    with db.session(tmp / "d.db", tmp / "cat.db") as con:
        seed(con)
        resultados = []
        ok, errs = collection.import_csv(con, csv_path, resultados=resultados)
        assert ok == 3 and len(errs) == 1, (ok, errs)
        fotos = collection.arrumar_fotos(con, resultados, pendentes=pend)

        mes = f"{dt.date.today():%Y-%m}"
        destino = pend / "fotos processadas" / mes / "IMG_0001.jpg"

        # 1. a foto está no sítio certo, com o nome original, e não se apagou
        assert destino.exists(), sorted(p.name for p in pend.rglob("*"))
        assert destino.read_bytes() == b"\xff\xd8foto1"
        assert not boa.exists(), "a foto ficou duplicada em pendentes/"
        assert fotos["movidas"] == 1 and fotos["destino"] == f"fotos processadas/{mes}"
        print(f"foto arrumada em 'pendentes/fotos processadas/{mes}/', nome original")

        # 2. a ligação foto -> cópia está na base
        rel = f"fotos processadas/{mes}/IMG_0001.jpg"
        ligadas = [dict(r) for r in con.execute(
            "SELECT id, photo_path FROM copies WHERE photo_path = ? ORDER BY id", (rel,))]
        assert len(ligadas) == 2, ligadas
        print("copies.photo_path aponta para a foto arrumada:", rel)

        # 3. e no aplicado.csv, ao lado das fotos
        aplicado = pend / "fotos processadas" / "aplicado.csv"
        with aplicado.open(encoding="utf-8", newline="") as fh:
            linhas = list(csv.DictReader(fh))
        assert {int(l["copy_id"]) for l in linhas} == {c["id"] for c in ligadas}, linhas
        assert all(l["foto"] == rel for l in linhas), linhas
        print("aplicado.csv liga cada foto às cópias que criou")

        # 4. a foto do lote incompleto FICA em pendentes/, por catalogar
        assert mista.exists(), "arrumou uma foto com linhas por resolver"
        assert fotos["ficaram"] == ["IMG_0002.jpg"], fotos["ficaram"]
        assert not (pend / "fotos processadas" / mes / "IMG_0002.jpg").exists()
        # e a cópia que ENTROU dessa foto não fica a apontar para um sítio errado
        pendente = con.execute(
            "SELECT photo_path FROM copies WHERE photo_path = 'IMG_0002.jpg'").fetchall()
        assert len(pendente) == 1, [dict(r) for r in pendente]
        print("a foto com linhas por resolver fica em pendentes/")

        # 5. correr outra vez não parte nem duplica (o lote já foi arrumado)
        outra = collection.arrumar_fotos(con, resultados, pendentes=pend)
        assert outra["movidas"] == 0 and outra["ligadas"] == 2, outra
        assert destino.exists()
        print("repetir é inofensivo: não move nada nem perde a foto")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
