"""Loadout: alocar a coleção aos decks que ficam montados em deckbox.

O que aqui se tranca são as regras que custam dinheiro se partirem em silêncio:

  1. uma cópia física entra numa caixa e SÓ NUMA — quem ganha é a prioridade;
  2. a tranca do PT ("as cartas de Premodern são PT e NÃO entram noutros
     formatos"), com a excepção necessária: uma PT da era que já vive na caixa
     de outro deck é desse deck;
  2b. e o outro lado dela: uma caixa de Premodern só vê cópias PT ("o Premodern
     só usa em PT, mesmo eu tendo a carta em inglês") e só nos baldes de
     colecção — nem aloca uma EN, nem a conta como substituto; para essas caixas
     a carta é falta a comprar em PT. Da Caixa Reserved List vê a metade PT e
     não vê a metade EN ("na Caixa RL, as PT e as ENG estão separadas"); as EN
     continuam a servir o Legacy;
  3. a regra do foil ("Standard/Pioneer/Modern/Legacy são todas foil menos as
     Reserved List") — uma nonfoil não fecha o slot, aparece como substituto;
  4. a coleção de colecionador nunca entra, e as reservas por deck respeitam-se;
  5. o backup: 4 por carta na COLEÇÃO INTEIRA (não 4 por balde) e 1 por deck de
     Commander; básicas nunca se vendem;
  6. um substituto NUNCA vai para a venda — foi o erro que a primeira versão
     fez: mandava vender as cartas que faltam a uma caixa e só falham no
     acabamento (as EN do Premodern deixaram de ser substituto, ver 2b);
  7. ONDE ESTÁ A CARTA (André, 2026-09-07): uma carta que a alocação deu a outra
     caixa NÃO é falta nem compra — diz-se em que caixa está e quantas, e não
     soma ao custo de fechar. Era isto que mandava comprar quatro Swords to
     Plowshares para cada uma das seis caixas de Premodern;
  8. as REGRAS POR GRUPO DE FORMATO e a ordem que ele ditou a seguir
     ("Premodern > cEDH > Duel Commander > Pauper > SPML", os decks vigiados
     primeiro dentro do grupo, cEDH só inglês non-foil, Duel Commander só foil,
     Pauper foil quando há, e o Pauper a ir buscar ao SPML o que precisa).
     Uma cópia que está DENTRO da caixa do próprio deck escapa a estas regras —
     senão a regra nova desmontava no papel um deck que está montado.
  9. os DECKS PERMANENTES (André, 2026-09-07: *"os decks que eu pedi para serem
     permanentes são a minha prioridade máxima!"*): um permanente aloca antes de
     qualquer candidato, mesmo que o candidato seja de um grupo de formato que
     vem primeiro; e marcar um candidato como permanente po-lo a receber cartas;
 10. a ARRUMAÇÃO FÍSICA: o plano de movimentos é a diferença entre onde a carta
     está e onde deve estar, o "já arrumei" persiste a alocação (e é idempotente),
     e uma cópia já arrumada numa caixa escapa às regras de material — a versão
     nova da excepção do balde, agora que a caixa já não é um balde.

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
CFG = {"regras_colecao": {"Blue Farm": {"reter_extras_meses": 6},
                          "Cloud": {"reter_extras_meses": 6},
                          "Cloud cEDH": {"reter_extras_meses": 6},
                          "Pauper Affinity": {"reter_extras_meses": 6}},
       "decks_vigiados": ["Oswald"]}
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


def deck(con, nome, fmt, cartas, side=()):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for board, linhas in (("main", cartas), ("side", side)):
        for nm, q in linhas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?,?,?,?)", (did, nm, q, board))
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


def preco(con, nm, finish, trend):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date, trend)
                   VALUES (?, 'cardmarket', ?, '2026-09-07', ?)""", (sid, finish, trend))
    con.commit()


