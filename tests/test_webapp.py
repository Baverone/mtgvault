"""Modo edição (webapp.py): os botões, sem servidor nenhum a correr.

O que aqui se tranca:

  1. **Tornar permanente / Deixar de ser permanente** escreve no
     `colecao_config.json` e a alocação muda logo a seguir — é a ordem do André
     (*"os decks que eu estiver quase a concluir, tenho que ter uma opção que os
     marque como permanentes para começarem a receber alocação de cartas"*);
  2. **Subir / Descer** mexe no `prioridade` DENTRO do grupo, e renumera o grupo
     em vez de trocar dois números — com números repetidos ou saltados no
     config, um swap simples não mexia em nada;
  3. o botão diz a verdade quando não pode fazer nada (primeiro/último do grupo,
     ou único) em vez de fingir que fez;
  4. **gravar o config não estraga o config**: o ficheiro a sério passa por uma
     ida e volta e sai igual, chave a chave. Um `json.dump` cru rebentava as
     catorze linhas do `loadout` em duzentas e apagava a forma com que ele o lê;
  5. **Sleevado e na caixa** grava a `copy_allocation` daquela caixa (e só
     daquela), e "tirar da caixa" apaga-a.

Não abre socket nenhum e não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "loadout": [
        {"slot": "a", "nome": "A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "prioridade": 7, "permanente": True},
        {"slot": "b", "nome": "B", "formato": "legacy", "fonte": "deck",
         "ref": "B", "balde": "Colecção", "prioridade": 7, "permanente": True},
        {"slot": "c", "nome": "C", "formato": "legacy", "fonte": "deck",
         "ref": "C", "balde": "Colecção", "prioridade": 9, "permanente": False},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import db, loadout, sources  # noqa: E402

import webapp  # noqa: E402

CATALOGO = [("Sol Ring", "c21", "2021-04-23", 0), ("Opt", "eld", "2019-10-04", 0)]
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
             rel, json.dumps({"legacy": "legal"}), rl))
    for nome in ("A", "B", "C"):
        con.execute("INSERT INTO decks (name, format) VALUES (?, 'legacy')", (nome,))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, 'Sol Ring', 1, 'main')", (did,))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    sid = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES ('id-0', 1, 'foil', 'en',
                   'player', ?)""", (sid,))
    con.commit()
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def quem_tem(con, cfg):
    rep = loadout.report(con, cfg["loadout"])
    return next(s["nome"] for s in rep["slots"] if s["tenho"])


# ---------------------------------------------------------------------------
def caso_tornar_permanente_muda_a_alocacao():
    repor()
    con = base()
    cfg = webapp.ler_config()
    assert quem_tem(con, cfg) == "A"      # A e B são permanentes, C é candidato
    # Tira-se a A e a B de permanentes: o candidato C passa a ser o primeiro.
    for slot in ("a", "b"):
        webapp.alternar(cfg, slot, "permanente", True)
    webapp.alternar(cfg, "c", "permanente", True)
    for s in cfg["loadout"]:
        s["prioridade"] = {"a": 3, "b": 2, "c": 1}[s["slot"]]
    assert quem_tem(con, cfg) == "C", quem_tem(con, cfg)
    print("tornar permanente muda quem fica com a carta")


def caso_subir_renumera_o_grupo():
    repor()
    con = base()
    cfg = webapp.ler_config()
    # A e B têm o MESMO `prioridade` (7) no config: um swap de números não
    # mexia em nada. A renumeração é que faz isto funcionar.
    msg = webapp.mover(con, cfg, "b", -1)
    prio = {s["slot"]: s["prioridade"] for s in cfg["loadout"]}
    assert prio["b"] < prio["a"], prio
    assert "subiu" in msg, msg
    assert quem_tem(con, cfg) == "B", quem_tem(con, cfg)
    print("subir renumera o grupo e a carta muda de caixa")


def caso_descer_e_os_limites():
    repor()
    con = base()
    cfg = webapp.ler_config()
    assert "já é o primeiro" in webapp.mover(con, cfg, "a", -1)
    assert "já é o último" in webapp.mover(con, cfg, "b", 1)
    # O candidato está sozinho no seu grupo (permanente=False).
    assert "único do grupo" in webapp.mover(con, cfg, "c", -1)
    assert webapp.mover(con, cfg, "nao-existe", 1) == "esse slot não existe"
    print("os limites do grupo dizem-se, em vez de fingir que mexeram")


def caso_gravar_o_config_a_serio_nao_o_estraga():
    """O ficheiro real do André passa por uma ida e volta e sai igual."""
    original = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    destino = _TMP / "roundtrip.json"
    webapp.escrever_config(original, destino)
    volta = json.loads(destino.read_text(encoding="utf-8"))
    assert volta == original, "o config não sobreviveu à ida e volta"
    assert list(volta) == list(original), "a ordem das chaves mudou"
    texto = destino.read_text(encoding="utf-8")
    # As catorze caixas continuam a ser catorze linhas, não duzentas.
    assert texto.count('{ "slot"') + texto.count('{"slot"') == len(original["loadout"])
    print("gravar o colecao_config.json a serio nao lhe estraga a forma")


def caso_sleevado_e_na_caixa():
    repor()
    con = base()
    n = webapp.marcar_na_caixa(con, "a", True)
    assert n == 1, n
    linhas = con.execute("SELECT slot, quantity FROM copy_allocation").fetchall()
    assert [(r["slot"], r["quantity"]) for r in linhas] == [("a", 1)], linhas
    # A caixa passa a ser a morada da carta.
    rep = loadout.report(con, webapp.ler_config()["loadout"])
    assert next(s for s in rep["slots"] if s["slot"] == "a")["origens"] == {"A": 1}
    # E tirar da caixa desfaz — só daquela caixa.
    assert webapp.marcar_na_caixa(con, "b", False) == 0
    assert webapp.marcar_na_caixa(con, "a", False) == 1
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation").fetchone()["c"] == 0
    print("sleevado e na caixa grava (e tira) so aquela caixa")


def run():
    for fn in (caso_tornar_permanente_muda_a_alocacao, caso_subir_renumera_o_grupo,
               caso_descer_e_os_limites, caso_gravar_o_config_a_serio_nao_o_estraga,
               caso_sleevado_e_na_caixa):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
