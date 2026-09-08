"""A Reserved List em PT serve o Legacy — e não vai à venda por causa disso.

Ordem do André (2026-09-08, à letra): *"RL em PT pode servir para Legacy e
Premodern, mas não para cEDH nem outro formato."*

São duas metades da mesma decisão, e uma sem a outra não vale nada:

  1. a **caixa de Legacy passa a ver** uma cópia da Reserved List em português,
     apesar de o grupo SPML ser *"tudo foil e inglês"* e de uma PT de impressão
     até ao Scourge estar trancada ao Premodern desde 2026-09-07. A excepção é
     do FORMATO e não do grupo (`por_formato` nas `regras_por_formato`): o
     Standard, o Pioneer e o Modern continuam como estavam, e o cEDH também;
  2. e a lista de venda **guarda-lhe essas cópias**. Enquanto a caixa de Legacy
     não tem deck escolhido, quem diz o que ela vai pedir é o top-N do metagame
     — o mesmo `foil_report` que a página mostra. Sem esta metade, a regra nova
     abria a porta a uma Mox Diamond PT no dia em que a lista de venda a mandava
     embora.

E o que NÃO muda, que é metade do valor de um teste destes: uma carta normal
(fora da Reserved List) continua a vender-se, porque se compra outra vez; e uma
PT da era que não seja RL continua trancada ao Premodern.

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

# As regras tal como estão no repositório desde 2026-09-08: o Legacy é SPML (a
# ordem da alocação e a partilha de compras são as do grupo) e só a RL é que
# muda de língua.
BASE_CFG = {
    "metagame_fontes": {"_default": {"tiers": ["Challenge"], "ligas": False}},
    "metagame_top_n": 2,
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "edicoes": "premodern", "estrita": True,
         "baldes": ["Colecção", "Caixa Reserved List"]},
        {"grupo": "cedh", "formatos": ["cedh"], "dedicado": True,
         "lingua": "en", "acabamento": "nonfoil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "lingua": "en", "acabamento": "foil",
         "por_formato": {"legacy": {"rl_lingua": ["pt", "en"]}}},
    ],
    "venda": {"reservar_rl_formatos": ["legacy"]},
}


def cfg(**venda):
    from mtgvault import sources
    novo = json.loads(json.dumps(BASE_CFG))
    novo["venda"].update(venda)
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return novo


CFG_PATH.write_text(json.dumps(BASE_CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import analysis, db, loadout  # noqa: E402

# (nome, edição, data, reserved). O Mox Diamond é o caso a sério: RL, impressão
# da era (Stronghold, 1998) e as cópias dele na colecção do André são PT.
CATALOGO = [
    ("Mox Diamond", "sth", "1998-03-02", 1),
    ("City of Traitors", "exo", "1998-06-15", 1),
    ("Gaea's Cradle", "usg", "1998-10-12", 1),
    ("Force of Will", "all", "1996-06-10", 1),
    ("Brainstorm", "ice", "1995-06-01", 0),
    ("Swords to Plowshares", "4bb", "1995-04-01", 0),
    ("Island", "4bb", "1995-04-01", 0),
]

# Dois arquétipos de Legacy. Partilham a Force of Will (como na vida real) e cada
# um traz uma RL só sua — é isso que deixa ver a reserva a encolher quando ele
# escolhe um deles.
LOAM = [("Mox Diamond", 4), ("City of Traitors", 2), ("Force of Will", 4),
        ("Brainstorm", 4), ("Island", 20)]
ELVES = [("Gaea's Cradle", 3), ("Force of Will", 4), ("Swords to Plowshares", 4),
         ("Island", 20)]

_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Artifact',2,'',?,?,?,0,?)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i),
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"legacy": "legal", "premodern": "legal",
                         "cedh": "legal", "commander": "legal"}), rl))
    con.commit()
    return con


def listas(con, cartas, n, jogador, fmt="legacy"):
    quando = (date.today() - timedelta(days=3)).isoformat()
    for i in range(n):
        con.execute(
            """INSERT INTO decklists (source, source_key, format, event_name,
               event_date, player, event_tier) VALUES
               ('mtgo', ?, ?, 'Legacy Challenge', ?, ?, 'Challenge')""",
            (f"{jogador}-{i}", fmt, quando, f"{jogador}{i}"))
        did = con.execute("SELECT MAX(id) i FROM decklists").fetchone()["i"]
        for nm, q in cartas:
            con.execute("INSERT INTO decklist_cards (decklist_id, card_name, "
                        "quantity, board) VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def add(con, nm, q=1, finish="nonfoil", lang="pt", sub="Colecção"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,?,'player',?)""",
                (sid, q, finish, lang, sub_id))
    con.commit()


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def caixa(slot, nome, fmt, ref=None, balde="Colecção", **kw):
    d = {"slot": slot, "nome": nome, "formato": fmt, "balde": balde,
         "estado": "permanente", "prioridade": 1}
    if ref:
        d.update({"fonte": "deck", "ref": ref})
    d.update(kw)
    return d


