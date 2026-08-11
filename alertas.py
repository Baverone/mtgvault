"""Alertas de preço: o que VENDER (cartas minhas que valorizaram) e o que
COMPRAR (cartas que me faltam para os top decks e que baixaram de preço).

Usa só o que o job diário já grava: `price_latest` (agora) e `price_history`
(que só guarda MUDANÇAS de preço). Poucos dados recentes = poucos alertas — é
honesto, não inventa movimentos. A wantlist de compra vem da cobertura do
metagame (as cartas em falta dos top decks).

Uso:  python alertas.py   ->  escreve alertas.html na raiz do repositório.
"""
from __future__ import annotations

import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import collection, db  # noqa: E402
import meta_coverage  # noqa: E402

WINDOW = 7         # janela de comparação (dias) — o histórico ainda é curto
MIN_PCT = 5.0      # só mostrar movimentos >= 5%
MIN_EUR = 1.0      # piso de preço, para não alertar cartas de cêntimos
TOP = 40           # máximo por lista


def _delta(con, sid, days=WINDOW):
    """(antes, agora, %) de uma impressão na janela. O 'antes' é o preço mais
    recente até há `days` dias; se não houver (histórico curto), cai para o mais
    antigo registado, para haver na mesma um ponto de comparação."""
    r = con.execute(
        """SELECT l.trend AS agora,
                  COALESCE(
                    (SELECT h.trend FROM price_history h
                      WHERE h.scryfall_id = ? AND h.finish = 'nonfoil' AND h.source = 'cardmarket'
                        AND h.date <= date('now', '-' || ? || ' days')
                      ORDER BY h.date DESC LIMIT 1),
                    (SELECT h2.trend FROM price_history h2
                      WHERE h2.scryfall_id = ? AND h2.finish = 'nonfoil' AND h2.source = 'cardmarket'
                      ORDER BY h2.date ASC LIMIT 1)
                  ) AS antes
             FROM price_latest l
            WHERE l.scryfall_id = ? AND l.finish = 'nonfoil' AND l.source = 'cardmarket'""",
        (sid, days, sid, sid)).fetchone()
    if not r or r["antes"] is None or r["agora"] is None or r["antes"] <= 0.10:
        return None
    return {"antes": r["antes"], "agora": r["agora"],
            "pct": round(100 * (r["agora"] - r["antes"]) / r["antes"], 1)}


def build_report(con):
    # VENDER: as minhas cartas que subiram (movers já é scoped à coleção)
    sell = [r for r in collection.movers(con, days=WINDOW)["up"]
            if (r["pct"] or 0) >= MIN_PCT and (r["after"] or 0) >= MIN_EUR]

    # COMPRAR: cartas em falta dos top decks cuja impressão mais barata baixou
    rep = meta_coverage.build_report(con)
    need = {}
    for pairs in rep["want"].values():
        for name, q in pairs:
            need[name] = max(need.get(name, 0), q)
    buy = []
    for name, prints in rep["prints"].items():
        priced = [p for p in prints if p.get("p") is not None]
        if not priced:
            continue
        cheap = min(priced, key=lambda p: p["p"])
        d = _delta(con, cheap["s"])
        if d and d["pct"] <= -MIN_PCT and d["antes"] >= MIN_EUR:
            buy.append({"name": name, "set": cheap["n"], "need": need.get(name, 1), **d})
    buy.sort(key=lambda x: x["pct"])            # maior queda primeiro
    sell.sort(key=lambda x: -(x["pct"] or 0))   # maior subida primeiro
    return {"sell": sell[:TOP], "buy": buy[:TOP]}


def _eur(v):
    return f"{v:,.2f} €".replace(",", " ") if v else "—"


def _rows_sell(items):
    out = ""
    for r in items:
        out += (f'<li><div class="ci"><div class="cn">{html.escape(r["name"])}'
                f'<span class="st">{html.escape(r["set_code"] or "")}</span></div></div>'
                f'<span class="mv">{_eur(r["before"])} → <b>{_eur(r["after"])}</b></span>'
                f'<span class="pc up">+{r["pct"]:.0f}%</span></li>')
    return out or '<li class="dim">sem subidas na janela</li>'


def _rows_buy(items):
    out = ""
    for r in items:
        out += (f'<li><div class="ci"><div class="cn"><b>{r["need"]}×</b> {html.escape(r["name"])}'
                f'<span class="st">{html.escape(r["set"] or "")}</span></div></div>'
                f'<span class="mv">{_eur(r["antes"])} → <b>{_eur(r["agora"])}</b></span>'
                f'<span class="pc down">{r["pct"]:.0f}%</span></li>')
    return out or '<li class="dim">sem descidas na janela</li>'


def build_html(rep, today):
    return (_TMPL.replace("%SELL%", _rows_sell(rep["sell"]))
            .replace("%BUY%", _rows_buy(rep["buy"]))
            .replace("%TODAY%", today).replace("%WIN%", str(WINDOW))
            .replace("%NSELL%", str(len(rep["sell"]))).replace("%NBUY%", str(len(rep["buy"]))))


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mtgvault — alertas de preço</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e8794b}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:900px;margin:0 auto;padding:24px 16px 60px}
 h1{margin:0 0 2px;font-size:22px} .sub{color:var(--muted);font-size:13px;margin-bottom:8px} .sub a{color:var(--accent)}
 .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
 @media(max-width:680px){.cols{grid-template-columns:1fr}}
 .box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
 h2{font-size:15px;margin:2px 0 8px} .g{color:var(--add)} .r{color:var(--warn)}
 ul{list-style:none;margin:0;padding:0;font-size:13px}
 li{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px solid var(--line)} li:first-child{border-top:0}
 .ci{flex:1;min-width:0} .cn{white-space:normal} .st{display:block;font-size:11px;color:var(--muted);text-transform:uppercase}
 .mv{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;font-size:12px} .mv b{color:var(--ink)}
 .pc{font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap;width:52px;text-align:right} .pc.up{color:var(--add)} .pc.down{color:var(--warn)}
 .dim{color:var(--muted)} footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>Alertas de preço</h1>
<div class="sub">Movimentos ≥ 5% nos últimos %WIN% dias · dados de %TODAY% · <a href="index.html">← início</a> · <a href="cobertura.html">cobertura</a> · <a href="colecao.html">galeria</a></div></header>
<div class="cols">
<div class="box"><h2 class="g">📈 Vender <span class="dim">— cartas tuas que valorizaram (%NSELL%)</span></h2><ul>%SELL%</ul></div>
<div class="box"><h2 class="r">📉 Comprar <span class="dim">— cartas que te faltam e baixaram (%NBUY%)</span></h2><ul>%BUY%</ul></div>
</div>
<footer>"Vender" = exemplares da tua coleção cujo preço subiu (podes realizar lucro). "Comprar" = cartas em falta dos top decks (ver cobertura) cuja impressão jogável mais barata desceu. Preços: tendência Cardmarket via Scryfall; o histórico só regista mudanças, por isso a janela pode ter poucos movimentos. Não é conselho financeiro.</footer>
</div></body></html>"""


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "alertas.html")
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    rep = build_report(con)
    out.write_text(build_html(rep, today), encoding="utf-8")
    return out, rep


def main():
    with db.session() as con:
        out, rep = build(con)
    print(f"alertas.html escrito: {out}  (vender {len(rep['sell'])}, comprar {len(rep['buy'])})")


if __name__ == "__main__":
    main()
