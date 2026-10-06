"""SEMPRE MONTADOS, MESMO COM PROXIES, E O STIFLENOUGHT VOLTA AO LUFFY
(André, 2026-10-05, à letra).

    *"no Premodern, o Stiflenought e lista do Luffy tambem, o UW Replenish e que
      e para procurar"*
    *"Esses sao os meus decks principais, esses quero ter sempre montados, mesmo
      que com proxies"*

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_sempre_montado.py`, que desliga uma peça de cada vez e exige
vermelho:

  1. a caixa do Stiflenought SERVE a lista do Luffy e SEGUE o jogador;
  2. a lista do Simone Fierro está no HISTÓRICO e não se perdeu;
  3. num deck `sempre_montado` os proxies são TODAS as faltas e não só as
     partilhadas;
  4. dois decks que pedem a mesma carta: um leva as verdadeiras e o outro leva
     proxies, e a página diz QUAL;
  5. a marca `principal` é EDITÁVEL e as caixas a 0 % não a têm;
  6. uma básica da PILHA nunca é proxy — e uma Snow-Covered continua a ser falta;
  7. desmarcar devolve o formato ao `cartas_partilhadas` do grupo (as duas
     direcções), e nem a chave nem o código das partilhadas se apagaram;
  8. `sempre_montado` escrito à mão GANHA ao `principal`;
  9. a ordem das verdadeiras é a `prioridade` e é DETERMINISTA;
 10. as duas metades (verdadeiras + proxies) somam SEMPRE o total do deck.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

#: Três caixas de Premodern (o grupo é `rotativas` no config, como o dele) e duas
#: de cEDH (`dedicadas`). É o mínimo para o eixo novo se ver a GANHAR ao modo do
#: formato num lado e a não mudar nada no outro.
CAIXAS = [
    {"slot": "pm-a", "nome": "Enchantress", "formato": "premodern",
     "fonte": "deck", "ref": "EN", "balde": "Colecção", "estado": "permanente",
     "prioridade": 1},
    {"slot": "pm-b", "nome": "Oath", "formato": "premodern", "fonte": "deck",
     "ref": "OA", "balde": "Colecção", "estado": "permanente", "prioridade": 2},
    {"slot": "pm-c", "nome": "Stiflenought", "formato": "premodern",
     "fonte": "vigiado", "ref": "Luffy — Premodern", "balde": "Colecção",
     "estado": "montada", "prioridade": 3},
    {"slot": "cedh-a", "nome": "Blue Farm", "formato": "cedh", "fonte": "deck",
     "ref": "BF", "balde": "Colecção", "estado": "montada", "prioridade": 4},
    # Uma caixa a 0 %: `fonte: consenso` SEM assinatura é o gesto do «já não vou
    # montar este» (desactivada). Nunca pode ficar `principal`.
    {"slot": "zero", "nome": "Sem lista", "formato": "legacy",
     "fonte": "consenso", "balde": "Colecção", "estado": "candidata",
     "prioridade": 9},
]
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
        {"grupo": "cedh", "formatos": ["cedh"], "dedicado": True,
         "cartas_partilhadas": "dedicadas"},
        {"grupo": "spml", "formatos": ["legacy"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 30},
    "decks_montar": {},
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(**mudancas):
    from mtgvault import sources                             # noqa: PLC0415
    d = json.loads(json.dumps(CFG))
    for k, v in mudancas.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    return d


def principais(cfg, *slots, **extra):
    """Marca as caixas dadas como `principal` no config do teste."""
    for c in cfg["caixas"]:
        if c["slot"] in slots:
            c["principal"] = True
            c.update(extra.get(c["slot"], {}))
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    from mtgvault import sources                             # noqa: PLC0415
    sources.esquecer_config()
    return cfg


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, db, decks_vista as dv,  # noqa: E402
                      loadout, marcas, sources)

#: (nome, edição, data, preço, type_line)
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.50, "Instant"),
    ("Wrath of God", "4ed", "1995-04-01", 15.0, "Sorcery"),
    ("Enlightened Tutor", "mir", "1996-10-08", 20.0, "Instant"),
    ("Wasteland", "tmp", "1997-10-14", 80.0, "Land"),
    ("Mox Diamond", "sth", "1998-03-02", 500.0, "Artifact"),
    ("Phyrexian Dreadnought", "mir", "1996-10-08", 60.0,
     "Artifact Creature — Dreadnought"),
    ("Stifle", "scg", "2003-05-26", 20.0, "Instant"),
    ("Island", "4ed", "1995-04-01", 0.2, "Basic Land — Island"),
    ("Snow-Covered Plains", "ice", "1995-06-01", 7.0, "Basic Snow Land — Plains"),
]
_ABERTAS = []

#: `ref -> [(board, nome, qty)]`. A Enchantress e o Oath pedem 4 Swords CADA (é
#: a carta disputada); o Stiflenought vem do VIGIADO e tem Island (a pilha).
LISTAS = {
    "EN": [("main", "Swords to Plowshares", 4), ("main", "Wrath of God", 2),
           ("side", "Enlightened Tutor", 3)],
    "OA": [("main", "Swords to Plowshares", 4), ("main", "Wasteland", 2)],
    "BF": [("main", "Mox Diamond", 1), ("main", "Wasteland", 1)],
}
#: A lista do Luffy, como a vigia a guarda (o `watched_snapshots.cards`).
LISTA_LUFFY = [["main", "Phyrexian Dreadnought", 4], ["main", "Stifle", 4],
               ["main", "Island", 10], ["side", "Enlightened Tutor", 2]]


def base():
    """Uma base nova com o catálogo mínimo, os decks e a vigia do Luffy."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-04', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    for ref, cards in LISTAS.items():
        fmt = "cedh" if ref == "BF" else "premodern"
        con.execute("INSERT INTO decks (name, format) VALUES (?, ?)", (ref, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?",
                          (ref,)).fetchone()["id"]
        for board, nm, q in cards:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,?)", (did, nm, q, board))
    # A VIGIA DO LUFFY: a caixa do Stiflenought lê a lista daqui (`fonte:
    # vigiado`), que é o que a faz acompanhar sozinha quando ele a mudar.
    con.execute("INSERT INTO watched (kind, key, format, label, last_checked) "
                "VALUES ('mtgo_player','LuffyDoChapeuDePalha','premodern',"
                "'Luffy — Premodern','2026-10-05')")
    wid = con.execute("SELECT id FROM watched WHERE label = 'Luffy — Premodern'"
                      ).fetchone()["id"]
    con.execute("INSERT INTO watched_snapshots (watched_id, taken_at, list_hash, "
                "cards) VALUES (?, '2026-10-03', 'h1', ?)",
                (wid, json.dumps(LISTA_LUFFY)))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção")
    con.commit()
    return cid


