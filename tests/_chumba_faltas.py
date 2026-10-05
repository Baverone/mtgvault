"""A prova de que o `test_faltas_imagens.py` chumba sem o trabalho de 2026-10-05
(a lista de faltas para Ghent, e as imagens nas três listas de cartas).

Um alvo por passagem, num processo próprio (como o `_chumba_mox.py`): desliga-se
uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_faltas.py

Um processo por alvo de propósito: o que aqui se desliga são TEXTOS de módulo já
importados (`arrumacao._JS`, `paginas.JS_IMAGENS`) e funções de módulo
(`loadout.preco_fora_da_regra`), e num processo só o primeiro alvo envenenava os
seguintes em silêncio.

Os alvos:
  1. o `sid` fora dos campos da tabela — a Fase 3 volta a não ter imagem;
  2. o orçamento de imagens ignorado — o primeiro ecrã volta a pedir tudo;
  3. a falta a contar o `missing` em vez do `comprar` — volta a mandar comprar
     o que ele tem;
  4. as cartas do total somadas deck a deck em vez de contadas por nome;
  5. o `preco_fora_da_regra` a devolver sempre `None` — o preço de outra língua
     ou de outra edição volta a aparecer como se fosse o certo;
  6. o `sem_deck_escolhido` sempre falso — as faltas de Legacy entram no total;
  7. o `fase3` a ler `p.candidatos` — o defeito de 2026-10-01, que punha a Fase 3
     a mostrar «não consegui carregar os dados»;
  8. a curva do limiar deitada fora no `return` do `moxHTML`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[0]

GUIAO = r"""
import sys
sys.path.insert(0, r'{raiz}')
sys.path.insert(0, r'{aqui}')
import test_faltas_imagens as T
{preparo}
maus = []
for c in T.CASOS:
    if c.__name__ not in {alvos}:
        continue
    try:
        c()
    except BaseException as e:
        maus.append(c.__name__ + ': ' + type(e).__name__)
print('@@' + repr(maus))
"""


def passagem(nome: str, preparo: str, alvos: list[str]) -> bool:
    guiao = GUIAO.format(raiz=RAIZ, aqui=AQUI, preparo=preparo,
                         alvos=repr(set(alvos)))
    r = subprocess.run([sys.executable, "-c", guiao], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=AQUI)
    linha = next((l for l in r.stdout.splitlines() if l.startswith("@@")), None)
    if linha is None:
        print(f"  ?? {nome}: a passagem nem correu")
        print((r.stdout or "")[-900:], (r.stderr or "")[-900:])
        return False
    maus = eval(linha[2:])                                    # noqa: S307
    faltam = [a for a in alvos if not any(m.startswith(a) for m in maus)]
    if faltam:
        print(f"  NAO CHUMBOU {nome} -> {faltam}")
        return False
    print(f"  chumba OK   {nome} ({len(maus)} casos vermelhos)")
    return True


ALVOS = [
    ("o `sid` fora dos campos da tabela da Fase 3",
     "import arrumacao\n"
     "arrumacao._CAMPOS_TABELA = tuple(c for c in arrumacao._CAMPOS_TABELA"
     " if c != 'sid')",
     ["caso_as_tres_listas_mostram_imagem"]),
    ("o orcamento de imagens ignorado (pede-se tudo)",
     "from mtgvault import paginas\n"
     "paginas.JS_IMAGENS = paginas.JS_IMAGENS.replace('if (!com) return',"
     " 'if (false) return')",
     ["caso_o_primeiro_ecra_nao_passa_do_lote_de_imagens"]),
    ("a falta a contar o `missing` em vez do `comprar`",
     "from mtgvault import faltas_vista\n"
     "_v = faltas_vista.vista\n"
     "def vista(con, rep, cfg=None):\n"
     "    for s in rep['slots']:\n"
     "        for m in s['missing']:\n"
     "            m['comprar'] = m['missing']\n"
     "    return _v(con, rep, cfg)\n"
     "faltas_vista.vista = vista",
     ["caso_a_vista_de_faltas_nao_mostra_o_que_ele_tem"]),
    ("as cartas do total somadas deck a deck",
     "from mtgvault import faltas_vista\n"
     "_v = faltas_vista.vista\n"
     "def vista(con, rep, cfg=None):\n"
     "    v = _v(con, rep, cfg)\n"
     "    v['totais']['cartas'] = sum(d['cartas'] for d in v['decks'])\n"
     "    return v\n"
     "faltas_vista.vista = vista",
     ["caso_o_subtotal_por_deck_soma_o_total"]),
    ("o `preco_fora_da_regra` sempre None",
     "from mtgvault import loadout\n"
     "loadout.preco_fora_da_regra = lambda *a, **k: None",
     ["caso_um_preco_fora_da_regra_aparece_marcado"]),
    ("o `sem_deck_escolhido` sempre falso",
     "from mtgvault import faltas_vista\n"
     "faltas_vista.sem_deck_escolhido = lambda *a, **k: False",
     ["caso_as_faltas_de_legacy_ficam_fora_do_total"]),
    ("o `fase3` a ler `p.candidatos` (o defeito de 01/10)",
     "import arrumacao\n"
     "arrumacao._JS = arrumacao._JS.replace('  const c = p;',"
     " '  const c = p.candidatos;')",
     ["caso_a_fase_3_desenha_as_duas_listas"]),
    ("a curva do limiar deitada fora no `return`",
     "import arrumacao\n"
     "arrumacao._JS = arrumacao._JS.replace('    + curva;', '    + \\'\\';')",
     ["caso_a_fase_3_desenha_as_duas_listas"]),
]


def main() -> int:
    print(f"{len(ALVOS)} alvos, um processo por alvo\n")
    ok = sum(passagem(n, p, a) for n, p, a in ALVOS)
    print(f"\n{ok}/{len(ALVOS)} alvos chumbam como devem")
    return 0 if ok == len(ALVOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
