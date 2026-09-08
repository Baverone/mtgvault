"""A identidade de um arquétipo: pelo CONTEÚDO, não pelo rótulo.

O erro que isto vem corrigir, medido em corridas a sério: o *"Dimir Psychatog"*
do ranking de Premodern passou a *"Dimir Polluted Delta"* no dia seguinte, e o
*"Mono-Preto Graveborn Muse"* a *"Mono-Preto Withered Wretch"*. O clustering
nomeia pelas cartas mais distintivas do núcleo, e o núcleo mexe um bocadinho
todos os dias porque a janela de 30 dias entra e sai listas.

Enquanto o nome era só um rótulo, isso era feio. Deixou de o ser em 2026-09-08,
quando a **recusa** (*"não quero este"*), a **escolha** (*"vou montar este"*) e o
reconhecimento de uma sugestão como já sendo uma caixa passaram a fazer-se pelo
nome: uma recusa de ontem deixava de bater hoje, a sugestão voltava sozinha e as
cartas dela saíam outra vez da lista de venda — sem ninguém ter carregado em
nada, e sem um único erro. É o padrão do `event_tier`.

O que aqui se tranca:

  1. **o `id` sai do núcleo** e sobrevive a uma carta trocada (herda-se acima dos
     70 % em comum), mas **não** a um baralho diferente;
  2. **uma recusa sobrevive a uma mudança de rótulo** — e o teste mostra também
     o defeito, com a forma antiga (chave = nome) a deixar de bater;
  3. **os nomes conhecidos vêm por REGRA**, incluindo os que só nomeiam
     (`combo: false`) e os que pedem a cor (`cor: true`).

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
CFG_PATH = _TMP / "cfg.json"

REGRA_PM = {"grupo": "premodern", "formatos": ["premodern"], "dedicado": False,
            "playset_maximo": 4, "lingua": "pt", "edicoes": "premodern",
            "estrita": True,
            "baldes": ["Colecção", "Premodern (geral)", "SPML",
                       "Caixa Reserved List"]}
BASE_CFG = {
    "metagame_fontes": {"_default": {"tiers": ["Challenge"], "ligas": False}},
    "regras_por_formato": [REGRA_PM],
    "premodern": {"top_representados": 5, "top_combo": 3, "min_listas": 5,
                  "sugerir_a_partir_de_pct": 50},
}


def cfg(caixas=None, **premodern):
    from mtgvault import sources
    novo = json.loads(json.dumps(BASE_CFG))
    novo["premodern"].update(premodern)
    if caixas is not None:
        novo["caixas"] = caixas
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return novo


CFG_PATH.write_text(json.dumps(BASE_CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
# O registo (`arquetipos.json`) vive ao lado da base: aponta-se para uma pasta
# temporária ANTES de importar o `db`, que fixa a raiz no momento do import.
os.environ["MTGVAULT_HOME"] = str(_TMP)

from mtgvault import analysis, arquetipos, db, loadout, premodern  # noqa: E402

# (nome, edição, data, identidade de cor). Tudo até ao Scourge = "da era".
CATALOGO = [
    ("Psychatog", "ulg", "1999-02-15", "UB"),
    ("Circular Logic", "tor", "2002-02-04", "U"),
    ("Upheaval", "ody", "2001-10-01", "U"),
    ("Standstill", "ody", "2001-10-01", "U"),
    ("Mishra's Factory", "atq", "1994-03-04", ""),
    ("Exalted Angel", "ons", "2002-10-07", "W"),
    ("Vindicate", "apc", "2001-06-04", "WB"),
    ("Duress", "usg", "1998-10-12", "B"),
    ("The Rack", "atq", "1994-03-04", ""),
    ("Fireblast", "vis", "1997-02-03", "R"),
    ("Pyrostatic Pillar", "jud", "2002-05-27", "R"),
    ("Quirion Dryad", "ons", "2002-10-07", "G"),
    ("Werebear", "ody", "2001-10-01", "G"),
    ("Wall of Blossoms", "sth", "1998-03-02", "G"),
    ("Sylvan Library", "leg", "1994-06-01", "G"),
    ("Gaea's Blessing", "wth", "1997-06-09", "G"),
    ("Land Grant", "mmq", "1999-10-04", "G"),
    ("Island", "4bb", "1995-04-01", "U"),
    ("Swamp", "4bb", "1995-04-01", "B"),
    ("Forest", "4bb", "1995-04-01", "G"),
]

# Um arquétipo que NÃO bate em regra nenhuma — é o que fica com o rótulo do
# clustering e o que, por isso, troca de nome de corrida para corrida.
SEM_REGRA = [("Quirion Dryad", 4), ("Werebear", 4), ("Wall of Blossoms", 4),
             ("Sylvan Library", 3), ("Gaea's Blessing", 2), ("Land Grant", 4),
             ("Forest", 20)]
# Um que bate numa regra que só NOMEIA (`combo: false`), e cujo nome leva a cor.
ANJO = [("Exalted Angel", 4), ("Vindicate", 4), ("Duress", 4), ("Swamp", 20)]
# E um que bate numa regra de COMBO, para o contraste.
TOG = [("Psychatog", 4), ("Circular Logic", 4), ("Upheaval", 3), ("Island", 20)]

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, ci) in enumerate(CATALOGO):
        tipo = "Basic Land" if nm in ("Island", "Swamp", "Forest") else "Creature"
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare',?,2,?,?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), tipo, ci,
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"premodern": "legal", "legacy": "legal"})))
    con.commit()
    return con


def listas(con, cartas, n, jogador):
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


def add(con, nm, q=1, sub="Colecção"):
    """Cópias PT da era, que é o que uma caixa de Premodern vê."""
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,'nonfoil','pt',
                   'player',?)""", (sid, q, sub_id))
    con.commit()


