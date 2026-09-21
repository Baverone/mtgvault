"""PIONEER: SÓ O GREASEFANG E O JESKAI CONTROL (André, 2026-09-21, à letra):
*"Pioneer apenas Greasefang e jeskai control
https://mtgtop8.com/event?e=90797&d=889461&f=PI"*.

O que aqui se tranca:

  1. **a segunda caixa de Pioneer existe no config a sério** (`pioneer-jeskai`,
     lista padrão FIXA com a origem = o URL dele, 60 main + 15 side, o side
     separado) e vem a seguir ao Greasefang na ordem da alocação; a lista
     padrão não é pisada pelo daily (a caixa lê `listas_escolhidas`, não a
     tabela `decks`); as regras são as do grupo SPML (EN foil, dedicada);
  2. **o Pioneer deixou de ter candidatos** — `colecao_config.json →
     formatos_decididos` tira-o do top-N (`metagame.formatos_top()`), a secção
     do Metagame passa a mostrar as duas caixas (modo `caixas`) sem «vou
     montar este», a aba da caixa na Deckboxes fica sem o bloco «o que estás
     mais perto de concluir», e o endpoint `/api/escolher` recusa uma escolha
     para uma caixa desse formato. **O Standard e o Legacy continuam com o
     top-N** (a decisão de 2026-09-07 fica para eles);
  3. **a reserva da caixa Jeskai fica fora da venda** — as nonfoil EN que ele
     já tem das cartas da lista (Thor, Jeskai Revelation, Tablet, Great Hall…)
     são substitutos para a caixa (compra-se foil) e nunca vão à venda.

Tudo contra cópias (`MTGVAULT_HOME` + `MTGVAULT_DB` fixados); sem rede.
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
LISTA = ("4 Jeskai Revelation\n2 Thor, God of Thunder\n4 Steam Vents\n"
         "1 Pop Quiz\n// Sideboard\n1 Negate\n1 Thor, God of Thunder\n")
ORIGEM = "https://mtgtop8.com/event?e=90797&d=889461&f=PI"
CFG = {
    "regras_colecao": {}, "decks_vigiados": [],
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "metagame_top_n": 3,
    "formatos_decididos": ["pioneer"],
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "dedicado": True, "lingua": "en", "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "standard", "nome": "Standard", "formato": "standard", "fonte": "deck",
         "ref": None, "balde": "SPML", "estado": "candidata", "prioridade": 11, "notas": ""},
        {"slot": "pioneer", "nome": "Pioneer — Greasefang", "formato": "pioneer",
         "fonte": "deck", "ref": "Greasefang", "balde": "SPML", "estado": "permanente",
         "prioridade": 13, "notas": ""},
        {"slot": "pioneer-jeskai", "nome": "Jeskai Control", "formato": "pioneer",
         "fonte": "deck", "ref": None, "balde": "SPML", "estado": "permanente",
         "prioridade": 14, "notas": ""},
        {"slot": "legacy", "nome": "Legacy", "formato": "legacy", "fonte": "deck",
         "ref": None, "balde": "SPML", "estado": "candidata", "prioridade": 15, "notas": ""},
    ],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import configio, db, loadout, padrao, sources  # noqa: E402

import deckboxes  # noqa: E402
import metagame  # noqa: E402
import webapp  # noqa: E402

# O `webapp` regenera as páginas no `webapp.ROOT` (a raiz do repositório):
# apontado aqui para um teste nunca reescrever o `deckboxes.html` a sério.
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

# (nome, edição, data)
CATALOGO = [
    ("Jeskai Revelation", "tdm", "2025-04-11"),
    ("Thor, God of Thunder", "msh", "2026-01-23"),
    ("Steam Vents", "exp", "2015-10-02"),
    ("Pop Quiz", "tla", "2025-11-21"),
    ("Negate", "tla", "2025-11-21"),
    ("Greasefang, Okiba Boss", "neo", "2022-02-18"),
    ("Parhelion II", "war", "2019-05-03"),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Instant',1,'U',?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"pioneer": "legal", "modern": "legal", "legacy": "legal"})))
        for fin in ("nonfoil", "foil"):
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, "
                        "date, trend) VALUES (?, 'cardmarket', ?, '2026-09-21', ?)",
                        (f"id-{i}", fin, 2.0 if fin == "nonfoil" else 5.0))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", sub="Colecção"):
    i = [c[0] for c in CATALOGO].index(nm)
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, 'player')",
                (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?", (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                   sub_collection_id) VALUES (?,?,?,'en','player',?)""",
                (f"id-{i}", q, finish, sub_id))
    con.commit()


