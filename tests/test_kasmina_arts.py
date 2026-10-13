"""A KASMINA EM PIONEER, A VIGIA DO TRIO E A REGRA DAS ARTS (André, 2026-10-13).

O que aqui se tranca:
  1. a VIGIA DO COMBO: uma lista com DUAS das três peças (Kasmina, Jace's
     Machinations, Avatar of Burgeoning Echoes) é apanhada em QUALQUER formato,
     e uma liga com ela guarda-se mesmo num formato que não conta ligas; uma
     peça sozinha não é o deck — nem avisa nem abre a porta;
  2. a Kasmina sozinha passou a ser vigiada em TODOS os formatos;
  3. o config a sério: a Kasmina de Modern SAIU (não se apagou), o deck de
     Pioneer é um BREW marcado, com 60 + 15, sem nenhum dos 14 nomes que não são
     legais em Pioneer, e as trocas batem carta a carta com as duas listas;
  4. um brew desenha-se como brew e NUNCA com ficha de evento;
  5. a regra das arts, pela ordem dele: básica nunca se pede; a escolhida ganha;
     uma impressão só → a que tem; duas → pergunta-se; nenhuma → pede-se;
  6. o `arts.registar` confere no catálogo antes de escrever e escreve na forma
     canónica do config (a lição do commit `ac1f776`);
  7. nas faltas o PREÇO é o da art (a que tem / a escolhida) e cada linha diz de
     onde veio; a lista das arts por escolher vai por valor.

Não abre a rede nem as bases do André: tudo em temporárias. Fixa
`MTGVAULT_HOME`, `MTGVAULT_DB` e `MTGVAULT_CATALOG` antes do import (ver
`tests/_bateria.py`).
"""
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
KASMINA, JACE, AVATAR = ("Kasmina, Enigma Sage", "Jace's Machinations",
                         "Avatar of Burgeoning Echoes")
CAIXAS = [{"slot": "ced", "nome": "Blue Farm", "formato": "cedh", "fonte": "deck",
           "ref": "CEDH", "balde": "Colecção", "estado": "permanente",
           "prioridade": 1}]
