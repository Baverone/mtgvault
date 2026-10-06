"""A ABA DECKS: formato -> deck -> cartas, com + e - (André, 2026-10-04).

As palavras dele: *"Fazemos como no riftvault, fazes uma aba ou botao para
decks"*; *"CDEH, sao 2 decks, ambos tem link, cada deck tem as suas proprias
cartas, fazes a imagem de cada carta, com + e - para eu marcar se tenho a
carta"*; *"Premodern, (...) nos decks ficam apenas as cartas que sao proprias do
deck e cartas usadas em varios decks ficam de fora, vou imprimir proxie"*;
*"SPML a mesma coisa de Premodern"*.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_decks_vista.py`, que desliga uma peça de cada vez e exige
vermelho:

  1. a MARCA dele ganha ao inventário e os dois estados ficam distinguíveis;
  2. num formato `dedicadas` a mesma carta em dois decks pede DUAS cópias;
  3. num formato `rotativas` pede UMA — e os dois números mostram-se os dois;
  4. marcar um deck faz a necessidade CRESCER e desmarcar faz ENCOLHER;
  5. uma carta passa de PRÓPRIA a PARTILHADA quando ele marca o segundo deck que
     a usa, e volta atrás quando desmarca;
  6. a lista de PROXIES de um deck é exactamente a das partilhadas desse deck;
  7. o SIDEBOARD conta à parte do main, e os dois somam o total;
  8. um Artifact Creature cai em Creature e uma Artifact Land cai em LAND;
  9. o COMANDANTE aparece acima dos Creature, e a ordem dos grupos é a dele;
 10. as marcas SOBREVIVEM a uma corrida do daily;
 11. a página não embebe imagens e não passa do tecto de bytes;
 12. a regra das FOTOS está desligada e a colecção NÃO se lê como vazia;
 13. a escrita é um DELTA com `request_id` — um retry não conta a dobrar.

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

# Duas caixas de cEDH (cartas DEDICADAS) e três de Premodern (ROTATIVAS). É o
# mínimo para as duas regras se verem lado a lado no mesmo config.
CAIXAS = [
    {"slot": "cedh-a", "nome": "Blue Farm", "formato": "cedh", "fonte": "deck",
     "ref": "BF", "balde": "Colecção", "estado": "montada", "prioridade": 1},
    {"slot": "cedh-b", "nome": "Cloud cEDH", "formato": "cedh", "fonte": "deck",
     "ref": "CL", "balde": "Colecção", "estado": "montada", "prioridade": 2},
    {"slot": "pm-a", "nome": "Enchantress", "formato": "premodern",
     "fonte": "deck", "ref": "EN", "balde": "Colecção", "estado": "permanente",
     "prioridade": 3},
    {"slot": "pm-b", "nome": "Oath", "formato": "premodern", "fonte": "deck",
     "ref": "OA", "balde": "Colecção", "estado": "permanente", "prioridade": 4},
    {"slot": "pm-c", "nome": "Stiflenought", "formato": "premodern",
     "fonte": "deck", "ref": "ST", "balde": "Colecção", "estado": "permanente",
     "prioridade": 5},
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
    ],
    "caixas": CAIXAS,
    # A REGRA DAS FOTOS ESTÁ DESLIGADA (04/10/2026): é o que esta aba substitui.
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 30},
    "decks_montar": {},
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(**mudancas):
    """O config do teste, com as mudanças pedidas."""
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


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, confirmado, db,  # noqa: E402
                      decks_vista as dv, marcas, paginas, sources)

#: (nome, edição, data, preço, type_line). As três últimas são o caso 8: um
#: Artifact Creature, uma Artifact Land e uma Enchantment Land — cartas com mais
#: do que um tipo, que é onde a precedência se vê.
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.50, "Instant"),
    ("Birds of Paradise", "4ed", "1995-04-01", 9.0, "Creature — Bird"),
    ("Wasteland", "tmp", "1997-10-14", 80.0, "Land"),
    ("Mox Diamond", "sth", "1998-03-02", 500.0, "Artifact"),
    ("Cloud, Midgar Mercenary", "fin", "2025-06-13", 12.0,
     "Legendary Creature — Human Soldier"),
    ("Memnite", "som", "2010-10-01", 3.0, "Artifact Creature — Construct"),
    ("Ancient Den", "mrd", "2003-10-02", 4.0, "Artifact Land"),
    ("Urza's Saga", "mh2", "2021-06-18", 60.0, "Enchantment Land — Urza's Saga"),
    ("Enlightened Tutor", "mir", "1996-10-08", 20.0, "Instant"),
    ("Wrath of God", "4ed", "1995-04-01", 15.0, "Sorcery"),
]
_ABERTAS = []

#: As listas de cada deck: `ref -> [(board, nome, qty)]`.
LISTAS = {
    # cEDH (dedicadas): as duas pedem 1 Mox Diamond cada.
    "BF": [("main", "Mox Diamond", 1), ("main", "Cloud, Midgar Mercenary", 1),
           ("main", "Birds of Paradise", 1)],
    "CL": [("main", "Mox Diamond", 1), ("main", "Wasteland", 1)],
    # Premodern (rotativas): a Enchantress e o Oath pedem 4 Swords cada; o
    # Stiflenought não pede nenhuma. A Wrath é só da Enchantress.
    "EN": [("main", "Swords to Plowshares", 4), ("main", "Wrath of God", 2),
           ("side", "Enlightened Tutor", 3)],
    "OA": [("main", "Swords to Plowshares", 4), ("main", "Wasteland", 2)],
    "ST": [("main", "Memnite", 4), ("main", "Ancient Den", 4),
           ("main", "Urza's Saga", 2)],
}


def base():
    """Uma base nova com o catálogo mínimo e os cinco decks."""
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
        fmt = "cedh" if ref in ("BF", "CL") else "premodern"
        con.execute("INSERT INTO decks (name, format) VALUES (?, ?)", (ref, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (ref,)).fetchone()["id"]
        for board, nm, q in cards:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,?)", (did, nm, q, board))
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


def deck_de(rep, deck_id):
    return rep["decks"][deck_id]


# ===========================================================================
# 1. A MARCA DELE GANHA AO INVENTÁRIO, E OS DOIS ESTADOS SÃO DISTINGUÍVEIS
# ===========================================================================
def caso_a_marca_dele_ganha_ao_inventario():
    """*"NAO o ponhas a marcar tudo de novo a partir do zero"*: o inventário
    pré-preenche, e a marca dele ganha quando difere.

    As duas coisas nunca se confundem no ecrã: `origem` é `inventario` ou
    `marcado`, e a marca leva a DATA.
    """
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=3)

    p = marcas.posse(con)
    assert p["Mox Diamond"]["q"] == 3, p["Mox Diamond"]
    assert p["Mox Diamond"]["origem"] == marcas.INVENTARIO
    assert p["Mox Diamond"]["em"] is None

    # Ele diz que só tem 1 (perdeu duas). O `−` parte do INVENTÁRIO.
    r = marcas.ajustar(con, "Mox Diamond", -2, request_id="r1")
    assert r["base"] == marcas.INVENTARIO, r
    assert r["q"] == 1, r
    p = marcas.posse(con)
    assert p["Mox Diamond"]["q"] == 1
    assert p["Mox Diamond"]["origem"] == marcas.MARCADO
    assert p["Mox Diamond"]["em"], "a marca tem de levar a data"

    # E o INVENTÁRIO continua lá: nada se apagou da colecção.
    assert marcas.inventario(con)["Mox Diamond"] == 3
    assert paginas.posse_total(con)["Mox Diamond"] == 3

    # «esquecer» devolve ao inventário, e também não apaga nada.
    marcas.esquecer(con, "Mox Diamond")
    p = marcas.posse(con)
    assert p["Mox Diamond"]["q"] == 3
    assert p["Mox Diamond"]["origem"] == marcas.INVENTARIO


def caso_o_resumo_separa_as_duas_origens():
    """A linha honesta de cada página: quantas vêm do inventário e quantas ele
    marcou. Sem isto o número de cima não dizia de onde vinha."""
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=3)
    copia(con, "Wasteland", "tmp", q=2)
    r = marcas.resumo(con)
    assert r["marcados_por_ti"] == 0, r
    assert "todas do inventário" in marcas.frase(con)
    marcas.ajustar(con, "Wasteland", 1, request_id="w1")
    r = marcas.resumo(con)
    assert r["marcados_por_ti"] == 1, r
    assert r["copias_marcadas"] == 3, r
    assert r["copias_do_inventario"] == 3, r      # as 3 Mox, que ele não tocou
    assert "marcaste tu" in marcas.frase(con)


def caso_um_retry_nao_conta_a_dobrar():
    """A escrita é um DELTA com `request_id` (o padrão do riftvault): repetir o
    MESMO pedido dá o mesmo resultado, e não soma outra vez."""
    escreve_cfg()
    con = base()
    copia(con, "Wasteland", "tmp", q=1)
    a = marcas.ajustar(con, "Wasteland", 1, request_id="mesmo")
    assert a["q"] == 2, a
    b = marcas.ajustar(con, "Wasteland", 1, request_id="mesmo")
    assert b["repetido"] is True, b
    assert b["q"] == 2, "um retry com o mesmo request_id contou a dobrar"
    # Um pedido NOVO soma.
    c = marcas.ajustar(con, "Wasteland", 1, request_id="outro")
    assert c["q"] == 3, c


def caso_o_menos_trava_no_zero_e_o_nome_valida_se():
    escreve_cfg()
    con = base()
    r = marcas.ajustar(con, "Wasteland", -5, request_id="z")
    assert r["q"] == 0, r
    try:
        marcas.ajustar(con, "Carta Que Nao Existe", 1)
    except marcas.CartaDesconhecida:
        pass
    else:
        raise AssertionError("marcou uma carta que o catálogo não conhece")


# ===========================================================================
# 2 e 3. DEDICADAS SOMA, ROTATIVAS TIRA O MÁXIMO
# ===========================================================================
def caso_dedicadas_a_mesma_carta_em_dois_decks_pede_duas():
    """*"cada deck tem as suas proprias cartas"* (02/10) — e é isso que o cEDH
    continua a ser. Os dois decks pedem 1 Mox Diamond cada: a necessidade do
    formato é **2**."""
    escreve_cfg(decks_montar={"caixa:cedh-a": "2026-10-04",
                              "caixa:cedh-b": "2026-10-04"})
    con = base()
    cfg = sources.config()
    assert dv.partilha_do_formato("cedh") == dv.DEDICADAS
    rep = dv.relatorio(con, cfg)
    f = fmt_de(rep, "cedh")
    assert f["modo"] == dv.DEDICADAS
    nec = dv.necessidade([deck_de(rep, i) for i in
                          ("caixa:cedh-a", "caixa:cedh-b")])
    assert nec["Mox Diamond"]["soma"] == 2, nec["Mox Diamond"]
    assert nec["Mox Diamond"]["maximo"] == 1, nec["Mox Diamond"]
    # e a regra do formato usa a SOMA
    pos = marcas.posse(con)
    assert dv.faltas(nec, pos, dv.DEDICADAS)["Mox Diamond"] == 2


def caso_rotativas_a_mesma_carta_em_dois_decks_pede_uma():
    """*"cartas usadas em varios decks ficam de fora, vou imprimir proxie, e so
    meto as verdadeiras no deck quando for jogar"* — logo uma cópia verdadeira
    serve os dois, e a necessidade é o MÁXIMO."""
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04",
                              "caixa:pm-b": "2026-10-04"})
    con = base()
    assert dv.partilha_do_formato("premodern") == dv.ROTATIVAS
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["modo"] == dv.ROTATIVAS
    nec = dv.necessidade([deck_de(rep, i) for i in ("caixa:pm-a", "caixa:pm-b")])
    assert nec["Swords to Plowshares"]["soma"] == 8, nec["Swords to Plowshares"]
    assert nec["Swords to Plowshares"]["maximo"] == 4, nec["Swords to Plowshares"]
    pos = marcas.posse(con)
    assert dv.faltas(nec, pos, dv.ROTATIVAS)["Swords to Plowshares"] == 4


def caso_os_dois_numeros_mostram_se_sempre_os_dois():
    """*"Mostra SEMPRE os dois numeros lado a lado"*: mesmo o que a regra do
    formato não usa. É a diferença entre eles que diz quanto custa a decisão."""
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04",
                              "caixa:pm-b": "2026-10-04",
                              "caixa:cedh-a": "2026-10-04",
                              "caixa:cedh-b": "2026-10-04"})
    con = base()
    rep = dv.relatorio(con, sources.config())
    for nome in ("premodern", "cedh"):
        n = fmt_de(rep, nome)["necessidade"]
        for k in ("soma", "maximo", "faltam_a_somar", "faltam_a_rodar"):
            assert k in n, f"{nome} não traz {k}: {n}"
    pm = fmt_de(rep, "premodern")["necessidade"]
    assert pm["soma"] > pm["maximo"], pm
    assert pm["faltam_a_somar"] > pm["faltam_a_rodar"], pm


# ===========================================================================
# 4. MARCAR FAZ CRESCER, DESMARCAR FAZ ENCOLHER
# ===========================================================================
def caso_marcar_um_deck_faz_a_necessidade_crescer_e_desmarcar_encolher():
    escreve_cfg(decks_montar={"caixa:cedh-a": "2026-10-04"})
    con = base()
    um = fmt_de(dv.relatorio(con, sources.config()), "cedh")["necessidade"]

    escreve_cfg(decks_montar={"caixa:cedh-a": "2026-10-04",
                              "caixa:cedh-b": "2026-10-04"})
    dois = fmt_de(dv.relatorio(con, sources.config()), "cedh")["necessidade"]
    assert dois["soma"] > um["soma"], (um, dois)

    escreve_cfg(decks_montar={})
    zero = fmt_de(dv.relatorio(con, sources.config()), "cedh")["necessidade"]
    assert zero["soma"] == 0, zero
    assert zero["cartas"] == 0, zero


def caso_marcar_e_reversivel_e_datado():
    cfg = json.loads(json.dumps(CFG))
    dv.marcar(cfg, "caixa:pm-a", True, quando="2026-10-04")
    assert cfg["decks_montar"] == {"caixa:pm-a": "2026-10-04"}
    dv.marcar(cfg, "caixa:pm-a", False)
    assert cfg["decks_montar"] == {}


# ===========================================================================
# 5 e 6. PRÓPRIA vs PARTILHADA, E OS PROXIES
# ===========================================================================
def caso_propria_passa_a_partilhada_quando_marca_o_segundo_deck():
    """*"NÃO É UMA ETIQUETA DA CARTA: depende de QUAIS decks ele marcou"*. Com a
    Enchantress sozinha, as 4 Swords são PRÓPRIAS dela; marcando o Oath (que
    também as joga) passam a PARTILHADAS — e desmarcar faz o caminho de volta."""
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04"})
    con = base()
    rep = dv.relatorio(con, sources.config())
    d = deck_de(rep, "caixa:pm-a")
    rp = dv.reparticao([d])
    assert not dv.e_partilhada("Swords to Plowshares", rp), "sozinha já é partilhada"
    p = dv.proprias_e_partilhadas(d, rp)
    assert ("main", "Swords to Plowshares", 4) in p["proprias"], p["proprias"]
    assert p["n_partilhadas"] == 0, p

    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04",
                              "caixa:pm-b": "2026-10-04"})
    rep = dv.relatorio(con, sources.config())
    ds = [deck_de(rep, i) for i in ("caixa:pm-a", "caixa:pm-b")]
    rp = dv.reparticao(ds)
    assert dv.e_partilhada("Swords to Plowshares", rp), \
        "com dois decks a usá-la, continua a dizer-se própria"
    p = dv.proprias_e_partilhadas(ds[0], rp)
    assert ("main", "Swords to Plowshares", 4) in p["partilhadas"], p["partilhadas"]
    # a Wrath of God é só da Enchantress: continua própria
    assert ("main", "Wrath of God", 2) in p["proprias"], p["proprias"]
    assert p["com_quem"]["Swords to Plowshares"] == ["caixa:pm-b"], p["com_quem"]

    # E VOLTA ATRÁS ao desmarcar o segundo.
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04"})
    rep = dv.relatorio(con, sources.config())
    rp = dv.reparticao([deck_de(rep, "caixa:pm-a")])
    assert not dv.e_partilhada("Swords to Plowshares", rp), \
        "desmarcar não devolveu a carta a própria"


def caso_a_lista_de_proxies_e_igual_as_partilhadas():
    """*"a LISTA DE PROXIES A IMPRIMIR = exactamente as partilhadas desse
    deck"*. Se um dia as duas discordarem, ele imprime o proxy errado."""
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04",
                              "caixa:pm-b": "2026-10-04"})
    con = base()
    rep = dv.relatorio(con, sources.config())
    ds = [deck_de(rep, i) for i in ("caixa:pm-a", "caixa:pm-b")]
    rp = dv.reparticao(ds)
    for d in ds:
        p = dv.proprias_e_partilhadas(d, rp)
        px = dv.proxies_do_deck(d, rp)
        esperado = {}
        for _b, nm, q in p["partilhadas"]:
            esperado[nm] = esperado.get(nm, 0) + q
        assert {x["nm"]: x["q"] for x in px} == esperado, (d["id"], px, esperado)
        assert sum(x["q"] for x in px) == p["n_partilhadas"], (d["id"], px)


