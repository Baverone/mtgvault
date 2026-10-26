"""aria-pressed nos botoes de filtro e de ordem (Faltas e Arrumacao).

Ordem mtg-aprovadas-1026 (aprovada pelo Andre no painel a 25/10/2026): num leitor
de ecra so a classe `cur` dizia que filtro/ordem estava activo. Mede-se no HTML
que o JavaScript DESENHOU (a barra e redesenhada a cada clique) e nao no codigo.
Reaproveita a base e o harness de `test_faltas_imagens` (que fixa as variaveis
de ambiente ANTES do import, como a bateria exige).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_faltas_imagens as base_t                               # noqa: E402

_BARRA = """
const g = () => barraHTML();
const antes = g();
FMT = ''; ORD = 'valor';
const a = g();
ORD = 'deck';
const b = g();
FMT = D.formatos[0];
const c = g();
const resultado = {a, b, c};
"""


def _botoes(html):
    return re.findall(r'<button[^>]*>', html)


def caso_faltas_os_botoes_de_formato_e_ordem_levam_aria_pressed():
    import faltas                                                  # noqa: PLC0415
    con = base_t.base()
    r = base_t.avaliar(faltas.html_page(con), _BARRA)
    if r is None:
        print("sem node - saltado")
        return
    for k in "abc":
        for b in _botoes(r[k]):
            assert 'aria-pressed="' in b, f"botao sem aria-pressed: {b}"
    # a: Todos + por valor ligados
    ligados = lambda h: [b for b in _botoes(h) if 'aria-pressed="true"' in b]  # noqa: E731
    assert len(ligados(r["a"])) == 2, r["a"]
    assert 'data-ord="valor"' in "".join(ligados(r["a"]))
    # b: a ordem muda ao carregar -> o atributo acompanha
    assert 'data-ord="deck"' in "".join(ligados(r["b"]))
    assert 'data-ord="valor"' not in "".join(ligados(r["b"]))
    # c: o formato escolhido deixa de ser "Todos"
    assert 'data-fmt=""' not in "".join(ligados(r["c"])), r["c"]
    # o aspecto nao muda: a classe cur continua a acompanhar o atributo
    for b in _botoes(r["b"]):
        assert ('cur' in b) == ('aria-pressed="true"' in b), b


def caso_arrumacao_os_botoes_das_fases_levam_aria_pressed():
    import arrumacao                                               # noqa: PLC0415
    con = base_t.base()
    r = base_t.avaliar(arrumacao.html_page(con), """
const out = [];
for (const k of ['f1', 'f2']) { ABA = k; barra(); out.push(document.getElementById('fasebar').innerHTML); }
const resultado = out;
""")
    if r is None:
        print("sem node - saltado")
        return
    for i, h in enumerate(r):
        bs = _botoes(h)
        assert bs, "a barra de fases veio vazia"
        assert all('aria-pressed="' in b for b in bs), h[:300]
        lig = [b for b in bs if 'aria-pressed="true"' in b]
        assert len(lig) == 1 and f'data-aba="f{i + 1}"' in lig[0], lig


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("caso_"):
            f()
            print("ok", n)
