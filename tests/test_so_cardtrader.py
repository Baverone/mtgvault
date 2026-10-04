"""SÓ CARDTRADER (André, 2026-10-04, à letra).

*"faz a tua pesquisa dos precos apenas no cardtrader, esquece o cardmarket"* e
*"refaz o meu site com essas alteracoes"*.

A cadeia de fontes passou a ser UMA SÓ (`precos.fonte_recurso` vazia) e a série
da Reserved List passou ao CardTrader. O que isto tranca, por ordem de
importância:

  1. **Uma cópia que o CardTrader não cote fica «sem preço»** — `None`, nunca
     0 €, nunca o Cardmarket calado por trás. É a regra dele de 24-25/09 e é a
     única coisa aqui que pode custar dinheiro: um zero numa soma tira uma
     carta de 900 € do total sem uma linha a dizê-lo.
  2. **O config a sério está mesmo numa fonte só.** O resto é mecanismo; esta
     é a decisão.
  3. **As páginas geradas não dizem «Cardmarket» onde falam de PREÇO.** Com
     UMA excepção declarada e testada — ver (4).
  4. A ESCALA DO ESTADO (MT/NM/EX/…) continua a dizer de onde foi transcrita, e
     a SAÍDA DE STOCK da venda continua a ser o ficheiro do Cardmarket. Não são
     esquecimentos: a primeira é vocabulário de ESTADO e não um preço, e a
     segunda está atrás do `venda.mostrar` (hoje `false`). Chamar CardTrader a
     um CSV com o `idProduct` do Cardmarket lá dentro era inventar.
  5. O CLI aceita esvaziar a cadeia (`precos fonte cardtrader --recurso`), e
     isso CARIMBA a régua — a regra dos 5 % da RL tem de ficar em suspenso.
  6. O campo do vendor da feira passou de `cardmarket` a `loja`, e a forma
     antiga continua a LER-SE (config e endpoint): uma página aberta ontem no
     telemóvel ainda manda o nome velho.

Não toca na rede.
"""
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG_PATH = _TMP / "cfg.json"
BASE_CFG = {"regras_por_formato": [
    {"grupo": "spml", "formatos": ["legacy"], "lingua": "en"}]}
