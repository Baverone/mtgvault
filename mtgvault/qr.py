"""Códigos QR em Python puro — para o link do MODO EDIÇÃO no telemóvel.

Porque não uma biblioteca (André, 2026-09-08: *"ele vai estar à frente da
estante com o telemóvel"*): o `webapp.py` já é `http.server` da biblioteca
padrão de propósito, e este vault corre num PC de casa e no GitHub Actions. Uma
dependência nova para desenhar um quadrado preto e branco pagava-se todos os dias
em instalações e não se paga uma única vez. O `qrcode`, quando está instalado,
continua a servir para o QR em ASCII na consola; a página não depende dele.

O que está implementado: **modo byte, nível de correcção M, versões 1 a 10** — o
suficiente com folga para um `http://192.168.1.70:8771/?t=<32 hex>` (54 bytes,
versão 4). O resto da norma (modos numérico/alfanumérico, versões acima de 10,
ECI) não entra: código que ninguém corre é código que ninguém corrige.

Referência: ISO/IEC 18004. O `test_qr.py` compara a matriz, quando a biblioteca
`qrcode` está instalada, com a dela — é a verificação que importa, porque um QR
"quase certo" não dá erro nenhum: dá um quadrado que o telemóvel não lê.
"""
from __future__ import annotations

# (versão): (total de codewords, EC codewords por bloco, [(nº blocos, data cw)])
# Nível M. Os números são a tabela 13-22 da norma; o `test_qr` confere a soma.
TABELA_M: dict[int, tuple[int, int, list[tuple[int, int]]]] = {
    1: (26, 10, [(1, 16)]),
    2: (44, 16, [(1, 28)]),
    3: (70, 26, [(1, 44)]),
    4: (100, 18, [(2, 32)]),
    5: (134, 24, [(2, 43)]),
    6: (172, 16, [(4, 27)]),
    7: (196, 18, [(4, 31)]),
    8: (242, 22, [(2, 38), (2, 39)]),
    9: (292, 22, [(3, 36), (2, 37)]),
    10: (346, 26, [(4, 43), (1, 44)]),
}
# Centros dos padrões de alinhamento, por versão.
ALINHAMENTO: dict[int, list[int]] = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}
NIVEL_M = 0b00          # os dois bits de nível de correcção do format info
MASCARAS = [
    lambda i, j: (i + j) % 2 == 0,
    lambda i, j: i % 2 == 0,
    lambda i, j: j % 3 == 0,
    lambda i, j: (i + j) % 3 == 0,
    lambda i, j: (i // 2 + j // 3) % 2 == 0,
    lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
]

# ---------------------------------------------------------------------------
# GF(256) — a aritmética dos códigos Reed-Solomon
# ---------------------------------------------------------------------------
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D                      # o polinómio primitivo da norma
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _gerador(n: int) -> list[int]:
    """O polinómio gerador de grau `n`: o produto de (x + α^i), i em 0..n-1.

    Coeficientes do maior grau para o menor. Multiplicar por (x + α^i) é somar o
    polinómio deslocado com o polinómio escalado — e o ciclo desce de propósito,
    para cada passo usar os coeficientes ANTIGOS.
    """
    g = [1]
    for i in range(n):
        g.append(0)
        for k in range(len(g) - 1, 0, -1):
            g[k] ^= _mul(g[k - 1], _EXP[i])
    return g


def _ec(dados: list[int], n: int) -> list[int]:
    """Os `n` codewords de correcção de um bloco de dados."""
    g = _gerador(n)
    resto = list(dados) + [0] * n
    for i in range(len(dados)):
        c = resto[i]
        if c:
            for j in range(len(g)):
                resto[i + j] ^= _mul(g[j], c)
    return resto[len(dados):]


# ---------------------------------------------------------------------------
# Codificação
# ---------------------------------------------------------------------------
def _capacidade(v: int) -> int:
    """Quantos BYTES de conteúdo cabem na versão `v` (modo byte, nível M)."""
    _tot, _ecb, blocos = TABELA_M[v]
    dados = sum(n * d for n, d in blocos)
    cabecalho = 4 + (8 if v < 10 else 16)
    return dados - (cabecalho + 7) // 8


def versao_para(texto: str | bytes) -> int:
    b = texto.encode("utf-8") if isinstance(texto, str) else texto
    for v in sorted(TABELA_M):
        if len(b) <= _capacidade(v):
            return v
    raise ValueError(f"{len(b)} bytes é mais do que a versão 10 leva "
                     f"({_capacidade(10)}) — este módulo pára aqui de propósito")


def _codewords(b: bytes, v: int) -> list[int]:
    """O conteúdo já em codewords, com correcção de erros e intercalado."""
    bits: list[int] = []

    def junta(valor: int, n: int):
        bits.extend((valor >> (n - 1 - k)) & 1 for k in range(n))

    junta(0b0100, 4)                                  # modo byte
    junta(len(b), 8 if v < 10 else 16)
    for x in b:
        junta(x, 8)
    total_dados = sum(n * d for n, d in TABELA_M[v][2])
    junta(0, min(4, total_dados * 8 - len(bits)))      # terminador
    bits.extend([0] * (-len(bits) % 8))                # fecha o byte
    dados = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    for i in range(total_dados - len(dados)):          # bytes de enchimento
        dados.append(0xEC if i % 2 == 0 else 0x11)

    n_ec = TABELA_M[v][1]
    blocos_d, blocos_e, k = [], [], 0
    for n, d in TABELA_M[v][2]:
        for _ in range(n):
            blocos_d.append(dados[k:k + d])
            blocos_e.append(_ec(blocos_d[-1], n_ec))
            k += d
    out: list[int] = []
    for i in range(max(len(x) for x in blocos_d)):
        out += [x[i] for x in blocos_d if i < len(x)]
    for i in range(n_ec):
        out += [x[i] for x in blocos_e]
    return out


# ---------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------
def _bch(valor: int, gerador: int, grau: int) -> int:
    """O resto BCH de `valor` — a correcção de erros do format/version info."""
    d = valor << grau
    while d.bit_length() > grau:
        d ^= gerador << (d.bit_length() - gerador.bit_length())
    return d


def _formato(mascara: int) -> int:
    v = (NIVEL_M << 3) | mascara
    return ((v << 10) | _bch(v, 0b10100110111, 10)) ^ 0b101010000010010


def _versao_bits(v: int) -> int:
    return (v << 12) | _bch(v, 0b1111100100101, 12)


def matriz(texto: str | bytes, versao: int | None = None,
           mascara: int | None = None) -> list[list[int]]:
    """A matriz do QR: 1 = módulo escuro. Sem a margem branca (ver `svg`).

    `mascara` força uma das oito (é o que o teste usa para comparar com a
    biblioteca de referência); por omissão escolhe-se a de menor penalização,
    como a norma manda.
    """
    b = texto.encode("utf-8") if isinstance(texto, str) else texto
    v = versao or versao_para(b)
    n = 17 + 4 * v
    m = [[None] * n for _ in range(n)]          # None = ainda livre

    def quadrado(r, c, tamanho, borda=True):
        for i in range(tamanho):
            for j in range(tamanho):
                if 0 <= r + i < n and 0 <= c + j < n:
                    m[r + i][c + j] = 0
        if not borda:
            return
        for i in range(tamanho):
            for j in range(tamanho):
                anel = min(i, j, tamanho - 1 - i, tamanho - 1 - j)
                # Anéis escuro/claro de fora para dentro. O `anel >= 3` é o
                # centro do localizador 7×7, que é o bloco 3×3 escuro inteiro —
                # com `anel % 2` sozinho o módulo do meio saía branco e o
                # telemóvel não encontrava o código.
                m[r + i][c + j] = 1 if anel % 2 == 0 or anel >= 3 else 0

    for r, c in ((0, 0), (0, n - 7), (n - 7, 0)):      # localizadores
        quadrado(r, c, 7)
        for i in range(-1, 8):                          # separadores
            for j in range(-1, 8):
                if 0 <= r + i < n and 0 <= c + j < n and not (0 <= i < 7 and 0 <= j < 7):
                    m[r + i][c + j] = 0
    for i in range(8, n - 8):                           # padrões de tempo
        m[6][i] = m[i][6] = 1 - i % 2
    centros = ALINHAMENTO[v]
    for r in centros:
        for c in centros:
            if (r < 8 and c < 8) or (r < 8 and c > n - 9) or (r > n - 9 and c < 8):
                continue
            quadrado(r - 2, c - 2, 5)
    m[n - 8][8] = 1                                     # módulo escuro
    for i in range(9):                                  # reservas do format info
        if m[8][i] is None:
            m[8][i] = 0
        if m[i][8] is None:
            m[i][8] = 0
    for i in range(8):
        m[8][n - 1 - i] = m[n - 1 - i][8] = 0
    if v >= 7:                                          # reservas do version info
        for i in range(6):
            for j in range(3):
                m[n - 11 + j][i] = m[i][n - 11 + j] = 0

    reservado = [[c is not None for c in linha] for linha in m]
    dados = _codewords(b, v)
    bits = [(x >> (7 - k)) & 1 for x in dados for k in range(8)]
    # Colocação em zigue-zague: colunas de duas em duas, da direita para a
    # esquerda, a subir e a descer alternadamente. A coluna 6 salta-se (é o
    # padrão de tempo vertical).
    k, coluna, subindo = 0, n - 1, True
    while coluna > 0:
        if coluna == 6:
            coluna -= 1                   # a coluna 6 é o padrão de tempo
        for passo in range(n):
            linha = (n - 1 - passo) if subindo else passo
            for c in (coluna, coluna - 1):
                if not reservado[linha][c]:
                    m[linha][c] = bits[k] if k < len(bits) else 0
                    k += 1
        subindo = not subindo
        coluna -= 2

    melhor, melhor_nota = None, None
    for mask in (range(8) if mascara is None else (mascara,)):
        cand = [[(v_ ^ 1) if (not reservado[i][j] and MASCARAS[mask](i, j)) else v_
                 for j, v_ in enumerate(linha)] for i, linha in enumerate(m)]
        _escreve_formato(cand, v, mask)
        nota = _penalizacao(cand)
        if melhor_nota is None or nota < melhor_nota:
            melhor, melhor_nota = cand, nota
    return melhor


def _escreve_formato(m, v, mask):
    """As duas cópias do format info (15 bits) e, na v7+, do version info.

    O mapeamento é o da implementação de referência da norma, com `i` a contar do
    bit menos significativo. Escrito à mão dá-se um bit trocado — e um format
    info errado faz o leitor desistir do código inteiro sem dizer porquê.
    """
    n = len(m)
    f = _formato(mask)
    for i in range(15):
        bit = (f >> i) & 1
        if i < 6:                                  # cópia 1, vertical
            m[i][8] = bit
        elif i < 8:
            m[i + 1][8] = bit
        else:                                      # cópia 2, vertical
            m[n - 15 + i][8] = bit
        if i < 8:                                  # cópia 2, horizontal
            m[8][n - i - 1] = bit
        elif i == 8:
            m[8][7] = bit
        else:                                      # cópia 1, horizontal
            m[8][15 - i - 1] = bit
    m[n - 8][8] = 1                                # módulo escuro
    if v >= 7:
        vb = _versao_bits(v)
        for i in range(18):
            bit = (vb >> i) & 1
            m[n - 11 + i % 3][i // 3] = bit
            m[i // 3][n - 11 + i % 3] = bit


def _penalizacao(m) -> int:
    n = len(m)
    total = 0
    linhas = [list(r) for r in m] + [[m[i][j] for i in range(n)] for j in range(n)]
    for linha in linhas:                                # regra 1: corridas
        corrida, anterior = 0, None
        for x in linha:
            if x == anterior:
                corrida += 1
            else:
                if corrida >= 5:
                    total += 3 + corrida - 5
                corrida, anterior = 1, x
        if corrida >= 5:
            total += 3 + corrida - 5
    for i in range(n - 1):                              # regra 2: blocos 2x2
        for j in range(n - 1):
            if m[i][j] == m[i][j + 1] == m[i + 1][j] == m[i + 1][j + 1]:
                total += 3
    # Regra 3: o padrão 1:1:3:1:1 (o do localizador) com quatro módulos claros de
    # um dos lados — 40 por cada lado que cumpra, e vale também encostado à
    # borda. É como a implementação de referência o conta, e a escolha da máscara
    # depende do total: contá-lo de outra maneira dá um QR igualmente válido mas
    # diferente do de qualquer outra ferramenta, e uma diferença dessas não se
    # distingue de um erro.
    padrao = [1, 0, 1, 1, 1, 0, 1]
    for linha in linhas:
        for i in range(n - 6):
            if linha[i:i + 7] != padrao:
                continue
            if i + 7 >= n or not any(linha[i + 7:i + 11]):
                total += 40
            if i - 4 < 0 or not any(linha[i - 4:i]):
                total += 40
    escuros = sum(sum(r) for r in m)
    total += 10 * (abs(escuros * 100 // (n * n) - 50) // 5)  # regra 4: equilíbrio
    return total


# ---------------------------------------------------------------------------
# Saídas
# ---------------------------------------------------------------------------
def svg(texto: str, escala: int = 6, margem: int = 4, fundo: str = "#ffffff",
        frente: str = "#000000") -> str:
    """O QR como SVG — é o que a página do modo edição mostra num `<img>`.

    Fundo BRANCO mesmo numa página escura, e com a margem de 4 módulos que a
    norma pede: um QR desenhado a claro sobre escuro, ou sem margem, é lido por
    alguns telemóveis e por outros não — e o que falha não diz porquê.
    """
    m = matriz(texto)
    n = len(m)
    lado = (n + 2 * margem) * escala
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" '
              f'height="{lado}" viewBox="0 0 {n + 2 * margem} {n + 2 * margem}" '
              f'shape-rendering="crispEdges" role="img" '
              f'aria-label="QR do link do modo edição">',
              f'<rect width="100%" height="100%" fill="{fundo}"/>',
              f'<g fill="{frente}">']
    for i, linha in enumerate(m):
        j = 0
        while j < n:
            if linha[j]:
                largura = 1
                while j + largura < n and linha[j + largura]:
                    largura += 1
                partes.append(f'<rect x="{j + margem}" y="{i + margem}" '
                              f'width="{largura}" height="1"/>')
                j += largura
            else:
                j += 1
    partes.append("</g></svg>")
    return "".join(partes)


def ascii_arte(texto: str, margem: int = 2) -> str:
    """O QR em blocos de meia-altura, para a consola (dois módulos por linha)."""
    m = matriz(texto)
    n = len(m)
    linhas = ([[0] * (n + 2 * margem)] * margem
              + [[0] * margem + linha + [0] * margem for linha in m]
              + [[0] * (n + 2 * margem)] * margem)
    out = []
    for i in range(0, len(linhas), 2):
        cima = linhas[i]
        baixo = linhas[i + 1] if i + 1 < len(linhas) else [0] * len(cima)
        # Invertido: a consola tem fundo escuro, e o QR precisa do contrário.
        out.append("".join({(0, 0): "█", (1, 0): "▄", (0, 1): "▀", (1, 1): " "}[
            (c, b)] for c, b in zip(cima, baixo)))
    return "\n".join(out)
