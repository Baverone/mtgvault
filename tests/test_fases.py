"""AS REGRAS DA VENDA E AS FASES DA ARRUMAÇÃO (André, 2026-10-01 e 2026-10-02).

Cada caso aqui chumba se a regra for RETIRADA — é o padrão do `_provar_chumba`
que a regra dos 5 % da Reserved List já usa. O que se tranca:

  1. as TRÊS listas de terras (duais, shock, fetch) **derivam-se do catálogo**;
     sem `oracle_text` a derivação **levanta** em vez de devolver uma lista
     curta (uma protecção vazia em silêncio é o que a ordem proíbe);
  2. **R1** — das duais originais protegem-se QUATRO fora dos decks e a quinta
     é candidata, apesar de serem Reserved List (*"para elas manda a R1, que é
     mais específica"*);
  3. **R2/R3** — uma shockland non-foil extra, fora de qualquer deck, nunca
     aparece nos candidatos. Nem nenhuma outra cópia de uma shock/fetch:
     *"todas as cópias"*, todos os acabamentos, todas as línguas;
  4. **R4** — uma carta de Reserved List que ele joga nunca aparece; a que ele
     NÃO joga não é protegida por aqui (segue a regra dos 5 %);
  5. **RD** — uma cópia alocada a um deck cujo `estado` protege nunca aparece, e
     uma caixa `candidata` liberta as cartas dela;
  6. **a omissão do `estado` PROTEGE** — um deck sem estado escrito não manda
     uma única carta para a venda;
  7. **R5** — uma carta jogada no arquétipo há 20 dias está protegida e uma de
     há 40 não. Sem amostra (menos de `MIN_LISTAS_RESERVA` listas) a reserva
     automática fica VAZIA;
  8. **R5b** — uma staple de sideboard de Premodern acima do corte está
     protegida, e abaixo do corte não;
  9. a **trava** de 2026-10-12 recusa a saída de venda, e deixa-a passar no dia;
 10. a fila de candidatos sai **por valor decrescente** e um playset é **uma**
     foto de quatro cartas;
 11. cada exclusão guarda o **motivo em português** e **qual** das regras a
     apanhou;
 12. as protecções valem **também no motor** (`loadout.sell_list`), e não só na
     página — uma protecção que valesse numa página só deixava a aba Vender a
     oferecer a mesma carta.

A IDENTIDADE por CARTA-ASSINATURA e o botão *«não é necessária»* estão em
`tests/test_decks_finais.py`.

Não toca na rede nem na base a sério. Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB`
(ver `tests/_bateria.py`: os ficheiros que acompanham a base saem da pasta da
`MTGVAULT_DB`, e sem a fixar a bateria escrevia no `data/` a sério).
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

# ---------------------------------------------------------------------------
# O catálogo de mentira, com ORACLE TEXT A SÉRIO
# ---------------------------------------------------------------------------
# As dez shocklands e as dez fetchlands, com o texto REAL da Scryfall (trechos
# capturados do catálogo deste PC a 2026-10-01). É o que a regra do projecto
# manda: um trecho real como fixture, nunca um `mock` da biblioteca.
SHOCK = [
    ("Hallowed Fountain", "Plains Island", "{W}", "{U}"),
    ("Watery Grave", "Island Swamp", "{U}", "{B}"),
    ("Blood Crypt", "Swamp Mountain", "{B}", "{R}"),
    ("Stomping Ground", "Mountain Forest", "{R}", "{G}"),
    ("Temple Garden", "Forest Plains", "{G}", "{W}"),
    ("Godless Shrine", "Plains Swamp", "{W}", "{B}"),
    ("Steam Vents", "Island Mountain", "{U}", "{R}"),
    ("Overgrown Tomb", "Swamp Forest", "{B}", "{G}"),
    ("Sacred Foundry", "Mountain Plains", "{R}", "{W}"),
    ("Breeding Pool", "Forest Island", "{G}", "{U}"),
]
FETCH = [
    ("Flooded Strand", "a Plains or Island"),
    ("Polluted Delta", "an Island or Swamp"),      # «an», não «a» — ver o módulo
    ("Bloodstained Mire", "a Swamp or Mountain"),
    ("Wooded Foothills", "a Mountain or Forest"),
    ("Windswept Heath", "a Forest or Plains"),
    ("Marsh Flats", "a Plains or Swamp"),
    ("Scalding Tarn", "an Island or Mountain"),    # idem
    ("Verdant Catacombs", "a Swamp or Forest"),
    ("Arid Mesa", "a Mountain or Plains"),
    ("Misty Rainforest", "a Forest or Island"),
]
# As terras que NÃO podem entrar: têm o mesmo `type_line` (ou o mesmo género de
# texto) e não são do ciclo. Se a derivação as apanhar, a conta deixa de dar 10
# e o caso chumba — que é exactamente o controlo que se quer.
ISCAS = [
    # As duais originais: dois sub-tipos básicos e nenhum texto.
    ("Tundra", "Land — Plains Island", "({T}: Add {W} or {U}.)"),
    ("Underground Sea", "Land — Island Swamp", "({T}: Add {U} or {B}.)"),
    # Surveil land (MKM): dois sub-tipos básicos, entra SEMPRE virada.
    ("Undercity Sewers", "Land — Island Swamp",
     "({T}: Add {U} or {B}.) This land enters tapped. When this land enters, "
     "surveil 1."),
    # Slow land (DMU): dois sub-tipos básicos, entra virada por condição.
    ("Contaminated Aquifer", "Land — Island Swamp",
     "({T}: Add {U} or {B}.) This land enters tapped."),
    # Procura uma BÁSICA qualquer: paga 1 de vida e sacrifica-se, mas não nomeia
    # dois tipos — não é deste ciclo.
    ("Prismatic Vista", "Land",
     "{T}, Pay 1 life, Sacrifice Prismatic Vista: Search your library for a "
     "basic land card, put it onto the battlefield, then shuffle."),
    # Terra rara de Onslaught que o filtro SEM oracle text apanhava.
    ("Riptide Laboratory", "Land",
     "{T}: Add {C}. {1}{U}, {T}: Return target Wizard you control to its "
     "owner's hand."),
]

OUTRAS = [
    # (nome, edição, nº, reserved, cor, tipo)
    ("Sol Ring", "c21", "263", 0, "", "Artifact"),
    ("Dark Ritual", "4ed", "129", 0, "B", "Instant"),
    ("Gilded Drake", "usg", "76", 1, "U", "Creature"),      # RL que ele JOGA
    ("Taiga", "3ed", "287", 1, "RG", "Land"),               # RL que NÃO joga
    ("Force of Will", "all", "42", 0, "U", "Instant"),      # a reserva
    ("Oswald Fiddlebender", "clb", "60", 0, "W", "Creature"),  # a assinatura
    ("Swan Song", "the", "48", 0, "U", "Instant"),          # 30 % do consenso
]

HOJE = date.today().isoformat()

CFG_BASE = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    # Um grupo só, sem regras de material: o que se mede aqui são as quatro
    # protecções, e uma regra de língua/acabamento punha substitutos pelo meio.
    "regras_por_formato": [{"grupo": "livre", "formatos": ["modern", "premodern"]}],
    "metagame_fontes": {"_default": {"tiers": ["Challenge"],
                                     "min_jogadores_presencial": 0}},
    "caixas": [
        {"slot": "d1", "nome": "Deck Um", "formato": "modern", "fonte": "deck",
         "ref": "Deck Um", "balde": "Colecção", "estado": "montada",
         "prioridade": 1, "reserva_assinatura": ["Oswald Fiddlebender"]},
        {"slot": "d2", "nome": "Deck Dois", "formato": "premodern",
         "fonte": "deck", "ref": "Deck Dois", "balde": "Colecção",
         "estado": "permanente", "prioridade": 2},
    ],
    # A TRAVA passou a MANUAL a 2026-10-04 (era `congelado_ate: "2026-10-12"`,
    # que se levantava sozinha no dia 12). Ver a secção 7.
    "venda": {"mostrar": True, "congelada": True},
    # Sem limiar (foi apagado a 2026-10-02) e com o corte das staples no máximo
    # da curva, para a R5b não morder nos casos que medem outras regras.
    "reserva": {"janela_dias": 30, "staples_premodern_pct": 90},
}
CFG_PATH = _TMP / "cfg.json"


def escreve_cfg(**muda):
    cfg = json.loads(json.dumps(CFG_BASE))
    for k, v in muda.items():
        if k == "caixas_estado":
            for c in cfg["caixas"]:
                if c["slot"] in v:
                    c["estado"] = v[c["slot"]]
        elif k == "caixa_chave":
            for c in cfg["caixas"]:
                if c["slot"] in v:
                    c.update(v[c["slot"]])
        elif k == "sem_estado":
            for c in cfg["caixas"]:
                if c["slot"] in v:
                    c.pop("estado", None)
        elif k == "staples_pct":
            cfg["reserva"]["staples_premodern_pct"] = v
        elif k == "congelada":
            if v is None:
                cfg["venda"].pop("congelada", None)
            else:
                cfg["venda"]["congelada"] = v
        elif k == "congelado_ate":
            # A chave ANTIGA, para os casos que provam que já não tem efeito.
            if v is None:
                cfg["venda"].pop("congelado_ate", None)
            else:
                cfg["venda"]["congelado_ate"] = v
        else:
            cfg[k] = v
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    from mtgvault import sources
    sources._CFG_CACHE.clear()
    return cfg


CFG_PATH.write_text(json.dumps(CFG_BASE, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
# TEM de ser fixa junto com o HOME: os ficheiros que acompanham a base saem de
# `db.pasta_dados()`, que é a pasta da MTGVAULT_DB (ver tests/_bateria.py).
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import db, fases, loadout, sources, venda  # noqa: E402

_ABERTAS = []


# ---------------------------------------------------------------------------
# A base de mentira
# ---------------------------------------------------------------------------
def _carta(con, i, nm, sc, num, rl, ci, tl, texto, finishes=("nonfoil", "foil")):
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line,
           oracle_text, cmc, color_identity, finishes, released_at, legalities,
           digital, reserved, set_type)
           VALUES (?,?,?,?,?,?,'en','rare',?,?,0,?,?,'2005-10-07',?,0,?,'expansion')""",
        (f"id-{i}", f"or-{i}", nm, sc, f"Set {sc.upper()}", num, tl, texto, ci,
         json.dumps(list(finishes)), json.dumps({"modern": "legal",
                                                 "premodern": "legal"}), rl))
    for fin in finishes:
        con.execute("""INSERT OR REPLACE INTO price_latest (scryfall_id, source,
                       finish, date, low, trend, receita)
                       VALUES (?,'cardmarket',?,?,?,?,'unico')""",
                    (f"id-{i}", fin, HOJE, 10.0 + i, 10.0 + i))


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    i = 0
    for nm, sub, m1, m2 in SHOCK:
        _carta(con, i, nm, "rav", str(100 + i), 0, "".join(
            c for c in (m1 + m2) if c in "WUBRG"), f"Land — {sub}",
            f"({{T}}: Add {m1} or {m2}.)\nAs {nm} enters, you may pay 2 life. "
            f"If you don't, it enters tapped.")
        i += 1
    for nm, alvo in FETCH:
        _carta(con, i, nm, "ons", str(200 + i), 0, "", "Land",
               f"{{T}}, Pay 1 life, Sacrifice {nm}: Search your library for "
               f"{alvo} card, put it onto the battlefield, then shuffle.")
        i += 1
    for nm, tl, texto in ISCAS:
        _carta(con, i, nm, "isc", str(300 + i), 0, "", tl, texto)
        i += 1
    for nm, sc, num, rl, ci, tl in OUTRAS:
        _carta(con, i, nm, sc, num, rl, ci, tl, "")
        i += 1
    for nome, fmt, cartas in (
            ("Deck Um", "modern", [("Sol Ring", 1), ("Gilded Drake", 1)]),
            ("Deck Dois", "premodern", [("Dark Ritual", 1)])):
        con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?",
                          (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?, 'main')", (did, nm, q))
    for sub in ("Colecção", "Caixa Reserved List"):
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
    con.commit()
    return con


