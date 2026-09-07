"""Gera metagame.html — os decks que ele está MAIS PERTO de concluir.

Ordem do André (2026-09-07, à letra): *"Para os decks 'metagame', em vez de me
dares todas as listas, dás-me só o top-3 decks que estou mais perto de concluir
para os formatos Standard, Pioneer, Legacy."*

Por isso esta página deixou de ser um mostruário do metagame (o top-10 de cada
formato com a lista mais recente de cada um) e passou a responder a uma só
pergunta: **qual é o próximo deck que vale a pena montar, e o que falta para
isso**. O que mudou de fundo:

  * **Standard, Pioneer e Legacy** — os `metagame_top_n` arquétipos (3 por
    omissão, `colecao_config.json → metagame_top_n`) com maior percentagem já
    tida, cada um com a sua **lista de consenso** (a lista padrão de sempre, do
    `stock.stock_list`). São os três slots que no `loadout` estão `por_confirmar`
    — é a pergunta "que deck é que eu meto nesta caixa?".
  * **Modern** — não há nada a escolher: o deck está escolhido (UW Oswald) e
    mostra-se a caixa do loadout, com as variantes marcadas.
  * **Premodern** — só o UW Replenish e a Enchantress, os alvos de consenso do
    `premodern_arquetipos_alvo` (âmbito de 2026-09-07). O Stiflenought não está
    aqui de propósito: segue a lista do Luffy e vive no `meusdecks.html`.

E a posse é a do LOADOUT, com os três estados de sempre — **tenho** (verde),
**está noutra caixa** (azul, vai-se buscar, não se compra) e **falta** (vermelho,
é compra). Nos formatos com regra de foil, uma nonfoil de uma carta que não é da
Reserved List não fecha o slot, e o custo usa o preço FOIL. Sem isso o ranking
dizia que ele tem cartas que não pode pôr no deck.

O `cobertura.html` (a vista do metagame inteiro, top-10 ponderado) e o
`showcase.html` ficam como estavam: a pergunta deles é outra. O
`decksfaziveis.html` foi retirado — perguntava exactamente isto e respondia pior
(cartas distintas do main da lista mais recente, sem regra de material).

NÃO inventa nada: se um formato não tem listas que contem, diz-se.
"""
from __future__ import annotations

import html
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import meta_coverage as mc  # noqa: E402
from mtgvault import loadout, paginas, sources  # noqa: E402

# Que formatos aparecem e COMO. É a ordem do André, tal como ele a deu:
#   'top'    — os N arquétipos que ele está mais perto de concluir (os slots do
#              loadout que estão por confirmar: Standard, Pioneer, Legacy);
#   'caixas' — o deck já escolhido, tal como está no loadout (Modern);
#   'alvos'  — só os arquétipos de `premodern_arquetipos_alvo` (Premodern).
SECOES = [
    ("standard", "Standard", "top"),
    ("pioneer", "Pioneer", "top"),
    ("legacy", "Legacy", "top"),
    ("modern", "Modern", "caixas"),
    ("premodern", "Premodern", "alvos"),
]

# Mínimo de listas para um arquétipo entrar no ranking. Abaixo disto a lista de
# consenso é ruído de um ou dois resultados soltos.
MIN_LISTS = 8

TABS = paginas.nav("metagame.html")


def top_n() -> int:
    """Quantos decks por formato. André, 2026-09-07: *"o top-3 decks que estou
    mais perto de concluir"*. Configurável em `colecao_config.json`."""
    try:
        return max(1, int(sources.config().get("metagame_top_n") or 3))
    except (TypeError, ValueError):
        return 3


def _alvos_premodern() -> set[str]:
    """Os alvos de consenso, como o `premodern_decks` os grava na tabela `decks`."""
    import premodern_decks as pd
    return {t + pd.SUFIXO for t in pd.alvos()}


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _img_map(con, names):
    """nome -> scryfall_id. Prefere-se a impressão que ele TEM: é a carta que vai
    mesmo estar na caixa."""
    out = {}
    for r in con.execute("""SELECT c.name nm, cp.scryfall_id sid FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player'"""):
        out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    falta = [n for n in names if n not in out]
    for i in range(0, len(falta), 300):
        ch = falta[i:i + 300]
        ph = ",".join("?" for _ in ch)
        for r in con.execute(f"""SELECT name nm, scryfall_id sid FROM cards
                                  WHERE name IN ({ph}) AND digital = 0 GROUP BY name""", ch):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    for n in [x for x in falta if x not in out]:      # DFCs: casa pela frente
        r = con.execute("SELECT scryfall_id sid FROM catalog.cards "
                        "WHERE name LIKE ? AND digital = 0 LIMIT 1",
                        (n + " // %",)).fetchone()
        if r:
            out[n] = r["sid"]
    return out


