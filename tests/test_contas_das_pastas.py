"""AS DUAS CONTAS DAS PASTAS DE CARTA (André, 2026-10-16).

A 16/10 o `fotos-plano` dizia «595 por fotografar» e no disco havia 650 pastas
de carta. 24 eram de VERSÕES que não são caixa (o Oswald, o Orzhov Monument) —
decks dele, e o plano não as conta por desenho; 31 eram RESTOS de listas que
mudaram, a pedir-lhe fotos que nenhum deck quer. A diferença não aparecia em
sítio nenhum. Trancado aqui:

  1. cada pasta cai num de três grupos — no plano, de versão, por explicar;
  2. uma versão que saiu (`_saiu`) não explica pasta nenhuma;
  3. com pastas por explicar o passo fica VERMELHO (`exige_contas_explicadas`
     levanta) e a frase diz as duas contas;
  4. as pastas `_…` (`_fora do plano`, `_nomes antigos`) não contam.

Não abre base nenhuma: a conta só precisa do relatório, do config e do disco.
"""
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from mtgvault import fotos  # noqa: E402

CFG = {
    "caixas": [{"slot": "pioneer", "nome": "Pioneer — Greasefang",
                "formato": "pioneer", "fonte": "escolhido", "ref": "pioneer"}],
    "familias_fotos": [],
    "decks_por_formato": {"pioneer": {"versoes": [
        {"id": "versao:pioneer:orzhov", "nome": "Orzhov Monument"},
        {"id": "versao:pioneer:parhelion", "nome": "Parhelion", "_saiu": {"em": "2026-10-13"}},
    ]}},
    "listas_escolhidas": {
        "versao:pioneer:orzhov": {"cards": [["main", "Monument to Endurance", 4],
                                            ["main", "Greasefang, Okiba Boss", 4]]},
        "versao:pioneer:parhelion": {"cards": [["main", "Starting Town", 1]]},
    },
}
RES = {"slots": [{"slot": "pioneer", "nome": "Pioneer — Greasefang",
                  "formato": "pioneer",
                  "have": [{"nm": "Greasefang, Okiba Boss", "need": 4}],
                  "missing": [{"nm": "Thundering Broodwagon", "need": 4}]}]}


def _arvore(*pastas):
    raiz = Path(tempfile.mkdtemp())
    deck = fotos.pasta_novas(raiz) / "Pioneer — Greasefang"
    for p in pastas:
        (deck / p).mkdir(parents=True)
    (fotos.pasta_novas(raiz) / fotos.PASTA_FORA_DO_PLANO / "Pioneer — Greasefang"
     / "Caves of Koilos (4)").mkdir(parents=True)
    return raiz


def caso_cada_pasta_cai_num_grupo():
    raiz = _arvore("Greasefang, Okiba Boss (4)", "Thundering Broodwagon (4)",
                   "Monument to Endurance (4)", "lote1")
    c = fotos.contas_das_pastas(RES, CFG, raiz)
    assert c["no_disco"] == 3, c                       # o «lote1» não é pasta de carta
    assert c["no_plano"] == 2, c
    assert [x["pasta"] for x in c["de_versoes"]] == ["Monument to Endurance (4)"], c
    assert c["de_versoes"][0]["versoes"] == ["Orzhov Monument"], c
    assert c["por_explicar"] == [], c                  # e a `_fora do plano` não contou
    t = fotos.exige_contas_explicadas(c, 2)
    assert "2 por fotografar (plano), 3 pastas no disco" in t, t
    assert "1 de versões que não são caixa (Orzhov Monument 1)" in t, t
    assert "0 por explicar" in t, t


def caso_uma_versao_que_saiu_nao_explica_nada():
    raiz = _arvore("Greasefang, Okiba Boss (4)", "Starting Town (1)")
    c = fotos.contas_das_pastas(RES, CFG, raiz)
    assert [x["pasta"] for x in c["por_explicar"]] == ["Starting Town (1)"], c


def caso_pastas_por_explicar_poem_o_passo_a_vermelho():
    raiz = _arvore("Greasefang, Okiba Boss (4)", "Starting Town (1)",
                   "Rip Apart (1)")
    c = fotos.contas_das_pastas(RES, CFG, raiz)
    try:
        fotos.exige_contas_explicadas(c, 1)
    except fotos.PastasPorExplicar as e:
        msg = str(e)
        assert "2 pastas de carta que nenhuma lista pede" in msg, msg
        assert "Rip Apart (1)" in msg and "Starting Town (1)" in msg, msg
        assert "1 por fotografar (plano), 3 pastas no disco — diferença 2" in msg, msg
        assert fotos.PASTA_FORA_DO_PLANO in msg, msg
    else:
        raise AssertionError("duas pastas por explicar e o passo ficava verde")


def caso_o_daily_usa_a_mesma_verificacao():
    txt = (RAIZ / "daily.py").read_text(encoding="utf-8")
    assert "exige_contas_explicadas" in txt, "o fotos-plano deixou de verificar as duas contas"


if __name__ == "__main__":
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    for c in casos:
        c()
        print("ok", c.__name__)
    print(f"{len(casos)} casos ok")
