"""As fotos do núcleo (spec «Fotos»): tirar a foto que ele mandou no chat do
registo da sessão, recortar cada carta, e validar as cópias contra os recortes.

O caminho de uma foto:

1. **Extrair** — as imagens vêm do `.jsonl` da sessão do Claude Code neste PC
   (`~/.claude/projects/<projeto>/<sessão>.jsonl`), em base64. O original grava-se
   TAL E QUAL chegou em `data/fotos/originais/AAAA-MM-DD/<id>.<ext>` (fora do
   Git): reconverter perdia qualidade e o original é a prova.
2. **Recortar** — o OpenCV procura os quadriláteros com forma de carta,
   endireita-os e grava `assets/cartas/<foto>-<n>.jpg` (488 × 680, JPEG 82, no
   Git, porque o site público também os mostra).
3. **Validar** — com o «sim» dele, uma cópia passa a validada e fica ligada ao
   recorte (`n_validacao`).

Decisões que não se leem do código:

- **Só as imagens de topo das mensagens `user`** (ruling R12). Dentro de um
  `tool_result` também há imagens — as capturas de ecrã das ferramentas —, e
  essas não são fotos dele.
- **A chave de uma foto é sessão + linha + índice** (`UNIQUE` na `n_foto`):
  extrair duas vezes a mesma imagem não cria duas fotos.
- **O recorte não adivinha.** Devolve as cartas que encontrou e quantas; se
  faltarem, quem chama diz-lho e pede outra foto. Um recorte inventado era uma
  validação contra uma imagem que não é a carta.
- **As validadas nunca passam a posse.** Uma descida abaixo delas desfaz a mais
  recente (`desfeita_em`) e a linha FICA: a ligação à foto não se perde. Se a
  mais recente tiver várias cópias e só sobrar uma a mais, a linha parte-se em
  duas (a parte que fica e a desfeita), para não desfazer mais do que a descida.
- **Uma foto que não bate certo não corrige nada sozinha.** Num deck, a edição
  e o acabamento da foto têm de ser os que contam para a carta; se não forem,
  `ValueError` com as duas, e o Claude pergunta-lhe antes de mudar a edição.

As funções que escrevem abrem a sua transação (`posse._transacao`), menos o
`aparar_validadas`, que corre DENTRO da transação de quem desce a posse (um
`with con:` aninhado fazia commit a meio da do chamador).

O `cv2` e o `numpy` importam-se dentro das funções que os usam: o `colecoes`
importa este módulo, e o `daily` no GitHub Actions corre sem o OpenCV — só o
recorte, que corre neste PC, precisa dele.
"""
from __future__ import annotations

import base64
import json
import sqlite3
from datetime import date
from pathlib import Path

from . import colecoes, posse

PASTA_ORIGINAIS = "data/fotos/originais"
PASTA_RECORTES = "assets/cartas"
LARGURA = 488
ALTURA = 680

# a razão lado curto / lado longo de uma carta é 63/88 ≈ 0,716; a margem cobre
# a perspetiva de uma foto tirada um pouco de lado
RAZAO_MIN, RAZAO_MAX = 0.62, 0.80
# abaixo disto é um pormenor da mesa, não uma carta (1,5 % da imagem)
AREA_MIN = 0.015
QUALIDADE_JPEG = 82

_EXTENSAO = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
             "image/webp": "webp", "image/gif": "gif"}


# ---------------------------------------------------------------------------
# Extrair do registo da sessão
# ---------------------------------------------------------------------------
def sessao_mais_recente(raiz_projetos: Path) -> Path:
    """O `.jsonl` mexido mais recentemente em `raiz_projetos/*/` (a sessão em
    curso é a que está a ser escrita). `ValueError` se não houver nenhum."""
    registos = list(Path(raiz_projetos).glob("*/*.jsonl"))
    if not registos:
        raise ValueError(f"não há registos de sessão em {raiz_projetos}")
    return max(registos, key=lambda p: p.stat().st_mtime)


def _extensao(media_type: str) -> str:
    if media_type in _EXTENSAO:
        return _EXTENSAO[media_type]
    sub = media_type.rsplit("/", 1)[-1]
    return "".join(c for c in sub if c.isalnum()) or "bin"


