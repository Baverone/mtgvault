"""A JANELA DO CONSENSO (André, 2026-10-03).

À letra: *"faz a pesquisa de decks só a partir do dia que reality fracture ficou
disponível"* — e a data é **2026-09-29**, o dia em que o set entrou na loja do
Magic Online (em papel só saiu a 02/10, mas o metagame que o vault recolhe é
quase todo de MTGO).

O que aqui se tranca — e cada caso tem de CHUMBAR se a funcionalidade for
desligada (ver `tests/_chumba_janela.py`):

  1. **o consenso não volta a contar listas anteriores ao corte.** É o caso
     central: o `counting_sql` e o `lista_conta` levam o corte, e por isso o
     clustering, o consenso por comandante, a lista de uma caixa de
     `fonte: consenso`, a cobertura e o showcase ficam todos com a mesma janela;
  2. **a RESERVA da venda continua na janela DELA** (`reserva.janela_dias`, 30
     dias). São duas perguntas — *"como é que este deck se joga agora"* e *"que
     carta é que eu joguei no último mês e por isso não devo vender"* — e
     encurtar a segunda a cinco dias desprotegia carta que ele usou há duas
     semanas. Medido a 03/10: punha **+426 cópias / +11 796,69 €** na lista
     VENDER;
  3. **abaixo do mínimo de listas diz «amostra insuficiente» e NÃO dá
     percentagens.** Ordem dele: *"com 2 listas uma carta aparece a 50 % ou a
     100 % sem isso querer dizer nada. Prefiro «não dá para dizer» a um número
     bonito e falso"*;
  4. a pergunta *"a partir de quando conta"* vive **num sítio só** — há uma
     varredura do código à procura de quem leia `consenso.desde` à mão;
  5. as **excepções por formato** funcionam (hoje o `premodern`: o Reality
     Fracture não é legal lá — o formato acaba no Scourge, 2003 — e das 978
     listas de premodern da base **zero** jogam uma carta do set);
  6. **sem a chave no config nada muda**: apagar o `consenso.desde` devolve o
     vault exactamente ao que era. É o padrão do `venda.mostrar`;
  7. **seguir UMA lista não é consenso**: o `my_decks` fica fora do corte, de
     propósito e por escrito;
  8. a janela **viaja para a página** e aparece no rodapé — uma janela que a
     página não diz é uma página a mentir em silêncio.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RAIZ = Path(__file__).resolve().parents[1]
_TMP = Path(tempfile.mkdtemp())

CORTE = "2026-09-29"
ANTES = "2026-09-20"       # antes do corte
DEPOIS = "2026-09-30"      # depois do corte
CMD = "Cloud, Midgar Mercenary"

CFG = {
    "caixas": [], "regras_por_formato": [], "decks_vigiados": [],
    "premodern_arquetipos_alvo": [], "regras_colecao": {}, "spml_formatos": {},
    "consenso": {"desde": CORTE, "excepcoes": ["premodern"],
                 "motivo": "o Reality Fracture entrou no MTGO a 29/09/2026",
                 "fonte": "https://www.mtgo.com/news/mtgo092226"},
    "consenso_comandante": {"formato": "duel-commander", "comandante": CMD,
                            "min_listas": 8, "nucleo_pct": 90, "flex_pct": 40,
                            "max_comandantes": 40},
    "reserva": {"janela_dias": 30, "staples_premodern_pct": 10},
    # Modern/Premodern: a regra de sempre. Duel Commander: ligas e presenciais
    # de qualquer dimensão, como no config dele.
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                     "min_jogadores_presencial": 0, "ligas": False},
        "duel-commander": {"tiers": ["Challenge", "Presencial"],
                           "min_jogadores_presencial": 0, "ligas": True}},
}


def _config(extra=None, sem=()):
    """Escreve um config novo e limpa a cache do `sources` (lido por mtime)."""
    cfg = json.loads(json.dumps(CFG))
    for k, v in (extra or {}).items():
        cfg[k] = v
    for k in sem:
        cfg.pop(k, None)
    p = _TMP / f"cfg-{len(list(_TMP.glob('cfg-*.json')))}.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    os.environ["MTGVAULT_CONFIG"] = str(p)
    from mtgvault import sources
    sources._CFG_CACHE.clear()
    return p


_config()
os.environ["MTGVAULT_HOME"] = str(_TMP)
# O MTGVAULT_DB fixa-se JUNTO com o HOME: os ficheiros que acompanham a base saem
# de `db.pasta_dados()`, que é a pasta da MTGVAULT_DB — e neste PC essa variável
# aponta para o `data/` a sério (ver `test_paginas
# .caso_a_bateria_nao_escreve_no_data_a_serio`).
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import consenso, db, fases, loadout, sources  # noqa: E402

_ABERTAS = []

CATALOGO = [
    (CMD, "fin", "Legendary Creature — Human Soldier Mercenary", "W"),
    ("Weapons Manufacturing", "mh3", "Artifact", ""),
    ("Mox Opal", "som", "Legendary Artifact", ""),
    ("Urza's Saga", "mh2", "Enchantment Land — Urza's Saga", ""),
    ("Thoughtcast", "mrd", "Sorcery", "U"),
    ("Swords to Plowshares", "lea", "Instant", "W"),
    ("Path to Exile", "con", "Instant", "W"),
    ("Mother of Runes", "ulg", "Creature — Human Cleric", "W"),
    ("Brainstorm", "ice", "Instant", "U"),
    ("Argothian Enchantress", "usg", "Creature — Human Druid", "G"),
    ("Replenish", "usg", "Sorcery", "W"),
    ("Plains", "unh", "Basic Land — Plains", "W"),
]


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, tl, ci) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               set_type)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,?,?,'2000-01-01',?,0,0,'expansion')""",
            (f"sid{i}", f"or{i}", nm, sc, f"Set {sc}", str(i), tl, ci,
             json.dumps(["nonfoil", "foil"]),
             json.dumps({"commander": "legal", "modern": "legal"})))
    con.commit()
    return con


