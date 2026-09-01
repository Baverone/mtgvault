"""Índice de torneios do mtgdecks.net.

O mtgdecks agrega muitas fontes (mtgmelee, hareruya, mtgtop8, SCG, tcgplayer…) e
dá, por torneio, o **nº de jogadores** (peso), a **data** e o **nome** — o que o
mtgtop8 nem sempre tem. Funciona com `requests` desde que se use um User-Agent de
browser (a deteção de bots do mtgdecks reage ao UA, não ao IP).

LIMITE: as CARTAS das listas são anti-scraped (renderizadas por JS / base64, e os
endpoints de export dão 403). Por isso isto serve para DESCOBRIR e PESAR eventos;
as cartas continuam a vir do mtgtop8 (export .dec limpo). NÃO parsear as listas
daqui — não vale a pena lutar com o anti-scraping.
"""
from __future__ import annotations

import re
from datetime import date

import requests

BASE = "https://mtgdecks.net"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}
FMT = {"standard": "Standard", "pioneer": "Pioneer", "modern": "Modern",
       "legacy": "Legacy", "pauper": "Pauper", "vintage": "Vintage", "pioneer ": "Pioneer"}
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _iso(daymon: str, today: date) -> str | None:
    """'30-Aug' -> ISO, inferindo o ano (o mais recente que não fica no futuro)."""
    m = re.match(r"(\d{1,2})-(\w{3})", daymon)
    if not m:
        return None
    d, mon = int(m.group(1)), _MONTHS.get(m.group(2).title())
    if not mon:
        return None
    y = today.year
    try:
        iso = date(y, mon, d)
    except ValueError:
        return None
    if iso > today:               # ainda não aconteceu este ano -> foi no ano passado
        iso = date(y - 1, mon, d)
    return iso.isoformat()


def tournaments(fmt: str, today: date | None = None) -> list[dict]:
    """[{date, players, name, url}] dos torneios recentes do formato (1ª página).

    Ordenados como no site (mais recentes primeiro). `players` é None quando o site
    mostra '?'. Levanta requests.RequestException se a rede falhar."""
    f = FMT[fmt.lower()]
    today = today or date.today()
    html = requests.get(f"{BASE}/{f}/tournaments", headers=UA, timeout=25).text
    out, seen = [], set()
    # Cada torneio é uma <tr> com <strong>data</strong>, "N Players" e um link
    # "/<Fmt>/<slug>-tournament-<ID>". Ícone mtgo = online, senão presencial.
    for row in re.split(r"<tr\b", html)[1:]:
        dm = re.search(r"<strong>(\d{1,2}-[A-Za-z]{3})</strong>", row)
        lk = re.search(r'href="(/' + re.escape(f) + r'/[^"]+-tournament-\d+)"[^>]*>([^<]+)', row)
        if not (dm and lk) or lk.group(1) in seen:
            continue
        seen.add(lk.group(1))
        pl = re.search(r"(\d+|\?)\s*Players", row, re.I)
        out.append({
            "date": _iso(dm.group(1), today),
            "players": int(pl.group(1)) if pl and pl.group(1).isdigit() else None,
            "platform": "online" if "/img/icons/mtgo" in row else "paper",
            "name": re.sub(r"\s+", " ", lk.group(2)).strip(),
            "url": BASE + lk.group(1),
        })
    return out


if __name__ == "__main__":
    for fmt in ("standard", "pioneer", "modern", "legacy"):
        try:
            ts = tournaments(fmt)
        except requests.RequestException as e:
            print(fmt, "erro:", e)
            continue
        big = sorted((t for t in ts if (t["players"] or 0) >= 24),
                     key=lambda t: -(t["players"] or 0))
        print(f"\n{fmt} — {len(ts)} torneios, {len(big)} com >=24 jogadores:")
        for t in big[:8]:
            print(f"   {t['players']:>4}j · {t['date']} · {t['name'][:55]}")
