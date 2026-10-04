"""AS DECKLISTS QUE ELE VAI VER NO SITE (André, 2026-10-04, ao fim do dia).

As palavras dele: *"Quero que atualizes as decklists no site, para eu aceder e
comecar a sleevar as coisas"*; *"falta escolher decks, falta depois eu organizar
os decks, guardar as que sao staples"*; *"vi que nao leste o RC Qualifier nas
decklists"*.

Uma lista errada custa-lhe uma tarde de sleeves, e é isso que cada caso aqui
tranca. Chumbam todos se a funcionalidade for retirada — a prova está em
`tests/_chumba_decklists.py`, que desliga uma peça de cada vez e exige vermelho:

  1. um torneio de 1 000+ jogadores traz MAIS listas do que uma Challenge 64 —
     e o tecto decide-se pelos JOGADORES, não pelo nome;
  2. a escala é só para o PAPEL: uma «MTGO Challenge 64» não passa a pedir 64;
  3. a revisita FORÇADA de um evento já processado funciona, e um evento cuja
     página já não existe NÃO se marca nem entope a fila;
  4. o NOME de uma caixa corresponde à lista que ela tem dentro;
  5. uma caixa DESACTIVADA não aparece como um deck de 0 % ao lado dos outros;
  6. cada caixa diz a LISTA, a FONTE e a DATA — as de consenso a janela, as
     vigiadas quando a vigia leu;
  7. um consenso abaixo do mínimo de listas DI-LO em vez de inventar;
  8. marcar um deck recalcula próprias, partilhadas e as staples do formato.

Sem rede: os pedidos ao mtgtop8 são substituídos por um `_get` de mentira que
conta as chamadas. Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver
`tests/_bateria.py`).
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

CAIXAS = [
    # Uma caixa com lista ESCOLHIDA (é a `modern` dele): o nome tem de dizer o
    # que a lista tem dentro.
    {"slot": "modern", "nome": "Modern — Pinnacle Affinity", "formato": "modern",
     "fonte": "escolhido", "ref": "modern", "balde": "Colecção",
     "estado": "permanente", "prioridade": 1},
    # DESACTIVADA: `fonte: consenso` sem `assinatura` — o gesto do «já não vou
    # montar este», com o que ela tinha em `_antes`.
    {"slot": "modern-affinity", "nome": "Modern — Affinity", "formato": "modern",
     "fonte": "consenso", "balde": "Colecção", "estado": "candidata",
     "prioridade": 2,
     "_antes": {"fonte": "consenso", "assinatura": ["Weapons Manufacturing"]}},
    # Consenso COM assinatura, mas com poucas listas: tem de dizer que não chega.
    {"slot": "pm-igg", "nome": "Ill-Gotten Gains", "formato": "premodern",
     "fonte": "consenso", "assinatura": ["Ill-Gotten Gains"],
     "balde": "Colecção", "estado": "permanente", "prioridade": 3},
    # Consenso com listas que chegam.
    {"slot": "pm-oath", "nome": "Oath of Druids", "formato": "premodern",
     "fonte": "consenso", "assinatura": ["Oath of Druids"],
     "balde": "Colecção", "estado": "permanente", "prioridade": 4},
    {"slot": "pm-elves", "nome": "Elves", "formato": "premodern",
     "fonte": "consenso", "assinatura": ["Wirewood Symbiote"],
     "balde": "Colecção", "estado": "permanente", "prioridade": 5},
    # Vigiada: tem de dizer a data da lista E a da leitura.
    {"slot": "cedh-bf", "nome": "Blue Farm", "formato": "cedh",
     "fonte": "vigiado", "ref": "Blue Farm [Primer]", "balde": "Colecção",
     "estado": "montada", "prioridade": 6},
    # Por escolher: nunca teve lista e não tem fonte.
    {"slot": "legacy-ab", "nome": "Artifacts Blue", "formato": "legacy",
     "fonte": "manual", "balde": "Colecção", "estado": "permanente",
     "prioridade": 7},
]
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
        {"grupo": "modern", "formatos": ["modern"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
        {"grupo": "cedh", "formatos": ["cedh"], "dedicado": True,
         "cartas_partilhadas": "dedicadas"},
        {"grupo": "legacy", "formatos": ["legacy"], "dedicado": True,
         "cartas_partilhadas": "rotativas"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 30},
    "decks_montar": {},
    "stock": {"min_lists": 5},
    # Sem janela do consenso nestes testes: o que aqui se mede é a NOTA, e uma
    # janela a cortar as listas semeadas mudava a amostra de caso para caso.
    "consenso": {"desde": None},
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Presencial", "Qualifier"],
                     "min_jogadores_presencial": 0, "ligas": True},
    },
    "mtgtop8": {"paginas_indice": 1, "revisitas_por_corrida": 1,
                "grandes": {"padroes": ["championship"], "listas_por_evento": 64,
                            "min_jogadores": 64,
                            "escala_jogadores": {"128": 64, "64": 32}}},
    "listas_escolhidas": {
        "modern": {
            "nome": "Modern — Pinnacle Affinity",
            "arquetipo": "Pinnacle Affinity",
            "padrao": True,
            "escolhido_em": "2026-10-04",
            "origem": "lista de qualificacao, dada pelo Andre a 04/10/2026",
            "cards": [["main", "Kappa Cannoneer", 4],
                      ["main", "Weapons Manufacturing", 4],
                      ["main", "Mox Diamond", 1]],
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

from mtgvault import db, decks_vista as dv, mtgtop8, sources  # noqa: E402

_ABERTAS = []

CATALOGO = [
    ("Kappa Cannoneer", "nec", "2022-04-29", 20.0, "Artifact Creature — Turtle"),
    ("Weapons Manufacturing", "fra", "2026-10-02", 2.0, "Enchantment"),
    ("Mox Diamond", "sth", "1998-03-02", 500.0, "Artifact"),
    ("Oath of Druids", "exo", "1998-06-15", 40.0, "Enchantment"),
    ("Wirewood Symbiote", "lgn", "2003-02-03", 8.0, "Creature — Insect"),
    ("Ill-Gotten Gains", "usg", "1998-10-12", 30.0, "Sorcery"),
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.5, "Instant"),
    ("Brainstorm", "ice", "1995-06-01", 0.5, "Instant"),
    ("Forest", "4ed", "1995-04-01", 0.1, "Basic Land — Forest"),
    ("Birds of Paradise", "4ed", "1995-04-01", 9.0, "Creature — Bird"),
]


def base():
    """Base nova com o catálogo mínimo."""
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
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-04', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def semeia_listas(con, fmt, n, cartas, *, prefixo="L", event="Torneio",
                  data="2026-09-20", players=100, tier="Presencial"):
    """`n` decklists iguais naquele formato, para o consenso ter amostra."""
    from mtgvault import sources as _s                       # noqa: PLC0415
    for i in range(n):
        _s.store_decklist(con, source="manual", source_key=f"{prefixo}-{i}",
                          fmt=fmt, cards=[("main", nm, q) for nm, q in cartas],
                          event_name=event, event_date=data,
                          player=f"j{i}", placement="1", event_players=players,
                          arquetipo=None, arquetipo_de=None)
    con.commit()


def listas_de_evento(con, eid, fmt, code, nome, data, players, n=2):
    """`n` listas de mtgtop8 daquele evento, com o `url` que a semente lê."""
    from mtgvault import sources as _s                       # noqa: PLC0415
    for i in range(n):
        _s.store_decklist(
            con, source="mtgtop8", source_key=f"{eid}-{i}", fmt=fmt,
            cards=[("main", "Kappa Cannoneer", 4), ("main", "Mox Diamond", i + 1)],
            event_name=nome, event_date=data, player=f"p{i}", placement="1",
            event_players=players,
            url=f"https://mtgtop8.com/event?e={eid}&d={900 + i}&f={code}")
    con.commit()


def semeia_memoria_de(con, *eventos):
    """Põe os eventos na memória como a SEMENTE os põe: `tecto` antigo,
    `na_pagina` a NULL e `completo = 0`.

    Faz-se pelo `mtgtop8.semear_memoria` a sério, a partir das listas que cada
    evento deixou na base, e não com um INSERT à mão: é esse o caminho que corre
    na primeira noite, e um INSERT por fora podia passar com a semente avariada.
    A semente corre **uma vez só** (`MARCA_SEMEADO`), por isso as listas de TODOS
    os eventos têm de estar na base antes de ela ser chamada.
    """
    for e in eventos:
        listas_de_evento(con, *e)
    return mtgtop8.semear_memoria(con)


def fmt_de(rep, nome):
    return next(f for f in rep["formatos"] if f["formato"] == nome)


def linha(f, nome):
    return next(d for d in f["decks"] if d["nome"] == nome)


# ===========================================================================
# 1. O TECTO DECIDE-SE PELOS JOGADORES, E UM RC TRAZ MAIS QUE UMA CHALLENGE 64
# ===========================================================================
def caso_um_torneio_de_mil_jogadores_traz_mais_listas_que_uma_challenge():
    """O defeito de 04/10: o `Modern event - Regional Championship` de 1 486
    jogadores tinha 16 listas na base e uma Challenge 64 traz 32 — o maior torneio
    de papel de Modern contribuía metade de uma Challenge. Medido no site: a
    página dele serve 64 links de deck."""
    escreve_cfg()
    # O RC (presencial, 1 486 jogadores) contra uma Challenge 64 do MTGO.
    rc = mtgtop8.tecto_do_evento(True, 1486, 16, nome="Modern event - Regional Championship")
    ch = mtgtop8.tecto_do_evento(False, 64, 16, nome="Modern event - MTGO Challenge 64")
    assert rc == 64, rc
    assert rc > 32, (rc, "um RC de 1 486 jogadores tem de trazer mais do que "
                         "as 32 de uma Challenge")
    # E um nome que NENHUM padrão reconhece, com o campo grande, também sobe: é o
    # «Buckeye Brawl II - Retromancers» (125 jogadores, 32 listas na página), o
    # evento que só esta regra apanha.
    assert not mtgtop8.e_grande("Premodern event - Buckeye Brawl II - Retromancers")
    assert mtgtop8.tecto_do_evento(
        False, 125, 16, nome="Premodern event - Buckeye Brawl II") == 32
    # Abaixo de 64 jogadores nada muda — é o tecto de sempre.
    assert mtgtop8.tecto_do_evento(False, 32, 16, nome="Premodern event - Loja") == 16
    # E a escala NUNCA baixa o que o nome já dava: o «RC Hangzhou Side Event» tem
    # 70 jogadores e nome reconhecido, e continua em 64 (pela escala eram 32).
    assert mtgtop8.tecto_do_evento(
        True, 70, 16, nome="Legacy event - RC Championship Hangzhou") == 64
    print("o tecto sobe com o tamanho do campo, e nunca baixa o que o nome dava")


# ===========================================================================
# 2. A ESCALA É SÓ PARA O PAPEL
# ===========================================================================
def caso_a_escala_nao_se_aplica_a_uma_challenge_de_mtgo():
    """Sem isto, a fila de revisitas dava 54 eventos e 28 eram Challenges de MTGO
    de Modern — cujas listas o vault já tem pela fonte directa (mtgo.com) e que a
    deduplicação descarta. Eram ~28 noites de pedidos a produzir zero listas."""
    escreve_cfg()
    assert mtgtop8.escala_do_tecto(128, "Modern event - MTGO Challenge 64") == 0
    assert mtgtop8.escala_do_tecto(128, "Premodern event - Bogardan War II") == 64
    # O tecto de uma Challenge de MTGO com 128 jogadores fica nos 16 de sempre.
    assert mtgtop8.tecto_do_evento(
        False, 128, 16, nome="Modern event - MTGO Challenge 64") == 16
    print("a escala é só para o papel: uma Challenge de MTGO não sobe de tecto")


# ===========================================================================
# 3. A REVISITA FORÇADA, E A PÁGINA QUE JÁ NÃO EXISTE
# ===========================================================================
PAGINA_RC = """<html><title>Modern event - Regional Championship @ Lisboa</title>
 <body>1486 players - 12/09/26
 <a href=event?e=90762&d=1001&f=MO>Pinnacle Affinity</a>
 <a href=search?player=Ana>Ana</a>
 <a href=event?e=90762&d=1002&f=MO>Esper Blink</a>
 <a href=search?player=Bruno>Bruno</a>
 <a href=event?e=90762&d=1003&f=MO>Ruby Storm</a>
 <a href=search?player=Carla>Carla</a>
 </body></html>"""
# O que o mtgtop8 responde (200!) a um evento que já não tem. Trecho real do
# evento 90532 a 2026-10-04: 12 KB, título genérico, zero datas, e `d=0` nos
# links do menu.
PAGINA_MORTA = """<html><title>MTG Decks Database</title><body>
 <a class=menu_item href=/format?f=PEA>PEASANT</a>
 <a href=event?e=0&d=0&f=PREM>&rarr;</a></body></html>"""
DEC = "4 [MRD] Kappa Cannoneer\n4 [FRA] Weapons Manufacturing\n"


def _finge_rede(paginas, contador):
    """Substitui o `_get` do mtgtop8 por um que serve `paginas` e CONTA."""
    def _get(path, **params):
        contador.append((path, params))
        if path == "/dec":
            return DEC
        chave = (path, params.get("e"))
        if chave in paginas:
            return paginas[chave]
        raise AssertionError(f"pedido inesperado: {path} {params}")
    return _get


def caso_a_revisita_forcada_de_um_evento_ja_processado_funciona():
    """O `harvest` revisita 1 por formato e por corrida, o que é lento demais
    quando se acabou de mudar a regra do tecto — a 04/10 eram 9 eventos truncados
    e o RC demorava uma noite a entrar. A revisita forçada é o *"usa-a nestes"*."""
    escreve_cfg()
    con = base()
    # O evento já está na memória com o tecto ANTIGO, posto pela semente.
    assert semeia_memoria_de(
        con, (90762, "modern", "MO", "Modern event - Regional Championship",
              "2026-09-12", 1486)) == 1
    linha_mem = dict(con.execute(
        "SELECT * FROM mtgtop8_eventos WHERE event_id = 90762").fetchone())
    assert linha_mem["tecto"] == mtgtop8.TECTO_ANTIGO, linha_mem
    assert not linha_mem["completo"], linha_mem
    assert mtgtop8.por_fazer(linha_mem, True, 16), \
        "com o tecto de hoje maior, há que voltar lá"

    pedidos = []
    antigo = mtgtop8._get
    mtgtop8._get = _finge_rede({("/event", 90762): PAGINA_RC}, pedidos)
    try:
        res = mtgtop8.revisitar(con, "modern", [90762])
    finally:
        mtgtop8._get = antigo
    assert len(res) == 1, res
    r = res[0]
    assert r["marcou"] is True, r
    assert r["antes"] == 2, r                      # as 2 que a semente conhecia
    assert r["novas"] == 3, r                      # as 3 listas da página
    assert r["tecto_antes"] == 16 and r["tecto"] == 64, r
    assert r["completo"] is True, r
    # E não se volta lá: a fila esvaziou-se.
    assert mtgtop8.revisitas_pendentes(con, "modern", 16) == []
    print("a revisita forçada traz as listas que faltavam e fecha o evento")


def caso_uma_pagina_que_ja_nao_e_do_evento_nao_se_marca_nem_entope_a_fila():
    """Dois defeitos num: (a) o mtgtop8 responde 200 com a página genérica a um
    evento que já não tem, e lá dentro há `d=0` — sem o crivo, revisitar o 90532
    pedia o `.dec` do deck 0 e dava por COMPLETO um evento de 218 jogadores;
    (b) esse evento não se marca (de propósito) e, sendo o 1.º da fila pelo nº de
    jogadores, ficava à cabeça dela TODAS as noites — os outros nunca chegavam."""
    escreve_cfg()
    con = base()
    assert mtgtop8.parse_deck_ids(PAGINA_MORTA) == [], "d=0 não é um deck"
    assert not mtgtop8.e_pagina_de_evento(
        mtgtop8.parse_event_meta(PAGINA_MORTA), [])
    # O morto (218 jogadores, à cabeça da fila) e um que dá listas (139).
    assert semeia_memoria_de(
        con,
        (90532, "premodern", "PREM",
         "Premodern event - European Championship 2026", "2026-09-05", 218),
        (91399, "premodern", "PREM",
         "Premodern event - Bogardan War II", "2026-09-27", 139)) == 2
    fila = mtgtop8.revisitas_pendentes(con, "premodern", 16)
    assert [r["event_id"] for r in fila] == [90532, 91399], fila

    pedidos = []
    antigo = mtgtop8._get
    mtgtop8._get = _finge_rede({("/event", 90532): PAGINA_MORTA,
                                ("/event", 91399): PAGINA_RC}, pedidos)
    try:
        # O `harvest` com um índice vazio: só as revisitas correm.
        mtgtop8._get = _finge_rede(
            {("/event", 90532): PAGINA_MORTA, ("/event", 91399): PAGINA_RC,
             ("/format", None): "<html></html>"}, pedidos)
        mtgtop8.harvest(con, "premodern", max_events=0)
    finally:
        mtgtop8._get = antigo
    # O morto continua por fazer; o outro FOI feito na mesma noite — é a prova de
    # que a vez não se gasta numa página que não existe.
    por_fazer = {r["event_id"] for r in
                 mtgtop8.revisitas_pendentes(con, "premodern", 16)}
    assert 90532 in por_fazer, "o evento morto não se marca"
    assert 91399 not in por_fazer, ("a fila não pode entupir na cabeça: o "
                                    "segundo tem de ser visto na mesma noite")
    print("a página morta não se marca, não cria listas e não entope a fila")


# ===========================================================================
# 4. O NOME DA CAIXA CORRESPONDE À LISTA QUE ELA TEM DENTRO
# ===========================================================================
def caso_o_nome_da_caixa_modern_corresponde_a_lista_que_tem_dentro():
    """A caixa chamava-se «Modern — UW Oswald» e a lista lá dentro é a de
    qualificação dele, que é Izzet Affinity: 4 Kappa Cannoneer, 4 Weapons
    Manufacturing, zero cartas brancas e zero Oswald Fiddlebender. O nome dizia um
    deck e o conteúdo era outro — e é a partir disto que ele vai sleevar."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con)
    d = linha(fmt_de(rep, "modern"), "Modern — Pinnacle Affinity")
    cards = {nm for _b, nm, _q in rep["decks"][d["id"]]["cards"]}
    assert "Kappa Cannoneer" in cards and "Weapons Manufacturing" in cards, cards
    assert "Oswald" not in d["nome"], d["nome"]
    # O nome da caixa tem de bater com o que a lista é. A prova que não depende
    # de uma string escrita neste teste: nenhuma carta da lista é do deck que o
    # nome antigo nomeava, e o nome actual é o que a FONTE dá ao arquétipo.
    assert "Affinity" in d["nome"], d["nome"]
    # E o meta com o MESMO nome não se oferece como se fosse outro deck.
    semeia_listas(con, "modern", 6,
                  [("Kappa Cannoneer", 4), ("Weapons Manufacturing", 4)],
                  event="Modern event - Challenge")
    con.execute("UPDATE decklists SET arquetipo_fonte = 'Pinnacle Affinity', "
                "arquetipo_fonte_de = 'evento' WHERE format = 'modern'")
    con.commit()
    rep = dv.relatorio(con)
    f = fmt_de(rep, "modern")
    metas = [d for d in f["decks"] if d["fonte"] == "meta"]
    assert metas, "a semente devia dar um arquétipo meta"
    assert all(m["ja_e_caixa"] for m in metas if m["nome"] == "Pinnacle Affinity"), \
        "o meta com o nome do arquétipo da caixa tem de dizer «já é uma caixa tua»"
    print("o nome da caixa diz a lista que ela tem dentro, e o meta não duplica")


