"""A CASCA de todas as páginas do site: tokens, navegação, cabeçalho, rodapé.

Pedido do André (2026-09-24, à letra): *"no mtgvault quero uma organização
diferente, acho tudo muito confuso, ter que andar a correr os botões para os
lados. Faz toda uma reestruturação para um site profissional, bem organizado,
bem estruturado!"*

O que estava mal, e que isto vem fechar:

  * **cada página tinha a sua barra de botões horizontal** — `nav.tabs` numa,
    `.ftabs` noutra, `.decktabs` com scroll lateral na Deckboxes, `.subnav` no
    Metagame, `.filter` na Reserved List — com estilos diferentes e, na
    Deckboxes, **dezanove botões a correr para o lado** num telemóvel. Navegar
    era adivinhar o que estava fora do ecrã;
  * **o `index.html` era uma grelha de atalhos** escrita à mão, sem um único
    número da colecção;
  * a paleta era partilhada (`paginas.TEMA`) mas a **estrutura** não: cada
    gerador escrevia o seu `<header>`, a sua `.wrap`, o seu `body{}`. Duas
    páginas ao lado uma da outra alinhavam o conteúdo em sítios diferentes.

Agora há **um** sítio: a navegação é uma BARRA LATERAL fixa (≥ 900 px) agrupada
por secções, e no telemóvel a MESMA navegação abre em painel a partir de um
botão de menu. O corpo nunca tem scroll horizontal. O `abrir()`/`fechar()` de
cada página dá-lhe o cabeçalho (migalhas, título, subtítulo, ações) e o rodapé.

É a mesma lição do `sources.lista_conta` e do `loadout.rotulo_material`: a regra
num sítio só. Uma secção nova é uma linha no `SECCOES`.

**Não importa nada do resto do pacote, de propósito**: o `paginas.py` importa
ESTE módulo (para o `TEMA` e o `META` continuarem a chamar-se o que se chamavam)
e um import ao contrário fazia um ciclo.
"""
from __future__ import annotations

import html
import json

