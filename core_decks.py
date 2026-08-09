"""Gera a pagina Core Decks (coredecks.html) do mtgvault.

Para cada deck-'core' que o Andre segue por formato mostra:
- decks de CONSENSO (procurados por mim): a lista-padrao (main+SB) calculada das
  listas premier em vault.db, com precos, + tracking de alteracoes em
  `core_snapshots` (marca quando o padrao muda e o diff);
- decks VIGIADOS (lista de um jogador): a ultima lista do jogador (watched_snapshots)
  com link, data e diff da ultima mudanca.

Corre a mao com `python core_decks.py`, ou e chamado pelo daily.py (step "core-decks").
Dados so de vault.db — nunca inventa listas nem precos.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db  # noqa: E402

BASICS = {"Island", "Plains", "Swamp", "Mountain", "Forest",
          "Snow-Covered Island", "Snow-Covered Plains", "Snow-Covered Swamp",
          "Snow-Covered Mountain", "Snow-Covered Forest"}

# Preto (fontes+cartas) para separar Jeskai WUR (Lessons) de WUBR (4C).
BLACK = {
    "Swamp", "Blood Crypt", "Watery Grave", "Godless Shrine", "Undercity Sewers",
    "Gloomlake Verge", "Bleachbone Verge", "Shattered Sanctum",
    "Duress", "Deadly Cover-Up", "Together as One", "Nowhere to Run",
}

FMT_ORDER = [("modern", "Modern"), ("pioneer", "Pioneer"), ("standard", "Standard"),
             ("legacy", "Legacy"), ("premodern", "Premodern"),
             ("duel-commander", "Duel-Commander"), ("cedh", "cEDH"), ("pauper", "Pauper")]


# ---------------------------------------------------------------- selectores
def _by_tag(con, tag, fmt):
    return [r[0] for r in con.execute(
        """SELECT DISTINCT t.decklist_id FROM decklist_tags t JOIN decklists d ON d.id=t.decklist_id
           WHERE t.name=? AND d.format=?""", (tag, fmt))]


def _by_label(con, label, fmt):
    return [r[0] for r in con.execute(
        """SELECT d.id FROM decklists d JOIN archetypes a ON a.id=d.archetype_id
           WHERE a.label=? AND d.format=?""", (label, fmt))]


def _by_card(con, card, fmt):
    return [r[0] for r in con.execute(
        """SELECT DISTINCT dc.decklist_id FROM decklist_cards dc JOIN decklists d ON d.id=dc.decklist_id
           WHERE dc.card_name=? AND d.format=?""", (card, fmt))]


def _by_card_main(con, card, fmt, minq=1):
    return [r[0] for r in con.execute(
        """SELECT DISTINCT dc.decklist_id FROM decklist_cards dc JOIN decklists d ON d.id=dc.decklist_id
           WHERE dc.card_name=? AND d.format=? AND dc.board='main' AND dc.quantity>=?""",
        (card, fmt, minq))]


def _has_black(con, did):
    ph = ",".join("?" * len(BLACK))
    return con.execute(
        f"SELECT 1 FROM decklist_cards WHERE decklist_id=? AND card_name IN ({ph}) LIMIT 1",
        [did, *BLACK]).fetchone() is not None


# ---------------------------------------------------------------- precos
def _prices(con):
    """Mapa nome->EUR. card_price (em vault.db) manda; o catalogo (price_latest,
    via ATTACH) preenche buracos MAS pode nao existir (ex.: GitHub Actions nao tem
    catalog.db) — por isso e opcional e nunca rebenta."""
    price = {r["card_name"]: r["eur"] for r in con.execute("SELECT card_name, eur FROM card_price")
             if r["eur"] is not None}
    try:
        for r in con.execute(
            """SELECT c.name n, MIN(p.trend) e FROM cards c JOIN price_latest p ON p.scryfall_id=c.scryfall_id
               WHERE p.finish='nonfoil' GROUP BY c.name"""):
            if r["e"] is not None and r["n"] not in price:
                price[r["n"]] = r["e"]
    except Exception:  # sem catalog.db (CI): fica so com card_price
        pass
    return price


def _row(name, qty, price):
    return [name, qty, round(price.get(name, 0.0), 2)]


def _cost(*lists):
    return round(sum(q * u for lst in lists for _, q, u in lst), 2)


# ---------------------------------------------------------------- consenso
def _consensus(con, ids, price, thr_main=0.35, thr_sb=0.30):
    if not ids:
        return [], []
    ph = ",".join("?" * len(ids))
    out = {}
    for board, thr in (("main", thr_main), ("side", thr_sb)):
        per = {}
        for r in con.execute(
            f"""SELECT card_name, quantity FROM decklist_cards
                WHERE decklist_id IN ({ph}) AND board=?""", [*ids, board]):
            per.setdefault(r["card_name"], []).append(r["quantity"])
        n = len(ids)
        need = max(2, math.ceil(thr * n))  # min 2 listas: evita inflar amostras pequenas
        cards = [(len(q), Counter(q).most_common(1)[0][0], name)
                 for name, q in per.items() if len(q) >= need]
        cards.sort(key=lambda c: (-c[0], -c[1], c[2]))
        out[board] = [_row(name, qty, price) for _, qty, name in cards]
    return out["main"], out["side"]


# ---------------------------------------------------------------- vigiados
def _watched_build(con, wid, price):
    rows = con.execute(
        """SELECT taken_at, cards FROM watched_snapshots WHERE watched_id=?
           ORDER BY taken_at DESC, id DESC""", (wid,)).fetchall()
    if not rows:
        return None
    latest = json.loads(rows[0]["cards"])
    buckets = {"cmd": {}, "main": {}, "side": {}}
    for entry in latest:
        board, name, qty = entry[0], entry[1], entry[2]
        key = "side" if board == "side" else ("cmd" if board in ("commander", "companion") else "main")
        buckets[key][name] = buckets[key].get(name, 0) + qty

    def mk(d):
        items = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
        return [_row(n, q, price) for n, q in items]
    cmd, main, sb = mk(buckets["cmd"]), mk(buckets["main"]), mk(buckets["side"])
    # estado: comparar as duas ultimas fotos com conteudo distinto
    def canon(js):
        return sorted([[e[0], e[1], e[2]] for e in json.loads(js)])
    status, since, diff = "same", rows[0]["taken_at"], None
    cur = canon(rows[0]["cards"])
    for r in rows[1:]:
        prev = canon(r["cards"])
        if prev != cur:
            old = {(b, n): q for b, n, q in prev}
            new = {(b, n): q for b, n, q in cur}
            add = [[b, n, q] for (b, n), q in new.items() if (b, n) not in old]
            rem = [[b, n, q] for (b, n), q in old.items() if (b, n) not in new]
            status, diff = "changed", {"add": sorted(add), "rem": sorted(rem), "chg": []}
            break
        else:
            since = r["taken_at"]  # estavel desde a foto identica mais antiga
    return {"cmd": cmd, "main": main, "sb": sb,
            "mainN": sum(q for _, q, _ in main), "sbN": sum(q for _, q, _ in sb),
            "cmdN": sum(q for _, q, _ in cmd), "cost": _cost(cmd, main, sb),
            "status": status, "since": since, "diff": diff, "kind": "watched",
            "src": con.execute("SELECT source_url FROM watched_snapshots WHERE watched_id=? "
                               "ORDER BY taken_at DESC, id DESC LIMIT 1", (wid,)).fetchone()[0]}


# ---------------------------------------------------------------- snapshots (consenso)
def _ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS core_snapshots(
        id INTEGER PRIMARY KEY AUTOINCREMENT, core_key TEXT NOT NULL, taken_at TEXT NOT NULL,
        list_hash TEXT NOT NULL, cards_json TEXT NOT NULL)""")


