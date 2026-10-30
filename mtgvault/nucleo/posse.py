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
  máximo). Só um rotativo está montado de cada vez (`n_montado`), e o monte
  inteiro está na caixa dele: montar outro é trazer o monte todo.
- **Baixar a quantidade numa lista é uma saída parcial:** o que fica marcado
  acima do que é preciso vai para `n_saida` (`saiu_da_lista`).
- **As coleções emprestam aos decks de Standard, Pioneer, Modern e Legacy**
  (André, 30/10/2026: *«os únicos decks que podem usar cartas da coleção»*;
  `FORMATOS_COM_COLECAO`). O deck usa primeiro as cópias dele, e só o que
  faltar vem de uma coleção — qualquer edição e acabamento, mas só em inglês
  (as Shocks em português ficam sempre na coleção). É um EMPRÉSTIMO: o `tenho`
  da coleção, a meta e o valor não mexem, e nada se escreve. Como só um
  rotativo está montado de cada vez, dois decks podem contar com a mesma cópia
  emprestada (é a regra do máximo das partilhadas).

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
# os formatos cujos decks podem usar cartas das coleções (André, 30/10/2026)
FORMATOS_COM_COLECAO = frozenset({"standard", "pioneer", "modern", "legacy"})
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


def _fotos():
    # importado aqui: o `fotos` importa este módulo no topo
    from . import fotos                                     # noqa: PLC0415
    return fotos


def _por_nome(linhas) -> dict[str, int]:
    """Quantidade total por nome, somando as secções, pela ordem de entrada."""
    soma: dict[str, int] = {}
    for l in linhas:
        soma[l.nome] = soma.get(l.nome, 0) + l.qtd
    return soma


def _nomes_rotativos(con: sqlite3.Connection,
                     substituir: tuple[str, dict] | None = None
                     ) -> dict[str, dict[str, int]]:
    """`slug → {nome: qtd}` da versão atual, para cada deck rotativo (a qtd
    soma as secções).

    `substituir=(slug, {nome: qtd})` troca a lista de um deck — é assim que o
    `depois_de_versao` pergunta como estava o mundo ANTES da versão nova, que
    a essa altura já está gravada.
    """
    mapa: dict[str, dict[str, int]] = {}
    for (slug,) in con.execute(
            "SELECT slug FROM n_deck WHERE modo = 'rotativo' ORDER BY ordem"):
        v = _versao(con, slug)
        mapa[slug] = _por_nome(v["linhas"]) if v else {}
    if substituir is not None and substituir[0] in mapa:
        mapa[substituir[0]] = dict(substituir[1])
    return mapa


def _partilhadas_de(mapa: dict[str, dict[str, int]]) -> set[str]:
    conta: dict[str, int] = {}
    for nomes in mapa.values():
        for n in nomes:
            conta[n] = conta.get(n, 0) + 1
    return {n for n, c in conta.items() if c >= 2}


def _ambito_de(deck: dict, nome: str, partilhadas_: set[str]) -> str:
    if deck["modo"] == "rotativo" and nome in partilhadas_:
        return ROT
    return deck["slug"]


def _emprestaveis(con: sqlite3.Connection, nome: str) -> list[dict]:
    """As cópias deste nome que as coleções podem emprestar — só em inglês, de
    qualquer edição e acabamento —, pela ordem das coleções. Cada fonte leva as
    `livres` e as `validadas` (nunca mais do que as livres), que o
    `_pedir_emprestado` vai gastando."""
    fontes = []
    for r in con.execute(
            "SELECT cc.colecao, c.nome, c.ordem, cc.scryfall_id, cc.acabamento,"
            " cc.tenho FROM n_colecao_carta cc JOIN n_colecao c"
            " ON c.slug = cc.colecao WHERE cc.nome = ? AND cc.lingua = 'en'"
            " AND cc.tenho > 0 ORDER BY c.ordem, cc.id", (nome,)):
        fontes.append({
            "colecao": r[0], "colecao_nome": r[1], "ordem": r[2],
            "scryfall_id": r[3], "acabamento": r[4], "livres": r[5],
            "validadas": min(r[5], _fotos().validadas(con, r[0], r[3], r[4]))})
    return fontes


