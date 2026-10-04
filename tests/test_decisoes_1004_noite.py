"""AS TRÊS DECISÕES DE 04/10/2026 AO FIM DO DIA (André).

  1. **o sideboard do Modern APLICA-SE**: -1 Consign to Memory (fica em 3),
     +1 Whipflare (entra, não tinha nenhum). O side continua em 15, e o registo
     da proposta original FICA (ele pode querer voltar atrás antes de 9/10).
     O Whipflare entra nas FALTAS com prioridade alta e data-limite 09/10/2026
     (primeiro dia do RC Ghent), e a excepção ao foil fica **PENDENTE DE DECISÃO
     DELE** — o foil só existe em New Phyrexia a 20,20 € contra 0,21 € do
     nonfoil, 96× por uma carta de sideboard em cópia única, e isso não se
     decide aqui.
  2. **o limiar das staples passa de 10 % para 20 %**, e a lista de candidatas a
     venda muda em consequência.
  3. **a vigia do arquétipo do Cloud no mtgtop8** (`archetype?a=2629`) ou corre
     a sério ou não está inscrita — uma vigia que não vigia é pior do que
     nenhuma, porque ele fica a pensar que está coberta.

Não toca na rede: a página do arquétipo é um trecho REAL, capturado a
04/10/2026 de `https://mtgtop8.com/archetype?a=2629&f=EDH`.
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

# O grupo `spml` exige foil — é essa regra que a excepção do Whipflare contorna.
REGRAS = [
    {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
     "dedicado": True, "lingua": "en", "acabamento": "foil"},
    {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
     "lingua": "pt", "acabamento": "nonfoil", "edicoes": "premodern",
     "estrita": True, "baldes": ["Colecção"]},
    # O grupo `prefere_foil` existe aqui por causa do defeito medido a
    # 2026-10-04: ver `caso_uma_caixa_prefere_foil_orcamenta_o_nonfoil`.
    {"grupo": "duel-commander", "formatos": ["duel-commander"],
     "dedicado": True, "lingua": "en", "acabamento": "prefere_foil"},
]
CAIXA_DC = {"slot": "dc", "nome": "Cloud (DC)", "formato": "duel-commander",
            "fonte": "escolhido", "ref": "dc", "balde": "Colecção",
            "estado": "permanente", "prioridade": 2}
URGENTE = {
    "carta": "Whipflare", "caixa": "modern", "prioridade": "alta",
    "ate": "2026-10-09",
    "porque": "entrou no sideboard a 04/10 e ele nao tem nenhum; RC Ghent 9-11/10",
    "material_pendente": {
        "estado": "PENDENTE DE DECISÃO DO ANDRÉ", "aplicado": False,
        "regra_do_grupo": "foil (grupo `spml`)",
        "sugerido_entretanto": "nonfoil",
        "porque": "o foil so existe em NPH a 20,20 EUR contra 0,21 do nonfoil",
        "precos": {"foil": 20.2, "nonfoil": 0.21}},
}
CAIXA = {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
         "fonte": "escolhido", "ref": "modern", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1}
BASE_CFG = {
    "regras_colecao": {}, "decks_vigiados": [],
    "baldes_coleccao": ["Colecção"],
    "regras_por_formato": REGRAS,
    "caixas": [CAIXA],
    "reserva": {"janela_dias": 30, "staples_premodern_pct": 20,
                "curva": [10, 20, 30, 40, 50]},
    "listas_escolhidas": {"modern": {
        "nome": "Modern — UW Oswald", "padrao": True, "formato": "modern",
        "cards": [["main", "Thoughtcast", 4], ["main", "Island", 56],
                  ["side", "Consign to Memory", 3], ["side", "Whipflare", 1],
                  ["side", "Blood Moon", 11]]}},
    "compras_urgentes": [URGENTE],
    "basicas": {"isentas_de_regras": True, "edicao": "Unhinged"},
}
CFG_PATH = _TMP / "cfg.json"


def escrever_cfg(cfg: dict) -> None:
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


escrever_cfg(BASE_CFG)
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout, mtgtop8, watchlist  # noqa: E402

CFG_REAL = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))

# O TRECHO REAL da página do arquétipo 2629, capturado a 2026-10-04. Quatro
# linhas: duas de MTGO/loja e duas do presencial que ele segue (Liwei Luo, 1.º).
PAGINA_ARQ = """
<table class=Stable>
<tr class=hover_tr>
  <td><input type=checkbox name=deck_check[1] value=1 checked><input type=hidden name=deck_ref[1] value=894562></td>
  <td><a href=/event?e=91455&d=894562&f=EDH>Cloud, Midgar Mercenary</a></td>
  <td><a class=player href=/search?player=ambroiseb1>ambroiseb1</a></td>
  <td><a href=/event?e=91455&f=EDH>MTGO League</a></td>
  <td class=O16><img src=/graph/star.png></td>
  <td>5</td>
  <td>30/09/26</td>
