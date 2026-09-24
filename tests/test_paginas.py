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
from mtgvault import site_shell as shell  # noqa: E402


def caso_o_menu_marca_a_pagina_actual():
    """A barra lateral marca a página em que ele está — uma e uma só.

    Era `paginas.nav()` (a barra horizontal); desde a reestruturação de
    2026-09-24 é `site_shell.barra()`. Os itens com âncora (`deckboxes.html
    #comprar`) NUNCA se marcam pelo ficheiro: quem os acende é o
    `location.hash`, do lado do browser — senão, em `deckboxes.html`, acendiam
    os seis ao mesmo tempo.
    """
    nav = shell.barra("deckboxes.html")
    assert nav.count('class="sli cur"') == 1, nav
    assert 'href="deckboxes.html" aria-current="page"' in nav
    # E sem página actual não há nenhuma marcada.
    assert "cur" not in shell.barra("")
    print("a barra lateral marca a pagina actual, e so uma")


def caso_o_menu_tem_todas_as_paginas():
    nav = shell.barra("index.html")
    for f in paginas.MENU:
        assert f'href="{f}"' in nav, f
    # E toda a sub-vista da barra aponta para uma página que o menu leva.
    for _sec, itens in shell.SECCOES:
        for f, a, *_r in itens:
            assert f in paginas.MENU, f
            if a:
                assert f'href="{f}#{a}"' in nav, (f, a)
    print("a barra lateral leva a todas as paginas e sub-vistas")


def caso_as_seccoes_do_menu_sao_as_que_ele_pediu():
    """A arquitetura de informação de 2026-09-24, à letra: *Início*, *Decks*,
    *Coleção*, *Metagame*, *Compras e venda*. Fica trancada porque é a decisão
    dele, não uma escolha de quem mexeu no ficheiro a seguir."""
    secs = [s for s, _itens in shell.SECCOES]
    assert secs == ["", "Decks", "Coleção", "Metagame", "Compras e venda"], secs
    # Nenhuma secção vazia, e nenhum item sem rótulo.
    for sec, itens in shell.SECCOES:
        assert itens, sec
        for f, _a, ic, rot, _n in itens:
            assert f.endswith(".html") and ic and rot, (sec, f)
    print("as seccoes sao as cinco que ele pediu, pela ordem dele")


def caso_todas_as_paginas_do_menu_sao_publicadas():
    """Uma página do menu que ninguém faz `git add` fica congelada no site."""
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    publicadas = set(re.findall(r"[a-z_]+\.html", linha))
    for f in paginas.MENU:
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
    assert "meusdecks.html" not in paginas.MENU
    assert 'href="meusdecks.html"' not in (RAIZ / "index.html").read_text(
        encoding="utf-8"), "o índice ainda aponta para a página fundida"
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert "meusdecks.html" in linha, "o reencaminhamento tem de ser publicado"
    assert "deckboxes.html" in paginas.MENU
    print("a pagina fundida saiu do menu e continua a ser publicada")


# As páginas que o site GERA e publica. (O `alertas.py` e o `buildability.py`
# foram apagados a 2026-09-15 por decisão do André — ver
# `caso_as_paginas_orfas_foram_mesmo_apagadas`.)
GERADORES = ["inicio.py", "deckboxes.py", "metagame.py", "meta_coverage.py",
             "showcase.py", "colecao_cor.py", "caixarl.py", "reservedlist.py",
             "collection_gallery.py"]

# Apagadas a 2026-09-15 (decisão do André): estavam fora do menu, não corriam no
# daily e ninguém as importava desde a v6. Uma página órfã não dá erro — só
# deixa de se lá chegar — e é por isso que fica aqui a lista: se alguém voltar a
# criar um destes ficheiros, ou a referi-lo, o teste diz que a decisão foi outra.
APAGADAS = ["alertas.py", "alertas.html", "buildability.py", "buildability.html"]


def caso_as_paginas_orfas_foram_mesmo_apagadas():
    """Os quatro ficheiros não existem, e nada no código, no workflow, no índice
    nem na tarefa do PC os refere. O `CLAUDE.md` é a excepção de propósito: é lá
    que a decisão fica registada, com a data."""
    for nome in APAGADAS:
        assert not (RAIZ / nome).exists(), f"{nome} voltou a aparecer"
    padrao = re.compile(r"\b(alertas|buildability)\.(py|html)\b")
    suspeitos = {}
    ficheiros = (list(RAIZ.glob("*.py")) + list(RAIZ.glob("*.html"))
                 + list((RAIZ / "mtgvault").glob("*.py"))
                 + list((RAIZ / "tests").glob("*.py"))
                 + list((RAIZ / "scripts").glob("*"))
                 + [RAIZ / ".github" / "workflows" / "daily.yml", RAIZ / "README.md",
                    RAIZ / "colecao_config.json"])
    ficheiros = [p for p in ficheiros if p.is_file() and p.name != Path(__file__).name]
    for p in ficheiros:
        txt = p.read_text(encoding="utf-8", errors="replace")
        achados = sorted(set(padrao.findall(txt)))
        if achados:
            suspeitos[p.name] = [".".join(a) for a in achados]
    assert not suspeitos, suspeitos
    # E a tarefa do PC, que tem a sua própria lista de HTML a publicar.
    tarefa = RAIZ.parent.parent / "ai-pc" / "tasks" / "mtgvault-daily" / "run.py"
    if tarefa.exists():
        assert not padrao.search(tarefa.read_text(encoding="utf-8", errors="replace")), \
            "a tarefa mtgvault-daily ainda refere uma página apagada"
    print("alertas e buildability foram apagadas e ninguem as refere")


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
    do_tema = set(re.findall(r"--([a-z0-9-]+):", paginas.TEMA))
    faltam = {}
    # A CASCA também usa variáveis (é ela que desenha a barra lateral e os
    # botões); se uma delas não estiver no tema, é a navegação inteira a cair
    # para a cor por omissão do browser.
    for alvo, txt in ([("site_shell.py (a casca)", shell.CSS)]
                      + [(n, (RAIZ / n).read_text(encoding="utf-8", errors="replace"))
                         for n in GERADORES]):
        usadas = set(re.findall(r"var\(--([a-z0-9-]+)", txt))
        if not usadas:
            continue
        proprias = set(re.findall(r"--([a-z0-9-]+)\s*:", txt))
        # `shell.head()` embute o tema partilhado — é o caminho de todas as
        # páginas desde 2026-09-24. Os dois nomes antigos ficam: um gerador que
        # ainda escreva `%TEMA%` à mão continua a ser reconhecido.
        partilhado = ("%TEMA%" in txt or "paginas.TEMA" in txt
                      or "shell.head(" in txt or alvo.startswith("site_shell"))
        definidas = proprias | (do_tema if partilhado else set())
        em_falta = usadas - definidas
        if em_falta:
            faltam[alvo] = sorted(em_falta)
    assert not faltam, faltam
    print("todas as paginas (e a casca) definem as variaveis que usam")


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