def deck(con, nome, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?, 'premodern')", (nome,))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def mundo():
    """Três arquétipos e uma caixa de Premodern (sem ela a regra não corre)."""
    con = base()
    listas(con, SEM_REGRA, 9, "gro")
    listas(con, ANJO, 7, "anjo")
    listas(con, TOG, 6, "tog")
    analysis.rebuild_archetypes(con, "premodern")
    analysis.rebuild_roles(con, "premodern")
    con.commit()
    deck(con, "Psychatog (consenso)", TOG)
    slots = [{"slot": "premodern-tog", "nome": "Psychatog", "formato": "premodern",
              "fonte": "deck", "ref": "Psychatog (consenso)",
              "balde": "Premodern (geral)", "estado": "permanente",
              "prioridade": 1}]
    return con, slots


def limpar_registo():
    p = arquetipos.ficheiro()
    if p.exists():
        p.unlink()


def por_nome(pm):
    return {c["nome"]: c for c in pm["todos"]}


# ---------------------------------------------------------------------------
def caso_o_id_sai_do_nucleo_e_aguenta_uma_carta_trocada():
    """O `id` é do CONTEÚDO, e herda-se quando o núcleo mexe pouco.

    O hash sozinho só resolveria o caso em que nada muda — que é precisamente o
    caso que não dá problema. É a herança por semelhança (≥ 70 %) que faz o `id`
    aguentar a carta que entra e sai da lista de consenso todas as semanas.
    """
    doze = [f"Carta {i:02d}" for i in range(12)]
    assert arquetipos.nucleo(doze + ["Carta 99"]) == sorted(doze), "corta no tecto"
    # As básicas nunca entram: estão em toda a gente e não distinguem nada.
    assert "Island" not in arquetipos.nucleo(["Island"] + doze)
    # E a ordem de entrada não muda o `id`: quem ordena é o núcleo, não a
    # heurística de distintividade (que muda de corrida para corrida).
    assert (arquetipos.identidade("premodern", arquetipos.nucleo(doze))
            == arquetipos.identidade("premodern",
                                     arquetipos.nucleo(list(reversed(doze)))))

    r = arquetipos.Registo()
    a = r.resolver("premodern", arquetipos.nucleo(doze), "Simic Carta 00")
    assert a["novo"] and not a["herdado"]

    # Amanhã: uma carta trocada, e o rótulo do clustering mudou.
    trocado = arquetipos.nucleo(doze[:-1] + ["Carta 50"])
    b = arquetipos.Registo(r.dados()).resolver("premodern", trocado,
                                               "Simic Carta 50")
    assert b["id"] == a["id"], (a, b)
    assert b["herdado"] and b["semelhanca"] >= 0.9
    assert b["nome"] == "Simic Carta 00", "o nome de ontem é que vale"
    print("o id sai do núcleo, aguenta uma carta trocada e traz o nome de ontem")

    # Mas um baralho DIFERENTE não herda: com 5 de 12 trocadas fica em 58 %.
    outro = arquetipos.nucleo(doze[:7] + [f"Nova {i}" for i in range(5)])
    c = arquetipos.Registo(r.dados()).resolver("premodern", outro, "Outra Coisa")
    assert c["id"] != a["id"] and c["novo"], c
    print("e um baralho diferente (58% em comum) fica com identidade própria")

    # Dois formatos com o mesmo núcleo são duas decisões diferentes: um Doomsday
    # de Legacy e um de Premodern não podem partilhar a recusa.
    leg = arquetipos.Registo(r.dados()).resolver("legacy",
                                                 arquetipos.nucleo(doze), "X")
    assert leg["id"] != a["id"], "o formato entra no hash"
    print("o mesmo núcleo em dois formatos são dois arquétipos")


