"""A FOTO É A VERDADE, E A BASE É O REGISTO DELA (André, 2026-10-02).

As palavras dele: *"cada deck tem as suas cartas"*; *"o que eu colocar de fotos
no deck, é daquele deck, ponto"*; *"se não tiver foto, não tem carta"*; *"assim
fico responsável por cada vez que comprar cartas, ter que tirar a foto para
atualizar"*.

Cada caso aqui CHUMBA se a funcionalidade for retirada — a prova está em
`tests/_chumba_foto_manda.py`, que desliga uma peça de cada vez e exige vermelho:

  1. uma cópia sem foto não conta para *"o deck está completo"*;
  2. uma cópia sem foto nunca entra na lista de venda — e sai por uma saída
     PRÓPRIA (`sem_foto`), nunca confundida com as `protegidas`;
  3. uma foto largada na pasta do deck X aloca a cópia ao deck X **mesmo que ela
     estivesse noutro** (até 02/10 era o contrário: o registo ganhava à foto);
  4. uma foto nos `Extras (fora dos decks)` TIRA a alocação;
  5. uma segunda alocação da mesma cópia é RECUSADA, e as duas que já existem na
     base dele ficam como conflito visível (ordem dele: não se resolvem);
  6. uma carta nova numa pasta de deck cria a cópia **já alocada** a esse deck —
     é assim que uma compra entra («comprar = fotografar»);
  7. o «confirmado» e o «por confirmar» somam SEMPRE o total, e nunca se mostra
     só uma das metades;
  8. nada se apagou: as cópias sem foto continuam na base e continuam a valer.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
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
    {"slot": "cedh-cloud", "nome": "Cloud cEDH", "formato": "cedh",
     "fonte": "deck", "ref": "CL", "balde": "Colecção", "estado": "montada",
     "prioridade": 2},
]
CFG = {
    "venda": {"mostrar": True},          # para a lista de venda existir no teste
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
}
CAMINHO = _TMP / "cfg.json"


def escreve_cfg(**mudancas):
    """O config do teste, com as mudanças pedidas. Reescreve-se o ficheiro e
    limpa-se a cache do `sources`: é assim que se exercita o INTERRUPTOR."""
    from mtgvault import sources                             # noqa: PLC0415
    d = json.loads(json.dumps(CFG))
    for k, v in mudancas.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    return d


CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, confirmado, db, fotos,  # noqa: E402
                      fotosite, loadout, sources, venda)

SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.50, "Instant"),
    ("Birds of Paradise", "4ed", "1995-04-01", 9.0, "Creature"),
    ("Wasteland", "tmp", "1997-10-14", 80.0, "Land"),
    ("Mox Diamond", "sth", "1998-03-02", 500.0, "Artifact"),
]
_ABERTAS = []


def base(deck=None):
    """Uma base nova com o catálogo mínimo e um deck de 2 cartas por caixa."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-09-20', ?, ?)", (f"id-{i}", preco, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    # Os dois decks: cada um pede 2 Swords to Plowshares.
    for ref, nome in (("BF", "Blue Farm"), ("CL", "Cloud cEDH")):
        con.execute("INSERT INTO decks (name, format) VALUES (?, 'cedh')", (ref,))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (ref,)).fetchone()["id"]
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, 'Swords to Plowshares', 2, 'main')", (did,))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1, slot=None, foto=None, validado=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção",
                              photo_path=foto)
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.execute("UPDATE copies SET validado_em = ? WHERE id = ?", (validado, cid))
    con.commit()
    return cid


def alocacoes(con, cid=None):
    q = "SELECT copy_id, slot, quantity FROM copy_allocation"
    rows = con.execute(q).fetchall()
    return {(r["copy_id"], r["slot"]): r["quantity"] for r in rows
            if cid is None or r["copy_id"] == cid}


def csv_de(linhas, nome="recat.csv"):
    campos = ["name", "set_code", "collector_number", "quantity", "finish",
              "language", "condition", "sub_collection", "photo_path"]
    out = [",".join(campos)]
    for l in linhas:
        out.append(",".join(str(l.get(c, "")) for c in campos))
    p = _TMP / nome
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def linha(nm, sc, foto, q=1, num=""):
    return {"name": nm, "set_code": sc, "collector_number": num, "quantity": q,
            "finish": "nonfoil", "language": "en", "condition": "NM",
            "sub_collection": "Colecção", "photo_path": foto}


