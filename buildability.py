"""Gera buildability.html — "Lista de Compras".

SÓ os decks-alvo do André (tabela `decks`), e SÓ os que estão a mais de 50% de
completos (faltam menos de 50% das cartas) — ou seja, os que vale a pena acabar
de comprar. Mostra as cartas que faltam, com a imagem da edição a comprar e o
preço. As que faltam em vários decks vão para uma secção de "staples" (compras
uma vez, servem vários); em cada deck ficam só as específicas.

Reutiliza meta_coverage._visual (imagem+preço). NÃO inventa nada.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

BASICS = mc.BASICS
FMT_LABEL = {"standard": "Standard", "pioneer": "Pioneer", "modern": "Modern",
             "legacy": "Legacy", "premodern": "Premodern",
             "duel-commander": "Duel Commander", "cedh": "cEDH", "pauper": "Pauper"}
FMT_ORDER = ["standard", "pioneer", "modern", "legacy", "premodern",
             "duel-commander", "cedh", "pauper"]
MIN_PCT = 50  # só decks a mais de 50% de completos


def deck_status(con, deck_id, owned):
    need = have = 0
    missing = []
    for r in con.execute("""SELECT card_name nm, SUM(quantity) q FROM deck_cards
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
                            "img": v["img"], "mine": v["mine"]})
    pct = round(100 * have / need) if need else 0
    return {"need": need, "have": have, "pct": pct, "missing": missing}


def _cardli(m):
    price = f'{m["unit"]:.2f}€' if m["unit"] else "?"
    ed = '<span class="ed">✓ed</span>' if m["mine"] else ""
    img = f'<img loading="lazy" src="{m["img"]}" alt="">' if m["img"] else '<div class="noimg"></div>'
    return (f'<div class="c" title="{html.escape(m["name"])}">{img}'
            f'<span class="q">{m["need"]}x</span><span class="pz">{price}</span>{ed}</div>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "buildability.html")
    owned = owned_playable(con)
    decks = []
    for d in con.execute("SELECT id, name, format FROM decks"):
        st = deck_status(con, d["id"], owned)
        if st["need"] == 0 or st["pct"] <= MIN_PCT or not st["missing"]:
            continue
        decks.append({"name": d["name"], "format": d["format"], **st})
    decks.sort(key=lambda x: -x["pct"])

    # staples: cartas que faltam em >=2 destes decks
    seen = defaultdict(list)
    for d in decks:
        for m in d["missing"]:
            seen[m["name"]].append(m)
    shared = {nm for nm, occ in seen.items() if len(occ) >= 2}
    staples = []
    for nm in shared:
        occ = seen[nm]
        need = max(m["need"] for m in occ)
        staples.append({**occ[0], "need": need, "n_decks": len(occ),
                        "cost": (occ[0]["unit"] or 0) * need})
    staples.sort(key=lambda s: (-s["n_decks"], -s["cost"]))

    total = 0.0
    sec = ""
    if staples:
        scost = sum(s["cost"] for s in staples)
        total += scost
        sec += (f'<section><h2>🧩 Staples <span class="dim">servem vários decks · '
                f'{scost:.2f}€</span></h2><div class="grid">'
                + "".join(_cardli(s) for s in staples) + "</div></section>")
    for d in decks:
        spec = [m for m in d["missing"] if m["name"] not in shared]
        cost = sum((m["unit"] or 0) * m["need"] for m in spec)
        total += cost
        col = "var(--add)" if d["pct"] >= 90 else "var(--gold)"
        grid = "".join(_cardli(m) for m in spec) or '<div class="dim">só staples partilhados</div>'
        sec += (
            f'<section class="deck"><h2>{html.escape(d["name"])} '
            f'<span class="dim">[{html.escape(FMT_LABEL.get(d["format"], d["format"]))}] · '
            f'<b style="color:{col}">{d["pct"]}%</b> · falta {cost:.2f}€</span></h2>'
            f'<div class="grid">{grid}</div></section>')

    empty = "" if decks else ('<div class="dim" style="padding:20px 0">Nenhum deck acima de 50% com '
                              'cartas em falta — ou já os tens, ou estão longe de completos.</div>')
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%SECS%", sec or empty).replace("%N%", str(len(decks)))
                   .replace("%TOTAL%", f"{total:.2f}").replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lista de Compras</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 h2{font-size:15px;margin:20px 0 8px;border-bottom:1px solid var(--line);padding-bottom:5px} .dim{color:var(--muted);font-size:12px;font-weight:400}
 section.deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:10px} section.deck h2{border:0;margin:0 0 6px}
 .grid{display:flex;flex-wrap:wrap;gap:6px}
 .c{position:relative;width:66px} .c img,.c .noimg{width:66px;height:92px;border-radius:5px;display:block;background:#0c0f14}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:10px;padding:0 4px;border-radius:6px}
 .c .pz{position:absolute;bottom:2px;left:2px;right:2px;text-align:center;background:#000a;color:var(--gold);font-size:9px;border-radius:4px}
 .c .ed{position:absolute;top:2px;right:2px;background:#12351f;color:var(--add);font-size:8px;padding:0 3px;border-radius:4px}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🛒 Lista de Compras</h1>
<div class="lead">Os teus decks a mais de 50% · %N% decks · total ~%TOTAL%€ · dados de %TODAY%</div>
<nav class="tabs"><a href="index.html">🏠 Início</a><a href="meusdecks.html">🎴 Os meus decks</a><a href="metagame.html">🌐 Metagame</a><a class="cur" href="buildability.html">🔨 Montar</a><a href="colecao_cor.html">🎨 Coleção</a></nav></header>
%SECS%
<footer>Só os teus decks que estão a mais de 50% de completos (vale a pena acabar). As <b>staples</b> faltam em vários decks — compras uma vez, servem todos. Cada carta mostra a edição a comprar (✓ed = já tens uma edição) e o preço (tendência Cardmarket). Atualiza diariamente.</footer>
</div></body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("buildability.html:", build(con))


if __name__ == "__main__":
    main()
