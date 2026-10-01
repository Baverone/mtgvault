"""A FILA DA FASE 2 E O BOTÃO DO ALVO NO MESMO SÍTIO (André, 2026-10-01).

A Fase 2 da página das fases mostra a fila das fotos dos decks montados; o botão
que diz *"é esta caixa que estou a fotografar"* vivia só na Deckboxes. Ele
perguntou **onde é que punha as fotos** — o sinal de que o caminho não estava à
vista de onde ele trabalha. O que aqui se tranca, e cada caso CHUMBA se a
funcionalidade for retirada:

  1. o botão da Fase 2 define MESMO o alvo da revalidação (o mesmo
     `/api/revalidacao` da Deckboxes, não um segundo caminho ao lado) e escreve
     o `pendentes/esperadas.md`;
  2. a página mostra o ALVO ACTUAL em destaque, com quantas cópias faltam
     fotografar nele — e di-lo claramente quando não há alvo nenhum. Sem isso ele
     fotografa uma caixa a pensar que está a fotografar outra;
  3. a página diz ONDE largar as fotos: soltas na raiz de `pendentes\\`, nunca em
     `pendentes\\deckboxes\\` (a foto da caixa física) nem em «Colocar fotos da
     coleção aqui» (cartas NOVAS — estas cópias já estão no inventário);
  4. **definir o alvo e ver a fila NÃO são travados pelo `venda.congelado_ate`**:
     a trava de 12/10 é para a SAÍDA de venda, e as fotos dos decks são de ANTES
     de Ghent. A mesma chamada que recusa a exportação deixa passar o alvo;
  5. a fila mede **FOTOS de até 4 cartas**: um playset é **uma** foto (corrigido
     a 2026-10-01 — esteve aqui a regra errada, «um playset dá quatro linhas»);
  6. o caminho da Fase 4 está preparado (o mesmo botão, com alvo `venda`) e **não
     se abre antes da data da trava**.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`: os ficheiros que acompanham a base
saem da pasta da `MTGVAULT_DB`, e sem a fixar a bateria escrevia no `data/` a
sério).
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
ONTEM, FUTURO = "2026-01-01", "2099-01-01"

CFG = {
    # A venda LIGADA: é a única forma de o teste da trava chegar à trava (com o
    # interruptor desligado o `_exige_venda` recusa antes, por outra razão).
    "venda": {"mostrar": True, "congelado_ate": FUTURO},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "edicoes": "premodern", "estrita": True},
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"},
    ],
    "caixas": [
        {"slot": "pm", "nome": "UW Replenish", "formato": "premodern",
         "fonte": "deck", "ref": "PM", "balde": "Colecção",
         "estado": "montada", "prioridade": 1},
        {"slot": "lg", "nome": "Legacy — Doomsday", "formato": "legacy",
         "fonte": "deck", "ref": "LG", "balde": "Colecção",
         "estado": "permanente", "prioridade": 2},
    ],
    "revalidacao": {"desde": "2026-09-20", "alvo": None},
    "reserva": {"limiar_pct": 20},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, configio, db, fases, loadout,  # noqa: E402
                      revalidacao, sources)

import arrumacao  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"], 1.50),
    ("Force of Will", "all", "1996-06-10", ["nonfoil", "foil"], 60.0),
]
_ABERTAS = []


# ---------------------------------------------------------------------------
# A base de mentira
# ---------------------------------------------------------------------------
def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, fin, preco) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Instant',1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i),
             json.dumps(fin), rel,
             json.dumps({"legacy": "legal", "premodern": "legal"})))
        for f in fin:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-20', ?)", (f"id-{i}", f, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    for nome, fmt, cartas in (("PM", "premodern", [("Swords to Plowshares", 4)]),
                              ("LG", "legacy", [("Force of Will", 1)])):
        con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?",
                          (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?, 'main')", (did, nm, q))
    con.commit()
    # A base que o `webapp` e o `arrumacao` vão abrir por si (`db.session()`).
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1, lang="pt", finish="nonfoil", slot=None, validado=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language=lang,
                              finish=finish, sub_collection="Colecção")
    con.execute("UPDATE copies SET validado_em = ? WHERE id = ?", (validado, cid))
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.commit()
    return cid


def mundo():
    """A caixa `pm` montada com um PLAYSET lá dentro (uma linha da `copies`)."""
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4, slot="pm")
    return con


def repor(alvo=None, congelado=FUTURO, campanha=True):
    cfg = json.loads(json.dumps(CFG))
    if congelado is None:
        cfg["venda"].pop("congelado_ate", None)
    else:
        cfg["venda"]["congelado_ate"] = congelado
    if not campanha:
        cfg.pop("revalidacao")
    elif alvo:
        cfg["revalidacao"]["alvo"] = alvo
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    webapp._CACHE.clear()
    return cfg


# ---------------------------------------------------------------------------
# HTTP, como o botão da página o faria
# ---------------------------------------------------------------------------
class Pedido(webapp.Handler):
    def __init__(self, path, corpo=None, ip="127.0.0.1"):
        self.path = path
        self.client_address = (ip, 5555)
        self.rfile = io.BytesIO((corpo or "").encode("utf-8"))
        self.headers = {"Content-Length": str(len(corpo or "")) or "0"}
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


# ---------------------------------------------------------------------------
# O que a página DESENHA, com o JS a sério (`tests/avaliar_js.js`)
# ---------------------------------------------------------------------------
def desenha(con, aba, editavel=True):
    """O `innerHTML` de `#vista` com a aba `aba` aberta.

    Corre o JavaScript DA PÁGINA (`arrumacao.html_page`, com os dados
    embutidos) no harness de node: é a única forma de saber que o bloco do alvo
    e o botão chegam mesmo ao ecrã — a casca sozinha está sempre certa.
    """
    html = _TMP / f"arr-{aba}-{int(editavel)}.html"
    html.write_text(arrumacao.html_page(con, loadout.report(con), editavel=editavel),
                    encoding="utf-8")
    js = _TMP / "ver.js"
    js.write_text(f"""
      const resultado = (async () => {{
        ABA = {aba!r};
        await render();
        return document.getElementById('vista').innerHTML;
      }})();
    """, encoding="utf-8")
    r = subprocess.run([shutil.which("node"), str(RAIZ / "tests" / "avaliar_js.js"),
                        str(html), str(js)], capture_output=True, text=True,
                       encoding="utf-8", cwd=str(RAIZ), timeout=180)
    assert r.returncode == 0, f"node falhou: {r.stderr[-1200:]}"
    return json.loads(r.stdout)


# ===========================================================================
# 1. O BOTÃO DA FASE 2 DEFINE O ALVO E ESCREVE O `esperadas.md`
# ===========================================================================
def caso_o_botao_da_fase2_define_o_alvo_e_escreve_o_esperadas_md():
    """O botão da fila de cada deck manda o MESMO pedido que o «Fotografar esta
    caixa» da Deckboxes (`/api/revalidacao`, `act: alvo`). Um segundo caminho ao
    lado discordava do primeiro um dia qualquer, em silêncio."""
    repor()
    con = mundo()
    assert revalidacao.alvo() is None, "parte-se sem alvo"
    # É este o pedido que o `data-alvo-tipo`/`data-alvo-slot` da Fase 2 manda.
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "caixa", "slot": "pm"})
    assert cod == 200, (cod, j)
    assert j["por_revalidar"] == 4, j          # o playset, cópia a cópia
    assert revalidacao.alvo() == {"tipo": "caixa", "slot": "pm",
                                  "em": revalidacao.hoje()}
    assert configio.ler()["revalidacao"]["alvo"]["slot"] == "pm"
    txt = (webapp.ROOT / "pendentes" / "esperadas.md").read_text(encoding="utf-8")
    assert "## Caixa UW Replenish — por revalidar (4 cópias)" in txt, txt
    assert "Swords to Plowshares" in txt, txt
    # E a página passa a dizê-lo, sem ninguém reconstruir a conta: o número sai
    # do MESMO `revalidacao.progresso` que a Deckboxes mostra.
    idx, _partes = arrumacao.dados(con, loadout.report(con), editavel=True)
    assert idx["revalidacao"]["alvo"]["slot"] == "pm", idx["revalidacao"]
    assert idx["revalidacao"]["alvo"]["por_revalidar"] == 4, idx["revalidacao"]
    assert idx["revalidacao"]["alvo"]["nome"] == "Caixa UW Replenish"
    _post("/api/revalidacao", {"act": "parar"})
    assert revalidacao.alvo() is None
    repor()
    print("o botao da Fase 2 fixa o alvo pelo mesmo endpoint e escreve o esperadas.md")


def caso_o_botao_so_existe_no_modo_edicao():
    """No site publicado não há endpoint que grave — um botão que não grava é
    pior do que botão nenhum (a regra de sempre). A INFORMAÇÃO fica nos dois."""
    repor()
    con = mundo()
    if not shutil.which("node"):
        print("sem node: salto o desenho da pagina")
        return
    v = desenha(con, "f2", editavel=True)
    assert 'data-alvo-tipo="caixa"' in v and 'data-alvo-slot="pm"' in v, v[:800]
    ro = desenha(con, "f2", editavel=False)
    assert "data-alvo-tipo" not in ro and "data-alvo-parar" not in ro, ro[:800]
    assert "UW Replenish" in ro, "a fila continua à vista no site publicado"
    print("o botao do alvo so no 8771; a informacao nos dois")


# ===========================================================================
# 2 e 3. O ALVO ACTUAL EM DESTAQUE, E ONDE LARGAR AS FOTOS
# ===========================================================================
def caso_a_pagina_mostra_o_alvo_actual_e_onde_largar_as_fotos():
    """Sem o alvo à vista ele fotografa uma caixa a pensar que está a fotografar
    outra — e a corrida da noite liga as fotos às cópias erradas. E a página tem
    de dizer ONDE largar as fotos: era essa a pergunta dele."""
    if not shutil.which("node"):
        print("sem node: salto o desenho da pagina")
        return
    repor()
    con = mundo()
    # (a) SEM alvo, di-lo claramente.
    v = desenha(con, "f2")
    assert "Não há alvo de revalidação" in v, v[:900]
    # (b) COM alvo, diz qual é e quantas faltam.
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-10-01"})
    v = desenha(con, "f2")
    assert "Estás a fotografar" in v and "Caixa UW Replenish" in v, v[:900]
    assert "4 cópias</b> por fotografar" in v, v[:1500]
    assert "data-alvo-parar" in v, "tem de haver como parar"
    # (c) ONDE: as DUAS portas. Esta asserção mudou a 2026-10-01 à tarde, com a
    # decisão dele (*"o melhor é criar pasta"*): até aí a página mandava-o para
    # a raiz de `pendentes\` e dizia que «Colocar fotos da coleção aqui» era só
    # para cartas NOVAS. Agora a PASTA DO DECK é uma porta a sério — ver
    # `test_pasta_por_deck.py` — e o que tem de continuar escrito é a outra
    # pasta que nunca é para cartas.
    assert "Colocar fotos da coleção aqui" in v, v[:1500]
    assert "pasta do deck" in v and "vale" in v, v[:1500]
    assert "pendentes\\deckboxes\\" in v and "caixa de plástico" in v, v[:1500]
    assert "liga cada foto à" in v, "tem de dizer que a foto se LIGA à cópia"
    repor()
    print("a pagina diz qual e o alvo, quantas faltam, e as duas portas das fotos")


def caso_o_rodape_tambem_diz_onde_e_onde_nao():
    """Escrito na PRÓPRIA página, não só no LEIA-ME: é na página que ele está.

    Desde a decisão dele de 2026-10-01 à tarde o rodapé tem de dizer as DUAS
    portas (a página e a pasta do deck) e continuar a dizer a pasta que NUNCA é
    para cartas (`pendentes\\deckboxes\\`).
    """
    rod = arrumacao._RODAPE
    assert "Colocar fotos da coleção aqui" in rod, rod[-900:]
    assert "pasta do deck" in rod and "_plano.txt" in rod, rod[-900:]
    assert "Tirar fotos" in rod, "a outra porta é a página"
    assert "pendentes\\deckboxes\\" in rod and "caixa de plástico" in rod
    assert "ligar-se à cópia que já existe" in rod
    print("o rodape da pagina diz as duas portas das fotos e a pasta que nao e")


# ===========================================================================
# 4. A TRAVA DE 12/10 É PARA A VENDA, NÃO PARA AS FOTOS
# ===========================================================================
def caso_definir_o_alvo_nao_e_travado_pela_data():
    """A trava (`venda.congelado_ate`) existe para a SAÍDA de venda — ele joga o
    RC Ghent a 9-11/10. As fotos dos decks são de ANTES de Ghent: travá-las era
    travar exactamente o passo que a Fase 2 existe para fazer agora.

    Mede-se com a trava LIGADA e no mesmo pedido: a exportação recusa-se (409) e
    o alvo passa (200).
    """
    repor(congelado=FUTURO)
    con = mundo()
    assert fases.venda_congelada(), "o fixture tem de estar com a trava ligada"
    cod, j = _post("/api/venda-export", {})
    assert cod == 409 and "CONGELADA" in j["erro"], (cod, j)
    # E, com a MESMA trava ligada, fixar o alvo passa.
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "caixa", "slot": "pm"})
    assert cod == 200, (cod, j)
    assert revalidacao.alvo()["slot"] == "pm"
    # A fila da Fase 2 também não se cala com a trava ligada.
    rep = loadout.report(con)
    f2 = fases.fila_decks(con, rep)
    assert f2["barra"]["cartas"] == 4, f2["barra"]
    idx, partes = arrumacao.dados(con, rep, editavel=True)
    assert idx["congelada"] is True, idx["congelada"]
    assert partes["fase2"]["barra"]["cartas"] == 4, partes["fase2"]["barra"]
    assert idx["revalidacao"]["alvo"]["por_revalidar"] == 4
    _post("/api/revalidacao", {"act": "parar"})
    repor()
    print("a trava recusa a saida de venda e deixa passar o alvo e a fila da Fase 2")


# ===========================================================================
# 5. A FILA MEDE FOTOS DE ATÉ 4 CARTAS
# ===========================================================================
def caso_a_fila_da_fase2_mede_fotos_de_ate_quatro_cartas():
    """*"organiza o Blue farm e CDEH por tipo de carta e ate 4 cartas por foto"*
    e *"se sao 4 fotos, e 1 foto com as 4 cartas"*.

    CORRIGIDO a 2026-10-01: este caso exigia o contrário (quatro linhas para um
    playset), que era quatro vezes o trabalho dele. O playset é UMA foto de
    quatro cartas; o ALVO continua a contar CÓPIAS, que é outra pergunta (quantas
    cópias faltam revalidar) e tem de continuar a dar 4.
    """
    repor()
    con = mundo()
    f2 = fases.fila_decks(con, loadout.report(con))
    fila = next(x for x in f2["filas"] if x["slot"] == "pm")
    swords = [f for f in fila["fotos"]
              if any(i["nm"] == "Swords to Plowshares" for i in f["itens"])]
    assert len(swords) == 1, f"o playset deu {len(swords)} fotos"
    assert swords[0]["cartas"] == 4 and swords[0]["linhas"] == 1, swords[0]
    assert fila["barra"]["fotos"] == 1 and fila["barra"]["falta"] == 1
    assert fila["barra"]["cartas"] == 4 and fila["barra"]["linhas"] == 1
    assert f2["max_cartas"] == 4
    assert all(f["cartas"] <= 4 for f in fila["fotos"])
    # E o número do ALVO conta CÓPIAS (quantas faltam revalidar): 4.
    repor(alvo={"tipo": "caixa", "slot": "pm", "em": "2026-10-01"})
    idx, _p = arrumacao.dados(con, loadout.report(con))
    assert idx["revalidacao"]["alvo"]["por_revalidar"] == 4, idx["revalidacao"]
    assert idx["totais"]["fase2_fotos"] == 1, idx["totais"]
    assert idx["totais"]["fase2_cartas"] == 4, idx["totais"]
    repor()
    print("a fila da Fase 2 mede FOTOS (1 de 4 cartas) e o alvo conta 4 copias")


# ===========================================================================
# 6. O CAMINHO DA FASE 4 ESTÁ PREPARADO E NÃO SE ABRE ANTES DA DATA
# ===========================================================================
def caso_a_fase4_usa_a_mesma_mecanica_e_nao_abre_antes_da_data():
    """A Fase 4 é a MESMA mecânica com o alvo `venda`. O caminho fica feito e
    abre-se sozinho na data da trava — abri-lo antes era começar o passo que a
    trava existe para adiar."""
    if not shutil.which("node"):
        print("sem node: salto o desenho da pagina")
        return
    repor(congelado=FUTURO)
    con = mundo()
    v = desenha(con, "f4")
    assert 'data-alvo-tipo="venda"' not in v, "não se abre antes da data"
    assert f"A partir de <b>{FUTURO}</b>" in v, v[:900]
    assert "mesmo botão da Fase 2" in v and "venda" in v, v[:900]
    assert "pendentes\\</code></b>" in v, "mesmo fechada, diz onde as fotos vão"
    # Passada a data, o botão aparece — sem ninguém mexer no código.
    repor(congelado=ONTEM)
    v = desenha(con, "f4")
    assert 'data-alvo-tipo="venda"' in v, v[:900]
    assert "A partir de" not in v, v[:900]
    # E o alvo `venda` é um alvo válido do mesmo endpoint.
    cod, j = _post("/api/revalidacao", {"act": "alvo", "tipo": "venda"})
    assert cod == 200 and j["nome"] == "Venda", (cod, j)
    _post("/api/revalidacao", {"act": "parar"})
    repor()
    print("a Fase 4 reusa o alvo `venda` e so abre a partir da data da trava")


# ===========================================================================
def main():
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for f in casos:
        try:
            f()
            print(f"  ok   {f.__name__}")
        except Exception as e:                       # noqa: BLE001
            falhas += 1
            print(f"  FAIL {f.__name__}: {type(e).__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                            # noqa: BLE001, S110
            pass
    print(f"\n{len(casos) - falhas}/{len(casos)} casos ok")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
