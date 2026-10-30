"""A página Coleção do núcleo (`colecoes.html`, `nucleo_colecoes.py`).

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários (`db.session(tmp/"v.db", tmp/"c.db")`), semeia o catálogo com o
`semear` de `test_nucleo_colecoes.py` (as três coleções fechadas e uma carta da
Reserved List) e escreve preços, posse e jogadas à mão.
"""
import html
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import nucleo_colecoes  # noqa: E402
import test_nucleo_colecoes as base  # noqa: E402
from mtgvault import db, paginas  # noqa: E402
from mtgvault.nucleo import colecoes, visual  # noqa: E402

HOJE = date.today().isoformat()
SLUGS = ["duals_revised", "expeditions", "shocks_pt", "reserved_list"]

US = base._sid("Underground Sea", "3ed")
SV = base._sid("Steam Vents", "gpt")
TARN = base._sid("Scalding Tarn", "exp")


def ha(dias: int) -> str:
    return (date.today() - timedelta(days=dias)).isoformat()


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def pronta():
    return base._pronta()


def vigiado(con, sid, acab, dia, preco):
    con.execute("INSERT OR REPLACE INTO n_preco_vigiado (scryfall_id, acabamento,"
                " dia, preco_eur) VALUES (?,?,?,?)", (sid, acab, dia, preco))
    con.commit()


def preco_pt(con, sid, dia, preco, acab="nonfoil"):
    con.execute("INSERT OR REPLACE INTO n_preco_pt (scryfall_id, acabamento, dia,"
                " preco_eur, ofertas) VALUES (?,?,?,?,1)", (sid, acab, dia, preco))
    con.commit()


def seccao(pagina, slug):
    m = re.search(rf'<section class="dk" id="{slug}"[^>]*>(.*?)</section>',
                  pagina, re.S)
    assert m, f"não há <section id={slug!r}>"
    return m.group(1)


def figura(trecho, nome):
    """A classe da `<figure>` da carta e o bloco de informação a seguir."""
    m = re.search(rf'<figure class="([^"]*)" title="{re.escape(html.escape(nome))}"'
                  r'.*?</figure>(.*?)(?=<div class="cc"|</div></section>|$)',
                  trecho, re.S)
    assert m, f"não há carta {nome!r}"
    return m.group(1).split(), m.group(2)


def texto(trecho):
    return html.unescape(re.sub(r"<[^>]+>", " ", trecho))


# ---------------------------------------------------------------------------
def caso_mosaicos():
    """Sem `#`: um botão por coleção (as quatro) e o de «A subir», cada um com
    o `href` do slug; a arte da coleção é a carta dela."""
    with pronta() as con:
        p = nucleo_colecoes.html_page(con)
        todos = p[p.index('<div id="todos">'):p.index('<section class="dk"')]
        for slug in SLUGS + ["subir"]:
            assert f'href="#{slug}"' in todos, slug
        assert len(re.findall(r'<a class="tile"', todos)) == 5
        assert re.findall(r'<span class="tn">([^<]*)', todos) == [
            "Duals de Revised", "Zendikar Expeditions",
            "Shocks originais em português", "Reserved List", "A subir"]
        # fechadas: «tenho X de Y»; aberta: «N cartas»
        assert "tenho 0 de 40" in texto(todos)
        assert "0 cartas" in texto(todos)
        # a arte é a da carta da coleção (3ed, exp, gpt), não de outra edição
        assert "art_crop/front/3/e/3ed-underground-sea.jpg" in todos
        assert "art_crop/front/e/x/exp-scalding-tarn.jpg" in todos
        assert "art_crop/front/g/p/gpt-steam-vents.jpg" in todos
        # uma secção por coleção e a de «A subir»
        ids = re.findall(r'<section class="dk" id="([a-z_]+)"', p)
        assert ids == SLUGS + ["subir"], ids


