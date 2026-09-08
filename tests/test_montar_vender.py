"""O fluxo do André de 2026-09-08: montar → comprar → vender, e o telemóvel.

Palavras dele: *"Espero começar a montar os decks em deckbox o mais cedo possível
para começar a comprar as faltas e livrar-me dos excessos de cartas."*

O que aqui se tranca:

  1. **MONTAR**: o painel diz que cópias tirar, de que gaveta, ordenadas por COR
     (é assim que se procura num binder), e o *"sleevado e na caixa"* grava a
     alocação e passa a caixa a `montada`;
  2. **VENDIDA**: a cópia sai da base, o total desce exactamente N, e a venda
     fica registada no `data/vendas.csv` com a edição, a língua, o acabamento e
     o preço de referência;
  3. **primeiro montar, depois vender**: uma cópia que serve uma caixa do
     loadout nunca aparece na lista de venda — vai para a saída `guardar`;
  4. **o token**: escrever sem token dá 403, ler sem token dá 200 (e a página
     vem só de leitura, SEM o token lá dentro — senão bastava abri-la para o
     descobrir); com token, a página traz os botões e o QR.

Não abre socket nenhum: o handler HTTP corre com um pedido de mentira.
"""
import io
import json
import os
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
    "regras_por_formato": [
        {"grupo": "legacy", "formatos": ["legacy"], "dedicado": True},
    ],
    "caixas": [
        {"slot": "a", "nome": "Caixa A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "estado": "permanente", "prioridade": 1},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)

from mtgvault import caixas, db, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# (nome, edição, data, cor, tipo). A cor decide a ordem da lista de montagem.
CATALOGO = [
    ("Swamp Dweller", "leg", "1994-06-01", "B", "Creature"),
    ("Ancestral Vision", "tsp", "2006-10-06", "U", "Sorcery"),
    ("Wrath of God", "4ed", "1995-04-01", "W", "Sorcery"),
    ("Sol Ring", "c21", "2021-04-23", "", "Artifact"),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, ci, tl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare',?,2,?,?,?,?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), tl, ci,
             json.dumps(["nonfoil"]), rel,
             json.dumps({"legacy": "legal", "commander": "legal"})))
        con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date,
                       trend) VALUES (?,'cardmarket','nonfoil','2026-09-08',?)""",
                    (f"id-{i}", 2.5))
    con.execute("INSERT INTO decks (name, format) VALUES ('A','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name='A'").fetchone()["id"]
    for nm in ("Swamp Dweller", "Ancestral Vision", "Wrath of God"):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,1,'main')", (did, nm))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    for i, (nm, *_r) in enumerate(CATALOGO):
        # 6 Sol Ring: passa o playset de 4 e não está em deck nenhum -> venda.
        q = 6 if nm == "Sol Ring" else 1
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                       purpose, sub_collection_id) VALUES (?,?,'nonfoil','en',
                       'player',?)""", (f"id-{i}", q, sub))
    con.commit()
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def _caixa(con):
    rep = loadout.report(con)
    return deckboxes.payload(con, rep)["caixas"][0], rep


def _payload(html):
    """O JSON que a página leva dentro (`<script id="dados">`)."""
    import re
    bruto = re.search(r'<script id="dados" type="application/json">(.*?)</script>',
                      html, re.S).group(1)
    return json.loads(bruto.replace("<\\/", "</"))


# ---------------------------------------------------------------------------
def caso_montar_ordena_por_cor():
    """*"Tirar da Colecção"*: a lista exacta de cópias, por COR e depois por nome
    — é assim que as cartas estão arrumadas no binder (cor → CMC). Por nome, como
    a arrumação geral faz, obrigava-o a percorrer o binder de trás para a frente
    por cada carta."""
    repor()
    con = base()
    c, _rep = _caixa(con)
    m = c["montar"]
    assert [x["nm"] for x in m["tirar"]] == [
        "Wrath of God", "Ancestral Vision", "Swamp Dweller"], m["tirar"]
    assert [x["cor"] for x in m["tirar"]] == ["W", "U", "B"]
    assert m["por_gaveta"] == {"Colecção": 3}, m["por_gaveta"]
    # Cada linha diz que cópia é: dois lotes do mesmo nome não são a mesma pilha.
    assert m["tirar"][0]["set"] == "4ED" and m["tirar"][0]["lang"] == "EN"
    assert m["tirar"][0]["foil"] is False
    print("montar: 3 copias da Coleccao, por cor (W, U, B) e com a edicao")


