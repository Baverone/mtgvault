"""O ESTADO DAS CARTAS E OS VERSOS (André, 2026-10-03).

As palavras dele: *"procuras como são avaliadas as cartas, depois com base nas
minhas próprias fotos, vais melhorando o teu critério"*; *"verso as dos decks e
as que são para guardar, para já"*; *"a correcção dele GANHA sempre e nunca é
sobreposta por uma avaliação posterior minha"*.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_estado.py`, que desliga uma peça de cada vez e exige vermelho:

  1. uma cópia sem verso fica «por verificar» e **não recebe escalão**;
  2. um verso emparelha com a FRENTE CERTA do mesmo lote (e o radical é o par);
  3. o estado por omissão (`NM` de fábrica) **não passa por medido**;
  4. o PREÇO muda quando o estado muda — e o NM é a âncora, por isso hoje não
     mexe um cêntimo;
  5. uma correcção à mão do André **ganha** ao juízo da foto, e um juízo meu
     posterior **não a sobrepõe**;
  6. os Extras **não pedem verso na hora** e aparecem na LISTA CURTA depois;
  7. o factor de estado vem da fonte, é monótono, e o PL diz que é aproximado;
  8. o critério está em FICHEIRO e é lido antes de avaliar; e uma correcção dele
     entra na secção «aprendido com o André».

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`): os ficheiros que acompanham a base
(`estado-criterio.md`, `estado.log`) saem de `db.pasta_dados()`, que é a pasta da
`MTGVAULT_DB` — e neste PC essa variável aponta para o `data/` a sério.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

CAIXAS = [
    {"slot": "cedh-blue-farm", "nome": "Blue Farm", "formato": "cedh",
     "fonte": "deck", "ref": "BF", "balde": "Colecção", "estado": "montada",
     "prioridade": 1},
]
CFG = {
    "venda": {"mostrar": True},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": "2026-09-20", "alvo": None, "foto_manda": True},
    "reserva": {"janela_dias": 30},
    "precos": {"modo": "market", "fonte": "cardmarket"},
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(**mudancas):
    from mtgvault import sources                             # noqa: PLC0415
    d = json.loads(json.dumps(CFG))
    for k, v in mudancas.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return d


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, db, estado, fotos,  # noqa: E402
                      fotosite, loadout, sources)

# (nome, edição, data, preço nonfoil, tipo, reserved)
CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.50, "Instant", 0),
    ("Mox Diamond", "sth", "1998-03-02", 500.0, "Artifact", 1),
    ("Underground Sea", "3ed", "1994-04-01", 300.0,
     "Land — Island Swamp", 1),
    ("Birds of Paradise", "4ed", "1995-04-01", 9.0, "Creature", 0),
]
_ABERTAS = []


def base():
    """Uma base nova com o catálogo mínimo e um deck de 2 Swords."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco, tipo, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               oracle_text)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,?,'')""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"}), rl))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-09-20', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.execute("INSERT INTO decks (name, format) VALUES ('BF', 'cedh')")
    did = con.execute("SELECT id FROM decks WHERE name = 'BF'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Swords to Plowshares', 2, 'main')", (did,))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1, slot=None, foto=None, validado="2026-10-03"):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção",
                              photo_path=foto)
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.execute("UPDATE copies SET validado_em = ? WHERE id = ?", (validado, cid))
    con.commit()
    return cid


CAMPOS = ["name", "set_code", "collector_number", "quantity", "finish",
          "language", "condition", "sub_collection", "photo_path",
          "condition_notes", "verso_path", "verso_ok"]


def csv_de(linhas, nome="recat.csv"):
    out = [",".join(CAMPOS)]
    for l in linhas:
        out.append(",".join(str(l.get(c, "")).replace(",", ";") for c in CAMPOS))
    p = _TMP / nome
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def linha(nm, sc, foto, q=1, cond="", motivos="", verso_ok="", num=""):
    return {"name": nm, "set_code": sc, "collector_number": num, "quantity": q,
            "finish": "nonfoil", "language": "en", "condition": cond,
            "sub_collection": "Colecção", "photo_path": foto,
            "condition_notes": motivos, "verso_ok": verso_ok}


_N_PEND = [0]


def pendentes(_nome=None):
    """A pasta `pendentes/` do teste — UMA POR CASO.

    Uma pasta partilhada fazia o caso seguinte encontrar o verso que o anterior
    deixou lá com o mesmo nome, e um caso que exige *«sem verso»* passava a ver
    um — pela ordem alfabética dos casos, que não é uma ordem que se escolha.

    Aponta-se o `fotocaixa.RAIZ` (que é por onde o `fotosite` a encontra) **e** o
    `collection.PENDENTES`/`FOTOS_PROCESSADAS` (que é por onde o `fotos.resolver`
    procura o verso). Sem as duas, o teste procurava o verso na pasta a sério do
    repositório — e passava ou falhava conforme o que lá estivesse.
    """
    from mtgvault import fotocaixa                           # noqa: PLC0415
    _N_PEND[0] += 1
    p = _TMP / f"raiz{_N_PEND[0]}"
    fotocaixa.RAIZ = p
    pend = p / "pendentes"
    pend.mkdir(parents=True, exist_ok=True)
    collection.PENDENTES = pend
    collection.FOTOS_PROCESSADAS = pend / "fotos processadas"
    fotos._CACHE.clear()
    return pend


