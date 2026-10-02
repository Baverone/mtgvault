"""O NOME DO ARQUÉTIPO VEM DA FONTE (André, 2026-10-02, à letra).

*"Procura no mtgtop8, lá tem os nomes, e a partir daí já tens ideia do que são as
listas."* Tinha razão: a página do evento do mtgtop8 traz o nome ao lado de cada
deck e a recolha deitava-o fora — 2 635 listas de `mtgtop8` na base e nenhuma
coluna onde esse nome estivesse. É a MESMA falha do `commander`, fechada a
2026-10-01.

Cada caso aqui CHUMBA se a funcionalidade for retirada (é o padrão do
`_provar_chumba`; os alvos estão em `tests/_chumba_nomes.py`). O que se tranca:

  1. uma lista de mtgtop8 guarda o nome da fonte NA RECOLHA (`harvest` →
     `decklists.arquetipo_fonte`), e o parser lê-o de um trecho REAL da página;
  2. o nome da FONTE ganha ao do agrupamento — e um grupo sem nenhuma lista
     nomeada **não inventa nome** (fica provisório, com a etiqueta ao lado);
  3. uma lista de `mtgo`, que não traz nome nenhum, HERDA o do grupo;
  4. as **124 listas de Enchantress** e as **62 de Replenish** ficam em
     arquétipos DIFERENTES — e é por isso que a negação (`assinatura_sem`)
     existe: todas as 124 jogam `Replenish`;
  5. o backfill é RETOMÁVEL e não repete um evento já lido (o progresso é a
     própria base: `arquetipo_fonte_de = 'sem-nome'` quando a página não trazia
     nome), e a coluna nova está nos TRÊS sítios (schema, `_migrate`, quem a
     escreve) — com o ÍNDICE no `_migrate` e nunca no `schema.sql`.

Sem rede: o HTML é um trecho capturado da página real
`https://mtgtop8.com/event?e=91451&f=PREM` (2026-10-02). Fixa `MTGVAULT_HOME`
**e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
"""
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