def caso_um_punhado_de_cartas_nao_e_uma_identidade():
    """O `NUCLEO_MIN` estava escrito e documentado — e nao estava a ser aplicado.

    Viu-se na primeira corrida a serio: o registo publicado ficou com entradas de
    DUAS e tres cartas (um *"Mono-Azul Frogmite"* de 2), porque a distintividade
    do `card_roles` as vezes so devolve um punhado. Dois baralhos diferentes que
    partilhassem essas duas cartas passavam a ser o mesmo arquetipo — e um `id`
    que confunde dois decks e pior do que um `id` que muda, porque leva a recusa
    de um a apagar a sugestao do outro.
    """
    poucas = ["Carta A", "Carta B"]
    lista = sorted(f"Enchimento {i:02d}" for i in range(20))
    assert arquetipos.nucleo(poucas) == sorted(poucas), "sem `resto`, fica curto"
    cheio = arquetipos.nucleo(poucas, resto=lista)
    assert len(cheio) == arquetipos.NUCLEO_MAX, cheio
    assert set(poucas) <= set(cheio), "as distintivas ficam todas"

    # Quem ja tem o minimo NAO se enche: o `resto` e um remendo, nao uma fonte —
    # senao o nucleo passava a depender da lista inteira, que muda todos os dias.
    oito = [f"Carta {i}" for i in range(arquetipos.NUCLEO_MIN)]
    assert arquetipos.nucleo(oito, resto=lista) == sorted(oito)

    # E o `resto` nao traz basicas nem repetidos.
    assert arquetipos.nucleo(["Ilha"], resto=["Island", "Ilha", "Bosque"]) == \
        sorted(["Ilha", "Bosque"])
    print("um nucleo curto completa-se pela lista de consenso, ate ao minimo")


def caso_dois_clusters_nao_herdam_a_mesma_identidade():
    """Dois clusters de hoje não podem herdar a MESMA entrada de ontem — senão o
    segundo roubava a identidade do primeiro e as duas linhas da página
    apareciam com o mesmo nome (e a mesma recusa)."""
    doze = [f"Carta {i:02d}" for i in range(12)]
    ontem = arquetipos.Registo()
    velho = ontem.resolver("premodern", arquetipos.nucleo(doze), "Um")

    hoje = arquetipos.Registo(ontem.dados())
    a = hoje.resolver("premodern", arquetipos.nucleo(doze[:-1] + ["Carta 50"]),
                      "Cluster A")
    b = hoje.resolver("premodern", arquetipos.nucleo(doze[:-2] + ["Carta 51",
                                                                  "Carta 52"]),
                      "Cluster B")
    assert a["id"] == velho["id"] and a["herdado"], a
    assert b["id"] != a["id"] and b["novo"], (a, b)
    print("dois clusters parecidos não ficam com a mesma identidade na mesma corrida")