def add(con, nm, q=1, sub="Colecção", lang="en", finish="nonfoil", slot=None):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    cid = con.execute("""INSERT INTO copies (scryfall_id, quantity, finish,
                         language, condition, purpose, sub_collection_id)
                         VALUES (?,?,?,?,'NM','player',?)""",
                      (sid, q, finish, lang, sub_id)).lastrowid
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.commit()
    return cid


def _dias(n):
    """A data de há `n` dias (a janela da R5 é de 30)."""
    from datetime import timedelta
    return (date.today() - timedelta(days=n)).isoformat()


def decklists(con, fmt="modern", n=10, assinatura="Oswald Fiddlebender",
              extras=(), dias=1, board="main", chave=""):
    """`n` listas, todas com a carta-assinatura, datadas de há `dias` dias.

    `extras` são `(carta, em_quantas)` — a carta entra nas primeiras `em_quantas`
    listas, e é assim que se fabrica uma percentagem conhecida (8 de 10 = 80 %).
    `dias` é o que faz a R5 morder ou não: 20 dias está na janela, 40 não.
    """
    pref = chave or f"k{fmt}{dias}{board}"
    for k in range(n):
        con.execute("""INSERT INTO decklists (source, source_key, format,
                       event_date, event_tier, player)
                       VALUES ('mtgo', ?, ?, ?, 'Challenge', ?)""",
                    (f"{pref}{k}", fmt, _dias(dias), f"j{pref}{k}"))
        lid = con.execute("SELECT id FROM decklists WHERE source_key = ?",
                          (f"{pref}{k}",)).fetchone()["id"]
        con.execute("""INSERT OR REPLACE INTO decklist_cards (decklist_id,
                       card_name, quantity, board) VALUES (?,?,1, 'main')""",
                    (lid, assinatura))
        for nm, quantas in extras:
            if k < quantas:
                con.execute("""INSERT OR REPLACE INTO decklist_cards (decklist_id,
                               card_name, quantity, board) VALUES (?,?,1,?)""",
                            (lid, nm, board))
    con.commit()


