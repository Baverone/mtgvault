"""NENHUM TESTE ABRE A BASE OU O CATÁLOGO DO ANDRÉ (2026-10-06).

O que aconteceu, e é o que este ficheiro existe para não voltar a acontecer
--------------------------------------------------------------------------
A 2026-10-06 o André encontrou, de fora e com SQL, **fixtures de teste dentro
das bases a sério**: quatro linhas em `catalog.cards` com um `scryfall_id` que
não é um uuid (`s-falta`, `s-leg`, `s-tem` e um **`sid-0` que era um Tundra de
Revised FALSO**), **63 linhas / 252 exemplares** em `copies` e três linhas em
`price_latest` a 10,00 €. Efeito: a colecção dizia **1 930** cópias quando tem
**1 678**, valia ~2 520 € a mais, e a carta «Tem Esta» aparecia em **primeiro
lugar na lista do que há para vender** — e já tinha sido publicada no site
(`colecao.html`, `colecao_cor.html` e quatro ficheiros de `data/paginas/`).
Nenhum teste falhava: é o padrão do `event_tier`.

E A CAUSA ERA UMA SÓ, EM DUAS FORMAS — as duas em `mtgvault/db.py`:

  1. **faltou o `MTGVAULT_CATALOG`.** O `tests/test_estado_endpoint.py` fixava o
     `MTGVAULT_HOME` e o `MTGVAULT_DB` (cumpria a regra de 2026-09-09, que é
     sobre os ficheiros que acompanham a base) e **não o `MTGVAULT_CATALOG`** —
     que NESTE PC está definido no ambiente e aponta para o `data/catalog.db` a
     sério. O `ROOT/catalog.db` nunca chegava a valer: o ambiente ganhava. Era
     este o escritor do `sid-0`, **medido** a correr o ficheiro num processo
     novo e a comparar o catálogo antes e depois.
  2. **a variável foi posta TARDE.** O `_revisao/ghent/tests/test_faltas_ghent.py`
     (um rascunho de uma ordem anterior, nunca commitado com esse nome) fixava
     as QUATRO variáveis — e fazia-o no `setUp`, **depois** de importar o
     `mtgvault.db`. Os `db.DEFAULT_DB`/`DEFAULT_CATALOG` são constantes lidas no
     IMPORT: a variável não tem efeito nenhum e o teste escreveu 63 linhas na
     base do André a acreditar que estava numa temporária. Foi daqui que vieram
     o `s-tem` e as 252 cartas.

A LIÇÃO: **uma convenção não chega.** A regra de 2026-09-09 («todo o teste que
fixe o `MTGVAULT_HOME` fixa também o `MTGVAULT_DB`») está escrita, tem teste
(`test_paginas.caso_a_bateria_nao_escreve_no_data_a_serio`) — e passou ao lado
das duas, porque a primeira cumpria-a à letra e a segunda cumpria-a tarde. Um
teste que PODE abrir a base a sério acaba por a abrir.

O QUE SE TRANCA AQUI: uma TRAVA no `db.connect`, armada pela bateria
(`MTGVAULT_BASES_PROIBIDAS`), que **recusa alto** a base e o catálogo do André.
Quem precisa deles a sério — o `test_publicar`, que mede o determinismo das
páginas sobre a colecção real — pede-os pelo nome (`a_serio=True`), e a lista de
quem pede está AQUI, à vista. A trava está desligada em produção: sem a
variável, o `db.connect` é exactamente o que era.

Não abre socket nenhum nem toca na rede (o caso do endpoint do estado levanta um
servidor em `127.0.0.1`, dentro do processo filho dele).
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mtgvault import db  # noqa: E402

# OS FICHEIROS DE TESTE QUE PODEM ABRIR AS BASES A SÉRIO, com a razão. É uma
# lista explícita de propósito: sem ela, o primeiro teste novo que precisasse da
# base real punha-se a si próprio na excepção e a trava deixava de valer para
# ele — em silêncio, que é o defeito que isto fecha.
PODEM_A_SERIO = {
    "test_publicar.py": ("mede o DETERMINISMO das 14 páginas sobre a colecção "
                         "real: duas passagens têm de dar o mesmo byte. Só LÊ "
                         "(o `publicar.SO_LEITURA` tira o `historico` da "
                         "Galeria, e há caso próprio a exigir que o `-wal` não "
                         "cresça)."),
    "medir_determinismo.py": ("a ferramenta que o `test_publicar` corre em DOIS "
                              "subprocessos — a pergunta («a ordem de um `set` "
                              "muda entre processos?») só vale sobre a colecção "
                              "real. Também só lê."),
}

# As bases a sério, como o ambiente deste PC as resolve. É o que a bateria passa
# na `MTGVAULT_BASES_PROIBIDAS`.
A_SERIO = (Path(db.DEFAULT_DB), Path(db.DEFAULT_CATALOG))


def _ambiente(proibidas) -> dict:
    e = dict(os.environ)
    e[db.VAR_PROIBIDAS] = os.pathsep.join(str(Path(p).resolve())
                                          for p in proibidas)
    return e


def _correr(codigo: str, env: dict) -> subprocess.CompletedProcess:
    """Corre um pedaço de Python num processo NOVO, com este ambiente.

    Num processo novo de propósito: o que se mede é o que as constantes do
    `mtgvault.db` valem NO IMPORT, e isso não se reproduz dentro de um processo
    onde o módulo já está importado.
    """
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "p.py"
        f.write_text(codigo, encoding="utf-8")
        return subprocess.run([sys.executable, str(f)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=180, env=env, cwd=str(RAIZ))


# ---------------------------------------------------------------------------
def caso_a_bateria_arma_a_trava():
    """O `_bateria.py` tem de armar a trava e passar o ambiente aos filhos.

    Sem o `env=` no `subprocess.run`, a variável ficava no processo da bateria e
    nenhum teste a via — a trava existia e não travava nada.
    """
    txt = (RAIZ / "tests" / "_bateria.py").read_text(encoding="utf-8")
    assert db.VAR_PROIBIDAS in txt or "VAR_PROIBIDAS" in txt, (
        "o _bateria.py não arma a MTGVAULT_BASES_PROIBIDAS")
    assert re.search(r"subprocess\.run\((?:.|\n)*?env\s*=", txt), (
        "o _bateria.py não passa o ambiente aos processos filhos")
    assert "DEFAULT_DB" in txt and "DEFAULT_CATALOG" in txt, (
        "o _bateria.py tem de proibir as DUAS bases, não só a vault.db — "
        "foi o catálogo que levou o sid-0")
    print("a bateria arma a trava e passa-a aos filhos")


def caso_a_base_e_o_catalogo_proibidos_sao_recusados():
    """Com a trava armada, abrir uma base proibida LEVANTA — não avisa."""
    with tempfile.TemporaryDirectory() as d:
        vault, cat = Path(d) / "v.db", Path(d) / "c.db"
        outra = Path(d) / "temporaria.db"
        env = _ambiente([vault, cat])
        for alvo, rotulo in ((vault, "base"), (cat, "catálogo")):
            p = _correr(
                "import sys\n"
                f"sys.path.insert(0, {str(RAIZ)!r})\n"
                "from mtgvault import db\n"
                f"db.connect({str(vault if alvo is vault else outra)!r},"
                f" {str(cat if alvo is cat else outra)!r})\n", env)
            assert p.returncode != 0, (
                f"o {rotulo} proibido foi aberto sem uma queixa:\n{p.stdout}")
            assert "BaseALaSerio" in (p.stderr or ""), (rotulo, p.stderr[-800:])
            # A mensagem tem de NOMEAR o ficheiro: «uma base foi recusada» não
            # diz a ninguém qual, e são duas.
            assert alvo.name in (p.stderr or ""), (rotulo, p.stderr[-800:])
    print("a base e o catálogo proibidos são recusados, e a queixa nomeia o ficheiro")


def caso_a_variavel_posta_tarde_nao_engana_a_trava():
    """A FORMA 2 da avaria: fixar o `MTGVAULT_DB` depois do import.

    É o caso do `test_faltas_ghent`, que escreveu 63 linhas na base do André a
    acreditar que estava numa temporária. A trava tem de o apanhar — e a
    mensagem tem de DIZER que a variável foi posta tarde, senão quem a ler vai
    procurar o erro no sítio errado (ele fixou a variável; o que falhou foi o
    momento).
    """
    with tempfile.TemporaryDirectory() as d:
        vault, cat = Path(d) / "v.db", Path(d) / "c.db"
        tarde = Path(d) / "tarde"
        env = _ambiente([vault, cat])
        env["MTGVAULT_DB"] = str(vault)        # o ambiente "a sério"
        env["MTGVAULT_CATALOG"] = str(cat)
        p = _correr(
            "import os, sys\n"
            f"sys.path.insert(0, {str(RAIZ)!r})\n"
            "from mtgvault import db          # <- as constantes ficam aqui\n"
            f"os.environ['MTGVAULT_DB'] = {str(tarde / 'v.db')!r}\n"
            f"os.environ['MTGVAULT_CATALOG'] = {str(tarde / 'c.db')!r}\n"
            "db.connect()                     # abre as de SEMPRE\n", env)
        assert p.returncode != 0, (
            "a variável posta tarde passou: a base a sério foi aberta\n"
            + (p.stdout or ""))
        assert "BaseALaSerio" in (p.stderr or ""), p.stderr[-800:]
        assert "import" in (p.stderr or "").lower(), (
            "a mensagem não diz que a variável pode ter sido posta depois do "
            "import — era essa a avaria", p.stderr[-800:])
    print("a variável posta tarde é apanhada, e a mensagem diz porquê")


def caso_sem_a_trava_a_producao_nao_muda():
    """A trava está DESLIGADA sem a variável. O `daily` e o 8771 não a vêem."""
    with tempfile.TemporaryDirectory() as d:
        vault, cat = Path(d) / "v.db", Path(d) / "c.db"
        env = dict(os.environ)
        env.pop(db.VAR_PROIBIDAS, None)
        p = _correr(
            "import sys\n"
            f"sys.path.insert(0, {str(RAIZ)!r})\n"
            "from mtgvault import db\n"
            f"con = db.connect({str(vault)!r}, {str(cat)!r})\n"
            "db.init(con); print('ok')\n", env)
        assert p.returncode == 0, (p.stdout, p.stderr[-800:])
        assert "ok" in p.stdout
    print("sem a variável nada muda: a trava é só para a bateria")


def caso_quem_precisa_da_base_a_serio_pede_a_serio():
    """`a_serio=True` abre mesmo com a trava armada — e quem o usa está na lista.

    A lista é explícita para a excepção não se poder tomar em silêncio. Hoje é
    um ficheiro só, e a razão está escrita ao lado.
    """
    with tempfile.TemporaryDirectory() as d:
        vault, cat = Path(d) / "v.db", Path(d) / "c.db"
        env = _ambiente([vault, cat])
        p = _correr(
            "import sys\n"
            f"sys.path.insert(0, {str(RAIZ)!r})\n"
            "from mtgvault import db\n"
            f"con = db.connect({str(vault)!r}, {str(cat)!r}, a_serio=True)\n"
            "db.init(con); print('ok')\n", env)
        assert p.returncode == 0, (p.stdout, p.stderr[-800:])
    # Varre TODOS os `.py` de `tests/`, não só os `test_*`: o `medir_determinismo`
    # é uma ferramenta que o `test_publicar` corre em subprocessos e herda a trava
    # armada — se ficasse fora da varredura, podia pedir a base a sério sem se
    # inscrever. Foi o que a bateria apanhou a 2026-10-06.
    usam = set()
    for f in sorted((RAIZ / "tests").glob("*.py")):
        if f.name == Path(__file__).name:
            continue
        if re.search(r"a_serio\s*=\s*True", f.read_text(encoding="utf-8")):
            usam.add(f.name)
    assert usam == set(PODEM_A_SERIO), (
        "a lista dos que podem abrir as bases a sério mudou e esta não a "
        "acompanhou", sorted(usam), sorted(PODEM_A_SERIO))
    print(f"o `a_serio=True` funciona e só {len(usam)} ficheiro(s) o usam:",
          ", ".join(sorted(usam)))


def caso_a_bateria_inteira_nao_toca_nas_bases_do_andre():
    """A prova de ponta a ponta, no ficheiro que SUJOU: corre com a trava armada
    nas bases A SÉRIO e tem de passar.

    Antes da correcção este ficheiro acrescentava uma linha ao `catalog.db` do
    André em **cada** corrida da bateria (medido: `cards` 112 754 → 112 755). Com
    a trava armada, se ele voltar a abrir o catálogo a sério isto fica vermelho
    aqui em vez de ficar verde e deixar lá a linha.

    Corre-se UM ficheiro e não os 97: a bateria inteira já corre com a trava
    armada (é o `_bateria.py` que a arma), por isso quem a violar fica vermelho
    na sua própria linha, com o nome. O que falta provar é que o mecanismo chega
    a um teste a sério, e é isto.
    """
    env = _ambiente(A_SERIO)
    p = subprocess.run([sys.executable, "test_estado_endpoint.py"],
                       cwd=str(RAIZ / "tests"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300, env=env)
    assert p.returncode == 0, (
        "o test_estado_endpoint continua a abrir as bases do André:\n"
        + (p.stdout or "")[-1200:] + "\n" + (p.stderr or "")[-1200:])
    print("o test_estado_endpoint corre com as bases do André trancadas")


def caso_os_testes_que_abrem_a_base_pelo_ambiente_fixam_as_duas():
    """Quem chama `db.connect()`/`db.session()` SEM caminho fixa as DUAS variáveis.

    É a regra de 2026-09-09 estendida ao CATÁLOGO, que era o buraco: o
    `MTGVAULT_DB` sozinho manda a base para a temporária e deixa o catálogo a
    sério — e foi assim que o `sid-0` lá entrou. Só se olha para quem chama sem
    caminho: um `db.session(d / "v.db", d / "c.db")` já diz onde escreve.
    """
    faltam = []
    for f in sorted((RAIZ / "tests").glob("test_*.py")):
        txt = f.read_text(encoding="utf-8")
        if not re.search(r"\bdb\.(connect|session)\(\s*\)", txt):
            continue
        if f.name in PODEM_A_SERIO:
            continue
        cabeca = txt.split("\ndef ", 1)[0]
        tem = ("MTGVAULT_DB" in cabeca or "DEFAULT_DB" in txt,
               "MTGVAULT_CATALOG" in cabeca or "DEFAULT_CATALOG" in txt)
        if not all(tem):
            faltam.append((f.name, tem))
    assert not faltam, (
        "estes testes abrem a base pelo ambiente e não fixam as duas "
        "variáveis (a do catálogo é a que falhava)", faltam)
    print("quem abre a base pelo ambiente fixa a base E o catálogo")


def run():
    for fn in (caso_a_bateria_arma_a_trava,
               caso_a_base_e_o_catalogo_proibidos_sao_recusados,
               caso_a_variavel_posta_tarde_nao_engana_a_trava,
               caso_sem_a_trava_a_producao_nao_muda,
               caso_quem_precisa_da_base_a_serio_pede_a_serio,
               caso_os_testes_que_abrem_a_base_pelo_ambiente_fixam_as_duas,
               caso_a_bateria_inteira_nao_toca_nas_bases_do_andre):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
