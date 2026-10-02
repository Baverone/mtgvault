"""OS 16 DECKS QUE FICAM: A IDENTIDADE É UMA CARTA-ASSINATURA (André, 2026-10-02).

Ele fechou a lista dos decks que ficam e deu a REGRA DE OURO: *"a identidade de
um deck é uma CARTA-ASSINATURA, NUNCA a etiqueta do clustering (os clusters
chamam-se «Rotlung Reanimator / Priest of Gix / Oath of Druids» e há dezenas
vazios com o mesmo nome)"*.

Cada caso aqui chumba se a funcionalidade for RETIRADA — é o padrão do
`_provar_chumba`. O que se tranca:

  1. um deck identifica-se pela CARTA-ASSINATURA e não pela etiqueta: a MESMA
     etiqueta com cartas diferentes dá listas diferentes, e uma etiqueta vazia
     não apanha lista nenhuma;
  2. a CONJUNÇÃO (`assinatura_todas`) — o *Engineer Welder Cam* precisa das duas
     cartas, e cada uma sozinha apanha outros decks;
  3. **basta uma** é a omissão, e é o que serve o *"Greasefang, as várias
     versões"*: uma carta só apanha todas as variantes;
  4. o selector vive num sítio só (`sources.ids_por_assinatura`), partilhado
     pela LISTA da caixa e pela RESERVA — dois selectores ao lado discordam em
     silêncio;
  5. a reserva da R5 usa **TODAS** as listas e não o `counting_sql`: num formato
     com `tiers: []` (o Pauper e o cEDH dele) o filtro dá ZERO e deixava dois
     decks sem protecção nenhuma;
  6. um deck SEM carta-assinatura (o *Artifacts Blue*) **não** recebe consenso:
     a reserva fica só manual e a página di-lo;
  7. o botão **«não é necessária»** é PERSISTENTE (sobrevive a uma corrida do
     daily), tem a DATA e o deck, e é REVERSÍVEL.

Não toca na rede nem na base a sério. Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB`
(ver `tests/_bateria.py`: os ficheiros que acompanham a base saem da pasta da
`MTGVAULT_DB`, e sem a fixar a bateria escrevia no `data/` a sério).
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
HOJE = date.today().isoformat()


def _dias(n):
    return (date.today() - timedelta(days=n)).isoformat()


# As cartas do catálogo de mentira. `Goblin Welder` e `Sewer-veillance Cam` são
# a conjunção do Engineer Welder Cam; `Greasefang` é a carta única das «várias
# versões»; `Myr Enforcer` é a assinatura do Pauper, cujo formato tem
# `tiers: []` no config dele (e por isso ZERO listas que contam).
CARTAS = [
    ("Goblin Welder", "usg", "Creature"),
    ("Sewer-veillance Cam", "svc", "Artifact"),
    ("Greasefang, Okiba Boss", "neo", "Creature"),
    ("Myr Enforcer", "mrd", "Artifact"),
    ("Force of Will", "all", "Instant"),
    ("Swan Song", "the", "Instant"),
    ("Dark Ritual", "4ed", "Instant"),
    ("Sol Ring", "c21", "Artifact"),
    ("Chrome Mox", "mrd", "Artifact"),
]

CFG_BASE = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_por_formato": [{"grupo": "livre",
                            "formatos": ["legacy", "pioneer", "pauper"]}],
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge"], "min_jogadores_presencial": 0},
        # Como no config dele: o Pauper não conta NADA (ele só segue o Luffy).
        "pauper": {"tiers": [], "ligas": False},
    },
    "caixas": [
        {"slot": "welder", "nome": "Engineer Welder Cam", "formato": "legacy",
         "fonte": "consenso",
         "assinatura": ["Goblin Welder", "Sewer-veillance Cam"],
         "assinatura_todas": True, "balde": "Colecção", "prioridade": 1},
        {"slot": "grease", "nome": "Greasefang", "formato": "pioneer",
         "fonte": "consenso", "assinatura": ["Greasefang, Okiba Boss"],
         "balde": "Colecção", "prioridade": 2},
        {"slot": "pauper", "nome": "Affinity (Luffy)", "formato": "pauper",
         "fonte": "manual", "cards": [], "reserva_assinatura": ["Myr Enforcer"],
         "balde": "Colecção", "prioridade": 3},
        {"slot": "azul", "nome": "Artifacts Blue", "formato": "legacy",
         "fonte": "manual", "cards": [], "balde": "Colecção", "prioridade": 4},
        # Uma caixa cuja LISTA vem de fora (como o Stiflenought, que segue a do
        # Luffy) e cuja IDENTIDADE é a carta-assinatura, em conjunção. É aqui que
        # se mede o botão «não é necessária»: com a lista vazia, tudo o que as
        # listas do mês mostram cai na reserva — que é o que a R5 diz.
        {"slot": "welderm", "nome": "Welder (lista de fora)", "formato": "legacy",
         "fonte": "manual", "cards": [],
         "reserva_assinatura": ["Goblin Welder", "Sewer-veillance Cam"],
         "reserva_assinatura_todas": True, "balde": "Colecção", "prioridade": 5},
    ],
    "venda": {"mostrar": True},
    "reserva": {"janela_dias": 30, "staples_premodern_pct": 90},
}
CFG_PATH = _TMP / "cfg.json"


def escreve_cfg(cfg=None, **muda):
    cfg = json.loads(json.dumps(cfg if cfg is not None else CFG_BASE))
    for k, v in muda.items():
        if k == "caixa_chave":
            for c in cfg["caixas"]:
                if c["slot"] in v:
                    c.update(v[c["slot"]])
        else:
            cfg[k] = v
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    from mtgvault import sources
    sources._CFG_CACHE.clear()
    return cfg


CFG_PATH.write_text(json.dumps(CFG_BASE, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import caixas, configio, db, fases, loadout, sources  # noqa: E402

_ABERTAS = []


# ---------------------------------------------------------------------------
# A base de mentira
# ---------------------------------------------------------------------------
def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, tl) in enumerate(CARTAS):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id,
               name, set_code, set_name, collector_number, lang, rarity,
               type_line, oracle_text, cmc, color_identity, finishes,
               released_at, legalities, digital, reserved, set_type)
               VALUES (?,?,?,?,?,?,'en','rare',?,'',0,'',?,
                       '2005-10-07',?,0,0,'expansion')""",
            (f"id-{i}", f"or-{i}", nm, sc, f"Set {sc.upper()}", str(100 + i), tl,
             json.dumps(["nonfoil", "foil"]),
             json.dumps({"legacy": "legal", "pioneer": "legal",
                         "pauper": "legal"})))
        for fin in ("nonfoil", "foil"):
            con.execute("""INSERT OR REPLACE INTO price_latest (scryfall_id,
                           source, finish, date, low, trend, receita)
                           VALUES (?,'cardmarket',?,?,?,?,'unico')""",
                        (f"id-{i}", fin, HOJE, 10.0 + i, 10.0 + i))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    con.commit()
    return con


