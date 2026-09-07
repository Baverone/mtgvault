"""Modelo de colecção única: a migração e o "onde está a carta" depois dela.

André, 2026-09-07, à letra: *"Põe a colecção toda em uma coisa só, com excepção
da RL, e assim vais buscar as cartas ao mesmo sítio, mas aplicando as regras."*

O que aqui se tranca é o que custa caro se partir em silêncio:

  1. a migração funde as gavetas na `Colecção` e **não toca** na Caixa Reserved
     List nem na colecção de colecionador;
  2. é **idempotente** — correr duas vezes não grava `Colecção` por cima do
     `balde_origem`, que é a única pista de onde a carta estava;
  3. os decks que estão MONTADOS continuam montados: as cartas que viviam no
     balde de um deck ficam registadas dentro da caixa desse deck. Sem isto, a
     migração desmontava no papel quatro decks que estão na estante — as regras
     de material voltavam a aplicar-se a cartas já sleevadas;
  4. depois da migração, "onde está a carta" é a caixa (ou a gaveta), e a aba
     Arrumar sabe dizer de onde ela veio (`balde_origem`).

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CFG = {"regras_colecao": {"Blue Farm": {"reter_extras_meses": 6}},
       "baldes_coleccao": ["Colecção", "SPML", "Premodern (geral)",
                           "Caixa Reserved List"]}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import db, loadout, migracao  # noqa: E402

CATALOGO = [("Lotus Petal", "tmp", "1997-10-14", 0),
            ("Sol Ring", "c21", "2021-04-23", 0),
            ("Tarnished Citadel", "ody", "2001-10-01", 0),
            ("Mox Diamond", "sth", "1997-03-24", 1)]

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Artifact',1,'',?,?,?,0,?)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]),
             rel, json.dumps({"legacy": "legal", "commander": "legal",
                              "premodern": "legal"}), rl))
    con.commit()
    return con


def add(con, nm, q=1, sub=None, purpose="player", finish="nonfoil", lang="en"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = None
    if sub:
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
        sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                             (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,?,?)""",
                (sid, q, finish, lang, purpose, sub_id))
    con.commit()


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def povoada():
    con = base()
    add(con, "Sol Ring", 4, sub="SPML")
    add(con, "Lotus Petal", 2, sub="Premodern (geral)")
    # A cópia que só existe dentro da caixa do Blue Farm, e que a regra do cEDH
    # ("só EN nonfoil") mais a tranca do PT rejeitariam se ela lá não estivesse.
    add(con, "Tarnished Citadel", 1, sub="Blue Farm", finish="foil", lang="pt")
    add(con, "Mox Diamond", 3, sub="Caixa Reserved List")
    add(con, "Sol Ring", 1, sub="Colecionador", purpose="collector")
    deck(con, "BF", "cedh", [("Tarnished Citadel", 1)])
    return con


SLOTS = [{"slot": "cedh-blue-farm", "nome": "Blue Farm", "formato": "cedh",
          "fonte": "deck", "ref": "BF", "balde": "Blue Farm", "prioridade": 1}]


def por_balde(con):
    return migracao.estado(con)


# ---------------------------------------------------------------------------
def caso_funde_gavetas_e_deixa_a_rl_em_paz():
    con = povoada()
    rep = migracao.migrar(con, com_backup=False, cfg_slots=SLOTS)
    est = por_balde(con)
    assert est == {"Colecção": 7, "Caixa Reserved List": 3}, est
    assert rep["movidas"] == {"SPML": 4, "Premodern (geral)": 2, "Blue Farm": 1}, \
        rep["movidas"]
    assert rep["arrumadas"] == {"cedh-blue-farm": 1}, rep["arrumadas"]
    print("a migracao funde as gavetas e nao toca na Caixa Reserved List")