</tr>
<tr class=hover_tr>
  <td><input type=checkbox name=deck_check[2] value=1 checked><input type=hidden name=deck_ref[2] value=894751></td>
  <td><a href=/event?e=91487&d=894751&f=EDH>Cloud, Midgar Mercenary</a></td>
  <td><a class=player href=/search?player=Ybai34>Ybai34</a></td>
  <td><a href=/event?e=91487&f=EDH>Mr. Lee Cup #3</a></td>
  <td class=O16><img src=/graph/star.png></td>
  <td>3-4</td>
  <td>30/09/26</td>
</tr>
<tr class=hover_tr>
  <td><input type=checkbox name=deck_check[3] value=1 checked><input type=hidden name=deck_ref[3] value=894185></td>
  <td><a href=/event?e=91401&d=894185&f=EDH>Cloud, Midgar Mercenary</a></td>
  <td><a class=player href=/search?player=Liwei+Luo>Liwei Luo</a></td>
  <td><a href=/event?e=91401&f=EDH>Watermelon Champion Cup Nights</a></td>
  <td class=O16><img src=/graph/star.png></td>
  <td>1</td>
  <td>29/09/26</td>
</tr>
<tr class=hover_tr>
  <td><input type=checkbox name=deck_check[4] value=1 checked><input type=hidden name=deck_ref[4] value=894187></td>
  <td><a href=/event?e=91401&d=894187&f=EDH>Cloud, Midgar Mercenary</a></td>
  <td><a class=player href=/search?player=Ruicheng+Gao>Ruicheng Gao</a></td>
  <td><a href=/event?e=91401&f=EDH>Watermelon Champion Cup Nights</a></td>
  <td class=O16><img src=/graph/star.png></td>
  <td>3</td>
  <td>29/09/26</td>
</tr>
</table>
<div class=w_title>Duel Commander METAGAME BREAKDOWN</div>
<a href=/event?e=99999&f=EDH>isto nao e uma lista: nao tem deck nem data</a>
"""

# As impressões REAIS do Whipflare e do Cursed Totem, com os preços medidos a
# 2026-10-04 no price guide do Cardmarket.
CATALOGO = [
    ("Whipflare", "nph", "2011-05-13", ["nonfoil", "foil"],
     {"foil": 20.2, "nonfoil": 0.35}),
    ("Whipflare", "c14", "2014-11-07", ["nonfoil"], {"nonfoil": 0.21}),
    ("Cursed Totem", "mh2", "2021-06-18", ["nonfoil", "foil"],
     {"foil": 6.83, "nonfoil": 1.16}),
    ("Consign to Memory", "mh3", "2024-06-14", ["nonfoil", "foil"],
     {"foil": 7.4, "nonfoil": 5.79}),
    ("Thoughtcast", "mrd", "2003-10-02", ["nonfoil", "foil"],
     {"foil": 3.0, "nonfoil": 1.0}),
    ("Blood Moon", "mh2", "2021-06-18", ["nonfoil", "foil"],
     {"foil": 12.0, "nonfoil": 8.0}),
    ("Island", "unh", "2004-11-19", ["nonfoil", "foil"], {"nonfoil": 0.2}),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fins, precos) in enumerate(CATALOGO):
        tipo = "Basic Land" if nm == "Island" else "Artifact"
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, set_type)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'',?,?,?,0,0,'expansion')""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), str(i), tipo,
             json.dumps(fins), rel,
             json.dumps({"modern": "legal", "premodern": "legal"})))
        for f, p in precos.items():
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source,"
                        " finish, date, trend, low) VALUES (?, 'cardmarket', ?, "
                        "'2026-10-04', ?, ?)", (f"id-{i}", f, p, p))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", sc=None):
    q_sql = ("SELECT scryfall_id FROM catalog.cards WHERE name = ?"
             + (" AND set_code = ?" if sc else "") + " ORDER BY released_at LIMIT 1")
    sid = con.execute(q_sql, (nm, sc) if sc else (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,'en','player',?)""",
                (sid, q, finish, sub))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def falta_de(res, nm):
    s = res["slots"][0]
    return [m for m in s["missing"] if m["nm"] == nm]