def nomes(linhas):
    return {l["nm"] for l in linhas}


def cands(con, **cfg):
    escreve_cfg(**cfg)
    res = loadout.report(con)
    return fases.candidatos(con, res), res


# ===========================================================================
# 1. AS DUAS LISTAS DE TERRAS
# ===========================================================================
def caso_as_tres_listas_de_terras_derivam_do_catalogo():
    con = base()
    sh, fe, du = fases.shocklands(con), fases.fetchlands(con), fases.duais(con)
    assert sh["n"] == 10, sh
    assert fe["n"] == 10, fe
    assert sh["nomes"] == sorted(n for n, _s, _a, _b in SHOCK), sh["nomes"]
    assert fe["nomes"] == sorted(n for n, _a in FETCH), fe["nomes"]
    # A regra fica GRAVADA, que é o que a ordem pede.
    assert "2 life" in sh["regra"] and "oracle" not in sh["regra"].lower()[:5]
    assert "1 life" in fe["regra"] or "1 ponto de vida" in fe["regra"]
    # E as iscas de dois sub-tipos ficaram todas fora das shock/fetch.
    for nm, _tl, _t in ISCAS:
        assert nm not in sh["nomes"] and nm not in fe["nomes"], nm
    # AS DUAIS: dois sub-tipos básicos E só o lembrete de mana. Neste catálogo de
    # mentira as únicas são a Tundra e a Underground Sea, e é isso que separa a
    # regra de «sem texto nenhum» (que dava ZERO: as originais trazem o lembrete
    # entre parênteses) e de «dois sub-tipos» (que apanhava as dez shocklands e
    # as de surveil e de entrada virada).
    assert du["nomes"] == ["Tundra", "Underground Sea"], du["nomes"]
    assert du["alvo_fora"] == 4
    for nm in sh["nomes"]:
        assert nm not in du["nomes"], nm
    for nm in ("Undercity Sewers", "Contaminated Aquifer"):
        assert nm not in du["nomes"], nm
    # As duais NÃO estão nas `terras_protegidas`: a regra delas é a quota.
    tp = fases.terras_protegidas(con)
    assert "Tundra" not in tp and "Hallowed Fountain" in tp


def caso_a_derivacao_levanta_quando_nao_da_dez():
    """Sem `oracle_text` não se devolve uma lista curta: levanta-se.

    É a diferença entre um erro alto e uma protecção vazia em silêncio — que
    mandaria shocklands para a lista de venda sem um único passo a falhar.
    """
    con = base()
    con.execute("UPDATE catalog.cards SET oracle_text = NULL "
                " WHERE name = 'Hallowed Fountain'")
    con.commit()
    try:
        # `exigir=True` é o que o `verificar` (e o `cli fases terras`) faz. Aqui
        # pergunta-se só às shocklands: neste catálogo de mentira as duais são
        # DUAS de propósito (só a Tundra e a Underground Sea lá estão), e o
        # `verificar` levantaria por essas primeiro.
        fases.shocklands(con, exigir=True)
    except fases.TerrasNaoDerivadas as e:
        assert len(e.nomes) == 9, e.nomes
        assert "Hallowed Fountain" not in e.nomes
        assert "sync-cards" in str(e)          # diz como se resolve
        assert e.regra                          # e diz a regra que usou
    else:
        raise AssertionError("a derivação devolveu 9 nomes sem levantar")


def caso_um_catalogo_pequeno_nao_rebenta_o_motor():
    """A conta tem de dar dez NUM CATÁLOGO COMPLETO. Numa base de trinta cartas
    que não tem shocklands nenhumas, «zero» é a resposta certa — é o mesmo
    princípio do `foil_info` (uma carta que o catálogo não conhece não é uma
    carta «sem foil»).

    Sem esta distinção, acrescentar a P1 ao `loadout.sell_list` rebentava o
    `report` em **vinte ficheiros de teste** e, pior, em qualquer base nova.
    """
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    _carta(con, 900, "Sol Ring", "c21", "263", 0, "", "Artifact", "")
    con.commit()
    assert not fases.catalogo_completo(con)
    assert fases.shocklands(con)["n"] == 0          # não levanta
    assert fases.terras_protegidas(con) == {}
    escreve_cfg()
    res = loadout.report(con)                       # e o motor corre
    assert res["protegidas"] == []
    # Mas a verificação explícita continua a dizer que não dá dez.
    try:
        fases.verificar(con)
    except fases.TerrasNaoDerivadas:
        pass
    else:
        raise AssertionError("o `verificar` não insistiu")


# ===========================================================================
# 2. R1 — as duais: QUATRO fora dos decks, o resto é candidato
# ===========================================================================
def caso_a_quinta_dual_fora_dos_decks_vai_a_venda_e_a_quarta_nao():
    """*"Quer ter 4 de cada em colecção FORA dos decks; o que passar disso
    vende-se ou troca-se."* E as duais são Reserved List: se a R4 as salvasse, a
    R1 nunca morderia — é por isso que ela vem primeiro e é exclusiva
    (*"para elas manda a R1, que é mais específica"*)."""
    con = base()
    add(con, "Tundra", 5, sub="Caixa Reserved List")   # cinco fora dos decks
    c, res = cands(con)
    prot = [l for l in c["protegidas"] if l["nm"] == "Tundra"]
    cand = [l for l in c["linhas"] if l["nm"] == "Tundra"]
    assert sum(l["q"] for l in prot) == 4, prot
    assert sum(l["q"] for l in cand) == 1, cand
    assert prot[0]["proteccao"] == fases.R1, prot[0]
    assert "4 de cada fora dos decks" in prot[0]["motivo"], prot[0]["motivo"]
    # E o plano diz as duas listas que ele pediu.
    d = fases.plano_duais(con, res)
    linha = next(x for x in d["linhas"] if x["nm"] == "Tundra")
    assert (linha["fora"], linha["protegidas"], linha["vender"]) == (5, 4, 1), linha
    assert linha["comprar"] == 0
    # A Underground Sea, que ele não tem, aparece na lista de COMPRAR.
    us = next(x for x in d["linhas"] if x["nm"] == "Underground Sea")
    assert (us["fora"], us["comprar"], us["vender"]) == (0, 4, 0), us
    assert {x["nm"] for x in d["comprar"]} == {"Underground Sea"}
    assert d["totais"]["vender"] == 1 and d["totais"]["comprar"] == 4


