"""O MODO DE EDIÇÃO COM UTILIZADOR E PASSWORD (2026-10-31).

O túnel da Cloudflare liga-se ao 8771 pelo loopback, por isso até hoje quem
passasse o Cloudflare Access caía no «loopback é de confiança» e escrevia. Agora
um pedido com cabeçalhos de proxy é DE FORA e entra com o nome e a password do
cofre de contas partilhado com o riftvault (`mtgvault/conta.py`).

O servidor é o `webapp.Handler` a sério, num porto livre, sobre uma base, um
catálogo e um COFRE temporários: o `MTGVAULT_*` e o `CONTAS_DB` vão para uma
pasta temporária ANTES do import (o `MTGVAULT_DB` está no ambiente deste PC e
aponta para o `data/` a sério — ver `tests/_bateria.py`). O túnel imita-se com
os cabeçalhos que o `cloudflared` põe; a rede de casa (`192.168.1.99`) entra por
um pedido de mentira, porque não há como pôr esse IP num socket de teste.

As passwords daqui são inventadas e só existem nesta pasta temporária.
"""
import http.client
import io
import json
import os
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import types
from email.message import Message
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = _TMP / "cfg.json"
CFG.write_text(json.dumps({"nucleo": {"ligado": True}, "caixas": [],
                           "decks_vigiados": []}, ensure_ascii=False),
               encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")          # ver tests/_bateria.py
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")
os.environ["CONTAS_DB"] = str(_TMP / "contas.db")           # o cofre, nunca o a sério

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mtgvault import conta, db  # noqa: E402
from mtgvault.nucleo import listas, modelo  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

import webapp  # noqa: E402

webapp.ROOT = _TMP

REP = "premodern_replenish"
# Inventadas, para esta pasta temporária e mais nenhuma.
SENHAS = {"baverone": "lanterna-de-papel-teste", "ana": "girassol-no-telhado-teste",
          "carla": "comboio-das-onze-teste"}


def semear():
    con = db.connect()
    db.init(con)
    con.execute(
        """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
           set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, cardmarket_id, digital,
           set_type)
           VALUES ('repl-a','or-repl','Replenish','ulg','Urza''s Legacy','1',
           'en','rare','Enchantment',4,'W','["nonfoil"]','1999-02-15',1000,0,
           'expansion')""")
    con.commit()
    modelo.garantir_decks(con)
    listas.gravar_versao(con, REP, [Linha("main", "Replenish", 4)],
                         fonte="teste", origem="andre")
    con.commit()
    con.close()


def semear_cofre():
    m = conta.modulo()
    cc = m.abrir(conta.caminho_cofre())
    try:
        for i, (slug, sites) in enumerate((("baverone", ["mtg", "rift"]),
                                           ("ana", ["rift"]),
                                           ("carla", ["mtg"])), start=1):
            m.criar_conta(cc, slug, slug.title(), conta_id=i)
            m.definir_password(cc, i, SENHAS[slug], validar=False)
            for s in sites:
                m.dar_acesso(cc, i, s)
    finally:
        cc.close()


semear()
semear_cofre()
TOKEN = webapp.token()   # o de ESTA pasta temporária

with socket.socket() as _s:
    _s.bind(("127.0.0.1", 0))
    PORTO = _s.getsockname()[1]
SRV = webapp.ThreadingHTTPServer(("127.0.0.1", PORTO), webapp.Handler)
threading.Thread(target=SRV.serve_forever, daemon=True).start()


def tunel(ip="203.0.113.7"):
    """Os cabeçalhos que o `cloudflared` acrescenta a um pedido do túnel."""
    return {"Host": "editar-mtg.baverone.com", "Cf-Connecting-Ip": ip,
            "Cf-Ray": "8f00000000000000-LIS", "Cf-Visitor": '{"scheme":"https"}',
            "X-Forwarded-Proto": "https", "X-Forwarded-For": ip}


class R:
    def __init__(self, cod, corpo, cab):
        self.cod, self.corpo, self.cab = cod, corpo, cab

    def cookies(self):
        return self.cab.get_all("Set-Cookie") or []

    def __repr__(self):
        return f"R({self.cod}, {str(self.corpo)[:300]!r})"


def pedir(metodo, caminho, corpo=None, cab=None, tipo="application/json"):
    """Um pedido a sério ao servidor, SEM seguir redirecionamentos e com o
    `Host` que se quiser (o `urllib` não deixa nem uma coisa nem a outra)."""
    h = {"Host": f"127.0.0.1:{PORTO}"}
    h.update(cab or {})
    dados = None
    if corpo is not None:
        dados = (json.dumps(corpo) if tipo == "application/json" else corpo).encode("utf-8")
        h["Content-Type"] = tipo
    c = http.client.HTTPConnection("127.0.0.1", PORTO, timeout=120)
    try:
        c.request(metodo, caminho, body=dados, headers=h)
        r = c.getresponse()
        bruto = r.read()
        txt = bruto.decode("utf-8", "replace")
        if "json" in (r.headers.get("Content-Type") or ""):
            return R(r.status, json.loads(txt), r.headers)
        return R(r.status, txt, r.headers)
    finally:
        c.close()


def cookie_de(r) -> str:
    for linha in r.cookies():
        if linha.startswith(conta.COOKIE + "="):
            return linha.split(";", 1)[0]
    raise AssertionError(f"sem cookie de sessão: {r.cookies()}")


def entrar(nome, ip, senha=None):
    return pedir("POST", "/api/conta/entrar",
                 {"nome": nome, "senha": SENHAS[nome] if senha is None else senha},
                 cab=tunel(ip))


def entrar_e_marca(nome, ip):
    """Entra pelo túnel e vai buscar o CSRF onde a página o recebe: o `?t=` do
    redirecionamento de `/`. Devolve (cookie, csrf)."""
    r = entrar(nome, ip)
    assert r.cod == 200, r
    ck = cookie_de(r)
    r2 = pedir("GET", "/", cab={**tunel(ip), "Cookie": ck})
    assert r2.cod == 302, r2
    m = re.search(r"[?&]t=([^&#]+)", r2.cab.get("Location") or "")
    assert m, r2.cab.get("Location")
    return ck, m.group(1)


_n = [0]


def marca(rid=None):
    _n[0] += 1
    return {"deck": REP, "nome": "Replenish", "delta": 1,
            "request_id": rid or f"conta-{_n[0]}"}


def passou_a_porta(cod):
    return cod not in (401, 403)


class Pedido(webapp.Handler):
    """Um pedido de mentira com um IP qualquer: o mesmo handler, sem rede."""

    def __init__(self, path, corpo=None, ip="192.168.1.99", cab=None,
                 metodo="POST"):
        self.path = path
        self.client_address = (ip, 5555)
        bruto = json.dumps(corpo).encode("utf-8") if corpo is not None else b""
        self.rfile = io.BytesIO(bruto)
        self.headers = Message()
        self.headers["Host"] = "192.168.1.10:8771"
        self.headers["Content-Length"] = str(len(bruto))
        self.headers["Content-Type"] = "application/json"
        for k, v in (cab or {}).items():
            self.headers[k] = v
        self.server = None
        self.codigo, self.corpo, self.cab = None, "", []
        (self.do_POST if metodo == "POST" else self.do_GET)()

    def send_response(self, code, *_a):
        self.codigo = code

    def send_header(self, k, v):
        self.cab.append((k, v))

    def end_headers(self):
        for linha in self.__dict__.pop("_cookies_a_por", ()):
            self.send_header("Set-Cookie", linha)

    @property
    def wfile(self):
        self_ = self

        class Escritor:
            def write(self, b):
                self_.corpo = b.decode("utf-8", "replace")
        return Escritor()


# ---------------------------------------------------------------------------
def caso_tunel_e_de_fora():
    """Pelo túnel (loopback + Cf-*) e sem cookie: a caixa de entrada, sem o
    token. Era aqui que o «loopback é de confiança» dava escrita a quem
    passasse o Access."""
    for caminho in ("/", "/deck.html", "/deckboxes.html", "/deckboxes.js",
                    "/metagame.html", "/foto?copy=1"):
        r = pedir("GET", caminho, cab=tunel())
        assert r.cod == 200, (caminho, r)
        assert 'id="entrar"' in r.corpo, (caminho, r)
        assert TOKEN not in r.corpo, f"o token saiu em {caminho}"
        assert "data-editavel" not in r.corpo, caminho
    # e escrever pelo túnel sem sessão é o 403 de sempre, a mandar entrar
    r = pedir("POST", "/api/n/marca", marca(), cab=tunel())
    assert r.cod == 403 and "password" in r.corpo["erro"], r
    print("túnel sem sessão: a caixa de entrada em todo o lado, sem o token")


def caso_casa_continua():
    """No PC (loopback, sem cabeçalhos, Host de loopback): como sempre."""
    for host in (f"localhost:{PORTO}", f"127.0.0.1:{PORTO}", "LOCALHOST"):
        r = pedir("GET", "/", cab={"Host": host})
        assert r.cod == 200, (host, r)
        assert 'data-editavel="1"' in r.corpo, host
        assert "?t=" + TOKEN in r.corpo, f"de casa a página leva o token ({host})"
        assert 'id="entrar"' not in r.corpo
    r = pedir("POST", "/api/n/marca", marca(), cab={"Host": f"localhost:{PORTO}"})
    assert r.cod == 200, r
    print("de casa: página editável com o token e o POST aceite")


def caso_host_estranho_sem_token():
    """DNS rebinding: `evil.example` a apontar para 127.0.0.1 chega com o
    `Host` dele. Não é de casa — nem o token na página, nem escrita."""
    r = pedir("GET", "/", cab={"Host": "evil.example"})
    assert r.cod == 200, r
    assert TOKEN not in r.corpo
    assert 'data-editavel="1"' not in r.corpo
    r = pedir("POST", "/api/n/marca", marca(), cab={"Host": "evil.example"})
    assert r.cod == 403, r
    print("loopback com Host estranho: sem token na página e 403 a escrever")


def caso_lan_com_token():
    """Da rede de casa: com o `?t=` escreve, sem ele 403 (como até hoje)."""
    p = Pedido("/api/n/marca?t=" + TOKEN, marca())
    assert p.codigo == 200, (p.codigo, p.corpo)
    p = Pedido("/api/n/marca", marca(), cab={webapp.CABECALHO_TOKEN: TOKEN})
    assert p.codigo == 200, (p.codigo, p.corpo)
    p = Pedido("/api/n/marca", marca())
    assert p.codigo == 403, (p.codigo, p.corpo)
    # e ler da rede de casa sem token continua livre e só de leitura
    p = Pedido("/", metodo="GET")
    assert p.codigo == 200 and 'id="entrar"' not in p.corpo, p.codigo
    assert TOKEN not in p.corpo and 'data-editavel="1"' not in p.corpo
    print("rede de casa: com o token escreve, sem ele 403")


def caso_entrar_e_escrever():
    r = entrar("baverone", "203.0.113.10")
    assert r.cod == 200, r
    assert r.corpo == {"ok": True}, f"o corpo não leva sid nem csrf: {r.corpo}"
    linha = next(c for c in r.cookies() if c.startswith(conta.COOKIE + "="))
    for parte in ("HttpOnly", "SameSite=Lax", "Path=/", "Max-Age=2592000", "Secure"):
        assert parte in linha, (parte, linha)
    ck = linha.split(";", 1)[0]
    # com o cookie, a página manda para o mesmo caminho com a marca no URL
    r2 = pedir("GET", "/", cab={**tunel("203.0.113.10"), "Cookie": ck})
    assert r2.cod == 302, r2
    loc = r2.cab.get("Location")
    csrf = re.search(r"[?&]t=([^&#]+)", loc).group(1)
    assert loc.startswith("/?"), loc
    assert csrf != TOKEN and len(csrf) >= 32, "o CSRF não é o token"
    r3 = pedir("GET", loc, cab={**tunel("203.0.113.10"), "Cookie": ck})
    assert r3.cod == 200 and 'data-editavel="1"' in r3.corpo, r3
    assert "?t=" + csrf in r3.corpo, "os links levam o CSRF onde levavam o token"
    assert TOKEN not in r3.corpo, "o token deste PC não vai para quem tem sessão"
    # escrever: com o CSRF no cabeçalho 200; sem ele, ou com outro, 403
    r4 = pedir("POST", "/api/n/marca", marca(),
               cab={**tunel("203.0.113.10"), "Cookie": ck,
                    webapp.CABECALHO_TOKEN: csrf})
    assert r4.cod == 200, r4
    r5 = pedir("POST", "/api/n/marca", marca(),
               cab={**tunel("203.0.113.10"), "Cookie": ck})
    assert r5.cod == 403, r5
    r6 = pedir("POST", "/api/n/marca", marca(),
               cab={**tunel("203.0.113.10"), "Cookie": ck,
                    webapp.CABECALHO_TOKEN: csrf[:-1] + ("A" if csrf[-1] != "A" else "B")})
    assert r6.cod == 403, r6
    # o CSRF sem o cookie não vale nada
    r7 = pedir("POST", "/api/n/marca", marca(),
               cab={**tunel("203.0.113.10"), webapp.CABECALHO_TOKEN: csrf})
    assert r7.cod == 403, r7
    # e os dados da página vêm editáveis, com o CSRF no sítio do token
    r8 = pedir("GET", "/api/n/procurar?q=re",
               cab={**tunel("203.0.113.10"), "Cookie": ck})
    assert r8.cod == 200, r8
    print("entrar pelo túnel: cookie HttpOnly, página editável com o CSRF, 200/403")


def caso_entrar_exige_json():
    r = pedir("POST", "/api/conta/entrar",
              "nome=baverone&senha=" + SENHAS["baverone"],
              cab=tunel("203.0.113.11"), tipo="application/x-www-form-urlencoded")
    assert r.cod == 415, r
    assert not r.cookies(), "um formulário não pode abrir sessão"
    r = pedir("POST", "/api/conta/entrar", "{}", cab=tunel("203.0.113.11"),
              tipo="text/plain")
    assert r.cod == 415, r
    print("entrar só por application/json (415 o resto)")


def caso_amigo_nao_entra_no_mtg():
    """A `ana` só tem o riftvault: com a password CERTA falha como uma errada."""
    certa = entrar("ana", "203.0.113.12")
    errada = entrar("baverone", "203.0.113.13", senha="nao-e-esta-password")
    assert certa.cod == 401 and errada.cod == 401, (certa, errada)
    assert certa.corpo["erro"] == errada.corpo["erro"], (certa.corpo, errada.corpo)
    assert not certa.cookies()
    inexistente = entrar("baverone", "203.0.113.14", senha="x")
    r = pedir("POST", "/api/conta/entrar", {"nome": "ninguem", "senha": "x-y-z-w"},
              cab=tunel("203.0.113.14"))
    assert r.cod == 401 and r.corpo["erro"] == errada.corpo["erro"], (r, inexistente)
    print("conta sem acesso ao mtg: 401 com a frase de uma password errada")


def caso_travao():
    """Seis falhas da mesma conta: à sexta, 429 com o tempo a esperar."""
    cods = []
    for i in range(6):
        # um endereço por tentativa: é o travão da CONTA que se prova aqui
        r = entrar("carla", f"198.51.100.{i + 1}", senha="errada-de-proposito")
        cods.append(r.cod)
    assert cods == [401] * 5 + [429], cods
    assert int(r.cab.get("Retry-After") or 0) > 0, r.cab.get("Retry-After")
    assert "Espera" in r.corpo["erro"], r
    # a password certa entra na mesma (o «tranca-o-amigo» do cofre)
    ok = entrar("carla", "198.51.100.99")
    assert ok.cod == 200, ok
    print("travão: 5 falhas livres, à 6.ª 429; a certa entra na mesma")


def caso_travao_da_rede_nao_confia_no_cf():
    """Da rede de casa, um `Cf-Connecting-Ip` inventado a cada tentativa NÃO
    muda a chave do travão: só o túnel (socket de loopback) a pode dizer. Dez
    falhas livres por endereço, e a 11.ª é 429 — sem ela, um aparelho no Wi-Fi
    tentava passwords à vontade, um IP falso por palpite."""
    cods = []
    for i in range(11):
        p = Pedido("/api/conta/entrar",
                   {"nome": "ninguem-na-rede", "senha": "palpite-de-teste"},
                   ip="192.168.1.77",
                   cab={"Cf-Connecting-Ip": f"203.0.113.{100 + i}",
                        "Cf-Ray": "falso-LIS"})
        cods.append(p.codigo)
    assert cods == [401] * 10 + [429], cods
    assert "deste sítio" in json.loads(p.corpo)["erro"], p.corpo
    print("rede de casa: o Cf-Connecting-Ip falso não foge ao travão (11.ª → 429)")


def _no_cofre(fn):
    m = conta.modulo()
    cc = m.abrir(conta.caminho_cofre())
    try:
        return fn(m, cc)
    finally:
        cc.close()


def caso_geracao_antiga_fecha_sessao():
    ck, csrf = entrar_e_marca("baverone", "203.0.113.20")
    nova = "lanterna-nova-de-papel-teste"
    _no_cofre(lambda m, cc: m.definir_password(cc, 1, nova, validar=False))
    SENHAS["baverone"] = nova
    r = pedir("GET", "/", cab={**tunel("203.0.113.20"), "Cookie": ck})
    assert r.cod == 200 and 'id="entrar"' in r.corpo, r
    r = pedir("POST", "/api/n/marca", marca(),
              cab={**tunel("203.0.113.20"), "Cookie": ck,
                   webapp.CABECALHO_TOKEN: csrf})
    assert r.cod == 403, r
    print("password mudada no cofre: a sessão de antes volta à caixa")


def caso_tirar_acesso_fecha_sessao():
    ck, _ = entrar_e_marca("carla", "203.0.113.21")
    _no_cofre(lambda m, cc: m.tirar_acesso(cc, 3, "mtg"))
    try:
        r = pedir("GET", "/", cab={**tunel("203.0.113.21"), "Cookie": ck})
        assert r.cod == 200 and 'id="entrar"' in r.corpo, r
    finally:
        _no_cofre(lambda m, cc: m.dar_acesso(cc, 3, "mtg"))
    print("acesso ao mtg tirado: a sessão vai-se no pedido seguinte")


def caso_cookie_ao_lado_dos_do_cloudflare():
    """O Cloudflare põe os cookies dele no mesmo cabeçalho; o da sessão tem de
    se ler na mesma, à frente ou atrás deles."""
    r = entrar("baverone", "203.0.113.23")
    ck = cookie_de(r)
    for juntos in (f'CF_Authorization=eyJh.bGc.iOi; __cf_bm=a"b; {ck}',
                   f"{ck}; CF_Authorization=eyJh.bGc.iOi"):
        r2 = pedir("GET", "/api/n/procurar?q=re",
                   cab={**tunel("203.0.113.23"), "Cookie": juntos})
        assert r2.cod == 200, (juntos, r2)
    print("o cookie da sessão lê-se no meio dos do Cloudflare")


def caso_conta_recriada_nao_herda_sessao():
    """Apagar uma conta e criar outra com o MESMO número põe a geração a zero:
    sem o slug na sessão, a da conta apagada valia para a nova."""
    def preparar(m, cc):
        m.criar_conta(cc, "dora", "Dora", conta_id=9)
        m.definir_password(cc, 9, "dora-dos-cadernos-teste", validar=False)
        m.dar_acesso(cc, 9, "mtg")
    _no_cofre(preparar)
    SENHAS["dora"] = "dora-dos-cadernos-teste"
    ck, _ = entrar_e_marca("dora", "203.0.113.22")
    ger = _no_cofre(lambda m, cc: m.geracao(cc, 9))

    def recriar(m, cc):
        m.apagar_conta(cc, 9)
        m.criar_conta(cc, "eva", "Eva", conta_id=9)
        m.dar_acesso(cc, 9, "mtg")
        # a mesma geração, à mão, para só o slug os distinguir
        cc.execute("UPDATE contas SET geracao = ? WHERE id = 9", (ger,))
        cc.commit()
    _no_cofre(recriar)
    r = pedir("GET", "/", cab={**tunel("203.0.113.22"), "Cookie": ck})
    assert r.cod == 200 and 'id="entrar"' in r.corpo, r
    print("conta recriada com o mesmo número: a sessão antiga não serve")


def caso_sair():
    ck, csrf = entrar_e_marca("baverone", "203.0.113.30")
    # sem o CSRF não se sai (uma `<img>` de outro site não põe ninguém na rua)
    r = pedir("POST", "/api/conta/sair", {}, cab={**tunel("203.0.113.30"), "Cookie": ck})
    assert r.cod == 403, r
    r = pedir("GET", "/conta.html?t=" + csrf, cab={**tunel("203.0.113.30"), "Cookie": ck})
    assert r.cod == 200 and "Entraste como" in r.corpo and "Baverone" in r.corpo, r
    r = pedir("POST", "/api/conta/sair", {},
              cab={**tunel("203.0.113.30"), "Cookie": ck, webapp.CABECALHO_TOKEN: csrf})
    assert r.cod == 200, r
    linha = next(c for c in r.cookies() if c.startswith(conta.COOKIE + "="))
    assert "Max-Age=0" in linha, linha
    r = pedir("GET", "/", cab={**tunel("203.0.113.30"), "Cookie": ck})
    assert r.cod == 200 and 'id="entrar"' in r.corpo, r
    print("sair: cookie apagado e o pedido seguinte volta à caixa")


def caso_volta_so_interna():
    for mau in ("//evil.example", "https://evil.example/", "/\\evil.example",
                "evil.example", "/\nevil.example"):
        html = conta.pagina_entrar(volta=mau)
        assert "evil.example" not in html, mau
        assert 'id="entrar"' in html
    html = conta.pagina_entrar(volta="/deck.html?x=1")
    assert '"/deck.html?x=1"' in html, "um caminho interno fica"
    html = conta.pagina_entrar(volta="/</script><script>alert(1)</script>")
    assert "<script>alert(1)" not in html, "o `volta` não fecha o <script>"
    html = conta.pagina_entrar("/", erro="<b>x</b>")
    assert "<b>x</b>" not in html and "&lt;b&gt;" in html
    print("a caixa só volta para caminhos deste site")


def caso_api_de_fora_sem_sessao():
    for caminho in ("/api/n/procurar?q=is", "/data/paginas/deckboxes.json",
                    "/data/paginas/faltas.json"):
        r = pedir("GET", caminho, cab=tunel())
        assert r.cod == 401 and r.corpo == {"erro": "precisas de entrar"}, (caminho, r)
    print("dados de fora sem sessão: 401 em JSON")


def caso_sessao_nao_guarda_o_sid():
    r = entrar("baverone", "203.0.113.40")
    sid = cookie_de(r).split("=", 1)[1]
    con = sqlite3.connect(str(conta.caminho_sessoes()))
    try:
        linhas = con.execute("SELECT * FROM sessoes").fetchall()
    finally:
        con.close()
    assert linhas and not any(sid in map(str, l) for l in linhas), \
        "o sid em claro não pode estar na base"
    assert conta.caminho_sessoes() == Path(db.ROOT) / "sessoes.db"
    print("sessões: na base só o SHA-256 do sid")


def caso_sessao_desliza():
    """Uma sessão tocada há mais de uma hora adia o fim — e o cookie anda com
    ela, senão o browser deitava-o fora aos 30 dias da entrada."""
    r = entrar("baverone", "203.0.113.41")
    ck = cookie_de(r)
    con = sqlite3.connect(str(conta.caminho_sessoes()))
    con.execute("UPDATE sessoes SET visto_em = '2026-01-01T00:00:00+00:00', "
                "expira_em = '2099-01-01T00:00:00+00:00'")
    con.commit()
    con.close()
    r = pedir("GET", "/api/n/procurar?q=re", cab={**tunel("203.0.113.41"), "Cookie": ck})
    assert r.cod == 200, r
    assert any(c.startswith(ck) and "Max-Age=2592000" in c for c in r.cookies()), r.cookies()
    r = pedir("GET", "/api/n/procurar?q=re", cab={**tunel("203.0.113.41"), "Cookie": ck})
    assert not r.cookies(), "no máximo uma renovação por hora"
    print("sessão deslizante: renova uma vez por hora, com o cookie")


def caso_cache_guarda_a_pagina_sem_marca():
    """A cache das páginas geradas é por `editavel` e não por pessoa: a marca
    entra à saída. Com o token lá dentro, quem tinha sessão recebia o token."""
    falsa = types.SimpleNamespace(
        html_page=lambda con, editable=False, token="": f"<p>marca={token}</p>")
    webapp.PAGINAS_EDITAVEIS["/falsa.html"] = falsa
    try:
        assert webapp.pagina_editavel("/falsa.html", True) == f"<p>marca={TOKEN}</p>"
        assert webapp.pagina_editavel("/falsa.html", True, "csrf-x") == "<p>marca=csrf-x</p>"
        assert webapp.pagina_editavel("/falsa.html", False) == "<p>marca=</p>"
    finally:
        del webapp.PAGINAS_EDITAVEIS["/falsa.html"]
    print("a cache das páginas não guarda a marca de ninguém")


def caso_cofre_e_da_pasta_contas():
    """O `CONTAS_DB` manda; sem ele é o `data/contas.db` do pacote `contas`,
    nunca uma coisa tirada do `MTGVAULT_*`."""
    assert conta.caminho_cofre() == Path(os.environ["CONTAS_DB"])
    pasta = conta.pasta_contas()
    assert (pasta / "contas" / "__init__.py").is_file()
    antes = os.environ.pop("CONTAS_DB")
    try:
        assert conta.caminho_cofre() == pasta / "data" / "contas.db"
    finally:
        os.environ["CONTAS_DB"] = antes
    print(f"o cofre: CONTAS_DB, senão {pasta.name}/data/contas.db")


def _temporaria_para(slug, conta_id):
    """Uma conta com acesso ao mtg e uma TEMPORÁRIA acabada de dar."""
    def preparar(m, cc):
        m.criar_conta(cc, slug, slug.title(), conta_id=conta_id)
        m.dar_acesso(cc, conta_id, "mtg")
        return m.nova_temporaria(cc, conta_id)
    return _no_cofre(preparar)


def _sessoes_de(conta_id):
    con = sqlite3.connect(str(conta.caminho_sessoes()))
    try:
        return con.execute("SELECT COUNT(*) FROM sessoes WHERE conta_id = ?",
                           (conta_id,)).fetchone()[0]
    finally:
        con.close()


def _estado(conta_id):
    return _no_cofre(lambda m, cc: m.estado_password(cc, conta_id))


def caso_temporaria_pede_a_nova():
    """Uma password TEMPORÁRIA não abre sessão: o 403 diz `trocar` e a caixa
    pede a password nova. A temporária nunca é a password de todos os dias."""
    temp = _temporaria_para("filipa", 10)
    r = pedir("POST", "/api/conta/entrar", {"nome": "filipa", "senha": temp},
              cab=tunel("203.0.113.50"))
    assert r.cod == 403, r
    assert r.corpo.get("trocar") is True, r
    assert "password nova" in r.corpo["erro"], r
    assert not r.cookies(), "uma temporária não pode abrir sessão"
    assert temp not in json.dumps(r.corpo), "a temporária não volta na resposta"
    assert _sessoes_de(10) == 0, "ficou uma sessão aberta com a temporária"
    print("password temporária: 403 com `trocar`, sem sessão")


def caso_temporaria_troca_e_entra():
    temp = _temporaria_para("gil", 11)
    nova = "farol-de-inverno-teste"
    r = pedir("POST", "/api/conta/entrar",
              {"nome": "gil", "senha": temp, "nova": nova},
              cab=tunel("203.0.113.51"))
    assert r.cod == 200 and r.corpo == {"ok": True}, r
    assert nova not in json.dumps(r.corpo) and temp not in json.dumps(r.corpo)
    ck = cookie_de(r)
    e = _estado(11)
    assert e["tem"] and e["temporaria"] is False, e
    # a sessão serve: a página manda para o mesmo caminho com o CSRF
    r2 = pedir("GET", "/", cab={**tunel("203.0.113.51"), "Cookie": ck})
    assert r2.cod == 302 and "t=" in r2.cab.get("Location", ""), r2
    # a temporária já não entra; a nova entra
    r3 = pedir("POST", "/api/conta/entrar", {"nome": "gil", "senha": temp},
               cab=tunel("203.0.113.52"))
    assert r3.cod == 401, r3
    r4 = pedir("POST", "/api/conta/entrar", {"nome": "gil", "senha": nova},
               cab=tunel("203.0.113.52"))
    assert r4.cod == 200 and r4.corpo == {"ok": True}, r4
    print("temporária + password nova: grava, abre sessão, a temporária deixa de servir")


def caso_trocar_recusa_o_que_nao_deve():
    temp = _temporaria_para("helena", 12)
    # nova fraca: 400, continua temporária e sem sessão
    r = pedir("POST", "/api/conta/entrar",
              {"nome": "helena", "senha": temp, "nova": "curta"},
              cab=tunel("203.0.113.53"))
    assert r.cod == 400 and r.corpo.get("trocar") is True, r
    assert not r.cookies() and _estado(12)["temporaria"] is True, r
    # nova igual à temporária
    r = pedir("POST", "/api/conta/entrar",
              {"nome": "helena", "senha": temp, "nova": temp},
              cab=tunel("203.0.113.53"))
    assert r.cod == 400 and _estado(12)["temporaria"] is True, r
    # temporária errada: 401, como uma password errada
    r = pedir("POST", "/api/conta/entrar",
              {"nome": "helena", "senha": "nao-e-esta-123", "nova": "farol-de-inverno-teste"},
              cab=tunel("203.0.113.53"))
    assert r.cod == 401 and _estado(12)["temporaria"] is True, r
    # com uma password que não é temporária não se troca nada por aqui
    g = _no_cofre(lambda m, cc: m.geracao(cc, 3))
    r = pedir("POST", "/api/conta/entrar",
              {"nome": "carla", "senha": SENHAS["carla"], "nova": "farol-de-inverno-teste"},
              cab=tunel("203.0.113.54"))
    assert r.cod == 400 and not r.cookies(), r
    assert _no_cofre(lambda m, cc: m.geracao(cc, 3)) == g, "mudou a password"
    # caducada: 401 a dizer porquê
    def envelhecer(m, cc):
        cc.execute("UPDATE senhas SET mudado_em = '2026-01-01T00:00:00+00:00' "
                   "WHERE conta_id = 12")
        cc.commit()
    _no_cofre(envelhecer)
    r = pedir("POST", "/api/conta/entrar", {"nome": "helena", "senha": temp},
              cab=tunel("203.0.113.55"))
    assert r.cod == 401 and "24 horas" in r.corpo["erro"], r
    assert not r.corpo.get("trocar"), r
    print("troca recusada: fraca/igual 400, errada 401, não-temporária 400, caducada 401")


def caso_caixa_tem_o_passo_da_password_nova():
    p = conta.pagina_entrar("/")
    for pedaco in ('id="nova"', 'id="repete"', 'autocomplete="new-password"',
                   "j.trocar", "Gravar e entrar"):
        assert pedaco in p, pedaco
    print("a caixa de entrada tem o passo da password nova")


def caso_503_nao_escreve_a_query_no_log():
    """O `?t=` é o token (ou o CSRF de uma sessão): um log não o pode levar."""
    import contextlib
    h = webapp.Handler.__new__(webapp.Handler)
    h.path = "/data/paginas/deckboxes.json?t=segredo-do-teste&x=1"
    h._json = lambda *a, **k: None
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        h._ainda_nao(webapp.DadosAindaNaoProntos("as Deckboxes", 26.0, 25.0))
    linha = saida.getvalue()
    assert "/data/paginas/deckboxes.json" in linha, linha
    assert "?" not in linha and "segredo-do-teste" not in linha, linha
    print("o 503 regista o caminho, sem a query")


def caso_arranque_diz_o_cofre():
    """O arranque diz que cofre usa e quantas contas entram no mtg — nunca
    quais —, e um cofre que falta diz-se sem se criar."""
    import contextlib
    from unittest import mock
    linha = conta.linha_de_arranque()
    assert str(conta.caminho_cofre()) in linha, linha
    n = _no_cofre(lambda m, cc: cc.execute(
        "SELECT COUNT(DISTINCT conta_id) FROM acessos WHERE site = 'mtg'").fetchone()[0])
    assert f"{n} contas com acesso ao mtg" in linha, (n, linha)
    for slug in ("baverone", "carla", "ana"):
        assert slug not in linha, linha
    falta = _TMP / "nao-ha" / "contas.db"
    antes = os.environ["CONTAS_DB"]
    os.environ["CONTAS_DB"] = str(falta)
    try:
        sem = conta.linha_de_arranque()
    finally:
        os.environ["CONTAS_DB"] = antes
    assert "NÃO EXISTE" in sem and str(falta) in sem, sem
    assert not falta.parent.exists(), "o arranque criou o cofre"

    class Srv:
        def __init__(self, *a):
            pass

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            pass
    saida = io.StringIO()
    with mock.patch.object(webapp, "ThreadingHTTPServer", Srv), \
            mock.patch.object(webapp, "vigia_versao", lambda: None), \
            mock.patch.object(webapp, "preparar_nucleo", lambda con: None), \
            mock.patch.object(webapp, "ligacao_local",
                              lambda port=None: {"url": "http://exemplo:8771/"}), \
            contextlib.redirect_stdout(saida):
        webapp.main(port=8999, host="127.0.0.1")
    assert linha in saida.getvalue(), saida.getvalue()
    print("o arranque diz o cofre e quantas contas entram no mtg")


def caso_bateria_isola_o_cofre():
    import _bateria
    try:
        cofre = Path(_bateria.AMBIENTE["CONTAS_DB"]).resolve()
        real = (conta.pasta_contas() / "data").resolve()
        assert not cofre.is_relative_to(real), cofre
        assert cofre.parent.is_dir(), "a pasta temporária existe"
    finally:
        shutil.rmtree(_bateria._COFRE_DA_CORRIDA, ignore_errors=True)
    print("a bateria põe o CONTAS_DB fora do cofre a sério")


if __name__ == "__main__":
    try:
        for nome, f in list(globals().items()):
            if nome.startswith("caso_") and callable(f):
                f()
    finally:
        SRV.shutdown()
        SRV.server_close()
    print("\nTUDO OK")
