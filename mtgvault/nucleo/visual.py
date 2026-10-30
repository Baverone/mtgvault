"""O que as páginas do núcleo partilham: o CSS, o mosaico de um deck, a carta
em imagem, a barra de progresso, o gráfico do valor e as pequenas frases. E, da
página Coleção, o mosaico de uma coleção, a carta de coleção e a tabela «A
subir».

As páginas (`nucleo_painel.py`, `nucleo_decks.py`, `nucleo_vender.py` e
`nucleo_colecoes.py`, na raiz) só montam; o desenho vive aqui para terem a mesma
cara. O que se
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
  de dois dias de valor não há linha nenhuma — diz-se porquê. (R18) O último
  ponto é o valor de hoje ao vivo, o mesmo número do topo do Painel.
- **Uma carta sem preço nunca vale 0 €**: diz «sem preço».
"""
from __future__ import annotations

import html
import re
import sqlite3
from datetime import date, timedelta

from .. import paginas, scryfall
from .. import site_shell as shell
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


def nomes_de_deck(con: sqlite3.Connection) -> dict[str, str]:
    """`{slug: nome}` para mostrar onde o deck não se vê ao lado (Vender, a
    caixa de montar). (M4, 2026-10-29) Um nome que se repete — «Affinity» no
    Pauper e no Modern, «Cloud» no cEDH e no Duel Commander — leva o formato:
    «Affinity (Modern)». Os outros ficam como estão."""
    from . import modelo                                     # noqa: PLC0415
    ds = modelo.decks(con)
    conta: dict[str, int] = {}
    for d in ds:
        conta[d["nome"]] = conta.get(d["nome"], 0) + 1
    return {d["slug"]: d["nome"] if conta[d["nome"]] == 1
            else f'{d["nome"]} ({formato(d["formato"])})' for d in ds}


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


# Um URL dentro do texto de uma fonte: só http(s) — um `javascript:` nunca casa,
# e fica texto. A pontuação final («… /lista.») não é do URL.
_URL = re.compile(r"https?://[^\s<>\"']+")


def fonte_html(fonte: str | None) -> str:
    """A fonte de uma versão (texto livre); cada link fica um link, também no
    meio do texto (M9, 2026-10-29: a vigia do MTGO escreve «MTGO · evento ·
    dia · URL»)."""
    f = (fonte or "").strip()
    if not f:
        return "sem fonte"
    out, i = [], 0
    for m in _URL.finditer(f):
        url = m.group(0).rstrip(".,;:)»")
        out.append(e(f[i:m.start()]))
        curto = url.split("://", 1)[1].rstrip("/")
        if len(curto) > 42:
            curto = curto[:40] + "…"
        out.append(f'<a href="{e(url)}" rel="noopener">{e(curto)}</a>')
        i = m.start() + len(url)
    out.append(e(f[i:]))
    return "".join(out)


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