def caso_uma_dual_dentro_de_um_deck_nao_conta_para_as_quatro_de_fora():
    """*"4 de cada em colecção FORA dos decks"* — a que está sleevada está
    protegida pelo deck e não gasta a quota."""
    con = base()
    add(con, "Tundra", 1, slot="d1")                   # dentro do deck
    add(con, "Tundra", 4, sub="Caixa Reserved List")   # quatro fora
    c, res = cands(con)
    assert "Tundra" not in nomes(c["linhas"]), "nenhuma devia ser candidata"
    d = fases.plano_duais(con, res)
    linha = next(x for x in d["linhas"] if x["nm"] == "Tundra")
    assert (linha["copias"], linha["em_decks"], linha["fora"]) == (5, 1, 4), linha
    assert linha["vender"] == 0 and linha["comprar"] == 0, linha
    quem = {l["proteccao"] for l in c["protegidas"] if l["nm"] == "Tundra"}
    assert quem == {fases.R1, fases.RD}, quem


# ===========================================================================
# 3. R2/R3 — TODAS as cópias das shock/fetch
# ===========================================================================
def caso_uma_shockland_extra_fora_de_qualquer_deck_nunca_e_candidata():
    con = base()
    add(con, "Hallowed Fountain", 1)             # non-foil, solta, a mais
    c, _res = cands(con)
    assert "Hallowed Fountain" not in nomes(c["linhas"]), \
        "uma shockland solta apareceu nos candidatos"
    linha = next(l for l in c["protegidas"] if l["nm"] == "Hallowed Fountain")
    assert linha["proteccao"] == fases.R2, linha
    assert "shockland" in linha["motivo"], linha["motivo"]


def caso_todas_as_copias_de_uma_shock_fetch_ficam_protegidas():
    """*"Todas as cópias — todos os acabamentos, todas as línguas, todas as
    repetidas, estejam ou não num deck. Sem excepções."*"""
    con = base()
    add(con, "Flooded Strand", 1, finish="nonfoil")
    add(con, "Flooded Strand", 4, finish="foil")
    add(con, "Flooded Strand", 2, lang="pt")
    add(con, "Flooded Strand", 1, slot="d1")     # dentro de um deck
    add(con, "Steam Vents", 3, sub="Caixa Reserved List")
    c, _res = cands(con)
    assert "Flooded Strand" not in nomes(c["linhas"])
    assert "Steam Vents" not in nomes(c["linhas"])
    # As 8 cópias de Flooded Strand pela R3 e as 3 de Steam Vents pela R2 — a que
    # está dentro do deck inclusive (vêm ANTES da RD de propósito: é a razão que
    # SOBREVIVE se ele passar o deck a candidato).
    fe = [l for l in c["protegidas"] if l["proteccao"] == fases.R3]
    sh = [l for l in c["protegidas"] if l["proteccao"] == fases.R2]
    assert sum(l["q"] for l in fe) == 8, [(l["nm"], l["q"]) for l in fe]
    assert sum(l["q"] for l in sh) == 3, [(l["nm"], l["q"]) for l in sh]


# ===========================================================================
# 4. R4 — a Reserved List que ele JOGA
# ===========================================================================
def caso_uma_rl_que_ele_joga_nunca_e_candidata():
    con = base()
    add(con, "Gilded Drake", 3, sub="Caixa Reserved List")   # 1 no deck, 2 a mais
    c, _res = cands(con)
    assert "Gilded Drake" not in nomes(c["linhas"]), \
        "uma RL que ele joga apareceu nos candidatos"
    linha = next(l for l in c["protegidas"] if l["nm"] == "Gilded Drake")
    assert linha["proteccao"] in (fases.R4, fases.RD), linha
    joga = fases.rl_que_joga(con, loadout.report(con))
    assert "Gilded Drake" in joga and "Deck Um" in joga["Gilded Drake"], joga


def caso_uma_rl_que_ele_nao_joga_nao_e_protegida_pela_r4():
    """A R4 protege o que ele JOGA. O resto da RL **não** é protegido por aqui:
    continua a passar pela regra dos 5 % de 2026-09-08, que é outra decisão."""
    con = base()
    add(con, "Taiga", 2, sub="Caixa Reserved List")
    res = loadout.report(con)
    assert "Taiga" not in fases.rl_que_joga(con, res), \
        "a Taiga não está em deck nenhum e a R4 deu-a como jogada"
    c = fases.candidatos(con, res)
    prot = [l for l in c["protegidas"] if l["nm"] == "Taiga"]
    assert not prot, prot


def caso_a_rl_de_uma_lista_que_nao_e_deck_dele_nao_protege():
    """*"O RL que ELE joga"*. A tabela `decks` tem listas de metagame e de
    jogadores vigiados que não são decks dele (na base de 2026-10-02: *Jeskai
    Lessons*, *4c Control*, *Cori-Steel Cutter*, *Legacy (Harry1232)*). O caminho
    (c) da R4 passou a olhar só para as listas que uma CAIXA referencia: um deck
    que saiu do config deixa de proteger no mesmo dia."""
    con = base()
    con.execute("INSERT INTO decks (name, format) VALUES ('Lista Alheia','modern')")
    did = con.execute("SELECT id FROM decks WHERE name = 'Lista Alheia'"
                      ).fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Taiga', 1, 'main')", (did,))
    con.commit()
    add(con, "Taiga", 2, sub="Caixa Reserved List")
    res = loadout.report(con)
    assert "Taiga" not in fases.rl_que_joga(con, res), \
        "uma lista que não é caixa dele protegeu Reserved List"


# ===========================================================================
# 5. RD — os decks cujo ESTADO protege
# ===========================================================================
def caso_uma_copia_num_deck_permanente_nunca_e_candidata():
    con = base()
    add(con, "Sol Ring", 1, slot="d1")
    c, _res = cands(con, caixas_estado={"d1": "permanente"})
    assert "Sol Ring" not in nomes(c["linhas"])
    linha = next(l for l in c["protegidas"] if l["nm"] == "Sol Ring")
    assert linha["proteccao"] == fases.RD, linha
    assert "permanente" in linha["motivo"], linha["motivo"]


def caso_uma_caixa_candidata_liberta_as_cartas():
    """O `candidata` é o único estado que NÃO protege por si — é para isso que
    ele serve na escala da v6."""
    con = base()
    add(con, "Sol Ring", 1, slot="d1")
    c_mont, _ = cands(con, caixas_estado={"d1": "montada"})
    c_cand, _ = cands(con, caixas_estado={"d1": "candidata"})
    assert "Sol Ring" not in nomes(c_mont["linhas"])
    assert "Sol Ring" in nomes(c_cand["linhas"]), \
        "passar a caixa a candidata não libertou a carta"
    assert c_cand["copias"] > c_mont["copias"]