def caso_noutra_caixa_nao_e_compra():
    """André, 2026-09-07: *"indicas onde está a carta, para, se eu quiser ir jogar,
    saber onde ir buscar e não ter que comprar múltiplos para todos."*

    Quatro Swords to Plowshares pedidas por três caixas: uma fica com elas, as
    outras duas dizem "em <caixa>" e **não somam ao custo**. Antes desta regra o
    vault pedia 8 Swords compradas para tapar um buraco que não existe.
    """
    con = base()
    preco(con, "Swords to Plowshares", "foil", 1.5)
    for nome in ("A", "B", "C"):
        deck(con, nome, "legacy", [("Swords to Plowshares", 4)])
    # Foil porque o grupo SPML é "tudo foil e inglês" (a regra dele de
    # 2026-09-07); o que este caso tranca é o "noutra caixa", não o acabamento.
    add(con, "Swords to Plowshares", 4, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1, balde="SPML"),
                               slot("B", "legacy", "B", prioridade=2, balde="SPML"),
                               slot("C", "legacy", "C", prioridade=3, balde="SPML")])
    s = por_nome(rep)

    assert s["A"]["pct"] == 100 and s["A"]["comprar"] == 0 and s["A"]["noutra"] == 0
    for nome in ("B", "C"):
        m = [x for x in s[nome]["missing"] if x["nm"] == "Swords to Plowshares"][0]
        assert m["missing"] == 4, m
        assert m["noutra"] == {"A": 4}, m["noutra"]
        assert m["comprar"] == 0 and m["cost"] == 0, m
        assert s[nome]["comprar"] == 0 and s[nome]["noutra"] == 4, s[nome]
        assert s[nome]["custo"] == 0, s[nome]["custo"]
        assert [x["nm"] for x in s[nome]["noutra_caixa"]] == ["Swords to Plowshares"]
    assert rep["custo_total"] == 0, rep["custo_total"]
    assert rep["comprar_total"] == 0 and rep["noutra_total"] == 8
    print("carta que está noutra caixa diz onde está e não entra na compra")

    # E continua a ser uma carta partilhada: quem a TEM é o A, quem a vai BUSCAR
    # são o B e o C. É a mesma leitura da antiga secção de conflitos.
    c = [x for x in rep["conflitos"] if x["nm"] == "Swords to Plowshares"][0]
    assert c["ficam_com"] == ["A"] and c["ficam_sem"] == ["B", "C"], c
    print("as partilhadas dizem quem a tem e quem a vai buscar")


def caso_noutra_caixa_e_compra_misturadas():
    """O caso meio: a caixa precisa de 4, só existem 2 e foram para outra. Duas
    vão-se buscar, DUAS compram-se — e o custo é só o das duas."""
    con = base()
    preco(con, "Swords to Plowshares", "foil", 10.0)
    deck(con, "A", "legacy", [("Swords to Plowshares", 4)])
    deck(con, "B", "legacy", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 2, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1, balde="SPML"),
                               slot("B", "legacy", "B", prioridade=2, balde="SPML")])
    b = por_nome(rep)["B"]
    m = b["missing"][0]
    assert m["missing"] == 4 and m["noutra"] == {"A": 2} and m["comprar"] == 2, m
    assert m["cost"] == 20.0 and b["custo"] == 20.0, (m, b["custo"])
    assert b["comprar"] == 2 and b["noutra"] == 2, b
    print("metade noutra caixa, metade a comprar: o custo é só o da metade")

    # O A, que também não fecha (precisa de 4 e só levou 2), não tem para onde ir
    # buscar: as cópias são dele. Para ele é compra a sério.
    a = por_nome(rep)["A"]
    assert a["noutra"] == 0 and a["comprar"] == 2 and a["custo"] == 20.0, a
    print("a caixa que já tem as cópias não se vai buscar a si própria")


def caso_noutra_caixa_nao_conta_a_mesma_copia_duas_vezes():
    """A mesma carta no main E no side são DUAS linhas de falta. Se cada uma
    olhar para a caixa do lado por si, prometem a mesma cópia física duas vezes —
    e o "ir buscar" fica maior do que o que lá está. É a mesma armadilha do
    `livre`, um nível acima."""
    con = base()
    preco(con, "Swords to Plowshares", "foil", 2.0)
    deck(con, "A", "legacy", [("Swords to Plowshares", 4)])
    deck(con, "B", "legacy", [("Swords to Plowshares", 3)],
         side=[("Swords to Plowshares", 2)])
    add(con, "Swords to Plowshares", 4, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1, balde="SPML"),
                               slot("B", "legacy", "B", prioridade=2, balde="SPML")])
    b = por_nome(rep)["B"]
    # O A tem 4; o B pede 5. Vai buscar 4 (não 5) e compra 1.
    assert b["noutra"] == 4 and b["comprar"] == 1, b
    assert b["custo"] == 2.0, b["custo"]
    print("main + side não reclamam a mesma cópia física duas vezes")


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
    """André, 2026-09-07: *"O Premodern só usa em PT, mesmo eu tendo a carta em
    inglês."* Uma EN não fecha o slot, e também NÃO é substituto: para uma caixa
    de Premodern a carta é falta, e compra-se em PT.

    (Até esta ordem as EN apareciam como substituto — "serve mas não é PT". Ele
    já decidiu que não abre a excepção, e um substituto que nunca se usa só faz
    a página parecer mais cheia do que a caixa está.)
    """
    con = base()
    deck(con, "Replenish", "premodern", [("Opalescence", 4)])
    add(con, "Opalescence", 2, lang="pt", sub="Premodern (geral)")
    add(con, "Opalescence", 4, lang="en", sub="SPML")
    rep = loadout.report(con, [slot("Replenish", "premodern", "Replenish",
                                    lingua="pt", balde="Premodern (geral)")])
    s = por_nome(rep)["Replenish"]
    assert s["tenho"] == 2, s["tenho"]
    assert not s["subs"], s["subs"]
    falta = [m for m in s["missing"] if m["nm"] == "Opalescence"][0]
    assert falta["alt"] == {} and falta["comprar"] == 2, falta
    print("slot de Premodern: a EN não fecha nem é substituto — compra-se em PT")