def caso_mosaico_valor_e_variacao():
    """O mosaico e o cabeçalho dizem o valor de hoje e a variação a 30 e a 90
    dias da série da coleção (a de há N dias é o último ponto até esse dia);
    sem ponto até lá, «sem histórico». Um preço de há 95 dias dá a de 90."""
    with pronta() as con:
        us = base._carta(con, "duals_revised", "Underground Sea")
        base._marcar(con, us["id"], 1)
        vigiado(con, US, "nonfoil", ha(95), 50.0)
        vigiado(con, US, "nonfoil", ha(35), 100.0)
        base._preco(con, US, "nonfoil", 110.0)
        p = nucleo_colecoes.html_page(con)
        todos = p[p.index('<div id="todos">'):p.index('<section class="dk"')]
        t = re.search(r'<a class="tile" href="#duals_revised">.*?</a>', todos,
                      re.S).group(0)
        assert paginas.eur(110.0) in texto(t), texto(t)
        assert "+10,0 % 30 d" in texto(t) and "+120,0 % 90 d" in texto(t), texto(t)
        # o mesmo no cabeçalho da coleção
        cab = seccao(p, "duals_revised").split('<div class="graf">')[0]
        assert "+10,0 % 30 d" in texto(cab) and "+120,0 % 90 d" in texto(cab), texto(cab)
        # as outras não têm série
        o = re.search(r'<a class="tile" href="#expeditions">.*?</a>', todos,
                      re.S).group(0)
        assert "sem histórico" in texto(o), texto(o)
        # só um ponto até há 30 dias: a de 30 dias existe, a de 90 diz-se
        with pronta() as con2:
            c2 = base._carta(con2, "duals_revised", "Underground Sea")
            base._marcar(con2, c2["id"], 1)
            vigiado(con2, US, "nonfoil", ha(35), 100.0)
            base._preco(con2, US, "nonfoil", 110.0)
            p2 = nucleo_colecoes.html_page(con2)
            t2 = re.search(r'<a class="tile" href="#duals_revised">.*?</a>',
                           p2, re.S).group(0)
            assert "+10,0 % 30 d" in texto(t2), texto(t2)
            assert "sem histórico 90 d" in texto(t2), texto(t2)


def caso_colecao_fechada():
    """«2 de 40 cartas», o progresso e o que falta em euros; a que falta fica
    a cinzento (e a que só tem algumas, a cinzento mais claro); «tenho /
    meta» no canto; «quero vender» só na carta marcada."""
    with pronta() as con:
        us = base._carta(con, "duals_revised", "Underground Sea")
        base._marcar(con, us["id"], 2)
        base._preco(con, US, "nonfoil", 100.0)
        colecoes.marcar_vender(con, us["id"], True)
        p = nucleo_colecoes.html_page(con)
        s = seccao(p, "duals_revised")
        assert "2 de 40 cartas" in texto(s), texto(s)[:400]
        assert "5 %" in texto(s)
        assert 'class="pbar"' in s
        # falta: 2 × 100 € das que tem em meta + as 9 sem preço ficam de fora
        assert "falta" in texto(s) and paginas.eur(200.0) in texto(s)
        assert "9 sem preço" in texto(s), texto(s)
        # o valor (200 €) não se queixa das 9 que ele nem tem
        assert "tua" not in texto(s).split("Cartas")[0], texto(s)
        sem = base._carta(con, "duals_revised", "Bayou")["id"]
        base._marcar(con, sem, 1)                      # tem, e não tem preço
        t2 = texto(seccao(nucleo_colecoes.html_page(con), "duals_revised"))
        assert "1 carta tua sem preço, fora da conta" in t2, t2
        base._marcar(con, sem, -1)
        cls_us, info_us = figura(s, "Underground Sea")
        assert "falta" in cls_us and "parcial" in cls_us, cls_us
        cls_ba, info_ba = figura(s, "Bayou")
        assert "falta" in cls_ba and "parcial" not in cls_ba, cls_ba
        assert '<u class="q">2 / 4</u>' in s and '<u class="q">0 / 4</u>' in s
        assert paginas.eur(100.0) in texto(info_us)
        assert "sem preço" in texto(info_ba)
        # «quero vender» só onde ele marcou
        assert s.count("quero vender") == 1, s.count("quero vender")
        assert "quero vender" in info_us and "quero vender" not in info_ba
        # tudo o que tem passa a cores
        base._marcar(con, us["id"], 2)
        s = seccao(nucleo_colecoes.html_page(con), "duals_revised")
        cls_us, _ = figura(s, "Underground Sea")
        assert "falta" not in cls_us, cls_us


