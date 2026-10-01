"""As fotos nunca se apagam depois de importar, e ficam ligadas à cópia.

As fotos de origem das cópias 1-156 (10 042 €) já não existem: o fluxo antigo
movia-as para uma pasta única e nada guardava a que cópia cada uma deu origem.
Quando apareceu a primeira suspeita de edição errada não houve nada para reler.

Agora: a foto vai para **`data/fotos/<slot>/`** com o nome original (era
`pendentes/fotos processadas/<AAAA-MM>/`; mudou a 2026-10-01 — as fotos novas
ficam organizadas POR DECK, com o slot a vir do alvo da revalidação, e sem alvo
vão para `fotos/sem-alvo/<AAAA-MM>/`), a `copies.photo_path` passa a apontar
para lá, e a ligação repete-se no `aplicado.csv`. Uma foto cujas linhas não
entraram todas fica em `pendentes/` — arrumá-la escondia trabalho por fazer.
"""
import csv
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Fixa o ambiente ANTES do import: sem isto este teste lia o
# `colecao_config.json` a sério (a campanha de revalidação ligada) e, desde
# 2026-10-01, o `arrumar_fotos` escrevia as fotos no `data/` dele — ver a regra
# do `MTGVAULT_DB` no CLAUDE.md e o `tests/_bateria.py`.
_ENV = Path(tempfile.mkdtemp())
(_ENV / "cfg.json").write_text(json.dumps(
    {"baldes_coleccao": ["Colecção"], "caixas": [], "regras_colecao": {}}),
    encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_ENV / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_ENV)
os.environ["MTGVAULT_DB"] = str(_ENV / "vault.db")

from mtgvault import collection, db, fotos as fotos_mod  # noqa: E402


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
        # IMG_0001: as duas linhas entram -> a foto arruma-se. 3 + 1 = 4 cartas,
        # que é o tecto de 2026-10-01 («até 4 cartas por foto»).
        {"name": "Lightning Bolt", "set_code": "tst", "quantity": 3,
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
        # SEM ALVO não se adivinha o deck: a foto vai para `fotos/sem-alvo/<mês>`
        # (com alvo iria para `fotos/<slot>/` — ver `test_fotos_ate_4`).
        rel_dir = f"fotos/{fotos_mod.SEM_ALVO}/{mes}"
        destino = db.pasta_dados() / rel_dir / "IMG_0001.jpg"

        # 1. a foto está no sítio certo, com o nome original, e não se apagou
        assert destino.exists(), sorted(
            str(p) for p in db.pasta_dados().rglob("*"))
        assert destino.read_bytes() == b"\xff\xd8foto1"
        assert not boa.exists(), "a foto ficou duplicada em pendentes/"
        assert fotos["movidas"] == 1 and fotos["destinos"] == [rel_dir], fotos
        print(f"foto arrumada em 'data/{rel_dir}/', nome original")

        # 2. a ligação foto -> cópia está na base, e o resolvedor acha-a
        rel = f"{rel_dir}/IMG_0001.jpg"
        ligadas = [dict(r) for r in con.execute(
            "SELECT id, photo_path FROM copies WHERE photo_path = ? ORDER BY id", (rel,))]
        assert len(ligadas) == 2, ligadas
        assert fotos_mod.resolver(rel) == destino, fotos_mod.resolver(rel)
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
        assert not (db.pasta_dados() / rel_dir / "IMG_0002.jpg").exists()
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
