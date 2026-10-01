"""NENHUM PEDIDO DO WEBAPP FICA PENDURADO (André, 2026-10-01).

Ele abriu a Deckboxes no telemóvel, pelo túnel, e a secção de um deck deu
*«não consegui ir buscar deckboxes/caixa-premodern-stiflenought.json: o
servidor respondeu 502»*. Do lado do PC o pedido não estava lento, estava **a
correr**, e ninguém lhe punha um fim:

  * o `/data/paginas/deckboxes/<parte>.json` **não cai** no servidor de
    ficheiros estáticos — o `_DADOS_DECKBOXES` apanha-o primeiro e GERA o
    payload inteiro a pedido. Medido nesse dia, em pedidos HTTP a sério contra
    a base dele: a secção do Modern, pedida a frio, **46 911 ms**; o índice
    **45 240 ms**; a Arrumação **37 249 ms**; o `metagame.html` **39 717 ms**.
    Não era «o Stiflenought»: era a primeira secção que fosse pedida;
  * o que custava os segundos era uma VARREDURA do catálogo — o
    `scryfall.impressoes_foil` caía num `name LIKE ? || ' // %'` que o
    `EXPLAIN QUERY PLAN` dava como `SCAN cards`, uma vez por carta que nunca
    saiu em foil (nos anos 90 são quase todas). Medido: **276 ms cada**, 550
    nomes, **57 s dos 74,5 s** do `loadout.report`;
  * e o Cloudflare desistia de esperar: 502, sem uma palavra a explicar.

O que este ficheiro tranca, e cada caso tem de CHUMBAR sem a funcionalidade
(ver `_chumba_prazo.py`):

  1. a consulta da frente de uma dupla face usa o ÍNDICE (`EXPLAIN QUERY PLAN`
     sem `SCAN`), e dá o MESMO que o LIKE dava;
  2. o catálogo responde UMA vez por nome num relatório (o `foil_cache` é
     partilhado pelas duas passagens do `lots()`);
  3. PONTA A PONTA, por HTTP: cada `.json` de página responde **200 em menos de
     2 s**, e a geração corre UMA vez para o índice e as partes todas;
  4. com a geração TRAVADA, o servidor responde um **503 explicado em
     português** (com `Retry-After`) em vez de pendurar — e o cálculo continua,
     por isso o pedido seguinte encontra os dados feitos;
  5. uma vista lenta **não tranca** outra (o lock da cache já não se segura
     durante o cálculo);
  6. um botão não fica pendurado atrás de uma escrita (o `ESCRITA` tem prazo);
  7. a ligação à base espera por quem está a escrever (`PRAGMA busy_timeout`).

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CFG = {
    "caixas": [
        {"slot": "stifle", "nome": "Stiflenought", "formato": "premodern",
         "fonte": "deck", "ref": "Stiflenought", "balde": "Premodern (geral)",
         "estado": "permanente", "prioridade": 1},
        {"slot": "dc", "nome": "Cloud (Duel Commander)",
         "formato": "duel-commander", "fonte": "deck", "ref": "Cloud",
         "balde": "Cloud", "estado": "permanente", "prioridade": 2},
    ],
    "regras_por_formato": [
        # O `prioridade_por: "pct"` é o que faz o `resolve_slots` correr o
        # SEGUNDO `lots()` (o `_pcts_da_coleccao`) — é esse que corria sem cache.
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "edicoes": "premodern", "estrita": True, "prioridade_por": "pct",
         "baldes": ["Colecção", "Premodern (geral)", "SPML"]},
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "acabamento": "foil"},
    ],
    "loadout": [], "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_colecao": {}, "spml_formatos": {},
}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG, ensure_ascii=False),
                               encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

from mtgvault import collection, db, loadout, scryfall     # noqa: E402

import deckboxes                                           # noqa: E402
import webapp                                              # noqa: E402

# Uma carta de DUPLA FACE no catálogo: é ela que faz a consulta de recurso
# correr. As listas escrevem só a frente («Fire»); o catálogo tem o nome
# inteiro («Fire // Ice»).
CATALOGO = [
    ("Island", "unh", "2004-11-19", "Land", '["nonfoil","foil"]'),
    ("Stifle", "scg", "2003-05-26", "Instant", '["nonfoil"]'),
    ("Phyrexian Dreadnought", "mir", "1996-10-08", "Creature", '["nonfoil"]'),
    ("Sol Ring", "unh", "2004-11-19", "Artifact", '["nonfoil","foil"]'),
    ("Fire // Ice", "apc", "2001-06-04", "Instant // Instant", '["nonfoil"]'),
    ("Wear // Tear", "dgm", "2013-05-03", "Instant // Instant",
     '["nonfoil","foil"]'),
]


def base(con=None):
    """A base de teste, com catálogo, duas listas e algumas cópias."""
    con = con or db.connect()
    db.init(con)
    for i, (nm, sc, rel, tl, fins) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards
               (scryfall_id, oracle_id, name, set_code, set_name,
                collector_number, lang, rarity, type_line, cmc, color_identity,
                finishes, released_at, legalities, digital, reprint, reserved,
                set_type)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'[]',?,?,'{}',0,0,0,'expansion')""",
            (f"sid-{i}", f"oid-{i}", nm, sc, sc.upper(), str(i + 1), tl, fins,
             rel))
    for i, (nm, sc, rel, tl, fins) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards
               (scryfall_id, oracle_id, name, set_code, set_name,
                collector_number, lang, rarity, type_line, cmc, color_identity,
                finishes, released_at, legalities, digital, reprint, reserved,
                set_type)
               VALUES (?,?,?,?,?,?,'pt','rare',?,1,'[]',?,?,'{}',0,0,0,'expansion')""",
            (f"sidpt-{i}", f"oid-{i}", nm, sc, sc.upper(), str(i + 1), tl,
             fins, rel))
    for nome, ref, cartas in (
            ("Stiflenought", "stifle",
             [("Stifle", 4), ("Phyrexian Dreadnought", 4), ("Fire", 2),
              ("Island", 10)]),
            ("Cloud", "dc", [("Sol Ring", 1), ("Wear", 1), ("Island", 8)])):
        cur = con.execute(
            "INSERT INTO decks (name, format) VALUES (?, ?)",
            (nome, "premodern" if ref == "stifle" else "duel-commander"))
        did = cur.lastrowid
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,'main')", (did, nm, q))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    bal = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    for sid, q, fin, lang in (("sidpt-1", 2, "nonfoil", "pt"),
                              ("sidpt-2", 1, "nonfoil", "pt"),
                              ("sid-3", 1, "foil", "en"),
                              ("sid-0", 4, "nonfoil", "en")):
        con.execute(
            """INSERT INTO copies (scryfall_id, quantity, finish, language,
               condition, purpose, sub_collection_id, created_at)
               VALUES (?,?,?,?,'NM','player',?, datetime('now'))""",
            (sid, q, fin, lang, bal))
    con.commit()
    return con


CON = base()
CON.close()

PORTO = 0
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    PORTO = s.getsockname()[1]
SRV = webapp.ThreadingHTTPServer(("127.0.0.1", PORTO), webapp.Handler)
threading.Thread(target=SRV.serve_forever, daemon=True).start()


def pede(caminho, prazo=30):
    """`(estado, segundos, corpo)` — nunca levanta por um código de erro."""
    t0 = time.monotonic()
    req = urllib.request.Request(f"http://127.0.0.1:{PORTO}{caminho}")
    try:
        with urllib.request.urlopen(req, timeout=prazo) as r:
            return r.status, time.monotonic() - t0, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, time.monotonic() - t0, e.read(), dict(e.headers)


def limpar():
    with webapp._CACHE_LOCK:
        webapp._CACHE.clear()
        webapp._EM_CURSO.clear()


# ---------------------------------------------------------------------------
# 1. A consulta de recurso usa o índice — e dá o mesmo
# ---------------------------------------------------------------------------
def caso_a_frente_de_dupla_face_nao_varre_o_catalogo():
    """`EXPLAIN QUERY PLAN` sem `SCAN`: era `SCAN cards`, 276 ms por nome.

    É o mesmo tipo de trava que o `precos.sql_impressao` tem desde 2026-09-25 —
    um plano de consulta que se degrada não dá erro nenhum: dá uma página que
    demora quarenta segundos e um 502 que não se explica.
    """
    with db.session() as con:
        q = (f"SELECT set_code FROM cards WHERE "
             f"{scryfall.frente_de_dupla_face()}")
        plano = [r["detail"] for r in
                 con.execute("EXPLAIN QUERY PLAN " + q,
                             scryfall.limites_dupla_face("Fire"))]
    assert plano, "o EXPLAIN nao devolveu nada"
    assert not any("SCAN" in p for p in plano), (
        f"a consulta da frente de dupla face VARRE o catalogo: {plano}")
    assert any("ix_cards_name" in p for p in plano), (
        f"nao usa o ix_cards_name: {plano}")
    print("ok  o plano da frente de dupla face usa o indice")


def caso_a_frente_de_dupla_face_da_o_mesmo_que_o_like():
    """O resultado tem de ser o mesmo — medido nos 550 nomes reais dele, 0
    diferenças; aqui trancado numa carta de dupla face a sério."""
    with db.session() as con:
        novo = [tuple(r) for r in con.execute(
            f"SELECT name, set_code FROM cards WHERE "
            f"{scryfall.frente_de_dupla_face()} ORDER BY name, lang",
            scryfall.limites_dupla_face("Fire"))]
        velho = [tuple(r) for r in con.execute(
            "SELECT name, set_code FROM cards WHERE name LIKE ? || ' // %' "
            "ORDER BY name, lang", ("Fire",))]
        assert novo == velho, f"{novo} != {velho}"
        assert novo, "a carta de dupla face nao foi encontrada"
        # E a função de cima continua a encontrar a foil pela frente.
        rows = scryfall.impressoes_foil(con, "Wear")
        assert rows, "o `Wear // Tear` existe em foil e nao foi encontrado"
        assert scryfall.conhecida(con, "Fire"), "o `Fire` devia ser conhecido"
        assert not scryfall.conhecida(con, "Carta Que Nao Existe")
    print(f"ok  a frente de dupla face da o mesmo ({len(novo)} linhas)")


# ---------------------------------------------------------------------------
# 2. O catálogo responde uma vez por nome
# ---------------------------------------------------------------------------
def caso_o_catalogo_responde_uma_vez_por_nome():
    """O `foil_cache` é partilhado pelas DUAS passagens do `lots()`.

    O `resolve_slots` corre o seu (`_pcts_da_coleccao`, para os grupos que
    ordenam por % completo) e o `allocate` corre outro. A primeira passagem não
    levava cache nenhuma: na base dele eram **1 683** consultas ao catálogo
    onde **946** bastam.
    """
    vistos = []
    orig = scryfall.impressoes_foil
    scryfall.impressoes_foil = lambda con, nm: (vistos.append(nm),
                                                orig(con, nm))[1]
    try:
        with db.session() as con:
            loadout.report(con)
    finally:
        scryfall.impressoes_foil = orig
    assert vistos, "o relatorio nao perguntou nada ao catalogo"
    repetidos = {nm for nm in vistos if vistos.count(nm) > 1}
    assert not repetidos, (
        f"o catalogo foi perguntado DUAS vezes sobre {sorted(repetidos)} — "
        f"{len(vistos)} chamadas para {len(set(vistos))} nomes: o foil_cache "
        f"nao esta a ser partilhado pelas duas passagens do lots()")
    print(f"ok  o catalogo responde uma vez por nome ({len(vistos)} chamadas, "
          f"{len(set(vistos))} nomes)")


# ---------------------------------------------------------------------------
# 3. Ponta a ponta: cada .json responde 200 em menos de 2 s
# ---------------------------------------------------------------------------
TECTO = 2.0


def caso_cada_json_de_pagina_responde_em_menos_de_dois_segundos():
    limpar()
    st, dt, corpo, _ = pede("/data/paginas/deckboxes.json")
    assert st == 200, f"o indice da Deckboxes deu {st}: {corpo[:300]}"
    partes = json.loads(corpo)["_partes"]
    assert partes, "o indice nao traz partes"
    lentos, maus = [], []
    for p in partes + ["nao-existe-esta"]:
        st, dt, corpo, _ = pede(f"/data/paginas/deckboxes/{p}.json")
        esperado = 404 if p == "nao-existe-esta" else 200
        if st != esperado:
            maus.append((p, st, corpo[:200]))
        if dt > TECTO:
            lentos.append((p, dt))
    st, dt, corpo, _ = pede("/data/paginas/arrumacao.json")
    if st != 200:
        maus.append(("arrumacao", st, corpo[:200]))
    for p in json.loads(corpo).get("_partes", []) if st == 200 else []:
        st2, dt2, c2, _ = pede(f"/data/paginas/arrumacao/{p}.json")
        if st2 != 200:
            maus.append((f"arrumacao/{p}", st2, c2[:200]))
        if dt2 > TECTO:
            lentos.append((f"arrumacao/{p}", dt2))
    assert not maus, f"secoes com estado errado: {maus}"
    assert not lentos, f"secoes acima de {TECTO} s: {lentos}"
    print(f"ok  {len(partes) + 1} secoes das Deckboxes + a Arrumacao, "
          f"todas 200 em menos de {TECTO:.0f} s")


def aquecido(limite=20):
    """Aquece até nada estar frio — é o que o servidor a sério faz no arranque.

    Precisa de mais do que uma passagem porque o PRÓPRIO `loadout.report`
    escreve o `data/arquetipos.json` (o `ultima = hoje` de cada arquétipo que
    vê), e esse ficheiro está no `_versao()` — de propósito: o `daily` também o
    escreve e o webapp tem de dar por isso. Consequência, que vale a pena ter
    escrita: o primeiro relatório do dia invalida-se a si próprio uma vez. É o
    aquecedor que paga isso, nunca um pedido dele. (É o mesmo ritmo que o
    CLAUDE.md descreve no `arquetipos.json` «modificado todas as manhãs».)
    """
    for _ in range(limite):
        if not webapp.aquecer():
            return
        time.sleep(0.2)
    raise AssertionError("nao conseguiu aquecer")


def _conta_relatorios(pedidos) -> int:
    n = [0]
    orig = loadout.report

    def conta(con, *a, **k):
        n[0] += 1
        return orig(con, *a, **k)
    loadout.report = conta
    try:
        for caminho in pedidos:
            st, _, corpo, _ = pede(caminho, prazo=60)
            assert st == 200, f"{caminho} deu {st}: {corpo[:200]}"
            if caminho.endswith(("deckboxes.json", "arrumacao.json")):
                raiz = caminho[:-5]
                for p in json.loads(corpo).get("_partes", []):
                    st2, _, c2, _ = pede(f"{raiz}/{p}.json", prazo=60)
                    assert st2 == 200, f"{raiz}/{p} deu {st2}: {c2[:200]}"
    finally:
        loadout.report = orig
    return n[0]


def caso_abrir_e_fechar_a_base_nao_atira_a_cache_fora():
    """O `vault.db-wal` VAZIO não pode mudar a versão (2026-10-01).

    O ficheiro aparece e desaparece ao ritmo de quem abre e fecha a base — o
    webapp, o `daily` das 03:30, as ordens do runner. A versão saltava entre
    `(mtime, 0)` e `(None, None)` sem uma única carta ter mudado, a cache era
    atirada fora, e o pedido seguinte voltava a pagar o relatório inteiro.
    """
    v_fora = webapp._versao()
    con = db.connect()
    db.init(con)
    try:
        wal = Path(str(db.DEFAULT_DB) + "-wal")
        v_dentro = webapp._versao()
        assert v_dentro == v_fora, (
            f"abrir a base mudou a versao (wal existe: {wal.exists()}, "
            f"tamanho {wal.stat().st_size if wal.exists() else '-'}) — a cache "
            f"e atirada fora a cada ligacao")
    finally:
        con.close()
    assert webapp._versao() == v_fora, "fechar a base mudou a versao"
    print("ok  abrir e fechar a base nao muda a versao da cache")


def caso_a_geracao_corre_uma_vez_para_o_indice_e_as_partes():
    """22 secções + a Arrumação não podem ser 23 relatórios — nem dois.

    São duas afirmações, e as duas importam:
      * com os dados AQUECIDOS e nada mudado, zero relatórios (a cache acerta);
      * a FRIO, **um** — a Deckboxes e a Arrumação partilham-no. Eram dois, e
        dois relatórios são duas respostas à mesma pergunta (é a decisão de
        2026-09-24 sobre o Início e a Deckboxes).
    """
    limpar()
    aquecido()
    pedidos = ["/data/paginas/deckboxes.json", "/data/paginas/arrumacao.json"]
    n = _conta_relatorios(pedidos)
    assert n == 0, (f"o relatorio correu {n} vezes com os dados aquecidos e "
                    f"nada mudado — nao devia correr nenhuma")
    # E agora a FRIO, com a versão igual (o `aquecido` já assentou o
    # `arquetipos.json`): esvazia-se a cache sem mexer em ficheiro nenhum.
    limpar()
    n = _conta_relatorios(pedidos)
    assert n == 1, (f"a frio, o relatorio correu {n} vezes para a Deckboxes e "
                    f"a Arrumacao — devia correr UM, partilhado pelas duas")
    print("ok  aquecido: 0 relatorios; a frio: 1 para as duas vistas e as "
          "partes todas")


# ---------------------------------------------------------------------------
# 4. Com a geração travada: 503 explicado, e o cálculo continua
# ---------------------------------------------------------------------------
def caso_a_geracao_travada_da_um_erro_explicado_em_vez_de_pendurar():
    """O caso do André, ao contrário: em vez de 100 s e um 502 mudo, um 503
    que diz o que está a acontecer — e DEPRESSA."""
    limpar()
    espera, orig = webapp.ESPERA_DADOS, loadout.report
    webapp.ESPERA_DADOS = 0.5
    travao = threading.Event()

    def devagar(con, *a, **k):
        travao.wait(20)
        return orig(con, *a, **k)
    loadout.report = devagar
    try:
        st, dt, corpo, cab = pede("/data/paginas/deckboxes/caixa-stifle.json")
        assert st == 503, f"devia ser 503 e foi {st} (corpo: {corpo[:200]})"
        assert dt < 5, f"respondeu em {dt:.1f} s — o tecto era 0,5 s"
        assert cab.get("Retry-After"), "falta o cabecalho Retry-After"
        d = json.loads(corpo)
        texto = d.get("erro", "")
        for palavra in ("gerar", "Tenta"):
            assert palavra in texto, f"a frase nao diz {palavra!r}: {texto!r}"
        assert "a_gerar" in d and d["a_gerar"], "nao diz O QUE esta a gerar"
        # E o CÁLCULO CONTINUA: solta-se o travão e o pedido seguinte encontra
        # os dados feitos, sem ninguem ter de recomecar nada.
        travao.set()
        webapp.ESPERA_DADOS = 30
        st2, dt2, corpo2, _ = pede(
            "/data/paginas/deckboxes/caixa-stifle.json")
        assert st2 == 200, f"o segundo pedido deu {st2}: {corpo2[:200]}"
        assert json.loads(corpo2), "o segundo pedido veio vazio"
    finally:
        travao.set()
        loadout.report = orig
        webapp.ESPERA_DADOS = espera
    print(f"ok  geracao travada -> 503 explicado em {dt * 1000:.0f} ms, e o "
          f"pedido seguinte da 200")


def caso_o_503_tambem_vale_para_a_arrumacao_e_para_o_metagame():
    """O tecto vive no `do_GET`/`do_POST` e não em cada rota: uma rota nova que
    se esquecesse dele voltava a pendurar um pedido."""
    limpar()
    espera, orig = webapp.ESPERA_DADOS, loadout.report
    webapp.ESPERA_DADOS = 0.5
    travao = threading.Event()
    loadout.report = lambda con, *a, **k: (travao.wait(20), orig(con, *a, **k))[1]
    try:
        for caminho in ("/data/paginas/arrumacao.json",
                        "/data/paginas/arrumacao/fase2.json"):
            st, dt, corpo, _ = pede(caminho)
            assert st == 503, f"{caminho} deu {st} (devia ser 503)"
            assert dt < 5, f"{caminho} respondeu em {dt:.1f} s"
    finally:
        travao.set()
        loadout.report = orig
        webapp.ESPERA_DADOS = espera
    print("ok  o 503 vale para a Arrumacao e para as partes dela")


# ---------------------------------------------------------------------------
# 5. Uma vista lenta não tranca outra
# ---------------------------------------------------------------------------
def caso_uma_vista_lenta_nao_tranca_outra():
    """O lock da cache já NÃO se segura durante o cálculo.

    Segurava: um `GET /metagame.html` ficava doze segundos atrás de um cálculo
    da Deckboxes que não tem nada a ver com ele.
    """
    limpar()
    # Primeiro aquece-se o metagame, para a comparação ser só sobre o LOCK.
    assert pede("/metagame.html")[0] == 200
    travao = threading.Event()
    orig = deckboxes.payload
    deckboxes.payload = lambda *a, **k: (travao.wait(20), orig(*a, **k))[1]
    resultado = {}

    def lento():
        resultado["deckboxes"] = pede("/data/paginas/deckboxes.json", prazo=40)
    try:
        t = threading.Thread(target=lento, daemon=True)
        t.start()
        time.sleep(1.0)       # o cálculo lento já está a correr
        st, dt, _, _ = pede("/metagame.html", prazo=10)
        assert st == 200, f"o metagame deu {st} com a Deckboxes a calcular"
        assert dt < TECTO, (
            f"o metagame esperou {dt:.1f} s por um calculo da Deckboxes que "
            f"nao lhe diz nada — o lock da cache esta a ser segurado durante "
            f"o calculo")
    finally:
        travao.set()
        deckboxes.payload = orig
        t.join(40)
    print(f"ok  uma vista lenta nao tranca outra (metagame em {dt * 1000:.0f} ms)")


# ---------------------------------------------------------------------------
# 6. Um botão não fica pendurado atrás de uma escrita
# ---------------------------------------------------------------------------
def caso_um_botao_nao_fica_pendurado_atras_de_uma_escrita():
    espera = webapp.ESPERA_ESCRITA
    webapp.ESPERA_ESCRITA = 0.5
    webapp.ESCRITA.acquire()
    try:
        t0 = time.monotonic()
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORTO}/api/vista",
            data=b'{"vista":"lista"}', method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                st, corpo, cab = r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            st, corpo, cab = e.code, e.read(), dict(e.headers)
        dt = time.monotonic() - t0
        assert st == 503, f"devia ser 503 e foi {st}: {corpo[:200]}"
        assert dt < 5, f"o botao esperou {dt:.1f} s pelo lock de escrita"
        assert "gravar" in json.loads(corpo).get("erro", ""), (
            f"a frase nao explica: {corpo[:200]}")
    finally:
        webapp.ESCRITA.release()
        webapp.ESPERA_ESCRITA = espera
    print(f"ok  um botao atras de uma escrita da 503 em {dt * 1000:.0f} ms")


# ---------------------------------------------------------------------------
# 7. A base espera por quem está a escrever
# ---------------------------------------------------------------------------
def caso_a_base_espera_por_quem_esta_a_escrever():
    """`PRAGMA busy_timeout`: o `vault.db` tem três escritores (o webapp, o
    `daily` das 03:30 e as ordens do runner). Sem isto, uma ordem a escrever
    durante seis segundos dava *«database is locked»* a uma página."""
    with db.session() as con:
        ms = con.execute("PRAGMA busy_timeout").fetchone()[0]
    assert ms >= 10000, (
        f"o busy_timeout e {ms} ms — uma escrita de alguns segundos ainda da "
        f"«database is locked» a uma pagina")
    assert ms < webapp.ESPERA_DADOS * 1000, (
        f"o busy_timeout ({ms} ms) e maior do que o tecto do pedido "
        f"({webapp.ESPERA_DADOS * 1000:.0f} ms): o pedido desistia sempre "
        f"antes de a base ter oportunidade de responder")
    print(f"ok  a base espera {ms} ms por quem escreve "
          f"(tecto do pedido {webapp.ESPERA_DADOS:.0f} s)")


CASOS = [caso_a_frente_de_dupla_face_nao_varre_o_catalogo,
         caso_a_frente_de_dupla_face_da_o_mesmo_que_o_like,
         caso_o_catalogo_responde_uma_vez_por_nome,
         caso_cada_json_de_pagina_responde_em_menos_de_dois_segundos,
         caso_abrir_e_fechar_a_base_nao_atira_a_cache_fora,
         caso_a_geracao_corre_uma_vez_para_o_indice_e_as_partes,
         caso_a_geracao_travada_da_um_erro_explicado_em_vez_de_pendurar,
         caso_o_503_tambem_vale_para_a_arrumacao_e_para_o_metagame,
         caso_uma_vista_lenta_nao_tranca_outra,
         caso_um_botao_nao_fica_pendurado_atras_de_uma_escrita,
         caso_a_base_espera_por_quem_esta_a_escrever]

if __name__ == "__main__":
    for c in CASOS:
        c()
    print(f"\n{len(CASOS)} casos ok")
