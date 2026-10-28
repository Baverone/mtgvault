"""O que as três páginas do núcleo partilham: o CSS, o mosaico de um deck, a
carta em imagem, a barra de progresso, o gráfico do valor e as pequenas frases.

As páginas (`nucleo_painel.py`, `nucleo_decks.py`, `nucleo_vender.py`, na raiz)
só montam; o desenho vive aqui para as três terem a mesma cara. O que se
decidiu e vale a pena saber:

- **As cores são as da casca** (`site_shell.TEMA`). Este ficheiro não escreve
  um único hex (o `test_tokens` tem um tecto de cores à mão e o
  `test_nucleo_paginas` exige zero aqui): os véus sobre as imagens são
  `rgba(0,0,0,…)`, que é sombra e não cor.
- **As imagens vêm só do CDN do Scryfall** (`cards.scryfall.io`), pelo
  `scryfall_id`. Nunca da API (`api.scryfall.com/cards/named`), que é um pedido
  por imagem ao servidor deles — os esboços usavam-na e estava bem para um
  esboço. A arte de um deck é o `art_crop` da carta `arte_nome`
  (`arte_do_deck`).
- **O gráfico não inventa pontos.** É SVG desenhado no servidor (um por
  período: 1 mês, 3 meses, tudo) e o JavaScript só esconde e mostra. Com menos
  de dois dias de valor não há linha nenhuma — diz-se porquê.
- **Uma carta sem preço nunca vale 0 €**: diz «sem preço».
"""
from __future__ import annotations

import html
import sqlite3
from datetime import date

from .. import paginas, scryfall
from . import posse

CDN = "https://cards.scryfall.io"

FORMATOS = {
    "premodern": "Premodern", "cedh": "cEDH", "pauper": "Pauper",
    "duel-commander": "Duel Commander", "standard": "Standard",
    "pioneer": "Pioneer", "modern": "Modern", "legacy": "Legacy",
}
ACABAMENTO = {"nonfoil": "normal", "foil": "foil"}
SECCAO = {"comandante": "Comandante", "main": "Main", "side": "Sideboard"}
ORDEM_SECCAO = ("comandante", "main", "side")

# Os três períodos do gráfico: (chave, rótulo, dias; None = tudo). Abre em
# «3 meses», como no esboço aprovado.
PERIODOS = (("1m", "1 mês", 30), ("3m", "3 meses", 90), ("tudo", "tudo", None))
PERIODO_INICIAL = "3m"

e = html.escape


# ---------------------------------------------------------------------------
# Pequenas frases
# ---------------------------------------------------------------------------
def data_pt(iso: str | None) -> str:
    """`2026-10-14T03:30:00` → `14/10/2026`. Sem data, «—»."""
    if not iso:
        return "—"
    s = str(iso)[:10]
    try:
        a, m, d = s.split("-")
        return f"{d}/{m}/{a}"
    except ValueError:
        return s


def _dia(iso: str) -> date:
    return date.fromisoformat(str(iso)[:10])


def formato(f: str) -> str:
    return FORMATOS.get(f, f)


def aviso_vigia(deck) -> str | None:
    """A frase de uma vigia que falhou, ou `None` se a última correu bem.

    Com `vigia_ok_em`, diz desde quando a lista que se vê é a última boa; sem
    ela, a vigia nunca leu nada.
    """
    if not deck["vigia"] or not deck["vigia_erro"]:
        return None
    if deck["vigia_ok_em"]:
        return f"não consegui ver a lista desde {data_pt(deck['vigia_ok_em'])}"
    return "ainda não consegui ver a lista"