def caso_os_sleeves_contam_as_verdadeiras_e_os_proxies():
    """ESCRITO a 2026-10-04 à tarde; a asserção dos `proxies` CORRIGIDA ao fim do
    mesmo dia, e não mascarada.

    Até ao fim do dia o `proxies` eram CÓPIAS — 4 Swords em cada um dos dois
    decks davam 8. Ao fim do dia mediu-se a conta que o André trouxe da mesa
    (*"149 PROXIES"* em Modern, *"63"* em Premodern) e ela é por **carta
    diferente em cada deck**: por aparições dão 147 e 69, por cópias davam 334 e
    201. Ou seja ele imprime um proxy por carta diferente — serve de marcador de
    *"esta vem da pilha"* — e não quatro proxies de um playset.

    Portanto `proxies` é o que ele IMPRIME (2: um Swords em cada um dos dois
    decks) e `proxies_copias` é o que SAI dos decks (8). O que não mudou é que as
    duas metades têm de somar o total — uma cópia perdida pelo caminho é meia
    verdade com cara de verdade.
    """
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04",
                              "caixa:pm-b": "2026-10-04"})
    con = base()
    rep = dv.relatorio(con, sources.config())
    s = fmt_de(rep, "premodern")["sleeves"]
    ds = [deck_de(rep, i) for i in ("caixa:pm-a", "caixa:pm-b")]
    rp = dv.reparticao(ds)
    esperado = sum(sum(q for _b, _n, q in dv.proprias_e_partilhadas(d, rp)[k])
                   for d in ds for k in ("proprias", "partilhadas"))
    assert s["total"] == esperado, (s, esperado)
    assert s["reais"] + s["proxies_copias"] == s["total"], s
    assert s["proxies_copias"] == 8, s   # 4 Swords em cada um dos dois decks
    assert s["proxies"] == 2, s          # um proxy de Swords por deck
    assert s["proxies_nomes"] == 1, s    # e é uma carta diferente só
    # Num formato DEDICADO não há sleeves/proxies: não há nada a rodar.
    assert fmt_de(rep, "cedh")["sleeves"] is None


