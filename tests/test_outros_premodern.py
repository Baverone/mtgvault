"""A PASTA «OUTROS (JOGAM PREMODERN)» (André, 2026-10-16, à letra).

*"para além das cartas que jogam nos decks que estou a montar, quero que me
indiques, dentro do premodern, um género de pasta «outros» com cartas que jogam
premodern, estão em decks que eu não estou a montar, mas caso eu tenha essas
cartas coloco lá as fotografias e já sabes que eu as tenho"*.

O que se tranca aqui:

1. a pasta é um ALVO PRÓPRIO (`outros`) e não os Extras: a foto prova a carta e
   NUNCA mexe na alocação (nos Extras tira-a — caso 4 do `test_foto_manda`);
2. o critério é a UNIÃO DOS NÚCLEOS dos arquétipos elegíveis que não são caixa,
   menos o que os decks dele pedem e menos as básicas;
3. a pasta NÃO conta para «o que falta fotografar», não é órfã, as pastas de
   carta não levam `(N)`, a vazia de uma carta que um deck passou a pedir sai, a
   com fotos fica, e a de uma carta que ele já tem não nasce;
4. as regras de combo de 16/10 (Hermit Druid, Aluren e Rector antes do
   Stiflenought, Frantic Storm, Balancing Tings, o en-Kor Life, o Reanimator
   sem Psychatog).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

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
    "caixas": [{"slot": "cedh-blue-farm", "nome": "Blue Farm", "formato": "cedh",
                "fonte": "deck", "ref": "BF", "balde": "Colecção",
                "estado": "montada", "prioridade": 1}],
    "revalidacao": {"desde": None, "alvo": None},
    "reserva": {"limiar_pct": 20},
    "premodern": {"outros": {"nucleo_pct": 50, "incluir": ["Sligh"],
                             "excluir": ["Full English Breakfast"]}},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, confirmado, db, fotocaixa, fotos,  # noqa: E402
                      fotosite, loadout, premodern)

SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)
fotocaixa.RAIZ = SITE
POR = fotos.pasta_novas(SITE)
OUT = POR / fotos.PASTA_OUTROS
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, rl) in enumerate((("Swords to Plowshares", 0), ("Mogg Fanatic", 0),
                                  ("Cursed Scroll", 1), ("Goblin Lackey", 0))):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,'tmp','TMP',?,'en','rare','Creature',1,'R','["nonfoil"]',
                       '1997-10-14','{}',0,?)""",
            (f"id-{i}", f"or-{nm}", nm, str(i), rl))
    con.execute("INSERT INTO decks (name, format) VALUES ('BF', 'cedh')")
    did = con.execute("SELECT id FROM decks WHERE name = 'BF'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Swords to Plowshares', 4, 'main')", (did,))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def foto(p: Path, mtime: float = 1_700_000_000) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    os.utime(p, (mtime, mtime))
    return p


def _o(cartas):
    return {"alvos": [{"nome": "Goblins", "n_lists": 18, "nucleo": 3,
                       "pct_nos_meus_decks": 0}],
            "cartas": {nm: {"q": 4, "arquetipos": ["Goblins"], "pct": 80}
                       for nm in cartas},
            "nucleo_pct": 50, "limiar": 50}


# ===========================================================================
# 1. UM ALVO PRÓPRIO, QUE NÃO MEXE NA ALOCAÇÃO
# ===========================================================================
def caso_a_pasta_e_um_alvo_proprio_que_nao_tira_alocacao():
    a = fotos.alvo_da_pasta(OUT / "Mogg Fanatic" / "x.jpg")
    assert a == {"tipo": fotos.ALVO_OUTROS, "slot": None}, a
    nome = fotosite.nome_ficheiro("outros", None, dt.datetime(2026, 10, 16, 9, 0), 1, "jpg")
    assert nome == "site-outros-20261016-090000-1.jpg", nome
    o = fotosite.origem(nome)
    assert o["tipo"] == "outros" and o["slot"] is None, o
    # A diferença que importa: nos Extras a foto DECIDE (tira a alocação); aqui não.
    assert confirmado.alvo_da_pasta(nome) == (False, None)
    assert confirmado.alvo_da_pasta("site-colecao-20261016-090000-1.jpg") == (True, None)
    # E arruma-se na mesma pasta em «Decks Processados».
    assert fotos.pasta_do_alvo(o, SITE).name == fotos.PASTA_OUTROS
    print("Outros é alvo próprio: prova a carta e não tira alocação (os Extras tiram)")