def caso_congelada_vale_montada_e_protege():
    """O `congelada` é CALCULADO (`caixas.estado_de`) e escrevê-lo vale
    `montada` — não pode deixar de proteger por causa disso."""
    con = base()
    add(con, "Sol Ring", 1, slot="d1")
    c, _res = cands(con, caixas_estado={"d1": "congelada"})
    assert "Sol Ring" not in nomes(c["linhas"])
    assert fases.protege(fases.estado_de({"estado": "congelada"}))


# ===========================================================================
# 6. A OMISSÃO DO `estado` PROTEGE
# ===========================================================================
def caso_uma_caixa_sem_estado_protege():
    assert fases.ESTADO_OMISSAO == "permanente"
    assert fases.estado_de({"slot": "x"}) == "permanente"
    assert fases.protege(fases.estado_de({"slot": "x"}))
    # `congelada` vale `montada`; um valor que não é da escala cai na omissão,
    # que protege. Nunca o contrário.
    assert fases.estado_de({"estado": "congelada"}) == "montada"
    assert fases.protege(fases.estado_de({"estado": "qualquer"}))
    assert not fases.protege("candidata")


def caso_uma_caixa_sem_estado_nao_manda_nada_para_a_venda():
    """Um deck novo, sem estado escrito, não manda uma única carta.

    Se a omissão não protegesse, acrescentar uma caixa ao config punha o
    conteúdo dela à venda sem ninguém decidir nada.
    """
    con = base()
    add(con, "Sol Ring", 1, slot="d1")
    add(con, "Dark Ritual", 1, slot="d1")
    escreve_cfg(sem_estado=["d1", "d2"])          # NENHUM estado escrito
    res = loadout.report(con)
    e = fases.estados()
    assert e["d1"] == "permanente" and e["d2"] == "permanente", e
    c = fases.candidatos(con, res)
    for nm in ("Sol Ring", "Dark Ritual"):
        assert nm not in nomes(c["linhas"]), f"{nm} foi à venda sem estado"
    # E a página diz que o estado NÃO está escrito — não o dá por escolhido.
    decks = fases.decks_para_decidir(con, res)
    assert all(not x["estado_explicito"] for x in decks), decks
    assert all(x["protege"] for x in decks), decks


# ===========================================================================
# 7. R5 — a reserva: o que foi jogado nos últimos 30 dias
# ===========================================================================
def caso_uma_carta_jogada_ha_vinte_dias_esta_protegida():
    con = base()
    decklists(con, extras=[("Force of Will", 8)], dias=20)
    add(con, "Force of Will", 2)
    c, res = cands(con)
    r = next(x for x in fases.decks_para_decidir(con, res)
             if x["slot"] == "d1")["reserva"]
    assert r["listas"] == 10 and r["suficiente"], r
    assert r["janela_dias"] == 30 and r["desde"] <= _dias(20), r
    assert "Force of Will" in {x["nm"] for x in r["final"]}, r["final"]
    assert "Force of Will" not in nomes(c["linhas"]), \
        "uma carta jogada há 20 dias apareceu nos candidatos"
    linha = next(l for l in c["protegidas"] if l["nm"] == "Force of Will")
    assert linha["proteccao"] == fases.R5, linha
    assert "últimos 30 dias" in linha["motivo"], linha["motivo"]
    assert "Deck Um" in linha["motivo"], linha["motivo"]


def caso_uma_carta_jogada_ha_quarenta_dias_nao_esta_protegida():
    """A janela de 30 dias é o travão que substituiu o limiar de 20 %: tem de
    morder nos dois sentidos, senão a reserva apanhava tudo o que alguma vez
    apareceu numa lista e não sobrava nada para vender."""
    con = base()
    decklists(con, extras=[("Swan Song", 8)], dias=40)
    add(con, "Swan Song", 2)
    c, res = cands(con)
    r = next(x for x in fases.decks_para_decidir(con, res)
             if x["slot"] == "d1")["reserva"]
    assert r["listas"] == 0, r
    assert "Swan Song" in nomes(c["linhas"]), \
        "uma carta jogada há 40 dias ficou protegida — a janela não morde"


def caso_uma_carta_SO_no_sideboard_tambem_entra_na_reserva():
    """*"Main ou side"* — é a ordem dele, à letra."""
    con = base()
    decklists(con, extras=[("Force of Will", 8)], dias=10, board="side")
    add(con, "Force of Will", 2)
    c, _res = cands(con)
    assert "Force of Will" not in nomes(c["linhas"]), \
        "uma carta que só aparece no sideboard não entrou na reserva"


def caso_a_reserva_nao_se_enche_sem_amostra():
    """Com menos de `MIN_LISTAS_RESERVA` listas a reserva automática é VAZIA.

    É a ordem dele sobre o *Ill-Gotten Gains*: *"SÓ 3 listas, abaixo do mínimo
    de 8. Marca-o como SEM CONSENSO SUFICIENTE e deixa a lista manual; não
    inventes consenso com 3 listas."*
    """
    con = base()
    decklists(con, n=3, extras=[("Force of Will", 1)], dias=5)
    add(con, "Force of Will", 2)
    c, res = cands(con)
    r = next(x for x in fases.decks_para_decidir(con, res)
             if x["slot"] == "d1")["reserva"]
    assert r["listas"] == 3 and not r["suficiente"], r
    assert not r["automatica"], r["automatica"]
    assert fases.NOTA_SEM_CONSENSO in r["nota"], r["nota"]
    assert "Force of Will" in nomes(c["linhas"]), \
        "uma reserva de 3 listas protegeu uma carta"


# ===========================================================================
# 8. R5b — as staples de sideboard de Premodern
# ===========================================================================
def caso_uma_staple_de_sideboard_de_premodern_acima_do_corte_esta_protegida():
    """*"SÓ PARA PREMODERN: protege as staples de sideboard do formato."* A
    curva mede-se com `curva_staples`; o corte vive no config."""
    con = base()
    # 10 listas de Premodern, 8 com a Swan Song no SIDEBOARD = 80 %.
    # A assinatura destas listas é a Taiga e NÃO o Dark Ritual (a lista do Deck
    # Dois): assim o arquétipo dele não casa com elas, a R5 não as apanha, e o
    # que se mede aqui é só a R5b. Sem isto a R5 chegava lá primeiro e o caso
    # passava por outra razão.
    decklists(con, fmt="premodern", assinatura="Taiga",
              extras=[("Swan Song", 8)], dias=5, board="side")
    add(con, "Swan Song", 2)
    st = fases.staples_sideboard(con, corte=50)
    assert st["com_sideboard"] == 8, st
    assert st["nomes"].get("Swan Song") == 100.0, st["nomes"]
    c50, _ = cands(con, staples_pct=50)
    assert "Swan Song" not in nomes(c50["linhas"]), \
        "uma staple de sideboard acima do corte foi para VENDER"
    linha = next(l for l in c50["protegidas"] if l["nm"] == "Swan Song")
    assert linha["proteccao"] == fases.R5B, linha
    assert "staple de sideboard" in linha["motivo"], linha["motivo"]
    # Acima do corte ela sai: a regra morde nos dois sentidos.
    con.execute("UPDATE decklist_cards SET card_name = 'Sol Ring' "
                " WHERE card_name = 'Swan Song'")
    con.commit()
    c, _ = cands(con, staples_pct=50)
    assert "Swan Song" in nomes(c["linhas"])