CFG_PATH.write_text(json.dumps(BASE_CFG), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, feira, loadout, precos, prices  # noqa: E402
from mtgvault import sources  # noqa: E402

HOJE = date.today().isoformat()
_ABERTAS = []

# Duas cartas: uma que o CardTrader cota e outra que só o Cardmarket cotava.
# É o par que distingue «sem preço» de «o Cardmarket calado por trás».
CATALOGO = [
    ("ct-sol", "Sol Ring", "usg", 0),
    ("cm-only", "Gilded Drake", "usg", 1),
]


def cfg(**blocos):
    novo = json.loads(json.dumps(BASE_CFG))
    novo.update(blocos)
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()
    return novo


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (sid, nm, sete, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Land',0,'',?,'1998-10-12',?,0,?)""",
            (sid, f"or-{nm}", nm, sete, sete.upper(), str(i),
             json.dumps(["nonfoil", "foil"]),
             json.dumps({"legacy": "legal"}), rl))
    con.commit()
    return con


def add(con, sid, q=1, sub="Colecção"):
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES (?, 'player')", (sub,))
    sid_sub = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                          (sub,)).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,'nonfoil','en','player',?)""",
                (sid, q, sid_sub))
    con.commit()


def cota(con, sid, fonte, low, trend, quando=None,
         receita=precos.RECEITA_CT_OFERTAS):
    prices.write_prices(con, [(sid, fonte, quando or HOJE, "nonfoil", low,
                               trend, None, None, "EUR", receita)])


# ---------------------------------------------------------------------------
# 1. SEM PREÇO É SEM PREÇO — nunca 0 €, nunca o Cardmarket calado por trás
# ---------------------------------------------------------------------------
def caso_sem_cotacao_no_cardtrader_e_sem_preco_e_nao_zero():
    """A cópia que o CardTrader não cota vale `None` e conta em `sem_preco`.

    O Cardmarket TEM preço para ela na base (é de propósito: a recolha dele não
    foi desligada). Com a cadeia numa fonte só, esse preço não pode entrar —
    nem como número, nem como zero.
    """
    con = base()
    add(con, "ct-sol", 1)
    add(con, "cm-only", 1)
    cota(con, "ct-sol", "cardtrader", 10.0, 12.0)
    cota(con, "cm-only", "cardmarket", 500.0, 500.0, receita=precos.RECEITA_CM_GUIDE)

    cfg(precos={"fonte": "cardtrader", "fonte_recurso": ["cardmarket"],
                "modo": "market"})
    com = collection.valor_da_coleccao(con)
    assert com["sem_preco"] == 0, com["sem_preco"]
    assert round(com["total"]["trend"], 2) == 512.00, com["total"]

    cfg(precos={"fonte": "cardtrader", "fonte_recurso": [], "modo": "market"})
    so = collection.valor_da_coleccao(con)
    assert precos.fontes() == ("cardtrader",), precos.fontes()
    # A Gilded Drake sai do total INTEIRA — não vale 500 €, e também não vale 0.
    assert round(so["total"]["trend"], 2) == 12.00, so["total"]
    assert so["sem_preco"] == 1, so["sem_preco"]
    assert so["q"] == 2, "a cópia não desaparece da colecção, só do dinheiro"
    linha = next(c for c in so["copias"] if c["copy_id"]
                 and c["unit"] is None)
    assert linha["q"] == 1
    # E a página tem de poder dizer de onde veio cada euro.
    assert so["por_fonte"].get("cardtrader") == 1, so["por_fonte"]
    assert so["por_fonte"].get("cardmarket") is None, so["por_fonte"]
    assert so["por_fonte"].get("sem preço") == 1, so["por_fonte"]


def caso_o_preco_da_copia_nao_cai_calado_para_outra_fonte():
    """`loadout.preco_da_copia` devolve `sem-preco`, não um preço do Cardmarket."""
    con = base()
    cota(con, "cm-only", "cardmarket", 500.0, 500.0, receita=precos.RECEITA_CM_GUIDE)
    cfg(precos={"fonte": "cardtrader", "fonte_recurso": [], "modo": "market"})
    mapa = collection.mapa_precos(con)
    d = collection.preco_impressao_detalhe(mapa, "cm-only", "nonfoil")
    assert d["preco"] is None, d
    assert d["fonte"] is None, d
    # E com a cadeia de volta, o mesmo mapa responde — é a prova de que o que
    # mudou foi a RÉGUA e não os dados: o preço do Cardmarket continua na base.
    cfg(precos={"fonte": "cardtrader", "fonte_recurso": ["cardmarket"],
                "modo": "market"})
    d2 = collection.preco_impressao_detalhe(collection.mapa_precos(con),
                                            "cm-only", "nonfoil")
    assert d2["preco"] == 500.0 and d2["fonte"] == "cardmarket", d2


# ---------------------------------------------------------------------------
# 2. O CONFIG A SÉRIO — é esta a decisão dele, e não um mecanismo
# ---------------------------------------------------------------------------
def caso_o_config_a_serio_esta_numa_fonte_so():
    cfg_real = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    b = cfg_real["precos"]
    assert b["fonte"] == "cardtrader", b
    assert b["fonte_recurso"] == [], b["fonte_recurso"]
    assert b["fonte_serie"] == "cardtrader", b.get("fonte_serie")
    # A régua mudou hoje: sem o carimbo, a regra dos 5 % comparava a mediana
    # das ofertas de hoje com o Trend de há 90 dias.
    assert b["fonte_desde"] == "2026-10-04", b.get("fonte_desde")
    assert b["modo"] == "market", "o modo não se tocou"


# ---------------------------------------------------------------------------
# 3. AS PÁGINAS — o que o André VÊ
# ---------------------------------------------------------------------------
SCRIPTS = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
ETIQ = re.compile(r"<[^>]+>")


def _visivel(bruto: str) -> str:
    import html as _h
    return _h.unescape(ETIQ.sub(" ", SCRIPTS.sub(" ", bruto)))


def caso_nenhuma_pagina_gerada_diz_cardmarket_no_texto_visivel():
    """O texto visível das páginas publicadas, varrido.

    O `<script>` fica de fora de propósito: um template string do JavaScript
    está SEMPRE no ficheiro, desenhe-se ou não (a lição de 2026-10-04, as fotos
    apagadas). O que lá vive tem caso próprio, a seguir.
    """
    maus = []
    for p in sorted(RAIZ.glob("*.html")):
        txt = _visivel(p.read_text(encoding="utf-8", errors="replace"))
        for m in re.finditer(r"cardmarket", txt, re.I):
            a, b = max(0, m.start() - 70), min(len(txt), m.end() + 70)
            maus.append(f"{p.name}: …{' '.join(txt[a:b].split())}…")
    assert not maus, ("«Cardmarket» no texto visível de uma página:\n"
                      + "\n".join(maus))


def caso_os_dados_a_parte_tambem_nao_dizem_cardmarket():
    """`data/paginas/**.json` — é de lá que as páginas pesadas tiram o que mostram.

    Sem isto, a casca ficava limpa e o `fetch` trazia a palavra de volta.
    """
    pag = RAIZ / "data" / "paginas"
    if not pag.exists():
        print("    (sem data/paginas — nada a varrer)")
        return
    maus = []
    for p in sorted(pag.rglob("*.json")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"cardmarket", txt, re.I):
            a, b = max(0, m.start() - 60), min(len(txt), m.end() + 60)
            maus.append(f"{p.relative_to(RAIZ)}: …{' '.join(txt[a:b].split())}…")
    assert not maus, ("«Cardmarket» nos dados de uma página:\n"
                      + "\n".join(maus))


def caso_o_javascript_so_diz_cardmarket_na_saida_de_stock_da_venda():
    """A ÚNICA excepção viva no `deckboxes.js`, e é declarada.

    O CSV de stock é o ficheiro do Cardmarket — leva o `idProduct` dele e o
    formato aprende-se de `data/cardmarket-stock-exemplo.csv`. Chamar-lhe
    CardTrader era inventar uma integração que não existe. Está atrás do
    `venda.mostrar` (hoje `false`), por isso não se vê.

    Se um dia aparecer aqui uma ocorrência que NÃO seja da saída de stock, este
    caso chumba — é o que impede a palavra de voltar por uma porta lateral.
    """
    js = RAIZ / "deckboxes.js"
    if not js.exists():
        print("    (sem deckboxes.js gerado — nada a varrer)")
        return
    txt = js.read_text(encoding="utf-8", errors="replace")
    vivo = re.sub(r"/\*.*?\*/", " ", txt, flags=re.S)
    vivo = re.sub(r"^\s*//.*$", " ", vivo, flags=re.M)
    achados = []
    for m in re.finditer(r"cardmarket", vivo, re.I):
        a, b = max(0, m.start() - 160), min(len(vivo), m.end() + 160)
        achados.append(" ".join(vivo[a:b].split()))
    # As três da saída de stock: o título do bloco, o aviso do formato e o
    # nome do ficheiro de exemplo.
    permitidas = ("Saída: para o", "NÃO confirmado", "stock-exemplo.csv")
    maus = [a for a in achados if not any(p in a for p in permitidas)]
    assert not maus, ("«Cardmarket» fora da saída de stock da venda:\n"
                      + "\n".join(maus))
    assert len(achados) <= 3, achados


def caso_a_escala_do_estado_continua_a_dizer_de_onde_vem():
    """A escala MT/NM/EX/GD/LP/PL/PO **não** é um preço, e não se apaga.

    As definições estão transcritas à letra de help.cardmarket.com para o
    `data/estado-criterio.md`, que é o ficheiro que o passo que avalia LÊ.
    Tirar-lhe o nome deixava a página sem poder dizer de onde vem a régua do
    ESTADO — e os FACTORES de preço, esses, são medidos no CardTrader.
    """
    txt = (RAIZ / "arrumacao.py").read_text(encoding="utf-8")
    assert "A escala do estado é a do <b>Cardmarket</b>" in txt
    assert "medidos nas ofertas do <b>CardTrader</b>" in txt
    crit = RAIZ / "data" / "estado-criterio.md"
    if crit.exists():
        assert "help.cardmarket.com" in crit.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 4. O CLI — esvaziar a cadeia, e o carimbo
# ---------------------------------------------------------------------------
def caso_o_cli_aceita_esvaziar_a_cadeia_e_carimba_a_regua():
    p = _TMP / "cli.json"
    p.write_text(json.dumps({"precos": {"fonte": "cardtrader",
                                        "fonte_recurso": ["cardmarket"],
                                        "fonte_desde": "2026-09-25"}}),
                 encoding="utf-8")
    r = precos.gravar_fonte("cardtrader", [], path=p, hoje="2026-10-04")
    assert r["fontes"] == ["cardtrader"], r
    assert r["mudou"] is True and r["desde"] == "2026-10-04", r
    b = json.loads(p.read_text(encoding="utf-8"))["precos"]
    assert b["fonte_recurso"] == [], b
    # Repetir é um no-op: não se reinicia a janela da RL por um clique sem efeito.
    r2 = precos.gravar_fonte("cardtrader", [], path=p, hoje="2026-12-01")
    assert r2["mudou"] is False and r2["desde"] == "2026-10-04", r2


def caso_a_serie_segue_a_cadeia_e_nao_fica_no_cardmarket():
    cfg(precos={"fonte": "cardtrader", "fonte_recurso": []})
    assert precos.fonte_serie() == "cardtrader", precos.fonte_serie()
    # Com a chave escrita, ganha a chave (é como ele a pode voltar a mudar).
    cfg(precos={"fonte": "cardtrader", "fonte_recurso": [],
                "fonte_serie": "cardmarket"})
    assert precos.fonte_serie() == "cardmarket"


def caso_a_reserved_list_diz_que_a_serie_e_nova_em_vez_de_deixar_a_coluna_vazia():
    """Com a série no CardTrader, o «há ~1 mês» é zero — e a página di-lo.

    Medido a 2026-10-04 na base dele: a história do CardTrader começa a
    2026-09-25 (9 dias), por isso a coluna e a variação ficam vazias em TODAS as
    cartas. Um branco sem razão ao lado é o defeito que isto fecha.
    """
    import reservedlist
    con = base()
    cota(con, "ct-sol", "cardtrader", 10.0, 12.0)
    cfg(precos={"fonte": "cardtrader", "fonte_recurso": []})
    f = reservedlist.frase_serie(con)
    assert "cardtrader" in f, f
    assert "Ainda não chega para comparar" in f, f
    assert "não é uma avaria" in f.lower(), f
    # E a frase entra mesmo no rodapé da página.
    assert "%SERIE%" not in reservedlist._tmpl(con)
    assert "Ainda não chega para comparar" in reservedlist._tmpl(con)


# ---------------------------------------------------------------------------
# 5. O VENDOR DA FEIRA — `loja`, com a forma antiga ainda a ler-se
# ---------------------------------------------------------------------------
def caso_o_vendor_passou_a_loja_e_a_forma_antiga_continua_a_ler_se():
    velho = {"feira": {"vendors": [{"nome": "Banca A", "cardmarket": "bancaA"}]}}
    assert feira.vendors(velho)[0]["loja"] == "bancaA", feira.vendors(velho)
    novo = {"feira": {"vendors": [{"nome": "Banca B", "loja": "bancaB"}]}}
    assert feira.vendors(novo)[0]["loja"] == "bancaB"
    c: dict = {}
    v = feira.vendor_add(c, "Banca C", "", "bancaC", "")
    assert v == {"nome": "Banca C", "loja": "bancaC"}, v
    assert "cardmarket" not in json.dumps(c), c


# ---------------------------------------------------------------------------
# 6. A RECOLHA NÃO SE DESLIGOU — é grátis, não se vê, e deixa a porta aberta
# ---------------------------------------------------------------------------
def caso_a_recolha_do_cardmarket_continua_de_pe():
    """Nada visível a usa, mas o caminho fica: voltar atrás é uma linha.

    Se alguém apagar isto por limpeza, este caso chumba e obriga a decidir em
    vez de descobrir daqui a um mês que não há histórico nenhum para comparar.
    """
    assert hasattr(prices, "load_cardmarket_file")
    assert hasattr(prices, "CM_PRICEGUIDE_PUBLICO")
    daily = (RAIZ / "daily.py").read_text(encoding="utf-8")
    assert "cardmarket" in daily.lower(), "o passo do price guide saiu do daily"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    casos = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]
    falhas = 0
    for c in casos:
        try:
            c()
            print(f"  ok   {c.__name__}")
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print(f"  FAIL {c.__name__}: {e}")
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                   # noqa: BLE001,S110
            pass
    print(f"{len(casos) - falhas}/{len(casos)} ok")
    sys.exit(1 if falhas else 0)