def fmt_de(rep, nome):
    return next(f for f in rep["formatos"] if f["formato"] == nome)


def linha_de(f, deck_id):
    return next(d for d in f["decks"] if d["id"] == deck_id)


# ===========================================================================
# 1. A CAIXA DO STIFLENOUGHT SERVE A LISTA DO LUFFY E SEGUE O JOGADOR
# ===========================================================================
def caso_o_stiflenought_serve_a_lista_do_luffy_e_segue_o_jogador():
    """*"no Premodern, o Stiflenought e lista do Luffy tambem"*.

    A ordem `mtg-listas-de-eventos` de 04/10 trocou-a pela do Simone Fierro
    porque a regra manda preferir presenciais com campo grande. Estava errado: o
    Stiflenought dele vem do jogador que ele SEGUE.

    `fonte: vigiado` é o que faz a caixa acompanhar sozinha — o mesmo caminho do
    pauper. E a NOTA tem de dizer de quando é a lista e quando foi conferida: ele
    vai sleevar a partir disto.
    """
    escreve_cfg()
    con = base()
    cfg = sources.config()
    caixa = next(c for c in cfg["caixas"] if c["slot"] == "pm-c")
    assert caixa["fonte"] == "vigiado", caixa["fonte"]
    assert caixa["ref"] == "Luffy — Premodern", caixa["ref"]

    decks = {d["id"]: d for d in dv.decks_das_caixas(con, cfg)}
    d = decks["caixa:pm-c"]
    cartas = {(b, nm): q for b, nm, q in d["cards"]}
    assert cartas == {("main", "Phyrexian Dreadnought"): 4,
                      ("main", "Stifle"): 4, ("main", "Island"): 10,
                      ("side", "Enlightened Tutor"): 2}, cartas
    # A nota diz as DUAS datas (a da lista e a da conferência) — uma lista
    # conferida hoje não pode parecer informação de há um mês.
    assert "2026-10-03" in d["nota"], d["nota"]
    assert "2026-10-05" in d["nota"], d["nota"]
    # E a carta-assinatura do Stiflenought está na lista: é a prova de que a
    # lista é mesmo deste deck e não de outro.
    assert ("main", "Phyrexian Dreadnought") in cartas


