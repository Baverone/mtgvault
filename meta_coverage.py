"""Cobertura do metagame: os top decks de cada formato, quanto já tenho de cada
um (% completo) e o que falta comprar — com a IMAGEM de cada carta em falta.

Lê o que o job diário já produziu — arquétipos agrupados (`archetypes`) e a
análise de núcleo (`card_roles`) — e cruza com a coleção (`owned_playable`).
NÃO vai à net nem inventa listas: usa só o núcleo (as cartas que se levam
sempre) de cada arquétipo, calculado a partir das decklists reais recolhidas.

Ideia (pedido do André): em vez de eu dizer que decks tenho, o vault mostra-me
os melhores decks do momento e o estado da minha coleção para cada um. As
cartas que faltam em VÁRIOS dos decks mostrados juntam-se numa lista geral
(staples partilhados); em cada deck ficam só as específicas dele.

Imagem da carta em falta (crucial p/ saber que edição comprar):
  - se já tenho algumas (ex.: tenho 3, faltam 1), mostro a EDIÇÃO QUE POSSUO,
    para comprar igual;
  - se não tenho nenhuma, mostro a impressão legal mais barata (a do preço).
Impressões não jogáveis (gold-border World Championship, Collectors'/Intl.
Edition, digitais) ficam de fora dos preços e das sugestões.

Uso:  python meta_coverage.py   ->  escreve cobertura.html na raiz do repositório.
"""
from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

FORMATS = [
    ("standard", "Standard", 5, []),
    ("pioneer", "Pioneer", 5, ["__greasefang__"]),
    ("modern", "Modern", 10, []),
    ("legacy", "Legacy", 5, []),
    ("premodern", "Premodern", 10, []),
]

BASICS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
    "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes",
}

NICE = {"__greasefang__": "Greasefang"}

# quantos staples partilhados mostrar no topo (o resto vê-se em cada deck)
GENERAL_MAX = 24

# impressões que NÃO se jogam em torneio — fora dos preços e das sugestões de compra
_NOT_PLAYABLE = (
    "AND c.digital = 0 "
    "AND c.set_name NOT LIKE '%World Championship%' "
    "AND c.set_name NOT LIKE '%Collector%Edition%' "
    "AND c.set_name NOT LIKE '%International Edition%' "
    "AND c.set_name NOT LIKE '%Oversized%' "
)


def _thumb(uri):
    """Miniatura pequena da Scryfall a partir do image_uri 'normal'."""
    return uri.replace("/normal/", "/small/") if uri else ""


def _visual(con, name, owned_qty):
    """Que imagem/edição/preço mostrar para uma carta em falta.

    owned_qty>0  -> a edição que o André mais possui (para comprar igual).
    owned_qty==0 -> a impressão jogável mais barata (a que dita o preço).
    """
    if owned_qty > 0:
        r = con.execute(
            """SELECT c.set_code, c.set_name, c.image_uri, cp.finish,
                      SUM(cp.quantity) q,
                      (SELECT p.trend FROM price_latest p
                        WHERE p.scryfall_id = c.scryfall_id AND p.source = 'cardmarket'
                          AND p.finish = cp.finish) AS trend
                 FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.purpose = 'player'
                GROUP BY c.scryfall_id ORDER BY q DESC LIMIT 1""", (name,)).fetchone()
        if r:
            return {"img": _thumb(r["image_uri"]), "set_code": r["set_code"],
                    "set_name": r["set_name"], "unit": r["trend"], "mine": True}

    r = con.execute(
        f"""SELECT c.set_code, c.set_name, c.image_uri, p.trend
              FROM cards c JOIN price_latest p ON p.scryfall_id = c.scryfall_id
             WHERE c.name = ? AND p.source = 'cardmarket' AND p.finish = 'nonfoil'
               AND c.lang = 'en' {_NOT_PLAYABLE}
             ORDER BY p.trend ASC LIMIT 1""", (name,)).fetchone()
    if r:
        return {"img": _thumb(r["image_uri"]), "set_code": r["set_code"],
                "set_name": r["set_name"], "unit": r["trend"], "mine": False}
    # sem preço: pelo menos uma imagem jogável recente
    r = con.execute(
        f"""SELECT set_code, set_name, image_uri FROM cards c
             WHERE c.name = ? AND c.lang = 'en' {_NOT_PLAYABLE}
             ORDER BY released_at DESC LIMIT 1""", (name,)).fetchone()
    if r:
        return {"img": _thumb(r["image_uri"]), "set_code": r["set_code"],
                "set_name": r["set_name"], "unit": None, "mine": False}
    return {"img": "", "set_code": "", "set_name": "", "unit": None, "mine": False}