CFG = {
    "regras_colecao": {}, "baldes_coleccao": ["Colecção"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "caixas": [], "regras_por_formato": [],
    "metagame_fontes": {"_default": {"tiers": ["Challenge", "Presencial"],
                                     "min_jogadores_presencial": 0}},
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import db, mtgtop8, nomes, sources  # noqa: E402

_ABERTAS = []

# ---------------------------------------------------------------------------
# O trecho REAL da página do evento (mtgtop8.com/event?e=91451&f=PREM, 02/10/2026).
# Dois decks, com a seta do deck aberto e os links da miniatura pelo meio — é
# exactamente a forma que o `parse_deck_archetypes` tem de aguentar.
# ---------------------------------------------------------------------------
PAGINA = """
  <div class=event_title><a class=arrow href=?e=91451&d=894542&f=PREM>&rarr;</a></div>
	<div class=meta_arch style="padding:2px;">Premodern <img src=/graph/star.png></div>
	<div style="margin-bottom:5px;">12 players - 30/09/26</div>
			<div class=chosen_tr style="padding:3px 0px 3px 0px;" align=left>
			    <div style="width:42px;" align=center class=S14>1</div>
			    <div style="width:80px;height:40px;background:black;"><a href=?e=91451&d=894541&f=PREM><img src=/metas_thumbs/1479.jpg></a></div>
			      <div class=S14 style="width:100%;padding-left:4px;margin-bottom:4px;"><a href=?e=91451&d=894541&f=PREM>Goblins</a> </div>
			      <div style="margin-right:10px;" align=right class=G11><a class=player href=search?player=Enrico+Vair>Enrico Vair</a></div>
			<div class=hover_tr style="padding:3px 0px 3px 0px;" align=left>
			    <div style="width:42px;" align=center class=S14>2</div>
			    <div style="width:80px;height:40px;background:black;"><a href=?e=91451&d=894542&f=PREM><img src=/metas_thumbs/1473.jpg></a></div>
			      <div class=S14 style="width:100%;padding-left:4px;margin-bottom:4px;"><a href=?e=91451&d=894542&f=PREM>Landstill</a> </div>
			      <div style="margin-right:10px;" align=right class=G11><a class=player href=search?player=Vittorio+Piatti>Vittorio Piatti</a></div>
			<div class=S14><a href=archetype?a=1479>Goblins decks</a></div>
"""

# A mesma página com os `&` escapados, que o mtgtop8 também serve.
PAGINA_AMP = PAGINA.replace("&d=", "&amp;d=").replace("&f=", "&amp;f=")

# Uma página de um evento em que o mtgtop8 não deu nome a um dos decks (acontece:
# na recuperação de 02/10/2026, 18 das 2 635 listas ficaram assim).
PAGINA_SEM_NOME = """
			      <div class=S14><a href=?e=777&d=111&f=PREM>Goblins</a> </div>
			      <div class=S14><a href=?e=777&d=222&f=PREM></a> </div>
"""

DEC = "// comentario\n4 [AVR] Griselbrand\n2 [] Force of Will\nSB: 1 [all] Swan Song\n"


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    return cm.__enter__()


def _lista(con, fonte, chave, fmt="premodern", cartas=(("Force of Will", "main"),),
           arquetipo=None, aid=None, url=None):
    sources.store_decklist(
        con, source=fonte, source_key=chave, fmt=fmt,
        cards=[(b, nm, 1) for nm, b in cartas], event_name="X Challenge",
        event_date="2026-09-20", player=f"j-{chave}", url=url or "",
        arquetipo=arquetipo)
    lid = con.execute("SELECT id FROM decklists WHERE source = ? AND source_key = ?",
                      (fonte, chave)).fetchone()["id"]
    if aid is not None:
        con.execute("UPDATE decklists SET archetype_id = ? WHERE id = ?", (aid, lid))
        con.commit()
    return lid


def _cluster(con, fmt, label):
    con.execute("INSERT OR IGNORE INTO archetypes (format, label) VALUES (?,?)",
                (fmt, label))
    con.commit()
    return con.execute("SELECT id FROM archetypes WHERE format = ? AND label = ?",
                       (fmt, label)).fetchone()["id"]


# ===========================================================================
# 1. O PARSER E A RECOLHA
# ===========================================================================
def caso_o_parser_le_o_nome_da_pagina_real():
    """A página do evento dá o nome ao lado de cada deck. O link da miniatura (que
    tem um `<img>` lá dentro) e a seta do deck aberto (`&rarr;`) não são nomes."""
    for titulo, html in (("normal", PAGINA), ("com &amp;", PAGINA_AMP)):
        achado = mtgtop8.parse_deck_archetypes(html)
        assert achado == {894541: "Goblins", 894542: "Landstill"}, (titulo, achado)
    # O link vazio não inventa nome nenhum.
    assert mtgtop8.parse_deck_archetypes(PAGINA_SEM_NOME) == {111: "Goblins"}
    assert mtgtop8.parse_deck_archetypes("<html>nada</html>") == {}
    print("o parser lê os nomes de um trecho real, e não inventa nenhum")


def caso_a_recolha_grava_o_nome_da_fonte(monkey=True):
    """O `harvest` do mtgtop8 guarda o nome NA RECOLHA — é o passo que o deitava
    fora. Sem rede: trocam-se os pedidos por páginas de mentira."""
    con = base()
    paginas = {"/format": "<a href=event?e=91451>x</a>",
               "/event": PAGINA, "/dec": DEC}
    antes = mtgtop8._get
    mtgtop8._get = lambda path, **kw: paginas[path]
    try:
        n = mtgtop8.harvest(con, "premodern", max_events=1)
    finally:
        mtgtop8._get = antes
    assert n == 2, n
    rows = {r["source_key"]: (r["arquetipo_fonte"], r["arquetipo_fonte_de"])
            for r in con.execute("SELECT source_key, arquetipo_fonte, "
                                 "arquetipo_fonte_de FROM decklists")}
    assert rows == {"894541": ("Goblins", "evento"),
                    "894542": ("Landstill", "evento")}, rows
    print("a recolha grava o nome da fonte, com `arquetipo_fonte_de = evento`")


def caso_a_coluna_esta_nos_tres_sitios_e_o_indice_no_migrate():
    """Uma coluna nova entra nos TRÊS sítios, e o ÍNDICE nasce no `_migrate`.

    O `schema.sql` corre INTEIRO antes do `_migrate`, por isso numa base já criada
    a coluna ainda não existe nesse momento: um `CREATE INDEX` ali rebentava o
    `db.init` com *"no such column"* — em todas as páginas e no `daily`. Já
    aconteceu duas vezes (o `ix_copies_validado` a 09/09, o `ix_dl_commander` a
    01/10). Este caso simula a base DELE: tira as colunas e manda abrir.
    """
    esquema = (RAIZ / "mtgvault" / "schema.sql").read_text(encoding="utf-8")
    assert "arquetipo_fonte" in esquema, "a coluna não está no schema.sql"
    assert "ix_dl_arquetipo" not in esquema, \
        "o CREATE INDEX da coluna nova NÃO pode viver no schema.sql"
    assert "ix_dl_arquetipo" in (RAIZ / "mtgvault" / "db.py").read_text(
        encoding="utf-8"), "o índice tem de nascer no _migrate"

    # A base ANTIGA, como a dele era: a `decklists` com tudo menos as duas
    # colunas novas. Reconstrói-se a partir das colunas que lá estão (menos as
    # duas) para o resto do `schema.sql` continuar a poder correr — há índices
    # noutras colunas (`ix_dl_dedupe` precisa do `content_hash`).
    d = Path(tempfile.mkdtemp())
    con = db.connect(d / "velha.db", d / "c.db")
    db.init(con)
    velhas = [(r["name"], r["type"]) for r in con.execute("PRAGMA table_info(decklists)")
              if r["name"] not in ("arquetipo_fonte", "arquetipo_fonte_de")]
    defs = ", ".join(f"{n} {t or 'TEXT'}" for n, t in velhas)
    cols = ", ".join(n for n, _t in velhas)
    con.execute(f"CREATE TABLE dl_velha ({defs}, UNIQUE (source, source_key))")
    con.execute(f"INSERT INTO dl_velha ({cols}) SELECT {cols} FROM decklists")
    con.execute("DROP TABLE decklists")
    con.execute("ALTER TABLE dl_velha RENAME TO decklists")
    con.execute("DROP INDEX IF EXISTS ix_dl_arquetipo")
    con.commit()
    cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
    assert "arquetipo_fonte" not in cols, cols
    db.init(con)                               # era aqui que rebentava
    cols = {r["name"] for r in con.execute("PRAGMA table_info(decklists)")}
    assert {"arquetipo_fonte", "arquetipo_fonte_de"} <= cols, cols
    idx = {r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert "ix_dl_arquetipo" in idx, idx
    con.close()
    print("a coluna está nos três sítios e a base antiga abre na mesma")


# ===========================================================================
# 2. O NOME DA FONTE GANHA; SEM FONTE NÃO SE INVENTA
# ===========================================================================
def caso_o_nome_da_fonte_ganha_ao_do_agrupamento():
    con = base()
    aid = _cluster(con, "premodern", "Solitary Confinement / Argothian Enchantress")
    _lista(con, "mtgtop8", "1", arquetipo="Enchantress", aid=aid)
    _lista(con, "mtgtop8", "2", arquetipo="Enchantress", aid=aid,
           cartas=(("Swan Song", "main"),))
    rot = nomes.rotulo(con, aid, etiqueta="Solitary Confinement / Argothian Enchantress",
                       gerado="Mono-Verde Argothian Enchantress", fmt="premodern")
    assert rot["nome"] == "Enchantress", rot
    assert rot["provisorio"] is False, rot
    assert rot["votos"] == 2 and rot["nomeadas"] == 2, rot
    print("o nome da fonte ganha, e a página sabe que não é provisório")


def caso_um_grupo_sem_nenhuma_lista_nomeada_nao_inventa_nome():
    """É a metade honesta da regra: sem nome na fonte, mostra-se o que se tinha —
    o nome composto das cartas e a etiqueta — e diz-se que é PROVISÓRIO."""
    con = base()
    aid = _cluster(con, "modern", "Carta A / Carta B / Carta C")
    _lista(con, "mtgo", "só-mtgo", fmt="modern", aid=aid)
    assert nomes.nome_do_cluster(con, aid, "modern") is None
    rot = nomes.rotulo(con, aid, etiqueta="Carta A / Carta B / Carta C",
                       gerado="Izzet Carta A", fmt="modern")
    assert rot["nome"] == "Izzet Carta A", rot
    assert rot["provisorio"] is True, rot
    assert rot["etiqueta"] == "Carta A / Carta B / Carta C", rot
    print("sem nome na fonte não se inventa um: fica provisório, com a etiqueta")


def caso_uma_lista_de_mtgo_herda_o_nome_do_grupo():
    """As 5 173 listas de `mtgo` da base dele não trazem nome nenhum. *"Uma lista
    de mtgo que caia no cluster da Enchantress passa a chamar-se Enchantress."*"""
    con = base()
    aid = _cluster(con, "premodern", "Sterling Grove / Wild Growth / Brushland")
    _lista(con, "mtgtop8", "nomeada", arquetipo="Enchantress", aid=aid)
    sem_nome = _lista(con, "mtgo", "herdeira", aid=aid,
                      cartas=(("Swan Song", "main"),))
    nome, origem = nomes.nome_da_lista(con, sem_nome)
    assert (nome, origem) == ("Enchantress", nomes.ORIGEM_HERDADO), (nome, origem)
    # E a que traz o nome responde pelo seu, não pelo do grupo.
    propria = con.execute("SELECT id FROM decklists WHERE source_key = 'nomeada'"
                          ).fetchone()["id"]
    assert nomes.nome_da_lista(con, propria) == ("Enchantress", nomes.ORIGEM_FONTE)
    # A cobertura conta as duas vias à parte — é o número do relatório.
    c = nomes.cobertura(con, "premodern")
    assert (c["da_fonte"], c["herdado"], c["sem_nome"]) == (1, 1, 0), c
    print("uma lista de mtgo herda o nome do grupo, e a cobertura conta as vias")


def caso_o_mais_votado_ganha_e_o_desempate_e_pelo_nome():
    """O desempate é ALFABÉTICO e nunca a ordem em que as linhas saem da base: um
    nome que muda de um dia para o outro sem nada ter mudado é o defeito que isto
    veio corrigir (foi o que aconteceu ao *"Dimir Psychatog"*)."""
    con = base()
    aid = _cluster(con, "legacy", "X / Y / Z")
    _lista(con, "mtgtop8", "a", fmt="legacy", arquetipo="Zebra", aid=aid)
    _lista(con, "mtgtop8", "b", fmt="legacy", arquetipo="Aluren", aid=aid,
           cartas=(("Swan Song", "main"),))
    v = nomes.nome_do_cluster(con, aid, "legacy")
    assert v["nome"] == "Aluren" and v["segundo"] == "Zebra", v
    # Com três votos, ganha o mais votado mesmo sendo o último por ordem.
    _lista(con, "mtgtop8", "c", fmt="legacy", arquetipo="Zebra", aid=aid,
           cartas=(("Dark Ritual", "main"),))
    v = nomes.nome_do_cluster(con, aid, "legacy")
    assert v["nome"] == "Zebra" and v["votos"] == 2, v
    print("ganha o mais votado; o empate desempata-se pelo nome, sempre igual")


# ===========================================================================
# 3. A ENCHANTRESS E O REPLENISH SÃO DOIS DECKS
# ===========================================================================
def caso_enchantress_e_replenish_ficam_em_arquetipos_diferentes():
    """O erro que esta ordem veio corrigir, e o mais caro da semana.

    Medido na base dele a 2026-10-02: **124** listas de Premodern jogam
    `Argothian Enchantress` e **todas as 124** jogam também `Replenish`; há **62**
    com Replenish e sem Argothian. São dois decks — as 124 são verde-brancas
    (Wild Growth, Mirri's Guile, Serra's Sanctum, Sterling Grove, Solitary
    Confinement) e as 62 são o combo azul-branco (Attunement, Frantic Search,
    Opalescence, Decree of Silence, Intuition). A assinatura `["Replenish"]`
    sozinha apanhava as 186 e fundia-os num consenso que não é de deck nenhum.
    """
    con = base()
    for i in range(3):      # a Enchantress: joga Replenish TAMBÉM
        _lista(con, "mtgtop8", f"ench{i}", arquetipo="Enchantress",
               cartas=(("Replenish", "main"), ("Argothian Enchantress", "main"),
                       ("Sterling Grove", "main")))
    for i in range(2):      # o combo azul-branco
        _lista(con, "mtgtop8", f"rep{i}", arquetipo="Replenish",
               cartas=(("Replenish", "main"), ("Attunement", "main"),
                       ("Decree of Silence", "main")))

    todas = sources.ids_por_assinatura(con, "premodern", ["Replenish"],
                                       so_que_contam=False)
    assert len(todas) == 5, "sem negação, a assinatura funde os dois decks"
    rep = sources.ids_por_assinatura(con, "premodern", ["Replenish"],
                                     sem=["Argothian Enchantress"],
                                     so_que_contam=False)
    ench = sources.ids_por_assinatura(con, "premodern", ["Argothian Enchantress"],
                                      so_que_contam=False)
    assert len(rep) == 2 and len(ench) == 3, (rep, ench)
    assert not (set(rep) & set(ench)), "os dois decks ainda se tocam"
    # E a FONTE confirma a separação, que é a prova que a ordem pede.
    assert nomes.nome_das_listas(con, ench)["nome"] == "Enchantress"
    assert nomes.nome_das_listas(con, rep)["nome"] == "Replenish"
    print("a negação separa os dois decks, e a fonte confirma os dois nomes")


def caso_a_negacao_vale_tambem_na_conjuncao():
    """O `sem` entra nos DOIS ramos do selector (o `IN` e o `EXISTS`): se só
    valesse num, a mesma pergunta tinha duas respostas conforme o `todas`."""
    con = base()
    _lista(con, "mtgtop8", "com", fmt="legacy", arquetipo="A",
           cartas=(("Goblin Welder", "main"), ("Sewer-veillance Cam", "main"),
                   ("Dark Ritual", "main")))
    _lista(con, "mtgtop8", "sem", fmt="legacy", arquetipo="B",
           cartas=(("Goblin Welder", "main"), ("Sewer-veillance Cam", "main")))
    par = ["Goblin Welder", "Sewer-veillance Cam"]
    assert len(sources.ids_por_assinatura(con, "legacy", par, todas=True,
                                          so_que_contam=False)) == 2
    so_um = sources.ids_por_assinatura(con, "legacy", par, todas=True,
                                       sem=["Dark Ritual"], so_que_contam=False)
    assert len(so_um) == 1, so_um
    assert sources.texto_assinatura(par, True, ["Dark Ritual"]) == \
        "Goblin Welder e Sewer-veillance Cam sem Dark Ritual"
    print("a negação vale na conjunção e no `basta uma`, e escreve-se por extenso")


# ===========================================================================
# 4. O BACKFILL É RETOMÁVEL
# ===========================================================================
def caso_o_backfill_e_retomavel_e_nao_repete_eventos():
    """O progresso é a PRÓPRIA BASE e não um ficheiro: uma lista cuja página já
    foi lida fica com nome ou com `arquetipo_fonte_de = 'sem-nome'`, e nunca mais
    entra na lista do que falta. É o mesmo truque do `event_players` a gravar 0.
    """
    con = base()
    # Duas listas do mesmo evento, uma das quais a página não nomeia.
    for did in (111, 222):
        _lista(con, "mtgtop8", str(did), url=f"https://mtgtop8.com/event?e=777&d={did}&f=PREM")
    con.execute("UPDATE decklists SET arquetipo_fonte = NULL, "
                "arquetipo_fonte_de = NULL")
    con.commit()
    por = mtgtop8.eventos_por_recuperar(con)
    assert por == {(777, "PREM"): [222, 111]} or por == {(777, "PREM"): [111, 222]}, por

    pedidos = []

    def falso(path, **kw):
        pedidos.append((path, kw))
        return PAGINA_SEM_NOME

    antes = mtgtop8._get
    mtgtop8._get = falso
    try:
        resumo = mtgtop8.backfill_archetype_names(con)
        assert "1 listas com nome" in resumo and "1 sem nome" in resumo, resumo
        assert len(pedidos) == 1, "mais do que uma página por EVENTO"
        # A segunda passagem não faz um único pedido.
        assert mtgtop8.backfill_archetype_names(con) == "nada por recuperar"
        assert len(pedidos) == 1, pedidos
    finally:
        mtgtop8._get = antes
    rows = {r["source_key"]: (r["arquetipo_fonte"], r["arquetipo_fonte_de"])
            for r in con.execute("SELECT source_key, arquetipo_fonte, "
                                 "arquetipo_fonte_de FROM decklists")}
    assert rows == {"111": ("Goblins", "recuperado"),
                    "222": (None, "sem-nome")}, rows
    print("o backfill lê uma página por evento, é retomável e não repete")


def caso_um_evento_que_falha_fica_para_a_corrida_seguinte():
    """Não se marca `sem-nome` a quem não foi LIDO: isso perdia o nome para
    sempre por causa de uma falha de rede de um segundo."""
    import requests                                           # noqa: PLC0415
    con = base()
    _lista(con, "mtgtop8", "999",
           url="https://mtgtop8.com/event?e=888&d=999&f=PREM")
    con.execute("UPDATE decklists SET arquetipo_fonte = NULL, "
                "arquetipo_fonte_de = NULL")
    con.commit()

    def rebenta(path, **kw):
        raise requests.ConnectionError("sem rede")

    antes = mtgtop8._get
    mtgtop8._get = rebenta
    try:
        resumo = mtgtop8.backfill_archetype_names(con)
    finally:
        mtgtop8._get = antes
    assert "1 eventos a falhar" in resumo, resumo
    r = con.execute("SELECT arquetipo_fonte_de FROM decklists").fetchone()
    assert r["arquetipo_fonte_de"] is None, "marcou um evento que não leu"
    assert mtgtop8.eventos_por_recuperar(con), "o evento saiu da fila"
    print("um evento que falha não se marca e volta na corrida seguinte")


def caso_a_pergunta_do_nome_vive_num_sitio_so():
    """Três sítios fazem a pergunta *"como se chama este deck?"* — o metagame, o
    showcase (que tem agrupamento próprio) e a arrumação por fases. Os três
    passam pelo `mtgvault.nomes`; o segundo contador ao lado discordava um dia
    qualquer, em silêncio (é a lição do `event_tier`, do `e_foil` e do
    `precos.sql()`)."""
    for ficheiro in ("meta_coverage.py", "showcase.py", "mtgvault/fases.py"):
        t = (RAIZ / ficheiro).read_text(encoding="utf-8")
        assert "nomes." in t, f"{ficheiro} não passa pelo mtgvault.nomes"
    # E ninguém volta a ler a coluna à mão para compor um nome. Os quatro que
    # podem tocá-la são os de sempre: o `nomes` (que a lê), o `sources`/`mtgtop8`
    # (que a escrevem na recolha), o `cli` e o `db` (o esquema). Uma MENÇÃO em
    # comentário ou docstring não conta — o que não pode haver é uma segunda
    # LEITURA: a coluna dentro de SQL, ou lida de uma linha da base.
    PODEM = {"nomes.py", "sources.py", "mtgtop8.py", "cli.py", "db.py"}
    # `decklists.arquetipo_fonte` aparece em prosa, por isso o uso de atributo
    # não serve de marca (e as linhas da base lêem-se por subscrito, não por
    # atributo: o `sqlite3.Row` é assim).
    USO = ("SELECT", "UPDATE", "INSERT", '["arquetipo_fonte"]',
           "['arquetipo_fonte']")
    maus = []
    for p in list(RAIZ.glob("*.py")) + list((RAIZ / "mtgvault").glob("*.py")):
        if p.name in PODEM:
            continue
        for i, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "arquetipo_fonte" in linha and any(u in linha for u in USO):
                maus.append(f"{p.name}:{i}")
    assert not maus, f"estes lêem a coluna à mão em vez do mtgvault.nomes: {maus}"
    print("a pergunta do nome vive num sítio só")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]


def run():
    for f in CASOS:
        f()
    print(f"\nTUDO OK ({len(CASOS)} casos)")


if __name__ == "__main__":
    try:
        run()
    finally:
        for cm in _ABERTAS:
            try:
                cm.__exit__(None, None, None)
            except sqlite3.Error:
                pass
