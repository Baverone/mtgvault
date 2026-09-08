"""Premodern: sugerir o que montar com o que sobra, e vender o resto.

Ordem do André (2026-09-08, à letra): *"O que não estiver a ser usado em
Premodern e se encaixe na regra do Premodern deve ser sugerido para venda. Antes
disso, procura decklists do formato; se o deck for top-10 de representação ou
top-5 decks combo do formato, sugere a lista para montar o deck caso eu tenha
pelo menos 50 % das cartas (sem contar com as básicas para a %); se não, envia
para vender."*

O que aqui se tranca é a ordem em que as três regras se aplicam — trocá-la muda
o que ele vende, e vender é a decisão que não se desfaz:

  1. o **top-10 de representação** e o **top-5 de combo** saem das listas que
     CONTAM (a regra de sempre), e o combo decide-se por REGRA sobre a lista de
     consenso — a mesma que separa a Enchantress do UW Replenish, que 96% das
     listas confundem;
  2. a **cobertura** conta as cópias PT que NENHUMA caixa levou, e **sem as
     básicas**: medi-la sobre a colecção inteira dava 60% a um deck cujas cartas
     estão todas dentro de outro deck montado;
  3. o que uma **sugestão** usaria não vai para a venda enquanto ele não decidir;
     o *"não quero este"* liberta-o no mesmo dia;
  4. uma cópia que serve uma caixa de OUTRO formato no material que essa caixa
     aceita nunca entra na venda — é a irmã da saída `guardar`;
  5. e nada sai da base de dados por causa disto: a lista é uma sugestão, quem
     tira a cópia é o botão *"vendida"*.

Não toca na rede.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
CFG_PATH = _TMP / "cfg.json"

# O grupo de Premodern tal como está no repositório: PT, edições até ao Scourge,
# estrita, e os baldes de colecção. É ele que decide o que uma caixa de Premodern
# VÊ — e, por isso, o que a regra da venda considera "por usar".
REGRA_PM = {"grupo": "premodern", "formatos": ["premodern"], "dedicado": False,
            "playset_maximo": 4, "lingua": "pt", "edicoes": "premodern",
            "estrita": True,
            "baldes": ["Colecção", "Premodern (geral)", "SPML",
                       "Caixa Reserved List"]}
BASE_CFG = {
    "metagame_fontes": {"_default": {"tiers": ["Challenge"], "ligas": False}},
    "regras_por_formato": [
        REGRA_PM,
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "acabamento": "foil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "lingua": "en", "acabamento": "foil"},
    ],
    "premodern": {"top_representados": 2, "top_combo": 1, "min_listas": 5,
                  "sugerir_a_partir_de_pct": 50},
}


def cfg(**premodern):
    """Reescreve o config e esquece a cache — como o `webapp.escrever_config`.

    Os limiares são config, e um teste que não os possa mexer não prova que eles
    mandam: provava só o que o valor de omissão faz.
    """
    from mtgvault import sources
    novo = json.loads(json.dumps(BASE_CFG))
    novo["premodern"].update(premodern)
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return novo


CFG_PATH.write_text(json.dumps(BASE_CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import analysis, db, loadout, premodern  # noqa: E402

# (nome, edição, data). Antes do Scourge (2003-05-26) = "da era".
CATALOGO = [
    ("Argothian Enchantress", "usg", "1998-10-12"),
    ("Enchantress's Presence", "ons", "2002-10-07"),
    ("Sterling Grove", "usg", "1998-10-12"),
    ("Serra's Sanctum", "usg", "1998-10-12"),
    ("Stasis", "4bb", "1995-04-01"),
    ("Forsaken City", "wth", "1997-06-09"),
    ("Black Vise", "4bb", "1995-04-01"),
    ("Goblin Warchief", "scg", "2003-05-26"),
    ("Goblin Piledriver", "ons", "2002-10-07"),
    ("Mogg Fanatic", "tmp", "1997-10-14"),
    ("Swords to Plowshares", "4bb", "1995-04-01"),
    ("Sylvan Library", "4bb", "1995-04-01"),
    ("Kappa Cannoneer", "mh3", "2024-06-14"),
    ("Island", "4bb", "1995-04-01"),
    ("Plains", "4bb", "1995-04-01"),
]

# Os três arquétipos de mentira. O primeiro e o segundo batem em regras de combo
# (Enchantress e Stasis); o terceiro não bate em nenhuma, e é o mais
# representado — é ele que prova que "não ser combo" não tira ninguém do top-10.
ENCHANTRESS = [("Argothian Enchantress", 4), ("Enchantress's Presence", 4),
               ("Sterling Grove", 3), ("Serra's Sanctum", 4), ("Plains", 20)]
STASIS = [("Stasis", 4), ("Forsaken City", 4), ("Black Vise", 4), ("Island", 20)]
GOBLINS = [("Goblin Warchief", 4), ("Goblin Piledriver", 4),
           ("Mogg Fanatic", 4), ("Plains", 20)]

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Enchantment',2,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i),
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"premodern": "legal", "legacy": "legal",
                         "duel-commander": "legal", "commander": "legal"})))
    con.commit()
    return con


def listas(con, cartas, n, jogador):
    """`n` decklists iguais de um Challenge recente — as que CONTAM."""
    quando = (date.today() - timedelta(days=3)).isoformat()
    for i in range(n):
        con.execute(
            """INSERT INTO decklists (source, source_key, format, event_name,
               event_date, player, event_tier) VALUES
               ('mtgo', ?, 'premodern', 'Premodern Challenge', ?, ?, 'Challenge')""",
            (f"{jogador}-{i}", quando, f"{jogador}{i}"))
        did = con.execute("SELECT MAX(id) i FROM decklists").fetchone()["i"]
        for nm, q in cartas:
            con.execute("INSERT INTO decklist_cards (decklist_id, card_name, "
                        "quantity, board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def analisa(con):
    analysis.rebuild_archetypes(con, "premodern")
    analysis.rebuild_roles(con, "premodern")
    con.commit()


def add(con, nm, q=1, finish="nonfoil", lang="pt", sub="Colecção"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub_id))
    con.commit()


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def caixa(slot, nome, fmt, ref, balde="Premodern (geral)", **kw):
    d = {"slot": slot, "nome": nome, "formato": fmt, "fonte": "deck", "ref": ref,
         "balde": balde, "estado": "permanente", "prioridade": 1}
    d.update(kw)
    return d


def mundo(com_caixa=True):
    """Uma base com três arquétipos e (opcionalmente) a caixa da Enchantress."""
    con = base()
    listas(con, GOBLINS, 9, "gob")
    listas(con, ENCHANTRESS, 7, "ench")
    listas(con, STASIS, 6, "sta")
    analisa(con)
    slots = []
    if com_caixa:
        deck(con, "Enchantress (consenso)", "premodern", ENCHANTRESS)
        slots.append(caixa("premodern-enchantress", "Enchantress", "premodern",
                           "Enchantress (consenso)"))
    return con, slots


def pm_de(rep):
    return rep["premodern"]


def por_nome(pm):
    return {c["nome"]: c for c in pm["todos"]}


# ---------------------------------------------------------------------------
def caso_top10_e_top5_combo():
    """*"Top-10 de representação **ou** top-5 decks combo"* — são duas listas.

    Com `top_representados: 2`, os Goblins e a Enchantress entram por serem os
    mais jogados; o Stasis fica de fora do top e entra pela porta do combo. Se as
    duas listas fossem uma soma, o critério por que cada deck entrou deixava de
    se poder ler na página — e é ele que explica porque é que um deck com 6
    listas aparece ao lado de um com 9.
    """
    cfg()
    con, slots = mundo()
    rep = loadout.report(con, slots)
    pm = pm_de(rep)
    assert pm["activo"], "há uma caixa de Premodern: a regra está em vigor"
    nomes = [c["nome"] for c in pm["top"]]
    assert nomes == ["Goblins", "Enchantress"], nomes
    assert [c["nome"] for c in pm["combo"]] == ["Enchantress"], pm["combo"]
    # O Stasis não é dos dois mais jogados nem é o combo mais jogado: fica fora.
    assert "Stasis" not in [c["nome"] for c in pm["elegiveis"]]
    print("top-N por representação e top-N de combo são duas listas, com a marca "
          "de por onde cada um entrou")

    cfg(top_combo=2)
    pm = pm_de(loadout.report(con, slots))
    assert [c["nome"] for c in pm["combo"]] == ["Enchantress", "Stasis"]
    assert "Stasis" in [c["nome"] for c in pm["elegiveis"]], "entrou pelo combo"
    print("com top_combo=2 o Stasis entra pela porta do combo, não pela do top")


def caso_combo_por_regra_nomeia_e_separa():
    """O combo (e o NOME) decidem-se por regra sobre a lista de consenso.

    O `meta_coverage.KNOWN` chama *"Replenish"* à Enchantress e ao UW Replenish,
    porque bate na primeira carta que encontra. A regra com `none` separa-os — é
    o mesmo truque do `archetype_rules.json`, e sem ele as duas caixas dele
    tinham o mesmo nome no ranking.
    """
    cfg()
    ench = {"Argothian Enchantress", "Replenish", "Opalescence"}
    repl = {"Replenish", "Opalescence", "Attunement"}
    assert premodern.classificar(ench)[0] == "Enchantress"
    assert premodern.classificar(repl)[0] == "UW Replenish"
    # A ORDEM das regras é a prioridade: o Full English Breakfast joga Survival
    # of the Fittest e, escrito depois do Elves/Survival, chamava-se Elves.
    feb = {"Volrath's Shapeshifter", "Survival of the Fittest"}
    assert premodern.classificar(feb)[0] == "Full English Breakfast"
    assert premodern.classificar({"Survival of the Fittest"})[0] == "Elves / Survival"
    # Um deck que não bate em regra nenhuma não é combo — e não deixa de contar.
    assert premodern.classificar({"Mogg Fanatic"}) == (None, None)
    print("combo e nome por regra: Enchantress ≠ UW Replenish, e a ordem manda")


def caso_cobertura_e_do_que_sobra_e_sem_basicas():
    """A percentagem é a das cópias que NENHUMA caixa levou, e ignora as básicas.

    A caixa da Enchantress leva as 4 Argothian; o candidato Enchantress fica com
    0% do que sobra, mesmo tendo 100% contando a colecção inteira. Medir sobre a
    colecção inteira era prometer-lhe um deck feito das cartas de outro deck.
    """
    cfg()
    con, slots = mundo()
    for nm, q in ENCHANTRESS:
        add(con, nm, q)
    pm = pm_de(loadout.report(con, slots))
    c = por_nome(pm)["Enchantress"]
    assert c["pct"] == 0, f'sobra {c["pct"]}%'
    assert c["pct_total"] == 100, f'ao todo {c["pct_total"]}%'
    # E as básicas ficam de fora da conta: 20 Plains em 35 cartas fariam qualquer
    # deck começar acima dos 55% e nenhum se distinguia dos outros.
    assert c["need"] == sum(q for nm, q in ENCHANTRESS if nm != "Plains"), c["need"]
    print("a cobertura é a do que sobra (0%) e não a da colecção inteira (100%), "
          "e as básicas não entram")

    # Sem a caixa, as mesmas cópias estão livres e a cobertura é 100%.
    con2, _ = mundo(com_caixa=False)
    for nm, q in ENCHANTRESS:
        add(con2, nm, q)
    solta = caixa("premodern-stasis", "Stasis", "premodern", "Stasis (consenso)")
    deck(con2, "Stasis (consenso)", "premodern", STASIS)
    pm2 = pm_de(loadout.report(con2, [solta]))
    assert por_nome(pm2)["Enchantress"]["pct"] == 100
    print("as mesmas cópias, sem a caixa que as levava, dão 100%")


def caso_sugestao_reserva_as_cartas_e_tira_as_da_venda():
    """*"Enquanto forem só sugestões, as cartas que precisariam ficam reservadas."*

    Sem esta regra a lista de venda mandava vender exactamente o deck que a
    página do lado lhe estava a sugerir montar — o mesmo erro que a saída
    `guardar` veio corrigir na primeira versão da venda.
    """
    # `top_combo=2` para o Stasis ser elegível: só se sugere o que passou por uma
    # das duas portas (top-10 ou top-5 combo), e com `top_combo=1` a porta do
    # combo é da Enchantress. É a regra a funcionar, não um ajuste do teste.
    cfg(sugerir_a_partir_de_pct=50, top_combo=2)
    con, slots = mundo()
    for nm, q in STASIS:               # tem o Stasis inteiro, e não é caixa
        add(con, nm, q)
    rep = loadout.report(con, slots)
    pm = pm_de(rep)
    assert [c["nome"] for c in pm["sugestoes"]] == ["Stasis"], pm["sugestoes"]
    reservado = {r["nm"] for r in rep["reservadas"]}
    assert {"Stasis", "Forsaken City", "Black Vise"} <= reservado, reservado
    assert all("reservada para Stasis" in r["reason"] for r in rep["reservadas"])
    vendidas = {r["nm"] for r in rep["venda"] + rep["venda_rl"]}
    assert not (vendidas & reservado), vendidas & reservado
    # A básica nunca entra em nenhuma das duas listas.
    assert "Island" not in reservado and "Island" not in vendidas
    print("uma sugestão aberta reserva as cartas dela: não se vendem, e a linha "
          "diz para que sugestão é")


def caso_recusa_liberta_as_cartas_para_a_venda():
    """*"Se ele desmarcar/ignorar uma sugestão, as cartas libertam-se para venda."*

    A recusa fica escrita e datada no config: guardá-la só no browser fazia a
    sugestão voltar amanhã e as cartas dela saírem outra vez da lista de venda.
    """
    cfg(sugerir_a_partir_de_pct=50, top_combo=2)
    con, slots = mundo()
    for nm, q in STASIS:
        add(con, nm, q)
    assert loadout.report(con, slots)["reservadas"], "há sugestão, há reserva"

    cfg(sugerir_a_partir_de_pct=50, top_combo=2,
        sugestoes_recusadas={"Stasis": "2026-09-08"})
    rep = loadout.report(con, slots)
    pm = pm_de(rep)
    assert pm["sugestoes"] == [], pm["sugestoes"]
    assert por_nome(pm)["Stasis"]["estado"] == "recusada"
    assert not rep["reservadas"], rep["reservadas"]
    vendidas = {r["nm"]: r for r in rep["venda"] + rep["venda_rl"]}
    assert "Stasis" in vendidas, list(vendidas)
    assert vendidas["Stasis"]["reason"] == loadout.RAZAO_PREMODERN
    print("recusar a sugestão liberta as cartas dela, com o motivo próprio")

    # E o botão do modo edição escreve isso no config — com a data.
    cfg2 = {"premodern": {}}
    premodern.recusar(cfg2, "Stasis", "2026-09-08")
    assert cfg2["premodern"]["sugestoes_recusadas"] == {"Stasis": "2026-09-08"}
    premodern.aceitar(cfg2, "Stasis")
    assert not cfg2["premodern"].get("sugestoes_recusadas")
    print("o «não quero este» escreve-se com a data, e desfaz-se")


def caso_pt_da_era_por_usar_vai_para_venda_com_motivo_proprio():
    """*"O que não estiver a ser usado em Premodern (...) deve ser sugerido para
    venda."* Com motivo próprio, e não misturado no "excedente (mais de 4)".

    Uma PT da era está TRANCADA ao Premodern; se nenhuma caixa a usa não serve
    mais nada. Mas as duas razões são decisões diferentes — *"tens cópias a
    mais"* e *"não tens onde a jogar"* — e um total que as some não se pode usar.
    """
    cfg()
    con, slots = mundo()
    add(con, "Swords to Plowshares", 2)     # PT da era, nenhum deck a pede
    add(con, "Kappa Cannoneer", 2)          # de 2024: não é da era, não entra
    add(con, "Sylvan Library", 1, lang="en")  # EN: a caixa nem a vê
    rep = loadout.report(con, slots)
    linhas = {r["nm"]: r for r in rep["venda"] + rep["venda_rl"]}
    assert "Swords to Plowshares" in linhas, list(linhas)
    assert linhas["Swords to Plowshares"]["reason"] == loadout.RAZAO_PREMODERN
    assert linhas["Swords to Plowshares"]["q"] == 2
    assert "Kappa Cannoneer" not in linhas, "não é da era Premodern"
    assert "Sylvan Library" not in linhas, "é EN: não cumpre a regra do Premodern"
    print("as PT da era por usar vão para a venda com motivo próprio; as outras não")

    # Sem NENHUMA caixa de Premodern a regra não corre: "não usada por nenhum
    # deck" não quer dizer nada quando não há deck nenhum, e a alternativa era
    # mandar vender a colecção inteira de Premodern por o config estar vazio.
    con2, _ = mundo(com_caixa=False)
    add(con2, "Swords to Plowshares", 2)
    rep2 = loadout.report(con2, [caixa("legacy", "Legacy", "legacy", None,
                                       balde="SPML")])
    assert not pm_de(rep2)["activo"]
    assert not [r for r in rep2["venda"] if r["reason"] == loadout.RAZAO_PREMODERN]
    print("sem caixas de Premodern a regra não corre — não se vende por falta de config")


def caso_excedente_e_premodern_nao_se_misturam():
    """Seis cópias de uma carta que nenhum deck pede: 2 são excedente (passam do
    playset de 4) e 4 são "não usadas". Cada uma com o seu motivo.

    Contá-las duas vezes — uma em cada regra — dava uma lista de venda com mais
    cópias do que ele tem em casa, que é o erro mais caro que uma lista destas
    pode ter.
    """
    cfg()
    con, slots = mundo()
    add(con, "Swords to Plowshares", 6)
    rep = loadout.report(con, slots)
    linhas = [r for r in rep["venda"] if r["nm"] == "Swords to Plowshares"]
    assert sum(r["q"] for r in linhas) == 6, linhas
    motivos = {r["reason"]: r["q"] for r in linhas}
    assert motivos == {"excedente (mais de 4)": 2,
                       loadout.RAZAO_PREMODERN: 4}, motivos
    print("6 cópias = 2 de excedente + 4 por não estarem em deck nenhum, sem se "
          "contarem duas vezes")


def caso_carta_que_serve_outra_caixa_nao_se_vende():
    """*"Se a carta servir outro formato dele num material que esse formato
    aceite, não a mandes vender — di-lo."*

    O caso real é raro e existe: uma PT **foil** da era, arrumada num balde que
    uma caixa reclama (e por isso fora da tranca do PT), serve a caixa de Duel
    Commander — *"apenas foil"*, sem exigir língua. A cópia a mais dessa caixa
    cumpre a regra do Premodern e nenhuma caixa de Premodern a usa: sem esta
    excepção ia para a venda, e ele ficava sem a segunda cópia de uma carta que
    joga.
    """
    cfg()
    con, slots = mundo()
    deck(con, "Cloud (DC)", "duel-commander", [("Sylvan Library", 1)])
    slots.append(caixa("dc", "Cloud (DC)", "duel-commander", "Cloud (DC)",
                       balde="Cloud", prioridade=2))
    add(con, "Sylvan Library", 2, finish="foil", sub="Premodern (geral)")
    rep = loadout.report(con, slots)
    assert not [r for r in rep["venda"] + rep["venda_rl"]
                if r["nm"] == "Sylvan Library"], "não se vende o que serve uma caixa"
    guardadas = {r["nm"]: r for r in rep["guardar"]}
    assert "Sylvan Library" in guardadas, rep["guardar"]
    assert "duel-commander" in guardadas["Sylvan Library"]["reason"]
    print("a cópia a mais que serve outra caixa fica em «guardar» e diz de quem é")


def caso_nada_sai_da_base_sem_o_botao():
    """A lista é uma SUGESTÃO. Correr o relatório não tira uma cópia de casa."""
    cfg()
    con, slots = mundo()
    add(con, "Swords to Plowshares", 6)
    antes = con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"]
    rep = loadout.report(con, slots)
    assert rep["copias"] > 0, "há mesmo coisas a sugerir para venda"
    depois = con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"]
    assert antes == depois == 6, (antes, depois)
    # E o botão «vendida» continua a ser quem tira — com registo no CSV.
    linha = [r for r in rep["venda"] if r["reason"] == loadout.RAZAO_PREMODERN][0]
    csv = _TMP / "vendas-teste.csv"
    loadout.registar_venda(con, linha, 1, csv_path=csv)
    assert con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"] == 5
    assert "Swords to Plowshares" in csv.read_text(encoding="utf-8")
    print("o relatório não tira nada; quem tira é o «vendida», e fica no CSV")


def _abas_desenhadas(pagina):
    """`{aba: HTML}` — o que o browser mostraria. `None` sem `node`."""
    if not shutil.which("node"):
        return None
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_a_pagina_mostra_a_sugestao_e_a_venda():
    """O que a página DESENHA — a aba Sugestões e o motivo novo na aba Vender.

    A `deckboxes.html` é JSON + JavaScript: uma aba que rebenta só aparece ao
    CLICAR nela, em branco e sem erro no gerador. Por isso lê-se o HTML que o
    JavaScript desenhou, e não o ficheiro.
    """
    import deckboxes
    cfg(sugerir_a_partir_de_pct=50, top_combo=2)
    con, slots = mundo()
    for nm, q in STASIS:
        add(con, nm, q)
    add(con, "Swords to Plowshares", 2)          # PT da era, sem deck nenhum
    rep = loadout.report(con, slots)
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out, rep=rep)
    texto = out.read_text(encoding="utf-8")
    d = json.loads(re.search(
        r'<script id="dados" type="application/json">(.*?)</script>',
        texto, re.S).group(1).replace("<\\/", "</"))
    assert d["premodern"]["activo"] and d["premodern"]["sugestoes"] == 1
    assert d["pm_razao"] == loadout.RAZAO_PREMODERN, d["pm_razao"]
    assert d["venda"]["reservadas"]["copias"] > 0

    abas = _abas_desenhadas(out)
    if abas is None:
        print("página: sem `node`, saltado")
        return
    s = abas["sugestoes"]
    assert "Stasis" in s and "sugerido — montar?" in s, s[:400]
    assert "🧰" in s, "a caixa que ele já tem vem marcada como tal"
    assert "data-act=" not in s, "a página publicada não desenha botões"
    v = abas["vender"]
    assert loadout.RAZAO_PREMODERN in v, "o motivo novo aparece na tabela"
    assert "Reservadas" in v, "e as reservadas têm bloco próprio"
    assert "Stasis" not in v.split("Reservadas")[0], \
        "a carta reservada não pode estar na lista de venda"
    print("a página desenha a aba Sugestões e separa a venda das reservadas")


def caso_limiar_e_do_config():
    """O limiar é uma linha de config, não uma linha de código."""
    cfg(sugerir_a_partir_de_pct=50, top_combo=2)
    con, slots = mundo()
    for nm, q in STASIS[:1]:           # só uma das três cartas não-básicas
        add(con, nm, q)
    pm = pm_de(loadout.report(con, slots))
    stasis = por_nome(pm)["Stasis"]
    assert stasis["estado"] == "abaixo", (stasis["pct"], stasis["estado"])
    cfg(sugerir_a_partir_de_pct=stasis["pct"], top_combo=2)
    pm = pm_de(loadout.report(con, slots))
    assert por_nome(pm)["Stasis"]["estado"] == "sugerida"
    print(f'a {stasis["pct"]}% o Stasis é sugestão ou não conforme o limiar')


def run():
    for fn in (caso_top10_e_top5_combo,
               caso_combo_por_regra_nomeia_e_separa,
               caso_cobertura_e_do_que_sobra_e_sem_basicas,
               caso_sugestao_reserva_as_cartas_e_tira_as_da_venda,
               caso_recusa_liberta_as_cartas_para_a_venda,
               caso_pt_da_era_por_usar_vai_para_venda_com_motivo_proprio,
               caso_excedente_e_premodern_nao_se_misturam,
               caso_carta_que_serve_outra_caixa_nao_se_vende,
               caso_nada_sai_da_base_sem_o_botao,
               caso_a_pagina_mostra_a_sugestao_e_a_venda,
               caso_limiar_e_do_config):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
