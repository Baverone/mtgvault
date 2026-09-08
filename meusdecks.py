"""Gera meusdecks.html — que desde a v6 é só um REENCAMINHAMENTO.

André, 2026-09-08: *"No mtgvault já começamos a ter informação duplicada. Temos
decks vigiados e deckbox que é a mesma coisa."*

Esta página era a *Decks permanentes*: os decks que ele segue, com a % de
completo, a evolução da lista e a lista toda em arte. Fazia exactamente a mesma
pergunta que a *Deckboxes* — **quanto tenho deste deck?** — e respondia com outro
número, porque contava a **colecção inteira** por deck em vez da alocação. Duas
respostas para a mesma pergunta, com o rodapé de cada página a explicar porque é
que a outra estava certa também: é o padrão que já custou caro no `event_tier` e
no filtro de listas.

Na v6 a **Deckboxes é a página dos decks**. O que esta tinha e ela não tinha
mudou-se para lá, para a aba de cada caixa:

  * a lista agrupada por tipo e com **imagens grandes** (o botão *imagens
    grandes* / *por tipo*);
  * o **texto da lista** para copiar (*copiar a lista*);
  * **quantas tenho na colecção inteira**, como informação secundária de cada
    carta (no `title` do cartão) — o número que manda continua a ser o da
    alocação;
  * a **evolução da lista vigiada** aparece onde é accionável: o delta *"tirar
    X, meter Y"* da aba *Arrumar*, nas caixas montadas.

O ficheiro continua a ser gerado porque o telemóvel dele tem o link no histórico
e o site publicado tem-no em páginas antigas. Um 404 não explica nada; "mudou de
sítio, é aqui" explica. As funções que outras páginas usavam (agrupar por tipo,
o mapa de tipos, o bloco de faltas) vivem agora em `mtgvault/paginas.py` — é o
sítio das coisas que as páginas partilham.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

import deckboxes  # noqa: E402

DESTINO = "deckboxes.html"


def build(con=None, out_path=None):
    out = Path(out_path) if out_path else (ROOT / "meusdecks.html")
    out.write_text(deckboxes.redireccionamento(DESTINO, "Decks permanentes"),
                   encoding="utf-8")
    return out


def main():
    print("meusdecks.html:", build())


if __name__ == "__main__":
    main()