# ===========================================================================
# 7. O SIDEBOARD CONTA À PARTE DO MAIN
# ===========================================================================
def caso_o_sideboard_conta_a_parte_do_main():
    """A Enchantress tem 6 no main (4 Swords + 2 Wrath) e 3 no side (Tutor).
    Ele tem de montar o sideboard à parte, e um número que os misture não lhe
    diz se já pode ir jogar."""
    escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4)
    copia(con, "Enlightened Tutor", "mir", q=1)
    rep = dv.relatorio(con, sources.config())
    d = deck_de(rep, "caixa:pm-a")
    c = dv.conta_do_deck(d, marcas.posse(con))
    assert c["main"] == {"total": 6, "tem": 4}, c["main"]
    assert c["side"] == {"total": 3, "tem": 1}, c["side"]
    assert c["total"] == 9 and c["tem"] == 5, c
    # as duas metades somam SEMPRE o total
    assert c["main"]["total"] + c["side"]["total"] == c["total"], c
    assert c["main"]["tem"] + c["side"]["tem"] == c["tem"], c
    # e a página desenha-os em dois blocos
    pag = dv.deck_para_pagina(con, d, marcas.posse(con), dv.ROTATIVAS, {})
    assert pag["main"] and pag["side"], pag
    nomes_side = {x["nm"] for g in pag["side"] for x in g["cartas"]}
    assert nomes_side == {"Enlightened Tutor"}, nomes_side