def _lista(con, chave, fmt, cartas, *, dia, tier="Presencial",
           source="mtgtop8", jogadores=80, comandante=None, nome_fonte=None,
           board="main"):
    con.execute(
        """INSERT INTO decklists (source, source_key, format, event_name,
             event_date, player, event_tier, event_players, commander,
             commander_fonte, arquetipo_fonte)
           VALUES (?,?,?,?,?,'jogador',?,?,?,?,?)""",
        (source, chave, fmt, f"{tier} qualquer", dia, tier, jogadores,
         comandante, "sideboard" if comandante else None, nome_fonte))
    did = con.execute("SELECT id FROM decklists WHERE source=? AND source_key=?",
                      (source, chave)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                    " quantity, board) VALUES (?,?,?,?)", (did, nm, q, board))
    if comandante:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                    " quantity, board) VALUES (?,?,1,'main')", (did, comandante))
    con.commit()
    return did


# ---------------------------------------------------------------------------
# 1. O CASO CENTRAL: o consenso não volta a contar o que é anterior ao corte
# ---------------------------------------------------------------------------
def caso_o_consenso_nao_conta_listas_anteriores_ao_corte():
    """Este é o caso que a ordem pede: *"um teste que chumba se o consenso voltar
    a contar listas anteriores a 29/09"*.

    Seis listas antes do corte e duas depois. O consenso tem de ver DUAS — nas
    três superfícies que respondem à mesma pergunta (o SQL, o Python linha a
    linha, e o selector de listas de um deck).
    """
    _config()
    con = base()
    cartas = [("Weapons Manufacturing", 4), ("Mox Opal", 4), ("Thoughtcast", 4)]
    for i in range(6):
        _lista(con, f"velha{i}", "modern", cartas, dia=ANTES)
    for i in range(2):
        _lista(con, f"nova{i}", "modern", cartas, dia=DEPOIS)

    # (a) o SQL
    conta, cp = sources.counting_sql("modern", "d")
    n = con.execute(f"SELECT COUNT(*) FROM decklists d WHERE d.format='modern' "
                    f"AND {conta}", cp).fetchone()[0]
    assert n == 2, f"o counting_sql conta {n} listas, e só 2 são de {CORTE} em diante"
    assert CORTE in cp, cp

    # (b) o Python, linha a linha
    linhas = list(con.execute("SELECT * FROM decklists"))
    contam = [r for r in linhas if sources.lista_conta(r, "modern")]
    assert len(contam) == 2, [dict(r) for r in contam]
    assert all((r["event_date"] or "") >= CORTE for r in contam)

    # (c) o selector de listas de um deck (a lista de uma caixa de consenso)
    ids = sources.ids_por_assinatura(con, "modern", ["Weapons Manufacturing"])
    assert len(ids) == 2, ids

    # E a lista da caixa sai do consenso das DUAS, não das oito.
    cards, nota = loadout._cards_from_consensus(con, "modern",
                                                ["Weapons Manufacturing"])
    assert "2 listas" in nota, nota
    print("o consenso conta 2 das 8 listas — as anteriores a 2026-09-29 ficam fora")


