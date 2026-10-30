"""As fotos do núcleo (spec «Fotos»): tirar as imagens do registo da sessão,
recortar as cartas, validar as cópias contra os recortes e desfazer as
validadas que deixam de caber na posse.

Nada aqui abre a base do André nem o `~/.claude/projects` a sério: cada caso
constrói a sua base temporária (`db.session(tmp/"v.db", tmp/"c.db")`), um
`.jsonl` falso numa pasta temporária e imagens sintéticas feitas com o numpy e
o OpenCV em memória.
"""
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import db  # noqa: E402
from mtgvault.nucleo import colecoes, fotos, listas, modelo, posse  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

REP = "premodern_replenish"     # um deck sempre montado
COL = "teste_aberta"            # uma coleção aberta só destes testes


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def _tmp() -> Path:
    return Path(tempfile.mkdtemp())


def _levanta(chamar) -> str:
    try:
        chamar()
    except ValueError as e:
        return str(e)
    raise AssertionError("devia levantar ValueError")


# ---------------------------------------------------------------------------
# Imagens e registos falsos
# ---------------------------------------------------------------------------
def _png(cor=(0, 0, 255), lado=20) -> bytes:
    img = np.zeros((lado, lado, 3), np.uint8)
    img[:] = cor
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _item_imagem(dados: bytes, media_type="image/png") -> dict:
    return {"type": "image", "source": {
        "type": "base64", "media_type": media_type,
        "data": base64.b64encode(dados).decode("ascii")}}


def _jsonl(pasta: Path, linhas: list, nome="sessao-teste.jsonl") -> Path:
    p = pasta / nome
    with open(p, "w", encoding="utf-8") as f:
        for l in linhas:
            f.write(l if isinstance(l, str) else json.dumps(l))
            f.write("\n")
    return p


def _registo(pasta: Path) -> Path:
    """Linha 0: texto do utilizador; linha 1: utilizador com 2 imagens; linha 2:
    uma do assistente com uma imagem; linha 3: um `tool_result` com uma captura
    de ecrã (não conta); linha 4: lixo que não se lê."""
    a, b, c, d = _png((0, 0, 255)), _png((0, 255, 0)), _png((255, 0, 0)), _png()
    return _jsonl(pasta, [
        {"type": "user", "timestamp": "2026-10-30T10:00:00Z",
         "message": {"role": "user", "content": "olá"}},
        {"type": "user", "timestamp": "2026-10-30T10:01:00Z",
         "message": {"role": "user", "content": [
             {"type": "text", "text": "as cartas"},
             _item_imagem(a), _item_imagem(b, "image/jpeg")]}},
        {"type": "assistant", "timestamp": "2026-10-30T10:02:00Z",
         "message": {"role": "assistant", "content": [_item_imagem(c)]}},
        {"type": "user", "timestamp": "2026-10-30T10:03:00Z",
         "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "x",
              "content": [_item_imagem(d)]}]}},
        '{"type": "user", "message": {',
    ])


# ---------------------------------------------------------------------------
# Catálogo, deck e coleção
# ---------------------------------------------------------------------------
# (scryfall_id, nome, set, finishes, trend nonfoil)
IMPRESSOES = [
    ("tm-a", "Thought Monitor", "mh2", ["nonfoil", "foil"], 0.5),
    ("tm-b", "Thought Monitor", "pmh2", ["nonfoil", "foil"], 2.0),
    ("moat", "Moat", "leg", ["nonfoil"], 900.0),
]