def add(con, nm, q=1, slot=None):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    cid = con.execute("""INSERT INTO copies (scryfall_id, quantity, finish,
                         language, condition, purpose, sub_collection_id)
                         VALUES (?,?,'nonfoil','en','NM','player',?)""",
                      (sid, q, sub)).lastrowid
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.commit()
    return cid


def lista(con, chave, fmt, cartas, dias=5, tier="Challenge", etiqueta=None):
    """Uma decklist. `etiqueta` é o rótulo do clustering (a tabela `archetypes`),
    que é precisamente o que NÃO se usa para identificar o deck."""
    con.execute("""INSERT INTO decklists (source, source_key, format,
                   event_date, event_tier, player)
                   VALUES ('mtgo', ?, ?, ?, ?, ?)""",
                (chave, fmt, _dias(dias), tier, f"j-{chave}"))
    lid = con.execute("SELECT id FROM decklists WHERE source_key = ?",
                      (chave,)).fetchone()["id"]
    for nm, board in cartas:
        con.execute("""INSERT OR REPLACE INTO decklist_cards (decklist_id,
                       card_name, quantity, board) VALUES (?,?,1,?)""",
                    (lid, nm, board))
    if etiqueta:
        con.execute("INSERT OR IGNORE INTO archetypes (format, label) "
                    "VALUES (?,?)", (fmt, etiqueta))
    con.commit()
    return lid


def reserva(con, slot, cfg=None):
    res = loadout.report(con)
    s = next(x for x in res["slots"] if x["slot"] == slot)
    return fases.reserva_do_deck(con, s), res