def caso_todas_as_paginas_geradas_levam_a_barra_lateral():
    """TODA a página publicada tem a MESMA navegação, e ninguém a escreve à mão.

    Era aqui que vivia o `caso_o_indice_tem_o_mesmo_menu_que_o_paginas`: o
    `index.html` era a única página com o menu escrito à mão (estático) e o
    teste comparava-o, linha a linha, com o `paginas.MENU`. Desde 2026-09-24 o
    índice é GERADO (`inicio.py`, o painel com os números que ele pediu) e a
    navegação sai do `site_shell` em todas — o defeito que aquele teste
    guardava deixou de ser possível por construção, e o que se tranca agora é
    que ninguém volte a escrever um `<nav>` à mão.

    Verifica-se no HTML PUBLICADO, não no código: uma página que o `daily` não
    tenha regenerado desde a mudança fica com a barra antiga, e é isso que o
    site mostra.
    """
    faltam, velhas = [], []
    for f in sorted(paginas.MENU):
        p = RAIZ / f
        if not p.is_file():
            faltam.append(f + " (não existe)")
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if '<aside class="side"' not in txt or 'class="sidenav"' not in txt:
            faltam.append(f)
        if '<nav class="tabs">' in txt:
            velhas.append(f)
        # A página inteira tem de estar na barra, e a barra tem de levar a todas.
        for alvo in paginas.MENU:
            assert f'href="{alvo}"' in txt, (f, alvo)
    assert not faltam, ("estas páginas não têm a barra lateral da casca", faltam)
    assert not velhas, ("estas páginas ainda têm a barra horizontal antiga", velhas)
    print(f"as {len(paginas.MENU)} paginas publicadas levam a mesma barra lateral")


def caso_a_bateria_nao_escreve_no_data_a_serio():
    """Correr a bateria não pode mexer nos ficheiros da colecção dele.

    Aconteceu, a 2026-09-09: uma corrida da bateria **esvaziou o
    `data/arquetipos.json`** (24 arquétipos, 333 linhas). Os ficheiros que
    acompanham a base saem de `db.pasta_dados()`, que é a pasta da
    `MTGVAULT_DB` — e neste PC essa variável está no ambiente e aponta para o
    `data/` a sério. Pôr só o `MTGVAULT_HOME`, como os testes faziam, não chega.
    Nenhum teste falhou: o `arquetipos.carregar` responde com um registo vazio de
    propósito, e a corrida seguinte reescrevia os nomes todos do zero.

    O que se tranca: todo o teste que fixe o `MTGVAULT_HOME` fixa também o
    `MTGVAULT_DB`, e nenhum deles aponta para dentro do repositório.
    """
    faltam, maus = [], []
    for f in sorted((RAIZ / "tests").glob("test_*.py")):
        txt = f.read_text(encoding="utf-8")
        # Só o bloco de arranque (antes do primeiro `def`): o resto pode falar
        # das variáveis sem as pôr — é o caso do `test_arquetipos`, que testa
        # precisamente esta regra com subprocessos.
        cabeca = txt.split("\ndef ", 1)[0]
        if "MTGVAULT_HOME" not in cabeca:
            continue
        if "MTGVAULT_DB" not in cabeca:
            faltam.append(f.name)
        elif re.search(r'MTGVAULT_DB"\]\s*=\s*str\(RAIZ', cabeca):
            maus.append(f.name)
    assert not faltam, ("estes testes fixam o MTGVAULT_HOME e não o MTGVAULT_DB: "
                        "vão escrever no data/ a sério", faltam)
    assert not maus, maus
    print("nenhum teste da bateria escreve nos ficheiros do data/ a serio")


def run():
    for fn in (caso_o_menu_marca_a_pagina_actual, caso_o_menu_tem_todas_as_paginas,
               caso_as_seccoes_do_menu_sao_as_que_ele_pediu,
               caso_todas_as_paginas_geradas_levam_a_barra_lateral,
               caso_a_bateria_nao_escreve_no_data_a_serio,
               caso_todas_as_paginas_do_menu_sao_publicadas,
               caso_o_registo_de_arquetipos_e_publicado,
               caso_a_pagina_fundida_saiu_do_menu_mas_continua_publicada,
               caso_o_tema_tem_as_variaveis_que_as_paginas_usam,
               caso_os_precos_sao_escritos_em_portugues,
               caso_nenhuma_pagina_liga_a_uma_que_ninguem_publica,
               caso_as_paginas_orfas_foram_mesmo_apagadas):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