def semear(con):
    for i, (sid, nome, sc, fins, trend) in enumerate(IMPRESSOES):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital,
               set_type)
               VALUES (?,?,?,?,'Test Set',?,'en','rare','Artifact',0,'',?,
               '2021-06-18',?,0,'expansion')""",
            (sid, "or-" + nome, nome, sc, str(i), json.dumps(fins), 1000 + i))
        con.execute(
            "INSERT INTO price_latest (scryfall_id, source, finish, date, low,"
            " trend) VALUES (?, 'cardmarket', 'nonfoil', '2026-10-28', ?, ?)",
            (sid, trend, trend))
    con.execute("INSERT INTO n_colecao (slug, nome, tipo, arte_nome, ordem)"
                " VALUES (?, 'Teste', 'aberta', NULL, 9)", (COL,))
    con.commit()
    modelo.garantir_decks(con)
    listas.gravar_versao(con, REP, [Linha("main", "Thought Monitor", 4)],
                         fonte="teste", origem="andre")


_n = [0]


def _req() -> str:
    _n[0] += 1
    return f"r{_n[0]}"


def _marcar_deck(con, delta):
    return posse.ajustar(con, REP, "Thought Monitor", delta, request_id=_req())


def _recorte(con, nome="x") -> int:
    """Uma foto e um recorte à mão (sem imagem): a validação só precisa do id."""
    _n[0] += 1
    fid = con.execute(
        "INSERT INTO n_foto (caminho, dia, sessao, linha, indice)"
        " VALUES (?, '2026-10-30', 's', ?, 0)",
        (f"data/fotos/originais/{nome}.png", _n[0])).lastrowid
    rid = con.execute(
        "INSERT INTO n_recorte (foto_id, numero, caminho) VALUES (?, 1, ?)",
        (fid, f"assets/cartas/{fid}-1.jpg")).lastrowid
    con.commit()
    return rid


def _caminho_recorte(con, rid) -> str:
    return con.execute("SELECT caminho FROM n_recorte WHERE id = ?",
                       (rid,)).fetchone()[0]


# ---------------------------------------------------------------------------
# Extrair
# ---------------------------------------------------------------------------
def caso_imagens_da_sessao():
    """Só as imagens de topo das mensagens `user` (nem as do assistente nem as
    capturas dentro de um `tool_result`); a linha partida salta-se."""
    jsonl = _registo(_tmp())
    imgs = fotos.imagens_da_sessao(jsonl)
    assert [(i["linha"], i["indice"]) for i in imgs] == [(1, 1), (1, 2)], imgs
    assert [i["media_type"] for i in imgs] == ["image/png", "image/jpeg"]
    assert imgs[0]["dados"] == _png((0, 0, 255))
    assert imgs[0]["quando"] == "2026-10-30T10:01:00Z"


def caso_sessao_mais_recente():
    """O `.jsonl` mexido mais recentemente, em qualquer projeto."""
    raiz = _tmp()
    (raiz / "p1").mkdir()
    (raiz / "p2").mkdir()
    velho = _jsonl(raiz / "p1", ["{}"], "a.jsonl")
    novo = _jsonl(raiz / "p2", ["{}"], "b.jsonl")
    os.utime(velho, (1_000_000, 1_000_000))
    os.utime(novo, (2_000_000, 2_000_000))
    assert fotos.sessao_mais_recente(raiz) == novo
    _levanta(lambda: fotos.sessao_mais_recente(_tmp()))


def caso_sessao_mais_recente_salta_o_observador():
    """(R24) As pastas de projeto com «observer» no nome são os registos do
    observador do claude-mem, que escreve a toda a hora e quase sempre tem o
    `.jsonl` mais recente: nunca são a sessão dele."""
    raiz = _tmp()
    (raiz / "C--Users-Catarina-Desktop-Claude").mkdir()
    (raiz / "C--Users-Catarina--claude-mem-observer-sessions").mkdir()
    dele = _jsonl(raiz / "C--Users-Catarina-Desktop-Claude", ["{}"], "a.jsonl")
    obs = _jsonl(raiz / "C--Users-Catarina--claude-mem-observer-sessions", ["{}"],
                 "b.jsonl")
    os.utime(dele, (1_000_000, 1_000_000))
    os.utime(obs, (2_000_000, 2_000_000))
    assert fotos.sessao_mais_recente(raiz) == dele
    # só registos do observador = não há sessão
    raiz2 = _tmp()
    (raiz2 / "x-observer").mkdir()
    _jsonl(raiz2 / "x-observer", ["{}"], "c.jsonl")
    _levanta(lambda: fotos.sessao_mais_recente(raiz2))


def caso_extrair_idempotente():
    """Extrair as mesmas imagens duas vezes não cria duas fotos; os originais
    ficam tal e qual chegaram, em `data/fotos/originais/AAAA-MM-DD/`."""
    jsonl = _registo(_tmp())
    raiz = _tmp()
    with sessao() as con:
        novas = fotos.extrair(con, jsonl, raiz, ultimas=2, para=REP)
        assert len(novas) == 2, novas
        assert fotos.extrair(con, jsonl, raiz, ultimas=2, para=REP) == []
        linhas = con.execute("SELECT id, caminho, sessao, linha, indice, para"
                             " FROM n_foto ORDER BY id").fetchall()
        assert len(linhas) == 2
        assert [(l["sessao"], l["linha"], l["indice"], l["para"]) for l in linhas] \
            == [("sessao-teste", 1, 1, REP), ("sessao-teste", 1, 2, REP)]
        for n, l in zip(novas, linhas):
            assert n == {"foto_id": l["id"], "caminho": l["caminho"]}
            assert l["caminho"].startswith(fotos.PASTA_ORIGINAIS + "/"), l["caminho"]
            assert "\\" not in l["caminho"]
        assert linhas[0]["caminho"].endswith(f"/{linhas[0]['id']}.png")
        assert linhas[1]["caminho"].endswith(f"/{linhas[1]['id']}.jpg")
        assert (raiz / linhas[0]["caminho"]).read_bytes() == _png((0, 0, 255))
        assert (raiz / linhas[1]["caminho"]).read_bytes() == _png((0, 255, 0))


def caso_extrair_so_as_ultimas():
    """`ultimas=1` tira só a última; a seguir, `ultimas=2` só traz a que falta."""
    jsonl = _registo(_tmp())
    raiz = _tmp()
    with sessao() as con:
        a = fotos.extrair(con, jsonl, raiz)
        assert len(a) == 1
        assert con.execute("SELECT indice FROM n_foto").fetchone()[0] == 2
        b = fotos.extrair(con, jsonl, raiz, ultimas=2)
        assert len(b) == 1 and b[0]["foto_id"] != a[0]["foto_id"]


# ---------------------------------------------------------------------------
# Recortar
# ---------------------------------------------------------------------------
CORES = [(90, 200, 240), (240, 200, 90), (120, 240, 120)]   # BGR, uma por carta


def _foto_sintetica(cartas=True) -> np.ndarray:
    """1600×1200, fundo escuro; três cartas claras 300×420 em duas filas: em
    cima à esquerda (rodada 5°) e à direita, em baixo ao meio. As cores dizem
    qual é qual."""
    img = np.full((1200, 1600, 3), 30, np.uint8)
    if not cartas:
        return img
    for (cx, cy), ang, cor in zip([(450, 320), (1150, 300), (800, 870)],
                                  [5, 0, 0], CORES):
        caixa = cv2.boxPoints(((cx, cy), (300, 420), ang)).astype(np.int32)
        cv2.fillPoly(img, [caixa], cor)
    return img


def _foto_na_base(con, raiz: Path, img: np.ndarray) -> int:
    rel = "data/fotos/originais/2026-10-30/sint.png"
    (raiz / rel).parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".png", img)[1].tofile(str(raiz / rel))
    fid = con.execute("INSERT INTO n_foto (caminho, dia, sessao, linha, indice)"
                      " VALUES (?, '2026-10-30', 'sint', 0, 0)", (rel,)).lastrowid
    con.commit()
    return fid


def _ler(p: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)


def caso_recortar_sintetico():
    """Três cartas, cada uma num JPEG 488×680, pela ordem: a fila de cima por x,
    depois a de baixo. Repetir o recorte não duplica as linhas."""
    raiz = _tmp() / "Coleçao"      # um «ç» no caminho, como na pasta a sério
    with sessao() as con:
        fid = _foto_na_base(con, raiz, _foto_sintetica())
        r = fotos.recortar(con, fid, raiz)
        assert r["encontradas"] == 3, r
        assert [x["numero"] for x in r["recortes"]] == [1, 2, 3]
        for x, cor in zip(r["recortes"], CORES):
            assert x["caminho"] == f"{fotos.PASTA_RECORTES}/{fid}-{x['numero']}.jpg"
            img = _ler(raiz / x["caminho"])
            assert img.shape == (fotos.ALTURA, fotos.LARGURA, 3), img.shape
            meio = img[200:480, 100:388].reshape(-1, 3).mean(axis=0)
            assert np.abs(meio - np.array(cor)).max() < 25, (x, meio, cor)
        assert fotos.recortar(con, fid, raiz)["encontradas"] == 3
        assert con.execute("SELECT COUNT(*) FROM n_recorte WHERE foto_id = ?",
                           (fid,)).fetchone()[0] == 3


def caso_recortar_foto_validada_nao_se_refaz():
    """Uma foto com validações (ativas ou já desfeitas) não se volta a recortar:
    os recortes são a prova delas. Nada muda."""
    raiz = _tmp()
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 1)
        fid = _foto_na_base(con, raiz, _foto_sintetica())
        r = fotos.recortar(con, fid, raiz)
        fotos.validar(con, r["recortes"][0]["id"], REP, "tm-a", "nonfoil")
        antes = [tuple(x) for x in con.execute("SELECT * FROM n_recorte")]
        msg = _levanta(lambda: fotos.recortar(con, fid, raiz))
        assert "prova" in msg, msg
        _marcar_deck(con, -1)          # a validação fica desfeita
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 0
        _levanta(lambda: fotos.recortar(con, fid, raiz))
        assert [tuple(x) for x in con.execute("SELECT * FROM n_recorte")] == antes


def caso_recortar_sem_cartas_nao_apaga_os_de_antes():
    """Uma segunda passagem que não encontra cartas (a foto trocada por fundo
    liso) devolve 0 e deixa os recortes de antes, linhas e ficheiros."""
    raiz = _tmp()
    with sessao() as con:
        fid = _foto_na_base(con, raiz, _foto_sintetica())
        r = fotos.recortar(con, fid, raiz)
        assert r["encontradas"] == 3
        rel = con.execute("SELECT caminho FROM n_foto WHERE id = ?",
                          (fid,)).fetchone()[0]
        cv2.imencode(".png", _foto_sintetica(cartas=False))[1].tofile(
            str(raiz / rel))
        assert fotos.recortar(con, fid, raiz) == {"recortes": [], "encontradas": 0}
        assert con.execute("SELECT COUNT(*) FROM n_recorte WHERE foto_id = ?",
                           (fid,)).fetchone()[0] == 3
        for x in r["recortes"]:
            assert (raiz / x["caminho"]).exists(), x


def caso_recortar_falha_diz():
    """Uma foto sem cartas não dá recortes inventados."""
    raiz = _tmp()
    with sessao() as con:
        fid = _foto_na_base(con, raiz, _foto_sintetica(cartas=False))
        assert fotos.recortar(con, fid, raiz) == {"recortes": [], "encontradas": 0}
        assert con.execute("SELECT COUNT(*) FROM n_recorte").fetchone()[0] == 0
        _levanta(lambda: fotos.recortar(con, 99999, raiz))


# ---------------------------------------------------------------------------
# Validar
# ---------------------------------------------------------------------------
def caso_validar_nao_passa_posse():
    """Posse 2: validar 3 levanta «só tens 2»; validar 2 grava."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 2)
        rid = _recorte(con)
        msg = _levanta(lambda: fotos.validar(con, rid, REP, "tm-a", "nonfoil",
                                             qtd=3))
        assert "só tens 2" in msg, msg
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 0
        fotos.validar(con, rid, REP, "tm-a", "nonfoil", qtd=2)
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 2
        assert fotos.recorte_de(con, REP, "tm-a", "nonfoil") == \
            _caminho_recorte(con, rid)


