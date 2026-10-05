"""A LISTA DE UM DECK É UMA LISTA QUE ALGUÉM JOGOU (André, 2026-10-04, ao fim do
dia).

As palavras dele: *"as listas especificas e que quero fixas"* e *"as outras quero
que esquecas as decklists e vamos focar nas decklists baseadas em eventos
reais"*. Acaba o consenso como lista de DECK: uma média de muitas listas é um
deck que ninguém jogou. O motor do consenso **não se apaga** — continua a medir o
metagame, a dar os nomes e a alimentar a reserva da venda.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_listas_eventos.py`, que desliga uma peça de cada vez e exige
vermelho:

  1. a regra prefere PRESENCIAL a online;
  2. entre presenciais, o CAMPO MAIOR;
  3. entre online, o evento mais IMPORTANTE (um RC Qualifier antes de uma
     Challenge) — sem isto o vault preferia a Challenge por ela ter contagem de
     jogadores e a qualificação não, ou seja deixava a FONTE decidir;
  4. a MESMA lista repetida em vários resultados ganha a um resultado único
     melhor (o caso do Cloud, três primeiros lugares sem mudar uma carta);
  5. uma Challenge sem classificação desempata pela DATA, não pela repetição —
     jogar a mesma lista em três 5-0 não é «ter ganhado três vezes»;
  6. a JANELA filtra PRIMEIRO, e a melhor presencial que ela corta fica ao lado
     com o aviso de que é anterior ao Reality Fracture;
  7. o premodern está EXCEPCIONADO da janela e usa a história toda;
  8. a proveniência GRAVA-SE e sobrevive ao `prune_decklists(30)`;
  9. a caixa trocada mostra as SEIS coisas: jogador, evento, data, jogadores,
     classificação e URL;
 10. o consenso que saiu da caixa fica GUARDADO e uma segunda passagem não o
     pisa;
 11. nenhum deck mostra um consenso com a mesma cara de uma lista real;
 12. um deck que estava TRANCADO por falta de amostra destranca com uma lista
     real (a `premodern-igg`, 4 listas e um mínimo de 5);
 13. uma caixa sem carta-assinatura continua VAZIA e a pedi-la;
 14. os decks dele entram mesmo quando a fonte não lhes dá nome nenhum;
 15. um deck por confirmar NÃO fica marcado como deck a montar;
 16. a amostra fina de uma lista só vai para a página, e não para um rodapé.

E dois casos lêem o `colecao_config.json` A SÉRIO: as cinco caixas que ele
mandou não tocar e as sete que trocaram.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

CAIXAS = [
    {"slot": "pm-oath", "nome": "Oath of Druids", "formato": "premodern",
     "fonte": "consenso", "assinatura": ["Oath of Druids"], "balde": "Colecção",
     "estado": "permanente", "prioridade": 1},
    {"slot": "pm-igg", "nome": "Ill-Gotten Gains", "formato": "premodern",
     "fonte": "consenso", "assinatura": ["Ill-Gotten Gains"], "balde": "Colecção",
     "estado": "permanente", "prioridade": 2},
    {"slot": "pi-grease", "nome": "Greasefang", "formato": "pioneer",
     "fonte": "consenso", "assinatura": ["Greasefang"], "balde": "Colecção",
     "estado": "permanente", "prioridade": 3},
    {"slot": "lg-azul", "nome": "Artifacts Blue", "formato": "legacy",
     "fonte": "manual", "ref": None, "balde": "Colecção",
     "estado": "permanente", "prioridade": 4},
]
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
        {"grupo": "spml", "formatos": ["pioneer", "legacy", "modern"],
         "dedicado": True, "cartas_partilhadas": "rotativas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 30},
    "decks_montar": {},
    # A JANELA DO CONSENSO de 2026-10-03, com a excepção do premodern.
    "consenso": {"desde": "2026-09-29", "excepcoes": ["premodern"]},
    "metagame_fontes": {"_default": {"tiers": ["Presencial", "Qualifier",
                                              "Challenge"],
                                     "min_jogadores_presencial": 0,
                                     "ligas": False}},
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

from mtgvault import (configio, db, decks_vista as dv,  # noqa: E402
                      eventos, loadout, sources)

CATALOGO = [
    ("Oath of Druids", "exo", "1998-06-15", 40.0, "Enchantment"),
    ("Ill-Gotten Gains", "usg", "1998-10-12", 30.0, "Sorcery"),
    ("Greasefang, Okiba Boss", "neo", "2022-02-18", 5.0,
     "Legendary Creature — Rat"),
    ("Forbidden Orchard", "chk", "2004-10-01", 20.0, "Land"),
    ("Brainstorm", "ice", "1995-06-01", 1.0, "Instant"),
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.5, "Instant"),
    ("Parallax Wave", "nem", "2000-02-14", 25.0, "Enchantment"),
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
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-04', ?, ?)", (f"id-{i}", preco, preco))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def lista(con, *, fmt, jogador, evento, data, tier, jogadores=None,
          pos=None, cards=(("main", "Oath of Druids", 1),), url=None,
          hash_=None, fonte="mtgtop8"):
    """Uma decklist com proveniência, como o mtgtop8/mtgo a dão."""
    cur = con.execute(
        """INSERT INTO decklists (source, source_key, format, event_name,
             event_date, player, placement, url, content_hash, fetched_at,
             event_tier, event_players)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (fonte, f"{evento}-{jogador}-{data}", fmt, evento, data, jogador, pos,
         url or f"https://mtgtop8.com/event?e=1&d={jogador}", hash_ or f"h-{jogador}-{data}",
         "2026-10-04", tier, jogadores))
    did = cur.lastrowid
    for board, nm, q in cards:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name, "
                    "quantity, board) VALUES (?,?,?,?)", (did, nm, q, board))
    con.commit()
    return did


