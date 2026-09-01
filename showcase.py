"""Gera showcase.html — "Decks Showcase Challenger".

Abas por formato (Standard/Pioneer/Modern/Legacy). Por formato, pega no ÚLTIMO
Showcase Challenge, agrupa as listas em ARQUÉTIPOS (Jaccard das cartas não-básicas
do main >= THRESH), e mostra cada arquétipo, POR ORDEM DE CLASSIFICAÇÃO:
  - a LISTA PADRÃO (a melhor classificada = 1ª publicada; o MTGO não dá placement),
    com main e SIDEBOARD, organizada por tipo, cartas a cor = o André tem;
  - uma secção OPÇÕES: as cartas DIFERENTES das outras listas do mesmo arquétipo
    (não repete a lista se for igual — só acrescenta o que muda), com o nº de
    listas em que cada uma aparece.
NÃO inventa nada: usa só as decklists reais do harvest.
"""
from __future__ import annotations

import html
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meusdecks as md  # noqa: E402  (_type_map/_group_by_type/_bucket/_art/_img_map/_faltas/_faltas_html)
from mtgvault.collection import owned_playable  # noqa: E402

FORMATS = [("standard", "Standard"), ("pioneer", "Pioneer"),
           ("modern", "Modern"), ("legacy", "Legacy")]
THRESH = 0.5     # Jaccard mínimo p/ duas listas serem o mesmo arquétipo
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
          "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
          "Snow-Covered Mountain", "Snow-Covered Forest"}

# Carta-assinatura -> nome do arquétipo (do que reconheci nos 4 eventos). Sem
# match, o nome é gerado pelas 2 cartas mais distintivas (data-driven).
KNOWN = {
    "Living End": "Living End", "Sneak Attack": "Sneak & Show", "Doomsday": "Doomsday",
    "Kappa Cannoneer": "Affinity", "Scion of Draco": "Domain Zoo",
    "Goblin Charbelcher": "Belcher", "Guide of Souls": "Boros Energy",
    "Hollow One": "Hollow One", "Aether Vial": "Death & Taxes",
    "Arclight Phoenix": "Izzet Phoenix", "Nykthos, Shrine to Nyx": "Mono-G Devotion",
    "Indomitable Creativity": "Izzet Creativity", "Show and Tell": "Show and Tell",
    "Griselbrand": "Reanimator", "Atraxa, Grand Unifier": "Reanimator (Atraxa)",
    "Slickshot Show-Off": "Izzet Prowess", "Devoted Druid": "Devoted Druid Combo",
    "Aluren": "Aluren", "Craterhoof Behemoth": "Elves/Devotion",
    "Devourer of Destiny": "Eldrazi Ramp", "Cranial Plating": "Affinity",
    "Chalice of the Void": "Chalice Prison", "Mystic Forge": "Mystic Forge",
    "Up the Beanstalk": "Beanstalk Control", "Jeskai Revelation": "Jeskai Control",
    "Inti, Seneschal of the Sun": "Rakdos Aggro", "Kaito, Bane of Nightmares": "Dimir Tempo",
    "Amalia Benavides Aguirre": "Amalia Combo", "Adeline, Resplendent Cathar": "Mono-W Aggro",
    "Screaming Nemesis": "Mono-R Aggro", "Vivi Ornitier": "Vivi/Loki",
    "Collected Company": "CoCo", "Cleansing Wildfire": "Wildfire Control",
}

NAV = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
       '<a href="meusdecks.html">🎴 Decks permanentes</a>'
       '<a class="cur" href="showcase.html">🎯 Showcase Challenger</a>'
       '<a href="colecao_cor.html">📚 Coleção</a>'
       '<a href="caixarl.html">📦 Caixa RL</a></nav>')


