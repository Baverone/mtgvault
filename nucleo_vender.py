"""Gera a página Vender do núcleo novo (`vender.html`): o que tens a mais, o que
saiu das listas dos decks e o que ficou de uma edição que trocaste — cada carta
com a edição, o acabamento, a quantidade e o preço de hoje, e o total no topo.

As linhas vêm todas do `valor.a_vender` (o mesmo preço do valor da coleção: o
trend do Cardmarket da impressão e do acabamento exatos). Uma carta sem preço
diz «sem preço» e fica fora do total — nunca vale 0 €.
"""
from __future__ import annotations

import html
from pathlib import Path

from mtgvault import paginas
from mtgvault import site_shell as shell
from mtgvault.nucleo import valor, visual

ROOT = Path(__file__).resolve().parent
FICHEIRO = "vender.html"
TITULO = "Vender"

e = html.escape

_SUB = "O que podes vender, ao preço de hoje."

_RODAPE = ("Preço: o trend do Cardmarket da edição e do acabamento de cada "
           "carta. As cartas que saem de um deck continuam a ser tuas até "
           "decidires o que lhes fazer.")

# (motivo, título, frase quando está vazio)
BLOCOS = (
    ("a_mais", "Tenho a mais", "Nada marcado como a mais."),
    ("saiu_da_lista", "Saíram dos decks", "Nenhuma carta saiu da lista de um deck."),
    ("trocou_edicao", "Trocaste de edição", "Nenhuma troca de edição por decidir."),
)


def _linha(l: dict, editavel: bool) -> str:
    dados = ""
    if editavel:
        dados = (f' data-sid="{e(l["scryfall_id"])}" data-acab="{e(l["acabamento"])}"'
                 f' data-nome="{e(l["nome"])}" data-motivo="{e(l["motivo"])}"')
        if "id" in l:
            dados += f' data-saida="{l["id"]}"'
    img = (visual.img_carta(l["scryfall_id"], l["nome"])
           if l["scryfall_id"] else '<span class="vsem"></span>')
    meta = [e((l["set_code"] or "?").upper()),
            visual.ACABAMENTO.get(l["acabamento"], e(l["acabamento"]))]
    if l["deck"]:
        meta.append(f'do {e(l["deck"])}')
    if l["preco_un"] is None:
        num = f'<span class="sp">sem preço</span><b>—</b>'
        un = f'×{l["qtd"]} · {num}'
    else:
        un = (f'×{l["qtd"]} · {paginas.eur(l["preco_un"])}/un'
              f'<b>{paginas.eur(l["qtd"] * l["preco_un"])}</b>')
    return (f'<li class="vl"{dados}>{img}<div class="vi"><b>{e(l["nome"])}</b>'
            f'<small>{" · ".join(meta)}</small></div>'
            f'<div class="vn">{un}</div></li>')


def _bloco(titulo: str, vazio: str, linhas: list[dict], editavel: bool) -> str:
    total = sum(l["qtd"] * l["preco_un"] for l in linhas if l["preco_un"] is not None)
    copias = sum(l["qtd"] for l in linhas)
    cab = (f'<h2 class="gt">{titulo} <small>{paginas.plural(copias, "cópia")}</small>'
           f'<span class="val">{paginas.eur(total)}</span></h2>' if linhas
           else f'<h2 class="gt">{titulo}</h2>')
    if not linhas:
        return cab + f'<p class="vazio">{vazio}</p>'
    return (cab + '<ul class="vls">'
            + "".join(_linha(l, editavel) for l in linhas) + "</ul>")


def html_page(con, *, editable: bool = False, token: str = "") -> str:
    """A página inteira. Com `editable`, cada linha leva `data-sid`,
    `data-acab`, `data-nome`, `data-motivo` (e `data-saida` nas saídas); o
    `token` nunca é escrito na página."""
    del token                     # o modo de edição (Task 8) lê-o do URL
    v = valor.a_vender(con)
    todas = v["a_mais"] + v["saidas"]
    copias = sum(l["qtd"] for l in todas)
    nota = paginas.plural(copias, "cópia") if copias else "nada por decidir"
    if v["sem_preco"]:
        nota += (f" · {paginas.plural(v['sem_preco'], 'cópia')} sem preço"
                 " fora do total")
    corpo_ = (f'<div class="vtot"><span>Se venderes tudo<small>{nota}</small>'
              f'</span><b>{paginas.eur(v["total_eur"])}</b></div>')
    for motivo, titulo, vazio in BLOCOS:
        linhas = [l for l in todas if l["motivo"] == motivo]
        corpo_ += _bloco(titulo, vazio, linhas, editable)
    return ("<!doctype html><html lang=\"pt-PT\"><head>"
            + shell.head(TITULO, visual.CSS) + "</head>" + visual.corpo(editable)
            + shell.abrir(FICHEIRO, TITULO, _SUB)
            + f'<div class="wrap nuc">{corpo_}</div>'
            + shell.fechar(_RODAPE) + "</body></html>")


def build(con, out_path=None, rep=None) -> Path:
    """Escreve `vender.html`. O `rep` aceita-se e não se usa."""
    out = Path(out_path) if out_path else ROOT / FICHEIRO
    out.write_text(html_page(con), encoding="utf-8")
    return out


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print(build(con))