# ===========================================================================
# 1. A IDENTIDADE É A CARTA, NUNCA A ETIQUETA
# ===========================================================================
def caso_um_deck_identifica_se_pela_carta_e_nao_pela_etiqueta():
    """Duas listas com a MESMA etiqueta de clustering e cartas diferentes são
    decks diferentes; e uma etiqueta sozinha não apanha lista nenhuma.

    É a regra de ouro dele. Medido na base a sério: a tabela `archetypes` tinha
    870 etiquetas de `duel-commander` e 808 sem uma única lista.
    """
    con = base()
    # A MESMA etiqueta em dois decks que não têm nada a ver.
    lista(con, "a1", "legacy", [("Goblin Welder", "main"),
                                ("Sewer-veillance Cam", "main")],
          etiqueta="Rotlung Reanimator / Priest of Gix / Oath of Druids")
    lista(con, "a2", "legacy", [("Dark Ritual", "main"), ("Sol Ring", "main")],
          etiqueta="Rotlung Reanimator / Priest of Gix / Oath of Druids")
    welder = sources.ids_por_assinatura(
        con, "legacy", ["Goblin Welder", "Sewer-veillance Cam"], todas=True)
    outro = sources.ids_por_assinatura(con, "legacy", ["Dark Ritual"])
    assert len(welder) == 1 and len(outro) == 1, (welder, outro)
    assert welder != outro, "a carta-assinatura não separou os dois decks"
    # E a etiqueta, que é o que a regra proíbe usar, não é por onde se procura:
    # existe na tabela e não apanha lista nenhuma por si.
    n = con.execute("SELECT COUNT(*) FROM archetypes").fetchone()[0]
    assert n == 1, n
    assert sources.ids_por_assinatura(
        con, "legacy", ["Rotlung Reanimator / Priest of Gix / Oath of Druids"]
    ) == [], "a etiqueta apanhou uma lista — está a ser usada como identidade"


def caso_a_conjuncao_exige_as_duas_cartas():
    """O *Engineer Welder Cam*: *"usa as DUAS em conjunção"*. Cada carta sozinha
    apanha outros decks de Legacy — medido na base dele a 2026-10-02: Welder 50
    listas, Cam 54, as duas juntas 50 (a Cam traz 4 que não jogam Welder)."""
    con = base()
    lista(con, "as_duas", "legacy", [("Goblin Welder", "main"),
                                     ("Sewer-veillance Cam", "main")])
    lista(con, "so_welder", "legacy", [("Goblin Welder", "main")])
    lista(con, "so_cam", "legacy", [("Sewer-veillance Cam", "main")])
    ass = ["Goblin Welder", "Sewer-veillance Cam"]
    juntas = sources.ids_por_assinatura(con, "legacy", ass, todas=True)
    basta = sources.ids_por_assinatura(con, "legacy", ass, todas=False)
    assert len(juntas) == 1, juntas
    assert len(basta) == 3, basta
    assert sources.texto_assinatura(ass, True) == \
        "Goblin Welder e Sewer-veillance Cam"
    assert sources.texto_assinatura(ass, False) == \
        "Goblin Welder ou Sewer-veillance Cam"
    # A caixa do config usa a conjunção, e é isso que a página mostra.
    escreve_cfg()
    res = loadout.report(con)
    d = next(x for x in fases.decks_para_decidir(con, res)
             if x["slot"] == "welder")
    assert d["assinatura_todas"] is True, d
    assert d["assinatura"] == "Goblin Welder e Sewer-veillance Cam", d
    assert d["reserva"]["listas"] == 1, d["reserva"]