def caso_uma_lista_manual_tambem_respeita_o_corte():
    """As listas `manual` contam SEMPRE (foi ele que as meteu à mão) — mas não
    podem ser mais velhas do que a janela, senão essa excepção era o buraco por
    onde Setembro voltava a entrar."""
    _config()
    con = base()
    _lista(con, "m-velha", "modern", [("Mox Opal", 4)], dia=ANTES,
           source="manual", tier=None, jogadores=None)
    _lista(con, "m-nova", "modern", [("Mox Opal", 4)], dia=DEPOIS,
           source="manual", tier=None, jogadores=None)
    conta, cp = sources.counting_sql("modern", "d")
    datas = [r[0] for r in con.execute(
        f"SELECT d.event_date FROM decklists d WHERE d.format='modern' "
        f"AND {conta}", cp)]
    assert datas == [DEPOIS], datas
    linhas = list(con.execute("SELECT * FROM decklists"))
    assert [r["event_date"] for r in linhas
            if sources.lista_conta(r, "modern")] == [DEPOIS]
    print("a lista manual conta sempre, mas nao antes da janela")


def caso_o_consenso_por_comandante_leva_o_mesmo_corte():
    """O `consenso.consenso` não escreve um segundo corte: herda-o do
    `counting_sql`, que é onde a pergunta vive."""
    _config()
    con = base()
    for i in range(9):
        _lista(con, f"dc-velha{i}", "duel-commander",
               [("Swords to Plowshares", 1), ("Mother of Runes", 1)],
               dia=ANTES, comandante=CMD, tier="League", jogadores=None)
    for i in range(9):
        _lista(con, f"dc-nova{i}", "duel-commander",
               [("Swords to Plowshares", 1), ("Path to Exile", 1)],
               dia=DEPOIS, comandante=CMD, tier="League", jogadores=None)
    c = consenso.consenso(con, CMD)
    assert c["listas"] == 9, c["listas"]
    assert c["desde"] == CORTE, c
    nomes = {x["nm"] for x in c["cartas"]}
    assert "Path to Exile" in nomes, nomes
    assert "Mother of Runes" not in nomes, \
        "uma carta que só aparece nas listas velhas não pode estar no consenso"
    print("o consenso por comandante ve so as listas de 2026-09-29 em diante")


