"""Gera caixarl.html — a "Caixa Reserved List".

Regra do André (2026-08-31):
- RL em INGLÊS só pode ser usada em cEDH + Duel-Commander (baldes Blue Farm, Cloud
  cEDH, Cloud). O que não estiver nesses decks vai para a Caixa (secção inglesa).
- RL em PORTUGUÊS só pode ser usada em Premodern. O que não estiver num deck
  Premodern vai para a Caixa (secção portuguesa, SEPARADA das inglesas).
- A Caixa ordena-se por: idioma (EN separado de PT) e depois por preço unitário
  (cada carta), do mais caro para o mais barato.

Por agora (escolha do André) TODAS as PT vão para a caixa; à medida que montarmos
os decks Premodern, as cartas saem da caixa para o deck.

NB: é uma VISTA calculada a partir da regra — não move cartas. Quando o André
confirmar, cria-se o sub_collection "Caixa Reserved List" e movem-se as cópias.
"""
from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# O balde da Caixa (é para onde as cópias foram movidas).
CAIXA = "Caixa Reserved List"
# Baldes dos decks onde a RL inglesa PODE ser usada (cEDH + Duel-Commander).
CEDH_DC = {"Blue Farm", "Cloud cEDH", "Cloud"}

# As 10 duais ABUR ficam num grupo à parte do resto da RL, mas na mesma caixa
# (pedido do André, 2026-08-31).
DUALS = {"Tundra", "Underground Sea", "Badlands", "Taiga", "Savannah",
         "Scrubland", "Volcanic Island", "Bayou", "Plateau", "Tropical Island"}

NAV = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
       '<a href="meusdecks.html">🎴 Decks vigiados</a>'
       '<a href="metagame.html">🌐 Metagame</a>'
       '<a href="decksfaziveis.html">🛠️ Decks fazíveis</a>'
       '<a href="colecao_cor.html">📚 Binders</a>'
       '<a href="reservedlist.html">🏆 Reserved List</a>'
       '<a class="cur" href="caixarl.html">📦 Caixa RL</a></nav>')

_CSS = """
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e2795b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1000px;margin:0 auto;padding:22px 14px 60px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:100px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .banner{background:#2a1f0b;border:1px solid #4a3714;color:var(--gold);border-radius:10px;padding:10px 14px;font-size:13px;margin:10px 0 18px}
 h2{font-size:15px;margin:24px 0 4px;display:flex;align-items:baseline;gap:10px}
 h2 .n{color:var(--muted);font-size:12px;font-weight:500}
 h2 .val{margin-left:auto;color:var(--gold);font-size:13px;font-weight:700}
 .sub{color:var(--muted);font-size:12px;margin:0 0 8px}
 table{width:100%;border-collapse:collapse;font-size:13px}
 th{text-align:left;color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;padding:4px 8px;border-bottom:1px solid var(--line)}
 td{padding:5px 8px;border-bottom:1px solid #1b212c;vertical-align:middle}
 tr:hover td{background:#141a24}
 .th{width:34px} .th img{width:30px;height:42px;border-radius:3px;display:block;background:#0c0f14;object-fit:cover;object-position:top}
 .q{text-align:center;font-weight:700;width:34px}
 .q.hi{color:var(--warn)}
 .nm{font-weight:600} .st{color:var(--muted);font-size:11px}
 .u{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
 .t{text-align:right;white-space:nowrap;color:var(--muted);font-variant-numeric:tabular-nums}
 .flag{color:var(--warn);font-size:11px;margin-left:5px}
 footer{margin-top:28px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
 .ref{opacity:.72}
"""

_TMPL = ("""<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caixa Reserved List</title><style>""" + _CSS + """</style></head><body><div class="wrap">
<header><h1>📦 Caixa Reserved List</h1>
<div class="lead">RL guardada fora da coleção jogável. Inglesas → só cEDH/Duel-Commander; Portuguesas → só Premodern. O que não está em uso fica aqui, separado por idioma e ordenado por preço unitário. · dados %TODAY%</div>
%NAV%</header>
%BANNER%
%SECS%
<footer>Regra do André (2026-08-31). Preços: Cardmarket (mínimo à venda) por impressão — as antigas mostram <code>low==trend</code> (dados de mercado limitados). ⚠️ = quantidade alta, confirma na revisão.</footer>
</div></body></html>""")


def _price_maps(con):
    nf, fo = {}, {}
    for r in con.execute(
            "SELECT scryfall_id sid, finish, MIN(COALESCE(low,trend)) m FROM price_latest "
            "WHERE COALESCE(low,trend) IS NOT NULL GROUP BY scryfall_id, finish"):
        (fo if r["finish"] == "foil" else nf)[r["sid"]] = r["m"]
    return nf, fo