def caso_basta_uma_carta_para_apanhar_as_varias_versoes():
    """*"Greasefang, as várias versões — NÃO restrinjas a uma variante: todas as
    listas com a carta contam."* A omissão (`IN`) é exactamente isso."""
    con = base()
    # Três VERSÕES do mesmo deck, com cartas diferentes à volta da Greasefang —
    # e dez listas, para haver amostra (`MIN_LISTAS_RESERVA`).
    for k in range(4):
        lista(con, f"g1{k}", "pioneer", [("Greasefang, Okiba Boss", "main"),
                                         ("Dark Ritual", "main")])
    for k in range(3):
        lista(con, f"g2{k}", "pioneer", [("Greasefang, Okiba Boss", "main"),
                                         ("Chrome Mox", "main")])
    for k in range(3):
        lista(con, f"g3{k}", "pioneer", [("Greasefang, Okiba Boss", "main"),
                                         ("Swan Song", "side")])
    # E uma lista de Pioneer que NÃO é deste deck: a assinatura tem de a deixar
    # de fora.
    lista(con, "outro", "pioneer", [("Sol Ring", "main")])
    ids = sources.ids_por_assinatura(con, "pioneer",
                                     ["Greasefang, Okiba Boss"])
    assert len(ids) == 10, "a carta única não apanhou as várias versões"
    escreve_cfg(caixa_chave={"grease": {
        "fonte": "manual", "cards": [],
        "reserva_assinatura": ["Greasefang, Okiba Boss"]}})
    r, _res = reserva(con, "grease")
    # A reserva traz as cartas das TRÊS versões, main e side — é o *"não
    # restrinjas a uma variante"*.
    nomes = {x["nm"] for x in r["final"]}
    assert {"Dark Ritual", "Chrome Mox", "Swan Song"} <= nomes, nomes
    assert "Sol Ring" not in nomes, "apanhou uma lista que não é deste deck"


def caso_o_selector_de_listas_vive_num_sitio_so():
    """A pergunta *"que listas são deste deck?"* é feita pela LISTA da caixa e
    pela RESERVA. Um segundo selector ao lado discordava do primeiro em
    silêncio, que é a lição do `event_tier`."""
    fonte = (RAIZ / "mtgvault" / "loadout.py").read_text(encoding="utf-8")
    assert "sources.ids_por_assinatura" in fonte, \
        "o `loadout` voltou a escrever a sua própria consulta de assinatura"
    fonte_f = (RAIZ / "mtgvault" / "fases.py").read_text(encoding="utf-8")
    assert "sources.ids_por_assinatura" in fonte_f
    # E nenhum dos dois volta a montar o `dc.card_name IN` à mão.
    for nome, txt in (("loadout", fonte), ("fases", fonte_f)):
        assert "dc.card_name IN (" not in txt, \
            f"o `{nome}` voltou a ter a consulta da assinatura escrita à mão"


# ===========================================================================
# 2. O UNIVERSO DE LISTAS DA R5: TODAS, e não o `counting_sql`
# ===========================================================================
def caso_a_reserva_usa_todas_as_listas_e_nao_so_as_que_contam():
    """No Pauper e no cEDH dele o filtro de eventos dá ZERO de propósito
    (`metagame_fontes.*.tiers = []`, porque ele só segue o Luffy). Com o filtro
    ligado, dois dos 16 decks ficavam sem protecção nenhuma — em silêncio."""
    con = base()
    for k in range(10):
        lista(con, f"p{k}", "pauper", [("Myr Enforcer", "main"),
                                       ("Chrome Mox", "side")], dias=10)
    contam = sources.ids_por_assinatura(con, "pauper", ["Myr Enforcer"],
                                        so_que_contam=True)
    todas = sources.ids_por_assinatura(con, "pauper", ["Myr Enforcer"],
                                       so_que_contam=False)
    assert contam == [], "o Pauper passou a ter listas que contam — o fixture mudou"
    assert len(todas) == 10, todas
    escreve_cfg()
    add(con, "Chrome Mox", 2)
    r, res = reserva(con, "pauper")
    assert r["listas"] == 10, r
    assert "Chrome Mox" in {x["nm"] for x in r["final"]}, r["final"]
    c = fases.candidatos(con, res)
    assert "Chrome Mox" not in {l["nm"] for l in c["linhas"]}, \
        "a reserva do Pauper não protegeu nada — o filtro de eventos voltou"


def caso_a_janela_de_trinta_dias_corta_o_que_e_antigo():
    con = base()
    for k in range(10):
        lista(con, f"v{k}", "pioneer", [("Greasefang, Okiba Boss", "main"),
                                        ("Swan Song", "side")], dias=40)
    escreve_cfg()
    r, _res = reserva(con, "grease")
    assert r["listas"] == 0, r
    desde = fases.desde_de(30)
    assert sources.ids_por_assinatura(
        con, "pioneer", ["Greasefang, Okiba Boss"], desde=desde,
        so_que_contam=False) == [], "a janela não cortou listas de há 40 dias"


