"""Loadout: os decks que ficam montados em deckboxes, e o que sobra para vender.

O André (2026-09-07): *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."*

O LOADOUT é a lista de decks que estão montados AO MESMO TEMPO. Está em
`colecao_config.json -> loadout`: um slot por caixa, cada um com a fonte da sua
lista (`vigiado` / `deck` / `consenso`), o balde onde as cartas vivem, a
prioridade (quem ganha um conflito) e as restrições de material.

O que este módulo faz é ALOCAR exemplares físicos aos slots. Não é uma soma de
coberturas independentes: uma cópia física só entra numa caixa de cada vez, por
isso a alocação é global e por ordem de prioridade. Daí saírem três coisas que
uma cobertura por deck nunca dá:

  * **conflito** — duas caixas querem a mesma carta e não há cópias para as duas;
  * **substituto** — a cópia existe mas não serve àquela caixa (é EN num deck de
    Premodern, é nonfoil num deck que ele quer todo em foil);
  * **venda** — o que sobra depois de alocar tudo e de guardar o backup.

DUAS REGRAS DE MATERIAL, ditadas pelo André no mesmo dia
--------------------------------------------------------
1. *"Para Premodern as cartas são das edições que tínhamos visto e em Português;
   essas cartas NÃO entram para outros formatos!!"* — uma cópia PT de uma
   impressão da era Premodern (até ao Scourge, 2003-05-26) fica TRANCADA ao
   Premodern. E, do outro lado, um slot de Premodern só fecha com cópias PT: uma
   EN aparece como substituto ("serve mas não é PT"), não como slot fechado.
2. *"Standard, Pioneer, Modern e Legacy: as cartas são todas Foil (menos as
   Reserved List)"* — nesses slots só contam `foil`/`etched`; uma carta da
   Reserved List (`catalog.cards.reserved`) pode ser nonfoil. Uma nonfoil de uma
   carta não-RL NÃO fecha o slot: fica como substituto ("tenho em nonfoil").

A tranca de PT tem uma excepção que os dados obrigam a ter: as cópias que vivem
no BALDE de outro slot do loadout já são desse deck (o Blue Farm tem um Lotus
Petal e um Tarnished Citadel PT de 1997/2001 dentro da caixa dele). Trancá-las
ao Premodern desmontaria um deck que está montado — por isso o balde manda.

E o outro lado da mesma regra (André, 2026-09-07): *"O Premodern não é para
olhar para a minha Caixa RL, pois o Premodern só vai usar as cartas em
Português; na Caixa RL só estão cartas RL em inglês."* Um slot de Premodern nem
VÊ o balde `Caixa Reserved List`: as cópias de lá não fecham o slot, não contam
como substituto e não descontam no custo. Para uma caixa de Premodern, uma carta
que só existe em EN é FALTA — compra-se em PT. Isto é mais forte do que a regra
da língua, e é de propósito: um substituto diz "tens a carta, decide se abres
excepção", e aqui ele já decidiu que não abre.

Sem rede e sem efeitos colaterais: lê o `vault.db` e devolve números.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from . import sources, stock

# Última edição legal em Premodern (Scourge). É por aqui que se decide se uma
# impressão é "da era" — a alternativa (a legalidade `premodern` da Scryfall) é
# por carta e não por impressão, e o que o André descreveu foram as EDIÇÕES.
PREMODERN_END = "2003-05-26"
# O balde da Reserved List. Os slots de Premodern não olham para aqui (regra do
# André, 2026-09-07) — ver o cabeçalho do módulo e `_fora_de_vista`.
BALDE_RL = "Caixa Reserved List"
CONSTRUCTED_LIMIT = 4                      # playset: acima disto é excedente
FOIL_FINISHES = ("foil", "etched")
COMMANDER_FORMATS = {"duel-commander", "cedh", "commander", "edh"}
# Se uma carta não é legal em nenhum destes, não joga em lado nenhum. É a mesma
# rede de segurança do classify.py: nunca sugerir vender uma carta jogável.
REAL_FORMATS = ("standard", "pioneer", "modern", "legacy", "premodern",
                "vintage", "pauper", "commander")

BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
          "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
          "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes"}


def _front(name: str) -> str:
    """Nome da frente de uma carta de dupla face — é assim que as listas a escrevem."""
    return (name or "").split(" // ")[0]


# ---------------------------------------------------------------------------
# Preços
# ---------------------------------------------------------------------------
def card_price(con, name: str, finish: str = "nonfoil",
               source: str = "cardmarket") -> tuple[float | None, str | None]:
    """(preço da impressão mais barata, acabamento a que esse preço corresponde).

    O `wantlist.cheapest_price` só olha para nonfoil, e metade do loadout tem de
    ser comprada em FOIL — com o preço nonfoil o custo de fechar esses decks vinha
    sistematicamente abaixo do real. Quando não há preço foil, devolve o nonfoil e
    diz que é nonfoil, para quem mostra poder marcar a estimativa como incerta.
    """
    fins = FOIL_FINISHES if finish in FOIL_FINISHES else ("nonfoil",)
    marks = ",".join("?" * len(fins))
    row = con.execute(
        f"""SELECT MIN(p.trend) preco FROM cards c
              JOIN price_latest p ON p.scryfall_id = c.scryfall_id
             WHERE c.name = ? AND p.source = ? AND p.finish IN ({marks})""",
        (name, source, *fins)).fetchone()
    if row and row["preco"] is not None:
        return row["preco"], fins[0]
    if fins[0] == "nonfoil":
        return None, None
    row = con.execute(
        """SELECT MIN(p.trend) preco FROM cards c
             JOIN price_latest p ON p.scryfall_id = c.scryfall_id
            WHERE c.name = ? AND p.source = ? AND p.finish = 'nonfoil'""",
        (name, source)).fetchone()
    return ((row["preco"], "nonfoil") if row and row["preco"] is not None
            else (None, None))


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
def config_slots() -> list[dict]:
    """`colecao_config.json -> loadout`, sem as chaves de ajuda `_xxx`."""
    v = sources.config().get("loadout") or []
    return [{k: x[k] for k in x if not str(k).startswith("_")} for x in v]


def _retencao() -> dict[str, int]:
    """Baldes com `reter_extras_meses` (regras_colecao). Enquanto não houver fonte
    de "última utilização" (ver CLAUDE.md), estes extras RETÊM-SE — nunca entram
    na venda; a página di-lo em vez de fingir que a regra já corre."""
    regras = sources.config().get("regras_colecao") or {}
    return {b: r["reter_extras_meses"] for b, r in regras.items()
            if isinstance(r, dict) and r.get("reter_extras_meses")}


# ---------------------------------------------------------------------------
# De onde vem a lista de cada slot
# ---------------------------------------------------------------------------
def _cards_from_deck(con, name: str) -> tuple[list[tuple[str, str, int]], str]:
    row = con.execute("SELECT id, notes FROM decks WHERE name = ?", (name,)).fetchone()
    if row is None:
        return [], f"deck {name!r} não existe na tabela `decks`"
    cards = [(("side" if r["board"] == "side" else "main"), _front(r["nm"]), r["q"])
             for r in con.execute(
                 """SELECT card_name nm, board, SUM(quantity) q FROM deck_cards
                     WHERE deck_id = ? GROUP BY card_name, board""", (row["id"],))]
    return cards, (row["notes"] or "")


def _cards_from_watched(con, label: str) -> tuple[list[tuple[str, str, int]], str]:
    row = con.execute(
        """SELECT ws.cards, ws.taken_at FROM watched w
             JOIN watched_snapshots ws ON ws.watched_id = w.id
            WHERE w.label = ? ORDER BY ws.taken_at DESC LIMIT 1""", (label,)).fetchone()
    if row is None:
        return [], f"vigiado {label!r} ainda sem snapshot"
    agg: dict[tuple[str, str], int] = defaultdict(int)
    for board, nm, q in json.loads(row["cards"]):
        agg[("side" if board == "side" else "main", _front(nm))] += q
    return ([(b, n, q) for (b, n), q in agg.items()],
            f"lista vigiada de {row['taken_at']}")


def _cards_from_consensus(con, fmt: str, assinatura: list[str]
                          ) -> tuple[list[tuple[str, str, int]], str]:
    """Consenso de um arquétipo identificado por carta-assinatura.

    Só listas que CONTAM (`sources.counting_sql`) e o mesmo cálculo de lista
    padrão de toda a gente (`stock.stock_from_lists`) — não se inventa aqui um
    segundo consenso que discordasse do resto do vault em silêncio.
    """
    if not assinatura:
        return [], "sem assinatura configurada"
    conta, cp = sources.counting_sql(fmt, "d")
    marks = ",".join("?" * len(assinatura))
    ids = [r[0] for r in con.execute(
        f"""SELECT DISTINCT d.id FROM decklists d
              JOIN decklist_cards dc ON dc.decklist_id = d.id
             WHERE d.format = ? AND dc.card_name IN ({marks}) AND {conta}""",
        (fmt, *assinatura, *cp))]
    if len(ids) < stock_min_lists():
        return [], f"só {len(ids)} listas contam — poucas para consenso"
    ph = ",".join("?" * len(ids))
    main: dict[int, dict[str, int]] = defaultdict(dict)
    side: dict[int, dict[str, int]] = defaultdict(dict)
    for r in con.execute(
            f"""SELECT decklist_id i, card_name nm, quantity q, board b
                  FROM decklist_cards WHERE decklist_id IN ({ph})""", ids):
        (side if r["b"] == "side" else main)[r["i"]][_front(r["nm"])] = r["q"]
    sl = stock.stock_from_lists(fmt, [main[i] for i in ids if main.get(i)],
                                [side[i] for i in ids if side.get(i)])
    cards = [("main", c["card_name"], c["quantity"]) for c in sl["main"]]
    cards += [("side", c["card_name"], c["quantity"]) for c in sl["side"]]
    return cards, f"consenso de {len(ids)} listas"


def stock_min_lists() -> int:
    return 5      # o mesmo mínimo do analysis.rebuild_roles / premodern_decks


def _slot_cards(con, s: dict) -> tuple[list[tuple[str, str, int]], str]:
    fonte = (s.get("fonte") or "").lower()
    ref = s.get("ref")
    if not ref and fonte != "consenso":
        return [], "slot por confirmar — sem lista escolhida"
    if fonte == "deck":
        return _cards_from_deck(con, ref)
    if fonte == "vigiado":
        return _cards_from_watched(con, ref)
    if fonte == "consenso":
        return _cards_from_consensus(con, s["formato"], s.get("assinatura") or [])
    return [], f"fonte {fonte!r} desconhecida"


def resolve_slots(con, cfg_slots: list[dict] | None = None) -> list[dict]:
    """Os slots do loadout com a lista de cada um já resolvida.

    `variantes`: um slot pode juntar mais do que um deck (o André: *"1 deck de
    Modern (+ possíveis variantes desse deck — as variantes partilham a caixa")*.
    A caixa leva a UNIÃO das cartas, cada uma na quantidade máxima que alguma
    variante pede, e as que não são comuns a todas ficam marcadas — é o que se
    quer ver ao montar: o que sai e entra para trocar de variante.
    """
    out = []
    for s in (cfg_slots if cfg_slots is not None else config_slots()):
        s = dict(s)
        cards, nota = _slot_cards(con, s)
        so_de: dict[str, set[str]] = defaultdict(set)
        variantes = list(s.get("variantes") or [])
        if variantes:
            base = {(b, n): q for b, n, q in cards}
            for v in variantes:
                vc, _ = _cards_from_deck(con, v)
                for b, n, q in vc:
                    base[(b, n)] = max(base.get((b, n), 0), q)
                    so_de[n].add(v)
            for _b, n, _q in cards:
                so_de.pop(n, None)          # está na base: não é exclusiva
            cards = [(b, n, q) for (b, n), q in base.items()]
        s["cards"] = sorted(cards, key=lambda c: (c[0] != "main", c[1]))
        s["nota"] = nota
        s["so_de_variante"] = {n: sorted(v) for n, v in so_de.items()}
        s["vazio"] = not cards
        s.setdefault("prioridade", 99)
        s.setdefault("nome", s.get("ref") or s.get("slot"))
        out.append(s)
    return sorted(out, key=lambda x: (x["prioridade"], x["nome"]))


# ---------------------------------------------------------------------------
# Exemplares
# ---------------------------------------------------------------------------
def _legal_em(leg_json, formatos) -> bool:
    try:
        leg = json.loads(leg_json) if leg_json else {}
    except (TypeError, ValueError):
        return True                     # na dúvida, não sugerir venda
    return any(leg.get(f) in ("legal", "restricted") for f in formatos)


def lots(con) -> dict[str, list[dict]]:
    """Exemplares 'player' por nome de carta. A coleção de colecionador nunca
    entra (regra de domínio: é avaliada, não é jogada)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in con.execute(
        """SELECT cp.id, cp.quantity q, cp.finish, cp.language lang,
                  cp.reserved_deck_id rdid, s.name sub,
                  c.name nm, c.scryfall_id sid, c.set_code, c.set_name,
                  c.released_at rel, COALESCE(c.reserved, 0) rl, c.legalities leg
             FROM copies cp
             JOIN cards c ON c.scryfall_id = cp.scryfall_id
             LEFT JOIN sub_collections s ON s.id = cp.sub_collection_id
            WHERE cp.purpose = 'player'"""):
        d = dict(r)
        d["nm"] = _front(d["nm"])
        d["sub"] = d["sub"] or "(sem balde)"
        d["era_pm"] = bool(d["rel"]) and d["rel"] <= PREMODERN_END
        d["rl"] = bool(d["rl"])
        d["livre"] = d["q"]
        d["substituto"] = {}          # slot -> porque é que não fecha o slot
        out[d["nm"]].append(d)
    return out


def _deck_ids(con, slots) -> dict[str, int | None]:
    """slot -> id na tabela `decks` (para respeitar `copies.reserved_deck_id`)."""
    out = {}
    for s in slots:
        row = (con.execute("SELECT id FROM decks WHERE name = ?", (s["ref"],)).fetchone()
               if s.get("fonte") == "deck" and s.get("ref") else None)
        out[s["slot"]] = row["id"] if row else None
    return out


def _fora_de_vista(lot: dict, s: dict) -> bool:
    """Cópias que este slot nem VÊ — nem para alocar, nem como substituto.

    André (2026-09-07): *"O Premodern não é para olhar para a minha Caixa RL,
    pois o Premodern só vai usar as cartas em Português; na Caixa RL só estão
    cartas RL em inglês."* É diferente do `_porque_nao`: ali a cópia existe e não
    serve (fica como substituto, "decide se abres excepção"); aqui ele já
    decidiu — para uma caixa de Premodern a carta é FALTA, compra-se em PT.
    """
    return s.get("formato") == "premodern" and lot["sub"] == BALDE_RL


def _porque_nao(lot: dict, s: dict, baldes_de_deck: set[str]) -> str | None:
    """Porque é que este exemplar NÃO serve este slot (None = serve)."""
    if s.get("lingua") and lot["lang"] != s["lingua"]:
        return f"não é {s['lingua'].upper()}"
    if s.get("acabamento") == "foil" and lot["finish"] not in FOIL_FINISHES \
            and not lot["rl"]:
        return "não é foil"
    # Tranca do Premodern: PT + impressão da era. Excepção: se a cópia vive no
    # balde de OUTRO slot do loadout, é desse deck (está fisicamente na caixa
    # dele) e não se lhe mexe.
    if (lot["lang"] == "pt" and lot["era_pm"] and s["formato"] != "premodern"
            and lot["sub"] not in baldes_de_deck):
        return "PT da era Premodern (trancada ao Premodern)"
    return None


def _ordem(lot: dict, s: dict) -> tuple:
    """Que exemplar gastar primeiro: o da própria caixa, depois o menos versátil
    (uma nonfoil não serve os decks de foil — gasta-se essa antes da foil)."""
    return (lot["sub"] != s.get("balde"),
            lot["finish"] in FOIL_FINISHES,
            not lot["rl"],
            lot["set_code"] or "", lot["id"])


# ---------------------------------------------------------------------------
# Alocação
# ---------------------------------------------------------------------------
def allocate(con, cfg_slots: list[dict] | None = None) -> dict:
    """Aloca a colecção aos slots do loadout, por ordem de prioridade.

    Devolve {"slots": [...], "conflitos": [...], "pedido": {...}, "lots": {...}}.
    Cada slot traz `have`/`missing`/`subs` (substitutos: existe mas não serve) e
    o custo de fechar. Uma cópia física entra numa caixa e só numa.
    """
    slots = resolve_slots(con, cfg_slots)
    pool = lots(con)
    dids = _deck_ids(con, slots)
    baldes = {s["balde"] for s in slots if s.get("balde")}
    pedido: dict[str, int] = defaultdict(int)
    # carta -> [(slot, quanto pediu, quanto levou)], para o detalhe do conflito
    disputa: dict[str, list[dict]] = defaultdict(list)

    for s in slots:
        did = dids.get(s["slot"])
        foil = s.get("acabamento") == "foil"
        have, missing, subs = [], [], []
        usadas = 0
        precisa = 0
        pediu_slot: dict[str, int] = defaultdict(int)
        levou_slot: dict[str, int] = defaultdict(int)
        for board, nm, need in s["cards"]:
            pedido[nm] += need
            pediu_slot[nm] += need
            basica = nm in BASICS
            precisa += need
            if basica:                     # básicas: assume-se que as tem sempre
                usadas += need
                have.append({"board": board, "nm": nm, "need": need, "got": need,
                             "basica": True, "lotes": []})
                continue
            falta = need
            gastos = []
            cands = sorted(pool.get(nm, []), key=lambda l: _ordem(l, s))
            for lot in cands:
                if falta <= 0:
                    break
                if lot["livre"] <= 0:
                    continue
                if lot["rdid"] is not None and lot["rdid"] != did:
                    continue              # dedicada a outro deck (regra de domínio)
                if _fora_de_vista(lot, s) or _porque_nao(lot, s, baldes):
                    continue
                take = min(lot["livre"], falta)
                lot["livre"] -= take
                falta -= take
                gastos.append({"id": lot["id"], "q": take, "sub": lot["sub"],
                               "finish": lot["finish"], "lang": lot["lang"],
                               "set_code": lot["set_code"], "sid": lot["sid"]})
            got = need - falta
            usadas += got
            levou_slot[nm] += got
            linha = {"board": board, "nm": nm, "need": need, "got": got,
                     "basica": False, "lotes": gastos}
            if falta:
                # Existe mas não serve: é a diferença entre "não tenho" e "tenho
                # a carta errada". São coisas diferentes na hora de comprar.
                alt = defaultdict(int)
                for lot in cands:
                    if lot["livre"] <= 0 or (lot["rdid"] is not None and lot["rdid"] != did):
                        continue
                    if _fora_de_vista(lot, s):
                        continue      # a Caixa RL não existe para o Premodern
                    razao = _porque_nao(lot, s, baldes)
                    if razao:
                        alt[razao] += lot["livre"]
                        # Marca o exemplar como SUBSTITUTO: serve este slot, só não
                        # na língua/acabamento que ele pediu. Sem esta marca a
                        # venda mandava-o embora. O caso que obrigou a inventá-la
                        # foram as 4 Opalescence EN da Caixa RL — que desde
                        # 2026-09-07 já nem chegam aqui (o Premodern não olha para
                        # a Caixa RL, ver `_fora_de_vista`, e por decisão dele
                        # essas vão mesmo para a venda a confirmar). A marca
                        # continua a valer para as nonfoil dos slots de foil e
                        # para as EN que vivem nos baldes de colecção.
                        lot["substituto"][s["nome"]] = razao
                unit, pfin = card_price(con, nm, "foil" if foil else "nonfoil")
                linha.update(missing=falta, unit=unit, price_finish=pfin,
                             cost=round((unit or 0) * falta, 2),
                             alt={k: v for k, v in alt.items()})
                missing.append(linha)
                if alt:
                    subs.append(linha)
            else:
                have.append(linha)
        for nm, q in pediu_slot.items():
            disputa[nm].append({"slot": s["nome"], "prioridade": s["prioridade"],
                                "pediu": q, "levou": levou_slot.get(nm, 0)})
        s["have"] = sorted(have, key=lambda r: (r["board"] != "main", r["nm"]))
        s["missing"] = sorted(missing, key=lambda r: -(r["cost"] or 0))
        s["subs"] = subs
        s["precisa"] = precisa
        s["tenho"] = usadas
        s["pct"] = round(100 * usadas / precisa) if precisa else 0
        s["custo"] = round(sum(m["cost"] or 0 for m in missing), 2)
        s["faltam"] = sum(m["missing"] for m in missing)

    # CONFLITO = duas ou mais caixas querem a mesma carta e não há cópias para
    # todas. Uma caixa sozinha a que falta uma carta NÃO é conflito — é uma falta,
    # e resolve-se a comprar. Aqui a compra não é a única saída: pode ser mais
    # barato tirar o deck de menor prioridade do loadout.
    conflitos = []
    for nm, quem in disputa.items():
        if len(quem) < 2 or nm in BASICS:
            continue
        if all(q["levou"] >= q["pediu"] for q in quem):
            continue                     # chegou para todos: não há disputa
        if not sum(l["q"] for l in pool.get(nm, [])):
            continue                     # não tem nenhuma: é falta, não disputa
        conflitos.append({
            "nm": nm, "pedido": pedido[nm],
            "tenho": sum(l["q"] for l in pool.get(nm, [])),
            "por_slot": sorted(quem, key=lambda q: q["prioridade"]),
            "ficam_com": sorted({q["slot"] for q in quem if q["levou"]}),
            "ficam_sem": sorted({q["slot"] for q in quem if q["levou"] < q["pediu"]}),
        })
    conflitos.sort(key=lambda c: (-(c["pedido"] - c["tenho"]), c["nm"]))
    return {"slots": slots, "conflitos": conflitos, "pedido": dict(pedido),
            "pool": pool}


# ---------------------------------------------------------------------------
# Venda
# ---------------------------------------------------------------------------
def caixas_de_deck(slots) -> set[str]:
    """Baldes que são a CAIXA de um deck, e não colecção.

    São os que o `colecao_config.json -> regras_colecao` já nomeia — o CLAUDE.md
    diz-lhes "coleção própria + lista vigiada" (Blue Farm, Cloud, Cloud cEDH,
    Pauper Affinity) — mais o balde de qualquer slot de Commander do loadout, que
    é uma caixa de deck por definição mesmo que ainda não tenha regra escrita.

    Tudo o resto (SPML, Premodern (geral), Caixa Reserved List) é COLECÇÃO e
    partilha um único limite de playset. Contar 4 por balde deixava passar o
    dobro: 4 Intuition no Premodern mais 4 na Caixa RL são 8 da mesma carta.
    """
    caixas = set(_retencao())
    for s in slots:
        if s.get("balde") and s.get("formato") in COMMANDER_FORMATS:
            caixas.add(s["balde"])
    return caixas


def sell_list(con, res: dict) -> dict:
    """O que sobra depois de alocar e de guardar o backup permitido.

    A regra é por COLECÇÃO, como o CLAUDE.md diz ("cada pasta é uma coleção com a
    sua regra"), mas o limite de playset é sobre a colecção INTEIRA, não por
    balde: quatro Intuition no balde Premodern mais quatro na Caixa Reserved List
    são oito cópias da mesma carta, e o playset são 4 — contar 4 por balde deixava
    passar o dobro.

      * caixas de deck de Commander -> 1 por deck que a usa (singleton);
      * o resto da colecção          -> 4 por carta (playset), a somar todos os
                                        baldes de colecção;
      * básicas                      -> nunca;
      * não legal em formato nenhum  -> vender tudo o que não foi alocado.

    Três saídas separadas, porque têm riscos diferentes e misturá-las dava um
    total que não se pode usar:
      `venda`     — o excedente normal;
      `venda_rl`  — Reserved List: cartas que não se voltam a imprimir. É a maior
                    fatia do valor e a decisão menos reversível — vai à parte
                    para ser confirmada uma a uma;
      `guardar`   — SUBSTITUTOS: cópias que servem um deck do loadout e só não
                    fecham o slot por causa da língua ou do acabamento (as
                    nonfoil dos slots de foil, as EN nos baldes de colecção). A
                    Caixa RL já não entra aqui pelo lado do Premodern: desde
                    2026-09-07 essas caixas não olham para ela, e o que lá
                    sobrar do playset vai para `venda_rl` a confirmar;
      `retidos`   — baldes com `reter_extras_meses`. A regra dos 6 meses precisa
                    de uma data de última utilização que ainda não existe (ver
                    CLAUDE.md), por isso estes extras GUARDAM-SE e dizem-no, em
                    vez de entrarem na venda como se a regra já corresse.
    """
    pool = res["pool"]
    retidos_baldes = _retencao()
    caixas = caixas_de_deck(res["slots"])
    # Quantas cópias cada caixa de Commander pede de cada carta.
    cmd_need: dict[tuple[str, str], int] = defaultdict(int)
    for s in res["slots"]:
        if s["formato"] not in COMMANDER_FORMATS or not s.get("balde"):
            continue
        for _b, nm, q in s["cards"]:
            cmd_need[(s["balde"], nm)] = max(cmd_need[(s["balde"], nm)], q)

    venda, venda_rl, retidos, guardar = [], [], [], []
    for nm, ls in pool.items():
        if nm in BASICS:
            continue
        legal = _legal_em(ls[0]["leg"], REAL_FORMATS)
        # Grupos: cada caixa de deck é o seu grupo; toda a colecção é UM grupo.
        grupos: dict[str, list[dict]] = defaultdict(list)
        for lot in ls:
            grupos[lot["sub"] if lot["sub"] in caixas else ""].append(lot)
        for grupo, lotes in grupos.items():
            if sum(l["livre"] for l in lotes) <= 0:
                continue
            alocado = sum(l["q"] - l["livre"] for l in lotes)
            if grupo and (grupo, nm) in cmd_need:
                limite = max(alocado, cmd_need[(grupo, nm)])
                razao = "excedente (Commander: 1 por deck)"
            elif legal:
                limite = max(alocado, CONSTRUCTED_LIMIT)
                razao = f"excedente (mais de {CONSTRUCTED_LIMIT})"
            else:
                limite = alocado
                razao = "não joga em formato nenhum"
            resto = sum(l["q"] for l in lotes) - limite
            if resto <= 0:
                continue
            # Vender primeiro o que menos falta faz: os substitutos por último
            # (servem um deck), depois as que não são Reserved List, depois as
            # nonfoil, e as PT no fim — são as que servem o Premodern, o único
            # formato onde ele exige a língua.
            for lot in sorted(lotes, key=lambda l: (bool(l["substituto"]), l["rl"],
                                                    l["finish"] in FOIL_FINISHES,
                                                    l["lang"] == "pt", l["id"])):
                if resto <= 0:
                    break
                take = min(lot["livre"], resto)
                if take <= 0:
                    continue
                resto -= take
                unit, pfin = card_price(con, nm, lot["finish"])
                linha = {"nm": nm, "sub": lot["sub"], "q": take,
                         "finish": lot["finish"], "lang": lot["lang"],
                         "set_code": lot["set_code"], "set_name": lot["set_name"],
                         "sid": lot["sid"], "rl": lot["rl"], "unit": unit,
                         "price_finish": pfin,
                         "total": round((unit or 0) * take, 2), "reason": razao,
                         "reter": retidos_baldes.get(lot["sub"]),
                         "substituto": dict(lot["substituto"])}
                if linha["substituto"]:
                    quem = ", ".join(sorted(linha["substituto"]))
                    linha["reason"] = f"serve {quem} ({'; '.join(sorted(set(linha['substituto'].values())))})"
                    guardar.append(linha)
                elif linha["reter"]:
                    retidos.append(linha)
                else:
                    (venda_rl if lot["rl"] else venda).append(linha)

    def _fecha(rows):
        # Junta lotes iguais: dois lotes da mesma impressão são a mesma linha na
        # lista de venda, e apareciam duas vezes só porque entraram em alturas
        # diferentes.
        junto: dict[tuple, dict] = {}
        for r in rows:
            k = (r["nm"], r["sub"], r["finish"], r["lang"], r["set_code"], r["reason"])
            if k in junto:
                junto[k]["q"] += r["q"]
                junto[k]["total"] = round((junto[k]["unit"] or 0) * junto[k]["q"], 2)
            else:
                junto[k] = dict(r)
        out = sorted(junto.values(), key=lambda r: (-(r["total"] or 0), r["nm"]))
        return {"linhas": out, "total": round(sum(r["total"] or 0 for r in out), 2),
                "copias": sum(r["q"] for r in out)}

    v, vrl, ret, gd = (_fecha(venda), _fecha(venda_rl), _fecha(retidos),
                       _fecha(guardar))
    return {"venda": v["linhas"], "venda_rl": vrl["linhas"],
            "retidos": ret["linhas"], "guardar": gd["linhas"],
            "total": v["total"], "copias": v["copias"],
            "total_rl": vrl["total"], "copias_rl": vrl["copias"],
            "total_retido": ret["total"], "copias_retidas": ret["copias"],
            "total_guardar": gd["total"], "copias_guardar": gd["copias"]}


def report(con, cfg_slots: list[dict] | None = None) -> dict:
    """Alocação + venda, de uma vez. É o que as páginas e o CLI consomem."""
    res = allocate(con, cfg_slots)
    res.update(sell_list(con, res))
    res["custo_total"] = round(sum(s["custo"] for s in res["slots"]), 2)
    return res


# ---------------------------------------------------------------------------
# Ranking de arquétipos por material (para escolher os slots por confirmar)
# ---------------------------------------------------------------------------
def foil_report(con: sqlite3.Connection, fmt: str, top: int = 5,
                min_lists: int = 8) -> list[dict]:
    """Arquétipos de um formato ordenados pela % que o André JÁ TEM em foil.

    Serve os slots por confirmar (Standard, Pioneer, Legacy): *"faz uma pesquisa
    de decks e diz-me quais os decks que eu mais tenho cartas para não ser tão
    difícil montar"*. A lista de cada arquétipo é a lista padrão de sempre
    (`stock.coverage_of_archetype` usa o mesmo `stock_list`), mas a posse conta só
    exemplares que servem a regra do foil — senão o ranking dizia que ele tem
    cartas que não pode pôr no deck.
    """
    pool = lots(con)

    def tenho(nm: str) -> tuple[int, int]:
        """(cópias que servem em foil, cópias em qualquer acabamento)."""
        ls = pool.get(nm, [])
        return (sum(l["q"] for l in ls
                    if l["finish"] in FOIL_FINISHES or l["rl"]),
                sum(l["q"] for l in ls))

    rows = con.execute(
        """SELECT a.id, a.label, COUNT(d.id) n FROM archetypes a
             JOIN decklists d ON d.archetype_id = a.id
            WHERE a.format = ? GROUP BY a.id HAVING n >= ?
            ORDER BY n DESC LIMIT 40""", (fmt, min_lists)).fetchall()
    out = []
    vistos: dict[tuple, dict] = {}
    for r in rows:
        try:
            sl = stock.stock_list(con, r["id"])
        except LookupError:
            continue
        cards = [(b, c["card_name"], c["quantity"])
                 for b in ("main", "side") for c in sl.get(b, [])]
        if not cards:
            continue
        # O clustering parte o mesmo deck em vários `archetypes` (rótulos
        # diferentes, lista igual). Duas entradas com a MESMA lista padrão são o
        # mesmo baralho: junta-se o nº de listas em vez de aparecer duas vezes.
        chave = tuple(sorted(cards))
        if chave in vistos:
            vistos[chave]["n_lists"] += r["n"]
            vistos[chave]["ids"].append(r["id"])
            continue
        need = have_f = have_a = 0
        custo = 0.0
        faltam = []
        for _b, nm, q in cards:
            if nm in BASICS:
                continue
            f, a = tenho(nm)
            need += q
            have_f += min(q, f)
            have_a += min(q, a)
            if f < q:
                unit, pfin = card_price(con, nm, "foil")
                custo += (unit or 0) * (q - f)
                faltam.append({"nm": nm, "falta": q - f, "tenho_nonfoil": min(q, a) - min(q, f),
                               "unit": unit, "price_finish": pfin,
                               "cost": round((unit or 0) * (q - f), 2)})
        if not need:
            continue
        linha = {"archetype_id": r["id"], "ids": [r["id"]], "label": r["label"],
                 "n_lists": r["n"], "need": need, "have_foil": have_f,
                 "have_any": have_a, "pct_foil": round(100 * have_f / need),
                 "pct_any": round(100 * have_a / need), "custo": round(custo, 2),
                 "faltam": sorted(faltam, key=lambda x: -(x["cost"] or 0))}
        vistos[chave] = linha
        out.append(linha)
    return sorted(out, key=lambda x: (-x["pct_foil"], x["custo"]))[:top]
