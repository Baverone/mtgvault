"""Corre UM caso do `test_foto_manda` com uma peça da funcionalidade desligada.

`py tests/_chumba_foto_manda.py <alvo> <nome_do_caso>` — sai a 0 se o caso
passar (o que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom).
Está num processo próprio porque o `test_foto_manda` fixa o `MTGVAULT_CONFIG`,
o `MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ANTES desta ordem numa peça só:

  manda      — o interruptor nunca liga: a foto volta a ser só um ✓ que não mexe
               um número, que é exactamente o que era até 2026-10-02;
  pct        — o `pct`/`tenho` de cada caixa volta a ser o FÍSICO: um deck
               sleevado e por fotografar volta a dizer-se completo;
  venda      — o filtro `filtrar_sem_foto` desaparece: as 114 cópias da base
               dele voltam à lista de venda sem uma única foto desta campanha;
  alocacao   — a foto deixa de mandar na alocação: o registo volta a ganhar à
               foto (o ponto 5 de 09/09), e a pasta do deck deixa de decidir;
  extras     — a foto nos Extras deixa de TIRAR a alocação: a cópia fica no deck
               onde estava, apesar de a foto provar que está fora dele;
  dupla      — a trava da alocação dupla desaparece: a mesma cópia volta a poder
               ficar em dois decks;
  metades    — o `metades` deixa de conferir a soma: uma metade perdida pelo
               caminho passa a dar um par de números com cara de honesto;
  topo       — o relatorio deixa de levar as duas metades: nenhuma pagina tem
               por onde dizer o que esta confirmado e o que esta por confirmar;
  playset    — o tecto de playset do Premodern volta: a regra que ele mandou
               esquecer volta a cortar compras.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_foto_manda as T                                   # noqa: E402
from mtgvault import confirmado, loadout                      # noqa: E402

if alvo == "manda":
    confirmado.manda = lambda cfg=None: False
    loadout._conf.manda = confirmado.manda
elif alvo == "pct":
    # O `allocate` volta a escrever o pct FÍSICO, como antes de 02/10.
    _al = loadout.allocate

    def _fisico(con, cfg_slots=None):
        res = _al(con, cfg_slots)
        for s in res["slots"]:
            s["tenho"] = s.get("tenho_fisico", s["tenho"])
            s["pct"] = s.get("pct_fisico", s["pct"])
        return res

    loadout.allocate = _fisico
elif alvo == "topo":
    # As DUAS METADES saem do RELATORIO: e o mtgvault de ontem, onde nenhuma
    # pagina tinha por onde dizer o que esta confirmado e o que esta por
    # confirmar. E o unico alvo que APAGA chaves em vez de trocar uma resposta,
    # porque e isso que «retirar a funcionalidade» quer dizer aqui. Patcha-se o
    # `report` e nao o `allocate`: e o `report` que junta os totais no topo, e
    # strippa-los do `allocate` so os via o `report` a reescrever.
    _rep = loadout.report

    def _sem_metades(con, cfg_slots=None):
        res = _rep(con, cfg_slots)
        for k in ("tenho_conf_total", "fotografar_total", "tenho_fisico_total",
                  "cartas_metades"):
            res.pop(k, None)
        for s in res["slots"]:
            for k in ("tenho_conf", "fotografar", "tenho_fisico", "pct_fisico",
                      "cartas_metades"):
                s.pop(k, None)
        return res

    loadout.report = _sem_metades
elif alvo == "venda":
    confirmado.filtrar_sem_foto = lambda linhas: (list(linhas), [])
    loadout._conf.filtrar_sem_foto = confirmado.filtrar_sem_foto
elif alvo == "alocacao":
    # A foto volta a NÃO decidir o deck: é o `alvo_da_pasta` a dizer sempre «não
    # sei», que é o mtgvault de ontem — a foto ligava-se à cópia e mais nada.
    confirmado.alvo_da_pasta = lambda photo_path: (False, None)
elif alvo == "extras":
    _ap = confirmado.alvo_da_pasta
    confirmado.alvo_da_pasta = (
        lambda p: (lambda d, s: (d and s is not None, s))(*_ap(p)))
elif alvo == "dupla":
    confirmado.exige_alocacao_unica = lambda con, linhas, permitir=None: None
    confirmado.exige_uma_so = lambda con, cid, slot, q: None
    loadout._conf.exige_alocacao_unica = confirmado.exige_alocacao_unica
    loadout._conf.exige_uma_so = confirmado.exige_uma_so
elif alvo == "metades":
    def _sem_conferir(confirmado_, total, *, unidade="cartas", casas=0):
        """A versão ingénua: devolve as duas parcelas sem exigir que somem — e
        a de baixo vem de uma segunda conta, que é como elas divergem."""
        return {"confirmado": confirmado_, "por_confirmar": total,
                "total": total, "pct": 0, "unidade": unidade, "frase": ""}

    confirmado.metades = _sem_conferir
    loadout._conf.metades = _sem_conferir
elif alvo == "playset":
    loadout.playset_maximo = lambda s: (int(s["playset_maximo"])
                                        if s.get("playset_maximo") else None)
else:
    print(f"alvo desconhecido: {alvo}")
    sys.exit(2)

fn = getattr(T, caso)
try:
    fn()
except AssertionError as e:
    print(f"CHUMBOU (bom): {caso} com {alvo} desligado -> {e}")
    sys.exit(1)
except Exception as e:                                        # noqa: BLE001
    print(f"CHUMBOU (bom, por erro): {caso} com {alvo} -> {type(e).__name__} {e}")
    sys.exit(1)
print(f"PASSOU (MAU): {caso} passa com {alvo} desligado")
sys.exit(0)
