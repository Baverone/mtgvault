"""«JÁ A TENHO, ESTÁ NO DECK»: dar check numa carta da lista de compras.

André, 2026-09-08, à letra (com a imagem do painel «Montar Blue Farm» aberto no
passo 2): *"Arranja forma de eu poder dar check nas cartas das faltas, para dizer
que já as tenho e já coloquei no deck."*

O que aqui se tranca:

  1. **o check cria a cópia E mete-a na caixa** — uma sem a outra deixava o vault
     a discordar dele (a cópia sem caixa manda-o à gaveta onde ela não está; a
     caixa sem cópia volta a pedir a carta amanhã);
  2. **a regra de material da caixa manda** — o Premodern fica PT e nunca
     adivinha uma impressão posterior ao Scourge; uma caixa de foil fica EN foil.
     Adivinhar uma edição que a própria caixa recusa era criar a falta outra vez
     com mais passos;
  3. **a linha muda de passo**: sai de «comprar» (com o custo) e aparece no
     passo 1 como *na caixa ✓*, com a edição por confirmar;
  4. **anular apaga a cópia que acabou de nascer** — e só essa: uma cópia normal
     da colecção não se apaga por um `copy_id` trocado;
  5. **a foto que chega depois ACERTA a edição** em vez de criar uma segunda
     cópia (era o dobro das cartas na base por ele ter sido diligente);
  6. o pedido passa pelo mesmo handler HTTP, e sem token é 403;
  7. o check **não existe no site publicado** (lá não há endpoint que grave).

Não abre socket nenhum nem toca na rede.
"""
import csv as _csv
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
    # As duas regras que este ficheiro mede: o Premodern (PT, só edições da era)
    # e um grupo de foil inglês. É o que decide o material da cópia que o check
    # cria, e a ordem desta lista é a ordem da alocação.
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "edicoes": "premodern", "dedicado": False},
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "pm", "nome": "UW Replenish", "formato": "premodern",
         "fonte": "deck", "ref": "PM", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1},
        {"slot": "lg", "nome": "Legacy — Doomsday", "formato": "legacy",
         "fonte": "deck", "ref": "LG", "balde": "Colecção",
         "estado": "permanente", "prioridade": 2},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)

from mtgvault import collection, db, loadout, scryfall, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# O `webapp._caixa` regenera as páginas e escreve-as no `webapp.ROOT` — que é a
# raiz do repositório. Apontado aqui, logo no import (ver `test_montar_barra`).
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

# (nome, edição, data, acabamentos). Três impressões de Swords to Plowshares, de
# propósito: duas da era Premodern e uma de 2022. É a de 2022 que um palpite sem
# regras escolheria — e é exactamente a que a caixa de Premodern recusa.
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"]),
    ("Swords to Plowshares", "ody", "2001-09-24", ["nonfoil", "foil"]),
    ("Swords to Plowshares", "2x2", "2022-07-08", ["nonfoil", "foil"]),
    ("Force of Will", "all", "1996-06-10", ["nonfoil"]),
    ("Force of Will", "2xm", "2020-08-07", ["nonfoil", "foil"]),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fin) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Instant',1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i),
             json.dumps(fin), rel,
             json.dumps({"legacy": "legal", "premodern": "legal"})))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    return con


def deck(con, nome, fmt, cartas):
    con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
    did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
    for nm, q, board in cartas:
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,?)", (did, nm, q, board))
    con.commit()
    return did


def montavel():
    """Duas caixas sem uma única cópia na colecção: tudo é falta a comprar."""
    con = base()
    deck(con, "PM", "premodern", [("Swords to Plowshares", 2, "main")])
    deck(con, "LG", "legacy", [("Force of Will", 1, "main")])
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def caixa(con, slot="pm", editable=True):
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=editable)
    return next(c for c in d["caixas"] if c["slot"] == slot), rep, d


def copias(con):
    return [dict(r) for r in con.execute(
        """SELECT cp.id, cp.quantity, cp.finish, cp.language, cp.notes,
                  c.name, c.set_code
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            ORDER BY cp.id""")]