# ---------------------------------------------------------------------------
# OS ÍCONES, num sítio só (2.ª passagem, 2026-09-24)
# ---------------------------------------------------------------------------
# *"Troca os emojis da barra lateral, dos atalhos e dos títulos de secção por um
# conjunto único de ícones SVG em linha (traço 1.8, estilo «outline», cor
# herdada), iguais em todo o lado."*
#
# Porquê SVG e não emoji: um emoji é desenhado pelo SISTEMA, não pela página.
# O 🧰 do telemóvel dele (Android) e o do Chrome no Windows são dois desenhos
# diferentes, com pesos e cores diferentes — e o 🗺️ e o 🛡️ levam variação
# `FE0F`, que em Windows saía a preto-e-branco no meio de ícones a cor. Um
# conjunto único, com `currentColor` e traço 1.8, é a única forma de a barra
# lateral se ver igual nos dois sítios e de acender a dourado quando está activa.
#
# **Os emojis DENTRO DOS DADOS ficam** (ordem dele, à letra: *"podem ficar se
# forem informação"*): o ✅/🛒/📷 de uma carta diz o ESTADO dela — é conteúdo,
# não decoração de navegação.
#
# A geometria é a do conjunto Feather (MIT, feathericons.com), redesenhada aqui
# em `path`s soltos para não trazer uma dependência nem um segundo ficheiro: são
# ~3 KB dentro de uma casca que já vai embutida.
_SVG: dict[str, str] = {
    "inicio": '<path d="M3 9.5 12 2l9 7.5V20a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
              '<path d="M9 22V12.5h6V22"/>',
    "caixas": '<path d="M2.5 3.5h19v5h-19z"/><path d="M4.4 8.5V20a1.5 1.5 0 0 0 '
              '1.5 1.5h12.2a1.5 1.5 0 0 0 1.5-1.5V8.5"/><path d="M10 12.5h4"/>',
    "montado": '<path d="M21.5 11.1V12a9.5 9.5 0 1 1-5.6-8.7"/>'
               '<path d="m8 11.5 3.2 3.2L22 4"/>',
    "montar": '<path d="M14.6 6.2a1 1 0 0 0 0 1.4l1.8 1.8a1 1 0 0 0 1.4 0l3.6-3.6'
              'a6 6 0 0 1-7.9 7.9l-6.6 6.6a2.1 2.1 0 1 1-3-3l6.6-6.6a6 6 0 0 1 '
              '7.9-7.9z"/>',
    "plano": '<path d="M1.8 6.2 8.4 2.6l7.2 3.6 6.6-3.6v15.2l-6.6 3.6-7.2-3.6'
             '-6.6 3.6z"/><path d="M8.4 2.6v18.2"/><path d="M15.6 6.2v18"/>',
    "arrumar": '<path d="M22 12.5h-5.4l-1.8 2.8H9.2l-1.8-2.8H2"/>'
               '<path d="M5.4 5.1 2 12.5V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5.5'
               'l-3.4-7.4A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.8 1.1z"/>',
    "binders": '<path d="M12 2.4 2.2 7.2 12 12l9.8-4.8z"/>'
               '<path d="m2.2 16.8 9.8 4.8 9.8-4.8"/><path d="m2.2 12 9.8 4.8L21.8 12"/>',
    "galeria": '<rect x="3" y="3" width="18" height="18" rx="2.2"/>'
               '<circle cx="8.6" cy="8.6" r="1.6"/><path d="m21 15.5-4.8-4.8L5.5 21"/>',
    "caixarl": '<path d="M16.5 9.4 7.5 4.2"/><path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4'
               'a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 '
               '2 0l7-4A2 2 0 0 0 21 16z"/><path d="m3.3 7 8.7 5 8.7-5"/>'
               '<path d="M12 22V12"/>',
    "precos": '<path d="M22.5 6.5 13.8 15.2l-4.6-4.6L1.5 18.3"/>'
              '<path d="M16.8 6.5h5.7v5.7"/>',
    "metagame": '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19"/>'
                '<path d="M12 2.5A14.6 14.6 0 0 1 15.8 12 14.6 14.6 0 0 1 12 21.5'
                ' 14.6 14.6 0 0 1 8.2 12 14.6 14.6 0 0 1 12 2.5z"/>',
    "cobertura": '<path d="M12 20.5V9.5"/><path d="M18.2 20.5v-17"/>'
                 '<path d="M5.8 20.5v-6"/>',
    "showcase": '<circle cx="12" cy="8.6" r="6.6"/>'
                '<path d="m8.2 14 -1.2 7.6L12 18.4l5 3.2L15.8 14"/>',
    "comprar": '<circle cx="9.5" cy="20.5" r="1.3"/><circle cx="19" cy="20.5" r="1.3"/>'
               '<path d="M1.5 2h3.3l2.5 12.2a1.9 1.9 0 0 0 1.9 1.5h9.2a1.9 1.9 0 0 0 '
               '1.9-1.5L22.2 6H6.2"/>',
    "encomendas": '<path d="M1.5 4h13.6v12.4H1.5z"/>'
                  '<path d="M15.1 8.4h3.9l3.5 3.5v4.5h-7.4z"/>'
                  '<circle cx="6" cy="19" r="2.2"/><circle cx="18.4" cy="19" r="2.2"/>',
    "vender": '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6'
              'a2 2 0 0 1 0 2.8z"/><circle cx="7.2" cy="7.2" r="1.1"/>',
    "feira": '<rect x="2" y="7.2" width="20" height="13.3" rx="2.2"/>'
             '<path d="M16 20.5V5.2a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v15.3"/>',
    "revalidacao": '<path d="M22.5 19a2 2 0 0 1-2 2h-17a2 2 0 0 1-2-2V8.4a2 2 0 0 1 '
                   '2-2h3.4l1.9-2.9h6.4l1.9 2.9h3.4a2 2 0 0 1 2 2z"/>'
                   '<circle cx="12" cy="13.4" r="3.8"/>',
    "sugestoes": '<path d="M13.2 2 3.4 13.8h8.1l-.7 8.2 9.8-11.8h-8.1z"/>',
    "partilhadas": '<path d="m17 1.5 4 4-4 4"/><path d="M3 11.5v-2a4 4 0 0 1 4-4h14"/>'
                   '<path d="m7 22.5-4-4 4-4"/><path d="M21 12.5v2a4 4 0 0 1-4 4H3"/>',
    "procurar": '<circle cx="10.8" cy="10.8" r="7.8"/><path d="m21 21-4.7-4.7"/>',
    "todas": '<path d="M3.2 3.2h7.2v7.2H3.2z"/><path d="M13.6 3.2h7.2v7.2h-7.2z"/>'
             '<path d="M13.6 13.6h7.2v7.2h-7.2z"/><path d="M3.2 13.6h7.2v7.2H3.2z"/>',
    "fechar": '<path d="M4 15.2s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/>'
              '<path d="M4 22v-6.8"/>',
    "colecao": '<path d="M2 3.5h5.5a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/>'
               '<path d="M22 3.5h-5.5a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3H22z"/>',
    "atualizar": '<path d="M22.5 4.2v6h-6"/><path d="M1.5 19.8v-6h6"/>'
                 '<path d="M4 9.2a8.5 8.5 0 0 1 14-3.2l4.5 4.2"/>'
                 '<path d="M1.5 13.8 6 18a8.5 8.5 0 0 0 14-3.2"/>',
    "local": '<path d="M20.5 10.5c0 6.6-8.5 12.4-8.5 12.4S3.5 17.1 3.5 10.5a8.5 8.5 '
             '0 0 1 17 0z"/><circle cx="12" cy="10.3" r="2.9"/>',
    "saida": '<path d="M21 15.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3.6"/>'
             '<path d="m16.8 7.8 -4.8-4.8-4.8 4.8"/><path d="M12 3v12.6"/>',
    "sideboard": '<path d="M12 22s8-4.1 8-10.2V5.1L12 2 4 5.1v6.7C4 17.9 12 22 12 22z"/>',
    "emergir": '<path d="M22 12h-4.2l-2.9 8.4L9 3.6 6.1 12H2"/>',
    "aviso": '<path d="m10.3 3.9-8.5 14.2A2 2 0 0 0 3.5 21h17a2 2 0 0 0 1.7-3L13.7 3.9'
             'a2 2 0 0 0-3.4 0z"/><path d="M12 9.2v4.2"/><path d="M12 17.2h.01"/>',
    "nuvem": '<path d="M18 10.2h-1.3A8 8 0 1 0 9 20.2h9a5 5 0 0 0 0-10z"/>',
    "livro": '<path d="M4 3.5h13a2 2 0 0 1 2 2v15H6a2 2 0 0 1-2-2z"/>'
             '<path d="M6 16.5h13"/>',
    "ajuda": '<circle cx="12" cy="12" r="9.5"/>'
             '<path d="M9.3 9.2a2.8 2.8 0 0 1 5.4.9c0 1.9-2.7 2.8-2.7 2.8"/>'
             '<path d="M12 17h.01"/>',
    "menu": '<path d="M3.5 12h17"/><path d="M3.5 6h17"/><path d="M3.5 18h17"/>',
}


# Os tamanhos que o site usa. São CLASSES e não atributos `width`/`height`
# porque o resto — `fill`, `stroke`, a espessura e as pontas do traço — também
# vive no CSS: escrito em cada `<svg>`, eram **190 bytes de repetição por
# ícone**, e a casca da Deckboxes (que leva a barra lateral inteira) passava dos
# 70 KB que o `test_telemovel` defende. Assim são ~48.
TAMANHOS = (14, 15, 16, 17, 18, 21, 24)


