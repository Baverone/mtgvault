"""AS FOTOS: no máximo QUATRO cartas por foto, e onde cada foto vive
(André, 2026-10-01).

À letra: *"organiza o Blue farm e CDEH por tipo de carta e ate 4 cartas por
foto"* e *"se sao 4 fotos, e 1 foto com as 4 cartas"*.

Isto corrige DUAS regras erradas que estiveram escritas neste repositório no
mesmo dia, e as duas pela mesma razão — a unidade da fila:

  * *"a fila conta CÓPIAS FÍSICAS: um playset dá quatro linhas"* (o `_explode`
    do `fases.py`). Dava **quatro fotos** a um playset, que é exactamente o
    contrário do que ele pediu;
  * *"uma foto por linha, e uma foto só valida cópias da MESMA carta"*. Também
    não: uma foto PODE validar cartas diferentes.

A regra verdadeira, e é uma só: **uma foto leva no máximo 4 CARTAS**, dispostas
e agrupadas para cada uma se ver e se poder avaliar.

  1. as cópias da MESMA carta vão sempre juntas na mesma foto (4× Mox Opal = 1
     foto, não 4);
  2. num deck singleton (os dois de cEDH) juntam-se até 4 cartas DIFERENTES na
     mesma foto, **agrupadas por tipo** — planeswalkers, criaturas, artefactos,
     encantamentos, instantâneos, feitiços, terras;
  3. uma linha da `copies` não se parte entre duas fotos. A única excepção é a
     linha que sozinha passa das 4 cartas (as 29 Snow-Covered Plains): essa
     enche fotas inteiras só dela — não há outra forma de respeitar o tecto, e
     fica dito em vez de resolvido em silêncio.

O que distingue estas fotos das de GRUPO antigas **não é serem da mesma carta**:
é serem no máximo quatro, dispostas e agrupadas. Medido na base de 2026-10-01,
as antigas têm média de **4,8 cartas** e chegam a **33** num monte sem ordem, e
numa dessas não se consegue julgar o estado de cada carta. Por isso uma foto
antiga com mais de 4 cartas **não conta como validação** (`valida`), e a mesma
régua recusa uma foto NOVA que traga mais do que quatro.

E AQUI VIVE TAMBÉM O «ONDE ESTÁ A FOTO» — pela mesma razão de sempre (o
`e_foil`, o `vistoId`, o `precos.sql()`): a segunda resposta à mesma pergunta
discorda da primeira um dia qualquer, em silêncio.

  * `resolver` — o `copies.photo_path` é, na base dele, um **nome simples**
    (`<uuid>.jpg`; medido: 348 distintos, **zero** com separador de pasta) que
    valia por estar numa pasta só. Arquivá-las sem mais nada quebrava 723
    registos, por isso o resolvedor procura nas DUAS: a pasta de trabalho
    (`pendentes/`) **ganha**, e o arquivo (`data/fotos/`) responde pelo resto.
    Não se reescreveu uma única das 723 linhas.
  * `arquivar` — move (nunca apaga; a regra dele de 09/09) as fotos de
    `pendentes/fotos processadas/` para `data/fotos/anteriores/`, para a pasta
    de trabalho dele ficar limpa sem se perder a prova.
  * `pasta_do_alvo` — as fotos NOVAS ficam arrumadas por DECK sozinhas
    (`data/fotos/<slot>/`), com o slot a vir do **alvo da revalidação** e nunca
    de um palpite.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import db

# ---------------------------------------------------------------------------
# A REGRA, num sítio só
# ---------------------------------------------------------------------------
MAX_CARTAS = 4

# A ORDEM por que ele dispõe as cartas na mesa, nas palavras dele:
# «planeswalkers, criaturas, artefactos, encantamentos, instantâneos, feitiços,
# terras». É DELIBERADAMENTE outra ordem que a do `paginas.TIPOS` (Creature
# primeiro), que é a ordem por que se LÊ uma decklist (pedido dele de
# 2026-08-31) — duas perguntas, duas ordens. O que NÃO se duplica é a
# PRECEDÊNCIA: em que tipo cai uma carta de vários tipos continua a responder o
# `paginas.tipo_de` (Artifact Land → Artifact, Enchantment Land → Enchantment,
# Artifact Creature → Creature), e é dele que estes nomes saem.
ORDEM_TIPO = ["Planeswalker", "Creature", "Artifact", "Enchantment",
              "Instant", "Sorcery", "Land", "Other"]
ROTULO_TIPO = {"Planeswalker": "Planeswalkers", "Creature": "Criaturas",
               "Artifact": "Artefactos", "Enchantment": "Encantamentos",
               "Instant": "Instantâneos", "Sorcery": "Feitiços",
               "Land": "Terras", "Other": "Outras"}


def valida(cartas: int, max_cartas: int = MAX_CARTAS) -> bool:
    """Esta foto conta como validação? Só se trouxer 1 a `max_cartas` cartas.

    É a trava, e vale para os dois lados: a foto NOVA que traga mais do que
    quatro é recusada à entrada, e a foto ANTIGA com mais do que quatro nunca
    conta — as cópias dela continuam por revalidar.
    """
    return 0 < int(cartas or 0) <= max_cartas


def motivo_demasiadas(cartas: int, max_cartas: int = MAX_CARTAS) -> str:
    return (f"a foto tem {cartas} cartas — uma foto valida no máximo "
            f"{max_cartas}. Volta a fotografar em grupos de até {max_cartas}, "
            "agrupados por tipo de carta, com cada carta à vista.")


# ---------------------------------------------------------------------------
# AGRUPAR: as linhas de uma fila em FOTOS de até 4 cartas
# ---------------------------------------------------------------------------
def agrupar(linhas: list[dict], *, tipos: dict[str, str] | None = None,
            por_tipo: bool = True, max_cartas: int = MAX_CARTAS,
            prefixo: str = "") -> list[dict]:
    """`[linha, …]` → `[foto, …]`, cada foto com no máximo `max_cartas` cartas.

    Cada `linha` é uma linha da `copies` com `nm`, `copy_id`, `q` e `unit` (o
    preço por cópia). Cada `foto` leva:

        n           o número dentro da fila (1, 2, 3…)
        foto_id     id estável, para o browser e para os testes
        tipo        o tipo em que esta foto cai (só com `por_tipo`)
        cartas      quantas CARTAS FÍSICAS a foto cobre (o que o tecto limita)
        linhas      quantas linhas da `copies` ela cobre
        itens       as linhas, com a quantidade que vai NESTA foto
        valor       a soma do preço das cartas que lá estão
        feita       `True` quando TODAS as cópias dela já estão validadas
        perdidas    quantas delas não têm hoje foto no disco

    Com `por_tipo` as fotos **não atravessam tipos**: um tipo que acabe com uma
    carta deixa uma foto de uma carta em vez de a juntar à do tipo seguinte. É o
    que ele pediu («organiza por tipo de carta»), e é o que o plano de
    `ai-pc/work/saidas/plano-fotos-cedh-2026-10-01.txt` tem. Sem `por_tipo`
    respeita-se a ordem com que as linhas vêm (é o caso da Fase 4, que é por
    preço decrescente).
    """
    tipos = tipos or {}
    if por_tipo:
        baldes: list[tuple[str, list[dict]]] = []
        for t in ORDEM_TIPO:
            ls = [l for l in linhas if tipos.get(l["nm"], "Other") == t]
            if ls:
                baldes.append((t, sorted(ls, key=_ordem_no_tipo)))
        # Um tipo que o `ORDEM_TIPO` não conheça não desaparece: vai no fim.
        resto = [l for l in linhas if tipos.get(l["nm"], "Other") not in ORDEM_TIPO]
        if resto:
            baldes.append(("Other", sorted(resto, key=_ordem_no_tipo)))
    else:
        baldes = [("", list(linhas))]

    out: list[dict] = []
    for tipo, ls in baldes:
        atual: list[dict] = []
        cartas = 0
        for l in ls:
            q = int(l.get("q") or 0)
            if q <= 0:
                continue
            if q > max_cartas:
                # A linha que SOZINHA passa do tecto (as 29 Snow-Covered
                # Plains): fecha o que estava a juntar e enche fotos inteiras
                # só dela. É a única forma de respeitar as 4 cartas, e por isso
                # a foto di-lo (`partida`) em vez de o esconder.
                if atual:
                    out.append(_foto(out, atual, tipo, prefixo))
                    atual, cartas = [], 0
                resta = q
                while resta > 0:
                    leva = min(resta, max_cartas)
                    out.append(_foto(out, [dict(l, q=leva)], tipo, prefixo,
                                     partida=True))
                    resta -= leva
                continue
            if atual and cartas + q > max_cartas:
                out.append(_foto(out, atual, tipo, prefixo))
                atual, cartas = [], 0
            atual.append(dict(l, q=q))
            cartas += q
        if atual:
            out.append(_foto(out, atual, tipo, prefixo))
    return out


def _ordem_no_tipo(l: dict) -> tuple:
    return (l.get("nm") or "", l.get("set") or "", l.get("copy_id") or 0)


# Os campos que uma linha leva DENTRO de uma foto, e só esses. A linha de
# candidato traz o `set_name`, a fonte e a origem do preço, o `sid` e a caixa —
# nada disso se desenha, e com eles a parte `fase4` saía em centenas de KB para
# uma página que é para abrir no telemóvel pela rede de casa. É a mesma
# disciplina do `deckboxes.CAIXA_PESADO` (2026-09-15).
CAMPOS_ITEM = ("nm", "copy_id", "q", "set", "lang", "finish", "foil", "cond",
               "local", "validado", "rl", "foto_perdida")


def _foto(ja: list, itens: list[dict], tipo: str, prefixo: str,
          partida: bool = False) -> dict:
    n = len(ja) + 1
    magros = [{k: i[k] for k in CAMPOS_ITEM if k in i} for i in itens]
    cartas = sum(int(i["q"]) for i in magros)
    return {
        "n": n, "foto_id": f"{prefixo}f{n:03d}" if prefixo else f"f{n:03d}",
        "tipo": tipo, "tipo_nome": ROTULO_TIPO.get(tipo, tipo),
        "cartas": cartas, "linhas": len(magros), "itens": magros,
        "valor": round(sum((i.get("unit") or 0) * int(i["q"]) for i in itens), 2),
        # O preço da carta MAIS CARA da foto. É por ele que a Fase 4 se ordena
        # (*"por carta, da mais cara para a mais barata"*) e é por ele que o
        # teste mede a ordem: o `valor` da foto depende de quantas cartas lá
        # cabem e não serve para a comparar com a do lado.
        "preco_max": round(max((i.get("unit") or 0) for i in itens), 2),
        "feita": all(i.get("validado") for i in magros),
        "feitas_cartas": sum(int(i["q"]) for i in magros if i.get("validado")),
        "perdidas": sum(int(i["q"]) for i in magros if i.get("foto_perdida")),
        "partida": partida,
    }


def texto_do_plano(nome: str, slot: str, fotos_: list[dict], *,
                   conversao: bool = False, nota: str = "") -> str:
    """O plano de fotos de um deck em TEXTO, para ele ler à frente da estante.

    Sai das MESMAS fotos que a página desenha (`fases.fila_decks`) — não é uma
    segunda contagem. Existe porque o supervisor pré-criou uma pasta por deck em
    `Colocar fotos da coleção aqui\\` com um `_plano.txt` que prometia este
    plano **e mandava largar as fotos nessa pasta** — e nada no vault processa
    essa pasta: as fotos ficavam lá para sempre, sem um único erro. O plano
    fica; a instrução passou a dizer o sítio certo.
    """
    cartas = sum(f["cartas"] for f in fotos_)
    out = [f"PLANO DE FOTOS -- {nome}",
           f"slot: {slot} | {len(fotos_)} fotos para {cartas} cartas",
           "",
           f"REGRA: no maximo {MAX_CARTAS} CARTAS por foto, agrupadas por TIPO.",
           "As copias da MESMA carta vao sempre juntas (4x Mox Opal = 1 foto).",
           "Cada carta tem de estar a vista e poder avaliar-se.",
           ""]
    if conversao:
        out += ["*** ESTE DECK FICA PARA DEPOIS ***", nota or NOTA_CONVERSAO_TXT, ""]
    out += ["ONDE LARGAR AS FOTOS: soltas na RAIZ de  pendentes\\",
            "  (ou pelo telemovel, no botao «Tirar fotos» da pagina)",
            "NAO as largues nesta pasta: 'Colocar fotos da colecao aqui' e para",
            "  cartas NOVAS e NADA a processa -- as fotos ficavam aqui para sempre.",
            "Antes de fotografar, fixa o ALVO: pagina «Arrumacao por fases», Fase 2,",
            "  botao «Fotografar este deck». E o alvo que arruma as fotos por deck.",
            "", "=" * 70, ""]
    tipo = None
    for f in fotos_:
        if f["tipo"] != tipo:
            tipo = f["tipo"]
            out.append(f"  {ROTULO_TIPO.get(tipo, tipo).upper()}")
        out.append(f"    foto {f['n']:02d}  ({f['cartas']} carta"
                   f"{'' if f['cartas'] == 1 else 's'}"
                   + (", lote partido" if f["partida"] else "") + ")")
        for i in f["itens"]:
            pre = f"{i['q']}x " if i["q"] > 1 else "   "
            out.append(f"         {pre}{i['nm'][:38]:38} {i.get('set', ''):5} "
                       f"{i.get('finish', ''):8} {i.get('lang', '')}"
                       + ("   [a foto antiga desapareceu]"
                          if i.get("foto_perdida") else ""))
    out.append("")
    return "\n".join(out) + "\n"


NOTA_CONVERSAO_TXT = ("Este deck e do grupo que partilha as cartas e se monta "
                      "por conversao de outro. Primeiro os de lista unica.")


def barra(fotos: list[dict]) -> dict:
    """A barra de progresso de uma fila, em FOTOS — e com as cartas e as linhas
    ao lado, que é o que ele precisa de saber para ir à estante.

    A unidade é a FOTO porque é o gesto: a barra tem de dizer quantas fotos
    faltam tirar, não quantas cartas existem. As cartas e as linhas vão ao lado
    porque uma foto de 4 e uma foto de 1 não dão o mesmo trabalho.
    """
    feitas = [f for f in fotos if f["feita"]]
    falta = [f for f in fotos if not f["feita"]]
    return {
        "fotos": len(fotos), "feitas": len(feitas), "falta": len(falta),
        "cartas": sum(f["cartas"] for f in fotos),
        "linhas": sum(f["linhas"] for f in fotos),
        "cartas_feitas": sum(f["feitas_cartas"] for f in fotos),
        "perdidas": sum(f["perdidas"] for f in fotos),
        "valor": round(sum(f["valor"] for f in fotos), 2),
        "feitas_valor": round(sum(f["valor"] for f in feitas), 2),
        "falta_valor": round(sum(f["valor"] for f in falta), 2),
        "pct": round(100 * len(feitas) / len(fotos), 1) if fotos else 0.0,
    }


# ---------------------------------------------------------------------------
# ONDE ESTÁ A FOTO
# ---------------------------------------------------------------------------
# A pasta das fotos vive ao lado da BASE (`db.pasta_dados()`), como o
# `arquetipos.json` e o `data/deckboxes/`: quem corre isto com o `MTGVAULT_DB`
# a apontar para outro sítio quer as fotos lá, não na pasta do código. E fica
# FORA do Git — são imagens, e a regra do «não guardar imagens» vale aqui (a
# única excepção consciente continua a ser a reduzida da deckbox física).
PASTA = "fotos"
ANTERIORES = "anteriores"
SEM_ALVO = "sem-alvo"
EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def pasta_fotos() -> Path:
    return db.pasta_dados() / PASTA


def pasta_arquivo() -> Path:
    """`data/fotos/anteriores/` — onde as fotos de «fotos processadas» ficam."""
    return pasta_fotos() / ANTERIORES


def pasta_do_alvo(alvo: dict | None) -> Path:
    """Onde uma foto NOVA se arruma: `data/fotos/<slot>/` quando há um alvo de
    caixa, `data/fotos/venda|rl|coleccao/` nos outros tipos, e
    `data/fotos/sem-alvo/` quando não há alvo nenhum.

    *"O slot vem do alvo da revalidação, não de adivinhar."* Sem alvo não se
    inventa um deck: a foto fica em `sem-alvo/`, à vista.
    """
    if not alvo or not alvo.get("tipo"):
        return pasta_fotos() / SEM_ALVO
    if alvo["tipo"] == "caixa":
        slot = str(alvo.get("slot") or "").strip()
        return pasta_fotos() / (slot or SEM_ALVO)
    return pasta_fotos() / str(alvo["tipo"])


def _pastas_de_busca() -> list[Path]:
    """Por ordem de preferência: a pasta de TRABALHO primeiro.

    *"A pasta de trabalho ganha quando a foto existe nas duas."* Uma foto que
    ele acabou de largar em `pendentes/` é mais recente do que uma do arquivo
    com o mesmo nome, e é essa que se serve.
    """
    from . import collection                                # noqa: PLC0415
    return [collection.PENDENTES, collection.FOTOS_PROCESSADAS, pasta_fotos()]


_CACHE: dict[tuple, dict[str, Path]] = {}


def _assinatura(pastas: list[Path]) -> tuple:
    """Um carimbo das PASTAS (não dos ficheiros): o mtime de uma pasta muda
    quando um ficheiro lá entra ou sai, e por isso chega para invalidar o
    índice sem o refazer a cada chamada. O `_copias()` resolve 737 caminhos de
    uma vez — um `rglob` por caminho punha a página em minutos."""
    out = []
    for p in pastas:
        for d in ([p] + [x for x in p.rglob("*") if x.is_dir()] if p.exists() else []):
            try:
                out.append((str(d), d.stat().st_mtime_ns))
            except OSError:                                # noqa: PERF203
                pass
    return tuple(sorted(out))


def indice() -> dict[str, Path]:
    """`nome do ficheiro -> caminho`, nas pastas de busca, a de trabalho a ganhar."""
    pastas = _pastas_de_busca()
    chave = _assinatura(pastas)
    pronto = _CACHE.get(chave)
    if pronto is not None:
        return pronto
    _CACHE.clear()
    idx: dict[str, Path] = {}
    for p in reversed(pastas):            # ao contrário: a de trabalho escreve por cima
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file() and f.suffix.lower() in EXT:
                idx[f.name] = f
    _CACHE[chave] = idx
    return idx


def resolver(photo_path: str | None) -> Path | None:
    """O ficheiro de uma foto, se existir no disco — ou `None`.

    Tenta, por esta ordem: o caminho absoluto; o caminho tal e qual relativo à
    `pendentes/`, à pasta da base e à raiz do repositório (é o que o resolvedor
    de antes fazia, e é o que faz um `photo_path` de uma corrida futura
    continuar a valer); e por fim pelo **NOME**, que é a forma que os 348
    `photo_path` da base dele têm.
    """
    if not photo_path:
        return None
    from . import collection                                # noqa: PLC0415
    p = Path(str(photo_path))
    if p.is_absolute():
        return p if p.is_file() else None
    for base in (collection.PENDENTES, db.pasta_dados(), collection.ROOT):
        c = base / p
        if c.is_file():
            return c
    return indice().get(p.name)


def perdidas(photo_paths) -> set[str]:
    """Os `photo_path` que **já não têm ficheiro no disco**.

    Na base de 2026-10-01 são **33** (155 linhas da `copies`): são as únicas
    cópias que hoje não têm prova nenhuma, e por isso vão à cabeça da fila de
    revalidação. Não se inventa a foto nem se limpa o campo — o campo é a prova
    de que ela existiu.
    """
    from . import collection                                # noqa: PLC0415
    idx = indice()
    bases = (collection.PENDENTES, db.pasta_dados(), collection.ROOT)
    out = set()
    for f in {x for x in photo_paths if x}:
        p = Path(str(f))
        if p.is_absolute():
            if not p.is_file():
                out.add(f)
            continue
        if any((b / p).is_file() for b in bases):
            continue
        if p.name not in idx:
            out.add(f)
    return out


def copias_sem_foto_no_disco(con) -> dict[int, str]:
    """`copy_id -> photo_path` das cópias cuja foto se perdeu. Uma consulta e
    um índice: é o que a lista de por-revalidar e o relatório usam."""
    from . import collection                                # noqa: PLC0415
    rows = con.execute(
        f"""SELECT id, photo_path FROM copies cp
             WHERE {collection.na_estante()} AND photo_path IS NOT NULL
               AND photo_path <> ''""").fetchall()
    faltam = perdidas(r["photo_path"] for r in rows)
    return {r["id"]: r["photo_path"] for r in rows if r["photo_path"] in faltam}


# ---------------------------------------------------------------------------
# ARQUIVAR as fotos antigas — mover, NUNCA apagar
# ---------------------------------------------------------------------------
def arquivar(pendentes: str | Path | None = None,
             destino: str | Path | None = None) -> dict:
    """Move `pendentes/fotos processadas/**` para `data/fotos/anteriores/`.

    O André propôs **apagar** as fotos antigas e tirar tudo de novo. Refotografar
    é o que a campanha de 20/09 faz; apagar não se faz, e ele aceitou:

      * **98 MB não custam nada** (medido: 322 ficheiros, 96,4 MiB);
      * enquanto a campanha não acabar, as antigas são a **única prova** de 723
        das 737 linhas da `copies`;
      * o `foto_anterior` existe para a correcção (0b) ser confiável — sem a
        foto antiga no disco não há como confirmar uma correcção;
      * **33 já estavam perdidas**, e é exactamente por isso que não se apaga o
        resto.

    Não se reescreve uma única linha de `copies`: quem passa a procurar nas duas
    pastas é o `resolver`. Um ficheiro que já exista no destino **não se pisa** —
    fica onde está e vai em `ja_lá`.
    """
    from . import collection                                # noqa: PLC0415
    origem = (Path(pendentes) / "fotos processadas" if pendentes
              else collection.FOTOS_PROCESSADAS)
    alvo = Path(destino) if destino else pasta_arquivo()
    movidas, ja_la, outros = [], [], []
    if not origem.exists():
        return {"movidas": 0, "ja_la": 0, "outros": 0, "bytes": 0,
                "destino": str(alvo), "lista": [], "lista_ja_la": []}
    alvo.mkdir(parents=True, exist_ok=True)
    tam = 0
    for f in sorted(x for x in origem.rglob("*") if x.is_file()):
        if f.suffix.lower() not in EXT:
            outros.append(f.name)          # o `aplicado.csv` e companhia FICAM
            continue
        d = alvo / f.name
        if d.exists():
            ja_la.append(f.name)
            continue
        tam += f.stat().st_size
        shutil.move(str(f), str(d))
        movidas.append(f.name)
    # As pastas por mês que ficaram vazias removem-se; a `fotos processadas`
    # fica (o `aplicado.csv` vive lá e o importador escreve-lhe).
    for d in sorted((x for x in origem.rglob("*") if x.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    _CACHE.clear()
    return {"movidas": len(movidas), "ja_la": len(ja_la), "outros": len(outros),
            "bytes": tam, "destino": str(alvo), "lista": movidas,
            "lista_ja_la": ja_la}
