"""Parsers do mtgo.com contra HTML real — sem rede.

Os dois blobs abaixo são trechos REAIS capturados de páginas do mtgo.com em
2026-08-02, reduzidos a uma decklist com meia dúzia de cartas (nomes, logins,
datas e chaves são os verdadeiros — só há menos cartas). Servem para trancar
os três bugs que o mtgo.com destapou quando o ciclo correu pela primeira vez:

  1. a data caía para hoje nas ligas (o blob traz `publish_date`, não `date`);
  2. o formato vinha sujo nas challenges (`format` = "CMODERN") e duplicava o
     mesmo formato (modern vs cmodern);
  3. o comandante ficava no sideboard (o mtgo serve-o em `sideboard_deck`),
     fora do main e da análise de core — e com content_hash diferente do
     mtgtop8, o que partia a deduplicação entre as fontes.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, sources  # noqa: E402

# --- página de LIGA: {name, publish_date}, comandante em sideboard_deck ------
LEAGUE_JSON = r'''{"name": "Duel Commander League", "publish_date": "2026-08-01", "site_name": "duel-commander-league-2026-08-0110931", "playeventid": "10931", "instance_id": "10931_2026-08-01", "decklists": [{"loginid": "3522198", "player": "konviczka", "instance_id": "10931_2026-08-01", "main_deck": [{"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "The Underworld Cookbook"}}, {"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "Monument to Endurance"}}, {"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "Currency Converter"}}], "sideboard_deck": [{"qty": "1", "sideboard": "true", "card_attributes": {"card_name": "Asmoranomardicadaistinaculdacar"}}]}]}'''

# --- página de CHALLENGE: {description, starttime, format:"CMODERN"} ---------
#     `player_count` é real: as challenges trazem-no (validado ao vivo a
#     2026-09-18 — "Pauper Challenge 32" → 32); as ligas não.
CHALLENGE_JSON = r'''{"description": "Modern Challenge 64", "starttime": "2026-08-01 01:00:00.0", "format": "CMODERN", "site_name": "modern-challenge-64-2026-08-0112849460", "type": "TOURNAMENT", "player_count": 64, "decklists": [{"loginid": "875470", "player": "Tree42o", "tournamentid": "12849460", "main_deck": [{"qty": "4", "sideboard": "false", "card_attributes": {"card_name": "Allosaurus Rider"}}, {"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "Wooded Foothills"}}, {"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "Ureni, the Song Unending"}}], "sideboard_deck": [{"qty": "1", "sideboard": "true", "card_attributes": {"card_name": "Atraxa, Grand Unifier"}}, {"qty": "2", "sideboard": "true", "card_attributes": {"card_name": "Nature's Claim"}}]}]}'''

LEAGUE_URL = "https://www.mtgo.com/decklist/duel-commander-league-2026-08-0110931"
CHALLENGE_URL = "https://www.mtgo.com/decklist/modern-challenge-64-2026-08-0112849460"


def _page(json_blob: str) -> str:
    """Envolve o blob como o mtgo.com o serve: dentro de <script>, seguido das
    outras duas atribuições (para o regex não-guloso ter de parar no `};` certo)."""
    return (
        "<html><head></head><body>\n"
        "<script>\n"
        f"window.MTGO.decklists.data = {json_blob};\n"
        'window.MTGO.decklists.roundNames = [];\n'
        'window.MTGO.decklists.type = "TOURNAMENT";\n'
        "</script></body></html>"
    )


def board_map(con, did):
    return {(r["board"], r["card_name"]): r["quantity"] for r in con.execute(
        "SELECT board, card_name, quantity FROM decklist_cards WHERE decklist_id = ?",
        (did,))}


def run():
    # --- parse_mtgo_page apanha o blob dentro do HTML realista --------------
    blob = sources.parse_mtgo_page(_page(LEAGUE_JSON))
    assert blob is not None, "o regex não apanhou o blob window.MTGO.decklists.data"
    assert blob["name"] == "Duel Commander League"
    assert len(blob["decklists"]) == 1
    assert sources.parse_mtgo_page("<html>sem blob nenhum</html>") is None
    print("parse_mtgo_page apanha o blob e devolve None quando não há")

    tmp = Path(tempfile.mkdtemp()) / "s.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        # --- LIGA: data real, nome real, comandante no main -----------------
        n = sources.store_event(con, sources.parse_mtgo_page(_page(LEAGUE_JSON)),
                                LEAGUE_URL)
        assert n == 1, n
        row = con.execute("SELECT * FROM decklists WHERE source='mtgo'").fetchone()
        assert row["format"] == "duel-commander", row["format"]
        assert row["event_date"] == "2026-08-01", row["event_date"]  # publish_date
        assert row["event_name"] == "Duel Commander League", row["event_name"]
        cards = board_map(con, row["id"])
        # O comandante (vinha em sideboard_deck) tem de estar no MAIN e o side vazio
        assert ("main", "Asmoranomardicadaistinaculdacar") in cards, cards
        assert not any(b == "side" for b, _ in cards), cards
        assert cards[("main", "The Underworld Cookbook")] == 1
        print("liga: data e nome corretos, comandante reencaminhado para o main")

        # --- CHALLENGE: formato normalizado (não 'cmodern'), data do starttime
        sources.store_event(con, sources.parse_mtgo_page(_page(CHALLENGE_JSON)),
                            CHALLENGE_URL)
        ch = con.execute("SELECT * FROM decklists WHERE event_name='Modern Challenge 64'").fetchone()
        assert ch["format"] == "modern", f"esperava 'modern', obtive {ch['format']!r}"
        assert ch["event_date"] == "2026-08-01", ch["event_date"]  # starttime[:10]
        chc = board_map(con, ch["id"])
        assert chc[("main", "Allosaurus Rider")] == 4      # qty vem como string "4"
        assert chc[("side", "Nature's Claim")] == 2        # não é comandante: fica no side
        assert ch["event_players"] == 64, ch["event_players"]   # player_count do blob
        assert row["event_players"] is None, row["event_players"]  # a liga não traz
        print("challenge: 'CMODERN' -> 'modern', starttime -> data, side preservado, "
              "player_count guardado")

    # --- _guess_format: premodern não pode ser classificado como modern -----
    assert sources._guess_format(
        "https://www.mtgo.com/decklist/premodern-league-2026-08-0110871") == "premodern"
    assert sources._guess_format(
        "https://www.mtgo.com/decklist/modern-league-2026-08-0110847") == "modern"
    assert sources._guess_format(
        "https://www.mtgo.com/decklist/duel-commander-league-2026-08-0110931") == "duel-commander"
    print("_guess_format distingue premodern de modern (determinístico)")

    cache_do_config()

    print("\nTUDO OK")


def cache_do_config():
    """A CACHE DO CONFIG ESQUECE-SE PELO NOME CERTO (2026-10-06).

    Treze ficheiros de teste reescrevem o config para exercitar um INTERRUPTOR e
    os treze tinham `sources._CONFIG_CACHE = None` copiado à mão — um nome que
    **não existe**. Não limpava nada: o que os fazia passar era o `_config()`
    comparar o `st_mtime`, e duas escritas no MESMO tique do relógio do sistema
    de ficheiros devolviam o config ANTERIOR. Apanhado na bateria de 06/10 pelo
    `test_foto_manda.caso_a_frase_honesta_diz_x_de_y` — vermelho uma vez, verde
    **10 de 10** corrido sozinho.

    Mede as duas pontas: o `esquecer_config` esquece mesmo **com o mtime
    empatado** (é aí que a cache era a única coisa a decidir), e nenhum ficheiro
    de teste volta a usar o nome morto.
    """
    import json                                               # noqa: PLC0415
    import os                                                 # noqa: PLC0415

    p = Path(tempfile.mkdtemp()) / "colecao_config.json"
    antes = os.environ.get("MTGVAULT_CONFIG")
    os.environ["MTGVAULT_CONFIG"] = str(p)
    try:
        p.write_text(json.dumps({"marca": "antes"}), encoding="utf-8")
        sources.esquecer_config()
        assert sources.config()["marca"] == "antes"
        mt = p.stat().st_mtime
        # A segunda escrita com o mtime EMPATADO: sem esquecer a cache, o
        # `_config()` não tem como saber que o ficheiro mudou.
        p.write_text(json.dumps({"marca": "depois"}), encoding="utf-8")
        os.utime(p, (mt, mt))
        assert sources.config()["marca"] == "antes", (
            "sem esquecer, a cache responde com o config anterior — é este o "
            "empate que torna os treze testes do interruptor intermitentes")
        sources.esquecer_config()
        assert sources.config()["marca"] == "depois", (
            "o `esquecer_config` tem de limpar a cache a sério (`_CFG_CACHE`)")
    finally:
        if antes is None:
            os.environ.pop("MTGVAULT_CONFIG", None)
        else:
            os.environ["MTGVAULT_CONFIG"] = antes
        sources.esquecer_config()

    # E NINGUÉM volta a usar o nome morto. A ÚNICA excepção declarada é este
    # ficheiro, que é o que explica a regra e por isso tem de nomear o nome
    # errado — é o padrão do `estado.medido`, onde o `db._migrate` é a excepção.
    maus = [f.name for f in sorted((Path(__file__).parent).glob("*.py"))
            if f.name != Path(__file__).name
            and "_CONFIG_CACHE" in f.read_text(encoding="utf-8")]
    assert not maus, (
        f"estes ficheiros limpam a cache do config por um nome que não existe "
        f"({maus}) — a cache é a `sources._CFG_CACHE` e quem a esquece é o "
        f"`sources.esquecer_config()`. Uma linha que parece limpar e não limpa "
        f"deixa o teste do interruptor a depender do relógio do disco")
    print("a cache do config esquece-se num sítio só, e com o mtime empatado")


if __name__ == "__main__":
    run()
