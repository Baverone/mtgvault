"""A BARRA DE MONTAGEM: marcar as cartas todas é dizer que o deck está montado.

André, 2026-09-08, à letra: *"Não é mais fácil confirmares que eu seleccionei
todas as cartas do deck, e assim eu confirmo que montei o deck?"* Ele estava à
frente da estante, no telemóvel, a marcar cartas — e não encontrou o *"Sim, está
montada assim"*, que fica no fim de 58 linhas.

O que aqui se tranca:

  1. **a barra conta o que a grelha desenhou** — o `marcar_q` do Python e os ids
     das checkboxes têm de dar o mesmo número (uma barra a dizer "0 de 58" com
     58 cartas por baixo não daria erro nenhum: é o padrão do `event_tier` do
     lado do browser);
  2. **marcar tudo = montada**: o registo completo põe a caixa em `montada` e a
     `copy_allocation` com todas as cópias;
  3. **registo PARCIAL**: com algumas marcadas grava-se só essas, a caixa sobe a
     `permanente` (nunca a `montada`) e diz *"N de M na caixa"*;
  4. **anular**: repõe a alocação e o estado exactamente como estavam, sem
     backup — é o inverso de uma escrita de há segundos, não um `desmontar`;
  5. o que é de OUTRA caixa não impede esta de ficar completa;
  6. o `auto_registar` vem do config, e a barra **não existe** no site publicado
     (lá o endpoint não existe, e uma barra que não regista é pior do que nada).

Não abre socket nenhum nem toca na rede.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    # Sem regras de material: o que aqui se mede é a contagem da barra, e uma
    # regra de língua a tirar cópias de vista só tornava os números opacos.
    "regras_por_formato": [
        {"grupo": "legacy", "formatos": ["legacy"], "dedicado": False},
    ],
    "caixas": [
        # CANDIDATA de propósito: é assim que se vê a subida a `permanente` do
        # registo parcial. Uma caixa que já fosse permanente não provava nada.
        {"slot": "a", "nome": "Caixa A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "estado": "candidata", "prioridade": 1},
        {"slot": "b", "nome": "Caixa B", "formato": "legacy", "fonte": "deck",
         "ref": "B", "balde": "Colecção", "estado": "candidata", "prioridade": 2},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import caixas, db, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# O `webapp._caixa` regenera as páginas depois de cada escrita, e escreve-as no
# `webapp.ROOT` — que é a raiz do repositório. Apontado aqui, logo no import: um
# POST bem sucedido a meio de um teste reescrevia o `deckboxes.html` do
# repositório com dados de mentira, e o `git status` era a única pista.
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

# (nome, edição, tipo). A Island é a básica: entra no bloco próprio do painel.
CATALOGO = [
    ("Wrath of God", "4ed", "Sorcery"),
    ("Ancestral Vision", "tsp", "Sorcery"),
    ("Swamp Dweller", "leg", "Creature"),
    ("Sol Ring", "c21", "Artifact"),
    ("Island", "unh", "Basic Land — Island"),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, tl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare',?,2,'U',?,'2004-11-19',?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), tl,
             json.dumps(["nonfoil"]),
             json.dumps({"legacy": "legal", "commander": "legal"})))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    return con


def deck(con, nome, cartas):
    """`cartas` = [(nome, quantidade, bloco)]."""
    con.execute("INSERT INTO decks (name, format) VALUES (?, 'legacy')", (nome,))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q, board in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,?)", (did, nm, q, board))
    con.commit()
    return did


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


def montavel():
    """Uma caixa com as três coisas que se marcam: main, sideboard e básicas.

    Main: Wrath of God + Ancestral Vision. Sideboard: Swamp Dweller. E 3 Island
    REGISTADAS na colecção (um lote de 3 = uma checkbox que vale 3 cópias, que é
    precisamente o caso em que uma contagem por linhas dava o número errado).
    """
    con = base()
    deck(con, "A", [("Wrath of God", 1, "main"), ("Ancestral Vision", 1, "main"),
                    ("Swamp Dweller", 1, "side"), ("Island", 3, "main")])
    for nm in ("Wrath of God", "Ancestral Vision", "Swamp Dweller"):
        add(con, nm, 1)
    add(con, "Island", 3)
    return con


def repor(extra=None):
    cfg = json.loads(json.dumps(CFG))
    if extra:
        cfg.update(extra)
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def caixa(con, slot="a", editable=True):
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=editable)
    return next(c for c in d["caixas"] if c["slot"] == slot), rep, d


def ids_dos_vistos(c):
    """Os ids das checkboxes, pela MESMA regra do `vistoId` do JavaScript.

    Escrita aqui à mão de propósito: se o JavaScript mudar a regra e o Python
    não, a barra passa a contar zero — e é isso que o caso do node apanha, ao
    semear estes ids e ler o "N de M" que a barra desenhou.
    """
    out = []
    for b in c["montar"]["blocos"]:
        for m in b["movs"]:
            out.append((f'mt|{c["slot"]}|{m["copy_id"]}|{m["nm"]}|{m["board"]}',
                        m["q"]))
    for b in c["montar"]["basicas"]:
        for m in b["tirar"]:
            out.append((f'bs|{c["slot"]}|{m["copy_id"]}|{b["nm"]}', m["q"]))
    return out


def alocacao(con, slot="a"):
    return {r["copy_id"]: r["quantity"] for r in con.execute(
        "SELECT copy_id, quantity FROM copy_allocation WHERE slot = ?", (slot,))}


def estado(slot="a"):
    return caixas.estado_de(caixas.caixa_do_cfg(webapp.ler_config(), slot))


# ---------------------------------------------------------------------------
def caso_a_barra_conta_o_que_a_grelha_desenhou():
    """O «N de M» tem de ser o mesmo número de cópias que as checkboxes valem.

    Duas contas: o `marcar_q` do Python (que é o "M" e o que o cabeçalho da
    caixa usa no *"N de M na caixa"*) e a soma dos itens que a grelha desenha.
    Se divergirem, a barra fica a dizer uma coisa e a página outra — sem erro."""
    repor()
    con = montavel()
    c, _rep, _d = caixa(con)
    M = c["montar"]
    itens = ids_dos_vistos(c)
    # 4 checkboxes (3 cartas + 1 lote de 3 Island) que valem 6 cópias.
    assert len(itens) == 4, itens
    assert sum(q for _i, q in itens) == 6, itens
    assert M["marcar_q"] == 6, M["marcar_q"]
    assert M["dentro"] == 0, "ainda não está nada lá dentro"
    # E as três pilhas estão separadas: main, sideboard e básicas.
    assert [b["board"] for b in M["blocos"]] == ["main", "side"], M["blocos"]
    assert [b["nm"] for b in M["basicas"]] == ["Island"], M["basicas"]
    print("a barra conta 6 copias em 4 marcas: main, sideboard e as basicas")


def caso_registo_parcial_nao_diz_montada():
    """*"Registar as N marcadas"*: grava só essas, e a caixa **sobe a
    permanente** — não a montada. Dizer "montada" com metade das cartas na
    gaveta era o vault a mentir sobre a estante, que é o erro que este fluxo
    todo veio evitar."""
    repor()
    con = montavel()
    c, _rep, _d = caixa(con)
    assert estado() == "candidata", estado()
    alvo = next(m for b in c["montar"]["blocos"] for m in b["movs"]
                if m["nm"] == "Wrath of God")

    cfg = webapp.ler_config()
    r = webapp.registar_parcial(con, cfg, "a", [alvo["copy_id"]])
    webapp.escrever_config(cfg, CAMINHO)
    assert r["completa"] is False and r["falta"] == 5, r
    assert r["copias"] == 1 and r["estado"] == "permanente", r
    assert alocacao(con) == {alvo["copy_id"]: 1}, alocacao(con)
    assert estado() == "permanente", estado()

    # E a caixa passa a dizer "1 de 6 na caixa": o painel já só manda tirar 5.
    c, _rep, _d = caixa(con)
    assert c["montar"]["dentro"] == 1 and c["montar"]["marcar_q"] == 5, c["montar"]
    assert c["montado"] is False
    assert sum(q for _i, q in ids_dos_vistos(c)) == 5, "a marcada saiu da grelha"
    repor()
    print("registo parcial: 1 copia gravada, a caixa sobe a permanente (1 de 6)")


def caso_marcar_tudo_passa_a_montada():
    """Marcar a última cópia é dizer que o deck está montado: a caixa passa a
    `montada` e a `copy_allocation` fica com as cópias todas — as básicas
    registadas incluídas."""
    repor()
    con = montavel()
    c, _rep, _d = caixa(con)
    todas = [m["copy_id"] for b in c["montar"]["blocos"] for m in b["movs"]]
    todas += [m["copy_id"] for b in c["montar"]["basicas"] for m in b["tirar"]]

    cfg = webapp.ler_config()
    r = webapp.registar_parcial(con, cfg, "a", todas)
    webapp.escrever_config(cfg, CAMINHO)
    assert r["completa"] is True and r["falta"] == 0, r
    assert r["copias"] == 6 and r["estado"] == "montada", r
    assert sum(alocacao(con).values()) == 6, alocacao(con)
    assert estado() == "montada", estado()

    # E o painel deixa de mandar tirar seja o que for.
    c, _rep, _d = caixa(con)
    assert c["montado"] is True
    assert c["montar"]["marcar_q"] == 0 and c["montar"]["dentro"] == 6, c["montar"]
    repor()
    print("marcar tudo: 6 copias gravadas e a caixa passa a montada")


def caso_anular_repoe_a_alocacao_e_o_estado():
    """O *anular* do aviso de 6 segundos: repõe a `copy_allocation` e o `estado`
    exactamente como estavam. Não é um `desmontar` (esse apaga o que ele
    confirmou à mão, com backup e registo): é o inverso de uma escrita que
    aconteceu há segundos."""
    repor()
    con = montavel()
    c, _rep, _d = caixa(con)
    primeira = next(m for b in c["montar"]["blocos"] for m in b["movs"]
                    if m["nm"] == "Wrath of God")["copy_id"]

    # Um primeiro registo, que é o estado a que o anular tem de voltar.
    cfg = webapp.ler_config()
    webapp.registar_parcial(con, cfg, "a", [primeira])
    webapp.escrever_config(cfg, CAMINHO)
    antes = alocacao(con)
    assert antes == {primeira: 1} and estado() == "permanente"

    # O segundo: tudo. E anula-se.
    c, _rep, _d = caixa(con)
    todas = [primeira] + [m["copy_id"] for b in c["montar"]["blocos"]
                          for m in b["movs"]]
    todas += [m["copy_id"] for b in c["montar"]["basicas"] for m in b["tirar"]]
    cfg = webapp.ler_config()
    webapp.registar_parcial(con, cfg, "a", todas)
    webapp.escrever_config(cfg, CAMINHO)
    assert estado() == "montada" and sum(alocacao(con).values()) == 6

    cfg = webapp.ler_config()
    msg = webapp.anular_registo(con, cfg, "a")
    webapp.escrever_config(cfg, CAMINHO)
    assert "anulado" in msg, msg
    assert alocacao(con) == antes, ("volta ao registo anterior, não ao vazio",
                                    alocacao(con))
    assert estado() == "permanente", estado()

    # Anular duas vezes não desfaz o registo de antes: há UMA fotografia por
    # caixa, e ela é do último gesto. Sem isto, dois toques no telemóvel
    # esvaziavam uma caixa que ele nunca mandou esvaziar.
    cfg = webapp.ler_config()
    assert webapp.anular_registo(con, cfg, "a") == ""
    assert alocacao(con) == antes, alocacao(con)
    repor()
    print("anular: repoe a alocacao e o estado do gesto anterior, e so uma vez")


def caso_o_que_e_de_outra_caixa_nao_impede_de_fechar():
    """Uma cópia que a alocação deu a OUTRA caixa aparece no painel («podes
    tirá-la já») mas **não conta para o «N de M»**: esperá-la era impedir esta
    caixa de ficar completa por causa de uma carta que é de outra."""
    repor()
    con = base()
    deck(con, "A", [("Sol Ring", 1, "main")])
    deck(con, "B", [("Sol Ring", 1, "main"), ("Wrath of God", 1, "main")])
    add(con, "Sol Ring", 1)
    add(con, "Wrath of God", 1)

    b, _rep, _d = caixa(con, "b")
    # A caixa A (prioridade 1) levou o Sol Ring; a B vê-o como "destinado a A".
    assert b["montar"]["copias_de_outra"] == 1, b["montar"]
    assert b["montar"]["marcar_q"] == 1, ("só o Wrath of God", b["montar"])
    assert sum(q for _i, q in ids_dos_vistos(b)) == 1

    # Marcar o Wrath of God fecha a caixa B, mesmo com o Sol Ring por tirar.
    alvo = b["montar"]["blocos"][0]["movs"][0]["copy_id"]
    cfg = webapp.ler_config()
    r = webapp.registar_parcial(con, cfg, "b", [alvo])
    webapp.escrever_config(cfg, CAMINHO)
    assert r["completa"] is True and r["estado"] == "montada", r
    repor()
    print("destinadas a outra caixa: aparecem, mas nao trancam o «N de M»")


def caso_o_config_manda_no_auto_registo():
    """`colecao_config.json → montar`. Por omissão o registo é automático — mas
    é uma escrita na base, e uma escrita automática tem de ser uma decisão
    escrita em algum lado, não um efeito secundário do código."""
    repor()
    con = montavel()
    assert loadout.montar_auto_registar() is True
    assert loadout.montar_anular_segundos() == loadout.ANULAR_SEGUNDOS == 6
    _c, _rep, d = caixa(con)
    assert d["auto_registar"] is True and d["anular_segundos"] == 6, d["anular_segundos"]

    repor({"montar": {"auto_registar": False, "anular_segundos": 12}})
    assert loadout.montar_auto_registar() is False
    assert loadout.montar_anular_segundos() == 12
    _c, _rep, d = caixa(con)
    assert d["auto_registar"] is False and d["anular_segundos"] == 12, d
    repor()
    print("auto_registar e anular_segundos saem do config (6 s por omissao)")


# ---------------------------------------------------------------------------
# O que o BROWSER desenha
# ---------------------------------------------------------------------------
def _abas(con, editable, feitos=None):
    """`{aba: html}` + `{"barra:<aba>": html}`, corrido no harness de node.

    `None` quando não há `node`: a bateria tem de correr num PC sem ele."""
    if not shutil.which("node"):
        return None
    pasta = Path(tempfile.mkdtemp())
    pagina = pasta / "deckboxes.html"
    pagina.write_text(deckboxes.html_page(con, editable=editable),
                      encoding="utf-8")
    dump = pasta / "abas.json"
    argv = ["node", str(Path(__file__).with_name("render_deckboxes.js")),
            str(pagina), str(dump)]
    if feitos is not None:
        seed = pasta / "feitos.json"
        seed.write_text(json.dumps(feitos), encoding="utf-8")
        argv.append(str(seed))
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_a_barra_desenha_o_progresso_e_o_botao():
    """O que ele vê no telemóvel: *"Montar Caixa A: N de 6 cópias marcadas"*, a
    barra de progresso e o botão de registar — fora da vista, fixos no fundo do
    ecrã, para não ficarem no fim de 58 linhas."""
    repor()
    con = montavel()
    c, _rep, _d = caixa(con)
    itens = ids_dos_vistos(c)
    if not shutil.which("node"):
        print("barra de montagem: sem `node`, saltado")
        return

    # Nada marcado: a barra existe na mesma (é onde estão o "marcar tudo" e o
    # botão), e o registo está desactivado — não há nada para registar.
    abas = _abas(con, True)
    barra = abas["barra:a"]
    assert "Montar Caixa A" in barra, barra
    assert "0 de 6 cópias marcadas" in barra, barra
    assert 'data-estado="vazio"' in barra and "disabled" in barra, barra
    assert 'id="b-tudo"' in barra and 'id="b-limpar"' in barra, barra

    # Uma marca — e a que se marca é o LOTE DE 3 Island: a barra tem de dizer
    # "3 de 6" e não "1 de 6". Uma contagem por linhas dava o número errado.
    ilha = next(i for i, _q in itens if i.startswith("bs|"))
    barra = _abas(con, True, {ilha: 1})["barra:a"]
    assert "3 de 6 cópias marcadas" in barra, barra
    assert "Registar as 3 marcadas" in barra, barra
    assert 'data-estado="meio"' in barra, barra

    # Tudo marcado: a barra fica cheia e o botão passa a ser o gesto de hoje.
    barra = _abas(con, True, {i: 1 for i, _q in itens})["barra:a"]
    assert "6 de 6 cópias marcadas · tudo marcado" in barra, barra
    assert "✅ Registar como montada" in barra, barra
    assert 'data-estado="cheia"' in barra, barra
    print("barra: 0 de 6 -> 3 de 6 (o lote de Island) -> 6 de 6 e o botao verde")


def caso_a_barra_nao_existe_no_site_publicado():
    """No GitHub Pages o endpoint de escrita não existe. Uma barra que conta
    cópias e não regista nada é pior do que não haver barra — é a mesma razão
    por que os botões só se desenham no modo edição."""
    repor()
    con = montavel()
    abas = _abas(con, False)
    if abas is None:
        print("barra no site publicado: sem `node`, saltado")
        return
    assert abas["barra:a"] == "", abas["barra:a"][:200]
    assert abas["barra:plano"] == "", abas["barra:plano"]
    # E a aba continua a desenhar-se: o dump vem do `#vista`, não do último
    # innerHTML — a barra a seguir à vista não pode roubar-lhe o lugar.
    assert "Caixa A" in abas["a"], abas["a"][:200]
    print("barra: nao existe no site publicado, e a vista continua inteira")


def caso_o_pedido_de_registo_passa_pelo_handler():
    """O caminho todo, pelo mesmo handler HTTP que o telemóvel usa: `registar`
    grava, `anular` desfaz — e sem token, da rede, é 403 nos dois."""
    repor()
    con = montavel()
    c, _rep, _d = caixa(con)
    alvo = c["montar"]["blocos"][0]["movs"][0]["copy_id"]
    # O handler abre a SUA ligação: aponta-se a base do módulo para a do teste,
    # senão isto corria na base do André. Nos atributos do módulo e não no
    # ambiente — o `db` lê as variáveis no import, e a esta altura já as leu.
    # (o `webapp.ROOT`, para onde as páginas se regeneram, está no topo.)
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])

    corpo = json.dumps({"act": "registar", "slot": "a", "copias": [alvo]})
    p = Pedido("/api/caixa", corpo)
    p.do_POST()
    assert p.codigo == 403, (p.codigo, p.corpo)
    assert not alocacao(con), "um pedido sem token nao pode ter gravado nada"

    p = Pedido("/api/caixa", corpo, ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo[:300])
    assert "faltam 5 por tirar" in p.corpo, p.corpo
    assert estado() == "permanente", estado()

    p = Pedido("/api/caixa", json.dumps({"act": "anular", "slot": "a"}),
               ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo[:300])
    assert estado() == "candidata", estado()
    repor()
    print("handler: registar grava, anular desfaz, e sem token e 403")


class Pedido(webapp.Handler):
    """Um pedido de mentira: o mesmo handler, sem rede por baixo."""

    def __init__(self, path, corpo=None, token=None, ip="192.168.1.99"):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO((corpo or "").encode("utf-8"))
        self.headers = {"Content-Length": str(len(corpo or "")) or "0"}
        if token:
            self.headers[webapp.CABECALHO_TOKEN] = token
        self.codigo, self.corpo = None, ""

    def send_response(self, code, *_a):
        self.codigo = code

    def send_header(self, *_a):
        pass

    def end_headers(self):
        pass

    @property
    def wfile(self):
        self_ = self

        class Escritor:
            def write(self, b):
                self_.corpo = b.decode("utf-8", "replace")
        return Escritor()


def run():
    for fn in (caso_a_barra_conta_o_que_a_grelha_desenhou,
               caso_registo_parcial_nao_diz_montada,
               caso_marcar_tudo_passa_a_montada,
               caso_anular_repoe_a_alocacao_e_o_estado,
               caso_o_que_e_de_outra_caixa_nao_impede_de_fechar,
               caso_o_config_manda_no_auto_registo,
               caso_a_barra_desenha_o_progresso_e_o_botao,
               caso_a_barra_nao_existe_no_site_publicado,
               caso_o_pedido_de_registo_passa_pelo_handler):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
