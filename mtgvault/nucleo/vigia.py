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
  como estava — é ele que deixa a página dizer «desde dia X». No Moxfield o
  `vigia_ok_em` é o `lido_em` do ficheiro (quando a lista foi LIDA no Chrome),
  não a hora a que o daily a viu (I2, 2026-10-29);
- o `vigia_erro` vai para o site publicado: **nunca leva um caminho do PC**
  (M1). O caminho, quando ajuda, vai no `detalhe`, que só chega ao log;
- só escreve nas tabelas `n_*`. As `decklists` só se leem.

Os AVISOS, que não são falhas (não pintam o daily de vermelho; põem o
`vigia_erro`, para a página dizer «não consegui ver a lista desde X», e deixam
a versão e o `vigia_ok_em` como estavam):
- `erro_fonte` (R17): o Moxfield falhou hoje ({"erro"}) num deck que JÁ TEM
  versão, ou o ficheiro mais recente tem mais de 2 dias. Quem fica vermelho é
  a tarefa `mtg-moxfield-chrome` do ai-pc: uma causa, um vermelho. Um deck que
  nunca teve versão falha na mesma — sem lista nenhuma não há nada a mostrar;
- `lista_suspeita` (R19): a guarda de antes de gravar (`_guarda`) — um deck de
  comandante tem 100 cartas, um de 60 tem main >= 60 e side <= 15 e, havendo
  versão, a lista lida tem de ter pelo menos 60 % dos nomes dela. Uma lista
  cortada ou de outro deck não entra; se for uma mudança grande a sério, ele
  cola-a à mão.

O MTGO E O LUFFY (M6): as listas do Pauper vêm da recolha do mtgvault de
sempre, que no Pauper só guarda os jogadores vigiados — a tabela ANTIGA
`watched` e o `colecao_config.json → so_jogadores_vigiados`. É por ela que as
listas do LuffyDoChapeuDePalha chegam às `decklists`: as linhas dele nessa
tabela e nesse config têm de ficar, mesmo que o resto do site antigo saia.

Formato do ficheiro do Moxfield, `data/moxfield/AAAA-MM-DD.json`:
`{"lido_em": iso, "decks": {"<id>": {"texto": "<export>", "titulo": str}
| {"erro": str}}}`.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime
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
# (I2/I3, 2026-10-29) avisos: põem o `vigia_erro` e mais nada (ver o topo)
AVISOS = ("erro_fonte", "lista_suspeita")

# Um ficheiro do Moxfield com mais dias do que isto já não é «a lista de hoje»
DIAS_FICHEIRO_VELHO = 2
# (R19) a guarda da lista lida
FORMATOS_COMANDANTE = ("cedh", "duel-commander")
CARTAS_COMANDANTE = 100
MIN_MAIN = 60
MAX_SIDE = 15
MIN_NOMES_EM_COMUM = 0.6


