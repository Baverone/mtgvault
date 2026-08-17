"""Gera colvalor.html — o valor de TODA a coleção, carta a carta.

O mesmo tratamento da Reserved List, mas para tudo o que o André tem: por carta,
quantas tem (Inglês/Português), o preço de hoje (Cardmarket, mínimo entre fontes),
a evolução e o valor de há ~1 mês. Agrupado por balde (sub-coleção), com subtotal
de cada um e o total geral. Os preços de tudo o que ele tem já são recolhidos
(entram em `prices.cards_of_interest`), por isso isto é só a vista.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db as _db  # noqa: E402
from reservedlist import _art, _eur, _spark, price_maps  # noqa: E402

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a href="meusdecks.html">🎴 Os meus decks</a>'
        '<a href="metagame.html">🌐 Metagame</a>'
        '<a href="buildability.html">🔨 Montar</a>'
        '<a href="colecao_cor.html">🎨 Coleção</a></nav>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "colvalor.html")
    price, month, hist = price_maps(con)

    # Posse por (balde, impressão, língua).
    subs = defaultdict(lambda: defaultdict(lambda: {"name": "", "set": "", "en": 0, "pt": 0}))
    for r in con.execute(
        """SELECT s.name sub, cp.scryfall_id sid, c.name nm, c.set_name setn,
                  cp.language lang, SUM(cp.quantity) q
             FROM copies cp
             JOIN catalog.cards c ON c.scryfall_id = cp.scryfall_id
             JOIN sub_collections s ON s.id = cp.sub_collection_id
            GROUP BY s.name, cp.scryfall_id, cp.language"""):
        d = subs[r["sub"]][r["sid"]]
        d["name"], d["set"] = r["nm"], r["setn"]
        d["en" if (r["lang"] or "en") == "en" else "pt"] += r["q"]

    # Subtotais por balde + total geral (e o total de há ~1 mês, p/ a variação).
    sub_tot, grand, grand_month = {}, 0.0, 0.0
    for sub, cards in subs.items():
        t = 0.0
        for sid, d in cards.items():
            qty = d["en"] + d["pt"]
            t += (price.get(sid) or 0) * qty
            if month.get(sid):
                grand_month += month[sid] * qty
        sub_tot[sub] = t
        grand += t

    secs = ""
    for balde in sorted(subs, key=lambda s: -sub_tot[s]):
        cards = subs[balde]
        rows = sorted(cards.items(),
                      key=lambda kv: -((price.get(kv[0]) or 0) * (kv[1]["en"] + kv[1]["pt"])))
        cells = ""
        for sid, d in rows:
            en, pt = d["en"], d["pt"]
            qty = en + pt
            u = price.get(sid)
            line = (u or 0) * qty
            m = month.get(sid)
            own = (f'<span class="en">{en} EN</span>' if en else "") + \
                  (f'<span class="pt">{pt} PT</span>' if pt else "")
            mon = ""
            if m and u is not None:
                chg = (u - m) / m * 100 if m else 0
                col = "var(--add)" if chg > 1 else "var(--warn)" if chg < -1 else "var(--muted)"
                sign = "+" if chg >= 0 else ""
                mon = (f'<div class="mon">há 1 mês {_eur(m)} · '
                       f'<b style="color:{col}">{sign}{chg:.0f}%</b></div>')
            unit = f'{qty}× · {_eur(u)}' if u is not None else f'{qty}× · sem preço'
            cells += (
                f'<div class="c" title="{html.escape(d["name"])} — {html.escape(d["set"] or "")}">'
                f'<img loading="lazy" src="{_art(sid)}" alt="">'
                f'<div class="nm">{html.escape(d["name"])}</div>'
                f'<div class="own">{own}</div>'
                f'<div class="val">{_eur(line)} <small>{unit}</small></div>'
                f'<div class="ev">{_spark(hist.get(sid, []))}</div>{mon}</div>')
        secs += (f'<section><h2>{html.escape(balde)} '
                 f'<span class="dim">{len(cards)} cartas · {_eur(sub_tot[balde])}</span></h2>'
                 f'<div class="grid">{cells}</div></section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    ncards = sum(d["en"] + d["pt"] for cards in subs.values() for d in cards.values())
    var = ""
    if grand_month:
        chg = (grand - grand_month) / grand_month * 100
        col = "var(--add)" if chg > 0.5 else "var(--warn)" if chg < -0.5 else "var(--muted)"
        var = f' · há 1 mês {_eur(grand_month)} (<b style="color:{col}">{"+" if chg>=0 else ""}{chg:.1f}%</b>)'
    head = f'Valor total: <b>{_eur(grand)}</b>{var} · {ncards} cartas · dados de {today}'
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SECS%", secs)
                   .replace("%HEAD%", head), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Valor da coleção</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b;--pt:#5b8cff}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px} .lead b{color:var(--ink)}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px} .tabs a:hover{border-color:var(--accent)}
 h2{font-size:15px;margin:20px 0 8px;border-bottom:1px solid var(--line);padding-bottom:5px} .dim{color:var(--muted);font-size:12px;font-weight:400}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
 .c{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px;display:grid;grid-template-columns:38px 1fr;grid-template-areas:"img nm" "img own" "val ev" "mon mon";gap:2px 8px;align-items:center}
 .c img{grid-area:img;width:38px;height:53px;border-radius:4px;display:block;background:#0c0f14}
 .c .nm{grid-area:nm;font-weight:600;font-size:12.5px;line-height:1.15;align-self:end}
 .c .own{grid-area:own;font-size:11px;align-self:start} .c .own span{margin-right:5px;font-weight:700}
 .c .own .en{color:var(--add)} .c .own .pt{color:var(--pt)}
 .c .val{grid-area:val;font-weight:800;font-size:14px;color:var(--gold)} .c .val small{color:var(--muted);font-weight:600;font-size:9px}
 .c .ev{grid-area:ev;display:flex;align-items:center;gap:4px;justify-content:flex-end} .c .ev .sk{opacity:.9} .c .ev .chg{font-size:10px;font-weight:700}
 .c .mon{grid-area:mon;font-size:10.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:3px;margin-top:2px} .c .mon b{font-weight:700}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>💰 Valor da coleção</h1>
<div class="lead">%HEAD%</div>
%TABS%</header>
%SECS%
<footer>Toda a coleção, balde a balde, com o valor de cada carta. Por carta: cópias em Inglês (verde) e Português (azul), o valor total (nº de cópias × preço mínimo de hoje do Cardmarket), a evolução e o de há ~1 mês (média de 30 dias, ou o valor exato quando a nossa história tiver 30 dias). O total de cada balde e o total geral estão nos cabeçalhos. Atualiza diariamente.</footer>
</div></body></html>"""


def main():
    with _db.session() as con:
        print("colvalor.html:", build(con))


if __name__ == "__main__":
    main()
