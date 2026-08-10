"""Gera colecao.html — a galeria da coleção física, com imagens.

Lê `copies` + o catálogo (`cards`: imagem, edição, número) + os preços
(`price_latest`), e embute tudo num HTML estático, tal como o coredecks.html.
O catálogo é reconstruído no job diário, por isso as imagens e as impressões
exatas entram na página sem ser preciso carregar o catálogo (119 MB) no browser.

Corre à mão com `python collection_gallery.py`, ou é chamado pelo daily.py.
Dados só de vault.db + catálogo — nunca inventa.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db  # noqa: E402


def _price_map(con):
    """(scryfall_id, finish) -> preço Cardmarket mais recente. Opcional: se não
    houver catálogo/preços, fica vazio e a galeria mostra as cartas sem valor."""
    price = {}
    try:
        for r in con.execute(
            "SELECT scryfall_id, finish, trend FROM price_latest WHERE source='cardmarket'"
        ):
            if r["trend"] is not None:
                price[(r["scryfall_id"], r["finish"])] = r["trend"]
    except Exception:  # noqa: BLE001
        pass
    return price


def _cards(con):
    """Uma linha por lote em copies, com nome/edição/imagem do catálogo e preço.

    Junta ao catálogo (ATTACH) para a imagem e a edição exata. Se o catálogo não
    estiver presente, a carta entra na mesma (sem imagem/edição), para nunca
    desaparecer da galeria.
    """
    price = _price_map(con)
    # A junção ao catálogo é LEFT para tolerar catálogo em falta.
    rows = []
    for r in con.execute(
        """SELECT cp.scryfall_id AS sid, cp.quantity AS qty, cp.finish AS finish,
                  cp.purpose AS purpose, COALESCE(sc.name, '—') AS sub,
                  c.name AS name, c.set_code AS set_code,
                  c.collector_number AS cn, c.image_uri AS img
             FROM copies cp
             LEFT JOIN cards c ON c.scryfall_id = cp.scryfall_id
             LEFT JOIN sub_collections sc ON sc.id = cp.sub_collection_id"""
    ):
        p = price.get((r["sid"], r["finish"]))
        rows.append({
            "name": r["name"] or "(desconhecida)",
            "set": (r["set_code"] or "").upper(),
            "cn": r["cn"] or "",
            "img": r["img"] or "",
            "qty": r["qty"],
            "foil": r["finish"] == "foil",
            "collector": r["purpose"] == "collector",
            "sub": r["sub"],
            "eur": round(p, 2) if p is not None else None,
        })
    return rows


# ---------------------------------------------------------------------------
# Histórico do valor da coleção (um ponto por dia, gravado pelo job diário)
# ---------------------------------------------------------------------------
def _ensure_value(con):
    con.execute("CREATE TABLE IF NOT EXISTS value_history ("
                "date TEXT PRIMARY KEY, total_eur REAL NOT NULL, cards INTEGER)")
    con.commit()


def _record_value(con, total_eur, cards, day):
    con.execute("INSERT OR REPLACE INTO value_history (date, total_eur, cards) VALUES (?,?,?)",
                (day, total_eur, cards))
    con.commit()


def _value_history(con):
    return [(r["date"], r["total_eur"]) for r in
            con.execute("SELECT date, total_eur FROM value_history ORDER BY date")]


def _evo_block(history):
    """Bloco HTML: indicador de valorização + gráfico SVG (desenhado no servidor)."""
    if len(history) < 2:
        return ('<div class="evo"><div class="evo-top"><span class="evo-h">Evolução do valor</span></div>'
                '<div class="evo-note">O histórico começa agora — o gráfico preenche-se a cada dia '
                'que o job diário grava o valor.</div></div>')
    dates = [d for d, _ in history]
    vals = [v for _, v in history]
    first, last = vals[0], vals[-1]
    pct = (last - first) / first * 100 if first else 0.0
    cls = "up" if last >= first else "down"
    arrow = "▲" if last >= first else "▼"
    W, H, pad = 640, 96, 8
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)

    def px(i):
        return pad + (i * (W - 2 * pad) / (n - 1) if n > 1 else 0)

    def py(v):
        return H - pad - (v - lo) / span * (H - 2 * pad)

    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
    area = f"{px(0):.1f},{H - pad} " + pts + f" {px(n - 1):.1f},{H - pad}"
    dots = "".join(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="2.6" class="dot {cls}"/>'
                   for i, v in enumerate(vals))
    svg = (f'<svg viewBox="0 0 {W} {H}" class="spark">'
           f'<polygon points="{area}" class="fill {cls}"/>'
           f'<polyline points="{pts}" class="line {cls}"/>{dots}</svg>')
    return (f'<div class="evo"><div class="evo-top"><span class="evo-h">Evolução do valor</span>'
            f'<span class="evo-ind {cls}">{arrow} {pct:+.1f}% <em>desde {dates[0]}</em></span></div>'
            f'<div class="evo-axis"><span>{dates[0]}</span><span>{dates[-1]}</span></div>{svg}</div>')


def build(con, out_path):
    rows = _cards(con)
    # Agrupa por sub-coleção; ordena os grupos por valor descendente.
    groups: dict[str, list] = {}
    for c in rows:
        groups.setdefault(c["sub"], []).append(c)

    def gval(cards):
        return round(sum((c["eur"] or 0) * c["qty"] for c in cards), 2)

    ordered = []
    for sub in sorted(groups, key=lambda s: -gval(groups[s])):
        cards = sorted(groups[sub], key=lambda c: (-(c["eur"] or 0), c["name"]))
        ordered.append({"sub": sub, "value": gval(cards),
                        "qty": sum(c["qty"] for c in cards), "cards": cards})

    total_qty = sum(c["qty"] for c in rows)
    total_val = round(sum((c["eur"] or 0) * c["qty"] for c in rows), 2)
    today = _dt.date.today().isoformat()
    _ensure_value(con)
    _record_value(con, total_val, total_qty, today)
    history = _value_history(con)
    _write_html(out_path, ordered, total_qty, total_val, today, history)
    return f"{total_qty} exemplares em {len(ordered)} coleções ({out_path.name})"


_TMPL = """<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A minha coleção</title>
<style>
 :root{--bg:#f6f7f9;--card:#fff;--ink:#12151a;--muted:#5b6672;--line:#e4e7ec;--accent:#2f6df6;--gold:#b8860b}
 @media(prefers-color-scheme:dark){:root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b}}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:20px 16px 60px}
 @media(max-width:600px){.wrap{padding:14px 10px 48px}}
 h1{margin:0 0 2px;font-size:21px} .sub{color:var(--muted);font-size:13px} .sub a{color:var(--accent)}
 .tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0 4px}
 #q{flex:1;min-width:180px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:14px}
 .count{color:var(--muted);font-size:12.5px;white-space:nowrap}
 .tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 2px}
 .tab{border:1px solid var(--line);background:var(--card);color:var(--muted);border-radius:999px;padding:6px 13px;font-size:13px;font-weight:600;cursor:pointer}
 .tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
 .tab b{opacity:.65}
 .tab .tv{color:var(--gold);font-weight:600}
 .tab.active .tv{color:#fff}
 .evo{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:14px 0 2px}
 .evo-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
 .evo-h{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
 .evo-ind{font-weight:700;font-size:15px} .evo-ind em{font-style:normal;font-weight:400;color:var(--muted);font-size:12px}
 .evo-ind.up{color:var(--add)} .evo-ind.down{color:var(--rem)}
 .evo-axis{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin:6px 0 0}
 .spark{width:100%;height:auto;display:block}
 .spark .line{fill:none;stroke-width:2;vector-effect:non-scaling-stroke} .spark .line.up{stroke:var(--add)} .spark .line.down{stroke:var(--rem)}
 .spark .fill.up{fill:var(--add);opacity:.13} .spark .fill.down{fill:var(--rem);opacity:.13}
 .spark .dot{stroke:var(--card);stroke-width:1} .spark .dot.up{fill:var(--add)} .spark .dot.down{fill:var(--rem)}
 .evo-note{color:var(--muted);font-size:12.5px;margin-top:6px}
 h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:26px 0 6px;border-bottom:1px solid var(--line);padding-bottom:6px;display:flex;justify-content:space-between;gap:10px;align-items:baseline}
 h2 b{color:var(--ink)} h2 .gv{color:var(--gold);font-variant-numeric:tabular-nums;font-size:13px;text-transform:none;letter-spacing:0}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
 .c{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;position:relative}
 .c .imgwrap{position:relative;aspect-ratio:488/680;background:var(--line)}
 .c img{width:100%;height:100%;object-fit:cover;display:block}
 .c .noimg{width:100%;height:100%;display:flex;align-items:center;justify-content:center;text-align:center;padding:8px;font-size:12px;color:var(--muted)}
 .c .qty{position:absolute;top:6px;right:6px;background:rgba(0,0,0,.78);color:#fff;font-weight:700;font-size:12px;padding:1px 7px;border-radius:999px}
 .c .foil{position:absolute;top:6px;left:6px;font-size:12px;background:linear-gradient(135deg,#8ae,#e8a,#8ea);color:#111;font-weight:700;padding:1px 6px;border-radius:999px}
 .c .meta{padding:7px 9px} .c .nm{font-weight:600;font-size:12.5px;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .c .ed{color:var(--muted);font-size:11px;margin-top:1px} .c .pr{color:var(--gold);font-size:12px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}
 .c .col{color:var(--muted);font-size:10.5px}
 footer{margin-top:34px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
 .empty{color:var(--muted);padding:30px 0;text-align:center}
</style></head><body><div class="wrap">
<header><h1>A minha coleção</h1>
<div class="sub">%TOTQ% exemplares · valor ~<b style="color:var(--gold)">%TOTV%</b> · imagens e preços via Scryfall/Cardmarket · dados até %TODAY% ·
<a href="index.html">← resumo</a> · <a href="coredecks.html">core decks →</a></div></header>
%EVO%
<div class="tools"><input id="q" type="search" placeholder="Procurar carta ou edição…" autocomplete="off"><span class="count" id="count"></span></div>
<div id="tabs" class="tabs"></div>
<div id="app"></div>
<footer>Cada imagem é a impressão exata da carta (edição + número). Clica para abrir em grande. A galeria regenera-se sozinha no job diário.</footer>
</div>
<script>
const DATA=%DATA%;
const esc=s=>(s==null?"":String(s)).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const eur=x=>x==null?"":(x||0).toLocaleString("pt-PT",{style:"currency",currency:"EUR"});
function cardHtml(c){
 const img=c.img?('<a href="'+esc(c.img)+'" target="_blank" rel="noopener"><img loading="lazy" src="'+esc(c.img)+'" alt="'+esc(c.name)+'"></a>')
                 :('<div class="noimg">'+esc(c.name)+'</div>');
 return '<div class="c" data-s="'+esc((c.name+' '+c.set).toLowerCase())+'"><div class="imgwrap">'+img+
  '<span class="qty">'+c.qty+'x</span>'+(c.foil?'<span class="foil">foil</span>':'')+'</div>'+
  '<div class="meta"><div class="nm" title="'+esc(c.name)+'">'+esc(c.name)+'</div>'+
  '<div class="ed">'+esc(c.set)+(c.cn?' · '+esc(c.cn):'')+(c.collector?' <span class="col">· colec.</span>':'')+'</div>'+
  (c.eur!=null?'<div class="pr">'+eur(c.eur)+'</div>':'')+'</div></div>';
}
let ACTIVE="*";
function buildTabs(){
 const t=document.getElementById("tabs"), total=DATA.reduce((s,g)=>s+g.qty,0), totv=DATA.reduce((s,g)=>s+g.value,0);
 let h='<button class="tab" data-sub="*">Todas <b>('+total+')</b> <span class="tv">'+eur(totv)+'</span></button>';
 for(const g of DATA) h+='<button class="tab" data-sub="'+esc(g.sub)+'">'+esc(g.sub)+' <b>('+g.qty+')</b> <span class="tv">'+eur(g.value)+'</span></button>';
 t.innerHTML=h;
 t.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{ACTIVE=b.dataset.sub;render(document.getElementById("q").value);}));
}
function render(filter){
 const f=(filter||"").trim().toLowerCase(); const app=document.getElementById("app"); let html="", shown=0;
 document.querySelectorAll("#tabs .tab").forEach(b=>b.classList.toggle("active",b.dataset.sub===ACTIVE));
 for(const g of DATA){
  if(ACTIVE!=="*" && g.sub!==ACTIVE) continue;
  const cards=f?g.cards.filter(c=>(c.name+' '+c.set).toLowerCase().includes(f)):g.cards;
  if(!cards.length) continue; shown+=cards.reduce((s,c)=>s+c.qty,0);
  html+='<h2><span>'+esc(g.sub)+' <b>('+g.qty+')</b></span><span class="gv">'+eur(g.value)+'</span></h2>'+
        '<div class="grid">'+cards.map(cardHtml).join("")+'</div>';
 }
 app.innerHTML=html||'<div class="empty">Nada encontrado.</div>';
 document.getElementById("count").textContent=f?(shown+" a mostrar"):"";
}
document.getElementById("q").addEventListener("input",e=>render(e.target.value));
buildTabs();
render("");
</script></body></html>
"""


def _write_html(out_path, groups, total_qty, total_val, today, history):
    eur = f"{total_val:,.2f} €".replace(",", " ")
    html = (_TMPL
            .replace("%DATA%", json.dumps(groups, ensure_ascii=False))
            .replace("%TOTQ%", str(total_qty))
            .replace("%TOTV%", eur)
            .replace("%TODAY%", today)
            .replace("%EVO%", _evo_block(history)))
    Path(out_path).write_text(html, encoding="utf-8")


def main():
    with db.session() as con:
        print(build(con, ROOT / "colecao.html"))


if __name__ == "__main__":
    main()
