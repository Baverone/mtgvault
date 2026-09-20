"""AS CARTAS EM IMAGEM (André, 2026-09-20, à letra): *"cada deck poderia ter as
cartas visualmente ao invés de só o nome?"* — e a regra geral dele, de 16/09:
*"gosto de ter em imagem da carta e não apenas texto, faz algo visualmente
apelativo"*.

O que aqui se tranca (`deckboxes.py`, JS `tileHTML`/`grelhaHTML`, e o `sid`
que o Python passou a dar por cópia):

  1. **cada secção desenha tiles com imagem e o estado certo** — a grelha da
     caixa, o passo 1 (com a checkbox e o MESMO `data-id` por que a barra
     conta), as básicas, a wantlist (com o preço e os botões `+`/`−`/«já a
     tenho»), a Reserva, a Revalidação (📷/✓), as Encomendas (a caminho /
     pendente de foto), a aba Vender (com o «vendida»), a estante, a Feira
     (com o «levo») e o Arrumar (com a checkbox);
  2. **a imagem é a da impressão exacta** que ele tem (o `sid` da cópia), e
     para o que falta a da impressão mais barata no acabamento da compra;
  3. **o interruptor «Imagens / Lista»** volta à lista de antes de 20/09 —
     no aparelho (`P.imagens`) e, no modo edição, no config (`api/vista`);
  4. **os botões dentro dos tiles fazem os mesmos pedidos** de antes;
  5. **sem `sid` fica o nome no quadrado**, nunca um buraco, e cada `<img>`
     tem `onerror`, `loading="lazy"` e o tamanho escrito;
  6. **as grelhas grandes vêm aos poucos** (tecto por aba + «mostrar as
     outras N») só nas abas sem procura;
  7. **nenhum número da alocação, da venda ou da feira muda** — o payload
     não toca no relatório;
  8. o CSS: 3 colunas a 640 px, checkbox ≥ 28 px, `aspect-ratio` fixo.

Não abre socket para fora nem toca na `vault.db` a sério.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {}, "decks_vigiados": [],
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "regras_por_formato": [
        {"grupo": "duel-commander", "formatos": ["duel-commander"],
         "dedicado": True, "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "dc", "nome": "Cloud (DC)", "formato": "duel-commander",
         "fonte": "deck", "ref": "Cloud (DC)", "balde": "Cloud",
         "estado": "permanente", "prioridade": 1, "notas": "",
         "reserva": ["Winter Moon"]},
    ],
    "revalidacao": {"desde": "2026-09-20"},
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import configio, db, encomendas, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"           # nunca o repositório
webapp.ROOT.mkdir(exist_ok=True)

# (nome, edição, data, reserved, preço nonfoil, preço foil). A Path to Exile tem
# DUAS impressões, a mais barata em foil é a `pf20` — é essa a imagem da compra.
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 0, 1.0, 5.0),
    ("Mother of Runes", "sld", "2022-01-01", 0, 2.0, 6.0),
    ("Path to Exile", "pf20", "2020-01-01", 0, 3.0, 9.0),
    ("Path to Exile", "con", "2009-02-06", 0, 4.0, 30.0),
    ("Get Lost", "lci", "2023-11-17", 0, 4.0, 8.0),
    ("Winter Moon", "ltr", "2023-06-23", 0, 10.0, 20.0),
    ("City of Traitors", "exo", "1998-06-15", 1, 100.0, 100.0),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, rl, p_n, p_f) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               image_uri)
               VALUES (?,?,?,?,'S',?,'en','rare','Instant',1,?,?,?,?,0,?,?)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), "U" if nm == "Winter Moon" else "W",
             json.dumps(["nonfoil", "foil"]), rel,
             json.dumps({"commander": "legal", "duel": "legal"}), rl,
             f"https://cards.scryfall.io/normal/front/i/d/id-{i}.jpg"))
        for fin, preco in (("nonfoil", p_n), ("foil", p_f)):
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-19', ?)", (f"id-{i}", fin, preco))
            for dia in ("2026-06-01", "2026-09-19"):
                con.execute("INSERT OR REPLACE INTO price_history (scryfall_id, "
                            "source, date, finish, trend) VALUES (?, 'cardmarket', "
                            "?, ?, ?)", (f"id-{i}", dia, fin, preco))
    con.execute("INSERT OR IGNORE INTO decks (name, format) VALUES ('Cloud (DC)', 'duel-commander')")
    did = con.execute("SELECT id FROM decks WHERE name = 'Cloud (DC)'").fetchone()["id"]
    # A Carta Inventada não está no catálogo: é o tile sem imagem.
    for nm, q in (("Swords to Plowshares", 1), ("Mother of Runes", 1),
                  ("Path to Exile", 2), ("Carta Inventada", 1)):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.commit()
    return con


def add(con, nm, q=1, finish="nonfoil", lang="en", sub="Colecção", validado=None,
        set_code=None):
    i = next(k for k, c in enumerate(CATALOGO)
             if c[0] == nm and (set_code is None or c[1] == set_code))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, 'player')",
                (sub,))
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?", (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language, purpose,
                   sub_collection_id, validado_em, photo_path)
                   VALUES (?,?,?,?,'player',?,?,?)""",
                (f"id-{i}", q, finish, lang, sub_id, validado,
                 "fotos/x.jpg" if validado else None))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def coleccao():
    """Tem a Swords foil (fecha), a Mother nonfoil (substituto — a caixa quer
    foil), 6 Get Lost foil (2 para a venda, 4 validadas), 1 Winter Moon (a
    reserva), 5 City of Traitors RL; falta a Path (compra, 2 impressões) e a
    Carta Inventada (sem catálogo). E uma encomenda a caminho de Path."""
    con = base()
    add(con, "Swords to Plowshares", 1, finish="foil")
    add(con, "Mother of Runes", 1, finish="nonfoil")
    add(con, "Get Lost", 4, finish="foil", validado="2026-09-20")
    add(con, "Get Lost", 2, finish="foil")
    add(con, "Winter Moon", 1, finish="nonfoil")
    add(con, "City of Traitors", 5, finish="nonfoil", sub="Caixa Reserved List")
    encomendas.adicionar(con, "dc", "Path to Exile", 1, origem="loja X",
                         log_path=_TMP / "enc.log")
    con.commit()
    return con


