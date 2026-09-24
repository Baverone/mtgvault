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
    `stock.stock_list`). São as três caixas do `colecao_config.json → caixas`
    que ainda estão sem `ref` — a pergunta "que deck meto nesta caixa?".
  * **Modern** — não há nada a escolher: o deck está escolhido (UW Oswald) e
    mostra-se a caixa do loadout, com as variantes marcadas.
  * **Pioneer, desde 2026-09-21** — o mesmo que o Modern, por decisão dele
    (*"Pioneer apenas Greasefang e jeskai control"*): as duas caixas, sem
    top-N. É `colecao_config.json → formatos_decididos` (`formatos_decididos()`
    / `secoes()`), não código: o top-N fica pronto para o dia em que ele tirar
    o formato de lá.
  * **Premodern** — o **top-10 de representação** e o **top-5 de combo** do
    formato (André, 2026-09-08), cada um com a cobertura medida sobre o que
    SOBRA: as cópias PT que nenhuma caixa levou. É a pergunta *"que mais posso
    montar com o que está na gaveta?"*, e a resposta a partir de
    `premodern.sugerir_a_partir_de_pct` (50 %) traz os botões *"vou montar
    este"* e *"não quero este"*. As caixas que ele já tem aparecem marcadas —
    o UW Replenish e a Enchantress (os alvos de consenso de 2026-09-07) entre
    elas, e o Stiflenought, que segue a lista do Luffy.

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
from mtgvault import site_shell as shell  # noqa: E402

# Que formatos aparecem e COMO. É a ordem do André, tal como ele a deu:
#   'top'    — os N arquétipos que ele está mais perto de concluir (os slots do
#              loadout que estão por confirmar: Standard, Pioneer, Legacy);
#   'caixas' — o deck já escolhido, tal como está no loadout (Modern);
#   'premodern' — o top-10 de representação + o top-5 de combo, com a cobertura
#              medida sobre o que SOBRA e o botão de sugerir/recusar (André,
#              2026-09-08). Era 'alvos' — só o UW Replenish e a Enchantress — e
#              essa vista não respondia à pergunta nova: *"o que é que eu monto
#              com o que não está em caixa nenhuma?"*.
SECOES = [
    ("standard", "Standard", "top"),
    ("pioneer", "Pioneer", "top"),
    ("legacy", "Legacy", "top"),
    ("modern", "Modern", "caixas"),
    ("premodern", "Premodern", "premodern"),
]

# Mínimo de listas para um arquétipo entrar no ranking. Abaixo disto a lista de
# consenso é ruído de um ou dois resultados soltos.
MIN_LISTS = 8



def top_n() -> int:
    """Quantos decks por formato. André, 2026-09-07: *"o top-3 decks que estou
    mais perto de concluir"*. Configurável em `colecao_config.json`."""
    try:
        return max(1, int(sources.config().get("metagame_top_n") or 3))
    except (TypeError, ValueError):
        return 3


def formatos_decididos() -> list[str]:
    """Os formatos em que ele já DECIDIU os decks — sem top-N, sem candidatos,
    sem «vou montar este».

    André, 2026-09-21, à letra: *"Pioneer apenas Greasefang e jeskai control"*.
    A decisão de 2026-09-07 (ver o top-3 mais perto de concluir e escolher) fica
    para os formatos que não estão aqui — Standard e Legacy —; para o Pioneer
    é substituída por esta. Vive em `colecao_config.json → formatos_decididos`
    e não no código: tirar o formato da lista devolve-lhe os candidatos, e o
    código do top-N não se apaga (apagar é decisão dele).
    """
    v = sources.config().get("formatos_decididos")
    return [str(f).lower() for f in v] if isinstance(v, list) else []


def secoes() -> list[tuple[str, str, str]]:
    """As `SECOES` com o modo EFECTIVO: um formato de `top` que ele já decidiu
    passa a `caixas` — mostra as caixas dele, como o Modern, e mais nada. O
    `SECOES` fica como a ordem que ele deu em 2026-09-07; o que muda por
    formato é config."""
    dec = set(formatos_decididos())
    return [(f, t, "caixas" if modo == "top" and f in dec else modo)
            for f, t, modo in SECOES]


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


_img_map = paginas.img_map      # era uma cópia à letra da do `deckboxes.py`