def imagens_da_sessao(jsonl: Path) -> list[dict]:
    """As imagens que ele mandou nesta sessão, pela ordem do registo:
    `{"linha", "indice", "media_type", "dados", "quando"}`.

    `linha` é o índice (desde 0) da linha no `.jsonl` e `indice` a posição da
    imagem no `message.content`. Uma linha que não se lê salta-se: a última
    pode estar a meio de ser escrita pela própria sessão.
    """
    imagens = []
    with open(jsonl, encoding="utf-8", errors="replace") as f:
        for linha, texto in enumerate(f):
            try:
                obj = json.loads(texto)
            except ValueError:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "user":
                continue
            msg = obj.get("message")
            conteudo = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(conteudo, list):
                continue        # um texto simples não traz imagens
            for indice, item in enumerate(conteudo):
                if not isinstance(item, dict) or item.get("type") != "image":
                    continue
                fonte = item.get("source") or {}
                if fonte.get("type") != "base64" or not fonte.get("data"):
                    continue
                try:
                    dados = base64.b64decode(fonte["data"])
                except ValueError:
                    continue
                imagens.append({
                    "linha": linha, "indice": indice,
                    "media_type": fonte.get("media_type") or "image/jpeg",
                    "dados": dados, "quando": obj.get("timestamp")})
    return imagens


def extrair(con: sqlite3.Connection, jsonl: Path, raiz: Path, *,
            ultimas: int = 1, para: str | None = None) -> list[dict]:
    """Grava as `ultimas` imagens da sessão que ainda não foram extraídas e
    devolve `[{"foto_id", "caminho"}]` das novas (vazio se já estavam todas).

    A janela são as `ultimas` imagens DO REGISTO, e só depois se tiram as já
    extraídas: repetir o comando não vai buscar fotos antigas que ele não quis.
    O `caminho` é relativo à `raiz`, com `/`. `para` é o deck ou a coleção a
    que a foto se destina, se ele o disse.
    """
    jsonl = Path(jsonl)
    sessao = jsonl.stem
    janela = imagens_da_sessao(jsonl)[-ultimas:] if ultimas > 0 else []
    dia = date.today().isoformat()
    novas = []
    with posse._transacao(con):
        for img in janela:
            if con.execute("SELECT 1 FROM n_foto WHERE sessao = ? AND linha = ?"
                           " AND indice = ?",
                           (sessao, img["linha"], img["indice"])).fetchone():
                continue
            fid = con.execute(
                "INSERT INTO n_foto (caminho, dia, sessao, linha, indice, para)"
                " VALUES ('', ?, ?, ?, ?, ?)",
                (dia, sessao, img["linha"], img["indice"], para)).lastrowid
            rel = (f"{PASTA_ORIGINAIS}/{dia}/{fid}."
                   f"{_extensao(img['media_type'])}")
            destino = Path(raiz) / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(img["dados"])
            con.execute("UPDATE n_foto SET caminho = ? WHERE id = ?", (rel, fid))
            novas.append({"foto_id": fid, "caminho": rel})
    return novas


# ---------------------------------------------------------------------------
# Recortar
# ---------------------------------------------------------------------------
def _cantos(quad):
    """Os quatro vértices por ordem TL, TR, BR, BL (sentido dos ponteiros, no
    eixo da imagem, com o y para baixo), em retrato: se o lado de cima for o
    longo, roda-se um vértice para o lado longo ficar na vertical."""
    import numpy as np                                          # noqa: PLC0415
    pts = np.asarray(quad, dtype=np.float32).reshape(4, 2)
    centro = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - centro[1], pts[:, 0] - centro[0])
    pts = pts[np.argsort(ang)]                   # esquerda → cima → direita → baixo
    tl = int(np.argmin(pts.sum(axis=1)))
    pts = np.roll(pts, -tl, axis=0)
    largura = np.linalg.norm(pts[1] - pts[0])
    altura = np.linalg.norm(pts[2] - pts[1])
    if largura > altura:
        pts = np.roll(pts, -1, axis=0)
    return pts


