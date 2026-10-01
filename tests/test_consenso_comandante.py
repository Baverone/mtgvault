"""CONSENSO POR COMANDANTE (André, 2026-10-01).

*"Quero consenso de Duel Commander do deck dele (comandante CLOUD) sempre
actualizado, da mesma forma que já tem para os arquétipos de Modern."*

O que aqui se tranca — e cada caso tem de CHUMBAR se a tarefa não fizer nada:

  1. **agrupa-se por COMANDANTE e nunca pela etiqueta do agrupamento
     automático.** Duas listas com a MESMA etiqueta e comandantes diferentes são
     dois decks; duas listas com etiquetas diferentes e o mesmo comandante são
     um. É a razão de ser disto: na base de 01/10 havia 870 etiquetas de
     `duel-commander` e 808 sem uma única lista;
  2. o comandante vem do SIDEBOARD da fonte (`commander_fonte = 'sideboard'`) e
     **grava-se** — e a derivação pela ordem das cartas nunca pisa o que a fonte
     já disse, nem faz nada à segunda corrida;
  3. o JSON do consenso é escrito com a data de HOJE, com uma parte por
     comandante;
  4. um comandante **sem listas** não rebenta a página: diz que não sabe;
  5. as percentagens e os papéis (>=90 núcleo, 40–90 flex, <40 raro), com o
     comandante fora da lista das cartas, e o que ele TEM / o que FALTA;
  6. o filtro de eventos é o de sempre (`metagame_fontes`) e é configurável: pôr
     `ligas: false` no Duel Commander tira as ligas do consenso;
  7. PONTA A PONTA: serve-se a pasta por HTTP, abre-se a página com `node` (o
     `fetch` vai MESMO ao servidor) e confirma-se que o consenso aparece depois
     do fetch; sem o JSON, a página diz-lho em português;
  8. a página vai ao `git add` das duas corridas e está na barra lateral.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RAIZ = Path(__file__).resolve().parents[1]
_TMP = Path(tempfile.mkdtemp())

CMD = "Cloud, Midgar Mercenary"
OUTRO = "Tasigur, the Golden Fang"
SEM_LISTAS = "Yoshimaru, Ever Faithful"

CFG = {
    "caixas": [], "regras_por_formato": [], "decks_vigiados": [],
    "premodern_arquetipos_alvo": [], "regras_colecao": {}, "spml_formatos": {},
    "consenso_comandante": {"formato": "duel-commander", "comandante": CMD,
                            "min_listas": 8, "nucleo_pct": 90, "flex_pct": 40,
                            "max_comandantes": 40},
    # A regra do Duel Commander: ligas contam e os presenciais não têm mínimo.
    "metagame_fontes": {"duel-commander": {"tiers": ["Challenge", "Presencial"],
                                           "min_jogadores_presencial": 0,
                                           "ligas": True}},
}


def _config(extra=None):
    """Escreve um config novo e limpa a cache do `sources` (o ficheiro é lido
    por mtime, e dois ficheiros escritos no mesmo segundo podiam colidir)."""
    cfg = json.loads(json.dumps(CFG))
    if extra:
        for k, v in extra.items():
            cfg[k] = v
    p = _TMP / f"cfg-{len(list(_TMP.glob('cfg-*.json')))}.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    os.environ["MTGVAULT_CONFIG"] = str(p)
    from mtgvault import sources
    sources._CFG_CACHE.clear()
    return p


_config()
os.environ["MTGVAULT_HOME"] = str(_TMP)
# O MTGVAULT_DB tem de ser fixado JUNTO com o HOME: os ficheiros que acompanham a
# base saem de `db.pasta_dados()`, que é a pasta da MTGVAULT_DB — e neste PC essa
# variável aponta para o `data/` a sério (ver `test_paginas
# .caso_a_bateria_nao_escreve_no_data_a_serio`).
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import consenso, db, sources  # noqa: E402

import comandantes  # noqa: E402

_ABERTAS = []

# Nome, edição, tipo. As lendárias são os comandantes.
CATALOGO = [
    (CMD, "fin", "Legendary Creature — Human Soldier Mercenary", "W"),
    (OUTRO, "ktk", "Legendary Creature — Human Shaman", "BGU"),
    (SEM_LISTAS, "znc", "Legendary Creature — Dog", "W"),
    ("Swords to Plowshares", "lea", "Instant", "W"),
    ("Path to Exile", "con", "Instant", "W"),
    ("Mother of Runes", "ulg", "Creature — Human Cleric", "W"),
    ("Plains", "unh", "Basic Land — Plains", "W"),
    ("Brainstorm", "ice", "Instant", "U"),
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
             json.dumps({"commander": "legal"})))
    con.commit()
    return con


def _lista(con, con_id, comandante, cartas, *, tier="Presencial",
           source="mtgtop8", jogadores=20, dia=None, fonte="sideboard"):
    """Uma decklist de duel-commander, com o comandante gravado como a fonte o
    daria. As cartas entram pela ordem dada e o comandante vai no FIM, que é
    como o `store_event`/`harvest` as deixam (`main += side`)."""
    dia = dia or date.today().isoformat()
    con.execute("""INSERT INTO decklists (source, source_key, format, event_name,
                   event_date, player, event_tier, event_players, commander,
                   commander_fonte)
                   VALUES (?,?,'duel-commander',?,?,'jogador',?,?,?,?)""",
                (source, con_id, f"{tier} qualquer", dia, tier, jogadores,
                 comandante if fonte else None, fonte or None))
    did = con.execute("SELECT id FROM decklists WHERE source=? AND source_key=?",
                      (source, con_id)).fetchone()["id"]
    for nm, q in list(cartas) + [(comandante, 1)]:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name, quantity,"
                    " board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


# ---------------------------------------------------------------------------
# 1. A identidade é o COMANDANTE
# ---------------------------------------------------------------------------
def caso_agrupa_por_comandante_e_nao_pela_etiqueta():
    """*"Em Duel Commander a identidade do deck é o COMANDANTE, nunca a etiqueta
    do clustering."* Duas listas com a MESMA etiqueta e comandantes diferentes
    são dois decks; duas com etiquetas DIFERENTES e o mesmo comandante são um."""
    con = base()
    # Uma etiqueta só para as duas primeiras, duas etiquetas para as do Cloud.
    for lbl in ("A / B / C", "D / E / F", "G / H / I"):
        con.execute("INSERT INTO archetypes (format, label) VALUES "
                    "('duel-commander', ?)", (lbl,))
    ids = [r["id"] for r in con.execute("SELECT id FROM archetypes ORDER BY id")]
    d1 = _lista(con, "k1", CMD, [("Swords to Plowshares", 1)])
    d2 = _lista(con, "k2", OUTRO, [("Brainstorm", 1)])
    d3 = _lista(con, "k3", CMD, [("Path to Exile", 1)])
    # A MESMA etiqueta para o Cloud e para o Tasigur; outra para a 3.ª lista.
    con.execute("UPDATE decklists SET archetype_id=? WHERE id IN (?,?)",
                (ids[0], d1, d2))
    con.execute("UPDATE decklists SET archetype_id=? WHERE id=?", (ids[1], d3))
    con.commit()

    por = {c["nome"]: c["listas"] for c in consenso.comandantes(con)}
    assert por == {CMD: 2, OUTRO: 1}, por
    # E a etiqueta não entra em sítio nenhum do consenso.
    c = consenso.consenso(con, CMD)
    assert c["listas"] == 2
    assert {x["nm"] for x in c["cartas"]} == {"Swords to Plowshares", "Path to Exile"}
    print("agrupa por comandante: a mesma etiqueta da dois decks, etiquetas "
          "diferentes dao um")


def caso_o_comandante_vem_do_sideboard_da_fonte():
    """O mtgo.com serve o comandante no `sideboard_deck` e o vault funde-o no
    main (é isso que faz o `content_hash` coincidir com o do mtgtop8). O nome
    tem de ser lido ANTES dessa fusão — era aí que a informação se perdia."""
    con = base()
    blob = {"description": "Duel Commander League", "publish_date": date.today().isoformat(),
            "decklists": [{"player": "luffy", "loginid": "1",
                           "main_deck": [{"card_attributes": {"card_name": "Swords to Plowshares"},
                                          "quantity": 1},
                                         {"card_attributes": {"card_name": "Plains"},
                                          "quantity": 98}],
                           "sideboard_deck": [{"card_attributes": {"card_name": CMD},
                                               "quantity": 1}]}]}
    n = sources.store_event(con, blob,
                            "https://www.mtgo.com/decklist/duel-commander-league-2026-10-01")
    assert n == 1, n
    r = con.execute("SELECT commander c, commander_fonte f FROM decklists").fetchone()
    assert (r["c"], r["f"]) == (CMD, "sideboard"), dict(r)
    # E o comandante continua no MAINBOARD (a regra de sempre: conta para as 100).
    boards = {x["board"] for x in con.execute(
        "SELECT board FROM decklist_cards WHERE card_name = ?", (CMD,))}
    assert boards == {"main"}, boards
    # E o .dec do mtgtop8 pelo mesmo caminho: o `SB:` é o comandante.
    from mtgvault import mtgtop8
    dec = f"4 [LEA] Swords to Plowshares\n1 [] Plains\nSB: 1 [FIN] {CMD}\n"
    assert mtgtop8.comandantes_do_dec(dec) == [CMD]
    assert consenso.nome_do_comandante(con, mtgtop8.comandantes_do_dec(dec)) == CMD
    # E o `harvest` passa-o ao `store_decklist` — senão a coluna ficava a NULL
    # nas listas de papel, que são 80 % delas, sem um único erro.
    fonte = (RAIZ / "mtgvault" / "mtgtop8.py").read_text(encoding="utf-8")
    assert "commander=comandante" in fonte
    print("o comandante vem do sideboard da fonte (mtgo e mtgtop8) e fica gravado")


def caso_derivar_nao_pisa_a_fonte_e_e_idempotente():
    """As listas que já cá estavam não têm sideboard nenhum para ler: deriva-se
    pela ORDEM DE INSERÇÃO (o comandante é a última carta, porque o `SB:` vem no
    fim do .dec e o `store_event` faz `main += side`). Mas um palpite **nunca**
    pisa o que a fonte disse, e a segunda corrida não faz nada."""
    con = base()
    _lista(con, "k1", CMD, [("Swords to Plowshares", 1)], fonte="sideboard")
    # Uma lista "antiga": sem comandante marcado.
    did = _lista(con, "k2", OUTRO, [("Brainstorm", 1)], fonte=None)
    assert con.execute("SELECT commander c FROM decklists WHERE id=?",
                       (did,)).fetchone()["c"] is None
    r = consenso.derivar(con)
    assert r["derivadas"] == 1 and r["por_derivar"] == 0, r
    row = con.execute("SELECT commander c, commander_fonte f FROM decklists "
                      "WHERE id=?", (did,)).fetchone()
    assert (row["c"], row["f"]) == (OUTRO, "ordem"), dict(row)
    # A da fonte continua a dizer `sideboard`.
    assert con.execute("SELECT commander_fonte f FROM decklists WHERE source_key='k1'"
                       ).fetchone()["f"] == "sideboard"
    # Idempotente.
    assert consenso.derivar(con)["derivadas"] == 0
    f = consenso.fontes(con)
    assert f == {"total": 2, "sideboard": 1, "ordem": 1, "sem": 0}, f
    print("derivar: usa a ultima carta, nao pisa a fonte, e a 2.a corrida nao faz nada")


# ---------------------------------------------------------------------------
# 2. As percentagens, os papéis e a posse
# ---------------------------------------------------------------------------
def _dez_listas(con):
    """10 listas do Cloud: Swords em 10 (100 %), Path em 5 (50 %), Mother em 2
    (20 %). Mais uma lista de outro comandante, para provar que não se misturam."""
    for i in range(10):
        cartas = [("Swords to Plowshares", 1)]
        if i < 5:
            cartas.append(("Path to Exile", 1))
        if i < 2:
            cartas.append(("Mother of Runes", 1))
        _lista(con, f"c{i}", CMD, cartas)
    _lista(con, "x1", OUTRO, [("Brainstorm", 1)])
    return con


def caso_as_percentagens_e_os_papeis():
    con = _dez_listas(base())
    c = consenso.consenso(con, CMD)
    assert c["listas"] == 10 and c["suficiente"] is True, c["listas"]
    por = {x["nm"]: x for x in c["cartas"]}
    assert CMD not in por, "o comandante não é uma escolha do deck: vai à parte"
    assert (por["Swords to Plowshares"]["pct"], por["Swords to Plowshares"]["papel"]) == (100.0, "nucleo")
    assert (por["Path to Exile"]["pct"], por["Path to Exile"]["papel"]) == (50.0, "flex")
    assert (por["Mother of Runes"]["pct"], por["Mother of Runes"]["papel"]) == (20.0, "raro")
    assert "Brainstorm" not in por, "uma lista de outro comandante entrou no consenso"
    assert c["papeis"] == {"nucleo": 1, "flex": 1, "raro": 1}, c["papeis"]
    # Singleton: a moda de cópias é 1, e di-lo em vez de o esconder.
    assert all(x["copias"] == 1 for x in c["cartas"])
    # A ordem é por percentagem, de cima para baixo.
    assert [x["nm"] for x in c["cartas"]][0] == "Swords to Plowshares"
    print("percentagens e papeis: 100 % nucleo, 50 % flex, 20 % raro, comandante a parte")


def caso_poucas_listas_dizem_que_sao_poucas():
    con = base()
    for i in range(3):
        _lista(con, f"p{i}", CMD, [("Swords to Plowshares", 1)])
    c = consenso.consenso(con, CMD)
    assert c["listas"] == 3 and c["suficiente"] is False and c["min_listas"] == 8
    assert c["cartas"], "as cartas continuam à vista — só se diz que são poucas"
    print("abaixo do minimo a pagina diz que sao poucas listas, em vez de calar")


def caso_a_posse_e_o_que_falta_saem_da_coleccao():
    con = _dez_listas(base())
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name=?",
                      ("Swords to Plowshares",)).fetchone()[0]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,2,'nonfoil','en','player',?)""",
                (sid, sub))
    con.commit()
    idx, partes = comandantes.dados(con)
    por = {c["nm"]: c for c in partes["Cloud_Midgar_Mercenary"]["cartas"]}
    assert (por["Swords to Plowshares"]["tenho"], por["Swords to Plowshares"]["falta"]) == (2, 0)
    assert (por["Path to Exile"]["tenho"], por["Path to Exile"]["falta"]) == (0, 1)
    assert por["Swords to Plowshares"]["sid"], "cada carta leva a impressão para a imagem"
    print("cada carta do consenso diz quantas ele tem e quantas faltam")


