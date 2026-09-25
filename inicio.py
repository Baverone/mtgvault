"""Gera index.html — o INÍCIO: o painel com os números reais de hoje.

André, 2026-09-24: *"no mtgvault quero uma organização diferente [...] Faz toda
uma reestruturação para um site profissional, bem organizado, bem estruturado!"*
— e, na arquitetura que ele pediu, o Início é *"um painel com números reais:
decks montados / para montar, cartas em falta para os decks permanentes, cartas
na coleção, valor, últimas atualizações dos dados, e atalhos para o que ele usa
mais"*.

Até aqui o `index.html` era **estático, escrito à mão**: cinco botões, três
links e um rodapé. Isso tinha uma razão registada no CLAUDE.md — *"gerá-lo por
código era trazer um gerador novo para a porta de entrada do site"* — e um
teste (`caso_o_indice_tem_o_mesmo_menu_que_o_paginas`) a comparar o menu escrito
à mão com o `paginas.MENU`. Duas coisas mudaram e fazem essa decisão deixar de
valer:

  1. **o menu já não se escreve à mão em lado nenhum** — vem do
     `site_shell.barra()`, como em todas as páginas, e por isso a porta de
     entrada não pode ficar para trás como o `cobertura.html` ficou em Agosto;
  2. **ele pediu números**, e um número escrito à mão numa página estática é a
     definição de um número que vai ficar errado.

NÃO INVENTA NENHUM NÚMERO. Todos saem de onde as outras páginas os vão buscar:
o `loadout.report` (as caixas, o que falta comprar, a venda, as encomendas, a
revalidação) e a base (as cópias, o valor, as datas). É a mesma regra do
"posse: quem conta o quê" — se um número aqui discordasse da Deckboxes, era o
padrão do `event_tier` na primeira página que ele abre.
"""
from __future__ import annotations

import html
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import collection, loadout, paginas, venda  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402