# ===========================================================================
# 2. O CRITÉRIO: A UNIÃO DOS NÚCLEOS, MENOS OS MEUS DECKS
# ===========================================================================
def caso_o_criterio_e_a_uniao_dos_nucleos_menos_os_meus_decks():
    # núcleo = 50 % ou mais das listas, mediana das cópias (arredondada para
    # cima, tecto 4), básicas fora
    listas = [{"Goblin Lackey": 4, "Mogg Fanatic": 2, "Mountain": 18},
              {"Goblin Lackey": 4, "Mogg Fanatic": 3, "Pyrokinesis": 1},
              {"Goblin Lackey": 3, "Pyrokinesis": 1},
              {"Goblin Lackey": 4}]
    nu = premodern.nucleo_das_listas(listas, 50)
    assert set(nu) == {"Goblin Lackey", "Mogg Fanatic", "Pyrokinesis"}, nu
    assert nu["Goblin Lackey"] == (1.0, 4) and nu["Mogg Fanatic"][1] == 3, nu
    burn = premodern.nucleo_das_listas([{"Mogg Fanatic": 4, "Lightning Bolt": 4}], 50)
    u = premodern.uniao_dos_nucleos([("Goblins", nu), ("Burn", burn)],
                                    {"Pyrokinesis": "Terrageddon"})
    assert "Pyrokinesis" not in u, "uma carta que um deck dele pede não vai para Outros"
    assert u["Mogg Fanatic"]["q"] == 4 and u["Mogg Fanatic"]["arquetipos"] == ["Goblins", "Burn"]
    # Os alvos: elegíveis que não são caixa, + incluir, − excluir (config)
    rank = {"todos": [
        {"nome": "Enchantress", "estado": "caixa", "elegivel": True},
        {"nome": "Goblins", "estado": "abaixo", "elegivel": True},
        {"nome": "Full English Breakfast", "estado": "abaixo", "elegivel": True},
        {"nome": "Sligh", "estado": "abaixo", "elegivel": False},
        {"nome": "The Rack", "estado": "abaixo", "elegivel": False}]}
    assert [c["nome"] for c in premodern.alvos_outros(rank)] == ["Goblins", "Sligh"]
    print("união dos núcleos dos elegíveis que não são caixa, menos os meus decks")