# ---------------------------------------------------------------------------
# 3. O filtro de eventos — medido e configurável
# ---------------------------------------------------------------------------
def caso_o_filtro_de_eventos_e_o_de_sempre_e_configuravel():
    """A regra do Modern (sem ligas, presencial com 64+) não deixava NADA em Duel
    Commander: medido a 2026-10-01, 48 listas no formato inteiro e **zero** do
    Cloud, contra 652/41 com a regra dele. Por isso o filtro é o
    `sources.lista_conta` de sempre — e tem de obedecer ao `metagame_fontes`."""
    con = base()
    for i in range(4):          # 4 ligas
        _lista(con, f"l{i}", CMD, [("Swords to Plowshares", 1)],
               tier="League", source="mtgo", jogadores=None)
    for i in range(3):          # 3 presenciais pequenos
        _lista(con, f"s{i}", CMD, [("Swords to Plowshares", 1)],
               tier="Presencial", jogadores=20)
    assert consenso.consenso(con, CMD)["listas"] == 7

    _config({"metagame_fontes": {"duel-commander": {
        "tiers": ["Challenge", "Presencial"], "min_jogadores_presencial": 0,
        "ligas": False}}})
    assert consenso.consenso(con, CMD)["listas"] == 3, "as ligas continuaram a contar"

    _config({"metagame_fontes": {"duel-commander": {
        "tiers": ["Challenge", "Presencial"], "min_jogadores_presencial": 64,
        "ligas": False}}})
    assert consenso.consenso(con, CMD)["listas"] == 0, \
        "a regra do Modern tinha de deixar isto a zero — é a medição que a recusou"
    _config()
    assert consenso.consenso(con, CMD)["listas"] == 7
    print("o filtro de eventos e o metagame_fontes de sempre, e obedece ao config")


