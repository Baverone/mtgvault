"""Gera o Painel do núcleo novo (`index.html`): quanto vale o que tens, a
variação do mês e o gráfico, os 14 decks em mosaico e a caixa Vender.

É a primeira das quatro perguntas do site (spec «Páginas», 2026-10-28): que
decks tenho, o que falta, o que vender, como evolui o valor. O desenho é o do
esboço aprovado pelo André («B · Painel + página de cada deck», gráfico «Só o
que tens»): uma linha só, a do que ele tem. As peças vivem em
`mtgvault/nucleo/visual.py`.
"""
from __future__ import annotations

from pathlib import Path

from mtgvault import paginas
from mtgvault import site_shell as shell
from mtgvault.nucleo import valor, visual

ROOT = Path(__file__).resolve().parent
FICHEIRO = "index.html"
TITULO = "Painel"

_SUB = "Os teus decks, o que lhes falta e quanto vale o que tens."


def _rodape(dia: str | None) -> str:
    return ("O valor soma o que marcaste como teu — decks, partilhadas, tenho a "
            "mais e o que saiu dos decks —, cada cópia uma vez, ao trend do "
            "Cardmarket da edição e do acabamento dela. Uma carta sem preço fica "
            f"fora da soma. Preços de {visual.data_pt(dia)}.")


def _valor(con) -> str:
    v = valor.valor_em(con)
    s = valor.serie(con)
    nota = paginas.plural(v["copias"], "cópia")
    if v["sem_preco"]:
        nota += f" · {paginas.plural(v['sem_preco'], 'cópia')} sem preço fora da soma"
    if not v["copias"]:
        nota = "Ainda não marcaste nenhuma carta como tua."
    return ('<section class="vcard" aria-label="Valor do que tens">'
            '<div class="vlab">O que tens vale</div>'
            f'<div class="vlin"><span class="vbig">{paginas.eur(v["total_eur"])}</span>'
            f'{visual.variacao_html(s)}</div>'
            f'<p class="vnota">{nota}</p>{visual.grafico(s)}</section>')


def _vender(con) -> str:
    v = valor.a_vender(con)
    linhas = v["a_mais"] + v["saidas"]
    copias = sum(l["qtd"] for l in linhas)
    if not copias:
        txt = "Vender<small>nada por decidir</small>"
    else:
        sp = (f" · {v['sem_preco']} sem preço" if v["sem_preco"] else "")
        txt = f"Vender<small>{paginas.plural(copias, 'cópia')}{sp}</small>"
    return (f'<a class="vbox" href="vender.html"><span>{txt}</span>'
            f'<b>{paginas.eur(v["total_eur"])}</b></a>')


def html_page(con, *, editable: bool = False, token: str = "") -> str:
    """A página inteira. Com `editable`, o `<body>` leva a marca do modo de
    edição; o `token` nunca é escrito na página."""
    del token                     # o modo de edição (Task 8) lê-o do URL
    corpo_ = (_valor(con) + visual.mosaicos(visual.dados_decks(con), "deck.html")
              + _vender(con))
    return ("<!doctype html><html lang=\"pt-PT\"><head>"
            + shell.head(TITULO, visual.CSS) + "</head>" + visual.corpo(editable)
            + shell.abrir(FICHEIRO, TITULO, _SUB)
            + f'<div class="wrap nuc">{corpo_}</div>'
            + shell.fechar(_rodape(visual.preco_do_dia(con)),
                           f"<script>{visual.JS_GRAFICO}</script>")
            + "</body></html>")


def build(con, out_path=None, rep=None) -> Path:
    """Escreve `index.html`. O `rep` (o relatório do loadout antigo, que o
    `publicar` passa a todas) aceita-se e não se usa."""
    out = Path(out_path) if out_path else ROOT / FICHEIRO
    out.write_text(html_page(con), encoding="utf-8")
    return out


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print(build(con))
