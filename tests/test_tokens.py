"""OS TOKENS VÊM DE UM SÍTIO SÓ (André, 2026-10-04).

*"Um so conjunto de tokens — cores, escala tipografica, espacamento, raios,
sombras — definido num sitio e usado por TODAS as paginas. Hoje cada pagina tem
o seu CSS; isso acaba."*

A premissa dele estava meio certa, e a medição vale mais do que a frase: a casca
partilhada existe desde 2026-09-24 (`site_shell.TEMA` + `site_shell.CSS`) e
todas as páginas já a usam. O que NÃO existia era um conjunto COMPLETO: ficavam
**297 valores de cor escritos à mão** em 9 ficheiros, **136 deles distintos** —
quatro cinzentos de painel quase iguais, três laranjas de aviso, dois azuis de
«está noutra caixa». Era essa a deriva que ele via de página para página.

O que estes casos trancam:

  1. **os tokens de estado existem, e só na casca** — nenhuma página os
     redefine;
  2. **todo o `var(--x)` que uma página usa está DEFINIDO** na casca. É o caso
     que apanha um erro de escrita (`var(--ok-lin)`), que no CSS não dá erro
     nenhum: a propriedade é simplesmente ignorada e a cor vem do que estiver
     por trás. É o padrão do `event_tier` aplicado à cor;
  3. **os estados de erro/vazio/carregamento não têm uma cor escrita à mão** —
     são os três ecrãs que o site tem de desenhar bem, e eram os que tinham
     mais valores soltos;
  4. **a deriva não pode CRESCER**: há um tecto no número de cores à mão. Não é
     zero, e isso é honesto — ver `PORQUE_NAO_ZERO`.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from mtgvault import paginas  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402

# As páginas que geram HTML e têm CSS próprio.
GERADORES = ["inicio.py", "decks.py", "deckboxes.py", "arrumacao.py",
             "comandantes.py", "colecao_cor.py", "collection_gallery.py",
             "caixarl.py", "reservedlist.py", "meta_coverage.py",
             "metagame.py", "showcase.py", "mtgvault/paginas.py"]

RX_COR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RX_VAR = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")
RX_DEF = re.compile(r"(--[a-z0-9-]+)\s*:")

# O TECTO. A 2026-10-04 eram 297 cores à mão; a conversão explícita baixou-as
# para 155. O tecto é esse número: não se exige zero, e a razão está escrita.
TECTO_CORES = 155

PORQUE_NAO_ZERO = """
Porque é que o tecto não é zero (medido em `_revisao/tokens_mapa.py` antes de se
decidir): uma troca automática do resto tem quatro modos de falhar, e os quatro
mordem nesta base —

  (a) `#000d`, `#0009`, `#000b` são hex com ALFA (sombras, véus, o fundo de um
      modal). Trocá-los por um token opaco tapava a página;
  (b) a matiz de uma cor quase negra é instável: o `#0c0f14`, que é uma
      superfície neutra, classifica-se como «azul» e arrastava 24 valores com
      ele para um tom de informação que não é o dele;
  (c) o valor dominante de uma família redefinia tokens que já existem — o
      `--line2` passava de `#2c3243` a `#5a6472` e mudava TODAS as bordas do
      site;
  (d) a banda de «texto» vai do `#fff` ao `#79c9c4`: o branco de um botão caía
      em `--ink2` e ficava cinzento.

