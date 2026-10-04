"""UM DECK POR FORMATO, COM VERSÕES POR DENTRO (André, 2026-10-04, à noite).

As palavras dele: *"vamos fazer uma coisa diferente, a ver como fica"*; *"quero
apenas manter decks que usem Mox Opal, tudo o resto e para vender (em modern)"*;
*"quero ficar com 1 deck e versoes do deck (como opcoes)"*; *"Legacy ainda nao
sei"*.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_versoes.py`, que desliga uma peça de cada vez e exige vermelho:

  1. o formato tem UM deck com N versões, e não N decks;
  2. os outros que jogam a carta-chave aparecem FORA da escolha e **não
     desaparecem** — com o teste do critério ao lado;
  3. um deck que SAIU da escolha continua consultável, com a lista e a razão;
  4. uma carta que joga num formato POR DECIDIR acima do limiar **não entra**
     nas candidatas, e entra assim que o formato for decidido;
  5. mudar a versão escolhida recalcula a necessidade e as próprias/partilhadas;
  6. todas as versões continuam PROTEGIDAS, não só a escolhida;
  7. um formato fora do modelo (o Premodern) fica exactamente como estava;
  8. esvaziar o bloco devolve o vault ao modelo anterior (é o interruptor);
  9. escolher uma versão que não existe é recusado, e repetir é um no-op;
 10. a lista dos «outros» é DERIVADA da base — um deck novo aparece sozinho.

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

CAIXAS = [
    # Premodern FICA COMO ESTÁ: dois decks, a pergunta «queres montar este?» de
    # sempre. É o controlo do caso 7.
    {"slot": "pm-a", "nome": "Enchantress", "formato": "premodern",
     "fonte": "deck", "ref": "EN", "balde": "Colecção", "estado": "permanente",
     "prioridade": 1},
    {"slot": "pm-b", "nome": "Oath", "formato": "premodern", "fonte": "deck",
     "ref": "OA", "balde": "Colecção", "estado": "permanente", "prioridade": 2},
    # A caixa de Modern é a lista DELE, e é também a versão «alfa».
    {"slot": "mod", "nome": "Modern — Affinity", "formato": "modern",
     "fonte": "deck", "ref": "MO", "balde": "Colecção", "estado": "permanente",
     "prioridade": 3},
    {"slot": "leg", "nome": "Legacy", "formato": "legacy", "fonte": "deck",
     "ref": "LG", "balde": "Colecção", "estado": "permanente", "prioridade": 4},
]

VERSOES = [
    {"id": "versao:modern:alfa", "arquetipo_id": 1, "nome": "Alfa",
     "listas": 20, "deck": "caixa:mod"},
    {"id": "versao:modern:beta", "arquetipo_id": 2, "nome": "Beta", "listas": 8},
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
        {"grupo": "spml", "formatos": ["modern", "legacy"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 30},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": {
        # A lista da versão «beta», fixada como uma lista de evento real.
        "versao:modern:beta": {
            "nome": "Beta", "formato": "modern", "padrao": True,
            "origem": "um jogador · um evento · 2026-10-01",
            "cards": [["main", "Mox Opal", 4], ["main", "Kappa Cannoneer", 2],
                      ["main", "Pinnacle Emissary", 4],
                      ["main", "Wrath of God", 2]],
        },
    },
    "decks_por_formato": {
        "_corte_pct": 5.0,
        "modern": {
            "nome": "Affinity (Mox Opal)", "porque": "só decks de Mox Opal",
            "em": "2026-10-04",
            "criterio": {"carta": "Mox Opal",
                         "exige": ["Kappa Cannoneer", "Pinnacle Emissary"],
                         "pct_minima": 50},
            "versoes": VERSOES, "versao": "versao:modern:alfa",
        },
        "legacy": {"nome": "(por decidir)", "por_decidir": True, "versoes": []},
    },
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(_substitui=(), **mudancas):
    """O config do teste. As chaves em `_substitui` TROCAM-SE inteiras em vez de
    se fundirem — sem isso, `decks_por_formato={}` era um `update({})`, ou seja
    um no-op, e o caso do interruptor passava a verde sem provar nada."""
    from mtgvault import sources                             # noqa: PLC0415
    d = json.loads(json.dumps(CFG))
    for k, v in mudancas.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict) and k not in _substitui:
            d[k].update(v)
        else:
            d[k] = v
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    return d


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, db, decks_vista as dv,  # noqa: E402
                      fases, loadout, sources, versoes)

CATALOGO = [
    ("Mox Opal", "som", "2010-10-01", 300.0, "Legendary Artifact"),
    ("Kappa Cannoneer", "unf", "2022-10-07", 20.0, "Artifact Creature — Turtle"),
    ("Pinnacle Emissary", "fra", "2026-09-29", 8.0, "Artifact Creature — Golem"),
    ("Wrath of God", "4ed", "1995-04-01", 15.0, "Sorcery"),
    ("Orcish Bowmasters", "ltr", "2023-06-23", 60.0, "Creature — Orc Archer"),
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.5, "Instant"),
    ("Birds of Paradise", "4ed", "1995-04-01", 9.0, "Creature — Bird"),
    ("Lantern of Insight", "som", "2010-10-01", 4.0, "Artifact"),
    # Em lista NENHUMA e em deck nenhum: é o controlo da RE (ver o caso).
    ("Pithing Needle", "som", "2010-10-01", 3.0, "Artifact"),
]
_ABERTAS = []

#: `ref -> [(board, nome, qty)]` das caixas.
LISTAS = {
    "MO": [("main", "Mox Opal", 4), ("main", "Kappa Cannoneer", 4),
           ("main", "Pinnacle Emissary", 4)],
    "EN": [("main", "Swords to Plowshares", 4)],
    "OA": [("main", "Swords to Plowshares", 4), ("main", "Birds of Paradise", 2)],
    "LG": [],
}

#: As listas de METAGAME que a base leva, por formato. `(archetype_id, cartas)`.
#: O cluster 1 e o 2 são as duas versões; o 3 joga Mox Opal e NÃO é versão
#: (não joga Pinnacle Emissary); o 4 é de Legacy e é quem segura a Bowmasters.
META = [
    ("modern", 1, [("Mox Opal", 4), ("Kappa Cannoneer", 4),
                   ("Pinnacle Emissary", 4)], 3),
    ("modern", 2, [("Mox Opal", 4), ("Kappa Cannoneer", 2),
                   ("Pinnacle Emissary", 4)], 2),
    ("modern", 3, [("Mox Opal", 4), ("Lantern of Insight", 4)], 4),
    ("legacy", 4, [("Orcish Bowmasters", 4), ("Swords to Plowshares", 2)], 6),
    ("legacy", 5, [("Birds of Paradise", 4)], 14),
]


def base():
    """Uma base com o catálogo mínimo, as caixas e as listas de metagame."""
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
        fmt = {"MO": "modern", "LG": "legacy"}.get(ref, "premodern")
        con.execute("INSERT INTO decks (name, format) VALUES (?, ?)", (ref, fmt))
        did = con.execute("SELECT id FROM decks WHERE name=?", (ref,)).fetchone()["id"]
        for board, nm, q in cards:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,?)", (did, nm, q, board))
    semear_meta(con)
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def semear_meta(con, extra=None):
    """As listas de metagame, com `archetype_id`. Datas DENTRO da janela do
    consenso para contarem como «joga-se hoje». Com `extra`, semeia SÓ essas —
    a base já tem as outras, e repeti-las dá `UNIQUE constraint`."""
    for fmt, aid, cartas, n in (list(extra) if extra else list(META)):
        con.execute("INSERT OR IGNORE INTO archetypes (id, format, label) "
                    "VALUES (?,?,?)", (aid, fmt, f"cluster {aid}"))
        for k in range(n):
            con.execute(
                """INSERT INTO decklists (format, source, source_key, event_name,
                   event_date, event_tier, event_players, player, archetype_id,
                   content_hash)
                   VALUES (?,?,?,?,?,'Challenge',64,?,?,?)""",
                (fmt, "mtgo", f"k{aid}-{k}", f"{fmt} Challenge", "2026-10-02",
                 f"j{aid}-{k}", aid, f"h{aid}-{k}"))
            did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
            for nm, q in cartas:
                con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                            " quantity, board) VALUES (?,?,?,'main')", (did, nm, q))


def copia(con, nm, sc, q=1):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção")
    con.commit()
    return cid


def fmt_de(rep, nome):
    return next(f for f in rep["formatos"] if f["formato"] == nome)


# ===========================================================================
# 1. UM DECK COM N VERSÕES, E NÃO N DECKS
# ===========================================================================
def caso_o_formato_tem_um_deck_com_versoes():
    """*"quero ficar com 1 deck e versoes do deck (como opcoes)"*.

    O Modern tem UM deck — «Affinity (Mox Opal)» — com duas versões por dentro,
    e não dois decks lado a lado. A versão escolhida está marcada e só UMA está.
    """
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "modern")
    u = f["deck_unico"]
    assert u, "o Modern tem de ter um deck único"
    assert u["nome"] == "Affinity (Mox Opal)", u["nome"]
    assert len(u["versoes"]) == 2, u["versoes"]
    esc = [v for v in u["versoes"] if v["escolhida"]]
    assert len(esc) == 1, esc
    assert esc[0]["id"] == "versao:modern:alfa", esc

    # E o que CONTA como escolhido no formato é UMA só — a versão a montar.
    assert f["n_marcados"] == 1, f["n_marcados"]


def caso_um_formato_sem_modelo_fica_como_estava():
    """O Premodern — que ele não mexeu — continua com os seus decks e com a
    pergunta «queres montar este?» de sempre. O modelo é por formato."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "premodern")
    assert f["deck_unico"] is None, f["deck_unico"]
    assert f["n_marcados"] == 0
    assert any("data-quero" not in str(d) for d in f["decks"])
    # e marcar continua a valer
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04"})
    rep = dv.relatorio(con, sources.config())
    assert fmt_de(rep, "premodern")["n_marcados"] == 1