def _pedir_emprestado(fontes: list[dict], n: int) -> list[dict]:
    """Tira até `n` cópias das `fontes`, por ordem, e devolve o que tirou de
    cada uma (`qtd` e quantas dessas estão `validadas`). Gasta as fontes: o
    mesmo nome em main e side não empresta duas vezes a mesma cópia."""
    tirado = []
    for f in fontes:
        if n <= 0:
            break
        q = min(n, f["livres"])
        if q <= 0:
            continue
        v = min(q, f["validadas"])
        f["livres"] -= q
        f["validadas"] -= v
        n -= q
        tirado.append({**{k: f[k] for k in ("colecao", "colecao_nome", "ordem",
                                            "scryfall_id", "acabamento")},
                       "qtd": q, "validadas": v})
    return tirado


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
    """Grava a posse de uma impressão num âmbito (0 apaga a linha) e apara as
    fotos validadas à posse nova.

    É o único sítio que escreve na `n_posse`, por isso é aqui que se guarda a
    regra «as validadas nunca passam a posse»: o −1, a troca de edição, a saída
    de uma lista (`saiu_da_lista`), a saída parcial e a mudança de âmbito
    passam todos por cá. Subir não desfaz nada (as validadas já cabiam).
    """
    if qtd > 0:
        con.execute(
            "INSERT INTO n_posse (ambito, scryfall_id, acabamento, qtd)"
            " VALUES (?,?,?,?) ON CONFLICT (ambito, scryfall_id, acabamento)"
            " DO UPDATE SET qtd = excluded.qtd", (ambito_, sid, acab, qtd))
    else:
        con.execute("DELETE FROM n_posse WHERE ambito = ? AND scryfall_id = ?"
                    " AND acabamento = ?", (ambito_, sid, acab))
    _fotos().aparar_validadas(con, ambito_, sid, acab, "en", max(0, qtd))


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


def _aparar(con, ambito_: str, nome: str, precisa: int, *, slug: str,
            versao_id: int | None) -> None:
    """Passa para `n_saida` (`saiu_da_lista`) a posse de um nome num âmbito
    que fica ACIMA do que é preciso — baixar a quantidade numa lista é uma
    saída parcial. As cópias de outra edição (que não contam) saem primeiro."""
    linhas = _posse_do_nome(con, ambito_, nome)
    a_mais = sum(q for _s, _a, q in linhas) - max(0, precisa)
    if a_mais <= 0:
        return
    escolha = _escolha(con, ambito_, nome)
    linhas.sort(key=lambda l: (l[0], l[1]) == escolha)
    agora = _agora()
    for sid, acab, qtd in linhas:
        if a_mais <= 0:
            break
        sai = min(a_mais, qtd)
        con.execute(
            "INSERT INTO n_saida (slug, motivo, versao_id, scryfall_id,"
            " acabamento, qtd, em) VALUES (?,?,?,?,?,?,?)",
            (slug, "saiu_da_lista", versao_id, sid, acab, sai, agora))
        _por_qtd(con, ambito_, sid, acab, qtd - sai)
        a_mais -= sai


