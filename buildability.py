"""Gera buildability.html — "O que consigo montar" + loadout interativo.

Por formato, mostra primeiro os DECKS-ALVO do André (tabela `decks`) e a seguir
o RESTO do metagame desse formato (top-10 por arquétipo, ponderado — vem de
`meta_coverage`). Cada deck: a % que já tem da lista e as cartas em falta
(imagem da edição a comprar + preço). Ordenado por quão perto está.

LOADOUT (ideia do André, 2026-08-14): cada deck tem um checkmark "montado". Ao
marcar, as cartas ficam reservadas a esse deck (no cliente). Para cada deck NÃO
montado, calcula o que terias de **mover** dos montados (cartas comuns) e o que
ainda terias de **comprar**. Assim mantém vários decks montados e só passa as
cartas comuns. Client-side (localStorage) — fica na cloud, sem servidor.

Cruza a lista (`deck_cards`/consenso) com a coleção (`owned_playable`, que
normaliza os nomes de dupla-face). NÃO inventa nada. Corre no job diário.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402  (ranking do metagame + _visual/_core_rows)
from mtgvault.collection import owned_playable  # noqa: E402

BASICS = mc.BASICS
FMT_LABEL = {"standard": "Standard", "pioneer": "Pioneer", "modern": "Modern",
             "legacy": "Legacy", "premodern": "Premodern",
             "duel-commander": "Duel Commander", "cedh": "cEDH", "pauper": "Pauper"}
FMT_ORDER = ["standard", "pioneer", "modern", "legacy", "premodern",
             "duel-commander", "cedh", "pauper"]
META_FMTS = ["standard", "pioneer", "modern", "legacy", "premodern"]


def deck_status(con, deck_id, owned):
    """Deck-alvo (tabela decks): lista completa (main, sem básicas) + o que falta."""
    full = []
    need = have = 0
    missing = []
    for r in con.execute(
        """SELECT card_name nm, SUM(quantity) q FROM deck_cards
            WHERE deck_id = ? AND board IN ('main', '') GROUP BY card_name""", (deck_id,)):
        nm = r["nm"]
        if nm in BASICS:
            continue
        q = r["q"]
        full.append([nm, q])
        o = owned.get(nm, 0)
        got = min(q, o)
        need += q
        have += got
        if got < q:
            v = mc._visual(con, nm, o)
            missing.append({"name": nm, "need": q - got, "unit": v["unit"],
                            "img": v["img"], "mine": v["mine"]})
    return _pack(full, need, have, missing)


def _meta_deck(con, aid, name, owned):
    """Deck do metagame (arquétipo): consenso de core como lista, + o que falta."""
    cov = mc.deck_coverage(con, aid, owned, name)
    full = [[r["card_name"], r["core_copies"]] for r in mc._core_rows(con, aid, "main")
            if r["card_name"] not in BASICS]
    missing = [{"name": m["name"], "need": m["missing"], "unit": m["unit"],
                "img": m["img"], "mine": m["mine"]} for m in cov["missing"]]
    st = _pack(full, cov["core_total"], cov["have"], missing)
    st["pct"] = cov["pct"]   # usa a % do deck_coverage (inclui sideboard de consenso)
    return st


def _pack(full, need, have, missing):
    pct = round(100 * have / need) if need else 0
    missing = sorted(missing, key=lambda m: -((m["unit"] or 0) * m["need"]))
    cost = round(sum((m["unit"] or 0) * m["need"] for m in missing), 2)
    return {"full": full, "need": need, "have": have, "pct": pct, "missing": missing, "cost": cost}


def _deck_html(d):
    col = "var(--add)" if d["pct"] >= 90 else "var(--gold)" if d["pct"] >= 60 else "var(--warn)"
    miss_txt = (f'faltam {len(d["missing"])} cartas · {d["cost"]:.2f}€'
                if d["missing"] else "COMPLETO ✅")
    grid = ""
    for m in d["missing"]:
        mine = ' title="tens esta edição"' if m["mine"] else ""
        price = f'{m["unit"]:.2f}€' if m["unit"] else "?"
        grid += (f'<div class="c"{mine}><img loading="lazy" src="{m["img"]}" alt="">'
                 f'<span class="q">{m["need"]}x</span><span class="pz">{price}</span>'
                 f'{"<span class=ed>✓ed</span>" if m["mine"] else ""}</div>')
    nm = html.escape(d["name"])
    cls = "deck" if d["is_target"] else "deck meta"
    tag = "" if d["is_target"] else '<span class="mtag">metagame</span>'
    return (
        f'<div class="deck"><div class="dh">'
        f'<b>{nm}</b>{tag}<span class="hv">{d["have"]}/{d["need"]}</span></div>'
        f'<div class="bar"><span style="width:{d["pct"]}%;background:{col}"></span>'
        f'<em>{d["pct"]}%</em></div>'
        f'<div class="mt">{miss_txt}</div>'
        + (f'<div class="grid">{grid}</div>' if grid else "")
        + "</div>")


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "buildability.html")
    owned = owned_playable(con)
    try:
        montado_cfg = json.loads(
            (ROOT / "colecao_config.json").read_text(encoding="utf-8")).get("decks_montados", [])
    except Exception:
        montado_cfg = []
    deck_full = {}          # nome -> [[carta, qty], ...]  (para o loadout no cliente)
    relevant = set()
    targets = defaultdict(list)
    target_names = defaultdict(set)
    for d in con.execute("SELECT id, name, format FROM decks"):
        st = deck_status(con, d["id"], owned)
        if st["need"] == 0:
            continue
        deck_full[d["name"]] = st["full"]
        relevant.update(c for c, _ in st["full"])
        targets[d["format"]].append({"name": d["name"], "is_target": True, **st})
        target_names[d["format"]].add(d["name"].lower())

    tcache = {}
    meta = defaultdict(list)
    for fmt in META_FMTS:
        dfq = mc._format_df(con, fmt)
        for aid, _score in mc._rank(con, fmt, 10):
            name = mc._name_for(con, aid, dfq, tcache)
            low = name.lower()
            # não repetir um deck que já é alvo (ex.: Stiflenought (Luffy) vs Stiflenought)
            if any(low in tn or tn.split(" (")[0].strip() in low for tn in target_names[fmt]):
                continue
            if name in deck_full:   # nomes iguais entre arquétipos — evita colisão
                continue
            st = _meta_deck(con, aid, name, owned)
            if st["need"] == 0:
                continue
            deck_full[name] = st["full"]
            relevant.update(c for c, _ in st["full"])
            meta[fmt].append({"name": name, "is_target": False, **st})

    owned_sub = {c: owned.get(c, 0) for c in relevant}

    secs = ""
    seen = set()
    for fmt in FMT_ORDER + [f for f in list(targets) + list(meta) if f not in FMT_ORDER]:
        if fmt in seen:
            continue
        seen.add(fmt)
        tg = sorted(targets.get(fmt, []), key=lambda x: -x["pct"])
        mt = sorted(meta.get(fmt, []), key=lambda x: -x["pct"])
        if not tg and not mt:
            continue
        secs += f'<h2>{html.escape(FMT_LABEL.get(fmt, fmt))}</h2>'
        if tg:
            secs += '<div class="rest">🎯 os teus alvos</div>'
            secs += "".join(_deck_html(d) for d in tg)
        if mt:
            secs += '<div class="rest">📊 resto do metagame</div>'
            secs += "".join(_deck_html(d) for d in mt)

    n_tg = sum(len(v) for v in targets.values())
    n_mt = sum(len(v) for v in meta.values())
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(
        _TMPL.replace("%SECS%", secs).replace("%NTG%", str(n_tg)).replace("%NMT%", str(n_mt))
             .replace("%TODAY%", today),
        encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>O que consigo montar</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:20px 14px 60px}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px;margin-bottom:6px} .sub a{color:var(--accent)}
 .tip{background:#141b26;border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:12px;color:var(--muted);margin-bottom:10px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 h2{font-size:15px;margin:22px 0 4px;color:var(--ink);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);padding-bottom:4px}
 .rest{color:var(--muted);font-size:12px;margin:10px 0 6px;font-weight:600}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px}
 .deck.meta{background:#12151b;opacity:.92} .deck.on{border-color:var(--add);box-shadow:inset 0 0 0 1px var(--add)}
 .mtag{font-size:9px;color:var(--muted);border:1px solid var(--line);border-radius:6px;padding:0 4px;text-transform:uppercase}
 .dh{display:flex;align-items:center;gap:8px} .dh b{font-size:15px} .hv{color:var(--muted);font-size:12px;margin-left:auto}
 .mont-l{font-size:11px;color:var(--muted);cursor:pointer;user-select:none;display:flex;align-items:center;gap:3px}
 .deck.on .mont-l{color:var(--add)}
 .bar{position:relative;height:18px;background:#0c0f14;border-radius:999px;margin:6px 0;overflow:hidden}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .bar em{position:absolute;right:8px;top:1px;font-size:11px;font-style:normal;font-weight:700;mix-blend-mode:difference}
 .mt{color:var(--muted);font-size:12px} .loadout{font-size:12px;margin:5px 0}
 .loadout .mv{color:var(--gold)} .loadout .by{color:var(--warn)} .loadout .ok{color:var(--add)}
 .grid{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
 .c{position:relative;width:66px} .c img{width:66px;border-radius:5px;display:block;background:#0c0f14}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:10px;padding:0 4px;border-radius:6px}
 .c .pz{position:absolute;bottom:2px;left:2px;right:2px;text-align:center;background:#000a;color:var(--gold);font-size:9px;border-radius:4px}
 .c .ed{position:absolute;top:2px;right:2px;background:#12351f;color:var(--add);font-size:8px;padding:0 3px;border-radius:4px}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🔨 O que consigo montar</h1>
<div class="sub">%NTG% decks-alvo + %NMT% do metagame · dados de %TODAY%</div>
<nav class="tabs"><a href="index.html">🏠 Início</a><a href="meusdecks.html">🎴 Os meus decks</a><a href="metagame.html">🌐 Metagame</a><a class="cur" href="buildability.html">🔨 Montar</a><a href="colecao_cor.html">🎨 Coleção</a></nav></header>
%SECS%
<footer>Por formato: primeiro os teus alvos, depois o resto do metagame (top-10 ponderado). Cada deck com a % que já tens e as cartas em falta (imagem da edição, ✓ed = edição que já tens, preço). Terras básicas não contam. Atualiza sozinho todos os dias.</footer>
</div></body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("buildability.html:", build(con))


if __name__ == "__main__":
    main()