# ---------------------------------------------------------------------------
# 4. A página
# ---------------------------------------------------------------------------
_SITE = None


def site():
    global _SITE
    if _SITE is None:
        _config()
        con = _dez_listas(base())
        d = Path(tempfile.mkdtemp())
        comandantes.build(con, d / "comandantes.html")
        _SITE = (d, con)
    return _SITE


def caso_o_json_e_de_hoje_com_uma_parte_por_comandante():
    d, _con = site()
    idx = json.loads((d / "data" / "paginas" / "comandantes.json")
                     .read_text(encoding="utf-8"))
    assert idx["_gerado_em"].startswith(date.today().isoformat()), idx["_gerado_em"]
    assert sorted(idx["_partes"]) == ["Cloud_Midgar_Mercenary",
                                      "Tasigur_the_Golden_Fang"], idx["_partes"]
    for p in idx["_partes"]:
        f = d / "data" / "paginas" / "comandantes" / f"{p}.json"
        assert f.is_file(), p
        json.loads(f.read_text(encoding="utf-8"))
    assert idx["comandante"] == CMD and idx["comandantes"][0]["listas"] == 10
    # A casca não leva os dados todos — só o comandante que abre.
    casca = (d / "comandantes.html").read_text(encoding="utf-8")
    assert '<script id="dados"' not in casca
    assert "carregaDados(" in casca and "erroDados(" in casca
    assert OUTRO not in casca, "a casca não pode trazer os dados dos outros"
    print("indice + uma parte por comandante, com a data de hoje; a casca sem dados")