def caso_a_posse_trava_no_que_o_deck_pede():
    """Ter 8 Swords não faz um deck que pede 4 ficar a 200 %."""
    escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=8)
    rep = dv.relatorio(con, sources.config())
    c = dv.conta_do_deck(deck_de(rep, "caixa:pm-b"), marcas.posse(con))
    assert c["tem"] == 4 and c["total"] == 6, c
    assert c["pct"] == 67, c


# ===========================================================================
# 8. O TIPO MAIS ESPECÍFICO
# ===========================================================================
def caso_artifact_creature_cai_em_creature_e_artifact_land_em_land():
    """*"pelo mais ESPECIFICO: um Artifact Creature conta como Creature (nao
    como Artifact), um Enchantment Creature como Creature, uma Artifact Land
    como Land"*.

    É DELIBERADAMENTE outra resposta que a do `paginas.tipo_de`, que diz
    `Artifact` à Ancient Den — e continua a dizer, para a Deckboxes e o Showcase
    não mudarem o agrupamento sem ninguém pedir.
    """
    assert dv.tipo_da_carta("Artifact Creature — Construct") == "Creature"
    assert dv.tipo_da_carta("Artifact Land") == "Land"
    assert dv.tipo_da_carta("Enchantment Land — Urza's Saga") == "Land"
    assert dv.tipo_da_carta("Legendary Enchantment Creature — God") == "Creature"
    assert dv.tipo_da_carta("Battle — Siege") == "Outras"
    assert dv.tipo_da_carta("Kindred Sorcery — Goblin") == "Sorcery"
    assert dv.tipo_da_carta(None) == "Outras"
    # a divergência é DELIBERADA e fica trancada
    assert paginas.tipo_de("Artifact Land") == "Artifact", \
        "o paginas.tipo_de mudou: a Deckboxes mudou de agrupamento sem ninguém pedir"