def caso_premodern_e_a_caixa_rl_partida_em_pt_e_en():
    """André, 2026-09-07 (a corrigir a ordem da manhã): *"Na Caixa RL, as PT e as
    ENG estão separadas."*

    A Caixa RL é UM balde no config e DUAS caixas na estante. A caixa de
    Premodern vê a metade PT e não vê a metade EN — e a localização di-lo, para
    ele saber a que caixa ir: `Caixa RL (PT)` / `Caixa RL (EN)`.
    """
    con = base()
    deck(con, "Ench", "premodern", [("Opalescence", 4)])
    add(con, "Opalescence", 1, lang="pt", sub="Premodern (geral)")
    add(con, "Opalescence", 4, lang="en", sub="Caixa Reserved List")
    pm = slot("Ench", "premodern", "Ench", lingua="pt", balde="Premodern (geral)")
    rep = loadout.report(con, [pm])
    s = por_nome(rep)["Ench"]
    assert s["tenho"] == 1, s["tenho"]                     # só a PT
    assert not s["subs"], s["subs"]                        # as EN nem aparecem
    falta = [m for m in s["missing"] if m["nm"] == "Opalescence"][0]
    assert falta["missing"] == 3 and falta["alt"] == {}, falta
    # E não é "está noutra caixa" nenhuma: a cópia que a caixa não vê não pode
    # aparecer como "vai lá buscar" — para o Premodern é compra em PT.
    assert falta["noutra"] == {} and falta["comprar"] == 3, falta
    print("Opalescence EN na Caixa RL não conta para a Enchantress")

    # A mesma carta, na mesma Caixa RL, mas em PT: essa conta e fecha o slot.
    add(con, "Opalescence", 3, lang="pt", sub="Caixa Reserved List")
    rep2 = loadout.report(con, [pm])
    s2 = por_nome(rep2)["Ench"]
    assert s2["pct"] == 100 and not s2["missing"], (s2["pct"], s2["missing"])
    assert s2["origens"] == {"Caixa RL (PT)": 3, "Premodern (geral)": 1}, s2["origens"]
    print("Opalescence PT na Caixa RL conta — e a localização diz 'Caixa RL (PT)'")

    # E sem a marca de substituto, o excedente do playset vai para a venda a
    # confirmar (são Reserved List), como o André quer.
    assert not [r for r in rep["guardar"] if r["nm"] == "Opalescence"], rep["guardar"]
    vrl = [r for r in rep["venda_rl"] if r["nm"] == "Opalescence"]
    assert sum(r["q"] for r in vrl) == 1, vrl        # 5 cópias, playset 4 -> 1
    assert vrl[0]["local"] == "Caixa RL (EN)", vrl[0]["local"]

    # As mesmas cópias EN continuam disponíveis para o Legacy.
    deck(con, "Leg", "legacy", [("Opalescence", 4)])
    rep = loadout.report(con, [pm, slot("Leg", "legacy", "Leg", prioridade=2,
                                        acabamento="foil", balde="SPML")])
    s = por_nome(rep)["Leg"]
    assert s["tenho"] == 4, s["tenho"]
    assert s["origens"] == {"Caixa RL (EN)": 4}, s["origens"]
    print("as cópias EN da Caixa RL continuam a servir o Legacy")


def caso_premodern_nao_tira_de_caixa_de_outro_deck():
    """Uma PT que vive DENTRO da caixa de outro deck montado (Blue Farm) não é
    material para montar um deck de Premodern: está num deck. A caixa de
    Premodern vê o seu balde, o SPML e a Caixa RL (PT) — mais nada."""
    con = base()
    deck(con, "Ench", "premodern", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 1, lang="pt", sub="Blue Farm")
    rep = loadout.report(con, [slot("Ench", "premodern", "Ench", lingua="pt",
                                    balde="Premodern (geral)")])
    s = por_nome(rep)["Ench"]
    assert s["tenho"] == 0 and s["missing"][0]["comprar"] == 1, s
    assert not s["subs"], s["subs"]
    print("a caixa de Premodern não tira cartas de dentro de outro deck")


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

    # Mas uma PT MODERNA (impressão posterior ao Scourge) não está trancada — vai
    # para uma caixa que não exija inglês (o Duel Commander só exige foil).
    add(con, "Sol Ring", 1, lang="pt", finish="foil", sub="SPML")
    deck(con, "L2", "duel-commander", [("Sol Ring", 1)])
    rep = loadout.report(con, [slot("L2", "duel-commander", "L2")])
    assert por_nome(rep)["L2"]["pct"] == 100
    print("PT de impressão moderna não está trancada")


