"""A prova de que o `test_sempre_montado.py` chumba sem o trabalho de 2026-10-05.

Um alvo por passagem, num processo próprio (como o `_chumba_decks_vista.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_sempre_montado.py

Um processo por alvo de propósito: metade do que aqui se desliga é um módulo
inteiro em memória (`dv.sempre_montado`, `dv.da_pilha`), e num processo só o
primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. o `sempre_montado` sempre FALSO (como se o eixo novo não existisse);
  2. o `principal` a deixar de implicar `sempre_montado` (a chave desencostada);
  3. o `sempre_montado` escrito à mão a deixar de ganhar ao `principal`;
  4. os proxies de um deck sempre montado a voltarem a ser as PARTILHADAS;
  5. a repartição das verdadeiras a dar tudo a todos (ninguém leva proxy);
  6. a repartição sem ORDEM (a `prioridade` ignorada);
  7. as `disputadas` desligadas — a página deixa de dizer QUEM leva as
     verdadeiras;
  8. as BÁSICAS da pilha a voltarem a contar como falta (e a levar proxy);
  9. o `modo_efectivo` a ignorar os sempre montados (o formato volta ao máximo);
 10. o `marcar_principal` a não gravar a data / a escrever `false` em vez de
     apagar a chave;
 11. uma caixa desactivada a entrar como escolhida;
 12. o config a sério sem a troca do Stiflenought (volta à lista do Fierro);
 13. o config a sério com a lista do Fierro na chave do SLOT (a ficha mente);
 14. o config a sério sem as marcas `principal`;
 15. o visto do `principal` sem o gate do `EDIT()` — um botão numa página
     estática é um botão que não faz nada;
 16. o endpoint a dar 400 (pedido mal feito) a uma caixa desconhecida, em vez de
     409 («recarrega a página»).
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
import test_sempre_montado as T
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
    linha = next((ln for ln in r.stdout.splitlines() if ln.startswith("@@")), None)
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


#: O config a sério, lido e mexido em memória — é assim que se prova que os casos
#: que afirmam o ESTADO do `colecao_config.json` chumbam sem a mudança. Nunca se
#: escreve o ficheiro: troca-se o que o `Path.read_text` do teste devolve.
TROCA_CFG = """
import json
from pathlib import Path
_real = Path(r'{raiz}') / 'colecao_config.json'
_cfg = json.loads(_real.read_text(encoding='utf-8'))
{mexe}
_txt = json.dumps(_cfg, ensure_ascii=False)
_rt = Path.read_text
def _ler(self, *a, **k):
    if self.name == 'colecao_config.json':
        return _txt
    return _rt(self, *a, **k)
