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
CHALLENGE_JSON = r'''{"description": "Modern Challenge 64", "starttime": "2026-08-01 01:00:00.0", "format": "CMODERN", "site_name": "modern-challenge-64-2026-08-0112849460", "type": "TOURNAMENT", "decklists": [{"loginid": "875470", "player": "Tree42o", "tournamentid": "12849460", "main_deck": [{"qty": "4", "sideboard": "false", "card_attributes": {"card_name": "Allosaurus Rider"}}, {"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "Wooded Foothills"}}, {"qty": "1", "sideboard": "false", "card_attributes": {"card_name": "Ureni, the Song Unending"}}], "sideboard_deck": [{"qty": "1", "sideboard": "true", "card_attributes": {"card_name": "Atraxa, Grand Unifier"}}, {"qty": "2", "sideboard": "true", "card_attributes": {"card_name": "Nature's Claim"}}]}]}'''

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
        print("challenge: 'CMODERN' -> 'modern', starttime -> data, side preservado")

    # --- _guess_format: premodern não pode ser classificado como modern -----
    assert sources._guess_format(
        "https://www.mtgo.com/decklist/premodern-league-2026-08-0110871") == "premodern"
    assert sources._guess_format(
        "https://www.mtgo.com/decklist/modern-league-2026-08-0110847") == "modern"
    assert sources._guess_format(
        "https://www.mtgo.com/decklist/duel-commander-league-2026-08-0110931") == "duel-commander"
    print("_guess_format distingue premodern de modern (determinístico)")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