# ===========================================================================
# 1-3. A ORDEM DOS CRITÉRIOS
# ===========================================================================
def caso_a_regra_prefere_presencial_a_online():
    """*"presenciais antes de online -- papel e o que ele joga"*."""
    escreve_cfg()
    con = base()
    ch = lista(con, fmt="premodern", jogador="online", evento="Challenge 32",
               data="2026-09-20", tier="Challenge", jogadores=200, pos="1")
    pr = lista(con, fmt="premodern", jogador="papel", evento="Torneio",
               data="2026-09-05", tier="Presencial", jogadores=20, pos="9-16")
    r = eventos.escolher(con, "premodern", [ch, pr])
    assert r["escolhida"]["decklist_id"] == pr, r["escolhida"]
    # E diz porquê, em português.
    assert "presencial" in r["porque"], r["porque"]


def caso_entre_presenciais_ganha_o_campo_maior():
    """*"um 5-8 de 218 jogadores vale mais do que um 1.o lugar de 16"*."""
    escreve_cfg()
    con = base()
    peq = lista(con, fmt="premodern", jogador="campeao-pequeno", evento="Loja",
                data="2026-09-20", tier="Presencial", jogadores=16, pos="1")
    gr = lista(con, fmt="premodern", jogador="oitavos-grande", evento="Europeu",
               data="2026-09-05", tier="Presencial", jogadores=218, pos="5-8")
    r = eventos.escolher(con, "premodern", [peq, gr])
    assert r["escolhida"]["decklist_id"] == gr, r["escolhida"]
    assert "218" in r["porque"], r["porque"]


def caso_entre_online_ganha_o_evento_mais_importante():
    """O RC Super Qualifier antes da Challenge — e a razão é de DADOS.

    Medido na base a sério a 2026-10-04: o `Modern RC Super Qualifier` vem do
    mtgo.com e tem **31 listas, zero classificações e zero contagens de
    jogadores**; a mesma Challenge re-hospedada pelo mtgtop8 traz `100 jogadores`
    e `3-4`. Sem o critério do tier, o vault preferia a Challenge — ou seja
    deixava a FONTE decidir o que devia ser decidido pelo torneio. Foi assim que
    ele escolheu, 9 vezes de 9.
    """
    escreve_cfg()
    con = base()
    ch = lista(con, fmt="modern", jogador="challenger", evento="MTGO Challenge 64",
               data="2026-10-01", tier="Challenge", jogadores=100, pos="3-4")
    qu = lista(con, fmt="modern", jogador="qualificando", evento="RC Super Qualifier",
               data="2026-10-03", tier="Qualifier", jogadores=None, pos=None,
               fonte="mtgo")
    r = eventos.escolher(con, "modern", [ch, qu])
    assert r["escolhida"]["decklist_id"] == qu, r["escolhida"]
    assert "Qualifier" in r["porque"], r["porque"]