def caso_um_comandante_sem_listas_nao_rebenta():
    """O que ele escolheu pode não ter listas nenhumas (um comandante novo, uma
    janela vazia). Isso é uma RESPOSTA — *"ainda não sei"* — e não um erro."""
    _config({"consenso_comandante": dict(CFG["consenso_comandante"],
                                         comandante=SEM_LISTAS)})
    con = _dez_listas(base())
    d = Path(tempfile.mkdtemp())
    comandantes.build(con, d / "comandantes.html")
    idx = json.loads((d / "data" / "paginas" / "comandantes.json")
                     .read_text(encoding="utf-8"))
    assert idx["comandante"] == SEM_LISTAS
    parte = json.loads((d / "data" / "paginas" / "comandantes"
                        / "Yoshimaru_Ever_Faithful.json").read_text(encoding="utf-8"))
    assert parte["listas"] == 0 and parte["cartas"] == [] and parte["sid"]
    assert parte["suficiente"] is False and parte["papeis"] == {
        "nucleo": 0, "flex": 0, "raro": 0}
    # E o selector continua a levar os que TÊM listas.
    assert [c["nome"] for c in idx["comandantes"]][:2] == [SEM_LISTAS, CMD]
    # Um comandante que nem no catálogo existe também não rebenta.
    _config({"consenso_comandante": dict(CFG["consenso_comandante"],
                                         comandante="Carta Que Nao Existe")})
    comandantes.build(con, d / "comandantes.html")
    _config()
    print("um comandante sem listas da uma resposta em vez de rebentar")


