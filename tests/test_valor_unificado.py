"""O valor da coleção é UMA conta só — e as três páginas mostram-na igual.

André, 2026-09-24: *"corrige tudo o que achares que é erro"*, sobre a Galeria a
dizer **97 761,26 €** e os Binders por cor a dizerem **97 772,93 €** para o
mesmo dinheiro. Onze euros e sessenta e sete cêntimos de discórdia, em três
cartas foil (Ethersworn Canonist SLD, Cid FIC, Helitrooper FIC) cujo Cardmarket
não cota o foil: os Binders faziam cair o preço para o nonfoil e a Galeria
dava-as como *sem preço*. Nenhum passo dava erro — é o padrão do `event_tier`.

Havia QUATRO contas para *"quanto vale esta cópia?"*: a da Galeria, a dos
Binders, a do `collection_value` (o `cli value`) e a primeira versão do Início,
que já tinha desistido da sua. Agora há uma —
`collection.valor_da_coleccao` — e este teste falha se alguma página voltar a
escrever a sua.

O que aqui se tranca:
  1. as TRÊS páginas publicadas (Galeria, Binders por cor, Início) mostram o
     mesmo total, lido do HTML que desenharam — inclusive com o mesmo número de
     casas decimais (os Binders mostravam `97 773 €`);
  2. a regra da queda de acabamento: uma foil sem preço foil vale o nonfoil, e
     a Galeria diz que é estimativa;
  3. uma **etched** cai para FOIL e não para nonfoil (era o que a conta antiga
     fazia, com o «outro acabamento» escrito à mão como
     `"foil" if fin == "nonfoil" else "nonfoil"`);
  4. as cópias de COLECIONADOR contam para o valor — e contam da mesma maneira
     nas três páginas (a conta dos Binders usava o `jogaveis()`, que as deixa de
     fora, enquanto a Galeria usava o `na_estante()`, que as inclui);
  5. a fonte dos preços está FIXA no `cardmarket`: a conta dos Binders fazia
     `MIN` sobre a `price_latest` inteira, e ligar a CardTrader mudava o valor
     da coleção sem ninguém mexer numa carta;
  6. nenhuma página tem um mapa de preços próprio.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps({
    "caixas": [], "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_colecao": {}, "spml_formatos": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
}, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db  # noqa: E402
import colecao_cor  # noqa: E402
import collection_gallery  # noqa: E402
import inicio  # noqa: E402

_ABERTAS = []

# Cada carta é um caso da regra. Os preços são inventados, mas as SITUAÇÕES são
# as da base dele.
CARTAS = [
    # (sid, nome, acabamentos do catálogo)
    ("id-normal", "Brainstorm", ["nonfoil", "foil"]),
    ("id-so-nonfoil", "Ethersworn Canonist", ["nonfoil", "foil"]),
    ("id-etched", "Blood Moon", ["nonfoil", "foil", "etched"]),
    ("id-sem-preco", "Ademi of the Silkchutes", ["nonfoil"]),
]
# (sid, acabamento, trend) — repara no que NÃO está aqui: a `id-so-nonfoil` não
# tem linha foil, a `id-etched` não tem linha etched, a `id-sem-preco` não tem
# linha nenhuma.
PRECOS = [
    ("id-normal", "nonfoil", 1.50), ("id-normal", "foil", 9.00),
    ("id-so-nonfoil", "nonfoil", 10.67),
    ("id-etched", "nonfoil", 3.00), ("id-etched", "foil", 25.00),
]


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for sid, nome, fins in CARTAS:
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved,
               image_uri)
               VALUES (?,?,?,'sld','Secret Lair','1','en','rare','Artifact',2,'U',
                       ?, '2021-01-01', ?, 0, 0, '')""",
            (sid, "or-" + sid, nome, json.dumps(fins),
             json.dumps({"legacy": "legal"})))
    for sid, fin, tr in PRECOS:
        con.execute(
            "INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, "
            "date, low, trend) VALUES (?,'cardmarket',?, '2026-09-24', ?, ?)",
            (sid, fin, tr, tr))
    con.commit()
    return con


def _sub(con, nome):
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?, 'player')",
                (nome,))
    con.commit()
    return con.execute("SELECT id FROM sub_collections WHERE name = ?",
                       (nome,)).fetchone()["id"]