def _lists(con, fmt):
    """(event_name, event_date, [ {rank, player, main, side, set} ]) do último
    Showcase Challenge do formato, por ordem de publicação (líder = 1º)."""
    ev = con.execute("SELECT event_name, event_date FROM decklists WHERE format=? "
                     "AND event_name LIKE '%Showcase Challenge%' "
                     "ORDER BY event_date DESC LIMIT 1", (fmt,)).fetchone()
    if not ev:
        return None, None, []
    out = []
    for rank, r in enumerate(con.execute("SELECT id, player FROM decklists WHERE format=? "
                                         "AND event_name=? AND event_date=? ORDER BY id",
                                         (fmt, ev["event_name"], ev["event_date"])), 1):
        main, side = {}, {}
        for c in con.execute("SELECT card_name nm, board b, quantity q FROM decklist_cards "
                             "WHERE decklist_id=?", (r["id"],)):
            f = c["nm"].split(" // ")[0]
            d = side if c["b"] == "side" else main
            d[f] = d.get(f, 0) + c["q"]
        out.append({"rank": rank, "player": r["player"], "main": main, "side": side,
                    "set": frozenset(k for k in main if k not in BASICS)})
    return ev["event_name"], ev["event_date"], out


def _cluster(lists):
    """Agrupa por líder: cada lista junta-se ao arquétipo mais parecido se Jaccard
    >= THRESH; senão inicia um novo (e fica líder). Devolve (clusters, df)."""
    df = Counter()
    for L in lists:
        for c in L["set"]:
            df[c] += 1

    def sim(a, b):
        return len(a & b) / len(a | b) if (a | b) else 0

    clusters = []
    for L in lists:
        best, bs = None, 0.0
        for c in clusters:
            s = sim(L["set"], c["leader"]["set"])
            if s > bs:
                bs, best = s, c
        if best and bs >= THRESH:
            best["members"].append(L)
        else:
            clusters.append({"leader": L, "members": [L]})
    return clusters, df


def _name(cluster, df):
    s = cluster["leader"]["set"]
    for card, name in KNOWN.items():
        if card in s:
            return name
    dist = sorted(s, key=lambda x: (df[x], x))[:2]
    return " · ".join(dist) if dist else "?"


def _mkcards(cards, owned_qty, sidmap, freq=None, nlists=0):
    """{carta:qty} -> [{nm,qty,hq,state,sid,_type?,_freq?}] (como o meusdecks). Se
    `freq` for dado (opções), cada carta leva o nº de listas em que aparece."""
    out = []
    for nm, q in cards.items():
        oq = q if nm in BASICS else owned_qty.get(nm, 0)
        hq = min(q, oq)
        c = {"nm": nm, "qty": q, "hq": hq, "sid": sidmap.get(nm),
             "state": "have" if hq >= q else ("part" if hq > 0 else "miss")}
        if freq is not None:
            c["_freq"] = (freq.get(nm, 0), nlists)
        out.append(c)
    return out


