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
    out += ["ONDE LARGAR AS FOTOS: NESTA PASTA.",
            f"  O vault reconhece a pasta como este deck (alvo: {slot}) e trata",
            "  as fotos como se as tivesses tirado na pagina. Nao precisas de",
            "  fixar alvo nenhum. Podes fazer subpastas de lote ('lote1').",
            "  A foto e MOVIDA daqui para pendentes\\ com o nome a dizer o deck,",
            "  e depois arrumada em data\\fotos\\" + slot + "\\. Nada se apaga.",
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
    for s in res.get("slots") or []:
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


TEXTO_ORFA = (
    "ESTA PASTA JA NAO E UM DECK\n"
    "===========================\n\n"
    "O deck que tinha este nome foi renomeado ou dissolvido, por isso o vault\n"
    "JA NAO RECONHECE esta pasta: uma foto largada aqui fica aqui e nao e\n"
    "catalogada.\n\n"
    "Larga as fotos na pasta com o nome ACTUAL do deck (estao todas em\n"
    "«Colocar fotos da colecao aqui\\», uma por deck), ou usa o botao\n"
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
    com_fila = set()
    for f in f2["filas"]:
        d = pasta_do_deck(f["nome"], raiz)
        if not d.is_dir():
            out["sem_pasta"].append(f["nome"])
            continue
        com_fila.add(f["nome"])
        (d / _PLANO).write_text(
            texto_do_plano(f["nome"], f["slot"], f["fotos"],
                           conversao=f["conversao"], nota=f["nota"]),
            encoding="utf-8")
        out["escritos"].append({"nome": f["nome"], "slot": f["slot"],
                                "fotos": f["barra"]["fotos"],
                                "cartas": f["barra"]["cartas"],
                                "ficheiro": str(d / _PLANO)})
    for s in res.get("slots") or []:
        nome = s.get("nome") or s["slot"]
        d = pasta_do_deck(nome, raiz)
        if nome in com_fila or not (d / _PLANO).is_file():
            continue
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
    if base.is_dir():
        mapa = mapa_pastas(cfg)
        conhecidas = ({_norm(g) for g in PASTAS_DE_GRUPO}
                      | {_norm(g) for g in PASTAS_FORA_DOS_DECKS})
        for d in sorted(x for x in base.iterdir() if x.is_dir()):
            if d.name.startswith("_") or _norm(d.name) in conhecidas:
                continue
            if _norm(d.name) in mapa or not (d / _PLANO).is_file():
                continue
            if (d / _PLANO).read_text(encoding="utf-8") != TEXTO_ORFA:
                (d / _PLANO).write_text(TEXTO_ORFA, encoding="utf-8")
            out["orfas"].append(d.name)
    return out


def texto_sem_cartas(nome: str, slot: str) -> str:
    return (f"PLANO DE FOTOS -- {nome}\nslot: {slot}\n\n"
            "Este deck NAO tem cartas registadas dentro da caixa, por isso\n"
            "nao ha nada para fotografar aqui ainda.\n\n"
            "Quando houver, as fotos vem para ESTA pasta: o vault reconhece\n"
            f"a pasta como este deck (alvo: {slot}) e trata-as como se as\n"
            "tivesses tirado na pagina. Nada se apaga.\n"
            f"A outra porta: {URL_EDICAO}\n"
            "O plano a serio esta na pagina «Arrumacao por fases», Fase 2.\n")


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
PASTA_NOVAS = "Colocar fotos da coleção aqui"
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


def alvo_da_pasta(caminho: Path | str, cfg: dict | None = None) -> dict | None:
    """O ALVO da revalidação a que uma foto pertence, pela PASTA em que está:

        {"tipo": "caixa",    "slot": "cedh-blue-farm"}   uma pasta de deck
        {"tipo": "coleccao", "slot": None}               `Extras (fora dos decks)`
        None                                             grupo/desconhecida/raiz

    É a pergunta de que a recolha precisa, e vive **num sítio só**: o
    `slot_da_pasta` responde a *"que caixa é esta pasta"* e continua a responder
    só isso (devolve `None` para os Extras, que não são caixa nenhuma). Duas
    respostas à mesma pergunta discordam um dia qualquer, em silêncio — a lição
    do `e_foil`, do `vistoId` e do `precos.sql()`.
    """
    partes = Path(str(caminho)).parts
    base = _norm(PASTA_NOVAS)
    i = next((k for k, p in enumerate(partes) if _norm(p) == base), None)
    resto = partes[i + 1:] if i is not None else partes
    if len(resto) < 2:
        return None                        # está na pasta-mãe: não tem alvo
    if _norm(resto[0]) in {_norm(p) for p in PASTAS_FORA_DOS_DECKS}:
        return {"tipo": ALVO_FORA_DOS_DECKS, "slot": None}
    slot = mapa_pastas(cfg).get(_norm(resto[0]))
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
    if not base.is_dir():
        return []
    mapa = mapa_pastas(cfg)
    grupos = {_norm(g) for g in PASTAS_DE_GRUPO}
    fora = {_norm(g) for g in PASTAS_FORA_DOS_DECKS}
    out = []
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        if d.name.startswith("_"):
            continue
        slot = mapa.get(_norm(d.name))
        # O TIPO de alvo da pasta: uma caixa, ou o `coleccao` dos Extras. É o que
        # a recolha precisa de saber para dar o nome à foto.
        tipo = (ALVO_FORA_DOS_DECKS if _norm(d.name) in fora
                else "caixa" if slot else None)
        for f in sorted(x for x in d.rglob("*")
                        if x.is_file() and x.suffix.lower() in EXT):
            out.append({"ficheiro": f, "pasta": d.name, "slot": slot,
                        "tipo": tipo, "grupo": _norm(d.name) in grupos,
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
    """
    from . import fotosite                                   # noqa: PLC0415
    agora = time.time() if agora is None else agora
    pend = fotosite.pasta_pendentes(raiz)
    out: dict = {"recolhidas": [], "ignorados": [], "a_chegar": [],
                 "pastas": 0, "destino": str(pend)}
    itens = fotos_nas_pastas(cfg, raiz)
    if not itens:
        return out
    out["pastas"] = len({i["pasta"] for i in itens})
    pend.mkdir(parents=True, exist_ok=True)
    for it in itens:
        f = it["ficheiro"]
        if not it.get("tipo"):
            out["ignorados"].append({
                "ficheiro": f.name, "pasta": it["pasta"],
                "porque": ("é uma pasta de grupo — ninguém a processa "
                           "automaticamente, como sempre" if it["grupo"] else
                           f"{it['pasta']!r} não é o nome de nenhuma caixa do "
                           "config (não se adivinha o deck)")})
            continue
        if agora - it["mtime"] < sossego_s:
            out["a_chegar"].append({"ficheiro": f.name, "pasta": it["pasta"]})
            continue
        quando = _dt.datetime.fromtimestamp(it["mtime"]).replace(microsecond=0)
        nome = _nome_livre(pend, it["tipo"], it["slot"], quando,
                           f.suffix.lstrip(".").lower())
        shutil.move(str(f), str(pend / nome))
        out["recolhidas"].append({"de": f.name, "pasta": it["pasta"],
                                  "slot": it["slot"], "tipo": it["tipo"],
                                  "para": nome})
    if out["recolhidas"]:
        _CACHE.clear()
    return out