def _mover(con, nome: str, de: str, para: str, *, slug: str,
           versao_id: int | None) -> None:
    """Muda a posse e a escolha de edição de um nome de um âmbito para outro,
    somando ao que já lá houver. A escolha de quem leva as cópias ganha: é a
    edição em que elas estão marcadas. Se o destino já tinha OUTRA escolha com
    cópias, essas cópias vão para `n_saida` (`trocou_edicao`) antes — um
    âmbito tem uma edição só, e as cópias nunca desaparecem."""
    e = _escolha(con, de, nome)
    if e is not None:
        alvo = _escolha(con, para, nome)
        if alvo is not None and alvo != e:
            _para_saida(con, para, nome, slug=slug, motivo="trocou_edicao",
                        versao_id=versao_id, menos=e)
    for sid, acab, qtd in _posse_do_nome(con, de, nome):
        # as validadas vão com as cópias (são as mesmas cartas a mudar de
        # caixa) ANTES de se escrever a posse: o `_por_qtd` apara-as já no
        # destino, à posse nova, e a origem a zero não tem nada a desfazer
        con.execute("UPDATE n_validacao SET ambito = ? WHERE ambito = ? AND"
                    " scryfall_id = ? AND acabamento = ? AND desfeita_em IS NULL",
                    (para, de, sid, acab))
        _por_qtd(con, para, sid, acab, _qtd(con, para, (sid, acab)) + qtd)
        _por_qtd(con, de, sid, acab, 0)
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

    O âmbito resolve-se DEPOIS do `BEGIN IMMEDIATE`: uma versão gravada entre
    a pergunta e a escrita podia mudar a carta de fixa para partilhada, e a
    escolha ia para o âmbito errado.
    """
    if acabamento not in ACABAMENTOS:
        raise ValueError(f"acabamento inválido: {acabamento!r} (nonfoil | foil)")
    with _transacao(con):
        amb = ambito(con, slug, nome)
        r = con.execute("SELECT name, finishes, digital FROM cards"
                        " WHERE scryfall_id = ?", (scryfall_id,)).fetchone()
        if r is None or r["name"] != nome or r["digital"]:
            raise ValueError(
                f"{scryfall_id!r} não é uma impressão em papel de {nome!r}")
        if acabamento not in _finishes(r):
            raise ValueError(f"{nome!r} ({scryfall_id}) não existe em {acabamento}")
        v = _versao(con, slug)
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
    na mesma. A primeira marcação fixa a edição da omissão (ver o topo). O
    âmbito e a edição resolvem-se dentro da transação (`BEGIN IMMEDIATE`).
    """
    if not request_id:
        raise ValueError("falta o request_id")
    with _transacao(con):
        amb = ambito(con, slug, nome)
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
        mesmo caso, e as cópias marcadas nunca desaparecem.
    (b) Num rotativo, cada nome que mudou de fixa para partilhada (ou ao
        contrário) muda de âmbito com a posse e a escolha de edição. Uma
        partilhada que este deck deixou de jogar não vai para o `n_saida` se
        outro rotativo ainda a joga: só muda de caixa.
    (c) Baixar a quantidade é uma saída PARCIAL (spec: «as cartas que saíram e
        estavam marcadas passam para Vender»): depois das mudanças de âmbito,
        o que estiver marcado acima do que é preciso vai para `n_saida`
        (`saiu_da_lista`). Numa fixa, o preciso é a quantidade do deck dono
        (todas as secções); no monte `ROT`, o máximo que um rotativo pede.

    Um slug que não esteja em `n_deck` trata-se como um deck sempre montado (o
    `gravar_versao` aceita-o, e a posse dele é só dele).
    """
    r = con.execute("SELECT modo FROM n_deck WHERE slug = ?", (slug,)).fetchone()
    rotativo = r is not None and r[0] == "rotativo"
    qtd_antes, qtd_depois = _por_nome(antes), _por_nome(depois)
    nomes_antes, nomes_depois = set(qtd_antes), set(qtd_depois)
    marca = {"slug": slug, "versao_id": versao_id}

    if rotativo:
        mapa_depois = _nomes_rotativos(con, substituir=(slug, qtd_depois))
        mapa_antes = dict(mapa_depois)
        mapa_antes[slug] = qtd_antes
        part_antes = _partilhadas_de(mapa_antes)
        part_depois = _partilhadas_de(mapa_depois)
    else:
        part_antes = part_depois = set()

    # (a)
    for nome in sorted(nomes_antes - nomes_depois):
        if nome in part_antes:
            continue                     # era do monte: trata-o o (b)
        _para_saida(con, slug, nome, motivo="saiu_da_lista", **marca)

    # (b) só os nomes deste deck podem ter mudado de estado
    if rotativo:
        for nome in sorted(nomes_antes | nomes_depois):
            era, e = nome in part_antes, nome in part_depois
            if era == e:
                continue
            if e:
                # fixa → partilhada: vem da caixa do (único) deck que a tinha
                for outro, nomes in mapa_antes.items():
                    if nome in nomes:
                        _mover(con, nome, outro, ROT, **marca)
            else:
                donos = [s for s, nomes in mapa_depois.items() if nome in nomes]
                if donos:
                    # partilhada → fixa: o monte vai para a caixa de quem a joga
                    _mover(con, nome, ROT, donos[0], **marca)
                else:
                    _para_saida(con, ROT, nome, motivo="saiu_da_lista", **marca)

    # (c) o que ficou marcado acima do que é preciso
    for nome in sorted(nomes_depois - part_depois):
        _aparar(con, slug, nome, qtd_depois[nome], **marca)
    if rotativo:
        for nome in sorted(nomes_antes | nomes_depois):
            if nome in part_depois:
                precisa = max(m.get(nome, 0) for m in mapa_depois.values())
                _aparar(con, ROT, nome, precisa, **marca)
            elif nome in part_antes:
                # passou a fixa de outro deck: o monte que lá chegou apara-se
                # ao que esse deck pede
                for dono, nomes in mapa_depois.items():
                    if nome in nomes and dono != slug:
                        _aparar(con, dono, nome, nomes[nome], **marca)


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

    Nos formatos de `FORMATOS_COM_COLECAO`, o que as cópias do deck não cobrem
    vem emprestado das coleções e conta para o `tenho`: cada carta diz quantas
    são (`da_colecao`), de que coleções (`colecoes`, e o pormenor em
    `emprestimo`), e as validadas na coleção contam como validadas aqui.
    """
    deck = _deck(con, slug)
    v = _versao(con, slug)
    rotativo = deck["modo"] == "rotativo"
    empresta = deck["formato"] in FORMATOS_COM_COLECAO
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
    # as validadas do nome (a edição que conta, no âmbito gravado) repartem-se
    # como a posse: um nome em main e em side é UMA edição física, e dar a cada
    # linha o `min(tenho, validadas)` à parte somava mais do que o deck tem
    por_validar: dict[str, int] = {}
    tenho_por: dict[int, int] = {}
    validadas_por: dict[int, int] = {}
    fontes: dict[str, list[dict]] = {}
    emprestado_por: dict[int, list[dict]] = {}
    for i in sorted(range(len(linhas)),
                    key=lambda i: (_ORDEM_SECCAO.get(linhas[i].seccao, 9), i)):
        l = linhas[i]
        amb = _ambito_de(deck, l.nome, part)
        if l.nome not in edicoes:
            edicoes[l.nome] = _edicao_em(con, amb, l.nome)
            monte[l.nome] = _qtd(con, amb, edicoes[l.nome])
            ed_ = edicoes[l.nome]
            por_validar[l.nome] = (
                _fotos().validadas(con, amb, ed_[0], ed_[1]) if ed_ else 0)
        tenho_por[i] = min(l.qtd, monte[l.nome])
        monte[l.nome] -= tenho_por[i]
        validadas_por[i] = min(tenho_por[i], por_validar[l.nome])
        por_validar[l.nome] -= validadas_por[i]
        emprestado_por[i] = []
        if empresta and tenho_por[i] < l.qtd:
            if l.nome not in fontes:
                fontes[l.nome] = _emprestaveis(con, l.nome)
            emprestado_por[i] = _pedir_emprestado(fontes[l.nome],
                                                  l.qtd - tenho_por[i])

    cartas = []
    for i, l in enumerate(linhas):
        ed = edicoes[l.nome]
        amb = _ambito_de(deck, l.nome, part)
        emp = emprestado_por[i]
        da_colecao = sum(x["qtd"] for x in emp)
        tenho = tenho_por[i] + da_colecao
        validadas = validadas_por[i] + sum(x["validadas"] for x in emp)
        # o recorte da cópia dele; se só as emprestadas estão validadas, o
        # recorte da coleção (é a foto de uma cópia que está neste deck)
        recorte = (_fotos().recorte_de(con, amb, ed[0], ed[1])
                   if ed and validadas_por[i] else None)
        if recorte is None:
            for x in emp:
                if x["validadas"]:
                    recorte = _fotos().recorte_de(con, x["colecao"],
                                                  x["scryfall_id"],
                                                  x["acabamento"])
                    break
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
            "tenho": tenho, "falta": l.qtd - tenho,
            "grupo": ("partilhada" if partilhada else "fixa") if rotativo
            else None,
            "onde": onde,
            "preco_un": _trend_hoje(con, ed[0], ed[1]) if ed else None,
            "validadas": validadas,
            # o recorte só aparece onde esta linha tem uma cópia validada
            "recorte": recorte,
            "da_colecao": da_colecao,
            "colecoes": list(dict.fromkeys(x["colecao_nome"] for x in emp)),
            "emprestimo": emp,
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
        "da_colecao": sum(c["da_colecao"] for c in cartas),
        "validadas": sum(c["validadas"] for c in cartas),
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

    O monte das partilhadas anda INTEIRO com o deck montado («as partilhadas
    formam um monte e andam com o deck montado»): está todo na caixa do
    montado antes, e vem todo — também as que este deck não joga, que estão lá
    porque viajaram com a montagem anterior. Um movimento por partilhada com
    cópias no monte (na edição e no acabamento escolhidos), por ordem do nome.
    Nada montado antes, ou este já montado: nada a mover.
    """
    deck = _deck(con, slug)
    if deck["modo"] != "rotativo":
        raise ValueError(f"{slug!r} fica sempre montado: não se monta")
    antes = _montado(con)
    if antes is None or antes == slug:
        return []
    movs = []
    for nome in sorted(partilhadas(con), key=lambda n: (n.lower(), n)):
        n = _qtd(con, ROT, _edicao_em(con, ROT, nome))
        if n > 0:
            movs.append({"nome": nome, "qtd": n, "de": antes, "para": slug})
    return movs


def da_colecao_para(con: sqlite3.Connection, slug: str) -> list[dict]:
    """O que este deck vai buscar às coleções (o empréstimo do
    `estado_deck`), somado por carta e por coleção: `{nome, qtd, colecao,
    colecao_nome}`, pelo nome e depois pela ordem das coleções. Vazio num
    formato que não empresta. Não grava nada: a carta continua na coleção."""
    soma: dict[tuple[str, str], dict] = {}
    for c in estado_deck(con, slug)["cartas"]:
        for x in c["emprestimo"]:
            k = (c["nome"], x["colecao"])
            if k not in soma:
                soma[k] = {"nome": c["nome"], "qtd": 0, "colecao": x["colecao"],
                           "colecao_nome": x["colecao_nome"], "_o": x["ordem"]}
            soma[k]["qtd"] += x["qtd"]
    linhas = sorted(soma.values(),
                    key=lambda m: (m["nome"].lower(), m["nome"], m["_o"]))
    return [{k: m[k] for k in ("nome", "qtd", "colecao", "colecao_nome")}
            for m in linhas]


def definir_montado(con: sqlite3.Connection, slug: str) -> list[dict]:
    """Monta este rotativo (grava `n_montado`) e devolve os movimentos,
    calculados dentro da mesma transação que grava."""
    with _transacao(con):
        movs = movimentos_para(con, slug)
        con.execute("INSERT OR REPLACE INTO n_montado (id, slug) VALUES (1, ?)",
                    (slug,))
    return movs
