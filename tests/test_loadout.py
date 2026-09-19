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

DESDE 2026-09-19 (André, à letra: *"cada deck deverá ter as suas próprias cartas
dentro, não repetindo com outros decks!"*) o ponto 7 está SUPERSEDED: uma carta
que a alocação deu a outra caixa é COMPRA para esta (com uma nota *"tens N no
X"*), o `noutra` é zero em todos os formatos, não há compras partilhadas, e
`conflitos`/`partilhas` são vazios por regra. Os casos que fixavam a partilha
(v4, 2026-09-07; Premodern, 2026-09-08) foram reescritos para a regra nova, um a
um, com o porquê no docstring. O que se mantém é o TECTO de playset do
Premodern, agora sobre o grupo inteiro (ver `test_caixas_dedicadas.py`).

E a segunda regra do mesmo dia (*"confirma se há foil"*) mudou a mensagem *"não
é foil"*: passou a dizer em que edições a carta existe em foil — `nao_foil(nm)`
abaixo compõe-na a partir do catálogo de teste (ver `test_foil_existe.py`).

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
CFG = {"regras_colecao": {"Blue Farm": {"reter_extras": True},
                          "Cloud": {"reter_extras": True},
                          "Cloud cEDH": {"reter_extras": True},
                          "Pauper Affinity": {"reter_extras": True}},
       "decks_vigiados": ["Oswald"]}
_TMP = Path(tempfile.mkdtemp())
_CFG_PATH = _TMP / "cfg.json"
_CFG_PATH.write_text(json.dumps(CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

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
        reserved_deck_id=None, borigem=None):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = None
    if sub:
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
        sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                             (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id, reserved_deck_id, balde_origem)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (sid, q, finish, lang, purpose, sub_id, reserved_deck_id, borigem))
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


def nao_foil(nm):
    """A mensagem *"não é foil (existe em foil: 4BB 1995)"* desta carta, tal como
    o `loadout.razao_nao_foil` a compõe do catálogo de teste (uma impressão por
    carta, todas com foil)."""
    sc, rel = next((sc, rel) for n, sc, rel, _rl in CATALOGO if n == nm)
    return loadout.razao_nao_foil([f"{sc.upper()} {rel[:4]}"])


# ---------------------------------------------------------------------------
def caso_uma_copia_uma_caixa():
    """Duas caixas, uma cópia: ganha a de prioridade mais alta. Somar coberturas
    independentes dava 100% às duas.

    Até 2026-09-19 a segunda ficava em `conflitos` (*"ficam_sem"*) e ia buscar a
    cópia à primeira. Desde então (*"cada deck deverá ter as suas próprias
    cartas dentro"*) a segunda COMPRA a sua, os `conflitos` são vazios por regra
    e o que fica é a nota *"tens 1 no A"*.
    """
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 1)])
    deck(con, "B", "legacy", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1),
                               slot("B", "legacy", "B", prioridade=2)])
    s = por_nome(rep)
    assert s["A"]["pct"] == 100 and s["B"]["pct"] == 0, (s["A"]["pct"], s["B"]["pct"])
    assert rep["conflitos"] == [], rep["conflitos"]
    m = s["B"]["missing"][0]
    assert m["comprar"] == 1 and m["noutra"] == {} and m["noutra_nota"] == {"A": 1}, m
    assert loadout.nota_onde(m) == "tens 1 no A", loadout.nota_onde(m)
    print("uma cópia física serve uma caixa só; a outra compra e sabe que a tem")

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
    """SUPERSEDED a 2026-09-19 — o nome ficou para o histórico dizer o que mudou.

    Até aí (André, 2026-09-07: *"indicas onde está a carta, para (...) não ter
    que comprar múltiplos para todos"*) quatro Swords pedidas por três caixas
    eram uma compra de zero: a primeira ficava com elas e as outras diziam "em
    A". Desde 2026-09-19 (*"cada deck deverá ter as suas próprias cartas dentro,
    não repetindo com outros decks!"*) as outras duas COMPRAM as suas 4 — o
    `noutra` é zero, o custo soma, e a nota *"tens 4 no A"* fica só para ele
    saber que a carta existe em casa.
    """
    con = base()
    preco(con, "Swords to Plowshares", "foil", 1.5)
    for nome in ("A", "B", "C"):
        deck(con, nome, "legacy", [("Swords to Plowshares", 4)])
    # Foil porque o grupo SPML é "tudo foil e inglês" (a regra dele de
    # 2026-09-07); o que este caso tranca é o "cada caixa compra as suas".
    add(con, "Swords to Plowshares", 4, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1, balde="SPML"),
                               slot("B", "legacy", "B", prioridade=2, balde="SPML"),
                               slot("C", "legacy", "C", prioridade=3, balde="SPML")])
    s = por_nome(rep)

    assert s["A"]["pct"] == 100 and s["A"]["comprar"] == 0 and s["A"]["noutra"] == 0
    for nome in ("B", "C"):
        m = [x for x in s[nome]["missing"] if x["nm"] == "Swords to Plowshares"][0]
        assert m["missing"] == 4, m
        assert m["noutra"] == {} and m["noutra_q"] == 0, m["noutra"]
        assert m["noutra_nota"] == {"A": 4}, m["noutra_nota"]
        assert m["comprar"] == 4 and m["cost"] == 6.0, m
        assert s[nome]["comprar"] == 4 and s[nome]["noutra"] == 0, s[nome]
        assert s[nome]["custo"] == 6.0, s[nome]["custo"]
        assert s[nome]["noutra_caixa"] == [], s[nome]["noutra_caixa"]
        assert [x["nm"] for x in s[nome]["noutra_notas"]] == ["Swords to Plowshares"]
    assert rep["custo_total"] == 12.0, rep["custo_total"]
    assert rep["comprar_total"] == 8 and rep["noutra_total"] == 0
    assert rep["conflitos"] == [] and rep["partilhas"] == []
    print("carta que está noutra caixa compra-se para esta — e diz onde a tens")


def caso_noutra_caixa_e_compra_misturadas():
    """O caso meio: duas caixas pedem 4, só existem 2 e foram para a primeira.

    Até 2026-09-19 compravam-se DUAS (a partilha de compras da v4) e a segunda
    ia buscar as quatro. Desde então cada caixa compra as suas: o A compra as 2
    que lhe faltam e o B compra 4 — com a nota de que 2 estão no A. Nada é
    partilhado nem "futuro"; `partilhas` e `poupado_total` são zero por regra.
    """
    con = base()
    preco(con, "Swords to Plowshares", "foil", 10.0)
    deck(con, "A", "legacy", [("Swords to Plowshares", 4)])
    deck(con, "B", "legacy", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 2, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1, balde="SPML"),
                               slot("B", "legacy", "B", prioridade=2, balde="SPML")])
    b = por_nome(rep)["B"]
    m = b["missing"][0]
    assert m["missing"] == 4 and m["comprar"] == 4 and m["cost"] == 40.0, m
    assert m["noutra"] == {} and m["noutra_futura"] == {}, m
    assert m["noutra_nota"] == {"A": 2}, m["noutra_nota"]
    assert b["comprar"] == 4 and b["noutra"] == 0 and b["custo"] == 40.0, b
    a = por_nome(rep)["A"]
    assert a["noutra"] == 0 and a["comprar"] == 2 and a["custo"] == 20.0, a
    assert rep["comprar_total"] == 6 and rep["custo_total"] == 60.0, rep["custo_total"]
    assert rep["poupado_total"] == 0 and rep["partilhas"] == [], rep["partilhas"]
    print("duas caixas, faltam 2 no mundo: cada uma compra as suas (2 + 4)")


