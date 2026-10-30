"""O interruptor `nucleo.ligado` liga o núcleo novo ao site, à publicação e à
recolha diária (2026-10-28).

Com ele LIGADO o menu é um só, «MTG», com Painel · Decks · Coleção · Vender; o
`publicar` gera e publica só essas quatro páginas; e o `daily` corre só a recolha que o
núcleo usa (catálogo, MTGO de Pauper e Premodern, preços, podas) e os passos
do núcleo. Com ele DESLIGADO tudo fica exatamente como estava — o código antigo
não se apagou.

Nada aqui abre a base do André nem sai para a rede: a base e o catálogo são
temporários, o config é uma cópia temporária (`_nucleo_interruptor`), e cada
passo do `daily` que tocaria na rede ou no disco do site é trocado por uma
função falsa que só regista que foi chamada.
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="mtg-nucleo-ligado-"))
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import nucleo_decks  # noqa: E402
import nucleo_painel  # noqa: E402
import nucleo_colecoes  # noqa: E402
import nucleo_vender  # noqa: E402
from _nucleo_interruptor import interruptor  # noqa: E402
from mtgvault import db, loadout, paginas, publicar  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402
from mtgvault.nucleo import modelo, valor, vigia  # noqa: E402

QUATRO = [("nucleo_painel", "index.html", False),
          ("nucleo_decks", "deck.html", False),
          ("nucleo_colecoes", "colecoes.html", False),
          ("nucleo_vender", "vender.html", False)]
MENU = ["index.html", "deck.html", "colecoes.html", "vender.html"]
# A pasta dos recortes das fotos entra na publicação (não é gerada pelo publicar).
RECORTES = "assets/cartas"
TITULOS = {"index.html": nucleo_painel.TITULO, "deck.html": nucleo_decks.TITULO,
           "colecoes.html": nucleo_colecoes.TITULO,
           "vender.html": nucleo_vender.TITULO}

ESPERADOS = ["catalogo", "harvest-mtgo", "precos-scryfall", "precos-cardmarket",
             "podar-precos", "podar-ligas", "prune", "nucleo-decks",
             "nucleo-vigias", "nucleo-valor", "nucleo-paginas", "checkpoint"]


def caso_menu_quatro_entradas():
    with interruptor(True):
        assert modelo.ligado() is True
        secs = shell.seccoes()
        assert [s for s, _ in secs] == ["MTG"], secs
        itens = secs[0][1]
        assert [(f, a, rot) for f, a, _i, rot, _n in itens] == [
            ("index.html", "", "Painel"), ("deck.html", "", "Decks"),
            ("colecoes.html", "", "Coleção"), ("vender.html", "", "Vender")], itens
        for _f, _a, ic, _rot, nota in itens:
            assert ic in shell._SVG, ic                 # ícones que já existem
            assert nota, "cada entrada leva uma nota curta"
        # O rótulo do menu é o título da página (a casca exige h1 == rótulo).
        for f, tit in TITULOS.items():
            assert shell.titulo_de(f) == tit, (f, shell.titulo_de(f), tit)
        assert shell.PAGINAS_DO_MENU == MENU
        assert paginas.MENU == MENU
        nav = shell.barra("deck.html")
        for f in TITULOS:
            assert f'href="{f}"' in nav, f
        for velha in ("decks.html", "deckboxes.html", "metagame.html",
                      "arrumacao.html", "faltas.html"):
            assert f'href="{velha}' not in nav, velha
        assert nav.count('class="sli cur"') == 1, nav
    print("ligado: o menu é Painel · Decks · Coleção · Vender, numa secção só")


def caso_menu_antigo_com_interruptor_desligado():
    with interruptor(False):
        assert modelo.ligado() is False
        secs = [s for s, _ in shell.seccoes()]
        assert secs[:4] == ["", "Montar decks", "Ver a coleção",
                            "Seguir o metagame"], secs
        assert secs[4] in (shell.SECCAO_VENDA, shell.SECCAO_SEM_VENDA), secs
        antigas = list(dict.fromkeys(f for _s, its in shell.SECCOES
                                     for f, a, *_r in its if not a))
        assert shell.PAGINAS_DO_MENU == antigas
        assert paginas.MENU == antigas
        assert len(antigas) == 13 and "deck.html" not in antigas, antigas
        assert shell.titulo_de("index.html") == "Início"
        assert shell.titulo_de("decks.html") == "Decks"
        assert len(publicar.PAGINAS) == 14, publicar.PAGINAS
        assert publicar.PAGINAS[0] == ("inicio", "index.html", True)
        assert "data/paginas" in publicar.PUBLICAVEIS
        assert "deckboxes.js" in publicar.PUBLICAVEIS
        nav = shell.barra("index.html")
        assert 'href="deckboxes.html"' in nav and 'href="deck.html"' not in nav
    print("desligado: o menu e as catorze páginas de antes, sem mudar nada")


# --------------------------------------------------------------------------
# O daily
# --------------------------------------------------------------------------
def _correr_daily(vigiar=None):
    """Corre o `daily.main()` com cada passo trocado por uma função falsa.

    Devolve `(passos, chamadas)`: os passos pela ordem em que ficaram no
    `job_runs` (`[(nome, estado)]`) e o que as funções falsas receberam. Um
    passo que não seja dos do núcleo NÃO corre: fica no `job_runs` como erro e
    o caso chumba pela lista — e nada vai à rede nem escreve no site.
    """
    import daily                                               # noqa: PLC0415
    from mtgvault import analysis, sources                    # noqa: PLC0415
    chamadas: dict = {}
    real_step = daily._step

    def step(con, nome, fn):
        if nome in ESPERADOS:
            return real_step(con, nome, fn)
        db.log_job(con, nome, "erro", "não devia correr com o núcleo ligado")
        return None

    def harvest(con, days_back=1, formats=None, incluir_hoje=False):
        chamadas["harvest"] = {"formats": formats, "days_back": days_back}
        return 0

    def vigiar_falso(con, *, pasta=None, levantar=False):
        chamadas["vigiar"] = {"levantar": levantar}
        if vigiar:
            return vigiar(con)
        return {}

    real_valor = valor.gravar_valor_do_dia

    def valor_falso(con, dia):
        chamadas["valor"] = dia
        return real_valor(con, dia)

    def gerar_falso(con, destino, rep=None):
        chamadas["gerar"] = Path(destino)
        return [f for _m, f, _r in publicar.PAGINAS]

    trocas = [
        (daily, "_step", step),
        (daily, "_catalog", lambda con: "catálogo falso"),
        (sources, "harvest_mtgo", harvest),
        (daily, "_scryfall_prices", lambda con: "scryfall falso"),
        (daily, "_cardmarket", lambda con: "cardmarket falso"),
        (daily, "_prune_prices", lambda con, keep_days=30: "podar falso"),
        (daily, "_podar_ligas", lambda con: "ligas falso"),
        (analysis, "prune_decklists", lambda con, dias=30: 0),
        (vigia, "vigiar_todos", vigiar_falso),
        (valor, "gravar_valor_do_dia", valor_falso),
        (publicar, "gerar", gerar_falso),
    ]
    antes = [(o, n, getattr(o, n)) for o, n, _f in trocas]
    with db.session() as con:
        ultimo = con.execute("SELECT COALESCE(MAX(id), 0) FROM job_runs").fetchone()[0]
    try:
        for o, n, f in trocas:
            setattr(o, n, f)
        daily.main()
    finally:
        for o, n, f in antes:
            setattr(o, n, f)
    with db.session() as con:
        passos = [(r[0], r[1]) for r in con.execute(
            "SELECT job, status FROM job_runs WHERE id > ? ORDER BY id", (ultimo,))]
    return passos, chamadas


def caso_daily_passos_ligado():
    import daily                                               # noqa: PLC0415
    with interruptor(True):
        passos, chamadas = _correr_daily()
    assert [n for n, _s in passos] == ESPERADOS, passos
    assert all(s == "ok" for _n, s in passos), passos
    assert chamadas["harvest"]["formats"] == {"pauper", "premodern"}, chamadas
    assert chamadas["vigiar"] == {"levantar": True}, chamadas
    assert chamadas["valor"] == __import__("datetime").date.today().isoformat()
    # As quatro páginas vão para onde as antigas iam: a raiz do repositório.
    assert chamadas["gerar"] == daily.ROOT, chamadas
    # E o núcleo ficou com os 14 decks na base.
    with db.session() as con:
        assert con.execute("SELECT COUNT(*) FROM n_deck").fetchone()[0] == len(
            modelo.DECKS)
    print("ligado: o daily corre só a recolha do núcleo, pela ordem certa")


def caso_vigia_falhada_fica_vermelha():
    def falha(con):
        raise vigia.VigiaFalhou({"cedh_cloud": {"estado": "sem_ficheiro",
                                                "mensagem": "sem ficheiro"}})

    with interruptor(True):
        passos, _ch = _correr_daily(vigiar=falha)
    estado = dict(passos)
    assert estado["nucleo-vigias"] == "erro", passos
    # O erro não leva o resto: os passos a seguir correm na mesma.
    assert [n for n, _s in passos] == ESPERADOS, passos
    for depois in ("nucleo-valor", "nucleo-paginas", "checkpoint"):
        assert estado[depois] == "ok", (depois, passos)
    with db.session() as con:
        det = con.execute("SELECT detail FROM job_runs WHERE job = 'nucleo-vigias'"
                          " ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert "VigiaFalhou" in det and "cedh_cloud" in det, det
    print("uma vigia que falha deixa o passo nucleo-vigias a vermelho")


# --------------------------------------------------------------------------
# A publicação
# --------------------------------------------------------------------------
def caso_publicar_quatro_paginas():
    with interruptor(True):
        assert publicar.PAGINAS == QUATRO, publicar.PAGINAS
        assert publicar.paginas() == QUATRO
        assert publicar.PUBLICAVEIS == [*MENU, RECORTES]
        # Nenhuma das quatro precisa do relatório do loadout antigo: não se calcula.
        real_report = loadout.report

        def proibido(*_a, **_k):
            raise AssertionError("o loadout.report não devia correr com o núcleo")
        loadout.report = proibido
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                with db.session(tmp / "v.db", tmp / "c.db") as con:
                    modelo.garantir_decks(con)
                    a, b = tmp / "a", tmp / "b"
                    assert publicar.gerar(con, a) == [f for _m, f, _r in QUATRO]
                    publicar.gerar(con, b)
                    assert sorted(p.name for p in a.iterdir()) == sorted(TITULOS)
                    d = publicar.comparar(a, b)
                    assert not (d["mudaram"] or d["novos"]), d
                    for f, tit in TITULOS.items():
                        txt = (a / f).read_text(encoding="utf-8")
                        assert f"<h1>{tit}</h1>" in txt or f">{tit}</h1>" in txt, f
                        for g in TITULOS:
                            assert f'href="{g}"' in txt, (f, g)
                    # Num site com as partes velhas em `data/paginas`, publicar
                    # duas vezes não pode dar «mudou» para sempre: essa pasta já
                    # não é do que se publica.
                    raiz = tmp / "site"
                    (raiz / "data" / "paginas" / "deckboxes").mkdir(parents=True)
                    (raiz / "data" / "paginas" / "deckboxes" / "x.json").write_text(
                        "{}", encoding="utf-8")
                    r1 = publicar.publicar(con, raiz)
                    assert r1["escreveu"] and r1["paginas"] == 4, r1
                    assert r1["publicaveis"] == [*MENU, RECORTES], r1
                    r2 = publicar.publicar(con, raiz)
                    assert not r2["escreveu"] and not r2["a_mais"], r2
        finally:
            loadout.report = real_report
    print("ligado: o publicar gera e publica só as quatro páginas")


_GUIAO = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from mtgvault import publicar
with publicar.abrir(sys.argv[2], sys.argv[3]) as con:
    print(",".join(publicar.gerar(con, Path(sys.argv[4]))))
'''


def caso_quatro_paginas_iguais_em_dois_processos_e_so_leitura():
    """A tarefa de 30 em 30 min decide «há algo para commitar?» pela diferença
    entre duas gerações — e tem de ser igual em DOIS PROCESSOS (o hash das
    strings muda a cada arranque, e um `set` pelo meio muda de ordem). Gera-se
    pela ligação SÓ DE LEITURA do `publicar.abrir`, a mesma da tarefa: uma
    página do núcleo que tentasse escrever rebentava aqui."""
    import subprocess                                          # noqa: PLC0415
    with interruptor(True), tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        v, c = tmp / "v.db", tmp / "c.db"
        with db.session(v, c) as con:
            modelo.garantir_decks(con)
        guiao = tmp / "gerar.py"
        guiao.write_text(_GUIAO, encoding="utf-8")
        for i, semente in enumerate(("1", "2")):
            amb = dict(os.environ, PYTHONHASHSEED=semente)
            r = subprocess.run([sys.executable, str(guiao), str(RAIZ), str(v),
                                str(c), str(tmp / f"s{i}")], env=amb,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=600)
            assert r.returncode == 0, r.stdout + r.stderr
            assert r.stdout.strip() == ",".join(MENU), r.stdout
        d = publicar.comparar(tmp / "s0", tmp / "s1")
        assert not (d["mudaram"] or d["novos"] or d["a_mais"]), d
    print("ligado: as quatro páginas saem iguais em dois processos, só a ler")


def caso_publicar_com_base_por_migrar():
    """(I4) O interruptor ligado e o `vault.db` a sério ainda sem as tabelas
    `n_*` (antes da primeira corrida do webapp ou do daily): o `publicar` não
    rebenta com um traceback — diz «base por migrar» e sai com erro."""
    import contextlib                                          # noqa: PLC0415
    import io                                                  # noqa: PLC0415
    import sqlite3                                             # noqa: PLC0415
    with interruptor(True), tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        v, c = tmp / "v.db", tmp / "c.db"
        for f in (v, c):
            sqlite3.connect(f).close()                         # bases vazias
        antes = publicar.abrir
        publicar.abrir = lambda *a, **k: db.ler(v, c)
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                try:
                    codigo = publicar.main([])
                except Exception as e:                         # noqa: BLE001
                    raise AssertionError(f"rebentou em vez de explicar: {e!r}")
        finally:
            publicar.abrir = antes
        assert codigo not in (0, None), codigo
        assert "base por migrar: corre o webapp ou o daily uma vez" in err.getvalue(), err.getvalue()
    # com as tabelas (uma base migrada) passa
    with interruptor(True), tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with db.session(tmp / "v.db", tmp / "c.db") as con:
            modelo.garantir_decks(con)
        with db.ler(tmp / "v.db", tmp / "c.db") as con:
            publicar.exige_base_do_nucleo(con)
    print("ligado: base por migrar = mensagem e erro, sem traceback")


def caso_config_diz_como_voltar_atras():
    """(I5) O texto do `_nucleo` no `colecao_config.json` diz o que se repõe à
    mão para voltar ao site antigo: o `git add` do `daily.yml`."""
    from mtgvault import configio                              # noqa: PLC0415
    cfg = configio.ler(RAIZ / "colecao_config.json")
    txt = cfg["_nucleo"]
    assert ".github/workflows/daily.yml" in txt, txt
    assert "git add index.html deck.html vender.html" in txt, txt
    assert "false" in txt


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for c in CASOS:
        c()
    print("\nTUDO OK")
