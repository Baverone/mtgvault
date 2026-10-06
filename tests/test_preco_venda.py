"""UMA LINHA DE VENDA NUNCA LEVA O PREÇO DE OUTRA IMPRESSÃO (André, 2026-10-06).

À letra: *"uma linha de VENDA (ou qualquer valor que ele possa usar para decidir
vender ou para pedir um preco) usa o preco do scryfall_id EXACTO da copia e do
finish EXACTO dela. Se nao houver preco para essa impressao, a linha sai com
'sem preco' e entra numa lista de pendentes — NUNCA cai para o preco de outra
impressao."*

E a outra metade da mesma ordem: *"SETS QUE NAO SAO PRECO: Summer Magic / Edgar
(sum), 30th Anniversary Edition (30a), Collectors' Edition (ced), Intl.
Collectors' Edition (cei) … Nenhum destes pode emprestar preco a outra
impressao, em sitio nenhum do app."*

O QUE ISTO VINHA A CUSTAR, medido na base dele nesse dia:

  - o `preco_da_copia` caía para o `card_price` (o mínimo entre impressões do
    mesmo NOME) em **176 das 737 linhas** — o Powder Keg a 450,63 € de uma promo
    que ele não tem, a Ancient Tomb de `ltc` a 140,64 €;
  - e caía para o OUTRO ACABAMENTO em 3 linhas / 178,39 €, uma delas 4 **Goblin
    Engineer nonfoil** avaliadas ao preço do FOIL (19,74 € cada);
  - com a fonte `cardmarket`, **87** dos mínimos por nome vinham de um set que
    não é preço: Tundra **0,25 €** (Summer Magic) contra 374,34 € da impressão
    dele, Badlands **0,02 €**, Black Lotus 2 277,81 € (`30a`) contra 13 760,80 €,
    Gaea's Cradle 272,71 € (`wc99`) contra 1 085,40 €.

Não abre socket nenhum nem toca na rede.
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
BASE_CFG = {
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "regras_colecao": {},
    "regras_por_formato": [],
    "caixas": [],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(BASE_CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")      # ver tests/_bateria.py
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")   # e o CATÁLOGO: 06/10

from mtgvault import collection, configio, db, loadout, precos  # noqa: E402
from mtgvault import scryfall, venda, wantlist  # noqa: E402

HOJE = date.today().isoformat()
_ABERTAS = []

# (id, nome, edição, set_type, digital). O par que importa é a impressão LEGAL
# contra a que não é preço.
CATALOGO = [
    ("tun-3ed", "Tundra", "3ed", "core", 0),
    ("tun-sum", "Tundra", "sum", "core", 0),          # Summer Magic
    ("lot-2ed", "Black Lotus", "2ed", "core", 0),
    ("lot-30a", "Black Lotus", "30a", "memorabilia", 0),
    ("cra-usg", "Gaea's Cradle", "usg", "expansion", 0),
    ("cra-wc99", "Gaea's Cradle", "wc99", "memorabilia", 0),
    ("bay-3ed", "Bayou", "3ed", "core", 0),
    ("bay-cei", "Bayou", "cei", "memorabilia", 0),
    ("bay-ced", "Bayou", "ced", "memorabilia", 0),
    ("mox-mps", "Mox Opal", "mps", "masters", 0),
    ("mox-som", "Mox Opal", "som", "expansion", 0),
    ("eng-sld", "Goblin Engineer", "sld", "masters", 0),
]


def cfg(**blocos):
    from mtgvault import sources
    novo = json.loads(json.dumps(BASE_CFG))
    novo.update(blocos)
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources.esquecer_config()
    return novo


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (sid, nm, sete, st, dg) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, set_type)
               VALUES (?,?,?,?,?,?,'en','rare','Land',0,'',?,?,?,?,0,?)""",
            (sid, f"or-{nm}", nm, sete, sete.upper(), str(i),
             json.dumps(["nonfoil", "foil"]), "1994-04-11",
             json.dumps({"legacy": "legal"}), dg, st))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    con.commit()
    return con


def cota(con, sid, low, trend, fonte="cardmarket", fin="nonfoil"):
    con.execute(
        "INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, date,"
        " low, trend, currency, receita) VALUES (?,?,?,?,?,?, 'EUR','cm-guide')",
        (sid, fonte, fin, HOJE, low, trend))
    con.commit()


