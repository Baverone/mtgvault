"""AS FOTOS FORAM APAGADAS, A PEDIDO DELE (André, 04/10/2026, à letra).

*"podes apagar todas as fotos, A MINHA RESPONSABILIDADE, se for para ter fotos,
vou tirar as fotos todas novamente"*.

É um levantamento **pontual** da regra de 09/09 (*nada se apaga*) e **só para as
fotos de cartas**: as 322 imagens de `data/fotos/anteriores/` saíram do disco e
os 723 `photo_path` da `copies` foram limpos. A regra continua inteira para tudo
o resto — a base, o config, os registos, e as próprias linhas da `copies`, que
ficam todas (737 linhas / 1 678 cartas).

O que estes casos trancam, e cada um chumba sem o trabalho desta ordem:

  1. uma cópia **sem** `photo_path` não rebenta nenhuma página — as onze geram-se
     e nenhuma diz que a colecção está vazia;
  2. o **showcase e as grelhas continuam a mostrar imagens**, porque as imagens
     das cartas vêm do CATÁLOGO (`cards.image_uri`, remotas, do Scryfall) e nunca
     foram fotos dele. É a distinção que a ordem manda não confundir;
  3. o **CSV do registo** tem uma linha por cópia que tinha foto, com o caminho
     que ela tinha — é o que fica escrito quando o ficheiro já não existe;
  4. os leitores das colunas de foto respondem «não há» em vez de levantarem:
     `loadout.foto_da_copia`, `fotos.resolver`, `fases.fotos_perdidas`,
     `revalidacao.progresso`, `confirmado.metades`;
  5. a **campanha ficou desligada** no config a sério, e o caminho das fotos
     **não** foi apagado: os módulos continuam todos de pé e voltam a morder no
     dia em que ele puser `desde` e `foto_manda`.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import csv
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
    # A CAMPANHA DESLIGADA, que é o estado que esta ordem deixou.
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 30},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, confirmado, db, fases, fotos,  # noqa: E402
                      loadout, revalidacao, sources)

CSV_REGISTO = "fotos-apagadas-2026-10-04.csv"

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", 1.50, "Instant"),
    ("Mox Diamond", "sth", "1998-03-02", 500.0, "Artifact"),
]
_ABERTAS = []


def base():
    """Uma base nova, com o catálogo mínimo e um deck de 2 cartas."""
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               image_uri)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W',?,?,?,0,0,?)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i), tipo,
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"}),
             f"https://cards.scryfall.io/small/{i}.jpg"))
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


def copia(con, nm, sc, q=1, slot=None, foto=None):
    cid = collection.add_copy(con, nm, set_code=sc, quantity=q, language="en",
                              finish="nonfoil", sub_collection="Colecção",
                              photo_path=foto)
    if slot:
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity) "
                    "VALUES (?,?,?)", (cid, slot, q))
    con.commit()
    return cid


# ===========================================================================
# 1. UMA CÓPIA SEM `photo_path` NÃO REBENTA NADA — E NÃO DIZ «VAZIA»
# ===========================================================================
def caso_uma_copia_sem_photo_path_nao_rebenta_o_relatorio():
    """O relatório inteiro sobre cópias sem uma única foto: tem de correr, e as
    cartas têm de CONTAR. Antes de 04/10 o vault tinha 723 `photo_path`
    preenchidos; a seguir tem zero, e isto é o que garante que a diferença é
    invisível para quem só quer saber se o deck está montado."""
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
    res = loadout.report(con)
    slot = res["slots"][0]
    assert slot["tenho"] == 2, slot["tenho"]
    assert slot["pct"] == 100, slot["pct"]
    assert slot["pct_fisico"] == 100, slot["pct_fisico"]


def caso_o_fotografar_fica_como_informacao_e_nao_decide():
    """O `fotografar` (= `got - got_conf`) continua a contar as cópias sem foto
    desta campanha, com a regra ligada ou desligada — é a metade informativa, e
    sempre foi assim. O que o interruptor desliga é a DECISÃO: com
    `foto_manda: false` o `pct`/`tenho` passam a ser o físico, e por isso um deck
    com 2 de 2 na caixa diz 100 % mesmo com as duas por fotografar.

    Mede-se aqui para ficar escrito que o número existe e não é uma avaria: na
    base dele são 589, e nenhuma página o lê como «a colecção está vazia»."""
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
    res = loadout.report(con)
    slot = res["slots"][0]
    assert slot["fotografar"] == 2, slot["fotografar"]
    assert slot["pct"] == 100, "a decisão tem de usar o físico"
    # e não vira compra: a foto tapa-se com a câmara, não com a carteira
    assert slot["comprar"] == 0, slot["comprar"]
    assert not res.get("custo_total"), res.get("custo_total")


def caso_sem_foto_a_copia_continua_a_valer_dinheiro():
    """Decisão de 02/10 que esta ordem não mexeu: *'sem foto' quer dizer 'ainda
    não conta', nunca 'não existe'*. Sem `photo_path`, o valor e a contagem da
    colecção ficam iguais — é o que impede a Galeria e os Binders de dizerem que
    a colecção está vazia."""
    con = base()
    copia(con, "Mox Diamond", "sth", q=1)
    v = collection.valor_da_coleccao(con)
    assert v["q"] == 1, v["q"]
    assert v["total"]["trend"] == 500.0, v["total"]


def caso_a_miniatura_de_uma_copia_sem_foto_e_None_e_nao_um_erro():
    """`loadout.foto_da_copia` é o que serve o `/foto?copy=` do 8771. Com a
    coluna vazia responde `None` (o chamador mostra «sem foto»); levantar punha
    a 404 a virar 500 e, com ela, a página inteira."""
    con = base()
    cid = copia(con, "Mox Diamond", "sth")
    assert loadout.foto_da_copia(con, cid) is None
    assert loadout.foto_da_copia(con, 99999) is None


def caso_o_resolvedor_responde_que_nao_ha_em_vez_de_levantar():
    """`fotos.resolver` procurava nas duas pastas (trabalho e arquivo). Com as
    duas vazias tem de devolver `None` — é por aqui que passam as miniaturas e o
    arquivo, e um `FileNotFoundError` aqui subia até à página."""
    assert fotos.resolver("841012f7-nao-existe.jpg") is None
    assert fotos.resolver("") is None


def caso_nao_ha_fotos_perdidas_quando_nao_ha_promessa_de_foto():
    """Uma «foto perdida» é `photo_path` cheio **e** ficheiro fora do disco — as
    33 de 01/10. Limpando a coluna, a resposta certa é ZERO: já não há uma
    afirmação de que existiu uma foto. Deixar o caminho lá era a base a apontar
    para o vazio e a Fase 2 a abrir com 33 linhas que ninguém pode resolver."""
    con = base()
    copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
    res = loadout.report(con)
    perdidas = fases.fotos_perdidas(con, res)
    assert perdidas.get("fotos") == [], perdidas.get("fotos")
    assert not perdidas.get("copias"), perdidas.get("copias")


def caso_o_progresso_da_revalidacao_diz_que_esta_desligada():
    """Com `desde: null` a campanha não existe: `activa` é falso e a aba 📷
    desaparece. O que NÃO pode acontecer é responder *«0 de 1 678 validadas»* com
    a campanha desligada — isso é o ecrã a dizer que a colecção está vazia."""
    con = base()
    copia(con, "Mox Diamond", "sth")
    prog = revalidacao.progresso(con)
    assert prog.get("activa") is False, prog
    assert prog.get("desde") is None, prog


def caso_as_metades_continuam_a_somar_o_total():
    """O `confirmado.metades` LEVANTA se as metades não somarem o total. Com zero
    confirmadas tem de somar na mesma — uma metade perdida pelo caminho é meia
    verdade com cara de verdade."""
    m = confirmado.metades(0, 1678, declarado=88)
    assert m["confirmado"] + m["declarado"] + m["por_confirmar"] == m["total"]
    assert m["por_confirmar"] == 1590, m
    # e a frase não anuncia um zero quando a regra está desligada
    assert "1 678" in confirmado.frase(0, 1678, declarado=88)


# ===========================================================================
# 2. AS IMAGENS DAS CARTAS VÊM DO CATÁLOGO, NÃO DAS FOTOS DELE
# ===========================================================================
def caso_as_imagens_das_cartas_vem_do_catalogo_e_nao_das_fotos():
    """A distinção que a ordem manda não confundir: o `image_uri` é do Scryfall,
    é REMOTO, e não é uma foto dele. Apagar as fotos não lhe pode tirar uma única
    imagem do site — se isto chumbar, apagou-se a coisa errada."""
    con = base()
    copia(con, "Mox Diamond", "sth")
    from mtgvault import paginas                             # noqa: PLC0415
    mapa = paginas.img_map(con, ["Mox Diamond"])
    sid = mapa.get("Mox Diamond")
    assert sid, mapa
    # o `img_map` dá o `scryfall_id` e o `art` constrói o URL — e é REMOTO
    url = paginas.art(sid)
    assert url.startswith("https://cards.scryfall.io/"), url
    assert "data/fotos" not in url and "photo" not in url, url
    # e responde a uma carta de que ele NÃO tem cópia nenhuma: a imagem do site
    # nunca dependeu de ele ter fotografado a carta
    assert paginas.art(paginas.img_map(con, ["Swords to Plowshares"])
                       .get("Swords to Plowshares")).startswith("https://")


def caso_o_showcase_desenha_imagens_sem_uma_unica_foto():
    """O `showcase.html` tinha 4 319 `<img>` e nenhuma delas é foto dele: o `src`
    sai do `paginas.art(sid)` com o `sid` do `img_map(..., da_coleccao=False)` —
    ou seja, do catálogo e **explicitamente não** da colecção. Desenha-se um
    arquétipo com a base sem uma única foto e exige-se o `<img>` remoto."""
    con = base()
    from mtgvault import paginas                             # noqa: PLC0415
    import showcase                                          # noqa: PLC0415
    nomes = ["Mox Diamond", "Swords to Plowshares"]
    sidmap = paginas.img_map(con, nomes, da_coleccao=False)
    arq = {"members": [{"main": {"Mox Diamond": 1, "Swords to Plowshares": 2},
                        "side": {}, "player": "ninguem", "weight": 1.0,
                        "event": "Ev", "date": "2026-10-01", "fmt": "cedh",
                        "placement": "1", "source": "manual", "url": "",
                        "tier": "Presencial", "id": 1}]}
    saida = showcase._archetype_html(
        arq, "Teste", paginas.tipo_map(con, nomes) if hasattr(
            paginas, "tipo_map") else {n: "Artifact" for n in nomes},
        set(), {}, sidmap)
    texto = saida if isinstance(saida, str) else json.dumps(saida)
    assert "<img" in texto, texto[:400]
    assert "https://cards.scryfall.io/" in texto, texto[:400]
    # e nenhuma imagem sai de uma pasta de fotos dele
    for proibido in ("data/fotos", "photo_path", "/foto?copy="):
        assert proibido not in texto, proibido


# ===========================================================================
# 3. O REGISTO DO QUE CADA CÓPIA TINHA
# ===========================================================================
def caso_o_csv_tem_uma_linha_por_copia_que_tinha_foto():
    """*"para ficar escrito o que cada cópia tinha, mesmo que o ficheiro deixe de
    existir"*. O CSV é a única memória do que se apagou: tem de ter uma linha por
    cópia com `photo_path`, e o caminho em cada uma."""
    alvo = RAIZ / "data" / CSV_REGISTO
    assert alvo.exists(), f"falta o registo {alvo}"
    with alvo.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    assert len(linhas) == 723, f"{len(linhas)} linhas, esperavam-se 723"
    for col in ("copy_id", "carta", "edicao", "acabamento", "lingua",
                "photo_path"):
        assert col in linhas[0], f"falta a coluna {col}"
    sem_caminho = [l for l in linhas if not l["photo_path"]]
    assert not sem_caminho, f"{len(sem_caminho)} linhas sem photo_path"
    ids = {l["copy_id"] for l in linhas}
    assert len(ids) == 723, "copy_id repetido no registo"


def caso_a_base_a_serio_nao_tem_uma_unica_referencia_a_foto():
    """A outra ponta: ficheiro apagado e coluna limpa andam juntos. Uma coluna
    preenchida com o ficheiro fora é a base a apontar para o vazio."""
    import sqlite3                                           # noqa: PLC0415
    vault = RAIZ / "data" / "vault.db"
    if not vault.exists():                 # noutra máquina não há base dele
        return
    con = sqlite3.connect(f"file:{vault}?mode=ro", uri=True)
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM copies WHERE photo_path IS NOT NULL "
            "OR foto_anterior IS NOT NULL OR validado_em IS NOT NULL "
            "OR verso_path IS NOT NULL").fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM copies").fetchone()[0]
        cartas = con.execute("SELECT SUM(quantity) FROM copies").fetchone()[0]
    finally:
        con.close()
    assert n == 0, f"{n} cópias ainda referem uma foto"
    # NADA SE APAGOU na base: a regra de 09/09 continua inteira para as cópias.
    # «Nada se apagou» é um PISO e não uma igualdade — e isto era uma igualdade
    # (`total == 737 and cartas == 1678`, o estado de 2026-10-04). A colecção é
    # uma tabela VIVA: a 2026-10-05 tinha **800 linhas / 1 930 cartas** (ele
    # continuou a meter cartas) e o caso ficou vermelho a dizer que faltavam
    # linhas quando o que havia eram mais. Um teste que chumba por a colecção
    # crescer deixa de se ler — e era o único vermelho a tapar os outros.
    # O que se tranca é o que a frase quer dizer: **nunca menos** do que o que
    # havia no dia em que as fotos se apagaram.
    PISO_LINHAS, PISO_CARTAS = 737, 1678
    assert total >= PISO_LINHAS, (
        f"a `copies` tem {total} linhas e no dia em que as fotos se apagaram "
        f"(2026-10-04) tinha {PISO_LINHAS}: alguma coisa se apagou")
    assert cartas >= PISO_CARTAS, (
        f"{cartas} cartas contra as {PISO_CARTAS} de 2026-10-04: "
        f"alguma coisa se apagou")


def caso_a_pasta_do_arquivo_ficou_vazia_mas_existe():
    """Os ficheiros foram-se; a PASTA fica. É ela o destino do `fotos.arquivar`,
    e apagá-la era estragar um caminho que o código continua a usar."""
    pasta = RAIZ / "data" / "fotos" / "anteriores"
    if not (RAIZ / "data" / "vault.db").exists():
        return
    assert pasta.is_dir(), f"a pasta do arquivo desapareceu: {pasta}"
    imagens = [p for p in pasta.rglob("*")
               if p.is_file() and p.suffix.lower() in
               {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}]
    assert not imagens, f"sobraram {len(imagens)} imagens"


# ===========================================================================
# 4. O CAMINHO DAS FOTOS NÃO FOI APAGADO
# ===========================================================================
def caso_o_codigo_das_fotos_continua_todo_de_pe():
    """*"se voltar a querer fotos tira-as de novo — o caminho tem de continuar a
    existir"*. Não se apagou um módulo: isto importa-os todos e chama uma função
    de cada um."""
    from mtgvault import (confirmado as cf, fotocaixa, fotos as ft,  # noqa
                          fotosite, revalidacao as rv)
    for mod, fn in ((ft, "arquivar"), (ft, "resolver"), (ft, "agrupar"),
                    (fotosite, "nome_ficheiro"), (fotosite, "origem"),
                    (fotocaixa, "guardar"), (rv, "revalidar"),
                    (rv, "definir_alvo"), (cf, "manda"), (cf, "metades")):
        assert hasattr(mod, fn), f"{mod.__name__}.{fn} desapareceu"


def caso_a_campanha_esta_desligada_no_config_a_serio():
    """O config DELE: `desde: null` e `foto_manda: false`. Sem isto, e sem uma
    única foto no disco, o vault dizia ZERO cartas confirmadas e punha os decks a
    0 % com 96 % na gaveta — a regra existe para o obrigar a fotografar, não para
    lhe esconder a colecção enquanto não o faz."""
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    rev = cfg.get("revalidacao") or {}
    assert rev.get("foto_manda") is False, rev
    assert not rev.get("desde"), rev
    # e o porquê fica escrito ao lado, com a data
    assert "_revalidacao_desligada" in cfg, "falta a nota do porquê no config"
    assert "04/10/2026" in cfg["_revalidacao_desligada"]


def caso_voltar_a_ligar_a_regra_volta_a_morder():
    """O interruptor é um interruptor: com `foto_manda: true` e sem fotos, a
    cópia volta a NÃO contar. É isto que prova que não se amputou nada e que o
    dia em que ele voltar a fotografar está coberto."""
    d = json.loads(json.dumps(CFG))
    d["revalidacao"] = {"desde": "2026-10-04", "alvo": None, "foto_manda": True}
    CAMINHO.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    sources._CONFIG_CACHE = None
    try:
        assert confirmado.manda() is True
        con = base()
        copia(con, "Swords to Plowshares", "4ed", q=2, slot="cedh-blue-farm")
        res = loadout.report(con)
        slot = res["slots"][0]
        assert slot["pct"] == 0, f"com a regra ligada e sem foto: {slot['pct']}"
        assert slot["pct_fisico"] == 100, slot["pct_fisico"]
    finally:
        CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
        sources._CONFIG_CACHE = None


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