_CSS = """
 /* A GRELHA DOS NÚMEROS (2.ª passagem, 2026-09-24). Era `auto-fit` com um
    mínimo de 262 px: a 1440 px cabiam QUATRO por linha e os seis cartões saíam
    4 + 2, com um buraco à direita — *"os 6 cartões ficam 4 + 2 com um buraco"*.
    Agora são três colunas fixas (duas no telemóvel), que é o que dá 3 × 2 com
    os seis de sempre; havendo os dois cartões condicionais (encomendas e
    revalidação) ficam 3 × 2 + 2, que é a mesma grelha e não um acaso.
    `align-items:stretch` + `flex` dentro do cartão: as alturas de cada linha
    são iguais mesmo com detalhes de uma ou de três linhas. */
 .kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 22px;align-items:stretch}
 .kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);padding:15px 17px;min-width:0;display:flex;flex-direction:column}
 .kpi .kl{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:11.5px;font-weight:600;text-transform:uppercase;letter-spacing:.07em}
 .kpi .kl svg.ico{opacity:.85}
 .kpi .kv{font-family:var(--font-hd);font-size:27px;font-weight:700;line-height:1.15;margin-top:7px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
 .kpi .kd{color:var(--dim);font-size:12px;margin-top:3px;line-height:1.45}
 @media(max-width:899px){
   .kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
   .kpi{padding:13px 14px}
   .kpi .kv{font-size:22px}
   .kpi .kl{font-size:10.5px;letter-spacing:.05em}
 }
 @media(max-width:359px){ .kpis{grid-template-columns:minmax(0,1fr)} }
 .kpi.gold .kv{color:var(--gold)} .kpi.add .kv{color:var(--add)}
 .kpi.warn .kv{color:var(--warn)} .kpi.info .kv{color:var(--ob)}
 .kpi a{color:inherit;text-decoration:none} .kpi a:hover .kv{text-decoration:underline}
 h2.sh{font-family:var(--font-hd);font-size:13px;margin:26px 0 10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-weight:700}
 .duas{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;align-items:start}
 .painel{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);padding:15px 17px;min-width:0}
 .painel h3{margin:0 0 10px;font-size:14px;font-weight:700;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
 .painel h3 .n{margin-left:auto;color:var(--dim);font-size:11.5px;font-weight:600}
 .cx{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--line);min-width:0;color:var(--ink2);text-decoration:none}
 .cx:first-of-type{border-top:0}
 .cx:hover{color:var(--ink)} .cx:hover .cxn{color:var(--accent)}
 .cxf{width:34px;height:34px;flex:none;border-radius:8px;object-fit:cover;background:var(--bg);border:1px solid var(--line2)}
 span.cxf{display:inline-flex;align-items:center;justify-content:center;font-size:14px;color:var(--dim);border-style:dashed}
 .cxi{min-width:0;flex:1}
 .cxn{display:block;font-size:13.5px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .cxs{display:block;color:var(--dim);font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .cxb{flex:none;width:96px}
 .cxp{font-size:12px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
 .mini{height:5px;border-radius:999px;background:var(--bg);overflow:hidden;margin-top:4px}
 .mini i{display:block;height:100%;border-radius:999px}
 .atalhos{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin:0 0 6px}
 .at{display:flex;align-items:center;gap:10px;padding:13px 15px;border-radius:var(--r);background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;transition:.14s}
 .at:hover{border-color:var(--accent);background:var(--card3)}
 .at .ai{flex:none;display:flex;align-items:center;color:var(--muted)}
 .at:hover .ai{color:var(--accent)}
 .at>span:last-child{min-width:0}
 .at b{display:block;font-size:13.5px;font-weight:600}
 .at small{display:block;color:var(--dim);font-size:11.5px;line-height:1.35}
 .fontes{list-style:none;margin:0;padding:0;font-size:12.5px}
 .fontes li{display:flex;gap:10px;padding:6px 0;border-top:1px solid var(--line);color:var(--muted);flex-wrap:wrap}
 .fontes li:first-child{border-top:0}
 .fontes b{color:var(--ink2);font-weight:600;min-width:170px}
 .fontes .d{font-variant-numeric:tabular-nums;white-space:nowrap}
 .fontes .q{margin-left:auto;color:var(--dim);font-variant-numeric:tabular-nums;white-space:nowrap}
 @media(max-width:560px){
   /* A 390 px a data partia-se em «2026-09-» + «24». Aqui o nome leva a linha
      toda e a data e a contagem ficam na de baixo, nas pontas. */
   .fontes b{min-width:100%}
   .fontes li{gap:4px 10px;padding:8px 0}
 }
"""

_RODAPE = ("Todos os números desta página saem de onde as outras os vão buscar — "
           "o <code>loadout.report</code> (as caixas, o que falta comprar%VENDA%) "
           "e a base (as cópias e o valor). Se um número aqui discordasse da "
           "Deckboxes seria um <b>bug</b>, não uma segunda opinião: é a regra de "
           "«posse: quem conta o quê». O site atualiza-se sozinho todos os dias.")


def _tmpl() -> str:
    """O molde. É uma FUNÇÃO desde 2026-09-25 pela mesma razão do `deckboxes`:
    a barra lateral e o rodapé seguem o `venda.mostrar`, e uma constante de
    módulo congelava-os no instante do `import`."""
    rodape = _RODAPE.replace("%VENDA%", ", a venda" if venda.mostrar() else "")
    return ("""<!doctype html><html lang="pt-PT"><head>"""
            + shell.head("Início", _CSS) + """</head><body>"""
            + shell.abrir("index.html", "Início", "%LEAD%") + """
<div class="wrap">
%KPIS%
%ATALHOS%
%PAINEIS%
</div>""" + shell.fechar(rodape) + """</body></html>""")


def _cor_pct(p: int) -> str:
    return ("var(--add)" if p >= 90 else "var(--gold)" if p >= 50
            else "var(--warn)")


def _kpi(ic: str, label: str, valor: str, detalhe: str = "", cls: str = "",
         href: str = "") -> str:
    v = f'<a href="{href}"><span class="kv">{valor}</span></a>' if href \
        else f'<span class="kv">{valor}</span>'
    d = f'<div class="kd">{detalhe}</div>' if detalhe else ""
    return (f'<div class="kpi {cls}"><div class="kl">{shell.icone(ic, 15)}'
            f'<span>{html.escape(label)}</span></div>{v}{d}</div>')