def caso_a_curva_das_staples_mede_copias_e_valor():
    """*"MEDE A CURVA (10/20/30/40/50 %) em cópias e valor para ele escolher com
    números à frente. Não fixes o corte sem lhe mostrar a curva."*"""
    con = base()
    # A assinatura destas listas é a Taiga e NÃO o Dark Ritual (a lista do Deck
    # Dois): assim o arquétipo dele não casa com elas, a R5 não as apanha, e o
    # que se mede aqui é só a R5b. Sem isto a R5 chegava lá primeiro e o caso
    # passava por outra razão.
    decklists(con, fmt="premodern", assinatura="Taiga",
              extras=[("Swan Song", 4)], dias=5, board="side")
    add(con, "Swan Song", 2)
    escreve_cfg()
    res = loadout.report(con)
    curva = fases.curva_staples(con, res)
    assert [x["corte"] for x in curva] == [10, 20, 30, 40, 50], curva
    for x in curva:
        for lado in ("a_mais", "sozinha"):
            assert set(x[lado]) >= {"cartas", "copias", "valor", "so_premodern"}
    # A 100 % de presença, a Swan Song entra em todos os cortes e protege as 2
    # cópias; e a curva não pode ser monótona crescente com o corte.
    assert curva[0]["sozinha"]["copias"] >= curva[-1]["sozinha"]["copias"]
    assert curva[0]["cartas_staple"] >= curva[-1]["cartas_staple"]


def caso_a_reserva_manual_fica_mesmo_sem_consenso():
    """O que ele escreveu à mão é uma DECISÃO, não uma inferência: fica, haja ou
    não amostra."""
    con = base()
    add(con, "Force of Will", 2)
    c, _res = cands(con, caixa_chave={"d1": {"reserva": ["Force of Will"]}})
    assert "Force of Will" not in nomes(c["linhas"])


# ===========================================================================
# 7. A TRAVA, MANUAL desde 2026-10-04
# ===========================================================================
# CORRIGIDO a 2026-10-04 ao fim do dia, e não mascarado: estes dois casos
# chamavam-se *"…antes de doze de outubro"* / *"…a partir de doze de outubro"* e
# afirmavam que a trava era uma DATA que *"passa sozinha"*. Ele decidiu o
# contrário — a venda destranca só quando ELE disser —, por isso o que se
# corrige é a ASSERÇÃO: já não há data, há interruptor.
def caso_a_saida_de_venda_recusa_se_com_a_trava_posta():
    con = base()
    add(con, "Dark Ritual", 6)
    escreve_cfg()
    # A DATA DE HOJE É IRRELEVANTE: era ela que decidia, e hoje não decide nada.
    assert fases.venda_congelada(hoje="2026-10-01") is True
    assert fases.venda_congelada(hoje="2026-10-11") is True
    assert fases.venda_congelada(hoje="2026-10-12") is True, \
        "o dia 12 era o dia em que a trava caía sozinha — já não cai"
    assert fases.venda_congelada(hoje="2027-01-01") is True, \
        "nem daqui a três meses: a trava é manual"
    pasta = Path(tempfile.mkdtemp())
    try:
        venda.exportar(con, pasta=pasta)
    except fases.VendaCongelada as e:
        assert "congelada" in str(e).lower(), str(e)
        # A FRASE TEM DE DIZER COMO SE DESTRANCA — é a pergunta que ele faz
        # dentro de um mês, e sem isto mandava-o procurar.
        assert "--congelada off" in str(e), str(e)
        assert "venda.congelada" in str(e), str(e)
        assert isinstance(e, ValueError)          # o do_POST traduz em 409
    else:
        raise AssertionError("a exportação correu com a venda congelada")
    # E NÃO deixou ficheiro nenhum atrás dela.
    assert not list(pasta.glob("*")), list(pasta.glob("*"))


def caso_levantar_o_interruptor_destranca_e_baixar_volta_a_travar():
    """O interruptor manda nos dois sentidos, e a data antiga não manda em nada."""
    con = base()
    add(con, "Dark Ritual", 6)

    # DESTRANCADO: a saída corre.
    escreve_cfg(congelada=False)
    assert fases.congelada() is False
    assert fases.venda_congelada(hoje="2026-10-01") is False
    fases.exige_descongelado()                       # não levanta
    pasta = Path(tempfile.mkdtemp())
    venda.exportar(con, pasta=pasta)
    assert list(pasta.glob("*")), "destrancada, a exportação escreve"

    # SEM A CHAVE vale destrancado — é o que a ausência já valia antes.
    escreve_cfg(congelada=None)
    assert fases.congelada() is False, "sem a chave não há trava"
    assert fases.CONGELADA_OMISSAO is False

    # TRAVAR OUTRA VEZ volta a recusar.
    escreve_cfg(congelada=True)
    assert fases.congelada() is True
    pasta2 = Path(tempfile.mkdtemp())
    try:
        venda.exportar(con, pasta=pasta2)
    except fases.VendaCongelada:
        pass
    else:
        raise AssertionError("baixar o interruptor tem de voltar a travar")
    assert not list(pasta2.glob("*"))


def caso_a_data_antiga_no_config_deixou_de_travar_e_di_lo():
    """A chave antiga não se apagou — mas já não decide, e isso diz-se.

    Uma chave que ninguém lê é o padrão do `event_tier`: quem a escrevesse a
    pensar que trava ficava sem saber porque é que parou.
    """
    # A data SOZINHA, no futuro, já não trava.
    escreve_cfg(congelada=None, congelado_ate="2099-01-01")
    assert fases.congelada() is False, \
        "a data no futuro não pode travar: quem manda é o interruptor"
    assert fases.congelado_ate() == "2099-01-01", "lê-se, só para se poder dizer"
    aviso = fases.data_sem_efeito()
    assert "JÁ NÃO TEM EFEITO" in aviso, aviso
    assert "venda.congelada" in aviso, aviso
    assert "destravada" in aviso, aviso

    # E com as duas escritas, quem ganha é o interruptor.
    escreve_cfg(congelada=True, congelado_ate="2020-01-01")
    assert fases.congelada() is True, \
        "uma data PASSADA não pode destrancar o que o interruptor travou"
    assert "travada" in fases.data_sem_efeito()

    # Sem a chave antiga não há aviso nenhum (é o estado do config dele).
    escreve_cfg(congelada=True)
    assert fases.data_sem_efeito() == "", fases.data_sem_efeito()
    print("trava: manual; a data antiga não trava nem destranca, e di-lo")


