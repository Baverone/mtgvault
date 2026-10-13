"""AS QUATRO REGRAS DA FOTOGRAFIA (André, 2026-10-13, à letra).

  *"vou sempre fotografar as cartas até ao playset
   caso peça apenas 2x e eu tenho playset, eu vou fotografar playset
   caso peça playset e eu so fotografar 2x, é porque só tenho 2x
   caso vários decks peçam a mesma carta, e eu coloque em diferentes pastas a
   mesma carta, é porque tenho multiplos da carta"*

A regra por baixo das quatro: **o `(N)` do nome da pasta é o que o DECK PEDE;
a quantidade é a da FOTO.** É a «foto manda» de 02/10 estendida à quantidade.
Um caso por ponto:

  1. pasta `(2)`, foto com 4 → entram 4, o deck leva 2 e as outras 2 ficam sem
     deck (nunca recusada, nunca juntada à alocação do deck);
  2. pasta `(4)`, foto com 2 → entram 2, o deck fica a dever 2, e a pasta NÃO
     volta a ser pedida por a conta não bater com o `(N)`;
  3. a mesma carta em duas pastas de deck → DUAS cópias, uma em cada deck, e
     isso não é a «segunda alocação da mesma cópia» que o caso 5 do
     `test_foto_manda` recusa (que continua a recusar);
  4. o playset cabe na foto de até 4 cartas: uma pasta `(2)` não recusa uma
     foto de 4.

A prova de que chumbam está em `tests/_chumba_foto_ate_playset.py`. Fixa
`MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

CAIXAS = [
    {"slot": "cedh-blue-farm", "nome": "Blue Farm", "formato": "cedh",
     "fonte": "deck", "ref": "BF", "balde": "Colecção", "estado": "montada",
     "prioridade": 1},
    {"slot": "cedh-cloud", "nome": "Cloud cEDH", "formato": "cedh",
     "fonte": "deck", "ref": "CL", "balde": "Colecção", "estado": "montada",
     "prioridade": 2},
]
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": "2026-09-20", "alvo": None, "foto_manda": True},
    "reserva": {"janela_dias": 30},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, confirmado, db, fotocaixa,  # noqa: E402
                      fotos, fotosite, loadout, sources)

SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)
fotocaixa.RAIZ = SITE
PEND = fotosite.pasta_pendentes(SITE)
POR = fotos.pasta_novas(SITE)
FEITOS = fotos.pasta_processados(SITE)
SWORDS = "Swords to Plowshares"
_ABERTAS = []


def escreve_cfg(**mudancas):
    d = json.loads(json.dumps(CFG))
    for k, v in mudancas.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()


def base(pede=None):
    """Base nova; `pede` = {ref: quantas Swords o deck pede}."""
    pede = {"BF": 2, "CL": 2} if pede is None else pede
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, legalities, digital, reserved)
           VALUES ('id-sw','or-sw',?,'4ed','4ED set','1','en','rare','Instant',1,
                   'W','["nonfoil"]','1995-04-01','{}',0,0)""", (SWORDS,))
    con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, "
                "date, trend, low) VALUES ('id-sw', 'cardmarket', 'nonfoil', "
                "'2026-10-13', 1.5, 1.5)")
    for ref in ("BF", "CL"):
        con.execute("INSERT INTO decks (name, format) VALUES (?, 'cedh')", (ref,))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (ref,)).fetchone()["id"]
        if pede.get(ref):
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?, ?, ?, 'main')", (did, SWORDS, pede[ref]))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def csv_de(linhas, nome):
    campos = ["name", "set_code", "collector_number", "quantity", "finish",
              "language", "condition", "sub_collection", "photo_path"]
    out = [",".join(campos)]
    for l in linhas:
        out.append(",".join(str(l.get(c, "")) for c in campos))
    p = _TMP / nome
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def linha(foto, q):
    return {"name": SWORDS, "set_code": "4ed", "collector_number": "1",
            "quantity": q, "finish": "nonfoil", "language": "en",
            "condition": "", "sub_collection": "Colecção", "photo_path": foto}


