"""As vigias do núcleo: duas listas do MTGO que a recolha diária já guardou e dois
decks do Moxfield que chegam por um ficheiro.

Nada aqui abre a base do André nem sai para a rede: cada caso constrói a sua
base e o seu catálogo temporários (`db.session(vault_tmp, catalog_tmp)`), semeia
o `catalog.cards`, as `decklists` e as `decklist_cards` à mão, e o ficheiro do
Moxfield vive numa pasta temporária (`MTGVAULT_MOXFIELD_DIR`).
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

# antes do import: a omissão da pasta lê-se uma vez, no import do módulo
_PASTA_OMISSAO = tempfile.mkdtemp()
os.environ["MTGVAULT_MOXFIELD_DIR"] = _PASTA_OMISSAO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nucleo_decks  # noqa: E402
from mtgvault import db  # noqa: E402
from mtgvault.nucleo import listas, modelo, vigia  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

# Os ficheiros do Moxfield destes casos são de 28/10/2026: o «hoje» da vigia
# fica no dia seguinte, para um ficheiro de 28/10 não passar a velho (I2) com
# o calendário. Os casos do ficheiro velho mudam-no à mão.
HOJE_DOS_CASOS = date(2026, 10, 29)
vigia._hoje = lambda: HOJE_DOS_CASOS

CATALOGO = [
    "Myr Enforcer", "Thoughtcast", "Lightning Bolt", "Fling", "Island",
    "Stifle", "Force of Will", "Kraum, Ludevic's Opus", "Brainstorm",
    "Cloud, Midgar Mercenary", "Mountain",
]

BLUE_FARM = "7O1sCuIti0igU6Us_Jhadg"
CLOUD = "k6f2yED7oUGPtK2_rN_xwg"
LUFFY = "LuffyDoChapeuDePalha"


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def semear(con):
    for i, nome in enumerate(CATALOGO):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital)
               VALUES (?,?,?,'tst','Test Set',?,'en','rare','Land',0,'',?,
               '1993-08-05',?,0)""",
            (f"id-{i}", f"or-{i}", nome, str(i), json.dumps(["nonfoil"]),
             1000 + i))
    con.commit()
    modelo.garantir_decks(con)


def cheio(cartas):
    """(R19) Uma lista de 60: o main enche-se de Mountain até às 60 cartas."""
    main = sum(q for _n, q, b in cartas if b == "main")
    return list(cartas) + ([("Mountain", 60 - main, "main")] if main < 60 else [])


def cem(texto, comandante=0):
    """(R19) Um export do Moxfield com 100 cartas: acaba com o Mountain que
    falta até às 100 (o comandante conta; o side não)."""
    n, seccao, vistas = 0, "main", False
    for l in texto.splitlines():
        t = l.strip()
        if not t:
            if seccao == "main" and vistas:
                seccao = "side"
            elif seccao == "comandante":
                seccao = "main"
            continue
        if t.lower().startswith(("commander", "deck", "sideboard")):
            seccao = {"c": "comandante", "d": "main", "s": "side"}[t[0].lower()]
            vistas = False
            continue
        if seccao == "main":
            vistas = True
        if seccao != "side":
            n += int(t.split()[0])
    assert n < 100, n
    return texto.rstrip("\n") + "\n" + f"{100 - n} Mountain\n" if seccao != "side" \
        else texto


def lista_mtgo(con, *, jogador=LUFFY, formato="pauper", data="2026-10-20",
               evento="Pauper Challenge", cartas=(), source="mtgo", chave=None):
    """Uma decklist como a `harvest-mtgo` a deixa. `cartas`: (nome, qtd, board)."""
    cur = con.execute(
        "INSERT INTO decklists (source, source_key, format, event_name,"
        " event_date, player, url) VALUES (?,?,?,?,?,?,?)",
        (source, chave or f"{jogador}-{formato}-{data}-{evento}", formato,
         evento, data, jogador, f"https://www.mtgo.com/decklist/{data}"))
    for nome, qtd, board in cartas:
        con.execute("INSERT INTO decklist_cards (decklist_id, card_name,"
                    " quantity, board) VALUES (?,?,?,?)",
                    (cur.lastrowid, nome, qtd, board))
    con.commit()
    return cur.lastrowid