def linha_de(s, nm):
    return next(m for m in s["have"] + s["missing"] if m["nm"] == nm)


def slot_de(rep, slot):
    return next(s for s in rep["slots"] if s["slot"] == slot)


def a_venda_rl(rep):
    """As linhas de RL que SAÍRAM da colecção do ponto de vista desta regra.

    Estas bases não têm `price_history`, por isso a regra dos 5 % manda-as todas
    para `rl_sem_historico` — o que se está a testar aqui é uma decisão ANTERIOR
    a essa (foi reservada ou não foi), e juntar as saídas é o que impede que um
    teste passe por causa da outra regra.
    """
    return rep["venda_rl"] + rep["rl_segurar"] + rep["rl_sem_historico"]


def mundo_com_metagame():
    """Uma base com os dois arquétipos de Legacy e nenhuma caixa com lista."""
    con = base()
    listas(con, LOAM, 9, "loam")
    listas(con, ELVES, 8, "elv")
    analysis.rebuild_archetypes(con, "legacy")
    analysis.rebuild_roles(con, "legacy")
    con.commit()
    return con


# ---------------------------------------------------------------------------
def caso_rl_em_pt_entra_na_caixa_de_legacy():
    """A caixa de Legacy fecha o slot com uma Mox Diamond PT nonfoil.

    Duas regras tinham de se abrir para isto, e é de propósito que são as duas:
    o grupo SPML é *"tudo foil e inglês"* (a RL já podia ser nonfoil, a língua
    não) e uma PT de impressão até ao Scourge está TRANCADA ao Premodern desde
    2026-09-07. Sem a segunda, a carta continuava a ser falta.
    """
    cfg()
    con = base()
    deck(con, "Loam", "legacy", LOAM)
    add(con, "Mox Diamond", 2, lang="pt")
    rep = loadout.report(con, [caixa("legacy", "Legacy — Loam", "legacy", "Loam")])
    s = slot_de(rep, "legacy")
    m = linha_de(s, "Mox Diamond")
    assert m["got"] == 2 and m["comprar"] == 2, m      # a lista pede 4
    assert not m.get("substituto"), m
    print("uma Mox Diamond PT da era fecha slot numa caixa de Legacy")

    # E o que NÃO mudou: uma carta normal em PT continua trancada ao Premodern.
    con2 = base()
    deck(con2, "Loam", "legacy", LOAM)
    add(con2, "Brainstorm", 4, lang="pt")
    s2 = slot_de(loadout.report(con2, [caixa("legacy", "Leg", "legacy", "Loam")]),
                 "legacy")
    m2 = linha_de(s2, "Brainstorm")
    assert m2["got"] == 0 and m2["comprar"] == 4, m2
    print("e uma PT da era que não seja RL continua trancada ao Premodern")


def caso_rl_em_pt_nao_entra_no_cedh():
    """*"(...) mas não para cEDH nem outro formato."* A excepção é de UM formato.

    O cEDH é *"apenas inglês non-foil"* e continua a ser: a mesma cópia que fecha
    o slot do Legacy é falta na caixa de cEDH. E o Modern, que está no MESMO
    grupo do Legacy, também não a aceita — é o que prova que a excepção está no
    `por_formato` e não na regra do grupo.
    """
    cfg()
    con = base()
    deck(con, "cEDH", "cedh", [("Mox Diamond", 1)])
    deck(con, "Mod", "modern", [("Mox Diamond", 4)])
    add(con, "Mox Diamond", 4, lang="pt")
    rep = loadout.report(con, [caixa("cedh", "Blue Farm", "cedh", "cEDH"),
                               caixa("modern", "Modern", "modern", "Mod")])
    for slot in ("cedh", "modern"):
        m = linha_de(slot_de(rep, slot), "Mox Diamond")
        assert m["got"] == 0 and m["comprar"] == m["need"], (slot, m)
    print("a mesma cópia PT não entra no cEDH nem no Modern — a excepção é só "
          "do Legacy")


def caso_um_candidato_de_legacy_reserva_a_rl():
    """Sem deck escolhido, quem segura as cartas é o top-N do metagame.

    É a metade que faz a regra valer alguma coisa hoje: a caixa de Legacy dele
    está `candidata` e vazia, por isso a alocação não lhe dá nada e as cópias de
    RL apareciam todas na lista de venda. Enquanto ele não escolhe, o que a caixa
    vai pedir é o que os candidatos pedem.
    """
    cfg()
    con = mundo_com_metagame()
    add(con, "Mox Diamond", 6, lang="pt")          # 2 acima do playset
    add(con, "Swords to Plowshares", 6, lang="en")  # não é RL: vende-se
    rep = loadout.report(con, [caixa("legacy", "Legacy", "legacy")])
    reservado = {r["nm"]: r for r in rep["reservadas"]}
    assert "Mox Diamond" in reservado, rep["reservadas"]
    assert reservado["Mox Diamond"]["q"] == 2, reservado
    assert reservado["Mox Diamond"]["reason"].startswith("serve Legacy:"), \
        reservado["Mox Diamond"]["reason"]
    assert not a_venda_rl(rep), a_venda_rl(rep)
    # A carta normal que o outro candidato usa continua a vender-se: compra-se
    # outra vez, e segurar a colecção inteira por causa de três listas de
    # metagame era o contrário do que ele pediu.
    assert any(r["nm"] == "Swords to Plowshares" for r in rep["venda"]), rep["venda"]
    print("um candidato de Legacy segura a RL que usaria, e só a RL")

    # E desligar a regra devolve-as à venda — é uma linha de config.
    cfg(reservar_rl_formatos=[])
    rep2 = loadout.report(con, [caixa("legacy", "Legacy", "legacy")])
    assert not rep2["reservadas"] and a_venda_rl(rep2), rep2["reservadas"]
    print("e `reservar_rl_formatos: []` devolve-as à venda")