def icone(nome: str, tam: int = 18) -> str:
    """Um ícone do conjunto, em linha. Cor herdada (`currentColor`), traço 1.8.

    Um nome que não exista devolve **string vazia** e não um quadrado vazio: um
    ícone a faltar não pode tapar o rótulo que está ao lado dele.
    """
    d = _SVG.get(nome)
    if not d:
        return ""
    if tam == 18:
        cls, sty = "ico", ""
    elif tam in TAMANHOS:
        cls, sty = f"ico i{tam}", ""
    else:                       # um tamanho fora da lista continua a funcionar
        cls, sty = "ico", f' style="width:{tam}px;height:{tam}px"'
    return (f'<svg class="{cls}"{sty} viewBox="0 0 24 24" aria-hidden="true">'
            f'{d}</svg>')


def js_icones() -> str:
    """O MESMO conjunto, para o JavaScript que desenha as vistas da Deckboxes.

    Um segundo conjunto escrito à mão em JS era a segunda oportunidade de os
    dois discordarem — a lição do `loadout.e_foil` e do `vistoId`.
    """
    return ("const ICO = " + json.dumps({n: icone(n) for n in _SVG},
                                        ensure_ascii=False) + ";\n"
            "const ico = n => ICO[n] || '';\n")


# ---------------------------------------------------------------------------
# A NAVEGAÇÃO, num sítio só
# ---------------------------------------------------------------------------
# `(seccao, [(ficheiro, ancora, ícone, rótulo, nota)])`. A âncora vazia é a
# página inteira; com âncora, é uma SUB-VISTA da página (a Deckboxes lê o
# `location.hash` e abre a aba certa — ver `deckboxes.JS`, `abaDoHash`).
#
# A ordem é a do pedido dele: Início, Decks, Coleção, Metagame, Compras e venda.
#
# **Os rótulos dizem o que é à primeira leitura** (2.ª passagem, 2026-09-24), e a
# nota só existe quando ACRESCENTA: *"Por cor · os binders"* eram duas palavras
# para a mesma coisa em duas linhas, e *"Caixa Reserved List"* logo por cima de
# *"Reserved List"* obrigava a ler a nota para saber qual era qual. Agora são
# «Binders por cor», «Reserved List · caixa» e «Reserved List · preços» — os
# nomes que ele escreveu na ordem.
#
# E o TÍTULO de cada página é o MESMO rótulo (`shell.abrir`): clicar em «Binders
# por cor» e chegar a uma página que se chama «Coleção por cor» é a página a
# discordar do menu que lá levou.
SECCOES: list[tuple[str, list[tuple[str, str, str, str, str]]]] = [
    ("", [
        ("index.html", "", "inicio", "Início", "o painel de hoje"),
    ]),
    ("Decks", [
        ("deckboxes.html", "", "caixas", "Deck boxes", "todas as caixas"),
        ("deckboxes.html", "montados", "montado", "Decks montados", ""),
        ("deckboxes.html", "pormontar", "montar", "Decks para montar", ""),
        ("deckboxes.html", "plano", "plano", "Plano de montagem", ""),
        ("deckboxes.html", "arrumar", "arrumar", "Arrumar cartas", ""),
    ]),
    ("Coleção", [
        ("colecao_cor.html", "", "binders", "Binders por cor", ""),
        ("colecao.html", "", "galeria", "Galeria de cartas", ""),
        ("caixarl.html", "", "caixarl", "Reserved List · caixa", ""),
        ("reservedlist.html", "", "precos", "Reserved List · preços", ""),
    ]),
    ("Metagame", [
        ("metagame.html", "", "metagame", "Metagame", "o que estás perto de fechar"),
        ("cobertura.html", "", "cobertura", "Cobertura do metagame", ""),
        ("showcase.html", "", "showcase", "Showcase Challenger",
         "decks de eventos recentes"),
    ]),
    ("Compras e venda", [
        ("deckboxes.html", "comprar", "comprar", "Comprar", ""),
        ("deckboxes.html", "encomendas", "encomendas", "Encomendas", ""),
        ("deckboxes.html", "vender", "vender", "Vender", ""),
        ("deckboxes.html", "feira", "feira", "Feira", ""),
        ("deckboxes.html", "revalidacao", "revalidacao", "Revalidação por foto", ""),
    ]),
]

# O link para a casa-mãe, no topo da barra lateral (pedido dele: o site do
# mtgvault é uma secção do baverone.com).
CASA = ("https://baverone.com", "baverone.com")

# «PARA JÁ TIRA O VENDER» (André, 2026-09-25). Com `venda.mostrar` a `false`, a
# secção fica só com as COMPRAS — e por isso muda de nome. «Compras e venda»
# por cima de quatro itens que não têm venda nenhuma era a barra a prometer uma
# vista que já não existe, que é o mesmo defeito do item órfão que isto veio
# tirar. A arquitectura de 2026-09-24 não mudou: `SECCOES` continua a ser a
# lista inteira, e é o que o teste dela lê.
SECCAO_VENDA = "Compras e venda"
SECCAO_SEM_VENDA = "Compras"

# As páginas que o site GERA, para quem precise da lista (testes, `daily`).
# Sai de `SECCOES` e não de `seccoes()`: o interruptor tira uma SUB-VISTA (uma
# âncora), nunca uma página — nenhum ficheiro `.html` deixa de se gerar, e uma
# lista de publicação que encolhesse com um config era como o `deckboxes.html`
# ficou semanas sem ser publicado.
PAGINAS_DO_MENU = list(dict.fromkeys(f for _s, itens in SECCOES
                                     for f, a, *_r in itens if not a))