def caso_as_cartas_a_serio_caem_no_grupo_certo():
    """Com cartas DA BASE e não com `type_line` escrito à mão (ordem: *"testa
    com um Artifact Creature e uma Artifact Land verdadeiras da base"*)."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    pag = dv.deck_para_pagina(con, deck_de(rep, "caixa:pm-c"),
                              marcas.posse(con), dv.ROTATIVAS, {})
    onde = {x["nm"]: g["tipo"] for g in pag["main"] for x in g["cartas"]}
    assert onde["Memnite"] == "Creature", onde          # Artifact Creature
    assert onde["Ancient Den"] == "Land", onde          # Artifact Land
    assert onde["Urza's Saga"] == "Land", onde          # Enchantment Land


# ===========================================================================
# 9. O COMANDANTE À CABEÇA, E A ORDEM DELE
# ===========================================================================
def caso_o_comandante_aparece_acima_dos_creature():
    """Correcção pedida pelo supervisor: é a carta que identifica o deck, e
    enterrada no meio dos Creature não se encontra."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    d = deck_de(rep, "caixa:cedh-a")
    pag = dv.deck_para_pagina(con, d, marcas.posse(con), dv.DEDICADAS, {},
                              cmdr="Cloud, Midgar Mercenary")
    tipos = [g["tipo"] for g in pag["main"]]
    assert tipos[0] == dv.COMANDANTE, tipos
    assert "Creature" in tipos and tipos.index(dv.COMANDANTE) < tipos.index("Creature")
    cmdr = [x["nm"] for g in pag["main"] if g["tipo"] == dv.COMANDANTE
            for x in g["cartas"]]
    assert cmdr == ["Cloud, Midgar Mercenary"], cmdr
    # e as Birds continuam em Creature, não no grupo do comandante
    cr = [x["nm"] for g in pag["main"] if g["tipo"] == "Creature" for x in g["cartas"]]
    assert cr == ["Birds of Paradise"], cr


