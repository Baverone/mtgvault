"""O MODO DE EDIÇÃO do núcleo novo, por HTTP (Task 8, 2026-10-28).

O servidor é o `webapp.Handler` a sério, num porto livre, sobre uma base e um
catálogo temporários (nunca os do André: o `MTGVAULT_DB` e o
`MTGVAULT_CATALOG` vão para uma pasta temporária ANTES do import, e o
`webapp.ROOT` também, para nada escrever páginas na árvore de trabalho).

O cenário é o do `test_nucleo_paginas`, em ponto pequeno: um deck sempre
montado (UW Replenish) e dois rotativos (Modern Affinity e Welder Cam) que
partilham a Urza's Saga; a Island tem 15 impressões, para provar que a folha
da carta mostra TODAS (o `scryfall.impressoes` corta em 12 por omissão).

O que não vem do loopback (o telemóvel na rede de casa) entra por um pedido de
mentira (`Pedido`), com o IP `192.168.1.99`: é a única maneira de provar o 403
sem pôr o servidor na rede.
"""
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = _TMP / "cfg.json"


def config(ligado: bool) -> None:
    CFG.write_text(json.dumps({"nucleo": {"ligado": ligado}, "caixas": [],
                               "decks_vigiados": []}, ensure_ascii=False),
                   encoding="utf-8")


config(True)
os.environ["MTGVAULT_CONFIG"] = str(CFG)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")          # ver tests/_bateria.py
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

from mtgvault import db, prices  # noqa: E402
from mtgvault.nucleo import edicao_js, listas, modelo, posse  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

import webapp  # noqa: E402

webapp.ROOT = _TMP

REP = "premodern_replenish"
MOD = "modern_affinity"
LEG = "legacy_welder_cam"
DIA = "2026-10-28"