# ---------------------------------------------------------------------------
# 1) O SIDEBOARD
# ---------------------------------------------------------------------------
def caso_o_sideboard_do_modern_tem_3_consign_1_whipflare_e_soma_15():
    """A decisão dele, no config A SÉRIO. É o que chumba sem o trabalho feito."""
    m = CFG_REAL["listas_escolhidas"]["modern"]
    side = {c[1]: c[2] for c in m["cards"] if c[0] == "side"}
    assert side.get("Consign to Memory") == 3, \
        f"o Consign to Memory tem de ficar em 3, está {side.get('Consign to Memory')}"
    assert side.get("Whipflare") == 1, "o Whipflare tem de entrar com 1 cópia"
    assert sum(side.values()) == 15, f"o side tem de somar 15, soma {sum(side.values())}"
    assert sum(c[2] for c in m["cards"] if c[0] == "main") == 60, "o main fica em 60"

    # O AJUSTE CONDICIONAL NÃO ENTRA NA LISTA. O Cursed Totem era um ajuste que
    # lhe foi proposto contra mais combo e que ele NÃO decidiu — pô-lo aqui era
    # decidir por ele.
    assert "Cursed Totem" not in side, \
        "o Cursed Totem é um ajuste condicional e NÃO decidido: não entra no side"

    # NADA SE APAGA: a proposta original fica, com o caminho de volta.
    p = m["proposta_sideboard"]
    assert p["estado"] == "APLICADA", p["estado"]
    assert p["estado_anterior"] == "PROPOSTA NÃO APLICADA"
    assert p["aplicada_em"] == "2026-10-04"
    assert p["tirar"] == ["side", "Consign to Memory", 1], "o registo do que saiu"
    assert p["meter"] == ["side", "Whipflare", 1], "o registo do que entrou"
    volta = p["como_voltar_atras"]
    for x in ("Consign to Memory", "Whipflare", "9/10"):
        assert x in volta, f"o caminho de volta tem de nomear '{x}': {volta}"
    print("sideboard: 3 Consign + 1 Whipflare = 15, proposta APLICADA e histórico no sítio")


def caso_o_whipflare_aparece_nas_faltas_com_a_data_limite():
    """A falta tem de dizer QUANDO é precisa — não havia campo nenhum."""
    escrever_cfg(BASE_CFG)
    con = base()
    res = loadout.report(con)
    linhas = falta_de(res, "Whipflare")
    assert linhas, "o Whipflare tem de estar nas faltas (ele não tem nenhum)"
    m = linhas[0]
    assert m["comprar"] == 1, m["comprar"]
    u = m.get("urgencia")
    assert u, "a linha de falta tem de trazer a ficha de urgência"
    assert u["ate"] == "2026-10-09", u["ate"]
    assert u["prioridade"] == "alta", u["prioridade"]
    assert u["dias"] is not None, "os dias até à data-limite calculam-se"
    assert "RC Ghent" in u["porque"], u["porque"]

    # O `dias` é CALCULADO e não escrito: a cinco dias diz 5, no dia seguinte 4.
    s = res["slots"][0]
    assert loadout.urgencia_da_compra(s, "Whipflare", hoje="2026-10-04")["dias"] == 5
    assert loadout.urgencia_da_compra(s, "Whipflare", hoje="2026-10-08")["dias"] == 1
    passou = loadout.urgencia_da_compra(s, "Whipflare", hoje="2026-10-11")
    assert passou["dias"] == -2 and passou["passou"] is True, \
        "uma data-limite que passou continua a dizer-se, não desaparece calada"

    # Uma carta SEM urgência escrita não ganha ficha nenhuma.
    outra = falta_de(res, "Consign to Memory")
    assert outra and "urgencia" not in outra[0], \
        "só a carta escrita no config leva urgência"
    print(f"faltas: Whipflare com data-limite {u['ate']} (faltam {u['dias']} dias), "
          f"prioridade {u['prioridade']}")


