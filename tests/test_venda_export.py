"""A SAÍDA da lista de venda (2026-09-18): o CSV de stock e a lista da estante.

O que aqui se tranca:

  1. **o CSV predefinido** tem uma linha por CÓPIA (não por linha da página),
     com nome, edição, número, língua, acabamento, ESTADO da cópia, quantidade,
     preço de referência e comentário — e o estado vem da `copies`, por isso
     dois lotes da mesma impressão em estados diferentes são duas linhas;
  2. **o formato APRENDE com o ficheiro dele**: com um
     `data/cardmarket-stock-exemplo.csv` a exportação sai com o cabeçalho, o
     delimitador e o vocabulário desse ficheiro (foil `1`/`0`, língua por id,
     decimal com vírgula), com as colunas desconhecidas vazias na posição
     delas — e sem o ficheiro volta ao predefinido, dito como não confirmado;
  3. **a lista da estante** agrupa por ONDE a cópia está (Colecção, Caixa RL
     PT/EN) e ordena por cor dentro do grupo, com totais por grupo que somam o
     total;
  4. **o que não se vende fica de fora e diz porquê**: `rl_segurar`,
     `rl_sem_historico`, `guardar`, `reservadas` e `retidos` não entram no CSV
     nem na estante, e a secção "fora" traz o motivo por linha — com a
     percentagem e a janela, no caso da RL;
  5. **o `exportar` escreve os dois ficheiros** em `data/` (e são reescritos,
     não acumulados), o `daily` chama-o, o `webapp` tem o endpoint, a página
     desenha a secção, e o `.gitignore` apanha os dois ficheiros.

Cada caso chumba se a tarefa não fizer nada: lê-se o ficheiro escrito, o HTML
que o JavaScript desenhou e a resposta do handler, não o código de saída.
Não toca na rede.
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {"Blue Farm": {"reter_extras": True}},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"}],
    "caixas": [
        {"slot": "leg", "nome": "Leg", "formato": "legacy", "fonte": "deck",
         "ref": "Leg", "balde": "Colecção", "estado": "permanente",
         "prioridade": 1}],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout, prices, venda  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# O `webapp` regenera as páginas no `webapp.ROOT` — a raiz do repositório.
# Apontado aqui, logo no import, como nos outros testes do modo edição.
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

HOJE = date.today()
# (nome, edição, número, reserved, cor, tipo, cardmarket_id)
CATALOGO = [
    ("Sol Ring", "c21", "263", 0, "", "Artifact", 12345),
    ("Swords to Plowshares", "4ed", "51", 0, "W", "Instant", None),
    ("Dark Ritual", "4ed", "129", 0, "B", "Instant", 777),
    ("Gilded Drake", "usg", "78", 1, "U", "Creature", 999),
    ("Null Rod", "wth", "150", 1, "", "Artifact", 888),
    ("Brainstorm", "ice", "61", 0, "U", "Instant", 555),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, num, rl, ci, tl, cmid) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, cardmarket_id)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,?,?,'1995-04-01',?,0,?,?)""",
            (f"id-{i}", f"or-{i}", nm, sc, f"Set {sc.upper()}", num, tl, ci,
             json.dumps(["nonfoil", "foil"]),
             json.dumps({"legacy": "legal", "commander": "legal"}), rl, cmid))
        con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date,
                       trend) VALUES (?,'cardmarket','nonfoil',?,?)""",
                    (f"id-{i}", HOJE.isoformat(), 2.0 + i))
    # A caixa de Legacy pede 1 Brainstorm foil EN — para haver um SUBSTITUTO
    # (a nonfoil serve o deck e só falha no acabamento -> `guardar`).
    con.execute("INSERT INTO decks (name, format) VALUES ('Leg','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name='Leg'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Brainstorm', 1, 'main')", (did,))
    for sub in ("Colecção", "Caixa Reserved List", "Blue Farm"):
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
    con.commit()
    return con


def add(con, nm, q=1, sub="Colecção", lang="en", finish="nonfoil", cond="NM"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    cur = con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                         condition, purpose, sub_collection_id)
                         VALUES (?,?,?,?,?,'player',?)""",
                      (sid, q, finish, lang, cond, sub_id))
    con.commit()
    return cur.lastrowid


def cota(con, nm, quando, valor):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    prices.write_prices(con, [(sid, "cardmarket", quando, "nonfoil",
                               valor, valor, None, None, "EUR")])