def _eur(v):
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",", 1) if v else "—"


def _resumo(linhas):
    """tenho / noutra caixa / comprar / custo de uma lista, SEM as básicas.

    As básicas ficam de fora da percentagem de propósito: com elas dentro um deck
    com 20 terras começava aos 33% e os arquétipos deixavam de se distinguir uns
    dos outros — que é exactamente o que esta página existe para mostrar.
    """
    nb = [m for m in linhas if not m.get("basica")]
    need = sum(m["need"] for m in nb)
    got = sum(m["got"] for m in nb)
    noutra = sum(m["noutra_q"] for m in nb)
    comprar = sum(m["comprar"] for m in nb)
    custo = round(sum(m["cost"] or 0 for m in nb), 2)
    return {"need": need, "got": got, "noutra": noutra, "comprar": comprar,
            "custo": custo, "tenho": got + noutra,
            "pct": round(100 * got / need) if need else 0,
            "pct_tenho": round(100 * (got + noutra) / need) if need else 0}


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def _bar(pct, pct_tenho):
    """Duas barras numa: a verde é o que está livre, a azul o que se vai buscar."""
    cor = "var(--add)" if pct >= 90 else "var(--gold)" if pct >= 60 else "var(--warn)"
    return (f'<div class="bar"><span class="ob" style="width:{pct_tenho}%"></span>'
            f'<span style="width:{pct}%;background:{cor}"></span></div>')


def _card(nm, sid, estado, etiq="", titulo=""):
    img = (f'<img loading="lazy" src="{_art(sid)}" alt="">' if sid
           else '<div class="noimg"></div>')
    q = f'<span class="cq">{etiq}</span>' if etiq else ""
    return (f'<div class="cd {estado}" title="{html.escape(titulo or nm)}">'
            f'{img}{q}</div>')


def _grid(linhas, imgs):
    """Cartas do deck pelo estado: tenho / está noutra caixa / falta."""
    def chave(m):
        if m["got"] >= m["need"]:
            return (0, m["nm"])
        return (1 if m["noutra_q"] else 2, m["nm"])
    out = ""
    for m in sorted(linhas, key=chave):
        if m["got"] >= m["need"]:
            est, tip = "have", f'{m["nm"]} — tens {m["got"]}/{m["need"]}'
        elif m["noutra_q"]:
            onde = "; ".join(f'{q}× em {c}' for c, q in sorted(m["noutra"].items()))
            est, tip = "noutra", f'{m["nm"]} — {onde}'
            if m["comprar"]:
                tip += f' · comprar {m["comprar"]}'
        else:
            est, tip = "miss", f'{m["nm"]} — comprar {m["comprar"]}'
        etiq = f'{m["got"]}/{m["need"]}' if m["got"] < m["need"] else (
            str(m["need"]) if m["need"] > 1 else "")
        out += _card(m["nm"], imgs.get(m["nm"]), est, etiq, tip)
    return out


def _onde_html(linhas):
    """'Ir buscar a outra caixa' — a resposta à pergunta 'onde está a carta'."""
    rows = sorted((m for m in linhas if m["noutra_q"]),
                  key=lambda m: (-m["noutra_q"], m["nm"]))
    if not rows:
        return ""
    itens = "".join(
        f'<li>{html.escape(m["nm"])} — '
        + "; ".join(f'<b>{q}×</b> em {html.escape(c)}'
                    for c, q in sorted(m["noutra"].items()))
        + (f' <span class="dim">(comprar mais {m["comprar"]})</span>'
           if m["comprar"] else "") + "</li>" for m in rows)
    n = sum(m["noutra_q"] for m in rows)
    return (f'<div class="onde"><b>📦 ir buscar a outra caixa — {n} cópias</b>'
            f'<ul>{itens}</ul></div>')