def caso_validar_deck_outra_edicao():
    """A foto mostra outra edição (ou foil): não se troca nada sozinho, levanta
    com as duas edições para o Claude perguntar."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 2)
        rid = _recorte(con)
        msg = _levanta(lambda: fotos.validar(con, rid, REP, "tm-b", "nonfoil"))
        assert "tm-b" in msg and "tm-a" in msg, msg
        msg = _levanta(lambda: fotos.validar(con, rid, REP, "tm-a", "foil"))
        assert "foil" in msg, msg
        assert posse.edicao(con, REP, "Thought Monitor") == ("tm-a", "nonfoil")
        assert con.execute("SELECT COUNT(*) FROM n_validacao").fetchone()[0] == 0
        _levanta(lambda: fotos.validar(con, rid, "nao_existe", "tm-a", "nonfoil"))


def caso_validar_o_mesmo_recorte_duas_vezes():
    """Um recorte é uma carta: com a validação dele ativa, não se valida outra
    vez (era contar a mesma carta duas vezes)."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 3)
        rid = _recorte(con)
        fotos.validar(con, rid, REP, "tm-a", "nonfoil")
        _levanta(lambda: fotos.validar(con, rid, REP, "tm-a", "nonfoil"))
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 1


def caso_menos_um_desfaz_a_mais_recente():
    """2 validadas (A e B) com posse 2: o −1 desfaz a de B, que fica na tabela
    com `desfeita_em`; o recorte que aparece passa a ser o de A."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 2)
        a, b = _recorte(con, "a"), _recorte(con, "b")
        fotos.validar(con, a, REP, "tm-a", "nonfoil")
        fotos.validar(con, b, REP, "tm-a", "nonfoil")
        assert fotos.recorte_de(con, REP, "tm-a", "nonfoil") == _caminho_recorte(con, b)
        assert _marcar_deck(con, -1) == 1
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 1
        linhas = {r["recorte_id"]: r["desfeita_em"] for r in con.execute(
            "SELECT recorte_id, desfeita_em FROM n_validacao")}
        assert set(linhas) == {a, b}, "a linha de B continua na tabela"
        assert linhas[a] is None and linhas[b] is not None, linhas
        assert fotos.recorte_de(con, REP, "tm-a", "nonfoil") == _caminho_recorte(con, a)
        # até zero: a de A também se desfaz, e não há recorte
        _marcar_deck(con, -1)
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 0
        assert fotos.recorte_de(con, REP, "tm-a", "nonfoil") is None
        assert con.execute("SELECT COUNT(*) FROM n_validacao").fetchone()[0] == 2


def caso_menos_um_tira_primeiro_por_validar():
    """Posse 3 com 2 validadas: o −1 tira a que estava por validar."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 3)
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil")
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil")
        assert _marcar_deck(con, -1) == 2
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 2
        assert con.execute("SELECT COUNT(*) FROM n_validacao WHERE desfeita_em"
                           " IS NOT NULL").fetchone()[0] == 0