def caso_excepcao_do_balde():
    """Uma regra de material nova não desmonta um deck que está montado: a cópia
    que vive DENTRO da caixa do próprio deck é desse deck.

    O caso original era a tranca do PT (o Blue Farm tem lá um Lotus Petal PT da
    era). Desde as regras por formato (2026-09-07) vale para todas: o cEDH passou
    a ser "apenas inglês non-foil", e sem esta excepção a mesma cópia PT — que
    está fisicamente dentro da caixa — deixava de contar."""
    con = base()
    deck(con, "Blue Farm", "cedh", [("Lotus Petal", 1), ("Sol Ring", 1)])
    add(con, "Lotus Petal", 1, lang="pt", sub="Blue Farm")
    add(con, "Sol Ring", 1, finish="foil", sub="Blue Farm")   # foil num slot nonfoil
    rep = loadout.report(con, [slot("Blue Farm", "cedh", "Blue Farm", balde="Blue Farm")])
    assert por_nome(rep)["Blue Farm"]["pct"] == 100, por_nome(rep)["Blue Farm"]
    print("o que está dentro da caixa do próprio deck escapa às regras de material")

    # Fora da caixa dele, a regra manda: a mesma foil no SPML já não serve.
    con = base()
    deck(con, "Blue Farm", "cedh", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("Blue Farm", "cedh", "Blue Farm", balde="Blue Farm")])
    s = por_nome(rep)["Blue Farm"]
    assert s["tenho"] == 0 and s["missing"][0]["alt"] == {"não é nonfoil": 1}, s
    print("mas fora da caixa a regra do cEDH manda: foil não serve")


def caso_ordem_dos_grupos_de_formato():
    """André, 2026-09-07: *"Ordem de prioridade na alocação: Premodern > cEDH >
    Duel Commander > Pauper > SPML."*

    A ordem já não são os números soltos do config: são os grupos de formato, e
    o `prioridade` de cada slot é só o desempate DENTRO do grupo. Aqui os números
    do config estão de propósito ao contrário da ordem certa."""
    con = base()
    for nome, fmt in (("PM", "premodern"), ("CE", "cedh"), ("DC", "duel-commander"),
                      ("PA", "pauper"), ("SP", "legacy")):
        deck(con, nome, fmt, [("Sol Ring", 1)])
    slots = [slot("SP", "legacy", "SP", prioridade=1),
             slot("PA", "pauper", "PA", prioridade=2),
             slot("DC", "duel-commander", "DC", prioridade=3),
             slot("CE", "cedh", "CE", prioridade=4),
             slot("PM", "premodern", "PM", prioridade=5)]
    ordem = [s["nome"] for s in loadout.resolve_slots(con, slots)]
    assert ordem == ["PM", "CE", "DC", "PA", "SP"], ordem
    print("a ordem é a dos grupos de formato, não a dos números do config")

    # E é a ordem que decide quem fica com a cópia: uma Sol Ring foil PT moderna
    # serve o Duel Commander e o Pauper; fica com o DC, que vem antes.
    add(con, "Sol Ring", 1, finish="foil", lang="pt", sub="SPML")
    rep = loadout.report(con, [slot("PA", "pauper", "PA", prioridade=1),
                               slot("DC", "duel-commander", "DC", prioridade=9)])
    s = por_nome(rep)
    assert s["DC"]["pct"] == 100 and s["PA"]["pct"] == 0, s
    print("o Duel Commander escolhe antes do Pauper, mesmo com prioridade pior")


def caso_vigiado_escolhe_primeiro_dentro_do_grupo():
    """André, 2026-09-07: *"Os decks vigiados têm prioridade para ficarem com as
    cartas, desde que respeitem as regras."* Dentro do mesmo grupo, o vigiado vem
    à frente — e "desde que respeitem as regras" é literal: se a cópia não servir
    o vigiado, ele não a leva à mesma."""
    con = base()
    deck(con, "Oswald", "modern", [("Kappa Cannoneer", 1)])
    deck(con, "Outro", "modern", [("Kappa Cannoneer", 1)])
    add(con, "Kappa Cannoneer", 1, finish="foil", sub="SPML")
    # "Oswald" está em `decks_vigiados` (config deste teste); "Outro" não.
    outro = slot("Outro", "modern", "Outro", prioridade=1, balde="SPML")
    oswald = slot("Oswald", "modern", "Oswald", prioridade=9, balde="SPML")
    rep = loadout.report(con, [outro, oswald])
    assert por_nome(rep)["Oswald"]["pct"] == 100 and por_nome(rep)["Outro"]["pct"] == 0
    print("o deck vigiado escolhe antes, mesmo com o pior `prioridade` do config")

    # Entre dois não-vigiados volta a mandar o `prioridade` do config.
    deck(con, "Terceiro", "modern", [("Kappa Cannoneer", 1)])
    rep = loadout.report(con, [dict(outro, prioridade=2),
                               slot("Terceiro", "modern", "Terceiro",
                                    prioridade=1, balde="SPML")])
    assert por_nome(rep)["Terceiro"]["pct"] == 100, por_nome(rep)
    print("entre não-vigiados, o desempate continua a ser o `prioridade`")