def caso_o_registo_grava_e_protege_o_que_o_config_refere():
    """O registo é um ficheiro: sem gravar, a identidade durava um processo.

    E a poda nunca apaga um arquétipo que o config refere — apagar a entrada de
    uma recusa fazia-a deixar de bater, que é o defeito que isto vem corrigir.
    """
    p = _TMP / "reg.json"
    r = arquetipos.Registo(caminho=p)
    ident = r.resolver("premodern", ["A", "B", "C"], "Um")["id"]
    assert r.gravar() == p and p.exists()
    assert r.gravar() is None, "sem mudanças não se reescreve"
    lido = arquetipos.Registo.carregar(p)
    assert lido.nome_de(ident) == "Um"

    # Um ficheiro estragado não pára a corrida: começa-se do zero.
    mau = _TMP / "mau.json"
    mau.write_text("{isto não é json", encoding="utf-8")
    assert arquetipos.Registo.carregar(mau).arquetipos == {}

    velho = arquetipos.Registo({"arquetipos": {
        "aaa": {"formato": "premodern", "nome": "Antigo", "nucleo": ["A"],
                "ultima": "2020-01-01"},
        "bbb": {"formato": "premodern", "nome": "Recusado", "nucleo": ["B"],
                "ultima": "2020-01-01"}}})
    assert velho.podar(dias=365, proteger=["bbb"]) == ["aaa"]
    assert set(velho.arquetipos) == {"bbb"}
    print("o registo grava, sobrevive a um ficheiro estragado, e a poda respeita "
          "o que o config refere")


def caso_o_registo_fica_ao_lado_da_base_e_nao_na_home():
    """O ficheiro tem de cair no `data/` do repositório — senão não é publicado.

    Neste PC o `MTGVAULT_HOME` **não está definido**; só o `MTGVAULT_DB`, que
    aponta para o `data/` do repositório. Pelo `db.ROOT` o registo ia parar a
    `~/mtgvault`: o `git add data/arquetipos.json` do `daily.yml` não encontrava
    nada, o registo nunca era publicado e os nomes voltavam a mudar de um dia
    para o outro — sem um único erro. Corre-se num subprocesso porque o `db`
    fixa os caminhos no momento do import.
    """
    import subprocess
    casa, base = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
    guiao = ("import mtgvault.db as db\n"
             "from mtgvault import arquetipos, loadout\n"
             "print(arquetipos.ficheiro())\nprint(loadout.ficheiro_vendas())\n")
    for amb, esperado in (({"MTGVAULT_DB": str(base / "vault.db"),
                            "MTGVAULT_HOME": str(casa)}, base),
                          # E sem `MTGVAULT_DB` continua a dar o que sempre deu.
                          ({"MTGVAULT_HOME": str(casa)}, casa)):
        env = {k: v for k, v in os.environ.items()
               if k not in ("MTGVAULT_DB", "MTGVAULT_HOME")}
        env.update(amb, PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-c", guiao], env=env, timeout=120,
                           capture_output=True, text=True, encoding="utf-8",
                           cwd=str(Path(__file__).resolve().parents[1]))
        assert p.returncode == 0, p.stderr
        for linha in p.stdout.strip().splitlines():
            assert Path(linha).parent == esperado, (linha, esperado, amb)
    print("o registo (e o vendas.csv) ficam ao lado da base, não na home")