def caso_compra_partilhada_e_o_maximo_nao_a_soma():
    """SUPERSEDED a 2026-09-19: agora é a SOMA, não o máximo.

    Até aí três caixas do mesmo material a pedir 4 cartas que ele não tinha
    compravam 4 (a partilha da v4, *"não ter que comprar múltiplos para
    todos"*). Desde 2026-09-19 (*"cada deck deverá ter as suas próprias cartas
    dentro, não repetindo com outros decks!"*) compram 12: cada caixa as suas,
    e é isso que o "fechar tudo" diz.
    """
    con = base()
    preco(con, "Swords to Plowshares", "foil", 10.0)
    for nome in ("A", "B", "C"):
        deck(con, nome, "legacy", [("Swords to Plowshares", 4)])
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1),
                               slot("B", "legacy", "B", prioridade=2),
                               slot("C", "legacy", "C", prioridade=3)])
    s = por_nome(rep)
    for nome in "ABC":
        assert s[nome]["comprar"] == 4 and s[nome]["custo"] == 40.0, s[nome]
        assert s[nome]["noutra"] == 0, s[nome]
        m = s[nome]["missing"][0]
        assert m["noutra"] == {} and m["noutra_futura"] == {} and m["noutra_nota"] == {}, m
    assert rep["comprar_total"] == 12 and rep["custo_total"] == 120.0, rep["custo_total"]
    assert rep["poupado_total"] == 0, rep["poupado_total"]
    assert all(s[n]["pct"] == 0 and s[n]["faltam"] == 4 for n in "ABC"), s
    print("três caixas, três compras: cada caixa compra as suas cartas")


def caso_main_e_side_da_mesma_caixa_continuam_a_somar():
    """Dentro da MESMA caixa o main e o side estão na mesa ao mesmo tempo: essas
    faltas somam (5). E desde 2026-09-19 entre caixas também somam — o B compra
    as suas 4, em vez de ir buscar as do A."""
    con = base()
    preco(con, "Swords to Plowshares", "foil", 10.0)
    deck(con, "A", "legacy", [("Swords to Plowshares", 3)],
         side=[("Swords to Plowshares", 2)])
    deck(con, "B", "legacy", [("Swords to Plowshares", 4)])
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1),
                               slot("B", "legacy", "B", prioridade=2)])
    s = por_nome(rep)
    assert s["A"]["comprar"] == 5 and s["A"]["custo"] == 50.0, s["A"]
    assert sorted(m["comprar"] for m in s["A"]["missing"]) == [2, 3], s["A"]["missing"]
    assert s["B"]["comprar"] == 4 and s["B"]["noutra"] == 0, s["B"]
    assert rep["comprar_total"] == 9, rep["comprar_total"]
    print("main + side da mesma caixa somam; e entre caixas também (cada uma as suas)")


def caso_pools_de_material_diferentes_nao_se_partilham():
    """Uma Swords PT da era não serve o Legacy (que a quer foil e EN) e uma EN
    foil não serve o Premodern. São duas compras, e a partilha não pode fundi-las
    — é o mesmo erro, ao contrário: comprar uma e julgar que serve as duas."""
    con = base()
    preco(con, "Swords to Plowshares", "foil", 10.0)
    preco(con, "Swords to Plowshares", "nonfoil", 4.0)
    deck(con, "P", "premodern", [("Swords to Plowshares", 4)])
    deck(con, "L", "legacy", [("Swords to Plowshares", 4)])
    rep = loadout.report(con, [slot("P", "premodern", "P", balde="Premodern (geral)"),
                               slot("L", "legacy", "L", balde="SPML")])
    s = por_nome(rep)
    assert s["P"]["comprar"] == 4 and s["L"]["comprar"] == 4, (s["P"], s["L"])
    assert rep["comprar_total"] == 8 and not rep["partilhas"], rep["partilhas"]
    # E cada linha diz o material que aquela compra tem de ter.
    assert s["P"]["missing"][0]["marca_compra"] == "PT", s["P"]["missing"][0]
    assert s["L"]["missing"][0]["marca_compra"] == "EN foil", s["L"]["missing"][0]
    print("PT do Premodern e EN foil do Legacy são pools diferentes: duas compras")


def caso_pool_foil_en_junta_o_duel_commander_e_o_spml():
    """SUPERSEDED a 2026-09-19. Os pools que SE TOCAM (o Duel Commander é
    *"apenas foil"* sem língua, o SPML *"tudo foil e inglês"*) já não fundem
    compra nenhuma: cada caixa compra a sua Sol Ring. O que fica do pool é o
    MATERIAL de cada linha (`marca_compra`), que continua certo por caixa."""
    con = base()
    preco(con, "Sol Ring", "foil", 12.0)
    deck(con, "Cloud", "duel-commander", [("Sol Ring", 1)])
    deck(con, "Oswald", "modern", [("Sol Ring", 1)])
    rep = loadout.report(con, [slot("Cloud", "duel-commander", "Cloud"),
                               slot("Oswald", "modern", "Oswald")])
    s = por_nome(rep)
    assert s["Cloud"]["comprar"] == 1 and s["Oswald"]["comprar"] == 1, (s, )
    assert s["Oswald"]["noutra"] == 0 and s["Cloud"]["noutra"] == 0, s["Oswald"]
    assert rep["comprar_total"] == 2 and rep["custo_total"] == 24.0, rep["custo_total"]
    assert rep["partilhas"] == [], rep["partilhas"]
    assert s["Cloud"]["missing"][0]["marca_compra"] == "foil"
    assert s["Oswald"]["missing"][0]["marca_compra"] == "EN foil"
    print("Duel Commander e Modern compram cada um a sua Sol Ring, no seu material")


def caso_compras_dedicadas_nao_partilham():
    """`compras_dedicadas` deixou de fazer diferença a 2026-09-19: TODAS as
    caixas compram as suas (a chave fica no config sem efeito — apagá-la é
    decisão dele). Três caixas a pedir 4, três compras de 4."""
    con = base()
    preco(con, "Swords to Plowshares", "foil", 10.0)
    for nome in ("A", "B", "C"):
        deck(con, nome, "legacy", [("Swords to Plowshares", 4)])
    rep = loadout.report(con, [
        slot("A", "legacy", "A", prioridade=1),
        slot("B", "legacy", "B", prioridade=2, compras_dedicadas=True),
        slot("C", "legacy", "C", prioridade=3)])
    s = por_nome(rep)
    assert all(s[n]["comprar"] == 4 and s[n]["noutra"] == 0 for n in "ABC"), s
    assert rep["comprar_total"] == 12, rep["comprar_total"]
    assert rep["partilhas"] == [], rep["partilhas"]
    print("com ou sem compras_dedicadas, cada caixa compra as suas")


