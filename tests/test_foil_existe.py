"""«SÓ FOIL» SÓ QUANDO A CARTA EXISTE EM FOIL (André, 2026-09-19, à letra):
*"quando escreves que a carta não serve porque devia ser foil e não é foil,
confirma se há foil."*

O que aqui se tranca, contra um catálogo de teste com as impressões de cartas
REAIS da base dele (as que o teste de 2026-09-19 apanhou):

  1. a **Glimmer Lens** (ONC, só nonfoil) FECHA o slot do Duel Commander em
     nonfoil — não é substituto, não vai à venda, e a percentagem sobe;
  2. a **Dust Bowl** nonfoil continua a NÃO servir (existe em foil: MMQ 1999,
     EXP 2016, OTP 2024, EOS 2025) — e a mensagem diz as edições, as 3–4
     primeiras por data, EN, sem repetir o código;
  3. a **Swift Reconfiguration** só tem foil na `prm` DIGITAL (MTGO): para o
     papel nunca saiu em foil, e a nonfoil serve — um foil de MTGO não se mete
     numa caixa;
  4. a wantlist de uma carta sem foil pede **nonfoil** e di-lo (*"nonfoil —
     nunca saiu em foil"*), ao preço do nonfoil; a `marca_compra` é `EN nonfoil`;
  5. a **venda** não leva a nonfoil de uma carta sem foil que uma caixa pede
     (está alocada), nem a põe em `guardar`;
  6. a Reserved List continua a poder ser nonfoil como sempre;
  7. uma carta que o catálogo NÃO conhece não é "sem foil": a regra da caixa
     fica como está (não se inventa);
  8. a verdade vive num sítio (`acabamento_efectivo`): `regra_da_carta`,
     `finishes_aceites`, `material_da_caixa`, `impressoes_da_falta` e o
     `encomendas.validar` dão nonfoil para a carta sem foil e foil para a outra;
  9. a página (payload e HTML desenhado) e o CLI dizem-no.

Não toca na rede.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {"regras_colecao": {}, "decks_vigiados": [],
       "baldes_coleccao": ["Colecção", "Caixa Reserved List"]}
(_TMP / "cfg.json").write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, encomendas, loadout, scryfall  # noqa: E402
from mtgvault import cli  # noqa: E402

import deckboxes  # noqa: E402

# (nome, edição, data, acabamentos, língua, digital, set_type, reserved) — as
# impressões tal como estão no catálogo da base dele a 2026-09-19.
CATALOGO = [
    ("Glimmer Lens", "onc", "2023-02-10", ["nonfoil"], "en", 0, "commander", 0),
    ("Dust Bowl", "mmq", "1999-10-04", ["nonfoil", "foil"], "en", 0, "expansion", 0),
    ("Dust Bowl", "wc00", "2000-08-02", ["nonfoil"], "en", 0, "memorabilia", 0),
    ("Dust Bowl", "exp", "2016-01-22", ["foil"], "en", 0, "masterpiece", 0),
    ("Dust Bowl", "otp", "2024-04-19", ["nonfoil", "foil"], "en", 0, "masterpiece", 0),
    ("Dust Bowl", "eos", "2025-08-01", ["foil"], "en", 0, "expansion", 0),
    ("Dust Bowl", "eos", "2025-08-01", ["nonfoil", "foil"], "en", 0, "expansion", 0),
    ("Dust Bowl", "mmq", "1999-10-04", ["nonfoil", "foil"], "pt", 0, "expansion", 0),
    ("Swift Reconfiguration", "nec", "2022-02-18", ["nonfoil"], "en", 0, "commander", 0),
    ("Swift Reconfiguration", "prm", "2022-07-14", ["nonfoil", "foil"], "en", 1, "promo", 0),
    ("Tangle Wire", "nem", "2000-02-14", ["nonfoil", "foil"], "en", 0, "expansion", 0),
    ("Tangle Wire", "v13", "2013-08-23", ["foil"], "en", 0, "from_the_vault", 0),
    ("Swan Song", "ths", "2013-09-27", ["nonfoil", "foil"], "en", 0, "expansion", 0),
    ("Swan Song", "c16", "2016-11-11", ["nonfoil"], "en", 0, "commander", 0),
    ("Mishra's Workshop", "atq", "1994-03-04", ["nonfoil"], "en", 0, "expansion", 1),
    ("Mox Diamond", "sth", "1998-03-02", ["nonfoil"], "en", 0, "expansion", 1),
    ("Island", "unh", "2004-11-19", ["nonfoil", "foil"], "en", 0, "funny", 0),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fins, lang, dig, st, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, set_type)
               VALUES (?,?,?,?,?,?,?,'rare','Artifact',1,'',?,?,?,?,?,?)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), str(i), lang,
             json.dumps(fins), rel,
             json.dumps({"legacy": "legal", "commander": "legal", "modern": "legal"}),
             dig, rl, st))
        for f in fins:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-19', ?)", (f"id-{i}", f, 10.0 if f == "foil" else 2.0))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub="Colecção", set_code=None):
    q_sql = "SELECT scryfall_id FROM catalog.cards WHERE name = ? AND lang = ?"
    args = [nm, lang]
    if set_code:
        q_sql += " AND set_code = ?"
        args.append(set_code)
    sid = con.execute(q_sql + " ORDER BY released_at LIMIT 1", args).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, 'player')",
                (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?", (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                   sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub_id))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def slot(nome, fmt, ref, **kw):
    d = {"slot": nome.lower().replace(" ", "-"), "nome": nome, "formato": fmt,
         "fonte": "deck", "ref": ref, "balde": "Colecção", "prioridade": 1}
    d.update(kw)
    return d


def por_nome(rep):
    return {s["nome"]: s for s in rep["slots"]}


def linha(s, nm):
    return next(m for m in s["have"] + s["missing"] if m["nm"] == nm)


DUST_BOWL_EDS = ["MMQ 1999", "EXP 2016", "OTP 2024", "EOS 2025"]


# ---------------------------------------------------------------------------
def caso_o_catalogo_diz_se_existe_em_foil():
    """`scryfall.impressoes_foil` / `loadout.foil_info`: papel, qualquer edição
    e língua, EN primeiro, sem repetir o código, digital e memorabilia fora."""
    con = base()
    assert scryfall.impressoes_foil(con, "Glimmer Lens") == []
    fi = loadout.foil_info(con, "Glimmer Lens")
    assert fi == {"existe": False, "edicoes": []}, fi
    fi = loadout.foil_info(con, "Dust Bowl")
    assert fi["existe"] and fi["edicoes"] == DUST_BOWL_EDS, fi
    # A `prm` da Swift Reconfiguration é digital (MTGO): não conta.
    assert loadout.foil_info(con, "Swift Reconfiguration")["existe"] is False
    # Uma que só tem foil em PT conta na mesma (qualquer língua) — e diz a edição.
    con.execute("UPDATE catalog.cards SET finishes = '[\"nonfoil\"]' WHERE name = 'Dust Bowl' "
                "AND lang = 'en'")
    con.commit()
    fi = loadout.foil_info(con, "Dust Bowl")
    assert fi["existe"] and fi["edicoes"] == ["MMQ 1999"], fi
    # A cache é por corrida: a mesma pergunta não volta ao catálogo.
    cache = {}
    loadout.foil_info(con, "Glimmer Lens", cache)
    con.execute("UPDATE catalog.cards SET finishes = '[\"foil\"]' WHERE name = 'Glimmer Lens'")
    con.commit()
    assert loadout.foil_info(con, "Glimmer Lens", cache)["existe"] is False
    assert loadout.foil_info(con, "Glimmer Lens")["existe"] is True
    # E uma carta que o catálogo não conhece NÃO é "sem foil": não se inventa.
    fi = loadout.foil_info(con, "Ademi of the Silkchutes")
    assert fi == {"existe": True, "edicoes": []}, fi
    # A mensagem, num sítio só.
    assert loadout.razao_nao_foil(DUST_BOWL_EDS) == \
        "não é foil (existe em foil: MMQ 1999, EXP 2016, OTP 2024, EOS 2025)"
    assert loadout.razao_nao_foil([]) == loadout.RAZAO_NAO_FOIL
    print("o catalogo diz se a carta existe em foil (papel, EN primeiro, sem digital)")


def caso_acabamento_efectivo_num_sitio_so():
    """A verdade da regra 1 vive em `acabamento_efectivo`; tudo o resto lê de lá."""
    con = base()
    dc = {"formato": "duel-commander", "acabamento": "foil", "nome": "Cloud"}
    pa = {"formato": "pauper", "acabamento": "prefere_foil"}
    ce = {"formato": "cedh", "acabamento": "nonfoil", "lingua": "en"}
    assert loadout.acabamento_efectivo(dc, True) == "foil"
    assert loadout.acabamento_efectivo(dc, False) == loadout.SEM_FOIL
    assert loadout.acabamento_efectivo(pa, False) == loadout.SEM_FOIL
    # O cEDH ("só nonfoil") não muda: uma carta que só existe em foil continua
    # a não lhe servir — ele não pediu o contrário.
    assert loadout.acabamento_efectivo(ce, False) == "nonfoil"
    gl = loadout.regra_da_carta(con, dc, "Glimmer Lens")
    db_ = loadout.regra_da_carta(con, dc, "Dust Bowl")
    assert gl["acabamento"] == loadout.SEM_FOIL and db_ is dc
    assert loadout.finishes_aceites(gl) == ("nonfoil",)
    assert loadout.finishes_aceites(db_) == loadout.FOIL_FINISHES
    assert loadout.material_da_caixa(gl) == ("nonfoil", "en")
    assert loadout.material_da_caixa(db_) == ("foil", "en")
    assert loadout.requisito_material(gl) == "nonfoil — nunca saiu em foil"
    assert loadout.requisito_material(db_) == "foil"
    assert loadout.marca_compra(gl) == "nonfoil" and loadout.marca_compra(db_) == "foil"
    sp = {"formato": "legacy", "acabamento": "foil", "lingua": "en"}
    assert loadout.requisito_material(loadout.regra_da_carta(con, sp, "Glimmer Lens")) \
        == "EN · nonfoil — nunca saiu em foil"
    assert loadout.marca_compra(loadout.regra_da_carta(con, sp, "Glimmer Lens")) \
        == "EN nonfoil"
    # O selector do «já a tenho» / das encomendas oferece as nonfoil, e o
    # `validar` das encomendas fica em nonfoil — sem `finish` explícito.
    eds = loadout.impressoes_da_falta(con, dc, "Glimmer Lens")
    assert [e["set"] for e in eds] == ["onc"], eds
    v = encomendas.validar(con, dict(dc, slot="dc"), "Glimmer Lens")
    assert v["finish"] == "nonfoil", v
    v = encomendas.validar(con, dict(dc, slot="dc"), "Dust Bowl")
    assert v["finish"] == "foil", v
    ok, porque = encomendas.cumpre_regra(con, dict(dc, slot="dc"), "Glimmer Lens",
                                         None, "en", "nonfoil")
    assert ok, porque
    ok, porque = encomendas.cumpre_regra(con, dict(dc, slot="dc"), "Dust Bowl",
                                         None, "en", "nonfoil")
    assert not ok and "foil" in porque, porque
    print("acabamento_efectivo: uma verdade, lida por finishes/material/requisito/encomendas")


def caso_nonfoil_de_carta_sem_foil_fecha_o_slot():
    """A Glimmer Lens nonfoil serve o Duel Commander; a Dust Bowl nonfoil não, e
    a recusa diz em que edições existe em foil. O mesmo no SPML e no Pauper."""
    con = base()
    deck(con, "Cloud", "duel-commander", [("Glimmer Lens", 1), ("Dust Bowl", 1),
                                         ("Swift Reconfiguration", 1)])
    add(con, "Glimmer Lens")
    add(con, "Dust Bowl", set_code="mmq")
    add(con, "Swift Reconfiguration")
    rep = loadout.report(con, [slot("Cloud", "duel-commander", "Cloud")])
    s = por_nome(rep)["Cloud"]
    assert s["tenho"] == 2 and s["pct"] == 67, (s["tenho"], s["pct"])
    gl = linha(s, "Glimmer Lens")
    assert gl["got"] == 1 and gl["foil_existe"] is False and gl["foil_edicoes"] == [], gl
    sr = linha(s, "Swift Reconfiguration")
    assert sr["got"] == 1 and sr["foil_existe"] is False, sr
    dbw = linha(s, "Dust Bowl")
    assert dbw["got"] == 0 and dbw["comprar"] == 1, dbw
    assert dbw["alt"] == {loadout.razao_nao_foil(DUST_BOWL_EDS): 1}, dbw["alt"]
    assert dbw["foil_existe"] and dbw["foil_edicoes"] == DUST_BOWL_EDS, dbw
    assert [m["nm"] for m in s["subs"]] == ["Dust Bowl"], s["subs"]
    # E os lotes dizem o mesmo (é de lá que o `_porque_nao` lê).
    lote = rep["pool"]["Dust Bowl"][0]
    assert lote["substituto"] == {"Cloud": loadout.razao_nao_foil(DUST_BOWL_EDS)}
    assert rep["pool"]["Glimmer Lens"][0]["substituto"] == {}
    print("Duel Commander: a Glimmer Lens nonfoil fecha o slot; a Dust Bowl nao, e diz onde ha foil")

    # SPML ("tudo foil e inglês") e Pauper ("foil se houver") fazem o mesmo.
    con = base()
    deck(con, "Oswald", "modern", [("Glimmer Lens", 1), ("Tangle Wire", 1)])
    deck(con, "Luffy", "pauper", [("Swan Song", 1)])
    add(con, "Glimmer Lens")
    add(con, "Tangle Wire")
    add(con, "Swan Song")
    rep = loadout.report(con, [slot("Oswald", "modern", "Oswald"),
                               slot("Luffy", "pauper", "Luffy", prioridade=2)])
    s = por_nome(rep)
    assert s["Oswald"]["tenho"] == 1, s["Oswald"]["tenho"]
    tw = linha(s["Oswald"], "Tangle Wire")
    assert tw["alt"] == {loadout.razao_nao_foil(["NEM 2000", "V13 2013"]): 1}, tw["alt"]
    assert s["Luffy"]["pct"] == 100, "o Pauper aceita a nonfoil de qualquer maneira"
    print("SPML e Pauper: o mesmo — a exigencia de foil so vale onde ha foil")


def caso_a_wantlist_pede_nonfoil_quando_nao_ha_foil():
    """Uma falta de carta sem foil numa caixa de foil pede nonfoil, di-lo, e
    custa o preço do nonfoil (o foil não existe para o pedir)."""
    con = base()
    deck(con, "Cloud", "duel-commander", [("Glimmer Lens", 1), ("Dust Bowl", 1)])
    rep = loadout.report(con, [slot("Cloud", "duel-commander", "Cloud")])
    s = por_nome(rep)["Cloud"]
    gl, dbw = linha(s, "Glimmer Lens"), linha(s, "Dust Bowl")
    assert gl["req_compra"] == "nonfoil — nunca saiu em foil", gl["req_compra"]
    assert gl["marca_compra"] == "nonfoil" and gl["price_finish"] == "nonfoil", gl
    assert gl["unit"] == 2.0 and gl["cost"] == 2.0, gl
    assert dbw["req_compra"] == "foil" and dbw["marca_compra"] == "foil", dbw
    assert dbw["unit"] == 10.0 and dbw["price_finish"] == "foil", dbw
    assert s["custo"] == 12.0, s["custo"]
    # Na página: a linha da wantlist e a da aba Comprar dizem-no; a carta leva
    # a marca `sfoil`; o texto copiado «com material» diz nonfoil.
    d = deckboxes.payload(con, rep)
    c = next(x for x in d["caixas"] if x["slot"] == "cloud")
    w = {x["nm"]: x for x in c["wantlist"]}
    assert w["Glimmer Lens"]["sfoil"] is True and w["Glimmer Lens"]["req"] == \
        "nonfoil — nunca saiu em foil", w["Glimmer Lens"]
    assert w["Glimmer Lens"]["mat"] == "nonfoil" and w["Dust Bowl"]["mat"] == "foil"
    assert w["Dust Bowl"]["sfoil"] is False
    cartas = {x["nm"]: x for x in c["cartas"]}
    assert cartas["Glimmer Lens"]["sfoil"] and not cartas["Dust Bowl"]["sfoil"]
    g = {x["nm"]: x for x in d["compras"]}
    assert g["Glimmer Lens"]["sfoil"] and g["Glimmer Lens"]["req"] == \
        "nonfoil — nunca saiu em foil", g["Glimmer Lens"]
    assert g["Glimmer Lens"]["mat"] == "nonfoil", g["Glimmer Lens"]
    # O ranking do metagame (`foil_report`) faz a mesma conta: preço nonfoil.
    print("a wantlist pede nonfoil, di-lo, e custa o nonfoil")


def caso_a_venda_nao_leva_a_nonfoil_que_a_caixa_usa():
    """A Glimmer Lens nonfoil que fecha o slot está ALOCADA: não vai à venda
    nem a `guardar`. A Dust Bowl nonfoil continua substituto (guardar) e a
    razão diz as edições em foil — na venda e na exportação."""
    con = base()
    deck(con, "Cloud", "duel-commander", [("Glimmer Lens", 1), ("Dust Bowl", 1),
                                         ("Mox Diamond", 1)])
    add(con, "Glimmer Lens", 5)              # 5: uma acima do playset
    add(con, "Dust Bowl", 5, set_code="mmq")  # idem — e nenhuma serve
    add(con, "Mox Diamond")                  # Reserved List: nonfoil serve
    rep = loadout.report(con, [slot("Cloud", "duel-commander", "Cloud")])
    s = por_nome(rep)["Cloud"]
    assert s["tenho"] == 2, ("Glimmer Lens + Mox Diamond (RL)", s["tenho"])
    nomes = lambda k: {r["nm"] for r in rep[k]}    # noqa: E731
    # A 5.ª Glimmer Lens é excedente NORMAL (a caixa tem a dela): vai à venda
    # como qualquer carta, sem "guardar" — não é substituto de nada.
    gl = [r for r in rep["venda"] if r["nm"] == "Glimmer Lens"]
    assert sum(r["q"] for r in gl) == 1 and "excedente" in gl[0]["reason"], gl
    assert "Glimmer Lens" not in nomes("guardar")
    assert "Mox Diamond" not in nomes("venda_rl") | nomes("rl_sem_historico")
    # A 5.ª Dust Bowl é substituto (serve a caixa, só não é foil): guarda-se, e a
    # razão diz onde há foil.
    g = next(r for r in rep["guardar"] if r["nm"] == "Dust Bowl")
    assert "existe em foil: MMQ 1999" in g["reason"], g["reason"]
    # A exportação da venda leva a mesma razão (é a mesma linha).
    from mtgvault import venda
    fora = [l for bloco in venda.fora_da_exportacao(rep) for l in bloco["linhas"]
            if l["nm"] == "Dust Bowl"]
    assert fora and "existe em foil: MMQ 1999" in fora[0]["motivo"], fora
    print("a venda nao leva a Glimmer Lens; a Dust Bowl fica em guardar e diz onde ha foil")


def caso_a_pagina_e_o_cli_dizem_no():
    """O HTML desenhado (se houver `node`) e o `loadout <deck>` do CLI."""
    con = base()
    deck(con, "Cloud", "duel-commander", [("Glimmer Lens", 1), ("Dust Bowl", 1),
                                         ("Swan Song", 1)])
    add(con, "Glimmer Lens")
    add(con, "Dust Bowl", set_code="mmq")
    slots = [slot("Cloud", "duel-commander", "Cloud")]
    rep = loadout.report(con, slots)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli._loadout_detalhe(rep, "Cloud")
    txt = buf.getvalue()
    assert "existe em foil: MMQ 1999, EXP 2016" in txt, txt
    assert "Swan Song" in txt and "1 Swan Song [foil]" in txt, txt
    assert "Glimmer Lens" not in txt.split("wantlist")[1], "a Glimmer Lens esta na caixa"
    print("CLI: a recusa diz as edicoes em foil")

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
    h = abas["cloud"]
    assert "existe em foil: MMQ 1999, EXP 2016, OTP 2024, EOS 2025" in h, h[:1500]
    assert "nunca saiu em foil" in h, h[:1500]
    assert re.search(r'data-nm="Glimmer Lens"[^>]*title="[^"]*nunca saiu em foil', h) \
        or "nunca saiu em foil — a nonfoil serve" in h, "o cartao da Glimmer Lens di-lo"
    print("HTML: a caixa diz as edicoes em foil e que a Glimmer Lens nunca saiu em foil")


def run():
    for fn in (caso_o_catalogo_diz_se_existe_em_foil,
               caso_acabamento_efectivo_num_sitio_so,
               caso_nonfoil_de_carta_sem_foil_fecha_o_slot,
               caso_a_wantlist_pede_nonfoil_quando_nao_ha_foil,
               caso_a_venda_nao_leva_a_nonfoil_que_a_caixa_usa,
               caso_a_pagina_e_o_cli_dizem_no):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
