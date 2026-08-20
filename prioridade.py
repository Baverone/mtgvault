"""Gera prioridade.html — prioridade e alocação exclusiva dos decks.

O André não quer partilhar cartas entre decks: cada carta vai para o deck de
MAIOR prioridade que precisa dela. Aqui ele ARRASTA os decks para reordenar a
prioridade (fica no navegador), e vê em tempo real a % de cada deck com as
cartas que lhe SOBRAM depois de os de cima ficarem servidos — e o que perde
para os de cima. Assim, decks que competem pelo mesmo core caro (ex.: os 3 de
Mox Opal) mostram só o de topo completo, sem precisar de "blocos".

Dois pools independentes (não partilham cartas entre si): Premodern e SPML.
Tudo client-side. NÃO inventa nada.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import classify  # noqa: E402
from mtgvault import db as _db  # noqa: E402  (só p/ o main)

BASICS = classify.BASICS


def _owned(con, balde):
    out = defaultdict(int)
    for r in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                              JOIN sub_collections s ON s.id = cp.sub_collection_id
                             WHERE cp.purpose = 'player' AND s.name = ? GROUP BY c.name""", (balde,)):
        out[r["nm"].split(" // ")[0]] += r["q"]
    return out


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "prioridade.html")
    pools = {}

    # Premodern: consenso de cada deck + ordem por prioridade do deck_meta
    pm = classify.premodern_status(con)
    pm_decks = {d: st["cons"] for d, st in pm.items() if st["cons"]}
    pm_order = [r["sub_collection"] for r in con.execute(
        "SELECT sub_collection FROM deck_meta WHERE pool='Premodern' AND priority IS NOT NULL "
        "ORDER BY priority") if r["sub_collection"] in pm_decks]
    pm_order += [d for d in pm_decks if d not in pm_order]
    # Premodern partilha as cartas ATÉ um deck completar; aí tranca-as nesse deck.
    # A prioridade decide quem completa/tranca primeiro → alocação exclusiva.
    pools["Premodern"] = {"decks": pm_decks, "owned": _owned(con, "Premodern (geral)"),
                          "order": pm_order, "shared": False}

    # SPML: decks-alvo (std/pio/mod/leg) da tabela decks
    spml_decks = {}
    for d in con.execute("SELECT id, name FROM decks WHERE format IN ('standard','pioneer','modern','legacy')"):
        cards = {}
        for r in con.execute("SELECT card_name nm, SUM(quantity) q FROM deck_cards "
                             "WHERE deck_id=? AND board IN ('main','') GROUP BY card_name", (d["id"],)):
            if r["nm"] not in BASICS:
                cards[r["nm"]] = r["q"]
        if cards:
            spml_decks[d["name"]] = cards
    # SPML partilha SEMPRE a coleção: cada deck mede-se contra o pool inteiro,
    # sem alocação exclusiva (uma carta pode servir qualquer deck SPML).
    pools["SPML"] = {"decks": spml_decks, "owned": _owned(con, "SPML"),
                     "order": sorted(spml_decks), "shared": True}

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%POOLS%", json.dumps(pools, ensure_ascii=False))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prioridade e alocação</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:760px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800} .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px} .tabs a:hover{border-color:var(--accent)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 h2{font-size:14px;margin:22px 0 4px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
 .hint{color:#5a6472;font-size:12px;margin:0 0 8px}
 .prow{display:grid;grid-template-columns:auto 1fr auto;grid-template-areas:"g n p" "g b b" "g m m";gap:2px 8px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:7px;cursor:grab}
 .prow.drag{opacity:.4} .prow.over{border-color:var(--accent)} .prow.shared{cursor:default}
 .grip{grid-area:g;color:#4a5666;font-size:20px;cursor:grab;user-select:none} .pn{grid-area:n;font-weight:600} .pp{grid-area:p;font-weight:800;font-size:16px}
 .pbar{grid-area:b;height:7px;background:#0b0e14;border-radius:999px;overflow:hidden;margin-top:2px} .pbar span{display:block;height:100%;border-radius:999px}
 .pmiss{grid-area:m;color:var(--warn);font-size:11px;margin-top:2px} .pok{grid-area:m;color:var(--add);font-size:11px;margin-top:2px}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>⚖️ Prioridade e alocação</h1>
<div class="lead">No Premodern arrastas para definir quem completa (e tranca) primeiro; o SPML partilha sempre · dados de %TODAY%</div>
<nav class="tabs"><a href="index.html">🏠 Início</a><a href="meusdecks.html">🎴 Decks vigiados</a><a href="metagame.html">🌐 Metagame</a><a href="colecao_cor.html">📚 Binders</a><a href="reservedlist.html">🏆 Reserved List</a></nav></header>
<section><h2>🕰️ Premodern <span style="text-transform:none;letter-spacing:0;color:#5a6472;font-weight:400">— partilha até completar, depois tranca</span></h2><div class="hint">As cartas partilham-se até um deck ficar completo; aí trancam-se nesse deck. A prioridade decide quem completa primeiro: cada carta contestada vai para o deck de cima. Arrasta ⠿ para reordenar.</div><div id="pool-Premodern"></div></section>
<section><h2>🔷 SPML <span style="text-transform:none;letter-spacing:0;color:#5a6472;font-weight:400">— partilha sempre</span></h2><div class="hint">As cartas partilham-se sempre: cada deck mede-se contra a coleção SPML inteira. A mesma carta pode servir vários decks — não os montas todos ao mesmo tempo com as mesmas cópias, mas isso é o <i>loadout</i> (logo se vê).</div><div id="pool-SPML"></div></section>
<footer>Premodern: a % de cada deck é com as cartas que lhe SOBRAM depois de os de cima ficarem servidos (alocação exclusiva por prioridade — "perde p/ prioridade" = cartas que foram para um deck de cima). A ordem fica guardada no teu navegador. SPML: partilha sempre, por isso cada deck mostra a % contra a coleção inteira e o que lhe falta.</footer>
</div>
<script>
const POOLS=%POOLS%;
function ordKey(p){return 'prio_'+p;}
function getOrder(p){try{const v=localStorage.getItem(ordKey(p));if(v)return JSON.parse(v).filter(d=>d in POOLS[p].decks);}catch(e){}return POOLS[p].order.slice();}
function setOrder(p,o){try{localStorage.setItem(ordKey(p),JSON.stringify(o));}catch(e){}}
function allocate(p,order){
  // Exclusiva (Premodern): esgota o pool pela ordem de prioridade.
  const decks=POOLS[p].decks, pool=Object.assign({},POOLS[p].owned), res={};
  order.forEach(dn=>{const need=decks[dn]||{};let have=0,tot=0;const miss=[];
    for(const c in need){const q=need[c];tot+=q;const take=Math.min(q,pool[c]||0);pool[c]=(pool[c]||0)-take;have+=take;if(take<q)miss.push((q-take)+'x '+c);}
    res[dn]={have:have,tot:tot,pct:tot?Math.round(100*have/tot):0,miss:miss};});
  return res;
}
function shared(p){
  // Partilhada (SPML): cada deck mede-se contra a coleção INTEIRA, sem esgotar.
  const decks=POOLS[p].decks, pool=POOLS[p].owned, res={};
  for(const dn in decks){const need=decks[dn];let have=0,tot=0;const miss=[];
    for(const c in need){const q=need[c];tot+=q;const got=Math.min(q,pool[c]||0);have+=got;if(got<q)miss.push((q-got)+'x '+c);}
    res[dn]={have:have,tot:tot,pct:tot?Math.round(100*have/tot):0,miss:miss};}
  return res;
}
function render(p){
  const box=document.getElementById('pool-'+p),isShared=POOLS[p].shared;let h='';
  if(isShared){
    const res=shared(p);
    const order=Object.keys(POOLS[p].decks).sort((a,b)=>res[b].pct-res[a].pct||a.localeCompare(b));
    order.forEach(dn=>{const r=res[dn];const col=r.pct>=90?'var(--add)':r.pct>=60?'var(--gold)':'var(--warn)';
      const esc=dn.replace(/&/g,'&amp;').replace(/</g,'&lt;');
      h+='<div class="prow shared" data-pool="'+p+'">'
        +'<span class="pn">'+esc+' <span style="color:var(--muted);font-weight:400">'+r.have+'/'+r.tot+'</span></span>'
        +'<span class="pp" style="color:'+col+'">'+r.pct+'%</span>'
        +'<div class="pbar"><span style="width:'+r.pct+'%;background:'+col+'"></span></div>'
        +(r.miss.length?'<div class="pmiss" style="color:var(--muted)">falta: '+r.miss.slice(0,10).join(' · ')+(r.miss.length>10?' …':'')+'</div>':'<div class="pok">tens tudo o que precisa ✅</div>')
        +'</div>';});
    box.innerHTML=h;return;
  }
  const order=getOrder(p),res=allocate(p,order);
  order.forEach((dn,i)=>{const r=res[dn]||{pct:0,have:0,tot:0,miss:[]};const col=r.pct>=90?'var(--add)':r.pct>=60?'var(--gold)':'var(--warn)';
    const esc=dn.replace(/&/g,'&amp;').replace(/</g,'&lt;');
    h+='<div class="prow" draggable="true" data-pool="'+p+'" data-i="'+i+'">'
      +'<span class="grip">⠿</span><span class="pn">'+(i+1)+'. '+esc+' <span style="color:var(--muted);font-weight:400">'+r.have+'/'+r.tot+'</span></span>'
      +'<span class="pp" style="color:'+col+'">'+r.pct+'%</span>'
      +'<div class="pbar"><span style="width:'+r.pct+'%;background:'+col+'"></span></div>'
      +(r.miss.length?'<div class="pmiss">perde: '+r.miss.slice(0,10).join(' · ')+(r.miss.length>10?' …':'')+'</div>':'<div class="pok">fica com tudo o que precisa ✅</div>')
      +'</div>';});
  box.innerHTML=h;
}
let dP=null,dI=null;
document.addEventListener('dragstart',e=>{const r=e.target.closest('.prow');if(r){dP=r.dataset.pool;dI=+r.dataset.i;r.classList.add('drag');e.dataTransfer.effectAllowed='move';}});
document.addEventListener('dragend',e=>{const r=e.target.closest('.prow');if(r)r.classList.remove('drag');document.querySelectorAll('.over').forEach(x=>x.classList.remove('over'));});
document.addEventListener('dragover',e=>{const r=e.target.closest('.prow');if(r&&r.dataset.pool===dP){e.preventDefault();document.querySelectorAll('.over').forEach(x=>x.classList.remove('over'));r.classList.add('over');}});
document.addEventListener('drop',e=>{const r=e.target.closest('.prow');if(!r||r.dataset.pool!==dP)return;e.preventDefault();
  const to=+r.dataset.i,order=getOrder(dP);const m=order.splice(dI,1)[0];order.splice(to,0,m);setOrder(dP,order);render(dP);});
['Premodern','SPML'].forEach(render);
</script>
</body></html>"""


def main():
    with _db.session() as con:
        print("prioridade.html:", build(con))


if __name__ == "__main__":
    main()
