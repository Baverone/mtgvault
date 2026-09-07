"""Gera deckboxes.html — "Deckboxes": os decks montados em simultâneo, e a venda.

O André (2026-09-07): *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."*

Uma caixa por deck do `colecao_config.json -> loadout`, com a barra de completude,
as cartas em falta por preço, a wantlist para copiar para o Cardmarket, e as
CARTAS PARTILHADAS em destaque — as que duas caixas querem e não chegam para as
duas. No fim, "Para vender".

E, desde 07/09/2026, a pergunta "onde está a carta". O André: *"Vamos fazer como
no riftvault: indicas onde está a carta, para, se eu quiser ir jogar, saber onde
ir buscar e não ter que comprar múltiplos para todos."* Uma carta que a alocação
deu a outra caixa aparece a **âmbar** com *"em &lt;caixa&gt;"*, e **não entra na
lista de compras nem no custo de fechar**. Cada caixa mostra dois números:
*faltam comprar* e *ir buscar a outra caixa*.

A diferença para a página `meusdecks.html` (que mostra deck a deck, cada um a
contar a colecção inteira) é que aqui a colecção é REPARTIDA: uma cópia física
entra numa caixa e só numa. É por isso que esta página mostra números mais baixos
— e é este o número real de quem quer os decks todos montados ao mesmo tempo.

Reutiliza `mtgvault.loadout` para as contas. Não inventa nada.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import loadout  # noqa: E402

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a href="meusdecks.html">🎴 Decks permanentes</a>'
        '<a class="cur" href="deckboxes.html">🧰 Deckboxes</a>'
        '<a href="showcase.html">🎯 Showcase Challenger</a>'
        '<a href="colecao_cor.html">📚 Coleção</a>'
        '<a href="caixarl.html">📦 Caixa RL</a></nav>')


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _img_map(con, names):
    """nome -> scryfall_id de uma impressão com arte. Preferem-se as impressões
    que ele TEM (é a carta que vai estar na caixa)."""
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
                        "WHERE name LIKE ? AND digital = 0 LIMIT 1", (n + " // %",)).fetchone()
        if r:
            out[n] = r["sid"]
    return out


def _eur(v):
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",", 1) if v else "—"


def _bar(pct):
    cor = "var(--add)" if pct >= 90 else "var(--gold)" if pct >= 60 else "var(--warn)"
    return f'<div class="bar"><span style="width:{max(pct,2)}%;background:{cor}"></span></div>'


def _wantlist(missing, marca):
    """Bloco de COMPRAS com botão copiar, no formato que o Cardmarket aceita.

    Só entra o que é mesmo compra: uma carta que existe noutra caixa vai-se
    buscar, não se compra (regra do André de 07/09/2026). Por isso a quantidade é
    `comprar`, não `missing`, e as linhas que ficam a zero saem daqui.
    """
    ordem = sorted((m for m in missing if m["comprar"] > 0), key=lambda m: m["nm"])
    if not ordem:
        return ""
    itens = "".join(
        f'<li><b>{m["comprar"]}×</b> {html.escape(m["nm"])}'
        f'<span class="pz">{_eur(m["cost"])}</span></li>' for m in ordem)
    txt = "\n".join(f'{m["comprar"]} {m["nm"]}' for m in ordem)
    extra = f' <span class="mrk">{marca}</span>' if marca else ""
    return (f'<div class="faltas"><div class="flh">🛒 Comprar{extra}'
            f'<span class="dim">{len(ordem)} cartas</span>'
            f'<button class="cpbtn" onclick="cp(this)">copiar</button></div>'
            f'<ul class="fl">{itens}</ul>'
            f'<textarea class="cmk" readonly>{html.escape(txt)}</textarea></div>')


def _card(nm, sid, estado, etiq="", titulo=""):
    img = (f'<img loading="lazy" src="{_art(sid)}" alt="">' if sid
           else '<div class="noimg"></div>')
    q = f'<span class="cq">{etiq}</span>' if etiq else ""
    t = html.escape(titulo or nm)
    return f'<div class="cd {estado}" title="{t}">{img}{q}</div>'


def _slot_html(s, imgs, conflitos_por_carta):
    badges = []
    if s.get("montado"):
        badges.append('<span class="bdg ok">✅ montado</span>')
    elif s.get("por_confirmar") or s["vazio"]:
        badges.append('<span class="bdg wt">❓ por confirmar</span>')
    else:
        badges.append('<span class="bdg">🔧 a montar</span>')
    if s.get("lingua"):
        badges.append(f'<span class="bdg pt">🇵🇹 só {s["lingua"].upper()}</span>')
    if s.get("formato") == "premodern":
        badges.append('<span class="bdg pt">🚫 sem Caixa RL</span>')
    if s.get("acabamento") == "foil":
        badges.append('<span class="bdg fo">✨ só foil</span>')
    if s.get("variantes"):
        badges.append(f'<span class="bdg">⇄ {len(s["variantes"])} variantes</span>')

    if s["vazio"]:
        return (f'<div class="deck vazio"><div class="dtop"><b>{html.escape(s["nome"])}</b>'
                f'<span class="pct dim">—</span></div>'
                f'<div class="badges">{"".join(badges)}</div>'
                f'<div class="nota">{html.escape(s["nota"])}</div>'
                f'<div class="vaziomsg">Caixa por atribuir. Não escolhi por ti: '
                f'vê a recomendação no relatório e diz-me o deck.</div></div>')

    tidos = "".join(_card(m["nm"], imgs.get(m["nm"]), "have",
                          f'{m["got"]}' if m["need"] > 1 else "",
                          f'{m["nm"]} — tens {m["got"]}/{m["need"]}')
                    for m in s["have"])
    faltas = ""
    for m in s["missing"]:
        # Âmbar (o terceiro estado) para as duas maneiras de "tens, mas não aqui":
        # está noutra caixa, ou está e não serve. Vermelho fica só para o que não
        # existe em lado nenhum — é o que é mesmo compra.
        est = "sub" if (m["noutra_q"] or m["alt"]) else "miss"
        onde = "; ".join(f'{q}× em {c}' for c, q in sorted(m["noutra"].items()))
        razao = "; ".join(x for x in (
            onde, "; ".join(f'{v}× {k}' for k, v in m["alt"].items())) if x)
        if m["comprar"]:
            razao = "; ".join(x for x in (f'comprar {m["comprar"]}', razao) if x)
        conflito = " cf" if m["nm"] in conflitos_por_carta else ""
        faltas += _card(m["nm"], imgs.get(m["nm"]), est + conflito,
                        f'{m["got"]}/{m["need"]}',
                        f'{m["nm"]} — falta {m["missing"]} · '
                        f'{razao or "não tens nenhuma"}')

    onde = ""
    if s["noutra_caixa"]:
        linhas = "".join(
            f'<li>{html.escape(m["nm"])} — '
            + "; ".join(f'<b>{q}×</b> em {html.escape(c)}'
                        for c, q in sorted(m["noutra"].items()))
            + (f' <span class="dim">(comprar mais {m["comprar"]})</span>'
               if m["comprar"] else "")
            + "</li>" for m in s["noutra_caixa"])
        onde = (f'<div class="subs onde"><b>📦 ir buscar a outra caixa — '
                f'{s["noutra"]} cópias</b><ul>{linhas}</ul></div>')

    subs = ""
    if s["subs"]:
        linhas = "".join(
            f'<li>{html.escape(m["nm"])} — falta {m["missing"]}: '
            + "; ".join(f'tens <b>{v}</b> que {html.escape(k)}'
                        for k, v in m["alt"].items())
            # Onde estão: é a mesma pergunta das que estão noutra caixa. A Caixa
            # RL aparece separada em PT e EN, que é como elas estão na estante.
            + (' <span class="dim">(em '
               + html.escape(", ".join(f"{k}: {v}" for k, v in m["alt_onde"].items()))
               + ')</span>' if m["alt_onde"] else "") + "</li>"
            for m in s["subs"])
        subs = (f'<div class="subs"><b>↻ tens a carta, não serve a caixa</b>'
                f'<ul>{linhas}</ul></div>')

    # De onde se tiram as cartas para montar esta caixa.
    origens = ""
    if s["origens"]:
        origens = ('<div class="orig">🗂️ tirar de: '
                   + " · ".join(f'{html.escape(k)} <b>{v}</b>'
                                for k, v in s["origens"].items()) + '</div>')

    marca = ("FOIL" if s.get("acabamento") == "foil"
             else "PT" if s.get("lingua") == "pt" else "")
    return (
        f'<div class="deck">'
        f'<div class="dtop"><b>{html.escape(s["nome"])}</b>'
        f'<span class="pct">{s["pct"]}%</span></div>'
        f'{_bar(s["pct"])}'
        f'<div class="badges">{"".join(badges)}</div>'
        f'<div class="meta"><span>{s["tenho"]}/{s["precisa"]} cópias</span>'
        f'<span>faltam comprar <b>{s["comprar"]}</b></span>'
        f'<span class="ob">ir buscar a outra caixa <b>{s["noutra"]}</b></span>'
        f'<span>fechar por <b>{_eur(s["custo"])}</b></span></div>'
        f'<div class="nota">{html.escape(s["nota"])}</div>'
        f'{origens}'
        f'<div class="cards">{tidos}{faltas}</div>'
        f'{onde}{subs}{_wantlist(s["missing"], marca)}</div>')


def _conflitos_html(conflitos, imgs):
    if not conflitos:
        return ""
    linhas = ""
    for c in conflitos:
        # Quem levou "tem" a carta; quem não levou "vai buscar" — é a leitura que
        # o André pediu a 07/09/2026, e é por isso que já não se chama conflito.
        det = "".join(
            f'<span class="cs {"ok" if q["levou"] >= q["pediu"] else "no"}">'
            f'{html.escape(q["slot"])} {q["levou"]}/{q["pediu"]}</span>'
            for q in c["por_slot"])
        tem = ", ".join(c["ficam_com"]) or "ninguém"
        # Uma caixa pode estar nas duas listas (levou 3 das 4 que pedia). Essa não
        # "vai buscar" — não há lá nada para ela; falta-lhe mesmo e compra-se.
        # E se ninguém ficou com ela (as cópias existem mas nenhuma caixa as pode
        # usar — PT trancadas ao Premodern, p.ex.), não há nada a ir buscar.
        vai = ", ".join(x for x in c["ficam_sem"]
                        if c["ficam_com"] and x not in c["ficam_com"])
        linhas += (f'<div class="cfrow">{_card(c["nm"], imgs.get(c["nm"]), "cf")}'
                   f'<div class="cfb"><b>{html.escape(c["nm"])}</b>'
                   f'<span class="dim">tens {c["tenho"]} para {c["pedido"]} pedidas'
                   f' · está em <b>{html.escape(tem)}</b>'
                   + (f' · vai buscar: {html.escape(vai)}' if vai else "")
                   + f'</span><div class="csl">{det}</div></div></div>')
    return (f'<section id="conflitos"><h2>🔁 Cartas partilhadas entre caixas '
            f'<span class="n">{len(conflitos)}</span></h2>'
            f'<p class="lead">Cartas que duas ou mais caixas querem e não chegam '
            f'para todas. <b>Não são compras.</b> A cópia física fica na caixa de '
            f'<b>prioridade</b> mais alta (colecao_config.json → loadout) e as '
            f'outras vão lá buscá-la quando forem jogar — é por isso que aparecem '
            f'a âmbar com <b>“em &lt;caixa&gt;”</b> e não somam ao custo. Se '
            f'quiseres os decks todos prontos ao mesmo tempo sem trocas, aí sim: '
            f'compram-se cópias dedicadas, ou tira-se do loadout o deck de '
            f'prioridade mais baixa.</p>'
            f'<div class="cfgrid">{linhas}</div></section>')


def _venda_tabela(linhas, imgs, cls=""):
    tr = ""
    for r in linhas:
        rl = ' <span class="rl">RL</span>' if r["rl"] else ""
        fin = "✨" if r["finish"] in loadout.FOIL_FINISHES else ""
        tr += (f'<tr><td class="q">{r["q"]}×</td>'
               f'<td>{html.escape(r["nm"])}{rl}</td>'
               f'<td class="dim">{html.escape(r["local"])}</td>'
               f'<td class="dim">{html.escape((r["set_code"] or "").upper())} '
               f'{fin} {r["lang"].upper()}</td>'
               f'<td class="pz">{_eur(r["unit"])}</td>'
               f'<td class="pz tot">{_eur(r["total"])}</td>'
               f'<td class="dim rz">{html.escape(r["reason"])}</td></tr>')
    return (f'<table class="vt {cls}"><thead><tr><th></th><th>carta</th>'
            f'<th>balde</th><th>edição</th><th>un.</th><th>total</th>'
            f'<th>porquê</th></tr></thead><tbody>{tr}</tbody></table>')


def _venda_html(rep, imgs):
    def bloco(id_, titulo, lead, linhas, total, copias, aberto=False):
        if not linhas:
            return ""
        txt = "\n".join(f'{r["q"]} {r["nm"]}' for r in sorted(linhas, key=lambda x: x["nm"]))
        op = " open" if aberto else ""
        return (f'<details class="vblk" id="{id_}"{op}><summary>{titulo} '
                f'<span class="vtot">{copias} cópias · {_eur(total)}</span></summary>'
                f'<p class="lead">{lead}</p>'
                f'<div class="flh"><button class="cpbtn" onclick="cp(this)">copiar lista'
                f'</button></div><textarea class="cmk" readonly>{html.escape(txt)}</textarea>'
                f'{_venda_tabela(linhas, imgs)}</details>')

    return ('<section id="vender"><h2>💰 Para vender</h2>'
            '<p class="lead"><b>Sugestão a confirmar.</b> Nada sai da coleção sem '
            'tu dizeres. É o que sobra depois de encher todas as caixas do loadout '
            'e de guardar o backup: <b>4 por carta</b> na coleção (playset, a somar '
            'SPML + Premodern + Caixa RL — não 4 por balde) e <b>1 por deck</b> nas '
            'caixas de Commander. <b>Básicas nunca.</b></p>'
            + bloco("v-normal", "Excedente normal", "Cópias a mais de cartas que não "
                    "são Reserved List. É por aqui que se começa: o risco é baixo e "
                    "o dinheiro é real.", rep["venda"], rep["total"], rep["copias"], True)
            + bloco("v-rl", "⚠️ Reserved List — confirmar uma a uma",
                    "Cartas que nunca mais são impressas. A regra dá-as como "
                    "excedente, mas a decisão não se desfaz — e os preços de cartas "
                    "antigas na base não são de confiança (ver doubts.md). Confere "
                    "cada uma antes de listar.", rep["venda_rl"], rep["total_rl"],
                    rep["copias_rl"])
            + bloco("v-guardar", "🔒 Guardar — servem um deck do loadout",
                    "Estas passariam o limite de 4, mas são substitutos de cartas "
                    "que faltam a uma caixa: servem o deck e só não fecham o slot "
                    "por causa da língua (PT) ou do acabamento (foil). Se mudares "
                    "essas regras, entram nos decks; vendê-las era comprá-las outra "
                    "vez.", rep["guardar"], rep["total_guardar"], rep["copias_guardar"])
            + bloco("v-retidos", "⏳ Retidos — extras de decks montados",
                    "Baldes com <code>reter_extras_meses</code>: guardam-se até 6 "
                    "meses depois da última utilização. Ainda não há registo de "
                    "\"última utilização\", por isso ficam todos — não se vende "
                    "nada por uma regra que ainda não corre.",
                    rep["retidos"], rep["total_retido"], rep["copias_retidas"])
            + '</section>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "deckboxes.html")
    rep = loadout.report(con)
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""

    nomes = {c["nm"] for c in rep["conflitos"]}
    for s in rep["slots"]:
        nomes |= {n for _b, n, _q in s["cards"]}
    for k in ("venda", "venda_rl", "guardar", "retidos"):
        nomes |= {r["nm"] for r in rep[k]}
    imgs = _img_map(con, sorted(nomes))
    cfs = {c["nm"] for c in rep["conflitos"]}

    montados = [s for s in rep["slots"] if s.get("montado")]
    montar = [s for s in rep["slots"] if not s.get("montado") and not s["vazio"]]
    abertos = [s for s in rep["slots"] if s["vazio"]]

    secs, subnav = "", ""
    for sid, titulo, grupo, lead in (
        ("montados", "✅ Montados", montados,
         "Já estão em caixa. A % diz quanto da lista actual está lá dentro."),
        ("montar", "🔧 A montar", montar,
         "Caixas com deck escolhido, ainda por fechar. Ordenadas por prioridade."),
        ("abertos", "❓ Por confirmar", abertos,
         "Slots do loadout sem deck escolhido. Ficam vazios de propósito."),
    ):
        if not grupo:
            continue
        subnav += f'<a href="#{sid}">{titulo}</a>'
        cards = "".join(_slot_html(s, imgs, cfs) for s in grupo)
        secs += (f'<section id="{sid}"><h2>{titulo} <span class="n">{len(grupo)}'
                 f'</span></h2><p class="lead">{lead}</p>'
                 f'<div class="grid">{cards}</div></section>')
    subnav += ('<a href="#conflitos">🔁 Partilhadas</a>'
               '<a href="#vender">💰 Para vender</a>')
    secs += _conflitos_html(rep["conflitos"], imgs) + _venda_html(rep, imgs)

    # Wantlist geral: a soma do que é mesmo COMPRA em todas as caixas. Uma carta
    # que já está noutra caixa não entra aqui — vai-se buscar (regra do André,
    # 07/09/2026: "não ter que comprar múltiplos para todos").
    geral: dict[str, dict] = {}
    for s in rep["slots"]:
        for m in s["missing"]:
            if not m["comprar"]:
                continue
            g = geral.setdefault(m["nm"], {"nm": m["nm"], "comprar": 0, "cost": 0.0})
            g["comprar"] += m["comprar"]
            g["cost"] = round(g["cost"] + (m["cost"] or 0), 2)
    if geral:
        secs += ('<section id="compras"><h2>🛒 Comprar — todas as caixas</h2>'
                 '<p class="lead">Só o que <b>não existe</b> na coleção, ou existe '
                 'mas não serve na língua/acabamento que a caixa exige. As cartas '
                 'que estão noutra caixa <b>não estão aqui</b>: vão-se buscar. '
                 f'São <b>{rep["noutra_total"]}</b> cópias a ir buscar contra '
                 f'<b>{rep["comprar_total"]}</b> a comprar.</p>'
                 + _wantlist(sorted(geral.values(), key=lambda g: -g["cost"]), "") +
                 '</section>')

    resumo = (f'{len(montados)} montados · {len(montar)} a montar · '
              f'{len(abertos)} por confirmar · comprar {rep["comprar_total"]} '
              f'cópias por {_eur(rep["custo_total"])} · ir buscar a outra caixa '
              f'{rep["noutra_total"]} · vender {_eur(rep["total"])}')
    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SUBNAV%", subnav)
                   .replace("%SECS%", secs).replace("%RESUMO%", resumo)
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deckboxes</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em}
 h2{font-size:14px;margin:24px 0 4px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .lead{color:var(--muted);font-size:12.5px;margin:2px 0 12px} .lead b{color:#c3cdd9}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px} .deck:hover{border-color:#37445a}
 .deck.vazio{border-style:dashed;opacity:.85}
 .dtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px} .dtop b{font-size:15px} .pct{font-weight:800;font-size:16px} .pct.dim{color:var(--muted)}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:7px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .badges{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:7px 0}
 .bdg{font-size:11px;padding:2px 8px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .bdg.ok{background:#123020;color:var(--add)} .bdg.wt{background:#241a10;color:var(--gold)}
 .bdg.pt{background:#101c2e;color:#7fa8ff} .bdg.fo{background:#2a2410;color:var(--gold)}
 .meta{display:flex;flex-wrap:wrap;gap:4px 12px;color:var(--muted);font-size:11.5px;margin:5px 0} .meta b{color:var(--ink)}
 .nota{color:#5a6472;font-size:11px;margin:3px 0 2px}
 .vaziomsg{background:#241a10;border:1px solid #6a4f2f;border-radius:10px;padding:8px 10px;margin-top:8px;font-size:12px;color:#f0dcc0}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
 .cd{position:relative;width:52px;border-radius:5px} .cd img,.cd .noimg{width:52px;height:73px;border-radius:4px;display:block;background:#0c0f14}
 .cd.have{box-shadow:0 0 0 2px var(--add)}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.75) brightness(.55)}
 .cd.sub{box-shadow:0 0 0 2px var(--gold)} .cd.sub img{filter:grayscale(.35) brightness(.7)}
 .cd.cf::after{content:"⚔";position:absolute;top:1px;right:1px;background:var(--warn);color:#160a06;font-size:9px;font-weight:800;width:14px;height:14px;line-height:14px;text-align:center;border-radius:4px}
 .cd .cq{position:absolute;bottom:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 .subs{margin-top:9px;background:#0f141c;border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:11.5px;color:var(--muted)}
 .subs b{color:var(--gold);display:block;margin-bottom:4px;font-size:11px}
 .subs ul{margin:0;padding-left:16px} .subs li{padding:1px 0} .subs li b{display:inline;color:var(--ink)}
 .subs.onde{background:#0e1620;border-color:#25415e} .subs.onde>b{color:#7fa8ff}
 .subs.onde li b{color:#7fa8ff} .subs.onde .dim{color:#5a6472}
 .meta .ob{color:#7fa8ff} .meta .ob b{color:#7fa8ff}
 .orig{color:var(--muted);font-size:11px;margin:2px 0 0} .orig b{color:var(--ink);font-variant-numeric:tabular-nums}
 .faltas{margin-top:10px}
 .flh{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;color:#e2795b} .flh .dim{color:var(--muted);font-weight:400} .flh .cpbtn{margin-left:auto}
 .mrk{font-size:10px;font-weight:800;padding:1px 6px;border-radius:5px;background:#2a2410;color:var(--gold)}
 .faltas ul.fl{list-style:none;margin:6px 0 0;padding:0;font-size:12px} .faltas ul.fl li{display:flex;gap:6px;padding:1.5px 0} .faltas ul.fl b{color:var(--gold);font-variant-numeric:tabular-nums}
 .faltas ul.fl .pz{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums}
 #compras ul.fl{column-width:230px;column-gap:22px} #compras ul.fl li{break-inside:avoid}
 .cpbtn{font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;border:1px solid var(--line);background:#1a2230;color:var(--muted);cursor:pointer} .cpbtn:hover{border-color:var(--accent);color:var(--ink)} .cpbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
 .cfgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
 .cfrow{display:flex;gap:9px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px}
 .cfb{min-width:0;display:flex;flex-direction:column;gap:3px} .cfb b{font-size:13px} .cfb .dim{color:var(--muted);font-size:11px}
 .csl{display:flex;flex-wrap:wrap;gap:3px;margin-top:2px}
 .cs{font-size:10.5px;padding:1px 6px;border-radius:5px;font-variant-numeric:tabular-nums}
 .cs.ok{background:#0f2418;color:var(--add)} .cs.no{background:#2a1414;color:#ff8f8f}
 .vblk{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:10px}
 .vblk>summary{cursor:pointer;font-weight:700;font-size:14px;color:var(--ink)}
 .vblk .vtot{float:right;color:var(--gold);font-variant-numeric:tabular-nums}
 .vblk code{background:#0f141c;padding:0 4px;border-radius:4px;font-size:11px}
 table.vt{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
 table.vt th{text-align:left;color:#4a5666;font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);padding:4px 6px}
 table.vt td{padding:3px 6px;border-bottom:1px solid #1a212c} table.vt tr:hover td{background:#141a24}
 table.vt td.q{color:var(--gold);font-weight:700;font-variant-numeric:tabular-nums;text-align:right}
 table.vt td.dim{color:var(--muted)} table.vt td.pz{text-align:right;font-variant-numeric:tabular-nums}
 table.vt td.tot{color:var(--gold);font-weight:700} table.vt td.rz{font-size:11px}
 .rl{font-size:9px;font-weight:800;padding:0 4px;border-radius:4px;background:#3a1f1f;color:#ff9f8f;vertical-align:middle}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
 @media(max-width:640px){table.vt td.rz,table.vt th:last-child{display:none}}
</style></head><body><div class="wrap">
<header><h1>🧰 Deckboxes</h1>
<div class="lead">Os decks montados ao mesmo tempo, cada um na sua caixa · %RESUMO% · dados de %TODAY%</div>
%TABS%
<div class="subnav">%SUBNAV%</div></header>
%SECS%
<footer>Uma cópia física entra numa caixa e <b>só numa</b> — por isso os números aqui são
mais baixos que os da página <b>Decks permanentes</b>, onde cada deck conta a coleção
inteira. <b style="color:var(--add)">Verde</b> = tens · <b style="color:var(--gold)">âmbar</b>
= tens a carta mas não está nesta caixa: ou está <b>noutra caixa</b> (diz qual e quantas —
vais lá buscá-la, não se compra) ou não serve esta (língua ou acabamento) ·
<b style="color:var(--warn)">vermelho</b> = não tens nenhuma, é compra ·
<b>⚔</b> = partilhada com outra caixa. Regras de material: os decks de
<b>Premodern</b> só levam cartas <b>PT</b> das edições da era, e essas não entram em mais
nenhum formato — e <b>só vêem cartas PT</b> (regra de 07/09/2026): uma cópia em inglês não
conta, nem sequer como âmbar, é compra em PT. Da <b>Caixa RL</b> vêem só a metade
<b>PT</b> — na estante são duas caixas, e por isso a localização diz sempre
<b>Caixa RL (PT)</b> ou <b>Caixa RL (EN)</b>; <b>Standard/Pioneer/Modern/Legacy</b> só levam
<b>foil</b>, menos as da Reserved List. Quem manda no loadout é o <code>colecao_config.json → loadout</code>.
A lista para vender é uma <b>sugestão a confirmar</b>. Atualiza diariamente.</footer>
</div>
<script>
function cp(btn){
  const c=btn.closest('.faltas')||btn.closest('.vblk');
  const t=c&&c.querySelector('textarea.cmk'); if(!t)return;
  const done=()=>{btn.textContent='✓ copiado';btn.classList.add('done');};
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t.value).then(done).catch(()=>{t.select();document.execCommand('copy');done();});
  }else{t.select();try{document.execCommand('copy');done();}catch(e){}}
}
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("deckboxes.html:", build(con))


if __name__ == "__main__":
    main()
