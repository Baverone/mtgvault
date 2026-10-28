"""AS CORRECÇÕES DO mtg.baverone.com DA AUDITORIA DE 2026-10-20.

Pedido do André: *"corrige tudo o que for relacionado com o site baverone.com e
os subsites do mtg"*. A auditoria (`ai-pc/work/auditoria-sites-1020/`) achou sete
defeitos no mtg e o supervisor um oitavo:

  M1. uma nota com prazo («até 2026-10-09») continuava à vista, a vermelho, onze
      dias depois do prazo — na lista de Faltas e no chip da Deckboxes;
  M2. nenhuma página declarava favicon (o rift e o tibia têm);
  M3. percentagens à inglesa («-100.0%») na Galeria e no texto da janela da RL;
  M4. a nota «As faltas saem da BASE, não do que ele diz ter» falava dele na
      3.ª pessoa e aparecia uma vez por lista (4× no Metagame);
  M5. a Reserved List com «só as que tenho» e nenhuma carta deixava 23
      cabeçalhos vazios e não dizia que não há nenhuma;
  M6. dois cinzentos do Showcase abaixo de 4,5:1;
  M7. três campos sem rótulo acessível (Galeria, Cobertura, Faltas);
  e a COLEÇÃO VAZIA desde 13/10 (refeita por fotos) mostrava «0 cartas · 0,00 €»
  sem uma palavra a explicar.

Não toca na `vault.db` a sério: fixa `MTGVAULT_HOME`, `MTGVAULT_DB` e
`MTGVAULT_CATALOG` antes de importar o `mtgvault` (ver `tests/_bateria.py`).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

from mtgvault import paginas, site_shell as shell  # noqa: E402


def avaliar(html: str, js: str):
    """Corre `js` no contexto de `html` (o harness `avaliar_js.js`)."""
    if not shutil.which("node"):
        return None
    d = Path(tempfile.mkdtemp())
    (d / "p.html").write_text(html, encoding="utf-8")
    (d / "t.js").write_text(js, encoding="utf-8")
    p = subprocess.run(["node", str(Path(__file__).with_name("avaliar_js.js")),
                        str(d / "p.html"), str(d / "t.js")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert p.returncode == 0, (p.stdout or "") + (p.stderr or "")[-2500:]
    return json.loads(p.stdout)


def _funcao_js(fonte: str, nome: str) -> str:
    """O texto de uma `function nome(...) {...}` de topo, por contagem de
    chavetas (as funções do deckboxes não têm chavetas em strings)."""
    i = fonte.index(f"function {nome}(")
    j = fonte.index("{", i)
    n = 0
    for k in range(j, len(fonte)):
        n += {"{": 1, "}": -1}.get(fonte[k], 0)
        if n == 0:
            return fonte[i:k + 1]
    raise AssertionError(nome)


URG_PASSADA = {"ate": "2026-10-09", "dias": -11, "passou": True,
               "porque": "entrou no sideboard pela decisão de 04/10",
               "prioridade": "alta", "material_pendente": None,
               "pendente": False}
URG_FUTURA = dict(URG_PASSADA, ate="2099-01-01", dias=999, passou=False)
#: Uma página gerada ANTES do prazo e aberta DEPOIS: o Python disse
#: `passou: false` no dia em que a escreveu, e o browser tem de ver a data.
URG_VELHA = dict(URG_PASSADA, passou=False, dias=3)


# ===========================================================================
def caso_m1_nota_com_prazo_passado_fica_discreta():
    """M1. Uma nota cujo `urgencia.ate` já passou não aparece como aviso: fica
    marcada como passada, discreta — nas Faltas E no chip da Deckboxes."""
    import deckboxes                                           # noqa: PLC0415
    import faltas                                              # noqa: PLC0415
    js = faltas._js()
    assert "\narranca();" in js
    pagina = "<script>" + js.replace("\narranca();", "\n") + "</script>"
    r = avaliar(pagina, """
D = {totais: {}};
const l = u => ({nm: 'Whipflare', q: 1, unit: 1, total: 1, req: 'EN', urgencia: u});
const resultado = {passada: linhaHTML(l(%s), false, false),
                   futura: linhaHTML(l(%s), false, false),
                   velha: linhaHTML(l(%s), false, false)};