def caso_gravar_o_registo_e_atomico():
    """Duas escritas ao mesmo tempo nao podem apagar os nomes todos.

    Aconteceu na primeira corrida a serio: o `daily` e o `webapp.py` (que fica de
    pe o dia todo, servido pela tarefa `mtgvault-serve`) escrevem os dois este
    ficheiro, e **24 arquetipos passaram a 7**. Com um `write_text` cru o
    ficheiro fica truncado entre o `open` e o `write`; quem o apanhasse assim lia
    um JSON invalido, o `carregar` respondia com um registo VAZIO e a gravacao
    seguinte apagava os nomes todos. Nada disto da erro -- e o padrao do
    `event_tier`, sobre a coisa que este modulo existe para nao perder.
    """
    p = _TMP / "atomico.json"
    r = arquetipos.Registo(caminho=p)
    for i in range(30):
        r.resolver("premodern", [f"Carta {i}-{j}" for j in range(9)], f"Deck {i}")
    r.gravar()

    # NUNCA se ve o ficheiro a meio: a escrita vai a um temporario e so depois e
    # que o `os.replace` o poe no lugar, que e uma operacao so.
    ficheiros = sorted(x.name for x in p.parent.iterdir()
                       if x.name.startswith("atomico"))
    assert ficheiros == ["atomico.json"], f"ficou lixo: {ficheiros}"
    assert len(json.loads(p.read_text(encoding="utf-8"))["arquetipos"]) == 30

    # E um ficheiro estragado nao desaparece sem deixar rasto: guarda-se ao lado
    # antes de se comecar do zero, senao a unica prova do que aconteceu ia-se.
    mau = _TMP / "estragado.json"
    mau.write_text('{"arquetipos": {"aaa": ', encoding="utf-8")
    assert arquetipos.Registo.carregar(mau).arquetipos == {}
    assert not mau.exists(), "o estragado sai da frente"
    guardado = [x for x in _TMP.iterdir() if x.name.startswith("estragado-mau-")]
    assert len(guardado) == 1, [x.name for x in _TMP.iterdir()]
    print("a gravacao do registo e atomica, e um ficheiro estragado fica guardado")


def caso_nomes_conhecidos_por_regra():
    """Os clássicos do formato ganham nome por REGRA — e nomear não é ser combo.

    Sem a chave `combo: false`, acrescentar o Landstill à lista para lhe dar um
    nome estável punha-o a disputar o top-5 de combo com o Stiflenought: dar nome
    e dizer que é combo são duas decisões diferentes.
    """
    cfg()
    def nome(cartas):
        r = premodern.classificar_regra(set(cartas))
        return (r or {}).get("nome"), premodern.e_combo(r)

    assert nome(["Psychatog", "Circular Logic"]) == ("Psychatog", False)
    assert nome(["Standstill", "Mishra's Factory"]) == ("Landstill", False)
    assert nome(["Standstill"]) == (None, False), "Landstill precisa das duas"
    assert nome(["The Rack", "Duress"]) == ("The Rack", False)
    assert nome(["Exalted Angel"]) == ("Exalted Angel", False)
    assert nome(["Graveborn Muse"]) == ("Graveborn Muse", False)
    assert nome(["Goblin Lackey"]) == ("Goblins", False)
    # A ORDEM continua a mandar: o Pyrostatic Pillar joga Fireblast e, escrito
    # depois do Sligh, chamava-se Sligh.
    assert nome(["Fireblast"]) == ("Sligh", False)
    assert nome(["Pyrostatic Pillar", "Fireblast"]) == ("Pyrostatic Pillar", False)
    # E as de combo continuam a ser combo, com o grau.
    assert nome(["Stasis"]) == ("Stasis", True)
    assert premodern.classificar({"Stasis"}) == ("Stasis", "prisao")
    # O `classificar` (que é sobre COMBO) não passa a dizer que os Goblins são
    # combo só porque agora há uma regra que lhes dá nome.
    assert premodern.classificar({"Goblin Lackey"}) == (None, None)
    print("os clássicos ganham nome por regra, e nomear não é ser combo")


