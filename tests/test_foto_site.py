"""TIRAR AS FOTOS DAS CARTAS DIRECTAMENTE DO SITE, NO TELEMÓVEL (André,
2026-09-21, à letra): *"é possível ter o site preparado para eu abrir no
telefone e tirar as fotos directamente do site?"* — *"e guardares as fotos,
claro"*.

O que aqui se tranca (`mtgvault/fotosite.py` + o 8771 + o import + a página):

  1. **o NOME diz a origem** e lê-se de volta (`nome_ficheiro` ↔ `origem`):
     `site-<slot>-<data>-<n>[-c<copy_id>].<ext>`, `site-venda-…`, `site-rl-…`,
     `site-colecao-…`; um slot com hífenes não confunde; uma foto largada à
     mão não tem origem;
  2. **`ler_multipart` + `guardar`**: a foto guarda-se INTEIRA, tal como veio
     (bytes iguais — não se reduz), várias por pedido, e um ficheiro que não é
     imagem recusa o pedido inteiro SEM escrever nada;
  3. **`POST /api/foto`**: grava com token (ou do loopback), 403 sem ele e
     sem escrever, 409 a um ficheiro inválido / caixa ou cópia que não existe,
     413 a um corpo grande de mais; o `esperadas.md` ganha a secção das fotos
     do site e o índice da Deckboxes conta-as;
  4. **«⚡ Processar agora»** escreve a ordem `command` na inbox do runner com
     o formato certo (`py runner.py run mtg-fotos-novas`, `cwd` do ai-pc,
     atómica, `nao_antes` = a foto mais recente + 2 min), no máximo uma por 5
     min, e «já está a processar» com uma pendente;
  5. **o `import_csv` prefere a caixa e a cópia do nome** (passo (0) e a
     discrepância), mesmo sem alvo no config;
  6. **as fotos por resolver** (linhas paradas do `recat-…-resultado.csv`
     com a foto ainda em `pendentes/`) saem com o motivo;
  7. **a página nos dois modos** (node): «Tirar fotos» (multiple), o 📷 por
     cópia (`data-copy`) e o «Processar agora» só no 8771; a lista «à
     espera» nos dois;
  8. **nenhum número da alocação ou da venda muda**.

Não toca na rede. Precisa do Pillow para gerar as imagens de teste.
"""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
SITE = _TMP / "site"
SITE.mkdir()
INBOX = _TMP / "aipc" / "inbox"
CFG = {
    # O alvo «venda» da câmara vive no grupo Venda da aba Revalidação, e esse
    # grupo fica VAZIO com o interruptor de 2026-09-25 (a omissão é desligado):
    # as cópias passam a contar no sítio onde estão. Este ficheiro testa esse
    # alvo, por isso liga-o.
    "venda": {"mostrar": True},
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
    "revalidacao": {"desde": "2026-09-20", "alvo": None},
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, configio, db, encomendas, fotocaixa,  # noqa: E402
                      fotosite, loadout, revalidacao, sources)

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# Tudo o que o 8771 e a página escrevem vai para a pasta de teste — nunca para
# o `pendentes/` do repositório nem para a inbox a sério do ai-pc.
webapp.ROOT = SITE
fotocaixa.RAIZ = SITE
fotosite.INBOX = INBOX
PEND = SITE / "pendentes"

from PIL import Image  # noqa: E402

CATALOGO = [("Swords to Plowshares", "4ed", "1995-04-01"),
            ("Mother of Runes", "sld", "2022-01-01"),
            ("Path to Exile", "pf20", "2020-01-01"),
            ("Path to Exile", "mm3", "2017-03-17"),
            ("Brainstorm", "ice", "1995-06-03")]
_ABERTAS = []
Q = dt.datetime(2026, 9, 21, 10, 15, 0)


def imagem(w=1200, h=900, fmt="JPEG", cor=(180, 40, 40)):
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
            (f"id-{i}", f"or-{nm}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"legacy": "legal", "modern": "legal", "duel": "legal"})))
        for fin in ("nonfoil", "foil"):
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, "
                        "date, trend) VALUES (?, 'cardmarket', ?, '2026-09-21', ?)",
                        (f"id-{i}", fin, 2.5))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES ('Colecção', 'player')")
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


def copia(con, nm, sc, q=1, finish="foil", foto="velha.jpg", slot=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish=finish, sub_collection="Colecção")
    con.execute("UPDATE copies SET photo_path = ?, validado_em = NULL WHERE id = ?", (foto, cid))
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) VALUES (?,?,?)",
                    (cid, slot, q))
    con.commit()
    return cid