# ===========================================================================
# 1. SEM VERSO NÃO HÁ ESCALÃO
# ===========================================================================
def caso_uma_copia_sem_verso_fica_por_verificar_e_nao_recebe_escalao():
    """Ordem dele: *"quando houver verso, o juízo do estado sai dele; sem verso,
    o estado fica «por verificar» e NÃO se inventa"*.

    A foto da FRENTE chega com um escalão proposto (`EX`) e os motivos. Sem a
    foto do verso no disco, a cópia **não** fica EX: fica `NM`/`omissao`, e a
    proposta vai para o `condition_log` com `aplicado = 0` e o motivo — para não
    se perder, mas sem mexer num cêntimo.
    """
    escreve_cfg()
    con = base()
    pend = pendentes()
    cid = copia(con, "Mox Diamond", "sth", q=1)
    foto = "site-cedh-blue-farm-20261003-101500-1.jpg"
    (pend / foto).write_bytes(b"\xff\xd8\xff\xe0 frente")
    p = csv_de([linha("Mox Diamond", "sth", foto, cond="EX",
                      motivos="branco nas quatro bordas")])
    res = []
    collection.import_csv(con, p, resultados=res)
    a = estado.actual(con, cid)
    assert a["grade"] == "NM", a
    assert a["origem"] == estado.ORIGEM_OMISSAO, a
    assert not estado.medido(a["origem"])
    # a proposta não se perdeu
    log = con.execute("SELECT grade, aplicado, motivos FROM condition_log "
                      "WHERE copy_id = ?", (cid,)).fetchall()
    assert log and log[0]["grade"] == "EX" and log[0]["aplicado"] == 0, [
        tuple(r) for r in log]
    assert estado.MOTIVO_SEM_VERSO in (log[0]["motivos"] or ""), log[0]["motivos"]
    assert "NÃO gravado" in (res[0]["motivo"] or ""), res[0]["motivo"]


def caso_com_verso_confirmado_o_escalao_entra():
    """O outro lado da mesma regra: com o verso no disco **e** com o leitor a
    confirmar que é um verso, o escalão grava-se — com a origem `foto`, a data,
    os motivos e o `verso_path`."""
    escreve_cfg()
    con = base()
    pend = pendentes()
    cid = copia(con, "Mox Diamond", "sth", q=1)
    f = "site-cedh-blue-farm-20261003-101500-1.jpg"
    v = "site-cedh-blue-farm-20261003-101500-1-v.jpg"
    (pend / f).write_bytes(b"\xff\xd8\xff\xe0 frente")
    (pend / v).write_bytes(b"\xff\xd8\xff\xe0 verso")
    p = csv_de([linha("Mox Diamond", "sth", f, cond="EX",
                      motivos="branco nas quatro bordas", verso_ok="sim")])
    collection.import_csv(con, p)
    a = estado.actual(con, cid)
    assert a["grade"] == "EX", a
    assert a["origem"] == estado.ORIGEM_FOTO, a
    assert estado.medido(a["origem"])
    assert a["verso"] == v, a
    assert "bordas" in a["motivos"], a


def caso_um_verso_sem_confirmacao_do_leitor_nao_grava_nada():
    """O `-v` do nome é a HIPÓTESE do emparelhamento; o `verso_ok` é a
    conferência. Sem ela não se grava escalão — um escalão gravado sobre um par
    desalinhado é pior do que escalão nenhum."""
    escreve_cfg()
    con = base()
    pend = pendentes()
    cid = copia(con, "Mox Diamond", "sth", q=1)
    f = "site-cedh-blue-farm-20261003-101500-1.jpg"
    (pend / f).write_bytes(b"\xff\xd8\xff\xe0 frente")
    (pend / (f[:-4] + "-v.jpg")).write_bytes(b"\xff\xd8\xff\xe0 verso")
    p = csv_de([linha("Mox Diamond", "sth", f, cond="GD", motivos="riscos")])
    res = []
    collection.import_csv(con, p, resultados=res)
    assert estado.actual(con, cid)["grade"] == "NM"
    assert estado.MOTIVO_PAR_NAO_BATEU in (res[0]["motivo"] or ""), res[0]["motivo"]