def _quadrilateros(img) -> list:
    """Os quadriláteros com forma de carta: cinzento → desfoque → Canny →
    contornos exteriores → `approxPolyDP` com 4 vértices convexos, área ≥ 1,5 %
    da imagem e razão dos lados entre 0,62 e 0,80."""
    import cv2                                                  # noqa: PLC0415
    import numpy as np                                          # noqa: PLC0415
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cinza = cv2.GaussianBlur(cinza, (5, 5), 0)
    bordas = cv2.Canny(cinza, 50, 150)
    # fechar os buracos da borda: um contorno partido não dá 4 vértices
    bordas = cv2.dilate(bordas, np.ones((3, 3), np.uint8), iterations=2)
    contornos, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    area_img = img.shape[0] * img.shape[1]
    achados = []
    for c in contornos:
        perimetro = cv2.arcLength(c, True)
        aprox = cv2.approxPolyDP(c, 0.02 * perimetro, True)
        if len(aprox) != 4 or not cv2.isContourConvex(aprox):
            continue
        if cv2.contourArea(aprox) < AREA_MIN * area_img:
            continue
        pts = _cantos(aprox)
        lados = [np.linalg.norm(pts[i] - pts[(i + 1) % 4]) for i in range(4)]
        curto = (lados[0] + lados[2]) / 2
        longo = (lados[1] + lados[3]) / 2
        if longo <= 0 or not RAZAO_MIN <= curto / longo <= RAZAO_MAX:
            continue
        achados.append(pts)
    return achados


def _por_filas(quads: list) -> list:
    """Ordem de leitura: por filas (centro y) e, dentro da fila, por x. Uma
    carta abre fila nova quando o centro dela está mais de meia altura de carta
    abaixo do da primeira da fila."""
    import numpy as np                                          # noqa: PLC0415
    if not quads:
        return []
    centros = [q.mean(axis=0) for q in quads]
    alturas = [np.linalg.norm(q[2] - q[1]) for q in quads]
    meia = float(np.median(alturas)) / 2
    ordem = sorted(range(len(quads)), key=lambda i: centros[i][1])
    filas: list[list[int]] = []
    for i in ordem:
        if filas and centros[i][1] - centros[filas[-1][0]][1] <= meia:
            filas[-1].append(i)
        else:
            filas.append([i])
    return [quads[i] for fila in filas
            for i in sorted(fila, key=lambda i: centros[i][0])]


def _ler_imagem(p: Path):
    # o `cv2.imread` falha em caminhos com «ç» no Windows: lê-se pelo numpy
    import cv2                                                  # noqa: PLC0415
    import numpy as np                                          # noqa: PLC0415
    try:
        buf = np.fromfile(str(p), np.uint8)
    except OSError:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR) if buf.size else None


def recortar(con: sqlite3.Connection, foto_id: int, raiz: Path) -> dict:
    """Recorta as cartas da foto e devolve `{"recortes": [{"id", "numero",
    "caminho"}], "encontradas": n}`.

    Cada carta vai endireitada para 488 × 680 em `raiz/assets/cartas/
    <foto_id>-<n>.jpg` (JPEG 82), por ordem de leitura. Repetir o recorte
    substitui os da foto com a mesma numeração (não duplica linhas) e tira os
    números que deixaram de existir. Sem cartas, `encontradas == 0` e nada se
    grava nem se apaga (os recortes de antes ficam).

    Uma foto que já validou cartas (validações ativas OU desfeitas) não se
    volta a recortar: `ValueError` e nada muda. Os recortes são a prova dessas
    validações, e um recorte novo com o mesmo número podia ser outra carta.
    """
    import cv2                                                  # noqa: PLC0415
    import numpy as np                                          # noqa: PLC0415
    r = con.execute("SELECT caminho FROM n_foto WHERE id = ?",
                    (foto_id,)).fetchone()
    if r is None:
        raise ValueError(f"foto desconhecida: {foto_id!r}")
    if con.execute("SELECT 1 FROM n_validacao v JOIN n_recorte c ON c.id ="
                   " v.recorte_id WHERE c.foto_id = ? LIMIT 1",
                   (foto_id,)).fetchone():
        raise ValueError(f"a foto {foto_id} já validou cartas; os recortes são"
                         " a prova: não se voltam a fazer")
    img = _ler_imagem(Path(raiz) / r[0])
    if img is None:
        raise ValueError(f"não consegui ler a foto {foto_id}: {r[0]}")
    quads = _por_filas(_quadrilateros(img))
    if not quads:
        return {"recortes": [], "encontradas": 0}
    destino = np.array([[0, 0], [LARGURA - 1, 0], [LARGURA - 1, ALTURA - 1],
                        [0, ALTURA - 1]], dtype=np.float32)
    recortes = []
    with posse._transacao(con):
        for n, q in enumerate(quads, start=1):
            m = cv2.getPerspectiveTransform(q.astype(np.float32), destino)
            carta = cv2.warpPerspective(img, m, (LARGURA, ALTURA))
            rel = f"{PASTA_RECORTES}/{foto_id}-{n}.jpg"
            p = Path(raiz) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            ok, buf = cv2.imencode(".jpg", carta,
                                   [cv2.IMWRITE_JPEG_QUALITY, QUALIDADE_JPEG])
            if not ok:
                raise ValueError(f"não consegui gravar o recorte {rel}")
            buf.tofile(str(p))
            con.execute(
                "INSERT INTO n_recorte (foto_id, numero, caminho) VALUES (?,?,?)"
                " ON CONFLICT (foto_id, numero) DO UPDATE SET caminho ="
                " excluded.caminho", (foto_id, n, rel))
            rid = con.execute("SELECT id FROM n_recorte WHERE foto_id = ? AND"
                              " numero = ?", (foto_id, n)).fetchone()[0]
            recortes.append({"id": rid, "numero": n, "caminho": rel})
        for rid, caminho in con.execute(
                "SELECT id, caminho FROM n_recorte WHERE foto_id = ? AND numero > ?",
                (foto_id, len(quads))).fetchall():
            con.execute("DELETE FROM n_recorte WHERE id = ?", (rid,))
            (Path(raiz) / caminho).unlink(missing_ok=True)
    return {"recortes": recortes, "encontradas": len(recortes)}