def mundo(con):
    """Duel Commander: 1 Swords + 1 Mother (na caixa); Modern: 4 Path (2 na
    caixa, 2 na gaveta). Tudo por revalidar."""
    a = copia(con, "Swords to Plowshares", "4ed", slot="duel-commander")
    b = copia(con, "Mother of Runes", "sld", slot="duel-commander")
    c = copia(con, "Path to Exile", "pf20", q=2, slot="modern")
    d = copia(con, "Path to Exile", "pf20", q=2)
    return a, b, c, d


def copias(con):
    return {r["id"]: dict(r) for r in con.execute(
        """SELECT cp.id, cp.quantity, cp.finish, cp.notes, cp.photo_path, cp.validado_em,
                  cp.foto_anterior, c.name, c.set_code
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id ORDER BY cp.id""")}


def cfg_novo(alvo=None):
    webapp.esperar_fundo(120)          # uma regeneração em fundo do caso anterior
    cfg = json.loads(json.dumps(CFG))
    cfg["revalidacao"]["alvo"] = alvo
    configio.escrever(cfg, CFG_PATH)
    sources._CFG_CACHE.clear()
    for p in (PEND, INBOX, SITE / "data"):
        shutil.rmtree(p, ignore_errors=True)
    webapp._CACHE.clear()
    return cfg


def ligar_base(con):
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(next(r["file"] for r in dbs if r["name"] == "main"))
    db.DEFAULT_CATALOG = Path(next(r["file"] for r in dbs if r["name"] == "catalog"))
    webapp.CONFIG = CFG_PATH


def multipart(ficheiros, fronteira="Xx1234"):
    """Um corpo `multipart/form-data` como o browser o manda: `[(nome, bytes)]`."""
    b = b""
    for nome, dados in ficheiros:
        b += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"foto\"; "
              f"filename=\"{nome}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() \
             + dados + b"\r\n"
    b += f"--{fronteira}--\r\n".encode()
    return f"multipart/form-data; boundary={fronteira}", b


def numeros(rep):
    return {"custo": rep["custo_total"], "comprar": rep["comprar_total"],
            "venda": (rep["copias"], rep["total"]), "arrumar": rep["arrumacao"]["copias"],
            "caixas": [(s["slot"], s["pct"], s["tenho"], s["comprar"]) for s in rep["slots"]]}


# ---------------------------------------------------------------------------
def caso_o_nome_diz_a_origem_e_le_se_de_volta():
    casos = [("caixa", "duel-commander", None, "site-duel-commander-20260921-101500-1.jpg"),
             ("caixa", "pioneer-jeskai", 739, "site-pioneer-jeskai-20260921-101500-1-c739.jpg"),
             ("venda", None, None, "site-venda-20260921-101500-1.jpg"),
             ("rl", None, 12, "site-rl-20260921-101500-1-c12.jpg"),
             ("coleccao", None, None, "site-colecao-20260921-101500-1.jpg")]
    for tipo, slot, cid, esperado in casos:
        nome = fotosite.nome_ficheiro(tipo, slot, Q, 1, "jpg", cid)
        assert nome == esperado, (nome, esperado)
        o = fotosite.origem(nome)
        assert o == {"tipo": tipo, "slot": slot, "quando": "2026-09-21 10:15:00", "n": 1,
                     "copy_id": cid}, (nome, o)
    # Um caminho inteiro também se lê; a extensão pode variar; maiúsculas idem.
    assert fotosite.origem(r"C:\x\pendentes\site-modern-20260921-101500-3.PNG")["n"] == 3
    assert fotosite.origem("site-venda-20260921-101500-2-c5.heic")["copy_id"] == 5
    # O que NÃO veio do site.
    for nome in ("IMG_2031.jpg", "site-modern.jpg", "site-modern-2026-09-21-1.jpg",
                 "recat-20260921-0230-resultado.csv", "", None):
        assert fotosite.origem(nome) is None, nome
    # Recusas: tipo que não existe, caixa sem slot, slot que se confunde com um alvo.
    for args in (("xpto", None), ("caixa", None), ("caixa", "venda"), ("caixa", "a b")):
        try:
            fotosite.nome_ficheiro(args[0], args[1], Q, 1, "jpg")
            raise AssertionError(f"{args}: tinha de recusar")
        except fotocaixa.FotoInvalida:
            pass
    print("o nome diz a origem (caixa/venda/rl/colecao, copia) e le-se de volta")