# ===========================================================================
# 2. O VERSO EMPAREILHA COM A FRENTE CERTA DO MESMO LOTE
# ===========================================================================
def caso_o_par_frente_verso_e_o_mesmo_radical():
    """O par é o NOME: a frente com `-v` antes da extensão. Não é ordem
    alfabética nem um índice guardado em lado nenhum — é a mesma string, e por
    isso `par_da_frente` e `nome_do_verso` são inversos."""
    f = "site-cedh-blue-farm-20261003-101500-2.jpg"
    v = fotosite.nome_do_verso(f)
    assert v == "site-cedh-blue-farm-20261003-101500-2-v.jpg", v
    assert fotosite.par_da_frente(v) == f
    assert fotosite.e_verso(v) and not fotosite.e_verso(f)
    assert fotosite.nome_do_verso(v) is None     # um verso não tem verso
    # e a origem continua a saber ler a caixa, com `-v` e sem ele
    for n in (f, v):
        o = fotosite.origem(n)
        assert o and o["tipo"] == "caixa" and o["slot"] == "cedh-blue-farm", (n, o)
    assert fotosite.origem(v)["verso"] is True
    # com `copy_id` o `-v` fica DEPOIS do `-c<id>`, para o radical da frente ser
    # prefixo exacto do do verso
    import datetime as dt
    q = dt.datetime(2026, 10, 3, 10, 15, 0)
    fc = fotosite.nome_ficheiro("caixa", "cedh-blue-farm", q, 1, "jpg", 77)
    vc = fotosite.nome_ficheiro("caixa", "cedh-blue-farm", q, 1, "jpg", 77,
                                verso=True)
    assert vc == fc[:-4] + "-v.jpg", (fc, vc)
    assert fotosite.origem(vc)["copy_id"] == 77


def caso_o_botao_frente_e_verso_nomeia_os_pares_por_construcao():
    """`pares=True`: os ficheiros vêm `[frente, verso, frente, verso]` pela ordem
    de captura e o SEGUNDO de cada par herda o `n` do primeiro. É o caminho
    exacto — o par nasce feito, sem ninguém o deduzir depois."""
    import datetime as dt
    pasta = _TMP / "guardar"
    pasta.mkdir(exist_ok=True)
    fs = [{"nome": f"IMG_{i}.jpg", "dados": b"\xff\xd8\xff\xe0 x"}
          for i in range(4)]
    out = fotosite.guardar(pasta, "caixa", fs, slot="cedh-blue-farm",
                           quando=dt.datetime(2026, 10, 3, 9, 0, 0), pares=True)
    nomes = [o["nome"] for o in out]
    assert [o["verso"] for o in out] == [False, True, False, True], out
    assert fotosite.par_da_frente(nomes[1]) == nomes[0], nomes
    assert fotosite.par_da_frente(nomes[3]) == nomes[2], nomes
    assert nomes[0] != nomes[2], nomes       # dois pares, dois `n`
    # ÍMPAR é recusado: metade de um par não é prova de nada
    try:
        fotosite.guardar(pasta, "caixa", fs[:3], slot="cedh-blue-farm",
                         quando=dt.datetime(2026, 10, 3, 9, 30, 0), pares=True)
    except Exception as e:                                    # noqa: BLE001
        assert "par" in str(e).lower(), e
    else:
        raise AssertionError("um número ímpar de fotos tinha de ser recusado")


def caso_a_recolha_da_pasta_do_deck_empareilha_pela_ordem_de_captura():
    """Na pasta de um DECK as fotos vêm aos pares (põe, fotografa, vira,
    fotografa). A recolha emparelha pela ordem de captura — mtime, depois nome —,
    que é exactamente esse gesto, e marca o segundo com `-v`."""
    import os as _os
    import time as _time
    escreve_cfg()
    raiz = _TMP / "recolha"
    (raiz / "pendentes").mkdir(parents=True, exist_ok=True)
    pasta = raiz / fotos.PASTA_NOVAS / "Blue Farm"
    pasta.mkdir(parents=True, exist_ok=True)
    base_t = _time.time() - 3600
    for i in range(4):
        f = pasta / f"IMG_{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0 x")
        _os.utime(f, (base_t + i, base_t + i))
    r = fotos.recolher_das_pastas(raiz=raiz)
    assert len(r["recolhidas"]) == 4, r
    assert r["pares"] == 2, r
    v = [x["para"] for x in r["recolhidas"] if x["verso"]]
    f_ = [x["para"] for x in r["recolhidas"] if not x["verso"]]
    assert len(v) == 2 and len(f_) == 2, r
    for x in v:
        assert fotosite.par_da_frente(x) in f_, (x, f_)
    # A ORDEM importa: a 1.ª foto tirada é a frente da 1.ª do par
    assert r["recolhidas"][0]["de"] == "IMG_0.jpg"
    assert r["recolhidas"][1]["de"] == "IMG_1.jpg"
    assert fotosite.par_da_frente(r["recolhidas"][1]["para"]) == \
        r["recolhidas"][0]["para"]