def img_recorte(caminho: str, alt: str) -> str:
    """A `<img>` do recorte da foto dele (`assets/cartas/…`): o mesmo tamanho
    escrito e o mesmo `lazy`/`async` da imagem do Scryfall, para a grelha não
    saltar. É uma só: o recorte tem 488 px de largura, sem `srcset`."""
    return (f'<img src="{e(caminho)}" alt="{e(alt)}" loading="lazy"'
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
    cada uma ou «sem preço». Nas partilhadas, `com_onde` põe por cima disso
    onde está o monte (aqui / o nome do deck montado, com o ícone da caixa).
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
                 f' data-acab="{e(c["acabamento"] or "")}"'
                 # a carta abre a folha da edição: tem de se chegar lá com o
                 # teclado também (Enter/Espaço, no `edicao_js`)
                 ' tabindex="0" role="button" aria-haspopup="dialog"')
    recorte = c.get("recorte")
    if recorte and c["scryfall_id"]:
        # a foto dele; a oficial fica à mão em `data-oficial` para a poder ver
        img = img_recorte(recorte, c["nome"])
        dados += f' data-oficial="{e(url_carta(c["scryfall_id"], "normal"))}"'
    elif c["scryfall_id"]:
        img = img_carta(c["scryfall_id"], c["nome"])
    else:
        img = f'<span class="nm">{e(c["nome"])}</span>'
    n_val = c.get("validadas") or 0
    if n_val:
        cls.append("validada")
        cam = (f'<i class="cam" title="{n_val} validada'
               f'{"s" if n_val != 1 else ""} com foto">'
               f'{shell.icone("camara", 12)}</i>')
        img += cam
    q = f'<u class="q">{c["qtd"]}</u>'
    onde = ""
    if com_onde and c.get("onde"):
        # o NOME do deck inteiro, com o ícone da caixa à frente: «no Welder
        # Cam» numa etiqueta de uma linha saía «no We…» a 390 px
        if c["onde"] == "aqui":
            onde = '<i class="onde aqui">aqui</i>'
        else:
            onde = (f'<i class="onde" title="na caixa do {e(c["onde"])}">'
                    f'{shell.icone("caixas", 14)}{e(c["onde"])}</i>')
    falta = ""
    if c["falta"]:
        # dois pedaços que não se partem por dentro: numa carta de 85 px o
        # «€» ficava sozinho na linha de baixo
        if c["preco_un"] is None:
            preco = "sem preço"
        else:
            preco = "× " + paginas.eur(c["preco_un"]).replace(" ", " ")
        falta = (f'<em><b>falta {c["falta"]}</b> <span>{preco}</span></em>')
    # o nome entre a carta e o preço (André, 30/10/2026): numa carta a
    # cinzento ou pequena no telemóvel, a imagem sozinha não se lê. Sem
    # imagem o nome já está ao centro (`.nm`) e não se repete.
    nome = f'<i class="cn">{e(c["nome"])}</i>' if c["scryfall_id"] else ""
    return (f'<figure class="{" ".join(cls)}" title="{e(c["nome"])}"{dados}>'
            f'{img}{q}<span class="rod">{onde}{nome}{falta}</span></figure>')


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
    return (f'<a class="tile" href="{e(href)}">{img}{chips}'
            f'<span class="tx"><span class="tn">{e(d["nome"])}</span>'
            f'<span class="tp">{prog}</span></span>'
            f'{barra(est["tenho"], est["total"], "tb")}</a>')


def mosaicos(itens: list[dict], prefixo: str) -> str:
    """Os decks por formato, na ordem de `modelo.ORDEM_FORMATO` (29/10).

    Primeiro «Rotativos»: os quatro formatos lado a lado, uma coluna cada,
    porque partilham cartas (um formato sem deck fica com a coluna «sem
    deck»). Depois «Sempre montados»: um formato por linha, com os decks dele
    lado a lado. `prefixo` é o que vem antes do `#slug` (`deck.html` no
    Painel, nada na página dos decks)."""
    from .modelo import MODO_DO_FORMATO, ORDEM_FORMATO          # noqa: PLC0415

    def do_formato(f):
        return [i for i in itens if i["deck"]["formato"] == f]

    def tiles(grupo):
        return "".join(mosaico(i, f'{prefixo}#{i["deck"]["slug"]}') for i in grupo)

    out = ""
    rot = [f for f in ORDEM_FORMATO if MODO_DO_FORMATO[f] == "rotativo"]
    grupo = [i for f in rot for i in do_formato(f)]
    if grupo:
        m = [i["deck"]["nome"] for i in grupo if i["estado"]["montado"]]
        nota = (paginas.plural(len(grupo), "deck") + " · partilham cartas"
                + (f" · montado: {e(m[0])}" if m else " · nenhum montado"))
        out += (f'<h2 class="gt">Rotativos <small>{nota}</small></h2>'
                '<div class="fcols">'
                + "".join(f'<div class="fcol"><h3 class="ft">{e(formato(f))}</h3>'
                          + (tiles(do_formato(f))
                             or '<span class="tile vaz">sem deck</span>')
                          + "</div>" for f in rot) + "</div>")
    sem = [f for f in ORDEM_FORMATO if MODO_DO_FORMATO[f] == "sempre"]
    n = sum(len(do_formato(f)) for f in sem)
    if n:
        out += (f'<h2 class="gt">Sempre montados'
                f' <small>{paginas.plural(n, "deck")}</small></h2>')
        for f in sem:
            if do_formato(f):
                out += (f'<h3 class="ft">{e(formato(f))}</h3>'
                        f'<div class="tiles">{tiles(do_formato(f))}</div>')
    return out


