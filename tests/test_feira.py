"""A FEIRA: moeda de troca vs. o que quero trazer (André, 2026-09-20, à letra):
*"fazemos logo uma projeção do que vou levar como moeda de troca para o que
quero trazer; indico-te a wantlist e prováveis vendors que lá estarão, que
poderão ter os preços das cartas no market, e avaliamos."*

O que aqui se tranca (`mtgvault/feira.py`):

  1. **as taxas** — omissão 0,55 / 0,70, aceitam `55` e `0.55`, recusam o que
     não é uma fracção; o dinheiro e a troca são Trend × taxa;
  2. **«levo / não levo»** — a marca fica no config, por impressão; uma linha
     marcada sai dos totais e volta quando se desmarca;
  3. **«só validadas»** — com a campanha ligada só vão as cópias com foto (o
     resto fica em `fora_foto`, à vista); com o filtro a `false`, ou sem
     campanha, vai tudo;
  4. **wantlist manual + automática sem duplicar** — a mesma carta para a
     mesma caixa é UMA linha (`caixa+manual`), com o máximo dele; uma manual
     sem caixa é a sua linha; `add` substitui, não soma;
  5. **o saldo** nas duas taxas e por caixa;
  6. **a página** nos dois modos (partir/juntar, o índice sem os textos, a
     aba na fila, botões só no modo edição);
  7. **a CLI** e **o endpoint** `/api/feira` (403 sem token; 409 fora do
     catálogo). Nada disto toca na base.

Não toca na rede.
"""
import io
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
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "dedicado": True, "acabamento": "foil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "dedicado": True, "lingua": "en", "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "duel-commander", "nome": "Cloud (Duel Commander)",
         "formato": "duel-commander", "fonte": "deck", "ref": "Cloud (Duel Commander)",
         "balde": "Cloud", "estado": "permanente", "prioridade": 1, "notas": ""},
        {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
         "fonte": "deck", "ref": "Modern — UW Oswald", "balde": "SPML",
         "estado": "permanente", "prioridade": 2, "notas": ""},
    ],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import configio, db, feira, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# O `webapp._feira` regenera as páginas e escreve-as no `webapp.ROOT`, que é a
# raiz do repositório. Apontado aqui, no import, para nunca reescrever o
# `deckboxes.html` a sério.
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

