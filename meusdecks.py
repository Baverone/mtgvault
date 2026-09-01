"""Gera meusdecks.html — "Os meus decks".

Só os decks do André: os que segue (tabela `decks`) e os que tem montados com
lista vigiada (Blue Farm, Cloud cEDH, Pauper — via `watched`+`deck_collection`).

Por deck: quem segue/vigia, % de completo, datas (última verificação / última
alteração), link à fonte, a EVOLUÇÃO da lista (▲ entrou / ▼ saiu, com datas, e
cada carta a VERDE se a tenho / VERMELHO se não), e a lista COMPLETA (main+side,
com básicas) em arte — verde = tenho, vermelho = falta. NÃO inventa nada.
"""
from __future__ import annotations

import html
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import buildability as bd  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

FMT_LABEL = bd.FMT_LABEL
FMT_ORDER = bd.FMT_ORDER

DECK_CORE = {
    "Izzet Affinity (Kappa Cannoneer)": "modern:affinity-kappa",
    "Grinding Station": "modern:grinding-station",
    "Cloud (Duel Commander)": "dc:cloud",
    "Jeskai Lessons": "standard:jeskai:wur",
    "Greasefang": "pioneer:greasefang:orzhov",
}


def _decks_vigiados():
    """Nomes de decks (da tabela `decks`) a mostrar na página 'Decks permanentes',
    lidos do colecao_config.json. Vazio/em falta = critério antigo (link/auto)."""
    try:
        cfg = json.loads((ROOT / "colecao_config.json").read_text(encoding="utf-8"))
        return set(cfg.get("decks_vigiados") or [])
    except Exception:
        return set()

TABS = ('<nav class="tabs"><a href="index.html">🏠 Início</a>'
        '<a class="cur" href="meusdecks.html">🎴 Decks permanentes</a><a href="showcase.html">🎯 Showcase Challenger</a>'
        ''
        ''
        '<a href="colecao_cor.html">📚 Coleção</a><a href="caixarl.html">📦 Caixa RL</a></nav>')


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _owned_sid(con):
    out = {}
    for r in con.execute("""SELECT c.name nm, cp.scryfall_id sid FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player'"""):
        out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    return out


def _img_map(con, names):
    out = {}
    names = list(names)
    for i in range(0, len(names), 300):
        chunk = names[i:i + 300]
        ph = ",".join("?" for _ in chunk)
        for r in con.execute(f"""SELECT name nm, scryfall_id sid FROM cards
                                  WHERE name IN ({ph}) AND digital = 0 GROUP BY name""", chunk):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    # DFCs: o catálogo guarda "frente // verso"; casa pela FRENTE as que faltaram
    # (ex.: Boggart Trawler), senão ficavam sem imagem (carta preta).
    for n in [x for x in names if x not in out]:
        r = con.execute("SELECT scryfall_id sid FROM catalog.cards "
                        "WHERE (name = ? OR name LIKE ?) AND digital = 0 LIMIT 1",
                        (n, n + " // %")).fetchone()
        if r:
            out[n] = r["sid"]
    return out


def _timeline(snaps, limit=40):
    events = []
    for i in range(len(snaps) - 1):
        new, old = snaps[i][1], snaps[i + 1][1]
        ins = sorted(k[1] for k in set(new) | set(old) if new.get(k, 0) > old.get(k, 0))
        outs = sorted(k[1] for k in set(new) | set(old) if new.get(k, 0) < old.get(k, 0))
        if ins or outs:
            events.append({"date": snaps[i][0], "ins": ins, "outs": outs})
    return events[:limit]


def _evolution_core(con, core_key):
    if not core_key:
        return []
    snaps = [(r["taken_at"],
              {tuple(c[:2]): (c[2] if len(c) > 2 else 1) for c in json.loads(r["cards_json"])})
             for r in con.execute("SELECT taken_at, cards_json FROM core_snapshots "
                                  "WHERE core_key = ? ORDER BY taken_at DESC", (core_key,))]
    return _timeline(snaps)


def _evolution_watched(con, wid):
    rows = con.execute("SELECT taken_at, cards FROM watched_snapshots "
                       "WHERE watched_id = ? ORDER BY taken_at DESC", (wid,)).fetchall()
    snaps = [(r["taken_at"], {(b, nm): q for b, nm, q in json.loads(r["cards"])}) for r in rows]
    return _timeline(snaps)


def _source(notes):
    notes = notes or ""
    if "consenso" in notes:
        return "🧩 consenso"
    if "auto:" in notes:
        p = notes.split()
        return f"🎯 segue {p[2] if len(p) > 2 else '?'}"
    return "🎯 seguido"


def _target_link(con, notes):
    """Link para a decklist de origem (do #id na nota) e a data dela."""
    m = re.search(r"#(\d+)", notes or "")
    if not m:
        return None, None
    r = con.execute("SELECT url, event_date FROM decklists WHERE id = ?", (m.group(1),)).fetchone()
    return (r["url"] if r else None), (r["event_date"] if r else None)