# ---------------------------------------------------------------------------
# As coleções (página `colecoes.html`)
# ---------------------------------------------------------------------------
def variacao_serie(serie: list[tuple], hoje: str, dias: int = 30) -> dict | None:
    """A variação de uma série de `valor.serie_colecao` → `{delta, pct, desde,
    hoje}` (a forma que o `variacao_html` lê), ou `None`.

    Compara o ponto de hoje com o último ponto até `hoje − dias` (a série só
    tem um ponto por dia com dados, por isso o valor desse dia é o do último
    ponto até lá). `None` quando a série não chega a esse dia, não acaba em
    hoje, ou nesse dia havia mais cópias sem preço do que hoje (os dois totais
    já não somavam as mesmas cartas). Nunca 0 % por falta de dados.
    """
    if not serie or serie[-1][0] != hoje:
        return None
    alvo = (_dia(hoje) - timedelta(days=dias)).isoformat()
    antes = [p for p in serie if p[0] <= alvo]
    if not antes:
        return None
    agora, ref = serie[-1], antes[-1]
    if ref[2] > agora[2]:
        return None
    delta = round(agora[1] - ref[1], 2)
    pct = round(100 * delta / ref[1], 1) if ref[1] else None
    return {"delta": delta, "pct": pct, "desde": alvo, "hoje": hoje}


def visto_ha(dia: str | None, hoje: str) -> str:
    """«visto hoje» / «visto há 1 dia» / «visto há 5 dias» (o dia do último
    preço português). Sem dia, vazio."""
    if not dia:
        return ""
    n = max(0, (_dia(hoje) - _dia(dia)).days)
    return "visto hoje" if n == 0 else f"visto há {paginas.plural(n, 'dia')}"


def _pct_span(v: float | None, dias: int) -> str:
    if v is None:
        return f'<span class="sv0">sem histórico {dias} d</span>'
    cls = " sobe" if v > 0 else " desce" if v < 0 else ""
    return f'<span class="sv{cls}">{paginas.pct(v)} {dias} d</span>'


def variacoes_html(var30: float | None, var90: float | None) -> str:
    """«+25,0 % 30 d · +100,0 % 90 d»; sem as duas, só «sem histórico»."""
    if var30 is None and var90 is None:
        return '<span class="sv0">sem histórico</span>'
    return _pct_span(var30, 30) + " · " + _pct_span(var90, 90)


def valor_colecao_texto(est: dict) -> str:
    """O valor de hoje de uma coleção: sem cópias é 0 €; com cópias todas sem
    preço é «sem preço» (nunca um 0 € inventado)."""
    if est["valor_eur"] == 0 and est["tenho"] and est["sem_preco"]:
        return "sem preço"
    return paginas.eur(est["valor_eur"])


def _arte_tile(sid: str | None) -> str:
    return (f'<img src="{url_arte(sid)}" alt="" loading="lazy" decoding="async"'
            f' width="626" height="457">' if sid else "")


def mosaico_colecao(item: dict, href: str) -> str:
    """O botão de uma coleção: arte, nome, «tenho X de Y» (aberta: «N cartas»),
    valor de hoje e a variação a 30 e a 90 dias (`item["var30"]`/`["var90"]`,
    as de `variacao_serie`; `None` é «sem histórico»)."""
    est = item["estado"]
    if est["tipo"] == "fechada":
        prog = f'tenho {est["tenho"]} de {est["total"]}'
        bar = barra(est["tenho"], est["total"], "tb")
    else:
        prog, bar = paginas.plural(est["tenho"], "carta"), ""
    var = variacoes_html(item["var30"], item["var90"])
    return (f'<a class="tile" href="{e(href)}">{_arte_tile(item["arte"])}'
            f'<span class="tx"><span class="tn">{e(est["nome"])}</span>'
            f'<span class="tp">{prog}</span>'
            f'<span class="tp">{valor_colecao_texto(est)}</span>'
            f'<span class="tp">{var}</span></span>{bar}</a>')


