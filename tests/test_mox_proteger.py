"""MONTAR E PROTEGER SÃO DUAS PERGUNTAS (André, 2026-10-05, à letra).

    *"quando digo as decklists que jogam Mox Opal, e porque assim ficamos com
    uma lista de cartas que eu gostaria de nao vender, tudo o resto e «seguro»
    vender"*
    *"aplica o mesmo para Legacy, assim jogo Mox Opal nos 2 formatos"*

CORRIGE a leitura de 2026-10-04 à noite, que escolheu as quatro versões da
Affinity a assumir que a lista de decks de Mox Opal era para **MONTAR**. É para
**PROTEGER**, e isso inverte o critério: passa a ser INCLUSIVO.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_mox.py`, que desliga uma peça de cada vez e exige vermelho:

  1. uma carta que só aparece numa lista de Mox Opal de **LEGACY** não entra
     nas candidatas à venda;
  2. os arquétipos que ficaram FORA das versões voltam a **proteger** — é o
     inclusivo contra o selectivo;
  3. o conjunto de MONTAR (as versões) é DIFERENTE do de PROTEGER (todas as
     listas) e os dois não se confundem;
  4. mudar o limiar de 1 para 2 listas muda o total protegido;
  5. as shocklands e as fetchlands continuam protegidas **pela regra** (R2/R3)
     e não por este critério;
  6. o `protege_todas` é o interruptor: um formato sem ele (o Pioneer) fica
     exactamente como estava;
  7. o Legacy deixou de estar `por_decidir`, logo a **RLG não dispara** — e
     volta a disparar se alguém lá puser um formato por decidir;
  8. o universo das listas é SEM o filtro de tier (uma liga conta), que é a
     mesma excepção da R5 e pela mesma razão;
  9. a curva do limiar dá os DOIS números (`a_mais` e `sozinha`), como a
     `curva_staples`.

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
    {"slot": "mod", "nome": "Modern — Affinity", "formato": "modern",
     "fonte": "deck", "ref": "MO", "balde": "Colecção", "estado": "permanente",
     "prioridade": 1},
    {"slot": "leg", "nome": "Legacy", "formato": "legacy", "fonte": "deck",
     "ref": "LG", "balde": "Colecção", "estado": "permanente", "prioridade": 2},
    {"slot": "pio", "nome": "Pioneer — Greasefang", "formato": "pioneer",
     "fonte": "deck", "ref": "PI", "balde": "Colecção", "estado": "permanente",
     "prioridade": 3},
]

#: Só o cluster 1 é versão (joga as duas cartas do `exige`). O 3 joga Mox Opal
#: e NÃO é versão — é o equivalente dos cinco que ele tinha posto de fora.
VERSOES = [{"id": "versao:modern:alfa", "arquetipo_id": 1, "nome": "Alfa",
            "listas": 6, "deck": "caixa:mod"}]

CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["modern", "legacy", "pioneer"],
         "dedicado": True, "cartas_partilhadas": "rotativas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    # A R5 DESLIGADA de propósito: ela apanha tudo o que foi jogado nos últimos
    # 30 dias e esconderia a RP atrás dela. Quem a exercita é o `test_fases`.
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": {},
    "decks_por_formato": {
        "_corte_pct": 5.0,
        "_limiar_listas": 1,
        "modern": {
            "nome": "Affinity (Mox Opal)", "em": "2026-10-04",
            "criterio": {"carta": "Mox Opal", "protege_todas": True,
                         "exige": ["Kappa Cannoneer", "Pinnacle Emissary"],
                         "pct_minima": 50},
            "versoes": VERSOES, "versao": "versao:modern:alfa",
        },
        "legacy": {
            "nome": "Decks de Mox Opal", "em": "2026-10-05",
            "criterio": {"carta": "Mox Opal", "protege_todas": True},
            "versoes": [],
        },
        # O Pioneer tem carta-chave e NÃO é inclusivo: é o controlo do caso 6.
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
    """O config do teste. As chaves em `_substitui` TROCAM-SE inteiras em vez
    de se fundirem — sem isso, `decks_por_formato={}` era um `update({})`, ou
    seja um no-op, e o caso do interruptor passava a verde sem provar nada."""
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

from mtgvault import (collection, db, fases, loadout,  # noqa: E402
                      sources, versoes)

SHOCK = ("You may pay 2 life. If you don't, it enters tapped. "
         "{T}: Add {W} or {U}.")
FETCH = ("{T}, Pay 1 life, Sacrifice Hallowed Fountainless: Search your "
         "library for a Plains or Island card, put it onto the battlefield, "
         "then shuffle.")

#: `(nome, set, data, preço, type_line, oracle_text)`
CATALOGO = [
    ("Mox Opal", "som", "2010-10-01", 300.0, "Legendary Artifact", ""),
    ("Kappa Cannoneer", "unf", "2022-10-07", 20.0, "Artifact Creature", ""),
    ("Pinnacle Emissary", "fra", "2026-09-29", 8.0, "Artifact Creature", ""),
    ("Lantern of Insight", "som", "2010-10-01", 4.0, "Artifact", ""),
    # SÓ em listas de Legacy que jogam Mox Opal — é o caso 1.
    ("Chrome Mox", "mrd", "2003-10-02", 50.0, "Artifact", ""),
    # SÓ no cluster 3 (joga Mox Opal e não é versão) — é o caso 2.
    ("Scrabbling Claws", "dst", "2004-02-06", 2.0, "Artifact", ""),
    # Em lista NENHUMA: tem de ficar candidata, senão o critério não corta nada.
    ("Pithing Needle", "som", "2010-10-01", 3.0, "Artifact", ""),
    # Aparece numa ÚNICA lista de Mox Opal — é o caso 4 (o limiar).
    ("Tormod's Crypt", "tsp", "2006-10-06", 6.0, "Artifact", ""),
    # UMA lista de Modern e UMA de Legacy: soma 2, máximo 1. É o que separa a
    # leitura literal de *"em quantas listas"* de um máximo por formato.
    ("Lotus Petal", "tmp", "1997-10-14", 40.0, "Artifact", ""),
    # Uma shockland que TAMBÉM aparece numa lista de Mox Opal — é o caso 5.
    ("Hallowed Fountain", "rav", "2005-10-07", 12.0,
     "Land — Plains Island", SHOCK),
    ("Hallowed Fountainless", "ons", "2002-10-07", 30.0,
     "Land", FETCH),
    ("Greasefang, Okiba Boss", "neo", "2022-02-18", 5.0,
     "Legendary Creature", ""),
    ("Parhelion II", "war", "2019-05-03", 4.0, "Legendary Artifact", ""),
]
_ABERTAS = []

LISTAS = {"MO": [("main", "Mox Opal", 4)], "LG": [], "PI": []}

#: As listas de METAGAME. `(formato, archetype_id, cartas, n, tier)`.
#:   1 — a versão de Modern (joga as duas do `exige`)
#:   3 — joga Mox Opal e NÃO é versão: é quem segura a Scrabbling Claws
#:   4 — Legacy com Mox Opal: é quem segura o Chrome Mox
#:   5 — Legacy SEM Mox Opal: o que lá estiver não é protegido por este critério
#:   6 — Pioneer (o controlo do interruptor)
META = [
    ("modern", 1, [("Mox Opal", 4), ("Kappa Cannoneer", 4),
                   ("Pinnacle Emissary", 4), ("Hallowed Fountain", 2),
                   ("Hallowed Fountainless", 4)], 6, "Challenge"),
    ("modern", 3, [("Mox Opal", 4), ("Lantern of Insight", 4),
                   ("Scrabbling Claws", 2)], 4, "Challenge"),
    ("legacy", 4, [("Mox Opal", 4), ("Chrome Mox", 4)], 5, "Challenge"),
    ("legacy", 5, [("Pithing Needle", 4)], 7, "Challenge"),
    ("pioneer", 6, [("Greasefang, Okiba Boss", 4), ("Parhelion II", 2)], 4,
     "Challenge"),
]


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco, tipo, txt) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line,
               oracle_text, cmc, color_identity, finishes, released_at,
               legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,?,1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             txt, json.dumps(["nonfoil"]), rel,
             json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-04', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    for ref, cards in LISTAS.items():
        fmt = {"MO": "modern", "LG": "legacy"}.get(ref, "pioneer")
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


def semear_meta(con, extra=None):
    for fmt, aid, cartas, n, tier in (list(extra) if extra else list(META)):
        con.execute("INSERT OR IGNORE INTO archetypes (id, format, label) "
                    "VALUES (?,?,?)", (aid, fmt, f"cluster {aid}"))
        for k in range(n):
            con.execute(
                """INSERT INTO decklists (format, source, source_key, event_name,
                   event_date, event_tier, event_players, player, archetype_id,
                   content_hash)
                   VALUES (?,?,?,?,?,?,64,?,?,?)""",
                (fmt, "mtgo", f"k{aid}-{k}", f"{fmt} evento", "2026-10-02",
                 tier, f"j{aid}-{k}", aid, f"h{aid}-{k}"))
            did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
            for nm, q in cartas:
                con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                            " quantity, board) VALUES (?,?,?,'main')",
                            (did, nm, q))


def copia(con, nm, sc, q=1):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção")
    con.commit()
    return cid


def candidatas(con, **kw):
    """`{nome: cópias}` do que SOBRA para venda, e o índice das protegidas."""
    res = loadout.report(con)
    c = fases.candidatos(con, res, sources.config(), {}, **kw)
    venda = {}
    for l in c["linhas"]:
        venda[l["nm"]] = venda.get(l["nm"], 0) + l["q"]
    prot = {}
    for l in c["protegidas"]:
        prot[l["nm"]] = l["proteccao"]
    return venda, prot, c


# ===========================================================================
def caso_uma_carta_de_lista_de_legacy_de_mox_opal_nao_e_candidata():
    """1. *"aplica o mesmo para Legacy, assim jogo Mox Opal nos 2 formatos"*.

    O Chrome Mox só aparece no cluster 4 — Legacy, com Mox Opal. Antes de
    2026-10-05 o Legacy estava `por_decidir` e não tinha critério nenhum: esta
    carta ia à venda. Hoje é a RP que a segura.
    """
    escreve_cfg()
    con = base()
    copia(con, "Chrome Mox", "mrd", 3)
    copia(con, "Pithing Needle", "som", 2)
    venda, prot, _c = candidatas(con)
    assert "Chrome Mox" not in venda, (
        f"o Chrome Mox joga-se numa lista de Mox Opal de Legacy e foi à venda: "
        f"{venda}")
    assert prot.get("Chrome Mox") == fases.RP, (
        f"devia ser a RP a segurá-lo, e foi {prot.get('Chrome Mox')!r}")
    # O CONTROLO: a Pithing Needle só aparece no cluster 5, de Legacy SEM Mox
    # Opal. Sem este contraste o critério podia estar a proteger tudo.
    assert venda.get("Pithing Needle") == 2, (
        f"a Pithing Needle não se joga em deck de Mox Opal nenhum e tinha de "
        f"ficar candidata: venda={venda}, protegida por {prot.get('Pithing Needle')!r}")


def caso_os_arquetipos_fora_das_versoes_voltam_a_proteger():
    """2. O critério é INCLUSIVO, não selectivo.

    A Scrabbling Claws só se joga no cluster 3, que joga Mox Opal e **não é
    uma versão** (não joga Pinnacle Emissary). É o equivalente dos cinco que
    tinham ficado de fora a 04/10. Para MONTAR continua fora; para PROTEGER
    conta.
    """
    escreve_cfg()
    con = base()
    copia(con, "Scrabbling Claws", "dst", 4)
    venda, prot, _c = candidatas(con)
    assert "Scrabbling Claws" not in venda, (
        f"um arquétipo que joga Mox Opal e não é versão tem de PROTEGER na "
        f"mesma: {venda}")
    assert prot.get("Scrabbling Claws") == fases.RP
    # E continua FORA das versões — é a outra metade da mesma asserção.
    ids = {v["arquetipo_id"] for v in versoes.versoes("modern")}
    assert 3 not in ids, "o cluster 3 não pode ter virado versão"


def caso_montar_e_proteger_sao_conjuntos_diferentes():
    """3. *"Mantem a distincao no ecra entre proteger e montar."*

    Se os dois conjuntos se confundirem, ou ele monta decks que não quer, ou
    vende cartas que quer. O de MONTAR são as versões; o de PROTEGER são todas
    as listas da carta-chave.
    """
    escreve_cfg()
    con = base()
    montar = versoes.ids_que_ficam()
    proteger = set(versoes.nomes_protegidos(con))
    assert montar == {"caixa:mod", "caixa:pio"}, montar
    # O de proteger tem cartas que NENHUMA versão joga.
    assert "Scrabbling Claws" in proteger and "Chrome Mox" in proteger, proteger
    # E o de montar continua a ser só a versão escolhida de cada formato.
    assert versoes.versao_escolhida("modern") == "versao:modern:alfa"
    # As duas perguntas não dão a mesma resposta — é isso que as torna duas.
    nomes_montar = set(versoes.nomes_que_ficam(loadout.report(con)))
    assert proteger - nomes_montar, (
        "o conjunto de PROTEGER tem de ser MAIOR do que o de MONTAR; se forem "
        "iguais, voltou-se ao critério selectivo de 04/10")


def caso_mudar_o_limiar_muda_o_total_protegido():
    """4. *"Poe um LIMIAR configuravel … e NAO escolhas por ele."*

    A Tormod's Crypt aparece numa ÚNICA lista de Mox Opal. A 1 fica protegida;
    a 2 passa a candidata.
    """
    escreve_cfg()
    con = base()
    # Um cluster NOVO (8) com UMA lista — repetir o `aid` 1 dava
    # `UNIQUE constraint failed: decklists.source_key`.
    semear_meta(con, [("modern", 8, [("Mox Opal", 4),
                                     ("Tormod's Crypt", 1)], 1, "Challenge")])
    con.commit()
    copia(con, "Tormod's Crypt", "tsp", 4)

    assert versoes.limiar_listas() == 1
    venda1, prot1, _ = candidatas(con)
    assert "Tormod's Crypt" not in venda1, (
        f"com o limiar a 1 uma carta de uma única lista fica protegida: {venda1}")
    assert prot1.get("Tormod's Crypt") == fases.RP

    escreve_cfg(decks_por_formato={**CFG["decks_por_formato"],
                                   "_limiar_listas": 2})
    assert versoes.limiar_listas() == 2
    venda2, _prot2, _ = candidatas(con)
    assert venda2.get("Tormod's Crypt") == 4, (
        f"com o limiar a 2 ela tinha de passar a candidata: {venda2}")


def caso_o_limiar_conta_a_soma_entre_formatos():
    """4b. *"em quantas listas"* — as 25 de Modern e as 23 de Legacy são 48
    listas de Mox Opal, e uma carta que esteja numa de cada está em **duas**
    delas. É a leitura literal, e é a mais conservadora: com o máximo por
    formato esta carta ia à venda ao limiar 2.
    """
    escreve_cfg(decks_por_formato={**CFG["decks_por_formato"],
                                   "_limiar_listas": 2})
    con = base()
    semear_meta(con, [
        ("modern", 9, [("Mox Opal", 4), ("Lotus Petal", 4)], 1, "Challenge"),
        ("legacy", 10, [("Mox Opal", 4), ("Lotus Petal", 4)], 1, "Challenge"),
    ])
    con.commit()
    copia(con, "Lotus Petal", "tmp", 4)
    info = versoes.contagem_por_carta(con, sources.config(), {})["Lotus Petal"]
    assert info["formatos"] == {"modern": 1, "legacy": 1}, info
    assert info["listas"] == 2, (
        f"a soma entre formatos tem de ser 2 e deu {info['listas']} — com o "
        f"máximo por formato daria 1 e a carta ia à venda")
    venda, prot, _c = candidatas(con)
    assert "Lotus Petal" not in venda, (
        f"está em duas listas de Mox Opal e o limiar é 2: {venda}")
    assert prot.get("Lotus Petal") == fases.RP


def caso_as_terras_continuam_protegidas_pela_regra():
    """5. *"as ShockLands e FetchLands continuam fora por regra e nao por este
    criterio"*.

    As duas aparecem numa lista de Mox Opal — e têm de continuar a dizer R2/R3.
    A ordem das regras é o que o garante: se amanhã o critério mudar, elas
    continuam protegidas, e é esse o ponto.
    """
    escreve_cfg()
    con = base()
    copia(con, "Hallowed Fountain", "rav", 4)
    copia(con, "Hallowed Fountainless", "ons", 4)
    _venda, prot, _c = candidatas(con)
    assert prot.get("Hallowed Fountain") == fases.R2, (
        f"a shockland tem de sair pela R2 e saiu por {prot.get('Hallowed Fountain')!r}")
    assert prot.get("Hallowed Fountainless") == fases.R3, (
        f"a fetchland tem de sair pela R3 e saiu por "
        f"{prot.get('Hallowed Fountainless')!r}")
    # E o critério CONHECE-AS — ou seja, não é por estarem fora dele que o
    # motivo é outro: é pela ordem das regras.
    p = versoes.nomes_protegidos(con)
    assert "Hallowed Fountain" in p and "Hallowed Fountainless" in p


def caso_o_protege_todas_e_o_interruptor():
    """6. Um formato com carta-chave e SEM `protege_todas` fica como estava.

    O Pioneer tem critério (é por ele que se escolhem as versões) e **não** é
    inclusivo: ele nomeou as três versões. Alargá-lo por simetria era decidir
    por ele.
    """
    escreve_cfg()
    con = base()
    assert versoes.formatos_inclusivos() == ["legacy", "modern"]
    assert not versoes.protege_todas("pioneer")
    copia(con, "Parhelion II", "war", 4)
    _venda, prot, _c = candidatas(con)
    # A Parhelion II joga-se na lista de Greasefang, mas o Pioneer não é
    # inclusivo: se estiver protegida, é por outra regra que não a RP.
    assert prot.get("Parhelion II") != fases.RP, (
        "o Pioneer não é inclusivo e não pode proteger pela RP")
    # E desligar o `protege_todas` do Modern devolve o critério ao que era.
    d = json.loads(json.dumps(CFG["decks_por_formato"]))
    d["modern"]["criterio"].pop("protege_todas")
    d["legacy"]["criterio"].pop("protege_todas")
    escreve_cfg(("decks_por_formato",), decks_por_formato=d)
    assert versoes.formatos_inclusivos() == []
    assert versoes.nomes_protegidos(con) == {}


def caso_o_legacy_deixou_de_estar_por_decidir():
    """7. A RLG desliga-se sozinha — era para isto que ela foi escrita.

    *"E O LEGACY ENTRA … Deixa de estar «por decidir»."* Com isso nenhum
    formato está por decidir e a RLG não dispara. E volta a disparar no dia em
    que houver outro — não se apagou nada.
    """
    escreve_cfg()
    con = base()
    assert versoes.formatos_por_decidir() == []
    copia(con, "Pithing Needle", "som", 2)
    _venda, prot, c = candidatas(con)
    assert c["por_proteccao"][fases.RLG]["copias"] == 0, (
        "nenhum formato está por decidir, logo a RLG não pode proteger nada")
    assert prot.get("Pithing Needle") is None
    # Com um formato por decidir outra vez, a RLG volta. A Pithing Needle joga
    # em 7 das 12 listas de Legacy da janela — muito acima do corte de 5 %.
    d = json.loads(json.dumps(CFG["decks_por_formato"]))
    d["legacy"] = {"nome": "(por decidir)", "por_decidir": True, "versoes": []}
    escreve_cfg(("decks_por_formato",), decks_por_formato=d)
    assert versoes.formatos_por_decidir() == ["legacy"]
    _v2, prot2, _c2 = candidatas(con)
    assert prot2.get("Pithing Needle") == fases.RLG, (
        f"a RLG tinha de voltar a segurá-la: {prot2.get('Pithing Needle')!r}")


def caso_o_universo_das_listas_nao_leva_o_filtro_de_tier():
    """8. É a mesma excepção da R5, e pela mesma razão.

    *Sub-contar numa regra de protecção é VENDER uma carta que ele precisa.* Um
    5-0 de league que jogue Mox Opal conta — e é também o universo em que os
    números que ele mediu batem (modern 25 de 364, legacy 23 de 171).
    """
    escreve_cfg()
    con = base()
    # Uma LIGA de Modern, que o `counting_sql` recusa, com uma carta só dela.
    semear_meta(con, [("modern", 7, [("Mox Opal", 4),
                                     ("Pithing Needle", 2)], 1, "League")])
    con.commit()
    copia(con, "Pithing Needle", "som", 2)
    p = versoes.nomes_protegidos(con)
    assert "Pithing Needle" in p, (
        "uma liga que joga a carta-chave tem de contar para a protecção")
    _venda, prot, _c = candidatas(con)
    assert prot.get("Pithing Needle") == fases.RP


def caso_a_curva_do_limiar_da_os_dois_numeros():
    """9. O padrão da `curva_staples`: `a_mais` e `sozinha`.

    Com uma coluna só, uma curva plana lia-se como *"o limiar não importa"*
    quando o que se passa é que outra regra chegou primeiro.
    """
    escreve_cfg()
    con = base()
    copia(con, "Chrome Mox", "mrd", 3)
    copia(con, "Scrabbling Claws", "dst", 4)
    res = loadout.report(con)
    curva, uma = fases.curva_limiar(con, res, (1, 2), sources.config(), {})
    assert [c["limiar"] for c in curva] == [1, 2]
    for c in curva:
        assert {"a_mais", "sozinha", "cartas_criterio"} <= set(c), c
        assert c["a_mais"]["copias"] <= c["sozinha"]["copias"], (
            "o que a regra protege POR CIMA das outras nunca pode ser mais do "
            "que o que protegeria sozinha")
    assert curva[0]["cartas_criterio"] >= curva[1]["cartas_criterio"], (
        "subir o limiar nunca pode aumentar o número de cartas no critério")
    assert set(uma) >= {"linhas", "copias", "valor"}, uma


def caso_a_pagina_diz_os_dois_totais_e_o_que_o_legacy_arrastou():
    """O que ele LÊ. *"Mostra os dois totais lado a lado"* e *"DIZ-LHE ISTO NA
    PAGINA, porque e a consequencia que ele talvez nao tenha visto."*"""
    escreve_cfg()
    con = base()
    copia(con, "Chrome Mox", "mrd", 3)
    copia(con, "Pithing Needle", "som", 2)
    res = loadout.report(con)
    cache: dict = {}
    cands = fases.candidatos(con, res, sources.config(), cache)
    m = fases.resumo_mox(con, res, cands, sources.config(), cache)
    assert m, "o bloco da RP tem de existir quando há formatos inclusivos"
    assert set(m["formatos"]) == {"modern", "legacy"}
    assert m["formatos"]["legacy"]["carta"] == "Mox Opal"
    assert m["nao_vender"]["valor"] >= 0 and m["seguro_vender"]["valor"] >= 0
    # O Chrome Mox só se joga em Legacy: tem de aparecer na fatia do Legacy.
    assert "Chrome Mox" in {x["nm"] for x in m["so_legacy"]["piores"]}, m["so_legacy"]
    assert m["limiar"] == 1


def caso_sem_o_bloco_no_config_nada_muda():
    """O interruptor de sempre: esvaziar o `decks_por_formato` devolve o vault
    ao modelo anterior, e a RP deixa de existir."""
    escreve_cfg(("decks_por_formato",), decks_por_formato={})
    con = base()
    copia(con, "Chrome Mox", "mrd", 3)
    assert versoes.formatos_inclusivos() == []
    venda, prot, c = candidatas(con)
    assert venda.get("Chrome Mox") == 3, venda
    assert c["por_proteccao"][fases.RP]["copias"] == 0
    assert prot.get("Chrome Mox") is None


#: Os casos, por nome — é por aqui que o `_chumba_mox.py` lhes pega.
CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]


def main():
    casos = CASOS
    maus = 0
    for f in casos:
        try:
            f()
            print(f"  ok   {f.__name__}")
        except Exception as e:                                # noqa: BLE001
            maus += 1
            print(f"  FAIL {f.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                     # noqa: BLE001, S110
            pass
    print(f"{len(casos) - maus}/{len(casos)} ok")
    return 1 if maus else 0


if __name__ == "__main__":
    sys.exit(main())
