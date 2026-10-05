"""O MODERN SÃO TODOS OS DECKS DE MOX OPAL (André, 2026-10-05, à letra).

    *"no Modern, a unica coisa e que quero os decks que joguem Mox Opal, seja
    affinity, seja grinding station, seja outra coisa qualquer"*

**FECHA a dúvida que a ordem de 2026-10-04 à noite deixou aberta**, em que o
`criterio.exige` (Kappa Cannoneer + Pinnacle Emissary) escolhia quais os
clusters que eram versões e **cinco arquétipos ficaram «de fora, à espera de
confirmação»**. Ele confirmou o CONTRÁRIO do que lhe foi proposto: entram
todos. Em Modern a escolha passou a ser a MESMA pergunta que a protecção — um
critério só, *joga Mox Opal*.

E por isso o conjunto **não pode ser uma lista de `archetype_id` a martelo**: a
regra é permanente, e um arquétipo novo com a carta tem de entrar sozinho. Era
exactamente esse o defeito — daqui a uma semana havia um deck de Mox Opal de
fora e ninguém reparava.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_opal_todos.py`, que desliga uma peça de cada vez e exige
vermelho:

  1. **todo** o cluster que joga a carta-chave é versão, mesmo o que o `exige`
     recusava — é o inclusivo contra o selectivo;
  2. **o critério é permanente**: um cluster NOVO que apareça na base entra
     como versão sem se tocar no config;
  3. uma versão **conhecida sem listas na janela** diz que tem **zero** — é o
     Grinding Station, que ele deu como exemplo e que não tem uma única lista
     desde 29/09. Nem se esconde, nem conta como actual;
  4. uma lista a que o agrupamento não deu identidade **conta-se e diz-se** e
     nunca vira versão;
  5. a Affinity é a **principal**, e isso é um eixo distinto da escolhida;
  6. a caixa dos *«outros decks que jogam a carta»* **desapareceu** num formato
     derivado — era ela que guardava os cinco «à espera de confirmação»;
  7. o `versoes_todas` é o **interruptor**: o Pioneer, onde ele nomeou as três
     versões à mão, fica exactamente como estava (a caixa dos outros incluída);
  8. escolher uma versão **derivada** não é recusada com 409;
  9. um nome que venha da **etiqueta** do agrupamento diz que é etiqueta — não
     se inventa um nome com a cara de um nome verdadeiro;
 10. o motor da venda **não muda**: uma versão derivada não tem lista fixada e
     por isso não acrescenta nomes à RE;
 11. uma versão **sem lista fixada não é um deck de 0 %** no registo;
 12. o config A SÉRIO tem o Modern derivado, a Affinity principal e o Grinding
     Station como versão conhecida.

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

#: A janela do consenso do teste. Antes dela é «conhecido»; depois é «actual».
DESDE = "2026-10-01"
ANTES, DEPOIS = "2026-09-20", "2026-10-02"

CAIXAS = [
    {"slot": "mod", "nome": "Modern — Affinity", "formato": "modern",
     "fonte": "deck", "ref": "MO", "balde": "Colecção", "estado": "permanente",
     "prioridade": 1},
    {"slot": "pio", "nome": "Pioneer — Greasefang", "formato": "pioneer",
     "fonte": "deck", "ref": "PI", "balde": "Colecção", "estado": "permanente",
     "prioridade": 2},
]

#: As ANOTAÇÕES, que é o que a lista do config passou a ser num formato
#: derivado: o nome, o ponteiro para o deck, a marca `principal` e a memória
#: das conhecidas. O cluster 9 é o Grinding Station do teste — anotado, com
#: listas só ANTES da janela.
VERSOES_MOD = [
    {"id": "versao:modern:alfa", "arquetipo_id": 1, "nome": "Alfa",
     "listas": 6, "deck": "caixa:mod", "principal": True},
    {"id": "versao:modern:conhecida", "arquetipo_id": 9,
     "nome": "Grinding Station"},
]

CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "consenso": {"desde": DESDE},
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["modern", "pioneer"],
         "dedicado": True, "cartas_partilhadas": "rotativas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": {},
    "decks_por_formato": {
        "_corte_pct": 5.0,
        "_limiar_listas": 1,
        "modern": {
            "nome": "Affinity (Mox Opal)", "em": "2026-10-05",
            "criterio": {"carta": "Mox Opal", "protege_todas": True,
                         "versoes_todas": True},
            "versoes": VERSOES_MOD, "versao": "versao:modern:alfa",
        },
        # O Pioneer é o CONTROLO do interruptor: tem carta-chave, tem `exige`
        # e NÃO é derivado — ele nomeou as versões à mão.
        "pioneer": {
            "nome": "Greasefang", "em": "2026-10-04",
            "criterio": {"carta": "Greasefang, Okiba Boss",
                         "exige": ["Greasefang, Okiba Boss"], "pct_minima": 50},
            "versoes": [{"id": "versao:pioneer:a", "arquetipo_id": 6,
                         "nome": "A", "listas": 4, "deck": "caixa:pio"}],
            "versao": "versao:pioneer:a",
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

from mtgvault import (collection, db, decks_vista as dv,   # noqa: E402
                      loadout, scryfall, sources, versoes)

#: `(nome, set, data, preço, type_line)`
CATALOGO = [
    ("Mox Opal", "som", "2010-10-01", 300.0, "Legendary Artifact"),
    ("Kappa Cannoneer", "unf", "2022-10-07", 20.0, "Artifact Creature"),
    ("Pinnacle Emissary", "fra", "2026-09-29", 8.0, "Artifact Creature"),
    ("Scrabbling Claws", "dst", "2004-02-06", 2.0, "Artifact"),
    ("Grinding Station", "som", "2010-10-01", 7.0, "Artifact"),
    ("Emry, Lurker of the Loch", "eld", "2019-10-04", 9.0, "Legendary Creature"),
    ("Greasefang, Okiba Boss", "neo", "2022-02-18", 5.0, "Legendary Creature"),
    ("Parhelion II", "war", "2019-05-03", 4.0, "Legendary Artifact"),
]
_ABERTAS = []

LISTAS = {"MO": [("main", "Mox Opal", 4)], "PI": []}

#: `(formato, archetype_id, cartas, n, data)`
#:   1 — a versão anotada e PRINCIPAL (joga as duas do antigo `exige`)
#:   3 — joga Mox Opal e o `exige` RECUSAVA: é um dos cinco que ficaram de fora
#:   9 — o Grinding Station: anotado, e SÓ com listas antes da janela
#:   6 — Pioneer (o controlo do interruptor)
META = [
    ("modern", 1, [("Mox Opal", 4), ("Kappa Cannoneer", 4),
                   ("Pinnacle Emissary", 4)], 6, DEPOIS),
    ("modern", 3, [("Mox Opal", 4), ("Scrabbling Claws", 2)], 4, DEPOIS),
    ("modern", 9, [("Mox Opal", 4), ("Grinding Station", 3)], 5, ANTES),
    ("pioneer", 6, [("Greasefang, Okiba Boss", 4), ("Parhelion II", 2)], 4,
     DEPOIS),
]


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


def base():
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
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-04', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    for ref, cards in LISTAS.items():
        fmt = "modern" if ref == "MO" else "pioneer"
        con.execute("INSERT INTO decks (name, format) VALUES (?, ?)", (ref, fmt))
        did = con.execute("SELECT id FROM decks WHERE name=?",
                          (ref,)).fetchone()["id"]
        for board, nm, q in cards:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,?)", (did, nm, q, board))
    semear_meta(con)
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def ders(con, fmt="modern"):
    return versoes.versoes_derivadas(con, fmt, sources.config())


def por_aid(d):
    return {v["arquetipo_id"]: v for v in d["versoes"]}


# ---------------------------------------------------------------------------
def caso_todo_o_cluster_que_joga_a_carta_e_versao():
    """1. *"entram TODOS, Affinity ou nao."*

    O cluster 3 joga Mox Opal e o `exige` de 04/10 recusava-o — era um dos
    cinco que ficaram «de fora, à espera de confirmação». Hoje é versão.
    """
    escreve_cfg()
    con = base()
    d = ders(con)
    assert d["derivado"], d
    aids = set(por_aid(d))
    assert 3 in aids, (
        f"um cluster que joga a carta-chave TEM de ser versão, mesmo que não "
        f"jogue as cartas da Affinity: {aids}")
    assert 1 in aids, aids
    assert por_aid(d)[3]["na_janela"], por_aid(d)[3]


def caso_o_criterio_e_permanente_e_um_arquetipo_novo_entra_sozinho():
    """2. *"quando aparecer um arquetipo novo com Mox Opal, entra sozinho."*

    É O CASO QUE MOTIVOU A ORDEM. Com o conjunto escrito como lista de
    `archetype_id` no config, um deck novo de Mox Opal ficava de fora e ninguém
    reparava. Aqui semeia-se um cluster NOVO e **não se toca no config**.
    """
    escreve_cfg()
    con = base()
    antes = set(por_aid(ders(con)))
    assert 77 not in antes, antes
    semear_meta(con, [("modern", 77, [("Mox Opal", 4),
                                      ("Emry, Lurker of the Loch", 1)], 3,
                       DEPOIS)])
    con.commit()
    depois = por_aid(ders(con))
    assert 77 in depois, (
        f"o critério tem de ser PERMANENTE: um arquétipo novo com a carta-chave "
        f"entra sem ninguém escrever no config. Versões: {sorted(depois)}")
    v = depois[77]
    assert v["na_janela"] and v["listas"] == 3, v
    assert not v["anotada"], "não está no config, e não precisa de estar"
    assert v["id"] == versoes.id_derivado("modern", 77), v["id"]


def caso_uma_versao_conhecida_sem_listas_na_janela_diz_que_tem_zero():
    """3. O GRINDING STATION. *"Mostra-o como versao conhecida mas com 'zero
    listas na janela' bem visivel, nao o inventes como actual nem o escondas."*

    O cluster 9 só tem listas ANTES do corte. Fica na lista, com o zero dito e
    o total ao lado, e **não** no grupo do que se joga agora.
    """
    escreve_cfg()
    con = base()
    d = ders(con)
    v = por_aid(d).get(9)
    assert v, f"a versão conhecida não pode DESAPARECER: {sorted(por_aid(d))}"
    assert v["na_janela"] is False, v
    assert v["listas"] == 0, f"zero listas na janela, e di-lo: {v}"
    assert v["listas_total"] == 5, f"e o total ao lado, para não parecer que a "\
                                   f"carta nunca se jogou: {v}"
    assert v["nome"] == "Grinding Station", v
    # E a ORDEM põe-na depois das actuais: o que se joga agora vem primeiro.
    pos = [x["arquetipo_id"] for x in d["versoes"]]
    assert pos.index(9) > pos.index(1) and pos.index(9) > pos.index(3), pos


def caso_a_lista_sem_arquetipo_conta_se_e_nunca_vira_versao():
    """4. Uma versão precisa de uma identidade estável; uma lista sem cluster
    não tem nenhuma. Conta-se e diz-se — e o nome que a FONTE lhe dá também,
    porque «1 lista sem arquétipo» sozinho é informação a menos."""
    escreve_cfg()
    con = base()
    con.execute(
        """INSERT INTO decklists (format, source, source_key, event_name,
           event_date, event_tier, event_players, player, archetype_id,
           arquetipo_fonte, content_hash)
           VALUES ('modern','mtgtop8','sc-1','ev',?, 'Presencial',64,'x',NULL,
                   'Song of Creation','hsc')""", (DEPOIS,))
    did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
    con.execute("INSERT INTO decklist_cards (decklist_id, card_name, quantity,"
                " board) VALUES (?, 'Mox Opal', 4, 'main')", (did,))
    con.commit()
    d = ders(con)
    assert d["sem_cluster"] == 1, d["sem_cluster"]
    assert d["sem_cluster_nomes"] == ["Song of Creation"], d["sem_cluster_nomes"]
    assert None not in por_aid(d), "uma lista sem cluster não pode virar versão"


def caso_a_affinity_e_a_principal():
    """5. *"o deck principal e Affinity sem duvida"* (04/10).

    E é um eixo DISTINTO da versão escolhida: a escolhida muda com um toque, a
    principal é a identidade do deck e está escrita no config.
    """
    escreve_cfg()
    con = base()
    assert versoes.principal("modern") == "versao:modern:alfa"
    d = ders(con)
    assert por_aid(d)[1]["principal"] is True, por_aid(d)[1]
    assert not any(v["principal"] for v in d["versoes"]
                   if v["arquetipo_id"] != 1), d["versoes"]
    # Trocar a ESCOLHIDA não troca a principal.
    cfg = escreve_cfg()
    versoes.escolher(cfg, "modern", versoes.id_derivado("modern", 3),
                     hoje="2026-10-05", validas=[v["id"] for v in d["versoes"]])
    assert versoes.principal("modern", cfg) == "versao:modern:alfa", (
        "a principal não é a escolhida: são dois eixos")


def caso_a_caixa_dos_outros_que_jogam_desapareceu():
    """6. Era ela que guardava os cinco «de fora, à espera de confirmação» —
    a dúvida que ele fechou. Num formato derivado não há «outros»: quem joga a
    carta-chave É uma versão."""
    escreve_cfg()
    con = base()
    assert versoes.outros_que_jogam(con, "modern", sources.config()) == [], (
        "num formato derivado a caixa dos «outros» tem de ficar VAZIA, senão o "
        "mesmo arquétipo aparece como versão e como «não é versão»")


def caso_o_pioneer_fica_com_a_lista_fixa():
    """7. O `versoes_todas` é o INTERRUPTOR, e é chave própria e não o
    `protege_todas`: no Pioneer ele nomeou as três versões à mão."""
    escreve_cfg()
    con = base()
    assert not versoes.versoes_todas("pioneer")
    d = ders(con, "pioneer")
    assert d["derivado"] is False, d
    assert [v.get("nome") for v in versoes.versoes("pioneer")] == ["A"]
    # E a caixa dos «outros» continua inteira lá.
    assert versoes.outros_que_jogam(con, "pioneer", sources.config()) is not None
    # Tirar o `versoes_todas` ao Modern devolve-o ao comportamento antigo.
    bl = json.loads(json.dumps(CFG["decks_por_formato"]))
    bl["modern"]["criterio"].pop("versoes_todas")
    escreve_cfg(("decks_por_formato",), decks_por_formato=bl)
    assert ders(con)["derivado"] is False, "o interruptor tem de desligar"
    assert versoes.outros_que_jogam(con, "modern", sources.config()), (
        "desligado, a caixa dos «outros» volta")


def caso_escolher_uma_versao_derivada_nao_e_recusada():
    """8. A maior parte das versões não está escrita no config. Validar só
    contra o config recusava, com 409, um clique numa versão que a página
    acabou de desenhar."""
    escreve_cfg()
    con = base()
    d = ders(con)
    vid = versoes.id_derivado("modern", 3)
    cfg = escreve_cfg()
    # Sem a lista das válidas (o caminho antigo) é recusada, e isso é certo:
    # é o que protege os formatos de lista fixa.
    try:
        versoes.escolher(cfg, "modern", vid, hoje="2026-10-05")
        raise AssertionError("sem `validas` tinha de recusar")
    except versoes.VersaoDesconhecida:
        pass
    versoes.escolher(cfg, "modern", vid, hoje="2026-10-05",
                     validas=[v["id"] for v in d["versoes"]])
    assert cfg["decks_por_formato"]["modern"]["versao"] == vid
    # E uma que a página NÃO ofereceu continua a ser recusada.
    try:
        versoes.escolher(cfg, "modern", "versao:modern:a999", hoje="2026-10-05",
                         validas=[v["id"] for v in d["versoes"]])
        raise AssertionError("uma versão que não existe tinha de recusar")
    except versoes.VersaoDesconhecida:
        pass


def caso_um_nome_de_etiqueta_diz_que_e_etiqueta():
    """9. *"um nome inventado com o mesmo aspecto de um nome verdadeiro"* é o
    que custou três erros nesta semana (02/10). O cluster 3 não tem nome da
    fonte: mostra-se a etiqueta do agrupamento, MARCADA como etiqueta."""
    escreve_cfg()
    con = base()
    v = por_aid(ders(con))[3]
    assert v["origem_nome"] == "etiqueta", v
    assert v["nome"] == "cluster 3", v
    # O nome do config GANHA sempre: é dele.
    assert por_aid(ders(con))[1]["origem_nome"] == "config"
    # E um nome que a FONTE dê ganha à etiqueta.
    con.execute("UPDATE decklists SET arquetipo_fonte='Lantern Control' "
                "WHERE archetype_id=3")
    con.commit()
    v2 = por_aid(ders(con))[3]
    assert v2["nome"] == "Lantern Control", v2
    assert v2["origem_nome"] != "etiqueta", v2


def caso_o_motor_da_venda_nao_muda_com_as_versoes_derivadas():
    """10. Uma versão derivada não tem lista fixada, logo não acrescenta nomes
    à **RE** — e em Modern a protecção já é a **RP**, que é inclusiva. Se isto
    mudar, a lista de venda dele muda sem ninguém ter pedido."""
    escreve_cfg()
    con = base()
    res = loadout.report(con)
    antes = set(versoes.nomes_que_ficam(res, sources.config()))
    # A Scrabbling Claws é jogada SÓ pelo cluster 3 — uma versão derivada, sem
    # lista fixada. Se ela entrar na RE, a lista de venda dele mexe sem ninguém
    # ter pedido; quem a protege em Modern é a RP, que é outra regra.
    assert scryfall.chave("Scrabbling Claws") not in antes, (
        f"uma versão DERIVADA não tem lista fixada e não entra na RE: {antes}")
    semear_meta(con, [("modern", 78, [("Mox Opal", 4),
                                      ("Emry, Lurker of the Loch", 1)], 2,
                       DEPOIS)])
    con.commit()
    assert 78 in por_aid(ders(con)), "o cluster novo é versão"
    depois = set(versoes.nomes_que_ficam(loadout.report(con), sources.config()))
    assert scryfall.chave("Emry, Lurker of the Loch") not in depois, (
        f"nem uma versão derivada NOVA: {depois - antes}")
    assert antes == depois, (
        f"entraram {depois - antes}, saíram {antes - depois}")


def caso_uma_versao_sem_lista_fixada_nao_e_um_deck_de_zero_por_cento():
    """11. A lição da `modern-affinity` de 04/10: um deck a 0 % ao lado dos que
    ele vai montar lê-se como um deck que lhe falta tudo, quando o que se passa
    é que não há lista nenhuma. O Grinding Station não tem — de propósito."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    assert "versao:modern:conhecida" not in rep["decks"], (
        f"uma versão sem lista fixada não entra no registo como deck: "
        f"{sorted(rep['decks'])}")
    # Mas APARECE no selector de versões, que é onde a decisão se toma.
    u = dv.deck_unico(con, "modern", list(rep["decks"].values()), rep["pos"],
                      sources.config())
    v = next(x for x in u["versoes"] if x["arquetipo_id"] == 9)
    # E SEM o «ver ▶»: um botão para um deck que não existe é pior do que botão
    # nenhum. Apanhado a ler o HTML que o JS desenhou, não a raciocinar.
    assert v["deck"] == "", (
        f"a versão sem deck no registo não pode trazer um caminho para ele: {v}")
    # A versão que TEM lista fixada continua a trazê-lo.
    w = next(x for x in u["versoes"] if x["id"] == "versao:modern:alfa")
    assert w["deck"] == "caixa:mod", w