def alocacao(con, slot=None):
    q = "SELECT copy_id, slot, quantity FROM copy_allocation"
    args = ()
    if slot:
        q += " WHERE slot = ?"
        args = (slot,)
    return [dict(r) for r in con.execute(q, args)]


def log(caminho):
    if not Path(caminho).exists():
        return []
    with Path(caminho).open(encoding="utf-8", newline="") as fh:
        return list(_csv.DictReader(fh))


# ---------------------------------------------------------------------------
def caso_o_check_cria_a_copia_e_mete_a_na_caixa():
    """Um check grava as DUAS metades: a cópia (é uma carta que existe em casa e
    o vault não sabia) e o lugar dela (dentro daquela caixa, que foi o que ele
    disse). E fica registado no `registos-faltas.csv` — é um botão que CRIA
    cartas, e sem rasto ninguém sabe daqui a um mês donde ela veio."""
    repor()
    con = montavel()
    reg = _TMP / "faltas1.csv"
    c, rep, _d = caixa(con)
    assert [w["nm"] for w in c["wantlist"]] == ["Swords to Plowshares"], c["wantlist"]
    assert c["comprar"] == 2 and c["pct"] == 0, (c["comprar"], c["pct"])

    r = loadout.registar_falta(con, rep, "pm", "Swords to Plowshares",
                               board="main", quantidade=2, csv_path=reg)
    assert r["q"] == 2 and r["palpite"] is True, r

    cps = copias(con)
    assert len(cps) == 1, cps
    assert cps[0]["quantity"] == 2 and cps[0]["name"] == "Swords to Plowshares"
    assert "registada a partir das faltas" in cps[0]["notes"], cps[0]["notes"]
    assert collection.MARCA_POR_CONFIRMAR in cps[0]["notes"], cps[0]["notes"]
    assert alocacao(con) == [{"copy_id": cps[0]["id"], "slot": "pm",
                              "quantity": 2}], alocacao(con)

    linhas = log(reg)
    assert len(linhas) == 1, linhas
    assert linhas[0]["accao"] == "registada" and linhas[0]["caixa"] == "UW Replenish"
    assert linhas[0]["carta"] == "Swords to Plowshares"
    assert linhas[0]["quantidade"] == "2" and linhas[0]["palpite"] == "sim"
    assert linhas[0]["copy_id"] == str(cps[0]["id"]), linhas[0]
    print("check: cria a copia, mete-a na caixa e escreve a linha no registo")


def caso_a_regra_de_material_da_caixa_manda():
    """O Premodern é *"PT e só edições até ao Scourge"*, e o palpite tem de o
    respeitar: a impressão mais recente desta carta é de 2022 e é a que um
    `--adivinhar` sem regras escolheria — a caixa recusá-la-ia no dia seguinte,
    e a carta voltava à lista de compras sem ninguém perceber porquê."""
    repor()
    con = montavel()
    rep = loadout.report(con)
    loadout.registar_falta(con, rep, "pm", "Swords to Plowshares", quantidade=1,
                           csv_path=_TMP / "faltas2.csv")
    pm = copias(con)[0]
    assert pm["language"] == "pt", pm
    assert pm["finish"] == "nonfoil", pm
    assert pm["set_code"] == "ody", ("a mais recente ATÉ ao Scourge", pm)

    # A caixa de Legacy é "tudo foil e inglês": a cópia nasce foil EN, e a
    # impressão escolhida tem de existir em foil (a de 1996 não tem).
    rep = loadout.report(con)
    loadout.registar_falta(con, rep, "lg", "Force of Will", quantidade=1,
                           csv_path=_TMP / "faltas2.csv")
    lg = copias(con)[-1]
    assert lg["language"] == "en" and lg["finish"] == "foil", lg
    assert lg["set_code"] == "2xm", ("a `all` de 1996 não existe em foil", lg)

    # E uma edição escrita à mão que a caixa não aceita é recusada: o selector
    # nunca a ofereceu, e um pedido cru não pode meter um 2x2 no Premodern.
    rep = loadout.report(con)
    try:
        loadout.registar_falta(con, rep, "pm", "Swords to Plowshares",
                               quantidade=1, set_code="2x2",
                               csv_path=_TMP / "faltas2.csv")
        raise AssertionError("devia ter recusado a edição de 2022")
    except ValueError as e:
        assert "2X2" in str(e), str(e)
    print("material: Premodern PT/ody, Legacy EN foil/2xm, e o 2x2 e recusado")


