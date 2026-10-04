"""OS CODIGOS DE EDICAO DO CARDTRADER NAO SAO UNICOS ENTRE JOGOS (2026-10-04).

Medido contra a API nesse dia, so leitura: `/expansions` devolve **3 876**
expansoes de 24 jogos, todas com `game_id` e `code`, e **142** codigos
aparecem em mais do que um jogo. Os dois sitios que o liam faziam

    exps = {e["code"].lower(): e["id"] for e in ct.expansions() if e.get("code")}

— um `dict`, logo **o ultimo ganha** — e em **26** desses codigos o ultimo e
de outro jogo:

    'exp' -> 1991 «ADV Expansion Pack» (Pokemon)  em vez de 83  Zendikar Expeditions
    'sld' -> 3202 «Sword & Shield ... Darkrai»    em vez de 990 Secret Lair Drop Series
    'mrd' -> 1049 «Metal Raiders» (Yu-Gi-Oh!)     em vez de 303 Mirrodin

Pedia-se depois `/blueprints/export` e `/marketplace/products` do id errado:
nenhum blueprint batia certo com o catalogo de Magic, o `cardtrader_map`
ficava vazio e a carta ficava **sem preco do CardTrader** — sem um unico
erro, sem um passo a falhar. E o padrao do `event_tier`, desta vez sobre as
23 Zendikar Expeditions dele (10,8 mil euros a Cardmarket).

O que se tranca aqui, e porque e que cada caso chumba em cima do codigo
antigo:

  1. `expansoes_mtg` so ve `game_id == 1` — o caso do 'exp'/'sld' chumba
     porque o antigo devolvia o id do Pokemon;
  2. a chamada a `/blueprints/export` e a `/marketplace/products` vai ao id
     do MAGIC — e o mapa enche-se e o preco fica gravado (e isto o defeito a
     serio: o resto e maneira de la chegar);
  3. um codigo que SO existe noutro jogo nunca entra no mapa (o antigo
     entrava, e pedia duas paginas por nada);
  4. um codigo que repete DENTRO do Magic fica com o id mais baixo e **diz-se
     no log**. Hoje nao acontece (793 expansoes de Magic, 0 codigos
     repetidos — verificado, nao assumido), mas a decisao nao pode voltar a
     ser «a ordem em que a API os serve».

Sem rede: o cliente falso devolve trechos com a forma real da API (as chaves
sao exactamente as quatro que ela manda: `id`, `code`, `game_id`, `name`).
"""
import json
import logging
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps({}), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, prices  # noqa: E402

HOJE = date.today().isoformat()
_ABERTAS = []

# As expansoes de Magic que o bug roubava, com os ids a serio.
EXP_MTG, EXP_POKEMON = 83, 1991
SLD_MTG, SLD_POKEMON = 990, 3202
LTR_MTG, LTR_POKEMON = 3261, 1896
USG = 324

# Trecho com a forma real do /expansions (as quatro chaves que a API manda).
# A ORDEM importa, e o 'ltr' esta ca de proposito:
#   'exp'/'sld' — o outro jogo vem DEPOIS do Magic, e o antigo escolhia-o;
#   'ltr'       — o outro jogo vem ANTES e tem id MAIS BAIXO, por isso o
#                 antigo acertava por sorte E um desempate «fica o id mais
#                 baixo» sem filtro de jogo erraria. E o que obriga o filtro a
#                 ser pelo `game_id` e nao por uma heuristica de ids.
EXPANSOES = [
    {"id": USG, "code": "usg", "game_id": 1, "name": "Urza's Saga"},
    {"id": EXP_MTG, "code": "exp", "game_id": 1, "name": "Zendikar Expeditions"},
    {"id": EXP_POKEMON, "code": "exp", "game_id": 5, "name": "ADV Expansion Pack"},
    {"id": SLD_MTG, "code": "sld", "game_id": 1, "name": "Secret Lair Drop Series"},
    {"id": SLD_POKEMON, "code": "sld", "game_id": 5,
     "name": "Sword & Shield Starter Set Darkrai VSTAR"},
    {"id": LTR_POKEMON, "code": "ltr", "game_id": 5, "name": "Legendary Treasures"},
    {"id": LTR_MTG, "code": "ltr", "game_id": 1, "name": "The Lord of the Rings"},
    # So existe no Yu-Gi-Oh!: nunca pode entrar no mapa.
    {"id": 1031, "code": "dds", "game_id": 4, "name": "Dark Duel Stories"},
]