def pasta_moxfield(ficheiros):
    """{nome do ficheiro: dict (ou texto cru)} → pasta temporária."""
    pasta = Path(tempfile.mkdtemp())
    for nome, conteudo in ficheiros.items():
        texto = conteudo if isinstance(conteudo, str) else json.dumps(conteudo)
        (pasta / nome).write_text(texto, encoding="utf-8")
    return pasta


def n_versoes(con, slug=None):
    if slug:
        return con.execute("SELECT count(*) FROM n_versao WHERE slug = ?",
                           (slug,)).fetchone()[0]
    return con.execute("SELECT count(*) FROM n_versao").fetchone()[0]


def estado_vigia(con, slug):
    return con.execute("SELECT vigia_ok_em, vigia_erro FROM n_deck"
                       " WHERE slug = ?", (slug,)).fetchone()


def caso_mtgo_ultima_do_jogador():
    with sessao() as con:
        semear(con)
        lista_mtgo(con, data="2026-10-10", evento="Pauper Challenge A",
                   cartas=cheio([("Fling", 4, "main"), ("Island", 10, "main")]))
        # o nome do jogador com outra caixa também casa, e é a mais recente
        recente = lista_mtgo(
            con, jogador=LUFFY.lower(), data="2026-10-20",
            evento="Pauper Challenge B",
            cartas=cheio([("Myr Enforcer", 4, "main"), ("Thoughtcast", 4, "main"),
                          ("Island", 8, "main"), ("Lightning Bolt", 2, "side")]))
        # outro jogador, outro formato e outra fonte, mais recentes: não contam
        lista_mtgo(con, jogador="Outro", data="2026-10-27",
                   cartas=[("Brainstorm", 4, "main")])
        lista_mtgo(con, formato="premodern", data="2026-10-27",
                   cartas=[("Stifle", 4, "main")])
        lista_mtgo(con, source="mtgtop8", data="2026-10-28",
                   cartas=[("Force of Will", 4, "main")])
        assert recente

        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "nova", r
        v = listas.versao_atual(con, "pauper_affinity")
        assert v["numero"] == 1 and v["origem"] == "vigia", v
        assert sorted(v["linhas"]) == sorted([
            Linha("main", "Myr Enforcer", 4), Linha("main", "Thoughtcast", 4),
            Linha("main", "Island", 8), Linha("main", "Mountain", 44),
            Linha("side", "Lightning Bolt", 2)]), v
        assert v["fonte"] == ("MTGO · Pauper Challenge B · 2026-10-20 · "
                              "https://www.mtgo.com/decklist/2026-10-20"), v

        # uma lista ainda mais recente do mesmo dia (id maior) ganha o desempate
        lista_mtgo(con, data="2026-10-20", evento="Pauper Challenge C",
                   cartas=cheio([("Myr Enforcer", 4, "main"), ("Thoughtcast", 4, "main"),
                                 ("Island", 8, "main"), ("Fling", 4, "main")]))
        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "nova" and r["numero"] == 2, r
        assert "Pauper Challenge C" in listas.versao_atual(
            con, "pauper_affinity")["fonte"]
    print("MTGO: a lista mais recente do jogador, sem caixa, no formato dele")


def caso_mtgo_ganha_a_data_do_evento_e_nao_o_id():
    with sessao() as con:
        semear(con)
        lista_mtgo(con, data="2026-10-20", evento="Evento Novo",
                   cartas=cheio([("Fling", 4, "main")]))
        # inserida DEPOIS (id maior), mas de um evento mais antigo
        lista_mtgo(con, data="2026-10-10", evento="Evento Velho",
                   cartas=cheio([("Island", 4, "main")]))
        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "nova", r
        v = listas.versao_atual(con, "pauper_affinity")
        assert v["linhas"] == [Linha("main", "Fling", 4),
                               Linha("main", "Mountain", 56)], v
        assert "Evento Novo" in v["fonte"], v["fonte"]
    print("MTGO: ganha o event_date mais recente, não o id maior")


