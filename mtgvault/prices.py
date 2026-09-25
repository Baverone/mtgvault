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

from . import precos

CT_BASE = "https://api.cardtrader.com/api/v2"
CM_EXPORTS = "https://www.cardmarket.com/en/Magic/Data/File-Exports"
# O price guide de Magic (idCategory 1) está PÚBLICO no S3 do Cardmarket, sem
# sessão — validado a 2026-09-18: 26 MB, 127 216 produtos, `createdAt` de hoje
# às 02:49, e o `load_cardmarket_file` lê-o tal e qual (JSON com `priceGuides`,
# `idProduct`, low/trend/avg30 e as variantes -foil). É a mesma família de
# ficheiros da página de exports; a página só acrescenta o login.
CM_PRICEGUIDE_PUBLICO = ("https://downloads.s3.cardmarket.com/productCatalog/"
                         "priceGuide/price_guide_1.json")


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
            batch.append((sid, "cardmarket", day, finish, low, trend, avg30,
                          None, "EUR", precos.RECEITA_CM_GUIDE))
        if len(batch) >= 5000:
            n += _flush(con, batch)
    n += _flush(con, batch)
    return n


def _flush(con, batch) -> int:
    return write_prices(con, batch)


# ---------------------------------------------------------------------------
# Preços via Scryfall (grátis, sem credenciais)
# ---------------------------------------------------------------------------
def load_scryfall_prices(con: sqlite3.Connection, bulk_path, day: str | None = None,
                         only_interest: bool = True) -> int:
    """Carrega preços a partir do bulk da Scryfall (o mesmo ficheiro do sync-cards).

    O campo `prices.eur`/`prices.eur_foil` de cada impressão É o preço do
    Cardmarket (a Scryfall vai lá buscá-lo), por isso guarda-se com source
    'cardmarket' — assim o `value`, o `movers` e as cobranças funcionam sem
    mudar nada. É um único valor por impressão (não tem low/trend/avg30
    separados), por isso trend=low=eur. Gratuito e sem cookie/token — a
    alternativa ao price guide oficial quando não há sessão.
    """
    import gzip

    day = day or date.today().isoformat()
    interest = cards_of_interest(con) if only_interest else None
    opener = gzip.open if str(bulk_path).endswith(".gz") else open
    batch, n = [], 0
    with opener(bulk_path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = c.get("id")
            if interest is not None and sid not in interest:
                continue
            pr = c.get("prices") or {}
            for finish, key in (("nonfoil", "eur"), ("foil", "eur_foil")):
                v = pr.get(key)
                if v in (None, ""):
                    continue
                try:
                    eur = float(v)
                except (TypeError, ValueError):
                    continue
                # `unico`: um valor só, copiado para as duas colunas — os três
                # modos de preço dão aqui exactamente o mesmo número.
                batch.append((sid, "cardmarket", day, finish, eur, eur, None,
                              None, "EUR", precos.RECEITA_UNICA))
            if len(batch) >= 5000:
                n += write_prices(con, batch)
    n += write_prices(con, batch)
    return n


# ---------------------------------------------------------------------------
# Escrita de preços: só guardamos MUDANÇAS
# ---------------------------------------------------------------------------
def cards_of_interest(con: sqlite3.Connection) -> set[str]:
    """scryfall_ids cujo preço vale a pena seguir.

    Seguir o mercado inteiro todos os dias seria insustentável — centenas de
    milhares de impressões vezes 365 dias. Só interessam:
      1. o que já tenho na coleção
      2. todas as impressões das cartas que preciso (decks, vigiados, cores)
      3. a Reserved List inteira (impressões em papel) — a página reservedlist
         mostra o valor e a evolução de cada edição, tenha-a eu ou não
    """
    ids = {r["scryfall_id"] for r in
           con.execute("SELECT DISTINCT scryfall_id FROM copies")}
    ids |= {r["scryfall_id"] for r in con.execute(
        "SELECT scryfall_id FROM cards WHERE reserved = 1 AND digital = 0")}

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

    rows = [(scryfall_id, source, date, finish, low, trend, avg30, available, cur
             [, receita])]

    A RECEITA é o 10.º elemento e é opcional (quem não a manda fica com
    `unico`, que é o que os dois carregadores antigos escrevem: um valor só,
    copiado para as duas colunas). **Ela entra na comparação**: os números
    podem ser os mesmos e quererem dizer outra coisa, e uma linha de histórico
    sem a receita nova deixava a regra da Reserved List a comparar receitas
    diferentes sem dar por isso — ver `mtgvault.precos`.
    """
    if not rows:
        return 0
    # `rows` é o batch do chamador e é ELE que se esvazia no fim (`_flush`
    # conta com isso) — por isso a normalização vai para uma lista à parte.
    linhas = [tuple(r) + (precos.RECEITA_UNICA,) if len(r) < 10 else tuple(r)
              for r in rows]
    latest = {
        (r["scryfall_id"], r["source"], r["finish"]):
            (r["low"], r["trend"], r["avg30"],
             r["receita"] or precos.RECEITA_UNICA)
        for r in con.execute("SELECT * FROM price_latest")
    }
    changed = []
    for row in linhas:
        sid, src, day, fin, low, trend, avg30 = row[:7]
        if latest.get((sid, src, fin)) != (low, trend, avg30, row[9]):
            changed.append(row)
    if changed:
        con.executemany(
            """INSERT OR REPLACE INTO price_history
               (scryfall_id, source, date, finish, low, trend, avg30, available,
                currency, receita) VALUES (?,?,?,?,?,?,?,?,?,?)""", changed)
    con.executemany(
        """INSERT OR REPLACE INTO price_latest
           (scryfall_id, source, finish, date, low, trend, avg30, available,
            currency, receita)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [(r[0], r[1], r[3], r[2], r[4], r[5], r[6], r[7], r[8], r[9])
         for r in linhas])
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
    """OS DOIS VALORES por blueprint: best value e market value (2026-09-25).

    Até esta data guardava-se **um só** — `min(ofertas)` copiado para o `low` e
    para o `trend` —, e por isso os três modos de preço do André davam todos o
    mesmo número. Agora:

        low   = a oferta mais barata das utilizáveis   (**best value**)
        trend = a MEDIANA das utilizáveis              (**market value**)

    A API do CardTrader não publica campo nenhum de "market value" (sondada a
    2026-09-25: os blueprints não trazem preço e cada oferta traz só o seu
    `price_cents`) — por isso calcula-se, e a mediana é o que resiste à cauda
    de cópias estrangeiras e maltratadas. **E as ofertas filtram-se**, com o
    mesmo crivo do riftvault (`precos.oferta_utilizavel`): sem ele o preço de
    um Mountain de Odyssey era os 0,28 € de uma cópia italiana «Poor» com o
    verso escrito à mão.

    Devolve o nº de linhas gravadas em `price_history`.
    """
    day = date.today().isoformat()
    aceites = precos.linguas()
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
            uteis = [o for o in offers if precos.oferta_utilizavel(o, aceites)]
            for finish, want_foil in (("nonfoil", False), ("foil", True)):
                sel = [
                    o for o in uteis
                    if bool((o.get("properties_hash") or {}).get("mtg_foil")) == want_foil
                ]
                if not sel:
                    continue
                v = precos.dois_valores(sel)
                batch.append((sid, "cardtrader", day, finish, v["low"], v["trend"],
                              None, v["copias"], "EUR", precos.RECEITA_CT_OFERTAS))
        n += _flush(con, batch)
    return n


