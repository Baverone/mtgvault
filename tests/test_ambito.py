"""Âmbito do metagame por formato (decisões do André, 2026-09-07).

À letra:
  - "Duel Commander: só quero listas do comandante que tinha pedido (Cloud)."
  - "Pauper também não precisa, pois só sigo a lista Pauper do jogador
     específico (Luffy)."
  - "Premodern: o deck de Stiflenought não preciso de listas, sigo a lista do
     jogador específico (Luffy). Preciso de consenso para lista de alguns decks
     de Premodern: Replenish, Enchantress."

Este teste tranca as três pontas que custam caro se partirem em silêncio:
  1. tirar o Pauper do metagame NÃO pode matar a vigilância do Luffy (o
     `watchlist` não vai à rede — lê o que o harvest guardou);
  2. o UW Replenish e a Enchantress têm de ficar SEPARADOS (96% das listas de
     Enchantress jogam Replenish; sem a regra `none` eram o mesmo arquétipo);
  3. a lista padrão calculada de decklists em memória tem de dar o MESMO que a
     calculada da tabela `card_roles` — senão o consenso de Premodern diverge do
     resto do vault sem ninguém dar por isso.

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# O config manda na regra e tem de estar em vigor ANTES de o `sources` ser
# importado a valer. Escreve-se um igual ao do repositório para o teste não
# passar a depender de o André não lhe mexer.
CFG = {
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "duel-commander": {"min_jogadores_presencial": 0, "ligas": True},
        "pauper": {"tiers": [], "ligas": False},
    },
    "formatos_metagame": ["standard", "pioneer", "modern"],
    "premodern_arquetipos_alvo": ["UW Replenish", "Enchantress"],
    "so_jogadores_vigiados": ["pauper"],
}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import analysis, db, sources, stock, tagging, watchlist  # noqa: E402

LUFFY = "LuffyDoChapeuDePalha"
AFFINITY = [("main", "Frogmite", 4), ("main", "Carapace Forger", 4),
            ("main", "Island", 16), ("side", "Dispel", 2)]
OUTRO = [("main", "Lightning Bolt", 4), ("main", "Mountain", 20)]


def _base():
    d = Path(tempfile.mkdtemp())
    return db.session(d / "v.db", d / "c.db")


# ---------------------------------------------------------------------------
def caso_pauper_sem_metagame():
    """O Pauper não conta para nada — nem as Challenges, que noutro formato contam."""
    assert sources.metagame_rules("pauper")["tiers"] == []
    assert not sources.lista_conta(
        {"event_tier": "Challenge", "event_players": None, "source": "mtgo"}, "pauper")
    assert sources.lista_conta(
        {"event_tier": "Challenge", "event_players": None, "source": "mtgo"}, "modern")
    # ... e o SQL responde o mesmo: só as manuais.
    sql, params = sources.counting_sql("pauper", "d")
    assert "manual" in sql and not params
    print("pauper: nenhuma lista conta para o metagame (só as manuais)")


def caso_so_o_jogador_vigiado_e_guardado():
    """A ponta perigosa: o Pauper sai do metagame mas a lista do Luffy TEM de
    continuar a entrar, senão a vigilância congela sem dar erro."""
    assert sources.so_jogadores_vigiados() == {"pauper"}
    with _base() as con:
        watchlist.add(con, "mtgo_player", LUFFY, "Luffy — Pauper", "pauper")

        def guarda(player, cards=AFFINITY, fmt="pauper", source="mtgo"):
            return sources.store_decklist(
                con, source=source, source_key=f"{fmt}|{player}|{cards[0][1]}", fmt=fmt,
                cards=cards, event_name="Pauper Challenge 32",
                event_date="2026-09-01", player=player)

        assert guarda(LUFFY), "a lista do jogador vigiado guarda-se"
        assert guarda("outro_qualquer", OUTRO) is None, "a de mais ninguém, não"
        assert guarda("", OUTRO) is None, "nem uma sem jogador"
        # O mesmo jogador noutro formato não está vigiado lá — mas Modern não está
        # em `so_jogadores_vigiados`, por isso guarda-se na mesma.
        assert guarda("desconhecido", OUTRO, fmt="modern")
        # Manual passa sempre: é a porta de entrada do André.
        assert sources.store_manual(con, "4 Frogmite\n16 Island", "pauper",
                                    "à mão", "2026-09-02", "quem quiser")

        n = con.execute("SELECT COUNT(*) c FROM decklists WHERE format='pauper' "
                        "AND source='mtgo'").fetchone()["c"]
        assert n == 1, f"só devia lá estar a lista do Luffy, estão {n}"

        # E a vigilância encontra-a — que é o ponto de tudo isto.
        wid = con.execute("SELECT id FROM watched WHERE key = ?", (LUFFY,)).fetchone()["id"]
        res = watchlist.check_mtgo_player(con, wid)
        assert res["found"] and res["changed"]
        assert ("main", "Frogmite", 4) in res["cards"]
    print("pauper: guarda-se a lista do Luffy (e a vigilância vê-a), mais nenhuma")


def caso_regra_none_separa_replenish_de_enchantress():
    """Sem `none`, "tem Replenish" apanhava as duas — a Enchantress joga-o em 96%
    das listas."""
    ench = {"Argothian Enchantress", "Enchantress's Presence", "Serra's Sanctum",
            "Replenish", "Opalescence", "Wild Growth"}
    repl = {"Replenish", "Opalescence", "Attunement", "Parallax Wave", "Intuition"}
    rules = tagging.load_rules().get("premodern") or []
    assert rules, "archetype_rules.json tem de ter regras de premodern"
    nomes = {r["name"] for r in rules}
    assert {"UW Replenish", "Enchantress"} <= nomes

    def tags(cards):
        return {r["name"] for r in rules if tagging._matches(cards, r)}

    assert "UW Replenish" in tags(repl)
    assert "Enchantress" not in tags(repl)
    assert "Enchantress" in tags(ench)
    assert "UW Replenish" not in tags(ench), "a Enchantress joga Replenish e não é UW Replenish"
    assert "Enchantress (GW Sanctum)" in tags(ench), "a variante também etiqueta (etiqueta dupla)"
    print("premodern: UW Replenish e Enchantress separados pela regra `none`")


def caso_alvos_de_premodern_do_config():
    import premodern_decks
    assert premodern_decks.alvos() == ["UW Replenish", "Enchantress"]
    # Os alvos TÊM de existir em archetype_rules.json, senão o passo diário
    # calcula o consenso de um arquétipo que ninguém etiqueta e vem vazio.
    nomes = {r["name"] for r in tagging.load_rules().get("premodern", [])}
    assert set(premodern_decks.alvos()) <= nomes
    print("premodern: alvos do config batem certo com as regras de arquétipo")


def caso_formatos_do_metagame_saem_do_config():
    import meta_coverage
    fmts = [f[0] for f in meta_coverage.FORMATS]
    assert fmts == ["standard", "pioneer", "modern"]
    assert "premodern" not in fmts, "o Premodern saiu das páginas de metagame"
    # metagame.py e decks_faziveis.py leem a MESMA lista — não têm cópia própria.
    import decks_faziveis
    import metagame
    assert metagame.mc.FORMATS is meta_coverage.FORMATS
    assert decks_faziveis.mc.FORMATS is meta_coverage.FORMATS
    print("metagame/cobertura/decks-fazíveis: formatos vêm do colecao_config.json")


def caso_lista_padrao_de_listas_em_memoria():
    """O `stock_from_lists` tem de dar o MESMO que o `stock_list` da base de dados
    — é a mesma matemática, e é por isso que partilham o `_slots`."""
    # O exemplo canónico do test_analysis: 8 listas com 3 cópias, 2 com 4.
    listas = [{"Counterspell": 3, "Island": 20}] * 8 + [{"Counterspell": 4, "Island": 20}] * 2
    roles = analysis.card_roles(listas)
    assert roles["Counterspell"]["core_copies"] == 3

    sl = stock.stock_from_lists("premodern", listas)
    quantos = {c["card_name"]: c["quantity"] for c in sl["main"]}
    assert quantos["Counterspell"] == 4, "a 4.ª cópia tem p=0.2 e ainda entra no limiar"
    assert sl["main_count"] == 24 and sl["main_target"] == 60
    assert sl["n"] == 10

    # Singleton: em Commander o alvo são 100 cartas, não 60+15.
    assert stock.stock_from_lists("duel-commander", listas)["main_target"] == 100
    assert stock.stock_from_lists("duel-commander", listas)["side_target"] == 0

    # E o caminho da base de dados chega ao mesmo através do mesmo `_slots`.
    dbslots = stock._slots({"Counterspell": roles["Counterspell"]})
    assert [round(s["p"], 3) for s in dbslots] == [1.0, 1.0, 1.0, 0.2]
    print("stock: a lista padrão de decklists em memória bate com a da base de dados")


def caso_consenso_de_premodern_ponta_a_ponta():
    """Do harvest ao deck: listas -> etiquetas -> consenso -> decks/deck_cards."""
    import premodern_decks
    ench = [("main", n, q) for n, q in
            [("Argothian Enchantress", 4), ("Enchantress's Presence", 4),
             ("Serra's Sanctum", 4), ("Replenish", 3), ("Opalescence", 3),
             ("Wild Growth", 4), ("Sterling Grove", 3), ("Forest", 8), ("Plains", 4)]]
    repl = [("main", n, q) for n, q in
            [("Replenish", 4), ("Opalescence", 4), ("Attunement", 4),
             ("Parallax Wave", 4), ("Intuition", 3), ("Frantic Search", 3),
             ("Island", 8), ("Plains", 6)]]
    with _base() as con:
        for i in range(6):
            for nome, cards in (("ench", ench), ("repl", repl)):
                assert sources.store_decklist(
                    con, source="mtgo", source_key=f"{nome}{i}", fmt="premodern",
                    cards=cards, event_name="Premodern Challenge 32",
                    event_date=f"2026-09-0{i + 1}", player=f"{nome}{i}")
        assert tagging.tag_format(con, "premodern") > 0
        assert premodern_decks.consensus(con, "UW Replenish")["n"] == 6
        assert premodern_decks.consensus(con, "Enchantress")["n"] == 6

        premodern_decks.refresh(con)
        cartas = {}
        for r in con.execute(
                """SELECT d.name dn, dc.card_name nm FROM deck_cards dc
                     JOIN decks d ON d.id = dc.deck_id"""):
            cartas.setdefault(r["dn"], set()).add(r["nm"])
        assert "Argothian Enchantress" in cartas["Enchantress (consenso)"]
        assert "Argothian Enchantress" not in cartas["UW Replenish (consenso)"]
        assert "Attunement" in cartas["UW Replenish (consenso)"]
        # Os alvos são decks POR MONTAR: não podem estar em `decks_vigiados`, que
        # é o que desconta cartas à coleção disponível (meta_coverage).
        vig = set(sources.config().get("decks_vigiados") or [])
        assert not (vig & set(cartas)), "um alvo de consenso não é um deck vigiado"
    print("premodern: consenso ponta a ponta grava dois decks separados")


CASOS = [caso_pauper_sem_metagame, caso_so_o_jogador_vigiado_e_guardado,
         caso_regra_none_separa_replenish_de_enchantress,
         caso_alvos_de_premodern_do_config, caso_formatos_do_metagame_saem_do_config,
         caso_lista_padrao_de_listas_em_memoria,
         caso_consenso_de_premodern_ponta_a_ponta]

if __name__ == "__main__":
    for c in CASOS:
        c()
    print("TUDO OK")
