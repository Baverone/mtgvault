"""O menu e o tema partilhados (`mtgvault/paginas.py`).

Duas coisas que já correram mal em silêncio e que aqui ficam trancadas:

  1. **uma página fora do menu.** O `cobertura.html` ficou meses com um menu de
     Agosto — sem *Deckboxes* e sem *Metagame* — porque cada gerador escrevia o
     seu `<nav>` à mão. Uma página órfã não dá erro: só deixa de se lá chegar;
  2. **uma página que ninguém publica.** Toda a página do menu tem de estar no
     `git add` do `daily.yml` *e* na lista do `ai-pc/tasks/mtgvault-daily`. Se
     faltar num dos dois, o site fica com uma versão antiga e não avisa — foi o
     que aconteceu ao `deckboxes.html` no job do PC.

Não toca na rede nem na base de dados.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mtgvault import paginas  # noqa: E402


def caso_o_menu_marca_a_pagina_actual():
    nav = paginas.nav("deckboxes.html")
    assert nav.count('class="cur"') == 1, nav
    assert 'class="cur" href="deckboxes.html"' in nav
    # E sem página actual não há nenhuma marcada (é o caso do índice).
    assert 'class="cur"' not in paginas.nav("")
    print("o menu marca a pagina actual, e so uma")


def caso_o_menu_tem_todas_as_paginas():
    nav = paginas.nav("index.html", extra=True)
    for f, _i, _t in paginas.MENU + paginas.EXTRA:
        assert f'href="{f}"' in nav, f
    print("o menu leva a todas as paginas, principais e secundarias")


def caso_todas_as_paginas_do_menu_sao_publicadas():
    """Uma página do menu que ninguém faz `git add` fica congelada no site."""
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    publicadas = set(re.findall(r"[a-z_]+\.html", linha))
    for f, _i, _t in paginas.MENU:
        if f == "index.html":
            continue           # o índice é escrito à mão, não é gerado
        assert f in publicadas, f"{f} não vai ao `git add` do daily.yml"
    print("todas as paginas do menu vao ao git add do workflow")


def caso_o_tema_tem_as_variaveis_que_as_paginas_usam():
    """O `TEMA` é um superconjunto: se uma página usa `var(--x)` e o tema não o
    define, a cor cai para o valor por omissão do browser — texto preto em fundo
    preto, sem erro nenhum."""
    definidas = set(re.findall(r"--([a-z0-9]+):", paginas.TEMA))
    faltam = {}
    for py in sorted(RAIZ.glob("*.py")):
        txt = py.read_text(encoding="utf-8", errors="replace")
        if "%TEMA%" not in txt and "paginas.TEMA" not in txt:
            continue
        usadas = set(re.findall(r"var\(--([a-z0-9]+)", txt))
        # `--r`/`--r2` (os raios dos cantos) são do deckboxes e ficam lá.
        em_falta = usadas - definidas - {"r", "r2"}
        if em_falta:
            faltam[py.name] = sorted(em_falta)
    assert not faltam, faltam
    print("o tema define todas as variaveis que as paginas pedem")


def run():
    for fn in (caso_o_menu_marca_a_pagina_actual, caso_o_menu_tem_todas_as_paginas,
               caso_todas_as_paginas_do_menu_sao_publicadas,
               caso_o_tema_tem_as_variaveis_que_as_paginas_usam):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
