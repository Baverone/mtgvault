"""A troca de lista de referência que não entra em silêncio (André, 2026-10-16).

*"uma troca de lista de referência que mude mais de N cartas não se aceita em
silêncio — fica como aviso e o deck mantém a lista anterior até o André decidir.
E uma lista que deixe de jogar a carta que dá o nome ao deck recusa-se sempre."*

O caso real: a 16/10 o Grinding Station passou da decklist 26604 (Cachorrowo,
Modern Challenge 16 de 12/10, a variante de Kethis) para a 27439 (howa, Modern
Challenge 64 de 15/10, a de Loki) — 82 cartas. As duas listas abaixo são as da
base (`decklist_cards`, lidas a 2026-10-16), tal e qual. Bases temporárias com
caminho explícito; nunca a dele.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, painel, sources  # noqa: E402
import my_decks  # noqa: E402

L26604 = [
    ('main', "Agatha's Soul Cauldron", 2), ('main', 'Boseiju, Who Endures', 3),
    ('main', 'Emry, Lurker of the Loch', 4), ('main', "Giant's Boulder", 4),
    ('main', 'Grinding Station', 4), ('main', 'Haywire Mite', 1), ('main', 'Island', 1),
    ('main', 'Jace, the Perfected Mind', 1), ('main', 'Kethis, the Hidden Hand', 4),
    ('main', 'Malevolent Rumble', 4), ('main', "Minamo, School at Water's Edge", 1),
    ('main', "Mishra's Bauble", 4), ('main', 'Mox Amber', 4), ('main', 'Mox Opal', 4),
    ('main', 'Otawara, Soaring City', 1), ('main', 'Plaza of Heroes', 4),
    ('main', "Sevinne's Reclamation", 1), ('main', 'Sewer-veillance Cam', 2),
    ('main', 'Starting Town', 4), ('main', 'Tamiyo, Inquisitive Student', 3),
    ('main', 'Teferi, Time Raveler', 1), ('main', "Urza's Saga", 3),
    ('side', 'Consign to Memory', 3), ('side', 'Erode', 2), ('side', 'Forest', 1),
    ('side', 'Metallic Rebuke', 2), ('side', "Nature's Claim", 2),
    ('side', 'Nihil Spellbomb', 1), ('side', 'Stone of Erech', 1),
    ('side', 'Teferi, Time Raveler', 1), ('side', 'Toxic Deluge', 1),
    ('side', 'Vexing Bauble', 1),
]
L27439 = [
    ('main', 'Aether Spellbomb', 1), ('main', 'Breeding Pool', 1),
    ('main', 'Emry, Lurker of the Loch', 4), ('main', 'Flooded Strand', 1),
    ('main', 'Gemstone Caverns', 1), ('main', 'Grinding Station', 2),
    ('main', 'Haywire Mite', 1), ('main', 'Hedge Maze', 1), ('main', 'Island', 3),
    ('main', 'Key to the Side-Door', 1), ('main', 'Lavaspur Boots', 1),
    ('main', 'Loki, God of Mischief', 4), ('main', 'Metallic Rebuke', 4),
    ('main', "Minamo, School at Water's Edge", 1), ('main', "Mishra's Bauble", 4),
    ('main', 'Misty Rainforest', 1), ('main', 'Mox Amber', 4), ('main', 'Mox Opal', 4),
    ('main', 'Otawara, Soaring City', 3), ('main', 'Polluted Delta', 1),
    ('main', 'Scalding Tarn', 1), ('main', 'Sewer-veillance Cam', 4),
    ('main', 'Sink into Stupor', 2), ('main', 'Tamiyo, Inquisitive Student', 4),
    ('main', "Tormod's Crypt", 2), ('main', "Urza's Saga", 4),
    ('side', 'Boseiju, Who Endures', 1), ('side', 'Consign to Memory', 4),
    ('side', 'Dismember', 1), ('side', 'Engineered Explosives', 1),
    ('side', 'Force of Negation', 2), ('side', 'Mystical Dispute', 1),
    ('side', "Nature's Claim", 1), ('side', 'Pithing Needle', 1),
    ('side', 'Shadowspear', 1), ('side', 'Spell Snare', 1), ('side', 'Swan Song', 1),
]
NOME = ["Grinding Station"]


def _guardar(con, chave, cartas, dia, jogador, evento):
    return sources.store_decklist(con, source="mtgo", source_key=chave, fmt="modern",
                                  cards=cartas, event_name=evento, event_date=dia,
                                  player=jogador)


def caso_as_duas_regras_e_a_fronteira():
    """82 cartas: recusada. Sem a carta do nome: recusada mesmo com 8 cartas.
    60 entra, 62 não."""
    assert sum(q for _b, _n, q in L26604) == 75 and sum(q for _b, _n, q in L27439) == 75
    porque = my_decks.avaliar_troca(L26604, L27439, NOME)
    assert porque == "82 cartas trocadas (mais de 60)", porque
    # a lista nova continua a jogar Grinding Station (4 -> 2): a regra que morde
    # aqui é o tamanho, não a carta do nome
    assert any(n == "Grinding Station" for _b, n, _q in L27439)
    sem = [(b, n, q) for b, n, q in L26604 if n != "Grinding Station"] + [("main", "Ornithopter", 4)]
    assert my_decks.avaliar_troca(L26604, sem, NOME) == "a lista nova nao joga Grinding Station"
    assert my_decks.avaliar_troca(L26604, sem, []) is None, "8 cartas e sem carta-nome: entra"
    base = [("main", f"C{i}", 4) for i in range(15)] + [("side", f"S{i}", 1) for i in range(15)]
    trinta = [("main", f"C{i}", 4) for i in range(15)][:-8] + [("main", f"N{i}", 4) for i in range(7)] \
        + [("main", "N7", 2), ("main", "C14", 2)] + [("side", f"S{i}", 1) for i in range(15)]
    n30 = sum(abs(d) for _b, _n, d in painel.diferencas(base, trinta))
    assert n30 == 60 and my_decks.avaliar_troca(base, trinta, []) is None, n30
    trinta1 = [(b, n, q) for b, n, q in trinta if n != "S0"] + [("side", "X", 1)]
    assert my_decks.avaliar_troca(base, trinta1, []) == "62 cartas trocadas (mais de 60)"
    print("regras: 26604 -> 27439 recusada (82); sem a carta do nome recusada; 60 entra, 62 nao")


def caso_a_troca_real_e_recusada_e_o_deck_fica(con, raiz):
    a = _guardar(con, "26604", L26604, "2026-10-12", "Cachorrowo", "Modern Challenge 16")
    b = _guardar(con, "27439", L27439, "2026-10-15", "howa", "Modern Challenge 64")
    con.commit()
    # a 26604 é a variante de Kethis, que a assinatura do `main` exclui — por isso
    # o deck só a tem se ele a pedir: é o «repor a 26604» da ordem
    my_decks.aceitar(con, "Grinding Station", a, hoje="2026-10-14")
    nota = lambda: con.execute(  # noqa: E731
        "SELECT notes FROM decks WHERE name = 'Grinding Station'").fetchone()[0]
    assert nota().endswith(f"(#{a})")
    gs = [s for s in my_decks.seguidos() if s["deck"] == "Grinding Station"][0]
    assert gs["procura"](con)["id"] == b

    for _ in range(2):
        r = my_decks.refresh(con, hoje="2026-10-16")
        assert "Grinding Station: troca RECUSADA -> 2026-10-15 howa (82 cartas trocadas" in r, r
    assert nota().endswith(f"(#{a})"), "recusada, o deck fica com a lista anterior"
    cartas = {(x["board"], x["card_name"]): x["quantity"] for x in con.execute(
        "SELECT * FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id WHERE d.name = 'Grinding Station'")}
    assert cartas[("main", "Kethis, the Hidden Hand")] == 4 and ("main", "Loki, God of Mischief") not in cartas
    t = con.execute("SELECT * FROM deck_lista_trocas WHERE deck = 'Grinding Station' "
                    "AND motivo = 'recusada'").fetchall()
    assert len(t) == 1 and (t[0]["de_decklist_id"], t[0]["para_decklist_id"]) == (a, b), \
        [dict(x) for x in t]
    assert len(json.loads(t[0]["para_cartas"])) == len(L27439)

    raiz.mkdir(parents=True, exist_ok=True)
    painel.escrever(con, raiz=raiz, hoje="2026-10-16")
    av = json.loads((raiz / "avisos.json").read_text(encoding="utf-8"))
    rec = [x for x in av if x["deck"] == "Grinding Station" and x["aviso"].startswith("troca recusada")]
    assert rec and rec[0]["gravidade"] == "alta", av
    assert "82 cartas trocadas" in rec[0]["aviso"] and "aceitar" in rec[0]["detalhe"], rec
    alts = json.loads((raiz / "alteracoes.json").read_text(encoding="utf-8"))
    assert not [x for x in alts if x["deck"] == "Grinding Station"], "recusada não é alteração"

    # ele decide: aceita
    assert "atualizado -> 2026-10-15 howa" in my_decks.aceitar(con, "Grinding Station", hoje="2026-10-16")
    assert nota().endswith(f"(#{b})")
    assert "já atual" in my_decks.refresh(con, hoje="2026-10-16")
    painel.escrever(con, raiz=raiz, hoje="2026-10-16")
    av = json.loads((raiz / "avisos.json").read_text(encoding="utf-8"))
    assert not [x for x in av if x["aviso"].startswith("troca recusada")], av

    # a carta do nome, pelo caminho do `_store` (a procura por assinatura nunca
    # devolve uma lista sem ela — é a rede para quem a chame com outra lista):
    # 8 cartas de diferença e mesmo assim recusada
    sem = [(b, n, q) for b, n, q in L27439 if n != "Grinding Station"] + [("main", "Ornithopter", 2)]
    c = _guardar(con, "semgs", sem, "2026-10-17", "alguem", "Modern Challenge 32")
    con.commit()
    dl = con.execute("SELECT id, source, player, event_date FROM decklists WHERE id = ?", (c,)).fetchone()
    out = []
    my_decks._store(con, "Grinding Station", "modern", dl, out, "2026-10-17", gs["assinatura"])
    assert "nao joga Grinding Station" in out[0], out
    assert nota().endswith(f"(#{b})")
    print("26604 -> 27439: recusada, o deck fica, aviso alta todos os dias; aceite, entra; "
          "sem a carta do nome, recusada pelo _store")


def caso_aceitar_recusa_o_que_nao_e_do_deck(con):
    for args, msg in ((("Nao Existe",), "nao seguido"),
                      (("Grinding Station", 999999), "nao existe")):
        try:
            my_decks.aceitar(con, *args)
        except ValueError as e:
            assert msg in str(e), e
        else:
            raise AssertionError(f"aceitar{args} devia recusar")
    print("aceitar: deck não seguido e lista inexistente são recusados")


def run():
    caso_as_duas_regras_e_a_fronteira()
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        caso_a_troca_real_e_recusada_e_o_deck_fica(con, tmp / "painel")
        caso_aceitar_recusa_o_que_nao_e_do_deck(con)
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
