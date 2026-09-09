"""O REGISTO GRAVA SÓ O QUE ELE MARCOU, CÓPIA A CÓPIA.

André, 2026-09-09, à letra: *"se eu não seleccionar no deck que meti a carta, com
checkmark, é porque eu não a tenho e estás a fazer confusão."*

A 09/09 às 10:39:55 o Cloud cEDH ganhou **65 linhas** na `copy_allocation` de uma
vez — todas as que a alocação tinha calculado, incluindo duas cartas que ele não
tem na caixa. Nenhum passo deu erro: é o padrão do `event_tier`, sobre a única
tabela que diz onde uma carta está.

O que aqui se tranca:

  1. um registo com lista PARCIAL grava só essas cópias (e o que já lá estava);
  2. um pedido **sem lista** é **400** com a razão, e não escreve nada — vale
     para os três nomes (`registar`, `montado`, `confirmar`), porque uma página
     velha no telemóvel ainda manda os dois últimos;
  3. o auto-registo só se dispara com **zero** por marcar;
  4. cada cópia que entra numa caixa deixa **uma linha** no
     `data/registos-caixas.csv`, com o clique de onde veio — e os outros dois
     caminhos que escrevem na `copy_allocation` também lá escrevem;
  5. a correcção do Cloud cEDH (`corrigir_alocacao`) é **idempotente** e deixa
     backup e uma linha no `correcoes.log`.

Não abre socket nenhum nem toca na rede.
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
    "premodern_arquetipos_alvo": [],
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
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import caixas, db, loadout, sources  # noqa: E402

import webapp  # noqa: E402

# O `webapp._caixa` regenera as páginas depois de cada escrita, no `webapp.ROOT`
# — que é a raiz do repositório. Apontado aqui, logo no import.
webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

CATALOGO = [("Wrath of God", "4ed"), ("Ancestral Vision", "tsp"),
            ("Swamp Dweller", "leg")]
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
               VALUES (?,?,?,?,'S',?,'en','rare','Sorcery',2,'U',?,'2004-11-19',?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil"]),
             json.dumps({"legacy": "legal"})))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.execute("INSERT INTO decks (name, format) VALUES ('A', 'legacy')")
    did = con.execute("SELECT id FROM decks WHERE name = 'A'").fetchone()["id"]
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    for i, (nm, _sc) in enumerate(CATALOGO):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board)"
                    " VALUES (?,?,1,'main')", (did, nm))
        con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                       purpose, sub_collection_id) VALUES (?,1,'nonfoil','en',
                       'player',?)""", (f"id-{i}", sub))
    con.commit()
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def movimentos(con, slot="a"):
    rep = loadout.report(con)
    s = next(x for x in rep["slots"] if x["slot"] == slot)
    return rep, loadout.movimentos_de_entrada(
        s, loadout.caixas_de_deck(rep["slots"]))


def alocacao(con, slot="a"):
    return {r["copy_id"]: r["quantity"] for r in con.execute(
        "SELECT copy_id, quantity FROM copy_allocation WHERE slot = ?", (slot,))}


def estado(slot="a"):
    return caixas.estado_de(caixas.caixa_do_cfg(webapp.ler_config(), slot))


def _aponta_a_base(con):
    """O handler abre a SUA ligação: aponta-se a do módulo para a do teste."""
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])


# ---------------------------------------------------------------------------
def caso_o_registo_grava_so_as_marcadas():
    """Três cartas na gaveta, uma marcada: entra UMA na `copy_allocation`.

    As outras duas continuam em *"tirar da colecção"* — que é a diferença entre
    o vault saber o que está na caixa e o vault repetir o que ele calculou."""
    repor()
    con = base()
    _rep, movs = movimentos(con)
    assert len(movs) == 3, movs
    alvo = next(m for m in movs if m["nm"] == "Wrath of God")

    cfg = webapp.ler_config()
    r = webapp.registar_parcial(con, cfg, "a", [alvo["copy_id"]])
    webapp.escrever_config(cfg, CAMINHO)
    assert r["copias"] == 1 and r["falta"] == 2, r
    assert alocacao(con) == {alvo["copy_id"]: 1}, alocacao(con)
    assert estado() == "permanente", "a meio nunca é montada"

    # E as outras duas continuam por tirar — não foram dadas como estando lá.
    _rep, movs = movimentos(con)
    assert sorted(m["nm"] for m in movs) == ["Ancestral Vision", "Swamp Dweller"]
    repor()
    print("registo: 1 marcada -> 1 na caixa, e as outras 2 continuam na gaveta")