def caso_mtgo_igual_nao_cria_versao():
    with sessao() as con:
        semear(con)
        lista_mtgo(con, cartas=cheio([("Fling", 4, "main"), ("Island", 8, "side")]))
        assert vigia.vigiar_mtgo(con, "pauper_affinity")["estado"] == "nova"
        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "igual", r
        assert n_versoes(con, "pauper_affinity") == 1
        # outra lista com as mesmas cartas (outro evento) continua a ser igual
        lista_mtgo(con, data="2026-10-25", evento="Outro Evento",
                   cartas=cheio([("Fling", 4, "main"), ("Island", 8, "side")]))
        assert vigia.vigiar_mtgo(con, "pauper_affinity")["estado"] == "igual"
        assert n_versoes(con, "pauper_affinity") == 1
    print("MTGO: a mesma lista não cria versão")


def caso_mtgo_sem_lista():
    """Nunca teve versão e não há lista: é uma falha (`sem_lista`)."""
    with sessao() as con:
        semear(con)
        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "sem_lista" and r["mensagem"], r
        assert n_versoes(con) == 0
    print("MTGO: sem lista e sem versão = sem_lista (falha)")


def caso_mtgo_sem_lista_nova_nao_e_falha():
    """A recolha poda as listas a 30 dias. Se o deck já tem versão, não haver
    lista na janela não é falha: fica a última versão, sem erro, e o
    `vigia_ok_em` não anda."""
    with sessao() as con:
        semear(con)
        # só este deck é vigiado, para o VigiaFalhou não ter outras causas
        con.execute("UPDATE n_deck SET vigia = NULL WHERE slug <> 'pauper_affinity'")
        con.commit()
        lista_mtgo(con, cartas=cheio([("Fling", 4, "main")]))
        assert vigia.vigiar_todos(con)["pauper_affinity"]["estado"] == "nova"
        ok_em, erro = estado_vigia(con, "pauper_affinity")
        assert ok_em and erro is None
        # um erro antigo desaparece quando o estado passa a sem_lista_nova
        con.execute("UPDATE n_deck SET vigia_erro = 'velho' WHERE slug ="
                    " 'pauper_affinity'")
        con.execute("DELETE FROM decklists")
        con.commit()

        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "sem_lista_nova" and r["mensagem"], r
        assert n_versoes(con, "pauper_affinity") == 1
        res = vigia.vigiar_todos(con, levantar=True)        # não levanta
        assert res["pauper_affinity"]["estado"] == "sem_lista_nova", res
        assert tuple(estado_vigia(con, "pauper_affinity")) == (ok_em, None)
        assert listas.versao_atual(con, "pauper_affinity")["numero"] == 1
    print("MTGO: sem lista nova mas com versão = não é falha, ok_em intacto")


def caso_mtgo_nome_desconhecido_nada_grava():
    with sessao() as con:
        semear(con)
        lista_mtgo(con, cartas=cheio([("Fling", 4, "main"),
                                      ("Carta Que Nao Existe", 2, "main")]))
        r = vigia.vigiar_mtgo(con, "pauper_affinity")
        assert r["estado"] == "erro", r
        assert "Carta Que Nao Existe" in r["mensagem"], r
        assert n_versoes(con) == 0
    print("MTGO: nome desconhecido = erro, nenhuma versão parcial")


