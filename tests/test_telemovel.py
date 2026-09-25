"""O MODO EDIÇÃO NO TELEMÓVEL (2026-09-18): à frente da estante, a 390 px.

O uso real do mtgvault é o André com o telemóvel, no modo edição do 8771, a
marcar cartas. Auditoria em `ai-pc/work/revisao/mtgvault-telemovel-0918.md`.
O que aqui se tranca — e cada caso CHUMBA se a tarefa não fizer nada:

  1. **o JavaScript saiu da casca** para `deckboxes.js`, apontado pelo hash do
     conteúdo (`?v=`): a casca encolhe de 150 KB para ~30, o `build` escreve o
     ficheiro, o `webapp.py` serve-o DA MEMÓRIA e cacheável só com o `?v=`, e
     o `html_page` (que os testes lêem de um ficheiro solto) continua a embutir
     o MESMO texto;
  2. o `.js` vai ao `git add` do `daily.yml` e da tarefa `mtgvault-daily` — sem
     isso o site publicado abre a casca e não desenha nada;
  3. **a procura** na aba da caixa: filtra sem acentos, sem maiúsculas e por
     palavras em qualquer ordem; a grelha, as linhas do passo 1, as básicas e as
     compras levam `data-nm`; existe também na página publicada (só lê);
  4. **o toque numa miniatura** mostra o que o `title` dizia (no telemóvel não há
     hover);
  5. **«Limpar os vistos» do Arrumar** deixou de apagar as marcas do painel
     Montar de todas as caixas (era `P.feitos = {}`);
  6. **«vendida» em dois toques**, com o nome da carta no segundo;
  7. **sem rede**: o `gravar` diz em português que não sabe se gravou, e desiste
     ao fim de um prazo em vez de deixar o botão morto;
  8. **`recarregar()`** vai buscar os dados de novo em vez de `location.reload()`
     — e se isso falhar, diz e deixa a página no sítio;
  9. os alvos de toque a 640 px (`.mv` ≥ 44 px, `.btn.sm` ≥ 36 px), o `hidden`
     que ganha ao `display:flex`, e a barra de filtros `sticky`.

Não abre socket para fora nem toca na `vault.db` a sério.
"""
import hashlib
import io
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
    # O «vendida» em dois toques é um dos casos deste ficheiro: o interruptor
    # de 2026-09-25 (omissão desligado) tem de estar ligado.
    "venda": {"mostrar": True},
    "regras_colecao": {}, "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_por_formato": [{"grupo": "legacy", "formatos": ["legacy"],
                            "dedicado": False}],
    "caixas": [{"slot": "a", "nome": "Caixa A", "formato": "legacy",
                "fonte": "deck", "ref": "A", "balde": "Colecção",
                "estado": "candidata", "prioridade": 1}],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"           # nunca o repositório (ver test_montar_barra)
webapp.ROOT.mkdir(exist_ok=True)

