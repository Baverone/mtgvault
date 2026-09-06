"""A matemática do núcleo (core) vs tech.

O CLAUDE.md e o README apontam para este ficheiro como o sítio onde o exemplo
canónico está trancado ("Não mudes o cálculo sem atualizar esse teste") — mas o
ficheiro não existia. Fica aqui, com o exemplo do enunciado:

    uma carta em 100% das listas, 80% com 3 cópias e 20% com 4
    P(>=3) = 1.00 -> core        P(>=4) = 0.20 -> não core
    core_copies = 3,  flex_copies = 3.2 - 3 = 0.2
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault.analysis import card_roles, cluster_decklists, jaccard  # noqa: E402


def lista(**cartas):
    return dict(cartas)


def run():
    # --- o exemplo canónico: 80% joga 3 cópias, 20% joga 4 ----------------
    listas = [{"Bolt": 3}] * 8 + [{"Bolt": 4}] * 2
    r = card_roles(listas)["Bolt"]
    assert r["core_copies"] == 3, r
    assert abs(r["flex_copies"] - 0.2) < 1e-9, r
    assert r["role"] == "core", r
    assert r["inclusion_rate"] == 1.0, r
    assert r["avg_copies_all"] == 3.2, r
    assert r["dist"] == {"3": 0.8, "4": 0.2}, r
    print("exemplo 80/20: core=3, flex=0.2 (o do CLAUDE.md e do README)")

    # --- o limiar dos 90% é medido sobre TODAS as listas, não só as que a
    #     jogam: 85% com 4 cópias não chega para a 4.ª ser core ------------
    listas = [{"Bolt": 4}] * 85 + [{"Ponder": 1}] * 15
    r = card_roles(listas)["Bolt"]
    assert r["core_copies"] == 0, r
    assert r["role"] == "flex", r        # inclusão 0.85 >= 0.40
    print("85% de inclusão com playset: sem core, mas flex (limiar sobre todas)")

    # --- 91% já chega -----------------------------------------------------
    listas = [{"Bolt": 4}] * 91 + [{"Ponder": 1}] * 9
    assert card_roles(listas)["Bolt"]["core_copies"] == 4
    print("91% de inclusão com playset: core=4")

    # --- carta esporádica = tech -----------------------------------------
    listas = [{"Bolt": 4}] * 90 + [{"Bolt": 4, "Boil": 1}] * 10
    r = card_roles(listas)["Boil"]
    assert r["role"] == "tech", r
    assert r["core_copies"] == 0 and r["inclusion_rate"] == 0.10, r
    print("carta em 10% das listas: tech")

    # --- sem listas não se inventa nada ----------------------------------
    assert card_roles([]) == {}
    print("zero listas -> zero papéis (não inventa)")

    # --- clustering: as terras básicas não podem colar decks diferentes ---
    burn = {"Lightning Bolt", "Lava Spike", "Boros Charm", "Mountain"}
    tron = {"Karn Liberated", "Urza's Tower", "Expedition Map", "Forest"}
    assert jaccard(burn, tron) == 0.0
    clusters = cluster_decklists({1: burn, 2: set(burn) | {"Skewer"}, 3: tron})
    grupos = sorted(sorted(m) for m in clusters.values())
    assert grupos == [[1, 2], [3]], grupos
    print("clustering separa Burn de Tron e junta as duas listas de Burn")

    print("\nTUDO OK")


if __name__ == "__main__":
    run()
