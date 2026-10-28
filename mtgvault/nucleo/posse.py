"""A posse do núcleo: que edição e acabamento contam, o que ele tem de cada
carta, o que falta, as partilhadas dos decks rotativos e o que trazer de que
caixa para montar um deck.

As regras (spec «Regras», 2026-10-28):

- **Uma carta é uma edição e um acabamento.** Só conta como «tenho» a edição
  escolhida, no acabamento escolhido. Sem escolha, vale a impressão `nonfoil`
  com o menor trend do Cardmarket (> 0); sem nenhuma com preço, a primeira do
  `scryfall.impressoes`.
- **Uma escolha por carta e por âmbito.** O âmbito é o deck (`slug`), ou
  `ROT` para as partilhadas dos rotativos (são as mesmas cópias físicas a
  andar de caixa em caixa, por isso a edição escolhe-se uma vez para todos).
  Mudar a escolha não apaga o que estava marcado: vai para `n_saida`
  (`trocou_edicao`), para ele decidir.
- **Sempre montados:** cada deck tem as suas cópias.
- **Rotativos:** uma carta (pelo nome) é partilhada se aparece na versão atual
  de dois ou mais decks rotativos; as partilhadas vivem num monte só (`ROT`) e
  cada deck precisa da quantidade que ELE pede (o monte tem de chegar ao
  máximo). Só um rotativo está montado de cada vez (`n_montado`).

Duas decisões que não estão escritas na spec e que valem a pena saber:

- **A primeira marcação FIXA a edição da omissão** (`ajustar` grava-a em
  `n_edicao`). A omissão depende do preço de hoje; sem isto, amanhã o trend
  de outra impressão descia, a omissão mudava, e as cópias que ele marcou
  ficavam numa edição que já não conta — sem passarem pelo `n_saida`, ou
  seja, a desaparecer em silêncio.
- **O mesmo nome no main e no side do mesmo deck é UM monte de posse**: o
  `tenho` reparte-o pelas linhas por esta ordem — comandante, main, side.

Só escreve nas tabelas `n_*`. As funções que escrevem (`escolher_edicao`,
`ajustar`, `definir_montado`) abrem e fecham a sua transação; o
`depois_de_versao` corre DENTRO da do `listas.gravar_versao` e nunca faz
commit.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from .. import scryfall

ROT = "rotativos"
ACABAMENTOS = ("nonfoil", "foil")
# a ordem por que o monte de posse de um nome se reparte pelas linhas do deck
_ORDEM_SECCAO = {"comandante": 0, "main": 1, "side": 2}


# ---------------------------------------------------------------------------
# Ajudantes
# ---------------------------------------------------------------------------
def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _deck(con: sqlite3.Connection, slug: str) -> dict:
    """A linha do `n_deck`, ou `ValueError` se o slug não for de um deck."""
    r = con.execute("SELECT slug, nome, formato, modo FROM n_deck"
                    " WHERE slug = ?", (slug,)).fetchone()
    if r is None:
        raise ValueError(f"deck desconhecido: {slug!r}")
    return {"slug": r[0], "nome": r[1], "formato": r[2], "modo": r[3]}


def _versao(con: sqlite3.Connection, slug: str) -> dict | None:
    # importado aqui: o `listas` importa este módulo no topo
    from . import listas                                    # noqa: PLC0415
    return listas.versao_atual(con, slug)


def _por_nome(linhas) -> dict[str, int]:
    """Quantidade total por nome, somando as secções, pela ordem de entrada."""
    soma: dict[str, int] = {}
    for l in linhas:
        soma[l.nome] = soma.get(l.nome, 0) + l.qtd
    return soma


def _nomes_rotativos(con: sqlite3.Connection,
                     substituir: tuple[str, set] | None = None
                     ) -> dict[str, set[str]]:
    """`slug → nomes da versão atual`, para cada deck rotativo.

    `substituir=(slug, nomes)` troca os nomes de um deck — é assim que o
    `depois_de_versao` pergunta como estava o mundo ANTES da versão nova, que
    a essa altura já está gravada.
    """
    mapa: dict[str, set[str]] = {}
    for (slug,) in con.execute(
            "SELECT slug FROM n_deck WHERE modo = 'rotativo' ORDER BY ordem"):
        v = _versao(con, slug)
        mapa[slug] = set(_por_nome(v["linhas"])) if v else set()
    if substituir is not None and substituir[0] in mapa:
        mapa[substituir[0]] = set(substituir[1])
    return mapa


def _partilhadas_de(mapa: dict[str, set[str]]) -> set[str]:
    conta: dict[str, int] = {}
    for nomes in mapa.values():
        for n in nomes:
            conta[n] = conta.get(n, 0) + 1
    return {n for n, c in conta.items() if c >= 2}


def _ambito_de(deck: dict, nome: str, partilhadas_: set[str]) -> str:
    if deck["modo"] == "rotativo" and nome in partilhadas_:
        return ROT
    return deck["slug"]


def _exige_nome(con: sqlite3.Connection, slug: str, nome: str) -> dict:
    """A versão atual do deck, ou `ValueError` se o nome não estiver nela."""
    v = _versao(con, slug)
    if v is None or nome not in {l.nome for l in v["linhas"]}:
        raise ValueError(f"{nome!r} não está na lista atual de {slug!r}")
    return v


def _trend_hoje(con: sqlite3.Connection, scryfall_id: str,
                acabamento: str) -> float | None:
    """O trend do Cardmarket de hoje para esta impressão e acabamento.

    Provisório: a Task 4 traz o `valor.preco`, e é lá que o preço do núcleo
    passa a viver. Um trend a 0 não é preço (é o Cardmarket sem vendas).
    """
    r = con.execute(
        "SELECT trend FROM price_latest WHERE scryfall_id = ?"
        " AND source = 'cardmarket' AND finish = ? AND trend > 0",
        (scryfall_id, acabamento)).fetchone()
    return float(r[0]) if r else None


def _finishes(row) -> list[str]:
    try:
        return list(json.loads(row["finishes"] or "[]"))
    except (TypeError, ValueError):
        return []


def _omissao(con: sqlite3.Connection, nome: str) -> tuple[str, str] | None:
    """A edição da omissão: a `nonfoil` com o menor trend > 0; sem nenhuma com
    preço, a primeira do `scryfall.impressoes` (no acabamento que ela tiver)."""
    imps = scryfall.impressoes(con, nome, limite=None)
    melhor = None
    for r in imps:
        if "nonfoil" not in _finishes(r):
            continue
        p = _trend_hoje(con, r["scryfall_id"], "nonfoil")
        # `<` estrito: no empate fica a que o `impressoes` pôs primeiro
        if p is not None and (melhor is None or p < melhor[0]):
            melhor = (p, r["scryfall_id"])
    if melhor is not None:
        return (melhor[1], "nonfoil")
    for r in imps:
        fins = _finishes(r)
        for acab in ACABAMENTOS:
            if acab in fins:
                return (r["scryfall_id"], acab)
    return None


def _escolha(con: sqlite3.Connection, ambito_: str,
             nome: str) -> tuple[str, str] | None:
    r = con.execute("SELECT scryfall_id, acabamento FROM n_edicao"
                    " WHERE ambito = ? AND nome = ?", (ambito_, nome)).fetchone()
    return (r[0], r[1]) if r else None


def _edicao_em(con, ambito_: str, nome: str) -> tuple[str, str] | None:
    return _escolha(con, ambito_, nome) or _omissao(con, nome)


def _posse_do_nome(con: sqlite3.Connection, ambito_: str,
                   nome: str) -> list[tuple[str, str, int]]:
    """As linhas de `n_posse` de um nome num âmbito (qualquer edição).

    A `n_posse` não guarda o nome — a impressão diz qual é —, por isso o nome
    vem do catálogo pelo `scryfall_id`.
    """
    return [(r[0], r[1], r[2]) for r in con.execute(
        "SELECT p.scryfall_id, p.acabamento, p.qtd FROM n_posse p"
        " JOIN cards c ON c.scryfall_id = p.scryfall_id"
        " WHERE p.ambito = ? AND c.name = ? AND p.qtd > 0"
        " ORDER BY p.scryfall_id, p.acabamento", (ambito_, nome))]


def _qtd(con, ambito_: str, ed: tuple[str, str] | None) -> int:
    if ed is None:
        return 0
    r = con.execute("SELECT qtd FROM n_posse WHERE ambito = ? AND scryfall_id = ?"
                    " AND acabamento = ?", (ambito_, ed[0], ed[1])).fetchone()
    return r[0] if r else 0


def _por_qtd(con, ambito_: str, sid: str, acab: str, qtd: int) -> None:
    if qtd > 0:
        con.execute(
            "INSERT INTO n_posse (ambito, scryfall_id, acabamento, qtd)"
            " VALUES (?,?,?,?) ON CONFLICT (ambito, scryfall_id, acabamento)"
            " DO UPDATE SET qtd = excluded.qtd", (ambito_, sid, acab, qtd))
    else:
        con.execute("DELETE FROM n_posse WHERE ambito = ? AND scryfall_id = ?"
                    " AND acabamento = ?", (ambito_, sid, acab))


def _para_saida(con, ambito_: str, nome: str, *, slug: str, motivo: str,
                versao_id: int | None, menos: tuple[str, str] | None = None
                ) -> None:
    """Passa para `n_saida` a posse de um nome num âmbito (menos a da edição
    `menos`, se for dada) e zera-a. As cópias marcadas nunca desaparecem: ou
    contam, ou estão no `n_saida` à espera de decisão."""
    agora = _agora()
    for sid, acab, qtd in _posse_do_nome(con, ambito_, nome):
        if menos is not None and (sid, acab) == menos:
            continue
        con.execute(
            "INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
            " acabamento, qtd, em) VALUES (?,?,?,?,?,?,?)",
            (slug, motivo, versao_id, sid, acab, qtd, agora))
        _por_qtd(con, ambito_, sid, acab, 0)


def _mover(con, nome: str, de: str, para: str) -> None:
    """Muda a posse e a escolha de edição de um nome de um âmbito para outro,
    somando ao que já lá houver. A escolha de quem leva as cópias ganha: é a
    edição em que elas estão marcadas."""
    for sid, acab, qtd in _posse_do_nome(con, de, nome):
        _por_qtd(con, para, sid, acab, _qtd(con, para, (sid, acab)) + qtd)
        _por_qtd(con, de, sid, acab, 0)
    e = _escolha(con, de, nome)
    if e is not None:
        con.execute("INSERT OR REPLACE INTO n_edicao (ambito, nome, scryfall_id,"
                    " acabamento) VALUES (?,?,?,?)", (para, nome, e[0], e[1]))
        con.execute("DELETE FROM n_edicao WHERE ambito = ? AND nome = ?",
                    (de, nome))


def _transacao(con: sqlite3.Connection):
    """A transação de uma escrita: `BEGIN IMMEDIATE` (se ninguém a abriu) e o
    `with con:` que faz commit ou rollback."""
    if not con.in_transaction:
        con.execute("BEGIN IMMEDIATE")
    return con


def _montado(con: sqlite3.Connection) -> str | None:
    r = con.execute("SELECT slug FROM n_montado WHERE id = 1").fetchone()
    return r[0] if r else None


# ---------------------------------------------------------------------------
# Partilhadas e âmbito
# ---------------------------------------------------------------------------
def partilhadas(con: sqlite3.Connection) -> set[str]:
    """Os nomes que estão na versão atual de dois ou mais decks rotativos
    (todas as secções contam)."""
    return _partilhadas_de(_nomes_rotativos(con))


def ambito(con: sqlite3.Connection, slug: str, nome: str) -> str:
    """`ROT` se o deck é rotativo e o nome é partilhado; senão o `slug`."""
    deck = _deck(con, slug)
    _exige_nome(con, slug, nome)
    return _ambito_de(deck, nome, partilhadas(con))


# ---------------------------------------------------------------------------
# Edição
# ---------------------------------------------------------------------------
def edicao(con: sqlite3.Connection, slug: str,
           nome: str) -> tuple[str, str] | None:
    """`(scryfall_id, acabamento)` que conta para esta carta neste deck: a
    escolha gravada no âmbito, ou a omissão. `None` se o nome não tiver
    impressões em papel."""
    return _edicao_em(con, ambito(con, slug, nome), nome)


def escolher_edicao(con: sqlite3.Connection, slug: str, nome: str,
                    scryfall_id: str, acabamento: str) -> None:
    """Grava a edição e o acabamento desta carta no âmbito dela.

    A impressão tem de ser desse nome, de papel, e ter esse acabamento no
    `finishes` (um foil que nunca existiu não se escolhe). A posse de qualquer
    outra edição no âmbito passa para `n_saida` (`trocou_edicao`) e zera.
    """
    amb = ambito(con, slug, nome)
    if acabamento not in ACABAMENTOS:
        raise ValueError(f"acabamento inválido: {acabamento!r} (nonfoil | foil)")
    r = con.execute("SELECT name, finishes, digital FROM cards"
                    " WHERE scryfall_id = ?", (scryfall_id,)).fetchone()
    if r is None or r["name"] != nome or r["digital"]:
        raise ValueError(f"{scryfall_id!r} não é uma impressão em papel de {nome!r}")
    if acabamento not in _finishes(r):
        raise ValueError(f"{nome!r} ({scryfall_id}) não existe em {acabamento}")
    v = _versao(con, slug)
    with _transacao(con):
        _para_saida(con, amb, nome, slug=slug, motivo="trocou_edicao",
                    versao_id=v["id"] if v else None,
                    menos=(scryfall_id, acabamento))
        con.execute("INSERT OR REPLACE INTO n_edicao (ambito, nome, scryfall_id,"
                    " acabamento) VALUES (?,?,?,?)",
                    (amb, nome, scryfall_id, acabamento))


# ---------------------------------------------------------------------------
# Marcar a posse
# ---------------------------------------------------------------------------
def ajustar(con: sqlite3.Connection, slug: str, nome: str, delta: int, *,
            request_id: str) -> int:
    """Soma `delta` à posse desta carta, na edição atual do âmbito, e devolve a
    quantidade nova.

    Idempotente por `request_id` (o mesmo pedido duas vezes — o telemóvel a
    repetir um toque — conta uma vez e devolve a quantidade de agora). Nunca
    abaixo de 0: o que passaria do zero é cortado, e o pedido fica registado
    na mesma. A primeira marcação fixa a edição da omissão (ver o topo).
    """
    if not request_id:
        raise ValueError("falta o request_id")
    amb = ambito(con, slug, nome)
    with _transacao(con):
        ed = _edicao_em(con, amb, nome)
        if ed is None:
            raise ValueError(f"{nome!r} não tem impressões em papel")
        if con.execute("SELECT 1 FROM n_posse_log WHERE request_id = ?",
                       (request_id,)).fetchone():
            return _qtd(con, amb, ed)
        if _escolha(con, amb, nome) is None:
            con.execute("INSERT INTO n_edicao (ambito, nome, scryfall_id,"
                        " acabamento) VALUES (?,?,?,?)", (amb, nome, *ed))
        antes = _qtd(con, amb, ed)
        nova = max(0, antes + int(delta))
        _por_qtd(con, amb, ed[0], ed[1], nova)
        # o delta registado é o que se aplicou (o corte no zero fica visível)
        con.execute("INSERT INTO n_posse_log (request_id, ambito, scryfall_id,"
                    " acabamento, delta, em) VALUES (?,?,?,?,?,?)",
                    (request_id, amb, ed[0], ed[1], nova - antes, _agora()))
    return nova


# ---------------------------------------------------------------------------
# Depois de uma versão nova
# ---------------------------------------------------------------------------
def depois_de_versao(con: sqlite3.Connection, slug: str, antes: list,
                     depois: list, versao_id: int, origem: str) -> None:
    """Chamado por `listas.gravar_versao` na MESMA transação que grava a versão
    (não abre nem fecha transação; se levantar, a versão não fica gravada).

    `antes` e `depois` são as listas (`Linha`) da versão anterior (vazia se for
    a primeira) e da nova.

    (a) Os nomes que saíram do deck com posse no âmbito DO DECK passam para
        `n_saida` (`saiu_da_lista`), venha a lista da vigia ou do André — é o
        mesmo caso, e as cópias marcadas nunca desaparecem. Baixar a
        quantidade não é sair: o que sobra fica marcado.
    (b) Num rotativo, cada nome que mudou de fixa para partilhada (ou ao
        contrário) muda de âmbito com a posse e a escolha de edição. Uma
        partilhada que este deck deixou de jogar não vai para o `n_saida` se
        outro rotativo ainda a joga: só muda de caixa.

    Um slug que não esteja em `n_deck` trata-se como um deck sempre montado (o
    `gravar_versao` aceita-o, e a posse dele é só dele).
    """
    r = con.execute("SELECT modo FROM n_deck WHERE slug = ?", (slug,)).fetchone()
    rotativo = r is not None and r[0] == "rotativo"
    nomes_antes, nomes_depois = set(_por_nome(antes)), set(_por_nome(depois))

    if rotativo:
        mapa_depois = _nomes_rotativos(con, substituir=(slug, nomes_depois))
        mapa_antes = dict(mapa_depois)
        mapa_antes[slug] = nomes_antes
        part_antes = _partilhadas_de(mapa_antes)
        part_depois = _partilhadas_de(mapa_depois)
    else:
        part_antes = part_depois = set()

    # (a)
    for nome in sorted(nomes_antes - nomes_depois):
        if nome in part_antes:
            continue                     # era do monte: trata-o o (b)
        _para_saida(con, slug, nome, slug=slug, motivo="saiu_da_lista",
                    versao_id=versao_id)

    if not rotativo:
        return
    # (b) só os nomes deste deck podem ter mudado de estado
    for nome in sorted(nomes_antes | nomes_depois):
        era, e = nome in part_antes, nome in part_depois
        if era == e:
            continue
        if e:
            # fixa → partilhada: vem da caixa do (único) deck que a tinha
            for outro, nomes in mapa_antes.items():
                if nome in nomes:
                    _mover(con, nome, outro, ROT)
        else:
            donos = [s for s, nomes in mapa_depois.items() if nome in nomes]
            if donos:
                # partilhada → fixa: o monte vai para a caixa de quem a joga
                _mover(con, nome, ROT, donos[0])
            else:
                _para_saida(con, ROT, nome, slug=slug, motivo="saiu_da_lista",
                            versao_id=versao_id)


# ---------------------------------------------------------------------------
# O estado de um deck
# ---------------------------------------------------------------------------
def estado_deck(con: sqlite3.Connection, slug: str) -> dict:
    """Carta a carta, o que o deck pede, que edição conta, o que ele tem e o
    que falta.

    `tenho = min(qtd, posse no âmbito)`; nos rotativos as partilhadas usam a
    posse de `ROT` e cada deck pede a SUA quantidade. O mesmo nome em várias
    secções reparte um monte só (comandante, main, side). `custo_falta` soma
    só o que tem preço; `sem_preco` conta as cartas (linhas) em falta sem
    preço — um total sem preço não é zero euros, é um mínimo.
    """
    deck = _deck(con, slug)
    v = _versao(con, slug)
    rotativo = deck["modo"] == "rotativo"
    montado = _montado(con)
    nome_montado = None
    if montado:
        r = con.execute("SELECT nome FROM n_deck WHERE slug = ?",
                        (montado,)).fetchone()
        nome_montado = r[0] if r else montado
    part = partilhadas(con) if rotativo else set()
    linhas = list(v["linhas"]) if v else []

    edicoes: dict[str, tuple[str, str] | None] = {}
    monte: dict[str, int] = {}
    tenho_por: dict[int, int] = {}
    for i in sorted(range(len(linhas)),
                    key=lambda i: (_ORDEM_SECCAO.get(linhas[i].seccao, 9), i)):
        l = linhas[i]
        amb = _ambito_de(deck, l.nome, part)
        if l.nome not in edicoes:
            edicoes[l.nome] = _edicao_em(con, amb, l.nome)
            monte[l.nome] = _qtd(con, amb, edicoes[l.nome])
        tenho_por[i] = min(l.qtd, monte[l.nome])
        monte[l.nome] -= tenho_por[i]

    cartas = []
    for i, l in enumerate(linhas):
        ed = edicoes[l.nome]
        partilhada = rotativo and l.nome in part
        if partilhada:
            onde = None if montado is None else (
                "aqui" if montado == slug else nome_montado)
        else:
            onde = None
        cartas.append({
            "nome": l.nome, "seccao": l.seccao, "qtd": l.qtd,
            "scryfall_id": ed[0] if ed else None,
            "acabamento": ed[1] if ed else None,
            "tenho": tenho_por[i], "falta": l.qtd - tenho_por[i],
            "grupo": ("partilhada" if partilhada else "fixa") if rotativo
            else None,
            "onde": onde,
            "preco_un": _trend_hoje(con, ed[0], ed[1]) if ed else None,
        })
    custo = sum(c["falta"] * c["preco_un"] for c in cartas
                if c["falta"] and c["preco_un"] is not None)
    return {
        "slug": slug, "nome": deck["nome"], "formato": deck["formato"],
        "modo": deck["modo"],
        "versao": ({k: v[k] for k in ("id", "numero", "criada_em", "fonte",
                                      "origem")} if v else None),
        "cartas": cartas,
        "total": sum(c["qtd"] for c in cartas),
        "tenho": sum(c["tenho"] for c in cartas),
        "custo_falta": round(custo, 2),
        "sem_preco": sum(1 for c in cartas
                         if c["falta"] and c["preco_un"] is None),
        "montado": True if not rotativo else montado == slug,
    }


# ---------------------------------------------------------------------------
# Montar um rotativo
# ---------------------------------------------------------------------------
def movimentos_para(con: sqlite3.Connection, slug: str) -> list[dict]:
    """O que trazer de que caixa para montar este rotativo, sem gravar nada.

    O monte das partilhadas anda com o deck montado: cada partilhada que este
    deck usa vem da caixa do montado antes, na quantidade que este pede (até
    ao que há no monte). Nada montado antes, ou este já montado: nada a mover.
    """
    deck = _deck(con, slug)
    if deck["modo"] != "rotativo":
        raise ValueError(f"{slug!r} fica sempre montado: não se monta")
    antes = _montado(con)
    if antes is None or antes == slug:
        return []
    v = _versao(con, slug)
    if v is None:
        return []
    part = partilhadas(con)
    movs = []
    for nome, qtd in _por_nome(v["linhas"]).items():
        if nome not in part:
            continue
        n = min(qtd, _qtd(con, ROT, _edicao_em(con, ROT, nome)))
        if n > 0:
            movs.append({"nome": nome, "qtd": n, "de": antes, "para": slug})
    return movs


def definir_montado(con: sqlite3.Connection, slug: str) -> list[dict]:
    """Monta este rotativo (grava `n_montado`) e devolve os movimentos."""
    movs = movimentos_para(con, slug)
    with _transacao(con):
        con.execute("INSERT OR REPLACE INTO n_montado (id, slug) VALUES (1, ?)",
                    (slug,))
    return movs
