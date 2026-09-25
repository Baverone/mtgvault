"""Gera colecao_cor.html — a COLEÇÃO (só ela) organizada como o André a arruma
fisicamente: por COR e, dentro de cada cor, por CUSTO DE MANA (CMC).

As cartas são classificadas em classify.py: só as de estado "Coleção" entram
aqui. As de deck ficam de fora (estão nos decks montados) e as de venda vão
para uma secção própria no fim. Serve de guia para arrumar e para ver o que
ainda falta fotografar.

Terras à parte (não têm CMC), por nome. Marcadores: ★ = foil, PT = português.
Imagens da Scryfall (CDN), construídas a partir do scryfall_id.

Uso:  python colecao_cor.py   ->  escreve colecao_cor.html na raiz do repo.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import classify  # noqa: E402
import commander_decks  # noqa: E402  (decks de consenso em camadas núcleo/flex/tech)
from mtgvault import db, loadout, paginas, precos  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402
from mtgvault import collection as col  # noqa: E402
from mtgvault.collection import jogaveis, owned_playable, valor_da_coleccao  # noqa: E402

COLOR = {"W": "Branco", "U": "Azul", "B": "Preto", "R": "Vermelho", "G": "Verde"}
ORDER = ["Branco", "Azul", "Preto", "Vermelho", "Verde", "Multicor",
         "Incolor / Artefacto", "Terras"]


def _bucket(type_line, ci):
    if type_line and "Land" in type_line:
        return "Terras"
    try:
        cols = json.loads(ci) if ci and ci.strip().startswith("[") else [c for c in (ci or "") if c in "WUBRG"]
    except Exception:
        cols = [c for c in (ci or "") if c in "WUBRG"]
    if len(cols) >= 2:
        return "Multicor"
    if len(cols) == 1:
        return COLOR[cols[0]]
    return "Incolor / Artefacto"


def _img(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg"


def _card(x, badge_cls="q"):
    fo = '<span class="mk foil">★</span>' if x["fin"] == "foil" else ""
    pt = '<span class="mk pt">PT</span>' if x["lang"] == "pt" else ""
    cls, tag, data = "c", "", ""
    tip = html.escape(x["nm"] or "")
    if x.get("used_by"):          # vai para um deck — só MARCADA (o botão escurece)
        where = ", ".join(x["used_by"])
        data = f' data-used="{html.escape(where)}"'
        tag = f'<span class="use">{html.escape(where)}</span>'
        tip += f' — vai para: {html.escape(where)}'
    elif x.get("de"):             # o loadout dá-a a esta caixa, mas está noutro balde
        cls = "c fora"
        tag = (f'<span class="fora" title="está em {html.escape(x["de"])} — '
               f'é de lá que a tiras para montar">de {html.escape(x["de"])}</span>')
        tip += f' — está em {html.escape(x["de"])}'
    elif x.get("extra"):          # deck vigiado: carta que saiu da lista, guardada
        cls = "c extra"
        tag = '<span class="ex" title="fora da lista, guardada sem prazo">extra</span>'
        tip += " — extra (saiu da lista, guardada sem prazo)"
    # O NOME no `alt`: a imagem é o conteúdo. Sem ele, uma rede fraca deixava o
    # binder inteiro em quadrados vazios — e é esta a página com que ele enche
    # os binders. Ver a mesma nota no `metagame._card`.
    return (f'<div class="{cls}"{data} title="{tip}">'
            f'<img loading="lazy" src="{_img(x["sid"])}" '
            f'alt="{html.escape(x["nm"] or "")}">'
            f'<span class="{badge_cls}">{x["q"]}</span>{fo}{pt}{tag}</div>')


# Um "binder" por cor. Ícone e slug (para âncoras) de cada cor.
ICON = {"Branco": "⬜", "Azul": "🟦", "Preto": "⬛", "Vermelho": "🟥", "Verde": "🟩",
        "Multicor": "🟪", "Incolor / Artefacto": "⚙️", "Terras": "🏔️"}
SLUG = {"Branco": "branco", "Azul": "azul", "Preto": "preto", "Vermelho": "vermelho",
        "Verde": "verde", "Multicor": "multicor", "Incolor / Artefacto": "incolor",
        "Terras": "terras"}
# Os baldes de coleção (sub_collection -> rótulo curto), pela ordem em que
# aparecem DENTRO de cada cor. Desde o modelo de colecção única (André,
# 2026-09-07: *"põe a colecção toda em uma coisa só, com excepção da RL"*) é um
# só; os nomes antigos ficam para o mesmo código estar certo antes e depois da
# migração, e só aparecem os que têm cartas.
ROTULOS = {"Colecção": "📚 Coleção", "SPML": "🔷 SPML",
           "Premodern (geral)": "🕰️ Premodern", "Jogar": "🎴 Jogar"}


def _pools():
    """(balde, rótulo) dos baldes de colecção — a Caixa RL fica de fora."""
    return [(b, ROTULOS.get(b, b)) for b in loadout.baldes_coleccao()
            if b != loadout.BALDE_RL]


def _cmc_grids(rows, is_land):
    """Grelhas por custo de mana (ou uma só, para Terras)."""
    bycmc = defaultdict(list)
    for r in rows:
        bycmc[0 if is_land else int(r["cmc"] or 0)].append(r)
    out = ""
    for cmc in sorted(bycmc):
        cards = sorted(bycmc[cmc], key=lambda x: (x["nm"] or "").lower())
        lbl = "Terras" if is_land else f"CMC {cmc}"
        out += f'<h4>{lbl} <span class="n">{sum(x["q"] for x in cards)}</span></h4><div class="grid">'
        out += "".join(_card(x) for x in cards)
        out += "</div>"
    return out


# Decks permanentes de LISTA FIXA (balde físico + rótulo). O Cloud (Duel Commander)
# não entra aqui — é de CONSENSO, mostrado em camadas (núcleo/flex/tech) mais abaixo.
WATCHED_BALDES = [("Blue Farm", "🩸 Blue Farm [cEDH]"),
                  ("Cloud cEDH", "☁️ Cloud [cEDH]"),
                  ("Pauper Affinity", "🔧 Pauper Affinity")]
# Comandantes seguidos por consenso (balde -> (nome do deck, formato, comandante)).
CONSENSUS_BALDES = {"Cloud": ("Cloud (Duel Commander)", "duel-commander", "Cloud, Midgar Mercenary")}
CI_ICON = {"W": "⬜", "U": "🟦", "B": "⬛", "R": "🟥", "G": "🟩"}


def _alocacao(con):
    """A alocação do loadout, uma vez por página. Se falhar, as secções ficam
    como estavam — mais vale isso do que a página inteira ir abaixo."""
    try:
        return loadout.allocate(con)
    except Exception:                       # noqa: BLE001
        return None


def _de_outro_balde(con, res, balde, cur):
    """Cartas que o LOADOUT deu a esta caixa mas que vivem noutro balde.

    O balde é onde a carta está arrumada hoje; a caixa é o deck que a vai levar.
    Nem sempre coincidem — os quatro Utrom Monitor do Pauper estão no `SPML`
    (André, 2026-09-07: *"estavam lá 4 Utrom Monitor, mas no deck Pauper não
    aparecem como se eu tivesse a carta"*). Sem isto a secção mostrava um deck
    mais incompleto do que ele está, e não dizia onde ir buscar o resto.

    Devolve linhas com a mesma forma das outras (`_card`), marcadas com `de` = o
    balde de onde saem.
    """
    if res is None:
        return []
    slot = _slot_do_balde(res, balde)
    if slot is None:
        return []
    fora = {}                               # (sid, finish, lang, balde) -> qty
    # `linhas_alocadas` e não só o `have`: as cópias de uma linha INCOMPLETA
    # (pede 4, tem 2) são desta caixa na mesma, e estavam a desaparecer daqui
    # exactamente como desapareciam do painel Montar.
    for m in loadout.linhas_alocadas(slot):
        if m["nm"] not in cur:
            continue
        for g in m["lotes"]:
            # Já está na caixa (pelo balde antigo ou pela arrumação nova): não é
            # "ir buscar", e contá-la aqui era mostrá-la duas vezes.
            if g["sub"] == balde or g["local"] == slot["nome"]:
                continue
            k = (g["sid"], g["finish"], g["lang"], g["local"])
            fora[k] = fora.get(k, 0) + g["q"]
    if not fora:
        return []
    ph = ",".join("?" * len({k[0] for k in fora}))
    meta = {r["sid"]: dict(r) for r in con.execute(
        f"""SELECT scryfall_id sid, name nm, cmc, type_line tl, color_identity ci
              FROM cards WHERE scryfall_id IN ({ph})""",
        sorted({k[0] for k in fora}))}
    out = []
    for (sid, fin, lang, local), q in fora.items():
        m = meta.get(sid)
        if not m:
            continue
        out.append({"sid": sid, "nm": m["nm"], "cmc": m["cmc"], "tl": m["tl"],
                    "ci": m["ci"], "fin": fin, "lang": lang, "q": q, "de": local})
    return out


def _slot_do_balde(res, balde):
    return next((s for s in (res or {}).get("slots", []) if s.get("balde") == balde),
                None)


def _copias_na_caixa(con, res, balde):
    """As cópias que estão fisicamente DENTRO desta caixa.

    Duas maneiras de lá estar, e as duas contam para o mesmo código funcionar
    antes e depois do modelo de colecção única:
      * vivem no balde do deck (`Blue Farm`, `Cloud cEDH`, ...) — o modelo antigo;
      * estão registadas na `copy_allocation` daquele slot — o modelo novo, em
        que a colecção é um balde só e a caixa é a arrumação.
    """
    slot = _slot_do_balde(res, balde)
    sid = slot["slot"] if slot else None
    return con.execute(
        f"""SELECT c.scryfall_id sid, c.name nm, c.cmc cmc, c.type_line tl,
                  c.color_identity ci, cp.finish fin, cp.language lang,
                  SUM(CASE WHEN a.quantity IS NOT NULL THEN a.quantity
                           ELSE cp.quantity END) q
             FROM copies cp
             JOIN cards c ON c.scryfall_id = cp.scryfall_id
             LEFT JOIN sub_collections s ON s.id = cp.sub_collection_id
             LEFT JOIN copy_allocation a ON a.copy_id = cp.id AND a.slot = ?
            WHERE {jogaveis()} AND (s.name = ? OR a.quantity IS NOT NULL)
            GROUP BY c.scryfall_id, cp.finish, cp.language
            HAVING q > 0""", (sid, balde)).fetchall()


def _watched_deck_pools(con):
    """Por cada deck vigiado: o deck por INTEIRO (o que tem e está na lista atual)
    + as cartas EXTRA (as que já tem mas saíram da lista) — GUARDADAS SEM PRAZO
    (André, 2026-09-15; era "até 6 meses da última utilização, depois vender", e a
    fonte dessa data nunca foi decidida — deixou de ser precisa). Saem daqui só
    quando ele carregar em «vendida», carta a carta.

    A lista atual vem da lista vigiada (watched_snapshots); para o Cloud (Duel
    Commander), do consenso (deck_cards).

    O que está NA CAIXA sai do balde do deck; o que o loadout lhe deu de OUTRO
    balde vem do `_de_outro_balde` e aparece marcado com "de <balde>" — é a mesma
    regra "indicas onde está a carta" que vale no resto do site.
    """
    res = _alocacao(con)
    wmap = {r["sub_collection"]: r["watched_id"]
            for r in con.execute("SELECT sub_collection, watched_id FROM deck_collection")}

    def _lista_actual(balde):
        # Só a lista MAIS RECENTE. Até 2026-09-15 percorriam-se todos os
        # snapshots para datar a "última utilização" de cada carta — era a base
        # de um prazo de 6 meses que ele acabou por não querer.
        wid = wmap.get(balde)
        if wid:
            r = con.execute("SELECT cards FROM watched_snapshots WHERE watched_id = ? "
                            "ORDER BY taken_at DESC LIMIT 1", (wid,)).fetchone()
            return ({c[1].split(" // ")[0] for c in json.loads(r["cards"])}
                    if r else set())
        # Cloud (Duel Commander): consenso.
        return {r["nm"].split(" // ")[0] for r in con.execute(
            "SELECT card_name nm FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id "
            "WHERE d.name = 'Cloud (Duel Commander)'")}

    out = []
    for balde, title in WATCHED_BALDES:
        cur = _lista_actual(balde)
        deck_rows, extra_rows = [], []
        for r in _copias_na_caixa(con, res, balde):
            row = dict(r)
            front = r["nm"].split(" // ")[0]
            if front in cur:
                deck_rows.append(row)
            else:
                row["extra"] = True
                extra_rows.append(row)
        outros = _de_outro_balde(con, res, balde, cur)
        deck_rows += outros
        if deck_rows or extra_rows:
            out.append({"title": title, "deck": deck_rows, "extra": extra_rows,
                        "n_list": len(cur), "n_have": len(deck_rows),
                        "n_fora": sum(x["q"] for x in outros)})
    return out


def _consensus_tiers_html(con):
    """Decks de consenso (ex.: Cloud) em camadas: núcleo (≥50%, o deck), flex
    (25–50%) e tech (15–25%). Só cartas dentro da cor do comandante. Cada carta a
    cores se o André a tem, a cinzento se falta, com a % de listas que a jogam."""
    owned = set(owned_playable(con))
    out = ""
    for balde, (name, fmt, commander) in CONSENSUS_BALDES.items():
        t, n = commander_decks.tiers(con, fmt, commander)
        if not t:
            continue
        names = [nm.split(" // ")[0] for k in ("core", "flex", "tech") for nm, _ in t[k]]
        osid, cat = {}, {}
        for r in con.execute("SELECT c.name nm, cp.scryfall_id sid FROM copies cp "
                             "JOIN cards c ON c.scryfall_id = cp.scryfall_id "
                             "WHERE " + jogaveis()):
            osid.setdefault(r["nm"].split(" // ")[0], r["sid"])
        for i in range(0, len(names), 300):
            ch = names[i:i + 300]
            ph = ",".join("?" for _ in ch)
            for r in con.execute(f"SELECT name nm, scryfall_id sid FROM cards "
                                 f"WHERE name IN ({ph}) AND digital=0 GROUP BY name", ch):
                cat.setdefault(r["nm"], r["sid"])

        def tcard(nm, pct):
            front = nm.split(" // ")[0]
            have = front in owned
            sid = osid.get(front) or cat.get(front)
            img = (f'<img loading="lazy" src="{_img(sid)}" '
                   f'alt="{html.escape(front)}">' if sid
                   else '<div class="noimg"></div>')
            return (f'<div class="c {"" if have else "miss"}" '
                    f'title="{html.escape(nm)} · {pct}% das listas">{img}'
                    f'<span class="q pctb">{pct}%</span></div>')

        def own(lst):
            return sum(1 for nm, _ in lst if nm.split(" // ")[0] in owned)
        ico = CI_ICON.get(t["ci"], "🌈") if len(t["ci"]) == 1 else ("⚙️" if not t["ci"] else "🌈")
        out += (f'<h3>{shell.icone("nuvem")} {html.escape(name)} {ico} <span class="n">núcleo {len(t["core"])} '
                f'(tens {own(t["core"])}) · flex {len(t["flex"])} (tens {own(t["flex"])}) · '
                f'tech {len(t["tech"])} (tens {own(t["tech"])}) · de {n} listas</span></h3>')
        out += ('<h4>núcleo (≥50%) — o deck</h4><div class="grid">'
                + "".join(tcard(nm, p) for nm, p in t["core"]) + '</div>')
        out += '<div class="tiersep">↓ opções para as vagas (verde = tens · cinza = falta) ↓</div>'
        out += ('<h4>flex (25–50%)</h4><div class="grid">'
                + "".join(tcard(nm, p) for nm, p in t["flex"]) + '</div>')
        out += ('<h4>tech (15–25%)</h4><div class="grid">'
                + "".join(tcard(nm, p) for nm, p in t["tech"]) + '</div>')
    return out


def _value(con):
    """Valor de TUDO o que o André tem na estante, em DOIS cenários:
      'min'   = preço mais BAIXO à venda (Cardmarket `low`)
      'trend' = preço de TENDÊNCIA (Cardmarket `trend`)
    Cada um repartido em [coleção, decks, caixa RL, colecionador].

    A CONTA NÃO VIVE AQUI (2026-09-24): é a `collection.valor_da_coleccao`, a
    mesma que a Galeria, o Início e o `cli value` usam. Esta função ficou só a
    dar-lhe a forma que a página já lia (duas listas por cenário) — havia quatro
    contas para *"quanto vale esta cópia?"* e duas páginas a dizerem 97 761,26 €
    e 97 772,93 € sobre o mesmo dinheiro. Ver o cabeçalho da secção no
    `mtgvault/collection.py`.
    """
    v = valor_da_coleccao(con)
    # Desde o MODO DE PREÇO (2026-09-25) o `trend` desta página é o cenário EM
    # VIGOR (market/best/média) e não a coluna `trend`: o rótulo interno ficou,
    # porque é o que o resto do ficheiro já lia, mas o número é o mesmo que a
    # Galeria e o Início mostram. O `min` continua a ser o best value.
    return {c: [v["partes"][cen][p] for p in col.PARTES]
            for c, cen in (("min", "low"), ("trend", v["cenario"]))}


def _eur(x):
    # COM CÊNTIMOS (2026-09-24). Era `casas=0`: o total desta página saía
    # «97 773 €» e o mesmo número saía «97 772,93 €» na Galeria e no Início.
    # A conta era a mesma, o arredondamento é que não — e quem lê as duas
    # páginas vê dois números. É o irmão pequeno do `event_tier`.
    return paginas.eur(x)


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "colecao_cor.html")
    # Fase "encher os binders": mostra TUDO o que o André tem nos baldes de
    # coleção (SPML + Premodern), por cor→CMC, SEM remover nada para decks nem
    # venda. As que iriam para um deck ficam só MARCADAS (data-used) — o botão
    # "sombrear as que vão para decks" liga isso quando ele passar a essa fase.
    spml_formatos, completos, montados = classify._config()
    active_fmts = [f for f, s in spml_formatos.items() if s in classify.ACTIVE_STATUSES]
    pm_status = classify.premodern_status(con, sticky=completos)
    used_by = classify._used_by(con, active_fmts, pm_status, montados)

    baldes = [b for b, _ in _pools()]
    ph = ",".join("?" * len(baldes))
    colrows = defaultdict(lambda: defaultdict(list))   # cor -> balde -> linhas
    n_deckbound = 0
    for r in con.execute(
        f"""SELECT c.scryfall_id sid, c.name nm, c.cmc cmc, c.type_line tl,
                   c.color_identity ci, cp.finish fin, cp.language lang, s.name sub,
                   SUM(cp.quantity - COALESCE((SELECT SUM(a.quantity)
                        FROM copy_allocation a WHERE a.copy_id = cp.id), 0)) q
              FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
              JOIN sub_collections s ON s.id = cp.sub_collection_id
             WHERE {jogaveis()} AND s.name IN ({ph})
             GROUP BY c.scryfall_id, cp.finish, cp.language, s.name
             HAVING q > 0""", baldes):
        # As cópias que já estão DENTRO de uma deckbox saem daqui: aparecem na
        # secção "Decks permanentes", que é onde elas estão. É o que os baldes
        # `Blue Farm`/`Cloud`/... faziam antes de a colecção passar a ser um só.
        row = dict(r)
        ub = used_by.get(r["nm"])
        if ub:
            row["used_by"] = sorted(ub)
            n_deckbound += r["q"]
        colrows[_bucket(r["tl"], r["ci"])][r["sub"]].append(row)

    secs, navs = "", []
    for b in ORDER:
        pools = colrows.get(b)
        if not pools:
            continue
        total = sum(x["q"] for rs in pools.values() for x in rs)
        slug = SLUG[b]
        navs.append(f'<a href="#bind-{slug}">{ICON[b]} {b} '
                    f'<span class="sn">{total}</span></a>')
        secs += (f'<h2 id="bind-{slug}" class="pool">{ICON[b]} {html.escape(b)} '
                 f'<span class="n">{total}</span></h2>')
        for sub, short in _pools():
            rs = pools.get(sub)
            if not rs:
                continue
            secs += f'<h3>{short} <span class="n">{sum(x["q"] for x in rs)}</span></h3>'
            secs += _cmc_grids(rs, b == "Terras")
    # O índice das cores: era uma linha de links separados por `·` numa barra
    # sticky. Passou a controlo segmentado (`.seg`), o mesmo de todas as
    # páginas — envolve em vez de correr para o lado.
    topnav = "".join(navs)

    # Decks permanentes (só decks). Lista fixa (Blue Farm/Cloud cEDH/Pauper): o deck
    # por inteiro + extras. Consenso (Cloud DC): camadas núcleo/flex/tech.
    wsec_body = ""
    for p in _watched_deck_pools(con):
        fora = (f' · {p["n_fora"]} de outro balde' if p.get("n_fora") else "")
        wsec_body += (f'<h3>{html.escape(p["title"])} <span class="n">'
                      f'{p["n_have"]} na lista{fora} · {len(p["extra"])} extra</span></h3>')
        dcards = sorted(p["deck"], key=lambda x: (int(x["cmc"] or 0), (x["nm"] or "").lower()))
        wsec_body += '<div class="grid">' + "".join(_card(x) for x in dcards) + '</div>'
        if p["extra"]:
            ex = sorted(p["extra"], key=lambda x: (int(x["cmc"] or 0), (x["nm"] or "").lower()))
            wsec_body += ('<h4>extra — fora da lista, retidas</h4><div class="grid">'
                          + "".join(_card(x) for x in ex) + '</div>')
    wsec_body += _consensus_tiers_html(con)

    wsec = ""
    if wsec_body:
        topnav += '<a href="#vigiados">🃏 Decks montados</a>'
        wsec = ('<h2 id="vigiados" class="pool">🃏 Decks montados '
                '<span class="n">só decks — não coleção</span></h2>'
                '<p class="hint">Lista fixa (Blue Farm, Cloud cEDH, Pauper): o deck por inteiro '
                # «vendida» era o nome do botão que as tirava daqui, e esse
                # botão está fora de vista desde 25/09/2026. A frase diz a
                # mesma coisa sem nomear uma acção que ele já não vê.
                '+ as <b>extra</b> (saíram da lista, guardadas sem prazo — só saem '
                'quando tu o disseres, carta a carta). As cartas com '
                '<b style="color:#bcd4ff">de &lt;balde&gt;</b> estão arrumadas noutro sítio mas o '
                '<b>loadout</b> dá-as a esta caixa — é de lá que as tiras para montar (foi o caso '
                'dos 4 Utrom Monitor do Pauper, que vivem no SPML). Consenso (Cloud): em '
                'camadas — <b>núcleo</b> (≥50% das listas) é o deck; <b>flex</b> (25–50%) e '
                '<b>tech</b> (15–25%) são opções para as vagas. Só cartas dentro da cor do '
                'comandante.</p>' + wsec_body)

    total_col = sum(x["q"] for pools in colrows.values() for rs in pools.values() for x in rs)
    ESTADO = {"a jogar": "#4ac585", "a treinar": "#e0b64b",
              "a preparar": "#5b8cff", "ignorar": "#93a0ad"}
    fmts = " ".join(
        f'<b style="color:{ESTADO.get(s, "#93a0ad")}">{html.escape(f.capitalize())}</b>'
        f'<span class="muted"> {html.escape(s)}</span>'
        for f, s in spml_formatos.items())
    pm_completos = [d for d, st in pm_status.items() if st["locked"]]
    pm_str = ", ".join(pm_completos) if pm_completos else f"0 completos · {len(pm_status)} a montar"
    mont_str = (f' &nbsp;·&nbsp; 🔒 montados: <b>{", ".join(html.escape(m) for m in montados)}</b>'
                if montados else "")
    cfg_line = (f'🔷 SPML: {fmts} &nbsp;·&nbsp; 🕰️ Premodern: <b>{html.escape(pm_str)}</b>{mont_str}'
                f'<span class="muted"> — diz-me se mudas de formato ou quando montas um deck</span>')
    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""

    val = _value(con)
    total = sum(val["trend"])   # o cenário EM VIGOR (ver `_value`)
    # Com a receita `unico` (o bulk da Scryfall) as duas colunas são iguais e os
    # três modos dão o mesmo número — vale a pena dizê-lo, senão o interruptor
    # parece avariado. Com o CardTrader ligado deixa de ser verdade.
    todos_iguais = abs(sum(val["min"]) - total) < 0.005

    def _vrow(lbl, i):
        return f'<tr><td>{lbl}</td><td>{_eur(val["trend"][i])}</td></tr>'
    # A linha do colecionador só aparece quando há alguma: um «0,00 €» fixo é
    # ruído, e omiti-la quando existe era somá-la sem o dizer.
    rows = _vrow("📚 Coleção", 0) + _vrow("🃏 Decks", 1) + _vrow("📦 Caixa RL", 2)
    if val["trend"][3]:
        rows += _vrow("🏛️ Colecionador", 3)
    valor_html = (
        f'<div class="valor"><div class="vtot">💰 <b class="vtr">{_eur(total)}</b> '
        f'<span class="vall">— valor total de tudo (coleção + decks + caixa), '
        f'pelo <b>{html.escape(precos.ROTULOS[precos.modo()])}</b> '
        f'({html.escape(precos.fonte())})</span></div>'
        f'<table class="vtab"><tr><th></th><th>valor</th></tr>{rows}</table>'
        f'<div class="vnote">A <b>mesma conta</b> da '
        f'<a href="colecao.html">Galeria</a> e do <a href="index.html">Início</a>, '
        f'no modo de preço que está escolhido (<b>market</b> = o que o mercado pede · '
        f'<b>best</b> = a oferta mais barata · <b>média</b> dos dois; troca-se no modo '
        f'edição). Quando o acabamento da cópia não está cotado, cai para o outro (uma '
        f'foil sem preço vale o nonfoil) — a Galeria marca essas com <b>~</b>. '
        f'{"Enquanto a fonte der <b>um só valor</b> por carta os três modos coincidem." if todos_iguais else ""}'
        f'</div></div>')

    out.write_text(_TMPL
                   .replace("%SECS%", secs).replace("%VIGIADOS%", wsec)
                   .replace("%VALOR%", valor_html)
                   .replace("%NAV%", topnav).replace("%TOTAL%", str(total_col))
                   .replace("%DECKN%", str(n_deckbound))
                   .replace("%CFG%", cfg_line).replace("%TODAY%", today), encoding="utf-8")
    return out


_CSS = """
 .nav{position:sticky;top:var(--sticky);z-index:20;padding:10px 0 12px;margin-bottom:4px;
   background:linear-gradient(180deg,var(--bg) 78%,transparent)}
 .nav .seg{max-width:100%}
 .nav .sn{color:var(--dim);font-weight:600;font-size:11px}
 h2.pool{font-family:var(--font-hd);font-size:19px;margin:34px 0 4px;padding:9px 13px;
   border-radius:var(--r);background:var(--card);border:1px solid var(--line);
   border-left:3px solid var(--accent);scroll-margin-top:calc(var(--sticky) + 58px)}
 .colnav{font-size:12px;margin:0 0 8px;display:flex;flex-wrap:wrap;gap:4px 10px}
 .colnav a{color:var(--muted);text-decoration:none} .colnav a:hover{color:var(--accent)}
 h3{font-size:15px;margin:18px 0 5px;border-bottom:1px solid var(--line);padding-bottom:5px}
 h4{color:var(--muted);font-size:12px;margin:10px 0 4px;text-transform:uppercase;letter-spacing:.04em}
 .n{color:var(--muted);font-size:12px;font-weight:400}
 .grid{display:flex;flex-wrap:wrap;gap:6px}
 .c{position:relative;width:74px} .c img{width:74px;border-radius:5px;display:block;background:#0c0f14}
 /* Como se lê o `alt` (o nome da carta) quando a imagem não carrega — é esta a
    página com que ele enche os binders, e uma parede de quadrados vazios não
    serve para nada. */
 .c img{min-height:103px;overflow:hidden;font-size:9px;line-height:1.15;color:var(--muted);padding:2px}
 .c .q{position:absolute;top:2px;left:2px;background:#000b;color:#fff;font-weight:700;font-size:11px;padding:0 5px;border-radius:7px}
 .c .q.sell{background:#7a1d1d}
 .c .use{display:none;position:absolute;bottom:0;left:0;right:0;background:#000e;color:#c7d0da;font-size:8px;line-height:1.3;padding:1px 3px;border-radius:0 0 5px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center}
 body.deckmode .c[data-used] img{filter:grayscale(1) brightness(.42)}
 body.deckmode .c[data-used] .q{background:#000d;color:#9aa6b2}
 body.deckmode .c[data-used] .use{display:block}
 .c.extra img{filter:brightness(.82) sepia(.35) saturate(1.3) hue-rotate(-15deg)}
 .c .ex{position:absolute;bottom:0;left:0;right:0;background:#5a4a1f;color:#f4e0a0;font-size:8.5px;font-weight:700;line-height:1.35;padding:1px 3px;border-radius:0 0 5px 5px;text-align:center}
 .c.fora img{box-shadow:0 0 0 2px #7fa8ff}
 .c .fora{position:absolute;bottom:0;left:0;right:0;background:#1b2c4d;color:#bcd4ff;font-size:8.5px;font-weight:700;line-height:1.35;padding:1px 3px;border-radius:0 0 5px 5px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .c.miss{opacity:.72} .c.miss img{filter:grayscale(1) brightness(.5)}
 .c .noimg{width:74px;height:103px;border-radius:5px;background:#0c0f14}
 .c .q.pctb{background:#1c2c4a;color:#9cc2ff}
 .tiersep{margin:14px 0 7px;padding:6px 11px;border-radius:9px;background:var(--card);border:1px dashed var(--line2);color:var(--muted);font-size:12px;text-align:center;font-weight:600}
 .mk{position:absolute;bottom:3px;right:3px;font-size:10px;font-weight:700}
 .mk.foil{color:var(--gold);text-shadow:0 0 3px #000} .mk.pt{background:#12351f;color:var(--add);border-radius:4px;padding:0 3px;font-size:9px}
 .tally{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .tally b{display:inline-block;padding:4px 11px;border-radius:999px;font-size:12px;font-weight:700}
 .t-col{background:var(--info-soft);color:var(--ob)} .t-deck{background:#0f2a1c;color:var(--add)} .t-sell{background:#3a1516;color:#f0a0a0}
 .hint{color:var(--muted);font-size:12px;margin:4px 0 10px}
 .cfg{font-size:12.5px;margin:0 0 14px;padding:10px 13px;border-radius:var(--r);background:var(--card);border:1px solid var(--line);color:var(--ink2)}
 .cfg .muted{color:var(--muted)}
 .valor{margin:0 0 6px;background:var(--card);border:1px solid var(--line);border-radius:var(--r2);padding:13px 16px}
 .valor .vtot{font-size:15px} .valor .vmin{color:var(--add);font-weight:800;font-size:19px} .valor .vtr{color:var(--gold);font-weight:800;font-size:19px} .valor .vlbl{color:var(--muted);font-size:11px} .valor .vall{color:var(--muted);font-size:12px;margin-left:4px}
 .vtab{border-collapse:collapse;margin:9px 0 3px;font-size:13px} .vtab th{color:var(--dim);font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:.07em;padding:2px 18px 4px 0;text-align:right} .vtab th:first-child{text-align:left} .vtab td{padding:2px 18px 2px 0;text-align:right;font-variant-numeric:tabular-nums} .vtab td:first-child{text-align:left} .vtab td:nth-child(2){color:var(--add)} .vtab td:nth-child(3){color:var(--gold)}
 .vnote{color:var(--dim);font-size:11px;margin-top:5px}
"""

_LEAD = ("TUDO o que tens nos baldes de coleção, por <b>cor → custo de mana</b> — "
         "nada removido para decks. Enche os binders e fotografa o que não "
         "aparecer · dados de <b>%TODAY%</b>")

_ACCOES = ('<div class="tally"><b class="t-col">🔵 %TOTAL% nos binders</b>'
           '<b class="t-deck">🟢 %DECKN% p/ decks</b></div>'
           '<button class="btn" id="dm" type="button" onclick="toggleDM()">'
           '🎯 marcar as que vão p/ decks</button>')

_RODAPE = ("<b>Um binder por cor</b>; dentro de cada cor, <b>SPML</b> e "
           "<b>Premodern</b> separados, cada um por custo de mana (as Terras por "
           "nome). Mostra <b>TUDO</b> o que tens nesses baldes — nada é removido "
           "para decks (enche primeiro os binders; os decks vêm depois). Os decks "
           "montados (Blue Farm, Cloud, etc.) ficam <b>à parte</b>, na secção "
           "🃏 Decks montados. O número em cada carta é quantas tens; ★ = foil, "
           "PT = português. <b>Se tiveres uma carta na mão que não aparece — ou "
           "mais do que o número — ainda não está catalogada: fotografa.</b> O "
           "botão <b>🎯 marcar as que vão p/ decks</b> sombreia as que já estão "
           "reservadas a um deck. Atualiza sozinho todos os dias.")

_TMPL = ("""<!doctype html><html lang="pt-PT"><head>"""
         + shell.head("Binders por cor", _CSS) + """</head><body>"""
         + shell.abrir("colecao_cor.html", "Binders por cor", _LEAD, _ACCOES) + """
<div class="wrap">
<div class="cfg">%CFG%</div>
%VALOR%
<div class="nav"><div class="seg">%NAV%</div></div>
%SECS%
%VIGIADOS%
</div>""" + shell.fechar(_RODAPE, """
<script>
function toggleDM(){var on=document.body.classList.toggle('deckmode');
  var b=document.getElementById('dm');b.classList.toggle('on',on);
  b.textContent=on?'🎯 a sombrear as de decks':'🎯 marcar as que vão p/ decks';
  try{localStorage.setItem('cc_deckmode',on?'1':'');}catch(e){}}
try{if(localStorage.getItem('cc_deckmode'))toggleDM();}catch(e){}
</script>""") + """</body></html>""")


def main():
    with db.session() as con:
        out = build(con)
    print(f"colecao_cor.html escrito: {out}")


if __name__ == "__main__":
    main()