def caso_multipart_e_guardar_inteira_sem_reduzir():
    cfg_novo()
    jpg, png = imagem(1600, 1200), imagem(700, 500, "PNG")
    assert len(jpg) > 20_000
    ct, corpo = multipart([("IMG_1.jpg", jpg), ("a b.png", png)])
    partes = fotosite.ler_multipart(ct, corpo)
    assert [(p["campo"], p["nome"]) for p in partes] == [("foto", "IMG_1.jpg"), ("foto", "a b.png")]
    assert partes[0]["dados"] == jpg and partes[1]["dados"] == png, "os bytes chegam tal e qual"
    r = fotosite.guardar(PEND, "caixa", partes, slot="modern", quando=Q)
    assert [g["nome"] for g in r] == ["site-modern-20260921-101500-1.jpg",
                                      "site-modern-20260921-101500-2.png"], r
    assert (PEND / r[0]["nome"]).read_bytes() == jpg, "a foto guarda-se INTEIRA, tal como veio"
    assert (PEND / r[1]["nome"]).read_bytes() == png
    assert not list(PEND.glob("*.tmp")), "escrita atómica: não fica temporário"
    # O mesmo segundo outra vez: o `n` salta o que já lá está; com cópia, `-c<id>`.
    r2 = fotosite.guardar(PEND, "caixa", [{"nome": "x.jpg", "dados": jpg}], slot="modern",
                          quando=Q, copy_id=7)
    assert r2[0]["nome"] == "site-modern-20260921-101500-1-c7.jpg", r2
    r3 = fotosite.guardar(PEND, "caixa", [{"nome": "x.jpg", "dados": jpg}], slot="modern", quando=Q)
    assert r3[0]["nome"] == "site-modern-20260921-101500-3.jpg", r3
    # Recusas SEM escrever nada: um ficheiro que não é imagem estraga o pedido inteiro.
    antes = sorted(p.name for p in PEND.iterdir())
    for fich, txt in (([("a.jpg", jpg), ("b.jpg", b"isto nao e uma imagem")], "não é uma imagem"),
                      ([("a.jpg", b"")], "vazio"),
                      ([], "nenhuma foto"),
                      ([(f"{i}.jpg", jpg) for i in range(fotosite.MAX_FICHEIROS + 1)], "máximo")):
        try:
            fotosite.guardar(PEND, "venda", [{"nome": n, "dados": d} for n, d in fich], quando=Q)
            raise AssertionError(f"{txt}: tinha de recusar")
        except fotocaixa.FotoInvalida as e:
            assert txt in str(e), (txt, e)
    assert sorted(p.name for p in PEND.iterdir()) == antes
    # O corpo tem de ser multipart.
    try:
        fotosite.ler_multipart("application/json", b"{}")
        raise AssertionError("tinha de recusar")
    except fotocaixa.FotoInvalida as e:
        assert "multipart" in str(e)
    # `enviadas`: da mais recente para a mais antiga, com a origem e o «pronta».
    env = fotosite.enviadas(PEND, agora=time.time())
    assert len(env) == 4 and all(e["origem"]["slot"] == "modern" for e in env)
    assert not any(e["pronta"] for e in env), "acabadas de escrever: menos de 2 min"
    env = fotosite.enviadas(PEND, agora=time.time() + 200)
    assert all(e["pronta"] for e in env)
    print("multipart le-se; guardar escreve inteira, atomica, sem reduzir; recusa sem escrever")


class Pedido(webapp.Handler):
    """Um pedido de mentira, com o corpo em BYTES e o Content-Type do multipart."""

    def __init__(self, path, corpo=b"", ip="127.0.0.1", tamanho=None, content_type=None):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO(corpo)
        self.headers = {"Content-Length": str(len(corpo) if tamanho is None else tamanho)}
        if content_type:
            self.headers["Content-Type"] = content_type
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


def _post(caminho, ficheiros=None, ip="127.0.0.1", tamanho=None, json_=None):
    if json_ is not None:
        corpo, ct = json.dumps(json_).encode("utf-8"), "application/json"
    else:
        ct, corpo = multipart(ficheiros or [])
    p = Pedido(caminho, corpo, ip=ip, tamanho=tamanho, content_type=ct)
    p.do_POST()
    txt = p.corpo.decode("utf-8", "replace")
    return p.codigo, (json.loads(txt) if txt.startswith("{") else txt)