# (nome, edição, data, reserved, preço nonfoil, preço foil)
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 0, 1.0, 5.0),
    ("Mother of Runes", "sld", "2022-01-01", 0, 2.0, 6.0),
    ("Path to Exile", "pf20", "2020-01-01", 0, 3.0, 9.0),
    ("Get Lost", "lci", "2023-11-17", 0, 4.0, 8.0),
    ("Winter Moon", "ltr", "2023-06-23", 0, 10.0, 20.0),
    ("City of Traitors", "exo", "1998-06-15", 1, 100.0, 100.0),
    ("Solitude", "mh2", "2021-06-18", 0, 30.0, 40.0),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, rl, p_n, p_f) in enumerate(CATALOGO):
        for lang in ("en", "pt"):
            con.execute(
                """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
                   set_code, set_name, collector_number, lang, rarity, type_line, cmc,
                   color_identity, finishes, released_at, legalities, digital, reserved)
                   VALUES (?,?,?,?,'S',?,?,'rare','Instant',1,?,?,?,?,0,?)""",
                (f"id-{i}-{lang}", f"or-{i}", nm, sc, str(i), lang,
                 "U" if nm == "Winter Moon" else "W",
                 json.dumps(["nonfoil", "foil"]), rel,
                 json.dumps({"legacy": "legal", "modern": "legal", "commander": "legal",
                             "duel": "legal"}), rl))
            for fin, preco in (("nonfoil", p_n), ("foil", p_f)):
                con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                            "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                            "'2026-09-19', ?)", (f"id-{i}-{lang}", fin, preco))
                # Histórico chão (sem subida) desde há 3 meses: a regra dos 5 %
                # da RL decide "não subiu" e a City of Traitors VAI à venda —
                # sem isto ficava em `rl_sem_historico`, fora da feira.
                for dia in ("2026-06-01", "2026-09-19"):
                    con.execute("INSERT OR REPLACE INTO price_history (scryfall_id, "
                                "source, date, finish, trend) VALUES (?, 'cardmarket', "
                                "?, ?, ?)", (f"id-{i}-{lang}", dia, fin, preco))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub="Colecção", validado=None):
    i = [c[0] for c in CATALOGO].index(nm)
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, 'player')",
                (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?", (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                   sub_collection_id, validado_em, photo_path)
                   VALUES (?,?,?,?,'player',?,?,?)""",
                (f"id-{i}-{lang}", q, finish, lang, sub_id, validado,
                 "fotos/x.jpg" if validado else None))
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


def cfg_novo(**feira_cfg):
    cfg = json.loads(json.dumps(CFG))
    if feira_cfg:
        cfg["feira"] = feira_cfg
    cfg_escrever(cfg)
    return cfg


def coleccao_tipo(con):
    """Uma colecção com excedente: 6 Get Lost foil (vende 2: 8 € cada), 5 City
    of Traitors RL nonfoil na Caixa RL (vende 1: 100 €), 6 Solitude nonfoil
    (vende 2 — o Modern quer foil, a nonfoil é substituto... só se o pedir).
    Os decks pedem o que não há: o Cloud 2 Mother of Runes, o Modern 2 Path."""
    deck(con, "Cloud (Duel Commander)", "duel-commander", [("Mother of Runes", 2)])
    deck(con, "Modern — UW Oswald", "modern", [("Path to Exile", 2)])
    add(con, "Get Lost", 4, finish="foil", validado="2026-09-20")
    add(con, "Get Lost", 2, finish="foil")                    # sem foto
    add(con, "City of Traitors", 5, finish="nonfoil", sub="Caixa Reserved List")
    return con


def linha(lv, nm):
    return next(l for l in lv["linhas"] if l["nm"] == nm)


# ---------------------------------------------------------------------------
def caso_as_taxas():
    """Omissão 0,55 / 0,70; `55` vale 0,55; fora de [0,1] é erro; o dinheiro e a
    troca de cada linha são Trend × taxa, e os totais somam."""
    cfg = cfg_novo()
    assert feira.taxas(cfg) == (0.55, 0.70)
    feira.definir_taxas(cfg, "60", "75")
    assert feira.taxas(cfg) == (0.60, 0.75), feira.taxas(cfg)
    feira.definir_taxas(cfg, 0.5, None)
    assert feira.taxas(cfg) == (0.50, 0.75)
    for mau in ("abc", "-1", "150"):
        try:
            feira.definir_taxas(cfg, mau, None)
            raise AssertionError(f"{mau!r} tinha de ser recusado")
        except ValueError as e:
            assert "taxa" in str(e), e
    cfg_escrever(cfg)
    con = coleccao_tipo(base())
    rep = loadout.report(con)
    assert rep["copias"] == 2 and rep["copias_rl"] == 1, (rep["copias"], rep["copias_rl"])
    lv = feira.levar(con, rep, cfg)
    assert lv["taxa_dinheiro"] == 0.5 and lv["taxa_troca"] == 0.75
    assert lv["revalidacao"] is False, "sem campanha, o filtro não corta"
    gl = linha(lv, "Get Lost")
    assert gl["q"] == 2 and gl["leva_q"] == 2 and gl["unit"] == 8.0, gl
    assert gl["trend"] == 16.0 and gl["dinheiro"] == 8.0 and gl["troca"] == 12.0, gl
    assert gl["chave"] == "Get Lost|LCI|en|foil", gl["chave"]
    ct = linha(lv, "City of Traitors")
    assert ct["rl"] is True and ct["local"] == "Caixa RL (EN)" and ct["trend"] == 100.0, ct
    assert lv["copias"] == 3 and lv["trend"] == 116.0
    assert lv["dinheiro"] == 58.0 and lv["troca"] == 87.0, (lv["dinheiro"], lv["troca"])
    assert lv["rl_copias"] == 1 and lv["rl_trend"] == 100.0
    print("as taxas: omissao, validacao, dinheiro e troca = Trend x taxa")


def caso_levo_nao_levo():
    """A marca vive no config, por impressão. Marcar tira a linha dos totais
    (fica à vista, `levo: false`, `leva_q: 0`); desmarcar repõe."""
    cfg = cfg_novo()
    con = coleccao_tipo(base())
    rep = loadout.report(con)
    lv = feira.levar(con, rep, cfg)
    assert lv["copias"] == 3 and lv["nao_levo"] == 0
    feira.marcar(cfg, "City of Traitors|EXO|en|nonfoil", levo=False)
    assert cfg["feira"]["nao_levo"] == ["City of Traitors|EXO|en|nonfoil"]
    cfg_escrever(cfg)
    lv = feira.levar(con, rep, cfg)
    ct = linha(lv, "City of Traitors")
    assert ct["levo"] is False and ct["leva_q"] == 0 and ct["trend"] == 0, ct
    assert ct["q"] == 1, "a linha continua à vista, com a quantidade real"
    assert lv["copias"] == 2 and lv["trend"] == 16.0 and lv["rl_copias"] == 0
    assert lv["nao_levo"] == 1 and lv["nao_levo_trend"] == 100.0
    assert "não levo" in feira.texto_levar(feira.projeccao(con, rep, cfg)), "o texto di-lo"
    assert "City of Traitors" not in feira.texto_levar(feira.projeccao(con, rep, cfg)).split("■")[1]
    feira.marcar(cfg, "City of Traitors|EXO|en|nonfoil", levo=True)
    assert "nao_levo" not in cfg["feira"], cfg["feira"]
    lv = feira.levar(con, rep, cfg)
    assert lv["copias"] == 3
    try:
        feira.marcar(cfg, "sem barras", False)
        raise AssertionError("chave inválida tinha de falhar")
    except ValueError:
        pass
    print("levo / nao levo: marca no config, fora dos totais, volta")


def caso_so_validadas():
    """Com a campanha ligada (`revalidacao.desde`) e o filtro por omissão, só
    as cópias com foto vão: dos 2 Get Lost a mais, a venda escolhe... e a
    feira leva só o que tem `validado_em`; o resto fica em `fora_foto`.
    Filtro a `false` → vai tudo. Sem campanha → vai tudo."""
    cfg = cfg_novo()
    cfg["revalidacao"] = {"desde": "2026-09-20"}
    cfg_escrever(cfg)
    con = base()
    deck(con, "Cloud (Duel Commander)", "duel-commander", [("Mother of Runes", 2)])
    add(con, "Get Lost", 4, finish="foil")                          # sem foto
    add(con, "Get Lost", 3, finish="foil", validado="2026-09-20")   # com foto
    rep = loadout.report(con)
    assert rep["copias"] == 3, rep["copias"]                        # 7 − 4
    lv = feira.levar(con, rep, cfg)
    assert lv["revalidacao"] is True and lv["so_validadas"] is True
    gl = linha(lv, "Get Lost")
    # A venda tira do lote em pior estado / mais antigo: o que importa aqui é
    # que só o que tem foto conta, e o resto fica dito.
    assert gl["q"] == 3 and gl["validadas"] + gl["por_revalidar"] == 3, gl
    assert gl["leva_q"] == gl["validadas"] and gl["fora_foto"] == gl["por_revalidar"]
    assert lv["copias"] == gl["validadas"] and lv["fora_foto"] == gl["por_revalidar"]
    assert lv["fora_foto_trend"] == round(8.0 * gl["por_revalidar"], 2)
    assert lv["copias"] + lv["fora_foto"] == 3
    feira.definir_so_validadas(cfg, False)
    cfg_escrever(cfg)
    lv = feira.levar(con, rep, cfg)
    assert lv["so_validadas"] is False and lv["copias"] == 3 and lv["fora_foto"] == 0
    # Sem campanha, o `so_validadas: true` não corta nada.
    cfg.pop("revalidacao")
    feira.definir_so_validadas(cfg, True)
    cfg_escrever(cfg)
    lv = feira.levar(con, rep, cfg)
    assert lv["revalidacao"] is False and lv["copias"] == 3 and lv["fora_foto"] == 0
    print("so validadas: com campanha so vai o que tem foto; o resto fica dito")


def caso_wantlist_manual_e_automatica_sem_duplicar():
    """O Cloud pede 2 Mother of Runes (foil) e o Modern 2 Path (foil EN): duas
    linhas automáticas. Uma manual «Mother of Runes» para o Cloud funde-se
    (uma linha, `caixa+manual`, q = max, máximo dele); uma manual sem caixa
    é a sua linha; `add` substitui; `remover` tira."""
    cfg = cfg_novo()
    con = coleccao_tipo(base())
    rep = loadout.report(con)
    tz = feira.trazer(con, rep, cfg)
    assert [(l["nm"], l["slot"], l["q"], l["origem"]) for l in tz["linhas"]] == [
        ("Mother of Runes", "duel-commander", 2, "caixa"),
        ("Path to Exile", "modern", 2, "caixa")], tz["linhas"]
    mr = tz["linhas"][0]
    assert mr["unit"] == 6.0 and mr["minimo"] == 12.0 and mr["maximo"] == 12.0, mr
    assert "foil" in mr["req"].lower(), mr["req"]
    assert tz["copias"] == 4 and tz["minimo"] == 12.0 + 18.0 and tz["com_maximo"] == 0
    # A manual para a MESMA caixa: funde-se.
    e = feira.wantlist_add(cfg, "Mother of Runes", 1, None, None, "4.50", "duel-commander",
                           "banca do fundo")
    assert e == {"nome": "Mother of Runes", "q": 1, "max": 4.5, "slot": "duel-commander",
                 "notas": "banca do fundo"}, e
    # Sem caixa: linha própria, ao preço nonfoil (é a omissão sem caixa).
    feira.wantlist_add(cfg, "Winter Moon", 3, "en", None, None, None, "")
    cfg_escrever(cfg)
    tz = feira.trazer(con, rep, cfg)
    assert len(tz["linhas"]) == 3, [(l["nm"], l["slot"]) for l in tz["linhas"]]
    mr = next(l for l in tz["linhas"] if l["nm"] == "Mother of Runes")
    assert mr["origem"] == "caixa+manual" and mr["q"] == 2 and mr["manual_q"] == 1, mr
    assert mr["max"] == 4.5 and mr["maximo"] == 9.0 and mr["minimo"] == 12.0, mr
    assert mr["notas"] == "banca do fundo"
    wm = next(l for l in tz["linhas"] if l["nm"] == "Winter Moon")
    assert wm["origem"] == "manual" and wm["caixa"] == "Colecção" and wm["q"] == 3, wm
    assert wm["unit"] == 10.0 and wm["mat"] == "EN", wm
    assert tz["copias"] == 7 and tz["minimo"] == 12.0 + 18.0 + 30.0
    assert tz["maximo"] == 9.0 + 18.0 + 30.0 and tz["com_maximo"] == 1
    assert tz["manuais"] == 2
    caixas = [(c["caixa"], c["copias"], c["minimo"]) for c in tz["por_caixa"]]
    assert caixas == [("Cloud (Duel Commander)", 2, 12.0), ("Modern — UW Oswald", 2, 18.0),
                      ("Colecção", 3, 30.0)], caixas
    # `add` da mesma (carta, caixa) SUBSTITUI: 2 não vira 3.
    feira.wantlist_add(cfg, "Winter Moon", 2, "en", None, None, None, "")
    assert [e["q"] for e in feira.wantlist(cfg) if e["nome"] == "Winter Moon"] == [2]
    # Uma manual com caixa e a mesma carta sem caixa são duas entradas.
    feira.wantlist_add(cfg, "Winter Moon", 1, None, None, None, "modern", "")
    assert len(feira.wantlist(cfg)) == 3
    assert feira.wantlist_remover(cfg, "Winter Moon", "modern") == 2
    try:
        feira.wantlist_remover(cfg, "Winter Moon", "modern")
        raise AssertionError("remover o que não está tinha de falhar")
    except ValueError:
        pass
    for maus in (("Mother of Runes", 0), ):
        try:
            feira.wantlist_add(cfg, *maus)
            raise AssertionError("quantidade 0 tinha de falhar")
        except ValueError:
            pass
    try:
        feira.wantlist_add(cfg, "Get Lost", 1, "fr")
        raise AssertionError("língua fr tinha de falhar")
    except ValueError:
        pass
    try:
        feira.wantlist_add(cfg, "Get Lost", 1, None, None, None, "nao-existe")
        raise AssertionError("caixa inexistente tinha de falhar")
    except KeyError:
        pass
    # Vendors e «pode ter».
    feira.vendor_add(cfg, "Banca A", "bons preços", "bancaA", "")
    try:
        feira.pode_ter(cfg, "Mother of Runes", "Banca B")
        raise AssertionError("vendor desconhecido tinha de falhar")
    except ValueError:
        pass
    assert feira.pode_ter(cfg, "Mother of Runes", "Banca A") == ["Banca A"]
    cfg_escrever(cfg)
    tz = feira.trazer(con, rep, cfg)
    assert next(l for l in tz["linhas"] if l["nm"] == "Mother of Runes")["vendors"] == ["Banca A"]
    assert tz["vendors"][0]["nome"] == "Banca A" and tz["vendors"][0]["cardmarket"] == "bancaA"
    assert feira.pode_ter(cfg, "mother of runes", "Banca A", sim=False) == []
    assert "pode_ter" not in cfg["feira"]
    feira.pode_ter(cfg, "Path to Exile", "Banca A")
    feira.vendor_remover(cfg, "Banca A")
    assert "vendors" not in cfg["feira"] and "pode_ter" not in cfg["feira"], cfg["feira"]
    print("wantlist manual + automatica sem duplicar; vendors e pode-ter")


def caso_o_saldo():
    """Levar 3 cópias / Trend 116 € (dinheiro 63,80 · troca 81,20); trazer
    mínimo 30 € → saldo dinheiro +33,80, troca +51,20; com um máximo de 4,50
    na Mother, trazer máximo 27 €. E por caixa."""
    cfg = cfg_novo()
    feira.wantlist_add(cfg, "Mother of Runes", 2, None, None, 4.5, "duel-commander", "")
    cfg_escrever(cfg)
    con = coleccao_tipo(base())
    rep = loadout.report(con)
    p = feira.projeccao(con, rep, cfg, hoje="2026-09-20")
    assert p["levar"]["trend"] == 116.0 and p["levar"]["dinheiro"] == 63.8
    assert p["levar"]["troca"] == 81.2, p["levar"]["troca"]
    assert p["trazer"]["minimo"] == 30.0 and p["trazer"]["maximo"] == 27.0
    s = p["saldo"]
    assert s == {"dinheiro": 33.8, "troca": 51.2, "dinheiro_max": 36.8, "troca_max": 54.2,
                 "trend": 86.0}, s
    pc = {c["caixa"]: c for c in p["por_caixa"]}
    assert pc["Cloud (Duel Commander)"]["saldo_troca"] == round(81.2 - 12.0, 2)
    assert pc["Modern — UW Oswald"]["saldo_dinheiro"] == round(63.8 - 18.0, 2)
    assert pc["Cloud (Duel Commander)"]["pct_da_troca"] == round(100 * 12.0 / 81.2, 1)
    assert "saldo dinheiro +33.80 €" in feira.resumo(p) and "troca +51.20 €" in feira.resumo(p)
    assert "FEIRA — LEVAR (2026-09-20)" in p["texto_levar"]
    assert "2× Get Lost · LCI EN foil NM · 8.00 €/un · Colecção" in p["texto_levar"], p["texto_levar"]
    assert "1× City of Traitors (RL) · EXO EN nonfoil NM · 100.00 €/un · Caixa RL (EN)" in p["texto_levar"]
    assert "■ Cloud (Duel Commander) — 2 cópias · 12.00 €" in p["texto_trazer"], p["texto_trazer"]
    # O Duel Commander não exige língua: o material é só «foil» (o Modern é EN foil).
    assert "2× Mother of Runes [foil] · 6.00 €/un · máx 4.50 €" in p["texto_trazer"], p["texto_trazer"]
    assert "2× Path to Exile [EN foil] · 9.00 €/un" in p["texto_trazer"]
    assert p["texto_cardmarket"] == ("// Cloud (Duel Commander)\n2 Mother of Runes\n"
                                     "// Modern — UW Oswald\n2 Path to Exile"), p["texto_cardmarket"]
    # A alocação e a venda NÃO mexem com a feira: os números do relatório são
    # os mesmos com e sem o bloco `feira` no config.
    cfg_novo()
    rep2 = loadout.report(con)
    assert (rep2["custo_total"], rep2["comprar_total"], rep2["copias"], rep2["total"]) == \
        (rep["custo_total"], rep["comprar_total"], rep["copias"], rep["total"])
    print("o saldo nas duas taxas, por caixa, e os textos")


def caso_a_pagina_nos_dois_modos():
    """O payload leva `feira`; `partir`/`juntar` são inversos e o índice fica sem
    os textos; a fila tem «🎒 Feira»; o JS desenha Levar/Trazer/Vendors; os
    botões (`data-feira`) só no modo edição."""
    cfg = cfg_novo()
    feira.wantlist_add(cfg, "Winter Moon", 1, "en", "nonfoil", 7, None, "se houver")
    feira.vendor_add(cfg, "Banca A", "", "bancaA", "")
    feira.pode_ter(cfg, "Mother of Runes", "Banca A")
    cfg_escrever(cfg)
    con = coleccao_tipo(base())
    rep = loadout.report(con)
    for editable in (False, True):
        d = deckboxes.payload(con, rep, editable=editable)
        F = d["feira"]
        assert F["saldo"]["troca"] == round(81.2 - 40.0, 2), F["saldo"]
        idx, partes = deckboxes.partir(d)
        assert "texto_levar" not in idx["feira"] and "linhas" not in idx["feira"]["levar"]
        assert idx["feira"]["saldo"]["troca"] == F["saldo"]["troca"]
        assert "texto_levar" in partes["feira"] and partes["feira"]["levar"]["linhas"]
        assert deckboxes.juntar(idx, partes) == d
        html = deckboxes.html_page(con, editable=editable, rep=rep)
        assert "vistaFeira" in html and "feiraAccao" in html
        pagina = _TMP / f"dx-{int(editable)}.html"
        pagina.write_text(html, encoding="utf-8")
        if not shutil.which("node"):
            print("  (sem node: o render não foi verificado)")
            continue
        dump = _TMP / f"abas-{int(editable)}.json"
        p = subprocess.run(["node", str(RAIZ / "tests" / "render_deckboxes.js"),
                            str(pagina), str(dump)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
        abas = json.loads(dump.read_text(encoding="utf-8"))
        # Desde a 2.ª passagem de 2026-09-24 a Feira entra pela BARRA LATERAL do
        # site (o índice interno ficou só com as caixas) e o saldo em troca é o
        # subtítulo do título da vista, não da fila.
        assert 'href="deckboxes.html#feira"' in html, "a barra perdeu a Feira"
        aba = abas["feira"]
        assert "troca +" in aba, aba[:600]
        for txt in ("1. Levar", "2. Trazer", "3. Vendors", "4. Por caixa", "Get Lost",
                    "City of Traitors", "Mother of Runes", "Winter Moon", "Banca A pode ter",
                    "estimativas tuas", "55 %", "70 %", "se houver", "Cloud (Duel Commander)"):
            assert txt in aba, (txt, aba[:1500])
        assert ("data-feira=" in aba) is editable, "botões só no modo edição"
        assert ("feira-vend" in aba) is editable
        assert " blocos de escrita (editavel=" in p.stdout, p.stdout
        # O `partir` escreve a parte no disco como as outras.
        out = _TMP / f"site-{int(editable)}" / "deckboxes.html"
        out.parent.mkdir(exist_ok=True)
        deckboxes.build(con, out, editable=editable, rep=rep)
        assert (out.parent / "data" / "paginas" / "deckboxes" / "feira.json").exists()
    print("a pagina nos dois modos: partes, fila, botoes so no modo edicao")


def caso_a_cli():
    cfg_novo()
    con = coleccao_tipo(base())
    con.commit()
    dbp = con.execute("PRAGMA database_list").fetchall()
    vault = next(r["file"] for r in dbp if r["name"] == "main")
    cat = next(r["file"] for r in dbp if r["name"] == "catalog")
    env = dict(os.environ, MTGVAULT_DB=vault, MTGVAULT_CATALOG=cat,
               MTGVAULT_CONFIG=str(CFG_PATH), PYTHONIOENCODING="utf-8")

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "mtgvault.cli", *args], cwd=RAIZ,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env)

    p = cli("feira")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "levar 3c / Trend 116.00 €" in p.stdout and "trazer 4c / 30.00 €" in p.stdout, p.stdout
    assert "saldo dinheiro +33.80 €" in p.stdout and "FEIRA — LEVAR" in p.stdout, p.stdout
    p = cli("feira", "--json")
    j = json.loads(p.stdout)
    assert j["saldo"]["troca"] == 51.2 and len(j["trazer"]["linhas"]) == 2, j["saldo"]
    p = cli("feira", "wantlist", "add", "Carta Que Nao Ha")
    assert p.returncode == 2 and "catálogo" in p.stdout, p.stdout
    p = cli("feira", "wantlist", "add", "winter moon", "--qty", "3", "--lang", "en",
            "--max", "7.5", "--notas", "se houver")
    assert p.returncode == 0 and "3× Winter Moon" in p.stdout, p.stdout + p.stderr
    assert cfg_ler()["feira"]["wantlist"] == [{"nome": "Winter Moon", "q": 3, "lang": "en",
                                              "max": 7.5, "notas": "se houver"}]
    p = cli("feira", "wantlist", "add", "Mother of Runes", "--caixa", "duel-commander", "--max", "4")
    assert p.returncode == 0, p.stdout + p.stderr
    p = cli("feira", "wantlist", "add", "Mother of Runes", "--caixa", "nao-existe")
    assert p.returncode == 2 and "não existe" in p.stdout, p.stdout
    p = cli("feira", "wantlist", "listar")
    assert "3× Winter Moon" in p.stdout and "para Cloud (Duel Commander)" in p.stdout, p.stdout
    p = cli("feira", "vendor", "add", "Banca A", "--cardmarket", "bancaA")
    assert p.returncode == 0, p.stdout + p.stderr
    p = cli("feira", "pode-ter", "Mother of Runes", "Banca A")
    assert p.returncode == 0 and "Banca A pode ter" in p.stdout, p.stdout
    p = cli("feira", "taxas", "--dinheiro", "60")
    assert p.returncode == 0 and "dinheiro 60%" in p.stdout, p.stdout
    p = cli("feira", "nao-levo", "City of Traitors|EXO|en|nonfoil")
    assert p.returncode == 0, p.stdout + p.stderr
    p = cli("feira")
    assert "levar 2c / Trend 16.00 €" in p.stdout and "dinheiro 9.60 € @ 60%" in p.stdout, p.stdout
    assert "Banca A pode ter" in p.stdout and "máx 4.00 €" in p.stdout, p.stdout
    assert "trazer 7c / 60.00 € (máx 48.50 €)" in p.stdout, p.stdout
    p = cli("feira", "levo", "City of Traitors|EXO|en|nonfoil")
    assert p.returncode == 0 and "nao_levo" not in cfg_ler()["feira"]
    p = cli("feira", "wantlist", "remover", "Winter Moon")
    assert p.returncode == 0, p.stdout + p.stderr
    p = cli("feira", "vendor", "remover", "Banca A")
    assert p.returncode == 0 and "pode_ter" not in cfg_ler()["feira"], p.stdout
    p = cli("feira", "vendor", "listar")
    assert "0 vendor" in p.stdout, p.stdout
    print("a CLI: projeccao, --json, wantlist, vendor, pode-ter, taxas, levo")


class Pedido(webapp.Handler):
    """Um pedido de mentira: o mesmo handler, sem rede por baixo."""

    def __init__(self, path, corpo=None, ip="127.0.0.1"):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO((corpo or "").encode("utf-8"))
        self.headers = {"Content-Length": str(len(corpo or ""))}
        self.codigo, self.corpo = None, ""

    def send_response(self, code, *_a):
        self.codigo = code

    def send_header(self, *_a):
        pass

    def end_headers(self):
        pass

    @property
    def wfile(self):
        self_ = self

        class Escritor:
            def write(self, b):
                self_.corpo = b.decode("utf-8", "replace")
        return Escritor()


def _post(dados, ip="127.0.0.1"):
    p = Pedido("/api/feira", json.dumps(dados), ip=ip)
    p.do_POST()
    return p.codigo, (json.loads(p.corpo) if p.corpo.startswith("{") else p.corpo)


def caso_o_endpoint_do_8771():
    """`POST /api/feira`: taxas, filtro, levo/nao-levo, wl-add (409 fora do
    catálogo / caixa inexistente), max, wl-tirar, vendor-add/tirar, pode-ter —
    e sem token (rede) é 403 e não escreve."""
    cfg_novo()
    con = coleccao_tipo(base())
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(next(r["file"] for r in dbs if r["name"] == "main"))
    db.DEFAULT_CATALOG = Path(next(r["file"] for r in dbs if r["name"] == "catalog"))
    webapp.CONFIG = CFG_PATH
    cod, j = _post({"act": "taxas", "dinheiro": "60", "troca": "80"}, ip="192.168.1.9")
    assert cod == 403 and "feira" not in cfg_ler(), (cod, j)
    cod, j = _post({"act": "taxas", "dinheiro": "60", "troca": "80"})
    assert cod == 200 and "dinheiro 60%" in j["msg"], (cod, j)
    assert cfg_ler()["feira"] == {"taxa_dinheiro": 0.6, "taxa_troca": 0.8}
    cod, j = _post({"act": "taxas", "dinheiro": "abc"})
    assert cod == 409 and "taxa" in j["erro"], (cod, j)
    cod, j = _post({"act": "filtro", "so_validadas": False})
    assert cod == 200 and cfg_ler()["feira"]["so_validadas"] is False, (cod, j)
    cod, j = _post({"act": "nao-levo", "chave": "Get Lost|LCI|en|foil"})
    assert cod == 200 and cfg_ler()["feira"]["nao_levo"] == ["Get Lost|LCI|en|foil"], (cod, j)
    cod, j = _post({"act": "levo", "chave": "Get Lost|LCI|en|foil"})
    assert cod == 200 and "nao_levo" not in cfg_ler()["feira"], (cod, j)
    cod, j = _post({"act": "wl-add", "nome": "Carta Que Nao Ha", "q": 1})
    assert cod == 409 and "catálogo" in j["erro"], (cod, j)
    cod, j = _post({"act": "wl-add", "nome": "winter moon", "q": 2, "slot": "nao-existe"})
    assert cod == 409 and "já não existe" in j["erro"], (cod, j)
    cod, j = _post({"act": "wl-add", "nome": "winter moon", "q": 2, "lang": "en",
                    "max": "7", "notas": "x"})
    assert cod == 200 and "2× Winter Moon" in j["msg"], (cod, j)
    assert cfg_ler()["feira"]["wantlist"] == [{"nome": "Winter Moon", "q": 2, "lang": "en",
                                              "max": 7.0, "notas": "x"}]
    # «máx €» numa linha automática cria a entrada manual dessa caixa.
    cod, j = _post({"act": "max", "nome": "Mother of Runes", "slot": "duel-commander",
                    "q": 2, "max": "4.5"})
    assert cod == 200 and "máx 4.50" in j["msg"], (cod, j)
    wl = cfg_ler()["feira"]["wantlist"]
    assert {"nome": "Mother of Runes", "q": 2, "max": 4.5, "slot": "duel-commander"} in wl, wl
    # Tirar o máximo deixa a entrada sem `max`.
    cod, j = _post({"act": "max", "nome": "Mother of Runes", "slot": "duel-commander", "max": ""})
    assert cod == 200 and "tirado" in j["msg"], (cod, j)
    assert {"nome": "Mother of Runes", "q": 2, "slot": "duel-commander"} in cfg_ler()["feira"]["wantlist"]
    cod, j = _post({"act": "wl-tirar", "nome": "Mother of Runes", "slot": "duel-commander"})
    assert cod == 200 and len(cfg_ler()["feira"]["wantlist"]) == 1, (cod, j)
    cod, j = _post({"act": "vendor-add", "nome": "Banca A", "cardmarket": "bancaA"})
    assert cod == 200 and cfg_ler()["feira"]["vendors"] == [{"nome": "Banca A", "cardmarket": "bancaA"}], (cod, j)
    cod, j = _post({"act": "pode-ter", "nome": "Winter Moon", "vendor": "Banca A"})
    assert cod == 200 and cfg_ler()["feira"]["pode_ter"] == {"Winter Moon": ["Banca A"]}, (cod, j)
    cod, j = _post({"act": "pode-ter", "nome": "Winter Moon", "vendor": "Banca Z"})
    assert cod == 409 and "vendors" in j["erro"], (cod, j)
    cod, j = _post({"act": "pode-ter-nao", "nome": "Winter Moon", "vendor": "Banca A"})
    assert cod == 200 and "pode_ter" not in cfg_ler()["feira"], (cod, j)
    cod, j = _post({"act": "vendor-tirar", "vendor": "Banca A"})
    assert cod == 200 and "vendors" not in cfg_ler()["feira"], (cod, j)
    cod, j = _post({"act": "outra"})
    assert cod == 200 and "desconhecida" in j["erro"], (cod, j)
    # As páginas regeneraram-se no ROOT de teste, nunca no repositório.
    assert (webapp.ROOT / "deckboxes.html").exists()
    assert (webapp.ROOT / "data" / "paginas" / "deckboxes" / "feira.json").exists()
    print("o endpoint /api/feira escreve, valida e recusa sem token")


def run():
    for fn in (caso_as_taxas, caso_levo_nao_levo, caso_so_validadas,
               caso_wantlist_manual_e_automatica_sem_duplicar, caso_o_saldo,
               caso_a_pagina_nos_dois_modos, caso_a_cli, caso_o_endpoint_do_8771):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
