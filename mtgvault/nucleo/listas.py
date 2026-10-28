"""As listas do núcleo: colar texto, resolver os nomes no catálogo e gravar uma
versão com a sua fonte e o que mudou.

Uma versão é uma lista inteira (`n_versao` + `n_versao_carta`), nunca um
remendo da anterior: ver o que mudou é comparar duas versões (`diferenca`). A
`fonte` é obrigatória — *de onde veio esta lista?* é a pergunta a que uma versão
sem resposta deixa de poder responder daqui a um mês — e a `origem` diz quem a
trouxe: ele (`andre`) ou a vigia (`vigia`).

Só escreve nas tabelas `n_*`. Os nomes validam-se contra o `cards` do catálogo
(a ligação tem de ter o `catalog` anexado, como a de `db.session`): um nome que
o catálogo não conheça nunca é gravado, é devolvido junto com os outros em
`NomesDesconhecidos`, para ele corrigir a gralha de uma vez.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from typing import NamedTuple

from .. import scryfall
from . import posse

SECCOES = ("comandante", "main", "side")
ORIGENS = ("andre", "vigia")


class Linha(NamedTuple):
    seccao: str   # 'main' | 'side' | 'comandante'
    nome: str
    qtd: int


class NomesDesconhecidos(ValueError):
    """Nomes que o catálogo não conhece, por ordem de entrada e como foram
    escritos. Levanta-se **antes** de gravar fosse o que fosse."""

    def __init__(self, nomes: list[str]):
        self.nomes = list(nomes)
        super().__init__("o catálogo não conhece: " + "; ".join(self.nomes))


# ---------------------------------------------------------------------------
# Ler o texto colado
# ---------------------------------------------------------------------------
# Cabeçalhos que se vêem nas exportações (Moxfield, MTGO, Arena) e à mão.
# `None` = ignora a secção inteira (o maybeboard não é do deck).
_CABECALHOS = {
    "commander": "comandante", "comandante": "comandante",
    "companion": "side",
    "sideboard": "side", "side": "side",
    "deck": "main", "main": "main", "mainboard": "main",
    "maybeboard": None, "maybe": None,
}
_CABECALHO = re.compile(r"^([A-Za-zçÇ]+)\s*(?:\(\d+\))?\s*:?$")
_LINHA = re.compile(r"^(?:(\d+)x?\s+)?(.+)$", re.IGNORECASE)
_SB = re.compile(r"^SB:\s*", re.IGNORECASE)
_MARCADOR = re.compile(r"\s+\*[A-Za-z]\*$")
# «(CMR) 89», «(ALL) 54a», «(UNF)»: edição entre parênteses (2–6 letras ou
# dígitos, sem espaços — «Erase (Not the Urza's Saga One)» é um nome a sério) e
# o número de colecionador opcional.
_EDICAO = re.compile(r"\s+\([A-Za-z0-9]{2,6}\)(?:\s+\S+)?$")

_IGNORAR = object()


def _limpar_nome(nome: str) -> str:
    nome = nome.strip()
    while True:
        novo = _MARCADOR.sub("", nome)
        novo = _EDICAO.sub("", novo)
        if novo == nome:
            return nome
        nome = novo.strip()


def _juntar(linhas: list[Linha]) -> list[Linha]:
    """Soma as quantidades repetidas por (secção, nome), pela ordem em que cada
    uma apareceu. Nunca devolve duas linhas para a mesma carta na mesma secção:
    a tabela `n_versao_carta` não tem unicidade, é daqui que ela vem."""
    soma: dict[tuple[str, str], int] = {}
    for l in linhas:
        k = (l.seccao, l.nome)
        soma[k] = soma.get(k, 0) + l.qtd
    return [Linha(s, n, q) for (s, n), q in soma.items()]


def ler_texto(texto: str) -> list[Linha]:
    """O texto colado → linhas `(secção, nome, qtd)`.

    Aceita `4 Nome`, `4x Nome`, `SB: 2 Nome`, o export do Moxfield
    (`1 Nome (SET) 123 *F*`) e os cabeçalhos `Commander`/`Comandante`,
    `Companion` e `Sideboard` (vão para o side), `Deck`/`Main`/`Mainboard`; o
    `Maybeboard` ignora-se. Sem cabeçalho de sideboard, a primeira linha vazia
    depois das cartas do main abre o sideboard. Linhas que começam por `//` são
    comentários. Repetidos somam-se.
    """
    seccao = "main"
    vistas_no_main = False
    linhas: list[Linha] = []
    for bruta in (texto or "").splitlines():
        t = bruta.strip()
        if not t:
            if seccao == "main" and vistas_no_main:
                seccao = "side"
            elif seccao == "comandante":
                seccao = "main"
            continue
        if t.startswith("//"):
            continue
        m = _CABECALHO.match(t)
        if m and m.group(1).lower() in _CABECALHOS:
            destino = _CABECALHOS[m.group(1).lower()]
            seccao = _IGNORAR if destino is None else destino
            vistas_no_main = False
            continue
        if seccao is _IGNORAR:
            continue
        esta = seccao
        if _SB.match(t):
            t = _SB.sub("", t)
            esta = "side"
        m = _LINHA.match(t)
        qtd = int(m.group(1)) if m.group(1) else 1
        nome = re.sub(r"\s+", " ", _limpar_nome(m.group(2)))
        if not nome or qtd <= 0:
            continue
        if seccao == "main" and esta == "main":
            vistas_no_main = True
        linhas.append(Linha(esta, nome, qtd))
    return _juntar(linhas)


# ---------------------------------------------------------------------------
# Resolver os nomes no catálogo
# ---------------------------------------------------------------------------
def _escapar_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _resolver(con: sqlite3.Connection, nome: str) -> str | None:
    """O `name` do catálogo para um nome escrito, ou `None`.

    Só papel (`digital = 0`). Primeiro o que vai pelo índice — nome exato, e a
    frente de uma carta de duas faces (`Delver of Secrets` → `Delver of Secrets
    // Insectile Aberration`), também com o separador escrito à Moxfield
    (`Fire/Ice`) —, e só se nada casar a varredura sem caixa. A maioria dos
    nomes de uma lista sai à primeira.
    """
    for arg in dict.fromkeys((nome, scryfall.canonizar(nome))):
        r = con.execute("SELECT name FROM cards WHERE name = ? AND digital = 0"
                        " LIMIT 1", (arg,)).fetchone()
        if r:
            return r[0]
        r = con.execute(
            f"SELECT name FROM cards WHERE {scryfall.frente_de_dupla_face()}"
            " AND digital = 0 LIMIT 1",
            scryfall.limites_dupla_face(arg)).fetchone()
        if r:
            return r[0]
    for arg in dict.fromkeys((nome, scryfall.canonizar(nome))):
        # sem caixa: o nome inteiro ganha à frente (ORDER BY ... DESC)
        r = con.execute(
            "SELECT name FROM cards WHERE digital = 0 AND ("
            " name = ?1 COLLATE NOCASE OR name LIKE ?2 ESCAPE '\\')"
            " ORDER BY (name = ?1 COLLATE NOCASE) DESC, name LIMIT 1",
            (arg, _escapar_like(arg) + " // %")).fetchone()
        if r:
            return r[0]
    return None


def normalizar(con: sqlite3.Connection, linhas: list[Linha]) -> list[Linha]:
    """As linhas com o nome do catálogo, repetidos juntos.

    Levanta `NomesDesconhecidos` com TODOS os nomes que não resolveram (por
    ordem, como foram escritos, sem repetir); nesse caso não devolve nada.
    """
    resolvidos: dict[str, str | None] = {}
    desconhecidos: list[str] = []
    for l in linhas:
        if l.nome not in resolvidos:
            resolvidos[l.nome] = _resolver(con, l.nome)
            if resolvidos[l.nome] is None:
                desconhecidos.append(l.nome)
    if desconhecidos:
        raise NomesDesconhecidos(desconhecidos)
    return _juntar([Linha(l.seccao, resolvidos[l.nome], l.qtd) for l in linhas])


# ---------------------------------------------------------------------------
# Versões
# ---------------------------------------------------------------------------
def versao_atual(con: sqlite3.Connection, slug: str) -> dict | None:
    """A versão de maior número do deck, ou `None` se ainda não tem nenhuma."""
    v = con.execute(
        "SELECT id, numero, criada_em, fonte, origem FROM n_versao"
        " WHERE slug = ? ORDER BY numero DESC LIMIT 1", (slug,)).fetchone()
    if v is None:
        return None
    cartas = con.execute(
        "SELECT seccao, nome, qtd FROM n_versao_carta WHERE versao_id = ?"
        " ORDER BY rowid", (v[0],)).fetchall()
    return {"id": v[0], "numero": v[1], "criada_em": v[2], "fonte": v[3],
            "origem": v[4], "linhas": [Linha(*c) for c in cartas]}


def _por_nome(linhas: list[Linha]) -> dict[str, int]:
    soma: dict[str, int] = {}
    for l in linhas:
        soma[l.nome] = soma.get(l.nome, 0) + l.qtd
    return soma


def diferenca(antes: list[Linha], depois: list[Linha]) -> dict:
    """O que entrou e o que saiu, por nome e somando as secções (mudar uma
    carta do main para o side não é entrar nem sair). Cada lista sai por ordem
    alfabética, com a quantidade da diferença."""
    a, d = _por_nome(antes), _por_nome(depois)
    def ordem(nome):
        return (nome.lower(), nome)
    return {
        "entrou": [(n, d[n] - a.get(n, 0)) for n in sorted(d, key=ordem)
                   if d[n] > a.get(n, 0)],
        "saiu": [(n, a[n] - d.get(n, 0)) for n in sorted(a, key=ordem)
                 if a[n] > d.get(n, 0)],
    }


def _mesma_lista(x: list[Linha], y: list[Linha]) -> bool:
    return sorted(x) == sorted(y)


def gravar_versao(con: sqlite3.Connection, slug: str, linhas: list[Linha], *,
                  fonte: str, origem: str,
                  quando: str | None = None) -> dict | None:
    """Grava `linhas` como a versão seguinte do deck.

    Normaliza os nomes (e levanta `NomesDesconhecidos` sem gravar nada), e se a
    lista for igual à atual — mesmas cartas nas mesmas secções, pela ordem que
    for — devolve `None`: colar duas vezes a mesma lista não cria versão. Senão
    grava `numero + 1` e devolve `{versao_id, numero, entrou, saiu}`.

    A versão, as cartas e o `posse.depois_de_versao` vão numa só transação: se
    a posse falhar, não fica nada.
    """
    if not (fonte or "").strip():
        raise ValueError("de onde veio a lista?")
    if origem not in ORIGENS:
        raise ValueError(f"origem inválida: {origem!r} (andre | vigia)")
    depois = normalizar(con, linhas)
    if not depois:
        raise ValueError("a lista está vazia")
    criada = quando or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # BEGIN IMMEDIATE antes de ler a versão atual: dois escritores a gravar o
    # mesmo deck não podem ficar os dois com o mesmo `numero + 1`.
    if not con.in_transaction:
        con.execute("BEGIN IMMEDIATE")
    with con:
        atual = versao_atual(con, slug)
        antes = atual["linhas"] if atual else []
        if atual and _mesma_lista(antes, depois):
            return None
        numero = atual["numero"] + 1 if atual else 1
        cur = con.execute(
            "INSERT INTO n_versao (slug, numero, criada_em, fonte, origem)"
            " VALUES (?,?,?,?,?)",
            (slug, numero, criada, fonte.strip(), origem))
        versao_id = cur.lastrowid
        con.executemany(
            "INSERT INTO n_versao_carta (versao_id, seccao, nome, qtd)"
            " VALUES (?,?,?,?)",
            [(versao_id, l.seccao, l.nome, l.qtd) for l in depois])
        posse.depois_de_versao(con, slug, antes, depois, versao_id, origem)
    return {"versao_id": versao_id, "numero": numero,
            **diferenca(antes, depois)}