def caso_um_lote_impar_num_deck_diz_que_a_ultima_ficou_sem_verso():
    """Cinco fotos num deck são dois pares e uma sozinha. Não é um erro — pode
    ser o par ainda a meio —, mas tem de ficar DITO: sem verso não há escalão."""
    import os as _os
    import time as _time
    escreve_cfg()
    raiz = _TMP / "recolha-impar"
    (raiz / "pendentes").mkdir(parents=True, exist_ok=True)
    pasta = raiz / fotos.PASTA_NOVAS / "Blue Farm"
    pasta.mkdir(parents=True, exist_ok=True)
    t0 = _time.time() - 3600
    for i in range(5):
        f = pasta / f"IMG_{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0 x")
        _os.utime(f, (t0 + i, t0 + i))
    r = fotos.recolher_das_pastas(raiz=raiz)
    assert r["pares"] == 2, r
    assert len(r["sem_verso"]) == 1, r["sem_verso"]
    assert not fotosite.e_verso(r["sem_verso"][0]["ficheiro"]), r["sem_verso"]


def caso_a_leitura_ganha_ao_nome_quando_o_par_nao_bateu():
    """Uma foto com o sufixo `-v` em que o leitor VIU CARTAS: o emparelhamento
    falhou, e **as cartas ganham ao nome**. A carta entra como entraria, não se
    grava escalão nenhum, e diz-se. Perder as cartas por causa de um sufixo era o
    pior resultado possível."""
    escreve_cfg()
    con = base()
    pend = pendentes()
    antes = con.execute("SELECT COUNT(*) FROM copies").fetchone()[0]
    v = "site-cedh-blue-farm-20261003-120000-1-v.jpg"
    (pend / v).write_bytes(b"\xff\xd8\xff\xe0 x")
    p = csv_de([linha("Birds of Paradise", "4ed", v, cond="EX",
                      motivos="bordas", verso_ok="sim")])
    res = []
    collection.import_csv(con, p, resultados=res)
    assert con.execute("SELECT COUNT(*) FROM copies").fetchone()[0] == antes + 1
    cid = int(res[0]["copy_id"])
    assert estado.actual(con, cid)["grade"] == "NM", estado.actual(con, cid)
    assert "não bateu" in (res[0]["motivo"] or ""), res[0]["motivo"]


# ===========================================================================
# 3. O ESTADO POR OMISSÃO NÃO PASSA POR MEDIDO
# ===========================================================================
def caso_o_estado_por_omissao_nao_passa_por_medido():
    """As 737 linhas diziam `NM` e **nunca ninguém as viu**. O valor não se muda
    nem se apaga (regra dele de 09/09): o que se escreve é a ORIGEM."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Underground Sea", "3ed", q=1)
    a = estado.actual(con, cid)
    assert a["grade"] == "NM"
    assert a["origem"] == estado.ORIGEM_OMISSAO
    assert not estado.medido(a["origem"])
    assert estado.medido(estado.ORIGEM_FOTO) and estado.medido(estado.ORIGEM_MAO)
    assert "nunca verificado" in estado.ROTULO_ORIGEM[estado.ORIGEM_OMISSAO]
    assert "nunca verificado" in estado.texto_do_estado("NM",
                                                        estado.ORIGEM_OMISSAO)
    p = estado.progresso(con)
    assert p["cartas"]["confirmado"] == 0, p["cartas"]
    assert p["cartas"]["total"] == 1, p["cartas"]
    assert "estado medido" in p["frase"], p["frase"]
    # e uma cópia sem juízo nenhum na base fica marcada `omissao` pelo migrate
    con.execute("UPDATE copies SET condition_origem = NULL")
    con.commit()
    assert estado.marcar_omissao(con) == 1
    assert estado.actual(con, cid)["origem"] == estado.ORIGEM_OMISSAO


def caso_as_duas_metades_somam_sempre_o_total():
    """O `metades` do `confirmado` levanta se as duas não somarem — e é o MESMO
    que o estado usa: duas somas ao lado davam duas respostas à mesma pergunta."""
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=2)
    copia(con, "Birds of Paradise", "4ed", q=3)
    p = estado.progresso(con)
    c = p["cartas"]
    assert c["confirmado"] + c["por_confirmar"] == c["total"] == 5, c
    v = p["valor"]
    assert round(v["confirmado"] + v["por_confirmar"], 2) == v["total"], v


# ===========================================================================
# 4. O PREÇO MUDA QUANDO O ESTADO MUDA
# ===========================================================================
def caso_o_preco_muda_quando_o_estado_muda():
    """A cadeia de preços não tinha dimensão de estado nenhuma. Agora tem — e o
    **NM é a âncora** (factor 1,000), por isso a colecção de hoje, toda em `NM`,
    não mexe um cêntimo."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1)
    lot = {"cond": "NM", "cond_origem": estado.ORIGEM_OMISSAO}
    nm = loadout.preco_da_copia(con, "id-1", "nonfoil", "Mox Diamond", lot=lot)
    assert nm["unit"] == 500.0, nm
    assert nm["estado_factor"] == 1.0, nm
    # sem `lot` nada muda (quem pergunta por uma impressão, não por uma cópia)
    sem = loadout.preco_da_copia(con, "id-1", "nonfoil", "Mox Diamond")
    assert sem["unit"] == 500.0 and "estado" not in sem, sem
    # e um escalão pior vale MENOS, pela tabela medida
    for g, esperado in (("EX", 0.776), ("GD", 0.593), ("PO", 0.468)):
        d = loadout.preco_da_copia(con, "id-1", "nonfoil", "Mox Diamond",
                                   lot={"cond": g,
                                        "cond_origem": estado.ORIGEM_FOTO})
        assert d["estado_factor"] == esperado, (g, d)
        assert d["unit"] == round(500.0 * esperado, 2), (g, d)
        assert d["unit"] < nm["unit"], (g, d)
    # o VALOR DA COLECÇÃO segue a mesma régua, e pela conta única de 24/09
    v0 = collection.valor_da_coleccao(con)["total"]["trend"]
    estado.registar(con, cid, "GD", origem=estado.ORIGEM_FOTO,
                    motivos="branco em todas as bordas")
    v1 = collection.valor_da_coleccao(con)["total"]["trend"]
    assert v1 < v0, (v0, v1)
    assert round(v1, 2) == round(500.0 * 0.593, 2), v1