def caso_o_endpoint_grava_com_token_e_recusa_sem():
    cfg_novo()
    con = base()
    a, b, c, d = mundo(con)
    ligar_base(con)
    jpg = imagem(1400, 1000, cor=(30, 60, 200))
    # Da rede, sem token: 403 e nada escrito.
    cod, j = _post("/api/foto?tipo=caixa&slot=duel-commander", [("IMG_1.jpg", jpg)], ip="192.168.1.9")
    assert cod == 403 and not PEND.exists(), (cod, j)
    # Do loopback: grava as duas, diz o que fez, e o nome traz a caixa.
    cod, j = _post("/api/foto?tipo=caixa&slot=duel-commander", [("IMG_1.jpg", jpg), ("IMG_2.jpg", jpg)])
    assert cod == 200 and j["ok"] and len(j["ficheiros"]) == 2, (cod, j)
    assert all(f.startswith("site-duel-commander-") and f.endswith(".jpg") for f in j["ficheiros"]), j
    assert "Cloud (Duel Commander)" in j["msg"] and "02:30" in j["msg"] and "2 fotos" in j["msg"], j["msg"]
    for f in j["ficheiros"]:
        assert (PEND / f).read_bytes() == jpg, "inteira, na RAIZ de pendentes/"
    # Com a cópia esperada: `-c<id>`; uma cópia que não existe é 409.
    cod, j = _post(f"/api/foto?tipo=caixa&slot=modern&copy={c}", [("IMG_3.jpg", jpg)])
    assert cod == 200 and j["ficheiros"][0].endswith(f"-c{c}.jpg") and j["copy_id"] == c, j
    cod, j = _post("/api/foto?tipo=caixa&slot=modern&copy=99999", [("IMG_3.jpg", jpg)])
    assert cod == 409 and "já não existe" in j["erro"], (cod, j)
    # Os outros alvos não levam slot.
    cod, j = _post("/api/foto?tipo=venda", [("IMG_4.jpg", jpg)])
    assert cod == 200 and j["ficheiros"][0].startswith("site-venda-") and j["slot"] is None, j
    cod, j = _post("/api/foto?tipo=coleccao&slot=modern", [("IMG_5.jpg", jpg)])
    assert cod == 200 and j["ficheiros"][0].startswith("site-colecao-"), j
    # Com token da rede: também grava.
    ct, corpo = multipart([("IMG_6.jpg", jpg)])
    p = Pedido(f"/api/foto?tipo=rl&t={webapp.token()}", corpo, ip="192.168.1.9", content_type=ct)
    p.do_POST()
    assert p.codigo == 200 and json.loads(p.corpo)["ficheiros"][0].startswith("site-rl-"), p.corpo
    n_antes = len(list(PEND.glob("site-*")))
    assert n_antes == 6
    # Recusas: ficheiro inválido (409, e as outras do pedido também não entram),
    # caixa que não existe (409), tipo desconhecido (409), sem slot (409),
    # corpo grande de mais (413), JSON em vez de multipart (409).
    cod, j = _post("/api/foto?tipo=caixa&slot=modern", [("a.jpg", jpg), ("b.jpg", b"lixo")])
    assert cod == 409 and "não é uma imagem" in j["erro"], (cod, j)
    cod, j = _post("/api/foto?tipo=caixa&slot=nao-existe", [("a.jpg", jpg)])
    assert cod == 409 and "não existe" in j["erro"], (cod, j)
    cod, j = _post("/api/foto?tipo=xpto", [("a.jpg", jpg)])
    assert cod == 409 and "desconhecido" in j["erro"], (cod, j)
    cod, j = _post("/api/foto?tipo=caixa", [("a.jpg", jpg)])
    assert cod == 409 and "slot" in j["erro"], (cod, j)
    cod, j = _post("/api/foto?tipo=caixa&slot=modern", [], tamanho=fotosite.MAX_PEDIDO + 1)
    assert cod == 413 and "máximo" in j["erro"], (cod, j)
    cod, j = _post("/api/foto?tipo=caixa&slot=modern", json_={"x": 1})
    assert cod == 409 and "multipart" in j["erro"], (cod, j)
    assert len(list(PEND.glob("site-*"))) == n_antes, "as recusas não escreveram nada"
    # Regenerou EM FUNDO (a resposta não espera): o `esperadas.md` tem a
    # secção das fotos do site, com a caixa e a cópia que o nome indica.
    webapp.esperar_fundo(120)
    assert not any(t.is_alive() for t in webapp._FUNDO), "a regeneração em fundo acabou"
    esp = (PEND / "esperadas.md").read_text(encoding="utf-8")
    assert "## Fotos tiradas no site (6)" in esp, esp[:400]
    assert f"cópia #{c}: 2× **Path to Exile** — PF20 #2 foil en" in esp, esp
    assert "caixa Cloud (Duel Commander)" in esp and "— Venda" in esp and "— Caixa Reserved List" in esp
    # O índice conta-as e a parte da caixa lista as dela.
    g = Pedido("/data/paginas/deckboxes.json")
    g.do_GET()
    idx = json.loads(g.corpo.decode("utf-8"))
    assert idx["revalidacao"]["site"]["n"] == 6 and idx["revalidacao"]["site"]["prontas"] == 0, idx["revalidacao"]["site"]
    g = Pedido("/data/paginas/deckboxes/caixa-duel-commander.json")
    g.do_GET()
    parte = json.loads(g.corpo.decode("utf-8"))
    assert [e["origem"]["slot"] for e in parte["rev"]["site"]] == ["duel-commander"] * 2, parte["rev"]["site"]
    # A `copies` e a `copy_allocation` não mexeram: só a foto cria/liga cópias.
    assert len(copias(con)) == 4 and all(not v["validado_em"] for v in copias(con).values())
    print("o endpoint grava com token (multipart, varias, -c<id>), recusa sem ele, regenera o esperadas.md")