def _wantlist(linhas, marca=""):
    """Só o que é MESMO compra (`comprar`), no formato que o Cardmarket aceita."""
    ordem = sorted((m for m in linhas if m["comprar"] > 0), key=lambda m: m["nm"])
    if not ordem:
        return '<div class="ok">nada a comprar ✓</div>'
    itens = "".join(f'<li><b>{m["comprar"]}×</b> {html.escape(m["nm"])}'
                    f'<span class="pz">{_eur(m["cost"])}</span></li>' for m in ordem)
    txt = "\n".join(f'{m["comprar"]} {m["nm"]}' for m in ordem)
    extra = f' <span class="mrk">{marca}</span>' if marca else ""
    return (f'<div class="faltas"><div class="flh">🛒 Comprar{extra}'
            f'<span class="dim">{len(ordem)} cartas</span>'
            f'<button class="cpbtn" onclick="cp(this)">copiar</button></div>'
            f'<ul class="fl">{itens}</ul>'
            f'<textarea class="cmk" readonly>{html.escape(txt)}</textarea></div>')


def _deck_html(d, imgs):
    r = _resumo(d["linhas"])
    badges = "".join(f'<span class="bdg {c}">{t}</span>' for c, t in d.get("badges", []))
    # A percentagem do cabeçalho é a de QUANTO ELE TEM — livre mais o que está
    # noutra caixa, porque essa também é dele e vai-se lá buscar. É a mesma que
    # ordena o top-N; mostrar aqui a outra (só o livre) fazia a lista aparecer
    # desordenada sem explicação. A repartição fica na linha de baixo.
    return (
        f'<details class="deck"{" open" if d.get("aberto") else ""}><summary>'
        f'<b>{html.escape(d["nome"])}</b>'
        f'<span class="cov">{r["tenho"]}/{r["need"]} · {r["pct_tenho"]}%</span>'
        f'<span class="src">{html.escape(d["sub"])}</span></summary>'
        f'{_bar(r["pct"], r["pct_tenho"])}'
        f'<div class="badges">{badges}</div>'
        f'<div class="meta"><span>tenho livre <b>{r["got"]}</b></span>'
        f'<span class="ob">ir buscar a outra caixa <b>{r["noutra"]}</b></span>'
        f'<span>comprar <b>{r["comprar"]}</b></span>'
        f'<span>fechar por <b>{_eur(r["custo"])}</b></span></div>'
        f'<div class="cards">{_grid(d["linhas"], imgs)}</div>'
        f'{_onde_html(d["linhas"])}{_wantlist(d["linhas"], d.get("marca", ""))}'
        f'</details>')


# ---------------------------------------------------------------------------
def _decks_de_slots(slots, fmt, so_refs=None):
    """As caixas do loadout de um formato, já com a alocação lá dentro."""
    out = []
    for s in slots:
        if s.get("formato") != fmt or s["vazio"]:
            continue
        if so_refs is not None and s.get("ref") not in so_refs:
            continue
        badges = []
        if s.get("montado"):
            badges.append(("ok", "✅ montado"))
        # As regras de material do grupo de formato, todas (ver `deckboxes`).
        for ico, txt in loadout.rotulo_material(s):
            badges.append(("fo" if "foil" in txt else "pt", f"{ico} {txt}"))
        if s.get("so_de_variante"):
            badges.append(("", f'⇄ {len(s["so_de_variante"])} cartas só de variante'))
        out.append({"nome": s["nome"], "sub": s["nota"], "badges": badges,
                    "linhas": s["have"] + s["missing"],
                    "marca": loadout.marca_wantlist(s)})
    return out