# ---------------------------------------------------------------------------
# 2. A RESERVA FICA NA JANELA DELA
# ---------------------------------------------------------------------------
def caso_a_reserva_continua_na_janela_dela():
    """*"deixa a reserva como está e assinala o conflito"* (ordem dele, 03/10).

    A R5 protege *"toda a carta que tenha sido jogada no último mês"*. A janela
    do consenso não lhe toca: ela não passa pelo `counting_sql` (o
    `ids_por_assinatura` da reserva usa `so_que_contam=False`) e por isso vê as
    listas dos 30 dias, corte ou não corte.
    """
    # As datas são RELATIVAS a hoje, de propósito: a janela da reserva são 30
    # dias a rolar, e um teste com datas fixas passava hoje e chumbava em
    # Novembro sem nada ter mudado.
    from datetime import timedelta
    hoje = date.today()
    corte = (hoje - timedelta(days=2)).isoformat()      # o consenso
    velho = (hoje - timedelta(days=10)).isoformat()     # dentro dos 30 dias
    _config({"consenso": dict(CFG["consenso"], desde=corte)})
    con = base()
    cartas = [("Weapons Manufacturing", 4), ("Mox Opal", 4),
              ("Urza's Saga", 4), ("Thoughtcast", 4)]
    for i in range(8):
        _lista(con, f"r-velha{i}", "modern", cartas, dia=velho)
    _lista(con, "r-nova", "modern", cartas, dia=hoje.isoformat())

    # A reserva vê as 9 listas (a janela dela é de 30 dias e nenhuma é mais
    # velha do que isso).
    desde = fases.desde_de(fases.janela_dias())
    ids = sources.ids_por_assinatura(con, "modern", ["Weapons Manufacturing"],
                                     desde=desde, so_que_contam=False)
    assert len(ids) == 9, f"a reserva ve {len(ids)} listas, deviam ser 9"
    assert fases.janela_dias() == 30, fases.janela_dias()

    # ... e o consenso vê apenas a que está depois do corte.
    do_consenso = sources.ids_por_assinatura(con, "modern",
                                             ["Weapons Manufacturing"])
    assert len(do_consenso) == 1, (len(do_consenso), len(ids))

    # E a prova a sério: a janela da reserva é a `reserva.janela_dias`, nunca o
    # `consenso.desde`. Mexer no `desde` não lhe mexe um dia nem uma lista.
    _config({"consenso": dict(CFG["consenso"],
                              desde=hoje.isoformat())})
    assert fases.desde_de(fases.janela_dias()) == desde, \
        "a janela da reserva mudou quando o consenso.desde mudou"
    ids2 = sources.ids_por_assinatura(con, "modern", ["Weapons Manufacturing"],
                                      desde=desde, so_que_contam=False)
    assert len(ids2) == 9, len(ids2)
    print("a reserva fica nos 30 dias dela, com o corte do consenso a mudar ao lado")


def caso_a_assinatura_derivada_tambem_fica_fora_do_corte():
    """A assinatura DERIVADA é a frequência de cada carta no formato, e serve a
    RESERVA. Com o corte, as contagens caíam abaixo do `ASSINATURA_MIN` (3) e a
    assinatura derivada de uma caixa desaparecia — a caixa ficava com a reserva
    só manual, sem um único erro."""
    _config()
    con = base()
    cartas = [("Weapons Manufacturing", 4), ("Mox Opal", 4), ("Thoughtcast", 4)]
    for i in range(5):
        _lista(con, f"d-velha{i}", "modern", cartas, dia=ANTES)
    _lista(con, "d-nova", "modern", cartas, dia=DEPOIS)
    s = {"slot": "x", "nome": "x", "formato": "modern",
         "cards": [("main", "Weapons Manufacturing", 4),
                   ("main", "Mox Opal", 4), ("main", "Thoughtcast", 4)]}
    der = fases.assinatura_derivada(con, s, {})
    assert der, ("a assinatura derivada ficou vazia — o corte apanhou a "
                 "frequência que serve a reserva")
    # Com o corte aplicado só havia UMA lista, abaixo do ASSINATURA_MIN de 3.
    print(f"a assinatura derivada continua a sair das 6 listas: {der}")


