"""A PASTA DE UMA FAMÍLIA DE DECKS, E UMA CAIXA QUE SAI (André, 2026-10-13).

*"os decks de modern partilham muitas cartas, sugeria que pegasses nos decks que
partilham muitas cartas e criasses uma pasta para esses decks todos juntos"* — e
*"Standard vou ficar sem deck … podemos eliminar esse deck"*.

O que aqui se tranca:

  1. a pasta da família é um ALVO PRÓPRIO (`familia`), nunca o slot de uma
     das caixas — um alias para `modern` punha, com «a foto manda», as cartas
     de Legacy dentro da caixa de Modern;
  2. a recolha move a foto para `pendentes/` com `site-familia-<id>-…`,
     EMPARELHA frente/verso como uma pasta de deck, e o `fotosite.origem` lê-a;
  3. a foto da família NÃO decide o deck (`confirmado.alvo_da_pasta`);
  4. o passo (0) da revalidação prefere as cópias de QUALQUER caixa da família;
  5. uma foto nunca fica sem alvo em silêncio: a pasta de uma família sem
     caixas vivas e as pastas arquivadas (`_…`) aparecem em `ignorados` com
     «caixa do config» (o que a tarefa das 02:30 trata como erro);
  6. a família tem pasta e plano; as caixas dela deixam de ganhar pasta própria;
  7. o nome de um slot não se pode confundir com uma família;
  8. uma caixa com `_saiu` sai do que se monta (caixas, loadout, pastas) e
     continua no config;
  9. o config a sério diz o que foi decidido a 13/10.

Não abre socket nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME` **e**
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

CAIXAS = [
    {"slot": "modern", "nome": "Modern — Pinnacle Affinity", "formato": "modern",
     "fonte": "deck", "ref": "MO", "balde": "Colecção", "estado": "montada",
     "prioridade": 1},
    {"slot": "legacy-welder", "nome": "Engineer Welder Cam", "formato": "legacy",
     "fonte": "deck", "ref": "EW", "balde": "Colecção", "estado": "montada",
     "prioridade": 2},
    {"slot": "cedh-blue-farm", "nome": "Blue Farm", "formato": "cedh",
     "fonte": "deck", "ref": "BF", "balde": "Colecção", "estado": "montada",
     "prioridade": 3},
    {"slot": "standard", "nome": "Bant Airbend", "formato": "standard",
     "fonte": "deck", "ref": "ST", "balde": "Colecção", "estado": "permanente",
     "prioridade": 4, "_saiu": {"em": "2026-10-13", "porque": "rotacao"}},
]
FAMILIA = {"id": "mox-opal", "pasta": "Mox Opal (Modern + Legacy)",
           "slots": ["modern", "legacy-welder"]}
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en", "acabamento": "nonfoil"},
        {"grupo": "spml", "formatos": ["modern", "legacy", "standard"]},
    ],
    "caixas": CAIXAS,
    "familias_fotos": [FAMILIA],
    "revalidacao": {"desde": "2026-09-20", "alvo": None},
    "reserva": {"limiar_pct": 20},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (caixas, collection, configio, confirmado, db,  # noqa: E402
                      fotocaixa, fotos, fotosite, loadout, revalidacao, sources,
                      versoes)

SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)
fotocaixa.RAIZ = SITE
_ABERTAS = []
CATALOGO = [("Mox Opal", "som", ["nonfoil", "foil"]),
            ("Goblin Welder", "ulg", ["nonfoil"]),
            ("Force of Will", "all", ["nonfoil"])]


def repor(**muda):
    cfg = json.loads(json.dumps(CFG))
    cfg.update(muda)
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return cfg


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, fin) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Artifact',1,'',?, '2010-01-01',?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), str(i), json.dumps(fin),
             json.dumps({"modern": "legal", "legacy": "legal"})))
    for nome, fmt, cartas in (("MO", "modern", ["Mox Opal"]),
                              ("EW", "legacy", ["Mox Opal", "Goblin Welder"]),
                              ("BF", "cedh", ["Force of Will"]),
                              ("ST", "standard", ["Force of Will"])):
        con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name=?", (nome,)).fetchone()["id"]
        for nm in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?,?,1,'main')", (did, nm))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, slot=None, finish="nonfoil"):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=1, language="en",
                              finish=finish, sub_collection="Colecção")
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,1)",
                    (cid, slot))
    con.commit()
    return cid


def larga(*partes):
    d = fotos.pasta_novas()
    for p in partes[:-1]:
        d = d / p
    d.mkdir(parents=True, exist_ok=True)
    f = d / partes[-1]
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    os.utime(f, (1_700_000_000, 1_700_000_000))
    return f


def limpar():
    p = fotosite.pasta_pendentes(SITE)
    if p.is_dir():
        for f in p.glob("*"):
            if f.is_file():
                f.unlink()
    fotos._CACHE.clear()


# 1 -------------------------------------------------------------------------
def caso_a_pasta_da_familia_e_um_alvo_proprio_e_nao_uma_caixa():
    repor()
    a = fotos.alvo_da_pasta(f"{FAMILIA['pasta']}/Mox Opal (4)/x.jpg")
    assert a and a["tipo"] == "familia" and a["slot"] is None, a
    assert a["familia"] == "mox-opal" and a["slots"] == ["modern", "legacy-welder"], a
    # e o `slot_da_pasta` (a pergunta «que CAIXA é esta pasta») não lhe dá caixa
    assert fotos.slot_da_pasta(f"{FAMILIA['pasta']}/x.jpg") is None
    # uma pasta de deck que não está na família continua a valer como antes
    assert fotos.alvo_da_pasta("Blue Farm/x.jpg") == {"tipo": "caixa", "slot": "cedh-blue-farm"}
    print("a pasta da familia e um alvo proprio, nunca o slot de uma das caixas")


# 2 + 3 ---------------------------------------------------------------------
def caso_a_recolha_da_familia_emparelha_e_nao_decide_o_deck():
    repor()
    limpar()
    base()
    f1 = larga(FAMILIA["pasta"], "Mox Opal (4)", "IMG_1.jpg")
    f2 = larga(FAMILIA["pasta"], "Mox Opal (4)", "IMG_2.jpg")
    os.utime(f2, (1_700_000_010, 1_700_000_010))
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert len(r["recolhidas"]) == 2 and r["pares"] == 1, r
    frente, verso = r["recolhidas"]
    assert frente["para"].startswith("site-familia-mox-opal-"), frente
    assert verso["verso"] and fotosite.par_da_frente(verso["para"]) == frente["para"], r
    assert not f1.exists() and not f2.exists()
    o = fotosite.origem(frente["para"])
    assert o["tipo"] == "familia" and o["familia"] == "mox-opal" and o["slot"] is None, o
    # a foto prova a carta e NÃO decide o deck — a alocação não se toca
    assert confirmado.alvo_da_pasta(frente["para"]) == (False, None)
    # arruma-se numa pasta da família, nunca em `sem-alvo` nem na de uma caixa
    # [CORRIGIDO A 2026-10-13] era `familia-mox-opal` (em `data/fotos/`); desde
    # as duas árvores a foto processada vai para a MESMA pasta da família em
    # «Decks Processados» — o nome da pasta onde ele a largou.
    assert fotos.pasta_do_alvo(dict(o)).name == fotos.familia("mox-opal")["pasta"]
    limpar()
    print("a recolha da familia emparelha frente/verso e nao decide o deck")


# 4 -------------------------------------------------------------------------
def caso_a_revalidacao_prefere_as_copias_de_qualquer_caixa_da_familia():
    repor()
    con = base()
    a = copia(con, "Mox Opal", "som", slot="modern")
    b = copia(con, "Goblin Welder", "ulg", slot="legacy-welder")
    c = copia(con, "Force of Will", "all", slot="cedh-blue-farm")
    nome = fotosite.nome_ficheiro("familia", "mox-opal",
                                  __import__("datetime").datetime(2026, 10, 13, 10, 0, 0), 1, "jpg")
    alvo, _p = revalidacao.alvo_da_foto(con, nome, {}, None)
    assert alvo and alvo["tipo"] == "familia", alvo
    assert {a, b} <= alvo["copias"] and c not in alvo["copias"], alvo["copias"]
    print("o passo (0) prefere as copias das DUAS caixas da familia, e so dessas")


# 5 -------------------------------------------------------------------------
def caso_uma_foto_nunca_fica_sem_alvo_em_silencio():
    limpar()
    # a família sem caixas vivas: a pasta passa a desconhecida, e diz-se
    repor(familias_fotos=[{"id": "x", "pasta": "Morta", "slots": ["nao-existe"]}])
    f = larga("Morta", "a.jpg")
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert f.exists() and not r["recolhidas"], r
    assert any("caixa do config" in x["porque"] for x in r["ignorados"]), r
    f.unlink()
    # a pasta arquivada também se diz
    repor()
    g = larga("_nomes antigos", "Engineer Welder Cam", "b.jpg")
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert g.exists() and any("caixa do config" in x["porque"] and x["ficheiro"] == "b.jpg"
                              for x in r["ignorados"]), r
    g.unlink()
    print("familia sem caixas e pasta arquivada: a foto fica, mas e DITA")


# 6 -------------------------------------------------------------------------
def caso_a_familia_tem_pasta_e_plano_e_as_caixas_dela_nao_tem_pasta_propria():
    repor()
    con = base()
    copia(con, "Mox Opal", "som", slot="modern")
    rep = loadout.report(con)
    r = fotos.escrever_planos(con, rep, raiz=SITE)
    base_ = fotos.pasta_novas(SITE)
    assert (base_ / FAMILIA["pasta"]).is_dir(), r
    assert not (base_ / "Modern — Pinnacle Affinity").exists(), "a caixa da familia nao ganha pasta"
    assert not (base_ / "Engineer Welder Cam").exists()
    assert (base_ / "Blue Farm").is_dir(), "uma caixa fora da familia continua a ter pasta"
    plano = (base_ / FAMILIA["pasta"] / "_plano.txt").read_text(encoding="utf-8")
    assert "PASTA DA FAMILIA" in plano and "Engineer Welder Cam" in plano \
        and "Modern — Pinnacle Affinity" in plano, plano
    assert FAMILIA["pasta"] not in r["orfas"], r
    print("a familia tem pasta e plano; as caixas dela nao ganham pasta propria")


# 7 -------------------------------------------------------------------------
def caso_um_slot_nao_se_confunde_com_uma_familia():
    import datetime as dt
    q = dt.datetime(2026, 10, 13, 9, 0, 0)
    try:
        fotosite.nome_ficheiro("caixa", "familia-x", q, 1, "jpg")
    except fotocaixa.FotoInvalida:
        pass
    else:
        raise AssertionError("um slot 'familia-…' confundia-se com uma familia")
    n = fotosite.nome_ficheiro("familia", "mox-opal", q, 3, "jpg", verso=True)
    o = fotosite.origem(n)
    assert o["tipo"] == "familia" and o["familia"] == "mox-opal" and o["n"] == 3 and o["verso"], o
    o2 = fotosite.origem(fotosite.nome_ficheiro("caixa", "legacy-welder", q, 1, "jpg"))
    assert o2["tipo"] == "caixa" and o2["slot"] == "legacy-welder" and "familia" not in o2, o2
    print("nome e origem sao inversos para a familia, e um slot nao a imita")


# 8 -------------------------------------------------------------------------
def caso_uma_caixa_que_saiu_nao_se_monta_e_continua_no_config():
    cfg = repor()
    slots = [s["slot"] for s in caixas.slots(cfg)]
    assert "standard" not in slots and "modern" in slots, slots
    assert [c["slot"] for c in caixas.saidas(cfg)] == ["standard"]
    assert any(c["slot"] == "standard" for c in cfg["caixas"]), "nada se apaga"
    con = base()
    # mesmo com a lista CRUA do config (há quem a passe), o loadout salta-a
    assert "standard" not in [s["slot"] for s in loadout.resolve_slots(con, cfg["caixas"])]
    assert "standard" not in [s["slot"] for s in loadout.report(con)["slots"]]
    assert fotos.alvo_da_pasta("Bant Airbend/x.jpg") is None, "a pasta dela deixa de ser alvo"
    # repor é tirar a marca
    cfg2 = repor(caixas=[{k: v for k, v in c.items() if k != "_saiu"} for c in CAIXAS])
    assert "standard" in [s["slot"] for s in caixas.slots(cfg2)]
    repor()
    print("uma caixa com _saiu sai do que se monta, fica no config, e repoe-se")


# 9 -------------------------------------------------------------------------
def caso_o_config_a_serio_tem_as_decisoes_de_13_10():
    real = configio.ler(RAIZ / "colecao_config.json")
    std = next(c for c in real["caixas"] if c["slot"] == "standard")
    assert caixas.saiu(std) and "Janeiro" in std["_saiu"]["porque"], std.get("_saiu")
    assert "standard" not in [s["slot"] for s in caixas.slots(real)]
    pio = next(c for c in real["caixas"] if c["slot"] == "pioneer")
    assert not caixas.saiu(pio), "o Greasefang FICA (ele voltou atras a 13/10)"
    for slot in ("legacy-welder", "legacy-artifacts-blue"):
        rec = real["listas_escolhidas"][slot]
        assert rec.get("evento") and rec.get("fonte_decklist"), slot
        assert next(c for c in real["caixas"] if c["slot"] == slot)["fonte"] == "escolhido"
    fam = real["familias_fotos"][0]
    # A `modern-affinity` (desactivada desde 04/10) também é Mox Opal: sem ela na
    # família, o daily recriava todas as noites a pasta `Modern — Affinity` que
    # o supervisor tinha arquivado.
    assert fam["slots"] == ["modern", "legacy-artifacts-blue", "legacy-welder",
                            "modern-affinity"], fam
    k = real["listas_escolhidas"]["deck:modern:jaces-machinations-combo"]
    assert sum(q for b, _n, q in k["cards"] if b == "main") == 60
    assert sum(q for b, _n, q in k["cards"] if b == "side") == 15
    dk = next(d for d in real["decks_de_evento"]
              if d["id"] == "deck:modern:jaces-machinations-combo")
    # 13/10 de manhã a decisão estava PENDENTE; à tarde ele decidiu («vai para
    # Pioneer com lista nova»): a de Modern SAI (não se apaga) e a pergunta fica
    # arquivada em `_decisao_1013`. Ver test_kasmina_arts.
    assert dk.get("_saiu") and dk.get("_decisao_1013") \
        and not dk.get("decisao_pendente"), dk
    # nao e uma versao do Mox Opal, logo nao entra na proteccao RE
    assert "deck:modern:jaces-machinations-combo" not in versoes.ids_que_ficam(real)
    vp = {v["id"]: v for v in real["decks_por_formato"]["pioneer"]["versoes"]}
    assert vp["versao:pioneer:broodwagon"]["nome"] == "Abzan Greasefang"
    assert vp["versao:pioneer:mycosynth"]["nome"] == "Orzhov Monument"
    assert vp["versao:pioneer:parhelion"].get("_saiu"), "o «Parhelion» era a Abzan"
    print("o config a serio diz o que foi decidido a 13/10")


CASOS = (caso_a_pasta_da_familia_e_um_alvo_proprio_e_nao_uma_caixa,
         caso_a_recolha_da_familia_emparelha_e_nao_decide_o_deck,
         caso_a_revalidacao_prefere_as_copias_de_qualquer_caixa_da_familia,
         caso_uma_foto_nunca_fica_sem_alvo_em_silencio,
         caso_a_familia_tem_pasta_e_plano_e_as_caixas_dela_nao_tem_pasta_propria,
         caso_um_slot_nao_se_confunde_com_uma_familia,
         caso_uma_caixa_que_saiu_nao_se_monta_e_continua_no_config,
         caso_o_config_a_serio_tem_as_decisoes_de_13_10)


def main():
    for c in CASOS:
        c()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001
            pass
    print(f"\nOK — {len(CASOS)} casos (a pasta da familia e a caixa que sai)")


if __name__ == "__main__":
    main()
