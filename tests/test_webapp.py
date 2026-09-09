"""Modo edição (webapp.py): os botões, sem servidor nenhum a correr.

O que aqui se tranca:

  1. **Tornar permanente / Deixar de ser permanente** escreve no
     `colecao_config.json` e a alocação muda logo a seguir — é a ordem do André
     (*"os decks que eu estiver quase a concluir, tenho que ter uma opção que os
     marque como permanentes para começarem a receber alocação de cartas"*);
  2. **Subir / Descer** mexe no `prioridade` DENTRO do grupo, e renumera o grupo
     em vez de trocar dois números — com números repetidos ou saltados no
     config, um swap simples não mexia em nada;
  3. o botão diz a verdade quando não pode fazer nada (primeiro/último do grupo,
     ou único) em vez de fingir que fez;
  4. **gravar o config não estraga o config**: o ficheiro a sério passa por uma
     ida e volta e sai igual, chave a chave. Um `json.dump` cru rebentava as
     catorze linhas do `loadout` em duzentas e apagava a forma com que ele o lê;
  5. **Sleevado e na caixa** grava a `copy_allocation` daquela caixa (e só
     daquela), e "tirar da caixa" apaga-a.

Não abre socket nenhum e não toca na rede.
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
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "caixas": [
        {"slot": "a", "nome": "A", "formato": "legacy", "fonte": "deck",
         "ref": "A", "balde": "Colecção", "estado": "permanente", "prioridade": 7},
        {"slot": "b", "nome": "B", "formato": "legacy", "fonte": "deck",
         "ref": "B", "balde": "Colecção", "estado": "permanente", "prioridade": 7},
        {"slot": "c", "nome": "C", "formato": "legacy", "fonte": "deck",
         "ref": "C", "balde": "Colecção", "estado": "candidata", "prioridade": 9},
    ],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import db, loadout, sources  # noqa: E402

import webapp  # noqa: E402

CATALOGO = [("Sol Ring", "c21", "2021-04-23", 0), ("Opt", "eld", "2019-10-04", 0)]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, rl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,'S',?,'en','rare','Artifact',1,'',?,?,?,0,?)""",
            (f"id-{i}", f"or-{i}", nm, sc, str(i), json.dumps(["nonfoil", "foil"]),
             rel, json.dumps({"legacy": "legal"}), rl))
    for nome in ("A", "B", "C"):
        con.execute("INSERT INTO decks (name, format) VALUES (?, 'legacy')", (nome,))
        did = con.execute("SELECT id FROM decks WHERE name = ?", (nome,)).fetchone()["id"]
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, 'Sol Ring', 1, 'main')", (did,))
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    sid = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id) VALUES ('id-0', 1, 'foil', 'en',
                   'player', ?)""", (sid,))
    con.commit()
    return con


def repor():
    CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


def quem_tem(con, cfg):
    rep = loadout.report(con, cfg["caixas"])
    return next(s["nome"] for s in rep["slots"] if s["tenho"])


# ---------------------------------------------------------------------------
def caso_tornar_permanente_muda_a_alocacao():
    repor()
    con = base()
    cfg = webapp.ler_config()
    assert quem_tem(con, cfg) == "A"      # A e B são permanentes, C é candidato
    # Tira-se a A e a B de permanentes: o candidato C passa a ser o primeiro.
    for slot in ("a", "b"):
        webapp.alternar_permanente(cfg, slot)
    webapp.alternar_permanente(cfg, "c")
    for s in cfg["caixas"]:
        s["prioridade"] = {"a": 3, "b": 2, "c": 1}[s["slot"]]
    assert quem_tem(con, cfg) == "C", quem_tem(con, cfg)
    print("tornar permanente muda quem fica com a carta")


def caso_subir_renumera_o_grupo():
    repor()
    con = base()
    cfg = webapp.ler_config()
    # A e B têm o MESMO `prioridade` (7) no config: um swap de números não
    # mexia em nada. A renumeração é que faz isto funcionar.
    msg = webapp.mover(con, cfg, "b", -1)
    prio = {s["slot"]: s["prioridade"] for s in cfg["caixas"]}
    assert prio["b"] < prio["a"], prio
    assert "subiu" in msg, msg
    assert quem_tem(con, cfg) == "B", quem_tem(con, cfg)
    print("subir renumera o grupo e a carta muda de caixa")


def caso_descer_e_os_limites():
    repor()
    con = base()
    cfg = webapp.ler_config()
    assert "já é o primeiro" in webapp.mover(con, cfg, "a", -1)
    assert "já é o último" in webapp.mover(con, cfg, "b", 1)
    # O candidato está sozinho no seu grupo (permanente=False).
    assert "único do grupo" in webapp.mover(con, cfg, "c", -1)
    assert webapp.mover(con, cfg, "nao-existe", 1) == "esse slot não existe"
    print("os limites do grupo dizem-se, em vez de fingir que mexeram")


def caso_subir_descer_bloqueado_na_ordem_automatica():
    """André, 2026-09-08: no Premodern *"a prioridade vem por ordem de % completo"*.

    Aí o `prioridade` do config já não decide nada, e o botão tem de o dizer.
    Escrever o número na mesma era o pior dos dois mundos: o ficheiro mudava, a
    ordem ficava igual, e o servidor respondia *"X subiu"* a uma caixa que não
    saiu do sítio.
    """
    repor()
    con = base()
    cfg = webapp.ler_config()
    for s in cfg["caixas"]:               # as três passam a ser de Premodern
        s["formato"] = "premodern"
    antes = json.dumps(cfg["caixas"], sort_keys=True)
    msg = webapp.mover(con, cfg, "b", -1)
    assert "ordem automática" in msg and "percentagem" in msg, msg
    assert "prioridade_por" in msg, msg      # diz-lhe COMO se muda
    assert json.dumps(cfg["caixas"], sort_keys=True) == antes, cfg["caixas"]
    print("subir/descer nao mexe num grupo de ordem automatica, e diz porque")


def caso_gravar_o_config_a_serio_nao_o_estraga():
    """O ficheiro real do André passa por uma ida e volta e sai igual."""
    original = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    destino = _TMP / "roundtrip.json"
    webapp.escrever_config(original, destino)
    volta = json.loads(destino.read_text(encoding="utf-8"))
    assert volta == original, "o config não sobreviveu à ida e volta"
    assert list(volta) == list(original), "a ordem das chaves mudou"
    texto = destino.read_text(encoding="utf-8")
    # As catorze caixas continuam a ser catorze linhas, não duzentas.
    assert texto.count('{ "slot"') + texto.count('{"slot"') == len(original["caixas"])
    print("gravar o colecao_config.json a serio nao lhe estraga a forma")


def caso_sleevado_e_na_caixa():
    repor()
    con = base()
    n = webapp.marcar_na_caixa(con, "a", True)
    assert n == 1, n
    linhas = con.execute("SELECT slot, quantity FROM copy_allocation").fetchall()
    assert [(r["slot"], r["quantity"]) for r in linhas] == [("a", 1)], linhas
    # A caixa passa a ser a morada da carta.
    rep = loadout.report(con, webapp.ler_config()["caixas"])
    assert next(s for s in rep["slots"] if s["slot"] == "a")["origens"] == {"A": 1}
    # E tirar da caixa desfaz — só daquela caixa.
    assert webapp.marcar_na_caixa(con, "b", False) == 0
    assert webapp.marcar_na_caixa(con, "a", False) == 1
    assert con.execute("SELECT COUNT(*) c FROM copy_allocation").fetchone()["c"] == 0
    print("sleevado e na caixa grava (e tira) so aquela caixa")


def caso_sugestao_de_premodern_abre_uma_caixa():
    """*"Vou montar este"* numa sugestão de Premodern CRIA a caixa.

    A diferença para o botão do top-N é essa: ali a caixa já existe e está vazia;
    aqui o que ele está a dizer é *"quero mais um deck de Premodern"*, e sem
    caixa o deck não entra na alocação — a sugestão ficava a ser papel.

    O nome da caixa é o do arquétipo e mais nada: é por ele que ela se reconhece
    como sendo aquela sugestão na corrida seguinte (`premodern._caixa_de`), e o
    *"Legacy — Doomsday"* do outro botão fazia a sugestão voltar a aparecer ao
    lado da caixa que ela própria criou.
    """
    repor()
    from mtgvault import premodern as pm
    cfg = webapp.ler_config()
    antes = len(cfg["caixas"])
    nova = webapp.caixa_para_sugestao(cfg, "Mono-Azul Stasis")
    assert len(cfg["caixas"]) == antes + 1
    assert nova["slot"] == pm.slug("Mono-Azul Stasis") == "premodern-mono-azul-stasis"
    assert nova["formato"] == "premodern" and nova["nome"] == "Mono-Azul Stasis"
    assert nova["balde"] == "Colecção", "sem irmãs de Premodern, a gaveta comum"
    # Idempotente: dois cliques (ou um duplo-toque no telemóvel) não dão duas caixas.
    assert webapp.caixa_para_sugestao(cfg, "Mono-Azul Stasis") is nova
    assert len(cfg["caixas"]) == antes + 1
    # E o nome sobrevive à ida e volta ao ficheiro, que é o que a corrida
    # seguinte lê para reconhecer a caixa.
    webapp.escrever_config(cfg, _TMP / "sug.json")
    lido = webapp.ler_config(_TMP / "sug.json")
    assert any(c["slot"] == nova["slot"] and c["nome"] == "Mono-Azul Stasis"
               for c in lido["caixas"])
    print("a sugestão abre uma caixa nova, com o nome do arquétipo, e sem duplicar")

    # E o «não quero este» escreve-se no config, com a data — pelo `id` estável
    # do arquétipo, com o nome ao lado. A chave era o nome, e o nome do
    # clustering muda entre corridas: a recusa deixava de bater e a sugestão
    # voltava sozinha (ver `test_arquetipos.py`).
    msg = pm.recusar(cfg, "Mono-Azul Stasis", "2026-09-08", ident="f0f1f2f3f4")
    assert cfg["premodern"]["sugestoes_recusadas"] == {
        "f0f1f2f3f4": {"nome": "Mono-Azul Stasis", "em": "2026-09-08"}}
    assert "venda" in msg, msg
    # E o «volta a considerar» desfaz pelo mesmo `id`, mesmo que o nome já tenha
    # mudado de rótulo entretanto — que é o caso para que isto existe.
    pm.aceitar(cfg, "Mono-Azul Polluted Delta", "f0f1f2f3f4")
    assert not cfg["premodern"].get("sugestoes_recusadas")
    print("o «não quero este» fica escrito pelo id, datado, e desfaz-se pelo id")


def caso_gravar_o_config_e_atomico():
    """O `write_text` normal TRUNCA o ficheiro antes de escrever: um erro a meio
    — ou dois pedidos ao mesmo tempo, que o `ThreadingHTTPServer` permite —
    deixava o `colecao_config.json` cortado, e com ele o loadout, as regras de
    material e as listas escolhidas. Escreve-se ao lado e troca-se de nome.

    Prova-se pelo caminho oposto: se a escrita falhar, o ficheiro antigo tem de
    continuar inteiro e não pode ficar lixo ao lado."""
    destino = _TMP / "atomico.json"
    webapp.escrever_config({"a": 1}, destino)
    original = destino.read_text(encoding="utf-8")

    class Explode(dict):
        def items(self):
            raise RuntimeError("a serializacao rebentou a meio")

    try:
        webapp.escrever_config(Explode(), destino)
    except RuntimeError:
        pass
    else:
        raise AssertionError("devia ter rebentado")
    assert destino.read_text(encoding="utf-8") == original, "o config foi truncado"
    assert not destino.with_name(destino.name + ".tmp").exists(), "ficou um .tmp"
    print("gravar o config e atomico: uma falha nao trunca o ficheiro")


def caso_escritas_em_paralelo_nao_se_atropelam():
    """Dois cliques ao mesmo tempo (ou um duplo-toque no telemóvel) eram dois
    ler-mexer-gravar em paralelo, e o segundo gravava por cima do primeiro. O
    `ESCRITA` serializa-os; aqui prova-se que o lock existe e que é reentrante
    do ponto de vista de quem o usa (um pedido de cada vez, nunca dois)."""
    import threading

    repor()
    destino = _TMP / "paralelo.json"
    webapp.escrever_config({"n": 0}, destino)
    dentro, maximo = [0], [0]

    def clique():
        with webapp.ESCRITA:
            dentro[0] += 1
            maximo[0] = max(maximo[0], dentro[0])
            cfg = json.loads(destino.read_text(encoding="utf-8"))
            cfg["n"] += 1
            webapp.escrever_config(cfg, destino)
            dentro[0] -= 1

    fios = [threading.Thread(target=clique) for _ in range(20)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    assert maximo[0] == 1, ("duas escritas ao mesmo tempo", maximo[0])
    assert json.loads(destino.read_text(encoding="utf-8"))["n"] == 20, "perdeu-se um clique"
    print("vinte cliques em paralelo: nenhum se perde e nunca ha dois a escrever")


def caso_ler_config_segue_o_ficheiro_que_o_motor_le():
    """O `CONFIG` estava congelado no import: se o `MTGVAULT_CONFIG` mudasse, o
    webapp escrevia num ficheiro e o `sources.config()` lia de outro — um botão
    que "não faz nada" sem erro nenhum."""
    antigo = os.environ["MTGVAULT_CONFIG"]
    outro = _TMP / "outro.json"
    outro.write_text(json.dumps({"caixas": []}), encoding="utf-8")
    os.environ["MTGVAULT_CONFIG"] = str(outro)
    try:
        assert webapp.config_path() == outro, webapp.config_path()
        assert webapp.ler_config() == {"caixas": []}
    finally:
        os.environ["MTGVAULT_CONFIG"] = antigo
    print("o webapp le e escreve o mesmo ficheiro que o motor le")


def caso_o_menu_leva_o_token_no_modo_edicao():
    """No telemóvel, um toque no menu não pode apagar o modo edição.

    Os links do `paginas.nav` são `href="metagame.html"` — sem query nenhuma —
    e o servidor só confia em quem traz o `?t=`. Ele ia à Coleção, voltava à
    Deckboxes e os botões tinham desaparecido, sem erro e sem explicação. No PC
    nunca se via: o loopback é de confiança sem token.

    E o **🏠 Início** tem de ir para o índice: estava mapeado para a Deckboxes,
    ou seja, levava-o à página onde ele já estava.
    """
    from mtgvault import paginas

    menu = paginas.nav("deckboxes.html", extra=True)
    com = webapp.com_token(menu, "abc123")
    assert 'href="metagame.html?t=abc123"' in com, com
    assert 'href="index.html?t=abc123"' in com, com
    assert 'href="colecao.html?t=abc123"' in com, com
    # Sem token (site publicado / leitura) a página não pode ganhar `?t=`.
    assert webapp.com_token(menu, "") == menu
    # E nada além dos links internos é tocado.
    fora = '<a href="https://github.com/Baverone/mtgvault">repo</a>'
    assert webapp.com_token(fora, "abc123") == fora

    assert "/index.html" not in webapp.PAGINAS_EDITAVEIS, \
        "o «Início» do menu voltava a dar a Deckboxes"
    assert "/" in webapp.PAGINAS_EDITAVEIS
    print("o menu do modo edicao leva o token, e o Inicio vai para o indice")


def run():
    for fn in (caso_tornar_permanente_muda_a_alocacao, caso_subir_renumera_o_grupo,
               caso_descer_e_os_limites,
               caso_subir_descer_bloqueado_na_ordem_automatica,
               caso_gravar_o_config_a_serio_nao_o_estraga,
               caso_sleevado_e_na_caixa,
               caso_sugestao_de_premodern_abre_uma_caixa,
               caso_gravar_o_config_e_atomico,
               caso_escritas_em_paralelo_nao_se_atropelam,
               caso_ler_config_segue_o_ficheiro_que_o_motor_le,
               caso_o_menu_leva_o_token_no_modo_edicao):
        fn()
    repor()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
