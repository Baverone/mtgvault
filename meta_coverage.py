"""Cobertura do metagame: os top decks de cada formato, quanto já tenho de cada
um (% completo) e o que falta comprar — com a IMAGEM de cada carta em falta.

Lê o que o job diário já produziu — arquétipos agrupados (`archetypes`) e a
análise de núcleo (`card_roles`) — e cruza com a coleção (`owned_playable`).
NÃO vai à net nem inventa listas: usa só o núcleo (as cartas que se levam
sempre) de cada arquétipo, calculado a partir das decklists reais recolhidas.

Ideia (pedido do André): em vez de eu dizer que decks tenho, o vault mostra-me
os melhores decks do momento e o estado da minha coleção para cada um. As
cartas que faltam em VÁRIOS dos decks mostrados juntam-se numa lista geral
(staples partilhados); em cada deck ficam só as específicas dele.

Imagem da carta em falta (crucial p/ saber que edição comprar):
  - se já tenho algumas (ex.: tenho 3, faltam 1), mostro a EDIÇÃO QUE POSSUO,
    para comprar igual;
  - se não tenho nenhuma, mostro a impressão legal mais barata (a do preço).
Impressões não jogáveis (gold-border World Championship, Collectors'/Intl.
Edition, digitais) ficam de fora dos preços e das sugestões.

Uso:  python meta_coverage.py   ->  escreve cobertura.html na raiz do repositório.
"""
from __future__ import annotations

import html
import json
import os
import urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db  # noqa: E402
from mtgvault.collection import owned_playable  # noqa: E402

FORMATS = [
    ("standard", "Standard", 10, []),
    ("pioneer", "Pioneer", 10, ["__greasefang__"]),
    ("modern", "Modern", 10, []),
    # Legacy esquecido por agora (André, 2026-08-31): fora do metagame/decks-fazíveis.
    ("premodern", "Premodern", 10, []),
]

# A COLEÇÃO disponível para montar decks do metagame = só estes baldes. Os baldes
# dos decks vigiados (Blue Farm, Cloud, Cloud cEDH, Pauper Affinity) estão agregados
# a esses decks e NÃO contam como disponíveis (regra do André, 2026-08-26).
COLLECTION_BALDES = {"SPML", "Premodern (geral)"}


def _committed_to_watched(con):
    """Cartas (nome->qty) comprometidas com decks vigiados que VIVEM na coleção.
    Os decks vigiados de Commander/Pauper têm balde próprio (já fora de
    COLLECTION_BALDES); só o(s) de Premodern (Stiflenought-Luffy) têm as cartas no
    balde Premodern (geral) — essas subtraem-se aqui para deixarem de estar
    disponíveis (regra do André: todas as cartas dos decks vigiados pertencem ao
    deck e saem da coleção)."""
    import json
    try:
        vig = json.loads((ROOT / "colecao_config.json").read_text(encoding="utf-8")).get("decks_vigiados") or []
    except Exception:
        vig = []
    if not vig:
        return {}
    ph = ",".join("?" * len(vig))
    comm = {}
    for r in con.execute(
            f"""SELECT dc.card_name nm, SUM(dc.quantity) q FROM deck_cards dc
                 JOIN decks d ON d.id = dc.deck_id
                WHERE d.format = 'premodern' AND d.name IN ({ph})
                GROUP BY dc.card_name""", vig):
        comm[r["nm"].split(" // ")[0]] = (comm.get(r["nm"].split(" // ")[0], 0) + (r["q"] or 0))
    return comm


def owned_available(con):
    """Cartas DISPONÍVEIS na coleção (SPML + Premodern) para montar decks do
    metagame, como {nome: qty_livre} — já sem as comprometidas com os decks
    vigiados. metagame/decks-fazíveis fazem set(...) para os nomes; a cobertura usa
    as quantidades."""
    col = owned_playable(con, baldes=COLLECTION_BALDES)
    comm = _committed_to_watched(con)
    return {nm: q - comm.get(nm, 0) for nm, q in col.items() if q > comm.get(nm, 0)}

# Ponderação por importância do torneio MTGO (pesos confirmados pelo André,
# 2026-08-14), numa janela recente. `placement` está vazio nos dados, por isso
# não entra ainda. Reutilizado no ranking e na deteção de decks emergentes.
RECENT_DAYS = 30
# Regra do André (2026-08-26): o metagame conta SÓ Challenges e Showcases, e os
# Showcases pesam mais. Os restantes tiers ficam com peso 0 (e são filtrados no
# _rank/emerging, por isso nem entram).
_TIER_WEIGHT = """CASE
        WHEN d.event_tier = 'Showcase' THEN 3
        WHEN d.event_tier = 'Challenge' THEN 1
        ELSE 0 END"""

BASICS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
    "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes",
}

NICE = {"__greasefang__": "Greasefang"}

# quantos staples partilhados mostrar no topo (o resto vê-se em cada deck)
GENERAL_MAX = 24