# ===========================================================================
# 4-5. A LISTA REPETIDA, E O QUE NÃO CONTA COMO REPETIÇÃO
# ===========================================================================
def caso_a_lista_repetida_ganha_a_um_resultado_unico_melhor():
    """O caso do Cloud: TRÊS primeiros lugares com a MESMA lista, sem mudar uma
    vírgula. Ganha a um 1.º lugar isolado no mesmo tamanho de campo.

    E o que decide é a contagem de VITÓRIAS, não de resultados — *"se o MESMO
    piloto **ganhou** mais de uma vez"*. Medido a 2026-10-04: com a contagem de
    resultados, três 9-16 ganhavam a um 5-8, e no Esper Blink isso afastava a
    escolha da dele. Ganhar é vencer; o caso que originou a regra são três
    PRIMEIROS lugares.
    """
    escreve_cfg()
    con = base()
    unico = lista(con, fmt="premodern", jogador="unico", evento="A",
                  data="2026-09-29", tier="Presencial", jogadores=20, pos="1")
    for i, data in enumerate(("2026-09-08", "2026-09-22", "2026-09-28")):
        rep = lista(con, fmt="premodern", jogador="tricampeao", evento=f"B{i}",
                    data=data, tier="Presencial", jogadores=20, pos="1",
                    hash_="mesma-lista")
    r = eventos.escolher(con, "premodern", [unico, rep])
    esc = r["escolhida"]
    # Ganha apesar de a do «unico» ser MAIS RECENTE: a repetição vem antes da data.
    assert esc["jogador"] == "tricampeao", esc
    assert esc["vitorias"] == 3 and esc["repetida"] == 3, esc
    assert "venceu 3 vezes" in r["porque"], r["porque"]
    # E a prova viaja no registo, para a página a poder mostrar depois da poda.
    assert len(esc["repeticoes"]) == 3, esc

    # TRÊS NONOS LUGARES NÃO SÃO TRÊS VITÓRIAS: aí a classificação manda.
    con2 = base()
    bom = lista(con2, fmt="premodern", jogador="quinto", evento="C",
                data="2026-09-29", tier="Challenge", jogadores=45, pos="5-8")
    for i, data in enumerate(("2026-09-20", "2026-09-22", "2026-09-28")):
        pior = lista(con2, fmt="premodern", jogador="nono", evento=f"D{i}",
                     data=data, tier="Challenge", jogadores=45, pos="9-16",
                     hash_="tres-nonos")
    r2 = eventos.escolher(con2, "premodern", [bom, pior])
    assert r2["escolhida"]["jogador"] == "quinto", r2["escolhida"]


def caso_uma_challenge_sem_classificacao_nao_conta_como_ter_ganhado():
    """Jogar a mesma lista em três 5-0 do MTGO **não** é ter ganhado três vezes.

    É o caso real da `premodern-igg`: o Vlalutscher tem a mesma lista em 08/09 e
    10/09 e outra a 03/10. Se a repetição contasse, a de 08/09 ganhava; ele
    escolheu a de 03/10 — a mais recente. Uma Challenge do mtgo.com não traz
    classificação nenhuma, logo não prova resultado.
    """
    escreve_cfg()
    con = base()
    for data in ("2026-09-08", "2026-09-10"):
        velha = lista(con, fmt="premodern", jogador="vlal", evento="Challenge 32",
                      data=data, tier="Challenge", pos=None, hash_="mesma",
                      fonte="mtgo")
    nova = lista(con, fmt="premodern", jogador="vlal", evento="Challenge 16",
                 data="2026-10-03", tier="Challenge", pos=None, fonte="mtgo")
    r = eventos.escolher(con, "premodern", [velha, nova])
    assert r["escolhida"]["decklist_id"] == nova, r["escolhida"]
    assert r["escolhida"]["repetida"] == 0, r["escolhida"]
    assert "mais recente" in r["porque"], r["porque"]


# ===========================================================================
# 6-7. A JANELA
# ===========================================================================
def caso_a_janela_filtra_primeiro_e_a_alternativa_fica_ao_lado():
    """A regra 5 dele, à letra: *"se a melhor presencial for ANTERIOR a janela,
    NAO a esconda e NAO a descartes: mostra-a com a data bem visivel (...) e poe
    ao lado a melhor lista DENTRO da janela, para ele escolher."*

    É o caso real do Greasefang: a melhor presencial é de 22/09 (3-4 de 65) e a
    janela começa a 29/09, por isso a escolhida é a Challenge de 01/10. Sem a
    janela a filtrar PRIMEIRO, o vault escolhia a lista pré-Reality Fracture e
    contradizia a escolha dele.
    """
    escreve_cfg()
    con = base()
    velha = lista(con, fmt="pioneer", jogador="presencial-velho", evento="Papel",
                  data="2026-09-22", tier="Presencial", jogadores=65, pos="3-4",
                  cards=(("main", "Greasefang, Okiba Boss", 4),))
    nova = lista(con, fmt="pioneer", jogador="challenge-nova", evento="Challenge 32",
                 data="2026-10-01", tier="Challenge", pos=None, fonte="mtgo",
                 cards=(("main", "Greasefang, Okiba Boss", 4),))
    r = eventos.escolher(con, "pioneer", [velha, nova])
    assert r["escolhida"]["decklist_id"] == nova, r["escolhida"]
    alt = r["alternativa"]
    assert alt is not None, "a melhor presencial tem de ficar ao lado"
    assert alt["decklist_id"] == velha, alt
    assert alt["data"] == "2026-09-22", alt
    assert "Reality Fracture" in alt["porque"], alt["porque"]


