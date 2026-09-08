"""«Decks montados» e «Decks para montar»: dois botões, duas perguntas.

André, 2026-09-08, à letra: *"No mtgvault, quero decks montados num botão
específico, e um botão a dizer «decks para montar», para poder separar as
coisas."*

São duas perguntas diferentes e ele está à frente da estante quando faz cada
uma: num caso já tem a caixa na mão (o que lá está, e desmontá-la); no outro
ainda a vai montar (o que tirar da colecção, o que comprar). A vista *Todas*
junta-as por prioridade de alocação, que é a resposta a outra pergunta.

O que aqui se tranca:

  1. cada caixa aparece numa vista **e só numa**, pelo `estado`: `montada` e
     `congelada` na primeira, tudo o resto na segunda — e os dois contadores do
     cabeçalho somam sempre o total de caixas (uma caixa não se esconde);
  2. **mudar o estado muda a vista** (montar/desmontar move a caixa de lado),
     que é o que garante que os dois botões continuam a dizer a verdade quando
     ele carrega nos outros;
  3. a vista dos montados diz **«montada em <data>»** — a data vem da
     `copy_allocation` (`loadout.datas_de_arrumacao`), e uma caixa que se diz
     montada e de que o vault não sabe o conteúdo **não ganha data nenhuma**:
     diz que falta confirmar. Inventar-lhe o dia de hoje era assinar por ele uma
     confirmação que ele nunca fez (é o caso do Stiflenought);
  4. o **Desmontar** só se desenha no modo edição (o publicado não tem
     endpoints de escrita), e o **Montar** — que é só navegação — existe nos
     dois;
  5. a fila de abas fica **agrupada**: as montadas primeiro, com o ponto verde.

Não abre socket nenhum e não toca na rede. O HTML desenhado só se verifica se
houver `node` (a bateria tem de correr num PC sem ele).
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
# Quatro caixas, uma de cada lado da pergunta: uma montada de que o vault sabe o
# conteúdo, uma que se DIZ montada e não tem linhas na `copy_allocation` (o caso
# do Stiflenought), uma permanente por montar e uma candidata por montar.
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção"],
    "decks_vigiados": [],
    "regras_por_formato": [
        {"grupo": "legacy", "formatos": ["legacy"], "dedicado": True},
    ],
    "caixas": [
        {"slot": "montada", "nome": "Caixa Montada", "formato": "legacy",
         "fonte": "deck", "ref": "A", "balde": "Colecção",
         "estado": "montada", "prioridade": 1},
        {"slot": "porconfirmar", "nome": "Caixa Por Confirmar",
         "formato": "legacy", "fonte": "deck", "ref": "B", "balde": "Colecção",
         "estado": "montada", "prioridade": 2},
        {"slot": "perm", "nome": "Caixa Permanente", "formato": "legacy",
         "fonte": "deck", "ref": "C", "balde": "Colecção",
         "estado": "permanente", "prioridade": 3},
        {"slot": "cand", "nome": "Caixa Candidata", "formato": "legacy",
         "fonte": "deck", "ref": "D", "balde": "Colecção",
         "estado": "candidata", "prioridade": 4},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)

from mtgvault import db, loadout, sources  # noqa: E402

import deckboxes  # noqa: E402

CATALOGO = [("Wrath of God", "4ed"), ("Ancestral Vision", "tsp"),
            ("Swamp Dweller", "leg"), ("Chromatic Star", "shm")]
# Uma lista por caixa. Todas pedem cartas que ele tem, para nenhuma delas ficar
# a zero por acidente e o teste medir o que quer medir.
LISTAS = {"A": [("Wrath of God", 1)], "B": [("Ancestral Vision", 1)],
          "C": [("Swamp Dweller", 1)], "D": [("Chromatic Star", 1)]}
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Sorcery',2,'W',?,'2005-01-01',?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil"]),
             json.dumps({"legacy": "legal"})))
        con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date,
                       trend) VALUES (?,'cardmarket','nonfoil','2026-09-08',?)""",
                    (f"id-{i}", 3.0))
    for nome, cartas in LISTAS.items():
        con.execute("INSERT INTO decks (name, format) VALUES (?, 'legacy')", (nome,))
        did = con.execute("SELECT id FROM decks WHERE name = ?",
                          (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,'main')", (did, nm, q))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    for i, _c in enumerate(CATALOGO):
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                       purpose, sub_collection_id) VALUES (?,1,'nonfoil','en',
                       'player',?)""", (f"id-{i}", sub))
    con.commit()
    return con


def arrumar(con, slot, carta, quando="2026-09-05 18:30:00"):
    """Regista uma cópia DENTRO de uma caixa, com data — é o que o botão
    «sleevado e na caixa» grava (`guardar_arrumacao`)."""
    cid = con.execute("SELECT cp.id FROM copies cp JOIN cards c "
                      "ON c.scryfall_id = cp.scryfall_id WHERE c.name = ?",
                      (carta,)).fetchone()["id"]
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at) "
                "VALUES (?,?,1,?)", (cid, slot, quando))
    con.commit()


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def _dados(con, editable=False):
    return deckboxes.payload(con, loadout.report(con), editable=editable)


def _abas(con, editable=False):
    """`{aba: HTML}` — o que o browser mostraria. `None` sem `node`."""
    if not shutil.which("node"):
        return None
    out = Path(tempfile.mkdtemp()) / "deckboxes.html"
    out.write_text(deckboxes.html_page(con, editable=editable), encoding="utf-8")
    dump = Path(tempfile.mkdtemp()) / "abas.json"
    harness = Path(__file__).with_name("render_deckboxes.js")
    p = subprocess.run(["node", str(harness), str(out), str(dump)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2000:]
    return json.loads(dump.read_text(encoding="utf-8"))


def _cartoes(html):
    """Os nomes das caixas que a vista desenhou, pela ordem em que lá estão."""
    return [re.sub(r"<[^>]+>", "", m) for m in
            re.findall(r'<div class="btop"><b>(.*?)</b>', html)]


# ---------------------------------------------------------------------------
def caso_cada_caixa_esta_numa_vista_e_so_numa():
    """Os dois botões só servem para separar se a soma deles for o total. Uma
    caixa que não aparecesse em nenhuma das duas desaparecia da página sem um
    único erro — é o padrão do `event_tier`, do lado do browser."""
    repor()
    con = base()
    d = _dados(con)
    r = d["resumo"]
    assert r["montados"] == 2, r
    assert r["por_montar"] == 2, r
    assert r["montados"] + r["por_montar"] == len(d["caixas"]), r

    abas = _abas(con)
    if abas is None:
        print("montados/por montar: sem `node`, so o payload verificado")
        return
    assert _cartoes(abas["montados"]) == ["Caixa Montada", "Caixa Por Confirmar"]
    # A ordem da vista de montar é a do PLANO: permanentes primeiro.
    assert _cartoes(abas["pormontar"]) == ["Caixa Permanente", "Caixa Candidata"]
    assert "Caixa Permanente" not in abas["montados"], abas["montados"][:600]
    assert "Caixa Montada" not in abas["pormontar"], abas["pormontar"][:600]
    print("cada caixa numa vista e so numa · 2 montados + 2 por montar = 4 caixas")


def caso_montar_e_desmontar_move_a_caixa_de_vista():
    """Mudar o `estado` tem de mudar o lado. Se não mudasse, os dois botões
    diziam a verdade no dia em que foram escritos e mentiam a partir do
    primeiro clique no «sleevado e na caixa»."""
    repor()
    con = base()
    d = _dados(con)
    assert {c["slot"] for c in d["caixas"] if c["montado"]} == {"montada",
                                                                "porconfirmar"}
    # A Caixa Permanente passa a montada (o que o «sleevado e na caixa» faz ao
    # config), e a Caixa Montada volta a permanente (o que o «desmontar» faz).
    novo = json.loads(json.dumps(CFG))
    for cx in novo["caixas"]:
        if cx["slot"] == "perm":
            cx["estado"] = "montada"
        if cx["slot"] == "montada":
            cx["estado"] = "permanente"
    CAMINHO.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()

    d = _dados(con)
    assert {c["slot"] for c in d["caixas"] if c["montado"]} == {"perm",
                                                                "porconfirmar"}
    assert d["resumo"]["montados"] == 2 and d["resumo"]["por_montar"] == 2

    abas = _abas(con)
    if abas is None:
        print("mudanca de estado: sem `node`, so o payload verificado")
        repor()
        return
    assert "Caixa Permanente" in abas["montados"], "a que montou nao mudou de lado"
    assert "Caixa Montada" in abas["pormontar"], "a que desmontou nao mudou de lado"
    assert "Caixa Permanente" not in abas["pormontar"]
    assert "Caixa Montada" not in abas["montados"]
    repor()
    print("montar e desmontar movem a caixa de vista, e os contadores acompanham")


def caso_montada_em_diz_a_data_ou_diz_que_nao_sabe():
    """A data vem da `copy_allocation`. A caixa que se diz montada e não tem
    linhas lá dentro NÃO ganha data — diz que falta confirmar o que lá está.
    Dar-lhe o dia de hoje era assinar por ele uma confirmação que ele nunca
    fez, que é exactamente o defeito do `event_tier`: um valor plausível onde
    devia estar um "não sei"."""
    repor()
    con = base()
    arrumar(con, "montada", "Wrath of God")
    assert loadout.datas_de_arrumacao(con) == {"montada": "2026-09-05"}, \
        loadout.datas_de_arrumacao(con)

    caixas = {c["slot"]: c for c in _dados(con)["caixas"]}
    assert caixas["montada"]["arrumada_em"] == "2026-09-05", caixas["montada"]
    assert caixas["porconfirmar"]["arrumada_em"] == "", caixas["porconfirmar"]
    assert caixas["perm"]["arrumada_em"] == "", caixas["perm"]

    abas = _abas(con)
    if abas is None:
        print("montada em <data>: sem `node`, so o payload verificado")
        return
    html = abas["montados"]
    assert "montada em <b>2026-09-05</b>" in html, html[:1200]
    assert "ainda não me disseste o que lá está" in html, html[:1200]
    print("montados: «montada em 2026-09-05», e a outra diz que falta confirmar")


def caso_os_botoes_certos_em_cada_vista():
    """O **Desmontar** escreve na base e por isso só se desenha no modo edição —
    no site publicado o endpoint não existe e um botão que não faz nada é pior
    do que não haver botão. O **Montar** só muda de aba: existe nos dois."""
    repor()
    con = base()
    arrumar(con, "montada", "Wrath of God")
    abas = _abas(con)
    if abas is None:
        print("botoes das duas vistas: sem `node`, saltado")
        return
    edi = _abas(con, editable=True)
    assert 'data-act="desmontar"' not in abas["montados"], \
        "o publicado desenhou um botao de escrita"
    assert 'data-act="desmontar"' in edi["montados"], \
        "falta o Desmontar no modo edicao"
    # O Montar é navegação: tem de existir nos dois, e só do lado de montar.
    for h in (abas, edi):
        assert 'data-montar="perm"' in h["pormontar"], h["pormontar"][:800]
        assert "data-montar=" not in h["montados"], h["montados"][:800]
    print("Desmontar so em edicao · Montar nas duas (e so na vista de montar)")


def caso_as_abas_de_cada_deck_ficam_agrupadas():
    """As abas individuais MANTÊM-SE — só passam a vir agrupadas, montadas
    primeiro e com o ponto verde. Antes vinham pela ordem da alocação e a caixa
    que está na estante aparecia no meio das que ainda não existem."""
    repor()
    con = base()
    abas = _abas(con)
    if abas is None:
        print("fila de abas agrupada: sem `node`, saltado")
        return
    fila = abas["__fila"]
    assert "✅ Decks montados" in fila and "🔧 Decks para montar" in fila, fila[:900]
    # As abas de deck: montadas primeiro, com o ponto verde; depois as outras.
    ordem = re.findall(r'data-aba="(montada|porconfirmar|perm|cand)"', fila)
    assert ordem == ["montada", "porconfirmar", "perm", "cand"], ordem
    verdes = re.findall(r'<i class="pin (\w+)"></i>([^<]+)', fila)
    assert [nm for cls, nm in verdes if cls == "done"] == ["Caixa Montada",
                                                           "Caixa Por Confirmar"], verdes
    assert fila.count('class="dtsep"') == 2, "faltam os separadores dos grupos"
    # E a aba de cada caixa continua a existir e a desenhar, uma por caixa.
    d = _dados(con)
    for c in d["caixas"]:
        assert abas[c["slot"]], f"a aba da caixa {c['slot']} deixou de desenhar"
    print(f"a fila mantem as {len(d['caixas'])} abas de deck, agrupadas e com pin")


def run():
    for fn in (caso_cada_caixa_esta_numa_vista_e_so_numa,
               caso_montar_e_desmontar_move_a_caixa_de_vista,
               caso_montada_em_diz_a_data_ou_diz_que_nao_sabe,
               caso_os_botoes_certos_em_cada_vista,
               caso_as_abas_de_cada_deck_ficam_agrupadas):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
