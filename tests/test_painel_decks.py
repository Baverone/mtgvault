"""O painel das alterações nos decks (André, 2026-10-16) e as duas correcções
que vieram com ele: a gravação que perdia cópias e o histórico das trocas.

*"todos os dias quero que mostres aqui ao lado as alterações ocorridas nos
decks"*. Tudo em bases temporárias com caminho explícito (nunca a dele).
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, painel, sources  # noqa: E402
import my_decks  # noqa: E402

URL = "https://www.mtgo.com/decklist/modern-challenge-64-2026-10-1512856574"

# Trecho REAL da página da Modern Challenge 64 de 15/10/2026 (mtgo.com, capturado
# a 2026-10-16), só a lista do howa e só os campos que o parser lê. A página serve
# a MESMA carta em várias entradas — Tamiyo 3 + 1, Consign to Memory 3 + 1 — e era
# isso que a gravação antiga (`INSERT OR REPLACE`) encurtava para 57 / 12.
HOWA = json.loads('{"player": "howa", "loginid": "1855222", "main_deck": [{"qty": "4", "card_attributes": {"card_name": "Loki, God of Mischief"}}, {"qty": "4", "card_attributes": {"card_name": "Mishra\'s Bauble"}}, {"qty": "4", "card_attributes": {"card_name": "Emry, Lurker of the Loch"}}, {"qty": "3", "card_attributes": {"card_name": "Tamiyo, Inquisitive Student"}}, {"qty": "1", "card_attributes": {"card_name": "Tamiyo, Inquisitive Student"}}, {"qty": "4", "card_attributes": {"card_name": "Mox Amber"}}, {"qty": "4", "card_attributes": {"card_name": "Mox Opal"}}, {"qty": "2", "card_attributes": {"card_name": "Tormod\'s Crypt"}}, {"qty": "4", "card_attributes": {"card_name": "Urza\'s Saga"}}, {"qty": "3", "card_attributes": {"card_name": "Island"}}, {"qty": "1", "card_attributes": {"card_name": "Hedge Maze"}}, {"qty": "1", "card_attributes": {"card_name": "Breeding Pool"}}, {"qty": "3", "card_attributes": {"card_name": "Otawara, Soaring City"}}, {"qty": "1", "card_attributes": {"card_name": "Haywire Mite"}}, {"qty": "2", "card_attributes": {"card_name": "Grinding Station"}}, {"qty": "2", "card_attributes": {"card_name": "Sink into Stupor"}}, {"qty": "1", "card_attributes": {"card_name": "Minamo, School at Water\'s Edge"}}, {"qty": "4", "card_attributes": {"card_name": "Sewer-veillance Cam"}}, {"qty": "4", "card_attributes": {"card_name": "Metallic Rebuke"}}, {"qty": "1", "card_attributes": {"card_name": "Gemstone Caverns"}}, {"qty": "1", "card_attributes": {"card_name": "Key to the Side-Door"}}, {"qty": "1", "card_attributes": {"card_name": "Lavaspur Boots"}}, {"qty": "1", "card_attributes": {"card_name": "Aether Spellbomb"}}, {"qty": "1", "card_attributes": {"card_name": "Polluted Delta"}}, {"qty": "1", "card_attributes": {"card_name": "Misty Rainforest"}}, {"qty": "1", "card_attributes": {"card_name": "Scalding Tarn"}}, {"qty": "1", "card_attributes": {"card_name": "Flooded Strand"}}], "sideboard_deck": [{"qty": "1", "card_attributes": {"card_name": "Spell Snare"}}, {"qty": "3", "card_attributes": {"card_name": "Consign to Memory"}}, {"qty": "1", "card_attributes": {"card_name": "Nature\'s Claim"}}, {"qty": "1", "card_attributes": {"card_name": "Swan Song"}}, {"qty": "1", "card_attributes": {"card_name": "Mystical Dispute"}}, {"qty": "1", "card_attributes": {"card_name": "Boseiju, Who Endures"}}, {"qty": "1", "card_attributes": {"card_name": "Dismember"}}, {"qty": "1", "card_attributes": {"card_name": "Shadowspear"}}, {"qty": "2", "card_attributes": {"card_name": "Force of Negation"}}, {"qty": "1", "card_attributes": {"card_name": "Consign to Memory"}}, {"qty": "1", "card_attributes": {"card_name": "Pithing Needle"}}, {"qty": "1", "card_attributes": {"card_name": "Engineered Explosives"}}]}')
BLOB = {"description": "Modern Challenge 64", "starttime": "2026-10-15T08:00:00",
        "format": "CMODERN", "player_count": "64", "decklists": [HOWA]}
PAGINA = ("<script>window.MTGO.decklists.data = " + json.dumps(BLOB)
          + ";</script>")

# Uma lista do Grinding Station «de Emry» anterior (sintética, 60 + 15): 4 Grinding
# Station, para a troca para a do howa (2) dar o aviso da carta-nome.
ANTES = ([("main", "Grinding Station", 4), ("main", "Mox Opal", 4),
          ("main", "Emry, Lurker of the Loch", 4), ("main", "Sewer-veillance Cam", 3),
          ("main", "Urza's Saga", 4), ("main", "Mishra's Bauble", 4),
          ("main", "Mox Amber", 4), ("main", "Island", 9), ("main", "Thoughtcast", 4),
          ("main", "Frogmite", 4), ("main", "Myr Enforcer", 4), ("main", "Darkslick Shores", 4),
          ("main", "Spellstutter Sprite", 4), ("main", "Ornithopter", 4)]
         + [("side", "Consign to Memory", 4), ("side", "Force of Negation", 3),
            ("side", "Dismember", 2), ("side", "Pithing Needle", 2),
            ("side", "Spell Snare", 4)])

# Outro deck que também joga Mox Opal + Grinding Station: a troca para ele passa
# das 60 cartas — é o emparelhador a trocar de arquétipo.
OUTRO = ([("main", "Grinding Station", 1), ("main", "Mox Opal", 4),
          ("main", "Ruby Medallion", 4), ("main", "Desperate Ritual", 4),
          ("main", "Pyretic Ritual", 4), ("main", "Manamorphose", 4),
          ("main", "Past in Flames", 3), ("main", "Grapeshot", 2), ("main", "Mountain", 10),
          ("main", "Ral, Monsoon Mage", 4), ("main", "Reckless Impulse", 4),
          ("main", "Wrenn's Resolve", 4), ("main", "Valakut Awakening", 4), ("main", "Wish", 4)]
         + [("side", "Orim's Chant", 4), ("side", "Prismatic Ending", 4),
            ("side", "Empty the Warrens", 4), ("side", "Wear / Tear", 3)])


def _guardar(con, chave, cartas, dia, jogador):
    return sources.store_decklist(con, source="mtgo", source_key=chave, fmt="modern",
                                  cards=cartas, event_name="Modern Challenge 32",
                                  event_date=dia, player=jogador)


def _ler(p, nome):
    return json.loads((p / nome).read_text(encoding="utf-8"))


def _soma(con, did, board):
    return con.execute("SELECT COALESCE(SUM(quantity),0) FROM decklist_cards "
                       "WHERE decklist_id = ? AND board = ?", (did, board)).fetchone()[0]


def caso_a_gravacao_soma_as_entradas_repetidas(con):
    """A página do mtgo.com parte a mesma carta em várias entradas; gravada pelo
    `store_event`, a lista do howa tem de ficar com 60 + 15, não 57 + 12."""
    assert sources.store_event(con, BLOB, URL) == 1
    did = con.execute("SELECT id FROM decklists WHERE player = 'howa'").fetchone()[0]
    assert (_soma(con, did, "main"), _soma(con, did, "side")) == (60, 15)
    tam = con.execute("SELECT quantity FROM decklist_cards WHERE decklist_id = ? "
                      "AND card_name LIKE 'Tamiyo%'", (did,)).fetchone()[0]
    assert tam == 4, tam
    print("a gravação soma as entradas repetidas: howa 60 + 15, Tamiyo 4")
    return did


def caso_reler_acerta_a_lista_curta_e_funde_a_duplicada(con, did):
    """Uma lista gravada pela regra antiga (a última entrada ganhava) relê-se da
    página e fica certa; a re-hospedagem do mtgtop8, que passa a ser a mesma
    lista, sai — e deixa-lhe o nome do arquétipo."""
    cheia = [(r["board"], r["card_name"], r["quantity"]) for r in con.execute(
        "SELECT * FROM decklist_cards WHERE decklist_id = ?", (did,))]
    # a regra antiga: Tamiyo 3 + 1 ficava 1
    con.execute("UPDATE decklist_cards SET quantity = 1 WHERE decklist_id = ? "
                "AND card_name LIKE 'Tamiyo%'", (did,))
    con.execute("UPDATE decklists SET content_hash = 'velho' WHERE id = ?", (did,))
    # a do mtgtop8 entra com o conteúdo CERTO (o hash da curta era outro, por
    # isso a dedup não as juntava)
    top8 = con.execute(
        "INSERT INTO decklists (source, source_key, format, event_name, event_date, player, "
        "content_hash, event_tier, arquetipo_fonte, arquetipo_fonte_de) "
        "VALUES ('mtgtop8','t8','modern','Modern event - MTGO Challenge 64','2026-10-15',"
        "'howa',?, 'Challenge', 'Emry Grinding Cam', 'evento')",
        (sources.content_hash("modern", cheia),)).lastrowid
    con.executemany("INSERT INTO decklist_cards VALUES (?,?,?,?)",
                    [(top8, n, q, b) for b, n, q in cheia])
    con.commit()
    assert _soma(con, did, "main") == 57

    class R:
        text = PAGINA

        def raise_for_status(self):
            pass

    antigo = sources._get_mtgo
    sources._get_mtgo = lambda url, **k: R()
    try:
        r = sources.reler_mtgo(con)
    finally:
        sources._get_mtgo = antigo
    assert r["acertadas"] == 1 and r["copias"] == 3 and r["fundidas"] == 1, r
    assert _soma(con, did, "main") == 60
    assert con.execute("SELECT COUNT(*) FROM decklists WHERE id = ?", (top8,)).fetchone()[0] == 0
    nome = con.execute("SELECT arquetipo_fonte FROM decklists WHERE id = ?", (did,)).fetchone()[0]
    assert nome == "Emry Grinding Cam", nome
    print("reler-mtgo: lista curta acertada (+3), duplicada do mtgtop8 fundida e o nome herdado")


def caso_a_troca_fica_no_historico_e_o_painel_escreve_os_ficheiros(con, raiz):
    gs = [s for s in my_decks.seguidos() if s["deck"] == "Grinding Station"][0]
    # o howa (15/10) já cá está; tira-se de cena para a primeira corrida ver a de antes
    con.execute("UPDATE decklists SET event_date = '2026-10-11' WHERE player = 'howa'")
    _guardar(con, "antes", ANTES, "2026-10-12", "Comrac")
    con.commit()
    my_decks.refresh(con, hoje="2026-10-13")
    assert con.execute("SELECT COUNT(*) FROM deck_lista_trocas").fetchone()[0] == 0, \
        "a primeira lista de um deck novo não é uma troca"
    con.execute("UPDATE decklists SET event_date = '2026-10-15' WHERE player = 'howa'")
    con.commit()
    assert gs["procura"](con)["player"] == "howa"

    my_decks.refresh(con, hoje="2026-10-16")
    t = con.execute("SELECT * FROM deck_lista_trocas").fetchall()
    assert len(t) == 1, "a troca de lista TEM de ficar gravada no histórico"
    t = t[0]
    assert (t["deck"], t["motivo"], t["de_jogador"], t["de_data"], t["para_jogador"],
            t["para_data"], t["corrida"]) == ("Grinding Station", "troca", "Comrac",
                                              "2026-10-12", "howa", "2026-10-15",
                                              "2026-10-16"), dict(t)
    assert sum(q for _b, _n, q in json.loads(t["de_cartas"])) == 75
    assert sum(q for _b, _n, q in json.loads(t["para_cartas"])) == 75
    # a mesma corrida outra vez não grava nada de novo
    my_decks.refresh(con, hoje="2026-10-16")
    assert con.execute("SELECT COUNT(*) FROM deck_lista_trocas").fetchone()[0] == 1

    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / "valencia.json").write_text('[{"id": "000"}]\n', encoding="utf-8")
    r = painel.escrever(con, raiz=raiz, hoje="2026-10-16")
    for nome in painel.FICHEIROS:
        assert (raiz / nome).exists(), nome
    assert (raiz / "historico" / "2026-10-16.json").exists()
    assert (raiz / "valencia.json").read_text(encoding="utf-8") == '[{"id": "000"}]\n', \
        "o valencia.json não se reescreve"

    for nome, campos in painel.CAMPOS.items():
        linhas = _ler(raiz, nome)
        assert linhas, f"{nome} vazio"
        for ln in linhas:
            assert list(ln) == campos, (nome, list(ln))
        if "id" in campos:
            ids = [ln["id"] for ln in linhas]
            assert len(ids) == len(set(ids)), f"{nome}: ids repetidos"
    alts = _ler(raiz, "alteracoes.json")
    assert alts == _ler(raiz / "historico", "2026-10-16.json")
    for a in alts:
        assert a["delta"] != 0 and isinstance(a["delta"], int), a
        assert a["abs"] == abs(a["delta"])
        assert a["sinal"] == ("entra" if a["delta"] > 0 else "sai")
        assert a["board"] in ("main", "sideboard")
        assert (a["de"], a["para"]) == ("Comrac 12/10", "howa 15/10")
    gst = [a for a in alts if a["carta"] == "Grinding Station"][0]
    assert gst["delta"] == -2
    est = {e["deck"]: e for e in _ler(raiz, "estado-decks.json")}
    assert set(est) == {s["deck"] for s in my_decks.seguidos()}
    assert "Jeskai Lessons" not in est and "4c Control" not in est, "o Standard saiu a 13/10"
    g = est["Grinding Station"]
    assert (g["mudou"], g["lista"], g["anterior"], g["main"], g["sideboard"]) == \
        ("sim", "howa 15/10", "Comrac 12/10", 60, 15), g
    assert g["cartas_trocadas"] == sum(a["abs"] for a in alts)
    av = _ler(raiz, "avisos.json")
    assert any(a["deck"] == "Grinding Station" and a["gravidade"] == "media"
               and "4 -> 2" in a["aviso"] for a in av), av
    assert any(a["deck"] == "Cloud (Duel Commander)" and a["gravidade"] == "media"
               and "sem lista" in a["aviso"] for a in av), av
    assert r["alteracoes"] == len(alts) and r["mudaram"] == 1
    print(f"troca gravada; painel: {len(alts)} alterações, {len(est)} decks, "
          f"{len(av)} avisos; valencia intacto")
    return alts


def caso_troca_de_arquetipo_e_oscilacao(con, raiz):
    """Mais de 60 cartas trocadas é ALTA; voltar no dia seguinte a uma lista que
    já se deixou é a oscilação, e diz-se."""
    _guardar(con, "outro", OUTRO, "2026-10-17", "Cachorrowo")
    con.commit()
    my_decks.refresh(con, hoje="2026-10-17")
    painel.escrever(con, raiz=raiz, hoje="2026-10-17")
    av = _ler(raiz, "avisos.json")
    assert any(a["gravidade"] == "alta" and "cartas trocadas" in a["aviso"]
               and a["deck"] == "Grinding Station" for a in av), av
    assert av[0]["gravidade"] == "alta", "os avisos vêm por gravidade"
    assert any(a["deck"] == "Grinding Station" and a["aviso"] == "main com 56 cartas, nao 60"
               for a in av), av
    # volta a uma lista quase igual à do howa
    volta = [(r["board"], r["card_name"], r["quantity"]) for r in con.execute(
        "SELECT * FROM decklist_cards WHERE decklist_id = (SELECT id FROM decklists "
        "WHERE player = 'howa')")]
    volta = [(b, n, q) for b, n, q in volta if n != "Haywire Mite"] + [("main", "Ornithopter", 1)]
    _guardar(con, "volta", volta, "2026-10-18", "bbotonline")
    con.commit()
    my_decks.refresh(con, hoje="2026-10-18")
    painel.escrever(con, raiz=raiz, hoje="2026-10-18")
    av = _ler(raiz, "avisos.json")
    assert any(a["deck"] == "Grinding Station" and "voltou a uma lista como a de howa"
               in a["aviso"] for a in av), av
    assert sorted(p.name for p in (raiz / "historico").iterdir()) == \
        ["2026-10-16.json", "2026-10-17.json", "2026-10-18.json"], "o histórico não se apaga"
    print("troca de arquétipo = alta; oscilação dita; o histórico acumula")


def run():
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        did = caso_a_gravacao_soma_as_entradas_repetidas(con)
        caso_reler_acerta_a_lista_curta_e_funde_a_duplicada(con, did)
        caso_a_troca_fica_no_historico_e_o_painel_escreve_os_ficheiros(con, tmp / "painel")
        caso_troca_de_arquetipo_e_oscilacao(con, tmp / "painel")
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