def caso_cedh_so_ingles_nonfoil():
    """*"cEDH apenas inglês non-foil."* Uma foil ou uma PT existem, mas não
    fecham o slot: ficam como SUBSTITUTO (tens a carta, não serve a caixa) — ele
    não fechou a porta a estas como fechou às EN do Premodern."""
    con = base()
    deck(con, "CE", "cedh", [("Sol Ring", 2)])
    add(con, "Sol Ring", 1, finish="foil", sub="SPML")
    add(con, "Sol Ring", 1, finish="nonfoil", lang="pt", sub="SPML")
    rep = loadout.report(con, [slot("CE", "cedh", "CE", balde="Cloud cEDH")])
    s = por_nome(rep)["CE"]
    assert s["tenho"] == 0, s["tenho"]
    assert s["missing"][0]["alt"] == {"não é nonfoil": 1, "não é EN": 1}, \
        s["missing"][0]["alt"]
    print("cEDH: nem foil nem PT fecham o slot, ficam como substitutos")


def caso_duel_commander_so_foil():
    """*"Duel Commander: apenas foil."* Uma nonfoil não fecha o slot."""
    con = base()
    deck(con, "DC", "duel-commander", [("Sol Ring", 2)])
    add(con, "Sol Ring", 1, finish="foil", sub="SPML")
    add(con, "Sol Ring", 1, finish="nonfoil", sub="SPML")
    rep = loadout.report(con, [slot("DC", "duel-commander", "DC", balde="Cloud")])
    s = por_nome(rep)["DC"]
    assert s["tenho"] == 1 and s["missing"][0]["alt"] == {"não é foil": 1}, s
    print("Duel Commander: só foil fecha o slot")


def caso_pauper_prefere_foil_mas_aceita_nonfoil():
    """*"Pauper: tudo foil se houver disponível, senão pode ser non-foil."*

    As duas metades importam: a nonfoil FECHA o slot (não é substituto), mas
    quando há foil é a foil que vai para a caixa."""
    con = base()
    deck(con, "PA", "pauper", [("Thoughtcast", 1)])
    add(con, "Thoughtcast", 1, finish="nonfoil", sub="SPML")
    rep = loadout.report(con, [slot("PA", "pauper", "PA", balde="Pauper Affinity")])
    assert por_nome(rep)["PA"]["pct"] == 100, "sem foil, a nonfoil serve"

    add(con, "Thoughtcast", 1, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("PA", "pauper", "PA", balde="Pauper Affinity")])
    s = por_nome(rep)["PA"]
    assert s["have"][0]["lotes"][0]["finish"] == "foil", s["have"][0]["lotes"]
    print("Pauper: leva a foil quando há, e a nonfoil quando não há")


def caso_pauper_agrega_do_spml():
    """*"Para Pauper, utilizas as cartas que forem necessárias do SPML e agregas
    ao Pauper."* É o caso dos 4 Utrom Monitor: estão no SPML, o deck de Pauper
    precisa deles, e é a caixa do Pauper que fica com eles — mesmo com o SPML a
    querê-los para o Modern, que escolhe depois."""
    con = base()
    deck(con, "PA", "pauper", [("Thoughtcast", 4)])
    deck(con, "MO", "modern", [("Thoughtcast", 4)])
    add(con, "Thoughtcast", 4, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("MO", "modern", "MO", prioridade=1, balde="SPML"),
                               slot("PA", "pauper", "PA", prioridade=9,
                                    balde="Pauper Affinity")])
    s = por_nome(rep)
    assert s["PA"]["pct"] == 100, s["PA"]
    assert s["PA"]["origens"] == {"SPML": 4}, s["PA"]["origens"]
    assert s["MO"]["noutra"] == 4 and s["MO"]["comprar"] == 0, s["MO"]
    print("Pauper agrega do SPML o que precisa, e o Modern vai lá buscá-las")


def caso_premodern_so_edicoes_da_era():
    """*"Premodern: apenas as edições da era Premodern."* Uma PT de uma impressão
    posterior ao Scourge é substituto, não slot fechado — a diferença para as EN
    é de propósito: ali ele fechou a porta, aqui só diz que a edição é outra."""
    con = base()
    deck(con, "PM", "premodern", [("Thoughtcast", 1)])     # mrd, 2003-10-02
    add(con, "Thoughtcast", 1, lang="pt", sub="Premodern (geral)")
    rep = loadout.report(con, [slot("PM", "premodern", "PM",
                                    balde="Premodern (geral)")])
    s = por_nome(rep)["PM"]
    assert s["tenho"] == 0, s["tenho"]
    assert s["missing"][0]["alt"] == {"edição posterior ao Scourge": 1}, \
        s["missing"][0]["alt"]
    print("Premodern: uma impressão posterior ao Scourge não fecha o slot")


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
    """O erro caro: o playset de 4 mandava vender exactamente as cartas que
    faltam a uma caixa do loadout e que só não fecham o slot pelo acabamento.

    (O caso original era o do Premodern com as EN. Desde 2026-09-07 as EN nem são
    vistas por essas caixas e vão mesmo para a venda a confirmar — a saída
    `guardar` fica para o acabamento, que é onde ele não fechou a porta.)
    """
    con = base()
    deck(con, "M", "modern", [("Kappa Cannoneer", 4)])
    add(con, "Kappa Cannoneer", 1, finish="foil", sub="SPML")
    add(con, "Kappa Cannoneer", 4, finish="nonfoil", sub="SPML")
    rep = loadout.report(con, [slot("M", "modern", "M", acabamento="foil",
                                    balde="SPML")])
    # 5 cópias, playset 4 -> 1 de excesso. Sai das nonfoil, que são as livres —
    # mas são as que faltam ao deck, por isso guarda-se em vez de ir à venda.
    assert not [r for r in rep["venda"] + rep["venda_rl"]
                if r["nm"] == "Kappa Cannoneer"], rep["venda"]
    g = [r for r in rep["guardar"] if r["nm"] == "Kappa Cannoneer"]
    assert sum(r["q"] for r in g) == 1, g
    assert g[0]["finish"] == "nonfoil" and "M" in g[0]["reason"], g
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


