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

# O menu, pela ordem em que aparece no `index.html`. (ficheiro, ícone, rótulo).
MENU = [
    ("index.html", "🏠", "Início"),
    ("meusdecks.html", "🎴", "Decks permanentes"),
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