def importar(con, linhas, nome):
    res: list[dict] = []
    collection.import_csv(con, csv_de(linhas, nome), resultados=res)
    return res


def copias(con):
    return [dict(r) for r in con.execute(
        "SELECT id, quantity, photo_path FROM copies ORDER BY id")]


def alocacoes(con):
    return {(r["copy_id"], r["slot"]): r["quantity"] for r in con.execute(
        "SELECT copy_id, slot, quantity FROM copy_allocation")}


def linha_do_deck(rep, slot):
    s = next(x for x in rep["slots"] if x["slot"] == slot)
    ls = [m for m in list(s.get("have") or []) + list(s.get("missing") or [])
          if m["nm"] == SWORDS]
    return s, ls


def jpg(p: Path, mtime: float = 1_700_000_000) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    os.utime(p, (mtime, mtime))
    return p


def limpar():
    import shutil
    for d in (POR, FEITOS, PEND):
        if d.exists():
            shutil.rmtree(d)
    fotos._CACHE.clear()


def recolher_uma(pasta_carta: str, deck: str = "Blue Farm") -> str:
    """Larga UMA foto em `Decks Por Processar/<deck>/<pasta_carta>/` e recolhe-a
    como a tarefa das 02:30. Devolve o nome que ela ganhou em `pendentes/`."""
    jpg(POR / deck / pasta_carta / "IMG_0001.jpg")
    r = fotos.recolher_das_pastas(raiz=SITE, agora=time.time())
    assert len(r["recolhidas"]) == 1, r
    return r["recolhidas"][0]["para"]


# ===========================================================================
# 1. PASTA (2), FOTO COM 4 → ENTRAM 4; O DECK LEVA 2; AS OUTRAS FICAM SEM DECK
# ===========================================================================
def caso_pasta_2_foto_com_4_entram_4_e_o_deck_leva_2():
    """*"caso peça apenas 2x e eu tenho playset, eu vou fotografar playset"*.

    Não é erro, não se recusa, e as duas a mais NÃO se juntam à alocação do
    deck: até 13/10 a `alocar_por_foto` metia o lote inteiro no deck da pasta.
    E a pasta da carta apaga-se quando a foto entra — com 4 numa pasta (2)."""
    escreve_cfg()
    limpar()
    con = base({"BF": 2})
    nome = recolher_uma("Swords to Plowshares (2)")
    res = importar(con, [linha(nome, 4)], "r1.csv")
    assert res[0]["resultado"] == "importada", res
    cs = copias(con)
    assert sum(c["quantity"] for c in cs) == 4, f"tinham de entrar as 4: {cs}"
    cid = int(res[0]["copy_id"])
    assert alocacoes(con) == {(cid, "cedh-blue-farm"): 2}, (
        f"o deck leva o que PEDE (2), não o lote: {alocacoes(con)}")
    a = collection.arrumar_fotos(con, res, pendentes=PEND)
    assert a["pastas_apagadas"] == ["Blue Farm/Swords to Plowshares (2)"], a
    rep = loadout.report(con)
    s, ls = linha_do_deck(rep, "cedh-blue-farm")
    assert sum(m.get("got") or 0 for m in ls) == 2, ls
    assert s["pct"] == 100, s["pct"]
    # E com a foto a NÃO mandar (o config dele hoje), entram na mesma as 4.
    escreve_cfg(revalidacao={"desde": None, "foto_manda": False})
    limpar()
    con = base({"BF": 2})
    res = importar(con, [linha("site-cedh-blue-farm-20261013-100000-1.jpg", 4)],
                   "r1b.csv")
    assert res[0]["resultado"] == "importada", res
    assert sum(c["quantity"] for c in copias(con)) == 4, copias(con)
    escreve_cfg()
    print("pasta (2) + foto de 4: entraram 4, o deck leva 2, a pasta apagou-se")