def _greasefang_id(con):
    r = con.execute(
        """SELECT a.id, COUNT(d.id) n FROM archetypes a
             JOIN decklists d ON d.archetype_id = a.id
            WHERE a.format = 'pioneer' AND a.id IN (
                  SELECT DISTINCT archetype_id FROM card_roles
                   WHERE card_name LIKE 'Greasefang%' AND core_copies >= 1)
            GROUP BY a.id ORDER BY n DESC LIMIT 1""").fetchone()
    return r["id"] if r else None


def _rank(con, fmt, n):
    return [r["id"] for r in con.execute(
        """SELECT a.id, COUNT(d.id) n FROM archetypes a
             JOIN decklists d ON d.archetype_id = a.id
            WHERE a.format = ? GROUP BY a.id ORDER BY n DESC LIMIT ?""", (fmt, n))]


def _label(con, aid):
    r = con.execute("SELECT label FROM archetypes WHERE id = ?", (aid,)).fetchone()
    return r["label"] if r else f"#{aid}"


def _n_lists(con, aid):
    return con.execute("SELECT COUNT(*) c FROM decklists WHERE archetype_id = ?",
                       (aid,)).fetchone()["c"]


def _display_name(con, aid, override=None):
    if override:
        return override
    parts = [p.strip() for p in _label(con, aid).split("/") if p.strip()]
    return " / ".join(parts[:2]) if parts else f"#{aid}"


def _core_rows(con, aid, board="main"):
    return con.execute(
        """SELECT card_name, core_copies, inclusion_rate FROM card_roles
             WHERE archetype_id = ? AND board = ? AND core_copies >= 1
               AND window_end = (SELECT MAX(window_end) FROM card_roles WHERE archetype_id = ?)
            ORDER BY inclusion_rate DESC, core_copies DESC""", (aid, board, aid)).fetchall()


def deck_coverage(con, aid, owned, override=None):
    total = have = 0
    missing = []
    for r in _core_rows(con, aid, "main"):
        name = r["card_name"]
        if name in BASICS:
            continue
        need = r["core_copies"]
        got = min(owned.get(name, 0), need)
        total += need
        have += got
        if got < need:
            v = _visual(con, name, owned.get(name, 0))
            missing.append({"name": name, "need": need, "have": got, "missing": need - got,
                            "unit": v["unit"], "cost": round((v["unit"] or 0) * (need - got), 2),
                            "img": v["img"], "set_name": v["set_name"], "mine": v["mine"]})
    pct = round(100 * have / total) if total else 0
    return {"id": aid, "name": _display_name(con, aid, override), "label": _label(con, aid),
            "n_lists": _n_lists(con, aid), "core_total": total, "have": have, "pct": pct,
            "missing": sorted(missing, key=lambda m: -(m["cost"] or 0))}