def _track(con, key, main, sb, today):
    canon = sorted([["main", n, q] for n, q, _ in main] + [["side", n, q] for n, q, _ in sb])
    h = hashlib.sha1(json.dumps(canon, ensure_ascii=False).encode()).hexdigest()
    last = con.execute("SELECT taken_at, list_hash, cards_json FROM core_snapshots WHERE core_key=? "
                       "ORDER BY taken_at DESC, id DESC LIMIT 1", (key,)).fetchone()
    if last is None:
        con.execute("INSERT INTO core_snapshots(core_key,taken_at,list_hash,cards_json) VALUES(?,?,?,?)",
                    (key, today, h, json.dumps(canon, ensure_ascii=False)))
        return {"status": "new", "since": today, "diff": None}
    if last["list_hash"] == h:
        return {"status": "same", "since": last["taken_at"], "diff": None}
    old = {(b, n): q for b, n, q in json.loads(last["cards_json"])}
    new = {(b, n): q for b, n, q in canon}
    add = [[b, n, q] for (b, n), q in new.items() if (b, n) not in old]
    rem = [[b, n, q] for (b, n), q in old.items() if (b, n) not in new]
    chg = [[b, n, old[(b, n)], q] for (b, n), q in new.items() if (b, n) in old and old[(b, n)] != q]
    con.execute("INSERT INTO core_snapshots(core_key,taken_at,list_hash,cards_json) VALUES(?,?,?,?)",
                (key, today, h, json.dumps(canon, ensure_ascii=False)))
    return {"status": "changed", "since": today,
            "diff": {"add": sorted(add), "rem": sorted(rem), "chg": sorted(chg)}}


