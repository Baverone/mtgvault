"""Três defeitos achados na ronda de 2026-10-21, cada um com o caso que o prova.

1. o aviso «voltou a uma lista como a de …» saía em quase todas as trocas (num
   deck que evolui aos poucos todas as listas seguidas são ≥80 % iguais);
2. o `aceitar` de uma lista rejeitada deixava a rejeição de pé, e na noite
   seguinte a procura saltava a lista que o deck acabava de receber;
3. o texto copiável das faltas somava o preço do motor, e a página o da
   impressão que serve.

As sobreposições do caso 1 são as medidas na base de 21/10 (Izzet Affinity
0,93 com uma lista velha e 0,96 com a de hoje; Stiflenought 1,00 / 1,00;
Grinding Station 0,97 / 0,65). Bases temporárias com caminho explícito.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, faltas_vista, paginas, painel, sources  # noqa: E402
import my_decks  # noqa: E402


def _lista(base, troca=0, extra="X"):
    """Uma lista de 60 + 15 a partir de `base` com `troca` cópias de main
    trocadas por `extra`."""
    main = {f"C{i}": 4 for i in range(15)}
    for n, q in base.items():
        main[n] = q
    out = [("main", n, q) for n, q in main.items()]
    if troca:
        n0 = sorted(main)[0]
        out = [(b, n, q - troca if n == n0 else q) for b, n, q in out]
        out.append(("main", extra, troca))
    return out + [("side", f"S{i}", 1) for i in range(15)]


def _troca(con, deck, corrida, de, para, dj, pj):
    con.execute(
        "INSERT INTO deck_lista_trocas (deck, formato, corrida, motivo, de_jogador, "
        "de_data, de_cartas, para_jogador, para_data, para_cartas) "
        "VALUES (?, 'modern', ?, 'troca', ?, ?, ?, ?, ?, ?)",
        (deck, corrida, dj, corrida, json.dumps(de), pj, corrida, json.dumps(para)))
    return con.execute("SELECT * FROM deck_lista_trocas ORDER BY id DESC LIMIT 1").fetchone()


def caso_um_deck_que_evolui_nao_oscila_e_o_que_volta_atras_sim(con):
    """A lista nova parecida com uma velha E com a de hoje é evolução; parecida
    com a velha e longe da de hoje é oscilação (o Grinding Station de 21/10)."""
    a = _lista({})
    b = _lista({}, 4, "Y")          # a evoluir: 4 cópias de diferença de cada vez
    c = _lista({}, 8, "Y")
    _troca(con, "Evolui", "2026-10-18", a, b, "a", "b")
    t = _troca(con, "Evolui", "2026-10-21", b, c, "b", "c")
    sob_velha = painel._sobreposicao(painel._contar(c), painel._contar(a))
    sob_hoje = painel._sobreposicao(painel._contar(c), painel._contar(b))
    assert sob_velha >= painel.SOBREPOSICAO_OSCILA and sob_hoje > sob_velha, (sob_velha, sob_hoje)
    assert painel.oscilacao(con, t, "2026-10-07", "2026-10-21") is None, \
        "passar o limiar não chega: a lista nova é MAIS parecida com a que deixa hoje"
    # a mesma lista outra vez (os Stiflenought de 21/10, 0 cartas trocadas)
    _troca(con, "Igual", "2026-10-19", a, a, "l", "l")
    t = _troca(con, "Igual", "2026-10-21", a, a, "l", "l")
    assert painel.oscilacao(con, t, "2026-10-07", "2026-10-21") is None
    # howa -> Alakai -> howa: a lista de hoje é outro deck (40 cartas), e volta-se
    howa = _lista({})
    alakai = ([("main", f"C{i}", 4) for i in range(5)] + [("main", f"A{i}", 4) for i in range(10)]
              + [("side", f"S{i}", 1) for i in range(15)])
    _troca(con, "Grinding", "2026-10-20", howa, alakai, "howa", "Alakai")
    t = _troca(con, "Grinding", "2026-10-21", alakai, howa, "Alakai", "howa")
    v = painel.oscilacao(con, t, "2026-10-07", "2026-10-21")
    assert v is not None and v["de_jogador"] == "howa", "a oscilação verdadeira continua a avisar"
    print("oscilação: evoluir não avisa, a mesma lista não avisa, voltar atrás avisa")


def _guardar(con, chave, cartas, dia, jogador):
    return sources.store_decklist(con, source="mtgo", source_key=chave, fmt="modern",
                                  cards=cartas, event_name="Modern Challenge 32",
                                  event_date=dia, player=jogador)


def caso_aceitar_uma_rejeitada_levanta_a_rejeicao(con):
    gs = [s for s in my_decks.seguidos() if s["deck"] == "Grinding Station"][0]
    base = {"Grinding Station": 4, "Mox Opal": 4, "Emry, Lurker of the Loch": 4,
            "Sewer-veillance Cam": 4}
    velha = _guardar(con, "v", _lista(base), "2026-10-15", "howa")
    nova = _guardar(con, "n", _lista(base, 4, "Ornithopter"), "2026-10-17", "Alakai")
    con.commit()
    my_decks.aceitar(con, "Grinding Station", velha, hoje="2026-10-16")
    assert "rejeitada" in my_decks.rejeitar(con, "Grinding Station", nova, hoje="2026-10-18")
    assert gs["procura"](con)["id"] == velha
    # ele muda de ideias: aceita a que tinha rejeitado
    r = my_decks.aceitar(con, "Grinding Station", nova, hoje="2026-10-19")
    assert f"rejeicao de #{nova} levantada" in r and "atualizado" in r, r
    assert nova not in my_decks.rejeitadas(con, "Grinding Station", "modern")
    assert gs["procura"](con)["id"] == nova, "a procura já não a salta"
    # a noite seguinte NÃO regride para a velha nem grava uma recusa falsa
    assert "já atual" in my_decks.refresh(con, hoje="2026-10-20")
    nota = con.execute("SELECT notes FROM decks WHERE name = 'Grinding Station'").fetchone()[0]
    assert nota.endswith(f"(#{nova})"), nota
    assert not con.execute("SELECT 1 FROM deck_lista_trocas WHERE motivo = 'recusada' "
                           "AND deck = 'Grinding Station'").fetchone()
    # nada se apagou: a rejeição continua no histórico, e pode voltar a fazer-se
    assert con.execute("SELECT COUNT(*) FROM deck_lista_trocas WHERE motivo = 'rejeitada'"
                       ).fetchone()[0] == 1
    my_decks.aceitar(con, "Grinding Station", velha, hoje="2026-10-21")
    assert "rejeitada" in my_decks.rejeitar(con, "Grinding Station", nova, hoje="2026-10-21")
    assert nova in my_decks.rejeitadas(con, "Grinding Station", "modern"), \
        "rejeitar outra vez volta a valer: conta a decisão mais recente"
    print("aceitar uma rejeitada levanta a rejeição; o deck não regride; nada se apaga")


def caso_o_texto_das_faltas_bate_com_a_pagina():
    """O texto copiável soma o `valor_ref`, como a página e o `texto_totais`."""
    def deck(nome, valor, ref):
        return {"nome": nome, "copias": 1, "valor": valor, "valor_ref": ref,
                "linhas": [{"q": 1, "nm": nome + " carta", "total": valor, "total_ref": ref}]}
    v = {"decks": [deck("A", 1.0, 10.0), deck("B", 2.0, 20.0)],
         "proposta": [deck("P", 3.0, 30.0)],
         "totais": {"cartas": 2, "copias": 2, "valor": 3.0, "valor_ref": 30.0},
         "staples": {}}
    t = faltas_vista.texto(v)
    assert f"// A — 1 cóp., {paginas.eur(10.0)}" in t, t
    assert f"// P — 1 cóp., {paginas.eur(30.0)}" in t, t
    assert f"// TOTAL: 2 cartas, 2 cópias, {paginas.eur(30.0)}" in t, t
    # o total do texto é a soma das linhas pela régua da página (total_ref)
    assert v["totais"]["valor_ref"] == sum(l["total_ref"] for d in v["decks"] for l in d["linhas"])
    pag = (Path(__file__).resolve().parents[1] / "faltas.py").read_text(encoding="utf-8")
    assert "eur(d.valor)}</span></div>" not in pag and "eur(p.valor)}" not in pag, \
        "a PROPOSTA da página também usa o valor_ref"
    print("faltas: subtotais e TOTAL do texto pelo valor_ref, como a página")


def run():
    caso_o_texto_das_faltas_bate_com_a_pagina()
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        caso_um_deck_que_evolui_nao_oscila_e_o_que_volta_atras_sim(con)
        caso_aceitar_uma_rejeitada_levanta_a_rejeicao(con)
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