# ===========================================================================
# 5. UMA CAIXA DESACTIVADA NÃO É UM DECK DE 0 %
# ===========================================================================
def caso_uma_caixa_desactivada_nao_aparece_como_deck_de_zero_por_cento():
    """Ele mandou desactivar a `modern-affinity` a 04/10 e ela continuava na lista
    de Modern com 0 %, ao lado dos decks que vai montar, com o estado `candidata`
    — que é um estado normal da escala e não quer dizer «desactivada»."""
    escreve_cfg()
    con = base()
    rep = dv.relatorio(con)
    f = fmt_de(rep, "modern")
    d = linha(f, "Modern — Affinity")
    assert d["desactivada"] is True, d
    assert d["rotulo_estado"], "tem de dizer POR ESCRITO que está desactivada"
    assert "desactivada" in d["rotulo_estado"].lower(), d["rotulo_estado"]
    # Não conta como deck do formato...
    assert f["n_desactivadas"] == 1, f["n_desactivadas"]
    assert f["n_decks"] == len(f["decks"]) - 1, (f["n_decks"], len(f["decks"]))
    # ... e vai para o FIM da lista, depois dos que têm lista.
    assert f["decks"][-1]["nome"] == "Modern — Affinity", \
        [x["nome"] for x in f["decks"]]
    # E NÃO se esconde: ele tem o `_antes` no config para a repor.
    assert any(x["nome"] == "Modern — Affinity" for x in f["decks"])
    # A que está «por escolher» é outra coisa, e diz outra coisa.
    ab = linha(fmt_de(rep, "legacy"), "Artifacts Blue")
    assert ab["desactivada"] is False, ab
    assert "escolher" in (ab["rotulo_estado"] or ""), ab["rotulo_estado"]
    print("a desactivada fica marcada e no fim; a «por escolher» diz outra coisa")