Path.read_text = _ler
"""


def com_config(mexe: str) -> str:
    return TROCA_CFG.format(raiz=RAIZ, mexe=mexe)


ALVOS = [
    # 1. o eixo novo não existe
    ("o sempre_montado sempre FALSO (o eixo novo desligado)",
     "from mtgvault import decks_vista as dv\n"
     "dv.sempre_montado = lambda s: False",
     ["caso_num_deck_sempre_montado_os_proxies_sao_todas_as_faltas",
      "caso_um_deck_a_60_por_cento_leva_os_proxies_de_tudo_o_que_falta",
      "caso_dois_decks_a_pedir_a_mesma_carta_um_leva_as_verdadeiras",
      "caso_desmarcar_devolve_o_formato_ao_modo_do_grupo",
      "caso_uma_basica_da_pilha_nunca_e_proxy",
      "caso_um_formato_de_cartas_dedicadas_ganha_proxies_e_sleeves",
      "caso_a_marca_principal_e_editavel"]),
    # 2. o principal deixa de implicar sempre montado
    ("o `principal` a deixar de implicar `sempre_montado`",
     "from mtgvault import decks_vista as dv\n"
     "dv.sempre_montado = lambda s: bool(s.get('sempre_montado'))",
     ["caso_num_deck_sempre_montado_os_proxies_sao_todas_as_faltas",
      "caso_dois_decks_a_pedir_a_mesma_carta_um_leva_as_verdadeiras",
      "caso_a_marca_principal_e_editavel"]),
    # 3. o sempre_montado explícito deixa de ganhar
    ("o `sempre_montado` escrito a mao a deixar de ganhar",
     "from mtgvault import decks_vista as dv\n"
     "dv.sempre_montado = lambda s: bool(s.get('principal'))",
     ["caso_o_sempre_montado_escrito_a_mao_ganha_ao_principal"]),
    # 4. os proxies voltam a ser as partilhadas
    ("os proxies de um deck sempre montado a voltarem as PARTILHADAS",
     "from mtgvault import decks_vista as dv\n"
     "_p = dv.proxies_do_deck\n"
     "dv.proxies_do_deck = lambda d, rep, repartido=None: _p(d, rep)",
     ["caso_num_deck_sempre_montado_os_proxies_sao_todas_as_faltas",
      "caso_um_deck_a_60_por_cento_leva_os_proxies_de_tudo_o_que_falta",
      "caso_uma_snow_covered_continua_a_ser_falta",
      "caso_um_formato_de_cartas_dedicadas_ganha_proxies_e_sleeves"]),
    # 5. a repartição dá tudo a todos
    ("a reparticao a dar as verdadeiras a TODOS os decks",
     "from mtgvault import decks_vista as dv\n"
     "from collections import defaultdict\n"
     "def _r(decks, pos):\n"
     "    out = {}\n"
     "    for d in decks:\n"
     "        if not dv.sempre_montado(d):\n"
     "            continue\n"
     "        ped = defaultdict(int)\n"
     "        for _b, nm, q in (d.get('cards') or []):\n"
     "            ped[nm] += q\n"
     "        out[d['id']] = {nm: {'q': q, 'verdadeiras': q, 'proxies': 0,\n"
     "                             'pilha': False} for nm, q in ped.items()}\n"
     "    return out\n"
     "dv.reparte_verdadeiras = _r",
     ["caso_dois_decks_a_pedir_a_mesma_carta_um_leva_as_verdadeiras",
      "caso_num_deck_sempre_montado_os_proxies_sao_todas_as_faltas",
      "caso_as_duas_metades_somam_sempre_o_total"]),
    # 6. a repartição sem ordem
    ("a reparticao a ignorar a `prioridade` da caixa",
     "from mtgvault import decks_vista as dv\n"
     "dv.ordem_das_verdadeiras = lambda decks: list(reversed(list(decks)))",
     ["caso_a_ordem_das_verdadeiras_e_a_prioridade_e_e_determinista",
      "caso_dois_decks_a_pedir_a_mesma_carta_um_leva_as_verdadeiras"]),
    # 7. as disputadas desligadas
    ("as `disputadas` desligadas (a pagina deixa de dizer quem leva as reais)",
     "from mtgvault import decks_vista as dv\n"
     "dv.disputadas = lambda decks, repartido, pos=None: []",
     ["caso_dois_decks_a_pedir_a_mesma_carta_um_leva_as_verdadeiras",
      "caso_desmarcar_devolve_o_formato_ao_modo_do_grupo"]),
    # 8. as básicas voltam a ser falta
    ("as BASICAS da pilha a voltarem a contar como falta",
     "from mtgvault import decks_vista as dv\n"
     "dv.da_pilha = lambda nm: False\n"
     "dv.tenho_para = lambda nm, pede, pos: min(pede, pos.get(nm, {}).get('q', 0))",
     # O caso do Stiflenought NÃO entra aqui: ele afirma que a caixa SERVE a
     # lista do Luffy (as cartas e as duas datas), e isso continua verdade com as
     # básicas mal contadas. São duas peças e cada uma tem o seu alvo.
     ["caso_uma_basica_da_pilha_nunca_e_proxy"]),
    # 9. o modo efectivo a ignorar os sempre montados
    ("o `modo_efectivo` a ignorar os sempre montados",
     "from mtgvault import decks_vista as dv\n"
     "dv.modo_efectivo = lambda modo_fmt, escolhidos: modo_fmt",
     ["caso_desmarcar_devolve_o_formato_ao_modo_do_grupo"]),
    # 10. o marcar_principal sem data / a escrever false
    ("o `marcar_principal` a escrever `false` em vez de apagar a chave",
     "from mtgvault import decks_vista as dv\n"
     "def _m(cfg, slot, principal, quando=None):\n"
     "    for c in cfg.get('caixas') or []:\n"
     "        if c.get('slot') == slot:\n"
     "            c['principal'] = bool(principal)\n"
     "            return bool(principal)\n"
     "    raise ValueError(slot)\n"
     "dv.marcar_principal = _m",
     ["caso_a_marca_principal_e_editavel"]),
    # 11. uma caixa desactivada entra como escolhida
    ("uma caixa DESACTIVADA a entrar como escolhida",
     "from mtgvault import decks_vista as dv\n"
     "dv.sem_lista_porque = lambda s: ('', '')",
     ["caso_uma_caixa_desactivada_nao_entra_como_escolhida"]),
    # 12. o config sem a troca do Stiflenought
    ("o config a serio SEM a troca do Stiflenought (volta ao Fierro)",
     com_config(
         "for _c in _cfg['caixas']:\n"
         "    if _c.get('slot') == 'premodern-stiflenought':\n"
         "        _c['fonte'] = 'escolhido'\n"
         "        _c['ref'] = 'premodern-stiflenought'\n"
         "        _c.pop('_antes_1004', None)"),
     ["caso_a_lista_do_fierro_esta_no_historico"]),
    # 13. a lista do Fierro na chave do SLOT (a ficha mente)
    ("o config a serio com a lista do Fierro na chave do SLOT",
     com_config(
         "_h = _cfg['listas_escolhidas'].pop('_premodern-stiflenought-anterior')\n"
         "_cfg['listas_escolhidas']['premodern-stiflenought'] = _h"),
     ["caso_a_lista_do_fierro_esta_no_historico"]),
    # 14. o config sem as marcas principal
    ("o config a serio SEM as marcas `principal`",
     com_config(
         "for _c in _cfg['caixas']:\n"
         "    _c.pop('principal', None)\n"
         "    _c.pop('principal_em', None)"),
     ["caso_as_caixas_a_zero_por_cento_nao_sao_principais"]),
    # 15. o controlo da pagina sem o gate do modo de edicao
    ("o visto do `principal` sem o gate do EDIT() (botao numa pagina estatica)",
     "import decks\n"
     "import re\n"
     "decks._JS = re.sub(r'  if \\(!EDIT\\(\\)\\) \\{\\n(.|\\n)*?\\n  \\}\\n',\n"
     "                   '', decks._JS, count=1)",
     ["caso_a_pagina_oferece_a_marca_so_no_modo_de_edicao"]),
    # 16. o endpoint a nao distinguir «caixa desconhecida» de «pedido mal feito»
    ("o endpoint a responder 400 a uma caixa desconhecida (em vez de 409)",
     "import webapp\n"
     "_d = webapp.Handler._deck_principal\n"
     "def _p(self, dados):\n"
     "    try:\n"
     "        return _d(self, dados)\n"
     "    except ValueError as e:\n"
     "        if isinstance(e, webapp.SemLista):\n"
     "            raise\n"
     "        raise webapp.SemLista(str(e)) from None\n"
     "webapp.Handler._deck_principal = _p",
     ["caso_o_endpoint_grava_a_marca_e_recusa_uma_caixa_que_nao_existe"]),
]

if __name__ == "__main__":
    print(f"{len(ALVOS)} alvos, um processo por alvo\n")
    bons = sum(1 for nome, prep, alvos in ALVOS if passagem(nome, prep, alvos))
    print(f"\n{bons}/{len(ALVOS)} alvos chumbam como deviam")
    sys.exit(0 if bons == len(ALVOS) else 1)
