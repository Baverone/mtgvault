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


# `nome -> scryfall_id`: vive no `paginas` desde a revisão de 2026-09-07 (19:00).
# Estava copiado à letra aqui e no `metagame.py`.
_img_map = paginas.img_map


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


def _candidatos(con, rep):
    """`slot -> top-N de arquétipos que ele está mais perto de concluir`.

    André, 2026-09-07 (19:00): *"quero ver os top-3 mais perto de concluir e
    marcar qual vou montar"* — e não só na página do Metagame: também na aba da
    caixa, que é onde ele está quando decide. *"A caixa Pioneer já é Greasefang
    mas mostra também os 3 candidatos."*

    O cálculo é o do `metagame.candidatos` e mais nenhum: duas respostas
    diferentes à mesma pergunta é o padrão que este vault já pagou caro.
    """
    import metagame

    out = {}
    for fmt in metagame.formatos_top():
        s = metagame.slot_do_formato(rep["slots"], fmt)
        if s is None:
            continue
        out[s["slot"]] = [
            {"nome": c["nome"], "subtitulo": c["subtitulo"],
             "archetype_id": c["archetype_id"], "n_lists": c["n_lists"],
             "pct": round(100 * (sum(m["got"] for m in c["linhas"] if not m["basica"])
                                 + sum(m["noutra_q"] for m in c["linhas"]))
                          / max(1, sum(m["need"] for m in c["linhas"]
                                       if not m["basica"]))),
             "comprar": sum(m["comprar"] for m in c["linhas"]),
             "custo": round(sum(m["cost"] or 0 for m in c["linhas"]), 2),
             "escolhido": c["escolhido"], "escolhido_em": c["escolhido_em"]}
            for c in metagame.candidatos(con, fmt, rep)]
    return out


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
        # Caixa DEDICADA (2026-09-07, 19:00): não empresta nem vai buscar. A
        # página tem de o dizer — é o que explica porque é que uma carta que ele
        # TEM aparece na lista de compras desta caixa.
        "dedicado": bool(s.get("dedicado")),
        "congelada": bool(s.get("congelada")),
        "por_confirmar": bool(s.get("por_confirmar")), "vazio": s["vazio"],
        "nota": s["nota"], "fonte": s.get("fonte"), "ref": s.get("ref"),
        "pct": s["pct"], "tenho": s["tenho"], "precisa": s["precisa"],
        "comprar": s["comprar"], "noutra": s["noutra"], "faltam": s["faltam"],
        "custo": s["custo"], "origens": s["origens"],
        # Quantas cópias a comprar não têm preço na base: o "fechar por" é um
        # MÍNIMO, e a página tem de o dizer em vez de o dar como a conta toda.
        "sem_preco": s["sem_preco"],
        # (ícone, texto, classe) — a classe vem do loadout, não de um teste de
        # substring na página (ver `loadout.rotulo_material`).
        "regras": [[i, t, c] for i, t, c in loadout.rotulo_material(s)],
        "req": loadout.requisito_material(s),
        "marca": loadout.marca_wantlist(s),
        "variantes": list(s.get("variantes") or []),
        "cartas": cartas,
        # `mat` é o material que vai DENTRO da linha copiada (`2 Swords [PT]`).
        # Vem da linha e não da caixa porque uma compra partilhada obedece ao
        # material do POOL, que pode ser mais exigente do que o desta caixa.
        "wantlist": sorted(({"nm": m["nm"], "q": m["comprar"], "cost": m["cost"],
                             "mat": m.get("marca_compra") or ""}
                            for m in s["missing"] if m["comprar"] > 0),
                           key=lambda x: x["nm"]),
        # `futura`: a parte do "ir buscar" que ainda não está em casa — é uma
        # cópia que outra caixa vai comprar e partilhar. Dizê-lo é a diferença
        # entre uma indicação e uma mentira.
        "buscar": [{"nm": m["nm"], "noutra": m["noutra"], "comprar": m["comprar"],
                    "futura": m.get("noutra_futura") or {}}
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

    # A LISTA DE COMPRAS, com a atribuição a caixas. Só `{nm, q, cost}` não
    # chegava: uma compra sem dizer PARA QUE CAIXA e EM QUE LÍNGUA/ACABAMENTO é
    # meio caminho para comprar a versão errada — 4 Swords to Plowshares EN não
    # servem a caixa de Premodern, que as quer PT e até ao Scourge.
    # E, desde 2026-09-07, com a PARTILHA: `q` é o que se compra mesmo (o máximo
    # de uma caixa, não a soma) e o `para` mostra também as caixas que a compra
    # serve sem pagar — `serve: true`. Ver `loadout.partilhar_compras`.
    servidas: dict[str, list[dict]] = {}
    # Quantas caixas partilham a compra desta carta. NÃO é `len(para)`: a mesma
    # carta pode ser comprada em dois materiais e só um deles ser partilhado — o
    # Lion's Eye Diamond compra-se 2 em PT (Premodern, sozinho) e 1 em EN nonfoil
    # para as duas caixas de cEDH. Aí o chip diz 2 caixas, não 3.
    n_partilha: dict[str, int] = {}
    for p in rep.get("partilhas") or []:
        servidas[p["nm"]] = [
            {"caixa": c["caixa"], "slot": c["slot"], "q": c["pediu"], "cost": 0.0,
             "unit": None, "req": p["req"], "mat": p["marca"], "serve": True}
            for c in p["caixas"] if not c["compra"]]
        n_partilha[p["nm"]] = max(n_partilha.get(p["nm"], 0), len(p["caixas"]))
    geral: dict[str, dict] = {}
    for s in rep["slots"]:
        for m in s["missing"]:
            if not m["comprar"]:
                continue
            g = geral.setdefault(m["nm"], {"nm": m["nm"], "q": 0, "cost": 0.0,
                                           "unit": None, "para": [], "req": "",
                                           "mat": "", "partilhada": 0})
            g["q"] += m["comprar"]
            g["cost"] = round(g["cost"] + (m["cost"] or 0), 2)
            # O preço por cópia é o mais alto das caixas que a pedem — é o que
            # decide se a carta entra no bolo das "caras", e por baixo era pior.
            if m["unit"] and (g["unit"] is None or m["unit"] > g["unit"]):
                g["unit"] = m["unit"]
            g["para"].append({"caixa": s["nome"], "slot": s["slot"],
                              "q": m["comprar"], "cost": m["cost"],
                              "unit": m["unit"],
                              # O material vem da LINHA: numa compra partilhada
                              # é o do pool (o mais exigente das caixas), não o
                              # desta caixa. Comprar uma foil PT porque o Duel
                              # Commander não exige língua deixava o Modern sem
                              # a carta na mesma.
                              "req": m.get("req_compra") or "",
                              "mat": m.get("marca_compra") or ""})
    for nm, extra in servidas.items():
        if nm in geral:
            geral[nm]["para"].extend(extra)
    for g in geral.values():
        # Duas caixas podem querer a mesma carta em material diferente; nesse
        # caso são duas compras e a linha di-lo, em vez de escolher uma.
        g["req"] = " / ".join(r for r in dict.fromkeys(p["req"] for p in g["para"]) if r)
        g["mat"] = " / ".join(r for r in dict.fromkeys(p["mat"] for p in g["para"]) if r)
        g["partilhada"] = n_partilha.get(g["nm"], 0)
        g["para"].sort(key=lambda p: (bool(p.get("serve")), -p["q"], p["caixa"]))

    def venda_bloco(chave, copias, total):
        return {"linhas": [{"nm": r["nm"], "q": r["q"], "local": r["local"],
                            "set": (r["set_code"] or "").upper(), "fin": r["finish"],
                            # Quem decide se é foil é o Python (`FOIL_FINISHES`).
                            # A página fazia `/foil|etched/.test(fin)` e punha ✨
                            # em cópias `nonfoil`, que contém "foil".
                            "foil": loadout.e_foil(r["finish"]),
                            "lang": r["lang"], "unit": r["unit"],
                            "total": r["total"], "rl": bool(r["rl"]),
                            "reason": r["reason"], "sid": imgs.get(r["nm"])}
                           for r in rep[chave]],
                "copias": rep[copias], "total": rep[total]}

    arr = rep["arrumacao"]
    # As regras de cada caixa, por NOME: é assim que o `conflitos` identifica
    # quem disputa a carta. A aba Partilhadas precisa delas para dizer que uma
    # partilha respeita as regras de quem vai buscar — o Enchantress vai buscar
    # a Swords to Plowshares PT ao UW Replenish, nunca a foil do Cloud.
    reqs = {s["nome"]: loadout.requisito_material(s) for s in rep["slots"]}
    return {
        "gerado": con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or "",
        "hoje": date.today().isoformat(),
        "editable": bool(editable),
        "caixas": [_caixa_payload(s, imgs, cfs) for s in rep["slots"]],
        # O top-N por caixa por escolher (Standard/Pioneer/Legacy) — o "vou
        # montar este" também mora aqui, não só no metagame.html.
        "candidatos": _candidatos(con, rep),
        "resumo": {"montados": sum(1 for s in rep["slots"] if s.get("montado")),
                   "permanentes": sum(1 for s in rep["slots"] if s["permanente"]),
                   "candidatos": sum(1 for s in rep["slots"] if not s["permanente"]),
                   "comprar": rep["comprar_total"], "noutra": rep["noutra_total"],
                   # Cópias que a partilha poupou (o que a soma caixa a caixa
                   # pedia a mais). Mostrado na aba Comprar.
                   "poupado": rep.get("poupado_total", 0),
                   "sem_preco": rep.get("sem_preco_total", 0),
                   "custo": rep["custo_total"], "venda": rep["total"],
                   "venda_rl": rep["total_rl"], "arrumar": arr["copias"]},
        "compras": sorted(geral.values(), key=lambda g: -g["cost"]),
        "partilhadas": [{"nm": c["nm"], "pedido": c["pedido"], "tenho": c["tenho"],
                         "sid": imgs.get(c["nm"]),
                         "por_slot": [dict(q, req=reqs.get(q["slot"], ""))
                                      for q in c["por_slot"]],
                         "ficam_com": c["ficam_com"], "ficam_sem": c["ficam_sem"]}
                        for c in rep["conflitos"]],
        "venda": {"normal": venda_bloco("venda", "copias", "total"),
                  "rl": venda_bloco("venda_rl", "copias_rl", "total_rl"),
                  "guardar": venda_bloco("guardar", "copias_guardar", "total_guardar"),
                  "retidos": venda_bloco("retidos", "copias_retidas", "total_retido")},
        "arrumar": {"por_origem": arr["por_origem"], "por_destino": arr["por_destino"],
                    "copias": arr["copias"], "linhas": arr["linhas"],
                    # As caixas CONGELADAS não se arrumam, actualizam-se: o
                    # "já arrumei tudo" geral não lhes toca e cada uma tem o seu
                    # botão "actualizei" (André, 2026-09-07: *"apenas mexer para
                    # actualizar"*).
                    "actualizacoes": list(arr["actualizacoes"].values()),
                    "copias_actualizar": arr["copias_actualizar"],
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
 .badges{display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap;margin:8px 0}
 /* `white-space:normal` de propósito: com `nowrap`, a etiqueta das fontes
    ("fontes: Colecção + Caixa RL (PT)") transbordava o cartão no desktop em vez
    de partir a linha. Um chip nunca pode ser mais largo do que a caixa. */
 .bdg{font-size:11px;padding:3px 9px;border-radius:20px;background:#1e2531;
   color:var(--muted);white-space:normal;max-width:100%;overflow-wrap:anywhere}
 .bdg.ok{background:#123020;color:var(--add)} .bdg.wt{background:#241a10;color:var(--gold)}
 .bdg.pt{background:#101c2e;color:#7fa8ff} .bdg.fo{background:#2a2410;color:var(--gold)}
 .bdg.ded{background:#2c1b2e;color:#e0a8ea}
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
   font-variant-numeric:tabular-nums;flex:0 0 auto}
 ul.fl .wn{flex:1 1 auto;min-width:0}
 ul.fl .wn small{display:block;color:var(--dim);font-size:11px;line-height:1.35}
 ul.fl .pz{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums;
   flex:0 0 auto}
 .cara{font-size:9px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#3a1f1f;color:#ff9f8f;margin-left:5px;white-space:nowrap}
 .part{font-size:9px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#101c2e;color:#7fa8ff;margin-left:5px;white-space:nowrap}
 .chosen{font-size:9px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#123020;color:var(--add);margin-left:5px;white-space:nowrap}
 .cand-blk .flh{color:#7fa8ff}
 .cand-blk ul.fl li{align-items:flex-start;padding:5px 0;
   border-bottom:1px solid #1a212c}
 .cand-blk ul.fl li:last-child{border-bottom:0}
 .cand-blk ul.fl b{color:var(--ink);min-width:38px}
 .cand-blk .pz{display:flex;align-items:center;gap:8px}
 .cand-blk .nota{margin-top:8px}
 #v-compras ul.fl{column-width:280px;column-gap:22px} #v-compras ul.fl li{break-inside:avoid}
 .selc{font:inherit;font-size:12.5px;font-weight:600;padding:7px 12px;
   border-radius:20px;border:1px solid var(--line);background:var(--card);
   color:var(--ink);cursor:pointer;max-width:100%}
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
 .cfb .creq{font-size:11px;color:var(--dim);line-height:1.4;margin-top:1px}
 .cfb .creq b{color:var(--muted);font-weight:700}
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
<nav class="decktabs" id="decktabs" role="tablist" aria-label="Caixas e vistas"></nav>
<main id="vista" role="tabpanel" tabindex="-1" aria-live="polite"></main>
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
/* Acima disto (por cópia) a compra é uma decisão à parte, não uma ida ao
   Cardmarket: a Mishra's Workshop sozinha vale mais do que o resto da lista
   toda junta. A aba Comprar separa os dois totais em vez de os somar. */
const CARA = 100;

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
  const arr = D.arrumar.copias + ' cópias'
    + (D.arrumar.copias_actualizar ? ` · ${D.arrumar.copias_actualizar} a actualizar`
                                   : '');
  const fixas = [['todas', '▦ Todas', ''], ['arrumar', '📥 Arrumar', arr],
                 ['partilhadas', '🔁 Partilhadas', D.partilhadas.length + ' cartas'],
                 ['comprar', '🛒 Comprar', D.resumo.comprar + ' cópias'],
                 ['vender', '💰 Vender', eur(D.resumo.venda)]];
  let h = '';
  /* `role=tab` + `aria-selected` para o leitor de ecrã dizer qual está aberta,
     e `tabindex=-1` nas outras: numa fila de 19 abas, o Tab passava por todas
     antes de chegar ao conteúdo. Andar entre elas é com as setas (ver abaixo),
     que é o que o padrão de tablist manda. */
  const tab = (id, dentro, extra) =>
    `<button class="dt${aba === id ? ' on' : ''}${extra || ''}" role="tab"`
    + ` aria-selected="${aba === id}" tabindex="${aba === id ? 0 : -1}"`
    + ` data-aba="${esc(id)}">${dentro}</button>`;
  for (const [id, lbl, sub] of fixas) {
    h += tab(id, lbl + (sub ? `<small>${esc(sub)}</small>` : ''));
  }
  for (const c of D.caixas) {
    const p = c.vazio ? '—' : c.pct + '%';
    h += tab(c.slot,
      `<span><i class="pin ${c.vazio ? 'low' : pin(c.pct)}"></i>${esc(c.nome)}</span>`
      + `<small>${p}${c.vazio ? '' : ` · ${c.tenho}/${c.precisa}`}</small>`,
      c.permanente ? '' : ' cand');
  }
  nav.innerHTML = h;
  const botoes = [...nav.querySelectorAll('.dt')];
  botoes.forEach((b, i) => {
    b.onclick = () => ir(b.dataset.aba);
    b.onkeydown = (e) => {
      const d = { ArrowRight: 1, ArrowLeft: -1, Home: -i, End: botoes.length - 1 - i };
      if (!(e.key in d)) return;
      e.preventDefault();
      ir(botoes[(i + d[e.key] + botoes.length) % botoes.length].dataset.aba);
      const novo = nav.querySelector('.dt.on');
      if (novo) novo.focus();
    };
  });
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
  /* A classe vem no payload (`loadout.rotulo_material`). Decidi-la aqui com
     /foil/ pintava de dourado o chip "só nonfoil" do cEDH — "nonfoil" contém
     "foil", e um teste de substring nunca serve para isto. */
  for (const [ico, txt, cls] of c.regras) {
    h += `<span class="bdg ${cls || ''}">${ico} ${esc(txt)}</span>`;
  }
  if (c.variantes.length) h += `<span class="bdg">⇄ ${c.variantes.length} variantes</span>`;
  h += `<span class="bdg">#${c.prioridade} na alocação</span>`;
  return h;
}

/* `detalhe` acrescenta, por baixo do nome, o requisito de material e as caixas
   que pedem a carta — é o que a aba Comprar precisa e o cartão de uma caixa
   não (ali a caixa e o material já estão no cabeçalho). A mesma função para as
   duas: o botão "copiar" copia sempre exactamente a lista que está à vista. */
function wantlistHTML(itens, marca, id, detalhe) {
  if (!itens.length) return '';
  const li = itens.map(m => {
    const cara = detalhe && (m.unit || 0) >= CARA;
    const compra = (m.para || []).filter(p => !p.serve);
    const serve = (m.para || []).filter(p => p.serve);
    const sub = !detalhe ? '' : [m.req || '',
      compra.length ? 'para: ' + compra.map(p => `${p.caixa} ${p.q}×`).join(' · ') : '',
      serve.length ? 'serve também: ' + serve.map(p => p.caixa).join(', ') : '']
      .filter(Boolean).join(' — ');
    return `<li><b>${m.q}×</b><span class="wn">${esc(m.nm)}`
      + (cara ? `<span class="cara">💶 cara</span>` : '')
      + (m.partilhada ? `<span class="part">🔁 partilhada por `
        + `${m.partilhada} caixas</span>` : '')
      + (sub ? `<small>${esc(sub)}</small>` : '')
      + `</span><span class="pz">${eur(m.cost)}</span></li>`;
  }).join('');
  /* O material vai DENTRO da linha copiada (`2 Swords to Plowshares [PT]`).
     Sem ele, a lista que ele leva para o Cardmarket não distingue a PT da era
     Premodern da EN non-foil do cEDH — e comprar a errada é comprar duas vezes.
     Desde que as compras se partilham, a linha já nem pertence a uma caixa só. */
  const txt = itens.map(m => `${m.q} ${m.nm}` + (m.mat ? ` [${m.mat}]` : ''))
    .join('\n');
  return `<div class="blk" id="${id || ''}"><div class="flh">🛒 Comprar`
    + (marca ? ` <span class="mrk">${esc(marca)}</span>` : '')
    + `<span class="dim">${itens.length} cartas</span>`
    + `<button class="cpbtn" onclick="copiar(this)" aria-label="Copiar as `
    + `${itens.length} cartas desta lista de compras">copiar</button></div>`
    + `<ul class="fl">${li}</ul>`
    + `<textarea class="cmk" readonly>${esc(txt)}</textarea></div>`;
}

/* O top-N que ele está mais perto de concluir, para as caixas por escolher
   (Standard, Pioneer, Legacy). "Vou montar este" fixa a lista de consenso desse
   arquétipo nesta caixa, congelada com a data — no site publicado é só a lista
   com o crachá de quem já foi escolhido. */
function candidatosHTML(c) {
  const lista = (D.candidatos || {})[c.slot] || [];
  if (!lista.length) return '';
  const escolhido = lista.some(x => x.escolhido);
  const li = lista.map(x => `<li><b>${x.pct}%</b><span class="wn">${esc(x.nome)}`
    + (x.escolhido ? `<span class="chosen">✔ escolhido em `
        + `${esc(x.escolhido_em || '?')}</span>`
       : escolhido ? `<span class="part">alternativa</span>` : '')
    + `<small>${esc(x.subtitulo)} · ${x.n_lists} listas · comprar ${x.comprar}`
    + `</small></span><span class="pz">${eur(x.custo)}`
    + (D.editable ? (x.escolhido
        ? `<button class="btn" data-act="desmarcar" data-slot="${esc(c.slot)}" `
          + `aria-label="Deixar de montar ${esc(x.nome)}">✕ já não</button>`
        : `<button class="btn pri" data-act="escolher" data-slot="${esc(c.slot)}" `
          + `data-aid="${x.archetype_id}" `
          + `aria-label="Vou montar ${esc(x.nome)} nesta caixa">✔ vou montar este`
          + `</button>`) : '')
    + `</span></li>`).join('');
  return `<div class="blk cand-blk"><div class="flh">🎯 O que estás mais perto de `
    + `concluir<span class="dim">${lista.length} arquétipos</span></div>`
    + `<ul class="fl">${li}</ul>`
    + `<p class="nota">A lista de cada um está na página `
    + `<a href="metagame.html#f-${esc(c.formato)}">Metagame</a>. `
    + (D.editable ? 'Escolher fixa a lista de consenso <b>com a data</b>: não muda '
        + 'debaixo dos pés se o metagame mudar amanhã.'
       : 'Para escolheres, corre <code>python webapp.py</code> no PC (porto 8771).')
    + `</p></div>`;
}

function caixaHTML(c, compacta) {
  if (c.vazio) {
    return `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
      + `<span class="pct dim">—</span></div><div class="badges">${badges(c)}</div>`
      + `<div class="nota">${esc(c.nota)}</div>`
      + `<div class="vaziomsg">Caixa por atribuir — não escolhi por ti. `
      + `Escolhe aqui em baixo, ou vê a lista de cada um na página `
      + `<a href="metagame.html">Metagame</a>.</div>`
      + (compacta ? '' : candidatosHTML(c))
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
    + `<div class="num eur">fechar por<b>${eur(c.custo)}</b>`
    + (c.sem_preco ? `<span class="dim"> no mínimo — ${c.sem_preco} sem preço`
                     + ` na base</span>` : '') + `</div></div>`
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
    /* `futura` = a cópia ainda não está em casa; é uma compra de OUTRA caixa
       que esta partilha. Dizê-lo evita a página mandá-lo à caixa do lado
       buscar uma carta que ninguém comprou ainda. */
    const li = c.buscar.map(m => `<li>${esc(m.nm)} — `
      + Object.entries(m.noutra).map(([k, v]) => `<b>${v}×</b> em ${esc(k)}`
          + ((m.futura || {})[k] ? ` <span class="dim">(${m.futura[k]} depois de `
             + `${esc(k)} comprar)</span>` : '')).join('; ')
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
  h += candidatosHTML(c);
  if (D.editable) h += acoesHTML(c);
  return h + `</div>`;
}

/* Os botões só se DESENHAM no modo edição. No site publicado os endpoints de
   escrita não existem, e um botão que não faz nada é pior do que não haver
   botão nenhum. O `render_deckboxes.js` (na bateria) confirma que a página
   publicada não desenha nenhum. */
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

/* As caixas CONGELADAS (dedicadas e montadas) não se arrumam — actualizam-se.
   O "já arrumei tudo" geral não lhes toca de propósito: abrir um deck que está
   sleevado é outro gesto, e é ele que decide quando o faz. */
function actualizarHTML() {
  const acts = D.arrumar.actualizacoes || [];
  if (!acts.length) return '';
  const lado = (movs, verbo, seta) => movs.map(m =>
    `<div class="mv"><span class="q">${m.q}×</span>`
    + `<span class="nm">${esc(m.nm)}</span>`
    + `<span class="to">${verbo} ${seta} ${esc(verbo === 'tirar' ? m.para : m.de)}`
    + `</span></div>`).join('');
  return `<h2>🔄 Actualizar decks montados <span class="n">${acts.length}</span></h2>`
    + `<p class="lead">Caixas <b>dedicadas e montadas</b>: a lista mudou, o deck `
    + `não. Ficam como estão até seres tu a abri-las — o <b>já arrumei tudo</b> `
    + `não lhes toca. Quando as actualizares, `
    + (D.editable ? 'carrega em <b>actualizei</b> nessa caixa.'
                  : 'diz-me (ou usa o modo edição, <code>python webapp.py</code>).')
    + `</p>`
    + acts.map(a => `<div class="arr"><div class="arrh"><b>${esc(a.caixa)}</b>`
        + `<span>${a.copias} cópias · tirar ${a.sai.length} · meter `
        + `${a.entra.length}</span></div>`
        + lado(a.sai, 'tirar', '→') + lado(a.entra, 'meter', '←')
        + (D.editable ? `<div class="acts"><button class="btn pri" `
            + `data-act="actualizar" data-slot="${esc(a.slot)}">🔄 Actualizei o `
            + `${esc(a.caixa)}</button></div>` : '')
        + `</div>`).join('');
}

function vistaArrumar() {
  const a = D.arrumar;
  if (!a.linhas) {
    return actualizarHTML()
      + `<h2>📥 Arrumar</h2><p class="empty">Nada a arrumar: a estante já está `
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
  return actualizarHTML()
    + `<h2>📥 Arrumar — ${a.copias} cópias</h2>`
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
    const det = c.por_slot.map(q => `<span class="cs ${q.levou >= q.pediu ? 'ok' : 'no'}"`
      + `${q.req ? ` title="${esc(q.slot)}: só cópias ${esc(q.req)}"` : ''}>`
      + `${esc(q.slot)} ${q.levou}/${q.pediu}</span>`).join('');
    /* Uma caixa só vai buscar o que cumpre as REGRAS dela — dizê-lo aqui evita
       a leitura errada de que qualquer cópia serve qualquer caixa. */
    const regras = c.por_slot.filter(q => q.req).map(q =>
      `${esc(q.slot)}: só cópias <b>${esc(q.req)}</b>`).join(' · ');
    const tem = c.ficam_com.join(', ') || 'ninguém';
    const vai = c.ficam_sem.filter(x => c.ficam_com.length && !c.ficam_com.includes(x))
      .join(', ');
    return `<div class="cfrow"><div class="cd sub">`
      + (c.sid ? `<img loading="lazy" src="${art(c.sid)}" alt="">` : '')
      + `</div><div class="cfb"><b>${esc(c.nm)}</b>`
      + `<span class="dim">tens ${c.tenho} para ${c.pedido} pedidas · está em `
      + `<b>${esc(tem)}</b>${vai ? ' · vai buscar: ' + esc(vai) : ''}</span>`
      + `<div class="csl">${det}</div>`
      + (regras ? `<span class="dim creq">${regras}</span>` : '')
      + `</div></div>`;
  }).join('');
  return `<h2>🔁 Cartas partilhadas entre caixas <span class="n">`
    + `${D.partilhadas.length}</span></h2>`
    + `<p class="lead"><b>Só se partilham cópias que cumprem as regras da caixa que `
    + `vai buscar.</b> `
    + `Cartas que duas ou mais caixas querem e não chegam para todas. `
    + `<b>Não são compras.</b> A cópia fica na caixa que aloca primeiro (permanentes, `
    + `depois o grupo de formato) e as outras vão lá buscá-la quando forem jogar — é `
    + `por isso que aparecem a âmbar com <b>“em &lt;caixa&gt;”</b> e não somam ao `
    + `custo. Se quiseres os decks todos prontos ao mesmo tempo sem trocas, aí sim: `
    + `compram-se cópias dedicadas.</p><div class="cfgrid">${rows}</div>`;
}

/* A linha de compra vista pelos olhos de UMA caixa: a quantidade, o custo e o
   material passam a ser os dela. Sem isto o filtro mostrava a linha inteira e o
   "copiar" dava-lhe a lista das outras caixas por cima. */
/* Uma caixa SERVIDA por uma compra partilhada não aparece na lista dela: a
   compra é de outra caixa, e pô-la aqui era comprá-la duas vezes — que é
   exactamente o defeito que a partilha veio corrigir. */
function soDaCaixa(m, slot) {
  const p = (m.para || []).find(x => x.slot === slot && !x.serve);
  if (!p) return null;
  return Object.assign({}, m, { q: p.q, cost: p.cost, unit: p.unit,
                                req: p.req, mat: p.mat, para: [p],
                                partilhada: 0 });
}

function vistaComprar() {
  const sel = P.compra || 'todas';
  const itens = (sel === 'todas' ? D.compras.slice()
                 : D.compras.map(m => soDaCaixa(m, sel)).filter(Boolean))
    .sort((a, b) => (b.cost || 0) - (a.cost || 0));
  const caras = itens.filter(m => (m.unit || 0) >= CARA);
  const resto = itens.filter(m => (m.unit || 0) < CARA);
  const soma = l => l.reduce((s, m) => s + (m.cost || 0), 0);
  const nome = sel === 'todas' ? 'todas as caixas'
    : ((D.caixas.find(c => c.slot === sel) || {}).nome || sel);
  /* O selector reaproveita as caixas que já são abas — só as que têm mesmo
     alguma coisa a comprar entram na lista (uma caixa SERVIDA por outra não
     compra nada). */
  const compraDe = (m, slot) => (m.para || []).some(p => p.slot === slot && !p.serve);
  const comCompras = D.caixas.filter(c => D.compras.some(m => compraDe(m, c.slot)));
  const opt = (v, t, n) => `<option value="${esc(v)}"${sel === v ? ' selected' : ''}>`
    + `${esc(t)}${n == null ? '' : ` — ${n} cartas`}</option>`;
  const selector = `<div class="seg"><select class="selc" id="compra-caixa">`
    + opt('todas', 'todas as caixas', D.compras.length)
    + comCompras.map(c => opt(c.slot, c.nome,
        D.compras.filter(m => compraDe(m, c.slot)).length)).join('')
    + `</select></div>`;
  return `<h2>🛒 Comprar — ${esc(nome)}</h2>`
    + `<p class="lead">Só o que <b>não existe</b> na coleção, ou existe mas não serve `
    + `na língua/acabamento que a caixa exige. As cartas que estão noutra caixa `
    + `<b>não estão aqui</b>: vão-se buscar. São <b>${D.resumo.noutra}</b> cópias a ir `
    + `buscar contra <b>${D.resumo.comprar}</b> a comprar. Debaixo de cada nome está `
    + `<b>para que caixa</b> é a compra e <b>em que material</b> — comprar a versão `
    + `errada é comprar duas vezes.</p>`
    + (D.resumo.poupado ? `<p class="lead">🔁 <b>Uma cópia serve as caixas todas.</b> `
        + `Quando duas caixas querem a mesma carta no mesmo material, compra-se `
        + `<b>uma vez</b> e as outras vão lá buscá-la — como já fazes com as que tens. `
        + `São <b>${D.resumo.poupado}</b> cópias que a lista deixou de pedir. Se `
        + `quiseres uma caixa fechada sem trocas, marca-a com `
        + `<code>compras_dedicadas</code> no <code>colecao_config.json</code>.</p>` : '')
    + selector
    + (!itens.length ? `<p class="empty">Não falta comprar nada aqui. Está tudo em casa.</p>`
       : `<div class="nums">`
         + `<div class="num buy">cópias<b>${itens.reduce((s, m) => s + m.q, 0)}</b></div>`
         + `<div class="num eur">💶 caras (≥ ${CARA} €/cópia)<b>${eur(soma(caras))}</b>`
         + `<span class="dim"> ${caras.length} cartas</span></div>`
         + `<div class="num eur">resto<b>${eur(soma(resto))}</b>`
         + `<span class="dim"> ${resto.length} cartas</span></div></div>`
       + (caras.length ? `<p class="lead">As <b>💶 caras</b> decidem-se uma a uma: `
         + `só elas valem ${eur(soma(caras))} dos ${eur(soma(itens))} da lista.</p>` : '')
       + (D.resumo.sem_preco ? `<p class="lead">⚠️ <b>${D.resumo.sem_preco}</b> `
         + `cópias desta lista não têm preço na base (contam como 0 €). `
         + `O total é um <b>mínimo</b>, não a conta fechada.</p>` : '')
       + wantlistHTML(itens, '', 'v-compras', true));
}

function vistaVender() {
  const bloco = (id, titulo, lead, b, aberto, rotulo) => !b.linhas.length ? '' :
    `<details class="vblk" id="${id}"${aberto ? ' open' : ''}>`
    + `<summary><span>${titulo}</span><span class="vtot">${b.copias} cópias · `
    + `${eur(b.total)}</span></summary><p class="lead">${lead}</p>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this)" `
    + `aria-label="Copiar a lista: ${esc(rotulo)}">copiar lista`
    + `</button></div><textarea class="cmk" readonly>`
    + esc(b.linhas.slice().sort((x, y) => x.nm.localeCompare(y.nm))
        .map(r => `${r.q} ${r.nm}`).join('\n')) + `</textarea>`
    + `<table class="vt"><thead><tr><th></th><th>carta</th><th>onde está</th>`
    + `<th>edição</th><th>un.</th><th>total</th><th class="rz">porquê</th></tr></thead>`
    + `<tbody>` + b.linhas.map(r => `<tr><td class="q">${r.q}×</td>`
      + `<td>${esc(r.nm)}${r.rl ? ' <span class="rl">RL</span>' : ''}</td>`
      + `<td class="dim">${esc(r.local)}</td>`
      // `r.foil` vem do Python (`loadout.e_foil`). Este teste era
      // `/foil|etched/.test(r.fin)` e marcava com ✨ as cópias `nonfoil` — a
      // palavra "nonfoil" contém "foil". Aparecia em Lotus Petal e Mirri's
      // Guile, que são nonfoil, e mandava-o listá-las como foil.
      + `<td class="dim">${esc(r.set)} ${r.foil ? '✨' : ''} `
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
        + 'real.', V.normal, true, 'excedente normal')
    + bloco('v-rl', '⚠️ Reserved List — confirmar uma a uma', 'Cartas que nunca mais '
        + 'são impressas. A regra dá-as como excedente, mas a decisão não se desfaz — '
        + 'e os preços de cartas antigas na base não são de confiança (ver '
        + '<code>doubts.md</code>). Confere cada uma antes de listar.', V.rl, false,
        'Reserved List')
    + bloco('v-guardar', '🔒 Guardar — servem um deck do loadout', 'Passariam o limite '
        + 'de 4, mas são substitutos de cartas que faltam a uma caixa: servem o deck e '
        + 'só não fecham o slot por causa da língua ou do acabamento. Vendê-las era '
        + 'comprá-las outra vez.', V.guardar, false, 'guardar')
    + bloco('v-retidos', '⏳ Retidos — extras de decks montados', 'Baldes com '
        + '<code>reter_extras_meses</code>: guardam-se até 6 meses depois da última '
        + 'utilização. Ainda não há registo de "última utilização", por isso ficam '
        + 'todos — não se vende nada por uma regra que ainda não corre.', V.retidos,
        false, 'retidos')
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
  /* `aria-pressed`: são dois botões que ficam carregados, não links. Sem isto o
     leitor de ecrã lia "Todas as cartas, botão" nos dois, sem dizer qual está
     activo — e a diferença é só a cor de fundo. */
  const b = (f, t) => `<button class="${filtro === f ? 'on' : ''}" data-f="${f}"`
    + ` aria-pressed="${filtro === f}">${t}</button>`;
  return `<div class="seg" role="group" aria-label="Filtrar as cartas">`
    + b('tudo', 'Todas as cartas') + b('faltam', 'Só o que falta') + `</div>`;
}

function ligar() {
  for (const b of document.querySelectorAll('[data-f]')) {
    b.onclick = () => { filtro = b.dataset.f; P.filtro = filtro; save(); render(); };
  }
  for (const b of document.querySelectorAll('.mini[data-slot]')) {
    b.onclick = () => ir(b.dataset.slot);
  }
  /* Todos os botões de escrita, estejam num `.acts` ou dentro da lista de
     candidatos — um selector demasiado apertado deixava o "vou montar este"
     desenhado e morto, que é o pior dos dois mundos. */
  for (const b of document.querySelectorAll('[data-act]')) {
    b.onclick = () => accao(b.dataset.act, b.dataset.slot, b, b.dataset.aid);
  }
  for (const l of document.querySelectorAll('.mv')) {
    const cb = l.querySelector('input');
    cb.onchange = () => {
      if (cb.checked) P.feitos[l.dataset.id] = 1; else delete P.feitos[l.dataset.id];
      l.classList.toggle('feito', cb.checked);
      save();
    };
  }
  const cc = $('#compra-caixa');
  if (cc) cc.onchange = () => { P.compra = cc.value; save(); render(); };
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

/* Escolher um deck para uma caixa é outro endpoint (`api/escolher`): mexe na
   `listas_escolhidas` e refaz as DUAS páginas, não só esta. */
const ESCOLHA = { escolher: 1, desmarcar: 1 };

async function accao(act, slot, btn, aid) {
  btn.disabled = true;
  try {
    const r = await fetch(ESCOLHA[act] ? 'api/escolher' : 'api/caixa', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ act, slot, aid: aid ? Number(aid) : null }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Feito — a alocação foi refeita.');
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
