"""Gera a página das coleções do núcleo novo (`colecoes.html`): as quatro
coleções (Duals de Revised, Zendikar Expeditions, Shocks originais em
português, Reserved List) e «A subir», numa página só — uma `<section>` por
coleção e uma para as cartas a subir, e os botões de todas quando não há `#` no
endereço. Como o `nucleo_decks`, e com o mesmo JavaScript de `#`
(`visual.JS_ROTA`).

**Esta página nunca escreve**: o `publicar` gera-a a partir de uma ligação só de
leitura. As coleções são criadas por `colecoes.garantir_colecoes` (no arranque
do modo de edição e no daily); sem elas a página di-lo, em vez de mostrar «0 de
40».

O nome do ficheiro não é `colecao.html` porque esse é a Galeria do site antigo,
ainda ligada à publicação dele.

Cada coleção: o valor de hoje com as variações a 30 e a 90 dias e o gráfico, o progresso
e quanto falta em euros (as fechadas), e as cartas em imagem — a cores as que
tem, a cinzento as que faltam — com «tenho / meta», o preço (nas portuguesas
com o dia em que foi visto), a variação a 30 e a 90 dias, onde se joga e «quero
vender». As peças vivem em `mtgvault/nucleo/visual.py`.
"""
from __future__ import annotations

import html
import sqlite3
from datetime import date
from pathlib import Path

from mtgvault import paginas
from mtgvault import site_shell as shell
from mtgvault.nucleo import colecoes, cotacoes, edicao_js, valor, visual

ROOT = Path(__file__).resolve().parent
FICHEIRO = "colecoes.html"
TITULO = "Coleção"

e = html.escape

_SUB = ("Toca numa coleção para ver as cartas: a cores as que tens, a cinzento "
        "as que faltam.")

_RODAPE = ("O preço de uma carta em inglês é o trend do Cardmarket da edição e do "
           "acabamento. Nas portuguesas é a oferta portuguesa mais barata do "
           "último dia em que o CardTrader teve alguma («visto há N dias»): nunca "
           "se usa o preço inglês. «Sem preço» não é 0 €. «Joga»: a carta está "
           "num deck teu ou em listas de torneio dos últimos três meses. «A "
           "subir» são números, não recomendações.")


# ---------------------------------------------------------------------------
# Os dados
# ---------------------------------------------------------------------------
def _pct(v: dict | None) -> float | None:
    """A percentagem de uma `visual.variacao_serie`; sem ela (ou com o ponto de
    partida a 0 €), `None` — «sem histórico»."""
    return v["pct"] if v else None


def _dados(con, hoje: str) -> list[dict]:
    """As coleções por ordem, cada uma com o estado, a série do valor, as
    variações a 30 e a 90 dias e a carta que lhe dá a arte (a `arte_nome` dela; sem
    ela, a primeira carta; vazia, sem arte)."""
    out = []
    for col in colecoes.colecoes(con):
        est = colecoes.estado_colecao(con, col["slug"], hoje)
        serie = valor.serie_colecao(con, col["slug"], hoje)
        cartas = est["cartas"]
        arte = next((c["scryfall_id"] for c in cartas
                     if c["nome"] == col["arte_nome"]),
                    cartas[0]["scryfall_id"] if cartas else None)
        out.append({"estado": est, "serie": serie, "arte": arte,
                    "var30": _pct(visual.variacao_serie(serie, hoje)),
                    "var90": _pct(visual.variacao_serie(serie, hoje, 90))})
    return out


# ---------------------------------------------------------------------------
# Uma coleção
# ---------------------------------------------------------------------------
def _cabecalho(item: dict) -> str:
    est = item["estado"]
    arte = (f'<img class="dka" src="{visual.url_arte(item["arte"])}" alt=""'
            f' loading="lazy" decoding="async" width="626" height="457">'
            if item["arte"] else '<span class="dka"></span>')
    tipo = "lista fixa" if est["tipo"] == "fechada" else "aberta · sem meta"
    return (f'<header class="dkh">{arte}<div><h2 id="t-{e(est["slug"])}">'
            f'{e(est["nome"])}</h2><div class="dks">{tipo}</div></div></header>')


