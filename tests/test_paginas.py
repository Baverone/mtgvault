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


def caso_o_registo_de_arquetipos_e_publicado():
    """O `data/arquetipos.json` tem de ir no `git add` — nas duas corridas.

    É a mesma armadilha das páginas, com outra roupa: o registo dá os nomes
    ESTÁVEIS aos arquétipos, e se ficasse só no PC a corrida do GitHub Actions
    via um registo vazio, reescrevia os nomes todos e commitava-os. Ninguém dava
    erro — os nomes é que voltavam a mudar de um dia para o outro, que é o
    defeito que ele veio corrigir.
    """
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert "data/arquetipos.json" in linha, \
        "o registo de arquétipos não vai ao `git add` do daily.yml"
    # E o registo não pode estar no `.gitignore` (o `data/` tem lá meia dúzia de
    # linhas, e uma delas a mais deixava o `git add` a falhar em silêncio).
    ignore = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/arquetipos.json" not in [l.strip() for l in ignore]
    print("o registo de arquetipos vai ao git add do workflow")


def caso_a_pagina_fundida_saiu_do_menu_mas_continua_publicada():
    """A *Decks permanentes* foi fundida na *Deckboxes* (v6). Duas coisas têm de
    ser verdade ao mesmo tempo: **sair do menu** (senão continuam duas páginas a
    responder à mesma pergunta com números diferentes) e **continuar a ser
    publicada** (senão o link antigo, que ele tem no telemóvel, dá 404 em vez de
    dizer para onde a coisa se mudou)."""
    assert "meusdecks.html" not in [f for f, _i, _t in paginas.MENU + paginas.EXTRA]
    assert 'href="meusdecks.html"' not in (RAIZ / "index.html").read_text(
        encoding="utf-8"), "o índice ainda aponta para a página fundida"
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert "meusdecks.html" in linha, "o reencaminhamento tem de ser publicado"
    assert "deckboxes.html" in [f for f, _i, _t in paginas.MENU]
    print("a pagina fundida saiu do menu e continua a ser publicada")


# As páginas que o site GERA e publica. O `buildability.py` fica de fora de
# propósito: está dormente desde a v6 (o "Montar" saiu do menu para o André o
# refazer), não corre no daily nem vai ao `git add`, e mexer-lhe era arrumar
# código que ele quer redefinir. (Tem os mesmos dois defeitos, se algum dia
# voltar: usa `var(--warn)` sem o definir e escreve os euros à mão.)
GERADORES = ["deckboxes.py", "metagame.py", "meta_coverage.py", "showcase.py",
             "colecao_cor.py", "caixarl.py", "reservedlist.py",
             "collection_gallery.py", "alertas.py"]


def caso_o_tema_tem_as_variaveis_que_as_paginas_usam():
    """Toda a `var(--x)` que uma página usa tem de estar definida ALGURES.

    Se não está, a cor cai para o valor por omissão do browser — texto preto em
    fundo preto, sem erro nenhum. Antes isto só olhava para as páginas que
    pedem o `%TEMA%` partilhado, e por isso a **Galeria** escapou: escreve a sua
    própria paleta (é a única clara) e usava `var(--add)`/`var(--rem)` — o verde
    de *"subiu"* e o vermelho de *"desceu"* da evolução do valor da colecção —
    sem os definir. O indicador saía na cor do texto e a linha do gráfico sem
    cor nenhuma. Agora conta também o que cada ficheiro define por si.
    """
    do_tema = set(re.findall(r"--([a-z0-9]+):", paginas.TEMA))
    faltam = {}
    for nome in GERADORES:
        py = RAIZ / nome
        txt = py.read_text(encoding="utf-8", errors="replace")
        usadas = set(re.findall(r"var\(--([a-z0-9]+)", txt))
        if not usadas:
            continue
        proprias = set(re.findall(r"--([a-z0-9]+)\s*:", txt))
        partilhado = "%TEMA%" in txt or "paginas.TEMA" in txt
        definidas = proprias | (do_tema if partilhado else set())
        em_falta = usadas - definidas
        if em_falta:
            faltam[py.name] = sorted(em_falta)
    assert not faltam, faltam
    print("todas as paginas definem as variaveis de cor que usam")


def caso_os_precos_sao_escritos_em_portugues():
    """`1 009,27 €` em todas as páginas — e não `1 009.27 €` em quatro delas.

    Cada página escrevia o seu formatador à mão e **quatro ficaram em inglês**:
    a Cobertura, a Caixa RL, a Galeria e a Reserved List mostravam o ponto
    decimal enquanto a Deckboxes e o Metagame mostravam a vírgula. A Cobertura
    chegava a ter as duas dentro da mesma página (o `_eur` do Python com ponto,
    o `ceur` do JavaScript com vírgula). Nenhuma dava erro: é o mesmo número com
    dois pontos decimais conforme a página em que ele está.

    A regra passou a viver num sítio só (`paginas.eur`), e o que aqui se tranca
    é que ninguém volte a escrever a sua.
    """
    assert paginas.eur(1009.27) == "1 009,27 €"
    assert paginas.eur(4.42) == "4,42 €"
    assert paginas.eur(47939.0, 0, espaco=False) == "47 939€"
    # Nenhum gerador formata um euro à mão (um `{...f}` colado a um `€`).
    mao = re.compile(r"\{[^{}]*:[^{}]*f\}\s*(?:&nbsp;)?€")
    maus = {}
    for nome in GERADORES:
        txt = (RAIZ / nome).read_text(encoding="utf-8", errors="replace")
        linhas = [l.strip() for l in txt.splitlines() if mao.search(l)]
        if linhas:
            maus[nome] = linhas
    assert not maus, maus
    print("os precos sao todos escritos em portugues, por um so formatador")


def caso_nenhuma_pagina_liga_a_uma_que_ninguem_publica():
    """Um `href` para um HTML que ninguém gera é um 404 no telemóvel dele.

    Aconteceu: a Galeria ficou com um *"core decks →"* a apontar para o
    `coredecks.html`, apagado a 2026-08-26 e desde então fora do `git add`. A
    página continuou a ser gerada todos os dias, com o link lá dentro, e nada
    deu erro — só quem carregasse é que ia parar ao 404.
    """
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    publicadas = set(re.findall(r"[a-z_]+\.html", linha)) | {"index.html"}
    maus = {}
    for f in GERADORES + ["index.html"]:
        txt = (RAIZ / f).read_text(encoding="utf-8", errors="replace")
        alvos = {a for a in re.findall(r'href="([a-z_]+\.html)', txt)}
        fora = alvos - publicadas
        if fora:
            maus[f] = sorted(fora)
    assert not maus, maus
    print("nenhuma pagina liga a um html que ninguem publica")


def run():
    for fn in (caso_o_menu_marca_a_pagina_actual, caso_o_menu_tem_todas_as_paginas,
               caso_todas_as_paginas_do_menu_sao_publicadas,
               caso_o_registo_de_arquetipos_e_publicado,
               caso_a_pagina_fundida_saiu_do_menu_mas_continua_publicada,
               caso_o_tema_tem_as_variaveis_que_as_paginas_usam,
               caso_os_precos_sao_escritos_em_portugues,
               caso_nenhuma_pagina_liga_a_uma_que_ninguem_publica):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
