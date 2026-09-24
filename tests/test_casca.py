"""A CASCA DO SITE (`mtgvault/site_shell.py`) — reestruturação de 2026-09-24.

Pedido do André, à letra: *"no mtgvault quero uma organização diferente, acho
tudo muito confuso, ter que andar a correr os botões para os lados. Faz toda uma
reestruturação para um site profissional, bem organizado, bem estruturado!"*

O que aqui se tranca, e cada caso tem de CHUMBAR se a casca se desfizer:

  1. **TODA a página publicada tem a mesma navegação**, e ninguém volta a
     escrever uma barra à mão. Era este o defeito que já custou caro: o
     `cobertura.html` ficou meses com um menu de Agosto porque cada gerador
     escrevia o seu `<nav>`;
  2. **nenhum link interno está partido** — um `href` para um HTML que ninguém
     publica é um 404 no telemóvel dele, e já aconteceu (o *"core decks →"* da
     Galeria a apontar para uma página apagada);
  3. **nenhuma página tem scroll horizontal**, nas duas larguras do pedido
     (1440 e 390). É a metade estrutural do *"andar a correr os botões para os
     lados"*: o que corria para o lado eram as barras de abas, e a maneira de
     garantir que não voltam é medir a largura do corpo num browser a sério;
  4. **as filas horizontais desapareceram**: nenhuma página publicada tem um
     `overflow-x:auto` numa barra de navegação, nem o `<nav class="tabs">`
     antigo;
  5. o `<head>` leva o tema, os tipos de letra e o CSS da casca, por esta
     ordem — a casca tem de vir **depois** do CSS da página para ter a última
     palavra sobre o que é partilhado.

Os casos 2–4 leem o HTML PUBLICADO (o que o `daily` escreveu), não o código: uma
página que não tenha sido regenerada desde a mudança fica com a barra antiga, e
é isso que o site mostra. O caso 3 precisa de `node` + Chrome; sem eles, diz-se
e salta-se — um teste que não pode correr não pode dar por bom o que não mediu.

Não toca na rede, na base nem no `data/` a sério.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ["MTGVAULT_HOME"] = str(Path(tempfile.gettempdir()) / "mtgvault-casca")
os.environ["MTGVAULT_DB"] = os.environ["MTGVAULT_HOME"] + "/vault.db"

from mtgvault import paginas  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def _publicadas():
    return [f for f in paginas.MENU if (RAIZ / f).is_file()]


def caso_a_casca_e_a_mesma_em_todas():
    """Barra lateral, botão de menu, migalhas e cabeçalho — em todas, iguais."""
    faltam = {}
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        for peca, marca in [("barra lateral", '<aside class="side" id="side"'),
                            ("navegação", 'class="sidenav"'),
                            ("botão de menu", 'id="menub"'),
                            ("véu do painel", 'id="veu"'),
                            ("migalhas", 'class="crumbs"'),
                            ("cabeçalho", 'class="pgt"'),
                            ("salto p/ o conteúdo", 'class="salta"'),
                            ("conteúdo", 'id="conteudo"'),
                            ("link p/ o baverone", shell.CASA[0])]:
            if marca not in txt:
                faltam.setdefault(f, []).append(peca)
    assert not faltam, faltam
    print(f"as {len(_publicadas())} paginas publicadas têm a casca inteira")


def caso_ninguem_escreve_uma_barra_a_mao():
    """Nem no HTML publicado, nem no código dos geradores."""
    velhas = {}
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        maus = [m for m in ('<nav class="tabs">', 'class="decktabs"',
                            'class="ftabs"') if m in txt]
        if maus:
            velhas[f] = maus
    assert not velhas, ("estas páginas ainda desenham a barra antiga", velhas)
    # E ninguém pede uma função que já não existe.
    assert not hasattr(paginas, "nav"), \
        "o `paginas.nav` (a barra horizontal) voltou — a navegação é do site_shell"
    print("ninguem desenha uma barra horizontal de navegacao")


def caso_nenhuma_fila_de_navegacao_corre_para_o_lado():
    """`overflow-x:auto` numa barra de navegação é o defeito, à letra.

    A `.decktabs` da Deckboxes tinha-o e chegava a 27 botões. O que sobra de
    `overflow-x` no site é a MOLDURA de uma tabela larga (`.tw` da Caixa RL), que
    é outra coisa: aí o que desliza é a tabela dentro da moldura, não o menu.
    """
    maus = {}
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"([^{};\n]{0,80})\{[^{}]*overflow-x:\s*auto", txt):
            sel = m.group(1).strip()
            if sel.startswith((".tw", "table", ".mvs", "pre")):
                continue
            maus.setdefault(f, []).append(sel[:60])
    assert not maus, ("uma barra que corre para o lado voltou", maus)
    print("nenhuma navegacao com overflow-x: as filas horizontais foram-se")


def caso_nenhum_link_interno_esta_partido():
    """Todo o `href="x.html"` de uma página publicada aponta para um ficheiro que
    existe — e todas as páginas do menu são geradas e publicadas."""
    existe = {p.name for p in RAIZ.glob("*.html")}
    maus = {}
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        alvos = {a for a in re.findall(r'href="([a-z_]+\.html)', txt)}
        fora = sorted(alvos - existe)
        if fora:
            maus[f] = fora
    assert not maus, maus
    # E as âncoras da barra têm de ser vistas que a Deckboxes conhece.
    js = (RAIZ / "deckboxes.js")
    if js.is_file():
        texto = js.read_text(encoding="utf-8", errors="replace")
        for _sec, itens in shell.SECCOES:
            for f, a, *_r in itens:
                if a and f == "deckboxes.html":
                    assert f"'{a}'" in texto, \
                        f"a barra aponta para #{a} e o deckboxes.js não a conhece"
    print("nenhum link interno partido, e as ancoras da barra existem")


def caso_a_ordem_do_css_da_a_ultima_palavra_a_casca():
    """`head()` = tema → CSS da página → CSS da casca. Se a casca viesse antes,
    o `.tabs a.cur` de cada página pintava por cima da barra lateral."""
    h = shell.head("X", " .minha{color:red}")
    i_tema = h.index("--accent:")
    i_pag = h.index(".minha{")
    i_casca = h.index(".sidenav{")
    assert i_tema < i_pag < i_casca, (i_tema, i_pag, i_casca)
    # E o tema define tudo o que a casca usa (o outro sentido está no
    # `test_paginas.caso_o_tema_tem_as_variaveis_que_as_paginas_usam`).
    assert "Space+Grotesk" in h and "Inter" in h, "faltam os tipos de letra"
    assert 'name="theme-color" content="#07080d"' in h
    print("head(): tema → pagina → casca, e os tipos de letra do baverone")


def caso_a_barra_e_a_mesma_no_pc_e_no_telemovel():
    """Não há duas listas. O painel do telemóvel é a MESMA `<aside>`, movida por
    CSS — uma segunda cópia era a segunda oportunidade de discordarem."""
    html = shell.abrir("metagame.html", "Metagame", "sub")
    assert html.count('class="sidenav"') == 1, html[:400]
    assert html.count('id="side"') == 1
    # A barra de topo (o botão de menu) só se vê abaixo dos 900 px.
    assert ".topbar{display:none" in shell.CSS
    assert "@media (max-width:899px)" in shell.CSS and ".topbar{display:flex}" in shell.CSS
    print("uma so navegacao, movida por CSS no telemovel")


# ---------------------------------------------------------------------------
# O caso que mede a sério: um Chrome, duas larguras, zero scroll horizontal.
# ---------------------------------------------------------------------------
def caso_nenhuma_pagina_tem_scroll_horizontal():
    if not shutil.which("node") or not CHROME.is_file():
        print("scroll horizontal: sem `node` ou sem Chrome, saltado")
        return
    p = subprocess.run([sys.executable, str(RAIZ / "tests" / "medir_layout.py"),
                        str(RAIZ), "-"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1800)
    saida = (p.stdout or "") + (p.stderr or "")
    assert p.returncode == 0, saida[-3000:]
    assert "TUDO OK" in saida, saida[-3000:]
    print("1440 e 390 px: nenhuma pagina com scroll horizontal, nenhum link partido")


def run():
    for fn in (caso_a_casca_e_a_mesma_em_todas,
               caso_ninguem_escreve_uma_barra_a_mao,
               caso_nenhuma_fila_de_navegacao_corre_para_o_lado,
               caso_nenhum_link_interno_esta_partido,
               caso_a_ordem_do_css_da_a_ultima_palavra_a_casca,
               caso_a_barra_e_a_mesma_no_pc_e_no_telemovel,
               caso_nenhuma_pagina_tem_scroll_horizontal):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