def caso_processar_agora_escreve_a_ordem_e_limita():
    cfg_novo()
    con = base()
    mundo(con)
    ligar_base(con)
    # Sem fotos: não há o que processar.
    r = fotosite.pedir_processamento(PEND, INBOX, agora=Q)
    assert not r["escrita"] and "Não há fotos" in r["msg"] and not INBOX.exists(), r
    PEND.mkdir(parents=True)
    foto = PEND / "site-modern-20260921-101400-1.jpg"
    foto.write_bytes(imagem())
    t_foto = dt.datetime(2026, 9, 21, 10, 14, 30)
    os.utime(foto, (t_foto.timestamp(), t_foto.timestamp()))
    # Escreve a ordem, com o formato que o runner lê, e `nao_antes` depois da foto + 2 min.
    r = fotosite.pedir_processamento(PEND, INBOX, agora=Q, raiz_aipc=Path(r"C:\Users\Catarina\Desktop\ai-pc"))
    assert r["escrita"] and r["ordem"] == "mtgvault-fotos-20260921-101500.json", r
    ordem = json.loads((INBOX / r["ordem"]).read_text(encoding="utf-8"))
    assert ordem["kind"] == "command", ordem
    assert ordem["command"] == ["py", "runner.py", "run", "mtg-fotos-novas"], ordem
    assert ordem["cwd"] == r"C:\Users\Catarina\Desktop\ai-pc", ordem
    assert ordem["nao_antes"] == "2026-09-21 10:16:45", ordem       # 10:14:30 + 120 s + 15 s
    assert ordem["fotos"] == [foto.name] and "10:16" in r["msg"], r
    assert not list(INBOX.glob("*.tmp")), "atómica"
    # Segunda vez: já está pendente.
    r2 = fotosite.pedir_processamento(PEND, INBOX, agora=Q + dt.timedelta(minutes=1))
    assert not r2["escrita"] and "Já está a processar" in r2["msg"] and r2["ordem"] == r["ordem"], r2
    # O runner correu-a (está em done/): menos de 5 min depois, não; depois, sim.
    (INBOX / "done").mkdir()
    shutil.move(str(INBOX / r["ordem"]), str(INBOX / "done" / r["ordem"]))
    r3 = fotosite.pedir_processamento(PEND, INBOX, agora=Q + dt.timedelta(minutes=3))
    assert not r3["escrita"] and "no máximo uma por 5 min" in r3["msg"], r3
    r4 = fotosite.pedir_processamento(PEND, INBOX, agora=Q + dt.timedelta(minutes=6))
    assert r4["escrita"] and r4["ordem"] == "mtgvault-fotos-20260921-102100.json", r4
    j4 = json.loads((INBOX / r4["ordem"]).read_text(encoding="utf-8"))
    assert j4["nao_antes"] == "2026-09-21 10:21:00", "a foto já tem mais de 2 min: corre já"
    est = fotosite.estado(PEND, INBOX)
    assert est["processar"]["pendente"]["nome"] == r4["ordem"]
    assert est["processar"]["ultima"]["nome"] == r["ordem"] and est["processar"]["ultima"]["estado"] == "feita"
    # O endpoint: 403 sem token, 200 do loopback com a mensagem do motor.
    cod, j = _post("/api/processar-fotos", json_={}, ip="192.168.1.9")
    assert cod == 403, (cod, j)
    cod, j = _post("/api/processar-fotos", json_={})
    assert cod == 200 and j["ok"] and not j["escrita"] and "Já está a processar" in j["msg"], j
    shutil.rmtree(INBOX)
    cod, j = _post("/api/processar-fotos", json_={})
    assert cod == 200 and j["escrita"] and (INBOX / j["ordem"]).exists(), j
    o = json.loads((INBOX / j["ordem"]).read_text(encoding="utf-8"))
    assert o["cwd"] == str(INBOX.parent) and o["command"][-1] == "mtg-fotos-novas", o
    # O índice passa a dizer «já está a processar».
    g = Pedido("/data/paginas/deckboxes.json")
    g.do_GET()
    idx = json.loads(g.corpo.decode("utf-8"))
    assert idx["revalidacao"]["site"]["processar"]["pendente"]["nome"] == j["ordem"]
    print("processar agora: ordem command na inbox (formato, nao_antes), uma por 5 min, ja pendente")


