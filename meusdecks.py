"""Gera meusdecks.html — "Os meus decks".

Só os decks do André: os que segue (tabela `decks`) e os que tem montados com
lista vigiada (Blue Farm, Cloud cEDH, Pauper — via `watched`+`deck_collection`).

Por deck: estado (🔒 montado, quem segue/vigia), % que já tem, EVOLUÇÃO da lista
com datas (▲ entrou / ▼ saiu, dos snapshots — a mais recente à vista), e um
expansível "🃏 ver cartas" que mostra a lista com ARTE; as cartas que faltam
aparecem a CINZENTO. NÃO inventa nada.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import buildability as bd  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

FMT_LABEL = bd.FMT_LABEL
FMT_ORDER = bd.FMT_ORDER

# UMA chave de core por deck (variantes diferentes dariam diffs falsos ao misturar).
DECK_CORE = {
    "Izzet Affinity (Kappa Cannoneer)": "modern:affinity-kappa",
    "Grinding Station": "modern:grinding-station",
    "Cloud (Duel Commander)": "dc:cloud",
    "Jeskai Lessons": "standard:jeskai:wur",
    "Greasefang": "pioneer:greasefang:orzhov",
}

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a class="cur" href="meusdecks.html">🎴 Os meus decks</a>'
        '<a href="cobertura.html">🌐 Metagame</a>'
        '<a href="buildability.html">🔨 Montar</a>'
        '<a href="colecao_cor.html">🎨 Coleção</a></nav>')


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _owned_sid(con):
    """nome (frente) -> scryfall_id da edição que o André tem (para a arte)."""
    out = {}
    for r in con.execute("""SELECT c.name nm, cp.scryfall_id sid FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player'"""):
        out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    return out


def _img_map(con, names):
    """nome (frente) -> scryfall_id de uma impressão do catálogo (para o que falta)."""
    out = {}
    names = list(names)
    for i in range(0, len(names), 300):
        chunk = names[i:i + 300]
        ph = ",".join("?" for _ in chunk)
        for r in con.execute(
            f"""SELECT name nm, scryfall_id sid FROM cards
                 WHERE name IN ({ph}) AND digital = 0 GROUP BY name""", chunk):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    return out


def _timeline(snaps, limit=4):
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


def _cards(items, owned_map, osid, imgmap):
    """items = [(nome, qty)] -> [{nm, qty, have, sid}] (para o detalhe com arte)."""
    out = []
    for nm, q in items:
        have = owned_map.get(nm, 0) >= q
        out.append({"nm": nm, "qty": q, "have": have,
                    "sid": osid.get(nm) or imgmap.get(nm)})
    return sorted(out, key=lambda c: (c["have"], c["nm"]))  # faltas primeiro