def linhas_e_cartas(con):
    r = con.execute("SELECT COUNT(*), COALESCE(SUM(quantity),0) "
                    "FROM copies").fetchone()
    return (r[0], r[1])


# ===========================================================================
# 1. SEM FOTO NÃO CONTA PARA «O DECK ESTÁ COMPLETO»
# ===========================================================================
def caso_uma_copia_sem_foto_nao_fecha_o_deck():
    """*"se não tiver foto, não tem carta"*. Duas Swords na caixa do Blue Farm,
    nenhuma fotografada nesta campanha: fisicamente o deck está a 100 %, e a
    pergunta *"está completo?"* tem de responder 0 %.

    E as DUAS metades vão no slot: `pct` (a decisão) e `pct_fisico` (a carta está
    mesmo na gaveta). Mostrar só a primeira era dizer-lhe que não tem nada.
    """
    escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
    rep = loadout.report(con)
    bf = next(s for s in rep["slots"] if s["slot"] == "cedh-blue-farm")
    assert bf["pct_fisico"] == 100, bf["pct_fisico"]
    assert bf["pct"] == 0, f"sem foto o deck não está completo: {bf['pct']}"
    assert bf["tenho_conf"] == 0 and bf["tenho_fisico"] == 2, bf
    # A falta que se tapa com a CÂMARA e não com a carteira:
    assert bf["fotografar"] == 2, bf["fotografar"]
    assert bf["comprar"] == 0, "não se compra o que ele tem em casa"


def caso_com_foto_desta_campanha_o_deck_fecha():
    """A outra metade da mesma regra: com a foto, conta. Sem este caso o teste de
    cima passaria com um `pct` sempre a zero."""
    escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm",
          foto="site-cedh-blue-farm-20261002-120000-1.jpg", validado="2026-10-02")
    rep = loadout.report(con)
    bf = next(s for s in rep["slots"] if s["slot"] == "cedh-blue-farm")
    assert bf["pct"] == 100 and bf["tenho_conf"] == 2, bf
    assert bf["fotografar"] == 0, bf["fotografar"]


def caso_o_interruptor_devolve_o_vault_ao_que_era():
    """`foto_manda: false` — o padrão do `venda.mostrar`. *"Para já"* é literal:
    desligar tem de devolver exactamente os números de antes."""
    escreve_cfg(revalidacao={"foto_manda": False})
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
    rep = loadout.report(con)
    bf = next(s for s in rep["slots"] if s["slot"] == "cedh-blue-farm")
    assert rep["foto_manda"] is False, rep["foto_manda"]
    assert bf["pct"] == 100 == bf["pct_fisico"], bf
    assert not rep.get("sem_foto"), "com a regra desligada nada sai por falta de foto"
    escreve_cfg()


# ===========================================================================
# 2. NADA SE VENDE SEM FOTO — E É UMA SAÍDA PRÓPRIA
# ===========================================================================
def caso_uma_copia_sem_foto_nunca_entra_na_venda():
    """Um excedente a sério (6 Wasteland, nenhum deck as pede) não vai à venda
    sem foto desta campanha — e sai em `sem_foto`, **não** em `protegidas`:
    ordem dele, *"separa os dois motivos na saída, que são coisas diferentes"*.
    Uma é decisão tomada, a outra é decisão por tomar.
    """
    escreve_cfg()
    con = base()
    copia(con, "Wasteland", "tmp", q=6)
    rep = loadout.report(con)
    assert rep["copias"] == 0, f"a venda tinha de estar vazia: {rep['venda']}"
    # SAO DUAS e nao seis: o playset de 4 ja guarda quatro como backup
    # (`CONSTRUCTED_LIMIT`), e so o que passa disso e excedente.
    assert rep["copias_sem_foto"] == 2, rep["copias_sem_foto"]
    linhas = rep["sem_foto"]
    assert linhas and all("sem foto" in (l["reason"] or "").lower() for l in linhas), linhas
    # e NÃO se misturou com as protegidas
    assert all(l["nm"] != "Wasteland" for l in rep["protegidas"]), rep["protegidas"]
    # o motivo diz-lhe o que fazer, em português
    assert "tira-lhe a foto" in linhas[0]["motivo"], linhas[0]["motivo"]