def caso_esvaziar_o_bloco_devolve_o_modelo_anterior():
    """O INTERRUPTOR, como o `venda.mostrar` e o `cartas_vigiadas`: sem o bloco,
    nada muda — o formato volta a ser uma lista de decks marcados à mão."""
    escreve_cfg(_substitui=("decks_por_formato",), decks_por_formato={},
                decks_montar={"caixa:mod": "2026-10-04"})
    con = base()
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "modern")
    assert f["deck_unico"] is None, f["deck_unico"]
    assert f["n_marcados"] == 1, f["n_marcados"]


# ===========================================================================
# 2. OS OUTROS QUE JOGAM A CARTA-CHAVE: FORA DA ESCOLHA, E NÃO DESAPARECEM
# ===========================================================================
def caso_os_outros_que_jogam_a_carta_ficam_a_vista():
    """*"Poe os cinco de fora MAS deixa-os visiveis"*.

    O cluster 3 joga Mox Opal e **não** é uma versão (não joga Pinnacle
    Emissary). Tem de aparecer na lista dos outros, com o teste do critério ao
    lado, e NUNCA desaparecer: a leitura dele é que manda.
    """
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    u = fmt_de(rep, "modern")["deck_unico"]
    ids = [o["arquetipo_id"] for o in u["outros"]]
    assert 3 in ids, ids
    # e as duas versões NÃO estão lá: já são o deck
    assert 1 not in ids and 2 not in ids, ids
    o = next(o for o in u["outros"] if o["arquetipo_id"] == 3)
    assert o["passa_criterio"] is False, o
    assert o["listas"] == 4, o
    # o critério diz-se carta a carta, com a percentagem
    cartas = {e["carta"]: e["pct"] for e in o["exige"]}
    assert cartas["Pinnacle Emissary"] == 0.0, cartas
    assert cartas["Kappa Cannoneer"] == 0.0, cartas