def caso_as_regras_do_codigo_estao_TAMBEM_no_config():
    """Uma regra acrescentada só ao `COMBO_DEFAULT` fica MORTA, e sem erro.

    O `combo_regras()` devolve a lista do `colecao_config.json` **em vez** da do
    código, não a par dela — e o config dele já tinha 16 regras. As oito regras
    de nome novas ficaram escritas no `COMBO_DEFAULT`, os testes passavam
    (constroem o seu próprio config) e na base a sério não nomeavam nada: o
    Sligh continuava a chamar-se *"Mono-Vermelho Bloodstained Mire"*. É o padrão
    do `event_tier` outra vez — o passo corre, ninguém dá erro, a resposta é que
    está errada.

    Não se exige a lista inteira igual (ele pode acrescentar regras ao config,
    e acrescenta): exige-se que nenhum NOME do código falte lá.
    """
    real = json.loads((Path(__file__).resolve().parents[1] /
                       "colecao_config.json").read_text(encoding="utf-8"))
    no_cfg = {r["nome"] for r in
              (real.get("premodern") or {}).get("combo_arquetipos", [])}
    faltam = [r["nome"] for r in premodern.COMBO_DEFAULT
              if r["nome"] not in no_cfg]
    assert not faltam, (
        f"regras que só existem no código e por isso não correm: {faltam}")
    # E as que só NOMEIAM têm de estar no FIM: a primeira que bate ganha, e um
    # deck que também é combo tem de ficar com o nome do combo (as listas de UW
    # Replenish jogam Exalted Angel).
    ordem = [bool(r.get("combo", True)) for r in
             (real.get("premodern") or {}).get("combo_arquetipos", [])]
    assert ordem == sorted(ordem, reverse=True), \
        "as regras `combo: false` têm de vir depois das de combo"
    print(f"as {len(premodern.COMBO_DEFAULT)} regras do código estão no config, "
          f"e as que só nomeiam vêm no fim")


def caso_o_nome_leva_a_cor_quando_o_nome_proprio_nao_a_implica():
    """*"A cor entra só quando o nome próprio não a implica."*

    Um Psychatog é Dimir por definição; um Exalted Angel não diz cor nenhuma.
    Calcular a cor em vez de a escrever na regra evita chamar *"Orzhov"* a um
    Exalted Angel mono-branco.
    """
    cfg()
    limpar_registo()
    con, slots = mundo()
    pm = loadout.report(con, slots)["premodern"]
    nomes = {c["nome"] for c in pm["todos"]}
    assert "Orzhov Exalted Angel" in nomes, nomes
    assert "Psychatog" in nomes, "o nome próprio já diz a cor"
    print("o nome leva a cor quando a regra a pede: Orzhov Exalted Angel")


