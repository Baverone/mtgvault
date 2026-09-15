"""Os extras dos decks vigiados ficam guardados SEM PRAZO (André, 2026-09-15).

Até aqui havia dois prazos escritos e nenhum a correr: o `reter_extras_meses: 6`
do `colecao_config.json` (*"guardam-se até 6 meses da última utilização"*), que
esperava por uma fonte de "última utilização" que nunca foi decidida, e o
`SELL_STALE_DAYS = 180` do `classify.py` (*"6 meses sem ser jogada em torneio →
vender"*), que nunca podia morder porque o `daily` só guarda ~30 dias de listas.
Ele decidiu que não quer prazo nenhum: o que sai dos decks vigiados sai quando
ele o disser, carta a carta, com o «vendida».

O que aqui se tranca:
  1. o `classify` já não tem a regra dos 180 dias — uma carta cuja única
     aparição em torneio é de há muito tempo continua na coleção;
  2. o config diz `reter_extras: true` para os quatro decks vigiados e já não
     traz o prazo;
  3. o texto das páginas e do CLI diz "sem prazo" e não "até 6 meses" — uma
     regra que a página não diz é a página a mentir, e uma que diz e não corre
     também.

Não toca na rede.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps({
    "spml_formatos": {"legacy": "a jogar"},
    "regras_colecao": {"Blue Farm": {"reter_extras": True}},
    "baldes_coleccao": ["Colecção", "SPML"]}), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

import classify  # noqa: E402
from mtgvault import db, loadout  # noqa: E402

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, legalities, digital, reserved)
           VALUES ('id-1','or-1','Thoughtcast','mrd','Mirrodin','1','en','common',
                   'Sorcery',2,'U',?, '2003-10-02', ?, 0, 0)""",
        (json.dumps(["nonfoil", "foil"]), json.dumps({"legacy": "legal"})))
    con.commit()
    return con


def caso_o_classify_ja_nao_tem_prazo():
    """Uma carta legal cuja ÚNICA aparição em torneio é de há 400 dias fica na
    coleção (backup até 4). Antes ia para "vender" com o motivo "fora do meta há
    6+ meses" — a regra saiu, e não pode voltar por outro nome."""
    assert not hasattr(classify, "SELL_STALE_DAYS"), "o prazo dos 180 dias voltou"
    assert not hasattr(classify, "_last_played"), "a 'última utilização' voltou"
    con = base()
    con.execute("INSERT INTO sub_collections (name, purpose) VALUES ('SPML','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='SPML'").fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                   sub_collection_id) VALUES ('id-1', 2, 'nonfoil', 'en', 'player', ?)""",
                (sub,))
    con.execute("""INSERT INTO decklists (source, source_key, format, event_date, player)
                   VALUES ('manual', 'x', 'legacy', date('now','-400 days'), 'p')""")
    dl = con.execute("SELECT id FROM decklists").fetchone()["id"]
    con.execute("INSERT INTO decklist_cards (decklist_id, board, card_name, quantity) "
                "VALUES (?, 'main', 'Thoughtcast', 4)", (dl,))
    con.commit()
    rep = classify.build(con)
    vender = [r for r in rep["vender"] if r["nm"] == "Thoughtcast"]
    assert not vender, vender
    assert sum(r["q"] for r in rep["colecao"] if r["nm"] == "Thoughtcast") == 2, rep["colecao"]
    assert not any("6+ meses" in (r.get("reason") or "") for r in rep["vender"])
    print("o classify ja nao manda vender por 'fora do meta ha 6+ meses'")


def caso_o_config_do_andre_guarda_sem_prazo():
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    regras = cfg["regras_colecao"]
    for balde in ("Blue Farm", "Cloud", "Cloud cEDH", "Pauper Affinity"):
        assert regras.get(balde, {}).get("reter_extras") is True, (balde, regras.get(balde))
        assert "reter_extras_meses" not in regras[balde], balde
    assert "sem prazo" in cfg["_regras_colecao"].lower()
    assert "2026-09-15" in cfg["_regras_colecao"]
    print("o config guarda os extras dos quatro decks vigiados sem prazo")


def caso_as_paginas_dizem_sem_prazo_e_nao_ate_6_meses():
    """O texto VIVO (o que a página desenha e o CLI imprime) não pode continuar a
    dizer "até 6 meses". Os comentários podem — é lá que a história fica."""
    assert "sem prazo" in loadout.RAZAO_RETIDO
    vivo = re.compile(r"(retid[ao]s? até 6 meses|até 6 meses d[ea]|guardam-se até 6 meses"
                      r"|reter_extras_meses</code>)")
    # Só os ficheiros que DESENHAM texto para ele (o `loadout` e o `classify`
    # guardam a história em docstrings e comentários, e isso é de propósito).
    for nome in ("deckboxes.py", "colecao_cor.py", "mtgvault/cli.py"):
        txt = (RAIZ / nome).read_text(encoding="utf-8")
        linhas = [l for l in txt.splitlines() if not l.strip().startswith("#")]
        maus = [l for l in linhas if vivo.search(l) and "2026-09-15" not in l
                and "era " not in l]
        assert not maus, (nome, maus)
    for nome in ("deckboxes.py", "colecao_cor.py", "mtgvault/cli.py"):
        assert "sem prazo" in (RAIZ / nome).read_text(encoding="utf-8"), nome
    print("as paginas e o CLI dizem 'sem prazo'")


def run():
    for fn in (caso_o_classify_ja_nao_tem_prazo, caso_o_config_do_andre_guarda_sem_prazo,
               caso_as_paginas_dizem_sem_prazo_e_nao_ate_6_meses):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