def caso_a_lista_do_fierro_esta_no_historico():
    """*"A lista do Simone Fierro NAO SE APAGA: fica no historico"*.

    Vive em `listas_escolhidas._premodern-stiflenought-anterior` e **não** na
    chave do slot: com o registo no lugar do slot, o `_com_proveniencia` punha a
    ficha do Fierro (*"1.º de 218 jogadores"*) por cima das cartas do Luffy — a
    página a mentir sobre a lista por que ele vai sleevar, que é o pior resultado
    possível. Uma chave com `_` nunca é um `ref` de caixa.
    """
    cfg_real = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    le = cfg_real.get("listas_escolhidas") or {}
    assert "premodern-stiflenought" not in le, \
        "a chave do slot tem de sair, senão a ficha de proveniência mente"
    hist = le.get("_premodern-stiflenought-anterior")
    assert hist, "a lista do Fierro não se apaga"
    assert hist.get("cards"), "o histórico guarda as CARTAS"
    assert (hist.get("evento") or {}).get("jogador") == "Simone Fierro", hist.get("evento")
    assert hist.get("_substituida_em") == "2026-10-05", hist.get("_substituida_em")
    assert hist.get("_razao"), "a troca tem de dizer a RAZÃO"
    # E a caixa a sério tem de estar a seguir o Luffy.
    caixa = next(c for c in cfg_real["caixas"]
                 if c["slot"] == "premodern-stiflenought")
    assert caixa["fonte"] == "vigiado", caixa
    assert caixa["ref"] == "Luffy — Premodern", caixa
    assert caixa.get("_antes_1004"), "o estado que se substituiu fica registado"


# ===========================================================================
# 3. OS PROXIES DE UM DECK SEMPRE MONTADO SÃO TODAS AS FALTAS
# ===========================================================================
def caso_num_deck_sempre_montado_os_proxies_sao_todas_as_faltas():
    """*"o numero de PROXIES por deck deixa de ser «as partilhadas» e passa a ser
    TUDO O QUE FALTA"*.

    A Enchantress pede 4 Swords (partilhada com o Oath), 2 Wrath (PRÓPRIA) e 3
    Enlightened Tutor (própria). Sem nenhuma cópia na colecção:

      - pelo modelo de 04/10 os proxies eram **1 carta** (só as Swords);
      - sempre montado são **3 cartas / 9 cópias** (tudo o que falta).

    E a lista de proxies É a lista de faltas, carta a carta.
    """
    cfg = escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    assert esc == [], "sem marcas e sem principais, não há escolhidos"

    # (a) o modelo de 04/10: marca-se à mão, os proxies são as partilhadas.
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-05",
                              "caixa:pm-b": "2026-10-05"})
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["modo"] == dv.ROTATIVAS, f["modo"]
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    px_antes = dv.proxies_do_deck(rep["decks"]["caixa:pm-a"],
                                  dv.reparticao(esc))
    assert [x["nm"] for x in px_antes] == ["Swords to Plowshares"], px_antes

    # (b) sempre montado: os proxies passam a ser TODAS as faltas.
    cfg = escreve_cfg(decks_montar={})
    principais(cfg, "pm-a", "pm-b")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["n_sempre"] == 2, f["n_sempre"]
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    repartido = dv.reparte_verdadeiras(esc, rep["pos"])
    px = dv.proxies_do_deck(rep["decks"]["caixa:pm-a"], {}, repartido)
    assert {x["nm"]: x["q"] for x in px} == {
        "Swords to Plowshares": 4, "Wrath of God": 2,
        "Enlightened Tutor": 3}, px
    assert len(px) == 3 and sum(x["q"] for x in px) == 9, px
    # ... e é EXACTAMENTE a lista de faltas desse deck.
    nec = dv.necessidade([rep["decks"]["caixa:pm-a"]], rep["pos"])
    faltas = dv.faltas(nec, rep["pos"], dv.DEDICADAS)
    assert {x["nm"]: x["q"] for x in px} == faltas, (px, faltas)


def caso_um_deck_a_60_por_cento_leva_os_proxies_de_tudo_o_que_falta():
    """*"Um deck a 60% leva 30 proxies, nao 8"*: com cópias a sério na colecção, o
    número de proxies é a diferença e não o número de partilhadas."""
    cfg = escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4)
    copia(con, "Wrath of God", "4ed", q=1)
    principais(cfg, "pm-a")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    repartido = dv.reparte_verdadeiras(esc, rep["pos"])
    px = dv.proxies_do_deck(rep["decks"]["caixa:pm-a"], {}, repartido)
    # Tem as 4 Swords e 1 Wrath: faltam 1 Wrath e 3 Enlightened Tutor.
    assert {x["nm"]: x["q"] for x in px} == {"Wrath of God": 1,
                                            "Enlightened Tutor": 3}, px
    c = dv.conta_do_deck(rep["decks"]["caixa:pm-a"], rep["pos"])
    assert c["tem"] == 5 and c["total"] == 9, c


