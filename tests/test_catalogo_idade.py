"""O CATÁLOGO DO PC RECARREGA-SE QUANDO TEM MAIS DE 7 DIAS (2026-10-31).

O `daily._catalog` saltava sempre que o catálogo tinha >= 1000 impressões,
à espera de um «`sync-cards` semanal» que nada corria neste PC. O `catalog.db`
ficou parado de 06/10 a 31/10 sem um passo a falhar. Agora a data da última
carga vive na própria base (`catalog.catalogo_meta`, escrita pelo
`scryfall.load_bulk`) e o `_catalog` recarrega do bulk quando ela tem mais de
`daily.CATALOGO_MAX_DIAS` dias — ou quando não se sabe (um catálogo de antes de
31/10 não a guardava). Na cloud o catálogo vem vazio e recarrega-se sempre, como
antes.

Sem rede: o bulk é um .jsonl.gz de três linhas numa pasta temporária, posto no
`daily._BULK`, e o `scryfall.download_bulk` rebenta se for chamado. Fixa
`MTGVAULT_HOME`, `MTGVAULT_DB` e `MTGVAULT_CATALOG` antes do import (ver
`tests/_bateria.py`).
"""
import datetime as _dt
import gzip
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps({"caixas": [], "regras_por_formato": []}), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

import daily  # noqa: E402
from mtgvault import db, scryfall  # noqa: E402

_ABERTAS = []
NOVA = "Carta Nova do Bulk"


def _carta(i, nome, **k):
    c = {"id": f"00000000-0000-0000-0000-{i:012d}", "oracle_id": f"o-{i}",
         "name": nome, "set": "tst", "collector_number": str(i), "lang": "en",
         "layout": "normal", "oracle_text": "Texto.", "reserved": False}
    c.update(k)
    return c


def _bulk(cartas):
    p = Path(tempfile.mkdtemp()) / "default_cards.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for c in cartas:
            fh.write(json.dumps(c) + "\n")
    return p


BULK = _bulk([_carta(5001, NOVA), _carta(5002, "Outra Nova"),
              _carta(5003, "Terceira Nova", reserved=True)])


def _sem_rede(*_a, **_k):
    raise AssertionError("o teste não vai à rede: o bulk está no daily._BULK")


daily._BULK["path"] = BULK
scryfall.download_bulk = _sem_rede


def base_cheia():
    """Uma base com 1000 impressões e a metadata nova (reserved + oracle_text),
    como o catálogo deste PC: o `has_card_meta` diz sim e não força nada."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    linhas = [(f"id-{i}", f"o-{i}", f"Velha {i}", "old", "Old", str(i), "en", "common",
               "Creature", "Texto.", None, 1, "", "[]", "2026-01-01", None, None, None,
               "{}", 0, 0, 1 if i == 0 else 0, "core") for i in range(1000)]
    con.executemany(scryfall.INSERT, linhas)
    con.commit()
    assert db.catalog_size(con) == 1000 and scryfall.has_card_meta(con)
    return con


def _tem(con, nome):
    return con.execute("SELECT COUNT(*) FROM catalog.cards WHERE name = ?",
                       (nome,)).fetchone()[0] > 0


def _carimbar(con, dias_atras):
    d = (_dt.date.today() - _dt.timedelta(days=dias_atras)).isoformat()
    con.execute("INSERT OR REPLACE INTO catalog.catalogo_meta (chave, valor)"
                " VALUES ('carregado_em', ?)", (d,))
    con.commit()


def caso_um_catalogo_cheio_sem_data_recarrega():
    """É o catálogo deste PC a 31/10: cheio, com a metadata, e sem data de carga.
    O código antigo dizia «já existe — saltado» e a carta nova nunca entrava."""
    con = base_cheia()
    r = daily._catalog(con)
    assert _tem(con, NOVA), f"o catálogo não recarregou: {r!r}"
    assert "recarregado" in r, r
    assert scryfall.carregado_em(con) == _dt.date.today().isoformat()


def caso_um_catalogo_com_mais_de_7_dias_recarrega():
    con = base_cheia()
    _carimbar(con, daily.CATALOGO_MAX_DIAS + 1)
    r = daily._catalog(con)
    assert _tem(con, NOVA), f"um catálogo de 8 dias tem de recarregar: {r!r}"
    assert f"com {daily.CATALOGO_MAX_DIAS + 1} dias" in r, r


def caso_um_catalogo_fresco_nao_recarrega():
    """Recarregar todas as noites eram ~40 s por nada: até 7 dias salta, e diz
    há quantos dias foi."""
    con = base_cheia()
    _carimbar(con, daily.CATALOGO_MAX_DIAS)
    r = daily._catalog(con)
    assert not _tem(con, NOVA), f"um catálogo de 7 dias não recarrega: {r!r}"
    assert "saltado" in r and f"há {daily.CATALOGO_MAX_DIAS} dias" in r, r


def caso_a_idade_conta_a_partir_do_hoje_dado():
    con = base_cheia()
    _carimbar(con, 0)
    amanha_8 = _dt.date.today() + _dt.timedelta(days=8)
    assert scryfall.idade_dias(con, amanha_8) == 8
    r = daily._catalog(con, hoje=amanha_8)
    assert _tem(con, NOVA), r


def caso_a_cloud_continua_a_carregar_um_catalogo_vazio():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    r = daily._catalog(con)
    assert r == "3 impressões", r
    assert _tem(con, NOVA)


def caso_um_bulk_vazio_nao_carimba_o_catalogo_de_fresco():
    con = base_cheia()
    assert scryfall.load_bulk(con, _bulk([])) == 0
    assert scryfall.carregado_em(con) is None, \
        "um bulk sem linhas não pode adiar a recarga uma semana"


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    maus = 0
    for c in CASOS:
        try:
            c()
            print(f"  ok   {c.__name__}")
        except Exception as e:                                # noqa: BLE001
            maus += 1
            print(f"  FAIL {c.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        cm.__exit__(None, None, None)
    print(f"{len(CASOS) - maus}/{len(CASOS)} ok")
    sys.exit(1 if maus else 0)