# ---------------------------------------------------------------------------
# Validar
# ---------------------------------------------------------------------------
def validadas(con: sqlite3.Connection, ambito: str, scryfall_id: str,
              acabamento: str, lingua: str = "en") -> int:
    """Quantas cópias estão validadas (a soma das validações não desfeitas).
    `ambito` é o GRAVADO: slug do deck, `rotativos` ou slug da coleção."""
    return con.execute(
        "SELECT COALESCE(SUM(qtd), 0) FROM n_validacao WHERE ambito = ? AND"
        " scryfall_id = ? AND acabamento = ? AND lingua = ? AND desfeita_em"
        " IS NULL", (ambito, scryfall_id, acabamento, lingua)).fetchone()[0]


def recorte_de(con: sqlite3.Connection, ambito: str, scryfall_id: str,
               acabamento: str, lingua: str = "en") -> str | None:
    """O caminho (`assets/cartas/…`) do recorte da validação ativa mais
    recente, ou `None` se não houver nenhuma."""
    r = con.execute(
        "SELECT r.caminho FROM n_validacao v JOIN n_recorte r ON r.id ="
        " v.recorte_id WHERE v.ambito = ? AND v.scryfall_id = ? AND"
        " v.acabamento = ? AND v.lingua = ? AND v.desfeita_em IS NULL"
        " ORDER BY v.em DESC, v.id DESC LIMIT 1",
        (ambito, scryfall_id, acabamento, lingua)).fetchone()
    return r[0] if r else None


def aparar_validadas(con: sqlite3.Connection, ambito: str, scryfall_id: str,
                     acabamento: str, lingua: str, posse_atual: int) -> int:
    """Enquanto as validadas passarem a `posse_atual`, desfaz a validação mais
    recente (`desfeita_em`; a linha fica). Devolve quantas CÓPIAS desfez.

    Como a posse que conta já desceu, «−1 tira primeiro uma por validar» sai
    daqui de graça: com 3 de posse e 2 validadas, descer para 2 não desfaz
    nada. Corre dentro da transação de quem desceu a posse.
    """
    a_mais = validadas(con, ambito, scryfall_id, acabamento, lingua) \
        - max(0, int(posse_atual))
    if a_mais <= 0:
        return 0
    agora = posse._agora()
    desfeitas = 0
    for vid, qtd in con.execute(
            "SELECT id, qtd FROM n_validacao WHERE ambito = ? AND scryfall_id = ?"
            " AND acabamento = ? AND lingua = ? AND desfeita_em IS NULL"
            " ORDER BY em DESC, id DESC",
            (ambito, scryfall_id, acabamento, lingua)).fetchall():
        if a_mais <= 0:
            break
        if qtd <= a_mais:
            con.execute("UPDATE n_validacao SET desfeita_em = ? WHERE id = ?",
                        (agora, vid))
            sai = qtd
        else:
            # parte-se a linha: fica a parte que ainda cabe, e a desfeita é uma
            # cópia dela com a mesma foto e a mesma data, para a ligação ficar
            sai = a_mais
            con.execute("UPDATE n_validacao SET qtd = ? WHERE id = ?",
                        (qtd - sai, vid))
            con.execute(
                "INSERT INTO n_validacao (recorte_id, ambito, scryfall_id,"
                " acabamento, lingua, qtd, em, desfeita_em) SELECT recorte_id,"
                " ambito, scryfall_id, acabamento, lingua, ?, em, ? FROM"
                " n_validacao WHERE id = ?", (sai, agora, vid))
        a_mais -= sai
        desfeitas += sai
    return desfeitas