def mundo():
    """A colecção do teste, com uma cópia em cada saída da venda:

      * 6 Sol Ring na Colecção, 4 NM + 2 EX (lotes separados)  -> venda (2 EX)
      * 6 Swords to Plowshares (4 NM + 2 LP)                    -> venda (2 LP)
      * 5 Null Rod EN na Caixa RL, preço parado                 -> venda_rl (1)
      * 6 Gilded Drake, +50 % em 90 dias                         -> rl_segurar (2)
      * 5 Dark Ritual no Blue Farm (balde com reter_extras)      -> retidos (1)
      * 5 Brainstorm nonfoil: a caixa pede 1 foil               -> guardar (1)
    """
    con = base()
    add(con, "Sol Ring", 4, cond="NM")
    add(con, "Sol Ring", 2, cond="EX")
    add(con, "Swords to Plowshares", 4, cond="NM")
    add(con, "Swords to Plowshares", 2, cond="LP")
    add(con, "Null Rod", 5, sub="Caixa Reserved List")
    cota(con, "Null Rod", (HOJE - timedelta(days=90)).isoformat(), 6.0)
    cota(con, "Null Rod", HOJE.isoformat(), 6.0)
    add(con, "Gilded Drake", 6, sub="Caixa Reserved List", lang="pt")
    cota(con, "Gilded Drake", (HOJE - timedelta(days=90)).isoformat(), 5.0)
    cota(con, "Gilded Drake", HOJE.isoformat(), 7.5)
    add(con, "Dark Ritual", 5, sub="Blue Farm")
    add(con, "Brainstorm", 5)
    return con


def _rep(con):
    rep = loadout.report(con)
    # A premissa do teste — cada saída tem o que a docstring do `mundo` diz.
    por = {k: {r["nm"]: r["q"] for r in rep[k]}
           for k in ("venda", "venda_rl", "rl_segurar", "guardar", "retidos")}
    assert por["venda"] == {"Sol Ring": 2, "Swords to Plowshares": 2}, por
    assert por["venda_rl"] == {"Null Rod": 1}, por
    assert por["rl_segurar"] == {"Gilded Drake": 2}, por
    assert por["guardar"] == {"Brainstorm": 1}, por
    assert por["retidos"] == {"Dark Ritual": 1}, por
    return rep


# ---------------------------------------------------------------------------
def caso_csv_predefinido_uma_linha_por_copia_com_estado():
    con = mundo()
    rep = _rep(con)
    linhas = venda.linhas_export(con, rep)
    # 5 cópias em 3 lotes: 2 Sol Ring EX, 2 Swords LP, 1 Null Rod NM. As 4 NM
    # de cada uma são o playset e ficam em casa — é o lote em PIOR ESTADO que
    # vai à venda (`loadout.ordem_estado`; antes desempatava pelo `id` e
    # vendia 2 das NM, com a lista de stock a dizer NM de uma cópia EX).
    assert sum(l["q"] for l in linhas) == 5, linhas
    por = {(l["nm"], l["cond"]): l["q"] for l in linhas}
    assert por == {("Sol Ring", "EX"): 2, ("Swords to Plowshares", "LP"): 2,
                   ("Null Rod", "NM"): 1}, por
    nr = next(l for l in linhas if l["nm"] == "Null Rod")
    assert nr["set"] == "WTH" and nr["num"] == "150" and nr["cm_id"] == 888, nr
    assert nr["rl"] is True and nr["local"] == "Caixa RL (EN)", nr
    assert nr["comment"] == f"mtgvault #{nr['copy_id']} · Caixa RL (EN)", nr

    texto = venda.csv_stock(linhas)
    rows = list(__import__("csv").reader(io.StringIO(texto)))
    assert rows[0] == list(venda.COLUNAS_PREDEFINIDAS), rows[0]
    assert len(rows) == 4, rows
    sr = next(r for r in rows[1:] if r[0] == "Sol Ring")
    assert sr == ["Sol Ring", "C21", "263", "English", "nonfoil", "EX", "2",
                  "2.00", sr[8]], sr
    assert sr[8].startswith("mtgvault #"), sr
    # E o formato diz-se NÃO confirmado — é a parte honesta do predefinido.
    f = venda.descricao_formato(None)
    assert f["origem"] == "predefinido" and f["confirmado"] is False
    assert "NÃO confirmado" in f["nota"], f["nota"]
    print("CSV predefinido: uma linha por copia, com o estado da copia, e dito "
          "como nao confirmado")