def caso_a_linha_muda_de_passo():
    """Depois do check a linha sai de «comprar» (e do custo) e aparece no passo 1
    como *na caixa ✓*, com a marca «edição por confirmar». A percentagem e os
    totais são os da alocação de sempre — não há uma segunda contagem."""
    repor()
    con = montavel()
    c, rep, d = caixa(con)
    custo_antes = d["resumo"]["custo"]
    loadout.registar_falta(con, rep, "pm", "Swords to Plowshares",
                           board="main", quantidade=2,
                           csv_path=_TMP / "faltas3.csv")

    c, _rep, d = caixa(con)
    assert c["wantlist"] == [], ("saiu do passo 2", c["wantlist"])
    assert c["comprar"] == 0 and c["pct"] == 100, (c["comprar"], c["pct"])
    assert d["resumo"]["custo"] <= custo_antes, (d["resumo"]["custo"], custo_antes)
    M = c["montar"]
    assert M["copias_por_confirmar"] == 2, M["copias_por_confirmar"]
    assert [x["nm"] for x in M["por_confirmar"]] == ["Swords to Plowshares"]
    # E não há nada para tirar da gaveta: a cópia já está DENTRO da caixa.
    assert M["marcar_q"] == 0 and M["tirar"] == [], M
    print("a linha sai de «comprar» e entra no passo 1 como «na caixa ✓»")


def caso_anular_apaga_a_copia_que_acabou_de_nascer():
    """O *anular* do aviso: a cópia desaparece e a caixa volta a ter a falta. E
    só apaga o que o check criou — este é o único botão do vault que apaga uma
    cópia sem passar pelo «vendida», e um `copy_id` trocado não pode levar uma
    carta a sério à frente."""
    repor()
    con = montavel()
    reg = _TMP / "faltas4.csv"
    rep = loadout.report(con)
    r = loadout.registar_falta(con, rep, "pm", "Swords to Plowshares",
                               quantidade=2, csv_path=reg)
    # Uma cópia normal da colecção, para provar que o anular não lhe toca.
    normal = collection.add_copy(con, "Force of Will", set_code="all",
                                 quantity=1, sub_collection="Colecção")
    assert loadout.anular_falta(con, normal, csv_path=reg)["copias"] == 0
    assert any(x["id"] == normal for x in copias(con)), "a normal ficou"

    fora = loadout.anular_falta(con, r["copy_id"], csv_path=reg)
    assert fora["copias"] == 2 and fora["nm"] == "Swords to Plowshares", fora
    assert [x["id"] for x in copias(con)] == [normal], copias(con)
    assert alocacao(con, "pm") == [], alocacao(con, "pm")

    c, _rep, _d = caixa(con)
    assert c["comprar"] == 2, ("a falta voltou", c["comprar"])
    linhas = log(reg)
    assert [l["accao"] for l in linhas] == ["registada", "anulada"], linhas
    print("anular: a copia sai, a falta volta, e uma copia normal nao e tocada")