class CTFalso:
    """O CardTrader sem rede. Guarda a QUE ids lhe pediram — e a pergunta
    desta bateria e precisamente essa."""

    def __init__(self, expansoes=None, blueprints=None, ofertas=None):
        self.exps = expansoes if expansoes is not None else EXPANSOES
        self._bp = blueprints or {}
        self._of = ofertas or {}
        self.pedidos_bp: list[int] = []
        self.pedidos_mkt: list[int] = []

    def expansions(self):
        return [dict(e) for e in self.exps]

    def blueprints(self, expansion_id: int):
        self.pedidos_bp.append(expansion_id)
        return self._bp.get(expansion_id, [])

    def marketplace(self, expansion_id: int):
        self.pedidos_mkt.append(expansion_id)
        return self._of.get(expansion_id, {})


class Apanha(logging.Handler):
    """Apanha os avisos de `prices` sem os imprimir."""

    def __init__(self):
        super().__init__()
        self.linhas = []

    def emit(self, record):
        self.linhas.append(record.getMessage())


def base():
    """Base com duas cartas de 'exp' e uma de 'sld' no catalogo."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    cartas = [("sid-waste", "Wasteland", "exp", "45"),
              ("sid-arid", "Arid Mesa", "exp", "1"),
              ("sid-bolt", "Lightning Bolt", "sld", "100")]
    for sid, nm, st, cn in cartas:
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Land',0,'',?,'2015-10-02',?,0,0)""",
            (sid, "or-" + sid, nm, st, st.upper(), cn,
             json.dumps(["nonfoil", "foil"]), json.dumps({"legacy": "legal"})))
    con.commit()
    return con


def _oferta(cents, uid=1, foil=False):
    """Uma oferta com a forma do /marketplace/products (sonda de 2026-09-25).

    A API manda o preco nas DUAS formas — `price_cents`/`price_currency` a
    plano e `price: {cents, currency}` — e e a plana que o
    `precos.oferta_utilizavel` le.
    """
    return {"id": 10_000 + uid, "blueprint_id": 777, "quantity": 1,
            "price_cents": cents, "price_currency": "EUR",
            "graded": False, "on_vacation": False,
            "properties_hash": {"condition": "Near Mint", "mtg_language": "en",
                                "mtg_foil": foil, "signed": False,
                                "altered": False},
            "user": {"id": uid, "username": "x"},
            "price": {"cents": cents, "currency": "EUR"}}


# ---------------------------------------------------------------------------
# 1. O MAPA SO VE MAGIC
# ---------------------------------------------------------------------------
def caso_o_codigo_repetido_entre_jogos_fica_com_a_expansao_de_magic():
    """'exp' e 'sld' existem nos dois jogos e o Magic tem de ganhar.

    Chumba em cima do codigo antigo: o `dict` por compreensao deixava o
    ultimo ganhar, e o ultimo e o Pokemon.
    """
    exps = prices.expansoes_mtg(CTFalso())
    assert exps["exp"] == EXP_MTG, (
        f"'exp' ficou com {exps['exp']} (Pokemon e {EXP_POKEMON}; "
        f"Zendikar Expeditions e {EXP_MTG})")
    assert exps["sld"] == SLD_MTG, (
        f"'sld' ficou com {exps['sld']} (Pokemon e {SLD_POKEMON}; "
        f"Secret Lair e {SLD_MTG})")
    # o 'ltr' e o contra-exemplo: o id de Magic e o MAIS ALTO dos dois, por
    # isso quem desempatar por id em vez de por jogo erra aqui.
    assert exps["ltr"] == LTR_MTG, (
        f"'ltr' ficou com {exps['ltr']} (Pokemon e {LTR_POKEMON}, mais baixo; "
        f"The Lord of the Rings e {LTR_MTG})")
    assert exps["usg"] == USG