# ===========================================================================
# 4. QUEM FICA COM AS VERDADEIRAS, E QUEM LEVA PROXY
# ===========================================================================
def caso_dois_decks_a_pedir_a_mesma_carta_um_leva_as_verdadeiras():
    """*"se dois decks pedem 4 Swords e ele tem 4, um leva as verdadeiras e o
    outro leva 4 proxies. Mostra isso, e mostra QUAL deck fica com as
    verdadeiras"*.

    A ordem é a `prioridade` da caixa (critério dele). A Enchantress é a 1 e o
    Oath a 2: as 4 verdadeiras vão para a Enchantress.
    """
    cfg = escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4)
    principais(cfg, "pm-a", "pm-b")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    r = dv.reparte_verdadeiras(esc, rep["pos"])
    assert r["caixa:pm-a"]["Swords to Plowshares"] == {
        "q": 4, "verdadeiras": 4, "proxies": 0, "pilha": False}
    assert r["caixa:pm-b"]["Swords to Plowshares"] == {
        "q": 4, "verdadeiras": 0, "proxies": 4, "pilha": False}

    # E a PÁGINA diz qual é qual: é isso o `disputadas`.
    disp = f["disputadas"]
    sw = next(x for x in disp if x["nm"] == "Swords to Plowshares")
    assert sw["n_decks"] == 2 and sw["pede"] == 8, sw
    assert sw["verdadeiras"] == 4 and sw["proxies"] == 4, sw
    # O que leva as verdadeiras vem à frente, com nome: é o que ele lê.
    assert sw["decks"][0]["nome"] == "Enchantress", sw["decks"]
    assert sw["decks"][0]["verdadeiras"] == 4, sw["decks"][0]
    assert sw["decks"][1]["nome"] == "Oath", sw["decks"]
    assert sw["decks"][1]["proxies"] == 4, sw["decks"][1]

    # ... e o tile do deck que leva proxy di-lo, com a QUANTIDADE.
    pag = dv.deck_para_pagina(con, rep["decks"]["caixa:pm-b"], rep["pos"],
                              f["modo"], {}, repartido=r)
    cartas = {c["nm"]: c for g in pag["main"] for c in g["cartas"]}
    assert cartas["Swords to Plowshares"]["em_proxy"] is True
    assert cartas["Swords to Plowshares"]["proxies"] == 4
    pag_a = dv.deck_para_pagina(con, rep["decks"]["caixa:pm-a"], rep["pos"],
                                f["modo"], {}, repartido=r)
    cartas_a = {c["nm"]: c for g in pag_a["main"] for c in g["cartas"]}
    assert cartas_a["Swords to Plowshares"]["em_proxy"] is False


def caso_a_ordem_das_verdadeiras_e_a_prioridade_e_e_determinista():
    """A ordem é a `prioridade` da caixa — a que ele já escreveu no config — e
    nunca a ordem em que os decks saem do registo.

    Determinista de propósito: a lista de proxies que ele imprime não pode trocar
    de deck de um dia para o outro sem nada ter mudado (é a lição do desempate
    alfabético dos nomes, 2026-10-02).
    """
    cfg = escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4)
    principais(cfg, "pm-a", "pm-b")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    nomes = [d["nome"] for d in dv.ordem_das_verdadeiras(esc)]
    assert nomes == ["Enchantress", "Oath"], nomes
    # A ordem não depende da ordem de entrada.
    assert [d["nome"] for d in dv.ordem_das_verdadeiras(list(reversed(esc)))] \
        == nomes

    # Trocar a prioridade no config troca quem leva as verdadeiras — e é lá que
    # se troca, não no código.
    cfg2 = escreve_cfg()
    for c in cfg2["caixas"]:
        if c["slot"] == "pm-a":
            c["prioridade"] = 7
    principais(cfg2, "pm-a", "pm-b")
    rep2 = dv.relatorio(con, sources.config())
    f2 = fmt_de(rep2, "premodern")
    esc2 = [rep2["decks"][i] for i in f2["ids_escolhidos"]]
    r2 = dv.reparte_verdadeiras(esc2, rep2["pos"])
    assert r2["caixa:pm-b"]["Swords to Plowshares"]["verdadeiras"] == 4, r2
    assert r2["caixa:pm-a"]["Swords to Plowshares"]["proxies"] == 4, r2


