"""Gera buildability.html — "O que consigo montar" + loadout interativo.

Para cada deck-alvo do André (tabela `decks`), mostra a % que já tem da lista e
as cartas que faltam (imagem da edição a comprar + preço). Ordenado por quão
perto está de estar montado.

LOADOUT (ideia do André, 2026-08-14): cada deck tem um checkmark "montado". Ao
marcar, as cartas ficam reservadas a esse deck (no cliente). Para cada deck NÃO
montado, calcula o que terias de **mover** dos montados (cartas comuns) e o que
ainda terias de **comprar** para o montar. Assim mantém vários decks montados e
só passa as cartas comuns. Tudo client-side (localStorage) — fica na cloud, sem
servidor; é um planeador (o físico é ele). Se não gostar, é só não usar.

Cruza a lista (`deck_cards`) com a coleção (`owned_playable`, que normaliza os
nomes de dupla-face). NÃO inventa nada. Corre no job diário.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402  (reutiliza _visual: imagem+preço da edição)
from mtgvault.collection import owned_playable  # noqa: E402

BASICS = mc.BASICS
FMT_LABEL = {"standard": "Standard", "pioneer": "Pioneer", "modern": "Modern",
             "legacy": "Legacy", "premodern": "Premodern",
             "duel-commander": "Duel Commander", "cedh": "cEDH", "pauper": "Pauper"}
FMT_ORDER = ["standard", "pioneer", "modern", "legacy", "premodern",
             "duel-commander", "cedh", "pauper"]


def deck_status(con, deck_id, owned):
    """Lista completa (main, sem básicas) e o que falta face à coleção."""
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
                            "img": v["img"], "set_name": v["set_name"], "mine": v["mine"]})
    pct = round(100 * have / need) if need else 0
    cost = round(sum((m["unit"] or 0) * m["need"] for m in missing), 2)
    missing.sort(key=lambda m: -((m["unit"] or 0) * m["need"]))
    return {"full": full, "need": need, "have": have, "pct": pct, "missing": missing, "cost": cost}


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "buildability.html")
    owned = owned_playable(con)
    by_fmt = defaultdict(list)
    deck_full = {}          # nome -> [[carta, qty], ...]  (para o loadout no cliente)
    relevant = set()
    for d in con.execute("SELECT id, name, format FROM decks"):
        st = deck_status(con, d["id"], owned)
        if st["need"] == 0:
            continue
        deck_full[d["name"]] = st["full"]
        relevant.update(c for c, _ in st["full"])
        by_fmt[d["format"]].append({"name": d["name"], **st})
    owned_sub = {c: owned.get(c, 0) for c in relevant}

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
                         f'<span class="q">{m["need"]}x</span><span class="pz">{price}</span>'
                         f'{"<span class=ed>✓ed</span>" if m["mine"] else ""}</div>')
            nm = html.escape(d["name"])
            secs += (
                f'<div class="deck" data-deck="{nm}"><div class="dh">'
                f'<label class="mont-l"><input type="checkbox" class="mont"> montado</label>'
                f'<b>{nm}</b><span class="hv">{d["have"]}/{d["need"]}</span></div>'
                f'<div class="bar"><span style="width:{d["pct"]}%;background:{col}"></span>'
                f'<em>{d["pct"]}%</em></div>'
                f'<div class="mt">{miss_txt}</div><div class="loadout"></div>'
                + (f'<div class="grid">{grid}</div>' if grid else "")
                + "</div>")

    total = sum(len(v) for v in by_fmt.values())
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(
        _TMPL.replace("%SECS%", secs).replace("%N%", str(total)).replace("%TODAY%", today)
             .replace("%DECKS%", json.dumps(deck_full, ensure_ascii=False))
             .replace("%OWNED%", json.dumps(owned_sub, ensure_ascii=False)),
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
 h2{font-size:15px;margin:22px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);padding-bottom:4px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px}
 .deck.on{border-color:var(--add);box-shadow:inset 0 0 0 1px var(--add)}
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
<div class="sub">%N% decks-alvo · dados de %TODAY% · <a href="index.html">← início</a> · <a href="cobertura.html">metagame</a> · <a href="colecao_cor.html">coleção</a></div>
<div class="tip">✅ Marca "montado" nos decks que tens montados. Para cada outro deck, digo-te o que <b style="color:var(--gold)">🔀 mover</b> desses montados (cartas comuns) e o que <b style="color:var(--warn)">🛒 comprar</b>. Fica guardado só neste dispositivo.</div></header>
%SECS%
<footer>Cada deck-alvo com a % que já tens e as cartas em falta (imagem da edição a comprar, ✓ed = edição que já tens, preço). O loadout é um planeador: os checkmarks e o cálculo do que mover ficam no teu navegador. Terras básicas não contam. Atualiza sozinho todos os dias.</footer>
</div>
<script>
const DECKS=%DECKS%, OWNED=%OWNED%, KEY='mtg_montado_v1';
let _mem=null;  // fallback em memória se o localStorage estiver indisponível
function getM(){if(_mem)return new Set(_mem);try{return new Set(JSON.parse(localStorage.getItem(KEY)||'[]'));}catch(e){return new Set();}}
function setM(s){_mem=[...s];try{localStorage.setItem(KEY,JSON.stringify([...s]));}catch(e){}}
function srcDeck(c,M){for(const dn of M){if((DECKS[dn]||[]).some(x=>x[0]===c))return dn;}return null;}
function recompute(){
  const M=getM(), reserved={};
  M.forEach(dn=>(DECKS[dn]||[]).forEach(p=>{reserved[p[0]]=(reserved[p[0]]||0)+p[1];}));
  document.querySelectorAll('.deck').forEach(el=>{
    const dn=el.dataset.deck, cb=el.querySelector('.mont');
    if(cb)cb.checked=M.has(dn);
    el.classList.toggle('on',M.has(dn));
    const out=el.querySelector('.loadout'); if(!out)return;
    if(M.has(dn)){out.innerHTML='<span class="ok">✅ montado · cartas reservadas a este deck</span>';return;}
    const moves=[],buys=[];
    (DECKS[dn]||[]).forEach(p=>{
      const c=p[0],q=p[1],own=OWNED[c]||0,used=Math.min(reserved[c]||0,own),free=own-used;
      let short=q-Math.min(q,free);
      if(short>0){const canMove=Math.min(short,used);
        if(canMove>0){const s=srcDeck(c,M);moves.push(canMove+'x '+c+(s?' ('+s+')':''));}
        const buy=short-canMove; if(buy>0)buys.push(buy+'x '+c);}
    });
    let h='';
    if(moves.length)h+='<div class="mv"><b>🔀 mover:</b> '+moves.join(' · ')+'</div>';
    if(buys.length)h+='<div class="by"><b>🛒 comprar:</b> '+buys.join(' · ')+'</div>';
    if(!h)h='<span class="ok">✅ dá para montar já, sem mexer nos outros</span>';
    out.innerHTML=h;
  });
}
document.addEventListener('change',e=>{
  if(e.target.classList.contains('mont')){
    const dn=e.target.closest('.deck').dataset.deck, M=getM();
    e.target.checked?M.add(dn):M.delete(dn); setM(M); recompute();
  }
});
recompute();
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("buildability.html:", build(con))


if __name__ == "__main__":
    main()