O que sobra são, em grande parte, cores em que a cor É o dado e não o estilo: as
cinco de ESTADO de um deck no `colecao_cor` (uma por palavra da legenda), as
cores de identidade de Magic, e os hex com alfa. Converter esses é uma ordem
própria, com capturas antes e depois — não um `sub()` por cima de 155 valores.
""".strip()


def _texto(f):
    return (RAIZ / f).read_text(encoding="utf-8")


def _tokens_da_casca():
    """Os tokens que a casca DEFINE (no `TEMA` e no `CSS`)."""
    return set(RX_DEF.findall(shell.TEMA)) | set(RX_DEF.findall(shell.CSS))


def caso_os_tokens_de_estado_vivem_na_casca():
    """Os trios de estado (fundo / linha / texto) estão no `TEMA`, e só lá."""
    tema = shell.TEMA
    for t in ("--ok", "--ok-soft", "--ok-line",
              "--info", "--info-soft", "--info-line",
              "--warn-soft", "--warn-line", "--warn-forte",
              "--bad", "--bad-soft", "--bad-line", "--bad-ink",
              "--sunken", "--accent", "--accent-soft", "--accent-line"):
        assert f"{t}:" in tema, f"o token {t} saiu do TEMA da casca"
    # e nenhuma página os redefine por baixo
    for f in GERADORES:
        if f.endswith("paginas.py"):
            continue
        t = _texto(f)
        for tok in ("--ok-soft", "--bad-soft", "--warn-soft", "--sunken",
                    "--info-soft", "--bad-line", "--ok-line"):
            assert f"{tok}:" not in t, (f, tok, "uma página redefiniu um token")
    print("os tokens de estado vivem na casca, e nenhuma pagina os redefine")


def caso_todo_o_var_usado_esta_definido():
    """Um `var(--x)` por um token que não existe **não dá erro no CSS**.

    A propriedade é ignorada em silêncio e a cor vem do que estiver por trás —
    o padrão do `event_tier` aplicado à cor. Este caso apanha o erro de escrita
    no instante em que ele entra.
    """
    definidos = _tokens_da_casca()
    assert "--accent" in definidos and "--ok-soft" in definidos, definidos
    maus = {}
    for f in GERADORES:
        for tok in set(RX_VAR.findall(_texto(f))):
            if tok not in definidos:
                maus.setdefault(f, set()).add(tok)
    # o `site_shell` usa `--sticky`/`--side`/`--maxw`, que também define
    assert not maus, ("ha var(--x) por tokens que a casca nao define", maus)
    print(f"as {len(definidos)} variaveis usadas pelas paginas estao todas definidas")


def caso_os_estados_de_erro_e_carregamento_nao_tem_cor_a_mao():
    """Os três ecrãs que o site tem de desenhar bem: vazio, a carregar, erro."""
    css = paginas.CSS_DADOS
    cores = RX_COR.findall(css)
    assert not cores, ("o CSS dos dados voltou a ter cor escrita a mao", cores)
    # e usa mesmo os tokens do estado de erro
    for tok in ("--bad-soft", "--bad-line", "--bad-ink", "--bad"):
        assert f"var({tok})" in css, (tok, "o estado de erro deixou de usar o token")
    # o estado VAZIO vive na casca e também é por tokens
    i = shell.CSS.index(".vazio{")
    bloco = shell.CSS[i:i + 400]
    assert not RX_COR.findall(bloco), ("o estado vazio tem cor a mao", bloco[:200])
    print("os estados de vazio/carregamento/erro sao todos por tokens")


def caso_a_deriva_de_cores_nao_cresce():
    """Tecto no número de cores escritas à mão. Ver `PORQUE_NAO_ZERO`."""
    total, por_ficheiro = 0, {}
    for f in GERADORES:
        n = len(RX_COR.findall(_texto(f)))
        por_ficheiro[f] = n
        total += n
    assert total <= TECTO_CORES, (
        f"as cores escritas a mao subiram para {total} (tecto {TECTO_CORES}). "
        f"Usa um token do site_shell.TEMA em vez de um hex novo.", por_ficheiro)
    print(f"{total} cores a mao (tecto {TECTO_CORES}) — a deriva nao cresceu")


def caso_a_escala_nao_e_so_cor():
    """Raios, sombras e larguras também vivem num sítio — o pedido dele fala de
    *"cores, escala tipografica, espacamento, raios, sombras"*."""
    for t in ("--r:", "--r2:", "--sombra:", "--maxw:", "--side:", "--sticky:",
              "--font:", "--font-hd:"):
        assert t in shell.TEMA, f"{t} saiu do TEMA"
    print("raios, sombras, larguras e tipos de letra tambem vem do TEMA")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for c in CASOS:
        c()
    print("\nTUDO OK")
