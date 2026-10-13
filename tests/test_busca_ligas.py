"""PIONEER E LEGACY: EVENTOS DO MTGO OU PRESENCIAIS COM MAIS DE 30, E A LIGA COMO
FONTE DE BUSCA (André, 2026-10-13, à letra).

    *"para Pioneer apenas quero registos do MTGO ou torneios presenciais com mais
    de 30 pessoas"* · *"para Legacy igual"* · *"as ligas servem apenas para
    procurar listas de decks novos, como a Kasmina, ou se a amostra de decks que
    procuramos e baixa"*

Três coisas, e cada caso tranca uma:

  1. **a porta dos presenciais desce de 64 para 31** no Pioneer e no Legacy, e é
     pelo `event_tier` e não pela FONTE (o mesmo Challenge entra pelo mtgo.com e
     pelo mtgtop8 — é o mesmo evento);
  2. **um presencial sem número de jogadores não conta, e diz-se** — o que não se
     sabe não conta, mas deixou de cair em silêncio
     (`sources.presenciais_sem_numero`);
  3. **a liga é BUSCA, nunca CONTAGEM** (`"ligas": "busca"`): não entra na
     percentagem, no consenso nem no agrupamento; guarda-se só para um ALVO
     NOMEADO (um deck seguido com amostra baixa, um jogador vigiado, uma carta
     vigiada); e a poda não apaga as que lá estão.

Não abre socket para fora. Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver
`tests/_bateria.py`).
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
DESDE = "2026-10-01"
DEPOIS = "2026-10-02"

CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "consenso": {"desde": DESDE},
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["modern", "legacy", "pioneer"],
         "dedicado": True},
    ],
    "caixas": [
        {"slot": "pio", "nome": "Pioneer — Greasefang", "formato": "pioneer",
         "fonte": "deck", "ref": "PIO", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1,
         "reserva_assinatura": ["Greasefang, Okiba Boss"]},
    ],
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": {},
    "cartas_vigiadas": [],
    "ligas_busca": {"amostra_baixa_max": 2},
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial",
                               "Qualifier"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "modern": {"min_jogadores_presencial": 0, "ligas": "busca"},
        "pioneer": {"min_jogadores_presencial": 31, "ligas": "busca"},
        "legacy": {"min_jogadores_presencial": 31, "ligas": "busca"},
        "duel-commander": {"tiers": ["Challenge", "Showcase", "Presencial",
                                     "outro"],
                           "min_jogadores_presencial": 0, "ligas": True},
    },
    "decks_por_formato": {
        "_corte_pct": 5.0,
        "_limiar_listas": 1,
        "modern": {
            "nome": "Affinity (Mox Opal)", "em": "2026-10-05",
            "criterio": {"carta": "Mox Opal", "protege_todas": True},
            "versoes": [
                {"id": "versao:modern:affinity", "nome": "Affinity",
                 "meta": {"cartas": ["Kappa Cannoneer", "Mox Opal"]}},
                {"id": "versao:modern:oswald", "nome": "Oswald",
                 "meta": {"cartas": ["Oswald Fiddlebender"]}},
            ],
            "versao": "versao:modern:affinity",
        },
    },
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(**mudancas):
    from mtgvault import busca_ligas, sources                # noqa: PLC0415
    d = json.loads(json.dumps(CFG))
    for k, v in mudancas.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    busca_ligas.esquecer()
    return d


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import analysis, busca_ligas, db, sources, versoes   # noqa: E402

CATALOGO = ["Mox Opal", "Kappa Cannoneer", "Oswald Fiddlebender",
            "Greasefang, Okiba Boss", "Lightning Bolt"]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, nm in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line,
               oracle_text, cmc, color_identity, finishes, released_at,
               legalities, digital, reserved)
               VALUES (?,?,?,'xxx','X set',?,'en','rare','Artifact','',1,'',?,
                       '2020-01-01','{}',0,0)""",
            (f"id-{i}", f"or-{nm}", nm, str(i), json.dumps(["nonfoil"])))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    busca_ligas.esquecer()
    return con


