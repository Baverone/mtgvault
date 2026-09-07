"""Gera deckboxes.html — "Deckboxes": os decks montados em simultâneo, e a venda.

O André (2026-09-07): *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."*

E, no mesmo dia, o que esta versão traz:

  * *"Os decks gostava que fizesses algo como fizeste para o riftvault — no
    botão, cada deck tem uma aba própria."* → a página deixou de ser uma lista
    de cartões todos abertos e passou a ser **uma fila de abas**, uma por caixa,
    com a % e a cor do estado. Clicar abre só aquela caixa. Há duas abas a mais:
    **Todas** (a vista de conjunto, um cartão por caixa) e **Arrumar**;
  * *"Quero que me ajudem a ser mais organizado com as cartas."* → a aba
    **Arrumar** traduz a alocação em instruções para a gaveta: por caixa de
    ORIGEM o que se tira e para onde vai, por caixa de DESTINO o que entra, com
    checkboxes que ficam no browser e um CSV para levar para a mesa;
  * *"Os decks que eu pedi para serem permanentes são a minha prioridade
    máxima!"* → cada caixa diz se é **permanente** ou **candidata**, e no modo
    edição (`python webapp.py`, porto 8771) os botões mudam isso, reordenam e
    marcam "sleevado e na caixa".

O que a página continua a ser: o LOADOUT, ou seja a colecção REPARTIDA. Uma
cópia física entra numa caixa e só numa — por isso os números aqui são mais
baixos que os da página `meusdecks.html`, onde cada deck conta a colecção
inteira. Três estados por carta: **verde** = está nesta caixa · **âmbar** = tens
mas não aqui (está noutra caixa, e diz qual, ou não serve na língua/acabamento)
· **vermelho** = não tens nenhuma, é compra.

O mesmo ficheiro serve os dois modos. No GitHub Pages `editable` é `false` e os
botões de escrita nem existem no HTML; no `webapp.py` é `true`. O frontend é o
mesmo — é a lição do riftvault: duas páginas diferentes divergem em silêncio.

Reutiliza `mtgvault.loadout` para as contas. Não inventa nada.
"""
from __future__ import annotations

import html
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import loadout, paginas  # noqa: E402

TABS = paginas.nav("deckboxes.html")


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


def _img_map(con, names):
    """nome -> scryfall_id de uma impressão com arte. Preferem-se as impressões
    que ele TEM (é a carta que vai estar na caixa)."""
    out = {}
    for r in con.execute("""SELECT c.name nm, cp.scryfall_id sid FROM copies cp
                              JOIN cards c ON c.scryfall_id = cp.scryfall_id
                             WHERE cp.purpose = 'player'"""):
        out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    falta = [n for n in names if n not in out]
    for i in range(0, len(falta), 300):
        ch = falta[i:i + 300]
        ph = ",".join("?" for _ in ch)
        for r in con.execute(f"""SELECT name nm, scryfall_id sid FROM cards
                                  WHERE name IN ({ph}) AND digital = 0 GROUP BY name""", ch):
            out.setdefault(r["nm"].split(" // ")[0], r["sid"])
    for n in [x for x in falta if x not in out]:      # DFCs: casa pela frente
        r = con.execute("SELECT scryfall_id sid FROM catalog.cards "
                        "WHERE name LIKE ? AND digital = 0 LIMIT 1", (n + " // %",)).fetchone()
        if r:
            out[n] = r["sid"]
    return out


# ---------------------------------------------------------------------------
# Payload: tudo o que a página mostra, em JSON. O HTML é uma casca.
# ---------------------------------------------------------------------------
def _estado_carta(m):
    """Os três estados. Âmbar é para as DUAS maneiras de "tens, mas não aqui" —
    está noutra caixa, ou está e não serve. Vermelho fica só para o que não
    existe em lado nenhum, que é o que é mesmo compra."""
    if not m["missing"]:
        return "have"
    if m["noutra_q"] or m["alt"]:
        return "sub"
    return "miss"


def _caixa_payload(s, imgs, cfs):
    cartas = []
    for m in s["have"] + s["missing"]:
        cartas.append({
            "nm": m["nm"], "board": m["board"], "need": m["need"], "got": m["got"],
            "est": _estado_carta(m), "sid": imgs.get(m["nm"]),
            "basica": bool(m.get("basica")),
            "missing": m["missing"], "comprar": m["comprar"],
            "noutra": m["noutra"], "alt": m["alt"], "alt_onde": m["alt_onde"],
            "cost": m["cost"], "unit": m["unit"],
            "cf": m["nm"] in cfs,
            "so_de": s["so_de_variante"].get(m["nm"]) or [],
            "lotes": [{"local": g["local"], "q": g["q"], "fin": g["finish"],
                       "lang": g["lang"], "set": (g["set_code"] or "").upper()}
                      for g in m["lotes"]],
        })
    cartas.sort(key=lambda c: (c["board"] != "main",
                               {"have": 0, "sub": 1, "miss": 2}[c["est"]], c["nm"]))
    return {
        "slot": s["slot"], "nome": s["nome"], "formato": s["formato"],
        "grupo": s.get("grupo"), "prioridade": s["prioridade"],
        "permanente": s["permanente"], "montado": bool(s.get("montado")),
        "por_confirmar": bool(s.get("por_confirmar")), "vazio": s["vazio"],
        "nota": s["nota"], "fonte": s.get("fonte"), "ref": s.get("ref"),
        "pct": s["pct"], "tenho": s["tenho"], "precisa": s["precisa"],
        "comprar": s["comprar"], "noutra": s["noutra"], "faltam": s["faltam"],
        "custo": s["custo"], "origens": s["origens"],
        "regras": [[i, t] for i, t in loadout.rotulo_material(s)],
        "marca": loadout.marca_wantlist(s),
        "variantes": list(s.get("variantes") or []),
        "cartas": cartas,
        "wantlist": sorted(({"nm": m["nm"], "q": m["comprar"], "cost": m["cost"]}
                            for m in s["missing"] if m["comprar"] > 0),
                           key=lambda x: x["nm"]),
        "buscar": [{"nm": m["nm"], "noutra": m["noutra"], "comprar": m["comprar"]}
                   for m in s["noutra_caixa"]],
        "subs": [{"nm": m["nm"], "missing": m["missing"], "alt": m["alt"],
                  "onde": m["alt_onde"]} for m in s["subs"]],
    }


