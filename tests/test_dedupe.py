"""A mesma lista vinda de fontes diferentes não pode contar duas vezes."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db, mtgtop8, sources  # noqa: E402

CLOUD = [("main", "Cloud, Midgar Mercenary", 1),
         ("main", "Swords to Plowshares", 1),
         ("main", "Snow-Covered Plains", 26),
         ("main", "Stoneforge Mystic", 1)]

# Trecho real de uma página de evento do mtgtop8 (MTGO League, 22/07/26),
# no layout ANTIGO: deck e jogador coladinhos com event?e=..&amp;d=..&amp;f=..
EVENTO = '''
<a href="event?e=88639&amp;d=872806&amp;f=EDH">Thanos, the Mad Titan</a>
<a href="search?player=wooop_orc">wooop_orc</a>
<a href="event?e=88639&amp;d=872807&amp;f=EDH">Cloud, Midgar Mercenary</a>
<a href="search?player=xJCloud">xJCloud</a>
<a href="event?e=88639&amp;d=872808&amp;f=EDH">Yoshimaru</a>
<a href="search?player=Nicholas+Balugani">Nicholas Balugani</a>
'''

# Trecho REAL do layout NOVO (evento e=89021, papel, 2026-07-30), capturado em
# 2026-08-02 com os espaços comprimidos. Os links de deck passaram a relativos
# (?e=..&d=..&f=.., sem &amp;) e o link do jogador já não vem colado ao do deck:
# há <div>s de permeio, e o mesmo deck aparece em vários links por linha
# (miniatura + nome). Foi isto que o parser antigo deixou de apanhar.
EVENTO_NOVO = (
    'class=hover_tr align=left> <div style="display:flex;align-items:center;"> '
    '<div class=S14>2</div> <div><a href=?e=89021&d=875670&f=EDH>'
    '<img src=/metas_thumbs/1571.jpg></a></div> <div style="flex:1;"> '
    '<div class=S14><a href=?e=89021&d=875670&f=EDH></a> </div> '
    '<div align=right class=G11><a class=player href=search?player=Anthony+Tessier>'
    'Anthony Tessier</a></div> </div> </div> '
    '<div class=hover_tr align=left> <div style="display:flex;align-items:center;"> '
    '<div class=S14>3</div> <div><a href=?e=89021&d=875671&f=EDH>'
    '<img src=/metas_thumbs/2153.jpg></a></div> <div style="flex:1;"> '
    '<div class=S14><a href=?e=89021&d=875671&f=EDH>Oswald Fiddlebender</a> </div> '
    '<div align=right class=G11><a class=player href=search?player=Alex+Dumont>'
    'Alex Dumont</a></div> </div> </div>'
)

# Trecho REAL de um export .dec do mtgtop8 (deck de Reanimator, Legacy, capturado
# em 2026-08-02). Cada carta vem prefixada com o código de edição entre parênteses
# retos (vazio quando é edição recente). O parser tem de o remover, senão os nomes
# não batem com o catálogo nem com as listas do mtgo — e a dedup nunca dispara.
DEC_REAL = """// Deck file created with mtgtop8.com
4 [AVR] Griselbrand
2 [] Koma, World-Eater
4 [TE] Reanimate
SB:  4 [ON] Chain of Smog
SB:  4 [] Witherbloom Apprentice
"""


def n_listas(con):
    return con.execute("SELECT COUNT(*) c FROM decklists").fetchone()["c"]


def run():
    tmp = Path(tempfile.mkdtemp()) / "d.db"
    with db.session(tmp, tmp.with_name("cat.db")) as con:
        # --- a mesma lista, primeiro do mtgo, depois do mtgtop8 ----------
        a = sources.store_decklist(
            con, source="mtgo", source_key="k1", fmt="duel-commander",
            cards=CLOUD, event_date="2026-07-22", player="xJCloud")
        assert a is not None
        b = sources.store_decklist(
            con, source="mtgtop8", source_key="872807", fmt="duel-commander",
            cards=CLOUD, event_date="2026-07-22", player="xJCloud")
        assert b is None, "o mtgtop8 não devia duplicar o que já veio do mtgo"
        assert n_listas(con) == 1
        print("mtgtop8 não duplica a lista que já veio do mtgo")

        # --- ordem inversa: o mtgo substitui o mtgtop8 --------------------
        sources.store_decklist(
            con, source="mtgtop8", source_key="999", fmt="legacy",
            cards=[("main", "Brainstorm", 4)], event_date="2026-07-20",
            player="alguem")
        sources.store_decklist(
            con, source="mtgo", source_key="k2", fmt="legacy",
            cards=[("main", "Brainstorm", 4)], event_date="2026-07-20",
            player="alguem")
        fontes = [r["source"] for r in con.execute(
            "SELECT source FROM decklists WHERE format = 'legacy'")]
        assert fontes == ["mtgo"], fontes
        print("mtgo substitui a versão do mtgtop8 quando chega depois")

        # --- jogadores diferentes = listas diferentes ---------------------
        sources.store_decklist(
            con, source="mtgtop8", source_key="1000", fmt="duel-commander",
            cards=CLOUD, event_date="2026-07-22", player="OutroJogador")
        assert n_listas(con) == 3, "dois jogadores distintos são duas listas"
        print("jogadores diferentes com a mesma lista contam as duas")

        # --- lista diferente no mesmo dia ---------------------------------
        outra = CLOUD + [("main", "Mother of Runes", 1)]
        assert sources.store_decklist(
            con, source="mtgtop8", source_key="1001", fmt="duel-commander",
            cards=outra, event_date="2026-07-22", player="xJCloud") is not None
        print("uma carta diferente já é outra lista")

        # --- parsing do jogador: layout ANTIGO ----------------------------
        jog = mtgtop8.parse_deck_entries(EVENTO)
        assert jog[872807] == "xJCloud", jog
        assert jog[872806] == "wooop_orc", jog
        assert jog[872808] == "Nicholas Balugani", jog
        print(f"Layout antigo: {len(jog)} jogadores extraídos")

        # --- parsing do jogador: layout NOVO (links relativos) ------------
        ids = mtgtop8.parse_deck_ids(EVENTO_NOVO)
        assert ids == [875670, 875671], ids
        jn = mtgtop8.parse_deck_entries(EVENTO_NOVO)
        assert jn[875670] == "Anthony Tessier", jn
        assert jn[875671] == "Alex Dumont", jn
        print(f"Layout novo (relativo): {len(jn)} jogadores extraídos")

        # --- .dec: o código de edição [SET] tem de ser removido -----------
        cards = mtgtop8.parse_dec(DEC_REAL)
        assert not any(n.startswith("[") for _, n, _ in cards), cards
        assert ("main", "Griselbrand", 4) in cards, cards
        assert ("main", "Koma, World-Eater", 2) in cards, cards   # prefixo vazio []
        assert ("side", "Chain of Smog", 4) in cards, cards
        # O content_hash de um .dec com [SET] tem de ser igual ao de uma lista
        # de nomes limpos — é o que faz a dedup entre mtgo e mtgtop8 disparar.
        limpo = [("main", "Griselbrand", 4), ("main", "Koma, World-Eater", 2),
                 ("main", "Reanimate", 4), ("side", "Chain of Smog", 4),
                 ("side", "Witherbloom Apprentice", 4)]
        assert sources.content_hash("legacy", cards) == sources.content_hash("legacy", limpo)
        # Em formato de comandante, o SB vai para o main (comandante conta p/ 100)
        cmd = mtgtop8.parse_dec(DEC_REAL, commander_format=True)
        assert ("main", "Chain of Smog", 4) in cmd and not any(b == "side" for b, _, _ in cmd)
        print("parse_dec: [SET] removido, hash coincide com nomes limpos, SB->main em comandante")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
