"""Preços diários: Cardmarket (ficheiro oficial) e CardTrader (API v2).

CARDMARKET
    Não se raspa o site — bloqueia e é contra os termos. O Cardmarket publica
    um price guide e um catálogo de produtos para download, atualizados uma vez
    por dia, em https://www.cardmarket.com/en/Magic/Data/File-Exports
    A ponte para nós é o `cardmarket_id` (idProduct) que a Scryfall já traz.

    O ficheiro é servido como JSON ou CSV consoante a opção escolhida; o parser
    abaixo aceita ambos. Se o formato mudar, é o único sítio a mexer.

CARDTRADER
    API REST oficial, autenticada com Bearer token obtido nas definições do
    perfil. Limite de 200 pedidos por 10 segundos.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import time
from datetime import date
from pathlib import Path

import requests

CT_BASE = "https://api.cardtrader.com/api/v2"
CM_EXPORTS = "https://www.cardmarket.com/en/Magic/Data/File-Exports"


# ---------------------------------------------------------------------------
# Cardmarket
# ---------------------------------------------------------------------------
def _cm_rows(path: Path):
    """Normaliza o price guide para dicionários, venha em JSON ou CSV."""
    text = path.read_text(encoding="utf-8-sig", errors="replace").lstrip()
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("priceGuides") or data.get("products") or []
        yield from data
    else:
        yield from csv.DictReader(text.splitlines())


def _f(v):
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "", "null") else None
    except ValueError:
        return None


def load_cardmarket_file(con: sqlite3.Connection, path: str | Path,
                         day: str | None = None,
                         only_interest: bool = True) -> int:
    """Carrega um price guide já descarregado. Devolve nº de linhas gravadas."""
    day = day or date.today().isoformat()
    interest = cards_of_interest(con) if only_interest else None
    known = {
        r["cardmarket_id"]: r["scryfall_id"]
        for r in con.execute(
            "SELECT cardmarket_id, scryfall_id FROM cards WHERE cardmarket_id IS NOT NULL"
        )
        if interest is None or r["scryfall_id"] in interest
    }
    batch, n = [], 0
    for row in _cm_rows(Path(path)):
        try:
            pid = int(row.get("idProduct") or row.get("Product ID") or 0)
        except (TypeError, ValueError):
            continue
        sid = known.get(pid)
        if not sid:
            continue
        for finish, keys in (
            ("nonfoil", ("low", "trend", "avg30")),
            ("foil", ("low-foil", "trend-foil", "avg30-foil")),
        ):
            low, trend, avg30 = (_f(row.get(k)) for k in keys)
            if trend is None and low is None:
                continue
            batch.append((sid, "cardmarket", day, finish, low, trend, avg30, None, "EUR"))
        if len(batch) >= 5000:
            n += _flush(con, batch)
    n += _flush(con, batch)
    return n


def _flush(con, batch) -> int:
    return write_prices(con, batch)

# ---------------------------------------------------------------------------
# Escrita de preços: só guardamos MUDANÇAS
# ---------------------------------------------------------------------------
def cards_of_interest(con: sqlite3.Connection) -> set[str]:
    """scryfall_ids cujo preço vale a pena seguir.

    Seguir o mercado inteiro todos os dias seria insustentável — centenas de
    milhares de impressões vezes 365 dias. Só interessam:
      1. o que já tenho na coleção
      2. todas as impressões das cartas que preciso (decks, vigiados, cores)
    """
    ids = {r["scryfall_id"] for r in
           con.execute("SELECT DISTINCT scryfall_id FROM copies")}

    names: set[str] = {r["card_name"] for r in
                       con.execute("SELECT DISTINCT card_name FROM deck_cards")}
    names |= {r["card_name"] for r in con.execute(
        "SELECT DISTINCT card_name FROM card_roles WHERE role IN ('core','flex')")}
    for r in con.execute("SELECT cards FROM watched_snapshots"):
        for _, name, _q in json.loads(r["cards"]):
            names.add(name)

    if names:
        marks = ",".join("?" * len(names))
        ids |= {r["scryfall_id"] for r in con.execute(
            f"SELECT scryfall_id FROM cards WHERE digital = 0 AND name IN ({marks})",
            tuple(names))}
    return ids


def write_prices(con: sqlite3.Connection, rows: list[tuple]) -> int:
    """Grava preços. Uma linha em price_history só se o valor MUDOU.

    A maior parte das cartas não mexe de um dia para o outro; guardar tudo
    todos os dias multiplicaria o tamanho da base de dados por nada. O
    price_latest fica sempre atualizado, por isso não se perde informação:
    "não há linha nova" quer dizer "o preço manteve-se".

    rows = [(scryfall_id, source, date, finish, low, trend, avg30, available, cur)]
    """
    if not rows:
        return 0
    latest = {
        (r["scryfall_id"], r["source"], r["finish"]): (r["low"], r["trend"], r["avg30"])
        for r in con.execute("SELECT * FROM price_latest")
    }
    changed = []
    for row in rows:
        sid, src, day, fin, low, trend, avg30 = row[:7]
        if latest.get((sid, src, fin)) != (low, trend, avg30):
            changed.append(row)
    if changed:
        con.executemany(
            """INSERT OR REPLACE INTO price_history
               (scryfall_id, source, date, finish, low, trend, avg30, available,
                currency) VALUES (?,?,?,?,?,?,?,?,?)""", changed)
    con.executemany(
        """INSERT OR REPLACE INTO price_latest
           (scryfall_id, source, finish, date, low, trend, avg30, available, currency)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [(r[0], r[1], r[3], r[2], r[4], r[5], r[6], r[7], r[8]) for r in rows])
    con.commit()
    rows.clear()
    return len(changed)



