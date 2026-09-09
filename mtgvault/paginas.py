"""O que TODAS as páginas do site partilham: o tema e o menu.

Antes, cada gerador escrevia o seu `:root{...}` e o seu `<nav class="tabs">` à
mão. As consequências apareceram as duas:

  * o `cobertura.html` ficou com um menu de Agosto — sem **Deckboxes** e sem
    **Metagame** — porque quem acrescentou as abas novas não se lembrou de lá ir.
    Uma página órfã não dá erro nenhum: só deixa de se lá chegar;
  * metade das páginas usava `#0d1017` e a outra metade `#0e1116`, com dois
    cinzentos de texto diferentes. Passar de uma para a outra no telemóvel dava
    um salto de cor que não queria dizer nada.

Por isso o menu e a paleta vivem aqui, e as páginas pedem-nos. Uma aba nova
entra numa lista só. É a mesma lição do `sources.lista_conta` e do
`loadout.rotulo_material`: a regra num sítio só.
"""
from __future__ import annotations

import html
import json
from collections import defaultdict

# O menu, pela ordem em que aparece no `index.html`. (ficheiro, ícone, rótulo).
#
# A **Deckboxes é a página dos decks** (André, 2026-09-08: *"temos decks vigiados
# e deckbox que é a mesma coisa"*). A antiga *Decks permanentes*
# (`meusdecks.html`) saiu do menu na v6: fazia a mesma pergunta e respondia com
# outro número, porque contava a colecção inteira por deck em vez da alocação. O
# ficheiro continua a ser gerado, mas só como **reencaminhamento** — os links
# antigos (e o histórico do telemóvel dele) não podem cair num 404.
MENU = [
    ("index.html", "🏠", "Início"),
    ("deckboxes.html", "🧰", "Deckboxes"),
    ("metagame.html", "🌐", "Metagame"),
    ("showcase.html", "🎯", "Showcase Challenger"),
    ("colecao_cor.html", "📚", "Coleção"),
    ("caixarl.html", "📦", "Caixa RL"),
]
# Páginas que não estão no menu principal mas que devem poder voltar a ele.
EXTRA = [("cobertura.html", "📊", "Cobertura"),
         ("reservedlist.html", "🏆", "Reserved List"),
         ("colecao.html", "🖼️", "Galeria")]


def img_map(con, names, da_coleccao: bool = True) -> dict[str, str]:
    """`nome de carta -> scryfall_id` de uma impressão com arte.

    Vive aqui pela mesma razão que o menu: estava copiada à letra no
    `deckboxes.py` e no `metagame.py`, e quase à letra no `meusdecks.py` — três
    sítios para corrigir de cada vez que um caso novo de dupla face aparecia.

    `da_coleccao` prefere a impressão que ele TEM (é a carta que vai mesmo estar
    na caixa). O `meusdecks` não a usa, e é de propósito: ali a lista é a do deck
    seguido, não a da coleção.

    As de dupla face casam-se pela FRENTE (o catálogo guarda `frente // verso`),
    senão ficavam sem imagem — um quadrado preto na grelha.
    """
    out: dict[str, str] = {}
    if da_coleccao:
        for r in con.execute("""SELECT c.name nm, cp.scryfall_id sid FROM copies cp
                                  JOIN cards c ON c.scryfall_id = cp.scryfall_id
                                 WHERE cp.purpose = 'player'"""):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    falta = [n for n in names if n not in out]
    for i in range(0, len(falta), 300):
        ch = falta[i:i + 300]
        ph = ",".join("?" for _ in ch)
        for r in con.execute(f"""SELECT name nm, scryfall_id sid FROM cards
                                  WHERE name IN ({ph}) AND digital = 0
                                  GROUP BY name""", ch):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    for n in [x for x in falta if x not in out]:
        r = con.execute("SELECT scryfall_id sid FROM catalog.cards "
                        "WHERE (name = ? OR name LIKE ?) AND digital = 0 LIMIT 1",
                        (n, n + " // %")).fetchone()
        if r:
            out[n] = r["sid"]
    return out


def art(sid) -> str:
    """O URL da arte pequena de uma impressão. Estava copiado em cinco páginas."""
    return (f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg"
            if sid else "")


# ---------------------------------------------------------------------------
# Cartas: cor, tipo e quantas ele tem
# ---------------------------------------------------------------------------
# A COR, pela ordem por que ele arruma as cartas (a mesma do `colecao_cor.html`:
# cor -> CMC). É por aqui que se procura numa caixa de colecção, e por isso é
# esta a ordem da lista "tirar da Colecção" do painel Montar (v6).
CORES = [("W", "⬜ Branco"), ("U", "🟦 Azul"), ("B", "⬛ Preto"),
         ("R", "🟥 Vermelho"), ("G", "🟩 Verde"), ("M", "🌈 Multicor"),
         ("C", "⚙️ Incolor / Artefacto"), ("L", "🏞️ Terras")]
COR_ORDEM = {k: i for i, (k, _t) in enumerate(CORES)}
COR_NOME = dict(CORES)

