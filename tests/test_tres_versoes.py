"""O MODERN FECHA EM TRES VERSOES (André, 2026-10-06, ao fim do dia, à letra).

    *"vou tentar ter correspondencia de decks em papel com os decks no MTGO"*
    *"entao modern sera o Izzet Affinity (Weapons) + Oswald + Versao com
    Cori-Steel Cutter"*

**ESTREITA o critério de 05/10** (*"qualquer deck com Mox Opal"*, que dava oito
clusters em seis famílias): as versões passam a ser **três, nomeadas**, e o
conjunto está ESCRITO no config. O critério *joga Mox Opal* continua inteiro
para a **PROTECÇÃO** — *"para MONTAR sao estas tres e so estas"*.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_tres_versoes.py`, que desliga uma peça de cada vez e exige
vermelho:

  1. o formato tem **UM deck com TRÊS versões nomeadas**, e já não derivadas;
  2. o **NÚCLEO COMUM** às três aparece em separado, com a básica marcada e as
     «em duas das três» à parte — *"e o argumento inteiro da correspondencia"*;
  3. a lista de uma versão **continua a dele** e as do META aparecem como
     **alternativas ao lado**, com o que cada uma tem a MAIS;
  4. a **AMBIGUIDADE** de uma carta com dois decks aparece com os **dois
     números** e nomeia o outro deck — *"NAO escolhas por ele"*;
  5. as **faltas por versão somam o total sem repetir o núcleo**: a carta comum
     conta UMA vez, e `só desta` + `partilhadas` fecham sempre o total;
  6. as versões que **saíram da escolha continuam consultáveis**, com ficha e
     caminho para a lista;
  7. uma **alternativa em DECK continua protegida pela RE** — era a lista do RC
     de Ghent, e sem isto perdia a protecção três dias antes do torneio;
  8. o universo de uma versão sai das **CARTAS** e não do `archetype_id`: um
     cluster novo não lhe mexe na contagem, e ela **nunca é órfã**;
  9. um cluster que **já é uma versão** não aparece também nos «outros»;
 10. as **FAMÍLIAS não se perderam**: mudaram para o bloco da protecção;
 11. uma lista que **não é de evento** diz a origem dela e não «sem lista»;
 12. o `_saiu` é o **interruptor**: tirar a marca devolve a versão à escolha;
 13. o **config A SÉRIO** tem as três versões, a escolhida, as seis saídas e a
     forma canónica.

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

#: A janela do consenso do teste.
DESDE = "2026-10-01"
ANTES, DEPOIS = "2026-09-20", "2026-10-02"

CAIXAS = [
    {"slot": "mod", "nome": "Modern — a tua lista", "formato": "modern",
     "fonte": "escolhido", "ref": "mod", "balde": "Colecção",
     "estado": "permanente", "prioridade": 1},
]

#: AS TRÊS VERSÕES NOMEADAS. Cada uma tem `meta.cartas` — o universo dela sai
#: das CARTAS e não do `archetype_id`, que é refeito todas as noites.
VERSOES = [
    {"id": "versao:modern:a", "nome": "Afa (Chave)",
     "deck": "deck:modern:qualifier", "principal": True,
     "meta": {"cartas": ["Chave", "Mox Opal"]},
     # A ALTERNATIVA EM DECK: a lista DELE, ao lado e não em vez da da versão.
     "alternativas": [{"deck": "caixa:mod", "rotulo": "a tua lista",
                       "_porque": "o deck do torneio"}]},
    {"id": "versao:modern:b", "nome": "Beta",
     "meta": {"cartas": ["Beta Fiddle"]}},
    {"id": "versao:modern:c", "nome": "Gama",
     "meta": {"cartas": ["Gama Cutter", "Mox Opal"],
              "ambiguidade": {"carta": "Gama Cutter",
                              "_porque": "a carta tem dois decks"}}},
    {"id": "versao:modern:saiu", "nome": "Saiu",
     "arquetipo_id": 9,
     "_saiu": {"em": "2026-10-06", "porque": "não é uma das três"}},
]

#: As cartas de cada lista. `Island` está nas TRÊS (é a básica do núcleo) e
#: `Mox Opal`/`Chave`… repartem-se para dar núcleo, «em duas» e só-de-uma.
L_QUALIFIER = [["main", "Mox Opal", 4], ["main", "Island", 1],
               ["main", "Chave", 4], ["main", "Comum Duas", 2],
               ["side", "So Da A", 2]]
L_CAIXA = [["main", "Mox Opal", 4], ["main", "Island", 1],
           ["main", "Chave", 4], ["side", "So Da Caixa", 1]]
L_B = [["main", "Mox Opal", 4], ["main", "Island", 2],
       ["main", "Beta Fiddle", 4], ["main", "Comum Duas", 1],
       ["side", "So Da B", 3]]
L_C = [["main", "Mox Opal", 4], ["main", "Island", 2],
       ["main", "Gama Cutter", 4], ["side", "So Da C", 1]]
L_SAIU = [["main", "Mox Opal", 4], ["main", "Saiu Carta", 3]]

CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "consenso": {"desde": DESDE},
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["modern"], "dedicado": True,
         "cartas_partilhadas": "dedicadas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [
        {"id": "deck:modern:qualifier", "slug": "qualifier",
         "nome": "Qualifier", "formato": "modern"},
    ],
    "listas_escolhidas": {
        "mod": {"nome": "Modern — a tua lista", "padrao": True,
                "origem": "a lista de qualificacao dele", "formato": "modern",
                "cards": L_CAIXA},
        "deck:modern:qualifier": {
            "nome": "Qualifier", "padrao": True, "origem": "o Qualifier",
            "formato": "modern", "cards": L_QUALIFIER,
            "evento": {"decklist_id": 101, "jogador": "Pil", "data": DEPOIS,
                       "evento": "Qualifier", "tier": "Qualifier"},
            "fonte_decklist": 101},
        # A LISTA DELE: sem `evento`, como o Oswald do config a sério (o
        # maindeck que ele deu mais o sideboard do consenso).
        "versao:modern:b": {"nome": "Beta", "padrao": True,
                            "origem": "a lista DELE, do deck manual",
                            "formato": "modern", "cards": L_B, "fonte_deck": 12},
        "versao:modern:c": {"nome": "Gama", "padrao": True,
                            "origem": "a presencial", "formato": "modern",
                            "cards": L_C,
                            "evento": {"decklist_id": 301, "jogador": "Ky",
                                       "data": DEPOIS, "evento": "RC",
                                       "tier": "Presencial", "jogadores": 449},
                            "fonte_decklist": 301},
        "versao:modern:saiu": {"nome": "Saiu", "padrao": True,
                               "origem": "a que saiu", "formato": "modern",
                               "cards": L_SAIU},
    },
    "decks_por_formato": {
        "_corte_pct": 5.0,
        "_limiar_listas": 1,
        "modern": {
            "nome": "Mox Opal", "em": "2026-10-06",
            "criterio": {
                "carta": "Mox Opal", "protege_todas": True,
                "familias": [
                    {"nome": "Gama", "cartas": ["Gama Cutter"]},
                    {"nome": "Beta", "cartas": ["Beta Fiddle"]},
                    {"nome": "Afa", "cartas": ["Chave"]},
                ],
            },
            "versoes": VERSOES, "versao": "versao:modern:a",
        },
    },
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(_substitui=(), **mudancas):
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

from mtgvault import (db, decks_vista as dv, loadout,        # noqa: E402
                      marcas, sources, versoes)

#: `(nome, set, data, preço, type_line)`
CATALOGO = [
    ("Mox Opal", "som", "2010-10-01", 300.0, "Legendary Artifact"),
    ("Chave", "fra", "2026-09-29", 8.0, "Artifact"),
    ("Beta Fiddle", "eld", "2019-10-04", 5.0, "Creature"),
    ("Gama Cutter", "fra", "2026-09-29", 3.0, "Artifact"),
    ("Comum Duas", "som", "2010-10-01", 2.0, "Artifact"),
    ("So Da A", "som", "2010-10-01", 1.0, "Artifact"),
    ("So Da B", "som", "2010-10-01", 1.5, "Artifact"),
    ("So Da C", "som", "2010-10-01", 2.5, "Artifact"),
    ("So Da Caixa", "som", "2010-10-01", 4.0, "Artifact"),
    ("Saiu Carta", "som", "2010-10-01", 6.0, "Artifact"),
    ("Outro Deck", "som", "2010-10-01", 9.0, "Artifact"),
    ("Island", "unh", "2004-11-19", 0.2, "Basic Land — Island"),
]
_ABERTAS = []

#: `(formato, archetype_id, cartas, n, data)` — o meta.
#:   1 — joga `Chave` + Mox Opal: o universo da versão A (3 listas)
#:   2 — joga `Beta Fiddle`: o universo da versão B (2 listas)
#:   3 — joga `Gama Cutter` + Mox Opal: o universo da versão C (1 lista)
#:   4 — joga `Gama Cutter` e NAO Mox Opal: a AMBIGUIDADE (7 listas)
#:   9 — o cluster da versão que SAIU
#:   5 — um deck que joga Mox Opal e não é versão nenhuma: os «outros»
META = [
    ("modern", 1, [("Mox Opal", 4), ("Chave", 4)], 3, DEPOIS),
    # O `Outro Deck` está aqui de propósito: é o que as listas do meta da versão
    # B têm **a MAIS** do que a lista dela, e sem uma carta a mais o caso das
    # alternativas não media a parte que ele pediu (*"a do jinavie tem o combo …
    # que a dele nao tem: vale a pena ele ver"*).
    ("modern", 2, [("Mox Opal", 4), ("Beta Fiddle", 4), ("Outro Deck", 1)], 2,
     DEPOIS),
    ("modern", 3, [("Mox Opal", 4), ("Gama Cutter", 4)], 1, DEPOIS),
    ("modern", 4, [("Gama Cutter", 4), ("Outro Deck", 2)], 7, DEPOIS),
    ("modern", 9, [("Mox Opal", 4), ("Saiu Carta", 3)], 2, DEPOIS),
    ("modern", 5, [("Mox Opal", 4), ("Outro Deck", 4)], 2, DEPOIS),
]

#: A POSSE do teste. Tem o NÚCLEO todo (Mox Opal, Island) e parte do resto, para
#: as faltas de cada versão serem diferentes entre si. A `Comum Duas` está a
#: ZERO de propósito: é ela que dá uma falta PARTILHADA por duas versões, e sem
#: uma o caso das três metades não media nada.
POSSE = {"Mox Opal": 4, "Island": 2, "Chave": 4, "Comum Duas": 0,
         "Beta Fiddle": 1, "Gama Cutter": 4, "So Da A": 0, "So Da B": 1,
         "So Da C": 0, "So Da Caixa": 1}


def pos_do_teste(extra=None):
    d = {nm: {"q": q, "origem": marcas.INVENTARIO}
         for nm, q in {**POSSE, **(extra or {})}.items()}
    return d


def semear_meta(con, extra=None):
    for fmt, aid, cartas, n, data in (list(extra) if extra else list(META)):
        con.execute("INSERT OR IGNORE INTO archetypes (id, format, label) "
                    "VALUES (?,?,?)", (aid, fmt, f"cluster {aid}"))
        for k in range(n):
            con.execute(
                """INSERT INTO decklists (format, source, source_key, event_name,
                   event_date, event_tier, event_players, player, archetype_id,
                   content_hash)
                   VALUES (?,?,?,?,?,'Challenge',64,?,?,?)""",
                (fmt, "mtgo", f"k{aid}-{k}-{data}", f"{fmt} evento", data,
                 f"j{aid}-{k}", aid, f"h{aid}-{k}-{data}"))
            did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
            for nm, q in cartas:
                con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                            " quantity, board) VALUES (?,?,?,'main')",
                            (did, nm, q))


def base(extra_meta=None):
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line,
               oracle_text, cmc, color_identity, finishes, released_at,
               legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,'',1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"modern": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-06', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    semear_meta(con, extra_meta)
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def unico(con, cfg=None, pos=None, fmt="modern"):
    cfg = cfg or sources.config()
    decks = dv.registo(con, cfg).get(fmt) or []
    return dv.deck_unico(con, fmt, decks, pos or pos_do_teste(), cfg)


def por_id(u):
    return {v["id"]: v for v in u["versoes"]}


# ---------------------------------------------------------------------------
def caso_o_formato_tem_um_deck_com_tres_versoes_nomeadas():
    """1. *"quero ficar com 1 deck e versoes do deck"* + *"entao modern sera o
    Izzet Affinity (Weapons) + Oswald + Versao com Cori-Steel Cutter"*.

    TRÊS versões, NOMEADAS, e o conjunto vem do CONFIG e já não da base: um
    quarto cluster que jogue a carta-chave já **não** entra como versão.
    """
    escreve_cfg()
    con = base()
    cfg = sources.config()
    assert not versoes.versoes_todas("modern", cfg), (
        "o derivado saiu: as versões passaram a ser as três do config")
    vs = versoes.versoes("modern", cfg)
    assert len(vs) == 3, [v["id"] for v in vs]
    assert [v["nome"] for v in vs] == ["Afa (Chave)", "Beta", "Gama"], vs
    u = unico(con)
    assert u["derivado"] is False, u["derivado"]
    assert len(u["versoes"]) == 3, [v["id"] for v in u["versoes"]]
    # O cluster 5 joga Mox Opal e NÃO é versão nenhuma — no modelo derivado era.
    assert 5 not in {v["arquetipo_id"] for v in u["versoes"]}, u["versoes"]
    assert u["versao"] == "versao:modern:a"
    assert u["principal"] == "versao:modern:a"


def caso_o_nucleo_comum_aparece_em_separado():
    """2. *"Mostra o nucleo em separado na pagina: e o que ele sleeva uma vez e
    serve as tres, e e o argumento inteiro da correspondencia"*.

    As cartas que estão nas TRÊS num bloco, as «em duas das três» noutro, e a
    básica MARCADA — ela está mesmo nos três decks mas sai da pilha a granel.
    """
    escreve_cfg()
    con = base()
    u = unico(con)
    n = u["nucleo"]
    assert n["versoes"] == 3, n
    nms = {l["nm"]: l for l in n["nucleo"]}
    assert set(nms) == {"Mox Opal", "Island"}, (
        f"o núcleo são as cartas que estão nas TRÊS versões: {sorted(nms)}")
    # A quantidade é o MÁXIMO: a versão A pede 1 Island e as outras 2.
    assert nms["Island"]["pede"] == 2, nms["Island"]
    assert nms["Island"]["da_pilha"] is True, (
        "a básica fica na lista e vai MARCADA — tirá-la era a conta a fechar "
        "por outro número")
    assert nms["Mox Opal"]["da_pilha"] is False
    assert n["cartas"] == 2 and n["copias"] == 6, n
    assert n["basicas"] == 1, n
    # AS «EM DUAS DAS TRÊS» À PARTE: `Comum Duas` está em A e em B.
    duas = {l["nm"] for l in n["em_duas"]}
    assert duas == {"Comum Duas"}, duas
    assert n["em_duas_n"] == 1, n
    # E uma carta que esteja só numa não entra em nenhuma das duas listas.
    assert "So Da A" not in nms and "So Da A" not in duas


def caso_a_lista_dele_fica_e_as_do_meta_sao_alternativas():
    """3. *"NAO o substituas por uma lista do meta: e a lista dele … Mostra-as
    como alternativas ao lado da dela, nao em vez dela"*.

    A versão B continua com as cartas DELA e as 2 listas do meta aparecem como
    alternativas, cada uma com o que tem **a MAIS** do que a dela — sem isso,
    duas listas do mesmo arquétipo lêem-se como a mesma coisa.
    """
    escreve_cfg()
    con = base()
    u = unico(con)
    b = por_id(u)["versao:modern:b"]
    # A LISTA É A DELE: as cartas do config, não as do meta.
    assert b["total"] == sum(q for _b, _n, q in L_B), b
    assert b["listas_meta"] == 2, b
    alt = [a for a in b["alternativas"] if a["origem"] == "meta"]
    assert len(alt) == 2, alt
    # O QUE CADA UMA TEM A MAIS — é esta a parte que ele pediu: *"a do jinavie
    # tem o combo … que a dele nao tem: vale a pena ele ver"*.
    for a in alt:
        assert a["extra"] == ["Outro Deck"], (
            f"a alternativa tem de dizer o que tem A MAIS do que a lista da "
            f"versão: {a}")
        assert a["extra_n"] == 1, a
        assert a["jogador"] and a["data"] == DEPOIS, a
    # A versão A tem uma alternativa em DECK — a lista dele, com ficha.
    a1 = por_id(u)["versao:modern:a"]
    d = [x for x in a1["alternativas"] if x["origem"] == "deck"]
    assert len(d) == 1 and d[0]["deck"] == "caixa:mod", d
    assert d[0]["rotulo"] == "a tua lista", d
    assert d[0]["total"] == sum(q for _b, _n, q in L_CAIXA), d
    assert d[0]["pct"] > 0, d


def caso_a_ambiguidade_aparece_com_os_dois_numeros():
    """4. *"CUIDADO COM A AMBIGUIDADE … Poe a alternativa a vista com os dois
    numeros (4 contra 100) e deixa-o decidir -- NAO escolhas por ele"*.

    OS DOIS números saem da base: com a carta-chave, e com a carta ambígua
    sozinha. E nomeia-se o OUTRO deck — sem ele, «as outras 100» não diz nada.
    """
    escreve_cfg()
    con = base()
    u = unico(con)
    c = por_id(u)["versao:modern:c"]
    a = c["ambiguidade"]
    assert a, "a versão com `meta.ambiguidade` tem de trazer os dois números"
    assert a["carta"] == "Gama Cutter"
    assert a["com"] == 1, (
        f"as listas que jogam Gama Cutter E Mox Opal: {a}")
    assert a["so_a_carta"] == 8, (
        f"as que jogam Gama Cutter, seja com que deck for: {a}")
    assert a["outras"] == 7, a
    assert a["outro"] and a["outro"]["listas"] == 7, a["outro"]
    assert a["outro"]["arquetipo_id"] == 4, a["outro"]
    # As versões SEM ambiguidade declarada não inventam nenhuma.
    assert por_id(u)["versao:modern:a"]["ambiguidade"] is None
    assert por_id(u)["versao:modern:b"]["ambiguidade"] is None


def caso_as_faltas_por_versao_somam_o_total_sem_repetir_o_nucleo():
    """5. *"as faltas por versao somam o total sem repetir o nucleo"*.

    Cada linha é o MÁXIMO que as versões pedem daquela carta, por isso a carta
    comum conta UMA vez; e `só desta` + `partilhadas` fecham sempre o total —
    a disciplina do `confirmado.metades`.
    """
    escreve_cfg()
    con = base()
    u = unico(con)
    f = u["faltas_versoes"]
    assert f, "com três versões com lista, as faltas saem"
    assert len(f["versoes"]) == 3, f["versoes"]
    # AS DUAS METADES FECHAM O TOTAL.
    so = sum(v["so"]["copias"] for v in f["versoes"])
    assert so + f["partilhadas"]["copias"] == f["totais"]["copias"], (
        f"«só desta» + «partilhadas» tem de fechar o total: {so} + "
        f"{f['partilhadas']['copias']} != {f['totais']['copias']}")
    so_c = sum(v["so"]["cartas"] for v in f["versoes"])
    assert so_c + f["partilhadas"]["cartas"] == f["totais"]["cartas"], (
        f"e o mesmo em CARTAS: {so_c} + {f['partilhadas']['cartas']} != "
        f"{f['totais']['cartas']}")
    # E O TOTAL NÃO REPETE O COMUM: a soma dos «se montares só esta» é MAIOR do
    # que o total, porque cada uma inclui as partilhadas.
    soma_isolada = sum(v["so_este"]["copias"] for v in f["versoes"])
    assert f["partilhadas"]["copias"] > 0, (
        "o fixture tem de ter uma falta partilhada, senão este caso não mede "
        "nada")
    assert soma_isolada > f["totais"]["copias"], (
        f"o total tem de ser MENOR do que a soma dos três sacos isolados: "
        f"{soma_isolada} vs {f['totais']['copias']}")
    # A carta do núcleo que ele TEM não aparece em falta nenhuma.
    nms = {l["nm"] for v in f["versoes"] for l in v["linhas"]}
    nms |= {l["nm"] for l in f["partilhadas"]["linhas"]}
    assert "Mox Opal" not in nms and "Island" not in nms, nms


def caso_as_que_sairam_continuam_consultaveis():
    """6. *"Nada se apaga -- as versoes que saem da escolha … ficam consultaveis
    como «meta, nao escolhido»"*.

    CONSULTÁVEL quer dizer com a ficha E com o caminho para a lista: até 06/10 o
    bloco das saídas tinha um resumo e **corpo nenhum**.
    """
    escreve_cfg()
    con = base()
    cfg = sources.config()
    # Fora da escolha…
    assert "versao:modern:saiu" not in {v["id"]
                                        for v in versoes.versoes("modern", cfg)}
    # …e DENTRO das saídas, com a razão.
    sai = versoes.versoes_saidas("modern", cfg)
    assert [v["id"] for v in sai] == ["versao:modern:saiu"], sai
    assert sai[0]["_saiu"]["porque"]
    # O DECK dela continua no registo (é por aí que se consulta) e com as cartas.
    reg = dv.registo(con, cfg)["modern"]
    d = next((x for x in reg if x["id"] == "versao:modern:saiu"), None)
    assert d is not None, (
        f"a versão que saiu tem de continuar a ser um deck do registo: "
        f"{[x['id'] for x in reg]}")
    assert len(d["cards"]) == len(L_SAIU), d
    assert d["rotulo_estado"] == versoes.TEXTO_SAIU, d["rotulo_estado"]
    # E a vista traz a FICHA: nome, conta e caminho.
    u = unico(con)
    s = next(x for x in u["saidas"] if x["id"] == "versao:modern:saiu")
    assert s["deck"] == "versao:modern:saiu" and s["total"] > 0, s
    assert s["em"] == "2026-10-06" and s["porque"], s
    # A carta dela continua PROTEGIDA pelo critério (RP): sair da escolha é sair
    # do que se MONTA, não do que se guarda.
    prot = versoes.nomes_protegidos(con, cfg)
    assert "saiu carta" in {k.lower() for k in prot}, (
        f"a carta de uma versão que saiu continua protegida pela RP: "
        f"{sorted(prot)[:12]}")


def caso_uma_alternativa_em_deck_continua_protegida_pela_re():
    """7. A LISTA DO RC DE GHENT NÃO PERDE A PROTECÇÃO.

    A lista de qualificação dele passou a ser a ALTERNATIVA «a tua lista» da
    versão da Affinity. Sem as alternativas em `decks_das_versoes`, ela saía de
    `ids_que_ficam` e perdia a **RE** três dias antes do torneio — e nada dava
    erro.
    """
    escreve_cfg()
    con = base()
    cfg = sources.config()
    ids = versoes.ids_que_ficam(cfg)
    assert "caixa:mod" in ids, (
        f"o deck de uma alternativa continua guardado pelo modelo: {sorted(ids)}")
    assert "deck:modern:qualifier" in ids, sorted(ids)
    res = loadout.report(con)
    nf = versoes.nomes_que_ficam(res, cfg)
    assert "so da caixa" in {k.lower() for k in nf}, (
        f"uma carta que SÓ a lista da alternativa joga tem de ficar na RE: "
        f"{sorted(nf)}")
    # E a versão que SAIU não entra na RE (é a semântica de 04/10).
    assert "versao:modern:saiu" not in ids, sorted(ids)


def caso_o_universo_sai_das_cartas_e_a_versao_nunca_e_orfa():
    """8. O `archetype_id` é refeito todas as noites e MUDA: em três dias
    seguidos (04, 05 e 06/10) as anotações do config ficaram com zero listas na
    janela, e o aviso da órfã disparou sobre o deck do RC de Ghent.

    Com o universo nas CARTAS, um cluster novo não lhe mexe na contagem e não há
    cluster para perder — por isso **nenhuma destas três pode aparecer órfã**.
    """
    escreve_cfg()
    con = base()
    u = unico(con)
    assert por_id(u)["versao:modern:a"]["listas_meta"] == 3, por_id(u)
    # NÃO HÁ CLUSTER PARA PERDER: é esta a razão estrutural, e sem ela o «nunca
    # é órfã» era uma coincidência do formato não ser derivado.
    for v in u["versoes"]:
        assert v["arquetipo_id"] is None, (
            f"uma versão ancorada nas CARTAS não tem `arquetipo_id`: {v['id']}")
        assert v["fixa"] is True, v
    assert u["orfas"] == [], u["orfas"]
    # O MESMO universo, com o agrupamento re-reparticionado: as listas do
    # cluster 1 passam para um cluster NOVO e a contagem da versão não mexe.
    con.execute("INSERT OR IGNORE INTO archetypes (id, format, label) "
                "VALUES (77,'modern','cluster novo')")
    con.execute("UPDATE decklists SET archetype_id = 77 WHERE archetype_id = 1")
    con.commit()
    u2 = unico(con)
    assert por_id(u2)["versao:modern:a"]["listas_meta"] == 3, (
        "a contagem da versão sai das CARTAS: mudar o cluster não lhe pode "
        "mexer")
    assert u2["orfas"] == [], u2["orfas"]


def caso_um_cluster_que_ja_e_versao_nao_aparece_nos_outros():
    """9. Com as versões ancoradas em cartas, a Affinity dele — 53 listas —
    aparecia ao mesmo tempo como versão 1 e como «outro deck que joga Mox
    Opal», no mesmo ecrã. Quem decide é a MAIORIA das listas do cluster."""
    escreve_cfg()
    con = base()
    u = unico(con)
    aids = {o["arquetipo_id"] for o in u["outros"]}
    for aid in (1, 2, 3):
        assert aid not in aids, (
            f"o cluster {aid} é o universo de uma versão e não pode aparecer "
            f"também nos «outros»: {sorted(x for x in aids if x)}")
    # O cluster 5 joga Mox Opal e NÃO é versão nenhuma: fica nos outros.
    assert 5 in aids, sorted(x for x in aids if x)
    # E conta-se quantos ficaram de fora por já serem versão.
    jv = next((o for o in u["outros"] if o.get("ja_e_versao")), None)
    assert jv and jv["ja_e_versao"] == 3, u["outros"]


def caso_as_familias_nao_se_perderam_e_mudaram_para_a_proteccao():
    """10. AS FAMÍLIAS MUDARAM DE SÍTIO E NÃO SE PERDERAM.

    Nasceram a 06/10 de manhã para tornar legível a lista de VERSÕES derivadas.
    Com o formato fechado em três nomeadas, o universo da PROTECÇÃO continua a
    ter as mesmas famílias — e deixá-las cair com o `versoes_todas` era apagar
    em silêncio um bloco que ele viu de manhã.
    """
    escreve_cfg()
    con = base()
    u = unico(con)
    fs = {f["nome"]: f["listas"] for f in u["familias_protege"]}
    assert fs, "as famílias do config continuam a ser mostradas, na protecção"
    assert fs.get("Gama") == 1 and fs.get("Beta") == 2 and fs.get("Afa") == 3, fs
    assert sum(fs.values()) == u["protege"]["listas"], (
        f"as famílias têm de somar as listas da protecção: {fs} vs "
        f"{u['protege']['listas']}")
    # Sem a chave no config NÃO há agrupamento — é o interruptor.
    cfg = escreve_cfg(decks_por_formato={
        **CFG["decks_por_formato"],
        "modern": {**CFG["decks_por_formato"]["modern"],
                   "criterio": {"carta": "Mox Opal", "protege_todas": True}}})
    assert versoes.familias_que_protegem(con, "modern", cfg) == []


def caso_uma_lista_que_nao_e_de_evento_diz_a_origem():
    """11. A versão B é a lista DELE (o maindeck que ele deu mais o sideboard do
    consenso) e a página dizia *«sem lista de evento fixada»* ao lado de 74
    cartas. Era verdade à letra e falso ao que ele lê: *«sem lista»*."""
    escreve_cfg()
    con = base()
    reg = dv.registo(con, sources.config())["modern"]
    b = next(x for x in reg if x["id"] == "versao:modern:b")
    assert "sem lista" not in b["nota"].lower(), (
        f"uma lista que não é de evento diz a ORIGEM dela: {b['nota']!r}")
    assert "lista DELE" in b["nota"], b["nota"]
    # E uma que TEM proveniência de evento continua a dizê-la.
    c = next(x for x in reg if x["id"] == "versao:modern:c")
    assert c["nota"].startswith("lista de evento real"), c["nota"]


def caso_o_saiu_e_o_interruptor():
    """12. Repor uma versão é tirar-lhe o `_saiu` — e nada mais."""
    con = base()
    escreve_cfg()
    assert len(versoes.versoes("modern", sources.config())) == 3
    vs = json.loads(json.dumps(VERSOES))
    for v in vs:
        v.pop("_saiu", None)
    cfg = escreve_cfg(decks_por_formato={
        **CFG["decks_por_formato"],
        "modern": {**CFG["decks_por_formato"]["modern"], "versoes": vs}})
    assert len(versoes.versoes("modern", cfg)) == 4, (
        "tirar o `_saiu` devolve a versão à escolha")
    assert versoes.versoes_saidas("modern", cfg) == []
    u = unico(con, cfg)
    assert len(u["versoes"]) == 4 and u["saidas"] == [], u["saidas"]


def caso_o_config_a_serio_tem_as_tres_versoes():
    """13. O CONFIG A SÉRIO (2026-10-06, ao fim do dia).

    As TRÊS versões nomeadas, a escolhida, as seis que saíram com a razão, o
    `versoes_todas` arquivado e **não apagado**, o `protege_todas` inteiro, e a
    FORMA canónica do ficheiro (a lição do commit `ac1f776`).
    """
    from mtgvault import configio                            # noqa: PLC0415
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    m = cfg["decks_por_formato"]["modern"]
    fica = [v for v in m["versoes"] if not v.get("_saiu")]
    sai = [v for v in m["versoes"] if v.get("_saiu")]
    assert [v["nome"] for v in fica] == [
        "Izzet Affinity (Weapons)", "Oswald", "Cori-Steel Cutter"], (
        [v["nome"] for v in fica])
    assert len(sai) == 6, [v["id"] for v in sai]
    for v in sai:
        assert v["_saiu"]["em"] == "2026-10-06" and v["_saiu"]["porque"], v
    assert m["versao"] == "versao:modern:izzet-affinity-weapons", m["versao"]
    # O UNIVERSO DE CADA UMA SAI DAS CARTAS — nenhuma das três tem cluster.
    for v in fica:
        assert v.get("arquetipo_id") is None, (
            f"uma versão ancorada em cartas não tem `arquetipo_id`: {v['id']}")
        assert v["meta"]["cartas"], v
    por = {v["id"]: v for v in fica}
    assert por["versao:modern:izzet-affinity-weapons"]["meta"]["cartas"] == [
        "Weapons Manufacturing", "Mox Opal"]
    assert por["versao:modern:oswald"]["meta"]["cartas"] == ["Oswald Fiddlebender"]
    cs = por["versao:modern:cori-steel"]["meta"]
    assert cs["cartas"] == ["Cori-Steel Cutter", "Mox Opal"]
    assert cs["ambiguidade"]["carta"] == "Cori-Steel Cutter", cs
    # A LISTA DELE fica ao lado e não em vez: a caixa `modern` é a alternativa.
    alt = por["versao:modern:izzet-affinity-weapons"]["alternativas"]
    assert [a["deck"] for a in alt] == ["caixa:modern"], alt
    assert "Ghent" in alt[0]["rotulo"], alt[0]
    # A LISTA DO OSWALD É A DELE, copiada do deck 12 e não uma do meta.
    osw = cfg["listas_escolhidas"]["versao:modern:oswald"]
    assert osw["fonte_deck"] == 12 and len(osw["cards"]) == 34, len(osw["cards"])
    assert "evento" not in osw, "a lista dele não é de evento nenhum"
    # A do Cori-Steel é a presencial do Kody Lyons.
    csl = cfg["listas_escolhidas"]["versao:modern:cori-steel"]
    assert csl["evento"]["decklist_id"] == 25051, csl["evento"]
    assert csl["evento"]["jogadores"] == 449, csl["evento"]
    # A versão `izzet-pinnacle` foi ARQUIVADA e não apagada.
    assert m["_versao_izzet_pinnacle_antes"]["entrada"]["id"] == \
        "versao:modern:izzet-pinnacle"
    # A FORMA do ficheiro: round-trip igual BYTE A BYTE.
    alvo = _TMP / "rt-tres.json"
    configio.escrever(cfg, alvo)
    assert alvo.read_bytes() == (RAIZ / "colecao_config.json").read_bytes(), (
        "o `colecao_config.json` saiu da forma canónica do `configio.escrever`")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    maus = 0
    for c in CASOS:
        try:
            c()
            print(f"  ok   {c.__name__}")
        except Exception as e:                                # noqa: BLE001
            maus += 1
            print(f"  FAIL {c.__name__}: {type(e).__name__}: {e}")
    print(f"{len(CASOS) - maus}/{len(CASOS)} ok")
    sys.exit(1 if maus else 0)