def _importar(con, linha, nome):
    p = _TMP / nome
    p.write_text("name,set_code,collector_number,quantity,finish,language,sub_collection,photo_path\n"
                 + linha, encoding="utf-8")
    res = []
    ok, erros = collection.import_csv(con, p, resultados=res)
    assert not erros, erros
    return res


def caso_o_import_prefere_a_caixa_e_a_copia_do_nome():
    """Sem alvo no config. Duas cópias iguais por revalidar: uma na caixa do
    Modern (2, na `copy_allocation`) e outra na gaveta (2). Uma foto
    `site-modern-…` valida a DA CAIXA; uma `IMG_…` (sem prefixo) segue a
    ordem de sempre; uma `…-c<id>` vai à cópia nomeada mesmo contra a ordem."""
    cfg_novo()
    con = base()
    a, b, c, d = mundo(con)
    # Uma QUINTA Path (o deck pede 4: c + d chegam) — fica na gaveta, fora da
    # caixa do Modern, e é a que a ordem de sempre escolhe para uma foto de 1
    # (a mesma quantidade da foto).
    e = copia(con, "Path to Exile", "pf20", q=1)
    assert revalidacao.alvo() is None
    # (A) Sem prefixo: a ordem de sempre — a MESMA quantidade da foto → `e`.
    res = _importar(con, "Path to Exile,pf20,2,1,foil,en,Colecção,IMG_9.jpg", "f0.csv")
    assert res[0]["motivo"] == "1 revalidada: foto nova" and res[0]["copy_id"] == e, res[0]
    assert copias(con)[e]["validado_em"] and copias(con)[c]["quantity"] == 2
    con.execute("UPDATE copies SET validado_em = NULL, photo_path = 'velha.jpg' WHERE id = ?", (e,))
    con.commit()
    # (B) Com `site-modern-…` (sem cópia): prefere as cópias DA CAIXA do Modern
    # — `c` (na copy_allocation) e `d` (que a alocação lhe dá) — à `e` da
    # gaveta, mesmo que `e` tenha a quantidade da foto e não haja alvo no
    # config. Empate entre c e d pelo id → c, que se parte.
    res = _importar(con, "Path to Exile,pf20,2,1,foil,en,Colecção,site-modern-20260921-101500-2.jpg", "f2.csv")
    cps = copias(con)
    assert res[0]["motivo"] == "1 revalidada: foto nova", res[0]
    assert cps[c]["quantity"] == 1 and cps[d]["quantity"] == 2, "saiu de c"
    assert cps[e]["quantity"] == 1 and not cps[e]["validado_em"], "e não foi tocada"
    assert cps[res[0]["copy_id"]]["validado_em"] and cps[res[0]["copy_id"]]["photo_path"].startswith("site-modern-")
    # (C) Com `-c<d>` no nome: vai à cópia `d`, mesmo que a ordem (c, id menor,
    # e agora com a quantidade da foto) escolhesse outra.
    res = _importar(con, f"Path to Exile,pf20,2,1,foil,en,Colecção,site-modern-20260921-101500-1-c{d}.jpg", "f1.csv")
    cps = copias(con)
    assert cps[d]["quantity"] == 1, "foi à cópia d, que se partiu"
    assert cps[c]["quantity"] == 1 and not cps[c]["validado_em"] and not cps[e]["validado_em"]
    assert cps[res[0]["copy_id"]]["photo_path"].endswith(f"-c{d}.jpg"), res[0]
    # DISCREPÂNCIA pelo prefixo: a caixa do Duel Commander tem a Swords 4ED foil
    # por revalidar; a foto `site-duel-commander-…` traz uma Swords que não
    # existe igual — corrige a cópia da caixa (é o passo (0b) com o alvo do
    # nome), com linha no log.
    res = _importar(con, "Swords to Plowshares,4ed,0,1,nonfoil,en,Colecção,site-duel-commander-20260921-101500-1.jpg", "f3.csv")
    assert "corrigida" in res[0]["motivo"] and res[0]["copy_id"] == a, res[0]
    assert copias(con)[a]["finish"] == "nonfoil" and revalidacao.MARCA_CORRIGIDA in copias(con)[a]["notes"]
    # A mesma discrepância SEM prefixo e sem alvo entra como nova — é o que
    # sempre foi (só o nome da foto mudou o caminho).
    res = _importar(con, "Mother of Runes,sld,1,1,nonfoil,en,Colecção,IMG_10.jpg", "f4.csv")
    assert res[0]["motivo"] == "" and res[0]["copy_id"] != b, res[0]
    assert revalidacao.MARCA_NOVA in (copias(con)[res[0]["copy_id"]]["notes"] or "")
    # Uma caixa que já não existe no nome: só a cópia (`primeiro`) conta; nada rebenta.
    a2, _p = revalidacao.alvo_da_foto(con, "site-nao-ha-20260921-101500-1-c5.jpg", {}, None)
    assert a2 is None and _p == 5
    print("import: o nome da foto manda — a caixa do prefixo, a copia do -c<id>, e a discrepancia pelo prefixo")


