"""A FOTO DA DECKBOX FÍSICA de cada caixa (André, 2026-09-21, à letra): *"quero
poder tirar foto à deckbox onde vai ficar cada deck, para ser referência
também"*.

O que aqui se tranca (`mtgvault/fotocaixa.py` + o 8771 + a página):

  1. **`guardar` valida pelos bytes e escreve nos três sítios** — o original
     em `data/deckboxes/<slot>.<ext>`, a reduzida (≤ 800 px, JPEG) em
     `assets/deckboxes/<slot>.jpg`, a data em `caixas[].foto`; substituir
     guarda a anterior em `anteriores/`; um ficheiro que não é imagem, ou um
     slot que não existe, é recusado SEM escrever nada;
  2. **a subpasta `pendentes/deckboxes/` é invisível para quem cataloga
     cartas** — o `mtg-fotos-novas` só vê a raiz de `pendentes/`, o
     `collection.arrumar_fotos` só move da raiz, e o `recolher` deixa no sítio
     (e diz) o que não tem nome de slot;
  3. **`POST /api/foto-caixa`** grava com token (ou do loopback), 403 sem ele
     e sem escrever, 409 a um ficheiro inválido, 413 a um corpo grande de mais;
     o `GET /assets/deckboxes/<slot>.jpg` serve a reduzida;
  4. **a página desenha com e sem foto** (node): a miniatura no cartão da
     fila, a foto e o «ampliar» na aba da caixa, o quadrado «sem foto» — que só
     no modo edição leva o `<input type="file">`;
  5. **nenhum número da alocação ou da venda muda** com a foto guardada.

Não toca na rede. Precisa do Pillow para gerar as imagens de teste (é o mesmo
Pillow com que o `reduzir` trabalha).
"""
import importlib.util
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
SITE = _TMP / "site"
SITE.mkdir()
CFG = {
    "regras_colecao": {}, "decks_vigiados": [],
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "regras_por_formato": [
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "dedicado": True, "acabamento": "foil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "dedicado": True, "lingua": "en", "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "duel-commander", "nome": "Cloud (Duel Commander)",
         "formato": "duel-commander", "fonte": "deck", "ref": "Cloud (Duel Commander)",
         "balde": "Cloud", "estado": "permanente", "prioridade": 1, "notas": ""},
        {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "modern",
         "fonte": "deck", "ref": "Modern", "balde": "SPML",
         "estado": "permanente", "prioridade": 2, "notas": ""},
    ],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, configio, db, fotocaixa, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# Tudo o que o 8771 e a página escrevem vai para a pasta de teste — nunca para
# o `assets/deckboxes/` nem para o `deckboxes.html` do repositório.
webapp.ROOT = SITE
fotocaixa.RAIZ = SITE

from PIL import Image  # noqa: E402

CATALOGO = [("Swords to Plowshares", "4ed", "1995-04-01"),
            ("Mother of Runes", "sld", "2022-01-01"),
            ("Path to Exile", "pf20", "2020-01-01")]
_ABERTAS = []


