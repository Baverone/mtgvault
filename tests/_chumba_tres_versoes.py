"""A prova de que o `test_tres_versoes.py` chumba sem o trabalho de 2026-10-06
ao fim do dia (o Modern fecha em TRES versoes nomeadas).

Um alvo por passagem, num processo proprio (como o `_chumba_opal_todos.py`):
desliga-se uma peca e exige-se VERMELHO. Corre-se a mao:

    py tests\\_chumba_tres_versoes.py

Um processo por alvo de proposito: o que aqui se desliga sao funcoes de modulo
ja importadas (`versoes.versoes`, `decks_vista.nucleo_das_versoes`), e num
processo so o primeiro alvo envenenava os seguintes em silencio.
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
import test_tres_versoes as T
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
    # ---- 1) as tres versoes nomeadas ------------------------------------
    ("o `versoes()` deixa de filtrar o `_saiu` (a que saiu volta a ser versao)",
     "from mtgvault import versoes\n"
     "versoes.versoes = versoes._versoes_escritas\n"
     "versoes.versoes_saidas = lambda fmt, cfg=None: []",
     ["caso_o_formato_tem_um_deck_com_tres_versoes_nomeadas",
      "caso_as_que_sairam_continuam_consultaveis",
      "caso_o_saiu_e_o_interruptor"]),
    ("o conjunto volta a ser DERIVADO da base (o modelo de 05/10)",
     "from mtgvault import versoes\n"
     "versoes.versoes_todas = lambda fmt, cfg=None: True",
     ["caso_o_formato_tem_um_deck_com_tres_versoes_nomeadas"]),
    # ---- 2) o nucleo comum ----------------------------------------------
    ("o NUCLEO desaparece (nao se mostra em separado)",
     "from mtgvault import decks_vista as dv\n"
     "dv.nucleo_das_versoes = (lambda alvos, pos: {'versoes': 0, 'nucleo': [],\n"
     "    'em_duas': [], 'cartas': 0, 'copias': 0, 'tem': 0, 'falta': 0,\n"
     "    'basicas': 0, 'em_duas_n': 0, 'em_duas_copias': 0})",
     ["caso_o_nucleo_comum_aparece_em_separado"]),
    ("o nucleo pela SOMA e nao pelo maximo (pede 5 Island em vez de 2)",
     "from mtgvault import decks_vista as dv\n"
     "_n = dv.nucleo_das_versoes\n"
     "def _s(alvos, pos):\n"
     "    r = _n(alvos, pos)\n"
     "    ped = dv._pede_por_versao(alvos)\n"
     "    for l in r['nucleo'] + r['em_duas']:\n"
     "        l['pede'] = sum(ped[l['nm']].values())\n"
     "    r['copias'] = sum(l['pede'] for l in r['nucleo'])\n"
     "    return r\n"
     "dv.nucleo_das_versoes = _s",
     ["caso_o_nucleo_comum_aparece_em_separado"]),
    ("a BASICA tirada do nucleo em silencio (a conta fecha por outro numero)",
     "from mtgvault import decks_vista as dv\n"
     "_n = dv.nucleo_das_versoes\n"
     "def _b(alvos, pos):\n"
     "    r = _n(alvos, pos)\n"
     "    r['nucleo'] = [l for l in r['nucleo'] if not l['da_pilha']]\n"
     "    r['cartas'] = len(r['nucleo'])\n"
     "    r['copias'] = sum(l['pede'] for l in r['nucleo'])\n"
     "    r['basicas'] = 0\n"
     "    return r\n"
     "dv.nucleo_das_versoes = _b",
     ["caso_o_nucleo_comum_aparece_em_separado"]),
    ("as «em duas das tres» misturadas com o nucleo",
     "from mtgvault import decks_vista as dv\n"
     "_n = dv.nucleo_das_versoes\n"
     "def _m(alvos, pos):\n"
     "    r = _n(alvos, pos)\n"
     "    r['nucleo'] = r['nucleo'] + r['em_duas']\n"
     "    r['cartas'] = len(r['nucleo'])\n"
     "    r['em_duas'], r['em_duas_n'] = [], 0\n"
     "    return r\n"
     "dv.nucleo_das_versoes = _m",
     ["caso_o_nucleo_comum_aparece_em_separado"]),
    # ---- 3) as alternativas ---------------------------------------------
    ("as ALTERNATIVAS desaparecem (a lista do meta em vez da dele, ou nada)",
     "from mtgvault import versoes\n"
     "versoes.alternativas_da_versao = (\n"
     "    lambda con, fmt, v, cfg=None, desde=None: [])",
     ["caso_a_lista_dele_fica_e_as_do_meta_sao_alternativas"]),
    ("as alternativas sem o que tem A MAIS (duas listas iguais no ecra)",
     "from mtgvault import versoes\n"
     "_a = versoes.alternativas_da_versao\n"
     "def _x(con, fmt, v, cfg=None, desde=None):\n"
     "    out = _a(con, fmt, v, cfg, desde)\n"
     "    for z in out:\n"
     "        if z.get('origem') == 'meta':\n"
     "            z['extra'], z['extra_n'] = [], 0\n"
     "    return out\n"
     "versoes.alternativas_da_versao = _x",
     ["caso_a_lista_dele_fica_e_as_do_meta_sao_alternativas"]),
    ("a alternativa em DECK sem ficha (um id e mais nada)",
     "from mtgvault import versoes\n"
     "_a = versoes.alternativas_da_versao\n"
     "def _d(con, fmt, v, cfg=None, desde=None):\n"
     "    return [z for z in _a(con, fmt, v, cfg, desde)\n"
     "            if z.get('origem') != 'deck']\n"
     "versoes.alternativas_da_versao = _d",
     ["caso_a_lista_dele_fica_e_as_do_meta_sao_alternativas"]),
    # ---- 4) a ambiguidade ------------------------------------------------
    ("a AMBIGUIDADE desaparece (as 4 listas sem as 104 ao lado)",
     "from mtgvault import versoes\n"
     "versoes.ambiguidade_da_versao = (\n"
     "    lambda con, fmt, v, cfg=None, desde=None: None)",
     ["caso_a_ambiguidade_aparece_com_os_dois_numeros"]),
    ("a ambiguidade SEM o outro deck nomeado («as outras 100» sem dizer quem)",
     "from mtgvault import versoes\n"
     "_a = versoes.ambiguidade_da_versao\n"
     "def _o(con, fmt, v, cfg=None, desde=None):\n"
     "    r = _a(con, fmt, v, cfg, desde)\n"
     "    if r:\n"
     "        r['outro'] = None\n"
     "    return r\n"
     "versoes.ambiguidade_da_versao = _o",
     ["caso_a_ambiguidade_aparece_com_os_dois_numeros"]),
    ("a ambiguidade com UM numero so (o universo da carta ignorado)",
     "from mtgvault import versoes\n"
     "_a = versoes.ambiguidade_da_versao\n"
     "def _u(con, fmt, v, cfg=None, desde=None):\n"
     "    r = _a(con, fmt, v, cfg, desde)\n"
     "    if r:\n"
     "        r['so_a_carta'], r['outras'] = r['com'], 0\n"
     "    return r\n"
     "versoes.ambiguidade_da_versao = _u",
     ["caso_a_ambiguidade_aparece_com_os_dois_numeros"]),
    # ---- 5) as faltas por versao -----------------------------------------
    ("as FALTAS POR VERSAO desaparecem",
     "from mtgvault import decks_vista as dv\n"
     "dv.faltas_das_versoes = (\n"
     "    lambda con, fmt, decks, pos, cfg=None, cache=None: None)",
     ["caso_as_faltas_por_versao_somam_o_total_sem_repetir_o_nucleo"]),
    ("o total REPETE o nucleo (soma os tres sacos isolados)",
     "from mtgvault import decks_vista as dv\n"
     "_f = dv.faltas_das_versoes\n"
     "def _r(con, fmt, decks, pos, cfg=None, cache=None):\n"
     "    r = _f(con, fmt, decks, pos, cfg, cache)\n"
     "    if r:\n"
     "        r['totais'] = dict(r['totais'])\n"
     "        r['totais']['copias'] = sum(v['so_este']['copias']\n"
     "                                    for v in r['versoes'])\n"
     "    return r\n"
     "dv.faltas_das_versoes = _r",
     ["caso_as_faltas_por_versao_somam_o_total_sem_repetir_o_nucleo"]),
    ("as partilhadas atiradas para dentro de cada versao (o saco do meio cai)",
     "from mtgvault import decks_vista as dv\n"
     "_f = dv.faltas_das_versoes\n"
     "def _p(con, fmt, decks, pos, cfg=None, cache=None):\n"
     "    r = _f(con, fmt, decks, pos, cfg, cache)\n"
     "    if r:\n"
     "        for v in r['versoes']:\n"
     "            v['so'] = dict(v['so_este'])\n"
     "            v['linhas'] = v['linhas'] + r['partilhadas']['linhas']\n"
     "        r['partilhadas'] = {'cartas': 0, 'copias': 0, 'eur': 0,\n"
     "                            'eur_nonfoil': 0, 'sem_preco': 0, 'linhas': []}\n"
     "    return r\n"
     "dv.faltas_das_versoes = _p",
     ["caso_as_faltas_por_versao_somam_o_total_sem_repetir_o_nucleo"]),
    # ---- 6) as saidas consultaveis ---------------------------------------
    ("as saidas deixam de ser decks do registo (o «ver» nao leva a nada)",
     "from mtgvault import versoes\n"
     "_v = versoes.versoes_saidas\n"
     "import mtgvault.decks_vista as dv\n"
     "_dvs = dv.decks_de_versoes\n"
     "def _x(con, cfg=None):\n"
     "    versoes.versoes_saidas = lambda fmt, c=None: []\n"
     "    try:\n"
     "        return _dvs(con, cfg)\n"
     "    finally:\n"
     "        versoes.versoes_saidas = _v\n"
     "dv.decks_de_versoes = _x",
     ["caso_as_que_sairam_continuam_consultaveis"]),
    ("a vista deixa de trazer as saidas",
     "from mtgvault import decks_vista as dv\n"
     "_u = dv.deck_unico\n"
     "def _x(con, fmt, decks, pos, cfg=None):\n"
     "    r = _u(con, fmt, decks, pos, cfg)\n"
     "    if r:\n"
     "        r['saidas'] = []\n"
     "    return r\n"
     "dv.deck_unico = _x",
     ["caso_as_que_sairam_continuam_consultaveis"]),
    # ---- 7) a RE das alternativas ----------------------------------------
    ("as ALTERNATIVAS fora de `decks_das_versoes` (a lista de Ghent perde a RE)",
     "from mtgvault import versoes\n"
     "versoes.decks_das_versoes = (lambda fmt, cfg=None: [\n"
     "    versoes.deck_da_versao(v) for v in versoes.versoes(fmt, cfg)\n"
     "    if versoes.deck_da_versao(v)])",
     ["caso_uma_alternativa_em_deck_continua_protegida_pela_re"]),
    # ---- 8) o universo pelas cartas --------------------------------------
    ("o universo da versao deixa de sair das CARTAS",
     "from mtgvault import versoes\n"
     "versoes.cartas_do_meta = lambda v: []",
     ["caso_o_universo_sai_das_cartas_e_a_versao_nunca_e_orfa",
      "caso_a_lista_dele_fica_e_as_do_meta_sao_alternativas",
      "caso_a_ambiguidade_aparece_com_os_dois_numeros"]),
    ("as versoes voltam a ancorar no CLUSTER (ha cluster para perder outra vez)",
     "from mtgvault import versoes\n"
     "_v = versoes.versoes\n"
     "def _x(fmt, cfg=None):\n"
     "    out = []\n"
     "    for v in _v(fmt, cfg):\n"
     "        w = dict(v)\n"
     "        if w.get('arquetipo_id') is None:\n"
     "            w['arquetipo_id'] = 1\n"
     "        out.append(w)\n"
     "    return out\n"
     "versoes.versoes = _x",
     ["caso_o_universo_sai_das_cartas_e_a_versao_nunca_e_orfa"]),
    # ---- 9) os «outros» ---------------------------------------------------
    ("um cluster que JA e versao volta a aparecer nos «outros»",
     "from mtgvault import versoes\n"
     "versoes._e_de_uma_versao = (\n"
     "    lambda con, fmt, aid, das_versoes: False)",
     ["caso_um_cluster_que_ja_e_versao_nao_aparece_nos_outros"]),
    # ---- 10) as familias --------------------------------------------------
    ("as FAMILIAS caem com o `versoes_todas` (apagadas em silencio)",
     "from mtgvault import versoes\n"
     "versoes.familias_que_protegem = (\n"
     "    lambda con, fmt, cfg=None, desde=None: [])",
     ["caso_as_familias_nao_se_perderam_e_mudaram_para_a_proteccao"]),
    # ---- 11) a nota de uma lista que nao e de evento ----------------------
    ("a nota antiga: «sem lista de evento fixada» ao lado de 74 cartas",
     "from mtgvault import decks_vista as dv\n"
     "from mtgvault import eventos\n"
     "def _n(rec):\n"
     "    prov = rec.get('evento') or {{}}\n"
     "    if not prov:\n"
     "        return 'sem lista de evento fixada'\n"
     "    return 'lista de evento real - ' + eventos.texto_prov(prov)\n"
     "dv._nota_do_evento = _n",
     ["caso_uma_lista_que_nao_e_de_evento_diz_a_origem"]),
    # ---- 14) «para ja» e literal: a versao que ele tirou fica inteira ------
    # (2026-10-06, ao fim do dia: "entao apagamos para ja essa versao")
    #
    # NOTA: o `{raiz}` NAO se substitui dentro de um `preparo` -- o `.format` do
    # GUIAO troca o `{preparo}` pelo valor e nao volta a formatar o valor. O
    # guiao ja fez `import test_tres_versoes as T`, por isso o caminho vem de
    # `T.RAIZ`; e redireccionar `T.RAIZ` para uma copia e o que faz os casos do
    # «config a serio» lerem um config estragado sem tocar no a serio.
    ("o `_saiu` da versao do Cori-Steel desaparece do config (volta a ser versao)",
     "import json, pathlib, tempfile\n"
     "from mtgvault import configio\n"
     "_c = json.loads((T.RAIZ / 'colecao_config.json').read_text('utf-8'))\n"
     "for _v in _c['decks_por_formato']['modern']['versoes']:\n"
     "    if _v['id'] == 'versao:modern:cori-steel':\n"
     "        _v.pop('_saiu', None)\n"
     "_p = pathlib.Path(tempfile.mkdtemp()) / 'colecao_config.json'\n"
     "configio.escrever(_c, _p)\n"
     "T.RAIZ = _p.parent",
     ["caso_a_versao_que_ele_tirou_fica_inteira",
      "caso_o_config_a_serio_tem_as_duas_versoes",
      "caso_o_nucleo_com_duas_versoes_sobe_e_o_em_duas_desaparece"]),
    ("a LISTA do Kody Lyons e apagada com a versao (so ficava a marca)",
     "import json, pathlib, tempfile\n"
     "from mtgvault import configio\n"
     "_c = json.loads((T.RAIZ / 'colecao_config.json').read_text('utf-8'))\n"
     "_c['listas_escolhidas'].pop('versao:modern:cori-steel', None)\n"
     "_p = pathlib.Path(tempfile.mkdtemp()) / 'colecao_config.json'\n"
     "configio.escrever(_c, _p)\n"
     "T.RAIZ = _p.parent",
     ["caso_a_versao_que_ele_tirou_fica_inteira"]),
    ("a nota da AMBIGUIDADE e apagada (perde-se a razao por que ele a tirou)",
     "import json, pathlib, tempfile\n"
     "from mtgvault import configio\n"
     "_c = json.loads((T.RAIZ / 'colecao_config.json').read_text('utf-8'))\n"
     "for _v in _c['decks_por_formato']['modern']['versoes']:\n"
     "    if _v['id'] == 'versao:modern:cori-steel':\n"
     "        _v['meta'].pop('ambiguidade', None)\n"
     "_p = pathlib.Path(tempfile.mkdtemp()) / 'colecao_config.json'\n"
     "configio.escrever(_c, _p)\n"
     "T.RAIZ = _p.parent",
     ["caso_a_versao_que_ele_tirou_fica_inteira"]),
    # ---- 15) o nucleo com duas versoes -------------------------------------
    ("o `em_duas` deixa de ser «mais do que uma mas nao todas» (entra no nucleo)",
     "from mtgvault import decks_vista as dv\n"
     "_n = dv.nucleo_das_versoes\n"
     "def _x(alvos, pos):\n"
     "    r = _n(alvos, pos)\n"
     "    r['nucleo'] = [l for l in r['nucleo'] if l['em'] == r['versoes']\n"
     "                   and l['nm'] not in ('Damping Sphere', 'Vexing Bauble')]\n"
     "    r['cartas'] = len(r['nucleo'])\n"
     "    r['copias'] = sum(l['pede'] for l in r['nucleo'])\n"
     "    return r\n"
     "dv.nucleo_das_versoes = _x",
     ["caso_o_nucleo_com_duas_versoes_sobe_e_o_em_duas_desaparece"]),
    ("a quantidade do nucleo volta a ser a SOMA e nao o maximo",
     "from mtgvault import decks_vista as dv\n"
     "_p = dv._pede_por_versao\n"
     "_n = dv.nucleo_das_versoes\n"
     "def _x(alvos, pos):\n"
     "    r = _n(alvos, pos)\n"
     "    pede = _p(alvos)\n"
     "    for l in r['nucleo']:\n"
     "        l['pede'] = sum(pede[l['nm']].values())\n"
     "    r['copias'] = sum(l['pede'] for l in r['nucleo'])\n"
     "    return r\n"
     "dv.nucleo_das_versoes = _x",
     ["caso_o_nucleo_com_duas_versoes_sobe_e_o_em_duas_desaparece"]),
]

if __name__ == "__main__":
    print(f"{len(ALVOS)} alvos, um processo por alvo\n")
    ok = sum(1 for nome, prep, alvos in ALVOS if passagem(nome, prep, alvos))
    print(f"\n{ok}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if ok == len(ALVOS) else 1)