def caso_um_outro_que_PASSA_o_criterio_diz_que_passa():
    """Um cluster novo que jogue as três cartas passa o critério e **di-lo** —
    é assim que ele o pode incluir com um toque. Era o caso dos clusters 7400,
    7010 e 6491 da base a sério, que ficaram fora da escolha dele."""
    escreve_cfg()
    con = base()
    semear_meta(con, extra=[("modern", 9, [("Mox Opal", 4),
                                           ("Kappa Cannoneer", 4),
                                           ("Pinnacle Emissary", 4)], 2)])
    con.commit()
    u = dv.deck_unico(con, "modern", [], {}, sources.config())
    o = next(o for o in u["outros"] if o["arquetipo_id"] == 9)
    assert o["passa_criterio"] is True, o
    # DERIVADO da base: ninguém o escreveu no config e ele aparece sozinho.
    assert o["arquetipo_id"] not in [v.get("arquetipo_id")
                                     for v in versoes.versoes("modern")]


# ===========================================================================
# 3. UM DECK QUE SAIU CONTINUA CONSULTÁVEL
# ===========================================================================
def caso_um_deck_que_saiu_continua_consultavel():
    """**Nada se apaga** (a regra dele de 2026-09-09). O deck que saiu da
    escolha fica no registo, com as cartas e a razão — repor é tirar-lhe a
    marca."""
    cards = [["main", "Lantern of Insight", 4], ["main", "Mox Opal", 2]]
    escreve_cfg(
        decks_de_evento=[{"id": "deck:modern:lantern", "slug": "lantern",
                          "formato": "modern", "nome": "Lantern Control",
                          "_saiu": {"em": "2026-10-04",
                                    "porque": "nao joga Mox Opal"}}],
        listas_escolhidas={"deck:modern:lantern": {
            "nome": "Lantern Control", "formato": "modern", "cards": cards}})
    con = base()
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "modern")
    d = next(d for d in f["decks"] if d["id"] == "deck:modern:lantern")
    assert d["saiu"], "o deck tem de dizer que saiu"
    assert d["saiu"]["porque"] == "nao joga Mox Opal"
    assert d["rotulo_estado"] == versoes.TEXTO_SAIU, d["rotulo_estado"]
    # CONSULTÁVEL: a lista continua lá, com o total certo.
    assert not d["sem_lista"], "um deck que saiu não perde a lista"
    assert d["total"] == 6, d["total"]
    assert d["quero"] is False, "mas não é um deck que ele vai montar"