def caso_aparar_parte_uma_validacao_de_varias():
    """Uma validação de 3 cópias e a posse a descer para 2: desfaz-se só uma
    cópia (a linha parte-se), nunca as três."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 3)
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil", qtd=3)
        _marcar_deck(con, -1)
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 2
        assert [tuple(r) for r in con.execute(
            "SELECT qtd, desfeita_em IS NOT NULL FROM n_validacao ORDER BY id")] \
            == [(2, 0), (1, 1)]


def caso_trocar_edicao_desfaz_as_validadas():
    """`escolher_edicao` zera a posse da edição antiga (vai para `n_saida`): as
    validadas dela ficam desfeitas."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 2)
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil")
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil")
        posse.escolher_edicao(con, REP, "Thought Monitor", "tm-b", "nonfoil")
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 0
        assert con.execute("SELECT COUNT(*) FROM n_validacao WHERE desfeita_em"
                           " IS NOT NULL").fetchone()[0] == 2


MOD = "modern_affinity"          # dois rotativos: o que os dois jogam é
LEG = "legacy_welder_cam"        # partilhado (âmbito `rotativos`)


def _versao(con, slug, linhas):
    return listas.gravar_versao(con, slug, [Linha(*l) for l in linhas],
                                fonte="teste", origem="andre")