def caso_o_premodern_esta_excepcionado_da_janela():
    """O Reality Fracture não é legal em Premodern (o formato acaba no Scourge):
    lá a história toda conta, e uma lista de 05/09 pode ganhar."""
    escreve_cfg()
    con = base()
    velha = lista(con, fmt="premodern", jogador="europeu", evento="Europeu",
                  data="2026-09-05", tier="Presencial", jogadores=218, pos="1")
    nova = lista(con, fmt="premodern", jogador="recente", evento="Challenge",
                 data="2026-10-03", tier="Challenge", pos=None, fonte="mtgo")
    r = eventos.escolher(con, "premodern", [velha, nova])
    assert r["escolhida"]["decklist_id"] == velha, r["escolhida"]
    # E não há alternativa a mostrar: a janela não cortou nada.
    assert r["alternativa"] is None, r["alternativa"]


# ===========================================================================
# 8. A PROVENIÊNCIA GRAVA-SE E SOBREVIVE À PODA
# ===========================================================================
def caso_a_proveniencia_grava_se_e_sobrevive_a_poda():
    """O `daily.prune_decklists(30)` apaga as decklists ao fim de um mês.

    Uma caixa que fosse um PONTEIRO para um `decklist_id` ficava **vazia em
    Novembro**, sem um único passo a falhar — o padrão do `event_tier` aplicado à
    lista por que ele vai sleevar. Este caso apaga a decklist à mão e exige que a
    caixa continue com as cartas E com a ficha de onde veio.
    """
    cfg = escreve_cfg()
    con = base()
    did = lista(con, fmt="premodern", jogador="Shroomboy", evento="Buckeye Brawl II",
                data="2026-09-12", tier="Presencial", jogadores=125, pos="1",
                cards=(("main", "Oath of Druids", 4), ("main", "Forbidden Orchard", 4),
                       ("side", "Brainstorm", 2)))
    eventos.fixar(cfg, con, "pm-oath", did, nome="Oath of Druids",
                  formato="premodern", quando="2026-10-04")
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None

    # A PODA: a decklist desaparece da base, como daqui a um mês.
    con.execute("DELETE FROM decklist_cards WHERE decklist_id = ?", (did,))
    con.execute("DELETE FROM decklists WHERE id = ?", (did,))
    con.commit()
    assert con.execute("SELECT COUNT(*) c FROM decklists").fetchone()["c"] == 0

    s = next(x for x in __import__("mtgvault.caixas", fromlist=["x"]).slots(
        sources.config()) if x["slot"] == "pm-oath")
    cards, nota = loadout._slot_cards(con, s)
    assert sum(q for _b, _n, q in cards) == 10, cards
    prov = (eventos.registo_de_evento(sources.config(), "pm-oath") or {})["evento"]
    assert prov["jogador"] == "Shroomboy", prov
    assert prov["jogadores"] == 125 and prov["classificacao"] == "1", prov
    assert "Shroomboy" in nota, nota


# ===========================================================================
# 9. A CAIXA TROCADA MOSTRA AS SEIS COISAS
# ===========================================================================
def caso_a_caixa_trocada_mostra_as_seis_coisas():
    """*"Na pagina de cada deck fica SEMPRE, a vista: jogador, evento, data,
    numero de jogadores, classificacao e o URL da fonte."* Ele vai sleevar a
    partir disto."""
    cfg = escreve_cfg()
    con = base()
    did = lista(con, fmt="premodern", jogador="Max Deschamps", evento="Buckeye Brawl II",
                data="2026-09-12", tier="Presencial", jogadores=125, pos="2",
                url="https://mtgtop8.com/event?e=90776&d=889300&f=PREM",
                cards=(("main", "Oath of Druids", 4),))
    eventos.fixar(cfg, con, "pm-oath", did, nome="Oath of Druids",
                  formato="premodern", quando="2026-10-04")
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None

    rep = dv.relatorio(con, sources.config())
    linha = next(d for f in rep["formatos"] for d in f["decks"]
                 if d["id"] == "caixa:pm-oath")
    e = linha["evento"]
    for campo, valor in (("jogador", "Max Deschamps"),
                         ("evento", "Buckeye Brawl II"),
                         ("data", "2026-09-12"), ("jogadores", 125),
                         ("classificacao", "2")):
        assert e[campo] == valor, (campo, e)
    assert e["url"].startswith("https://mtgtop8.com/"), e
    # E a parte do deck leva a MESMA ficha — é lá que ele a lê antes de sleevar.
    d = rep["decks"]["caixa:pm-oath"]
    p = dv.deck_para_pagina(con, d, rep["pos"], "rotativas", {})
    assert p["evento"]["jogador"] == "Max Deschamps", p["evento"]


