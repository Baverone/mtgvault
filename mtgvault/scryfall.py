"""Catálogo de cartas via Scryfall bulk data.

A Scryfall é a espinha dorsal: dá-nos o ID de cada impressão, o nome oracle,
as legalidades e — crucialmente — o `cardmarket_id`, que é a ponte para os
preços do Cardmarket.

Usamos o ficheiro "default_cards" (todas as impressões). A Scryfall serve-o
agora como JSONL comprimido (.jsonl.gz, ~77 MB); lemos linha a linha, em
streaming, descomprimindo com gzip (ver download_bulk/load_bulk).
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

import requests

BULK_INDEX = "https://api.scryfall.com/bulk-data"
UA = {"User-Agent": "mtgvault/0.1", "Accept": "application/json"}
_LAST_CALL = 0.0


def _polite_get(url: str, **kw) -> requests.Response:
    """A Scryfall pede 50-100ms entre pedidos. Respeitamos."""
    global _LAST_CALL
    wait = 0.1 - (time.time() - _LAST_CALL)
    if wait > 0:
        time.sleep(wait)
    r = requests.get(url, headers=UA, timeout=60, **kw)
    _LAST_CALL = time.time()
    r.raise_for_status()
    return r


def download_bulk(kind: str = "default_cards", dest: Path | None = None) -> Path:
    """Descarrega o ficheiro bulk mais recente. Devolve o caminho local.

    A Scryfall migrou o bulk data (2025) para JSONL comprimido: cada entrada traz
    agora `jsonl_download_uri` (um .jsonl.gz em data.scryfall.io) e a antiga
    `download_uri` (array JSON descomprimido) desapareceu. Aceita as duas por
    segurança, preferindo o JSONL.
    """
    index = _polite_get(BULK_INDEX).json()
    entry = next(d for d in index["data"] if d["type"] == kind)
    url = entry.get("jsonl_download_uri") or entry.get("download_uri")
    if not url:
        raise RuntimeError(f"bulk-data sem URL de download para {kind!r}")
    suffix = ".jsonl.gz" if url.endswith(".gz") else ".json"
    dest = dest or Path.home() / "mtgvault" / "cache" / f"{kind}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    with _polite_get(url, stream=True) as r, dest.open("wb") as fh:
        for chunk in r.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
    return dest


def _texto_oracle(c: dict) -> str | None:
    """O texto da carta. Numa carta de duas faces junta as duas com ` // `.

    É de 2026-10-01, e existe para UMA pergunta: derivar do catálogo as listas de
    shocklands e de fetchlands das quatro protecções da venda (ver
    `mtgvault/fases.py`). Sem ele, as fetchlands não se distinguem das outras
    terras de Onslaught/Zendikar — o filtro possível (`type_line = 'Land'`, 1.ª
    impressão em ONS/ZEN, rare) dá **19** nomes e não 10: leva o Riptide
    Laboratory, o Grand Coliseum, o Valakut. A alternativa era escrever as dez à
    mão, e uma lista escrita de memória não se pode verificar.

    Guarda-se o texto das DUAS faces porque o `fases` procura por padrões
    (*"Search your library for a ... land card"*) e a face de trás de uma
    modal-DFC pode ser precisamente a terra.
    """
    t = c.get("oracle_text")
    if t:
        return t
    faces = [f.get("oracle_text") or "" for f in (c.get("card_faces") or [])]
    faces = [f for f in faces if f]
    return " // ".join(faces) if faces else None


def _row(c: dict) -> tuple | None:
    if c.get("layout") in ("art_series", "token", "double_faced_token", "emblem"):
        return None
    img = (c.get("image_uris") or {}).get("normal")
    if not img and c.get("card_faces"):
        img = (c["card_faces"][0].get("image_uris") or {}).get("normal")
    return (
        c["id"],
        c.get("oracle_id") or c["id"],
        c["name"],
        c["set"],
        c.get("set_name"),
        c.get("collector_number"),
        c.get("lang"),
        c.get("rarity"),
        c.get("type_line"),
        _texto_oracle(c),
        c.get("mana_cost"),
        c.get("cmc"),
        "".join(c.get("color_identity") or []),
        json.dumps(c.get("finishes") or []),
        c.get("released_at"),
        c.get("cardmarket_id"),
        c.get("tcgplayer_id"),
        img,
        json.dumps(c.get("legalities") or {}),
        int(bool(c.get("digital"))),
        int(bool(c.get("reprint"))),
        int(bool(c.get("reserved"))),
        c.get("set_type"),
    )


INSERT = """INSERT OR REPLACE INTO catalog.cards (
    scryfall_id, oracle_id, name, set_code, set_name, collector_number, lang,
    rarity, type_line, oracle_text, mana_cost, cmc, color_identity, finishes,
    released_at, cardmarket_id, tcgplayer_id, image_uri, legalities, digital,
    reprint, reserved, set_type
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


def load_bulk(con: sqlite3.Connection, path: Path, batch: int = 5000) -> int:
    """Carrega o ficheiro bulk para a tabela `cards`.

    O bulk da Scryfall passou a JSONL comprimido (um objeto por linha, .jsonl.gz).
    Lê-se linha a linha (streaming, sem carregar tudo em memória) e descomprime-se
    com gzip. Tolera também o formato antigo (array JSON), saltando os
    delimitadores `[`/`]` e a vírgula final de cada linha.
    """
    import gzip

    opener = gzip.open if str(path).endswith(".gz") else open
    n, buf = 0, []
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            try:
                card = json.loads(line)
            except json.JSONDecodeError:
                continue
            row = _row(card)
            if row is None:
                continue
            buf.append(row)
            if len(buf) >= batch:
                con.executemany(INSERT, buf)
                con.commit()
                n += len(buf)
                buf.clear()
    if buf:
        con.executemany(INSERT, buf)
        con.commit()
        n += len(buf)
    return n


def has_card_meta(con: sqlite3.Connection) -> bool:
    """Se o catálogo já traz a metadata nova. Um catálogo antigo em cache (ex.: na
    cloud, ou o deste PC antes de 2026-10-01) tem as colunas a 0/NULL — daí o
    reload. É o `daily._catalog` que a pergunta, e é por aqui que uma coluna
    nova do catálogo se faz PREENCHER: o `_catalog` salta o `sync` quando o
    catálogo tem linhas, e sem esta pergunta a coluna ficava a NULL para sempre.

    `oracle_text` (2026-10-01) entrou por isso mesmo: é dele que saem as
    shocklands e as fetchlands das quatro protecções da venda
    (`mtgvault/fases.py`), e um catálogo sem ele faz o `fases.fetchlands`
    levantar — alto, e não com uma protecção vazia.
    """
    r = con.execute("""SELECT
            SUM(CASE WHEN reserved = 1 THEN 1 ELSE 0 END) rl,
            SUM(CASE WHEN oracle_text IS NOT NULL AND oracle_text <> ''
                     THEN 1 ELSE 0 END) txt
          FROM catalog.cards""").fetchone()
    return bool(r) and (r["rl"] or 0) > 0 and (r["txt"] or 0) > 0


def sync(con: sqlite3.Connection) -> int:
    """Atualiza o catálogo completo. Correr uma vez por semana chega."""
    return load_bulk(con, download_bulk())


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------
MOTIVO_EDICAO = "edicao em falta"


class EdicaoEmFalta(LookupError):
    """Pediu-se uma impressão sem dizer qual é a edição.

    Antes de 2026-09-08 isto não dava erro: `find_printing` sem `set_code`
    terminava em `ORDER BY released_at ASC LIMIT 1` e devolvia a impressão
    **mais antiga** — para as básicas, sempre Alpha. Uma linha de CSV com a
    edição em branco não falhava: gravava a edição errada em silêncio, e foi
    assim que 5 Plains do Cloud cEDH ficaram `lea #287` (309,50 € de valor
    fantasma; ver `work/revisao/mtgvault-edicoes-suspeitas.md`). É o padrão do
    `event_tier`: um passo que corre sem erro e produz um valor falso.

    É `LookupError` para os importadores que já apanhavam `LookupError` não
    mudarem de comportamento — mudou só a mensagem, que agora diz o motivo.
    """

    def __init__(self, name: str):
        super().__init__(f"{MOTIVO_EDICAO}: {name}")
        self.card_name = name


def _preco(con: sqlite3.Connection, scryfall_id: str) -> float:
    """Preço de referência de uma impressão; infinito quando não há preço.

    Sem preço não se pode dizer que é "a mais barata", e um desempate que
    invente um número escolheria sempre a mesma impressão sem razão nenhuma.
    """
    try:
        from . import precos                               # noqa: PLC0415
        expr = precos.sql(alias="p")
        r = con.execute(
            f"SELECT MIN({expr}) t FROM price_latest p WHERE scryfall_id = ? "
            f"AND {expr} IS NOT NULL", (scryfall_id,)).fetchone()
    except sqlite3.OperationalError:      # catálogo sozinho, sem a vault.db
        return float("inf")
    return r["t"] if r and r["t"] is not None else float("inf")


def _clausula_finish(finishes) -> tuple[str, list]:
    """SQL que aceita só as impressões que existem num destes acabamentos.

    O `cards.finishes` é JSON (`["nonfoil","foil"]`), e por isso a comparação é
    com as aspas dentro: `LIKE '%foil%'` dá TODA a impressão nonfoil como foil —
    é a mesma armadilha do `loadout.e_foil` (*"nonfoil" contém "foil"*), que já
    marcou 41 linhas de venda com um ✨ que não lhes pertencia.
    """
    if not finishes:
        return "", []
    return (" AND (" + " OR ".join("finishes LIKE ?" for _f in finishes) + ")",
            [f'%"{f}"%' for f in finishes])


# ---------------------------------------------------------------------------
# OS SETS QUE NÃO SÃO PREÇO (André, 2026-10-06, à letra)
# ---------------------------------------------------------------------------
# *"Summer Magic / Edgar (sum), 30th Anniversary Edition (30a), Collectors'
# Edition (ced), Intl. Collectors' Edition (cei). Os tres ultimos nao sao cartas
# legais e o primeiro quase nao transacciona — os precos do cardmarket para ele
# sao lixo (0,02 EUR num Badlands). Nenhum destes pode emprestar preco a outra
# impressao, em sitio nenhum do app. Se ele TIVER uma copia de um destes sets, o
# preco dessa copia e o do set dela e esta certo; o que esta proibido e usa-lo
# para outra copia."*
#
# A LISTA DELE ESTAVA INCOMPLETA, e a medição di-lo: dos **87** mínimos por nome
# que hoje vêm de um set destes (fonte `cardmarket`, as 580 cartas da colecção),
# só ~10 são `sum`/`30a`/`ced`/`cei` — **a maioria são os decks do World
# Championship** (`wc97`…`wc04`, `ptc`, `olep`, `olgc`, `ocm1`), que são cartas
# de borda dourada, não legais, e `set_type = 'memorabilia'`. E são eles que
# fazem três dos sete exemplos que ele deu: **Gaea's Cradle 272,71 €** (wc99),
# **Grim Monolith 22,15 €** (wc99) e **Flooded Strand 11,64 €** (wc04). Com a
# lista dos quatro sozinha, os piores casos dele ficavam por corrigir.
#
# Daí a regra ser: papel, não-memorabilia, e os quatro sets pelo nome. O `sum` é
# o único dos quatro que PRECISA de estar escrito — os outros três já são
# `memorabilia` (conferido no catálogo); a Summer Magic é `core` e escapa a tudo.
#
# E ISTO ESTAVA ESCRITO QUATRO VEZES, nenhuma delas completa — o padrão do
# `e_foil`, do `vistoId` e do `precos.sql()`: o `scryfall.impressoes`
# (`digital = 0 AND set_type <> 'memorabilia'`), o `fases._preco_jogavel` (igual,
# com a nota a dizer que o `sum` lhe escapa), o `meta_coverage._NOT_PLAYABLE`
# (por `set_name LIKE`, que apanha o World Championship e não o `sum` nem o
# `30a`) e o `loadout.mais_barata_que_serve` (só `digital = 0`). Agora é uma, e
# as quatro lêem de cá.
SETS_SEM_PRECO = ("sum", "30a", "ced", "cei")


def sql_impressao_a_serio(alias: str = "c") -> str:
    """O predicado: esta impressão pode EMPRESTAR o preço (e a identidade) a outra?

    Papel (`digital = 0`), não memorabilia, e fora dos `SETS_SEM_PRECO`. Vale
    para as duas perguntas que são a mesma: *«qual é a impressão mais barata
    desta carta?»* (o preço de uma COMPRA) e *«que impressão é esta cópia?»* (o
    palpite de edição). Uma impressão de um destes sets continua a ter o SEU
    preço — o que ela não faz é responder pelas outras.

    Os `COALESCE` são precisos: num catálogo antigo o `digital` e o `set_type`
    nascem a NULL (entraram por `ALTER TABLE`), e `NULL <> 'memorabilia'` é NULL,
    que em SQL não é verdadeiro — sem eles o predicado deitava fora o catálogo
    inteiro em vez de o filtrar. Os literais vêm de uma tupla do código, nunca de
    entrada de ninguém.
    """
    a = f"{alias}." if alias else ""
    sets = ", ".join(f"'{s}'" for s in SETS_SEM_PRECO)
    return (f"COALESCE({a}digital, 0) = 0 "
            f"AND COALESCE({a}set_type, '') <> 'memorabilia' "
            f"AND lower(COALESCE({a}set_code, '')) NOT IN ({sets})")


def impressoes(con: sqlite3.Connection, name: str, *, ate: str | None = None,
               finishes=None, limite: int = 12) -> list[sqlite3.Row]:
    """As impressões candidatas de uma carta, a MELHOR PRIMEIRA.

    "Melhor" é a definição do `_adivinhar`: a mais RECENTE e, dentro dessa data,
    a mais BARATA. As outras vêm por data decrescente, para o selector de edição
    do *"já a tenho"* (deckboxes) começar no palpite e ter as alternativas
    plausíveis logo a seguir.

    `ate` corta as impressões posteriores a uma data — é a regra de edições de
    uma caixa (`edicoes: "premodern"` = até ao Scourge). Sem ela, o palpite de
    uma caixa de Premodern era uma reimpressão de 2024, que a própria caixa
    depois recusa. `finishes` faz o mesmo para o acabamento.

    O preço só se pergunta às impressões do PRIMEIRO dia (as que disputam o
    palpite): uma carta com quarenta reimpressões dava quarenta consultas de
    preço para ordenar uma lista que ele vai ler por data.
    """
    # O `name = ?` usa o índice `ix_cards_name`; o `lower(name) = lower(?)` faz
    # uma varredura das ~500 mil impressões do catálogo. A página das caixas
    # chama isto uma vez por carta em falta (~150), e pela via lenta eram 10
    # segundos por cada regeneração do modo edição — que corre a cada clique.
    # O caminho tolerante fica como recurso, para os nomes escritos à mão.
    # O predicado vive num sítio só (`sql_impressao_a_serio`): era `digital = 0
    # AND set_type <> 'memorabilia'` escrito aqui, e deixava passar a **Summer
    # Magic** — que é `core`. Um palpite de edição para um Tundra podia cair numa
    # impressão de 1994 que nunca se transaccionou.
    q = f"SELECT * FROM cards WHERE name = ? AND {sql_impressao_a_serio('')}"
    args: list = [name]
    if ate:
        q += " AND released_at <= ?"
        args.append(ate)
    extra, mais = _clausula_finish(finishes)
    ordem = " ORDER BY released_at DESC, set_code"
    rows = con.execute(q + extra + ordem, args + mais).fetchall()
    if not rows:
        q = q.replace("WHERE name = ?", "WHERE lower(name) = lower(?)", 1)
        rows = con.execute(q + extra + ordem, args + mais).fetchall()
    if not rows and extra:
        # Nenhuma impressão neste acabamento (uma carta de 1997 numa caixa de
        # foil). Vale mais oferecer a lista sem o filtro — a cópia fica com a
        # nota "edição por confirmar" e a foto acerta-a — do que um selector
        # vazio, que não diz porquê.
        rows = con.execute(q + " ORDER BY released_at DESC, set_code",
                           args).fetchall()
    if not rows:
        return []
    dia = rows[0]["released_at"]
    # o collector_number desempata o que o preço não desempata: sem ele, duas
    # artes sem preço davam uma escolha que mudava com a ordem da tabela.
    recentes = sorted((r for r in rows if r["released_at"] == dia),
                      key=lambda r: (_preco(con, r["scryfall_id"]),
                                     r["collector_number"] or ""))
    resto = [r for r in rows if r["released_at"] != dia]
    return (recentes + resto)[:limite]


FOIL_FINISHES = ("foil", "etched")

# O limite de cima de um prefixo, para a FRENTE de uma carta de dupla face
# (2026-10-01). O SQLite compara TEXT byte a byte (UTF-8) e o U+10FFFF é o ponto
# de código mais alto que existe, por isso nenhum nome válido pode passar daqui.
_ALTO = "\U0010ffff"


def frente_de_dupla_face(coluna: str = "name") -> str:
    """`name >= ? AND name < ?` — a frente de uma carta de dupla face, PELO ÍNDICE.

    Era `name LIKE ? || ' // %'`, e isso **varria o catálogo inteiro**: o
    `EXPLAIN QUERY PLAN` dizia `SCAN cards`, porque a optimização do LIKE do
    SQLite não se aplica a um padrão que é uma EXPRESSÃO (`? || '…'`) nem a uma
    coluna de colação BINARY. Um intervalo de prefixo usa o `ix_cards_name` que
    já existe (`SEARCH cards USING INDEX ix_cards_name (name>? AND name<?)`).

    **Porque é que isto era a avaria de 2026-10-01**: o `impressoes_foil` corre
    esta consulta uma vez por carta que nunca saiu em foil — nos anos 90 são
    quase todas —, e o `oracle_text` que entrou no catálogo nesse mesmo dia pôs
    o `catalog.db` em 143 MB: cada varredura passou a ler muito mais página.
    Medido na base dele, nos 550 nomes reais que caem aqui: **276 ms cada** com
    o LIKE contra **0,29 ms** com o intervalo, e o `loadout.report` inteiro de
    74,5 s para 18,7 s. O resultado é o MESMO nos 550 (comparado um a um).

    Dá os parâmetros com o `limites_dupla_face(nome)`, na mesma ordem.
    """
    return f"{coluna} >= ? AND {coluna} < ?"


def limites_dupla_face(name: str) -> tuple[str, str]:
    """Os dois parâmetros do `frente_de_dupla_face`, por esta ordem."""
    return (f"{name} // ", f"{name} // {_ALTO}")


# ---------------------------------------------------------------------------
# O CRUZAMENTO NOME-DE-LISTA ↔ CATÁLOGO, NUM SÍTIO SÓ (2026-10-04)
# ---------------------------------------------------------------------------
# A AVARIA que isto fecha: o cruzamento era IGUALDADE DE NOME, e o catálogo
# guarda as cartas de duas faces com o nome inteiro (`Witch Enchanter //
# Witch-Blessed Meadow`) enquanto as listas trazem só a frente (`Witch
# Enchanter`). Quando o cruzamento falha, a carta fica SEM TIPO, SEM PREÇO e
# CONTADA COMO NÃO TIDA — ou seja, a aplicação mandava COMPRAR cartas que ele
# já tem. Medido na base dele a 2026-10-04: **240 nomes distintos** de
# `decklist_cards` não casavam, em **7 983 linhas** e **4 258 das 7 724 listas
# (55 %)**.
#
# São DUAS vias, e por isso o predicado tem quatro ramos:
#   (a) a FRENTE de uma carta de duas faces — 181 nomes, 7 034 linhas;
#   (b) o SEPARADOR escrito de outra maneira (`Wear/Tear`, `Bedeck / Bedazzle`,
#       `Breaking/Entering`) — 33 nomes, 701 linhas. O catálogo usa sempre
#       ` // `.
#
# **A ORDEM DOS RAMOS É UMA DECISÃO DE SEGURANÇA, não estética.** O nome TAL E
# QUAL vem primeiro porque há cartas a sério com barras no nome que NÃO são
# separador: `SP//dr, Piloted by Peni` e `Summon: Choco/Mog`. Canonizar às
# cegas partia-as em duas faces que não existem. Verificado no catálogo inteiro
# (112 755 impressões, 974 nomes com ` // `): **zero** nomes reais cuja
# canonização seja outro nome real, e as duas armadilhas canonizam para algo
# que não existe — por isso os ramos (b) não lhes podem roubar a resposta.
#
# **E É TODO PELO ÍNDICE**, que é o que partiu o site a 2026-10-01: o
# `EXPLAIN QUERY PLAN` dá `MULTI-INDEX OR` com os quatro ramos em
# `SEARCH cards USING INDEX ix_cards_name`. Um `name LIKE ? || ' // %'` dá
# `SCAN cards` — e era isso que estava escrito no `collection`, no `marcas`, no
# `paginas` e no `import_owned`, por isso esta correcção torna-os mais
# RÁPIDOS. Medido nos 4 721 nomes reais de lista: `name = ?` sozinho 0,0077 ms
# por nome, o predicado dos quatro ramos **0,0097 ms** (36,2 → 45,6 ms ao
# todo), e os nomes que casam passam de 4 481 para **4 695**.
SEPARADOR = " // "


_BARRAS = re.compile(r"\s*/{1,2}\s*")


def canonizar(nome: str) -> str:
    """O nome com o SEPARADOR do catálogo: `Wear/Tear` → `Wear // Tear`.

    Normaliza uma ou duas barras com ou sem espaços à volta. Um nome sem barra
    nenhuma sai igual, e é por isso que esta função **nunca se usa sozinha**:
    quem decide é o `sql_nome`/`resolver`, onde o nome tal e qual é tentado
    primeiro (o `SP//dr, Piloted by Peni` é uma carta a sério).

    **O `"/" not in nome` à cabeça não é um requinte.** Isto corre uma vez por
    consulta a um `MapaDeCartas`, e esses são consultados milhares de vezes por
    página — na primeira versão desta correcção o `loadout.report` passou de
    0,7 s para **10,1 s** só por causa do regex. Dos 4 721 nomes de lista da
    base dele, **33** têm barra: a saída antecipada trata os outros 4 688.
    """
    nome = nome or ""
    if "/" not in nome:
        return nome
    partes = [p.strip() for p in _BARRAS.split(nome) if p.strip()]
    return SEPARADOR.join(partes) if len(partes) > 1 else nome


def chave(nome: str) -> str:
    """A CHAVE de cruzamento de um nome de carta: a FRENTE, canonizada.

    `Wear/Tear` → `Wear`; `Witch Enchanter // Witch-Blessed Meadow` → `Witch
    Enchanter`; `Swords to Plowshares` → igual. É esta a chave de todo o
    dicionário que case o que uma LISTA pede com o que a COLECÇÃO tem — e tem
    de ser a mesma função nos dois lados, senão a `posse_total` guarda `Wear`
    (do catálogo) e a lista procura `Wear/Tear`, que é exactamente como as 2
    cópias de `Wear // Tear` dele contavam como zero.

    Caminho rápido pela mesma razão do `canonizar`: a esmagadora maioria dos
    nomes não tem barra nenhuma e sai sem tocar no regex nem no `split`.
    """
    nome = nome or ""
    if "/" not in nome:
        return nome
    return canonizar(nome).split(SEPARADOR)[0].strip()


class MapaDeCartas(dict):
    """Um `dict` indexado por NOME DE CARTA que aplica o `chave()` sozinho.

    **É isto que torna «uma função só» verdade do lado dos dicionários.** A
    posse, os tipos, as cores e as imagens são mapas `nome -> coisa`, e há mais
    de vinte sítios a fazer `mapa.get(nm)` com o nome que a LISTA deu. Pedir a
    cada um deles que se lembre de canonizar era deixar o primeiro que se
    esquecesse a responder *"não tenho"* — que é exactamente como as 2 cópias
    de `Wear // Tear` dele contavam zero contra uma lista que pede `Wear/Tear`.
    Aqui a regra vive no próprio mapa: quem guarda e quem procura passam os dois
    pela mesma porta, e nenhum sítio tem de saber disto.

    As chaves GUARDADAS são sempre canónicas, por isso iterar, `items()` e o
    `json.dump` não mudam de forma.
    """

    def __init__(self, inicial=None):
        super().__init__()
        if inicial:
            for k, v in dict(inicial).items():
                self[k] = v

    def __setitem__(self, k, v):
        super().__setitem__(chave(k), v)

    def __getitem__(self, k):
        return super().__getitem__(chave(k))

    def __contains__(self, k):
        return super().__contains__(chave(k))

    def get(self, k, omissao=None):
        return super().get(chave(k), omissao)

    def setdefault(self, k, omissao=None):
        return super().setdefault(chave(k), omissao)


def sql_nome(coluna: str = "name") -> str:
    """O PREDICADO do cruzamento, pelo índice. Dá-lhe os `params_nome(nome)`.

    Quatro ramos, nesta ordem: o nome tal e qual, a frente de uma dupla face,
    o nome canonizado, e a frente dele. Ver o comentário da secção.

    **QUANDO É QUE ISTO NÃO SE USA — e custou 12 s a descobrir.** O predicado
    serve a consulta em que a `cards` é a tabela que MANDA (o `card_price`, o
    `impressao_mais_barata`): aí os quatro ramos entram pelo `ix_cards_name` e
    o custo é 0,0077 → 0,0097 ms por nome. Numa consulta em que o nome está do
    lado LONGE de um JOIN com uma tabela grande, o `MULTI-INDEX OR` tira à
    `cards` o papel de condutor e o SQLite passa a varrer a outra: no
    `loadout._historico` (que junta a `price_history`) a consulta foi de
    **0,1 ms para 21,7 ms** e o `loadout.report` de 0,7 s para **12,9 s**. Nesse
    caso resolve-se o nome ANTES, com o `resolver()`, e compara-se por
    igualdade. A regra: **se o `EXPLAIN QUERY PLAN` deixar de dizer
    `SEARCH … USING INDEX ix_cards_name`, usa o `resolver()`.**
    """
    return (f"({coluna} = ? OR ({coluna} >= ? AND {coluna} < ?)"
            f" OR {coluna} = ? OR ({coluna} >= ? AND {coluna} < ?))")


def params_nome(nome: str) -> tuple[str, str, str, str, str, str]:
    """Os seis parâmetros do `sql_nome`, por esta ordem.

    Quando o nome não tem barras, o canonizado é igual e os dois últimos ramos
    repetem os dois primeiros — é inofensivo (continua `MULTI-INDEX OR`) e
    mantém o SQL com uma forma só, que é o que deixa o SQLite guardar o plano.
    """
    nm = nome or ""
    c = canonizar(nm)
    return (nm, *limites_dupla_face(nm), c, *limites_dupla_face(c))


def resolver(con: sqlite3.Connection, nome: str) -> str | None:
    """O nome do CATÁLOGO para um nome de lista, ou `None` se não existir.

    `None` quer dizer **DESCONHECIDA** e nunca *"não tenho"*: uma carta que não
    casa é um problema a mostrar, com o nome à vista, e não uma falta a
    comprar. Quem o diz ao André é o `desconhecidas()`.

    O nome tal e qual GANHA sempre, pela razão do `SP//dr`.
    """
    for arg in (nome, canonizar(nome)):
        if not arg:
            continue
        r = con.execute("SELECT name FROM cards WHERE name = ? LIMIT 1",
                        (arg,)).fetchone()
        if r:
            return r["name"]
        r = con.execute(
            f"SELECT name FROM cards WHERE {frente_de_dupla_face()} LIMIT 1",
            limites_dupla_face(arg)).fetchone()
        if r:
            return r["name"]
    return None


def resolver_muitos(con: sqlite3.Connection,
                    nomes) -> dict[str, str | None]:
    """`nome de lista -> nome do catálogo (ou None)`, num lote.

    Os que casam pelo nome exacto saem numa consulta por 300; os outros —
    poucos, 240 em 4 721 na base dele — pagam o `resolver`. É o padrão do
    `impressoes_foil`: o caminho rápido primeiro, o tolerante só para quem
    sobrar.
    """
    nomes = [n for n in dict.fromkeys(nomes) if n]
    out: dict[str, str | None] = {}
    for i in range(0, len(nomes), 300):
        ch = nomes[i:i + 300]
        ph = ",".join("?" for _ in ch)
        achados = {r["name"] for r in con.execute(
            f"SELECT name FROM cards WHERE name IN ({ph})", ch)}
        for n in ch:
            if n in achados:
                out[n] = n
    for n in nomes:
        if n not in out:
            out[n] = resolver(con, n)
    return out


def desconhecidas(con: sqlite3.Connection, nomes) -> list[str]:
    """Os nomes que o catálogo NÃO conhece, por ordem. Para os mostrar.

    Na base dele a 2026-10-04 são **25** e nenhum é um catálogo atrasado: o
    bulk estava sincronizado (de hoje) e a própria Scryfall responde 404 a
    `Ademi of the Silkchutes` e a `Zora, Spider Fancier`. Não se inventa a
    carta — fica desconhecida e dita pelo nome.
    """
    mapa = resolver_muitos(con, nomes)
    return sorted(n for n, a in mapa.items() if a is None)


def impressoes_foil(con: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    """As impressões desta carta que EXISTEM em foil (ou etched), por data.

    André, 2026-09-19, à letra: *"quando escreves que a carta não serve porque
    devia ser foil e não é foil, confirma se há foil."* Uma caixa que exige foil
    (SPML, Duel Commander) recusava a Glimmer Lens nonfoil — e a Glimmer Lens
    nunca saiu em foil: a exigência não se pode cumprir, e a cópia que ele tem é
    a única que existe. Quem decide o que isso significa para a caixa é o
    `loadout.acabamento_efectivo`; aqui responde-se só à pergunta do catálogo.

    Qualquer edição e qualquer língua contam para "existe" — o `cards.finishes`
    é por impressão (`["nonfoil","foil"]`, `["foil"]`, `["etched"]`). As EN vêm
    primeiro, porque é a lista que a mensagem *"existe em foil: MMQ 1999, EXP
    2016…"* mostra. O `name = ?` usa o `ix_cards_name` (o `lower()` varria o
    catálogo inteiro — ver `impressoes`); o segundo caminho é para a frente de
    uma carta de dupla face, que as listas escrevem sem o `//`.

    Só PAPEL: as impressões `digital` (MTGO — a Swift Reconfiguration só tem
    foil na `prm` de MTGO, a Tundra na `vma`) e a memorabilia ficam de fora,
    como no `impressoes`. Um foil que só existe no MTGO não é um foil que ele
    possa meter na caixa, e dizer-lhe "existe em foil" por causa dele era
    mandá-lo comprar o que não se vende.
    """
    extra, mais = _clausula_finish(FOIL_FINISHES)
    q = ("SELECT set_code, released_at, lang, finishes FROM cards "
         "WHERE name = ? AND digital = 0 "
         "AND COALESCE(set_type,'') != 'memorabilia'" + extra
         + " ORDER BY (lang != 'en'), released_at, set_code")
    rows = con.execute(q, [name, *mais]).fetchall()
    if not rows:
        rows = con.execute(q.replace("name = ?", frente_de_dupla_face(), 1),
                           [*limites_dupla_face(name), *mais]).fetchall()
    return rows


def conhecida(con: sqlite3.Connection, name: str) -> bool:
    """O catálogo conhece esta carta (pelo nome exacto, ou pela frente de uma
    dupla face)? Pelo índice — o `resolve_name` tolerante varre o catálogo
    inteiro, e isto corre uma vez por carta que nunca saiu em foil, que nos
    anos 90 são todas."""
    if con.execute("SELECT 1 FROM cards WHERE name = ? LIMIT 1", (name,)).fetchone():
        return True
    return con.execute(
        f"SELECT 1 FROM cards WHERE {frente_de_dupla_face()} LIMIT 1",
        limites_dupla_face(name)).fetchone() is not None


def _adivinhar(con: sqlite3.Connection, name: str,
               collector_number: str | None,
               ate: str | None = None, finishes=None) -> sqlite3.Row | None:
    """A impressão mais RECENTE e, dentro dessa data, a mais BARATA.

    O contrário do que a função fazia antes, e de propósito: quem não sabe a
    edição de um Plains tem quase de certeza o Plains barato de um set recente,
    não o de Alpha. Continua a ser um palpite — quem o pede fica com a nota
    "edicao adivinhada" na cópia.

    É, literalmente, a primeira linha do `impressoes()`: o selector de edição do
    *"já a tenho"* mostra essa lista e pré-selecciona a primeira, e duas contas
    diferentes deixariam o palpite do servidor a discordar do que a página
    mostrou por omissão.
    """
    cands = impressoes(con, name, ate=ate, finishes=finishes, limite=999)
    if collector_number:
        cands = [r for r in cands if r["collector_number"] == collector_number]
    return cands[0] if cands else None


def find_printing(
    con: sqlite3.Connection,
    name: str,
    set_code: str | None = None,
    collector_number: str | None = None,
    *,
    adivinhar: bool = False,
    ate: str | None = None,
    finishes=None,
) -> sqlite3.Row | None:
    """Encontra uma impressão específica.

    **Sem `set_code` levanta `EdicaoEmFalta`** — não se inventa uma edição (ver
    a classe). Quem quiser mesmo um palpite pede `adivinhar=True` e recebe a
    impressão mais recente e mais barata; nesse caso `collection.add_copy`
    escreve "edicao adivinhada" na `notes` da cópia.

    `ate` é a regra de edições de quem pede (uma caixa de Premodern só usa
    impressões até ao Scourge) e vale nos DOIS caminhos: um palpite que a
    ignorasse escolhia uma edição que a caixa recusa, e uma edição escrita à mão
    que a ignorasse era a mesma coisa com mais passos. O `finishes` guia só o
    palpite e o selector — quando ele NOMEIA a edição está a dizer que tem
    aquela cópia na mão, e o catálogo não é quem lhe diz o contrário.
    """
    if not set_code:
        if not adivinhar:
            raise EdicaoEmFalta(name)
        return _adivinhar(con, name, collector_number, ate, finishes)

    q = ("SELECT * FROM cards WHERE lower(name) = lower(?) AND digital = 0 "
         "AND lower(set_code) = lower(?)")
    args: list = [name, set_code]
    if collector_number:
        q += " AND collector_number = ?"
        args.append(collector_number)
    if ate:
        q += " AND released_at <= ?"
        args.append(ate)
    q += " ORDER BY released_at ASC LIMIT 1"
    return con.execute(q, args).fetchone()


def resolve_name(con: sqlite3.Connection, name: str) -> str | None:
    """Normaliza um nome escrito à mão para o nome oracle exato.

    Tolera falta de acentos, apóstrofos diferentes e só a primeira face
    de cartas duplas ("Fable of the Mirror-Breaker" -> nome completo).
    """
    name = name.strip()
    # O caminho INDEXADO primeiro (`resolver`): trata o nome exacto, a frente de
    # uma dupla face e o separador escrito de outra maneira sem varrer nada. O
    # `lower()` e o apóstrofo curvo ficam como recurso — esses varrem mesmo o
    # catálogo, e é por isso que não podem ser a primeira tentativa.
    achado = resolver(con, name)
    if achado:
        return achado
    row = con.execute(
        "SELECT name FROM cards WHERE lower(name) = lower(?) LIMIT 1", (name,)
    ).fetchone()
    if row:
        return row["name"]
    row = con.execute(
        f"SELECT name FROM cards WHERE {frente_de_dupla_face('lower(name)')} LIMIT 1",
        limites_dupla_face(name.lower())
    ).fetchone()
    if row:
        return row["name"]
    row = con.execute(
        "SELECT name FROM cards WHERE lower(replace(name, '’', '''')) = lower(?) LIMIT 1",
        (name.replace("’", "'"),),
    ).fetchone()
    return row["name"] if row else None