def caso_joga_e_variacao_da_carta():
    """A carta mostra onde se joga (as etiquetas) e a variação a 30 e 90 dias;
    sem histórico di-lo."""
    with pronta() as con:
        con.execute("INSERT INTO n_jogada (formato, mes, nome, listas)"
                    " VALUES ('legacy', ?, 'Underground Sea', 7)", (HOJE[:7],))
        vigiado(con, US, "nonfoil", ha(100), 50.0)
        vigiado(con, US, "nonfoil", ha(40), 80.0)
        vigiado(con, US, "nonfoil", ha(2), 100.0)
        s = seccao(nucleo_colecoes.html_page(con), "duals_revised")
        _, info = figura(s, "Underground Sea")
        t = texto(info)
        assert "Legacy" in info and 'class="jg"' in info, info
        assert "+25,0 % 30 d" in t and "+100,0 % 90 d" in t, t
        _, info2 = figura(s, "Bayou")
        assert "sem histórico" in texto(info2), texto(info2)
        assert 'class="jg"' not in info2


def caso_pt_visto_ha():
    """Shock PT com preço de há 5 dias: o preço PT e «visto há 5 dias»; nunca
    o preço inglês (que existe na base); sem nenhum, «sem preço»."""
    with pronta() as con:
        preco_pt(con, SV, ha(5), 10.15)
        base._preco(con, SV, "nonfoil", 99.0)       # o inglês: nunca se usa
        s = seccao(nucleo_colecoes.html_page(con), "shocks_pt")
        _, info = figura(s, "Steam Vents")
        t = texto(info)
        assert paginas.eur(10.15) in t and "visto há 5 dias" in t, t
        assert "99,00" not in s
        _, nada = figura(s, "Blood Crypt")
        assert "sem preço" in texto(nada) and "visto há" not in texto(nada)
        # um dia só e hoje
        preco_pt(con, base._sid("Blood Crypt", "dis"), ha(1), 8.0)
        preco_pt(con, base._sid("Breeding Pool", "dis"), HOJE, 9.0)
        s = seccao(nucleo_colecoes.html_page(con), "shocks_pt")
        assert "visto há 1 dia" in texto(figura(s, "Blood Crypt")[1])
        assert "visto hoje" in texto(figura(s, "Breeding Pool")[1])
        # as inglesas não têm «visto há»
        assert "visto há" not in seccao(nucleo_colecoes.html_page(con),
                                        "duals_revised")


def caso_subir():
    """A Reserved List a subir (preço ≥ 20 €) aparece com a variação a 30 dias,
    a de 90 ao lado, se ele a tem e onde joga; abaixo de 20 € não aparece."""
    with pronta() as con:
        vigiado(con, base.RL_SID, "nonfoil", ha(95), 20.0)
        vigiado(con, base.RL_SID, "nonfoil", ha(35), 25.0)
        vigiado(con, base.RL_SID, "nonfoil", ha(1), 40.0)
        vigiado(con, US, "nonfoil", ha(1), 5.0)              # barata: fora
        cid = colecoes.juntar(con, "reserved_list", base.RL_SID, "nonfoil")
        base._marcar(con, cid, 2)
        con.execute("INSERT INTO n_jogada (formato, mes, nome, listas)"
                    " VALUES ('modern', ?, 'Moat', 3)", (HOJE[:7],))
        con.commit()
        p = nucleo_colecoes.html_page(con)
        s = seccao(p, "subir")
        t = texto(s)
        assert "Moat" in s and paginas.eur(40.0) in t, t
        assert "+60,0 %" in t, t                              # 40 / 25 em 30 d
        assert "+100,0 %" in t, t                             # 40 / 20 em 90 d
        assert "tens 2" in t and "Modern" in s, t
        assert "Underground Sea" not in s
        # o mosaico de «A subir» diz quantas e a maior subida
        todos = p[p.index('<div id="todos">'):p.index('<section class="dk"')]
        tile = re.search(r'<a class="tile" href="#subir">.*?</a>', todos, re.S).group(0)
        assert "1 carta" in texto(tile) and "+60,0 %" in texto(tile), texto(tile)


def caso_subir_vazio():
    with pronta() as con:
        s = seccao(nucleo_colecoes.html_page(con), "subir")
        assert "Nenhuma carta" in texto(s), texto(s)
        assert "<table" not in s