def _valor(item: dict) -> str:
    est = item["estado"]
    var = ('<span class="vvar">'
           + visual.variacoes_html(item["var30"], item["var90"]) + "</span>")
    # só as cartas que ele tem: as que faltam e não têm preço não entram no valor
    sem = sum(1 for c in est["cartas"] if c["tenho"] and c["preco_un"] is None)
    nota = (f'<div class="vnota">{paginas.plural(sem, "carta tua", "cartas tuas")}'
            ' sem preço, fora da conta</div>' if sem else "")
    return ('<div class="vcard"><div class="vlab">Valor de hoje</div>'
            f'<div class="vlin"><span class="vbig">{visual.valor_colecao_texto(est)}'
            f'</span>{var}</div>{nota}{visual.grafico(item["serie"])}</div>')


def _progresso(est: dict) -> str:
    val = est["validadas"]
    validadas = (f' · {val} validada{"s" if val != 1 else ""}' if val else "")
    if est["tipo"] != "fechada":
        return (f'<div class="kpi"><span>{paginas.plural(est["tenho"], "carta")}'
                f'{validadas}</span></div>')
    sp = (f' <small>({est["sem_preco"]} sem preço)</small>'
          if est["sem_preco"] else "")
    if est["tenho"] >= est["total"]:
        falta = "<b>completa</b>"
    elif not est["custo_falta"] and est["sem_preco"]:
        # tudo o que falta está sem preço: «0,00 €» seria um número inventado
        falta = f"falta <b>—</b>{sp}"
    else:
        falta = f'falta <b>{paginas.eur(est["custo_falta"])}</b>{sp}'
    return (visual.barra(est["tenho"], est["total"])
            + f'<div class="kpi"><span>{est["tenho"]} de {est["total"]} cartas'
            f' · {visual.pct_de(est["tenho"], est["total"])} %{validadas}</span>'
            f'<span>{falta}</span></div>')


# A busca de «juntar carta» (só na coleção aberta, só em edição): é a de Vender
# — o `edicao_js` procura no catálogo (`/api/n/procurar`) e um toque num nome
# abre a escolha da edição e do acabamento. Fica escondida atrás do botão, para
# a página não abrir com um campo de texto (e o teclado) à frente das cartas.
def _juntar(slug: str) -> str:
    return (f'<div class="ed-lin cjb"><button type="button" class="btn ed-b cbt pri"'
            f' data-acao="cjuntar" data-colecao="{e(slug)}">Juntar carta</button></div>'
            # um `<div>`, não uma `<section>`: dentro da secção da coleção
            '<div class="ed-proc" role="search" hidden aria-labelledby="ed-proc-t">'
            '<h2 class="gt" id="ed-proc-t">Juntar uma carta</h2>'
            '<label for="ed-q">Procura a carta (pelo nome em inglês)</label>'
            '<input id="ed-q" type="search" autocomplete="off" autocapitalize="off"'
            ' spellcheck="false" enterkeyhint="search" placeholder="ex.: Moat">'
            f'<ul class="ed-res" id="ed-res" data-res="cjuntar"'
            f' data-colecao="{e(slug)}" aria-live="polite"></ul></div>')


def seccao_colecao(item: dict, hoje: str, editavel: bool = False) -> str:
    est = item["estado"]
    cartas = (visual.grelha_colecao(est["cartas"], slug=est["slug"], hoje=hoje,
                                    editavel=editavel)
              if est["cartas"] else
              '<p class="vazio">Ainda não há cartas nesta coleção.</p>')
    juntar = _juntar(est["slug"]) if editavel and est["tipo"] == "aberta" else ""
    return (f'<section class="dk" id="{e(est["slug"])}" data-nome="{e(est["nome"])}"'
            f' aria-labelledby="t-{e(est["slug"])}">'
            '<a class="volta lk" href="#">← Todas as coleções</a>'
            f'{_cabecalho(item)}{_valor(item)}{_progresso(est)}'
            f'<h2 class="gt">Cartas <small>{paginas.plural(len(est["cartas"]), "carta")}'
            f' na lista</small></h2>{juntar}{cartas}</section>')


