"""TODOS OS TORNEIOS EM MODERN: LIGAS E PRESENCIAIS DE QUALQUER TAMANHO
(André, 2026-10-05, à letra).

    *"para modern, apenas os decks de Mox Opal, procura todos os torneios !
    incluindo ligas, torneios presenciais"*

A primeira metade (*apenas os decks de Mox Opal*) foi a ordem
`mtg-modern-todo-opal`. Esta é a segunda: abrir as FONTES de Modern. Eram duas
coisas a travá-las, e as duas no `metagame_fontes._default`:

  * **`ligas: false`** — e as ligas não existiam de todo em Modern: zero listas
    com tier `League` em toda a história, contra 125 em `duel-commander`, o
    único formato que as contava. A colheita **salta a página de liga antes de a
    pedir**, por isso isto não se resolvia a consultar a base: tinha de se
    LIGAR e COLHER;
  * **`min_jogadores_presencial: 64`** — na janela havia 14 listas de
    presenciais de Modern, **todas** de eventos com menos de 64 jogadores (12 e
    17), e uma delas joga Mox Opal.

O interruptor é UM SÓ e abre QUATRO portas, porque as quatro lêem o mesmo
`sources.metagame_rules()["tiers"]`: a colheita (`harvest_mtgo`), a gravação
(`store_decklist`), a contagem (`lista_conta`/`counting_sql`) e a poda
(`analysis.prune_leagues`). Um teste por porta — a que faltasse deixava a
funcionalidade meia: colher sem contar, ou contar e apagar na mesma corrida.

E O AVISO, que é a parte que não se vê num número: uma liga é um **5-0 sem
classificação e sem tamanho de campo**. Somada a uma Challenge, a percentagem
do formato passa a medir duas coisas, e medido no dia em que isto entrou ela
**DESCE** (as ligas trazem 5,7 % de Mox Opal contra 6,9 % no resto). Por isso a
página mostra as DUAS contas lado a lado — é a disciplina do *«a somar»* vs *«a
rodar»* de 04/10. Sem isso ele olhava para um número que pode ter mexido só
porque a fonte mudou.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_ligas.py`, que desliga uma peça de cada vez e exige vermelho.

Não abre socket para fora. Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver
`tests/_bateria.py`).
"""
import io
import json
import os
import re
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
        {"grupo": "spml", "formatos": ["modern", "legacy"], "dedicado": True},
    ],
    "caixas": [
        {"slot": "mod", "nome": "Modern — Affinity", "formato": "modern",
         "fonte": "deck", "ref": "MO", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1},
    ],
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": {},
    "cartas_vigiadas": [],
    # A REGRA DESTA ORDEM: só o `modern`. O `_default` fica com a de 2026-09-07
    # e é ele o CONTROLO — é o que prova que os outros formatos não mudaram.
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial",
                               "Qualifier"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "modern": {"min_jogadores_presencial": 0, "ligas": True},
        # O duel-commander vai aqui porque vai no config A SÉRIO, e o fixture
        # tem de ser fiel: o `_default` do config GANHA ao
        # `sources.DEFAULT_METAGAME_BY_FORMAT` do código (é mais específico que
        # os valores de arranque e menos que a secção do formato). Sem a secção,
        # o `ligas: false` do `_default` apagava o `ligas: true` que o código
        # traz para este formato — foi o que este teste me apanhou a assumir.
        "duel-commander": {"tiers": ["Challenge", "Showcase", "Presencial",
                                     "outro"],
                           "min_jogadores_presencial": 0, "ligas": True},
    },
    "decks_por_formato": {
        "_corte_pct": 5.0,
        "_limiar_listas": 1,
        "modern": {
            "nome": "Affinity (Mox Opal)", "em": "2026-10-05",
            "criterio": {"carta": "Mox Opal", "protege_todas": True,
                         "versoes_todas": True},
            "versoes": [{"id": "versao:modern:alfa", "arquetipo_id": 1,
                         "nome": "Alfa", "listas": 4, "deck": "caixa:mod",
                         "principal": True}],
            "versao": "versao:modern:alfa",
        },
        # O Legacy é inclusivo para a PROTECÇÃO e não conta ligas: é o controlo
        # do `sem_ligas` num formato que não as tem.
        "legacy": {
            "nome": "Legacy", "em": "2026-10-05",
            "criterio": {"carta": "Mox Opal", "protege_todas": True},
            "versoes": [],
        },
    },
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
    sources._CONFIG_CACHE = None
    return d


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import analysis, db, sources, versoes       # noqa: E402

