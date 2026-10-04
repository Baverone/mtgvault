"""A prova de que o `test_listas_de_eventos.py` chumba sem o trabalho de
2026-10-04 ao fim do dia.

Um alvo por passagem, num processo próprio (como o `_chumba_decks_vista.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_listas_eventos.py

Um processo por alvo de propósito: o que aqui se desliga são funções de módulo em
memória (`eventos.criterios`, `eventos.fixar`, `dv.decks_de_evento`), e num
processo só o primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. o critério PRESENCIAL desligado — uma Challenge grande ganha ao papel;
  2. o critério do CAMPO desligado — um 1.º de 16 ganha a um 5-8 de 218;
  3. o critério do TIER desligado — a Challenge com contagem ganha à
     qualificação sem contagem, ou seja a FONTE decide em vez do torneio;
  4. o critério da REPETIDA desligado — o tricampeão perde para a mais recente;
  5. as VITÓRIAS trocadas por RESULTADOS — três 9-16 ganham a um 5-8 (o defeito
     medido no Esper Blink);
  6. o critério da JANELA desligado — escolhe-se a presencial pré-Reality
     Fracture e a alternativa deixa de existir;
  7. a excepção do PREMODERN desligada — a história toda deixa de contar lá;
  8. a PROVENIÊNCIA a não ser gravada — a caixa fica sem ficha depois da poda;
  9. o `_consenso_anterior` a ser PISADO por uma segunda passagem;
 10. a marca `e_consenso` desligada — a média volta a ter a cara de uma lista
     real;
 11. os `decks_de_evento` fora do registo — os dez decks dele desaparecem;
 12. o `por_confirmar` ignorado — o deck à espera parece decidido;
 13. a `amostra_fina` ignorada — o Hammer Time aparece com o peso dos outros;
 14. a `alternativa` deixada de fora — a melhor presencial desaparece em vez de
     ficar ao lado.
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
import test_listas_de_eventos as T
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
    linha = next((x for x in r.stdout.splitlines() if x.startswith("@@")), None)
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


def _sem(criterio: str) -> str:
    return ("from mtgvault import eventos\n"
            "eventos.criterios = lambda: [c for c, _r in eventos.REGRA_OMISSAO "
            f"if c != {criterio!r}]")


ALVOS = [
    ("o criterio do CAMPO desligado", _sem("campo"),
     ["caso_entre_presenciais_ganha_o_campo_maior"]),
    # O TIER é UM critério e responde às duas afirmações dele: «presenciais antes
    # de online» (o primeiro degrau) e «um Qualifier antes de uma Challenge».
    # Houve uma passagem com os dois separados e o «presencial» nunca mudava
    # nada — foi este ficheiro que o apanhou, a tentar prová-lo.
    ("o criterio do TIER desligado", _sem("tier"),
     ["caso_a_regra_prefere_presencial_a_online",
      "caso_entre_online_ganha_o_evento_mais_importante"]),
    ("o criterio da REPETIDA desligado", _sem("repetida"),
     ["caso_a_lista_repetida_ganha_a_um_resultado_unico_melhor"]),
    # 5. VITÓRIAS -> RESULTADOS: o defeito que o Esper Blink mediu.
    ("as vitorias trocadas por resultados",
     "from mtgvault import eventos\n"
     "eventos._vitorias = eventos._repeticoes",
     ["caso_a_lista_repetida_ganha_a_um_resultado_unico_melhor"]),
    ("o criterio da JANELA desligado", _sem("janela"),
     ["caso_a_janela_filtra_primeiro_e_a_alternativa_fica_ao_lado"]),
    # 7. A excepção do premodern: sem ela a janela corta lá também.
    ("a excepcao do premodern desligada",
     "from mtgvault import sources\n"
     "sources.consenso_desde = lambda fmt=None: '2026-09-29'",
     ["caso_o_premodern_esta_excepcionado_da_janela"]),
    # 8. A proveniência a não ser gravada.
    ("a proveniencia a nao ser gravada",
     "from mtgvault import eventos\n"
     "_f = eventos.fixar\n"
     "def _sem_prov(cfg, con, chave, did, **kw):\n"
     "    rec = _f(cfg, con, chave, did, **kw)\n"
     "    rec.pop('evento', None)\n"
     "    return rec\n"
     "eventos.fixar = _sem_prov",
     ["caso_a_proveniencia_grava_se_e_sobrevive_a_poda",
      "caso_a_caixa_trocada_mostra_as_seis_coisas"]),
    # 9. O consenso guardado a ser pisado (o defeito que custou duas medições).
    ("o consenso anterior a ser pisado",
     "from mtgvault import eventos\n"
     "_f = eventos.fixar\n"
     "def _pisa(cfg, con, chave, did, **kw):\n"
     "    (cfg.get('listas_escolhidas') or {}).get(chave, {}).pop(\n"
     "        '_consenso_anterior', None)\n"
     "    return _f(cfg, con, chave, did, **kw)\n"
     "eventos.fixar = _pisa",
     ["caso_o_consenso_anterior_fica_guardado_e_nao_se_pisa"]),
    # 10. A marca do consenso desligada.
    ("a marca e_consenso desligada",
     "from mtgvault import decks_vista as dv\n"
     "_a = dv.arquetipos_meta\n"
     "dv.arquetipos_meta = lambda *a, **k: [\n"
     "    {**m, 'e_consenso': False, 'rotulo_estado': ''} for m in _a(*a, **k)]",
     ["caso_nenhum_deck_mostra_consenso_como_se_fosse_a_lista"]),
    # 11. Os decks dele fora do registo.
    ("os decks dele fora do registo",
     "from mtgvault import decks_vista as dv\n"
     "dv.decks_de_evento = lambda con, cfg=None: []",
     ["caso_os_decks_dele_entram_mesmo_sem_nome_da_fonte",
      "caso_o_deck_por_confirmar_nao_fica_marcado",
      "caso_a_amostra_fina_vai_para_a_pagina"]),
    # 12. O `por_confirmar` ignorado.
    ("o por_confirmar ignorado",
     "from mtgvault import decks_vista as dv\n"
     "_d = dv.decks_de_evento\n"
     "dv.decks_de_evento = lambda con, cfg=None: [\n"
     "    {**x, 'por_confirmar': False, 'carta_chave': ''} for x in _d(con, cfg)]",
     ["caso_o_deck_por_confirmar_nao_fica_marcado"]),
    # 13. A amostra fina ignorada.
    ("a amostra fina ignorada",
     "from mtgvault import decks_vista as dv\n"
     "_d = dv.decks_de_evento\n"
     "dv.decks_de_evento = lambda con, cfg=None: [\n"
     "    {**x, 'amostra_fina': ''} for x in _d(con, cfg)]",
     ["caso_a_amostra_fina_vai_para_a_pagina"]),
    # 14. A alternativa deixada de fora.
    ("a alternativa deixada de fora",
     "from mtgvault import eventos\n"
     "_e = eventos.escolher\n"
     "eventos.escolher = lambda con, fmt, ids: {\n"
     "    **_e(con, fmt, ids), 'alternativa': None}",
     ["caso_a_janela_filtra_primeiro_e_a_alternativa_fica_ao_lado"]),
]


def main() -> int:
    print(f"a provar {len(ALVOS)} alvos, um processo por alvo\n")
    bons = sum(1 for nome, prep, alvos in ALVOS if passagem(nome, prep, alvos))
    print(f"\n{bons}/{len(ALVOS)} alvos chumbam como devem")
    return 0 if bons == len(ALVOS) else 1


if __name__ == "__main__":
    sys.exit(main())