# (scryfall_id, nome, set, data, finishes)
IMPRESSOES = [
    ("repl-a", "Replenish", "ulg", "1999-02-15", ["nonfoil"]),
    ("opal-a", "Opalescence", "usg", "1998-10-12", ["nonfoil"]),
    ("tm-a", "Thought Monitor", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("saga-a", "Urza's Saga", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("saga-b", "Urza's Saga", "h2r", "2022-03-01", ["foil"]),
    ("weld-a", "Goblin Welder", "ulg", "1999-02-15", ["nonfoil"]),
] + [(f"isl-{i:02d}", "Island", f"s{i:02d}", f"20{i:02d}-01-01", ["nonfoil"])
     for i in range(15)]


def semear():
    con = db.connect()
    db.init(con)
    for i, (sid, nome, sc, data, fins) in enumerate(IMPRESSOES):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital,
               set_type)
               VALUES (?,?,?,?,?,?,'en','rare','Artifact',0,'',?,?,?,0,
               'expansion')""",
            (sid, "or-" + nome, nome, sc, "Set " + sc.upper(), str(i),
             json.dumps(fins), data, 1000 + i))
    con.commit()
    modelo.garantir_decks(con)
    for sid, acab, trend in (("repl-a", "nonfoil", 10.0), ("opal-a", "nonfoil", 5.0),
                             ("tm-a", "nonfoil", 2.0), ("tm-a", "foil", 3.0),
                             ("saga-a", "nonfoil", 30.0), ("saga-a", "foil", 50.0),
                             ("isl-03", "nonfoil", 0.2)):
        prices.write_prices(con, [(sid, "cardmarket", DIA, acab, trend, trend,
                                   trend, None, "EUR")])
    for slug, linhas in (
            (REP, [("main", "Replenish", 4), ("main", "Opalescence", 2),
                   ("side", "Island", 3)]),
            (MOD, [("main", "Thought Monitor", 4), ("main", "Urza's Saga", 4)]),
            (LEG, [("main", "Goblin Welder", 4), ("main", "Urza's Saga", 2)])):
        listas.gravar_versao(con, slug, [Linha(*l) for l in linhas],
                             fonte="teste", origem="andre")
    posse.definir_montado(con, LEG)
    con.commit()
    con.close()


semear()

with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    PORTO = _s.getsockname()[1]
SRV = webapp.ThreadingHTTPServer(("127.0.0.1", PORTO), webapp.Handler)
threading.Thread(target=SRV.serve_forever, daemon=True).start()


def pedir(metodo, caminho, corpo=None, cabecalhos=None, prazo=120):
    """`(código, corpo)` — o corpo em dicionário/lista se for JSON, senão texto.
    Nunca levanta por um código de erro."""
    dados = None if corpo is None else json.dumps(corpo).encode("utf-8")
    h = {"Content-Type": "application/json"} if corpo is not None else {}
    h.update(cabecalhos or {})
    req = urllib.request.Request(f"http://127.0.0.1:{PORTO}{caminho}",
                                 data=dados, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=prazo) as r:
            cod, bruto, tipo = r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        cod, bruto, tipo = e.code, e.read(), e.headers.get("Content-Type", "")
    txt = bruto.decode("utf-8", "replace")
    if "json" in tipo:
        return cod, json.loads(txt)
    return cod, txt


def q(**kw):
    return "?" + urllib.parse.urlencode(kw)


_n = [0]


def novo_id():
    _n[0] += 1
    return f"teste-{_n[0]}"


def ler(sql, args=()):
    con = db.connect()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


class Pedido(webapp.Handler):
    """Um pedido de mentira: o mesmo handler, sem rede por baixo."""

    def __init__(self, path, corpo=None, token=None, ip="192.168.1.99",
                 metodo="POST"):
        self.path = path
        self.client_address = (ip, 5555)
        bruto = json.dumps(corpo).encode("utf-8") if corpo is not None else b""
        self.rfile = io.BytesIO(bruto)
        self.headers = {"Content-Length": str(len(bruto))}
        if token:
            self.headers[webapp.CABECALHO_TOKEN] = token
        self.server = None
        self.codigo, self.corpo = None, ""
        (self.do_POST if metodo == "POST" else self.do_GET)()

    def send_response(self, code, *_a):
        self.codigo = code

    def send_header(self, *_a):
        pass

    def end_headers(self):
        pass

    @property
    def wfile(self):
        self_ = self

        class Escritor:
            def write(self, b):
                self_.corpo = b.decode("utf-8", "replace")
        return Escritor()


# ---------------------------------------------------------------------------
def caso_marca_idempotente():
    """O mesmo `request_id` duas vezes (o telemóvel a repetir um toque que já
    tinha chegado) conta UMA vez; um id novo conta outra."""
    rid = novo_id()
    corpo = {"deck": REP, "nome": "Opalescence", "delta": 1, "request_id": rid}
    c1, j1 = pedir("POST", "/api/n/marca", corpo)
    c2, j2 = pedir("POST", "/api/n/marca", corpo)
    assert (c1, c2) == (200, 200), (c1, j1, c2, j2)
    assert j1["qtd"] == 1 and j2["qtd"] == 1, (j1, j2)
    c3, j3 = pedir("POST", "/api/n/marca", {**corpo, "request_id": novo_id()})
    assert c3 == 200 and j3["qtd"] == 2, j3
    c4, j4 = pedir("POST", "/api/n/marca",
                   {**corpo, "delta": -1, "request_id": novo_id()})
    assert c4 == 200 and j4["qtd"] == 1, j4
    # sem request_id não se marca nada: um retry sem id contava a dobrar
    c5, j5 = pedir("POST", "/api/n/marca", {**corpo, "request_id": ""})
    assert c5 == 409 and "request_id" in j5["erro"], (c5, j5)
    # um nome que não está na lista do deck
    c6, j6 = pedir("POST", "/api/n/marca",
                   {**corpo, "nome": "Goblin Welder", "request_id": novo_id()})
    assert c6 == 409 and "erro" in j6, (c6, j6)
    c7, j7 = pedir("POST", "/api/n/marca",
                   {**corpo, "delta": "dois", "request_id": novo_id()})
    assert c7 == 409, (c7, j7)
    print("marca: o mesmo request_id conta uma vez")


def caso_sem_token_recusa():
    """Da rede de casa sem token: 403, e nada é escrito. Com o token: 200."""
    antes = ler("SELECT COUNT(*) FROM n_posse_log")[0][0]
    corpo = {"deck": REP, "nome": "Replenish", "delta": 1, "request_id": novo_id()}
    p = Pedido("/api/n/marca", corpo)
    assert p.codigo == 403, (p.codigo, p.corpo)
    assert ler("SELECT COUNT(*) FROM n_posse_log")[0][0] == antes
    for caminho, c in (("/api/n/edicao", {"deck": MOD, "nome": "Thought Monitor",
                                          "scryfall_id": "tm-a",
                                          "acabamento": "foil"}),
                       ("/api/n/lista", {"deck": REP, "texto": "4 Replenish",
                                         "fonte": "x"}),
                       ("/api/n/montar", {"deck": MOD}),
                       ("/api/n/a_mais", {"scryfall_id": "tm-a",
                                          "acabamento": "foil", "delta": 1}),
                       ("/api/n/saida", {"id": 1, "destino": "descartar"})):
        p = Pedido(caminho, c)
        assert p.codigo == 403, (caminho, p.codigo, p.corpo)
    p = Pedido("/api/n/marca", corpo, token="errado")
    assert p.codigo == 403, p.codigo
    p = Pedido("/api/n/marca", corpo, token=webapp.token())
    assert p.codigo == 200, (p.codigo, p.corpo)
    assert json.loads(p.corpo)["qtd"] == 1
    print("sem token, da rede de casa: 403 em todos os POST")


def caso_lista_sem_fonte_409():
    for fonte in ("", "   ", None):
        c, j = pedir("POST", "/api/n/lista",
                     {"deck": REP, "texto": "4 Replenish\n4 Opalescence",
                      "fonte": fonte})
        assert c == 409 and j["erro"] == "de onde veio a lista?", (fonte, c, j)
    c, j = pedir("POST", "/api/n/lista", {"deck": REP, "texto": "", "fonte": "x"})
    assert c == 409 and "vazia" in j["erro"], (c, j)
    c, j = pedir("POST", "/api/n/lista",
                 {"deck": "nao_existe", "texto": "4 Replenish", "fonte": "x"})
    assert c == 409 and "deck" in j["erro"], (c, j)
    print("lista sem fonte: 409 «de onde veio a lista?»")


def caso_lista_nome_errado_422_com_nomes():
    v = ler("SELECT COUNT(*) FROM n_versao WHERE slug = ?", (REP,))[0][0]
    c, j = pedir("POST", "/api/n/lista",
                 {"deck": REP, "fonte": "Discord",
                  "texto": "4 Replenish\n2 Opalesence\n1 Islnd\n\nSideboard\n3 Island"})
    assert c == 422, (c, j)
    assert j["nomes"] == ["Opalesence", "Islnd"], j
    assert "Opalesence" in j["erro"], j
    assert ler("SELECT COUNT(*) FROM n_versao WHERE slug = ?", (REP,))[0][0] == v
    print("lista com gralhas: 422 com os nomes, nada gravado")


def caso_lista_grava_e_igual():
    texto = "4 Replenish\n2 Opalescence\n\nSideboard\n2 Island"
    c, j = pedir("POST", "/api/n/lista",
                 {"deck": REP, "texto": texto, "fonte": " https://x.pt/lista "})
    assert c == 200, (c, j)
    assert j["numero"] == 2 and j["saiu"] == [["Island", 1]] and j["entrou"] == [], j
    r = ler("SELECT fonte, origem FROM n_versao WHERE slug = ? AND numero = 2", (REP,))
    assert tuple(r[0]) == ("https://x.pt/lista", "andre"), tuple(r[0])
    c, j = pedir("POST", "/api/n/lista", {"deck": REP, "texto": texto, "fonte": "y"})
    assert c == 200 and j == {"igual": True}, (c, j)
    print("lista: grava a versão com a fonte; a mesma outra vez é «igual»")


def caso_edicoes_todas():
    c, j = pedir("GET", "/api/n/edicoes" + q(nome="Island", deck=REP))
    assert c == 200, (c, j)
    assert len(j) == 15, len(j)
    chaves = {"scryfall_id", "set_code", "set_name", "collector_number",
              "finishes", "imagem", "preco_nonfoil", "preco_foil", "escolhida"}
    assert chaves <= set(j[0]), set(j[0])
    por = {e["scryfall_id"]: e for e in j}
    assert por["isl-03"]["preco_nonfoil"] == 0.2
    assert por["isl-04"]["preco_nonfoil"] is None and por["isl-04"]["preco_foil"] is None
    # a omissão (a normal mais barata com preço) é a escolhida
    assert [e["scryfall_id"] for e in j if e["escolhida"]] == ["isl-03"], j
    assert por["isl-03"]["imagem"].startswith("https://cards.scryfall.io/small/")
    assert por["isl-03"]["finishes"] == ["nonfoil"]
    # sem deck (a busca de Vender): nenhuma escolhida
    c, j = pedir("GET", "/api/n/edicoes" + q(nome="Urza's Saga"))
    assert c == 200 and len(j) == 2 and not any(e["escolhida"] for e in j), j
    saga = {e["scryfall_id"]: e for e in j}
    assert saga["saga-a"]["preco_foil"] == 50.0 and saga["saga-b"]["finishes"] == ["foil"]
    c, j = pedir("GET", "/api/n/edicoes" + q(nome="Não Existe Nada"))
    assert c == 200 and j == [], j
    print("edições: as 15 impressões, com preço ou «sem preço»")


def caso_carta_partilhada():
    c, j = pedir("GET", "/api/n/carta" + q(deck=MOD, nome="Urza's Saga"))
    assert c == 200, (c, j)
    assert j["partilhada"] is True and j["ambito"] == posse.ROT, j
    assert j["usos"] == [{"slug": MOD, "nome": "Affinity", "qtd": 4},
                         {"slug": LEG, "nome": "Welder Cam", "qtd": 2}], j["usos"]
    assert j["precisa"] == 4 and j["pede"] == 4, j
    assert j["scryfall_id"] == "saga-a" and j["acabamento"] == "nonfoil", j
    c, j = pedir("GET", "/api/n/carta" + q(deck=MOD, nome="Thought Monitor"))
    assert c == 200 and j["partilhada"] is False and j["ambito"] == MOD, j
    c, j = pedir("GET", "/api/n/carta" + q(deck=MOD, nome="Replenish"))
    assert c == 409, (c, j)
    print("carta: partilhada · Affinity (4) e Welder Cam (2) → precisas de 4")


def caso_edicao_e_acabamento():
    c, j = pedir("POST", "/api/n/edicao", {"deck": MOD, "nome": "Thought Monitor",
                                           "scryfall_id": "tm-a",
                                           "acabamento": "foil"})
    assert c == 200 and j == {"ok": True}, (c, j)
    assert posse.edicao(_con(), MOD, "Thought Monitor") == ("tm-a", "foil")
    # um foil que não existe nessa edição, e uma edição de outra carta
    c, j = pedir("POST", "/api/n/edicao", {"deck": MOD, "nome": "Urza's Saga",
                                           "scryfall_id": "saga-b",
                                           "acabamento": "nonfoil"})
    assert c == 409, (c, j)
    c, j = pedir("POST", "/api/n/edicao", {"deck": MOD, "nome": "Urza's Saga",
                                           "scryfall_id": "tm-a",
                                           "acabamento": "nonfoil"})
    assert c == 409, (c, j)
    c, j = pedir("GET", "/api/n/edicoes" + q(nome="Thought Monitor", deck=MOD))
    assert [e["escolhida"] for e in j] == [True], j
    print("edição: escolhe-se com o acabamento; um foil que não existe é 409")


_CON = []


def _con():
    if not _CON:
        _CON.append(db.connect())
    _CON[0].rollback()
    return _CON[0]


def caso_montar_sempre_montado_409():
    c, j = pedir("POST", "/api/n/montar", {"deck": REP})
    assert c == 409 and "sempre montado" in j["erro"], (c, j)
    c, j = pedir("GET", "/api/n/movimentos" + q(deck=REP))
    assert c == 409, (c, j)
    # o monte das partilhadas: 2 Urza's Saga marcadas, na caixa do Welder Cam
    rid = novo_id()
    c, j = pedir("POST", "/api/n/marca", {"deck": LEG, "nome": "Urza's Saga",
                                          "delta": 2, "request_id": rid})
    assert c == 200 and j["qtd"] == 2, j
    c, j = pedir("GET", "/api/n/movimentos" + q(deck=MOD))
    assert c == 200, (c, j)
    assert j["montado_agora"] == "Welder Cam", j
    assert j["movimentos"] == [{"nome": "Urza's Saga", "qtd": 2, "de": LEG,
                                "de_nome": "Welder Cam", "para": MOD}], j
    c, j = pedir("POST", "/api/n/montar", {"deck": MOD})
    assert c == 200 and j["movimentos"][0]["qtd"] == 2, (c, j)
    assert ler("SELECT slug FROM n_montado")[0][0] == MOD
    c, j = pedir("GET", "/api/n/movimentos" + q(deck=MOD))
    assert c == 200 and j["movimentos"] == [], j
    print("montar: um sempre montado é 409; um rotativo devolve os movimentos")


def caso_vender_procurar_a_mais_saida():
    c, j = pedir("GET", "/api/n/procurar" + q(q="u"))
    assert c == 200 and j == [], j                          # menos de 2 letras
    c, j = pedir("GET", "/api/n/procurar" + q(q="saga"))
    assert c == 200 and j == ["Urza's Saga"], j
    c, j = pedir("GET", "/api/n/procurar" + q(q="isl"))
    assert c == 200 and j == ["Island"], j                  # sem repetir o nome
    c, j = pedir("GET", "/api/n/procurar" + q(q="%a"))
    assert c == 200 and j == [], j                          # o % não é «tudo»
    c, j = pedir("POST", "/api/n/a_mais", {"scryfall_id": "saga-b",
                                           "acabamento": "foil", "delta": 3})
    assert c == 200 and j == {"qtd": 3}, (c, j)
    c, j = pedir("POST", "/api/n/a_mais", {"scryfall_id": "saga-b",
                                           "acabamento": "foil", "delta": -1})
    assert c == 200 and j == {"qtd": 2}, (c, j)
    c, j = pedir("POST", "/api/n/a_mais", {"scryfall_id": "saga-b",
                                           "acabamento": "nonfoil", "delta": 1})
    assert c == 409, (c, j)
    # uma saída: trocar a edição da Opalescence marcada passa-a para Vender
    con = db.connect()
    con.execute("INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
                " acabamento, qtd, em) VALUES (?,?,?,?,?,?,?)",
                (REP, "saiu_da_lista", None, "opal-a", "nonfoil", 2, DIA))
    con.commit()
    sid = con.execute("SELECT MAX(id) FROM n_saida").fetchone()[0]
    con.close()
    c, j = pedir("POST", "/api/n/saida", {"id": sid, "destino": "a_mais"})
    assert c == 200 and j == {"ok": True}, (c, j)
    assert ler("SELECT qtd FROM n_a_mais WHERE scryfall_id = 'opal-a'")[0][0] == 2
    c, j = pedir("POST", "/api/n/saida", {"id": sid, "destino": "descartar"})
    assert c == 409, (c, j)                                 # já não existe
    c, j = pedir("POST", "/api/n/saida", {"id": "x", "destino": "descartar"})
    assert c == 409, (c, j)
    print("vender: procurar, tenho a mais e as saídas")


def caso_pagina_editavel_tem_token_e_js():
    tok = webapp.token()
    for caminho, marca in (("/", "Painel"), ("/index.html", "Painel"),
                           ("/deck.html", "Decks"), ("/vender.html", "Vender")):
        c, p = pedir("GET", caminho + "?t=" + tok)
        assert c == 200, (caminho, c)
        assert f'<h1 class="pgt">{marca}</h1>' in p, caminho
        assert '<body data-editavel="1">' in p, caminho
        assert edicao_js.MARCA in p, caminho
        # os links levam o token, também os que têm âncora com «_»
        assert re.search(r'href="vender\.html\?t=' + tok, p), caminho
    c, p = pedir("GET", "/?t=" + tok)
    assert f'href="deck.html?t={tok}#modern_affinity"' in p
    c, p = pedir("GET", "/deck.html")
    # o loopback é de confiança: editável e com o JS, sem precisar do ?t=
    assert '<body data-editavel="1">' in p and edicao_js.MARCA in p
    assert 'data-acao="colar"' in p and 'data-acao="montar"' in p
    c, p = pedir("GET", "/vender.html")
    assert 'id="ed-q"' in p, "falta a busca de Vender"
    # da rede de casa SEM token: a página é a de leitura, sem JS nem token
    for caminho in ("/", "/deck.html", "/vender.html"):
        g = Pedido(caminho, metodo="GET")
        assert g.codigo == 200, (caminho, g.codigo)
        assert "data-editavel" not in g.corpo and edicao_js.MARCA not in g.corpo
        assert tok not in g.corpo, caminho
        assert 'data-acao=' not in g.corpo
    g = Pedido("/deck.html?t=" + tok, metodo="GET")
    assert '<body data-editavel="1">' in g.corpo and edicao_js.MARCA in g.corpo
    print("páginas: editáveis com o token nos links e o JS; sem token, só leitura")


def caso_js_request_id_sem_contexto_seguro():
    """No telemóvel, em http na rede de casa, o `crypto.randomUUID` não existe
    (contexto inseguro): o id tem de sair do `getRandomValues`, e o retry
    reutiliza-o."""
    js = edicao_js.JS
    assert "randomUUID" in js and "getRandomValues" in js
    assert "X-Mtgvault-Token" in js
    assert "nuc:atualizada" in js
    for proibido in ("<script", "</script", "src=\"", "url(", "api.scryfall.com"):
        assert proibido not in js, proibido
    rx = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    texto = (RAIZ / "mtgvault" / "nucleo" / "edicao_js.py").read_text(encoding="utf-8")
    assert not rx.findall(texto), rx.findall(texto)[:5]
    from mtgvault import site_shell
    usados = set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", edicao_js.CSS))
    definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", site_shell.TEMA))
    assert usados <= definidos, usados - definidos
    # a sintaxe, quando há `node` (um erro de sintaxe era a página sem edição
    # nenhuma, sem um único erro do lado do servidor)
    if shutil.which("node"):
        f = _TMP / "edicao.js"
        f.write_text(js, encoding="utf-8")
        p = subprocess.run(["node", "--check", str(f)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        assert p.returncode == 0, p.stderr
    else:
        print("js: sem `node`, a sintaxe não foi verificada")
    print("js: request_id com recurso ao getRandomValues, cores dos tokens")


def caso_desligado_e_como_antes():
    config(False)
    try:
        c, p = pedir("GET", "/")
        assert c == 200 and "data-editavel" not in p and edicao_js.MARCA not in p
        c, j = pedir("POST", "/api/n/marca", {"deck": REP, "nome": "Replenish",
                                              "delta": 1, "request_id": novo_id()})
        assert c == 404, (c, j)
        c, j = pedir("GET", "/api/n/edicoes" + q(nome="Island"))
        assert c == 404, (c, j)
    finally:
        config(True)
    print("com o interruptor desligado: o webapp de antes")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_") and callable(f):
            f()
    SRV.shutdown()
    print("TUDO OK")