def seccoes() -> list[tuple[str, list[tuple[str, str, str, str, str]]]]:
    """As secções EFECTIVAS da barra lateral — `SECCOES` menos o que está
    desligado hoje.

    Hoje só há um interruptor (`venda.mostrar`, 2026-09-25) e por isso isto é
    quase a lista inteira. Existe na mesma como função porque é ela que a barra,
    as migalhas e o título de cada página passam a ler: com a lista a ser lida
    directamente em cinco sítios, o primeiro que se esquecesse do interruptor
    punha um item «Vender» numa página onde a aba não existe — um 404 com mais
    passos. O import é lá dentro porque o `venda` chega aqui pelo `paginas`.
    """
    from . import venda                                      # noqa: PLC0415
    if venda.mostrar():
        return SECCOES
    fora = {("deckboxes.html", "vender")}
    out = []
    for sec, itens in SECCOES:
        restam = [it for it in itens if (it[0], it[1]) not in fora]
        if not restam:
            continue
        out.append((SECCAO_SEM_VENDA if sec == SECCAO_VENDA else sec, restam))
    return out


def seccao_de(ficheiro: str) -> str:
    """A secção a que uma página pertence (a primeira que a tem, sem âncora)."""
    for sec, itens in seccoes():
        for f, a, *_r in itens:
            if f == ficheiro and not a:
                return sec
    return ""


def titulo_de(ficheiro: str) -> str:
    for _sec, itens in SECCOES:
        for f, a, _i, rot, _n in itens:
            if f == ficheiro and not a:
                return rot
    return ficheiro


# ---------------------------------------------------------------------------
# `<head>`: meta, tipos de letra, tokens
# ---------------------------------------------------------------------------
META = ('<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, '
        'viewport-fit=cover">\n'
        '<meta name="theme-color" content="#07080d">')

# Space Grotesk nos títulos, Inter no texto (pedido dele, para casar com o
# baverone.com). Com `display=swap` e uma pilha de sistema por trás: se o
# Google Fonts não responder — ou se ele abrir isto sem rede — a página lê-se na
# mesma, só com outra letra.
FONTES = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700'
    '&display=swap">'
)

# A PALETA. Fundo #07080d, painéis #0e1018/#12151f, texto #eef0f6 e o dourado
# #f5c451 do mtgvault — os valores que ele deu, para casar com o baverone.com.
#
# É um SUPERCONJUNTO: tem as variáveis de todas as páginas, para nenhuma ficar
# sem a sua. Duas notas que custaram a descobrir e que ficam:
#
#   * o `--dim` é o cinzento do texto pequeno que EXPLICA as coisas (a razão de
#     uma venda, de que gaveta vem a carta). Esteve em `#5a6472` — 2,88:1 sobre
#     o painel, abaixo do mínimo do WCAG AA — e no telemóvel, de dia, não se
#     lia. Os valores de hoje ficam todos acima de 4,5:1 sobre o `--card`;
#   * o `--accent` passou a ser o DOURADO da marca. O azul que ele era continua
#     a existir em `--info` (e em `--ob`/`--pt`), porque o azul quer dizer uma
#     coisa nesta página — *"a carta está noutra caixa"* — e trocá-lo por
#     dourado punha dois significados na mesma cor. Quem escreve texto por cima
#     do dourado usa `--accent-ink` (escuro): branco sobre `#f5c451` é 1,9:1.
TEMA = (
    " :root{--bg:#07080d;--card:#12151f;--card2:#0e1018;--card3:#171b28;"
    "--ink:#eef0f6;--ink2:#c8cede;--muted:#949cb0;--dim:#838b9e;"
    "--line:#1d2130;--line2:#2c3243;"
    "--accent:#f5c451;--accent-ink:#0b0d14;--accent-soft:#2a2210;"
    "--accent-line:#5a4a1c;"
    "--info:#6f9bff;--info-soft:#131c31;"
    "--gold:#f5c451;--add:#4fd08a;--warn:#f0805a;--ob:#8ab0ff;"
    "--pt:#8ab0ff;--rem:#ff7b7b;"
    "--font:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;"
    "--font-hd:'Space Grotesk','Inter',system-ui,-apple-system,sans-serif;"
    # `--sticky` é a altura ocupada no topo do ecrã por barras fixas da CASCA.
    # Zero no PC (não há nenhuma) e a altura da barra de topo no telemóvel — é
    # por isso que tudo o que se prende ao topo (o índice de cores da Coleção, a
    # barra de filtros da Deckboxes) e todo o `scroll-margin-top` a usam: sem
    # ela, a secção para onde ele salta nascia por baixo do botão de menu.
    "--maxw:1200px;--side:258px;--sticky:0px;--r:12px;--r2:16px;"
    "--sombra:0 10px 30px rgba(0,0,0,.35)}\n"
    " html{-webkit-text-size-adjust:100%}"
)