def caso_o_formato_aprende_com_o_ficheiro_dele():
    """Com o `cardmarket-stock-exemplo.csv` a exportação sai NA FORMA DELE."""
    con = mundo()
    rep = _rep(con)
    linhas = venda.linhas_export(con, rep)
    exemplo = Path(tempfile.mkdtemp()) / "cardmarket-stock-exemplo.csv"
    # Um ficheiro como um "descarregar stock" europeu: `;`, BOM, CRLF, uma
    # coluna que não sabemos preencher (Rarity), foil como 1/0, língua por id,
    # preço com vírgula, e o idProduct à cabeça.
    exemplo.write_bytes(
        "﻿idProduct;Name;Expansion;Rarity;Language;Foil;Condition;Amount;"
        "Price;Comment\r\n"
        "111;Lightning Bolt;Fourth Edition;Common;1;0;NM;3;0,25;\r\n"
        "222;Force of Will;Alliances;Uncommon;8;1;EX;1;60,00;jogada\r\n"
        .encode("utf-8"))
    fmt = venda.formato_exemplo(exemplo)
    assert fmt["delimitador"] == ";" and fmt["bom"] is True, fmt
    assert fmt["fim_de_linha"] == "\r\n"
    assert fmt["mapa"] == {"idProduct": "cm_id", "Name": "nm",
                           "Expansion": "set_name", "Rarity": None,
                           "Language": "lang", "Foil": "foil", "Condition": "cond",
                           "Amount": "q", "Price": "price", "Comment": "comment"}, \
        fmt["mapa"]
    assert fmt["vocabulario"] == {"foil": "01", "lang": "id", "decimal": ","}, \
        fmt["vocabulario"]

    texto = venda.csv_stock(linhas, fmt)
    assert texto.startswith("﻿idProduct;Name;Expansion;Rarity;"), texto[:80]
    rows = list(__import__("csv").reader(io.StringIO(texto.lstrip("﻿")),
                                         delimiter=";"))
    assert rows[0] == fmt["colunas"]
    nr = next(r for r in rows[1:] if r[1] == "Null Rod")
    #        id     nome        expansão    rar  lang foil cond  q    preço
    assert nr[:9] == ["888", "Null Rod", "Set WTH", "", "1", "0", "NM", "1",
                      "6,00"], nr
    assert nr[9].startswith("mtgvault #"), nr
    # A Rarity ficou vazia na posição dela; nenhuma coluna foi inventada.
    assert all(len(r) == 10 for r in rows), [len(r) for r in rows]
    assert "\r\n" in texto
    f = venda.descricao_formato(fmt)
    assert f["origem"] == "exemplo" and f["vazias"] == ["Rarity"], f
    assert "aprendido" in f["nota"] and "Rarity" in f["nota"], f["nota"]

    # E o outro vocabulário: sem linhas de exemplo, o cabeçalho manda e os
    # valores ficam nos predefinidos (nome da língua, "foil"/"nonfoil").
    so_cab = exemplo.with_name("so-cabecalho.csv")
    so_cab.write_text("Card Name,Set Code,Collector Number,Lang,Is Foil,Qty\n",
                      encoding="utf-8")
    fmt2 = venda.formato_exemplo(so_cab)
    assert fmt2["delimitador"] == "," and fmt2["bom"] is False
    assert [fmt2["mapa"][c] for c in fmt2["colunas"]] == \
        ["nm", "set", "num", "lang", "foil", "q"], fmt2["mapa"]
    rows2 = list(__import__("csv").reader(io.StringIO(venda.csv_stock(linhas, fmt2))))
    nr2 = next(r for r in rows2[1:] if r[0] == "Null Rod")
    assert nr2 == ["Null Rod", "WTH", "150", "English", "nonfoil", "1"], nr2
    # Sem ficheiro nenhum: `None`, e o `relatorio` cai no predefinido.
    assert venda.formato_exemplo(exemplo.with_name("nao-existe.csv")) is None
    r = venda.relatorio(con, rep, exemplo=exemplo.with_name("nao-existe.csv"))
    assert r["formato"]["origem"] == "predefinido"
    r2 = venda.relatorio(con, rep, exemplo=exemplo)
    assert r2["formato"]["origem"] == "exemplo" and r2["csv"] == texto
    print("o formato aprende com o ficheiro dele: cabecalho, delimitador, BOM, "
          "CRLF e vocabulario; sem ficheiro volta ao predefinido")