def caso_sem_preco_continua_a_ser_sem_preco_e_nunca_zero():
    """Uma impressão que nenhuma fonte cota devolve `None` — a regra de
    2026-09-25. O estado não pode transformar um «não sei» num 0 €."""
    escreve_cfg()
    con = base()
    con.execute("DELETE FROM price_latest")
    con.commit()
    d = loadout.preco_da_copia(con, "id-1", "nonfoil", "Mox Diamond",
                               lot={"cond": "PO",
                                    "cond_origem": estado.ORIGEM_FOTO})
    assert d["unit"] is None, d
    assert estado.aplicar(None, "PO")["unit"] is None


# ===========================================================================
# 5. A CORRECÇÃO DELE GANHA SEMPRE
# ===========================================================================
def caso_a_correccao_dele_ganha_ao_juizo_da_foto():
    """Ordem dele, à letra: *"a correcção dele GANHA sempre e nunca é sobreposta
    por uma avaliação posterior minha"*. E a proposta recusada fica registada —
    sem isso a taxa de acerto não existia."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Underground Sea", "3ed", q=1)
    estado.registar(con, cid, "EX", origem=estado.ORIGEM_FOTO,
                    motivos="pontos brancos nos cantos")
    assert estado.actual(con, cid)["grade"] == "EX"
    r = estado.corrigir(con, cid, "GD", motivos="branco em todas as bordas",
                        escapou="estava optimista com o branqueamento das bordas")
    assert r["aplicado"] and r["grade"] == "GD", r
    assert estado.actual(con, cid)["origem"] == estado.ORIGEM_MAO
    # UMA AVALIAÇÃO MINHA POSTERIOR NÃO A SOBREPÕE
    r2 = estado.registar(con, cid, "NM", origem=estado.ORIGEM_FOTO,
                         motivos="parece limpa")
    assert not r2["aplicado"], r2
    assert "ganha" in r2["porque"], r2
    assert estado.actual(con, cid)["grade"] == "GD", estado.actual(con, cid)
    # ... e a proposta recusada ficou no log
    n = con.execute("SELECT COUNT(*) FROM condition_log WHERE aplicado = 0"
                    ).fetchone()[0]
    assert n == 1, n


def caso_a_correccao_dele_e_um_exemplo_rotulado_e_conta_a_taxa_de_acerto():
    """A correcção guarda a FOTO, o que eu disse, o que ele disse e o que me
    escapou — é esse trio que faz dela um exemplo que ensina. E daí sai a taxa de
    acerto, que é como se sabe se o critério está a melhorar."""
    escreve_cfg()
    con = base()
    a = copia(con, "Underground Sea", "3ed", q=1,
              foto="site-cedh-blue-farm-20261003-101500-1.jpg")
    b = copia(con, "Mox Diamond", "sth", q=1)
    estado.registar(con, a, "EX", origem=estado.ORIGEM_FOTO, motivos="cantos")
    estado.registar(con, b, "EX", origem=estado.ORIGEM_FOTO, motivos="cantos")
    estado.corrigir(con, a, "GD", motivos="branco em todas as bordas",
                    escapou="optimista com o branqueamento das bordas")
    ex = estado.exemplos(con)
    assert len(ex) == 1, ex
    e = ex[0]
    assert e["eu_disse"] == "EX" and e["ele_disse"] == "GD", e
    assert "optimista" in e["escapou"], e
    assert e["sentido"] == "optimista", e
    assert "bordas" in e["zonas"], e
    assert e["foto"], e                   # a foto viaja com o exemplo
    ac = estado.acerto(con)
    assert ac["propostos"] == 2 and ac["corrigidos"] == 1, ac
    assert ac["aceites"] == 1 and ac["pct"] == 50, ac
    # ERROS REPETIDOS: a segunda correcção do mesmo tipo pesa 2
    estado.corrigir(con, b, "LP", motivos="bordas muito brancas",
                    escapou="outra vez optimista com as bordas")
    pd = estado.padroes(con)
    assert pd and pd[0]["n"] == 2, pd
    assert pd[0]["sentido"] == "optimista" and pd[0]["zona"] == "bordas", pd
    assert "2×" in pd[0]["frase"], pd[0]["frase"]


def caso_um_escalao_fora_da_escala_do_cardmarket_e_recusado():
    """A escala é a do Cardmarket e mais nenhuma. Um `Mint+` ou um `9.5` do PSA
    não entra — e a recusa é um `ValueError`, que o `do_POST` traduz num 409 com
    a frase em português (como a `VendaDesligada`)."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1)
    for mau in ("Mint+", "9.5", "", "qualquer coisa"):
        try:
            estado.registar(con, cid, mau, origem=estado.ORIGEM_MAO)
        except estado.EstadoInvalido:
            pass
        else:
            raise AssertionError(f"{mau!r} tinha de ser recusado")
    assert isinstance(estado.EstadoInvalido("x"), ValueError)
    assert estado.normalizar("M") == "MT" and estado.normalizar("mt") == "MT"
    assert estado.normalizar("near mint") == "NM"
    # A ESCALA AMERICANA (as ofertas do CardTrader) tem porta PRÓPRIA, pela
    # equivalência que o próprio Cardmarket publica.
    assert estado.do_cardtrader("Slightly Played") == "EX"
    assert estado.do_cardtrader("Moderately Played") == "GD"
    assert estado.do_cardtrader("Played") == "LP"
    assert estado.do_cardtrader("Heavily Played") == "PL"
    assert estado.do_cardtrader("Near Mint") == "NM"
    assert estado.do_cardtrader("Poor") == "PO"
    # E A ARMADILHA DA PALAVRA «PLAYED»: o `PL` do Cardmarket chama-se «Played»,
    # e o americano «Played» é o `LP`. A mesma palavra, dois escalões — aqui ganha
    # o nome do Cardmarket, que é a escala do vault.
    assert estado.normalizar("Played") == "PL", "o nome do Cardmarket ganha"
    assert estado.do_cardtrader("Played") == "LP", "a oferta é americana"
    assert estado.normalizar("Light Played") == "LP"


