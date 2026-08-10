"""Interface web LOCAL do mtgvault (biblioteca-padrão, sem frameworks).

Corre no PC (ou no VPS), não no GitHub Pages — porque ESCREVE no vault.db.
Uso:  python webapp.py   →  http://localhost:8770

Decks premodern por prioridade. Botão "Sleevado e na caixa" (v2):
- RESERVA as cartas da sub-coleção do deck a esse deck (copies.reserved_deck_id,
  o mesmo mecanismo do CLI) — deixam de estar disponíveis para os outros decks
  do formato, na app, no site e na análise (owned_playable exclui reservadas).
- Tira essas cartas do pool partilhado "Premodern (geral)".
"Tirar da caixa" liberta as cartas.

As cartas de cada deck defines-as pondo as fotos na pasta do deck; a prioridade
(deck_meta.priority) diz quem tem precedência sobre cartas partilhadas.
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
SHARED = "Premodern (geral)"


def _ensure(con):
    con.execute("CREATE TABLE IF NOT EXISTS boxed_decks ("
                "sub_collection TEXT PRIMARY KEY, boxed_at TEXT NOT NULL)")
    con.commit()


def _price(con):
    return {(r["scryfall_id"], r["finish"]): r["trend"] for r in con.execute(
        "SELECT scryfall_id, finish, trend FROM price_latest WHERE source='cardmarket'")
        if r["trend"] is not None}


def _sub_stats(con, name, price):
    """(nº de cartas, valor EUR) das cópias na sub-coleção `name`."""
    n, val = 0, 0.0
    for r in con.execute(
        "SELECT cp.scryfall_id sid, cp.finish, cp.quantity q FROM copies cp "
        "JOIN sub_collections sc ON sc.id = cp.sub_collection_id WHERE sc.name = ?", (name,)
    ):
        n += r["q"]
        val += (price.get((r["sid"], r["finish"])) or 0) * r["q"]
    return n, round(val, 2)


def _decks(con, price):
    boxed = {r["sub_collection"] for r in con.execute("SELECT sub_collection FROM boxed_decks")}
    out = []
    for r in con.execute("SELECT sub_collection, priority FROM deck_meta WHERE pool = ? "
                         "ORDER BY COALESCE(priority, 99), sub_collection", (POOL,)):
        name = r["sub_collection"]
        n, val = _sub_stats(con, name, price)
        out.append({"name": name, "priority": r["priority"], "cards": n,
                    "value": val, "boxed": name in boxed})
    return out


def _deck_id(con, name):
    con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?, 'premodern')", (name,))
    con.commit()
    return con.execute("SELECT id FROM decks WHERE name = ?", (name,)).fetchone()["id"]


def box(con, name):
    did = _deck_id(con, name)
    con.execute("UPDATE copies SET reserved_deck_id = ? WHERE sub_collection_id = "
                "(SELECT id FROM sub_collections WHERE name = ?)", (did, name))
    con.execute("INSERT OR IGNORE INTO boxed_decks (sub_collection, boxed_at) "
                "VALUES (?, datetime('now'))", (name,))
    con.commit()


def unbox(con, name):
    row = con.execute("SELECT id FROM decks WHERE name = ?", (name,)).fetchone()
    if row:
        con.execute("UPDATE copies SET reserved_deck_id = NULL WHERE reserved_deck_id = ?", (row["id"],))
    con.execute("DELETE FROM boxed_decks WHERE sub_collection = ?", (name,))
    con.commit()


def _eur(v):
    return f"{v:,.2f} €".replace(",", " ")


def _page(con):
    price = _price(con)
    decks = _decks(con, price)
    shared_n, shared_v = _sub_stats(con, SHARED, price)
    rows = ""
    for d in decks:
        estado = ('<span class="tag boxed">na caixa</span>' if d["boxed"]
                  else '<span class="tag open">no pool</span>')
        act = "unbox" if d["boxed"] else "box"
        lbl = "Tirar da caixa" if d["boxed"] else "Sleevado e na caixa 📦"
        bcls = "unbox" if d["boxed"] else "box"
        botao = (f'<form method="post" action="/{act}"><input type="hidden" name="deck" '
                 f'value="{html.escape(d["name"])}"><button class="b {bcls}">{lbl}</button></form>')
        rows += (f'<tr class="{"isboxed" if d["boxed"] else ""}"><td class="pr">{d["priority"] or "—"}</td>'
                 f'<td class="nm">{html.escape(d["name"])}</td><td class="ct">{d["cards"]}</td>'
                 f'<td class="vl">{_eur(d["value"]) if d["value"] else "—"}</td>'
                 f'<td>{estado}</td><td class="ac">{botao}</td></tr>')
    return (_TMPL.replace("%ROWS%", rows)
            .replace("%SHN%", str(shared_n)).replace("%SHV%", _eur(shared_v)))


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>mtgvault — local</title>
<style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:860px;margin:0 auto;padding:24px 16px 60px}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px} .sub a{color:var(--accent)}
 .pool{margin:16px 0;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:12px}
 .pool b{color:var(--gold);font-variant-numeric:tabular-nums}
 table{width:100%;border-collapse:collapse;margin-top:10px;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
 th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line)} th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em}
 tr:last-child td{border-bottom:0} tr.isboxed{opacity:.7} .pr{width:34px;color:var(--muted);text-align:center} .nm{font-weight:600}
 .ct{width:56px;font-variant-numeric:tabular-nums;color:var(--muted)} .vl{width:100px;color:var(--gold);font-variant-numeric:tabular-nums;font-size:13px}
 .tag{font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px} .tag.boxed{background:#3a2c12;color:var(--gold)} .tag.open{background:#12351f;color:var(--add)}
 .ac{text-align:right;width:210px} .b{border:0;border-radius:8px;padding:8px 12px;font-size:13px;font-weight:600;cursor:pointer;color:#fff}
 .b.box{background:var(--accent)} .b.unbox{background:transparent;border:1px solid var(--line);color:var(--muted)}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>mtgvault — controlo local</h1>
<div class="sub">Decks Premodern por prioridade · esta app escreve no vault.db · <a href="colecao.html">galeria da coleção</a></div></header>
<div class="pool">Pool partilhado <b>Premodern (geral)</b>: %SHN% cartas · <b>%SHV%</b> <span style="color:var(--muted)">(o que fica disponível para os decks ainda não fechados)</span></div>
<table><tr><th>Prio</th><th>Deck</th><th>Cartas</th><th>Valor</th><th>Estado</th><th></th></tr>%ROWS%</table>
<footer>"Sleevado e na caixa" reserva as cartas da pasta do deck a esse deck (deixam de estar disponíveis para os outros decks do formato). As cartas de cada deck defines-as pondo as fotos na pasta do deck; a prioridade dá precedência sobre cartas partilhadas.</footer>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, code=200):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
            self._send("404", 404)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        deck = (form.get("deck") or [""])[0]
        if deck and path in ("/box", "/unbox"):
            with db.session() as con:
                _ensure(con)
                (box if path == "/box" else unbox)(con, deck)
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, *a):
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
