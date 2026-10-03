"""Corre UM caso do `test_janela_consenso` com a funcionalidade desligada.

`py tests/_chumba_janela.py <alvo> <nome_do_caso>` — sai a 0 se o caso PASSAR (o
que é mau: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_janela.py`; está num processo próprio porque o
`test_janela_consenso` fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o
`MTGVAULT_DB` no import, e porque metade do que aqui se desliga é global.

Cada `alvo` é o mtgvault de ontem numa peça só:

  corte      — o `consenso_desde` devolve sempre `""`: a janela desaparece e o
               consenso volta a contar Setembro inteiro;
  sql        — o `counting_sql` deixa de levar o corte por omissão. É o defeito
               mais provável: a primeira consulta nova que se esquecesse dele;
  python     — o `lista_conta` ignora a data, e o SQL e o Python passam a dar
               duas respostas à mesma pergunta;
  amostra    — a percentagem volta a viajar abaixo do mínimo de listas: com 2
               listas uma carta «aparece em 50 %»;
  frase      — a frase da amostra insuficiente fica vazia, e a página volta a
               dizer só *"só N listas contam"*;
  reserva    — a R5 passa a levar o corte do consenso: é o conflito que a ordem
               manda assinalar e NÃO aplicar (medido: +426 cópias na venda);
  derivada   — a assinatura derivada passa a levar o corte, e a reserva de uma
               caixa sem assinatura escrita desaparece em silêncio;
  seguir     — o `my_decks` passa a levar o corte: seguir UMA lista deixa de ser
               diferente de calcular um consenso;
  excepcoes  — as excepções por formato são ignoradas, e o Premodern (onde o set
               não é legal) perde o consenso por nada;
  paginas    — a janela deixa de viajar para o rodapé: as páginas mostram um
               quinto das listas sem dizer porquê;
  daily      — o passo do daily deixa de dizer a janela, e o log de um dia com
               corte fica igual ao de um dia sem.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_janela_consenso as T                             # noqa: E402
from mtgvault import consenso, fases, loadout, sources       # noqa: E402

if alvo == "corte":
    sources.consenso_desde = lambda fmt=None, cfg=None: ""
elif alvo == "sql":
    _cs = sources.counting_sql
    sources.counting_sql = (lambda fmt, alias="d", consenso=True:
                            _cs(fmt, alias, consenso=False))
elif alvo == "python":
    _lc = sources.lista_conta
    sources.lista_conta = (lambda row, fmt=None, consenso=True:
                           _lc(row, fmt, consenso=False))
elif alvo == "amostra":
    # A percentagem volta a sair sempre, e os papéis com ela.
    _c = consenso.consenso

    def _sempre_pct(con, comandante, fmt=None):
        out = _c(con, comandante, fmt)
        n = out["listas"] or 1
        for x in out["cartas"]:
            x["pct"] = round(100 * x["listas"] / n, 1)
            x["papel"] = consenso.papel(x["pct"])
        out["amostra"] = ""
        out["suficiente"] = True
        return out

    consenso.consenso = _sempre_pct
elif alvo == "frase":
    sources.texto_amostra = lambda listas, minimo, fmt=None: ""
elif alvo == "reserva":
    # A R5 a levar o corte: é exactamente o que a ordem manda NÃO fazer.
    _ids = sources.ids_por_assinatura

    def _com_corte(con, fmt, assinatura, todas=False, desde=None,
                   so_que_contam=True, sem=None):
        return _ids(con, fmt, assinatura, todas=todas, sem=sem,
                    desde=sources.consenso_desde(fmt) or desde,
                    so_que_contam=True)

    sources.ids_por_assinatura = _com_corte
    fases.sources.ids_por_assinatura = _com_corte
elif alvo == "derivada":
    _cs = sources.counting_sql
    fases.sources.counting_sql = (lambda fmt, alias="d", consenso=False:
                                  _cs(fmt, alias, consenso=True))
elif alvo == "seguir":
    import my_decks
    my_decks._conta = lambda fmt: sources.counting_sql(fmt, "dl")
    my_decks._conta.__doc__ = ""
elif alvo == "excepcoes":
    _r = sources.regras_consenso

    def _sem_excepcoes(cfg=None):
        r = dict(_r(cfg))
        r["excepcoes"] = []
        return r

    sources.regras_consenso = _sem_excepcoes
elif alvo == "paginas":
    sources.frase_janela_rodape = lambda: ""
    sources.texto_janela_consenso = lambda fmt=None: ""
    import comandantes
    comandantes._rodape = lambda: comandantes._RODAPE.replace("%JANELA%", "")
elif alvo == "daily":
    import daily
    daily._janela_consenso = lambda: "feito"
else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

getattr(T, caso)()
print(f"[MAU] {caso} passou com '{alvo}' desligado")
