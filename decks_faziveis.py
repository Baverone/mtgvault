"""Gera decksfaziveis.html — os decks do top-10 do metagame que o André JÁ CONSEGUE
montar (>= X% das cartas). O mínimo (%) é ajustável em colecao_config.json
(`decks_faziveis_min_pct`, começa em 50; se for pouco, sobe-se). Reusa o ranking
(`meta_coverage._rank`, só Challenges/Showcases, 30 dias) e o grid com posse do
metagame (`metagame._grid`): a cor = tenho, a cinza = falta; + wantlist por deck.
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402
import metagame as mg  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

NAV = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
       '<a href="meusdecks.html">🎴 Decks vigiados</a>'
       '<a href="metagame.html">🌐 Metagame</a>'
       '<a class="cur" href="decksfaziveis.html">🛠️ Decks fazíveis</a>'
       '<a href="colecao_cor.html">📚 Binders</a>'
       '<a href="reservedlist.html">🏆 Reserved List</a></nav>')

_CSS = """
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 h2{font-size:14px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:8px}
 .deck>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:10px;list-style:none}
 .deck>summary::-webkit-details-marker{display:none} .deck>summary b{font-size:15px} .deck>summary::before{content:"▸";color:var(--muted);margin-right:6px} .deck[open]>summary::before{content:"▾"}
 .src{color:var(--muted);font-size:11px;margin-left:auto} .src a{color:var(--accent);text-decoration:none}
 .sbh{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin:8px 0 4px}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
 .cd{position:relative;width:60px} .cd img,.cd .noimg{width:60px;height:84px;border-radius:4px;display:block;background:#0c0f14}
 .cd .cq{position:absolute;top:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 .cd.miss img{filter:grayscale(1) brightness(.5)} .cd.have img{box-shadow:0 0 0 1.5px var(--add)}
 .cov{font-size:12px;font-weight:700;padding:1px 9px;border-radius:20px;margin-left:8px;flex:none;white-space:nowrap}
 .cov.add{background:#123a22;color:var(--add)} .cov.gold{background:#3a3312;color:var(--gold)} .cov.warn{background:#3a1c12;color:#e2795b}
 .wl{margin-top:10px;background:#160f0d;border:1px solid #3a2418;border-radius:8px;padding:8px 12px}
 .wl .wlh{color:#e2795b;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px}
 .wl ul{list-style:none;margin:0;padding:0;columns:2;column-gap:18px;font-size:12px} .wl li{color:var(--ink);padding:1px 0;break-inside:avoid}
 .lead2{color:var(--muted);font-size:13px;margin:8px 0}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
"""

_TMPL = ("""<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decks fazíveis</title><style>""" + _CSS + """</style></head><body><div class="wrap">
<header><h1>🛠️ Decks fazíveis</h1>
<div class="lead">Os decks do top-10 (Challenges/Showcases, 30 dias) que já tens a <b style="color:var(--add)">≥ %MIN%%</b> — os que consegues montar (ou quase). Cartas <b style="color:var(--add)">a cor</b> = tens, <b style="color:#8b97a6">a cinza</b> = faltam; wantlist por baixo. · dados de %TODAY%</div>
%NAV%<div class="subnav">%SUBNAV%</div></header>
%SECS%
<footer>Mínimo de %MIN%% ajustável em colecao_config.json (<code>decks_faziveis_min_pct</code>) — se for pouco, sobe-se. Só Challenges e Showcases contam. Atualiza diariamente.</footer>
</div></body></html>""")


def _min_pct():
    try:
        cfg = json.loads((ROOT / "colecao_config.json").read_text(encoding="utf-8"))
        return int(cfg.get("decks_faziveis_min_pct") or 50)
    except Exception:
        return 50


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "decksfaziveis.html")
    owned = set(mc.owned_available(con))   # só a coleção, SEM as cartas comprometidas com decks vigiados
    minpct = _min_pct()
    tcache = {}
    names = set()
    data = {}   # fmt -> [(nm, lst, have, tot, pct, miss)]
    for fmt, _t, n, _e in mc.FORMATS:
        df = mc._format_df(con, fmt)
        feas = []
        for aid, _s in mc._rank(con, fmt, n):
            lst = mg._latest_list(con, aid)
            if not lst:
                continue
            nb = [c for c, _q in lst["main"] if c not in mc.BASICS]
            tot = len(nb)
            have = sum(1 for c in nb if c.split(" // ")[0] in owned)
            pct = round(100 * have / tot) if tot else 0
            if pct < minpct:
                continue
            nm = mc._name_for(con, aid, df, tcache)
            miss = [(c, q) for c, q in lst["main"]
                    if c not in mc.BASICS and c.split(" // ")[0] not in owned]
            feas.append((nm, lst, have, tot, pct, miss))
            for c, _q in lst["main"] + lst["side"]:
                names.add(c.split(" // ")[0])
        feas.sort(key=lambda x: -x[4])   # % desc: os mais completos primeiro
        data[fmt] = feas
    imgmap = mg._img_map(con, names)

    subnav, secs = "", ""
    for fmt, _t, _n, _e in mc.FORMATS:
        feas = data.get(fmt) or []
        if not feas:
            continue
        lbl = mg.FMT_TITLE.get(fmt, fmt)
        subnav += f'<a href="#f-{fmt}">{html.escape(lbl)} {len(feas)}</a>'
        cards = ""
        for nm, lst, have, tot, pct, miss in feas:
            cc = "add" if pct >= 90 else "gold" if pct >= 60 else "warn"
            cov = f'<span class="cov {cc}">{have}/{tot} · {pct}%</span>'
            wl = ""
            if miss:
                items = "".join(f'<li>{q}× {html.escape(c)}</li>'
                                for c, q in sorted(miss, key=lambda x: (-x[1], x[0])))
                wl = (f'<div class="wl"><div class="wlh">🛒 faltam {len(miss)} cartas:</div>'
                      f'<ul>{items}</ul></div>')
            src = f'{lst["player"] or "?"} · {lst["date"]}'
            lk = (f' · <a href="{html.escape(lst["url"])}" target="_blank" rel="noopener">🔗</a>'
                  if lst.get("url") else "")
            sb = (f'<div class="sbh">Sideboard</div><div class="cards">{mg._grid(lst["side"], imgmap, owned)}</div>'
                  if lst["side"] else "")
            cards += (f'<details class="deck"><summary><b>{html.escape(nm)}</b>{cov}'
                      f'<span class="src">{html.escape(src)}{lk}</span></summary>'
                      f'<div class="cards">{mg._grid(lst["main"], imgmap, owned)}</div>{sb}{wl}</details>')
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(lbl)} '
                 f'<span class="n">{len(feas)}</span></h2>{cards}</section>')

    if not secs:
        secs = (f'<p class="lead2">Ainda não tens nenhum deck do top-10 a ≥ {minpct}%. '
                f'Baixa o mínimo em colecao_config.json (<code>decks_faziveis_min_pct</code>) para veres mais.</p>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%NAV%", NAV).replace("%SUBNAV%", subnav)
                   .replace("%SECS%", secs).replace("%MIN%", str(minpct))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print("decksfaziveis.html:", build(con))
