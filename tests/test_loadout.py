"""Loadout: alocar a coleção aos decks que ficam montados em deckbox.

O que aqui se tranca são as regras que custam dinheiro se partirem em silêncio:

  1. uma cópia física entra numa caixa e SÓ NUMA — quem ganha é a prioridade;
  2. a tranca do PT ("as cartas de Premodern são PT e NÃO entram noutros
     formatos"), com a excepção necessária: uma PT da era que já vive na caixa
     de outro deck é desse deck;
  2b. e o outro lado dela: uma caixa de Premodern NÃO OLHA para a Caixa Reserved
     List ("na Caixa RL só estão cartas RL em inglês") — nem aloca de lá, nem as
     conta como substituto; para essas caixas a carta é falta. As mesmas cópias
     continuam a servir o Legacy;
  3. a regra do foil ("Standard/Pioneer/Modern/Legacy são todas foil menos as
     Reserved List") — uma nonfoil não fecha o slot, aparece como substituto;
  4. a coleção de colecionador nunca entra, e as reservas por deck respeitam-se;
  5. o backup: 4 por carta na COLEÇÃO INTEIRA (não 4 por balde) e 1 por deck de
     Commander; básicas nunca se vendem;
  6. um substituto NUNCA vai para a venda — foi o erro que a primeira versão
     fez: mandava vender as 4 Opalescence EN que faltam à Enchantress.

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# O loadout lê o config para as `regras_colecao`; um config próprio impede que o
# teste passe a depender de o André não mexer no dele.
CFG = {"regras_colecao": {"Blue Farm": {"reter_extras_meses": 6}}}
_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import db, loadout  # noqa: E402

# (nome, edição, data, reserved). A data decide se a impressão é "da era
# Premodern" (até ao Scourge, 2003-05-26).
CATALOGO = [
    ("Swords to Plowshares", "4bb", "1995-04-01", 0),
    ("Replenish", "uds", "1999-06-07", 1),
    ("Opalescence", "uds", "1999-06-07", 1),
    ("Lotus Petal", "tmp", "1997-10-14", 0),
    ("Kappa Cannoneer", "mh3", "2024-06-14", 0),
    ("Thoughtcast", "mrd", "2003-10-02", 0),
    ("Ancient Tomb", "tmp", "1997-10-14", 1),
    ("Sol Ring", "c21", "2021-04-23", 0),
    ("Island", "4bb", "1995-04-01", 0),
]


_ABERTAS = []      # segura os context managers: sem isto o GC fecha a ligação


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
               VALUES (?,?,?,?,'S',?,'en','rare','Instant',1,'W',?,?,?,0,?)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]),
             rel, json.dumps({"legacy": "legal", "commander": "legal",
                              "premodern": "legal", "modern": "legal"}), rl))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub=None, purpose="player",
        reserved_deck_id=None):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = None
    if sub:
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
        sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                             (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id, reserved_deck_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (sid, q, finish, lang, purpose, sub_id, reserved_deck_id))
    con.commit()


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return did


def slot(nome, fmt, ref, **kw):
    d = {"slot": nome.lower(), "nome": nome, "formato": fmt, "fonte": "deck",
         "ref": ref, "prioridade": kw.pop("prioridade", 1)}
    d.update(kw)
    return d


def por_nome(rep):
    return {s["nome"]: s for s in rep["slots"]}


# ---------------------------------------------------------------------------
def caso_uma_copia_uma_caixa():
    """Duas caixas, uma cópia: ganha a de prioridade mais alta, e o conflito diz
    quem ficou sem. Somar coberturas independentes dava 100% às duas."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 1)])
    deck(con, "B", "legacy", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1),
                               slot("B", "legacy", "B", prioridade=2)])
    s = por_nome(rep)
    assert s["A"]["pct"] == 100 and s["B"]["pct"] == 0, (s["A"]["pct"], s["B"]["pct"])
    c = [x for x in rep["conflitos"] if x["nm"] == "Sol Ring"]
    assert c and c[0]["ficam_com"] == ["A"] and c[0]["ficam_sem"] == ["B"], c
    print("uma cópia física serve uma caixa só; o conflito diz quem fica sem")

    # A prioridade manda: invertida, ganha o B.
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=2),
                               slot("B", "legacy", "B", prioridade=1)])
    s = por_nome(rep)
    assert s["B"]["pct"] == 100 and s["A"]["pct"] == 0
    print("a prioridade do config decide quem ganha o conflito")