""" % (json.dumps(URG_PASSADA), json.dumps(URG_FUTURA), json.dumps(URG_VELHA)))
    if r is None:
        print("sem node — saltado")
        return
    assert "entrou no sideboard" in r["futura"] and 'class="urg"' in r["futura"], r
    for k in ("passada", "velha"):
        assert "entrou no sideboard" not in r[k], (k, "a nota caducada continua à vista", r[k])
        assert 'class="urg"' not in r[k], (k, "continua com o estilo de aviso", r[k])
        assert "urg passou" in r[k] and "2026-10-09" in r[k], (k, r[k])
    # A Deckboxes: o mesmo, no chip.
    fonte = deckboxes.JS
    chip = _funcao_js(fonte, "chipUrg")
    pagina = ("<script>" + paginas.JS_DADOS
              + "\nfunction esc(s){return String(s == null ? '' : s);}\n"
              + chip + "</script>")
    r = avaliar(pagina, "const resultado = {p: chipUrg(%s), f: chipUrg(%s), v: chipUrg(%s)};"
                % (json.dumps(URG_PASSADA), json.dumps(URG_FUTURA), json.dumps(URG_VELHA)))
    assert "urg passou" not in r["f"], r
    for k in ("p", "v"):
        assert "urg passou" in r[k] and "urg ja" not in r[k], (k, r[k])
        assert "2026-10-09" in r[k], (k, r[k])
    print("M1: a nota com prazo passado fica discreta (faltas e deckboxes)")


def caso_m2_todas_as_paginas_tem_favicon():
    """M2. O `<head>` comum declara o ícone, e todas as páginas publicadas o
    levam (lê-se o HTML publicado, como o `caso_todas_as_paginas_geradas_levam_a_barra_lateral`)."""
    h = shell.head("x")
    assert re.search(r'<link rel="icon" href="data:image/svg\+xml,', h), h[:400]
    faltam = []
    # As páginas dos DOIS menus (2026-10-28): o config do repositório tem o
    # `nucleo.ligado`, e o HTML publicado em disco é ainda o do site antigo até
    # o `daily` o regenerar — as treze de antes continuam a ser conferidas.
    sys.path.insert(0, str(RAIZ / "tests"))
    import _nucleo_interruptor                                   # noqa: PLC0415
    with _nucleo_interruptor.interruptor(False):
        antigo = list(paginas.MENU)
    for f in sorted(set(antigo) | set(paginas.MENU)):
        p = RAIZ / f
        if p.is_file() and 'rel="icon"' not in p.read_text(encoding="utf-8", errors="replace"):
            faltam.append(f)
    assert not faltam, ("páginas publicadas sem favicon", faltam)
    print("M2: favicon em todas as páginas")


def caso_m3_percentagens_a_portuguesa():
    """M3. «−100,0 %», com vírgula, o sinal menos e o espaço antes do %."""
    assert paginas.pct(-100) == "−100,0 %", paginas.pct(-100)
    assert paginas.pct(12.345) == "+12,3 %", paginas.pct(12.345)
    assert paginas.pct(0) == "+0,0 %", paginas.pct(0)
    assert paginas.pct(4.9, casas=0) == "+5 %", paginas.pct(4.9, casas=0)
    from mtgvault import loadout                               # noqa: PLC0415
    t = loadout._texto_janela(4.9, 27)
    assert "+4,9 %" in t and "." not in t, t
    # Ninguém volta a escrever uma VARIAÇÃO (com sinal) com o formato do Python
    # — `:+.1f}%` ou o sinal à mão `{sign}{x:.0f}%`. (As linhas do CLI e do log
    # do daily não são o site, e ficam fora.)
    maus = []
    for p in list(RAIZ.glob("*.py")) + list((RAIZ / "mtgvault").glob("*.py")):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if (re.search(r"\{[^{}]*:\+\.\d+f\}\s?%", ln)
                    or re.search(r"\{sign\}\{[^{}]*:\.\d+f\}\s?%", ln)) \
                    and "Era `f'" not in ln:
                maus.append(f"{p.name}:{i}: {ln.strip()[:90]}")
    assert not maus, ("percentagens à inglesa", maus)
    print("M3: percentagens à portuguesa")


ACHADO = {"carta": "Kasmina", "formato": "modern", "evento": "Liga", "data": "2026-10-19",
          "fonte": "mtgo", "faltas": {"linhas": [{"falta": 2, "basica": False,
                                                  "nm": "Kasmina", "tem": 0, "precisa": 2}],
                                      "falta_total": 2}}


def caso_m4_a_nota_das_faltas_fala_com_tu_e_aparece_uma_vez():
    """M4. «tu», como o resto do site, e uma vez por página — não uma por lista."""
    import metagame                                            # noqa: PLC0415
    from mtgvault import vigia                                 # noqa: PLC0415
    n = vigia.NOTA_FALTAS
    assert " ele " not in n and "acabou" not in n, n
    assert "dizes" in n and "acabaste" in n, n
    painel = {"vigiadas": [{"carta": "Kasmina", "formatos": ["modern"], "achados": 4,
                            "ultima": "2026-10-19", "nota": ""}],
              "achados": [dict(ACHADO, faltas=dict(ACHADO["faltas"], nota=n))
                          for _ in range(4)],
              "total": 4, "nota": n}
    real = metagame.vigia.painel
    metagame.vigia.painel = lambda con: painel
    try:
        h = metagame._vigia_html(None)
    finally:
        metagame.vigia.painel = real
    import html as _h                                          # noqa: PLC0415
    assert h.count(_h.escape(n)) == 1, h.count(_h.escape(n))
    print("M4: a nota fala com tu e aparece uma vez")


def caso_m5_rl_so_as_que_tenho_sem_nenhuma():
    """M5. Uma edição sem nenhuma carta tua é marcada e some com o filtro; e a
    página diz que não há nenhuma quando não tens nenhuma."""
    import reservedlist                                        # noqa: PLC0415
    e0 = reservedlist.cabecalho_edicao({"parte": "usg", "nome": "Urza's Saga",
                                        "ano": "1998", "tens": 0, "n": 14})
    e1 = reservedlist.cabecalho_edicao({"parte": "ulg", "nome": "Urza's Legacy",
                                        "ano": "1999", "tens": 1, "n": 9})
    assert 'class="ed vazia"' in e0, e0
    assert "vazia" not in e1, e1
    css = reservedlist._CSS
    assert "body.only section.ed.vazia" in css and "body.only .edidx a.vazia" in css, css[-600:]
    assert "não tens nenhuma" in reservedlist.frase_nenhuma(0).lower()
    assert reservedlist.frase_nenhuma(3) == ""
    print("M5: a RL esconde as edições vazias e diz que não há nenhuma")


def _rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _lum(h):
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in _rgb(h)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contraste(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def caso_m6_contraste_do_showcase():
    """M6. Os dois cinzentos do Showcase acima de 4,5:1 contra o fundo deles."""
    tema = dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{3,6})", shell.TEMA))
    src = (RAIZ / "showcase.py").read_text(encoding="utf-8")

    def cor(sel):
        m = re.search(re.escape(sel) + r"\{color:([^;}]+)", src)
        assert m, sel
        v = m.group(1).strip()
        return tema[v[6:-1]] if v.startswith("var(") else v
    for sel, fundo in ((".typehdr .dim", "#12151f"), (".bdg.dim", "#1d2130")):
        c = contraste(cor(sel), fundo)
        assert c >= 4.5, (sel, cor(sel), fundo, round(c, 2))
    print("M6: contraste do showcase acima de 4,5:1")


def caso_m7_campos_com_rotulo():
    """M7. A procura da Galeria, os selects de edição da Cobertura e a caixa da
    wantlist das Faltas têm rótulo acessível."""
    import collection_gallery                                  # noqa: PLC0415
    import faltas                                              # noqa: PLC0415
    g = collection_gallery._TMPL
    assert re.search(r'<input id="q"[^>]*aria-label="', g), "procura da Galeria"
    assert re.search(r'<textarea id="cmk"[^>]*aria-label="', faltas._tmpl()), "wantlist"
    mc = (RAIZ / "meta_coverage.py").read_text(encoding="utf-8")
    i = mc.index("function preparar(")
    assert "aria-label" in mc[i:i + 1500], "os selects de edição da Cobertura"
    print("M7: os três campos têm rótulo")


def caso_colecao_vazia_diz_porque():
    """Coleção vazia: uma frase, uma vez, que desaparece quando entrar a primeira
    carta — sem inventar números."""
    from mtgvault import collection, db                        # noqa: PLC0415
    d = Path(tempfile.mkdtemp())
    with db.session(d / "v.db", d / "c.db") as con:
        con.execute(
            """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
               set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES ('s1','o1','Island','unh','Unhinged','1','en','common',
               'Basic Land',0,'','["nonfoil"]','2004-11-19','{}',0,0)""")
        con.commit()
        assert paginas.colecao_vazia(con)
        pag = '<body><div class="wrap"><p>0 cartas</p></div><div class="wrap"></div>'
        h = paginas.com_aviso_colecao(pag, con)
        assert h.count('class="cvazia"') == 1, h
        assert "13/10" in h and "fotografado" in h, h
        assert h.index('class="cvazia"') < h.index("0 cartas"), "o aviso vem antes do 0"
        collection.add_copy(con, "Island", set_code="unh", quantity=1,
                            sub_collection="Colecção")
        con.commit()
        assert not paginas.colecao_vazia(con)
        assert paginas.com_aviso_colecao(pag, con) == pag
    # As cinco páginas onde se vê o 0 passam pelo aviso.
    for f in ("inicio.py", "collection_gallery.py", "colecao_cor.py", "caixarl.py",
              "meta_coverage.py"):
        assert "com_aviso_colecao(" in (RAIZ / f).read_text(encoding="utf-8"), f
    assert ".cvazia" in shell.CSS
    print("coleção vazia: uma frase, que sai sozinha")


CASOS = (caso_m1_nota_com_prazo_passado_fica_discreta,
         caso_m2_todas_as_paginas_tem_favicon,
         caso_m3_percentagens_a_portuguesa,
         caso_m4_a_nota_das_faltas_fala_com_tu_e_aparece_uma_vez,
         caso_m5_rl_so_as_que_tenho_sem_nenhuma,
         caso_m6_contraste_do_showcase,
         caso_m7_campos_com_rotulo,
         caso_colecao_vazia_diz_porque)


def run():
    falhas = []
    for fn in CASOS:
        try:
            fn()
        except Exception as e:                                 # noqa: BLE001
            falhas.append(f"{fn.__name__}: {type(e).__name__}: {str(e)[:300]}")
    shutil.rmtree(_TMP, ignore_errors=True)
    if falhas:
        print("\n".join(["FALHAS:"] + falhas))
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    run()
