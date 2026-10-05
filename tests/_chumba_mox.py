"""A prova de que o `test_mox_proteger.py` chumba sem o trabalho de 2026-10-05
(montar e proteger são duas perguntas; o critério do Mox Opal é INCLUSIVO).

Um alvo por passagem, num processo próprio (como o `_chumba_versoes.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_mox.py

Um processo por alvo de propósito: o que aqui se desliga são funções de módulo
já importadas (`versoes.nomes_protegidos`, `fases.quem_protege`), e num
processo só o primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. a regra **RP** desligada — volta-se ao critério selectivo de 04/10;
  2. o `protege_todas` ignorado (nenhum formato é inclusivo);
  3. o `protege_todas` LIGADO em todos (o interruptor deixa de existir);
  4. o limiar fixo em 1 (mexer no config deixa de ter efeito);
  5. o limiar a contar pelo MÁXIMO entre formatos em vez da soma;
  6. a RP posta ANTES da R2/R3 — as terras deixam de sair por regra;
  7. o universo das listas COM o filtro de tier — a liga deixa de contar;
  8. o Legacy fora do critério (só Modern protege);
  9. a curva do limiar sem o segundo número;
 10. o `resumo_mox` vazio — a página deixa de dizer o que a regra faz.
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
import test_mox_proteger as T
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
    ("a regra RP desligada",
     "from mtgvault import versoes\n"
     "versoes.nomes_protegidos = lambda *a, **k: {}",
     ["caso_uma_carta_de_lista_de_legacy_de_mox_opal_nao_e_candidata",
      "caso_os_arquetipos_fora_das_versoes_voltam_a_proteger",
      "caso_mudar_o_limiar_muda_o_total_protegido",
      "caso_o_universo_das_listas_nao_leva_o_filtro_de_tier"]),
    ("o `protege_todas` ignorado (nenhum formato e inclusivo)",
     "from mtgvault import versoes\n"
     "versoes.protege_todas = lambda fmt, cfg=None: False",
     ["caso_uma_carta_de_lista_de_legacy_de_mox_opal_nao_e_candidata",
      "caso_montar_e_proteger_sao_conjuntos_diferentes",
      "caso_a_pagina_diz_os_dois_totais_e_o_que_o_legacy_arrastou"]),
    ("o `protege_todas` LIGADO em todos (o interruptor deixa de existir)",
     "from mtgvault import versoes\n"
     # O `caso_sem_o_bloco_no_config_nada_muda` NÃO entra aqui de propósito:
     # com o bloco vazio não há formatos nenhuns para percorrer, por isso o
     # `protege_todas` nunca é perguntado e o interruptor do bloco continua a
     # valer. São duas trancas independentes, e é bom que sejam.
     "versoes.protege_todas = lambda fmt, cfg=None: True",
     ["caso_o_protege_todas_e_o_interruptor"]),
    ("o limiar fixo em 1 (o config deixa de ter efeito)",
     "from mtgvault import versoes\n"
     "versoes.limiar_listas = lambda cfg=None: 1",
     ["caso_mudar_o_limiar_muda_o_total_protegido"]),
    ("o limiar pelo MAXIMO entre formatos em vez da soma",
     "from mtgvault import versoes\n"
     "_c = versoes.contagem_por_carta\n"
     "def _m(con, cfg=None, cache=None):\n"
     "    d = _c(con, cfg, cache)\n"
     "    for v in d.values():\n"
     "        v['listas'] = max(v['formatos'].values())\n"
     "    return d\n"
     "versoes.contagem_por_carta = _m",
     ["caso_o_limiar_conta_a_soma_entre_formatos"]),
    ("a RP posta ANTES da R2/R3 (as terras deixam de sair por regra)",
     "from mtgvault import fases, scryfall, versoes\n"
     "_q = fases.quem_protege\n"
     "def _p(con, res, nm, lot, ctx):\n"
     "    rp = (ctx.get('protegidos') or {}).get(scryfall.chave(nm))\n"
     "    if rp:\n"
     "        return fases.RP, 'RP primeiro', int(lot.get('q') or 0)\n"
     "    return _q(con, res, nm, lot, ctx)\n"
     "fases.quem_protege = _p",
     ["caso_as_terras_continuam_protegidas_pela_regra"]),
    ("o universo das listas COM o filtro de tier (a liga deixa de contar)",
     "from mtgvault import scryfall, sources, versoes\n"
     "def _l(con, fmt, carta, desde=None):\n"
     "    desde = desde or sources.consenso_desde()\n"
     "    sql, par = sources.counting_sql(fmt, 'd')\n"
     "    return [r['id'] for r in con.execute(\n"
     "        'SELECT d.id FROM decklists d WHERE d.format=? AND '\n"
     "        'd.event_date>=? AND ' + sql + ' AND EXISTS (SELECT 1 FROM '\n"
     "        'decklist_cards k WHERE k.decklist_id=d.id AND '\n"
     "        + scryfall.sql_nome('k.card_name') + ')',\n"
     "        [fmt, desde] + list(par) + list(scryfall.params_nome(carta)))]\n"
     "versoes.listas_da_carta = _l",
     ["caso_o_universo_das_listas_nao_leva_o_filtro_de_tier"]),
    ("o Legacy fora do criterio (so o Modern protege)",
     "from mtgvault import versoes\n"
     "_f = versoes.formatos_inclusivos\n"
     "versoes.formatos_inclusivos = lambda cfg=None: "
     "[f for f in _f(cfg) if f != 'legacy']",
     ["caso_uma_carta_de_lista_de_legacy_de_mox_opal_nao_e_candidata",
      "caso_o_protege_todas_e_o_interruptor",
      "caso_a_pagina_diz_os_dois_totais_e_o_que_o_legacy_arrastou"]),
    ("a curva do limiar sem o segundo numero",
     "from mtgvault import fases\n"
     "_c = fases.curva_limiar\n"
     "def _k(con, res, limiares=(1, 2, 3), cfg=None, cache=None):\n"
     "    curva, uma = _c(con, res, limiares, cfg, cache)\n"
     "    for x in curva:\n"
     "        x['sozinha'] = dict(x['a_mais'], copias=0, valor=0.0)\n"
     "    return curva, uma\n"
     "fases.curva_limiar = _k",
     ["caso_a_curva_do_limiar_da_os_dois_numeros"]),
    ("o `resumo_mox` vazio (a pagina deixa de dizer o que a regra faz)",
     "from mtgvault import fases\n"
     "fases.resumo_mox = lambda *a, **k: {}",
     ["caso_a_pagina_diz_os_dois_totais_e_o_que_o_legacy_arrastou"]),
]

if __name__ == "__main__":
    print(f"a provar {len(ALVOS)} alvos, um processo cada\n")
    bons = sum(1 for n, p, a in ALVOS if passagem(n, p, a))
    print(f"\n{bons}/{len(ALVOS)} alvos chumbam como devem")
    sys.exit(0 if bons == len(ALVOS) else 1)
