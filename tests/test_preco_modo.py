"""O MODO DE PREÇO: market, best ou a média dos dois (André, 2026-09-25).

À letra: *"tal como no riftvault, o preço da colecção pode ser pelo market
value do cardtrader, ou o best value, ou a média dos 2"*.

O que aqui se tranca, por ordem de importância:

  1. **Trocar de modo NÃO pode mandar uma RL para a venda.** É a única coisa
     que muda de comportamento e não só de número, e é irreversível: uma
     Reserved List vendida não se volta a comprar pelo mesmo dinheiro. Dois
     casos — o modo trocado hoje (`precos.modo_desde`) e a RECEITA trocada
     (a coluna `trend` a querer dizer outra coisa) — e nos dois a resposta
     tem de ser `rl_sem_historico`, a terceira resposta que existe desde
     2026-09-08, nunca *"não subiu"*.
  2. O CardTrader passa a guardar **os dois** valores (era um só, copiado
     para as duas colunas) e a filtrar as ofertas impróprias.
  3. Uma carta sem preço na fonte escolhida é *"sem preço"*, **não 0 €**.
  4. O modo manda em TODAS as superfícies ao mesmo tempo — o valor da
     colecção, o que falta comprar, as wantlists e a venda. Duas páginas com
     duas contas para o mesmo dinheiro é o defeito que isto não pode criar.

Não toca na rede: as ofertas do CardTrader são um trecho com a forma real
devolvida por `/marketplace/products` (sonda de 2026-09-25).
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
CFG_PATH = _TMP / "cfg.json"
BASE_CFG = {"regras_por_formato": [
    {"grupo": "spml", "formatos": ["legacy"], "lingua": "en"}]}
CFG_PATH.write_text(json.dumps(BASE_CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, loadout, precos, prices, wantlist  # noqa: E402

HOJE = date.today()
_ABERTAS = []

CATALOGO = [("Gilded Drake", 1), ("Null Rod", 1), ("Sol Ring", 0)]


def cfg(**blocos):
    """Reescreve o config e esquece as caches."""
    from mtgvault import sources
    novo = json.loads(json.dumps(BASE_CFG))
    novo.update(blocos)
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return novo


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,'usg','S',?,'en','rare','Artifact',2,'',?,
                       '1998-10-12',?,0,?)""",
            (f"id-{i}", f"or-{i}", nm, str(i), json.dumps(["nonfoil", "foil"]),
             json.dumps({"legacy": "legal", "commander": "legal"}), rl))
    con.commit()
    return con


def sid_de(con, nm):
    return con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                       (nm,)).fetchone()["scryfall_id"]


