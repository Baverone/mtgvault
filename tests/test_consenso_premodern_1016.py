"""Premodern em consenso menos o Stiflenought (André, 2026-10-16, à letra:
*"em premodern todos são consensos menos o Stiflenought que é a lista do
Luffy"*).

O que aqui se tranca:
  1. a regra `so_main` do `tagging`: a carta que dá identidade a um deck tem de
     estar no MAINDECK — um Reanimator com Oath of Druids no sideboard não é um
     Oath;
  2. os cinco alvos do config existem TODOS nas regras de Premodern (um alvo sem
     regra não tem etiqueta, e o consenso dele sai «listas insuficientes» para
     sempre, sem erro), e o Stiflenought continua fora;
  3. o `premodern_decks` calcula o consenso de um alvo novo a partir das listas
     com a etiqueta.

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps({
    "premodern_arquetipos_alvo": ["Oath of Druids"],
    "metagame_fontes": {"_default": {"tiers": ["Challenge"], "min_jogadores_presencial": 64,
                                     "ligas": False}}}), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, tagging  # noqa: E402
import premodern_decks  # noqa: E402

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    return cm.__enter__()


def _lista(con, i, cartas, side=()):
    con.execute("""INSERT INTO decklists (source, source_key, format, event_date, player,
                   event_tier) VALUES ('mtgo', ?, 'premodern', date('now'), ?, 'Challenge')""",
                (f"k{i}", f"p{i}"))
    dl = con.execute("SELECT max(id) i FROM decklists").fetchone()["i"]
    for b, cs in (("main", cartas), ("side", side)):
        for nm, q in cs:
            con.execute("INSERT INTO decklist_cards (decklist_id, board, card_name, quantity) "
                        "VALUES (?, ?, ?, ?)", (dl, b, nm, q))
    return dl


def caso_so_main_nao_apanha_o_sideboard():
    con = base()
    regras = {"premodern": [{"name": "Oath of Druids", "all": ["Oath of Druids"], "so_main": True},
                            {"name": "Tem Oath", "all": ["Oath of Druids"]}]}
    antes = tagging.load_rules
    tagging.load_rules = lambda: regras
    try:
        oath = _lista(con, 1, [("Oath of Druids", 4), ("Forest", 56)])
        rean = _lista(con, 2, [("Exhume", 4), ("Swamp", 56)], side=[("Oath of Druids", 4)])
        tagging.tag_format(con, "premodern")
    finally:
        tagging.load_rules = antes
    tags = {(r["decklist_id"], r["name"]) for r in con.execute("SELECT * FROM decklist_tags")}
    assert (oath, "Oath of Druids") in tags and (rean, "Oath of Druids") not in tags, tags
    assert (rean, "Tem Oath") in tags, "sem so_main a regra continua a ver o sideboard"
    print("so_main: o Oath no sideboard nao faz de um Reanimator um Oath")


def caso_os_alvos_tem_regra_e_o_stiflenought_fica_fora():
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    alvos = cfg["premodern_arquetipos_alvo"]
    assert alvos == ["UW Replenish", "Enchantress", "Elves", "Oath of Druids",
                     "Ill-Gotten Gains"], alvos
    assert "Stiflenought" not in alvos
    assert "2026-10-16" in cfg["_premodern_arquetipos_alvo"]
    regras = {r["name"] for r in tagging.load_rules()["premodern"]}
    assert set(alvos) <= regras, set(alvos) - regras
    stf = next(c for c in cfg["caixas"] if c["slot"] == "premodern-stiflenought")
    assert stf["fonte"] == "vigiado" and stf["ref"] == "Luffy — Premodern", stf
    print("os cinco alvos tem regra; o Stiflenought continua a seguir o Luffy")


def caso_o_consenso_de_um_alvo_novo_sai_das_etiquetas():
    con = base()
    oath = [("Oath of Druids", 4), ("Forest", 20), ("Spike Feeder", 4), ("Terravore", 4),
            ("Mox Diamond", 4), ("Wasteland", 4), ("Sylvan Library", 4), ("Plains", 16)]
    for i in range(6):
        _lista(con, 10 + i, oath, side=[("Naturalize", 4), ("Warmth", 4), ("Aura of Silence", 4),
                                         ("Crumble", 3)])
    antes = tagging.load_rules
    tagging.load_rules = lambda: {"premodern": [
        {"name": "Oath of Druids", "all": ["Oath of Druids"], "so_main": True}]}
    try:
        tagging.tag_format(con, "premodern")
    finally:
        tagging.load_rules = antes
    out = premodern_decks.refresh(con)
    assert "Oath of Druids (consenso)" in out and "6 listas" in out, out
    n = con.execute("""SELECT count(*) c FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id
                        WHERE d.name = 'Oath of Druids (consenso)'""").fetchone()["c"]
    assert n > 0, out
    print("o consenso do Oath sai das listas etiquetadas:", out)


def run():
    for fn in (caso_so_main_nao_apanha_o_sideboard,
               caso_os_alvos_tem_regra_e_o_stiflenought_fica_fora,
               caso_o_consenso_de_um_alvo_novo_sai_das_etiquetas):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
