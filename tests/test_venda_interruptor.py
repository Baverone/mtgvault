"""«PARA JÁ TIRA O VENDER» (André, 2026-09-25, à letra) — o interruptor.

O **«para já» é literal**: isto tem de voltar com UMA chave, e nada se apaga.
O que aqui se tranca, nos dois sentidos:

  1. **desligado (`venda.mostrar: false`, a omissão desde hoje)** não sobra uma
     palavra de venda no que ele vê — nem na barra lateral do site, nem no
     Início, nem na Deckboxes (nas abas todas, nos dois modos, publicada E em
     modo edição), nem na Reserved List;
  2. **nem um botão órfão**: zero `data-vend` («vendida»), zero `data-saida`
     («gravar em data/») e zero `href="…#vender"` — um botão que sobrevivesse
     chamaria um endpoint que hoje responde 409;
  3. **ligado, volta tudo** — a aba, os botões, o item da barra, o cartão do
     Início e o selo VENDER da Reserved List;
  4. **os endpoints de escrita recusam-se em condições**: 409 com a razão em
     português, e sem tocar na base nem escrever ficheiro nenhum;
  5. **o motor não sabe que isto existe**: o `loadout.report` é igual ao
     cêntimo nos dois estados, e o `venda.relatorio` continua a dar a lista;
  6. **o `daily` salta o passo e DIZ porquê**, e não mexe nos ficheiros que já
     lá estão;
  7. **a pergunta vive num sítio só** (`venda.mostrar`): ninguém volta a ler a
     chave do config à mão, que é como ficava um item da barra a apontar para
     uma aba que já não existe.

Cada caso chumba se a tarefa não fizer nada. Não toca na rede nem na base a
sério.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
# A omissão de hoje: SEM a chave. É de propósito — é assim que o config dele
# ficaria se alguém lhe apagasse a linha, e a resposta tem de ser «desligado».
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "spml", "formatos": ["legacy"], "lingua": "en",
         "acabamento": "foil"}],
    "caixas": [
        {"slot": "leg", "nome": "Leg", "formato": "legacy", "fonte": "deck",
         "ref": "Leg", "balde": "Colecção", "estado": "permanente",
         "prioridade": 1}],
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import db, loadout, sources, venda  # noqa: E402
from mtgvault import site_shell as shell  # noqa: E402

import daily  # noqa: E402
import deckboxes  # noqa: E402
import inicio  # noqa: E402
import reservedlist  # noqa: E402
import webapp  # noqa: E402

webapp.ROOT = _TMP / "site"
webapp.ROOT.mkdir(exist_ok=True)

HOJE = date.today().isoformat()
# (nome, edição, número, reserved, cor, tipo)
CATALOGO = [
    ("Sol Ring", "c21", "263", 0, "", "Artifact"),
    ("Dark Ritual", "4ed", "129", 0, "B", "Instant"),
    ("Gilded Drake", "usg", "78", 1, "U", "Creature"),
]
_ABERTAS = []


# ---------------------------------------------------------------------------
# A base de mentira
# ---------------------------------------------------------------------------
def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, num, rl, ci, tl) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital,
               reserved, set_type)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,?,?,'1995-04-01',?,0,?,'expansion')""",
            (f"id-{i}", f"or-{i}", nm, sc, f"Set {sc.upper()}", num, tl, ci,
             json.dumps(["nonfoil", "foil"]),
             json.dumps({"legacy": "legal"}), rl))
        con.execute("""INSERT INTO price_latest (scryfall_id, source, finish, date,
                       low, trend) VALUES (?,'cardmarket','nonfoil',?,?,?)""",
                    (f"id-{i}", HOJE, 3.0 + i, 3.0 + i))
    con.execute("INSERT INTO decks (name, format) VALUES ('Leg','legacy')")
    did = con.execute("SELECT id FROM decks WHERE name='Leg'").fetchone()["id"]
    con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                "VALUES (?, 'Sol Ring', 1, 'main')", (did,))
    for sub in ("Colecção", "Caixa Reserved List"):
        con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                    "VALUES (?, 'player')", (sub,))
    con.commit()
    # 6 Dark Ritual (playset de 4 -> 2 de excedente) e 1 Gilded Drake da RL.
    add(con, "Dark Ritual", 6)
    add(con, "Gilded Drake", 1, sub="Caixa Reserved List")
    return con