# ---------------------------------------------------------------------------
# CardTrader
# ---------------------------------------------------------------------------
class CardTrader:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("CARDTRADER_TOKEN")
        if not self.token:
            raise RuntimeError("Falta CARDTRADER_TOKEN no ambiente")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {self.token}"})
        self._calls: list[float] = []

    def get(self, path: str, **params):
        # 200 pedidos / 10 s
        now = time.time()
        self._calls = [t for t in self._calls if now - t < 10]
        if len(self._calls) >= 190:
            time.sleep(10 - (now - self._calls[0]))
        r = self.s.get(f"{CT_BASE}{path}", params=params, timeout=30)
        self._calls.append(time.time())
        r.raise_for_status()
        return r.json()

    def expansions(self):
        return self.get("/expansions")

    def blueprints(self, expansion_id: int):
        return self.get("/blueprints/export", expansion_id=expansion_id)

    def marketplace(self, expansion_id: int):
        """Ofertas por blueprint. Preços vêm em cêntimos."""
        return self.get("/marketplace/products", expansion_id=expansion_id)


def sync_cardtrader_map(con: sqlite3.Connection, ct: CardTrader,
                        set_codes: list[str] | None = None) -> int:
    """Constrói o mapa scryfall_id -> blueprint_id.

    Os blueprints do CardTrader trazem `scryfall_id` quando disponível; quando
    não trazem, cai para correspondência por (nome, código de edição).
    """
    exps = {e["code"].lower(): e["id"] for e in ct.expansions() if e.get("code")}
    codes = [c.lower() for c in (set_codes or exps)]
    n = 0
    for code in codes:
        eid = exps.get(code)
        if not eid:
            continue
        by_name = {
            r["name"].lower(): r["scryfall_id"]
            for r in con.execute(
                "SELECT name, scryfall_id FROM cards WHERE lower(set_code) = ?", (code,)
            )
        }
        rows = []
        for bp in ct.blueprints(eid):
            sid = bp.get("scryfall_id") or by_name.get((bp.get("name") or "").lower())
            if sid:
                rows.append((sid, bp["id"]))
        if rows:
            con.executemany(
                "INSERT OR REPLACE INTO cardtrader_map (scryfall_id, blueprint_id, "
                "checked_at) VALUES (?,?,date('now'))",
                rows,
            )
            con.commit()
            n += len(rows)
    return n


def fetch_cardtrader_prices(con: sqlite3.Connection, ct: CardTrader,
                            set_codes: list[str]) -> int:
    """Preço mais baixo por blueprint, para as edições indicadas."""
    day = date.today().isoformat()
    exps = {e["code"].lower(): e["id"] for e in ct.expansions() if e.get("code")}
    bp_to_sid = {
        r["blueprint_id"]: r["scryfall_id"]
        for r in con.execute("SELECT blueprint_id, scryfall_id FROM cardtrader_map")
    }
    n = 0
    for code in set_codes:
        eid = exps.get(code.lower())
        if not eid:
            continue
        data = ct.marketplace(eid)
        batch = []
        for bp_id, offers in data.items():
            sid = bp_to_sid.get(int(bp_id))
            if not sid or not offers:
                continue
            for finish, want_foil in (("nonfoil", False), ("foil", True)):
                sel = [
                    o for o in offers
                    if bool((o.get("properties_hash") or {}).get("mtg_foil")) == want_foil
                ]
                if not sel:
                    continue
                prices = [o["price"]["cents"] / 100 for o in sel if o.get("price")]
                if not prices:
                    continue
                batch.append((sid, "cardtrader", day, finish, min(prices), min(prices),
                              None, sum(o.get("quantity", 0) for o in sel), "EUR"))
        n += _flush(con, batch)
    return n


def download_cardmarket_priceguide(dest: Path | None = None) -> Path | None:
    """Descarrega o price guide usando um cookie de sessão.

    ISTO É A PARTE FRÁGIL DE TODO O SISTEMA. A página de exports do Cardmarket
    exige sessão iniciada, e num runner sem browser a única forma é guardar o
    cookie num secret. Quando a sessão expirar — e vai expirar — este passo
    falha e é preciso ir buscar um cookie novo.

    Falha em silêncio de propósito: devolve None e o daily.py regista o erro
    sem derrubar o resto do trabalho. É preferível ficar um dia sem preços
    novos do que perder a recolha de decklists.

    Variáveis: CARDMARKET_COOKIE e CARDMARKET_PRICEGUIDE_URL (o link exato do
    ficheiro, copiado da página de exports).
    """
    url = os.environ.get("CARDMARKET_PRICEGUIDE_URL")
    cookie = os.environ.get("CARDMARKET_COOKIE")
    if not url or not cookie:
        return None
    dest = dest or Path("priceguide.json")
    r = requests.get(
        url,
        headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 mtgvault/0.1"},
        timeout=120,
    )
    r.raise_for_status()
    body = r.content
    if b"<html" in body[:200].lower():
        raise RuntimeError(
            "O Cardmarket devolveu HTML em vez do ficheiro — a sessão expirou. "
            "Gera um cookie novo e atualiza o secret CARDMARKET_COOKIE."
        )
    dest.write_bytes(body)
    return dest
