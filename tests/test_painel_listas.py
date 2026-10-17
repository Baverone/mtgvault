"""As listas de referência e os resultados da semana no painel (André,
2026-10-17: *"todos os dias dá-me as decklists atualizadas e resultados que
tiveram"*).

Base e config temporários, com caminho explícito (nunca os dele). O que se
tranca: os dois ficheiros existem com EXACTAMENTE os campos que o painel lê, os
`id` são únicos, o `conta` só diz `sim`/`nao` e segue a regra do
`metagame_fontes`, e nenhum resultado aponta para um deck que não esteja nas
listas. E as quatro regras do emparelhamento: a caixa que saiu não recebe
resultados, a identidade que não está na lista do próprio deck é recusada, o
`!` do `my_decks.FOLLOWED` exclui, e em Duel Commander quem decide é o
comandante.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TMP = Path(tempfile.mkdtemp())
os.environ["MTGVAULT_CONFIG"] = str(TMP / "colecao_config.json")

from mtgvault import db, painel, painel_listas  # noqa: E402

HOJE = "2026-10-17"

TERRA = [["main", "Terravore", 4], ["main", "Mox Diamond", 4], ["main", "Armageddon", 4],
         ["main", "Forest", 20], ["main", "Plains", 28], ["side", "Choke", 15]]
IZZET = [["main", "Mox Opal", 4], ["main", "Kappa Cannoneer", 4], ["main", "Island", 52],
         ["side", "Spell Pierce", 15]]
CLOUD = [["main", "Cloud, Midgar Mercenary", 1], ["main", "Plains", 99]]
OATH = [["main", "Oath of Druids", 4], ["main", "Forest", 56], ["side", "Choke", 15]]

CFG = {
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial", "Qualifier"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "duel-commander": {"min_jogadores_presencial": 0, "ligas": True},
    },
    "caixas": [
        {"slot": "premodern-terra", "nome": "Terrageddon", "formato": "premodern",
         "fonte": "escolhido", "ref": "premodern-terra",
         "assinatura": ["Terravore", "Mox Diamond"], "assinatura_todas": True},
        # a identidade de reserva (Oswald) NÃO está na lista da caixa: é o caso
        # real da caixa `modern`, e tem de ser recusada
        {"slot": "modern", "nome": "Modern — Izzet", "formato": "modern",
         "fonte": "escolhido", "ref": "modern", "reserva_assinatura": ["Oswald Fiddlebender"]},
        {"slot": "dc", "nome": "Cloud (Duel Commander)", "formato": "duel-commander",
         "fonte": "escolhido", "ref": "dc", "comandante": "Cloud, Midgar Mercenary"},
        {"slot": "oath", "nome": "Oath of Druids", "formato": "premodern",
         "fonte": "escolhido", "ref": "oath", "assinatura": ["Oath of Druids"],
         "_saiu": {"em": "2026-10-16", "porque": "passou a Terrageddon"}},
    ],
    "listas_escolhidas": {
        "premodern-terra": {"cards": TERRA, "padrao": True, "origem": "teste"},
        "modern": {"cards": IZZET, "padrao": True, "origem": "teste"},
        "dc": {"cards": CLOUD, "padrao": True, "origem": "teste"},
        "oath": {"cards": OATH, "padrao": True, "origem": "teste"},
    },
}


def _lista(con, i, fmt, data, cartas, *, tier="Challenge", jogadores=None, jogador="x",
           evento=None, lugar="1", commander=None):
    con.execute(
        "INSERT INTO decklists (id, source, source_key, format, event_name, event_date, "
        "player, placement, url, event_players, event_tier, commander) "
        "VALUES (?, 'mtgtop8', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (i, f"k{i}", fmt, evento or f"{fmt.title()} event - Evento {i}", data, jogador,
         lugar, f"https://exemplo/{i}", jogadores, tier, commander))
    con.executemany("INSERT INTO decklist_cards (decklist_id, card_name, quantity, board) "
                    "VALUES (?,?,?,?)", [(i, n, q, b) for b, n, q in cartas])


def _semear(con):
    # o deck seguido «Grinding Station» (my_decks.FOLLOWED: Mox Opal + Grinding
    # Station, sem Kethis), com a lista na tabela `decks`
    gs = [["main", "Mox Opal", 4], ["main", "Grinding Station", 4], ["main", "Island", 52]]
    con.execute("INSERT INTO decks (name, format, notes) VALUES ('Grinding Station', 'modern', "
                "'auto: mtgo howa 2026-10-15 (#900)')")
    did = con.execute("SELECT id FROM decks WHERE name = 'Grinding Station'").fetchone()[0]
    con.executemany("INSERT INTO deck_cards (deck_id, card_name, quantity, board) VALUES (?,?,?,?)",
                    [(did, n, q, b) for b, n, q in gs])
    _lista(con, 1, "premodern", "2026-10-15", TERRA, jogador="Jind%26%23345%3Bich Petr",
           evento="Premodern event - MTGO Challenge 32")
    _lista(con, 2, "premodern", "2026-10-14", TERRA, tier="Presencial", jogadores=37,
           lugar="3-4")
    _lista(con, 3, "premodern", "2026-10-14", OATH)                       # caixa saiu
    _lista(con, 4, "modern", "2026-10-13", [["main", "Oswald Fiddlebender", 4]])
    _lista(con, 5, "modern", "2026-10-13", gs)
    _lista(con, 6, "modern", "2026-10-12", gs + [["main", "Kethis, the Hidden Hand", 1]])
    _lista(con, 7, "duel-commander", "2026-10-15", CLOUD, tier="League", lugar="",
           commander="Cloud, Midgar Mercenary")
    # o Cloud jogado por OUTRO comandante não é o deck dele
    _lista(con, 8, "duel-commander", "2026-10-15", CLOUD, commander="Aragorn, King of Gondor")
    _lista(con, 9, "premodern", "2026-10-01", TERRA)                      # fora dos 7 dias
    con.commit()


def caso_os_ficheiros_e_os_campos(con, raiz):
    r = painel_listas.escrever(con, raiz=raiz, hoje=HOJE)
    for nome, campos in painel_listas.CAMPOS.items():
        linhas = json.loads((raiz / nome).read_text(encoding="utf-8"))
        assert linhas, f"{nome} vazio"
        for ln in linhas:
            assert list(ln) == campos, (nome, list(ln))
        ids = [ln["id"] for ln in linhas]
        assert len(ids) == len(set(ids)), f"{nome}: ids repetidos"
        h = raiz / "historico" / f"{HOJE}-{nome.split('.')[0]}.json"
        assert json.loads(h.read_text(encoding="utf-8")) == linhas, h
    # o log diz o caminho COMPLETO e a hora de cada ficheiro
    txt = painel_listas.texto(r)
    for f, hora in r["ficheiros"]:
        assert Path(f).is_absolute() and f in txt and hora in txt, (f, txt)
    print(f"ficheiros e campos certos; {len(r['ficheiros'])} escritos com caminho e hora")
    return r


def caso_o_emparelhamento(con, raiz):
    listas = json.loads((raiz / "listas.json").read_text(encoding="utf-8"))
    res = {a["id"]: a for a in json.loads((raiz / "resultados.json").read_text(encoding="utf-8"))}
    decks = {x["deck"] for x in listas}
    assert "Oath of Druids" not in decks, "a caixa que saiu não é um deck dele"
    assert {"Terrageddon", "Modern — Izzet", "Cloud (Duel Commander)",
            "Grinding Station"} <= decks, decks
    assert all(a["deck"] in decks for a in res.values()), "resultado com deck fora das listas"
    assert all(a["conta"] in ("sim", "nao") for a in res.values())
    assert set(res) == {"1", "2", "5", "7"}, sorted(res)
    assert res["1"]["deck"] == "Terrageddon" and res["1"]["conta"] == "sim"
    assert res["1"]["jogador"] == "Jindřich Petr", res["1"]["jogador"]
    assert res["1"]["evento"] == "MTGO Challenge 32", res["1"]["evento"]
    assert res["2"]["conta"] == "nao", "presencial de 37 jogadores não chega aos 64 do Premodern"
    assert res["5"]["deck"] == "Grinding Station"
    assert res["7"]["deck"] == "Cloud (Duel Commander)" and res["7"]["conta"] == "sim", \
        "em Duel Commander as ligas contam"
    assert "comandante" in res["7"]["via"]
    print("emparelhamento: saída fora, identidade recusada, ! exclui, comandante decide")


def caso_a_identidade_recusada_fica_dita(r):
    assert any("Modern — Izzet" in n and "recusada" in n for n in r["notas"]), r["notas"]


def run():
    (TMP / "colecao_config.json").write_text(json.dumps(CFG, ensure_ascii=False),
                                              encoding="utf-8")
    raiz = TMP / "painel"
    with db.session(TMP / "v.db", TMP / "c.db") as con:
        _semear(con)
        r = caso_os_ficheiros_e_os_campos(con, raiz)
        caso_o_emparelhamento(con, raiz)
        caso_a_identidade_recusada_fica_dita(r)
        # o passo `painel` também passou a dizer caminho e hora
        p = painel.escrever(con, raiz=raiz, hoje=HOJE)
        assert all(Path(f).is_absolute() and h for f, h in p["ficheiros"]), p["ficheiros"]
        assert p["ficheiros"][0][0] in painel.texto(p)
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
