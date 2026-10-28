"""O ÍNDICE QUE NÃO RESPONDE NÃO É UM DIA SEM TORNEIOS (2026-10-28).

O `harvest-mtgo` ficou «ok, 0 novas» a 22, 24 e 27/10 — a 27/10 em ~0 s. O
`fetch_mtgo_index` engolia o erro de rede/HTTP do índice
(`/decklists/AAAA/MM`) e devolvia `[]`, que é exactamente o que devolve um dia
sem eventos; o `harvest_mtgo` engolia o resto. O passo ficava verde no
`job_runs`, a tarefa `ai-pc/tasks/mtgvault-daily` (que chumba com qualquer
passo ≠ `ok`) não tinha nada que ver, e o dia perdia-se ao fim de
`daily.MTGO_DAYS` noites. O `mtgtop8.harvest` tinha o mesmo padrão: um `break`
no primeiro pedido do índice e «0 novas».

Agora as duas coisas distinguem-se:
  * o índice RESPONDEU e não tem nada daquele dia → `[]` / 0 novas, verde;
  * o índice NÃO respondeu (rede ou HTTP) → `sources.IndiceFalhou`, que o
    `daily._step` grava como `erro` no `job_runs`.
E o que se colheu nos outros dias (ou nas revisitas do mtgtop8) fica na base: a
falha diz-se no FIM, não deita fora o trabalho.

Sem rede: o `requests.get` do `sources` e o `_get` do `mtgtop8` são trocados por
falsos. Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {}, "baldes_coleccao": ["Colecção"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "caixas": [], "regras_por_formato": [], "cartas_vigiadas": [],
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Presencial", "Qualifier"],
                     "min_jogadores_presencial": 64, "ligas": False},
    },
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

import requests  # noqa: E402

import daily  # noqa: E402
from mtgvault import db, mtgtop8, sources  # noqa: E402

HOJE = _dt.date(2026, 10, 27)
_ABERTAS = []


class _D(_dt.date):
    @classmethod
    def today(cls):
        return HOJE


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    return cm.__enter__()


class _Resp:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Server Error")


def _com_mtgo(get, fn):
    """Corre `fn` com o `requests.get` do `sources` trocado e sem pausa."""
    rg, rp, rd = sources.requests.get, sources.PAUSA_MTGO, sources.date
    sources.requests.get, sources.PAUSA_MTGO, sources.date = get, 0.0, _D
    try:
        return fn()
    finally:
        sources.requests.get, sources.PAUSA_MTGO, sources.date = rg, rp, rd


def _sem_rede(url, **_k):
    raise requests.ConnectionError("Max retries exceeded (rede em baixo)")


# ---------------------------------------------------------------------------
# mtgo.com
# ---------------------------------------------------------------------------
def caso_o_indice_do_mtgo_sem_rede_rebenta():
    pedidos = []

    def get(url, **k):
        pedidos.append(url)
        return _sem_rede(url, **k)

    try:
        _com_mtgo(get, lambda: sources.fetch_mtgo_index(HOJE))
    except sources.IndiceFalhou as e:
        assert "2026/10" in str(e) or "2026-10" in str(e), e
    else:
        raise AssertionError("um índice que não responde não pode dar [] (é o "
                             "que dá um dia sem eventos)")
    # As duas formas de URL foram tentadas (2 tentativas cada no `_get_mtgo`).
    assert any("/decklists/2026/10" in u for u in pedidos), pedidos
    assert any("year=2026" in u for u in pedidos), pedidos


def caso_o_indice_do_mtgo_com_erro_http_rebenta():
    try:
        _com_mtgo(lambda url, **k: _Resp("", 503),
                  lambda: sources.fetch_mtgo_index(HOJE))
    except sources.IndiceFalhou as e:
        assert "503" in str(e), e
    else:
        raise AssertionError("um 503 no índice não é um dia sem eventos")


def caso_um_dia_sem_eventos_continua_a_ser_zero_e_verde():
    """O índice respondeu, só não tem nada daquele dia: isso NÃO é erro."""
    indice = '<a href="/decklist/modern-challenge-32-2026-10-2512345"></a>'
    r = _com_mtgo(lambda url, **k: _Resp(indice),
                  lambda: sources.fetch_mtgo_index(HOJE))
    assert r == [], r
    con = base()
    n = _com_mtgo(lambda url, **k: _Resp(indice),
                  lambda: sources.harvest_mtgo(con, 2, {"modern"}))
    assert n == 0, n


def caso_basta_uma_forma_do_indice_responder():
    """A 1.ª forma de URL falha e a 2.ª responde (sem eventos): o índice existe,
    o dia está vazio — não é erro."""
    def get(url, **k):
        if "/decklists/2026/10" in url:
            raise requests.ConnectionError("rede")
        return _Resp("<html></html>")
    assert _com_mtgo(get, lambda: sources.fetch_mtgo_index(HOJE)) == []


def caso_o_harvest_mtgo_falha_no_fim_e_guarda_o_resto():
    """Um dia sem índice põe o passo a falhar — mas os dias que responderam
    ficam colhidos, e o erro diz quantos dias faltaram."""
    ontem = HOJE - _dt.timedelta(days=1)
    url_ev = f"/decklist/modern-challenge-32-{ontem:%Y-%m-%d}12345"
    blob = {"description": "Modern Challenge 32", "starttime": f"{ontem}",
            "player_count": 32, "decklists": [
                {"player": "Fulano", "loginid": 1, "rank": 1,
                 "main_deck": [{"quantity": 60,
                                "card_attributes": {"card_name": "Island"}}],
                 "sideboard_deck": []}]}
    pagina = f"<script>window.MTGO.decklists.data = {json.dumps(blob)};</script>"
    chamadas = {"indice": 0}

    def get(url, **k):
        if "/decklist/" in url:
            return _Resp(pagina)
        chamadas["indice"] += 1
        # o 1.º dia (ontem) responde; os seguintes (anteontem…) caem
        if chamadas["indice"] == 1:
            return _Resp(f'<a href="{url_ev}"></a>')
        raise requests.ConnectionError("rede em baixo")

    con = base()
    try:
        _com_mtgo(get, lambda: sources.harvest_mtgo(con, 2, {"modern"}))
    except sources.IndiceFalhou as e:
        msg = str(e)
        assert "1 de 2" in msg, msg
        assert "1 novas" in msg, msg
    else:
        raise AssertionError("o dia sem índice tem de pôr o passo a falhar")
    n = con.execute("SELECT COUNT(*) FROM decklists WHERE source = 'mtgo'").fetchone()[0]
    assert n == 1, f"a lista do dia que respondeu tem de ficar na base ({n})"


def caso_o_passo_do_daily_fica_erro_no_job_runs():
    """O que a tarefa do ai-pc lê é o `job_runs`: tem de lá estar `erro`."""
    con = base()
    _com_mtgo(_sem_rede, lambda: daily._step(
        con, "harvest-mtgo",
        lambda: f"{sources.harvest_mtgo(con, 1)} novas"))
    st, det = con.execute(
        "SELECT status, detail FROM job_runs WHERE job = 'harvest-mtgo' "
        "ORDER BY id DESC LIMIT 1").fetchone()
    assert st == "erro", (st, det)
    assert "IndiceFalhou" in det and "mtgo.com" in det, det


# ---------------------------------------------------------------------------
# mtgtop8
# ---------------------------------------------------------------------------
def _com_top8(get, fn):
    antigo = mtgtop8._get
    mtgtop8._get = get
    try:
        return fn()
    finally:
        mtgtop8._get = antigo


def caso_o_indice_do_mtgtop8_sem_rede_rebenta():
    def get(path, **params):
        if path == "/format":
            raise requests.ConnectionError("rede em baixo")
        raise AssertionError(f"pedido inesperado: {path} {params}")
    con = base()
    try:
        _com_top8(get, lambda: mtgtop8.harvest(con, "premodern", max_events=8))
    except sources.IndiceFalhou as e:
        assert "mtgtop8" in str(e) and "premodern" in str(e), e
    else:
        raise AssertionError("o índice do mtgtop8 sem rede não pode dar 0 novas")


def caso_o_indice_do_mtgtop8_vazio_e_zero_e_verde():
    def get(path, **params):
        if path == "/format":
            return "<html></html>"
        raise AssertionError(f"pedido inesperado: {path} {params}")
    con = base()
    assert _com_top8(get, lambda: mtgtop8.harvest(con, "premodern", max_events=8)) == 0


def caso_a_pagina_2_do_indice_do_mtgtop8_tambem_conta():
    """A página 1 diz que há 2 páginas; a 2.ª cai — é um pedaço do índice que
    não se viu, e diz-se."""
    pag1 = ("<div class=w_title align=center>LAST 20 EVENTS</div><table></table>"
            "<div><div class=Nav_norm><a href=?f=PREM&cp=2>2</a></div></div>")

    def get(path, **params):
        if path == "/format" and not params.get("cp"):
            return pag1
        if path == "/format":
            raise requests.ConnectionError("rede em baixo")
        raise AssertionError(f"pedido inesperado: {path} {params}")
    con = base()
    try:
        _com_top8(get, lambda: mtgtop8.harvest(con, "premodern", max_events=8,
                                               paginas=2))
    except sources.IndiceFalhou as e:
        assert "pagina 2" in str(e), e
    else:
        raise AssertionError("a página 2 do índice que não veio tem de se dizer")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    maus = 0
    for c in CASOS:
        try:
            c()
            print(f"  ok   {c.__name__}")
        except Exception as e:                                # noqa: BLE001
            maus += 1
            print(f"  FAIL {c.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        cm.__exit__(None, None, None)
    print(f"{len(CASOS) - maus}/{len(CASOS)} ok")
    sys.exit(1 if maus else 0)