# ===========================================================================
# 10. O CONSENSO FICA GUARDADO, E NÃO SE PISA
# ===========================================================================
def caso_o_consenso_anterior_fica_guardado_e_nao_se_pisa():
    """*Nada se apaga* (regra dele de 2026-09-09): a média que a caixa mostrava
    fica, com a data e a razão, para ele poder comparar com a lista real.

    E uma SEGUNDA passagem não a pisa — custou duas medições a descobrir: o
    `padrao.fixar` substitui o registo inteiro por um dicionário novo, por isso o
    bloco desaparecia e era recriado com a lista de evento que a primeira
    passagem acabara de fixar.
    """
    cfg = escreve_cfg()
    con = base()
    did = lista(con, fmt="premodern", jogador="Shroomboy", evento="Buckeye",
                data="2026-09-12", tier="Presencial", jogadores=125, pos="1",
                cards=(("main", "Oath of Druids", 4),))
    consenso = [["main", "Oath of Druids", 3], ["main", "Forbidden Orchard", 4]]
    eventos.fixar(cfg, con, "pm-oath", did, nome="Oath", formato="premodern",
                  consenso_antes=consenso, consenso_nota="consenso de 32 listas",
                  quando="2026-10-04")
    rec = cfg["listas_escolhidas"]["pm-oath"]
    assert rec["_consenso_anterior"]["cards"] == consenso, rec
    assert rec["_consenso_anterior"]["nota"] == "consenso de 32 listas", rec

    # Segunda passagem, agora com a lista de evento como «anterior»: não pisa.
    eventos.fixar(cfg, con, "pm-oath", did, nome="Oath", formato="premodern",
                  consenso_antes=[["main", "Oath of Druids", 4]],
                  consenso_nota="lista padrão fixada", quando="2026-10-04")
    rec = cfg["listas_escolhidas"]["pm-oath"]
    assert rec["_consenso_anterior"]["cards"] == consenso, rec
    assert rec["_consenso_anterior"]["nota"] == "consenso de 32 listas", rec


# ===========================================================================
# 11. UM CONSENSO DIZ QUE É UM CONSENSO
# ===========================================================================
def caso_nenhum_deck_mostra_consenso_como_se_fosse_a_lista():
    """O meta fica para CONSULTA (*"ficam no meta para consulta"*), e por isso
    continua a mostrar a média — o que não pode é ter a mesma cara de uma lista
    que alguém jogou na página por onde ele vai sleevar."""
    escreve_cfg()
    con = base()
    # Cinco listas nomeadas: o mínimo para o meta chamar consenso a isto.
    for i in range(5):
        lista(con, fmt="pioneer", jogador=f"p{i}", evento="Challenge 32",
              data="2026-10-01", tier="Challenge", pos=None, fonte="mtgo",
              cards=(("main", "Greasefang, Okiba Boss", 4),
                     ("main", "Brainstorm", 4)))
    con.execute("UPDATE decklists SET arquetipo_fonte = 'Greasefang' "
                "WHERE format = 'pioneer'")
    con.commit()
    rep = dv.relatorio(con, sources.config())
    metas = [d for f in rep["formatos"] for d in f["decks"]
             if d["id"].startswith("meta:")]
    assert metas, "o meta tem de continuar a existir, para consulta"
    for m in metas:
        assert m["e_consenso"], m
        assert "ninguém jogou" in m["rotulo_estado"], m
        assert not m["evento"], m


# ===========================================================================
# 12-13. DESTRANCAR, E O QUE CONTINUA TRANCADO
# ===========================================================================
def caso_um_deck_sem_amostra_destranca_com_uma_lista_real():
    """A `premodern-igg` tinha **4 listas** e o mínimo para se chamar consenso a
    algo é 5 — ficava sem lista nenhuma. Com a regra nova não precisa de 5:
    precisa de UMA lista real."""
    cfg = escreve_cfg()
    con = base()
    ids = [lista(con, fmt="premodern", jogador=f"v{i}", evento="Challenge 32",
                 data=f"2026-09-0{i + 1}", tier="Challenge", pos=None, fonte="mtgo",
                 cards=(("main", "Ill-Gotten Gains", 4),))
           for i in range(4)]
    from mtgvault import caixas as cx
    s = next(x for x in cx.slots(sources.config()) if x["slot"] == "pm-igg")
    antes, nota = loadout._slot_cards(con, s)
    assert not antes, "antes da troca a caixa estava trancada"
    assert "amostra insuficiente" in nota, nota

    r = eventos.escolher(con, "premodern", ids)
    eventos.fixar(cfg, con, "pm-igg", r["escolhida"]["decklist_id"],
                  nome="Ill-Gotten Gains", formato="premodern",
                  consenso_antes=antes, consenso_nota=nota, quando="2026-10-04")
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    s = next(x for x in cx.slots(sources.config()) if x["slot"] == "pm-igg")
    depois, nota2 = loadout._slot_cards(con, s)
    assert sum(q for _b, _n, q in depois) == 4, depois
    assert "amostra insuficiente" not in nota2, nota2
    # E a razão por que estava trancada fica guardada, não se apaga.
    guardado = cfg["listas_escolhidas"]["pm-igg"]["_consenso_anterior"]
    assert guardado["cards"] == [] and "amostra insuficiente" in guardado["nota"]