def build_report(con):
    owned = owned_playable(con)
    gid = _greasefang_id(con)
    sections, all_decks = [], []
    for fmt, title, n, extras in FORMATS:
        ids = _rank(con, fmt, n)
        for ex in extras:
            aid = gid if ex == "__greasefang__" else ex
            if aid and aid not in ids:
                ids.append(aid)
        decks = []
        for aid in ids:
            override = NICE["__greasefang__"] if (gid and aid == gid) else None
            decks.append(deck_coverage(con, aid, owned, override))
        decks.sort(key=lambda d: -d["n_lists"])
        sections.append({"fmt": fmt, "title": title, "decks": decks})
        all_decks += decks

    seen = defaultdict(list)
    for d in all_decks:
        for m in d["missing"]:
            seen[m["name"]].append(m)
    general, shared = [], set()
    for name, occ in seen.items():
        if len(occ) >= 2:
            shared.add(name)
            base = occ[0]
            general.append({"name": name, "need": max(m["missing"] for m in occ),
                            "unit": base["unit"], "img": base["img"],
                            "set_name": base["set_name"], "mine": base["mine"],
                            "n_decks": len(occ),
                            "cost": round((base["unit"] or 0) * max(m["missing"] for m in occ), 2)})
    general.sort(key=lambda g: (-g["n_decks"], -(g["cost"] or 0)))
    for d in all_decks:
        d["specific"] = [m for m in d["missing"] if m["name"] not in shared]
        d["spec_cost"] = round(sum(m["cost"] or 0 for m in d["specific"]), 2)
    return {"sections": sections, "general": general,
            "owned_total": sum(owned.values()),
            "general_cost": round(sum(g["cost"] or 0 for g in general), 2)}


# --- HTML ------------------------------------------------------------------
def _eur(v):
    return f"{v:,.2f} €".replace(",", " ") if v else "—"


def _bar(pct):
    col = "var(--add)" if pct >= 80 else "var(--gold)" if pct >= 45 else "var(--warn)"
    return (f'<div class="bar"><span style="width:{pct}%;background:{col}"></span>'
            f'<em>{pct}%</em></div>')


def _img_tag(uri):
    return (f'<img loading="lazy" src="{html.escape(uri)}" alt="" width="42" height="59">'
            if uri else '<div class="noimg"></div>')


def _edition(mine, have, set_name):
    if not set_name:
        return ""
    if mine:
        return f'<span class="ed mine">tens {have} · {html.escape(set_name)}</span>'
    return f'<span class="ed">+ barata: {html.escape(set_name)}</span>'


def _card_item(m):
    """Uma carta em falta de um deck, com miniatura e a edição a comprar."""
    price = _eur(m["cost"]) if m.get("unit") is not None else "<i>preço?</i>"
    return (f'<li>{_img_tag(m.get("img"))}<div class="ci"><div class="cn"><b>{m["missing"]}×</b> '
            f'{html.escape(m["name"])}</div>{_edition(m.get("mine"), m.get("have"), m.get("set_name"))}'
            f'</div><span class="pz">{price}</span></li>')


def _gen_item(g):
    """Uma carta na lista geral de staples partilhados."""
    price = _eur(g["cost"]) if g.get("unit") is not None else "<i>?</i>"
    return (f'<li>{_img_tag(g.get("img"))}<div class="ci"><div class="cn"><b>{g["need"]}×</b> '
            f'{html.escape(g["name"])} <span class="nd">{g["n_decks"]} decks</span></div>'
            f'{_edition(g.get("mine"), "algumas", g.get("set_name"))}</div>'
            f'<span class="pz">{price}</span></li>')