def vigia_texto(vigia: str | None) -> str:
    """De onde vem a lista, em HTML: «lista fixa» ou a fonte da vigia."""
    if not vigia:
        return "lista fixa"
    partes = vigia.split(":")
    if partes[0] == "mtgo" and len(partes) >= 2:
        return f"lista vigiada · MTGO, {e(partes[1])}"
    if partes[0] == "moxfield" and len(partes) >= 2:
        url = f"https://moxfield.com/decks/{e(partes[1])}"
        return (f'lista vigiada · <a href="{url}" rel="noopener">Moxfield</a>')
    return f"lista vigiada · {e(vigia)}"


def fonte_html(fonte: str | None) -> str:
    """A fonte de uma versão (texto livre); um link fica um link."""
    f = (fonte or "").strip()
    if f.startswith(("https://", "http://")):
        curto = f.split("://", 1)[1].rstrip("/")
        if len(curto) > 42:
            curto = curto[:40] + "…"
        return f'<a href="{e(f)}" rel="noopener">{e(curto)}</a>'
    return e(f) if f else "sem fonte"


def diferenca_html(dif: dict, limite: int | None = 8) -> str:
    """`+2 Galvanic Blast · −2 Fling` (o menos é o tipográfico, U+2212)."""
    itens = ([f'<span class="ent">+{q} {e(n)}</span>' for n, q in dif["entrou"]]
             + [f'<span class="sai">−{q} {e(n)}</span>' for n, q in dif["saiu"]])
    if not itens:
        return "só mudou de secção"
    if limite is not None and len(itens) > limite:
        resto = len(itens) - limite
        itens = itens[:limite] + [f"e mais {resto}"]
    return " · ".join(itens)


def preco_do_dia(con: sqlite3.Connection) -> str | None:
    r = con.execute("SELECT MAX(date) FROM price_latest"
                    " WHERE source = 'cardmarket'").fetchone()
    return r[0] if r and r[0] else None


def corpo(editavel: bool) -> str:
    """O `<body>`: no modo de edição leva a marca que o JavaScript da edição
    procura (o token nunca vai na página: vem no URL e fica lá)."""
    return '<body data-editavel="1">' if editavel else "<body>"


# ---------------------------------------------------------------------------
# Imagens
# ---------------------------------------------------------------------------
def url_carta(sid: str | None, tamanho: str = "small") -> str:
    """A imagem de uma impressão no CDN: `small` (146×204) ou `normal`."""
    if not sid:
        return ""
    return f"{CDN}/{tamanho}/front/{sid[0]}/{sid[1]}/{sid}.jpg"


def url_arte(sid: str | None) -> str:
    """A arte recortada (`art_crop`) de uma impressão: a cara de um deck."""
    return url_carta(sid, "art_crop")


def arte_do_deck(con: sqlite3.Connection, slug: str,
                 arte_nome: str | None) -> str | None:
    """O `scryfall_id` cuja arte dá a cara ao deck.

    Primeiro a edição que ele ESCOLHEU para essa carta num âmbito do deck; sem
    escolha, a PRIMEIRA impressão em papel, em inglês, de um set normal — a
    arte original. A «melhor» do `scryfall.impressoes` (a mais recente) não
    serve aqui: visto na base dele a 28/10, a mais recente do Kraum e da
    Greasefang são molduras especiais e o `art_crop` delas sai com texto por
    cima. Sem nenhuma, `None` — o mosaico fica liso, sem imagem inventada.
    """
    if not arte_nome:
        return None
    r = con.execute("SELECT scryfall_id FROM n_edicao WHERE nome = ?"
                    " AND ambito IN (?, ?) ORDER BY ambito = ? DESC LIMIT 1",
                    (arte_nome, slug, posse.ROT, slug)).fetchone()
    if r:
        return r[0]
    r = con.execute(
        "SELECT scryfall_id FROM cards WHERE name = ? AND "
        + scryfall.sql_impressao_a_serio("")
        + " ORDER BY COALESCE(lang, 'en') <> 'en',"
        " COALESCE(set_type, '') NOT IN ('core', 'expansion', 'commander',"
        " 'draft_innovation', 'masters'), released_at, scryfall_id LIMIT 1",
        (arte_nome,)).fetchone()
    return r[0] if r else None