# ===========================================================================
# 4. O FORMATO POR DECIDIR RETÉM
# ===========================================================================
def _candidatos(con):
    res = loadout.report(con)
    return fases.candidatos(con, res, sources.config())


def caso_uma_staple_de_um_formato_por_decidir_nao_vai_a_venda():
    """*"Legacy ainda nao sei"*.

    A Orcish Bowmasters joga em 6 das 20 listas de Legacy (30 %), muito acima
    do corte de 5 %. Enquanto o Legacy estiver por decidir **não entra nas
    candidatas** — vender uma staple do formato antes de ele escolher o deck era
    obedecer à letra e desobedecer à intenção.
    """
    escreve_cfg()
    con = base()
    copia(con, "Orcish Bowmasters", "ltr", q=4)
    c = _candidatos(con)
    nms = {l["nm"] for l in c["linhas"]}
    assert "Orcish Bowmasters" not in nms, "a staple de Legacy não pode ir à venda"
    prot = [l for l in c["protegidas"] if l["nm"] == "Orcish Bowmasters"]
    assert prot and prot[0]["proteccao"] == fases.RLG, prot
    assert "Legacy" in prot[0]["motivo"] or "legacy" in prot[0]["motivo"], prot[0]
    assert c["por_proteccao"][fases.RLG]["copias"] == 4


def caso_decidido_o_formato_a_carta_passa_a_candidata():
    """A regra desliga-se SOZINHA no dia em que ele escolher o deck de Legacy —
    é por isso que é sem estado e não uma lista congelada no config."""
    escreve_cfg()
    con = base()
    copia(con, "Orcish Bowmasters", "ltr", q=4)
    assert "Orcish Bowmasters" not in {l["nm"] for l in _candidatos(con)["linhas"]}
    # ele decide o Legacy: tira o `por_decidir`
    escreve_cfg(decks_por_formato={"legacy": {"nome": "Legacy", "versoes": []}})
    assert versoes.formatos_por_decidir(sources.config()) == []
    nms = {l["nm"] for l in _candidatos(con)["linhas"]}
    assert "Orcish Bowmasters" in nms, "decidido o formato, a carta volta a poder vender-se"