def _e_deck(con, slug: str) -> bool:
    return con.execute("SELECT 1 FROM n_deck WHERE slug = ?",
                       (slug,)).fetchone() is not None


def _e_colecao(con, slug: str) -> bool:
    return con.execute("SELECT 1 FROM n_colecao WHERE slug = ?",
                       (slug,)).fetchone() is not None


def _nome_da_impressao(con, scryfall_id: str) -> str:
    r = con.execute("SELECT name FROM cards WHERE scryfall_id = ?",
                    (scryfall_id,)).fetchone()
    if r is None:
        raise ValueError(f"o catálogo não tem a impressão {scryfall_id!r}")
    return r[0]


def _carta_colecao(con, slug: str, scryfall_id: str, acabamento: str,
                   lingua: str):
    return con.execute(
        "SELECT id, tenho FROM n_colecao_carta WHERE colecao = ? AND"
        " scryfall_id = ? AND acabamento = ? AND lingua = ?",
        (slug, scryfall_id, acabamento, lingua)).fetchone()


def _preparar_validacao(con, recorte_id, ambito, scryfall_id, acabamento,
                        lingua, qtd, registar, pendentes) -> dict:
    """Todas as verificações de uma validação, SEM escrever nada. Devolve o que
    `validar` precisa para escrever: o âmbito gravado, a língua, a posse que
    contará (já com a que `registar` vai somar), as validadas de agora e a
    função `somar` que regista a posse."""
    qtd = int(qtd)
    if qtd <= 0:
        raise ValueError(f"a quantidade tem de ser positiva: {qtd}")
    if acabamento not in posse.ACABAMENTOS:
        raise ValueError(f"acabamento inválido: {acabamento!r} (nonfoil | foil)")
    if con.execute("SELECT 1 FROM n_recorte WHERE id = ?",
                   (recorte_id,)).fetchone() is None:
        raise ValueError(f"recorte desconhecido: {recorte_id!r}")
    ativa = con.execute(
        "SELECT ambito, scryfall_id, acabamento FROM n_validacao WHERE"
        " recorte_id = ? AND desfeita_em IS NULL", (recorte_id,)).fetchone()
    if ativa is not None:
        raise ValueError(f"o recorte {recorte_id} já está validado"
                         f" ({ativa[0]}: {ativa[1]} {ativa[2]})")
    request_id = f"foto-{recorte_id}-{ambito}-{scryfall_id}-{acabamento}"

    if _e_deck(con, ambito):
        nome = _nome_da_impressao(con, scryfall_id)
        conta = posse.edicao(con, ambito, nome)
        if conta != (scryfall_id, acabamento):
            atual = f"{conta[0]} {conta[1]}" if conta else "nenhuma"
            raise ValueError(
                f"a foto é {scryfall_id} {acabamento}, mas em {ambito!r} a"
                f" {nome!r} conta na edição {atual}: pergunta antes de mudar")
        amb = posse.ambito(con, ambito, nome)
        lingua = "en"           # a posse dos decks não tem língua
        tem = posse._qtd(con, amb, conta)
        ja = con.execute("SELECT 1 FROM n_posse_log WHERE request_id = ?",
                         (request_id,)).fetchone()

        def somar():
            posse.ajustar(con, ambito, nome, qtd, request_id=request_id)
    elif _e_colecao(con, ambito):
        c = _carta_colecao(con, ambito, scryfall_id, acabamento, lingua)
        if c is None:
            raise ValueError(f"{scryfall_id} {acabamento} {lingua} não está na"
                             f" coleção {ambito!r}")
        amb, tem = ambito, c["tenho"]
        ja = con.execute("SELECT 1 FROM n_colecao_log WHERE request_id = ?",
                         (request_id,)).fetchone()

        def somar():
            colecoes.ajustar(con, c["id"], qtd, request_id=request_id)
    else:
        raise ValueError(f"nem deck nem coleção: {ambito!r}")

    somou = registar and not ja
    if somou:
        tem += qtd
    chave = (amb, scryfall_id, acabamento, lingua)
    # o que as linhas anteriores do lote vão escrever e ainda não está na base
    pend_val = pend_pos = 0
    if pendentes is not None:
        pend_val = pendentes.get(("validadas", chave), 0)
        pend_pos = pendentes.get(("posse", chave), 0)
    tem += pend_pos
    ja_validadas = validadas(con, amb, scryfall_id, acabamento, lingua)         + pend_val
    if ja_validadas + qtd > tem:
        raise ValueError(f"só tens {tem} ({ja_validadas} já validadas):"
                         f" não dá para validar mais {qtd}")
    if pendentes is not None:
        pendentes[("validadas", chave)] = pend_val + qtd
        if somou:
            pendentes[("posse", chave)] = pend_pos + qtd
    return {"amb": amb, "lingua": lingua, "tem": tem, "qtd": qtd,
            "validadas": ja_validadas + qtd, "somou": bool(somou),
            "somar": somar}