def _owned_qty(con):
    """nome (frente) -> nº de cópias que o André tem (jogáveis, coleção toda)."""
    out = defaultdict(int)
    for r in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player' GROUP BY c.name"""):
        out[r["nm"].split(" // ")[0]] += r["q"]
    return out


CLOUD_DC = "Cloud (Duel Commander)"
# Eventos casuais (excluídos do consenso de Cloud DC): só Challenges + torneios.
_CASUAL = ("League", "Liga", "FNM", "semanal", "Mercredi", "Duelo", "Tuesday")
CONS_MIN = 30   # limiar (%) das staples que faltam

# Ordem de organização dos decks por tipo de carta (pedido do André, 2026-08-31).
TYPE_ORDER = ["Creature", "Planeswalker", "Sorcery", "Instant", "Artifact", "Enchantment", "Land"]


def _bucket(type_line):
    """Tipo principal de uma carta, pela ordem do André (Creature 1º, Land último).
    Cartas de múltiplos tipos caem no 1º tipo que casa (ex.: Artifact Creature →
    Creature)."""
    tl = (type_line or "").split(" // ")[0]
    return next((t for t in TYPE_ORDER if t in tl), "Other")


def _type_map(con, names):
    """nome (frente) -> tipo principal (bucket)."""
    tm = {}
    names = list(names)
    for i in range(0, len(names), 300):
        chunk = names[i:i + 300]
        ph = ",".join("?" for _ in chunk)
        for r in con.execute(f"SELECT name nm, type_line tl FROM cards "
                             f"WHERE name IN ({ph}) AND digital=0 GROUP BY name", chunk):
            tm[r["nm"].split(" // ")[0]] = _bucket(r["tl"])
    # DFCs: o catálogo guarda "frente // verso"; casa pela frente as que faltaram.
    for n in [x for x in names if x not in tm]:
        r = con.execute("SELECT type_line tl FROM catalog.cards "
                        "WHERE (name = ? OR name LIKE ?) AND digital=0 LIMIT 1",
                        (n, n + " // %")).fetchone()
        if r:
            tm[n] = _bucket(r["tl"])
    return tm


def _group_by_type(cards, tm, render):
    """Agrupa os cartões por tipo (ordem do André) com um cabeçalho por grupo. Cada
    carta pode trazer o seu tipo em `_type` (ex.: staples que faltam); senão usa tm."""
    buckets = defaultdict(list)
    for c in cards:
        buckets[c.get("_type") or tm.get(c["nm"].split(" // ")[0], "Other")].append(c)
    out = ""
    for t in TYPE_ORDER + ["Other"]:
        b = buckets.get(t)
        if not b:
            continue
        out += (f'<div class="typehdr">{html.escape(t)} <span class="dim">{sum(c.get("qty", 1) for c in b)}</span></div>'
                f'<div class="cards">{"".join(render(c) for c in b)}</div>')
    return out


def _cloud_consensus(con, his_names):
    """Análise de consenso do Cloud (Duel Commander): sobre as listas de Cloud de
    eventos NÃO-casuais (Challenges + torneios), devolve
      pct = {carta: % de listas que a jogam}  (só não-básicas)
      missing = [{nm,pct,sid}] das cartas de consenso >= CONS_MIN que NÃO estão na
                lista do McWinSauce, ordenadas por consenso desc (staples que faltam).
    Mantém a lista do McWinSauce; isto é só o overlay. NÃO inventa nada."""
    excl = " AND ".join(f"dl.event_name NOT LIKE '%{k}%'" for k in _CASUAL)
    pool = [r["id"] for r in con.execute(
        f"""SELECT dl.id FROM decklists dl WHERE dl.format='duel-commander' AND {excl}
             AND EXISTS (SELECT 1 FROM decklist_cards y WHERE y.decklist_id=dl.id
                          AND y.card_name LIKE 'Cloud,%')""")]
    n = len(pool)
    if not n:
        return None
    ph = ",".join("?" * n)
    pct = {}
    for r in con.execute(f"SELECT card_name nm, COUNT(DISTINCT decklist_id) c "
                         f"FROM decklist_cards WHERE decklist_id IN ({ph}) GROUP BY card_name", pool):
        f = r["nm"].split(" // ")[0]
        if f not in bd.BASICS:
            pct[f] = max(pct.get(f, 0), round(100 * r["c"] / n))
    miss = sorted(((p, nm) for nm, p in pct.items() if nm not in his_names and p >= CONS_MIN),
                  reverse=True)
    names = [nm for _, nm in miss]
    sids, types = {}, {}
    if names:
        ph2 = ",".join("?" * len(names))
        for r in con.execute(f"SELECT name nm, scryfall_id sid, type_line tl FROM cards "
                             f"WHERE name IN ({ph2}) AND digital=0 GROUP BY name", names):
            f = r["nm"].split(" // ")[0]
            sids.setdefault(f, r["sid"])
            types.setdefault(f, _bucket(r["tl"]))
    miss_list = [{"nm": nm, "pct": p, "sid": sids.get(nm), "type": types.get(nm)} for p, nm in miss]
    # Trocas 1-a-1: as não-básicas de MENOR consenso dele <-> as staples de MAIOR
    # consenso que faltam, enquanto a que entra tem consenso maior que a que sai.
    his_nb = sorted((pct.get(nm, 0), nm) for nm in his_names if nm not in bd.BASICS)
    swaps = []
    for i in range(min(len(his_nb), len(miss_list))):
        op, on = his_nb[i]
        m = miss_list[i]
        if m["pct"] > op:
            swaps.append({"out": on, "outp": op, "in": m["nm"], "inp": m["pct"],
                          "insid": m["sid"], "intype": m["type"]})
        else:
            break
    return {"pct": pct, "n": n, "missing": miss_list, "swaps": swaps}


