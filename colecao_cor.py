"""Gera colecao_cor.html — a coleção organizada como o André a arruma
fisicamente: por COR e, dentro de cada cor, por CUSTO DE MANA (CMC). Serve de
guia para arrumar e para ver o que ainda falta fotografar (o que não aparecer
aqui, ou de que tenha mais na mão do que o número, ainda não está catalogado).

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


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "colecao_cor.html")
    groups = defaultdict(lambda: defaultdict(list))  # bucket -> cmc -> [rows]
    for r in con.execute(
        """SELECT c.scryfall_id sid, c.name nm, c.cmc cmc, c.type_line tl,
                  c.color_identity ci, cp.finish fin, cp.language lang, SUM(cp.quantity) q
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            GROUP BY c.scryfall_id, cp.finish, cp.language"""
    ):
        b = _bucket(r["tl"], r["ci"])
        cmc = 0 if b == "Terras" else int(r["cmc"] or 0)
        groups[b][cmc].append(r)
    total = sum(x["q"] for cm in groups.values() for lst in cm.values() for x in lst)

    nav = " · ".join(f'<a href="#{b}">{b}</a>' for b in ORDER if groups.get(b))
    secs = ""
    for b in ORDER:
        cm = groups.get(b)
        if not cm:
            continue
        tot = sum(x["q"] for lst in cm.values() for x in lst)
        secs += f'<h2 id="{html.escape(b)}">{html.escape(b)} <span class="n">{tot}</span></h2>'
        for cmc in sorted(cm):
            cards = sorted(cm[cmc], key=lambda x: (x["nm"] or "").lower())
            sub = "Terras" if b == "Terras" else f"CMC {cmc}"
            secs += f'<h3>{sub} <span class="n">{sum(x["q"] for x in cards)}</span></h3><div class="grid">'
            for x in cards:
                fo = '<span class="mk foil">★</span>' if x["fin"] == "foil" else ""
                pt = '<span class="mk pt">PT</span>' if x["lang"] == "pt" else ""
                secs += (f'<div class="c" title="{html.escape(x["nm"] or "")}">'
                         f'<img loading="lazy" src="{_img(x["sid"])}" alt="">'
                         f'<span class="q">{x["q"]}</span>{fo}{pt}</div>')
            secs += "</div>"
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%SECS%", secs).replace("%NAV%", nav)
                   .replace("%TOTAL%", str(total)).replace("%TODAY%", today), encoding="utf-8")
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
 h2{font-size:17px;margin:20px 0 4px;border-bottom:2px solid var(--line);padding-bottom:4px}
 h3{color:var(--muted);font-size:12px;margin:12px 0 4px;text-transform:uppercase;letter-spacing:.04em}
 .n{color:var(--muted);font-size:12px;font-weight:400}
 .grid{display:flex;flex-wrap:wrap;gap:6px}
 .c{position:relative;width:74px} .c img{width:74px;border-radius:5px;display:block;background:#0c0f14}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:11px;padding:0 5px;border-radius:7px}
 .mk{position:absolute;bottom:3px;right:3px;font-size:10px;font-weight:700}
 .mk.foil{color:var(--gold);text-shadow:0 0 3px #000} .mk.pt{background:#12351f;color:var(--add);border-radius:4px;padding:0 3px;font-size:9px}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎨 Coleção — por cor e custo de mana</h1>
<div class="sub">%TOTAL% cartas · a ordem por que arrumar · dados de %TODAY% · <a href="index.html">← início</a> · <a href="cobertura.html">cobertura</a> · <a href="colecao.html">galeria (por deck)</a></div></header>
<div class="nav">%NAV%</div>
%SECS%
<footer>Organizado como arrumas fisicamente: por cor e, dentro de cada cor, por custo de mana (as Terras à parte, por nome). O número em cada carta é quantas tens catalogadas; ★ = foil, PT = português. Se tiveres mais na mão do que o número — ou uma carta que não aparece — ainda não está catalogada: fotografa. Atualiza sozinho todos os dias.</footer>
</div></body></html>"""


def main():
    with db.session() as con:
        out = build(con)
    print(f"colecao_cor.html escrito: {out}")


if __name__ == "__main__":
    main()
