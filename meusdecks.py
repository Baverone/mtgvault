"""Gera meusdecks.html — "Os meus decks".

Só os decks do André: os que segue (tabela `decks`) e os que tem montados com
lista vigiada (Blue Farm, Cloud cEDH, Pauper — via `watched`+`deck_collection`).

Por deck: quem segue/vigia, % de completo, datas (última verificação / última
alteração), link à fonte, a EVOLUÇÃO da lista (▲ entrou / ▼ saiu, com datas, e
cada carta a VERDE se a tenho / VERMELHO se não), e a lista COMPLETA (main+side,
com básicas) em arte — verde = tenho, vermelho = falta. NÃO inventa nada.
"""
from __future__ import annotations

import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import buildability as bd  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

FMT_LABEL = bd.FMT_LABEL
FMT_ORDER = bd.FMT_ORDER

DECK_CORE = {
    "Izzet Affinity (Kappa Cannoneer)": "modern:affinity-kappa",
    "Grinding Station": "modern:grinding-station",
    "Cloud (Duel Commander)": "dc:cloud",
    "Jeskai Lessons": "standard:jeskai:wur",
    "Greasefang": "pioneer:greasefang:orzhov",
}

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a class="cur" href="meusdecks.html">🎴 Decks vigiados</a>'
        '<a href="metagame.html">🌐 Metagame</a>'
        '<a href="colecao_cor.html">📚 Binders</a><a href="reservedlist.html">🏆 Reserved List</a></nav>')


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _owned_sid(con):
    out = {}
    for r in con.execute("""SELECT c.name nm, cp.scryfall_id sid FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player'"""):
        out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    return out


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


def _timeline(snaps, limit=40):
    events = []
    for i in range(len(snaps) - 1):
        new, old = snaps[i][1], snaps[i + 1][1]
        ins = sorted(k[1] for k in set(new) | set(old) if new.get(k, 0) > old.get(k, 0))
        outs = sorted(k[1] for k in set(new) | set(old) if new.get(k, 0) < old.get(k, 0))
        if ins or outs:
            events.append({"date": snaps[i][0], "ins": ins, "outs": outs})
    return events[:limit]


def _evolution_core(con, core_key):
    if not core_key:
        return []
    snaps = [(r["taken_at"],
              {tuple(c[:2]): (c[2] if len(c) > 2 else 1) for c in json.loads(r["cards_json"])})
             for r in con.execute("SELECT taken_at, cards_json FROM core_snapshots "
                                  "WHERE core_key = ? ORDER BY taken_at DESC", (core_key,))]
    return _timeline(snaps)


def _evolution_watched(con, wid):
    rows = con.execute("SELECT taken_at, cards FROM watched_snapshots "
                       "WHERE watched_id = ? ORDER BY taken_at DESC", (wid,)).fetchall()
    snaps = [(r["taken_at"], {(b, nm): q for b, nm, q in json.loads(r["cards"])}) for r in rows]
    return _timeline(snaps)


def _source(notes):
    notes = notes or ""
    if "consenso" in notes:
        return "🧩 consenso"
    if "auto:" in notes:
        p = notes.split()
        return f"🎯 segue {p[2] if len(p) > 2 else '?'}"
    return "🎯 seguido"


def _target_link(con, notes):
    """Link para a decklist de origem (do #id na nota) e a data dela."""
    m = re.search(r"#(\d+)", notes or "")
    if not m:
        return None, None
    r = con.execute("SELECT url, event_date FROM decklists WHERE id = ?", (m.group(1),)).fetchone()
    return (r["url"] if r else None), (r["event_date"] if r else None)


def _owned_qty(con):
    """nome (frente) -> nº de cópias que o André tem (jogáveis, coleção toda)."""
    out = defaultdict(int)
    for r in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player' GROUP BY c.name"""):
        out[r["nm"].split(" // ")[0]] += r["q"]
    return out


def _cards(items, osid, imgmap, owned_qty):
    """items = [(nome, qty)] -> [{nm, qty, hq, state, sid}], contando CÓPIAS.
    hq = quantas dessas cópias o André tem (básicas = sempre suficientes). state:
    have (tem as que precisa) / part (tem algumas) / miss (não tem nenhuma)."""
    out = []
    for nm, q in items:
        oq = q if nm in bd.BASICS else owned_qty.get(nm, 0)
        hq = min(q, oq)
        state = "have" if hq >= q else ("part" if hq > 0 else "miss")
        out.append({"nm": nm, "qty": q, "hq": hq, "state": state,
                    "sid": osid.get(nm) or imgmap.get(nm)})
    return sorted(out, key=lambda c: ({"have": 0, "part": 1, "miss": 2}[c["state"]], c["nm"]))


