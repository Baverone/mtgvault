"""A LISTA DE FALTAS E AS IMAGENS NAS LISTAS DE CARTAS (André, 2026-10-05).

    *"quero as coisas publicadas no mtgvault, com imagem das cartas para eu me
    organizar"*
    *"preciso tambem da lista de faltas desses decks para poder procurar em
    Ghent"*

Sete casos, e cada um chumba se a peça correspondente for retirada — a prova está
em `tests/_chumba_faltas.py`, que desliga uma de cada vez e exige vermelho:

  1. as TRÊS listas (NÃO VENDER, SEGURO VENDER, FALTAS) mostram a carta;
  2. o primeiro ecrã de cada uma pede no máximo `paginas.IMG_LOTE` imagens —
     medido no HTML que o JavaScript desenhou, não no código;
  3. a vista de faltas NÃO mostra o que ele já tem;
  4. os subtotais por deck somam o total;
  5. um preço que não é do material que a regra pede aparece MARCADO na linha,
     com o preço da impressão que serve ao lado;
  6. as faltas de um formato sem deck escolhido ficam numa secção à parte e FORA
     do total;
  7. a Fase 3 da Arrumação desenha as duas listas — era o que estava avariado
     desde 2026-10-01 (`fase3` lia `p.candidatos` e a parte É o candidatos), e
     nenhum teste lia o HTML daquela aba.

Não abre socket para fora nem toca na `vault.db` a sério. Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
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

#: Uma caixa de PREMODERN (pt, nonfoil, ≤SCG) — é ela que faz nascer o aviso de
#: preço — e uma de CEDH sem regra de língua, que é o controlo: ali a linha não
#: pode levar marca nenhuma. Mais uma de LEGACY, que é a PROPOSTA.
CAIXAS = [
    {"slot": "prem", "nome": "Enchantress", "formato": "premodern",
     "fonte": "deck", "ref": "PREM", "balde": "Colecção",
     "estado": "permanente", "prioridade": 1},
    {"slot": "ced", "nome": "Blue Farm", "formato": "cedh", "fonte": "deck",
     "ref": "CEDH", "balde": "Colecção", "estado": "permanente",
     "prioridade": 2},
    {"slot": "leg", "nome": "Artifacts Blue", "formato": "legacy",
     "fonte": "deck", "ref": "LEG", "balde": "Colecção",
     "estado": "permanente", "prioridade": 3},
]

CFG = {
    "venda": {"mostrar": False, "congelada": True},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "lingua": "pt",
         "acabamento": "nonfoil", "edicoes": "premodern", "estrita": True,
         "dedicado": True},
        # SEM `lingua`: é o controlo do caso 5.
        {"grupo": "cedh", "formatos": ["cedh"], "dedicado": True},
        {"grupo": "spml", "formatos": ["legacy"], "dedicado": True},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None, "foto_manda": False},
    "reserva": {"janela_dias": 0, "staples_premodern_pct": 100},
    "decks_montar": {},
    "decks_de_evento": [],
    "listas_escolhidas": {},
    "basicas": {},
    # O `legacy` está no modelo «um deck por formato» e SEM versões: é isso que o
    # põe na PROPOSTA (`faltas_vista.sem_deck_escolhido`). O `premodern` não está
    # no modelo de propósito — ele nunca lhe tocou.
    "decks_por_formato": {
        "_limiar_listas": 1,
        "legacy": {"nome": "Decks de Mox Opal", "em": "2026-10-05",
                   "versoes": []},
    },
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import (collection, db, loadout,  # noqa: E402
                      faltas_vista, paginas)

#: `(nome, set, data, preço)`. A **Exploration** é o caso do aviso: tem uma
#: reimpressão BARATA de 2023 (que a caixa de Premodern recusa) e a impressão da
#: era a 77 € (que é o que ele vai pagar). A **Sterling Grove** é o controlo
#: inverso: a mais barata JÁ é da era, logo nenhuma marca de edição.
CATALOGO = [
    ("Exploration", "usg", "1998-10-12", 77.73),
    ("Exploration", "dmr", "2023-01-13", 41.49),
    ("Sterling Grove", "inv", "2000-10-02", 10.87),
    ("Argothian Enchantress", "usg", "1998-10-12", 83.81),
    ("Lotus Petal", "tmp", "1997-10-14", 40.0),
    # Em lista NENHUMA e não é RL: é ela que enche a lista de SEGURO VENDER.
    ("Pithing Needle", "som", "2010-10-01", 3.0),
]
#: 45 cartas baratas, só para a lista passar das 40 imagens (caso 2).
CATALOGO += [(f"Carta {i:02d}", "ons", "2002-10-07", 0.5 + i / 100)
             for i in range(45)]

#: A **Lotus Petal** entra em DUAS caixas de propósito: é ela que faz a diferença
#: entre contar as cartas por NOME (uma carta para procurar) e somar os `cartas`
#: de cada deck (que daria duas). Sem esta sobreposição o caso 4 passava a verde
#: com a conta errada.
LISTAS = {
    "PREM": [("main", "Exploration", 2), ("main", "Sterling Grove", 3),
             ("main", "Argothian Enchantress", 2), ("main", "Lotus Petal", 1)]
    + [("main", f"Carta {i:02d}", 1) for i in range(45)],
    "CEDH": [("main", "Lotus Petal", 1)],
    "LEG": [("main", "Lotus Petal", 2)],
}
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, preco) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line,
               oracle_text, cmc, color_identity, finishes, released_at,
               legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare','Enchantment','',1,'G',?,?,?,0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper() + " set", str(i),
             json.dumps(["nonfoil"]), rel, json.dumps({"legacy": "legal"})))
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low) VALUES (?, 'cardmarket', "
                    "'nonfoil', '2026-10-04', ?, ?)", (f"id-{i}", preco, preco))
    # A Lotus Petal é RESERVED LIST e está na lista de duas caixas: é a regra R4
    # («a RL que ele joga») que segura as cópias a mais, e é assim que a lista de
    # NÃO VENDER tem linhas para desenhar. Sem uma cópia protegida, o caso 1
    # passava a verde com a metade de cima vazia.
    con.execute("UPDATE catalog.cards SET reserved = 1 WHERE name = 'Lotus Petal'")
    con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                     watched_id INTEGER, sub_collection TEXT)""")
    for ref, cards in LISTAS.items():
        fmt = {"PREM": "premodern", "CEDH": "cedh"}.get(ref, "legacy")
        con.execute("INSERT INTO decks (name, format) VALUES (?, ?)", (ref, fmt))
        did = con.execute("SELECT id FROM decks WHERE name=?",
                          (ref,)).fetchone()["id"]
        for board, nm, q in cards:
            con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, "
                        "board) VALUES (?,?,?,?)", (did, nm, q, board))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def vista(con):
    return faltas_vista.vista(con, loadout.report(con))


