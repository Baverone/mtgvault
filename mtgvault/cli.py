"""Interface de linha de comandos.  Uso:  python -m mtgvault.cli <comando>"""
from __future__ import annotations

import argparse
import json
import sys

from . import (analysis, collection, db, mtgtop8, prices, scryfall, sources, stock,
               wantlist, watchlist)


def _p(rows, cols):
    """Impressão tabular simples."""
    if not rows:
        print("  (nada)")
        return
    w = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  " + "  ".join(c.ljust(w[c]) for c in cols))
    print("  " + "  ".join("-" * w[c] for c in cols))
    for r in rows:
        print("  " + "  ".join(str(r.get(c, "")).ljust(w[c]) for c in cols))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mtgvault", description="Gestor de coleção MTG")
    ap.add_argument("--db", default=None, help="caminho do vault.db")
    ap.add_argument("--catalog", default=None, help="caminho do catalog.db")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="criar a base de dados")
    sub.add_parser("sync-cards", help="atualizar catálogo Scryfall (semanal)")
    sub.add_parser("ensure-catalog", help="construir o catálogo só se estiver vazio")
    sub.add_parser("status", help="estado da base de dados")

    pr = sub.add_parser("prune", help="apagar decklists antigas (mantém a análise)")
    pr.add_argument("--days", type=int, default=180)

    a = sub.add_parser("add", help="adicionar carta à coleção")
    a.add_argument("name")
    a.add_argument("--set", dest="set_code")
    a.add_argument("--cn", dest="collector_number")
    a.add_argument("-q", "--quantity", type=int, default=1)
    a.add_argument("--foil", action="store_true")
    a.add_argument("--lang", default="en")
    a.add_argument("--condition", default="NM")
    a.add_argument("--collector", action="store_true",
                   help="marcar como coleção de colecionador (não joga)")
    a.add_argument("--sub", dest="sub_collection")
    a.add_argument("--photo", dest="photo_path")

    imp = sub.add_parser("import", help="importar coleção de um CSV")
    imp.add_argument("path")

    d = sub.add_parser("deck-add", help="criar deck a partir de ficheiro de texto")
    d.add_argument("name")
    d.add_argument("format")
    d.add_argument("path")

    dr = sub.add_parser("deck-reserve", help="dedicar cartas a um deck")
    dr.add_argument("deck_id", type=int)

    dl = sub.add_parser("deck-release", help="devolver as cartas ao pote comum")
    dl.add_argument("deck_id", type=int)

    sub.add_parser("reservations", help="que cartas estão dedicadas a que deck")

    s = sub.add_parser("deck-status", help="o que tenho e o que falta num deck")
    s.add_argument("deck_id", type=int)

    w = sub.add_parser("wantlist", help="wantlist agregada de todos os decks")
    w.add_argument("--deck", type=int, action="append")

    h = sub.add_parser("harvest", help="recolher decklists do MTGO")
    h.add_argument("--days", type=int, default=1)
    h.add_argument("--format", action="append")

    h8 = sub.add_parser("harvest-mtgtop8", help="recolher decklists do mtgtop8")
    h8.add_argument("format")
    h8.add_argument("--events", type=int, default=8)

    an = sub.add_parser("analyse", help="recalcular arquétipos e core/tech")
    an.add_argument("format")
    an.add_argument("--window", type=int, default=30)

    c = sub.add_parser("cores", help="mostrar o núcleo de um arquétipo")
    c.add_argument("archetype_id", type=int)

    sub.add_parser("archetypes", help="listar arquétipos detetados").add_argument(
        "format", nargs="?")

    g = sub.add_parser("gap", help="o que falta para montar um arquétipo")
    g.add_argument("archetype_id", type=int)
    g.add_argument("--flex", action="store_true")

    cm = sub.add_parser("prices-cardmarket", help="carregar price guide já descarregado")
    cm.add_argument("path")

    ct = sub.add_parser("prices-cardtrader", help="preços via API CardTrader")
    ct.add_argument("sets", nargs="+", help="códigos de edição, ex: mh3 otj")

    sub.add_parser("value", help="valor da coleção")

    m = sub.add_parser("movers", help="o que subiu e desceu")
    m.add_argument("--days", type=int, default=7)


    wp = sub.add_parser("watch-player", help="vigiar um jogador do MTGO")
    wp.add_argument("login"); wp.add_argument("label"); wp.add_argument("format")

    wm = sub.add_parser("watch-moxfield", help="vigiar um deck do Moxfield")
    wm.add_argument("url"); wm.add_argument("label"); wm.add_argument("format")

    sub.add_parser("watch-list", help="listar baralhos vigiados")

    wc = sub.add_parser("watch-check", help="ver se há atualizações")
    wc.add_argument("--id", type=int)

    wd = sub.add_parser("watch-diff", help="o que mudou na última versão")
    wd.add_argument("id", type=int)

    wpa = sub.add_parser("watch-paste", help="atualizar um vigiado a partir de texto")
    wpa.add_argument("id", type=int); wpa.add_argument("path")

    wcov = sub.add_parser("watch-coverage", help="quanto tenho de um vigiado")
    wcov.add_argument("id", type=int)

    stk = sub.add_parser("stock", help="lista padrão de um arquétipo")
    stk.add_argument("archetype_id", type=int)
    stk.add_argument("--coverage", action="store_true")

    rep = sub.add_parser("report", help="%% que tenho de cada arquétipo do formato")
    rep.add_argument("format")
    rep.add_argument("--min-lists", type=int, default=5)

    args = ap.parse_args(argv)

    with db.session(args.db, args.catalog) as con:
        if args.cmd == "init":
            print("Base de dados pronta.")

        elif args.cmd == "sync-cards":
            print(f"{scryfall.sync(con):,} impressões no catálogo.")

        elif args.cmd == "ensure-catalog":
            n = db.catalog_size(con)
            if n < 1000:
                print(f"Catálogo vazio ({n}). A construir...")
                print(f"{scryfall.sync(con):,} impressões.")
            else:
                print(f"Catálogo já tem {n:,} impressões — nada a fazer.")

        elif args.cmd == "status":
            q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
            print(f"| métrica | valor |\n|---|---|")
            print(f"| catálogo | {db.catalog_size(con):,} impressões |")
            print(f"| exemplares | {q('SELECT COALESCE(SUM(quantity),0) FROM copies'):,} |")
            print(f"| decklists | {q('SELECT COUNT(*) FROM decklists'):,} |")
            print(f"| arquétipos | {q('SELECT COUNT(*) FROM archetypes'):,} |")
            print(f"| preços (histórico) | {q('SELECT COUNT(*) FROM price_history'):,} |")
            print(f"| vigiados | {q('SELECT COUNT(*) FROM watched WHERE active=1'):,} |")
            falhas = [dict(r) for r in con.execute(
                "SELECT job, detail FROM job_runs WHERE status != 'ok' "
                "AND started > datetime('now','-2 days')")]
            for f in falhas:
                print(f"| FALHA | {f['job']} |")

        elif args.cmd == "prune":
            print(f"{analysis.prune_decklists(con, args.days):,} decklists apagadas.")

        elif args.cmd == "add":
            rid = collection.add_copy(
                con, args.name, set_code=args.set_code,
                collector_number=args.collector_number, quantity=args.quantity,
                finish="foil" if args.foil else "nonfoil", language=args.lang,
                condition=args.condition,
                purpose="collector" if args.collector else "player",
                sub_collection=args.sub_collection, photo_path=args.photo_path)
            print(f"Adicionado (id {rid}).")

        elif args.cmd == "import":
            ok, errs = collection.import_csv(con, args.path)
            print(f"{ok} linhas importadas.")
            for e in errs[:20]:
                print("  !", e)
            if len(errs) > 20:
                print(f"  ... e mais {len(errs) - 20} erros")

        elif args.cmd == "deck-add":
            text = open(args.path, encoding="utf-8").read()
            parsed = sources.parse_text_decklist(text)
            cur = con.execute(
                "INSERT OR IGNORE INTO decks (name, format) VALUES (?,?)",
                (args.name, args.format.lower()))
            did = cur.lastrowid or con.execute(
                "SELECT id FROM decks WHERE name = ? AND format = ?",
                (args.name, args.format.lower())).fetchone()["id"]
            rows = []
            for board in ("main", "side"):
                for name, qty in parsed[board]:
                    rows.append((did, scryfall.resolve_name(con, name) or name,
                                 qty, board))
            con.executemany(
                "INSERT OR REPLACE INTO deck_cards (deck_id, card_name, quantity, "
                "board) VALUES (?,?,?,?)", rows)
            con.commit()
            print(f"Deck {args.name} guardado (id {did}), {len(rows)} entradas.")

        elif args.cmd == "deck-reserve":
            res = collection.reserve_for_deck(con, args.deck_id)
            n = sum(res["reserved"].values())
            print(f"{n} cartas dedicadas a este deck.")
            if res["still_missing"]:
                print("\n  Ainda em falta (não dá para reservar o que não tens):")
                for name, q in sorted(res["still_missing"].items()):
                    print(f"    {q}x {name}")

        elif args.cmd == "deck-release":
            print(f"{collection.release_deck(con, args.deck_id)} lotes libertados.")

        elif args.cmd == "reservations":
            _p(collection.reservations(con), ["deck_id", "deck", "card_name",
                                              "quantity"])

        elif args.cmd == "deck-status":
            st = wantlist.deck_status(con, args.deck_id)
            print(f"\n{st['deck']['name']} ({st['deck']['format']})")
            print(f"Tenho: {len(st['have'])} entradas completas")
            print(f"Faltam: {st['missing_cards']} cartas  ~{st['missing_cost']:.2f} EUR\n")
            _p(st["missing"], ["card_name", "board", "need", "have", "missing",
                               "unit_price", "cost"])

        elif args.cmd == "wantlist":
            rows = wantlist.wantlist(con, args.deck)
            _p(rows, ["card_name", "quantity", "unit_price", "cost"])
            print(f"\n  Total: {sum(r['cost'] for r in rows):.2f} EUR")

        elif args.cmd == "harvest":
            n = sources.harvest_mtgo(con, args.days,
                                     set(args.format) if args.format else None)
            print(f"{n} decklists novas.")

        elif args.cmd == "harvest-mtgtop8":
            n = mtgtop8.harvest(con, args.format, args.events)
            print(f"{n} decklists novas de {args.format}.")

        elif args.cmd == "analyse":
            k = analysis.rebuild_archetypes(con, args.format.lower(), args.window)
            n = analysis.rebuild_roles(con, args.format.lower(), args.window)
            print(f"{k} arquétipos, {n} cartas classificadas.")

        elif args.cmd == "archetypes":
            q = "SELECT a.id, a.format, a.label, COUNT(d.id) AS lists FROM archetypes a "
            q += "LEFT JOIN decklists d ON d.archetype_id = a.id "
            q += ("WHERE a.format = ? " if args.format else "")
            q += "GROUP BY a.id ORDER BY lists DESC"
            rows = [dict(r) for r in con.execute(
                q, (args.format.lower(),) if args.format else ())]
            _p(rows, ["id", "format", "label", "lists"])

        elif args.cmd == "cores":
            rows = [dict(r) for r in con.execute(
                """SELECT card_name, board, role, core_copies, flex_copies,
                          inclusion_rate, avg_copies, dist
                     FROM card_roles WHERE archetype_id = ?
                      AND window_end = (SELECT MAX(window_end) FROM card_roles
                                         WHERE archetype_id = ?)
                    ORDER BY board, core_copies DESC, inclusion_rate DESC""",
                (args.archetype_id, args.archetype_id))]
            _p(rows, ["card_name", "board", "role", "core_copies", "flex_copies",
                      "inclusion_rate", "dist"])

        elif args.cmd == "gap":
            rows = wantlist.archetype_gap(con, args.archetype_id, args.flex)
            _p(rows, ["card_name", "board", "role", "need", "have", "missing",
                      "unit_price", "cost"])
            print(f"\n  Total: {sum(r['cost'] or 0 for r in rows):.2f} EUR")

        elif args.cmd == "prices-cardmarket":
            print(f"{prices.load_cardmarket_file(con, args.path):,} preços gravados.")

        elif args.cmd == "prices-cardtrader":
            ct = prices.CardTrader()
            prices.sync_cardtrader_map(con, ct, args.sets)
            print(f"{prices.fetch_cardtrader_prices(con, ct, args.sets):,} preços.")

        elif args.cmd == "value":
            rows = collection.collection_value(con)
            player = sum(r["total"] for r in rows if r["purpose"] == "player")
            coll = sum(r["total"] for r in rows if r["purpose"] == "collector")
            print(f"  Jogar:       {player:10,.2f} EUR")
            print(f"  Colecionador:{coll:10,.2f} EUR")
            print(f"  TOTAL:       {player + coll:10,.2f} EUR")
            sem = [r for r in rows if not r["unit_price"]]
            if sem:
                print(f"\n  ({len(sem)} lotes sem preço conhecido)")

        elif args.cmd == "movers":
            mv = collection.movers(con, args.days)
            print("\n  A SUBIR")
            _p(mv["up"], ["name", "set_code", "finish", "before", "after", "pct"])
            print("\n  A DESCER")
            _p(mv["down"], ["name", "set_code", "finish", "before", "after", "pct"])

        elif args.cmd == "watch-player":
            wid = watchlist.add(con, "mtgo_player", args.login, args.label,
                                args.format)
            print(f"A vigiar {args.login} em {args.format} (id {wid}).")

        elif args.cmd == "watch-moxfield":
            from . import moxfield
            wid = watchlist.add(con, "moxfield", moxfield.deck_id(args.url),
                                args.label, args.format)
            print(f"A vigiar deck Moxfield (id {wid}).")

        elif args.cmd == "watch-list":
            rows = [dict(r) for r in con.execute(
                "SELECT id, kind, key, label, format, last_checked, last_hash "
                "FROM watched WHERE active = 1 ORDER BY id")]
            _p(rows, ["id", "kind", "key", "label", "format", "last_checked"])

        elif args.cmd == "watch-check":
            if args.id:
                w = con.execute("SELECT kind FROM watched WHERE id = ?",
                                (args.id,)).fetchone()
                res = [watchlist.check_moxfield(con, args.id)
                       if w["kind"] == "moxfield"
                       else watchlist.check_mtgo_player(con, args.id)]
            else:
                res = watchlist.check_all(con)
            for r in res:
                lbl = r["watched"]["label"]
                if r.get("error"):
                    print(f"  [erro]  {lbl}: {r['error']}")
                elif not r.get("found"):
                    print(f"  [--]    {lbl}: sem listas ainda")
                elif r["changed"]:
                    print(f"  [MUDOU] {lbl}  ({r.get('date') or r.get('updated_at')})")
                else:
                    print(f"  [igual] {lbl}")

        elif args.cmd == "watch-diff":
            d = watchlist.diff(con, args.id)
            if d.get("note"):
                print(" ", d["note"])
            else:
                print(f"\n  {d['from']}  ->  {d['to']}")
                _p(d["changes"], ["board", "card_name", "before", "after", "delta"])

        elif args.cmd == "watch-paste":
            text = open(args.path, encoding="utf-8").read()
            parsed = sources.parse_text_decklist(text)
            cards = [(b, scryfall.resolve_name(con, n) or n, q)
                     for b in ("main", "side") for n, q in parsed[b]]
            changed = watchlist._save_snapshot(con, args.id, cards, "manual")
            print("Lista atualizada." if changed else "Lista igual à anterior.")

        elif args.cmd == "watch-coverage":
            cards = watchlist.latest_cards(con, args.id)
            if not cards:
                print("  Ainda não há lista guardada. Corre watch-check primeiro.")
            else:
                cov = stock.coverage(con, cards)
                w = con.execute("SELECT label FROM watched WHERE id = ?",
                                (args.id,)).fetchone()
                print(f"\n  {w['label']}: tenho {cov['cards_have']}/"
                      f"{cov['cards_needed']} cartas  ({cov['pct']}%)")
                print(f"  Faltam {cov['cards_missing']}  ~{cov['cost']:.2f} EUR\n")
                _p(cov["missing"], ["board", "card_name", "need", "have",
                                    "missing", "unit_price", "cost"])

        elif args.cmd == "stock":
            sl = stock.stock_list(con, args.archetype_id)
            print(f"\n  {sl['archetype']['label']} ({sl['archetype']['format']})")
            print(f"\n  MAIN ({sl.get('main_count', 0)}/{sl.get('main_target', 0)})")
            _p(sl["main"], ["quantity", "card_name"])
            if sl["side"]:
                print(f"\n  SIDE ({sl.get('side_count', 0)}/{sl.get('side_target', 0)})")
                _p(sl["side"], ["quantity", "card_name"])
            if args.coverage:
                cov = stock.coverage_of_archetype(con, args.archetype_id)
                print(f"\n  Tenho {cov['cards_have']}/{cov['cards_needed']} "
                      f"({cov['pct']}%)  |  faltam {cov['cards_missing']} "
                      f"~{cov['cost']:.2f} EUR\n")
                _p(cov["missing"], ["board", "card_name", "need", "have",
                                    "missing", "unit_price", "cost"])

        elif args.cmd == "report":
            rows = stock.format_report(con, args.format, args.min_lists)
            _p(rows, ["archetype_id", "label", "n_lists", "pct", "have",
                      "missing", "cost"])


if __name__ == "__main__":
    sys.exit(main())
