"""A prova de que o `test_modelo_versoes.py` chumba sem o trabalho de
2026-10-04 à noite (um deck por formato, com versões por dentro).

Um alvo por passagem, num processo próprio (como o `_chumba_decks_vista.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_versoes.py

Um processo por alvo de propósito: o que aqui se desliga são funções de módulo
já importadas (`versoes.do_formato`, `fases.quem_protege`), e num processo só o
primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. o `deck_unico` desligado — o formato volta a ser uma lista de decks;
  2. as VERSÕES a serem decks soltos (a escolha a apanhar todas, e não uma);
  3. a lista dos OUTROS vazia — os que jogam a carta-chave desaparecem;
  4. o critério a dar sempre `passa` — deixa de distinguir versão de outro deck;
  5. a marca `saiu` ignorada — um deck que saiu deixa de o dizer;
  6. a regra **RE** desligada: as versões não escolhidas vão à venda;
  7. a regra **RLG** desligada: as staples de Legacy vão à venda;
  8. o `por_decidir` ignorado — a RLG deixa de se desligar sozinha;
  9. a escolha de versão a aceitar qualquer id (o 409 deixa de existir);
 10. o `escolher` a reescrever a data mesmo sem mudança (o no-op some).
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
import test_modelo_versoes as T
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
    ("o deck unico desligado",
     "from mtgvault import decks_vista as dv\n"
     "dv.deck_unico = lambda *a, **k: None",
     ["caso_o_formato_tem_um_deck_com_versoes",
      "caso_os_outros_que_jogam_a_carta_ficam_a_vista"]),
    ("as versoes a contarem todas como escolhidas",
     "from mtgvault import versoes\n"
     "versoes.versao_escolhida = lambda fmt, cfg=None: ''",
     ["caso_o_formato_tem_um_deck_com_versoes",
      "caso_mudar_a_versao_recalcula_as_proprias_e_as_partilhadas"]),
    ("a lista dos OUTROS vazia",
     "from mtgvault import versoes\n"
     "versoes.outros_que_jogam = lambda *a, **k: []",
     ["caso_os_outros_que_jogam_a_carta_ficam_a_vista",
      "caso_um_outro_que_PASSA_o_criterio_diz_que_passa"]),
    ("o criterio a dar sempre passa",
     "from mtgvault import versoes\n"
     "_o = versoes.outros_que_jogam\n"
     "versoes.outros_que_jogam = lambda *a, **k: "
     "[dict(x, passa_criterio=True) for x in _o(*a, **k)]",
     ["caso_os_outros_que_jogam_a_carta_ficam_a_vista"]),
    ("a marca `saiu` ignorada",
     "from mtgvault import versoes\n"
     "versoes.saiu = lambda *a, **k: None",
     ["caso_um_deck_que_saiu_continua_consultavel"]),
    ("a regra RE desligada",
     "from mtgvault import versoes\n"
     "versoes.nomes_que_ficam = lambda *a, **k: {}",
     ["caso_todas_as_versoes_continuam_protegidas"]),
    ("a regra RLG desligada",
     "from mtgvault import versoes\n"
     "versoes.retidos = lambda *a, **k: {}",
     ["caso_uma_staple_de_um_formato_por_decidir_nao_vai_a_venda"]),
    ("o `por_decidir` ignorado (a RLG nunca se desliga)",
     "from mtgvault import versoes\n"
     "versoes.formatos_por_decidir = lambda cfg=None: ['legacy']",
     ["caso_decidido_o_formato_a_carta_passa_a_candidata"]),
    ("o corte da RLG ignorado (retem tudo o que toca o formato)",
     "from mtgvault import versoes\n"
     "versoes.corte_pct = lambda cfg=None: 0.0",
     ["caso_abaixo_do_corte_nao_retem"]),
    ("a escolha a aceitar qualquer versao",
     "from mtgvault import versoes\n"
     "def _e(cfg, fmt, vid, hoje=None):\n"
     "    cfg.setdefault('decks_por_formato', {}).setdefault(fmt, {})['versao'] = vid\n"
     "    return cfg\n"
     "versoes.escolher = _e",
     ["caso_uma_versao_que_nao_existe_e_recusada"]),
    ("o `escolher` a reescrever a data sempre",
     "from mtgvault import versoes\n"
     "_x = versoes.escolher\n"
     "def _e(cfg, fmt, vid, hoje=None):\n"
     "    d = (cfg.get('decks_por_formato') or {}).get(fmt)\n"
     "    if isinstance(d, dict):\n"
     "        d.pop('versao', None)\n"
     "    return _x(cfg, fmt, vid, hoje)\n"
     "versoes.escolher = _e",
     ["caso_escolher_a_que_ja_la_esta_e_um_no_op"]),
]

if __name__ == "__main__":
    print(f"a provar {len(ALVOS)} alvos, um processo cada\n")
    bons = sum(1 for n, p, a in ALVOS if passagem(n, p, a))
    print(f"\n{bons}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if bons == len(ALVOS) else 1)