# ===========================================================================
# 8. AS FILAS: FOTOS de até 4 cartas, por valor
# ===========================================================================
# CORRIGIDO a 2026-10-01: estes casos estavam escritos com a regra ERRADA — *"a
# fila conta cópias físicas: um playset dá quatro linhas"*. A regra dele, à
# letra, é *"organiza o Blue farm e CDEH por tipo de carta e ate 4 cartas por
# foto"* e *"se sao 4 fotos, e 1 foto com as 4 cartas"*: um playset é UMA foto.
def caso_a_fila_de_candidatos_sai_por_valor_decrescente():
    con = base()
    add(con, "Dark Ritual", 6)
    add(con, "Taiga", 2, sub="Caixa Reserved List")
    add(con, "Swan Song", 4)
    escreve_cfg()
    res = loadout.report(con)
    f = fases.fila_candidatos(con, res)
    # Pelo preço DA CÓPIA (`preco_max`), não pelo total da foto: um lote de 6
    # Dark Ritual soma mais do que uma Taiga e nem por isso é mais caro à carta.
    vals = [x["preco_max"] for x in f["fotos"]]
    assert vals == sorted(vals, reverse=True), vals[:12]
    assert f["lote"] == 50
    assert f["max_cartas"] == 4


def caso_um_playset_e_UMA_foto_e_nunca_quatro():
    """*"se são 4 fotos, é 1 foto com as 4 cartas"* — as cópias da MESMA carta
    vão sempre juntas. Um lote de 4 é UMA linha da `copies` e tem de dar **uma**
    foto de 4 cartas; dar-lhe quatro era quadruplicar o trabalho dele."""
    con = base()
    add(con, "Swan Song", 4)                 # um lote de 4: uma linha da copies
    escreve_cfg()
    res = loadout.report(con)
    f = fases.fila_candidatos(con, res)
    swan = [x for x in f["fotos"]
            if any(i["nm"] == "Swan Song" for i in x["itens"])]
    assert len(swan) == 1, f"o playset deu {len(swan)} fotos"
    assert swan[0]["cartas"] == 4 and swan[0]["linhas"] == 1, swan[0]
    assert f["barra"]["fotos"] == 1 and f["barra"]["cartas"] == 4, f["barra"]
    # A barra conta FOTOS e diz as cartas e as linhas ao lado.
    assert set(f["barra"]) >= {"fotos", "cartas", "linhas", "feitas", "pct"}
    # E cada item leva o seu acabamento, língua e estado.
    assert all(i["finish"] and i["lang"] and i["cond"] for i in swan[0]["itens"])


def caso_uma_foto_leva_no_maximo_quatro_cartas():
    """O tecto é por CARTAS e não por linhas: três cartas diferentes de uma cópia
    cada mais um lote de 2 são duas fotos (3 + 2 não cabe em 4), e nenhuma foto
    passa das quatro."""
    con = base()
    add(con, "Dark Ritual", 6)               # sozinha passa do tecto: 2 fotos
    add(con, "Swan Song", 2)
    add(con, "Sol Ring", 1)
    add(con, "Taiga", 1, sub="Caixa Reserved List")
    escreve_cfg()
    f = fases.fila_candidatos(con, loadout.report(con))
    assert f["fotos"], "a fila está vazia — o caso não mede nada"
    assert all(x["cartas"] <= 4 for x in f["fotos"]), \
        [(x["n"], x["cartas"]) for x in f["fotos"]]
    # A linha que SOZINHA passa das 4 cartas enche fotos inteiras só dela, e
    # a foto di-lo (`partida`) em vez de o esconder.
    dr = [x for x in f["fotos"] if any(i["nm"] == "Dark Ritual" for i in x["itens"])]
    assert len(dr) == 2 and sum(x["cartas"] for x in dr) == 6, dr
    assert all(x["partida"] for x in dr), dr
    assert all(x["linhas"] == 1 for x in dr), "misturou a linha partida com outras"


def caso_a_fila_dos_decks_conta_fotos_cartas_e_valor():
    con = base()
    add(con, "Swan Song", 4, slot="d1")
    add(con, "Sol Ring", 1, slot="d1")
    escreve_cfg(caixas_estado={"d1": "montada"})
    res = loadout.report(con)
    f = fases.fila_decks(con, res)
    fila = next(x for x in f["filas"] if x["slot"] == "d1")
    # 4 Swan Song (instantâneo) + 1 Sol Ring (artefacto) = 5 cartas. As fotos
    # NÃO atravessam tipos, por isso são DUAS: uma de 4 e uma de 1.
    assert fila["barra"]["cartas"] == 5, fila["barra"]
    assert fila["barra"]["fotos"] == 2, [x["itens"] for x in fila["fotos"]]
    assert fila["barra"]["linhas"] == 2
    assert fila["barra"]["falta"] == 2 and fila["barra"]["feitas"] == 0
    assert fila["barra"]["valor"] > 0
    tipos = [x["tipo"] for x in fila["fotos"]]
    assert tipos == ["Artifact", "Instant"], tipos
    # Uma caixa `candidata` não é um deck que ele leve: não entra na fila.
    escreve_cfg(caixas_estado={"d1": "candidata"})
    f2 = fases.fila_decks(con, loadout.report(con))
    assert not any(x["slot"] == "d1" for x in f2["filas"]), f2["filas"]


def caso_o_inventario_e_paralelo_e_nunca_bloqueia():
    """*"Nunca bloqueia nada e aparece como tal na página — é inventário, não é
    passo da venda."*"""
    con = base()
    add(con, "Taiga", 2, sub="Caixa Reserved List")
    add(con, "Hallowed Fountain", 1)
    add(con, "Flooded Strand", 1)
    escreve_cfg()
    inv = fases.fila_inventario(con, loadout.report(con))
    chaves = {g["chave"]: g["barra"]["cartas"] for g in inv["grupos"]}
    assert chaves == {"rl": 2, "shockland": 1, "fetchland": 1}, chaves
    # 2 Taiga são UMA foto, não duas.
    rl = next(g for g in inv["grupos"] if g["chave"] == "rl")
    assert rl["barra"]["fotos"] == 1, [x["itens"] for x in rl["fotos"]]
    assert "não é um passo da venda" in inv["nota"]