def _eur(v):
    return paginas.eur(v) if v else "—"


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
    # As três parcelas do "noutra caixa" (André, 2026-09-08): dentro de uma
    # caixa montada, na gaveta destinada a outra, ou ainda por comprar. Só a
    # primeira é uma ida a outra caixa.
    parcelas = {q: sum(sum((m.get(f"noutra_{q}") or {}).values()) for m in nb)
                for q in ("montada", "reservada", "futura")}
    comprar = sum(m["comprar"] for m in nb)
    custo = round(sum(m["cost"] or 0 for m in nb), 2)
    # Quantas cópias a comprar não têm preço na base. Sem isto o *"fechar por
    # 162,80 €"* passava por uma conta fechada quando quatro das cartas da lista
    # entravam a 0 € — a Deckboxes já dizia *"no mínimo — N sem preço"* e esta
    # página não. O mesmo número com duas honestidades diferentes.
    sem_preco = sum(m["comprar"] for m in nb
                    if m["comprar"] > 0 and m.get("unit") is None)
    return {"need": need, "got": got, "noutra": noutra, "comprar": comprar,
            "nmont": parcelas["montada"], "nres": parcelas["reservada"],
            "nfut": parcelas["futura"], "sem_preco": sem_preco,
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
    # O NOME no `alt` (2026-09-09): estava vazio e a imagem é o conteúdo, não
    # decoração. Numa rede fraca — que é onde ele está, à frente da estante — a
    # grelha virava uma parede de quadrados sem nada, e o nome só aparecia ao
    # parar o dedo em cima (o `title`). É o que a `deckboxes` já fazia.
    img = (f'<img loading="lazy" src="{_art(sid)}" alt="{html.escape(nm)}">'
           if sid else '<div class="noimg"></div>')
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
            # ONDE A CARTA ESTÁ (André, 2026-09-08): a frase vem do Python, e
            # distingue *"em UW Replenish"* (está lá dentro) de *"na Colecção —
            # destinada ao UW Replenish"* (a caixa ainda não está montada).
            # Composta aqui a partir do `noutra`, dizia sempre a primeira.
            onde = "; ".join(loadout.onde_esta(m))
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
    """'Onde está a carta' — em TRÊS blocos, porque são três sítios.

    André, 2026-09-08, à letra: *"De todas as cartas, só o Stiflenought está em
    deckbox; o resto ainda nada está em deckbox — e ainda estás a assumir que há
    cartas que já estão nas deckboxes dos decks."* Um bloco só, intitulado *"ir
    buscar a outra caixa"*, mandava-o abrir caixas que não existem na estante: a
    cópia está na `Colecção`, só está PROMETIDA a outra caixa. Quem parte e quem
    escreve a frase é o `loadout` — a página não recompõe isto a partir do
    `noutra`, que é a caixa destino e não o sítio.
    """
    out = ""
    for qual, titulo in (
            ("montada", "📦 ir buscar a outra caixa"),
            ("reservada", "🗂️ na gaveta, destinadas a outra caixa"),
            ("futura", "🛒 outra caixa vai comprá-las")):
        rows = sorted((m for m in linhas if m.get(f"noutra_{qual}")),
                      key=lambda m: (-sum(m[f"noutra_{qual}"].values()), m["nm"]))
        if not rows:
            continue
        n = sum(sum(m[f"noutra_{qual}"].values()) for m in rows)
        itens = "".join(
            f'<li>{html.escape(m["nm"])} — '
            + html.escape("; ".join(loadout.onde_esta(m, qual)))
            + (f' <span class="dim">(comprar mais {m["comprar"]})</span>'
               if m["comprar"] else "") + "</li>" for m in rows)
        out += (f'<div class="onde"><b>{titulo} — {paginas.plural(n, "cópia")}</b>'
                f'<ul>{itens}</ul></div>')
    return out


def _wantlist(linhas, marca=""):
    """Só o que é MESMO compra (`comprar`), no formato que o Cardmarket aceita."""
    ordem = sorted((m for m in linhas if m["comprar"] > 0), key=lambda m: m["nm"])
    if not ordem:
        return '<div class="ok">nada a comprar ✓</div>'
    # «SÓ FOIL» SÓ QUANDO EXISTE EM FOIL (2026-09-19): a linha de uma carta que
    # nunca saiu em foil di-lo, para a marca «FOIL» do bloco não valer para ela.
    itens = "".join(f'<li><b>{m["comprar"]}×</b> {html.escape(m["nm"])}'
                    + ('<small class="dim"> nonfoil — nunca saiu em foil</small>'
                       if not m.get("foil_existe", True) else "")
                    + f'<span class="pz">{_eur(m["cost"])}</span></li>' for m in ordem)
    txt = "\n".join(f'{m["comprar"]} {m["nm"]}' for m in ordem)
    extra = f' <span class="mrk">{marca}</span>' if marca else ""
    return (f'<div class="faltas"><div class="flh">🛒 Comprar{extra}'
            f'<span class="dim">{paginas.plural(len(ordem), "carta")}</span>'
            f'<button class="cpbtn" onclick="cp(this)">copiar</button></div>'
            f'<ul class="fl">{itens}</ul>'
            f'<textarea class="cmk" readonly>{html.escape(txt)}</textarea></div>')


def _premodern_acts_html(d, editable):
    """Os botões de uma linha do ranking de Premodern — só no MODO EDIÇÃO.

    São dois e são diferentes: *"vou montar este"* cria uma caixa nova (o
    arquétipo passa a ser um deck dele, com a lista congelada e datada) e
    *"não quero este"* recusa a sugestão — e essa recusa **liberta as cartas
    dela para a venda** no mesmo dia. Por isso a segunda diz o que faz: um botão
    que manda vender cartas não pode chamar-se só "não".
    """
    if not editable:
        return ""
    nome = html.escape(d["nome"])
    # O `id` estável vai em TODOS os botões: é por ele que a recusa e a escolha
    # se guardam. O `nome` continua a ir a par — é o que fica escrito ao lado no
    # config, para ele reconhecer a linha —, mas já não é a chave.
    ident = html.escape(d.get("id") or "")
    if d["estado"] == "caixa":
        return ""
    if d["estado"] == "recusada":
        return (f'<div class="acts"><button class="btn" data-act="pm-aceitar" '
                f'data-nome="{nome}" data-id="{ident}" '
                f'aria-label="Voltar a considerar {nome}">'
                f'↩ Voltar a considerar</button></div>')
    montar = (f'<button class="btn pri" data-act="pm-montar" data-nome="{nome}" '
              f'data-aid="{d["archetype_id"]}" data-id="{ident}" '
              f'aria-label="Vou montar {nome} numa caixa nova">'
              f'✔ Vou montar este</button>')
    recusar = (f'<button class="btn" data-act="pm-recusar" data-nome="{nome}" '
               f'data-id="{ident}" '
               f'aria-label="Não quero {nome} — as cartas dele vão para a venda">'
               f'✕ Não quero este</button>')
    return f'<div class="acts">{montar}{recusar}</div>'


def _escolher_html(d, editable):
    """O botão *"vou montar este"* — só no MODO EDIÇÃO (`python webapp.py`).

    No site publicado os endpoints de escrita não existem, e um botão que não faz
    nada é pior do que não haver botão nenhum (é a mesma regra do `deckboxes`).
    Lá, o que se vê é o crachá *"✔ escolhido em <data>"*.

    No ranking de Premodern os botões são outros (criam uma caixa, ou recusam a
    sugestão): despacha-se para lá, para o `_deck_html` continuar a ser um só.
    """
    if d.get("pm"):
        return _premodern_acts_html(d, editable)
    if not editable or not d.get("slot"):
        return ""
    if d.get("escolhido"):
        return (f'<div class="acts"><button class="btn" data-act="desmarcar" '
                f'data-slot="{html.escape(d["slot"])}" '
                f'aria-label="Deixar de montar {html.escape(d["nome"])}">'
                f'✕ Já não vou montar este</button></div>')
    return (f'<div class="acts"><button class="btn pri" data-act="escolher" '
            f'data-slot="{html.escape(d["slot"])}" '
            f'data-aid="{d["archetype_id"]}" '
            f'aria-label="Vou montar {html.escape(d["nome"])} nesta caixa">'
            f'✔ Vou montar este</button></div>')


def _deck_html(d, imgs, editable=False):
    r = _resumo(d["linhas"])
    badges = "".join(f'<span class="bdg {c}">{t}</span>' for c, t in d.get("badges", []))
    # A percentagem do cabeçalho é a de QUANTO ELE TEM — livre mais o que está
    # noutra caixa, porque essa também é dele e vai-se lá buscar. É a mesma que
    # ordena o top-N; mostrar aqui a outra (só o livre) fazia a lista aparecer
    # desordenada sem explicação. A repartição fica na linha de baixo.
    #
    # No PREMODERN o número que decide se a lista é uma sugestão é o de COMO
    # PRINCIPAL (André, 2026-09-08: *"tens que ver se a % desses decks aumentaria
    # se eles fossem o principal"*) — as caixas de Premodern partilham cartas. É
    # esse que vem à frente, com o do que sobra ao lado: mostrar um limiar de
    # 50 % ao lado de um número que não é o que ele mede era a página a
    # contradizer-se, e foi o que aconteceu quando o daqui era só o livre.
    # Desde 2026-09-19 (*"cada deck deverá ter as suas próprias cartas
    # dentro"*) nenhuma caixa empresta: a "como principal" é igual à do que
    # está livre, e o "ir buscar" é zero por regra. Mostra-se uma percentagem
    # só; o "ir buscar" só se imprime se um dia deixar de ser zero.
    cov = (f'{r["pct"]}% com o que está livre'
           if d.get("pm") else f'{r["tenho"]}/{r["need"]} · {r["pct_tenho"]}%')
    return (
        f'<details class="deck"{" open" if d.get("aberto") else ""}><summary>'
        f'<b>{html.escape(d["nome"])}</b>'
        f'<span class="cov">{cov}</span>'
        f'<span class="src">{html.escape(d["sub"])}</span></summary>'
        f'{_bar(r["pct"], d["pct_principal"] if d.get("pm") else r["pct_tenho"])}'
        f'<div class="badges">{badges}</div>'
        f'<div class="meta">'
        f'<span>tenho livre <b>{r["got"]}</b></span>'
        + (f'<span class="ob">ir buscar a outra caixa <b>{r["nmont"]}</b></span>'
           if r["nmont"] else "")
        + (f'<span class="ob">na gaveta, p/ outra caixa <b>'
           f'{r["nres"] + r["nfut"]}</b></span>' if r["nres"] + r["nfut"] else "")
        + f'<span>comprar <b>{r["comprar"]}</b></span>'
        f'<span>fechar por <b>{_eur(r["custo"])}</b>'
        + (f'<i class="semp" title="Estas cópias não têm preço na base e contam '
           f'como 0 €.">no mínimo — {r["sem_preco"]} sem preço</i>'
           if r["sem_preco"] else "") + '</span></div>'
        f'<div class="cards">{_grid(d["linhas"], imgs)}</div>'
        f'{_onde_html(d["linhas"])}{_wantlist(d["linhas"], d.get("marca", ""))}'
        f'{_escolher_html(d, editable)}'
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
        # As regras de material do grupo de formato, todas (ver `deckboxes`). A
        # classe vem do `rotulo_material`: decidi-la aqui com `"foil" in txt`
        # pintava de dourado a caixa que é *"só nonfoil"*.
        for ico, txt, cls in loadout.rotulo_material(s):
            badges.append((cls, f"{ico} {txt}"))
        if s.get("so_de_variante"):
            badges.append(("", f'⇄ {len(s["so_de_variante"])} cartas só de variante'))
        out.append({"nome": s["nome"], "sub": s["nota"], "badges": badges,
                    "linhas": s["have"] + s["missing"],
                    "marca": loadout.marca_wantlist(s)})
    return out


ESTADO_PM = {
    "caixa": ("ok", "🧰 já é uma caixa tua"),
    "sugerida": ("ok", "💡 sugerido — montar?"),
    "recusada": ("", "✕ recusado"),
    "abaixo": ("", "abaixo do limiar"),
}


def _decks_premodern(res):
    """O ranking de Premodern: top-10 de representação + top-5 de combo.

    André, 2026-09-08: *"se o deck for top-10 de representação ou top-5 decks
    combo do formato, sugere a lista para montar o deck caso eu tenha pelo menos
    50 % das cartas"*. A conta vive no `mtgvault.premodern` e chega aqui feita —
    esta página desenha, não decide.

    Substituiu a secção que mostrava só os dois alvos de consenso (o UW Replenish
    e a Enchantress). Esses continuam cá: são duas das caixas, e aparecem com o
    crachá *"já é uma caixa tua"*.
    """
    pm = res.get("premodern") or {}
    out = []
    for c in pm.get("elegiveis") or []:
        cls, txt = ESTADO_PM.get(c["estado"], ("", c["estado"]))
        badges = [(cls, txt)]
        if c["estado"] == "caixa" and c.get("caixa_nome"):
            badges = [(cls, f'🧰 {c["caixa_nome"]}')]
        if c["estado"] == "recusada":
            badges = [(cls, f'✕ recusado em {c["recusada_em"]}')]
        if c["combo"]:
            badges.append(("fo", f'🧩 {c["grau"]}'))
        badges.append(("", "🔟 top de representação" if c["top"]
                       else "🎯 top de combo"))
        badges.append(("pt", "🇵🇹 só PT · ≤SCG"))
        out.append({
            "nome": c["nome"], "sub": f'{c["n_lists"]} listas que contam · '
                                      f'{c["subtitulo"]}',
            "badges": badges, "linhas": c["linhas"], "marca": "PT",
            "pm": True, "estado": c["estado"],
            "id": c["id"],
            "archetype_id": c["archetype_id"], "pct_total": c["pct_total"],
            # As duas percentagens que a página mostra lado a lado: a de COMO
            # PRINCIPAL (a que decide o limiar) e a do que sobra (a que explica
            # quantas cartas viriam emprestadas das outras caixas de Premodern).
            "pct_principal": c["pct_principal"],
            "tenho_principal": c["tenho_principal"]})
    return out


def _e_lista(nomes) -> str:
    """`["A", "B", "C"]` → `"A, B e C"` (o rodapé)."""
    nomes = list(nomes)
    if not nomes:
        return "—"
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def formatos_top() -> list[str]:
    """Os formatos cuja secção é um TOP-N — os que têm "vou montar este".

    Lê o modo EFECTIVO (`secoes()`): um formato decidido (2026-09-21, o
    Pioneer) não entra, e é por aqui que a Deckboxes (`_candidatos`) e o
    `webapp` deixam de lhe oferecer candidatos — uma lista só, nos três sítios.
    """
    return [f for f, _t, modo in secoes() if modo == "top"]


def slot_do_formato(slots, fmt) -> dict | None:
    """A caixa do loadout deste formato (a primeira pela ordem da alocação).

    É nela que o botão *"vou montar este"* escreve. Um formato sem caixa não tem
    botão: escolher um deck para uma caixa que não existe não quer dizer nada.
    """
    return next((s for s in slots if s.get("formato") == fmt), None)


def candidatos(con, fmt, res, n=None):
    """Os N arquétipos que ele está mais perto de concluir, com lista de consenso.

    É a resposta a *"que deck é que eu meto nesta caixa?"*, e é a mesma lista nos
    dois sítios onde ele decide: a secção do formato no `metagame.html` e a aba
    da caixa no `deckboxes.html`. Uma segunda cópia deste cálculo era o padrão do
    `event_tier` outra vez — duas páginas a dizerem números diferentes.

    Cada entrada traz o `nome` legível (cores + carta-chave, ou o nome próprio),
    o `subtitulo` com o par de cartas distintivas, e se é **o escolhido** desta
    caixa (`escolhido` / `escolhido_em`).
    """
    n = n if n is not None else top_n()
    slot = slot_do_formato(res["slots"], fmt)
    escolhido = (slot or {}).get("archetype_id")
    df = mc._format_df(con, fmt)
    tcache = {}
    out = []
    for r in loadout.foil_report(con, fmt, top=n, min_lists=MIN_LISTS, res=res):
        # Sem `html.escape` aqui: quem escapa é quem desenha, e escapar duas
        # vezes punha "It&#x27;ll Quench Ya!" à vista na página.
        nome = mc._name_for(con, r["archetype_id"], df, tcache)
        par = mc._distinctive_name(con, r["archetype_id"], df, tcache)
        eu = escolhido is not None and escolhido in r["ids"]
        out.append({
            "nome": nome, "subtitulo": par, "linhas": r["linhas"], "marca": "FOIL",
            "archetype_id": r["archetype_id"], "n_lists": r["n_lists"],
            "formato": fmt, "slot": (slot or {}).get("slot"),
            "escolhido": eu,
            "escolhido_em": (slot or {}).get("escolhido_em") if eu else None,
            "sub": f'{r["n_lists"]} listas que contam · {par}',
            "badges": [("fo", "✨ só foil"), ("", "🧩 lista de consenso")]})
    return out


def _decks_do_topo(con, fmt, res, n):
    """O top-N do formato, já com os crachás de escolhido/alternativa."""
    decks = candidatos(con, fmt, res, n)
    for d in decks:
        if d["escolhido"]:
            d["badges"] = [("ok", f'✔ escolhido em {d["escolhido_em"] or "?"}')
                           ] + d["badges"]
        elif any(x["escolhido"] for x in decks):
            d["badges"] = [("", "alternativa")] + d["badges"]
    return decks


def build(con, out_path=None, editable=False):
    out = Path(out_path) if out_path else (ROOT / "metagame.html")
    out.write_text(html_page(con, editable=editable), encoding="utf-8")
    return out


def html_page(con, editable=False, token="", ligacao=None) -> str:
    """A página como texto — é o que o `webapp.py` serve sem escrever no disco.

    Com `editable`, cada deck do top-N ganha o botão *"vou montar este"*: é onde
    ele decide que deck vai para a caixa que está por escolher (André,
    2026-09-07, 19:00). O ficheiro publicado é o mesmo, sem os botões.
    """
    n = top_n()
    # `report` e não `allocate`: a secção do Premodern precisa do ranking de
    # sugestões, que vive no relatório (`res["premodern"]`) para a página e as
    # Deckboxes dizerem o mesmo número. Calculá-lo aqui à parte era a segunda
    # opinião do costume.
    res = loadout.report(con)

    data, names = [], set()
    decididos = set(formatos_decididos())
    for fmt, titulo, modo in secoes():
        if modo == "top":
            decks = _decks_do_topo(con, fmt, res, n)
            escolhido = next((d for d in decks if d["escolhido"]), None)
            caixa = slot_do_formato(res["slots"], fmt)
            lead = (f'Os <b>{n}</b> arquétipos deste formato que estás mais perto de '
                    f'concluir, com a lista de consenso de cada um. É a pergunta '
                    f'"que deck meto na caixa <b>{html.escape((caixa or {}).get("nome") or fmt)}</b>?".')
            if escolhido:
                lead += (f' Escolheste o <b>{html.escape(escolhido["nome"])}</b> em '
                         f'{escolhido["escolhido_em"] or "?"} — os outros ficam como '
                         f'alternativas.')
            elif editable:
                lead += ' Carrega em <b>✔ vou montar este</b> no que escolheres.'
            else:
                lead += (' Para escolheres, corre <code>python webapp.py</code> no PC '
                         '(porto 8771) e carrega em <b>vou montar este</b>.')
        elif modo == "caixas":
            decks = _decks_de_slots(res["slots"], fmt)
            if fmt in decididos:
                # FORMATO DECIDIDO (André, 2026-09-21: *"Pioneer apenas
                # Greasefang e jeskai control"*): as caixas dele e mais nada —
                # nem top-N, nem candidatos, nem «vou montar este». Diz-se
                # porquê, senão a secção parecia o Modern por acaso.
                lead = (f'Os <b>{len(decks)}</b> decks que decidiste para este '
                        f'formato, tal como estão nas caixas — sem top-{n} nem '
                        f'candidatos, de propósito (<code>colecao_config.json → '
                        f'formatos_decididos</code>; tirar o formato de lá devolve '
                        f'o top-{n}).')
            else:
                lead = 'O deck já escolhido para a caixa deste formato, e as suas variantes.'
        else:
            decks = _decks_premodern(res)
            pm = res.get("premodern") or {}
            n_sug = len(pm.get("sugestoes") or [])
            lead = (f'Os <b>{len(pm.get("top") or [])}</b> arquétipos mais '
                    f'representados e os <b>{len(pm.get("combo") or [])}</b> '
                    f'melhores <b>combo</b> do formato. A percentagem é a do que '
                    f'está <b>livre</b>: desde 19/09/2026 cada deck tem as suas '
                    f'próprias cartas e nenhuma caixa de Premodern empresta, por '
                    f'isso o que está dentro das outras caixas não conta para um '
                    f'deck novo. Com <b>{pm.get("limiar", 50)}%</b> ou mais, vira '
                    f'sugestão. '
                    + (f'Há <b>{n_sug}</b> por decidir.' if n_sug
                       else 'Hoje não há nenhuma acima do limiar com o que está '
                            'livre: o que sobra vai para a venda (aba '
                            '<b>Vender</b> das Deckboxes).')
                    + (' Carrega em <b>✔ vou montar este</b> para lhe abrires uma '
                       'caixa, ou em <b>✕ não quero este</b> para libertares as '
                       'cartas dele.' if editable else ''))
        for d in decks:
            for m in d["linhas"]:
                names.add(m["nm"])
        data.append((fmt, titulo, decks, lead))
    imgs = _img_map(con, sorted(names))

    subnav, secs = "", ""
    for fmt, titulo, decks, lead in data:
        subnav += (f'<a href="#f-{fmt}">{html.escape(titulo)} '
                   f'<span class="n">{len(decks)}</span></a>')
        if decks:
            decks[0]["aberto"] = True     # o primeiro de cada formato já aberto
            corpo = "".join(_deck_html(d, imgs, editable) for d in decks)
        else:
            corpo = ('<p class="vazio">Sem listas que contem para este formato — '
                     'ou sem caixa escolhida. Não invento uma lista para encher a '
                     'página; vê <code>colecao_config.json → metagame_fontes</code>.</p>')
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(titulo)} '
                 f'<span class="n">{len(decks)}</span></h2>'
                 f'<p class="lead">{lead}</p>{corpo}</section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    # O rodapé diz QUE formatos são top-N e quais mostram as caixas — escrito
    # à mão dizia "Standard, Pioneer e Legacy" no dia em que o Pioneer deixou
    # de o ser (2026-09-21). Sai da mesma lista que desenha as secções.
    tops = [t for _f, t, modo in secoes() if modo == "top"]
    cxs = [t for _f, t, modo in secoes() if modo == "caixas"]
    return (_TMPL
            .replace("%SUBNAV%", subnav)
            .replace("%SECS%", secs).replace("%N%", str(n))
            .replace("%TOPS%", html.escape(_e_lista(tops)))
            .replace("%CAIXAS%", html.escape(_e_lista(cxs)))
            .replace("%EDIT%", "1" if editable else "")
            # O token só entra na página quando o pedido que a foi buscar já o
            # trazia (ver `webapp`): é ele que autoriza os botões a gravar.
            .replace("%TOKEN%", token or "")
            .replace("%TODAY%", today))


_CSS = """
 .lead{color:var(--muted);font-size:12.5px;margin:2px 0 12px} .lead b{color:var(--ink2)}
 .subnav{margin:0 0 16px} .subnav .seg{max-width:100%}
 h2{font-family:var(--font-hd);font-size:13px;margin:28px 0 5px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;scroll-margin-top:calc(var(--sticky) + 12px)} h2 .n{color:var(--dim)}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:11px 15px;margin-bottom:8px}
 .deck>summary{cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:10px;list-style:none}
 .deck>summary::-webkit-details-marker{display:none} .deck>summary b{font-size:15px} .deck>summary::before{content:"\\25B8";color:var(--muted);margin-right:6px} .deck[open]>summary::before{content:"\\25BE"}
 /* `min-width:0` + `overflow-wrap`: sem eles, *"96 listas que contam ·
    Argothian Enchantress…"* empurrava o cartão 14 px para fora do ecrã a
    390 px, e a página inteira ganhava scroll horizontal por causa de uma linha
    de texto. */
 .src{color:var(--muted);font-size:11px;margin-left:auto;text-align:right;
   min-width:0;overflow-wrap:anywhere}
 .cov{font-size:12px;font-weight:700;padding:1px 9px;border-radius:20px;background:#1e2531;flex:none;white-space:nowrap}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:8px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px} .bar span.ob{background:#26406f}
 .badges{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:6px 0}
 .bdg{font-size:11px;padding:2px 8px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .bdg.ok{background:#123020;color:var(--add)} .bdg.pt{background:#101c2e;color:var(--ob)} .bdg.fo{background:#2a2410;color:var(--gold)}
 .meta{display:flex;flex-wrap:wrap;gap:4px 12px;color:var(--muted);font-size:11.5px;margin:4px 0} .meta b{color:var(--ink)}
 .semp{font-style:normal;color:var(--dim);margin-left:5px}
 .meta .ob,.meta .ob b{color:var(--ob)}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
 .cd{position:relative;width:56px;border-radius:5px} .cd img,.cd .noimg{width:56px;height:78px;border-radius:4px;display:block;background:#0c0f14}
 /* O `alt` passou a trazer o nome da carta; isto é como ele se lê quando a
    imagem não carrega — pequeno e dentro do quadrado, em vez de rebentar a
    grelha. */
 .cd img{overflow:hidden;font-size:9px;line-height:1.15;color:var(--dim);padding:2px}
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
 .cpbtn{font-size:11px;font-weight:700;padding:4px 12px;border-radius:999px;border:1px solid var(--line2);background:var(--card3);color:var(--muted);cursor:pointer} .cpbtn:hover{border-color:var(--accent);color:var(--ink)} .cpbtn.done{background:#0f2a1c;border-color:#2f6a45;color:var(--add)}
 .acts{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px;border-top:1px solid var(--line);padding-top:12px}
 .toast{position:fixed;left:50%;transform:translateX(-50%);bottom:22px;z-index:60;background:var(--card3);border:1px solid var(--accent);color:var(--ink);font-size:13px;padding:11px 17px;border-radius:22px;box-shadow:var(--sombra)}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
"""

_LEAD = ("Os <b>%N%</b> decks que estás mais perto de concluir em cada formato — "
         "com a lista de consenso, o que tens livre e o que falta comprar · dados "
         "de <b>%TODAY%</b>")

_RODAPE = ("""<b style="color:var(--add)">Verde</b> = tens a carta livre para esta caixa ·
<b style="color:var(--warn)">vermelho</b> = não tens livre, é compra. Desde 19/09/2026
<b>cada deck tem as suas próprias cartas</b>: uma cópia que está noutra caixa do loadout é
dessa caixa e <b>não conta</b> para esta — compra-se outra. A <b>percentagem</b> do topo é a do
que <b>tens livre</b>, e é ela que
ordena o top-%N%. Ignora as terras
básicas: com elas, todos os decks começavam acima dos 30% e nenhum se distinguia dos outros.
A <b>lista de consenso</b> é a lista padrão do arquétipo — cada lugar ocupado pela
cópia com maior probabilidade de lá estar, calculada das decklists reais que contam.
<b>%TOPS%</b> são as caixas por escolher: aqui está o top-%N% para
decidires. Em <b>%CAIXAS%</b> mostram-se os decks já escolhidos. No <b>Premodern</b> a pergunta é outra —
o top-10 do formato e os melhores combo, com a percentagem do que <b>sobra</b> depois de as
seis caixas estarem servidas: é com essas cartas que se monta mais um deck, e é o que não
for reservado por uma sugestão que vai para a venda.
Regra de material: nesses formatos as cartas são todas <b>foil</b> menos as da Reserved List
(o preço de fecho é o do foil), e no Premodern são todas <b>PT</b>.
Quem manda é o <code>colecao_config.json</code> (<code>metagame_top_n</code>, <code>caixas</code>).
Para o metagame inteiro, com o top-10 ponderado, vê a <a href="cobertura.html">Cobertura</a>. Atualiza diariamente.""")

_TMPL = ("""<!doctype html><html lang="pt-PT"><head>"""
         + shell.head("Metagame", _CSS) + """</head><body>"""
         + shell.abrir("metagame.html", "Metagame", _LEAD) + """
<div class="wrap">
<div class="subnav"><div class="seg">%SUBNAV%</div></div>
%SECS%
</div>""" + shell.fechar(_RODAPE, """
<script>
function cp(btn){
  const c=btn.closest('.faltas'); const t=c&&c.querySelector('textarea.cmk'); if(!t)return;
  const done=()=>{btn.textContent='\\u2713 copiado';btn.classList.add('done');};
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t.value).then(done).catch(()=>{t.select();document.execCommand('copy');done();});
  }else{t.select();try{document.execCommand('copy');done();}catch(e){}}
}
/* "Vou montar este" — so existe no MODO EDICAO (webapp.py, porto 8771). No site
   publicado o %EDIT% vem vazio, os botoes nem se desenham e este bloco nao liga
   nada: um botao que nao faz nada e pior do que nao haver botao. */
(function(){
  if(!"%EDIT%") return;
  const toast=t=>{const d=document.createElement('div');d.className='toast';
    d.textContent=t;document.body.appendChild(d);setTimeout(()=>d.remove(),3200);};
  for(const b of document.querySelectorAll('[data-act]')){
    b.onclick=async()=>{
      b.disabled=true;
      try{
        const r=await fetch('api/escolher',{method:'POST',
          headers:{'Content-Type':'application/json',
                   'X-Mtgvault-Token':"%TOKEN%"},
          body:JSON.stringify({act:b.dataset.act,slot:b.dataset.slot,
                               nome:b.dataset.nome||null,
                               id:b.dataset.id||null,
                               aid:b.dataset.aid?Number(b.dataset.aid):null})});
        if(!r.ok) throw new Error('HTTP '+r.status);
        const j=await r.json();
        if(j.erro) throw new Error(j.erro);
        toast(j.msg||'Feito.');
        location.reload();
      }catch(e){b.disabled=false;toast('Nao deu: '+e.message);}
    };
  }
})();
</script>""") + """</body></html>""")


def main():
    from mtgvault import db
    with db.session() as con:
        print("metagame.html:", build(con))


if __name__ == "__main__":
    main()