def mosaico_subir(linhas: list[dict], href: str, minimo: float) -> str:
    """O botão de «A subir»: quantas cartas e a maior subida a 30 dias; a arte
    é a carta que mais subiu."""
    com_var = [l for l in linhas if l["var30"] is not None]
    if linhas:
        resumo = [f'{paginas.plural(len(linhas), "carta")} acima de '
                  f'{paginas.eur(minimo, 0)}']
        if com_var:
            resumo.append(f'a maior: {e(com_var[0]["nome"])} '
                          f'{paginas.pct(com_var[0]["var30"])} em 30 d')
    else:
        resumo = [f'nenhuma carta acima de {paginas.eur(minimo, 0)}']
    arte = (com_var or linhas or [{}])[0].get("scryfall_id")
    spans = "".join(f'<span class="tp">{r}</span>' for r in resumo)
    return (f'<a class="tile" href="{e(href)}">{_arte_tile(arte)}'
            f'<span class="tx"><span class="tn">A subir</span>{spans}</span></a>')


def _preco_carta(c: dict, hoje: str) -> str:
    if c["preco_un"] is None:
        return '<b class="cp">sem preço</b>'
    visto = visto_ha(c.get("preco_visto_em"), hoje)
    return (f'<b class="cp">{paginas.eur(c["preco_un"])}</b>'
            + (f' <small>{visto}</small>' if visto else ""))


def carta_colecao(c: dict, *, slug: str, hoje: str, max_joga: int = 3) -> str:
    """Uma carta da coleção: a imagem de `carta` (a cores a que tem, a cinzento
    a que falta, «tenho / meta» no canto, o recorte dele se está validada) e,
    por baixo, o preço (nas portuguesas com «visto há N dias»), a variação a 30
    e a 90 dias, onde se joga e «quero vender». Numa aberta (`meta` `None`) o
    canto é só a quantidade e nada fica a cinzento."""
    meta = c["meta"]
    img = carta(dict(c, qtd=f'{c["tenho"]} / {meta}' if meta is not None
                     else c["tenho"], falta=c["falta"] or 0), slug=slug)
    joga = c["joga"]
    etiquetas = "".join(f'<i class="jg">{e(j)}</i>' for j in joga[:max_joga])
    if len(joga) > max_joga:
        etiquetas += f'<i class="jg mais">+{len(joga) - max_joga}</i>'
    info = (f'<div class="ci"><span>{_preco_carta(c, hoje)}</span>'
            f'<span class="cv">{variacoes_html(c["var30"], c["var90"])}</span>')
    if etiquetas:
        info += f'<span class="cj">{etiquetas}</span>'
    if c["vender"]:
        info += '<span class="cj"><i class="vd">quero vender</i></span>'
    # o `.ci` abriu-se em `info`: fecham-se os dois
    return f'<div class="cc">{img}{info}</div></div>'


def grelha_colecao(cartas: list[dict], *, slug: str, hoje: str) -> str:
    return ('<div class="cg ccg">'
            + "".join(carta_colecao(c, slug=slug, hoje=hoje) for c in cartas)
            + "</div>")


def _pct_td(v: float | None) -> str:
    if v is None:
        return '<span class="sv0">—</span>'
    cls = " sobe" if v > 0 else " desce" if v < 0 else ""
    return f'<span class="sv{cls}">{paginas.pct(v)}</span>'


def tabela_subir(linhas: list[dict], minimo: float) -> str:
    """«A subir»: uma linha por carta (já ordenada por `cotacoes.a_subir`) com o
    preço de hoje, a variação a 30 e a 90 dias, se ele a tem e onde se joga.
    Números, não recomendações."""
    if not linhas:
        return (f'<p class="vazio">Nenhuma carta com preço de hoje acima de '
                f'{paginas.eur(minimo, 0)}.</p>')
    corpo = ""
    for l in linhas:
        acab = " · foil" if l["acabamento"] == "foil" else ""
        tem = f'tens {l["tenho"]}' if l["tenho"] else "não tens"
        joga = ", ".join(e(j) for j in l["joga"]) if l["joga"] else "não joga"
        corpo += (
            '<tr><td><span class="sn">'
            f'<img src="{url_carta(l["scryfall_id"])}" alt="" loading="lazy"'
            ' decoding="async" width="34" height="48">'
            f'<span><b>{e(l["nome"])}</b>'
            f'<small>{e(str(l["set_code"]).upper())}{acab}</small>'
            f'<small>{tem} · {joga}</small></span></span></td>'
            f'<td class="n">{paginas.eur(l["preco"])}</td>'
            f'<td class="n">{_pct_td(l["var30"])}</td>'
            f'<td class="n">{_pct_td(l["var90"])}</td></tr>')
    return ('<table class="sub"><thead><tr><th>Carta</th><th>Preço</th>'
            '<th>30 d</th><th>90 d</th></tr></thead>'
            f'<tbody>{corpo}</tbody></table>')