def caso_a_caixa_sem_assinatura_continua_vazia_e_a_pedi_la():
    """A `legacy-artifacts-blue` é `manual` e **sem carta-assinatura**: ele nunca
    disse qual é. Sem assinatura não há como identificar o arquétipo, e não se
    adivinha a partir do nome."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con, sources.config())
    linha = next(d for f in rep["formatos"] for d in f["decks"]
                 if d["id"] == "caixa:lg-azul")
    assert linha["sem_lista"], linha
    assert not linha["evento"], linha
    assert linha["rotulo_estado"] == "por escolher — ainda sem lista", linha
    assert not linha["quero"], "uma caixa sem lista não se marca"


# ===========================================================================
# 14-16. OS DECKS DELE
# ===========================================================================
def caso_os_decks_dele_entram_mesmo_sem_nome_da_fonte():
    """Três dos dez que ele escolheu — UR Prowess, Goryo's Reanimator e Hammer
    Time — **não têm nome da fonte nenhum** (o `arquetipo_fonte` daquelas listas
    está a NULL, porque vêm do mtgo.com). Pelo meta nunca apareciam: ele agrupa
    pelo nome votado. Por isso são decks DELE, com o nome DELE."""
    cfg = escreve_cfg()
    con = base()
    did = lista(con, fmt="modern", jogador="BressD1", evento="RC Super Qualifier",
                data="2026-10-03", tier="Qualifier", pos=None, fonte="mtgo",
                cards=(("main", "Brainstorm", 4), ("main", "Swords to Plowshares", 2)))
    assert con.execute("SELECT arquetipo_fonte a FROM decklists WHERE id = ?",
                       (did,)).fetchone()["a"] is None
    chave = dv.id_deck("modern", "ur-prowess")
    cfg["decks_de_evento"] = [{"id": chave, "slug": "ur-prowess",
                               "nome": "UR Prowess", "formato": "modern",
                               "arquetipo_id": 7688}]
    eventos.fixar(cfg, con, chave, did, nome="UR Prowess", formato="modern",
                  quando="2026-10-04", caixa=False)
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    rep = dv.relatorio(con, sources.config())
    linha = next(d for f in rep["formatos"] for d in f["decks"] if d["id"] == chave)
    assert linha["nome"] == "UR Prowess", linha
    assert linha["fonte"] == "dele", linha
    assert linha["evento"]["jogador"] == "BressD1", linha["evento"]
    assert linha["total"] == 6, linha


def caso_o_deck_por_confirmar_nao_fica_marcado():
    """*"NAO O REGISTES COMO 'UR Lessons' SEM ELE CONFIRMAR: poe-no a espera."*

    Fica registado e visível, com a carta-chave à vista e a frase a dizer o que
    falta — e **não** marcado como deck a montar.
    """
    cfg = escreve_cfg()
    con = base()
    did = lista(con, fmt="pioneer", jogador="fazparte", evento="Challenge 32",
                data="2026-10-01", tier="Challenge", jogadores=40, pos="5-8",
                fonte="mtgo", cards=(("main", "Brainstorm", 4),))
    chave = dv.id_deck("pioneer", "flow-state")
    cfg["decks_de_evento"] = [{"id": chave, "slug": "flow-state",
                               "nome": "UR Aggro (Flow State)", "formato": "pioneer",
                               "arquetipo_id": 7589, "por_confirmar": True,
                               "carta_chave": "Flow State"}]
    eventos.fixar(cfg, con, chave, did, nome="UR Aggro (Flow State)",
                  formato="pioneer", quando="2026-10-04", caixa=False)
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    rep = dv.relatorio(con, sources.config())
    linha = next(d for f in rep["formatos"] for d in f["decks"] if d["id"] == chave)
    assert linha["por_confirmar"], linha
    assert linha["carta_chave"] == "Flow State", linha
    assert not linha["quero"], "fica à espera do OK dele"
    assert linha["evento"], "mas a lista já está escolhida e dita"


def caso_a_amostra_fina_vai_para_a_pagina():
    """O Hammer Time entra porque ele o pediu — e **não pode aparecer com o mesmo
    peso dos outros nove**, que era mentir-lhe por omissão. Medido: 1 lista em
    toda a colheita, contra 53 do Broodscale."""
    cfg = escreve_cfg()
    con = base()
    did = lista(con, fmt="modern", jogador="DeepDisherino", evento="Challenge 96",
                data="2026-10-02", tier="Challenge", pos=None, fonte="mtgo",
                cards=(("main", "Swords to Plowshares", 4),))
    chave = dv.id_deck("modern", "hammer-time")
    aviso = "AMOSTRA DE UMA LISTA SO. O Colossus Hammer aparece em 3 listas."
    cfg["decks_de_evento"] = [{"id": chave, "slug": "hammer-time",
                               "nome": "Hammer Time", "formato": "modern",
                               "arquetipo_id": 7456, "amostra_fina": aviso}]
    eventos.fixar(cfg, con, chave, did, nome="Hammer Time", formato="modern",
                  quando="2026-10-04", caixa=False)
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    rep = dv.relatorio(con, sources.config())
    linha = next(d for f in rep["formatos"] for d in f["decks"] if d["id"] == chave)
    assert linha["amostra_fina"] == aviso, linha
    d = rep["decks"][chave]
    p = dv.deck_para_pagina(con, d, rep["pos"], "rotativas", {})
    assert p["amostra_fina"] == aviso, p


# ===========================================================================
# O CONFIG A SÉRIO
# ===========================================================================
def _cfg_a_serio():
    return json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))


def caso_as_cinco_caixas_fixas_ficaram_intactas():
    """*"AS QUE FICAM FIXAS, NAO LHES TOQUES"*: a `modern` (a lista de
    qualificação dele), a `duel-commander` (o Liwei Luo, já de evento real), a
    `pauper` e as duas de `cedh` (primers e jogadores vigiados; o cEDH não tem
    eventos na base, por ordem dele de 2026-09-07, logo não há evento real para
    pôr no lugar).

    O que ele mandou não tocar é a **LISTA** e a FONTE de onde ela vem, e é isso
    que se compara com o HEAD do git, byte a byte.

    **[ASSERÇÃO CORRIGIDA a 2026-10-05]** comparava a caixa INTEIRA, chave a
    chave, e por isso chumbava no dia em que uma caixa fixa ganhasse uma marca
    que não mexe na lista — foi o que aconteceu com o `principal` dos decks
    sempre montados (*"esses quero ter sempre montados, mesmo que com
    proxies"*). Marcar uma caixa como principal não é tocar-lhe na lista;
    comparar tudo fazia deste caso uma proibição de qualquer decisão futura
    sobre estas cinco. Tranca-se o que a ordem de 04/10 queria proteger — a
    fonte, a referência, a assinatura e a lista —, e isso continua byte a byte.
    """
    fixas = ("modern", "duel-commander", "pauper", "cedh-blue-farm", "cedh-cloud")
    r = subprocess.run(["git", "-C", str(RAIZ), "show", "HEAD:colecao_config.json"],
                       capture_output=True)
    if r.returncode != 0:                       # sem git, o caso não se aplica
        return
    velho = json.loads(r.stdout.decode("utf-8"))
    novo = _cfg_a_serio()
    cv = {c["slot"]: c for c in velho["caixas"]}
    cn = {c["slot"]: c for c in novo["caixas"]}
    for slot in fixas:
        assert slot in cn, slot
        for campo in ("formato", "fonte", "ref", "assinatura",
                      "assinatura_todas", "assinatura_sem", "balde"):
            assert cv[slot].get(campo) == cn[slot].get(campo), \
                f"a caixa {slot} mudou de {campo} e ele mandou não lhe tocar"
        la = json.dumps(velho.get("listas_escolhidas", {}).get(slot),
                        ensure_ascii=False, sort_keys=True)
        lb = json.dumps(novo.get("listas_escolhidas", {}).get(slot),
                        ensure_ascii=False, sort_keys=True)
        assert la == lb, f"a lista de {slot} mudou e ele mandou não lhe tocar"


def caso_as_caixas_trocadas_tem_todas_proveniencia_completa():
    """As que trocaram de consenso para evento real têm, no config a sério, as
    seis coisas que a página mostra. Um campo em falta é uma ficha incompleta na
    página por onde ele vai sleevar.

    **[ASSERÇÃO CORRIGIDA a 2026-10-05]** eram SETE e são SEIS: o
    `premodern-stiflenought` saiu, porque ele disse *"no Premodern, o
    Stiflenought e lista do Luffy tambem"* e a caixa voltou a `fonte: vigiado`.
    A escolha de 04/10 (a lista do Simone Fierro, 1.º do European Championship)
    foi um erro meu — a regra `listas_de_evento.regra` manda preferir
    presenciais com campo grande, e o Stiflenought dele vem do jogador que ele
    SEGUE. A lista do Fierro não se apagou (fica em
    `listas_escolhidas._premodern-stiflenought-anterior`) e o caso novo está no
    `test_sempre_montado.caso_o_stiflenought_serve_a_lista_do_luffy_e_segue_o_jogador`.
    """
    novo = _cfg_a_serio()
    trocadas = ("premodern-replenish", "premodern-enchantress",
                "premodern-elves", "premodern-oath", "premodern-igg", "pioneer")
    for slot in trocadas:
        rec = (novo.get("listas_escolhidas") or {}).get(slot)
        assert rec, f"{slot} ficou sem lista"
        assert rec.get("cards"), f"{slot} ficou sem cartas"
        e = rec.get("evento")
        assert e, f"{slot} ficou sem proveniência"
        for campo in ("jogador", "evento", "data", "url", "decklist_id"):
            assert e.get(campo), f"{slot}: falta o campo {campo}"
        # A caixa tem de estar a ler de lá.
        caixa = next(c for c in novo["caixas"] if c["slot"] == slot)
        assert caixa.get("fonte") == "escolhido" and caixa.get("ref") == slot, caixa
        # E o que a caixa tinha antes fica guardado — nada se apaga.
        assert "_consenso_anterior" in rec, f"{slot}: perdeu-se o consenso antigo"
        assert "_antes" in caixa, f"{slot}: perdeu-se a fonte antiga"
    # O STIFLENOUGHT SAIU DESTE CONJUNTO (2026-10-05) e tem de ter saído MESMO:
    # sem esta asserção, a correcção do caso acima deixava de trancar nada e um
    # dia qualquer a caixa voltava ao Fierro sem ninguém dar por isso.
    stf = next(c for c in novo["caixas"] if c["slot"] == "premodern-stiflenought")
    assert stf.get("fonte") == "vigiado", stf
    assert stf.get("ref") == "Luffy — Premodern", stf
    assert "premodern-stiflenought" not in (novo.get("listas_escolhidas") or {})


def caso_a_regra_de_escolha_esta_escrita_no_config():
    """*"escreve-a no config para nao ser tua opiniao de hoje"*: os critérios,
    pela ordem, cada um com a razão em português."""
    novo = _cfg_a_serio()
    bloco = novo.get("listas_de_evento")
    assert bloco, "a regra tem de estar no config"
    criterios = [c[0] for c in bloco["regra"]]
    assert criterios == [c for c, _r in eventos.REGRA_OMISSAO], criterios
    for _c, razao in bloco["regra"]:
        assert len(razao) > 10, razao
    assert bloco.get("decidido_em") == "2026-10-04", bloco
    assert "ninguem jogou" in bloco.get("razao", ""), bloco


CASOS = [
    caso_a_regra_prefere_presencial_a_online,
    caso_entre_presenciais_ganha_o_campo_maior,
    caso_entre_online_ganha_o_evento_mais_importante,
    caso_a_lista_repetida_ganha_a_um_resultado_unico_melhor,
    caso_uma_challenge_sem_classificacao_nao_conta_como_ter_ganhado,
    caso_a_janela_filtra_primeiro_e_a_alternativa_fica_ao_lado,
    caso_o_premodern_esta_excepcionado_da_janela,
    caso_a_proveniencia_grava_se_e_sobrevive_a_poda,
    caso_a_caixa_trocada_mostra_as_seis_coisas,
    caso_o_consenso_anterior_fica_guardado_e_nao_se_pisa,
    caso_nenhum_deck_mostra_consenso_como_se_fosse_a_lista,
    caso_um_deck_sem_amostra_destranca_com_uma_lista_real,
    caso_a_caixa_sem_assinatura_continua_vazia_e_a_pedi_la,
    caso_os_decks_dele_entram_mesmo_sem_nome_da_fonte,
    caso_o_deck_por_confirmar_nao_fica_marcado,
    caso_a_amostra_fina_vai_para_a_pagina,
    caso_as_cinco_caixas_fixas_ficaram_intactas,
    caso_as_caixas_trocadas_tem_todas_proveniencia_completa,
    caso_a_regra_de_escolha_esta_escrita_no_config,
]


def run():
    maus = 0
    for f in CASOS:
        try:
            f()
            print("  ok   ", f.__name__)
        except AssertionError as e:
            maus += 1
            print("  FALHA", f.__name__, "->", e)
        except Exception as e:                      # noqa: BLE001
            maus += 1
            print("  ERRO ", f.__name__, "->", type(e).__name__, e)
    print(f"\n{len(CASOS) - maus}/{len(CASOS)} casos ok")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                           # noqa: BLE001, S110
            pass
    sys.exit(1 if maus else 0)


if __name__ == "__main__":
    run()