# ---------------------------------------------------------------------------
# 3. AMOSTRA INSUFICIENTE: «não dá para dizer», sem percentagens
# ---------------------------------------------------------------------------
def caso_abaixo_do_minimo_diz_amostra_insuficiente_e_nao_da_percentagens():
    """*"Prefiro «não dá para dizer» a um número bonito e falso."*

    Com 2 listas, uma carta que apareça numa delas «aparece em 50 %» — e isso
    não quer dizer nada. Por isso a percentagem **não sai do motor**: fica o
    número de listas, que é um facto, e a frase de amostra insuficiente.
    """
    _config()
    con = base()
    for i in range(2):
        _lista(con, f"poucas{i}", "duel-commander",
               [("Swords to Plowshares", 1)] + ([("Brainstorm", 1)] if i else []),
               dia=DEPOIS, comandante=CMD, tier="League", jogadores=None)
    c = consenso.consenso(con, CMD)
    assert c["listas"] == 2 and not c["suficiente"], c
    assert sources.AMOSTRA_INSUFICIENTE in c["amostra"], c["amostra"]
    assert "2 listas" in c["amostra"], c["amostra"]
    assert c["cartas"], "as cartas continuam à vista"
    assert all(x["pct"] is None for x in c["cartas"]), \
        "com 2 listas a percentagem não pode viajar: " + repr(c["cartas"])
    assert all(x["papel"] == "" for x in c["cartas"]), \
        "sem percentagem fiável não há núcleo/flex/raro"
    assert sum(c["papeis"].values()) == 0, c["papeis"]
    # O número de listas FICA — é um facto, ao contrário da percentagem.
    assert {x["nm"]: x["listas"] for x in c["cartas"]} == \
        {"Swords to Plowshares": 2, "Brainstorm": 1}

    # Acima do mínimo volta a haver percentagem e papéis.
    for i in range(8):
        _lista(con, f"muitas{i}", "duel-commander",
               [("Swords to Plowshares", 1)], dia=DEPOIS, comandante=CMD,
               tier="League", jogadores=None)
    c2 = consenso.consenso(con, CMD)
    assert c2["suficiente"] and c2["amostra"] == "", c2["amostra"]
    assert all(x["pct"] is not None for x in c2["cartas"])
    assert c2["papeis"]["nucleo"] >= 1, c2["papeis"]
    print("abaixo do minimo: «amostra insuficiente», listas sim, percentagens nao")


def caso_a_pagina_mostra_a_amostra_insuficiente_em_vez_das_percentagens():
    """O motor pode estar certo e a página mentir. O JavaScript tem de tratar o
    `pct` a `null` e de mostrar a frase em letra grande."""
    import comandantes
    js = comandantes._JS
    assert "d.suficiente" in js and "amostra" in js, \
        "a página não lê a amostra insuficiente"
    assert "aviso grande" in js, "o aviso não está em letra grande"
    assert "c.pct !== null" in js, \
        "o tile não trata o pct a null — ia desenhar «null %»"
    assert ".aviso.grande" in comandantes._CSS, "falta o CSS do aviso grande"
    print("a pagina trata o pct a null e mostra o aviso em letra grande")


def caso_a_caixa_sem_amostra_diz_amostra_insuficiente_na_nota():
    """A mesma frase na lista de uma caixa — e não um *"só 2 listas contam"* que
    o mandava procurar o porquê."""
    _config()
    con = base()
    for i in range(2):
        _lista(con, f"c{i}", "modern", [("Weapons Manufacturing", 4)],
               dia=DEPOIS)
    cards, nota = loadout._cards_from_consensus(con, "modern",
                                                ["Weapons Manufacturing"])
    assert cards == [], cards
    assert sources.AMOSTRA_INSUFICIENTE in nota, nota
    assert CORTE in nota, f"a nota tem de dizer a janela: {nota}"
    print(f"a caixa sem amostra diz: {nota}")


