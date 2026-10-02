"""A PASTA POR DECK VALE COMO ALVO (André, 2026-10-01, à letra: «o melhor é
criar pasta»).

Ele quer fotografar com a app da câmara e largar as fotos numa pasta com o nome
do deck, em `Colocar fotos da coleção aqui\\<Nome do deck>\\` — e isso tem de
ser tratado **exactamente** como se tivesse carregado em «Fotografar este deck»
e tirado a foto na página. Até hoje **nada no vault lia essa pasta**: o
`mtg-fotos-novas` e o `processar_fotos.py` só olham para a RAIZ de `pendentes/`,
e as fotos ficavam lá para sempre sem um único erro — o padrão do `event_tier`.

O que aqui se tranca, e cada caso CHUMBA se a funcionalidade for retirada:

  1. uma foto `x.jpg` em `Colocar fotos da coleção aqui\\Blue Farm\\` é
     reconhecida com o slot `cedh-blue-farm`;
  2. o mesmo numa **subpasta de lote** (`lote1`, e mais abaixo ainda);
  3. **renomear uma caixa no config muda a pasta reconhecida sem tocar em
     código** — o mapa é DERIVADO do `caixas`, nunca uma lista escrita à mão;
  4. a recolha MOVE a foto para a raiz de `pendentes/` com o nome
     `site-<slot>-…`, e é por isso que o `revalidacao.alvo_da_foto` lhe dá o
     alvo certo: um caminho só, o que já estava testado;
  5. as pastas de GRUPO (`Premodern (geral)`, `SPML (…)`, `Coleção Pessoal`,
     `Vender`) **não** valem como alvo e ficam com o comportamento de sempre —
     a foto fica lá, e diz-se porquê;
  6. o `_plano.txt` de uma caixa com um PLAYSET põe as 4 cópias na MESMA foto;
  7. **nenhuma foto de plano passa de 4 cartas**, em nenhum deck;
  8. uma caixa VAZIA não rebenta a geração (e o `_plano.txt` dela não promete
     fotos que não existem).

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`: os ficheiros que acompanham a base
saem da pasta da `MTGVAULT_DB`, e sem a fixar a bateria escrevia no `data/` a
sério).
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
    {"slot": "premodern-elves", "nome": "Elves / Survival", "formato": "premodern",
     "fonte": "deck", "ref": "EL", "balde": "Colecção", "estado": "montada",
     "prioridade": 2},
    {"slot": "modern", "nome": "Modern — UW Oswald", "formato": "legacy",
     "fonte": "deck", "ref": "MO", "balde": "Colecção", "estado": "candidata",
     "prioridade": 3},
]
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil"},
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "edicoes": "premodern", "estrita": True},
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": "2026-09-20", "alvo": None},
    "reserva": {"limiar_pct": 20},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, db, fases, fotocaixa,  # noqa: E402
                      fotos, fotosite, loadout, revalidacao, sources)

# A RAIZ do «site» (onde vive a pasta das fotos e a `pendentes/`) é a pasta de
# teste — nunca o repositório. O `fotocaixa.RAIZ` é o que o `fotos.pasta_novas`
# e o `fotosite.pasta_pendentes` lêem.
SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)
fotocaixa.RAIZ = SITE

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"], 1.50, "Instant"),
    ("Force of Will", "all", "1996-06-10", ["nonfoil", "foil"], 60.0, "Instant"),
    ("Birds of Paradise", "4ed", "1995-04-01", ["nonfoil"], 9.0, "Creature"),
    ("Wasteland", "tmp", "1997-10-14", ["nonfoil"], 80.0, "Land"),
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
    for i, (nm, sc, rel, fin, preco, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(fin), rel,
             json.dumps({"legacy": "legal", "premodern": "legal"})))
        for f in fin:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-20', ?)", (f"id-{i}", f, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    listas = (("BF", "cedh", [("Swords to Plowshares", 4), ("Birds of Paradise", 1),
                              ("Wasteland", 1), ("Force of Will", 1)]),
              ("EL", "premodern", [("Birds of Paradise", 1)]),
              ("MO", "legacy", [("Force of Will", 1)]))
    for nome, fmt, cartas in listas:
        con.execute("INSERT INTO decks (name, format) VALUES (?,?)", (nome, fmt))
        did = con.execute("SELECT id FROM decks WHERE name = ?",
                          (nome,)).fetchone()["id"]
        for nm, q in cartas:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?, 'main')", (did, nm, q))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1, lang="en", finish="nonfoil", slot=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language=lang,
                              finish=finish, sub_collection="Colecção")
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.commit()
    return cid


def mundo():
    """A `cedh-blue-farm` montada, com um PLAYSET e três singletons de tipos
    diferentes lá dentro — é o que faz o plano ter mais do que um grupo."""
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=4, slot="cedh-blue-farm")
    copia(con, "Birds of Paradise", "4ed", q=1, slot="cedh-blue-farm")
    copia(con, "Wasteland", "tmp", q=1, slot="cedh-blue-farm")
    copia(con, "Force of Will", "all", q=1, slot="cedh-blue-farm")
    return con


def repor(caixas=None):
    cfg = json.loads(json.dumps(CFG))
    if caixas is not None:
        cfg["caixas"] = caixas
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return cfg


def pasta(nome, *sub):
    d = fotos.pasta_novas()
    for p in (nome, *sub):
        d = d / p
    d.mkdir(parents=True, exist_ok=True)
    return d


def larga(nome_pasta, ficheiro, *sub, antiga=True):
    """Uma «foto» numa pasta de deck. `antiga` põe-lhe um mtime de ontem, para
    passar o sossego (uma foto ainda a ser copiada não se move)."""
    f = pasta(nome_pasta, *sub) / ficheiro
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    if antiga:
        os.utime(f, (1_700_000_000, 1_700_000_000))
    return f


def limpar_pendentes():
    p = fotosite.pasta_pendentes(SITE)
    if p.is_dir():
        for f in p.glob("*"):
            if f.is_file():
                f.unlink()
    fotos._CACHE.clear()


# ===========================================================================
# 1-2. A PASTA (e a subpasta de lote) DIZEM O DECK
# ===========================================================================
def caso_uma_foto_na_pasta_do_deck_e_reconhecida():
    """`Colocar fotos da coleção aqui\\Blue Farm\\x.jpg` → `cedh-blue-farm`.

    É o caso que ele pediu à letra. Sem o mapa pasta → slot, `slot_da_pasta`
    devolve `None` e a foto fica numa pasta que ninguém lê.
    """
    repor()
    f = larga("Blue Farm", "x.jpg")
    assert fotos.slot_da_pasta(f) == "cedh-blue-farm", f
    # E pelo caminho RELATIVO também (é a forma que um CSV pode trazer).
    assert fotos.slot_da_pasta("Blue Farm/x.jpg") == "cedh-blue-farm"
    f.unlink()
    print("uma foto na pasta 'Blue Farm' da o slot cedh-blue-farm")


def caso_a_subpasta_de_lote_conta_para_o_mesmo_deck():
    """`Blue Farm\\lote1\\x.jpg` é o MESMO deck — o LEIA-ME sempre disse que se
    podiam fazer subpastas de lote, e perdê-las aqui era mudar-lhe a rotina sem
    o avisar. O que manda é a PRIMEIRA pasta abaixo da pasta-mãe."""
    repor()
    f1 = larga("Blue Farm", "a.jpg", "lote1")
    f2 = larga("Blue Farm", "b.jpg", "lote1", "mais fundo")
    assert fotos.slot_da_pasta(f1) == "cedh-blue-farm", f1
    assert fotos.slot_da_pasta(f2) == "cedh-blue-farm", f2
    # Uma foto na pasta-MÃE não tem deck: aí não se adivinha nada.
    mae = fotos.pasta_novas() / "solta.jpg"
    assert fotos.slot_da_pasta(mae) is None, mae
    f1.unlink()
    f2.unlink()
    print("as subpastas de lote contam para o mesmo deck; a pasta-mae nao tem deck")


# ===========================================================================
# 3. O MAPA É DERIVADO DO CONFIG, NÃO ESCRITO À MÃO
# ===========================================================================
def caso_renomear_a_caixa_muda_a_pasta_sem_tocar_em_codigo():
    """O mapa sai do `caixas` do config. Uma lista escrita à mão (no vault ou,
    pior, na tarefa `mtg-fotos-novas`) ficava desactualizada no dia em que ele
    renomeasse um deck — e a pasta nova deixava de ser lida, em silêncio."""
    repor()
    assert fotos.slot_da_pasta("Blue Farm/x.jpg") == "cedh-blue-farm"
    novas = json.loads(json.dumps(CAIXAS))
    novas[0]["nome"] = "Blue Farm 2.0"
    repor(novas)
    assert fotos.slot_da_pasta("Blue Farm 2.0/x.jpg") == "cedh-blue-farm"
    assert fotos.slot_da_pasta("Blue Farm/x.jpg") is None, \
        "o nome antigo deixa de valer — é o config que manda"
    repor()
    assert fotos.slot_da_pasta("Blue Farm/x.jpg") == "cedh-blue-farm"
    print("renomear a caixa no config muda a pasta reconhecida, sem tocar em codigo")


def caso_a_pasta_aceita_as_duas_formas_do_nome_e_o_slot():
    """A «Elves / Survival» não cabe num caminho: a pasta à mão tem ` - `. As
    duas formas valem (`fotos.nome_de_pasta`, a MESMA regra por que o
    `_plano.txt` se escreve), e o próprio `slot` também — mas o NOME ganha
    sempre, para um slot não poder roubar a pasta de outra caixa."""
    repor()
    # O nome do config tem `/`, que não cabe num caminho: o MAPA tem de o
    # conhecer nas duas formas, e é a forma com ` - ` que existe no disco.
    mapa = fotos.mapa_pastas()
    assert mapa[fotos._norm("Elves / Survival")] == "premodern-elves", mapa
    for p in ("Elves - Survival", "elves survival", "premodern-elves"):
        assert fotos.slot_da_pasta(f"{p}/x.jpg") == "premodern-elves", p
    # O travessão do «Modern — UW Oswald» não pode depender de ele acertar.
    for p in ("Modern — UW Oswald", "Modern - UW Oswald", "modern uw oswald"):
        assert fotos.slot_da_pasta(f"{p}/x.jpg") == "modern", p
    assert fotos.nome_de_pasta("Elves / Survival") == "Elves - Survival"
    print("as duas formas do nome, o slot e o travessao dao todos o mesmo slot")


# ===========================================================================
# 4. UM CAMINHO SÓ: a foto passa a `pendentes/` com o nome do alvo
# ===========================================================================
def caso_a_recolha_move_a_foto_com_o_nome_do_alvo():
    """A foto da pasta fica a chamar-se `site-<slot>-…`, que é o nome que o botão
    «Tirar fotos» escreve — e por isso o `revalidacao.alvo_da_foto` dá-lhe a
    caixa certa **sem uma linha nova**. Escrever um segundo caminho ao lado era
    deixar os dois discordarem um dia, em silêncio.

    E MOVE-SE: a pasta fica limpa para o lote seguinte, o original é que fica
    ligado à cópia, e nada se apaga.
    """
    repor()
    limpar_pendentes()
    con = mundo()
    f = larga("Blue Farm", "IMG_4711.jpg")
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert len(r["recolhidas"]) == 1, r
    x = r["recolhidas"][0]
    assert x["slot"] == "cedh-blue-farm" and x["de"] == "IMG_4711.jpg", x
    assert not f.exists(), "a foto tem de SAIR da pasta do deck"
    novo = fotosite.pasta_pendentes(SITE) / x["para"]
    assert novo.is_file(), novo
    # O nome é o do site, e o `fotosite.origem` lê-o como uma foto de caixa.
    o = fotosite.origem(novo.name)
    assert o and o["tipo"] == "caixa" and o["slot"] == "cedh-blue-farm", (novo.name, o)
    # E é isso que faz o passo (0) da revalidação preferir as cópias desta caixa.
    alvo, primeiro = revalidacao.alvo_da_foto(con, novo.name, {}, None)
    assert alvo and alvo["tipo"] == "caixa" and alvo["slot"] == "cedh-blue-farm", alvo
    assert alvo["copias"], "o alvo tem de trazer as cópias da caixa"
    assert primeiro is None
    # Duas fotos no mesmo segundo não se pisam.
    larga("Blue Farm", "a.jpg")
    larga("Blue Farm", "b.jpg")
    r2 = fotos.recolher_das_pastas(raiz=SITE)
    nomes = {y["para"] for y in r2["recolhidas"]}
    assert len(nomes) == 2, r2
    assert all((fotosite.pasta_pendentes(SITE) / n).is_file() for n in nomes)
    limpar_pendentes()
    print("a recolha move a foto para pendentes/ com o nome site-<slot>- e o alvo bate")


def caso_uma_foto_ainda_a_ser_copiada_nao_se_mexe():
    """Uma foto acabada de largar (do telemóvel, da app do GitHub) pode estar a
    meio da cópia: movê-la era partir o ficheiro. Espera-se o sossego, e ela vem
    na corrida seguinte — como o `mtg-fotos-novas` já faz com os 2 minutos."""
    repor()
    limpar_pendentes()
    f = larga("Blue Farm", "fresca.jpg", antiga=False)
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert not r["recolhidas"] and len(r["a_chegar"]) == 1, r
    assert f.exists(), "a foto fica onde está"
    f.unlink()
    print("uma foto ainda a ser copiada fica na pasta e diz-se que esta a chegar")


# ===========================================================================
# 5. AS PASTAS DE GRUPO FICAM COMO SEMPRE FORAM
# ===========================================================================
def caso_as_pastas_de_grupo_nao_valem_como_alvo():
    """`Premodern (geral)`, `SPML (…)`, `Coleção Pessoal` e `Vender` não são um
    deck: ninguém as processa automaticamente, e era assim antes disto. A foto
    fica lá — mas **diz-se porquê**, que é a diferença entre «decidido» e
    «esquecido»."""
    repor()
    limpar_pendentes()
    f = larga("Vender", "v.jpg")
    g = larga("Premodern (geral)", "p.jpg")
    h = larga("Pasta que ele inventou", "q.jpg")
    for x in (f, g, h):
        assert fotos.slot_da_pasta(x) is None, x
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert not r["recolhidas"], r
    assert len(r["ignorados"]) == 3, r["ignorados"]
    porques = {i["ficheiro"]: i["porque"] for i in r["ignorados"]}
    assert "grupo" in porques["v.jpg"] and "grupo" in porques["p.jpg"], porques
    assert "não é o nome de nenhuma caixa" in porques["q.jpg"], porques
    assert all(x.exists() for x in (f, g, h)), "nada se mexe nem se apaga"
    for x in (f, g, h):
        x.unlink()
    print("as pastas de grupo e as desconhecidas ficam como estavam, com o porque")


def caso_a_pasta_de_nomes_antigos_fica_de_fora():
    """O supervisor mudou duas pastas com nomes antigos para `_nomes antigos\\`
    em vez de as apagar (a regra dele de 09/09). Uma pasta que começa por `_`
    não é um deck — e o `_plano.txt` também não é uma imagem."""
    repor()
    larga("_nomes antigos", "velha.jpg", "Pauper Affinity")
    (pasta("Blue Farm") / "_plano.txt").write_text("x", encoding="utf-8")
    itens = fotos.fotos_nas_pastas(raiz=SITE)
    assert not [i for i in itens if "nomes antigos" in str(i["ficheiro"])], itens
    assert not [i for i in itens if i["ficheiro"].name == "_plano.txt"], itens
    print("a pasta _nomes antigos e o _plano.txt ficam fora da recolha")


# ===========================================================================
# 6-8. O `_plano.txt`
# ===========================================================================
def caso_o_plano_de_um_playset_poe_as_quatro_na_mesma_foto():
    """A regra dele, à letra: *"se sao 4 fotos, e 1 foto com as 4 cartas"*. Um
    playset é UMA foto, não quatro — foi a regra errada que esteve escrita na
    manhã deste dia (o `fases._explode`)."""
    repor()
    con = mundo()
    pasta("Blue Farm")
    rep = loadout.report(con)
    r = fotos.escrever_planos(con, rep, raiz=SITE)
    assert [x["nome"] for x in r["escritos"]] == ["Blue Farm"], r
    txt = (fotos.pasta_novas(SITE) / "Blue Farm" / "_plano.txt").read_text(
        encoding="utf-8")
    # As 4 Swords numa linha só, com o `4x` à frente.
    assert "4x Swords to Plowshares" in txt, txt
    linhas = [l for l in txt.splitlines() if "Swords to Plowshares" in l]
    assert len(linhas) == 1, linhas
    # E a página diz o MESMO número que a pasta.
    f2 = fases.fila_decks(con, rep)
    fila = [f for f in f2["filas"] if f["slot"] == "cedh-blue-farm"][0]
    assert f"{fila['barra']['fotos']} fotos para {fila['barra']['cartas']} cartas" in txt
    swords = [ft for ft in fila["fotos"]
              if any(i["nm"] == "Swords to Plowshares" for i in ft["itens"])]
    assert len(swords) == 1, "o playset tem de estar numa foto só"
    assert swords[0]["cartas"] == 4, swords[0]
    print("o _plano.txt de um playset poe as 4 copias na mesma foto")


def caso_nenhuma_foto_do_plano_passa_de_quatro_cartas():
    """O tecto, em todos os decks e em todas as filas. Uma foto de 33 cartas é
    exactamente o que a campanha veio corrigir: nela não se julga o estado de
    carta nenhuma."""
    repor()
    con = mundo()
    rep = loadout.report(con)
    f2 = fases.fila_decks(con, rep)
    assert f2["barra"]["fotos"] > 0, f2
    for f in f2["filas"]:
        for ft in f["fotos"]:
            assert 0 < ft["cartas"] <= fotos.MAX_CARTAS, (f["nome"], ft)
            assert fotos.valida(ft["cartas"]), ft
            # Uma foto nunca atravessa dois TIPOS na Fase 2.
            assert ft["tipo"], ft
    # E a trava recusa mesmo o que passa do tecto, nos dois sentidos.
    assert not fotos.valida(5) and not fotos.valida(0) and fotos.valida(4)
    print("nenhuma foto do plano passa de 4 cartas, e a trava recusa 5")


def caso_uma_caixa_vazia_nao_rebenta_a_geracao():
    """A `modern` não tem uma única cópia dentro da caixa. A geração não pode
    rebentar — e o `_plano.txt` dela não pode prometer fotos que não existem: um
    plano de um deck vazio é um ficheiro a mentir."""
    repor()
    con = base()                       # ninguém tem nada alocado
    pasta("Blue Farm")
    d = pasta("Modern — UW Oswald")
    (d / "_plano.txt").write_text("plano velho a prometer fotos", encoding="utf-8")
    rep = loadout.report(con)
    r = fotos.escrever_planos(con, rep, raiz=SITE)
    assert r["escritos"] == [], r          # nenhuma caixa tem fila
    assert "Modern — UW Oswald" in r["vazios"], r
    txt = (d / "_plano.txt").read_text(encoding="utf-8")
    assert "NAO tem cartas registadas" in txt, txt
    assert "foto 01" not in txt, txt
    assert "modern" in txt, "tem de dizer o alvo, para quando houver cartas"
    # [CORRIGIDO A 2026-10-02] esta asserção era `not (...).exists()`, com o
    # comentário «uma pasta que não existe não se cria por iniciativa própria».
    # Era a regra certa em 01/10 e passou a estar errada no dia seguinte: medido
    # a 02/10, **7 das 17 caixas não tinham pasta** (as quatro novas desse dia,
    # as duas renomeadas e a `Elves`), e sem pasta o caminho que ele escolheu
    # (*"o melhor é criar pasta"*) não existe para esse deck — e ele não tem como
    # adivinhar o nome que o vault espera. Agora cria-se, e o nome sai do `caixas`
    # do config, que é a MESMA regra que a reconhece (`fotos.garantir_pastas`).
    # O que continua a NÃO se fazer é apagar ou mover: ver `TEXTO_ORFA`.
    # (afirma-se o RESULTADO e não quem a criou: casos anteriores deste mesmo
    # ficheiro já podem ter passado por lá, e `criadas` é só o delta da chamada.)
    elves = fotos.pasta_novas(SITE) / "Elves - Survival"
    assert elves.is_dir(), "a pasta de cada deck do config tem de existir"
    assert (elves / ".gitkeep").is_file(), "a estrutura viaja no Git"
    print("uma caixa vazia nao rebenta a geracao e o plano dela nao promete fotos")


def caso_o_plano_manda_largar_as_fotos_NESTA_pasta():
    """A instrução mudou DUAS vezes a 2026-10-01, e a segunda é a dele: de manhã
    este ficheiro mandava largá-las aqui (e nada as processava), corrigiu-se para
    `pendentes\\`, e à tarde ele decidiu *"o melhor é criar pasta"*. Agora a
    pasta é o alvo — e o texto tem de o dizer, com o endereço da outra porta."""
    repor()
    con = mundo()
    pasta("Blue Farm")
    rep = loadout.report(con)
    fotos.escrever_planos(con, rep, raiz=SITE)
    txt = (fotos.pasta_novas(SITE) / "Blue Farm" / "_plano.txt").read_text(
        encoding="utf-8")
    assert "NESTA PASTA" in txt, txt[:1200]
    assert "cedh-blue-farm" in txt, txt[:1200]
    assert "lote1" in txt, "as subpastas de lote continuam a valer"
    assert "https://editar-mtg.baverone.com/" in txt, txt[:1200]
    # E NÃO pode voltar a dizer que esta pasta não serve.
    assert "NADA a processa" not in txt, txt[:1200]
    print("o _plano.txt manda largar as fotos NESTA pasta e da o endereco da outra porta")


# ===========================================================================
# O ENDEREÇO
# ===========================================================================
def caso_o_endereco_do_modo_de_edicao_e_o_nome_e_nunca_o_ip():
    """Ordem dele de 2026-10-01: o modo de edição é
    `https://editar-mtg.baverone.com/` e **o IP da rede local não se usa**. O
    `ip`/`ips` saíram do dicionário de propósito: ele viajava daqui para o
    payload da página, e tirá-lo do ecrã e deixá-lo nos dados era tirá-lo só da
    vista.

    O `ligacao_local` sobreviveu ao QR (que saiu nesse mesmo dia, mais tarde):
    é dele que sai a linha do arranque na consola. O que deixou de existir é a
    viagem até à página.
    """
    import webapp                                            # noqa: PLC0415
    lig = webapp.ligacao_local()
    assert lig["url"].startswith("https://editar-mtg.baverone.com/?t="), lig
    assert lig["url"].endswith(lig["token"]), lig
    assert "ip" not in lig and "ips" not in lig, lig
    assert not any("192.168." in str(v) for v in lig.values()), lig
    assert lig["porto"] == webapp.PORT
    print("o endereco do modo de edicao e o nome, nunca o IP da rede local")


CASOS = (caso_uma_foto_na_pasta_do_deck_e_reconhecida,
         caso_a_subpasta_de_lote_conta_para_o_mesmo_deck,
         caso_renomear_a_caixa_muda_a_pasta_sem_tocar_em_codigo,
         caso_a_pasta_aceita_as_duas_formas_do_nome_e_o_slot,
         caso_a_recolha_move_a_foto_com_o_nome_do_alvo,
         caso_uma_foto_ainda_a_ser_copiada_nao_se_mexe,
         caso_as_pastas_de_grupo_nao_valem_como_alvo,
         caso_a_pasta_de_nomes_antigos_fica_de_fora,
         caso_o_plano_de_um_playset_poe_as_quatro_na_mesma_foto,
         caso_nenhuma_foto_do_plano_passa_de_quatro_cartas,
         caso_uma_caixa_vazia_nao_rebenta_a_geracao,
         caso_o_plano_manda_largar_as_fotos_NESTA_pasta,
         caso_o_endereco_do_modo_de_edicao_e_o_nome_e_nunca_o_ip)


def main():
    for c in CASOS:
        c()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001
            pass
    print(f"\nOK — {len(CASOS)} casos (a pasta por deck vale como alvo)")


if __name__ == "__main__":
    main()