def caso_noutra_caixa_nao_conta_a_mesma_copia_duas_vezes():
    """A mesma carta no main E no side são DUAS linhas de falta. Desde
    2026-09-19 nenhuma vai buscar nada: o B compra as 5 (3 + 2), e a nota diz
    que o A tem 4 — a nota é por linha, e as duas linhas dizem o mesmo, porque
    é informação e não uma cópia a repartir."""
    con = base()
    preco(con, "Swords to Plowshares", "foil", 2.0)
    deck(con, "A", "legacy", [("Swords to Plowshares", 4)])
    deck(con, "B", "legacy", [("Swords to Plowshares", 3)],
         side=[("Swords to Plowshares", 2)])
    add(con, "Swords to Plowshares", 4, finish="foil", sub="SPML")
    rep = loadout.report(con, [slot("A", "legacy", "A", prioridade=1, balde="SPML"),
                               slot("B", "legacy", "B", prioridade=2, balde="SPML")])
    b = por_nome(rep)["B"]
    assert b["noutra"] == 0 and b["comprar"] == 5, b
    assert b["custo"] == 10.0, b["custo"]
    assert all(m["noutra_nota"] == {"A": 4} for m in b["missing"]), b["missing"]
    print("main + side compram-se os dois; a nota 'tens 4 no A' vai nas duas linhas")


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
    #
    # Desde 2026-09-08 a lista da RL passa por mais um crivo: *"cartas de RL só
    # vão para venda se não tiverem subido 5 % de valor nos últimos 3 meses"*.
    # Esta base de teste não tem preço nenhum, por isso a cópia sai por
    # `rl_sem_historico` — que é o comportamento certo (não se vende uma RL sem
    # saber se subiu) e é o que a base a sério faz hoje, com o `price_history` a
    # começar em Agosto de 2026. O que este caso tranca é o outro lado: a cópia
    # que sai é a EN da Caixa RL, e sai UMA (5 cópias, playset 4).
    assert not [r for r in rep["guardar"] if r["nm"] == "Opalescence"], rep["guardar"]
    vrl = [r for r in rep["venda_rl"] + rep["rl_sem_historico"]
           if r["nm"] == "Opalescence"]
    assert sum(r["q"] for r in vrl) == 1, vrl        # 5 cópias, playset 4 -> 1
    assert vrl[0]["local"] == "Caixa RL (EN)", vrl[0]["local"]
    assert not rep["venda_rl"], "sem histórico de preços, nenhuma RL se vende"
    assert loadout.RAZAO_RL_SEM_HISTORICO in vrl[0]["reason"], vrl[0]["reason"]
    assert vrl[0]["porque_venderia"] == "excedente (mais de 4)", vrl[0]

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
    # A recusa diz em que edições a carta existe em foil (2026-09-19).
    assert s["tenho"] == 1 and s["missing"][0]["alt"] == {nao_foil("Sol Ring"): 1}, s
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
    # Desde 2026-09-07 (19:00) a caixa do Pauper é DEDICADA: não empresta. O
    # Modern deixou de dizer "vai buscar ao Pauper" e passa a comprar as suas —
    # *"cada deck montado deixa de partilhar cartas com outros decks"*.
    assert s["MO"]["comprar"] == 4 and s["MO"]["noutra"] == 0, s["MO"]
    print("Pauper agrega do SPML o que precisa; o Modern compra as dele")


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
    assert falta["alt"] == {nao_foil("Kappa Cannoneer"): 3}, falta["alt"]
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

    # A caixa de Commander tem `reter_extras`: os 2 extras guardam-se SEM PRAZO
    # (André, 2026-09-15) e a linha diz-o — e diz também por que iria à venda,
    # senão "guardada" é uma resposta sem a pergunta ao lado.
    sr = [r for r in rep["retidos"] if r["nm"] == "Sol Ring"]
    assert sum(r["q"] for r in sr) == 2, (sr, rep["venda"])
    assert not [r for r in rep["venda"] if r["nm"] == "Sol Ring"]
    assert all(r["reason"] == loadout.RAZAO_RETIDO for r in sr), sr
    assert "sem prazo" in loadout.RAZAO_RETIDO
    assert sr[0]["porque_venderia"] == "excedente (Commander: 1 por deck)", sr[0]
    print("extras de uma caixa de Commander ficam retidos sem prazo, não à venda")


