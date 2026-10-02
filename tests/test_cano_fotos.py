"""O CANO DAS FOTOS AGUENTA A CAMPANHA (André, 2026-10-02).

Ele vai fotografar a colecção INTEIRA — ~1 678 cartas em fotos de até quatro,
perto de 500 fotos, deck a deck, e o que não está em deck nenhum numa pasta nova
`Extras (fora dos decks)\\`. São dias de trabalho dele, e por isso o que aqui se
tranca é o cano, não a leitura das cartas.

Provado antes com o fluxo REAL das 02:30 (o `run.py` da tarefa `mtg-fotos-novas`,
sobre uma cópia da base dele e com imagens fabricadas, em
`_revisao/ensaio/casos.py`); isto é a rede permanente, e **cada caso chumba se a
correcção for retirada**:

  1. a pasta `Extras (fora dos decks)\\` vale como alvo **`coleccao`** — estava
     ligada a NADA: as fotos ficavam lá para sempre e a tarefa dizia «sem fotos
     novas», VERDE. Medido a 02/10;
  2. as QUATRO pastas de grupo (`Vender`, `Premodern (geral)`, `SPML (…)`,
     `Coleção Pessoal`) **continuam de fora** — não se começou a processá-las por
     iniciativa própria;
  3. o alvo `coleccao` aponta para cópias a sério: o `_chave` traduzia
     `coleccao → ("coleccao",)` e a `particao` chama-lhe `("resto",)`, logo o
     alvo da colecção ficava **sem cópia nenhuma** e a correcção por discrepância
     (0b) nunca disparava fora dos decks;
  4. a MESMA foto não é prova de duas cartas: relê-la não cria uma segunda cópia;
  5. o caso que ia acontecer todas as noites — uma foto com uma linha que não
     fecha **fica** em `pendentes/` (e bem), é relida na corrida seguinte, e as
     linhas que já tinham entrado voltavam a entrar. Uma cópia a mais por noite.

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

from mtgvault import (collection, db, fotocaixa, fotos,  # noqa: E402
                      fotosite, revalidacao, sources)

SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)
fotocaixa.RAIZ = SITE

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", ["nonfoil"], 1.50, "Instant"),
    ("Birds of Paradise", "4ed", "1995-04-01", ["nonfoil"], 9.0, "Creature"),
    ("Wasteland", "tmp", "1997-10-14", ["nonfoil"], 80.0, "Land"),
]
_ABERTAS = []


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
             json.dumps(fin), rel, json.dumps({"legacy": "legal"})))
        for f in fin:
            con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                        "finish, date, trend) VALUES (?, 'cardmarket', ?, "
                        "'2026-09-20', ?)", (f"id-{i}", f, preco))
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def copia(con, nm, sc, q=1, slot=None, foto=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção",
                              photo_path=foto)
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    # A campanha: por revalidar é `validado_em` a NULL.
    con.execute("UPDATE copies SET validado_em = NULL WHERE id = ?", (cid,))
    con.commit()
    return cid


def pasta(nome, *sub):
    d = fotos.pasta_novas()
    for p in (nome, *sub):
        d = d / p
    d.mkdir(parents=True, exist_ok=True)
    return d


def larga(nome_pasta, ficheiro, *sub):
    f = pasta(nome_pasta, *sub) / ficheiro
    f.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    os.utime(f, (1_700_000_000, 1_700_000_000))
    return f


def limpar_pendentes():
    p = fotosite.pasta_pendentes(SITE)
    if p.is_dir():
        for f in p.glob("*"):
            if f.is_file():
                f.unlink()
    fotos._CACHE.clear()


def csv_de(linhas, nome="recat.csv"):
    """Um CSV no formato do `processar_fotos` — o mesmo que o Claude escreve."""
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
    r = con.execute("SELECT COUNT(*), COALESCE(SUM(quantity),0) FROM copies").fetchone()
    return (r[0], r[1])


# ===========================================================================
# 1. A PASTA DOS EXTRAS VALE COMO «FORA DOS DECKS»
# ===========================================================================
def caso_a_pasta_dos_extras_vale_como_fora_dos_decks():
    """Ele criou `Extras (fora dos decks)\\` para o que não está em deck nenhum.
    A pasta não mapeava para caixa nenhuma, por isso o `recolher_das_pastas`
    deixava-a em `ignorados` — a foto ficava lá para sempre e a tarefa das 02:30
    dizia «sem fotos novas», verde. É o padrão do `event_tier` no sítio mais caro
    possível: o que se perde são dias de trabalho dele."""
    limpar_pendentes()
    f = larga("Extras (fora dos decks)", "x.jpg")
    alvo = fotos.alvo_da_pasta(f)
    assert alvo == {"tipo": "coleccao", "slot": None}, alvo
    # e NÃO é uma caixa: o `slot_da_pasta` continua a responder só «que caixa»
    assert fotos.slot_da_pasta(f) is None, "os Extras não são uma caixa"
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert len(r["recolhidas"]) == 1, r
    nome = r["recolhidas"][0]["para"]
    assert nome.startswith("site-colecao-"), nome
    assert not f.exists(), "a foto tinha de sair da pasta"
    # e o nome é lido de volta como alvo da COLECÇÃO (o caminho de 21/09)
    o = fotosite.origem(nome)
    assert o and o["tipo"] == "coleccao" and o["slot"] is None, o
    limpar_pendentes()


def caso_as_pastas_de_grupo_continuam_de_fora():
    """As quatro pastas de grupo já tinham um significado dele antes disto.
    Ligar os Extras **não** as ligou — processá-las por iniciativa própria era
    mudar-lhe a rotina sem ele pedir. Fica dito, com o porquê, em vez de
    silencioso."""
    limpar_pendentes()
    GRUPOS = ("Vender", "Premodern (geral)", "Coleção Pessoal")
    # limpa o que outro caso possa ter deixado nas pastas de grupo: aqui conta-se
    # quantas ficam de fora, e uma sobra de outro caso mudava o numero
    for p in GRUPOS:
        for x in pasta(p).glob("*.jpg"):
            x.unlink()
    for p in GRUPOS:
        f = larga(p, "y.jpg")
        assert fotos.alvo_da_pasta(f) is None, p
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert not r["recolhidas"], r["recolhidas"]
    assert len(r["ignorados"]) == 3, r["ignorados"]
    assert all("grupo" in i["porque"] for i in r["ignorados"]), r["ignorados"]
    for p in GRUPOS:
        (pasta(p) / "y.jpg").unlink()


def caso_todo_o_deck_do_config_ganha_pasta():
    """Medido no dia em que ele ia começar: das 17 caixas, **7 não tinham
    pasta** — umas por o deck ter sido renomeado (`Elves`, `Affinity (Luffy)`),
    outras por serem as caixas novas de 02/10 (`Aluren`, `Artifacts Blue`,
    `Modern — Affinity`, `Bant Airbend`, `Engineer Welder Cam`). Sem pasta, o
    caminho que ele escolheu não existe para esse deck, e ele não tem como saber
    o nome que o vault espera."""
    con = base()
    rep = {"slots": [{"slot": "cedh-blue-farm", "nome": "Blue Farm"},
                     {"slot": "legacy-aluren", "nome": "Aluren"},
                     {"slot": "premodern-elves", "nome": "Elves / Survival"}]}
    criadas = fotos.garantir_pastas(rep, raiz=SITE)
    assert "Aluren" in criadas, criadas
    # a «Elves / Survival» não cabe num caminho: a pasta é com ` - `, e é a
    # MESMA regra que o `mapa_pastas` usa para a reconhecer
    assert "Elves - Survival" in criadas, criadas
    for nome in ("Aluren", "Elves - Survival", "Blue Farm"):
        assert (fotos.pasta_novas(SITE) / nome).is_dir(), nome
        assert (fotos.pasta_novas(SITE) / nome / ".gitkeep").is_file(), nome
    # idempotente: correr outra vez não cria nada
    assert fotos.garantir_pastas(rep, raiz=SITE) == [], "criou duas vezes"


def caso_a_recolha_pergunta_o_alvo_num_sitio_so():
    """O `alvo_da_pasta` tem de ser a ÚNICA resposta a «de quem é esta pasta».

    Escrevi as duas no mesmo dia: a função, com a docstring a dizer «vive num
    sítio só», e uma segunda conta inline dentro do `fotos_nas_pastas` — que é
    por onde passa TODA a produção (`webapp`, `daily`, `cli`). A função ficava a
    ser chamada só pelos testes. Ligar uma pasta nova mexendo nela não teria
    efeito nenhum e as fotos ficavam na pasta, caladas: o defeito dos `Extras`
    recriado. Aqui troca-se a função e exige-se que a recolha mude com ela."""
    limpar_pendentes()
    larga("Vender", "z.jpg")                       # uma pasta de GRUPO
    r = fotos.recolher_das_pastas(raiz=SITE)
    assert not r["recolhidas"], "a de grupo não se recolhe (como sempre)"
    guardado = fotos.alvo_da_pasta
    try:
        fotos.alvo_da_pasta = (
            lambda caminho, cfg=None, mapa=None:
            {"tipo": "caixa", "slot": "cedh-blue-farm"}
            if "Vender" in str(caminho) else guardado(caminho, cfg, mapa))
        itens = fotos.fotos_nas_pastas(raiz=SITE)
        vender = [i for i in itens if i["pasta"] == "Vender"]
        assert vender and vender[0]["tipo"] == "caixa", \
            "o `fotos_nas_pastas` não perguntou ao `alvo_da_pasta`"
        r = fotos.recolher_das_pastas(raiz=SITE)
        assert len(r["recolhidas"]) == 1, r
        assert r["recolhidas"][0]["para"].startswith("site-cedh-blue-farm-"), r
    finally:
        fotos.alvo_da_pasta = guardado
        limpar_pendentes()


def caso_a_pasta_acabada_de_criar_diz_ao_que_vem():
    """A pasta criada para um deck sem cartas ficava com um `.gitkeep` e mais
    nada — nem uma linha a dizer que vale como alvo. Medido a 02/10: seis das
    pastas novas, caladas. E a pasta com o nome ANTIGO do deck, quando esse nome
    é o próprio `slot` (o `Standard\\` do slot `standard`, hoje «Bant Airbend»),
    continua a valer como alvo mas ficava com o plano congelado do dia do
    rename."""
    con = base()
    base_p = fotos.pasta_novas(SITE)
    (base_p / "cedh-blue-farm").mkdir(parents=True, exist_ok=True)  # o SLOT
    rep = {"slots": [{"slot": "cedh-blue-farm", "nome": "Blue Farm"}]}
    r = fotos.escrever_planos(con, rep, raiz=SITE)
    novo = base_p / "Blue Farm" / "_plano.txt"
    assert novo.is_file(), "a pasta do deck tem de ter plano"
    assert "Blue Farm" in novo.read_text(encoding="utf-8")
    # a pasta com o nome do SLOT aponta para a mesma caixa: o plano e o mesmo
    velho = base_p / "cedh-blue-farm" / "_plano.txt"
    assert velho.is_file(), "a pasta que vale como alvo pelo slot tambem tem plano"
    assert velho.read_text(encoding="utf-8") == novo.read_text(encoding="utf-8")
    # e nao e orfa: e a mesma caixa por outro nome
    assert "cedh-blue-farm" not in r["orfas"], r["orfas"]


def caso_a_pasta_de_um_deck_que_morreu_deixa_de_mentir():
    """O `_plano.txt` de 01/10 diz «LARGA AS FOTOS NESTA PASTA». Quando o deck é
    renomeado ou dissolvido o vault deixa de reconhecer a pasta — e o ficheiro
    NOSSO continuava lá a mandá-lo largar fotos que ninguém ia catalogar. Medido
    a 02/10: `Elves - Survival`, `Pauper (Luffy)`, `Jeskai Control`, `Legacy`.
    Troca-se o TEXTO; não se apaga nem se move a pasta (a regra dele de 09/09)."""
    con = base()
    morta = fotos.pasta_novas(SITE) / "Deck Que Morreu"
    morta.mkdir(parents=True, exist_ok=True)
    (morta / "_plano.txt").write_text("LARGA AS FOTOS NESTA PASTA\n",
                                      encoding="utf-8")
    rep = {"slots": [{"slot": "cedh-blue-farm", "nome": "Blue Farm"}]}
    r = fotos.escrever_planos(con, rep, raiz=SITE)
    assert "Deck Que Morreu" in r["orfas"], r["orfas"]
    txt = (morta / "_plano.txt").read_text(encoding="utf-8")
    assert "JA NAO E UM DECK" in txt, txt[:80]
    assert "LARGA AS FOTOS NESTA PASTA" not in txt, "continua a mentir"
    assert morta.is_dir(), "a pasta não se apaga"
    # e uma pasta de GRUPO nunca é órfã — nunca foi um deck
    assert "Vender" not in r["orfas"], r["orfas"]


# ===========================================================================
# 2. O ALVO DA COLECÇÃO APONTA PARA CÓPIAS A SÉRIO
# ===========================================================================
def caso_o_alvo_da_coleccao_aponta_para_as_copias_que_existem():
    """`_chave` devolvia `("coleccao",)` e a `particao` chama ao grupo
    `("resto",)`: o alvo da colecção dava `copias = set()`. Consequência — o passo
    (0) ficava sem preferência e a correcção por discrepância (0b), que EXIGE
    `alvo["copias"]`, **nunca disparava** fora dos decks: uma carta dos Extras
    fotografada noutra edição criava uma cópia nova em vez de corrigir a que lá
    está. Três sítios traduziam `coleccao → resto` à mão e este esqueceu-se."""
    con = base()
    dentro = copia(con, "Swords to Plowshares", "4ed", q=1, slot="cedh-blue-farm")
    fora = copia(con, "Wasteland", "tmp", q=1)
    assert revalidacao._chave({"tipo": "coleccao", "slot": None}) == ("resto",)
    cops = revalidacao.copias_do_alvo(con, {"tipo": "coleccao", "slot": None}, None)
    assert fora in cops, "a cópia fora de caixas é da colecção"
    assert dentro not in cops, "a que está na caixa não é «o resto»"
    # e o grupo existe no progresso com o mesmo nome
    prog = revalidacao.progresso(con, None)
    assert "resto" in prog, list(prog)


# ===========================================================================
# 3-4. A MESMA FOTO NÃO É PROVA DE DUAS CARTAS
# ===========================================================================
def caso_a_mesma_foto_nao_cria_uma_segunda_copia():
    """Ele volta a copiar o lote do telemóvel (o Explorador preserva a data, por
    isso a foto fica com o MESMO nome). Sem a trava, a cópia já estava validada —
    logo o passo (0) não a apanha —, já tinha `photo_path` — logo o (iii) também
    não — e caía no (iv), que CRIA uma cópia. Medido no ensaio de ponta a ponta."""
    con = base()
    copia(con, "Birds of Paradise", "4ed", q=1, foto="antiga.jpg")
    antes = linhas_e_cartas(con)
    p = csv_de([linha("Birds of Paradise", "4ed", "nova.jpg")])
    collection.import_csv(con, p)
    meio = linhas_e_cartas(con)
    assert meio == antes, f"a 1.ª passagem não devia criar cópia: {antes} -> {meio}"
    # a MESMA foto outra vez
    res: list[dict] = []
    collection.import_csv(con, p, resultados=res)
    fim = linhas_e_cartas(con)
    assert fim == meio, f"a 2.ª passagem criou cópia: {meio} -> {fim}"
    assert res and res[0]["resultado"] == "repetida", res
    assert "prova" in res[0]["motivo"], res[0]["motivo"]


def caso_a_foto_relida_depois_de_uma_linha_falhada_nao_duplica():
    """O caso que ia acontecer TODAS as noites numa campanha de 500 fotos: uma
    foto com duas cartas em que uma linha não fecha (sem edição). A regra do
    `arrumar_fotos` é que a foto cujas linhas não entraram todas **fica** em
    `pendentes/` — e está certa. Só que a corrida seguinte relê a MESMA foto e as
    linhas que entraram voltam a entrar: uma cópia a mais por noite, sem um único
    erro."""
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=1, foto="velha.jpg")
    antes = linhas_e_cartas(con)
    p = csv_de([linha("Swords to Plowshares", "4ed", "lote.jpg"),
                linha("Wasteland", "", "lote.jpg")],   # sem edição: PARA
               nome="parcial.csv")
    res1: list[dict] = []
    collection.import_csv(con, p, resultados=res1)
    meio = linhas_e_cartas(con)
    assert [r["resultado"] for r in res1] == ["importada", "erro"], res1
    # a noite seguinte: a foto ainda lá está e é relida tal e qual
    res2: list[dict] = []
    collection.import_csv(con, p, resultados=res2)
    fim = linhas_e_cartas(con)
    assert fim == meio, f"a releitura duplicou: {meio} -> {fim}"
    assert res2[0]["resultado"] == "repetida", res2
    # e a linha que falhou continua a falhar (é trabalho por fazer, não se tapa)
    assert res2[1]["resultado"] == "erro", res2


def caso_a_foto_arrumada_por_deck_continua_a_travar():
    """A comparação é pelo NOME do ficheiro e não pelo `photo_path` inteiro — e é
    essa a diferença que conta no cano a sério: depois de a foto entrar, o
    `arrumar_fotos` reescreve o `photo_path` com a pasta do deck à frente
    (`fotos/cedh-blue-farm/site-….jpg`, medido). A foto que fica em `pendentes/`
    continua a chamar-se `site-….jpg`, e uma trava que comparasse o caminho
    inteiro deixava de bater exactamente quando era precisa."""
    con = base()
    copia(con, "Birds of Paradise", "4ed", q=1,
          foto="fotos/cedh-blue-farm/site-cedh-blue-farm-20261002-120000-1.jpg")
    antes = linhas_e_cartas(con)
    p = csv_de([linha("Birds of Paradise", "4ed",
                      "site-cedh-blue-farm-20261002-120000-1.jpg")],
               nome="arrumada.csv")
    res: list[dict] = []
    collection.import_csv(con, p, resultados=res)
    assert res[0]["resultado"] == "repetida", res
    assert linhas_e_cartas(con) == antes, "criou cópia a partir da foto já arrumada"


def caso_a_conta_das_cartas_por_foto_e_pelo_NOME_do_ficheiro():
    """A regra das quatro cartas conta por FOTO. O `fotos_que_nao_validam`
    agrupava pelo `photo_path` INTEIRO — e o `arrumar_fotos` reescreve-o com a
    pasta do deck à frente só para as cópias da corrida em que a foto sai de
    `pendentes/`. A mesma foto ficava com duas chaves (`X.jpg` e
    `fotos/<slot>/X.jpg`), a contagem partia-se, e uma foto de 6 cartas lia-se
    como 3 + 3 — as duas dentro do tecto. O detector dava o número errado."""
    con = base()
    # a MESMA foto, metade das cópias já arrumada e metade não — é o estado que
    # uma foto relida deixa (ver `caso_a_foto_relida_...`)
    copia(con, "Swords to Plowshares", "4ed", q=3, foto="X.jpg")
    copia(con, "Birds of Paradise", "4ed", q=3,
          foto="fotos/cedh-blue-farm/X.jpg")
    nv = revalidacao.fotos_que_nao_validam(con)
    assert "X.jpg" in nv, nv
    assert nv["X.jpg"] == 6, "as 6 cartas da MESMA foto contam juntas: %s" % nv
    assert len(nv) == 1, "nao se parte em duas chaves: %s" % nv


def caso_duas_copias_a_serio_da_mesma_carta_continuam_a_entrar():
    """A trava é a identidade da FOTO e não da carta: ele TEM duas cópias e
    fotografa cada uma à parte. Travar isso era perder uma carta — e é o erro
    que esta trava não pode cometer."""
    con = base()
    antes = linhas_e_cartas(con)
    collection.import_csv(con, csv_de([linha("Wasteland", "tmp", "uma.jpg")],
                                      nome="u.csv"))
    collection.import_csv(con, csv_de([linha("Wasteland", "tmp", "outra.jpg")],
                                      nome="o.csv"))
    fim = linhas_e_cartas(con)
    assert fim[1] == antes[1] + 2, f"duas fotos, duas cartas: {antes} -> {fim}"


def caso_uma_foto_com_quatro_cartas_diferentes_entra_toda():
    """A regra das quatro cartas por foto: quatro linhas DIFERENTES na mesma foto
    entram todas. A trava das repetidas não pode confundir «quatro cartas na
    mesma foto» com «a mesma carta duas vezes» — é o lote inteiro dele."""
    con = base()
    antes = linhas_e_cartas(con)
    p = csv_de([linha("Swords to Plowshares", "4ed", "quatro.jpg", q=2),
                linha("Birds of Paradise", "4ed", "quatro.jpg"),
                linha("Wasteland", "tmp", "quatro.jpg")], nome="q.csv")
    res: list[dict] = []
    collection.import_csv(con, p, resultados=res)
    fim = linhas_e_cartas(con)
    assert all(r["resultado"] == "importada" for r in res), res
    assert fim[1] == antes[1] + 4, f"{antes} -> {fim}"


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