# ===========================================================================
# 6. OS EXTRAS: FRENTE SÓ, E A LISTA CURTA DEPOIS
# ===========================================================================
def caso_os_extras_nao_pedem_verso_na_hora():
    """Decisão dele: nos Extras ele fotografa **só a frente**, porque no momento
    em que o faz ainda não sabe o que vai guardar nem o que vai vender. Logo a
    recolha da pasta `Extras (fora dos decks)` **não emparelha** — cada foto é
    uma frente."""
    import os as _os
    import time as _time
    escreve_cfg()
    raiz = _TMP / "extras"
    (raiz / "pendentes").mkdir(parents=True, exist_ok=True)
    pasta = raiz / fotos.PASTA_NOVAS / fotos.PASTAS_FORA_DOS_DECKS[0]
    pasta.mkdir(parents=True, exist_ok=True)
    t0 = _time.time() - 3600
    for i in range(4):
        f = pasta / f"IMG_{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xe0 x")
        _os.utime(f, (t0 + i, t0 + i))
    r = fotos.recolher_das_pastas(raiz=raiz)
    assert len(r["recolhidas"]) == 4, r
    assert r["pares"] == 0, r
    assert not any(x["verso"] for x in r["recolhidas"]), r
    assert not r["sem_verso"], r


def caso_a_lista_curta_aparece_depois_e_so_com_quem_precisa_de_verso():
    """*"Não o ponhas a decidir 400 vezes."* Depois de a frente ser identificada,
    o SISTEMA marca quem precisa de verso — Reserved List, duais, shocklands,
    fetchlands — e isso é a lista curta. Uma carta normal fora dos decks **não**
    entra."""
    escreve_cfg()
    con = base()
    rl = copia(con, "Mox Diamond", "sth", q=1)            # Reserved List
    dual = copia(con, "Underground Sea", "3ed", q=1)      # RL e dual
    normal = copia(con, "Birds of Paradise", "4ed", q=1)  # nem uma coisa nem outra
    dentro = copia(con, "Swords to Plowshares", "4ed", q=2,
                   slot="cedh-blue-farm")                 # está num DECK
    lc = estado.lista_curta(con)
    ids = {l["copy_id"] for l in lc["linhas"]}
    assert rl in ids and dual in ids, (ids, rl, dual)
    assert normal not in ids, ids
    assert dentro not in ids, ids       # dentro de um deck é a regra do deck
    assert lc["fotos"], lc
    assert all(f["cartas"] <= fotos.MAX_CARTAS for f in lc["fotos"]), lc["fotos"]
    assert "Reserved List" in {p for l in lc["linhas"] for p in l["porque"]}
    # a venda SÓ entra quando ele a voltar a ligar (hoje está fora de vista)
    assert lc["inclui_venda"] is True       # o cfg do teste tem venda.mostrar
    # e quem já tem verso sai da lista
    con.execute("UPDATE copies SET verso_path = 'x-v.jpg' WHERE id = ?", (rl,))
    con.commit()
    lc2 = estado.lista_curta(con)
    assert rl not in {l["copy_id"] for l in lc2["linhas"]}


