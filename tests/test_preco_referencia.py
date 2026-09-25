"""O PREÇO DE REFERÊNCIA É O DA IMPRESSÃO DELE (André, 2026-09-25).

À letra: *"o que tinha pedido era alterar o preço REFERÊNCIA para Market Price
ou Best Deal, ao invés de MÍNIMO"*.

Havia DOIS mínimos e só um tinha sido tratado a 25/09:

  1. o mínimo entre **OFERTAS** — o `precos.oferta_utilizavel` (já tem casos em
     `test_preco_modo.py`);
  2. o mínimo entre **IMPRESSÕES** — o `loadout.card_price` faz `MIN` sobre
     todas as impressões do mesmo NOME. Para o que FALTA está certo (compra-se
     a mais barata); para uma cópia que ele TEM é avaliar a Underground Sea de
     Revised pela reimpressão mais barata que exista.

O que aqui se tranca, por ordem de importância:

  1. **Trocar de FONTE não pode mandar uma RL para a venda** — o gémeo do caso
     do modo, e a mesma coisa irreversível. Duas defesas: o carimbo
     (`precos.fonte_desde` → `regua_desde`) e a recusa de comparar o preço de
     hoje de uma fonte com o histórico de outra.
  2. A regra dos 5 % compara **a mesma impressão** nas duas pontas. Com o preço
     de hoje a ser o do Revised e o de há 90 dias a ser o mínimo entre
     impressões, a percentagem não era de carta nenhuma.
  3. O preço de uma cópia é o da impressão dela; o mínimo entre impressões só
     como último recurso, e **dito** (`origem`).
  4. A cadeia de fontes é *"a primeira que a cote"*, **nunca um MIN entre
     fontes** — isso era somar duas escalas de preço.

Não toca na rede.
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

from mtgvault import collection, db, loadout, precos, prices  # noqa: E402

HOJE = date.today()
_ABERTAS = []

# Duas IMPRESSÕES da mesma carta: a antiga (cara, a que ele tem) e a reimpressão
# barata. É o par que distingue as duas perguntas — quanto vale a dele, quanto
# custa comprar uma.
CATALOGO = [
    # (id, nome, edição, reserved)
    ("sea-3ed", "Underground Sea", "3ed", 1),
    ("sea-ced", "Underground Sea", "ced", 1),
    ("bolt-lea", "Lightning Bolt", "lea", 0),
    ("bolt-m10", "Lightning Bolt", "m10", 0),
    ("ring-usg", "Sol Ring", "usg", 0),
]


def cfg(**blocos):
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
    for i, (sid, nm, sete, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Land',0,'',?,?,?,0,?)""",
            (sid, f"or-{nm}", nm, sete, sete.upper(), str(i),
             json.dumps(["nonfoil", "foil"]),
             "1994-04-01" if sete in ("3ed", "lea") else "2010-07-16",
             json.dumps({"legacy": "legal", "commander": "legal"}), rl))
    con.commit()
    return con


