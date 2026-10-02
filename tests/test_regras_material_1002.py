"""TRÊS REGRAS DE MATERIAL NOVAS E AS DUAS EXCEPÇÕES DAS BÁSICAS
(André, 2026-10-02, à letra).

  · *"Duel Commander, so ingles, e so Foil (se nao houver, pode ser non-foil)"*
  · *"pauper so ingles tambem Foil (se nao houver, pode ser non-foil)"*
  · *"o premodern e apenas portugues, non-foil, nas edicoes indicadas"*
  · *"para as basicas, nos decks, tens que permitir tirar foto com mais cartas
    e nao apenas 4"*
  · *"depois indico quantas basicas tenho de cada"*
  · *"em todos os decks, as basicas sao todas de Unhinged"*

Repara que o SENTIDO não é o mesmo nos dois primeiros: no Duel Commander isto
AFROUXA o acabamento (de `foil` obrigatório para `prefere_foil`) e APERTA a
língua; no Premodern APERTA o acabamento, que nunca tinha tido chave nenhuma.

O que aqui se tranca:

  1. uma cópia **PT** não é alocada a uma caixa de Duel Commander nem de Pauper;
  2. uma cópia **PT FOIL** não é alocada a uma caixa de Premodern, e uma **PT
     non-foil** da era é;
  3. uma **EN non-foil** É alocada ao Duel Commander quando não há foil dessa
     carta (é a regra de 19/09 a continuar a valer), e também quando há —
     porque `prefere_foil` aceita as duas;
  4. uma **EN foil** ganha à non-foil nos dois grupos (`_ordem`);
  5. **20 básicas iguais cabem numa foto** e 5 cartas diferentes não;
  6. uma básica entra por **contagem declarada**, conta como tida, e aparece
     marcada `declarada` — nunca como «confirmada por foto»;
  7. a isenção das básicas cobre **língua, edição E acabamento** nos TRÊS
     grupos: uma Unhinged **EN foil** serve uma caixa de Premodern `nonfoil`, e
     uma Unhinged serve o Duel Commander e o Pauper;
  8. o `requisito_basicas` não pede o acabamento como REQUISITO enquanto a
     isenção estiver ligada (dizia *"non-foil"* a seco numa linha que o motor
     aceita em foil);
  9. nenhuma básica aparece como falta a COMPRAR por causa destas regras;
 10. uma básica **não leva escalão de estado nem verso**.

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
# AS REGRAS DE MATERIAL TAL COMO ELE AS DITOU A 2026-10-02 — é isto que o teste
# exerce, e é a mesma forma do `colecao_config.json` a sério.
REGRAS = [
    {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
     "lingua": "pt", "acabamento": "nonfoil", "edicoes": "premodern",
     "estrita": True,
     "baldes": ["Colecção", "SPML", "Caixa Reserved List"]},
    {"grupo": "duel-commander", "formatos": ["duel-commander"],
     "dedicado": True, "lingua": "en", "acabamento": "prefere_foil"},
    {"grupo": "pauper", "formatos": ["pauper"], "dedicado": True,
     "lingua": "en", "acabamento": "prefere_foil"},
]
CFG = {"regras_colecao": {}, "decks_vigiados": [],
       "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
       "regras_por_formato": REGRAS,
       "basicas": {"isentas_de_regras": True, "edicao": "Unhinged",
                   "comprar_se_material_especial": True,
                   "compram_se_faltarem": ["Snow-Covered Plains"]}}
CFG_PATH = _TMP / "cfg.json"


def escrever_cfg(**extra) -> None:
    """Escreve o config do teste (com `basicas.declaradas`, se for o caso)."""
    cfg = json.loads(json.dumps(CFG))
    for k, v in extra.items():
        if k == "basicas":
            cfg["basicas"].update(v)
        else:
            cfg[k] = v
    CFG_PATH.write_text(json.dumps(cfg), encoding="utf-8")
    sources._CACHE.clear() if hasattr(sources, "_CACHE") else None


escrever_cfg.__module__ = __name__
CFG_PATH.write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, estado, fotos, loadout, revalidacao, sources  # noqa: E402
from mtgvault import confirmado as _conf  # noqa: E402

# (nome, edição, data, acabamentos, língua, tipo) — impressões de cartas reais.
# A era Premodern acaba no Scourge (2003-05-26).
CATALOGO = [
    # a carta que a regra do Premodern vai medir: existe em PT nas duas formas
    ("Nantuko Vigilante", "lgn", "2003-02-03", ["nonfoil", "foil"], "pt", "Creature"),
    ("Nantuko Vigilante", "lgn", "2003-02-03", ["nonfoil", "foil"], "en", "Creature"),
    # existe em foil: a nonfoil NÃO fecha um slot `foil`, mas fecha um
    # `prefere_foil` — é a diferença que esta ordem introduz no Duel Commander
    ("Parallax Wave", "nem", "2000-02-14", ["nonfoil", "foil"], "en", "Enchantment"),
    ("Parallax Wave", "nem", "2000-02-14", ["nonfoil", "foil"], "pt", "Enchantment"),
    # nunca saiu em foil (a regra de 2026-09-19 continua a valer)
    ("Glimmer Lens", "onc", "2023-02-10", ["nonfoil"], "en", "Artifact"),
    # para o Pauper
    ("Myr Enforcer", "mrd", "2003-10-02", ["nonfoil", "foil"], "en", "Creature"),
    ("Myr Enforcer", "mrd", "2003-10-02", ["nonfoil", "foil"], "pt", "Creature"),
    # as básicas dele: Unhinged, EN, foil e non-foil
    ("Plains", "unh", "2004-11-19", ["nonfoil", "foil"], "en", "Basic Land"),
    ("Island", "unh", "2004-11-19", ["nonfoil", "foil"], "en", "Basic Land"),
    ("Snow-Covered Plains", "mh1", "2019-06-14", ["nonfoil", "foil"], "en",
     "Basic Snow Land"),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fins, lang, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, set_type)
               VALUES (?,?,?,?,?,?,?,'rare',?,1,'',?,?,?,0,0,'expansion')""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), str(i), lang, tipo,
             json.dumps(fins), rel,
             json.dumps({"legacy": "legal", "commander": "legal",
                         "premodern": "legal", "pauper": "legal"})))
        for f in fins:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-10-02', ?)",
                        (f"id-{i}", f, 10.0 if f == "foil" else 2.0))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub="Colecção"):
    sid = con.execute(
        "SELECT scryfall_id FROM catalog.cards WHERE name = ? AND lang = ? "
        "ORDER BY released_at LIMIT 1", (nm, lang)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub_id))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?",
                      (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                    "board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def slot(nome, fmt, ref, **kw):
    d = {"slot": nome.lower().replace(" ", "-"), "nome": nome, "formato": fmt,
         "fonte": "deck", "ref": ref, "balde": "Colecção", "prioridade": 1}
    d.update(kw)
    return d


def por_nome(rep):
    return {s["nome"]: s for s in rep["slots"]}


def linha(s, nm):
    return next(m for m in s["have"] + s["missing"] if m["nm"] == nm)


def rep_de(con, slots):
    return loadout.report(con, slots)


# ---------------------------------------------------------------------------
def caso_uma_copia_pt_nao_entra_no_duel_commander_nem_no_pauper():
    """A LÍNGUA APERTOU nos dois grupos: uma cópia PT deixa de servir.

    Antes de 2026-10-02 nenhum dos dois tinha chave de `lingua` — uma Parallax
    Wave PT foil fechava o slot do Duel Commander. Hoje é falta a comprar.
    """
    con = base()
    add(con, "Parallax Wave", 1, "foil", "pt")
    add(con, "Myr Enforcer", 1, "foil", "pt")
    deck(con, "Cloud", "duel-commander", [("Parallax Wave", 1)])
    deck(con, "Affinity", "pauper", [("Myr Enforcer", 1)])
    rep = rep_de(con, [slot("Cloud", "duel-commander", "Cloud"),
                       slot("Affinity", "pauper", "Affinity")])
    s = por_nome(rep)
    for nome, carta in (("Cloud", "Parallax Wave"), ("Affinity", "Myr Enforcer")):
        m = linha(s[nome], carta)
        assert m["got"] == 0, (nome, carta, m["got"])
        assert m["comprar"] == 1, (nome, m["comprar"])
        assert not m["lotes"], f"{nome}: a PT foi alocada e nao podia"
    print("OK 1: uma copia PT nao entra no Duel Commander nem no Pauper")


def caso_uma_pt_foil_nao_entra_no_premodern_e_uma_pt_nonfoil_entra():
    """O ACABAMENTO APERTOU no Premodern — e é a única cópia que esta ordem tira.

    Na base dele é a Nantuko Vigilante (LGN) PT foil, cópia #578, que a alocação
    dava ao Elves. A PT non-foil da mesma era continua a servir.
    """
    con = base()
    foil_id = add(con, "Nantuko Vigilante", 1, "foil", "pt")
    nonfoil_id = add(con, "Nantuko Vigilante", 1, "nonfoil", "pt")
    deck(con, "Elves", "premodern", [("Nantuko Vigilante", 2)])
    rep = rep_de(con, [slot("Elves", "premodern", "Elves")])
    m = linha(por_nome(rep)["Elves"], "Nantuko Vigilante")
    ids = {g["id"] for g in m["lotes"]}
    assert nonfoil_id in ids, f"a PT non-foil tinha de servir: {m['lotes']}"
    assert foil_id not in ids, f"a PT FOIL nao pode servir: {m['lotes']}"
    assert m["got"] == 1 and m["comprar"] == 1, (m["got"], m["comprar"])
    print("OK 2: no Premodern a PT non-foil entra e a PT FOIL nao")


def caso_en_nonfoil_entra_no_duel_commander():
    """O ACABAMENTO AFROUXOU: `prefere_foil` aceita a non-foil.

    Nos dois casos — a carta que **existe** em foil (Parallax Wave, que antes
    desta ordem era recusada) e a que nunca saiu em foil (Glimmer Lens, que já
    servia pela regra de 2026-09-19).
    """
    con = base()
    add(con, "Parallax Wave", 1, "nonfoil", "en")
    add(con, "Glimmer Lens", 1, "nonfoil", "en")
    deck(con, "Cloud", "duel-commander",
         [("Parallax Wave", 1), ("Glimmer Lens", 1)])
    rep = rep_de(con, [slot("Cloud", "duel-commander", "Cloud")])
    s = por_nome(rep)["Cloud"]
    for nm in ("Parallax Wave", "Glimmer Lens"):
        m = linha(s, nm)
        assert m["got"] == 1 and m["lotes"], f"{nm} tinha de fechar o slot: {m}"
        assert m["comprar"] == 0, (nm, m["comprar"])
    assert s["pct_fisico"] == 100, s["pct_fisico"]
    print("OK 3: EN non-foil fecha o slot do Duel Commander (exista ou nao foil)")


def caso_a_foil_ganha_a_nonfoil_nos_dois_grupos():
    """`prefere_foil` = *"tudo foil se houver disponível"*: a foil gasta-se
    primeiro. Com uma de cada e o deck a pedir UMA, vai a foil."""
    con = base()
    for fmt, nome, carta in (("duel-commander", "Cloud", "Parallax Wave"),
                             ("pauper", "Affinity", "Myr Enforcer")):
        con2 = base()
        nf = add(con2, carta, 1, "nonfoil", "en")
        fo = add(con2, carta, 1, "foil", "en")
        deck(con2, nome, fmt, [(carta, 1)])
        rep = rep_de(con2, [slot(nome, fmt, nome)])
        m = linha(por_nome(rep)[nome], carta)
        ids = {g["id"] for g in m["lotes"]}
        assert ids == {fo}, f"{nome}: devia gastar a FOIL primeiro, gastou {ids}"
        assert nf not in ids
    del con
    print("OK 4: a foil gasta-se primeiro nos dois grupos de prefere_foil")


def caso_vinte_basicas_iguais_cabem_numa_foto():
    """A REGRA DO MÁXIMO 4 CARTAS NÃO VALE PARA BÁSICAS (02/10/2026).

    *"para as basicas, nos decks, tens que permitir tirar foto com mais cartas
    e nao apenas 4"* — e nos dois sentidos: 5 cartas DIFERENTES continuam a não
    passar, e uma foto que MISTURE básicas com outra carta também não.
    """
    # a pergunta «isto é só básicas?», num sítio só
    assert fotos.so_basicas(["Plains"]) is True
    assert fotos.so_basicas(["Plains", "Island"]) is True
    assert fotos.so_basicas(["Snow-Covered Plains"]) is True
    assert fotos.so_basicas(["Plains", "Mox Opal"]) is False
    assert fotos.so_basicas([]) is False
    # a trava
    assert fotos.valida(20, isenta=True) is True, "20 basicas numa foto passam"
    assert fotos.valida(27, isenta=True) is True
    assert fotos.valida(5) is False, "5 cartas diferentes nao passam"
    assert fotos.valida(20) is False, "20 cartas normais nao passam"
    assert fotos.valida(4) is True and fotos.valida(0) is False
    assert fotos.valida(0, isenta=True) is False, "zero cartas nunca valida"
    # e o AGRUPAMENTO: 27 básicas são UMA foto, não sete
    fs = fotos.agrupar([{"nm": "Snow-Covered Plains", "copy_id": 1, "q": 27,
                         "unit": 2.0}], tipos={"Snow-Covered Plains": "Land"})
    assert len(fs) == 1, f"27 basicas tinham de dar 1 foto, deram {len(fs)}"
    assert fs[0]["cartas"] == 27 and fs[0]["isenta"] is True, fs[0]
    assert fs[0]["partida"] is False, "uma foto de basicas nao e partida"
    # uma carta normal de 27 cópias continua a partir-se em lotes de 4
    fs = fotos.agrupar([{"nm": "Parallax Wave", "copy_id": 2, "q": 27,
                        "unit": 2.0}], tipos={"Parallax Wave": "Enchantment"})
    assert len(fs) == 7, f"27 copias normais dao 7 fotos, deram {len(fs)}"
    assert all(f["partida"] and not f["isenta"] for f in fs), fs
    print("OK 5: 20 basicas iguais cabem numa foto; 5 cartas diferentes nao")


def caso_a_basica_e_contagem_declarada_e_nao_confirmada_por_foto():
    """As básicas contam como TIDAS sem foto, e vão numa PARCELA PRÓPRIA.

    *"depois indico quantas basicas tenho de cada"* — e por isso não podem somar
    ao «confirmado por foto»: até 02/10 somavam, e o vault dizia *"95 cartas
    confirmadas por foto"* num dia sem uma única foto desta campanha.
    """
    escrever_cfg(basicas={"declaradas": {"Plains": {"nonfoil": 40, "foil": 8}},
                          "declaradas_em": "2026-10-02"},
                 revalidacao={"desde": "2026-09-20", "foto_manda": True})
    try:
        assert loadout.basicas_declaradas() == {"Plains": {"nonfoil": 40,
                                                           "foil": 8}}
        assert loadout.basicas_declaradas_de("Plains") == 48
        assert loadout.basicas_declaradas_em() == "2026-10-02"
        # o atalho `{"Plains": 29}` vale nonfoil
        escrever_cfg(basicas={"declaradas": {"Plains": 29}},
                     revalidacao={"desde": "2026-09-20", "foto_manda": True})
        assert loadout.basicas_declaradas() == {"Plains": {"nonfoil": 29}}
        # e um nome que não é básica não entra (não se inventa uma)
        escrever_cfg(basicas={"declaradas": {"Mox Opal": 4, "Plains": 29}},
                     revalidacao={"desde": "2026-09-20", "foto_manda": True})
        assert "Mox Opal" not in loadout.basicas_declaradas()

        con = base()
        add(con, "Parallax Wave", 1, "foil", "en")
        deck(con, "Cloud", "duel-commander",
             [("Parallax Wave", 1), ("Plains", 10)])
        rep = rep_de(con, [slot("Cloud", "duel-commander", "Cloud")])
        s = por_nome(rep)["Cloud"]
        # A básica CONTA como tida SEM FOTO — é a excepção dele. A Parallax Wave
        # está fisicamente lá e NÃO conta, porque não tem foto desta campanha:
        # é exactamente a assimetria que esta ordem existe para tornar visível.
        assert s["tenho_fisico"] == 11, s["tenho_fisico"]
        assert s["tenho"] == 10 and s["pct"] == 91, (s["tenho"], s["pct"])
        # … e a básica vai na parcela DECLARADA, nunca na da foto
        assert s["tenho_decl"] == 10, s["tenho_decl"]
        assert s["tenho_conf"] == 0, s["tenho_conf"]
        assert s["sem_foto"] == 1, s["sem_foto"]
        assert rep["tenho_decl_total"] == 10, rep["tenho_decl_total"]
        assert rep["tenho_conf_total"] == 0, rep["tenho_conf_total"]
        m = rep["cartas_metades"]
        assert m["declarado"] == 10 and m["confirmado"] == 0, m
        assert m["por_confirmar"] == 1 and m["total"] == 11, m
        assert m["confirmado"] + m["declarado"] + m["por_confirmar"] == m["total"]
        assert "contagem declarada" in m["frase"], m["frase"]
        assert "0 de 11 cópias confirmadas por foto" in m["frase"], m["frase"]
        # a linha de básicas diz de onde vem a prova, e o que ele declarou
        b = next(x for x in s["basicas"] if x["nm"] == "Plains")
        assert b["origem"] == _conf.ORIGEM_DECLARADA == "declarada", b
        assert b["declarado_q"] == 29, b
        print("OK 6: a basica conta como tida, marcada «declarada» e nao «por foto»")
    finally:
        CFG_PATH.write_text(json.dumps(CFG), encoding="utf-8")


def caso_a_isencao_das_basicas_cobre_lingua_edicao_e_acabamento():
    """A ISENÇÃO TEM TRÊS PERNAS, e a do acabamento faltava (02/10/2026).

    Uma Unhinged EN **foil** tem de servir uma caixa de Premodern `nonfoil` (que
    além do acabamento exige PT e ≤ Scourge — e Unhinged é de 2004); e uma
    Unhinged serve o Duel Commander e o Pauper, que agora exigem EN.
    """
    # (grupo, formato, acabamento da cópia) — o caso de cada um dos três grupos
    casos = [("premodern", "Elves", "foil"),       # a caixa quer NON-foil
             ("premodern", "Elves", "nonfoil"),
             ("duel-commander", "Cloud", "nonfoil"),  # a caixa prefere foil
             ("pauper", "Affinity", "nonfoil")]
    for fmt, nome, fin in casos:
        con = base()
        add(con, "Plains", 10, fin, "en")
        deck(con, nome, fmt, [("Plains", 10)])
        rep = rep_de(con, [slot(nome, fmt, nome)])
        s = por_nome(rep)[nome]
        m = linha(s, "Plains")
        assert m["got"] == 10, f"{fmt}/{fin}: a basica tinha de servir: {m}"
        assert m["lotes"], f"{fmt}/{fin}: a basica nao foi alocada: {m}"
        assert sum(g["q"] for g in m["lotes"]) == 10, m["lotes"]
        # e NUNCA aparece como falta a comprar (ponto 9 da ordem)
        assert not s["basicas"] or all(b["comprar"] == 0 for b in s["basicas"]), \
            f"{fmt}/{fin}: uma basica apareceu como compra: {s['basicas']}"
        assert s["comprar"] == 0, (fmt, fin, s["comprar"])
    print("OK 7: a isencao das basicas cobre lingua, edicao E acabamento, nos 3")


def caso_o_requisito_das_basicas_nao_pede_o_acabamento_como_requisito():
    """Com a isenção ligada, o acabamento de uma básica é PREFERÊNCIA.

    O `requisito_basicas` dizia `"non-foil"` a seco — e a partir do dia em que o
    Premodern passou a `nonfoil` isso era a página a exigir o que o motor
    aceita em foil. Com a isenção desligada volta a ser um requisito.
    """
    assert loadout.basicas_isentas() is True
    assert loadout.requisito_basicas({"acabamento": "nonfoil"}) == "non-foil se houver"
    assert loadout.requisito_basicas({"acabamento": "foil"}) == "foil se houver"
    assert loadout.requisito_basicas({"acabamento": "prefere_foil"}) == "foil se houver"
    assert loadout.requisito_basicas({}) == ""
    escrever_cfg(basicas={"isentas_de_regras": False})
    try:
        assert loadout.basicas_isentas() is False
        assert loadout.requisito_basicas({"acabamento": "nonfoil"}) == "non-foil"
        assert loadout.requisito_basicas({"acabamento": "foil"}) == "foil"
    finally:
        CFG_PATH.write_text(json.dumps(CFG), encoding="utf-8")
    print("OK 8: o acabamento de uma basica e preferencia, e a frase di-lo")


def caso_uma_foto_so_de_basicas_valida_na_importacao():
    """A trava do import e o detector da base conhecem a mesma isenção."""
    revalidacao.declarar_lote({"muitas.jpg": 27, "normal.jpg": 6},
                              {"muitas.jpg"})
    try:
        assert revalidacao.valida_esta_foto("muitas.jpg") is True
        assert revalidacao.valida_esta_foto("x/muitas.jpg") is True
        assert revalidacao.valida_esta_foto("normal.jpg") is False
    finally:
        revalidacao.declarar_lote(None)
    # e na BASE: uma foto de 27 básicas valida; uma de 6 cartas normais não
    con = base()
    add(con, "Snow-Covered Plains", 27, "foil", "en")
    add(con, "Parallax Wave", 6, "foil", "en")
    con.execute("UPDATE copies SET photo_path = 'basicas.jpg' WHERE id = 1")
    con.execute("UPDATE copies SET photo_path = 'outras.jpg' WHERE id = 2")
    con.commit()
    maus = revalidacao.fotos_que_nao_validam(con)
    assert "basicas.jpg" not in maus, f"a foto de basicas tinha de valer: {maus}"
    assert maus.get("outras.jpg") == 6, maus
    print("OK 9: uma foto so de basicas valida; uma de 6 cartas normais nao")


def caso_uma_basica_nao_leva_escalao_de_estado_nem_verso():
    """`estado.registar` recusa-se ALTO numa básica (02/10/2026).

    Entram por contagem declarada e nunca por foto: não há foto de onde tirar um
    escalão. Recusar em silêncio parecia a regra da correcção dele
    (`aplicado = 0`), que é outra coisa.
    """
    con = base()
    bid = add(con, "Plains", 10, "foil", "en")
    oid = add(con, "Parallax Wave", 1, "foil", "en")
    assert estado.e_basica(con, bid) is True
    assert estado.e_basica(con, oid) is False
    try:
        estado.registar(con, bid, "EX", origem="mao", motivos="bordas")
        raise AssertionError("uma basica nao pode levar escalao")
    except estado.EstadoInvalido as e:
        assert "básicos" in str(e), str(e)
    # e não deixou rasto nenhum: nem no log nem na cópia
    n = con.execute("SELECT COUNT(*) c FROM condition_log WHERE copy_id = ?",
                    (bid,)).fetchone()["c"]
    assert n == 0, f"a recusa escreveu {n} linhas no condition_log"
    # a carta normal continua a aceitar
    r = estado.registar(con, oid, "EX", origem="mao", motivos="bordas brancas")
    assert r["aplicado"] and r["grade"] == "EX", r
    print("OK 10: uma basica nao leva escalao de estado nem verso")


def run():
    for fn in (caso_uma_copia_pt_nao_entra_no_duel_commander_nem_no_pauper,
               caso_uma_pt_foil_nao_entra_no_premodern_e_uma_pt_nonfoil_entra,
               caso_en_nonfoil_entra_no_duel_commander,
               caso_a_foil_ganha_a_nonfoil_nos_dois_grupos,
               caso_vinte_basicas_iguais_cabem_numa_foto,
               caso_a_basica_e_contagem_declarada_e_nao_confirmada_por_foto,
               caso_a_isencao_das_basicas_cobre_lingua_edicao_e_acabamento,
               caso_o_requisito_das_basicas_nao_pede_o_acabamento_como_requisito,
               caso_uma_foto_so_de_basicas_valida_na_importacao,
               caso_uma_basica_nao_leva_escalao_de_estado_nem_verso):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
