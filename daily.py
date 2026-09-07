"""Trabalho diário do mtgvault: recolha, preços, vigiados, análise e limpeza.

Cada passo é independente e fica registado em `job_runs` — se um falhar, os
outros continuam e o erro fica gravado, para o resumo do dia o mostrar. É
preferível ficar sem uma peça do que perder o resto da recolha.

Corre à mão com `python daily.py`, ou agenda-o (Agendador de Tarefas do Windows
ou GitHub Actions). As bases de dados assumem-se em ./data ao lado deste ficheiro;
o GitHub Actions sobrepõe com MTGVAULT_DB / MTGVAULT_CATALOG.

O catálogo reconstrói-se sozinho se estiver vazio — é o caso na cloud, onde o
catalog.db não é versionado por ser grande de mais — a partir do mesmo bulk da
Scryfall que também alimenta os preços grátis. Assim a cloud deixa de precisar
de um PC ligado para refrescar preços.
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

from mtgvault import (analysis, db, mtgtop8, prices, scryfall, sources,  # noqa: E402
                      tagging, watchlist)

import core_decks  # noqa: E402  (gera coredecks.html + tracking de alteracoes)
import collection_gallery  # noqa: E402  (gera colecao.html — galeria com imagens)
import colecao_cor  # noqa: E402  (gera colecao_cor.html — coleção por cor + custo de mana)
import meta_coverage  # noqa: E402  (gera cobertura.html — top decks + % que tenho + o que falta)
import meusdecks  # noqa: E402  (gera meusdecks.html — os meus decks: estado, % e evolução)
import deckboxes  # noqa: E402  (gera deckboxes.html — o loadout: decks montados em simultâneo + venda)
import metagame  # noqa: E402  (gera metagame.html — só ver o metagame: listas com arte)
import decks_faziveis  # noqa: E402  (gera decksfaziveis.html — decks do top-10 que já dá para montar)
import reservedlist  # noqa: E402  (gera reservedlist.html — Reserved List x coleção)
import caixarl  # noqa: E402  (gera caixarl.html — Caixa Reserved List: RL fora da coleção jogável)
import showcase  # noqa: E402  (gera showcase.html — Decks Showcase Challenger, arquétipos por formato)
import my_decks  # noqa: E402  (mantém atualizadas as listas dos decks que o André segue)
import commander_decks  # noqa: E402  (decks de comandante seguidos por consenso, ex.: Cloud DC)
import premodern_decks  # noqa: E402  (consenso dos arquétipos-alvo de Premodern: UW Replenish, Enchantress)
import refresh_collection  # noqa: E402  (reconstroi collection_owned p/ o index.html)

MTGO_DAYS = 3
# O mtgo cobre a maioria; o mtgtop8 acrescenta o papel e é a única fonte de cEDH.
MTGTOP8_FORMATS = ["duel-commander", "premodern"]  # cEDH saiu (Andre, 2026-09-07): os decks dele seguem links directos
# Torneios PRESENCIAIS (mtgtop8) para os formatos que o MTGO já cobre — para a
# página Showcase Challenger juntar o papel ao online (ex.: Magic Spotlight, ANZMTG
# Super Series). Os re-hosts de MTGO são deduplicados; ficam os presenciais, com
# placement pela posição.
MTGTOP8_PAPER = ["standard", "pioneer", "modern", "legacy"]
# Clustering + core/flex. Fora (André, 2026-09-07): o PAUPER, que já não tem
# metagame nenhum (só a lista do Luffy, ver sources.so_jogadores_vigiados), e o
# DUEL COMMANDER, onde só interessa o consenso do Cloud — esse sai de
# `commander_decks.tiers`, que lê as decklists directamente e nunca precisou dos
# `archetypes`/`card_roles` do formato. O PREMODERN FICA: já não tem página de
# metagame, mas o consenso do UW Replenish e da Enchantress precisa das listas.
ANALYSE_FORMATS = ["standard", "pioneer", "modern", "legacy", "vintage",
                   "premodern"]


def _step(con, nome, fn):
    """Corre um passo, regista o resultado, e nunca deixa rebentar o resto."""
    try:
        detalhe = fn()
        db.log_job(con, nome, "ok", str(detalhe or ""))
        print(f"[ok]   {nome}: {detalhe if detalhe is not None else ''}")
    except Exception as e:  # noqa: BLE001
        db.log_job(con, nome, "erro", repr(e))
        print(f"[ERRO] {nome}: {e}")


# O bulk da Scryfall (~77 MB) alimenta DOIS passos — reconstruir o catálogo e os
# preços grátis. Descarrega-se uma só vez por execução e reutiliza-se.
_BULK: dict = {}


def _bulk():
    if "path" not in _BULK:
        _BULK["path"] = scryfall.download_bulk()
    return _BULK["path"]


def _catalog(con):
    """Garante o catálogo. Na cloud o catalog.db não vem no clone (grande de mais
    para o Git), por isso reconstrói-se a cada execução. No PC local, se já
    estiver cheio, salta — o `sync-cards` semanal é que o atualiza."""
    if db.catalog_size(con) >= 1000:
        # Já existe. Mas um catálogo antigo em cache pode não ter a metadata nova
        # (reserved/set_type) — nesse caso repovoa uma vez a partir do bulk.
        if not scryfall.has_card_meta(con):
            return f"metadata em falta — repovoado ({scryfall.load_bulk(con, _bulk()):,})"
        return "já existe — saltado"
    return f"{scryfall.load_bulk(con, _bulk()):,} impressões"


def _scryfall_prices(con):
    """Preço-base grátis, tirado do próprio bulk da Scryfall: o campo `prices.eur`
    de cada impressão É o valor do Cardmarket (a Scryfall vai lá buscá-lo). Sem
    cookie nem token — é a fonte que a cloud consegue sempre. Corre ANTES do price
    guide oficial, para que os dados mais ricos (low/trend/avg30) se sobreponham
    quando há cookie."""
    return f"{prices.load_scryfall_prices(con, _bulk())} preços"


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


def _prune_prices(con, keep_days: int = 30):
    """Apaga histórico de preços antigo. Só interessa o recente — a Reserved List
    compara 'hoje vs há ~1 mês'. Sem isto o price_history cresce sem fim e é o que
    mais faz o vault.db aproximar-se do limite de 100 MB do GitHub."""
    n = con.execute("DELETE FROM price_history WHERE date < date('now', ?)",
                    (f"-{keep_days} days",)).rowcount
    con.commit()
    return f"{n} preços >{keep_days}d apagados"


def _podar_ligas(con):
    """Apaga as listas de liga dos formatos onde as ligas não contam.

    Decisão do André (2026-09-07): "no mtgvault não quero listas de league",
    menos no Duel Commander. A recolha já não as guarda; isto limpa o passado —
    eram cerca de um terço do vault.db sem alimentarem uma única página.

    Faz UM backup antes da primeira poda (data/backups/vault-antes-filtro-*.db)
    e nunca mais: é uma rede de segurança para a passagem, não um backup diário
    (que só faria o disco crescer com cópias de 100 MB).
    """
    backups = ROOT / "data" / "backups"
    guardado = ""
    if not list(backups.glob("vault-antes-filtro-*.db")):
        from datetime import date as _date
        backups.mkdir(parents=True, exist_ok=True)
        alvo = backups / f"vault-antes-filtro-{_date.today().isoformat()}.db"
        # VACUUM INTO em vez de copiar o ficheiro: dá uma cópia consistente do
        # `main` com a ligação aberta (e sem levar o catálogo anexado atrás).
        con.execute("VACUUM main INTO ?", (str(alvo),))
        guardado = f" (backup em {alvo.name})"
    return f"{analysis.prune_leagues(con)} listas de liga apagadas{guardado}"


def main():
    with db.session() as con:
        # O catálogo primeiro: os preços e a resolução de nomes dependem dele, e
        # na cloud ele não vem no clone.
        _step(con, "catalogo", lambda: _catalog(con))

        _step(con, "harvest-mtgo",
              lambda: f"{sources.harvest_mtgo(con, MTGO_DAYS)} novas")
        for fmt in MTGTOP8_FORMATS:
            _step(con, f"harvest-mtgtop8:{fmt}",
                  lambda fmt=fmt: f"{mtgtop8.harvest(con, fmt, max_events=8)} novas")
        for fmt in MTGTOP8_PAPER:
            _step(con, f"harvest-papel:{fmt}",
                  lambda fmt=fmt: f"{mtgtop8.harvest(con, fmt, max_events=6)} novas")

        # Classifica os eventos por importância (Showcase/Challenge/League/...).
        # Tem de correr DEPOIS da recolha: é esta coluna que decide que listas
        # contam. Enquanto ninguém a escrevia, o top-10 vinha vazio e o passo da
        # cobertura dizia na mesma "ok". É idempotente sobre TODAS as listas, não
        # só as que estão a NULL — quando a regra de classificação muda (2026-09-07,
        # re-hosts do MTGO a saírem de Presencial), as antigas acertam-se sozinhas.
        _step(con, "tier-eventos",
              lambda: f"{sources.backfill_event_tiers(con)} listas reclassificadas")

        # Nº de jogadores dos presenciais do mtgtop8. Sem ele um presencial não
        # conta (a regra pede 64+), e dois terços das listas estavam a NULL.
        # Poucos eventos por corrida e a 1 pedido/s — o mtgtop8 é pequeno.
        _step(con, "jogadores-eventos",
              lambda: mtgtop8.backfill_event_players(con, max_events=40))

        # Preços — cada fonte é opcional e salta em silêncio se não estiver
        # configurada. O bulk da Scryfall é a base grátis; Cardmarket e CardTrader
        # enriquecem quando há credenciais.
        _step(con, "precos-scryfall", lambda: _scryfall_prices(con))
        _step(con, "precos-cardmarket", lambda: _cardmarket(con))
        _step(con, "precos-cardtrader", lambda: _cardtrader(con))

        # O que interessa para a vigilância dos decks (Moxfield, jogadores MTGO).
        _step(con, "watch-check", lambda: _watch(con))

        for fmt in ANALYSE_FORMATS:
            _step(con, f"analyse:{fmt}", lambda fmt=fmt: _analyse(con, fmt))

        # O card_roles acumula uma janela nova por dia, mas só a mais recente é
        # usada. Podar as antigas mantém o vault.db leve (senão passa dos 100 MB
        # do GitHub). Sem VACUUM diário — o SQLite reutiliza as páginas livres.
        _step(con, "podar-card-roles",
              lambda: f"{con.execute('DELETE FROM card_roles WHERE window_end < (SELECT MAX(window_end) FROM card_roles)').rowcount} linhas antigas")

        # Arquétipos por regra (etiqueta dupla) — reaplicados DEPOIS do analyse
        # para o clustering automático nunca desfazer os nomes à mão.
        _step(con, "tag-arquetipos", lambda: f"{tagging.tag_all(con)} etiquetas")

        # Mantém as listas dos decks seguidos (os principais de Modern do André)
        # coladas à versão mais recente do metagame, para a % e a wantlist estarem
        # sempre atualizadas.
        _step(con, "meus-decks", lambda: my_decks.refresh(con))
        # Decks de comandante seguidos por consenso (ex.: Cloud, Midgar Mercenary
        # em Duel Commander). Reconstrói a lista de referência do metagame.
        _step(con, "decks-comandante", lambda: commander_decks.refresh(con))
        # Consenso dos arquétipos-alvo de Premodern (UW Replenish, Enchantress).
        # DEPOIS do `tag-arquetipos`: é das etiquetas dele que saem as listas de
        # cada arquétipo (o clustering não os separa — a Enchantress joga 96% de
        # Replenish e vinham colados).
        _step(con, "decks-premodern", lambda: premodern_decks.refresh(con))

        # Core decks: recalcula o consenso dos decks que sigo e regista se o
        # padrão mudou (core_snapshots). Corre DEPOIS de preços + tags.
        _step(con, "core-decks",
              lambda: str(core_decks.build(con, ROOT / "coredecks.html")))
        # Posse do site (collection_owned p/ o index.html) — depois do core-decks,
        # que atualiza o card_price de que a posse se serve.
        _step(con, "posse-site", lambda: refresh_collection.refresh(con))
        _step(con, "galeria-colecao",
              lambda: str(collection_gallery.build(con, ROOT / "colecao.html")))
        _step(con, "colecao-cor",
              lambda: str(colecao_cor.build(con, ROOT / "colecao_cor.html")))
        # Cobertura do metagame: top decks por formato, % que já tenho e o que falta.
        # Depois da análise (arquétipos/roles) e dos preços — depende dos dois.
        _step(con, "cobertura-metagame",
              lambda: str(meta_coverage.build(con, ROOT / "cobertura.html")[0]))
        _step(con, "meus-decks-pagina",
              lambda: str(meusdecks.build(con, ROOT / "meusdecks.html")))
        # Deckboxes: o loadout (os decks montados ao mesmo tempo) com a coleção
        # REPARTIDA entre eles, mais a lista de venda. Depois do `meus-decks` e
        # dos `decks-premodern`: lê as mesmas listas (decks/watched/consenso) e
        # precisa delas já atualizadas.
        _step(con, "deckboxes",
              lambda: str(deckboxes.build(con, ROOT / "deckboxes.html")))
        _step(con, "metagame-pagina",
              lambda: str(metagame.build(con, ROOT / "metagame.html")))
        _step(con, "decks-faziveis-pagina",
              lambda: str(decks_faziveis.build(con, ROOT / "decksfaziveis.html")))
        _step(con, "reserved-list-pagina",
              lambda: str(reservedlist.build(con, ROOT / "reservedlist.html")))
        _step(con, "caixa-reserved-list",
              lambda: str(caixarl.build(con, ROOT / "caixarl.html")))
        _step(con, "showcase-challenger",
              lambda: str(showcase.build(con, ROOT / "showcase.html")))

        _step(con, "podar-precos", lambda: _prune_prices(con, 30))
        # Ligas fora (2026-09-07). ANTES do `prune`, que é quem faz o VACUUM.
        _step(con, "podar-ligas", lambda: _podar_ligas(con))
        _step(con, "prune", lambda: f"{analysis.prune_decklists(con, 30)} apagadas")


if __name__ == "__main__":
    main()
