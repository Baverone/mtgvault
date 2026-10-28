"""Gera a página dos decks do núcleo novo (`deck.html`): os 14 decks numa
página só, um por `<section id="<slug>">`, e a grelha de todos quando não há
`#` no endereço.

Uma página e não catorze porque a casca e os testes só aceitam páginas na raiz
(spec «Páginas»). O JavaScript mostra a secção do `location.hash` e esconde as
outras; o botão «voltar» do telemóvel funciona porque cada deck é uma entrada
do histórico (`hashchange`). Sem JavaScript vê-se tudo, uma secção a seguir à
outra.

Cada deck: o cabeçalho (progresso, quanto falta em euros, a versão da lista, a
fonte e o que mudou na última, «ver versões») e as cartas em imagem — a cores
as que tens, a cinzento as que faltam. Os rotativos em duas partes, «Fixas
deste deck» e «Partilhadas» (com o sítio onde está o monte), e a caixa «Para
montar este deck». As peças vivem em `mtgvault/nucleo/visual.py`.
"""
from __future__ import annotations

import html
from pathlib import Path

from mtgvault import paginas
from mtgvault import site_shell as shell
from mtgvault.nucleo import listas, posse, visual
from mtgvault.nucleo.listas import Linha

ROOT = Path(__file__).resolve().parent
FICHEIRO = "deck.html"
TITULO = "Decks"

e = html.escape

_SUB = ("Toca num deck para ver as cartas: a cores as que tens, a cinzento as "
        "que faltam.")

_RODAPE = ("O preço de uma carta em falta é o trend do Cardmarket da edição "
           "escolhida (sem escolha, a normal mais barata com preço). «Sem preço» "
           "fica fora do «falta». Completo inclui o sideboard e o comandante.")

JS = r"""
(function(){
  var todos = document.getElementById('todos'),
      secs = document.querySelectorAll('section.dk'),
      titulo = document.title;
  function mostra(){
    var h = '';
    try { h = decodeURIComponent((location.hash || '').slice(1)); } catch (e) {}
    var alvo = null, i;
    for (i = 0; i < secs.length; i++) if (secs[i].id === h) alvo = secs[i];
    for (i = 0; i < secs.length; i++) secs[i].hidden = secs[i] !== alvo;
    if (todos) todos.hidden = !!alvo;
    var nome = alvo && alvo.getAttribute('data-nome');
    document.title = nome ? nome + ' · ' + titulo : titulo;
    if (alvo) window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', mostra);
  mostra();
})();
"""


# ---------------------------------------------------------------------------
# As versões
# ---------------------------------------------------------------------------
def versoes(con, slug: str) -> list[dict]:
    """Todas as versões do deck, da mais recente para a mais antiga, cada uma
    com o que entrou e saiu em relação à anterior (`None` na primeira)."""
    vs = con.execute("SELECT id, numero, criada_em, fonte, origem FROM n_versao"
                     " WHERE slug = ? ORDER BY numero", (slug,)).fetchall()
    out, antes = [], None
    for v in vs:
        linhas = [Linha(*c) for c in con.execute(
            "SELECT seccao, nome, qtd FROM n_versao_carta WHERE versao_id = ?"
            " ORDER BY rowid", (v[0],))]
        out.append({"numero": v[1], "criada_em": v[2], "fonte": v[3],
                    "origem": v[4],
                    "dif": None if antes is None else listas.diferenca(antes, linhas)})
        antes = linhas
    return out[::-1]


def _linha_versao(v: dict) -> str:
    quem = " (vigia)" if v["origem"] == "vigia" else ""
    return (f'<b>v{v["numero"]}</b> · {visual.data_pt(v["criada_em"])} · '
            f'{visual.fonte_html(v["fonte"])}{quem}')


def _versoes_html(vs: list[dict]) -> str:
    atual = vs[0]
    linha = _linha_versao(atual)
    if atual["dif"] is not None:
        linha += f'<br>v{atual["numero"]} vs v{atual["numero"] - 1}: ' \
                 + visual.diferenca_html(atual["dif"])
    itens = "".join(
        f'<li>{_linha_versao(v)}<br>'
        + ("primeira lista" if v["dif"] is None
           else visual.diferenca_html(v["dif"], limite=None)) + "</li>"
        for v in vs)
    return (f'<div class="ver">{linha}</div>'
            f'<details class="versoes"><summary>ver versões '
            f'({len(vs)})</summary><ol>{itens}</ol></details>')


# ---------------------------------------------------------------------------
# Um deck
# ---------------------------------------------------------------------------
def _cabecalho(item: dict) -> str:
    d, est = item["deck"], item["estado"]
    arte = (f'<img class="dka" src="{visual.url_arte(item["arte"])}" alt=""'
            f' loading="lazy" decoding="async" width="626" height="457">'
            if item["arte"] else '<span class="dka"></span>')
    modo = "sempre montado" if d["modo"] == "sempre" else "rotativo"
    return (f'<header class="dkh">{arte}<div><h2 id="t-{e(d["slug"])}">'
            f'{e(d["nome"])}</h2><div class="dks">{e(visual.formato(d["formato"]))}'
            f' · {modo} · {visual.vigia_texto(d["vigia"])}</div></div></header>')


def _aviso(d) -> str:
    frase = visual.aviso_vigia(d)
    if not frase:
        return ""
    return (f'<div class="avisov" role="note">{shell.icone("aviso", 16)}'
            f'<div><b>Vigia:</b> {e(frase)}.'
            f'<small>{e(d["vigia_erro"])}</small></div></div>')


