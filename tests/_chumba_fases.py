"""Corre UM caso do `test_fases` com uma das quatro protecções desligada.

`py tests/_chumba_fases.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o `test_fases`
fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o `MTGVAULT_DB` no import, e
partilhá-los com outro teste era pôr um a mexer no ambiente do outro.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  terras       — a P1 desaparece: as shocklands e as fetchlands voltam a ser
                 cartas como as outras e o excedente delas vai à venda;
  rl_joga      — a P2 desaparece: a Reserved List que ele joga deixa de estar
                 protegida e volta a depender só da regra dos 5 %;
  decisoes     — a P3 desaparece: a decisão de cada deck deixa de ser lida
                 (tudo conta como `dissolvido`), que é o mtgvault antes de os
                 três estados existirem;
  omissao      — a OMISSÃO passa a `dissolvido`. É o erro que mais dinheiro
                 custava: um deck novo, sem decisão, punha o conteúdo à venda;
  reservas     — a P4 desaparece: a reserva («maybe») deixa de proteger;
  limiar       — o limiar desce a zero: a reserva apanha tudo o que alguma vez
                 apareceu numa lista, e é o efeito perverso que a ordem nomeia;
  min_listas   — o mínimo de listas desaparece: um «consenso» de 3 listas volta
                 a encher a reserva (33 % numa lista só passa qualquer limiar);
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

if alvo == "terras":
    fases.terras_protegidas = lambda con, cache=None: {}
elif alvo == "rl_joga":
    fases.rl_que_joga = lambda con, res, cfg=None: {}
elif alvo == "decisoes":
    fases.decisoes = lambda cfg=None: {}
    fases.DECISAO_OMISSAO = fases.DISSOLVIDO
elif alvo == "omissao":
    fases.DECISAO_OMISSAO = fases.DISSOLVIDO
    _de = fases.decisao_de
    fases.decisao_de = lambda c: _de(c) if c.get("decisao") else fases.DISSOLVIDO
    fases.decisoes = lambda cfg=None: {
        c["slot"]: fases.decisao_de(c)
        for c in __import__("mtgvault.caixas", fromlist=["x"]).do_config(cfg)
        if c.get("slot")}
elif alvo == "reservas":
    fases.reservas = lambda con, res, limiar=None, cache=None: {}
elif alvo == "limiar":
    fases.limiar_pct = lambda cfg=None: 0
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

    def _sem_ordem(con, res, cfg=None, cache=None, cands=None):
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