def caso_as_duas_metades_somam_sempre_o_total():
    """`verdadeiras + proxies == total do deck`, sempre.

    É a disciplina do `confirmado.metades` (2026-10-02): uma metade perdida pelo
    caminho é meia verdade com cara de verdade.
    """
    cfg = escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=3)
    copia(con, "Wasteland", "tmp", q=1)
    principais(cfg, "pm-a", "pm-b", "pm-c")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    r = dv.reparte_verdadeiras(esc, rep["pos"])
    com_proxy = 0
    for d in esc:
        linha = r[d["id"]]
        v = sum(x["verdadeiras"] for x in linha.values())
        p = sum(x["proxies"] for x in linha.values())
        com_proxy += 1 if p else 0
        tot = dv.conta_do_deck(d, rep["pos"])["total"]
        assert v + p == tot, (d["nome"], v, p, tot)
        pag = dv.deck_para_pagina(con, d, rep["pos"], f["modo"], {},
                                  repartido=r)
        rp = pag["reparticao"]
        assert rp["n_verdadeiras"] + rp["n_proxies"] == pag["conta"]["total"], rp
    # ... e as metades não são trivialmente «tudo verdadeiro»: com 3 Swords para
    # dois decks que pedem 4 cada, há decks a levar proxy. Sem esta asserção, uma
    # repartição que desse as verdadeiras a TODOS passava neste caso.
    assert com_proxy >= 2, f"só {com_proxy} decks levam proxy"
    # E os sleeves do formato somam o mesmo.
    sl = dv.sleeves_do_formato(esc, {}, r)
    assert sl["reais"] + sl["proxies_copias"] == sl["total"], sl
    assert sl["proxies_copias"] > 0, sl


# ===========================================================================
# 5. A MARCA «principal» É EDITÁVEL, E AS CAIXAS A 0 % NÃO A TÊM
# ===========================================================================
def caso_a_marca_principal_e_editavel():
    """A escolha de quais são os principais foi INTERPRETAÇÃO minha (as 12 caixas
    que tinham lista), e por isso tem de se poder corrigir num toque.

    Põe-se e tira-se pelo `marcar_principal`, com DATA; tirar APAGA a chave em
    vez de escrever `false` — um `principal: false` em doze caixas era ruído num
    ficheiro que é para ser lido por uma pessoa.
    """
    cfg = escreve_cfg()
    assert dv.marcar_principal(cfg, "pm-a", True) is True
    c = next(x for x in cfg["caixas"] if x["slot"] == "pm-a")
    assert c["principal"] is True and c["principal_em"], c
    assert dv.sempre_montado(c) is True

    assert dv.marcar_principal(cfg, "pm-a", False) is False
    assert "principal" not in c and "principal_em" not in c, c
    assert dv.sempre_montado(c) is False

    # Uma caixa que o config não tem levanta — é o 409 do endpoint.
    try:
        dv.marcar_principal(cfg, "nao-existe", True)
        raise AssertionError("tinha de levantar")
    except ValueError as e:
        assert "nao-existe" in str(e), e


def caso_as_caixas_a_zero_por_cento_nao_sao_principais():
    """As quatro caixas sem lista (standard, os dois de legacy e a Artifacts Blue)
    e a `modern-affinity` desactivada ficam FORA da marca.

    Verifica-se no config a SÉRIO: é a interpretação que esta ordem fixou, e se
    estiver errada tem de se ver de onde veio.
    """
    cfg_real = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    por_slot = {c["slot"]: c for c in cfg_real["caixas"]}
    fora = ["standard", "legacy-aluren", "legacy-welder",
            "legacy-artifacts-blue", "modern-affinity"]
    for slot in fora:
        assert slot in por_slot, slot
        assert not por_slot[slot].get("principal"), \
            f"{slot} está a 0 % e não pode ser principal"
    dentro = ["pauper", "cedh-blue-farm", "cedh-cloud", "duel-commander",
              "premodern-stiflenought", "premodern-replenish",
              "premodern-enchantress", "premodern-elves", "premodern-oath",
              "premodern-igg", "modern", "pioneer"]
    for slot in dentro:
        assert por_slot[slot].get("principal") is True, slot
        assert por_slot[slot].get("principal_em") == "2026-10-05", slot
    assert sum(1 for c in cfg_real["caixas"] if c.get("principal")) == 12
    # E a razão da interpretação está ESCRITA no ficheiro.
    assert "INTERPRETACAO" in (cfg_real.get("_sempre_montado") or "")


def caso_uma_caixa_desactivada_nao_entra_como_escolhida():
    """Uma caixa `principal` sem lista (ou desactivada) não pode passar a contar
    como «vou montar este»: não há nada para montar nem para imprimir."""
    cfg = escreve_cfg()
    con = base()
    principais(cfg, "zero")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "legacy")
    assert f["ids_escolhidos"] == [], f["ids_escolhidos"]
    assert f["n_sempre"] == 0, f["n_sempre"]
    assert f["modo"] == dv.ROTATIVAS, "sem sempre-montados, o modo do grupo fica"
    linha = linha_de(f, "caixa:zero")
    assert linha["desactivada"] is True, linha