# Mapa de arquétipos conhecidos: carta-assinatura distintiva -> nome do deck.
# Aplica-se quando o núcleo (mainboard) contém a assinatura; ordem = prioridade
# (primeira que bate ganha). São nomes reais de arquétipos, não invenção — só se
# usam cartas que essencialmente só aquele deck joga, para não rotular mal.
KNOWN = [
    ("Greasefang, Okiba Boss", "Greasefang"),
    ("Goryo's Vengeance", "Goryo's Reanimator"),
    ("Doomsday", "Doomsday"),
    ("Sneak Attack", "Sneak & Show"),
    ("Show and Tell", "Sneak & Show"),
    ("Nadu, Winged Wisdom", "Nadu"),
    ("Murktide Regent", "Murktide"),
    ("Death's Shadow", "Death's Shadow"),
    ("Muxus, Goblin Grandee", "Goblins"),
    ("Goblin Warchief", "Goblins"),
    ("Goblin Piledriver", "Goblins"),
    ("Goblin Lackey", "Goblins"),
    ("Allosaurus Shepherd", "Elves"),
    ("Heritage Druid", "Elves"),
    ("Elvish Archdruid", "Elves"),
    ("Cephalid Illusionist", "Cephalid Breakfast"),
    ("Living End", "Living End"),
    ("Crashing Footfalls", "Crashing Footfalls"),
    ("Amulet of Vigor", "Amulet Titan"),
    ("Scapeshift", "Scapeshift"),
    ("Urza's Tower", "Tron"),
    ("Painter's Servant", "Painter"),
    ("Yawgmoth, Thran Physician", "Yawgmoth"),
    ("Underworld Breach", "Breach"),
    ("Aluren", "Aluren"),
    ("Thespian's Stage", "Dark Depths"),
    ("Dark Depths", "Dark Depths"),
    # premodern
    ("Replenish", "Replenish"),
    ("Sterling Grove", "Enchantress"),
    ("Argothian Enchantress", "Enchantress"),
    ("Oath of Druids", "Oath"),
    ("Survival of the Fittest", "Survival"),
    ("Standstill", "Landstill"),
    ("Illusions of Grandeur", "Donate"),
    ("Phyrexian Dreadnought", "Stiflenought"),
    ("Ill-Gotten Gains", "Ill-Gotten Gains"),
    ("Reanimate", "Reanimator"),
    ("Griselbrand", "Reanimator"),
    # standard — nomes reais aprendidos do mtggoldfish (evento 2026-08-01), só as
    # cartas que essencialmente definem cada deck (a "sopa Izzet" e os controlos
    # não se separam de forma fiável no clustering, por isso ficam de fora).
    ("Earthbender Ascension", "Landfall (Verde)"),
    ("Brightglass Gearhulk", "Selesnya Gearhulk"),
    ("Bringer of the Last Gift", "Reanimator"),
    ("Amalia Benavides Aguirre", "Amalia Combo"),
]

# impressões que NÃO se jogam em torneio — fora dos preços e das sugestões de compra
_NOT_PLAYABLE = (
    "AND c.digital = 0 "
    "AND c.set_name NOT LIKE '%World Championship%' "
    "AND c.set_name NOT LIKE '%Collector%Edition%' "
    "AND c.set_name NOT LIKE '%International Edition%' "
    "AND c.set_name NOT LIKE '%Oversized%' "
)


def _thumb(uri):
    """Miniatura pequena da Scryfall a partir do image_uri 'normal'."""
    return uri.replace("/normal/", "/small/") if uri else ""


def _visual(con, name, owned_qty):
    """Que imagem/edição/preço mostrar para uma carta em falta.

    owned_qty>0  -> a edição que o André mais possui (para comprar igual).
    owned_qty==0 -> a impressão jogável mais barata (a que dita o preço).
    """
    if owned_qty > 0:
        r = con.execute(
            """SELECT c.set_code, c.set_name, c.image_uri, cp.finish,
                      SUM(cp.quantity) q,
                      (SELECT p.trend FROM price_latest p
                        WHERE p.scryfall_id = c.scryfall_id AND p.source = 'cardmarket'
                          AND p.finish = cp.finish) AS trend
                 FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.purpose = 'player'
                GROUP BY c.scryfall_id ORDER BY q DESC LIMIT 1""", (name,)).fetchone()
        if r:
            return {"img": _thumb(r["image_uri"]), "set_code": r["set_code"],
                    "set_name": r["set_name"], "unit": r["trend"], "mine": True}

    r = con.execute(
        f"""SELECT c.set_code, c.set_name, c.image_uri, p.trend
              FROM cards c JOIN price_latest p ON p.scryfall_id = c.scryfall_id
             WHERE c.name = ? AND p.source = 'cardmarket' AND p.finish = 'nonfoil'
               AND c.lang = 'en' {_NOT_PLAYABLE}
             ORDER BY p.trend ASC LIMIT 1""", (name,)).fetchone()
    if r:
        return {"img": _thumb(r["image_uri"]), "set_code": r["set_code"],
                "set_name": r["set_name"], "unit": r["trend"], "mine": False}
    # sem preço: pelo menos uma imagem jogável recente
    r = con.execute(
        f"""SELECT set_code, set_name, image_uri FROM cards c
             WHERE c.name = ? AND c.lang = 'en' {_NOT_PLAYABLE}
             ORDER BY released_at DESC LIMIT 1""", (name,)).fetchone()
    if r:
        return {"img": _thumb(r["image_uri"]), "set_code": r["set_code"],
                "set_name": r["set_name"], "unit": None, "mine": False}
    return {"img": "", "set_code": "", "set_name": "", "unit": None, "mine": False}