def imagem(w=1600, h=1200, fmt="JPEG", cor=(180, 40, 40)):
    im = Image.new("RGB", (w, h), cor)
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


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
               VALUES (?,?,?,?,'S',?,'en','rare','Instant',1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"legacy": "legal", "modern": "legal", "duel": "legal"})))
        for fin in ("nonfoil", "foil"):
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, "
                        "date, trend) VALUES (?, 'cardmarket', ?, '2026-09-21', ?)",
                        (f"id-{i}", fin, 2.5))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES ('Colecção', 'player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'").fetchone()["id"]
    for i, q, fin in ((0, 1, "foil"), (1, 1, "foil"), (2, 6, "foil")):
        con.execute("INSERT INTO copies (scryfall_id, quantity, finish, language, purpose, "
                    "sub_collection_id) VALUES (?,?,?,'en','player',?)", (f"id-{i}", q, fin, sub))
    for nome, fmt, cartas in (("Cloud (Duel Commander)", "duel-commander",
                               [("Swords to Plowshares", 1), ("Mother of Runes", 1)]),
                              ("Modern", "modern", [("Path to Exile", 4)])):
        con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                        "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return con


def cfg_novo():
    cfg = json.loads(json.dumps(CFG))
    configio.escrever(cfg, CFG_PATH)
    sources._CFG_CACHE.clear()
    for p in (SITE / "assets" / "deckboxes", _TMP / "deckboxes", SITE / "pendentes"):
        shutil.rmtree(p, ignore_errors=True)
    return cfg


def cfg_ler():
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


def numeros(rep):
    return {"custo": rep["custo_total"], "comprar": rep["comprar_total"],
            "venda": (rep["copias"], rep["total"]), "arrumar": rep["arrumacao"]["copias"],
            "caixas": [(s["slot"], s["pct"], s["tenho"], s["comprar"]) for s in rep["slots"]]}


# ---------------------------------------------------------------------------
def caso_guardar_valida_pelos_bytes_e_escreve_nos_tres_sitios():
    cfg = cfg_novo()
    jpg = imagem()
    assert len(jpg) > 20_000, "a imagem de teste tem de ter tamanho de foto"
    r = fotocaixa.guardar(cfg, "duel-commander", jpg, raiz=SITE)
    orig, red = Path(r["original"]), Path(r["reduzida"])
    assert orig == _TMP / "deckboxes" / "duel-commander.jpg", orig
    assert red == SITE / "assets" / "deckboxes" / "duel-commander.jpg", red
    assert orig.read_bytes() == jpg, "o original guarda-se tal e qual"
    im = Image.open(io.BytesIO(red.read_bytes()))
    assert im.format == "JPEG" and max(im.size) <= fotocaixa.LADO_MAX, (im.format, im.size)
    assert im.size == (800, 600), im.size
    assert r["bytes_reduzida"] <= 150_000 and r["bytes_reduzida"] < r["bytes_original"], r
    foto = cfg["caixas"][0]["foto"]
    assert foto["ficheiro"] == "duel-commander.jpg" and len(foto["em"]) == 19, foto
    assert r["anterior"] is None and r["aviso"] == ""
    # A orientação EXIF respeita-se: uma foto "deitada" com a etiqueta de rodar
    # sai de pé (é como o telemóvel grava).
    im2 = Image.new("RGB", (1200, 900), (10, 120, 40))
    exif = Image.Exif()
    exif[0x0112] = 6                                   # Orientation: rodar 90°
    buf = io.BytesIO()
    im2.save(buf, "JPEG", exif=exif.tobytes())
    r2 = fotocaixa.guardar(cfg, "duel-commander", buf.getvalue(), raiz=SITE)
    assert Image.open(io.BytesIO(red.read_bytes())).size == (600, 800), "rodou pelo EXIF"
    # Substituir: a anterior vai para `anteriores/` com a data; nada se apaga.
    ant = Path(r2["anterior"])
    assert ant.parent == _TMP / "deckboxes" / "anteriores" and ant.name.startswith("duel-commander-")
    assert ant.read_bytes() == jpg, "a anterior é o original de antes"
    assert cfg["caixas"][0]["foto"]["em"] >= foto["em"]
    # PNG: o original fica `.png`, a versão do site é sempre `.jpg`.
    r3 = fotocaixa.guardar(cfg, "modern", imagem(900, 900, "PNG"), raiz=SITE)
    assert Path(r3["original"]).suffix == ".png" and Path(r3["reduzida"]).suffix == ".jpg"
    assert cfg["caixas"][1]["foto"]["ficheiro"] == "modern.png"
    # Recusas, sem escrever nada.
    antes = sorted(p.name for p in (_TMP / "deckboxes").iterdir())
    for slot, dados, txt in (("modern", b"isto nao e uma imagem", "não é uma imagem"),
                             ("nao-existe", jpg, "não existe"),
                             ("modern", b"", "vazio"),
                             ("modern", b"\xff\xd8\xff" + b"x" * 40, "não consegui ler")):
        try:
            fotocaixa.guardar(cfg, slot, dados, raiz=SITE)
            raise AssertionError(f"{slot}/{txt}: tinha de recusar")
        except fotocaixa.FotoInvalida as e:
            assert txt in str(e), (txt, e)
    assert sorted(p.name for p in (_TMP / "deckboxes").iterdir()) == antes
    assert cfg["caixas"][1]["foto"]["ficheiro"] == "modern.png", "a recusa não mexe na data"
    # `info`: a verdade é o ficheiro em assets/ (uma data sem ficheiro é «sem foto»).
    i = fotocaixa.info(cfg["caixas"][0], raiz=SITE)
    assert i["em"] == cfg["caixas"][0]["foto"]["em"][:10] and i["url"].startswith(
        "assets/deckboxes/duel-commander.jpg?v="), i
    assert fotocaixa.info({"slot": "legacy", "foto": {"em": "2026-09-21"}}, raiz=SITE) is None
    assert fotocaixa.tipo_da_imagem(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert fotocaixa.tipo_da_imagem(b"\x00\x00\x00\x18ftypheic\x00\x00") == "heic"
    print("guardar valida pelos bytes, reduz, arquiva a anterior e escreve a data")


def caso_a_subpasta_de_pendentes_e_invisivel_para_quem_cataloga_cartas():
    """Uma foto de uma caixa de plástico nunca pode chegar ao Claude que
    cataloga cartas: os dois importadores só olham para a RAIZ de
    `pendentes/`. Prova-se com os próprios programas, não com uma cópia da
    lógica deles."""
    cfg = cfg_novo()
    pend = SITE / "pendentes"
    (pend / "deckboxes").mkdir(parents=True)
    (pend / "deckboxes" / "duel-commander.jpg").write_bytes(imagem(1000, 700))
    (pend / "deckboxes" / "nao-e-slot.jpg").write_bytes(imagem(300, 300))
    (pend / "deckboxes" / "modern.jpg").write_bytes(b"lixo que nao e imagem")

    # (a) o `mtg-fotos-novas` do ai-pc: com SÓ a subpasta cheia, diz "sem fotos
    # novas" — a listagem dele nunca desce a `deckboxes/`.
    run_py = Path(os.environ.get("AIPC_ROOT") or Path.home() / "Desktop" / "ai-pc") \
        / "tasks" / "mtg-fotos-novas" / "run.py"
    if run_py.exists():
        os.environ["MTGVAULT_REPO"] = str(SITE)
        os.environ.setdefault("AIPC_ROOT", str(run_py.parents[2]))
        spec = importlib.util.spec_from_file_location("mtg_fotos_novas_run", run_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        estados = []

        class Fim(Exception):
            pass

        def finish(state, code=0):
            estados.append(state)
            raise Fim()
        mod.finish = finish
        try:
            mod.main()
        except Fim:
            pass
        assert estados == ["sem fotos novas"], estados
    else:
        print("  (sem ai-pc/tasks/mtg-fotos-novas/run.py: esse lado não foi verificado)")

    # (b) o `collection.arrumar_fotos` (o `processar_fotos.py` e o `import
    # --arrumar-fotos`): um resultado que aponte para a subpasta não move nada
    # de lá — só se arruma o que está em `pend / nome`.
    con = base()
    res = [{"resultado": "importada", "photo_path": "deckboxes/duel-commander.jpg",
            "copy_id": "", "name": "x", "set_code": "y", "collector_number": "1",
            "quantity": 1, "sub_collection": ""}]
    r = collection.arrumar_fotos(con, res, pendentes=pend)
    assert r["movidas"] == 0 and (pend / "deckboxes" / "duel-commander.jpg").exists(), r

    # (c) o `recolher`: leva a que tem nome de slot e é imagem; deixa (e diz)
    # as outras duas. A segunda corrida não faz nada.
    r = fotocaixa.recolher(cfg, raiz=SITE)
    assert [x["slot"] for x in r["recolhidas"]] == ["duel-commander"], r
    assert not (pend / "deckboxes" / "duel-commander.jpg").exists(), "moveu-se (não se apagou)"
    assert (_TMP / "deckboxes" / "duel-commander.jpg").exists()
    assert (SITE / "assets" / "deckboxes" / "duel-commander.jpg").exists()
    ig = {i["ficheiro"]: i["porque"] for i in r["ignorados"]}
    assert set(ig) == {"nao-e-slot.jpg", "modern.jpg"}, ig
    assert "não é o slot" in ig["nao-e-slot.jpg"] and "não é uma imagem" in ig["modern.jpg"], ig
    assert (pend / "deckboxes" / "nao-e-slot.jpg").exists() and (pend / "deckboxes" / "modern.jpg").exists()
    assert cfg["caixas"][0]["foto"]["ficheiro"] == "duel-commander.jpg"
    memo: dict = {}
    r = fotocaixa.recolher(cfg, raiz=SITE, ignorar=memo)
    assert r["recolhidas"] == [] and len(r["ignorados"]) == 2 and set(memo) == set(ig)
    assert not fotocaixa.ha_pendentes(SITE, ignorar=memo), "com o memo, nada por recolher"
    assert fotocaixa.ha_pendentes(SITE), "sem memo, os ignorados continuam lá"
    print("a subpasta pendentes/deckboxes e invisivel para quem cataloga cartas; recolher leva so os slots")


class Pedido(webapp.Handler):
    """Um pedido de mentira, com corpo em BYTES (a foto vai tal e qual)."""

    def __init__(self, path, corpo=b"", ip="127.0.0.1", tamanho=None):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO(corpo)
        self.headers = {"Content-Length": str(len(corpo) if tamanho is None else tamanho)}
        self.codigo, self.corpo = None, b""

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
                self_.corpo = b
        return Escritor()


def _post(slot, corpo, ip="127.0.0.1", tamanho=None):
    p = Pedido(f"/api/foto-caixa?slot={slot}", corpo, ip=ip, tamanho=tamanho)
    p.do_POST()
    txt = p.corpo.decode("utf-8", "replace")
    return p.codigo, (json.loads(txt) if txt.startswith("{") else txt)


def caso_o_endpoint_grava_com_token_e_recusa_sem():
    cfg_novo()
    con = base()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(next(r["file"] for r in dbs if r["name"] == "main"))
    db.DEFAULT_CATALOG = Path(next(r["file"] for r in dbs if r["name"] == "catalog"))
    webapp.CONFIG = CFG_PATH
    jpg = imagem(1400, 1000, cor=(30, 60, 200))
    # Da rede, sem token: 403 e nada escrito.
    cod, j = _post("duel-commander", jpg, ip="192.168.1.9")
    assert cod == 403 and "foto" not in cfg_ler()["caixas"][0], (cod, j)
    assert not (SITE / "assets" / "deckboxes").exists()
    # Do loopback: grava, regenera e diz o que fez.
    cod, j = _post("duel-commander", jpg)
    assert cod == 200 and j["ok"], (cod, j)
    assert "Cloud (Duel Commander)" in j["msg"] and "data/deckboxes/" in j["msg"], j["msg"]
    assert j["bytes_reduzida"] < j["bytes_original"] == len(jpg), j
    assert cfg_ler()["caixas"][0]["foto"]["ficheiro"] == "duel-commander.jpg"
    assert (SITE / "assets" / "deckboxes" / "duel-commander.jpg").exists()
    assert (SITE / "deckboxes.html").exists(), "regenerou no ROOT de teste"
    idx = json.loads((SITE / "data" / "paginas" / "deckboxes.json").read_text(encoding="utf-8"))
    c = next(x for x in idx["caixas"] if x["slot"] == "duel-commander")
    assert c["foto"] and c["foto"]["url"].startswith("assets/deckboxes/duel-commander.jpg?v="), c["foto"]
    # Com token da rede: também grava (a segunda vez arquiva a anterior).
    tok = webapp.token()
    p = Pedido(f"/api/foto-caixa?slot=duel-commander&t={tok}", jpg, ip="192.168.1.9")
    p.do_POST()
    j = json.loads(p.corpo.decode("utf-8"))
    assert p.codigo == 200 and j["anterior"] and "anteriores" in j["msg"], (p.codigo, j)
    # Recusas: ficheiro inválido (409), caixa que não existe (409), sem slot
    # (409), corpo grande de mais (413) — e a data fica a de antes.
    em = cfg_ler()["caixas"][0]["foto"]["em"]
    cod, j = _post("duel-commander", b"isto nao e uma imagem")
    assert cod == 409 and "não é uma imagem" in j["erro"], (cod, j)
    cod, j = _post("nao-existe", jpg)
    assert cod == 409 and "não existe" in j["erro"], (cod, j)
    cod, j = _post("", jpg)
    assert cod == 409 and "slot" in j["erro"], (cod, j)
    cod, j = _post("duel-commander", b"", tamanho=fotocaixa.MAX_BYTES + 1)
    assert cod == 413 and "máximo" in j["erro"], (cod, j)
    assert cfg_ler()["caixas"][0]["foto"]["em"] == em
    # O GET da reduzida: serve-se do disco; uma caixa sem foto é 404; fora
    # de `assets/deckboxes/` não se serve.
    g = Pedido("/assets/deckboxes/duel-commander.jpg?v=abc")
    g.do_GET()
    assert g.codigo == 200 and g.corpo[:3] == b"\xff\xd8\xff", g.codigo
    g = Pedido("/assets/deckboxes/modern.jpg")
    g.do_GET()
    assert g.codigo == 404
    # A recolha da subpasta acontece ao pedir o índice (o caminho (b) no 8771).
    (SITE / "pendentes" / "deckboxes").mkdir(parents=True, exist_ok=True)
    (SITE / "pendentes" / "deckboxes" / "modern.jpg").write_bytes(imagem(800, 500))
    g = Pedido("/data/paginas/deckboxes.json")
    g.do_GET()
    assert g.codigo == 200
    assert not (SITE / "pendentes" / "deckboxes" / "modern.jpg").exists(), "recolhida"
    assert cfg_ler()["caixas"][1]["foto"]["ficheiro"] == "modern.jpg"
    idx = json.loads(g.corpo.decode("utf-8"))
    assert next(x for x in idx["caixas"] if x["slot"] == "modern")["foto"], "o índice já a leva"
    print("o endpoint grava com token, recusa sem ele, e o GET serve a reduzida")


def caso_a_pagina_desenha_com_e_sem_foto():
    cfg = cfg_novo()
    con = base()
    fotocaixa.guardar(cfg, "duel-commander", imagem(1000, 800), raiz=SITE)
    configio.escrever(cfg, CFG_PATH)
    sources._CFG_CACHE.clear()
    rep = loadout.report(con)
    for editable in (False, True):
        d = deckboxes.payload(con, rep, editable=editable)
        dc = next(x for x in d["caixas"] if x["slot"] == "duel-commander")
        md = next(x for x in d["caixas"] if x["slot"] == "modern")
        assert dc["foto"]["url"].startswith("assets/deckboxes/duel-commander.jpg?v=") and md["foto"] is None
        idx, partes = deckboxes.partir(d)
        assert idx["caixas"][0]["foto"] == dc["foto"], "a foto fica no índice (é o cartão da fila)"
        assert deckboxes.juntar(idx, partes) == d
        html = deckboxes.html_page(con, editable=editable, rep=rep)
        pagina = _TMP / f"dx-{int(editable)}.html"
        pagina.write_text(html, encoding="utf-8")
        if not shutil.which("node"):
            print("  (sem node: o render não foi verificado)")
            continue
        dump = _TMP / f"abas-{int(editable)}.json"
        p = subprocess.run(["node", str(RAIZ / "tests" / "render_deckboxes.js"),
                            str(pagina), str(dump)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
        abas = json.loads(dump.read_text(encoding="utf-8"))
        # A fila: a miniatura no cartão da caixa com foto, o quadrado na outra.
        todas = abas["todas"]
        assert 'class="dbthumb"' in todas and "assets/deckboxes/duel-commander.jpg?v=" in todas, todas[:600]
        assert 'dbthumb vazia' in todas and "sem foto da deckbox" in todas, todas[:600]
        assert 'loading="lazy"' in todas
        # A aba da caixa com foto: a imagem maior, com o «ampliar»; a legenda
        # com a data; o «trocar» só no modo edição.
        aba = abas["duel-commander"]
        assert 'data-ampliar="assets/deckboxes/duel-commander.jpg?v=' in aba, aba[:800]
        assert "a deckbox desta caixa" in aba and "foto de 20" in aba, aba[:800]
        assert ("trocar a foto" in aba) is editable
        assert ('data-foto-caixa="duel-commander"' in aba) is editable
        # A aba da caixa sem foto: o quadrado — botão (input) só no modo edição.
        aba = abas["modern"]
        assert "📦 sem foto da deckbox" in aba, aba[:800]
        assert ('<input type="file"' in aba) is editable, "só no 8771 é botão"
        assert ('data-foto-caixa="modern"' in aba) is editable
        assert ("toca para fotografar" in aba) is editable
        assert 'data-ampliar' not in aba
        assert ("blocos de escrita (editavel=" in p.stdout), p.stdout
    print("a pagina desenha a miniatura, a foto grande com ampliar, e o quadrado sem foto")


def caso_nenhum_numero_muda():
    cfg_novo()
    con = base()
    antes = numeros(loadout.report(con))
    cfg = cfg_ler()
    for slot in ("duel-commander", "modern"):
        fotocaixa.guardar(cfg, slot, imagem(1200, 900), raiz=SITE)
    configio.escrever(cfg, CFG_PATH)
    sources._CFG_CACHE.clear()
    depois = numeros(loadout.report(con))
    assert antes == depois, (antes, depois)
    assert antes["caixas"] == [("duel-commander", 100, 2, 0), ("modern", 100, 4, 0)], antes
    assert antes["venda"] == (2, 5.0), antes["venda"]
    print("nenhum numero da alocacao ou da venda muda com a foto")


def run():
    for fn in (caso_guardar_valida_pelos_bytes_e_escreve_nos_tres_sitios,
               caso_a_subpasta_de_pendentes_e_invisivel_para_quem_cataloga_cartas,
               caso_o_endpoint_grava_com_token_e_recusa_sem,
               caso_a_pagina_desenha_com_e_sem_foto,
               caso_nenhum_numero_muda):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
