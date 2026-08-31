"""Gera colecao_cor.html — a COLEÇÃO (só ela) organizada como o André a arruma
fisicamente: por COR e, dentro de cada cor, por CUSTO DE MANA (CMC).

As cartas são classificadas em classify.py: só as de estado "Coleção" entram
aqui. As de deck ficam de fora (estão nos decks montados) e as de venda vão
para uma secção própria no fim. Serve de guia para arrumar e para ver o que
ainda falta fotografar.

Terras à parte (não têm CMC), por nome. Marcadores: ★ = foil, PT = português.
Imagens da Scryfall (CDN), construídas a partir do scryfall_id.

Uso:  python colecao_cor.py   ->  escreve colecao_cor.html na raiz do repo.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import classify  # noqa: E402
import commander_decks  # noqa: E402  (decks de consenso em camadas núcleo/flex/tech)
from mtgvault import db  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

COLOR = {"W": "Branco", "U": "Azul", "B": "Preto", "R": "Vermelho", "G": "Verde"}
ORDER = ["Branco", "Azul", "Preto", "Vermelho", "Verde", "Multicor",
         "Incolor / Artefacto", "Terras"]


def _bucket(type_line, ci):
    if type_line and "Land" in type_line:
        return "Terras"
    try:
        cols = json.loads(ci) if ci and ci.strip().startswith("[") else [c for c in (ci or "") if c in "WUBRG"]
    except Exception:
        cols = [c for c in (ci or "") if c in "WUBRG"]
    if len(cols) >= 2:
        return "Multicor"
    if len(cols) == 1:
        return COLOR[cols[0]]
    return "Incolor / Artefacto"


def _img(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg"


def _card(x, badge_cls="q"):
    fo = '<span class="mk foil">★</span>' if x["fin"] == "foil" else ""
    pt = '<span class="mk pt">PT</span>' if x["lang"] == "pt" else ""
    cls, tag, data = "c", "", ""
    tip = html.escape(x["nm"] or "")
    if x.get("used_by"):          # vai para um deck — só MARCADA (o botão escurece)
        where = ", ".join(x["used_by"])
        data = f' data-used="{html.escape(where)}"'
        tag = f'<span class="use">{html.escape(where)}</span>'
        tip += f' — vai para: {html.escape(where)}'
    elif x.get("extra"):          # deck vigiado: carta que saiu da lista, retida
        last = x.get("last")
        cls = "c extra"
        tag = (f'<span class="ex" title="fora da lista, retida'
               f'{(" · última utilização " + last) if last else ""}">extra</span>')
        tip += " — extra (saiu da lista, retida até 6 meses)"
    return (f'<div class="{cls}"{data} title="{tip}">'
            f'<img loading="lazy" src="{_img(x["sid"])}" alt="">'
            f'<span class="{badge_cls}">{x["q"]}</span>{fo}{pt}{tag}</div>')


# Um "binder" por cor. Ícone e slug (para âncoras) de cada cor.
ICON = {"Branco": "⬜", "Azul": "🟦", "Preto": "⬛", "Vermelho": "🟥", "Verde": "🟩",
        "Multicor": "🟪", "Incolor / Artefacto": "⚙️", "Terras": "🏔️"}
SLUG = {"Branco": "branco", "Azul": "azul", "Preto": "preto", "Vermelho": "vermelho",
        "Verde": "verde", "Multicor": "multicor", "Incolor / Artefacto": "incolor",
        "Terras": "terras"}
# As duas coleções (balde sub_collection -> rótulo curto), pela ordem em que
# aparecem DENTRO de cada cor.
POOLS = [("SPML", "🔷 SPML"), ("Premodern (geral)", "🕰️ Premodern")]


def _cmc_grids(rows, is_land):
    """Grelhas por custo de mana (ou uma só, para Terras)."""
    bycmc = defaultdict(list)
    for r in rows:
        bycmc[0 if is_land else int(r["cmc"] or 0)].append(r)
    out = ""
    for cmc in sorted(bycmc):
        cards = sorted(bycmc[cmc], key=lambda x: (x["nm"] or "").lower())
        lbl = "Terras" if is_land else f"CMC {cmc}"
        out += f'<h4>{lbl} <span class="n">{sum(x["q"] for x in cards)}</span></h4><div class="grid">'
        out += "".join(_card(x) for x in cards)
        out += "</div>"
    return out


# Decks permanentes de LISTA FIXA (balde físico + rótulo). O Cloud (Duel Commander)
# não entra aqui — é de CONSENSO, mostrado em camadas (núcleo/flex/tech) mais abaixo.
WATCHED_BALDES = [("Blue Farm", "🩸 Blue Farm [cEDH]"),
                  ("Cloud cEDH", "☁️ Cloud [cEDH]"),
                  ("Pauper Affinity", "🔧 Pauper Affinity")]
# Comandantes seguidos por consenso (balde -> (nome do deck, formato, comandante)).
CONSENSUS_BALDES = {"Cloud": ("Cloud (Duel Commander)", "duel-commander", "Cloud, Midgar Mercenary")}
CI_ICON = {"W": "⬜", "U": "🟦", "B": "⬛", "R": "🟥", "G": "🟩"}


def _watched_deck_pools(con):
    """Por cada deck vigiado: o deck por INTEIRO (o que tem e está na lista atual)
    + as cartas EXTRA (as que já tem mas saíram da lista) — retidas até 6 meses da
    última vez que estiveram na lista; passado isso, sugere-se vender.

    A lista atual e o histórico de "última utilização" vêm da lista vigiada
    (watched_snapshots); para o Cloud (Duel Commander), do consenso (deck_cards).
    """
    cutoff = con.execute("SELECT date('now','-6 months') d").fetchone()["d"]
    wmap = {r["sub_collection"]: r["watched_id"]
            for r in con.execute("SELECT sub_collection, watched_id FROM deck_collection")}
    today = con.execute("SELECT date('now') d").fetchone()["d"]

    def _list_and_last(balde):
        cur, last = set(), {}
        wid = wmap.get(balde)
        if wid:
            for r in con.execute("SELECT taken_at, cards FROM watched_snapshots "
                                 "WHERE watched_id = ? ORDER BY taken_at", (wid,)):
                names = {c[1].split(" // ")[0] for c in json.loads(r["cards"])}
                for nm in names:
                    last[nm] = (r["taken_at"] or "")[:10]
                cur = names
        else:   # Cloud (Duel Commander): consenso, sem histórico
            cur = {r["nm"].split(" // ")[0] for r in con.execute(
                "SELECT card_name nm FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id "
                "WHERE d.name = 'Cloud (Duel Commander)'")}
            for nm in cur:
                last[nm] = today
        return cur, last

    out = []
    for balde, title in WATCHED_BALDES:
        cur, last = _list_and_last(balde)
        deck_rows, extra_rows = [], []
        for r in con.execute(
            """SELECT c.scryfall_id sid, c.name nm, c.cmc cmc, c.type_line tl,
                      c.color_identity ci, cp.finish fin, cp.language lang, SUM(cp.quantity) q
                 FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                 JOIN sub_collections s ON s.id = cp.sub_collection_id
                WHERE cp.purpose = 'player' AND s.name = ?
                GROUP BY c.scryfall_id, cp.finish, cp.language""", (balde,)):
            row = dict(r)
            front = r["nm"].split(" // ")[0]
            if front in cur:
                deck_rows.append(row)
            else:
                lp = last.get(front)
                row["extra"] = True
                row["last"] = lp
                row["expired"] = bool(lp and lp < cutoff)
                extra_rows.append(row)
        if deck_rows or extra_rows:
            out.append({"title": title, "deck": deck_rows, "extra": extra_rows,
                        "n_list": len(cur), "n_have": len(deck_rows)})
    return out


def _consensus_tiers_html(con):
    """Decks de consenso (ex.: Cloud) em camadas: núcleo (≥50%, o deck), flex
    (25–50%) e tech (15–25%). Só cartas dentro da cor do comandante. Cada carta a
    cores se o André a tem, a cinzento se falta, com a % de listas que a jogam."""
    owned = set(owned_playable(con))
    out = ""
    for balde, (name, fmt, commander) in CONSENSUS_BALDES.items():
        t, n = commander_decks.tiers(con, fmt, commander)
        if not t:
            continue
        names = [nm.split(" // ")[0] for k in ("core", "flex", "tech") for nm, _ in t[k]]
        osid, cat = {}, {}
        for r in con.execute("SELECT c.name nm, cp.scryfall_id sid FROM copies cp "
                             "JOIN cards c ON c.scryfall_id = cp.scryfall_id "
                             "WHERE cp.purpose='player'"):
            osid.setdefault(r["nm"].split(" // ")[0], r["sid"])
        for i in range(0, len(names), 300):
            ch = names[i:i + 300]
            ph = ",".join("?" for _ in ch)
            for r in con.execute(f"SELECT name nm, scryfall_id sid FROM cards "
                                 f"WHERE name IN ({ph}) AND digital=0 GROUP BY name", ch):
                cat.setdefault(r["nm"], r["sid"])

        def tcard(nm, pct):
            front = nm.split(" // ")[0]
            have = front in owned
            sid = osid.get(front) or cat.get(front)
            img = (f'<img loading="lazy" src="{_img(sid)}" alt="">' if sid
                   else '<div class="noimg"></div>')
            return (f'<div class="c {"" if have else "miss"}" '
                    f'title="{html.escape(nm)} · {pct}% das listas">{img}'
                    f'<span class="q pctb">{pct}%</span></div>')

        def own(lst):
            return sum(1 for nm, _ in lst if nm.split(" // ")[0] in owned)
        ico = CI_ICON.get(t["ci"], "🌈") if len(t["ci"]) == 1 else ("⚙️" if not t["ci"] else "🌈")
        out += (f'<h3>☁️ {html.escape(name)} {ico} <span class="n">núcleo {len(t["core"])} '
                f'(tens {own(t["core"])}) · flex {len(t["flex"])} (tens {own(t["flex"])}) · '
                f'tech {len(t["tech"])} (tens {own(t["tech"])}) · de {n} listas</span></h3>')
        out += ('<h4>núcleo (≥50%) — o deck</h4><div class="grid">'
                + "".join(tcard(nm, p) for nm, p in t["core"]) + '</div>')
        out += '<div class="tiersep">↓ opções para as vagas (verde = tens · cinza = falta) ↓</div>'
        out += ('<h4>flex (25–50%)</h4><div class="grid">'
                + "".join(tcard(nm, p) for nm, p in t["flex"]) + '</div>')
        out += ('<h4>tech (15–25%)</h4><div class="grid">'
                + "".join(tcard(nm, p) for nm, p in t["tech"]) + '</div>')
    return out


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "colecao_cor.html")
    # Fase "encher os binders": mostra TUDO o que o André tem nos baldes de
    # coleção (SPML + Premodern), por cor→CMC, SEM remover nada para decks nem
    # venda. As que iriam para um deck ficam só MARCADAS (data-used) — o botão
    # "sombrear as que vão para decks" liga isso quando ele passar a essa fase.
    spml_formatos, completos, montados = classify._config()
    active_fmts = [f for f, s in spml_formatos.items() if s in classify.ACTIVE_STATUSES]
    pm_status = classify.premodern_status(con, sticky=completos)
    used_by = classify._used_by(con, active_fmts, pm_status, montados)

    colrows = defaultdict(lambda: defaultdict(list))   # cor -> balde -> linhas
    n_deckbound = 0
    for r in con.execute(
        """SELECT c.scryfall_id sid, c.name nm, c.cmc cmc, c.type_line tl,
                  c.color_identity ci, cp.finish fin, cp.language lang, s.name sub,
                  SUM(cp.quantity) q
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
             JOIN sub_collections s ON s.id = cp.sub_collection_id
            WHERE cp.purpose = 'player' AND s.name IN ('SPML', 'Premodern (geral)')
            GROUP BY c.scryfall_id, cp.finish, cp.language, s.name"""):
        row = dict(r)
        ub = used_by.get(r["nm"])
        if ub:
            row["used_by"] = sorted(ub)
            n_deckbound += r["q"]
        colrows[_bucket(r["tl"], r["ci"])][r["sub"]].append(row)

    secs, navs = "", []
    for b in ORDER:
        pools = colrows.get(b)
        if not pools:
            continue
        total = sum(x["q"] for rs in pools.values() for x in rs)
        slug = SLUG[b]
        navs.append(f'<a href="#bind-{slug}">{ICON[b]} {b}</a>')
        secs += (f'<h2 id="bind-{slug}" class="pool">{ICON[b]} {html.escape(b)} '
                 f'<span class="n">{total}</span></h2>')
        for sub, short in POOLS:
            rs = pools.get(sub)
            if not rs:
                continue
            secs += f'<h3>{short} <span class="n">{sum(x["q"] for x in rs)}</span></h3>'
            secs += _cmc_grids(rs, b == "Terras")
    topnav = " · ".join(navs)

    # Decks permanentes (só decks). Lista fixa (Blue Farm/Cloud cEDH/Pauper): o deck
    # por inteiro + extras. Consenso (Cloud DC): camadas núcleo/flex/tech.
    wsec_body = ""
    for p in _watched_deck_pools(con):
        wsec_body += (f'<h3>{html.escape(p["title"])} <span class="n">'
                      f'{p["n_have"]} na lista · {len(p["extra"])} extra</span></h3>')
        dcards = sorted(p["deck"], key=lambda x: (int(x["cmc"] or 0), (x["nm"] or "").lower()))
        wsec_body += '<div class="grid">' + "".join(_card(x) for x in dcards) + '</div>'
        if p["extra"]:
            ex = sorted(p["extra"], key=lambda x: (int(x["cmc"] or 0), (x["nm"] or "").lower()))
            wsec_body += ('<h4>extra — fora da lista, retidas</h4><div class="grid">'
                          + "".join(_card(x) for x in ex) + '</div>')
    wsec_body += _consensus_tiers_html(con)

    wsec = ""
    if wsec_body:
        topnav += ' · <a href="#vigiados">🃏 Decks permanentes</a>'
        wsec = ('<h2 id="vigiados" class="pool">🃏 Decks permanentes '
                '<span class="n">só decks — não coleção</span></h2>'
                '<p class="hint">Lista fixa (Blue Farm, Cloud cEDH, Pauper): o deck por inteiro '
                '+ as <b>extra</b> (saíram da lista, retidas até 6 meses). Consenso (Cloud): em '
                'camadas — <b>núcleo</b> (≥50% das listas) é o deck; <b>flex</b> (25–50%) e '
                '<b>tech</b> (15–25%) são opções para as vagas. Só cartas dentro da cor do '
                'comandante.</p>' + wsec_body)

    total_col = sum(x["q"] for pools in colrows.values() for rs in pools.values() for x in rs)
    ESTADO = {"a jogar": "#4ac585", "a treinar": "#e0b64b",
              "a preparar": "#5b8cff", "ignorar": "#93a0ad"}
    fmts = " ".join(
        f'<b style="color:{ESTADO.get(s, "#93a0ad")}">{html.escape(f.capitalize())}</b>'
        f'<span class="muted"> {html.escape(s)}</span>'
        for f, s in spml_formatos.items())
    pm_completos = [d for d, st in pm_status.items() if st["locked"]]
    pm_str = ", ".join(pm_completos) if pm_completos else f"0 completos · {len(pm_status)} a montar"
    mont_str = (f' &nbsp;·&nbsp; 🔒 montados: <b>{", ".join(html.escape(m) for m in montados)}</b>'
                if montados else "")
    cfg_line = (f'🔷 SPML: {fmts} &nbsp;·&nbsp; 🕰️ Premodern: <b>{html.escape(pm_str)}</b>{mont_str}'
                f'<span class="muted"> — diz-me se mudas de formato ou quando montas um deck</span>')
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%SECS%", secs).replace("%VIGIADOS%", wsec)
                   .replace("%NAV%", topnav).replace("%TOTAL%", str(total_col))
                   .replace("%DECKN%", str(n_deckbound))
                   .replace("%CFG%", cfg_line).replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coleção por cor</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:20px 14px 60px}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px;margin-bottom:6px} .sub a{color:var(--accent)}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .nav{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);font-size:13px;z-index:5}
 .nav a{color:var(--accent);margin-right:10px;text-decoration:none}
 h2.pool{font-size:20px;margin:30px 0 2px;padding:6px 10px;border-radius:8px;background:#141b26;border:1px solid var(--line);border-left:4px solid var(--accent)}
 .colnav{font-size:12px;margin:0 0 6px;padding-left:2px} .colnav a{color:var(--accent);margin-right:8px;text-decoration:none}
 h3{font-size:16px;margin:16px 0 4px;border-bottom:2px solid var(--line);padding-bottom:3px}
 h4{color:var(--muted);font-size:12px;margin:10px 0 4px;text-transform:uppercase;letter-spacing:.04em}
 .n{color:var(--muted);font-size:12px;font-weight:400}
 .grid{display:flex;flex-wrap:wrap;gap:6px}
 .c{position:relative;width:74px} .c img{width:74px;border-radius:5px;display:block;background:#0c0f14}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:11px;padding:0 5px;border-radius:7px}
 .c .q.sell{background:#7a1d1d}
 .c .use{display:none;position:absolute;bottom:0;left:0;right:0;background:#000e;color:#c7d0da;font-size:8px;line-height:1.3;padding:1px 3px;border-radius:0 0 5px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center}
 body.deckmode .c[data-used] img{filter:grayscale(1) brightness(.42)}
 body.deckmode .c[data-used] .q{background:#000d;color:#9aa6b2}
 body.deckmode .c[data-used] .use{display:block}
 .c.extra img{filter:brightness(.82) sepia(.35) saturate(1.3) hue-rotate(-15deg)}
 .c .ex{position:absolute;bottom:0;left:0;right:0;background:#5a4a1f;color:#f4e0a0;font-size:8.5px;font-weight:700;line-height:1.35;padding:1px 3px;border-radius:0 0 5px 5px;text-align:center}
 .c.miss{opacity:.72} .c.miss img{filter:grayscale(1) brightness(.5)}
 .c .noimg{width:74px;height:103px;border-radius:5px;background:#0c0f14}
 .c .q.pctb{background:#1c2c4a;color:#9cc2ff}
 .tiersep{margin:12px 0 6px;padding:5px 10px;border-radius:7px;background:#141b26;border:1px dashed var(--line);color:var(--muted);font-size:12px;text-align:center;font-weight:600}
 .mk{position:absolute;bottom:3px;right:3px;font-size:10px;font-weight:700}
 .mk.foil{color:var(--gold);text-shadow:0 0 3px #000} .mk.pt{background:#12351f;color:var(--add);border-radius:4px;padding:0 3px;font-size:9px}
 .tally{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0 2px}
 .tally b{display:inline-block;padding:3px 9px;border-radius:20px;font-size:12px;font-weight:600}
 .t-col{background:#16283f;color:#9cc2ff} .t-deck{background:#123020;color:#6ee0a0} .t-sell{background:#3a1516;color:#f0a0a0}
 .tgl{margin-left:auto;font-size:12px;font-weight:600;padding:4px 12px;border-radius:20px;border:1px solid var(--line);background:var(--card);color:var(--muted);cursor:pointer}
 .tgl.on{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent);color:var(--ink)}
 .hint{color:var(--muted);font-size:12px;margin:4px 0 8px}
 .cfg{font-size:12.5px;margin:2px 0 4px;padding:5px 9px;border-radius:7px;background:#141b26;border:1px solid var(--line)}
 .cfg .muted{color:var(--muted)}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>📚 Coleção — organizar e fotografar</h1>
<div class="sub">TUDO o que tens nos baldes de coleção, por cor→custo de mana · nada removido para decks · enche os binders e fotografa o que não aparecer · dados de %TODAY%</div>
<nav class="tabs"><a href="index.html">🏠 Início</a><a href="meusdecks.html">🎴 Decks permanentes</a><a class="cur" href="colecao_cor.html">📚 Coleção</a><a href="caixarl.html">📦 Caixa RL</a></nav>
<div class="tally"><b class="t-col">🔵 %TOTAL% cartas nos binders</b><b class="t-deck">🟢 %DECKN% que vão p/ decks</b><button class="tgl" id="dm" onclick="toggleDM()">🎯 marcar as que vão p/ decks</button></div>
<div class="cfg">%CFG%</div></header>
<div class="nav">%NAV%</div>
%SECS%
%VIGIADOS%
<footer><b>Um binder por cor</b>; dentro de cada cor, <b>SPML</b> e <b>Premodern</b> separados, cada um por custo de mana (as Terras por nome). Mostra <b>TUDO</b> o que tens nesses baldes — nada é removido para decks (enche primeiro os binders; os decks vêm depois). Os decks montados (Blue Farm, Cloud, etc.) ficam <b>à parte</b>, na secção 🃏 Decks permanentes. O número em cada carta é quantas tens; ★ = foil, PT = português. <b>Se tiveres uma carta na mão que não aparece — ou mais do que o número — ainda não está catalogada: fotografa.</b> O botão <b>🎯 marcar as que vão p/ decks</b> sombreia (mais tarde, quando montares) as que já estão reservadas a um deck. Atualiza sozinho todos os dias.</footer>
</div>
<script>
function toggleDM(){var on=document.body.classList.toggle('deckmode');
  var b=document.getElementById('dm');b.classList.toggle('on',on);
  b.textContent=on?'🎯 a sombrear as de decks':'🎯 marcar as que vão p/ decks';
  try{localStorage.setItem('cc_deckmode',on?'1':'');}catch(e){}}
try{if(localStorage.getItem('cc_deckmode'))toggleDM();}catch(e){}
</script>
</body></html>"""


def main():
    with db.session() as con:
        out = build(con)
    print(f"colecao_cor.html escrito: {out}")


if __name__ == "__main__":
    main()