def _owned_sid(con, name):
    """A impressão que o André mais possui desta carta (para ser a opção por omissão)."""
    r = con.execute(
        "SELECT c.scryfall_id sid FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id "
        "WHERE c.name = ? AND cp.purpose = 'player' GROUP BY c.scryfall_id "
        "ORDER BY SUM(cp.quantity) DESC LIMIT 1", (name,)).fetchone()
    return r["sid"] if r else None


def _playable_printings(con, name, limit=14):
    """Impressões jogáveis (en, sem gold-border/digitais) ordenadas por preço.
    Cada uma: {s: scryfall_id, n: nome do set, p: preço}. A imagem constrói-se
    no cliente a partir do id (poupa embeber URLs longos)."""
    rows = con.execute(
        f"""SELECT c.scryfall_id sid, c.set_name,
                   (SELECT p.trend FROM price_latest p WHERE p.scryfall_id = c.scryfall_id
                     AND p.source = 'cardmarket' AND p.finish = 'nonfoil') price
              FROM cards c WHERE c.name = ? AND c.lang = 'en' {_NOT_PLAYABLE}""", (name,)).fetchall()
    out = [{"s": r["sid"], "n": r["set_name"], "p": r["price"]} for r in rows]
    out.sort(key=lambda p: (p["p"] is None, p["p"] or 0))
    return out[:limit]


def _prints_for(con, name, owned):
    """Opções de edição a mostrar no seletor: as jogáveis + a que já tens (mesmo
    que não seja das mais baratas), marcada com m=1."""
    lst = _playable_printings(con, name)
    osid = _owned_sid(con, name) if owned.get(name, 0) else None
    if osid and not any(p["s"] == osid for p in lst):
        r = con.execute(
            "SELECT c.scryfall_id sid, c.set_name, (SELECT p.trend FROM price_latest p "
            "WHERE p.scryfall_id = c.scryfall_id AND p.source = 'cardmarket' AND p.finish = 'nonfoil') price "
            "FROM cards c WHERE c.scryfall_id = ?", (osid,)).fetchone()
        if r:
            lst.insert(0, {"s": r["sid"], "n": r["set_name"], "p": r["price"]})
    for p in lst:
        p["m"] = 1 if (osid and p["s"] == osid) else 0
    return lst


def _greasefang_id(con):
    r = con.execute(
        """SELECT a.id, COUNT(d.id) n FROM archetypes a
             JOIN decklists d ON d.archetype_id = a.id
            WHERE a.format = 'pioneer' AND a.id IN (
                  SELECT DISTINCT archetype_id FROM card_roles
                   WHERE card_name LIKE 'Greasefang%' AND core_copies >= 1)
            GROUP BY a.id ORDER BY n DESC LIMIT 1""").fetchone()
    return r["id"] if r else None


def _rank(con, fmt, n):
    """Top-n arquétipos do formato, PONDERADOS pela importância do torneio numa
    janela recente. Devolve [(id, score)] por ordem decrescente de peso."""
    return [(r["id"], round(r["score"], 1)) for r in con.execute(
        f"""SELECT a.id, SUM({_TIER_WEIGHT}) score FROM archetypes a
             JOIN decklists d ON d.archetype_id = a.id
            WHERE a.format = ? AND d.event_date >= date('now', '-{RECENT_DAYS} days')
              AND d.event_tier IN ('Challenge','Showcase')
            GROUP BY a.id ORDER BY score DESC, COUNT(d.id) DESC LIMIT ?""", (fmt, n))]


# Só Challenges e Showcases contam (regra do André, 2026-08-26). Emergente =
# aparece em Challenges/Showcases mas fica fora do top-10.
HIGH_TIERS = ("Challenge", "Showcase")


def emerging_decks(con):
    """Decks que aparecem em torneios de PESO mas ficam FORA do top-10 do formato
    — possíveis decks novos a surgir. Por formato, os de maior peso (mín. 2
    aparições para cortar ruído de um resultado isolado)."""
    tcache = {}
    out = []
    marks = ",".join("?" for _ in HIGH_TIERS)
    for fmt, _title, n, _extras in FORMATS:
        df = _format_df(con, fmt)
        ranked = _rank(con, fmt, n)
        top = {aid for aid, _ in ranked}
        # nomes já no top-10 (o clustering às vezes parte um deck em 2 ids com o
        # mesmo nome — não é "emergente" se já lá está por outro cluster).
        top_names = {_name_for(con, aid, df, tcache) for aid, _ in ranked}
        seen_names = set()
        found = []
        for r in con.execute(
            f"""SELECT a.id, SUM({_TIER_WEIGHT}) score, COUNT(DISTINCT d.id) nlists,
                       MAX(d.event_name) ev
                  FROM archetypes a JOIN decklists d ON d.archetype_id = a.id
                 WHERE a.format = ? AND d.event_date >= date('now', '-{RECENT_DAYS} days')
                   AND d.event_tier IN ({marks})
                 GROUP BY a.id HAVING nlists >= 2
                 ORDER BY score DESC""", (fmt, *HIGH_TIERS)):
            if r["id"] in top:
                continue
            name = _name_for(con, r["id"], df, tcache)
            if name in seen_names or name in top_names:
                continue
            seen_names.add(name)
            url = con.execute("SELECT url FROM decklists WHERE archetype_id = ? "
                              "ORDER BY event_date DESC, id DESC LIMIT 1", (r["id"],)).fetchone()
            found.append({"fmt": fmt, "aid": r["id"], "name": name, "score": round(r["score"], 1),
                          "nlists": r["nlists"], "ev": r["ev"], "url": url["url"] if url else None})
            if len(found) >= 3:
                break
        out += found
    return out