def verificar_validacao(con: sqlite3.Connection, recorte_id: int, ambito: str,
                        scryfall_id: str, acabamento: str, lingua: str = "en",
                        qtd: int = 1, *, registar: bool = False,
                        pendentes: dict | None = None) -> dict:
    """As mesmas verificações do `validar`, sem escrever nada: levanta
    `ValueError` se a validação seria recusada e devolve `{"ambito", "lingua",
    "posse", "validadas", "soma_posse"}` se passaria.

    Existe para o lote (`nucleo validar --lote`) conferir todas as linhas ANTES
    de gravar a primeira; o `validar` usa a mesma verificação, por isso as
    regras vivem num sítio só. `pendentes` é um dicionário que o lote passa a
    todas as linhas: guarda o que as linhas anteriores vão acrescentar a cada
    carta (validadas e posse) e que ainda não está na base, para duas linhas
    sobre a mesma carta se conferirem juntas. Só se atualiza se a linha passar.
    """
    r = _preparar_validacao(con, recorte_id, ambito, scryfall_id, acabamento,
                            lingua, qtd, registar, pendentes)
    return {"ambito": r["amb"], "lingua": r["lingua"], "posse": r["tem"],
            "validadas": r["validadas"], "soma_posse": r["somou"]}


def validar(con: sqlite3.Connection, recorte_id: int, ambito: str,
            scryfall_id: str, acabamento: str, lingua: str = "en",
            qtd: int = 1, *, registar: bool = False) -> dict:
    """Liga `qtd` cópias desta carta ao recorte, como validadas, e devolve
    `{"validacao_id", "ambito", "validadas", "posse"}`.

    `ambito` é aquilo para que a foto era: o slug de um deck (`n_deck`) ou de
    uma coleção (`n_colecao`); outra coisa levanta. Num deck, a impressão e o
    acabamento têm de ser os que contam (`posse.edicao`), senão `ValueError`
    com as duas — mudar a edição é decisão dele —; o âmbito GRAVADO é o da
    posse (o slug, ou `rotativos` numa partilhada) e a língua é `en`. Numa
    coleção a carta tem de lá estar (`n_colecao_carta`; na Reserved List o
    `colecoes.juntar` vem primeiro) e o âmbito gravado é o slug.

    `registar=True` é «registar por foto»: soma primeiro `qtd` à posse (com um
    `request_id` derivado do recorte, por isso repetir não soma duas vezes).
    Depois a regra: as validadas ativas mais `qtd` não passam a posse
    («só tens N»). Um recorte é uma carta: com uma validação dele ativa, não se
    valida outra vez.

    A verificação faz-se ANTES de somar a posse: o `ajustar` faz o seu próprio
    commit, e uma validação recusada depois dele deixava uma cópia registada
    sem foto nenhuma.
    """
    r = _preparar_validacao(con, recorte_id, ambito, scryfall_id, acabamento,
                            lingua, qtd, registar, None)
    if registar:
        r["somar"]()
    with posse._transacao(con):
        vid = con.execute(
            "INSERT INTO n_validacao (recorte_id, ambito, scryfall_id,"
            " acabamento, lingua, qtd, em) VALUES (?,?,?,?,?,?,?)",
            (recorte_id, r["amb"], scryfall_id, acabamento, r["lingua"],
             r["qtd"], posse._agora())).lastrowid
    return {"validacao_id": vid, "ambito": r["amb"],
            "validadas": r["validadas"], "posse": r["tem"]}