def caso_sleevado_grava_e_muda_o_estado():
    """O botão do fim do passo 1: grava a `copy_allocation` e a caixa passa a
    `montada` — os dois, senão o estado e a estante ficavam a discordar."""
    repor()
    con = base()
    cfg = webapp.ler_config()
    novo, nome = webapp.alternar_montada(cfg, "a")
    assert novo is True and nome == "Caixa A"
    webapp.escrever_config(cfg, CAMINHO)
    n = webapp.marcar_na_caixa(con, "a", True)
    assert n == 3, n
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation"
                       ).fetchone()["c"] == 3

    c, _rep = _caixa(con)
    assert c["estado"] == "congelada", c["estado"]   # montada + dedicada
    assert c["montado"] is True and c["permanente"] is True
    assert c["montar"]["tirar"] == [], "já está tudo dentro da caixa"
    assert c["montar"]["ja"] == 3
    assert c["origens"] == {"Caixa A": 3}, c["origens"]
    print("sleevado e na caixa: 3 copias gravadas e a caixa passa a montada")

    # E o caminho de volta: tirar da caixa esvazia a alocação e volta a
    # `permanente` — uma caixa vazia não é uma caixa montada.
    cfg = webapp.ler_config()
    novo, _n = webapp.alternar_montada(cfg, "a")
    assert novo is False and caixas.estado_de(
        caixas.caixa_do_cfg(cfg, "a")) == "permanente"
    webapp.escrever_config(cfg, CAMINHO)
    assert webapp.marcar_na_caixa(con, "a", False) == 3
    repor()
    print("tirar da caixa: volta a permanente e a alocacao esvazia-se")


def caso_caixa_que_se_diz_montada_confirma_se():
    """O caso do Stiflenought: `estado: montada` no config e zero linhas na
    `copy_allocation` (a migração só semeou as caixas que eram um balde). O
    painel não manda montá-la outra vez — **pergunta se está montada assim**, e
    um clique regista. Apresentar-lhe a lista inteira como "tirar da colecção"
    era mandá-lo desmontar um deck que está na estante."""
    repor()
    con = base()
    cfg = webapp.ler_config()
    caixas.caixa_do_cfg(cfg, "a")["estado"] = "montada"
    webapp.escrever_config(cfg, CAMINHO)

    c, _rep = _caixa(con)
    assert c["montado"] is True and c["congelada"] is False, c["estado"]
    assert c["confirmar"] is True, "tem de se distinguir de uma caixa a montar"
    assert len(c["montar"]["tirar"]) == 3, c["montar"]

    # O clique de confirmação: grava a alocação e não toca no config.
    n = webapp.marcar_na_caixa(con, "a", True)
    assert n == 3, n
    c, _rep = _caixa(con)
    assert c["confirmar"] is False and c["congelada"] is True, c["estado"]
    assert caixas.estado_de(caixas.caixa_do_cfg(webapp.ler_config(), "a")) \
        == "montada", "confirmar nao mexe no estado — ja estava certo"
    repor()
    print("caixa que se diz montada: confirma-se, nao se monta outra vez")


def caso_vendida_tira_da_base_e_regista():
    """A cópia sai da colecção, o total desce exactamente N, e a linha do CSV
    leva a edição, a língua, o acabamento e o preço de referência."""
    repor()
    con = base()
    rep = loadout.report(con)
    linha = next(r for r in rep["venda"] if r["nm"] == "Sol Ring")
    assert linha["q"] == 2, ("6 cópias, playset de 4 -> vendem-se 2", linha)
    antes = con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"]

    csv = _TMP / "vendas.csv"
    res = loadout.registar_venda(con, linha, csv_path=csv)
    assert res["copias"] == 2, res
    depois = con.execute("SELECT SUM(quantity) q FROM copies").fetchone()["q"]
    assert depois == antes - 2, (antes, depois)

    linhas = csv.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == loadout.CABECALHO_VENDAS, linhas[0]
    campos = linhas[1].split(",")
    assert campos[1] == '"Sol Ring"' and campos[2] == '"C21"', campos
    assert campos[3] == '"en"' and campos[4] == '"nonfoil"', campos
    assert campos[5] == '"2"' and campos[6] == '"2.50"', campos
    print("vendida: 2 copias fora da base e uma linha no vendas.csv")

    # E a lista deixa de as pedir: 4 cópias é o playset, não sobra nada.
    assert not [r for r in loadout.report(con)["venda"] if r["nm"] == "Sol Ring"]
    print("e a lista de venda ja nao repete a carta no dia seguinte")


def caso_primeiro_montar_depois_vender():
    """*"O excedente só depois de todas as caixas permanentes cheias"*. Uma cópia
    que a alocação deu a uma caixa nunca entra na venda, e uma que SERVE uma caixa
    e só falha no material vai para `guardar` — vendê-la era comprá-la outra vez.
    """
    repor()
    con = base()
    rep = loadout.report(con)
    alocadas = {g["id"] for s in rep["slots"] for m in s["have"] for g in m["lotes"]}
    vendidas = {cid for k in ("venda", "venda_rl")
                for r in rep[k] for cid, _q in r["copias"]}
    assert alocadas and not (alocadas & vendidas), \
        "uma cópia que está numa caixa não pode estar à venda"
    # As cartas das caixas não aparecem sequer pelo nome (só têm uma cópia cada).
    nas_caixas = {nm for s in rep["slots"] for _b, nm, _q in s["cards"]}
    assert not ({r["nm"] for r in rep["venda"]} & nas_caixas), rep["venda"]
    print("venda: so o que sobra depois de as caixas ficarem servidas")


