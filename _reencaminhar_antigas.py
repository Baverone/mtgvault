"""Troca as 14 páginas antigas do mtgvault por avisos, com a casca do site,
que levam ao site novo (29/10/2026). Uso: `py _reencaminhar_antigas.py .` na
raiz do mtgvault. Desligar o `nucleo.ligado` e correr o daily repõe as antigas."""
import html
import sys
from pathlib import Path

raiz = Path(sys.argv[1])
sys.path.insert(0, str(raiz))
from mtgvault import site_shell as shell  # noqa: E402

PARA_DECKS = {"decks.html", "meusdecks.html", "deckboxes.html", "decksfaziveis.html",
              "faltas.html", "comandantes.html", "caixarl.html", "arrumacao.html"}
ANTIGAS = ["arrumacao.html", "caixarl.html", "cobertura.html", "colecao.html",
           "colecao_cor.html", "comandantes.html", "deckboxes.html", "decks.html",
           "decksfaziveis.html", "faltas.html", "metagame.html", "meusdecks.html",
           "reservedlist.html", "showcase.html"]
TITULO = "Esta página mudou"

for f in ANTIGAS:
    p = raiz / f
    assert p.is_file(), p
    alvo, nome = (("deck.html", "os teus decks") if f in PARA_DECKS
                  else ("index.html", "o Painel"))
    extra = (f'<meta http-equiv="refresh" content="0; url={alvo}">'
             f'<meta name="robots" content="noindex">')
    corpo = (f'<div class="wrap"><p>Esta página saiu do site em 29/10/2026: o site '
             f'passou a ter só o Painel, os Decks e o Vender.</p>'
             f'<p><a href="{alvo}">Ir para {html.escape(nome)}</a></p></div>')
    txt = ("<!doctype html><html lang=\"pt-PT\"><head>"
           + shell.head(TITULO, "", extra) + "</head><body>"
           + shell.abrir(f, TITULO, "")
           + corpo
           + shell.fechar("", f'<script>location.replace("{alvo}");</script>')
           + "</body></html>")
    p.write_text(txt, encoding="utf-8", newline="\n")
    print(f, "->", alvo)
