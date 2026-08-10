"""Interface web LOCAL do mtgvault (biblioteca-padrão, sem frameworks).

Corre no PC (ou no VPS), não no GitHub Pages — porque ESCREVE no vault.db.
Uso:  python webapp.py   →  http://localhost:8770

O que faz (v1):
- Lista os decks premodern por prioridade (deck_meta.priority).
- Botão "Sleevado e na caixa": marca o deck como fechado. As cartas que estão
  na sub-coleção desse deck passam a ser EXCLUSIVAS dele e saem do pool
  partilhado do formato (a disponibilidade para os outros decks é recalculada
  aqui, ao vivo). Botão "Tirar da caixa" desfaz.

Modelo: a tabela `boxed_decks` guarda que decks estão fechados. Um deck fechado
tira as suas cartas (as da sua sub-coleção) do pool partilhado "Premodern (geral)".
As cartas de cada deck defines-as pondo as fotos na pasta do deck; a prioridade
serve para, no futuro, atribuir cartas contestadas ao deck de maior prioridade.
"""
from __future__ import annotations

import html
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db  # noqa: E402

PORT = 8770
POOL = "Premodern"


def _ensure(con):
    con.execute("CREATE TABLE IF NOT EXISTS boxed_decks ("
                "sub_collection TEXT PRIMARY KEY, boxed_at TEXT NOT NULL)")
    con.commit()


def _decks(con):
    """Decks do pool premodern, por prioridade, com nº de cartas e estado."""
    boxed = {r["sub_collection"] for r in con.execute("SELECT sub_collection FROM boxed_decks")}
    rows = []
    for r in con.execute(
        "SELECT sub_collection, priority FROM deck_meta WHERE pool = ? "
        "ORDER BY COALESCE(priority, 99), sub_collection", (POOL,)
    ):
        name = r["sub_collection"]
        n = con.execute(
            "SELECT COALESCE(SUM(cp.quantity),0) q FROM copies cp "
            "JOIN sub_collections sc ON sc.id = cp.sub_collection_id WHERE sc.name = ?",
            (name,)
        ).fetchone()["q"]
        rows.append({"name": name, "priority": r["priority"], "cards": n,
                     "boxed": name in boxed})
    return rows


def _pool_shared(con, decks):
    """Cartas no pool partilhado 'Premodern (geral)' menos as dos decks fechados."""
    shared = con.execute(
        "SELECT COALESCE(SUM(cp.quantity),0) q FROM copies cp "
        "JOIN sub_collections sc ON sc.id = cp.sub_collection_id WHERE sc.name = ?",
        ("Premodern (geral)",)
    ).fetchone()["q"]
    boxed_cards = sum(d["cards"] for d in decks if d["boxed"])
    return shared, boxed_cards


def _page(con):
    decks = _decks(con)
    shared, boxed_cards = _pool_shared(con, decks)
    rows = ""
    for d in decks:
        estado = ('<span class="tag boxed">na caixa</span>' if d["boxed"]
                  else '<span class="tag open">no pool</span>')
        botao = (f'<form method="post" action="/unbox"><input type="hidden" name="deck" value="{html.escape(d["name"])}">'
                 f'<button class="b unbox">Tirar da caixa</button></form>' if d["boxed"]
                 else f'<form method="post" action="/box"><input type="hidden" name="deck" value="{html.escape(d["name"])}">'
                      f'<button class="b box">Sleevado e na caixa 📦</button></form>')
        rows += (f'<tr class="{ "isboxed" if d["boxed"] else "" }"><td class="pr">{d["priority"] or "—"}</td>'
                 f'<td class="nm">{html.escape(d["name"])}</td>'
                 f'<td class="ct">{d["cards"]}</td><td>{estado}</td><td class="ac">{botao}</td></tr>')
    return _TMPL.replace("%ROWS%", rows).replace("%SHARED%", str(shared)).replace("%BOXED%", str(boxed_cards))


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>mtgvault — local</title>
<style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--rem:#ff6b6b}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:820px;margin:0 auto;padding:24px 16px 60px}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px} .sub a{color:var(--accent)}
 .pool{margin:16px 0;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:12px}
 .pool b{color:var(--gold);font-variant-numeric:tabular-nums}
 table{width:100%;border-collapse:collapse;margin-top:10px;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
 th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line)} th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em}
 tr:last-child td{border-bottom:0} tr.isboxed{opacity:.72} .pr{width:34px;color:var(--muted);text-align:center} .nm{font-weight:600} .ct{width:56px;font-variant-numeric:tabular-nums;color:var(--muted)}
 .tag{font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px} .tag.boxed{background:#3a2c12;color:var(--gold)} .tag.open{background:#12351f;color:var(--add)}
 .ac{text-align:right;width:210px} .b{border:0;border-radius:8px;padding:8px 12px;font-size:13px;font-weight:600;cursor:pointer;color:#fff}
 .b.box{background:var(--accent)} .b.unbox{background:transparent;border:1px solid var(--line);color:var(--muted)}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>mtgvault — controlo local</h1>
<div class="sub">Decks Premodern por prioridade · esta app escreve no vault.db · <a href="colecao.html">galeria da coleção</a></div></header>
<div class="pool">Pool partilhado <b>Premodern (geral)</b>: %SHARED% cartas · nas caixas (exclusivas de decks): <b>%BOXED%</b></div>
<table><tr><th>Prio</th><th>Deck</th><th>Cartas</th><th>Estado</th><th></th></tr>%ROWS%</table>
<footer>"Sleevado e na caixa" tira as cartas do deck do pool partilhado do formato. As cartas de cada deck defines-as pondo as fotos na pasta do deck. v1 — a integração com o site público e a atribuição por prioridade continuam a seguir.</footer>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, code=200, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            with db.session() as con:
                _ensure(con)
                self._send(_page(con))
        elif path == "/colecao.html" and (ROOT / "colecao.html").exists():
            self._send((ROOT / "colecao.html").read_text(encoding="utf-8"))
        else:
            self._send("404", 404, "text/plain; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        deck = (form.get("deck") or [""])[0]
        if deck and path in ("/box", "/unbox"):
            with db.session() as con:
                _ensure(con)
                if path == "/box":
                    con.execute("INSERT OR IGNORE INTO boxed_decks (sub_collection, boxed_at) "
                                "VALUES (?, datetime('now'))", (deck,))
                else:
                    con.execute("DELETE FROM boxed_decks WHERE sub_collection = ?", (deck,))
                con.commit()
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *a):  # silêncio
        pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"mtgvault local em http://localhost:{PORT}  (Ctrl+C para parar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