def _archetype_html(a, name, tm, owned, owned_qty, sidmap):
    members = a["members"]
    n = len(members)
    leader = members[0]
    lead_main = _mkcards(leader["main"], owned_qty, sidmap)
    lead_side = _mkcards(leader["side"], owned_qty, sidmap)
    nb = [c for c in lead_main if c["nm"] not in BASICS]
    have = sum(1 for c in nb if c["state"] != "miss")
    cov = round(100 * have / len(nb)) if nb else 0
    col = "var(--add)" if cov >= 90 else "var(--gold)" if cov >= 60 else "var(--warn)"

    def rc(c):
        img = (f'<img loading="lazy" src="{md._art(c["sid"])}" alt="">' if c.get("sid")
               else '<div class="noimg"></div>')
        qb = (f'<span class="cq">{c["hq"]}/{c["qty"]}</span>' if c.get("qty", 1) > 1
              else ('' if c["state"] == "have" else '<span class="cq">0/1</span>'))
        fb = ""
        if c.get("_freq"):
            k, tot = c["_freq"]
            fb = f'<span class="cs opt" title="em {k} de {tot} listas do arquétipo">{k}</span>'
        return f'<div class="cd {c["state"]}" title="{html.escape(c["nm"])}">{img}{qb}{fb}</div>'

    body = (f'<div class="cardshdr">🃏 Lista padrão <span class="dim">({html.escape(leader["player"] or "?")})</span></div>'
            f'{md._group_by_type(lead_main, tm, rc)}')
    if lead_side:
        body += (f'<div class="cardshdr sb">🎒 Sideboard</div>'
                 f'{md._group_by_type(lead_side, tm, rc)}')

    # Opções: cartas que OUTRAS listas do arquétipo jogam e o líder NÃO — o número
    # é em quantas listas aparece. Se as listas forem iguais, não há opções.
    if n > 1:
        freq = Counter()
        for m in members[1:]:
            for c in m["main"]:
                if c not in leader["main"] and c not in BASICS:
                    freq[c] += 1
        if freq:
            opt = _mkcards({c: 1 for c in freq}, owned_qty, sidmap, freq=freq, nlists=n)
            opt.sort(key=lambda c: -c["_freq"][0])
            body += (f'<div class="cardshdr op-h">🔀 Opções '
                     f'<span class="dim">(cartas das outras {n - 1} listas — o nº = em quantas)</span></div>'
                     f'{md._group_by_type(opt, tm, rc)}')
    body += md._faltas_html(md._faltas(lead_main + lead_side), cls="dk")

    return (f'<div class="deck">'
            f'<div class="dtop"><b>{html.escape(name)}</b>'
            f'<span class="pct" style="color:{col}">{have}/{len(nb)} · {cov}%</span></div>'
            f'<div class="badges"><span class="bdg src">🎯 pub#{leader["rank"]}</span>'
            f'<span class="bdg">{n} lista{"s" if n > 1 else ""}</span></div>'
            f'<div class="bar"><span style="width:{cov}%;background:{col}"></span></div>'
            f'{body}</div>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "showcase.html")
    owned_qty = owned_playable(con)
    owned = set(owned_qty)

    fmt_data, allnames = {}, set()
    for fmt, _lbl in FORMATS:
        ename, edate, lists = _lists(con, fmt)
        if not lists:
            continue
        clusters, df = _cluster(lists)
        clusters.sort(key=lambda c: c["leader"]["rank"])   # por ordem de classificação
        fmt_data[fmt] = {"ename": ename, "edate": edate, "clusters": clusters, "df": df}
        for L in lists:
            allnames |= set(L["main"]) | set(L["side"])
    sidmap = md._img_map(con, allnames)
    tm = md._type_map(con, allnames)

    tabs, panels = "", ""
    for fmt, lbl in FORMATS:
        d = fmt_data.get(fmt)
        if not d:
            continue
        act = " act" if not tabs else ""
        tabs += f'<button class="ftab{act}" data-f="{fmt}">{html.escape(lbl)} <span class="n">{len(d["clusters"])}</span></button>'
        cards = "".join(_archetype_html(a, _name(a, d["df"]), tm, owned, owned_qty, sidmap)
                        for a in d["clusters"])
        panels += (f'<section class="fpanel{act}" data-f="{fmt}">'
                   f'<div class="evh">{html.escape(d["ename"])} · {d["edate"]}</div>'
                   f'<div class="grid">{cards}</div></section>')

    out.write_text(_TMPL.replace("%NAV%", NAV).replace("%TABS%", tabs).replace("%PANELS%", panels),
                   encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Showcase Challenger</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:100px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .ftabs{display:flex;gap:7px;flex-wrap:wrap;margin:14px 0 4px} .ftab{padding:8px 15px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);font-weight:700;font-size:13px;cursor:pointer} .ftab .n{color:#4a5666;font-weight:600} .ftab:hover{color:var(--ink)} .ftab.act{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent);color:var(--ink)} .ftab.act .n{color:var(--accent)}
 .fpanel{display:none} .fpanel.act{display:block}
 .evh{color:var(--muted);font-size:12px;margin:8px 0 12px;text-transform:uppercase;letter-spacing:.05em}
 .grid{display:grid;grid-template-columns:1fr;gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
 .dtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px} .dtop b{font-size:16px} .pct{font-weight:800;font-size:16px}
 .badges{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:7px 0} .bdg{font-size:11px;padding:2px 8px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:5px 0 2px} .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .cardshdr{margin-top:11px;font-size:12px;color:var(--accent)} .cardshdr .dim{color:var(--muted)} .cardshdr.sb{color:var(--gold)} .cardshdr.op-h{color:#7fa8ff}
 .typehdr{margin:8px 0 1px;font-size:10.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} .typehdr .dim{color:#4a5666} .typehdr+.cards{margin-top:3px}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
 .cd{position:relative;width:52px} .cd img,.cd .noimg{width:52px;height:73px;border-radius:4px;display:block;background:#0c0f14}
 .cd.have{box-shadow:0 0 0 2px var(--add)} .cd.part{box-shadow:0 0 0 2px var(--gold)} .cd.part img{filter:brightness(.82)}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.7) brightness(.6)}
 .cd .cq{position:absolute;top:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 .cd .cs{position:absolute;bottom:1px;right:1px;font-size:9px;font-weight:800;padding:0 3px;border-radius:5px;color:#fff}
 .cd .cs.opt{background:rgba(91,140,255,.95)}
 .faltas.dk{margin-top:2px} .flh{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:12px;font-weight:700;color:#e2795b} .flh .dim{color:var(--muted);font-weight:400}
 .faltas ul.fl{list-style:none;margin:6px 0 0;padding:0;column-width:200px;column-gap:18px;font-size:12px} .faltas ul.fl li{padding:1.5px 0;break-inside:avoid} .faltas ul.fl b{color:var(--gold);font-variant-numeric:tabular-nums;margin-right:2px}
 .cpbtn{font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;border:1px solid var(--line);background:#1a2230;color:var(--muted);cursor:pointer} .cpbtn:hover{border-color:var(--accent);color:var(--ink)} .cpbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)} .flh .cpbtn{margin-left:auto}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎯 Decks Showcase Challenger</h1>
<div class="lead">O último Showcase Challenge de cada formato, agrupado por arquétipo. Por classificação: a <b>lista padrão</b> (a melhor) com main e sideboard, e por baixo as <b style="color:#7fa8ff">🔀 opções</b> — as cartas das outras listas do arquétipo que mudam (o nº = em quantas aparecem). Cartas <b style="color:var(--add)">a cor = tens</b>.</div>
%NAV%
<div class="ftabs">%TABS%</div></header>
%PANELS%
<footer>Agrupamento por Jaccard ≥ 0.5 das cartas não-básicas do main. O MTGO não dá classificação nestas listas — uso a ordem de publicação (pub# ≈ 1º→último). Atualiza diariamente.</footer>
</div>
<script>
function cpFaltas(btn){const c=btn.closest('.faltas'),t=c&&c.querySelector('textarea.cmk');if(!t)return;const d=()=>{btn.textContent='✓ copiado';btn.classList.add('done');};if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t.value).then(d).catch(()=>{t.select();document.execCommand('copy');d();});}else{t.select();try{document.execCommand('copy');d();}catch(e){}}}
document.querySelectorAll('.ftab').forEach(b=>b.onclick=()=>{
  const f=b.dataset.f;
  document.querySelectorAll('.ftab').forEach(x=>x.classList.toggle('act',x.dataset.f===f));
  document.querySelectorAll('.fpanel').forEach(x=>x.classList.toggle('act',x.dataset.f===f));
});
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("showcase.html:", build(con))


if __name__ == "__main__":
    main()