def lista(con, fmt="pioneer", tier="Challenge", jog=64, data=DEPOIS,
          cartas=(("Lightning Bolt", 4),), chave=None, nome=None, fonte="mtgo"):
    chave = chave or f"k-{fmt}-{tier}-{jog}-{data}-{id(cartas)}-{nome}"
    con.execute(
        """INSERT INTO decklists (format, source, source_key, event_name,
           event_date, event_tier, event_players, player, content_hash)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (fmt, fonte, chave, nome or f"{fmt} {tier}", data, tier, jog,
         f"j-{chave}", f"h-{chave}"))
    did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
    for nm, q in cartas:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                    " quantity, board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def _conta_sql(con, did, fmt):
    w, p = sources.counting_sql(fmt, "d")
    return con.execute(f"SELECT COUNT(*) c FROM decklists d WHERE d.id = ? "
                       f"AND {w}", [did] + p).fetchone()["c"] == 1


def _conta(con, did, fmt):
    """O `lista_conta` (Python) e o `counting_sql` (SQL) TÊM de dar o mesmo."""
    row = con.execute("SELECT * FROM decklists WHERE id = ?", (did,)).fetchone()
    a, b = sources.lista_conta(row, fmt), _conta_sql(con, did, fmt)
    assert a == b, f"lista_conta={a} e counting_sql={b} discordam ({fmt})"
    return a


# ---------------------------------------------------------------------------
# 1. A porta dos presenciais: 31 em Pioneer e Legacy, 64 no resto
# ---------------------------------------------------------------------------
def caso_pioneer_e_legacy_contam_presenciais_de_31_ou_mais():
    escreve_cfg()
    con = base()
    for fmt in ("pioneer", "legacy"):
        assert _conta(con, lista(con, fmt, "Presencial", 31), fmt), (
            f"{fmt}: um presencial de 31 jogadores ('mais de 30') tem de contar")
        assert not _conta(con, lista(con, fmt, "Presencial", 30), fmt), (
            f"{fmt}: um de 30 NÃO é 'mais de 30'")
        assert _conta(con, lista(con, fmt, "Presencial", 64), fmt)
        for t in ("Challenge", "Showcase", "Qualifier"):
            assert _conta(con, lista(con, fmt, t, None), fmt), (
                f"{fmt}: um {t} do MTGO conta, seja qual for a fonte")
        assert _conta(con, lista(con, fmt, "Challenge", None, fonte="mtgtop8"),
                      fmt), (
            f"{fmt}: o MESMO Challenge re-hospedado pelo mtgtop8 conta — a regra "
            "é pelo event_tier, não pela fonte")
    # O controlo: o `_default` (premodern) continua a 64.
    assert not _conta(con, lista(con, "premodern", "Presencial", 40),
                      "premodern"), "o _default continua a pedir 64"
    assert sources.metagame_rules("pioneer")["tiers"] == \
        ["Challenge", "Showcase", "Presencial", "Qualifier"], (
        "os tiers do pioneer herdam do _default")


def caso_um_presencial_sem_numero_nao_conta_e_fica_dito():
    """O que não se sabe não conta — e deixa de cair em silêncio."""
    escreve_cfg()
    con = base()
    sem = lista(con, "legacy", "Presencial", None, nome="Law League #2",
                chave="sem-1")
    zero = lista(con, "legacy", "Presencial", 0, nome="Law League #2",
                 chave="sem-2")
    assert not _conta(con, sem, "legacy"), (
        "um presencial SEM número de jogadores entrou na contagem sem se dar "
        "por isso")
    assert not _conta(con, zero, "legacy"), (
        "o backfill grava 0 quando a página não diz — 0 também é «não se sabe»")
    lista(con, "legacy", "Presencial", 35, nome="Law League #2", chave="gem")
    rows = sources.presenciais_sem_numero(con, "legacy")
    assert rows and rows[0]["listas"] == 2, rows
    assert rows[0]["gemeo_jogadores"] == 35, (
        "a re-publicação do mesmo evento com número tem de vir como pista")
    # Num formato sem mínimo não há nada a dizer.
    lista(con, "modern", "Presencial", None, chave="mod-sem")
    assert sources.presenciais_sem_numero(con, "modern") == []


# ---------------------------------------------------------------------------
# 2. A liga é busca, nunca contagem
# ---------------------------------------------------------------------------
def caso_a_liga_de_busca_nunca_conta():
    escreve_cfg()
    con = base()
    assert "League" not in sources.metagame_rules("modern")["tiers"], (
        "'busca' é uma string, e uma string é verdadeira: o `ligas` não pode "
        "ser lido como «truthy»")
    assert sources.conta_ligas("modern") is False
    assert busca_ligas.e_busca("modern") and busca_ligas.e_busca("legacy")
    liga = lista(con, "modern", "League", None,
                 cartas=(("Mox Opal", 4), ("Kappa Cannoneer", 4)))
    assert not _conta(con, liga, "modern"), "uma liga de busca entrou na conta"
    lista(con, "modern", "Challenge", 32,
          cartas=(("Mox Opal", 4), ("Kappa Cannoneer", 4)))
    lista(con, "modern", "Challenge", 32, cartas=(("Lightning Bolt", 4),))
    d = versoes.listas_do_formato(con)["modern"]
    assert (d["listas"], d["total"]) == (1, 2), (
        f"a percentagem de cabeça tem de ser SEM ligas; deu {d}")
    assert d["ligas"]["listas"] == 1 and d["ligas"]["busca"] is True, d["ligas"]
    assert d["ligas"]["conta"] is False


def caso_a_liga_guarda_se_so_com_um_alvo_nomeado():
    escreve_cfg()
    con = base()
    # Affinity com 3 listas que contam (> limiar 2): não é baixa.
    for i in range(3):
        lista(con, "modern", "Challenge", 32, chave=f"af{i}",
              cartas=(("Mox Opal", 4), ("Kappa Cannoneer", 4)))
    a = busca_ligas.alvos(con, "modern", fresco=True)
    baixos = {d["nome"] for d in a["baixos"]}
    assert "Oswald" in baixos and "Affinity" not in baixos, a["decks"]

    def guarda(cartas, player="x", k=[0]):
        k[0] += 1
        return sources.store_decklist(
            con, source="mtgo", source_key=f"liga-{k[0]}", fmt="modern",
            cards=[("main", c, 4) for c in cartas], event_name="Modern League",
            event_date=DEPOIS, player=f"{player}{k[0]}")

    assert guarda(["Oswald Fiddlebender", "Mox Opal"]), (
        "uma liga do Oswald (amostra baixa) tem de se guardar — é a busca")
    assert guarda(["Kappa Cannoneer", "Mox Opal"]) is None, (
        "a Affinity tem amostra suficiente fora das ligas: a liga não se guarda")
    assert guarda(["Lightning Bolt"]) is None, (
        "uma liga que não serve alvo nenhum não se guarda")
    # O jogador vigiado é um alvo nomeado.
    con.execute("INSERT INTO watched (kind, key, format, label, active) "
                "VALUES ('mtgo_player', 'CesarMerjan', 'modern', 'C', 1)")
    con.commit()
    busca_ligas.esquecer()
    assert sources.store_decklist(
        con, source="mtgo", source_key="liga-cesar", fmt="modern",
        cards=[("main", "Lightning Bolt", 4)], event_name="Modern League",
        event_date=DEPOIS, player="CesarMerjan"), (
        "a liga de um jogador vigiado guarda-se — a vigia dele não pode cegar")
    # E nada disto passou a contar.
    w, p = sources.counting_sql("modern", "d")
    n = con.execute(f"SELECT COUNT(*) c FROM decklists d WHERE d.event_tier="
                    f"'League' AND {w}", p).fetchone()["c"]
    assert n == 0, f"{n} listas de liga de busca entraram na contagem"


def caso_o_limiar_e_por_deck_seguido_e_nao_pelo_universo():
    """Mediana de um arquétipo = 2 listas em todos os formatos (13/10): um limiar
    sobre o universo disparava sempre. Os alvos são só os decks que o config
    nomeia."""
    escreve_cfg()
    con = base()
    for i in range(20):        # vinte arquétipos pequenos que ele NÃO segue
        lista(con, "modern", "Challenge", 32, chave=f"pq{i}",
              cartas=((f"Carta {i}", 4),))
    ids = {d["id"] for d in busca_ligas.alvos(con, "modern", fresco=True)["decks"]}
    assert ids == {"versao:modern:affinity", "versao:modern:oswald",
                   "criterio:modern"}, ids
    p = {d["id"] for d in busca_ligas.alvos(con, "pioneer", fresco=True)["decks"]}
    assert p == {"caixa:pio"}, p


def caso_a_colheita_so_abre_a_liga_quando_ha_alvo():
    con = base()
    pedidos = []

    class _R:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

    indice = "<a href=\"/decklist/modern-league-2026-10-02x\"></a>"

    def _get(url, **_k):
        pedidos.append(url)
        r = _R()
        r.text = indice if "/decklists" in url else ""
        return r

    import datetime as _dt

    class _D(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date(2026, 10, 3)

    def colhe():
        pedidos.clear()
        rg, rp, rd = sources.requests.get, sources.PAUSA_MTGO, sources.date
        sources.requests.get, sources.PAUSA_MTGO, sources.date = _get, 0.0, _D
        try:
            sources.harvest_mtgo(con, 1, {"modern"})
        finally:
            sources.requests.get, sources.PAUSA_MTGO, sources.date = rg, rp, rd
        return [u for u in pedidos if "/decklist/" in u]

    escreve_cfg()                            # Oswald com 0 listas: alvo
    assert colhe(), "com um deck seguido de amostra baixa a liga pede-se"
    escreve_cfg(ligas_busca={"amostra_baixa_max": -1})   # nenhum é baixo
    assert colhe() == [], (
        "sem alvo nenhum, a página de liga de um formato de busca salta-se")


def caso_a_poda_nao_apaga_as_ligas_de_um_formato_de_busca():
    escreve_cfg()
    con = base()
    lista(con, "modern", "League", None, chave="lm")
    lista(con, "premodern", "League", None, chave="lp")
    analysis.prune_leagues(con)
    fmts = {r[0] for r in con.execute(
        "SELECT format FROM decklists WHERE event_tier='League'")}
    assert "modern" in fmts, "a poda apagou ligas de busca — nada se apaga"
    assert "premodern" not in fmts, (
        "num formato com `ligas: false` a poda continua a apagar")


# ---------------------------------------------------------------------------
# 3. O config a sério
# ---------------------------------------------------------------------------
def caso_o_config_a_serio_tem_a_regra_e_a_forma():
    from mtgvault import configio                            # noqa: PLC0415
    texto = io.open(RAIZ / "colecao_config.json", encoding="utf-8").read()
    cfg = json.loads(texto)
    mf = cfg["metagame_fontes"]
    for f in ("pioneer", "legacy"):
        assert mf[f]["min_jogadores_presencial"] == 31, mf[f]
        assert mf[f]["ligas"] == "busca", mf[f]
        assert "tiers" not in mf[f], (
            f"{f}: os tiers HERDAM do _default — uma segunda cópia diverge")
        assert mf[f].get("_nota"), f"{f}: a regra leva as palavras dele ao lado"
    assert mf["modern"]["ligas"] == "busca"
    assert mf["_default"]["min_jogadores_presencial"] == 64
    assert mf["duel-commander"]["ligas"] is True, (
        "o duel-commander CONTA ligas, por decisão dele de 2026-09-07")
    assert cfg["ligas_busca"]["amostra_baixa_max"] == 10
    assert configio.texto(cfg) == texto.replace("\r\n", "\n"), (
        "o colecao_config.json saiu da forma canónica (a lição do ac1f776)")


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