def img_carta(sid: str, alt: str, cls: str = "") -> str:
    """A `<img>` de uma carta: `small`, com o `normal` para ecrãs densos.

    `lazy` (a página do deck tem os 14 decks: só se descarrega o que se vê),
    `async` e o tamanho escrito, para a grelha não saltar ao carregar.
    """
    c = f' class="{cls}"' if cls else ""
    return (f'<img{c} src="{url_carta(sid)}" srcset="{url_carta(sid)} 146w, '
            f'{url_carta(sid, "normal")} 488w" sizes="(min-width:1200px) 140px,'
            f' (min-width:900px) 16vw, 25vw" alt="{e(alt)}" loading="lazy"'
            f' decoding="async" width="146" height="204">')


# ---------------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------------
def pct_de(tenho: int, total: int) -> int:
    return int(round(100 * tenho / total)) if total else 0


def barra(tenho: int, total: int, cls: str = "pbar") -> str:
    p = pct_de(tenho, total)
    return (f'<i class="{cls}" role="img" aria-label="{tenho} de {total} cartas">'
            f'<b style="width:{p}%"></b></i>')


def carta(c: dict, *, slug: str, editavel: bool = False,
          com_onde: bool = False) -> str:
    """Uma carta do deck em imagem: a cores se a tens, a cinzento se falta.

    `falta` (e `parcial` se tens algumas) leva a imagem a cinzento; `foil` dá o
    brilho. A quantidade vai no canto; o que falta vai em baixo, com o preço de
    cada uma ou «sem preço». Nas partilhadas, `com_onde` põe em cima onde
    está o monte (aqui / no deck montado).
    """
    cls = ["ct"]
    if c["falta"]:
        cls.append("falta")
        if c["tenho"]:
            cls.append("parcial")
    if c["acabamento"] == "foil":
        cls.append("foil")
    if not c["scryfall_id"]:
        cls.append("semimg")
    dados = ""
    if editavel:
        dados = (f' data-deck="{e(slug)}" data-nome="{e(c["nome"])}"'
                 f' data-sid="{e(c["scryfall_id"] or "")}"'
                 f' data-acab="{e(c["acabamento"] or "")}"')
    img = (img_carta(c["scryfall_id"], c["nome"]) if c["scryfall_id"]
           else f'<span class="nm">{e(c["nome"])}</span>')
    sb = "<small> SB</small>" if c["seccao"] == "side" and c.get("grupo") else ""
    q = f'<u class="q">{c["qtd"]}{sb}</u>'
    onde = ""
    if com_onde and c.get("onde"):
        txt = "aqui" if c["onde"] == "aqui" else f"no {c['onde']}"
        aq = " aqui" if c["onde"] == "aqui" else ""
        onde = f'<i class="onde{aq}">{e(txt)}</i>'
    falta = ""
    if c["falta"]:
        # dois pedaços que não se partem por dentro: numa carta de 85 px o
        # «€» ficava sozinho na linha de baixo
        if c["preco_un"] is None:
            preco = "sem preço"
        else:
            preco = "× " + paginas.eur(c["preco_un"]).replace(" ", " ")
        falta = (f'<em><b>falta {c["falta"]}</b> <span>{preco}</span></em>')
    return (f'<figure class="{" ".join(cls)}" title="{e(c["nome"])}"{dados}>'
            f'{img}{q}{onde}{falta}</figure>')


def grelha(cartas: list[dict], *, slug: str, editavel: bool = False,
           com_onde: bool = False) -> str:
    return ('<div class="cg">'
            + "".join(carta(c, slug=slug, editavel=editavel, com_onde=com_onde)
                      for c in cartas) + "</div>")


