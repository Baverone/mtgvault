"""A REVISÃO COMPLETA DE 2026-10-25 — um caso por bug corrigido.

Cada caso reproduz o defeito tal como estava (e chumba com o código antigo):

  1. `webapp`: `data/paginas/../arquetipos.json` servia um `.json` de fora de
     `data/paginas/` a qualquer aparelho da rede;
  2. `webapp`: `/foto?copy=abc` e um `Content-Length` que não é número fechavam
     a ligação sem resposta; um `Content-Length: -1` pendurava o fio;
  3. `webapp`: um POST vindo de OUTRO site (o `Origin` diz qual) gravava pelo
     loopback sem token;
  4. `my_decks.fixar` com um id errado SOLTAVA a fixação antes de recusar;
  5. `vigia`: as peças de um combo partiam «Kasmina, Enigma Sage» na vírgula;
  6. `arts`: `MH2 197★.jpg` lia-se como a impressão #197;
  7. `painel`: os avisos das staples de um dia antigo entravam como de hoje;
  8. `decks.js`/`arrumacao`: uma resposta lenta escrevia por cima da vista
     actual, e o `+`/`−` deixava o índice com o número antigo.

Bases temporárias com caminho explícito; não toca na rede nem no `data/`.
"""
import http.client
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mtgvault import arts, db, painel, vigia  # noqa: E402
import my_decks  # noqa: E402
import webapp  # noqa: E402
from test_bugs_ronda_1021 import _guardar, _lista  # noqa: E402


