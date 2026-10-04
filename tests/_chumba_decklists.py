"""Corre UM caso do `test_decklists_no_site` com a funcionalidade desligada.

`py tests/_chumba_decklists.py <alvo> <nome_do_caso>` — sai a 0 se o caso PASSAR
(o que é mau: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Está num
processo próprio porque o `test_decklists_no_site` fixa o `MTGVAULT_CONFIG`, o
`MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  escala       — o tecto volta a depender SÓ do nome (a regra de 04/10 de manhã):
                 o RC de 1 486 jogadores é apanhado pelo padrão «championship»,
                 mas o «Buckeye Brawl II» de 125 jogadores volta a 16 — e era ele
                 o que tinha 16 listas a mais para dar;
  escala_online— a escala deixa de distinguir papel de MTGO: uma «MTGO Challenge
                 64» de 128 jogadores passa a pedir 64 `.dec` de listas que o
                 vault já tem pelo mtgo.com (eram 28 eventos na fila);
  revisitar    — não há forma de FORÇAR a revisita: a recuperação fica à mercê de
                 1 evento por formato e por noite;
  fila_grande  — a fila de revisitas volta a exigir `grande = 1` (o nome): os 4
                 eventos truncados cujo nome nenhum padrão reconhece ficam de fora
                 para sempre;
  d_zero       — o `parse_deck_ids` volta a aceitar `d=0`: a página genérica de um
                 evento que já não existe passa por uma página com uma lista;
  pagina_morta — o crivo da página de evento desaparece: um 200 com a página
                 genérica marca o evento como COMPLETO com uma lista;
  vez_gasta    — o travão das revisitas volta a contar TENTATIVAS: o evento cuja
                 página morreu fica à cabeça da fila todas as noites e os outros
                 nunca são vistos;
  nome_caixa   — o nome da caixa volta a ser o do deck ANTIGO («UW Oswald»)
                 enquanto a lista lá dentro é Izzet Affinity;
  arquetipo    — a caixa deixa de dizer que arquétipo é, e o meta com o mesmo nome
                 volta a aparecer como se fosse um segundo deck;
  desactivada  — a desactivação deixa de se reconhecer: a caixa volta a aparecer
                 como um deck de 0 % ao lado dos que ele vai montar;
  data_consenso— a nota do consenso volta a ser só «consenso de N listas», sem
                 dizer de que dia nem de que janela;
  data_vigia   — a nota da lista vigiada volta a dizer só o dia do snapshot: uma
                 lista conferida hoje parece informação de há um mês;
  amostra      — um consenso sem amostra deixa de o dizer e devolve uma lista
                 vazia calada;
  staples      — as staples do formato deixam de ser calculadas: ele marca os
                 decks e não tem a pilha que vai guardar à parte.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_decklists_no_site as T                            # noqa: E402

from mtgvault import decks_vista, loadout, mtgtop8            # noqa: E402

if alvo == "escala":
    # A regra de 04/10 de manhã: só o ramo do NOME.
    def _so_nome(grande, players, tecto_normal, cfg=None, nome=""):
        r = mtgtop8.regras_grandes(cfg)
        if grande and (players or 0) >= r["min_jogadores"]:
            return max(tecto_normal, r["listas_por_evento"])
        return tecto_normal

    mtgtop8.tecto_do_evento = _so_nome
    mtgtop8.escala_do_tecto = lambda players, nome="", cfg=None: 0
elif alvo == "escala_online":
    # A escala sem o crivo do papel: a primeira versão que escrevi.
    def _sem_crivo(players, nome="", cfg=None):
        p = players or 0
        for corte, tecto in mtgtop8.regras_grandes(cfg)["escala"]:
            if p >= corte:
                return tecto
        return 0

    mtgtop8.escala_do_tecto = _sem_crivo
elif alvo == "revisitar":
    mtgtop8.revisitar = lambda con, fmt=None, eventos=None, limite=None, \
        tecto_normal=16, cfg=None: []
elif alvo == "fila_grande":
    _por_fazer = mtgtop8.por_fazer

    def _so_grandes(con, fmt, tecto_normal, cfg=None):
        out = [dict(r) for r in con.execute(
            "SELECT * FROM mtgtop8_eventos WHERE format = ? AND event_id > 0 "
            "AND grande = 1 AND completo = 0", (fmt,))]
        out = [r for r in out if _por_fazer(r, True, tecto_normal, cfg)]
        out.sort(key=lambda r: -(r.get("players") or 0))
        return out

    mtgtop8.revisitas_pendentes = _so_grandes
elif alvo == "d_zero":
    import re

    def _com_zero(html):
        vistos, out = set(), []
        for m in mtgtop8.RE_DECK.finditer(html):
            did = int(m.group(1))
            if did not in vistos:
                vistos.add(did)
                out.append(did)
        return out

    mtgtop8.parse_deck_ids = _com_zero
    del re
elif alvo == "pagina_morta":
    mtgtop8.e_pagina_de_evento = lambda meta, ids: True
elif alvo == "vez_gasta":
    # O travão a contar TENTATIVAS, como antes: a fila entope na cabeça.
    _abrir = mtgtop8._abrir_evento
    mtgtop8._abrir_evento = lambda *a, **kw: (_abrir(*a, **kw)[0], True)
elif alvo == "nome_caixa":
    _slots = decks_vista.caixas.slots

    def _nome_antigo(cfg=None):
        out = []
        for s in _slots(cfg):
            if s.get("slot") == "modern":
                s = dict(s, nome="Modern — UW Oswald")
            out.append(s)
        return out

    decks_vista.caixas.slots = _nome_antigo
elif alvo == "arquetipo":
    decks_vista._nome_do_consenso = lambda d: ""
elif alvo == "desactivada":
    decks_vista.sem_lista_porque = lambda s: ("", "")
elif alvo == "data_consenso":
    _cfc = loadout._cards_from_consensus

    def _sem_data(con, fmt, assinatura, todas=False, sem=None):
        cards, nota = _cfc(con, fmt, assinatura, todas=todas, sem=sem)
        import re as _re
        return cards, _re.sub(r" de \d{4}-\d{2}-\d{2}.*$", "", nota)

    loadout._cards_from_consensus = _sem_data
elif alvo == "data_vigia":
    _cfw = loadout._cards_from_watched

    def _so_snapshot(con, label):
        cards, nota = _cfw(con, label)
        return cards, nota.split(" — ")[0].split(" (conferida")[0]

    loadout._cards_from_watched = _so_snapshot
elif alvo == "amostra":
    _cfc2 = loadout._cards_from_consensus

    def _calado(con, fmt, assinatura, todas=False, sem=None):
        cards, nota = _cfc2(con, fmt, assinatura, todas=todas, sem=sem)
        return (cards, nota) if cards else ([], "")

    loadout._cards_from_consensus = _calado
elif alvo == "staples":
    decks_vista.staples_do_formato = lambda decks, rep, pos=None: []
else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

getattr(T, caso)()
print(f"PASSOU SEM A FUNCIONALIDADE (alvo={alvo}): {caso}")