def caso_uma_recusa_sobrevive_a_mudanca_de_rotulo():
    """O caso que motivou tudo isto, ponta a ponta.

    O arquétipo sem regra fica com o rótulo do clustering. Amanhã o clustering
    chama-lhe outra coisa — e a recusa de hoje tem de continuar a valer. Mostra-se
    também o defeito: com a forma antiga (chave = nome) ela deixa de bater.
    """
    cfg()
    limpar_registo()
    con, slots = mundo()
    for nm, q in SEM_REGRA:                 # tem o deck inteiro, e não é caixa
        add(con, nm, q)
    pm = loadout.report(con, slots)["premodern"]
    alvo = next(c for c in pm["todos"] if not c["combo"] and "Quirion" in
                str(c["nucleo"]))
    ident, nome1 = alvo["id"], alvo["nome"]
    assert ident and alvo["estado"] == "sugerida", (alvo["estado"], alvo["pct"])
    assert arquetipos.ficheiro().exists(), "o registo ficou gravado"
    registo_de_ontem = arquetipos.ficheiro().read_text(encoding="utf-8")

    # Amanhã: o clustering troca o rótulo (é o que ele faz — ver o cabeçalho).
    original = premodern._nome_do_cluster
    premodern._nome_do_cluster = lambda *a, **k: "Simic Outro Rótulo"
    try:
        # (a) A forma ANTIGA, com a chave a ser o nome, e sem o registo a segurar
        #     o nome: a recusa deixa de bater e a sugestão volta sozinha.
        limpar_registo()
        cfg(sugestoes_recusadas={nome1: "2026-09-08"})
        pm_a = loadout.report(con, slots)["premodern"]
        c_a = next(c for c in pm_a["todos"] if c["id"] == ident)
        assert c_a["nome"] == "Simic Outro Rótulo", c_a["nome"]
        assert c_a["estado"] == "sugerida", "o DEFEITO: a recusa deixou de bater"

        # (b) A forma NOVA: a chave é o `id`, que vem do núcleo e não do rótulo.
        limpar_registo()
        cfg(sugestoes_recusadas={ident: {"nome": nome1, "em": "2026-09-08"}})
        pm_b = loadout.report(con, slots)["premodern"]
        c_b = next(c for c in pm_b["todos"] if c["id"] == ident)
        assert c_b["estado"] == "recusada", c_b["estado"]
        assert c_b["recusada_em"] == "2026-09-08"
        assert not loadout.report(con, slots)["reservadas"], \
            "recusada: as cartas dela libertam-se para a venda"

        # (c) E com o REGISTO de ontem em pé o nome também não muda: a corrida
        #     de ontem deixou-o escrito, e é ele que vale contra o rótulo de
        #     hoje. (As duas alíneas de cima apagaram-no de propósito, para o
        #     rótulo novo poder aparecer.)
        arquetipos.ficheiro().write_text(registo_de_ontem, encoding="utf-8")
        cfg()
        pm_c = loadout.report(con, slots)["premodern"]
        c_c = next(c for c in pm_c["todos"] if c["id"] == ident)
        assert c_c["nome"] == nome1, (c_c["nome"], nome1)
    finally:
        premodern._nome_do_cluster = original
    print(f'a recusa de "{nome1}" sobrevive à mudança de rótulo (pelo id), e o '
          f'registo mantém o nome')


def caso_a_caixa_reconhece_se_pelo_id():
    """Uma caixa criada a partir de uma sugestão reconhece-se pelo `id`.

    Era pelo NOME: a caixa nascia com um rótulo e, no dia em que o clustering
    trocasse, a sugestão reaparecia ao lado da caixa que ela própria criou.
    """
    cfg()
    limpar_registo()
    con, slots = mundo()
    for nm, q in SEM_REGRA:
        add(con, nm, q)
    pm = loadout.report(con, slots)["premodern"]
    alvo = next(c for c in pm["todos"] if not c["combo"] and "Quirion" in
                str(c["nucleo"]))
    # A caixa que o «vou montar este» cria: nome de ontem, `arquetipo` = o id.
    nova = {"slot": "premodern-nova", "nome": "Um Nome Qualquer",
            "formato": "premodern", "fonte": "deck", "ref": None,
            "balde": "Premodern (geral)", "estado": "permanente",
            "prioridade": 2, "arquetipo": alvo["id"]}
    pm2 = loadout.report(con, slots + [nova])["premodern"]
    c2 = next(c for c in pm2["todos"] if c["id"] == alvo["id"])
    assert c2["estado"] == "caixa", c2["estado"]
    assert c2["caixa_nome"] == "Um Nome Qualquer"
    print("a caixa reconhece a sugestão pelo id, mesmo com o nome trocado")


