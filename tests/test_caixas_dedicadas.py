"""CADA DECK BOX COM AS SUAS CARTAS (André, 2026-09-19, à letra): *"cada deck
deverá ter as suas próprias cartas dentro, não repetindo com outros decks!"*

Supersede o "ir buscar a outra caixa" de 2026-09-07, a partilha de compras da
v4 e a partilha entre caixas de Premodern de 2026-09-08. O que aqui se tranca:

  1. **nenhuma caixa vai buscar a outra, em nenhum formato** — Premodern, cEDH,
     Duel Commander, Pauper, SPML, e entre formatos (DC ↔ Modern): o `noutra` e
     as suas metades são zero, `conflitos` e `partilhas` vazios;
  2. **uma carta pedida por duas caixas é COMPRA na segunda** — o `missing`
     conta-a, o "fechar tudo" soma-a, a wantlist pede-a;
  3. **o config não devolve a partilha** — `dedicado: false` no grupo ou na
     caixa não tem efeito; `dedicadas()` devolve todas; `_empresta` é sempre
     falso;
  4. **a EXCEPÇÃO do Premodern fica**: o tecto de 4 no total — se ele já tem 4
     no grupo, a caixa de menor prioridade mostra *"não se compra (limite de 4
     no total; está no <deck>)"*, fora do "fechar tudo"; o tecto conta também o
     que o grupo vai comprar;
  5. **a nota "tens N no X"** — a página desenha-a (payload e HTML) sem a
     contar: a carta continua na wantlist e no `comprar`; a aba Partilhadas
     não aparece na fila de abas;
  6. consequência: uma caixa de Premodern montada e com conteúdo confirmado
     passa a CONGELAR (era impossível enquanto o grupo partilhava).

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
# Um config com `dedicado: false` em TODOS os grupos, de propósito: é o que
# prova que a chave deixou de mandar.
CFG = {
    "regras_colecao": {}, "decks_vigiados": [],
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": False,
         "playset_maximo": 4, "prioridade_por": "pct", "lingua": "pt",
         "edicoes": "premodern", "estrita": True,
         "baldes": ["Colecção", "Caixa Reserved List"]},
        {"grupo": "cedh", "formatos": ["cedh"], "dedicado": False,
         "lingua": "en", "acabamento": "nonfoil"},
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "dedicado": False, "acabamento": "foil"},
        {"grupo": "pauper", "formatos": ["pauper"], "dedicado": False,
         "acabamento": "prefere_foil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "dedicado": False, "lingua": "en", "acabamento": "foil"},
    ],
}
(_TMP / "cfg.json").write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout  # noqa: E402

import deckboxes  # noqa: E402

# (nome, edição, data, reserved)
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 0),
    ("Brushland", "ice", "1995-06-03", 0),
    ("Sol Ring", "c21", "2021-04-23", 0),
    ("Thoughtcast", "mrd", "2003-10-02", 0),
    ("Frogmite", "mrd", "2003-10-02", 0),
    ("Portable Hole", "afr", "2021-07-23", 0),
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
                             "commander": "legal", "pauper": "legal"}), rl))
            for fin in ("nonfoil", "foil"):
                con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                            "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                            "'2026-09-19', ?)", (f"id-{i}-{lang}", fin, 2.0))
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
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def slot(nome, fmt, ref=None, **kw):
    d = {"slot": nome.lower().replace(" ", "-"), "nome": nome, "formato": fmt,
         "fonte": "deck", "ref": ref or nome, "balde": "Colecção", "prioridade": 1}
    d.update(kw)
    return d


def por_nome(rep):
    return {s["nome"]: s for s in rep["slots"]}


def linha(s, nm):
    return next(m for m in s["have"] + s["missing"] if m["nm"] == nm)


def _sem_ir_buscar(rep):
    for s in rep["slots"]:
        assert s["noutra"] == 0 and s["noutra_montada"] == 0, s["nome"]
        assert s["noutra_reservada"] == 0 and s["noutra_futura"] == 0, s["nome"]
        assert s["noutra_caixa"] == [] and s["buscar_montada"] == [], s["nome"]
        assert s["buscar_reservada"] == [] and s["buscar_futura"] == [], s["nome"]
        for m in s["missing"]:
            assert m["noutra"] == {} and m["noutra_q"] == 0, m
            assert m["noutra_lotes"] == [] and m["noutra_futura"] == {}, m
    assert rep["noutra_total"] == 0 and rep["noutra_montada_total"] == 0
    assert rep["noutra_reservada_total"] == 0 and rep["noutra_futura_total"] == 0
    assert rep["conflitos"] == [] and rep["partilhas"] == []
    assert rep["poupado_total"] == 0


# ---------------------------------------------------------------------------
def caso_nenhuma_caixa_vai_buscar_a_outra_em_formato_nenhum():
    """Dois decks por formato a pedir a mesma carta com uma cópia só: em todos
    os formatos a segunda COMPRA — e entre formatos (DC ↔ Modern) também."""
    casos = [("premodern", "Swords to Plowshares", "pt", "nonfoil"),
             ("cedh", "Sol Ring", "en", "nonfoil"),
             ("duel-commander", "Sol Ring", "en", "foil"),
             ("pauper", "Frogmite", "en", "nonfoil"),
             ("modern", "Thoughtcast", "en", "foil")]
    for fmt, nm, lang, fin in casos:
        con = base()
        deck(con, "Um", fmt, [(nm, 1)])
        deck(con, "Dois", fmt, [(nm, 1)])
        add(con, nm, 1, finish=fin, lang=lang)
        rep = loadout.report(con, [slot("Um", fmt, prioridade=1),
                                   slot("Dois", fmt, prioridade=2)])
        s = por_nome(rep)
        primeira, segunda = sorted(s.values(), key=lambda x: x["prioridade"])
        assert primeira["pct"] == 100 and primeira["comprar"] == 0, (fmt, primeira)
        assert segunda["pct"] == 0 and segunda["comprar"] == 1, (fmt, segunda)
        assert segunda["custo"] == 2.0, (fmt, segunda["custo"])
        m = linha(segunda, nm)
        assert m["missing"] == 1 and m["comprar"] == 1, (fmt, m)
        assert m["noutra_nota"] == {primeira["nome"]: 1}, (fmt, m["noutra_nota"])
        assert loadout.nota_onde(m) == f"tens 1 no {primeira['nome']}"
        if fmt == "premodern":
            # A única excepção: o tecto de 4. Com 1 no grupo compra-se a 2.ª.
            assert m["playset_bloqueado"] == 0, m
        _sem_ir_buscar(rep)
        assert rep["comprar_total"] == 1 and rep["custo_total"] == 2.0, (fmt, rep["custo_total"])
        assert all(x["dedicado"] for x in rep["slots"]), "dedicado em todas"
        print(f"{fmt}: a segunda caixa compra; nada de 'ir buscar'")

    # Entre formatos: o Duel Commander levou a Sol Ring foil e o Modern compra.
    con = base()
    deck(con, "Cloud", "duel-commander", [("Sol Ring", 1)])
    deck(con, "Oswald", "modern", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil")
    rep = loadout.report(con, [slot("Cloud", "duel-commander"), slot("Oswald", "modern")])
    s = por_nome(rep)
    assert s["Cloud"]["pct"] == 100 and s["Oswald"]["comprar"] == 1, s
    assert linha(s["Oswald"], "Sol Ring")["noutra_nota"] == {"Cloud": 1}
    _sem_ir_buscar(rep)
    print("entre formatos (DC -> Modern) o mesmo: compra, com a nota")


def caso_o_config_nao_devolve_a_partilha():
    """`dedicado: false` no grupo (o config deste teste) e na caixa: sem efeito.
    A resposta está num sítio (`_empresta`), e é sempre não."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 1)])
    deck(con, "B", "legacy", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil")
    slots = [slot("A", "legacy", prioridade=1, dedicado=False),
             slot("B", "legacy", prioridade=2, dedicado=False, compras_dedicadas=False)]
    rep = loadout.report(con, slots)
    res = loadout.resolve_slots(con, slots)
    assert all(x["dedicado"] is True for x in res), [x["dedicado"] for x in res]
    assert loadout.dedicadas(res) == {"A", "B"}, loadout.dedicadas(res)
    assert loadout._empresta(res[1], "A", set()) is False
    assert loadout._empresta({"dedicado": False}, "X", set()) is False
    assert por_nome(rep)["B"]["comprar"] == 1
    _sem_ir_buscar(rep)
    # E o chip da caixa di-lo (uma regra que a página não diz é a página a mentir).
    textos = [t for _i, t, _c in loadout.rotulo_material(res[0])]
    assert any("não empresta nem vai buscar" in t for t in textos), textos
    print("dedicado: false no config nao tem efeito — a resposta e uma so")


def caso_o_premodern_respeita_o_limite_de_4_no_total():
    """A excepção mantida: o tecto de playset conta o GRUPO inteiro.

    Três caixas de Premodern pedem 4 Swords; ele tem 3 (na primeira, por %).
    O grupo pode chegar a 4: a primeira compra 1, e as outras duas ficam com
    as 4 POR TAPAR — ditas como *"não se compra (limite de 4 no total; está 4
    no Um)"* (a 4.ª que a Um vai comprar conta) —, fora do "fechar tudo".
    """
    con = base()
    for n in ("Um", "Dois", "Tres"):
        deck(con, n, "premodern", [("Swords to Plowshares", 4), ("Brushland", 1)])
    add(con, "Swords to Plowshares", 3, lang="pt")
    add(con, "Brushland", 1, lang="pt")
    slots = [slot("Um", "premodern", prioridade=1),
             slot("Dois", "premodern", prioridade=2),
             slot("Tres", "premodern", prioridade=3)]
    rep = loadout.report(con, slots)
    # As três empatam na % (é a mesma colecção): a ordem do grupo é pelo nome,
    # e quem fica com as cópias é a primeira dessa ordem.
    ordem = sorted(rep["slots"], key=lambda x: x["prioridade"])
    um, outras = ordem[0], ordem[1:]
    assert um["nome"] == "Dois" and um["pct"] == 80, (um["nome"], um["pct"])
    assert um["comprar"] == 1 and um["playset_bloqueado"] == 0, um
    for c in outras:
        n = c["nome"]
        stp, bl = linha(c, "Swords to Plowshares"), linha(c, "Brushland")
        assert stp["comprar"] == 0 and stp["playset_bloqueado"] == 4, stp
        assert stp["playset_onde"] == {"Dois": 4}, stp["playset_onde"]
        assert loadout.texto_playset(stp, 4) == \
            "4 não se compra (limite de 4 no total; está 4 no Dois)", \
            loadout.texto_playset(stp, 4)
        assert "4 não se compra (limite de 4 no total; está 4 no Dois)" in \
            loadout.nota_parcial(stp), loadout.nota_parcial(stp)
        # A Brushland: o grupo tem 1, tecto 4 → a Dois compra 1, a Tres compra 1
        # (3 no total). O tecto só corta o que passaria dos 4.
        assert bl["comprar"] == 1 and bl["playset_bloqueado"] == 0, bl
        assert c["comprar"] == 1 and c["playset_bloqueado"] == 4, (n, c["comprar"])
        assert c["custo"] == 2.0, ("só a Brushland conta para o fechar", c["custo"])
    assert rep["comprar_total"] == 3 and rep["custo_total"] == 6.0, rep["custo_total"]
    assert rep["bloqueado_total"] == 8, rep["bloqueado_total"]
    lim = rep["limites"]
    assert [(g["nm"], g["bloqueado"], g["onde"]) for g in lim] == \
        [("Swords to Plowshares", 8, {"Dois": 4})], lim
    _sem_ir_buscar(rep)
    print("Premodern: o tecto de 4 no total fica, e diz em que caixa estao as copias")

    # O tecto NÃO se aplica aos outros grupos: três caixas de Modern a pedir 4
    # compram 12.
    con = base()
    for n in ("Um", "Dois", "Tres"):
        deck(con, n, "modern", [("Thoughtcast", 4)])
    rep = loadout.report(con, [slot(n, "modern", prioridade=i)
                               for i, n in enumerate(("Um", "Dois", "Tres"), 1)])
    assert rep["comprar_total"] == 12 and rep["bloqueado_total"] == 0, rep["comprar_total"]
    print("fora do Premodern nao ha tecto: cada caixa compra as suas 4")


def caso_a_pagina_desenha_a_nota_sem_a_contar():
    """O payload e o HTML: *"tens 1 no Cloud"* na carta, na wantlist e no bloco
    «tens noutra caixa»; a carta continua vermelha, na wantlist e no `comprar`;
    a aba Partilhadas não está na fila; o texto copiado pede a carta."""
    con = base()
    deck(con, "Cloud", "duel-commander", [("Portable Hole", 1)])
    deck(con, "Oswald", "modern", [("Portable Hole", 1), ("Thoughtcast", 1)])
    add(con, "Portable Hole", 1, finish="foil")
    slots = [slot("Cloud", "duel-commander"), slot("Oswald", "modern")]
    rep = loadout.report(con, slots)
    d = deckboxes.payload(con, rep)
    assert d["partilhadas"] == [] and d["resumo"]["noutra"] == 0, d["resumo"]
    assert d["resumo"]["comprar"] == 2, d["resumo"]
    c = next(x for x in d["caixas"] if x["slot"] == "oswald")
    ph = next(x for x in c["cartas"] if x["nm"] == "Portable Hole")
    assert ph["est"] == "miss" and ph["comprar"] == 1 and ph["noutra"] == {}, ph
    assert ph["nota"] == "tens 1 no Cloud" and ph["onde"] == [], ph
    w = next(x for x in c["wantlist"] if x["nm"] == "Portable Hole")
    assert w["q"] == 1 and w["nota"] == "tens 1 no Cloud", w
    assert c["notas_onde"] == [{"nm": "Portable Hole", "nota": "tens 1 no Cloud"}], c["notas_onde"]
    assert c["buscar"] == {"montada": [], "reservada": [], "futura": []}, c["buscar"]
    assert c["comprar"] == 2 and c["noutra"] == 0, (c["comprar"], c["noutra"])
    # O índice leve (partes à parte) leva a nota como parte pesada — inversos.
    idx, partes = deckboxes.partir(d)
    assert "notas_onde" not in next(x for x in idx["caixas"] if x["slot"] == "oswald")
    assert deckboxes.juntar(idx, partes) == d
    print("payload: a nota vai na carta, na wantlist e no bloco; nada e descontado")

    if not shutil.which("node"):
        print("HTML: sem `node`, saltado")
        return
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    out.write_text(deckboxes.html_page(con, rep=rep), encoding="utf-8")
    dump = out.with_name("abas.json")
    p = subprocess.run(["node", str(Path(__file__).with_name("render_deckboxes.js")),
                        str(out), str(dump)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    abas = json.loads(dump.read_text(encoding="utf-8"))
    h = abas["oswald"]
    assert "tens 1 no Cloud" in h and "tens noutra caixa" in h, h[:1500]
    assert "em Cloud" not in h and "destinada a" not in h, "a nota nao e fonte"
    assert "1 Portable Hole" in h, "a carta continua na wantlist"
    assert "Partilhadas" not in abas.get("_nav", "") and "Partilhadas" not in abas["todas"], \
        "a aba Partilhadas nao aparece na fila quando esta vazia"
    assert "tens 1 no Cloud" in abas["comprar"], abas["comprar"][:1200]
    print("HTML: 'tens 1 no Cloud' desenhado, a carta pedida na mesma, sem aba Partilhadas")


def caso_uma_caixa_de_premodern_montada_congela():
    """Consequência da regra: `congelada` exige ser dedicada, e desde 2026-09-19
    todas o são. Uma caixa de Premodern montada e com conteúdo confirmado
    fica congelada — a cópia que a lista de hoje já não pede fica presa."""
    con = base()
    deck(con, "PM", "premodern", [("Swords to Plowshares", 1)])
    cid = add(con, "Swords to Plowshares", 1, lang="pt")
    add(con, "Brushland", 1, lang="pt")
    s = slot("PM", "premodern", estado="montada")
    rep = loadout.report(con, [s])
    assert por_nome(rep)["PM"]["congelada"] is False, "sem conteudo confirmado nao congela"
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?, 'pm', 1)",
                (cid,))
    con.commit()
    rep = loadout.report(con, [s])
    assert por_nome(rep)["PM"]["congelada"] is True, por_nome(rep)["PM"]["estado"]
    # A lista muda e a cópia fica presa: sai como delta de actualização.
    con.execute("UPDATE deck_cards SET card_name = 'Brushland'")
    con.commit()
    rep = loadout.report(con, [s])
    pm = por_nome(rep)["PM"]
    assert [p["nm"] for p in pm["presos"]] == ["Swords to Plowshares"], pm["presos"]
    assert "pm" in rep["actualizacoes"], rep["actualizacoes"]
    assert "Swords to Plowshares" not in {r["nm"] for r in rep["venda"]}
    print("uma caixa de Premodern montada e confirmada passa a congelar")


def run():
    for fn in (caso_nenhuma_caixa_vai_buscar_a_outra_em_formato_nenhum,
               caso_o_config_nao_devolve_a_partilha,
               caso_o_premodern_respeita_o_limite_de_4_no_total,
               caso_a_pagina_desenha_a_nota_sem_a_contar,
               caso_uma_caixa_de_premodern_montada_congela):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