def caso_a_excepcao_do_foil_fica_pendente_e_nao_decidida():
    """Os dois preços à vista, o nonfoil sugerido, e a decisão NÃO tomada."""
    escrever_cfg(BASE_CFG)
    con = base()
    res = loadout.report(con)
    s = res["slots"][0]
    m = falta_de(res, "Whipflare")[0]

    # 1. A SUGESTÃO DE COMPRA é nonfoil, e DIZ que está pendente.
    assert "nonfoil" in m["req_compra"], m["req_compra"]
    assert loadout.RAZAO_EXCEPCAO_PENDENTE in m["req_compra"], m["req_compra"]
    assert m["marca_compra"] == "EN nonfoil", m["marca_compra"]
    # ... e o PREÇO é do acabamento que a linha pede. Orçamentar o foil numa
    # linha que pede nonfoil era mandá-lo comprar com 20,20 € na cabeça.
    assert m["unit"] == 0.21, f"o preço tem de ser o do nonfoil, está {m['unit']}"
    assert m["cost"] == 0.21, m["cost"]

    # 2. A DECISÃO NÃO ESTÁ TOMADA: o estado di-lo, e `aplicado` é falso.
    u = m["urgencia"]
    mp = u["material_pendente"]
    assert u["pendente"] is True, "a excepção tem de ficar PENDENTE"
    assert mp["aplicado"] is False
    assert "PENDENTE" in mp["estado"].upper(), mp["estado"]
    assert mp["precos"]["foil"] == 20.2 and mp["precos"]["nonfoil"] == 0.21, \
        "os dois preços ficam à vista para ele decidir"
    assert "foil" in mp["regra_do_grupo"], mp["regra_do_grupo"]

    # 3. E A ALOCAÇÃO NÃO MUDA: enquanto estiver pendente, a caixa continua a
    #    exigir foil. Um nonfoil NÃO fecha o slot — decidir isso era decidir a
    #    excepção por ele.
    add(con, "Whipflare", 1, "nonfoil", sc="c14")
    res2 = loadout.report(con)
    ainda = falta_de(res2, "Whipflare")
    assert ainda and ainda[0]["comprar"] == 1, \
        "com a excepção PENDENTE, um Whipflare nonfoil não pode fechar o slot"
    assert res2["slots"][0]["subs"], "a cópia aparece como substituto, não desaparece"

    # 4. QUANDO ELE DECIDIR (`aplicado: true`), passa a valer também na alocação.
    cfg = json.loads(json.dumps(BASE_CFG))
    cfg["compras_urgentes"][0]["material_pendente"]["aplicado"] = True
    escrever_cfg(cfg)
    res3 = loadout.report(con)
    assert not falta_de(res3, "Whipflare"), \
        "aplicada a excepção, o nonfoil fecha o slot"
    s3 = res3["slots"][0]
    assert not any(x["nm"] == "Whipflare" for x in s3["subs"]), \
        "deixa de ser substituto: passou a servir"
    escrever_cfg(BASE_CFG)
    print("foil: excepção PENDENTE — sugere nonfoil (0,21 € vs 20,20 €), "
          "não fecha o slot; com `aplicado` fecha")


def caso_uma_caixa_prefere_foil_orcamenta_o_nonfoil():
    """Um defeito MEU, medido a 2026-10-04 e corrigido antes de ir ao `main`.

    Ao fazer o preço seguir o acabamento da linha escrevi
    `in ("foil", "prefere_foil")` — e numa caixa `prefere_foil` (Duel Commander,
    Pauper) a compra pode ser NONFOIL, que é a mais barata que serve. O «fechar
    tudo» do Cloud subia **de 188,61 € para 228,99 €** (+40,38 €) sem uma única
    carta mudar de lado: o número por que ele decide, a mentir por causa de um
    `in`. Fica trancado.
    """
    escrever_cfg(dict(BASE_CFG, caixas=[CAIXA, CAIXA_DC],
                      listas_escolhidas=dict(
                          BASE_CFG["listas_escolhidas"],
                          dc={"nome": "Cloud (DC)", "padrao": True,
                              "formato": "duel-commander",
                              "cards": [["main", "Cursed Totem", 1]]})))
    con = base()
    res = loadout.report(con)
    s = [x for x in res["slots"] if x["slot"] == "dc"][0]
    m = [x for x in s["missing"] if x["nm"] == "Cursed Totem"][0]
    assert m["unit"] == 1.16, (
        f"numa caixa `prefere_foil` o orçamento é o NONFOIL (1,16 €), "
        f"não o foil (6,83 €) — está {m['unit']}")
    assert "foil (ou nonfoil)" in m["req_compra"], m["req_compra"]
    assert m["marca_compra"] == "EN foil ou nonfoil", m["marca_compra"]
    escrever_cfg(BASE_CFG)
    print("prefere_foil: a compra orçamenta-se ao nonfoil (1,16 €, não 6,83 €)")