# ===========================================================================
# 6. UMA BÁSICA DA PILHA NUNCA É PROXY
# ===========================================================================
def caso_uma_basica_da_pilha_nunca_e_proxy():
    """*"em todos os decks, as basicas sao todas de Unhinged"* (08/09/2026).

    A pilha nunca foi uma linha da `copies` — entra por contagem declarada
    (02/10) — e por isso a `marcas.posse` responde ZERO a um Island. Enquanto isso
    só alimentava uma percentagem era inofensivo; com os proxies a serem as
    FALTAS, mandava-o imprimir 17 Island para o Stiflenought, que o `loadout` dá a
    100 % exactamente por esta isenção.

    Medido na base dele a 2026-10-05: **44 das 272 cópias em proxy eram básicas**.
    """
    cfg = escreve_cfg()
    con = base()
    principais(cfg, "pm-c")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    assert [d["id"] for d in esc] == ["caixa:pm-c"], esc
    r = dv.reparte_verdadeiras(esc, rep["pos"])
    px = dv.proxies_do_deck(esc[0], {}, r)
    assert "Island" not in [x["nm"] for x in px], px
    assert r["caixa:pm-c"]["Island"] == {"q": 10, "verdadeiras": 10,
                                        "proxies": 0, "pilha": True}
    # ... e a conta do deck conta-as como tidas, que é o que o `loadout` faz.
    c = dv.conta_do_deck(esc[0], rep["pos"])
    assert c["tem"] == 10, c      # as 10 Island; o resto não o tem
    # O tile di-lo, e NÃO mente dizendo «do inventário».
    pag = dv.deck_para_pagina(con, esc[0], rep["pos"], f["modo"], {}, repartido=r)
    cartas = {x["nm"]: x for g in pag["main"] for x in g["cartas"]}
    assert cartas["Island"]["pilha"] is True
    assert cartas["Island"]["origem"] == "pilha"
    assert cartas["Island"]["tenho"] == 10
    assert cartas["Island"]["na_base"] == 0


def caso_uma_snow_covered_continua_a_ser_falta():
    """As Snow-Covered NÃO existem em Unhinged, e por isso o que a colecção não
    tem é falta a sério — e leva proxy.

    A pergunta responde-se com a MESMA função do motor
    (`loadout.basicas_a_granel`) e não com uma lista nova aqui.
    """
    assert dv.da_pilha("Island") is True
    assert dv.da_pilha("Snow-Covered Plains") is False
    assert dv.da_pilha("Swords to Plowshares") is False
    assert loadout.basicas_a_granel("Snow-Covered Plains") is False

    cfg = escreve_cfg()
    con = base()
    # Um deck com Snow-Covered: a caixa pm-b passa a pedir 2.
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "SELECT id, 'Snow-Covered Plains', 2, 'main' FROM decks "
                "WHERE name = 'OA'")
    con.commit()
    principais(cfg, "pm-b")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    r = dv.reparte_verdadeiras(esc, rep["pos"])
    px = {x["nm"]: x["q"] for x in dv.proxies_do_deck(esc[0], {}, r)}
    assert px.get("Snow-Covered Plains") == 2, px


# ===========================================================================
# 7. DESMARCAR DEVOLVE O FORMATO AO MODO DO GRUPO
# ===========================================================================
def caso_desmarcar_devolve_o_formato_ao_modo_do_grupo():
    """*"NAO apagues o campo nem o codigo (...) Ele pode voltar atras"*.

    As duas direcções: com um deck principal o Premodern conta pela SOMA; sem
    nenhum volta ao `cartas_partilhadas: rotativas` do grupo e as próprias e
    partilhadas voltam a existir.
    """
    cfg = escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-05",
                                    "caixa:pm-b": "2026-10-05"})
    con = base()
    # (a) a rodar: a necessidade é o MÁXIMO (4 Swords para os dois decks).
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["modo"] == dv.ROTATIVAS and f["modo_trocado"] is False, f["modo"]
    # soma: 8 Swords + 2 Wrath + 3 Tutor + 2 Wasteland = 15
    # máximo: 4 Swords (uma cópia serve os dois) + 2 + 3 + 2 = 11
    assert f["necessidade"]["soma"] == 15, f["necessidade"]
    assert f["necessidade"]["maximo"] == 11, f["necessidade"]
    assert f["sleeves"]["proxies"] == 2, f["sleeves"]   # as Swords nos dois
    assert f["staples"], "o modelo de 04/10 tem staples"
    assert f["disputadas"] == [], "e não tem disputadas"

    # (b) principais: passa à SOMA, e a página diz qual era o modo do grupo.
    cfg2 = escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-05",
                                     "caixa:pm-b": "2026-10-05"})
    principais(cfg2, "pm-a", "pm-b")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["modo"] == dv.DEDICADAS, f["modo"]
    assert f["modo_formato"] == dv.ROTATIVAS, f["modo_formato"]
    assert f["modo_trocado"] is True
    assert f["n_sempre"] == 2, f["n_sempre"]
    assert f["staples"] == [], "sem pilha à parte não há staples"
    assert f["disputadas"], "passa a haver cartas disputadas"

    # (c) e volta atrás: desmarcar devolve tudo ao que era.
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-05",
                              "caixa:pm-b": "2026-10-05"})
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["modo"] == dv.ROTATIVAS and f["n_sempre"] == 0
    assert f["staples"] and f["disputadas"] == []


