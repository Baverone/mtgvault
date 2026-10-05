"""A prova de que o `test_ligas_modern.py` chumba sem o trabalho de 2026-10-05
(as ligas e os presenciais pequenos em Modern).

Um alvo por passagem, num processo próprio (como o `_chumba_opal_todos.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_ligas.py

Um processo por alvo de propósito: o que aqui se desliga são funções de módulo
já importadas (`sources.metagame_rules`, `versoes.listas_do_formato`) e ficheiros
de texto; num processo só, o primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. o `ligas` do modern a `false` — é o estado de ANTES desta ordem, e é o que
     tem de fechar as QUATRO portas de uma vez;
  2. o `min_jogadores_presencial` de volta a 64 — o presencial de 17 sai;
  3. o `_default` a ganhar ligas (a regra a escapar aos outros formatos);
  4. a conta SEM ligas igual à conta com elas (a divisão deixa de existir);
  5. o `sql_sem_ligas` sem o `IS NULL` — uma lista antiga sem tier caía fora
     das duas contas;
  6. o `ligasHTML` fora da página (o payload traz as duas e o ecrã mostra uma);
  7. o detector de anotações órfãs desligado — o deck PRINCIPAL volta a
     aparecer morto em silêncio;
  8. o detector a marcar TODAS as versões sem listas (o aviso permanente, que
     é um aviso que se deixa de ler);
  9. a pausa entre pedidos a zero;
 10. o `_get_mtgo` sem segunda tentativa — a página perdida por um timeout;
 11. o `incluir_hoje` a valer sempre (o `daily` ganha um pedido por formato);
 12. o JavaScript da aba Decks de volta à casca (o orçamento estoura).
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
import test_ligas_modern as T
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


def _regra(**troca):
    """Troca a regra EFECTIVA do modern, que é o que as quatro portas lêem."""
    return (
        "from mtgvault import sources\n"
        "_m = sources.metagame_rules\n"
        "def _f(fmt):\n"
        "    r = _m(fmt)\n"
        f"    if (fmt or '').lower() == 'modern':\n"
        f"        r = dict(r, **{troca!r})\n"
        "        if not r.get('ligas'):\n"
        "            r['tiers'] = [t for t in r['tiers'] if t != 'League']\n"
        "    return r\n"
        "sources.metagame_rules = _f")


ALVOS = [
    ("o `ligas` do modern a false (o estado de ANTES desta ordem)",
     _regra(ligas=False),
     ["caso_o_modern_aceita_ligas_e_presenciais_de_qualquer_tamanho",
      "caso_a_pergunta_das_ligas_vive_num_sitio_so",
      "caso_a_colheita_deixa_de_saltar_a_pagina_de_liga_de_modern",
      "caso_uma_lista_de_liga_de_modern_grava_se",
      "caso_uma_lista_de_liga_de_modern_entra_na_contagem",
      "caso_a_poda_nao_apaga_as_ligas_de_modern",
      "caso_a_contagem_com_e_sem_ligas_aparece_lado_a_lado"]),
    ("o `min_jogadores_presencial` de volta a 64",
     _regra(min_jogadores_presencial=64),
     ["caso_o_modern_aceita_ligas_e_presenciais_de_qualquer_tamanho",
      "caso_um_presencial_pequeno_de_modern_entra_na_contagem"]),
    ("a regra a escapar aos OUTROS formatos (o `_default` a ganhar ligas)",
     "from mtgvault import sources\n"
     "_m = sources.metagame_rules\n"
     "def _f(fmt):\n"
     "    r = _m(fmt)\n"
     "    if 'League' not in r['tiers']:\n"
     "        r = dict(r, tiers=r['tiers'] + ['League'], ligas=True,\n"
     "                 min_jogadores_presencial=0)\n"
     "    return r\n"
     "sources.metagame_rules = _f",
     ["caso_os_outros_formatos_nao_mudaram_de_regra"]),
    ("a conta SEM ligas igual a conta COM elas (a divisao desaparece)",
     "from mtgvault import versoes\n"
     "_l = versoes.listas_do_formato\n"
     "def _f(con, cfg=None):\n"
     "    out = _l(con, cfg)\n"
     "    for d in out.values():\n"
     "        d['sem_ligas'] = {'listas': d['listas'], 'total': d['total'],\n"
     "                          'pct': d['pct']}\n"
     "        d['ligas'] = dict(d['ligas'], listas=0, total=0, pct=0.0)\n"
     "    return out\n"
     "versoes.listas_do_formato = _f",
     ["caso_a_contagem_com_e_sem_ligas_aparece_lado_a_lado"]),
    ("o `sql_sem_ligas` sem o `IS NULL` (a lista antiga sem tier sai das duas)",
     "from mtgvault import sources\n"
     "def _s(alias='d'):\n"
     "    a = (alias + '.') if alias else ''\n"
     "    return '(' + a + \"event_tier <> ?)\", ['League']\n"
     "sources.sql_sem_ligas = _s",
     ["caso_a_pergunta_das_ligas_vive_num_sitio_so"]),
    ("o `ligasHTML` fora da pagina (o payload traz as duas, o ecra mostra uma)",
     "import io, pathlib\n"
     "import test_ligas_modern as _T\n"
     "_p = pathlib.Path(r'{raiz}') / 'decks.py'\n".replace("{raiz}", str(RAIZ))
     + "_t = io.open(_p, encoding='utf-8').read()\n"
     "_t = _t.replace('function ligasHTML', 'function _ligasHTML_fora')\n"
     "_t = _t.replace('ligasHTML(u.protege)', \"''\")\n"
     "import builtins\n"
     "_open = io.open\n"
     "def _fake(f, *a, **k):\n"
     "    if str(f).endswith('decks.py'):\n"
     "        import io as _io\n"
     "        return _io.StringIO(_t)\n"
     "    return _open(f, *a, **k)\n"
     "io.open = _fake",
     ["caso_a_pagina_desenha_as_duas_contas"]),
    ("o detector de anotacoes orfas desligado (o principal aparece morto)",
     "from mtgvault import versoes\n"
     "versoes._orfas = lambda vs: []",
     ["caso_a_anotacao_que_perdeu_o_cluster_e_dita"]),
    ("o detector a marcar TODAS as versoes sem listas (o aviso permanente)",
     "from mtgvault import versoes\n"
     "def _o(vs):\n"
     "    return [{'id': v['id'], 'nome': v['nome'],\n"
     "             'arquetipo_id': v['arquetipo_id'],\n"
     "             'principal': v['principal'], 'escolhida': v['escolhida'],\n"
     "             'candidato': None}\n"
     "            for v in vs if not v['listas']]\n"
     "versoes._orfas = _o",
     ["caso_uma_versao_legitimamente_adormecida_nao_leva_aviso",
      "caso_a_anotacao_que_perdeu_o_cluster_e_dita"]),
    ("a pausa entre pedidos ao mtgo.com a ZERO",
     "from mtgvault import sources\n"
     "sources.PAUSA_MTGO = 0.0",
     ["caso_a_colheita_espaca_os_pedidos_e_repete_um_erro_de_rede"]),
    ("o `_get_mtgo` sem segunda tentativa (a pagina perdida por um timeout)",
     "from mtgvault import sources\n"
     "def _g(url, tentativas=2):\n"
     "    import time\n"
     "    if sources.PAUSA_MTGO:\n"
     "        time.sleep(sources.PAUSA_MTGO)\n"
     "    return sources.requests.get(url, headers=sources.UA, timeout=30)\n"
     "sources._get_mtgo = _g",
     ["caso_a_colheita_espaca_os_pedidos_e_repete_um_erro_de_rede"]),
    ("o `incluir_hoje` a valer SEMPRE (o daily ganha um pedido por formato)",
     "from mtgvault import sources\n"
     "_h = sources.harvest_mtgo\n"
     "sources.harvest_mtgo = (lambda con, days_back=1, formats=None,\n"
     "                        incluir_hoje=False:\n"
     "                        _h(con, days_back, formats, True))",
     ["caso_a_colheita_comeca_em_ontem_por_omissao"]),
    ("o JavaScript da aba Decks de volta a CASCA (o orcamento estoura)",
     "import decks as D\n"
     "_t = D._tmpl\n"
     "D.casca = lambda: _t().replace('%SCRIPT%',\n"
     "    '<script>' + D.js_texto() + '</script>')",
     ["caso_o_javascript_da_aba_decks_saiu_da_casca",
      "caso_a_casca_da_aba_decks_cabe_no_orcamento"]),
]

if __name__ == "__main__":
    bons = 0
    for nome, preparo, alvos in ALVOS:
        if passagem(nome, preparo, alvos):
            bons += 1
    print(f"{bons}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if bons == len(ALVOS) else 1)