class VigiaFalhou(RuntimeError):
    """Pelo menos uma vigia falhou. `falhas` = {slug: resultado} das que falharam
    (as que correram bem já ficaram gravadas quando isto se levanta)."""

    def __init__(self, falhas: dict[str, dict]):
        self.falhas = dict(falhas)
        # o `detalhe` (um caminho, por exemplo) vai para o log, nunca para o site
        partes = [f"{slug}: {r.get('mensagem', r.get('estado'))}"
                  + (f" [{r['detalhe']}]" if r.get("detalhe") else "")
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


def _falha(estado: str, mensagem: str, detalhe: str | None = None) -> dict:
    r = {"estado": estado, "mensagem": mensagem}
    if detalhe:
        r["detalhe"] = detalhe
    return r


def _hoje() -> date:
    """O dia de hoje (os testes trocam-no, para um ficheiro de teste não
    envelhecer com o calendário)."""
    return date.today()


def _guarda(con: sqlite3.Connection, slug: str, linhas: list[Linha]) -> str | None:
    """(R19, 2026-10-29) O que está mal numa lista lida pela vigia, ou `None`.

    As `linhas` já vêm com os nomes do catálogo (`listas.normalizar`). Um deck
    de comandante (cEDH, Duel Commander) tem 100 cartas no comandante e no main
    (o side não conta: no Moxfield é uma lista à parte); os outros têm main >=
    60 e side <= 15. Com versão atual, pelo menos 60 % dos nomes dela têm de
    estar na lista lida — abaixo disso é outro deck (uma lista trocada no
    Moxfield, outro jogador com o mesmo nome no MTGO).
    """
    r = con.execute("SELECT formato FROM n_deck WHERE slug = ?", (slug,)).fetchone()
    formato = r[0] if r else None
    por = {"comandante": 0, "main": 0, "side": 0}
    for l in linhas:
        por[l.seccao] = por.get(l.seccao, 0) + l.qtd
    if formato in FORMATOS_COMANDANTE:
        n = por["comandante"] + por["main"]
        if n != CARTAS_COMANDANTE:
            return (f"{n} cartas no comandante e no main; um deck de comandante"
                    f" tem {CARTAS_COMANDANTE}")
    else:
        main = por["main"] + por["comandante"]
        if main < MIN_MAIN:
            return f"main com {main} cartas, menos de {MIN_MAIN}"
        if por["side"] > MAX_SIDE:
            return f"side com {por['side']} cartas, mais de {MAX_SIDE}"
    atual = listas.versao_atual(con, slug)
    if atual:
        antes = {l.nome for l in atual["linhas"]}
        comuns = len(antes & {l.nome for l in linhas})
        if antes and comuns / len(antes) < MIN_NOMES_EM_COMUM:
            return (f"só {round(100 * comuns / len(antes))} % dos nomes da"
                    f" v{atual['numero']}")
    return None


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
        # os nomes primeiro: um nome desconhecido é uma FALHA (vermelha), e a
        # guarda compara os nomes do catálogo com os da versão atual
        linhas = listas.normalizar(con, linhas)
        mal = _guarda(con, slug, linhas) if linhas else None
        if mal:
            return _falha("lista_suspeita", "a lista lida parece outro deck ou"
                                            f" está incompleta ({mal})")
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

    `{"estado": "nova" | "igual" | "sem_ficheiro" | "erro" | "erro_fonte" |
    "lista_suspeita", ...}`; numa leitura boa, `ok_em` é o `lido_em` do
    ficheiro.
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
        # (M1) a pasta é um caminho do PC: fica no `detalhe` (o log), nunca na
        # mensagem, que vai para o site publicado
        return _falha("sem_ficheiro", "ainda não há ficheiro do Moxfield",
                      detalhe=f"pasta {pasta}")
    dia = _FICHEIRO.match(ficheiro.name).group(1)
    tem_versao = listas.versao_atual(con, slug) is not None
    try:
        idade = (_hoje() - date.fromisoformat(dia)).days
    except ValueError:
        idade = 0
    if idade > DIAS_FICHEIRO_VELHO:
        # (I2) a tarefa do Chrome não escreveu nos últimos dias — ela é que
        # fica vermelha; aqui fica a versão de antes e o aviso
        a, m, d = dia.split("-")
        return _falha("erro_fonte", f"o último ficheiro do Moxfield é de {d}/{m}/{a}")
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
        # (R17) com versão é um aviso: fica a lista de antes e a página diz
        # desde quando; sem versão nenhuma é uma falha
        return _falha("erro_fonte" if tem_versao else "erro",
                      f"o Moxfield falhou a {dia}: {entrada['erro']}")
    texto = entrada.get("texto")
    if not isinstance(texto, str) or not texto.strip():
        return _falha("erro", f"o ficheiro de {dia} traz este deck sem lista")

    lido = dados.get("lido_em")
    lido_ok = isinstance(lido, str) and _DATA.match(lido)
    data_lida = lido[:10] if lido_ok else dia
    fonte = f"Moxfield · https://moxfield.com/decks/{id_deck} · lido a {data_lida}"
    r = _gravar(con, slug, lambda: listas.ler_texto(texto), fonte)
    if r["estado"] in ("nova", "igual"):
        # (I2) a lista é de quando foi lida, não de quando o daily a viu
        r["ok_em"] = lido[:19] if lido_ok else f"{dia}T00:00:00"
    return r


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
    `daily` ficar vermelho sem perder o que correu bem. Os AVISOS
    (`erro_fonte`, `lista_suspeita`) gravam o `vigia_erro` e não levantam.
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
            if r["estado"] in FALHAS or r["estado"] in AVISOS:
                con.execute("UPDATE n_deck SET vigia_erro = ? WHERE slug = ?",
                            (r["mensagem"], slug))
            elif r["estado"] == "sem_lista_nova":
                # não leu nada de novo: o `vigia_ok_em` fica como estava (é a data
                # da última leitura a sério) e só se limpa o erro anterior
                con.execute("UPDATE n_deck SET vigia_erro = NULL WHERE slug = ?",
                            (slug,))
            else:
                con.execute("UPDATE n_deck SET vigia_ok_em = ?, vigia_erro = NULL"
                            " WHERE slug = ?", (r.get("ok_em") or _agora(), slug))
    falhas = {s: r for s, r in resultados.items() if r["estado"] in FALHAS}
    if levantar and falhas:
        raise VigiaFalhou(falhas)
    return resultados