# Ordem de organização dos decks por tipo de carta (pedido do André, 2026-08-31).
TIPOS = ["Creature", "Planeswalker", "Sorcery", "Instant", "Artifact",
         "Enchantment", "Land"]


def cor_de(type_line: str | None, ci) -> str:
    """A gaveta de cor de uma carta: W/U/B/R/G, M (multicor), C ou L (terra).

    O mesmo critério do `colecao_cor._bucket` — as terras primeiro, senão uma
    Ancient Tomb caía em "incolor" e ele procura-a nas terras.
    """
    if type_line and "Land" in (type_line or "").split(" // ")[0]:
        return "L"
    try:
        cols = (json.loads(ci) if isinstance(ci, str) and ci.strip().startswith("[")
                else [c for c in (ci or "") if c in "WUBRG"])
    except (TypeError, ValueError):
        cols = [c for c in (ci or "") if c in "WUBRG"]
    cols = [c for c in cols if c in "WUBRG"]
    if len(cols) >= 2:
        return "M"
    return cols[0] if cols else "C"


def tipo_de(type_line: str | None) -> str:
    """Tipo principal de uma carta, pela ordem do André (Creature 1º, Land último).
    Cartas de múltiplos tipos caem no 1º tipo que casa (Artifact Creature →
    Creature)."""
    tl = (type_line or "").split(" // ")[0]
    return next((t for t in TIPOS if t in tl), "Other")


def _meta_cartas(con, names) -> dict[str, tuple[str, str]]:
    """`nome (frente) -> (type_line, color_identity)`, do catálogo.

    Uma consulta por lote de 300 e um fallback por LIKE para as de dupla face — o
    catálogo guarda `frente // verso` e as listas escrevem só a frente.
    """
    out: dict[str, tuple[str, str]] = {}
    names = [n for n in dict.fromkeys(names) if n]
    for i in range(0, len(names), 300):
        ch = names[i:i + 300]
        ph = ",".join("?" for _ in ch)
        for r in con.execute(f"""SELECT name nm, type_line tl, color_identity ci
                                   FROM cards WHERE name IN ({ph}) AND digital = 0
                                  GROUP BY name""", ch):
            out.setdefault(r["nm"].split(" // ")[0], (r["tl"], r["ci"]))
    for n in [x for x in names if x not in out]:
        r = con.execute("SELECT type_line tl, color_identity ci FROM catalog.cards "
                        "WHERE (name = ? OR name LIKE ?) AND digital = 0 LIMIT 1",
                        (n, n + " // %")).fetchone()
        if r:
            out[n] = (r["tl"], r["ci"])
    return out


def cores(con, names) -> dict[str, str]:
    """`nome -> gaveta de cor`. Usa-a o painel Montar para ordenar a lista."""
    return {n: cor_de(tl, ci) for n, (tl, ci) in _meta_cartas(con, names).items()}


def tipos(con, names) -> dict[str, str]:
    """`nome -> tipo principal`. Era o `meusdecks._type_map`."""
    return {n: tipo_de(tl) for n, (tl, _ci) in _meta_cartas(con, names).items()}


def posse_total(con) -> dict[str, int]:
    """`nome (frente) -> cópias jogáveis na COLECÇÃO INTEIRA.

    Era o `meusdecks._owned_qty`, e é a única coisa que aquela página dizia e a
    Deckboxes não: quantas ele tem ao todo, sem contar quem as leva. Na v6 é
    informação **secundária** de cada carta — o número que manda é o da alocação
    (é a mesma pergunta, e duas respostas era o defeito a corrigir).
    """
    out: dict[str, int] = defaultdict(int)
    for r in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player' GROUP BY c.name"""):
        out[r["nm"].split(" // ")[0]] += r["q"]
    return dict(out)


def grupos_por_tipo(cards, tm, render) -> str:
    """Agrupa os cartões por tipo (ordem do André) com um cabeçalho por grupo.

    Era o `meusdecks._group_by_type`, usado também pelo `showcase`. Cada carta
    pode trazer o seu tipo em `_type`; senão vem de `tm`.
    """
    buckets = defaultdict(list)
    for c in cards:
        buckets[c.get("_type") or tm.get(c["nm"].split(" // ")[0], "Other")].append(c)
    out = ""
    for t in TIPOS + ["Other"]:
        b = buckets.get(t)
        if not b:
            continue
        out += (f'<div class="typehdr">{html.escape(t)} '
                f'<span class="dim">{sum(c.get("qty", 1) for c in b)}</span></div>'
                f'<div class="cards">{"".join(render(c) for c in b)}</div>')
    return out


def faltas_de(cards, basicas=frozenset()) -> dict[str, int]:
    """`{nome: cópias a COMPRAR}` de uma lista de cartões, sem básicas.

    `comprar`, não `qty - hq`: uma carta que está noutra caixa do loadout já é
    dele e vai-se buscar (André, 2026-09-07). Era o `meusdecks._faltas`.
    """
    out: dict[str, int] = defaultdict(int)
    for c in cards:
        m = c.get("comprar", c["qty"] - c["hq"])
        if m > 0 and c["nm"] not in basicas:
            out[c["nm"].split(" // ")[0]] += m
    return dict(out)


