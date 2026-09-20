"""LISTA PADRÃO e RESERVA por caixa (André, 2026-09-20, à letra): *"preciso
urgentemente de estabelecer uma lista padrão para completar, e ver algumas
cartas que poderão ser possível entrar; não quero ter que vender cartas que
depois me poderão fazer falta."*

O que aqui se tranca (`mtgvault/padrao.py` + o que o `loadout` lê dele):

  1. **a lista padrão não é pisada pelo daily** — a caixa passa a ler a lista
     fixada em `listas_escolhidas[slot]` (`padrao: true`, data, origem); mudar
     a tabela `decks` por baixo (o que o `my_decks.refresh` faz todas as
     noites) não muda uma carta, e a nota da caixa di-lo; acrescentar/tirar
     editam essa lista; «voltar» repõe a fonte de antes;
  2. **a reserva sai da venda e da exportação** — as cópias de uma carta em
     `caixas[].reserva` vão para `guardar` com *"reserva da caixa <nome>"*,
     cumpram ou não a regra de material; não entram no CSV de stock nem na
     estante; o bloco da caixa diz onde cada cópia está e se serve;
  3. **uma PT da era Premodern não serve o Cloud** — é falta (comprar foil),
     com o substituto a dizer *"PT da era Premodern (trancada ao Premodern)"*;
  4. **a página desenha os dois blocos** e os botões só no modo edição;
  5. **a CLI** `padrao` e `reserva` escrevem no config e validam no catálogo.

Não toca na rede.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {}, "decks_vigiados": [],
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
         "playset_maximo": 4, "prioridade_por": "pct", "lingua": "pt",
         "edicoes": "premodern", "estrita": True,
         "baldes": ["Colecção", "Caixa Reserved List"]},
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "dedicado": True, "acabamento": "foil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "dedicado": True, "lingua": "en", "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "duel-commander", "nome": "Cloud (Duel Commander)",
         "formato": "duel-commander", "fonte": "deck", "ref": "Cloud (Duel Commander)",
         "balde": "Cloud", "estado": "permanente", "prioridade": 1, "notas": ""},
    ],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import configio, db, loadout, padrao, sources, venda  # noqa: E402

import deckboxes  # noqa: E402

# (nome, edição, data, reserved)
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 0),
    ("Rishadan Port", "mmq", "1999-10-04", 0),
    ("Mother of Runes", "sld", "2022-01-01", 0),
    ("Path to Exile", "pf20", "2020-01-01", 0),
    ("Winter Moon", "ltr", "2023-06-23", 0),
    ("Get Lost", "lci", "2023-11-17", 0),
    ("Witch Enchanter // Witch-Blessed Meadow", "mh3", "2024-06-14", 0),
    ("City of Traitors", "exo", "1998-06-15", 1),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, rl) in enumerate(CATALOGO):
        for lang in ("en", "pt"):
            con.execute(
                """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
                   set_code, set_name, collector_number, lang, rarity, type_line, cmc,
                   color_identity, finishes, released_at, legalities, digital, reserved)
                   VALUES (?,?,?,?,'S',?,?,'rare','Instant',1,'W',?,?,?,0,?)""",
                (f"id-{i}-{lang}", f"or-{i}", nm, sc, str(i), lang,
                 json.dumps(["nonfoil", "foil"]), rel,
                 json.dumps({"legacy": "legal", "premodern": "legal", "modern": "legal",
                             "commander": "legal", "duel": "legal"}), rl))
            for fin in ("nonfoil", "foil"):
                con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                            "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                            "'2026-09-19', ?)", (f"id-{i}-{lang}", fin, 3.0))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub="Colecção"):
    i = [c[0] for c in CATALOGO].index(nm)
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, 'player')",
                (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?", (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                   sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (f"id-{i}-{lang}", q, finish, lang, sub_id))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def deck(con, nome, fmt, cartas):
    con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def cfg_ler():
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


def cfg_escrever(cfg):
    configio.escrever(cfg, CFG_PATH)
    sources._CFG_CACHE.clear()


def cloud(rep):
    return next(s for s in rep["slots"] if s["slot"] == "duel-commander")


def nomes(cards):
    return sorted(n for _b, n, _q in cards)


# ---------------------------------------------------------------------------
def caso_a_lista_padrao_nao_e_pisada_pelo_daily():
    """A tabela `decks` diz uma coisa; a lista padrão diz outra. A caixa lê a
    padrão, e mudar a tabela por baixo (o `my_decks.refresh` de todas as
    noites) não lhe muda uma carta."""
    cfg_escrever(json.loads(json.dumps(CFG)))
    con = base()
    deck(con, "Cloud (Duel Commander)", "duel-commander",
         [("Swords to Plowshares", 1), ("Winter Moon", 1)])
    rep = loadout.report(con)
    assert nomes(cloud(rep)["cards"]) == ["Swords to Plowshares", "Winter Moon"]
    assert cloud(rep)["padrao"] is None

    cfg = cfg_ler()
    rec = padrao.fixar(cfg, "duel-commander",
                       padrao.parse_lista("1 Swords to Plowshares\n1 Mother of Runes\n"
                                          "// Sideboard\n1 Path to Exile"),
                       origem="83 listas mono-brancas, mtgtop8 21/08–19/09",
                       quando="2026-09-20")
    assert rec["padrao"] is True and rec["escolhido_em"] == "2026-09-20"
    assert rec["cards"] == [["main", "Mother of Runes", 1], ["main", "Swords to Plowshares", 1],
                            ["side", "Path to Exile", 1]], rec["cards"]
    s = next(c for c in cfg["caixas"] if c["slot"] == "duel-commander")
    assert s["fonte"] == "escolhido" and s["ref"] == "duel-commander"
    assert s["nome"] == "Cloud (Duel Commander)", "o nome da caixa não muda"
    assert s["_antes"] == {"fonte": "deck", "ref": "Cloud (Duel Commander)",
                           "nome": "Cloud (Duel Commander)", "estado": "permanente"}
    cfg_escrever(cfg)

    rep = loadout.report(con)
    c = cloud(rep)
    assert nomes(c["cards"]) == ["Mother of Runes", "Path to Exile", "Swords to Plowshares"]
    assert c["padrao"] == {"desde": "2026-09-20",
                           "origem": "83 listas mono-brancas, mtgtop8 21/08–19/09"}
    assert c["nota"].startswith("lista padrão fixada em 2026-09-20 · 83 listas"), c["nota"]
    assert [b for b, n, _q in c["cards"] if n == "Path to Exile"] == ["side"]

    # O daily pisa a tabela `decks`: a caixa não mexe.
    deck(con, "Cloud (Duel Commander)", "duel-commander", [("Winter Moon", 1)])
    rep = loadout.report(con)
    assert nomes(cloud(rep)["cards"]) == ["Mother of Runes", "Path to Exile",
                                          "Swords to Plowshares"]

    # Acrescentar, tirar, e o «voltar ao consenso».
    cfg = cfg_ler()
    padrao.acrescentar(cfg, "duel-commander", "Get Lost")
    padrao.acrescentar(cfg, "duel-commander", "Get Lost")       # soma
    padrao.tirar(cfg, "duel-commander", "Path to Exile")
    cfg_escrever(cfg)
    rep = loadout.report(con)
    c = cloud(rep)
    assert nomes(c["cards"]) == ["Get Lost", "Mother of Runes", "Swords to Plowshares"]
    assert next(q for _b, n, q in c["cards"] if n == "Get Lost") == 2
    try:
        padrao.tirar(cfg, "duel-commander", "Winter Moon")
        raise AssertionError("tirar o que não está tinha de falhar")
    except ValueError as e:
        assert "não está na lista padrão" in str(e), e
    # Fixar por cima não esquece o `_antes`.
    padrao.fixar(cfg, "duel-commander", [["main", "Mother of Runes", 1]], origem="v2")
    s = next(x for x in cfg["caixas"] if x["slot"] == "duel-commander")
    assert s["_antes"]["ref"] == "Cloud (Duel Commander)"
    msg = padrao.voltar(cfg, "duel-commander")
    assert "volta à fonte 'deck'" in msg, msg
    assert s["fonte"] == "deck" and s["ref"] == "Cloud (Duel Commander)"
    assert "_antes" not in s and "listas_escolhidas" not in cfg
    cfg_escrever(cfg)
    rep = loadout.report(con)
    assert nomes(cloud(rep)["cards"]) == ["Winter Moon"], "voltou à tabela decks"
    assert cloud(rep)["padrao"] is None
    print("a lista padrao nao e pisada pelo daily; add/tirar/voltar")


def caso_a_reserva_sai_da_venda_e_da_exportacao():
    """Ele tem 6 Path to Exile (2 a mais do playset) e 1 Winter Moon nonfoil que
    nada usa; a reserva do Cloud segura as duas cartas: `guardar`, com o
    motivo, fora do CSV e da estante — cumpram ou não a regra (o Cloud é foil
    e a Winter Moon é nonfoil)."""
    cfg = json.loads(json.dumps(CFG))
    cfg["caixas"][0]["reserva"] = ["Path to Exile", "Winter Moon", "City of Traitors"]
    cfg_escrever(cfg)
    con = base()
    deck(con, "Cloud (Duel Commander)", "duel-commander", [("Mother of Runes", 1)])
    add(con, "Mother of Runes", 1, finish="foil")
    add(con, "Path to Exile", 4, finish="foil")
    add(con, "Path to Exile", 2, finish="nonfoil")
    add(con, "Winter Moon", 1, finish="nonfoil")
    add(con, "City of Traitors", 5, finish="nonfoil", sub="Caixa Reserved List")
    add(con, "Get Lost", 6, finish="foil")                # sem reserva: vende 2
    rep = loadout.report(con)
    c = cloud(rep)
    assert c["pct"] == 100 and c["comprar"] == 0, c["pct"]
    vendidas = {r["nm"]: r for r in rep["venda"]}
    assert set(vendidas) == {"Get Lost"} and vendidas["Get Lost"]["q"] == 2, vendidas
    assert rep["venda_rl"] == [], rep["venda_rl"]
    g = {(r["nm"], r["reason"]): r for r in rep["guardar"]}
    razao = f"{loadout.RAZAO_RESERVA} Cloud (Duel Commander)"
    assert ("Path to Exile", razao) in g, g.keys()
    assert g[("Path to Exile", razao)]["q"] == 2
    assert g[("Path to Exile", razao)]["porque_venderia"] == "excedente (mais de 4)"
    assert g[("Path to Exile", razao)]["reserva_de"] == ["Cloud (Duel Commander)"]
    assert ("City of Traitors", razao) in g and g[("City of Traitors", razao)]["q"] == 1
    assert rep["rl_segurar"] == [] and rep["rl_sem_historico"] == [], "a RL reservada nem se mede"
    assert rep["copias_guardar"] == 3, rep["copias_guardar"]
    # A Winter Moon nonfoil não é excedente (1 cópia): nunca ia à venda; a
    # reserva não a inventa na lista de guardar — mas o bloco da caixa mostra-a.
    assert not any(r["nm"] == "Winter Moon" for r in rep["guardar"])
    bloco = {r["nm"]: r for r in c["reserva_linhas"]}
    assert set(bloco) == {"Path to Exile", "Winter Moon", "City of Traitors"}
    assert bloco["Path to Exile"]["q"] == 6 and bloco["Path to Exile"]["serve"] is True
    wm = bloco["Winter Moon"]
    assert wm["q"] == 1 and wm["serve"] is False
    assert wm["lotes"][0]["porque"].startswith("não é foil"), wm["lotes"][0]
    assert wm["lotes"][0]["onde"] == "Colecção", wm["lotes"][0]
    assert rep["reserva_total"] == 12, rep["reserva_total"]
    # A exportação: nem no CSV nem na estante.
    r = venda.relatorio(con, rep)
    assert "Path to Exile" not in r["csv"] and "City of Traitors" not in r["csv"], r["csv"]
    assert "Path to Exile" not in r["texto_estante"]
    assert "Get Lost" in r["csv"]
    fora = {f["chave"]: f for f in venda.fora_da_exportacao(rep)}
    assert any(l["nm"] == "Path to Exile" and razao in l["motivo"]
               and "ia por: excedente" in l["motivo"]
               for l in fora["guardar"]["linhas"]), fora["guardar"]
    assert "reserva" in fora["guardar"]["titulo"].lower(), fora["guardar"]["titulo"]
    # A reserva não conta para a caixa: a Path não está na lista.
    assert not any(m["nm"] == "Path to Exile" for m in c["have"] + c["missing"])
    print("a reserva sai da venda e da exportacao, com o motivo e o bloco")


def caso_uma_pt_da_era_nao_serve_o_cloud():
    """A Rishadan Port MMQ pt (e a Swords 4ED pt) estão trancadas ao Premodern:
    para o Cloud são FALTA — comprar foil —, e a cópia fica como substituto
    com a razão da tranca, não como «tem só nonfoil»."""
    cfg = json.loads(json.dumps(CFG))
    cfg_escrever(cfg)
    con = base()
    deck(con, "Cloud (Duel Commander)", "duel-commander",
         [("Rishadan Port", 1), ("Swords to Plowshares", 1)])
    add(con, "Rishadan Port", 2, finish="nonfoil", lang="pt")
    add(con, "Swords to Plowshares", 1, finish="nonfoil", lang="pt")
    rep = loadout.report(con)
    c = cloud(rep)
    assert c["pct"] == 0 and c["comprar"] == 2, (c["pct"], c["comprar"])
    for nm in ("Rishadan Port", "Swords to Plowshares"):
        m = next(x for x in c["missing"] if x["nm"] == nm)
        assert m["comprar"] == 1 and m["got"] == 0, m
        assert m["alt"] == {"PT da era Premodern (trancada ao Premodern)": (2 if nm == "Rishadan Port" else 1)}, m["alt"]
        assert "foil" in (m.get("req_compra") or loadout.requisito_material(c)).lower()
    assert {w["nm"] for w in c["missing"] if w["comprar"]} == {"Rishadan Port", "Swords to Plowshares"}
    # E na venda: a PT da era não usada por nenhum deck de Premodern só sai se
    # houver caixa de Premodern; aqui não há, logo não se vende — fica onde está.
    assert not any(r["nm"] == "Rishadan Port" for r in rep["venda"])
    print("uma PT da era Premodern e falta para o Cloud (comprar foil)")


def caso_a_pagina_desenha_a_reserva_e_a_lista_padrao():
    """O payload leva `padrao` e `reserva`; o HTML desenha «Reserva (N)» e a
    origem da lista padrão; os botões só no modo edição."""
    cfg = json.loads(json.dumps(CFG))
    cfg["caixas"][0]["reserva"] = ["Path to Exile"]
    padrao.fixar(cfg, "duel-commander", [["main", "Mother of Runes", 1]],
                 origem="teste", quando="2026-09-20")
    cfg_escrever(cfg)
    con = base()
    add(con, "Mother of Runes", 1, finish="foil")
    add(con, "Path to Exile", 1, finish="nonfoil")
    rep = loadout.report(con)
    for editable in (False, True):
        d = deckboxes.payload(con, rep, editable=editable)
        c = next(x for x in d["caixas"] if x["slot"] == "duel-commander")
        assert c["padrao"] == {"desde": "2026-09-20", "origem": "teste"}, c["padrao"]
        assert c["reserva"][0]["nm"] == "Path to Exile" and c["reserva"][0]["q"] == 1
        assert c["reserva"][0]["lotes"][0]["serve"] is False
        # `partir`/`juntar` continuam inversos com a chave nova.
        idx, partes = deckboxes.partir(d)
        assert "reserva" not in idx["caixas"][0] and deckboxes.juntar(idx, partes) == d
        html = deckboxes.html_page(con, editable=editable, rep=rep)
        assert "reservaHTML" in html and "padraoHTML" in html
        pagina = _TMP / f"dx-{int(editable)}.html"
        pagina.write_text(html, encoding="utf-8")
        # O JS desenha os blocos (o harness de node corre o render a sério).
        if not shutil.which("node"):
            print("  (sem node: o render não foi verificado)")
            continue
        dump = _TMP / f"abas-{int(editable)}.json"
        p = subprocess.run(["node", str(RAIZ / "tests" / "render_deckboxes.js"),
                            str(pagina), str(dump)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
        aba = json.loads(dump.read_text(encoding="utf-8"))["duel-commander"]
        assert "Reserva (1)" in aba and "Path to Exile" in aba, aba[:800]
        assert "não serve: não é foil" in aba, aba[:800]
        assert "Lista padrão desde 2026-09-20" in aba and "teste" in aba, aba[:800]
        assert ("data-padrao=" in aba) is editable, "botões só no modo edição"
        assert ("data-reserva=" in aba) is editable, "botões só no modo edição"
        assert (" blocos de escrita (editavel=" in p.stdout), p.stdout
    print("a pagina desenha a reserva e a lista padrao")


def caso_a_cli_escreve_no_config_e_valida_no_catalogo():
    cfg = json.loads(json.dumps(CFG))
    cfg_escrever(cfg)
    con = base()
    deck(con, "Cloud (Duel Commander)", "duel-commander", [("Winter Moon", 1)])
    con.commit()
    dbp = con.execute("PRAGMA database_list").fetchall()
    vault = next(r["file"] for r in dbp if r["name"] == "main")
    cat = next(r["file"] for r in dbp if r["name"] == "catalog")
    env = dict(os.environ, MTGVAULT_DB=vault, MTGVAULT_CATALOG=cat, MTGVAULT_CONFIG=str(CFG_PATH),
               PYTHONIOENCODING="utf-8")

    def cli(*args, entrada=None):
        return subprocess.run([sys.executable, "-m", "mtgvault.cli", *args], cwd=RAIZ,
                              input=entrada, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env)

    lista = _TMP / "lista.txt"
    lista.write_text("1 Mother of Runes\n1 Nao Existe Esta Carta\n", encoding="utf-8")
    p = cli("padrao", "duel-commander", "fixar", "--ficheiro", str(lista), "--origem", "x")
    assert p.returncode == 2 and "Nao Existe Esta Carta" in p.stdout, (p.stdout, p.stderr)
    assert "listas_escolhidas" not in cfg_ler(), "não fixou nada"
    lista.write_text("1 Mother of Runes\n1 witch enchanter\n", encoding="utf-8")
    p = cli("padrao", "duel-commander", "fixar", "--ficheiro", str(lista), "--origem", "x")
    assert p.returncode == 0, (p.stdout, p.stderr)
    rec = cfg_ler()["listas_escolhidas"]["duel-commander"]
    assert rec["cards"] == [["main", "Mother of Runes", 1], ["main", "Witch Enchanter", 1]], rec
    p = cli("padrao", "duel-commander", "add", "Get Lost", "--qty", "2")
    assert p.returncode == 0, p.stdout + p.stderr
    p = cli("padrao", "duel-commander", "tirar", "Witch Enchanter")
    assert p.returncode == 0, p.stdout + p.stderr
    p = cli("padrao", "duel-commander", "listar")
    assert "2 Get Lost" in p.stdout and "Witch" not in p.stdout, p.stdout
    p = cli("reserva", "duel-commander", "add", "Path to Exile")
    assert p.returncode == 0 and cfg_ler()["caixas"][0]["reserva"] == ["Path to Exile"], p.stdout
    p = cli("reserva", "duel-commander", "add", "Carta Inventada")
    assert p.returncode == 2 and "catálogo" in p.stdout, p.stdout
    p = cli("reserva", "duel-commander", "listar")
    assert "Path to Exile" in p.stdout, p.stdout
    p = cli("reserva", "duel-commander", "remover", "Path to Exile")
    assert p.returncode == 0 and "reserva" not in cfg_ler()["caixas"][0], p.stdout
    p = cli("padrao", "duel-commander", "voltar")
    assert p.returncode == 0 and "listas_escolhidas" not in cfg_ler(), p.stdout + p.stderr
    assert cfg_ler()["caixas"][0]["fonte"] == "deck"
    print("a CLI escreve no config e valida no catalogo")


def run():
    for fn in (caso_a_lista_padrao_nao_e_pisada_pelo_daily,
               caso_a_reserva_sai_da_venda_e_da_exportacao,
               caso_uma_pt_da_era_nao_serve_o_cloud,
               caso_a_pagina_desenha_a_reserva_e_a_lista_padrao,
               caso_a_cli_escreve_no_config_e_valida_no_catalogo):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