def caso_a_estante_agrupa_por_onde_esta_e_ordena_por_cor():
    con = mundo()
    rep = _rep(con)
    est = venda.lista_estante(con, rep)
    assert [g["local"] for g in est["grupos"]] == ["Colecção", "Caixa RL (EN)"], \
        [g["local"] for g in est["grupos"]]
    col = est["grupos"][0]
    # Por COR dentro do grupo: a Swords (W) antes do Sol Ring (incolor), embora
    # o Sol Ring venha primeiro por nome e por valor.
    assert [l["nm"] for l in col["linhas"]] == ["Swords to Plowshares", "Sol Ring"]
    assert [l["cor"] for l in col["linhas"]] == ["W", "C"], col["linhas"]
    assert col["copias"] == 4 and est["grupos"][1]["copias"] == 1
    # Os totais por grupo somam o total, ao cêntimo.
    assert round(sum(g["total"] for g in est["grupos"]), 2) == est["total"]
    assert est["copias"] == 5 and est["rl_copias"] == 1, est
    txt = venda.texto_estante(est, "2026-09-18")
    assert txt.startswith("VENDA — ir buscar à estante (2026-09-18)\n5 cópias"), txt
    assert "■ Colecção — 4 cópias" in txt and "■ Caixa RL (EN) — 1 cópia ·" in txt, txt
    assert "[W] 2× Swords to Plowshares · 4ED EN nonfoil LP" in txt, txt
    assert "1× Null Rod (RL) · WTH EN nonfoil NM" in txt, txt
    assert txt.index("Swords to Plowshares") < txt.index("Sol Ring"), txt
    print("a estante agrupa por onde a copia esta, por cor dentro do grupo, "
          "com totais que somam")


def caso_o_que_nao_se_vende_fica_de_fora_e_diz_porque():
    con = mundo()
    rep = _rep(con)
    r = venda.relatorio(con, rep)
    nomes_csv = {l["nm"] for l in r["linhas"]}
    assert nomes_csv == {"Sol Ring", "Swords to Plowshares", "Null Rod"}, nomes_csv
    for fora in ("Gilded Drake", "Dark Ritual", "Brainstorm"):
        assert fora not in r["csv"], fora
        assert fora not in r["texto_estante"], fora
    fora = {f["chave"]: f for f in r["fora"]}
    assert set(fora) == {"rl_segurar", "rl_sem_historico", "guardar",
                         "reservadas", "retidos"}, set(fora)
    seg = fora["rl_segurar"]
    assert seg["copias"] == 2 and seg["linhas"][0]["nm"] == "Gilded Drake", seg
    # A percentagem e a janela, e o motivo por que ia à venda.
    assert "+50.0 % em 88 d" in seg["linhas"][0]["motivo"], seg["linhas"][0]
    assert "(ia por: excedente (mais de 4))" in seg["linhas"][0]["motivo"]
    assert fora["retidos"]["linhas"][0]["nm"] == "Dark Ritual"
    assert "sem prazo" in fora["retidos"]["linhas"][0]["motivo"]
    assert fora["guardar"]["linhas"][0]["nm"] == "Brainstorm"
    assert "serve" in fora["guardar"]["linhas"][0]["motivo"]
    assert fora["rl_sem_historico"]["copias"] == 0 and fora["reservadas"]["copias"] == 0
    # E cada saída tem um "porquê" geral, para a página o dizer sem inventar.
    assert all(f["porque"] for f in r["fora"])
    print("o que nao se vende fica fora do CSV e da estante, e a seccao 'fora' "
          "diz o motivo por linha")