def deck(con, nome, fmt, cartas):
    con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    con.execute("DELETE FROM deck_cards WHERE deck_id = ?", (did,))
    for nm, q in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()


def cfg_ler():
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


def cfg_escrever(cfg):
    configio.escrever(cfg, CFG_PATH)
    sources._CFG_CACHE.clear()


def cfg_com_jeskai():
    cfg = json.loads(json.dumps(CFG))
    padrao.fixar(cfg, "pioneer-jeskai", padrao.parse_lista(LISTA), origem=ORIGEM,
                 quando="2026-09-21")
    return cfg


def caixa(rep, slot):
    return next(s for s in rep["slots"] if s["slot"] == slot)


# ---------------------------------------------------------------------------
def caso_a_segunda_caixa_de_pioneer_tem_a_lista_fixa_e_o_side():
    """A caixa `pioneer-jeskai` lê a lista padrão (main + side, o side
    separado), vem a seguir ao Greasefang, é EN foil e dedicada — e o daily não
    lhe muda uma carta, porque não lê a tabela `decks`."""
    cfg = cfg_com_jeskai()
    s = next(c for c in cfg["caixas"] if c["slot"] == "pioneer-jeskai")
    assert s["fonte"] == "escolhido" and s["ref"] == "pioneer-jeskai"
    assert s["_antes"] == {"fonte": "deck", "ref": None, "nome": "Jeskai Control",
                           "estado": "permanente"}, s["_antes"]
    rec = cfg["listas_escolhidas"]["pioneer-jeskai"]
    assert rec["padrao"] is True and rec["origem"] == ORIGEM and rec["escolhido_em"] == "2026-09-21"
    cfg_escrever(cfg)

    con = base()
    deck(con, "Greasefang", "pioneer", [("Greasefang, Okiba Boss", 4), ("Parhelion II", 2)])
    add(con, "Jeskai Revelation", 4, finish="foil")
    add(con, "Steam Vents", 4, finish="foil")
    add(con, "Thor, God of Thunder", 3, finish="nonfoil")   # nonfoil: não serve
    rep = loadout.report(con)
    j = caixa(rep, "pioneer-jeskai")
    assert j["padrao"] == {"desde": "2026-09-21", "origem": ORIGEM}, j["padrao"]
    assert j["nota"].startswith("lista padrão fixada em 2026-09-21 · https://mtgtop8.com"), j["nota"]
    assert j["cards"] == [("main", "Jeskai Revelation", 4), ("main", "Pop Quiz", 1),
                          ("main", "Steam Vents", 4), ("main", "Thor, God of Thunder", 2),
                          ("side", "Negate", 1), ("side", "Thor, God of Thunder", 1)], j["cards"]
    assert j["precisa"] == 13 and j["tenho"] == 8 and j["comprar"] == 5, (j["precisa"], j["tenho"], j["comprar"])
    assert j["pct"] == round(100 * 8 / 13)
    # O side vem separado: o Thor joga nos dois e são DUAS linhas.
    boards = sorted((m["board"], m["nm"]) for m in j["have"] + j["missing"])
    assert ("side", "Thor, God of Thunder") in boards and ("main", "Thor, God of Thunder") in boards
    assert loadout.totais_por_board(j) == {"main": 11, "side": 2}, loadout.totais_por_board(j)
    # A nonfoil é substituto (só foil, e existe em foil): compra-se foil.
    thor = next(m for m in j["missing"] if m["nm"] == "Thor, God of Thunder" and m["board"] == "main")
    assert thor["got"] == 0 and thor["comprar"] == 2 and thor["alt"], thor
    assert list(thor["alt"])[0].startswith("não é foil"), thor["alt"]
    assert "foil" in loadout.requisito_material(j).lower()
    assert j["dedicado"] is True and j["permanente"] is True
    # A ordem: Greasefang primeiro (é a mais antiga), Jeskai a seguir.
    ordem = [x["slot"] for x in rep["slots"]]
    assert ordem.index("pioneer") < ordem.index("pioneer-jeskai"), ordem
    assert caixa(rep, "pioneer")["cards"], "o Greasefang fica como está"
    # O daily pisa a tabela `decks` (e até cria um deck com o nome da caixa):
    # a caixa não mexe.
    deck(con, "Jeskai Control", "pioneer", [("Negate", 4)])
    deck(con, "pioneer-jeskai", "pioneer", [("Negate", 4)])
    rep = loadout.report(con)
    assert caixa(rep, "pioneer-jeskai")["cards"] == j["cards"]
    print("a segunda caixa de Pioneer tem a lista fixa, o side separado, e o daily nao a pisa")