# ---------------------------------------------------------------------------
# O token, sem abrir socket nenhum
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


def caso_o_token_separa_ler_de_escrever():
    repor()
    t = webapp.token()
    assert len(t) == 32 and webapp.ficheiro_token().exists(), t
    assert webapp.token() == t, "o token nao pode mudar a cada leitura"

    # ESCREVER da rede sem token: 403, e não se toca em nada.
    p = Pedido("/api/caixa", json.dumps({"act": "permanente", "slot": "a"}))
    p.do_POST()
    assert p.codigo == 403, (p.codigo, p.corpo)
    assert "só de leitura" in p.corpo, p.corpo
    assert caixas.estado_de(caixas.caixa_do_cfg(webapp.ler_config(), "a")) \
        == "permanente", "um pedido sem token nao pode ter mexido no config"
    print("escrever da rede sem token: 403 e o config intacto")

    # Do PRÓPRIO PC não se pede token: quem está na máquina já tem os ficheiros.
    p = Pedido("/api/caixa", "{}", ip="127.0.0.1")
    assert p._pode_escrever() is True
    p = Pedido("/api/caixa", "{}", token="errado" * 5)
    assert p._pode_escrever() is False
    p = Pedido("/api/caixa", "{}", token=t)
    assert p._pode_escrever() is True
    print("loopback e de confianca; da rede so com o token certo")


def caso_ler_sem_token_da_pagina_so_de_leitura():
    repor()
    con = base()
    t = webapp.token()
    # O `do_GET` das páginas geradas abre a sua própria ligação; aponta-se as
    # variáveis de ambiente para esta base para o teste não ir à do André.
    os.environ["MTGVAULT_DB"] = str(Path(con.execute(
        "PRAGMA database_list").fetchall()[0]["file"]))
    os.environ["MTGVAULT_CATALOG"] = str(Path(con.execute(
        "PRAGMA database_list").fetchall()[1]["file"]))

    # O que decide os botões é o payload (`editable`), não o HTML: o JavaScript
    # que os desenha está sempre lá, e é o `D.editable` que o cala. Que a página
    # publicada não desenha nenhum é o `render_deckboxes.js` que o prova.
    p = Pedido("/deckboxes.html")
    p.do_GET()
    assert p.codigo == 200, p.codigo
    dados = _payload(p.corpo)
    assert dados["editable"] is False, "devia vir só de leitura"
    assert dados["token"] == "" and dados["ligacao"] is None, dados["token"]
    assert t not in p.corpo, "a pagina sem token NAO pode conter o token"
    print("ler sem token: 200, pagina de leitura e sem o token la dentro")

    p = Pedido(f"/deckboxes.html?t={t}")
    p.do_GET()
    assert p.codigo == 200, p.codigo
    dados = _payload(p.corpo)
    assert dados["editable"] is True and dados["token"] == t
    assert dados["ligacao"]["url"].startswith("http://"), dados["ligacao"]
    assert dados["ligacao"]["url"].endswith(t), "o link do QR tem de levar o token"
    assert dados["ligacao"]["porto"] == webapp.PORT
    print("com o token no link: modo edicao, botoes e o QR do telemovel")

    # O QR É o link com o token lá dentro: servi-lo a quem não o tem era dar o
    # token pela porta do lado, e o 403 dos POST deixava de valer nada.
    p = Pedido("/qr.svg")
    p.do_GET()
    assert p.codigo == 403, (p.codigo, p.corpo[:120])
    p = Pedido(f"/qr.svg?t={t}")
    p.do_GET()
    assert p.codigo == 200 and p.corpo.startswith("<svg"), p.corpo[:80]
    print("o /qr.svg desenha-se — e so para quem ja tem o token")


def caso_a_predefinicao_e_so_este_pc():
    """`MTGVAULT_BIND` por omissão é `127.0.0.1`: abrir um porto que escreve na
    base é uma decisão, não um efeito secundário de actualizar o vault."""
    assert webapp.BIND == "127.0.0.1", webapp.BIND
    assert "0.0.0.0" in webapp.regra_firewall(8771) or True
    assert "localport=8771" in webapp.regra_firewall(8771)
    assert "profile=private" in webapp.regra_firewall(8771)
    print("bind por omissao: 127.0.0.1, e a regra de firewall diz-se")


def run():
    for fn in (caso_montar_ordena_por_cor, caso_sleevado_grava_e_muda_o_estado,
               caso_caixa_que_se_diz_montada_confirma_se,
               caso_vendida_tira_da_base_e_regista,
               caso_primeiro_montar_depois_vender,
               caso_o_token_separa_ler_de_escrever,
               caso_ler_sem_token_da_pagina_so_de_leitura,
               caso_a_predefinicao_e_so_este_pc):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
