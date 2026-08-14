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
from mtgvault import db  # noqa: E402

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
    return (f'<div class="c" title="{html.escape(x["nm"] or "")}">'
            f'<img loading="lazy" src="{_img(x["sid"])}" alt="">'
            f'<span class="{badge_cls}">{x["q"]}</span>{fo}{pt}</div>')


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


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "colecao_cor.html")
    rep = classify.build(con)

    # Coleção: um binder por COR; dentro, SPML e Premodern separados, por CMC.
    colrows = defaultdict(lambda: defaultdict(list))   # cor -> balde -> linhas
    for r in rep["colecao"]:
        colrows[_bucket(r["tl"], r["ci"])][r["sub"]].append(r)

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

    # Vender: por pool, depois por motivo, agregado por nome.
    vsec = ""
    if rep["vender"]:
        vsec += (f'<h2 id="Vender" class="pool">🔴 Vender <span class="n">{rep["counts"]["vender"]}</span></h2>'
                 '<p class="hint">Sugestões — <b>confirma antes de vender</b>. Alguns duplicados '
                 '(terras duais, fetchlands) podes querer manter para montar vários decks ao mesmo tempo.</p>')
        for sub, short in POOLS:
            rows = [r for r in rep["vender"] if r["sub"] == sub]
            if not rows:
                continue
            agg = defaultdict(lambda: {"q": 0, "row": None})
            for r in rows:
                k = (r["nm"], r["reason"])
                agg[k]["q"] += r["q"]
                agg[k]["row"] = r
            vsec += f'<h3>{short} <span class="n">{sum(r["q"] for r in rows)}</span></h3>'
            by_reason = defaultdict(list)
            for (nm, reason), v in agg.items():
                by_reason[reason].append(v)
            for reason in sorted(by_reason):
                items = sorted(by_reason[reason], key=lambda v: -v["q"])
                vsec += f'<h4>{html.escape(reason)}</h4><div class="grid">'
                for v in items:
                    row = dict(v["row"]); row["q"] = v["q"]
                    vsec += _card(row, badge_cls="q sell")
                vsec += "</div>"

    c = rep["counts"]
    ESTADO = {"a jogar": "#4ac585", "a treinar": "#e0b64b",
              "a preparar": "#5b8cff", "ignorar": "#93a0ad"}
    fmts = " ".join(
        f'<b style="color:{ESTADO.get(s, "#93a0ad")}">{html.escape(f.capitalize())}</b>'
        f'<span class="muted"> {html.escape(s)}</span>'
        for f, s in rep["spml_formatos"].items())
    pm = rep["premodern_status"]
    completos = [d for d, st in pm.items() if st["locked"]]
    pm_str = ", ".join(completos) if completos else f"0 completos · {len(pm)} a montar"
    mont = rep.get("decks_montados") or []
    mont_str = (f' &nbsp;·&nbsp; 🔒 montados: <b>{", ".join(html.escape(m) for m in mont)}</b>'
                if mont else "")
    cfg_line = (f'🔷 SPML: {fmts} &nbsp;·&nbsp; 🕰️ Premodern: <b>{html.escape(pm_str)}</b>{mont_str}'
                f'<span class="muted"> — diz-me se mudas de formato ou quando montas um deck</span>')
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%SECS%", secs).replace("%VENDER%", vsec)
                   .replace("%NAV%", topnav).replace("%COL%", str(c["colecao"]))
                   .replace("%DECK%", str(c["deck"])).replace("%SELL%", str(c["vender"]))
                   .replace("%CFG%", cfg_line).replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coleção por cor</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:20px 14px 60px}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px;margin-bottom:6px} .sub a{color:var(--accent)}
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
 .mk{position:absolute;bottom:3px;right:3px;font-size:10px;font-weight:700}
 .mk.foil{color:var(--gold);text-shadow:0 0 3px #000} .mk.pt{background:#12351f;color:var(--add);border-radius:4px;padding:0 3px;font-size:9px}
 .tally{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 2px}
 .tally b{display:inline-block;padding:3px 9px;border-radius:20px;font-size:12px;font-weight:600}
 .t-col{background:#16283f;color:#9cc2ff} .t-deck{background:#123020;color:#6ee0a0} .t-sell{background:#3a1516;color:#f0a0a0}
 .hint{color:var(--muted);font-size:12px;margin:4px 0 8px}
 .cfg{font-size:12.5px;margin:2px 0 4px;padding:5px 9px;border-radius:7px;background:#141b26;border:1px solid var(--line)}
 .cfg .muted{color:var(--muted)}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎨 Coleção — por cor e custo de mana</h1>
<div class="sub">um binder por cor · dentro, SPML e Premodern separados, por custo de mana · dados de %TODAY% · <a href="index.html">← início</a> · <a href="cobertura.html">cobertura</a> · <a href="colecao.html">galeria (por deck)</a></div>
<div class="tally"><b class="t-col">🔵 %COL% em coleção</b><b class="t-deck">🟢 %DECK% em decks (fora)</b><b class="t-sell">🔴 %SELL% a vender</b></div>
<div class="cfg">%CFG%</div></header>
<div class="nav">%NAV% · <a href="#Vender">🔴 Vender</a></div>
%SECS%
%VENDER%
<footer><b>Um binder por cor</b>; dentro de cada cor, a coleção de <b>SPML</b> e a de <b>Premodern</b> separadas, cada uma por custo de mana (as Terras por nome). Só aparece a coleção solta — as cartas dos decks montados ficam de fora. As de venda são as cópias acima de 4. O número em cada carta é quantas tens; ★ = foil, PT = português. Se tiveres mais na mão do que o número — ou uma carta que não aparece — ainda não está catalogada: fotografa. Atualiza sozinho todos os dias.</footer>
</div></body></html>"""


def main():
    with db.session() as con:
        out = build(con)
    print(f"colecao_cor.html escrito: {out}")


if __name__ == "__main__":
    main()