def _ativas_e_desfeitas(con):
    return [tuple(r) for r in con.execute(
        "SELECT COALESCE(SUM(qtd) FILTER (WHERE desfeita_em IS NULL), 0),"
        " COALESCE(SUM(qtd) FILTER (WHERE desfeita_em IS NOT NULL), 0)"
        " FROM n_validacao")][0]


def caso_lista_baixa_e_tira_apara_as_validadas():
    """Uma versão nova que baixa a quantidade apara as validadas à posse que
    fica (saída parcial); uma que tira a carta desfá-las todas — e as linhas
    ficam, com `desfeita_em`."""
    with sessao() as con:
        semear(con)
        _marcar_deck(con, 2)
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil")
        fotos.validar(con, _recorte(con), REP, "tm-a", "nonfoil")
        _versao(con, REP, [("main", "Thought Monitor", 1)])
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 1
        assert _ativas_e_desfeitas(con) == (1, 1)
        _versao(con, REP, [("main", "Moat", 1)])
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 0
        assert _ativas_e_desfeitas(con) == (0, 2), "as linhas ficam"


def caso_partilhada_leva_as_validadas():
    """Uma carta fixa que passa a partilhada (entra num segundo rotativo) leva
    as validadas com a posse para `rotativos`; o âmbito antigo fica a 0. Baixar
    depois o que os dois pedem apara-as no monte."""
    with sessao() as con:
        semear(con)
        _versao(con, MOD, [("main", "Thought Monitor", 2)])
        posse.ajustar(con, MOD, "Thought Monitor", 2, request_id=_req())
        fotos.validar(con, _recorte(con), MOD, "tm-a", "nonfoil")
        fotos.validar(con, _recorte(con), MOD, "tm-a", "nonfoil")
        _versao(con, LEG, [("main", "Thought Monitor", 2)])
        assert posse.ambito(con, MOD, "Thought Monitor") == posse.ROT
        assert fotos.validadas(con, posse.ROT, "tm-a", "nonfoil") == 2
        assert fotos.validadas(con, MOD, "tm-a", "nonfoil") == 0
        assert _ativas_e_desfeitas(con) == (2, 0), "mudaram, não se desfizeram"
        _versao(con, MOD, [("main", "Thought Monitor", 1)])
        _versao(con, LEG, [("main", "Thought Monitor", 1)])
        assert fotos.validadas(con, posse.ROT, "tm-a", "nonfoil") == 1
        # e de volta a fixa: o monte e as validadas vão para a caixa do dono
        _versao(con, LEG, [("main", "Moat", 1)])
        assert posse.ambito(con, MOD, "Thought Monitor") == MOD
        assert fotos.validadas(con, MOD, "tm-a", "nonfoil") == 1
        assert fotos.validadas(con, posse.ROT, "tm-a", "nonfoil") == 0