def caso_a_chave_antiga_reter_extras_meses_continua_a_guardar():
    """A 2026-09-15 o `reter_extras_meses: 6` passou a `reter_extras: true` — o
    prazo deixou de existir. Um config que ainda traga a chave antiga tem de
    continuar a GUARDAR: ler a chave nova só, e dar a antiga como "sem regra",
    mandava vender de um dia para o outro tudo o que ontem estava retido. E o
    número (6, 3, 12) não muda nada: não é um prazo, é "guarda"."""
    antigo = _CFG_PATH.read_text(encoding="utf-8")
    _CFG_PATH.write_text(json.dumps({"regras_colecao": {
        "Blue Farm": {"reter_extras_meses": 6},
        "Cloud": {"reter_extras_meses": 3},
        "Pauper Affinity": {"reter_extras": True},
        "SPML": {"reter_extras": False},
        "Outro": {"reter_extras_meses": 0}}}), encoding="utf-8")
    # O cache do `sources.config` vai pelo mtime: garantir que mudou.
    os.utime(_CFG_PATH, (os.path.getmtime(_CFG_PATH) + 5,) * 2)
    try:
        ret = loadout._retencao()
        assert ret == {"Blue Farm": True, "Cloud": True, "Pauper Affinity": True}, ret
        con = base()
        deck(con, "EDH", "cedh", [("Sol Ring", 1)])
        add(con, "Sol Ring", 3, sub="Blue Farm")
        rep = loadout.report(con, [slot("EDH", "cedh", "EDH", balde="Blue Farm")])
        assert sum(r["q"] for r in rep["retidos"] if r["nm"] == "Sol Ring") == 2, rep["retidos"]
        assert not [r for r in rep["venda"] if r["nm"] == "Sol Ring"], rep["venda"]
    finally:
        _CFG_PATH.write_text(antigo, encoding="utf-8")
        os.utime(_CFG_PATH, (os.path.getmtime(_CFG_PATH) + 10,) * 2)
    print("a chave antiga reter_extras_meses continua a guardar (sem prazo)")


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
    # As regras do grupo Premodern desligam-se todas neste slot: o que aqui se
    # mede é a ordem dos permanentes, não o material nem o `dedicado` (que, sem
    # isto, faria o candidato comprar em vez de dizer onde a carta está).
    cand = slot("Cand", "premodern", "Cand", lingua=None, estrita=False,
                edicoes=None, baldes=None, dedicado=False, permanente=False)
    perm = slot("Perm", "legacy", "Perm", permanente=True)
    rep = loadout.report(con, [cand, perm])
    s = por_nome(rep)
    assert [x["nome"] for x in rep["slots"]] == ["Perm", "Cand"], \
        [x["nome"] for x in rep["slots"]]
    assert s["Perm"]["tenho"] == 1
    assert s["Cand"]["tenho"] == 0
    # E o candidato COMPRA a carta (2026-09-19: cada caixa tem as suas), com a
    # nota de que a tem no Perm. Até aí dizia "em Perm" e não comprava.
    assert s["Cand"]["missing"][0]["noutra"] == {}
    assert s["Cand"]["missing"][0]["noutra_nota"] == {"Perm": 1}
    assert s["Cand"]["comprar"] == 1
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
    """Arrumar não pode mudar o que se compra — a invariante que este caso
    sempre trancou. Até 2026-09-19 media-a pelo "ir buscar" (a segunda caixa
    dizia "em Prem" antes e depois de arrumar); desde então (*"cada deck deverá
    ter as suas próprias cartas dentro"*) mede-a pela COMPRA: a segunda compra
    2 antes e 2 depois de arrumar, não "0 e depois 2". E a cópia que está dentro
    de uma caixa continua a não poder ser tirada de lá por um slot que corra
    ANTES — a ordem da alocação, sozinha, não chega para isso.

    O tecto de playset do Premodern fica desligado aqui (`playset_maximo=None`)
    para o caso medir a arrumação e não o tecto — esse tem casos próprios.
    """
    con = base()
    deck(con, "Prem", "premodern", [("Swords to Plowshares", 2)])
    deck(con, "Ench", "premodern", [("Swords to Plowshares", 2)])
    add(con, "Swords to Plowshares", 2, lang="pt", sub="Colecção")
    # `prioridade_por: None` de propósito: o que este caso mede é a ORDEM a
    # decidir quem fica com as cópias, e o `prioridade` do config só decide
    # isso quando o grupo não ordena sozinho. A ordem automática do Premodern
    # está no `caso_premodern_ordena_por_pct_completo`.
    slots = [slot("Prem", "premodern", "Prem", prioridade=1, baldes=["Colecção"],
                  prioridade_por=None, playset_maximo=None),
             slot("Ench", "premodern", "Ench", prioridade=2, baldes=["Colecção"],
                  prioridade_por=None, playset_maximo=None)]
    antes = por_nome(loadout.report(con, slots))
    assert antes["Prem"]["tenho"] == 2 and antes["Ench"]["tenho"] == 0
    assert antes["Ench"]["comprar"] == 2, antes["Ench"]["comprar"]
    assert antes["Ench"]["missing"][0]["noutra"] == {}
    assert antes["Ench"]["missing"][0]["noutra_nota"] == {"Prem": 2}

    loadout.guardar_arrumacao(con, loadout.report(con, slots))
    depois = por_nome(loadout.report(con, slots))
    assert depois["Prem"]["tenho"] == 2, depois["Prem"]["tenho"]
    assert depois["Ench"]["comprar"] == 2, depois["Ench"]["comprar"]
    assert depois["Ench"]["missing"][0]["noutra_nota"] == {"Prem": 2}, \
        depois["Ench"]["missing"][0]
    # E não é um substituto: é compra, com a nota.
    assert not depois["Ench"]["subs"], depois["Ench"]["subs"]

    # A caixa que corre PRIMEIRO não pode roubar o que está dentro da segunda.
    trocado = [dict(slots[0], prioridade=5), dict(slots[1], prioridade=1)]
    virado = por_nome(loadout.report(con, trocado))
    assert virado["Prem"]["tenho"] == 2, virado["Prem"]["tenho"]
    assert virado["Ench"]["tenho"] == 0 and virado["Ench"]["comprar"] == 2
    print("confirmar a arrumacao nao muda o que se compra, nem quem tem a copia")


def caso_carta_na_caixa_escapa_as_regras_de_material():
    """A irmã da excepção do balde, no modelo novo: uma cópia JÁ ARRUMADA na
    caixa deste deck escapa às regras de material — senão uma regra nova
    desmontava no papel um deck que está na estante.

    Desde 2026-09-09 a excepção pede uma prova a mais: a cópia tem de ter VINDO
    do balde desta caixa (`copies.balde_origem`, que a migração escreve). Sem
    ela, uma linha da `copy_allocation` escrita em bloco lavava uma correcção ao
    acabamento da cópia — foi o que pôs uma foil a fechar um slot do Cloud cEDH
    (ver `test_montada_alocacao.py`)."""
    con = base()
    deck(con, "EDH", "cedh", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 1, finish="foil", lang="pt", sub="Colecção",
        borigem="Cloud cEDH")
    s = slot("EDH", "cedh", "EDH", balde="Cloud cEDH")
    # Antes de arrumar: é PT da era Premodern e foil — o cEDH é "só EN nonfoil".
    assert por_nome(loadout.report(con, [s]))["EDH"]["tenho"] == 0
    cid = con.execute("SELECT id FROM copies").fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,1)",
                (cid, "edh"))
    con.commit()
    rep = por_nome(loadout.report(con, [s]))["EDH"]
    assert rep["tenho"] == 1, rep["tenho"]

    # E a mesma cópia, se tivesse vindo da gaveta partilhada, NÃO escapava: é a
    # diferença entre "está sleevada neste deck desde sempre" e "um registo em
    # bloco varreu-a para aqui".
    con.execute("UPDATE copies SET balde_origem = 'SPML'")
    con.commit()
    rep = por_nome(loadout.report(con, [s]))["EDH"]
    assert rep["tenho"] == 0, rep["tenho"]
    assert [c["nm"] for c in rep["contradicoes"]] == ["Lotus Petal"]
    print("uma copia ja arrumada na caixa escapa as regras de material")