# ---------------------------------------------------------------------------
# Os decks: dados de todos e o mosaico
# ---------------------------------------------------------------------------
def dados_decks(con: sqlite3.Connection) -> list[dict]:
    """Os decks por ordem, cada um com a linha do `n_deck`, o `estado_deck`
    e a arte. Calcula-se uma vez por página."""
    from . import modelo                                     # noqa: PLC0415
    out = []
    for d in modelo.decks(con):
        est = posse.estado_deck(con, d["slug"])
        out.append({"deck": d, "estado": est,
                    "arte": arte_do_deck(con, d["slug"], d["arte_nome"])})
    return out


def mosaico(item: dict, href: str) -> str:
    """O mosaico de um deck: arte, nome, formato, progresso e a barra."""
    d, est = item["deck"], item["estado"]
    img = (f'<img src="{url_arte(item["arte"])}" alt="" loading="lazy"'
           f' decoding="async" width="626" height="457">' if item["arte"] else "")
    if est["versao"] is None:
        prog = "à espera da lista" if not d["vigia"] else "à espera da vigia"
    else:
        prog = f'{est["tenho"]}/{est["total"]} · {pct_de(est["tenho"], est["total"])} %'
    chips = ""
    if d["modo"] == "rotativo" and est["montado"]:
        chips += '<span class="tc ok">montado</span>'
    if aviso_vigia(d):
        chips += '<span class="tc aviso">lista por ver</span>'
    return (f'<a class="tile" href="{e(href)}">{img}'
            f'<span class="tf">{e(formato(d["formato"]))}</span>{chips}'
            f'<span class="tx"><span class="tn">{e(d["nome"])}</span>'
            f'<span class="tp">{prog}</span></span>'
            f'{barra(est["tenho"], est["total"], "tb")}</a>')


def mosaicos(itens: list[dict], prefixo: str) -> str:
    """Os dois grupos, «Sempre montados» e «Rotativos». `prefixo` é o que vem
    antes do `#slug` (`deck.html` no Painel, nada na página dos decks)."""
    out = ""
    for modo, titulo in (("sempre", "Sempre montados"), ("rotativo", "Rotativos")):
        grupo = [i for i in itens if i["deck"]["modo"] == modo]
        if not grupo:
            continue
        nota = paginas.plural(len(grupo), "deck")
        if modo == "rotativo":
            m = [i["deck"]["nome"] for i in grupo if i["estado"]["montado"]]
            nota += (f" · montado: {e(m[0])}" if m else " · nenhum montado")
        out += (f'<h2 class="gt">{titulo} <small>{nota}</small></h2>'
                '<div class="tiles">'
                + "".join(mosaico(i, f'{prefixo}#{i["deck"]["slug"]}')
                          for i in grupo) + "</div>")
    return out


# ---------------------------------------------------------------------------
# O valor: variação do mês e o gráfico
# ---------------------------------------------------------------------------
def variacao_mes(serie: list[tuple[str, float]]) -> dict | None:
    """O último ponto contra o de há ~30 dias (o mais recente com data
    `<=` último − 30), ou contra o primeiro se a série for mais curta.

    `{delta, pct, desde}`; `pct` é `None` se o ponto de partida valia 0. Com
    menos de dois pontos não há variação: `None` (a página escreve «—»).
    """
    if len(serie) < 2:
        return None
    ult_dia, ult = serie[-1]
    limite = _dia(ult_dia).toordinal() - 30
    ref = serie[0]
    for p in serie[:-1]:
        if _dia(p[0]).toordinal() <= limite:
            ref = p
    delta = round(ult - ref[1], 2)
    pct = round(100 * delta / ref[1], 1) if ref[1] else None
    return {"delta": delta, "pct": pct, "desde": ref[0][:10]}


def _tudo_zero(serie) -> bool:
    """Sem nada marcado, a série é uma fila de 0 € (o inventário de hoje aos
    preços de cada dia): uma linha deitada no zero não diz nada."""
    return all(not v for _d, v in serie)