def build_html(rep, today):
    secs = ""
    for s in rep["sections"]:
        cards = ""
        for d in s["decks"]:
            spec = d["specific"]
            if spec:
                body = (f'<details><summary>{sum(m["missing"] for m in spec)} cartas específicas '
                        f'· {_eur(d["spec_cost"])}</summary><ul class="ml">'
                        + "".join(_card_item(m) for m in spec) + '</ul></details>')
            else:
                body = '<div class="ok">sem cartas específicas em falta ✓</div>'
            cards += (
                f'<div class="deck"><div class="dh"><div class="dn">{html.escape(d["name"])}'
                f'<span class="lab">{html.escape(d["label"])[:60]}</span></div>'
                f'<div class="pop">{d["n_lists"]} listas</div></div>{_bar(d["pct"])}'
                f'<div class="cnt">{d["have"]}/{d["core_total"]} do núcleo · '
                f'faltam {sum(m["missing"] for m in d["missing"])}</div>{body}</div>')
        secs += f'<section><h2>{s["title"]}</h2><div class="grid">{cards}</div></section>'

    shown = rep["general"][:GENERAL_MAX]
    gen = "".join(_gen_item(g) for g in shown)
    extra = len(rep["general"]) - len(shown)
    more = (f'<div class="dim" style="padding-top:8px">+ {extra} staples partilhados menores '
            f'(preço baixo) — vê cada deck para os detalhes</div>' if extra > 0 else "")

    return (_TMPL.replace("%SECS%", secs).replace("%GEN%", gen or "<li class='dim'>—</li>")
            .replace("%GENMORE%", more).replace("%TODAY%", today)
            .replace("%OWNED%", str(rep["owned_total"]))
            .replace("%GENCOST%", _eur(rep["general_cost"])))


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mtgvault — cobertura do metagame</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e8794b}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1120px;margin:0 auto;padding:24px 16px 70px}
 h1{margin:0 0 2px;font-size:22px} .sub{color:var(--muted);font-size:13px;margin-bottom:8px} .sub a{color:var(--accent)}
 h2{font-size:16px;margin:26px 0 6px;padding-bottom:6px;border-bottom:1px solid var(--line)}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
 .dh{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
 .dn{font-weight:700} .lab{display:block;color:var(--muted);font-size:11px;font-weight:400;margin-top:1px}
 .pop{color:var(--muted);font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}
 .bar{position:relative;height:16px;background:#0c0f14;border:1px solid var(--line);border-radius:999px;margin:9px 0 6px;overflow:hidden}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px} .bar em{position:absolute;right:8px;top:-1px;font-size:11px;font-style:normal;font-weight:700;mix-blend-mode:difference}
 .cnt{color:var(--muted);font-size:12px;margin-bottom:6px}
 details summary{cursor:pointer;color:var(--accent);font-size:13px} .ok{color:var(--add);font-size:13px}
 ul.ml,ul.gl{list-style:none;margin:8px 0 0;padding:0;font-size:13px}
 ul.ml li,ul.gl li{display:flex;align-items:center;gap:8px;padding:4px 0;border-top:1px solid var(--line)}
 ul.gl li:first-child{border-top:0}
 ul.ml img,ul.gl img,.noimg{border-radius:4px;flex:none;background:#0c0f14} .noimg{width:42px;height:59px;border:1px dashed var(--line)}
 .ci{min-width:0;flex:1} .cn{white-space:normal} .cn b{color:var(--ink)}
 .ed{display:block;font-size:11px;color:var(--muted)} .ed.mine{color:var(--add)}
 .nd{display:inline-block;font-size:11px;color:var(--accent);background:#12203f;padding:0 6px;border-radius:999px}
 .pz{margin-left:auto;color:var(--gold);font-variant-numeric:tabular-nums;white-space:nowrap;align-self:flex-start;padding-top:2px}
 .general{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:8px}
 .general h2{margin-top:0;border:0} .dim{color:var(--muted);font-size:12px}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>Cobertura do metagame</h1>
<div class="sub">Os melhores decks de cada formato e quanto já tens · %OWNED% cartas na coleção · dados de %TODAY% · <a href="index.html">← início</a> · <a href="colecao.html">galeria da coleção</a></div></header>
<div class="general"><h2>🛒 Staples que te faltam <span class="dim">(servem vários dos decks abaixo · total %GENCOST%)</span></h2>
<ul class="gl">%GEN%</ul>%GENMORE%</div>
%SECS%
<footer>% completo = cartas do núcleo (mainboard, sem terras básicas) que já tens, sobre o total do núcleo do arquétipo — o que as decklists reais levam quase sempre. Cada carta em falta mostra a imagem da edição a comprar: a que já tens (verde) se tiveres algumas, senão a impressão jogável mais barata. Preços: tendência Cardmarket (sem gold-border/digitais). "Específicas" de um deck = as que mais nenhum deck mostrado precisa; as partilhadas estão nos staples do topo.</footer>
</div></body></html>"""


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "cobertura.html")
    today = con.execute("SELECT MAX(window_end) w FROM card_roles").fetchone()["w"] or ""
    rep = build_report(con)
    out.write_text(build_html(rep, today), encoding="utf-8")
    return out, rep


def main():
    with db.session() as con:
        out, rep = build(con)
    n = sum(len(s["decks"]) for s in rep["sections"])
    print(f"cobertura.html escrito: {out}  ({n} decks, {len(rep['general'])} staples partilhados)")


if __name__ == "__main__":
    main()
