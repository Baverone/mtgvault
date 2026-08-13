"""Classifica a coleção física em três estados, segundo as regras do André:

  🟢 Deck    — carta comprometida a um deck montado.
  🔵 Coleção — jogável no formato, ainda por montar ou como backup (até 4).
  🔴 Vender  — cópias acima do limite (4 construído) OU cartas que não jogam
               em lado nenhum (não aparecem em nenhuma lista que sigo).

Regras (ditadas pelo André, 2026-08-13):
  - SÓ os baldes "SPML" e "Premodern (geral)" são coleção. Todo o resto
    (Blue Farm, Cloud, Cloud cEDH, Pauper Affinity) são decks montados → Deck
    inteiro, fora da Coleção.
  - No SPML, as cartas dos 3 decks de Modern seguidos (tabela `decks`) contam
    como Deck; o resto do SPML é coleção de Standard/Pioneer/Modern/Legacy.
  - No Premodern, os decks são os 6 arquétipos do André. Não temos as listas
    exatas, por isso tira-se o CONSENSO das listas do arquétipo já recolhidas
    (assinatura → listas → cartas em >=40% delas). É aproximado, como ele pediu.
  - Uma carta de deck: as cópias que o deck precisa são Deck; as que sobram até
    4 são backup (Coleção); acima de 4, Vender.
  - Uma carta que não é de deck mas se joga no formato: Coleção até 4, resto Vender.
  - Uma carta que não aparece em NENHUMA lista do formato: Vender (a rever).
  - Terras básicas nunca vão para Vender.

Sem efeitos colaterais: lê o vault.db e devolve a classificação. Quem gera o
HTML (colecao_cor.py) é que a consome.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

# Baldes que são coleção (o resto é deck montado). Mapeia para o "pool" de decks.
COLLECTION_SUBS = {"SPML": "msl", "Premodern (geral)": "premodern"}
CONSTRUCTED_LIMIT = 4          # playset: acima disto, vender
PREMODERN_INCLUSION = 0.40     # carta em >=40% das listas do arquétipo = é do deck
MSL_FORMATS = ("standard", "pioneer", "modern", "legacy")
# Formatos "reais": se uma carta não é legal em NENHUM destes, não joga em nada.
# (Uma carta jogável mas que o André não vai usar fica na Coleção por agora —
#  vender essas é uma afinação para mais tarde, decisão dele.)
REAL_FORMATS = ("standard", "pioneer", "modern", "legacy", "premodern",
                "vintage", "pauper", "commander")

# Assinatura de cada deck de Premodern do André (carta que define o arquétipo).
# Uma lista "é" do arquétipo se contém uma destas cartas.
PREMODERN_DECKS = {
    "Stiflenought": ["Phyrexian Dreadnought"],
    "UW Replenish": ["Replenish"],
    "Enchantress": ["Argothian Enchantress", "Enchantress's Presence"],
    "Oath of Druids": ["Oath of Druids"],
    "Elves": ["Priest of Titania"],
    "Ill-Gotten Gains": ["Ill-Gotten Gains"],
}

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
          "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
          "Snow-Covered Mountain", "Snow-Covered Forest"}


def _modern_need(con):
    """Quantas cópias cada carta precisa nos 3 decks de Modern seguidos.
    MAX entre decks (partilham o core Mox Opal e monta-se um de cada vez)."""
    need = defaultdict(int)
    for r in con.execute(
        """SELECT dc.card_name nm, dc.deck_id did, SUM(dc.quantity) q
             FROM deck_cards dc JOIN decks d ON d.id = dc.deck_id
            WHERE d.format = 'modern'
            GROUP BY dc.deck_id, dc.card_name"""):
        need[r["nm"]] = max(need[r["nm"]], min(r["q"], CONSTRUCTED_LIMIT))
    return need


def _premodern_need(con):
    """Consenso das listas de cada arquétipo de Premodern do André.
    Devolve need[carta] = maior qty típica entre os arquétipos dele."""
    need = defaultdict(int)
    for deck, sigs in PREMODERN_DECKS.items():
        marks = ",".join("?" for _ in sigs)
        ids = [r[0] for r in con.execute(
            f"""SELECT DISTINCT dl.id FROM decklists dl
                  JOIN decklist_cards dc ON dc.decklist_id = dl.id
                 WHERE dl.format = 'premodern' AND dc.card_name IN ({marks})""", sigs)]
        if not ids:
            continue
        marks_id = ",".join("?" for _ in ids)
        n = len(ids)
        # Por carta: em quantas listas entra e com que quantidades (para a moda).
        seen = defaultdict(set)   # carta -> {decklist_id}
        qtys = defaultdict(list)  # carta -> [qty por lista]
        for r in con.execute(
            f"""SELECT card_name nm, decklist_id lid, SUM(quantity) q
                  FROM decklist_cards
                 WHERE decklist_id IN ({marks_id})
                   AND (board = 'main' OR board IS NULL OR board = '')
                 GROUP BY decklist_id, card_name""", ids):
            seen[r["nm"]].add(r["lid"])
            qtys[r["nm"]].append(r["q"])
        for nm, lids in seen.items():
            if nm in BASICS:
                continue
            if len(lids) / n >= PREMODERN_INCLUSION:
                mode_q = Counter(qtys[nm]).most_common(1)[0][0]
                need[nm] = max(need[nm], min(mode_q, CONSTRUCTED_LIMIT))
    return need


def _played_names(con, formats):
    q = ",".join("?" for _ in formats)
    return {r[0] for r in con.execute(
        f"""SELECT DISTINCT dc.card_name FROM decklists dl
              JOIN decklist_cards dc ON dc.decklist_id = dl.id
             WHERE dl.format IN ({q})""", tuple(formats))}


def _legal_anywhere(legalities_json):
    """True se a carta é legal (ou restrita) em algum formato real — pela Scryfall.
    É a rede de segurança contra sugerir vender cartas jogáveis por falta de dados
    nas minhas listas recolhidas."""
    try:
        leg = json.loads(legalities_json) if legalities_json else {}
    except Exception:
        return True   # na dúvida, não sugerir venda
    return any(leg.get(f) in ("legal", "restricted") for f in REAL_FORMATS)


def build(con):
    """Devolve {'colecao':[...], 'vender':[...], 'deck_total':int, 'counts':{...},
    'premodern_need':N, 'modern_need':N}. Cada linha de coleção/venda tem
    sid,nm,cmc,tl,ci,fin,lang,q (+ reason nas de venda)."""
    need = {"msl": _modern_need(con), "premodern": _premodern_need(con)}
    played = {"msl": _played_names(con, MSL_FORMATS),
              "premodern": _played_names(con, ("premodern",))}

    # Cartas físicas dos baldes de coleção, agrupadas por carta (para as regras de
    # quantidade) e guardando cada grupo físico (sid/finish/lang) para a distribuição.
    by_name = defaultdict(lambda: {"pool": None, "groups": [], "legal": True})
    for r in con.execute(
        """SELECT c.scryfall_id sid, c.name nm, c.cmc cmc, c.type_line tl,
                  c.color_identity ci, c.legalities leg, cp.finish fin, cp.language lang,
                  s.name sub, SUM(cp.quantity) q
             FROM copies cp
             JOIN cards c ON c.scryfall_id = cp.scryfall_id
             JOIN sub_collections s ON s.id = cp.sub_collection_id
            WHERE cp.purpose = 'player' AND s.name IN ('SPML','Premodern (geral)')
            GROUP BY c.scryfall_id, cp.finish, cp.language, s.name"""):
        d = by_name[r["nm"]]
        d["pool"] = COLLECTION_SUBS[r["sub"]]
        d["legal"] = _legal_anywhere(r["leg"])
        d["groups"].append(dict(r))

    colecao, vender = [], []
    deck_total = 0
    for nm, d in by_name.items():
        pool = d["pool"]
        groups = d["groups"]
        Q = sum(g["q"] for g in groups)
        is_basic = nm in BASICS
        need_q = 0 if is_basic else need[pool].get(nm, 0)
        # "Joga em algum lado" = precisa num deck, OU é legal nalgum formato real,
        # OU aparece nalguma lista que sigo. Só se falhar tudo é que é para vender.
        is_played = (is_basic or need_q > 0 or d["legal"] or nm in played[pool])

        deck_q = min(Q, need_q)
        if is_basic:
            # Terras básicas: fica tudo como coleção, nunca se vendem.
            colecao_q = Q - deck_q
            vender_q = 0
            reason = ""
        elif is_played:
            colecao_q = min(Q - deck_q, max(0, CONSTRUCTED_LIMIT - deck_q))
            vender_q = Q - deck_q - colecao_q
            reason = "excesso (mais de 4)"
        else:
            colecao_q = 0
            vender_q = Q - deck_q
            reason = "não joga em nada que eu siga"
        deck_total += deck_q

        # Distribui deck→coleção→venda pelos grupos físicos (ordem estável).
        buckets = {"deck": deck_q, "colecao": colecao_q, "vender": vender_q}
        for g in sorted(groups, key=lambda x: (x["fin"] != "nonfoil", x["lang"] != "en")):
            avail = g["q"]
            for state in ("deck", "colecao", "vender"):
                if avail <= 0 or buckets[state] <= 0:
                    continue
                take = min(avail, buckets[state])
                buckets[state] -= take
                avail -= take
                if state == "deck":
                    continue
                row = {k: g[k] for k in ("sid", "nm", "cmc", "tl", "ci", "fin", "lang", "sub")}
                row["q"] = take
                if state == "colecao":
                    colecao.append(row)
                else:
                    row["reason"] = reason
                    vender.append(row)

    counts = {"deck": deck_total,
              "colecao": sum(r["q"] for r in colecao),
              "vender": sum(r["q"] for r in vender)}
    return {"colecao": colecao, "vender": vender, "deck_total": deck_total,
            "counts": counts,
            "modern_need": len(need["msl"]), "premodern_need": len(need["premodern"])}


def main():
    from mtgvault import db
    with db.session() as con:
        rep = build(con)
    print("Necessidades de deck: Modern", rep["modern_need"], "cartas;",
          "Premodern (consenso)", rep["premodern_need"], "cartas")
    print("Contagem:", rep["counts"])
    print("\nExemplos a Vender:")
    for r in sorted(rep["vender"], key=lambda x: x["reason"])[:15]:
        print(f"  {r['q']}x {r['nm']:<28} [{r['reason']}]")


if __name__ == "__main__":
    main()
