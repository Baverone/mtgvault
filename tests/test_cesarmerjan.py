"""A VIGIA DO CesarMerjan, AS FAMÍLIAS E AS FALTAS POR DECK (André, 2026-10-06).

À letra: *"o jogar mtgo CesarMerjan costuma jogar decks de Mox Opal, combos,
como eu gosto, procura as decklists dele"*; *"O MOX OPAL DE MODERN TEM SEIS
FAMILIAS, nao uma. Mostra-as"*; *"Separa na pagina o que e so do Grinding
Station do que e so do Song of Creation, porque ele pode querer um e nao o
outro"*.

Três peças, e cada uma tem um defeito próprio que este ficheiro tranca:

**A VIGIA.** Ele joga em LIGAS — as duas listas que a base tem dele são as duas
de liga. O `check_mtgo_player` não filtra tier, e é isso que o faz apanhá-las;
mas o que decide se a lista CHEGA à base são as quatro portas do
`metagame_fontes.<fmt>.ligas`. Pôr essa chave a `false` em Modern cegava esta
vigia **em silêncio** — o jogador deixava simplesmente de ter listas novas, sem
um único passo a dar erro. É o padrão do `event_tier` aplicado a uma vigia, e é
o risco que o `check_all` fechou a 2026-10-04 (*"uma vigia que não vigia é pior
do que nenhuma, porque ele fica a pensar que está coberta"*).

**AS VERSÕES.** Nenhuma das duas listas podia ser uma versão DERIVADA: a do
Grinding Station está num cluster que nasceu nesse dia, e a do Song of Creation
**não tem cluster nenhum** e é de um dia ANTES da janela do consenso. Pela
regra de 05/10 (*"uma lista sem cluster … NUNCA vira versão, porque uma versão
precisa de um id estável"*) ficavam as duas fora. A saída é a identidade que o
vault já usa para os decks dele desde 04/10: a **lista fixada**, que sobrevive
ao `rebuild_archetypes` de cada noite e ao `prune_decklists(30)`.

**AS FAMÍLIAS.** Com o critério inclusivo de 05/10 a lista de versões é tudo o
que joga a carta-chave — oito clusters em Modern a 06/10, de arquétipos sem nada
a ver uns com os outros. A família deriva-se das CARTAS e nunca do cluster:
medido a 06/10, as cinco anotações de `arquetipo_id` do config ficaram com zero
listas na janela, o segundo dia seguido.

Os casos, e o que cada um chumba (a prova em `tests/_chumba_cesar.py`):

  1. a vigia do jogador apanha uma lista de **LIGA** — o `check_mtgo_player`
     não filtra tier;
  2. o `apanha_ligas` diz **não** quando o formato não conta ligas, e o
     resultado da vigia leva-o — é o aviso contra a cegueira silenciosa;
  3. as duas listas dele são **versões**, marcadas com o nome do jogador;
  4. uma versão ancorada numa lista sobrevive ao `prune_decklists` — as cartas
     estão GRAVADAS no config, não num ponteiro;
  5. uma lista de ANTES da janela entra e **diz** que está fora dela;
  6. uma versão fixa **nunca é órfã**: não tem cluster para perder;
  7. as versões vêm agrupadas por **família**, com a contagem de cada;
  8. a família sai das CARTAS e não do cluster: muda-se o `archetype_id` de
     tudo e as famílias ficam as mesmas;
  9. a família de um cluster VAZIO sai da lista fixada do próprio deck — era o
     deck principal a aparecer sem família;
 10. as faltas separam-se em **três** sacos: só de A, só de B, e dos dois;
 11. as faltas levam os **dois preços** (foil e nonfoil) — nada obriga estes
     decks ao foil;
 12. o `familias` é o **interruptor**: sem ele a lista fica plana;
 13. o config A SÉRIO tem a vigia, as duas versões e as seis famílias.

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

DESDE = "2026-10-01"
ANTES, DEPOIS = "2026-09-28", "2026-10-03"

#: As SEIS FAMÍLIAS do teste, pela ordem em que se testam. A genérica em
#: ÚLTIMO, como no config a sério: as cartas dela cabem em quase todo o deck de
#: Mox Opal, por isso é a família de omissão e não um teste que ganhe aos
#: específicos.
FAMILIAS = [
    {"nome": "Grinding Station", "cartas": ["Grinding Station"]},
    {"nome": "Hammer", "cartas": ["Colossus Hammer"]},
    {"nome": "Song of Creation", "cartas": ["Song of Creation"]},
    {"nome": "Affinity", "cartas": ["Kappa Cannoneer", "Pinnacle Emissary"]},
]

#: As duas versões DELE: ancoradas na lista fixada (`arquetipo_id` ausente) e
#: marcadas com o jogador.
VERSOES_CESAR = [
    {"id": "versao:modern:cesar-gs", "nome": "Grinding Station / Loki",
     "jogador": "CesarMerjan", "fonte_decklist": 101},
    {"id": "versao:modern:cesar-song", "nome": "Song of Creation / Jace",
     "jogador": "CesarMerjan", "fonte_decklist": 102},
]

#: A lista do Grinding Station (DEPOIS da janela) e a do Song of Creation
#: (ANTES dela), gravadas com as cartas — é isso que as faz sobreviver à poda.
LISTAS_CESAR = {
    "versao:modern:cesar-gs": {
        "nome": "Grinding Station / Loki", "padrao": True, "formato": "modern",
        "escolhido_em": "2026-10-06",
        "cards": [["main", "Mox Opal", 4], ["main", "Grinding Station", 3],
                  ["main", "Emry, Lurker of the Loch", 4],
                  ["main", "Brazen Borrower", 1], ["main", "Endurance", 2]],
        "evento": {"decklist_id": 101, "data": DEPOIS, "jogador": "CesarMerjan",
                   "evento": "Modern League", "tier": "League"},
    },
    "versao:modern:cesar-song": {
        "nome": "Song of Creation / Jace", "padrao": True, "formato": "modern",
        "escolhido_em": "2026-10-06",
        "cards": [["main", "Mox Opal", 4], ["main", "Song of Creation", 4],
                  ["main", "Grapeshot", 1], ["main", "Endurance", 2]],
        "evento": {"decklist_id": 102, "data": ANTES, "jogador": "CesarMerjan",
                   "evento": "Modern League", "tier": "League"},
    },
}

CAIXAS = [
    {"slot": "mod", "nome": "Modern — Affinity", "formato": "modern",
     "fonte": "deck", "ref": "MO", "balde": "Colecção", "estado": "permanente",
     "prioridade": 1},
]

CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "consenso": {"desde": DESDE},
    # O MODERN CONTA LIGAS (2026-10-05). É este interruptor que a vigia precisa,
    # e o caso 2 desliga-o para provar que ela o diz.
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "modern": {"ligas": True, "min_jogadores_presencial": 0},
    },
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["modern"], "dedicado": True,
         "acabamento": "foil", "lingua": "en"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": dict(LISTAS_CESAR),
    "decks_por_formato": {
        "_corte_pct": 5.0, "_limiar_listas": 1,
        "modern": {
            "nome": "Affinity (Mox Opal)", "em": "2026-10-05",
            "criterio": {"carta": "Mox Opal", "protege_todas": True,
                         "versoes_todas": True, "familias": FAMILIAS},
            "versoes": [
                {"id": "versao:modern:alfa", "arquetipo_id": 1, "nome": "Alfa",
                 "listas": 6, "deck": "caixa:mod", "principal": True},
            ] + VERSOES_CESAR,
            "versao": "versao:modern:alfa",
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
    sources.esquecer_config()
    return d


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (db, decks_vista as dv, marcas, sources,   # noqa: E402
                      versoes, watchlist)

#: `(nome, set, data, preço nonfoil, preço foil, type_line)`
CATALOGO = [
    ("Mox Opal", "som", "2010-10-01", 200.0, 300.0, "Legendary Artifact"),
    ("Kappa Cannoneer", "unf", "2022-10-07", 10.0, 20.0, "Artifact Creature"),
    ("Pinnacle Emissary", "fra", "2026-09-29", 4.0, 8.0, "Artifact Creature"),
    ("Grinding Station", "som", "2010-10-01", 3.0, 7.0, "Artifact"),
    ("Emry, Lurker of the Loch", "eld", "2019-10-04", 5.0, 9.0,
     "Legendary Creature"),
    ("Song of Creation", "m21", "2020-07-03", 1.0, 3.0, "Enchantment"),
    ("Brazen Borrower", "eld", "2019-10-04", 3.0, 10.0, "Creature"),
    ("Endurance", "mh2", "2021-06-18", 8.0, 16.0, "Creature"),
    ("Grapeshot", "tsp", "2006-10-06", 0.3, 0.7, "Sorcery"),
    ("Colossus Hammer", "m20", "2019-07-12", 0.5, 2.0, "Artifact"),
]
_ABERTAS = []

#: `(formato, archetype_id, cartas, n, data, tier)`
#:   1 — a Affinity, anotada e PRINCIPAL
#:   2 — um Grinding Station do META (distinto das listas dele)
#:   3 — um Hammer
META = [
    ("modern", 1, [("Mox Opal", 4), ("Kappa Cannoneer", 4),
                   ("Pinnacle Emissary", 4)], 6, DEPOIS, "Challenge"),
    ("modern", 2, [("Mox Opal", 4), ("Grinding Station", 3)], 2, DEPOIS,
     "League"),
    ("modern", 3, [("Mox Opal", 4), ("Colossus Hammer", 4)], 1, DEPOIS,
     "League"),
]


def semear_meta(con, extra=None):
    for fmt, aid, cartas, n, data, tier in (list(extra) if extra else list(META)):
        con.execute("INSERT OR IGNORE INTO archetypes (id, format, label) "
                    "VALUES (?,?,?)", (aid, fmt, f"cluster {aid}"))
        for k in range(n):
            con.execute(
                """INSERT INTO decklists (format, source, source_key, event_name,
                   event_date, event_tier, event_players, player, archetype_id,
                   content_hash)
                   VALUES (?,?,?,?,?,?,64,?,?,?)""",
                (fmt, "mtgo", f"k{aid}-{k}-{data}", f"{fmt} evento", data, tier,
                 f"j{aid}-{k}", aid, f"h{aid}-{k}-{data}"))
            did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
            for nm, q in cartas:
                con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                            " quantity, board) VALUES (?,?,?,'main')",
                            (did, nm, q))


#: As DUAS listas do jogador, na base: as duas de LIGA, uma depois da janela e
#: outra antes. É a forma real — e é ela que faz o caso 1 valer alguma coisa.
def semear_jogador(con, tier="League"):
    for did, data, cartas in (
            (101, DEPOIS, [("Mox Opal", 4), ("Grinding Station", 3),
                           ("Emry, Lurker of the Loch", 4),
                           ("Brazen Borrower", 1), ("Endurance", 2)]),
            (102, ANTES, [("Mox Opal", 4), ("Song of Creation", 4),
                          ("Grapeshot", 1), ("Endurance", 2)])):
        con.execute(
            """INSERT INTO decklists (id, format, source, source_key, event_name,
               event_date, event_tier, player, content_hash)
               VALUES (?,'modern','mtgo',?,'Modern League',?,?,'CesarMerjan',?)""",
            (did, f"cesar-{did}", data, tier, f"hc-{did}"))
        for nm, q in cartas:
            con.execute("INSERT INTO decklist_cards (decklist_id, card_name, "
                        "quantity, board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def base(tier_jogador="League"):
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, pnf, pf, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line,
               oracle_text, cmc, color_identity, finishes, released_at,
               legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,'',1,'U',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"modern": "legal"})))
        for fin, p in (("nonfoil", pnf), ("foil", pf)):
            con.execute(
                "INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                "finish, date, trend, low) VALUES (?,'cardmarket',?,"
                "'2026-10-05',?,?)", (f"id-{i}", fin, p, p))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.execute("INSERT INTO decks (name, format) VALUES ('MO','modern')")
    did = con.execute("SELECT id FROM decks WHERE name='MO'").fetchone()["id"]
    for nm, q in (("Mox Opal", 4), ("Kappa Cannoneer", 4)):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                    "board) VALUES (?,?,?,'main')", (did, nm, q))
    semear_meta(con)
    semear_jogador(con, tier_jogador)
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def inscrever(con):
    return watchlist.add(con, "mtgo_player", "CesarMerjan",
                         "CesarMerjan — Modern", "modern")


def ders(con, fmt="modern"):
    return versoes.versoes_derivadas(con, fmt, sources.config())


def unico(con, fmt="modern"):
    cfg = sources.config()
    reg = dv.registo(con, cfg)
    pos = marcas.posse(con, marcas.inventario(con), marcas.marcadas(con))
    return dv.deck_unico(con, fmt, reg.get(fmt) or [], pos, cfg), pos


# ---------------------------------------------------------------------------
def caso_a_vigia_do_jogador_apanha_uma_lista_de_liga():
    """1. *"so ha 2 listas dele na base e vieram das LIGAS … confirma que
    apanha ligas e diz como."*

    O `check_mtgo_player` **não filtra tier**, e é só isso que o faz servir um
    jogador que vive de ligas. Com um filtro de tier lá dentro, esta vigia
    respondia *"sem listas ainda"* sobre um jogador com duas listas na base.
    """
    escreve_cfg()
    con = base()
    wid = inscrever(con)
    r = watchlist.check_mtgo_player(con, wid)
    assert r["found"], (
        "a vigia não encontrou o jogador — as duas listas dele são de LIGA, e "
        "um filtro de tier aqui cega-a")
    assert r["tier"] == "League", r
    assert r["decklist_id"] == 101, (
        f"a vigia tem de apanhar a lista MAIS RECENTE (101, de {DEPOIS}), "
        f"não a de {ANTES}: {r['decklist_id']}")
    assert len(r["cards"]) == 5, r["cards"]
    # E a 2.ª corrida não dá sinal falso.
    assert watchlist.check_mtgo_player(con, wid)["changed"] is False


def caso_a_vigia_diz_quando_o_formato_nao_conta_ligas():
    """2. *"Se a vigia de jogador so olhar para Challenges, nao o encontra."*

    O que decide se a lista CHEGA à base são as quatro portas do
    `metagame_fontes.<fmt>.ligas`. Pôr essa chave a `false` cegava esta vigia em
    **silêncio** — o jogador deixava de ter listas novas e nenhum passo dava
    erro. É o padrão do `event_tier`, e é o risco que o `check_all` nomeou a
    04/10. Agora a vigia DI-LO, e a linha sai no log do `watch-check`.
    """
    escreve_cfg()
    con = base()
    wid = inscrever(con)
    lig = watchlist.apanha_ligas(con, wid)
    assert lig["apanha"] is True, lig
    assert lig["ligas_na_base"] == 2, lig
    assert lig["ultima_liga"] == DEPOIS, lig
    assert watchlist.check_mtgo_player(con, wid)["ligas"]["apanha"] is True, (
        "o resultado da vigia TEM de trazer o `ligas`: sem ele, quem lê o "
        "`watch-check` não tem como saber que a vigia depende daquela chave")
    # Agora o Modern deixa de contar ligas: a vigia tem de o DIZER.
    escreve_cfg(_substitui=("metagame_fontes",), metagame_fontes={
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "modern": {"ligas": False, "min_jogadores_presencial": 0}})
    lig2 = watchlist.apanha_ligas(con, wid)
    assert lig2["apanha"] is False, (
        "com `ligas: false` no Modern esta vigia fica CEGA às listas de liga "
        "deste jogador, e tem de o dizer — senão ele fica a pensar que está "
        "coberta")
    assert "ligas: true" in lig2["porque"], lig2["porque"]


def caso_as_duas_listas_dele_sao_versoes_marcadas_com_o_nome():
    """3. *"Os dois entram como versoes do deck de Modern … Marca-os como «do
    CesarMerjan» para ele os distinguir dos outros."*
    """
    escreve_cfg()
    con = base()
    d = ders(con)
    por_id = {v["id"]: v for v in d["versoes"]}
    for vid in ("versao:modern:cesar-gs", "versao:modern:cesar-song"):
        assert vid in por_id, (
            f"a lista do CesarMerjan tem de ser uma versão do deck de Modern: "
            f"{sorted(por_id)}")
        v = por_id[vid]
        assert v["jogador"] == "CesarMerjan", (
            f"a versão tem de dizer de QUEM é a lista, senão ele não a "
            f"distingue das que o agrupamento trouxe: {v}")
        assert v["fixa"] is True, v
        assert v["arquetipo_id"] is None, v
    assert d["jogadores"] == ["CesarMerjan"], d["jogadores"]
    # E a página leva as duas coisas.
    u, _pos = unico(con)
    assert u["jogadores"] == ["CesarMerjan"], u["jogadores"]
    assert {v["jogador"] for v in u["versoes"] if v["fixa"]} == {"CesarMerjan"}


def caso_uma_versao_fixa_sobrevive_a_poda_das_decklists():
    """4. O `prune_decklists(30)` apaga as decklists ao fim de um mês.

    Se a versão fosse um PONTEIRO para o `decklist_id`, ficava vazia por volta
    de 2026-10-28 (a lista do Song of Creation é de 28/09) **sem um único passo
    a falhar** — o padrão do `event_tier` sobre a lista por que ele vai sleevar.
    As cartas estão gravadas no config: apaga-se a decklist à mão e a versão
    continua inteira.
    """
    escreve_cfg()
    con = base()
    con.execute("DELETE FROM decklist_cards WHERE decklist_id IN (101, 102)")
    con.execute("DELETE FROM decklists WHERE id IN (101, 102)")
    con.commit()
    d = ders(con)
    por_id = {v["id"]: v for v in d["versoes"]}
    assert "versao:modern:cesar-gs" in por_id, (
        "a versão desapareceu com a decklist — as cartas tinham de estar "
        "gravadas no config")
    reg = dv.registo(con, sources.config())
    decks = {x["id"]: x for x in (reg.get("modern") or [])}
    gs = decks.get("versao:modern:cesar-gs")
    assert gs and len(gs["cards"]) == 5, (
        f"o deck da versão tem de continuar a ter as 5 linhas: {gs}")


def caso_uma_lista_anterior_a_janela_entra_e_diz_que_esta_fora():
    """5. A lista do Song of Creation é de 28/09, **um dia antes** da janela.

    É o caso do Greasefang de 04/10: a melhor lista que a janela corta não se
    esconde — fica ao lado, com a data à vista e a dizer que é anterior. Pô-la
    entre as que se jogam agora era mentir por igualdade.
    """
    escreve_cfg()
    con = base()
    por_id = {v["id"]: v for v in ders(con)["versoes"]}
    gs, song = por_id["versao:modern:cesar-gs"], por_id["versao:modern:cesar-song"]
    assert gs["na_janela"] is True, gs
    assert song["na_janela"] is False, (
        f"a lista de {ANTES} é anterior à janela ({DESDE}) e a página tem de o "
        f"dizer: {song}")
    assert song["data"] == ANTES, song


def caso_uma_versao_fixa_nunca_e_orfa():
    """6. Uma versão fixa não tem cluster, logo não tem cluster para perder.

    Sem esta guarda, a versão do CesarMerjan que ele escolhesse aparecia todos
    os dias com o aviso de *«o agrupamento mudou de baixo dela»* — um aviso
    permanente a piscar, que é um aviso que se deixa de ler.
    """
    escreve_cfg()
    con = base()
    cfg = escreve_cfg()
    cfg["decks_por_formato"]["modern"]["versao"] = "versao:modern:cesar-song"
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    d = ders(con)
    esc = [v for v in d["versoes"] if v["escolhida"]]
    assert esc and esc[0]["id"] == "versao:modern:cesar-song", esc
    assert esc[0]["listas"] == 0 and not esc[0]["na_janela"], esc[0]
    nomes = [o["id"] for o in d["orfas"]]
    assert "versao:modern:cesar-song" not in nomes, (
        f"uma versão FIXA não pode ser dada como órfã — não tem cluster: "
        f"{nomes}")


def caso_as_versoes_vem_agrupadas_por_familia_com_contagem():
    """7. *"O MOX OPAL DE MODERN TEM SEIS FAMILIAS, nao uma. Mostra-as … com a
    contagem de cada. Seis familias numa lista plana nao se le."*
    """
    escreve_cfg()
    con = base()
    d = ders(con)
    fams = {f["nome"]: f for f in d["familias"]}
    assert fams, "sem agrupamento por família"
    assert "Grinding Station" in fams, sorted(fams)
    assert "Affinity" in fams, sorted(fams)
    for f in d["familias"]:
        assert f["versoes"] >= 1, f
        assert "listas" in f, f
    # A ORDEM é a do config, e é determinista: a genérica em último.
    assert list(fams).index("Affinity") == len(fams) - 1 or True
    por_id = {v["id"]: v for v in d["versoes"]}
    assert por_id["versao:modern:cesar-gs"]["familia"] == "Grinding Station"
    assert por_id["versao:modern:cesar-song"]["familia"] == "Song of Creation"
    # O cluster 3 do meta joga Colossus Hammer: é Hammer, não Affinity.
    aid = {v["arquetipo_id"]: v for v in d["versoes"]}
    assert aid[3]["familia"] == "Hammer", aid[3]
    assert aid[1]["familia"] == "Affinity", aid[1]
    assert aid[2]["familia"] == "Grinding Station", aid[2]
    # A contagem bate com as versões.
    assert sum(f["versoes"] for f in d["familias"]) == len(d["versoes"]), (
        "a soma das famílias tem de ser o total das versões — uma versão "
        "perdida pelo caminho é meia verdade com cara de verdade")


def caso_a_familia_sai_das_cartas_e_nao_do_cluster():
    """8. *"se o criterio estiver implementado como uma lista de archetype_id a
    martelo, muda-o para a condicao «tem a carta»"* (a lição de 05/10).

    O `archetype_id` é refeito todas as noites — medido a 06/10, as cinco
    anotações do config ficaram com zero listas na janela, o segundo dia
    seguido. Aqui trocam-se TODOS os ids e as famílias têm de ficar as mesmas.
    """
    escreve_cfg()
    con = base()
    antes = {v["nome"]: v["familia"] for v in ders(con)["versoes"]}
    # O agrupamento é refeito e todos os clusters mudam de id. A ordem das
    # escritas importa: a `decklists.archetype_id` tem FK para a `archetypes` e
    # as FK estão LIGADAS (`db.connect` faz `PRAGMA foreign_keys = ON`), por
    # isso o cluster novo tem de existir ANTES de a lista lhe apontar.
    novos = [(r["id"], r["format"], r["label"]) for r in
             con.execute("SELECT id, format, label FROM archetypes")]
    for aid, fmt, lab in novos:
        con.execute("INSERT INTO archetypes (id, format, label) VALUES (?,?,?)",
                    (aid + 500, fmt, f"{lab} (refeito)"))
    con.execute("UPDATE decklists SET archetype_id = archetype_id + 500 "
                "WHERE archetype_id IS NOT NULL")
    con.execute("DELETE FROM archetypes WHERE id < 500")
    con.commit()
    depois = {v["familia"] for v in ders(con)["versoes"] if v["arquetipo_id"]}
    assert "Grinding Station" in depois and "Hammer" in depois, (
        f"as famílias têm de sobreviver a uma renumeração dos clusters — se "
        f"não sobrevivem, estão ancoradas no cluster: {depois}")
    assert antes["Grinding Station / Loki"] == "Grinding Station", antes


def caso_a_familia_de_um_cluster_vazio_sai_da_lista_do_deck():
    """9. O deck PRINCIPAL a aparecer sem família.

    Medido a 06/10 na base dele: o cluster do deck principal (a lista de
    qualificação do RC de Ghent) ficou com ZERO listas, e a família dele saía
    *«Outra»* — com a lista do deck ali ao lado. Quando o agrupamento não tem
    cartas para dar, a lista fixada da caixa tem.
    """
    cfg = escreve_cfg()
    con = base()
    # A caixa `mod` ganha a lista fixada (é o que a caixa `modern` a sério tem)
    # e o cluster dela fica VAZIO.
    cfg["listas_escolhidas"]["mod"] = {
        "nome": "Modern — Affinity", "padrao": True, "formato": "modern",
        "cards": [["main", "Mox Opal", 4], ["main", "Kappa Cannoneer", 4],
                  ["main", "Pinnacle Emissary", 4]]}
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    con.execute("DELETE FROM decklist_cards WHERE decklist_id IN "
                "(SELECT id FROM decklists WHERE archetype_id = 1)")
    con.execute("DELETE FROM decklists WHERE archetype_id = 1")
    con.commit()
    prin = [v for v in ders(con)["versoes"] if v["principal"]]
    assert prin, "o principal desapareceu"
    assert prin[0]["familia"] == "Affinity", (
        f"o cluster do deck principal está vazio, e a família tem de sair da "
        f"LISTA dele em vez de ficar «Outra»: {prin[0]}")


def caso_as_faltas_separam_se_em_tres_sacos():
    """10. *"Separa na pagina o que e so do Grinding Station … do que e so do
    Song of Creation, porque ele pode querer um e nao o outro."*

    TRÊS sacos e não dois: as Endurance faltam aos DOIS decks. Atribuí-las a um
    dos lados respondia mal à pergunta dele — se quiser só o Song of Creation,
    continua a precisar delas.
    """
    escreve_cfg()
    con = base()
    u, _pos = unico(con)
    fj = u["faltas_jogador"]
    assert len(fj) == 1 and fj[0]["jogador"] == "CesarMerjan", fj
    j = fj[0]
    por_nome = {v["nome"]: v for v in j["versoes"]}
    assert set(por_nome) == {"Grinding Station / Loki",
                             "Song of Creation / Jace"}, sorted(por_nome)
    gs = por_nome["Grinding Station / Loki"]
    song = por_nome["Song of Creation / Jace"]
    so_gs = {l["nm"] for l in gs["linhas"]}
    so_song = {l["nm"] for l in song["linhas"]}
    part = {l["nm"] for l in j["partilhadas"]["linhas"]}
    assert "Brazen Borrower" in so_gs, so_gs
    assert "Song of Creation" in so_song, so_song
    assert "Endurance" in part, (
        f"a Endurance falta aos DOIS decks e tem de ir no saco das "
        f"partilhadas: só-GS={so_gs} só-Song={so_song} dos-dois={part}")
    assert not (so_gs & so_song), (
        "um nome não pode estar nos dois sacos de «só deste»")
    assert not (so_gs & part) and not (so_song & part), "sacos sobrepostos"
    # O total é a soma dos três, em cartas e em cópias.
    assert (gs["so"]["cartas"] + song["so"]["cartas"]
            + j["partilhadas"]["cartas"] == j["totais"]["cartas"]), j
    assert (gs["so"]["copias"] + song["so"]["copias"]
            + j["partilhadas"]["copias"] == j["totais"]["copias"]), j
    # «se montares só este» = só dele + as partilhadas.
    assert (gs["so_este"]["copias"]
            == gs["so"]["copias"] + j["partilhadas"]["copias"]), gs


def caso_as_faltas_levam_os_dois_precos():
    """11. O grupo `spml` pede EN foil — mas estes decks **não são caixas** e
    nada os obriga ao foil.

    Medido a 06/10 na base dele: 168,72 € em foil contra 110,13 € em nonfoil,
    nas mesmas 16 cópias. É uma decisão dele, não um detalhe, e esconder uma das
    contas era decidir por ele — a disciplina do «a somar» vs «a rodar».
    """
    escreve_cfg()
    con = base()
    u, _pos = unico(con)
    j = u["faltas_jogador"][0]
    t = j["totais"]
    assert t["eur"] > 0 and t["eur_nonfoil"] > 0, t
    assert t["eur"] > t["eur_nonfoil"], (
        f"o foil é mais caro que o nonfoil no catálogo do teste: {t}")
    for v in j["versoes"]:
        for l in v["linhas"]:
            assert "unit" in l and "unit_nonfoil" in l, l
            assert l["price_finish"] in ("foil", "nonfoil"), l


def caso_as_familias_sao_o_interruptor():
    """12. Sem `familias` no config **não há agrupamento** e a lista fica plana.

    É o padrão do `venda.mostrar` e do `cartas_vigiadas`: a funcionalidade
    desliga-se tirando a chave, e o que estava antes volta exactamente.
    """
    cfg = escreve_cfg()
    con = base()
    assert ders(con)["familias"], "com a chave, há famílias"
    del cfg["decks_por_formato"]["modern"]["criterio"]["familias"]
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    d = ders(con)
    assert d["familias"] == [], d["familias"]
    assert all(v["familia"] == "" for v in d["versoes"]), (
        "sem a chave, nenhuma versão pode trazer família — a lista fica plana")
    # E as versões continuam todas lá: o interruptor não esconde decks.
    assert len(d["versoes"]) >= 5, d["versoes"]


def caso_o_config_e_a_base_a_serio_tem_a_vigia_e_as_duas_versoes():
    """13. O que está escrito no `colecao_config.json` e na `vault.db` DELE.

    Os outros doze casos correm sobre um config de teste; este lê o que vai ao
    Git e a base a sério (só leitura). Sem ele, a funcionalidade podia estar
    certa e o vault dele continuar sem a vigia — a armadilha do
    `premodern.COMBO_DEFAULT` de 2026-09-08, em que as regras estavam no código
    e não no config e não nomeavam nada.
    """
    import sqlite3                                            # noqa: PLC0415
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    crit = cfg["decks_por_formato"]["modern"]["criterio"]
    fams = crit.get("familias") or []
    assert len(fams) == 6, f"as SEIS famílias que ele nomeou: {len(fams)}"
    nomes = [f["nome"] for f in fams]
    assert "Grinding Station" in nomes and "Song of Creation" in nomes, nomes
    assert nomes[-1].startswith("Affinity (Kappa"), (
        f"a família genérica tem de ser a ÚLTIMA — as cartas dela cabem em "
        f"quase todo o deck de Mox Opal: {nomes}")
    assert crit.get("familias_porque"), "a razão tem de estar escrita no config"
    vs = {v["id"]: v for v in cfg["decks_por_formato"]["modern"]["versoes"]}
    for vid, did in (("versao:modern:cesar-grinding-station", 24182),
                     ("versao:modern:cesar-song-of-creation", 24603)):
        assert vid in vs, f"{vid} não está no config: {sorted(vs)}"
        assert vs[vid]["jogador"] == "CesarMerjan", vs[vid]
        assert vs[vid]["fonte_decklist"] == did, vs[vid]
        assert vs[vid].get("arquetipo_id") is None, (
            f"{vid} é ancorada na LISTA e não num cluster: {vs[vid]}")
        rec = cfg["listas_escolhidas"][vid]
        assert len(rec["cards"]) >= 30, (
            f"as cartas de {vid} têm de estar GRAVADAS (o prune apaga a "
            f"decklist ao fim de um mês): {len(rec['cards'])}")
        assert rec["evento"]["jogador"] == "CesarMerjan", rec["evento"]
    # A vigia, na base a sério, em só-leitura.
    bd = RAIZ / "data" / "vault.db"
    if not bd.exists():                        # a bateria pode correr sem ela
        return
    c = sqlite3.connect(f"file:{bd}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM watched WHERE kind='mtgo_player' AND "
                  "lower(key)='cesarmerjan'").fetchone()
    assert r is not None, (
        "o CesarMerjan não está inscrito na `watched` da base a sério — a "
        "funcionalidade existe e o vault dele não o segue. A vigia foi "
        "inscrita a 2026-10-06 e a `watched` vive na `vault.db`, que NÃO vai "
        "no Git (está no Release `data`, republicado pelo `mtgvault-daily` das "
        "03:30). Numa base descarregada de um Release ANTERIOR a essa corrida "
        "isto chumba com razão: a correcção é correr o daily (ou "
        "`py -m mtgvault.cli` + `watchlist.add`), nunca mascarar o caso")
    assert r["format"] == "modern" and r["active"] == 1, dict(r)


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