def _decks_do_topo(con, fmt, res, n):
    """Os N arquétipos que ele está mais perto de concluir, com lista de consenso."""
    df = mc._format_df(con, fmt)
    tcache = {}
    out = []
    for r in loadout.foil_report(con, fmt, top=n, min_lists=MIN_LISTS, res=res):
        nome = mc._name_for(con, r["archetype_id"], df, tcache)
        # Sem `html.escape` aqui: quem escapa é o `_deck_html`, e escapar duas
        # vezes punha "It&#x27;ll Quench Ya!" à vista na página.
        out.append({"nome": nome, "linhas": r["linhas"], "marca": "FOIL",
                    "sub": f'{r["n_lists"]} listas que contam · {r["label"][:70]}',
                    "badges": [("fo", "✨ só foil"), ("", "🧩 lista de consenso")]})
    return out


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "metagame.html")
    n = top_n()
    res = loadout.allocate(con)
    alvos = _alvos_premodern()

    data, names = [], set()
    for fmt, titulo, modo in SECOES:
        if modo == "top":
            decks = _decks_do_topo(con, fmt, res, n)
            lead = (f'Os <b>{n}</b> arquétipos deste formato que estás mais perto de '
                    f'concluir, com a lista de consenso de cada um. É a caixa que '
                    f'ainda está por escolher no loadout.')
        elif modo == "caixas":
            decks = _decks_de_slots(res["slots"], fmt)
            lead = 'O deck já escolhido para a caixa deste formato, e as suas variantes.'
        else:
            decks = _decks_de_slots(res["slots"], fmt, so_refs=alvos)
            lead = ('Os alvos de consenso que pediste. O Stiflenought não está aqui: '
                    'segue a lista do Luffy, e vive nos <b>Decks permanentes</b>.')
        for d in decks:
            for m in d["linhas"]:
                names.add(m["nm"])
        data.append((fmt, titulo, decks, lead))
    imgs = _img_map(con, sorted(names))

    subnav, secs = "", ""
    for fmt, titulo, decks, lead in data:
        subnav += f'<a href="#f-{fmt}">{html.escape(titulo)} {len(decks)}</a>'
        if decks:
            decks[0]["aberto"] = True     # o primeiro de cada formato já aberto
            corpo = "".join(_deck_html(d, imgs) for d in decks)
        else:
            corpo = ('<p class="vazio">Sem listas que contem para este formato — '
                     'ou sem caixa escolhida. Não invento uma lista para encher a '
                     'página; vê <code>colecao_config.json → metagame_fontes</code>.</p>')
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(titulo)} '
                 f'<span class="n">{len(decks)}</span></h2>'
                 f'<p class="lead">{lead}</p>{corpo}</section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%META%", paginas.META)
                   .replace("%TEMA%", paginas.TEMA)
                   .replace("%TABS%", TABS).replace("%SUBNAV%", subnav)
                   .replace("%SECS%", secs).replace("%N%", str(n))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head>%META%