def caso_o_cartas_partilhadas_e_o_codigo_das_partilhadas_nao_se_apagaram():
    """A chave do grupo e o código das próprias/partilhadas FICAM — é o que faz o
    «voltar atrás» ser uma linha e não uma ordem nova."""
    cfg_real = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    por_grupo = {tuple(g.get("formatos") or []): g
                 for g in cfg_real["regras_por_formato"]}
    pm = por_grupo[("premodern",)]
    assert pm.get("cartas_partilhadas") == "rotativas", pm
    spml = next(g for k, g in por_grupo.items() if "modern" in k)
    assert spml.get("cartas_partilhadas") == "rotativas", spml
    # e as funções continuam de pé
    for nome in ("proprias_e_partilhadas", "e_partilhada", "reparticao",
                 "staples_do_formato", "partilha_do_formato", "e_rotativo"):
        assert callable(getattr(dv, nome)), nome
    assert dv.partilha_do_formato("premodern") == dv.ROTATIVAS
    assert dv.partilha_do_formato("cedh") == dv.DEDICADAS


# ===========================================================================
# 8. O `sempre_montado` ESCRITO À MÃO GANHA AO `principal`
# ===========================================================================
def caso_o_sempre_montado_escrito_a_mao_ganha_ao_principal():
    """Uma chave só para ele tocar (`principal`), e um eixo por caixa para o dia
    em que quiser desencostar os dois.

    Duas chaves com o mesmo valor em doze caixas eram duas verdades para a mesma
    pergunta — é o campo `decisao` que ele mandou apagar a 02/10.
    """
    assert dv.sempre_montado({"principal": True}) is True
    assert dv.sempre_montado({}) is False
    # um deck principal que ele quer a RODAR
    assert dv.sempre_montado({"principal": True, "sempre_montado": False}) is False
    # um deck que não é principal e fica montado
    assert dv.sempre_montado({"sempre_montado": True}) is True
    assert dv.e_principal({"sempre_montado": True}) is False

    cfg = escreve_cfg()
    con = base()
    principais(cfg, "pm-a", **{"pm-a": {"sempre_montado": False}})
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["n_sempre"] == 0, "o `sempre_montado: false` ganha"
    assert f["modo"] == dv.ROTATIVAS, f["modo"]
    assert linha_de(f, "caixa:pm-a")["principal"] is True
    assert linha_de(f, "caixa:pm-a")["sempre_montado"] is False


def caso_um_formato_de_cartas_dedicadas_ganha_proxies_e_sleeves():
    """O cEDH, o Duel Commander e o Pauper nunca tinham tido esta conta: o modo
    deles já era `dedicadas`, mas sem decks sempre montados não havia proxies
    nem sleeves (`sleeves: None`).

    Com um deck principal passam a ter as duas coisas — é o que ele pediu («esses
    quero ter sempre montados»), e é format-agnóstico.
    """
    cfg = escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    assert fmt_de(rep, "cedh")["sleeves"] is None
    assert fmt_de(rep, "cedh")["n_marcados"] == 0

    principais(cfg, "cedh-a")
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "cedh")
    assert f["modo"] == dv.DEDICADAS and f["modo_trocado"] is False
    assert f["n_sempre"] == 1 and f["n_marcados"] == 1
    assert f["sleeves"] is not None, "um deck montado tem sleeves"
    assert f["sleeves"]["proxies"] == 2, f["sleeves"]   # Mox Diamond + Wasteland
    assert linha_de(f, "caixa:cedh-a")["quero"] is True, \
        "um deck principal conta como escolhido, mesmo sem a marca à mão"
    # E a LISTA de proxies do deck também: num formato `dedicadas` nunca havia
    # repartição nenhuma, por isso é aqui que se vê que o caminho novo entra.
    esc = [rep["decks"][i] for i in f["ids_escolhidos"]]
    r = dv.reparte_verdadeiras(esc, rep["pos"])
    px = dv.proxies_do_deck(esc[0], {}, r)
    assert {x["nm"]: x["q"] for x in px} == {"Mox Diamond": 1,
                                            "Wasteland": 1}, px
    assert linha_de(f, "caixa:cedh-a")["proxies"] == 2, \
        "o índice leva o número de proxies de cada deck"