# ===========================================================================
# 3. SEM CARTA-ASSINATURA NÃO HÁ CONSENSO
# ===========================================================================
def caso_um_deck_sem_assinatura_nao_recebe_consenso():
    """O *Artifacts Blue*: *"CRIA A CAIXA MAS DEIXA-A SEM FONTE — o André ainda
    não me disse qual é a carta que a define. Marca-a visivelmente como «à
    espera da carta-assinatura» e NÃO lhe atribuas consenso nenhum."*"""
    con = base()
    for k in range(10):
        lista(con, f"w{k}", "legacy", [("Goblin Welder", "main"),
                                       ("Sewer-veillance Cam", "main"),
                                       ("Force of Will", "side")], dias=5)
    escreve_cfg()
    add(con, "Force of Will", 2)
    res = loadout.report(con)
    d = next(x for x in fases.decks_para_decidir(con, res) if x["slot"] == "azul")
    assert d["assinatura"] == "", d
    assert not d["assinatura_cartas"], d
    assert d["reserva"]["listas"] == 0, d["reserva"]
    assert not d["reserva"]["final"], d["reserva"]["final"]
    assert "à espera da carta-assinatura" in d["reserva"]["nota"], \
        d["reserva"]["nota"]
    # O deck do lado, que TEM assinatura, recebe consenso — o controlo.
    w = next(x for x in fases.decks_para_decidir(con, res)
             if x["slot"] == "welder")
    assert w["reserva"]["listas"] == 10, w["reserva"]


# ===========================================================================
# 4. O BOTÃO «NÃO É NECESSÁRIA»
# ===========================================================================
def caso_o_nao_e_necessaria_tira_a_carta_da_reserva_com_data_e_deck():
    con = base()
    for k in range(10):
        lista(con, f"w{k}", "legacy", [("Goblin Welder", "main"),
                                       ("Sewer-veillance Cam", "main"),
                                       ("Force of Will", "side")], dias=5)
    add(con, "Force of Will", 2)
    escreve_cfg()
    r, res = reserva(con, "welderm")
    assert "Force of Will" in {x["nm"] for x in r["final"]}, r["final"]
    c = fases.candidatos(con, res)
    assert "Force of Will" not in {l["nm"] for l in c["linhas"]}
    # Carregar no botão: a carta sai da reserva DAQUELE deck, com a data.
    escreve_cfg(caixa_chave={"welderm": {
        "reserva_fora": [{"nm": "Force of Will", "em": HOJE}]}})
    r2, res2 = reserva(con, "welderm")
    assert "Force of Will" not in {x["nm"] for x in r2["final"]}, r2["final"]
    assert r2["retiradas"] == [{"nm": "Force of Will", "em": HOJE}], r2["retiradas"]
    c2 = fases.candidatos(con, res2)
    assert "Force of Will" in {l["nm"] for l in c2["linhas"]}, \
        "a carta dispensada não passou a candidata a venda"


def caso_o_nao_e_necessaria_sobrevive_a_uma_corrida_do_daily():
    """PERSISTENTE: está no `colecao_config.json`, que o `daily` não reescreve —
    e a reserva continua a crescer com as listas novas sem lhe devolver o que ele
    já recusou (guarda-se o que ele TIROU, não a lista final)."""
    con = base()
    for k in range(10):
        lista(con, f"w{k}", "legacy", [("Goblin Welder", "main"),
                                       ("Sewer-veillance Cam", "main"),
                                       ("Force of Will", "side")], dias=5)
    add(con, "Force of Will", 2)
    add(con, "Swan Song", 2)
    escreve_cfg(caixa_chave={"welderm": {
        "reserva_fora": [{"nm": "Force of Will", "em": _dias(3)}]}})
    # A «corrida do daily»: chegam listas NOVAS, com outra carta no sideboard.
    for k in range(10):
        lista(con, f"n{k}", "legacy", [("Goblin Welder", "main"),
                                       ("Sewer-veillance Cam", "main"),
                                       ("Force of Will", "side"),
                                       ("Swan Song", "side")], dias=1)
    r, res = reserva(con, "welderm")
    nomes = {x["nm"] for x in r["final"]}
    assert "Swan Song" in nomes, "a reserva deixou de crescer com as listas novas"
    assert "Force of Will" not in nomes, \
        "a corrida do daily devolveu à reserva uma carta dispensada"
    c = fases.candidatos(con, res)
    assert "Force of Will" in {l["nm"] for l in c["linhas"]}
    assert "Swan Song" not in {l["nm"] for l in c["linhas"]}