# ---------------------------------------------------------------------------
# Decks permanentes e arrumação física (André, 2026-09-07)
# ---------------------------------------------------------------------------
def caso_permanente_escolhe_antes_do_candidato():
    """*"Os decks que eu pedi para serem permanentes são a minha prioridade
    máxima!"* — um permanente de SPML fica com a carta à frente de um candidato
    de Premodern, mesmo o Premodern sendo o primeiro grupo da ordem."""
    con = base()
    deck(con, "Cand", "premodern", [("Kappa Cannoneer", 1)])
    deck(con, "Perm", "legacy", [("Kappa Cannoneer", 1)])
    add(con, "Kappa Cannoneer", 1, finish="foil")
    # O candidato é de Premodern (grupo 1) e o permanente de Legacy (grupo 5):
    # sem a regra dos permanentes, o Premodern escolhia primeiro.
    cand = slot("Cand", "premodern", "Cand", lingua=None, estrita=False,
                edicoes=None, baldes=None, permanente=False)
    perm = slot("Perm", "legacy", "Perm", permanente=True)
    rep = loadout.report(con, [cand, perm])
    s = por_nome(rep)
    assert [x["nome"] for x in rep["slots"]] == ["Perm", "Cand"], \
        [x["nome"] for x in rep["slots"]]
    assert s["Perm"]["tenho"] == 1
    assert s["Cand"]["tenho"] == 0
    # E o candidato não pede a carta para comprar: sabe onde ela está.
    assert s["Cand"]["missing"][0]["noutra"] == {"Perm": 1}
    assert s["Cand"]["comprar"] == 0
    print("um deck permanente aloca antes de um candidato de grupo melhor")


