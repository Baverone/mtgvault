"""O FECHO DAS TRÊS DECISÕES DE 04/10/2026 (André, ao fim do dia).

  1. **A TRAVA DA VENDA DEIXA DE TER DATA.** Era `venda.congelado_ate:
     "2026-10-12"` e levantava-se SOZINHA no dia 12. Ele decidiu que não: a venda
     destranca só quando ELE disser, porque o estado das cartas está por avaliar.
     Passou a `venda.congelada` (booleano). Nada do comportamento mudou — o
     `venda.exportar`, o passo `venda-export` do daily e os dois endpoints de
     escrita do 8771 continuam a levantar `fases.VendaCongelada` e o `webapp`
     continua a traduzi-la num 409 em português. O que mudou é a CONDIÇÃO.
  2. **A RL QUE SÓ JOGA EM DUEL COMMANDER FICA VENDÁVEL** — e já ficava, por
     acidente de configuração (`venda.reservar_rl_formatos` nunca teve o
     duel-commander). O que faltava era a RAZÃO ESCRITA, e é o que se tranca
     aqui: *"«RL que jogue» são as que ELE joga nos decks dele, não as que o
     formato joga"*.
  3. **O WHIPFLARE: NONFOIL AGORA, FOIL DEPOIS.** A excepção ao `acabamento:
     foil` do grupo `spml` passou de PENDENTE a **DECIDIDA e aplicada**, marcada
     `provisoria: "trocar por foil"`, e a troca ficou VIGIADA (`watched` kind
     `preco_impressao`, alvo 10,00 €).

MEDIDO na base dele a 2026-10-04 (os números vão no relatório, não nas
asserções — estas trancam a REGRA, que é o que tem de continuar verdade):

    os 7 nomes da RL no decklist 22794 ..... 0 de 7 (nenhum entra)
    dos 7, na lista de candidatas .......... 6 (9 cópias / 640,98 €)
    o 7.º (Metalworker) ................... protegido pela R4: está no Cloud cEDH
    os 6 sem lista meta nenhuma ............ 11 cópias / 470,04 €
    candidatas, com a reserva a 20 % ....... 611 cópias / 17 888,30 €
    foil >= 10x o nonfoil, nas 34 compras .. 1 (só o Whipflare, 96,2x)

Não toca na rede nem na `vault.db` a sério. Fixa `MTGVAULT_HOME` **e**
`MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

# Os 7 nomes de RL que SÓ aparecem em listas de duel-commander (apurado e
# conferido na base a 04/10: cada um deles é `reserved = 1` e nenhum aparece
# numa lista de outro formato).
SETE_RL_DC = ["Memory Jar", "Metalworker", "Rofellos, Llanowar Emissary",
              "Time Spiral", "Treachery", "Yavimaya Hollow",
              "Yawgmoth's Bargain"]
DECKLIST_DO_CLOUD = 22794

REGRAS = [
    {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
     "dedicado": True, "lingua": "en", "acabamento": "foil"},
]
CAIXA = {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
         "fonte": "escolhido", "ref": "modern", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1}
URGENTE_DECIDIDO = {
    "carta": "Whipflare", "caixa": "modern", "prioridade": "alta",
    "ate": "2026-10-09", "porque": "RC Ghent 9-11/10 e ele nao tem nenhum",
    "material_pendente": {
        "estado": "DECIDIDA", "aplicado": True, "decidido_em": "2026-10-04",
        "provisoria": "trocar por foil",
        "decidido_por": "compra o nonfoil para jogar e troca quando baixar",
        "regra_do_grupo": "foil (grupo `spml`)",
        "sugerido_entretanto": "nonfoil",
        "porque": "o foil so existe em NPH a 20,20 EUR contra 0,21 do nonfoil",
        "precos": {"foil": 20.2, "nonfoil": 0.21}},
}
BASE_CFG = {
    "regras_colecao": {}, "decks_vigiados": [], "baldes_coleccao": ["Colecção"],
    "regras_por_formato": REGRAS, "caixas": [CAIXA],
    "venda": {"mostrar": True, "congelada": True},
    "reserva": {"janela_dias": 30, "staples_premodern_pct": 90},
    "listas_escolhidas": {"modern": {
        "nome": "Modern — UW Oswald", "padrao": True, "formato": "modern",
        "cards": [["main", "Thoughtcast", 4],
                  ["side", "Whipflare", 1]]}},
    "compras_urgentes": [URGENTE_DECIDIDO],
    "basicas": {"isentas_de_regras": True, "edicao": "Unhinged"},
}
CFG_PATH = _TMP / "cfg.json"


def escrever_cfg(cfg: dict) -> None:
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    from mtgvault import sources
    sources._CFG_CACHE.clear()


escrever_cfg(BASE_CFG)
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import db, fases, loadout, venda, watchlist  # noqa: E402

CFG_REAL = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))

CATALOGO = [
    ("Whipflare", "nph", "2011-05-13", ["nonfoil", "foil"],
     {"foil": 20.2, "nonfoil": 0.35}),
    ("Whipflare", "c14", "2014-11-07", ["nonfoil"], {"nonfoil": 0.21}),
    ("Thoughtcast", "mrd", "2003-10-02", ["nonfoil", "foil"],
     {"foil": 3.0, "nonfoil": 1.0}),
    ("Dark Ritual", "ice", "1995-06-01", ["nonfoil"], {"nonfoil": 0.5}),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fins, precos) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, set_type)
               VALUES (?,?,?,?,?,?,'en','rare','Artifact',1,'',?,?,?,0,0,'expansion')""",
            (f"id-{i}", f"or-{nm}-{sc}", nm, sc, sc.upper(), str(100 + i),
             json.dumps(fins), rel,
             json.dumps({"modern": "legal"})))
        for f, p in precos.items():
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source,"
                        " finish, date, trend, low, receita) VALUES (?,'cardmarket',"
                        "?, '2026-10-04', ?, ?, 'unico')", (f"id-{i}", f, p, p))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", sc=None):
    q_sql = ("SELECT scryfall_id FROM catalog.cards WHERE name = ?"
             + (" AND set_code = ?" if sc else "") + " ORDER BY released_at LIMIT 1")
    sid = con.execute(q_sql, (nm, sc) if sc else (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,'en','player',?)""",
                (sid, q, finish, sub))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def falta_de(res, nm):
    return [m for m in res["slots"][0]["missing"] if m["nm"] == nm]


# ===========================================================================
# 1) A TRAVA DA VENDA, SEM DATA
# ===========================================================================
def caso_o_config_a_serio_trava_a_venda_sem_a_data_de_12_10():
    """No config DELE: a trava está posta e a data já não está no bloco `venda`."""
    v = CFG_REAL["venda"]
    assert v.get("congelada") is True, \
        f"a venda tem de estar travada à mão, está {v.get('congelada')!r}"
    assert "congelado_ate" not in v, \
        ("a data saiu do bloco `venda` — se voltar, volta a levantar-se sozinha "
         f"a 12/10: {v.get('congelado_ate')!r}")
    # A data NÃO se apagou: ficou no histórico, com a razão e a data da troca.
    h = v.get("_congelado_ate_historico") or {}
    assert h.get("congelado_ate") == "2026-10-12", h
    assert h.get("substituida_em") == "2026-10-04", h
    assert "estado das cartas" in (h.get("porque_saiu") or "").lower(), h
    assert h.get("_texto_original"), "o texto explicativo antigo é memória do projecto"
    # E o `mostrar` NÃO se mexeu: são duas chaves diferentes.
    assert v.get("mostrar") is False, "ele não pediu para voltar a ver a venda"
    # A chave nova explica-se, e diz o comando que a abre.
    assert "--congelada off" in (v.get("_congelada") or ""), v.get("_congelada")
    print("config: venda.congelada = true, a data no historico, mostrar intacto")


def caso_a_venda_continua_travada_e_o_409_aparece_sem_a_data():
    """O comportamento não mudou: recusa-se, com `VendaCongelada`, e a frase diz
    como se abre. A data de hoje é irrelevante — era ela que decidia."""
    con = base()
    add(con, "Dark Ritual", 6)
    escrever_cfg(BASE_CFG)
    for dia in ("2026-10-01", "2026-10-12", "2027-06-01"):
        assert fases.venda_congelada(hoje=dia) is True, \
            f"a {dia} tinha de continuar travada (a trava é manual)"
    pasta = Path(tempfile.mkdtemp())
    try:
        venda.exportar(con, pasta=pasta)
    except fases.VendaCongelada as e:
        assert isinstance(e, ValueError), "o do_POST traduz um ValueError em 409"
        assert "CONGELADA" in str(e), str(e)
        assert "--congelada off" in str(e), "a recusa tem de dizer como se abre"
        assert "2026-10-12" not in str(e), \
            "a frase não pode prometer um dia: já não há data"
    else:
        raise AssertionError("a exportação correu com a venda travada")
    assert not list(pasta.glob("*")), "uma recusa não deixa ficheiro atrás dela"
    print("trava: recusa-se em qualquer data e a frase diz o comando que a abre")


def caso_levantar_o_interruptor_destranca_e_baixar_volta_a_travar():
    con = base()
    add(con, "Dark Ritual", 6)
    cfg = json.loads(json.dumps(BASE_CFG))

    cfg["venda"]["congelada"] = False
    escrever_cfg(cfg)
    assert fases.congelada() is False
    fases.exige_descongelado()                        # não levanta
    pasta = Path(tempfile.mkdtemp())
    venda.exportar(con, pasta=pasta)
    assert list(pasta.glob("*")), "destrancada, a saída escreve os ficheiros"

    cfg["venda"]["congelada"] = True
    escrever_cfg(cfg)
    assert fases.congelada() is True
    pasta2 = Path(tempfile.mkdtemp())
    try:
        venda.exportar(con, pasta=pasta2)
    except fases.VendaCongelada:
        pass
    else:
        raise AssertionError("baixar o interruptor tem de voltar a travar")
    assert not list(pasta2.glob("*"))
    escrever_cfg(BASE_CFG)
    print("interruptor: off destranca e escreve, on volta a travar")


def caso_o_cli_destranca_e_escreve_pelo_configio():
    """O caminho que ele usa. E escreve-se pelo `configio`, que preserva a forma
    do ficheiro — um `json.dump(indent=2)` aqui matava a revisão (`ac1f776`)."""
    from mtgvault import configio
    alvo = Path(tempfile.mkdtemp()) / "colecao_config.json"
    configio.escrever(json.loads(json.dumps(BASE_CFG)), alvo)
    antes = alvo.read_text(encoding="utf-8")

    r = fases.gravar_congelada(False, path=alvo)
    assert r["antes"] is True and r["congelada"] is False, r
    assert configio.ler(alvo)["venda"]["congelada"] is False
    # Repor é simétrico, e o ficheiro não cresce nem se reformata.
    fases.gravar_congelada(True, path=alvo)
    assert alvo.read_text(encoding="utf-8") == antes, \
        "ida e volta tem de devolver o ficheiro igual byte a byte"
    escrever_cfg(BASE_CFG)
    print("cli: gravar_congelada nos dois sentidos, sem estragar o ficheiro")


# ===========================================================================
# 2) A RL QUE SÓ JOGA EM DUEL COMMANDER
# ===========================================================================
def caso_a_razao_do_duel_commander_esta_escrita_no_config():
    """Estava a funcionar por ACIDENTE de configuração; passa a estar escrito."""
    v = CFG_REAL["venda"]
    assert v["reservar_rl_formatos"] == ["legacy"], \
        ("o duel-commander NÃO pode entrar aqui: punha o vault a segurar RL por "
         f"causa de decks que ele não joga — está {v['reservar_rl_formatos']}")
    porque = v.get("_reservar_rl_formatos") or ""
    assert porque, "a razão tem de estar escrita ao lado da chave"
    for pedaco in ("duel-commander", "decks dele", "22794"):
        assert pedaco in porque.lower(), f"falta «{pedaco}» na razão: {porque[:160]}"
    assert "Metalworker" in porque, \
        "a excepção medida (protegido pela R4, está no Cloud cEDH) tem de ficar dita"
    print("config: a razao do duel-commander escrita, com os numeros medidos")


def caso_nenhum_dos_sete_entra_na_lista_do_deck_de_duel_commander():
    """A premissa da decisão, conferida contra a lista que a caixa usa MESMO.

    A lista do Cloud está fixada em `listas_escolhidas["duel-commander"]` e vem
    do decklist **22794** (Liwei Luo). Se um dos 7 entrasse nela, a decisão
    estava errada e a carta não podia ir para a venda.
    """
    esc = CFG_REAL["listas_escolhidas"]["duel-commander"]
    assert esc.get("fonte_decklist") == DECKLIST_DO_CLOUD, \
        f"a lista tem de ser a do decklist {DECKLIST_DO_CLOUD}: {esc.get('fonte_decklist')}"
    nomes = {c[1] for c in esc["cards"] if len(c) >= 2}
    assert len(nomes) == 80, f"a lista do Cloud tem 80 nomes, tem {len(nomes)}"
    dentro = sorted(n for n in SETE_RL_DC if n in nomes)
    assert not dentro, \
        ("ESTES entram na lista do deck dele e NÃO podem ir para a venda: "
         f"{dentro}")
    print(f"os {len(SETE_RL_DC)} nomes de RL de duel-commander: nenhum entra nas "
          f"{len(nomes)} cartas do deck dele")


# ===========================================================================
# 3) O WHIPFLARE: NONFOIL AGORA, FOIL DEPOIS
# ===========================================================================
def caso_a_excepcao_do_whipflare_esta_decidida_e_nao_pendente():
    """No config a sério: DECIDIDA, aplicada, e marcada provisória."""
    urg = [x for x in CFG_REAL["compras_urgentes"] if x["carta"] == "Whipflare"]
    assert urg, "o Whipflare tem de continuar na lista de compras urgentes"
    mp = urg[0]["material_pendente"]
    assert mp["aplicado"] is True, \
        "com o nonfoil na mão a lista de compras fica satisfeita: `aplicado` é true"
    assert "PENDENTE" not in mp["estado"].upper(), mp["estado"]
    assert mp["estado"] == "DECIDIDA", mp["estado"]
    assert mp["decidido_em"] == "2026-10-04", mp
    assert mp.get("provisoria") == "trocar por foil", mp.get("provisoria")
    assert "nonfoil" in (mp.get("decidido_por") or "").lower(), mp.get("decidido_por")
    # Os dois preços ficam à vista, e a ressalva da régua também.
    assert mp["precos"]["foil"] == 20.2 and mp["precos"]["nonfoil"] == 0.21, mp
    assert "cardtrader" in mp["precos"]["fonte"], \
        "a ressalva de que a régua em vigor não cota esta carta tem de ficar"
    # E a troca está vigiada, não depende de ele se lembrar.
    assert "preco_impressao" in (mp.get("trocar_por_foil") or ""), mp
    print("config: excepcao DECIDIDA e aplicada, marcada provisoria, com vigia")


def caso_o_whipflare_nonfoil_satisfaz_a_lista_de_compras():
    """Aplicada a excepção, uma cópia nonfoil FECHA o slot — e a linha de compra
    deixa de dizer «pendente»."""
    escrever_cfg(BASE_CFG)
    con = base()
    res = loadout.report(con)
    m = falta_de(res, "Whipflare")
    assert m, "sem nenhuma cópia, continua a faltar (ainda não a comprou)"
    assert m[0]["comprar"] == 1, m[0]["comprar"]
    # A linha pede nonfoil e JÁ NÃO diz que está pendente.
    assert "nonfoil" in m[0]["req_compra"], m[0]["req_compra"]
    assert loadout.RAZAO_EXCEPCAO_PENDENTE not in m[0]["req_compra"], \
        f"a decisão está tomada: {m[0]['req_compra']}"
    assert m[0]["urgencia"]["pendente"] is False, m[0]["urgencia"]
    # ... e o preço é o do acabamento que a linha pede.
    assert m[0]["unit"] == 0.21, m[0]["unit"]

    # COM O NONFOIL NA MÃO: o slot fecha e a carta sai das faltas.
    add(con, "Whipflare", 1, "nonfoil", sc="c14")
    res2 = loadout.report(con)
    assert not falta_de(res2, "Whipflare"), \
        "aplicada a excepção, o nonfoil satisfaz a lista de compras"
    assert not any(x["nm"] == "Whipflare" for x in res2["slots"][0]["subs"]), \
        "e deixa de ser substituto: passou a servir"
    print("compras: o nonfoil fecha o slot e a linha nao diz 'pendente'")


def caso_a_vigia_do_foil_esta_inscrita_e_corre():
    """A vigia reaproveita a `watched`, não vai à rede, e avisa no alvo.

    Três coisas, e as três são o que a torna útil: inscreve-se (o CHECK aceita o
    kind), corre e devolve o preço, e **dispara o aviso quando desce ao alvo**.
    """
    con = base()
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name='Whipflare'"
                      " AND set_code='nph'").fetchone()["scryfall_id"]
    r = watchlist.vigiar_preco(con, "Whipflare", "nph", "foil", 10.0, "modern",
                               fonte="cardmarket", porque="troca quando baixar")
    assert r["scryfall_id"] == sid, r
    assert r["rotulo"].startswith("Whipflare (NPH"), r["rotulo"]

    # 1. Está INSCRITA, e no mapa dos verificadores (senão o `check_all` falha
    #    alto a dizer que está inscrita e não corre).
    w = con.execute("SELECT * FROM watched WHERE id = ?", (r["id"],)).fetchone()
    assert w["kind"] == "preco_impressao", w["kind"]
    assert w["key"] == watchlist.chave_preco(sid, "foil"), w["key"]
    assert "preco_impressao" in watchlist.VERIFICADORES

    # 2. CORRE: o preço de hoje, da fonte da inscrição, e NÃO avisa a 20,20 €.
    x = watchlist.check_preco_impressao(con, r["id"])
    assert x["found"] is True and x["changed"] is True, x
    assert x["preco"] == 20.2 and x["alvo"] == 10.0, x
    assert x["avisar"] is False, "a 20,20 € ainda não é para trocar"
    # Correr outra vez não inventa mudança nenhuma.
    assert watchlist.check_preco_impressao(con, r["id"])["changed"] is False

    # 3. DESCE AO ALVO -> avisa. É a razão de ser da vigia.
    con.execute("UPDATE price_latest SET trend = 9.5, low = 9.5 WHERE "
                "scryfall_id = ? AND finish = 'foil'", (sid,))
    con.commit()
    y = watchlist.check_preco_impressao(con, r["id"])
    assert y["avisar"] is True, y
    assert y["preco"] == 9.5 and y["preco_antes"] == 20.2, y

    # 4. Uma fonte que NÃO cota a impressão não dá 0 € nem avisa — diz-se.
    #    (É o caso real: a cadeia em vigor é só o cardtrader, que não a cota.)
    con.execute("UPDATE watched SET notes = ? WHERE id = ?",
                (json.dumps({"alvo_eur": 10.0, "fonte": "cardtrader"}), r["id"]))
    con.commit()
    z = watchlist.check_preco_impressao(con, r["id"])
    assert z["preco"] is None and z["avisar"] is False, z
    assert "não cota" in z["error"], z["error"]
    print("vigia: inscrita, corre, avisa a 9,50 EUR e nao inventa preco sem fonte")


def caso_a_vigia_nao_se_inscreve_sobre_uma_impressao_que_nao_existe():
    """Uma vigia sobre uma impressão que não existe nunca avisaria: levanta."""
    con = base()
    try:
        watchlist.vigiar_preco(con, "Whipflare", "c14", "foil", 10.0, "modern")
    except LookupError as e:
        assert "foil" in str(e) and "C14" in str(e).upper(), str(e)
    else:
        raise AssertionError("o C14 não existe em foil: tinha de levantar")
    print("vigia: nao se inscreve sobre uma impressao que nao existe")


def caso_o_kind_novo_entra_no_check_e_nao_perde_as_vigias_antigas():
    """O CHECK da `watched` é um só, e a lista dos kinds vive num sítio.

    O `_migrate` reconstrói a tabela quando FALTA algum kind — e não «quando
    falta o último que eu acrescentei», que era o que estava: numa base que já
    tivesse o `mtgtop8_archetype`, o `preco_impressao` ficava fora do CHECK e o
    `watchlist.add` dava `IntegrityError` outra vez.
    """
    assert "preco_impressao" in db.KINDS_VIGIA, db.KINDS_VIGIA
    esquema = (RAIZ / "mtgvault" / "schema.sql").read_text(encoding="utf-8")
    for k in db.KINDS_VIGIA:
        assert f"'{k}'" in esquema, \
            f"o kind {k} está no db.KINDS_VIGIA e não no schema.sql"

    # A migração acrescenta o kind novo e não perde uma única vigia nem um único
    # snapshot. Mede-se com DOIS pontos de partida, e o segundo é o que importa:
    #
    #   (a) a tabela de antes de 2026-10-04 (nem `mtgtop8_archetype` tem);
    #   (b) **a tabela como a base DELE está hoje** — já com o
    #       `mtgtop8_archetype`, que entrou nesta mesma noite, e sem o
    #       `preco_impressao`.
    #
    # Só o (b) apanha o defeito de a condição ser «falta o último kind que eu
    # acrescentei»: nessa base a reconstrução não corria, o kind novo ficava
    # fora do CHECK e o `watchlist.add` dava `IntegrityError`. O teste começou
    # com só o (a) e PASSAVA com o defeito posto — foi o `_chumba` que o
    # mostrou.
    ANTIGA = "('mtgo_player','moxfield')"
    HOJE = "('mtgo_player','moxfield','archetype','mtgtop8_archetype')"
    for rotulo, kinds in (("antes de 04/10", ANTIGA), ("a base dele hoje", HOJE)):
        con = base()
        con.execute("DROP TABLE watched_snapshots")
        con.execute("DROP TABLE watched")
        con.executescript(f"""
            CREATE TABLE watched (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL CHECK (kind IN {kinds}),
                key TEXT NOT NULL, label TEXT NOT NULL, format TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, last_checked TEXT,
                last_hash TEXT, notes TEXT, UNIQUE (kind, key, format));
            CREATE TABLE watched_snapshots (
                id INTEGER PRIMARY KEY,
                watched_id INTEGER NOT NULL REFERENCES watched(id) ON DELETE CASCADE,
                taken_at TEXT NOT NULL, list_hash TEXT NOT NULL, source_url TEXT,
                cards TEXT NOT NULL, UNIQUE (watched_id, list_hash));
            INSERT INTO watched (kind, key, label, format)
                VALUES ('mtgo_player', 'Luffy', 'Luffy — Pauper', 'pauper');
            INSERT INTO watched_snapshots (watched_id, taken_at, list_hash, cards)
                VALUES (1, '2026-09-01', 'h1', '[["main","Island",4]]');
        """)
        con.commit()
        db._migrate(con)
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name='watched'"
                          ).fetchone()["sql"]
        assert "preco_impressao" in sql, f"[{rotulo}] {sql}"
        assert con.execute("SELECT COUNT(*) c FROM watched").fetchone()["c"] == 1, \
            f"[{rotulo}] a migração não pode perder vigias"
        assert con.execute("SELECT COUNT(*) c FROM watched_snapshots"
                           ).fetchone()["c"] == 1, \
            f"[{rotulo}] nem snapshots: a `watched_snapshots` tem ON DELETE CASCADE"
        assert not list(con.execute("PRAGMA foreign_key_check")), rotulo
        # E o kind novo entra MESMO: é o `add` que falhava com IntegrityError.
        wid = watchlist.add(con, "preco_impressao", "sid|foil", "x", "modern")
        assert wid, rotulo
        # É idempotente.
        db._migrate(con)
        assert con.execute("SELECT COUNT(*) c FROM watched").fetchone()["c"] == 2
    print("watched: o kind novo entra no CHECK nas duas bases, sem perder nada")


# ===========================================================================
def main():
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for f in casos:
        try:
            f()
            print(f"  ok   {f.__name__}")
        except Exception as e:                       # noqa: BLE001
            falhas += 1
            print(f"  FAIL {f.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                            # noqa: BLE001, S110
            pass
    print(f"\n{len(casos) - falhas}/{len(casos)} casos ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