# ---------------------------------------------------------------------------
# O CSS da casca. Vai DEPOIS do CSS de cada página (ver `head`), para a casca
# ter a última palavra sobre o que é partilhado — o layout, a barra lateral, os
# botões, as tabelas — e a página continuar a mandar no que é dela.
# ---------------------------------------------------------------------------
CSS = r"""
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--font);
   -webkit-font-smoothing:antialiased;padding-bottom:env(safe-area-inset-bottom)}
 h1,h2,h3,h4,.fonte-hd{font-family:var(--font-hd);letter-spacing:-.01em}
 a{color:var(--accent);text-underline-offset:2px}
 img,svg,video,canvas,table,pre{max-width:100%}
 :focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
 .salta{position:absolute;left:-9999px;top:0;z-index:99;background:var(--accent);
   color:var(--accent-ink);padding:10px 16px;border-radius:0 0 10px 0;font-weight:700}
 .salta:focus{left:0}

 /* OS ÍCONES (2.ª passagem, 2026-09-24). Um só conjunto, `currentColor`: o
    ícone acende com o rótulo quando o item da barra fica activo, o que um emoji
    — desenhado pelo sistema, com cor própria — nunca fez. */
 svg.ico{display:inline-block;flex:none;width:18px;height:18px;fill:none;
   stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;
   vertical-align:-.16em}
 svg.i14{width:14px;height:14px} svg.i15{width:15px;height:15px}
 svg.i16{width:16px;height:16px} svg.i17{width:17px;height:17px}
 svg.i21{width:21px;height:21px} svg.i24{width:24px;height:24px}
 .ic>svg.ico{display:block;vertical-align:baseline}
 h1 svg.ico,h2 svg.ico,h3 svg.ico,h4 svg.ico,summary svg.ico{
   width:1em;height:1em;vertical-align:-.12em;margin-right:.14em;opacity:.85}

 /* ------------------------------------------------------------- estrutura */
 .shell{display:flex;min-height:100vh;align-items:stretch}
 .mainc{flex:1 1 auto;min-width:0;display:flex;flex-direction:column}
 main{flex:1 0 auto}
 .wrap,.pghin{width:100%;max-width:var(--maxw);margin-inline:auto;
   padding-inline:clamp(14px,2.6vw,30px)}
 .wrap{padding-block:22px 72px}

 /* --------------------------------------------------------- barra lateral */
 .side{flex:0 0 var(--side);width:var(--side);background:var(--card2);
   border-right:1px solid var(--line);position:sticky;top:0;align-self:flex-start;
   height:100vh;overflow-y:auto;overscroll-behavior:contain;
   scrollbar-width:thin;display:flex;flex-direction:column;z-index:40}
 .sidetop{padding:18px 16px 12px;border-bottom:1px solid var(--line)}
 .casa{display:inline-flex;align-items:center;gap:6px;color:var(--muted);
   font-size:11.5px;font-weight:600;text-decoration:none;padding:3px 0}
 .casa:hover{color:var(--accent)}
 .marca{display:flex;align-items:center;gap:9px;margin-top:8px;color:var(--ink);
   text-decoration:none}
 .marca .mk{width:30px;height:30px;flex:none;border-radius:9px;display:grid;
   place-items:center;background:linear-gradient(145deg,var(--accent),#c89a2c);
   color:var(--accent-ink);font-weight:800;font-size:15px;font-family:var(--font-hd)}
 .marca b{font-family:var(--font-hd);font-size:16.5px;font-weight:700;letter-spacing:-.02em}
 .marca small{display:block;color:var(--dim);font-size:10.5px;font-weight:600;
   letter-spacing:.09em;text-transform:uppercase;line-height:1.3}
 .sidenav{padding:10px 10px 22px;flex:1 0 auto}
 .sgrp{margin-top:14px}
 .sgrp:first-child{margin-top:2px}
 .sgh{padding:6px 10px 5px;font-size:10px;font-weight:700;letter-spacing:.11em;
   text-transform:uppercase;color:var(--dim)}
 .sli{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:10px;
   color:var(--ink2);text-decoration:none;font-size:13.5px;font-weight:600;
   line-height:1.25;min-height:38px;transition:background .12s,color .12s}
 .sli .ic{flex:none;width:19px;display:flex;align-items:center;justify-content:center;
   color:var(--muted)}
 .sli .tx{min-width:0}
 .sli .tx small{display:block;color:var(--dim);font-size:11px;font-weight:500;
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .sli:hover{background:var(--card);color:var(--ink)}
 .sli:hover .ic{color:var(--ink2)}
 .sli.cur{background:var(--accent-soft);color:var(--accent);
   box-shadow:inset 2px 0 0 var(--accent)}
 .sli.cur .ic{color:var(--accent)}
 .sli.cur .tx small{color:#b9a066}
 .sli.sub{min-height:32px;padding:5px 10px 5px 14px;font-size:12.5px;
   font-weight:500;color:var(--muted)}
 .sli.sub .ic{width:16px}
 .sli.sub:hover{color:var(--ink)}
 .sli.sub.cur{color:var(--accent);background:var(--accent-soft)}
 .sidept{padding:12px 16px 18px;border-top:1px solid var(--line);color:var(--dim);
   font-size:11px;line-height:1.5}
 .sidept a{color:var(--muted);text-decoration:none} .sidept a:hover{color:var(--accent)}

 /* ------------------------------------------------- barra de topo (móvel) */
 .topbar{display:none;position:sticky;top:0;z-index:35;align-items:center;gap:10px;
   padding:9px clamp(10px,3vw,16px);background:rgba(7,8,13,.94);
   backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
 .menub{display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:6px 12px;
   border-radius:10px;border:1px solid var(--line2);background:var(--card);
   color:var(--ink);font:inherit;font-size:13px;font-weight:700;cursor:pointer}
 .menub:hover{border-color:var(--accent)}
 .tbt{font-family:var(--font-hd);font-weight:700;font-size:15px;min-width:0;
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .veu{position:fixed;inset:0;background:rgba(3,4,8,.62);z-index:38;border:0}

 /* --------------------------------------------------- cabeçalho da página */
 .pgh{border-bottom:1px solid var(--line);
   background:radial-gradient(900px 260px at 12% -60%,rgba(245,196,81,.10),transparent 70%),
              var(--card2)}
 .pgh .pghin{padding-block:20px 18px}
 .crumbs{font-size:11.5px;color:var(--dim);display:flex;flex-wrap:wrap;gap:5px;
   align-items:center;margin-bottom:7px}
 .crumbs a{color:var(--muted);text-decoration:none} .crumbs a:hover{color:var(--accent)}
 .crumbs b{color:var(--ink2);font-weight:600}
 .crumbs i{font-style:normal;color:var(--line2)}
 .pgtop{display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap}
 .pgtit{min-width:0;flex:1 1 320px}
 h1.pgt{margin:0;font-size:clamp(21px,2.6vw,27px);font-weight:700;letter-spacing:-.025em}
 .pgsub{margin:5px 0 0;color:var(--muted);font-size:13px;line-height:1.55;max-width:78ch}
 .pgsub b{color:var(--ink2)} .pgsub a{color:var(--accent)}
 .pgacts{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-left:auto}

 /* ----------------------------------------------- componentes partilhados */
 .seg{display:inline-flex;flex-wrap:wrap;gap:4px;padding:4px;border-radius:12px;
   background:var(--card2);border:1px solid var(--line)}
 .seg button,.seg a{appearance:none;border:0;background:transparent;color:var(--muted);
   font:inherit;font-size:12.5px;font-weight:600;padding:7px 13px;border-radius:9px;
   cursor:pointer;min-height:36px;text-decoration:none;white-space:nowrap}
 .seg button:hover,.seg a:hover{color:var(--ink);background:var(--card)}
 .seg button.on,.seg a.on,.seg button[aria-selected="true"]{
   background:var(--accent-soft);color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent-line)}
 .btn{font:inherit;font-size:12.5px;font-weight:700;padding:8px 14px;border-radius:10px;
   border:1px solid var(--line2);background:var(--card);color:var(--ink2);cursor:pointer;
   min-height:38px;transition:.12s;text-decoration:none;display:inline-flex;
   align-items:center;gap:6px;justify-content:center}
 .btn:hover{border-color:var(--accent);color:var(--ink)}
 .btn.pri{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
 .btn.pri:hover{background:#ffd671;color:var(--accent-ink)}
 .btn.on{background:var(--accent-soft);border-color:var(--accent-line);color:var(--accent)}
 .btn.sm{min-height:32px;padding:5px 11px;font-size:12px;border-radius:9px}
 .btn[disabled]{opacity:.5;cursor:default}
 .chip{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:600;
   padding:3px 10px;border-radius:999px;background:var(--card3);color:var(--muted);
   border:1px solid var(--line)}
 .chip.ok{background:#0f2a1c;color:var(--add);border-color:#1e4a33}
 .chip.gold{background:var(--accent-soft);color:var(--accent);border-color:var(--accent-line)}
 .chip.info{background:var(--info-soft);color:var(--ob);border-color:#25406b}
 .vazio{color:var(--muted);font-size:13px;background:var(--card2);
   border:1px dashed var(--line2);border-radius:var(--r);padding:16px 18px}
 .vazio code{background:var(--bg);padding:1px 5px;border-radius:5px;font-size:12px}
 .pgft{border-top:1px solid var(--line);background:var(--card2);color:var(--dim);
   font-size:12px;line-height:1.65}
 .pgft .pghin{padding-block:18px 30px}
 .pgft b{color:var(--muted)} .pgft a{color:var(--muted)}
 .pgft code{background:var(--bg);padding:1px 5px;border-radius:5px}
 /* «COMO LER ESTA PÁGINA» (2.ª passagem, 2026-09-24). O rodapé da Deckboxes eram
    dezoito linhas de explicação abertas no fim de todas as vistas — texto que se
    lê UMA vez e depois é só distância até ao fim da página. Fechado por
    omissão, com o `<summary>` a dizer que está lá. */
 .pgft details.comoler>summary{cursor:pointer;list-style:none;display:inline-flex;
   align-items:center;gap:7px;color:var(--muted);font-weight:700;font-size:12.5px;
   padding:7px 12px;border:1px solid var(--line2);border-radius:10px;
   background:var(--card);min-height:36px}
 .pgft details.comoler>summary::-webkit-details-marker{display:none}
 .pgft details.comoler>summary:hover{border-color:var(--accent);color:var(--ink2)}
 .pgft details.comoler>summary svg.ico{opacity:.9;margin:0}
 .pgft details.comoler[open]>summary{margin-bottom:12px}
 .pgft details.comoler .cltx{max-width:92ch}

 /* ÍNDICE VERTICAL: a alternativa às filas de botões que corriam para o lado.
    Em ecrã largo fica numa coluna à esquerda do conteúdo; no telemóvel vira um
    `<select>` (é o `vindexHTML` do `deckboxes.js` que o desenha). */
 /* 216 px e não 238 (2.ª passagem, 2026-09-24): o índice deixou de repetir as
    vistas que já estão na barra lateral e ficou só com os NOMES das caixas —
    cabem em menos, e o que sobra é largura para o conteúdo. */
 .comidx{display:grid;grid-template-columns:216px minmax(0,1fr);gap:20px;
   align-items:start}
 .vidx{position:sticky;top:12px;max-height:calc(100vh - 24px);overflow-y:auto;
   scrollbar-width:thin;background:var(--card2);border:1px solid var(--line);
   border-radius:var(--r2);padding:8px}
 .vidx .vgh{padding:9px 10px 5px;font-size:10px;font-weight:700;letter-spacing:.11em;
   text-transform:uppercase;color:var(--dim)}
 .vidx button,.vidx a{display:flex;width:100%;text-align:left;gap:8px;align-items:center;
   appearance:none;border:0;background:transparent;color:var(--ink2);font:inherit;
   font-size:13px;font-weight:600;padding:7px 10px;border-radius:9px;cursor:pointer;
   min-height:36px;text-decoration:none;line-height:1.25}
 .vidx button:hover,.vidx a:hover{background:var(--card);color:var(--ink)}
 .vidx button.on,.vidx a.on{background:var(--accent-soft);color:var(--accent);
   box-shadow:inset 2px 0 0 var(--accent)}
 .vidx .vtx{min-width:0;flex:1}
 .vidx .vtx small{display:block;font-size:11px;font-weight:500;color:var(--dim);
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .vidx button.on .vtx small{color:#b9a066}
 .vidx .ic{flex:none;width:18px;display:flex;align-items:center;justify-content:center;
   color:var(--muted);font-size:13px}
 .vidx button.on .ic,.vidx a.on .ic{color:var(--accent)}
 .vidxsel{display:none;margin:0 0 12px}
 .vidxsel .vlbl{display:block;font-size:10px;font-weight:700;letter-spacing:.11em;
   text-transform:uppercase;color:var(--dim);margin-bottom:5px}
 .selc,select.selc{background:var(--card);color:var(--ink);border:1px solid var(--line2);
   border-radius:10px;font:inherit;font-size:13px;font-weight:600;padding:9px 12px;
   min-height:40px;width:100%;max-width:100%;cursor:pointer}

 /* ------------------------------------------------------------ telemóvel */
 @media (max-width:899px){
   :root{--sticky:57px}
   .topbar{display:flex}
   .side{position:fixed;inset:0 auto 0 0;transform:translateX(-102%);
     transition:transform .18s ease;box-shadow:var(--sombra);width:min(86vw,var(--side))}
   body.menu-on .side{transform:none}
   body:not(.menu-on) .veu{display:none}
   body.menu-on{overflow:hidden}
   .comidx{grid-template-columns:minmax(0,1fr);gap:12px}
   .vidx{display:none}
   .vidxsel{display:block}
   .pgh .pghin{padding-block:16px 14px}
   .wrap{padding-block:16px 60px}
   .pgacts{margin-left:0;width:100%}
   /* ALVOS DE TOQUE (a decisão de 2026-09-18, que só valia para a Deckboxes e
      só a 640 px: *"ele vai estar à frente da estante com o telemóvel"*).
      Passou para a casca e para os 900 px — o `.cpbtn` de 11 px do Metagame
      era um alvo de 22 px numa página que ele abre no telemóvel tal como a
      outra. */
   .btn,.cpbtn,.seg button,.seg a,.selc,select.selc,button.cp{min-height:40px}
   .btn.sm{min-height:36px}
   .sli.sub{min-height:38px}
   .casa{min-height:32px}
   /* O selector de edição da Cobertura fica nos 34 px, e não nos 40: são 199
      numa página só, e levá-los a 40 acrescentava ~1 600 px de altura a uma
      lista que já é longa. É um compromisso assumido, não um esquecimento. */
   select.pick{min-height:34px}
 }
 @media (min-width:900px){ .veu{display:none} }
 @media print{
   .side,.topbar,.veu,.salta,.pgacts,.pgft{display:none!important}
   .shell{display:block} body{background:#fff;color:#000}
 }
"""