def caso_as_fotos_por_resolver_saem_com_o_motivo():
    cfg_novo()
    PEND.mkdir(parents=True)
    (PEND / "site-modern-20260921-101500-1.jpg").write_bytes(imagem())
    (PEND / "IMG_7.jpg").write_bytes(imagem())
    cab = "linha,name,set_code,collector_number,quantity,sub_collection,photo_path,resultado,motivo,copy_id\n"
    (PEND / "recat-20260921-0230-resultado.csv").write_text(
        cab + "2,Path to Exile,,,1,,site-modern-20260921-101500-1.jpg,erro,edicao em falta: Path to Exile,\n"
        + "3,Brainstorm,ice,1,1,,IMG_7.jpg,importada,,12\n"
        + "4,Force of Will,all,1,1,,IMG_8.jpg,erro,nao esta no catalogo,\n", encoding="utf-8")
    # Um resultado mais recente sobre a mesma foto ganha ao antigo.
    (PEND / "recat-20260921-0900-resultado.csv").write_text(
        cab + "2,Path to Exile,pf20,2,1,,site-modern-20260921-101500-1.jpg,erro,a foto nao mostra a edicao,\n",
        encoding="utf-8")
    pr = fotosite.por_resolver(PEND)
    assert len(pr) == 1 and pr[0]["foto"] == "site-modern-20260921-101500-1.jpg", pr
    assert pr[0]["resultado"] == "recat-20260921-0900-resultado.csv"
    assert pr[0]["linhas"] == [{"name": "Path to Exile", "set_code": "pf20",
                                "motivo": "a foto nao mostra a edicao"}], pr
    # IMG_7 importou (não está por resolver); IMG_8 já não está na pasta (resolveu-se ou foi-se).
    est = fotosite.estado(PEND, INBOX)
    assert est["n"] == 2 and len(est["por_resolver"]) == 1
    print("por resolver: as linhas paradas cuja foto ainda esta em pendentes, com o motivo mais recente")


