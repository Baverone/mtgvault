"""Corre UM caso do `test_fases` com uma das quatro protecções desligada.

`py tests/_chumba_fases.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o `test_fases`
fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o `MTGVAULT_DB` no import, e
partilhá-los com outro teste era pôr um a mexer no ambiente do outro.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  duais        — a R1 desaparece: as duais originais voltam a ser Reserved List
                 como as outras, e a quota das quatro fora dos decks não morde;
  duais_quota  — a quota passa a infinita: nunca sobra uma dual para vender,
                 que é o contrário do *"o que passar disso vende-se"*;
  terras       — a R2/R3 desaparece: as shocklands e as fetchlands voltam a ser
                 cartas como as outras e o excedente delas vai à venda;
  rl_joga      — a R4 desaparece: a Reserved List que ele joga deixa de estar
                 protegida e volta a depender só da regra dos 5 %;
  estados      — a RD desaparece: o estado de cada caixa deixa de ser lido e
                 nada do que está num deck fica protegido;
  omissao      — a OMISSÃO deixa de proteger (uma caixa sem `estado` passa a
                 `candidata`). É o erro que mais dinheiro custava: um deck novo
                 punha o conteúdo à venda;
  reservas     — a R5 desaparece: a reserva («maybe») deixa de proteger;
  janela       — a janela da R5 passa a infinita: a reserva apanha tudo o que
                 alguma vez apareceu numa lista, e é o efeito perverso que a
                 ordem nomeia por outra porta;
  staples      — a R5b desaparece: as staples de sideboard de Premodern deixam
                 de estar protegidas;
  min_listas   — o mínimo de listas desaparece: um «consenso» de 3 listas volta
                 a encher a reserva (é o Ill-Gotten Gains, que ele nomeou);
  congelado    — a trava do RC Ghent desaparece e a exportação volta a correr;
  ate4         — o tecto das 4 cartas por foto desaparece: uma foto volta a
                 levar o que lhe caia, que é o monte de 33 cartas das antigas;
  por_tipo     — a fila deixa de se agrupar por tipo de carta, que é
                 exactamente o contrário da ordem que ele deu;
  explode      — a fila volta à regra ERRADA de 2026-10-01 (uma linha por CÓPIA
                 FÍSICA: um playset dá quatro fotos em vez de uma);
  ordem_fila   — a fila dos candidatos deixa de sair por valor decrescente.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_fases as T                                       # noqa: E402
from mtgvault import fases                                   # noqa: E402

if alvo == "duais":
    # A R1 desaparece e as duais voltam a ser RL como as outras.
    fases.duais = lambda con, cache=None, exigir=None: {
        "nomes": [], "regra": "(desligada)", "n": 0,
        "alvo_fora": fases.DUAIS_ALVO_FORA}
elif alvo == "duais_quota":
    fases.DUAIS_ALVO_FORA = 10 ** 6
elif alvo == "terras":
    fases.terras_protegidas = lambda con, cache=None: {}
elif alvo == "rl_joga":
    fases.rl_que_joga = lambda con, res, cfg=None, cache=None: {}
elif alvo == "estados":
    fases.estados = lambda cfg=None: {}
    fases.ESTADO_OMISSAO = "candidata"
elif alvo == "omissao":
    # A omissão deixa de proteger: uma caixa sem `estado` passa a candidata.
    fases.ESTADO_OMISSAO = "candidata"
    _ca = __import__("mtgvault.caixas", fromlist=["x"])
    fases.estado_de = lambda c: (_ca.estado_de(c) if c.get("estado")
                                 else "candidata")
    fases.estados = lambda cfg=None: {
        c["slot"]: fases.estado_de(c) for c in _ca.do_config(cfg)
        if c.get("slot")}
elif alvo == "reservas":
    fases.reservas = lambda con, res, _i=None, cache=None: {}
elif alvo == "janela":
    fases.janela_dias = lambda cfg=None: 10 ** 5
elif alvo == "staples":
    fases.staples_sideboard = lambda con, fmt=fases.STAPLES_FORMATO, corte=None, \
        desde=None, cache=None: {"formato": fmt, "corte": 100.0, "desde": "",
                                 "listas": 0, "com_sideboard": 0, "todas": [],
                                 "nomes": {}, "n": 0, "provisorio": False,
                                 "regra": "(desligada)"}
elif alvo == "min_listas":
    fases.MIN_LISTAS_RESERVA = 1
elif alvo == "congelado":
    fases.congelado_ate = lambda cfg=None: ""
elif alvo == "ate4":
    # Sem tecto: uma foto leva tudo o que lhe caia (o monte das antigas).
    from mtgvault import fotos as _ft                        # noqa: E402

    _ag = _ft.agrupar
    _ft.agrupar = lambda linhas, **kw: _ag(linhas, **{**kw, "max_cartas": 10 ** 6})
    _ft.valida = lambda cartas, max_cartas=_ft.MAX_CARTAS: int(cartas or 0) > 0
elif alvo == "por_tipo":
    # A fila deixa de se agrupar por tipo: as fotos atravessam tipos.
    from mtgvault import fotos as _ft                        # noqa: E402

    _ag = _ft.agrupar
    _ft.agrupar = lambda linhas, **kw: _ag(linhas, **{**kw, "por_tipo": False})
elif alvo == "explode":
    # A regra ERRADA que esteve escrita: uma linha por CÓPIA FÍSICA.
    from mtgvault import fotos as _ft                        # noqa: E402

    _ag = _ft.agrupar

    def _explode(linhas, **kw):
        soltas = [dict(l, q=1) for l in linhas for _ in range(int(l.get("q") or 0))]
        return _ag(soltas, **{**kw, "max_cartas": 1})

    _ft.agrupar = _explode
elif alvo == "ordem_fila":
    _fc = fases.fila_candidatos

    def _sem_ordem(con, res, cfg=None, cache=None, cands=None):  # noqa: ANN001
        r = _fc(con, res, cfg, cache, cands)
        # A ordem de ontem: pelo nome, que é o que uma lista "arrumada" daria.
        r["fotos"] = sorted(r["fotos"],
                            key=lambda f: (f["itens"][0]["nm"], f["n"]))
        r["lotes"] = fases._filas_por_lotes(r["fotos"])
        return r

    fases.fila_candidatos = _sem_ordem
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
