"""Trabalho diário do mtgvault: recolha, preços, vigiados, análise e limpeza.

Cada passo é independente e fica registado em `job_runs` — se um falhar, os
outros continuam e o erro fica gravado, para o resumo do dia o mostrar. É
preferível ficar sem uma peça do que perder o resto da recolha.

Corre à mão com `python daily.py`, ou agenda-o (Agendador de Tarefas do Windows
ou GitHub Actions). As bases de dados assumem-se em ./data ao lado deste ficheiro;
o GitHub Actions sobrepõe com MTGVAULT_DB / MTGVAULT_CATALOG.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# Por omissão, as BDs vivem em ./data ao lado do script. O ambiente ganha sempre
# (o workflow do GitHub define MTGVAULT_DB/MTGVAULT_CATALOG).
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))
# A API do Moxfield responde a um User-Agent honesto. Se um dia o suporte te der
# um UA autorizado, define MOXFIELD_USER_AGENT no ambiente e este default cede.
os.environ.setdefault("MOXFIELD_USER_AGENT", "mtgvault/0.1 (coleccao pessoal)")

from mtgvault import analysis, db, mtgtop8, prices, sources, tagging, watchlist  # noqa: E402

MTGO_DAYS = 3
# O mtgo cobre a maioria; o mtgtop8 acrescenta o papel e é a única fonte de cEDH.
MTGTOP8_FORMATS = ["duel-commander", "premodern", "cedh"]
ANALYSE_FORMATS = ["standard", "pioneer", "modern", "legacy", "vintage", "pauper",
                   "duel-commander", "premodern", "cedh"]


def _step(con, nome, fn):
    """Corre um passo, regista o resultado, e nunca deixa rebentar o resto."""
    try:
        detalhe = fn()
        db.log_job(con, nome, "ok", str(detalhe or ""))
        print(f"[ok]   {nome}: {detalhe if detalhe is not None else ''}")
    except Exception as e:  # noqa: BLE001
        db.log_job(con, nome, "erro", repr(e))
        print(f"[ERRO] {nome}: {e}")


def _cardmarket(con):
    caminho = os.environ.get("CARDMARKET_PRICEGUIDE")
    if not caminho:
        p = prices.download_cardmarket_priceguide()   # usa o cookie, se existir
        if not p:
            return "sem ficheiro nem cookie — saltado"
        caminho = str(p)
    return f"{prices.load_cardmarket_file(con, caminho)} preços"


def _cardtrader(con):
    if not os.environ.get("CARDTRADER_TOKEN"):
        return "sem token — saltado"
    sets = [s.strip() for s in os.environ.get("CARDTRADER_SETS", "").split(",") if s.strip()]
    if not sets:
        return "sem CARDTRADER_SETS — saltado"
    ct = prices.CardTrader()
    prices.sync_cardtrader_map(con, ct, sets)
    return f"{prices.fetch_cardtrader_prices(con, ct, sets)} preços"


def _watch(con):
    """Verifica os vigiados e, quando algo muda, imprime o que entrou e saiu."""
    res = watchlist.check_all(con)
    for r in res:
        w = r["watched"]
        lbl = w["label"]
        if r.get("error"):
            print(f"    [erro]  {lbl}: {r['error']}")
        elif not r.get("found"):
            print(f"    [--]    {lbl}: sem listas ainda")
        elif r["changed"]:
            print(f"    [MUDOU] {lbl}")
            d = watchlist.diff(con, w["id"])
            if d.get("note"):
                print(f"            ({d['note']})")
            else:
                print(f"            {d['from']} -> {d['to']}")
                for c in d["changes"]:
                    print(f"            {c['board']:4} {c['delta']:+d}  {c['card_name']} "
                          f"({c['before']}->{c['after']})")
        else:
            print(f"    [igual] {lbl}")
    return f"{len(res)} vigiados"


def _analyse(con, fmt):
    k = analysis.rebuild_archetypes(con, fmt)
    n = analysis.rebuild_roles(con, fmt)
    return f"{k} arquétipos, {n} cartas"


def main():
    with db.session() as con:
        _step(con, "harvest-mtgo",
              lambda: f"{sources.harvest_mtgo(con, MTGO_DAYS)} novas")
        for fmt in MTGTOP8_FORMATS:
            _step(con, f"harvest-mtgtop8:{fmt}",
                  lambda fmt=fmt: f"{mtgtop8.harvest(con, fmt, max_events=8)} novas")

        # Preços — cada fonte é opcional e salta em silêncio se não estiver configurada.
        _step(con, "precos-cardmarket", lambda: _cardmarket(con))
        _step(con, "precos-cardtrader", lambda: _cardtrader(con))

        # O que interessa para a vigilância dos decks (Moxfield, jogadores MTGO).
        _step(con, "watch-check", lambda: _watch(con))

        for fmt in ANALYSE_FORMATS:
            _step(con, f"analyse:{fmt}", lambda fmt=fmt: _analyse(con, fmt))

        # Arquétipos por regra (etiqueta dupla) — reaplicados DEPOIS do analyse
        # para o clustering automático nunca desfazer os nomes à mão.
        _step(con, "tag-arquetipos", lambda: f"{tagging.tag_all(con)} etiquetas")

        _step(con, "prune", lambda: f"{analysis.prune_decklists(con, 180)} apagadas")


if __name__ == "__main__":
    main()
