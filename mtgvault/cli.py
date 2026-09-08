"""Interface de linha de comandos.  Uso:  python -m mtgvault.cli <comando>"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (analysis, caixas, collection, db, loadout, mtgtop8, prices,
               scryfall, sources, stock, wantlist, watchlist)


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
    imp.add_argument("--resultado", help="CSV com o que aconteceu a cada linha")
    imp.add_argument("--arrumar-fotos", action="store_true",
                     help="mover as fotos deste lote para 'fotos processadas/<AAAA-MM>' "
                          "e ligar cada foto à cópia que criou")
    imp.add_argument("--adivinhar", action="store_true",
                     help="aceitar a impressão mais recente/barata quando a linha "
                          "não traz edição (fica dito na notes da cópia)")

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

    lo = sub.add_parser("loadout",
                        help="os decks montados em deckbox: estado, o que comprar "
                             "e o que ir buscar a outra caixa")
    lo.add_argument("deck", nargs="?", help="nome (ou parte) de um slot, para o detalhe")

    vd = sub.add_parser("vender", help="o que sobra depois de montar o loadout")
    vd.add_argument("--csv", action="store_true", help="saída em CSV")
    vd.add_argument("--tudo", action="store_true",
                    help="incluir Reserved List, substitutos e retidos")

    ar = sub.add_parser("arrumar",
                        help="o que mover de cada gaveta para cada deckbox")
    ar.add_argument("--csv", action="store_true", help="saída em CSV (moves)")
    ar.add_argument("--confirmar", action="store_true",
                    help='"já arrumei tudo": grava a alocação como a arrumação real')

    pm = sub.add_parser("premodern",
                        help="Premodern: o que montar a seguir com o que sobra")
    pm.add_argument("accao", nargs="?", default="sugestoes",
                    choices=["sugestoes"],
                    help="sugestoes = o ranking, a cobertura e o que vai a vender")
    pm.add_argument("--tudo", action="store_true",
                    help="mostrar todos os arquétipos, não só o top-10 e o top-5 combo")

    mc = sub.add_parser("migrar-caixas",
                        help="colecao_config.json: `loadout` -> `caixas` (v6)")
    mc.add_argument("--dry-run", action="store_true",
                    help="só diz o que faria; não escreve nada")

    ma = sub.add_parser("migrar-arquetipos",
                        help="recusas/escolhas por NOME -> por `id` estável")
    ma.add_argument("--dry-run", action="store_true",
                    help="só diz o que faria; não escreve nada")

    mig = sub.add_parser("migrar-coleccao-unica",
                         help="funde os baldes na `Colecção` (a RL fica de fora)")
    mig.add_argument("--dry-run", action="store_true",
                     help="só diz o que faria; não escreve nada")
    mig.add_argument("--sem-backup", action="store_true",
                     help="não fazer a cópia de segurança (não recomendado)")

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
            resultados: list[dict] = []
            ok, errs = collection.import_csv(
                con, args.path, adivinhar=args.adivinhar, resultados=resultados)
            print(f"{ok} linhas importadas.")
            for e in errs[:20]:
                print("  !", e)
            if len(errs) > 20:
                print(f"  ... e mais {len(errs) - 20} erros")
            if args.arrumar_fotos:
                f = collection.arrumar_fotos(con, resultados)
                print(f"{f['movidas']} fotos para 'pendentes/{f['destino']}', "
                      f"{f['ligadas']} ligações foto↔cópia registadas.")
                if f["ficaram"]:
                    print("  fotos que ficam em pendentes/ (têm linhas por "
                          "resolver): " + ", ".join(f["ficaram"][:10]))
            if args.resultado:
                print("resultado:", collection.gravar_resultado(resultados,
                                                                args.resultado))

        elif args.cmd == "deck-add":
            text = open(args.path, encoding="utf-8").read()
            parsed = sources.parse_text_decklist(text)
            cur = con.execute(
                "INSERT OR IGNORE INTO decks (name, format) VALUES (?,?)",
                (args.name, args.format.lower()))
            # Quando o INSERT é IGNORADO (deck já existe), o lastrowid NÃO fica a
            # zero: o SQLite devolve o rowid do último insert bem sucedido da
            # LIGAÇÃO, que pode ser de outra tabela ou de outro deck. Confiar
            # nele metia as cartas no deck errado. O rowcount é que diz se houve
            # mesmo inserção.
            did = cur.lastrowid if cur.rowcount else con.execute(
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

        elif args.cmd == "loadout":
            rep = loadout.report(con)
            if args.deck:
                _loadout_detalhe(rep, args.deck)
            else:
                _loadout_resumo(rep)

        elif args.cmd == "vender":
            _vender(loadout.report(con), csv_out=args.csv, tudo=args.tudo)

        elif args.cmd == "arrumar":
            _arrumar(con, csv_out=args.csv, confirmar=args.confirmar)

        elif args.cmd == "premodern":
            _premodern(loadout.report(con), tudo=args.tudo)

        elif args.cmd == "migrar-arquetipos":
            _migrar_arquetipos(con, dry_run=args.dry_run)

        elif args.cmd == "migrar-coleccao-unica":
            _migrar(con, dry_run=args.dry_run, com_backup=not args.sem_backup)

        elif args.cmd == "migrar-caixas":
            r = caixas.migrar_ficheiro(dry_run=args.dry_run)
            if not r["mudou"]:
                print(f"{r['path']}: já está no formato `caixas` (v6) — nada a fazer")
            elif args.dry_run:
                print(f"{r['path']}: {r['caixas']} caixas a converter (dry-run)")
            else:
                print(f"{r['path']}: {r['caixas']} caixas escritas "
                      f"(backup em {Path(r['backup']).name})")


def _loadout_resumo(rep):
    print("DECKS EM DECKBOX (uma caixa = um deck)\n")
    linhas = []
    for s in rep["slots"]:
        estado = ("deck por escolher" if s["vazio"] else s.get("estado"))
        linhas.append({"slot": s["nome"], "formato": s["formato"], "%": s["pct"],
                       "tenho": f"{s['tenho']}/{s['precisa']}",
                       "comprar": s["comprar"], "ir buscar": s["noutra"],
                       "custo": f"{s['custo']:.2f}€", "estado": estado})
    _p(linhas, ["slot", "formato", "%", "tenho", "comprar", "ir buscar", "custo",
                "estado"])
    # POR ONDE COMEÇAR (v6): a mesma ordem da aba Plano — permanentes primeiro,
    # depois as candidatas mais perto de fechar. Uma função só para os dois.
    por_montar = [m for m in rep.get("montagem") or [] if not m["montado"]]
    if por_montar:
        print("\nPOR ONDE COMEÇAR")
        for i, m in enumerate(por_montar, 1):
            print(f"  {i}. {m['caixa']:<28} {m['pct']:>3}%  tirar {m['tirar']:>3}"
                  f"  comprar {m['comprar']:>3} ({m['custo']:.2f}€)"
                  f"  {m['estado']}")
    print(f"\n  comprar: {rep['comprar_total']} cópias / {rep['custo_total']:.2f}€")
    print(f"  ir buscar a outra caixa: {rep['noutra_total']} cópias (não são compra)")
    if rep.get("bloqueado_total"):
        n, c = rep["bloqueado_total"], len(rep["limites"])
        print(f"  limite de playset: {n} {'cópia' if n == 1 else 'cópias'} que "
              f"não se {'compra' if n == 1 else 'compram'} "
              f"({c} {'carta' if c == 1 else 'cartas'})")
    print(f"  partilhadas: {len(rep['conflitos'])} cartas que 2+ caixas querem")
    print(f"  venda: {rep['copias']} cópias / {rep['total']:.2f}€"
          f"  ·  Reserved List à parte: {rep['copias_rl']} / {rep['total_rl']:.2f}€")
    if rep["conflitos"]:
        print("\nCARTAS PARTILHADAS ENTRE CAIXAS (as 10 mais pedidas)")
        for c in rep["conflitos"][:10]:
            det = " · ".join(f"{q['slot']} {q['levou']}/{q['pediu']}"
                             for q in c["por_slot"])
            print(f"  {c['nm']:<28} tenho {c['tenho']} para {c['pedido']}   {det}")
            # Quem está nas duas listas levou parte do que pedia: não tem para
            # onde ir buscar, falta-lhe mesmo. Não entra no "vai buscar".
            # E se ninguém ficou com ela (as cópias existem mas nenhuma caixa as
            # pode usar), não há nada a ir buscar: é compra para todas.
            vai = [x for x in c["ficam_sem"]
                   if c["ficam_com"] and x not in c["ficam_com"]]
            print(f"  {'':<28} está em: {', '.join(c['ficam_com']) or 'ninguém'}"
                  + (f"   vai buscar: {', '.join(vai)}" if vai else ""))


def _basicas(rep, s):
    """O bloco «terrenos básicos» de uma caixa, no CLI.

    André, 2026-09-08: *"faltou marcares, para completar o deck, os terrenos
    básicos necessários!"* Sai da MESMA lista que a página mostra
    (`loadout.plano_basicas`) — duas contagens das terras eram duas
    oportunidades de discordarem, como já aconteceu com tudo o resto.
    """
    plano = loadout.plano_montar(rep, s["slot"])
    bs = (plano or {}).get("basicas") or []
    if not bs:
        return
    total = sum(b["need"] for b in bs)
    print(f"\n  TERRENOS BÁSICOS ({total} cópias — não contam para a %):")
    for b in bs:
        partes = [f"tirar {m['q']}× de {m['de']} [{(m['set_code'] or '').upper()}"
                  f"{' foil' if loadout.e_foil(m['finish']) else ''}]"
                  for m in b["tirar"]]
        if b["ja"] > 0:
            partes.append(f"{b['ja']} já na caixa")
        if b["granel"]:
            partes.append(f"{b['granel']} das tuas ({loadout.basicas_edicao()})")
        if b["comprar"]:
            partes.append(f"COMPRAR {b['comprar']} {b['req']} "
                          f"({b['cost']:.2f}€) — confirma se já tens")
        req = f" ({b['req']})" if b["req"] else ""
        print(f"    {b['need']}× {b['nm']}{req}: " + " | ".join(partes))


def _wantlist_basicas(s):
    """As básicas dentro da wantlist copiável, comentadas com `//`.

    O Cardmarket ignora as linhas que começam por `//`, e é isso que se quer: são
    terras que ele já tem em casa. Sem o bloco, a lista que ele copia para ir
    montar o deck não diz uma palavra sobre as 17 Island que ele tem de tirar da
    pilha. O que é MESMO compra (as Snow-Covered, que não existem em Unhinged)
    vai em linha normal, para entrar no carrinho.
    """
    bs = s.get("basicas") or []
    if not bs:
        return
    print("\n    // Basicas")
    for b in bs:
        if b["comprar"]:
            req = f" [{b['req']}]" if b["req"] else ""
            print(f"    {b['comprar']} {b['nm']}{req}   // confirma se ja tens")
        if b["da_base"]:
            print(f"    // {b['da_base']} {b['nm']} (na coleccao)")
        if b["granel"]:
            print(f"    // {b['granel']} {b['nm']} ({loadout.basicas_edicao()})")


def _loadout_detalhe(rep, procura):
    alvo = procura.lower()
    achados = [s for s in rep["slots"]
               if alvo in s["nome"].lower() or alvo in str(s["slot"]).lower()]
    if not achados:
        print(f"Nenhum slot do loadout com {procura!r}. Slots: "
              + ", ".join(s["nome"] for s in rep["slots"]))
        return
    for s in achados:
        print(f"\n=== {s['nome']} ({s['formato']}) — {s['pct']}% "
              f"[{s['tenho']}/{s['precisa']}] ===")
        print(f"  fonte: {s.get('fonte')} {s.get('ref') or ''} — {s['nota']}")
        for _ico, txt, _cls in loadout.rotulo_material(s):
            print(f"  {txt}")
        # Onde estão as cartas que ele já tem: é a metade da pergunta "onde está
        # a carta" que não é falta nenhuma — é o que se tira da estante para
        # montar. A Caixa RL aparece partida em PT e EN, como está lá.
        if s["origens"]:
            print("  tirar de: " + " · ".join(f"{k} {v}" for k, v in s["origens"].items()))
        _basicas(rep, s)
        if not s["missing"]:
            print("  COMPLETO.")
            continue
        print(f"\n  FALTAM {s['faltam']} cópias: {s['comprar']} a comprar "
              f"({s['custo']:.2f}€) + {s['noutra']} a ir buscar a outra caixa")
        for m in s["missing"]:
            u = f"{m['unit']:.2f}€" if m["unit"] else "?"
            # Quando o slot é de foil e o preço veio do nonfoil, diz-se: a
            # estimativa está por baixo, e é melhor sabê-lo antes de comprar.
            if s.get("acabamento") == "foil" and m["price_finish"] == "nonfoil":
                u += "*"
            partes = [f"comprar {m['comprar']}"
                      if 0 < m["comprar"] < m["missing"] else "",
                      "; ".join(f"em {c}: {q}" for c, q in sorted(m["noutra"].items())),
                      "; ".join(f"{v}× {k}" for k, v in m["alt"].items()),
                      "; ".join(f"em {k}: {v}" for k, v in m["alt_onde"].items())]
            extra = "   [" + " | ".join(p for p in partes if p) + "]" \
                if any(partes) else ""
            print(f"    {m['missing']}× {m['nm']:<34} {u:>10} {m['board']}{extra}")
        if any(m["price_finish"] == "nonfoil" for m in s["missing"]) \
                and s.get("acabamento") == "foil":
            print("    (* sem preço foil na base — o valor é o do nonfoil, "
                  "por baixo do real)")
        # Onde ir buscar (André, 2026-09-07): estas NÃO se compram — a cópia
        # existe, está noutra caixa do loadout, e vai-se lá buscar para jogar.
        if s["noutra_caixa"]:
            print(f"\n  IR BUSCAR A OUTRA CAIXA ({s['noutra']} cópias — não são compra):")
            for m in s["noutra_caixa"]:
                # A parte que ainda não está em casa: é uma compra PARTILHADA
                # que outra caixa faz. Mandá-lo à caixa do lado buscar uma carta
                # que ninguém comprou ainda era o mesmo tipo de mentira que o
                # "noutra caixa" veio corrigir.
                fut = m.get("noutra_futura") or {}
                onde = ", ".join(
                    f"{q}× em {c}" + (f" ({fut[c]} depois de {c} comprar)"
                                      if fut.get(c) else "")
                    for c, q in sorted(m["noutra"].items()))
                mais = f"   (comprar mais {m['comprar']})" if m["comprar"] else ""
                print(f"    {m['nm']:<34} {onde}{mais}")
        # E o que o TECTO DE PLAYSET não deixa comprar (André, 2026-09-08: *"no
        # Premodern, afinal só vou ter até playset de cada carta"*). Sem isto a
        # caixa ficava à espera de uma carta que ninguém vai comprar.
        if s.get("playset_faltas"):
            n = s["playset_bloqueado"]
            print(f"\n  LIMITE DE PLAYSET ({n} {'cópia' if n == 1 else 'cópias'} — "
                  f"máximo {loadout.playset_maximo(s)} por carta em "
                  f"{s.get('grupo')}, somando todas as caixas):")
            for m in s["playset_faltas"]:
                print(f"    {m['nm']:<34} falta {m['playset_bloqueado']} "
                      f"que não se compra ({m['board']})")
        compras = sorted((m for m in s["missing"] if m["comprar"]),
                         key=lambda x: x["nm"])
        if not compras:
            print("\n  nada a comprar: o que falta está todo noutras caixas.")
        else:
            print("\n  wantlist (formato Cardmarket) — só o que é mesmo compra:")
            for m in compras:
                # O material vai na LINHA, e vem da linha: numa compra partilhada
                # entre caixas é o do pool, que pode ser mais exigente do que o
                # desta caixa (ver `loadout.partilhar_compras`).
                marca = m.get("marca_compra") or loadout.marca_wantlist(s)
                print(f"    {m['comprar']} {m['nm']}" + (f" [{marca}]" if marca else ""))
        _wantlist_basicas(s)


def _carta(m):
    """`Plains [10E]` — a carta com a edição, num movimento de arrumação.

    Sem a edição, duas linhas do mesmo nome (dois lotes de impressões
    diferentes) apareciam como *"tirar 5× Plains"* e *"tirar 7× Plains"*, uma a
    seguir à outra, sem nada que as distinguisse. Não são a mesma pilha.
    """
    sc = (m.get("set_code") or "").upper()
    return f"{m['nm']} [{sc}]" if sc else m["nm"]


def _actualizacoes(plano):
    """As caixas CONGELADAS que têm delta por aplicar ("tirar X, meter Y").

    Vem antes da arrumação normal de propósito: é um gesto diferente e mais raro
    — abrir um deck que está sleevado, trocar duas cartas e voltar a fechá-lo —
    e o `--confirmar` NÃO lhe toca. É a ordem do André: *"apenas mexer para
    actualizar"* (2026-09-07, 19:00).
    """
    acts = plano.get("actualizacoes") or {}
    if not acts:
        return
    print(f"ACTUALIZAR DECKS MONTADOS — {plano['copias_actualizar']} cópias\n"
          "  (caixas dedicadas e montadas: a lista mudou, o deck não. "
          "Aplica-se no botão 'actualizei' do modo edição.)\n")
    for a in acts.values():
        print(f"  {a['caixa']}")
        for m in a["sai"]:
            print(f"    tirar  {m['q']}× {_carta(m):<40} -> {m['para']}")
        for m in a["entra"]:
            print(f"    meter  {m['q']}× {_carta(m):<40} <- {m['de']}")
        print()
    print()


def _arrumar(con, csv_out=False, confirmar=False):
    """A folha de arrumação: de que gaveta sai cada carta e para que caixa vai.

    O André (2026-09-07): *"quero que me ajudem a ser mais organizado com as
    cartas."* Com `--confirmar` grava a alocação de hoje como a arrumação real —
    é o mesmo botão *"já arrumei tudo"* da página.
    """
    rep = loadout.report(con)
    plano = rep["arrumacao"]
    if csv_out:
        print(loadout.csv_arrumacao(plano), end="")
        return
    _actualizacoes(plano)
    if not plano["movimentos"]:
        print("Nada a arrumar: a estante já está igual à alocação"
              + (" (à parte das actualizações acima)." if plano.get("actualizacoes")
                 else "."))
        return
    print(f"ARRUMAR — {plano['copias']} cópias em {plano['linhas']} linhas\n")
    print("DE CADA GAVETA (o que se tira)")
    for origem, movs in plano["por_origem"].items():
        print(f"\n  {origem}  ({sum(m['q'] for m in movs)} cópias)")
        for m in sorted(movs, key=lambda x: (x["para"], x["nm"])):
            print(f"    {m['q']}× {_carta(m):<40} -> {m['para']}")
    print("\n\nPARA CADA CAIXA (o que entra)")
    for destino, movs in plano["por_destino"].items():
        print(f"\n  {destino}  ({sum(m['q'] for m in movs)} cópias)")
        for m in sorted(movs, key=lambda x: (x["de"], x["nm"])):
            print(f"    {m['q']}× {_carta(m):<40} <- {m['de']}")
    if confirmar:
        n = loadout.guardar_arrumacao(con, rep)
        print(f"\n  ARRUMADO: {n} cópias registadas nas caixas. "
              "A partir de agora o vault diz que estão lá.")
    else:
        print("\n  (isto é só a folha — corre com --confirmar quando tiveres "
              "arrumado a sério)")


def _migrar_arquetipos(con, dry_run=False):
    """Passa as recusas e as escolhas de chave-NOME para chave-`id` estável.

    O mapa nome→`id` sai do ranking do dia, que é o único sítio onde os dois se
    veem ao mesmo tempo. O que hoje não tem listas fica como está — um arquétipo
    volta ao metagame daqui a um mês e apagar-lhe a recusa era decidir por ele.
    """
    from . import configio, premodern, sources
    cands = premodern.candidatos(con, loadout.report(con))
    mapa = premodern.mapa_de_ids(cands)
    p = configio.caminho(None)
    cfg = configio.ler(p)
    _novo, n = premodern.migrar_config(cfg, mapa)
    print(f"{len(cands)} arquétipos de Premodern com `id` estável hoje.")
    if not n:
        print("Nada a migrar — as recusas e as escolhas já estão por `id`.")
        return
    if dry_run:
        print(f"{n} linha(s) a converter (dry-run — nada escrito).")
        return
    configio.escrever(cfg, p)
    sources._CFG_CACHE.clear()
    print(f"{n} linha(s) convertidas em {p}.")


def _migrar(con, dry_run=False, com_backup=True):
    """Funde os baldes de colecção e de deck na `Colecção` (a RL fica de fora)."""
    from . import migracao
    antes = migracao.estado(con)
    rep = migracao.migrar(con, dry_run=dry_run, com_backup=com_backup)
    print("ANTES:")
    for b, q in antes.items():
        print(f"  {b:<26} {q:>5}")
    if not rep["total"]:
        print("\nNada a migrar — já está tudo na `Colecção`.")
        return
    print(f"\n{'FARIA' if dry_run else 'MOVEU'}: {rep['total']} cópias para "
          f"`{loadout.BALDE_COLECCAO}`")
    for b, q in rep["movidas"].items():
        print(f"  {b:<26} {q:>5}")
    if rep["arrumadas"]:
        print("\nDecks que ficam registados como MONTADOS (as cartas já estavam "
              "na caixa deles):")
        for slot, q in rep["arrumadas"].items():
            print(f"  {slot:<26} {q:>5}")
    if rep["backup"]:
        print(f"\nbackup: {rep['backup']}")
    if not dry_run:
        print("\nDEPOIS:")
        for b, q in migracao.estado(con).items():
            print(f"  {b:<26} {q:>5}")


def _premodern(rep, tudo=False):
    """`premodern sugestoes`: o ranking, a cobertura e o que daí vai à venda.

    A mesma conta da página (`res["premodern"]`), para o CLI e o site não darem
    números diferentes à mesma pergunta.
    """
    pm = rep.get("premodern") or {}
    if not pm.get("activo"):
        print("Não há nenhuma caixa de Premodern no `colecao_config.json → caixas`: "
              "sem um deck de Premodern, 'não usada por nenhum deck' não quer dizer "
              "nada e não se sugere nem se vende nada por esta regra.")
        return
    linhas = pm["todos"] if tudo else pm["elegiveis"]
    print("PREMODERN — o que montar a seguir\n")
    print(f"  «principal» = as caixas de Premodern PARTILHAM, por isso conta-se o "
          f"que este deck\n  teria se escolhesse primeiro (livres + as que estão "
          f"nas outras caixas do grupo).\n  «sobra» = só as que nenhuma caixa "
          f"levou. Sugere-se a partir de {pm['limiar']}% como principal.\n")
    _p([{"listas": c["n_lists"],
         "principal": f'{c["pct_principal"]}%',
         "sobra": f'{c["pct"]}%', "total": f'{c["pct_total"]}%',
         # Com `--tudo` entram arquétipos que não passaram por porta nenhuma: um
         # "—" aqui quer dizer que o `estado` diz "sugerida" mas a sugestão não
         # existe (só se sugere o que é top-10 ou top-5 de combo). Sem a coluna
         # a dizê-lo, a lista prometia decks que a página não mostra.
         "onde": ("top-10" if c["top"] else "combo" if c["top_combo"] else "—"),
         "combo": c["grau"] or "—", "estado": c["estado"],
         "comprar": c["comprar"], "custo": f'{c["custo"]:.2f}€',
         "arquétipo": c["nome"]} for c in linhas],
       ["listas", "principal", "sobra", "total", "onde", "combo", "estado",
        "comprar", "custo", "arquétipo"])
    sugs = pm["sugestoes"]
    if sugs:
        print(f"\nSUGESTÕES ({len(sugs)}) — no modo edição, «vou montar este» abre "
              f"a caixa; «não quero este» liberta as cartas para a venda")
        for c in sugs:
            print(f'  {c["nome"]:<32} {c["pct_principal"]:>3}% como principal · '
                  f'{c["pct"]:>3}% com o que sobra · '
                  f'comprar {c["comprar"]} ({c["custo"]:.2f}€)')
    else:
        print("\n  Nenhum candidato chega ao limiar, nem sequer como principal. "
              "O que sobra vai à venda.")
    if pm["recusadas"]:
        print("\nRECUSADAS (as cartas delas estão livres para venda)")
        for nome, quando in sorted(pm["recusadas"].items()):
            print(f"  {nome:<32} em {quando}")
    n = sum(r["q"] for k in ("venda", "venda_rl") for r in rep[k]
            if r["reason"] == loadout.RAZAO_PREMODERN)
    v = sum(r["total"] or 0 for k in ("venda", "venda_rl") for r in rep[k]
            if r["reason"] == loadout.RAZAO_PREMODERN)
    print(f'\n  VENDER por "{loadout.RAZAO_PREMODERN}": {n} cópias / {v:.2f}€'
          f'  (vê a lista com `vender --tudo`)')
    if rep["copias_reservadas"]:
        print(f'  reservadas por sugestões abertas: {rep["copias_reservadas"]} '
              f'cópias / {rep["total_reservado"]:.2f}€ — não se vendem')


def _vender(rep, csv_out=False, tudo=False):
    blocos = [("VENDER", rep["venda"])]
    if tudo:
        blocos += [("VENDER — RESERVED LIST (confirmar uma a uma)", rep["venda_rl"]),
                   # A RL que a regra dos 5 % segurou (André, 2026-09-08). Duas
                   # listas e não uma: "subiu" é uma decisão tomada, "não sei" é
                   # uma decisão por tomar — e é só a segunda que ele pode querer
                   # forçar (baixando `venda.rl_janela_dias`).
                   ("RL A SEGURAR — valorizou, não se vende", rep["rl_segurar"]),
                   ("RL SEM HISTÓRICO SUFICIENTE — não se vende sem saber",
                    rep["rl_sem_historico"]),
                   ("GUARDAR — servem um deck do loadout", rep["guardar"]),
                   # Reservadas por uma sugestão de Premodern OU pela caixa de
                   # Legacy, que desde 2026-09-08 aceita RL em PT e ainda não tem
                   # deck escolhido (segura-a o top-N do metagame).
                   ("RESERVADAS — decks por decidir", rep["reservadas"]),
                   ("RETIDOS — extras de deck (reter_extras_meses)", rep["retidos"])]
    if csv_out:
        print("bloco,quantidade,carta,balde,edicao,acabamento,lingua,"
              "preco_unitario,total,reserved_list,motivo")
        for titulo, linhas in blocos:
            for r in linhas:
                print(f'{titulo},{r["q"]},"{r["nm"]}","{r["local"]}",{r["set_code"]},'
                      f'{r["finish"]},{r["lang"]},{r["unit"] or ""},{r["total"]},'
                      f'{1 if r["rl"] else 0},"{r["reason"]}"')
        return
    for titulo, linhas in blocos:
        print(f"\n{titulo}  —  {sum(r['q'] for r in linhas)} cópias, "
              f"{sum(r['total'] or 0 for r in linhas):.2f}€")
        _p([{"q": r["q"], "carta": r["nm"], "balde": r["local"], "ed": r["set_code"],
             "fin": r["finish"], "ln": r["lang"],
             "unit": f"{r['unit']:.2f}" if r["unit"] else "?",
             "total": f"{r['total']:.2f}",
             # A janela em que a subida foi medida, por cópia: com a janela a
             # crescer todos os dias, "não subiu" em 27 dias e em 90 não são a
             # mesma afirmação.
             "motivo": " ".join(x for x in (r["reason"], r.get("rl_nota")) if x)}
            for r in linhas],
            ["q", "carta", "balde", "ed", "fin", "ln", "unit", "total", "motivo"])
    if not tudo:
        print(f"\n  (à parte: Reserved List {rep['copias_rl']} cópias / "
              f"{rep['total_rl']:.2f}€, substitutos a guardar {rep['copias_guardar']} / "
              f"{rep['total_guardar']:.2f}€ — vê com --tudo)")
    if rep["copias_rl_retidas"]:
        maxi, mini = loadout.rl_janela_dias(), loadout.rl_janela_minima()
        pct = loadout.rl_subida_minima()
        print(f"\n  🔒 REGRA DA RL: {rep['copias_rl_retidas']} cópias / "
              f"{rep['total_rl_retido']:.2f}€ NÃO entram na venda — só se vende "
              f"Reserved List que não tenha subido {pct:.0f}% em {maxi} dias.\n"
              # A janela é um MÁXIMO desde 2026-09-08: cada carta é medida no
              # histórico que tem, e o limiar acompanha. Sem isto escrito, dois
              # dias seguidos dão respostas diferentes sem explicação nenhuma.
              f"     a janela é um máximo: cada carta mede-se no histórico que "
              f"tem (mínimo {mini} d)"
              + (f", com os {pct:.0f}% à letra (rl_limiar_fixo)."
                 if loadout.rl_limiar_fixo() else
                 f", e o limiar acompanha-a — {pct:.0f}% a {maxi} d, "
                 f"{pct * mini / maxi:.1f}% a {mini} d.") + "\n"
              f"     valorizou: {rep['copias_rl_segurar']} / "
              f"{rep['total_rl_segurar']:.2f}€ · sem histórico: "
              f"{rep['copias_rl_sem_historico']} / "
              f"{rep['total_rl_sem_historico']:.2f}€")
    if rep["copias_reservadas"]:
        print(f"  💡 RESERVADAS: {rep['copias_reservadas']} cópias / "
              f"{rep['total_reservado']:.2f}€ de decks por decidir "
              f"(sugestões de Premodern e a RL que o Legacy usaria).")
    print("\n  SUGESTÃO A CONFIRMAR: nada sai da coleção sem tu dizeres.")


if __name__ == "__main__":
    sys.exit(main())
