"""Gera reservedlist.html — a Reserved List cruzada com a coleção.

Mostra a Reserved List da Wizards (a flag `reserved` da Scryfall — não é
inventada) separada por EDIÇÃO, da mais recente para a mais antiga, só edições
reais (core/expansion — sem 30th Anniversary, World Championship, Collectors'
Edition, promos nem oversized). Por cada carta: quantas tenho em Inglês e em
Português, o valor (Cardmarket, via bulk grátis) e a evolução de preço. Cartas
de que não tenho nenhuma cópia aparecem SEM COR.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db as _db  # noqa: E402

# Só edições a sério: as impressões da Reserved List que interessam colecionar.
# memorabilia (30th Anniversary, World Championship Decks, Collectors' Edition,
# oversized), promo, from_the_vault e afins ficam de fora.
SET_TYPES = ("core", "expansion")

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a href="meusdecks.html">🎴 Os meus decks</a>'
        '<a href="metagame.html">🌐 Metagame</a>'
        '<a href="buildability.html">🔨 Montar</a>'
        '<a href="colecao_cor.html">🎨 Coleção</a></nav>')


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg"


def _eur(v):
    if v is None:
        return "—"
    if v >= 100:
        return f"{v:,.0f}€".replace(",", " ")
    if v >= 10:
        return f"{v:.1f}€"
    return f"{v:.2f}€"


def _spark(points):
    """Mini-gráfico SVG da evolução (lista de valores, do mais antigo ao mais
    recente) + variação %. Só quando há pelo menos 2 pontos."""
    vs = [p for p in points if p is not None]
    if len(vs) < 2:
        return ""
    lo, hi = min(vs), max(vs)
    rng = (hi - lo) or 1
    w, h = 66, 18
    step = w / (len(vs) - 1)
    pts = " ".join(f"{i*step:.1f},{h-1-(v-lo)/rng*(h-2):.1f}" for i, v in enumerate(vs))
    chg = (vs[-1] - vs[0]) / vs[0] * 100 if vs[0] else 0
    col = "var(--add)" if chg > 1 else "var(--warn)" if chg < -1 else "var(--muted)"
    sign = "+" if chg >= 0 else ""
    return (f'<svg class="sk" viewBox="0 0 {w} {h}" width="{w}" height="{h}" preserveAspectRatio="none">'
            f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.5"/></svg>'
            f'<span class="chg" style="color:{col}">{sign}{chg:.0f}%</span>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "reservedlist.html")
    marks = ",".join("?" * len(SET_TYPES))

    cards = con.execute(
        f"""SELECT scryfall_id sid, name, set_name, set_code, collector_number cn,
                   released_at rel, oracle_id
              FROM catalog.cards
             WHERE reserved = 1 AND digital = 0 AND set_type IN ({marks})
             ORDER BY rel DESC, set_name, name""", SET_TYPES).fetchall()

    # Posse por impressão e língua (inglês vs português).
    owned = defaultdict(lambda: {"en": 0, "pt": 0})
    for r in con.execute("SELECT scryfall_id sid, language lang, SUM(quantity) q "
                         "FROM copies GROUP BY scryfall_id, language"):
        k = "en" if (r["lang"] or "en") == "en" else "pt"
        owned[r["sid"]][k] += r["q"]

    # Valor de hoje (Cardmarket, nonfoil) por impressão.
    price = {r["scryfall_id"]: (r["trend"] if r["trend"] is not None else r["low"])
             for r in con.execute("SELECT scryfall_id, trend, low FROM price_latest "
                                  "WHERE source='cardmarket' AND finish='nonfoil'")}

    # Evolução: série de preços por impressão (do mais antigo ao mais recente).
    hist = defaultdict(list)
    for r in con.execute("SELECT scryfall_id sid, trend, low FROM price_history "
                         "WHERE source='cardmarket' AND finish='nonfoil' ORDER BY date"):
        hist[r["sid"]].append(r["trend"] if r["trend"] is not None else r["low"])

    total_rl = con.execute("SELECT COUNT(DISTINCT name) c FROM catalog.cards "
                           "WHERE reserved=1").fetchone()["c"]
    have_names, have_value = set(), 0.0

    # Agrupar por edição, mantendo a ordem (mais recente -> mais antiga).
    order, groups = [], defaultdict(list)
    for c in cards:
        if c["set_code"] not in groups:
            order.append((c["set_code"], c["set_name"], (c["rel"] or "")[:4]))
        groups[c["set_code"]].append(c)

    secs = ""
    for code, sname, year in order:
        rows = groups[code]
        rows.sort(key=lambda c: -(price.get(c["sid"]) or 0))
        n_have = 0
        cells = ""
        for c in rows:
            sid = c["sid"]
            o = owned.get(sid, {"en": 0, "pt": 0})
            en, pt = o["en"], o["pt"]
            has = en + pt > 0
            if has:
                n_have += 1
                have_names.add(c["name"])
                have_value += (price.get(sid) or 0) * (en + pt)
            val = price.get(sid)
            own = (f'<span class="en">{en} EN</span>' if en else "") + \
                  (f'<span class="pt">{pt} PT</span>' if pt else "")
            if not has:
                own = '<span class="no">não tens</span>'
            cells += (
                f'<div class="c {"have" if has else "miss"}" title="{html.escape(c["name"])}">'
                f'<img loading="lazy" src="{_art(sid)}" alt="">'
                f'<div class="nm">{html.escape(c["name"])}</div>'
                f'<div class="own">{own}</div>'
                f'<div class="val">{_eur(val)}</div>'
                f'<div class="ev">{_spark(hist.get(sid, []))}</div></div>')
        secs += (f'<section><h2>{html.escape(sname)} '
                 f'<span class="dim">{year} · tens {n_have}/{len(rows)}</span></h2>'
                 f'<div class="grid">{cells}</div></section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    head = (f'Tens <b>{len(have_names)}</b> de {total_rl} cartas da Reserved List · '
            f'valor da tua RL: <b>{_eur(have_value)}</b> · {len(cards)} impressões · dados de {today}')
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SECS%", secs)
                   .replace("%HEAD%", head), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reserved List</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b;--pt:#5b8cff}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px} .lead b{color:var(--ink)}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px} .tabs a:hover{border-color:var(--accent)}
 .filter{display:flex;gap:8px;align-items:center;margin:6px 0 4px} .filter button{background:var(--card);border:1px solid var(--line);color:var(--ink);border-radius:20px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer} .filter button.on{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 h2{font-size:15px;margin:20px 0 8px;border-bottom:1px solid var(--line);padding-bottom:5px} .dim{color:var(--muted);font-size:12px;font-weight:400}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
 .c{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px;display:grid;grid-template-columns:38px 1fr;grid-template-areas:"img nm" "img own" "val ev";gap:2px 8px;align-items:center}
 .c img{grid-area:img;width:38px;height:53px;border-radius:4px;display:block;background:#0c0f14}
 .c .nm{grid-area:nm;font-weight:600;font-size:12.5px;line-height:1.15;align-self:end}
 .c .own{grid-area:own;font-size:11px;align-self:start} .c .own span{margin-right:5px;font-weight:700}
 .c .own .en{color:var(--add)} .c .own .pt{color:var(--pt)} .c .own .no{color:#4a5666;font-weight:400}
 .c .val{grid-area:val;font-weight:800;font-size:13px;color:var(--gold)}
 .c .ev{grid-area:ev;display:flex;align-items:center;gap:4px;justify-content:flex-end} .c .ev .sk{opacity:.9} .c .ev .chg{font-size:10px;font-weight:700}
 /* SEM COR quando não tenho nenhuma cópia */
 .c.miss{opacity:.62} .c.miss img{filter:grayscale(1) brightness(.7)} .c.miss .val{color:var(--muted)}
 body.only .c.miss{display:none}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🏆 Reserved List</h1>
<div class="lead">%HEAD%</div>
%TABS%
<div class="filter"><button id="tgl" onclick="toggle()">Mostrar só as que tenho</button></div></header>
%SECS%
<footer>A Reserved List da Wizards (cartas que nunca serão reimpressas), pela flag oficial da Scryfall — separada por edição, da mais recente para a mais antiga, só edições reais (core/expansion; sem 30th Anniversary, World Championship, Collectors' Edition, promos ou oversized). Por carta: cópias em Inglês (verde) e Português (azul), valor de mercado (Cardmarket) e evolução de preço. Sem cor = não tens nenhuma. Atualiza diariamente — a evolução ganha pontos com os dias.</footer>
</div>
<script>
function toggle(){document.body.classList.toggle('only');
  const b=document.getElementById('tgl');const on=document.body.classList.contains('only');
  b.classList.toggle('on',on);b.textContent=on?'Mostrar todas':'Mostrar só as que tenho';
  try{localStorage.setItem('rl_only',on?'1':'');}catch(e){}}
try{if(localStorage.getItem('rl_only'))toggle();}catch(e){}
</script>
</body></html>"""


def main():
    with _db.session() as con:
        print("reservedlist.html:", build(con))


if __name__ == "__main__":
    main()