def caso_um_codigo_que_so_existe_noutro_jogo_nao_entra():
    """'dds' so existe no Yu-Gi-Oh! neste trecho: nao ha expansao de Magic.

    O antigo metia-o no mapa e ia pedir-lhe duas paginas — e, pior, se ele
    coincidisse com um codigo que o Andre tem na coleccao, o preco da carta
    dele vinha de outro jogo.
    """
    exps = prices.expansoes_mtg(CTFalso())
    assert "dds" not in exps, f"'dds' (Yu-Gi-Oh!) entrou como {exps.get('dds')}"
    assert sorted(exps) == ["exp", "ltr", "sld", "usg"], sorted(exps)


def caso_uma_expansao_sem_codigo_nao_rebenta():
    """A API manda sempre `code`, mas um vazio nao pode levantar."""
    exps = prices.expansoes_mtg(CTFalso([
        {"id": 1, "code": "", "game_id": 1, "name": "sem codigo"},
        {"id": 2, "code": None, "game_id": 1, "name": "nulo"},
        {"id": USG, "code": "USG", "game_id": 1, "name": "Urza's Saga"}]))
    assert exps == {"usg": USG}, exps


# ---------------------------------------------------------------------------
# 2. E O PEDIDO VAI AO ID DO MAGIC (o defeito a serio)
# ---------------------------------------------------------------------------
def caso_o_sync_do_mapa_pede_os_blueprints_do_magic():
    """`sync_cardtrader_map('exp')` tem de abrir a expansao 83 e encher o mapa.

    Esta e a metade que custava dinheiro: com o id do Pokemon os blueprints
    nao traziam `scryfall_id` nenhum que batesse certo, o mapa ficava vazio e
    **nenhum passo falhava**. Na base dele, a 2026-10-04: 0 das 45 impressoes
    de 'exp' no `cardtrader_map`.
    """
    con = base()
    ct = CTFalso(blueprints={
        EXP_MTG: [{"id": 9276, "name": "Wasteland", "scryfall_id": "sid-waste"},
                  {"id": 9277, "name": "Arid Mesa", "scryfall_id": "sid-arid"}],
        # o que o CardTrader serviria se lhe pedissem o id do Pokemon
        EXP_POKEMON: [{"id": 55_001, "name": "Blaziken ex", "scryfall_id": None}],
    })
    n = prices.sync_cardtrader_map(con, ct, ["exp"])

    assert ct.pedidos_bp == [EXP_MTG], (
        f"pediu os blueprints de {ct.pedidos_bp} (esperado [{EXP_MTG}])")
    assert n == 2, n
    mapa = dict(con.execute("SELECT scryfall_id, blueprint_id FROM cardtrader_map"))
    assert mapa == {"sid-waste": 9276, "sid-arid": 9277}, mapa


def caso_os_precos_saem_do_marketplace_do_magic():
    """Ponta a ponta: 'sld' -> expansao 990 -> oferta -> `price_latest`.

    Com o id do Pokemon o `/marketplace/products` devolve blueprints que nao
    estao no `cardtrader_map`, por isso **zero** linhas de preco. Com o id
    certo, a carta fica cotada.
    """
    con = base()
    con.execute("INSERT OR REPLACE INTO cardtrader_map (scryfall_id, "
                "blueprint_id, checked_at) VALUES ('sid-bolt', 777, ?)", (HOJE,))
    con.commit()
    ct = CTFalso(ofertas={
        SLD_MTG: {"777": [_oferta(1000, 1), _oferta(3000, 2), _oferta(5000, 3)]},
        SLD_POKEMON: {"88888": [_oferta(50, 9)]},
    })
    n = prices.fetch_cardtrader_prices(con, ct, ["sld"])

    assert ct.pedidos_mkt == [SLD_MTG], (
        f"pediu o marketplace de {ct.pedidos_mkt} (esperado [{SLD_MTG}])")
    assert n == 1, f"{n} linhas de preco (esperada 1)"
    r = con.execute("SELECT scryfall_id, low, trend FROM price_latest "
                    "WHERE source='cardtrader' AND finish='nonfoil'").fetchone()
    assert r["scryfall_id"] == "sid-bolt", dict(r)
    assert (r["low"], r["trend"]) == (10.0, 30.0), (r["low"], r["trend"])