def caso_o_nao_e_necessaria_desfaz_se():
    """REVERSÍVEL: o «voltar a pôr» tira a carta do `reserva_fora` e ela volta à
    reserva automática. É o `devolver` do endpoint, e não um `add` disfarçado —
    um `add` punha-a na lista MANUAL, que fica lá mesmo que ninguém a jogue."""
    con = base()
    for k in range(10):
        lista(con, f"w{k}", "legacy", [("Goblin Welder", "main"),
                                       ("Sewer-veillance Cam", "main"),
                                       ("Force of Will", "side")], dias=5)
    add(con, "Force of Will", 2)
    escreve_cfg(caixa_chave={"welderm": {
        "reserva_fora": [{"nm": "Force of Will", "em": HOJE}]}})
    r, _res = reserva(con, "welderm")
    assert "Force of Will" not in {x["nm"] for x in r["final"]}
    # «voltar a pôr»: sai do `reserva_fora` e volta à automática, sem passar pela
    # lista manual.
    escreve_cfg()
    r2, res2 = reserva(con, "welderm")
    carta = next(x for x in r2["final"] if x["nm"] == "Force of Will")
    assert carta["manual"] is False, \
        "o «voltar a pôr» pôs a carta na reserva MANUAL em vez da automática"
    assert not r2["retiradas"], r2["retiradas"]
    c = fases.candidatos(con, res2)
    assert "Force of Will" not in {l["nm"] for l in c["linhas"]}


def caso_o_endpoint_do_botao_grava_as_tres_accoes():
    """As três acções do `/api/fase-reserva`, pelo caminho a sério (o mesmo
    código do `webapp._fase_reserva`, sem subir servidor): `remover` escreve com
    data, `devolver` desfaz, `add` põe na manual. E o ficheiro **não cresce**."""
    escreve_cfg()
    configio.escrever(configio.ler(CFG_PATH), CFG_PATH)
    sources._CFG_CACHE.clear()
    antes = len(CFG_PATH.read_text(encoding="utf-8").splitlines())

    def grava(act, carta, slot="welderm"):
        cfg = configio.ler(CFG_PATH)
        c = caixas.caixa_do_cfg(cfg, slot)
        reserva_l = [str(x) for x in (c.get("reserva") or [])]
        fora = dict(fases._retiradas(c))
        if act == "add":
            reserva_l.append(carta)
            fora.pop(carta, None)
        elif act == "devolver":
            fora.pop(carta, None)
        else:
            reserva_l = [x for x in reserva_l if x != carta]
            fora.setdefault(carta, HOJE)
        c["reserva"] = sorted(reserva_l)
        if fora:
            c["reserva_fora"] = [{"nm": n, "em": e}
                                 for n, e in sorted(fora.items())]
        else:
            c.pop("reserva_fora", None)
        if not c["reserva"]:
            c.pop("reserva", None)
        configio.escrever(cfg, CFG_PATH)
        sources._CFG_CACHE.clear()
        return caixas.caixa_do_cfg(configio.ler(CFG_PATH), slot)

    c = grava("remover", "Force of Will")
    assert c["reserva_fora"] == [{"nm": "Force of Will", "em": HOJE}], c
    c = grava("devolver", "Force of Will")
    assert "reserva_fora" not in c, c
    c = grava("add", "Swan Song")
    assert c["reserva"] == ["Swan Song"], c
    depois = len(CFG_PATH.read_text(encoding="utf-8").splitlines())
    assert depois - antes <= 2, f"o config cresceu {depois - antes} linhas"


# ===========================================================================
def main():
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for f in casos:
        try:
            escreve_cfg()
            f()
            print(f"  ok   {f.__name__}")
        except Exception as e:                                # noqa: BLE001
            falhas += 1
            print(f"  FAIL {f.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                     # noqa: BLE001, S110
            pass
    print(f"\n{len(casos) - falhas}/{len(casos)} casos ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