# ---------------------------------------------------------------------------
# 2) O LIMIAR DAS STAPLES
# ---------------------------------------------------------------------------
def caso_o_limiar_da_reserva_e_20():
    """No config a sério, e com a razão escrita ao lado."""
    assert CFG_REAL["reserva"]["staples_premodern_pct"] == 20, \
        CFG_REAL["reserva"]["staples_premodern_pct"]
    porque = CFG_REAL["reserva"].get("_staples_premodern_pct") or ""
    for x in ("cartas_partilhadas", "rotativas", "20 %"):
        assert x in porque, f"a razão tem de dizer '{x}': daqui a um mês ninguém se lembra"
    # A medição tem de estar escrita, com números e não impressões.
    assert "606" in porque and "609" in porque, \
        "a razão leva os números medidos da lista de candidatas"
    print("reserva: staples_premodern_pct = 20, com a razão e os números medidos")


def caso_a_lista_de_candidatas_muda_com_o_limiar():
    """O corte MAIS ALTO protege MENOS: uma staple entre 10 % e 20 % cai."""
    from mtgvault import fases                                  # noqa: PLC0415
    escrever_cfg(BASE_CFG)
    con = base()
    # 10 listas de premodern com sideboard; a carta está em 1 (10 %) e a outra
    # em 3 (30 %). Com o corte a 20 % só a segunda continua staple.
    for i in range(10):
        con.execute("""INSERT INTO decklists (format, event_date, event_name,
                       source, source_key, player, content_hash)
                       VALUES ('premodern', date('now'), ?, 'mtgo', ?, ?, ?)""",
                    (f"ev{i}", f"k{i}", f"p{i}", f"h{i}"))
        did = con.execute("SELECT MAX(id) i FROM decklists").fetchone()["i"]
        con.execute("""INSERT INTO decklist_cards (decklist_id, board, card_name,
                       quantity) VALUES (?, 'side', 'Thoughtcast', 1)""", (did,))
        if i == 0:
            con.execute("""INSERT INTO decklist_cards (decklist_id, board,
                           card_name, quantity) VALUES (?, 'side', 'Cursed Totem', 1)""",
                        (did,))
        if i < 3:
            con.execute("""INSERT INTO decklist_cards (decklist_id, board,
                           card_name, quantity) VALUES (?, 'side', 'Blood Moon', 1)""",
                        (did,))
    con.commit()

    a10 = fases.staples_sideboard(con, corte=10, cache={})
    a20 = fases.staples_sideboard(con, corte=20, cache={})
    assert "Cursed Totem" in a10["nomes"], a10["nomes"]
    assert "Cursed Totem" not in a20["nomes"], \
        "a 10 % é staple, a 20 % deixa de ser — é isto que muda a lista"
    assert "Blood Moon" in a20["nomes"], "30 % continua staple nos dois cortes"
    assert a20["n"] < a10["n"], (a10["n"], a20["n"])
    assert a20["corte"] == 20
    # O corte em vigor sai do config e não de um valor escrito no código.
    assert fases.staples_corte() == 20, fases.staples_corte()
    print(f"candidatas: staples {a10['n']} a 10 % -> {a20['n']} a 20 %; "
          "o Cursed Totem deixa de ser protegido como staple")