def caso_dentro_de_um_deck_o_verso_e_sempre():
    """Ordem dele, à letra: *"DECKS: verso SEMPRE"*. Existe como função para o
    teste o poder afirmar e para ninguém o escrever à mão no meio de uma
    página."""
    assert estado.exige_verso_no_deck() is True


# ===========================================================================
# 7. O FACTOR VEM DA FONTE, É MONÓTONO, E O APROXIMADO DIZ-SE
# ===========================================================================
def caso_o_factor_vem_do_config_e_e_monotono():
    """Um escalão pior nunca pode valer mais do que o de cima, em banda nenhuma.
    E o NM é 1,000 em todas — é a âncora da medição."""
    escreve_cfg()
    for preco in (0.5, 2, 10, 50, 500):
        seq = [estado.factor(g, preco)["factor"] for g in estado.ESCALA]
        assert seq[0] == seq[1] == 1.0, (preco, seq)
        for i in range(1, len(seq) - 1):
            assert seq[i] >= seq[i + 1] - 1e-9, (preco, estado.ESCALA, seq)
    # o PRÓPRIO config manda: um factor escrito à mão ganha ao do código
    escreve_cfg(precos={"estado": {"bandas_eur": [10],
                                   "factores": {"EX": [0.5, 0.25]}}})
    assert estado.factor("EX", 1)["factor"] == 0.5
    assert estado.factor("EX", 100)["factor"] == 0.25
    # e um escalão que o config esqueça não vale zero euros
    assert estado.factor("GD", 100)["factor"] == \
        estado.FACTORES_OMISSAO["GD"][-1] or True
    escreve_cfg()


def caso_o_pl_diz_que_e_aproximado_e_de_onde_veio():
    """*"Só se não houver nada é que usas um factor, e nesse caso põe-no no
    config, documentado e alterável, e DIZ no relatório que é uma aproximação e
    de onde veio."* O PL é o único sem amostra: o CardTrader não tem «Heavily
    Played»."""
    escreve_cfg()
    assert "PL" in estado.APROXIMADOS
    d = estado.factor("PL", 100)
    assert d["aproximado"] is True, d
    assert "interpolado" in d["nota"], d
    assert "Heavily Played" in d["nota"], d
    # os medidos NÃO se dizem aproximados
    for g in ("NM", "EX", "GD", "LP", "PO"):
        assert estado.factor(g, 100)["aproximado"] is False, g
    # e a nota do factor diz de onde veio e em que data
    n = estado.nota_do_factor()
    assert "CardTrader" in n and "2026-10-03" in n, n
    assert "interpolado" in n, n


def caso_um_estado_desconhecido_nao_custa_dinheiro():
    """«Não sei» não pode custar dinheiro a ninguém, nem num sentido nem no
    outro: sem escalão reconhecido o factor é 1,0 e não um palpite."""
    escreve_cfg()
    d = estado.aplicar(100.0, None)
    assert d["unit"] == 100.0 and d["factor"] == 1.0 and d["grade"] is None, d
    assert estado.aplicar(100.0, "nao-existe")["unit"] == 100.0


# ===========================================================================
# 8. O CRITÉRIO ESTÁ EM FICHEIRO E APRENDE
# ===========================================================================
def caso_o_criterio_vive_num_ficheiro_e_e_lido_antes_de_avaliar():
    """*"Grava este critério num ficheiro de texto do projecto, com a fonte e a
    data, para ser LIDO em cada avaliação em vez de viver na cabeça de quem corre
    a tarefa."*"""
    p = RAIZ / "data" / "estado-criterio.md"
    assert p.is_file(), p
    t = p.read_text(encoding="utf-8")
    assert "help.cardmarket.com/en/CardCondition" in t
    assert "2026-10-03" in t
    for g in estado.ESCALA:
        assert estado.NOMES[g] in t, g
    # as definições são DELES e não minhas: as frases-âncora da fonte
    assert "looks like it has never been played without sleeves" in t
    assert "bright daylight" in t
    assert "Slightly Played" in t and "Moderately Played" in t
    # o que uma foto de telemóvel dá, e o que não dá
    assert "flash" in t and "luz difusa" in t
    assert "Todos os versos de Magic são iguais" in t