def caso_a_ordem_dos_grupos_e_a_dele():
    """*"Creature, Sorcery, Instant; Artifact, Enchantment, Planeswalker, Land,
    Outras"*, com o Commander à cabeça."""
    assert dv.ORDEM_TIPOS == ["Commander", "Creature", "Sorcery", "Instant",
                              "Artifact", "Enchantment", "Planeswalker",
                              "Land", "Outras"], dv.ORDEM_TIPOS
    # E É POR ELA QUE A PÁGINA ORDENA, não pela ordem alfabética. O conjunto é
    # escolhido de propósito para as duas DIFEREREM: com `{Land, Creature,
    # Instant, Commander, Outras}` a ordem alfabética dá por acaso a mesma
    # resposta, e o caso passava com um `sorted()` lá dentro (apanhado pelo
    # `_chumba_decks_vista`, alvo 11).
    g = dv.ordenar_grupos({"Land", "Creature", "Sorcery", "Artifact", "Commander"})
    assert g == ["Commander", "Creature", "Sorcery", "Artifact", "Land"], g
    assert g != sorted(g), "a ordem dele passou a ser a alfabética"
    assert dv.ORDEM_TIPOS[1:-1] != paginas.TIPOS, \
        "as duas ordens convergiram: uma delas deixou de responder à sua pergunta"


def caso_um_formato_sem_comandante_nao_tem_grupo_de_comandante():
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    assert dv.comandante_do_deck(con, deck_de(rep, "caixa:pm-a")) is None
    pag = dv.deck_para_pagina(con, deck_de(rep, "caixa:pm-a"),
                              marcas.posse(con), dv.ROTATIVAS, {})
    assert dv.COMANDANTE not in [g["tipo"] for g in pag["main"]]


# ===========================================================================
# 10. AS MARCAS SOBREVIVEM AO DAILY
# ===========================================================================
def caso_as_marcas_sobrevivem_ao_daily():
    """A corrida do `daily` reescreve o HTML e os `data/paginas/**`. As marcas
    vivem na BASE (`posse_marcada`) e por isso nenhuma regeneração lhes toca —
    é exactamente isso que este caso tranca."""
    import decks as decks_pag                                # noqa: PLC0415
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=3)
    marcas.ajustar(con, "Mox Diamond", -2, request_id="d1")
    antes = marcas.posse(con)["Mox Diamond"]
    assert antes == {"q": 1, "origem": marcas.MARCADO, "em": antes["em"]}

    out = _TMP / "site"
    out.mkdir(exist_ok=True)
    decks_pag.build(con, out / "decks.html")                 # a corrida do daily
    decks_pag.build(con, out / "decks.html")                 # e outra, por tirar a dúvida

    depois = marcas.posse(con)["Mox Diamond"]
    assert depois == antes, (antes, depois)
    assert marcas.marcadas(con)["Mox Diamond"]["q"] == 1
    # e a página desenhada diz que a marca é dele
    idx, partes = decks_pag.dados(con)
    p = partes["deck-" + decks_pag.parte_do_deck("caixa:cedh-a")]
    mox = next(x for g in p["main"] for x in g["cartas"] if x["nm"] == "Mox Diamond")
    assert mox["origem"] == marcas.MARCADO, mox
    assert mox["tenho"] == 1, mox