def variacao_html(serie: list[tuple[str, float]]) -> str:
    v = None if _tudo_zero(serie) else variacao_mes(serie)
    if v is None:
        return '<span class="vvar" title="ainda não há um dia anterior">—</span>'
    dias = _dia(serie[-1][0]).toordinal() - _dia(v["desde"]).toordinal()
    quando = "num mês" if 28 <= dias <= 32 else f"desde {data_pt(v['desde'])[:5]}"
    seta, cls = (("▲", " sobe") if v["delta"] > 0 else
                 ("▼", " desce") if v["delta"] < 0 else ("=", ""))
    pct = f" ({paginas.pct(v['pct'])})" if v["pct"] is not None else ""
    return (f'<span class="vvar{cls}">{seta} {paginas.eur(abs(v["delta"]))}'
            f'{pct} {quando}</span>')


def _svg(pontos: list[tuple[str, float]], rotulo: str) -> str:
    """Uma linha (o que tens) e a área por baixo, num `viewBox` 300×100."""
    x0 = _dia(pontos[0][0]).toordinal()
    x1 = _dia(pontos[-1][0]).toordinal()
    vs = [p[1] for p in pontos]
    lo, hi = min(vs), max(vs)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad

    def xy(p):
        x = 300 * (_dia(p[0]).toordinal() - x0) / ((x1 - x0) or 1)
        y = 100 - 100 * (p[1] - lo) / (hi - lo)
        return f"{x:.1f},{y:.1f}"
    linha = " ".join(xy(p) for p in pontos)
    area = f"0,100 {linha} 300,100"
    return (f'<svg viewBox="0 0 300 100" preserveAspectRatio="none" role="img"'
            f' aria-label="{e(rotulo)}"><polygon class="ga" points="{area}"/>'
            f'<polyline class="gl" points="{linha}"/></svg>')


def grafico(serie: list[tuple[str, float]]) -> str:
    """Os três períodos, cada um com o seu SVG; o JavaScript só alterna."""
    if len(serie) < 2:
        return ('<p class="gvazio">O gráfico aparece quando houver dois dias de '
                'valor guardados.</p>')
    if _tudo_zero(serie):
        return ('<p class="gvazio">O gráfico aparece quando marcares as '
                'primeiras cartas.</p>')
    fim = _dia(serie[-1][0]).toordinal()
    botoes, vistas = "", ""
    for chave, rot, dias in PERIODOS:
        pts = serie if dias is None else [
            p for p in serie if _dia(p[0]).toordinal() >= fim - dias]
        on = chave == PERIODO_INICIAL
        marca = ' class="on" aria-pressed="true"' if on else ' aria-pressed="false"'
        botoes += f'<button type="button" data-gv="{chave}"{marca}>{rot}</button>'
        if len(pts) < 2:
            corpo_ = '<p class="gvazio">Só há um dia de valor neste período.</p>'
        else:
            vs = [p[1] for p in pts]
            rotulo = (f"De {data_pt(pts[0][0])} a {data_pt(pts[-1][0])}: "
                      f"{paginas.eur(pts[0][1])} para {paginas.eur(pts[-1][1])}")
            corpo_ = (_svg(pts, rotulo)
                      + f'<div class="gx"><span>{data_pt(pts[0][0])[:5]}</span>'
                      f'<span>mín {paginas.eur(min(vs), 0)} · máx '
                      f'{paginas.eur(max(vs), 0)}</span>'
                      f'<span>{data_pt(pts[-1][0])[:5]}</span></div>')
        vistas += (f'<div class="gq" data-vista="{chave}"'
                   f'{"" if on else " hidden"}>{corpo_}</div>')
    return (f'<div class="seg gseg" role="group" aria-label="Período do gráfico">'
            f'{botoes}</div><div class="graf">{vistas}</div>')