def caso_o_config_a_serio_tem_a_caixa_e_o_pioneer_decidido():
    """O que o André pediu está ESCRITO no `colecao_config.json` do repositório:
    a caixa `pioneer-jeskai` com a lista do McWinSauce (60 main + 15 side, a
    origem é o URL dele), a seguir ao Greasefang, a reserva com as nonfoil, e o
    `pioneer` em `formatos_decididos`. Um config que perdesse isto num merge
    não dava erro: dava a página de ontem."""
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    slots = [c["slot"] for c in cfg["caixas"]]
    assert slots.index("pioneer") + 1 == slots.index("pioneer-jeskai"), slots
    s = next(c for c in cfg["caixas"] if c["slot"] == "pioneer-jeskai")
    assert s["formato"] == "pioneer" and s["fonte"] == "escolhido" and s["ref"] == "pioneer-jeskai"
    assert s["estado"] == "permanente" and s["nome"] == "Jeskai Control"
    g = next(c for c in cfg["caixas"] if c["slot"] == "pioneer")
    assert s["prioridade"] > g["prioridade"], "Greasefang primeiro"
    rec = cfg["listas_escolhidas"]["pioneer-jeskai"]
    assert rec["padrao"] is True and rec["escolhido_em"] == "2026-09-21"
    assert "mtgtop8.com/event?e=90797&d=889461&f=PI" in rec["origem"], rec["origem"]
    main = sum(q for b, _n, q in rec["cards"] if b == "main")
    side = sum(q for b, _n, q in rec["cards"] if b == "side")
    assert (main, side) == (60, 15), (main, side)
    assert len(rec["cards"]) == 37, len(rec["cards"])
    assert ["main", "Thor, God of Thunder", 2] in rec["cards"]
    assert ["side", "Negate", 1] in rec["cards"]
    for nm in ("Thor, God of Thunder", "Jeskai Revelation", "Tablet of Discovery",
               "Great Hall of the Biblioplex", "Combustion Technique", "It'll Quench Ya!"):
        assert nm in s["reserva"], (nm, s["reserva"])
    assert cfg["formatos_decididos"] == ["pioneer"], cfg.get("formatos_decididos")
    print("o config a serio tem a caixa Jeskai (60+15, origem = o URL dele) e o pioneer decidido")


class Pedido(webapp.Handler):
    """Um pedido de mentira: o mesmo handler, sem rede por baixo."""

    def __init__(self, path, corpo=None, ip="127.0.0.1"):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO((corpo or "").encode("utf-8"))
        self.headers = {"Content-Length": str(len(corpo or ""))}
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


def _post(caminho, dados, ip="127.0.0.1"):
    p = Pedido(caminho, json.dumps(dados), ip=ip)
    p.do_POST()
    return p.codigo, (json.loads(p.corpo) if p.corpo.startswith("{") else p.corpo)


def _candidato_falso(fmt, slot, nome):
    linhas = [{"nm": "Negate", "need": 4, "got": 1, "noutra_q": 0, "comprar": 3,
               "cost": 15.0, "unit": 5.0, "basica": False, "board": "main",
               "noutra": {}, "foil_existe": True}]
    return {"nome": nome, "subtitulo": "Negate / Pop Quiz", "linhas": linhas,
            "marca": "FOIL", "archetype_id": 77, "n_lists": 12, "formato": fmt,
            "slot": slot, "escolhido": False, "escolhido_em": None,
            "sub": "12 listas que contam · Negate / Pop Quiz",
            "badges": [("fo", "✨ só foil"), ("", "🧩 lista de consenso")]}