# O JavaScript da casca: abrir/fechar o painel de navegação no telemóvel e
# marcar o item da sub-vista activa pelo `location.hash`. É defensivo de
# propósito — o `tests/abrir_pagina.js` corre as páginas num DOM de mentira.
JS = r"""
(function(){
  var b = document.body, side = document.getElementById('side'),
      bt = document.getElementById('menub'), veu = document.getElementById('veu');
  function fecha(){ if(!b||!b.classList) return; b.classList.remove('menu-on');
    if(bt&&bt.setAttribute) bt.setAttribute('aria-expanded','false'); }
  function abre(){ if(!b||!b.classList) return; b.classList.add('menu-on');
    if(bt&&bt.setAttribute) bt.setAttribute('aria-expanded','true');
    if(side&&side.focus) try{ side.focus(); }catch(e){} }
  if(bt&&bt.addEventListener) bt.addEventListener('click', function(){
    (b.classList && b.classList.contains('menu-on')) ? fecha() : abre(); });
  if(veu&&veu.addEventListener) veu.addEventListener('click', fecha);
  if(document.addEventListener) document.addEventListener('keydown', function(e){
    if(e && e.key === 'Escape') fecha(); });
  /* Um toque num link do menu fecha o painel — senão, no telemóvel, ele ficava
     por cima da página a que acabou de chegar. */
  var links = document.querySelectorAll ? document.querySelectorAll('.sidenav a') : [];
  for (var i = 0; i < links.length; i++) {
    if (links[i].addEventListener) links[i].addEventListener('click', fecha);
  }
  /* A sub-vista activa: o `#comprar` da barra lateral acende quando a Deckboxes
     está nessa aba. Sem isto, os itens da última secção apontavam todos para a
     página em que ele já está, sem dizer qual estava aberta. */
  function marcaHash(){
    var h = '';
    try { h = (location.hash || '').replace('#',''); } catch(e){}
    var subs = document.querySelectorAll ? document.querySelectorAll('.sli.sub') : [];
    for (var i = 0; i < subs.length; i++) {
      var s = subs[i];
      if (!s.classList || !s.dataset) continue;
      s.classList.toggle('cur', !!h && s.dataset.ancora === h);
    }
  }
  if (window.addEventListener) window.addEventListener('hashchange', marcaHash);
  marcaHash();
  window.marcaSubVista = marcaHash;
})();
"""


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def head(titulo: str, css_pagina: str = "", extra: str = "") -> str:
    """O `<head>` inteiro: meta, fontes, título e o CSS (tokens → página → casca).

    A ORDEM importa: a casca vem por último para ter a última palavra sobre o
    que é partilhado (o layout, os botões, as tabelas). Era ao contrário e o
    `.tabs a.cur` de cada página pintava por cima da barra lateral.
    """
    return (f"{META}\n{FONTES}\n<title>{html.escape(titulo)} · mtgvault</title>\n"
            f"<style>\n{TEMA}\n{css_pagina}\n{CSS}\n</style>{extra}")


