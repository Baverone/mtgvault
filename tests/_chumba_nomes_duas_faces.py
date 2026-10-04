"""A PROVA de que o `test_nomes_duas_faces` chumba SEM a correccao.

Um teste que passa com e sem a funcionalidade nao prova nada. Aqui neutraliza-se
uma peca de cada vez — como se a correccao de 2026-10-04 nao tivesse sido feita
— e EXIGE-SE que o caso correspondente chumbe.

**UM PROCESSO POR ALVO**, de proposito: o `scryfall` e importado por meia duzia
de modulos e o `MapaDeCartas` por mais; neutralizar num processo so deixava o
primeiro alvo a envenenar os seguintes em silencio (a licao do
`tests/_chumba_prazo.py`).

    py tests/_chumba_nomes_duas_faces.py            # corre todos
    py tests/_chumba_nomes_duas_faces.py <alvo>     # corre um (filho)
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(AQUI))

#: alvo -> (o que se desliga, os casos que TEM de chumbar)
ALVOS = {
    "sem_prefixo": (
        "o `sql_nome` volta a ser so `coluna = ?` (o cruzamento por igualdade)",
        ["CasoPreco.caso_card_price_responde_a_uma_dupla_face",
         "CasoPreco.caso_card_price_responde_ao_separador_escrito_de_outra_maneira"],
    ),
    "sem_canonizar": (
        "o `canonizar` devolve o nome tal e qual (sem normalizar o separador)",
        ["CasoResolucao.caso_wear_tear_e_wear_barra_tear_dao_a_mesma_carta",
         "CasoResolucao.caso_a_chave_e_a_mesma_para_as_duas_escritas",
         "CasoPosse.caso_as_duas_wear_tear_aparecem_escrito_de_qualquer_maneira"],
    ),
    "sem_chave": (
        "a `chave` volta a ser um `split(' // ')[0]` cru, sem canonizar",
        ["CasoResolucao.caso_a_chave_e_a_mesma_para_as_duas_escritas",
         "CasoPosse.caso_as_duas_wear_tear_aparecem_escrito_de_qualquer_maneira"],
    ),
    "mapa_cru": (
        "o `MapaDeCartas` volta a ser um `dict` normal (nao canoniza a chave)",
        ["CasoPosse.caso_as_duas_wear_tear_aparecem_escrito_de_qualquer_maneira"],
    ),
    "resolver_exacto": (
        "o `resolver` so tenta o nome exacto (sem a frente nem o canonizado)",
        ["CasoResolucao.caso_a_frente_resolve_para_o_nome_inteiro",
         "CasoResolucao.caso_wear_tear_e_wear_barra_tear_dao_a_mesma_carta"],
    ),
    "posse_sem_chave": (
        "a `posse_total` volta a indexar pelo nome INTEIRO do catalogo",
        ["CasoPosse.caso_as_cinco_witch_enchanter_aparecem",
         "CasoPosse.caso_as_cinco_sink_into_stupor_aparecem",
         "CasoPosse.caso_as_quatro_tamiyo_aparecem"],
    ),
    "conta_sem_desconhecidas": (
        "o `conta_do_deck` deixa de contar as desconhecidas a parte",
        ["CasoDeck.caso_uma_desconhecida_nao_passa_por_nao_tenho"],
    ),
    "canonizar_cego": (
        "o `resolver` canoniza ANTES de tentar o nome exacto (estraga o `SP//dr`)",
        ["CasoResolucao.caso_uma_barra_que_nao_e_separador_nao_se_estraga"],
    ),
    "predicado_com_like": (
        "o `sql_nome` volta ao `LIKE ? || ' // %'` (que da SCAN cards)",
        ["CasoPlano.caso_o_predicado_entra_pelo_indice"],
    ),
}


def _neutralizar(alvo: str):
    """Desliga a peca do `alvo` nos modulos JA importados."""
    from mtgvault import paginas, scryfall, decks_vista

    if alvo == "sem_prefixo":
        scryfall.sql_nome = lambda coluna="name": f"{coluna} = ?"
        scryfall.params_nome = lambda nome: (nome or "",)
    elif alvo == "sem_canonizar":
        scryfall.canonizar = lambda nome: nome or ""
        scryfall.chave = lambda nome: (nome or "").split(" // ")[0].strip()
    elif alvo == "sem_chave":
        scryfall.chave = lambda nome: (nome or "").split(" // ")[0].strip()
    elif alvo == "mapa_cru":
        scryfall.MapaDeCartas = dict
        paginas._scry = scryfall
    elif alvo == "resolver_exacto":
        def so_exacto(con, nome):
            r = con.execute("SELECT name FROM cards WHERE name = ? LIMIT 1",
                            (nome,)).fetchone()
            return r["name"] if r else None
        scryfall.resolver = so_exacto
        scryfall.resolver_muitos = lambda con, nomes: {
            n: so_exacto(con, n) for n in dict.fromkeys(nomes) if n}
    elif alvo == "posse_sem_chave":
        def crua(con):
            from mtgvault import collection as _c
            out: dict[str, int] = {}
            for r in con.execute(
                    "SELECT c.name nm, SUM(cp.quantity) q FROM copies cp "
                    "JOIN cards c ON c.scryfall_id = cp.scryfall_id "
                    "WHERE " + _c.jogaveis() + " GROUP BY c.name"):
                out[r["nm"]] = out.get(r["nm"], 0) + r["q"]
            return out
        paginas.posse_total = crua
    elif alvo == "conta_sem_desconhecidas":
        antigo = decks_vista.conta_do_deck
        decks_vista.conta_do_deck = lambda d, pos, desc=None: {
            **antigo(d, pos, None), "desconhecidas": 0}
    elif alvo == "canonizar_cego":
        def cego(con, nome):
            for arg in (scryfall.canonizar(nome), nome):   # a ordem TROCADA
                r = con.execute("SELECT name FROM cards WHERE name = ? LIMIT 1",
                                (arg,)).fetchone()
                if r:
                    return r["name"]
                r = con.execute(
                    "SELECT name FROM cards WHERE name >= ? AND name < ? LIMIT 1",
                    scryfall.limites_dupla_face(arg)).fetchone()
                if r:
                    return r["name"]
            return None
        scryfall.resolver = cego
    elif alvo == "predicado_com_like":
        scryfall.sql_nome = (
            lambda coluna="name": f"({coluna} = ? OR {coluna} LIKE ? || ' // %')")
        scryfall.params_nome = lambda nome: (nome or "", nome or "")
    else:
        raise SystemExit("alvo desconhecido: %s" % alvo)


def _filho(alvo: str) -> int:
    """Corre, neste processo, os casos do alvo com a peca desligada."""
    import test_nomes_duas_faces as T

    _neutralizar(alvo)
    # O `_base()` reimporta o pacote (limpa o `sys.modules`), por isso a
    # neutralizacao tem de se repetir DEPOIS dele — e e no `setUp` que ele corre.
    base_original = T._base

    def base_e_neutralizar():
        r = base_original()
        _neutralizar(alvo)
        return r
    T._base = base_e_neutralizar

    _desc, casos = ALVOS[alvo]
    carregador = unittest.TestLoader()
    carregador.testMethodPrefix = "caso_"
    suite = unittest.TestSuite()
    for c in casos:
        cls, met = c.split(".")
        suite.addTest(getattr(T, cls)(met))
    r = unittest.TextTestRunner(verbosity=0).run(suite)
    chumbaram = len(r.failures) + len(r.errors)
    print("ALVO %s: %d de %d casos chumbaram" % (alvo, chumbaram, len(casos)))
    for t, _tb in r.failures + r.errors:
        print("   chumbou (bem): %s" % t)
    # O filho devolve 0 quando TODOS chumbaram (que e o que se quer).
    return 0 if chumbaram == len(casos) else 1


def main() -> int:
    if len(sys.argv) > 1:
        return _filho(sys.argv[1])
    bons, maus = 0, []
    for alvo, (desc, casos) in ALVOS.items():
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), alvo],
                           capture_output=True, text=True, cwd=str(AQUI))
        ok = p.returncode == 0
        print("%-24s %-5s %s" % (alvo, "OK" if ok else "FALHA", desc))
        for ln in (p.stdout or "").splitlines():
            if ln.startswith(("ALVO", "   ")):
                print("    " + ln)
        if ok:
            bons += 1
        else:
            maus.append(alvo)
            print((p.stdout or "")[-700:])
            print((p.stderr or "")[-700:])
    print("\n%d de %d alvos provaram que o teste chumba sem a correccao"
          % (bons, len(ALVOS)))
    if maus:
        print("ALVOS QUE NAO PROVARAM NADA:", maus)
    return 0 if not maus else 1


if __name__ == "__main__":
    sys.exit(main())
