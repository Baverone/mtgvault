"""A CLI `nucleo` (spec «Fotos»: são estes comandos que o Claude corre durante a
conversa para extrair, recortar e validar as fotos dele).

Nada aqui abre a base do André nem o `~/.claude/projects` a sério: cada caso
constrói a sua base temporária, um `.jsonl` falso e uma imagem sintética, e
chama `cli.main([...])` com `--db`/`--catalog` (opções do nível de cima, antes
do subcomando) e `--raiz` numa pasta temporária.
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mtgvault import cli, db  # noqa: E402
from mtgvault.nucleo import colecoes, fotos  # noqa: E402

import test_nucleo_colecoes as tcol  # noqa: E402
import test_nucleo_fotos as tfot  # noqa: E402

REP, COL = tfot.REP, tfot.COL


def _base():
    """`(tmp, v, c)`: pasta temporária e os dois caminhos das bases."""
    tmp = Path(tempfile.mkdtemp())
    return tmp, tmp / "v.db", tmp / "c.db"


def _correr(v, c, *args):
    """`(código, texto)` de `cli.main` com a saída (e os erros) apanhados."""
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
        try:
            rc = cli.main(["--db", str(v), "--catalog", str(c), *map(str, args)])
        except SystemExit as e:          # o argparse sai assim
            rc = e.code
    return (rc or 0), saida.getvalue()


def _com_foto(tmp):
    """Um `.jsonl` com a foto sintética (três cartas) numa mensagem dele."""
    png = cv2.imencode(".png", tfot._foto_sintetica())[1].tobytes()
    return tfot._jsonl(tmp, [
        {"type": "user", "timestamp": "2026-10-30T10:00:00Z",
         "message": {"role": "user", "content": [
             {"type": "text", "text": "as cartas"}, tfot._item_imagem(png)]}}])


def _lote(tmp, linhas, nome="lote.json"):
    p = tmp / nome
    p.write_text(json.dumps(linhas), encoding="utf-8")
    return p


def _validacoes(v, c):
    with db.session(v, c) as con:
        return con.execute("SELECT COUNT(*) FROM n_validacao").fetchone()[0]


def caso_colecoes():
    """Garante as coleções e imprime uma linha por coleção: as fechadas com
    `tenho/total`, a aberta com o nº de cartas."""
    tmp, v, c = _base()
    with db.session(v, c) as con:
        tcol.semear(con)
    rc, out = _correr(v, c, "nucleo", "colecoes")
    assert rc == 0, out
    linhas = out.strip().splitlines()
    assert len(linhas) == len(colecoes.COLECOES), out
    por_slug = {l.split(" · ")[0]: l for l in linhas}
    for col in colecoes.COLECOES:
        assert col["slug"] in por_slug, out
    assert " · 0/" in por_slug["duals_revised"], por_slug["duals_revised"]
    assert "€" in por_slug["duals_revised"], por_slug["duals_revised"]
    assert " · 0 cartas · " in por_slug["reserved_list"], por_slug["reserved_list"]
    # e as coleções ficaram na base
    with db.session(v, c) as con:
        assert len(colecoes.colecoes(con)) == len(colecoes.COLECOES)


def caso_extrair_recortar_validar():
    """A cadeia toda pela CLI: extrair a última imagem da sessão (a `--raiz`
    recebe o original), recortar as três cartas, validar por lote (uma
    registada por foto) e ver as validadas."""
    tmp, v, c = _base()
    with db.session(v, c) as con:
        tfot.semear(con)
    jsonl = _com_foto(tmp)
    raiz = tmp / "raiz"

    rc, out = _correr(v, c, "nucleo", "extrair", "--sessao", jsonl,
                      "--raiz", raiz, "--para", REP)
    assert rc == 0, out
    assert "sessao-teste.jsonl" in out, "diz que sessão usou: " + out
    linhas = [l for l in out.splitlines() if l.startswith("foto ")]
    assert len(linhas) == 1, out
    foto_id = int(linhas[0].split(":")[0].split()[1])
    caminho = linhas[0].split(": ", 1)[1]
    assert (raiz / caminho).is_file(), caminho
    # repetir não cria outra foto
    rc, out2 = _correr(v, c, "nucleo", "extrair", "--sessao", jsonl,
                       "--raiz", raiz)
    assert rc == 0 and "foto 1:" not in out2 and "nenhuma foto nova" in out2, out2

    rc, out = _correr(v, c, "nucleo", "recortar", foto_id, "--raiz", raiz)
    assert rc == 0, out
    assert out.splitlines()[0].startswith("3 recortes"), out
    rec = [l for l in out.splitlines() if l.startswith("recorte ")]
    assert len(rec) == 3, out
    ids = [int(l.split()[1]) for l in rec]
    for l in rec:
        assert (raiz / l.split(": ", 1)[1]).is_file(), l

    lote = _lote(tmp, [
        {"recorte_id": ids[0], "ambito": REP, "scryfall_id": "tm-a",
         "acabamento": "nonfoil", "registar": True},
        {"recorte_id": ids[1], "ambito": COL, "scryfall_id": "moat",
         "acabamento": "nonfoil", "lingua": "en", "qtd": 1, "registar": True}])
    with db.session(v, c) as con:
        colecoes.juntar(con, COL, "moat", "nonfoil")
    rc, out = _correr(v, c, "nucleo", "validar", "--lote", lote)
    assert rc == 0, out
    assert _validacoes(v, c) == 2

    rc, out = _correr(v, c, "nucleo", "validadas", REP)
    assert rc == 0, out
    assert "Thought Monitor" in out and "1 · 1" in out, out
    rc, out = _correr(v, c, "nucleo", "validadas", COL)
    assert rc == 0 and "Moat" in out and "1 · 1" in out, out
    rc, out = _correr(v, c, "nucleo", "validadas", "nao_existe")
    assert rc != 0 and "nao_existe" in out, out


def caso_lote_falha_nao_grava():
    """Uma linha 2 que viola «só tens N»: nada se grava (nem a linha 1, nem a
    posse que a linha 1 registaria) e o motivo diz «linha 2». Uma linha com a
    edição errada num deck também. Um ficheiro que não se lê não grava nada."""
    tmp, v, c = _base()
    with db.session(v, c) as con:
        tfot.semear(con)
        r1, r2 = tfot._recorte(con), tfot._recorte(con)
    lote = _lote(tmp, [
        {"recorte_id": r1, "ambito": REP, "scryfall_id": "tm-a",
         "acabamento": "nonfoil", "registar": True},
        # só tem 0 de Moat na coleção aberta (sem registar)
        {"recorte_id": r2, "ambito": COL, "scryfall_id": "moat",
         "acabamento": "nonfoil"}])
    with db.session(v, c) as con:
        colecoes.juntar(con, COL, "moat", "nonfoil")
    rc, out = _correr(v, c, "nucleo", "validar", "--lote", lote)
    assert rc != 0, out
    assert "linha 2" in out and "só tens 0" in out, out
    assert _validacoes(v, c) == 0
    with db.session(v, c) as con:
        assert con.execute("SELECT COUNT(*) FROM n_posse").fetchone()[0] == 0, \
            "a posse da linha 1 não devia ter sido registada"
        assert con.execute("SELECT COUNT(*) FROM n_posse_log").fetchone()[0] == 0

    # a mesma carta duas vezes na mesma carrada passa o «só tens» de cada linha
    # lida sozinha, mas não o das duas juntas
    lote = _lote(tmp, [
        {"recorte_id": r1, "ambito": REP, "scryfall_id": "tm-a",
         "acabamento": "nonfoil", "registar": True},
        {"recorte_id": r2, "ambito": REP, "scryfall_id": "tm-a",
         "acabamento": "nonfoil", "qtd": 5}], "lote2.json")
    rc, out = _correr(v, c, "nucleo", "validar", "--lote", lote)
    assert rc != 0 and "linha 2" in out, out
    assert _validacoes(v, c) == 0

    # edição que não conta num deck, recorte desconhecido, âmbito desconhecido
    for nome, linha, texto in [
            ("ed", {"recorte_id": r1, "ambito": REP, "scryfall_id": "tm-b",
                    "acabamento": "nonfoil"}, "conta na edição"),
            ("rc", {"recorte_id": 999, "ambito": REP, "scryfall_id": "tm-a",
                    "acabamento": "nonfoil"}, "recorte desconhecido"),
            ("am", {"recorte_id": r1, "ambito": "xpto", "scryfall_id": "tm-a",
                    "acabamento": "nonfoil"}, "nem deck nem coleção"),
            ("falta", {"recorte_id": r1, "ambito": REP}, "scryfall_id")]:
        rc, out = _correr(v, c, "nucleo", "validar", "--lote",
                          _lote(tmp, [linha], nome + ".json"))
        assert rc != 0 and "linha 1" in out and texto in out, (nome, out)
    rc, out = _correr(v, c, "nucleo", "validar", "--lote", tmp / "nao.json")
    assert rc != 0, out
    assert _validacoes(v, c) == 0


def caso_lote_falha_a_meio_diz_o_que_gravou():
    """Se algo que a verificação não vê falhar já na passagem de escrita, para,
    diz que linha falhou e quais ficaram gravadas, e sai com erro. Provoca-se
    trocando o `validar` por um que falha na linha 2."""
    tmp, v, c = _base()
    with db.session(v, c) as con:
        tfot.semear(con)
        r1, r2 = tfot._recorte(con), tfot._recorte(con)
    lote = _lote(tmp, [
        {"recorte_id": r1, "ambito": REP, "scryfall_id": "tm-a",
         "acabamento": "nonfoil", "registar": True},
        {"recorte_id": r2, "ambito": REP, "scryfall_id": "tm-a",
         "acabamento": "nonfoil", "registar": True}])
    original = fotos.validar
    chamadas = [0]

    def avariado(*a, **k):
        chamadas[0] += 1
        if chamadas[0] == 2:
            raise ValueError("avaria de teste")
        return original(*a, **k)
    fotos.validar = avariado
    try:
        rc, out = _correr(v, c, "nucleo", "validar", "--lote", lote)
    finally:
        fotos.validar = original
    assert rc != 0, out
    assert "linha 2" in out and "avaria de teste" in out, out
    assert "linha 1" in out and "gravada" in out, out
    assert _validacoes(v, c) == 1


def caso_argumentos():
    """Sem `--lote` o `validar` diz o que falta; o `recortar` sem id também; e
    um `recortar` de uma foto que não existe diz-lho sem traceback."""
    tmp, v, c = _base()
    with db.session(v, c) as con:
        tfot.semear(con)
    for args in [("validar",), ("recortar",), ("validadas",)]:
        rc, out = _correr(v, c, "nucleo", *args)
        assert rc != 0 and "Traceback" not in out, (args, out)
    rc, out = _correr(v, c, "nucleo", "recortar", 99, "--raiz", tmp)
    assert rc != 0 and "Traceback" not in out, out


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