def caso_com_foto_o_excedente_volta_a_vender_se():
    """A outra metade: fotografada, a mesma cópia aparece na venda. É o que torna
    o caso de cima uma trava e não um «a venda está sempre vazia»."""
    escreve_cfg()
    con = base()
    copia(con, "Wasteland", "tmp", q=6, foto="site-colecao-20261002-120000-1.jpg",
          validado="2026-10-02")
    rep = loadout.report(con)
    assert rep["copias"] == 2, rep["venda"]      # as 4 do playset ficam de backup
    assert rep["copias_sem_foto"] == 0, rep["sem_foto"]


def caso_a_saida_sem_foto_entra_no_fica_de_fora_da_exportacao():
    """O «fica de fora» do CSV do Cardmarket tem de dizer esta saída, senão 114
    cópias desaparecem da exportação sem uma linha a explicar porquê — que é o
    padrão do `event_tier` aplicado ao que vale mais dinheiro."""
    escreve_cfg()
    con = base()
    copia(con, "Wasteland", "tmp", q=6)
    rep = loadout.report(con)
    fora = venda.fora_da_exportacao(rep)
    chaves = [b["chave"] if isinstance(b, dict) and "chave" in b else b.get("k")
              for b in fora]
    assert "sem_foto" in [c for c in chaves if c], chaves
    bloco = next(b for b in fora if (b.get("chave") or b.get("k")) == "sem_foto")
    assert bloco["copias"] == 2, bloco
    assert bloco["linhas"] and "foto" in bloco["linhas"][0]["motivo"], bloco


# ===========================================================================
# 3. A FOTO MANDA NA ALOCAÇÃO
# ===========================================================================
def caso_a_foto_na_pasta_do_deck_aloca_a_copia_a_esse_deck():
    """*"o que eu colocar de fotos no deck, é daquele deck, ponto"*.

    A cópia está registada no Cloud cEDH; a foto é largada na pasta do Blue Farm.
    GANHA A FOTO: a cópia passa ao Blue Farm e SAI do Cloud. Até 02/10 era o
    contrário — a `copy_allocation` ganhava (o ponto 5 de 09/09), e a foto não
    mexia uma linha de alocação.
    """
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1, slot="cedh-cloud")
    assert alocacoes(con, cid) == {(cid, "cedh-cloud"): 1}
    foto = "site-cedh-blue-farm-20261002-120000-1.jpg"
    p = csv_de([linha("Mox Diamond", "sth", foto)], nome="mv.csv")
    res: list[dict] = []
    collection.import_csv(con, p, resultados=res)
    assert res[0]["resultado"] == "importada", res
    assert alocacoes(con, cid) == {(cid, "cedh-blue-farm"): 1}, alocacoes(con, cid)
    # não se criou uma cópia nova: a foto LIGOU-SE à que existia
    assert linhas_e_cartas(con) == (1, 1), linhas_e_cartas(con)
    # e ficou confirmada
    v = con.execute("SELECT validado_em FROM copies WHERE id = ?",
                    (cid,)).fetchone()["validado_em"]
    assert v, "a foto desta campanha confirma a cópia"


def caso_a_foto_nos_extras_tira_a_alocacao():
    """*"Foto em `Extras (fora dos decks)` = cópia SEM deck."* A pasta dos Extras
    vale como alvo `coleccao` desde 02/10 de manhã; agora também TIRA a cópia do
    deck onde ela estava registada — a foto prova que está fora."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1, slot="cedh-cloud")
    foto = "site-colecao-20261002-120000-7.jpg"
    p = csv_de([linha("Mox Diamond", "sth", foto)], nome="ex.csv")
    collection.import_csv(con, p, resultados=[])
    assert alocacoes(con, cid) == {}, alocacoes(con, cid)
    assert linhas_e_cartas(con) == (1, 1), "e a cópia continua lá — nada se apaga"


def caso_uma_foto_largada_a_mao_nao_mexe_na_alocacao():
    """Uma foto sem prefixo (largada na raiz de `pendentes/`) **não** diz de que
    deck é. Aí não se toca na alocação: usar o alvo GLOBAL do config para
    reescrever alocações fazia uma foto solta mudar o deck de uma carta por causa
    de um botão carregado ontem. A ordem dele é sobre a PASTA."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1, slot="cedh-cloud")
    p = csv_de([linha("Mox Diamond", "sth", "qualquer-coisa.jpg")], nome="mao.csv")
    collection.import_csv(con, p, resultados=[])
    assert alocacoes(con, cid) == {(cid, "cedh-cloud"): 1}, alocacoes(con, cid)