# ===========================================================================
# 11. A PÁGINA: SEM IMAGENS EMBUTIDAS E DENTRO DO TECTO
# ===========================================================================
def caso_a_pagina_nao_embebe_imagens_e_cabe_no_tecto():
    """CORRIGIDO A 2026-10-05: o JavaScript saiu da casca para o `decks.js`.

    A asserção não mudou de intenção — a página continua a não poder embeber
    imagens e tem de apontar ao CDN com as quatro coisas que impedem o ecrã de
    saltar. O que mudou é ONDE isso está escrito: as `<img>` são desenhadas pelo
    JavaScript, e esse passou a ser um ficheiro à parte (a casca ia a 89 393 de
    90 112 bytes; ver `decks.TECTO_CASCA`). Por isso o tecto mede a CASCA e as
    imagens medem-se na PÁGINA INTEIRA — casca + `.js` —, que é o que o browser
    acaba por ter. Mascarar isto era deixar de verificar as imagens no dia em
    que elas mudaram de ficheiro.
    """
    import decks as decks_pag                                # noqa: PLC0415
    escreve_cfg()
    con = base()
    casca = decks_pag.casca()
    n = len(casca.encode("utf-8"))
    assert n <= decks_pag.TECTO_CASCA, \
        f"a casca tem {n} bytes e o tecto é {decks_pag.TECTO_CASCA}"
    js = decks_pag.js_texto()
    # A CASCA tem de apontar para o `.js`, senão a página abre e não desenha.
    assert f'src="{decks_pag.NOME_JS}?v=' in casca, (
        "a casca tem de apontar para o `decks.js` com o hash do conteúdo")
    pagina = casca + js
    for onde, txt in (("casca", casca), ("decks.js", js)):
        assert "data:image" not in txt, f"a {onde} embebeu uma imagem"
        assert "base64" not in txt, f"a {onde} embebeu algo em base64"
    # as imagens são REMOTAS, do catálogo
    assert "cards.scryfall.io" in pagina, "a página não aponta ao CDN das artes"
    # e cada uma leva o que impede o ecrã de saltar e de carregar tudo de uma vez
    assert 'loading="lazy"' in pagina and 'decoding="async"' in pagina
    assert 'width="146" height="204"' in pagina, "faltam as dimensões na <img>"
    assert "aspect-ratio" in pagina, "falta o aspect-ratio da moldura"


def caso_cada_deck_vai_numa_parte_e_o_indice_nao_leva_cartas():
    """A decisão de 2026-09-15: o índice é a casca dos dados e as cartas vão à
    parte, idas buscar quando ele abre o deck."""
    import decks as decks_pag                                # noqa: PLC0415
    escreve_cfg()
    con = base()
    idx, partes = decks_pag.dados(con)
    assert len(partes) == len(CAIXAS), partes.keys()
    bruto = json.dumps(idx, ensure_ascii=False)
    assert "Swords to Plowshares" not in bruto, \
        "o índice levou a lista de cartas de um deck"
    for nome in partes:
        assert decks_pag.re.fullmatch(r"[A-Za-z0-9_-]+", nome), nome


def caso_o_nome_da_parte_bate_com_o_do_javascript():
    """A MESMA conta nos dois lados: se discordarem, o `fetch` dá 404."""
    import decks as decks_pag                                # noqa: PLC0415
    assert decks_pag.parte_do_deck("meta:premodern:enchantress") == \
        "meta-premodern-enchantress"
    assert decks_pag.parte_do_deck("caixa:pm-a") == "caixa-pm-a"
    js = decks_pag._JS
    assert "replace(/[^A-Za-z0-9_-]+/g, '-')" in js, \
        "o JavaScript deixou de calcular o nome da parte da mesma maneira"


def caso_a_barra_lateral_tem_a_aba_decks():
    from mtgvault import site_shell as shell                 # noqa: PLC0415
    itens = [(f, a, lab) for _s, its in shell.SECCOES for f, a, _i, lab, _n in its]
    assert ("decks.html", "", "Decks") in itens, itens
    assert "decks.html" in shell.PAGINAS_DO_MENU