def _servidor():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porto = s.getsockname()[1]
    s.close()
    srv = webapp.ThreadingHTTPServer(("127.0.0.1", porto), webapp.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, porto


def _pedido(porto, metodo, caminho, corpo=None, cab=None, prazo=5):
    c = http.client.HTTPConnection("127.0.0.1", porto, timeout=prazo)
    c.putrequest(metodo, caminho, skip_accept_encoding=True,
                 skip_host="Host" in (cab or {}))
    for k, v in (cab or {}).items():
        c.putheader(k, v)
    if corpo is not None and "Content-Length" not in (cab or {}):
        c.putheader("Content-Length", str(len(corpo)))
    c.endheaders()
    if corpo:
        c.send(corpo)
    r = c.getresponse()
    return r.status, r.read()


def caso_o_caminho_com_ponto_ponto_nao_sai_de_data_paginas():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data" / "paginas").mkdir(parents=True)
    (tmp / "data" / "paginas" / "x.json").write_text('{"ok": 1}', encoding="utf-8")
    (tmp / "data" / "segredo.json").write_text('{"nao": 1}', encoding="utf-8")
    raiz, webapp.ROOT = webapp.ROOT, tmp
    srv, porto = _servidor()
    try:
        st, _ = _pedido(porto, "GET", "/data/paginas/x.json")
        assert st == 200, st
        st, corpo = _pedido(porto, "GET", "/data/paginas/../segredo.json")
        assert st == 404, f"o .. saiu de data/paginas: {st} {corpo[:80]!r}"
    finally:
        srv.shutdown()
        webapp.ROOT = raiz
    print("data/paginas/../segredo.json → 404")


def caso_entradas_invalidas_dao_400_e_nao_penduram():
    srv, porto = _servidor()
    try:
        st, _ = _pedido(porto, "GET", "/foto?copy=abc")
        assert st == 400, st
        st, _ = _pedido(porto, "POST", "/api/vista", b"{}", {"Content-Length": "xx"})
        assert st == 400, st
        st, _ = _pedido(porto, "GET", "/foto?copy=%C2%B2")       # «²» é dígito
        assert st == 400, st
        t0 = time.monotonic()
        st, _ = _pedido(porto, "POST", "/api/vista", b"", {"Content-Length": "-1"})
        assert st == 400 and time.monotonic() - t0 < 3, st
    finally:
        srv.shutdown()
    print("copy=abc, Content-Length inválido e negativo → 400 sem pendurar")


def caso_um_post_de_outro_site_e_recusado():
    srv, porto = _servidor()
    try:
        corpo = b'{"vista": "zzz"}'
        st, txt = _pedido(porto, "POST", "/api/vista", corpo,
                          {"Origin": "https://mau.example", "Content-Type": "text/plain"})
        assert st == 403 and "outro site" in txt.decode("utf-8"), (st, txt[:120])
        st, _ = _pedido(porto, "POST", "/api/vista", corpo, {"Origin": "null"})
        assert st == 403, st
        # DNS rebinding: `evil.com` a apontar para 127.0.0.1 — o browser põe o
        # Host e o Origin iguais ao domínio do atacante. Pelo loopback não basta.
        st, _ = _pedido(porto, "POST", "/api/vista", corpo,
                        {"Origin": "http://evil.example:%d" % porto,
                         "Host": "evil.example:%d" % porto})
        assert st == 403, f"DNS rebinding passou: {st}"
        # a própria página (Origin = Host) e o endereço do modo de edição passam
        # a porta: o que responde a seguir já é o endpoint (409, valor inválido)
        for org in (f"http://127.0.0.1:{porto}", "https://editar-mtg.baverone.com"):
            st, txt = _pedido(porto, "POST", "/api/vista", corpo, {"Origin": org})
            assert st != 403, (org, st, txt[:120])
        st, _ = _pedido(porto, "POST", "/api/vista", corpo)   # sem Origin: o urllib
        assert st != 403, st
    finally:
        srv.shutdown()
    print("POST com Origin de outro site → 403; a própria página e o modo de edição passam")


def caso_o_get_nao_espera_um_minuto_pelo_lock():
    """O índice da Deckboxes recolhe fotos a cada pedido; com o lock de escrita
    ocupado (uma regeneração em fundo) esperava os 60 s de omissão e saía 503."""
    import webapp as w
    orig = (w.fotos_mod.fotos_nas_pastas, w.fotocaixa.ha_pendentes)
    w.fotos_mod.fotos_nas_pastas = lambda *a, **k: [{"x": 1}]
    w.fotocaixa.ha_pendentes = lambda *a, **k: True
    w.ESCRITA.acquire()
    try:
        t0 = time.monotonic()
        assert w.recolher_fotos_das_pastas() is None
        assert w.recolher_fotos_de_caixas() is None
        dt = time.monotonic() - t0
        assert dt < 6, f"o GET esperou {dt:.1f} s pelo lock"
    finally:
        w.ESCRITA.release()
        w.fotos_mod.fotos_nas_pastas, w.fotocaixa.ha_pendentes = orig
    print(f"recolher fotos com o lock ocupado: desiste em {dt:.1f} s")


def caso_fixar_com_id_errado_nao_solta_a_fixacao(con):
    base = {"Grinding Station": 4, "Mox Opal": 4, "Emry, Lurker of the Loch": 4,
            "Sewer-veillance Cam": 4}
    a = _guardar(con, "a", _lista(base, 4, "Ornithopter"), "2026-10-17", "Alakai")
    con.commit()
    my_decks.fixar(con, "Grinding Station", a, hoje="2026-10-21")
    try:
        my_decks.fixar(con, "Grinding Station", 99_999_999, hoje="2026-10-22")
        raise AssertionError("um id que não existe devia ser recusado")
    except ValueError:
        pass
    con.rollback()
    assert my_decks.fixada(con, "Grinding Station", "modern") == a, \
        "o fixar recusado deixou o deck solto"
    print("fixar com um id que não existe recusa e o deck continua fixado")


def caso_as_pecas_do_combo_nao_se_partem_na_virgula(con):
    cartas = [("main", "Kasmina, Enigma Sage", 4), ("main", "Jace's Machinations", 4),
              ("side", "Jace's Machinations", 1)] + [("main", f"K{i}", 4) for i in range(13)]
    _guardar(con, "k", cartas, "2026-10-23", "kas")
    con.commit()
    orig = vigia.combos
    vigia.combos = lambda: [{"carta": "combo Kasmina", "nota": "", "minimo": 2,
                             "combo": ["Kasmina, Enigma Sage", "Jace's Machinations"],
                             "formatos": []}]
    try:
        ach = vigia._achados_combos(con)
    finally:
        vigia.combos = orig
    assert ach, "o combo não foi achado"
    assert ach[0]["pecas"] == ["Jace's Machinations", "Kasmina, Enigma Sage"], ach[0]["pecas"]
    print("peças do combo:", ach[0]["pecas"])


def caso_o_numero_com_estrela_le_se_inteiro():
    m = arts._NOME_IMPRESSAO.match("MH2 197★.jpg")
    assert m and m.group(2) == "197★", m and m.groups()
    m = arts._NOME_IMPRESSAO.match("MH2 197.jpg")
    assert m and m.group(2) == "197", m and m.groups()
    m = arts._NOME_IMPRESSAO.match("ONS_316a (2).jpg")
    assert m and m.group(2) == "316a", m and m.groups()
    print("MH2 197★ → 197★; MH2 197 → 197; ONS_316a → 316a")


def caso_os_avisos_das_staples_de_outro_dia_nao_passam_por_hoje(con):
    raiz = Path(tempfile.mkdtemp())
    p = painel.pasta(raiz)
    p.mkdir(parents=True, exist_ok=True)
    velho = {"gravidade": "media", "deck": "Staples Premodern", "aviso": "VELHO", "detalhe": ""}
    (p / painel.OUTROS).write_text(json.dumps({"data": "2026-10-01", "avisos": [velho]}),
                                   encoding="utf-8")
    av = painel.construir(con, hoje="2026-10-25", raiz=raiz)["avisos.json"]
    assert not any(a["aviso"] == "VELHO" for a in av), av
    assert any("2026-10-01" in a["aviso"] for a in av), av
    (p / painel.OUTROS).write_text(json.dumps({"data": "2026-10-25", "avisos": [velho]}),
                                   encoding="utf-8")
    av = painel.construir(con, hoje="2026-10-25", raiz=raiz)["avisos.json"]
    assert any(a["aviso"] == "VELHO" for a in av), av
    print("avisos das staples só entram no dia em que foram escritos")


_JS_CORRIDA = r"""
// O fetch da parte do deck só responde quando o teste deixar; entretanto ele
// volta ao nível dos formatos. A parte não pode desenhar por cima.
resultado = (async () => {
  let solta;
  globalThis.fetch = fetch = (u) => new Promise(res => {
    const corpo = String(u).includes('decks/') ? {nome: 'x', grupos: []} : D;
    const r = {ok: true, status: 200, json: async () => corpo,
               text: async () => JSON.stringify(corpo)};
    if (String(u).includes('decks/')) solta = () => res(r); else res(r);
  });
  await new Promise(r => setTimeout(r, 50));   // o arranca() da página
  PARTES = {}; D.partes = {};
  FMT = 'f'; DECK = 'x';
  const p1 = render();
  FMT = ''; DECK = '';
  await render();
  const depois = el('vista').innerHTML;
  for (let i = 0; i < 20 && !solta; i++) await new Promise(r => setTimeout(r, 10));
  if (solta) solta();
  await p1;
  return {igual: el('vista').innerHTML === depois, pediu: !!solta,
          depois: depois.slice(0, 60)};
})();
"""


def caso_o_js_dos_decks_guarda_a_ordem_das_respostas():
    import decks as decks_pag
    js = decks_pag.js_texto()
    assert "if (seq !== RSEQ) return;" in js and "D_SUJO = true;" in js
    assert "pinta(tile, CONFIRMADO.get(nome), pede)" in js, \
        "uma escrita recusada não repõe o número"
    assert js.index("D_SUJO = false;") < js.index("D = await carregaDados('decks.json'); PARTES"), \
        "o D_SUJO tem de baixar ANTES do pedido"
    from arrumacao import _js
    assert "if (seq !== RSEQ) return;" in _js()
    # E a prova a correr, no harness de node, se houver node.
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        print("(sem node: só a verificação do texto)")
        return
    tmp = Path(tempfile.mkdtemp())
    idx = {"formatos": [], "frase_marcas": "", "editavel": False, "partes": {}}
    html = decks_pag._tmpl().replace(
        "%SCRIPT%", "<script>\n" + js.replace(
            "D = await carregaDados('decks.json')", "D = " + json.dumps(idx)) + "</script>")
    (tmp / "p.html").write_text(html, encoding="utf-8")
    (tmp / "t.js").write_text(_JS_CORRIDA, encoding="utf-8")
    r = subprocess.run(["node", str(RAIZ / "tests" / "avaliar_js.js"),
                        str(tmp / "p.html"), str(tmp / "t.js")],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-600:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["igual"], f"a resposta lenta escreveu por cima: {out}"
    print("decks.js: a resposta lenta não escreve por cima da vista actual", out)


def run():
    caso_o_caminho_com_ponto_ponto_nao_sai_de_data_paginas()
    caso_entradas_invalidas_dao_400_e_nao_penduram()
    caso_um_post_de_outro_site_e_recusado()
    caso_o_numero_com_estrela_le_se_inteiro()
    caso_o_get_nao_espera_um_minuto_pelo_lock()
    caso_o_js_dos_decks_guarda_a_ordem_das_respostas()
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        caso_fixar_com_id_errado_nao_solta_a_fixacao(con)
        caso_as_pecas_do_combo_nao_se_partem_na_virgula(con)
        caso_os_avisos_das_staples_de_outro_dia_nao_passam_por_hoje(con)
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