# ===========================================================================
# 6. CADA CAIXA DIZ A LISTA, A FONTE E A DATA
# ===========================================================================
def caso_cada_caixa_diz_a_lista_a_fonte_e_a_data():
    """Ele vai sleevar a partir disto: para cada caixa o site tem de dizer que
    lista é, de onde veio e de que dia, sem ele ter de perguntar."""
    import datetime as _dt
    escreve_cfg()
    con = base()
    # Consenso com amostra que chega.
    semeia_listas(con, "premodern", 6, [("Oath of Druids", 4),
                                        ("Swords to Plowshares", 4),
                                        ("Brainstorm", 4)],
                  prefixo="OA", data="2026-09-20")
    semeia_listas(con, "premodern", 6, [("Wirewood Symbiote", 4),
                                        ("Swords to Plowshares", 4),
                                        ("Forest", 6)],
                  prefixo="EL", data="2026-09-22")
    # Uma lista vigiada: snapshot de um dia, LEITURA noutro.
    con.execute("INSERT INTO watched (kind, key, label, format, active, "
                "last_checked, notes) VALUES ('moxfield', 'abc', "
                "'Blue Farm [Primer]', 'cedh', 1, '2026-10-04', "
                "'Blue Farm · https://moxfield.com/decks/abc')")
    wid = con.execute("SELECT id FROM watched WHERE label = 'Blue Farm [Primer]'"
                      ).fetchone()["id"]
    con.execute("INSERT INTO watched_snapshots (watched_id, taken_at, cards, "
                "list_hash) VALUES (?, '2026-09-04', ?, 'h')",
                (wid, json.dumps([["main", "Mox Diamond", 1]])))
    con.commit()

    rep = dv.relatorio(con)
    for fmt, nome in (("premodern", "Oath of Druids"), ("premodern", "Elves"),
                      ("cedh", "Blue Farm"), ("modern", "Modern — Pinnacle Affinity")):
        d = linha(fmt_de(rep, fmt), nome)
        assert d["nota"], f"{nome} sem nota nenhuma"
        # UMA DATA, em qualquer caixa com lista: `AAAA-MM-DD` na nota.
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", d["nota"]), (nome, d["nota"])
        assert d["origem"], f"{nome} sem fonte"
    # O consenso diz de QUE JANELA sai.
    oath = linha(fmt_de(rep, "premodern"), "Oath of Druids")
    assert "consenso de 6 listas" in oath["nota"], oath["nota"]
    assert "2026-09-20" in oath["nota"], oath["nota"]
    # A vigiada diz as DUAS datas: a da lista e a da leitura. Dizer só a do
    # snapshot fazia uma lista conferida hoje parecer de há um mês.
    bf = linha(fmt_de(rep, "cedh"), "Blue Farm")
    assert "2026-09-04" in bf["nota"] and "2026-10-04" in bf["nota"], bf["nota"]
    assert bf["link"].startswith("https://moxfield.com/"), bf["link"]
    print("cada caixa diz a lista, a fonte e a data — e a vigiada diz as duas datas")