# Nomes com acentos e ligaduras de propósito: é o que a procura tem de achar.
CATALOGO = [("Swords to Plowshares", "4ed", "Instant"),
            ("Æther Vial", "dst", "Artifact"),
            ("Séance", "dka", "Enchantment"),
            ("Lotus Petal", "tmp", "Artifact"),
            ("Island", "unh", "Basic Land — Island")]
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
               VALUES (?,?,?,?,'S',?,'en','rare',?,2,'W',?,'2004-11-19',?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), tl, json.dumps(["nonfoil"]),
             json.dumps({"legacy": "legal"})))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.execute("INSERT INTO decks (name, format) VALUES ('A', 'legacy')")
    did = con.execute("SELECT id FROM decks WHERE name = 'A'").fetchone()["id"]
    for nm, q in (("Swords to Plowshares", 2), ("Æther Vial", 1), ("Séance", 1),
                  ("Lotus Petal", 1), ("Island", 3)):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?,'main')", (did, nm, q))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    # Tem tudo menos a Séance; e 6 Lotus Petal, para haver excedente na venda.
    for nm, q in (("Swords to Plowshares", 2), ("Æther Vial", 1),
                  ("Lotus Petal", 6), ("Island", 3)):
        sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                          (nm,)).fetchone()["scryfall_id"]
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                       purpose, sub_collection_id) VALUES (?,?,'nonfoil','en',
                       'player',?)""", (sid, q, sub))
    con.commit()
    return con


_PAGINA = {}


def pagina(editable=True):
    """O `deckboxes.html` com o payload EMBUTIDO, para o node."""
    if editable not in _PAGINA:
        con = base()
        p = Path(tempfile.mkdtemp()) / "deckboxes.html"
        p.write_text(deckboxes.html_page(con, editable=editable), encoding="utf-8")
        _PAGINA[editable] = p
    return _PAGINA[editable]


def avaliar(js, editable=True):
    """Corre `js` no contexto da página e devolve o `resultado`. `None` sem node."""
    if not shutil.which("node"):
        return None
    t = Path(tempfile.mkdtemp()) / "teste.js"
    t.write_text(js, encoding="utf-8")
    p = subprocess.run(["node", str(Path(__file__).with_name("avaliar_js.js")),
                        str(pagina(editable)), str(t)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
    return json.loads(p.stdout)


def abas(editable=True):
    """`{aba: html}` desenhado pelo `render_deckboxes.js`. `None` sem node."""
    if not shutil.which("node"):
        return None
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    p = subprocess.run(["node", str(Path(__file__).with_name("render_deckboxes.js")),
                        str(pagina(editable)), str(dump)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
    return json.loads(dump.read_text(encoding="utf-8"))


class Pedido(webapp.Handler):
    """Um GET de mentira que guarda o código, os cabeçalhos e o corpo."""

    def __init__(self, path, ip="127.0.0.1"):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO(b"")
        self.headers = {"Content-Length": "0"}
        self.codigo, self.corpo, self.cab = None, b"", {}

    def send_response(self, code, *_a):
        self.codigo = code

    def send_header(self, k, v):
        self.cab[k] = v

    def end_headers(self):
        pass

    @property
    def wfile(self):
        self_ = self

        class Escritor:
            def write(self, b):
                self_.corpo += b
        return Escritor()


# ---------------------------------------------------------------------------
# 1. O JavaScript à parte
# ---------------------------------------------------------------------------
def caso_a_casca_aponta_para_o_js_pelo_hash():
    """`build` escreve `deckboxes.js` ao lado e a casca aponta-lhe com o hash do
    conteúdo; o `html_page` continua a embutir o mesmo texto."""
    con = base()
    d = Path(tempfile.mkdtemp())
    deckboxes.build(con, d / "deckboxes.html")
    casca = (d / "deckboxes.html").read_text(encoding="utf-8")
    js = (d / "deckboxes.js").read_text(encoding="utf-8")
    v = hashlib.sha1(js.encode("utf-8")).hexdigest()[:12]
    assert f'<script src="deckboxes.js?v={v}"></script>' in casca, casca[-400:]
    assert v == deckboxes.js_versao() and js == deckboxes.js_texto()
    assert "function render(" not in casca and "function render(" in js
    assert "%JS_DADOS%" not in js and "carregaDados(" in js and "erroDados(" in js
    # O TAMANHO é o ganho, e é ele que se tranca: 150 375 bytes antes de
    # 2026-09-18, 32 377 depois — porque os 123 KB de JavaScript saíram para o
    # `deckboxes.js`, que é cacheável e hoje já vai em 243 KB.
    #
    # O tecto subiu de 60 para 70 KB na reestruturação de 2026-09-24: a casca
    # ganhou a CASCA PARTILHADA (o CSS do layout e da barra lateral, 11 KB, mais
    # 3,5 KB da própria barra e 2 KB do JavaScript do menu). Medido: 46 692 →
    # 64 045 bytes. O que o tecto defende continua intacto — o JavaScript está
    # fora e é cacheável; o que cresceu foi CSS e markup partilhados por nove
    # páginas. Se voltar a subir, o passo seguinte é tirar o CSS partilhado para
    # um `.css` com hash no `?v=`, como se fez ao `.js` (custo: mais um ficheiro
    # nas duas listas de `git add`, e o site inteiro sem estilo se faltar lá).
    #
    # 2.ª PASSAGEM (2026-09-24): 64 045 → 68 842. Os ~4,8 KB são os 19 ícones
    # SVG da barra lateral (a decisão de trocar os emojis por um conjunto único)
    # e o CSS deles. Já estão MAGROS: `fill`, `stroke`, a espessura e as pontas
    # do traço vivem no CSS e não em cada `<svg>` — escritos em cada um, eram
    # 190 bytes de repetição por ícone e a casca ia a 71 336. O tecto sobe para
    # 74 KB, que deixa margem sem deixar de morder.
    tam = len(casca.encode("utf-8"))
    assert tam < 74_000, tam
    # Mudar o texto muda o hash — é o que faz o `immutable` ser honesto.
    assert deckboxes.js_versao(js + "\n// x") != v
    # O html_page embute, para os testes lerem de um ficheiro solto.
    inteira = deckboxes.html_page(con)
    assert '<script src="deckboxes.js' not in inteira and "function render(" in inteira
    assert '<script id="dados"' in inteira
    print(f"casca {tam} bytes a apontar para deckboxes.js?v={v}; html_page embute")


def caso_o_webapp_serve_o_js_da_memoria_e_cacheavel():
    """`/deckboxes.js` sai do texto deste processo (nunca de um ficheiro velho do
    disco), cacheável só quando o pedido traz o `?v=`."""
    (webapp.ROOT / "deckboxes.js").write_text("// ficheiro VELHO no disco",
                                              encoding="utf-8")
    v = deckboxes.js_versao()
    p = Pedido(f"/deckboxes.js?v={v}")
    p.do_GET()
    assert p.codigo == 200, p.codigo
    assert p.corpo.decode("utf-8") == deckboxes.js_texto(), "servia o ficheiro do disco"
    assert "immutable" in p.cab["Cache-Control"], p.cab
    assert p.cab["Content-Type"].startswith("text/javascript"), p.cab
    p = Pedido("/deckboxes.js")
    p.do_GET()
    assert p.codigo == 200 and "no-store" in p.cab["Cache-Control"], p.cab
    # E a casca que o webapp serve aponta para esse mesmo hash.
    p = Pedido("/deckboxes.html")
    p.do_GET()
    assert f'deckboxes.js?v={v}' in p.corpo.decode("utf-8"), p.corpo[-300:]
    assert "no-store" in p.cab["Cache-Control"], "a casca NÃO se guarda em cache"
    print("webapp: /deckboxes.js da memória, immutable com ?v=, no-store sem")


def caso_o_js_vai_ao_git_add_do_workflow_e_da_tarefa():
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    assert "deckboxes.js" in linha.split(), "o daily.yml não faz `git add deckboxes.js`"
    tarefa = RAIZ.parent.parent / "ai-pc" / "tasks" / "mtgvault-daily"
    if tarefa.is_dir():
        for f in ("run.py", "test.py"):
            assert '"deckboxes.js"' in (tarefa / f).read_text(encoding="utf-8"), \
                f"a tarefa mtgvault-daily ({f}) não leva o deckboxes.js"
    p = subprocess.run(["git", "-C", str(RAIZ), "check-ignore", "-q", "deckboxes.js"],
                       capture_output=True)
    assert p.returncode == 1, "deckboxes.js está no .gitignore"
    print("deckboxes.js vai ao git add do workflow e da tarefa, e não está ignorado")


def caso_os_harness_de_node_seguem_o_script_src():
    """Uma casca com `<script src>` também se corre no harness — senão o dia em
    que o `html_page` deixasse de embutir apagava a bateria inteira do node."""
    if not shutil.which("node"):
        print("harness com src: sem node, saltado")
        return
    con = base()
    d = Path(tempfile.mkdtemp())
    deckboxes.build(con, d / "deckboxes.html")
    # A casca não tem dados: injecta-se o payload embutido MAS deixa-se o
    # `<script src>` como está — é esse caminho que se testa.
    dados = deckboxes.payload(con, loadout.report(con))
    casca = (d / "deckboxes.html").read_text(encoding="utf-8")
    casca = casca.replace('<script src="', '<script id="dados" type="application/json">'
                          + json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
                          + '</script>\n<script src="')
    (d / "deckboxes.html").write_text(casca, encoding="utf-8")
    dump = d / "abas.json"
    p = subprocess.run(["node", str(Path(__file__).with_name("render_deckboxes.js")),
                        str(d / "deckboxes.html"), str(dump)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    assert "Caixa A" in json.loads(dump.read_text(encoding="utf-8"))["a"]
    print("render_deckboxes.js lê o deckboxes.js apontado por <script src>")


# ---------------------------------------------------------------------------
# 2. A procura
# ---------------------------------------------------------------------------
def caso_a_procura_ignora_acentos_maiusculas_e_ordem():
    r = avaliar("""
      const resultado = {
        acento: casaProcura('Séance', 'seance'),
        acento2: casaProcura('Cabeça de Dragão', 'CABECA drag'),
        ligadura: casaProcura('Æther Vial', 'aether'),
        ordem: casaProcura('Swords to Plowshares', 'plow swords'),
        parcial: casaProcura('Swords to Plowshares', 'plow'),
        nao: casaProcura('Swords to Plowshares', 'petal'),
        vazio: casaProcura('Lotus Petal', '   '),
        apostrofo: casaProcura("Sensei's Divining Top", 'senseis'),
        norm: normProcura('Élan Vital — Ø'),
      };""")
    if r is None:
        print("procura: sem node, saltado")
        return
    assert r["acento"] and r["acento2"] and r["ligadura"] and r["ordem"] \
        and r["parcial"] and r["apostrofo"], r
    assert r["nao"] is False and r["vazio"] is True, r
    assert r["norm"] == "elan vital o", r["norm"]
    print("procura: sem acentos, sem maiúsculas, por palavras em qualquer ordem")


def caso_a_aba_da_caixa_tem_a_procura_e_tudo_leva_o_nome():
    """O campo existe nos DOIS modos (só lê), e o que se filtra — miniaturas,
    linhas do passo 1, básicas, compras — leva `data-nm`."""
    for editable in (True, False):
        d = abas(editable)
        if d is None:
            print("aba com procura: sem node, saltado")
            return
        a = d["a"]
        assert 'id="procura"' in a and 'type="search"' in a, a[:600]
        assert 'class="seg topo"' in a, "a barra da procura tem de ser a sticky"
        # E os dois atalhos para o que vive três ecrãs abaixo.
        assert 'data-salto=".montar"' in a and 'data-salto="#passo2"' in a, a[:800]
        assert 'id="passo2"' in a and 'class="montar"' in a
        # 5 cartas na grelha + 4 linhas de tirar (o Island é um lote de 3 numa
        # linha só) + 1 básica + 1 compra (a Séance) — todas com o nome.
        nomes = re.findall(r'data-nm="([^"]+)"', a)
        assert nomes.count("Swords to Plowshares") >= 2, nomes    # grelha + passo 1
        assert "Séance" in nomes and "Island" in nomes and "Æther Vial" in nomes, nomes
        # Desde 2026-09-20 TODAS as secções são tiles (ver `test_visual.py`) e
        # cada tile sem checkbox responde ao toque: as 5 da grelha, mais a
        # compra (Séance) e as cópias da revalidação... — pelo menos as 5.
        assert a.count('onclick="tocarCarta(this)"') >= 5, "cada miniatura responde ao toque"
        # Em «Lista» a grelha vira linhas e continua a levar o nome.
        lista = d["lista:a"]
        assert re.findall(r'data-nm="([^"]+)"', lista).count("Swords to Plowshares") >= 2
    print("a aba da caixa tem a procura nos dois modos, e a grelha/passo 1/compras levam data-nm")


def caso_o_toque_numa_miniatura_mostra_o_title():
    r = avaliar("""
      tocarCarta({ getAttribute: (k) => k === 'title' ? 'Séance — falta 1 — comprar 1' : null });
      tocarCarta({ getAttribute: () => '' });
      const resultado = __toasts;""")
    if r is None:
        print("toque na miniatura: sem node, saltado")
        return
    assert r == ["Séance — falta 1 — comprar 1"], r
    print("o toque numa miniatura mostra o que o title dizia (e nada, sem title)")


# ---------------------------------------------------------------------------
# 3. Gestos destrutivos
# ---------------------------------------------------------------------------
def caso_limpar_vistos_do_arrumar_nao_apaga_as_marcas_das_caixas():
    r = avaliar("""
      P.feitos = { 'mt|a|1|Swords to Plowshares|main': 1, 'bs|a|4|Island': 1,
                   'mo|b|9|Lotus Petal|main': 1,
                   '7|Colecção|Caixa A|Lotus Petal': 1, '8|Caixa B|Colecção|X': 1 };
      const n = limparVistosArrumar(true);
      const resultado = { n, fica: Object.keys(P.feitos).sort(),
                          guardado: JSON.parse(localStorage.getItem(KEY)).feitos };""")
    if r is None:
        print("limpar vistos: sem node, saltado")
        return
    assert r["n"] == 2, r
    assert r["fica"] == ["bs|a|4|Island", "mo|b|9|Lotus Petal|main",
                         "mt|a|1|Swords to Plowshares|main"], r
    assert sorted(r["guardado"]) == r["fica"], "e fica gravado no aparelho"
    print("«Limpar os vistos» do Arrumar só limpa os da arrumação (2), as 3 marcas ficam")


def caso_vendida_pede_dois_toques_com_o_nome():
    r = avaliar("""
      const chamadas = [];
      fetch = async (u, o) => { chamadas.push([u, JSON.parse(o.body)]);
                               return { ok: true, status: 200, json: async () => ({ ok: true, msg: 'x' }) }; };
      const b = { dataset: { q: '2', nm: 'Lotus Petal', vend: 'k' }, textContent: 'vendida',
                  disabled: false, classList: { add() {}, remove() {} } };
      const resultado = (async () => {
        const p1 = vendida(b); const t1 = b.textContent; const c1 = chamadas.length;
        await p1;
        await vendida(b);
        return { t1, c1, depois: chamadas, texto: b.textContent, reloads: __reloads };
      })();""")
    if r is None:
        print("vendida: sem node, saltado")
        return
    assert r["c1"] == 0 and r["t1"] == "✓ vender 2× Lotus Petal?", r
    assert r["depois"] == [["api/vender", {"linha": "k", "q": 2}]], r
    assert r["texto"] == "vendida" and r["reloads"] == 1, r
    # E o botão desenhado leva o nome e diz que são dois toques.
    d = abas(True)
    v = d["vender"]
    assert 'data-vend=' in v and 'data-nm="Lotus Petal"' in v, v[:800]
    assert "dois toques" in v, "o aria-label tem de o dizer"
    print("«vendida»: o 1.º toque arma («✓ vender 2× Lotus Petal?»), só o 2.º grava")


def caso_o_botao_armado_desarma_sozinho():
    r = avaliar("""
      const b = { dataset: {}, textContent: 'vendida', classList: { add() {}, remove() {} } };
      const resultado = (async () => {
        const a1 = armar(b, 'confirmar?');
        const durante = b.textContent;
        await new Promise(res => setTimeout(res, ARMAR_MS + 200));
        return { a1, durante, depois: b.textContent, a2: armar(b, 'confirmar?') };
      })();""")
    if r is None:
        print("armar: sem node, saltado")
        return
    assert r["a1"] is False and r["durante"] == "confirmar?", r
    assert r["depois"] == "vendida" and r["a2"] is False, ("passado o prazo volta a armar", r)
    print("um botão armado desarma-se sozinho passado o prazo")


# ---------------------------------------------------------------------------
# 4. A rede a falhar a meio
# ---------------------------------------------------------------------------
def caso_gravar_sem_rede_diz_em_portugues_e_desiste_a_tempo():
    r = avaliar("""
      const resultado = (async () => {
        fetch = () => Promise.reject(new TypeError('Failed to fetch'));
        const semRede = await gravar('api/caixa', {}).then(() => 'ok', e => e.message);
        GRAVAR_TIMEOUT_MS = 80;
        fetch = (u, o) => new Promise((res, rej) => {
          o.signal.addEventListener('abort', () => {
            const e = new Error('abortado'); e.name = 'AbortError'; rej(e); });
        });
        const t0 = Date.now();
        const pendurado = await gravar('api/caixa', {}).then(() => 'ok', e => e.message);
        return { semRede, pendurado, ms: Date.now() - t0 };
      })();""")
    if r is None:
        print("gravar sem rede: sem node, saltado")
        return
    assert "sem ligação ao servidor" in r["semRede"] and "não sei se gravou" in r["semRede"], r
    assert "Failed to fetch" not in r["semRede"], r
    assert "sem resposta do servidor" in r["pendurado"] and r["ms"] < 5000, r
    print("gravar: sem rede diz em português que não sabe se gravou; pendurado desiste")


def caso_recarregar_vai_buscar_os_dados_sem_reload():
    r = avaliar("""
      const resultado = (async () => {
        const novo = JSON.parse(JSON.stringify(D)); novo.gerado = 'NOVO';
        D._completo = novo._completo = false;   // como no site: os dados vêm por fetch
        const pedidos = [];
        fetch = async (u) => { pedidos.push(u); return { ok: true, status: 200, json: async () => novo }; };
        await recarregar();
        const depois = { gerado: D.gerado, reloads: __reloads, pedidos: pedidos.slice(),
                         resumo: document.querySelector('#resumo').innerHTML.includes('NOVO') };
        // E quando a rede falha: a página fica, e diz-lho.
        fetch = () => Promise.reject(new TypeError('Failed to fetch'));
        await recarregar();
        return { depois, gerado2: D.gerado, reloads2: __reloads, toasts: __toasts };
      })();""")
    if r is None:
        print("recarregar: sem node, saltado")
        return
    d = r["depois"]
    assert d["gerado"] == "NOVO" and d["reloads"] == 0, d
    assert d["pedidos"] == ["data/paginas/deckboxes.json"], d
    assert d["resumo"] is True, "redesenha com os dados novos"
    assert r["gerado2"] == "NOVO" and r["reloads2"] == 0, r
    assert any("não consegui voltar a ler" in t for t in r["toasts"]), r["toasts"]
    # Com o payload embutido (os testes) não há de onde recarregar: é o reload.
    r2 = avaliar("const resultado = recarregar().then(() => __reloads);")
    assert r2 == 1, r2
    print("recarregar: vai buscar o índice e redesenha; sem rede diz e fica; embutido faz reload")


# ---------------------------------------------------------------------------
# 5. O CSS a 390 px
# ---------------------------------------------------------------------------
def caso_os_alvos_de_toque_e_o_hidden():
    casca = deckboxes.casca()
    css = re.search(r"<style>([\s\S]*?)</style>", casca).group(1)
    movel = css[css.rfind("@media(max-width:640px)"):]
    assert re.search(r"\.mv\{[^}]*min-height:44px", movel), "as linhas do passo 1 ≥ 44 px"
    assert re.search(r"\.btn\.sm\{[^}]*min-height:36px", movel), ".btn.sm era 22 px"
    assert re.search(r"\.mv \.nm\{[^}]*white-space:normal", movel), \
        "o nome da carta parte linha em vez de «Swords to Plow…»"
    assert re.search(r"\.mvs\{max-height:none\}", movel), "sem scroll próprio no telemóvel"
    assert re.search(r"\.pl\{[^}]*flex-wrap:wrap", movel), "a aba Plano em duas linhas"
    assert "[hidden]{display:none!important}" in css, "senão a procura não esconde um .mv"
    assert re.search(r"\.seg\.topo\{[^}]*position:sticky", css), "a procura fica no topo"
    assert ".btn.armado{" in css
    print("CSS: alvos ≥ 36/44 px a 640 px, nomes a partir linha, hidden com !important, filtro sticky")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for f in CASOS:
        f()
    print(f"\n{len(CASOS)} casos ok")