# ===========================================================================
# 3. NÃO É FALTA, NÃO É ÓRFÃ, E ALINHA-SE SOZINHA
# ===========================================================================
def caso_a_pasta_nao_conta_como_falta_e_alinha_se():
    import shutil
    shutil.rmtree(POR, ignore_errors=True)
    con = base()
    rep = loadout.report(con)
    POR.mkdir(parents=True)
    fotos.garantir_pastas(rep, SITE)
    antes = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)["por_pedir"]
    c_antes = fotos.contas_das_pastas(rep, raiz=SITE)
    # «Swords to Plowshares» está no Blue Farm: nunca entra (o motor já o tira
    # pelo `dos_decks`; aqui confirma-se que uma carta que ele TEM não nasce).
    cid = collection.add_copy(con, "Goblin Lackey", set_code="tmp", quantity=2,
                              sub_collection="Colecção")
    con.commit()
    r = fotos.sincronizar_outros(con, rep, raiz=SITE,
                                 outros=_o(["Mogg Fanatic", "Cursed Scroll", "Goblin Lackey"]),
                                 pendentes=SITE / "pendentes")
    assert cid and sorted(r["criadas"]) == ["Cursed Scroll", "Mogg Fanatic"], r
    assert r["ja_tens"] == 1 and r["rl"] == ["Cursed Scroll"], r
    assert (OUT / "Mogg Fanatic").is_dir() and not (OUT / "Goblin Lackey").exists()
    assert not any(fotos.RE_PASTA_CARTA.match(p.name) for p in OUT.iterdir()), \
        "as pastas de Outros não levam (N)"
    assert (fotos.pasta_processados(SITE) / fotos.PASTA_OUTROS).is_dir()
    # NÃO CONTA COMO FALTA: o «por fotografar» e as contas do disco não mexem.
    assert fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)["por_pedir"] == antes
    c_dep = fotos.contas_das_pastas(rep, raiz=SITE)
    assert c_dep == c_antes, (c_antes, c_dep)
    fotos.exige_contas_explicadas(c_dep, antes)
    # E NÃO É ÓRFÃ: o plano é o dela, não o «esta pasta já não é um deck».
    fotos.escrever_planos(con, rep, raiz=SITE)
    plano = (OUT / "_plano.txt").read_text(encoding="utf-8")
    assert plano != fotos.TEXTO_ORFA and "NAO E «FALTA FOTOGRAFAR»" in plano, plano[:200]
    # A carta que um deck passou a pedir (ou saiu do top) SAI — se a pasta
    # estiver vazia; com uma foto dentro, fica.
    foto(OUT / "Cursed Scroll" / "IMG_1.jpg")
    r2 = fotos.sincronizar_outros(con, rep, raiz=SITE, outros=_o([]),
                                  pendentes=SITE / "pendentes")
    assert r2["saiu"] == ["Mogg Fanatic"] and r2["ficam_com_fotos"] == ["Cursed Scroll"], r2
    assert (OUT / "Cursed Scroll" / "IMG_1.jpg").is_file()
    # A foto recolhe-se como «outros», de frente só (não empareilha).
    r3 = fotos.recolher_das_pastas(raiz=SITE, agora=time.time())
    assert [x["tipo"] for x in r3["recolhidas"]] == ["outros"], r3
    assert r3["recolhidas"][0]["para"].startswith("site-outros-"), r3
    print("Outros não conta como falta, não é órfã, sai a vazia e fica a com foto")


# ===========================================================================
# 4. AS REGRAS DE COMBO DE 16/10
# ===========================================================================
def caso_as_regras_de_combo_de_16_10():
    nome = lambda cs: (premodern.classificar_regra(set(cs), premodern.COMBO_DEFAULT)
                       or {}).get("nome")
    assert nome(["Hermit Druid", "Phyrexian Dreadnought", "Reanimate"]) == \
        "Angry Ghoul (Hermit Druid)"
    assert nome(["Academy Rector", "Phyrexian Dreadnought"]) == "Academy Rector"
    assert nome(["Aluren", "Academy Rector"]) == "Aluren"
    assert nome(["Volrath's Shapeshifter", "Hermit Druid"]) == "Full English Breakfast"
    assert nome(["Phyrexian Dreadnought", "Stifle"]) == "Stiflenought"
    assert nome(["Frantic Search", "Brain Freeze"]) == "Frantic Storm"
    assert nome(["Dream Halls", "Frantic Search", "Brain Freeze"]) == "Dream Halls"
    assert nome(["Balancing Act"]) == "Balancing Tings"
    assert nome(["Daru Spiritualist", "Worthy Cause"]) == "Life / Test of Endurance"
    assert nome(["Psychatog", "Reanimate"]) == "Psychatog"
    assert nome(["Reanimate", "Exhume"]) == "Reanimator"
    # E o config tem as mesmas, pela mesma ordem (é ele que manda).
    real = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    cfg = [r["nome"] for r in real["premodern"]["combo_arquetipos"]]
    assert cfg == [r["nome"] for r in premodern.COMBO_DEFAULT], cfg
    print("as regras de combo de 16/10, iguais no código e no config")


CASOS = (caso_a_pasta_e_um_alvo_proprio_que_nao_tira_alocacao,
         caso_o_criterio_e_a_uniao_dos_nucleos_menos_os_meus_decks,
         caso_a_pasta_nao_conta_como_falta_e_alinha_se,
         caso_as_regras_de_combo_de_16_10)


def main():
    for c in CASOS:
        c()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001
            pass
    print(f"\nOK — {len(CASOS)} casos (a pasta Outros do Premodern)")


if __name__ == "__main__":
    main()
