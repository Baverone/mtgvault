"""Os TERRENOS BÁSICOS aparecem no painel Montar, e vêm da pilha certa.

André, 2026-09-08: *"Faltou marcares, para completar o deck, os terrenos básicos
necessários!"* — e, na mesma tarde, *"Todas as minhas lands básicas são de
Unhinged, em inglês, foil ou não foil."*

Até aqui uma básica entrava na alocação com `got == need` e `lotes == []`:
contava como tida e não aparecia em lado nenhum. Um Stiflenought com 17 Island
montava-se, no painel Montar, sem uma única terra — e o painel é a folha que ele
leva para a frente da estante.

O que aqui se tranca:

  1. o bloco existe, com as quantidades certas por caixa (Stiflenought 17 Island,
     Duel Commander 23 Snow-Covered Plains em foil);
  2. as básicas que ESTÃO registadas na `copies` alocam-se como qualquer carta —
     dizem de que gaveta sair e entram na arrumação;
  3. as básicas são ISENTAS das regras de língua/edição: uma Island de Unhinged
     em inglês serve uma caixa de Premodern, que é *"só PT, só até ao Scourge"*;
  4. nas caixas de foil a foil vai à frente, mas a non-foil serve na mesma;
  5. o material especial (as Snow-Covered, que não existem em Unhinged) vai para
     a lista de Comprar, marcado *confirma se já tens* — e nunca para o
     `comprar_total`/`custo_total`, que são os números por que ele decide;
  6. as básicas continuam a NÃO contar para a percentagem nem para a venda.

Não toca na rede.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Config próprio: o teste não pode passar a depender de o André não mexer no dele.
CFG = {
    "caixas": [
        # Premodern: só PT e só até ao Scourge — é a caixa que prova a isenção.
        {"slot": "stifle", "nome": "Stiflenought", "formato": "premodern",
         "fonte": "deck", "ref": "Stiflenought", "balde": "Premodern (geral)",
         "estado": "permanente", "prioridade": 1},
        # Duel Commander: só foil, e é a única que joga Snow-Covered.
        {"slot": "dc", "nome": "Cloud (Duel Commander)", "formato": "duel-commander",
         "fonte": "deck", "ref": "Cloud", "balde": "Cloud",
         "estado": "permanente", "prioridade": 2},
    ],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": False,
         "lingua": "pt", "edicoes": "premodern", "estrita": True,
         "baldes": ["Colecção", "Premodern (geral)", "SPML"]},
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "acabamento": "foil"},
    ],
    "basicas": {"isentas_de_regras": True, "comprar_se_material_especial": True,
                "edicao": "Unhinged"},
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_colecao": {},
}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout  # noqa: E402

import deckboxes  # noqa: E402

# `released_at` conta: a tranca do Premodern é até ao Scourge (2003-05-26). O
# Unhinged é de 2004, o que torna a isenção visível — sem ela a Island dele nem
# sequer era VISTA por uma caixa de Premodern (`_fora_de_vista`).
CATALOGO = [
    ("Island", "unh", "2004-11-19"),
    ("Plains", "unh", "2004-11-19"),
    ("Snow-Covered Plains", "mh1", "2019-06-14"),
    ("Stifle", "scg", "2003-05-26"),
    ("Sol Ring", "unh", "2004-11-19"),
]

_ABERTAS = []      # segura os context managers: sem isto o GC fecha a ligação


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
               VALUES (?,?,?,?,'S',?,'en','common','Land',0,'',?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]),
             rel, json.dumps({"premodern": "legal", "legacy": "legal",
                              "commander": "legal"})))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub="Colecção"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub_id))
    con.commit()


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def montada(con):
    """As duas caixas do André, em miniatura: 17 Island no Premodern e 23
    Snow-Covered Plains no Duel Commander — os dois números que ele deu."""
    con_ = con
    deck(con_, "Stiflenought", "premodern", [("Stifle", 4), ("Island", 17)])
    deck(con_, "Cloud", "duel-commander",
         [("Sol Ring", 1), ("Snow-Covered Plains", 23)])
    return con_


def _bloco(rep, slot):
    """O bloco de básicas de uma caixa, por nome. Sai do `plano_montar`, que é
    exactamente o que a página e o CLI mostram."""
    plano = loadout.plano_montar(rep, slot)
    return {b["nm"]: b for b in plano["basicas"]}, plano


# ---------------------------------------------------------------------------
def caso_o_bloco_existe_com_as_quantidades_certas():
    """O caso dele, à letra: o painel Montar tem de dizer 17 Island e 23
    Snow-Covered Plains foil. Antes disto o bloco não existia de todo."""
    con = montada(base())
    rep = loadout.report(con)

    st, plano = _bloco(rep, "stifle")
    assert set(st) == {"Island"}, st
    assert st["Island"]["need"] == 17, st["Island"]
    assert plano["basicas_copias"] == 17, plano

    dc, plano = _bloco(rep, "dc")
    assert dc["Snow-Covered Plains"]["need"] == 23, dc
    # O material que a caixa exige é só o ACABAMENTO: a língua e a edição não
    # entram porque as básicas são isentas delas.
    assert dc["Snow-Covered Plains"]["req"] == "foil", dc
    assert st["Island"]["req"] == "", st["Island"]
    print("bloco de basicas: Stiflenought 17 Island, DC 23 Snow-Covered Plains foil")


def caso_as_basicas_registadas_alocam_se():
    """As cópias que a colecção TEM entram na alocação como qualquer outra carta:
    dizem de que gaveta sair, e por isso entram na arrumação. Sem isso ele tinha
    23 Snow-Covered Plains em casa e o painel mandava-o comprá-las."""
    con = montada(base())
    add(con, "Snow-Covered Plains", 23, finish="foil")
    rep = loadout.report(con)

    dc, plano = _bloco(rep, "dc")
    b = dc["Snow-Covered Plains"]
    assert b["da_base"] == 23 and b["granel"] == 0 and b["comprar"] == 0, b
    assert sum(m["q"] for m in b["tirar"]) == 23, b["tirar"]
    assert b["tirar"][0]["de"] == "Colecção", b["tirar"]
    # E não se misturam com a grelha por cor do passo 1 — são outra gaveta.
    assert all(not m["basica"] for m in plano["tirar"]), plano["tirar"]
    # Mas contam para a arrumação: é o mesmo gesto, e a caixa fica a saber o que
    # tem lá dentro quando ele carrega em "sleevado e na caixa".
    assert rep["arrumacao"]["copias"] >= 23, rep["arrumacao"]["copias"]
    print("as basicas registadas alocam-se e dizem de que gaveta sair")


def caso_as_basicas_sao_isentas_das_regras():
    """*"Todas as minhas lands básicas são de Unhinged, em inglês."* A caixa de
    Premodern é `estrita` — só PT e só até ao Scourge —, e mesmo assim aloca a
    Island de Unhinged em inglês. Sem a isenção a caixa nem a VIA."""
    con = montada(base())
    add(con, "Island", 17)                      # unh, EN, nonfoil
    rep = loadout.report(con)

    st, _ = _bloco(rep, "stifle")
    b = st["Island"]
    assert b["da_base"] == 17 and b["granel"] == 0, b
    assert b["comprar"] == 0, "uma básica de Unhinged nunca se compra"
    # A tranca continua inteira para tudo o que NÃO é básica: o Stifle é de uma
    # edição da era mas está em inglês, e essa caixa só fecha com PT.
    add(con, "Stifle", 4)
    rep = loadout.report(con)
    s = next(x for x in rep["slots"] if x["slot"] == "stifle")
    stifle = next(m for m in s["missing"] if m["nm"] == "Stifle")
    assert stifle["comprar"] == 4, stifle
    print("as basicas escapam as regras de lingua/edicao; o resto nao")


def caso_a_caixa_de_foil_prefere_a_foil():
    """*"Nas caixas foil prefere as foil se existirem, senão non-foil."* É uma
    preferência e não um requisito: ao contrário das outras cartas, uma básica
    non-foil também fecha o slot — senão o Duel Commander mandava comprar 23
    Snow-Covered Plains que estão na gaveta."""
    con = montada(base())
    add(con, "Snow-Covered Plains", 10, finish="foil")
    add(con, "Snow-Covered Plains", 10, finish="nonfoil")
    rep = loadout.report(con)

    dc, _ = _bloco(rep, "dc")
    b = dc["Snow-Covered Plains"]
    assert b["da_base"] == 20, b
    assert loadout.e_foil(b["tirar"][0]["finish"]), "a foil vai à frente"
    # e as 3 que faltam são compra, porque não há Snow-Covered em Unhinged
    assert b["comprar"] == 3 and b["granel"] == 0, b
    print("caixa de foil: a foil primeiro, a non-foil serve na mesma")


def caso_o_material_especial_vai_para_comprar():
    """As Snow-Covered não existem em Unhinged: o que a colecção não tem é compra,
    marcada *confirma se já tens*. É a ÚNICA básica que se compra."""
    con = montada(base())
    add(con, "Island", 17)
    rep = loadout.report(con)

    dc, _ = _bloco(rep, "dc")
    b = dc["Snow-Covered Plains"]
    assert b["comprar"] == 23 and b["granel"] == 0, b
    st, _ = _bloco(rep, "stifle")
    assert st["Island"]["comprar"] == 0, st["Island"]

    # E NUNCA no total por que ele decide: o `comprar_total`/`custo_total` são as
    # cartas a sério. Somar 23 Plains a confirmar mexia no número da decisão.
    assert rep["basicas_comprar_total"] == 23, rep["basicas_comprar_total"]
    assert all(m["nm"] != "Snow-Covered Plains"
               for s in rep["slots"] for m in s["missing"])
    print("as Snow-Covered vao para comprar, a parte do total de compras")


def caso_as_basicas_nao_contam_para_a_percentagem():
    """A regra de sempre, que não muda: uma básica conta como tida. Se contasse
    de outra maneira, a percentagem de um deck passava a medir quantas terras ele
    joga — e a ordem por % completo do Premodern ia atrás."""
    con = montada(base())
    rep = loadout.report(con)
    s = next(x for x in rep["slots"] if x["slot"] == "stifle")
    ilha = next(m for m in s["have"] if m["nm"] == "Island")
    assert ilha["got"] == ilha["need"] == 17, ilha
    assert ilha["missing"] == 0 and ilha["comprar"] == 0, ilha
    # 4 Stifle em falta de 21 cartas: a percentagem é 17/21, as terras contam.
    assert s["pct"] == round(100 * 17 / 21), s["pct"]
    print("as basicas contam como tidas: a % nao mede quantas terras o deck joga")


def caso_as_basicas_nao_entram_na_venda():
    """Cópias a mais de uma básica nunca são excedente. A regra já existia (o
    `sell_list` salta as `BASICS`) e a alocação nova não lhe pode mexer."""
    con = montada(base())
    add(con, "Island", 40)
    rep = loadout.report(con)
    tudo = (rep["venda"] + rep["venda_rl"] + rep["guardar"] + rep["retidos"])
    assert all(r["nm"] != "Island" for r in tudo), [r["nm"] for r in tudo]
    print("40 Island a mais e zero linhas de venda")


# ---------------------------------------------------------------------------
def _pagina(con):
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out)
    return out


def caso_a_pagina_leva_o_bloco():
    """O payload da Deckboxes tem de trazer o bloco e a lista de compras de
    básicas — a página é JSON + JavaScript, e uma chave em falta dá uma aba em
    branco sem um único erro no gerador."""
    con = montada(base())
    add(con, "Island", 17)
    pagina = _pagina(con)
    txt = pagina.read_text(encoding="utf-8")
    d = json.loads(re.search(
        r'<script id="dados" type="application/json">(.*?)</script>',
        txt, re.S).group(1).replace("<\\/", "</"))
    caixas = {c["slot"]: c for c in d["caixas"]}
    st = caixas["stifle"]["montar"]["basicas"]
    assert [b["nm"] for b in st] == ["Island"], st
    assert st[0]["need"] == 17 and st[0]["da_base"] == 17, st
    assert d["basicas_edicao"] == "Unhinged", d["basicas_edicao"]
    # As Snow-Covered do Duel Commander, na lista geral de compras de básicas.
    geral = {b["nm"]: b for b in d["basicas"]}
    assert geral["Snow-Covered Plains"]["q"] == 23, geral
    assert geral["Snow-Covered Plains"]["req"] == "foil", geral
    assert d["resumo"]["basicas"] == 23, d["resumo"]
    print("o payload da Deckboxes traz o bloco e as basicas a comprar")

    # E o que o browser DESENHA: sem isto, um erro no JS só aparecia ao clicar.
    if not shutil.which("node"):
        print("html das basicas: sem `node`, saltado")
        return
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    abas = json.loads(dump.read_text(encoding="utf-8"))
    caixa = abas.get("stifle") or ""
    assert "Terrenos básicos" in caixa, caixa[:600]
    assert "17" in caixa and "Island" in caixa
    compra = abas.get("comprar") or ""
    assert "Terrenos básicos" in compra, compra[-800:]
    assert "confirma se já tens" in compra, compra[-800:]
    # O bloco copiado vai comentado: o Cardmarket ignora as linhas com `//`, e
    # 17 Island a sério no carrinho era comprar terras que ele tem em casa.
    assert "// 17 Island (na coleccao)" in caixa, caixa[-1500:]
    print("a pagina desenha o bloco, e o texto copiado leva as basicas comentadas")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("caso_"):
            fn()
    print("\nOK — os terrenos básicos aparecem, e vêm da pilha certa.")