def _linha_caixa(c: dict, out_dir: Path) -> str:
    """Uma caixa na lista do painel: foto, nome, estado e percentagem."""
    foto = (c.get("foto") or {}).get("url") if isinstance(c.get("foto"), dict) else None
    img = (f'<img class="cxf" src="{html.escape(foto)}" alt="" loading="lazy" '
           f'decoding="async" onerror="this.remove()">' if foto
           else f'<span class="cxf">{shell.icone("caixas", 16)}</span>')
    pct = 0 if c.get("vazio") else int(c.get("pct") or 0)
    sub = (c.get("req") or c.get("formato") or "")
    if c.get("vazio"):
        marca, barra = "sem deck", ""
    else:
        marca = f"{pct}%"
        barra = (f'<div class="mini"><i style="width:{pct}%;'
                 f'background:{_cor_pct(pct)}"></i></div>')
    return (f'<a class="cx" href="deckboxes.html#{html.escape(c["slot"])}">{img}'
            f'<span class="cxi"><span class="cxn">{html.escape(c["nome"])}</span>'
            f'<span class="cxs">{html.escape(sub)}</span></span>'
            f'<span class="cxb"><span class="cxp" style="color:{_cor_pct(pct)}">'
            f'{marca}</span>{barra}</span></a>')


def _valor_coleccao(con) -> tuple[int, float]:
    """(exemplares na estante, valor total a preço Cardmarket).

    OS DOIS NÚMEROS SAEM DA MESMA CHAMADA — `collection.valor_da_coleccao`, a
    conta única do valor (2026-09-24). Escrevi uma primeira versão própria e ela
    dava **97 761,26 €** contra os **97 772,93 €** da página dos binders: a
    diferença são as cópias cujo acabamento não tem preço e caem para o outro
    (foil → nonfoil). Passei então a chamar o `colecao_cor._value`, o que tirava
    a discórdia desta página mas deixava a Galeria a dizer o número antigo — e o
    **número de cartas** continuava a sair de uma consulta própria, com o
    `jogaveis()`, enquanto o valor contava o `na_estante()`: bastava entrar uma
    cópia de colecionador para o cartão dizer *"N cartas valem X"* com o X a
    contar cartas que o N não conta. Onze euros e sete cêntimos de discórdia
    entre duas páginas sobre o mesmo número, sem um único erro — o padrão do
    `event_tier` na porta de entrada do site.
    """
    v = collection.valor_da_coleccao(con)
    # O cenário é o do MODO DE PREÇO em vigor (2026-09-25) e não o `trend`
    # escrito à mão: com o modo `best` ligado, esta página dizia o market value
    # e a do lado o best value — a mesma discórdia que a conta única fechou.
    return int(v["q"]), float(v["total"][v["cenario"]])


def _fontes(con) -> list[tuple[str, str, str]]:
    """(o quê, quando, quanto) — as últimas atualizações dos dados.

    São as datas por que se percebe se uma página está a mentir por estar velha.
    Cada uma sai da tabela que a alimenta; nenhuma é `hoje` escrito à mão.
    """
    def um(sql, *a):
        try:
            r = con.execute(sql, a).fetchone()
            return (r[0], r[1]) if r else (None, None)
        except Exception:  # noqa: BLE001  (uma tabela que ainda não exista)
            return (None, None)

    linhas = []
    d, n = um("SELECT MAX(date), COUNT(*) FROM price_latest")
    linhas.append(("Preços (Cardmarket/Scryfall)", d, f"{n or 0} impressões"))
    d, n = um("SELECT MAX(event_date), COUNT(*) FROM decklists")
    linhas.append(("Decklists de torneio", d, f"{n or 0} listas"))
    d, n = um("SELECT MAX(window_end), COUNT(DISTINCT archetype_id) FROM card_roles")
    linhas.append(("Arquétipos (clustering)", d, f"{n or 0} arquétipos"))
    d, n = um("SELECT MAX(placed_at), SUM(quantity) FROM copy_allocation")
    linhas.append(("Cartas dentro das caixas", (d or "")[:10] or None,
                   f"{n or 0} cópias"))
    d, n = um("SELECT MAX(taken_at), COUNT(*) FROM watched_snapshots")
    linhas.append(("Decks vigiados", (d or "")[:10] or None, f"{n or 0} fotografias"))
    return [(t, dt or "—", q) for t, dt, q in linhas]