def add(con, sid, q=1, sub="Colecção", finish="nonfoil"):
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,'en','player',?)""",
                (sid, q, finish, sub_id))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def dia(n):
    return (HOJE - timedelta(days=n)).isoformat()


def cota(con, sid, quando, low, trend, fonte="cardmarket",
         receita=precos.RECEITA_UNICA, finish="nonfoil"):
    prices.write_prices(con, [(sid, fonte, quando, finish, low, trend,
                               None, None, "EUR", receita)])


def slot_legacy():
    return {"slot": "leg", "nome": "Leg", "formato": "legacy", "fonte": "deck",
            "ref": "Leg", "prioridade": 1, "balde": "Colecção"}


def deck_vazio(con):
    con.execute("INSERT INTO decks (name, format) VALUES ('Leg','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name = 'Leg'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Sol Ring', 1, 'main')", (did,))
    con.commit()


def venda_de(con, nm):
    rep = loadout.report(con, [slot_legacy()])
    for saida in ("venda", "venda_rl", "rl_segurar", "rl_sem_historico",
                  "guardar", "reservadas", "retidos"):
        if any(l["nm"] == nm for l in rep.get(saida) or []):
            return saida, [l for l in rep[saida] if l["nm"] == nm]
    return None, []


# ---------------------------------------------------------------------------
# 1. A REGRA DA RESERVED LIST — o que é irreversível
# ---------------------------------------------------------------------------
def caso_trocar_de_fonte_nao_manda_nenhuma_rl_para_a_venda():
    """O gémeo do caso do modo, para a FONTE (o ponto 4 da ordem).

    Cenário: 200 dias de histórico no Cardmarket em que a carta NÃO subiu — a
    regra mandá-la-ia vender. Hoje muda-se a fonte principal para o CardTrader,
    que só tem o preço de hoje. Sem o carimbo (`precos.fonte_desde`), a regra
    compara a mediana das ofertas de hoje com o Trend de há 200 dias e decide
    com uma percentagem que não mediu nada. A resposta tem de ser
    `rl_sem_historico` — *"não sei"*, a terceira resposta desde 2026-09-08.
    """
    con = base()
    deck_vazio(con)
    add(con, "sea-3ed", q=6)                     # 6 > playset: 2 vão à venda
    for n in range(200, -1, -10):                # estável: 100 € o tempo todo
        cota(con, "sea-3ed", dia(n), 90.0, 100.0)
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    saida, _ = venda_de(con, "Underground Sea")
    assert saida == "venda_rl", f"sem troca de fonte devia vender-se: {saida}"

    # E agora a troca, pelo caminho a sério (é ele que carimba a data).
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    precos.gravar_fonte("cardtrader", ["cardmarket"], path=CFG_PATH,
                        hoje=HOJE.isoformat())
    cota(con, "sea-3ed", HOJE.isoformat(), 120.0, 160.0, fonte="cardtrader",
         receita=precos.RECEITA_CT_OFERTAS)
    assert precos.fontes() == ("cardtrader", "cardmarket")
    assert precos.regua_desde() == HOJE.isoformat()
    saida, linhas = venda_de(con, "Underground Sea")
    assert saida == "rl_sem_historico", f"trocar de fonte vendeu a RL: {saida}"
    assert "não sei" in linhas[0]["reason"] or "histórico" in linhas[0]["reason"]


def caso_o_preco_de_hoje_e_o_historico_tem_de_ser_da_mesma_fonte():
    """Uma cópia cujo preço de hoje veio da fonte de RECURSO não se avalia.

    O CardTrader é a fonte principal e não tem esta impressão à venda; o preço
    de hoje vem do Cardmarket. O histórico é do CardTrader. Comparar os dois é
    medir a diferença entre dois mercados e chamar-lhe subida — e é com essa
    percentagem que se decide vender uma carta que não se volta a imprimir.
    """
    con = base()
    deck_vazio(con)
    add(con, "sea-3ed", q=6)
    # A fonte principal (CardTrader) tem histórico de OUTRA impressão, não desta.
    for n in range(200, -1, -10):
        cota(con, "sea-ced", dia(n), 40.0, 50.0, fonte="cardtrader",
             receita=precos.RECEITA_CT_OFERTAS)
    cota(con, "sea-3ed", HOJE.isoformat(), 90.0, 100.0)      # só no Cardmarket
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "fonte_recurso": ["cardmarket"]})
    saida, linhas = venda_de(con, "Underground Sea")
    assert saida == "rl_sem_historico", f"comparou dois mercados: {saida}"
    assert "cardmarket" in linhas[0]["reason"], linhas[0]["reason"]


def caso_a_regra_da_rl_compara_a_impressao_dela_nas_duas_pontas():
    """As duas pontas da percentagem têm de ser a MESMA carta.

    A impressão dele (3ed) SOBE — 122 € há 90 dias, 140 € hoje (+14,8 %), acima
    do limiar: segura-se. A reimpressão barata (ced) DESCE, 30 € → 10 €. Pela
    conta antiga as duas pontas eram o mínimo entre impressões, ou seja a ced
    dos dois lados: *"não subiu"*, e a carta de Revised que valorizou ia à venda
    por causa do preço de outra carta. As duas pontas medem a 3ed.
    """
    con = base()
    deck_vazio(con)
    add(con, "sea-3ed", q=6)
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    for n in range(200, -1, -10):
        cota(con, "sea-3ed", dia(n), 90.0, 100.0 + (200 - n) * 0.2)
        cota(con, "sea-ced", dia(n), 20.0, 30.0 - (200 - n) * 0.1)
    saida, linhas = venda_de(con, "Underground Sea")
    assert saida == "rl_segurar", f"a impressão dele subiu: {saida}"
    # A percentagem da 3ED (122 -> 140), não a da mistura das duas impressões.
    assert "+14.8" in linhas[0]["reason"], linhas[0]["reason"]


# ---------------------------------------------------------------------------
# 2. O PREÇO DE REFERÊNCIA
# ---------------------------------------------------------------------------
def caso_o_preco_de_uma_copia_e_o_da_impressao_dela():
    """O caso que a ordem nomeia, e o que chumba sem esta tarefa.

    Ele tem a Underground Sea de **Revised** (900 €). Existe uma reimpressão a
    30 €. O `card_price` — que é *"quanto custa comprar uma"* — continua a dar
    30 €, e está certo. O preço de REFERÊNCIA da cópia dele é 900 €.
    """
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    cota(con, "sea-3ed", HOJE.isoformat(), 800.0, 900.0)
    cota(con, "sea-ced", HOJE.isoformat(), 25.0, 30.0)
    add(con, "sea-3ed")

    compra, _ = loadout.card_price(con, "Underground Sea", "nonfoil")
    assert compra == 30.0, f"o preço de COMPRA é o mínimo entre impressões: {compra}"

    p = loadout.preco_da_copia(con, "sea-3ed", "nonfoil", "Underground Sea")
    assert p["unit"] == 900.0, f"a cópia dele vale a impressão dela: {p}"
    assert p["origem"] == precos.ORIGEM_IMPRESSAO
    assert p["fonte"] == "cardmarket"


def caso_sem_cotacao_da_impressao_cai_no_minimo_e_diz_que_e_estimativa():
    """Último recurso, e DITO.

    A impressão dela não está cotada em fonte nenhuma. O número que se mostra é
    o de outra carta impressa — é uma estimativa, e uma estimativa que se soma
    calada a preços a sério é a mentira que a `origem` existe para impedir.
    """
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    cota(con, "bolt-m10", HOJE.isoformat(), 1.0, 2.0)        # só a reimpressão
    p = loadout.preco_da_copia(con, "bolt-lea", "nonfoil", "Lightning Bolt")
    assert p["unit"] == 2.0, p
    assert p["origem"] == precos.ORIGEM_MIN_IMPRESSOES, p
    assert "estimativa" in precos.ROTULOS_ORIGEM[p["origem"]]


def caso_sem_preco_em_fonte_nenhuma_nao_e_zero_euros():
    """*"Sem preço"* e *"vale 0 €"* não são a mesma coisa. Uma cópia de 900 € que
    a fonte não cota tirava-se do total sem uma linha a dizê-lo."""
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    add(con, "ring-usg")
    p = loadout.preco_da_copia(con, "ring-usg", "nonfoil", "Sol Ring")
    assert p["unit"] is None, p
    assert p["origem"] == precos.ORIGEM_SEM_PRECO, p
    val = collection.valor_da_coleccao(con)
    assert val["sem_preco"] == 1, val["sem_preco"]
    assert val["total"]["trend"] == 0.0


# ---------------------------------------------------------------------------
# 3. A CADEIA DE FONTES
# ---------------------------------------------------------------------------
def caso_a_cadeia_usa_a_principal_e_cai_na_de_recurso():
    """*"Pergunta ao CardTrader; se ele não a tem, pergunta ao Cardmarket, e diz
    que foi de lá."* É o ponto 3 da ordem: 36 % das cópias dele não estão no
    marketplace, e um terço da colecção sem preço era pior do que o mínimo que
    isto veio corrigir."""
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "fonte_recurso": ["cardmarket"]})
    cota(con, "sea-3ed", HOJE.isoformat(), 700.0, 1000.0, fonte="cardtrader",
         receita=precos.RECEITA_CT_OFERTAS)
    cota(con, "sea-3ed", HOJE.isoformat(), 800.0, 900.0)     # cardmarket
    cota(con, "bolt-lea", HOJE.isoformat(), 400.0, 500.0)    # só no cardmarket
    add(con, "sea-3ed")
    add(con, "bolt-lea")

    a = loadout.preco_da_copia(con, "sea-3ed", "nonfoil", "Underground Sea")
    assert (a["unit"], a["fonte"]) == (1000.0, "cardtrader"), a
    b = loadout.preco_da_copia(con, "bolt-lea", "nonfoil", "Lightning Bolt")
    assert (b["unit"], b["fonte"]) == (500.0, "cardmarket"), b

    val = collection.valor_da_coleccao(con)
    assert val["por_fonte"] == {"cardtrader": 1, "cardmarket": 1}, val["por_fonte"]
    assert val["total"]["trend"] == 1500.0


def caso_a_cadeia_nao_e_um_minimo_entre_fontes():
    """A cadeia é uma ORDEM, não um `MIN`.

    O CardTrader pede 1 000 € pela mesma impressão que o Cardmarket cota a
    900 €. Um `MIN` ficava com os 900 — e no dia seguinte, noutra carta, com os
    do CardTrader: o total passava a ser a soma de duas escalas de preço, que é
    exactamente o defeito que a `receita` existe para impedir.
    """
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "fonte_recurso": ["cardmarket"]})
    cota(con, "sea-3ed", HOJE.isoformat(), 700.0, 1000.0, fonte="cardtrader",
         receita=precos.RECEITA_CT_OFERTAS)
    cota(con, "sea-3ed", HOJE.isoformat(), 800.0, 900.0)
    p = loadout.preco_da_copia(con, "sea-3ed", "nonfoil", "Underground Sea")
    assert p["unit"] == 1000.0, f"a cadeia escolheu o mínimo entre fontes: {p}"


def caso_uma_fonte_com_gralha_nao_entra_em_sql():
    """O nome da fonte entra na consulta como LITERAL (a ordem da cadeia é um
    `CASE`, e um `?` não ordena). Vem do config, que ele edita à mão."""
    con = base()
    cfg(precos={"modo": "market", "fonte": "card'; DROP TABLE copies;--"})
    assert precos.fontes() == ("cardmarket",), precos.fontes()
    # E pelo caminho de escrita a recusa é explícita.
    try:
        precos.gravar_fonte("mau nome!", path=CFG_PATH)
    except ValueError:
        pass
    else:
        raise AssertionError("uma fonte inválida foi aceite")
    assert con.execute("SELECT COUNT(*) c FROM copies").fetchone()["c"] == 0


def caso_trocar_para_a_mesma_cadeia_nao_reinicia_a_janela():
    """Um clique sem efeito não pode custar-lhe 25 dias de regra."""
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "fonte_recurso": ["cardmarket"], "fonte_desde": "2026-01-01"})
    r = precos.gravar_fonte("cardtrader", ["cardmarket"], path=CFG_PATH,
                            hoje=HOJE.isoformat())
    assert r["mudou"] is False, r
    assert r["desde"] == "2026-01-01", r


# ---------------------------------------------------------------------------
# 4. O QUE ALIMENTA A CADEIA
# ---------------------------------------------------------------------------
def caso_as_edicoes_do_cardtrader_saem_da_coleccao():
    """Com o `precos.fonte` em `cardtrader`, um `CARDTRADER_SETS` esquecido era o
    site inteiro a cair na fonte de recurso sem um único erro."""
    con = base()
    add(con, "sea-3ed")
    add(con, "bolt-m10")
    assert prices.edicoes_da_coleccao(con) == ["3ed", "m10"]


def caso_o_historico_do_marketplace_sem_consumidor_e_podado():
    """O CardTrader escreveu 53 113 linhas de histórico na primeira corrida (27
    MB) e só 1 025 eram de cartas dele ou da Reserved List. As outras não
    alimentam página nenhuma — o que a lista de compras usa é o `price_latest`,
    que fica inteiro. A trinta dias isso eram centenas de MB num ficheiro que é
    descarregado e republicado INTEIRO a cada corrida."""
    import daily
    con = base()
    add(con, "bolt-m10")                     # tem esta
    for sid in ("bolt-m10", "bolt-lea", "sea-3ed", "ring-usg"):
        cota(con, sid, HOJE.isoformat(), 1.0, 2.0, fonte="cardtrader",
             receita=precos.RECEITA_CT_OFERTAS)
    cota(con, "ring-usg", HOJE.isoformat(), 1.0, 2.0)     # cardmarket: fica
    n = daily._prune_marketplace(con)
    ficam = {r["scryfall_id"] for r in con.execute(
        "SELECT scryfall_id FROM price_history WHERE receita = ?",
        (precos.RECEITA_CT_OFERTAS,))}
    assert n == 2, n
    assert ficam == {"bolt-m10", "sea-3ed"}, ficam   # a dele e as duas RL
    assert con.execute(
        "SELECT COUNT(*) c FROM price_latest WHERE receita = ?",
        (precos.RECEITA_CT_OFERTAS,)).fetchone()["c"] == 4, "o preço de hoje fica"
    assert con.execute(
        "SELECT COUNT(*) c FROM price_history WHERE source = 'cardmarket'"
    ).fetchone()["c"] == 1, "a poda não pode tocar no price guide"


def caso_o_preco_da_cadeia_entra_pela_chave_e_ve_a_escrita():
    """A cadeia é uma subconsulta CORRELACIONADA, não uma tabela por cima da
    `price_latest` inteira.

    O `card_price` é chamado milhares de vezes por relatório: a primeira versão
    (tabela derivada com `ROW_NUMBER`) varria as 86 480 linhas das duas fontes a
    cada chamada e punha o relatório em dezenas de minutos. Aqui exige-se o
    plano: o SQLite tem de entrar na `price_latest` pela chave primária e **não
    pode haver SCAN** dela. (Materializá-la numa temporária resolvia o tempo e
    partia quinze ficheiros de teste: o esquema `temp` entra no
    `PRAGMA database_list`, onde eles apanham o catálogo pelo índice 1.)

    E, sem tabela intermédia, não há cache que possa responder com um preço de
    antes — o que se lê é o que está na base. Vale a pena trancar as duas
    coisas juntas: a segunda é a razão por que a primeira não se resolve com uma
    cache qualquer.
    """
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "fonte_recurso": ["cardmarket"]})
    cota(con, "sea-3ed", HOJE.isoformat(), 800.0, 900.0)
    assert loadout.card_price(con, "Underground Sea")[0] == 900.0

    cota(con, "sea-3ed", HOJE.isoformat(), 800.0, 950.0)     # o mercado mexeu
    assert loadout.card_price(con, "Underground Sea")[0] == 950.0, "preço velho"

    cfg(precos={"modo": "best", "fonte": "cardtrader",
                "fonte_recurso": ["cardmarket"]})
    assert loadout.card_price(con, "Underground Sea")[0] == 800.0, "modo velho"

    expr = precos.sql_impressao()
    plano = [r["detail"] for r in con.execute(
        f"EXPLAIN QUERY PLAN SELECT MIN({expr}) FROM cards c "
        f"JOIN {precos.sql_acabamentos(('nonfoil',))} f WHERE c.name = ?",
        ("nonfoil", "Underground Sea"))]
    maus = [d for d in plano if "SCAN" in d and "price_latest" in d]
    assert not maus, f"varre a price_latest inteira: {plano}"


def caso_a_pergunta_da_cadeia_vive_num_sitio_so():
    """A primeira consulta que voltasse a escrever `p.source = ?` à mão punha
    uma página a dizer o preço do Cardmarket e a do lado o do CardTrader, sem um
    único erro. É a regra do `e_foil`, do `jogaveis()` e do `precos.sql()`."""
    raiz = Path(__file__).resolve().parents[1]
    ficheiros = ([raiz / "mtgvault" / f for f in ("loadout.py", "collection.py",
                                                  "wantlist.py")]
                 + [raiz / f for f in ("meta_coverage.py", "reservedlist.py",
                                       "caixarl.py")])
    maus = []
    for f in ficheiros:
        if not f.exists():
            continue
        for i, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            nu = linha.strip()
            if nu.startswith("#") or nu.startswith("*") or "precos." in nu:
                continue
            if "MIN(low)" in nu or "MIN(trend)" in nu:
                maus.append(f"{f.name}:{i}: {nu}")
    assert not maus, "preço por impressão escrito à mão:\n" + "\n".join(maus)


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