def add(con, nm, q=1, sub="Colecção"):
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,'nonfoil','en',
                   'player',?)""", (sid_de(con, nm), q, sub_id))
    con.commit()


def dia(n):
    return (HOJE - timedelta(days=n)).isoformat()


def cota(con, nm, quando, low, trend, receita=precos.RECEITA_UNICA):
    """Uma cotação num dia, pelo `prices.write_prices` — é ele que decide o que
    entra no `price_history`, e escrever a tabela à mão provava outra coisa."""
    prices.write_prices(con, [(sid_de(con, nm), "cardmarket", quando, "nonfoil",
                               low, trend, None, None, "EUR", receita)])


def deck_vazio(con):
    con.execute("INSERT INTO decks (name, format) VALUES ('Leg','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name = 'Leg'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Sol Ring', 1, 'main')", (did,))
    con.commit()


def slot_legacy():
    return {"slot": "leg", "nome": "Leg", "formato": "legacy", "fonte": "deck",
            "ref": "Leg", "prioridade": 1, "balde": "Colecção"}


def venda_de(con, nm):
    """Em que saída da venda é que esta carta está hoje."""
    rep = loadout.report(con, [slot_legacy()])
    for saida in ("venda", "venda_rl", "rl_segurar", "rl_sem_historico",
                  "guardar", "reservadas", "retidos"):
        if any(l["nm"] == nm for l in rep.get(saida) or []):
            return saida, [l for l in rep[saida] if l["nm"] == nm]
    return None, []


# ---------------------------------------------------------------------------
# 1. A REGRA DA RESERVED LIST
# ---------------------------------------------------------------------------
def caso_trocar_de_modo_nao_manda_nenhuma_rl_para_a_venda():
    """O caso que o André mandou forçar, à letra.

    Cenário: 200 dias de histórico, e nele o **market value** (trend) subiu
    8 % — a carta está a ser SEGURA — enquanto o **best value** (low) desceu
    2 %. Trocar para `best` faria uma comparação que, sozinha, diria *"não
    subiu"* e mandava a Gilded Drake à venda; só que o que mudou não foi o
    mercado, foi a régua. Enquanto não houver `rl_janela_minima_dias` medidos
    NO MODO NOVO, a resposta tem de ser `rl_sem_historico`.

    Este caso chumba em cima de um `avaliar_rl` que ignore o `modo_desde`: sem
    esse travão a carta cai em `venda_rl`, que é exactamente o que não pode
    acontecer.
    """
    cfg(venda={"rl_subida_minima_pct": 5, "rl_janela_dias": 90,
               "rl_janela_minima_dias": 25},
        precos={"modo": "market", "fonte": "cardmarket"})
    con = base()
    deck_vazio(con)
    add(con, "Gilded Drake", 6)
    cota(con, "Gilded Drake", dia(200), 100.0, 100.0)
    cota(con, "Gilded Drake", HOJE.isoformat(), 98.0, 108.0)

    saida, _ = venda_de(con, "Gilded Drake")
    assert saida == "rl_segurar", f"em `market` devia segurar, está em {saida}"

    # E agora ele troca para «best value», hoje.
    precos.gravar_modo("best", CFG_PATH, hoje=HOJE.isoformat())
    from mtgvault import sources
    sources._CFG_CACHE.clear()
    assert precos.modo() == "best"

    saida, linhas = venda_de(con, "Gilded Drake")
    assert saida == "rl_sem_historico", (
        f"trocar de modo mandou a RL para «{saida}» — é exactamente o que não "
        f"pode acontecer. Motivo: {linhas and linhas[0].get('motivo')}")
    assert saida != "venda_rl"


def caso_a_receita_nova_nao_se_compara_com_a_antiga():
    """A coluna é a mesma, o significado mudou — e isso não se compara.

    Até 2026-09-25 o CardTrader escrevia `low = trend = min(ofertas)`; agora o
    `trend` é a MEDIANA. Uma linha antiga (receita `unico`) e uma de hoje
    (`ct-ofertas`) não estão na mesma escala: comparar as duas inventa uma
    subida de dezenas por cento que nunca houve. O `_historico` só traz pontos
    da receita em vigor — e sem janela a resposta é «não sei».
    """
    cfg(venda={"rl_subida_minima_pct": 5, "rl_janela_dias": 90,
               "rl_janela_minima_dias": 25},
        precos={"modo": "market", "fonte": "cardmarket"})
    con = base()
    deck_vazio(con)
    add(con, "Null Rod", 6)
    cota(con, "Null Rod", dia(200), 40.0, 40.0, precos.RECEITA_UNICA)
    cota(con, "Null Rod", HOJE.isoformat(), 39.0, 39.0, precos.RECEITA_CM_GUIDE)

    assert precos.receita_em_vigor(con, "cardmarket") == precos.RECEITA_CM_GUIDE
    rows = loadout._historico(con, "Null Rod", "nonfoil")
    assert [r["d"] for r in rows] == [HOJE.isoformat()], (
        "o histórico trouxe pontos de outra receita: " + str([r["d"] for r in rows]))
    saida, _ = venda_de(con, "Null Rod")
    assert saida == "rl_sem_historico", saida


def caso_trocar_para_o_mesmo_modo_nao_reinicia_a_janela():
    """Carregar no botão que já está escolhido não é trocar de modo.

    Reiniciar a janela por um clique sem efeito era castigá-lo por confirmar
    uma escolha que já tinha feito — e deixava a regra em «não sei» para
    sempre, bastando tocar no botão de vez em quando.
    """
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    r = precos.gravar_modo("market", CFG_PATH, hoje=HOJE.isoformat())
    assert r["mudou"] is False
    assert precos.modo_desde() is None
    r = precos.gravar_modo("media", CFG_PATH, hoje=HOJE.isoformat())
    assert r["mudou"] is True and r["desde"] == HOJE.isoformat()


def caso_um_modo_desconhecido_e_recusado():
    """O config é editável à mão: uma gralha não pode deixar o site sem preços
    (fica com o de omissão), mas quem ESCREVE tem de ser recusado."""
    cfg(precos={"modo": "azul", "fonte": "cardmarket"})
    assert precos.modo() == precos.MODO_OMISSAO
    try:
        precos.gravar_modo("azul", CFG_PATH)
    except ValueError as e:
        assert "azul" in str(e)
    else:
        raise AssertionError("um modo desconhecido tinha de ser recusado")


# ---------------------------------------------------------------------------
# 2. OS DOIS VALORES DO CARDTRADER
# ---------------------------------------------------------------------------
# Trecho com a forma REAL de `/marketplace/products` (sonda de 2026-09-25 à
# expansão `ody`): cada oferta traz só o seu `price_cents` — não há campo
# nenhum de "market value" na API, e é por isso que ele se calcula.
def _oferta(cents, *, cond="Near Mint", lang="en", foil=False, graded=False,
            vacation=False, signed=False, quantity=1, uid=1):
    return {"id": cents, "blueprint_id": 27930, "name_en": "Gilded Drake",
            "price_cents": cents, "price_currency": "EUR", "quantity": quantity,
            "graded": graded, "on_vacation": vacation,
            "properties_hash": {"mtg_rarity": "Rare", "condition": cond,
                                "mtg_language": lang, "mtg_foil": foil,
                                "signed": signed, "altered": False,
                                "collector_number": "1"},
            "user": {"id": uid, "username": "x"},
            "price": {"cents": cents, "currency": "EUR"}}


class CTFalso:
    """O CardTrader sem rede: devolve o trecho acima."""

    def __init__(self, ofertas):
        self.ofertas = ofertas

    def expansions(self):
        return [{"id": 324, "code": "usg", "name_en": "Urza's Saga"}]

    def marketplace(self, expansion_id):
        return {"27930": self.ofertas}


def caso_o_cardtrader_guarda_os_dois_valores():
    """`low` = a oferta mais barata, `trend` = a MEDIANA das utilizáveis.

    Era um só, copiado para as duas colunas — e por isso os três modos do
    André davam todos o mesmo número. Chumba em cima do código antigo.
    """
    cfg(precos={"modo": "market", "fonte": "cardtrader"})
    con = base()
    con.execute("INSERT OR REPLACE INTO cardtrader_map (scryfall_id, "
                "blueprint_id, checked_at) VALUES (?, 27930, '2026-09-25')",
                (sid_de(con, "Gilded Drake"),))
    con.commit()
    ofertas = [_oferta(c, uid=i) for i, c in enumerate((1000, 2000, 3000,
                                                        4000, 9000))]
    prices.fetch_cardtrader_prices(con, CTFalso(ofertas), ["usg"])

    r = con.execute("SELECT low, trend, receita FROM price_latest "
                    "WHERE source='cardtrader' AND finish='nonfoil'").fetchone()
    assert r["low"] == 10.0, r["low"]
    assert r["trend"] == 30.0, f"a mediana de 10..90 é 30, veio {r['trend']}"
    assert r["low"] != r["trend"], "os dois valores voltaram a ser o mesmo"
    assert r["receita"] == precos.RECEITA_CT_OFERTAS


def caso_as_ofertas_improprias_nao_fazem_preco():
    """O filtro do riftvault (`prices._usable`), copiado à letra.

    Sem ele, o preço de um Mountain de Odyssey era os 0,28 € de uma cópia
    italiana «Poor» com o verso escrito à mão — e esse número entrava no valor
    da colecção e na lista de compras.
    """
    cfg(precos={"modo": "best", "fonte": "cardtrader", "linguas": ["en", "pt"]})
    con = base()
    con.execute("INSERT OR REPLACE INTO cardtrader_map (scryfall_id, "
                "blueprint_id, checked_at) VALUES (?, 27930, '2026-09-25')",
                (sid_de(con, "Gilded Drake"),))
    con.commit()
    lixo = [_oferta(10, cond="Poor", uid=90),
            _oferta(11, lang="it", uid=91),
            _oferta(12, graded=True, uid=92),
            _oferta(13, vacation=True, uid=93),
            _oferta(14, signed=True, uid=94)]
    bons = [_oferta(5000, uid=1), _oferta(6000, uid=2)]
    prices.fetch_cardtrader_prices(con, CTFalso(lixo + bons), ["usg"])

    r = con.execute("SELECT low, trend FROM price_latest "
                    "WHERE source='cardtrader' AND finish='nonfoil'").fetchone()
    assert r["low"] == 50.0, (
        f"uma oferta imprópria fez o preço: {r['low']} € (esperado 50,00 €)")


# ---------------------------------------------------------------------------
# 3. «SEM PREÇO» NÃO É ZERO EUROS
# ---------------------------------------------------------------------------
def caso_sem_preco_na_fonte_escolhida_nao_e_zero_euros():
    """Uma impressão que a fonte não cota vale `None`, e nunca 0,00 €.

    Zero numa soma é a mentira mais cara que uma página de preços conta: some
    silenciosamente uma carta de 900 € do total sem nenhuma linha dizer que
    faltou.
    """
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    con = base()
    add(con, "Gilded Drake", 1)
    add(con, "Null Rod", 1)
    cota(con, "Gilded Drake", HOJE.isoformat(), 50.0, 60.0)
    # A Null Rod fica sem cotação nenhuma.
    v = collection.valor_da_coleccao(con)
    assert v["sem_preco"] == 1, v["sem_preco"]
    assert v["total"]["trend"] == 60.0
    linha = [c for c in v["copias"] if c["sid"] == sid_de(con, "Null Rod")][0]
    assert linha["unit"] is None, f"sem preço virou {linha['unit']!r}"

    assert loadout.card_price(con, "Null Rod") == (None, None)
    assert wantlist.cheapest_price(con, "Null Rod") is None


# ---------------------------------------------------------------------------
# 4. O MODO MANDA EM TODAS AS SUPERFÍCIES, AO MESMO TEMPO
# ---------------------------------------------------------------------------
def caso_os_tres_modos_dao_tres_precos_e_todas_as_paginas_concordam():
    """best 50 €, market 60 €, média 55 € — e o valor da colecção, o preço de
    compra e a wantlist dizem os TRÊS o mesmo em cada modo.

    É a razão de o `precos.sql` existir: o `MIN(p.trend)` estava escrito à mão
    em oito consultas, e a primeira que se esquecesse do modo punha duas
    páginas a dizer dois números para o mesmo dinheiro — o defeito que a conta
    única do valor corrigiu a 2026-09-24 e que isto não podia trazer de volta.
    """
    con = base()
    add(con, "Gilded Drake", 2)
    cota(con, "Gilded Drake", HOJE.isoformat(), 50.0, 60.0)
    esperado = {"best": 50.0, "market": 60.0, "media": 55.0}
    for m, p in esperado.items():
        cfg(precos={"modo": m, "fonte": "cardmarket"})
        v = collection.valor_da_coleccao(con)
        assert v["total"][collection.cenario_em_vigor()] == p * 2, (m, v["total"])
        assert loadout.card_price(con, "Gilded Drake")[0] == p, m
        assert wantlist.cheapest_price(con, "Gilded Drake") == p, m
        assert v["modo"] == m


def caso_a_media_de_um_so_valor_e_esse_valor():
    """Com `low` e sem `trend`, a média é o `low`.

    Inventar o outro lado para fazer média era pior do que não a fazer; e dar
    `None` escondia um preço que existe. (Com a receita `unico` — a de hoje na
    base dele — as duas colunas são iguais e os três modos coincidem, que é o
    que faz trocar de modo ser inofensivo até o CardTrader entrar.)
    """
    assert precos.de_valores(50.0, None, precos.MEDIA) == 50.0
    assert precos.de_valores(None, 60.0, precos.MEDIA) == 60.0
    assert precos.de_valores(None, None, precos.MEDIA) is None
    assert precos.de_valores(None, 60.0, precos.BEST) is None
    assert precos.de_valores(50.0, None, precos.MARKET) is None
    assert precos.de_valores(40.0, 60.0, precos.MEDIA) == 50.0


def caso_a_receita_entra_na_comparacao_do_write_prices():
    """Os mesmos números com outra receita são uma linha NOVA no histórico.

    O `write_prices` só grava mudanças. Se a receita não entrasse na
    comparação, o dia em que o significado da coluna mudou não ficava
    registado — e o `_historico` não tinha como separar as duas escalas.
    """
    con = base()
    cota(con, "Sol Ring", dia(2), 10.0, 10.0, precos.RECEITA_UNICA)
    n = prices.write_prices(con, [(sid_de(con, "Sol Ring"), "cardmarket",
                                   dia(1), "nonfoil", 10.0, 10.0, None, None,
                                   "EUR", precos.RECEITA_CT_OFERTAS)])
    assert n == 1, "a receita nova não gerou linha de histórico"
    linhas = con.execute("SELECT date, receita FROM price_history "
                         "ORDER BY date").fetchall()
    assert [l["receita"] for l in linhas] == [precos.RECEITA_UNICA,
                                              precos.RECEITA_CT_OFERTAS]


def caso_uma_linha_antiga_sem_receita_vale_unico():
    """A base dele tem 250 000 linhas escritas antes desta coluna existir.

    Ficam a NULL e valem `unico` — que é o que elas SÃO (o bulk da Scryfall
    escreve o mesmo número nas duas colunas). Marcá-las com uma receita que
    nunca tiveram era inventar histórico.
    """
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    con = base()
    sid = sid_de(con, "Sol Ring")
    con.execute("INSERT INTO price_history (scryfall_id, source, date, finish, "
                "low, trend) VALUES (?, 'cardmarket', ?, 'nonfoil', 7.0, 7.0)",
                (sid, dia(30)))
    con.execute("INSERT INTO price_latest (scryfall_id, source, finish, date, "
                "low, trend) VALUES (?, 'cardmarket', 'nonfoil', ?, 7.0, 7.0)",
                (sid, dia(30)))
    con.commit()
    assert precos.receita_em_vigor(con, "cardmarket") == precos.RECEITA_UNICA
    assert len(loadout._historico(con, "Sol Ring", "nonfoil")) == 1


def caso_a_coluna_receita_existe_nos_tres_sitios():
    """Uma coluna nova tem de entrar no `schema.sql`, no `db._migrate()` e ter
    quem a escreva — a regra que o `decklists.event_tier` pagou em 2026-08-03.

    Aqui prova-se o segundo: apaga-se a coluna de uma base já feita (como a
    dele, criada antes de hoje) e o `db.init` tem de a repor.
    """
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    con.execute("DROP TABLE price_latest")
    con.execute("""CREATE TABLE price_latest (
        scryfall_id TEXT NOT NULL, source TEXT NOT NULL, finish TEXT NOT NULL,
        date TEXT NOT NULL, low REAL, trend REAL, avg30 REAL,
        available INTEGER, currency TEXT DEFAULT 'EUR',
        PRIMARY KEY (scryfall_id, source, finish))""")
    con.commit()
    db._migrate(con)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(price_latest)")}
    assert "receita" in cols, "o _migrate não repôs a coluna numa base antiga"


def caso_o_sql_do_preco_vive_num_sitio_so():
    """Ninguém volta a escrever `MIN(p.trend)` à mão.

    É a regra do `e_foil` e do `jogaveis()`: a primeira consulta que se
    esquecesse do modo voltava a pôr duas páginas a discordar sobre o mesmo
    dinheiro, sem um único erro.
    """
    raiz = Path(__file__).resolve().parents[1]
    ficheiros = ([raiz / "mtgvault" / f for f in ("loadout.py", "collection.py",
                                                  "wantlist.py", "scryfall.py")]
                 + [raiz / f for f in ("meta_coverage.py", "core_decks.py",
                                       "reservedlist.py", "refresh_collection.py",
                                       "import_owned.py")])
    maus = []
    for f in ficheiros:
        if not f.exists():
            continue
        for i, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            nu = linha.strip()
            # Um comentário ou um trecho entre crases é PROSA a explicar o que
            # deixou de se fazer — o que se procura é SQL a sério.
            if nu.startswith("#") or "precos.sql" in nu:
                continue
            for mau in ("MIN(p.trend)", "ORDER BY p.trend"):
                if mau in nu and f"`{mau}`" not in nu:
                    maus.append(f"{f.name}:{i}: {nu}")
    assert not maus, "preço escrito à mão fora do `precos.sql`:\n" + "\n".join(maus)


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
