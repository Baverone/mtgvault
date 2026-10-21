"""As duas decisões de caixas do André a 2026-10-21.

1. A caixa «Pioneer — Greasefang» passa à lista da Cudibunda de 19/10 (decklist
   29104), em vez da do Martin_Dominguez de 01/10 (fixada a 04/10). As versões e a
   alternativa ficam; a lista antiga não se apaga.
2. Caixa NOVA de Modern para o Grinding Station, com a lista do Alakai de 17/10
   (decklist 28370), FIXA — o mesmo caminho das outras caixas de lista de evento
   (`eventos.fixar`), por isso leva a proveniência e o link para a lista original.

Lê o `colecao_config.json` a sério (só leitura) e não abre a base.
"""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
_TMP = Path(tempfile.mkdtemp(prefix="caixas1021-"))
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")      # ver tests/_bateria.py

from mtgvault import caixas, configio, fotos  # noqa: E402

SLOT_GS = "modern-grinding-station"


def _real():
    return configio.ler(RAIZ / "colecao_config.json")


def caso_o_greasefang_usa_a_lista_da_cudibunda():
    cfg = _real()
    rec = cfg["listas_escolhidas"]["pioneer"]
    assert rec.get("fonte_decklist") == 29104, rec.get("fonte_decklist")
    ev = rec["evento"]
    assert ev["jogador"] == "Cudibunda" and ev["data"] == "2026-10-19", ev
    assert "mtgo.com/decklist/" in (ev.get("url") or ""), ev
    main = sum(q for b, _n, q in rec["cards"] if b == "main")
    side = sum(q for b, _n, q in rec["cards"] if b == "side")
    assert (main, side) == (60, 15), (main, side)
    assert ["main", "Lush Portico", 1] in rec["cards"]
    # nada se apaga: a do Martin_Dominguez fica arquivada, a alternativa e o
    # consenso anterior continuam no registo
    ant = cfg["listas_escolhidas"]["_pioneer-anterior-1021"]
    assert ant["evento"]["decklist_id"] == 23333, ant.get("evento")
    assert rec.get("alternativa", {}).get("decklist_id") == 22490
    assert rec.get("_consenso_anterior", {}).get("cards")
    cx = caixas.caixa_do_cfg(cfg, "pioneer")
    assert cx["fonte"] == "escolhido" and cx["ref"] == "pioneer", cx
    vp = {v["id"]: v for v in cfg["decks_por_formato"]["pioneer"]["versoes"]}
    assert vp["versao:pioneer:broodwagon"]["nome"] == "Abzan Greasefang"
    assert vp["versao:pioneer:mycosynth"]["nome"] == "Orzhov Monument"
    print("o Greasefang usa a lista da Cudibunda (29104)")


def caso_ha_caixa_de_grinding_station_com_a_lista_do_alakai():
    cfg = _real()
    slots = {s["slot"]: s for s in caixas.slots(cfg)}
    assert SLOT_GS in slots, "a caixa do Grinding Station não existe (ou saiu)"
    cx = caixas.caixa_do_cfg(cfg, SLOT_GS)
    assert cx["formato"] == "modern" and cx["fonte"] == "escolhido" and cx["ref"] == SLOT_GS, cx
    assert cx.get("balde") == "SPML", cx           # as regras de Modern (grupo SPML)
    rec = cfg["listas_escolhidas"][SLOT_GS]
    assert rec.get("padrao") is True, "lista fixa"
    assert rec.get("fonte_decklist") == 28370, rec.get("fonte_decklist")
    ev = rec["evento"]
    assert ev["jogador"] == "Alakai" and ev["data"] == "2026-10-17", ev
    assert (ev.get("url") or "").startswith("https://www.mtgo.com/decklist/"), ev
    main = sum(q for b, _n, q in rec["cards"] if b == "main")
    side = sum(q for b, _n, q in rec["cards"] if b == "side")
    assert (main, side) == (60, 15), (main, side)
    assert ["main", "Grinding Station", 1] in rec["cards"]
    # joga Mox Opal: entra na pasta comum da família, como as outras caixas Mox Opal
    assert fotos.familia_do_slot(SLOT_GS, cfg) is not None
    print("a caixa do Grinding Station existe com a lista do Alakai (28370)")


CASOS = (caso_o_greasefang_usa_a_lista_da_cudibunda,
         caso_ha_caixa_de_grinding_station_com_a_lista_do_alakai)


def main():
    for c in CASOS:
        c()


if __name__ == "__main__":
    main()