def _item(f: str, ancora: str, ic: str, rot: str, nota: str, atual: str) -> str:
    href = f + (f"#{ancora}" if ancora else "")
    cur = (not ancora) and f == atual
    cls = "sli" + (" sub" if ancora else "") + (" cur" if cur else "")
    dat = f' data-ancora="{html.escape(ancora)}"' if ancora else ""
    aria = ' aria-current="page"' if cur else ""
    nt = f'<small>{html.escape(nota)}</small>' if nota else ""
    return (f'<a class="{cls}" href="{href}"{dat}{aria}>'
            f'<span class="ic">{icone(ic, 17 if ancora else 18)}</span>'
            f'<span class="tx">{html.escape(rot)}{nt}</span></a>')


def nav_lateral(atual: str = "") -> str:
    """A navegação, agrupada por secções. A mesma no PC e no painel do telemóvel."""
    out = ""
    for sec, itens in seccoes():
        cab = (f'<div class="sgh">{html.escape(sec)}</div>' if sec else "")
        out += ('<div class="sgrp">' + cab
                + "".join(_item(*it, atual) for it in itens) + "</div>")
    return out


def barra(atual: str = "") -> str:
    """A barra lateral inteira (marca, navegação, rodapé)."""
    return (
        '<aside class="side" id="side" tabindex="-1" aria-label="Navegação do site">'
        '<div class="sidetop">'
        f'<a class="casa" href="{CASA[0]}">← {html.escape(CASA[1])}</a>'
        '<a class="marca" href="index.html">'
        '<span class="mk" aria-hidden="true">M</span>'
        '<span><b>mtgvault</b><small>coleção do Prime</small></span></a>'
        '</div>'
        f'<nav class="sidenav">{nav_lateral(atual)}</nav>'
        '<div class="sidept">Atualiza sozinho todos os dias · '
        '<a href="https://github.com/Baverone/mtgvault">repositório</a></div>'
        '</aside>')


