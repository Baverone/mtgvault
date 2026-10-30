"""As três páginas do núcleo: Painel (`index.html`), Decks (`deck.html`) e
Vender (`vender.html`).

Nada aqui abre a base do André: cada caso constrói a sua base e o seu catálogo
temporários (`db.session(vault_tmp, catalog_tmp)`), semeia o `catalog.cards` à
mão, grava versões com o `listas.gravar_versao`, preços com o
`prices.write_prices` e a posse com o `posse.ajustar`.

O cenário: um deck sempre montado (UW Replenish) e dois rotativos (Modern
Affinity e Welder Cam) que partilham a Urza's Saga e o Springleaf Drum; o Welder
Cam está montado.
"""
import html
import json
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nucleo_decks  # noqa: E402
import nucleo_painel  # noqa: E402
import nucleo_vender  # noqa: E402
from mtgvault import db, paginas, prices  # noqa: E402
from mtgvault.nucleo import listas, modelo, posse, valor, visual  # noqa: E402
from mtgvault.nucleo.listas import Linha  # noqa: E402

# (scryfall_id, nome, set, data, finishes)
IMPRESSOES = [
    ("repl-a", "Replenish", "ulg", "1999-02-15", ["nonfoil"]),
    ("repl-b", "Replenish", "uds", "1999-06-07", ["nonfoil"]),
    ("opal-a", "Opalescence", "usg", "1998-10-12", ["nonfoil"]),
    ("isl-a", "Island", "usg", "1998-10-12", ["nonfoil"]),
    ("tm-a", "Thought Monitor", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("saga-a", "Urza's Saga", "mh2", "2021-06-18", ["nonfoil", "foil"]),
    ("weld-a", "Goblin Welder", "ulg", "1999-02-15", ["nonfoil"]),
    ("drum-a", "Springleaf Drum", "lrw", "2007-10-12", ["nonfoil"]),
]

REP = "premodern_replenish"
MOD = "modern_affinity"
LEG = "legacy_welder_cam"
OATH = "premodern_oath"
AFF = "pauper_affinity"
CLOUD = "cedh_cloud"

DIA = "2026-10-28"
_n = [0]
# (R18) o Painel mede «hoje» pelo relógio: os casos do valor contam os dias
# para trás a partir de hoje
HOJE = date.today().isoformat()


def ha(dias: int) -> str:
    return (date.today() - timedelta(days=dias)).isoformat()


def ultimos_pontos(p: str) -> list[str]:
    """O valor do último ponto de cada período do gráfico (o «para X» do
    `aria-label` de cada SVG)."""
    return [html.unescape(x) for x in re.findall(r'aria-label="De [^"]* para ([^"]*)"', p)]


def topo(p: str) -> str:
    return html.unescape(re.search(r'<span class="vbig">(.*?)</span>', p).group(1))


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def semear(con):
    for i, (sid, nome, sc, data, fins) in enumerate(IMPRESSOES):
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, cardmarket_id, digital,
               set_type)
               VALUES (?,?,?,?,'Test Set',?,'en','rare','Artifact',0,'',?,?,?,?,
               'expansion')""",
            (sid, "or-" + nome, nome, sc, str(i), json.dumps(fins), data,
             1000 + i, 0))
    con.commit()
    modelo.garantir_decks(con)


def preco(con, sid, acab, trend, dia=DIA):
    prices.write_prices(con, [(sid, "cardmarket", dia, acab, trend, trend,
                               trend, None, "EUR")])


def versao(con, slug, linhas, fonte="teste", quando=None):
    return listas.gravar_versao(con, slug, [Linha(*l) for l in linhas],
                                fonte=fonte, origem="andre", quando=quando)


def marcar(con, slug, nome, delta):
    _n[0] += 1
    return posse.ajustar(con, slug, nome, delta, request_id=f"t{_n[0]}")


def cenario(con):
    semear(con)
    preco(con, "repl-a", "nonfoil", 10.0)
    preco(con, "repl-b", "nonfoil", 12.0)
    preco(con, "opal-a", "nonfoil", 5.0)
    preco(con, "tm-a", "nonfoil", 2.0)
    preco(con, "tm-a", "foil", 3.0)
    preco(con, "saga-a", "nonfoil", 30.0)
    preco(con, "saga-a", "foil", 50.0)
    preco(con, "drum-a", "nonfoil", 1.0)
    # o Goblin Welder e a Island ficam sem preço
    versao(con, REP, [("main", "Replenish", 4), ("main", "Opalescence", 2),
                      ("side", "Island", 3)], fonte="Premodern Discord",
           quando="2026-10-01T10:00:00")
    versao(con, MOD, [("main", "Thought Monitor", 4), ("main", "Urza's Saga", 4),
                      ("main", "Springleaf Drum", 4)], fonte="twitter @Kappa",
           quando="2026-10-14T10:00:00")
    versao(con, LEG, [("main", "Goblin Welder", 4), ("main", "Urza's Saga", 2),
                      ("main", "Springleaf Drum", 4)], fonte="mtgtop8",
           quando="2026-10-15T10:00:00")
    posse.definir_montado(con, LEG)
    marcar(con, REP, "Replenish", 4)        # completa
    marcar(con, REP, "Opalescence", 1)      # falta 1
    posse.escolher_edicao(con, MOD, "Thought Monitor", "tm-a", "foil")
    marcar(con, MOD, "Thought Monitor", 4)  # foil, completa
    marcar(con, LEG, "Urza's Saga", 4)      # o monte das partilhadas


def seccao(pagina, slug):
    m = re.search(rf'<section class="dk" id="{slug}"[^>]*>(.*?)</section>',
                  pagina, re.S)
    assert m, f"não há <section id={slug!r}>"
    return m.group(1)


def classes_da_carta(trecho, nome):
    m = re.search(rf'<figure class="([^"]*)" title="{re.escape(html.escape(nome))}"',
                  trecho)
    assert m, f"não há carta {nome!r}"
    return m.group(1).split()


# ---------------------------------------------------------------------------
def caso_painel_tem_valor_e_decks():
    with sessao() as con:
        cenario(con)
        v = valor.valor_em(con)
        # 4×10 Replenish + 1×5 Opalescence + 4×3 Thought Monitor foil + 4×30 Saga
        assert v["total_eur"] == 177.0, v
        p = nucleo_painel.html_page(con)
        assert paginas.eur(v["total_eur"]) in p
        assert len(re.findall(r'<a class="tile', p)) == 14
        # (29/10) por formato, na ordem que ele pediu: primeiro os rotativos
        # (partilham cartas) lado a lado, depois os sempre montados um formato
        # por linha; o Standard aparece mesmo sem deck
        assert "Sempre montados" in p and "Rotativos" in p
        assert p.index("Rotativos") < p.index("Sempre montados")
        fts = re.findall(r'<h3 class="ft">([^<]+)', p)
        assert fts == ["Standard", "Pioneer", "Modern", "Legacy", "Premodern",
                       "Pauper", "cEDH", "Duel Commander"], fts
        cols = p[p.index('<div class="fcols">'):p.index("Sempre montados")]
        assert cols.count('<div class="fcol">') == 4
        assert "sem deck" in cols
        assert cols.index("#pioneer_greasefang") < cols.index("#modern_affinity")             < cols.index("#modern_oswald") < cols.index("#legacy_welder_cam")
        sem = p[p.index("Sempre montados"):]
        assert sem.index("#premodern_stifflenough") < sem.index("#pauper_affinity")             < sem.index("#cedh_blue_farm") < sem.index("#dc_cloud")
        # a página dos decks segue a mesma ordem
        d = nucleo_decks.html_page(con)
        ids = re.findall(r'<section class="dk" id="([a-z_]+)"', d)
        assert ids[:5] == ["pioneer_greasefang", "modern_affinity", "modern_oswald",
                           "legacy_welder_cam", "premodern_stifflenough"], ids
        assert ids[-1] == "dc_cloud", ids
        # a arte do deck vem do art_crop da impressão que o deck usa
        assert "https://cards.scryfall.io/art_crop/front/t/m/tm-a.jpg" in p
        # sem escolha, a primeira impressão (a arte original), não a mais nova
        assert "https://cards.scryfall.io/art_crop/front/r/e/repl-a.jpg" in p
        assert "repl-b" not in p
        # os mosaicos levam à página do deck
        assert 'href="deck.html#modern_affinity"' in p
        # a caixa Vender, com o total (aqui não há nada a vender)
        assert 'href="vender.html"' in p
        # (R18) o último ponto do gráfico é o número do topo
        assert topo(p) == paginas.eur(v["total_eur"])
        assert set(ultimos_pontos(p)) <= {paginas.eur(v["total_eur"])}, ultimos_pontos(p)


def caso_painel_grafico_e_variacao():
    """(R18) O gráfico: os dias gravados com cópias e, no fim, o valor de hoje
    ao vivo. A variação do topo: o que ele tem hoje, aos preços de hoje e aos
    de há 30 dias."""
    with sessao() as con:
        semear(con)
        preco(con, "repl-a", "nonfoil", 10.0, dia=ha(45))
        preco(con, "repl-a", "nonfoil", 11.0, dia=ha(10))
        con.execute("INSERT INTO n_posse (ambito, scryfall_id, acabamento, qtd)"
                    " VALUES (?, 'repl-a', 'nonfoil', 10)", (REP,))
        for dia, total, copias in ((ha(60), 50.0, 5), (ha(20), 105.0, 10)):
            con.execute("INSERT INTO n_valor (dia, total_eur, copias, sem_preco)"
                        " VALUES (?,?,?,0)", (dia, total, copias))
        con.commit()
        s = valor.serie(con, HOJE)
        assert s == [(ha(60), 50.0, 0), (ha(20), 105.0, 0), (HOJE, 110.0, 0)], s
        var = valor.variacao_mes(con, HOJE)
        assert var == {"delta": 10.0, "pct": 10.0, "desde": ha(30), "hoje": HOJE}, var
        p = nucleo_painel.html_page(con)
        assert p.count("<polyline") == 3          # 1 mês · 3 meses · tudo
        for r in ("1 mês", "3 meses", "tudo"):
            assert r in p
        assert paginas.pct(10.0) in p and "num mês" in p
        assert topo(p) == paginas.eur(110.0)
        assert ultimos_pontos(p) == [paginas.eur(110.0)] * 3, ultimos_pontos(p)


def caso_painel_sem_nada_marcado():
    """A coleção vazia (a dele, hoje): a série é uma fila de 0 €. Não se
    desenha uma linha deitada no zero nem uma «variação» de 0 €."""
    with sessao() as con:
        semear(con)
        preco(con, "repl-a", "nonfoil", 10.0, dia=ha(28))
        preco(con, "repl-a", "nonfoil", 11.0, dia=ha(1))
        assert valor.serie(con, HOJE) == [(ha(28), 0.0, 0), (ha(1), 0.0, 0),
                                          (HOJE, 0.0, 0)]
        p = nucleo_painel.html_page(con)
        assert "<polyline" not in p
        assert "quando marcares as primeiras cartas" in p
        assert "num mês" not in p
        assert paginas.eur(0.0) in p


def caso_painel_dia_vazio_e_depois_marcar():
    """(C1, R18) O primeiro dia dele: o daily grava o valor ANTES de ele marcar
    uma carta (0 €, zero cópias) e depois ele marca um deck. O Painel nunca
    pode dizer «−100 %» nem desenhar uma queda a 0 €, e o número do topo é o
    último ponto do gráfico."""
    with sessao() as con:
        semear(con)
        preco(con, "repl-a", "nonfoil", 10.0, dia=ha(40))
        versao(con, REP, [("main", "Replenish", 4)])
        r = valor.gravar_valor_do_dia(con, ha(1))
        assert r["copias"] == 0
        assert con.execute("SELECT count(*) FROM n_valor").fetchone()[0] == 0
        # um dia vazio gravado antes da correção (o que a base dele já tem)
        con.execute("INSERT INTO n_valor (dia, total_eur, copias, sem_preco)"
                    " VALUES (?, 0.0, 0, 0)", (ha(2),))
        con.commit()
        marcar(con, REP, "Replenish", 4)
        p = nucleo_painel.html_page(con)
        assert topo(p) == paginas.eur(40.0), topo(p)
        assert ultimos_pontos(p) and set(ultimos_pontos(p)) == {paginas.eur(40.0)}, \
            ultimos_pontos(p)
        assert "▼" not in p and paginas.pct(-100.0) not in p and "−100" not in p
        assert "mín " + paginas.eur(0.0, 0) not in p
        assert all(t > 0 for _d, t, _s in valor.serie(con, HOJE))


def caso_painel_sem_salto_falso():
    """(R15) O degrau que se viu na base dele: os dias de trás em que a maior
    parte das cartas ainda não tinha preço valiam muito menos, e o Painel
    dizia «+261 % num mês». Esses dias saem da série — o gráfico e a variação
    só usam dias com a cobertura de hoje."""
    with sessao() as con:
        semear(con)
        preco(con, "repl-a", "nonfoil", 10.0, dia=ha(70))
        # a Saga (30 €) só ganha preço há 33 dias
        preco(con, "saga-a", "nonfoil", 30.0, dia=ha(33))
        preco(con, "repl-a", "nonfoil", 11.0, dia=ha(2))
        con.execute("INSERT INTO n_posse (ambito, scryfall_id, acabamento, qtd)"
                    " VALUES ('premodern_replenish', 'repl-a', 'nonfoil', 1),"
                    " ('rotativos', 'saga-a', 'nonfoil', 1)")
        con.commit()
        s = valor.serie(con, HOJE)
        assert s == [(ha(33), 40.0, 0), (ha(2), 41.0, 0), (HOJE, 41.0, 0)], s
        p = nucleo_painel.html_page(con)
        # a variação é 40 → 41, nunca 10 → 41 (+310 %)
        assert paginas.pct(2.5) in p, re.findall(r'class="vvar[^>]*>[^<]*', p)
        assert paginas.pct(310.0) not in p
        assert visual.data_pt(ha(70))[:5] not in p


def caso_deck_cinzento_e_cor():
    with sessao() as con:
        cenario(con)
        p = nucleo_decks.html_page(con)
        rep = seccao(p, REP)
        assert "falta" in classes_da_carta(rep, "Opalescence")
        assert "falta" not in classes_da_carta(rep, "Replenish")
        assert "falta" in classes_da_carta(rep, "Island")
        assert "sem preço" in rep
        # cabeçalho: tenho/total, quanto falta, versão e fonte
        e = posse.estado_deck(con, REP)
        assert e["tenho"] == 5 and e["total"] == 9, e
        assert f'{e["tenho"]}/{e["total"]}' in rep or f'{e["tenho"]} de {e["total"]}' in rep
        assert paginas.eur(e["custo_falta"]) in rep
        assert "(1 sem preço)" in rep
        assert "v1" in rep and "01/10/2026" in rep and "Premodern Discord" in rep
        # main e side com os seus títulos
        assert "Main" in rep and "Sideboard" in rep
        assert rep.index("Main") < rep.index("Sideboard")
        # foil brilha
        mod = seccao(p, MOD)
        assert "foil" in classes_da_carta(mod, "Thought Monitor")
        assert "foil" not in classes_da_carta(mod, "Urza's Saga")
        # todos os decks numa página, cada um na sua secção
        assert len(re.findall(r'<section class="dk" id="', p)) == 14
        # sem hash: a grelha de todos os decks
        assert 'id="todos"' in p and 'href="#modern_affinity"' in p
        assert "hashchange" in p


def caso_versoes_e_diferenca():
    with sessao() as con:
        cenario(con)
        versao(con, REP, [("main", "Replenish", 4), ("main", "Opalescence", 2),
                          ("main", "Island", 1), ("side", "Island", 3)],
               fonte="lista do Pedro", quando="2026-10-20T10:00:00")
        versao(con, REP, [("main", "Replenish", 4), ("side", "Island", 4)],
               fonte="ajuste", quando="2026-10-25T10:00:00")
        rep = seccao(nucleo_decks.html_page(con), REP)
        assert "v3" in rep and "25/10/2026" in rep and "ajuste" in rep
        # a última diferença: saiu a Opalescence (2)
        cab = rep.split("<details", 1)[0]
        assert "−2 Opalescence" in cab, cab
        # «ver versões» com as três
        det = re.search(r"<details class=\"versoes\">(.*?)</details>", rep, re.S)
        assert det, "falta o «ver versões»"
        d = det.group(1)
        assert "ver versões" in d
        for t in ("v1", "v2", "v3", "lista do Pedro", "Premodern Discord"):
            assert t in d, t
        assert "+1 Island" in d


def caso_rotativo_duas_partes():
    with sessao() as con:
        cenario(con)
        p = nucleo_decks.html_page(con)
        mod = seccao(p, MOD)
        i_fix, i_par = mod.index("Fixas deste deck"), mod.index("Partilhadas")
        assert i_fix < i_par
        fixas, partilhadas = mod[i_fix:i_par], mod[i_par:]
        assert 'title="Thought Monitor"' in fixas
        assert html.escape("Urza's Saga") in partilhadas
        assert "Thought Monitor" not in partilhadas
        # onde estão as partilhadas: no deck montado
        assert "Welder Cam" in partilhadas
        assert "falta" in classes_da_carta(mod, "Springleaf Drum")
        assert "falta" not in classes_da_carta(mod, "Urza's Saga")
        # para montar este: o monte vem da caixa do Welder Cam
        assert "Para montar este deck" in mod
        assert html.escape("4 Urza's Saga") in mod
        assert "Está montado" not in mod
        # o montado diz que está montado, e as partilhadas estão «aqui»
        leg = seccao(p, LEG)
        assert "Está montado" in leg
        assert "Para montar este deck" not in leg
        assert "aqui" in leg[leg.index("Partilhadas"):]


def caso_rotativo_main_e_sideboard():
    """(André, 29/10/2026) «dentro do deck, consegues separar o que é mainboard
    do que é sideboard?» — nos rotativos, cada bloco (Fixas, Partilhadas) leva
    o seu Main e o seu Sideboard, cada um com a sua conta."""
    with sessao() as con:
        cenario(con)
        versao(con, MOD, [("main", "Thought Monitor", 4), ("main", "Urza's Saga", 4),
                          ("main", "Springleaf Drum", 4), ("side", "Island", 2),
                          ("side", "Goblin Welder", 1)], fonte="com side",
               quando="2026-10-20T10:00:00")
        mod = seccao(nucleo_decks.html_page(con), MOD)
        i_fix, i_par = mod.index("Fixas deste deck"), mod.index("Partilhadas")
        fixas, partilhadas = mod[i_fix:i_par], mod[i_par:]

        def partes(bloco):
            m = re.search(r'<h3 class="gs">Main <small>(.*?)</small></h3>(.*?)'
                          r'<h3 class="gs">Sideboard <small>(.*?)</small></h3>(.*)',
                          bloco, re.S)
            assert m, bloco[:400]
            return m.groups()

        c_main, main, c_side, side = partes(fixas)
        assert 'title="Thought Monitor"' in main and 'title="Island"' in side
        assert 'title="Island"' not in main and c_side == "0 de 2", c_side
        c_main, main, c_side, side = partes(partilhadas)
        assert 'title="Goblin Welder"' in side and 'title="Goblin Welder"' not in main
        assert html.escape("Urza's Saga") in main and c_side == "0 de 1", c_side
        # a etiqueta «SB» na quantidade deixou de ser precisa
        assert "<small> SB</small>" not in mod


def caso_nome_entre_a_carta_e_o_preco():
    """(André, 30/10/2026) «entre a carta e o preço, preciso que esteja lá o
    nome» — o nome por cima do «falta N × €», e também nas que já tem."""
    with sessao() as con:
        cenario(con)
        p = nucleo_decks.html_page(con)
        rep = seccao(p, REP)

        def figura(trecho, nome):
            m = re.search(rf'<figure [^>]*title="{re.escape(html.escape(nome))}".*?</figure>',
                          trecho, re.S)
            assert m, nome
            return m.group(0)

        op = figura(rep, "Opalescence")                       # falta 1
        assert '<i class="cn">Opalescence</i>' in op, op
        assert op.index('class="cn"') < op.index("<em>"), op
        assert '<i class="cn">Replenish</i>' in figura(rep, "Replenish")   # completa
        mod = seccao(p, MOD)
        dr = figura(mod, "Springleaf Drum")                   # partilhada em falta: onde, nome, preço
        assert dr.index('class="onde') < dr.index('class="cn"') < dr.index("<em>"), dr
        # o nome vem escapado como o resto
        sg = figura(mod, "Urza's Saga")
        assert f'<i class="cn">{html.escape("Urza" + chr(39) + "s Saga")}</i>' in sg, sg


def caso_onde_legivel():
    """A etiqueta das partilhadas mostra o NOME do deck inteiro (com um
    ícone), não «no We…» cortado."""
    with sessao() as con:
        cenario(con)
        mod = seccao(nucleo_decks.html_page(con), MOD)
        m = re.search(r'<i class="onde"[^>]*>(.*?)</i>', mod, re.S)
        assert m and "Welder Cam" in m.group(1), m and m.group(1)
        assert "no Welder Cam" not in mod
        assert "text-overflow:ellipsis" not in visual.CSS.split(".ct .onde{", 1)[1].split("}", 1)[0]


def caso_falta_sem_euros_diz_traco():
    """Tudo o que falta está sem preço: «falta —», nunca «falta 0,00 €»."""
    with sessao() as con:
        cenario(con)
        marcar(con, REP, "Opalescence", 1)      # Opalescence completa
        e = posse.estado_deck(con, REP)
        assert e["custo_falta"] == 0 and e["sem_preco"] == 1, e
        rep = seccao(nucleo_decks.html_page(con), REP)
        assert "falta <b>—</b>" in rep, rep[:2000]
        assert "falta <b>" + paginas.eur(0.0) not in rep


def caso_sem_injeccao():
    """Texto que vem de fora (a fonte de uma versão, o erro da vigia, um nome)
    nunca entra na página como HTML nem como link `javascript:`."""
    mau = '"><img src=x onerror=alert(1)>'
    with sessao() as con:
        cenario(con)
        versao(con, REP, [("main", "Replenish", 4), ("side", "Island", 3)],
               fonte=mau)
        versao(con, MOD, [("main", "Thought Monitor", 4),
                          ("main", "Urza's Saga", 4)], fonte="javascript:alert(1)")
        con.execute("UPDATE n_deck SET vigia_erro = ?, vigia_ok_em = NULL,"
                    " nome = ? WHERE slug = ?", (mau + "<script>x</script>",
                                                 "A<b>ff</b>" + mau, AFF))
        # um nome com `<` no catálogo e no «tenho a mais»
        con.execute("UPDATE catalog.cards SET name = 'Is<land' WHERE"
                    " scryfall_id = 'isl-a'")
        con.commit()
        valor.a_mais_ajustar(con, "isl-a", "nonfoil", 1)
        for mod in (nucleo_painel, nucleo_decks, nucleo_vender):
            for ed in (False, True):
                p = mod.html_page(con, editable=ed, token="t")
                corpo = re.sub(r"(?s)<script>.*?</script>", "", p)
                assert "<img src=x" not in p, mod.__name__
                assert "<script>x" not in p, mod.__name__
                assert "<script" not in corpo, mod.__name__
                assert not re.search(r'href="\s*javascript:', p, re.I), mod.__name__
                assert "<b>ff</b>" not in p and "Is<land" not in p, mod.__name__
        d = nucleo_decks.html_page(con)
        assert html.escape(mau) in seccao(d, REP)
        assert "javascript:alert(1)" in seccao(d, MOD)      # como texto


def caso_espera_lista():
    with sessao() as con:
        cenario(con)
        p = nucleo_decks.html_page(con)
        oath = seccao(p, OATH)
        assert "À espera da tua lista" in oath
        assert "modo de edição" in oath
        assert "<figure" not in oath
        # um deck vigiado sem versão não pede a lista a ele
        aff = seccao(p, AFF)
        assert "À espera da tua lista" not in aff
        # no painel, o mosaico diz o mesmo
        painel = nucleo_painel.html_page(con)
        assert "à espera da lista" in painel


def caso_vigia_com_erro_diz():
    with sessao() as con:
        cenario(con)
        con.execute("UPDATE n_deck SET vigia_ok_em = '2026-10-20T03:30:00',"
                    " vigia_erro = 'o MTGO não respondeu' WHERE slug = ?", (AFF,))
        con.execute("UPDATE n_deck SET vigia_ok_em = NULL,"
                    " vigia_erro = 'sem ficheiro' WHERE slug = ?", (CLOUD,))
        con.commit()
        p = nucleo_decks.html_page(con)
        assert "não consegui ver a lista desde 20/10/2026" in seccao(p, AFF)
        assert "ainda não consegui ver a lista" in seccao(p, CLOUD)
        # sem erro, nada
        assert "não consegui ver a lista" not in seccao(p, REP)
        assert "consegui ver a lista" not in seccao(p, "premodern_stifflenough")


def caso_vender_total():
    with sessao() as con:
        cenario(con)
        valor.a_mais_ajustar(con, "isl-a", "nonfoil", 3)        # sem preço
        valor.a_mais_ajustar(con, "saga-a", "foil", 1)          # 50 €
        # a Opalescence sai da lista: 1 marcada → «saíram dos decks» (5 €)
        versao(con, REP, [("main", "Replenish", 4), ("side", "Island", 3)],
               fonte="sem Opalescence")
        # trocar a edição do Replenish: as 4 de ULG → «trocaste de edição» (40 €)
        posse.escolher_edicao(con, REP, "Replenish", "repl-b", "nonfoil")
        v = valor.a_vender(con)
        assert v["total_eur"] == 95.0, v
        p = nucleo_vender.html_page(con)
        topo = p.index(paginas.eur(95.0))
        a_mais, saidas, trocas = (p.index("Tenho a mais"),
                                  p.index("Saíram dos decks"),
                                  p.index("Trocaste de edição"))
        assert topo < a_mais < saidas < trocas
        assert "(3 cópias sem preço)" in p or "3 cópias sem preço" in p
        b_mais, b_saidas, b_trocas = p[a_mais:saidas], p[saidas:trocas], p[trocas:]
        assert "Island" in b_mais and "sem preço" in b_mais
        assert html.escape("Urza's Saga") in b_mais and "MH2" in b_mais
        assert "foil" in b_mais and paginas.eur(50.0) in b_mais
        assert "Opalescence" in b_saidas and "UW Replenish" in b_saidas
        assert "Replenish" in b_trocas and paginas.eur(40.0) in b_trocas
        assert "ULG" in b_trocas


def caso_vender_vazio():
    with sessao() as con:
        semear(con)
        p = nucleo_vender.html_page(con)
        assert paginas.eur(0.0) in p
        assert p.count('class="vazio"') == 3, p.count('class="vazio"')


def caso_modo_edicao():
    with sessao() as con:
        cenario(con)
        valor.a_mais_ajustar(con, "isl-a", "nonfoil", 1)
        for mod in (nucleo_painel, nucleo_decks, nucleo_vender):
            ver = mod.html_page(con)
            assert 'data-editavel' not in ver
            ed = mod.html_page(con, editable=True, token="segredo-123")
            assert '<body data-editavel="1">' in ed, mod.__name__
            assert "segredo-123" not in ed, mod.__name__
        ed = nucleo_decks.html_page(con, editable=True, token="segredo-123")
        mod_ = seccao(ed, MOD)
        assert 'data-deck="modern_affinity"' in mod_
        assert 'data-nome="Thought Monitor"' in mod_
        assert 'data-sid="tm-a"' in mod_ and 'data-acab="foil"' in mod_
        ver = nucleo_decks.html_page(con)
        assert "data-deck=" not in ver and "data-sid=" not in ver
        vend = nucleo_vender.html_page(con, editable=True)
        assert 'data-sid="isl-a"' in vend and 'data-acab="nonfoil"' in vend


def caso_sem_rede():
    with sessao() as con:
        cenario(con)
        valor.a_mais_ajustar(con, "isl-a", "nonfoil", 1)
        for mod in (nucleo_painel, nucleo_decks, nucleo_vender):
            for ed in (False, True):
                p = mod.html_page(con, editable=ed)
                assert not re.search(r"<script[^>]*\bsrc=", p), mod.__name__
                srcs = re.findall(r'\bsrc="([^"]*)"', p)
                for s in re.findall(r'\bsrcset="([^"]*)"', p):
                    srcs += [x.strip().split()[0] for x in s.split(",")]
                assert srcs, mod.__name__
                for s in srcs:
                    assert s.startswith("https://cards.scryfall.io/"), (mod.__name__, s)
                assert "url(" not in re.sub(r"(?s)<style>.*?</style>", "", p)
                assert "api.scryfall.com" not in p


def caso_casca():
    esperado = {nucleo_painel: ("index.html", "Painel"),
                nucleo_decks: ("deck.html", "Decks"),
                nucleo_vender: ("vender.html", "Vender")}
    with sessao() as con:
        cenario(con)
        for mod, (ficheiro, titulo) in esperado.items():
            assert mod.FICHEIRO == ficheiro and mod.TITULO == titulo
            p = mod.html_page(con)
            assert p.startswith("<!doctype html>")
            h1 = re.findall(r'<h1 class="pgt">(.*?)</h1>', p)
            assert h1 == [mod.TITULO], (mod.__name__, h1)
            assert f'<span class="tbt">{mod.TITULO}</span>' in p
            assert '<main id="conteudo"' in p and "</body></html>" in p
            # o build escreve o ficheiro certo
            tmp = Path(tempfile.mkdtemp())
            # o `rep` (o relatório do loadout antigo) aceita-se e não se usa
            out = mod.build(con, tmp / ficheiro, rep=None)
            assert out == tmp / ficheiro and out.read_text(encoding="utf-8") == p
        # o Painel é a entrada: as migalhas não levam a «Início»
        p = nucleo_painel.html_page(con)
        assert '<nav class="crumbs" aria-label="Migalhas"><b>Painel</b></nav>' in p


def caso_sem_cores_a_mao():
    """As cores vêm dos tokens da casca (`TEMA`), nunca de um hex novo."""
    rx = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    raiz = Path(__file__).resolve().parents[1]
    for f in ("mtgvault/nucleo/visual.py", "nucleo_painel.py", "nucleo_decks.py",
              "nucleo_vender.py"):
        texto = (raiz / f).read_text(encoding="utf-8")
        assert not rx.findall(texto), (f, rx.findall(texto)[:5])
    usados = set(re.findall(r"var\(\s*(--[a-z0-9-]+)\s*\)", visual.CSS))
    from mtgvault import site_shell
    definidos = set(re.findall(r"(--[a-z0-9-]+)\s*:", site_shell.TEMA))
    assert usados <= definidos, usados - definidos


def caso_nomes_repetidos_levam_o_formato():
    """(M4) «Affinity» e «Cloud» há dois de cada: em Vender («do …») e na caixa
    de montar o nome leva o formato quando se repete."""
    with sessao() as con:
        cenario(con)
        # a Opalescence marcada sai da lista do Modern Affinity
        versao(con, MOD, [("main", "Thought Monitor", 4), ("main", "Urza's Saga", 4),
                          ("main", "Springleaf Drum", 4), ("main", "Opalescence", 1)])
        marcar(con, MOD, "Opalescence", 1)
        versao(con, MOD, [("main", "Thought Monitor", 4), ("main", "Urza's Saga", 4),
                          ("main", "Springleaf Drum", 4)])
        assert visual.nomes_de_deck(con)[MOD] == "Affinity (Modern)"
        assert visual.nomes_de_deck(con)[AFF] == "Affinity (Pauper)"
        assert visual.nomes_de_deck(con)[REP] == "UW Replenish"
        p = nucleo_vender.html_page(con)
        assert "do Affinity (Modern)" in p, re.findall(r"do [^<·]*", p)
        # o deck montado com um nome repetido, na caixa de montar
        con.execute("UPDATE n_deck SET nome = 'Affinity' WHERE slug = ?", (LEG,))
        con.commit()
        mod = seccao(nucleo_decks.html_page(con), MOD)
        assert "Montado agora: Affinity (Legacy)" in mod, mod[-600:]
        assert "Traz da caixa do Affinity (Legacy)" in mod
        # (M5) «Voltar ao deck» só quando a carta voltou à lista do deck
        assert 'data-destino="devolver"' not in nucleo_vender.html_page(con, editable=True)
        versao(con, MOD, [("main", "Thought Monitor", 4), ("main", "Urza's Saga", 4),
                          ("main", "Springleaf Drum", 4), ("main", "Opalescence", 1)])
        ed = nucleo_vender.html_page(con, editable=True)
        assert ed.count('data-destino="devolver"') == 1 and "Voltar ao deck" in ed
        assert 'data-destino="devolver"' not in nucleo_vender.html_page(con)


def caso_fonte_com_link_no_meio():
    """(M9) A fonte de uma versão da vigia do MTGO é «MTGO · evento · dia ·
    URL»: o URL vira link mesmo no meio do texto. Só http(s): um
    `javascript:` fica texto."""
    f = visual.fonte_html("MTGO · Pauper Challenge · 2026-10-20 · "
                          "https://www.mtgo.com/decklist/pauper-2026-10-20")
    assert f.startswith("MTGO · Pauper Challenge · 2026-10-20 · <a href="), f
    assert '<a href="https://www.mtgo.com/decklist/pauper-2026-10-20" rel="noopener">' in f, f
    f = visual.fonte_html("vi em https://x.pt/lista. e no discord")
    assert '<a href="https://x.pt/lista" rel="noopener">x.pt/lista</a>. e no discord' in f, f
    assert "<a" not in visual.fonte_html("javascript:alert(1)")
    assert "<a" not in visual.fonte_html('"><img src=x>')
    assert visual.fonte_html("https://moxfield.com/decks/abc").startswith('<a href="https://moxfield.com/decks/abc"')
    assert visual.fonte_html("") == "sem fonte"


def validar_direto(con, slug, sid, acab, qtd, n=1):
    """Põe `qtd` cópias validadas, com um recorte de teste, sem passar pelas
    fotos a sério (a escrita de verdade tem os seus casos em test_nucleo_fotos).
    Devolve o caminho do recorte."""
    _n[0] += 1
    fid = con.execute(
        "INSERT INTO n_foto (caminho, dia, sessao, linha, indice) VALUES"
        " ('x', '2026-10-30', 's', ?, 0)", (_n[0],)).lastrowid
    caminho = f"assets/cartas/{fid}-{n}.jpg"
    rid = con.execute("INSERT INTO n_recorte (foto_id, numero, caminho) VALUES"
                      " (?, ?, ?)", (fid, n, caminho)).lastrowid
    con.execute("INSERT INTO n_validacao (recorte_id, ambito, scryfall_id,"
                " acabamento, lingua, qtd, em) VALUES (?, ?, ?, ?, 'en', ?,"
                " '2026-10-30T10:00:00')", (rid, slug, sid, acab, qtd))
    con.commit()
    return caminho


def figuras(trecho):
    return re.findall(r'<figure class="([^"]*)"', trecho)


def figura(trecho, nome):
    m = re.search(rf'<figure [^>]*title="{re.escape(html.escape(nome))}".*?</figure>',
                  trecho, re.S)
    assert m, nome
    return m.group(0)


def caso_carta_com_recorte():
    """(Tarefa 8) Uma carta validada mostra o RECORTE da foto dele (não a
    imagem do Scryfall), leva a classe `validada` e guarda a oficial em
    `data-oficial` (para a poder mostrar ao toque); as outras ficam como
    estavam."""
    with sessao() as con:
        cenario(con)
        caminho = validar_direto(con, MOD, "tm-a", "foil", 1)
        mod = seccao(nucleo_decks.html_page(con), MOD)
        fig = figura(mod, "Thought Monitor")
        assert "validada" in classes_da_carta(mod, "Thought Monitor")
        assert f'src="{caminho}"' in fig, fig
        assert 'width="146" height="204"' in fig and 'loading="lazy"' in fig, fig
        assert 'src="https://' not in fig, "o recorte substitui a imagem do CDN"
        assert 'data-oficial="https://' in fig and "/normal/front/" in fig, fig
        assert 'class="cam"' in fig and "<svg" in fig, "falta a câmara no canto"
        # as outras cartas do deck continuam com a imagem do Scryfall
        outra = figura(mod, "Springleaf Drum")
        assert "data-oficial" not in outra and 'src="https://' in outra, outra
        assert "validada" not in classes_da_carta(mod, "Springleaf Drum")


def caso_progresso_com_validadas():
    """(Tarefa 8) A linha do progresso diz quantas cartas estão validadas, no
    singular e no plural, e só quando há."""
    with sessao() as con:
        cenario(con)
        validar_direto(con, MOD, "tm-a", "foil", 1)
        mod = seccao(nucleo_decks.html_page(con), MOD)
        assert "· 1 validada<" in mod and "validadas<" not in mod, mod[:600]
        validar_direto(con, MOD, "tm-a", "foil", 1, n=2)
        mod = seccao(nucleo_decks.html_page(con), MOD)
        assert "· 2 validadas<" in mod, mod[:600]
        est = posse.estado_deck(con, MOD)
        assert est["validadas"] == 2 and est["validadas"] <= est["tenho"]
        tm = [c for c in est["cartas"] if c["nome"] == "Thought Monitor"][0]
        assert tm["validadas"] == 2 and tm["recorte"].startswith("assets/cartas/")


def caso_sem_validacao_igual():
    """(Tarefa 8) Sem nenhuma validação, a página não diz nada de validadas e
    as cartas levam a imagem do Scryfall, como antes."""
    with sessao() as con:
        cenario(con)
        p = nucleo_decks.html_page(con)
        for cls in figuras(p):
            assert "validada" not in cls.split(), cls
        assert "data-oficial" not in p and "assets/cartas" not in p
        assert not re.search(r"· \d+ validadas?<", p)
        est = posse.estado_deck(con, MOD)
        assert est["validadas"] == 0
        assert all(c["validadas"] == 0 and c["recorte"] is None
                   for c in est["cartas"])


def caso_validadas_nunca_passam_a_posse_main_e_side():
    """(Tarefa 8) Uma carta em main e em side é a mesma edição física: as
    validadas repartem-se como a posse (main antes do side), por isso a soma
    nunca passa o `tenho` do deck."""
    with sessao() as con:
        cenario(con)
        versao(con, MOD, [("main", "Thought Monitor", 2), ("side", "Thought Monitor", 2),
                          ("main", "Urza's Saga", 4), ("main", "Springleaf Drum", 4)],
               fonte="com side", quando="2026-10-20T10:00:00")
        marcar(con, MOD, "Thought Monitor", -1)          # 4 → 3 cópias
        validar_direto(con, MOD, "tm-a", "foil", 3)
        est = posse.estado_deck(con, MOD)
        tms = {c["seccao"]: c for c in est["cartas"]
               if c["nome"] == "Thought Monitor"}
        assert (tms["main"]["tenho"], tms["side"]["tenho"]) == (2, 1)
        assert (tms["main"]["validadas"], tms["side"]["validadas"]) == (2, 1), tms
        assert tms["main"]["recorte"] and tms["side"]["recorte"]
        assert est["validadas"] <= est["tenho"], (est["validadas"], est["tenho"])
    # com menos validadas do que a posse, vão primeiro para o main
    with sessao() as con:
        cenario(con)
        versao(con, MOD, [("main", "Thought Monitor", 2),
                          ("side", "Thought Monitor", 2)],
               fonte="com side", quando="2026-10-20T10:00:00")
        validar_direto(con, MOD, "tm-a", "foil", 3)      # posse 4
        e2 = posse.estado_deck(con, MOD)
        t2 = {c["seccao"]: c for c in e2["cartas"]}
        assert (t2["main"]["validadas"], t2["side"]["validadas"]) == (2, 1)
        assert e2["validadas"] == 3 and e2["tenho"] == 4


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