def caso_registar_por_foto_deck():
    """`registar=True` num deck: a posse sobe e a cópia entra já validada; o
    mesmo pedido outra vez não soma a posse."""
    with sessao() as con:
        semear(con)
        rid = _recorte(con)
        fotos.validar(con, rid, REP, "tm-a", "nonfoil", registar=True)
        est = posse.estado_deck(con, REP)
        assert next(c for c in est["cartas"]
                    if c["nome"] == "Thought Monitor")["tenho"] == 1
        assert fotos.validadas(con, REP, "tm-a", "nonfoil") == 1
        _levanta(lambda: fotos.validar(con, rid, REP, "tm-a", "nonfoil",
                                       registar=True))
        assert posse.ajustar(con, REP, "Thought Monitor", 0,
                             request_id=_req()) == 1


def caso_registar_por_foto_coleccao():
    """`registar=True` numa coleção: o `tenho` sobe e as validadas também. Sem
    registar, com `tenho` 0, levanta «só tens 0»; uma carta (ou uma língua) que
    não está na coleção levanta a dizê-lo."""
    with sessao() as con:
        semear(con)
        cid = colecoes.juntar(con, COL, "moat", "nonfoil")
        rid = _recorte(con)
        msg = _levanta(lambda: fotos.validar(con, rid, COL, "moat", "nonfoil"))
        assert "só tens 0" in msg, msg
        msg = _levanta(lambda: fotos.validar(con, rid, COL, "tm-a", "nonfoil"))
        assert "não está na coleção" in msg, msg
        fotos.validar(con, rid, COL, "moat", "nonfoil", registar=True)
        tenho = con.execute("SELECT tenho FROM n_colecao_carta WHERE id = ?",
                            (cid,)).fetchone()[0]
        assert tenho == 1
        assert fotos.validadas(con, COL, "moat", "nonfoil") == 1
        msg = _levanta(lambda: fotos.validar(con, _recorte(con), COL, "moat",
                                             "nonfoil", lingua="pt"))
        assert "não está na coleção" in msg, msg
        # e o −1 da coleção desfaz-a
        colecoes.ajustar(con, cid, -1, request_id=_req())
        assert fotos.validadas(con, COL, "moat", "nonfoil") == 0


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