def caso_moxfield_ficheiro_mais_recente():
    pasta = pasta_moxfield({
        "2026-10-26.json": {"lido_em": "2026-10-26T09:00:00", "decks": {
            BLUE_FARM: {"texto": cem("1 Fling\n1 Island\n"), "titulo": "Blue Farm"}}},
        "2026-10-28.json": {"lido_em": "2026-10-28T09:30:12", "decks": {
            BLUE_FARM: {"texto": "Commander\n1 Kraum, Ludevic's Opus (CMR) 89\n"
                                 "\nDeck\n1 Force of Will (ALL) 54a *F*\n"
                                 "2 Island\n96 Mountain\n\nSideboard\n1 Fling\n",
                        "titulo": "Blue Farm"},
            CLOUD: {"texto": "Commander\n1 Cloud, Midgar Mercenary\n"
                             "\n99 Mountain\n", "titulo": "Cloud"}}},
        # ficheiros com outro nome não contam, mesmo que "mais recentes"
        "2026-11-30-copia.json": {"lido_em": "2026-11-30T00:00:00", "decks": {}},
        "notas.txt": "nada",
        "2026-10-29.json.bak": "{",
    })
    with sessao() as con:
        semear(con)
        r = vigia.vigiar_moxfield(con, "cedh_blue_farm", pasta=pasta)
        assert r["estado"] == "nova", r
        v = listas.versao_atual(con, "cedh_blue_farm")
        assert v["origem"] == "vigia" and v["numero"] == 1, v
        assert sorted(v["linhas"]) == sorted([
            Linha("comandante", "Kraum, Ludevic's Opus", 1),
            Linha("main", "Force of Will", 1), Linha("main", "Island", 2),
            Linha("main", "Mountain", 96), Linha("side", "Fling", 1)]), v
        assert v["fonte"] == ("Moxfield · https://moxfield.com/decks/"
                              f"{BLUE_FARM} · lido a 2026-10-28"), v["fonte"]
        assert vigia.vigiar_moxfield(con, "cedh_blue_farm",
                                     pasta=pasta)["estado"] == "igual"
        r = vigia.vigiar_moxfield(con, "cedh_cloud", pasta=pasta)
        assert r["estado"] == "nova", r
        assert "moxfield.com/decks/" + CLOUD in listas.versao_atual(
            con, "cedh_cloud")["fonte"]
    print("Moxfield: o ficheiro mais recente pelo nome, os outros ignoram-se")


def caso_moxfield_sem_ficheiro_ou_sem_o_deck():
    vazia = pasta_moxfield({"notas.txt": "nada"})
    inexistente = Path(tempfile.mkdtemp()) / "nao-existe"
    so_um = pasta_moxfield({"2026-10-28.json": {
        "lido_em": "2026-10-28T09:30:12",
        "decks": {BLUE_FARM: {"texto": "1 Fling\n", "titulo": "x"}}}})
    with sessao() as con:
        semear(con)
        for pasta in (vazia, inexistente):
            r = vigia.vigiar_moxfield(con, "cedh_blue_farm", pasta=pasta)
            assert r["estado"] == "sem_ficheiro" and r["mensagem"], r
        r = vigia.vigiar_moxfield(con, "cedh_cloud", pasta=so_um)
        assert r["estado"] == "sem_ficheiro", r
        assert "2026-10-28" in r["mensagem"] and "não tem este deck" in r[
            "mensagem"], r
        assert n_versoes(con) == 0
    print("Moxfield: sem ficheiro, ou ficheiro sem o deck")


def caso_moxfield_erro_no_ficheiro():
    pastas = {
        "json estragado": pasta_moxfield({"2026-10-28.json": "{ isto nao"}),
        "deck com erro": pasta_moxfield({"2026-10-28.json": {
            "lido_em": "2026-10-28T09:30:12",
            "decks": {BLUE_FARM: {"erro": "o Moxfield pediu um desafio"}}}}),
        "nome desconhecido": pasta_moxfield({"2026-10-28.json": {
            "lido_em": "2026-10-28T09:30:12",
            "decks": {BLUE_FARM: {"texto": "1 Fling\n1 Carta Inventada\n",
                                  "titulo": "x"}}}}),
        "sem texto": pasta_moxfield({"2026-10-28.json": {
            "lido_em": "2026-10-28T09:30:12",
            "decks": {BLUE_FARM: {"texto": "", "titulo": "x"}}}}),
    }
    with sessao() as con:
        semear(con)
        for que, pasta in pastas.items():
            r = vigia.vigiar_moxfield(con, "cedh_blue_farm", pasta=pasta)
            assert r["estado"] == "erro" and r["mensagem"], (que, r)
            assert n_versoes(con) == 0, que
        assert "desafio" in vigia.vigiar_moxfield(
            con, "cedh_blue_farm", pasta=pastas["deck com erro"])["mensagem"]
        assert "Carta Inventada" in vigia.vigiar_moxfield(
            con, "cedh_blue_farm",
            pasta=pastas["nome desconhecido"])["mensagem"]

        # vigiar_todos grava a razão em n_deck.vigia_erro
        vigia.vigiar_todos(con, pasta=pastas["deck com erro"])
        ok_em, erro = estado_vigia(con, "cedh_blue_farm")
        assert ok_em is None and "desafio" in erro, (ok_em, erro)
    print("Moxfield: ficheiro estragado, deck com erro, nomes e lista vazia")