class _Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _servir(pasta):
    s = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Silencioso, directory=str(pasta)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}"


def _abrir(url):
    saida = Path(tempfile.mkdtemp()) / "dom.json"
    p = subprocess.run(["node", str(Path(__file__).with_name("abrir_pagina.js")),
                        url, str(saida)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(saida.read_text(encoding="utf-8"))


def caso_ponta_a_ponta_servida_por_http():
    if not shutil.which("node"):
        print("ponta a ponta: sem `node`, saltado")
        return
    d, _con = site()
    srv, url = _servir(d)
    try:
        dom = _abrir(f"{url}/comandantes.html")
        vista = dom["#vista"]
        assert CMD in vista, vista[:500]
        assert "Swords to Plowshares" in vista and "100 %" in vista, vista[:500]
        assert "Núcleo" in vista and "Flex" in vista and "Raro" in vista, vista[:500]
        assert "carregando" not in vista and "erro-dados" not in vista, vista[:500]
        # O selector levou os dois comandantes, e abriu no dele.
        sel = dom["#cmd"]
        assert CMD in sel and OUTRO in sel, sel[:300]
        assert "sideboard" in dom["#chips"], dom["#chips"]
        print("ponta a ponta: o consenso do Cloud aparece depois do fetch")

        # SEM os dados: a mensagem em português, não um ecrã em branco.
        shutil.rmtree(d / "data" / "paginas" / "comandantes")
        (d / "data" / "paginas" / "comandantes.json").unlink()
        dom = _abrir(f"{url}/comandantes.html")
        assert "Não consegui carregar" in dom["#vista"] and "404" in dom["#vista"], \
            dom["#vista"]
        print("sem o JSON, a pagina diz-lhe em portugues o que falhou")
    finally:
        srv.shutdown()
        global _SITE
        _SITE = None


def caso_a_pagina_e_publicada_e_esta_na_barra():
    """Uma página que ninguém faz `git add` fica congelada no site — e o
    `deckboxes.html` esteve semanas só na lista do workflow, nunca publicado
    pelo PC. As duas listas têm de a levar."""
    from mtgvault import site_shell as shell
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert "comandantes.html" in linha.split(), \
        "comandantes.html não vai ao `git add` do daily.yml"
    tarefa = Path(r"C:\Users\Catarina\Desktop\ai-pc\tasks\mtgvault-daily\run.py")
    if tarefa.exists():
        assert "comandantes.html" in tarefa.read_text(encoding="utf-8"), \
            "a tarefa mtgvault-daily do ai-pc não publica a página"
    assert "comandantes.html" in shell.PAGINAS_DO_MENU
    assert 'href="comandantes.html"' in shell.barra("comandantes.html")
    # E o passo corre no daily.
    assert '"consenso-comandante"' in (RAIZ / "daily.py").read_text(encoding="utf-8")
    print("a pagina vai ao git add das duas corridas, esta na barra e corre no daily")


def caso_a_coluna_existe_nos_tres_sitios():
    """Uma coluna nova entra no `schema.sql`, no `db._migrate()` e em quem a
    escreve. Já custou caro uma vez (o `event_tier`, 2026-08-03): a coluna existia
    só na base dele, nada a preenchia, o metagame vinha vazio e o daily dizia
    `[ok]`. Aqui prova-se nos três, e numa base JÁ CRIADA (é o `_migrate` que a
    põe lá — o `schema.sql` corre inteiro antes dele)."""
    esquema = (RAIZ / "mtgvault" / "schema.sql").read_text(encoding="utf-8")
    assert "    commander       TEXT," in esquema
    # E o ÍNDICE não pode estar no `schema.sql`: esse ficheiro corre inteiro antes
    # do `_migrate`, e numa base já criada a coluna ainda não existe — rebentava
    # o `db.init` com "no such column: commander" (aconteceu a 2026-10-01, e é a
    # mesma armadilha do `ix_copies_validado` de 2026-09-09).
    assert not [l for l in esquema.splitlines()
                if "ix_dl_commander" in l and "CREATE INDEX" in l], \
        "o índice do commander voltou ao schema.sql — rebenta o db.init"
    assert "ix_dl_commander" in (RAIZ / "mtgvault" / "db.py").read_text(encoding="utf-8")
    d = Path(tempfile.mkdtemp())
    con = db.connect(d / "v.db", d / "c.db")
    con.executescript((RAIZ / "mtgvault" / "catalog_schema.sql").read_text(encoding="utf-8"))
    con.executescript(esquema
                      .replace("    commander       TEXT,\n", "")
                      .replace("    commander_fonte TEXT,\n", ""))
    cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
    assert "commander" not in cols, "o truque deste teste deixou de funcionar"
    db._migrate(con)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
    assert {"commander", "commander_fonte"} <= cols, sorted(cols)
    # E alguém a ESCREVE (não é uma coluna que ninguém preenche).
    src = (RAIZ / "mtgvault" / "sources.py").read_text(encoding="utf-8")
    assert "commander_fonte" in src and "commander=comandante" in src
    con.close()
    print("a coluna commander existe no schema, na migracao e em quem a escreve")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for f in CASOS:
        f()
    print(f"\n{len(CASOS)} casos ok")
