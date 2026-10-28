"""As vigias do núcleo: manter atualizados os 4 decks que têm a lista noutro sítio.

Dois vêm do MTGO (as listas do jogador LuffyDoChapeuDePalha que a recolha diária,
`harvest-mtgo`, já guardou em `decklists`) e dois do Moxfield, através de um
**ficheiro** `AAAA-MM-DD.json` que outra tarefa (a do ai-pc, no Chrome do André)
escreve depois de ler os decks. Este módulo nunca fala com o Moxfield: o site
recusa pedidos que não sejam de um browser a sério, e fingir um (User-Agent
falso) é o contrário do que se quer. Só lê o ficheiro.

A `vigia` de cada deck (`n_deck.vigia`) diz de onde vem a lista:
`mtgo:<jogador>:<formato>` ou `moxfield:<id público>`.

Regras que importam:
- uma vigia que falha **não** estraga as outras, nem escreve uma versão pela
  metade: `NomesDesconhecidos` numa lista lida conta como falha daquele deck;
- `n_deck.vigia_ok_em` marca a última leitura que correu bem (nova ou igual) e
  `vigia_erro` a razão da falha, em português. Numa falha o `vigia_ok_em` fica
  como estava — é ele que deixa a página dizer «desde dia X»;
- só escreve nas tabelas `n_*`. As `decklists` só se leem.

Formato do ficheiro do Moxfield, `data/moxfield/AAAA-MM-DD.json`:
`{"lido_em": iso, "decks": {"<id>": {"texto": "<export>", "titulo": str}
| {"erro": str}}}`.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from . import listas, modelo
from .listas import Linha, NomesDesconhecidos

PASTA_MOXFIELD = Path(os.environ.get(
    "MTGVAULT_MOXFIELD_DIR",
    Path(__file__).resolve().parents[2] / "data" / "moxfield"))

# o `source` que o `sources.harvest_mtgo` escreve (`store_decklist(source="mtgo")`)
FONTE_MTGO = "mtgo"

_FICHEIRO = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
_BOARD_PARA_SECCAO = {"main": "main", "side": "side"}
_MAX_NOMES_NA_MENSAGEM = 8

# estados que contam como falha da vigia. `sem_lista_nova` (MTGO: nada na janela
# da recolha, mas o deck já tem versão) NÃO é falha.
FALHAS = ("sem_lista", "sem_ficheiro", "erro")


class VigiaFalhou(RuntimeError):
    """Pelo menos uma vigia falhou. `falhas` = {slug: resultado} das que falharam
    (as que correram bem já ficaram gravadas quando isto se levanta)."""

    def __init__(self, falhas: dict[str, dict]):
        self.falhas = dict(falhas)
        partes = [f"{slug}: {r.get('mensagem', r.get('estado'))}"
                  for slug, r in self.falhas.items()]
        super().__init__("vigia(s) com falha — " + "; ".join(partes))


# ---------------------------------------------------------------------------
# O que é comum às duas fontes
# ---------------------------------------------------------------------------
def _vigia_do_deck(con: sqlite3.Connection, slug: str) -> str | None:
    r = con.execute("SELECT vigia FROM n_deck WHERE slug = ?", (slug,)).fetchone()
    if r is None:
        raise ValueError(f"deck desconhecido: {slug!r}")
    return r[0]


def _falha(estado: str, mensagem: str) -> dict:
    return {"estado": estado, "mensagem": mensagem}


def _mensagem_nomes(nomes: list[str]) -> str:
    vistos = nomes[:_MAX_NOMES_NA_MENSAGEM]
    resto = len(nomes) - len(vistos)
    texto = "; ".join(vistos) + (f" (e mais {resto})" if resto > 0 else "")
    return f"o catálogo não conhece estas cartas: {texto}"


def _gravar(con: sqlite3.Connection, slug: str, ler_linhas, fonte: str) -> dict:
    """Grava a lista lida como versão do deck. Nunca grava metade: o
    `listas.gravar_versao` valida todos os nomes antes de escrever. `ler_linhas`
    é uma função sem argumentos que devolve as `Linha`s: a leitura do texto fica
    dentro da mesma guarda, porque uma linha mal formada (um `SB:` sozinho) é uma
    falha deste deck e não uma exceção a subir."""
    try:
        linhas = ler_linhas()
    except Exception as e:
        return _falha("erro", f"não consegui ler a lista ({type(e).__name__}): {e}")
    try:
        r = listas.gravar_versao(con, slug, linhas, fonte=fonte, origem="vigia")
    except NomesDesconhecidos as e:
        return _falha("erro", _mensagem_nomes(e.nomes))
    except ValueError as e:                      # lista vazia, etc.
        return _falha("erro", str(e))
    if r is None:
        return {"estado": "igual", "fonte": fonte}
    return {"estado": "nova", "fonte": fonte, "numero": r["numero"],
            "versao_id": r["versao_id"], "entrou": r["entrou"], "saiu": r["saiu"]}


# ---------------------------------------------------------------------------
# MTGO: a última lista do jogador que a recolha já guardou
# ---------------------------------------------------------------------------
def vigiar_mtgo(con: sqlite3.Connection, slug: str) -> dict:
    """Lê a lista mais recente do jogador no formato do deck (`decklists`, fonte
    MTGO; o jogador compara-se sem caixa; mais recente = `event_date`, e o `id`
    desempata) e grava-a como versão nova se mudou.

    `{"estado": "nova" | "igual" | "sem_lista" | "sem_lista_nova" | "erro", ...}`;
    `sem_lista` só se o deck nunca teve versão.
    """
    vigia = _vigia_do_deck(con, slug)
    partes = (vigia or "").split(":", 2)
    if len(partes) != 3 or partes[0] != "mtgo" or not all(partes[1:]):
        return _falha("erro", f"vigia MTGO mal escrita: {vigia!r}"
                              " (devia ser mtgo:<jogador>:<formato>)")
    _, jogador, formato = partes
    d = con.execute(
        "SELECT id, event_name, event_date, url FROM decklists"
        " WHERE source = ? AND lower(player) = lower(?) AND format = ?"
        " ORDER BY event_date DESC, id DESC LIMIT 1",
        (FONTE_MTGO, jogador, formato)).fetchone()
    if d is None:
        if listas.versao_atual(con, slug) is not None:
            # a recolha só guarda 30 dias de listas: o jogador não jogou nesse
            # tempo. A lista que o deck já tem continua a ser a dele — não é uma
            # falha, só não há novidade (a página mostra a data da versão).
            return {"estado": "sem_lista_nova",
                    "mensagem": f"{jogador} não tem lista nova em {formato} no MTGO"
                                " (fica a última versão)"}
        return _falha("sem_lista",
                      f"ainda não há lista de {jogador} em {formato} no MTGO")
    cartas = con.execute(
        "SELECT board, card_name, quantity FROM decklist_cards"
        " WHERE decklist_id = ? ORDER BY rowid", (d[0],)).fetchall()
    fonte = " · ".join(p for p in ("MTGO", d[1], d[2], d[3]) if p)
    return _gravar(con, slug, lambda: [Linha(_BOARD_PARA_SECCAO[b], n, q)
                                       for b, n, q in cartas], fonte)


# ---------------------------------------------------------------------------
# Moxfield: o ficheiro que a tarefa do ai-pc escreve
# ---------------------------------------------------------------------------
def _ficheiro_mais_recente(pasta: Path) -> Path | None:
    """O `AAAA-MM-DD.json` de nome mais alto. Outros nomes ignoram-se."""
    try:
        nomes = [p for p in Path(pasta).iterdir()
                 if p.is_file() and _FICHEIRO.match(p.name)]
    except OSError:
        return None
    return max(nomes, key=lambda p: p.name) if nomes else None


def vigiar_moxfield(con: sqlite3.Connection, slug: str,
                    pasta: Path | None = None) -> dict:
    """Lê o deck do ficheiro mais recente de `pasta` e grava-o como versão nova
    se mudou. Não procura em ficheiros mais antigos: um ficheiro de hoje que não
    traz o deck é uma falha de hoje, e a página di-lo.

    `{"estado": "nova" | "igual" | "sem_ficheiro" | "erro", ...}`.
    """
    pasta = PASTA_MOXFIELD if pasta is None else Path(pasta)
    vigia = _vigia_do_deck(con, slug)
    partes = (vigia or "").split(":", 1)
    if len(partes) != 2 or partes[0] != "moxfield" or not partes[1]:
        return _falha("erro", f"vigia Moxfield mal escrita: {vigia!r}"
                              " (devia ser moxfield:<id>)")
    id_deck = partes[1]

    ficheiro = _ficheiro_mais_recente(pasta)
    if ficheiro is None:
        return _falha("sem_ficheiro",
                      "ainda não há ficheiro do Moxfield em " + str(pasta))
    dia = _FICHEIRO.match(ficheiro.name).group(1)
    try:
        dados = json.loads(ficheiro.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return _falha("erro", f"não consegui ler o ficheiro de {dia}: {e}")
    decks = dados.get("decks") if isinstance(dados, dict) else None
    if not isinstance(decks, dict):
        return _falha("erro", f"o ficheiro de {dia} não tem o formato esperado")
    if id_deck not in decks:
        return _falha("sem_ficheiro", f"o ficheiro de {dia} não tem este deck")
    entrada = decks[id_deck]
    if not isinstance(entrada, dict):
        return _falha("erro", f"o ficheiro de {dia} traz este deck mal formado")
    if entrada.get("erro"):
        return _falha("erro", f"o Moxfield falhou a {dia}: {entrada['erro']}")
    texto = entrada.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        return _falha("erro", f"o ficheiro de {dia} traz este deck sem lista")

    lido = dados.get("lido_em")
    data_lida = lido[:10] if isinstance(lido, str) and _DATA.match(lido) else dia
    fonte = f"Moxfield · https://moxfield.com/decks/{id_deck} · lido a {data_lida}"
    return _gravar(con, slug, lambda: listas.ler_texto(texto), fonte)


_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# Todas
# ---------------------------------------------------------------------------
def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _vigiar_um(con: sqlite3.Connection, slug: str, vigia: str,
               pasta: Path | None) -> dict:
    prefixo = vigia.split(":", 1)[0]
    if prefixo == "mtgo":
        return vigiar_mtgo(con, slug)
    if prefixo == "moxfield":
        return vigiar_moxfield(con, slug, pasta)
    return _falha("erro", f"não sei vigiar {vigia!r} (prefixo {prefixo!r}"
                          " desconhecido)")


def vigiar_todos(con: sqlite3.Connection, *, pasta: Path | None = None,
                 levantar: bool = False) -> dict[str, dict]:
    """Visita os decks que têm `vigia`, por ordem da página, e devolve
    `{slug: resultado}`. Grava `n_deck.vigia_ok_em` (e limpa o `vigia_erro`) se
    a leitura correu bem; `sem_lista_nova` só limpa o erro; numa falha grava o
    `vigia_erro` e deixa o `vigia_ok_em` como estava. Um deck que falha nunca
    impede os outros.

    Com `levantar=True`, depois de gravar tudo, levanta `VigiaFalhou` se algum
    deck acabou em `sem_lista`/`sem_ficheiro`/`erro` — é o que faz o passo do
    `daily` ficar vermelho sem perder o que correu bem.
    """
    resultados: dict[str, dict] = {}
    for d in modelo.decks(con):
        if not d["vigia"]:
            continue
        slug = d["slug"]
        try:
            r = _vigiar_um(con, slug, d["vigia"], pasta)
        except Exception as e:                    # um deck não derruba os outros
            if con.in_transaction:
                con.rollback()
            r = _falha("erro", f"falhou a ler a vigia: {type(e).__name__}: {e}")
        resultados[slug] = r
        with con:
            if r["estado"] in FALHAS:
                con.execute("UPDATE n_deck SET vigia_erro = ? WHERE slug = ?",
                            (r["mensagem"], slug))
            elif r["estado"] == "sem_lista_nova":
                # não leu nada de novo: o `vigia_ok_em` fica como estava (é a data
                # da última leitura a sério) e só se limpa o erro anterior
                con.execute("UPDATE n_deck SET vigia_erro = NULL WHERE slug = ?",
                            (slug,))
            else:
                con.execute("UPDATE n_deck SET vigia_ok_em = ?, vigia_erro = NULL"
                            " WHERE slug = ?", (_agora(), slug))
    falhas = {s: r for s, r in resultados.items() if r["estado"] in FALHAS}
    if levantar and falhas:
        raise VigiaFalhou(falhas)
    return resultados