def caso_sem_lista_nao_se_grava_nada():
    """Um pedido sem `copias` é **400** e não escreve. Era este o caminho: o
    *"sleevado e na caixa"* gravava a alocação calculada, e foi assim que duas
    cartas que ele não tem foram parar ao Cloud cEDH.

    Vale para os TRÊS nomes: uma página aberta no telemóvel antes de hoje ainda
    manda `montado`/`confirmar`, e esses não podem cair no comportamento antigo
    por serem antigos."""
    repor()
    con = base()
    _aponta_a_base(con)
    for act in ("registar", "montado", "confirmar"):
        for corpo in ({"act": act, "slot": "a"},
                      {"act": act, "slot": "a", "copias": []}):
            p = Pedido("/api/caixa", json.dumps(corpo), ip="127.0.0.1")
            p.do_POST()
            assert p.codigo == 400, (act, corpo, p.codigo, p.corpo[:300])
            assert "marcaste" in p.corpo, p.corpo[:300]
            assert not alocacao(con), (act, "não pode ter gravado nada")
    assert estado() == "candidata", estado()

    # E o motor recusa pela raiz, mesmo sem passar pelo HTTP.
    rep, movs = movimentos(con)
    try:
        loadout.registar_marcadas(con, rep, "a", [])
        raise AssertionError("tinha de levantar ValueError")
    except ValueError as e:
        assert "marcaste" in str(e), e
    assert not alocacao(con)
    repor()
    print("sem lista: 400 nos tres actos, e nada escrito")


def caso_o_registo_completo_fecha_a_caixa():
    """Marcar as três é dizer que o deck está montado: a caixa passa a `montada`
    e a alocação fica com as três cópias. É o mesmo caminho do registo parcial —
    quem decide se está completa é a BASE (`falta == 0`), não o browser."""
    repor()
    con = base()
    _rep, movs = movimentos(con)
    cfg = webapp.ler_config()
    r = webapp.registar_parcial(con, cfg, "a", [m["copy_id"] for m in movs])
    webapp.escrever_config(cfg, CAMINHO)
    assert r["completa"] is True and r["copias"] == 3, r
    assert estado() == "montada", estado()
    assert sum(alocacao(con).values()) == 3
    repor()
    print("registo completo: 3 marcadas -> a caixa passa a montada")


def caso_o_csv_ganha_uma_linha_por_copia():
    """*"Se um dia uma cópia aparecer na caixa sem linha neste ficheiro, é
    bug."* O rasto é o que permite responder daqui a um mês à pergunta que hoje
    não tem resposta: **quais** das 65 linhas de 09/09 é que ele marcou."""
    repor()
    con = base()
    csv = _TMP / "registos-caixas.csv"
    if csv.exists():
        csv.unlink()
    rep, movs = movimentos(con)
    alvo = next(m for m in movs if m["nm"] == "Wrath of God")
    loadout.registar_marcadas(con, rep, "a", [alvo["copy_id"]],
                              origem="manual", csv_path=csv)
    linhas = csv.read_text(encoding="utf-8").strip().splitlines()
    assert linhas[0] == loadout.CABECALHO_REGISTOS_CAIXAS, linhas[0]
    assert len(linhas) == 2, linhas
    assert '"manual"' in linhas[1] and '"Caixa A"' in linhas[1], linhas[1]
    assert '"Wrath of God"' in linhas[1] and '"4ED"' in linhas[1], linhas[1]
    assert f'"{alvo["copy_id"]}"' in linhas[1], linhas[1]

    # O auto-registo diz que foi automático: é a diferença entre ele ter
    # carregado e a última marca ter disparado sozinha.
    rep, movs = movimentos(con)
    loadout.registar_marcadas(con, rep, "a", [m["copy_id"] for m in movs],
                              origem="auto", csv_path=csv)
    linhas = csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 4, ("mais duas — a que já lá estava não se repete",
                              linhas)
    assert all('"auto"' in x for x in linhas[2:]), linhas[2:]

    # Registar outra vez o mesmo não escreve nada: só entra o DELTA.
    rep, movs = movimentos(con)
    assert movs == [], "já está tudo dentro"
    assert csv.read_text(encoding="utf-8").strip().splitlines() == linhas
    print("registos-caixas.csv: uma linha por copia que entra, com o clique")