def payload(con, rep, editable=False):
    nomes = {c["nm"] for c in rep["conflitos"]}
    for s in rep["slots"]:
        nomes |= {n for _b, n, _q in s["cards"]}
    for k in ("venda", "venda_rl", "guardar", "retidos"):
        nomes |= {r["nm"] for r in rep[k]}
    nomes |= {m["nm"] for m in rep["arrumacao"]["movimentos"]}
    imgs = _img_map(con, sorted(nomes))
    cfs = {c["nm"] for c in rep["conflitos"]}

    geral: dict[str, dict] = {}
    for s in rep["slots"]:
        for m in s["missing"]:
            if not m["comprar"]:
                continue
            g = geral.setdefault(m["nm"], {"nm": m["nm"], "q": 0, "cost": 0.0})
            g["q"] += m["comprar"]
            g["cost"] = round(g["cost"] + (m["cost"] or 0), 2)

    def venda_bloco(chave, copias, total):
        return {"linhas": [{"nm": r["nm"], "q": r["q"], "local": r["local"],
                            "set": (r["set_code"] or "").upper(), "fin": r["finish"],
                            "lang": r["lang"], "unit": r["unit"],
                            "total": r["total"], "rl": bool(r["rl"]),
                            "reason": r["reason"], "sid": imgs.get(r["nm"])}
                           for r in rep[chave]],
                "copias": rep[copias], "total": rep[total]}

    arr = rep["arrumacao"]
    return {
        "gerado": con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or "",
        "hoje": date.today().isoformat(),
        "editable": bool(editable),
        "caixas": [_caixa_payload(s, imgs, cfs) for s in rep["slots"]],
        "resumo": {"montados": sum(1 for s in rep["slots"] if s.get("montado")),
                   "permanentes": sum(1 for s in rep["slots"] if s["permanente"]),
                   "candidatos": sum(1 for s in rep["slots"] if not s["permanente"]),
                   "comprar": rep["comprar_total"], "noutra": rep["noutra_total"],
                   "custo": rep["custo_total"], "venda": rep["total"],
                   "venda_rl": rep["total_rl"], "arrumar": arr["copias"]},
        "compras": sorted(geral.values(), key=lambda g: -g["cost"]),
        "partilhadas": [{"nm": c["nm"], "pedido": c["pedido"], "tenho": c["tenho"],
                         "sid": imgs.get(c["nm"]), "por_slot": c["por_slot"],
                         "ficam_com": c["ficam_com"], "ficam_sem": c["ficam_sem"]}
                        for c in rep["conflitos"]],
        "venda": {"normal": venda_bloco("venda", "copias", "total"),
                  "rl": venda_bloco("venda_rl", "copias_rl", "total_rl"),
                  "guardar": venda_bloco("guardar", "copias_guardar", "total_guardar"),
                  "retidos": venda_bloco("retidos", "copias_retidas", "total_retido")},
        "arrumar": {"por_origem": arr["por_origem"], "por_destino": arr["por_destino"],
                    "copias": arr["copias"], "linhas": arr["linhas"],
                    "csv": loadout.csv_arrumacao(arr)},
    }


def build(con, out_path=None, editable=False, rep=None):
    out = Path(out_path) if out_path else (ROOT / "deckboxes.html")
    rep = rep if rep is not None else loadout.report(con)
    dados = payload(con, rep, editable=editable)
    out.write_text(_html(dados), encoding="utf-8")
    return out


def _html(dados):
    return (_TMPL.replace("%META%", paginas.META)
            .replace("%TEMA%", paginas.TEMA)
            .replace("%TABS%", TABS)
            # O `</` escapado é o que impede um nome de carta com `</script>` de
            # fechar a etiqueta a meio do payload.
            .replace("%DADOS%", json.dumps(dados, ensure_ascii=False)
                     .replace("</", "<\\/")))


def html_page(con, editable=False, rep=None):
    """A página como texto — é o que o `webapp.py` serve sem escrever no disco."""
    return _html(payload(con, rep if rep is not None else loadout.report(con),
                         editable=editable))