def _label(con, aid):
    r = con.execute("SELECT label FROM archetypes WHERE id = ?", (aid,)).fetchone()
    return r["label"] if r else f"#{aid}"


def _n_lists(con, aid):
    return con.execute("SELECT COUNT(*) c FROM decklists WHERE archetype_id = ?",
                       (aid,)).fetchone()["c"]


def _format_df(con, fmt):
    """Quantos arquétipos do formato jogam cada carta no núcleo (mainboard).
    Serve para medir distintividade: carta rara entre decks = carta que dá nome."""
    return {r["card_name"]: r["df"] for r in con.execute(
        """SELECT cr.card_name, COUNT(DISTINCT cr.archetype_id) df
             FROM card_roles cr JOIN archetypes a ON a.id = cr.archetype_id
            WHERE a.format = ? AND cr.board = 'main' AND cr.core_copies >= 1
              AND cr.window_end = (SELECT MAX(w.window_end) FROM card_roles w
                                    WHERE w.archetype_id = cr.archetype_id)
            GROUP BY cr.card_name""", (fmt,))}


def _type_boost(con, name, cache):
    """Os decks costumam ter o nome do payoff (criatura/planeswalker lendário),
    não do removal. Dá peso a esses tipos na escolha do nome."""
    t = cache.get(name)
    if t is None:
        row = con.execute("SELECT type_line FROM cards WHERE name = ? LIMIT 1", (name,)).fetchone()
        t = (row["type_line"] or "") if row else ""
        cache[name] = t
    if "Planeswalker" in t:
        return 2.2
    if "Creature" in t:
        return 1.6 if "Legendary" in t else 1.3
    return 1.0


def _distinctive_name(con, aid, df, tcache):
    """Nome do deck = as cartas do núcleo mais distintivas (raras noutros decks),
    com preferência pelo payoff. Melhor que a label crua do clustering."""
    best = []
    for r in _core_rows(con, aid, "main"):
        n = r["card_name"]
        if n in BASICS or r["inclusion_rate"] < 0.5:
            continue
        score = r["inclusion_rate"] / df.get(n, 1) * _type_boost(con, n, tcache)
        best.append((score, r["inclusion_rate"], n))
    best.sort(reverse=True)
    top = [n for _, _, n in best[:2]]
    return " / ".join(top) if top else f"#{aid}"


def _known_name(con, aid):
    """Nome de arquétipo conhecido, se o núcleo tiver uma carta-assinatura."""
    core = {r["card_name"] for r in _core_rows(con, aid, "main")}
    for sig, nm in KNOWN:
        if sig in core:
            return nm
    return None


def _name_for(con, aid, df, tcache):
    return _known_name(con, aid) or _distinctive_name(con, aid, df, tcache)


def _core_rows(con, aid, board="main"):
    return con.execute(
        """SELECT card_name, core_copies, inclusion_rate FROM card_roles
             WHERE archetype_id = ? AND board = ? AND core_copies >= 1
               AND window_end = (SELECT MAX(window_end) FROM card_roles WHERE archetype_id = ?)
            ORDER BY inclusion_rate DESC, core_copies DESC""", (aid, board, aid)).fetchall()


def _sideboard(con, aid, owned, limit=15):
    """Sideboard de consenso: as cartas de SB que o metagame mais joga neste
    arquétipo (por inclusão). Marca as que já tens. É o 'o que deves ter no SB' —
    não é um guia de matchups (esses vêm de fora, ver o link 'procurar guia')."""
    out = []
    for r in con.execute(
        """SELECT card_name, avg_copies, core_copies, inclusion_rate FROM card_roles
             WHERE archetype_id = ? AND board = 'side'
               AND window_end = (SELECT MAX(window_end) FROM card_roles WHERE archetype_id = ?)
             ORDER BY inclusion_rate DESC, avg_copies DESC LIMIT ?""", (aid, aid, limit)):
        if r["card_name"] in BASICS:
            continue
        out.append({"name": r["card_name"],
                    "qty": max(1, round(r["avg_copies"] or r["core_copies"] or 1)),
                    "incl": round(100 * (r["inclusion_rate"] or 0)),
                    "have": owned.get(r["card_name"], 0)})
    return out