def _watched_decks(con, osid, imgmap, owned_names):
    out = []
    for r in con.execute("""SELECT w.id wid, w.label, w.format, w.notes, w.last_checked, dc.sub_collection balde
                              FROM watched w JOIN deck_collection dc ON dc.watched_id = w.id
                             ORDER BY w.label"""):
        m = re.search(r"https?://\S+", r["notes"] or "")
        wurl = m.group(0) if m else None
        snap = con.execute("SELECT taken_at, cards FROM watched_snapshots WHERE watched_id = ? "
                           "ORDER BY taken_at DESC LIMIT 1", (r["wid"],)).fetchone()
        if not snap:
            continue
        main_i, side_i = defaultdict(int), defaultdict(int)
        for b, nm, q in json.loads(snap["cards"]):
            (side_i if b == "side" else main_i)[nm.split(" // ")[0]] += q
        oq = defaultdict(int)
        for o in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                                  JOIN cards c ON c.scryfall_id = cp.scryfall_id
                                  JOIN sub_collections s ON s.id = cp.sub_collection_id
                                 WHERE s.name = ? GROUP BY c.name""", (r["balde"],)):
            oq[o["nm"].split(" // ")[0]] += o["q"]
        evol = _evolution_watched(con, r["wid"])
        out.append({"name": r["label"], "format": r["format"], "source": "👁️ vigiado",
                    "main": _cards(list(main_i.items()), osid, imgmap, oq),
                    "side": _cards(list(side_i.items()), osid, imgmap, oq),
                    "evol": evol, "owned_names": set(oq),
                    "verif": r["last_checked"] or snap["taken_at"],
                    "alter": evol[0]["date"] if evol else None, "link": wurl})
    return out


def _deck_card(d):
    def cnt(cards):
        return sum(c["hq"] for c in cards), sum(c["qty"] for c in cards)
    mh, mt = cnt(d["main"])
    sh, st = cnt(d["side"])
    have, tot = mh + sh, mt + st          # POR CÓPIAS (ex.: 68/75), não distintas
    pct = round(100 * have / tot) if tot else 0
    col = "var(--add)" if pct >= 90 else "var(--gold)" if pct >= 60 else "var(--warn)"
    on = d.get("owned_names", set())
    meta = f'<span class="mi">🔄 verificado {d["verif"] or "—"}</span>'
    meta += f'<span class="mi">✏️ alterado {d["alter"] or "—"}</span>'
    if d.get("link"):
        meta += f'<a class="mi lk" href="{html.escape(d["link"])}" target="_blank" rel="noopener">🔗 lista ↗</a>'
    ev = d["evol"]
    if ev:
        def line(e):
            def chip(c, arrow):
                cls = "have" if (c in on or c in bd.BASICS) else "miss"
                return f'<span class="ec {cls}">{arrow}{html.escape(c)}</span>'
            body = "".join(chip(c, "▲") for c in e["ins"]) + "".join(chip(c, "▼") for c in e["outs"])
            return f'<div class="evrow"><span class="evd">{e["date"]}</span>{body}</div>'
        head = f'<div class="evnow"><span class="evt">📈 última alteração</span>{line(ev[0])}</div>'
        rest = "".join(line(e) for e in ev[1:4])
        more = (f'<details class="evol"><summary>+ {len(ev) - 1} anteriores</summary>{rest}</details>'
                if rest else "")
        evol = head + more
    else:
        evol = '<div class="evx">📈 evolução — histórico a acumular</div>'

    def grid(cards):
        g = ""
        for c in cards:
            img = (f'<img loading="lazy" src="{_art(c["sid"])}" alt="">' if c["sid"]
                   else '<div class="noimg"></div>')
            qb = (f'<span class="cq">{c["hq"]}/{c["qty"]}</span>' if c["qty"] > 1
                  else ('' if c["state"] == "have" else '<span class="cq">0/1</span>'))
            g += f'<div class="cd {c["state"]}" title="{html.escape(c["nm"])}">{img}{qb}</div>'
        return g
    detail = (f'<div class="cardshdr">🃏 main deck <span class="dim">({mh}/{mt})</span></div>'
              f'<div class="cards">{grid(d["main"])}</div>')
    if d["side"]:
        detail += (f'<div class="cardshdr sb">🎒 sideboard <span class="dim">({sh}/{st})</span></div>'
                   f'<div class="cards">{grid(d["side"])}</div>')
    return (
        f'<div class="deck" data-deck="{html.escape(d["name"])}"><div class="dtop">'
        f'<b>{html.escape(d["name"])}</b>'
        f'<span class="pct" style="color:{col}">{have}/{tot} · {pct}%</span></div>'
        f'<div class="badges"><span class="bdg src">{d["source"]}</span>'
        f'<button class="updbtn" onclick="markUpd(this)">atualizado</button></div>'
        f'<div class="bar"><span style="width:{pct}%;background:{col}"></span></div>'
        f'<div class="meta">{meta}</div>'
        f'<div class="upd"></div>'
        f'{evol}{detail}</div>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "meusdecks.html")
    owned_names = set(owned_playable(con))
    owned_qty = _owned_qty(con)
    osid = _owned_sid(con)

    rows = list(con.execute("SELECT id, name, format, notes FROM decks"))
    allnames = set()
    for d in rows:
        for r in con.execute("SELECT card_name nm FROM deck_cards WHERE deck_id=?", (d["id"],)):
            allnames.add(r["nm"].split(" // ")[0])
    for r in con.execute("""SELECT ws.cards FROM watched_snapshots ws
                             JOIN deck_collection dc ON dc.watched_id = ws.watched_id"""):
        for b, nm, q in json.loads(r["cards"]):
            allnames.add(nm.split(" // ")[0])
    imgmap = _img_map(con, allnames)

    by_fmt = defaultdict(list)
    for d in rows:
        main_items = [(r["nm"], r["q"]) for r in con.execute(
            "SELECT card_name nm, SUM(quantity) q FROM deck_cards WHERE deck_id=? "
            "AND board IN ('main','') GROUP BY card_name", (d["id"],))]
        side_items = [(r["nm"], r["q"]) for r in con.execute(
            "SELECT card_name nm, SUM(quantity) q FROM deck_cards WHERE deck_id=? "
            "AND board='side' GROUP BY card_name", (d["id"],))]
        if not main_items and not side_items:
            continue
        link, ldate = _target_link(con, d["notes"])
        # Decks vigiados: só os que têm LINK e/ou JOGADOR vigiado. Exclui os de
        # puro consenso (ex.: Cloud Duel Commander), que não têm nenhum dos dois.
        if not link and "auto:" not in (d["notes"] or ""):
            continue
        evol = _evolution_core(con, DECK_CORE.get(d["name"]))
        core_dates = [r["taken_at"] for r in con.execute(
            "SELECT MAX(taken_at) taken_at FROM core_snapshots WHERE core_key=?",
            (DECK_CORE.get(d["name"], ""),))] if DECK_CORE.get(d["name"]) else []
        by_fmt[d["format"]].append({
            "name": d["name"], "format": d["format"], "source": _source(d["notes"]),
            "main": _cards(main_items, osid, imgmap, owned_qty),
            "side": _cards(side_items, osid, imgmap, owned_qty), "evol": evol,
            "owned_names": owned_names,
            "verif": (core_dates[0] if core_dates and core_dates[0] else ldate),
            "alter": evol[0]["date"] if evol else None, "link": link})
    for d in _watched_decks(con, osid, imgmap, owned_names):
        by_fmt[d["format"]].append(d)

    # Lista ATUAL de cada deck (nome + imagem), main+side, um por nome. O cliente
    # compara-a com a lista de quando o André marcou "atualizado" e mostra o diff
    # LÍQUIDO (entram / saem). Por ser diferença de conjuntos, trata sozinha as
    # re-entradas: sai e volta = sem mudança; entra e sai = sem mudança.
    deckcur = {}
    for decks in by_fmt.values():
        for d in decks:
            seen = {}
            for c in d["main"] + d["side"]:
                f = c["nm"].split(" // ")[0]
                seen.setdefault(f, c["sid"])
            deckcur[d["name"]] = [[f, s] for f, s in seen.items()]

    secs, subnav, n_total = "", "", 0
    for fmt in FMT_ORDER + [f for f in by_fmt if f not in FMT_ORDER]:
        decks = by_fmt.get(fmt)
        if not decks:
            continue
        decks.sort(key=lambda x: -(sum(c["hq"] for c in x["main"] + x["side"])
                                    / max(1, sum(c["qty"] for c in x["main"] + x["side"]))))
        n_total += len(decks)
        lbl = FMT_LABEL.get(fmt, fmt)
        subnav += f'<a href="#f-{fmt}">{html.escape(lbl)}</a>'
        cards = "".join(_deck_card(d) for d in decks)
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(lbl)} '
                 f'<span class="n">{len(decks)}</span></h2><div class="grid">{cards}</div></section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SUBNAV%", subnav)
                   .replace("%SECS%", secs).replace("%N%", str(n_total))
                   .replace("%DECKCUR%", json.dumps(deckcur, ensure_ascii=False))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decks vigiados</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 h2{font-size:14px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
 .deck:hover{border-color:#37445a}
 .dtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px} .dtop b{font-size:15px} .pct{font-weight:800;font-size:16px}
 .badges{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:7px 0} .bdg{font-size:11px;padding:2px 7px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .updbtn{margin-left:auto;font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;border:1px solid var(--line);background:#1a2230;color:var(--muted);cursor:pointer}
 .updbtn:hover{border-color:var(--accent);color:var(--ink)} .updbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .upd:empty{display:none}
 .upend{background:#241a10;border:1px solid #6a4f2f;border-radius:10px;padding:7px 9px;margin:6px 0;font-size:11.5px;color:#f0dcc0} .upend b{color:var(--gold)}
 .uprow{display:flex;flex-wrap:wrap;gap:4px 5px;align-items:center;padding:2px 0}
 .upd-d{color:var(--muted);min-width:66px;font-variant-numeric:tabular-nums}
 .uok{color:var(--add);font-size:11.5px;margin:5px 0}
 .chgbox{background:#0f141c;border:1px solid #37445a;border-radius:10px;padding:8px 10px;margin:6px 0}
 .chglbl{color:var(--gold);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;font-weight:700}
 .chgi{display:flex;gap:9px;align-items:flex-start}
 .chgrp{flex:1;min-width:0} .chgrp>b{display:block;font-size:11px;margin-bottom:4px} .chgrp>b.in{color:var(--add)} .chgrp>b.out{color:var(--warn)}
 .chc-row{display:flex;flex-wrap:wrap;gap:3px}
 .chc{width:42px;height:59px;border-radius:4px;object-fit:cover;display:block}
 .chc.in{box-shadow:0 0 0 2px var(--add)} .chc.out{box-shadow:0 0 0 2px var(--warn);filter:grayscale(.3) brightness(.82)}
 .chc.noi{background:#0c0f14} .chbar{width:1px;align-self:stretch;background:var(--line)}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:4px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .meta{display:flex;flex-wrap:wrap;gap:4px 10px;color:var(--muted);font-size:11px;margin:5px 0} .mi.lk{color:var(--accent);text-decoration:none}
 .evx{color:#5a6472;font-size:11px;margin-top:6px}
 .evnow{background:#0f141c;border:1px solid var(--line);border-radius:10px;padding:7px 9px;margin-top:6px}
 .evt{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
 .evol{margin-top:6px} .evol>summary,.cardsd>summary{cursor:pointer;color:var(--accent);font-size:12px}
 .evrow{display:flex;flex-wrap:wrap;gap:4px 5px;align-items:center;font-size:11px;padding:2px 0}
 .evd{color:var(--muted);min-width:70px;font-variant-numeric:tabular-nums}
 .ec{padding:0 4px;border-radius:5px} .ec.have{color:var(--add);background:#0f2418} .ec.miss{color:#ff8f8f;background:#2a1414}
 .cardshdr{margin-top:9px;font-size:12px;color:var(--accent)} .cardshdr .dim{color:var(--muted)} .cardshdr.sb{color:var(--gold)}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
 .cd{position:relative;width:58px;border-radius:5px} .cd img,.cd .noimg{width:58px;height:81px;border-radius:4px;display:block;background:#0c0f14}
 .cd.have{box-shadow:0 0 0 2px var(--add)} .cd.part{box-shadow:0 0 0 2px var(--gold)} .cd.part img{filter:brightness(.82)}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.7) brightness(.6)}
 .cd .cq{position:absolute;top:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎴 Decks vigiados</h1>
<div class="lead">%N% decks com link e/ou jogador vigiado · % de completo, datas, evolução e a lista completa · dados de %TODAY%</div>
%TABS%
<div class="subnav">%SUBNAV%</div></header>
%SECS%
<footer><b>Main deck</b> e <b>sideboard</b> à parte, contados por <b>cópias</b> (ex.: 68/75, não por cartas diferentes): <b style="color:var(--add)">verde = tens as que precisas</b>, <b style="color:var(--gold)">âmbar = tens algumas</b> (mostra 2/4), <b style="color:var(--warn)">vermelho = não tens</b>. Na evolução, cada carta que entrou (▲) ou saiu (▼) está verde se a tens, vermelha se não. Datas: 🔄 última verificação · ✏️ última alteração. A caixa <b>⇄ trocas por fazer</b> mostra, em imagem, as cartas a <b style="color:var(--add)">meter (▲)</b> e a <b style="color:var(--warn)">tirar (▼)</b> para o teu deck físico ficar igual à lista — é o <b>diff líquido</b> desde a última vez que marcaste <b>atualizado</b> (se uma carta sai e volta, ou entra e sai, não conta). Marcas atualizado quando sincronizares; volta a acumular quando a lista mudar. Atualiza diariamente.</footer>
</div>
<script>
const DECKCUR=%DECKCUR%;
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function art(sid){return sid?('https://cards.scryfall.io/small/front/'+sid[0]+'/'+sid[1]+'/'+sid+'.jpg'):'';}
function ackKey(n){return 'md_ack_'+n;}
function cimg(name,sid,cls){return sid?('<img class="chc '+cls+'" loading="lazy" src="'+art(sid)+'" title="'+esc(name)+'">'):('<span class="chc '+cls+' noi" title="'+esc(name)+'"></span>');}
function renderChg(el){
  const n=el.dataset.deck, cur=DECKCUR[n]||[];
  const box=el.querySelector('.upd'), btn=el.querySelector('.updbtn');
  if(!cur.length){if(btn)btn.style.display='none';if(box)box.innerHTML='';return;}
  const curNames=new Set(cur.map(p=>p[0]));
  // Baseline: a lista de quando marcou "atualizado". 1ª vez = assume sincronizado.
  let ack=null; try{ack=JSON.parse(localStorage.getItem(ackKey(n)));}catch(e){}
  if(!Array.isArray(ack)){try{localStorage.setItem(ackKey(n),JSON.stringify(cur));}catch(e){} ack=cur;}
  const ackNames=new Set(ack.map(p=>p[0]));
  const entra=cur.filter(p=>!ackNames.has(p[0]));   // na lista atual, não na marcada
  const saem=ack.filter(p=>!curNames.has(p[0]));    // na marcada, já não na atual
  if(!entra.length&&!saem.length){
    if(box)box.innerHTML='<div class="uok">✓ sem trocas por fazer</div>';
    if(btn){btn.textContent='✓ atualizado';btn.classList.add('done');}
    return;
  }
  let h='<div class="chgbox"><div class="chglbl">⇄ trocas por fazer (até marcares atualizado)</div><div class="chgi">'
    +'<span class="chgrp"><b class="in">▲ metes '+entra.length+'</b><span class="chc-row">'+entra.map(p=>cimg(p[0],p[1],'in')).join('')+'</span></span>'
    +'<span class="chbar"></span>'
    +'<span class="chgrp"><b class="out">▼ tiras '+saem.length+'</b><span class="chc-row">'+saem.map(p=>cimg(p[0],p[1],'out')).join('')+'</span></span>'
    +'</div></div>';
  if(box)box.innerHTML=h;
  if(btn){btn.textContent='marcar atualizado';btn.classList.remove('done');}
}
function markUpd(btn){
  const el=btn.closest('.deck'),n=el.dataset.deck;
  try{localStorage.setItem(ackKey(n),JSON.stringify(DECKCUR[n]||[]));}catch(e){}
  renderChg(el);
}
document.querySelectorAll('.deck[data-deck]').forEach(renderChg);
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("meusdecks.html:", build(con))


if __name__ == "__main__":
    main()
