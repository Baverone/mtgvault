"""A prova de que o `test_sources.cache_do_config` chumba sem a correccao de
2026-10-06 (a cache do config esquece-se num sitio so).

Corre-se a mao:

    py tests\\_chumba_cache_config.py

Um alvo por passagem, num processo proprio: o que aqui se desliga e uma funcao
de modulo ja importada (`sources.esquecer_config`), e num processo so o primeiro
alvo envenenava os seguintes em silencio.

O DEFEITO QUE ISTO TRANCA: treze ficheiros de teste exercitavam um INTERRUPTOR
do config reescrevendo o ficheiro e limpavam a cache com
`sources._CONFIG_CACHE = None` -- um nome que NAO EXISTE (a cache e a
`_CFG_CACHE`). Nao limpava nada; o que os fazia passar era o `_config()`
comparar o `st_mtime`, e duas escritas no MESMO tique do relogio do sistema de
ficheiros devolviam o config ANTERIOR. Apanhado na bateria de 2026-10-06 pelo
`test_foto_manda.caso_a_frase_honesta_diz_x_de_y`: vermelho UMA vez e verde
10 de 10 corrido sozinho.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[0]

GUIAO = r"""
import sys
sys.path.insert(0, r'{raiz}')
sys.path.insert(0, r'{aqui}')
import test_sources as T
{preparo}
try:
    T.cache_do_config()
except BaseException as e:
    print('@@vermelho: ' + type(e).__name__)
else:
    print('@@verde')
"""


def passagem(nome: str, preparo: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-c", GUIAO.format(raiz=RAIZ, aqui=AQUI,
                                            preparo=preparo)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=AQUI)
    linha = next((l for l in (r.stdout or "").splitlines()
                  if l.startswith("@@")), None)
    if linha is None:
        print(f"  ?? {nome}: a passagem nem correu")
        print((r.stdout or "")[-600:], (r.stderr or "")[-900:])
        return False
    ok = linha.startswith("@@vermelho")
    print(f"  {'chumba OK  ' if ok else 'NAO CHUMBOU'} {nome} -> {linha[2:]}")
    return ok


def _pasta_com_nome_morto() -> Path:
    """Uma pasta de mentira com um ficheiro de teste que copiou o nome errado --
    e o que o varredor do caso tem de ver."""
    d = Path(tempfile.mkdtemp(prefix="chumba-cache-"))
    (d / "test_copiou_o_nome_morto.py").write_text(
        "sources._CONFIG_CACHE = None\n", encoding="utf-8")
    return d


ALVOS = [
    # 1) a correccao desfeita: o `esquecer_config` volta a nao fazer nada, que e
    #    exactamente o que o nome errado fazia.
    ("o `esquecer_config` volta a ser um no-op",
     "from mtgvault import sources\n"
     "sources.esquecer_config = lambda: None"),
    # 2) o varredor: um ficheiro de teste a usar o nome morto outra vez. Aponta-se
    #    o `__file__` do caso para uma pasta de mentira -- e o `glob('*.py')` dele
    #    que decide onde procura.
    ("um ficheiro de teste volta a usar o nome morto",
     "import test_sources as _T\n"
     f"_T.__file__ = r'{_pasta_com_nome_morto() / 'test_sources.py'}'"),
]

if __name__ == "__main__":
    print(f"{len(ALVOS)} alvos, um processo por alvo\n")
    ok = sum(1 for nome, prep in ALVOS if passagem(nome, prep))
    print(f"\n{ok}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if ok == len(ALVOS) else 1)