JS_GRAFICO = r"""
(function(){
  var bs = document.querySelectorAll('[data-gv]'),
      vs = document.querySelectorAll('[data-vista]');
  function liga(v){
    for (var i = 0; i < bs.length; i++) {
      var on = bs[i].getAttribute('data-gv') === v;
      bs[i].classList.toggle('on', on);
      bs[i].setAttribute('aria-pressed', on ? 'true' : 'false');
    }
    for (var j = 0; j < vs.length; j++) vs[j].hidden = vs[j].getAttribute('data-vista') !== v;
  }
  for (var i = 0; i < bs.length; i++) bs[i].addEventListener('click', function(){
    liga(this.getAttribute('data-gv'));
  });
})();
"""


# ---------------------------------------------------------------------------
# O CSS das três páginas (mobile primeiro: 4 cartas por linha a 390 px, 8 a
# 1440; mosaicos 2 por linha no telemóvel, 4–5 no PC)
# ---------------------------------------------------------------------------
CSS = r"""
 .nuc [hidden]{display:none!important}
 .nuc h2.gt{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);
   margin:28px 0 10px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;font-weight:700}
 .nuc h2.gt small{text-transform:none;letter-spacing:0;color:var(--ink2);font:500 12.5px var(--font)}
 .nuc h2.gt .val{margin-left:auto;color:var(--accent);font:700 14px var(--font-hd);letter-spacing:0}
 .nuc .vazio{margin:0}
 .nuc a.lk{min-height:36px;display:inline-flex;align-items:center}

 /* o valor */
 .vcard{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);padding:16px 16px 12px}
 .vlab{color:var(--muted);font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:700}
 .vlin{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px}
 .vbig{font:700 34px/1.15 var(--font-hd);color:var(--accent);font-variant-numeric:tabular-nums}
 .vvar{font-size:13px;font-weight:600;color:var(--muted);white-space:nowrap}
 .vvar.sobe{color:var(--ok)} .vvar.desce{color:var(--bad)}
 .vnota{color:var(--dim);font-size:12px;margin:2px 0 10px}
 .gseg{margin:2px 0 8px}
 .gseg button{min-height:36px}
 .graf svg{display:block;width:100%;height:140px;overflow:visible}
 .graf .gl{fill:none;stroke:var(--accent);stroke-width:2.2;vector-effect:non-scaling-stroke;
   stroke-linejoin:round;stroke-linecap:round}
 .graf .ga{fill:var(--accent-soft);stroke:none;opacity:.9}
 .gx{display:flex;justify-content:space-between;gap:8px;color:var(--dim);font-size:11px;
   font-variant-numeric:tabular-nums;margin-top:4px}
 .gvazio{color:var(--muted);font-size:13px;margin:6px 0 2px}

 /* os mosaicos dos decks */
 .tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
 @media (min-width:900px){ .tiles{grid-template-columns:repeat(4,minmax(0,1fr))} }
 @media (min-width:1300px){ .tiles{grid-template-columns:repeat(5,minmax(0,1fr))} }
 .tile{position:relative;display:block;aspect-ratio:4/3;border-radius:var(--r);overflow:hidden;
   background:var(--card3);border:1px solid var(--line);color:var(--ink);text-decoration:none;isolation:isolate}
 .tile img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:-2;
   transition:transform .35s ease}
 .tile:hover img{transform:scale(1.05)}
 .tile:hover{border-color:var(--accent-line)}
 .tile::before{content:"";position:absolute;inset:0;z-index:-1;
   background:linear-gradient(180deg,rgba(0,0,0,0) 30%,rgba(0,0,0,.82) 100%)}
 .tile .tf{position:absolute;left:7px;top:7px;font-size:9.5px;font-weight:700;letter-spacing:.07em;
   text-transform:uppercase;background:rgba(0,0,0,.6);padding:1px 7px;border-radius:99px}
 .tile .tc{position:absolute;right:7px;top:7px;font-size:10px;font-weight:700;padding:1px 7px;
   border-radius:99px;border:1px solid}
 .tile .tc.ok{background:var(--ok-soft);color:var(--ok);border-color:var(--ok-line)}
 .tile .tc.aviso{background:var(--warn-soft);color:var(--warn-forte);border-color:var(--warn-line)}
 .tile .tc+.tc{top:28px}
 .tile .tx{position:absolute;left:9px;right:9px;bottom:10px}
 .tile .tn{display:block;font:700 15px/1.2 var(--font-hd);text-shadow:0 1px 3px rgba(0,0,0,.9);
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .tile .tp{display:block;font-size:11.5px;color:var(--ink2);font-variant-numeric:tabular-nums}
 .tile .tb{position:absolute;left:0;right:0;bottom:0;height:4px;background:var(--line2)}
 .tile .tb b{display:block;height:100%;background:var(--ok)}

 /* a caixa Vender */
 .vbox{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
   margin-top:24px;padding:14px 16px;border-radius:var(--r2);background:var(--ok-soft);
   border:1px solid var(--ok-line);color:var(--ink);text-decoration:none}
 .vbox:hover{border-color:var(--ok)}
 .vbox span{font-weight:600}
 .vbox small{display:block;color:var(--muted);font-weight:500;font-size:12px}
 .vbox b{color:var(--ok);font:700 22px var(--font-hd);font-variant-numeric:tabular-nums}

 /* a página de um deck */
 .volta{font-size:13px;margin-bottom:6px;text-decoration:none}
 .dkh{display:flex;gap:12px;align-items:center;margin:4px 0 6px}
 .dka{width:96px;height:70px;border-radius:9px;object-fit:cover;flex:none;background:var(--card3);
   border:1px solid var(--line)}
 span.dka{display:block}
 .dkh h2{margin:0;font-size:23px;line-height:1.15}
 .dks{color:var(--muted);font-size:12.5px;line-height:1.4}
 .pbar{display:block;height:8px;background:var(--line2);border-radius:99px;overflow:hidden;margin:12px 0 6px}
 .pbar b{display:block;height:100%;background:var(--ok);border-radius:99px}
 .kpi{display:flex;justify-content:space-between;gap:4px 12px;flex-wrap:wrap;font-size:13.5px;color:var(--ink2)}
 .kpi b{color:var(--accent);font-variant-numeric:tabular-nums}
 .kpi small{color:var(--dim)}
 .ver{margin:10px 0 2px;font-size:12.5px;color:var(--ink2);line-height:1.5}
 .ver b{color:var(--ink)}
 .ent{color:var(--ok)} .sai{color:var(--rem)}
 details.versoes{margin:2px 0 4px;font-size:12.5px}
 details.versoes summary{cursor:pointer;color:var(--ob);min-height:36px;display:inline-flex;align-items:center}
 details.versoes ol{list-style:none;margin:2px 0 6px;padding:8px 12px;background:var(--card2);
   border:1px solid var(--line);border-radius:var(--r)}
 details.versoes li{padding:5px 0;border-bottom:1px solid var(--line);color:var(--ink2)}
 details.versoes li:last-child{border-bottom:0}
 .avisov{display:flex;gap:8px;align-items:flex-start;background:var(--warn-soft);border:1px solid var(--warn-line);
   color:var(--warn-forte);border-radius:var(--r);padding:8px 12px;font-size:13px;margin:10px 0}
 .avisov small{display:block;color:var(--muted)}
 .espera{margin-top:14px}
 .espera b{display:block;color:var(--ink);font:700 16px var(--font-hd);margin-bottom:2px}
 .mv{margin-top:18px;padding:11px 13px;border-radius:var(--r);background:var(--accent-soft);
   border:1px solid var(--accent-line);color:var(--accent);font-size:13px;line-height:1.5}
 .mv b{display:block}
 .mv.ok{background:var(--ok-soft);border-color:var(--ok-line);color:var(--ok)}
 .gsub{color:var(--dim);font-size:12px;margin:-4px 0 8px}

 /* as cartas */
 .cg{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
 @media (min-width:600px){ .cg{grid-template-columns:repeat(5,minmax(0,1fr))} }
 @media (min-width:900px){ .cg{grid-template-columns:repeat(6,minmax(0,1fr));gap:8px} }
 @media (min-width:1200px){ .cg{grid-template-columns:repeat(8,minmax(0,1fr))} }
 .ct{position:relative;margin:0;aspect-ratio:146/204;border-radius:6%/4.3%;overflow:hidden;
   background:var(--sunken);border:1px solid var(--line)}
 .ct img{display:block;width:100%;height:100%;object-fit:cover}
 .ct.falta img{filter:grayscale(1) brightness(.48)}
 .ct.falta.parcial img{filter:grayscale(1) brightness(.75)}
 .ct.semimg{background:var(--card3)}
 .ct .nm{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
   padding:6px;text-align:center;font-size:11px;color:var(--ink2);line-height:1.25}
 .ct .q{position:absolute;top:4px;right:4px;z-index:2;text-decoration:none;font-size:11px;font-weight:700;
   background:rgba(0,0,0,.74);color:var(--ink);padding:0 5px;border-radius:5px;line-height:1.5}
 .ct .q small{font-size:8.5px;color:var(--muted)}
 .ct .onde{position:absolute;left:3px;top:4px;z-index:2;font-style:normal;font-size:9.5px;font-weight:600;
   background:var(--info-soft);color:var(--ob);border:1px solid var(--info-line);border-radius:4px;
   padding:0 4px;max-width:calc(100% - 34px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.5}
 .ct .onde.aqui{background:var(--ok-soft);color:var(--ok);border-color:var(--ok-line)}
 .ct em{position:absolute;left:3px;right:3px;bottom:3px;z-index:2;font-style:normal;font-size:10px;
   text-align:center;background:var(--bad-soft);color:var(--bad-ink);border:1px solid var(--bad-line);
   border-radius:4px;line-height:1.3;padding:1px 2px}
 .ct em b,.ct em span{white-space:nowrap}
 .ct em b{color:var(--bad);font-weight:700}
 .ct.foil::after{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;mix-blend-mode:screen;
   background:linear-gradient(115deg,rgba(255,255,255,0) 28%,rgba(255,255,255,.30) 44%,
   rgba(170,210,255,.22) 52%,rgba(255,220,170,.16) 58%,rgba(255,255,255,0) 72%)}

 /* Vender */
 .vtot{display:flex;justify-content:space-between;align-items:center;gap:6px 12px;flex-wrap:wrap;
   padding:14px 16px;border-radius:var(--r2);background:var(--ok-soft);border:1px solid var(--ok-line)}
 .vtot span{font-weight:600}
 .vtot small{display:block;color:var(--muted);font-weight:500;font-size:12px}
 .vtot b{color:var(--ok);font:700 26px var(--font-hd);font-variant-numeric:tabular-nums}
 ul.vls{list-style:none;margin:0;padding:0;background:var(--card);border:1px solid var(--line);border-radius:var(--r)}
 li.vl{display:grid;grid-template-columns:42px minmax(0,1fr) auto;gap:10px;align-items:center;
   padding:8px 12px;border-bottom:1px solid var(--line)}
 li.vl:last-child{border-bottom:0}
 li.vl img,li.vl .vsem{width:42px;height:59px;border-radius:3px;object-fit:cover;display:block;background:var(--sunken)}
 .vi b{display:block;font-size:14px;line-height:1.3;overflow-wrap:anywhere}
 .vi small{color:var(--dim);font-size:11.5px}
 .vn{text-align:right;font-variant-numeric:tabular-nums;font-size:12px;white-space:nowrap;color:var(--muted)}
 .vn b{display:block;color:var(--ink);font-size:14px}
 .vn .sp{color:var(--bad)}
"""
