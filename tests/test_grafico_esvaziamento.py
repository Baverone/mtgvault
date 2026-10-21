"""O gráfico da Galeria marca o ESVAZIAMENTO da colecção e não calcula
percentagens por cima dele (2026-10-21).

A 13/10 a `copies` foi esvaziada e reconstrói-se pelas fotos. No `value_history`
dele o ponto de 13/10 ainda é a colecção antiga (133 496,67 €) e o de 14/10 já é
0 €: uma variação de ponta a ponta dizia ≈ −99,9 %, uma queda que não é mercado.

O que aqui se tranca, com séries SINTÉTICAS (os números imitam a forma da base
dele, não são lidos dela):
  1. só pontos ANTERIORES: sem marcador, percentagem normal;
  2. só pontos POSTERIORES: sem marcador, percentagem normal — e base a 0 € dá
     «sem variação» em vez de um 0 % inventado;
  3. série MISTA: marcador, linha partida em dois troços, nota, e a percentagem
     é só do troço posterior (ou omitida se ele não a permite);
  4. o histórico fica intacto: o `build(historico=False)` não lhe toca e o
     desenho não muda a lista que recebe.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps({
    "caixas": [], "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_colecao": {}, "spml_formatos": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
}, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db  # noqa: E402
import collection_gallery as cg  # noqa: E402

E = cg.ESVAZIAMENTO   # 2026-10-13, último dia da colecção antiga

ANTES = [("2026-10-05", 135782.25), ("2026-10-07", 133464.55),
         ("2026-10-12", 132858.30), (E, 133496.67)]
DEPOIS_ZERO = [("2026-10-14", 0.0), ("2026-10-20", 0.0), ("2026-10-21", 152.67)]
DEPOIS = [("2026-10-21", 152.67), ("2026-10-22", 160.00)]


def _indicador(bloco):
    return re.search(r'<span class="evo-ind[^"]*">(.*?)</span></div>', bloco).group(1)


def caso_so_pontos_anteriores():
    bloco = cg._evo_block(ANTES)
    assert cg._esvaziamento([d for d, _ in ANTES]) is None
    assert 'class="esvaziamento"' not in bloco and "foi esvaziada" not in bloco
    assert bloco.count("<polyline") == 1
    assert "−1,7 %" in _indicador(bloco) and "desde 2026-10-05" in bloco, _indicador(bloco)
    print("so antes: sem marcador, percentagem normal")


def caso_so_pontos_posteriores():
    bloco = cg._evo_block(DEPOIS)
    assert cg._esvaziamento([d for d, _ in DEPOIS]) is None
    assert 'class="esvaziamento"' not in bloco
    assert "+4,8 %" in _indicador(bloco), _indicador(bloco)
    # A colecção a recomeçar do zero: um 0 € de base não dá percentagem.
    zero = cg._evo_block(DEPOIS_ZERO)
    ind = _indicador(zero)
    assert "%" not in ind and "sem variação" in ind and "0 €" in ind, ind
    print("so depois: sem marcador; base a zero sem percentagem")


def caso_serie_mista():
    serie = ANTES + DEPOIS_ZERO
    dates = [d for d, _ in serie]
    assert cg._esvaziamento(dates) == len(ANTES)
    bloco = cg._evo_block(serie)
    assert bloco.count('class="esvaziamento"') == 1
    assert f"foi esvaziada a {E}" in bloco
    assert bloco.count("<polyline") == 2           # a queda não é desenhada
    ind = _indicador(bloco)
    assert "%" not in ind, ind                      # ≈ −99,9 % seria a mentira
    # O marcador fica ENTRE o último ponto antigo e o primeiro novo.
    xs = [float(x) for x in re.findall(r'<circle cx="([\d.]+)"', bloco)]
    xc = float(re.search(r'<line x1="([\d.]+)"[^>]*class="esvaziamento"', bloco).group(1))
    assert xs[len(ANTES) - 1] < xc < xs[len(ANTES)], (xs, xc)
    # Todos os pontos continuam desenhados, dos dois lados.
    assert len(xs) == len(serie)
    # Com dois pontos posteriores e base positiva, a percentagem é SÓ do troço novo.
    mista2 = cg._evo_block(ANTES + DEPOIS)
    ind2 = _indicador(mista2)
    assert "+4,8 %" in ind2 and "desde 2026-10-21" in ind2, ind2
    # Um só ponto depois do corte: sem percentagem.
    um = cg._evo_block(ANTES + [("2026-10-14", 0.0)])
    assert "%" not in _indicador(um) and "um só ponto" in _indicador(um)
    # A costura da regra de 24/09 continua a desenhar-se ao lado do corte.
    com_regra = cg._evo_block([("2026-09-01", 100.0)] + ANTES + DEPOIS)
    assert 'class="regra"' in com_regra and 'class="esvaziamento"' in com_regra
    print("mista: marcador, linha partida, percentagem so do troco novo")


def caso_o_historico_fica_intacto():
    d = Path(tempfile.mkdtemp())
    with db.session(d / "v.db", d / "c.db") as con:
        cg._ensure_value(con)
        for dia, v in ANTES + DEPOIS_ZERO:
            cg._record_value(con, v, 1 if v else 0, dia)
        antes = con.execute("SELECT * FROM value_history ORDER BY date").fetchall()
        antes = [tuple(r) for r in antes]
        hist = cg._value_history(con)
        copia = list(hist)
        cg._evo_block(hist)
        assert hist == copia                        # o desenho não mexe na série
        cg.build(con, d / "colecao.html", historico=False)
        depois = [tuple(r) for r in
                  con.execute("SELECT * FROM value_history ORDER BY date").fetchall()]
    assert depois == antes, (antes, depois)
    html = (d / "colecao.html").read_text(encoding="utf-8")
    assert 'class="esvaziamento"' in html and f"foi esvaziada a {E}" in html
    assert "2026-10-05" in html                     # o ponto mais antigo continua lá
    print("o historico fica como foi medido, dos dois lados do corte")


def run():
    for fn in (caso_so_pontos_anteriores, caso_so_pontos_posteriores,
               caso_serie_mista, caso_o_historico_fica_intacto):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