def avaliar(html: str, js: str):
    """Corre `js` no contexto da página desenhada. `None` sem node."""
    if not shutil.which("node"):
        return None
    d = Path(tempfile.mkdtemp())
    (d / "p.html").write_text(html, encoding="utf-8")
    (d / "t.js").write_text(js, encoding="utf-8")
    p = subprocess.run(["node", str(Path(__file__).with_name("avaliar_js.js")),
                        str(d / "p.html"), str(d / "t.js")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
    return json.loads(p.stdout)


_CONTA = """
const v = document.getElementById('vista').innerHTML;
const n = (s, re) => (s.match(re) || []).length;
const resultado = {erro: v.indexOf('erro-dados') >= 0,
                   imgs: n(v, /<img\\b/g), vazias: n(v, /data-sid=/g),
                   linhas: n(v, /<li class="fr">/g),
                   avisos: n(v, /class="av aviso"/g),
                   html: v};
"""


# ===========================================================================
def caso_as_tres_listas_mostram_imagem():
    """1. *"com imagem das cartas para eu me organizar"* — nas TRÊS listas.

    A de FALTAS, e as duas da Fase 3 da Arrumação (NÃO VENDER = as protegidas,
    SEGURO VENDER = os candidatos). Mede-se no HTML que o JavaScript desenhou,
    porque é isso que ele vê — o `sid` estar no JSON não prova nada.
    """
    import arrumacao                                           # noqa: PLC0415
    import faltas                                              # noqa: PLC0415
    con = base()
    collection.add_copy(con, "Lotus Petal", set_code="tmp", quantity=8,
                        language="en", finish="nonfoil",
                        sub_collection="Colecção")
    collection.add_copy(con, "Pithing Needle", set_code="som", quantity=3,
                        language="en", finish="nonfoil",
                        sub_collection="Colecção")
    con.commit()
    r = avaliar(faltas.html_page(con), _CONTA)
    if r is None:
        print("sem node — saltado")
        return
    assert not r["erro"], r["html"][:400]
    assert r["imgs"] > 0, "a lista de FALTAS não desenhou uma única imagem"
    # As duas da Fase 3, no mesmo DOM.
    f3 = avaliar(arrumacao.html_page(con), """
ABA = 'f3';
const resultado = render().then(() => {
  const v = document.getElementById('vista').innerHTML;
  const i = v.indexOf('Protegidas <span');
  const n = (s, re) => (s.match(re) || []).length;
  return {erro: v.indexOf('erro-dados') >= 0,
          sv: n(v.slice(0, i), /<img\\b/g), nv: n(v.slice(i), /<img\\b/g),
          linhas_sv: n(v.slice(0, i), /<td class="mini">/g),
          linhas_nv: n(v.slice(i), /<td class="mini">/g), html: v.slice(0, 400)};
});
""")
    assert not f3["erro"], f3["html"]
    assert f3["linhas_sv"] and f3["linhas_nv"], \
        f"uma das listas da Fase 3 veio vazia: {f3}"
    assert f3["sv"] > 0, "a lista SEGURO VENDER não desenhou uma única imagem"
    assert f3["nv"] > 0, "a lista NÃO VENDER não desenhou uma única imagem"
    print(f"as tres listas mostram imagem (faltas {r['imgs']}, "
          f"seguro vender {f3['sv']}, nao vender {f3['nv']})")


def caso_o_primeiro_ecra_nao_passa_do_lote_de_imagens():
    """2. O primeiro ecrã de CADA lista pede no máximo `paginas.IMG_LOTE`.

    Não é o `loading="lazy"`: as linhas acima do lote nascem SEM `<img>` e com o
    `data-sid` à espera do observador. O `lazy` é uma sugestão que cada browser
    cumpre como quer; este número é nosso e conta-se.
    """
    import faltas                                              # noqa: PLC0415
    con = base()
    r = avaliar(faltas.html_page(con), _CONTA)
    if r is None:
        print("sem node — saltado")
        return
    assert r["linhas"] > paginas.IMG_LOTE, (
        f"o caso não prova nada com {r['linhas']} linhas: precisa de mais de "
        f"{paginas.IMG_LOTE}")
    assert r["imgs"] <= paginas.IMG_LOTE, (
        f"o primeiro ecrã pediu {r['imgs']} imagens, acima do lote de "
        f"{paginas.IMG_LOTE}")
    assert r["vazias"] > 0, "nenhuma moldura ficou à espera do observador"
    print(f"o primeiro ecra pede {r['imgs']} imagens em {r['linhas']} linhas "
          f"({r['vazias']} molduras a espera)")


def caso_a_vista_de_faltas_nao_mostra_o_que_ele_tem():
    """3. *"as que ele ja tem NAO aparecem"*.

    A falta é o **`comprar`** da alocação e nunca o `missing`: o `comprar` já
    desconta o que ele tem, o que está noutra caixa e **o que já encomendou**
    (2026-09-19). As duas metades:

      * as 3 Sterling Grove que entram na colecção tiram a carta da lista;
      * uma ENCOMENDA de 2 Argothian Enchantress tira-a também — e é esta que
        separa o `comprar` do `missing`, porque uma encomenda não cria cópia
        nenhuma e o `missing` continua a 2. Sem ela o caso passava com a conta
        errada (medido: `tests/_chumba_faltas.py`, alvo 3).
    """
    from mtgvault import encomendas                            # noqa: PLC0415
    con = base()
    antes = vista(con)
    nomes = {l["nm"] for d in antes["decks"] for l in d["linhas"]}
    assert {"Sterling Grove", "Argothian Enchantress"} <= nomes, nomes
    collection.add_copy(con, "Sterling Grove", set_code="inv", quantity=3,
                        language="pt", finish="nonfoil",
                        sub_collection="Colecção")
    encomendas.adicionar(con, "prem", "Argothian Enchantress", 2,
                         log_path=_TMP / "enc.log")
    con.commit()
    dep = vista(con)
    nomes2 = {l["nm"] for d in dep["decks"] for l in d["linhas"]}
    assert "Sterling Grove" not in nomes2, (
        "a carta que ele tem continua na lista de faltas")
    assert "Argothian Enchantress" not in nomes2, (
        "a carta que ele já encomendou continua na lista de faltas — a falta é o "
        "`comprar`, não o `missing`")
    assert "Exploration" in nomes2, "e levou as outras com ela"
    assert dep["totais"]["valor"] < antes["totais"]["valor"]
    print("o que ele tem e o que ja encomendou saem da lista de faltas")


def caso_o_subtotal_por_deck_soma_o_total():
    """4. *"SUBTOTAL POR DECK, que e o que lhe diz o que vale a pena cacar"*.

    Os subtotais têm de somar o total, ao cêntimo e à cópia — senão é o padrão
    do `event_tier` sobre a lista com que ele vai gastar dinheiro. E as CARTAS
    contam-se por NOME sem repetir entre decks (a mesma carta a faltar em dois
    decks é uma carta para procurar e duas cópias para comprar).
    """
    con = base()
    v = vista(con)
    t = v["totais"]
    assert t["decks"] == len(v["decks"]) and t["decks"] >= 2, v["decks"]
    assert round(sum(d["valor"] for d in v["decks"]), 2) == t["valor"], (
        [(d["nome"], d["valor"]) for d in v["decks"]], t["valor"])
    assert sum(d["copias"] for d in v["decks"]) == t["copias"]
    nomes = {l["nm"] for d in v["decks"] for l in d["linhas"]}
    assert t["cartas"] == len(nomes), (t["cartas"], len(nomes))
    assert t["linhas"] >= t["cartas"], (t["linhas"], t["cartas"])
    print(f"os subtotais somam o total ({t['decks']} decks, {t['cartas']} "
          f"cartas, {t['copias']} copias, {t['valor']:.2f} EUR)")


def _pro(con):
    """Anúncios de VENDEDOR PROFISSIONAL (`cardtrader-pro-<língua>`, 2026-10-17).

    Exploration: PT 80,00 na impressão da era (USG), PT 30,00 na de 2023 (que a
    caixa de Premodern recusa) e EN 70,00 (língua errada) — a referência é 80.
    Sterling Grove: só EN — em Premodern fica «sem PT à venda».
    Lotus Petal: PT 50 e EN 45 — o cEDH não pede língua, fica a mais barata."""
    sid = {(nm, sc): f"id-{i}" for i, (nm, sc, _r, _p) in enumerate(CATALOGO)}
    for nm, sc, fonte, p in (("Exploration", "usg", "cardtrader-pro-pt", 80.0),
                             ("Exploration", "dmr", "cardtrader-pro-pt", 30.0),
                             ("Exploration", "usg", "cardtrader-pro-en", 70.0),
                             ("Sterling Grove", "inv", "cardtrader-pro-en", 9.0),
                             ("Lotus Petal", "tmp", "cardtrader-pro-pt", 50.0),
                             ("Lotus Petal", "tmp", "cardtrader-pro-en", 45.0)):
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, trend, low, receita) VALUES (?, ?, 'nonfoil', "
                    "'2026-10-17', ?, ?, 'ct-pro')", (sid[(nm, sc)], fonte, p, p))
    con.commit()


def caso_o_preco_e_o_1o_anuncio_profissional_na_lingua_e_edicao_da_regra():
    """5. [REESCRITO A 2026-10-17] O preço de referência de uma falta passou a ser
    o 1.º anúncio de um VENDEDOR PROFISSIONAL, na língua e no acabamento que a
    regra pede, da impressão que a caixa aceita (André: *"só PT"* em Premodern).

    O caso de 2026-10-05 (*"quando o preco mostrado nao e da lingua ou do
    acabamento que a regra pede, a PAGINA TEM DE O DIZER NA LINHA"*) deixou de
    poder acontecer: o preço já É o da impressão que serve, na língua certa. O que
    a linha diz agora é quando NÃO há anúncio — «sem PT à venda», sem preço,
    nunca o de uma oferta inglesa nem 0 €.
    """
    con = base()
    # Sem nenhum anúncio profissional recolhido, fica o preço de antes — e o
    # relatório diz que régua valeu, em vez de pôr tudo «sem preço» calado.
    antes = loadout.report(con)
    assert antes["regua_faltas"] == "motor", antes["regua_faltas"]
    _pro(con)
    rep = loadout.report(con)
    assert rep["regua_faltas"] == "vendedor-profissional", rep["regua_faltas"]
    v = faltas_vista.vista(con, rep)
    assert v["totais"]["regua"] == "vendedor-profissional"
    assert "1.º anúncio de vendedor profissional" in faltas_vista.texto_totais(v["totais"])
    porc = {(d["slot"], l["nm"]): l for d in v["decks"] for l in d["linhas"]}
    exp = porc[("prem", "Exploration")]
    assert exp["unit"] == 80.0, ("a referência é o PT da impressão da era, não a "
                                 "reimpressão de 2023 (30) nem o EN (70)", exp)
    assert exp["unit_motor"] == 41.49 and exp["aviso"] is None, exp
    assert exp["total_serve"] == 160.0 and exp["total"] == round(2 * 41.49, 2), exp
    assert "cardmarket.com" in exp["cm_url"] and "Exploration" in exp["cm_url"]
    sg = porc[("prem", "Sterling Grove")]
    assert sg["unit"] is None, ("sem PT à venda não pode ganhar o preço EN", sg)
    assert sg["aviso"]["motivos"] == ["sem_pro"] and "sem PT" in sg["aviso"]["frase"], sg
    assert porc[("ced", "Lotus Petal")]["unit"] == 45.0, porc[("ced", "Lotus Petal")]
    # O «FECHAR TUDO» É ESTE PREÇO (resolve a decisão pendente de 16/10).
    prem = next(s for s in rep["slots"] if s["slot"] == "prem")
    assert prem["custo"] == round(sum((m["unit"] or 0) * m["comprar"]
                                      for m in prem["missing"]), 2)
    d = next(d for d in v["decks"] if d["slot"] == "prem")
    assert d["valor_serve"] == prem["custo"], (d["valor_serve"], prem["custo"])
    print("o preço é o 1.º anúncio profissional, na língua e na edição da regra")


def caso_as_linhas_pro_saem_das_mesmas_ofertas():
    """O `prices.linhas_pro` (2026-10-17): só `user_type == "pro"`, por língua e
    acabamento, com o crivo de sempre (sem played, graded, férias)."""
    from mtgvault import prices                                # noqa: PLC0415

    def o(c, lang, tipo="pro", foil=False, cond="Near Mint", **k):
        return {"price_cents": c, "price_currency": "EUR",
                "user": {"user_type": tipo},
                "properties_hash": {"mtg_language": lang, "mtg_foil": foil,
                                    "condition": cond}, **k}
    ofs = [o(500, "pt"), o(300, "pt", tipo="normal"), o(450, "pt", cond="Played"),
           o(200, "pt", graded=True), o(700, "en"), o(650, "en", foil=True),
           o(100, "it")]
    r = {(x[1], x[3]): x[4] for x in prices.linhas_pro("S", ofs, "2026-10-17")}
    assert r == {("cardtrader-pro-pt", "nonfoil"): 5.0,
                 ("cardtrader-pro-en", "nonfoil"): 7.0,
                 ("cardtrader-pro-en", "foil"): 6.5}, r
    print("linhas pro: só profissionais, por língua e acabamento")


def caso_as_faltas_de_legacy_ficam_fora_do_total():
    """6. *"se mostrares faltas de legacy, e numa secao separada marcada como
    PROPOSTA e fora do total"*.

    Quem decide não é uma lista de nomes: é o formato estar no modelo «um deck por
    formato» e não ter versão nenhuma. No dia em que ele escolher o deck de
    Legacy, a secção desaparece sozinha — e é isso que a segunda metade prova.
    """
    con = base()
    v = vista(con)
    assert [d["nome"] for d in v["proposta"]] == ["Artifacts Blue"], v["proposta"]
    assert all(d["formato"] != "legacy" for d in v["decks"]), \
        "uma falta de legacy entrou no total"
    assert "legacy" not in v["formatos"], v["formatos"]
    assert v["totais_proposta"]["copias"] > 0, "a secção da proposta veio vazia"
    assert v["totais"]["copias"] + v["totais_proposta"]["copias"] == \
        sum(d["copias"] for d in v["decks"] + v["proposta"])
    # ESCOLHIDO O DECK, deixa de ser proposta.
    cfg = json.loads(CAMINHO.read_text(encoding="utf-8"))
    cfg["decks_por_formato"]["legacy"]["versoes"] = [
        {"id": "versao:legacy:a", "nome": "A", "deck": "caixa:leg"}]
    CAMINHO.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    from mtgvault import sources                               # noqa: PLC0415
    sources.esquecer_config()
    try:
        v2 = vista(con)
        assert not v2["proposta"], "escolhido o deck, continuou na proposta"
        assert any(d["formato"] == "legacy" for d in v2["decks"])
    finally:
        CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
        sources.esquecer_config()
    print("as faltas de um formato sem deck escolhido ficam fora do total")


def caso_a_fase_3_desenha_as_duas_listas():
    """7. A FASE 3 DA ARRUMAÇÃO DESENHA, e isto esteve quatro dias avariado.

    O `fase3(p)` lia `p.candidatos` e a parte **é** o candidatos (`dados()` escreve
    `partes["candidatos"] = _magra(...)`): `c.linhas` rebentava, o `catch` do
    `render` chamava o `erroDados`, e o separador mostrava *«não consegui carregar
    os dados desta secção»* desde 2026-10-01 — o dia em que a página nasceu. A
    página respondia 200, os ficheiros de dados respondiam 200, e **nenhum teste
    lia o HTML desta aba**. O bloco do Mox Opal de 2026-10-05 entrou para dentro
    desta função e também nunca apareceu — a CURVA DO LIMIAR era composta e
    deitada fora no `return`.
    """
    import arrumacao                                           # noqa: PLC0415
    con = base()
    collection.add_copy(con, "Lotus Petal", set_code="tmp", quantity=8,
                        language="en", finish="nonfoil",
                        sub_collection="Colecção")
    collection.add_copy(con, "Pithing Needle", set_code="som", quantity=3,
                        language="en", finish="nonfoil",
                        sub_collection="Colecção")
    con.commit()
    r = avaliar(arrumacao.html_page(con), """
ABA = 'f3';
/* O bloco do Mox Opal chama-se com um `m` à mão: num cenário sem listas de
   metagame o motor não o produz, e o que aqui se tranca é o DESENHO — o `curva`
   era composto e deitado fora no `return` do `moxHTML`. */
const mox = moxHTML({
  limiar: 1, cartas_criterio: 9,
  formatos: {modern: {listas: 2, total: 4, pct: 50, carta: 'Mox Opal'}},
  nao_vender: {linhas: 3, copias: 5, valor: 100},
  seguro_vender: {linhas: 1, copias: 2, valor: 10},
  uma_lista: {linhas: 1, copias: 1, valor: 5},
  curva: [{limiar: 1, cartas_criterio: 9, a_mais: {copias: 5, valor: 50},
           sozinha: {copias: 9, valor: 90}},
          {limiar: 2, cartas_criterio: 4, a_mais: {copias: 1, valor: 5},
           sozinha: {copias: 3, valor: 30}}],
});
const resultado = render().then(() => {
  const v = document.getElementById('vista').innerHTML;
  return {erro: v.indexOf('erro-dados') >= 0,
          vender: v.indexOf('Fase 3 · VENDER') >= 0,
          protegidas: v.indexOf('Porque está protegida') >= 0,
          mox_titulo: mox.indexOf('Não vender · seguro vender') >= 0,
          curva: mox.indexOf('O limiar é uma decisão tua') >= 0,
          curva_dois: mox.indexOf('Protegeria sozinha') >= 0,
          html: v.slice(0, 500)};
});
""")
    if r is None:
        print("sem node — saltado")
        return
    assert not r["erro"], ("a Fase 3 continua a mostrar um erro de dados: "
                           + r["html"])
    assert r["vender"], "a lista VENDER não apareceu: " + r["html"]
    assert r["protegidas"], "a coluna do motivo da protecção não apareceu"
    assert r["mox_titulo"], "o bloco «não vender · seguro vender» não apareceu"
    assert r["curva"], ("a curva do limiar é CALCULADA e tem de ser DESENHADA — "
                        "é a decisão que fica para ele, e o `moxHTML` compunha-a "
                        "e deitava-a fora no `return`")
    assert r["curva_dois"], "a curva tem de dar os DOIS números (a mais / sozinha)"
    print("a fase 3 desenha as duas listas, e o bloco do mox desenha a curva")


#: A lista é pública para o `tests/_chumba_faltas.py` lhe poder escolher alvos.
CASOS = (caso_as_tres_listas_mostram_imagem,
         caso_o_primeiro_ecra_nao_passa_do_lote_de_imagens,
         caso_a_vista_de_faltas_nao_mostra_o_que_ele_tem,
         caso_o_subtotal_por_deck_soma_o_total,
         caso_o_preco_e_o_1o_anuncio_profissional_na_lingua_e_edicao_da_regra,
         caso_as_linhas_pro_saem_das_mesmas_ofertas,
         caso_as_faltas_de_legacy_ficam_fora_do_total,
         caso_a_fase_3_desenha_as_duas_listas)


def run():
    for fn in CASOS:
        fn()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                      # noqa: BLE001
            pass
    shutil.rmtree(_TMP, ignore_errors=True)
    print("OK")


if __name__ == "__main__":
    run()
