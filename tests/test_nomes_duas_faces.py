"""O CRUZAMENTO NOME-DE-LISTA <-> CATALOGO (2026-10-04).

A AVARIA: o cruzamento era IGUALDADE DE NOME, e o catalogo guarda as cartas de
duas faces com o nome inteiro (`Witch Enchanter // Witch-Blessed Meadow`)
enquanto as listas trazem so a frente (`Witch Enchanter`). Quando falha, a carta
fica SEM TIPO, SEM PRECO e CONTADA COMO NAO TIDA -- ou seja, a aplicacao mandava
COMPRAR cartas que o Andre JA TEM.

Medido na base dele: 240 nomes distintos nao casavam, em 7 983 linhas e 4 258
das 7 724 listas (55 %). Duas vias: 181 nomes sao a FRENTE de uma dupla face,
33 sao o SEPARADOR escrito de outra maneira (`Wear/Tear`), e 26 ficam
desconhecidos (25 que nem a Scryfall tem, mais 1 variante de pontuacao).

Sem rede: tudo contra uma base construida aqui, com nomes REAIS do catalogo.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

#: Cartas de DUAS FACES, como a Scryfall as escreve. Sao as tres que o André
#: nomeou (e que ele TEM), mais a `Wear // Tear` da via do separador.
DUPLAS = [
    ("Witch Enchanter // Witch-Blessed Meadow", "mh3", "189",
     "Creature — Elf Druid // Land"),
    ("Sink into Stupor // Soporific Springs", "mom", "76",
     "Instant // Land"),
    ("Tamiyo, Inquisitive Student // Tamiyo, Seasoned Scholar", "mom", "64",
     "Legendary Creature — Moonfolk Wizard // Legendary Planeswalker — Tamiyo"),
    ("Wear // Tear", "dgm", "135", "Instant // Instant"),
    ("Agadeem's Awakening // Agadeem, the Undercrypt", "znr", "90",
     "Sorcery // Land"),
]
#: As duas armadilhas: cartas a serio com barras no nome que NAO sao separador.
#: Sao as unicas duas que existem no catalogo (112 755 impressoes, 974 nomes com
#: ` // `), e canonizar as cegas partia-as em duas faces que nao existem.
ARMADILHAS = [("SP//dr, Piloted by Peni", "spm", "7", "Legendary Creature — Robot"),
              ("Summon: Choco/Mog", "fin", "233",
               "Enchantment Creature — Saga Bird Moogle")]

#: SINTETICO, e dito: hoje o catalogo NAO tem nenhum par assim (verificado, zero
#: nomes reais cuja canonizacao seja outro nome real). Esta aqui para trancar a
#: ORDEM dos ramos: se um dia aparecer uma carta cujo nome canonizado seja outra
#: carta, o nome TAL E QUAL tem de ganhar. Sem este par, a regra da ordem nao e
#: falsificavel e o teste nao provava nada.
COLISAO = [("SP // dr, Piloted by Peni", "zzz", "1", "Sorcery")]
SIMPLES = [("Swords to Plowshares", "3ed", "28", "Instant"),
           ("Plains", "unh", "136", "Basic Land — Plains")]


def _base():
    """Uma base nova com catalogo, as duplas, as armadilhas e copias do André."""
    tmp = tempfile.mkdtemp(prefix="mtg-duasfaces-")
    db_ = os.path.join(tmp, "vault.db")
    cat = os.path.join(tmp, "catalog.db")
    # O MTGVAULT_DB e o MTGVAULT_HOME fixam-se SEMPRE os dois (regra do
    # CLAUDE.md): os ficheiros que acompanham a base saem da pasta do
    # MTGVAULT_DB, e sem isto a bateria escrevia no data/ a serio.
    os.environ["MTGVAULT_HOME"] = tmp
    os.environ["MTGVAULT_DB"] = db_
    os.environ["MTGVAULT_CATALOG"] = cat
    os.environ.pop("MTGVAULT_CONFIG", None)
    for m in [k for k in list(sys.modules) if k.startswith("mtgvault")]:
        del sys.modules[m]
    from mtgvault import db as dbmod
    con = dbmod.connect()
    dbmod.init(con)
    sid = 0
    for nome, sc, num, tl in DUPLAS + ARMADILHAS + COLISAO + SIMPLES:
        sid += 1
        s = "%08d-0000-0000-0000-000000000000" % sid
        con.execute(
            "INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name, "
            "set_code, collector_number, lang, type_line, color_identity, "
            "finishes, released_at, digital, reserved) "
            "VALUES (?,?,?,?,?,'en',?,'',?,'2024-01-01',0,0)",
            (s, "o" + s[1:], nome, sc, num, tl, '["nonfoil","foil"]'))
        con.execute("INSERT OR REPLACE INTO price_latest "
                    "(scryfall_id, source, finish, low, trend, receita, date) "
                    "VALUES (?,?, 'nonfoil', 1.0, 2.0, 'ct-ofertas', '2026-10-04')",
                    (s, "cardtrader"))
    con.commit()
    return tmp, con, dbmod


class CasoBase(unittest.TestCase):
    def setUp(self):
        self.tmp, self.con, self.dbmod = _base()
        from mtgvault import collection, scryfall
        self.collection, self.scryfall = collection, scryfall

    def _sid(self, nome):
        r = self.con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                             (nome,)).fetchone()
        self.assertIsNotNone(r, "o fixture nao tem %r" % nome)
        return r[0]

    def _tenho(self, nome, q):
        """Mete `q` copias da carta `nome` (o nome INTEIRO do catalogo)."""
        self.con.execute(
            "INSERT INTO sub_collections (name, purpose) "
            "VALUES ('Colecção', 'player') ON CONFLICT(name) DO NOTHING")
        bid = self.con.execute(
            "SELECT id FROM sub_collections WHERE name = 'Colecção'").fetchone()[0]
        self.con.execute(
            "INSERT INTO copies (scryfall_id, quantity, finish, language, "
            "condition, purpose, sub_collection_id) "
            "VALUES (?,?, 'nonfoil', 'en', 'NM', 'player', ?)",
            (self._sid(nome), q, bid))
        self.con.commit()


class CasoResolucao(CasoBase):
    """A resolucao de um nome de lista para o nome do catalogo."""

    def caso_a_frente_resolve_para_o_nome_inteiro(self):
        """`Witch Enchanter` -> `Witch Enchanter // Witch-Blessed Meadow`."""
        for inteiro, *_ in DUPLAS:
            frente = inteiro.split(" // ")[0]
            self.assertEqual(self.scryfall.resolver(self.con, frente), inteiro,
                             "a frente %r nao resolveu" % frente)

    def caso_wear_tear_e_wear_barra_tear_dao_a_mesma_carta(self):
        """As quatro formas do separador resolvem para `Wear // Tear`."""
        for escrito in ("Wear/Tear", "Wear // Tear", "Wear / Tear", "Wear//Tear"):
            self.assertEqual(self.scryfall.resolver(self.con, escrito),
                             "Wear // Tear",
                             "%r nao resolveu para Wear // Tear" % escrito)

    def caso_a_chave_e_a_mesma_para_as_duas_escritas(self):
        """A CHAVE dos dicionarios e a frente canonizada, igual nos dois lados."""
        self.assertEqual(self.scryfall.chave("Wear/Tear"), "Wear")
        self.assertEqual(self.scryfall.chave("Wear // Tear"), "Wear")
        self.assertEqual(self.scryfall.chave("Witch Enchanter"), "Witch Enchanter")
        self.assertEqual(
            self.scryfall.chave("Witch Enchanter // Witch-Blessed Meadow"),
            "Witch Enchanter")

    def caso_uma_barra_que_nao_e_separador_nao_se_estraga(self):
        """`SP//dr` e `Summon: Choco/Mog` sao cartas a serio: o nome TAL E QUAL
        tem de ganhar, senao a canonizacao parte-as em duas faces que nao
        existem. Verificado no catalogo inteiro: zero nomes reais cuja
        canonizacao seja outro nome real.

        O par do `COLISAO` e sintetico e torna a regra da ORDEM falsificavel: o
        fixture tem `SP//dr, Piloted by Peni` E `SP // dr, Piloted by Peni`, e a
        resolucao do primeiro tem de dar o primeiro.
        """
        for nome, *_ in ARMADILHAS:
            self.assertEqual(self.scryfall.resolver(self.con, nome), nome,
                             "a canonizacao estragou %r" % nome)
        # ... e a ordem dos ramos: o exacto ANTES do canonizado.
        self.assertEqual(
            self.scryfall.resolver(self.con, "SP//dr, Piloted by Peni"),
            "SP//dr, Piloted by Peni",
            "o canonizado roubou a resposta ao nome tal e qual")

    def caso_um_nome_que_nao_existe_fica_DESCONHECIDO(self):
        """`None` e DESCONHECIDA, e nunca «nao tenho»: nao se inventa a carta."""
        for inventado in ("Ademi of the Silkchutes", "Zora, Spider Fancier",
                          "Carta Que Nao Existe"):
            self.assertIsNone(self.scryfall.resolver(self.con, inventado))
        self.assertEqual(
            self.scryfall.desconhecidas(
                self.con, ["Witch Enchanter", "Ademi of the Silkchutes",
                           "Swords to Plowshares", "Wear/Tear"]),
            ["Ademi of the Silkchutes"])


class CasoPosse(CasoBase):
    """O que ele TEM aparece — era isto que a avaria lhe escondia."""

    def caso_as_cinco_witch_enchanter_aparecem(self):
        """Ele tem 5; a aplicacao dizia 0 e mandava comprar."""
        self._tenho("Witch Enchanter // Witch-Blessed Meadow", 5)
        from mtgvault import paginas
        self.assertEqual(paginas.posse_total(self.con).get("Witch Enchanter"), 5)

    def caso_as_cinco_sink_into_stupor_aparecem(self):
        self._tenho("Sink into Stupor // Soporific Springs", 5)
        from mtgvault import paginas
        self.assertEqual(paginas.posse_total(self.con).get("Sink into Stupor"), 5)

    def caso_as_quatro_tamiyo_aparecem(self):
        self._tenho("Tamiyo, Inquisitive Student // Tamiyo, Seasoned Scholar", 4)
        from mtgvault import paginas
        self.assertEqual(
            paginas.posse_total(self.con).get("Tamiyo, Inquisitive Student"), 4)

    def caso_as_duas_wear_tear_aparecem_escrito_de_qualquer_maneira(self):
        """A posse e indexada pela frente do catalogo (`Wear`) e a lista pede
        `Wear/Tear`: sem a chave canonica as 2 copias contavam ZERO."""
        self._tenho("Wear // Tear", 2)
        from mtgvault import paginas
        pt = paginas.posse_total(self.con)
        for escrito in ("Wear/Tear", "Wear // Tear", "Wear"):
            self.assertEqual(pt.get(escrito), 2,
                             "a posse nao respondeu a %r" % escrito)

    def caso_marcas_de_conta_as_copias_de_uma_dupla_face(self):
        self._tenho("Witch Enchanter // Witch-Blessed Meadow", 5)
        from mtgvault import marcas
        self.assertEqual(marcas.de(self.con, "Witch Enchanter")["q"], 5)


class CasoDeck(CasoBase):
    """O «tens X de Y» de um deck, que e o numero por que ele decide."""

    def _deck(self, cartas):
        self.con.execute("INSERT INTO decks (name, format) VALUES ('T','modern')")
        did = self.con.execute("SELECT id FROM decks WHERE name='T'").fetchone()[0]
        for nm, q in cartas:
            self.con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity,"
                             " board) VALUES (?,?,?, 'main')", (did, nm, q))
        self.con.commit()
        return {"cards": [("main", nm, q) for nm, q in cartas]}

    def caso_o_deck_conta_as_duplas_que_ele_tem(self):
        """4 Witch Enchanter + 2 Wear/Tear, e ele tem as 6: 6 de 6, 100 %."""
        self._tenho("Witch Enchanter // Witch-Blessed Meadow", 5)
        self._tenho("Wear // Tear", 2)
        d = self._deck([("Witch Enchanter", 4), ("Wear/Tear", 2)])
        from mtgvault import decks_vista, marcas
        c = decks_vista.conta_do_deck(d, marcas.posse(self.con))
        self.assertEqual((c["tem"], c["total"], c["pct"]), (6, 6, 100))

    def caso_uma_desconhecida_nao_passa_por_nao_tenho(self):
        """Conta no total (o deck pede-a) e NUNCA em `tem`, e o numero DI-LO."""
        self._tenho("Witch Enchanter // Witch-Blessed Meadow", 4)
        d = self._deck([("Witch Enchanter", 4),
                        ("Ademi of the Silkchutes", 1)])
        from mtgvault import decks_vista, marcas, scryfall
        nms = [nm for _b, nm, _q in d["cards"]]
        desc = {n: a is None
                for n, a in scryfall.resolver_muitos(self.con, nms).items()}
        c = decks_vista.conta_do_deck(d, marcas.posse(self.con), desc)
        self.assertEqual(c["total"], 5)
        self.assertEqual(c["tem"], 4)
        self.assertEqual(c["desconhecidas"], 1,
                         "a desconhecida tem de se contar a parte")


class CasoPreco(CasoBase):
    """O PRECO de uma carta de duas faces: era `None` em todo o vault."""

    def caso_card_price_responde_a_uma_dupla_face(self):
        from mtgvault import loadout
        for inteiro, *_ in DUPLAS:
            frente = inteiro.split(" // ")[0]
            p, _fin = loadout.card_price(self.con, frente)
            self.assertIsNotNone(p, "%r continua sem preco" % frente)

    def caso_card_price_responde_ao_separador_escrito_de_outra_maneira(self):
        from mtgvault import loadout
        p, _ = loadout.card_price(self.con, "Wear/Tear")
        self.assertIsNotNone(p, "Wear/Tear continua sem preco")

    def caso_o_tipo_de_uma_dupla_face_nao_e_vazio(self):
        """Sem tipo, a carta caia no grupo «Outras» da pagina do deck."""
        from mtgvault import paginas
        tm = paginas.tipos(self.con, ["Witch Enchanter", "Wear/Tear",
                                      "Agadeem's Awakening"])
        self.assertEqual(tm.get("Witch Enchanter"), "Creature")
        self.assertEqual(tm.get("Wear/Tear"), "Instant")
        self.assertEqual(tm.get("Agadeem's Awakening"), "Sorcery")


class CasoUmSitioSo(unittest.TestCase):
    """A resolucao passa por UMA funcao. Chumba se aparecer um segundo caminho.

    É a licao do `event_tier`, do `e_foil`, do `vistoId` e do `precos.sql()`:
    dois caminhos a responder a mesma pergunta discordam um dia qualquer, em
    silencio. Este caso varre o codigo vivo a procura de quem volte a cruzar um
    nome de carta com o catalogo a mao.
    """

    #: Os padroes proibidos fora do `scryfall.py`. O `' //%'`/`' // %'` como
    #: expressao de LIKE e o pior: alem de divergir, da `SCAN cards`.
    PROIBIDOS = (
        "LIKE ? || ' //%'",
        "LIKE ? || ' // %'",
        'LIKE ? || " //%"',
        "+ \" // %\"",
        "+ ' // %'",
    )
    #: Quem pode falar da forma `X // Y` sem passar pelo `scryfall`. Sao sitios
    #: que leem o nome que o CATALOGO deu (nao cruzam um nome de lista) ou que
    #: o `scryfall` ja serve por dentro.
    PERDOADOS = {
        "mtgvault/scryfall.py",       # é a casa da regra
        "tests",
        "_revisao",
        "_scratch",
    }

    def _ficheiros(self):
        for p in sorted(RAIZ.glob("*.py")) + sorted((RAIZ / "mtgvault").glob("*.py")):
            rel = p.relative_to(RAIZ).as_posix()
            if any(rel.startswith(x) for x in self.PERDOADOS):
                continue
            yield rel, p.read_text(encoding="utf-8")

    def caso_nenhum_sitio_cruza_nomes_a_mao(self):
        maus = []
        for rel, t in self._ficheiros():
            for pad in self.PROIBIDOS:
                if pad in t:
                    maus.append((rel, pad))
        self.assertEqual(maus, [],
                         "cruzamento de nome escrito a mao (usa o "
                         "scryfall.sql_nome/params_nome ou o scryfall.chave): "
                         + repr(maus))

    #: Os TRES sitios onde o `.split(" // ")` fica, e porque: partem um
    #: `type_line` (`Instant // Land` -> `Instant`), que NAO e um nome de carta.
    #: Tudo o resto passou a `scryfall.chave` a 2026-10-04 (25 sitios).
    TIPO_LINE_OK = 3

    def caso_o_split_do_separador_nao_se_refaz_a_mao(self):
        """`.split(" // ")[0]` sobre um NOME e o `scryfall.chave` escrito a mao.

        Ficam exactamente tres, e sao `type_line`. Se este numero subir, alguem
        voltou a escrever a regra ao lado em vez de a usar — e e assim que duas
        respostas a mesma pergunta nascem.
        """
        onde = [(rel, t.count('.split(" // ")'))
                for rel, t in self._ficheiros() if '.split(" // ")' in t]
        n = sum(c for _r, c in onde)
        self.assertEqual(
            n, self.TIPO_LINE_OK,
            "o `.split(\" // \")` a mao esta em %d sitios (esperados %d, todos "
            "`type_line`): %r — usa o scryfall.chave"
            % (n, self.TIPO_LINE_OK, onde))

    def caso_a_funcao_unica_existe_e_e_indexada(self):
        """O predicado tem de ser o de intervalo, nunca um LIKE com % a frente."""
        from mtgvault import scryfall
        sql = scryfall.sql_nome("c.name")
        self.assertNotIn("LIKE", sql.upper())
        self.assertEqual(sql.count("?"), 6)
        self.assertEqual(len(scryfall.params_nome("Wear/Tear")), 6)
        # O canonizado entra nos ramos 4-6, a frente dele nos limites.
        p = scryfall.params_nome("Wear/Tear")
        self.assertEqual(p[0], "Wear/Tear")
        self.assertEqual(p[3], "Wear // Tear")


class CasoPlano(CasoBase):
    """O predicado tem de usar o indice. Foi isto que partiu o site a 02/10."""

    def caso_o_predicado_entra_pelo_indice(self):
        linhas = [r[-1] for r in self.con.execute(
            "EXPLAIN QUERY PLAN SELECT scryfall_id FROM catalog.cards WHERE "
            + self.scryfall.sql_nome("name"),
            self.scryfall.params_nome("Witch Enchanter"))]
        junto = " | ".join(linhas)
        self.assertNotIn("SCAN cards", junto,
                         "o predicado passou a varrer o catalogo: " + junto)
        self.assertIn("ix_cards_name", junto,
                      "o predicado deixou de usar o ix_cards_name: " + junto)

    def caso_o_historico_nao_perde_o_indice(self):
        """O `_historico` junta a `price_history`, que e grande: ali o nome
        RESOLVE-SE antes e compara-se por igualdade. Com o predicado, o plano
        trocava para `SCAN price_history` e a consulta ia de 0,1 ms para
        21,7 ms (medido) — o `report` de 0,7 s para 12,9 s."""
        from mtgvault import loadout, precos
        expr = precos.sql(alias="h")
        linhas = [r[-1] for r in self.con.execute(
            f"EXPLAIN QUERY PLAN SELECT h.date, {expr} t FROM price_history h "
            "JOIN cards c ON c.scryfall_id = h.scryfall_id "
            "WHERE c.name = ? AND h.source = ?",
            ("Witch Enchanter // Witch-Blessed Meadow", precos.fonte()))]
        junto = " | ".join(linhas)
        self.assertNotIn("SCAN h", junto, "o historico varre a price_history")
        # ... e a funcao a serio continua a responder a frente.
        self.assertIsInstance(
            loadout._historico(self.con, "Witch Enchanter", "nonfoil"), list)


def _correr():
    carregador = unittest.TestLoader()
    carregador.testMethodPrefix = "caso_"
    suite = unittest.TestSuite(
        carregador.loadTestsFromTestCase(c) for c in
        (CasoResolucao, CasoPosse, CasoDeck, CasoPreco, CasoUmSitioSo, CasoPlano))
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if r.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(_correr())