_PAGINA = {}


def pagina(editable=True):
    if editable not in _PAGINA:
        con = coleccao()
        p = Path(tempfile.mkdtemp()) / "deckboxes.html"
        p.write_text(deckboxes.html_page(con, editable=editable), encoding="utf-8")
        _PAGINA[editable] = p
    return _PAGINA[editable]


def avaliar(js, editable=True):
    if not shutil.which("node"):
        return None
    t = Path(tempfile.mkdtemp()) / "teste.js"
    t.write_text(js, encoding="utf-8")
    p = subprocess.run(["node", str(Path(__file__).with_name("avaliar_js.js")),
                        str(pagina(editable)), str(t)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
    return json.loads(p.stdout)


_ABAS = {}


def abas(editable=True):
    """`{aba: html}` nos dois modos: `<aba>` em imagens, `lista:<aba>` em lista."""
    if not shutil.which("node"):
        return None
    if editable not in _ABAS:
        dump = Path(tempfile.mkdtemp()) / "abas.json"
        p = subprocess.run(["node", str(Path(__file__).with_name("render_deckboxes.js")),
                            str(pagina(editable)), str(dump)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
        _ABAS[editable] = json.loads(dump.read_text(encoding="utf-8"))
    return _ABAS[editable]


def tiles(html, est=None):
    """Os tiles desenhados: [(classes, nome, o html do tile)]."""
    out = []
    for m in re.finditer(r'<(?:div|label|li) class="tl ([^"]*)" data-nm="([^"]*)"', html):
        if est is None or f" {est} " in f" {m.group(1)} ":
            out.append((m.group(1), m.group(2), html[m.start():m.start() + 2500]))
    return out


# ---------------------------------------------------------------------------
# 1. Cada secção desenha tiles com imagem e o estado certo
# ---------------------------------------------------------------------------
def caso_a_aba_da_caixa_e_toda_em_imagem():
    d = abas(True)
    if d is None:
        print("aba da caixa em imagem: sem node, saltado")
        return
    a = d["dc"]
    # A grelha: a Swords fecha (verde, a impressão exacta da cópia), a Mother é
    # substituto (âmbar), a Path é compra (vermelho, com o preço e «comprar 1»).
    grelha = a[:a.find('class="montar"')]
    sw = next(t for t in tiles(grelha, "have") if t[1] == "Swords to Plowshares")
    # (com a campanha ligada o chip diz o que falta fotografar em vez de «✓ tens»)
    assert '/small/front/i/d/id-0.jpg' in sw[2] and '"tlr">📷 1 por fotografar' in sw[2], sw[2][:600]
    assert "<span>4ED</span><span>✨</span><span>EN</span>" in sw[2], "o material da cópia"
    mo = next(t for t in tiles(grelha, "sub") if t[1] == "Mother of Runes")
    assert 'class="tlr">tens, não serve' in mo[2], mo[2][:600]
    pe = next(t for t in tiles(grelha, "miss") if t[1] == "Path to Exile")
    # Pede 2, 1 vem a caminho: compra 1 (9 € foil) e diz o que vem a caminho.
    assert "🛒 comprar 1" in pe[2] and "9,00 €" in pe[2] and "1 a caminho" in pe[2], pe[2][:800]
    # ... e a imagem da compra é a da impressão MAIS BARATA em foil (a pf20, id-2),
    # não a con (id-3, 30 €).
    assert "/id-2.jpg" in pe[2] and "/id-3.jpg" not in pe[2], pe[2][:400]
    # O passo 1: a Swords vai tirar-se da Colecção — um tile-label com a
    # checkbox e o MESMO id por que a barra conta.
    montar = a[a.find('class="montar"'):]
    p1 = next(t for t in tiles(montar, "have") if t[1] == "Swords to Plowshares")
    assert p1[2].startswith('<label class="tl have"'), p1[2][:200]
    assert 'data-id="mt|dc|' in p1[2] and 'class="tlck" type="checkbox"' in p1[2], p1[2][:400]
    assert 'class="tlr">tirar' in p1[2] and "de Colecção" in p1[2], p1[2][:900]
    # A wantlist do passo 2: um `<li class="tl miss">` com o preço, o «já a
    # tenho» e os `+`/`−` das encomendas (a Path tem 1 a caminho → 0× a comprar).
    wl = next(t for t in tiles(montar, "miss") if t[1] == "Carta Inventada")
    assert wl[2].startswith('<li class="tl miss"'), wl[2][:200]
    assert "comprar 1" in wl[2] and 'data-enc="1"' in wl[2], wl[2][:1500]
    pe2 = next(t for t in tiles(montar, "miss") if t[1] == "Path to Exile")
    assert pe2[2].startswith('<li class="tl miss enc-l"') and "9,00 €" in pe2[2], pe2[2][:400]
    assert "1 a caminho" in pe2[2] and 'data-chegou="1"' in pe2[2] \
        and 'data-falta="1"' in pe2[2], pe2[2][:2000]
    # A reserva: a Winter Moon nonfoil — tem, não serve (a caixa quer foil).
    rs = next(t for t in tiles(a, "sub") if t[1] == "Winter Moon")
    assert "🛡️ reserva · não serve" in rs[2] and 'data-reserva="tirar"' in rs[2], rs[2][:1200]
    # A revalidação «na caixa»: a Swords por fotografar (📷, âmbar), com o #copy.
    rv = [t for t in tiles(a, "rev") if t[1] == "Swords to Plowshares"]
    assert rv and "📷 por fotografar" in rv[0][2] and 'data-copy="' in rv[0][2], rv
    print("a aba da caixa: grelha, passo 1 (checkbox + data-id), wantlist (preço, +/−, "
          "chegou), reserva e revalidação, todos em tiles com a impressão certa")


def caso_as_outras_abas_sao_em_imagem():
    d = abas(True)
    if d is None:
        print("outras abas em imagem: sem node, saltado")
        return
    # Encomendas: a Path a caminho (azul tracejado) com «Chegou».
    e = d["encomendas"]
    en = next(t for t in tiles(e, "enc") if t[1] == "Path to Exile")
    assert "🚚 a caminho" in en[2] and 'data-chegou="1"' in en[2] and "loja X" in en[2], en[2][:1200]
    # Vender: os 2 Get Lost a mais — 4 validadas (✓ verde), 2 sem foto (📷);
    # o «vendida» (dois toques) no rodapé; a City of Traitors com o chip RL.
    v = d["vender"]
    gl = [t for t in tiles(v) if t[1] == "Get Lost"]
    assert gl and any('data-vend="' in t[2] and "dois toques" in t[2] for t in gl), gl[0][2][:1500]
    assert all(t[0].split()[0] in ("ok", "rev") for t in gl), [t[0] for t in gl]
    assert '<span class="rl">RL</span>' in v
    # Feira: o «levo / não levo» dentro do tile.
    f = d["feira"]
    fl = [t for t in tiles(f) if t[1] == "Get Lost"]
    assert fl and any('data-feira="nao-levo"' in t[2] for t in fl), (fl and fl[0][2][:1200])
    # Arrumar: a Swords entra na caixa — tile-label com a checkbox e o id de sempre.
    ar = d["arrumar"]
    at = next(t for t in tiles(ar) if t[1] == "Swords to Plowshares")
    assert at[2].startswith('<label class="tl') and 'data-id="' in at[2] \
        and '|Colecção|Cloud (DC)|Swords to Plowshares"' in at[2], at[2][:500]
    # Revalidação: a Colecção (o resto) por cor, em tiles, com 📷 / ✓.
    r = d["revalidacao"]
    assert tiles(r, "rev") and tiles(r, "ok"), "faltam tiles por fotografar / validadas"
    assert 'class="corhdr"' in r, "por cor, como o binder"
    # E o interruptor no topo de cada uma.
    for aba in ("encomendas", "vender", "feira", "arrumar", "revalidacao", "comprar", "dc"):
        assert 'data-vista="lista"' in d[aba] and 'data-vista="imagens"' in d[aba], aba
    print("Encomendas, Vender, Feira, Arrumar e Revalidação em tiles, com os botões; "
          "interruptor em todas")


def caso_no_site_publicado_os_tiles_nao_tem_botoes():
    d = abas(False)
    if d is None:
        print("site publicado: sem node, saltado")
        return
    for aba in ("dc", "encomendas", "vender", "feira", "arrumar"):
        assert tiles(d[aba]), f"{aba}: sem tiles no site publicado"
        assert not re.search(r"data-(enc|chegou|vend|feira|falta|reserva)=", d[aba]), aba
    # ... mas o interruptor (só lê) existe.
    assert 'data-vista="lista"' in d["dc"]
    print("site publicado: tiles sem um único botão de escrita, com o interruptor")


# ---------------------------------------------------------------------------
# 2. O interruptor
# ---------------------------------------------------------------------------
def caso_o_interruptor_volta_a_lista():
    d = abas(True)
    if d is None:
        print("interruptor: sem node, saltado")
        return
    a, lista = d["dc"], d["lista:dc"]
    assert tiles(a) and not tiles(lista), "em «Lista» não há um único tile"
    # A lista é a de antes de 20/09: as linhas `.mv` do passo 1 com o mesmo id,
    # a `<li>` da wantlist com `<b>1×</b>`, a `.mv.rv` da revalidação.
    assert re.search(r'<label class="mv[^"]*" data-id="mt\|dc\|', lista), lista[:2000]
    assert '<li data-nm="Carta Inventada"><b>1×</b>' in lista, lista[-3000:]
    assert 'class="mv rv foto"' in lista
    assert 'class="mv have"' in lista, "a grelha vira linhas"
    # Os ids dos vistos são os MESMOS nos dois modos.
    ids = lambda h: sorted(set(re.findall(r'data-id="(mt\|[^"]+)"', h)))  # noqa: E731
    assert ids(a) == ids(lista) and ids(a), (ids(a), ids(lista))
    for aba in ("vender", "feira", "encomendas", "arrumar", "revalidacao"):
        assert not tiles(d["lista:" + aba]), aba
    assert "<table class=\"vt\">" in d["lista:vender"] and 'class="enct' not in d["lista:encomendas"]
    print("«Lista» é a página de antes de 20/09, com os mesmos data-id; «Imagens» são tiles")


def caso_o_interruptor_fica_no_aparelho_e_no_config():
    r = avaliar("""
      const pedidos = [];
      fetch = async (u, o) => { pedidos.push([u, JSON.parse(o.body)]);
                               return { ok: true, status: 200, json: async () => ({ ok: true }) }; };
      const resultado = (async () => {
        const antes = comImagens();
        await mudarVista('lista');
        const depois = comImagens();
        const guardado = JSON.parse(localStorage.getItem(KEY)).imagens;
        await mudarVista('imagens');
        return { antes, depois, guardado, pedidos, fim: comImagens(), vista: D.vista };
      })();""")
    if r is None:
        print("interruptor no config: sem node, saltado")
        return
    assert r["antes"] is True and r["depois"] is False and r["guardado"] is False, r
    assert r["pedidos"] == [["api/vista", {"vista": "lista"}], ["api/vista", {"vista": "imagens"}]], r
    assert r["fim"] is True and r["vista"] == "imagens", r
    # No site publicado não há pedido nenhum: fica só no aparelho.
    r2 = avaliar("""
      let n = 0; fetch = async () => { n++; return { ok: true, json: async () => ({}) }; };
      const resultado = mudarVista('lista').then(() => ({ n, im: comImagens() }));""",
                 editable=False)
    assert r2 == {"n": 0, "im": False}, r2
    # E o config manda quando o aparelho não diz nada.
    r3 = avaliar("""
      delete P.imagens; imagens = null; D.vista = 'lista';
      const a = comImagens(); D.vista = 'imagens';
      const resultado = { a, b: comImagens() };""")
    assert r3 == {"a": False, "b": True}, r3
    print("o interruptor: no aparelho sempre, no config só em modo edição; o config é a omissão")


def caso_a_preferencia_grava_no_config_pelo_endpoint():
    cfg_path = _TMP / "cfg-vista.json"
    cfg_path.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    r = webapp.gravar_vista({"vista": "lista"}, cfg_path)
    assert r["vista"] == "lista", r
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["deckboxes"]["vista"] == "lista", cfg.get("deckboxes")
    assert deckboxes.vista_config(cfg) == "lista"
    assert deckboxes.vista_config({"deckboxes": {"vista": "xpto"}}) == "imagens"
    assert deckboxes.vista_config({}) == "imagens"
    try:
        webapp.gravar_vista({"vista": "xpto"}, cfg_path)
        raise AssertionError("uma vista desconhecida tinha de ser recusada")
    except ValueError as e:
        assert "imagens ou lista" in str(e), e
    # O `do_POST` conhece o endpoint (é o que a página chama).
    assert '"/api/vista"' in Path(webapp.__file__).read_text(encoding="utf-8")
    # E as caixas do config ficam intactas (só se acrescentou o bloco).
    assert cfg["caixas"] == CFG["caixas"]
    print("api/vista grava deckboxes.vista no config; recusa o que não é imagens/lista")


# ---------------------------------------------------------------------------
# 3. Os botões dentro dos tiles fazem os mesmos pedidos
# ---------------------------------------------------------------------------
def caso_os_botoes_dos_tiles_fazem_os_pedidos_de_sempre():
    r = avaliar("""
      const pedidos = [];
      fetch = async (u, o) => { pedidos.push([u, JSON.parse(o.body)]);
                               return { ok: true, status: 200, json: async () => ({ ok: true, msg: 'x' }) }; };
      const btn = (ds) => ({ dataset: ds, disabled: false, textContent: 'b',
                             classList: { add() {}, remove() {} }, closest: () => null });
      const resultado = (async () => {
        await encAjustar(btn({ enc: '1', slot: 'dc', nm: 'Path to Exile', board: 'main' }));
        await encChegou(btn({ slot: 'dc', nm: 'Path to Exile' }), false);
        await feiraAccao(btn({ feira: 'nao-levo', chave: 'Get Lost|LCI|en|foil' }));
        const v = btn({ vend: 'k', q: '2', nm: 'Get Lost' });
        await vendida(v); await vendida(v);
        return pedidos;
      })();""")
    if r is None:
        print("botões dos tiles: sem node, saltado")
        return
    assert r == [
        ["api/encomenda", {"delta": 1, "slot": "dc", "nm": "Path to Exile", "id": None,
                           "set": "", "num": ""}],
        ["api/encomenda-chegou", {"slot": "dc", "nm": "Path to Exile", "id": None}],
        ["api/feira", {"act": "nao-levo", "chave": "Get Lost|LCI|en|foil"}],
        ["api/vender", {"linha": "k", "q": 2}],
    ], r
    # E a checkbox de um tile do passo 1 conta para a barra pelo mesmo id: os
    # ids desenhados são exactamente os `montarItens`.
    d = abas(True)
    ids = set(re.findall(r'data-id="(mt\|[^"]+|bs\|[^"]+)"', d["dc"]))
    r2 = avaliar("const resultado = montarItens(D.caixas.find(c => c.slot === 'dc')).map(i => i.id);")
    assert set(r2) == ids and ids, (r2, ids)
    print("+/− , Chegou, levo e vendida mandam o mesmo de sempre; os tiles do passo 1 "
          "têm os ids da barra")


# ---------------------------------------------------------------------------
# 4. Sem imagem fica o nome; lazy; os pedaços
# ---------------------------------------------------------------------------
def caso_sem_imagem_fica_o_nome_e_as_imagens_sao_lazy():
    d = abas(True)
    if d is None:
        print("sem imagem: sem node, saltado")
        return
    a = d["dc"]
    ci = [t for t in tiles(a) if t[1] == "Carta Inventada"]
    assert ci, "a carta fora do catálogo tem tile na mesma"
    for t in ci:
        tile = t[2][:t[2].find("</span>")]
        assert "<img" not in tile and '<b class="tlnm">Carta Inventada</b>' in tile, tile
    for img in re.findall(r"<img [^>]*>", a):
        if "tlck" in img:
            continue
        assert 'loading="lazy"' in img and 'onerror="this.remove()"' in img, img
        assert 'width="146" height="204"' in img and "/small/" in img, img
    print("sem sid é o nome no quadrado; cada <img> é lazy, small, com tamanho e onerror")


def caso_as_grelhas_grandes_vem_aos_poucos():
    r = avaliar("""
      const muitos = (n) => Array.from({ length: n }, (_, i) => ({ nm: 'c' + i, sid: null }));
      const conta = (h) => (h.match(/class="tl[ "]/g) || []).length;
      imagens = true; aba = 'x';
      const zera = () => { grelhaN = 0; tilesDesenhados = 0; GRELHAS_ABERTAS.clear(); };
      zera(); const semTecto = grelhaHTML(muitos(200));
      zera(); const comTecto = grelhaHTML(muitos(200), { max: 60 });
      zera(); const duas = grelhaHTML(muitos(100), { max: 60 }) + grelhaHTML(muitos(100), { max: 60 })
                          + grelhaHTML(muitos(100), { max: 60 });
      zera(); GRELHAS_ABERTAS.add('x|0'); const aberta = grelhaHTML(muitos(200), { max: 60 });
      const resultado = { semTecto: conta(semTecto), comTecto: conta(comTecto),
                          botao: /data-mais="x\\|0"/.test(comTecto) && /mostrar as outras 140 cartas/.test(comTecto),
                          duas: conta(duas), botoes: (duas.match(/data-mais=/g) || []).length,
                          aberta: conta(aberta), semBotao: !/data-mais/.test(aberta) };""")
    if r is None:
        print("grelhas grandes: sem node, saltado")
        return
    assert r["semTecto"] == 200, r
    assert r["comTecto"] == 60 and r["botao"], r
    # O tecto é por ABA (150): 60 + 60 + 30, e três botões.
    assert r["duas"] == 150 and r["botoes"] == 3, r
    assert r["aberta"] == 200 and r["semBotao"], r
    print("grelhas grandes: 60 por grelha, 150 por aba, «mostrar as outras N» abre")


# ---------------------------------------------------------------------------
# 5. Nenhum número muda
# ---------------------------------------------------------------------------
def caso_nenhum_numero_da_alocacao_venda_ou_feira_muda():
    con = coleccao()
    rep = loadout.report(con)
    chaves = ("custo_total", "comprar_total", "copias", "total", "copias_rl", "total_rl",
              "copias_guardar", "total_guardar")
    antes = {k: rep[k] for k in chaves}
    antes["slots"] = json.dumps([(s["slot"], s["pct"], s["tenho"], s["comprar"], s["custo"])
                                 for s in rep["slots"]])
    antes["arr"] = rep["arrumacao"]["copias"]
    for ed in (True, False):
        d = deckboxes.payload(con, rep, editable=ed)
        depois = {k: rep[k] for k in chaves}
        depois["slots"] = json.dumps([(s["slot"], s["pct"], s["tenho"], s["comprar"], s["custo"])
                                      for s in rep["slots"]])
        depois["arr"] = rep["arrumacao"]["copias"]
        assert antes == depois, (antes, depois)
        assert d["resumo"]["custo"] == rep["custo_total"] and d["resumo"]["venda"] == rep["total"]
        assert d["feira"]["saldo"]["troca"] == round(d["feira"]["levar"]["troca"]
                                                     - d["feira"]["trazer"]["minimo"], 2)
    # 2 Get Lost na venda (o excedente do playset), 1 City of Traitors na RL.
    assert rep["copias"] == 2 and rep["copias_rl"] == 1, (rep["copias"], rep["copias_rl"])
    print(f"payload nos dois modos não toca no relatório: fechar {rep['custo_total']} €, "
          f"comprar {rep['comprar_total']}, venda {rep['copias']}c")


def caso_o_sid_e_o_da_impressao_exacta_ou_a_mais_barata():
    con = coleccao()
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=False)
    c = next(x for x in d["caixas"] if x["slot"] == "dc")
    sw = next(x for x in c["cartas"] if x["nm"] == "Swords to Plowshares")
    assert sw["sid"] == "id-0" and sw["lotes"][0]["sid"] == "id-0", sw
    pe = next(x for x in c["cartas"] if x["nm"] == "Path to Exile")
    assert pe["sid"] == "id-2", ("a mais barata em foil é a pf20", pe["sid"])
    assert loadout.impressao_mais_barata(con, "Path to Exile", "nonfoil") == "id-2"
    assert loadout.impressao_mais_barata(con, "Carta Inventada", "foil") is None
    wl = next(x for x in c["wantlist"] if x["nm"] == "Path to Exile")
    assert wl["sid"] == "id-2" and wl["unit"] == 9.0, wl
    ci = next(x for x in c["cartas"] if x["nm"] == "Carta Inventada")
    assert ci["sid"] is None
    # A venda, a estante, a feira e a revalidação levam a impressão da cópia.
    gl = next(r for r in d["venda"]["normal"]["linhas"] if r["nm"] == "Get Lost")
    assert gl["sid"] == "id-4", gl
    est = d["venda"]["saida"]["estante"]["grupos"][0]["linhas"][0]
    assert est["sid"] == "id-4", est
    lv = next(l for l in d["feira"]["levar"]["linhas"] if l["nm"] == "Get Lost")
    assert lv["sid"] == "id-4"
    tz = d["feira"]["trazer"]["linhas"]
    assert all(l.get("sid") for l in tz if l["nm"] != "Carta Inventada"), tz
    rv = next(l for l in c["rev"]["linhas"] if l["nm"] == "Swords to Plowshares")
    assert rv["sid"] == "id-0"
    res = c["reserva"][0]
    assert res["nm"] == "Winter Moon" and res["sid"] == "id-5" and res["lotes"][0]["sid"] == "id-5"
    mv = next(m for b in c["montar"]["blocos"] for m in b["movs"])
    assert mv["sid"] == "id-0", mv
    assert d["vista"] == "imagens"
    print("sid: a cópia exacta na grelha/passo 1/venda/estante/feira/revalidação/reserva; "
          "a mais barata na compra; None fora do catálogo")


# ---------------------------------------------------------------------------
# 6. O CSS
# ---------------------------------------------------------------------------
def caso_o_css_dos_tiles():
    casca = deckboxes.casca()
    css = re.search(r"<style>([\s\S]*?)</style>", casca).group(1)
    assert re.search(r"\.tiles\{[^}]*grid-template-columns:repeat\(auto-fill,minmax\(120px", css)
    assert re.search(r"\.tl \.tli\{[^}]*aspect-ratio:\.716", css), "sem aspect-ratio a grelha salta"
    assert re.search(r"\.tl input\.tlck\{[^}]*width:28px", css), "a checkbox do tile ≥ 28 px"
    movel = css[css.find(".tiles{grid-template-columns:repeat(3,1fr)"):]
    assert movel and "@media(max-width:640px)" in css[:css.find(".tiles{grid-template-columns:repeat(3,1fr)")][-400:], \
        "3 colunas a 640 px"
    assert re.search(r"\.tl input\.tlck\{width:32px;height:32px\}", movel)
    assert ".tl .tlnm{" in css and ".tl.miss .tli{" in css and ".tl.enc .tli{" in css
    print("CSS: minmax(120px) em largo, 3 colunas a 640 px, aspect-ratio, checkbox 28/32 px")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for f in CASOS:
        f()
    print(f"\n{len(CASOS)} casos ok")