<title>Metagame</title><style>
%TEMA%
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em} .lead{color:var(--muted);font-size:12.5px;margin:2px 0 12px} .lead b{color:#c3cdd9}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 h2{font-size:14px;margin:24px 0 4px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .vazio{color:#5a6472;font-size:12.5px;background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:12px 14px} .vazio code{background:#0f141c;padding:0 4px;border-radius:4px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:8px}
 .deck>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:10px;list-style:none}
 .deck>summary::-webkit-details-marker{display:none} .deck>summary b{font-size:15px} .deck>summary::before{content:"\\25B8";color:var(--muted);margin-right:6px} .deck[open]>summary::before{content:"\\25BE"}
 .src{color:var(--muted);font-size:11px;margin-left:auto;text-align:right}
 .cov{font-size:12px;font-weight:700;padding:1px 9px;border-radius:20px;background:#1e2531;flex:none;white-space:nowrap}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:8px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px} .bar span.ob{background:#26406f}
 .badges{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:6px 0}
 .bdg{font-size:11px;padding:2px 8px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .bdg.ok{background:#123020;color:var(--add)} .bdg.pt{background:#101c2e;color:var(--ob)} .bdg.fo{background:#2a2410;color:var(--gold)}
 .meta{display:flex;flex-wrap:wrap;gap:4px 12px;color:var(--muted);font-size:11.5px;margin:4px 0} .meta b{color:var(--ink)}
 .meta .ob,.meta .ob b{color:var(--ob)}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
 .cd{position:relative;width:56px;border-radius:5px} .cd img,.cd .noimg{width:56px;height:78px;border-radius:4px;display:block;background:#0c0f14}
 .cd.have{box-shadow:0 0 0 2px var(--add)}
 .cd.noutra{box-shadow:0 0 0 2px var(--ob)} .cd.noutra img{filter:grayscale(.35) brightness(.74)}
 .cd.noutra::after{content:"\\1F4E6";position:absolute;top:1px;right:1px;font-size:10px;line-height:12px;background:#0e1620;border-radius:4px;padding:0 1px}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.75) brightness(.55)}
 .cd .cq{position:absolute;bottom:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 .onde{margin-top:9px;background:#0e1620;border:1px solid #25415e;border-radius:10px;padding:8px 10px;font-size:11.5px;color:var(--muted)}
 .onde>b{color:var(--ob);display:block;margin-bottom:4px;font-size:11px}
 .onde ul{margin:0;padding-left:16px} .onde li{padding:1px 0} .onde li b{color:var(--ob)} .onde .dim{color:#5a6472}
 .ok{color:var(--add);font-size:12px;margin-top:9px}
 .faltas{margin-top:10px}
 .flh{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;color:#e2795b} .flh .dim{color:var(--muted);font-weight:400} .flh .cpbtn{margin-left:auto}
 .mrk{font-size:10px;font-weight:800;padding:1px 6px;border-radius:5px;background:#2a2410;color:var(--gold)}
 .faltas ul.fl{list-style:none;margin:6px 0 0;padding:0;font-size:12px;column-width:250px;column-gap:22px} .faltas ul.fl li{display:flex;gap:6px;padding:1.5px 0;break-inside:avoid} .faltas ul.fl b{color:var(--gold);font-variant-numeric:tabular-nums}
 .faltas ul.fl .pz{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums}
 .cpbtn{font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;border:1px solid var(--line);background:#1a2230;color:var(--muted);cursor:pointer} .cpbtn:hover{border-color:var(--accent);color:var(--ink)} .cpbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🌐 Metagame</h1>
<div class="lead">Os <b>%N%</b> decks que estás mais perto de concluir em cada formato — com a lista de consenso, o que tens, o que está noutra caixa e o que falta comprar · dados de %TODAY%</div>
%TABS%<div class="subnav">%SUBNAV%</div></header>
%SECS%
<footer><b style="color:var(--add)">Verde</b> = tens a carta livre para esta caixa ·
<b style="color:var(--ob)">azul 📦</b> = tens a carta mas está <b>noutra caixa</b> do loadout
(diz qual e quantas — vais lá buscá-la, <b>não se compra</b>) ·
<b style="color:var(--warn)">vermelho</b> = não tens, é compra. A <b>percentagem</b> do topo é a do
que <b>tens</b> — verde mais azul, porque a que está noutra caixa também é tua — e é ela que
ordena o top-%N%; a barra mostra a repartição (a faixa clara é o verde). Ignora as terras
básicas: com elas, todos os decks começavam acima dos 30% e nenhum se distinguia dos outros.
A <b>lista de consenso</b> é a lista padrão do arquétipo — cada lugar ocupado pela
cópia com maior probabilidade de lá estar, calculada das decklists reais que contam.
<b>Standard, Pioneer e Legacy</b> são as caixas por escolher: aqui está o top-%N% para
decidires. <b>Modern</b> mostra o deck já escolhido; <b>Premodern</b>, os alvos de consenso.
Regra de material: nesses formatos as cartas são todas <b>foil</b> menos as da Reserved List
(o preço de fecho é o do foil), e no Premodern são todas <b>PT</b>.
Quem manda é o <code>colecao_config.json</code> (<code>metagame_top_n</code>, <code>loadout</code>).
Para o metagame inteiro, com o top-10 ponderado, vê <b>cobertura.html</b>. Atualiza diariamente.</footer>
</div>
<script>
function cp(btn){
  const c=btn.closest('.faltas'); const t=c&&c.querySelector('textarea.cmk'); if(!t)return;
  const done=()=>{btn.textContent='\\u2713 copiado';btn.classList.add('done');};
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t.value).then(done).catch(()=>{t.select();document.execCommand('copy');done();});
  }else{t.select();try{document.execCommand('copy');done();}catch(e){}}
}
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("metagame.html:", build(con))


if __name__ == "__main__":
    main()
