"""Reserved List: só vai para venda o que NÃO valorizou.

Ordem do André (2026-09-08, à letra): *"Cartas de RL só vão para venda se não
tiverem subido 5 % de valor nos últimos 3 meses."*

É a única regra da venda que olha para o TEMPO, e por isso é a única que pode
responder *"não sei"* — e o que aqui se tranca é sobretudo isso:

  1. subiu o mínimo → **fica**, com a percentagem e o motivo por que ia à venda;
  2. subiu menos → **vende-se**, como sempre;
  3. o vault não tem cotação que cubra a janela → **também não se vende**, e
     diz-se desde quando é que há dados. Uma RL é a decisão menos reversível de
     todas: dar "não subiu" como resposta a "não sei" era o defeito do
     `event_tier` outra vez, mas sobre dinheiro que não volta;
  4. o `price_history` só guarda MUDANÇAS (`prices.write_prices`), por isso o
     preço de há 90 dias é a ÚLTIMA cotação ATÉ esse dia — procurar uma linha
     datada dentro de uma janela estreita dava "não sei" a toda a carta estável,
     que é precisamente a que não subiu;
  5. os dois números (5 % e 90 dias) são config, não código;
  6. e nada sai da base: quem tira a cópia continua a ser o botão «vendida».

Não toca na rede.
"""
import json
import os
import re
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

from mtgvault import db, loadout, prices  # noqa: E402

HOJE = date.today()

# (nome, reserved). O `Sol Ring` está cá para provar o outro lado: a regra é só
# para a Reserved List, e uma carta normal continua a ir à venda sem histórico.
CATALOGO = [("Gilded Drake", 1), ("Null Rod", 1), ("Grim Monolith", 1),
            ("Tolarian Academy", 1), ("Sol Ring", 0)]

_ABERTAS = []


def cfg(**venda):
    """Reescreve o config e esquece a cache — os limiares têm de ser config."""
    from mtgvault import sources
    novo = json.loads(json.dumps(BASE_CFG))
    if venda:
        novo["venda"] = venda
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


