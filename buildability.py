"""Gera buildability.html — "O que consigo montar".

Para cada deck-alvo do André (tabela `decks`: os 3 de Modern, Legacy, Premodern
Stiflenought, Pioneer, Standard, Cloud DC...), mostra a % que já tem da lista e
as cartas que faltam (com imagem da edição a comprar e preço). Ordenado por
quão perto está de estar montado. A wantlist é POR DECK (cada carta que falta
está debaixo do deck a que pertence).

Cruza a lista (`deck_cards`) com a coleção (`owned_playable`, que já normaliza
os nomes de dupla-face). NÃO inventa nada. Corre no job diário.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402  (reutiliza _visual: imagem+preço da edição)
from mtgvault.collection import owned_playable  # noqa: E402

BASICS = mc.BASICS
# ordem e rótulo dos formatos
FMT_LABEL = {"standard": "Standard", "pioneer": "Pioneer", "modern": "Modern",
             "legacy": "Legacy", "premodern": "Premodern",
             "duel-commander": "Duel Commander", "cedh": "cEDH", "pauper": "Pauper"}
FMT_ORDER = ["standard", "pioneer", "modern", "legacy", "premodern",
             "duel-commander", "cedh", "pauper"]


def deck_status(con, deck_id, owned):
    """% da lista (mainboard, sem básicas) que já tenho + o que falta."""
    need = have = 0
    missing = []
    for r in con.execute(
        """SELECT card_name nm, SUM(quantity) q FROM deck_cards
            WHERE deck_id = ? AND board IN ('main', '') GROUP BY card_name""", (deck_id,)):
        nm = r["nm"]
        if nm in BASICS:
            continue
        q = r["q"]
        o = owned.get(nm, 0)
        got = min(q, o)
        need += q
        have += got
        if got < q:
            v = mc._visual(con, nm, o)
            missing.append({"name": nm, "need": q - got, "unit": v["unit"],
                            "img": v["img"], "set_name": v["set_name"], "mine": v["mine"]})
    pct = round(100 * have / need) if need else 0
    cost = round(sum((m["unit"] or 0) * m["need"] for m in missing), 2)
    missing.sort(key=lambda m: -((m["unit"] or 0) * m["need"]))
    return {"need": need, "have": have, "pct": pct, "missing": missing, "cost": cost}


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "buildability.html")
    owned = owned_playable(con)
    by_fmt = defaultdict(list)
    for d in con.execute("SELECT id, name, format FROM decks"):
        st = deck_status(con, d["id"], owned)
        if st["need"] == 0:
            continue
        by_fmt[d["format"]].append({"name": d["name"], **st})

    secs = ""
    for fmt in FMT_ORDER + [f for f in by_fmt if f not in FMT_ORDER]:
        decks = by_fmt.get(fmt)
        if not decks:
            continue
        decks.sort(key=lambda x: -x["pct"])
        secs += f'<h2>{html.escape(FMT_LABEL.get(fmt, fmt))}</h2>'
        for d in decks:
            col = "var(--add)" if d["pct"] >= 90 else "var(--gold)" if d["pct"] >= 60 else "var(--warn)"
            miss_txt = (f'faltam {len(d["missing"])} cartas · {d["cost"]:.2f}€'
                        if d["missing"] else "COMPLETO ✅")
            grid = ""
            for m in d["missing"]:
                mine = ' title="tens esta edição"' if m["mine"] else ""
                price = f'{m["unit"]:.2f}€' if m["unit"] else "?"
                grid += (f'<div class="c"{mine}><img loading="lazy" src="{m["img"]}" alt="">'
                         f'<span class="q">{m["need"]}x</span>'
                         f'<span class="pz">{price}</span>'
                         f'{"<span class=ed>✓ed</span>" if m["mine"] else ""}</div>')
            secs += (
                f'<div class="deck"><div class="dh"><b>{html.escape(d["name"])}</b>'
                f'<span class="hv">{d["have"]}/{d["need"]}</span></div>'
                f'<div class="bar"><span style="width:{d["pct"]}%;background:{col}"></span>'
                f'<em>{d["pct"]}%</em></div>'
                f'<div class="mt">{miss_txt}</div>'
                + (f'<div class="grid">{grid}</div>' if grid else "")
                + "</div>")

    total = sum(len(v) for v in by_fmt.values())
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%SECS%", secs).replace("%N%", str(total))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>O que consigo montar</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:20px 14px 60px}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px;margin-bottom:10px} .sub a{color:var(--accent)}
 h2{font-size:15px;margin:22px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);padding-bottom:4px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px}
 .dh{display:flex;justify-content:space-between;align-items:baseline} .dh b{font-size:15px} .hv{color:var(--muted);font-size:12px}
 .bar{position:relative;height:18px;background:#0c0f14;border-radius:999px;margin:6px 0;overflow:hidden}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .bar em{position:absolute;right:8px;top:1px;font-size:11px;font-style:normal;font-weight:700;mix-blend-mode:difference}
 .mt{color:var(--muted);font-size:12px;margin-bottom:6px}
 .grid{display:flex;flex-wrap:wrap;gap:6px}
 .c{position:relative;width:66px} .c img{width:66px;border-radius:5px;display:block;background:#0c0f14}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:10px;padding:0 4px;border-radius:6px}
 .c .pz{position:absolute;bottom:2px;left:2px;right:2px;text-align:center;background:#000a;color:var(--gold);font-size:9px;border-radius:4px}
 .c .ed{position:absolute;top:2px;right:2px;background:#12351f;color:var(--add);font-size:8px;padding:0 3px;border-radius:4px}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🔨 O que consigo montar</h1>
<div class="sub">%N% decks-alvo · ordenados por quão perto estão · dados de %TODAY% · <a href="index.html">← início</a> · <a href="cobertura.html">metagame</a> · <a href="colecao_cor.html">coleção</a></div></header>
%SECS%
<footer>Cada deck-alvo com a % da lista que já tens e as cartas que faltam (imagem da edição a comprar, ✓ed = edição que já tens, e preço). Cruza a lista atual do deck com toda a coleção. Terras básicas não contam. Atualiza sozinho todos os dias.</footer>
</div></body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("buildability.html:", build(con))


if __name__ == "__main__":
    main()