# ---------------------------------------------------------------------------
# 4. A PERGUNTA VIVE NUM SÍTIO SÓ
# ---------------------------------------------------------------------------
def caso_a_janela_vive_num_sitio_so():
    """Um segundo sítio a ler `consenso.desde` à mão discordava do primeiro num
    dia qualquer, em silêncio — é a lição do `event_tier`, do `e_foil` e do
    `precos.sql()`."""
    import re
    # `get("consenso")`, `["consenso"]` e `consenso.desde` — a leitura da CHAVE
    # do config. O `fonte == "consenso"` das caixas é outra coisa e não conta.
    padrao = re.compile(r'get\(\s*"consenso"|\[\s*"consenso"\s*\]'
                        r'|"consenso\.desde"|"consenso"\s*,\s*\{')
    alvos = [p for p in list(RAIZ.glob("*.py")) + list((RAIZ / "mtgvault").glob("*.py"))
             if p.name not in ("sources.py",)]
    maus = []
    for p in alvos:
        t = p.read_text(encoding="utf-8")
        for i, linha in enumerate(t.splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            if padrao.search(linha):
                maus.append(f"{p.name}:{i}: {linha.strip()[:90]}")
    assert not maus, ("alguém voltou a ler a chave `consenso` do config por "
                      "fora do sources: " + " | ".join(maus))
    # E as funções existem onde têm de existir.
    for nome in ("consenso_desde", "consenso_sql", "regras_consenso",
                 "texto_janela_consenso", "texto_amostra",
                 "frase_janela_rodape"):
        assert hasattr(sources, nome), nome
    print("a janela do consenso vive num sitio so (mtgvault/sources.py)")


# ---------------------------------------------------------------------------
# 5. EXCEPÇÕES POR FORMATO
# ---------------------------------------------------------------------------
def caso_o_premodern_fica_fora_do_corte():
    """O Reality Fracture não é legal em Premodern (o formato acaba no Scourge,
    2003): o corte não responderia a pergunta nenhuma e só apagava o consenso.
    Medido na base dele a 03/10: das 978 listas de premodern, ZERO jogam uma
    carta do set — e sem a excepção três caixas ficavam sem lista."""
    _config()
    con = base()
    cartas = [("Argothian Enchantress", 4), ("Replenish", 4)]
    for i in range(6):
        _lista(con, f"pm{i}", "premodern", cartas, dia=ANTES)
    assert sources.consenso_desde("premodern") == ""
    assert sources.consenso_desde("modern") == CORTE
    conta, cp = sources.counting_sql("premodern", "d")
    n = con.execute(f"SELECT COUNT(*) FROM decklists d WHERE "
                    f"d.format='premodern' AND {conta}", cp).fetchone()[0]
    assert n == 6, f"o premodern perdeu listas para o corte: {n}"
    ids = sources.ids_por_assinatura(con, "premodern",
                                     ["Argothian Enchantress"])
    assert len(ids) == 6, ids
    # E a excepção é uma linha: tirá-la do config põe o premodern no corte.
    _config({"consenso": dict(CFG["consenso"], excepcoes=[])})
    assert sources.consenso_desde("premodern") == CORTE
    conta, cp = sources.counting_sql("premodern", "d")
    n2 = con.execute(f"SELECT COUNT(*) FROM decklists d WHERE "
                     f"d.format='premodern' AND {conta}", cp).fetchone()[0]
    assert n2 == 0, n2
    print("o premodern fica fora do corte, e a excepcao e uma linha no config")


# ---------------------------------------------------------------------------
# 6. SEM A CHAVE NADA MUDA
# ---------------------------------------------------------------------------
def caso_sem_a_chave_o_vault_fica_exactamente_como_estava():
    """O padrão do `venda.mostrar`: apagar o `consenso.desde` devolve tudo ao
    que era, e não há um segundo sítio a lembrar-se do corte."""
    con = base()
    cartas = [("Weapons Manufacturing", 4), ("Mox Opal", 4)]
    for i in range(6):
        _lista(con, f"s{i}", "modern", cartas, dia=ANTES)
    for i in range(2):
        _lista(con, f"n{i}", "modern", cartas, dia=DEPOIS)

    _config(sem=("consenso",))
    assert sources.consenso_desde("modern") == ""
    assert sources.consenso_sql("modern", "d") == ("", [])
    assert sources.texto_janela_consenso("modern") == ""
    assert sources.frase_janela_rodape() == ""
    conta, cp = sources.counting_sql("modern", "d")
    assert "event_date" not in conta, conta
    n = con.execute(f"SELECT COUNT(*) FROM decklists d WHERE d.format='modern' "
                    f"AND {conta}", cp).fetchone()[0]
    assert n == 8, n
    assert len(sources.ids_por_assinatura(
        con, "modern", ["Weapons Manufacturing"])) == 8

    # Com um `desde` vazio é o mesmo que não ter a chave.
    _config({"consenso": {"desde": "", "excepcoes": []}})
    assert sources.consenso_desde("modern") == ""
    conta2, _ = sources.counting_sql("modern", "d")
    assert conta2 == conta
    print("sem consenso.desde o vault fica exactamente como estava")


# ---------------------------------------------------------------------------
# 7. SEGUIR UMA LISTA NÃO É CONSENSO
# ---------------------------------------------------------------------------
def caso_seguir_uma_lista_fica_fora_do_corte():
    """O `my_decks` pede *"a lista mais recente"*, e o corte não a torna mais
    recente — só pode fazê-la desaparecer e deixar a caixa sem lista. Medido a
    03/10: com o corte, o *Grinding Station* (28/09) e o *Jeskai Lessons*
    (27/09) ficavam sem lista nenhuma, sem um número novo a trocar."""
    _config()
    import my_decks
    sql, _p = my_decks._conta("modern")
    assert "event_date" not in sql, \
        "o my_decks voltou a levar o corte do consenso: " + sql
    # E está escrito porquê, no código, para não voltar por descuido.
    doc = my_decks._conta.__doc__ or ""
    assert "consenso" in doc.lower(), "falta o porquê no `my_decks._conta`"
    # O resto do vault continua a levá-lo.
    sql2, p2 = sources.counting_sql("modern", "d")
    assert "event_date" in sql2 and CORTE in p2
    print("seguir uma lista fica fora do corte, e esta escrito porque")


# ---------------------------------------------------------------------------
# 8. A JANELA VIAJA PARA A PÁGINA
# ---------------------------------------------------------------------------
def caso_a_janela_aparece_nas_paginas():
    """Uma janela que a página não diz é uma página a mentir em silêncio: o
    número de listas cai para um quinto e quem olha não tem como saber porquê."""
    _config()
    frase = sources.frase_janela_rodape()
    assert CORTE in frase and "janela" in frase.lower(), frase
    assert "premodern" in frase, "a excepção tem de estar dita"
    assert sources.AMOSTRA_INSUFICIENTE in frase, frase

    import comandantes
    rod = comandantes._rodape()
    assert CORTE in rod, "o rodapé dos Comandantes não diz a janela"
    assert "%JANELA%" not in rod, "ficou um marcador por substituir"

    import meta_coverage
    assert CORTE in meta_coverage._tmpl(), "a Cobertura não diz a janela"
    assert "%JANELA%" not in meta_coverage._tmpl()

    import showcase
    assert CORTE in showcase._tmpl(), "o Showcase não diz a janela"
    assert "%JANELA%" not in showcase._tmpl()

    # Sem a chave, nenhuma delas inventa uma janela.
    _config(sem=("consenso",))
    assert "%JANELA%" not in meta_coverage._tmpl()
    assert CORTE not in meta_coverage._tmpl()
    assert "%JANELA%" not in comandantes._rodape()
    assert CORTE not in comandantes._rodape()
    print("as paginas dizem a janela, e sem a chave nao inventam nenhuma")


def caso_o_daily_diz_a_janela_com_que_calculou():
    """Um log de um dia com corte era igual ao de um dia sem. O passo
    `janela-consenso` existe para essa linha ficar no `job_runs`."""
    _config()
    import daily
    txt = daily._janela_consenso()
    assert CORTE in txt, txt
    assert "premodern" in txt, txt
    _config(sem=("consenso",))
    txt2 = daily._janela_consenso()
    assert "sem corte" in txt2, txt2
    # E o passo está encadeado no job.
    src = (RAIZ / "daily.py").read_text(encoding="utf-8")
    assert '"janela-consenso"' in src, "o passo não está no daily"
    print("o daily diz a janela com que calculou, e diz quando nao ha corte")


def caso_o_config_a_serio_tem_a_janela_e_a_data_do_mtgo():
    """O config dele, não um de teste: a data é a do MTGO (29/09) e não a do
    papel (02/10), e o motivo e a fonte estão escritos."""
    os.environ.pop("MTGVAULT_CONFIG", None)
    sources._CFG_CACHE.clear()
    try:
        r = sources.regras_consenso()
        assert r["desde"] == CORTE, r
        assert "Magic Online" in (r.get("motivo") or ""), r
        assert "mtgo.com" in (r.get("fonte") or ""), r
        assert "premodern" in [str(x) for x in (r.get("excepcoes") or [])], r
        print(f"o config a serio: desde {r['desde']}, fora {r['excepcoes']}")
    finally:
        _config()


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for f in CASOS:
        f()
    print(f"\n{len(CASOS)} casos ok")