def caso_moxfield_ficheiro_com_bom_do_powershell():
    """O PowerShell 5.1 escreve UTF-8 com BOM; o ficheiro tem de ler na mesma."""
    pasta = Path(tempfile.mkdtemp())
    conteudo = json.dumps({"lido_em": "2026-10-28T09:30:12", "decks": {
        BLUE_FARM: {"texto": cem("1 Fling\n1 Island\n"), "titulo": "Blue Farm"}}})
    (pasta / "2026-10-28.json").write_bytes(b"\xef\xbb\xbf" + conteudo.encode())
    with sessao() as con:
        semear(con)
        r = vigia.vigiar_moxfield(con, "cedh_blue_farm", pasta=pasta)
        assert r["estado"] == "nova", r
    print("Moxfield: ficheiro com BOM lê-se")


def caso_moxfield_linha_mal_formada_e_erro():
    """`SB:` sozinho faz o `ler_texto` rebentar: é erro deste deck."""
    pasta = pasta_moxfield({"2026-10-28.json": {
        "lido_em": "2026-10-28T09:30:12",
        "decks": {BLUE_FARM: {"texto": "1 Fling\nSB:\n", "titulo": "x"}}}})
    with sessao() as con:
        semear(con)
        r = vigia.vigiar_moxfield(con, "cedh_blue_farm", pasta=pasta)
        assert r["estado"] == "erro" and r["mensagem"], r
        assert n_versoes(con) == 0
    print("Moxfield: linha mal formada = erro, sem levantar")


def caso_falha_levanta_no_fim():
    pasta = pasta_moxfield({"2026-10-28.json": {
        "lido_em": "2026-10-28T09:30:12",
        "decks": {BLUE_FARM: {"texto": cem("1 Fling\n1 Island\n"), "titulo": "x"},
                  CLOUD: {"erro": "não consegui abrir o deck"}}}})
    with sessao() as con:
        semear(con)
        # um vigia bom (Moxfield) e três a falhar (sem lista no MTGO x2, erro)
        try:
            vigia.vigiar_todos(con, pasta=pasta, levantar=True)
            raise AssertionError("devia ter levantado VigiaFalhou")
        except vigia.VigiaFalhou as e:
            assert set(e.falhas) == {"pauper_affinity", "premodern_stifflenough",
                                     "cedh_cloud"}, e.falhas
            assert "cedh_cloud" in str(e)
        # a versão boa ficou gravada antes de se levantar
        assert listas.versao_atual(con, "cedh_blue_farm")["numero"] == 1
        ok_em, erro = estado_vigia(con, "cedh_blue_farm")
        # (I2) o `vigia_ok_em` do Moxfield é o `lido_em` do ficheiro: a lista
        # é de quando foi LIDA no Chrome, não de quando o daily a viu
        assert erro is None and ok_em == "2026-10-28T09:30:12", ok_em
        for slug in ("pauper_affinity", "premodern_stifflenough", "cedh_cloud"):
            ok_em, erro = estado_vigia(con, slug)
            assert ok_em is None and erro, (slug, ok_em, erro)

        # sem `levantar` devolve tudo e não levanta
        res = vigia.vigiar_todos(con, pasta=pasta)
        assert res["cedh_blue_farm"]["estado"] == "igual"
        assert res["pauper_affinity"]["estado"] == "sem_lista"
        assert res["cedh_cloud"]["estado"] == "erro"
        # só os decks com vigia: os outros 10 não aparecem
        assert set(res) == {"pauper_affinity", "premodern_stifflenough",
                            "cedh_blue_farm", "cedh_cloud"}, set(res)
    print("vigiar_todos: grava os bons, levanta VigiaFalhou no fim")