def caso_a_mudanca_de_deck_fica_no_log():
    """A foto passou a poder TIRAR uma cópia do deck onde estava registada, e isso
    é a única coisa que se perde. Vai para `data/foto-manda.log`, pela razão do
    `revalidacao.log` e do `desmontar.log`."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1, slot="cedh-cloud")
    log = _TMP / "fm.log"
    if log.exists():
        log.unlink()
    mv = confirmado.alocar_por_foto(con, cid, "cedh-blue-farm", log_path=log)
    assert mv["mudou"] and mv["saiu"], mv
    texto = log.read_text(encoding="utf-8")
    assert "saiu-do-deck" in texto and "entrou-no-deck" in texto, texto
    assert str(cid) in texto, texto


# ===========================================================================
# 4. CADA DECK AS SUAS CARTAS: NENHUMA ALOCAÇÃO DUPLA NOVA
# ===========================================================================
def caso_uma_segunda_alocacao_da_mesma_copia_e_recusada():
    """*"cada deck tem as suas cartas"*. Uma cópia de UMA carta já no Cloud não
    pode passar a estar também no Blue Farm. Levanta `confirmado.AlocacaoDupla`,
    que é `ValueError` — é assim que o `webapp` a traduz num 409 com a frase em
    português, como a `VendaDesligada` e a `VendaCongelada`."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Mox Diamond", "sth", q=1, slot="cedh-cloud")
    try:
        confirmado.exige_uma_so(con, cid, "cedh-blue-farm", 1)
    except confirmado.AlocacaoDupla as e:
        assert isinstance(e, ValueError), "o webapp apanha ValueError"
        assert "dois decks" in str(e) or "dois sítios" in str(e), str(e)
    else:
        raise AssertionError("uma alocação dupla nova tinha de ser recusada")
    # e nada se escreveu
    assert alocacoes(con, cid) == {(cid, "cedh-cloud"): 1}, alocacoes(con, cid)


def caso_a_sobrealocacao_e_recusada_mesmo_com_a_regra_desligada():
    """Alocar 3 cópias de um lote de 2 é a mesma carta física em dois sítios, e
    isso é impossível com a regra ligada ou desligada — era já hoje impossível e
    nada o travava."""
    escreve_cfg(revalidacao={"foto_manda": False})
    con = base()
    cid = copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-cloud")
    try:
        confirmado.exige_alocacao_unica(con, [(cid, "cedh-cloud", 3)])
    except confirmado.AlocacaoDupla as e:
        assert "dois sítios" in str(e), str(e)
    else:
        raise AssertionError("a sobre-alocação tinha de ser recusada")
    escreve_cfg()


def caso_os_escritores_da_alocacao_passam_todos_pela_trava():
    """A trava tem de estar nos CAMINHOS e não na confiança de que ninguém faz
    mal. São quatro escritores — o *"sleevado e na caixa"* (`registar_marcadas`),
    o *"já arrumei tudo"* (`guardar_arrumacao`), o *"actualizei"*
    (`actualizar_caixa`) e a encomenda que a foto fecha —, e o que este caso
    exige é que cada um PERGUNTE à trava antes de escrever. Sem isto, o primeiro
    caminho novo que se esquecesse voltava a poder criar a segunda alocação em
    silêncio: é a lição do `e_foil` e do `vistoId`.

    Verifica-se com um espião e não com um cenário por escritor: o que interessa
    aqui é que a pergunta é FEITA; a resposta dela já está trancada nos dois
    casos de cima.

    (Pelo caminho da interface o caso nem chega à trava: uma caixa dedicada não
    VÊ uma cópia que está noutra, por isso o painel nunca a oferece para marcar.
    A trava é a segunda linha de defesa, e é essa que se mede.)
    """
    escreve_cfg()
    con = base()
    cid = copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm",
                foto="site-cedh-blue-farm-20261002-120000-1.jpg",
                validado="2026-10-02")
    rep = loadout.report(con)
    chamadas = []
    real = confirmado.exige_alocacao_unica

    def espia(c, linhas, **kw):
        chamadas.append([tuple(l) for l in linhas])
        return real(c, linhas, **kw)

    loadout._conf.exige_alocacao_unica = espia
    try:
        loadout.registar_marcadas(con, rep, "cedh-blue-farm", marcadas=[cid],
                                  csv_path=_TMP / "rm.csv")
        assert chamadas, "o «sleevado e na caixa» não perguntou à trava"
        n = len(chamadas)
        loadout.guardar_arrumacao(con, rep, csv_path=_TMP / "ga.csv")
        assert len(chamadas) > n, "o «já arrumei tudo» não perguntou à trava"
        n = len(chamadas)
        loadout.actualizar_caixa(con, rep, "cedh-blue-farm",
                                 csv_path=_TMP / "ac.csv")
        assert len(chamadas) > n, "o «actualizei» não perguntou à trava"
    finally:
        loadout._conf.exige_alocacao_unica = real


