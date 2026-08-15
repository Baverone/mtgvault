"""Gera meusdecks.html — "Os meus decks".

Ao contrário da cobertura (metagame geral), esta aba é SÓ dos decks do André:
os que ele segue (tabela `decks`: por assinatura, por jogador, ou consenso) com
o estado (🔒 montado, quem segue), a % que já tem, e a EVOLUÇÃO do deck com
datas (o que entrou/saiu na lista, a partir dos `core_snapshots`).

Protótipo do visual novo: navegação em botões grandes, cada deck é um cartão
"botão" que expande para os detalhes + evolução. NÃO inventa nada.
"""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import buildability as bd  # noqa: E402  (deck_status: % e o que falta)
from mtgvault.collection import owned_playable  # noqa: E402

FMT_LABEL = bd.FMT_LABEL
FMT_ORDER = bd.FMT_ORDER

# Deck (tabela decks) -> chave(s) de core_snapshots, para a evolução.
DECK_CORE = {
    "Izzet Affinity (Kappa Cannoneer)": ["modern:affinity-kappa"],
    "Grinding Station": ["modern:grinding-station"],
    "Cloud (Duel Commander)": ["dc:cloud"],
    "Jeskai Lessons": ["standard:jeskai:wur", "standard:jeskai:wubr"],
}


def _evolution(con, core_keys, limit=4):
    """Timeline de alterações (entrou/saiu) a partir dos core_snapshots das
    chaves dadas, diffs de snapshots consecutivos, mais recente primeiro."""
    events = []
    for ck in core_keys:
        snaps = con.execute(
            "SELECT taken_at, cards_json FROM core_snapshots WHERE core_key = ? "
            "ORDER BY taken_at DESC", (ck,)).fetchall()
        for i in range(len(snaps) - 1):
            new = {tuple(c[:2]): (c[2] if len(c) > 2 else 1) for c in json.loads(snaps[i]["cards_json"])}
            old = {tuple(c[:2]): (c[2] if len(c) > 2 else 1) for c in json.loads(snaps[i + 1]["cards_json"])}
            ins, outs = [], []
            for k in set(new) | set(old):
                if new.get(k, 0) > old.get(k, 0):
                    ins.append(k[1])
                elif new.get(k, 0) < old.get(k, 0):
                    outs.append(k[1])
            if ins or outs:
                events.append({"date": snaps[i]["taken_at"], "ins": sorted(ins), "outs": sorted(outs)})
    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:limit]


def _source(notes):
    notes = notes or ""
    if "consenso" in notes:
        return "🧩 consenso do metagame"
    if "auto:" in notes:
        # "auto: mtgo PLAYER data (#id)"
        parts = notes.split()
        player = parts[2] if len(parts) > 2 else "?"
        return f"🎯 segue {player}"
    return "🎯 seguido"


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "meusdecks.html")
    owned = owned_playable(con)
    try:
        montados = set(json.loads(
            (ROOT / "colecao_config.json").read_text(encoding="utf-8")).get("decks_montados", []))
    except Exception:
        montados = set()

    by_fmt = defaultdict(list)
    for d in con.execute("SELECT id, name, format, notes FROM decks"):
        st = bd.deck_status(con, d["id"], owned)
        if st["need"] == 0:
            continue
        by_fmt[d["format"]].append({
            "name": d["name"], "notes": d["notes"], **st,
            "montado": d["name"] in montados,
            "evol": _evolution(con, DECK_CORE.get(d["name"], [])),
        })

    secs = ""
    n_total = 0
    for fmt in FMT_ORDER + [f for f in by_fmt if f not in FMT_ORDER]:
        decks = by_fmt.get(fmt)
        if not decks:
            continue
        decks.sort(key=lambda x: -x["pct"])
        n_total += len(decks)
        cards = ""
        for d in decks:
            col = "var(--add)" if d["pct"] >= 90 else "var(--gold)" if d["pct"] >= 60 else "var(--warn)"
            badges = f'<span class="bdg src">{_source(d["notes"])}</span>'
            if d["montado"]:
                badges += '<span class="bdg on">🔒 montado</span>'
            miss_txt = (f'faltam {len(d["missing"])} · {d["cost"]:.2f}€' if d["missing"]
                        else "completo ✅")
            # evolução
            if d["evol"]:
                ev = ""
                for e in d["evol"]:
                    ins = "".join(f'<span class="in">▲ {html.escape(c)}</span>' for c in e["ins"])
                    outs = "".join(f'<span class="out">▼ {html.escape(c)}</span>' for c in e["outs"])
                    ev += f'<div class="evrow"><span class="evd">{e["date"]}</span>{ins}{outs}</div>'
                evol = f'<details class="evol"><summary>📈 Evolução da lista</summary>{ev}</details>'
            else:
                evol = '<div class="evx">📈 evolução — histórico a acumular</div>'
            cards += (
                f'<div class="deck">'
                f'<div class="dtop"><b>{html.escape(d["name"])}</b>'
                f'<span class="pct" style="color:{col}">{d["pct"]}%</span></div>'
                f'<div class="badges">{badges}</div>'
                f'<div class="bar"><span style="width:{d["pct"]}%;background:{col}"></span></div>'
                f'<div class="mt">{d["have"]}/{d["need"]} · {miss_txt}</div>'
                f'{evol}</div>')
        secs += (f'<section><h2>{html.escape(FMT_LABEL.get(fmt, fmt))} '
                 f'<span class="n">{len(decks)}</span></h2><div class="grid">{cards}</div></section>')

    today = con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or ""
    out.write_text(_TMPL.replace("%SECS%", secs).replace("%N%", str(n_total))
                   .replace("%TODAY%", today), encoding="utf-8")
    return out