def _consensus_build(con, key, name, ids, price, today):
    main, sb = _consensus(con, ids, price)
    t = _track(con, key, main, sb, today)
    return {"name": name, "n": len(ids), "cost": _cost(main, sb),
            "cmd": [], "main": main, "sb": sb,
            "mainN": sum(q for _, q, _ in main), "sbN": sum(q for _, q, _ in sb), "cmdN": 0,
            "status": t["status"], "since": t["since"], "diff": t["diff"], "kind": "consensus"}


def _up_to(con, ids):
    if not ids:
        return None
    ph = ",".join("?" * len(ids))
    return con.execute(f"SELECT MAX(event_date) FROM decklists WHERE id IN ({ph})", ids).fetchone()[0]


# ---------------------------------------------------------------- build
def build(con, out_path):
    _ensure_table(con)
    today = _dt.date.today().isoformat()
    price = _prices(con)
    data = {f: [] for f, _ in FMT_ORDER}
    unpriced, up_to = set(), None

    def note_prices(b):
        for lst in (b["cmd"], b["main"], b["sb"]):
            for name, _, u in lst:
                if u == 0 and name not in BASICS:
                    unpriced.add(name)

    # -- CONSENSO (procurados por mim) --
    jr = _by_card(con, "Jeskai Revelation", "standard")
    jr_wubr = [i for i in jr if _has_black(con, i)]
    jr_wur = [i for i in jr if i not in set(jr_wubr)]
    CONS = [
        ("modern", "Izzet Affinity (Kappa)", "Urza's Saga + Kappa Cannoneer · principal · combo T1-2",
         [("modern:affinity-kappa", "Consenso", _by_tag(con, "Affinity UR (Kappa)", "modern"))]),
        ("modern", "Grinding Station", "combo Emry + Grinding Station (o meu Grinding Emry)",
         [("modern:grinding-station", "Consenso", _by_tag(con, "Grinding Station", "modern"))]),
        ("pioneer", "Greasefang", "reanimar Parhelion II · Greasefang + Thoughtseize universais",
         [("pioneer:greasefang:abzan", "Abzan Broodwagon (verde)", _by_tag(con, "Greasefang Abzan", "pioneer")),
          ("pioneer:greasefang:orzhov", "Orzhov Monument (sem verde)", _by_tag(con, "Greasefang Orzhov (Monument)", "pioneer"))]),
        ("standard", "Jeskai Revelation", "controlo à volta de Jeskai Revelation",
         [("standard:jeskai:wur", "Jeskai Lessons (WUR)", jr_wur),
          ("standard:jeskai:wubr", "4C Control (WUBR, splash preto)", jr_wubr)]),
        ("standard", "Airbend (Azorius)", "tempo/prison WU · Aang + High Noon + Skycoach Conductor",
         [("standard:airbend", "Consenso", _by_label(con, "Skycoach Conductor / Restless Anchorage / High Noon", "standard"))]),
        ("legacy", "Izzet Welder Artefactos", "lista do Harry1232 · Goblin Welder/Engineer + Emry + Mox Opal",
         [("legacy:izzet-welder", "Consenso", _by_label(con, "The Filigree Sylex / Chromatic Star / Phyrexian Dragon Engine", "legacy"))]),
        ("premodern", "Replenish (UW combo)", "Attunement descarta → Replenish devolve → Opalescence+Parallax Wave",
         [("premodern:replenish", "Consenso", _by_label(con, "Attunement / Skycloud Expanse / Decree of Silence", "premodern"))]),
        ("premodern", "Enchantress (GW)", "Argothian Enchantress + Serra's Sanctum + Solitary Confinement",
         [("premodern:enchantress", "Consenso", _by_label(con, "Sterling Grove / Elephant Grass / Solitary Confinement", "premodern"))]),
        ("premodern", "Survival Elves", "Survival of the Fittest + Priest of Titania · RG Anger vs GW Armageddon",
         [("premodern:elves", "Consenso", _by_label(con, "Yavimaya Granger / Wirewood Symbiote / Priest of Titania", "premodern"))]),
        ("premodern", "Oath of Druids", "Oath → Terravore · prison/land-denial GW",
         [("premodern:oath", "Consenso (Oath main)", _by_card_main(con, "Oath of Druids", "premodern", 2))]),
        ("premodern", "Ill-Gotten Gains", "combo storm UB · Brain Freeze (amostra pequena)",
         [("premodern:igg", "Consenso", _by_label(con, "Ill-Gotten Gains / Cabal Ritual / Tormod's Crypt", "premodern"))]),
        ("duel-commander", "Cloud, Midgar Mercenary", "hatebears/stax · núcleo mono-branco (deriva Boros RW)",
         [("dc:cloud", "Consenso", _by_card(con, "Cloud, Midgar Mercenary", "duel-commander"))]),
    ]
    for fmt, name, sub, builds in CONS:
        obj = {"name": name, "sub": sub, "src": None, "builds": []}
        for key, bname, ids in builds:
            b = _consensus_build(con, key, bname, ids, price, today)
            note_prices(b)
            obj["builds"].append(b)
            d = _up_to(con, ids)
            if d and (up_to is None or d > up_to):
                up_to = d
        data[fmt].append(obj)

    # -- VIGIADOS (lista de jogador) --
    WATCH = [
        ("cedh", "Blue Farm", "cEDH · Tremnek", 1),
        ("cedh", "Cloud", "cEDH · Drakaiz & PTheWriter", 4),
        ("pauper", "Pauper (Luffy)", "jogador MTGO LuffyDoChapeuDePalha", 2),
        ("premodern", "Stiflenought", "Phyrexian Dreadnought + Stifle · MTGO LuffyDoChapeuDePalha", 3),
    ]
    for fmt, name, sub, wid in WATCH:
        b = _watched_build(con, wid, price)
        if not b:
            continue
        note_prices(b)
        b["name"] = "Lista atual"
        data[fmt].append({"name": name, "sub": sub, "src": b["src"], "builds": [b]})

    # Persiste os precos dos cards dos cores em card_price (que vive em vault.db),
    # para o GitHub Action regenerar a pagina com precos mesmo sem catalog.db.
    have = {r[0] for r in con.execute("SELECT card_name FROM card_price")}
    addp = {}
    for cores in data.values():
        for c in cores:
            for b in c["builds"]:
                for lst in (b["cmd"], b["main"], b["sb"]):
                    for name, _, u in lst:
                        if u > 0 and name not in have and name not in addp:
                            addp[name] = u
    if addp:
        con.executemany("INSERT INTO card_price(card_name,eur,source) VALUES(?,?,?)",
                        [(n, u, "core-fill") for n, u in addp.items()])

    _write_html(out_path, data, up_to, today)
    if unpriced:
        print(f"[core-decks] {len(unpriced)} cartas sem preco: {sorted(unpriced)[:40]}")
    return f"{sum(len(v) for v in data.values())} cores, {out_path.name} (dados ate {up_to})"