def _progresso(est: dict) -> str:
    sp = (f' <small>({est["sem_preco"]} sem preço)</small>'
          if est["sem_preco"] else "")
    if est["tenho"] >= est["total"]:
        falta = '<b>completo</b>'
    elif not est["custo_falta"] and est["sem_preco"]:
        # tudo o que falta está sem preço: «0,00 €» seria um número inventado
        falta = f'falta <b>—</b>{sp}'
    else:
        falta = f'falta <b>{paginas.eur(est["custo_falta"])}</b>{sp}'
    return (visual.barra(est["tenho"], est["total"])
            + f'<div class="kpi"><span>{est["tenho"]} de {est["total"]} cartas'
            f' · {visual.pct_de(est["tenho"], est["total"])} %</span>'
            f'<span>{falta}</span></div>')


def _conta(cartas) -> str:
    return (f'{sum(c["tenho"] for c in cartas)} de '
            f'{sum(c["qtd"] for c in cartas)}')


def _cartas_sempre(est: dict, editavel: bool) -> str:
    out = ""
    for s in visual.ORDEM_SECCAO:
        cs = [c for c in est["cartas"] if c["seccao"] == s]
        if not cs:
            continue
        out += (f'<h2 class="gt">{visual.SECCAO[s]} <small>{_conta(cs)}</small></h2>'
                + visual.grelha(cs, slug=est["slug"], editavel=editavel))
    return out


def _cartas_rotativo(est: dict, editavel: bool) -> str:
    fixas = [c for c in est["cartas"] if c["grupo"] == "fixa"]
    part = [c for c in est["cartas"] if c["grupo"] == "partilhada"]
    out = ('<h2 class="gt">Fixas deste deck <small>vivem na caixa dele · '
           f'{_conta(fixas)}</small></h2>')
    out += (visual.grelha(fixas, slug=est["slug"], editavel=editavel) if fixas
            else '<p class="vazio">Todas as cartas deste deck são partilhadas.</p>')
    out += ('<h2 class="gt">Partilhadas <small>andam com o deck montado · '
            f'{_conta(part)}</small></h2>')
    out += (visual.grelha(part, slug=est["slug"], editavel=editavel, com_onde=True)
            if part else '<p class="vazio">Nenhuma carta em comum com outro '
                         'rotativo.</p>')
    return out


def _montar(con, est: dict, nomes: dict) -> str:
    if est["montado"]:
        return ('<div class="mv ok"><b>Está montado</b>As partilhadas estão na '
                'caixa dele.</div>')
    movs = posse.movimentos_para(con, est["slug"])
    if not movs:
        return ""
    de = nomes.get(movs[0]["de"], movs[0]["de"])
    lista = ", ".join(f'{m["qtd"]} {e(m["nome"])}' for m in movs)
    return (f'<div class="mv"><b>Para montar este deck</b>Montado agora: '
            f'{e(de)}. Traz da caixa do {e(de)}: {lista}.</div>')


def _espera(d) -> str:
    if d["vigia"]:
        if visual.aviso_vigia(d):
            return ""            # o aviso da vigia já diz o que há
        return ('<p class="vazio espera"><b>À espera da primeira leitura</b>'
                'A lista entra sozinha quando a vigia a ler.</p>')
    return ('<p class="vazio espera"><b>À espera da tua lista</b>'
            'Cola-a no modo de edição, com «de onde veio».</p>')


def seccao(con, item: dict, nomes: dict, editavel: bool) -> str:
    d, est = item["deck"], item["estado"]
    corpo_ = _cabecalho(item) + _aviso(d)
    if est["versao"] is None:
        corpo_ += _espera(d)
    else:
        corpo_ += _progresso(est) + _versoes_html(versoes(con, d["slug"]))
        if d["modo"] == "rotativo":
            corpo_ += _cartas_rotativo(est, editavel) + _montar(con, est, nomes)
        else:
            corpo_ += _cartas_sempre(est, editavel)
    return (f'<section class="dk" id="{e(d["slug"])}" data-nome="{e(d["nome"])}"'
            f' aria-labelledby="t-{e(d["slug"])}">'
            '<a class="volta lk" href="#">← Todos os decks</a>'
            f'{corpo_}</section>')


def html_page(con, *, editable: bool = False, token: str = "") -> str:
    """A página inteira. Com `editable`, as cartas levam `data-deck`,
    `data-nome`, `data-sid` e `data-acab` e o `<body>` a marca do modo de
    edição; o `token` nunca é escrito na página."""
    del token                     # o modo de edição (Task 8) lê-o do URL
    itens = visual.dados_decks(con)
    nomes = {i["deck"]["slug"]: i["deck"]["nome"] for i in itens}
    corpo_ = (f'<div id="todos">{visual.mosaicos(itens, "")}</div>'
              + "".join(seccao(con, i, nomes, editable) for i in itens))
    return ("<!doctype html><html lang=\"pt-PT\"><head>"
            + shell.head(TITULO, visual.CSS) + "</head>" + visual.corpo(editable)
            + shell.abrir(FICHEIRO, TITULO, _SUB)
            + f'<div class="wrap nuc">{corpo_}</div>'
            + shell.fechar(_RODAPE, f"<script>{JS}</script>")
            + "</body></html>")


def build(con, out_path=None, rep=None) -> Path:
    """Escreve `deck.html`. O `rep` aceita-se e não se usa."""
    out = Path(out_path) if out_path else ROOT / FICHEIRO
    out.write_text(html_page(con), encoding="utf-8")
    return out


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print(build(con))
