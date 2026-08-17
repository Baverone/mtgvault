"""Gera metafaltas.html — "Decks meta para completar".

Os decks do METAGAME (não os alvos do André) em que ele já está a >=70% —
ou seja, os que está quase a conseguir montar e vale a pena completar. Top-5 de
Modern, Legacy e Premodern, ordenados por quão completos estão, com as cartas
que faltam (imagem da edição + preço). Reutiliza meta_coverage. NÃO inventa nada.
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402


def _config():
    try:
        return json.loads((ROOT / "colecao_config.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _scryfall_banned(con, fmt):
    """Cartas com legalities='banned' no formato, segundo a Scryfall. É a rede de
    segurança automática — mas o bulk deles atrasa-se face aos anúncios, por isso
    há também a lista manual em colecao_config.json."""
    try:
        return {r["card_name"] if "card_name" in r.keys() else r["name"]
                for r in con.execute(
                    "SELECT DISTINCT name FROM cards WHERE json_extract(legalities, ?)='banned'",
                    (f"$.{fmt}",))}
    except Exception:  # noqa: BLE001  (json_extract pode não existir; a lista manual chega)
        return set()


def _banned_set(con, fmt, cfg):
    b = set(cfg.get("banimentos_manuais", {}).get(fmt, []))
    return b | _scryfall_banned(con, fmt)


def _depends_on_banned(con, aid, banned):
    """True se o deck joga uma carta banida COMO NÚCLEO (`core_copies >= 1`, main
    ou side) — ou seja, uma carta que a % de completude conta. Aí o arquétipo,
    como é hoje, é ilegal → não o mostrar. Um 1-of marginal (core=0) não conta: o
    deck sobrevive sem ela e o `deck_coverage` nem sequer a inclui. Quando saírem
    listas pós-ban, o `card_roles` atualiza-se e o deck reaparece sozinho."""
    if not banned:
        return False
    for board in ("main", "side"):
        if any(r["card_name"] in banned for r in mc._core_rows(con, aid, board)):
            return True
    return False

FORMATS = [("pioneer", "Pioneer"), ("modern", "Modern"),
           ("legacy", "Legacy"), ("premodern", "Premodern")]
MIN_PCT = 50   # só decks a pelo menos 50% de completos
TOP = 5        # top-5 por formato
SCAN = 30      # quantos arquétipos do topo analisar para encontrar os 5

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a href="meusdecks.html">🎴 Os meus decks</a>'
        '<a href="metagame.html">🌐 Metagame</a>'
        '<a href="buildability.html">🔨 Montar</a>'
        '<a href="colecao_cor.html">📚 Binders</a><a href="reservedlist.html">🏆 Reserved List</a></nav>')


def _cardli(m):
    price = f'{m["unit"]:.2f}€' if m["unit"] else "?"
    ed = '<span class="ed">✓ed</span>' if m["mine"] else ""
    img = f'<img loading="lazy" src="{m["img"]}" alt="">' if m["img"] else '<div class="noimg"></div>'
    return (f'<div class="c" title="{html.escape(m["name"])}">{img}'
            f'<span class="q">{m["missing"]}x</span><span class="pz">{price}</span>{ed}</div>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "metafaltas.html")
    owned = owned_playable(con)
    cfg = _config()
    tcache = {}
    secs = ""
    n_total = 0
    for fmt, lbl in FORMATS:
        df = mc._format_df(con, fmt)
        banned = _banned_set(con, fmt, cfg)
        found = []
        seen = set()
        for aid, _score in mc._rank(con, fmt, SCAN):
            name = mc._name_for(con, aid, df, tcache)
            if name in seen:
                continue
            seen.add(name)
            # Decks cujo NÚCLEO depende de uma carta banida no formato estão
            # mortos como são hoje — não os mostres como "para completar". Apanha
            # bans recentes (lista manual) e os que a Scryfall já regista.
            if _depends_on_banned(con, aid, banned):
                continue
            cov = mc.deck_coverage(con, aid, owned, name)
            if cov["pct"] >= MIN_PCT:
                found.append(cov)
        found.sort(key=lambda d: -d["pct"])
        found = found[:TOP]
        n_total += len(found)
        cards = ""
        if not found:
            cards = '<div class="dim">Nenhum deck do metagame a ≥70% ainda.</div>'
        for d in found:
            col = "var(--add)" if d["pct"] >= 90 else "var(--gold)"
            miss = [m for m in d["missing"] if m["name"] not in mc.BASICS]
            cost = round(sum((m["unit"] or 0) * m["missing"] for m in miss), 2)
            grid = "".join(_cardli(m) for m in miss) or '<div class="dim">só falta básicas ✅</div>'
            cards += (
                f'<div class="deck"><div class="dh"><b>{html.escape(d["name"])}</b>'
                f'<span class="pp" style="color:{col}">{d["pct"]}%</span></div>'
                f'<div class="mt">{d["have"]}/{d["core_total"]} do núcleo · '
                f'faltam {len(miss)} cartas · {cost:.2f}€</div>'
                f'<div class="grid">{grid}</div></div>')
        secs += (f'<section><h2>{html.escape(lbl)} '
                 f'<span class="dim">{len(found)} decks ≥{MIN_PCT}%</span></h2>{cards}</section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    labels = [lbl for _f, lbl in FORMATS]
    fmts = ", ".join(labels[:-1]) + " e " + labels[-1] if len(labels) > 1 else labels[0]
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SECS%", secs)
                   .replace("%N%", str(n_total)).replace("%TODAY%", today)
                   .replace("%MIN%", str(MIN_PCT)).replace("%FMTS%", fmts), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decks meta para completar</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px} .tabs a:hover{border-color:var(--accent)}
 h2{font-size:15px;margin:22px 0 8px;border-bottom:1px solid var(--line);padding-bottom:5px} .dim{color:var(--muted);font-size:12px;font-weight:400}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:11px 14px;margin-bottom:9px}
 .dh{display:flex;justify-content:space-between;align-items:baseline} .dh b{font-size:15px} .pp{font-weight:800;font-size:16px}
 .mt{color:var(--muted);font-size:12px;margin:3px 0 6px}
 .grid{display:flex;flex-wrap:wrap;gap:6px}
 .c{position:relative;width:64px} .c img,.c .noimg{width:64px;height:89px;border-radius:5px;display:block;background:#0c0f14}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:10px;padding:0 4px;border-radius:6px}
 .c .pz{position:absolute;bottom:2px;left:2px;right:2px;text-align:center;background:#000a;color:var(--gold);font-size:9px;border-radius:4px}
 .c .ed{position:absolute;top:2px;right:2px;background:#12351f;color:var(--add);font-size:8px;padding:0 3px;border-radius:4px}
 footer{margin-top:24px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎯 Decks meta para completar</h1>
<div class="lead">Decks do metagame em que já estás a ≥%MIN%% — quase a montar · %N% decks · dados de %TODAY%</div>
%TABS%</header>
%SECS%
<footer>Só os decks do metagame (não os teus alvos) em que já tens ≥%MIN%% do núcleo — os que estás mais perto de conseguir montar. Top-5 de %FMTS%, com a imagem da edição a comprar (✓ed = já tens uma) e o preço. Atualiza diariamente.</footer>
</div></body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("metafaltas.html:", build(con))


if __name__ == "__main__":
    main()