# ---------------------------------------------------------------------------
# 3) A VIGIA DO ARQUÉTIPO
# ---------------------------------------------------------------------------
def caso_o_parser_do_arquetipo_le_a_pagina_real():
    """Reaproveita as regex do mtgtop8; a COLOCAÇÃO é o que faltava ler."""
    rows = mtgtop8.parse_archetype_rows(PAGINA_ARQ)
    assert len(rows) == 4, f"4 listas, não {len(rows)}"
    assert [r["deck_id"] for r in rows] == [894562, 894751, 894185, 894187]
    assert rows[0]["jogador"] == "ambroiseb1" and rows[0]["evento"] == "MTGO League"
    assert rows[0]["posicao"] == "5" and rows[0]["data"] == "2026-09-30"
    # O jogador com espaço vem como `Liwei+Luo` no link.
    assert rows[2]["jogador"] == "Liwei Luo", rows[2]["jogador"]
    assert rows[2]["posicao"] == "1" and rows[2]["data"] == "2026-09-29"
    assert rows[1]["posicao"] == "3-4", "o bracket fica tal e qual"
    # O link do «METAGAME BREAKDOWN» não é uma lista: não tem deck nem data.
    assert all(r["deck_id"] != 99999 for r in rows)
    # Os ids batem com o parser antigo — é a mesma página.
    assert [r["deck_id"] for r in rows] == mtgtop8.parse_deck_ids(PAGINA_ARQ)

    melhor = watchlist._melhor(rows)
    assert melhor["deck_id"] == 894185, \
        "a melhor é a de posição 1 mais recente (Liwei Luo, 29/09)"
    print("parser: 4 listas da página real, melhor = Liwei Luo 1.º @ 29/09")


def caso_a_vigia_do_arquetipo_corre_a_serio():
    """Inscrever não basta: tem de haver quem a corra, e detectar as duas coisas."""
    escrever_cfg(BASE_CFG)
    con = base()
    wid = watchlist.add(con, "mtgtop8_archetype", "2629", "Cloud (DC)",
                        "duel-commander")
    assert wid, "o kind novo tem de ser aceite pelo CHECK da tabela"
    assert "mtgtop8_archetype" in watchlist.VERIFICADORES, \
        "uma vigia inscrita sem verificador nunca corre"

    chamadas = []

    def falso(aid, fmt):
        chamadas.append((aid, fmt))
        return mtgtop8.parse_archetype_rows(PAGINA_ARQ)

    real = mtgtop8.archetype_listas
    mtgtop8.archetype_listas = falso
    try:
        r = watchlist.check_mtgtop8_archetype(con, wid)
        assert chamadas == [(2629, "duel-commander")], chamadas
        assert r["listas"] == 4 and r["changed"] is True
        assert r["primeira_vez"] is True and r["novas"] == []
        assert r["melhor"]["deck_id"] == 894185

        # 2.ª corrida, nada mudou: não há sinal falso.
        r2 = watchlist.check_mtgtop8_archetype(con, wid)
        assert r2["changed"] is False and r2["novas"] == []
        assert r2["melhor_mudou"] is False

        # LISTA NOVA: um deck que a página não tinha.
        nova = PAGINA_ARQ.replace("value=894562", "value=894562").replace(
            "</table>", """<tr class=hover_tr>
  <td><input type=hidden name=deck_ref[5] value=896000></td>
  <td><a href=/event?e=91500&d=896000&f=EDH>Cloud, Midgar Mercenary</a></td>
  <td><a class=player href=/search?player=NovoJogador>NovoJogador</a></td>
  <td><a href=/event?e=91500&f=EDH>Torneio Novo</a></td>
  <td class=O16><img src=/graph/star.png></td>
  <td>2</td>
  <td>03/10/26</td>
</tr></table>""")
        mtgtop8.archetype_listas = lambda a, f: mtgtop8.parse_archetype_rows(nova)
        r3 = watchlist.check_mtgtop8_archetype(con, wid)
        assert r3["changed"] is True, "uma lista nova é uma mudança"
        assert [x["deck_id"] for x in r3["novas"]] == [896000], r3["novas"]
        assert r3["melhor_mudou"] is False, "a melhor continua a ser a de 1.º"

        # A MELHOR MUDOU: alguém ganhou um torneio depois.
        venceu = nova.replace("<td>2</td>\n  <td>03/10/26</td>",
                              "<td>1</td>\n  <td>03/10/26</td>")
        mtgtop8.archetype_listas = lambda a, f: mtgtop8.parse_archetype_rows(venceu)
        r4 = watchlist.check_mtgtop8_archetype(con, wid)
        assert r4["melhor"]["deck_id"] == 896000, r4["melhor"]
        assert r4["melhor_mudou"] is True, \
            "a troca da melhor classificada é a segunda coisa que ele quer ver"
    finally:
        mtgtop8.archetype_listas = real
    print("vigia: corre, detecta lista nova e a troca da melhor classificada")