def caso_a_foto_acerta_a_edicao_em_vez_de_duplicar():
    """*"Se ele não mexer no selector, fica o palpite e a próxima foto dessa
    carta acerta a edição em vez de criar cópia nova."* Criar uma segunda cópia
    era ficar com o dobro das cartas na base por ele ter sido diligente — e a
    caixa passava a "ter" 4 Swords to Plowshares que na estante são 2."""
    repor()
    con = montavel()
    rep = loadout.report(con)
    r = loadout.registar_falta(con, rep, "pm", "Swords to Plowshares",
                               quantidade=2, csv_path=_TMP / "faltas5.csv")
    assert copias(con)[0]["set_code"] == "ody", "o palpite"

    # A foto diz que afinal é a de 4ed — e traz só UMA das duas.
    csvf = _TMP / "foto1.csv"
    csvf.write_text("name,set_code,quantity,language,sub_collection\n"
                    "Swords to Plowshares,4ed,1,pt,Colecção\n", encoding="utf-8")
    res = []
    ok, erros = collection.import_csv(con, csvf, resultados=res)
    assert (ok, erros) == (1, []), (ok, erros)
    assert "já a tenho" in res[0]["motivo"], res[0]

    cps = copias(con)
    assert len(cps) == 2, ("a linha partiu-se em duas, não duplicou", cps)
    porset = {x["set_code"]: x for x in cps}
    assert porset["4ed"]["quantity"] == 1 and porset["ody"]["quantity"] == 1
    assert collection.MARCA_POR_CONFIRMAR not in porset["4ed"]["notes"]
    assert "edicao confirmada" in porset["4ed"]["notes"], porset["4ed"]["notes"]
    assert collection.MARCA_POR_CONFIRMAR in porset["ody"]["notes"], "a outra espera"
    # A cópia confirmada leva consigo o lugar dentro da caixa: eram as duas que
    # lá estavam, e a caixa não pode perder a carta que ele acabou de fotografar.
    assert sorted(a["quantity"] for a in alocacao(con, "pm")) == [1, 1], alocacao(con)
    assert {a["copy_id"] for a in alocacao(con, "pm")} == {x["id"] for x in cps}
    c, _rep, _d = caixa(con)
    assert c["comprar"] == 0 and c["pct"] == 100, (c["comprar"], c["pct"])

    # A segunda foto fecha o resto — e continua a não criar cópia nova.
    csvf.write_text("name,set_code,quantity,language,sub_collection\n"
                    "Swords to Plowshares,4ed,1,pt,Colecção\n", encoding="utf-8")
    collection.import_csv(con, csvf)
    cps = copias(con)
    assert len(cps) == 2 and {x["set_code"] for x in cps} == {"4ed"}, cps
    assert not collection.copias_por_confirmar(con), "já não espera fotos"
    assert sum(x["quantity"] for x in cps) == 2, cps
    print("foto: acerta a edicao da copia que ja existia, e nao duplica")


def caso_a_foto_a_mais_continua_a_entrar():
    """A foto pode trazer mais cópias do que as que estavam por confirmar (ele
    comprou o playset). O que sobra entra como sempre entrou — senão o «já a
    tenho» passava a comer cartas."""
    repor()
    con = montavel()
    rep = loadout.report(con)
    loadout.registar_falta(con, rep, "pm", "Swords to Plowshares", quantidade=1,
                           csv_path=_TMP / "faltas6.csv")
    csvf = _TMP / "foto2.csv"
    csvf.write_text("name,set_code,quantity,language,sub_collection\n"
                    "Swords to Plowshares,4ed,3,pt,Colecção\n", encoding="utf-8")
    ok, erros = collection.import_csv(con, csvf)
    assert (ok, erros) == (1, []), (ok, erros)
    cps = copias(con)
    assert sum(x["quantity"] for x in cps) == 3, cps
    assert {x["set_code"] for x in cps} == {"4ed"}, cps
    print("foto com mais copias: uma acerta a que existia, as outras entram")


def caso_o_pedido_passa_pelo_handler():
    """O caminho todo, pelo mesmo handler HTTP que o telemóvel usa: `falta`
    grava, `falta-anular` desfaz — e sem token, da rede, é 403 nos dois."""
    repor()
    con = montavel()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])

    corpo = json.dumps({"act": "falta", "slot": "pm",
                        "nm": "Swords to Plowshares", "board": "main", "q": 1})
    p = Pedido("/api/caixa", corpo)
    p.do_POST()
    assert p.codigo == 403, (p.codigo, p.corpo)
    assert not copias(con), "um pedido sem token nao pode ter criado nada"

    p = Pedido("/api/caixa", corpo, ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo[:300])
    j = json.loads(p.corpo)
    assert "UW Replenish" in j["msg"] and j["copy_id"], j
    assert len(copias(con)) == 1 and alocacao(con, "pm"), copias(con)

    p = Pedido("/api/caixa", json.dumps({"act": "falta-anular",
                                         "copy_id": j["copy_id"]}),
               ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo[:300])
    assert not copias(con) and not alocacao(con), "a copia saiu"

    # E anular duas vezes não é um segundo caminho para apagar cartas.
    p = Pedido("/api/caixa", json.dumps({"act": "falta-anular",
                                         "copy_id": j["copy_id"]}),
               ip="127.0.0.1")
    p.do_POST()
    assert p.codigo == 200 and "erro" in json.loads(p.corpo), p.corpo[:300]
    print("handler: falta grava, falta-anular desfaz uma vez, e sem token e 403")


