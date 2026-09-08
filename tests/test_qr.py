"""O QR do link do modo edição (`mtgvault/qr.py`), em Python puro.

Um QR "quase certo" não dá erro nenhum: dá um quadrado que o telemóvel não lê. E
o telemóvel não diz porquê. Por isso este ficheiro verifica-o de três maneiras
independentes:

  1. **lê-se a si próprio.** Desfaz a máscara, lê o format info, tira os
     codewords, desintercala os blocos e descodifica o segmento — e tem de sair o
     texto original. É a prova que não depende de mais nada;
  2. **bate certo com a implementação de referência.** Quando a biblioteca
     `qrcode` está instalada (é opcional — o `webapp` só a usa para o QR na
     consola), a matriz tem de ser IGUAL à dela, nas oito máscaras. Sem ela, o
     caso salta e di-lo, em vez de fingir que passou;
  3. **a estrutura está lá**: tamanho certo, três localizadores, padrões de
     tempo alternados e o módulo escuro.

Não toca na rede.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import qr  # noqa: E402

URL = "http://192.168.1.70:8771/?t=0123456789abcdef0123456789abcdef"
CASOS = ["oi", URL, "http://localhost:8771/", "acentuação e €",
         "x" * 40, "y" * 100, "z" * 213]


# ---------------------------------------------------------------------------
# 1. o descodificador do teste (independente do que o módulo faz)
# ---------------------------------------------------------------------------
def _ler(m):
    """Lê uma matriz de QR (byte mode, nível M) de volta para texto."""
    n = len(m)
    v = (n - 17) // 4
    # O format info diz a máscara; lê-se da primeira cópia (bits 0..14).
    bits = []
    for i in range(15):
        bits.append(m[i][8] if i < 6 else m[i + 1][8] if i < 8
                    else m[n - 15 + i][8])
    valor = sum(b << i for i, b in enumerate(bits)) ^ 0b101010000010010
    mascara = (valor >> 10) & 0b111
    assert (valor >> 13) & 0b11 == qr.NIVEL_M, "o nivel de correccao nao e M"

    # As mesmas reservas do desenhador, para saber quais são os módulos de dados.
    reservado = [[False] * n for _ in range(n)]

    def marca(r, c, t):
        for i in range(t):
            for j in range(t):
                if 0 <= r + i < n and 0 <= c + j < n:
                    reservado[r + i][c + j] = True

    for r, c in ((0, 0), (0, n - 7), (n - 7, 0)):
        marca(r - 1, c - 1, 9)
    for i in range(n):
        reservado[6][i] = reservado[i][6] = True
    for r in qr.ALINHAMENTO[v]:
        for c in qr.ALINHAMENTO[v]:
            if (r < 8 and c < 8) or (r < 8 and c > n - 9) or (r > n - 9 and c < 8):
                continue
            marca(r - 2, c - 2, 5)
    for i in range(9):
        reservado[8][i] = reservado[i][8] = True
    for i in range(8):
        reservado[8][n - 1 - i] = reservado[n - 1 - i][8] = True
    if v >= 7:
        for i in range(6):
            for j in range(3):
                reservado[n - 11 + j][i] = reservado[i][n - 11 + j] = True

    dados, coluna, subindo = [], n - 1, True
    while coluna > 0:
        if coluna == 6:
            coluna -= 1
        for passo in range(n):
            linha = (n - 1 - passo) if subindo else passo
            for c in (coluna, coluna - 1):
                if not reservado[linha][c]:
                    x = m[linha][c]
                    if qr.MASCARAS[mascara](linha, c):
                        x ^= 1
                    dados.append(x)
        subindo = not subindo
        coluna -= 2
    cw = [int("".join(map(str, dados[i:i + 8])), 2)
          for i in range(0, len(dados) - 7, 8)]

    # Desintercalar: a ordem inversa da do `_codewords`.
    n_ec, blocos = qr.TABELA_M[v][1], qr.TABELA_M[v][2]
    tamanhos = [d for nb, d in blocos for _ in range(nb)]
    saida = [[] for _ in tamanhos]
    k = 0
    for i in range(max(tamanhos)):
        for j, t in enumerate(tamanhos):
            if i < t:
                saida[j].append(cw[k])
                k += 1
    fluxo = [x for b in saida for x in b]
    bits = [(x >> (7 - i)) & 1 for x in fluxo for i in range(8)]
    assert bits[:4] == [0, 1, 0, 0], "nao e o modo byte"
    largura = 8 if v < 10 else 16
    quantos = int("".join(map(str, bits[4:4 + largura])), 2)
    inicio = 4 + largura
    corpo = bytes(int("".join(map(str, bits[inicio + i * 8:inicio + i * 8 + 8])), 2)
                  for i in range(quantos))
    return corpo.decode("utf-8")


def caso_o_qr_le_se_a_si_proprio():
    for texto in CASOS:
        m = qr.matriz(texto)
        lido = _ler(m)
        assert lido == texto, (texto[:30], lido[:30])
    print(f"{len(CASOS)} codigos descodificados de volta ao texto original")


def caso_igual_a_implementacao_de_referencia():
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError:
        print("(sem a biblioteca `qrcode` instalada — comparacao saltada)")
        return
    total = 0
    for texto in CASOS:
        b = texto.encode("utf-8")
        v = qr.versao_para(b)
        for mascara in range(8):
            q = qrcode.QRCode(version=v, error_correction=ERROR_CORRECT_M,
                              border=0, mask_pattern=mascara)
            q.add_data(b, optimize=0)     # sem optimize: um segmento byte, como nós
            q.make(fit=False)
            ref = [[1 if c else 0 for c in linha] for linha in q.modules]
            assert qr.matriz(texto, mascara=mascara) == ref, (texto[:20], mascara)
            total += 1
    print(f"{total} matrizes iguais as da biblioteca de referencia (v1 a v10)")


def caso_a_estrutura_esta_la():
    m = qr.matriz(URL)
    n = len(m)
    assert n == 17 + 4 * qr.versao_para(URL) and n == 33, n
    for r, c in ((0, 0), (0, n - 7), (n - 7, 0)):
        # Localizador: anel escuro, anel claro, 3x3 escuro. O centro é escuro —
        # com `anel % 2` sozinho saía branco e o leitor nao encontrava o codigo.
        assert m[r][c] == 1 and m[r + 1][c + 1] == 0 and m[r + 3][c + 3] == 1
    assert all(m[6][i] == 1 - i % 2 for i in range(8, n - 8)), "padrao de tempo"
    assert m[n - 8][8] == 1, "modulo escuro"
    print(f"estrutura: {n}x{n}, tres localizadores, tempo e modulo escuro")


def caso_a_versao_cresce_com_o_texto():
    assert qr.versao_para("oi") == 1
    assert qr.versao_para(URL) == 4, qr.versao_para(URL)
    assert qr.versao_para("z" * 213) == 10
    try:
        qr.versao_para("z" * 400)
    except ValueError as e:
        assert "versão 10" in str(e), e
    else:
        raise AssertionError("acima da versao 10 tem de dizer que nao cabe")
    print("versao: 1 para 'oi', 4 para o link do modo edicao, 10 no maximo")


def caso_o_svg_desenha_se():
    s = qr.svg(URL)
    assert s.startswith("<svg") and s.endswith("</svg>")
    assert 'fill="#ffffff"' in s, "o fundo tem de ser BRANCO, mesmo numa pagina escura"
    assert s.count("<rect") > 20 and 'viewBox="0 0 41 41"' in s, s[:200]
    assert "aria-label" in s, "sem rotulo, um leitor de ecra le 'imagem'"
    # O ASCII (para a consola) também tem de sair sem rebentar.
    arte = qr.ascii_arte(URL)
    assert len(arte.splitlines()) >= 18 and "█" in arte
    print("svg com margem e fundo branco, e o ascii para a consola")


def run():
    for fn in (caso_o_qr_le_se_a_si_proprio, caso_igual_a_implementacao_de_referencia,
               caso_a_estrutura_esta_la, caso_a_versao_cresce_com_o_texto,
               caso_o_svg_desenha_se):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