def priceguide_publico_ligado() -> bool:
    """`CARDMARKET_PRICEGUIDE_PUBLICO=1` liga o price guide público (ver abaixo)."""
    return os.environ.get("CARDMARKET_PRICEGUIDE_PUBLICO", "").strip().lower() in (
        "1", "true", "sim", "yes")


def download_cardmarket_priceguide(dest: Path | None = None,
                                   _get=None) -> Path | None:
    """Descarrega o price guide: com cookie de sessão, ou o público (opt-in).

    ISTO É A PARTE FRÁGIL DE TODO O SISTEMA. A página de exports do Cardmarket
    exige sessão iniciada, e num runner sem browser a única forma é guardar o
    cookie num secret. Quando a sessão expirar — e vai expirar — este passo
    falha e é preciso ir buscar um cookie novo.

    Falha em silêncio de propósito: devolve None e o daily.py regista o erro
    sem derrubar o resto do trabalho. É preferível ficar um dia sem preços
    novos do que perder a recolha de decklists.

    Variáveis: CARDMARKET_COOKIE e CARDMARKET_PRICEGUIDE_URL (o link exato do
    ficheiro, copiado da página de exports).

    **O PÚBLICO É OPT-IN, E NÃO POR ACASO (2026-09-18).** O ficheiro em
    `CM_PRICEGUIDE_PUBLICO` não precisa de cookie e o parser lê-o à primeira —
    mas ligá-lo MUDA OS NÚMEROS do vault, e não pouco. Medido numa cópia da base
    desse dia, por cima dos preços da Scryfall (que são o `trend` do Cardmarket:
    78 % iguais ao cêntimo, mediana |Δ| 0 %): o guide traz **8 202 impressões**
    que a Scryfall não cota, e como o `loadout.card_price` é o MÍNIMO do `trend`
    entre as impressões do mesmo nome, a lista de venda passa de 1 499,70 € para
    **665,60 €** (as mesmas 246 cópias), o *"fechar tudo"* de 7 057,57 € para
    **5 164,65 €**, e a regra dos 5 % da Reserved List compara o mínimo de hoje
    (com as impressões novas) com o de há 90 dias (sem elas) e passa **22
    cópias / 3 583 €** de *"a segurar"* para *"vender"* — sem que o mercado
    tenha mexido. É a armadilha das *"duas contas"* do `card_price_em`, desta
    vez entre fontes. Ligar isto é uma decisão do André, e no dia em que ligar
    a janela da RL tem de recomeçar (o histórico de antes não é comparável).
    `_get` é só para os testes trocarem o pedido HTTP por um ficheiro.
    """
    get = _get or requests.get
    url = os.environ.get("CARDMARKET_PRICEGUIDE_URL")
    cookie = os.environ.get("CARDMARKET_COOKIE")
    headers = {"User-Agent": "Mozilla/5.0 mtgvault/0.1"}
    if url and cookie:
        headers["Cookie"] = cookie
    elif priceguide_publico_ligado():
        url = CM_PRICEGUIDE_PUBLICO
    else:
        return None
    dest = dest or Path("priceguide.json")
    r = get(url, headers=headers, timeout=120)
    r.raise_for_status()
    body = r.content
    if b"<html" in body[:200].lower():
        raise RuntimeError(
            "O Cardmarket devolveu HTML em vez do ficheiro — a sessão expirou. "
            "Gera um cookie novo e atualiza o secret CARDMARKET_COOKIE."
        )
    dest.write_bytes(body)
    return dest