def caso_candidato_promovido_a_permanente_recebe():
    """*"Os decks que eu estiver quase a concluir, tenho que ter uma opção que os
    marque como permanentes para começarem a receber alocação de cartas."*"""
    con = base()
    deck(con, "Cand", "legacy", [("Sol Ring", 1)])
    deck(con, "Perm", "legacy", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil")
    cand = slot("Cand", "legacy", "Cand", prioridade=1, permanente=False)
    perm = slot("Perm", "legacy", "Perm", prioridade=2, permanente=True)
    antes = por_nome(loadout.report(con, [cand, perm]))
    assert antes["Perm"]["tenho"] == 1 and antes["Cand"]["tenho"] == 0
    # Promove-se o candidato (é o que o botão do modo edição escreve no config):
    # volta ao seu grupo e, com prioridade 1, passa a receber.
    depois = por_nome(loadout.report(con, [dict(cand, permanente=True), perm]))
    assert depois["Cand"]["tenho"] == 1, depois["Cand"]["tenho"]
    assert depois["Perm"]["tenho"] == 0
    print("marcar um candidato como permanente po-lo a receber cartas")


def caso_arrumacao_diz_de_onde_tirar_e_para_onde_vai():
    """A aba Arrumar: a diferença entre onde a carta ESTÁ e onde DEVE estar."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 2)])
    add(con, "Sol Ring", 2, finish="foil", sub="Colecção")
    rep = loadout.report(con, [slot("A", "legacy", "A", balde="Colecção")])
    a = rep["arrumacao"]
    assert a["copias"] == 2, a
    assert list(a["por_origem"]) == ["Colecção"]
    assert list(a["por_destino"]) == ["A"]
    assert "sentido,quantidade,carta,de,para" in loadout.csv_arrumacao(a)
    assert '"Sol Ring","Colecção","A"' in loadout.csv_arrumacao(a)
    print("a arrumacao diz de que gaveta sai e para que caixa vai")


def caso_ja_arrumei_persiste_e_o_plano_esvazia():
    """Depois do "já arrumei", a carta ESTÁ na caixa: o plano fica vazio, o
    `local` passa a dizer a caixa, e a alocação do dia seguinte não a mexe."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 2)])
    add(con, "Sol Ring", 2, finish="foil", sub="Colecção")
    slots = [slot("A", "legacy", "A", balde="Colecção")]
    rep = loadout.report(con, slots)
    assert loadout.guardar_arrumacao(con, rep) == 2
    rep2 = loadout.report(con, slots)
    assert rep2["arrumacao"]["copias"] == 0, rep2["arrumacao"]
    assert por_nome(rep2)["A"]["origens"] == {"A": 2}, por_nome(rep2)["origens"]
    # Idempotente: guardar duas vezes não duplica linhas.
    loadout.guardar_arrumacao(con, rep2)
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation").fetchone()["c"] == 1
    print("guardar a arrumacao esvazia o plano e nao duplica linhas")


def caso_arrumar_nao_transforma_ir_buscar_em_compra():
    """A regra que quase se perdeu: uma cópia sleevada NOUTRA caixa continua a
    ser *"em &lt;caixa&gt;"*, não uma compra.

    Depois de confirmar a arrumação, a alocação tem de dar exactamente o mesmo —
    senão o "já arrumei tudo" fazia o custo de fechar subir 1 200 € só por ele
    ter arrumado as cartas. E a cópia que está dentro de uma caixa não pode ser
    tirada de lá por um slot que corra ANTES: a ordem da alocação, sozinha, não
    chega para isso.
    """
    con = base()
    deck(con, "Prem", "premodern", [("Swords to Plowshares", 2)])
    deck(con, "Ench", "premodern", [("Swords to Plowshares", 2)])
    add(con, "Swords to Plowshares", 2, lang="pt", sub="Colecção")
    slots = [slot("Prem", "premodern", "Prem", prioridade=1, baldes=["Colecção"]),
             slot("Ench", "premodern", "Ench", prioridade=2, baldes=["Colecção"])]
    antes = por_nome(loadout.report(con, slots))
    assert antes["Prem"]["tenho"] == 2 and antes["Ench"]["tenho"] == 0
    assert antes["Ench"]["comprar"] == 0, antes["Ench"]["comprar"]
    assert antes["Ench"]["missing"][0]["noutra"] == {"Prem": 2}

    loadout.guardar_arrumacao(con, loadout.report(con, slots))
    depois = por_nome(loadout.report(con, slots))
    assert depois["Prem"]["tenho"] == 2, depois["Prem"]["tenho"]
    assert depois["Ench"]["comprar"] == 0, depois["Ench"]["comprar"]
    assert depois["Ench"]["missing"][0]["noutra"] == {"Prem": 2}, \
        depois["Ench"]["missing"][0]["noutra"]
    # E não é um substituto: é ir buscar.
    assert not depois["Ench"]["subs"], depois["Ench"]["subs"]

    # A caixa que corre PRIMEIRO não pode roubar o que está dentro da segunda.
    trocado = [dict(slots[0], prioridade=5), dict(slots[1], prioridade=1)]
    virado = por_nome(loadout.report(con, trocado))
    assert virado["Prem"]["tenho"] == 2, virado["Prem"]["tenho"]
    assert virado["Ench"]["tenho"] == 0 and virado["Ench"]["comprar"] == 0
    print("confirmar a arrumacao nao transforma 'ir buscar' em compra")


def caso_carta_na_caixa_escapa_as_regras_de_material():
    """A irmã da excepção do balde, no modelo novo: uma cópia JÁ ARRUMADA na
    caixa deste deck escapa às regras de material — senão uma regra nova
    desmontava no papel um deck que está na estante."""
    con = base()
    deck(con, "EDH", "cedh", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 1, finish="foil", lang="pt", sub="Colecção")
    s = slot("EDH", "cedh", "EDH", balde="Colecção")
    # Antes de arrumar: é PT da era Premodern e foil — o cEDH é "só EN nonfoil".
    assert por_nome(loadout.report(con, [s]))["EDH"]["tenho"] == 0
    cid = con.execute("SELECT id FROM copies").fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,1)",
                (cid, "edh"))
    con.commit()
    rep = por_nome(loadout.report(con, [s]))["EDH"]
    assert rep["tenho"] == 1, rep["tenho"]
    print("uma copia ja arrumada na caixa escapa as regras de material")


def caso_lote_partido_entre_caixa_e_gaveta():
    """Um lote de 4 com 3 já na caixa e 1 solta: a excepção vale só para as 3."""
    con = base()
    deck(con, "EDH", "cedh", [("Lotus Petal", 4)])
    deck(con, "Leg", "legacy", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 4, finish="foil", lang="pt", sub="Colecção")
    cid = con.execute("SELECT id FROM copies").fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,3)",
                (cid, "edh"))
    con.commit()
    rep = por_nome(loadout.report(con, [slot("EDH", "cedh", "EDH", balde="Colecção"),
                                        slot("Leg", "legacy", "Leg", prioridade=2,
                                             balde="Colecção")]))
    # As 3 arrumadas fecham slot no cEDH; a 4ª continua PT da era e foil, por isso
    # não serve nem o cEDH (nonfoil) nem o Legacy (trancada ao Premodern).
    assert rep["EDH"]["tenho"] == 3, rep["EDH"]["tenho"]
    assert rep["Leg"]["tenho"] == 0
    print("um lote meio arrumado vale como meio arrumado, nao por inteiro")


