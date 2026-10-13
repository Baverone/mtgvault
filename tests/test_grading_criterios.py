"""O MÉTODO DE GRADING (André, 2026-10-13: *"não te esqueças de fazer uma
pesquisa elaborada sobre como atribuir grade às cartas"*).

A pesquisa está em `data/grading-pesquisa-2026-10-13.txt` e o método foi
dobrado para o `data/estado-criterio.md`. O que este ficheiro tranca:

  1. o critério NOMEIA os três critérios — cantos, bordas, superfície — cada um
     com secção própria, e dá a forma fixa do `condition_notes`;
  2. diz EXPLICITAMENTE que a centragem não conta, e porquê;
  3. cada regra vive num sítio só (as citações do Cardmarket que mudaram de
     sítio não ficaram duplicadas) e as transcrições dos sete escalões e a
     secção «Aprendido com o André» continuam lá — e o `escrever_aprendido`,
     que reescreve essa secção, não come o método;
  4. o `pendentes/esperadas.md` traz os três critérios à frente de quem vai
     julgar, antes do critério por extenso.

Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [],
    "caixas": [],
    "revalidacao": {"desde": None, "alvo": None},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, encomendas, estado  # noqa: E402

CRIT = RAIZ / "data" / estado.CRITERIO
PESQUISA = RAIZ / "data" / "grading-pesquisa-2026-10-13.txt"


def texto() -> str:
    return CRIT.read_text(encoding="utf-8")


def caso_o_criterio_nomeia_os_tres_criterios():
    t = texto()
    assert estado.CRITERIOS == ("cantos", "bordas", "superfície"), estado.CRITERIOS
    assert "três critérios — cantos, bordas, superfície" in t
    for titulo in ("### 1. Cantos", "### 2. Bordas", "### 3. Superfície"):
        assert titulo in t, titulo
    # a forma fixa do `condition_notes`, com as três palavras
    assert "cantos: <o que se vê e onde> | bordas: <…> | superfície: <…>" in t
    # os limiares que a pesquisa trouxe, na escala DELE
    assert "Branco visível na borda a olho nu = já não é NM" in t
    assert "Um único canto amolecido" in t and "passa a EX" in t
    assert "dois metros" in t
    assert "Na dúvida, desce um escalão" in t
    assert "andou num deck sem sleeve praticamente nunca é NM" in t
    assert "Tapete PRETO — é REQUISITO" in t
    assert "lascada" in t and "pintada com" in t
    assert "Urza's" in t and "7.ª edição" in t          # clouding nos foils
    assert "duais de Revised" in t and "rolo" in t      # linhas de impressão
    assert "ERA CONTRA" in t
    assert PESQUISA.is_file(), "a pesquisa tem de estar no repositório"
    print("o critério nomeia cantos, bordas e superfície, com os limiares")


def caso_a_centragem_esta_excluida_e_diz_porque():
    t = texto()
    assert "### A centragem NÃO conta — está excluída" in t
    assert "fabrico" in t and "desgaste" in t
    assert "continua **NM** no Cardmarket" in t
    for tol in ("55/45", "65/35", "70/30"):
        assert tol in t, tol
    assert "centragem" in estado.SEM_CENTRAGEM.lower()
    print("a centragem está excluída, com as tolerâncias do PSA e a razão")


def caso_cada_regra_vive_num_sitio_so_e_nada_se_perdeu():
    t = texto()
    for frase in ("Visible clouding precludes", "scratches on the surface",
                  "Inked / Blackened Borders", "deformed so strongly",
                  "excessive bending", "Production Errors", "Old cards",
                  "bright daylight", "We don't support this kind of grading",
                  "compounded for"):
        n = t.count(frase)
        assert n >= 1, f"a regra perdeu-se: {frase}"
    for frase in ("Visible clouding precludes", "scratches on the surface",
                  "Inked / Blackened Borders", "deformed so strongly"):
        assert t.count(frase) == 1, f"a regra está duplicada: {frase}"
    assert "As regras avulsas" not in t, "a secção avulsa foi dobrada nos critérios"
    # As transcrições dos sete escalões ficam como estavam.
    for g in estado.ESCALA:
        assert f"### {g} — {estado.NOMES[g]}" in t, g
    assert "looks like it has never been played without sleeves" in t
    assert "Todos os versos de Magic são iguais" in t
    # O «Aprendido» fica, e reescrevê-lo não come o método.
    assert estado.MARCA_APRENDIDO in t and "Gerado de 0 correcções dele" in t
    assert t.index("## O método") < t.index(estado.MARCA_APRENDIDO)
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    con = cm.__enter__()
    try:
        copia = d / "crit.md"
        copia.write_text(t, encoding="utf-8")
        estado.escrever_aprendido(con, copia)
        novo = copia.read_text(encoding="utf-8")
        assert "### A centragem NÃO conta" in novo and "### 1. Cantos" in novo
        assert novo.count(estado.MARCA_APRENDIDO) == 1
    finally:
        cm.__exit__(None, None, None)
    print("cada regra num sítio só; os escalões e o «Aprendido» ficaram")


def caso_o_esperadas_traz_os_tres_criterios_a_frente_de_quem_julga():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    con = cm.__enter__()
    try:
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
               set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES ('id-ts','or-ts','Tundra','3ed','Revised','1','en','rare',
                       'Land','0','WU','["nonfoil"]','1994-04-01','{}',0,1)""")
        con.commit()
        dbs = con.execute("PRAGMA database_list").fetchall()
        db.DEFAULT_DB = Path(dbs[0]["file"])
        db.DEFAULT_CATALOG = Path(dbs[1]["file"])
        # uma cópia sem foto: é o bastante para o `esperadas.md` existir
        collection.add_copy(con, "Tundra", set_code="3ed", quantity=1,
                            sub_collection="Colecção")
        con.commit()
        # o critério do repositório vai para a pasta de dados do teste (o gesto
        # do daily — o `MTGVAULT_DB` do teste aponta para outro sítio)
        alvo = db.pasta_dados() / estado.CRITERIO
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto(), encoding="utf-8")
        pend = d / "pendentes"
        pend.mkdir()
        p = encomendas.escrever_esperadas(con, pend, slots=[])
        assert p is not None and p.is_file(), "o esperadas.md não se escreveu"
        md = p.read_text(encoding="utf-8")
    finally:
        cm.__exit__(None, None, None)
    sec = md.index("## O ESTADO DAS CARTAS")
    bala = md.index("TRÊS CRITÉRIOS", sec)
    for c in estado.CRITERIOS:
        assert f"**{c}**" in md[bala:bala + 600], c
    assert estado.FORMA_MOTIVOS in md
    assert "CENTRAGEM não conta" in md[bala:bala + 900]
    # à FRENTE: a bala vem antes do critério por extenso que se segue
    assert bala < md.index("## O método", sec), "os critérios vêm à frente"
    assert "### A centragem NÃO conta" in md
    print("o esperadas.md põe cantos, bordas e superfície à frente de quem julga")


CASOS = (caso_o_criterio_nomeia_os_tres_criterios,
         caso_a_centragem_esta_excluida_e_diz_porque,
         caso_cada_regra_vive_num_sitio_so_e_nada_se_perdeu,
         caso_o_esperadas_traz_os_tres_criterios_a_frente_de_quem_julga)


def main():
    for c in CASOS:
        c()
    print(f"\nOK — {len(CASOS)} casos (o método de grading)")


if __name__ == "__main__":
    main()