_TMPL = """<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Os meus decks</title><style>
 :root{--bg:#0d1017;--card:#161b24;--ink:#eef2f7;--muted:#8b97a6;--line:#242c38;--accent:#5b8cff;--gold:#e0b64b;--add:#4ac585;--warn:#e0704b}
 *{box-sizing:border-box} body{margin:0;background:linear-gradient(180deg,#10141d,#0d1017);color:var(--ink);font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
 .wrap{max-width:1100px;margin:0 auto;padding:22px 14px 60px}
 h1{margin:0;font-size:24px;font-weight:800;letter-spacing:-.02em}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 14px}
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
 .tabs a{flex:1;min-width:130px;text-align:center;padding:12px 10px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:14px;transition:.15s}
 .tabs a:hover{border-color:var(--accent);transform:translateY(-1px)}
 .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 h2{font-size:14px;margin:20px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em} h2 .n{color:var(--line);-webkit-text-stroke:0;color:#4a5666}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
 .deck{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;transition:.15s}
 .deck:hover{border-color:#37445a}
 .dtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px} .dtop b{font-size:15px} .pct{font-weight:800;font-size:16px}
 .badges{display:flex;flex-wrap:wrap;gap:5px;margin:7px 0} .bdg{font-size:11px;padding:2px 7px;border-radius:20px;background:#1e2531;color:var(--muted)}
 .bdg.on{background:#123020;color:var(--add)}
 .bar{position:relative;height:8px;background:#0b0e14;border-radius:999px;overflow:hidden;margin:4px 0}
 .bar span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
 .mt{color:var(--muted);font-size:12px;margin-bottom:4px}
 .evx{color:#5a6472;font-size:11px;margin-top:6px}
 .evol{margin-top:6px} .evol>summary{cursor:pointer;color:var(--accent);font-size:12px}
 .evrow{display:flex;flex-wrap:wrap;gap:5px;align-items:center;padding:5px 0;border-top:1px solid var(--line);font-size:11px}
 .evd{color:var(--muted);min-width:74px} .in{color:var(--add)} .out{color:var(--warn)}
 footer{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
</style></head><body><div class="wrap">
<header><h1>🎴 Os meus decks</h1>
<div class="lead">%N% decks que sigo · estado, % que já tenho e a evolução da lista · dados de %TODAY%</div>
<nav class="tabs">
 <a href="index.html">🏠 Início</a>
 <a class="cur" href="meusdecks.html">🎴 Os meus decks</a>
 <a href="cobertura.html">🌐 Metagame</a>
 <a href="buildability.html">🔨 Montar</a>
 <a href="colecao_cor.html">🎨 Coleção</a>
</nav></header>
%SECS%
<footer>Só os teus decks (os que segues, vigias ou montas). A % é da lista atual sobre a tua coleção. A <b>Evolução</b> mostra o que entrou (▲) e saiu (▼) da lista consenso, com datas — enche-se sozinha com os dias. Atualiza diariamente.</footer>
</div></body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("meusdecks.html:", build(con))


if __name__ == "__main__":
    main()