def caso_ok_limpa_o_erro_e_a_falha_guarda_o_ultimo_ok():
    with sessao() as con:
        semear(con)
        # primeiro falha, depois a lista aparece
        vigia.vigiar_todos(con, pasta=pasta_moxfield({}))
        assert estado_vigia(con, "pauper_affinity")[1]
        lista_mtgo(con, cartas=cheio([("Fling", 4, "main")]))
        res = vigia.vigiar_todos(con, pasta=pasta_moxfield({}))
        assert res["pauper_affinity"]["estado"] == "nova"
        ok_em, erro = estado_vigia(con, "pauper_affinity")
        assert ok_em and erro is None, (ok_em, erro)
        # um Moxfield que passa a falhar guarda o último ok e põe o erro
        pasta = pasta_moxfield({"2026-10-28.json": {
            "lido_em": "2026-10-28T09:30:12",
            "decks": {BLUE_FARM: {"texto": cem("1 Fling\n"), "titulo": "x"}}}})
        vigia.vigiar_todos(con, pasta=pasta)
        ok_azul, erro_azul = estado_vigia(con, "cedh_blue_farm")
        assert ok_azul and erro_azul is None
        vigia.vigiar_todos(con, pasta=pasta_moxfield({}))
        ok_azul2, erro_azul2 = estado_vigia(con, "cedh_blue_farm")
        assert ok_azul2 == ok_azul and erro_azul2, (ok_azul, ok_azul2, erro_azul2)
        assert listas.versao_atual(con, "cedh_blue_farm")["numero"] == 1
    print("vigia_ok_em limpa o erro; a falha guarda o último ok")


def caso_vigia_desconhecida_e_pasta_por_omissao():
    pasta = Path(_PASTA_OMISSAO)
    (pasta / "2026-10-28.json").write_text(json.dumps({
        "lido_em": "2026-10-28T09:30:12",
        "decks": {BLUE_FARM: {"texto": cem("1 Fling\n"), "titulo": "x"}}}),
        encoding="utf-8")
    assert vigia.PASTA_MOXFIELD == pasta, vigia.PASTA_MOXFIELD
    try:
        with sessao() as con:
            semear(con)
            con.execute("UPDATE n_deck SET vigia = 'twitter:alguem'"
                        " WHERE slug = 'cedh_cloud'")
            con.commit()
            res = vigia.vigiar_todos(con)       # sem `pasta`: a da omissão
            assert res["cedh_blue_farm"]["estado"] == "nova", res
            assert res["cedh_cloud"]["estado"] == "erro", res
            assert "twitter" in res["cedh_cloud"]["mensagem"]
            assert "twitter" in estado_vigia(con, "cedh_cloud")[1]
    finally:
        (pasta / "2026-10-28.json").unlink()
    print("prefixo desconhecido = falha com mensagem; pasta por omissão")


def caso_so_escreve_tabelas_n():
    pasta = pasta_moxfield({"2026-10-28.json": {
        "lido_em": "2026-10-28T09:30:12",
        "decks": {BLUE_FARM: {"texto": cem("1 Fling\n"), "titulo": "x"}}}})
    tabelas = ("copies", "copy_allocation", "posse_marcada", "decks",
               "deck_cards", "decklists", "decklist_cards")
    with sessao() as con:
        semear(con)
        lista_mtgo(con, cartas=cheio([("Fling", 4, "main")]))
        antes = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                 for t in tabelas}
        vigia.vigiar_todos(con, pasta=pasta)
        depois = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in tabelas}
        assert antes == depois, (antes, depois)
    print("só escreve nas tabelas n_*")


def _so_vigiado(con, slug):
    con.execute("UPDATE n_deck SET vigia = NULL WHERE slug <> ?", (slug,))
    con.commit()


def _moxfield(dia, decks, lido_em=None):
    return pasta_moxfield({f"{dia}.json": {"lido_em": lido_em or f"{dia}T09:30:12",
                                           "decks": decks}})