def caso_a_vista_separa_os_dois_grupos_e_conta_o_resto():
    """12. A vista leva o que a página precisa para dizer a verdade: o grupo, o
    `principal`, as listas sem arquétipo e os clusters de antes da janela."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    u = dv.deck_unico(con, "modern", list(rep["decks"].values()), rep["pos"],
                      sources.config())
    assert u["derivado"] is True
    assert u["principal"] == "versao:modern:alfa"
    agora = [v for v in u["versoes"] if v["na_janela"]]
    fora = [v for v in u["versoes"] if not v["na_janela"]]
    assert len(agora) == 2 and len(fora) == 1, (agora, fora)
    assert fora[0]["listas"] == 0 and fora[0]["listas_total"] == 5, fora
    assert u["desde"] == DESDE, u["desde"]
    assert "fora_da_janela" in u and "sem_cluster" in u, sorted(u)


def caso_o_config_a_serio_fechou_a_duvida():
    """13. O CONFIG A SÉRIO (2026-10-05).

    Lê o `colecao_config.json` do repositório: o Modern derivado, a Affinity
    principal, o Grinding Station como versão conhecida, e **a nota dos cinco
    «de fora, à espera de confirmação» apagada** — é essa a dúvida que ele
    fechou. Mais o `exige` arquivado em vez de apagado (a regra de 09/09).
    """
    from mtgvault import configio                            # noqa: PLC0415
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    m = cfg["decks_por_formato"]["modern"]
    assert m["criterio"]["versoes_todas"] is True, m["criterio"]
    assert m["criterio"]["carta"] == "Mox Opal"
    assert "exige" not in m["criterio"], (
        "o `exige` deixou de decidir quais os clusters que são versões")
    assert m["criterio"]["_exige_antes"]["exige"] == [
        "Kappa Cannoneer", "Pinnacle Emissary"], (
        "e NÃO se apagou: ficou arquivado com a data e a razão")
    assert "_fora_da_escolha" not in m, (
        "a nota que dizia que cinco arquétipos ficavam «de fora, à espera de "
        "confirmação» tem de SAIR: ele respondeu, e entram todos")
    por_id = {v["id"]: v for v in m["versoes"]}
    assert por_id["versao:modern:izzet-pinnacle"]["principal"] is True
    assert sum(1 for v in m["versoes"] if v.get("principal")) == 1
    gs = por_id["versao:modern:grinding-station"]
    assert gs["arquetipo_id"] == 7394 and gs["nome"] == "Grinding Station", gs
    assert "zero listas" in gs["_porque"].lower(), gs["_porque"]
    # O Legacy e o Pioneer NÃO foram arrastados: o `versoes_todas` é por formato.
    assert not cfg["decks_por_formato"]["legacy"]["criterio"].get("versoes_todas")
    assert not cfg["decks_por_formato"]["pioneer"]["criterio"].get("versoes_todas")
    assert cfg["decks_por_formato"]["legacy"]["versoes"] == [], (
        "em Legacy nada se escolheu para MONTAR, e isso não mudou")
    # A FORMA do ficheiro: um round-trip pelo `configio.escrever` devolve-o
    # igual BYTE A BYTE. É a lição do commit ac1f776 — um diff ilegível neste
    # ficheiro é a revisão a deixar de existir. Compara-se pelo `escrever` e
    # não pelo `texto`, porque é o `escrever` que faz a tradução de fim de
    # linha do Windows: comparar com o `texto` cru dava vermelho em todas as
    # linhas, por causa do `\r`.
    alvo = _TMP / "rt.json"
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