def caso_falta_partilhada_nao_e_conflito():
    """Duas caixas querem uma carta que ele NÃO tem: é falta, não disputa.
    Chamar-lhe conflito enchia a página de ruído e escondia os reais."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 1)])
    deck(con, "B", "legacy", [("Sol Ring", 1)])
    rep = loadout.report(con, [slot("A", "legacy", "A"), slot("B", "legacy", "B", prioridade=2)])
    assert not rep["conflitos"], rep["conflitos"]
    print("carta que ninguém tem não entra nos conflitos")


def caso_premodern_so_pt():
    """Slot de Premodern só fecha com PT; a EN fica como SUBSTITUTO ('serve mas
    não é PT'), que é diferente de não ter a carta.

    As EN estão no SPML de propósito: as da Caixa RL nem chegam a ser vistas
    (ver `caso_premodern_nao_ve_a_caixa_rl`), e este caso é o da língua.
    """
    con = base()
    deck(con, "Replenish", "premodern", [("Opalescence", 4)])
    add(con, "Opalescence", 2, lang="pt", sub="Premodern (geral)")
    add(con, "Opalescence", 4, lang="en", sub="SPML")
    rep = loadout.report(con, [slot("Replenish", "premodern", "Replenish",
                                    lingua="pt", balde="Premodern (geral)")])
    s = por_nome(rep)["Replenish"]
    assert s["tenho"] == 2, s["tenho"]
    assert len(s["subs"]) == 1 and s["subs"][0]["alt"] == {"não é PT": 4}, s["subs"]
    print("slot de Premodern: só PT fecha; as EN aparecem como substituto")


def caso_premodern_nao_ve_a_caixa_rl():
    """André, 2026-09-07: 'O Premodern não é para olhar para a minha Caixa RL,
    pois o Premodern só vai usar as cartas em Português; na Caixa RL só estão
    cartas RL em inglês.'

    É mais forte que a regra da língua: as 4 Opalescence EN da Caixa RL não são
    substituto da Enchantress — para essa caixa a carta é FALTA, compra-se em PT.
    As mesmas cópias continuam a servir o Legacy (RL pode ser nonfoil).
    """
    con = base()
    deck(con, "Ench", "premodern", [("Opalescence", 4)])
    add(con, "Opalescence", 1, lang="pt", sub="Premodern (geral)")
    add(con, "Opalescence", 4, lang="en", sub="Caixa Reserved List")
    pm = slot("Ench", "premodern", "Ench", lingua="pt", balde="Premodern (geral)")
    rep = loadout.report(con, [pm])
    s = por_nome(rep)["Ench"]
    assert s["tenho"] == 1, s["tenho"]                     # só a PT
    assert not s["subs"], s["subs"]                        # a Caixa RL nem aparece
    falta = [m for m in s["missing"] if m["nm"] == "Opalescence"][0]
    assert falta["missing"] == 3 and falta["alt"] == {}, falta
    print("caixa de Premodern não vê a Caixa RL: é falta, não substituto")

    # E sem a marca de substituto, o excedente do playset vai para a venda a
    # confirmar (são Reserved List), como o André quer.
    assert not [r for r in rep["guardar"] if r["nm"] == "Opalescence"], rep["guardar"]
    vrl = [r for r in rep["venda_rl"] if r["nm"] == "Opalescence"]
    assert sum(r["q"] for r in vrl) == 1, vrl        # 5 cópias, playset 4 -> 1

    # As mesmas cópias continuam disponíveis para o Legacy.
    deck(con, "Leg", "legacy", [("Opalescence", 4)])
    rep = loadout.report(con, [pm, slot("Leg", "legacy", "Leg", prioridade=2,
                                        acabamento="foil", balde="SPML")])
    s = por_nome(rep)["Leg"]
    assert s["tenho"] == 4, s["tenho"]
    assert [l["sub"] for l in s["have"][0]["lotes"]] == ["Caixa Reserved List"], s["have"]
    print("as cópias da Caixa RL continuam a servir o Legacy")


def caso_pt_da_era_trancada_ao_premodern():
    """Uma PT de impressão da era Premodern não é alocada a outro formato.
    Palavras dele: 'essas cartas NÃO entram para outros formatos!!'"""
    con = base()
    deck(con, "Legacy", "legacy", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 1, lang="pt", sub="Premodern (geral)")
    rep = loadout.report(con, [slot("Legacy", "legacy", "Legacy", balde="SPML")])
    s = por_nome(rep)["Legacy"]
    assert s["tenho"] == 0, s["tenho"]
    assert "PT da era Premodern" in "".join(s["missing"][0]["alt"]), s["missing"][0]["alt"]
    print("PT da era Premodern não vai para outro formato")

    # Mas uma PT MODERNA (impressão posterior ao Scourge) não está trancada.
    add(con, "Sol Ring", 1, lang="pt", finish="foil", sub="SPML")
    deck(con, "L2", "legacy", [("Sol Ring", 1)])
    rep = loadout.report(con, [slot("L2", "legacy", "L2", balde="SPML")])
    assert por_nome(rep)["L2"]["pct"] == 100
    print("PT de impressão moderna não está trancada")


def caso_excepcao_do_balde():
    """A tranca do PT não desmonta um deck já montado: uma PT da era que vive na
    CAIXA de outro slot é desse deck (o Blue Farm tem lá Lotus Petal PT)."""
    con = base()
    deck(con, "Blue Farm", "cedh", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 1, lang="pt", sub="Blue Farm")
    rep = loadout.report(con, [slot("Blue Farm", "cedh", "Blue Farm", balde="Blue Farm")])
    assert por_nome(rep)["Blue Farm"]["pct"] == 100
    print("PT da era no balde do próprio deck continua a servir esse deck")


def caso_foil():
    """Standard/Pioneer/Modern/Legacy: só foil, menos as da Reserved List."""
    con = base()
    deck(con, "M", "modern", [("Kappa Cannoneer", 2), ("Ancient Tomb", 2)])
    add(con, "Kappa Cannoneer", 1, finish="foil", sub="SPML")
    add(con, "Kappa Cannoneer", 3, finish="nonfoil", sub="SPML")
    add(con, "Ancient Tomb", 2, finish="nonfoil", sub="Caixa Reserved List")
    rep = loadout.report(con, [slot("M", "modern", "M", acabamento="foil", balde="SPML")])
    s = por_nome(rep)["M"]
    # 1 Kappa foil + 2 Ancient Tomb (RL, podem ser nonfoil) = 3 de 4
    assert s["tenho"] == 3, s["tenho"]
    falta = [m for m in s["missing"] if m["nm"] == "Kappa Cannoneer"][0]
    assert falta["alt"] == {"não é foil": 3}, falta["alt"]
    print("só foil fecha o slot; a Reserved List pode ser nonfoil")


def caso_colecionador_e_reservas_fora():
    con = base()
    did = deck(con, "A", "legacy", [("Sol Ring", 3)])
    outro = deck(con, "Outro", "legacy", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil", purpose="collector")
    add(con, "Sol Ring", 1, finish="foil", reserved_deck_id=outro)
    add(con, "Sol Ring", 1, finish="foil")
    rep = loadout.report(con, [slot("A", "legacy", "A")])
    assert por_nome(rep)["A"]["tenho"] == 1, por_nome(rep)["A"]["tenho"]
    assert did
    print("colecionador e cartas reservadas a outro deck ficam de fora")


def caso_backup_e_venda():
    """4 por carta na COLEÇÃO INTEIRA (não 4 por balde) e 1 por deck de Commander.
    Básicas nunca se vendem."""
    con = base()
    deck(con, "EDH", "cedh", [("Sol Ring", 1)])
    # 4 no SPML + 4 na Caixa RL = 8 cópias da mesma carta: o playset são 4.
    add(con, "Thoughtcast", 4, finish="foil", sub="SPML")
    add(con, "Thoughtcast", 4, finish="foil", sub="Caixa Reserved List")
    add(con, "Sol Ring", 3, sub="Blue Farm")       # caixa de Commander: 1 chega
    add(con, "Island", 20, sub="SPML")
    rep = loadout.report(con, [slot("EDH", "cedh", "EDH", balde="Blue Farm")])

    tc = [r for r in rep["venda"] if r["nm"] == "Thoughtcast"]
    assert sum(r["q"] for r in tc) == 4, tc
    print("playset de 4 conta a coleção toda, não 4 por balde")

    assert not [r for r in rep["venda"] + rep["venda_rl"] if r["nm"] == "Island"], \
        "sugeriu vender terras básicas"
    print("terras básicas nunca vão para a venda")

    # A caixa de Commander tem `reter_extras_meses`: os 2 extras guardam-se e
    # dizem-no, em vez de entrarem na venda por uma regra que ainda não corre.
    sr = [r for r in rep["retidos"] if r["nm"] == "Sol Ring"]
    assert sum(r["q"] for r in sr) == 2, (sr, rep["venda"])
    assert not [r for r in rep["venda"] if r["nm"] == "Sol Ring"]
    print("extras de uma caixa de Commander ficam retidos (6 meses), não à venda")


def caso_substituto_nao_se_vende():
    """O erro caro: a Enchantress precisa de Opalescence, ele tem 4 EN noutro
    balde, a regra do PT põe-nas fora do deck — e o playset de 4 mandava
    vendê-las. São exactamente as cartas que lhe faltam.

    (O caso original eram as 4 EN da Caixa RL; desde 2026-09-07 essas já nem são
    vistas pelo Premodern e vão mesmo para a venda a confirmar — a saída
    `guardar` continua a valer para os outros baldes e para o acabamento.)
    """
    con = base()
    deck(con, "Ench", "premodern", [("Opalescence", 4)])
    add(con, "Opalescence", 3, lang="pt", sub="Premodern (geral)")
    add(con, "Opalescence", 4, lang="en", sub="SPML")
    rep = loadout.report(con, [slot("Ench", "premodern", "Ench", lingua="pt",
                                    balde="Premodern (geral)")])
    # 7 cópias, playset 4 -> 3 de excesso. Saem das EN, que são as livres — mas
    # são as que faltam ao deck, por isso guardam-se em vez de irem à venda.
    assert not [r for r in rep["venda"] + rep["venda_rl"] if r["nm"] == "Opalescence"]
    g = [r for r in rep["guardar"] if r["nm"] == "Opalescence"]
    assert sum(r["q"] for r in g) == 3, g
    assert g[0]["lang"] == "en" and "Ench" in g[0]["reason"], g
    print("substitutos não se vendem — guardam-se e dizem que deck servem")


def caso_variantes():
    """Variantes partilham a caixa: leva-se a união, cada carta na quantidade
    máxima que alguma variante pede, e marca-se o que só uma delas usa."""
    con = base()
    deck(con, "Base", "modern", [("Kappa Cannoneer", 2), ("Thoughtcast", 4)])
    deck(con, "Var", "modern", [("Kappa Cannoneer", 4), ("Sol Ring", 1)])
    s = loadout.resolve_slots(con, [slot("Modern", "modern", "Base",
                                         variantes=["Var"])])[0]
    cartas = {n: q for _b, n, q in s["cards"]}
    assert cartas == {"Kappa Cannoneer": 4, "Thoughtcast": 4, "Sol Ring": 1}, cartas
    assert s["so_de_variante"] == {"Sol Ring": ["Var"]}, s["so_de_variante"]
    print("variantes: união das cartas, e marca-se o que é só de uma")


def caso_slot_vazio():
    """Um slot sem deck escolhido fica vazio e assinalado — não se escolhe por ele."""
    con = base()
    rep = loadout.report(con, [dict(slot("Legacy", "legacy", None),
                                    por_confirmar=True)])
    s = por_nome(rep)["Legacy"]
    assert s["vazio"] and s["precisa"] == 0 and "por confirmar" in s["nota"], s["nota"]
    print("slot sem deck escolhido fica vazio e assinalado")


def caso_preco_foil():
    """O custo de fechar um deck de foil tem de usar o preço FOIL. Com o nonfoil
    (o que o wantlist.cheapest_price dá) vinha sistematicamente por baixo."""
    con = base()
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name='Kappa Cannoneer'"
                      ).fetchone()["scryfall_id"]
    for fin, tr in (("nonfoil", 2.0), ("foil", 30.0)):
        con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date, trend)
                       VALUES (?, 'cardmarket', ?, '2026-09-07', ?)""", (sid, fin, tr))
    con.commit()
    assert loadout.card_price(con, "Kappa Cannoneer", "foil") == (30.0, "foil")
    assert loadout.card_price(con, "Kappa Cannoneer", "nonfoil") == (2.0, "nonfoil")
    # Sem preço foil, cai para o nonfoil MAS diz que é nonfoil, para quem mostra
    # poder marcar a estimativa como estando por baixo.
    assert loadout.card_price(con, "Sol Ring", "foil") == (None, None)
    print("o custo de um deck de foil usa o preço do foil")


def run():
    for fn in (caso_uma_copia_uma_caixa, caso_falta_partilhada_nao_e_conflito,
               caso_premodern_so_pt, caso_premodern_nao_ve_a_caixa_rl,
               caso_pt_da_era_trancada_ao_premodern,
               caso_excepcao_do_balde, caso_foil, caso_colecionador_e_reservas_fora,
               caso_backup_e_venda, caso_substituto_nao_se_vende, caso_variantes,
               caso_slot_vazio, caso_preco_foil):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
