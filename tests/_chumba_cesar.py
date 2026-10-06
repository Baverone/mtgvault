"""A prova de que o `test_cesarmerjan.py` chumba sem o trabalho de 2026-10-06
(a vigia do CesarMerjan, as seis famílias do Mox Opal e as faltas por deck).

Um alvo por passagem, num processo próprio (como o `_chumba_opal_todos.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_cesar.py

Um processo por alvo de propósito: o que aqui se desliga são funções de módulo
já importadas (`watchlist.apanha_ligas`, `versoes.familias`,
`decks_vista.faltas_de_jogador`), e num processo só o primeiro alvo envenenava
os seguintes em silêncio.

Os alvos:
  1. a vigia do jogador a FILTRAR por tier — é o defeito que a ordem manda
     conferir: com ele, o CesarMerjan parece não ter listas nenhumas;
  2. a vigia a apanhar a lista mais ANTIGA em vez da mais recente;
  3. o `apanha_ligas` a dizer sempre «sim» — a cegueira silenciosa de volta;
  4. o resultado da vigia a não levar o `ligas`;
  5. as versões ancoradas numa LISTA a desaparecer (só clusters são versões) —
     é o estado de 05/10, em que nenhuma das duas listas dele entrava;
  6. a marca do JOGADOR deitada fora;
  7. uma versão fixa a ser dada como ÓRFÃ (o aviso permanente a piscar);
  8. a família ancorada no CLUSTER em vez das cartas;
  9. a família de um cluster vazio sem o recurso da lista do deck;
 10. a contagem por família a desaparecer;
 11. as faltas num saco só (as partilhadas atribuídas a um dos decks);
 12. as faltas sem o segundo preço (só o foil);
 13. o `familias` a ligar-se sempre (o interruptor deixa de existir).
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
import test_cesarmerjan as T
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
    # ------------------------------------------------------------- a vigia
    ("a vigia do jogador a FILTRAR por tier",
     "from mtgvault import watchlist\n"
     "def _c(con, wid):\n"
     "    w = con.execute('SELECT * FROM watched WHERE id=?', (wid,)).fetchone()\n"
     "    row = con.execute(\n"
     "        \"SELECT id, event_date, event_name, url, event_tier FROM decklists\"\n"
     "        \" WHERE lower(player)=lower(?) AND format=? AND event_tier <> 'League'\"\n"
     "        ' ORDER BY event_date DESC, id DESC LIMIT 1', (w['key'], w['format'])\n"
     "    ).fetchone()\n"
     "    if row is None:\n"
     "        return {'watched': dict(w), 'found': False,\n"
     "                'ligas': watchlist.apanha_ligas(con, wid)}\n"
     "    return {'watched': dict(w), 'found': True, 'changed': False,\n"
     "            'tier': row['event_tier'], 'decklist_id': row['id'],\n"
     "            'cards': [], 'ligas': watchlist.apanha_ligas(con, wid)}\n"
     "watchlist.check_mtgo_player = _c",
     ["caso_a_vigia_do_jogador_apanha_uma_lista_de_liga"]),
    ("a vigia a apanhar a lista mais ANTIGA",
     "from mtgvault import watchlist\n"
     "_o = watchlist.check_mtgo_player\n"
     "def _c(con, wid):\n"
     "    r = _o(con, wid)\n"
     "    if r.get('found'):\n"
     "        w = con.execute('SELECT * FROM watched WHERE id=?', (wid,)).fetchone()\n"
     "        x = con.execute('SELECT id, event_tier FROM decklists WHERE '\n"
     "            'lower(player)=lower(?) AND format=? ORDER BY event_date ASC '\n"
     "            'LIMIT 1', (w['key'], w['format'])).fetchone()\n"
     "        r['decklist_id'], r['tier'] = x['id'], x['event_tier']\n"
     "    return r\n"
     "watchlist.check_mtgo_player = _c",
     ["caso_a_vigia_do_jogador_apanha_uma_lista_de_liga"]),
    ("o `apanha_ligas` a dizer sempre que sim",
     "from mtgvault import watchlist\n"
     "_o = watchlist.apanha_ligas\n"
     "def _a(con, wid):\n"
     "    r = _o(con, wid)\n"
     "    r['apanha'] = True\n"
     "    r['porque'] = 'apanha sempre'\n"
     "    return r\n"
     "watchlist.apanha_ligas = _a",
     ["caso_a_vigia_diz_quando_o_formato_nao_conta_ligas"]),
    ("o resultado da vigia a nao levar o `ligas`",
     "from mtgvault import watchlist\n"
     "_o = watchlist.check_mtgo_player\n"
     "def _c(con, wid):\n"
     "    r = _o(con, wid)\n"
     "    r.pop('ligas', None)\n"
     "    return r\n"
     "watchlist.check_mtgo_player = _c",
     ["caso_a_vigia_diz_quando_o_formato_nao_conta_ligas"]),
    # ---------------------------------------------------- as versoes fixas
    ("as versoes ancoradas numa LISTA a desaparecer (o estado de 05/10)",
     "from mtgvault import versoes\n"
     "versoes.versoes_fixas = lambda fmt, cfg=None: []",
     ["caso_as_duas_listas_dele_sao_versoes_marcadas_com_o_nome",
      "caso_uma_versao_fixa_sobrevive_a_poda_das_decklists",
      "caso_uma_lista_anterior_a_janela_entra_e_diz_que_esta_fora"]),
    ("a marca do JOGADOR deitada fora",
     "from mtgvault import versoes\n"
     "_d = versoes.versoes_derivadas\n"
     "def _x(con, fmt, cfg=None, cache=None):\n"
     "    r = _d(con, fmt, cfg, cache)\n"
     "    for v in r.get('versoes') or []:\n"
     "        v['jogador'] = ''\n"
     "    r['jogadores'] = []\n"
     "    return r\n"
     "versoes.versoes_derivadas = _x\n"
     "versoes.jogadores = lambda fmt, cfg=None: []",
     ["caso_as_duas_listas_dele_sao_versoes_marcadas_com_o_nome"]),
    ("uma versao fixa a ser dada como ORFA",
     "from mtgvault import versoes\n"
     "_o = versoes._orfas\n"
     "def _f(vs):\n"
     "    out = list(_o(vs))\n"
     "    for v in vs:\n"
     "        if v.get('fixa') and not v['listas'] and (v['principal'] or v['escolhida']):\n"
     "            out.append({'id': v['id'], 'nome': v['nome'],\n"
     "                'arquetipo_id': None, 'principal': v['principal'],\n"
     "                'escolhida': v['escolhida'], 'candidato': None})\n"
     "    return out\n"
     "versoes._orfas = _f",
     ["caso_uma_versao_fixa_nunca_e_orfa"]),
    # ------------------------------------------------------- as familias
    ("a familia ancorada no CLUSTER em vez das cartas",
     "from mtgvault import versoes\n"
     "def _f(con, fmt, aid, cfg=None, desde=None, cache=None):\n"
     "    fams = versoes.familias(fmt, cfg)\n"
     "    return {'nome': fams[int(aid) % len(fams)]['nome'] if fams else '',\n"
     "            'n': 1, 'de': 1}\n"
     "versoes.familia_do_cluster = _f\n"
     "versoes._familia_da_versao = (lambda con, fmt, aid, v, cfg, desde, cache:\n"
     "    _f(con, fmt, aid, cfg, desde, cache)['nome'])",
     ["caso_as_versoes_vem_agrupadas_por_familia_com_contagem",
      "caso_a_familia_sai_das_cartas_e_nao_do_cluster"]),
    ("a familia de um cluster vazio sem o recurso da lista do deck",
     "from mtgvault import versoes\n"
     "versoes.cartas_fixadas = lambda deck_id, cfg=None: []",
     ["caso_a_familia_de_um_cluster_vazio_sai_da_lista_do_deck"]),
    ("a contagem por familia a desaparecer",
     "from mtgvault import versoes\n"
     "versoes.contagem_de_familias = lambda vs, fams: []",
     ["caso_as_versoes_vem_agrupadas_por_familia_com_contagem"]),
    # ---------------------------------------------------------- as faltas
    ("as faltas num saco so (as partilhadas atribuidas a um dos decks)",
     "from mtgvault import decks_vista as dv\n"
     "_o = dv.faltas_de_jogador\n"
     "def _f(con, fmt, decks, pos, cfg=None, cache=None):\n"
     "    out = _o(con, fmt, decks, pos, cfg, cache)\n"
     "    for j in out:\n"
     "        p = j['partilhadas']\n"
     "        if p['linhas'] and j['versoes']:\n"
     "            j['versoes'][0]['linhas'] = (list(j['versoes'][0]['linhas'])\n"
     "                                         + list(p['linhas']))\n"
     "            j['versoes'][0]['so'] = dict(j['versoes'][0]['so_este'])\n"
     "            j['partilhadas'] = {'cartas': 0, 'copias': 0, 'eur': 0.0,\n"
     "                'eur_nonfoil': 0.0, 'sem_preco': 0, 'linhas': []}\n"
     "    return out\n"
     "dv.faltas_de_jogador = _f",
     ["caso_as_faltas_separam_se_em_tres_sacos"]),
    ("as faltas sem o segundo preco (so o foil)",
     "from mtgvault import decks_vista as dv\n"
     "_o = dv.faltas_de_jogador\n"
     "def _f(con, fmt, decks, pos, cfg=None, cache=None):\n"
     "    out = _o(con, fmt, decks, pos, cfg, cache)\n"
     "    for j in out:\n"
     "        j['totais']['eur_nonfoil'] = 0.0\n"
     "        for v in j['versoes']:\n"
     "            v['so']['eur_nonfoil'] = 0.0\n"
     "            for l in v['linhas']:\n"
     "                l.pop('unit_nonfoil', None)\n"
     "    return out\n"
     "dv.faltas_de_jogador = _f",
     ["caso_as_faltas_levam_os_dois_precos"]),
    # ------------------------------------------------------- o interruptor
    ("o `familias` a ligar-se sempre (o interruptor deixa de existir)",
     "from mtgvault import versoes\n"
     "_PAD = [{'nome': 'Grinding Station', 'cartas': ['Grinding Station'],\n"
     "         'porque': ''},\n"
     "        {'nome': 'Affinity', 'cartas': ['Kappa Cannoneer'], 'porque': ''}]\n"
     "_o = versoes.familias\n"
     "versoes.familias = lambda fmt, cfg=None: (_o(fmt, cfg) or _PAD)",
     ["caso_as_familias_sao_o_interruptor"]),
]

if __name__ == "__main__":
    print(f"a provar {len(ALVOS)} alvos, um processo cada\n")
    bons = sum(1 for n, p, a in ALVOS if passagem(n, p, a))
    print(f"\n{bons}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if bons == len(ALVOS) else 1)