def caso_o_endpoint_grava_a_marca_e_recusa_uma_caixa_que_nao_existe():
    """`POST /api/deck-principal`: grava, é reversível, e **409 e não 500** numa
    caixa que o config já não tem.

    Uma página aberta ontem no telemóvel ainda manda a lista de caixas de ontem —
    é a regra da `VendaDesligada` e da `VersaoDesconhecida` (um `ValueError`, que
    o `do_POST` traduz). Sem slot é 400 (`SemLista`), que é outra coisa: o pedido
    está mal feito.
    """
    escreve_cfg()
    base()
    import webapp                                              # noqa: PLC0415
    gravados = []
    webapp.regenerar = lambda *a, **k: None
    webapp.escrever_config = lambda cfg: gravados.append(
        json.loads(json.dumps(cfg)))

    class Falso:
        _deck_principal = webapp.Handler._deck_principal

    f = Falso()
    r = f._deck_principal({"slot": "pm-a", "principal": True})
    assert r["ok"] and r["principal"] is True, r
    assert "principal" in r["msg"], r["msg"]
    c = next(x for x in gravados[-1]["caixas"] if x["slot"] == "pm-a")
    assert c["principal"] is True and c["principal_em"], c

    # ... e tira-se da mesma maneira.
    CAMINHO.write_text(json.dumps(gravados[-1], ensure_ascii=False),
                       encoding="utf-8")
    sources.esquecer_config()
    r = f._deck_principal({"slot": "pm-a", "principal": False})
    assert r["principal"] is False, r
    c = next(x for x in gravados[-1]["caixas"] if x["slot"] == "pm-a")
    assert "principal" not in c, c

    try:
        f._deck_principal({"slot": "nao-existe", "principal": True})
        raise AssertionError("tinha de levantar ValueError (409)")
    except webapp.SemLista:
        raise AssertionError("uma caixa desconhecida é 409, não 400") from None
    except ValueError as e:
        assert "nao-existe" in str(e), e

    try:
        f._deck_principal({"principal": True})
        raise AssertionError("tinha de levantar SemLista (400)")
    except webapp.SemLista as e:
        assert "caixa" in str(e), e


def caso_a_pagina_oferece_a_marca_so_no_modo_de_edicao():
    """O visto do `principal` existe **só** onde há endpoint que grave.

    No site publicado a informação fica (um rótulo «★ principal»), o controlo
    não — é a regra de sempre: um botão numa página estática é um botão que não
    faz nada. E o `data-principal` tem de estar ligado ao `change` delegado,
    senão o visto desenha-se e não grava (a lição do `data-enc` de 20/09, em que
    dois atributos iguais faziam o `+` chamar o «encontrei»).
    """
    import decks                                               # noqa: PLC0415
    js = decks._JS                                             # noqa: SLF001
    assert "data-principal" in js, "o controlo tem de existir"
    assert "principalHTML" in js
    assert "/api/deck-principal" in js, "e tem de ter endpoint"
    # o gate do modo de edição, na mesma função que desenha o controlo
    i = js.find("function principalHTML")
    j = js.find("\n}", i)
    corpo = js[i:j]
    assert "EDIT()" in corpo, "o controlo tem de estar atrás do EDIT()"
    assert "data-principal" in corpo
    # ... e o `change` delegado tem de o apanhar
    k = js.find("addEventListener('change'")
    assert k > 0 and "data-principal" in js[k:k + 600], \
        "o `data-principal` tem de estar ligado ao change delegado"
    # o endpoint está mesmo encaminhado no servidor
    import webapp                                              # noqa: PLC0415
    fonte = Path(webapp.__file__).read_text(encoding="utf-8")
    assert '"/api/deck-principal"' in fonte, fonte[:0]
    assert callable(webapp.Handler._deck_principal)


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    maus = 0
    for c in CASOS:
        try:
            c()
            print("  ok   ", c.__name__)
        except AssertionError as e:
            maus += 1
            print("  FALHA", c.__name__, "->", e)
        except Exception as e:                                 # noqa: BLE001
            maus += 1
            print("  ERRO ", c.__name__, "->", type(e).__name__, e)
    print(f"\n{len(CASOS) - maus}/{len(CASOS)} casos ok")
    sys.exit(1 if maus else 0)