# ---------------------------------------------------------------------------
# O que o BROWSER desenha
# ---------------------------------------------------------------------------
def _abas(con, editable):
    """`{aba: html}`, corrido no harness de node. `None` quando não há `node`."""
    if not shutil.which("node"):
        return None
    pasta = Path(tempfile.mkdtemp())
    pagina = pasta / "deckboxes.html"
    pagina.write_text(deckboxes.html_page(con, editable=editable),
                      encoding="utf-8")
    dump = pasta / "abas.json"
    p = subprocess.run(["node", str(Path(__file__).with_name("render_deckboxes.js")),
                        str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_a_pagina_desenha_o_check_e_o_selector():
    """O que ele vê no telemóvel, no passo 2: cada linha de compra com o
    selector de edição (o palpite escolhido) e o check «já a tenho, está no
    deck». No site publicado não existe: lá não há endpoint que grave, e um
    check que não grava mente — a mesma razão dos botões e da barra."""
    repor()
    con = montavel()
    abas = _abas(con, True)
    if abas is None:
        print("check das faltas: sem `node`, saltado")
        return
    html = abas["pm"]
    assert "já a tenho, está no deck" in html, html[-1500:]
    assert 'data-falta="1"' in html and 'data-nm="Swords to Plowshares"' in html
    assert 'class="jed"' in html, "o selector de edição"
    # A edição pré-seleccionada é o palpite — e é uma da era, não a de 2022.
    assert '<option value="ody|1" selected>' in html, html[-1500:]
    assert '2x2' not in html.lower().split('class="jed"')[1][:600], "nem a oferece"

    pub = _abas(con, False)
    assert "data-falta" not in pub["pm"], "no site publicado não há check"
    assert "class=\"jed\"" not in pub["pm"], "nem selector"
    print("passo 2: check + selector com o palpite, e nada disso no site publicado")


def caso_a_pagina_diz_a_edicao_por_confirmar():
    """Depois do check, o passo 1 mostra a cópia como *na caixa ✓* com o «📷
    edição por confirmar». Sem este bloco o palpite virava facto por ninguém
    voltar a olhar para a `notes` de uma cópia."""
    repor()
    con = montavel()
    rep = loadout.report(con)
    loadout.registar_falta(con, rep, "pm", "Swords to Plowshares", quantidade=2,
                           csv_path=_TMP / "faltas7.csv")
    abas = _abas(con, True)
    if abas is None:
        print("edição por confirmar: sem `node`, saltado")
        return
    html = abas["pm"]
    assert "Já na caixa (disseste que tinhas)" in html, html[-1500:]
    assert "📷 edição por confirmar" in html, html[-1500:]
    assert "2 cópias · edição por confirmar" in html, html[-1500:]
    print("passo 1: «já na caixa» com o aviso da edicao por confirmar")


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
    for fn in (caso_o_check_cria_a_copia_e_mete_a_na_caixa,
               caso_a_regra_de_material_da_caixa_manda,
               caso_a_linha_muda_de_passo,
               caso_anular_apaga_a_copia_que_acabou_de_nascer,
               caso_a_foto_acerta_a_edicao_em_vez_de_duplicar,
               caso_a_foto_a_mais_continua_a_entrar,
               caso_o_pedido_passa_pelo_handler,
               caso_a_pagina_desenha_o_check_e_o_selector,
               caso_a_pagina_diz_a_edicao_por_confirmar):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