def caso_exportar_escreve_os_dois_ficheiros_e_reescreve():
    con = mundo()
    rep = _rep(con)
    pasta = Path(tempfile.mkdtemp()) / "data"
    res = venda.exportar(con, rep, pasta=pasta,
                         exemplo=pasta / "nao-existe.csv")
    stock, est = Path(res["csv"]), Path(res["estante"])
    assert stock.name == "venda-stock.csv" and est.name == "venda-estante.txt"
    assert stock.parent == pasta and stock.is_file() and est.is_file()
    assert res["copias"] == 5 and res["linhas"] == 3 and res["fora"] == 4, res
    assert res["formato"] == "predefinido"
    assert "5 cópias" in res["resumo"] and "predefinido" in res["resumo"], res
    csv_txt = stock.read_text(encoding="utf-8")
    assert csv_txt.splitlines()[0] == ",".join(venda.COLUNAS_PREDEFINIDAS)
    assert "Null Rod" in csv_txt and "Gilded Drake" not in csv_txt
    assert "■ Colecção" in est.read_text(encoding="utf-8")
    # REESCRITO, não acumulado: vende-se o Null Rod e o ficheiro deixa de o ter.
    linha = next(x for x in rep["venda_rl"] if x["nm"] == "Null Rod")
    loadout.registar_venda(con, linha, csv_path=pasta / "vendas.csv")
    res2 = venda.exportar(con, pasta=pasta, exemplo=pasta / "nao-existe.csv")
    assert res2["copias"] == 4, res2
    assert "Null Rod" not in stock.read_text(encoding="utf-8")
    assert not list(pasta.glob("*.tmp")), list(pasta.iterdir())
    # E é `exportar(con)` sem `rep` que o daily pode chamar: calcula o relatório.
    print("exportar escreve venda-stock.csv + venda-estante.txt e reescreve-os")


def caso_o_daily_e_o_gitignore_conhecem_os_ficheiros():
    """O passo existe no `daily.py` e os ficheiros (com preços) não vão ao Git."""
    src = (RAIZ / "daily.py").read_text(encoding="utf-8")
    assert re.search(r'_step\(con,\s*"venda-export"', src), \
        "o daily.py tem de ter o passo venda-export"
    assert "venda.exportar(" in src, "e o passo tem de chamar venda.exportar"
    ign = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    for f in (venda.FICHEIRO_STOCK, venda.FICHEIRO_ESTANTE):
        assert f"data/{f}" in ign, f"data/{f} tem de estar no .gitignore"
    # O exemplo dele TAMBÉM fica fora: é uma exportação da conta, com preços.
    assert f"data/{venda.FICHEIRO_EXEMPLO}" in ign
    p = subprocess.run(["git", "-C", str(RAIZ), "check-ignore", "-q",
                        f"data/{venda.FICHEIRO_STOCK}"], capture_output=True)
    assert p.returncode == 0, "o git tem de ignorar data/venda-stock.csv"
    # E o CLAUDE.md diz que o formato NÃO foi confirmado.
    doc = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    assert "cardmarket-stock-exemplo.csv" in doc and "NÃO foi confirmado" in doc
    print("o daily tem o passo, o .gitignore apanha os ficheiros, o CLAUDE.md "
          "diz que o formato nao foi confirmado")


# ---------------------------------------------------------------------------
# A página e o modo edição
# ---------------------------------------------------------------------------
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


def _apontar(con):
    """O `do_GET`/`do_POST` abrem a sua própria ligação: apontam-se as variáveis
    de ambiente para ESTA base, para o teste não ir à do André."""
    ficheiros = con.execute("PRAGMA database_list").fetchall()
    os.environ["MTGVAULT_DB"] = str(Path(ficheiros[0]["file"]))
    os.environ["MTGVAULT_CATALOG"] = str(Path(ficheiros[1]["file"]))
    # O `db` fixa os caminhos no import; o handler abre `db.session()` sem
    # argumentos, por isso é aqui que se lhe diz que base é.
    db.DEFAULT_DB = Path(ficheiros[0]["file"])
    db.DEFAULT_CATALOG = Path(ficheiros[1]["file"])
    webapp._CACHE.clear()