def caso_o_pioneer_nao_tem_candidatos_e_o_standard_tem():
    """`formatos_decididos: ["pioneer"]`: o top-N sai do Pioneer nos três sítios
    — o Metagame (secção `caixas`, com as duas caixas e sem «vou montar
    este»), a Deckboxes (sem o bloco dos candidatos nas duas abas) e o
    endpoint `/api/escolher` (recusa). O Standard e o Legacy ficam como
    estavam. O cálculo dos candidatos é substituído por um falso: o que se
    testa é QUEM o pede, não o clustering."""
    cfg = cfg_com_jeskai()
    cfg_escrever(cfg)
    assert metagame.formatos_decididos() == ["pioneer"]
    assert metagame.formatos_top() == ["standard", "legacy"], metagame.formatos_top()
    assert dict((f, m) for f, _t, m in metagame.secoes())["pioneer"] == "caixas"
    assert [f for f, _t, m in metagame.SECOES if m == "top"] == ["standard", "pioneer", "legacy"], \
        "o SECOES fica como ele o deu em 2026-09-07 — o que muda é config"

    pedidos = []
    original = metagame.candidatos

    def falso(con, fmt, res, n=None):
        pedidos.append(fmt)
        slot = metagame.slot_do_formato(res["slots"], fmt)
        return [_candidato_falso(fmt, (slot or {}).get("slot"), f"Azorius Negate ({fmt})")]

    metagame.candidatos = falso
    try:
        con = base()
        deck(con, "Greasefang", "pioneer", [("Greasefang, Okiba Boss", 4)])
        add(con, "Negate", 1, finish="foil")
        rep = loadout.report(con)

        # A Deckboxes: candidatos só para o Standard e o Legacy.
        cand = deckboxes._candidatos(con, rep)
        assert set(cand) == {"standard", "legacy"}, cand.keys()
        assert sorted(pedidos) == ["legacy", "standard"], pedidos
        assert "pioneer" not in pedidos and "pioneer" not in cand

        # O Metagame: a secção do Pioneer traz as DUAS caixas e nenhum botão;
        # a do Standard traz o candidato e o botão (modo edição).
        html = metagame.html_page(con, editable=True)
        secs = {}
        for parte in html.split('<section id="f-')[1:]:
            secs[parte.split('"', 1)[0]] = parte
        pio = secs["pioneer"]
        assert "Pioneer — Greasefang" in pio and "Jeskai Control" in pio, pio[:600]
        assert 'data-act="escolher"' not in pio and "Azorius Negate" not in pio
        assert "decks que decidiste" in pio and "formatos_decididos" in pio, pio[:800]
        assert "lista padrão fixada em 2026-09-21" in pio, pio[:800]
        std = secs["standard"]
        assert 'data-act="escolher"' in std and "Azorius Negate (standard)" in std, std[:600]
        assert 'data-act="escolher"' in secs["legacy"]
        # O rodapé diz quem é top-N e quem mostra as caixas — sai da mesma lista.
        assert "<b>Standard e Legacy</b> são as caixas por escolher" in html
        assert "Em <b>Pioneer e Modern</b> mostram-se os decks já escolhidos" in html, \
            "o rodapé tem de listar o Pioneer entre os formatos das caixas"
        # E no site publicado (sem botões) a secção do Pioneer é a mesma.
        pub = metagame.html_page(con, editable=False)
        assert "Jeskai Control" in pub and 'data-act="escolher"' not in pub

        # A página das Deckboxes: o bloco dos candidatos só na caixa do Standard.
        d = deckboxes.payload(con, rep, editable=True)
        assert set(d["candidatos"]) == {"standard", "legacy"}, d["candidatos"].keys()
        pagina = _TMP / "dx-pioneer.html"
        pagina.write_text(deckboxes.html_page(con, editable=True, rep=rep), encoding="utf-8")
        if shutil.which("node"):
            dump = _TMP / "abas-pioneer.json"
            p = subprocess.run(["node", str(RAIZ / "tests" / "render_deckboxes.js"),
                                str(pagina), str(dump)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
            assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
            abas = json.loads(dump.read_text(encoding="utf-8"))
            assert "cand-blk" in abas["standard"] and "vou montar este" in abas["standard"]
            for slot in ("pioneer", "pioneer-jeskai"):
                assert "cand-blk" not in abas[slot], slot
                assert "vou montar este" not in abas[slot], slot
            assert "Lista padrão desde 2026-09-21" in abas["pioneer-jeskai"]
        else:
            print("  (sem node: o render não foi verificado)")

        # O endpoint recusa escolher um top-N para uma caixa do Pioneer — uma
        # página aberta ontem no telemóvel ainda tem o botão.
        dbs = con.execute("PRAGMA database_list").fetchall()
        db.DEFAULT_DB = Path(next(r["file"] for r in dbs if r["name"] == "main"))
        db.DEFAULT_CATALOG = Path(next(r["file"] for r in dbs if r["name"] == "catalog"))
        webapp.CONFIG = CFG_PATH
        antes = cfg_ler()
        cod, j = _post("/api/escolher", {"act": "escolher", "slot": "pioneer", "aid": 77})
        assert cod == 200 and "decidido" in j.get("erro", ""), (cod, j)
        cod, j = _post("/api/escolher", {"act": "escolher", "slot": "pioneer-jeskai", "aid": 77})
        assert "decidido" in j.get("erro", ""), (cod, j)
        assert cfg_ler() == antes, "não escreveu nada"
        cod, j = _post("/api/escolher", {"act": "escolher", "slot": "nao-existe", "aid": 77})
        assert "desconhecida" in j.get("erro", ""), (cod, j)
    finally:
        metagame.candidatos = original
    print("o Pioneer nao tem candidatos (Metagame, Deckboxes, endpoint); Standard/Legacy tem")


def caso_sem_a_chave_o_pioneer_volta_a_ter_candidatos():
    """Tirar o formato de `formatos_decididos` devolve-lhe o top-N — o código
    não se apagou, é config."""
    cfg = cfg_com_jeskai()
    cfg.pop("formatos_decididos")
    cfg_escrever(cfg)
    assert metagame.formatos_decididos() == []
    assert metagame.formatos_top() == ["standard", "pioneer", "legacy"]
    assert dict((f, m) for f, _t, m in metagame.secoes())["pioneer"] == "top"
    print("sem a chave o Pioneer volta a ter candidatos")


def caso_a_reserva_da_jeskai_fica_fora_da_venda():
    """As nonfoil EN que ele já tem das cartas da lista (3 Thor MSH, 4 Jeskai
    Revelation TDM…) não servem a caixa — é foil. HOJE já não iam à venda:
    são substitutos (`guardar`, *"serve Jeskai Control"*). A reserva é para o
    dia em que ele TIVER as foil — aí a nonfoil deixava de ser substituto,
    passava a excedente do playset e ia à venda; com a reserva fica em
    `guardar` com o motivo *"reserva da caixa Jeskai Control"*."""
    cfg = cfg_com_jeskai()
    s = next(c for c in cfg["caixas"] if c["slot"] == "pioneer-jeskai")
    s["reserva"] = ["Thor, God of Thunder", "Jeskai Revelation"]
    cfg_escrever(cfg)
    con = base()
    deck(con, "Greasefang", "pioneer", [("Greasefang, Okiba Boss", 4)])
    add(con, "Thor, God of Thunder", 3, finish="nonfoil")     # ainda sem foil: substituto
    add(con, "Jeskai Revelation", 4, finish="foil")           # já tem as foil...
    add(con, "Jeskai Revelation", 4, finish="nonfoil")        # ...e as nonfoil sobram
    add(con, "Pop Quiz", 1, finish="foil")
    add(con, "Pop Quiz", 4, finish="nonfoil")                 # sem reserva: sobram, vendem-se
    rep = loadout.report(con)
    j = caixa(rep, "pioneer-jeskai")
    assert j["tenho"] == 5 and j["comprar"] == 8, (j["tenho"], j["comprar"])
    razao = f"{loadout.RAZAO_RESERVA} Jeskai Control"
    g = {(r["nm"], r["reason"]): r for r in rep["guardar"]}
    assert ("Jeskai Revelation", razao) in g and g[("Jeskai Revelation", razao)]["q"] == 4, g.keys()
    assert g[("Jeskai Revelation", razao)]["porque_venderia"] == "excedente (mais de 4)"
    # Os 3 Thor cabem no playset (a lista pede 3): nunca iam à venda, e o
    # `guardar` não os inventa — é o bloco da caixa que os mostra.
    assert not any(r["nm"] == "Thor, God of Thunder" for r in rep["guardar"])
    assert not any(r["nm"] in ("Thor, God of Thunder", "Jeskai Revelation") for r in rep["venda"]), \
        [r["nm"] for r in rep["venda"]]
    # O playset conta a colecção inteira: 1 foil + 4 nonfoil = 5, sobra 1.
    vend = {r["nm"]: r["q"] for r in rep["venda"]}
    assert vend == {"Pop Quiz": 1}, vend
    bloco = {r["nm"]: r for r in j["reserva_linhas"]}
    assert bloco["Thor, God of Thunder"]["q"] == 3 and bloco["Thor, God of Thunder"]["serve"] is False
    assert bloco["Thor, God of Thunder"]["lotes"][0]["porque"].startswith("não é foil")
    assert bloco["Jeskai Revelation"]["q"] == 8
    print("a reserva da Jeskai fica fora da venda (hoje substituto; com as foil, reserva)")


def run():
    for fn in (caso_a_segunda_caixa_de_pioneer_tem_a_lista_fixa_e_o_side,
               caso_o_config_a_serio_tem_a_caixa_e_o_pioneer_decidido,
               caso_o_pioneer_nao_tem_candidatos_e_o_standard_tem,
               caso_sem_a_chave_o_pioneer_volta_a_ter_candidatos,
               caso_a_reserva_da_jeskai_fica_fora_da_venda):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