def _faltas(cards):
    """{nome (frente): cópias em falta} de uma lista de cartões (qty - hq), sem básicas."""
    out = defaultdict(int)
    for c in cards:
        m = c["qty"] - c["hq"]
        if m > 0 and c["nm"] not in bd.BASICS:
            out[c["nm"].split(" // ")[0]] += m
    return out


def _faltas_html(faltas, cls="", label="🛒 Faltas"):
    """Bloco de faltas: cabeçalho + lista 'N× Carta' (alfabética) + botão copiar
    (guarda o formato Cardmarket 'N Carta' numa textarea escondida)."""
    if not faltas:
        return ""
    order = sorted(faltas.items())
    items = "".join(f'<li><b>{q}×</b> {html.escape(nm)}</li>' for nm, q in order)
    cmk = "\n".join(f"{q} {nm}" for nm, q in order)
    return (f'<div class="faltas {cls}"><div class="flh">{label} '
            f'<span class="dim">{len(faltas)} · {sum(faltas.values())} cóp.</span>'
            f'<button class="cpbtn" onclick="cpFaltas(this)">copiar</button></div>'
            f'<ul class="fl">{items}</ul>'
            f'<textarea class="cmk" readonly>{html.escape(cmk)}</textarea></div>')


def _cards(items, osid, imgmap, owned_qty):
    """items = [(nome, qty)] -> [{nm, qty, hq, state, sid}], contando CÓPIAS.
    hq = quantas dessas cópias o André tem (básicas = sempre suficientes). state:
    have (tem as que precisa) / part (tem algumas) / miss (não tem nenhuma)."""
    out = []
    for nm, q in items:
        oq = q if nm in bd.BASICS else owned_qty.get(nm, 0)
        hq = min(q, oq)
        state = "have" if hq >= q else ("part" if hq > 0 else "miss")
        out.append({"nm": nm, "qty": q, "hq": hq, "state": state,
                    "sid": osid.get(nm) or imgmap.get(nm)})
    return sorted(out, key=lambda c: ({"have": 0, "part": 1, "miss": 2}[c["state"]], c["nm"]))


def _watched_decks(con, osid, imgmap, owned_names):
    out = []
    for r in con.execute("""SELECT w.id wid, w.label, w.format, w.notes, w.last_checked, dc.sub_collection balde
                              FROM watched w JOIN deck_collection dc ON dc.watched_id = w.id
                             ORDER BY w.label"""):
        m = re.search(r"https?://\S+", r["notes"] or "")
        wurl = m.group(0) if m else None
        snap = con.execute("SELECT taken_at, cards FROM watched_snapshots WHERE watched_id = ? "
                           "ORDER BY taken_at DESC LIMIT 1", (r["wid"],)).fetchone()
        if not snap:
            continue
        main_i, side_i = defaultdict(int), defaultdict(int)
        for b, nm, q in json.loads(snap["cards"]):
            (side_i if b == "side" else main_i)[nm.split(" // ")[0]] += q
        oq = defaultdict(int)
        for o in con.execute("""SELECT c.name nm, SUM(cp.quantity) q FROM copies cp
                                  JOIN cards c ON c.scryfall_id = cp.scryfall_id
                                  JOIN sub_collections s ON s.id = cp.sub_collection_id
                                 WHERE s.name = ? GROUP BY c.name""", (r["balde"],)):
            oq[o["nm"].split(" // ")[0]] += o["q"]
        evol = _evolution_watched(con, r["wid"])
        out.append({"name": r["label"], "format": r["format"], "source": "👁️ vigiado",
                    "main": _cards(list(main_i.items()), osid, imgmap, oq),
                    "side": _cards(list(side_i.items()), osid, imgmap, oq),
                    "evol": evol, "owned_names": set(oq),
                    "verif": r["last_checked"] or snap["taken_at"],
                    "alter": evol[0]["date"] if evol else None, "link": wurl})
    return out