# ===========================================================================
# 12. A REGRA DAS FOTOS ESTÁ DESLIGADA, E A COLECÇÃO NÃO SE LÊ COMO VAZIA
# ===========================================================================
def caso_a_regra_das_fotos_esta_desligada_e_a_coleccao_nao_e_vazia():
    """*"ISTO SUBSTITUI A CAMPANHA DAS FOTOS"*. Com o `foto_manda` ligado e sem
    fotos, a colecção inteira lia-se como vazia e nada funcionava.

    O interruptor é `revalidacao.foto_manda` — a chave de 02/10, não uma
    segunda —, e o código das fotos fica TODO no sítio: o caso seguinte volta a
    ligá-lo e exige que a regra morda outra vez.
    """
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=3)
    copia(con, "Swords to Plowshares", "4ed", q=4)
    assert confirmado.manda() is False, "a regra das fotos está ligada"
    pos = marcas.posse(con)
    assert sum(x["q"] for x in pos.values()) == 7, pos
    rep = dv.relatorio(con, sources.config())
    assert rep["marcas"]["copias"] == 7, rep["marcas"]
    # a Enchantress pede 4 Swords e ele tem-nas: não é zero por falta de foto
    c = dv.conta_do_deck(deck_de(rep, "caixa:pm-a"), pos)
    assert c["tem"] == 4, c


def caso_o_codigo_das_fotos_continua_todo_no_sitio():
    """Nada se apagou: voltar a ligar o `foto_manda` tem de fazer a regra morder
    outra vez. Se este caso deixar de passar, alguém arrancou o código pela
    raiz."""
    escreve_cfg(revalidacao={"desde": "2026-09-20", "foto_manda": True})
    assert confirmado.manda() is True, "o interruptor deixou de ligar"
    assert hasattr(confirmado, "sql") and hasattr(confirmado, "metades")
    from mtgvault import fotos, fotosite, revalidacao          # noqa: PLC0415
    for m in (fotos, fotosite, revalidacao):
        assert m is not None
    escreve_cfg()                                             # volta a desligar
    assert confirmado.manda() is False


# ===========================================================================
# 13. O REGISTO: PELO NOME DA FONTE, E O LINK DE CADA DECK
# ===========================================================================
def caso_o_meta_so_se_oferece_nos_formatos_rotativos():
    """A pergunta *"queres montar este?"* foi pedida para o Premodern e o SPML.
    Nos dedicados ele ENUMEROU os decks (*"CDEH, sao 2 decks"*), e os meta
    contam-se e dizem-se em vez de se oferecerem."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    for f in rep["formatos"]:
        if f["modo"] == dv.DEDICADAS:
            assert all(d["fonte"] == "caixa" for d in f["decks"]), f["formato"]
            assert "meta_fora" in f, f
        # e nos dois formatos o nº de decks é o nº de caixas + os meta
    assert len(fmt_de(rep, "cedh")["decks"]) == 2, "o cEDH tem de ter 2 decks"
    assert len(fmt_de(rep, "premodern")["decks"]) == 3


def caso_o_registo_nao_usa_a_etiqueta_do_clustering():
    """Os arquétipos meta saem de `decklists.arquetipo_fonte` — o nome que o
    mtgtop8 escreve na página do evento — e nunca da `archetypes.label`."""
    import inspect                                            # noqa: PLC0415
    from mtgvault import nomes                                # noqa: PLC0415
    src = inspect.getsource(dv.arquetipos_meta)
    assert "listas_por_nome" in src, src[:400]
    assert "archetypes" not in src and ".label" not in src, \
        "o registo voltou a ler a etiqueta do clustering"
    # E quem agrupa pela coluna é o `mtgvault.nomes`, num sítio só: o
    # `test_nomes_arquetipo.caso_a_pergunta_do_nome_vive_num_sitio_so` varre o
    # código à procura de um segundo leitor, e este caso diz onde vive o primeiro.
    assert "arquetipo_fonte" in inspect.getsource(nomes.listas_por_nome)


def caso_o_id_de_um_deck_e_estavel():
    """A marca dele tem de sobreviver às corridas: o id de um meta sai do NOME
    DA FONTE e o de uma caixa do `slot`."""
    assert dv.id_meta("premodern", "Enchantress") == "meta:premodern:enchantress"
    assert dv.id_meta("premodern", "Sligh (RDW)") == "meta:premodern:sligh-rdw"
    assert dv.id_da_caixa("pm-a") == "caixa:pm-a"
    # o mesmo nome dá sempre o mesmo id
    assert dv.id_meta("modern", "UR Cutter Prowess") == \
        dv.id_meta("modern", "UR Cutter Prowess")


def caso_a_ordem_dos_decks_e_pela_percentagem():
    """*"depois de escolher, ordenamos"*: maior percentagem primeiro, que é a
    resposta a *"qual é o mais barato de fechar"*."""
    escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4)
    copia(con, "Wasteland", "tmp", q=2)
    rep = dv.relatorio(con, sources.config())
    pcts = [d["pct"] for d in fmt_de(rep, "premodern")["decks"] if not d["sem_lista"]]
    assert pcts == sorted(pcts, reverse=True), pcts
    assert pcts[0] > pcts[-1], pcts


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