def caso_lote_partido_entre_caixa_e_gaveta():
    """Um lote de 4 com 3 já na caixa e 1 solta: a excepção vale só para as 3."""
    con = base()
    deck(con, "EDH", "cedh", [("Lotus Petal", 4)])
    deck(con, "Leg", "legacy", [("Lotus Petal", 1)])
    add(con, "Lotus Petal", 4, finish="foil", lang="pt", sub="Colecção",
        borigem="Cloud cEDH")
    cid = con.execute("SELECT id FROM copies").fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,3)",
                (cid, "edh"))
    con.commit()
    rep = por_nome(loadout.report(con, [slot("EDH", "cedh", "EDH",
                                             balde="Cloud cEDH"),
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


# ---------------------------------------------------------------------------
# CAIXAS DEDICADAS (André, 2026-09-07 às 19:00)
# ---------------------------------------------------------------------------
def caso_caixa_dedicada_nao_empresta_nem_vai_buscar():
    """*"Cada deck montado deixa de partilhar cartas com outros decks."*

    Duas caixas de cEDH, um playset só: a primeira leva-o e a segunda COMPRA as
    suas em vez de dizer *"vai buscar 4 ao Blue Farm"*.

    Era o Premodern que demonstrava isto até 2026-09-08 — nessa data ele voltou
    a partilhar e ficaram dedicados o cEDH e o Pauper. Desde 2026-09-19 é a
    regra de TODAS as caixas (*"cada deck deverá ter as suas próprias cartas
    dentro, não repetindo com outros decks!"*); o cEDH continua a ser o exemplo,
    e o resto está no `test_caixas_dedicadas.py`.
    """
    con = base()
    deck(con, "C1", "cedh", [("Swords to Plowshares", 4)])
    deck(con, "C2", "cedh", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 4, lang="en", sub="Colecção")
    rep = loadout.report(con, [slot("C1", "cedh", "C1", prioridade=1,
                                    balde="Colecção"),
                               slot("C2", "cedh", "C2", prioridade=2,
                                    balde="Colecção")])
    s = por_nome(rep)
    assert s["C1"]["pct"] == 100, s["C1"]
    assert s["C2"]["noutra"] == 0, s["C2"]["noutra_caixa"]
    assert s["C2"]["comprar"] == 4, s["C2"]
    assert s["C2"]["missing"][0]["noutra"] == {}, s["C2"]["missing"][0]
    print("caixa dedicada nao empresta: a segunda compra em vez de ir buscar")


def caso_caixa_dedicada_compra_sozinha():
    """`dedicado` implica `compras_dedicadas`. Duas caixas a que falta a mesma
    carta pedem duas compras, não uma partilhada."""
    con = base()
    deck(con, "C1", "cedh", [("Sol Ring", 2)])
    deck(con, "C2", "cedh", [("Sol Ring", 2)])
    preco(con, "Sol Ring", "nonfoil", 10.0)
    rep = loadout.report(con, [slot("C1", "cedh", "C1", prioridade=1),
                               slot("C2", "cedh", "C2", prioridade=2)])
    s = por_nome(rep)
    assert rep["partilhas"] == [], rep["partilhas"]
    assert s["C1"]["comprar"] == 2 and s["C2"]["comprar"] == 2, rep
    assert rep["comprar_total"] == 4, rep["comprar_total"]
    print("duas caixas dedicadas compram duas vezes — nao ha partilha")


def caso_duel_commander_e_spml_continuam_a_partilhar():
    """SUPERSEDED a 2026-09-19: o Duel Commander e o SPML eram os dois grupos que
    ainda iam buscar um ao outro (desde a v3). Agora também não: o Modern compra
    a sua Sol Ring e sabe que tem uma no DC."""
    con = base()
    deck(con, "DC", "duel-commander", [("Sol Ring", 1)])
    deck(con, "MO", "modern", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil", sub="Colecção")
    rep = loadout.report(con, [slot("DC", "duel-commander", "DC", prioridade=1,
                                    balde="Colecção"),
                               slot("MO", "modern", "MO", prioridade=1,
                                    balde="Colecção")])
    s = por_nome(rep)
    assert s["DC"]["pct"] == 100, s["DC"]
    assert s["MO"]["noutra"] == 0 and s["MO"]["comprar"] == 1, s["MO"]
    assert s["MO"]["noutra_caixa"] == [], s["MO"]["noutra_caixa"]
    assert s["MO"]["missing"][0]["noutra_nota"] == {"DC": 1}
    print("Duel Commander e SPML ja nao partilham: o Modern compra a sua")


def caso_excepcao_por_caixa_ganha_a_do_grupo():
    """O que estiver escrito no slot ganha à regra do grupo — uma excepção é uma
    linha de config, não uma linha de código. Com UMA excepção, desde
    2026-09-19: o `dedicado` já não se escreve por caixa — um `dedicado: false`
    no slot NÃO devolve a partilha (é a regra dele para todos os decks, não uma
    preferência). O que continua a ganhar são as outras chaves (a `lingua`,
    aqui): uma caixa de Premodern com `lingua: "en"` aceita a EN.
    """
    con = base()
    deck(con, "PM1", "premodern", [("Swords to Plowshares", 4)])
    deck(con, "PM2", "premodern", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 4, lang="pt", sub="Colecção")
    slots = [slot("PM1", "premodern", "PM1", prioridade=1, balde="Colecção"),
             slot("PM2", "premodern", "PM2", prioridade=2, balde="Colecção")]
    s = por_nome(loadout.report(con, [dict(x, dedicado=False) for x in slots]))
    assert s["PM2"]["noutra"] == 0 and s["PM2"]["comprar"] == 0, s["PM2"]
    assert s["PM2"]["playset_bloqueado"] == 4, s["PM2"]["playset_faltas"]
    assert all(x["dedicado"] for x in s.values()), "dedicado: false nao tem efeito"

    # A excepção que continua a valer: uma chave de material escrita no slot.
    add(con, "Swords to Plowshares", 4, lang="en", sub="Colecção")
    s = por_nome(loadout.report(con, [slots[0],
                                      dict(slots[1], lingua="en", estrita=False)]))
    assert s["PM1"]["tenho"] == 4 and s["PM2"]["tenho"] == 4, (s["PM1"], s["PM2"])
    print("uma excepcao de material no slot ganha ao grupo; o dedicado nao se desliga")


def caso_caixa_congelada_nao_perde_copias():
    """*"Apenas mexer para actualizar."* A caixa dedicada e montada fica
    congelada: a cópia que a lista de hoje já não pede continua lá dentro — não
    volta à gaveta, não é realocada e não entra na venda."""
    con = base()
    deck(con, "PA", "pauper", [("Thoughtcast", 1)])
    add(con, "Thoughtcast", 1, sub="Colecção")
    add(con, "Lotus Petal", 1, sub="Colecção")     # saiu da lista, ficou na caixa
    cfg = [slot("PA", "pauper", "PA", prioridade=1, balde="Colecção",
                montado=True)]
    # Arruma-se a caixa com as duas cartas (é o "sleevado e na caixa" de ontem).
    for cid in [r["id"] for r in con.execute("SELECT id FROM copies")]:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?, 'pa', 1)", (cid,))
    con.commit()
    rep = loadout.report(con, cfg)
    s = por_nome(rep)["PA"]
    assert s["congelada"] is True, s
    # O Lotus Petal saiu da lista mas continua preso na caixa.
    assert [p["nm"] for p in s["presos"]] == ["Lotus Petal"], s["presos"]
    assert not any(r["nm"] == "Lotus Petal" for r in rep["venda"]), rep["venda"]
    assert not any(m["nm"] == "Lotus Petal"
                   for m in rep["arrumacao"]["movimentos"]), rep["arrumacao"]
    # E aparece no delta de actualização daquela caixa, não no plano geral.
    act = rep["actualizacoes"]["pa"]
    assert [m["nm"] for m in act["sai"]] == ["Lotus Petal"], act
    print("caixa congelada nao perde copias: o extra fica preso e sai no delta")


def caso_delta_de_actualizacao_so_se_aplica_no_botao():
    """A lista vigiada mudou: a caixa continua montada com a lista antiga e o
    delta espera. O "já arrumei tudo" geral não lhe toca; o "actualizei" dela
    aplica-o."""
    con = base()
    deck(con, "PA", "pauper", [("Thoughtcast", 1)])
    add(con, "Thoughtcast", 1, sub="Colecção")          # a carta nova, na gaveta
    add(con, "Lotus Petal", 1, sub="Colecção")          # a velha, já na caixa
    velho = con.execute("SELECT id FROM copies WHERE quantity = 1 ORDER BY id"
                        ).fetchall()[1]["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                "VALUES (?, 'pa', 1)", (velho,))
    con.commit()
    cfg = [slot("PA", "pauper", "PA", prioridade=1, balde="Colecção",
                montado=True)]

    rep = loadout.report(con, cfg)
    act = rep["actualizacoes"]["pa"]
    assert [m["nm"] for m in act["sai"]] == ["Lotus Petal"], act
    assert [m["nm"] for m in act["entra"]] == ["Thoughtcast"], act

    # O botão geral arruma a colecção e deixa a caixa congelada como está.
    loadout.guardar_arrumacao(con, loadout.report(con, cfg))
    dentro = con.execute("SELECT copy_id FROM copy_allocation WHERE slot = 'pa'"
                         ).fetchall()
    assert [r["copy_id"] for r in dentro] == [velho], dentro

    # O "actualizei" daquela caixa é que aplica o delta.
    rep = loadout.report(con, cfg)
    n = loadout.actualizar_caixa(con, rep, "pa")
    assert n == 1, n
    depois = con.execute("SELECT copy_id FROM copy_allocation WHERE slot = 'pa'"
                         ).fetchall()
    assert [r["copy_id"] for r in depois] != [velho], depois
    assert not loadout.report(con, cfg)["actualizacoes"], "o delta ficou vazio"
    print("o delta espera pelo botao 'actualizei' — o 'ja arrumei' nao lhe toca")


def caso_montado_sem_arrumacao_nao_e_congelado():
    """Uma caixa que se diz montada mas de que o vault não sabe o conteúdo não
    está congelada — não há nada para prender, e dar a lista inteira como um
    delta de *"actualização"* mentia sobre o que ele tem de fazer (é montá-la).
    É o caso do Stiflenought: `montado: true` e zero linhas na `copy_allocation`.
    """
    con = base()
    deck(con, "PA", "pauper", [("Thoughtcast", 1)])
    add(con, "Thoughtcast", 1, sub="Colecção")
    cfg = [slot("PA", "pauper", "PA", balde="Colecção", montado=True)]
    s = por_nome(loadout.report(con, cfg))["PA"]
    assert s["congelada"] is False and s["montado_por_confirmar"] is True, s
    assert not loadout.report(con, cfg)["actualizacoes"], "nada a actualizar"
    # E a página tem de o dizer, senão a caixa mente em silêncio.
    assert any("Sleevado" in t for _i, t, _c in loadout.rotulo_material(s))
    print("montada sem arrumacao confirmada: nao congela, e a pagina di-lo")


def caso_alocacao_orfa_nao_prende_copias():
    """Uma linha de `copy_allocation` para uma caixa que já não está no loadout é
    órfã. Tratá-la como uma caixa a sério tirava a cópia de circulação para
    sempre — e mostrava o `slot` cru no lugar do nome, sem erro nenhum."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 1)])
    add(con, "Sol Ring", 1, finish="foil", sub="Colecção")
    cid = con.execute("SELECT id FROM copies").fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                "VALUES (?, 'caixa-que-ja-nao-existe', 1)", (cid,))
    con.commit()
    s = por_nome(loadout.report(con, [slot("A", "legacy", "A",
                                           balde="Colecção")]))["A"]
    assert s["tenho"] == 1 and s["pct"] == 100, s
    print("alocacao orfa ignora-se: a copia nao fica presa a uma caixa apagada")


def caso_compras_sem_preco_contam_se():
    """Uma carta sem preço na base entra na lista de compras a 0 € e some no
    total. O custo de fechar tem de dizer que é um MÍNIMO, não a conta toda."""
    con = base()
    deck(con, "A", "legacy", [("Sol Ring", 1), ("Kappa Cannoneer", 2)])
    preco(con, "Sol Ring", "foil", 3.0)          # a Kappa Cannoneer não tem
    rep = loadout.report(con, [slot("A", "legacy", "A")])
    s = por_nome(rep)["A"]
    assert s["comprar"] == 3 and s["custo"] == 3.0, s
    assert s["sem_preco"] == 2, s["sem_preco"]
    assert rep["sem_preco_total"] == 2, rep["sem_preco_total"]
    print("as copias a comprar sem preco contam-se: o custo e um minimo")


# ---------------------------------------------------------------------------
# O PREMODERN VOLTOU A PARTILHAR, COM TECTO DE PLAYSET (André, 2026-09-08)
# ---------------------------------------------------------------------------
def caso_premodern_voltou_a_partilhar():
    """SUPERSEDED a 2026-09-19 — o nome ficou para o histórico.

    A 2026-09-08 o Premodern voltou a emprestar entre caixas (*"os que vêm
    depois na prioridade indicam onde estão as cartas em falta"*). A 2026-09-19
    (*"cada deck deverá ter as suas próprias cartas dentro, não repetindo com
    outros decks!"*) deixou de o fazer, como toda a gente. O que FICA da regra
    de 08/09 é o tecto de playset: a segunda caixa não vai buscar as 4 Swords
    nem as compra — o grupo já tem 4 — e diz *"não se compra (limite de 4 no
    total; está 4 no PM1)"*. Ver `test_caixas_dedicadas.py`.
    """
    con = base()
    deck(con, "PM1", "premodern", [("Swords to Plowshares", 4)])
    deck(con, "PM2", "premodern", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 4, lang="pt", sub="Colecção")
    rep = loadout.report(con, [slot("PM1", "premodern", "PM1", balde="Colecção"),
                               slot("PM2", "premodern", "PM2", balde="Colecção")])
    s = por_nome(rep)
    primeira, segunda = (s["PM1"], s["PM2"]) if s["PM1"]["prioridade"] == 1 \
        else (s["PM2"], s["PM1"])
    assert primeira["pct"] == 100 and primeira["comprar"] == 0, primeira
    assert segunda["comprar"] == 0 and segunda["noutra"] == 0, segunda
    m = segunda["missing"][0]
    assert m["noutra"] == {} and m["noutra_nota"] == {primeira["nome"]: 4}, m
    assert m["playset_bloqueado"] == 4 and m["playset_onde"] == {primeira["nome"]: 4}, m
    assert loadout.texto_playset(m, 4) == \
        f"4 não se compra (limite de 4 no total; está 4 no {primeira['nome']})"
    print("as caixas de Premodern ja nao emprestam; o tecto de 4 no total fica")

    # E o cEDH continua dedicado: a mesma pergunta, a resposta contrária.
    con2 = base()
    deck(con2, "C1", "cedh", [("Sol Ring", 1)])
    deck(con2, "C2", "cedh", [("Sol Ring", 1)])
    add(con2, "Sol Ring", 1, lang="en", sub="Colecção")
    s = por_nome(loadout.report(con2, [
        slot("C1", "cedh", "C1", prioridade=1, balde="Colecção"),
        slot("C2", "cedh", "C2", prioridade=2, balde="Colecção")]))
    assert s["C2"]["comprar"] == 1 and s["C2"]["noutra"] == 0, s["C2"]
    print("e o cEDH e o Pauper continuam dedicados")


def caso_tecto_de_playset_no_premodern():
    """*"No Premodern, afinal só vou ter até playset de cada carta."*

    Cinco caixas a pedir 4 Swords to Plowshares e uma cópia em casa: compram-se
    3, não 20 — o grupo nunca passa de 4. Desde 2026-09-19 as outras quatro
    caixas já não vão buscar as 4 à primeira (*"cada deck deverá ter as suas
    próprias cartas dentro"*): ficam com a falta POR TAPAR, dita como tal
    (`playset_bloqueado`, 16 cópias), fora do "fechar tudo". E com 5 em casa
    não se compra nenhuma.
    """
    con = base()
    preco(con, "Swords to Plowshares", "nonfoil", 2.0)
    nomes = ["PM1", "PM2", "PM3", "PM4", "PM5"]
    for n in nomes:
        deck(con, n, "premodern", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 1, lang="pt", sub="Colecção")
    slots = [slot(n, "premodern", n, balde="Colecção") for n in nomes]
    rep = loadout.report(con, slots)
    assert rep["comprar_total"] == 3, rep["comprar_total"]
    assert rep["custo_total"] == 6.0, rep["custo_total"]
    assert rep["bloqueado_total"] == 16, rep["bloqueado_total"]
    assert rep["noutra_total"] == 0, rep["noutra_total"]
    print("necessidade 4 com 1 em casa: compram-se 3; as outras caixas ficam por tapar")

    # Com 5 em casa não se compra nada.
    add(con, "Swords to Plowshares", 4, lang="pt", sub="Colecção")
    rep = loadout.report(con, slots)
    assert rep["comprar_total"] == 0 and rep["custo_total"] == 0.0, rep["custo_total"]
    print("com 5 em casa nao se compra nenhuma")


def caso_excedente_de_playset_do_premodern_vai_para_venda():
    """O que passa das 4 PT — somando a Colecção e a Caixa RL (PT) — é venda.

    É a regra geral do playset (`sell_list`), e o que este caso tranca é que ela
    conta a colecção INTEIRA: contar 4 por balde deixava passar o dobro, porque
    as PT da Caixa Reserved List servem o Premodern como as outras.

    A cópia que uma caixa levou nunca entra aqui — é a regra de sempre, e é ela
    que explica porque é que o excedente é uma e não duas: quatro estão dentro da
    caixa.
    """
    con = base()
    deck(con, "PM1", "premodern", [("Replenish", 4)])
    add(con, "Replenish", 2, lang="pt", sub="Colecção")
    add(con, "Replenish", 3, lang="pt", sub="Caixa Reserved List")
    rep = loadout.report(con, [slot("PM1", "premodern", "PM1", balde="Colecção")])
    s = por_nome(rep)["PM1"]
    assert s["pct"] == 100 and s["comprar"] == 0, s
    # A Caixa RL (PT) alimentou o Premodern: 2 da Colecção + 2 de lá.
    assert s["origens"] == {"Colecção": 2, "Caixa RL (PT)": 2}, s["origens"]
    # É Reserved List, por isso a saída é do lado da RL — e desde 2026-09-08 a
    # RL passa ainda pela regra dos 5 % (`avaliar_rl`). Sem preços nenhuns nesta
    # base, cai em `rl_sem_historico`: não se vende uma RL sem saber se subiu.
    # O motivo por que ela ia à venda fica em `porque_venderia`, e é esse que
    # este caso tranca.
    linhas = [r for r in rep["venda_rl"] + rep["rl_sem_historico"]
              if r["nm"] == "Replenish"]
    assert sum(r["q"] for r in linhas) == 1, linhas
    assert linhas[0]["porque_venderia"] == "excedente (mais de 4)", linhas[0]
    assert not [r for r in rep["venda"] if r["nm"] == "Replenish"], rep["venda"]
    print("o que passa das 4 PT (Colecção + Caixa RL) e excedente de venda")


def caso_tecto_de_playset_diz_o_que_nao_se_compra():
    """Uma caixa que precise de mais do que o tecto permite tem de o DIZER.

    Se a falta saísse só da conta das compras, a caixa ficava à espera de uma
    carta que ninguém vai comprar — e não havia como perceber porquê.
    """
    con = base()
    preco(con, "Swords to Plowshares", "nonfoil", 2.0)
    # 4 no main + 1 no side: dentro da mesma caixa as faltas somam (estão na mesa
    # ao mesmo tempo), mas o tecto do grupo são 4.
    deck(con, "PM1", "premodern", [("Swords to Plowshares", 4)],
         side=[("Swords to Plowshares", 1)])
    rep = loadout.report(con, [slot("PM1", "premodern", "PM1", balde="Colecção")])
    s = por_nome(rep)["PM1"]
    assert s["comprar"] == 4 and s["custo"] == 8.0, s
    assert s["playset_bloqueado"] == 1, s["playset_bloqueado"]
    assert [(m["nm"], m["playset_bloqueado"]) for m in s["playset_faltas"]] == \
        [("Swords to Plowshares", 1)], s["playset_faltas"]
    lim = rep["limites"]
    assert [(g["nm"], g["bloqueado"], g["tecto"]) for g in lim] == \
        [("Swords to Plowshares", 1, 4)], lim
    assert lim[0]["caixas"] == [{"slot": "pm1", "caixa": "PM1", "q": 1,
                                 "board": "side"}], lim[0]["caixas"]
    print("o que o tecto corta diz-se: 'falta 1 que nao se compra'")


def caso_basicas_fora_do_tecto_de_playset():
    """As básicas são a excepção: um deck joga 12 Ilhas e não são um playset.

    Nunca chegam à conta do tecto porque o `allocate` as dá sempre por tidas —
    este caso tranca isso, porque um tecto que apanhasse as básicas punha metade
    de cada deck de Premodern a dizer *"falta 8 que não se compra"*.
    """
    con = base()
    deck(con, "PM1", "premodern", [("Island", 12), ("Swords to Plowshares", 4)])
    rep = loadout.report(con, [slot("PM1", "premodern", "PM1", balde="Colecção")])
    s = por_nome(rep)["PM1"]
    assert s["playset_bloqueado"] == 0, s["playset_faltas"]
    assert s["comprar"] == 4, s["comprar"]
    ilha = [m for m in s["have"] if m["nm"] == "Island"][0]
    assert ilha["got"] == 12 and ilha["playset_bloqueado"] == 0, ilha
    print("as basicas ficam fora do tecto de playset")


def caso_compras_partilhadas_nao_passam_do_tecto():
    """O tecto conta o que o GRUPO já tem: duas caixas a pedir 4 e duas cópias
    em casa (na primeira) compram 2, não 4 nem 8 — 2 compradas mais 2 em casa
    são 4, e ele disse quatro. (O nome vem de 2026-09-08, quando havia partilha
    de compras; desde 2026-09-19 não há, e o tecto passou a ser a única conta.)
    """
    con = base()
    preco(con, "Swords to Plowshares", "nonfoil", 2.0)
    for n in ("PM1", "PM2"):
        deck(con, n, "premodern", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 2, lang="pt", sub="Colecção")
    slots = [slot("PM1", "premodern", "PM1", balde="Colecção"),
             slot("PM2", "premodern", "PM2", balde="Colecção")]
    rep = loadout.report(con, slots)
    assert rep["comprar_total"] == 2, rep["comprar_total"]
    total = rep["comprar_total"] + sum(l["q"] for l in rep["pool"]
                                       ["Swords to Plowshares"])
    assert total == 4, total
    print("comprar + o que ja tem nunca passa do tecto de playset")


def caso_premodern_ordena_por_pct_completo():
    """*"Ordenamos os decks por prioridade (...) para já a prioridade vem por
    ordem de % completo."*

    A caixa mais perto de fechar escolhe primeiro, e o `prioridade` do config
    deixa de decidir — está escrito ao contrário aqui de propósito.
    """
    con = base()
    deck(con, "Perto", "premodern", [("Swords to Plowshares", 2)])
    deck(con, "Longe", "premodern", [("Swords to Plowshares", 1), ("Replenish", 1),
                                     ("Opalescence", 1), ("Lotus Petal", 1)])
    add(con, "Swords to Plowshares", 2, lang="pt", sub="Colecção")
    rep = loadout.report(con, [
        slot("Longe", "premodern", "Longe", prioridade=1, balde="Colecção"),
        slot("Perto", "premodern", "Perto", prioridade=2, balde="Colecção")])
    s = por_nome(rep)
    assert s["Perto"]["pct_coleccao"] == 100 and s["Longe"]["pct_coleccao"] == 25, s
    assert s["Perto"]["prioridade"] == 1 and s["Longe"]["prioridade"] == 2, \
        (s["Perto"]["prioridade"], s["Longe"]["prioridade"])
    assert s["Perto"]["posicao_grupo"] == 1 and s["Longe"]["posicao_grupo"] == 2
    assert s["Perto"]["prioridade_por"] == "pct"
    print("no Premodern manda a % completo, nao o numero do config")

    # Empate: decide o nome, para a ordem não mudar de corrida para corrida.
    deck(con, "Bea", "premodern", [("Replenish", 1)])
    deck(con, "Ana", "premodern", [("Opalescence", 1)])
    s = por_nome(loadout.report(con, [
        slot("Bea", "premodern", "Bea", prioridade=1, balde="Colecção"),
        slot("Ana", "premodern", "Ana", prioridade=2, balde="Colecção")]))
    assert s["Ana"]["pct_coleccao"] == s["Bea"]["pct_coleccao"] == 0
    assert s["Ana"]["prioridade"] == 1 and s["Bea"]["prioridade"] == 2, s
    print("empate na percentagem: desempata o nome")

    # E os outros grupos não mudaram: o `prioridade` do config continua a mandar.
    con2 = base()
    for n in ("A", "B"):
        deck(con2, n, "legacy", [("Sol Ring", 1)])
    s = por_nome(loadout.report(con2, [slot("A", "legacy", "A", prioridade=2),
                                       slot("B", "legacy", "B", prioridade=1)]))
    assert s["B"]["prioridade"] == 1 and not s["B"].get("prioridade_por"), s["B"]
    print("fora do Premodern a ordem continua a ser a do config")


def caso_pct_da_ordem_e_o_da_coleccao_inteira():
    """A percentagem que ordena é medida ANTES de alocar.

    Com a de depois, a caixa que ficasse em primeiro roubava a percentagem à
    seguinte e as duas trocavam de lugar a cada corrida. Aqui as duas pedem a
    mesma carta e só há um playset: a de depois dá 100%/0%, a de antes dá
    100%/100% — e é a segunda que decide a ordem.
    """
    con = base()
    for n in ("Ana", "Bea"):
        deck(con, n, "premodern", [("Swords to Plowshares", 4)])
    add(con, "Swords to Plowshares", 4, lang="pt", sub="Colecção")
    s = por_nome(loadout.report(con, [
        slot("Ana", "premodern", "Ana", balde="Colecção"),
        slot("Bea", "premodern", "Bea", balde="Colecção")]))
    assert s["Ana"]["pct_coleccao"] == s["Bea"]["pct_coleccao"] == 100, s
    assert s["Ana"]["pct"] == 100 and s["Bea"]["pct"] == 0, (s["Ana"]["pct"],
                                                            s["Bea"]["pct"])
    assert s["Ana"]["prioridade"] == 1, s["Ana"]["prioridade"]
    print("a % que ordena e a da coleccao inteira, antes de alocar")


def run():
    for fn in (caso_uma_copia_uma_caixa, caso_noutra_caixa_nao_e_compra,
               caso_noutra_caixa_e_compra_misturadas,
               caso_compra_partilhada_e_o_maximo_nao_a_soma,
               caso_main_e_side_da_mesma_caixa_continuam_a_somar,
               caso_pools_de_material_diferentes_nao_se_partilham,
               caso_pool_foil_en_junta_o_duel_commander_e_o_spml,
               caso_compras_dedicadas_nao_partilham,
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
               caso_backup_e_venda, caso_a_chave_antiga_reter_extras_meses_continua_a_guardar,
               caso_substituto_nao_se_vende, caso_variantes,
               caso_slot_vazio, caso_preco_foil,
               caso_permanente_escolhe_antes_do_candidato,
               caso_candidato_promovido_a_permanente_recebe,
               caso_arrumacao_diz_de_onde_tirar_e_para_onde_vai,
               caso_ja_arrumei_persiste_e_o_plano_esvazia,
               caso_arrumar_nao_transforma_ir_buscar_em_compra,
               caso_carta_na_caixa_escapa_as_regras_de_material,
               caso_lote_partido_entre_caixa_e_gaveta,
               caso_nonfoil_nunca_e_foil,
               caso_rotulo_material_diz_a_classe_e_as_fontes,
               caso_caixa_dedicada_nao_empresta_nem_vai_buscar,
               caso_caixa_dedicada_compra_sozinha,
               caso_duel_commander_e_spml_continuam_a_partilhar,
               caso_excepcao_por_caixa_ganha_a_do_grupo,
               caso_caixa_congelada_nao_perde_copias,
               caso_delta_de_actualizacao_so_se_aplica_no_botao,
               caso_montado_sem_arrumacao_nao_e_congelado,
               caso_alocacao_orfa_nao_prende_copias,
               caso_compras_sem_preco_contam_se,
               caso_premodern_voltou_a_partilhar,
               caso_tecto_de_playset_no_premodern,
               caso_excedente_de_playset_do_premodern_vai_para_venda,
               caso_tecto_de_playset_diz_o_que_nao_se_compra,
               caso_basicas_fora_do_tecto_de_playset,
               caso_compras_partilhadas_nao_passam_do_tecto,
               caso_premodern_ordena_por_pct_completo,
               caso_pct_da_ordem_e_o_da_coleccao_inteira):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