def add(con, sid, q=1, finish="nonfoil"):
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   condition, purpose, sub_collection_id)
                   VALUES (?,?,?,'en','NM','player',?)""", (sid, q, finish, sub))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


# ---------------------------------------------------------------------------
# 1. A REGRA ESTRITA
# ---------------------------------------------------------------------------
def caso_a_linha_de_venda_nunca_leva_o_preco_de_outra_impressao():
    """A impressão dela não está cotada: `unit` é None, e o preço da OUTRA não
    aparece em sítio nenhum da linha.

    É o caso do Powder Keg — 450,63 € de uma promo que ele não tem, dentro de
    uma linha de venda, marcada `min-impressoes` e somada ao total.
    """
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    cota(con, "mox-som", 100.0, 150.0)          # a BARATA está cotada
    # a dele (mps) NÃO está
    p = loadout.preco_da_copia(con, "mox-mps", "nonfoil", "Mox Opal")
    assert p["unit"] is None, (
        "a linha de venda caiu para o preço de outra impressão", p)
    assert p["origem"] == precos.ORIGEM_SEM_PRECO, p
    assert p["sem_preco_motivo"] == "impressao", p
    assert 150.0 not in [v for v in p.values() if isinstance(v, (int, float))], p
    # e o preço de COMPRA continua a ser o mínimo entre impressões: é outra
    # pergunta, e essa não mudou (2026-09-25).
    compra, _ = loadout.card_price(con, "Mox Opal", "nonfoil")
    assert compra == 150.0, compra
    print("sem preço da impressão dela, a linha sai sem número — e a COMPRA não muda")


def caso_a_linha_de_venda_nunca_leva_o_preco_do_outro_acabamento():
    """A impressão está cotada em nonfoil e a cópia é foil: `sem preço`.

    Medido na base dele: 4 **Goblin Engineer nonfoil** estavam a ser avaliadas
    ao preço do FOIL (19,74 € cada). Para SOMAR um inventário a tolerância é
    aceitável e vai marcada com `~`; para PEDIR um preço a alguém é o preço de
    outra carta.
    """
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    cota(con, "eng-sld", 15.0, 19.74, fin="foil")
    p = loadout.preco_da_copia(con, "eng-sld", "nonfoil", "Goblin Engineer")
    assert p["unit"] is None, ("o nonfoil levou o preço do foil", p)
    assert p["sem_preco_motivo"] == "acabamento", p
    # o INVENTÁRIO continua a tolerar, e a dizer que tolerou (2026-09-24)
    mapa = collection.mapa_precos(con)
    d = collection.preco_impressao_detalhe(mapa, "eng-sld", "nonfoil")
    assert d["preco"] == 19.74 and d["price_finish"] == "foil", d
    exacto = collection.preco_impressao_detalhe(mapa, "eng-sld", "nonfoil",
                                                exacto=True)
    assert exacto["preco"] is None, exacto
    print("o acabamento é exacto na venda e tolerante no inventário, e di-lo")


def caso_a_saida_sem_preco_recolhe_as_linhas_e_fica_fora_da_exportacao():
    """A «lista de pendentes» que ele pediu: saída própria, e nunca no CSV."""
    nomes = [n for n, _r, _e in venda.FORA]
    assert "sem_preco" in nomes, nomes
    # o CSV de stock leva uma coluna `Price`: uma linha sem preço não se lista.
    rep = {"venda": [], "venda_rl": [],
           "sem_preco": [{"nm": "Tundra", "q": 1, "unit": None,
                          "motivo": "x", "reason": "y", "copias": [[1, 1]],
                          "finish": "nonfoil", "lang": "en", "set_code": "3ed",
                          "set_name": "Revised", "sid": "tun-3ed",
                          "local": "Colecção", "sub": "Colecção", "total": 0,
                          "rl": 0, "caixa": None, "validado": "",
                          "cond": "NM"}]}
    fora = venda.fora_da_exportacao(rep)
    assert any(b["chave"] == "sem_preco" and b["linhas"] for b in fora), fora
    print("a saída `sem_preco` existe e fica fora do CSV de stock")


# ---------------------------------------------------------------------------
# 2. OS SETS QUE NÃO SÃO PREÇO
# ---------------------------------------------------------------------------
def caso_os_sets_que_nao_sao_preco_nao_emprestam_a_outra_impressao():
    """Summer Magic, 30th Anniversary, Collectors' e Intl. Collectors' — e a
    memorabilia inteira, que é o que faz os piores casos dele."""
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardmarket"})
    # a impressão legal, cara; e a que não é preço, barata
    cota(con, "tun-3ed", 300.0, 374.34)
    cota(con, "tun-sum", 0.20, 0.25)            # Summer Magic (set_type core!)
    cota(con, "lot-2ed", 12000.0, 13760.80)
    cota(con, "lot-30a", 2000.0, 2277.81)       # 30th Anniversary
    cota(con, "cra-usg", 900.0, 1085.40)
    cota(con, "cra-wc99", 200.0, 272.71)        # World Championship
    cota(con, "bay-3ed", 200.0, 279.78)
    cota(con, "bay-cei", 100.0, 170.81)
    cota(con, "bay-ced", 90.0, 150.00)
    for nm, esperado in (("Tundra", 374.34), ("Black Lotus", 13760.80),
                         ("Gaea's Cradle", 1085.40), ("Bayou", 279.78)):
        p, _ = loadout.card_price(con, nm, "nonfoil")
        assert p == esperado, (nm, p, esperado)
        assert wantlist.cheapest_price(con, nm) == esperado, (nm, "wantlist")
        sid = loadout.impressao_mais_barata(con, nm, "nonfoil")
        r = con.execute("SELECT set_code FROM cards WHERE scryfall_id = ?",
                        (sid,)).fetchone()
        assert (r["set_code"] or "").lower() not in ("sum", "30a", "ced", "cei"), (
            nm, "a IMAGEM ficou da impressão errada", r["set_code"])
    # e a Summer Magic continua a ter o SEU preço: o que ela não faz é responder
    # pelas outras (ordem dele, à letra).
    mapa = collection.mapa_precos(con)
    assert collection.preco_impressao(mapa, "tun-sum", "nonfoil")[0] == 0.25
    print("os sets que não são preço não emprestam — e mantêm o preço deles")


def caso_o_crivo_dos_sets_vive_num_sitio_so():
    """Estava escrito QUATRO vezes e nenhuma estava certa.

    `scryfall.impressoes`, `fases._preco_jogavel`, `meta_coverage._NOT_PLAYABLE`
    e `loadout.mais_barata_que_serve` tinham cada um a sua versão — e o `sum`
    escapava às quatro. Quem voltar a escrever o predicado à mão chumba aqui.
    """
    assert scryfall.SETS_SEM_PRECO == ("sum", "30a", "ced", "cei")
    sql = scryfall.sql_impressao_a_serio("c")
    for pedaco in ("digital", "memorabilia", "'sum'", "'30a'", "'ced'", "'cei'"):
        assert pedaco in sql, (pedaco, sql)
    maus = []
    for f in sorted(RAIZ.glob("*.py")) + sorted((RAIZ / "mtgvault").glob("*.py")):
        if f.name == "scryfall.py":
            continue
        txt = f.read_text(encoding="utf-8")
        # Só o CÓDIGO: um comentário pode (e deve) falar da regra.
        vivo = "\n".join(l.split("#")[0] for l in txt.splitlines())
        if re.search(r"set_type\s*(<>|!=)\s*'memorabilia'", vivo) or \
           re.search(r"set_name\s+NOT\s+LIKE\s*'%World Championship", vivo):
            maus.append(f.name)
    assert not maus, ("o crivo dos sets voltou a ser escrito à mão", maus)
    print("o crivo vive num sítio só e as quatro variantes desapareceram")


# ---------------------------------------------------------------------------
# 3. A RÉGUA DE VENDA
# ---------------------------------------------------------------------------
def caso_sem_o_bloco_precos_venda_nada_muda():
    """O interruptor: a chave que não existe não muda nada (padrão `venda.mostrar`)."""
    cfg(precos={"modo": "best", "fonte": "cardtrader"})
    assert precos.fontes_venda() == ("cardtrader",), precos.fontes_venda()
    assert precos.modo_venda() == "best", precos.modo_venda()
    cfg(precos={"modo": "best", "fonte": "cardtrader",
                "venda": {"fonte": "cardmarket", "modo": "market"}})
    assert precos.fontes_venda() == ("cardmarket",), precos.fontes_venda()
    assert precos.modo_venda() == "market", precos.modo_venda()
    assert precos.fontes() == ("cardtrader",), "a cadeia do VALOR não se tocou"
    assert precos.modo() == "best", "o modo do VALOR não se tocou"
    print("a régua de venda é própria, e sem o bloco vale a do valor")


def caso_a_regua_de_venda_manda_na_linha_e_nao_a_do_valor():
    """Duas fontes a cotar a MESMA impressão: a linha de venda usa a de venda."""
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "venda": {"fonte": "cardmarket", "modo": "market"}})
    cota(con, "tun-3ed", 300.0, 374.34, fonte="cardmarket")
    cota(con, "tun-3ed", 600.0, 647.21, fonte="cardtrader")
    p = loadout.preco_da_copia(con, "tun-3ed", "nonfoil", "Tundra")
    assert p["unit"] == 374.34, ("a linha de venda usou a régua do valor", p)
    assert p["fonte"] == "cardmarket", p
    mapa = collection.mapa_precos(con)
    assert collection.preco_impressao(mapa, "tun-3ed", "nonfoil")[0] == 647.21, (
        "o VALOR da colecção mudou de régua, e não devia")
    print("a venda mede-se na régua da venda; o valor fica na dele de 04/10")


def caso_o_aviso_de_divergencia_exige_os_dois_limiares():
    """Percentagem **e** euros. Sem o chão em euros, o aviso era ruído.

    O CardTrader tem um piso de oferta de ~0,11 €: as maiores percentagens são
    todas de cartas de cêntimos (medido: 11 das 20 piores abaixo de 3 €).
    """
    assert precos.DIVERGENCIA_PCT == 40.0
    assert precos.DIVERGENCIA_EUR == 2.00
    # muita percentagem, nenhum dinheiro -> não avisa
    d = precos.divergencia(0.03, 0.11)
    assert d and d["pct"] > 200 and not d["aviso"], d
    # muita percentagem E dinheiro -> avisa
    d = precos.divergencia(41.46, 151.57)
    assert d and d["aviso"], d
    # dinheiro mas pouca percentagem -> não avisa
    d = precos.divergencia(1000.0, 1100.0)
    assert d and not d["aviso"], d
    # sem a outra fonte não há aviso nenhum
    assert precos.divergencia(10.0, None) is None
    print("o aviso de divergência exige os dois limiares")


def caso_a_divergencia_chega_a_linha_de_venda_com_os_dois_numeros():
    """*"a linha leva aviso em vez de um numero so"* — os dois números viajam."""
    con = base()
    cfg(precos={"modo": "market", "fonte": "cardtrader",
                "venda": {"fonte": "cardmarket", "modo": "market"}})
    cota(con, "cra-usg", 40.0, 41.46, fonte="cardmarket")
    cota(con, "cra-usg", 151.57, 300.0, fonte="cardtrader")
    p = loadout.preco_da_copia(con, "cra-usg", "nonfoil", "Gaea's Cradle")
    d = p["divergencia"]
    assert d and d["aviso"], d
    # o que se compara é a oferta MAIS BARATA da outra fonte (151,57), e nunca a
    # mediana dos pedidos (300,00) — essa está estruturalmente acima.
    assert d["outra"] == 151.57, d
    assert d["fonte"] == "cardtrader", d
    print("a divergência compara com a oferta mais barata, não com a mediana")


def caso_o_config_a_serio_tem_a_regua_de_venda_escrita():
    """*"escreve qual e porque no colecao_config.json"* — e a razão fica lá.

    Não é cosmética: é o ficheiro que ele LÊ. Uma régua escolhida e não escrita
    é uma régua que ninguém consegue conferir nem mudar.
    """
    cfgs = configio.ler(RAIZ / "colecao_config.json")
    b = (cfgs.get("precos") or {}).get("venda")
    assert isinstance(b, dict), "falta o bloco `precos.venda` no config a sério"
    assert b.get("fonte") == "cardmarket", b
    assert b.get("modo") == "market", b
    assert b.get("desde"), b
    assert len(b.get("_porque") or "") > 300, (
        "a razão da régua não está escrita ao lado dela")
    print("o config a sério diz qual é a régua de venda e porquê")


def run():
    for fn in (caso_a_linha_de_venda_nunca_leva_o_preco_de_outra_impressao,
               caso_a_linha_de_venda_nunca_leva_o_preco_do_outro_acabamento,
               caso_a_saida_sem_preco_recolhe_as_linhas_e_fica_fora_da_exportacao,
               caso_os_sets_que_nao_sao_preco_nao_emprestam_a_outra_impressao,
               caso_o_crivo_dos_sets_vive_num_sitio_so,
               caso_sem_o_bloco_precos_venda_nada_muda,
               caso_a_regua_de_venda_manda_na_linha_e_nao_a_do_valor,
               caso_o_aviso_de_divergencia_exige_os_dois_limiares,
               caso_a_divergencia_chega_a_linha_de_venda_com_os_dois_numeros,
               caso_o_config_a_serio_tem_a_regua_de_venda_escrita):
        fn()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001
            pass
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
