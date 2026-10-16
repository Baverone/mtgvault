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

E DESDE 2026-10-01, À TARDE: **A PASTA POR DECK VALE COMO ALVO.** Decisão dele,
à letra — *"o melhor é criar pasta"*. Ele quer fotografar com a app da câmara e
largar as fotos numa pasta com o nome do deck, em ``Colocar fotos da coleção
aqui\\<Nome do deck>\\``, e isso tem de ser tratado **exactamente** como se ele
tivesse carregado em «Fotografar este deck» e tirado a foto na página.

  * `mapa_pastas`/`slot_da_pasta` — o mapa pasta → slot sai do `caixas` do
    config, nunca de uma lista escrita à mão: no dia em que ele renomear um deck
    a pasta reconhecida muda sozinha, sem se tocar em código. As subpastas de
    lote (`lote1`) contam para o mesmo slot. As pastas de GRUPO que já lá
    estavam — `Premodern (geral)`, `SPML (…)`, `Coleção Pessoal`, `Vender` — não
    mapeiam para slot nenhum e ficam com o comportamento que sempre tiveram.
  * `recolher_das_pastas` — **um caminho só, e é o que já estava testado**: a
    foto MOVE-SE para a raiz de `pendentes/` com o nome
    `site-<slot>-<data>-<n>.<ext>` (`fotosite.nome_ficheiro`), que é o mesmo
    nome que o botão «Tirar fotos» escreve. Daí para a frente é tudo o caminho
    de 2026-09-21 sem uma linha nova: o `revalidacao.alvo_da_foto` prefere as
    cópias daquela caixa, o `esperadas.md` diz o que esperar, o
    `arrumar_fotos`/`pasta_do_alvo` arruma-a em `data/fotos/<slot>/`. Escrever
    um segundo caminho ao lado era deixar os dois discordarem um dia, em
    silêncio — a lição do `e_foil`, do `vistoId` e do `venda.mostrar`.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path

from . import db
from .site_shell import URL_EDICAO

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


def so_basicas(nomes) -> bool:
    """Esta foto é SÓ de terrenos básicos? — e por isso isenta do tecto de 4.

    André, 2026-10-02, à letra: *"para as básicas, nos decks, tens que permitir
    tirar foto com mais cartas e não apenas 4"*. A razão é o gesto: um deck com
    27 Snow-Covered Plains não se fotografa em sete fotos de cartas idênticas, e
    o tecto de quatro existe para cada carta ficar **à vista e avaliável** — numa
    pilha de terras iguais não há nada para distinguir entre a 5.ª e a 20.ª.

    A lista de básicas vem do **`loadout.BASICS`** e não de uma sexta cópia dela
    neste módulo (já há cinco espalhadas pelo repositório): a pergunta *"isto é
    uma básica?"* tem de ter uma resposta só, pela razão do `e_foil` e do
    `precos.sql()`. O import é tardio porque o `loadout` é pesado e o `fotos` é
    importado por quem não precisa dele.
    """
    from . import loadout                                    # noqa: PLC0415
    lista = [str(n) for n in (nomes or []) if n]
    return bool(lista) and all(n in loadout.BASICS for n in lista)


def valida(cartas: int, max_cartas: int = MAX_CARTAS, *,
           isenta: bool = False) -> bool:
    """Esta foto conta como validação? Só se trouxer 1 a `max_cartas` cartas.

    É a trava, e vale para os dois lados: a foto NOVA que traga mais do que
    quatro é recusada à entrada, e a foto ANTIGA com mais do que quatro nunca
    conta — as cópias dela continuam por revalidar.

    **`isenta` abre a excepção dos terrenos básicos** (02/10/2026): aí não há
    tecto, só a exigência de trazer pelo menos uma carta. Quem responde se uma
    foto é isenta é o `so_basicas`, para a pergunta viver num sítio só.
    """
    n = int(cartas or 0)
    if n <= 0:
        return False
    return True if isenta else n <= max_cartas


def motivo_demasiadas(cartas: int, max_cartas: int = MAX_CARTAS) -> str:
    return (f"a foto tem {cartas} cartas — uma foto valida no máximo "
            f"{max_cartas}. Volta a fotografar em grupos de até {max_cartas}, "
            "agrupados por tipo de carta, com cada carta à vista. "
            "(Os terrenos básicos são a excepção: podes pôr quantos quiseres "
            "na mesma foto, desde que seja só básicas.)")


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
            if q > max_cartas and so_basicas([l.get("nm")]):
                # AS BÁSICAS NÃO SE PARTEM (André, 2026-10-02): *"para as
                # básicas, nos decks, tens que permitir tirar foto com mais
                # cartas e não apenas 4"*. As 27 Snow-Covered Plains são UMA
                # foto, não sete fotos de cartas idênticas. Vai numa foto só
                # dela (não se mistura com outras cartas, senão a foto deixava
                # de ser «só básicas» e o tecto voltava a valer) e marcada
                # `isenta`, para a página poder dizer porque é que esta tem 27.
                if atual:
                    out.append(_foto(out, atual, tipo, prefixo))
                    atual, cartas = [], 0
                out.append(_foto(out, [dict(l, q=q)], tipo, prefixo,
                                 isenta=True))
                continue
            if q > max_cartas:
                # A linha que SOZINHA passa do tecto e NÃO é básica: fecha o que
                # estava a juntar e enche fotos inteiras só dela. É a única forma
                # de respeitar as 4 cartas, e por isso a foto di-lo (`partida`)
                # em vez de o esconder.
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
          partida: bool = False, isenta: bool = False) -> dict:
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
        # ISENTA do tecto de 4: só os terrenos básicos (02/10/2026). Vai no
        # payload para a página poder explicar porque é que esta foto tem 27
        # cartas em vez de quatro — uma excepção calada parece um defeito.
        "isenta": isenta,
    }