# ===========================================================================
# 11. O MOTIVO, E QUAL DAS REGRAS
# ===========================================================================
def caso_cada_exclusao_tem_motivo_em_portugues_e_a_proteccao():
    """*"Cada cópia excluída da venda guarda o MOTIVO em português, e qual das
    regras a apanhou. Sem motivo não há exclusão silenciosa."*"""
    con = base()
    add(con, "Hallowed Fountain", 1)
    add(con, "Gilded Drake", 2, sub="Caixa Reserved List")
    add(con, "Sol Ring", 1, slot="d1")
    add(con, "Force of Will", 1)
    add(con, "Tundra", 6, sub="Caixa Reserved List")
    decklists(con, extras=[("Force of Will", 9)], dias=3)
    c, _res = cands(con, caixa_chave={"d1": {"reserva_assinatura":
                                             ["Oswald Fiddlebender"]}})
    assert c["protegidas"], "nada ficou protegido — o caso não mede nada"
    for l in c["protegidas"]:
        assert l["proteccao"] in fases.PROTECCOES, l
        assert l["motivo"] and len(l["motivo"]) > 15, l
        assert fases.ROTULOS[l["proteccao"]] in l["motivo"], l
        # Em português: nenhum motivo em inglês cru.
        assert not l["motivo"].startswith(("protected", "reserved")), l
    vistas = {l["proteccao"] for l in c["protegidas"]}
    assert {fases.R1, fases.R2, fases.R5} <= vistas, vistas
    for p, v in c["por_proteccao"].items():
        assert v["rotulo"] == fases.ROTULOS[p]


# ===========================================================================
# 12. AS PROTECÇÕES VALEM NO MOTOR, NÃO SÓ NA PÁGINA
# ===========================================================================
def caso_as_proteccoes_valem_tambem_no_motor_da_venda():
    """Uma protecção que valesse só na página das Fases deixava a aba Vender e a
    exportação a oferecer a mesma carta — o padrão do `event_tier` aplicado à
    decisão que vale mais dinheiro."""
    con = base()
    # 6 shocklands soltas: pelo playset de 4, duas seriam excedente de venda.
    add(con, "Hallowed Fountain", 6)
    add(con, "Dark Ritual", 6)            # o controlo: estas SIM, vão à venda
    escreve_cfg()
    res = loadout.report(con)
    assert "protegidas" in res, "o sell_list não ganhou a saída `protegidas`"
    assert "Hallowed Fountain" not in nomes(res["venda"]), \
        "uma shockland excedente ficou na lista de venda do motor"
    assert "Hallowed Fountain" in nomes(res["protegidas"])
    linha = next(l for l in res["protegidas"] if l["nm"] == "Hallowed Fountain")
    assert linha["proteccao"] == fases.R2, linha
    # O motivo por que IRIA à venda guarda-se, como nas RL a segurar.
    assert linha["porque_venderia"], linha
    assert "Dark Ritual" in nomes(res["venda"]), \
        "o controlo falhou: o motor deixou de vender o que devia"
    # E a saída aparece no «fica de fora» da exportação, com o motivo.
    fora = {f["chave"]: f for f in venda.fora_da_exportacao(res)}
    assert "protegidas" in fora and fora["protegidas"]["copias"] > 0, fora
    assert all(l["motivo"] for l in fora["protegidas"]["linhas"])


def caso_o_campo_decisao_foi_mesmo_apagado():
    """O `caixas[].decisao` de 2026-10-01 saiu por ordem dele: eram DUAS verdades
    para a mesma pergunta, ao lado do `estado` que as caixas já tinham. Este caso
    tranca que não volta — nem o campo, nem quem o lia.

    Um deck com `decisao: dissolvido` escrito à mão **não** liberta nada: quem
    manda é o `estado`. Se alguém voltar a ligar o campo, este caso chumba.
    """
    for nome in ("decisao_de", "decisoes", "gravar_decisao", "DECISOES",
                 "DECISAO_OMISSAO", "TEXTO_DECISAO", "limiar_pct",
                 "curva_do_limiar"):
        assert not hasattr(fases, nome), f"o `fases.{nome}` voltou"
    assert "decisao" not in _caixas_ORDEM(), "a chave `decisao` voltou à ORDEM"
    con = base()
    add(con, "Sol Ring", 1, slot="d1")
    c, _res = cands(con, caixa_chave={"d1": {"decisao": "dissolvido"}},
                    caixas_estado={"d1": "montada"})
    assert "Sol Ring" not in nomes(c["linhas"]), \
        "um `decisao: dissolvido` escrito à mão libertou a carta — o campo " \
        "voltou a ser lido"


def _caixas_ORDEM():
    from mtgvault import caixas as _c
    return _c.ORDEM


def caso_o_nao_e_necessaria_grava_se_no_config_sem_o_reformatar():
    """O `colecao_config.json` edita-se CIRURGICAMENTE (regra do CLAUDE.md): o
    commit `ac1f776` saiu com 861 inserções por ter sido reescrito com
    `indent=2`. O botão escreve com o `configio.escrever`, que preserva a forma
    uma-linha-por-caixa."""
    from mtgvault import configio
    escreve_cfg()
    # Parte-se de um ficheiro JÁ na forma canónica — é nessa forma que o
    # `colecao_config.json` dele está. (O `escreve_cfg` do teste escreve-o numa
    # linha só; medir o delta a partir daí media a formatação inicial, não o
    # efeito da gravação.)
    configio.escrever(configio.ler(CFG_PATH), CFG_PATH)
    sources._CFG_CACHE.clear()
    antes = CFG_PATH.read_text(encoding="utf-8")
    assert '"slot": "d1"' in antes
    assert sum(1 for l in antes.splitlines() if '"slot":' in l) == 2, \
        "o fixture não está na forma uma-linha-por-caixa"
    cfg = configio.ler(CFG_PATH)
    cfg["caixas"][0]["reserva_fora"] = [{"nm": "Force of Will", "em": HOJE}]
    configio.escrever(cfg, CFG_PATH)
    depois = CFG_PATH.read_text(encoding="utf-8")
    assert len(depois.splitlines()) - len(antes.splitlines()) <= 2, \
        f"o config cresceu {len(depois.splitlines()) - len(antes.splitlines())} linhas"
    # E a leitura aceita as DUAS formas: a lista de nomes de 2026-10-01 e a de
    # objectos com data de 2026-10-02.
    assert fases._retiradas(configio.ler(CFG_PATH)["caixas"][0]) == \
        {"Force of Will": HOJE}
    assert fases._retiradas({"reserva_fora": ["Swan Song"]}) == {"Swan Song": ""}


# ===========================================================================
def main():
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for f in casos:
        try:
            f()
            print(f"  ok   {f.__name__}")
        except Exception as e:                       # noqa: BLE001
            falhas += 1
            print(f"  FAIL {f.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                            # noqa: BLE001, S110
            pass
    print(f"\n{len(casos) - falhas}/{len(casos)} casos ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