def caso_moxfield_erro_da_fonte_com_versao_nao_e_falha():
    """(I2, R17) O Moxfield falhou hoje ({"erro"}) para um deck que já tem
    versão: fica a versão, a página diz «não consegui ver a lista desde X» e
    o daily NÃO fica vermelho por isso — quem fica vermelho é a tarefa do
    Chrome (uma causa, um vermelho). Um deck que nunca teve versão falha na
    mesma, e um nome desconhecido também."""
    with sessao() as con:
        semear(con)
        _so_vigiado(con, "cedh_blue_farm")
        bom = _moxfield("2026-10-28", {BLUE_FARM: {"texto": cem("1 Fling\n"),
                                                   "titulo": "x"}})
        vigia.vigiar_todos(con, pasta=bom, levantar=True)
        ok_em, erro = estado_vigia(con, "cedh_blue_farm")
        assert ok_em == "2026-10-28T09:30:12" and erro is None, (ok_em, erro)
        mau = _moxfield("2026-10-29", {BLUE_FARM: {"erro": "o Moxfield pediu um desafio"}})
        res = vigia.vigiar_todos(con, pasta=mau, levantar=True)     # não levanta
        assert res["cedh_blue_farm"]["estado"] == "erro_fonte", res
        ok2, erro2 = estado_vigia(con, "cedh_blue_farm")
        assert ok2 == ok_em and "desafio" in erro2, (ok2, erro2)
        assert listas.versao_atual(con, "cedh_blue_farm")["numero"] == 1
        # a página diz desde quando (é o aviso de qualquer vigia_erro)
        p = nucleo_decks.html_page(con)
        assert "não consegui ver a lista desde 28/10/2026" in p
        # um nome desconhecido num deck com versão continua a ser falha
        nomes = _moxfield("2026-10-29", {BLUE_FARM: {
            "texto": cem("1 Fling\n1 Carta Inventada\n"), "titulo": "x"}})
        try:
            vigia.vigiar_todos(con, pasta=nomes, levantar=True)
            raise AssertionError("um nome desconhecido devia levantar VigiaFalhou")
        except vigia.VigiaFalhou as e:
            assert set(e.falhas) == {"cedh_blue_farm"}, e.falhas
    with sessao() as con:
        semear(con)
        _so_vigiado(con, "cedh_blue_farm")
        mau = _moxfield("2026-10-29", {BLUE_FARM: {"erro": "o Moxfield pediu um desafio"}})
        try:
            vigia.vigiar_todos(con, pasta=mau, levantar=True)
            raise AssertionError("sem versão nenhuma, o erro da fonte é falha")
        except vigia.VigiaFalhou as e:
            assert e.falhas["cedh_blue_farm"]["estado"] == "erro", e.falhas
    print("Moxfield: o erro da fonte num deck com versão não pinta o daily")


def caso_moxfield_ficheiro_velho_nao_e_falha():
    """(I2) O ficheiro mais recente tem mais de 2 dias: a tarefa do Chrome não
    correu (e é ela que fica vermelha). Aqui é um aviso: «o último ficheiro do
    Moxfield é de 28/10/2026», sem tocar na versão nem no `vigia_ok_em`."""
    antes = vigia._hoje
    try:
        with sessao() as con:
            semear(con)
            _so_vigiado(con, "cedh_blue_farm")
            pasta = _moxfield("2026-10-28", {BLUE_FARM: {"texto": cem("1 Fling\n"),
                                                         "titulo": "x"}})
            vigia._hoje = lambda: date(2026, 10, 30)          # 2 dias: ainda serve
            assert vigia.vigiar_todos(con, pasta=pasta)["cedh_blue_farm"]["estado"] == "nova"
            ok_em = estado_vigia(con, "cedh_blue_farm")[0]
            vigia._hoje = lambda: date(2026, 10, 31)          # 3 dias: velho
            res = vigia.vigiar_todos(con, pasta=pasta, levantar=True)
            r = res["cedh_blue_farm"]
            assert r["estado"] == "erro_fonte", r
            assert r["mensagem"] == "o último ficheiro do Moxfield é de 28/10/2026", r
            assert tuple(estado_vigia(con, "cedh_blue_farm")) == (ok_em, r["mensagem"])
    finally:
        vigia._hoje = antes
    print("Moxfield: ficheiro com mais de 2 dias = aviso, não falha")