def deck_coverage(con, aid, owned, name):
    """% do núcleo (mainboard + sideboard de consenso) que já tenho, e o que
    falta. Ignora básicas. Uma cópia só conta uma vez (main tem prioridade
    sobre side), para não sobrecontar quando a carta está nos dois quadros."""
    total = have = 0
    missing = []
    used = {}
    for board in ("main", "side"):
        for r in _core_rows(con, aid, board):
            nm = r["card_name"]
            if nm in BASICS:
                continue
            need = r["core_copies"]
            avail = owned.get(nm, 0) - used.get(nm, 0)
            got = max(0, min(need, avail))
            used[nm] = used.get(nm, 0) + got
            total += need
            have += got
            if got < need:
                v = _visual(con, nm, owned.get(nm, 0))
                missing.append({"name": nm, "board": board, "need": need, "have": got,
                                "missing": need - got, "unit": v["unit"],
                                "cost": round((v["unit"] or 0) * (need - got), 2),
                                "img": v["img"], "set_name": v["set_name"], "mine": v["mine"]})
    pct = round(100 * have / total) if total else 0
    return {"id": aid, "name": name, "label": _label(con, aid),
            "n_lists": _n_lists(con, aid), "core_total": total, "have": have, "pct": pct,
            "missing": sorted(missing, key=lambda m: -(m["cost"] or 0)),
            "sideboard": _sideboard(con, aid, owned)}


def build_report(con):
    owned = owned_available(con)   # só a coleção, SEM as cartas comprometidas com decks vigiados
    gid = _greasefang_id(con)
    tcache = {}
    sections, all_decks = [], []
    for fmt, title, n, extras in FORMATS:
        df = _format_df(con, fmt)
        ranked = _rank(con, fmt, n)
        score = {aid: s for aid, s in ranked}
        ids = [aid for aid, _ in ranked]
        for ex in extras:
            aid = gid if ex == "__greasefang__" else ex
            if aid and aid not in ids:
                ids.append(aid)
                score.setdefault(aid, 0)
        decks = []
        for aid in ids:
            nm = _name_for(con, aid, df, tcache)
            d = deck_coverage(con, aid, owned, nm)
            d["score"] = score.get(aid, 0)
            decks.append(d)
        decks.sort(key=lambda d: -d["score"])
        sections.append({"fmt": fmt, "title": title, "decks": decks})
        all_decks += decks

    seen = defaultdict(list)
    for d in all_decks:
        for m in d["missing"]:
            seen[m["name"]].append(m)
    general, shared = [], set()
    for name, occ in seen.items():
        if len(occ) >= 2:
            shared.add(name)
            base = occ[0]
            general.append({"name": name, "need": max(m["missing"] for m in occ),
                            "unit": base["unit"], "img": base["img"],
                            "set_name": base["set_name"], "mine": base["mine"],
                            "have": owned.get(name, 0), "n_decks": len(occ),
                            "cost": round((base["unit"] or 0) * max(m["missing"] for m in occ), 2)})
    general.sort(key=lambda g: (-g["n_decks"], -(g["cost"] or 0)))
    for d in all_decks:
        d["specific"] = [m for m in d["missing"] if m["name"] not in shared]
        d["spec_cost"] = round(sum(m["cost"] or 0 for m in d["specific"]), 2)

    # opções de edição por carta (para o seletor de compra no cliente)
    names = {m["name"] for d in all_decks for m in d["missing"]}
    prints = {nm: _prints_for(con, nm, owned) for nm in names}
    # wantlist completa de cada deck (com staples partilhados) para exportar
    want = {d["id"]: [[m["name"], m["missing"]] for m in d["missing"]] for d in all_decks}
    return {"sections": sections, "general": general, "prints": prints, "want": want,
            "owned_total": sum(owned.values()), "emerging": emerging_decks(con),
            "general_cost": round(sum(g["cost"] or 0 for g in general), 2)}


# --- HTML ------------------------------------------------------------------
def _eur(v):
    return f"{v:,.2f} €".replace(",", " ") if v else "—"


def _bar(pct):
    col = "var(--add)" if pct >= 80 else "var(--gold)" if pct >= 45 else "var(--warn)"
    return (f'<div class="bar"><span style="width:{pct}%;background:{col}"></span>'
            f'<em>{pct}%</em></div>')


def _img_tag(uri):
    return (f'<img class="th" loading="lazy" src="{html.escape(uri)}" alt="" width="42" height="59">'
            if uri else '<div class="noimg th"></div>')


def _edition(mine, have, set_name):
    if not set_name:
        return ""
    if mine:
        return f'<span class="ed mine">tens {have} · {html.escape(set_name)}</span>'
    return f'<span class="ed">+ barata: {html.escape(set_name)}</span>'


def _li(name, qty, have, thumb_img, price_html, cn_inner, unit, mine, set_name):
    """Uma linha de carta em falta. `.ed-slot` leva a edição por omissão (fallback
    sem JS); o cliente substitui-a por um seletor de edição."""
    ecard = html.escape(name, quote=True)
    unit_attr = "" if unit is None else f' data-unit="{unit}"'
    return (f'<li data-card="{ecard}" data-qty="{qty}" data-have="{have}"{unit_attr}>'
            f'{thumb_img}<div class="ci"><div class="cn">{cn_inner}</div>'
            f'<div class="ed-slot">{_edition(mine, have, set_name)}</div></div>'
            f'<span class="pz">{price_html}</span></li>')