def caso_abaixo_do_corte_nao_retem():
    """5 % é um corte e não um «joga em alguma lista»: uma carta avulsa do
    formato não segura nada. A Swords joga em 6 de 20 listas de Legacy (30 %) e
    retém; a Birds joga em 14 de 20 (70 %) e retém; uma carta que não joga lá
    não retém — e é isso que se mede aqui, com o corte subido."""
    escreve_cfg(decks_por_formato={"_corte_pct": 80.0})
    con = base()
    copia(con, "Orcish Bowmasters", "ltr", q=4)
    nms = {l["nm"] for l in _candidatos(con)["linhas"]}
    assert "Orcish Bowmasters" in nms, "a 80 % de corte, 30 % não retém"


# ===========================================================================
# 5 e 6. A VERSÃO ESCOLHIDA, E O QUE ELA MUDA (E O QUE NÃO MUDA)
# ===========================================================================
def caso_mudar_a_versao_recalcula_as_proprias_e_as_partilhadas():
    """Trocar de versão muda o que ele MONTA: a necessidade do formato, as
    faltas e a lista de próprias. É o gesto novo da página."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    f1 = fmt_de(rep, "modern")
    nec1 = f1["necessidade"]
    d1 = next(d for d in f1["decks"] if d["id"] == "caixa:mod")
    assert d1["quero"] is True, "a versão escolhida é a que ele monta"

    cfg = sources.config()
    versoes.escolher(cfg, "modern", "versao:modern:beta", hoje="2026-10-05")
    escreve_cfg(decks_por_formato=cfg["decks_por_formato"])
    rep2 = dv.relatorio(con, sources.config())
    f2 = fmt_de(rep2, "modern")
    nec2 = f2["necessidade"]

    assert nec1 != nec2, (nec1, nec2)
    # a alfa pede 3 cartas distintas e a beta 4 — a Wrath só existe na beta
    assert nec1["cartas"] == 3 and nec2["cartas"] == 4, (nec1, nec2)
    d2 = next(d for d in f2["decks"] if d["id"] == "versao:modern:beta")
    assert d2["quero"] is True
    d1b = next(d for d in f2["decks"] if d["id"] == "caixa:mod")
    assert d1b["quero"] is False, "só se monta uma versão de cada vez"

    # AS PRÓPRIAS mudaram, e medem-se pela função que a página usa.
    def proprias(rep, fmt):
        f = fmt_de(rep, fmt)
        d = rep["decks"][next(x["id"] for x in f["decks"] if x["quero"])]
        p = dv.proprias_e_partilhadas(d, dv.reparticao([d]))
        return {nm for _b, nm, _q in p["proprias"]}, p

    p1, _ = proprias(rep, "modern")
    p2, info2 = proprias(rep2, "modern")
    assert "Wrath of God" not in p1 and "Wrath of God" in p2, (p1, p2)
    # Com UM deck por formato não há nada partilhado DENTRO do formato — e isso
    # é uma consequência do modelo, não um descuido: ele monta uma versão.
    assert info2["partilhadas"] == [], info2["partilhadas"]


def caso_a_pagina_nao_recalcula_os_escolhidos_por_si():
    """A repartição da PÁGINA sai da mesma lista que o cabeçalho
    (`ids_escolhidos`), e não de um segundo cálculo pelas marcas à mão.

    Sem isto, num formato do modelo o `decks.dados` lia o `decks_montar` de
    ontem e a página desenhava próprias/partilhadas de decks que já não são a
    escolha — dois contadores ao lado, nenhum erro, e a página a discordar de
    si própria. É o padrão do `event_tier`.
    """
    # uma marca à mão NUM DECK QUE NÃO É A VERSÃO ESCOLHIDA
    escreve_cfg(decks_montar={"versao:modern:beta": "2026-10-04"})
    con = base()
    rep = dv.relatorio(con, sources.config())
    f = fmt_de(rep, "modern")
    assert f["ids_escolhidos"] == ["caixa:mod"], f["ids_escolhidos"]

    import decks                                              # noqa: PLC0415
    idx, _partes = decks.dados(con, sources.config())
    fx = next(x for x in idx["formatos"] if x["formato"] == "modern")
    assert fx["ids_escolhidos"] == ["caixa:mod"], fx["ids_escolhidos"]
    # e o Premodern, que está FORA do modelo, continua a obedecer à marca
    escreve_cfg(decks_montar={"caixa:pm-a": "2026-10-04"})
    rep = dv.relatorio(con, sources.config())
    assert fmt_de(rep, "premodern")["ids_escolhidos"] == ["caixa:pm-a"]


def caso_todas_as_versoes_continuam_protegidas():
    """A escolha muda o que ele MONTA, não o que ele GUARDA: as outras versões
    são opções do mesmo deck, e vendê-las por ele ter hoje a alfa escolhida era
    desfazer a opção.

    A Wrath of God só está na versão **não escolhida** — e mesmo assim não vai
    à venda.
    """
    escreve_cfg()
    con = base()
    copia(con, "Wrath of God", "4ed", q=3)
    c = _candidatos(con)
    assert "Wrath of God" not in {l["nm"] for l in c["linhas"]}
    prot = [l for l in c["protegidas"] if l["nm"] == "Wrath of God"]
    assert prot and prot[0]["proteccao"] == fases.RE, prot
    assert "escolheste" in prot[0]["motivo"], prot[0]["motivo"]


def caso_uma_carta_de_nenhum_deck_continua_a_ir_a_venda():
    """O controlo: a RE não protege tudo. Uma carta que não está em deck
    nenhum, não é terra protegida e não joga em lista nenhuma continua
    candidata — senão a regra tinha deixado de ser uma regra.

    **Não serve a Lantern of Insight**, e vale a pena saber porquê: ela está nas
    listas do cluster 3 e por isso a **R5** (jogada nos últimos 30 dias) já a
    segura — o controlo passaria a medir a R5 e não a RE.
    """
    escreve_cfg()
    con = base()
    copia(con, "Pithing Needle", "som", q=2)
    nms = {l["nm"] for l in _candidatos(con)["linhas"]}
    assert "Pithing Needle" in nms, nms


# ===========================================================================
# 9. O ENDPOINT RECUSA-SE EM CONDIÇÕES
# ===========================================================================
def caso_uma_versao_que_nao_existe_e_recusada():
    """Uma página aberta ontem no telemóvel ainda manda a lista de versões de
    ontem: é 409 (a excepção é `ValueError`), nunca 500 e nunca um silêncio."""
    escreve_cfg()
    cfg = sources.config()
    try:
        versoes.escolher(cfg, "modern", "versao:modern:nao-existe")
        raise AssertionError("tinha de recusar")
    except versoes.VersaoDesconhecida as e:
        assert isinstance(e, ValueError)
        assert "versao:modern:alfa" in str(e), str(e)
    try:
        versoes.escolher(cfg, "premodern", "versao:modern:alfa")
        raise AssertionError("um formato fora do modelo também recusa")
    except versoes.VersaoDesconhecida:
        pass


def caso_escolher_a_que_ja_la_esta_e_um_no_op():
    """Repetir não reescreve a data: um clique sem efeito não pode parecer uma
    decisão nova no histórico (a regra do `precos.gravar_fonte`)."""
    escreve_cfg()
    cfg = sources.config()
    cfg["decks_por_formato"]["modern"]["versao_em"] = "2026-10-01"
    versoes.escolher(cfg, "modern", "versao:modern:alfa", hoje="2026-10-09")
    assert cfg["decks_por_formato"]["modern"]["versao_em"] == "2026-10-01"
    versoes.escolher(cfg, "modern", "versao:modern:beta", hoje="2026-10-09")
    assert cfg["decks_por_formato"]["modern"]["versao_em"] == "2026-10-09"


def caso_sem_escolha_escrita_vale_a_primeira():
    """Devolver vazio punha a página sem nada para abrir num formato que tem
    decks. A lista está ordenada por ele, logo a primeira é a resposta."""
    cfg = escreve_cfg()
    del cfg["decks_por_formato"]["modern"]["versao"]
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    assert versoes.versao_escolhida("modern") == "versao:modern:alfa"


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