def caso_sem_set_codes_o_sync_percorre_so_as_edicoes_de_magic():
    """`set_codes=None` usa o mapa inteiro — que agora e so Magic.

    O antigo percorria as 3 876 expansoes de todos os jogos.
    """
    con = base()
    ct = CTFalso()
    prices.sync_cardtrader_map(con, ct, None)
    assert sorted(ct.pedidos_bp) == sorted([USG, EXP_MTG, SLD_MTG, LTR_MTG]), (
        ct.pedidos_bp)


# ---------------------------------------------------------------------------
# 3. REPETIDO DENTRO DO MAGIC: FICA O MAIS BAIXO, E DIZ-SE
# ---------------------------------------------------------------------------
def caso_codigo_repetido_dentro_do_magic_fica_o_id_mais_baixo_e_avisa():
    """Hoje nao acontece (0 repetidos em 793), mas nao pode decidir-se sozinho.

    O id mais alto vem DEPOIS de proposito: e assim que se ve que a escolha
    deixou de ser «o ultimo que a API serviu».
    """
    h = Apanha()
    log = logging.getLogger("mtgvault.prices")
    log.addHandler(h)
    try:
        exps = prices.expansoes_mtg(CTFalso([
            {"id": 100, "code": "dup", "game_id": 1, "name": "A"},
            {"id": 900, "code": "dup", "game_id": 1, "name": "B"},
        ]))
    finally:
        log.removeHandler(h)
    assert exps == {"dup": 100}, exps
    assert any("dup" in m and "100" in m for m in h.linhas), h.linhas


def caso_o_desempate_nao_depende_da_ordem_da_api():
    """O mesmo par pela ordem contraria da a MESMA resposta."""
    h = Apanha()                      # so para o aviso nao ir para o stderr
    log = logging.getLogger("mtgvault.prices")
    log.addHandler(h)
    try:
        a = prices.expansoes_mtg(CTFalso([
            {"id": 100, "code": "dup", "game_id": 1, "name": "A"},
            {"id": 900, "code": "dup", "game_id": 1, "name": "B"}]))
        b = prices.expansoes_mtg(CTFalso([
            {"id": 900, "code": "dup", "game_id": 1, "name": "B"},
            {"id": 100, "code": "dup", "game_id": 1, "name": "A"}]))
    finally:
        log.removeHandler(h)
    assert a == b == {"dup": 100}, (a, b)


# ---------------------------------------------------------------------------
# 4. A PERGUNTA VIVE NUM SITIO SO
# ---------------------------------------------------------------------------
def caso_ninguem_volta_a_ler_o_expansions_a_mao():
    """Dois sitios faziam a mesma conta e os dois estavam errados.

    O proximo caminho que se esqueca do `game_id` repete o defeito em
    silencio — a licao do `e_foil`, do `precos.sql()` e do `venda.mostrar`.
    So o `expansoes_mtg` pode chamar o `ct.expansions()`.
    """
    raiz = Path(__file__).resolve().parents[1]
    maus = []
    for f in list(raiz.glob("*.py")) + list((raiz / "mtgvault").glob("*.py")):
        txt = f.read_text(encoding="utf-8")
        for i, linha in enumerate(txt.splitlines(), 1):
            if "expansions()" not in linha or linha.lstrip().startswith("#"):
                continue
            if f.name == "prices.py" and "for e in ct.expansions()" in linha:
                continue          # e o proprio `expansoes_mtg`
            maus.append(f"{f.name}:{i}: {linha.strip()}")
    assert not maus, ("alguem voltou a ler o /expansions por fora do "
                      "`prices.expansoes_mtg`", maus)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for c in casos:
        try:
            c()
            print(f"  ok   {c.__name__}")
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print(f"  FAIL {c.__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                   # noqa: BLE001,S110
            pass
    print(f"{len(casos) - falhas}/{len(casos)} ok")
    sys.exit(1 if falhas else 0)