def texto_do_plano(nome: str, slot: str, fotos_: list[dict], *,
                   conversao: bool = False, nota: str = "") -> str:
    """O plano de fotos de um deck em TEXTO, para ele ler à frente da estante.

    Sai das MESMAS fotos que a página desenha (`fases.fila_decks`) — não é uma
    segunda contagem: a pasta e a página têm de dizer o mesmo número.

    A instrução mudou DUAS vezes no mesmo dia, e a segunda é a dele: de manhã
    este ficheiro mandava largar as fotos nesta pasta e **nada no vault a
    processava** (ficavam lá para sempre); corrigiu-se para `pendentes\\`; e à
    tarde ele decidiu *"o melhor é criar pasta"*. Agora a pasta **é** o alvo —
    ver `recolher_das_pastas` —, e é isso que aqui está escrito.
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
    out += ["ONDE LARGAR AS FOTOS: NA PASTA DA CARTA, DENTRO DESTA.",
            f"  O vault reconhece a pasta como este deck (alvo: {slot}) e trata",
            "  as fotos como se as tivesses tirado na pagina. Nao precisas de",
            "  fixar alvo nenhum.",
            "  A foto e MOVIDA para pendentes\\, lida, e arrumada na MESMA pasta",
            "  dentro de «Decks Processados\\». Quando entra, a pasta da carta",
            "  AQUI e APAGADA: o que fica em «Decks Por Processar» e o que falta.",
            "",
            "A OUTRA PORTA: " + URL_EDICAO,
            "  botao «Tirar fotos» (abre a camara do telemovel) -- ai nao ha",
            "  pasta nenhuma, a foto guarda-se sozinha.",
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


def pasta_do_deck(nome: str, raiz: Path | str | None = None) -> Path:
    """A pasta de um deck em `Colocar fotos da coleção aqui\\`, nas duas formas
    (com `/` e com ` - `). A que EXISTE ganha; senão devolve a forma com o nome
    tal e qual, para quem chama poder dizer «não há pasta»."""
    base = pasta_novas(raiz)
    for n in (nome, nome_de_pasta(nome)):
        if (base / n).is_dir():
            return base / n
    return base / nome


_PLANO = "_plano.txt"


def garantir_pastas(res: dict, raiz: Path | str | None = None) -> list[str]:
    """Uma pasta por DECK do config, criada se faltar (2026-10-02).

    Medido no dia em que ele ia começar a fotografar: das 17 caixas, **7 não
    tinham pasta** (Affinity (Luffy), Elves, Modern — Affinity, Bant Airbend,
    Engineer Welder Cam, Aluren, Artifacts Blue) — umas porque o deck foi
    renomeado, outras porque são as caixas novas de 02/10. Sem pasta, o caminho
    que ele escolheu (*"o melhor é criar pasta"*) simplesmente não existe para
    esses decks, e ele não tem como saber qual é o nome que o vault espera.

    O nome sai do `caixas` do config, como o `mapa_pastas`: é a MESMA regra que
    reconhece a pasta, por isso a que se cria é, por construção, a que se
    reconhece. Cria-se a pasta e um `.gitkeep` (a estrutura viaja no Git; as
    imagens não — ver o `.gitignore`); o `_plano.txt` é o `escrever_planos` que
    o escreve a seguir. **Não se apaga nem se move nada** — a pasta de um deck
    que já não existe fica onde está e é o `escrever_planos` que lhe troca o
    texto (ver `TEXTO_ORFA`).
    """
    base = pasta_novas(raiz)
    if not base.is_dir():
        return []
    criadas = []
    # A PASTA DE UMA FAMÍLIA substitui as das caixas dela (2026-10-13): criar
    # também a pasta de cada caixa era voltar a dar-lhe quatro sítios para a
    # mesma carta, que é exactamente o que ele pediu para deixar de ter.
    em_familia = set()
    for f in familias():
        em_familia |= set(f["slots"])
        d = base / f["pasta"]
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            criadas.append(f["pasta"])
        if not (d / ".gitkeep").exists():
            (d / ".gitkeep").write_text("", encoding="ascii")
    for s in res.get("slots") or []:
        if s["slot"] in em_familia:
            continue
        nome = nome_de_pasta(s.get("nome") or s["slot"])
        d = pasta_do_deck(s.get("nome") or s["slot"], raiz)
        if d.is_dir():
            continue
        (base / nome).mkdir(parents=True, exist_ok=True)
        gk = base / nome / ".gitkeep"
        if not gk.exists():
            gk.write_text("", encoding="ascii")
        criadas.append(nome)
    return criadas


def _pastas_do_slot(slot: str, nome: str, cfg: dict | None = None,
                    raiz: Path | str | None = None) -> list[Path]:
    """TODAS as pastas que o `mapa_pastas` manda para este slot, a do nome de
    hoje à frente.

    São normalmente uma; são duas quando o deck foi renomeado e o nome antigo é
    o próprio `slot` — o `Standard\\` do slot `standard`, que hoje se chama «Bant
    Airbend». Essa continua a valer como alvo (o mapa indexa o slot), e por isso
    o plano dela também tem de estar certo: não é órfã, é a mesma caixa por outro
    nome.
    """
    base = pasta_novas(raiz)
    if not base.is_dir():
        return []
    mapa = mapa_pastas(cfg)
    primeira = pasta_do_deck(nome, raiz)
    out = [primeira] if primeira.is_dir() else []
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        if d.name.startswith("_") or d in out:
            continue
        if mapa.get(_norm(d.name)) == slot:
            out.append(d)
    return out


TEXTO_ORFA = (
    "ESTA PASTA JA NAO E UM DECK\n"
    "===========================\n\n"
    "O deck que tinha este nome foi renomeado ou dissolvido, por isso o vault\n"
    "JA NAO RECONHECE esta pasta: uma foto largada aqui fica aqui e nao e\n"
    "catalogada.\n\n"
    "Larga as fotos na pasta com o nome ACTUAL do deck (estao todas em\n"
    "«Decks Por Processar\\», uma por deck), ou usa o botao\n"
    "«Tirar fotos» no modo de edicao.\n\n"
    "Nada se apagou. Podes apagar esta pasta a mao quando quiseres.\n")


def escrever_planos(con, res: dict, cfg: dict | None = None,
                    raiz: Path | str | None = None) -> dict:
    """Reescreve o `_plano.txt` de cada pasta de deck, das MESMAS fotos que a
    página desenha (`fases.fila_decks`).

    Chamam-no o `cli fotos plano` e o passo `fotos-plano` do `daily` — o segundo
    é o que faz o ficheiro **nunca ficar velho** (ordem dele). Por isso o motor
    está aqui e não no CLI: a pasta e a página têm de dizer o mesmo número, e
    duas escritas do mesmo ficheiro divergiam no dia em que uma mudasse.

    **Só escreve onde a pasta JÁ existe** — não se criam pastas por iniciativa
    própria —, e a pasta de um deck sem nada na caixa, se já tiver um
    `_plano.txt`, fica com a nota a dizer que não há nada para fotografar: um
    plano que promete fotos de um deck vazio é um ficheiro a mentir.
    """
    from . import fases                                      # noqa: PLC0415
    f2 = fases.fila_decks(con, res, cfg)
    out: dict = {"escritos": [], "sem_pasta": [], "vazios": [], "orfas": [],
                 "criadas": garantir_pastas(res, raiz),
                 "fotos": f2["barra"]["fotos"], "cartas": f2["barra"]["cartas"]}
    # As pastas de CARTA dentro de cada deck (2026-10-13): é aqui, todas as
    # noites, que a pasta de uma carta volta quando precisa de foto outra vez.
    out["cartas_pastas"] = sincronizar_pastas_de_cartas(con, res, cfg, raiz)
    out["contas_pastas"] = contas_das_pastas(res, cfg, raiz)
    com_fila = set()
    # O plano de uma FAMÍLIA é o das caixas dela, um a seguir ao outro, na
    # pasta comum (2026-10-13) — escrito do MESMO `fila_decks`, para a pasta e
    # a página continuarem a dizer o mesmo número.
    fams = familias(cfg)
    fam_de = {s: f["id"] for f in fams for s in f["slots"]}
    fam_txt: dict[str, list[str]] = {f["id"]: [] for f in fams}
    for f in f2["filas"]:
        if f["slot"] in fam_de:
            com_fila.add(f["nome"])
            fam_txt[fam_de[f["slot"]]].append(texto_do_plano(
                f["nome"], f["slot"], f["fotos"],
                conversao=f["conversao"], nota=f["nota"]))
            out["escritos"].append({"nome": f["nome"], "slot": f["slot"],
                                    "fotos": f["barra"]["fotos"],
                                    "cartas": f["barra"]["cartas"],
                                    "familia": fam_de[f["slot"]]})
            continue
        pastas = _pastas_do_slot(f["slot"], f["nome"], cfg, raiz)
        if not pastas:
            out["sem_pasta"].append(f["nome"])
            continue
        com_fila.add(f["nome"])
        texto = texto_do_plano(f["nome"], f["slot"], f["fotos"],
                               conversao=f["conversao"], nota=f["nota"])
        for d in pastas:
            (d / _PLANO).write_text(texto, encoding="utf-8")
        out["escritos"].append({"nome": f["nome"], "slot": f["slot"],
                                "fotos": f["barra"]["fotos"],
                                "cartas": f["barra"]["cartas"],
                                "ficheiro": str(pastas[0] / _PLANO)})
    for s in res.get("slots") or []:
        nome = s.get("nome") or s["slot"]
        if nome in com_fila:
            continue
        if s["slot"] in fam_de:
            fam_txt[fam_de[s["slot"]]].append(texto_sem_cartas(nome, s["slot"]))
            out["vazios"].append(nome)
            continue
        # Escreve-se em TODAS as pastas que apontam para este slot, e não só na
        # que tem o nome de hoje. Duas razões, as duas medidas a 02/10:
        #   * a pasta ACABADA DE CRIAR não tinha `_plano.txt` nenhum — a guarda
        #     era `not (d/_PLANO).is_file(): continue`, e as seis caixas novas
        #     ficavam com um `.gitkeep` e mais nada, sem uma linha a dizer que a
        #     pasta vale como alvo;
        #   * a pasta com o nome ANTIGO do deck, quando esse nome é o próprio
        #     `slot` (o `Standard\` do slot `standard`, hoje «Bant Airbend»),
        #     continua a valer como alvo pelo `mapa_pastas` — por isso não é
        #     órfã — mas o `pasta_do_deck` não a encontra, e ficava com o plano
        #     congelado do dia anterior ao rename.
        for d in _pastas_do_slot(s["slot"], nome, cfg, raiz):
            (d / _PLANO).write_text(texto_sem_cartas(nome, s["slot"]),
                                    encoding="utf-8")
        out["vazios"].append(nome)
    # AS PASTAS ORFAS: um `_plano.txt` NOSSO a mentir é pior do que nenhum.
    # Uma pasta cujo deck foi renomeado ou dissolvido (medido a 02/10:
    # `Elves - Survival`, `Pauper (Luffy)`, `Jeskai Control`, `Legacy`) ficava
    # com o plano de 01/10 lá dentro a dizer «LARGA AS FOTOS NESTA PASTA» — e o
    # vault já não a reconhece, por isso a foto fica lá, calada. Troca-se o
    # TEXTO; não se apaga nem se move a pasta (a regra dele de 09/09), e só se
    # toca onde já existe um `_plano.txt`, que é um ficheiro escrito por nós.
    base = pasta_novas(raiz)
    for f in fams:
        d = base / f["pasta"]
        if d.is_dir():
            (d / _PLANO).write_text(texto_familia(f, fam_txt[f["id"]]),
                                    encoding="utf-8")
            out.setdefault("familias", []).append(f["pasta"])
    if base.is_dir():
        mapa = mapa_pastas(cfg)
        conhecidas = ({_norm(g) for g in PASTAS_DE_GRUPO}
                      | {_norm(g) for g in PASTAS_FORA_DOS_DECKS}
                      | {_norm(f["pasta"]) for f in fams})
        for d in sorted(x for x in base.iterdir() if x.is_dir()):
            if d.name.startswith("_") or _norm(d.name) in conhecidas:
                continue
            if _norm(d.name) in mapa or not (d / _PLANO).is_file():
                continue
            if (d / _PLANO).read_text(encoding="utf-8") != TEXTO_ORFA:
                (d / _PLANO).write_text(TEXTO_ORFA, encoding="utf-8")
            out["orfas"].append(d.name)
    return out


# AS QUATRO REGRAS DA FOTOGRAFIA (André, 2026-10-13, à letra). Vai no
# `_plano.txt` de cada pasta (é o que ele lê à frente da estante) e no LEIA-ME
# das duas árvores — o texto num sítio só, para os dois não se desencontrarem.
TEXTO_N_E_O_QUE_PEDE = (
    "O (N) DO NOME DA PASTA E O QUE O DECK PEDE, NAO O QUE TENS (13/10/2026).\n"
    "Fotografas o que TENS, ate ao playset -- as tuas palavras:\n"
    "  \"vou sempre fotografar as cartas ate ao playset\"\n"
    "  \"caso peca apenas 2x e eu tenho playset, eu vou fotografar playset\"\n"
    "  \"caso peca playset e eu so fotografar 2x, e porque so tenho 2x\"\n"
    "  \"caso varios decks pecam a mesma carta, e eu coloque em diferentes\n"
    "   pastas a mesma carta, e porque tenho multiplos da carta\"\n"
    "Pasta (2) e foto com 4 -> entram 4: o deck leva 2, as outras 2 ficam sem\n"
    "deck. Pasta (4) e foto com 2 -> entram 2 e o deck fica a dever 2. A pasta\n"
    "apaga-se quando a foto ENTRA, nao quando a conta bate com o (N). A mesma\n"
    "carta em duas pastas de deck sao copias diferentes, nunca a mesma.\n")


def texto_familia(fam: dict, planos: list[str]) -> str:
    from . import loadout                                    # noqa: PLC0415
    nomes = loadout.nomes_das_caixas()
    caixas_ = ", ".join(nomes.get(s) or s for s in fam["slots"])
    cab = (f"PASTA DA FAMILIA -- {fam['pasta']}\nfamilia: {fam['id']}\n"
           f"caixas: {caixas_}\n\n"
           "Estes decks partilham muitas cartas, por isso as fotos vem TODAS\n"
           "para esta pasta. A foto prova a carta; QUAL das caixas fica com ela\n"
           "decide-o a alocacao (o vault), nunca a pasta -- uma carta que serve\n"
           "duas caixas nao e tirada de uma para ir para a outra por causa da\n"
           "foto. As subpastas por carta sao so para arrumar: contam todas\n"
           "para a familia. Nada se apaga.\n\n"
           + TEXTO_N_E_O_QUE_PEDE + "\n"
           f"A outra porta: {URL_EDICAO}\n")
    return cab + "".join("\n" + "=" * 60 + "\n" + p for p in planos)


def texto_sem_cartas(nome: str, slot: str) -> str:
    return (f"PLANO DE FOTOS -- {nome}\nslot: {slot}\n\n"
            "O vault ainda nao tem cartas registadas neste deck (a colecao foi\n"
            "esvaziada a 13/10/2026 e reconstroi-se pelas fotos).\n\n"
            "O QUE FOTOGRAFAR: cada subpasta «<carta> (N)» desta pasta e uma\n"
            "carta do deck que ainda nao tem foto. Larga a foto da carta na\n"
            "pasta dela. Quando a foto entrar, a pasta da carta e APAGADA e a\n"
            "foto vai para a mesma pasta em «Decks Processados\\». O que ficar\n"
            "aqui e exactamente o que falta. Se a foto parar (uma linha nao\n"
            "entrou), volta para a pasta da carta com um «_porque_parou.txt».\n\n"
            + TEXTO_N_E_O_QUE_PEDE + "\n"
            f"O vault reconhece a pasta como este deck (alvo: {slot}).\n"
            f"A outra porta: {URL_EDICAO}\n")


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


def pasta_do_alvo(alvo: dict | None, raiz: Path | str | None = None) -> Path:
    """Onde se arruma uma foto que NÃO veio de uma pasta de carta (o botão
    «Tirar fotos» da página, ou uma foto largada à mão em `pendentes/`):
    `Decks Processados/<pasta do deck>/` — a MESMA pasta que o deck tem em
    «Por Processar», para as duas árvores se lerem lado a lado.

    Desde 2026-10-13 (era `data/fotos/<slot>/`). Uma caixa de uma FAMÍLIA vai
    para a pasta da família (é lá que ele larga as fotos dela); a colecção vai
    para `Extras (fora dos decks)`; a venda e a RL para `venda`/`rl`; e sem alvo
    para `sem-alvo/`, à vista. *"O slot vem do alvo, não de adivinhar."*
    """
    base = pasta_processados(raiz)
    if not alvo or not alvo.get("tipo"):
        return base / SEM_ALVO
    if alvo["tipo"] == "caixa":
        slot = str(alvo.get("slot") or "").strip()
        return base / (nome_da_pasta_do_slot(slot) if slot else SEM_ALVO)
    if alvo["tipo"] == ALVO_FAMILIA:
        f = familia(str(alvo.get("familia") or "").strip() or None)
        return base / (f["pasta"] if f else SEM_ALVO)
    if alvo["tipo"] == ALVO_FORA_DOS_DECKS:
        return base / PASTAS_FORA_DOS_DECKS[0]
    return base / str(alvo["tipo"])


def nome_da_pasta_do_slot(slot: str, cfg: dict | None = None) -> str:
    """O nome da pasta de um deck nas duas árvores: a da família, se a caixa
    pertencer a uma, senão o nome da caixa como pasta (`nome_de_pasta`). É a
    mesma regra do `garantir_pastas`, por isso a pasta onde a foto processada
    vai parar tem o nome da pasta onde ele a largou."""
    from . import caixas                                     # noqa: PLC0415
    f = familia_do_slot(slot, cfg)
    if f:
        return f["pasta"]
    nome = next((s.get("nome") for s in caixas.slots(cfg)
                 if s.get("slot") == slot), None)
    return nome_de_pasta(nome or slot)


def _pastas_de_busca() -> list[Path]:
    """Por ordem de preferência: a pasta de TRABALHO primeiro.

    *"A pasta de trabalho ganha quando a foto existe nas duas."* Uma foto que
    ele acabou de largar em `pendentes/` é mais recente do que uma do arquivo
    com o mesmo nome, e é essa que se serve.
    """
    from . import collection                                # noqa: PLC0415
    return [collection.PENDENTES, collection.FOTOS_PROCESSADAS, pasta_fotos(),
            pasta_processados()]


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


# ---------------------------------------------------------------------------
# A MESMA FOTO NÃO É PROVA DE DUAS CARTAS (2026-10-02)
# ---------------------------------------------------------------------------
# Medido no ensaio de ponta a ponta, com o fluxo das 02:30 a sério: uma foto com
# quatro cartas em que UMA linha não fecha (o Claude não conseguiu fixar a
# edição) **fica em `pendentes/`** — é a regra do `arrumar_fotos`, e está certa:
# «arrumá-la escondia trabalho por fazer». Só que a corrida seguinte volta a ler
# a MESMA foto, com o MESMO nome, e as três linhas que já tinham entrado voltam a
# entrar: a cópia já está validada, por isso o passo (0) não a apanha, já tem
# `photo_path`, por isso o (iii) também não — e cai no (iv), que CRIA uma cópia
# nova. Medido: duas linhas da `copies` com o mesmo `photo_path`, e **uma por
# noite** enquanto a linha falhada não fosse resolvida.
#
# Numa campanha de ~500 fotos isto não é um caso de bordo, é a regra: basta uma
# carta cuja edição não se consiga fixar para a colecção inflacionar sozinha,
# sem um único erro — o padrão do `event_tier` sobre o inventário dele.
#
# A trava é a identidade da FOTO, e não a campanha: um ficheiro de foto não pode
# ser a prova de duas cartas físicas. É a mesma razão por que a foto com mais de
# quatro cartas é recusada em vez de seguir para o (iv).
def consumidas(con) -> dict[str, set[tuple]]:
    """`nome do ficheiro -> {impressões de que essa foto já é prova}`.

    Uma consulta, lida UMA vez por importação (não por linha). A chave é o NOME
    do ficheiro porque é o que sobrevive ao `arrumar_fotos`, que reescreve o
    `photo_path` com a pasta do deck à frente.
    """
    out: dict[str, set[tuple]] = {}
    for r in con.execute(
            """SELECT cp.photo_path, c.name, c.set_code, c.collector_number,
                      cp.language, cp.finish
                 FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE cp.photo_path IS NOT NULL AND cp.photo_path <> ''"""):
        nome = Path(str(r["photo_path"])).name.casefold()
        if nome:
            out.setdefault(nome, set()).add(_chave_impressao(
                r["name"], r["set_code"], r["collector_number"],
                r["language"], r["finish"]))
    return out


def _chave_impressao(nm, set_code, num, lang, finish) -> tuple:
    return (str(nm or "").casefold(), str(set_code or "").casefold(),
            str(num or ""), str(lang or "").casefold(),
            str(finish or "").casefold())


def ja_e_prova(indice: dict[str, set[tuple]], photo_path: str | None,
               nm: str, set_code: str | None, num: str | None,
               lang: str, finish: str) -> bool:
    """Esta foto já é a prova desta impressão?

    O NÚMERO de coleccionador só conta quando os DOIS lados o têm: o guia manda
    escrever a edição, mas o número pode faltar — e exigi-lo deixava passar
    exactamente a repetição que isto trava.
    """
    if not photo_path:
        return False
    tem = indice.get(Path(str(photo_path)).name.casefold())
    if not tem:
        return False
    alvo = _chave_impressao(nm, set_code, num, lang, finish)
    for k in tem:
        if (k[0], k[1], k[3], k[4]) != (alvo[0], alvo[1], alvo[3], alvo[4]):
            continue
        if not k[2] or not alvo[2] or k[2] == alvo[2]:
            return True
    return False


MOTIVO_REPETIDA = ("esta foto já é a prova desta carta na base — não se cria "
                   "uma segunda cópia da mesma foto. Se tens mesmo outra cópia "
                   "desta carta, fotografa-a à parte.")


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


# ---------------------------------------------------------------------------
# A PASTA POR DECK VALE COMO ALVO (André, 2026-10-01, à letra: «o melhor é
# criar pasta»)
# ---------------------------------------------------------------------------
PASTA_NOVAS = "Decks Por Processar"
# AS DUAS ÁRVORES (André, 2026-10-13, à letra: *"o melhor e esvaziar tudo!"* e
# *"nao podes esquecer-te de apagar as pastas de onde as fotos foram movidas,
# para me dar a entender que ja nao as estas a pedir"*). Ele larga as fotos em
# `Decks Por Processar\<deck>\<carta (N)>\`; o `arrumar_fotos` MOVE-AS para a
# MESMA pasta relativa dentro de `Decks Processados\`, e é lá que o
# `photo_path` da base aponta. Substitui o `data/fotos/<slot>/` de 01/10: a foto
# fica num sítio só, ao lado da árvore onde ele a largou, e não se duplica.
# Quando uma foto é processada com sucesso, a pasta da carta em «Por Processar»
# é APAGADA (só se estiver vazia — ver `apagar_pasta_feita`): o que resta lá é
# exactamente o que falta fotografar.
PASTA_PROCESSADAS = "Decks Processados"
# O nome antigo da pasta-mãe. Já não se lê; mas uma foto largada lá por hábito
# (ou numa cópia antiga da pasta) NÃO pode ficar calada — o `fotos_nas_pastas`
# devolve-a em `ignorados` com a frase que a tarefa das 02:30 trata como ERRO.
PASTA_NOVAS_ANTIGA = "Colocar fotos da coleção aqui"
# As pastas de GRUPO que já lá estavam. Não mapeiam para slot nenhum e ficam
# com o comportamento de sempre — ninguém as processa automaticamente. Estão
# aqui NOMEADAS só para a recolha poder dizer *porquê* é que não lhes mexe, em
# vez de as tratar como uma pasta desconhecida.
PASTAS_DE_GRUPO = ("Premodern (geral)", "SPML (Standard Pioneer Modern Legacy)",
                   "Coleção Pessoal", "Vender")
# A PASTA DO QUE NÃO ESTÁ EM DECK NENHUM (André, 2026-10-02). Ele criou
# `Extras (fora dos decks)\` para fotografar o resto da colecção — as cartas que
# nenhuma caixa usa — e a pasta não estava ligada a nada: as fotos ficavam lá
# para sempre e a tarefa das 02:30 dizia «sem fotos novas», VERDE. Era o padrão
# do `event_tier` no sítio mais caro possível, porque o que se perde são dias de
# trabalho dele.
#
# Não mapeia para um SLOT — mapeia para o alvo **`coleccao`** da revalidação, que
# já existia desde 2026-09-21 (`fotosite.TIPOS`) e é exactamente isto: *"estou a
# fotografar a colecção, não um deck"*. Daí para a frente é o caminho de sempre,
# sem uma linha nova: a foto chama-se `site-colecao-<data>-<n>.<ext>`, o
# `revalidacao.alvo_da_foto` prefere as cópias que não estão em caixa nenhuma, e
# o `arrumar_fotos` arruma-a em `data/fotos/coleccao/`.
#
# As QUATRO de cima **não** se ligaram, e é uma decisão: `Vender`,
# `Premodern (geral)`, `SPML (…)` e `Coleção Pessoal` já tinham um significado
# dele antes disto, e pôr-me a processá-las por iniciativa própria era mudar-lhe
# a rotina sem ele pedir. Ligar qualquer uma é acrescentar uma linha aqui.
PASTAS_FORA_DOS_DECKS = ("Extras (fora dos decks)",)
ALVO_FORA_DOS_DECKS = "coleccao"
# A PASTA DE UMA FAMÍLIA DE DECKS (André, 2026-10-13, à letra: *"os decks de
# modern partilham muitas cartas, sugeria que pegasses nos decks que partilham
# muitas cartas e criasses uma pasta para esses decks todos juntos"*).
#
# Uma pasta de deck vale como alvo de UMA caixa (`mapa_pastas`), e com a regra
# «a foto manda» (02/10) essa pasta decide o deck de forma EXCLUSIVA — o que
# estava registado noutra caixa sai. Por isso a família NÃO é um alias de uma
# caixa: ligar `Mox Opal (Modern + Legacy)` ao slot `modern` punha, no dia em
# que a foto voltasse a mandar, todas as cartas de Legacy fotografadas ali
# dentro da caixa de Modern, e tirava-as das caixas de Legacy em silêncio.
#
# A família é um ALVO PRÓPRIO (`familia`): a foto chama-se
# `site-familia-<id>-…`, prova a carta, o passo (0) da revalidação prefere as
# cópias de QUALQUER caixa da família, e a ALOCAÇÃO não se toca (é o `loadout`
# que diz qual das caixas fica com cada cópia — `confirmado.alvo_da_pasta`
# responde «não decide»). Vive em `colecao_config.json → familias_fotos`, uma
# linha por família: `{id, pasta, slots}`. Uma caixa de uma família deixa de
# ganhar pasta própria no `garantir_pastas` — a dela é a da família.
ALVO_FAMILIA = "familia"
# Quanto tempo uma foto tem de estar quieta antes de se mexer nela. Uma foto
# que ainda está a ser copiada (do telemóvel, da app do GitHub) movia-se a
# meio. O `mtg-fotos-novas` tem a sua própria regra de 2 min sobre o mtime, e o
# `shutil.move` dentro do mesmo volume PRESERVA o mtime — por isso esta espera
# curta chega: a de 2 min continua a valer do outro lado.
SOSSEGO_S = 20


def _norm(s: str) -> str:
    """O nome de uma pasta reduzido ao que se pode comparar.

    `-`, `/`, `—`, `–`, `_`, `(`, `)` e qualquer espaço passam a UM espaço, e
    tudo em minúsculas. É o que faz «Elves - Survival» (a pasta, que não pode
    ter `/`), «Elves / Survival» (o nome da caixa) e «elves survival» serem a
    mesma coisa — e «Modern — UW Oswald» não depender de ele ter escrito o
    travessão certo.
    """
    t = unicodedata.normalize("NFC", str(s or "")).casefold()
    t = re.sub(r"[-/—–_()\s]+", " ", t)
    return t.strip()


def pasta_novas(raiz: Path | str | None = None) -> Path:
    from . import fotocaixa                                  # noqa: PLC0415
    return Path(raiz or fotocaixa.RAIZ) / PASTA_NOVAS


def pasta_processados(raiz: Path | str | None = None) -> Path:
    from . import fotocaixa                                  # noqa: PLC0415
    return Path(raiz or fotocaixa.RAIZ) / PASTA_PROCESSADAS


def nome_de_pasta(nome: str) -> str:
    """O nome de uma caixa como PASTA: a «Elves / Survival» não cabe num
    caminho. Vivia escrito à mão no `cli.fotos plano`; está aqui para a escrita
    e a leitura da pasta usarem a mesma regra."""
    return str(nome or "").replace(" / ", " - ").replace("/", "-")


def mapa_pastas(cfg: dict | None = None) -> dict[str, str]:
    """`nome de pasta normalizado -> slot`, DERIVADO do `caixas` do config.

    Nunca uma lista escrita à mão: no dia em que ele renomear um deck no config,
    a pasta que o vault reconhece muda com ele. Aceita o NOME da caixa (nas duas
    formas, com `/` e com ` - `) e o próprio `slot` — o nome ganha sempre, para
    um slot não poder roubar a pasta de outra caixa.
    """
    from . import caixas                                     # noqa: PLC0415
    slots = caixas.slots(cfg)
    out: dict[str, str] = {}
    for s in slots:                        # primeiro os NOMES
        if not s.get("slot"):
            continue
        nome = s.get("nome") or s["slot"]
        for forma in (nome, nome_de_pasta(nome)):
            out.setdefault(_norm(forma), s["slot"])
    for s in slots:                        # e só depois os slots
        if s.get("slot"):
            out.setdefault(_norm(s["slot"]), s["slot"])
    return out


def familias(cfg: dict | None = None) -> list[dict]:
    """As famílias de decks com pasta comum (`familias_fotos`), já limpas:
    `[{id, pasta, slots}]`, com os `slots` reduzidos às caixas que EXISTEM.

    Uma família sem nenhuma caixa viva não entra — a pasta dela passa a ser
    desconhecida, e uma foto lá dentro diz-se (é ERRO na tarefa das 02:30),
    em vez de ir para um alvo que não aponta para caixa nenhuma.
    """
    from . import caixas, sources                            # noqa: PLC0415
    cfg = cfg if cfg is not None else sources.config()
    vivos = {s["slot"] for s in caixas.slots(cfg) if s.get("slot")}
    out = []
    for f in cfg.get("familias_fotos") or []:
        if not isinstance(f, dict) or not f.get("id") or not f.get("pasta"):
            continue
        slots = [s for s in (f.get("slots") or []) if s in vivos]
        if slots:
            out.append({"id": str(f["id"]), "pasta": str(f["pasta"]),
                        "slots": slots})
    return out


def familia(fid: str | None, cfg: dict | None = None) -> dict | None:
    return next((f for f in familias(cfg) if f["id"] == fid), None)


def familia_do_slot(slot: str, cfg: dict | None = None) -> dict | None:
    """A família a que esta caixa pertence (a primeira), ou `None`."""
    return next((f for f in familias(cfg) if slot in f["slots"]), None)


def slot_da_pasta(caminho: Path | str, cfg: dict | None = None) -> str | None:
    """O slot da caixa a que uma foto pertence, pela PASTA em que está — ou
    `None` (pasta de grupo, pasta desconhecida, ou foto à solta na pasta-mãe).

    A subpasta de lote conta para o mesmo slot: o que manda é a **primeira**
    pasta abaixo de `Colocar fotos da coleção aqui\\`.
    """
    partes = Path(str(caminho)).parts
    base = _norm(PASTA_NOVAS)
    i = next((k for k, p in enumerate(partes) if _norm(p) == base), None)
    resto = partes[i + 1:] if i is not None else partes
    if len(resto) < 2:
        return None                        # está na pasta-mãe: não tem deck
    return mapa_pastas(cfg).get(_norm(resto[0]))


def alvo_da_pasta(caminho: Path | str, cfg: dict | None = None,
                  mapa: dict[str, str] | None = None) -> dict | None:
    """O ALVO da revalidação a que uma foto pertence, pela PASTA em que está:

        {"tipo": "caixa",    "slot": "cedh-blue-farm"}   uma pasta de deck
        {"tipo": "coleccao", "slot": None}               `Extras (fora dos decks)`
        {"tipo": "familia", "slot": None,                a pasta de uma FAMÍLIA
         "familia": "mox-opal", "slots": [...]}          (`familias_fotos`)
        None                                             grupo/desconhecida/raiz

    É a pergunta de que a recolha precisa, e vive **num sítio só**: o
    `slot_da_pasta` responde a *"que caixa é esta pasta"* e continua a responder
    só isso (devolve `None` para os Extras, que não são caixa nenhuma). Duas
    respostas à mesma pergunta discordam um dia qualquer, em silêncio — a lição
    do `e_foil`, do `vistoId` e do `precos.sql()`.

    O `mapa` é só uma optimização de quem chama em ciclo (o `fotos_nas_pastas`
    faz esta pergunta uma vez por pasta): a REGRA continua a viver aqui, e sem
    ele calcula-se na hora.
    """
    partes = Path(str(caminho)).parts
    base = _norm(PASTA_NOVAS)
    i = next((k for k, p in enumerate(partes) if _norm(p) == base), None)
    resto = partes[i + 1:] if i is not None else partes
    if len(resto) < 2:
        return None                        # está na pasta-mãe: não tem alvo
    if _norm(resto[0]) in {_norm(p) for p in PASTAS_FORA_DOS_DECKS}:
        return {"tipo": ALVO_FORA_DOS_DECKS, "slot": None}
    for f in familias(cfg):
        if _norm(resto[0]) == _norm(f["pasta"]):
            return {"tipo": ALVO_FAMILIA, "slot": None, "familia": f["id"],
                    "slots": list(f["slots"])}
    slot = (mapa if mapa is not None else mapa_pastas(cfg)).get(_norm(resto[0]))
    return {"tipo": "caixa", "slot": slot} if slot else None


def _nome_livre(pasta: Path, tipo: str, slot: str | None,
                quando: _dt.datetime, ext: str) -> str:
    from . import fotosite                                   # noqa: PLC0415
    usados = {p.name.lower() for p in pasta.glob("*")} if pasta.is_dir() else set()
    n = 1
    while True:
        nome = fotosite.nome_ficheiro(tipo, slot, quando, n, ext)
        if nome.lower() not in usados:
            return nome
        n += 1


def fotos_nas_pastas(cfg: dict | None = None,
                     raiz: Path | str | None = None) -> list[dict]:
    """O que está hoje nas pastas por deck: `[{ficheiro, pasta, slot, mtime}]`.

    Serve a recolha e serve para a página/CLI poderem dizer o que lá está sem
    mexer em nada. As pastas que começam por `_` (o `_nomes antigos\\` que o
    supervisor criou) ficam de fora, e o `_plano.txt` também (não é imagem).
    """
    base = pasta_novas(raiz)
    out = []
    # A PASTA-MÃE ANTIGA (2026-10-13). Se ela ainda existir com fotos dentro —
    # uma cópia antiga, um atalho no telemóvel que ainda aponta para lá —,
    # nenhuma delas se processa (já não é a pasta) e TODAS se dizem.
    antiga = base.parent / PASTA_NOVAS_ANTIGA
    if antiga.is_dir():
        for f in sorted(x for x in antiga.rglob("*")
                        if x.is_file() and x.suffix.lower() in EXT):
            out.append({"ficheiro": f, "pasta": PASTA_NOVAS_ANTIGA + "/"
                        + "/".join(f.relative_to(antiga).parts[:1]),
                        "slot": None, "tipo": None, "grupo": False,
                        "arquivada": True, "antiga": True,
                        "mtime": f.stat().st_mtime})
    if not base.is_dir():
        return out
    # UMA FOTO SOLTA NA PASTA-MÃE NÃO TEM DECK — e até 13/10 nem se dizia (o
    # ciclo de baixo só olha para subpastas). Fica onde está e entra na lista.
    for f in sorted(x for x in base.iterdir()
                    if x.is_file() and x.suffix.lower() in EXT):
        out.append({"ficheiro": f, "pasta": "(pasta-mãe)", "slot": None,
                    "tipo": None, "grupo": False, "arquivada": True,
                    "solta": True, "mtime": f.stat().st_mtime})
    grupos = {_norm(g) for g in PASTAS_DE_GRUPO}
    mapa = mapa_pastas(cfg)                # uma vez, não uma por pasta
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        if d.name.startswith("_"):
            # UMA FOTO NUMA PASTA ARQUIVADA NÃO FICA CALADA (2026-10-13). O
            # `_nomes antigos\` guarda as pastas dos decks renomeados, e a 13/10
            # passou a guardar também as das caixas que entraram numa família:
            # são nomes que ele conhece de cor, e uma foto largada lá por hábito
            # ficava ali para sempre com a tarefa a dizer «sem fotos novas». Não
            # se processa (não se adivinha o deck), mas entra na lista com o
            # porquê — e a tarefa das 02:30 trata-a como uma pasta órfã.
            for f in sorted(x for x in d.rglob("*")
                            if x.is_file() and x.suffix.lower() in EXT):
                out.append({"ficheiro": f,
                            "pasta": "/".join(f.relative_to(base).parts[:2]),
                            "slot": None, "tipo": None, "grupo": False,
                            "arquivada": True, "mtime": f.stat().st_mtime})
            continue
        # O ALVO da pasta sai do `alvo_da_pasta` e NÃO de uma segunda conta aqui.
        # Escrevi as duas no mesmo dia e a docstring dizia «vive num sítio só» —
        # era falso: a produção passa toda por aqui e o `alvo_da_pasta` só era
        # chamado pelos testes. Ligar uma pasta nova mexendo na função que a
        # documentação aponta não teria efeito nenhum, e as fotos ficavam na
        # pasta, caladas. É o defeito dos `Extras` recriado.
        alvo = alvo_da_pasta(d / "x.jpg", cfg, mapa)
        for f in sorted(x for x in d.rglob("*")
                        if x.is_file() and x.suffix.lower() in EXT):
            out.append({"ficheiro": f, "pasta": d.name,
                        "slot": (alvo or {}).get("slot"),
                        "tipo": (alvo or {}).get("tipo"),
                        "familia": (alvo or {}).get("familia"),
                        "grupo": _norm(d.name) in grupos,
                        "mtime": f.stat().st_mtime})
    return out


def recolher_das_pastas(cfg: dict | None = None, *,
                        raiz: Path | str | None = None,
                        agora: float | None = None,
                        sossego_s: float = SOSSEGO_S) -> dict:
    """As fotos das pastas por DECK → raiz de `pendentes/`, com o nome do alvo.

    É a decisão dele de 2026-10-01 à tarde (*"o melhor é criar pasta"*), e
    resolve-se com **o caminho que já existia**: a foto fica a chamar-se
    `site-<slot>-<data>-<n>.<ext>`, que é o nome que o botão «Tirar fotos» da
    página escreve, e por isso o passo (0) da revalidação, o `esperadas.md` e o
    `arrumar_fotos` tratam-na exactamente como uma foto tirada na página.

    MOVE-SE, nunca se copia nem se apaga (a regra dele de 09/09): o original é
    que fica ligado à cópia, e a pasta dele fica limpa para o lote seguinte. O
    nome ORIGINAL vai no relatório — não se perde em silêncio. O `quando` do
    nome novo é o **mtime** da foto (quando ela foi tirada/copiada), e não a hora
    da recolha: é o mtime que o `mtg-fotos-novas` usa para esperar 2 min, e o
    `move` dentro do mesmo volume preserva-o.

    Uma pasta de GRUPO ou desconhecida com imagens dentro **não se toca** e
    aparece em `ignorados` com o porquê — nunca se adivinha a caixa.

    OS VERSOS (André, 2026-10-03): numa pasta de DECK as fotos vêm aos pares —
    *"põe as até 4 cartas, fotografa, VIRA-AS NO SÍTIO sem mexer na disposição,
    fotografa outra vez"*. Logo a recolha empareilha **pela ordem de captura**
    (mtime, depois nome), que é exactamente esse gesto, e o segundo de cada par
    sai com o `-v` e o MESMO `n` do primeiro. Três decisões que a tornam segura:

    * **o grupo é a PASTA onde o ficheiro está** (uma subpasta `lote1` empareilha
      sozinha): um lote é uma sessão, e misturar duas sessões desalinhava as duas;
    * **se UMA foto do grupo ainda está no sossego, o grupo INTEIRO espera.**
      Emparelhar metade de um lote que ainda está a ser copiado trocava os pares
      todos a partir do ficheiro que faltava;
    * **o nome é uma hipótese, e o leitor confere.** Todos os versos de Magic são
      iguais, por isso «isto é um verso?» é a pergunta mais fiável que se lhe
      pode fazer; se a leitura discordar do nome, o par não se usa e diz-se
      (`collection`/`estado`). Nunca se grava um escalão sobre um emparelhamento
      que não bateu — e, se um `-v` trouxer cartas, as cartas ganham.

    Os `Extras (fora dos decks)` **não emparelham**: ali é frente só (decisão
    dele), porque no momento em que os fotografa ainda não sabe o que vai guardar
    nem o que vai vender. Quem precisa de verso fora dos decks sai depois na LISTA
    CURTA (`estado.lista_curta`), uma cópia de cada vez.
    """
    from . import fotosite                                   # noqa: PLC0415
    agora = time.time() if agora is None else agora
    pend = fotosite.pasta_pendentes(raiz)
    out: dict = {"recolhidas": [], "ignorados": [], "a_chegar": [],
                 "pastas": 0, "destino": str(pend), "pares": 0, "sem_verso": []}
    itens = fotos_nas_pastas(cfg, raiz)
    if not itens:
        return out
    out["pastas"] = len({i["pasta"] for i in itens})
    pend.mkdir(parents=True, exist_ok=True)
    # Por PASTA FÍSICA (a subpasta de lote conta), pela ordem de captura.
    grupos: dict[Path, list[dict]] = {}
    for it in itens:
        f = it["ficheiro"]
        if not it.get("tipo"):
            if it.get("antiga"):
                porque = (f"está na pasta antiga «{PASTA_NOVAS_ANTIGA}», que já "
                          "não se lê — não é o nome de nenhuma caixa do config; "
                          f"move a foto para «{PASTA_NOVAS}\\<deck>\\<carta>»")
            elif it.get("solta"):
                porque = ("está solta na pasta-mãe, fora de qualquer deck — não "
                          "é o nome de nenhuma caixa do config; move-a para a "
                          "pasta do deck (e da carta)")
            elif it.get("arquivada"):
                porque = (f"{it['pasta']!r} é uma pasta ARQUIVADA, não é o nome de "
                          "nenhuma caixa do config — move a foto para a pasta do "
                          "deck (ou da família) com o nome actual")
            elif it["grupo"]:
                porque = ("é uma pasta de grupo — ninguém a processa "
                          "automaticamente, como sempre")
            else:
                porque = (f"{it['pasta']!r} não é o nome de nenhuma caixa do "
                          "config (não se adivinha o deck)")
            out["ignorados"].append({"ficheiro": f.name, "pasta": it["pasta"],
                                     "porque": porque})
            continue
        grupos.setdefault(f.parent, []).append(it)
    base = pasta_novas(raiz)
    origens = ler_origens(pend)
    for pasta, lote in sorted(grupos.items()):
        # UMA FOTO QUE JÁ PAROU NÃO SE RELÊ TODAS AS NOITES (2026-10-13). Quando
        # uma linha não entra, o `arrumar_fotos` devolve a foto à pasta da carta
        # com um `_porque_parou.txt` — e a recolha seguinte apanhava-a outra
        # vez e pagava a mesma leitura para dar o mesmo motivo, para sempre. As
        # fotos mais VELHAS do que o motivo ficam; uma foto nova que ele lá
        # largue (mais recente) segue, e apagar o ficheiro do motivo é o «tenta
        # outra vez». Ficam DITAS em `paradas`, nunca caladas.
        marca = pasta / MOTIVO_PAROU
        if marca.is_file():
            t = marca.stat().st_mtime
            presas = [i for i in lote if i["mtime"] <= t]
            if presas:
                motivo = marca.read_text(encoding="utf-8", errors="replace")
                out.setdefault("paradas", []).extend(
                    {"ficheiro": i["ficheiro"].name, "pasta": i["pasta"],
                     "porque": motivo.strip().splitlines()[0] if motivo.strip()
                     else "parou na leitura anterior"} for i in presas)
            lote = [i for i in lote if i["mtime"] > t]
            if not lote:
                continue
        lote.sort(key=lambda i: (i["mtime"], i["ficheiro"].name))
        novas = [i for i in lote if agora - i["mtime"] < sossego_s]
        # A família são cartas de DECK (os versos contam), por isso emparelha
        # como uma pasta de caixa; só os Extras ficam de frente só.
        empareilha = lote[0]["tipo"] in ("caixa", ALVO_FAMILIA)
        if novas and empareilha:
            # O grupo inteiro espera: emparelhar com um ficheiro a meio da cópia
            # desalinhava todos os pares a partir dele.
            out["a_chegar"] += [{"ficheiro": i["ficheiro"].name,
                                 "pasta": i["pasta"]} for i in lote]
            continue
        for k, it in enumerate(lote):
            f = it["ficheiro"]
            if not empareilha and agora - it["mtime"] < sossego_s:
                out["a_chegar"].append({"ficheiro": f.name, "pasta": it["pasta"]})
                continue
            quando = _dt.datetime.fromtimestamp(it["mtime"]).replace(microsecond=0)
            ext = f.suffix.lstrip(".").lower()
            verso = bool(empareilha and k % 2)
            if verso:
                nome = fotosite.nome_do_verso(out["recolhidas"][-1]["para"])
                # A frente saiu com outra extensão (JPEG + HEIC no mesmo par):
                # o radical é o mesmo, só a extensão muda.
                nome = str(Path(nome).with_suffix("." + ext))
            elif (fotosite.origem(f.name) and not fotosite.e_verso(f.name)
                  and not (pend / f.name).exists()):
                # Uma foto que JÁ tem nome de site é uma que voltou (parou numa
                # leitura anterior e foi devolvida à pasta da carta). Mantém o
                # nome: é pelo NOME que o `ja_e_prova` reconhece as linhas que
                # já tinham entrado — com um nome novo eram criadas outra vez.
                nome = f.name
            else:
                nome = _nome_livre(pend, it["tipo"],
                                   it.get("familia") if it["tipo"] == ALVO_FAMILIA
                                   else it["slot"], quando, ext)
            shutil.move(str(f), str(pend / nome))
            # DE ONDE VEIO (2026-10-13): o `arrumar_fotos` precisa disto para a
            # pôr na MESMA pasta em «Decks Processados» e para apagar a pasta
            # da carta em «Por Processar» quando ela entrar — ou para a devolver
            # lá se uma linha parar. O nome novo não guarda a carta, por isso
            # guarda-se aqui.
            rel = f.parent.relative_to(base).as_posix()
            origens[nome] = {"rel": rel, "de": f.name,
                             "em": _dt.datetime.now().replace(
                                 microsecond=0).isoformat(sep=" ")}
            out["recolhidas"].append({"de": f.name, "pasta": it["pasta"],
                                      "slot": it["slot"], "tipo": it["tipo"],
                                      "para": nome, "verso": verso})
            if verso:
                out["pares"] += 1
        if empareilha and len(lote) % 2:
            # O último ficou sem verso. Não é um erro — pode ser mesmo o último
            # par ainda a meio —, mas tem de ficar DITO: sem verso não há escalão.
            out["sem_verso"].append({"ficheiro": out["recolhidas"][-1]["para"],
                                     "pasta": lote[-1]["pasta"],
                                     "porque": "o lote tem um número ímpar de "
                                               "fotos — esta ficou sem verso"})
    if out["recolhidas"]:
        gravar_origens(pend, origens)
        _CACHE.clear()
    return out


# ---------------------------------------------------------------------------
# AS DUAS ÁRVORES: DE ONDE VEIO CADA FOTO, E O APAGAR DAS PASTAS FEITAS
# (André, 2026-10-13)
# ---------------------------------------------------------------------------
ORIGENS = "_origens.json"
MOTIVO_PAROU = "_porque_parou.txt"
# O que pode estar numa pasta de carta sem a impedir de ser apagada: os nossos
# ficheiros e o lixo que o Windows/macOS deixam. TUDO o resto — e, acima de
# tudo, qualquer imagem — faz a pasta FICAR.
LIXO_PERMITIDO = {".gitkeep", MOTIVO_PAROU.lower(), "desktop.ini", "thumbs.db",
                  ".ds_store"}


def ler_origens(pend: Path | str) -> dict:
    """`pendentes/_origens.json`: `nome em pendentes -> {rel, de, em}`, onde
    `rel` é a pasta (relativa a «Decks Por Processar») de onde a foto saiu."""
    p = Path(pend) / ORIGENS
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def gravar_origens(pend: Path | str, d: dict) -> None:
    p = Path(pend) / ORIGENS
    if not d:
        p.unlink(missing_ok=True)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, p)


def tem_imagens(pasta: Path) -> bool:
    return pasta.is_dir() and any(
        x.is_file() and x.suffix.lower() in EXT for x in pasta.rglob("*"))


def apagar_pasta_feita(pasta: Path | str, base: Path | str) -> bool:
    """Apaga a pasta de UMA CARTA em «Decks Por Processar» — e só se estiver
    vazia. Devolve se apagou.

    É a única função que apaga uma pasta de fotos, e as guardas são todas
    precisas: (1) tem de ser exactamente `<base>/<deck>/<carta>` — nunca a
    pasta-mãe, nunca a pasta de um deck, nunca uma subpasta mais funda; (2)
    **NUNCA com uma imagem lá dentro**, a qualquer profundidade, com qualquer
    caixa de extensão; (3) nem com uma subpasta, nem com um ficheiro que não
    seja nosso (`LIXO_PERMITIDO`) — um ficheiro dele que não conhecemos é
    motivo para ficar, não para apagar. Tem teste que falha se uma pasta com
    imagens puder ir-se.
    """
    pasta, base = Path(pasta), Path(base)
    try:
        rel = pasta.resolve().relative_to(base.resolve())
    except (OSError, ValueError):
        return False
    if len(rel.parts) != 2 or not pasta.is_dir():
        return False
    filhos = list(pasta.iterdir())
    for x in filhos:
        if x.is_dir():
            return False
        if x.suffix.lower() in EXT or x.name.lower() not in LIXO_PERMITIDO:
            return False
    if tem_imagens(pasta):                 # redundante de propósito
        return False
    for x in filhos:
        x.unlink()
    pasta.rmdir()
    return True


RE_PASTA_CARTA = re.compile(r"^(?P<nm>.+) \((?P<q>\d+)\)$")
_SEGURO = str.maketrans({c: "-" for c in '<>:"/\\|?*'})


def nome_de_pasta_de_carta(nm: str, q: int) -> str:
    """`<carta> (N)`, com os caracteres que o Windows recusa trocados por `-`
    (a regra das 650 pastas que lá estavam a 13/10)."""
    return f"{str(nm).translate(_SEGURO)} ({int(q)})"


def precisa_por_pasta(res: dict, cfg: dict | None = None) -> dict[str, dict]:
    """`pasta do deck -> {carta: quantas}` — o que cada pasta de deck pede,
    saído das LISTAS das caixas (main + side somados por carta; numa família, o
    máximo entre as caixas dela). As caixas sem lista não pedem nada."""
    fam_de = {s: f for f in familias(cfg) for s in f["slots"]}
    out: dict[str, dict] = {}
    for s in res.get("slots") or []:
        f = fam_de.get(s["slot"])
        pasta = f["pasta"] if f else nome_de_pasta(s.get("nome") or s["slot"])
        tot: dict[str, int] = {}
        for m in list(s.get("have") or []) + list(s.get("missing") or []):
            tot[m["nm"]] = tot.get(m["nm"], 0) + int(m.get("need") or 0)
        d = out.setdefault(pasta, {})
        for nm, q in tot.items():
            if q > 0:
                d[nm] = max(d.get(nm, 0), q)
    return out


def provadas_por_pasta(con) -> dict[tuple[str, str], int]:
    """`(pasta do deck, chave da carta) -> cópias com foto lá dentro`: o que a
    BASE diz que já foi fotografado e processado em cada deck. É pela base e não
    pelo disco de propósito — a base viaja (o Release), as imagens não, e é ela
    que diz se uma cópia corrigida, vendida ou dada como não encontrada ainda
    conta."""
    from . import collection, scryfall                      # noqa: PLC0415
    pre = PASTA_PROCESSADAS + "/"
    out: dict[tuple[str, str], int] = {}
    for r in con.execute(
            f"""SELECT c.name, cp.quantity, cp.photo_path
                  FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                 WHERE {collection.jogaveis()} AND cp.photo_path LIKE ?""",
            (pre + "%",)):
        partes = str(r["photo_path"]).replace("\\", "/").split("/")
        if len(partes) < 3:
            continue
        k = (partes[1], scryfall.chave(r["name"]))
        out[k] = out.get(k, 0) + int(r["quantity"] or 0)
    return out


def carta_feita(provadas: int, pede: int) -> bool:
    """A pasta `<carta (N)>` de um deck está FEITA? Sim, desde que haja UMA
    cópia com foto daquele deck — o `pede` (o `(N)`) não entra na conta, de
    propósito (André, 2026-10-13: *"caso peça playset e eu so fotografar 2x, é
    porque só tenho 2x"*). Num sítio só, para o gerador e o teste dizerem o
    mesmo."""
    return int(provadas or 0) > 0


def sincronizar_pastas_de_cartas(con, res: dict, cfg: dict | None = None,
                                 raiz: Path | str | None = None,
                                 pendentes: Path | str | None = None) -> dict:
    """As pastas `<carta (N)>` de cada deck em «Decks Por Processar»,
    IDEMPOTENTE (André, 2026-10-13).

    * **cria** a pasta de uma carta que o deck pede e que a base ainda não tem
      fotografada naquele deck (`provadas == 0`) — é assim que a pasta VOLTA
      quando a carta precisa de foto outra vez: uma correcção que tirou a
      cópia, uma carta que entrou no deck. **Não volta por a quantidade não
      bater com o `(N)`** (2026-10-13: o `(N)` é o que o deck pede, a foto é o
      que ele tem — *"caso peça playset e eu so fotografar 2x, é porque só
      tenho 2x"*);
    * **não ressuscita** a de uma carta já provada: as provadas não se criam;
    * **apaga** a pasta (vazia!) de uma carta já provada — a que ficou por
      apagar porque a foto entrou por outro caminho (o botão da página);
    * **acerta as VAZIAS** (2026-10-16, `_acertar_vazias`): uma pasta de carta
      vazia que nenhuma lista pede apaga-se, e uma com o `(N)` velho passa ao
      de hoje — as das versões vivas que não são caixa (o Oswald, o Orzhov)
      ficam, e um nome que não lê fica.

    Nada com imagens se apaga (`apagar_pasta_feita`), nem uma pasta cuja foto
    ainda está à espera em `pendentes/` (`_origens.json`). As pastas que esta
    função não toca contam-se no `contas_das_pastas`, para a diferença entre o
    disco e o plano ficar dita.
    """
    from . import fotosite, scryfall                         # noqa: PLC0415
    base = pasta_novas(raiz)
    out = {"criadas": [], "apagadas": [], "ficam_com_fotos": [], "por_pedir": 0,
           "apagadas_fora": [], "renomeadas": []}
    if not base.is_dir():
        return out
    pend = Path(pendentes) if pendentes else fotosite.pasta_pendentes(raiz)
    em_espera = {str(v.get("rel") or "") for v in ler_origens(pend).values()}
    provadas = provadas_por_pasta(con)
    versoes = _versoes_por_pasta(res, cfg)
    for pasta, pede in sorted(precisa_por_pasta(res, cfg).items()):
        d = base / pasta
        if not d.is_dir():
            continue
        existentes: dict[str, list[tuple[Path, int]]] = {}
        for x in d.iterdir():
            m = RE_PASTA_CARTA.match(x.name) if x.is_dir() else None
            if m:
                existentes.setdefault(m["nm"].casefold(), []).append(
                    (x, int(m["q"])))
        for nm, q in sorted(pede.items()):
            seguro = str(nm).translate(_SEGURO).casefold()
            tem = provadas.get((pasta, scryfall.chave(nm)), 0)
            ja = existentes.get(seguro, [])
            # A CARTA ESTÁ FEITA QUANDO TEM FOTO NESTE DECK, SEJA QUAL FOR A
            # QUANTIDADE (André, 2026-10-13, à letra: *"caso peça playset e eu so
            # fotografar 2x, é porque só tenho 2x"*). O `(N)` é o que o deck
            # PEDE; a foto diz o que ele TEM. Comparar `tem < q` punha a pasta
            # `Mox Opal (4)` a renascer todas as noites depois de ele ter
            # fotografado as duas que tem — a pedir-lhe uma foto que não existe.
            # A falta (2) fica dita no deck, que é onde se compra; a pasta não
            # volta. Volta, sim, quando a prova cai a ZERO (uma correcção).
            if not carta_feita(tem, q):
                out["por_pedir"] += 1
                if not ja:
                    nova = d / nome_de_pasta_de_carta(nm, q)
                    nova.mkdir(parents=True, exist_ok=True)
                    out["criadas"].append(f"{pasta}/{nova.name}")
                continue
            for x, _qx in ja:
                rel = f"{pasta}/{x.name}"
                if rel in em_espera:
                    continue
                if apagar_pasta_feita(x, base):
                    out["apagadas"].append(rel)
                elif tem_imagens(x):
                    out["ficam_com_fotos"].append(rel)
        _acertar_vazias(d, pasta, pede, provadas, versoes.get(pasta, set()),
                        em_espera, base, out)
    return out


def _acertar_vazias(d: Path, pasta: str, pede: dict[str, int],
                    provadas: dict, de_versoes: set, em_espera: set,
                    base: Path, out: dict) -> None:
    """A PASTA DE CARTA VAZIA ALTERA-SE À VONTADE (André, 2026-10-16, à letra:
    *"como ainda nao fotografei nada, altera as pastas que tens que alterar"*).

    Depois do ciclo de cima, o deck fica exactamente com o que a lista de hoje
    pede: uma pasta de carta que nenhuma lista pede (nem a caixa, nem uma
    versão viva do formato) **apaga-se**; uma com o `(N)` velho dá lugar à do
    `(N)` de hoje. Sem corredor de espera — era o `_fora do plano\\` de 16/10 de
    manhã, que ele dispensou no mesmo dia.

    **Só pastas VAZIAS**: quem apaga é o `apagar_pasta_feita`, que recusa uma
    pasta com uma imagem (a qualquer profundidade), com uma subpasta ou com um
    ficheiro que não é nosso. A partir da primeira foto, essa pasta não se toca —
    é a metade da regra de 09/09 que continua inteira.
    """
    from . import scryfall                                   # noqa: PLC0415
    quer = {str(nm).translate(_SEGURO).casefold(): (nm, q) for nm, q in pede.items()}
    for x in sorted(y for y in d.iterdir() if y.is_dir()):
        m = RE_PASTA_CARTA.match(x.name)
        if not m:
            continue                       # um lote ou um nome que não lê: fica
        rel = f"{pasta}/{x.name}"
        if rel in em_espera:
            continue
        nm_cf = m["nm"].casefold()
        if nm_cf in quer:
            nm, q = quer[nm_cf]
            if (int(m["q"]) == int(q)
                    or carta_feita(provadas.get((pasta, scryfall.chave(nm)), 0), q)):
                continue                   # é a de hoje, ou o ciclo de cima já tratou
            nova = d / nome_de_pasta_de_carta(nm, q)
            ja_ha = nova.exists()
            if apagar_pasta_feita(x, base):
                if ja_ha:
                    out["apagadas_fora"].append(rel)
                else:
                    nova.mkdir(parents=True, exist_ok=True)
                    out["renomeadas"].append(f"{rel} -> {nova.name}")
            elif tem_imagens(x):
                out["ficam_com_fotos"].append(rel)
            continue
        if nm_cf in de_versoes:
            continue                       # uma versão viva do formato: fica
        if apagar_pasta_feita(x, base):
            out["apagadas_fora"].append(rel)
        elif tem_imagens(x):
            out["ficam_com_fotos"].append(rel)


def _versoes_por_pasta(res: dict, cfg: dict | None = None) -> dict[str, set]:
    """`pasta do deck -> {carta das VERSÕES vivas do formato dela}` (em forma de
    pasta, casefold) — o que o plano não conta por desenho e ele quer (o
    Oswald, o Orzhov Monument). A mesma conta para quem apaga e quem conta."""
    fam_de = {s: f for f in familias(cfg) for s in f["slots"]}
    fmts: dict[str, set] = {}
    for s in res.get("slots") or []:
        f = fam_de.get(s["slot"])
        pasta = f["pasta"] if f else nome_de_pasta(s.get("nome") or s["slot"])
        if s.get("formato"):
            fmts.setdefault(pasta, set()).add(s["formato"])
    versoes = cartas_das_versoes(cfg)
    return {pasta: {c for fmt in fs for cartas in versoes.get(fmt, {}).values()
                    for c in cartas}
            for pasta, fs in fmts.items()}


# O `_fora do plano\` (16/10 de manhã) — o corredor de espera das pastas de
# carta que nenhuma lista pedia — deixou de existir no MESMO DIA, a pedido dele:
# *"como ainda nao fotografei nada, altera as pastas que tens que alterar"*. Uma
# pasta de carta vazia que nenhuma lista pede apaga-se (`_acertar_vazias`).


def cartas_das_versoes(cfg: dict | None = None) -> dict[str, dict[str, set]]:
    """`formato -> {nome da versão: {carta em forma de pasta, casefold}}` — as
    VERSÕES vivas do `decks_por_formato` que têm lista própria no
    `listas_escolhidas` (o Oswald, o Orzhov Monument). Não são caixa, por isso o
    plano não as conta; mas são decks dele, e as pastas delas ficam."""
    from . import sources                                    # noqa: PLC0415
    cfg = cfg if cfg is not None else sources.config()
    le = cfg.get("listas_escolhidas") or {}
    out: dict[str, dict[str, set]] = {}
    for fmt, b in (cfg.get("decks_por_formato") or {}).items():
        if not isinstance(b, dict):
            continue
        for v in b.get("versoes") or []:
            if not isinstance(v, dict) or v.get("_saiu") or not v.get("id"):
                continue
            reg = le.get(v["id"])
            if not isinstance(reg, dict):
                continue
            nomes = {str(c[1]).translate(_SEGURO).casefold()
                     for c in (reg.get("cards") or [])
                     if isinstance(c, (list, tuple)) and len(c) >= 3}
            if nomes:
                out.setdefault(fmt, {})[str(v.get("nome") or v["id"])] = nomes
    return out


def contas_das_pastas(res: dict, cfg: dict | None = None,
                      raiz: Path | str | None = None) -> dict:
    """AS DUAS CONTAS (André, 2026-10-16): o que o plano pede e o que está no
    disco. A 16/10 eram 595 contra 650 e a diferença não aparecia em sítio
    nenhum. Cada pasta de carta no disco cai num de três grupos:

    * `no_plano` — uma carta que a caixa (ou a família) pede;
    * `de_versoes` — uma carta de uma VERSÃO viva do formato que não é caixa
      (`cartas_das_versoes`): ele quer-a, e o plano não a conta por desenho;
    * `por_explicar` — nem uma coisa nem outra: resto de uma lista que mudou.
      É isto que o passo do daily põe a vermelho, porque é uma pasta a pedir-lhe
      uma foto que nenhum deck quer.
    """
    out = {"no_disco": 0, "no_plano": 0, "de_versoes": [], "por_explicar": []}
    base = pasta_novas(raiz)
    if not base.is_dir():
        return out
    pede = precisa_por_pasta(res, cfg)
    fam_de = {s: f for f in familias(cfg) for s in f["slots"]}
    fmts: dict[str, set] = {}
    for s in res.get("slots") or []:
        f = fam_de.get(s["slot"])
        pasta = f["pasta"] if f else nome_de_pasta(s.get("nome") or s["slot"])
        if s.get("formato"):
            fmts.setdefault(pasta, set()).add(s["formato"])
    versoes = cartas_das_versoes(cfg)
    # `_versoes_por_pasta` é a mesma conta, achatada, para quem apaga; aqui
    # quer-se o NOME da versão, para a frase das contas.
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        if d.name.startswith("_"):
            continue
        quer = {str(nm).translate(_SEGURO).casefold() for nm in pede.get(d.name, {})}
        for x in sorted(y for y in d.iterdir() if y.is_dir()):
            m = RE_PASTA_CARTA.match(x.name)
            if not m:
                continue                   # um lote ou um nome que não lê: não é pasta de carta
            out["no_disco"] += 1
            nm = m["nm"].casefold()
            if nm in quer:
                out["no_plano"] += 1
                continue
            de = sorted(nome for fmt in fmts.get(d.name, ())
                        for nome, cartas in versoes.get(fmt, {}).items()
                        if nm in cartas)
            item = {"deck": d.name, "pasta": x.name}
            if de:
                out["de_versoes"].append({**item, "versoes": de})
            else:
                out["por_explicar"].append(item)
    return out


class PastasPorExplicar(RuntimeError):
    """Há pastas de carta no disco que nenhuma caixa nem versão pede."""


def exige_contas_explicadas(c: dict, por_pedir: int) -> str:
    """Devolve a frase das duas contas, ou LEVANTA se a diferença entre o disco
    e o plano não for toda explicada por pastas de versão. É o que põe o passo
    `fotos-plano` a vermelho: uma pasta por explicar é uma foto a mais que ele
    tiraria à mão.

    Desde 2026-10-16 o `sincronizar_pastas_de_cartas` apaga sozinho as VAZIAS
    que nenhuma lista pede; as que sobram aqui são as que ele não pode apagar —
    com uma imagem ou um ficheiro que não é nosso. Essas não se tocam: decide-se
    à mão."""
    t = texto_das_contas(c, por_pedir)
    sobra = c.get("por_explicar") or []
    if sobra:
        raise PastasPorExplicar(
            f"{len(sobra)} pastas de carta que nenhuma lista pede e que não se "
            "apagaram por terem fotos ou ficheiros que não são do vault ("
            + ", ".join(x["deck"] + "/" + x["pasta"] for x in sobra[:6])
            + (" …" if len(sobra) > 6 else "")
            + f"); {t}. Não se tocam: vê o que lá está e decide à mão")
    return t


def texto_das_contas(c: dict, por_pedir: int) -> str:
    """A frase das duas contas, a mesma no daily e no CLI."""
    from collections import Counter                          # noqa: PLC0415
    vers = Counter(v for x in c["de_versoes"] for v in x["versoes"][:1])
    t = (f"{por_pedir} por fotografar (plano), {c['no_disco']} pastas no disco"
         f" — diferença {c['no_disco'] - por_pedir}: "
         f"{len(c['de_versoes'])} de versões que não são caixa")
    if vers:
        t += " (" + ", ".join(f"{n} {q}" for n, q in sorted(vers.items())) + ")"
    t += f", {len(c['por_explicar'])} por explicar"
    if c["no_plano"] != por_pedir:
        # uma carta do plano sem pasta (o deck não tem pasta) ou uma pasta de
        # carta já provada que não se apagou (tem fotos): diz-se o número.
        t += f" (pastas do plano no disco: {c['no_plano']})"
    return t
