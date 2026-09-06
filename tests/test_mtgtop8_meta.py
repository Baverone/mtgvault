"""Um nn/nn/nn que não é data não pode matar a recolha do formato inteiro.

`parse_event_meta` construía a data com `date(2000+y, mth, d)` sobre a PRIMEIRA
sequência nn/nn/nn da página. O `harvest` só protege os pedidos HTTP, por isso
um ValueError aqui subia e abortava a recolha de todos os eventos daquele
formato — o passo diário ficava com um erro em vez de listas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import mtgtop8  # noqa: E402

# Trecho no formato das páginas de evento do mtgtop8 (data dd/mm/yy).
BOM = "<title>MTGO Duel Commander League @ MTGO</title> ... 128 players ... 22/07/26"

# O mesmo, mas com um nn/nn/nn que não é data nenhuma antes da data verdadeira
# (rácios, resultados de ronda, versões — a página tem muito número solto).
MAU = ("<title>Paper Duel Commander @ Lyon</title> ... 64 players ... "
       "ratio 13/45/99 ... 22/07/26")

SEM_DATA = "<title>Evento sem data @ sitio</title> ... 12 players ..."


def run():
    bom = mtgtop8.parse_event_meta(BOM)
    assert bom["event_date"] == "2026-07-22", bom
    assert bom["players"] == 128, bom
    assert bom["event_name"] == "MTGO Duel Commander League", bom
    print("página normal: nome, data e nº de jogadores")

    mau = mtgtop8.parse_event_meta(MAU)          # antes: ValueError
    assert mau["event_date"] == "2026-07-22", mau
    assert mau["players"] == 64, mau
    print("nn/nn/nn impossível é saltado, a data verdadeira continua a ser lida")

    sem = mtgtop8.parse_event_meta(SEM_DATA)
    assert sem["event_date"] is None, sem
    print("sem data na página devolve None (o harvest usa a data de hoje)")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