def caso_os_outros_caminhos_tambem_deixam_rasto():
    """O *"já arrumei tudo"* não passa pelas checkboxes — é ele a dizer que fez o
    plano inteiro. Por isso é dos que mais interessa poder reler: o ficheiro só
    serve para apanhar a escrita que ninguém está à espera."""
    repor()
    con = base()
    csv = _TMP / "arrumar.csv"
    if csv.exists():
        csv.unlink()
    loadout.guardar_arrumacao(con, loadout.report(con), csv_path=csv)
    linhas = csv.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 4, linhas          # cabeçalho + 3 cópias
    assert all('"arrumar"' in x for x in linhas[1:]), linhas
    assert sum(alocacao(con).values()) == 3
    repor()
    print("«ja arrumei tudo» tambem escreve no rasto, com origem=arrumar")


def caso_a_correccao_do_cloud_e_idempotente():
    """A correcção de dados de 09/09: as duas cópias que ele disse não ter na
    caixa saem da `copy_allocation`, com backup e uma linha no `correcoes.log`.
    Correr outra vez não faz nada — nem backup, nem linha nova."""
    repor()
    con = base()
    rep, movs = movimentos(con)
    loadout.registar_marcadas(con, rep, "a", [m["copy_id"] for m in movs],
                              csv_path=_TMP / "reg.csv")
    fora = [m["copy_id"] for m in movs if m["nm"] != "Swamp Dweller"]
    log = _TMP / "correcoes.log"
    if log.exists():
        log.unlink()

    r = loadout.corrigir_alocacao(con, "a", fora, "ele diz que não as tem",
                                  etiqueta="alocacao-teste", log_path=log)
    assert (r["linhas"], r["copias"]) == (2, 2), r
    assert sorted(alocacao(con)) == [m["copy_id"] for m in movs
                                     if m["nm"] == "Swamp Dweller"]
    assert Path(r["backup"]).exists() and "-alocacao-teste.db" in r["backup"]
    linha = log.read_text(encoding="utf-8").strip()
    assert "corrigir-alocacao slot='a'" in linha, linha
    assert "Wrath of God" in linha and "não as tem" in linha, linha

    r2 = loadout.corrigir_alocacao(con, "a", fora, "outra vez",
                                   etiqueta="alocacao-teste", log_path=log)
    assert r2 == {"linhas": 0, "copias": 0, "backup": None, "copy_ids": []}, r2
    assert log.read_text(encoding="utf-8").strip() == linha, "não repete a linha"
    # E as cópias continuam na colecção: uma correcção de alocação diz onde a
    # carta NÃO está, não que ela deixou de existir.
    assert con.execute("SELECT COUNT(*) c FROM copies").fetchone()["c"] == 3
    repor()
    print("corrigir-alocacao: 2 fora da caixa, backup e log — e idempotente")


def caso_o_auto_registo_so_com_tudo_marcado():
    """A regra do lado do browser: o auto-registo é a ÚLTIMA marca a fechar a
    caixa. Com cartas por marcar quem grava é ele, e leva o resumo à frente —
    gravar sozinho a meio era o vault a decidir o que está na estante."""
    repor()
    con = base()
    js = (RAIZ / "deckboxes.py").read_text(encoding="utf-8")
    assert "if (!montarEstado(c).completo) return;" in js, "o guarda do auto"
    assert "registar(c, $('#b-reg'), 'auto');" in js, "e diz que foi automático"
    # E o botão do painel deixou de mandar o acto antigo: passa pelo mesmo
    # `registar()` da barra, com o resumo e a pergunta.
    assert "data-act=\"${c.confirmar" not in js, "o segundo caminho tem de ter ido"
    assert "for (const b of document.querySelectorAll('[data-reg]'))" in js
    assert "function perguntaRegisto(c, e, faltam)" in js, "o resumo"
    print("auto-registo: so com tudo marcado; o painel usa o mesmo registar()")


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
    for fn in (caso_o_registo_grava_so_as_marcadas,
               caso_sem_lista_nao_se_grava_nada,
               caso_o_registo_completo_fecha_a_caixa,
               caso_o_csv_ganha_uma_linha_por_copia,
               caso_os_outros_caminhos_tambem_deixam_rasto,
               caso_a_correccao_do_cloud_e_idempotente,
               caso_o_auto_registo_so_com_tudo_marcado):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
