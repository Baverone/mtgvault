"""LINHAS INCOMPLETAS: as cópias que ele já tem entram no painel Montar.

O buraco estava escrito no `work/revisao/mtgvault-faltas-check.md` (a nota
*"arrumar 345 → 347"*) e ficou por corrigir nesse dia: uma linha que pede 4 e a
que a alocação só deu 2 vive em `missing`, e tudo o que percorria a alocação de
uma caixa percorria só o `have`. Resultado: as duas cópias que ele TEM existiam
na base, estavam alocadas àquela caixa e **não apareciam em lado nenhum** — nem
no painel *Montar*, nem na aba *Arrumar*, nem no CSV, nem na `copy_allocation`
do *"já arrumei tudo"*. Ele montava a caixa e ficavam as duas na prateleira,
enquanto a aba *Comprar* pedia as outras duas. É o padrão do `event_tier`:
nenhum passo dá erro, e a folha que ele leva para a estante está a menos duas
cartas.

O que aqui se tranca:

  1. uma linha INCOMPLETA gera movimento das cópias que existem, e a linha diz
     porque é que vem a menos (*"2 de 4 — 2 em Comprar"*);
  2. a **barra** conta-as (o `marcar_q` e as checkboxes que a grelha desenhou —
     as duas contas têm de dar o mesmo número);
  3. uma linha em falta **sem nenhuma cópia** não gera movimento nenhum: não há
     nada para tirar, é compra;
  4. o **registo** grava-as (`copy_allocation`) — sem isso o painel mandava-o
     tirá-las da gaveta e no dia seguinte outra vez;
  5. a aba **Arrumar** e o CSV levam-nas;
  6. a alocação, as compras e o custo **não mexem**: isto é o que se VÊ, não o
     que se compra.

Não abre socket nenhum nem toca na rede.
"""
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
    # Sem regras de material: o que aqui se mede é o que a linha incompleta
    # mostra, e uma regra de língua a tirar cópias de vista só tornava os
    # números opacos.
    "regras_por_formato": [
        {"grupo": "legacy", "formatos": ["legacy"], "dedicado": False},
    ],
    "caixas": [
        {"slot": "a", "nome": "Caixa A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "estado": "candidata", "prioridade": 1},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)

from mtgvault import db, loadout  # noqa: E402

import deckboxes  # noqa: E402
import webapp  # noqa: E402

# O `webapp._caixa` regenera as páginas depois de cada escrita, e escreve-as no
# `webapp.ROOT` — que é a raiz do repositório. Apontado aqui, logo no import.
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

CATALOGO = [
    ("Wrath of God", "4ed", "Sorcery"),
    ("Ancestral Vision", "tsp", "Sorcery"),
    ("Sol Ring", "c21", "Artifact"),
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


def curta():
    """A caixa do caso real: pede 4, tem 2. Mais uma completa e uma a zero.

    * **Wrath of God** — 4 no main, 2 na `Colecção`: a linha INCOMPLETA;
    * **Sol Ring** — 1 no main, 1 na `Colecção`: a linha completa, para se ver
      que as duas convivem na mesma grelha;
    * **Ancestral Vision** — 1 no main e nenhuma cópia: a linha que continua a
      viver só na aba *Comprar*.
    """
    con = base()
    deck(con, "A", [("Wrath of God", 4, "main"), ("Sol Ring", 1, "main"),
                    ("Ancestral Vision", 1, "main")])
    add(con, "Wrath of God", 2)
    add(con, "Sol Ring", 1)
    return con


def caixa(con, slot="a", editable=True):
    rep = loadout.report(con)
    d = deckboxes.payload(con, rep, editable=editable)
    return next(c for c in d["caixas"] if c["slot"] == slot), rep, d


def movs(rep, slot="a"):
    s = next(x for x in rep["slots"] if x["slot"] == slot)
    return s, loadout.movimentos_de_entrada(s, loadout.caixas_de_deck(rep["slots"]))


def alocacao(con, slot="a"):
    return {r["copy_id"]: r["quantity"] for r in con.execute(
        "SELECT copy_id, quantity FROM copy_allocation WHERE slot = ?", (slot,))}


# ---------------------------------------------------------------------------
def caso_a_linha_incompleta_gera_movimento():
    """As 2 cópias que ele tem de uma carta que o deck joga a 4 tiram-se na
    mesma — e a linha diz que vem a menos. Antes disto não apareciam em sítio
    nenhum: ficavam na prateleira enquanto a caixa dizia que faltavam 2."""
    con = curta()
    rep = loadout.report(con)
    s, ms = movs(rep)

    # A linha está em `missing` (falta-lhe 2) e tem lotes: as cópias existem.
    linha = next(m for m in s["missing"] if m["nm"] == "Wrath of God")
    assert linha["got"] == 2 and linha["missing"] == 2, linha
    assert sum(g["q"] for g in linha["lotes"]) == 2, linha["lotes"]

    wog = [m for m in ms if m["nm"] == "Wrath of God"]
    assert sum(m["q"] for m in wog) == 2, ("as 2 que ele tem", ms)
    assert all(m["parcial"] for m in wog), wog
    assert wog[0]["nota"] == "2 de 4 — 2 em Comprar", wog[0]["nota"]

    # A completa continua a vir, e sem nota nenhuma: não há o que explicar.
    sol = next(m for m in ms if m["nm"] == "Sol Ring")
    assert sol["parcial"] is False and sol["nota"] == "", sol
    print("linha incompleta: as 2 copias saem no plano, com «2 de 4 — 2 em Comprar»")


def caso_linha_sem_nenhuma_copia_nao_gera_movimento():
    """Uma falta a zero continua a viver só na aba *Comprar*. Não há nada para
    tirar da gaveta, e inventar-lhe um movimento era mandá-lo procurar uma carta
    que não existe em casa."""
    con = curta()
    rep = loadout.report(con)
    s, ms = movs(rep)
    linha = next(m for m in s["missing"] if m["nm"] == "Ancestral Vision")
    assert linha["got"] == 0 and linha["lotes"] == [], linha
    assert not [m for m in ms if m["nm"] == "Ancestral Vision"], ms
    assert loadout.nota_parcial(linha) == "0 de 1 — 1 em Comprar"
    print("falta a zero: sem movimento — nao ha nada para tirar da gaveta")


def caso_a_alocacao_e_as_compras_nao_mexem():
    """Isto é o que se VÊ, não o que se compra: a caixa continua a 3 de 6, com
    2 Wrath of God e 1 Ancestral Vision na lista de compras."""
    con = curta()
    rep = loadout.report(con)
    s, _ms = movs(rep)
    assert s["tenho"] == 3 and s["precisa"] == 6 and s["pct"] == 50, s["pct"]
    assert s["comprar"] == 3 and s["faltam"] == 3, (s["comprar"], s["faltam"])
    assert s["noutra"] == 0, s["noutra"]
    print("alocacao e compras iguais: 3 de 6, 3 a comprar")


def caso_a_barra_conta_as_copias_parciais():
    """O «N de M» e as checkboxes que a grelha desenhou têm de dar o mesmo
    número — e esse número inclui as parciais. Uma barra a dizer "1 de 1" com 3
    linhas por baixo não daria erro nenhum: é o padrão do `event_tier` do lado
    do browser."""
    con = curta()
    c, _rep, _d = caixa(con)
    M = c["montar"]
    itens = [(f'mt|{c["slot"]}|{m["copy_id"]}|{m["nm"]}|{m["board"]}', m["q"])
             for b in M["blocos"] for m in b["movs"]]
    assert sum(q for _i, q in itens) == 3, itens      # 2 Wrath + 1 Sol Ring
    assert M["marcar_q"] == 3, M["marcar_q"]
    assert M["dentro"] == 0 and M["ja"] == 0, M
    # E a linha leva a nota até ao payload: quem a compõe é o Python.
    wog = next(m for b in M["blocos"] for m in b["movs"]
               if m["nm"] == "Wrath of God")
    assert wog["parcial"] is True and wog["nota"] == "2 de 4 — 2 em Comprar", wog
    print("barra: 3 copias para marcar (2 parciais + 1 completa)")


def caso_o_registo_grava_as_parciais():
    """Marcar as parciais tem de as gravar na `copy_allocation`. Sem isso o
    painel mandava-o tirá-las da gaveta e no dia seguinte outra vez — e o
    *"já arrumei tudo"* deixava-as fora da caixa para sempre."""
    con = curta()
    c, _rep, _d = caixa(con)
    wog = next(m for b in c["montar"]["blocos"] for m in b["movs"]
               if m["nm"] == "Wrath of God")

    cfg = webapp.ler_config()
    r = webapp.registar_parcial(con, cfg, "a", [wog["copy_id"]])
    webapp.escrever_config(cfg, CAMINHO)
    assert r["copias"] == 2, ("o lote de 2 vale 2 cópias", r)
    assert alocacao(con) == {wog["copy_id"]: 2}, alocacao(con)
    # Falta 1 (o Sol Ring): a caixa sobe a `permanente`, nunca a `montada`.
    assert r["falta"] == 1 and r["completa"] is False, r

    # E no dia seguinte já não as manda tirar — mas a linha continua incompleta.
    c, rep, _d = caixa(con)
    assert c["montar"]["marcar_q"] == 1 and c["montar"]["dentro"] == 2, c["montar"]
    s, _ms = movs(rep)
    assert next(m for m in s["missing"] if m["nm"] == "Wrath of God")["comprar"] == 2
    print("registo: as 2 parciais ficam na copy_allocation e saem da grelha")


def caso_a_arrumacao_leva_as_parciais():
    """A aba *Arrumar*, o CSV e o *"já arrumei tudo"* saem todos da mesma lista.
    Antes desta correcção as parciais faltavam nos três."""
    con = curta()
    rep = loadout.report(con)
    plano = rep["arrumacao"]
    assert plano["copias"] == 3, plano["copias"]
    nomes = [m["nm"] for m in plano["movimentos"]]
    assert nomes.count("Wrath of God") == 1 and "Sol Ring" in nomes, nomes
    assert "Wrath of God" in loadout.csv_arrumacao(plano)

    n = loadout.guardar_arrumacao(con, rep)
    assert n == 3, n
    assert sum(alocacao(con).values()) == 3, alocacao(con)
    print("arrumar: 3 copias no plano, no CSV e na copy_allocation")


# ---------------------------------------------------------------------------
# O que o BROWSER desenha
# ---------------------------------------------------------------------------
def caso_a_pagina_escreve_a_nota_na_linha():
    """O «2 de 4 — 2 em Comprar» tem de chegar ao HTML: é a única coisa que o
    impede de contar 2 na grelha, 4 na lista e não saber qual das duas mente."""
    con = curta()
    if not shutil.which("node"):
        print("nota na linha: sem `node`, saltado")
        return
    pasta = Path(tempfile.mkdtemp())
    pagina = pasta / "deckboxes.html"
    pagina.write_text(deckboxes.html_page(con, editable=True), encoding="utf-8")
    dump = pasta / "abas.json"
    p = subprocess.run(
        ["node", str(Path(__file__).with_name("render_deckboxes.js")),
         str(pagina), str(dump)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    aba = json.loads(dump.read_text(encoding="utf-8"))["a"]
    assert "2 de 4 — 2 em Comprar" in aba, aba[:2000]
    assert "mv parc" in aba, "a linha parcial leva a moldura âmbar"
    # E a completa não leva nota nenhuma.
    assert aba.count("parcn") == 1, aba.count("parcn")
    print("pagina: a linha parcial desenha a nota e a moldura ambar")


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("caso_"):
            fn()
    print("\nOK: as copias das linhas incompletas entram no painel Montar")