def add(con, nm, q=1, sub="Colecção"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,'nonfoil','en',
                   'player',?)""", (sid, q, sub_id))
    con.commit()


def dia(n):
    """A data de há `n` dias, em ISO."""
    return (HOJE - timedelta(days=n)).isoformat()


def cota(con, nm, quando, valor):
    """Uma cotação num dia. Passa pelo `prices.write_prices` de propósito: é ele
    que decide o que entra no `price_history` (*só as mudanças*), e um teste que
    escrevesse a tabela à mão provava outra coisa que não o sistema."""
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    prices.write_prices(con, [(sid, "cardmarket", quando, "nonfoil",
                               valor, valor, None, None, "EUR")])


def slot_legacy(nome="Leg"):
    return {"slot": "leg", "nome": nome, "formato": "legacy", "fonte": "deck",
            "ref": nome, "prioridade": 1, "balde": "Colecção"}


def mundo(nm, antes=None, agora=100.0, quando=None, copias=6):
    """Uma carta com `copias` cópias que ninguém pede — o excedente do playset.

    Com uma cotação antiga (`antes`, no dia `quando`) e a de hoje (`agora`), que
    é a que a lista de venda mostra.
    """
    con = base()
    deck_vazio(con)
    add(con, nm, copias)
    if antes is not None:
        cota(con, nm, quando or dia(90), antes)
    cota(con, nm, HOJE.isoformat(), agora)
    return con


def deck_vazio(con):
    con.execute("INSERT INTO decks (name, format) VALUES ('Leg','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name = 'Leg'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Sol Ring', 1, 'main')", (did,))
    con.commit()


def linhas(rep, chave, nm):
    return [r for r in rep[chave] if r["nm"] == nm]


# ---------------------------------------------------------------------------
def caso_rl_que_subiu_5_por_cento_fica():
    """+5 % em 3 meses: a cópia sai da venda e vai para «RL a segurar».

    O limite é o do André, à letra — *"só vão para venda se não tiverem subido
    5 %"* —, por isso 5 % certos JÁ é subir: a comparação é `hoje >= antes ×
    1,05` e não `>`. Um limiar que deixa passar o próprio valor que o define é
    um limiar que ninguém consegue ler na página.
    """
    cfg()
    con = mundo("Gilded Drake", antes=100.0, agora=105.0)
    rep = loadout.report(con, [slot_legacy()])
    assert not linhas(rep, "venda_rl", "Gilded Drake"), rep["venda_rl"]
    seg = linhas(rep, "rl_segurar", "Gilded Drake")
    assert sum(r["q"] for r in seg) == 2, seg          # 6 cópias, playset 4
    assert loadout.RAZAO_RL_SEGURAR in seg[0]["reason"], seg[0]["reason"]
    # A janela é a que a carta dá: a primeira cotação é de há 90 dias, por isso
    # mediram-se 88 (o máximo são 90, e ficam 2 de folga). E o motivo diz-la —
    # "+5 %" sozinho não distingue uma carta parada de uma que subiu numa semana.
    assert "+5.0 % em 88 d" in seg[0]["reason"], seg[0]["reason"]
    # E diz-se porque é que ela ia à venda: "subiu 5%" é uma resposta, e sem a
    # pergunta ao lado não se percebe o que a regra impediu.
    assert seg[0]["porque_venderia"] == "excedente (mais de 4)", seg[0]
    assert rep["copias_rl_segurar"] == 2 and rep["total_rl_segurar"] > 0
    print("RL que subiu 5% fica: sai da venda, com a percentagem e o motivo "
          "por que lá ia")


def caso_rl_que_subiu_4_por_cento_vende_se():
    """+4 %: não chega ao limiar, e a cópia vai à venda como sempre."""
    cfg()
    con = mundo("Null Rod", antes=100.0, agora=104.0)
    rep = loadout.report(con, [slot_legacy()])
    vrl = linhas(rep, "venda_rl", "Null Rod")
    assert sum(r["q"] for r in vrl) == 2, vrl
    assert vrl[0]["reason"] == "excedente (mais de 4)", vrl[0]["reason"]
    assert not rep["rl_segurar"] and not rep["rl_sem_historico"], rep["rl_segurar"]
    print("RL que subiu 4% vende-se — o motivo continua a ser o de sempre")

    # E uma que DESCEU, com mais razão ainda.
    con2 = mundo("Null Rod", antes=100.0, agora=80.0)
    rep2 = loadout.report(con2, [slot_legacy()])
    assert sum(r["q"] for r in linhas(rep2, "venda_rl", "Null Rod")) == 2
    print("e uma que desceu também")


def caso_sem_historico_nao_se_vende_e_diz_desde_quando():
    """Sem cotação que cubra a janela, a cópia FICA — e diz desde quando há dados.

    É o caso da base a sério em 2026-09-08: o `price_history` do vault começou em
    2026-08-10, ou seja há 29 dias, e a janela são 90. Nenhuma RL passa o teste,
    e a lista de Reserved List fica vazia até a janela encher. É a resposta certa
    — a alternativa era vender por não se saber.
    """
    cfg()
    con = mundo("Grim Monolith", antes=None, agora=100.0)   # só a de hoje
    rep = loadout.report(con, [slot_legacy()])
    assert not rep["venda_rl"], rep["venda_rl"]
    sem = linhas(rep, "rl_sem_historico", "Grim Monolith")
    assert sum(r["q"] for r in sem) == 2, sem
    assert loadout.RAZAO_RL_SEM_HISTORICO in sem[0]["reason"], sem[0]["reason"]
    assert HOJE.isoformat() in sem[0]["reason"], sem[0]["reason"]
    assert rep["copias_rl_sem_historico"] == 2
    assert rep["copias_rl_retidas"] == 2, rep["copias_rl_retidas"]
    assert rep["total_rl_retido"] == rep["total_rl_sem_historico"]
    print("sem histórico que cubra a janela a RL não se vende, e a linha diz "
          "desde quando é que há preços")

    # E a regra é SÓ para a Reserved List: uma carta normal sem histórico
    # nenhum continua a ir à venda pela regra do playset.
    con2 = base()
    deck_vazio(con2)
    add(con2, "Sol Ring", 6)
    cota(con2, "Sol Ring", HOJE.isoformat(), 3.0)
    rep2 = loadout.report(con2, [slot_legacy()])
    assert sum(r["q"] for r in linhas(rep2, "venda", "Sol Ring")) == 2
    assert not rep2["rl_sem_historico"], rep2["rl_sem_historico"]
    print("a regra é só para a RL: uma carta normal sem histórico vende-se na mesma")


def caso_o_preco_de_ha_90_dias_e_a_ultima_cotacao_ate_esse_dia():
    """O `price_history` só guarda MUDANÇAS: sem linha nova, o preço manteve-se.

    Uma carta cotada há 200 dias e nunca mais mexida TEM preço de há 90 dias —
    é o mesmo. Procurar só uma linha datada dentro da janela dava "não sei" a
    toda a carta estável, que é justamente a que não subiu: a regra ficava a
    segurar exactamente aquilo que ela existe para deixar vender.
    """
    cfg()
    con = mundo("Tolarian Academy", antes=100.0, quando=dia(200), agora=101.0)
    rep = loadout.report(con, [slot_legacy()])
    assert sum(r["q"] for r in linhas(rep, "venda_rl", "Tolarian Academy")) == 2
    assert not rep["rl_sem_historico"], rep["rl_sem_historico"]
    print("uma cotação de há 200 dias serve de preço de há 90 — 'sem linha' "
          "quer dizer 'manteve-se'")

    # E um histórico mais curto do que o máximo já NÃO é "não sei": desde
    # 2026-09-08 a janela encolhe para o que a carta dá (85 → mede-se a 83), e
    # quem não chega ao mínimo é que fica sem resposta. Ver o caso a seguir.
    con2 = mundo("Tolarian Academy", antes=100.0, quando=dia(85), agora=130.0)
    rep2 = loadout.report(con2, [slot_legacy()])
    assert linhas(rep2, "rl_segurar", "Tolarian Academy"), rep2["rl_segurar"]
    assert "em 83 d" in linhas(rep2, "rl_segurar", "Tolarian Academy")[0]["reason"]
    print("uma cotação de há 85 dias mede-se numa janela de 83")


def caso_a_janela_cresce_com_o_historico():
    """*"Podemos começar já com 25 e vamos vendo como avança o histórico."*

    O `rl_janela_dias` deixou de ser A janela e passou a ser o MÁXIMO dela. A
    janela efectiva é o histórico que o vault tem daquela carta (menos dois dias
    de folga, para o dia-alvo cair depois da primeira cotação), até ao máximo. É
    o que faz a regra decidir HOJE com os 29 dias que o `price_history` tem, e
    estar nos 90 em Novembro sem ninguém lhe tocar no config.
    """
    cfg()
    for hist, esperado in ((30, 28), (60, 58), (95, 90)):
        con = mundo("Gilded Drake", antes=100.0, quando=dia(hist), agora=200.0)
        rep = loadout.report(con, [slot_legacy()])
        seg = linhas(rep, "rl_segurar", "Gilded Drake")
        assert seg, (hist, rep["venda_rl"], rep["rl_sem_historico"])
        assert seg[0]["rl_janela"] == esperado, (hist, seg[0]["rl_janela"])
        assert f"em {esperado} d" in seg[0]["reason"], seg[0]["reason"]
    print("a janela efectiva cresce com o histórico e pára no máximo do config")


def caso_menos_de_25_dias_de_historico_e_nao_sei():
    """Abaixo do `rl_janela_minima_dias` não se decide — nem para vender.

    É o mesmo argumento do "sem histórico": uma RL é a venda menos reversível de
    todas, e uma semana de preços não diz se uma carta subiu. O que muda é a
    fronteira, que passou a ser um número dele (25) em vez do máximo (90).
    """
    cfg()
    con = mundo("Grim Monolith", antes=100.0, quando=dia(20), agora=100.0)
    rep = loadout.report(con, [slot_legacy()])
    sem = linhas(rep, "rl_sem_historico", "Grim Monolith")
    assert sem and not rep["venda_rl"], rep["venda_rl"]
    assert "18 d, precisa de 25" in sem[0]["reason"], sem[0]["reason"]
    # Mais cinco dias de histórico e a mesma carta já se decide.
    con2 = mundo("Grim Monolith", antes=100.0, quando=dia(28), agora=100.0)
    rep2 = loadout.report(con2, [slot_legacy()])
    assert linhas(rep2, "venda_rl", "Grim Monolith"), rep2["rl_sem_historico"]
    assert not rep2["rl_sem_historico"]
    # E o mínimo é config, como tudo o resto.
    cfg(rl_janela_minima_dias=15)
    rep3 = loadout.report(con, [slot_legacy()])
    assert linhas(rep3, "venda_rl", "Grim Monolith"), rep3["rl_sem_historico"]
    print("menos de 25 dias de histórico é 'não sei', e a fronteira é config")


def caso_o_limiar_e_proporcional_a_janela():
    """Exigir 5 % a 27 dias era vender o que a regra dos 90 dias seguraria.

    Os 5 % dele são *"nos últimos 3 meses"*. Medidos numa janela de 25 dias, os
    mesmos 5 % são ~18 %/90 d — um filtro muito mais apertado, que deixava passar
    para a venda exactamente as cartas que estão a valorizar depressa. Por isso o
    limiar acompanha a janela: `5 % × janela / máximo`, ~1,4 % a 25 dias.
    """
    cfg()
    # +2 % em 25 dias: ao ritmo de 90 dias são +7,2 %, acima dos 5 %.
    con = mundo("Gilded Drake", antes=100.0, quando=dia(27), agora=102.0)
    rep = loadout.report(con, [slot_legacy()])
    seg = linhas(rep, "rl_segurar", "Gilded Drake")
    assert seg, rep["venda_rl"]
    assert seg[0]["rl_janela"] == 25 and seg[0]["rl_subida"] == 2.0, seg[0]
    assert seg[0]["rl_limiar"] == 1.39, seg[0]["rl_limiar"]
    assert "≈ +7.2 %/90 d" in seg[0]["reason"], seg[0]["reason"]
    # E o que sobe DEVAGAR continua a vender-se: +1 % em 25 dias são +3,6 %/90 d.
    con2 = mundo("Null Rod", antes=100.0, quando=dia(27), agora=101.0)
    rep2 = loadout.report(con2, [slot_legacy()])
    assert linhas(rep2, "venda_rl", "Null Rod"), rep2["rl_segurar"]
    print("o limiar acompanha a janela: +2% em 25 dias segura, +1% vende")

    # A ALTERNATIVA, que é dele e não minha: os 5 % à letra em qualquer janela.
    cfg(rl_limiar_fixo=True)
    rep3 = loadout.report(con, [slot_legacy()])
    assert linhas(rep3, "venda_rl", "Gilded Drake"), rep3["rl_segurar"]
    assert loadout.rl_limiar_fixo()
    print("e com `rl_limiar_fixo` os 5% valem à letra, seja qual for a janela")


def caso_os_dois_numeros_sao_do_config():
    """5 % e 90 dias são uma linha de config, não uma linha de código."""
    con = mundo("Gilded Drake", antes=100.0, agora=104.0)
    cfg()
    rep = loadout.report(con, [slot_legacy()])
    assert linhas(rep, "venda_rl", "Gilded Drake"), "a 5% de mínimo, +4% vende"

    cfg(rl_subida_minima_pct=3, rl_janela_dias=90)
    rep = loadout.report(con, [slot_legacy()])
    assert linhas(rep, "rl_segurar", "Gilded Drake"), "a 3% de mínimo, +4% fica"
    assert loadout.rl_subida_minima() == 3
    print("baixar o `rl_subida_minima_pct` para 3 segura o que a 5% se vendia")

    # E o MÁXIMO da janela também: com 40 dias de máximo, a mesma carta com 90
    # dias de histórico passa a ser medida em 40 — e o limiar proporcional passa
    # a ser sobre 40, não sobre 90.
    con2 = mundo("Gilded Drake", antes=100.0, quando=dia(90), agora=104.0)
    cfg(rl_subida_minima_pct=5, rl_janela_dias=40)
    rep2 = loadout.report(con2, [slot_legacy()])
    assert loadout.rl_janela_dias() == 40
    v = linhas(rep2, "venda_rl", "Gilded Drake")
    assert v and v[0]["rl_janela"] == 40, (v, rep2["rl_segurar"])
    # E o limiar é o do máximo, não o dos 90: a janela cheia paga os 5 % inteiros.
    assert v[0]["rl_limiar"] == 5.0, v[0]
    print("e o máximo da janela também: a 40 dias mede-se em 40, com os 5% "
          "inteiros")


def caso_nada_sai_da_base_e_nada_se_conta_duas_vezes():
    """A lista continua a ser uma SUGESTÃO, e cada cópia aparece numa só saída."""
    cfg()
    con = base()
    deck_vazio(con)
    add(con, "Gilded Drake", 6)
    add(con, "Null Rod", 6)
    cota(con, "Gilded Drake", dia(90), 100.0)
    cota(con, "Gilded Drake", HOJE.isoformat(), 150.0)      # +50%: fica
    cota(con, "Null Rod", dia(90), 100.0)
    cota(con, "Null Rod", HOJE.isoformat(), 100.0)          # não mexeu: vende
    antes = con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"]
    rep = loadout.report(con, [slot_legacy()])
    saidas = [r for k in ("venda", "venda_rl", "rl_segurar", "rl_sem_historico",
                          "guardar", "retidos", "reservadas") for r in rep[k]]
    por_carta: dict = {}
    for r in saidas:
        por_carta[r["nm"]] = por_carta.get(r["nm"], 0) + r["q"]
    assert por_carta == {"Gilded Drake": 2, "Null Rod": 2}, por_carta
    assert rep["copias_rl_segurar"] == 2 and rep["copias_rl"] == 2
    depois = con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"]
    assert antes == depois == 12, (antes, depois)
    print("cada cópia numa saída só, e o relatório não tira nada da base")


def caso_a_poda_diaria_nao_pode_matar_a_regra():
    """O `daily._prune_prices` guarda a Reserved List o tempo que a regra precisa.

    A poda apagava TUDO o que tivesse mais de 30 dias, todos os dias. Com a
    janela a 90, nunca haveria um preço de há três meses para comparar: a regra
    respondia *"não sei"* a tudo, **para sempre**, a lista de RL ficava vazia e
    nenhum passo do `daily.py` dava erro. É o padrão do `event_tier` — um passo
    que corre sem erro e produz uma página vazia —, desta vez sobre a decisão da
    venda que vale mais dinheiro.

    O que se guarda mais tempo é só a RL, e é por isso que isto cabe: na base a
    sério a RL são 2,5 % das linhas do `price_history`.
    """
    import daily
    cfg(rl_janela_dias=90, rl_tolerancia_dias=10)
    con = base()
    # A mesma cotação de há 95 dias — dentro do que a janela precisa (90 + 10 de
    # tolerância + 7 de folga = 107) e fora dos 30 da poda geral — para uma RL e
    # para uma carta normal.
    for nm in ("Gilded Drake", "Sol Ring"):
        cota(con, nm, dia(95), 10.0)
        cota(con, nm, dia(5), 11.0)
    detalhe = daily._prune_prices(con, 30)
    ficaram = {r["nm"]: r["n"] for r in con.execute(
        """SELECT c.name nm, COUNT(*) n FROM price_history h
             JOIN catalog.cards c ON c.scryfall_id = h.scryfall_id
            WHERE h.date < date('now', '-30 days') GROUP BY c.name""")}
    assert ficaram == {"Gilded Drake": 1}, ficaram
    assert "Reserved List guarda-se 107d" in detalhe, detalhe
    # E o resto continua a ser podado aos 30 dias, como sempre.
    assert con.execute("SELECT COUNT(*) n FROM price_history").fetchone()["n"] == 3
    print("a poda diária guarda a RL 107 dias e o resto 30 — sem isto a regra "
          "nunca teria um preço de há 3 meses")

    # E a JANELA do config é que manda: com 20 dias, guardam-se 37 e a mesma
    # cotação de há 95 dias já não sobrevive — nem sendo Reserved List.
    cfg(rl_janela_dias=20)
    con2 = base()
    cota(con2, "Gilded Drake", dia(95), 10.0)
    assert "guarda-se 37d" in daily._prune_prices(con2, 30), "a folga acompanha"
    assert con2.execute("SELECT COUNT(*) n FROM price_history").fetchone()["n"] == 0
    print("e a janela do config é que manda quanto tempo se guarda")


def _abas_desenhadas(pagina):
    """`{aba: HTML}` — o que o browser mostraria. `None` sem `node`."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        return None
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_a_pagina_separa_o_que_se_vende_do_que_se_segura():
    """A aba Vender DESENHADA: dois blocos novos, e nada de RL na venda sem passar.

    A `deckboxes.html` é JSON + JavaScript: um bloco que rebente só aparece ao
    clicar na aba, em branco e sem erro no gerador. Por isso lê-se o HTML que o
    JavaScript desenhou, e não o ficheiro.
    """
    import deckboxes
    cfg()
    con = base()
    deck_vazio(con)
    add(con, "Gilded Drake", 6)
    add(con, "Null Rod", 6)
    cota(con, "Gilded Drake", dia(90), 100.0)
    cota(con, "Gilded Drake", HOJE.isoformat(), 200.0)      # +100%: segura-se
    cota(con, "Null Rod", dia(90), 100.0)
    cota(con, "Null Rod", HOJE.isoformat(), 100.0)          # parado: vende-se
    rep = loadout.report(con, [slot_legacy()])
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    deckboxes.build(con, out, rep=rep)
    d = json.loads(re.search(
        r'<script id="dados" type="application/json">(.*?)</script>',
        out.read_text(encoding="utf-8"), re.S).group(1).replace("<\\/", "</"))
    assert d["rl_regra"]["copias"] == 2 and d["rl_regra"]["pct"] == 5
    assert d["venda"]["rl_segurar"]["copias"] == 2
    assert d["venda"]["rl"]["copias"] == 2

    abas = _abas_desenhadas(out)
    if abas is None:
        print("página: sem `node`, saltado")
        return
    v = abas["vender"]
    assert "RL a segurar" in v, v[:600]
    antes_dos_blocos, depois = v.split("RL a segurar", 1)
    assert "Gilded Drake" not in antes_dos_blocos, \
        "a RL que valorizou não pode aparecer na lista de venda"
    assert "Gilded Drake" in depois and "+100.0 %" in depois, depois[:800]
    assert "Null Rod" in antes_dos_blocos, "a que não subiu vende-se na mesma"
    print("a aba Vender desenha o bloco «RL a segurar» e não põe lá a RL que "
          "valorizou")


def run():
    for fn in (caso_rl_que_subiu_5_por_cento_fica,
               caso_rl_que_subiu_4_por_cento_vende_se,
               caso_sem_historico_nao_se_vende_e_diz_desde_quando,
               caso_o_preco_de_ha_90_dias_e_a_ultima_cotacao_ate_esse_dia,
               caso_a_janela_cresce_com_o_historico,
               caso_menos_de_25_dias_de_historico_e_nao_sei,
               caso_o_limiar_e_proporcional_a_janela,
               caso_os_dois_numeros_sao_do_config,
               caso_nada_sai_da_base_e_nada_se_conta_duas_vezes,
               caso_a_poda_diaria_nao_pode_matar_a_regra,
               caso_a_pagina_separa_o_que_se_vende_do_que_se_segura):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