# ---------------------------------------------------------------------------
# O valor: variação do mês e o gráfico
# ---------------------------------------------------------------------------
def _tudo_zero(serie) -> bool:
    """Sem nada marcado, a série é uma fila de 0 € (o inventário de hoje aos
    preços de cada dia): uma linha deitada no zero não diz nada."""
    return all(not p[1] for p in serie)


def variacao_html(v: dict | None) -> str:
    """A variação do topo do Painel, a de `valor.variacao_mes` (R18: o que tens
    hoje, aos preços de hoje e aos de há um mês). `None` é «—»."""
    if v is None:
        return ('<span class="vvar" title="ainda não há um dia comparável">'
                '—</span>')
    dias = _dia(v["hoje"]).toordinal() - _dia(v["desde"]).toordinal()
    quando = "num mês" if 28 <= dias <= 32 else f"desde {data_pt(v['desde'])[:5]}"
    seta, cls = (("▲", " sobe") if v["delta"] > 0 else
                 ("▼", " desce") if v["delta"] < 0 else ("=", ""))
    pct = f" ({paginas.pct(v['pct'])})" if v["pct"] is not None else ""
    return (f'<span class="vvar{cls}">{seta} {paginas.eur(abs(v["delta"]))}'
            f'{pct} {quando}</span>')


def _svg(pontos: list[tuple], rotulo: str) -> str:
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


def grafico(serie: list[tuple]) -> str:
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


