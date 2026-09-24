"""Gera colecao.html — a galeria da coleção física, com imagens.

Lê `copies` + o catálogo (`cards`: imagem, edição, número) + os preços
(`price_latest`), e embute tudo num HTML estático. O catálogo é reconstruído no
job diário, por isso as imagens e as impressões exatas entram na página sem ser
preciso carregar o catálogo (119 MB) no browser.

O MENU é o partilhado (`mtgvault.site_shell.barra`). Esta era a última página gerada
que escrevia a sua navegação à mão, e mostrou porquê: ficou com um *"core
decks →"* a apontar para o `coredecks.html`, apagado a 2026-08-26 e desde então
fora do `git add` do `daily.yml` — 404 no site publicado. E, sem o menu, da
Galeria só se saía para o índice. Uma página órfã não dá erro: só deixa de se lá
chegar (é a lição do `cobertura.html`, no cabeçalho do `paginas.py`).

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

from mtgvault import collection as col  # noqa: E402
from mtgvault import db, paginas  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402
from mtgvault.collection import na_estante  # noqa: E402

# O dia em que a Galeria passou a usar a conta única do valor (André,
# 2026-09-24: *"corrige tudo o que achares que é erro"*). Antes exigia o preço do
# acabamento EXACTO da cópia e por isso dava «sem preço» às foil que o Cardmarket
# não cota em foil — 11,67 € de discórdia com os Binders por cor, em três cartas
# (Ethersworn Canonist SLD, Cid FIC, Helitrooper FIC). O gráfico da evolução tem
# pontos dos DOIS lados desta data: os anteriores ficam como foram gravados (não
# se reescreve um histórico que se mediu), e o gráfico diz onde está a costura.
REGRA_NOVA = "2026-09-24"


def _cards(con):
    """Uma linha por lote em copies, com nome/edição/imagem do catálogo e preço.

    Junta ao catálogo (ATTACH) para a imagem e a edição exata. Se o catálogo não
    estiver presente, a carta entra na mesma (sem imagem/edição), para nunca
    desaparecer da galeria.

    O PREÇO sai da `collection.valor_da_coleccao` — a conta única (2026-09-24).
    Esta página tinha o seu `_price_map`, que exigia o acabamento exacto da cópia;
    agora cai para o outro acabamento como em todo o resto do vault, e a linha diz
    (`est`) quando o preço veio de lá.
    """
    precos = {c["copy_id"]: c for c in col.valor_da_coleccao(con)["copias"]}
    # A junção ao catálogo é LEFT para tolerar catálogo em falta.
    rows = []
    # As cópias que ele deu como NÃO ENCONTRADAS saem da galeria (2026-09-09):
    # esta página é o que ele TEM, e uma carta que não está na estante não é.
    # Onde elas se vêem é na aba «Não encontradas» da Deckboxes, com a foto.
    for r in con.execute(
        f"""SELECT cp.id AS id, cp.scryfall_id AS sid, cp.quantity AS qty,
                  cp.finish AS finish,
                  cp.purpose AS purpose, COALESCE(sc.name, '—') AS sub,
                  c.name AS name, c.set_code AS set_code,
                  c.collector_number AS cn, c.image_uri AS img
             FROM copies cp
             LEFT JOIN cards c ON c.scryfall_id = cp.scryfall_id
             LEFT JOIN sub_collections sc ON sc.id = cp.sub_collection_id
            WHERE {na_estante()}"""
    ):
        p = precos.get(r["id"], {})
        linha = {
            "name": r["name"] or "(desconhecida)",
            "set": (r["set_code"] or "").upper(),
            "cn": r["cn"] or "",
            "img": r["img"] or "",
            "qty": r["qty"],
            "foil": r["finish"] == "foil",
            "collector": r["purpose"] == "collector",
            "sub": r["sub"],
            "eur": round(p["unit"], 2) if p.get("unit") is not None else None,
        }
        # O preço veio do OUTRO acabamento: é uma estimativa, e diz-se. A chave só
        # existe quando é verdade — os dados vão EMBUTIDOS nesta página, e um
        # `"est": null` em cada uma das 737 linhas eram 10,7 KB para marcar três.
        if p.get("estimado"):
            linha["est"] = p["price_finish"]
        rows.append(linha)
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


def _costura(dates):
    """O índice do primeiro ponto já medido pela REGRA NOVA, ou `None`.

    O que está gravado antes de `REGRA_NOVA` foi medido com a regra antiga (sem a
    queda para o outro acabamento) e fica como está: reescrever pontos antigos com
    a regra de hoje era inventar um histórico que ninguém mediu. O que se faz é
    DIZER onde está a costura — um degrau de ~11,67 € que não é o mercado a mexer.
    """
    if dates[0] >= REGRA_NOVA:        # tudo já pela regra nova: não há costura
        return None
    for i, d in enumerate(dates):
        if d >= REGRA_NOVA:
            return i
    return None


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
    # A costura da mudança de regra, desenhada: uma linha tracejada no primeiro
    # ponto já medido pela regra nova. Sem ela, o degrau lia-se como mercado.
    ic = _costura(dates)
    marca = (f'<line x1="{px(ic):.1f}" y1="{pad}" x2="{px(ic):.1f}" y2="{H - pad}" '
             f'class="regra"/>' if ic is not None else "")
    nota = (f'<div class="evo-note">A <b>regra do preço mudou a {REGRA_NOVA}</b> '
            f'(uma cópia cujo acabamento não está cotado passou a valer o outro '
            f'acabamento, como nos <a href="colecao_cor.html">binders por cor</a>): '
            f'a linha tracejada é essa costura, e os pontos à esquerda dela estão '
            f'pela regra antiga (~11,67 € abaixo). Não é o mercado a mexer.</div>'
            if ic is not None else "")
    svg = (f'<svg viewBox="0 0 {W} {H}" class="spark">'
           f'<polygon points="{area}" class="fill {cls}"/>'
           f'<polyline points="{pts}" class="line {cls}"/>{dots}{marca}</svg>')
    return (f'<div class="evo"><div class="evo-top"><span class="evo-h">Evolução do valor</span>'
            f'<span class="evo-ind {cls}">{arrow} {pct:+.1f}% <em>desde {dates[0]}</em></span></div>'
            f'<div class="evo-axis"><span>{dates[0]}</span><span>{dates[-1]}</span></div>{svg}'
            f'{nota}</div>')


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


_CSS = """
 /* A galeria era a ÚNICA página em tema claro (`--bg:#f6f7f9`), com paleta
    própria — e por isso escapava ao teste do tema partilhado: usava `--add`/
    `--rem` sem os definir, e o indicador da evolução saía sem cor. Passou ao
    tema partilhado na reestruturação de 2026-09-24: passar da Coleção para a
    Galeria deixou de ser um flash branco. */
 .tools{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
 #q{flex:1;min-width:180px;padding:10px 13px;border:1px solid var(--line2);border-radius:10px;background:var(--card);color:var(--ink);font:inherit;font-size:14px;min-height:40px}
 .count{color:var(--muted);font-size:12.5px;white-space:nowrap}
 .tabs{margin:0 0 12px} .tabs .seg{max-width:100%}
 .tab b{opacity:.7;font-weight:600}
 .tab .tv{color:var(--gold);font-weight:700}
 .tab.active .tv{color:var(--accent)}
 .evo{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);padding:13px 16px;margin:0 0 14px}
 .evo-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
 .evo-h{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
 .evo-ind{font-weight:700;font-size:15px} .evo-ind em{font-style:normal;font-weight:400;color:var(--muted);font-size:12px}
 .evo-ind.up{color:var(--add)} .evo-ind.down{color:var(--rem)}
 .evo-axis{display:flex;justify-content:space-between;color:var(--muted);font-size:11px;margin:6px 0 0}
 .spark{width:100%;height:auto;display:block}
 .spark .line{fill:none;stroke-width:2;vector-effect:non-scaling-stroke} .spark .line.up{stroke:var(--add)} .spark .line.down{stroke:var(--rem)}
 .spark .fill.up{fill:var(--add);opacity:.13} .spark .fill.down{fill:var(--rem);opacity:.13}
 .spark .dot{stroke:var(--card);stroke-width:1} .spark .dot.up{fill:var(--add)} .spark .dot.down{fill:var(--rem)}
 .spark .regra{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3;vector-effect:non-scaling-stroke}
 .evo-note{color:var(--muted);font-size:12.5px;margin-top:6px}
 h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:7px;display:flex;justify-content:space-between;gap:10px;align-items:baseline}
 h2 b{color:var(--ink)} h2 .gv{color:var(--gold);font-variant-numeric:tabular-nums;font-size:13px;text-transform:none;letter-spacing:0}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
 .c{background:var(--card);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;position:relative}
 .c .imgwrap{position:relative;aspect-ratio:488/680;background:var(--line)}
 .c img{width:100%;height:100%;object-fit:cover;display:block}
 .c .noimg{width:100%;height:100%;display:flex;align-items:center;justify-content:center;text-align:center;padding:8px;font-size:12px;color:var(--muted)}
 .c .qty{position:absolute;top:6px;right:6px;background:rgba(0,0,0,.78);color:#fff;font-weight:700;font-size:12px;padding:1px 7px;border-radius:999px}
 .c .foil{position:absolute;top:6px;left:6px;font-size:12px;background:linear-gradient(135deg,#8ae,#e8a,#8ea);color:#111;font-weight:700;padding:1px 6px;border-radius:999px}
 .c .meta{padding:7px 9px} .c .nm{font-weight:600;font-size:12.5px;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .c .ed{color:var(--muted);font-size:11px;margin-top:1px} .c .pr{color:var(--gold);font-size:12px;font-weight:600;margin-top:2px;font-variant-numeric:tabular-nums}
 .c .pr .est{color:var(--muted);font-weight:400;cursor:help}
 .c .col{color:var(--muted);font-size:10.5px}
 .empty{color:var(--muted);padding:30px 0;text-align:center}
"""

_LEAD = ("<b>%TOTQ%</b> exemplares · valor ~<b style=\"color:var(--gold)\">%TOTV%</b>"
         " · imagens e preços via Scryfall/Cardmarket · dados até <b>%TODAY%</b>")

_RODAPE = ("Cada imagem é a impressão exata da carta (edição + número). Clica para "
           "abrir em grande. O valor é a mesma conta dos "
           '<a href="colecao_cor.html">binders</a>: as cartas com <b>~</b> não '
           "têm preço no acabamento da cópia e valem o do outro.")

_TMPL = ("""<!doctype html><html lang="pt-PT"><head>"""
         + shell.head("Galeria de cartas", _CSS) + """</head><body>"""
         + shell.abrir("colecao.html", "Galeria de cartas", _LEAD) + """
<div class="wrap">
%EVO%
<div class="tools"><input id="q" type="search" placeholder="Procurar carta ou edição…" autocomplete="off"><span class="count" id="count"></span></div>
<div id="tabs" class="tabs"></div>
<div id="app"></div>
</div>""" + shell.fechar(_RODAPE, """
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
  (c.eur!=null?'<div class="pr">'+(c.est?'<span class="est" title="sem preço neste acabamento — vale o preço '+esc(c.est)+'">~</span>':'')+eur(c.eur)+'</div>':'')+'</div></div>';
}
let ACTIVE="*";
function buildTabs(){
 const t=document.getElementById("tabs"), total=DATA.reduce((s,g)=>s+g.qty,0), totv=DATA.reduce((s,g)=>s+g.value,0);
 let h='<button class="tab" type="button" data-sub="*">Todas <b>('+total+')</b> <span class="tv">'+eur(totv)+'</span></button>';
 for(const g of DATA) h+='<button class="tab" type="button" data-sub="'+esc(g.sub)+'">'+esc(g.sub)+' <b>('+g.qty+')</b> <span class="tv">'+eur(g.value)+'</span></button>';
 /* `.seg` — o controlo segmentado partilhado. Era uma fila de pastilhas com o
    CSS desta página; agora é o mesmo de todas, e envolve em vez de correr. */
 t.innerHTML='<div class="seg" role="tablist" aria-label="Sub-coleção">'+h+'</div>';
 t.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{ACTIVE=b.dataset.sub;render(document.getElementById("q").value);}));
}
function render(filter){
 const f=(filter||"").trim().toLowerCase(); const app=document.getElementById("app"); let html="", shown=0;
 document.querySelectorAll("#tabs .tab").forEach(b=>{
   const on=b.dataset.sub===ACTIVE; b.classList.toggle("active",on); b.classList.toggle("on",on);
   b.setAttribute("aria-selected",on?"true":"false");});
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
</script>""") + """</body></html>""")


def _write_html(out_path, groups, total_qty, total_val, today, history):
    eur = paginas.eur(total_val)
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