# ---------------------------------------------------------------- html
_TMPL = """<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Core Decks — decks que sigo</title>
<style>
 :root{--bg:#f6f7f9;--card:#fff;--ink:#12151a;--muted:#5b6672;--line:#e4e7ec;--accent:#2f6df6;--add:#0f8a4d;--rem:#c0392b}
 @media (prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--add:#4ac585;--rem:#ff6b6b}}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1000px;margin:0 auto;padding:20px 16px 60px}
 @media(max-width:600px){.wrap{padding:14px 10px 48px}}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px} .sub a{color:var(--accent)}
 h2{font-size:14px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:30px 0 4px;border-bottom:1px solid var(--line);padding-bottom:6px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:12px}
 .name{font-weight:650;font-size:17px} .csub{color:var(--muted);font-size:12.5px;margin:2px 0 4px}
 .src{font-size:12px} .src a{color:var(--accent)}
 .build{border-top:1px solid var(--line);margin-top:10px;padding-top:10px} .build:first-of-type{border-top:0;margin-top:6px}
 .bhead{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap} .bname{font-weight:600}
 .when{color:var(--muted);font-size:12px;margin-left:auto;white-space:nowrap} .when b{color:var(--ink)}
 .tag{font-size:11px;font-weight:600;padding:1px 7px;border-radius:999px;background:var(--line);color:var(--muted)}
 .status{font-size:12.5px;margin:5px 0} .status.same{color:var(--muted)} .status.changed{color:var(--add);font-weight:650} .status.new{color:var(--muted)}
 .diff{margin:4px 0;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace} .diff .a{color:var(--add)} .diff .r{color:var(--rem)}
 details{margin-top:6px} summary{cursor:pointer;color:var(--accent);font-size:13px}
 .list{margin-top:8px;max-height:340px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:12.5px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}
 .b{color:var(--muted);text-transform:uppercase;font-size:10.5px;letter-spacing:.06em;margin:6px 0 2px} .b:first-child{margin-top:0}
 .row{display:flex;justify-content:space-between;gap:10px} .row .price{color:var(--muted);white-space:nowrap}
 footer{margin-top:34px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>Core Decks — decks que sigo</h1>
<div class="sub">Consenso premier + listas de jogador · preços Cardmarket · dados até %UPTO% ·
<a href="index.html">← coleção</a> · <a href="metagame.html">metagame →</a></div></header>
<div id="app"></div>
<footer>🔔 = o padrão/lista mudou desde a última recolha (mostra o que entrou/saiu) · ✓ = estável · atualiza sozinho todos os dias. Custo = comprar a lista completa na versão mais barata (algumas cartas muito recentes ainda sem preço).</footer>
</div>
<script>
const DATA=%DATA%;
const FMTS=%FMTS%;
const esc=s=>(s==null?"":String(s)).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const eur=x=>(x||0).toLocaleString("pt-PT",{style:"currency",currency:"EUR"});
const rows=a=>a.map(c=>'<div class="row"><span>'+c[1]+'x '+esc(c[0])+'</span><span class="price">'+eur(c[1]*c[2])+'</span></div>').join("");
function diffBlock(d){ if(!d) return "";
 let o=""; (d.add||[]).forEach(x=>o+='<div class="a">+ '+x[2]+'x '+esc(x[1])+'</div>');
 (d.chg||[]).forEach(x=>o+='<div class="a">~ '+esc(x[1])+' '+x[2]+'→'+x[3]+'x</div>');
 (d.rem||[]).forEach(x=>o+='<div class="r">− '+x[2]+'x '+esc(x[1])+'</div>');
 return o?'<div class="diff">'+o+'</div>':""; }
function statusLine(b){
 if(b.status==="changed") return '<div class="status changed">🔔 '+(b.kind==="watched"?"Lista mudou a ":"Padrão mudou a ")+b.since+'</div>'+diffBlock(b.diff);
 if(b.kind==="watched") return '<div class="status same">✓ Sem mudanças desde '+b.since+'</div>';
 if(b.status==="new") return '<div class="status new">Consenso inicial registado a '+b.since+'</div>';
 return '<div class="status same">✓ Padrão estável desde '+b.since+'</div>';
}
function build(b){
 const meta = b.kind==="watched" ? ('lista · atualizada '+b.since) : (b.n+' listas');
 let inner='';
 if(b.cmd&&b.cmd.length) inner+='<div class="b">Comandante</div>'+rows(b.cmd);
 inner+='<div class="b">Main ('+b.mainN+')</div>'+rows(b.main);
 if(b.sb&&b.sb.length) inner+='<div class="b">Sideboard ('+b.sbN+')</div>'+rows(b.sb);
 return '<div class="build"><div class="bhead"><span class="bname">'+esc(b.name)+'</span>'+
  (b.kind==="watched"?' <span class="tag">jogador</span>':'')+
  '<span class="when">'+meta+' · <b>'+eur(b.cost)+'</b></span></div>'+
  statusLine(b)+
  '<details><summary>ver lista ('+(b.cmdN+b.mainN+b.sbN)+')</summary><div class="list">'+inner+'</div></details></div>';
}
function core(c){
 return '<div class="card"><div class="name">'+esc(c.name)+'</div><div class="csub">'+esc(c.sub)+'</div>'+
  (c.src?'<div class="src"><a href="'+esc(c.src)+'" target="_blank" rel="noopener">↗ lista de referência</a></div>':"")+
  c.builds.map(build).join("")+'</div>';
}
document.getElementById("app").innerHTML=FMTS.map(f=>{
 const cs=DATA[f[0]]||[]; if(!cs.length) return "";
 return '<h2>'+f[1]+'</h2>'+cs.map(core).join("");
}).join("");
</script></body></html>
"""


def _write_html(out_path, data, up_to, today):
    html = (_TMPL.replace("%DATA%", json.dumps(data, ensure_ascii=False))
            .replace("%FMTS%", json.dumps(FMT_ORDER)).replace("%UPTO%", up_to or today))
    Path(out_path).write_text(html, encoding="utf-8")


def main():
    with db.session() as con:
        print(build(con, ROOT / "coredecks.html"))


if __name__ == "__main__":
    main()