def _card_item(m):
    price = _eur(m["cost"]) if m.get("unit") is not None else "<i>preço?</i>"
    sb = ' <span class="sb">SB</span>' if m.get("board") == "side" else ""
    cn = f'<b>{m["missing"]}×</b> {html.escape(m["name"])}{sb}'
    return _li(m["name"], m["missing"], m.get("have", 0), _img_tag(m.get("img")), price, cn,
               m.get("unit"), m.get("mine"), m.get("set_name"))


def _gen_item(g):
    price = _eur(g["cost"]) if g.get("unit") is not None else "<i>?</i>"
    cn = (f'<b>{g["need"]}×</b> {html.escape(g["name"])} '
          f'<span class="nd">{g["n_decks"]} decks</span>')
    return _li(g["name"], g["need"], g.get("have", 0), _img_tag(g.get("img")), price, cn,
               g.get("unit"), g.get("mine"), g.get("set_name"))


def build_html(rep, today):
    secs = ""
    for s in rep["sections"]:
        cards = ""
        for d in s["decks"]:
            spec = d["specific"]
            if spec:
                aid = d["id"]
                body = (f'<details><summary>{sum(m["missing"] for m in spec)} cartas específicas '
                        f'· <b id="spec-{aid}">{_eur(d["spec_cost"])}</b></summary>'
                        f'<ul class="ml" data-sum="spec-{aid}">'
                        + "".join(_card_item(m) for m in spec) + '</ul></details>')
            else:
                body = '<div class="ok">sem cartas específicas em falta ✓</div>'
            guide = ("https://www.google.com/search?q="
                     + urllib.parse.quote(f'MTG {d["name"]} {s["fmt"]} sideboard guide'))
            glink = f'<a href="{guide}" target="_blank" rel="noopener">🔎 procurar guia de sideboard ↗</a>'
            sb = d.get("sideboard") or []
            if sb:
                sbli = ""
                for x in sb:
                    mark = ' <span class="own2">✓ tens</span>' if x["have"] else ""
                    sbli += (f'<li><span class="si">{x["incl"]}%</span> <b>{x["qty"]}×</b> '
                             f'{html.escape(x["name"])}{mark}</li>')
                sbblock = (f'<details class="sbd"><summary>🛡️ Sideboard típico ({len(sb)})</summary>'
                           f'<div class="sbg">{glink}</div><ul class="sl">{sbli}</ul></details>')
            else:
                sbblock = f'<div class="sbg">{glink}</div>'
            copybtn = (f'<button class="cp" data-deck="{d["id"]}">📋 copiar wantlist</button>'
                       if d["missing"] else "")
            cards += (
                f'<div class="deck"><div class="dh"><div class="dn">{html.escape(d["name"])}'
                f'<span class="lab">{html.escape(d["label"])[:60]}</span></div>'
                f'<div class="pop" title="peso por importância de torneio (últimos '
                f'{RECENT_DAYS} dias)">⚖️ {d.get("score", 0)} · {d["n_lists"]} listas</div></div>{_bar(d["pct"])}'
                f'<div class="cnt">{d["have"]}/{d["core_total"]} do núcleo · '
                f'faltam {sum(m["missing"] for m in d["missing"])}</div>{body}{copybtn}{sbblock}</div>')
        secs += f'<section><h2>{s["title"]}</h2><div class="grid">{cards}</div></section>'

    shown = rep["general"][:GENERAL_MAX]
    gen = "".join(_gen_item(g) for g in shown)
    shown_cost = round(sum(g["cost"] or 0 for g in shown), 2)
    extra = len(rep["general"]) - len(shown)
    more = (f'<div class="dim" style="padding-top:8px">+ {extra} staples partilhados menores '
            f'(preço baixo) — vê cada deck para os detalhes</div>' if extra > 0 else "")

    ft = {f[0]: f[1] for f in FORMATS}
    em = rep.get("emerging") or []
    emerging_html = ""
    if em:
        rows = "".join(
            f'<li><span class="ef">{html.escape(ft.get(e["fmt"], e["fmt"]))}</span> '
            f'<b>{html.escape(e["name"])}</b> <span class="dim">⚖️ {e["score"]} · '
            f'{e["nlists"]} listas de peso · {html.escape(e["ev"] or "")}</span></li>'
            for e in em)
        emerging_html = ('<section class="emerging"><h2>🌱 Decks a emergir '
                         '<span class="dim">(fora do top-10, mas em torneios de peso — talvez algo novo)</span>'
                         f'</h2><ul class="eml">{rows}</ul></section>')

    return (_TMPL.replace("%SECS%", secs).replace("%EMERGING%", emerging_html)
            .replace("%GEN%", gen or "<li class='dim'>—</li>")
            .replace("%GENMORE%", more).replace("%TODAY%", today)
            .replace("%OWNED%", str(rep["owned_total"]))
            .replace("%GENSHOWN%", _eur(shown_cost))
            .replace("%GENCOST%", _eur(rep["general_cost"]))
            .replace("%PRINTS%", json.dumps(rep["prints"], ensure_ascii=False))
            .replace("%WANT%", json.dumps(rep["want"], ensure_ascii=False)))


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mtgvault — cobertura do metagame</title><style>
 :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#93a0ad;--line:#262c36;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e8794b}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1120px;margin:0 auto;padding:24px 16px 70px}
 h1{margin:0 0 2px;font-size:22px} .sub{color:var(--muted);font-size:13px;margin-bottom:8px} .sub a{color:var(--accent)}
 h2{font-size:16px;margin:26px 0 6px;padding-bottom:6px;border-bottom:1px solid var(--line)}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
 .dh{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
 .dn{font-weight:700} .lab{display:block;color:var(--muted);font-size:11px;font-weight:400;margin-top:1px}
 .pop{color:var(--muted);font-size:12px;white-space:nowrap;font-variant-numeric:tabular-nums}
 .bar{position:relative;height:16px;background:#0c0f14;border:1px solid var(--line);border-radius:999px;margin:9px 0 6px;overflow:hidden}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px} .bar em{position:absolute;right:8px;top:-1px;font-size:11px;font-style:normal;font-weight:700;mix-blend-mode:difference}
 .cnt{color:var(--muted);font-size:12px;margin-bottom:6px}
 details summary{cursor:pointer;color:var(--accent);font-size:13px} .ok{color:var(--add);font-size:13px}
 ul.ml,ul.gl{list-style:none;margin:8px 0 0;padding:0;font-size:13px}
 ul.ml li,ul.gl li{display:flex;align-items:center;gap:8px;padding:4px 0;border-top:1px solid var(--line)}
 ul.gl li:first-child{border-top:0}
 ul.ml img,ul.gl img,.noimg{border-radius:4px;flex:none;background:#0c0f14} .noimg{width:42px;height:59px;border:1px dashed var(--line)}
 .ci{min-width:0;flex:1} .cn{white-space:normal} .cn b{color:var(--ink)}
 .ed{display:block;font-size:11px;color:var(--muted)} .ed.mine{color:var(--add)}
 .nd{display:inline-block;font-size:11px;color:var(--accent);background:#12203f;padding:0 6px;border-radius:999px}
 .sb{font-size:10px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 4px;vertical-align:middle}
 .pz{margin-left:auto;color:var(--gold);font-variant-numeric:tabular-nums;white-space:nowrap;align-self:flex-start;padding-top:2px}
 .own{color:var(--add);font-size:11px} .ed-slot{margin-top:2px;display:flex;align-items:center;gap:4px;flex-wrap:wrap}
 select.pick{max-width:100%;background:#0c0f14;color:var(--ink);border:1px solid var(--line);border-radius:6px;font-size:11px;padding:2px 4px;cursor:pointer}
 .sbd{margin-top:8px} .sbd>summary{color:var(--muted);cursor:pointer;font-size:12px} .sbg{margin:6px 0} .sbg a{color:var(--accent);font-size:12px;text-decoration:none}
 ul.sl{list-style:none;margin:6px 0 0;padding:0;font-size:12px} ul.sl li{padding:2px 0} .si{display:inline-block;width:36px;color:var(--muted);font-variant-numeric:tabular-nums} .own2{color:var(--add);font-size:11px}
 button.cp{background:#12203f;color:var(--accent);border:1px solid var(--line);border-radius:8px;font-size:12px;padding:5px 10px;cursor:pointer;margin-top:8px} button.cp:hover{border-color:var(--accent)}
 .general{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:8px}
 .general h2{margin-top:0;border:0} .dim{color:var(--muted);font-size:12px}
 .emerging{background:#141b12;border:1px solid #2c3a1f;border-radius:12px;padding:12px 16px;margin-top:8px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0} .tabs a{flex:1;min-width:110px;text-align:center;padding:11px 8px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s} .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)} .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 .emerging h2{margin:0 0 6px;border:0;font-size:15px} .eml{list-style:none;margin:0;padding:0}
 .eml li{padding:4px 0;border-top:1px solid #2c3a1f} .eml li:first-child{border-top:0}
 .ef{display:inline-block;min-width:74px;color:var(--add);font-size:11px;text-transform:uppercase}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🌐 Metagame</h1>
<div class="sub">Os melhores decks de cada formato e quanto já tens · %OWNED% cartas na coleção · dados de %TODAY%</div>
<nav class="tabs"><a href="index.html">🏠 Início</a><a href="meusdecks.html">🎴 Decks permanentes</a><a href="colecao_cor.html">📚 Coleção</a><a href="caixarl.html">📦 Caixa RL</a></nav></header>
%EMERGING%
<div class="general"><h2>🛒 Staples que te faltam <span class="dim">(servem vários dos decks abaixo · mostrados <b id="gen-shown">%GENSHOWN%</b> de %GENCOST%)</span></h2>
<div><button id="copyall" class="cp">📋 Copiar wantlist completa (Cardmarket)</button></div>
<ul class="gl" data-sum="gen-shown">%GEN%</ul>%GENMORE%</div>
%SECS%
<footer>% completo = cartas do núcleo (mainboard + sideboard de consenso, sem terras básicas) que já tens, sobre o total do núcleo do arquétipo — o que as decklists reais levam quase sempre; cartas <span class="sb">SB</span> são de sideboard. Cada carta em falta mostra a imagem da edição a comprar: a que já tens (verde) se tiveres algumas, senão a impressão jogável mais barata. Preços: tendência Cardmarket (sem gold-border/digitais). O nome do deck vem das cartas mais distintivas do arquétipo (a label crua do clustering fica por baixo). "Específicas" de um deck = as que mais nenhum deck mostrado precisa; as partilhadas estão nos staples do topo. Podes escolher a edição de cada carta no seletor — a escolha fica guardada neste dispositivo.</footer>
</div>
<script>
var PRINT=%PRINTS%;
var WANT=%WANT%;
function cimg(s){return 'https://cards.scryfall.io/small/front/'+s[0]+'/'+s[1]+'/'+s+'.jpg';}
function ceur(v){return (v==null)?'preço?':(v.toFixed(2).replace('.',',')+' €');}
function ckey(n){return 'ed:'+n;}
function capply(li){
  var n=li.dataset.card,sel=li.querySelector('select.pick');if(!sel)return;
  var p=(PRINT[n]||[])[sel.value];if(!p)return;
  var q=+li.dataset.qty,im=li.querySelector('.th');
  if(im&&im.tagName==='IMG')im.src=cimg(p.s);
  li.dataset.unit=(p.p==null?'':p.p);
  var pz=li.querySelector('.pz');if(pz)pz.textContent=(p.p==null?'preço?':ceur(p.p*q));
}
function crecompute(){
  document.querySelectorAll('[data-sum]').forEach(function(box){
    var t=0;box.querySelectorAll('li[data-card]').forEach(function(li){
      var u=parseFloat(li.dataset.unit);if(!isNaN(u))t+=u*(+li.dataset.qty);});
    var out=document.getElementById(box.dataset.sum);if(out)out.textContent=ceur(t);});
}
document.querySelectorAll('li[data-card]').forEach(function(li){
  var n=li.dataset.card,prints=PRINT[n]||[];if(!prints.length)return;
  var sel=document.createElement('select');sel.className='pick';
  prints.forEach(function(p,i){var o=document.createElement('option');o.value=i;
    o.textContent=p.n+(p.p==null?' — s/preço':' — '+ceur(p.p))+(p.m?' ✓ tens':'');sel.appendChild(o);});
  var idx=-1,saved=localStorage.getItem(ckey(n));
  if(saved){for(var i=0;i<prints.length;i++){if(prints[i].s===saved){idx=i;break;}}}
  if(idx<0){for(var j=0;j<prints.length;j++){if(prints[j].m){idx=j;break;}}}
  if(idx<0)idx=0;
  sel.value=idx;
  var slot=li.querySelector('.ed-slot');
  if(slot){slot.innerHTML='';var hv=+li.dataset.have;
    if(hv>0){var b=document.createElement('span');b.className='own';b.textContent='tens '+hv+' ·';slot.appendChild(b);}
    slot.appendChild(sel);}
  capply(li);
  sel.addEventListener('change',function(){localStorage.setItem(ckey(n),prints[sel.value].s);capply(li);crecompute();});
});
crecompute();
// --- exportar wantlist (formato Cardmarket: "<qtd> <nome>") ---
function wlLines(pairs){var m={};pairs.forEach(function(p){var n=p[0],q=p[1];if(!(n in m)||q>m[n])m[n]=q;});
  return Object.keys(m).sort().map(function(n){return m[n]+' '+n;}).join('\\n');}
function copyWL(text,btn){var o=btn.textContent;
  function done(){btn.textContent='✓ copiado';setTimeout(function(){btn.textContent=o;},1500);}
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,function(){window.prompt('Copia (Ctrl+C):',text);});}
  else{window.prompt('Copia (Ctrl+C):',text);}}
var _all=[];Object.keys(WANT).forEach(function(k){WANT[k].forEach(function(p){_all.push(p);});});
var _ca=document.getElementById('copyall');
if(_ca)_ca.addEventListener('click',function(){copyWL(wlLines(_all),_ca);});
document.querySelectorAll('button.cp[data-deck]').forEach(function(b){
  b.addEventListener('click',function(){copyWL(wlLines(WANT[b.dataset.deck]||[]),b);});});
</script>
</body></html>"""


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "cobertura.html")
    today = con.execute("SELECT MAX(window_end) w FROM card_roles").fetchone()["w"] or ""
    rep = build_report(con)
    out.write_text(build_html(rep, today), encoding="utf-8")
    return out, rep


def main():
    with db.session() as con:
        out, rep = build(con)
    n = sum(len(s["decks"]) for s in rep["sections"])
    print(f"cobertura.html escrito: {out}  ({n} decks, {len(rep['general'])} staples partilhados)")


if __name__ == "__main__":
    main()