# ===========================================================================
# 2. PASTA (4), FOTO COM 2 → ENTRAM 2; O DECK DEVE 2; A PASTA NÃO VOLTA
# ===========================================================================
def caso_pasta_4_foto_com_2_o_deck_fica_a_dever_2_e_a_pasta_nao_volta():
    """*"caso peça playset e eu so fotografar 2x, é porque só tenho 2x"*.

    Nada presume as outras duas: a falta é 2. E o gerador das pastas de carta
    (5c1b9ec) NÃO volta a criar `Swords to Plowshares (4)` por a contagem não
    bater — ela apaga-se quando a foto entra, e volta só se a prova cair a zero.
    """
    escreve_cfg()
    limpar()
    con = base({"BF": 4})
    nome = recolher_uma("Swords to Plowshares (4)")
    res = importar(con, [linha(nome, 2)], "r2.csv")
    assert res[0]["resultado"] == "importada", res
    assert not any(r["resultado"] == "erro" for r in res), res
    assert sum(c["quantity"] for c in copias(con)) == 2, copias(con)
    cid = int(res[0]["copy_id"])
    assert alocacoes(con) == {(cid, "cedh-blue-farm"): 2}, alocacoes(con)
    a = collection.arrumar_fotos(con, res, pendentes=PEND)
    assert a["pastas_apagadas"] == ["Blue Farm/Swords to Plowshares (4)"], a
    assert not list(PEND.glob("*.jpg")), "a foto não fica em pendentes/"
    rep = loadout.report(con)
    s, ls = linha_do_deck(rep, "cedh-blue-farm")
    assert sum(m.get("got") or 0 for m in ls) == 2, ls
    falta = sum((m.get("comprar") or 0) + (m.get("fotografar") or 0) for m in ls)
    assert falta == 2, f"a falta é 2, nem mais nem menos: {ls}"
    # O GERADOR: três passagens, nenhuma recria a pasta.
    fotos.garantir_pastas(rep, SITE)
    for _ in range(3):
        r = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
        assert r["criadas"] == [], f"a pasta voltou por a conta não bater: {r}"
    assert not (POR / "Blue Farm" / "Swords to Plowshares (4)").exists()
    # …mas volta quando a prova cai a ZERO (uma correcção), como sempre.
    con.execute("UPDATE copies SET nao_encontrada_em = '2026-10-13' WHERE id = ?",
                (cid,))
    con.commit()
    r = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r["criadas"] == ["Blue Farm/Swords to Plowshares (4)"], r
    print("pasta (4) + foto de 2: entraram 2, o deck deve 2, a pasta não volta")


# ===========================================================================
# 3. A MESMA CARTA EM DUAS PASTAS DE DECK = DUAS CÓPIAS
# ===========================================================================
def _duas_pastas(con):
    return importar(con, [
        linha("site-cedh-blue-farm-20261013-100000-1.jpg", 2),
        linha("site-cedh-cloud-20261013-100500-1.jpg", 2),
    ], "r3.csv")


def caso_a_mesma_carta_em_duas_pastas_sao_duas_copias():
    """*"caso vários decks peçam a mesma carta, e eu coloque em diferentes pastas
    a mesma carta, é porque tenho multiplos da carta"*.

    Uma cópia NOVA por pasta, cada uma no seu deck. Nunca se desduplica nem se
    funde, e não é a «segunda alocação da mesma cópia» (caso 5 do
    `test_foto_manda`): essa defende UMA cópia em dois decks; aqui são DUAS. Por
    isso a trava não pode ser chamada a recusar nada — um espião prova-o."""
    for manda in (True, False):
        escreve_cfg(revalidacao=({} if manda else
                                 {"desde": None, "foto_manda": False}))
        con = base({"BF": 2, "CL": 2})
        recusas = []
        reais = (confirmado.exige_uma_so, confirmado.exige_alocacao_unica)

        def espia(real):
            def f(*a, **k):
                try:
                    return real(*a, **k)
                except confirmado.AlocacaoDupla as e:
                    recusas.append(str(e))
                    raise
            return f
        confirmado.exige_uma_so = espia(reais[0])
        confirmado.exige_alocacao_unica = espia(reais[1])
        try:
            res = _duas_pastas(con)
        finally:
            confirmado.exige_uma_so, confirmado.exige_alocacao_unica = reais
        assert [r["resultado"] for r in res] == ["importada", "importada"], res
        assert not recusas, recusas
        cs = copias(con)
        assert len(cs) == 2 and [c["quantity"] for c in cs] == [2, 2], (
            f"duas cópias de 2, nunca uma de 4 nem uma de 2: {cs}")
        a, b = (int(r["copy_id"]) for r in res)
        assert a != b, res
        if manda:
            assert alocacoes(con) == {(a, "cedh-blue-farm"): 2,
                                      (b, "cedh-cloud"): 2}, alocacoes(con)
            assert not confirmado.conflitos(con), confirmado.conflitos(con)
        rep = loadout.report(con)
        for slot in ("cedh-blue-farm", "cedh-cloud"):
            s, ls = linha_do_deck(rep, slot)
            assert sum(m.get("got") or 0 for m in ls) == 2, (slot, ls)
    escreve_cfg()
    print("a mesma carta em duas pastas: duas cópias, uma em cada deck, sem recusa")


