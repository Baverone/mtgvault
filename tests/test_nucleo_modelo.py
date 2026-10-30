"""O modelo do núcleo novo: as tabelas `n_*`, os 14 decks e o interruptor.

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários, e o `colecao_config.json` é um ficheiro temporário apontado por
`MTGVAULT_CONFIG` (lê-se a cada chamada, por isso pode mudar entre casos).
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db  # noqa: E402
from mtgvault.nucleo import modelo  # noqa: E402

TABELAS = ["n_deck", "n_versao", "n_versao_carta", "n_edicao", "n_posse",
           "n_posse_log", "n_montado", "n_a_mais", "n_saida", "n_valor",
           # A coleção, as fotos, o preço PT, o preço vigiado e as jogadas
           # (2026-10-30, ver schema.sql).
           "n_colecao", "n_colecao_carta", "n_colecao_log", "n_foto",
           "n_recorte", "n_validacao", "n_preco_pt", "n_preco_vigiado",
           "n_jogada"]

ROTATIVOS = {"pioneer_greasefang", "modern_affinity", "modern_oswald",
             "legacy_welder_cam"}
VIGIADOS = {"pauper_affinity": "mtgo:LuffyDoChapeuDePalha:pauper",
            "premodern_stifflenough": "mtgo:LuffyDoChapeuDePalha:premodern",
            "cedh_blue_farm": "moxfield:7O1sCuIti0igU6Us_Jhadg",
            "cedh_cloud": "moxfield:k6f2yED7oUGPtK2_rN_xwg"}


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def caso_tabelas_criadas():
    with sessao() as con:
        existem = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    em_falta = [t for t in TABELAS if t not in existem]
    assert not em_falta, f"tabelas em falta: {em_falta}"
    print(f"as {len(TABELAS)} tabelas n_* existem")


def caso_garantir_decks_idempotente():
    with sessao() as con:
        assert modelo.garantir_decks(con) == 14
        assert modelo.garantir_decks(con) == 0
        n = con.execute("SELECT count(*) FROM n_deck").fetchone()[0]
        assert n == 14, n
        # não mexe nos existentes: o André pode ter mudado o nome ou a ordem
        con.execute("UPDATE n_deck SET nome='Outro' WHERE slug='cedh_cloud'")
        con.commit()
        assert modelo.garantir_decks(con) == 0
        nome = con.execute(
            "SELECT nome FROM n_deck WHERE slug='cedh_cloud'").fetchone()[0]
        assert nome == "Outro", nome
    print("garantir_decks: 14, depois 0, e não pisa o que existe")


def caso_modos():
    with sessao() as con:
        modelo.garantir_decks(con)
        rot = {r["slug"] for r in modelo.decks(con, modo="rotativo")}
        sem = {r["slug"] for r in modelo.decks(con, modo="sempre")}
        todos = [r["slug"] for r in modelo.decks(con)]
        vig = {r["slug"]: r["vigia"] for r in modelo.decks(con)
               if r["vigia"]}
    assert rot == ROTATIVOS, rot
    assert len(sem) == 10 and not (sem & rot), sem
    assert len(todos) == 14 and len(set(todos)) == 14
    assert vig == VIGIADOS, vig
    ordem = [r["ordem"] for r in _linhas()]
    assert ordem == sorted(ordem) and len(set(ordem)) == 14, ordem
    print("4 rotativos, 10 sempre montados, 4 vigiados, por ordem")


def caso_ordem_por_formato_mesmo_numa_base_antiga():
    """(29/10) Uma base criada antes guarda a ordem antiga (Pauper primeiro);
    os decks saem na mesma pela ordem dos formatos que ele pediu."""
    antiga = ["pauper_affinity", "premodern_stifflenough", "premodern_replenish",
              "premodern_enchantress", "premodern_elves", "premodern_igg",
              "premodern_oath", "cedh_blue_farm", "cedh_cloud", "dc_cloud",
              "pioneer_greasefang", "modern_affinity", "modern_oswald",
              "legacy_welder_cam"]
    with sessao() as con:
        modelo.garantir_decks(con)
        for i, slug in enumerate(antiga, start=1):
            con.execute("UPDATE n_deck SET ordem = ? WHERE slug = ?", (i + 100, slug))
        for i, slug in enumerate(antiga, start=1):
            con.execute("UPDATE n_deck SET ordem = ? WHERE slug = ?", (i, slug))
        fmts = [r["formato"] for r in modelo.decks(con)]
        slugs = [r["slug"] for r in modelo.decks(con)]
    vistos = list(dict.fromkeys(fmts))
    assert vistos == [f for f in modelo.ORDEM_FORMATO if f in vistos], vistos
    assert slugs[:4] == ["pioneer_greasefang", "modern_affinity",
                         "modern_oswald", "legacy_welder_cam"], slugs
    assert slugs[4:10] == antiga[1:7], slugs
    print("os decks saem por formato mesmo com a ordem antiga guardada")


def _linhas():
    with sessao() as con:
        modelo.garantir_decks(con)
        return modelo.decks(con)


def caso_decks_coerentes_com_o_modo_do_formato():
    for d in modelo.DECKS:
        assert re.fullmatch(r"[a-z_]+", d["slug"]), d["slug"]
        assert d["formato"] in modelo.MODO_DO_FORMATO, d
        assert d["modo"] == modelo.MODO_DO_FORMATO[d["formato"]], d
        assert d["nome"] and d["arte_nome"], d
    assert modelo.MODO_DO_FORMATO == {
        "premodern": "sempre", "cedh": "sempre", "pauper": "sempre",
        "duel-commander": "sempre", "standard": "rotativo",
        "pioneer": "rotativo", "modern": "rotativo", "legacy": "rotativo"}
    print("slugs, formatos e modos coerentes")


def caso_ligado_omissao_false():
    antes = os.environ.get("MTGVAULT_CONFIG")
    try:
        tmp = Path(tempfile.mkdtemp()) / "cfg.json"
        os.environ["MTGVAULT_CONFIG"] = str(tmp)
        # sem ficheiro, sem chave e com o bloco sem a chave: tudo False
        assert modelo.ligado() is False
        tmp.write_text(json.dumps({"venda": {"mostrar": False}}), encoding="utf-8")
        assert modelo.ligado() is False
        tmp.write_text(json.dumps({"nucleo": {}}), encoding="utf-8")
        assert modelo.ligado() is False
        tmp.write_text(json.dumps({"nucleo": {"ligado": True}}), encoding="utf-8")
        assert modelo.ligado() is True
        # um cfg já lido ganha ao ficheiro
        assert modelo.ligado({}) is False
        assert modelo.ligado({"nucleo": {"ligado": True}}) is True
    finally:
        if antes is None:
            os.environ.pop("MTGVAULT_CONFIG", None)
        else:
            os.environ["MTGVAULT_CONFIG"] = antes
    print("nucleo.ligado: omissão False")


def caso_schema_e_migrate_iguais():
    """As definições `n_*` do `schema.sql` e do `db._migrate` não podem divergir:
    uma base nova e a do André ficavam com tabelas diferentes sem erro nenhum."""
    raiz = Path(__file__).resolve().parents[1] / "mtgvault"
    padrao = re.compile(r"CREATE (?:TABLE|INDEX) IF NOT EXISTS (?:n_|ix_n_)"
                        r"[^;\"]*", re.S)

    def normal(s):
        return re.sub(r"\s+", " ", s).strip()

    sql = [normal(m) for m in padrao.findall(
        (raiz / "schema.sql").read_text(encoding="utf-8"))]
    py = [normal(m) for m in padrao.findall(
        (raiz / "db.py").read_text(encoding="utf-8"))]
    # 19 tabelas (as 10 antigas e as 9 da coleção/fotos/preços) + 3 índices
    # (`ix_n_versao_carta`, `ix_n_validacao` e `ix_n_jogada_nome`, R25).
    assert len(sql) == 22, len(sql)
    assert sql == py, [(a, b) for a, b in zip(sql, py) if a != b]
    print(f"schema.sql e _migrate: {len(sql)} definições iguais")


def caso_checks_das_tabelas():
    import sqlite3
    with sessao() as con:
        for sql in (
            "INSERT INTO n_deck(slug,nome,formato,modo,ordem) VALUES('x','X','modern','talvez',1)",
            "INSERT INTO n_versao(slug,numero,criada_em,fonte,origem) VALUES('x',1,'d','f','outro')",
            "INSERT INTO n_posse(ambito,scryfall_id,acabamento,qtd) VALUES('a','s','nonfoil',-1)",
            "INSERT INTO n_montado(id,slug) VALUES(2,'x')",
            "INSERT INTO n_edicao(ambito,nome,scryfall_id,acabamento) VALUES('a','n','s','etched')",
        ):
            try:
                con.execute(sql)
            except sqlite3.IntegrityError:
                continue
            raise AssertionError(f"devia ter recusado: {sql}")
    print("os CHECK recusam o que não deviam aceitar")


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("caso_"):
            fn()
    print("\nTUDO OK")