def caso_colecionador_intocado():
    con = povoada()
    migracao.migrar(con, com_backup=False, cfg_slots=SLOTS)
    r = con.execute("""SELECT s.name b, cp.quantity q FROM copies cp
                         JOIN sub_collections s ON s.id = cp.sub_collection_id
                        WHERE cp.purpose = 'collector'""").fetchone()
    assert r["b"] == "Colecionador" and r["q"] == 1, dict(r)
    print("a coleccao de colecionador fica onde estava")


def caso_idempotente_e_guarda_o_balde_de_origem():
    con = povoada()
    migracao.migrar(con, com_backup=False, cfg_slots=SLOTS)
    origens = {r[0]: r[1] for r in con.execute(
        "SELECT COALESCE(balde_origem,'(nulo)'), SUM(quantity) FROM copies "
        "WHERE purpose = 'player' GROUP BY 1")}
    assert origens == {"SPML": 4, "Premodern (geral)": 2, "Blue Farm": 1,
                       "(nulo)": 3}, origens
    segunda = migracao.migrar(con, com_backup=False)
    assert segunda["total"] == 0, segunda
    depois = {r[0]: r[1] for r in con.execute(
        "SELECT COALESCE(balde_origem,'(nulo)'), SUM(quantity) FROM copies "
        "WHERE purpose = 'player' GROUP BY 1")}
    assert depois == origens, depois
    print("migrar duas vezes nao apaga o balde de origem")


def caso_deck_montado_continua_montado():
    """O caso caro: o Blue Farm tem um Tarnished Citadel PT foil lá dentro e o
    cEDH é "só EN nonfoil". Antes da migração o balde protegia-o; depois da
    migração tem de ser a arrumação a proteger, senão o deck desmonta-se no
    papel — e o vault mandava comprar uma carta que está sleevada na estante."""
    con = povoada()
    antes = loadout.report(con, SLOTS)["slots"][0]
    assert antes["tenho"] == 1, antes["tenho"]
    migracao.migrar(con, com_backup=False, cfg_slots=SLOTS)
    depois = loadout.report(con, SLOTS)["slots"][0]
    assert depois["tenho"] == 1, depois["tenho"]
    assert depois["origens"] == {"Blue Farm": 1}, depois["origens"]
    assert depois["comprar"] == 0, depois["comprar"]
    # E sem a arrumação (a caixa vazia) a mesma cópia já não serve: é a prova de
    # que é a `copy_allocation` que a está a segurar, não o acaso.
    con.execute("DELETE FROM copy_allocation")
    con.commit()
    sem = loadout.report(con, SLOTS)["slots"][0]
    assert sem["tenho"] == 0, sem["tenho"]
    print("um deck montado continua montado depois da migracao")


def caso_arrumacao_diz_de_que_gaveta_sai():
    con = povoada()
    deck(con, "Leg", "legacy", [("Sol Ring", 2)])
    slots = SLOTS + [{"slot": "legacy", "nome": "Legacy", "formato": "legacy",
                      "fonte": "deck", "ref": "Leg", "balde": "Colecção",
                      "prioridade": 2, "acabamento": None, "lingua": None}]
    migracao.migrar(con, com_backup=False, cfg_slots=SLOTS)
    plano = loadout.report(con, slots)["arrumacao"]
    movs = [m for m in plano["movimentos"] if m["para"] == "Legacy"]
    assert movs and movs[0]["de"] == "Colecção", plano["movimentos"]
    assert sum(m["q"] for m in movs) == 2, movs
    print("depois da migracao a arrumacao tira tudo da mesma gaveta")


def caso_dry_run_nao_escreve():
    con = povoada()
    antes = por_balde(con)
    rep = migracao.migrar(con, dry_run=True)
    assert rep["dry_run"] and rep["total"] == 7, rep
    assert por_balde(con) == antes, por_balde(con)
    print("o --dry-run conta o que faria e nao escreve nada")


def run():
    for fn in (caso_funde_gavetas_e_deixa_a_rl_em_paz, caso_colecionador_intocado,
               caso_idempotente_e_guarda_o_balde_de_origem,
               caso_deck_montado_continua_montado,
               caso_arrumacao_diz_de_que_gaveta_sai, caso_dry_run_nao_escreve):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