def caso_ao_escolher_o_deck_a_reserva_encolhe():
    """*"Quando ele escolher o deck de Legacy, a reserva passa a ser só a desse."*

    Com a caixa vazia, os dois candidatos seguram as suas RL. Assim que a caixa
    tem lista, quem manda é a lista: a RL do outro candidato passa a ser
    excedente como qualquer outra cópia.
    """
    cfg()
    con = mundo_com_metagame()
    add(con, "Mox Diamond", 6, lang="pt")        # só o Loam a pede
    add(con, "Gaea's Cradle", 6, lang="pt")      # só o Elves a pede
    rep = loadout.report(con, [caixa("legacy", "Legacy", "legacy")])
    assert {r["nm"] for r in rep["reservadas"]} == {"Mox Diamond", "Gaea's Cradle"}, \
        rep["reservadas"]

    deck(con, "Loam", "legacy", LOAM)
    rep2 = loadout.report(con, [caixa("legacy", "Legacy", "legacy", "Loam")])
    assert {r["nm"] for r in rep2["reservadas"]} == set(), rep2["reservadas"]
    # A caixa levou 4 Mox Diamond (a lista pede 4) e as outras 2 são excedente;
    # da Gaea's Cradle, que nenhum deck escolhido pede, vende-se o que passa do
    # playset — as outras 4 continuam a ser colecção, como qualquer carta.
    assert linha_de(slot_de(rep2, "legacy"), "Mox Diamond")["got"] == 4
    vendido = {r["nm"]: r["q"] for r in a_venda_rl(rep2)}
    assert vendido == {"Mox Diamond": 2, "Gaea's Cradle": 2}, vendido
    print("escolhido o deck, a reserva encolhe para a lista dele")


def caso_a_pt_que_o_premodern_nao_usa_fica_para_o_legacy():
    """O caso a sério: a RL PT que *"não é usada por nenhum deck de Premodern"*.

    Era a maior fatia da lista de venda de 2026-09-08 — Mox Diamond, Gilded
    Drake, Null Rod: PT, que os outros formatos recusavam por serem PT. Com o
    Legacy a aceitá-las, uma cópia que um candidato de Legacy usa deixa de ser
    peso morto e a saída dela passa a ser a reserva, não a venda.
    """
    cfg()
    con = mundo_com_metagame()
    deck(con, "PM", "premodern", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 4, lang="pt")
    add(con, "Mox Diamond", 2, lang="pt")        # abaixo do playset: só a 2ª regra
    add(con, "City of Traitors", 2, lang="pt")
    slots = [caixa("premodern-x", "Premodern", "premodern", "PM"),
             caixa("legacy", "Legacy", "legacy")]
    rep = loadout.report(con, slots)
    assert rep["premodern"]["activo"], "há caixa de Premodern: a regra corre"
    reservado = {r["nm"]: r["q"] for r in rep["reservadas"]}
    assert reservado == {"Mox Diamond": 2, "City of Traitors": 2}, reservado
    assert all(r["reason"].startswith("serve Legacy:") for r in rep["reservadas"])
    assert not [r for r in a_venda_rl(rep)
                if r.get("porque_venderia", r["reason"])
                == loadout.RAZAO_PREMODERN], a_venda_rl(rep)
    print("a RL PT que o Premodern não usa fica reservada para o Legacy em vez "
          "de ir à venda")

    # Sem a regra do PT no Legacy, as mesmas cópias iam à venda pelo motivo do
    # Premodern — é a medida de quanto esta mudança vale.
    cfg(reservar_rl_formatos=[])
    rep2 = loadout.report(con, slots)
    assert ({r["nm"] for r in a_venda_rl(rep2)}
            == {"Mox Diamond", "City of Traitors"}), a_venda_rl(rep2)
    print("e sem a regra as mesmas duas iam à venda")


def run():
    for fn in (caso_rl_em_pt_entra_na_caixa_de_legacy,
               caso_rl_em_pt_nao_entra_no_cedh,
               caso_um_candidato_de_legacy_reserva_a_rl,
               caso_ao_escolher_o_deck_a_reserva_encolhe,
               caso_a_pt_que_o_premodern_nao_usa_fica_para_o_legacy):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