# ===========================================================================
# 7. UM CONSENSO ABAIXO DO MÍNIMO DI-LO
# ===========================================================================
def caso_um_consenso_abaixo_do_minimo_diz_se_na_pagina():
    """A `premodern-igg` tinha poucas listas. Mostrar um consenso de 3 ou 4 listas
    como se fosse igual aos outros era inventar — e ele ia sleevar a partir
    disso."""
    escreve_cfg()
    con = base()
    semeia_listas(con, "premodern", 3, [("Ill-Gotten Gains", 4),
                                        ("Brainstorm", 4)], prefixo="IGG")
    con.commit()
    rep = dv.relatorio(con)
    d = linha(fmt_de(rep, "premodern"), "Ill-Gotten Gains")
    assert d["sem_lista"] is True, d
    assert d["desactivada"] is False, "não está desactivada: é falta de amostra"
    assert "insuficiente" in d["nota"].lower(), d["nota"]
    assert "3 listas" in d["nota"], d["nota"]
    assert "5" in d["nota"], ("tem de dizer qual é o mínimo", d["nota"])
    print("um consenso sem amostra di-lo, com o número de listas e o mínimo")


# ===========================================================================
# 8. MARCAR UM DECK RECALCULA PRÓPRIAS, PARTILHADAS E AS STAPLES
# ===========================================================================
def caso_marcar_um_deck_recalcula_proprias_partilhadas_e_staples():
    """A parte dele: *"falta escolher decks, falta depois eu organizar os decks,
    guardar as que sao staples"*. Se houver um caminho em que marcar não
    recalcula, é a avaria mais grave que esta ordem pode deixar passar."""
    escreve_cfg()
    con = base()
    semeia_listas(con, "premodern", 6, [("Oath of Druids", 4),
                                        ("Swords to Plowshares", 4)],
                  prefixo="OA")
    semeia_listas(con, "premodern", 6, [("Wirewood Symbiote", 4),
                                        ("Swords to Plowshares", 4),
                                        ("Forest", 6)], prefixo="EL")
    con.commit()

    rep = dv.relatorio(con)
    f = fmt_de(rep, "premodern")
    assert f["n_marcados"] == 0
    assert f["necessidade"]["soma"] == 0, f["necessidade"]
    assert f["staples"] == [], f["staples"]

    # Marca OS DOIS decks que partilham as Swords.
    ids = [dv.id_da_caixa("pm-oath"), dv.id_da_caixa("pm-elves")]
    escreve_cfg(decks_montar={i: "2026-10-04" for i in ids})
    rep = dv.relatorio(con)
    f = fmt_de(rep, "premodern")
    assert f["n_marcados"] == 2, f["n_marcados"]
    assert f["necessidade"]["soma"] > 0, f["necessidade"]
    # A regra do formato é ROTATIVAS: o máximo é menor do que a soma, porque as
    # Swords contam uma vez.
    assert f["necessidade"]["maximo"] < f["necessidade"]["soma"], f["necessidade"]
    # AS STAPLES: as Swords entram nos dois.
    nomes = {s["nm"]: s for s in f["staples"]}
    assert "Swords to Plowshares" in nomes, nomes
    assert nomes["Swords to Plowshares"]["n_decks"] == 2, nomes
    assert nomes["Swords to Plowshares"]["precisa"] == 4, nomes
    assert "Oath of Druids" not in nomes, "própria de um deck só, não é staple"
    assert f["sleeves"]["decks"] == 2 and f["sleeves"]["proxies"] > 0, f["sleeves"]

    # E por deck: as partilhadas de cada um SÃO os proxies dele.
    decks = dv.registo(con)["premodern"]
    mks = dv.marcados(sources.config())
    esc = [d for d in decks if d["id"] in mks]
    r = dv.reparticao(esc)
    for d in esc:
        p = dv.proprias_e_partilhadas(d, r)
        assert sorted({nm for _b, nm, _q in p["partilhadas"]}) == \
            sorted(x["nm"] for x in dv.proxies_do_deck(d, r)), d["nome"]
        assert "Swords to Plowshares" in {nm for _b, nm, _q in p["partilhadas"]}

    # DESMARCAR um volta atrás: a carta deixa de ser partilhada.
    escreve_cfg(decks_montar={ids[0]: "2026-10-04"})
    f = fmt_de(dv.relatorio(con), "premodern")
    assert f["n_marcados"] == 1
    assert f["staples"] == [], f["staples"]
    print("marcar recalcula a necessidade, as partilhadas e as staples; desmarcar volta")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]


def run():
    for f in CASOS:
        f()
    print(f"\nTUDO OK ({len(CASOS)} casos)")


if __name__ == "__main__":
    try:
        run()
    finally:
        for cm in _ABERTAS:
            try:
                cm.__exit__(None, None, None)
            except sqlite3.Error:
                pass