def faltas_html(faltas, cls="", label="🛒 Faltas") -> str:
    """Bloco de faltas: cabeçalho + lista 'N× Carta' + botão copiar (formato
    Cardmarket numa textarea escondida). Era o `meusdecks._faltas_html`."""
    if not faltas:
        return ""
    order = sorted(faltas.items())
    items = "".join(f'<li><b>{q}×</b> {html.escape(nm)}</li>' for nm, q in order)
    cmk = "\n".join(f"{q} {nm}" for nm, q in order)
    return (f'<div class="faltas {cls}"><div class="flh">{label} '
            f'<span class="dim">{len(faltas)} · {sum(faltas.values())} cóp.</span>'
            f'<button class="cpbtn" onclick="cpFaltas(this)">copiar</button></div>'
            f'<ul class="fl">{items}</ul>'
            f'<textarea class="cmk" readonly>{html.escape(cmk)}</textarea></div>')


def plural(n: int, singular: str, plural_: str | None = None) -> str:
    """`1 cópia` / `2 cópias`. O `deckboxes.py` tem o gémeo em JavaScript (`cop`).

    O bloco *"ir buscar a outra caixa"* dizia **«1 cópias»** — e não é um caso
    raro: uma caixa costuma ter exactamente uma carta noutro sítio.
    """
    return f"{n} {singular if n == 1 else (plural_ or singular + 's')}"


def eur(v, casas: int = 2, espaco: bool = True) -> str:
    """Um valor em euros escrito em português: `1 009,27 €`.

    Estava escrito à mão em cada página, e **quatro delas ficaram em inglês**: a
    Cobertura, a Caixa RL, a Galeria e a Reserved List mostravam `1 009.27 €`
    enquanto a Deckboxes e o Metagame mostravam `8 426,34 €`. A conta estava
    certa nas seis; o que mudava era o ponto decimal, conforme a página em que
    ele estava. Nenhuma dava erro — é o padrão do `event_tier` aplicado a um
    número que ele lê todos os dias. (O `meta_coverage` chegava a ter as duas
    dentro da MESMA página: o `_eur` do Python com ponto e o `ceur` do
    JavaScript com vírgula.)

    Só formata: quem decide o que mostrar quando não há valor é quem chama — a
    Reserved List escreve `—` só para `None` e a Cobertura também para o zero, e
    isso é uma decisão de cada página.

    `casas` para as páginas que arredondam (a Caixa RL mostra o total sem
    cêntimos) e `espaco=False` para as que colam o símbolo (`715,19€`).
    """
    return (f"{v:,.{casas}f}".replace(",", " ").replace(".", ",")
            + (" €" if espaco else "€"))


def nav(atual: str = "", extra: bool = False) -> str:
    """O menu, com a página `atual` marcada. `extra` acrescenta as secundárias."""
    itens = MENU + (EXTRA if extra else [])
    return ('<nav class="tabs">' + "".join(
        f'<a{" class=\"cur\"" if f == atual else ""} href="{f}">{i} {t}</a>'
        for f, i, t in itens) + '</nav>')


# As duas linhas do `<head>` que mudam a leitura no telemóvel: o `viewport-fit`
# (para o entalhe do ecrã não comer o conteúdo) e a `theme-color` (a barra do
# browser deixa de ser branca por cima de uma página escura).
META = ('<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, '
        'viewport-fit=cover">\n'
        '<meta name="theme-color" content="#0d1017">')

# A paleta. É um SUPERCONJUNTO: tem as variáveis de todas as páginas, para
# nenhuma ficar sem a sua ao passar a usar este bloco.
#   --ink2/--dim  são os dois cinzentos abaixo do texto normal (antes cada
#                 página inventava o seu);
#   --ob          o azul do "está noutra caixa";
#   --pt          o azul da etiqueta de Português;
#   --rem         o vermelho de "saiu da lista" do core_decks.
#
# O `--dim` era `#5a6472`: **2,88:1** sobre o `--card`, abaixo do mínimo do WCAG
# AA (4,5:1) e abaixo até do de texto grande (3:1). É a cor do texto pequeno que
# explica as coisas — a razão de uma venda, o cabeçalho de uma tabela, o "de que
# gaveta vem" — e no telemóvel, de dia, não se lia. `#7a8494` dá 4,57:1 sobre o
# `--card` e 5,03:1 sobre o `--bg`, e continua um degrau abaixo do `--muted`
# (5,82:1), que é para o que serve.
TEMA = (
    " :root{--bg:#0d1017;--card:#161b24;--card2:#12171f;--ink:#eef2f7;"
    "--ink2:#c3cdd9;--muted:#8b97a6;--dim:#7a8494;--line:#242c38;--line2:#37445a;"
    "--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b;--ob:#7fa8ff;"
    "--pt:#5b8cff;--rem:#ff6b6b}\n"
    " html{-webkit-text-size-adjust:100%}"
)
