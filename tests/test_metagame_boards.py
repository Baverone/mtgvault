"""O main e o sideboard são duas pilhas do MESMO deck (`loadout.foil_report`).

O `_estado_carta` NÃO consome — é de propósito: serve para comparar arquétipos
entre si, que são alternativas. Mas dentro de UM arquétipo o main e o side não
são alternativas: são duas pilhas que vão para a mesa ao mesmo tempo. O
`foil_report` perguntava-lhe uma vez por bloco, com o mesmo pool, e as MESMAS
cópias contavam como tidas dos dois lados.

Duas consequências, as duas visíveis na página (medidas na base de 2026-09-09):

  * a cobertura vinha por cima — o Pioneer *"Memory Deluge / Get Out"* dizia
    24 % e são 21 %, e a `pct_principal` da Enchantress 63 % em vez de 61 %. É a
    percentagem por que ele escolhe o deck a montar a seguir, e o limiar dos
    50 % das sugestões de Premodern corre sobre ela;
  * a lista de compras saía com a carta REPETIDA em duas linhas de 1 quando são
    2 — *"1× King T'Challa"* duas vezes no `metagame.html`, e o mesmo no texto
    que o botão «copiar» manda para o Cardmarket.

Nenhum passo dava erro: é o padrão do `event_tier` outra vez.

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "metagame_fontes": {"_default": {"tiers": ["Challenge"], "ligas": False}},
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"},
    ],
}
(_TMP / "cfg.json").write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import analysis, db, loadout  # noqa: E402

CATALOGO = [("Brainstorm", "ice", "1995-06-01"),
            ("Force of Will", "all", "1996-06-10"),
            ("Island", "4bb", "1995-04-01")]

# A carta que joga nos dois lados: 4 no main e 2 no side. São 6 cópias na mesa.
MAIN = [("Brainstorm", 4), ("Force of Will", 4), ("Island", 20)]
SIDE = [("Brainstorm", 2)]

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Instant',1,'U',?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i),
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"legacy": "legal"})))
    con.commit()
    return con


def listas(con, n=10):
    quando = (date.today() - timedelta(days=3)).isoformat()
    for i in range(n):
        con.execute(
            """INSERT INTO decklists (source, source_key, format, event_name,
               event_date, player, event_tier) VALUES
               ('mtgo', ?, 'legacy', 'Legacy Challenge', ?, ?, 'Challenge')""",
            (f"j-{i}", quando, f"jog{i}"))
        did = con.execute("SELECT MAX(id) i FROM decklists").fetchone()["i"]
        for board, cartas in (("main", MAIN), ("side", SIDE)):
            for nm, q in cartas:
                con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                            " quantity, board) VALUES (?,?,?,?)",
                            (did, nm, q, board))
    con.commit()


def add(con, nm, q, finish="foil", lang="en"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub))
    con.commit()


def mundo():
    con = base()
    listas(con)
    analysis.rebuild_archetypes(con, "legacy")
    analysis.rebuild_roles(con, "legacy")
    con.commit()
    return con


def linhas_de(rank, nm):
    return [m for m in rank[0]["linhas"] if m["nm"] == nm]


# ---------------------------------------------------------------------------
def caso_a_carta_dos_dois_blocos_conta_UMA_vez():
    """4 cópias não fecham 4 no main **e** 2 no side."""
    con = mundo()
    add(con, "Brainstorm", 4)
    rank = loadout.foil_report(con, "legacy", top=1, min_lists=5)
    assert rank, "sem arquétipos — a base de teste não montou o metagame"
    ms = linhas_de(rank, "Brainstorm")
    assert len(ms) == 1, f"a carta veio em {len(ms)} linhas: {ms}"
    m = ms[0]
    assert m["need"] == 6, m          # 4 main + 2 side
    assert m["got"] == 4, m           # é o que ele tem, não 4+2
    assert m["comprar"] == 2, m
    print("a carta que joga no main e no side conta uma vez so")


def caso_a_cobertura_nao_vem_por_cima():
    """A percentagem do arquétipo é a das cópias reais.

    Sem as básicas: 4 Brainstorm + 4 Force of Will = 8 num total de 6 + 4 = 10.
    """
    con = mundo()
    add(con, "Brainstorm", 4)
    add(con, "Force of Will", 4)
    d = loadout.foil_report(con, "legacy", top=1, min_lists=5)[0]
    assert d["need"] == 10, d
    assert d["got"] == 8, d
    assert d["pct"] == 80, d
    print("a cobertura do arquetipo conta cada copia uma vez")


def caso_a_wantlist_nao_repete_a_carta():
    """Uma linha por carta: *"2 Brainstorm"*, não *"1 ... 1 ..."*.

    É o texto que o botão «copiar» manda para o Cardmarket. Duas linhas de 1
    ainda somavam 2 na maioria dos casos — mas a lista à vista dizia que faltava
    1, que é o número por que ele decide se compra.
    """
    con = mundo()
    add(con, "Brainstorm", 5)         # fecha o main e uma do side
    d = loadout.foil_report(con, "legacy", top=1, min_lists=5)[0]
    faltam = [m for m in d["linhas"] if m["comprar"] > 0]
    assert [m["nm"] for m in faltam].count("Brainstorm") == 1, faltam
    assert next(m for m in faltam if m["nm"] == "Brainstorm")["comprar"] == 1
    print("a lista de compras traz a carta numa linha so")


def run():
    for fn in (caso_a_carta_dos_dois_blocos_conta_UMA_vez,
               caso_a_cobertura_nao_vem_por_cima,
               caso_a_wantlist_nao_repete_a_carta):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
