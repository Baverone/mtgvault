"""A FOTO É A VERDADE, E A BASE É O REGISTO DELA (André, 2026-10-02).

As palavras dele, à letra:

  *"cada deck tem as suas cartas"*
  *"o que eu colocar de fotos no deck, é daquele deck, ponto"*
  *"se não tiver foto, não tem carta"*
  *"assim fico responsável por cada vez que comprar cartas, ter que tirar a
  foto para atualizar"*

**ISTO INVERTE O MODELO.** Até 2026-10-02 a BASE era a verdade e a foto servia
para *revalidar* (a campanha de 2026-09-20): o `validado_em` era um 📷/✓ que a
página mostrava e que **não mexia um único número**. A partir de hoje é ao
contrário — a FOTO é a verdade, a base é o registo dela, e **uma cópia só CONTA
quando tem foto desta campanha**. A pasta onde ele larga a foto decide a que
deck a carta pertence (`fotos.alvo_da_pasta`, 2026-10-02 de manhã).

O QUE ISTO NÃO É
----------------
Não é apagar nada. As 737 linhas e as 1 678 cartas que já estão na base FICAM,
marcadas como «sem foto». A regra dele de 2026-09-09 mantém-se: **nada se
apaga.** *Sem foto* quer dizer *ainda não conta*, nunca *não existe* — e é por
isso que o `jogaveis()` do `collection` **não se tocou**: uma cópia sem foto
continua a ser uma cópia da colecção, continua a aparecer, continua a valer
dinheiro no total. O que ela não faz é fechar um slot, descontar uma compra ou
ir à venda.

O PERIGO, E O QUE SE FAZ CONTRA ELE
-----------------------------------
Ligar isto a bruto punha a colecção dele a valer zero até acabar de fotografar
1 678 cartas, e a app ficava inútil durante os dias de trabalho. Por isso:

- **TODO o número que a app mostra tem DUAS metades, lado a lado** —
  «confirmado por foto» e «por confirmar». Nunca só uma. Quem as compõe é o
  `metades()` **deste módulo e de nenhum outro**: duas somas ao lado davam duas
  respostas à mesma pergunta, que é a lição do `event_tier`, do `e_foil` e do
  `precos.sql()`. E o `metades()` **levanta** se as duas não somarem o total —
  uma metade que se perca pelo caminho é meia verdade com cara de verdade.
- **As DECISÕES usam só o confirmado**: o que falta a um deck, o que há para
  comprar, o que vai para venda, e o valor com que se decide.
- **O valor total da colecção mostra os dois, e diz qual é qual.**
- **Cada página leva a linha honesta** (`frase()`): *«X de 1 678 cartas
  confirmadas por foto»*.

O INTERRUPTOR
-------------
`colecao_config.json → revalidacao.foto_manda`. É a mesma campanha de 20/09
(`revalidacao.desde`) — não se inventou uma segunda —, e `foto_manda: false`
devolve o vault exactamente ao que era: a foto volta a ser só um ✓. É o padrão
do `venda.mostrar` (2026-09-25), e pela mesma razão: *"para já"* é literal.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from collections import defaultdict
from pathlib import Path

from . import db, revalidacao, sources

# ---------------------------------------------------------------------------
# O interruptor
# ---------------------------------------------------------------------------
CHAVE = "foto_manda"
MANDA_OMISSAO = True


def manda(cfg: dict | None = None) -> bool:
    """A foto manda? (campanha ligada **e** `revalidacao.foto_manda`)

    São as duas condições e não uma: sem campanha (`revalidacao.desde` vazio)
    não há «foto desta campanha» que se possa exigir, e exigi-la punha a
    colecção inteira a não contar por uma chave esquecida.
    """
    c = (cfg or {}).get("revalidacao") if cfg else revalidacao.config()
    c = c if isinstance(c, dict) else {}
    if not revalidacao.activa():
        return False
    v = c.get(CHAVE, MANDA_OMISSAO)
    return bool(v)


# ---------------------------------------------------------------------------
# «Esta cópia conta?» — num sítio só
# ---------------------------------------------------------------------------
# O WHERE de *"esta cópia está confirmada por foto desta campanha"*. Escreve-se
# AQUI e em mais nenhum sítio, pela razão do `collection.jogaveis()`: era
# `cp.validado_em IS NOT NULL` à mão em cada consulta nova, e a primeira que se
# esquecesse voltava a dizer-lhe que tem a carta. Tem teste que varre o código
# à procura do literal.
def sql(alias: str = "cp") -> str:
    """O WHERE de *"confirmada por foto desta campanha"*."""
    return f"{alias}.validado_em IS NOT NULL"


def confirmada(lot: dict) -> bool:
    """Este sub-lote do `loadout.lots()` está confirmado por foto?

    Lê o `validado` que o `lots()` já traz (o `copies.validado_em`). Não faz
    consulta nenhuma: corre milhares de vezes por relatório.
    """
    return bool(lot.get("validado"))


def conta(lot: dict) -> bool:
    """Este sub-lote conta para as DECISÕES?

    Com a foto a mandar, só se estiver confirmada; sem ela, sempre — é o que
    faz `foto_manda: false` devolver o vault ao que era.
    """
    return confirmada(lot) if manda() else True


# ---------------------------------------------------------------------------
# AS DUAS METADES — nunca se mostra só uma
# ---------------------------------------------------------------------------
UNIDADES = {"cartas": ("carta", "cartas"), "copias": ("cópia", "cópias"),
            "fotos": ("foto", "fotos")}

# O NOME da terceira parcela, num sítio só: é por ele que as páginas, os textos e
# o CLI distinguem *«confirmada por foto»* de *«contei e digo-te quantas tenho»*.
# Hoje só os terrenos básicos entram por aqui.
TERMO_DECLARADO = "básicas"
ORIGEM_DECLARADA = "declarada"


class MetadesQueNaoSomam(AssertionError):
    """As duas metades não somam o total.

    É `AssertionError` de propósito: não é um estado que se trate, é um defeito
    de programação. Uma metade que se perde pelo caminho dá um par de números
    que parece honesto e não é — e o número que ele vê todos os dias passa a
    estar errado sem um único passo a falhar (o padrão do `event_tier`).
    """


def metades(confirmado: float, total: float, *, unidade: str = "cartas",
            casas: int = 0, declarado: float = 0) -> dict:
    """As metades de um número: `{confirmado, declarado, por_confirmar, total,
    pct, frase, unidade}`.

    **É a única forma de apresentar um número desta app**, e devolve sempre
    TODAS as parcelas — nunca só a de cima. O `por_confirmar` CALCULA-SE do
    total (nunca se recebe de fora) exactamente para elas somarem por
    construção, e mesmo assim confere-se.

    **A TERCEIRA PARCELA É A CONTAGEM DECLARADA (André, 2026-10-02).** Os
    terrenos básicos entram por contagem dele e não por foto — *"depois indico
    quantas básicas tenho de cada"* —, e por isso **não podem somar-se ao
    «confirmado por foto»**: são duas afirmações de força diferente (uma tem uma
    fotografia por trás, a outra tem a palavra dele) e juntá-las dava um número
    que não serve para nenhuma das duas perguntas. É a mesma disciplina por que
    a venda tem nove saídas em vez de um total. Fica a ZERO por omissão, logo
    quem não a usa continua a ver exactamente as duas metades de sempre.
    """
    if unidade not in UNIDADES:
        raise ValueError(f"unidade desconhecida: {unidade}")

    def _r(v):
        return round(float(v or 0), casas) if casas else (v or 0)

    c, t, d = _r(confirmado), _r(total), _r(declarado)
    pc = round(t - c - d, casas) if casas else (t - c - d)
    if round(c + d + pc, 6) != round(t, 6):
        raise MetadesQueNaoSomam(
            f"{c} + {d} + {pc} != {t} — as parcelas têm de somar o total")
    return {"confirmado": c, "declarado": d, "por_confirmar": pc, "total": t,
            "pct": round(100 * c / t) if t else 0,
            "pct_contado": round(100 * (c + d) / t) if t else 0,
            "unidade": unidade,
            "frase": frase(c, t, unidade=unidade, declarado=d)}


def frase(confirmado: float, total: float, *, unidade: str = "cartas",
          declarado: float = 0) -> str:
    """A LINHA HONESTA que vai em cada página: *«X de 1 678 cartas confirmadas
    por foto»* — e, no estado de hoje, *«0 de 1 678 …»*, que é a verdade.

    Com a foto desligada diz o total e cala-se sobre metades que não mandam em
    nada: uma frase a prometer uma regra que não está ligada é pior do que
    frase nenhuma.

    A CONTAGEM DECLARADA vai **ao lado e com outro nome** (02/10/2026), nunca
    somada ao confirmado: *«0 de 1 678 cartas confirmadas por foto · 95 por
    contagem declarada (básicas)»*. Só aparece quando existe.
    """
    sing, plur = UNIDADES.get(unidade, UNIDADES["cartas"])
    nome = sing if total == 1 else plur
    if not manda():
        return f"{_n(total)} {nome}"
    base = (f"{_n(confirmado)} de {_n(total)} {nome} confirmadas por foto"
            if confirmado != total
            else f"as {_n(total)} {nome} estão confirmadas por foto")
    if declarado:
        base += (f" · {_n(declarado)} por contagem declarada "
                 f"({TERMO_DECLARADO})")
    return base


def _n(v) -> str:
    """Um numero INTEIRO em portugues: milhares separados por ESPACO.

    O mesmo separador do `paginas.eur`, e de proposito: a licao de 2026-09-24 e
    que *"a conta estava certa nas seis paginas; o que mudava era o separador"*.
    A primeira versao disto levava um espaco fino (U+202F) e dava
    `0 de 1 678` onde o resto do site diz `1 678` — o mesmo defeito, com um
    caracter invisivel.

    Os EUROS nao se formatam aqui: vao ao `paginas.eur`, que e o unico sitio onde
    isso se escreve.
    """
    return f"{int(round(v)):,}".replace(",", " ")


def euros(confirmado: float, total: float) -> dict:
    """As duas metades de um VALOR, com os textos em euros ja feitos.

    Os textos saem do **`paginas.eur`** e nao de um formatador novo: quatro
    paginas ja ficaram em ingles (`1 009.27 €`) por cada uma escrever o seu.
    """
    from . import paginas                                     # noqa: PLC0415
    m = metades(confirmado, total, unidade="cartas", casas=2)
    m["texto_confirmado"] = paginas.eur(m["confirmado"])
    m["texto_por_confirmar"] = paginas.eur(m["por_confirmar"])
    m["texto_total"] = paginas.eur(m["total"])
    m["frase"] = (f"{m['texto_confirmado']} confirmados por foto · "
                  f"{m['texto_por_confirmar']} por confirmar"
                  if manda() else m["texto_total"])
    return m


# ---------------------------------------------------------------------------
# NADA SE VENDE SEM FOTO — e é outro motivo, não uma protecção
# ---------------------------------------------------------------------------
# «Protegida» e «por confirmar» são coisas DIFERENTES e a saída separa-as
# (ordem dele). Uma protegida é uma decisão TOMADA — *"esta não se vende"*; uma
# por confirmar é uma decisão por TOMAR — *"ainda não sei o que isto é, tira-lhe
# a foto"*. Metê-las na mesma saída dava um número que não serve para nenhuma
# das duas perguntas, que é o defeito que as sete saídas da venda existem para
# não ter.
RAZAO_SEM_FOTO = "sem foto desta campanha"
MOTIVO_SEM_FOTO = ("sem foto desta campanha — ainda não conta; tira-lhe a foto "
                   "e ela aparece aqui na corrida seguinte")


def filtrar_sem_foto(linhas: list[dict]) -> tuple[list[dict], list[dict]]:
    """Parte uma lista de venda em `(as que podem sair, as que não têm foto)`.

    A linha traz `validado` (o `linha_de` do `sell_list` carimba-o do sub-lote,
    pela mesma razão por que carimba a `caixa`: um lote de 4 com 3 na caixa e 1
    na gaveta são dois sub-lotes com o mesmo `copies.id`).
    """
    if not manda():
        return list(linhas), []
    ficam, sem = [], []
    for r in linhas:
        if r.get("validado"):
            ficam.append(r)
        else:
            sem.append(dict(r, motivo=MOTIVO_SEM_FOTO,
                            porque_venderia=r.get("reason") or "",
                            reason=f"{RAZAO_SEM_FOTO}: {MOTIVO_SEM_FOTO}"))
    return ficam, sem


# ---------------------------------------------------------------------------
# CADA DECK AS SUAS CARTAS: uma cópia nunca em dois decks
# ---------------------------------------------------------------------------
class AlocacaoDupla(ValueError):
    """Pediu-se uma alocação que punha a mesma cópia em dois decks.

    É `ValueError` como a `webapp.VendaDesligada` e a `fases.VendaCongelada`,
    para o `do_POST` a traduzir num 409 com a frase em português — e para quem
    já apanhava `ValueError` não ficar a ver uma excepção nova.
    """


def alocacoes(con, copy_id: int) -> dict[str, int]:
    """`slot -> quantas` desta cópia, hoje, na `copy_allocation`."""
    try:
        rows = con.execute(
            "SELECT slot, quantity FROM copy_allocation WHERE copy_id = ?",
            (int(copy_id),))
    except sqlite3.OperationalError:
        return {}
    return {r[0]: r[1] for r in rows if (r[1] or 0) > 0}


def duplas(con) -> set[int]:
    """As cópias que estão HOJE em dois ou mais decks.

    São as que se GRANDFATHERAM: na base dele há exactamente duas (2026-10-02),
    e a ordem é explícita — *"não as resolvas por ti: marca-as como CONFLITO
    visível"*. O que o guarda recusa é uma dupla **nova**.
    """
    try:
        rows = con.execute(
            "SELECT copy_id FROM copy_allocation WHERE quantity > 0 "
            "GROUP BY copy_id HAVING COUNT(DISTINCT slot) > 1")
    except sqlite3.OperationalError:
        return set()
    return {int(r[0]) for r in rows}


def quantidades(con, ids) -> dict[int, int]:
    """`copy_id -> quantity` da `copies`, para o tecto da sobre-alocação."""
    ids = [int(i) for i in dict.fromkeys(ids)]
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {int(r[0]): int(r[1] or 0) for r in con.execute(
        f"SELECT id, quantity FROM copies WHERE id IN ({marks})", ids)}


def estado_final(con, slot: str, pares) -> list[tuple[int, str, int]]:
    """O estado da `copy_allocation` DEPOIS de escrever `pares` no `slot`.

    Serve os escritores que substituem a caixa inteira (`guardar_arrumacao`,
    `registar_marcadas`, `actualizar_caixa`): o que eles escrevem só se pode
    julgar contra o resto da tabela, nunca contra a tabela inteira de antes —
    senão a caixa que vai ser reescrita aparecia como «já está noutro sítio».
    """
    out = [(int(r[0]), r[1], int(r[2] or 0)) for r in con.execute(
        "SELECT copy_id, slot, quantity FROM copy_allocation WHERE slot <> ?",
        (slot,)) if (r[2] or 0) > 0]
    out += [(int(cid), slot, int(q)) for cid, q in pares if int(q) > 0]
    return out


def exige_alocacao_unica(con, linhas, *, permitir=None) -> None:
    """Levanta `AlocacaoDupla` se o estado FINAL puser uma cópia em dois decks
    ou alocar mais cópias do que o lote tem.

    São DUAS asserções e as duas são a mesma regra dele vista de dois lados:

    1. **a mesma cópia em dois decks** — *"cada deck tem as suas cartas"*. Esta
       só morde com a foto a mandar e **nunca** nas cópias que já estavam
       assim (`permitir`, por omissão as `duplas(con)` de hoje);
    2. **mais alocado do que existe** — a sobre-alocação, que é a mesma carta
       física em dois sítios ao mesmo tempo. Esta morde **sempre**, com a foto
       a mandar ou não: era já hoje impossível, e nada a travava.

    A verificação é PRÉ-VOO, antes de uma única linha ser escrita: validar
    depois obrigava a desfazer um `commit` que já tinha acontecido.
    """
    permitir = duplas(con) if permitir is None else {int(i) for i in permitir}
    por: dict[int, dict[str, int]] = defaultdict(dict)
    for cid, slot, q in linhas:
        if q > 0:
            por[int(cid)][slot] = por[int(cid)].get(slot, 0) + int(q)
    qtds = quantidades(con, list(por))
    for cid, sl in sorted(por.items()):
        usados = sorted(s for s, q in sl.items() if q > 0)
        if len(usados) > 1 and cid not in permitir and manda():
            raise AlocacaoDupla(
                f"a cópia {cid} ficava em dois decks ao mesmo tempo "
                f"({', '.join(usados)}) — cada deck tem as suas cartas. "
                f"Fotografa-a na pasta do deck a que pertence.")
        total = sum(sl.values())
        tecto = qtds.get(cid)
        if tecto is not None and total > tecto:
            raise AlocacaoDupla(
                f"a cópia {cid} tem {tecto} carta(s) e ficavam {total} "
                f"alocadas ({', '.join(f'{s}={q}' for s, q in sorted(sl.items()))})"
                f" — a mesma carta não está em dois sítios.")


def exige_uma_so(con, copy_id: int, slot: str, q: int) -> None:
    """A versão de UMA cópia, para quem insere uma linha só (a encomenda que a
    foto fecha, o *"já a tenho"*): o estado final desta cópia é o que ela já tem
    nos OUTROS slots mais o que se vai escrever neste."""
    al = {s: n for s, n in alocacoes(con, copy_id).items() if s != slot}
    linhas = [(copy_id, s, n) for s, n in al.items()]
    linhas.append((copy_id, slot, int(q)))
    exige_alocacao_unica(con, linhas)


def conflitos(con, nomes: dict[str, str] | None = None) -> list[dict]:
    """O CONFLITO VISÍVEL: as cópias em dois decks, para ele resolver quando
    fotografar esses decks.

    Não se resolve por iniciativa própria (ordem dele). Na base de 2026-10-02
    são duas, e as duas são **lotes partidos**: a 293 são 2 Sewer-veillance Cam
    foil EN com 1 no Modern e 1 no Pauper, e a 543 são 4 Hydroblast PT com 2 no
    UW Replenish e 2 no Stiflenought. As quantidades **somam** a do lote, por
    isso hoje nenhuma carta física está em dois sítios — o que está em dois
    sítios é a LINHA da `copies`, que é um lote e não uma carta. Mesmo assim
    é um conflito a resolver: a partir de hoje é a foto que diz de quem é cada
    carta, e um lote partido precisa de uma foto em cada pasta para continuar
    como está.
    """
    from . import loadout                                    # noqa: PLC0415
    nomes = loadout.nomes_das_caixas() if nomes is None else nomes
    ids = sorted(duplas(con))
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    det = {int(r["id"]): dict(r) for r in con.execute(
        f"""SELECT cp.id, cp.quantity q, cp.finish, cp.language lang,
                   cp.validado_em, cp.photo_path,
                   c.name nm, c.set_code, c.collector_number num
              FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
             WHERE cp.id IN ({marks})""", ids)}
    out = []
    for cid in ids:
        d = det.get(cid) or {}
        al = alocacoes(con, cid)
        out.append({
            "copy_id": cid, "nm": (d.get("nm") or "").split(" // ", 1)[0],
            "q": d.get("q") or 0, "set": (d.get("set_code") or "").upper(),
            "num": d.get("num") or "", "lang": (d.get("lang") or "").upper(),
            "finish": d.get("finish") or "", "validado": d.get("validado_em") or "",
            "slots": sorted(al), "quantidades": dict(sorted(al.items())),
            "decks": [nomes.get(s) or s for s in sorted(al)],
            "soma": sum(al.values()),
            # O lote PARTIDO (a soma bate com a quantidade) não é a mesma carta
            # em dois sítios; o que passa da quantidade é. São dois problemas e
            # a página tem de os poder dizer com palavras diferentes.
            "sobrealocada": sum(al.values()) > (d.get("q") or 0),
            "motivo": ("mais cópias alocadas do que o lote tem"
                       if sum(al.values()) > (d.get("q") or 0)
                       else "lote partido entre dois decks — precisa de uma "
                            "foto em cada pasta"),
        })
    return out


# ---------------------------------------------------------------------------
# A FOTO MANDA NA ALOCAÇÃO
# ---------------------------------------------------------------------------
LOG = "foto-manda.log"


def ficheiro_log() -> Path:
    """`data/foto-manda.log` — o que a foto mudou na alocação.

    Pela razão do `data/revalidacao.log` e do `desmontar.log`: a foto passou a
    poder TIRAR uma cópia do deck onde ela estava registada, e isso é a única
    coisa que se perde. Sai de `db.pasta_dados()` (a pasta da `MTGVAULT_DB`) e
    não de `db.ROOT` — é a nota de 2026-09-08, e foi por aí que o
    `arquetipos.json` foi parar fora do repositório.
    """
    return db.pasta_dados() / LOG


def _log(accao: str, detalhe: str, log_path: Path | None = None) -> Path:
    p = Path(log_path) if log_path else ficheiro_log()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}\t{accao}\t{detalhe}\n")
    return p


def alvo_da_pasta(photo_path: str | None) -> tuple[bool, str | None]:
    """A PASTA onde a foto foi largada decide a que deck a carta pertence:
    devolve `(decide, slot)`.

    `(True, "cedh-blue-farm")` — a foto veio da pasta daquele deck (ou do botão
    «Tirar fotos» com aquela caixa como alvo); `(True, None)` — veio de
    `Extras (fora dos decks)`, logo a cópia fica **sem deck**; `(False, None)` —
    a foto não diz nada e a alocação não se toca.

    Quem sabe ler isto é o `fotosite.origem`, pelo NOME do ficheiro
    (`site-<slot>-…`, `site-colecao-…`) — e é o `fotos.recolher_das_pastas` que
    renomeia a foto da pasta do deck para esse nome, desde 2026-10-01. Não se
    escreveu um segundo leitor: *«um caminho só, e é o que já estava testado»*.

    **O alvo GLOBAL do config não serve aqui, de propósito.** Ele é *"a caixa que
    estou a fotografar"* e vale para PREFERIR cópias no passo (0); usá-lo para
    REESCREVER alocações fazia uma foto largada à mão em `pendentes/` mudar o
    deck de uma carta por causa de um botão carregado ontem. A ordem dele é sobre
    a pasta: *"o que eu colocar de fotos no deck, é daquele deck, ponto"*.
    """
    from . import fotos, fotosite                            # noqa: PLC0415
    o = fotosite.origem(photo_path or "")
    if not o:
        return False, None
    if o["tipo"] == "caixa" and o.get("slot"):
        return True, o["slot"]
    if o["tipo"] == fotos.ALVO_FORA_DOS_DECKS:
        return True, None
    return False, None


def alocar_por_foto(con, copy_id: int, slot: str | None, q: int | None = None,
                    *, dia: str | None = None, nomes: dict | None = None,
                    log_path: Path | None = None) -> dict:
    """A foto decide a que deck esta cópia pertence. **Ganha a foto.**

    `slot` é a caixa da pasta onde a foto foi largada; `slot=None` é a pasta
    `Extras (fora dos decks)` — *"foto nos Extras = cópia SEM deck"*.

    É EXCLUSIVA: o que estava registado noutro deck SAI, com linha no
    `foto-manda.log` a dizer de onde para onde. É a inversão de 02/10 a
    morder — até aqui a `copy_allocation` ganhava à correcção (foi o defeito do
    ponto 5 de 09/09, *"um registo não lava uma correcção"*), e agora é a foto
    que ganha ao registo. A alocação automática do `loadout` passa a SUGERIR:
    continua a dizer onde a carta devia estar, e já não decide onde está.

    Devolve `{copy_id, slot, q, saiu, mudou}`.
    """
    from . import loadout                                    # noqa: PLC0415
    cid = int(copy_id)
    nomes = loadout.nomes_das_caixas() if nomes is None else nomes
    dia = dia or revalidacao.hoje()
    tecto = quantidades(con, [cid]).get(cid, 0)
    leva = tecto if q is None else max(0, min(int(q), tecto))
    antes = alocacoes(con, cid)
    saiu: list[dict] = []
    # O que ela pode ocupar NOUTROS decks depois desta foto: o resto do lote.
    sobra = max(0, tecto - leva)
    for outro in sorted(antes):
        if outro == slot:
            continue
        tinha = antes[outro]
        fica = min(tinha, sobra)
        sobra -= fica
        if fica >= tinha:
            continue
        if fica <= 0:
            con.execute("DELETE FROM copy_allocation WHERE copy_id = ? AND slot = ?",
                        (cid, outro))
        else:
            con.execute("UPDATE copy_allocation SET quantity = ? "
                        "WHERE copy_id = ? AND slot = ?", (fica, cid, outro))
        saiu.append({"slot": outro, "nome": nomes.get(outro) or outro,
                     "de": tinha, "para": fica})
        _log("saiu-do-deck",
             f"cópia {cid}: {nomes.get(outro) or outro} {tinha} → {fica} "
             f"(a foto pôs {leva} em {nomes.get(slot) or slot or 'Extras'})",
             log_path)
    if slot and leva > 0:
        con.execute(
            "INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at) "
            "VALUES (?,?,?,?) ON CONFLICT(copy_id, slot) DO UPDATE SET "
            "quantity = excluded.quantity, placed_at = excluded.placed_at",
            (cid, slot, leva, f"{dia} (foto)"))
        if antes.get(slot) != leva:
            _log("entrou-no-deck",
                 f"cópia {cid}: {nomes.get(slot) or slot} ← {leva} pela foto",
                 log_path)
    elif slot is None:
        # EXTRAS: a foto prova que está FORA dos decks. Não se apaga a cópia —
        # apaga-se a afirmação de que ela estava dentro de um deck.
        for outro in sorted(alocacoes(con, cid)):
            con.execute("DELETE FROM copy_allocation WHERE copy_id = ? AND slot = ?",
                        (cid, outro))
            _log("fora-dos-decks",
                 f"cópia {cid}: saiu de {nomes.get(outro) or outro} — a foto está "
                 f"nos Extras (fora dos decks)", log_path)
            saiu.append({"slot": outro, "nome": nomes.get(outro) or outro,
                         "de": antes.get(outro, 0), "para": 0})
    con.commit()
    depois = alocacoes(con, cid)
    return {"copy_id": cid, "slot": slot, "q": leva, "saiu": saiu,
            "mudou": depois != antes, "antes": antes, "depois": depois}


# ---------------------------------------------------------------------------
# O PROGRESSO: por deck e no total, em cartas e em euros
# ---------------------------------------------------------------------------
def progresso(con, rep: dict | None = None, dia: str | None = None) -> dict:
    """*«X de 1 678 cartas confirmadas por foto»*, por deck e no total, com o
    que falta em VALOR — é o que ele vai olhar todos os dias enquanto fotografa.

    **Não conta nada por si**: a contagem é o `revalidacao.progresso` de
    2026-09-20, que já parte a colecção por caixa/venda/RL/resto e já sabe
    quantas estão validadas. O que este acrescenta é o EURO de cada metade, pela
    conta única de 2026-09-24 (`collection.mapa_precos` + `preco_impressao`) —
    uma segunda contagem ao lado era a lição do `event_tier` outra vez.
    """
    from . import collection                                 # noqa: PLC0415
    base = revalidacao.progresso(con, rep, dia)
    mapa = collection.mapa_precos(con)

    def valor(linhas, so_validadas: bool | None = None) -> float:
        t = 0.0
        for l in linhas:
            if so_validadas is not None and bool(l.get("validado_em")) != so_validadas:
                continue
            # O `preco_impressao` devolve o PAR (preço, acabamento a que ele
            # corresponde) — a conta única de 2026-09-24. Só o primeiro entra.
            p, _fin = collection.preco_impressao(mapa, l.get("sid"), l.get("fin"))
            t += (p or 0) * (l.get("q") or 0)
        return round(t, 2)

    def enfeita(grp: dict) -> dict:
        ls = grp.get("linhas") or []
        tot, conf = valor(ls), valor(ls, True)
        grp["cartas"] = metades(grp.get("validadas", 0), grp.get("q", 0))
        grp["valor"] = euros(conf, tot)
        grp["falta_valor"] = grp["valor"]["por_confirmar"]
        return grp

    for grp in base.get("caixas") or []:
        enfeita(grp)
    for k in ("venda", "rl", "resto"):
        if isinstance(base.get(k), dict):
            enfeita(base[k])
    # O TOTAL sai da soma dos grupos e não de uma terceira consulta: a partição
    # já garante que a soma dos grupos É a colecção (tem teste desde 20/09).
    t = base["total"]
    grupos = list(base.get("caixas") or []) + [base[k] for k in ("venda", "rl", "resto")
                                               if isinstance(base.get(k), dict)]
    t["cartas"] = metades(t.get("validadas", 0), t.get("q", 0))
    t["valor"] = euros(sum(g["valor"]["confirmado"] for g in grupos),
                       sum(g["valor"]["total"] for g in grupos))
    base["manda"] = manda()
    base["conflitos"] = conflitos(con)
    base["frase"] = t["cartas"]["frase"]
    return base


# ---------------------------------------------------------------------------
# O relatório curto do CLI
# ---------------------------------------------------------------------------
def texto(con, rep: dict | None = None) -> str:
    """O progresso em texto, para o `cli foto` e para o log do `daily`."""
    p = progresso(con, rep)
    out = [f"A FOTO MANDA: {'ligada' if p['manda'] else 'DESLIGADA'}"
           f"  (campanha desde {p.get('desde') or '—'})",
           f"  {p['frase']}  ·  {p['total']['valor']['frase']}", ""]
    for g in sorted(p.get("caixas") or [], key=lambda g: -g["cartas"]["total"]):
        if not g["cartas"]["total"]:
            continue
        out.append(f"  {g['nome'][:34]:<34} {g['cartas']['confirmado']:>4} de "
                   f"{g['cartas']['total']:>4}  falta "
                   f"{g['valor']['texto_por_confirmar']:>12}")
    for k, t in (("resto", "Colecção (o resto)"), ("rl", "Caixa Reserved List"),
                 ("venda", "Venda")):
        g = p.get(k)
        if isinstance(g, dict) and g["cartas"]["total"]:
            out.append(f"  {t[:34]:<34} {g['cartas']['confirmado']:>4} de "
                       f"{g['cartas']['total']:>4}  falta "
                       f"{g['valor']['texto_por_confirmar']:>12}")
    if p["conflitos"]:
        out += ["", f"CONFLITOS DE ALOCAÇÃO DUPLA: {len(p['conflitos'])} "
                    f"(para ele resolver ao fotografar; não se tocam)"]
        for c in p["conflitos"]:
            out.append(f"  cópia {c['copy_id']}: {c['q']}× {c['nm']} ({c['set']} "
                       f"{c['lang']} {c['finish']}) — "
                       + ", ".join(f"{n}={q}" for n, q in
                                   zip(c['decks'], c['quantidades'].values()))
                       + f" · {c['motivo']}")
    return "\n".join(out)