# O router de `#` das páginas de uma só página (decks e coleções): mostra a
# `<section class="dk">` do `#` e esconde as outras; sem `#`, o `#todos`.
# As secções procuram-se a cada chamada e não uma vez: no modo de edição o
# `<main>` é trocado depois de cada gravação (`edicao_js`), e o evento
# `nuc:atualizada` volta a mostrar a secção do `#` SEM saltar para o topo — ele
# está a marcar cartas a meio da página.
JS_ROTA = r"""
(function(){
  var titulo = document.title;
  function mostra(ev){
    var todos = document.getElementById('todos'),
        secs = document.querySelectorAll('section.dk');
    var h = '';
    try { h = decodeURIComponent((location.hash || '').slice(1)); } catch (e) {}
    var alvo = null, i;
    for (i = 0; i < secs.length; i++) if (secs[i].id === h) alvo = secs[i];
    for (i = 0; i < secs.length; i++) secs[i].hidden = secs[i] !== alvo;
    if (todos) todos.hidden = !!alvo;
    var nome = alvo && alvo.getAttribute('data-nome');
    document.title = nome ? nome + ' · ' + titulo : titulo;
    if (alvo && !(ev && ev.type === 'nuc:atualizada')) window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', mostra);
  document.addEventListener('nuc:atualizada', mostra);
  mostra();
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
 .nuc h3.gs{font-size:13px;color:var(--ink2);margin:16px 0 8px;font-weight:600;
   display:flex;align-items:baseline;gap:8px}
 .nuc h3.gs small{color:var(--muted);font:500 12px var(--font)}
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
 .nuc h3.ft{font:700 15px var(--font-hd);color:var(--ink);margin:16px 0 8px}
 .fcols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 10px;align-items:start}
 @media (min-width:900px){ .fcols{grid-template-columns:repeat(4,minmax(0,1fr))} }
 .fcols h3.ft{margin-top:6px}
 .fcol{display:grid;gap:10px;align-content:start}
 .fcol h3.ft{margin-bottom:-2px}
 .tile.vaz{display:flex;align-items:center;justify-content:center;background:none;
   border-style:dashed;color:var(--dim);font-size:12.5px}
 .tile.vaz::before{display:none}
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
 .ct .rod{position:absolute;left:3px;right:3px;bottom:3px;z-index:2;display:flex;flex-direction:column;gap:2px}
 .ct .rod:empty{display:none}
 .ct .onde{display:flex;align-items:center;justify-content:center;gap:2px;font-style:normal;font-size:9.5px;
   font-weight:600;background:var(--info-soft);color:var(--ob);border:1px solid var(--info-line);border-radius:4px;
   padding:1px 3px;line-height:1.2;text-align:center;overflow-wrap:anywhere}
 .ct .onde svg.ico{width:11px;height:11px;flex:none}
 .ct .onde.aqui{background:var(--ok-soft);color:var(--ok);border-color:var(--ok-line)}
 .ct .cn{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
   font-style:normal;font-size:10px;font-weight:600;line-height:1.25;text-align:center;
   background:rgba(0,0,0,.74);color:var(--ink);border-radius:4px;padding:1px 3px;overflow-wrap:anywhere}
 .ct em{display:block;font-style:normal;font-size:10px;
   text-align:center;background:var(--bad-soft);color:var(--bad-ink);border:1px solid var(--bad-line);
   border-radius:4px;line-height:1.3;padding:1px 2px}
 .ct em b,.ct em span{white-space:nowrap}
 .ct em b{color:var(--bad);font-weight:700}
 .ct.validada{border-color:var(--ok-line)}
 .ct .cam{position:absolute;top:4px;left:4px;z-index:2;display:flex;align-items:center;justify-content:center;
   width:18px;height:18px;border-radius:5px;background:rgba(0,0,0,.74);color:var(--ok)}
 .ct .cam svg.ico{width:12px;height:12px}
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

 /* as coleções: o mosaico leva quatro linhas; a variação quebra se for preciso */
 .tile .sv0{color:var(--ink2)}
 .cg.ccg{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px 6px}
 @media (min-width:600px){ .cg.ccg{grid-template-columns:repeat(4,minmax(0,1fr))} }
 @media (min-width:900px){ .cg.ccg{grid-template-columns:repeat(5,minmax(0,1fr));gap:12px 8px} }
 @media (min-width:1200px){ .cg.ccg{grid-template-columns:repeat(6,minmax(0,1fr))} }
 .cc{min-width:0}
 .ci{display:flex;flex-direction:column;gap:3px;padding:5px 1px 0;font-size:11px;line-height:1.3;color:var(--ink2)}
 .ci .cp{font:700 13px var(--font-hd);color:var(--ink);white-space:nowrap;font-variant-numeric:tabular-nums}
 .ci small{color:var(--dim);font-size:10.5px}
 .ci .cv{font-variant-numeric:tabular-nums}
 .ci .cj{display:flex;flex-wrap:wrap;gap:3px}
 .sv.sobe{color:var(--ok)} .sv.desce{color:var(--bad)} .sv0{color:var(--dim)}
 .jg{font-style:normal;font-size:10px;font-weight:600;line-height:1.3;padding:0 4px;border-radius:4px;
   background:var(--info-soft);color:var(--ob);border:1px solid var(--info-line);overflow-wrap:anywhere}
 .jg.mais{background:none;color:var(--muted);border-color:var(--line2)}
 .vd{font-style:normal;font-size:10px;font-weight:700;line-height:1.3;padding:0 4px;border-radius:4px;
   background:var(--warn-soft);color:var(--warn-forte);border:1px solid var(--warn-line)}

 /* A subir */
 table.sub{width:100%;border-collapse:collapse;font-size:13px}
 table.sub th{text-align:right;color:var(--muted);font-size:11px;text-transform:uppercase;
   letter-spacing:.06em;font-weight:700;padding:6px 6px;border-bottom:1px solid var(--line2)}
 table.sub th:first-child{text-align:left}
 table.sub td{padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:middle}
 table.sub td.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
 table.sub .sn{display:flex;gap:8px;align-items:center;min-width:0}
 table.sub .sn img{width:34px;height:48px;border-radius:3px;object-fit:cover;flex:none;background:var(--sunken)}
 table.sub .sn b{display:block;font-size:13.5px;line-height:1.25;overflow-wrap:anywhere}
 table.sub .sn small{display:block;color:var(--dim);font-size:11px;line-height:1.3}
"""