def caso_o_caso_5_continua_a_defender_uma_copia_em_dois_decks():
    """A outra direcção: com as duas cópias da regra 3 na base, alocar a cópia
    do Blue Farm TAMBÉM ao Cloud continua a ser recusado. A regra 3 não
    enfraqueceu a trava — são duas perguntas sobre coisas diferentes."""
    escreve_cfg()
    con = base({"BF": 2, "CL": 2})
    res = _duas_pastas(con)
    a = int(res[0]["copy_id"])
    try:
        confirmado.exige_uma_so(con, a, "cedh-cloud", 1)
    except confirmado.AlocacaoDupla:
        pass
    else:
        raise AssertionError("a mesma cópia em dois decks tinha de ser recusada")
    print("o caso 5 continua a recusar UMA cópia em dois decks")


# ===========================================================================
# 4. O PLAYSET CABE NUMA FOTO DE ATÉ 4 CARTAS
# ===========================================================================
def caso_o_playset_cabe_na_foto_e_a_pasta_2_nao_recusa_4():
    """*"vou sempre fotografar as cartas até ao playset"* contra *"até 4 cartas
    por foto"* (01/10): um playset são 4 cartas, é UMA foto, e cabe. O pior
    caminho é o da campanha ligada com uma cópia por revalidar daquela impressão
    — é aí que a trava das 4 cartas RECUSA (`motivo_demasiadas`). Uma foto de 4
    numa pasta (2) tem de passar."""
    escreve_cfg()
    assert fotos.valida(4) and not fotos.valida(5)
    con = base({"BF": 2})
    velha = collection.add_copy(con, SWORDS, set_code="4ed", collector_number="1",
                                quantity=4, sub_collection="Colecção")
    con.execute("UPDATE copies SET validado_em = NULL WHERE id = ?", (velha,))
    con.commit()
    res = importar(con, [linha("site-cedh-blue-farm-20261013-110000-1.jpg", 4)],
                   "r4.csv")
    assert res[0]["resultado"] == "importada", f"a pasta (2) recusou 4: {res}"
    assert sum(c["quantity"] for c in copias(con)) == 4, copias(con)
    assert alocacoes(con) == {(velha, "cedh-blue-farm"): 2}, alocacoes(con)
    print("um playset é uma foto: a pasta (2) aceita a foto de 4")


CASOS = (caso_pasta_2_foto_com_4_entram_4_e_o_deck_leva_2,
         caso_pasta_4_foto_com_2_o_deck_fica_a_dever_2_e_a_pasta_nao_volta,
         caso_a_mesma_carta_em_duas_pastas_sao_duas_copias,
         caso_o_caso_5_continua_a_defender_uma_copia_em_dois_decks,
         caso_o_playset_cabe_na_foto_e_a_pasta_2_nao_recusa_4)


def main():
    for c in CASOS:
        c()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001
            pass
    print(f"\nOK — {len(CASOS)} casos (até ao playset)")


if __name__ == "__main__":
    main()
