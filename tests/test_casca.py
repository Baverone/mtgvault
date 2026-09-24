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
# A 2.ª PASSAGEM (revisão de 2026-09-24): navegação sem duplicação, um conjunto
# único de ícones, rodapés longos recolhidos e ortografia do Acordo.
# ---------------------------------------------------------------------------
def caso_o_indice_da_deckboxes_nao_repete_a_barra_lateral():
    """*"Hoje há duas colunas de navegação lado a lado (...) tira do índice
    interno tudo o que já está na barra lateral"*.

    O índice interno é desenhado em JavaScript (`deckboxes._filaDeAbas`), por
    isso quem aqui se lê é o TEXTO do `deckboxes.js`: as vistas que a barra
    lateral leva não podem voltar a ser itens do índice. A prova de que o índice
    desenha mesmo só as caixas está no `test_montados
    .caso_as_abas_de_cada_deck_ficam_agrupadas`, que corre o JS num `node`.
    """
    import deckboxes                                       # noqa: PLC0415
    js = deckboxes.js_texto()
    inicio = js.index("function _filaDeAbas()")
    fim = js.index("function renderTabs()")
    fila = js[inicio:fim]
    # As âncoras que a barra lateral já leva
    da_barra = {a for _sec, itens in shell.SECCOES
                for f, a, *_r in itens if a and f == "deckboxes.html"}
    assert da_barra, "a barra deixou de ter sub-vistas da Deckboxes"
    repetidas = sorted(a for a in da_barra if f"['{a}'," in fila)
    assert not repetidas, ("o índice interno voltou a repetir a barra lateral",
                           repetidas)
    # E o que NÃO está na barra continua a ter por onde se chegar lá.
    for a in ("todas", "sugestoes", "partilhadas", "naoenc"):
        assert f"['{a}'," in fila, f"a vista #{a} ficou sem entrada em lado nenhum"
    print("o indice interno da Deckboxes ficou so com as caixas")


def caso_ha_um_so_conjunto_de_icones():
    """Ícones SVG `outline`, traço 1.8, cor herdada — e o MESMO conjunto no
    Python e no JavaScript. Dois conjuntos era a segunda oportunidade de
    discordarem, a lição do `e_foil` e do `vistoId`."""
    import deckboxes                                       # noqa: PLC0415
    svg = shell.icone("comprar")
    assert svg.startswith('<svg class="ico"') and 'viewBox="0 0 24 24"' in svg
    assert shell.icone("nao-existe-isto") == "", "um nome errado tem de dar vazio"
    # O traço e a cor herdada vivem no CSS (é o que mantém a casca pequena).
    for regra in ("stroke:currentColor", "stroke-width:1.8", "fill:none"):
        assert regra in shell.CSS, regra
    # O conjunto do JavaScript é gerado do mesmo dicionário.
    js = deckboxes.js_texto()
    assert "const ICO = {" in js and "%JS_ICONES%" not in js
    for nome in ("comprar", "vender", "revalidacao", "arrumar"):
        assert f'"{nome}": "<svg' in js, nome
    # E as páginas publicadas usam-nos (a barra lateral leva um por item).
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        n = txt.count('<svg class="ico')       # «ico» ou «ico i15», «ico i21»…
        assert n >= 15, (f, n, "a barra lateral perdeu os ícones")
    print("um so conjunto de icones, no Python e no JavaScript")


def caso_a_barra_lateral_nao_tem_emojis():
    """A navegação é o sítio onde um emoji desenhado pelo sistema mais se nota:
    o mesmo item tinha um peso no telemóvel dele e outro no Chrome do PC."""
    emoji = re.compile("[\U0001F300-\U0001FAFF①-➿⬀-⯿☀-⛿]")
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        i = txt.index('<nav class="sidenav">')
        nav = txt[i:txt.index("</nav>", i)]
        achados = sorted(set(emoji.findall(nav)))
        assert not achados, (f, achados)
    # E os rótulos dizem o que são à primeira leitura, sem notas redundantes.
    rotulos = [rot for _s, itens in shell.SECCOES for _f, _a, _i, rot, _n in itens]
    assert len(rotulos) == len(set(rotulos)), ("dois itens com o mesmo rótulo",
                                               rotulos)
    for _sec, itens in shell.SECCOES:
        for _f, _a, _ic, rot, nota in itens:
            if nota:
                assert nota.lower() not in rot.lower(), (rot, nota)
    print("a barra lateral nao tem emojis, e nenhum rotulo se repete")


def caso_os_rodapes_longos_ficam_recolhidos():
    """*"Rodapés explicativos longos: passa para um bloco «Como ler esta página»
    recolhível, fechado por defeito."* Quem decide é o TAMANHO, para nenhum
    gerador ficar para trás."""
    longo = "x" * (shell.RODAPE_LONGO + 1)
    h = shell.fechar(longo)
    assert '<details class="comoler">' in h and "Como ler esta página" in h
    assert "<details open" not in h and 'class="comoler" open' not in h
    curto = shell.fechar("uma nota curta")
    assert "comoler" not in curto and "uma nota curta" in curto
    # E no HTML publicado: o rodapé da Deckboxes é o caso de que ele se queixou.
    txt = (RAIZ / "deckboxes.html").read_text(encoding="utf-8", errors="replace")
    i = txt.index('<footer class="pgft">')
    rod = txt[i:]
    assert '<details class="comoler">' in rod, "o rodapé da Deckboxes está aberto"
    assert "<details class=\"comoler\" open" not in rod
    print("os rodapes longos ficam num <details> fechado")


def caso_a_ortografia_e_a_do_acordo():
    """*"O site mistura «coleção» e «colecção», «atualizar» e «actualizar»."*

    Lê o HTML PUBLICADO, e só o TEXTO (fora das etiquetas): o `data-act=
    "actualizar"` é o nome de uma ação que o servidor compara literalmente, e o
    balde **`Colecção`** é um valor da base de dados — nenhum dos dois é texto
    que o site escreva, e por isso nenhum dos dois conta aqui.
    """
    velhas = re.compile(r"\b(colec[çc][ãõ]\w*|actualiz\w*|ac[çc][ãõ]\w*"
                        r"|selec[çc][ãõ]\w*|exac[t]\w*|excep[çc]\w*"
                        r"|correc[çc][ãõ]\w*|projec[çc][ãõ]\w*)", re.I)
    maus = {}
    for f in _publicadas():
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        texto = re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style)\b.*?</\1>",
                                               " ", txt))
        # O balde `Colecção` é um VALOR da base de dados (o nome da gaveta), não
        # texto que o site escreva: sai da conta enquanto lá estiver.
        achados = [m for m in velhas.findall(texto)
                   if m.lower() not in ("colecção",)]
        if achados:
            maus[f] = sorted(set(achados))[:8]
    assert not maus, ("ortografia fora do Acordo no texto visível", maus)
    print("o texto visivel das paginas publicadas segue o Acordo Ortografico")


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
               caso_o_indice_da_deckboxes_nao_repete_a_barra_lateral,
               caso_ha_um_so_conjunto_de_icones,
               caso_a_barra_lateral_nao_tem_emojis,
               caso_os_rodapes_longos_ficam_recolhidos,
               caso_a_ortografia_e_a_do_acordo,
               caso_nenhuma_pagina_tem_scroll_horizontal):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