# ---------------------------------------------------------------------------
# A subir
# ---------------------------------------------------------------------------
def seccao_subir(linhas: list[dict]) -> str:
    minimo = cotacoes.MINIMO_SUBIR
    return ('<section class="dk" id="subir" data-nome="A subir" '
            'aria-labelledby="t-subir"><a class="volta lk" href="#">← Todas as '
            'coleções</a><header class="dkh"><div><h2 id="t-subir">A subir</h2>'
            f'<div class="dks">Reserved List e as edições dos duals, shocks, '
            f'fetches e Zendikar Expeditions, só acima de '
            f'{paginas.eur(minimo, 0)} · por variação a 30 dias</div></div>'
            f'</header>{visual.tabela_subir(linhas, minimo)}</section>')


# ---------------------------------------------------------------------------
# A página
# ---------------------------------------------------------------------------
def _nao_preparadas() -> str:
    return ('<p class="vazio espera"><b>As coleções ainda não foram preparadas.</b>'
            'Aparecem aqui quando o modo de edição arrancar ou na próxima '
            'atualização diária.</p>')


def _tem_colecoes(con) -> bool:
    """Há coleções na base? Uma base sem as tabelas `n_colecao*` (ainda não
    migrada) conta como «não»: a página nunca cria nada."""
    try:
        return bool(colecoes.colecoes(con))
    except sqlite3.OperationalError:
        return False


def html_page(con, *, editable: bool = False, token: str = "",
              hoje: str | None = None) -> str:
    """A página inteira. Com `editable`, o `<body>` leva a marca do modo de
    edição; o `token` nunca é escrito na página. `hoje` é para os testes. Só
    lê: não cria as coleções (ver o início do módulo)."""
    # o `token` não se escreve: o JavaScript da edição lê-o do `?t=` do URL
    del token
    hoje = hoje or date.today().isoformat()
    if not _tem_colecoes(con):
        corpo_ = _nao_preparadas()
    else:
        itens = _dados(con, hoje)
        subir = cotacoes.a_subir(con, hoje)
        tiles = ("".join(visual.mosaico_colecao(i, f'#{i["estado"]["slug"]}')
                         for i in itens)
                 + visual.mosaico_subir(subir, "#subir", cotacoes.MINIMO_SUBIR))
        corpo_ = ('<div id="todos"><h2 class="gt">Coleções <small>'
                  f'{paginas.plural(len(itens), "coleção", "coleções")} e as '
                  f'cartas a subir</small></h2><div class="tiles">{tiles}</div>'
                  "</div>"
                  + "".join(seccao_colecao(i, hoje, editable) for i in itens)
                  + seccao_subir(subir))
    return ("<!doctype html><html lang=\"pt-PT\"><head>"
            + shell.head(TITULO, visual.CSS + edicao_js.css(editable)) + "</head>"
            + visual.corpo(editable)
            + shell.abrir(FICHEIRO, TITULO, _SUB)
            + f'<div class="wrap nuc">{corpo_}</div>'
            + shell.fechar(_RODAPE, f"<script>{visual.JS_ROTA}</script>"
                           f"<script>{visual.JS_GRAFICO}</script>"
                           + edicao_js.script(editable))
            + "</body></html>")


def build(con, out_path=None, rep=None) -> Path:
    """Escreve `colecoes.html`. O `rep` aceita-se e não se usa."""
    out = Path(out_path) if out_path else ROOT / FICHEIRO
    out.write_text(html_page(con), encoding="utf-8")
    return out


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print(build(con))
