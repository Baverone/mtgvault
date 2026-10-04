"""Corre UM caso do `test_papel_grande` com a funcionalidade desligada.

`py tests/_chumba_papel.py <alvo> <nome_do_caso>` — sai a 0 se o caso PASSAR (o
que é mau: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Está num
processo próprio porque o `test_papel_grande` fixa o `MTGVAULT_CONFIG`, o
`MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  indice     — o índice volta a dar só IDS (é o `parse_event_ids` de sempre, que
               numa página de Modern dá 375 ids de que só 20 são eventos). Sem
               nome não há como saltar uma liga antes de pedir a página, nem como
               reconhecer um torneio grande;
  ordem      — os eventos voltam a entrar pela ordem do índice e cortados em
               `max_events`: um RC em 20.º lugar fica fora PARA SEMPRE, que é o
               defeito que esta ordem veio fechar;
  liga       — a liga volta a ser saltada DEPOIS de se pedir a página do evento
               (o `if event_tier(...) == "League"` de 2026-09-07): cada liga gasta
               um lugar E um pedido;
  tecto      — o tecto de listas volta a ser sempre o normal: o RC de 1 486
               jogadores volta a entrar com 16 das suas 64 listas;
  memoria    — a memória deixa de responder, e cada corrida volta a pedir a página
               de todos os eventos do índice (é o que tornava caro ir mais fundo);
  marcador   — a recolha deixa de ESCREVER na memória: a leitura funciona e nunca
               tem nada lá dentro — o verde a fingir;
  marca_cedo — o evento é marcado ANTES de se lerem os `.dec` (como a primeira
               versão fazia): um `.dec` que falhe deixa a lista a faltar PARA
               SEMPRE, porque o evento fica dado por feito;
  semente_vazia — a guarda da semente volta a ser «a tabela está vazia» em vez da
               marca: a semente volta a correr e TAPA a repetição do evento que
               não se marcou;
  semente    — a semente não corre: as 48 listas que faltam ao RC que já está na
               base nunca entram, porque o evento não é visitado;
  jogadores  — o `por_fazer` volta a decidir com o tecto optimista em vez dos
               jogadores lembrados: um «Store Championship» de 25 jogadores é
               pedido todas as noites, para sempre;
  aviso      — o passo do daily deixa de ler a base e não avisa nunca.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_papel_grande as T                                 # noqa: E402

import daily                                                  # noqa: E402
from mtgvault import mtgtop8, sources                         # noqa: E402

if alvo == "indice":
    mtgtop8.parse_event_rows = lambda html: []
    mtgtop8.parse_paginas_indice = lambda html: 1
elif alvo == "ordem":
    # A ordem do índice e o corte em `max_events`, como era: o grande não salta a
    # fila nem entra se estiver fora dos primeiros.
    _cand = mtgtop8.candidatos_do_indice

    def _pela_ordem(linhas, fmt, max_events, cfg=None):
        out, ligas = _cand(linhas, fmt, 10 ** 6, cfg)
        pela_ordem = [li for li in linhas if li["id"] in {x["id"] for x in out}]
        return pela_ordem[:max_events], ligas

    mtgtop8.candidatos_do_indice = _pela_ordem
elif alvo == "liga":
    # A liga deixa de ser reconhecida pelo nome do índice, e volta a custar o
    # pedido da página do evento.
    _cand = mtgtop8.candidatos_do_indice
    mtgtop8.candidatos_do_indice = (
        lambda linhas, fmt, max_events, cfg=None:
        ([{**li, "grande": mtgtop8.e_grande(li["nome"], cfg)}
          for li in linhas][:max_events], 0))
elif alvo == "tecto":
    mtgtop8.tecto_do_evento = (
        lambda grande, players, tecto_normal, cfg=None: tecto_normal)
elif alvo == "memoria":
    mtgtop8.memoria_dos_eventos = lambda con, fmt: {}
    mtgtop8.por_fazer = lambda linha, grande, tecto_normal, cfg=None: True
elif alvo == "marcador":
    mtgtop8._registar_evento = lambda *a, **kw: None
elif alvo == "marca_cedo":
    # O evento marca-se quando a página é lida e não quando os `.dec` acabam —
    # era o que a primeira versão fazia. O `falhou_um_dec` deixa de contar.
    _reg = mtgtop8._registar_evento
    _get_antigo = mtgtop8._get
    marcados: set = set()

    def _get_e_marca(path, **params):
        html = _get_antigo(path, **params)
        if path == "/event":
            marcados.add(int(params["e"]))
        return html

    def _reg_tardio(con, eid, fmt, **kw):
        if eid in marcados:            # já foi marcado à cabeça; não repete
            return None
        return _reg(con, eid, fmt, **kw)

    # Marca à cabeça, pela página do evento, e desliga o registo do fim.
    def _harvest_marca_cedo(con, fmt, *a, **kw):
        import mtgvault.mtgtop8 as M
        orig = M._get

        def _g(path, **params):
            html = orig(path, **params)
            if path == "/event":
                todos = M.parse_deck_ids(html)
                meta = M.parse_event_meta(html)
                _reg(con, int(params["e"]), fmt.lower(),
                     nome=meta["event_name"] or "", data=meta["event_date"],
                     grande=False, players=meta.get("players"),
                     na_pagina=len(todos), tecto=kw.get("max_decks_per_event", 16))
                con.commit()
            return html

        M._get = _g
        M._registar_evento = lambda *x, **y: None
        try:
            return _harvest(con, fmt, *a, **kw)
        finally:
            M._get = orig

    _harvest = mtgtop8.harvest
    mtgtop8.harvest = _harvest_marca_cedo
elif alvo == "semente_vazia":
    # A guarda antiga: «a tabela está vazia». Com ela, um evento cujo `.dec`
    # falhou — e que por isso NÃO se marcou — é deduzido das listas que deixou e
    # marcado com o tecto antigo na corrida seguinte: a repetição morre.
    _semear = mtgtop8.semear_memoria

    def _semear_vazia(con):
        if con.execute("SELECT 1 FROM mtgtop8_eventos WHERE event_id > 0 LIMIT 1"
                       ).fetchone():
            return 0
        con.execute("DELETE FROM mtgtop8_eventos WHERE event_id = 0")
        con.commit()
        return _semear(con)

    mtgtop8.semear_memoria = _semear_vazia
elif alvo == "semente":
    mtgtop8.semear_memoria = lambda con: 0
elif alvo == "revisita_do_indice":
    # A primeira versão: as revisitas escolhiam-se entre os candidatos do ÍNDICE.
    # O RC de 12/09 não está no índice de hoje (20/09-03/10) e nunca era
    # recuperado — as 48 listas não vinham.
    _pend = mtgtop8.revisitas_pendentes
    mtgtop8.revisitas_pendentes = lambda con, fmt, tecto, cfg=None: []
elif alvo == "grande_na_semente":
    # O `grande` da semente a 0, como a primeira versão escrevia: com as revisitas
    # a lerem-se da memória, isso é o mesmo que não haver recuperação nenhuma.
    _sem = mtgtop8.semear_memoria

    def _sem_sem_grande(con):
        n = _sem(con)
        con.execute("UPDATE mtgtop8_eventos SET grande = 0 WHERE event_id > 0")
        con.commit()
        return n

    mtgtop8.semear_memoria = _sem_sem_grande
elif alvo == "jogadores":
    # O defeito da primeira versão: decidir com o tecto OPTIMISTA (o nome é
    # grande) e gravar o real (os jogadores são poucos) — revisita para sempre.
    def _optimista(linha, grande, tecto_normal, cfg=None):
        if linha is None:
            return True
        if linha.get("completo"):
            return False
        r = mtgtop8.regras_grandes(cfg)
        tecto = (max(tecto_normal, r["listas_por_evento"]) if grande
                 else tecto_normal)
        return int(linha.get("tecto") or 0) < tecto

    mtgtop8.por_fazer = _optimista
elif alvo == "aviso":
    mtgtop8.grandes_de_hoje = lambda con, dia=None: []
else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

getattr(T, caso)()
print(f"PASSOU SEM A FUNCIONALIDADE (alvo={alvo}): {caso}")