def caso_nonfoil_nunca_e_foil():
    """`"nonfoil"` CONTÉM `"foil"`. Quem testar o acabamento por substring dá
    uma cópia nonfoil como foil — foi assim que a tabela de venda pôs ✨ em
    Lotus Petal e Mirri's Guile, que são as duas nonfoil.

    A resposta vive num sítio só (`loadout.e_foil`), e é a mesma que a alocação
    usa (`FOIL_FINISHES`) — para a página não poder discordar do motor."""
    assert loadout.e_foil("foil") and loadout.e_foil("etched")
    assert not loadout.e_foil("nonfoil"), "'nonfoil' contém 'foil' — não é foil"
    assert not loadout.e_foil(None) and not loadout.e_foil("")
    # E a lista de venda de uma cópia nonfoil sai marcada como não-foil.
    con = base()
    add(con, "Sol Ring", 5, finish="nonfoil", sub="Colecção")
    rep = loadout.report(con, [])
    linha = next(r for r in rep["venda"] if r["nm"] == "Sol Ring")
    assert linha["finish"] == "nonfoil" and not loadout.e_foil(linha["finish"]), linha
    print("uma copia nonfoil nunca e tratada como foil")


def caso_rotulo_material_diz_a_classe_e_as_fontes():
    """Duas coisas que as páginas decidiam à sua maneira e erravam:

      * a CLASSE do chip — cada página fazia `"foil" in texto`, e o chip
        *"só nonfoil"* do cEDH vinha pintado de dourado como se fosse de foil;
      * as FONTES — `"só de Colecção · Premodern (geral) · SPML · Caixa RL"`
        transbordava o cartão e nomeava quatro sítios onde há dois (os três
        primeiros são a mesma gaveta desde a colecção única)."""
    pm = {"formato": "premodern", "lingua": "pt", "edicoes": "premodern",
          "balde": "Premodern (geral)", "estrita": True,
          "baldes": ["Colecção", "Premodern (geral)", "SPML", "Caixa Reserved List"]}
    cls = {t: c for _i, t, c in loadout.rotulo_material(pm)}
    assert cls["só PT"] == "pt", cls
    assert loadout.fontes_material(pm) == "fontes: Colecção + Caixa RL (PT)", \
        loadout.fontes_material(pm)
    assert "fontes: Colecção + Caixa RL (PT)" in cls, cls

    cedh = {"formato": "cedh", "lingua": "en", "acabamento": "nonfoil"}
    cls = {t: c for _i, t, c in loadout.rotulo_material(cedh)}
    assert cls["só nonfoil"] == "", ("o chip 'só nonfoil' não é um chip de foil", cls)
    spml = {"formato": "modern", "lingua": "en", "acabamento": "foil"}
    cls = {t: c for _i, t, c in loadout.rotulo_material(spml)}
    assert cls["só foil (a Reserved List pode ser nonfoil)"] == "fo", cls
    # Sem restrição de baldes (ou só a Colecção) não há chip de fontes nenhum:
    # uma regra que não restringe nada não é uma regra para mostrar.
    assert loadout.fontes_material(spml) is None
    assert loadout.fontes_material({"baldes": ["Colecção"]}) is None

    # O requisito curto, para cada linha da wantlist da aba Comprar.
    assert loadout.requisito_material(pm) == "PT · ≤SCG"
    assert loadout.requisito_material(cedh) == "EN · nonfoil"
    assert loadout.requisito_material(spml) == "EN · foil"
    assert loadout.requisito_material({"acabamento": "prefere_foil"}) == "foil (ou nonfoil)"
    assert loadout.requisito_material({}) == ""
    print("o rotulo de material traz a classe certa e as fontes em nome de gente")


def run():
    for fn in (caso_uma_copia_uma_caixa, caso_noutra_caixa_nao_e_compra,
               caso_noutra_caixa_e_compra_misturadas,
               caso_noutra_caixa_nao_conta_a_mesma_copia_duas_vezes,
               caso_falta_partilhada_nao_e_conflito,
               caso_premodern_so_pt,
               caso_premodern_e_a_caixa_rl_partida_em_pt_e_en,
               caso_premodern_nao_tira_de_caixa_de_outro_deck,
               caso_pt_da_era_trancada_ao_premodern,
               caso_premodern_so_edicoes_da_era,
               caso_excepcao_do_balde, caso_ordem_dos_grupos_de_formato,
               caso_vigiado_escolhe_primeiro_dentro_do_grupo,
               caso_cedh_so_ingles_nonfoil, caso_duel_commander_so_foil,
               caso_pauper_prefere_foil_mas_aceita_nonfoil,
               caso_pauper_agrega_do_spml,
               caso_foil, caso_colecionador_e_reservas_fora,
               caso_backup_e_venda, caso_substituto_nao_se_vende, caso_variantes,
               caso_slot_vazio, caso_preco_foil,
               caso_permanente_escolhe_antes_do_candidato,
               caso_candidato_promovido_a_permanente_recebe,
               caso_arrumacao_diz_de_onde_tirar_e_para_onde_vai,
               caso_ja_arrumei_persiste_e_o_plano_esvazia,
               caso_arrumar_nao_transforma_ir_buscar_em_compra,
               caso_carta_na_caixa_escapa_as_regras_de_material,
               caso_lote_partido_entre_caixa_e_gaveta,
               caso_nonfoil_nunca_e_foil,
               caso_rotulo_material_diz_a_classe_e_as_fontes):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