def caso_guarda_da_lista_lida():
    """(I3, R19) Antes de gravar uma versão da vigia: um deck de comandante tem
    100 cartas (comandante + main); um de 60 tem main >= 60 e side <= 15; e,
    havendo versão, a lista lida tem de ter pelo menos 60 % dos nomes dela.
    Senão não se grava nada e fica o aviso «a lista lida parece outro deck ou
    está incompleta (…)», sem pintar o daily."""
    with sessao() as con:
        semear(con)
        _so_vigiado(con, "cedh_blue_farm")
        curta = _moxfield("2026-10-28", {BLUE_FARM: {
            "texto": "1 Fling\n98 Mountain\n", "titulo": "x"}})
        res = vigia.vigiar_todos(con, pasta=curta, levantar=True)    # não levanta
        r = res["cedh_blue_farm"]
        assert r["estado"] == "lista_suspeita", r
        assert r["mensagem"].startswith("a lista lida parece outro deck ou está"
                                        " incompleta ("), r
        assert "99" in r["mensagem"] and "100" in r["mensagem"], r
        assert n_versoes(con) == 0
        ok_em, erro = estado_vigia(con, "cedh_blue_farm")
        assert ok_em is None and erro == r["mensagem"], (ok_em, erro)
        # 100 com o side à parte: passa
        boa = _moxfield("2026-10-28", {BLUE_FARM: {
            "texto": "Commander\n1 Kraum, Ludevic's Opus\n\nDeck\n1 Fling\n"
                     "98 Mountain\n\nSideboard\n3 Island\n", "titulo": "x"}})
        assert vigia.vigiar_todos(con, pasta=boa)["cedh_blue_farm"]["estado"] == "nova"
        # outro deck com 100 cartas: só 1 dos 4 nomes da versão (25 %)
        outro = _moxfield("2026-10-28", {BLUE_FARM: {
            "texto": "1 Brainstorm\n1 Stifle\n97 Lightning Bolt\n1 Fling\n",
            "titulo": "x"}})
        r = vigia.vigiar_todos(con, pasta=outro, levantar=True)["cedh_blue_farm"]
        assert r["estado"] == "lista_suspeita" and "25 % dos nomes da v1" in r["mensagem"], r
        assert listas.versao_atual(con, "cedh_blue_farm")["numero"] == 1
    with sessao() as con:
        semear(con)
        _so_vigiado(con, "pauper_affinity")
        lista_mtgo(con, data="2026-10-10", cartas=[("Fling", 4, "main"),
                                                    ("Mountain", 55, "main")])
        r = vigia.vigiar_todos(con, levantar=True)["pauper_affinity"]
        assert r["estado"] == "lista_suspeita" and "59" in r["mensagem"], r
        lista_mtgo(con, data="2026-10-11", cartas=[
            ("Fling", 4, "main"), ("Mountain", 56, "main"), ("Island", 16, "side")])
        r = vigia.vigiar_todos(con, levantar=True)["pauper_affinity"]
        assert r["estado"] == "lista_suspeita" and "16" in r["mensagem"], r
        assert n_versoes(con) == 0
        lista_mtgo(con, data="2026-10-12", cartas=[
            ("Fling", 4, "main"), ("Mountain", 56, "main"), ("Island", 15, "side")])
        assert vigia.vigiar_todos(con, levantar=True)["pauper_affinity"]["estado"] == "nova"
        assert estado_vigia(con, "pauper_affinity")[1] is None
    print("guarda: 100 no comandante, 60/15 nos outros, 60 % dos nomes")


def caso_mensagem_sem_caminho_do_pc():
    """(M1) O `vigia_erro` vai para o site publicado: nunca leva um caminho do
    PC. O caminho fica no `detalhe`, que só vai para o log (o VigiaFalhou)."""
    inexistente = Path(tempfile.mkdtemp()) / "nao-existe"
    with sessao() as con:
        semear(con)
        _so_vigiado(con, "cedh_blue_farm")
        try:
            vigia.vigiar_todos(con, pasta=inexistente, levantar=True)
            raise AssertionError("devia levantar")
        except vigia.VigiaFalhou as e:
            r = e.falhas["cedh_blue_farm"]
            assert str(inexistente) not in r["mensagem"], r
            assert str(inexistente) in r["detalhe"] and str(inexistente) in str(e), r
        erro = estado_vigia(con, "cedh_blue_farm")[1]
        assert erro and str(inexistente) not in erro and ":\\" not in erro, erro
        assert str(inexistente) not in nucleo_decks.html_page(con)
    print("a mensagem do site não leva o caminho da pasta")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
    print("TUDO OK")