def caso_a_pagina_nos_dois_modos():
    cfg_novo(alvo={"tipo": "venda", "slot": None, "em": "2026-09-21"})
    con = base()
    a, b, c, d = mundo(con)
    # Uma 5.ª Path (excedente → venda) e uma Brainstorm que nenhum deck pede
    # (→ Colecção, o resto): para a venda e a colecção terem o que fotografar.
    copia(con, "Path to Exile", "pf20", q=1)
    copia(con, "Brainstorm", "ice", q=1, finish="nonfoil")
    PEND.mkdir(parents=True)
    (PEND / "site-modern-20260921-101500-1.jpg").write_bytes(imagem())
    (PEND / f"site-duel-commander-20260921-101500-1-c{a}.jpg").write_bytes(imagem())
    (PEND / "IMG_7.jpg").write_bytes(imagem())
    cab = "linha,name,set_code,collector_number,quantity,sub_collection,photo_path,resultado,motivo,copy_id\n"
    (PEND / "recat-20260921-0230-resultado.csv").write_text(
        cab + "2,Path to Exile,,,1,,IMG_7.jpg,erro,edicao em falta: Path to Exile,\n", encoding="utf-8")
    INBOX.mkdir(parents=True)
    (INBOX / "mtgvault-fotos-20260921-101600.json").write_text(
        json.dumps({"kind": "command", "nao_antes": "2026-09-21 10:18:45"}), encoding="utf-8")
    rep = loadout.report(con)
    for editable in (False, True):
        d_ = deckboxes.payload(con, rep, editable=editable)
        S = d_["revalidacao"]["site"]
        assert S["n"] == 3 and len(S["por_resolver"]) == 1 and S["processar"]["pendente"]
        idx, partes = deckboxes.partir(d_)
        assert idx["revalidacao"]["site"]["n"] == 3 and "enviadas" not in idx["revalidacao"]["site"]
        assert deckboxes.juntar(idx, partes) == d_
        html = deckboxes.html_page(con, editable=editable, rep=rep)
        pagina = _TMP / f"fs-{int(editable)}.html"
        pagina.write_text(html, encoding="utf-8")
        if not shutil.which("node"):
            print("  (sem node: o render não foi verificado)")
            continue
        dump = _TMP / f"fs-abas-{int(editable)}.json"
        p = subprocess.run(["node", str(RAIZ / "tests" / "render_deckboxes.js"),
                            str(pagina), str(dump)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
        assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
        abas = json.loads(dump.read_text(encoding="utf-8"))
        # A aba da caixa: «Tirar fotos» (várias) e o 📷 por cópia — só no 8771;
        # a lista das fotos desta caixa «à espera» nos dois modos.
        aba = abas["duel-commander"]
        assert ('data-foto-site="caixa" data-slot="duel-commander"' in aba) is editable, aba[:800]
        assert ("📷 Tirar fotos" in aba) is editable
        assert ('capture="environment" multiple' in aba) is editable
        assert (f'data-copy="{a}" aria-label="Tirar foto"' in aba) is editable, "o 📷 da cópia"
        assert f"site-duel-commander-20260921-101500-1-c{a}.jpg" in aba and f"cópia #{a}" in aba
        assert "Fotos enviadas, à espera" in aba and "site-modern-" not in aba, "só as desta caixa"
        assert "Já está a processar" in aba and "10:18" in aba, "a ordem pendente diz-se nos dois modos"
        assert ("data-processar=" in aba) is False, "com uma ordem pendente não há botão"
        assert ("📷 Fotografar esta caixa" in aba) is editable, "o botão do alvo (20/09) fica"
        # No modo Lista o 📷 por cópia também lá está.
        lista = abas["lista:duel-commander"]
        assert (f'data-copy="{a}" aria-label="Tirar foto"' in lista) is editable
        # A aba Revalidação: todas as fotos à espera com a origem, as por
        # resolver com o motivo, o «Tirar fotos» do alvo (venda) e por grupo.
        rv = abas["revalidacao"]
        assert "Fotos enviadas, à espera" in rv and "site-modern-20260921-101500-1.jpg" in rv
        assert "Modern — UW Oswald" in rv and "largada à mão" in rv, rv[:1500]
        # (o ⚠ passou a ícone SVG na 2.ª passagem de 2026-09-24)
        assert "Fotos por resolver" in rv and "edicao em falta: Path to Exile" in rv and "IMG_7.jpg" in rv
        assert ('data-foto-site="venda"' in rv) is editable
        assert ('data-foto-site="coleccao"' in rv) is editable
        assert ("blocos de escrita (editavel=" in p.stdout), p.stdout
    # Sem ordem pendente, no 8771, há o botão «Processar agora».
    shutil.rmtree(INBOX)
    if shutil.which("node"):
        html = deckboxes.html_page(con, editable=True, rep=rep)
        pagina = _TMP / "fs-2.html"
        pagina.write_text(html, encoding="utf-8")
        dump = _TMP / "fs-abas-2.json"
        p = subprocess.run(["node", str(RAIZ / "tests" / "render_deckboxes.js"),
                            str(pagina), str(dump)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
        assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
        abas = json.loads(dump.read_text(encoding="utf-8"))
        assert 'data-processar="1"' in abas["revalidacao"] and "⚡ Processar agora" in abas["duel-commander"]
    print("pagina: Tirar fotos, 📷 por copia e Processar agora so no 8771; a espera e por resolver nos dois")


def caso_nenhum_numero_muda():
    cfg_novo()
    con = base()
    mundo(con)
    antes = numeros(loadout.report(con))
    PEND.mkdir(parents=True)
    fotosite.guardar(PEND, "caixa", [{"nome": "a.jpg", "dados": imagem()}], slot="modern", quando=Q)
    fotosite.guardar(PEND, "venda", [{"nome": "b.jpg", "dados": imagem()}], quando=Q)
    fotosite.pedir_processamento(PEND, INBOX, agora=Q)
    depois = numeros(loadout.report(con))
    assert antes == depois, (antes, depois)
    assert antes["caixas"] == [("duel-commander", 100, 2, 0), ("modern", 100, 4, 0)], antes
    print("nenhum numero da alocacao ou da venda muda com as fotos enviadas nem com a ordem")


def run():
    for fn in (caso_o_nome_diz_a_origem_e_le_se_de_volta,
               caso_multipart_e_guardar_inteira_sem_reduzir,
               caso_o_endpoint_grava_com_token_e_recusa_sem,
               caso_processar_agora_escreve_a_ordem_e_limita,
               caso_o_import_prefere_a_caixa_e_a_copia_do_nome,
               caso_as_fotos_por_resolver_saem_com_o_motivo,
               caso_a_pagina_nos_dois_modos,
               caso_nenhum_numero_muda):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