CFG = {
    "venda": {"mostrar": False, "congelada": True},
    "regras_colecao": {}, "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_por_formato": [{"grupo": "cedh", "formatos": ["cedh"], "dedicado": True}],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {}, "decks_de_evento": [], "listas_escolhidas": {},
    "basicas": {}, "decks_por_formato": {},
    "metagame_fontes": {"_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                                     "min_jogadores_presencial": 64, "ligas": False}},
    "cartas_vigiadas": [
        {"carta": KASMINA, "formatos": [], "nota": "todos"},
        {"carta": JACE, "formatos": ["modern", "pioneer"], "nota": ""},
        {"combo": [KASMINA, JACE, AVATAR], "minimo": 2, "nome": "Combo Kasmina",
         "formatos": [], "nota": ""}],
    "arts_procuradas": {},
}
CAMINHO = _TMP / "cfg.json"
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")          # ver tests/_bateria.py
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")


def escreve_cfg(extra=None):
    from mtgvault import configio, sources                    # noqa: PLC0415
    c = json.loads(json.dumps(CFG))
    c.update(extra or {})
    configio.escrever(c, CAMINHO)
    sources._CFG_CACHE.clear()


escreve_cfg()
from mtgvault import (arts, collection, configio, db, decks_vista,  # noqa: E402
                      faltas_vista, loadout, sources, vigia)

#: `(nome, set, numero, preço nonfoil)`. Os preços estão escolhidos para a regra
#: MEXER no número: a impressão que ele TEM da Mox Opal (2XM) é a mais cara, e a
#: mais barata que serve (SOM) é outra — se o preço da linha fosse o da regra
#: genérica, o caso 7 passava a verde com a conta errada.
CATALOGO = [
    ("Mox Opal", "som", "179", 20.0), ("Mox Opal", "2xm", "362", 100.0),
    ("Lotus Petal", "tmp", "294", 40.0), ("Lotus Petal", "mb2", "226", 5.0),
    ("Exploration", "usg", "250", 77.0), ("Exploration", "dmr", "160", 41.0),
    ("Island", "unh", "137", 0.3),
    (KASMINA, "stx", "60", 2.0), (JACE, "fra", "50", 3.0), (AVATAR, "fra", "200", 1.0),
]
LISTA = [("main", "Mox Opal", 2), ("main", "Lotus Petal", 3),
         ("main", "Exploration", 1), ("main", "Island", 10)]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, num, preco) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line,
               oracle_text, cmc, color_identity, finishes, released_at,
               legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Artifact','',1,'U',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), num,
             json.dumps(["nonfoil"]), f"20{10 + i:02d}-01-01",
             json.dumps({"cedh": "legal", "pioneer": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-13', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.execute("INSERT INTO decks (name, format) VALUES ('CEDH', 'cedh')")
    did = con.execute("SELECT id FROM decks WHERE name='CEDH'").fetchone()["id"]
    for b, nm, q in LISTA:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,?)", (did, nm, q, b))
    # O que ele TEM: uma Mox Opal (2XM, uma impressão só) e duas Lotus Petal em
    # DUAS impressões. Exploration: nenhuma.
    collection.add_copy(con, "Mox Opal", set_code="2xm", collector_number="362",
                        sub_collection="Colecção")
    collection.add_copy(con, "Lotus Petal", set_code="tmp", collector_number="294",
                        sub_collection="Colecção")
    collection.add_copy(con, "Lotus Petal", set_code="mb2", collector_number="226",
                        sub_collection="Colecção")
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


LIGA = {"source": "mtgo", "event_date": "2026-10-12", "placement": "5-0"}


def caso_a_vigia_do_combo_apanha_duas_pecas_em_qualquer_formato():
    con = base()
    # Duas peças numa liga de Legacy (formato que NÃO conta ligas): guarda-se.
    did = sources.store_decklist(
        con, fmt="legacy", event_name="Legacy League 2026-10-12",
        source_key="l1", player="alguem", url="u1",
        cards=[("main", JACE, 4), ("main", AVATAR, 4), ("main", "Island", 20)], **LIGA)
    assert did, "uma liga com duas pecas do combo tem de se guardar"
    # Uma peça só numa liga de Standard: não é o deck, não se guarda.
    so_um = sources.store_decklist(
        con, fmt="standard", event_name="Standard League 2026-10-12",
        source_key="l2", player="outro", url="u2",
        cards=[("main", JACE, 4), ("main", "Island", 20)], **LIGA)
    assert not so_um, "o Jace sozinho fora de modern/pioneer nao e o deck"
    # A Kasmina sozinha, num formato qualquer (Pauper): vigiada em todos.
    kas = sources.store_decklist(
        con, fmt="pauper", event_name="Pauper League 2026-10-12",
        source_key="l3", player="terceiro", url="u3",
        cards=[("main", KASMINA, 1), ("main", "Island", 20)], **LIGA)
    assert kas, "a Kasmina e vigiada em TODOS os formatos"
    con.commit()
    ach = Counter(a["carta"] for a in vigia.achados(con))
    assert ach == {"Combo Kasmina": 1, KASMINA: 1}, ach
    assert vigia.ha_vigia("premodern") and vigia.ha_vigia("vintage")
    assert vigia.nomes_na_lista("legacy", [("main", JACE, 1)]) == []
    print("vigia do combo: duas pecas em qualquer formato avisam, uma so nao")


def caso_o_combo_nao_e_lido_como_carta_solta():
    """A linha do combo traz `nome` — e o `_entradas` lia `nome` como carta. Sem a
    guarda, o combo aparecia duas vezes e a carta «Combo Kasmina» era procurada
    nas listas como se existisse."""
    assert [c["carta"] for c in vigia.cartas()] == [KASMINA, JACE]
    assert [c["carta"] for c in vigia.combos()] == ["Combo Kasmina"]
    assert len(vigia.vigiados()) == 3
    print("o combo e um combo, nao uma carta solta")


def caso_o_config_a_serio_tem_o_brew_e_a_vigia():
    real = configio.ler(RAIZ / "colecao_config.json")
    ks = [e for e in real["cartas_vigiadas"] if e.get("carta") == KASMINA]
    assert ks and ks[0]["formatos"] == [], "a Kasmina vigia-se em todos os formatos"
    cb = [e for e in real["cartas_vigiadas"] if e.get("combo")]
    assert cb and set(cb[0]["combo"]) == {KASMINA, JACE, AVATAR}
    assert not cb[0]["formatos"], "o combo vigia-se em todos os formatos"
    dde = {d["id"]: d for d in real["decks_de_evento"]}
    mod = dde["deck:modern:jaces-machinations-combo"]
    assert mod.get("_saiu"), "a Kasmina de Modern sai — e nao se apaga"
    assert "decisao_pendente" not in mod, "a decisao foi tomada: nao pode continuar pendente"
    pio = dde["deck:pioneer:kasmina-brew"]
    assert pio["formato"] == "pioneer" and pio.get("brew")
    rec = real["listas_escolhidas"]["deck:pioneer:kasmina-brew"]
    assert rec.get("brew") is True and "evento" not in rec
    main = sum(q for b, _, q in rec["cards"] if b == "main")
    side = sum(q for b, _, q in rec["cards"] if b == "side")
    assert (main, side) == (60, 15), (main, side)
    # Os 14 nomes da lista de Modern que NÃO são legais em Pioneer (medido no
    # catálogo a 2026-10-13; três deles banidos). Nenhum pode estar no brew.
    ilegais = {"Teferi, Time Raveler", "Flooded Strand", "Windswept Heath",
               "Preordain", "Prismatic Ending", "Brainsurge", "Orim's Chant",
               "Utopia Sprawl", "Misty Rainforest", "Consign to Memory",
               "Force of Negation", "Isochron Scepter", "Surgical Extraction",
               "Wrath of the Skies"}
    nomes = {n for _b, n, _q in rec["cards"]}
    assert not (nomes & ilegais), nomes & ilegais
    # As trocas batem carta a carta: o que entra É o brew, o que sai É a de Modern.
    entra, sai, lista, modern = Counter(), Counter(), Counter(), Counter()
    for s, qs, e, qe, _pq in rec["substituicoes"]:
        sai[s] += qs
        entra[e] += qe
    for _b, n, q in rec["cards"]:
        lista[n] += q
    for _b, n, q in real["listas_escolhidas"]["deck:modern:jaces-machinations-combo"]["cards"]:
        modern[n] += q
    assert entra == lista, (entra - lista, lista - entra)
    assert sai == modern, (sai - modern, modern - sai)
    for n in ("Llanowar Elves", "Cavern of Souls", "Mox Amber", "Thassa's Oracle",
              "Enter the Infinite", KASMINA, JACE, AVATAR, "Theorist's Sanctum"):
        assert n in nomes, n
    print("config: Modern saiu, Pioneer e brew 60+15 so com cartas legais, trocas batem")


def caso_um_brew_desenha_se_como_brew_e_sem_evento():
    escreve_cfg({
        "decks_de_evento": [{"id": "deck:pioneer:x", "slug": "x", "nome": "X",
                             "formato": "pioneer", "brew": "montado por mim"}],
        "listas_escolhidas": {"deck:pioneer:x": {
            "brew": True, "origem": "brew", "cards": [["main", KASMINA, 4]],
            "substituicoes": [["Utopia Sprawl", 4, "Llanowar Elves", 4, "porque"]]}}})
    con = base()
    d = decks_vista.decks_de_evento(con)[0]
    assert d["brew"] == "montado por mim" and d["substituicoes"]
    assert not d.get("evento"), "um brew nunca leva ficha de evento"
    assert "brew" in d["rotulo_estado"]
    assert not con.execute("SELECT 1 FROM decklists").fetchone(), \
        "um brew vive so no config: nunca e uma linha da decklists"
    escreve_cfg()
    print("um brew diz que e um brew, com as trocas, e sem ficha de evento")


def caso_a_regra_das_arts_pela_ordem_dele():
    escreve_cfg()
    con = base()
    assert arts.preferida(con, "Island")["origem"] == "basica"
    p = arts.preferida(con, "Mox Opal")
    assert p["origem"] == "a_que_tens" and (p["set"], p["num"]) == ("2xm", "362"), p
    assert arts.preferida(con, "Lotus Petal")["origem"] == "ambigua"
    assert len(arts.preferida(con, "Lotus Petal")["opcoes"]) == 2
    assert arts.preferida(con, "Exploration")["origem"] == "por_escolher"
    # A escolhida ganha a TUDO, incluindo à que ele tem.
    escreve_cfg({"arts_procuradas": {"Mox Opal": {"set": "som", "num": "179",
                                                   "em": "2026-10-13"},
                                     "Exploration": {"set": "usg", "num": "250",
                                                     "em": "2026-10-13"}}})
    p = arts.preferida(con, "Mox Opal")
    assert p["origem"] == "escolhida" and p["set"] == "som", p
    # Um registo que já não bate no catálogo não se usa calado.
    escreve_cfg({"arts_procuradas": {"Mox Opal": {"set": "xxx", "num": "1"}}})
    p = arts.preferida(con, "Mox Opal")
    assert p["origem"] == "a_que_tens" and p["registo_invalido"] == "XXX #1", p
    escreve_cfg()
    print("arts: basica / escolhida / a que tens / ambigua / por escolher")


def caso_registar_confere_e_escreve_na_forma_canonica():
    escreve_cfg()
    con = base()
    try:
        arts.registar(con, "Mox Opal", "usg", "250", path=CAMINHO)
        raise AssertionError("uma impressao de OUTRA carta nao pode passar")
    except ValueError as e:
        assert "não há impressão" in str(e)
    try:
        arts.registar(con, "Island", "unh", "137", path=CAMINHO)
        raise AssertionError("nao se pede art de basicas")
    except ValueError:
        pass
    r = arts.registar(con, "Mox Opal", "SOM", "179", hoje="2026-10-13", path=CAMINHO)
    assert (r["set"], r["num"]) == ("som", "179")
    txt = CAMINHO.read_text(encoding="utf-8")
    assert txt == configio.texto(configio.ler(CAMINHO)), "forma canonica"
    assert '"Mox Opal": {"set": "som", "num": "179", "em": "2026-10-13"}' in txt, \
        "uma carta por linha"
    assert arts.esquecer("Mox Opal", path=CAMINHO)
    sources._CFG_CACHE.clear()
    assert arts.registadas() == {}
    print("registar: confere no catalogo, recusa basicas, uma linha por carta")


def caso_as_faltas_usam_a_art_e_dizem_de_onde_vem():
    escreve_cfg({"arts_procuradas": {"Exploration": {"set": "usg", "num": "250",
                                                     "em": "2026-10-13"}}})
    con = base()
    v = faltas_vista.vista(con, loadout.report(con))
    ls = {l["nm"]: l for d in v["decks"] for l in d["linhas"]}
    mox = ls["Mox Opal"]
    assert mox["origem_preco"] == "a_que_tens", mox
    assert mox["unit_ref"] == 100.0, "o preco e o da art que ele TEM (2XM), nao o da SOM"
    assert mox["unit"] == 20.0, "o minimo do motor continua ao lado"
    exp = ls["Exploration"]
    assert exp["origem_preco"] == "escolhida" and exp["unit_ref"] == 77.0, exp
    lot = ls["Lotus Petal"]
    assert lot["origem_preco"] == "regra" and lot["arte"]["origem"] == "ambigua"
    assert lot["arte"]["opcoes"] == ["TMP #294", "MB2 #226"] or \
        sorted(lot["arte"]["opcoes"]) == ["MB2 #226", "TMP #294"]
    t = v["totais"]
    assert t["valor_ref"] == round(sum(l["total_ref"] for l in ls.values()), 2)
    assert t["por_origem"] == {"escolhida": 1, "a_que_tens": 1, "regra": 1}, t
    A = v["arts"]
    assert A["contagens"]["basicas"] == 1
    assert [x["nm"] for x in A["ambiguas"]] == ["Lotus Petal"], \
        "ambigua COM compra (falta 1): pergunta-se"
    assert [x["nm"] for x in A["escolhidas"]] == ["Exploration"]
    escreve_cfg()
    v = faltas_vista.vista(con, loadout.report(con))
    assert [x["nm"] for x in v["arts"]["por_escolher"]] == ["Exploration"]
    print("faltas: o preco e o da art (a que tem / a escolhida) e a linha di-lo")


def run():
    caso_a_vigia_do_combo_apanha_duas_pecas_em_qualquer_formato()
    caso_o_combo_nao_e_lido_como_carta_solta()
    caso_o_config_a_serio_tem_o_brew_e_a_vigia()
    caso_um_brew_desenha_se_como_brew_e_sem_evento()
    caso_a_regra_das_arts_pela_ordem_dele()
    caso_registar_confere_e_escreve_na_forma_canonica()
    caso_as_faltas_usam_a_art_e_dizem_de_onde_vem()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