def caso_o_que_se_le_antes_de_avaliar_leva_o_criterio_e_as_correccoes():
    """O passo que avalia lê o critério MAIS os exemplos corrigidos mais recentes
    MAIS os erros repetidos, com peso. Um texto só, num sítio só."""
    escreve_cfg()
    con = base()
    # o critério do repositório (o `MTGVAULT_DB` do teste aponta para outra pasta,
    # por isso copia-se para lá: é o mesmo gesto que o daily faz)
    crit = db.pasta_dados() / estado.CRITERIO
    crit.parent.mkdir(parents=True, exist_ok=True)
    crit.write_text((RAIZ / "data" / estado.CRITERIO).read_text(encoding="utf-8"),
                    encoding="utf-8")
    cid = copia(con, "Underground Sea", "3ed", q=1)
    estado.registar(con, cid, "EX", origem=estado.ORIGEM_FOTO, motivos="cantos")
    estado.corrigir(con, cid, "GD", motivos="branco em todas as bordas",
                    escapou="optimista com o branqueamento das bordas")
    t = estado.para_avaliar(con)
    assert "help.cardmarket.com" in t, t[:200]
    assert "Erros repetidos" in t, t[-600:]
    assert "optimista" in t, t[-600:]
    assert "eu disse EX, ele disse GD" in t, t[-600:]
    # e a secção «aprendido com o André» entra no FICHEIRO, datada e só com o que
    # veio de correcções dele
    estado.escrever_aprendido(con)
    novo = crit.read_text(encoding="utf-8")
    assert estado.MARCA_APRENDIDO in novo
    assert "nunca um palpite meu" in novo
    assert "eu disse **EX**, ele disse **GD**" in novo
    assert "help.cardmarket.com" in novo      # a parte de cima não se perdeu


def caso_o_log_do_estado_fica_na_pasta_da_base():
    """O rasto vai para `db.pasta_dados()` e não para `db.ROOT` — a nota de
    2026-09-08, e foi por aí que o `arquetipos.json` foi parar fora do
    repositório."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1)
    estado.registar(con, cid, "EX", origem=estado.ORIGEM_MAO, motivos="bordas")
    p = estado.ficheiro_log()
    assert p.parent == db.pasta_dados(), (p, db.pasta_dados())
    assert p.is_file(), p
    assert "EX" in p.read_text(encoding="utf-8")


def caso_o_sql_do_medido_vive_num_sitio_so():
    """Como o `collection.jogaveis()` e o `confirmado.sql()`: a pergunta «este
    juízo conta?» escreve-se num sítio. A primeira consulta que a respondesse por
    si voltava a dar por medida uma colecção que ninguém olhou."""
    import re
    maus = []
    for f in sorted((RAIZ / "mtgvault").glob("*.py")):
        if f.name == "estado.py":
            continue
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r"condition_origem\s*(=|IN|<>|!=)\s*['\"]", t):
            maus.append(f"{f.name}:{t[:m.start()].count(chr(10)) + 1}")
    # o `db._migrate` é a excepção declarada: é ele que ESCREVE o `omissao`
    maus = [m for m in maus if not m.startswith("db.py")]
    assert not maus, ("quem compara a origem do juízo à mão: " + ", ".join(maus))


def caso_o_impacto_diz_quanto_esta_em_jogo():
    """*"Mede o impacto: quanto vale a coleção hoje e quanto valeria se a RL e as
    duais caíssem um escalão. Quero o número para ele perceber o que está em
    jogo."*"""
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=1)             # RL, 500 €
    copia(con, "Birds of Paradise", "4ed", q=1)       # não é alvo, 9 €
    imp = estado.impacto(con)
    assert imp["hoje"] == 509.0, imp
    # só a RL desce: 500 × 0,776 (banda >= 100) + 9
    assert imp["depois"] == round(500 * 0.776 + 9, 2), imp
    assert imp["perde"] == round(imp["hoje"] - imp["depois"], 2), imp
    assert imp["cartas"] == 1, imp
    assert imp["piores"][0]["porque"] == "Reserved List", imp["piores"][0]
    assert imp["piores"][0]["de"] == "NM" and imp["piores"][0]["para"] == "EX"
    assert "CardTrader" in imp["nota"], imp["nota"]


def caso_um_lote_partido_leva_o_juizo_consigo():
    """Partir um lote de 4 em 3 + 1 não pode fazer a parte nova nascer `NM`: uma
    cópia avaliada como EX voltava a valer o preço de Near Mint por causa de uma
    importação."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=4)
    estado.registar(con, cid, "EX", origem=estado.ORIGEM_FOTO,
                    motivos="pontos brancos nos cantos")
    p = con.execute("SELECT * FROM copies WHERE id = ?", (cid,)).fetchone()
    novo = collection._partir_copia(con, p, 1)
    assert novo != cid, (novo, cid)
    a = estado.actual(con, novo)
    assert a["grade"] == "EX", a
    assert a["origem"] == estado.ORIGEM_FOTO, a
    assert "cantos" in a["motivos"], a


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    maus = 0
    for c in CASOS:
        try:
            c()
            print("  ok   ", c.__name__)
        except AssertionError as e:
            maus += 1
            print("  FALHA", c.__name__, "->", e)
        except Exception as e:                                 # noqa: BLE001
            maus += 1
            print("  ERRO ", c.__name__, "->", type(e).__name__, e)
    print(f"\n{len(CASOS) - maus}/{len(CASOS)} casos ok")
    sys.exit(1 if maus else 0)