def caso_os_botoes_levam_o_id():
    """O `id` tem de chegar ao BOTÃO — nas duas páginas onde ele decide.

    Se ficasse só no Python, o servidor continuava a receber apenas o nome e a
    guardar a recusa por nome: o motor estava certo e o vault errado na mesma.
    """
    import metagame
    limpar_registo()
    con, slots = mundo()
    # As páginas lêem as caixas do CONFIG (não recebem `slots` à mão como o
    # motor): sem elas lá, a secção do Premodern nem existe.
    cfg(caixas=slots)
    for nm, q in SEM_REGRA:
        add(con, nm, q)
    rep = loadout.report(con, slots)
    alvo = next(c for c in rep["premodern"]["todos"] if c["estado"] == "sugerida")

    ed = metagame.html_page(con, editable=True)
    assert f'data-id="{alvo["id"]}"' in ed, "o metagame não leva o id no botão"
    assert "data-act=" not in metagame.html_page(con), \
        "o site publicado não tem botões (nem ids neles)"

    # E a `deckboxes`, que é JSON + JavaScript: aqui o que interessa é o que o
    # browser DESENHA — o payload pode ter o `id` e o botão não o levar.
    import deckboxes
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    out.write_text(deckboxes.html_page(con, editable=True, rep=rep),
                   encoding="utf-8")
    abas = _abas_desenhadas(out)
    if abas is None:
        print("botões: metagame ok; deckboxes sem `node`, saltado")
        return
    s = abas["sugestoes"]
    assert f'data-id="{alvo["id"]}"' in s, s[:600]
    assert 'data-act="pm-recusar"' in s and 'data-act="pm-montar"' in s
    print("o id vai no botão das duas páginas, e o publicado não tem botões")


def _abas_desenhadas(pagina):
    """`{aba: HTML}` — o que o browser mostraria. `None` sem `node`."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        return None
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_migrar_config_passa_as_chaves_para_id():
    """As recusas e as escolhas antigas passam para `id`, com o nome ao lado.

    O que não aparecer no mapa do dia fica como está: um arquétipo volta ao
    metagame daqui a um mês, e apagar-lhe a recusa era decidir por ele.
    """
    cands = [{"nome": "Dimir Psychatog", "id": "aaaaaaaaaa"},
             {"nome": "Landstill", "id": "bbbbbbbbbb"}]
    mapa = premodern.mapa_de_ids(cands)
    cfg_v = {"premodern": {"sugestoes_recusadas": {
                 "Dimir Psychatog": "2026-09-01",
                 "Um Que Já Não Existe": "2026-08-01"}},
             "listas_escolhidas": {"premodern-landstill": {
                 "nome": "Landstill", "archetype_id": 7}}}
    _novo, n = premodern.migrar_config(cfg_v, mapa)
    assert n == 2, n
    fora = cfg_v["premodern"]["sugestoes_recusadas"]
    assert fora["aaaaaaaaaa"] == {"nome": "Dimir Psychatog", "em": "2026-09-01"}
    assert fora["Um Que Já Não Existe"] == "2026-08-01", "o que não se conhece fica"
    assert cfg_v["listas_escolhidas"]["premodern-landstill"]["id"] == "bbbbbbbbbb"
    # Idempotente: correr outra vez não mexe em nada.
    assert premodern.migrar_config(cfg_v, mapa)[1] == 0
    print("a migração passa as chaves para `id` sem apagar o que não conhece")


def run():
    for fn in (caso_o_id_sai_do_nucleo_e_aguenta_uma_carta_trocada,
               caso_um_punhado_de_cartas_nao_e_uma_identidade,
               caso_dois_clusters_nao_herdam_a_mesma_identidade,
               caso_o_registo_grava_e_protege_o_que_o_config_refere,
               caso_o_registo_fica_ao_lado_da_base_e_nao_na_home,
               caso_gravar_o_registo_e_atomico,
               caso_nomes_conhecidos_por_regra,
               caso_as_regras_do_codigo_estao_TAMBEM_no_config,
               caso_o_nome_leva_a_cor_quando_o_nome_proprio_nao_a_implica,
               caso_uma_recusa_sobrevive_a_mudanca_de_rotulo,
               caso_a_caixa_reconhece_se_pelo_id,
               caso_os_botoes_levam_o_id,
               caso_migrar_config_passa_as_chaves_para_id):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