CATALOGO = [
    ("Mox Opal", "som", "2010-10-01", 300.0, "Legendary Artifact"),
    ("Kappa Cannoneer", "unf", "2022-10-07", 20.0, "Artifact Creature"),
]
_ABERTAS = []


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
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def lista(con, fmt="modern", tier="Challenge", jog=64, data=DEPOIS,
          cartas=(("Mox Opal", 4),), aid=1, chave=None):
    """Mete uma decklist na base, com o tier e o nº de jogadores que se quiser."""
    chave = chave or f"k-{fmt}-{tier}-{jog}-{data}-{aid}-{id(cartas)}"
    con.execute("INSERT OR IGNORE INTO archetypes (id, format, label) "
                "VALUES (?,?,?)", (aid, fmt, f"cluster {aid}"))
    con.execute(
        """INSERT INTO decklists (format, source, source_key, event_name,
           event_date, event_tier, event_players, player, archetype_id,
           content_hash) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (fmt, "mtgo", chave, f"{fmt} {tier}", data, tier, jog,
         f"j-{chave}", aid, f"h-{chave}"))
    did = con.execute("SELECT last_insert_rowid() i").fetchone()["i"]
    for nm, q in cartas:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                    " quantity, board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


# ---------------------------------------------------------------------------
# 1. A REGRA: o modern aceita ligas e presenciais de qualquer tamanho
# ---------------------------------------------------------------------------
def caso_o_modern_aceita_ligas_e_presenciais_de_qualquer_tamanho():
    escreve_cfg()
    r = sources.metagame_rules("modern")
    assert "League" in r["tiers"], (
        "o `ligas: true` do modern tem de acrescentar o tier `League` — é ele "
        f"que abre as quatro portas. Deu {r['tiers']}")
    assert int(r.get("min_jogadores_presencial") or 0) == 0, (
        "um presencial de 17 jogadores tem de contar: ele disse «torneios "
        "presenciais» sem qualificar tamanho")
    # A LISTA DE TIERS NÃO SE REPETE NO CONFIG: a secção do modern não tem a
    # chave `tiers` e herda-a do `_default`. Uma segunda cópia divergia da
    # primeira no dia em que ele mexesse numa delas.
    assert "tiers" not in (CFG["metagame_fontes"]["modern"]), (
        "a secção do modern não pode repetir a lista de tiers — herda-a do "
        "`_default` e acrescenta-lhe `League` pelo `ligas`")
    for t in CFG["metagame_fontes"]["_default"]["tiers"]:
        assert t in r["tiers"], f"o modern perdeu o tier {t} do _default"


def caso_os_outros_formatos_nao_mudaram_de_regra():
    """O CONTROLO desta ordem: só o Modern mudou."""
    escreve_cfg()
    for fmt in ("legacy", "premodern", "standard", "pioneer", "vintage"):
        r = sources.metagame_rules(fmt)
        assert "League" not in r["tiers"], (
            f"{fmt} passou a contar ligas e ele não lhe tocou — a regra de "
            "2026-09-07 continua a valer onde ele não a mudou")
        assert int(r.get("min_jogadores_presencial") or 0) == 64, (
            f"{fmt} perdeu o mínimo de 64 jogadores nos presenciais")
    # O duel-commander já contava ligas ANTES desta ordem e continua a contar —
    # era o ÚNICO formato que as contava, e não se lhe tocou.
    dc = sources.metagame_rules("duel-commander")
    assert "League" in dc["tiers"], (
        f"o duel-commander perdeu as ligas que já tinha: {dc['tiers']}")
    assert int(dc.get("min_jogadores_presencial") or 0) == 0, dc


def caso_a_pergunta_das_ligas_vive_num_sitio_so():
    """`sources.conta_ligas` e `sql_sem_ligas` — e ninguém compara o tier à mão.

    O `event_tier = 'League'` escrito numa segunda consulta discordava desta num
    dia qualquer, em silêncio. É a lição do `e_foil`, do `precos.sql()` e do
    `venda.mostrar`.
    """
    escreve_cfg()
    assert sources.conta_ligas("modern") is True
    assert sources.conta_ligas("legacy") is False
    cond, par = sources.sql_sem_ligas("d")
    assert par == ["League"] and "d.event_tier" in cond
    # `NULL <> 'League'` em SQL não é verdadeiro: é NULL. Sem o `IS NULL OR`, uma
    # lista antiga sem tier caía fora das DUAS contas.
    assert "IS NULL" in cond, (
        "o predicado tem de deixar passar uma lista com `event_tier` a NULL — "
        "a coluna andou anos a ser lida sem ser escrita")
    # Ninguém volta a comparar o tier à mão fora do `sources`.
    maus = []
    for p in sorted(RAIZ.glob("*.py")) + sorted((RAIZ / "mtgvault").glob("*.py")):
        if p.name == "sources.py":
            continue
        t = io.open(p, encoding="utf-8").read()
        for m in re.finditer(r"event_tier\s*(?:<>|!=|==)\s*['\"]League['\"]", t):
            maus.append(f"{p.name}:{t[:m.start()].count(chr(10)) + 1}")
    assert not maus, (
        "o «isto é uma liga?» vive num sítio só (`sources.sql_sem_ligas` / "
        f"`conta_ligas`); comparado à mão em: {maus}")


# ---------------------------------------------------------------------------
# 2. AS QUATRO PORTAS
# ---------------------------------------------------------------------------
def caso_a_colheita_deixa_de_saltar_a_pagina_de_liga_de_modern():
    """A primeira porta. Sem ela nada disto serve: a página nem se pedia.

    Não vai à rede — troca o `requests.get` do `sources` por um que conta o que
    lhe pediram e devolve uma página vazia.
    """
    escreze = escreve_cfg()
    assert escreze  # o config está escrito
    con = base()
    pedidos = []

    class _Resp:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

    indice = ("<a href=\"/decklist/modern-league-2026-10-02x\"></a>"
              "<a href=\"/decklist/legacy-league-2026-10-02y\"></a>")

    def _get(url, **_k):
        pedidos.append(url)
        r = _Resp()
        r.text = indice if "/decklists" in url else ""
        return r

    real_get, real_pausa = sources.requests.get, sources.PAUSA_MTGO
    sources.requests.get, sources.PAUSA_MTGO = _get, 0.0
    try:
        import datetime as _dt
        hoje = _dt.date(2026, 10, 3)

        class _D(_dt.date):
            @classmethod
            def today(cls):
                return hoje
        real_date = sources.date
        sources.date = _D
        try:
            sources.harvest_mtgo(con, 1, {"modern", "legacy"})
        finally:
            sources.date = real_date
    finally:
        sources.requests.get, sources.PAUSA_MTGO = real_get, real_pausa

    paginas = [u for u in pedidos if "/decklist/" in u]
    assert any("modern-league" in u for u in paginas), (
        "a página de liga de MODERN tem de ser pedida — com `ligas: false` a "
        f"colheita saltava-a antes do pedido. Pediu: {paginas}")
    assert not any("legacy-league" in u for u in paginas), (
        "a de LEGACY continua a saltar-se: só o Modern mudou. "
        f"Pediu: {paginas}")


def caso_uma_lista_de_liga_de_modern_grava_se():
    """A segunda porta: o `store_decklist` recusava-a à entrada."""
    escreve_cfg()
    con = base()
    did = sources.store_decklist(
        con, source="mtgo", source_key="liga-1", fmt="modern",
        cards=[("main", "Mox Opal", 4)], event_name="Modern League",
        event_date=DEPOIS, player="alguem")
    assert did, "uma lista de liga de Modern tem de se GRAVAR"
    r = con.execute("SELECT event_tier FROM decklists WHERE id=?",
                    (did,)).fetchone()
    assert r["event_tier"] == "League", r["event_tier"]
    # E a de LEGACY continua recusada — o controlo.
    assert sources.store_decklist(
        con, source="mtgo", source_key="liga-2", fmt="legacy",
        cards=[("main", "Mox Opal", 4)], event_name="Legacy League",
        event_date=DEPOIS, player="outro") is None, (
        "a liga de Legacy continua a não se guardar")


def caso_uma_lista_de_liga_de_modern_entra_na_contagem():
    """A terceira porta: o `lista_conta` e o `counting_sql`, que são a MESMA
    resposta em Python e em SQL."""
    escreve_cfg()
    con = base()
    did = lista(con, tier="League", jog=None, chave="conta-liga")
    row = con.execute("SELECT * FROM decklists WHERE id=?", (did,)).fetchone()
    assert sources.lista_conta(row, "modern") is True, (
        "uma liga de Modern tem de contar para o metagame")
    sql, par = sources.counting_sql("modern", "d")
    n = con.execute(f"SELECT COUNT(*) c FROM decklists d WHERE d.format='modern'"
                    f" AND {sql}", par).fetchone()["c"]
    assert n >= 1, "o `counting_sql` tem de contar a liga tal como o `lista_conta`"
    # O SQL e o Python não podem discordar — é o defeito que o `counting_sql`
    # existe para não ter.
    todas = con.execute("SELECT * FROM decklists WHERE format='modern'").fetchall()
    py = sum(1 for r in todas if sources.lista_conta(r, "modern"))
    assert py == n, f"Python diz {py} e o SQL diz {n}"


def caso_um_presencial_pequeno_de_modern_entra_na_contagem():
    escreve_cfg()
    con = base()
    did = lista(con, tier="Presencial", jog=17, chave="pres-17")
    row = con.execute("SELECT * FROM decklists WHERE id=?", (did,)).fetchone()
    assert sources.lista_conta(row, "modern") is True, (
        "um presencial de 17 jogadores tem de contar em Modern")
    # O MESMO evento em Legacy continua fora: é o `min_jogadores_presencial`.
    assert sources.lista_conta(dict(row, format="legacy"), "legacy") is False, (
        "em Legacy um presencial de 17 continua a não contar")


def caso_a_poda_nao_apaga_as_ligas_de_modern():
    """A quarta porta, e sem ela as outras três não valiam nada: a liga entrava
    às 03:30 e o `prune_leagues` apagava-a na MESMA corrida, minutos depois."""
    escreve_cfg()
    con = base()
    lista(con, tier="League", jog=None, chave="poda-mod")
    lista(con, fmt="legacy", tier="League", jog=None, aid=2, chave="poda-leg")
    n = analysis.prune_leagues(con)
    fica = con.execute("SELECT format FROM decklists "
                       "WHERE event_tier='League'").fetchall()
    fmts = sorted(r["format"] for r in fica)
    assert fmts == ["modern"], (
        f"a liga de Modern tem de FICAR e a de Legacy de sair; ficaram {fmts}")
    assert n == 1, f"devia apagar só a de Legacy, apagou {n}"


# ---------------------------------------------------------------------------
# 3. AS DUAS CONTAS LADO A LADO
# ---------------------------------------------------------------------------
def caso_a_contagem_com_e_sem_ligas_aparece_lado_a_lado():
    """Uma liga é um 5-0 sem classificação e sem campo: somada a uma Challenge,
    a percentagem mede duas coisas. As duas contas vão sempre as duas."""
    escreve_cfg()
    con = base()
    # 2 de 4 Challenges jogam a carta (50 %); 1 de 6 ligas joga-a (17 %).
    for k in range(2):
        lista(con, tier="Challenge", chave=f"c-com-{k}")
    for k in range(2):
        lista(con, tier="Challenge", cartas=(("Kappa Cannoneer", 4),),
              chave=f"c-sem-{k}")
    lista(con, tier="League", jog=None, chave="l-com")
    for k in range(5):
        lista(con, tier="League", jog=None, cartas=(("Kappa Cannoneer", 4),),
              chave=f"l-sem-{k}")

    d = versoes.listas_do_formato(con)["modern"]
    assert d["listas"] == 3 and d["total"] == 10, d
    assert d["pct"] == 30.0, d
    assert d["sem_ligas"] == {"listas": 2, "total": 4, "pct": 50.0}, d["sem_ligas"]
    assert d["ligas"]["listas"] == 1 and d["ligas"]["total"] == 6, d["ligas"]
    assert d["ligas"]["pct"] == 16.7, d["ligas"]
    assert d["ligas"]["conta"] is True
    # A SOMA FECHA SEMPRE: as duas metades são o total. Uma metade perdida pelo
    # caminho é meia verdade com cara de verdade (é a regra do
    # `confirmado.metades`).
    assert d["sem_ligas"]["listas"] + d["ligas"]["listas"] == d["listas"]
    assert d["sem_ligas"]["total"] + d["ligas"]["total"] == d["total"]
    # E AQUI AS LIGAS DILUEM: é o caso real medido a 05/10 (5,7 % contra 6,9 %).
    assert d["ligas"]["pct"] < d["sem_ligas"]["pct"], (
        "neste cenário as ligas jogam a carta MENOS do que os torneios, por "
        "isso a percentagem de cima tem de ser mais baixa do que a de baixo")


def caso_num_formato_sem_ligas_as_duas_contas_sao_iguais():
    """O controlo: isto não muda nada no Legacy."""
    escreve_cfg()
    con = base()
    for k in range(3):
        lista(con, fmt="legacy", tier="Challenge", aid=2, chave=f"lg-{k}")
    d = versoes.listas_do_formato(con)["legacy"]
    assert d["sem_ligas"]["listas"] == d["listas"], d
    assert d["sem_ligas"]["total"] == d["total"], d
    assert d["sem_ligas"]["pct"] == d["pct"], d
    assert d["ligas"] == {"listas": 0, "total": 0, "pct": 0.0, "conta": False}, (
        d["ligas"])


def caso_a_pagina_desenha_as_duas_contas():
    """O JavaScript tem de as pôr no ecrã — não basta estarem no payload.

    Lê o TEXTO do `decks.py`: a função `ligasHTML` tem de existir, ser chamada
    do bloco do critério, e dizer as duas coisas.
    """
    t = io.open(RAIZ / "decks.py", encoding="utf-8").read()
    assert "function ligasHTML" in t, (
        "falta o `ligasHTML`: sem ele o payload traz as duas contas e a página "
        "mostra só uma")
    assert "ligasHTML(u.protege)" in t, (
        "o `ligasHTML` tem de ser CHAMADO do bloco do critério")
    i = t.find("function ligasHTML")
    corpo = t[i:i + 1600]
    assert "sem_ligas" in corpo and "ligas" in corpo, corpo[:200]
    assert "sem ligas" in corpo, "a página tem de DIZER «sem ligas» por extenso"
    for frase in ("diluem", "para cima"):
        assert frase in corpo, (
            f"falta o caso «{frase}»: a página tem de dizer em que SENTIDO as "
            "ligas mexeram no número, senão ele não sabe se subiu por mérito")
    assert "l.conta" in corpo, (
        "num formato que não conte ligas não se desenha nada — um bloco com "
        "dois zeros é ruído")


# ---------------------------------------------------------------------------
# 4. A ANOTAÇÃO QUE PERDEU O CLUSTER
# ---------------------------------------------------------------------------
def caso_a_anotacao_que_perdeu_o_cluster_e_dita():
    """As 430 listas das ligas fundiram dois clusters e o deck PRINCIPAL ficou a
    apontar para um grupo vazio. Nada dava erro — é o padrão do `event_tier`."""
    escreve_cfg()
    con = base()
    # O cluster 1 é o anotado/principal e fica SEM listas; o deck foi para o 2.
    for k in range(5):
        lista(con, tier="Challenge", aid=2, chave=f"novo-{k}")
    d = versoes.versoes_derivadas(con, "modern", sources.config())
    orfas = d["orfas"]
    assert len(orfas) == 1, (
        "o deck principal está a apontar para um cluster sem uma única lista "
        f"na janela e isso tem de ser DITO; deu {orfas}")
    o = orfas[0]
    assert o["arquetipo_id"] == 1 and o["principal"] is True, o
    assert o["candidato"] and o["candidato"]["arquetipo_id"] == 2, (
        "o aviso tem de dizer para onde o deck foi — o maior grupo sem "
        f"anotação. Deu {o['candidato']}")
    assert o["candidato"]["listas"] == 5, o["candidato"]
    # E a página desenha-o.
    t = io.open(RAIZ / "decks.py", encoding="utf-8").read()
    assert "u.orfas" in t, "o aviso tem de estar no JavaScript da página"
    assert "ficha aviso" in t, "e em destaque, não num rodapé"


def caso_uma_versao_legitimamente_adormecida_nao_leva_aviso():
    """O crivo é estreito de propósito: só a principal ou a escolhida.

    As conhecidas sem listas (o Grinding Station) têm legitimamente zero — e um
    aviso permanente a piscar é um aviso que se deixa de ler.
    """
    escreve_cfg(decks_por_formato=dict(
        CFG["decks_por_formato"],
        modern=dict(
            CFG["decks_por_formato"]["modern"],
            versoes=[
                {"id": "versao:modern:alfa", "arquetipo_id": 1, "nome": "Alfa",
                 "deck": "caixa:mod", "principal": True},
                {"id": "versao:modern:dorme", "arquetipo_id": 9,
                 "nome": "Grinding Station"},
            ])))
    con = base()
    lista(con, tier="Challenge", aid=1, chave="viva")
    # O 9 existe e só tem listas ANTES da janela.
    lista(con, tier="Challenge", aid=9, data="2026-09-20", chave="dorme")
    d = versoes.versoes_derivadas(con, "modern", sources.config())
    assert d["orfas"] == [], (
        "a versão adormecida NÃO é uma órfã: ela não clama ser o deck. "
        f"Deu {d['orfas']}")
    por_id = {v["id"]: v for v in d["versoes"]}
    assert por_id["versao:modern:dorme"]["listas"] == 0
    assert por_id["versao:modern:alfa"]["listas"] == 1


def caso_o_config_a_serio_re_aponta_a_affinity_e_guarda_o_id_antigo():
    """Nada se apaga: o 7614 ficou arquivado com a data e a razão."""
    from mtgvault import configio                            # noqa: PLC0415
    cfg = json.loads(io.open(RAIZ / "colecao_config.json",
                             encoding="utf-8").read())
    mf = cfg["metagame_fontes"]
    assert mf["modern"]["ligas"] is True
    assert mf["modern"]["min_jogadores_presencial"] == 0
    assert "tiers" not in mf["modern"], (
        "a secção do modern herda os tiers do `_default` — uma segunda cópia "
        "diverge")
    assert mf["_default"]["ligas"] is False and \
        mf["_default"]["min_jogadores_presencial"] == 64, (
        "o `_default` não se toca: é ele que serve os outros formatos")
    assert mf["duel-commander"]["ligas"] is True, (
        "o duel-commander era o ÚNICO formato que contava ligas antes desta "
        "ordem, e continua a contá-las")
    assert mf["modern"].get("_nota"), (
        "a regra nova leva a razão e a data ao lado, como as outras dele")
    m = cfg["decks_por_formato"]["modern"]
    v = next(x for x in m["versoes"]
             if x["id"] == "versao:modern:izzet-pinnacle")
    assert v["arquetipo_id"] == 5100, (
        "a Affinity passou para o cluster 5100 quando as ligas fundiram a "
        f"divisão do 7614; deu {v['arquetipo_id']}")
    antes = v.get("_arquetipo_id_antes") or {}
    assert antes.get("arquetipo_id") == 7614, (
        "o id antigo não se apaga — fica arquivado para se poder repor")
    assert antes.get("ate") == "2026-10-05" and antes.get("porque"), antes
    assert v.get("principal") is True, "a marca `principal` não se perdeu"
    assert v.get("deck") == "caixa:modern", (
        "o ponteiro para a caixa com a lista de qualificação não se perdeu")
    # A FORMA do ficheiro: round-trip pelo `configio.escrever`, byte a byte.
    alvo = _TMP / "rt.json"
    configio.escrever(cfg, alvo)
    assert alvo.read_bytes() == (RAIZ / "colecao_config.json").read_bytes(), (
        "o `colecao_config.json` saiu da forma canónica do `configio.escrever`")


# ---------------------------------------------------------------------------
# 5. O RITMO DOS PEDIDOS, E O DIA DE HOJE
# ---------------------------------------------------------------------------
def caso_a_colheita_espaca_os_pedidos_e_repete_um_erro_de_rede():
    """O mtgo.com não tem `robots.txt` (404, sondado a 05/10), por isso não há
    regra escrita a respeitar além do RITMO — e ele deu `read timeout` em 2 de
    15 pedidos. Uma página de liga perdida por um timeout ficava perdida para
    sempre: a recolha só volta 3 dias atrás."""
    assert sources.PAUSA_MTGO > 0, (
        "a pausa entre pedidos ao mtgo.com não pode ser zero em produção — era "
        "o único scraper do vault sem ritmo")
    dormiu, tentou = [], []

    class _Resp:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

    def _get(url, **_k):
        tentou.append(url)
        if len(tentou) == 1:
            raise sources.requests.RequestException("read timeout")
        return _Resp()

    real_get, real_sleep = sources.requests.get, sources.time.sleep
    sources.requests.get = _get
    sources.time.sleep = lambda s: dormiu.append(s)
    try:
        r = sources._get_mtgo("https://www.mtgo.com/x")
    finally:
        sources.requests.get, sources.time.sleep = real_get, real_sleep
    assert r.status_code == 200, "a segunda tentativa tem de valer"
    assert len(tentou) == 2, f"devia tentar 2 vezes, tentou {len(tentou)}"
    assert len(dormiu) == 2 and dormiu[0] > 0, (
        f"tem de dormir ANTES de cada pedido; dormiu {dormiu}")
    assert dormiu[1] > dormiu[0], (
        f"a segunda espera tem de ser mais longa; dormiu {dormiu}")


def caso_um_erro_de_http_nao_se_repete():
    """Um 404 não é azar, é a página. Repeti-lo era gastar o dobro dos pedidos."""
    tentou = []

    class _Resp:
        status_code = 404
        text = ""

        def raise_for_status(self):
            return None

    def _get(url, **_k):
        tentou.append(url)
        return _Resp()

    real_get, real_pausa = sources.requests.get, sources.PAUSA_MTGO
    sources.requests.get, sources.PAUSA_MTGO = _get, 0.0
    try:
        r = sources._get_mtgo("https://www.mtgo.com/y")
    finally:
        sources.requests.get, sources.PAUSA_MTGO = real_get, real_pausa
    assert r.status_code == 404 and len(tentou) == 1, tentou


def caso_a_colheita_comeca_em_ontem_por_omissao():
    """O `daily` das 03:30 não pode ganhar um pedido por formato a não trazer
    nada: a página de hoje está vazia a essa hora. O `--hoje` é opt-in."""
    import datetime as _dt
    pedidos = []

    class _Resp:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

    def _get(url, **_k):
        pedidos.append(url)
        return _Resp()

    hoje = _dt.date(2026, 10, 5)

    class _D(_dt.date):
        @classmethod
        def today(cls):
            return hoje

    con = base()
    real_get, real_pausa, real_date = (sources.requests.get,
                                       sources.PAUSA_MTGO, sources.date)
    sources.requests.get, sources.PAUSA_MTGO, sources.date = _get, 0.0, _D
    try:
        sources.harvest_mtgo(con, 2, {"modern"})
        sem = [u for u in pedidos if "/decklists/" in u or "year=" in u]
        assert not any("2026-10-05" in u for u in sem), (
            f"por omissão não se pede o dia de HOJE; pediu {sem}")
        pedidos.clear()
        sources.harvest_mtgo(con, 2, {"modern"}, incluir_hoje=True)
        com = [u for u in pedidos if "/decklists/" in u or "year=" in u]
        assert len(com) > len(sem), (
            "com `incluir_hoje=True` tem de haver um dia a mais na lista")
    finally:
        (sources.requests.get, sources.PAUSA_MTGO,
         sources.date) = real_get, real_pausa, real_date


# ---------------------------------------------------------------------------
# 6. O ORÇAMENTO DAS PÁGINAS
# ---------------------------------------------------------------------------
def caso_o_javascript_da_aba_decks_saiu_da_casca():
    """O tecto não subiu pela terceira vez: o JavaScript saiu, como a ordem de
    04/10 deixou escrito."""
    import decks as decks_pag                                # noqa: PLC0415
    assert decks_pag.NOME_JS == "decks.js"
    js = decks_pag.js_texto()
    assert len(js) > 20000, "o `js_texto` tem de ser o JavaScript inteiro"
    assert "%JS_DADOS%" not in js, "o `JS_DADOS` tem de ficar substituído"
    v = decks_pag.js_versao(js)
    assert re.fullmatch(r"[0-9a-f]{12}", v), v
    # O hash é do CONTEÚDO: texto diferente, URL diferente.
    assert decks_pag.js_versao(js + " ") != v
    casca = decks_pag.casca()
    assert f'src="decks.js?v={v}"' in casca, (
        "a casca tem de apontar para o `.js` com o hash do texto que ESTE "
        "processo tem")
    assert js[:400] not in casca, (
        "o JavaScript não pode estar embutido na casca — é isso que o tira do "
        "orçamento e o torna cacheável")
    # E as DUAS listas de publicação têm de o levar, senão o site abre a casca
    # e não desenha nada.
    from mtgvault import publicar                            # noqa: PLC0415
    assert "decks.js" in publicar.PUBLICAVEIS, (
        "falta o `decks.js` no `publicar.PUBLICAVEIS` — a tarefa de 30 min "
        "publicava a casca sem o ficheiro que ela pede")
    yml = io.open(RAIZ / ".github/workflows/daily.yml", encoding="utf-8").read()
    add = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert " decks.js " in add or add.rstrip().endswith(" decks.js"), (
        "falta o `decks.js` no `git add` do daily.yml")


def caso_a_casca_da_aba_decks_cabe_no_orcamento():
    import decks as decks_pag                                # noqa: PLC0415
    n = len(decks_pag.casca().encode("utf-8"))
    assert n <= decks_pag.TECTO_CASCA, (
        f"a casca da aba Decks tem {n:,} bytes e o tecto é "
        f"{decks_pag.TECTO_CASCA:,}")
    # E o tecto DESCEU: agora que o JavaScript está fora, ele mede HTML e CSS.
    assert decks_pag.TECTO_CASCA <= 48 * 1024, (
        "o tecto não pode voltar a subir para acomodar JavaScript — o passo "
        "seguinte é tirar o CSS, não subir isto")


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
