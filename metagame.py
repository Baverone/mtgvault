"""Gera metagame.html — só para VISUALIZAR o metagame.

Por formato, o top-10 de arquétipos (ponderado por torneio, de meta_coverage),
e a lista COMPLETA (mais recente) de cada um com ARTE. SEM percentagem do que o
André tem — é só para ver o metagame. Os decks a EMERGIR aparecem no topo com
link para a lista. As staples que faltam NÃO estão aqui (isso é na Lista de
Compras). Listas colapsáveis (a arte só carrega ao abrir). NÃO inventa nada.
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402

FMT_TITLE = {f[0]: f[1] for f in mc.FORMATS}

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a href="meusdecks.html">🎴 Decks vigiados</a>'
        '<a class="cur" href="metagame.html">🌐 Metagame</a>'
        '<a href="decksfaziveis.html">🛠️ Decks fazíveis</a>'
        '<a href="colecao_cor.html">📚 Binders</a><a href="reservedlist.html">🏆 Reserved List</a></nav>')


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _img_map(con, names):
    out = {}
    names = list(names)
    for i in range(0, len(names), 300):
        chunk = names[i:i + 300]
        ph = ",".join("?" for _ in chunk)
        for r in con.execute(f"""SELECT name nm, scryfall_id sid FROM cards
                                  WHERE name IN ({ph}) AND digital = 0 GROUP BY name""", chunk):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    return out


def _latest_list(con, aid):
    r = con.execute("SELECT id, player, event_date, url FROM decklists WHERE archetype_id = ? "
                    "ORDER BY event_date DESC, id DESC LIMIT 1", (aid,)).fetchone()
    if not r:
        return None
    main, side = [], []
    for c in con.execute("SELECT card_name nm, quantity q, board b FROM decklist_cards "
                         "WHERE decklist_id = ? ORDER BY quantity DESC, card_name", (r["id"],)):
        (side if c["b"] == "side" else main).append((c["nm"], c["q"]))
    return {"player": r["player"], "date": r["event_date"], "url": r["url"], "main": main, "side": side}


def _grid(cards, imgmap, owned):
    """Cartas do deck: a cor as que o André TEM (ou básicas), cinza as que faltam."""
    g = ""
    for nm, q in cards:
        front = nm.split(" // ")[0]
        cls = "have" if (front in owned or front in mc.BASICS or nm in mc.BASICS) else "miss"
        sid = imgmap.get(front)
        img = (f'<img loading="lazy" src="{_art(sid)}" alt="">' if sid else '<div class="noimg"></div>')
        qb = f'<span class="cq">{q}</span>' if q > 1 else ""
        g += f'<div class="cd {cls}" title="{html.escape(nm)}">{img}{qb}</div>'
    return g


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "metagame.html")
    owned = set(mc.owned_playable(con))   # cartas que o André tem (para colorir)
    tcache = {}
    data = {}  # fmt -> [(name, list)]
    names = set()
    for fmt, _title, n, _extras in mc.FORMATS:
        df = mc._format_df(con, fmt)
        decks = []
        for aid, _score in mc._rank(con, fmt, n):
            lst = _latest_list(con, aid)
            if not lst:
                continue
            nm = mc._name_for(con, aid, df, tcache)
            decks.append((nm, lst))
            for c, _q in lst["main"] + lst["side"]:
                names.add(c.split(" // ")[0])
        data[fmt] = decks
    imgmap = _img_map(con, names)

    # emergentes (com link)
    em = mc.emerging_decks(con)
    em_html = ""
    if em:
        rows = ""
        for e in em:
            lk = (f'<a href="{html.escape(e["url"])}" target="_blank" rel="noopener">🔗 lista ↗</a>'
                  if e.get("url") else "")
            rows += (f'<li><span class="ef">{html.escape(FMT_TITLE.get(e["fmt"], e["fmt"]))}</span> '
                     f'<b>{html.escape(e["name"])}</b> {lk} '
                     f'<span class="dim">⚖️ {e["score"]} · {html.escape(e["ev"] or "")}</span></li>')
        em_html = ('<section class="emerging"><h2>🌱 Decks a emergir '
                   '<span class="dim">(fora do top-10, em torneios de peso)</span></h2>'
                   f'<ul class="eml">{rows}</ul></section>')

    subnav, secs = "", ""
    sel = {}   # nome -> {fmt, cards:[[nome, qty, sid]]}  (para selecionar p/ a Lista de Compras)
    staples = {}   # carta em falta -> {decks: nº de wantlists, fmts:set, qty:max} (staples a comprar)
    for fmt, _title, _n, _extras in mc.FORMATS:
        decks = data.get(fmt)
        if not decks:
            continue
        lbl = FMT_TITLE.get(fmt, fmt)
        subnav += f'<a href="#f-{fmt}">{html.escape(lbl)}</a>'
        cards = ""
        for nm, lst in decks:
            sel[nm] = {"fmt": fmt, "cards": [[c, q, imgmap.get(c.split(" // ")[0])]
                                             for c, q in lst["main"] if c not in mc.BASICS]}
            # % que o André TEM do deck: cartas distintas não-básicas do main
            nb = [c for c, _q in lst["main"] if c not in mc.BASICS]
            tot = len(nb)
            have = sum(1 for c in nb if c.split(" // ")[0] in owned)
            pct = round(100 * have / tot) if tot else 0
            cc = "add" if pct >= 90 else "gold" if pct >= 60 else "warn"
            cov = f'<span class="cov {cc}">{have}/{tot} · {pct}%</span>'
            # wantlist: as cartas não-básicas do main que o André NÃO tem
            miss = [(c, q) for c, q in lst["main"]
                    if c not in mc.BASICS and c.split(" // ")[0] not in owned]
            for c, q in miss:   # acumula POR FORMATO para as "staples que faltam"
                fs = staples.setdefault(fmt, {})
                s = fs.setdefault(c, {"decks": 0, "qty": 1})
                s["decks"] += 1
                s["qty"] = max(s["qty"], q)
            wl = ""
            if miss:
                items = "".join(f'<li>{q}× {html.escape(c)}</li>'
                                for c, q in sorted(miss, key=lambda x: (-x[1], x[0])))
                wl = (f'<div class="wl"><div class="wlh">🛒 faltam {len(miss)} cartas:</div>'
                      f'<ul>{items}</ul></div>')
            src = f'{lst["player"] or "?"} · {lst["date"]}'
            lk = (f' · <a href="{html.escape(lst["url"])}" target="_blank" rel="noopener">🔗</a>'
                  if lst.get("url") else "")
            sb = (f'<div class="sbh">Sideboard</div><div class="cards">{_grid(lst["side"], imgmap, owned)}</div>'
                  if lst["side"] else "")
            cards += (
                f'<details class="deck"><summary>'
                f'<button class="add" data-deck="{html.escape(nm)}" title="adicionar à Lista de Compras">➕</button>'
                f'<b>{html.escape(nm)}</b>{cov}'
                f'<span class="src">{html.escape(src)}{lk}</span></summary>'
                f'<div class="cards">{_grid(lst["main"], imgmap, owned)}</div>{sb}{wl}</details>')
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(lbl)} '
                 f'<span class="n">{len(decks)}</span></h2>{cards}</section>')

    # Staples que faltam, POR FORMATO, ordenadas por preço (mais caras primeiro).
    price_cache = {}
    def _price(c):
        if c not in price_cache:
            price_cache[c] = mc._visual(con, c, 0).get("unit") or 0
        return price_cache[c]
    stap_secs, n_stap = "", 0
    for fmt, _t, _n, _e in mc.FORMATS:
        fs = staples.get(fmt, {})
        top = [c for c, s in fs.items() if s["decks"] >= 2]
        if not top:
            continue
        top.sort(key=lambda c: (-_price(c), -fs[c]["decks"], c))   # preço desc
        n_stap += len(top)
        cells, ftot = "", 0.0
        for c in top:
            s = fs[c]
            unit = _price(c)
            ftot += unit * s["qty"]
            pzt = "" if not unit else ("&lt;1€" if unit < 1 else f"{unit:.0f}€")
            pz = f'<span class="pz2">{pzt}</span>' if pzt else ''
            sid = imgmap.get(c.split(" // ")[0])
            img = (f'<img loading="lazy" src="{_art(sid)}" alt="">' if sid
                   else '<div class="noimg"></div>')
            cells += (f'<div class="cd miss stap" '
                      f'title="{html.escape(c)} — {s["decks"]} decks · {s["qty"]}× · {unit:.2f}€">'
                      f'{img}<span class="cq gold">{s["decks"]}×</span>{pz}</div>')
        lbl = FMT_TITLE.get(fmt, fmt)
        stap_secs += (f'<h3 class="staph">{html.escape(lbl)} <span class="n">{len(top)}</span> '
                      + f'<span class="dim">≈ {ftot:,.0f}€</span></h3>'.replace(",", " ")
                      + f'<div class="cards">{cells}</div>')
    if n_stap:
        subnav += '<a href="#f-staples">🛒 Staples que faltam</a>'
        secs += (f'<section id="f-staples"><h2>🛒 Staples que te faltam '
                 f'<span class="n">{n_stap}</span></h2>'
                 f'<div class="lead2">Por formato, as cartas em falta que aparecem em ≥2 decks do top-10, '
                 f'ordenadas por preço (mais caras primeiro). Canto sup. = nº de decks; '
                 f'canto inf. = preço da + barata.</div>{stap_secs}</section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SUBNAV%", subnav)
                   .replace("%EMERGING%", em_html).replace("%SECS%", secs)
                   .replace("%SEL%", json.dumps(sel, ensure_ascii=False)).replace("%TODAY%", today),
                   encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Metagame</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 h2{font-size:14px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .emerging{background:#141b12;border:1px solid #2c3a1f;border-radius:12px;padding:12px 16px;margin-bottom:10px}
 .emerging h2{margin:0 0 6px;color:var(--ink)} .eml{list-style:none;margin:0;padding:0} .eml li{padding:4px 0;border-top:1px solid #2c3a1f} .eml li:first-child{border-top:0}
 .ef{display:inline-block;min-width:74px;color:var(--add);font-size:11px;text-transform:uppercase} .dim{color:var(--muted);font-size:12px} .eml a{color:var(--accent);text-decoration:none;font-size:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:8px}
 .deck>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:10px;list-style:none}
 .deck>summary::-webkit-details-marker{display:none} .deck>summary b{font-size:15px} .deck>summary::before{content:"▸";color:var(--muted);margin-right:6px} .deck[open]>summary::before{content:"▾"}
 .src{color:var(--muted);font-size:11px;margin-left:auto} .src a{color:var(--accent);text-decoration:none}
 .add{background:#1b2c4d;border:1px solid var(--accent);color:var(--accent);border-radius:8px;font-size:12px;font-weight:700;padding:1px 8px;cursor:pointer;margin-right:8px;flex:none} .add.on{background:var(--add);border-color:var(--add);color:#06210f}
 .selbar{position:sticky;bottom:10px;margin-top:14px;background:#12305a;border:1px solid var(--accent);border-radius:12px;padding:9px 14px;font-size:13px;display:none;align-items:center;gap:10px} .selbar a{color:#cfe0ff;font-weight:700}
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
 .cq.gold{background:var(--gold);color:#1a1200;font-size:11px;padding:0 4px} .stap img{filter:grayscale(1) brightness(.72)!important}
 .lead2{color:var(--muted);font-size:12px;margin:2px 0 10px}
 .cd .pz2{position:absolute;bottom:1px;left:1px;right:1px;background:#000d;color:var(--add);font-size:9px;font-weight:700;text-align:center;padding:0 2px;border-radius:0 0 4px 4px}
 .staph{font-size:13px;margin:16px 0 5px;color:var(--ink);text-transform:none;letter-spacing:0} .staph .n{color:#4a5666} .staph .dim{font-weight:400}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🌐 Metagame</h1>
<div class="lead">Top-10 de cada formato (ponderado por torneio) · a lista mais recente de cada, com a <b style="color:var(--add)">% que já tens</b> — cartas <b style="color:var(--add)">a cor</b> = tens, <b style="color:#8b97a6">a cinza</b> = faltam · dados de %TODAY%</div>
%TABS%<div class="subnav">%SUBNAV%</div></header>
%EMERGING%
%SECS%
<div class="selbar" id="selbar"></div>
<footer>Só para visualizar o metagame: abre um deck para ver a lista completa. Carrega ➕ para o <b>adicionar à Lista de Compras</b> (fica no teu navegador; ➕ adiciona, ✓ tira). Os decks a emergir têm link. Atualiza diariamente.</footer>
</div>
<script>
const SEL=%SEL%, KEY='mtg_sel';
let _mem=null;
function get(){if(_mem)return _mem;try{return JSON.parse(localStorage.getItem(KEY)||'{}');}catch(e){return {};}}
function set(o){_mem=o;try{localStorage.setItem(KEY,JSON.stringify(o));}catch(e){}}
function refresh(){
  const cur=get();
  document.querySelectorAll('.add').forEach(b=>{const dn=b.dataset.deck;const on=dn in cur;b.classList.toggle('on',on);b.textContent=on?'✓':'➕';});
  const n=Object.keys(cur).length, bar=document.getElementById('selbar');
  if(n){bar.style.display='flex';bar.innerHTML=n+' deck'+(n>1?'s':'')+' selecionado'+(n>1?'s':'')+' &nbsp; <a href="buildability.html">→ ver na Lista de Compras</a> &nbsp; <a href="#" id="clr">limpar</a>';}
  else bar.style.display='none';
}
document.addEventListener('click',e=>{
  if(e.target.classList.contains('add')){e.preventDefault();e.stopPropagation();
    const dn=e.target.dataset.deck,cur=get();
    if(dn in cur)delete cur[dn]; else if(SEL[dn])cur[dn]=SEL[dn];
    set(cur);refresh();}
  if(e.target.id==='clr'){e.preventDefault();set({});refresh();}
});
refresh();
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("metagame.html:", build(con))


if __name__ == "__main__":
    main()