def _watched_decks(con, osid, imgmap):
    out = []
    for r in con.execute("""SELECT w.id wid, w.label, w.format, dc.sub_collection balde
                              FROM watched w JOIN deck_collection dc ON dc.watched_id = w.id
                             ORDER BY w.label"""):
        snap = con.execute("SELECT cards FROM watched_snapshots WHERE watched_id = ? "
                           "ORDER BY taken_at DESC LIMIT 1", (r["wid"],)).fetchone()
        if not snap:
            continue
        want = defaultdict(int)
        for b, nm, q in json.loads(snap["cards"]):
            if (b in ("main", "") or b is None) and nm not in bd.BASICS:
                want[nm.split(" // ")[0]] += q
        owned = defaultdict(int)
        for o in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                                  JOIN cards c ON c.scryfall_id = cp.scryfall_id
                                  JOIN sub_collections s ON s.id = cp.sub_collection_id
                                 WHERE s.name = ? GROUP BY c.name""", (r["balde"],)):
            owned[o["nm"].split(" // ")[0]] += o["q"]
        need = sum(want.values())
        have = sum(min(q, owned.get(nm, 0)) for nm, q in want.items())
        out.append({"name": r["label"], "format": r["format"], "notes": None,
                    "need": need, "have": have, "pct": round(100 * have / need) if need else 0,
                    "missing": [], "cost": 0, "montado": True, "watched": True,
                    "evol": _evolution_watched(con, r["wid"]),
                    "cards": _cards(want.items(), owned, osid, imgmap)})
    return out


def _deck_card(d):
    col = "var(--add)" if d["pct"] >= 90 else "var(--gold)" if d["pct"] >= 60 else "var(--warn)"
    badges = ('<span class="bdg watch">👁️ vigiado</span>' if d.get("watched")
              else f'<span class="bdg src">{_source(d["notes"])}</span>')
    if d["montado"]:
        badges += '<span class="bdg on">🔒 montado</span>'
    miss = (f'faltam {len(d["missing"])} · {d["cost"]:.2f}€' if d.get("missing")
            else ("completo ✅" if d["pct"] >= 100 else ""))
    ev = d["evol"]
    if ev:
        def line(e):
            i = "".join(f'<span class="in">▲{html.escape(c)}</span>' for c in e["ins"])
            o = "".join(f'<span class="out">▼{html.escape(c)}</span>' for c in e["outs"])
            return f'<div class="evrow"><span class="evd">{e["date"]}</span>{i}{o}</div>'
        head = f'<div class="evnow"><span class="evt">📈 última alteração</span>{line(ev[0])}</div>'
        rest = "".join(line(e) for e in ev[1:])
        more = (f'<details class="evol"><summary>+ {len(ev) - 1} anteriores</summary>{rest}</details>'
                if rest else "")
        evol = head + more
    else:
        evol = '<div class="evx">📈 evolução — histórico a acumular</div>'
    # detalhe: cartas com arte (faltas a cinzento)
    grid = ""
    for c in d.get("cards", []):
        cls = "cd" if c["have"] else "cd miss"
        img = (f'<img loading="lazy" src="{_art(c["sid"])}" alt="">' if c["sid"]
               else '<div class="noimg"></div>')
        qb = f'<span class="cq">{c["qty"]}</span>' if c["qty"] > 1 else ""
        grid += f'<div class="{cls}" title="{html.escape(c["nm"])}">{img}{qb}</div>'
    detail = (f'<details class="cardsd"><summary>🃏 ver cartas ({d["have"]}/{d["need"]})</summary>'
              f'<div class="cards">{grid}</div></details>' if grid else "")
    return (
        f'<div class="deck"><div class="dtop"><b>{html.escape(d["name"])}</b>'
        f'<span class="pct" style="color:{col}">{d["pct"]}%</span></div>'
        f'<div class="badges">{badges}</div>'
        f'<div class="bar"><span style="width:{d["pct"]}%;background:{col}"></span></div>'
        f'<div class="mt">{d["have"]}/{d["need"]}{" · " + miss if miss else ""}</div>'
        f'{evol}{detail}</div>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "meusdecks.html")
    owned = owned_playable(con)
    osid = _owned_sid(con)
    try:
        montados = set(json.loads(
            (ROOT / "colecao_config.json").read_text(encoding="utf-8")).get("decks_montados", []))
    except Exception:
        montados = set()

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
        st = bd.deck_status(con, d["id"], owned)
        if st["need"] == 0:
            continue
        by_fmt[d["format"]].append({
            "name": d["name"], "notes": d["notes"], **st,
            "montado": d["name"] in montados, "watched": False,
            "evol": _evolution_core(con, DECK_CORE.get(d["name"])),
            "cards": _cards(st["full"], owned, osid, imgmap)})
    for d in _watched_decks(con, osid, imgmap):
        by_fmt[d["format"]].append(d)

    secs, subnav, n_total = "", "", 0
    for fmt in FMT_ORDER + [f for f in by_fmt if f not in FMT_ORDER]:
        decks = by_fmt.get(fmt)
        if not decks:
            continue
        decks.sort(key=lambda x: -x["pct"])
        n_total += len(decks)
        lbl = FMT_LABEL.get(fmt, fmt)
        subnav += f'<a href="#f-{fmt}">{html.escape(lbl)}</a>'
        cards = "".join(_deck_card(d) for d in decks)
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(lbl)} '
                 f'<span class="n">{len(decks)}</span></h2><div class="grid">{cards}</div></section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SUBNAV%", subnav)
                   .replace("%SECS%", secs).replace("%N%", str(n_total))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Os meus decks</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 h2{font-size:14px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
 .deck:hover{border-color:#37445a}
 .dtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px} .dtop b{font-size:15px} .pct{font-weight:800;font-size:16px}
 .badges{display:flex;flex-wrap:wrap;gap:5px;margin:7px 0} .bdg{font-size:11px;padding:2px 7px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .bdg.on{background:#123020;color:var(--add)} .bdg.watch{background:#2a2136;color:#c6a6ff}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:4px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .mt{color:var(--muted);font-size:12px;margin-bottom:6px}
 .evx{color:#5a6472;font-size:11px;margin-top:6px}
 .evnow{background:#0f141c;border:1px solid var(--line);border-radius:10px;padding:7px 9px;margin-top:6px}
 .evt{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
 .evol{margin-top:6px} .evol>summary,.cardsd>summary{cursor:pointer;color:var(--accent);font-size:12px}
 .evrow{display:flex;flex-wrap:wrap;gap:5px 6px;align-items:center;font-size:11px;padding:2px 0}
 .evd{color:var(--muted);min-width:70px;font-variant-numeric:tabular-nums} .in{color:var(--add)} .out{color:var(--warn)}
 .cardsd{margin-top:8px} .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
 .cd{position:relative;width:58px} .cd img,.cd .noimg{width:58px;height:81px;border-radius:4px;display:block;background:#0c0f14}
 .cd.miss img{filter:grayscale(1) brightness(.45)}
 .cd .cq{position:absolute;top:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 .cd.miss::after{content:"falta";position:absolute;bottom:2px;left:2px;right:2px;text-align:center;background:#7a1d1dd9;color:#fff;font-size:8px;border-radius:3px}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎴 Os meus decks</h1>
<div class="lead">%N% decks · estado, % que já tenho, evolução e cartas · dados de %TODAY%</div>
%TABS%
<div class="subnav">%SUBNAV%</div></header>
%SECS%
<footer>Só os teus decks. A % é da lista atual sobre a coleção. <b>Evolução</b>: o que entrou (▲) e saiu (▼), com datas. <b>Ver cartas</b>: a lista com arte — as que faltam ficam a cinzento. Atualiza diariamente.</footer>
</div></body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("meusdecks.html:", build(con))


if __name__ == "__main__":
    main()