def _rows(con):
    """Cópias de RL do André, agregadas por (carta, idioma, finish). Guarda em
    SEPARADO as cópias que estão num deck de cEDH/DC (`used_q`) das que estão fora
    (`box_q`) — uma carta pode ter parte no deck e parte na coleção, e só o que
    está fora do deck vai à caixa. Idioma: en vs pt."""
    nf, fo = _price_maps(con)
    agg = {}
    for r in con.execute(
            """SELECT c.name nm, c.set_name st, c.image_uri img, cp.scryfall_id sid,
                      cp.finish fin, cp.language lang, COALESCE(s.name,'(sem balde)') balde,
                      SUM(cp.quantity) q
                 FROM copies cp JOIN catalog.cards c ON c.scryfall_id = cp.scryfall_id
                 LEFT JOIN sub_collections s ON s.id = cp.sub_collection_id
                WHERE cp.purpose = 'player' AND c.reserved = 1
                GROUP BY c.name, cp.language, cp.finish, s.name"""):
        lang = "en" if (r["lang"] or "en") == "en" else "pt"
        unit = (fo if r["fin"] == "foil" else nf).get(r["sid"], 0) or 0
        key = (r["nm"], lang, r["fin"])
        e = agg.setdefault(key, {"nm": r["nm"], "st": r["st"], "img": r["img"],
                                 "fin": r["fin"], "lang": lang, "unit": unit,
                                 "box_q": 0, "used_q": 0})
        if r["balde"] == CAIXA:
            e["box_q"] += r["q"]      # o que está mesmo na Caixa
        elif r["balde"] in CEDH_DC:
            e["used_q"] += r["q"]     # em uso nos decks eternos (referência)
        # RL noutros baldes (ex.: num deck Premodern) não é caixa nem cEDH/DC: ignora
    return list(agg.values())


def _as(items, qfield):
    """Entradas com quantidade > 0 no campo dado, expostas como 'q' para o _table."""
    return [{**e, "q": e[qfield]} for e in items if e[qfield] > 0]


def _table(items):
    body = ""
    for e in sorted(items, key=lambda x: (-x["unit"], x["nm"])):
        img = (f'<img src="{html.escape(e["img"])}" loading="lazy" alt="">'
               if e["img"] else "")
        foil = ' <span class="st">(foil)</span>' if e["fin"] == "foil" else ""
        qcls = "q hi" if e["q"] >= 5 else "q"
        flag = '<span class="flag">⚠️</span>' if e["q"] >= 5 else ""
        up = f'{e["unit"]:.2f}€' if e["unit"] else '<span class="st">s/preço</span>'
        tot = f'{e["q"]*e["unit"]:.0f}€' if e["unit"] else '—'
        body += (f'<tr><td class="th">{img}</td>'
                 f'<td class="{qcls}">{e["q"]}{flag}</td>'
                 f'<td class="nm">{html.escape(e["nm"])}{foil}<div class="st">{html.escape(e["st"])}</div></td>'
                 f'<td class="u">{up}</td><td class="t">{tot}</td></tr>')
    return ('<table><thead><tr><th class="th"></th><th class="q">Qt</th><th>Carta</th>'
            '<th class="u">Preço/un</th><th class="t">Total</th></tr></thead>'
            f'<tbody>{body}</tbody></table>')


def _val(items): return sum(e["q"] * e["unit"] for e in items)
def _qt(items): return sum(e["q"] for e in items)


def _section(title, sub, items, ref=False):
    if not items:
        return ""
    cls = ' class="ref"' if ref else ""
    inner = f'<div class="ref">{_table(items)}</div>' if ref else _table(items)
    return (f'<h2{cls}>{title} <span class="n">{len(items)} cartas · {_qt(items)} cópias</span>'
            f'<span class="val">~{_val(items):.0f}€</span></h2>'
            f'<p class="sub">{sub}</p>{inner}')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "caixarl.html")
    rows = _rows(con)

    def box_split(lang):
        box = _as([e for e in rows if e["lang"] == lang], "box_q")
        return ([e for e in box if e["nm"] in DUALS],
                [e for e in box if e["nm"] not in DUALS])

    en_duals, en_rest = box_split("en")
    pt_duals, pt_rest = box_split("pt")
    en_used = _as([e for e in rows if e["lang"] == "en"], "used_q")

    secs = ""
    secs += _section("🇬🇧 Inglesas · Duais", "As 10 duais ABUR, à parte do resto.", en_duals)
    secs += _section("🇬🇧 Inglesas · Resto da RL", "RL inglesas (não-duais) fora dos decks de cEDH/Duel-Commander.", en_rest)
    secs += _section("🇵🇹 Portuguesas · Duais", "Duais em português, à parte do resto.", pt_duals)
    secs += _section("🇵🇹 Portuguesas · Resto da RL", "Todas as RL portuguesas não-duais, por agora — saem da caixa à medida que montarmos cada deck Premodern.", pt_rest)
    secs += _section("✅ Inglesas em uso (cEDH/Duel-Commander)", "Ficam nos decks — não vão para a caixa (só referência).", en_used, ref=True)

    box = en_duals + en_rest + pt_duals + pt_rest
    banner = (f'<div class="banner">📦 <b>{len(box)} cartas · {_qt(box)} cópias · ~{_val(box):.0f}€</b> na Caixa. '
              f'Fora da coleção jogável (não contam para Metagame/Decks fazíveis). '
              f'As portuguesas voltam à coleção à medida que montarmos cada deck Premodern.</div>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%NAV%", NAV).replace("%BANNER%", banner)
                   .replace("%SECS%", secs).replace("%TODAY%", today), encoding="utf-8")
    return out


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print("caixarl.html:", build(con))