def _deck_card(d, tm):
    def cnt(cards):
        return sum(c["hq"] for c in cards), sum(c["qty"] for c in cards)
    mh, mt = cnt(d["main"])
    sh, st = cnt(d["side"])
    have, tot = mh + sh, mt + st          # POR CÓPIAS (ex.: 68/75), não distintas
    pct = round(100 * have / tot) if tot else 0
    col = "var(--add)" if pct >= 90 else "var(--gold)" if pct >= 60 else "var(--warn)"
    on = d.get("owned_names", set())
    cons = d.get("consensus")
    meta = f'<span class="mi">✅ Confirmado dia {d["verif"] or "—"}</span>'
    meta += f'<span class="mi">✏️ Última alteração foi {d["alter"] or "—"}</span>'
    if d.get("link"):
        meta += f'<a class="mi lk" href="{html.escape(d["link"])}" target="_blank" rel="noopener">🔗 lista ↗</a>'
    ev = d["evol"]
    if ev:
        def line(e):
            def chip(c, arrow):
                cls = "have" if (c in on or c in bd.BASICS) else "miss"
                return f'<span class="ec {cls}">{arrow}{html.escape(c)}</span>'
            body = "".join(chip(c, "▲") for c in e["ins"]) + "".join(chip(c, "▼") for c in e["outs"])
            return f'<div class="evrow"><span class="evd">{e["date"]}</span>{body}</div>'
        head = f'<div class="evnow"><span class="evt">📈 última alteração</span>{line(ev[0])}</div>'
        rest = "".join(line(e) for e in ev[1:4])
        more = (f'<details class="evol"><summary>+ {len(ev) - 1} anteriores</summary>{rest}</details>'
                if rest else "")
        evol = head + more
    else:
        evol = '<div class="evx">📈 evolução — histórico a acumular</div>'

    def _cs(nm):
        if not cons:
            return ""
        p = cons["pct"].get(nm.split(" // ")[0])
        if p is None:
            return ""
        t = "hi" if p >= 70 else "mid" if p >= CONS_MIN else "lo"
        return f'<span class="cs {t}" title="{p}% das listas de Cloud">{p}%</span>'

    def rc(c, mark=""):
        img = (f'<img loading="lazy" src="{_art(c["sid"])}" alt="">' if c.get("sid")
               else '<div class="noimg"></div>')
        qb = (f'<span class="cq">{c["hq"]}/{c["qty"]}</span>' if c.get("qty", 1) > 1
              else ('' if c["state"] == "have" else '<span class="cq">0/1</span>'))
        return f'<div class="cd {c["state"]}{mark}" title="{html.escape(c["nm"])}">{img}{qb}{_cs(c["nm"])}</div>'

    if cons:
        # Cloud DC: duas colunas — a lista dele | a alterada por consenso (trocas
        # 1-a-1 das mais fracas dele pelas staples de maior consenso). Cada coluna
        # organizada por tipo.
        swaps = cons["swaps"]
        outn = {s["out"] for s in swaps}
        ins = [{"nm": s["in"], "sid": s["insid"], "_type": s.get("intype"),
                "state": "have" if (s["in"] in on or s["in"] in bd.BASICS) else "miss"} for s in swaps]
        left = _group_by_type(d["main"], tm, lambda c: rc(c, " cut" if c["nm"] in outn else ""))
        right_cards = [c for c in d["main"] if c["nm"] not in outn] + [{**c, "_add": 1} for c in ins]
        right = _group_by_type(right_cards, tm, lambda c: rc(c, " addc" if c.get("_add") else ""))
        srows = "".join(
            f'<div class="swap"><span class="so">🔴 {html.escape(s["out"])}<em>{s["outp"]}%</em></span>'
            f'<span class="sar">→</span>'
            f'<span class="si">🟢 {html.escape(s["in"])}<em>{s["inp"]}%</em></span></div>' for s in swaps)
        detail = (f'<div class="twocol"><div class="tc">'
                  f'<div class="cardshdr">🃏 Lista McWinSauce <span class="dim">({len(d["main"])})</span></div>'
                  f'{left}</div><div class="tc">'
                  f'<div class="cardshdr cs-h">🧩 Alterada por consenso</div>{right}</div></div>')
        detail += (f'<div class="cardshdr cs-h">⇄ {len(swaps)} trocas que o consenso sugere '
                   f'<span class="dim">(popularidade, não sinergia)</span></div>'
                   f'<div class="swaps">{srows}</div>') if swaps else \
                  '<div class="evx">O consenso não sugere trocas — a lista já é standard.</div>'
    else:
        detail = (f'<div class="cardshdr">🃏 main deck <span class="dim">({mh}/{mt})</span></div>'
                  f'{_group_by_type(d["main"], tm, rc)}')
        if d["side"]:
            detail += (f'<div class="cardshdr sb">🎒 sideboard <span class="dim">({sh}/{st})</span></div>'
                       f'{_group_by_type(d["side"], tm, rc)}')
    detail += _faltas_html(_faltas(d["main"] + d["side"]), cls="dk")
    return (
        f'<div class="deck{" wide" if cons else ""}" data-deck="{html.escape(d["name"])}"><div class="dtop">'
        f'<b>{html.escape(d["name"])}</b>'
        f'<span class="pct" style="color:{col}">{have}/{tot} · {pct}%</span></div>'
        f'<div class="badges"><span class="bdg src">{d["source"]}</span>'
        f'<button class="updbtn" onclick="markUpd(this)">atualizado</button></div>'
        f'<div class="bar"><span style="width:{pct}%;background:{col}"></span></div>'
        f'<div class="meta">{meta}</div>'
        f'<div class="upd"></div>'
        f'{evol}{detail}</div>')


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "meusdecks.html")
    owned_names = set(owned_playable(con))
    owned_qty = _owned_qty(con)
    osid = _owned_sid(con)
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""

    rows = list(con.execute("SELECT id, name, format, notes FROM decks"))
    vigiados = _decks_vigiados()
    allnames = set()
    for d in rows:
        for r in con.execute("SELECT card_name nm FROM deck_cards WHERE deck_id=?", (d["id"],)):
            allnames.add(r["nm"].split(" // ")[0])
    for r in con.execute("""SELECT ws.cards FROM watched_snapshots ws
                             JOIN deck_collection dc ON dc.watched_id = ws.watched_id"""):
        for b, nm, q in json.loads(r["cards"]):
            allnames.add(nm.split(" // ")[0])
    # Decks Mox Opal — do pool competitivo do Showcase (Showcase Challenge +
    # presenciais); atualiza-se sozinho à medida que chegam eventos novos.
    import showcase  # deferido: o showcase importa meusdecks, evita ciclo no topo
    mox = showcase.decks_with_card(con, "Mox Opal", "modern")
    for _mn, _mc in mox:
        for m in _mc["members"]:
            allnames |= set(m["main"]) | set(m["side"])

    imgmap = _img_map(con, allnames)
    tm = _type_map(con, allnames)

    by_fmt = defaultdict(list)
    for d in rows:
        main_items = [(r["nm"], r["q"]) for r in con.execute(
            "SELECT card_name nm, SUM(quantity) q FROM deck_cards WHERE deck_id=? "
            "AND board IN ('main','') GROUP BY card_name", (d["id"],))]
        side_items = [(r["nm"], r["q"]) for r in con.execute(
            "SELECT card_name nm, SUM(quantity) q FROM deck_cards WHERE deck_id=? "
            "AND board='side' GROUP BY card_name", (d["id"],))]
        if not main_items and not side_items:
            continue
        link, ldate = _target_link(con, d["notes"])
        # Decks permanentes: só os que o André escolheu (decks_vigiados no config) —
        # exclui os decks de referência do metagame (Modern/Standard/Pioneer, Spock)
        # e INCLUI o consenso Cloud Duel Commander. Config vazio = critério antigo.
        if vigiados:
            if d["name"] not in vigiados:
                continue
        elif not link and "auto:" not in (d["notes"] or ""):
            continue
        evol = _evolution_core(con, DECK_CORE.get(d["name"]))
        core_dates = [r["taken_at"] for r in con.execute(
            "SELECT MAX(taken_at) taken_at FROM core_snapshots WHERE core_key=?",
            (DECK_CORE.get(d["name"], ""),))] if DECK_CORE.get(d["name"]) else []
        deck = {
            "name": d["name"], "format": d["format"], "source": _source(d["notes"]),
            "main": _cards(main_items, osid, imgmap, owned_qty),
            "side": _cards(side_items, osid, imgmap, owned_qty), "evol": evol,
            "owned_names": owned_names,
            "verif": (core_dates[0] if core_dates and core_dates[0] else ldate),
            "alter": evol[0]["date"] if evol else None, "link": link}
        if d["name"] == CLOUD_DC:
            deck["consensus"] = _cloud_consensus(con, {nm for nm, _ in main_items})
            deck["verif"] = today            # o job confirma o Cloud DC todos os dias
            deck["alter"] = ldate or deck["alter"]   # data da lista do McWinSauce seguida
        by_fmt[d["format"]].append(deck)
    for d in _watched_decks(con, osid, imgmap, owned_names):
        by_fmt[d["format"]].append(d)

    # Lista ATUAL de cada deck (nome + imagem), main+side, um por nome. O cliente
    # compara-a com a lista de quando o André marcou "atualizado" e mostra o diff
    # LÍQUIDO (entram / saem). Por ser diferença de conjuntos, trata sozinha as
    # re-entradas: sai e volta = sem mudança; entra e sai = sem mudança.
    deckcur = {}
    for decks in by_fmt.values():
        for d in decks:
            seen = {}
            for c in d["main"] + d["side"]:
                f = c["nm"].split(" // ")[0]
                seen.setdefault(f, c["sid"])
            deckcur[d["name"]] = [[f, s] for f, s in seen.items()]

    secs, subnav, n_total = "", "", 0
    for fmt in FMT_ORDER + [f for f in by_fmt if f not in FMT_ORDER]:
        decks = by_fmt.get(fmt)
        if not decks:
            continue
        decks.sort(key=lambda x: -(sum(c["hq"] for c in x["main"] + x["side"])
                                    / max(1, sum(c["qty"] for c in x["main"] + x["side"]))))
        n_total += len(decks)
        lbl = FMT_LABEL.get(fmt, fmt)
        subnav += f'<a href="#f-{fmt}">{html.escape(lbl)}</a>'
        cards = "".join(_deck_card(d, tm) for d in decks)
        secs += (f'<section id="f-{fmt}"><h2>{html.escape(lbl)} '
                 f'<span class="n">{len(decks)}</span></h2><div class="grid">{cards}</div></section>')

    # Secção Decks Mox Opal (metagame, atualiza sozinho) — renderizada pelo showcase.
    if mox:
        moxcards = "".join(showcase._archetype_html(mc, name, tm, owned_names, owned_qty, imgmap)
                           for name, mc in mox)
        subnav = '<a href="#mox">🔷 Mox Opal</a>' + subnav
        secs = (f'<section id="mox"><h2>🔷 Decks Mox Opal <span class="n">{len(mox)}</span></h2>'
                f'<p style="color:var(--muted);font-size:12px;margin:2px 0 10px">Arquétipos do metagame '
                f'(Showcase Challenge + presenciais) que jogam Mox Opal — melhor build primeiro, atualiza '
                f'sozinho. Cartas <b style="color:var(--add)">a cor = tens</b>.</p>'
                f'<div class="moxgrid">{moxcards}</div></section>') + secs

    # Faltas consolidadas: soma as faltas de TODOS os decks permanentes.
    faltas = defaultdict(int)
    for decks in by_fmt.values():
        for d in decks:
            for nm, q in _faltas(d["main"] + d["side"]).items():
                faltas[nm] += q
    if faltas:
        secs += ('<section id="faltas">'
                 + _faltas_html(faltas, cls="cons", label="🛒 Faltas — todos os decks")
                 + '</section>')

    out.write_text(_TMPL.replace("%TABS%", TABS).replace("%SUBNAV%", subnav)
                   .replace("%SECS%", secs).replace("%N%", str(n_total))
                   .replace("%DECKCUR%", json.dumps(deckcur, ensure_ascii=False))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decks permanentes</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .subnav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px} .subnav a{font-size:12px;padding:5px 11px;border-radius:20px;background:#141a24;border:1px solid var(--line);color:var(--muted);text-decoration:none} .subnav a:hover{color:var(--ink);border-color:var(--accent)}
 h2{font-size:14px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:#4a5666}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}
 .deck:hover{border-color:#37445a}
 .dtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px} .dtop b{font-size:15px} .pct{font-weight:800;font-size:16px}
 .badges{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:7px 0} .bdg{font-size:11px;padding:2px 7px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .updbtn{margin-left:auto;font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;border:1px solid var(--line);background:#1a2230;color:var(--muted);cursor:pointer}
 .updbtn:hover{border-color:var(--accent);color:var(--ink)} .updbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .upd:empty{display:none}
 .upend{background:#241a10;border:1px solid #6a4f2f;border-radius:10px;padding:7px 9px;margin:6px 0;font-size:11.5px;color:#f0dcc0} .upend b{color:var(--gold)}
 .uprow{display:flex;flex-wrap:wrap;gap:4px 5px;align-items:center;padding:2px 0}
 .upd-d{color:var(--muted);min-width:66px;font-variant-numeric:tabular-nums}
 .uok{color:var(--add);font-size:11.5px;margin:5px 0}
 .chgbox{background:#0f141c;border:1px solid #37445a;border-radius:10px;padding:8px 10px;margin:6px 0}
 .chglbl{color:var(--gold);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px;font-weight:700}
 .chgi{display:flex;gap:9px;align-items:flex-start}
 .chgrp{flex:1;min-width:0} .chgrp>b{display:block;font-size:11px;margin-bottom:4px} .chgrp>b.in{color:var(--add)} .chgrp>b.out{color:var(--warn)}
 .chc-row{display:flex;flex-wrap:wrap;gap:3px}
 .chc{width:42px;height:59px;border-radius:4px;object-fit:cover;display:block}
 .chc.in{box-shadow:0 0 0 2px var(--add)} .chc.out{box-shadow:0 0 0 2px var(--warn);filter:grayscale(.3) brightness(.82)}
 .chc.noi{background:#0c0f14} .chbar{width:1px;align-self:stretch;background:var(--line)}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:4px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .meta{display:flex;flex-wrap:wrap;gap:4px 10px;color:var(--muted);font-size:11px;margin:5px 0} .mi.lk{color:var(--accent);text-decoration:none}
 .evx{color:#5a6472;font-size:11px;margin-top:6px}
 .evnow{background:#0f141c;border:1px solid var(--line);border-radius:10px;padding:7px 9px;margin-top:6px}
 .evt{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}
 .evol{margin-top:6px} .evol>summary,.cardsd>summary{cursor:pointer;color:var(--accent);font-size:12px}
 .evrow{display:flex;flex-wrap:wrap;gap:4px 5px;align-items:center;font-size:11px;padding:2px 0}
 .evd{color:var(--muted);min-width:70px;font-variant-numeric:tabular-nums}
 .ec{padding:0 4px;border-radius:5px} .ec.have{color:var(--add);background:#0f2418} .ec.miss{color:#ff8f8f;background:#2a1414}
 .cardshdr{margin-top:9px;font-size:12px;color:var(--accent)} .cardshdr .dim{color:var(--muted)} .cardshdr.sb{color:var(--gold)}
 .typehdr{margin:8px 0 1px;font-size:10.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} .typehdr .dim{color:#4a5666}
 .typehdr+.cards{margin-top:3px}
 .cards{display:flex;flex-wrap:wrap;gap:4px;margin-top:7px}
 .cd{position:relative;width:58px;border-radius:5px} .cd img,.cd .noimg{width:58px;height:81px;border-radius:4px;display:block;background:#0c0f14}
 .cd.have{box-shadow:0 0 0 2px var(--add)} .cd.part{box-shadow:0 0 0 2px var(--gold)} .cd.part img{filter:brightness(.82)}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.7) brightness(.6)}
 .cd .cq{position:absolute;top:1px;left:1px;background:#000c;color:#fff;font-size:9px;font-weight:700;padding:0 3px;border-radius:5px}
 .cd .cs{position:absolute;bottom:1px;right:1px;font-size:9px;font-weight:800;padding:0 3px;border-radius:5px;color:#fff}
 .cd .cs.hi{background:rgba(26,122,69,.94)} .cd .cs.mid{background:rgba(150,115,30,.94)} .cd .cs.lo{background:rgba(150,54,54,.94)}
 .cardshdr.cs-h{color:var(--gold);margin-top:11px}
 .cd .cs.opt{background:rgba(91,140,255,.95)}
 .cardshdr.op-h{color:#7fa8ff}
 .bdg.seal{background:#2a2410;color:var(--gold);font-weight:700} .bdg.wt{background:#101c2e;color:#7fa8ff;font-weight:700}
 .moxgrid{display:grid;grid-template-columns:1fr;gap:12px;margin-top:8px}
 .deck.wide{grid-column:1/-1}
 .twocol{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:2px} @media(max-width:640px){.twocol{grid-template-columns:1fr}}
 .tc{min-width:0}
 .cd.cut img{filter:grayscale(.6) brightness(.5)} .cd.cut{box-shadow:0 0 0 2px var(--warn)}
 .cd.cut::after{content:"↓";position:absolute;top:1px;right:1px;background:var(--warn);color:#160a06;font-size:10px;font-weight:800;width:14px;height:14px;line-height:14px;text-align:center;border-radius:4px}
 .cd.addc{box-shadow:0 0 0 2px var(--add)}
 .cd.addc::after{content:"+";position:absolute;top:1px;right:1px;background:var(--add);color:#08130c;font-size:11px;font-weight:800;width:14px;height:14px;line-height:14px;text-align:center;border-radius:4px}
 .swaps{display:flex;flex-direction:column;gap:3px;margin-top:6px}
 .swap{display:flex;align-items:center;gap:8px;font-size:12px;background:#0f141c;border:1px solid var(--line);border-radius:8px;padding:4px 9px}
 .swap .so{color:#ffb0a0;flex:1;min-width:0} .swap .si{color:#9fe6bf;flex:1;min-width:0;text-align:right} .swap em{color:var(--muted);font-style:normal;font-size:10px;margin-left:5px} .swap .sar{color:var(--muted)}
 .faltas.dk{margin-top:2px} .faltas.cons{margin-top:24px;border-top:1px solid var(--line);padding-top:14px}
 .flh{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:12px;font-weight:700;color:#e2795b} .flh .dim{color:var(--muted);font-weight:400} .faltas.cons .flh{font-size:15px;margin-top:0}
 .faltas ul.fl{list-style:none;margin:6px 0 0;padding:0;font-size:12px} .faltas ul.fl li{padding:1.5px 0;break-inside:avoid} .faltas ul.fl b{color:var(--gold);font-variant-numeric:tabular-nums;margin-right:2px}
 .faltas.cons ul.fl{column-width:210px;column-gap:20px;font-size:13px}
 .cpbtn{font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;border:1px solid var(--line);background:#1a2230;color:var(--muted);cursor:pointer} .cpbtn:hover{border-color:var(--accent);color:var(--ink)} .cpbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .flh .cpbtn{margin-left:auto}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎴 Decks permanentes</h1>
<div class="lead">%N% decks com link e/ou jogador vigiado · % de completo, datas, evolução e a lista completa · dados de %TODAY%</div>
%TABS%
<div class="subnav">%SUBNAV%</div></header>
%SECS%
<footer><b>Main deck</b> e <b>sideboard</b> à parte, contados por <b>cópias</b> (ex.: 68/75, não por cartas diferentes): <b style="color:var(--add)">verde = tens as que precisas</b>, <b style="color:var(--gold)">âmbar = tens algumas</b> (mostra 2/4), <b style="color:var(--warn)">vermelho = não tens</b>. Na evolução, cada carta que entrou (▲) ou saiu (▼) está verde se a tens, vermelha se não. Datas: ✅ <b>Confirmado dia</b> = última vez que o job verificou a lista · ✏️ <b>Última alteração foi</b> = última vez que a lista mudou. No <b>Cloud (Duel Commander)</b>, o <b>%</b> em cada carta é o consenso nas listas de torneio de Cloud, e <b>📊 staples que faltam</b> são as cartas de consenso alto (≥30%) que o McWinSauce não joga (verde = já as tens). A caixa <b>⇄ trocas por fazer</b> mostra, em imagem, as cartas a <b style="color:var(--add)">meter (▲)</b> e a <b style="color:var(--warn)">tirar (▼)</b> para o teu deck físico ficar igual à lista — é o <b>diff líquido</b> desde a última vez que marcaste <b>atualizado</b> (se uma carta sai e volta, ou entra e sai, não conta). Marcas atualizado quando sincronizares; volta a acumular quando a lista mudar. Atualiza diariamente.</footer>
</div>
<script>
const DECKCUR=%DECKCUR%;
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function art(sid){return sid?('https://cards.scryfall.io/small/front/'+sid[0]+'/'+sid[1]+'/'+sid+'.jpg'):'';}
function ackKey(n){return 'md_ack_'+n;}
function cimg(name,sid,cls){return sid?('<img class="chc '+cls+'" loading="lazy" src="'+art(sid)+'" title="'+esc(name)+'">'):('<span class="chc '+cls+' noi" title="'+esc(name)+'"></span>');}
function renderChg(el){
  const n=el.dataset.deck, cur=DECKCUR[n]||[];
  const box=el.querySelector('.upd'), btn=el.querySelector('.updbtn');
  if(!cur.length){if(btn)btn.style.display='none';if(box)box.innerHTML='';return;}
  const curNames=new Set(cur.map(p=>p[0]));
  // Baseline: a lista de quando marcou "atualizado". 1ª vez = assume sincronizado.
  let ack=null; try{ack=JSON.parse(localStorage.getItem(ackKey(n)));}catch(e){}
  if(!Array.isArray(ack)){try{localStorage.setItem(ackKey(n),JSON.stringify(cur));}catch(e){} ack=cur;}
  const ackNames=new Set(ack.map(p=>p[0]));
  const entra=cur.filter(p=>!ackNames.has(p[0]));   // na lista atual, não na marcada
  const saem=ack.filter(p=>!curNames.has(p[0]));    // na marcada, já não na atual
  if(!entra.length&&!saem.length){
    if(box)box.innerHTML='<div class="uok">✓ sem trocas por fazer</div>';
    if(btn){btn.textContent='✓ atualizado';btn.classList.add('done');}
    return;
  }
  let h='<div class="chgbox"><div class="chglbl">⇄ trocas por fazer (até marcares atualizado)</div><div class="chgi">'
    +'<span class="chgrp"><b class="in">▲ metes '+entra.length+'</b><span class="chc-row">'+entra.map(p=>cimg(p[0],p[1],'in')).join('')+'</span></span>'
    +'<span class="chbar"></span>'
    +'<span class="chgrp"><b class="out">▼ tiras '+saem.length+'</b><span class="chc-row">'+saem.map(p=>cimg(p[0],p[1],'out')).join('')+'</span></span>'
    +'</div></div>';
  if(box)box.innerHTML=h;
  if(btn){btn.textContent='marcar atualizado';btn.classList.remove('done');}
}
function markUpd(btn){
  const el=btn.closest('.deck'),n=el.dataset.deck;
  try{localStorage.setItem(ackKey(n),JSON.stringify(DECKCUR[n]||[]));}catch(e){}
  renderChg(el);
}
function cpFaltas(btn){
  const c=btn.closest('.faltas'); const t=c&&c.querySelector('textarea.cmk'); if(!t)return;
  const done=()=>{btn.textContent='✓ copiado';btn.classList.add('done');};
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(t.value).then(done).catch(()=>{t.select();document.execCommand('copy');done();});
  }else{t.select();try{document.execCommand('copy');done();}catch(e){}}
}
document.querySelectorAll('.deck[data-deck]').forEach(renderChg);
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("meusdecks.html:", build(con))


if __name__ == "__main__":
    main()