def add(con, nm, q=1, sub="Colecção", lang="en", finish="nonfoil"):
    sid = con.execute("SELECT scryfall_id FROM catalog.cards WHERE name = ?",
                      (nm,)).fetchone()["scryfall_id"]
    sub_id = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                         (sub,)).fetchone()["id"]
    cur = con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                         condition, purpose, sub_collection_id)
                         VALUES (?,?,?,?,'NM','player',?)""",
                      (sid, q, finish, lang, sub_id))
    con.commit()
    return cur.lastrowid


def liga(valor: bool | None, revalidacao: bool = False):
    """Põe (ou tira) o `venda.mostrar` no config e esquece a cache."""
    novo = json.loads(json.dumps(CFG))
    if valor is not None:
        novo["venda"] = {"mostrar": valor}
    if revalidacao:
        novo["revalidacao"] = {"desde": "2026-09-20"}
    CFG_PATH.write_text(json.dumps(novo, ensure_ascii=False), encoding="utf-8")
    sources._CFG_CACHE.clear()


# ---------------------------------------------------------------------------
# As palavras de venda no TEXTO VISÍVEL
# ---------------------------------------------------------------------------
# `\b` de propósito: «Ancient Vendetta» e «Vendilion Clique» são NOMES DE CARTAS
# e não podem chumbar isto — o que não pode aparecer é a palavra inteira.
PALAVRA = re.compile(r"\b(vend[ae]s?|vender|vendidas?|vendidos?)\b", re.IGNORECASE)
# Os botões e os links que não podem sobreviver ao interruptor.
ORFAOS = re.compile(r'data-vend=|data-saida=|href="[^"]*#vender"|data-aba="vender"')


def sem_scripts(html: str) -> str:
    """O HTML sem o `<script>` e sem o `<style>`.

    O `html_page` EMBUTE o JavaScript inteiro (é o que os testes lêem de um
    ficheiro solto), e lá dentro estão as strings que desenham a aba Vender —
    incluindo `data-vend=`. Essas não são botões: são o código que só corre se
    o `D.venda` existir. O que conta é o que ficou no DOCUMENTO e o que o
    `render()` desenhou; é por isso que este teste lê as duas coisas.
    """
    t = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    return re.sub(r"(?is)<style\b.*?</style>", " ", t)


def visivel(html: str) -> str:
    """O que se LÊ na página: fora de `<script>`, `<style>` e das etiquetas.

    Um comentário de CSS ou de JavaScript não está à vista, e trancá-lo aqui
    era trocar o que ele vê pelo que o ficheiro tem escrito.
    """
    t = re.sub(r"(?s)<!--.*?-->", " ", sem_scripts(html))
    return re.sub(r"(?s)<[^>]+>", " ", t)


# A ÚNICA excepção, e é deliberada: o NOME DA CHAVE do config
# (`venda.mostrar`), que aparece onde a página explica uma ausência — a metade
# «levar» da Feira. É o que lhe diz como voltar a ligar isto, e sem ele a
# explicação mandava-o procurar. Não é uma lista de venda nem um botão; é a
# maçaneta da porta que acabou de fechar.
CHAVE = re.compile(r"venda\.mostrar")


def palavras(html: str) -> list[str]:
    txt = CHAVE.sub("«a chave»", visivel(html))
    return [" ".join(txt[max(0, m.start() - 60):m.start() + 60].split())
            for m in PALAVRA.finditer(txt)]


def _abas_desenhadas(con, editable):
    """`{aba: html}` — o que o JavaScript da Deckboxes DESENHOU em cada aba.

    Salta em silêncio sem `node`, como os outros testes que usam o harness: a
    bateria tem de correr num PC sem ele.
    """
    if not _tem_node():
        return None
    pasta = Path(tempfile.mkdtemp())
    pag = pasta / "deckboxes.html"
    pag.write_text(deckboxes.html_page(con, editable=editable,
                                       token="t" if editable else ""),
                   encoding="utf-8")
    dump = pasta / "dump.json"
    r = subprocess.run(["node", str(Path(__file__).parent / "render_deckboxes.js"),
                        str(pag), str(dump)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, (r.stdout, r.stderr)
    return json.loads(dump.read_text(encoding="utf-8"))


def _tem_node():
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


# ---------------------------------------------------------------------------
# 1 + 2. Desligado: nem palavra, nem botão
# ---------------------------------------------------------------------------
def caso_desligado_nao_sobra_venda_no_que_ele_ve():
    liga(None)                       # sem a chave = desligado, que é a omissão
    assert venda.mostrar() is False
    con = base()
    rep = loadout.report(con)
    # Há mesmo o que vender: se não houvesse, este teste passava por engano.
    assert rep["copias"] >= 2, rep["copias"]

    # (a) A BARRA LATERAL, que é igual em todas as páginas.
    nav = shell.barra("index.html")
    assert 'href="deckboxes.html#vender"' not in nav
    assert not palavras(nav), palavras(nav)
    assert ">Comprar<" in nav, "a secção das compras desapareceu inteira"

    # (b) A DECKBOXES, nos dois modos.
    for editable in (False, True):
        pag = deckboxes.html_page(con, rep=rep, editable=editable,
                                  token="t" if editable else "")
        assert not palavras(pag), (editable, palavras(pag)[:5])
        assert not ORFAOS.search(sem_scripts(pag)), \
            (editable, "botão ou link órfão no documento")
        # E o PAYLOAD vem sem a venda: é ele que decide o que o JavaScript
        # desenha, e é ele que viaja para o telemóvel.
        assert '"venda": null' in pag or '"venda":null' in pag, \
            "o payload ainda traz o bloco da venda"

    # (c) E o que o JAVASCRIPT desenha, aba a aba, nos dois modos.
    for editable in (False, True):
        abas = _abas_desenhadas(con, editable)
        if abas is None:
            print("  (sem node: o render das abas fica por verificar)")
            break
        for nome, html in abas.items():
            assert not palavras(html), (editable, nome, palavras(html)[:3])
            assert not ORFAOS.search(html), (editable, nome, "botão órfão")
        # E a aba «vender» não desaparece em erro: cai na vista das caixas.
        assert abas["vender"], "a aba vender ficou vazia em vez de cair nas caixas"

    # (d) O INÍCIO — era aqui que o valor da venda estava a negrito.
    out = _TMP / "index.html"
    inicio.build(con, out, rep=rep)
    idx = out.read_text(encoding="utf-8")
    assert not palavras(idx), palavras(idx)[:5]
    assert "#vender" not in idx
    assert "Para arrumar" in idx, "o painel do Início deixou de ter números"

    # (e) A RESERVED LIST — o selo VENDER e a caixa «A vender». Desde
    # 2026-09-15 as cartas vivem nas PARTES (`data/paginas/reservedlist/*.json`)
    # e não no HTML: ler só a casca era ler a página onde o selo não está.
    rl_dir = _TMP / "rl"
    rl_dir.mkdir(exist_ok=True)
    rl_out = rl_dir / "reservedlist.html"
    reservedlist.build(con, rl_out)
    partes = sorted((rl_dir / "data" / "paginas" / "reservedlist").glob("*.json"))
    assert partes, "a Reserved List não escreveu partes nenhumas"
    rl = rl_out.read_text(encoding="utf-8") + "".join(
        p.read_text(encoding="utf-8") for p in partes)
    assert not palavras(rl), palavras(rl)[:5]
    # O selo e a caixa — os ELEMENTOS, não os nomes das classes, que vivem no
    # CSS e não se apagam (é o mesmo ficheiro nos dois estados).
    assert '<span class="sellbadge">' not in rl, "o selo VENDER ficou"
    assert 'class="sellbox"' not in rl, "a caixa «A vender» ficou"
    assert "Reserved List" in rl, "a página ficou vazia"
    # O que NÃO se perde: «não joga em formato nenhum» é um facto sobre a
    # carta e é metade da razão por que esta página existe.
    assert "não joga em formato nenhum" in rl
    print("desligado: nem uma palavra de venda, nem um botao orfao, em lado nenhum")


# ---------------------------------------------------------------------------
# 3. Ligado: volta tudo
# ---------------------------------------------------------------------------
def caso_ligado_volta_tudo_como_estava():
    liga(True)
    assert venda.mostrar() is True
    con = base()
    rep = loadout.report(con)

    nav = shell.barra("index.html")
    assert 'href="deckboxes.html#vender"' in nav
    assert ">Vender<" in nav

    d = deckboxes.payload(con, rep, editable=True, token="t")
    assert d["venda"] and d["venda"]["normal"]["linhas"], "a aba Vender veio vazia"
    assert d["venda"]["saida"]["csv"], "o bloco Saída veio sem CSV"

    pag = deckboxes.html_page(con, rep=rep, editable=True, token="t")
    abas = _abas_desenhadas(con, True)
    if abas is not None:
        v = abas["vender"]
        assert "data-vend=" in v, "voltou a aba mas sem o botão «vendida»"
        assert "v-saida" in v, "voltou a aba mas sem o bloco Saída"
        assert palavras(v), "a aba Vender não fala de venda"
    else:
        assert "vistaVender" in pag

    out = _TMP / "index-on.html"
    inicio.build(con, out, rep=rep)
    idx = out.read_text(encoding="utf-8")
    assert "Para vender" in idx and "#vender" in idx

    rl_out = _TMP / "reservedlist-on.html"
    reservedlist.build(con, rl_out)
    rl = rl_out.read_text(encoding="utf-8")
    # Uma das duas: «A vender — N cartas» (sellbox) ou «nada a vender»
    # (sellnote). A caixa volta a falar de venda seja qual for a resposta.
    assert "sellbox" in rl or "sellnote" in rl, "a caixa da RL não voltou"
    assert palavras(rl), "a Reserved List voltou sem falar de venda"
    liga(None)
    print("ligado: a aba, os botoes, o item da barra, o cartao e o selo voltam")


# ---------------------------------------------------------------------------
# 4. Os endpoints de escrita
# ---------------------------------------------------------------------------
def caso_os_endpoints_de_escrita_recusam_se_em_condicoes():
    """Uma página aberta no telemóvel antes de hoje ainda pode mandar estes dois
    pedidos. A resposta tem de ser 409 com a razão em português — e, sobretudo,
    **sem tocar em nada**: o `/api/vender` é o botão que APAGA cartas da base."""
    liga(None)
    con = base()
    antes = con.execute("SELECT COUNT(*) c, SUM(quantity) q FROM copies").fetchone()
    # O «vendida», com uma chave que EXISTE mesmo na lista de hoje: assim o que
    # trava o pedido é o interruptor e não a chave não bater.
    rep = loadout.report(con)
    chave = loadout.chave_venda(rep["venda"][0])
    try:
        webapp.Handler._vender(object.__new__(webapp.Handler),
                               {"linha": chave, "q": 1})
        raise AssertionError("o «vendida» gravou com a venda desligada")
    except webapp.VendaDesligada as e:
        assert "venda.mostrar" in str(e), str(e)
    # É `ValueError`, logo o `do_POST` traduz num 409 com a mensagem (e não
    # num 500 com o nome de uma excepção que ele não percebe).
    assert issubclass(webapp.VendaDesligada, ValueError)
    assert not issubclass(webapp.VendaDesligada, webapp.SemLista)

    depois = con.execute("SELECT COUNT(*) c, SUM(quantity) q FROM copies").fetchone()
    assert (antes["c"], antes["q"]) == (depois["c"], depois["q"]), \
        "a recusa mexeu na colecção"

    # E o «gravar em data/»: a mesma recusa, e nenhum ficheiro escrito.
    pasta = Path(tempfile.mkdtemp())
    try:
        webapp._exige_venda()
        raise AssertionError("o `_exige_venda` deixou passar")
    except webapp.VendaDesligada:
        pass
    assert not list(pasta.iterdir())
    # Com o interruptor ligado o mesmo caminho deixa passar.
    liga(True)
    webapp._exige_venda()
    liga(None)
    print("os dois endpoints recusam com 409 e a razao, sem tocar em nada")


# ---------------------------------------------------------------------------
# 5. O motor não muda
# ---------------------------------------------------------------------------
def caso_o_motor_continua_a_calcular_as_sete_saidas():
    """O interruptor é sobre a VISTA. Se mexesse no motor, a regra dos 5 % da
    Reserved List — que é quem decide se uma carta que não se volta a imprimir
    vai à venda — passava a depender de uma preferência de apresentação."""
    con = base()
    SAIDAS = ("venda", "venda_rl", "rl_segurar", "rl_sem_historico",
              "guardar", "reservadas", "retidos")

    def medir():
        r = loadout.report(con)
        return {"custo": r["custo_total"], "comprar": r["comprar_total"],
                "arrumar": r["arrumacao"]["copias"],
                **{s: (len(r[s]), round(sum(x["total"] or 0 for x in r[s]), 2))
                   for s in SAIDAS}}

    liga(None)
    off = medir()
    liga(True)
    on = medir()
    liga(None)
    assert off == on, (off, on)
    # E há mesmo saídas com linhas — senão isto comparava dois vazios.
    assert off["venda"][0] > 0, off

    # A SAÍDA para o Cardmarket também continua a produzir-se a pedido.
    r = venda.relatorio(con, loadout.report(con))
    assert r["linhas"] and r["csv"].count("\n") > 1, "o CSV de stock deixou de sair"
    print("as sete saidas e a exportacao sao iguais com o interruptor nos dois estados")


# ---------------------------------------------------------------------------
# 5b. A revalidação não perde cópias pelo caminho
# ---------------------------------------------------------------------------
def caso_a_revalidacao_nao_perde_as_copias_da_venda():
    """A campanha é fotografar a colecção INTEIRA. Esconder só o grupo «Venda»
    levava com ele as cópias que lá estavam — sem uma linha a dizer para onde
    foram. Elas caem no sítio onde ESTÃO (Caixa RL ou Coleção), e a soma dos
    grupos continua a ser a colecção."""
    from mtgvault import revalidacao                        # noqa: PLC0415
    con = base()

    def grupos():
        rep = loadout.report(con)
        p = revalidacao.progresso(con, rep)
        soma = (sum(c["q"] for c in p["caixas"]) + p["venda"]["q"]
                + p["rl"]["q"] + p["resto"]["q"])
        return p, soma

    liga(True, revalidacao=True)
    on, soma_on = grupos()
    assert soma_on == on["total"]["q"], (soma_on, on["total"]["q"])
    assert on["venda"]["q"] > 0, "sem cópias na venda isto não provava nada"

    liga(None, revalidacao=True)
    off, soma_off = grupos()
    assert off["venda"]["q"] == 0, "o grupo «Venda» ficou com cópias"
    assert soma_off == off["total"]["q"] == on["total"]["q"], \
        "a campanha perdeu cópias pelo caminho"
    # E as que lá estavam apareceram noutro lado — não evaporaram.
    fora_on = on["rl"]["q"] + on["resto"]["q"]
    fora_off = off["rl"]["q"] + off["resto"]["q"]
    assert fora_off == fora_on + on["venda"]["q"], (fora_on, fora_off)
    liga(None)
    print("a revalidacao continua a ver a coleccao inteira: nada se perde")


# ---------------------------------------------------------------------------
# 6. O daily
# ---------------------------------------------------------------------------
def caso_o_daily_salta_o_passo_e_diz_porque():
    liga(None)
    con = base()
    pasta = Path(tempfile.mkdtemp())
    stock = pasta / venda.FICHEIRO_STOCK
    estante = pasta / venda.FICHEIRO_ESTANTE
    stock.write_text("a lista de ontem\n", encoding="utf-8")
    estante.write_text("a estante de ontem\n", encoding="utf-8")
    antes = (stock.read_text(encoding="utf-8"), estante.read_text(encoding="utf-8"))

    msg = daily.venda_export(con)
    assert msg.startswith("saltado:"), msg
    assert "venda.mostrar" in msg, "o log não diz porque é que saltou"
    assert venda.FICHEIRO_STOCK in msg and "ficam como estão" in msg
    # Nada foi tocado: nem apagado, nem reescrito.
    assert stock.is_file() and estante.is_file()
    assert (stock.read_text(encoding="utf-8"),
            estante.read_text(encoding="utf-8")) == antes

    # E ligado, o mesmo passo escreve mesmo (senão isto passava sempre).
    liga(True)
    msg2 = daily.venda_export(con)
    liga(None)
    assert not msg2.startswith("saltado:") and "cópias" in msg2, msg2
    # O `daily` chama esta função, e não uma cópia do corpo dela.
    fonte = (RAIZ / "daily.py").read_text(encoding="utf-8")
    assert 'venda-export", lambda: venda_export(' in fonte, \
        "o passo do daily deixou de passar por `venda_export`"
    print("o daily salta o passo, diz porque, e nao mexe nos ficheiros de ontem")


# ---------------------------------------------------------------------------
# 7. A pergunta vive num sítio só
# ---------------------------------------------------------------------------
def caso_o_interruptor_vive_num_sitio_so():
    """Oito superfícies fazem a mesma pergunta. A segunda que a respondesse por
    si própria deixava um item da barra a apontar para uma aba que já não
    existe — é a lição do `e_foil`, do `vistoId` e do `precos.sql`."""
    # O que se procura é quem vá ao CONFIG buscar a chave — não quem leia o
    # `{"mostrar": …}` que o `gravar_mostrar` devolve (o CLI faz isso, e está
    # certo). Por isso a linha tem de trazer as duas coisas: o sítio onde a
    # chave vive e o nome dela.
    CONFIG = re.compile(r'\bcfg\b|config\(|regras_venda\(|\[\s*["\']venda["\']\s*\]'
                        r'|get\(\s*["\']venda["\']')
    achados = []
    for f in list(RAIZ.glob("*.py")) + list((RAIZ / "mtgvault").glob("*.py")):
        if f.name == "venda.py":
            continue                 # é o dono da chave
        for n, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            nu = linha.split("#")[0]
            if not re.search(r'["\']mostrar["\']', nu) or not CONFIG.search(nu):
                continue
            achados.append(f"{f.name}:{n}: {linha.strip()}")
    assert not achados, ("alguém voltou a ler a chave à mão", achados)
    # E a prova de que o varrimento apanha mesmo alguma coisa: a linha que ele
    # procuraria existe, e é assim que se escreve.
    assert CONFIG.search('b = cfg.get("venda")') and \
        re.search(r'["\']mostrar["\']', 'b.get("mostrar")')
    # E a omissão é mesmo DESLIGADO — é a decisão de 2026-09-25.
    assert venda.MOSTRAR_OMISSAO is False
    liga(None)
    assert venda.mostrar() is False
    # O config do repositório diz o mesmo, por escrito.
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    assert cfg["venda"]["mostrar"] is False, cfg["venda"]
    assert "_mostrar" in cfg["venda"], "o config não explica a chave"
    print("a pergunta vive num sitio so, e a omissao e desligado")


# ---------------------------------------------------------------------------
# 8. Ligar e desligar pelo config
# ---------------------------------------------------------------------------
def caso_gravar_mostrar_liga_e_desliga():
    p = _TMP / "cfg-troca.json"
    p.write_text(json.dumps({"venda": {"rl_janela_dias": 90}}), encoding="utf-8")
    r = venda.gravar_mostrar(True, path=p)
    assert r == {"antes": False, "mostrar": True, "mudou": True}, r
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["venda"]["mostrar"] is True
    # E não deitou fora os parâmetros da regra da RL que vivem no mesmo bloco.
    assert d["venda"]["rl_janela_dias"] == 90
    assert venda.mostrar(d) is True
    r2 = venda.gravar_mostrar(False, path=p)
    assert r2["mudou"] is True and r2["antes"] is True
    assert venda.mostrar(json.loads(p.read_text(encoding="utf-8"))) is False
    # Num config sem bloco `venda` nenhum, cria-o.
    p2 = _TMP / "cfg-vazio.json"
    p2.write_text("{}", encoding="utf-8")
    venda.gravar_mostrar(True, path=p2)
    assert json.loads(p2.read_text(encoding="utf-8"))["venda"]["mostrar"] is True
    sources._CFG_CACHE.clear()
    print("gravar_mostrar liga e desliga sem estragar o resto do bloco venda")


CASOS = [caso_desligado_nao_sobra_venda_no_que_ele_ve,
         caso_ligado_volta_tudo_como_estava,
         caso_os_endpoints_de_escrita_recusam_se_em_condicoes,
         caso_o_motor_continua_a_calcular_as_sete_saidas,
         caso_a_revalidacao_nao_perde_as_copias_da_venda,
         caso_o_daily_salta_o_passo_e_diz_porque,
         caso_o_interruptor_vive_num_sitio_so,
         caso_gravar_mostrar_liga_e_desliga]


def run():
    for fn in CASOS:
        fn()
    for cm in _ABERTAS:
        cm.__exit__(None, None, None)


if __name__ == "__main__":
    run()