def caso_aberta_sem_meta():
    """A aberta diz «N cartas», não tem barra nem «de Y» nem «falta», e o canto
    da carta é só a quantidade."""
    with pronta() as con:
        cid = colecoes.juntar(con, "reserved_list", base.RL_SID, "nonfoil")
        base._marcar(con, cid, 2)
        base._preco(con, base.RL_SID, "nonfoil", 30.0)
        s = seccao(nucleo_colecoes.html_page(con), "reserved_list")
        t = texto(s)
        assert "2 cartas" in t, t
        assert not re.search(r"\d+ de \d+", t), t
        assert 'class="pbar"' not in s and "falta" not in t
        assert '<u class="q">2</u>' in s and "/ " not in re.search(
            r'<u class="q">[^<]*</u>', s).group(0)
        cls, info = figura(s, "Moat")
        assert "falta" not in cls
        assert paginas.eur(60.0) in t                         # o valor: 2 × 30
        # vazia: diz-o
        with pronta() as con2:
            s2 = seccao(nucleo_colecoes.html_page(con2), "reserved_list")
            assert "0 cartas" in texto(s2)


def caso_validadas_no_progresso():
    """«N de M cartas · V validadas» e V nunca passa de N."""
    with pronta() as con:
        pl = base._carta(con, "duals_revised", "Plateau")
        base._marcar(con, pl["id"], 6)
        fid = con.execute(
            "INSERT INTO n_foto (caminho, dia, sessao, linha, indice)"
            " VALUES ('x', ?, 's', 1, 0)", (HOJE,)).lastrowid
        rid = con.execute(
            "INSERT INTO n_recorte (foto_id, numero, caminho) VALUES (?, 1, ?)",
            (fid, f"assets/cartas/{fid}-1.jpg")).lastrowid
        con.commit()
        from mtgvault.nucleo import fotos
        fotos.validar(con, rid, "duals_revised", pl["scryfall_id"], "nonfoil",
                      qtd=6)
        s = seccao(nucleo_colecoes.html_page(con), "duals_revised")
        assert "4 de 40 cartas" in texto(s) and "4 validadas" in texto(s), texto(s)
        # o recorte dele em vez da imagem oficial, com a oficial à mão
        assert f"assets/cartas/{fid}-1.jpg" in s and "data-oficial=" in s


def caso_casca():
    """O título da página, o `<h1>`, o router por `#` e a ausência do token."""
    with pronta() as con:
        p = nucleo_colecoes.html_page(con, editable=True, token="segredo-123")
        assert '<h1 class="pgt">Coleção</h1>' in p
        assert "<title>Coleção · mtgvault</title>" in p
        assert 'lang="pt-PT"' in p
        assert "segredo-123" not in p
        assert 'data-editavel="1"' in p
        assert "nuc:atualizada" in p and "hashchange" in p
        assert nucleo_colecoes.FICHEIRO == "colecoes.html"
        # sem edição: nada do modo de edição
        q = nucleo_colecoes.html_page(con)
        assert "data-editavel" not in q


def caso_so_leitura():
    """A página gera-se a partir de uma ligação SÓ DE LEITURA (a do `publicar`):
    não levanta, não cria nada, e mostra as coleções que já existiam."""
    tmp = Path(tempfile.mkdtemp())
    with db.session(tmp / "v.db", tmp / "c.db") as con:
        base.semear(con)
        colecoes.garantir_colecoes(con)
        us = base._carta(con, "duals_revised", "Underground Sea")
        base._marcar(con, us["id"], 2)
        con.commit()
    with db.ler(tmp / "v.db", tmp / "c.db") as ro:
        p = nucleo_colecoes.html_page(ro)
        assert 'href="#duals_revised"' in p and "tenho 2 de 40" in texto(p)
        assert [r[0] for r in ro.execute(
            "SELECT slug FROM n_colecao ORDER BY ordem")] == SLUGS


def caso_nao_cria_as_colecoes():
    """Com o catálogo semeado mas sem as coleções criadas, a página não as cria:
    diz que ainda não foram preparadas (sem «0 de 40»); o mesmo se faltarem as
    tabelas."""
    with sessao() as con:
        base.semear(con)
        p = nucleo_colecoes.html_page(con)
        assert "As coleções ainda não foram preparadas." in p
        assert 'class="tile"' not in p and "de 40" not in p
        assert '<h1 class="pgt">Coleção</h1>' in p
        assert con.execute("SELECT COUNT(*) FROM n_colecao").fetchone()[0] == 0
        con.execute("PRAGMA foreign_keys = OFF")
        for t in ("n_colecao_carta", "n_colecao"):
            con.execute(f"DROP TABLE {t}")
        assert "As coleções ainda não foram preparadas." in             nucleo_colecoes.html_page(con)


def caso_build():
    with pronta() as con:
        d = Path(tempfile.mkdtemp())
        out = nucleo_colecoes.build(con, d / "colecoes.html")
        assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