def _abas_desenhadas(pagina):
    import shutil
    if not shutil.which("node"):
        return None
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(pagina), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def caso_a_aba_vender_leva_a_saida_e_o_modo_edicao_grava():
    con = mundo()
    rep = _rep(con)
    d = deckboxes.payload(con, rep)
    s = d["venda"]["saida"]
    assert s["copias"] == 5 and s["formato"]["origem"] == "predefinido", s
    assert s["csv"].startswith("Name,Set,Number") and "Null Rod" in s["csv"]
    assert [g["local"] for g in s["estante"]["grupos"]] == ["Colecção", "Caixa RL (EN)"]
    assert {f["chave"] for f in s["fora"]} == {"rl_segurar", "rl_sem_historico",
                                               "guardar", "reservadas", "retidos"}
    # A parte pesada da venda leva a saída (é lá que a aba a vai buscar).
    idx, partes = deckboxes.partir(d)
    assert partes["venda"]["saida"]["copias"] == 5
    assert "saida" in idx["venda"] and "csv" not in idx["venda"]["saida"], \
        "o índice leva só os totais, o CSV vai na parte"

    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    out.write_text(deckboxes.html_page(con, rep=rep), encoding="utf-8")
    abas = _abas_desenhadas(out)
    if abas is not None:
        v = abas["vender"]
        assert "Saída" in v and "venda-stock-" in v, v[:800]
        assert "NÃO confirmado" in v, "a página tem de dizer que o formato não foi confirmado"
        assert "Ir buscar à estante" in v and "Caixa RL (EN)" in v, v[:800]
        assert "Fica de fora" in v and "+50.0 % em 88 d" in v, v[:800]
        # A lista da estante desenha-se ANTES da tabela do excedente, com a
        # Swords antes do Sol Ring (cor) dentro da Colecção.
        est = v[v.index("Ir buscar à estante"):v.index("Excedente normal")]
        assert est.index("Swords to Plowshares") < est.index("Sol Ring"), est[:600]
        # No site publicado: copiar e descarregar, mas NUNCA o botão de gravar.
        assert 'data-cmk="csv"' in v and "id=\"saida-csv\"" in v, v[:800]
        assert "gravar em data/" not in v
        print("a aba Vender desenha a saida (CSV, estante, fora) sem botao de gravar")

    # O modo edição: `POST /api/venda-export` grava em `data/` — com token.
    _apontar(con)
    pasta = Path(db.pasta_dados())
    for f in (venda.FICHEIRO_STOCK, venda.FICHEIRO_ESTANTE):
        (pasta / f).unlink(missing_ok=True)
    p = Pedido("/api/venda-export", "{}")
    p.do_POST()
    assert p.codigo == 403 and not (pasta / venda.FICHEIRO_STOCK).exists(), \
        (p.codigo, p.corpo)
    p = Pedido("/api/venda-export", "{}", token=webapp.token())
    p.do_POST()
    assert p.codigo == 200, (p.codigo, p.corpo)
    j = json.loads(p.corpo)
    assert j.get("ok") and j["copias"] == 5 and "venda-stock.csv" in j["msg"], j
    assert (pasta / venda.FICHEIRO_STOCK).is_file(), list(pasta.iterdir())
    assert "Null Rod" in (pasta / venda.FICHEIRO_STOCK).read_text(encoding="utf-8")
    # E os dados do modo edição desenham o botão de gravar.
    p = Pedido(f"/data/paginas/deckboxes/venda.json?t={webapp.token()}")
    p.do_GET()
    assert p.codigo == 200 and json.loads(p.corpo)["saida"]["copias"] == 5
    if abas is not None:
        p = Pedido(f"/data/paginas/deckboxes.json?t={webapp.token()}")
        p.do_GET()
        idx = json.loads(p.corpo)
        p = Pedido(f"/data/paginas/deckboxes/venda.json?t={webapp.token()}")
        p.do_GET()
        partes = {"venda": json.loads(p.corpo)}
        for c in idx["caixas"]:
            q = Pedido(f"/data/paginas/deckboxes/{c['parte']}.json?t={webapp.token()}")
            q.do_GET()
            partes[c["parte"]] = json.loads(q.corpo)
        for nome in ("arrumar", "compras", "premodern"):
            q = Pedido(f"/data/paginas/deckboxes/{nome}.json?t={webapp.token()}")
            q.do_GET()
            partes[nome] = json.loads(q.corpo)
        out2 = out.with_name("edicao.html")
        out2.write_text(deckboxes._html(deckboxes.juntar(idx, partes)),
                        encoding="utf-8")
        v2 = _abas_desenhadas(out2)["vender"]
        assert "gravar em data/" in v2 and 'data-saida="gravar"' in v2, v2[:800]
        print("no modo edicao a aba tem o botao de gravar, e o POST escreve o ficheiro")
    print("o endpoint exige token e grava os dois ficheiros em data/")


def run():
    for fn in (caso_csv_predefinido_uma_linha_por_copia_com_estado,
               caso_o_formato_aprende_com_o_ficheiro_dele,
               caso_a_estante_agrupa_por_onde_esta_e_ordena_por_cor,
               caso_o_que_nao_se_vende_fica_de_fora_e_diz_porque,
               caso_exportar_escreve_os_dois_ficheiros_e_reescreve,
               caso_o_daily_e_o_gitignore_conhecem_os_ficheiros,
               caso_a_aba_vender_leva_a_saida_e_o_modo_edicao_grava):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