def build(con, out_path=None, rep=None):
    out = Path(out_path) if out_path else (ROOT / "index.html")
    res = rep if rep is not None else loadout.report(con)
    slots = res["slots"]
    montadas = [s for s in slots if s.get("montado")]
    por_montar = [s for s in slots if not s.get("montado")]
    # «Cartas em falta para os decks PERMANENTES» — o pedido dele, à letra. As
    # candidatas ficam de fora: são caixas que ele ainda não disse que quer.
    perm = [s for s in slots if s.get("permanente")]
    falta_perm = sum(s["comprar"] for s in perm)
    custo_perm = round(sum(s["custo"] for s in perm), 2)
    n_copias, valor = _valor_coleccao(con)

    # «PARA JÁ TIRA O VENDER» (André, 2026-09-25). O cartão e o atalho saem com
    # o interruptor: este é o primeiro ecrã que ele abre, e era aqui que o valor
    # da venda estava em euros, a negrito, com um link para a aba.
    mostra_venda = venda.mostrar()
    venda_q = sum(m["q"] for m in res.get("venda", []))
    venda_v = round(sum(m["q"] * (m.get("unit") or 0) for m in res.get("venda", [])), 2)
    rl_q = sum(m["q"] for m in res.get("venda_rl", []))
    rl_v = round(sum(m["q"] * (m.get("unit") or 0) for m in res.get("venda_rl", [])), 2)

    hoje = date.today().isoformat()
    lead = (f'O que a coleção diz <b>hoje</b> ({hoje}). '
            f'<b>{len(montadas)}</b> deck{"s" if len(montadas) != 1 else ""} '
            f'na estante, <b>{len(por_montar)}</b> por montar, '
            f'<b>{res["comprar_total"]}</b> cópias por comprar.')

    kpis = "".join([
        _kpi("montado", "Decks montados", str(len(montadas)),
             f"de {len(slots)} caixas · {len(por_montar)} por montar",
             "add", "deckboxes.html#montados"),
        _kpi("comprar", "Faltam aos permanentes", str(falta_perm),
             f"{paginas.eur(custo_perm)} · {len(perm)} caixas permanentes",
             "warn", "deckboxes.html#comprar"),
        _kpi("binders", "Cartas na coleção", f"{n_copias:,}".replace(",", " "),
             f"valor ~{paginas.eur(valor)} — o mesmo número dos "
             f"<a href=\"colecao_cor.html\">binders por cor</a> e da "
             f"<a href=\"colecao.html\">galeria</a>", "info", "colecao_cor.html"),
        (_kpi("vender", "Para vender", paginas.eur(venda_v),
              f"{venda_q} cópias · mais {rl_q} da Reserved List "
              f"({paginas.eur(rl_v)})", "gold", "deckboxes.html#vender")
         if mostra_venda else ""),
        _kpi("arrumar", "Para arrumar", str(res["arrumacao"]["copias"]),
             f'{len(res["arrumacao"]["movimentos"])} linhas de movimento', "",
             "deckboxes.html#arrumar"),
        _kpi("fechar", "Fechar tudo", paginas.eur(res["custo_total"]),
             f'{res["comprar_total"]} cópias'
             + (f' · {res["sem_preco_total"]} sem preço'
                if res["sem_preco_total"] else ""), "gold",
             "deckboxes.html#plano"),
    ])

    # Os dois blocos de encomendas/revalidação só existem quando há alguma coisa
    # para dizer — um cartão a dizer «0» é ruído na porta de entrada.
    extra = ""
    a_cam = res.get("a_caminho_total", 0)
    pend = res.get("pendente_foto_total", 0)
    if a_cam or pend:
        extra += _kpi("encomendas", "Encomendas", str(a_cam + pend),
                      f"{a_cam} a caminho · {pend} à espera de foto", "info",
                      "deckboxes.html#encomendas")
    rev = res.get("revalidacao") or {}
    tot = (rev.get("total") or {}) if isinstance(rev, dict) else {}
    if tot.get("total"):
        extra += _kpi("revalidacao", "Revalidação", f'{tot.get("pct", 0)}%',
                      f'{tot.get("por_revalidar", 0)} cópias por fotografar', "",
                      "deckboxes.html#revalidacao")
    kpis = f'<div class="kpis">{kpis}{extra}</div>'

    # Seis atalhos, e a grelha é 3×2 (2.ª passagem, 2026-09-24). Sem a venda
    # ficam cinco — e é a Feira que passa a fechar a linha, para a grelha não
    # ficar com um buraco.
    _atalhos = [("deckboxes.html#plano", "plano", "Plano", "por onde começar"),
                ("deckboxes.html#comprar", "comprar", "Comprar",
                 "a wantlist de todas")]
    if mostra_venda:
        _atalhos.append(("deckboxes.html#vender", "vender", "Vender",
                         "o excedente, a confirmar"))
    else:
        _atalhos.append(("deckboxes.html#encomendas", "encomendas", "Encomendas",
                         "o que já compraste"))
    _atalhos += [("deckboxes.html#arrumar", "arrumar", "Arrumar",
                  "o que muda de sítio"),
                 ("metagame.html", "metagame", "Metagame",
                  "o que estás perto de fechar"),
                 ("colecao_cor.html", "binders", "Binders", "a coleção por cor")]
    atalhos = ('<h2 class="sh">Onde vais mais vezes</h2><div class="atalhos">'
               + "".join(
                   f'<a class="at" href="{h}"><span class="ai">'
                   f'{shell.icone(i, 21)}</span>'
                   f'<span><b>{t}</b><small>{d}</small></span></a>'
                   for h, i, t, d in _atalhos) + "</div>")

    def bloco(titulo, lista, vazio, nota=""):
        corpo = ("".join(_linha_caixa(c, out.parent) for c in lista) if lista
                 else f'<p class="vazio">{vazio}</p>')
        n = f'<span class="n">{nota}</span>' if nota else ""
        return f'<div class="painel"><h3>{titulo}{n}</h3>{corpo}</div>'

    # A ordem das que faltam é a do PLANO (`ordem_de_montagem`), a mesma da aba
    # — reordená-la aqui dava duas respostas a *"por onde começo?"*.
    ordem = {m["slot"]: i for i, m in enumerate(res.get("montagem", []))}
    falta_ord = sorted(por_montar,
                       key=lambda s: (ordem.get(s["slot"], 999), s["nome"]))
    paineis = ('<h2 class="sh">Os decks</h2><div class="duas">'
               + bloco(shell.icone("montado") + " Na estante", montadas,
                       "Ainda não há nenhuma caixa montada.",
                       f"{len(montadas)} de {len(slots)}")
               + bloco(shell.icone("montar") + " Por montar", falta_ord[:8],
                       "Está tudo montado.",
                       f"{len(por_montar)} caixas · pela ordem do Plano")
               + "</div>")

    linhas = "".join(f'<li><b>{html.escape(t)}</b>'
                     f'<span class="d">{html.escape(d)}</span>'
                     f'<span class="q">{html.escape(q)}</span></li>'
                     for t, d, q in _fontes(con))
    paineis += ('<h2 class="sh">Últimas atualizações dos dados</h2>'
                f'<div class="painel"><ul class="fontes">{linhas}</ul></div>')

    out.write_text(_tmpl().replace("%LEAD%", lead).replace("%KPIS%", kpis)
                   .replace("%ATALHOS%", atalhos).replace("%PAINEIS%", paineis),
                   encoding="utf-8")
    return out


def main():
    from mtgvault import db
    with db.session() as con:
        print("index.html:", build(con))


if __name__ == "__main__":
    main()