def caso_um_kind_sem_verificador_nao_passa_calado():
    """Uma vigia que não vigia é pior do que nenhuma."""
    escrever_cfg(BASE_CFG)
    con = base()
    # O `archetype` está no CHECK desde o primeiro dia e NUNCA foi implementado.
    con.execute("""INSERT INTO watched (kind, key, label, format)
                   VALUES ('archetype', '1', 'orfã', 'modern')""")
    con.commit()
    res = watchlist.check_all(con)
    orfa = [r for r in res if r["watched"]["kind"] == "archetype"]
    assert len(orfa) == 1, "tem de SAIR uma linha, não ser saltada em silêncio"
    assert orfa[0].get("nao_implementado") is True
    assert "NAO corre" in orfa[0]["error"], orfa[0]["error"]
    print("check_all: um kind sem verificador sai com erro, não calado")


def caso_a_migracao_da_watched_nao_perde_o_historico():
    """O CHECK reconstrói a tabela — e a `watched_snapshots` tem CASCADE."""
    d = Path(tempfile.mkdtemp())
    v, c = d / "v.db", d / "c.db"
    con = db.connect(v, c)
    db.init(con)
    # Reconstrói a tabela na forma ANTIGA (sem o kind novo), com dados e um
    # snapshot — é a base dele antes desta ordem.
    con.commit()
    con.execute("PRAGMA foreign_keys = OFF")
    con.executescript("""
        DROP TABLE watched_snapshots; DROP TABLE watched;
        CREATE TABLE watched (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('mtgo_player','moxfield','archetype')),
            key TEXT NOT NULL, label TEXT NOT NULL, format TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            last_checked TEXT, last_hash TEXT, notes TEXT,
            UNIQUE (kind, key, format));
        CREATE TABLE watched_snapshots (
            id INTEGER PRIMARY KEY,
            watched_id INTEGER NOT NULL REFERENCES watched(id) ON DELETE CASCADE,
            taken_at TEXT NOT NULL, list_hash TEXT NOT NULL, source_url TEXT,
            cards TEXT NOT NULL, UNIQUE (watched_id, list_hash));
        INSERT INTO watched (kind, key, label, format)
            VALUES ('mtgo_player','Luffy','Luffy — Pauper','pauper');
        INSERT INTO watched_snapshots (watched_id, taken_at, list_hash, cards)
            VALUES (1, '2026-09-01', 'abc', '[["main","Island",4]]');
    """)
    con.commit()
    con.execute("PRAGMA foreign_keys = ON")
    try:
        con.execute("""INSERT INTO watched (kind, key, label, format)
                       VALUES ('mtgtop8_archetype','2629','x','duel-commander')""")
        raise AssertionError("o CHECK antigo tinha de recusar o kind novo")
    except sqlite3.IntegrityError:
        con.rollback()

    db.init(con)                                   # a migração
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name='watched'"
                      ).fetchone()["sql"]
    assert "mtgtop8_archetype" in sql, "o CHECK tem de passar a aceitar o kind novo"
    assert con.execute("SELECT COUNT(*) c FROM watched").fetchone()["c"] == 1, \
        "a vigia que lá estava não se perde"
    assert con.execute("SELECT COUNT(*) c FROM watched_snapshots"
                       ).fetchone()["c"] == 1, \
        "o histórico NÃO pode ir atrás do DROP (a FK é ON DELETE CASCADE)"
    assert not list(con.execute("PRAGMA foreign_key_check")), "sem órfãos"
    wid = watchlist.add(con, "mtgtop8_archetype", "2629", "Cloud", "duel-commander")
    assert wid, "e agora o kind novo entra"
    # Idempotente: correr outra vez não mexe em nada.
    db.init(con)
    assert con.execute("SELECT COUNT(*) c FROM watched").fetchone()["c"] == 2
    con.close()
    print("migração: CHECK novo, 1 vigia e 1 snapshot preservados, idempotente")


def run():
    caso_o_sideboard_do_modern_tem_3_consign_1_whipflare_e_soma_15()
    caso_o_whipflare_aparece_nas_faltas_com_a_data_limite()
    caso_a_excepcao_do_foil_fica_pendente_e_nao_decidida()
    caso_uma_caixa_prefere_foil_orcamenta_o_nonfoil()
    caso_o_limiar_da_reserva_e_20()
    caso_a_lista_de_candidatas_muda_com_o_limiar()
    caso_o_parser_do_arquetipo_le_a_pagina_real()
    caso_a_vigia_do_arquetipo_corre_a_serio()
    caso_um_kind_sem_verificador_nao_passa_calado()
    caso_a_migracao_da_watched_nao_perde_o_historico()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