def migalhas(atual: str, titulo: str) -> str:
    sec = seccao_de(atual)
    meio = (f'<i>›</i><span>{html.escape(sec)}</span>' if sec else "")
    if atual == "index.html":
        return f'<nav class="crumbs" aria-label="Migalhas"><b>{html.escape(titulo)}</b></nav>'
    return ('<nav class="crumbs" aria-label="Migalhas">'
            '<a href="index.html">Início</a>'
            f'{meio}<i>›</i><b>{html.escape(titulo)}</b></nav>')


def abrir(atual: str, titulo: str, subtitulo: str = "", accoes: str = "",
          id_sub: str = "") -> str:
    """Tudo o que vem antes do conteúdo: barra lateral, barra de topo, cabeçalho.

    `subtitulo` e `accoes` vão como HTML (é texto nosso, com `<b>` e links).
    `id_sub` é o id de um elemento que a página preenche por JavaScript com o
    subtítulo vivo (a Deckboxes escreve lá os números do dia).
    """
    sub = (f'<p class="pgsub" id="{id_sub}">{subtitulo}</p>' if id_sub
           else (f'<p class="pgsub">{subtitulo}</p>' if subtitulo else ""))
    acts = f'<div class="pgacts">{accoes}</div>' if accoes else ""
    return (
        '<a class="salta" href="#conteudo">Saltar para o conteúdo</a>'
        '<div class="shell">'
        + barra(atual) +
        '<button class="veu" id="veu" type="button" aria-label="Fechar o menu"></button>'
        '<div class="mainc">'
        '<header class="topbar">'
        '<button class="menub" id="menub" type="button" aria-expanded="false" '
        'aria-controls="side">' + icone("menu", 17) + '<span>Menu</span></button>'
        f'<span class="tbt">{html.escape(titulo)}</span></header>'
        '<div class="pgh"><div class="pghin">'
        + migalhas(atual, titulo) +
        '<div class="pgtop"><div class="pgtit">'
        f'<h1 class="pgt">{html.escape(titulo)}</h1>{sub}</div>{acts}</div>'
        '</div></div>'
        '<main id="conteudo" tabindex="-1">')


# Acima deste tamanho um rodapé deixa de ser uma nota e passa a ser um texto: o
# da Deckboxes tem ~1 200 caracteres e era a coisa mais comprida da página
# depois das cartas. O limiar é generoso de propósito — um rodapé de duas linhas
# escondido atrás de um botão é pior do que rodapé nenhum.
RODAPE_LONGO = 320


def fechar(rodape: str = "", scripts: str = "", recolher: bool | None = None) -> str:
    """O fim: fecha o conteúdo, escreve o rodapé e liga o JavaScript da casca.

    *"Rodapés explicativos longos: passa para um bloco «Como ler esta página»
    recolhível, fechado por defeito"* (André, 2.ª passagem, 2026-09-24). Quem
    decide é o TAMANHO (`RODAPE_LONGO`), e não cada gerador a lembrar-se — era
    assim que o `cobertura.html` ficava para trás de cada vez que a casca mudava.
    `recolher=True/False` força, para quem tenha razão para o fazer.
    """
    if not rodape:
        return '</main></div></div>' + scripts + f'<script>{JS}</script>'
    longo = len(rodape) > RODAPE_LONGO if recolher is None else recolher
    if longo:
        corpo = ('<details class="comoler"><summary>'
                 + icone("ajuda", 16) + '<span>Como ler esta página</span>'
                 f'</summary><div class="cltx">{rodape}</div></details>')
    else:
        corpo = rodape
    ft = f'<footer class="pgft"><div class="pghin">{corpo}</div></footer>'
    return ('</main>' + ft + '</div></div>' + scripts
            + f'<script>{JS}</script>')