def copia(con, sid, finish="nonfoil", q=1, balde="Colecção", purpose="player"):
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES (?,?,?,'en',?,?)""",
                (sid, q, finish, purpose, _sub(con, balde)))
    con.commit()
    return con.execute("SELECT MAX(id) i FROM copies").fetchone()["i"]


def povoar(con):
    """A coleção do teste: um caso de cada."""
    copia(con, "id-normal", "nonfoil", 4)                     # 4 × 1,50 =  6,00
    copia(con, "id-normal", "foil", 1)                        # 1 × 9,00 =  9,00
    copia(con, "id-so-nonfoil", "foil", 1)                    # 1 × 10,67 = 10,67
    copia(con, "id-etched", "etched", 3)                      # 3 × 25,00 = 75,00
    copia(con, "id-sem-preco", "nonfoil", 2)                  # sem preço =  0,00
    copia(con, "id-normal", "nonfoil", 2,                     # 2 × 1,50 =  3,00
          balde="Caixa Reserved List")
    copia(con, "id-normal", "foil", 1, purpose="collector")   # 1 × 9,00 =  9,00
    return 112.67


_EUR = re.compile(r"([0-9][0-9  .]*,[0-9]{2})\s*€")


def euros(txt):
    """Todos os valores em euros de um HTML, como float."""
    return [round(float(m.replace(" ", "").replace(" ", "")
                        .replace(".", "").replace(",", ".")), 2)
            for m in _EUR.findall(txt)]


def paginas_html(con):
    """Gera as três páginas para uma pasta temporária e devolve o HTML de cada."""
    out = Path(tempfile.mkdtemp())
    inicio.build(con, out / "index.html")
    colecao_cor.build(con, out / "colecao_cor.html")
    collection_gallery.build(con, out / "colecao.html")
    return {n: (out / n).read_text(encoding="utf-8")
            for n in ("index.html", "colecao_cor.html", "colecao.html")}


# ---------------------------------------------------------------------------


def caso_as_tres_paginas_mostram_o_mesmo_total():
    """O caso que ele viu: dois números para o mesmo dinheiro.

    Lê-se o HTML PUBLICADO e não as funções — foi lá que a discórdia apareceu, e
    uma delas mostrava o total arredondado aos euros com a conta certa por trás.
    """
    con = base()
    esperado = povoar(con)
    assert collection.valor_da_coleccao(con)["total"]["trend"] == esperado

    h = paginas_html(con)
    # Cada página escreve o total à sua maneira; o que tem de bater é o NÚMERO.
    gal = re.search(r'valor ~<b style="color:var\(--gold\)">([^<]+)</b>',
                    h["colecao.html"])
    cor = re.search(r'class="vtr">([^<]+)</b>', h["colecao_cor.html"])
    ini = re.search(r"valor ~([0-9][0-9  .]*,[0-9]{2}\s*€)",
                    h["index.html"])
    assert gal and cor and ini, (bool(gal), bool(cor), bool(ini))
    lidos = {"galeria": euros(gal.group(1))[0],
             "binders": euros(cor.group(1))[0],
             "inicio": euros(ini.group(1))[0]}
    assert set(lidos.values()) == {esperado}, lidos
    # E o `cli value`, que é a quarta superfície do mesmo número.
    cli = round(sum(r["total"] for r in collection.collection_value(con)), 2)
    assert cli == esperado, (cli, esperado)
    print("galeria, binders, inicio e `cli value` dizem o mesmo total")


def caso_as_tres_paginas_contam_as_mesmas_cartas():
    """Um valor sobre um conjunto de cópias e uma contagem sobre outro é o
    cartão do Início a dizer *"N cartas valem X"* com o X a contar cartas que o N
    não conta."""
    con = base()
    povoar(con)
    q = collection.valor_da_coleccao(con)["q"]
    assert q == 14, q                      # 4+1+1+3+2+2+1, colecionador incluído
    assert sum(c["qty"] for c in collection_gallery._cards(con)) == q
    assert inicio._valor_coleccao(con)[0] == q
    h = paginas_html(con)
    assert f"<b>{q}</b> exemplares" in h["colecao.html"]
    assert re.search(r'Cartas na coleção</span></div><a[^>]*><span class="kv">'
                     + str(q) + r"<", h["index.html"]), "o Início conta outro"
    print(f"as tres paginas contam as mesmas {q} cartas")


def caso_uma_foil_sem_preco_foil_vale_o_nonfoil():
    """As três cartas dele. A Galeria dava-as como *sem preço* e os Binders
    davam-lhes o nonfoil: 11,67 € de diferença."""
    con = base()
    povoar(con)
    linhas = {c["name"]: c for c in collection_gallery._cards(con)
              if c["name"] == "Ethersworn Canonist"}
    l = linhas["Ethersworn Canonist"]
    assert l["eur"] == 10.67, l
    assert l["est"] == "nonfoil", "a Galeria tem de dizer que é estimativa"
    # E a que TEM preço no seu acabamento não é estimativa nenhuma: a chave `est`
    # nem sequer existe (os dados vão embutidos na página — um `null` por linha
    # eram 10,7 KB na base dele para marcar três cartas).
    foil = [c for c in collection_gallery._cards(con)
            if c["name"] == "Brainstorm" and c["foil"]][0]
    assert foil["eur"] == 9.00 and "est" not in foil, foil
    print("uma foil sem preco foil vale o nonfoil, e diz que e estimativa")


def caso_uma_etched_cai_para_foil_e_nao_para_nonfoil():
    """Uma etched é FOIL (`loadout.FOIL_FINISHES`). A conta antiga tinha o
    «outro acabamento» escrito à mão (`"foil" if fin == "nonfoil" else
    "nonfoil"`) e por isso dava-lhe o preço do NONFOIL — 3,00 € em vez de
    25,00 €, por cópia."""
    mapa = {"trend": {("id-etched", "nonfoil"): 3.00, ("id-etched", "foil"): 25.00},
            "low": {}}
    p, fin = collection.preco_impressao(mapa, "id-etched", "etched")
    assert (p, fin) == (25.00, "foil"), (p, fin)
    # E o contrário: uma nonfoil sem preço nonfoil cai para foil, não ao invés.
    so_foil = {"trend": {("x", "foil"): 4.0}, "low": {}}
    assert collection.preco_impressao(so_foil, "x", "nonfoil") == (4.0, "foil")
    # Uma carta que a fonte não cota de todo não vale zero por engano: vale nada.
    assert collection.preco_impressao(so_foil, "y", "nonfoil") == (None, None)
    print("uma etched cai para foil (25,00) e nao para nonfoil (3,00)")


def caso_o_colecionador_conta_para_o_valor_e_tem_parte_propria():
    """*"As de colecionador são avaliadas mas nunca contam para decks, wantlists
    ou cobertura."* Entram no valor — e numa parte própria, para nenhuma vista as
    somar sem o dizer."""
    con = base()
    povoar(con)
    v = collection.valor_da_coleccao(con)
    assert v["partes"]["trend"]["colecionador"] == 9.00, v["partes"]
    assert sum(v["partes"]["trend"].values()) == v["total"]["trend"]
    # A Caixa RL é a sua parte; o resto da gaveta é "coleccao".
    assert v["partes"]["trend"]["rl"] == 3.00, v["partes"]
    # E a página mostra a linha do colecionador só quando há alguma.
    h = paginas_html(con)
    assert "Colecionador" in h["colecao_cor.html"]
    con2 = base()
    copia(con2, "id-normal", "nonfoil", 1)
    out = Path(tempfile.mkdtemp()) / "c.html"
    colecao_cor.build(con2, out)
    assert "Colecionador" not in out.read_text(encoding="utf-8"), \
        "uma linha a dizer 0,00 € é ruído"
    print("o colecionador entra no valor, em parte propria, e so aparece se existir")


def caso_a_fonte_dos_precos_esta_fixa_no_cardmarket():
    """A conta dos Binders fazia `MIN` sobre a `price_latest` inteira. No dia em
    que o `CARTRADER_SETS` ligar o marketplace, o valor da coleção mudava por
    causa de uma fonte nova — sem ninguém mexer numa carta."""
    con = base()
    copia(con, "id-normal", "nonfoil", 1)
    con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, finish, "
                "date, low, trend) VALUES ('id-normal','cardtrader','nonfoil',"
                "'2026-09-24', 0.05, 0.05)")
    con.commit()
    assert collection.valor_da_coleccao(con)["total"]["trend"] == 1.50
    mapa = collection.mapa_precos(con, "cardtrader")
    assert mapa["trend"][("id-normal", "nonfoil")] == 0.05, "a fonte é escolhível"
    print("o valor sai do cardmarket, e uma fonte nova nao o muda sozinha")


def caso_a_caixa_rl_tem_uma_linha_por_impressao():
    """O Taiga de Unlimited e o de Revised eram UMA linha.

    A chave era `(carta, idioma, acabamento)`: a linha ficava com a edição e o
    preço de UMA das impressões e a quantidade de TODAS — 6 Taiga e 5 Tropical
    Island ao preço da outra edição, **1 391,77 € a mais** na Caixa, e o nome de
    uma edição por cima de cópias da outra.
    """
    import caixarl                                        # noqa: PLC0415
    con = base()
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, legalities, digital, reserved,
           image_uri) VALUES ('id-rev','or-taiga','Taiga','3ed','Revised Edition',
           '1','en','rare','Land',0,'RG','["nonfoil"]','1994-04-11','{}',0,1,'')""")
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, legalities, digital, reserved,
           image_uri) VALUES ('id-unl','or-taiga','Taiga','2ed','Unlimited Edition',
           '1','en','rare','Land',0,'RG','["nonfoil"]','1993-12-01','{}',0,1,'')""")
    for sid, p in (("id-rev", 100.0), ("id-unl", 900.0)):
        con.execute("INSERT OR REPLACE INTO price_latest (scryfall_id, source, "
                    "finish, date, low, trend) VALUES (?,'cardmarket','nonfoil',"
                    "'2026-09-24', ?, ?)", (sid, p, p))
    con.commit()
    copia(con, "id-rev", "nonfoil", 3, balde="Caixa Reserved List")
    copia(con, "id-unl", "nonfoil", 3, balde="Caixa Reserved List")
    linhas = [e for e in caixarl._rows(con) if e["nm"] == "Taiga"]
    assert len(linhas) == 2, [(e["st"], e["unit"], e["box_q"]) for e in linhas]
    assert {e["unit"] for e in linhas} == {100.0, 900.0}, linhas
    total = sum(e["unit"] * e["box_q"] for e in linhas)
    assert total == 3000.0, total          # 3×100 + 3×900, não 6×100 nem 6×900
    # E é exactamente o que a conta única diz para as mesmas seis cópias.
    v = collection.valor_da_coleccao(con)
    assert round(sum(c["total"] for c in v["copias"]
                     if c["sid"] in ("id-rev", "id-unl")), 2) == total
    print("a Caixa RL tem uma linha por impressao, com o preco de cada uma")


def caso_a_conta_vive_num_sitio_so():
    """Nenhuma página pode voltar a construir o seu mapa de preços por cópia.

    É a mesma trava do `jogaveis()` (`test_nao_encontrei`): o defeito não foi
    ninguém enganar-se na conta — foi haver seis contas.
    """
    alvo = re.compile(r"FROM\s+price_latest", re.I)
    usam = ("collection_gallery.py", "colecao_cor.py", "inicio.py",
            "caixarl.py", "reservedlist.py")
    for nome in usam:
        txt = (RAIZ / nome).read_text(encoding="utf-8")
        for i, linha in enumerate(txt.splitlines(), 1):
            if alvo.search(linha):
                # Duas perguntas diferentes que podem ficar: «até quando é que
                # estes dados são» (`MAX(date)`) e o MERCADO de uma impressão ao
                # longo do tempo, que a Reserved List mede em nonfoil nas duas
                # pontas da percentagem.
                ok = "MAX(date)" in linha or nome == "reservedlist.py"
                assert ok, (nome, i, linha.strip())
        assert "valor_da_coleccao" in txt or "collection.mapa_precos" in txt \
            or "collection.preco_impressao" in txt, f"{nome} não usa a conta única"
    assert not hasattr(collection_gallery, "_price_map"), \
        "a Galeria voltou a ter mapa de preços próprio"
    import caixarl                                        # noqa: PLC0415
    assert not hasattr(caixarl, "_price_maps"), \
        "a Caixa RL voltou a ter mapa de preços próprio"
    print("a conta do valor de uma copia vive so na collection.valor_da_coleccao")


def caso_o_grafico_diz_onde_a_regra_mudou():
    """Os pontos antigos do histórico foram medidos pela regra antiga e ficam.
    O que o gráfico tem de fazer é DIZER onde está a costura — senão um degrau
    de 11,67 € lê-se como o mercado a subir."""
    d = collection_gallery.REGRA_NOVA
    assert collection_gallery._costura(["2026-09-01", "2026-09-23", d]) == 2
    # Tudo antes: não há costura para marcar (a regra nova ainda não correu).
    assert collection_gallery._costura(["2026-09-01", "2026-09-23"]) is None
    # Tudo depois: também não — não há pontos da regra antiga.
    assert collection_gallery._costura([d, "2026-09-25"]) is None
    bloco = collection_gallery._evo_block([("2026-09-01", 100.0), (d, 111.67)])
    assert 'class="regra"' in bloco and d in bloco, bloco
    sem = collection_gallery._evo_block([(d, 100.0), ("2026-09-25", 101.0)])
    assert 'class="regra"' not in sem
    print("o grafico marca a costura da mudanca de regra")


def run():
    for fn in (caso_as_tres_paginas_mostram_o_mesmo_total,
               caso_as_tres_paginas_contam_as_mesmas_cartas,
               caso_uma_foil_sem_preco_foil_vale_o_nonfoil,
               caso_uma_etched_cai_para_foil_e_nao_para_nonfoil,
               caso_o_colecionador_conta_para_o_valor_e_tem_parte_propria,
               caso_a_fonte_dos_precos_esta_fixa_no_cardmarket,
               caso_a_caixa_rl_tem_uma_linha_por_impressao,
               caso_a_conta_vive_num_sitio_so,
               caso_o_grafico_diz_onde_a_regra_mudou):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
