"""A prova de que o `test_opal_todos.py` chumba sem o trabalho de 2026-10-05
(o Modern são TODOS os decks de Mox Opal, e o critério é PERMANENTE).

Um alvo por passagem, num processo próprio (como o `_chumba_mox.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_opal_todos.py

Um processo por alvo de propósito: o que aqui se desliga são funções de módulo
já importadas (`versoes.versoes_derivadas`, `versoes.versoes_todas`), e num
processo só o primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. as versões voltam a ser a **lista fixa do config** — é o defeito que a
     ordem manda corrigir: o conjunto deixa de crescer sozinho;
  2. o conjunto derivado **só da janela** (as conhecidas desaparecem) — era
     esconder o Grinding Station;
  3. o conjunto derivado de **toda a história** (tudo conta como actual) — era
     inventá-lo como actual;
  4. as listas sem cluster viram versão;
  5. a marca `principal` ignorada;
  6. a caixa dos «outros que jogam» a voltar num formato derivado;
  7. o `versoes_todas` ligado em TODOS (o interruptor deixa de existir);
  8. o `escolher` a ignorar as `validas` (um clique numa versão derivada volta
     a dar 409);
  9. um nome de etiqueta a passar por nome da fonte;
 10. uma versão derivada a entrar na **RE** (a lista de venda mexia);
 11. uma versão sem lista fixada a voltar a ser um deck de 0 %;
 12. o `exige` de volta a decidir quem é versão.
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
import test_opal_todos as T
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


#: O conjunto derivado reduzido à lista fixa do config — o estado de 04/10.
_LISTA_FIXA = (
    "from mtgvault import versoes\n"
    "def _d(con, fmt, cfg=None, cache=None):\n"
    "    return {'derivado': False, 'versoes': [], 'sem_cluster': 0,\n"
    "            'fora_da_janela': {'clusters': 0, 'listas': 0},\n"
    "            'carta': versoes.carta_chave(fmt, cfg)}\n"
    "versoes.versoes_derivadas = _d"
)

ALVOS = [
    ("as versoes voltam a ser a lista FIXA do config (o defeito de 04/10)",
     _LISTA_FIXA,
     ["caso_todo_o_cluster_que_joga_a_carta_e_versao",
      "caso_o_criterio_e_permanente_e_um_arquetipo_novo_entra_sozinho",
      "caso_uma_versao_conhecida_sem_listas_na_janela_diz_que_tem_zero",
      "caso_a_lista_sem_arquetipo_conta_se_e_nunca_vira_versao",
      "caso_a_vista_separa_os_dois_grupos_e_conta_o_resto"]),
    ("o conjunto SO da janela (as conhecidas desaparecem)",
     "from mtgvault import versoes\n"
     "_d = versoes.versoes_derivadas\n"
     "def _j(con, fmt, cfg=None, cache=None):\n"
     "    r = _d(con, fmt, cfg, cache)\n"
     "    r['versoes'] = [v for v in r['versoes'] if v['na_janela']]\n"
     "    return r\n"
     "versoes.versoes_derivadas = _j",
     ["caso_uma_versao_conhecida_sem_listas_na_janela_diz_que_tem_zero",
      "caso_a_vista_separa_os_dois_grupos_e_conta_o_resto",
      "caso_uma_versao_sem_lista_fixada_nao_e_um_deck_de_zero_por_cento"]),
    ("o conjunto de TODA a historia (tudo conta como actual)",
     "from mtgvault import versoes\n"
     "_d = versoes.versoes_derivadas\n"
     "def _t(con, fmt, cfg=None, cache=None):\n"
     "    r = _d(con, fmt, cfg, cache)\n"
     "    for v in r['versoes']:\n"
     "        v['na_janela'] = True\n"
     "        v['listas'] = v['listas_total']\n"
     "    return r\n"
     "versoes.versoes_derivadas = _t",
     ["caso_uma_versao_conhecida_sem_listas_na_janela_diz_que_tem_zero",
      "caso_a_vista_separa_os_dois_grupos_e_conta_o_resto"]),
    ("as listas sem cluster viram versao",
     "from mtgvault import versoes\n"
     "_d = versoes.versoes_derivadas\n"
     "def _s(con, fmt, cfg=None, cache=None):\n"
     "    r = _d(con, fmt, cfg, cache)\n"
     "    if r['derivado'] and r['sem_cluster']:\n"
     "        r['versoes'].append({'id': 'x', 'arquetipo_id': None,\n"
     "            'nome': 'sem cluster', 'origem_nome': 'etiqueta', 'deck': '',\n"
     "            'listas': r['sem_cluster'], 'listas_total': r['sem_cluster'],\n"
     "            'na_janela': True, 'anotada': False, 'principal': False,\n"
     "            'escolhida': False, 'porque': ''})\n"
     "        r['sem_cluster'] = 0\n"
     "    return r\n"
     "versoes.versoes_derivadas = _s",
     ["caso_a_lista_sem_arquetipo_conta_se_e_nunca_vira_versao"]),
    ("a marca `principal` ignorada",
     "from mtgvault import versoes\n"
     "versoes.principal = lambda fmt, cfg=None: ''",
     ["caso_a_affinity_e_a_principal",
      "caso_a_vista_separa_os_dois_grupos_e_conta_o_resto"]),
    ("a caixa dos «outros que jogam» a voltar num formato derivado",
     "from mtgvault import versoes\n"
     "_o = versoes.outros_que_jogam\n"
     "def _x(con, fmt, cfg=None, min_listas=1):\n"
     "    versoes.versoes_todas = lambda f, c=None: False\n"
     "    try:\n"
     "        return _o(con, fmt, cfg, min_listas)\n"
     "    finally:\n"
     "        versoes.versoes_todas = _vt\n"
     "_vt = versoes.versoes_todas\n"
     "versoes.outros_que_jogam = _x",
     ["caso_a_caixa_dos_outros_que_jogam_desapareceu"]),
    ("o `versoes_todas` ligado em TODOS (o interruptor deixa de existir)",
     "from mtgvault import versoes\n"
     "versoes.versoes_todas = lambda fmt, cfg=None: True",
     ["caso_o_pioneer_fica_com_a_lista_fixa"]),
    ("o `escolher` a ignorar as `validas` (a versao derivada volta a dar 409)",
     "from mtgvault import versoes\n"
     "_e = versoes.escolher\n"
     "versoes.escolher = (lambda cfg, fmt, vid, hoje=None, validas=None:\n"
     "                    _e(cfg, fmt, vid, hoje))",
     ["caso_escolher_uma_versao_derivada_nao_e_recusada",
      "caso_a_affinity_e_a_principal"]),
    ("um nome de etiqueta a passar por nome da fonte",
     "from mtgvault import versoes\n"
     "_d = versoes.versoes_derivadas\n"
     "def _n(con, fmt, cfg=None, cache=None):\n"
     "    r = _d(con, fmt, cfg, cache)\n"
     "    for v in r['versoes']:\n"
     "        if v['origem_nome'] == 'etiqueta':\n"
     "            v['origem_nome'] = 'fonte'\n"
     "    return r\n"
     "versoes.versoes_derivadas = _n",
     ["caso_um_nome_de_etiqueta_diz_que_e_etiqueta"]),
    ("uma versao DERIVADA a entrar na RE (a lista de venda mexia)",
     "from mtgvault import scryfall, versoes\n"
     "_n = versoes.nomes_que_ficam\n"
     "def _r(res, cfg=None):\n"
     "    out = _n(res, cfg)\n"
     "    out.setdefault(scryfall.chave('Scrabbling Claws'), set()).add('x')\n"
     "    return out\n"
     "versoes.nomes_que_ficam = _r",
     ["caso_o_motor_da_venda_nao_muda_com_as_versoes_derivadas"]),
    ("uma versao sem lista fixada a voltar a ser um deck de 0 %",
     "from mtgvault import decks_vista as dv\n"
     "_g = dv.decks_de_versoes\n"
     "def _z(con, cfg=None):\n"
     "    out = list(_g(con, cfg))\n"
     "    out.append({'id': 'versao:modern:conhecida', 'slot': None,\n"
     "        'nome': 'Grinding Station', 'formato': 'modern',\n"
     "        'fonte': 'versao', 'origem': 'evento', 'nota': '', 'link': '',\n"
     "        'estado': None, 'cards': [], 'listas': 0, 'arquetipo_id': 9,\n"
     "        'desactivada': False, 'rotulo_estado': '', 'versao_de': 'modern'})\n"
     "    return out\n"
     "dv.decks_de_versoes = _z",
     ["caso_uma_versao_sem_lista_fixada_nao_e_um_deck_de_zero_por_cento"]),
    ("o `exige` de volta a decidir quem e versao",
     "from mtgvault import versoes\n"
     "_d = versoes.versoes_derivadas\n"
     "def _x(con, fmt, cfg=None, cache=None):\n"
     "    r = _d(con, fmt, cfg, cache)\n"
     "    if r['derivado']:\n"
     "        _c, exige, pct = versoes._criterio(fmt, cfg)\n"
     "        exige = exige or ['Kappa Cannoneer', 'Pinnacle Emissary']\n"
     "        r['versoes'] = [v for v in r['versoes']\n"
     "            if all(versoes._pct_no_cluster(con, v['arquetipo_id'], c) >= 50\n"
     "                   for c in exige)]\n"
     "    return r\n"
     "versoes.versoes_derivadas = _x",
     ["caso_todo_o_cluster_que_joga_a_carta_e_versao",
      "caso_o_criterio_e_permanente_e_um_arquetipo_novo_entra_sozinho"]),
]

if __name__ == "__main__":
    print(f"a provar {len(ALVOS)} alvos, um processo cada\n")
    bons = sum(1 for n, p, a in ALVOS if passagem(n, p, a))
    print(f"\n{bons}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if bons == len(ALVOS) else 1)
