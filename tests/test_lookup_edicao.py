"""O lookup sem edição deixa de inventar uma em silêncio.

`scryfall.find_printing` sem `set_code` terminava em
`ORDER BY released_at ASC LIMIT 1` e devolvia a impressão MAIS ANTIGA. Uma linha
de CSV com a edição em branco não dava erro nenhum: dava a edição errada, e para
as terras básicas dava sempre Alpha — foi assim que 5 Plains do Cloud cEDH
ficaram `lea #287`, 309,50 € de valor fantasma
(`work/revisao/mtgvault-edicoes-suspeitas.md`).

Este teste tranca os dois caminhos: por predefinição PARA (`EdicaoEmFalta`), e
com `adivinhar=True` escolhe a mais recente/barata e diz na `notes` que
adivinhou.
"""
import csv
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import collection, db, scryfall  # noqa: E402

# (set, nº, data, preço nonfoil) — o caso Alpha: a mais antiga é a mais cara.
PLAINS = [("lea", "287", "1993-08-05", 61.90),
          ("3ed", "295", "1994-04-11", 0.90),
          ("ody", "331", "2001-09-24", 0.40),
          ("fdn", "280", "2024-11-15", 0.05)]


def seed(con):
    for i, (s, cn, data, _preco) in enumerate(PLAINS):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,'or-plains','Plains',?,?,?,'en','common','Basic Land — Plains',
               0,'W',?,?,?,0)""",
            (f"pl-{s}", s, s.upper(), cn, json.dumps(["nonfoil"]), data, 100 + i))
    # duas artes do MESMO set recente: o desempate tem de ser determinista
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, cardmarket_id, digital)
           VALUES ('pl-fdn2','or-plains','Plains','fdn','FDN','281','en','common',
           'Basic Land — Plains',0,'W',?, '2024-11-15',199,0)""",
        (json.dumps(["nonfoil"]),))
    for sid, preco in [("pl-lea", 61.90), ("pl-3ed", 0.90), ("pl-ody", 0.40),
                       ("pl-fdn", 0.05), ("pl-fdn2", 0.12)]:
        con.execute(
            "INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, date, trend) "
            "VALUES (?,'cardmarket','nonfoil','2026-09-08',?)", (sid, preco))
    con.commit()


def run():
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "d.db", tmp / "cat.db") as con:
        seed(con)

        # 1. sem edição: PARA, e diz porquê
        try:
            scryfall.find_printing(con, "Plains")
            raise AssertionError("devolveu uma impressão sem ninguém dizer a edição")
        except scryfall.EdicaoEmFalta as e:
            assert str(e) == "edicao em falta: Plains", str(e)
        print("sem set_code levanta EdicaoEmFalta (o caso Alpha já não passa)")

        # continua a ser LookupError: quem já apanhava LookupError não muda
        assert issubclass(scryfall.EdicaoEmFalta, LookupError)

        # 2. com edição: continua a devolver a impressão pedida
        r = scryfall.find_printing(con, "Plains", "ody")
        assert r["scryfall_id"] == "pl-ody", dict(r)
        print("com set_code devolve a impressão pedida")

        # 3. adivinhar: a MAIS RECENTE e, dentro dessa data, a mais barata
        r = scryfall.find_printing(con, "Plains", adivinhar=True)
        assert r["set_code"] == "fdn" and r["collector_number"] == "280", dict(r)
        print("adivinhar dá a mais recente e mais barata, nunca a de Alpha")

        # 4. add_copy sem edição não insere NADA
        antes = con.execute("SELECT COUNT(*) c FROM copies").fetchone()["c"]
        try:
            collection.add_copy(con, "Plains", quantity=5)
            raise AssertionError("add_copy inventou uma edição")
        except scryfall.EdicaoEmFalta:
            pass
        assert con.execute("SELECT COUNT(*) c FROM copies").fetchone()["c"] == antes
        print("add_copy sem edição não insere nada")

        # 5. add_copy --adivinhar deixa a marca na cópia
        rid = collection.add_copy(con, "Plains", quantity=5, adivinhar=True)
        nota = con.execute("SELECT notes, scryfall_id FROM copies WHERE id = ?",
                           (rid,)).fetchone()
        assert nota["scryfall_id"] == "pl-fdn", nota["scryfall_id"]
        assert nota["notes"].startswith("edicao adivinhada em "), nota["notes"]
        assert "fdn #280" in nota["notes"], nota["notes"]
        print("adivinhada fica dita na notes da cópia:", nota["notes"])

        # 6. o CSV: a linha sem edição PARA com motivo, as outras entram
        csv_path = tmp / "lote.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=collection.CSV_FIELDS)
            w.writeheader()
            w.writerow({"name": "Plains", "set_code": "ody", "quantity": 7})
            w.writerow({"name": "Plains", "set_code": "", "quantity": 5})
        resultados = []
        ok, errs = collection.import_csv(con, csv_path, resultados=resultados)
        assert ok == 1, ok
        assert len(errs) == 1 and "motivo: edicao em falta" in errs[0], errs
        parada = [r for r in resultados if r["resultado"] == "erro"][0]
        assert parada["motivo"] == "edicao em falta: Plains", parada
        assert parada["linha"] == 3, parada
        print("no CSV, a linha sem edição para com 'motivo: edicao em falta'")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