_TMPL = r"""<!doctype html><html lang="pt-PT"><head>%META%
<title>Deckboxes</title><style>
%TEMA%
 :root{--r:12px;--r2:16px}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);
      font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      padding-bottom:env(safe-area-inset-bottom)}
 .wrap{max-width:1180px;margin:0 auto;padding:18px 14px 70px}
 a{color:var(--accent)}
 h1{margin:0;font-size:22px;font-weight:800;letter-spacing:-.02em}
 h2{font-size:13px;margin:22px 0 4px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.07em;font-weight:700} h2 .n{color:var(--dim);font-weight:600}
 h3{font-size:14px;margin:16px 0 6px;font-weight:700}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px} .lead b{color:var(--ink2)}
 .dim{color:var(--dim)}
 /* navegação entre páginas */
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
 .tabs a{flex:1 1 118px;text-align:center;padding:11px 8px;border-radius:var(--r);
   background:var(--card);border:1px solid var(--line);color:var(--ink);
   text-decoration:none;font-weight:600;font-size:14px;transition:.15s}
 .tabs a:hover{border-color:var(--accent)}
 .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 /* fila de abas: uma por deck (a ideia do riftvault) */
 .decktabs{display:flex;gap:6px;overflow-x:auto;padding:4px 0 8px;margin:6px -14px 10px;
   padding-inline:14px;scrollbar-width:thin;-webkit-overflow-scrolling:touch}
 .dt{flex:0 0 auto;display:flex;flex-direction:column;gap:1px;align-items:flex-start;
   padding:8px 12px;border-radius:var(--r);background:var(--card);
   border:1px solid var(--line);color:var(--ink2);cursor:pointer;font:inherit;
   font-size:13px;font-weight:600;line-height:1.25;white-space:nowrap;transition:.12s}
 .dt:hover{border-color:var(--line2)}
 .dt small{font-size:11px;font-weight:600;color:var(--muted);
   font-variant-numeric:tabular-nums}
 .dt.on{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent);color:#fff}
 .dt.on small{color:#c9d8ff}
 .dt .pin{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:5px;
   vertical-align:middle}
 .pin.ok{background:var(--add)} .pin.mid{background:var(--gold)} .pin.low{background:var(--warn)}
 .dt.cand{border-style:dashed;opacity:.9}
 /* cabeçalho de uma caixa */
 .box{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:15px}
 .box+.box{margin-top:12px}
 .btop{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
   flex-wrap:wrap}
 .btop b{font-size:17px;letter-spacing:-.01em}
 .pct{font-weight:800;font-size:19px;font-variant-numeric:tabular-nums}
 .pct.dim{color:var(--muted)}
 .bar{position:relative;height:8px;background:#0a0d13;border-radius:999px;
   overflow:hidden;margin:9px 0}
 .bar i{position:absolute;left:0;top:0;bottom:0;border-radius:999px;
   transition:width .3s}
 .badges{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:8px 0}
 .bdg{font-size:11px;padding:3px 9px;border-radius:20px;background:#1e2531;
   color:var(--muted);white-space:nowrap}
 .bdg.ok{background:#123020;color:var(--add)} .bdg.wt{background:#241a10;color:var(--gold)}
 .bdg.pt{background:#101c2e;color:#7fa8ff} .bdg.fo{background:#2a2410;color:var(--gold)}
 .bdg.perm{background:#1b2c4d;color:#9dbcff;font-weight:700}
 .bdg.cand{background:#241a10;color:var(--gold);font-weight:700}
 .nums{display:flex;flex-wrap:wrap;gap:6px 10px;margin:8px 0}
 .num{background:var(--card2);border:1px solid var(--line);border-radius:10px;
   padding:6px 10px;font-size:12px;color:var(--muted);flex:1 1 auto;min-width:112px}
 .num b{display:block;font-size:16px;color:var(--ink);font-weight:800;
   font-variant-numeric:tabular-nums}
 .num.buy b{color:var(--warn)} .num.get b{color:#7fa8ff} .num.eur b{color:var(--gold)}
 .nota{color:var(--dim);font-size:11.5px;margin:4px 0 0}
 .orig{color:var(--muted);font-size:12px;margin:6px 0 0}
 .orig b{color:var(--ink);font-variant-numeric:tabular-nums}
 .vaziomsg{background:#241a10;border:1px solid #6a4f2f;border-radius:10px;
   padding:10px 12px;margin-top:10px;font-size:13px;color:#f0dcc0}
 /* grelha de cartas */
 .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(58px,1fr));
   gap:5px;margin-top:10px}
 .cd{position:relative;border-radius:6px;aspect-ratio:.716;background:#0c0f14;
   overflow:hidden}
 .cd img{width:100%;height:100%;object-fit:cover;display:block}
 .cd.have{box-shadow:0 0 0 2px var(--add)}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.75) brightness(.5)}
 .cd.sub{box-shadow:0 0 0 2px var(--gold)} .cd.sub img{filter:grayscale(.35) brightness(.68)}
 .cd .cq{position:absolute;bottom:2px;left:2px;background:#000d;color:#fff;
   font-size:10px;font-weight:700;padding:0 4px;border-radius:5px;
   font-variant-numeric:tabular-nums}
 .cd .cf{position:absolute;top:2px;right:2px;background:var(--warn);color:#160a06;
   font-size:9px;font-weight:800;width:15px;height:15px;line-height:15px;
   text-align:center;border-radius:4px}
 .cd .onde{position:absolute;left:0;right:0;bottom:0;background:#000000cc;
   color:var(--gold);font-size:9px;line-height:1.25;padding:2px 3px;
   text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 /* blocos de detalhe */
 .blk{margin-top:11px;background:var(--card2);border:1px solid var(--line);
   border-radius:var(--r);padding:10px 12px;font-size:12.5px;color:var(--muted)}
 .blk>b{color:var(--gold);display:block;margin-bottom:5px;font-size:12px}
 .blk ul{margin:0;padding-left:17px} .blk li{padding:1.5px 0}
 .blk li b{color:var(--ink)}
 .blk.onde{background:#0e1620;border-color:#25415e} .blk.onde>b{color:#7fa8ff}
 .blk.onde li b{color:#7fa8ff}
 .flh{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:700;
   color:#e2795b;flex-wrap:wrap} .flh .dim{font-weight:400} .flh .cpbtn{margin-left:auto}
 .mrk{font-size:10px;font-weight:800;padding:1px 6px;border-radius:5px;
   background:#2a2410;color:var(--gold)}
 ul.fl{list-style:none;margin:7px 0 0;padding:0;font-size:12.5px}
 ul.fl li{display:flex;gap:7px;padding:2px 0} ul.fl b{color:var(--gold);
   font-variant-numeric:tabular-nums}
 ul.fl .pz{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums}
 #v-compras ul.fl{column-width:230px;column-gap:22px} #v-compras ul.fl li{break-inside:avoid}
 .btn,.cpbtn{font:inherit;font-size:12px;font-weight:700;padding:7px 13px;
   border-radius:20px;border:1px solid var(--line);background:#1a2230;
   color:var(--ink2);cursor:pointer;transition:.12s}
 .btn:hover,.cpbtn:hover{border-color:var(--accent);color:#fff}
 .btn.pri{background:var(--accent);border-color:var(--accent);color:#fff}
 .btn.warn{background:#2a1a12;border-color:#6a4f2f;color:var(--gold)}
 .cpbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .acts{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px;
   border-top:1px solid var(--line);padding-top:11px}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
 /* vista "Todas" */
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:11px}
 .mini{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:13px;cursor:pointer;transition:.12s;text-align:left;font:inherit;color:inherit}
 .mini:hover{border-color:var(--line2);transform:translateY(-1px)}
 .mini.cand{border-style:dashed}
 /* partilhadas */
 .cfgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}
 .cfrow{display:flex;gap:10px;background:var(--card);border:1px solid var(--line);
   border-radius:var(--r);padding:10px}
 .cfrow .cd{width:52px;flex:0 0 52px}
 .cfb{min-width:0;display:flex;flex-direction:column;gap:3px}
 .cfb b{font-size:13.5px} .cfb .dim{font-size:11.5px}
 .csl{display:flex;flex-wrap:wrap;gap:3px;margin-top:2px}
 .cs{font-size:10.5px;padding:2px 7px;border-radius:5px;font-variant-numeric:tabular-nums}
 .cs.ok{background:#0f2418;color:var(--add)} .cs.no{background:#2a1414;color:#ff8f8f}
 /* venda */
 details.vblk{background:var(--card);border:1px solid var(--line);
   border-radius:var(--r);padding:11px 13px;margin-bottom:10px}
 details.vblk>summary{cursor:pointer;font-weight:700;font-size:14px;color:var(--ink);
   display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
 .vtot{color:var(--gold);font-variant-numeric:tabular-nums;font-weight:800}
 table.vt{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:9px}
 table.vt th{text-align:left;color:var(--dim);font-weight:600;font-size:10.5px;
   text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);
   padding:5px 6px}
 table.vt td{padding:4px 6px;border-bottom:1px solid #1a212c}
 table.vt tr:hover td{background:#141a24}
 table.vt td.q{color:var(--gold);font-weight:700;text-align:right;
   font-variant-numeric:tabular-nums}
 table.vt td.dim{color:var(--muted)}
 table.vt td.pz{text-align:right;font-variant-numeric:tabular-nums}
 table.vt td.tot{color:var(--gold);font-weight:700}
 .rl{font-size:9px;font-weight:800;padding:1px 4px;border-radius:4px;
   background:#3a1f1f;color:#ff9f8f;vertical-align:middle}
 /* arrumar */
 .arr{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:13px;margin-bottom:11px}
 .arrh{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
   flex-wrap:wrap;margin-bottom:7px}
 .arrh b{font-size:15px} .arrh span{color:var(--muted);font-size:12px}
 .mv{display:flex;align-items:center;gap:9px;padding:6px 4px;
   border-bottom:1px solid #1a212c;font-size:13px}
 .mv:last-child{border-bottom:0}
 .mv input{width:19px;height:19px;flex:0 0 19px;accent-color:var(--add);cursor:pointer}
 .mv.feito{opacity:.4;text-decoration:line-through}
 .mv .q{color:var(--gold);font-weight:800;font-variant-numeric:tabular-nums;
   flex:0 0 auto;min-width:26px}
 .mv .nm{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
   white-space:nowrap}
 .mv .to{color:var(--muted);font-size:12px;flex:0 0 auto;max-width:45%;
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .seg{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}
 .seg button{font:inherit;font-size:12.5px;font-weight:600;padding:7px 14px;
   border-radius:20px;border:1px solid var(--line);background:var(--card);
   color:var(--muted);cursor:pointer}
 .seg button.on{background:#1b2c4d;border-color:var(--accent);color:#fff}
 .empty{color:var(--muted);font-size:13.5px;background:var(--card2);
   border:1px dashed var(--line2);border-radius:var(--r);padding:18px;text-align:center}
 .toast{position:fixed;left:50%;transform:translateX(-50%);bottom:22px;z-index:9;
   background:#1b2c4d;border:1px solid var(--accent);color:#fff;font-size:13px;
   padding:10px 16px;border-radius:22px;box-shadow:0 8px 26px #0009}
 footer{margin-top:28px;color:var(--muted);font-size:12.5px;
   border-top:1px solid var(--line);padding-top:14px}
 @media(max-width:640px){
   .wrap{padding:14px 11px 60px} h1{font-size:20px}
   .tabs a{flex:1 1 calc(50% - 8px);font-size:13px;padding:10px 6px}
   .cards{grid-template-columns:repeat(auto-fill,minmax(50px,1fr))}
   table.vt td.rz,table.vt th.rz{display:none}
   .num{min-width:calc(50% - 6px)}
 }
</style></head><body><div class="wrap">
<header><h1>🧰 Deckboxes</h1>
<div class="lead" id="resumo"></div>
%TABS%
</header>
<nav class="decktabs" id="decktabs" aria-label="Caixas"></nav>
<main id="vista"></main>
<footer>
Uma cópia física entra numa caixa e <b>só numa</b> — por isso os números aqui são mais
baixos que os da página <b>Decks permanentes</b>, onde cada deck conta a coleção inteira.
<b style="color:var(--add)">Verde</b> = está nesta caixa ·
<b style="color:var(--gold)">âmbar</b> = tens a carta mas não está aqui (ou está
<b>noutra caixa</b> — diz qual e quantas, vais lá buscá-la, não se compra — ou não serve
esta caixa na língua/acabamento) · <b style="color:var(--warn)">vermelho</b> = não tens
nenhuma, é compra · <b>⚔</b> = partilhada com outra caixa.
Os <b>permanentes</b> escolhem as cartas primeiro; um <b>candidato</b> fica com o que
sobrar. Quem manda no loadout é o <code>colecao_config.json → loadout</code>; para mexer
nele com botões, corre <code>python webapp.py</code> no PC (porto 8771).
A lista para vender é uma <b>sugestão a confirmar</b>. Atualiza diariamente.
</footer>
</div>
<script id="dados" type="application/json">%DADOS%</script>
<script>
const D = JSON.parse(document.getElementById('dados').textContent);
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const eur = v => v ? (v.toFixed(2).replace('.', ',') + ' €') : '—';
const art = sid => sid
  ? `https://cards.scryfall.io/small/front/${sid[0]}/${sid[1]}/${sid}.jpg` : '';
const cor = p => p >= 90 ? 'var(--add)' : p >= 60 ? 'var(--gold)' : 'var(--warn)';
const pin = p => p >= 90 ? 'ok' : p >= 60 ? 'mid' : 'low';

/* Estado no browser: a aba aberta, o filtro e o que já foi arrumado. É a mesma
   ideia do checkmark "atualizado" do meusdecks — o que é do André fica no
   aparelho dele, não na base de dados. */
const KEY = 'deckboxes.v2';
let P = {};
try { P = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { P = {}; }
P.feitos = P.feitos || {};
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(P)); } catch (e) {} };
let aba = P.aba || 'todas';
let filtro = P.filtro || 'tudo';

function toast(txt) {
  const d = document.createElement('div');
  d.className = 'toast'; d.textContent = txt;
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 2600);
}

/* ---------------------------------------------------------------- cabeçalho */
function renderResumo() {
  const r = D.resumo;
  $('#resumo').innerHTML =
    `${D.caixas.length} caixas (<b>${r.permanentes}</b> permanentes · `
    + `${r.candidatos} candidatas) · comprar <b>${r.comprar}</b> cópias por `
    + `<b>${eur(r.custo)}</b> · ir buscar a outra caixa <b>${r.noutra}</b> · `
    + `arrumar <b>${r.arrumar}</b> · vender <b>${eur(r.venda)}</b>`
    + (D.editable ? ' · <b style="color:var(--add)">modo edição</b>' : '')
    + `<br><span class="dim">dados de ${esc(D.gerado)}</span>`;
}

function renderTabs() {
  const nav = $('#decktabs');
  const fixas = [['todas', '▦ Todas', ''], ['arrumar', '📥 Arrumar',
                  D.arrumar.copias + ' cópias'],
                 ['partilhadas', '🔁 Partilhadas', D.partilhadas.length + ' cartas'],
                 ['comprar', '🛒 Comprar', D.resumo.comprar + ' cópias'],
                 ['vender', '💰 Vender', eur(D.resumo.venda)]];
  let h = '';
  for (const [id, lbl, sub] of fixas) {
    h += `<button class="dt${aba === id ? ' on' : ''}" data-aba="${id}">${lbl}`
       + (sub ? `<small>${esc(sub)}</small>` : '') + `</button>`;
  }
  for (const c of D.caixas) {
    const p = c.vazio ? '—' : c.pct + '%';
    h += `<button class="dt${aba === c.slot ? ' on' : ''}`
       + `${c.permanente ? '' : ' cand'}" data-aba="${c.slot}">`
       + `<span><i class="pin ${c.vazio ? 'low' : pin(c.pct)}"></i>${esc(c.nome)}</span>`
       + `<small>${p}${c.vazio ? '' : ` · ${c.tenho}/${c.precisa}`}</small></button>`;
  }
  nav.innerHTML = h;
  for (const b of nav.querySelectorAll('.dt')) b.onclick = () => ir(b.dataset.aba);
  const on = nav.querySelector('.dt.on');
  if (on) on.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}

function ir(id) { aba = id; P.aba = id; save(); renderTabs(); render(); }

/* ------------------------------------------------------------------ caixa */
function cardTile(c) {
  const onde = c.est === 'sub' && Object.keys(c.noutra).length
    ? Object.entries(c.noutra).map(([k, v]) => `${v}× ${k}`).join(', ') : '';
  const tit = [c.nm, c.est === 'have' ? `tens ${c.got}/${c.need}`
    : `falta ${c.missing}`,
    onde ? 'em ' + onde : '',
    Object.entries(c.alt).map(([k, v]) => `${v}× ${k}`).join('; '),
    c.comprar ? `comprar ${c.comprar}` : '',
    c.lotes.map(l => `${l.q}× ${l.local}`).join(' · '),
    c.so_de.length ? 'só da variante ' + c.so_de.join('/') : ''
  ].filter(Boolean).join(' — ');
  const q = c.need > 1 || c.est !== 'have'
    ? `<span class="cq">${c.got}/${c.need}</span>` : '';
  return `<div class="cd ${c.est}" title="${esc(tit)}">`
    + (c.sid ? `<img loading="lazy" src="${art(c.sid)}" alt="${esc(c.nm)}">` : '')
    + q + (c.cf ? '<span class="cf">⚔</span>' : '')
    + (onde ? `<span class="onde">${esc(onde)}</span>` : '') + '</div>';
}

function badges(c) {
  let h = c.permanente
    ? '<span class="bdg perm">★ permanente</span>'
    : '<span class="bdg cand">candidato</span>';
  if (c.montado) h += '<span class="bdg ok">✅ montado</span>';
  else if (c.por_confirmar || c.vazio) h += '<span class="bdg wt">❓ por confirmar</span>';
  else h += '<span class="bdg">🔧 a montar</span>';
  for (const [ico, txt] of c.regras) {
    const cls = /foil/.test(txt) ? 'fo' : 'pt';
    h += `<span class="bdg ${cls}">${ico} ${esc(txt)}</span>`;
  }
  if (c.variantes.length) h += `<span class="bdg">⇄ ${c.variantes.length} variantes</span>`;
  h += `<span class="bdg">#${c.prioridade} na alocação</span>`;
  return h;
}

function wantlistHTML(itens, marca, id) {
  if (!itens.length) return '';
  const li = itens.map(m => `<li><b>${m.q}×</b> ${esc(m.nm)}`
    + `<span class="pz">${eur(m.cost)}</span></li>`).join('');
  const txt = itens.map(m => `${m.q} ${m.nm}`).join('\n');
  return `<div class="blk" id="${id || ''}"><div class="flh">🛒 Comprar`
    + (marca ? ` <span class="mrk">${esc(marca)}</span>` : '')
    + `<span class="dim">${itens.length} cartas</span>`
    + `<button class="cpbtn" onclick="copiar(this)">copiar</button></div>`
    + `<ul class="fl">${li}</ul>`
    + `<textarea class="cmk" readonly>${esc(txt)}</textarea></div>`;
}

function caixaHTML(c, compacta) {
  if (c.vazio) {
    return `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
      + `<span class="pct dim">—</span></div><div class="badges">${badges(c)}</div>`
      + `<div class="nota">${esc(c.nota)}</div>`
      + `<div class="vaziomsg">Caixa por atribuir — não escolhi por ti. `
      + `Vê o top-3 que estás mais perto de concluir na página `
      + `<a href="metagame.html">Metagame</a> e diz-me o deck.</div>`
      + (D.editable ? acoesHTML(c) : '') + `</div>`;
  }
  let h = `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
    + `<span class="pct" style="color:${cor(c.pct)}">${c.pct}%</span></div>`
    + `<div class="bar"><i style="width:${Math.max(c.pct, 2)}%;background:${cor(c.pct)}"></i></div>`
    + `<div class="badges">${badges(c)}</div>`
    + `<div class="nums">`
    + `<div class="num">na caixa<b>${c.tenho}/${c.precisa}</b></div>`
    + `<div class="num buy">comprar<b>${c.comprar}</b></div>`
    + `<div class="num get">ir buscar<b>${c.noutra}</b></div>`
    + `<div class="num eur">fechar por<b>${eur(c.custo)}</b></div></div>`
    + `<div class="nota">${esc(c.nota)}</div>`;
  const orig = Object.entries(c.origens);
  if (orig.length) {
    h += `<div class="orig">🗂️ tirar de: `
      + orig.map(([k, v]) => `${esc(k)} <b>${v}</b>`).join(' · ') + `</div>`;
  }
  if (compacta) return h + `</div>`;

  const cartas = c.cartas.filter(x => filtro === 'tudo' || x.est !== 'have');
  h += `<div class="cards">${cartas.map(cardTile).join('')}</div>`;
  if (!cartas.length) {
    h += `<p class="empty">Nada em falta nesta caixa — está completa.</p>`;
  }
  if (c.buscar.length) {
    const li = c.buscar.map(m => `<li>${esc(m.nm)} — `
      + Object.entries(m.noutra).map(([k, v]) => `<b>${v}×</b> em ${esc(k)}`).join('; ')
      + (m.comprar ? ` <span class="dim">(comprar mais ${m.comprar})</span>` : '')
      + `</li>`).join('');
    h += `<div class="blk onde"><b>📦 ir buscar a outra caixa — ${c.noutra} cópias</b>`
      + `<ul>${li}</ul></div>`;
  }
  if (c.subs.length) {
    const li = c.subs.map(m => `<li>${esc(m.nm)} — falta ${m.missing}: `
      + Object.entries(m.alt).map(([k, v]) => `tens <b>${v}</b> que ${esc(k)}`).join('; ')
      + (Object.keys(m.onde).length ? ` <span class="dim">(em `
        + esc(Object.entries(m.onde).map(([k, v]) => `${k}: ${v}`).join(', ')) + `)</span>` : '')
      + `</li>`).join('');
    h += `<div class="blk"><b>↻ tens a carta, não serve a caixa</b><ul>${li}</ul></div>`;
  }
  h += wantlistHTML(c.wantlist, c.marca);
  if (D.editable) h += acoesHTML(c);
  return h + `</div>`;
}

/* Os botões só existem no modo edição — no site publicado nem chegam ao HTML,
   que é a única maneira de não prometer o que a página não pode cumprir. */
function acoesHTML(c) {
  const i = D.caixas.findIndex(x => x.slot === c.slot);
  return `<div class="acts">`
    + `<button class="btn ${c.permanente ? '' : 'pri'}" data-act="permanente" `
    + `data-slot="${esc(c.slot)}">`
    + (c.permanente ? 'Deixar de ser permanente' : '★ Tornar permanente') + `</button>`
    + `<button class="btn" data-act="subir" data-slot="${esc(c.slot)}"`
    + `${i === 0 ? ' disabled' : ''}>↑ Subir</button>`
    + `<button class="btn" data-act="descer" data-slot="${esc(c.slot)}"`
    + `${i === D.caixas.length - 1 ? ' disabled' : ''}>↓ Descer</button>`
    + `<button class="btn ${c.montado ? '' : 'warn'}" data-act="montado" `
    + `data-slot="${esc(c.slot)}">`
    + (c.montado ? 'Tirar da caixa' : '📦 Sleevado e na caixa') + `</button></div>`;
}

/* ------------------------------------------------------------- vistas */
function vistaTodas() {
  const bloco = (titulo, lista, lead) => !lista.length ? '' :
    `<h2>${titulo} <span class="n">${lista.length}</span></h2>`
    + `<p class="lead">${lead}</p><div class="grid">`
    + lista.map(c => `<button class="mini${c.permanente ? '' : ' cand'}" `
        + `data-slot="${esc(c.slot)}">${caixaHTML(c, true)}</button>`).join('')
    + `</div>`;
  const perm = D.caixas.filter(c => c.permanente);
  const cand = D.caixas.filter(c => !c.permanente);
  return bloco('★ Permanentes', perm,
      'Escolhem as cartas primeiro, por esta ordem. É a tua prioridade máxima.')
    + bloco('Candidatos', cand,
      'Só recebem o que sobrar dos permanentes. Para um começar a receber cartas, '
      + 'marca-o como permanente (no modo edição, <code>python webapp.py</code>).');
}

function vistaArrumar() {
  const a = D.arrumar;
  if (!a.linhas) {
    return `<h2>📥 Arrumar</h2><p class="empty">Nada a arrumar: a estante já está `
      + `igual à alocação. Quando comprares cartas novas (fotos em `
      + `<code>pendentes/</code>) ou mudares uma caixa, isto volta a encher-se.</p>`;
  }
  const linha = (m, lado) => {
    const id = `${m.copy_id}|${m.de}|${m.para}|${m.nm}`;
    const feito = !!P.feitos[id];
    return `<label class="mv${feito ? ' feito' : ''}" data-id="${esc(id)}">`
      + `<input type="checkbox"${feito ? ' checked' : ''}>`
      + `<span class="q">${m.q}×</span><span class="nm">${esc(m.nm)}</span>`
      + `<span class="to">${lado === 'origem' ? '→ ' + esc(m.para) : '← ' + esc(m.de)}`
      + `</span></label>`;
  };
  const secao = (mapa, lado, titulo, lead) => {
    let h = `<h2>${titulo}</h2><p class="lead">${lead}</p>`;
    for (const [nome, movs] of Object.entries(mapa)) {
      h += `<div class="arr"><div class="arrh"><b>${esc(nome)}</b>`
        + `<span>${movs.reduce((s, m) => s + m.q, 0)} cópias · ${movs.length} linhas`
        + `</span></div>`
        + movs.map(m => linha(m, lado)).join('') + `</div>`;
    }
    return h;
  };
  return `<h2>📥 Arrumar — ${a.copias} cópias</h2>`
    + `<p class="lead">A diferença entre <b>onde as cartas estão</b> e <b>onde a `
    + `alocação diz que deviam estar</b>. Vai marcando à medida que moves; os `
    + `visto ficam guardados neste aparelho. No fim, <b>já arrumei tudo</b>`
    + (D.editable ? ' grava a arrumação na base de dados (com backup).'
                  : ' descarrega o CSV para me dares.') + `</p>`
    + `<div class="seg"><button class="btn pri" id="arr-fim">✅ Já arrumei tudo</button>`
    + `<button class="btn" id="arr-csv">⬇ CSV (moves-${D.hoje}.csv)</button>`
    + `<button class="btn" id="arr-limpar">Limpar os vistos</button></div>`
    + secao(a.por_origem, 'origem', '🗂️ De cada gaveta (o que se tira)',
        'Abre esta gaveta uma vez e tira tudo o que está aqui.')
    + secao(a.por_destino, 'destino', '📦 Para cada caixa (o que entra)',
        'A mesma lista pelo outro lado: o que cada deckbox recebe.');
}

function vistaPartilhadas() {
  if (!D.partilhadas.length) {
    return `<h2>🔁 Cartas partilhadas</h2><p class="empty">Nenhuma caixa está a `
      + `disputar cartas com outra.</p>`;
  }
  const rows = D.partilhadas.map(c => {
    const det = c.por_slot.map(q => `<span class="cs ${q.levou >= q.pediu ? 'ok' : 'no'}">`
      + `${esc(q.slot)} ${q.levou}/${q.pediu}</span>`).join('');
    const tem = c.ficam_com.join(', ') || 'ninguém';
    const vai = c.ficam_sem.filter(x => c.ficam_com.length && !c.ficam_com.includes(x))
      .join(', ');
    return `<div class="cfrow"><div class="cd sub">`
      + (c.sid ? `<img loading="lazy" src="${art(c.sid)}" alt="">` : '')
      + `</div><div class="cfb"><b>${esc(c.nm)}</b>`
      + `<span class="dim">tens ${c.tenho} para ${c.pedido} pedidas · está em `
      + `<b>${esc(tem)}</b>${vai ? ' · vai buscar: ' + esc(vai) : ''}</span>`
      + `<div class="csl">${det}</div></div></div>`;
  }).join('');
  return `<h2>🔁 Cartas partilhadas entre caixas <span class="n">`
    + `${D.partilhadas.length}</span></h2>`
    + `<p class="lead">Cartas que duas ou mais caixas querem e não chegam para todas. `
    + `<b>Não são compras.</b> A cópia fica na caixa que aloca primeiro (permanentes, `
    + `depois o grupo de formato) e as outras vão lá buscá-la quando forem jogar — é `
    + `por isso que aparecem a âmbar com <b>“em &lt;caixa&gt;”</b> e não somam ao `
    + `custo. Se quiseres os decks todos prontos ao mesmo tempo sem trocas, aí sim: `
    + `compram-se cópias dedicadas.</p><div class="cfgrid">${rows}</div>`;
}

function vistaComprar() {
  return `<h2>🛒 Comprar — todas as caixas</h2>`
    + `<p class="lead">Só o que <b>não existe</b> na coleção, ou existe mas não serve `
    + `na língua/acabamento que a caixa exige. As cartas que estão noutra caixa `
    + `<b>não estão aqui</b>: vão-se buscar. São <b>${D.resumo.noutra}</b> cópias a ir `
    + `buscar contra <b>${D.resumo.comprar}</b> a comprar.</p>`
    + (D.compras.length ? wantlistHTML(D.compras, '', 'v-compras')
       : `<p class="empty">Não falta comprar nada. Está tudo em casa.</p>`);
}

function vistaVender() {
  const bloco = (id, titulo, lead, b, aberto) => !b.linhas.length ? '' :
    `<details class="vblk" id="${id}"${aberto ? ' open' : ''}>`
    + `<summary><span>${titulo}</span><span class="vtot">${b.copias} cópias · `
    + `${eur(b.total)}</span></summary><p class="lead">${lead}</p>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this)">copiar lista`
    + `</button></div><textarea class="cmk" readonly>`
    + esc(b.linhas.slice().sort((x, y) => x.nm.localeCompare(y.nm))
        .map(r => `${r.q} ${r.nm}`).join('\n')) + `</textarea>`
    + `<table class="vt"><thead><tr><th></th><th>carta</th><th>onde está</th>`
    + `<th>edição</th><th>un.</th><th>total</th><th class="rz">porquê</th></tr></thead>`
    + `<tbody>` + b.linhas.map(r => `<tr><td class="q">${r.q}×</td>`
      + `<td>${esc(r.nm)}${r.rl ? ' <span class="rl">RL</span>' : ''}</td>`
      + `<td class="dim">${esc(r.local)}</td>`
      + `<td class="dim">${esc(r.set)} ${/foil|etched/.test(r.fin) ? '✨' : ''} `
      + `${esc((r.lang || '').toUpperCase())}</td>`
      + `<td class="pz">${eur(r.unit)}</td><td class="pz tot">${eur(r.total)}</td>`
      + `<td class="dim rz">${esc(r.reason)}</td></tr>`).join('')
    + `</tbody></table></details>`;
  const V = D.venda;
  return `<h2>💰 Para vender</h2>`
    + `<p class="lead"><b>Sugestão a confirmar.</b> Nada sai da coleção sem tu dizeres. `
    + `É o que sobra depois de encher todas as caixas e de guardar o backup: `
    + `<b>4 por carta</b> na coleção (playset, a somar a Coleção e a Caixa RL — não 4 `
    + `por balde) e <b>1 por deck</b> nas caixas de Commander. <b>Básicas nunca.</b></p>`
    + bloco('v-normal', 'Excedente normal', 'Cópias a mais de cartas que não são '
        + 'Reserved List. É por aqui que se começa: o risco é baixo e o dinheiro é '
        + 'real.', V.normal, true)
    + bloco('v-rl', '⚠️ Reserved List — confirmar uma a uma', 'Cartas que nunca mais '
        + 'são impressas. A regra dá-as como excedente, mas a decisão não se desfaz — '
        + 'e os preços de cartas antigas na base não são de confiança (ver '
        + '<code>doubts.md</code>). Confere cada uma antes de listar.', V.rl)
    + bloco('v-guardar', '🔒 Guardar — servem um deck do loadout', 'Passariam o limite '
        + 'de 4, mas são substitutos de cartas que faltam a uma caixa: servem o deck e '
        + 'só não fecham o slot por causa da língua ou do acabamento. Vendê-las era '
        + 'comprá-las outra vez.', V.guardar)
    + bloco('v-retidos', '⏳ Retidos — extras de decks montados', 'Baldes com '
        + '<code>reter_extras_meses</code>: guardam-se até 6 meses depois da última '
        + 'utilização. Ainda não há registo de "última utilização", por isso ficam '
        + 'todos — não se vende nada por uma regra que ainda não corre.', V.retidos)
    + (V.normal.linhas.length || V.rl.linhas.length ? '' :
       `<p class="empty">Não há nada a mais para vender.</p>`);
}

/* ------------------------------------------------------------------ render */
function render() {
  const v = $('#vista');
  const caixa = D.caixas.find(c => c.slot === aba);
  if (caixa) {
    v.innerHTML = filtroHTML() + caixaHTML(caixa, false);
  } else if (aba === 'arrumar') { v.innerHTML = vistaArrumar(); }
  else if (aba === 'partilhadas') { v.innerHTML = vistaPartilhadas(); }
  else if (aba === 'comprar') { v.innerHTML = vistaComprar(); }
  else if (aba === 'vender') { v.innerHTML = vistaVender(); }
  else { v.innerHTML = vistaTodas(); }
  ligar();
  window.scrollTo({ top: 0 });
}

function filtroHTML() {
  return `<div class="seg">`
    + `<button class="${filtro === 'tudo' ? 'on' : ''}" data-f="tudo">Todas as cartas</button>`
    + `<button class="${filtro === 'faltam' ? 'on' : ''}" data-f="faltam">Só o que falta</button>`
    + `</div>`;
}

function ligar() {
  for (const b of document.querySelectorAll('[data-f]')) {
    b.onclick = () => { filtro = b.dataset.f; P.filtro = filtro; save(); render(); };
  }
  for (const b of document.querySelectorAll('.mini[data-slot]')) {
    b.onclick = () => ir(b.dataset.slot);
  }
  for (const b of document.querySelectorAll('.acts [data-act]')) {
    b.onclick = () => accao(b.dataset.act, b.dataset.slot, b);
  }
  for (const l of document.querySelectorAll('.mv')) {
    const cb = l.querySelector('input');
    cb.onchange = () => {
      if (cb.checked) P.feitos[l.dataset.id] = 1; else delete P.feitos[l.dataset.id];
      l.classList.toggle('feito', cb.checked);
      save();
    };
  }
  const fim = $('#arr-fim'), csv = $('#arr-csv'), lim = $('#arr-limpar');
  if (csv) csv.onclick = baixarCSV;
  if (lim) lim.onclick = () => { P.feitos = {}; save(); render(); toast('Vistos limpos.'); };
  if (fim) fim.onclick = jaArrumei;
}

function copiar(btn) {
  const c = btn.closest('.blk') || btn.closest('.vblk');
  const t = c && c.querySelector('textarea.cmk');
  if (!t) return;
  const feito = () => { btn.textContent = '✓ copiado'; btn.classList.add('done'); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t.value).then(feito)
      .catch(() => { t.select(); document.execCommand('copy'); feito(); });
  } else { t.select(); try { document.execCommand('copy'); feito(); } catch (e) {} }
}

function baixarCSV() {
  const b = new Blob([D.arrumar.csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = `moves-${D.hoje}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast('CSV descarregado.');
}

/* No site publicado, "já arrumei tudo" só pode dar-te o ficheiro; quem escreve
   na base é o modo edição. Dizê-lo é melhor do que ter um botão que não faz
   nada — foi a lição do banner de só-leitura do riftvault. */
async function jaArrumei() {
  if (!D.editable) {
    baixarCSV();
    toast('Guardado o CSV — dá-mo e eu aplico. (Para aplicar aqui: python webapp.py)');
    return;
  }
  if (!confirm(`Gravar a arrumação de ${D.arrumar.copias} cópias? `
      + `Faz backup da base antes.`)) return;
  try {
    const r = await fetch('api/arrumar', { method: 'POST' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    toast(`Arrumado: ${j.copias} cópias registadas.`);
    P.feitos = {}; save();
    location.reload();
  } catch (e) { toast('Não deu: ' + e.message); }
}

async function accao(act, slot, btn) {
  btn.disabled = true;
  try {
    const r = await fetch('api/caixa', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ act, slot }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    toast('Feito — a alocação foi refeita.');
    location.reload();
  } catch (e) { btn.disabled = false; toast('Não deu: ' + e.message); }
}

if (!D.caixas.some(c => c.slot === aba)
    && !['todas', 'arrumar', 'partilhadas', 'comprar', 'vender'].includes(aba)) {
  aba = 'todas';
}
renderResumo(); renderTabs(); render();
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("deckboxes.html:", build(con))


if __name__ == "__main__":
    main()