def caso_as_duas_duplas_da_base_dele_ficam_como_conflito_visivel():
    """Ordem dele: *"não as resolvas por ti: marca-as como CONFLITO visível"*.
    Uma dupla que JÁ existe não se apaga nem bloqueia uma gravação da mesma caixa
    — aparece em `conflitos`, com o diagnóstico certo: as duas da base dele são
    LOTES PARTIDOS (as quantidades somam a do lote), e por isso hoje nenhuma
    carta física está em dois sítios."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-cloud")
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                "VALUES (?, 'cedh-blue-farm', 1)", (cid,))
    con.execute("UPDATE copy_allocation SET quantity = 1 WHERE copy_id = ? "
                "AND slot = 'cedh-cloud'", (cid,))
    con.commit()
    cs = confirmado.conflitos(con)
    assert len(cs) == 1 and cs[0]["copy_id"] == cid, cs
    assert cs[0]["soma"] == 2 and not cs[0]["sobrealocada"], cs[0]
    assert "lote partido" in cs[0]["motivo"], cs[0]["motivo"]
    assert sorted(cs[0]["decks"]) == ["Blue Farm", "Cloud cEDH"], cs[0]["decks"]
    # e é GRANDFATHERADA: validar o mesmo estado não levanta
    confirmado.exige_alocacao_unica(
        con, [(cid, "cedh-cloud", 1), (cid, "cedh-blue-farm", 1)])
    # ... e vai no relatório, à vista
    rep = loadout.report(con)
    assert len(rep["conflitos_alocacao"]) == 1, rep["conflitos_alocacao"]


# ===========================================================================
# 5. COMPRAR = FOTOGRAFAR
# ===========================================================================
def caso_uma_carta_nova_na_pasta_do_deck_nasce_ja_alocada():
    """*"assim fico responsável por cada vez que comprar cartas, ter que tirar a
    foto para atualizar"*. Uma carta que a base NÃO tem, fotografada na pasta de
    um deck: cria a cópia, marcada «nova nesta campanha» com a data, e **já
    alocada a esse deck**. É assim que uma compra entra."""
    escreve_cfg()
    con = base()
    assert linhas_e_cartas(con) == (0, 0)
    foto = "site-cedh-blue-farm-20261002-120000-3.jpg"
    p = csv_de([linha("Birds of Paradise", "4ed", foto, q=1)], nome="nova.csv")
    res: list[dict] = []
    collection.import_csv(con, p, resultados=res)
    assert res[0]["resultado"] == "importada", res
    cid = int(res[0]["copy_id"])
    assert alocacoes(con, cid) == {(cid, "cedh-blue-farm"): 1}, alocacoes(con, cid)
    r = con.execute("SELECT notes, validado_em FROM copies WHERE id = ?",
                    (cid,)).fetchone()
    assert "nova nesta campanha" in (r["notes"] or ""), r["notes"]
    assert r["validado_em"], "nasce confirmada: a foto é a prova"


# ===========================================================================
# 6. AS DUAS METADES SOMAM SEMPRE, E NUNCA SE MOSTRA SÓ UMA
# ===========================================================================
def caso_as_duas_metades_somam_sempre_o_total():
    """A regra de apresentação dele: *"todo o número tem duas metades, lado a
    lado — nunca só uma"*. O `metades()` é o único sítio que as compõe e
    **levanta** se não somarem: uma metade perdida pelo caminho dá um par de
    números com cara de honesto que está errado, sem um único passo a falhar."""
    escreve_cfg()
    m = confirmado.metades(3, 10)
    assert (m["confirmado"], m["por_confirmar"], m["total"]) == (3, 7, 10), m
    assert m["confirmado"] + m["por_confirmar"] == m["total"]
    assert m["pct"] == 30, m
    assert set(m) >= {"confirmado", "por_confirmar", "total", "pct", "frase"}, m
    e = confirmado.euros(0, 1820.85)
    assert e["por_confirmar"] == 1820.85 and e["confirmado"] == 0, e
    assert "por confirmar" in e["frase"], e["frase"]


def caso_metades_que_nao_somam_levantam():
    """A trava da trava: o `metades` não aceita um «confirmado» maior do que o
    total. Sem isto, um erro de contagem passava por um número honesto."""
    try:
        confirmado.metades(11, 10)
    except confirmado.MetadesQueNaoSomam:
        raise AssertionError("11 de 10 devia dar por_confirmar negativo, não "
                             "um erro de soma") from None
    except Exception:                                        # noqa: BLE001
        pass
    # o caso que importa: forçar uma soma errada tem de levantar
    try:
        confirmado.metades(1, 2, casas=0)
    except confirmado.MetadesQueNaoSomam as e:               # pragma: no cover
        raise AssertionError(f"1 e 2 somam: {e}") from None
    m = confirmado.metades(1, 2)
    assert m["por_confirmar"] == 1, m


def caso_a_frase_honesta_diz_x_de_y():
    """*«X de 1 678 cartas confirmadas por foto»* — a linha que vai em cada
    página. Com a regra desligada diz só o total: uma frase a prometer uma regra
    que não está ligada é pior do que frase nenhuma."""
    escreve_cfg()
    f0 = confirmado.frase(0, 1678)
    assert f0 == "0 de 1 678 cartas confirmadas por foto", repr(f0)
    assert confirmado.frase(1678, 1678) == "as 1 678 cartas estão confirmadas por foto"
    escreve_cfg(revalidacao={"foto_manda": False})
    assert confirmado.frase(0, 1678) == "1 678 cartas", confirmado.frase(0, 1678)
    escreve_cfg()


def caso_o_relatorio_leva_as_duas_metades_no_topo():
    """As páginas não podem ter de somar isto por si — a segunda que o fizesse
    dava outro número. Vão no topo do relatório, feitas."""
    escreve_cfg()
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
    rep = loadout.report(con)
    m = rep["cartas_metades"]
    assert m["confirmado"] + m["por_confirmar"] == m["total"], m
    assert rep["tenho_conf_total"] + rep["fotografar_total"] == rep["tenho_fisico_total"]


# ===========================================================================
# 7. NADA SE APAGOU
# ===========================================================================
def caso_uma_copia_sem_foto_continua_na_base_e_continua_a_valer():
    """*Sem foto* quer dizer *ainda não conta*, nunca *não existe* (regra dele de
    09/09: nada se apaga). A cópia continua na `copies`, continua `jogaveis()` e
    continua a contar para o VALOR da colecção — é o total que mostra as duas
    metades, não o que esconde uma."""
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=1)
    assert linhas_e_cartas(con) == (1, 1)
    v = collection.valor_da_coleccao(con)
    assert v["q"] == 1, v
    total = v["total"][collection.cenario_em_vigor()]
    assert total and total > 0, v["total"]
    # e o filtro do «conta» NÃO é o `jogaveis`: esse não se tocou
    assert "validado_em" not in collection.jogaveis(), collection.jogaveis()


def caso_o_sql_do_confirmado_vive_num_sitio_so():
    """Era `cp.validado_em IS NOT NULL` à mão em cada consulta nova — a lição do
    `collection.jogaveis()`, do `e_foil` e do `precos.sql()`. Varre-se o código à
    procura do literal: a primeira consulta que se esquecesse da regra voltava a
    dizer-lhe que tem a carta, sem um único erro."""
    assert "validado_em IS NOT NULL" in confirmado.sql()
    maus = []
    for f in sorted((RAIZ / "mtgvault").glob("*.py")):
        if f.name == "confirmado.py":
            continue
        t = f.read_text(encoding="utf-8")
        for i, l in enumerate(t.splitlines(), 1):
            if "validado_em IS NOT NULL" in l or "validado_em is not null" in l:
                maus.append(f"{f.name}:{i}")
    assert not maus, ("o SQL do «confirmado por foto» vive em `confirmado.sql()`: "
                      + ", ".join(maus))


# ===========================================================================
# 8. O PROGRESSO
# ===========================================================================
def caso_o_progresso_da_as_duas_metades_por_deck_e_em_euros():
    """*"é o que ele vai olhar todos os dias enquanto fotografa"*: por deck e no
    total, quantas cartas confirmadas, quantas faltam, e quanto falta em valor.
    Não conta nada por si — a contagem é a `revalidacao.progresso` de 20/09."""
    escreve_cfg()
    con = base()
    copia(con, "Mox Diamond", "sth", q=1, slot="cedh-blue-farm")
    copia(con, "Wasteland", "tmp", q=1, slot="cedh-blue-farm",
          foto="site-cedh-blue-farm-20261002-120000-9.jpg", validado="2026-10-02")
    rep = loadout.report(con)
    p = confirmado.progresso(con, rep)
    bf = next(g for g in p["caixas"] if g["slot"] == "cedh-blue-farm")
    assert bf["cartas"]["total"] == 2 and bf["cartas"]["confirmado"] == 1, bf["cartas"]
    assert bf["valor"]["total"] > bf["valor"]["confirmado"] > 0, bf["valor"]
    assert bf["falta_valor"] == round(bf["valor"]["total"]
                                      - bf["valor"]["confirmado"], 2), bf["valor"]
    t = p["total"]["cartas"]
    assert t["confirmado"] + t["por_confirmar"] == t["total"] == 2, t
    assert "confirmadas por foto" in p["frase"], p["frase"]


def caso_o_progresso_nao_esconde_os_conflitos():
    """O progresso é o ecrã que ele abre todos os dias: os conflitos de alocação
    dupla vão lá, senão ficam numa página que ninguém abre."""
    escreve_cfg()
    con = base()
    cid = copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-cloud")
    con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                "VALUES (?, 'cedh-blue-farm', 1)", (cid,))
    con.execute("UPDATE copy_allocation SET quantity = 1 WHERE copy_id = ? "
                "AND slot = 'cedh-cloud'", (cid,))
    con.commit()
    p = confirmado.progresso(con, None)
    assert len(p["conflitos"]) == 1, p["conflitos"]


# ===========================================================================
# 9. O TECTO DE PLAYSET DO PREMODERN FOI-SE (ordem dele, no mesmo dia)
# ===========================================================================
def caso_o_tecto_de_playset_deixou_de_ter_efeito():
    """Ele mandou ESQUECER a regra do *"máximo um playset"* em Premodern. Um
    `playset_maximo: 4` esquecido num config deixa de ter efeito — como o
    `dedicado: false` desde 19/09 —, em vez de se apagar a chave e deixar quem a
    tivesse escrita sem saber porque é que parou de funcionar."""
    assert loadout.playset_maximo({"playset_maximo": 4}) is None
    assert loadout.playset_maximo({}) is None
    assert loadout.limites_de_playset([]) == []


def caso_o_config_a_serio_ja_nao_tem_tecto_de_playset():
    """E a chave saiu do `colecao_config.json` a sério: deixá-la lá era o ficheiro
    a documentar uma regra que já não existe. Este caso lê o config DELE."""
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    com = [r.get("grupo") for r in cfg.get("regras_por_formato") or []
           if r.get("playset_maximo")]
    assert not com, f"o tecto de playset foi-se a 02/10/2026: {com}"


def caso_o_de_conversao_continua_a_apanhar_o_premodern():
    """O `fases.de_conversao` derivava-se do `playset_maximo`; sem a chave
    responderia «nenhuma caixa é de conversão», em silêncio, e a Fase 2 perdia a
    ordem de trabalho dele. O sinal passou a ser o `prioridade_por: "pct"` do
    grupo — e a resposta tem de ser a MESMA."""
    from mtgvault import fases                               # noqa: PLC0415
    cfg = {"regras_por_formato": [
        {"grupo": "premodern", "prioridade_por": "pct"},
        {"grupo": "cedh"},
    ]}
    res = {"slots": [{"slot": "a", "grupo": "premodern"},
                     {"slot": "b", "grupo": "premodern"},
                     {"slot": "c", "grupo": "cedh"}]}
    d = fases.de_conversao(res, cfg)
    assert d == {"a": True, "b": True, "c": False}, d
    # uma caixa sozinha no grupo não é «de conversão»: não há com quem converter
    res1 = {"slots": [{"slot": "a", "grupo": "premodern"}]}
    assert fases.de_conversao(res1, cfg) == {"a": False}


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
