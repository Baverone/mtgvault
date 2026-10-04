"""NUNCA PERDER UM TORNEIO DE PAPEL GRANDE (André, 2026-10-04, à letra).

*"o mtgtop8 acaba por publicar esses torneios"* — e tinha razão: publica. O que
não os apanhava era a recolha. O `harvest` lia os `max_events` PRIMEIROS ids do
índice e **nunca voltava atrás**; em Modern entram várias ligas e challenges de
MTGO por dia, por isso um Regional Championship publicado hoje ficava fora para
sempre se oito eventos mais novos aparecessem nas horas seguintes.

E havia um desperdício que o agravava: a liga era saltada **depois** de se pedir a
página do evento, logo cada liga gastava um dos lugares **e** um pedido. O índice
do mtgtop8 traz os NOMES ao lado dos ids e o `parse_event_ids` deitava-os fora —
o mesmo padrão do comandante (01/10) e do nome do arquétipo (02/10).

Cada caso aqui CHUMBA se a funcionalidade for retirada (os alvos estão em
`tests/_chumba_papel.py`). O que se tranca:

  1. o índice dá NOME e DATA, e não só o id — lido de um trecho REAL da página;
  2. uma LIGA salta-se **sem se pedir a página do evento**;
  3. um evento com «Regional Championship» no nome é recolhido mesmo estando em
     20.º lugar no índice;
  4. um evento JÁ PROCESSADO não se pede outra vez (a memória `mtgtop8_eventos`,
     nos TRÊS sítios);
  5. o TECTO de listas é maior num torneio grande — e só quando a página do
     evento confirma que ele é grande;
  6. a semente recupera as listas que faltam a um torneio grande que já está na
     base, **uma vez** e não todas as noites;
  7. o AVISO dispara uma vez por torneio e nunca levanta.

Sem rede: o HTML do índice é um trecho capturado de
`https://mtgtop8.com/format?f=MO` (2026-10-04) e os pedidos são substituídos por
um `_get` de mentira que CONTA as chamadas — é a contagem que prova o ponto 2.
Fixa `MTGVAULT_HOME` **e** `MTGVAULT_DB` (ver `tests/_bateria.py`).
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
    # Espelha o `colecao_config.json` a sério no que isto precisa: o `_default`
    # sem ligas e a excepção do Duel Commander, que as conta (André, 2026-09-07).
    # O `_default` do config GANHA ao `DEFAULT_METAGAME_BY_FORMAT` do código, por
    # isso sem esta segunda chave o Duel Commander ficava sem ligas aqui.
    "metagame_fontes": {
        "_default": {"tiers": ["Challenge", "Presencial", "Qualifier"],
                     "min_jogadores_presencial": 64, "ligas": False},
        "duel-commander": {"tiers": ["Challenge", "Presencial", "outro"],
                           "min_jogadores_presencial": 0, "ligas": True},
    },
}
CFG_PATH = _TMP / "cfg.json"
CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CFG_PATH)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")

from mtgvault import db, mtgtop8, sources  # noqa: E402

_ABERTAS = []

# ---------------------------------------------------------------------------
# O TRECHO REAL do índice (mtgtop8.com/format?f=MO, 04/10/2026). Três linhas da
# tabela «LAST 20 EVENTS» — um evento de PAPEL com loja, uma liga de MTGO e uma
# Challenge com duas estrelas —, a paginação, e um link `event?e=` dos «RELATED
# LINKS» que o parser NÃO pode apanhar: na página real há 375 `event?e=` e só 20
# são eventos do índice (os outros vêm do METAGAME BREAKDOWN e dos links do fim).
# ---------------------------------------------------------------------------
INDICE_REAL = """
		<div class=w_title align=center>LAST 20 EVENTS<div class=c_tl></div></div>
		<table border=0 class=Stable width=98% align=center>
		<tr class=hover_tr>
		  <td width=5% align=center><img src=/graph/online/paper.png height=17 title="Paper"></td>
		  <td width=70% class=S14><a href=event?e=91582&f=MO>Win-A-Box</a> @ <a class=und href=event?e=91582&f=MO>Infinity Hobbies (Las Pi&ntilde;as, Philippines)</a> <span class=new>NEW</span></td>
		  <td width=13% align=center><img src=/graph/star.png></td>
		  <td align=right width=12% class=S12>03/10/26</td>
		</tr>
		<tr class=hover_tr>
		  <td width=5% align=center><img src=/graph/online/mtgo.png height=14 title="MTG Online"></td>
		  <td width=70% class=S14><a href=event?e=91570&f=MO>MTGO League</a> <span class=new>NEW</span></td>
		  <td width=13% align=center><img src=/graph/star.png></td>
		  <td align=right width=12% class=S12>02/10/26</td>
		</tr>
		<tr class=hover_tr>
		  <td width=5% align=center><img src=/graph/online/mtgo.png height=14 title="MTG Online"></td>
		  <td width=70% class=S14><a href=event?e=91569&f=MO>MTGO Challenge 64</a></td>
		  <td width=13% align=center><img src=/graph/star.png><img src=/graph/star.png></td>
		  <td align=right width=12% class=S12>01/10/26</td>
		</tr>
		</table>
      <div style="display:flex;"><div class=Nav_PN_no>Prev</div><div class=Nav_cur>1</div><div class=Nav_norm><a href=?f=MO&meta=54&cp=2>2</a></div><div class=Nav_norm><a href=?f=MO&meta=54&cp=3>3</a></div><div class=Nav_norm><a href=?f=MO&meta=54&cp=2>Next</a></div></div>
	<div class=w_title align=center>RELATED LINKS</div>
	<div align=center><div class=S14><a href=event?e=91369&f=MO>The Decks to Beat - September '26</a></div></div>
"""


def _linha(eid: int, nome: str, dia: str, *, online=False, loja=None, estrelas=1) -> str:
    """Uma linha do índice na forma REAL (ver `INDICE_REAL`)."""
    icone = "mtgo.png height=14 title=\"MTG Online\"" if online else \
        "paper.png height=17 title=\"Paper\""
    alvo = f"<a href=event?e={eid}&f=MO>{nome}</a>"
    if loja:
        alvo += f" @ <a class=und href=event?e={eid}&f=MO>{loja}</a>"
    return (f"\t\t<tr class=hover_tr>\n"
            f"\t\t  <td width=5% align=center><img src=/graph/online/{icone}></td>\n"
            f"\t\t  <td width=70% class=S14>{alvo}</td>\n"
            f"\t\t  <td width=13% align=center>"
            + "<img src=/graph/star.png>" * estrelas + "</td>\n"
            f"\t\t  <td align=right width=12% class=S12>{dia}</td>\n"
            f"\t\t</tr>\n")


def _indice(linhas: list[str], paginas: int = 1) -> str:
    nav = "".join(f"<div class=Nav_norm><a href=?f=MO&cp={n}>{n}</a></div>"
                  for n in range(2, paginas + 1))
    return ("<div class=w_title align=center>LAST 20 EVENTS</div><table>"
            + "".join(linhas) + "</table><div>" + nav + "</div>")


def _pagina_evento(eid: int, jogadores: int, n_decks: int,
                   nome="Modern event - Qualquer Coisa") -> str:
    """Uma página de evento com `n_decks` links de deck, na forma real."""
    corpo = "".join(
        f'<div class=hover_tr><div style="width:80px;">'
        f'<a href=?e={eid}&d={eid * 1000 + i}&f=MO><img src=/t.jpg></a></div>'
        f'<div class=S14><a href=?e={eid}&d={eid * 1000 + i}&f=MO>Deck {i}</a></div>'
        f'<div class=G11><a class=player href=search?player=J+{eid}-{i}>'
        f'J {eid}-{i}</a></div></div>'
        for i in range(1, n_decks + 1))
    return (f"<html><title>{nome} @ Qualquer Sitio</title>"
            f'<div style="margin-bottom:5px;">{jogadores} players - 12/09/26</div>'
            f"{corpo}</html>")


def _dec(deck_id: int) -> str:
    """Um `.dec` na forma real, DIFERENTE por deck.

    Tem de ser diferente: o `store_decklist` deduplica pelo `content_hash` (formato
    + cartas + dia + jogador), e com o mesmo `.dec` em todos os decks as listas do
    segundo evento desapareciam contra as do primeiro — a contagem de «novas»
    deixava de medir a recolha e passava a medir o dedup.
    """
    return (f"// deck {deck_id}\n4 [AVR] Griselbrand\n"
            f"2 [] Force of Will\n1 [] Carta {deck_id}\n")


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    return cm.__enter__()


class Rede:
    """Um `_get` de mentira que CONTA os pedidos. É a contagem que prova tudo."""

    def __init__(self, indices: dict[int, str], eventos: dict[int, str]):
        self.indices, self.eventos = indices, eventos
        self.pedidos: list[tuple[str, dict]] = []

    def get(self, path, **params):
        self.pedidos.append((path, params))
        if path == "/format":
            return self.indices[int(params.get("cp") or 1)]
        if path == "/event":
            return self.eventos[int(params["e"])]
        if path == "/dec":
            return _dec(int(params["d"]))
        raise AssertionError(f"pedido inesperado: {path} {params}")

    def eventos_pedidos(self) -> list[int]:
        return [int(p["e"]) for c, p in self.pedidos if c == "/event"]

    def decs_pedidos(self) -> int:
        return sum(1 for c, _ in self.pedidos if c == "/dec")


def _linhas_mem(con) -> list[dict]:
    """As linhas REAIS da memória, sem a marca da semente (`mtgtop8.MARCA_SEMEADO`,
    `event_id = 0`), que não é um evento. O `memoria_dos_eventos` nunca a vê porque
    filtra por formato; quem lê a tabela em cru tem de a descontar."""
    return [dict(r) for r in con.execute(
        "SELECT * FROM mtgtop8_eventos WHERE event_id > 0 ORDER BY event_id")]


def _com_rede(rede, fn):
    antigo = mtgtop8._get
    mtgtop8._get = rede.get
    try:
        return fn()
    finally:
        mtgtop8._get = antigo


# ===========================================================================
# 1. O ÍNDICE DÁ NOME E DATA
# ===========================================================================
def caso_o_indice_da_nome_e_data_e_nao_so_o_id():
    """O trecho REAL da página. O `parse_event_ids` dá 4 ids (3 eventos + o link
    dos «RELATED LINKS»); o `parse_event_rows` dá os 3 eventos, com nome, data,
    papel/online, loja e estrelas — a informação que a recolha deitava fora."""
    linhas = mtgtop8.parse_event_rows(INDICE_REAL)
    assert [li["id"] for li in linhas] == [91582, 91570, 91569], linhas
    assert [li["nome"] for li in linhas] == [
        "Win-A-Box", "MTGO League", "MTGO Challenge 64"], linhas
    assert [li["data"] for li in linhas] == [
        "2026-10-03", "2026-10-02", "2026-10-01"], linhas
    assert [li["online"] for li in linhas] == [False, True, True], linhas
    assert [li["estrelas"] for li in linhas] == [1, 1, 2], linhas
    # O `&ntilde;` vem desescapado e a loja é lida à parte do nome.
    assert linhas[0]["loja"] == "Infinity Hobbies (Las Piñas, Philippines)"
    assert linhas[1]["loja"] is None
    # O link dos RELATED LINKS não é um evento do índice: não tem data ao lado.
    assert 91369 not in [li["id"] for li in linhas]
    assert 91369 in mtgtop8.parse_event_ids(INDICE_REAL)
    # E a própria página diz quantas páginas o índice tem.
    assert mtgtop8.parse_paginas_indice(INDICE_REAL) == 3
    assert mtgtop8.parse_paginas_indice("<html>sem paginacao</html>") == 1
    print("o índice dá nome, data, papel/online, loja e estrelas — e a paginação")


def caso_o_nome_do_indice_da_o_mesmo_tier_que_a_pagina():
    """A liga passou a ser reconhecida pelo nome do ÍNDICE («MTGO League») e não
    pelo `<title>` da página do evento («Modern event - MTGO League»). Os dois têm
    de dar o mesmo `event_tier`, senão a recolha e a base discordam — o título é o
    nome do índice com um prefixo que não contém nenhuma das palavras-chave."""
    for curto, longo in (("MTGO League", "Modern event - MTGO League"),
                         ("MTGO Challenge 64", "Modern event - MTGO Challenge 64"),
                         ("Win-A-Box", "Modern event - Win-A-Box"),
                         ("Regional Championship",
                          "Modern event - Regional Championship"),
                         ("3City League (FRA) #1",
                          "Premodern event - 3City League (FRA) #1")):
        a = sources.event_tier("mtgtop8", curto)
        b = sources.event_tier("mtgtop8", longo)
        assert a == b, (curto, a, b)
    # E um «League» que não é do MTGO continua a ser papel — não se salta.
    assert sources.event_tier("mtgtop8", "3City League (FRA) #1") == "Presencial"
    print("o nome do índice e o título da página dão o mesmo tier")


# ===========================================================================
# 2. A LIGA SALTA-SE SEM UM PEDIDO
# ===========================================================================
def caso_a_liga_salta_sem_se_pedir_a_pagina_do_evento():
    """O ponto que paga a mudança. Antes: `_get("/event")` e só depois
    `if event_tier(...) == "League": continue` — um pedido e um lugar gastos por
    liga. Agora a liga nem entra nos candidatos."""
    linhas = [_linha(1, "MTGO League", "02/10/26", online=True),
              _linha(2, "MTGO Challenge 64", "01/10/26", online=True),
              _linha(3, "MTGO League", "01/10/26", online=True),
              _linha(4, "Win-A-Box", "30/09/26", loja="Loja")]
    rede = Rede({1: _indice(linhas)},
                {2: _pagina_evento(2, 64, 2), 4: _pagina_evento(4, 70, 2)})
    con = base()
    novas = _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=4, max_decks_per_event=2, paginas=1))
    assert rede.eventos_pedidos() == [2, 4], rede.eventos_pedidos()
    assert 1 not in rede.eventos_pedidos() and 3 not in rede.eventos_pedidos()
    assert novas == 4, novas
    # E o mesmo pela via directa, para o motivo ficar trancado sem a rede.
    cand, ligas = mtgtop8.candidatos_do_indice(
        mtgtop8.parse_event_rows(_indice(linhas)), "modern", 4)
    assert ligas == 2 and [li["id"] for li in cand] == [2, 4], (ligas, cand)
    print("as 2 ligas saltaram sem um único pedido à página do evento")


def caso_onde_as_ligas_contam_elas_nao_se_saltam():
    """Em Duel Commander as ligas CONTAM (André, 2026-09-07). O filtro novo tem de
    ler a mesma regra por formato que o antigo lia, e não uma sua."""
    linhas = mtgtop8.parse_event_rows(
        _indice([_linha(1, "MTGO League", "02/10/26", online=True)]))
    cand, ligas = mtgtop8.candidatos_do_indice(linhas, "duel-commander", 4)
    assert ligas == 0 and [li["id"] for li in cand] == [1], (ligas, cand)
    # E em Modern a mesma linha é saltada: a regra é a de sempre, por formato.
    cand, ligas = mtgtop8.candidatos_do_indice(linhas, "modern", 4)
    assert ligas == 1 and cand == [], (ligas, cand)
    print("em duel-commander a liga continua a entrar; em Modern não")


# ===========================================================================
# 3. O TORNEIO GRANDE ENTRA ESTEJA ONDE ESTIVER
# ===========================================================================
def caso_um_regional_championship_em_20o_lugar_e_recolhido():
    """O coração da ordem. Dezanove eventos à frente e o RC em 20.º: com
    `max_events=3`, a recolha antiga nunca o via."""
    linhas = [_linha(100 + i, f"MTGO Challenge {i}", "03/10/26", online=True)
              for i in range(1, 20)]
    linhas.append(_linha(999, "Regional Championship", "12/09/26", loja="Ghent"))
    eventos = {100 + i: _pagina_evento(100 + i, 64, 1) for i in range(1, 20)}
    eventos[999] = _pagina_evento(
        999, 1486, 64, nome="Modern event - Regional Championship")
    rede = Rede({1: _indice(linhas)}, eventos)
    con = base()
    _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=3, max_decks_per_event=2, paginas=1))
    pedidos = rede.eventos_pedidos()
    assert 999 in pedidos, f"o RC em 20.o lugar nao foi recolhido: {pedidos}"
    # E é o PRIMEIRO a ser aberto: um RC de há dez dias vale mais do que uma
    # Challenge de ontem.
    assert pedidos[0] == 999, pedidos
    # Só ele e os três do topo — não se abriu o índice todo.
    assert len(pedidos) == 4, pedidos
    guardadas = con.execute(
        "SELECT COUNT(*) c FROM decklists WHERE event_name LIKE '%Regional%'"
    ).fetchone()["c"]
    assert guardadas == 64, guardadas
    print("o RC em 20.º lugar entra primeiro, e com as 64 listas")


def caso_o_indice_le_mais_do_que_uma_pagina():
    """Sem a paginação, um evento grande da semana passada não está no índice de
    hoje. A paginação é real (`?f=MO&cp=2`) e dá 58 eventos em Modern."""
    p1 = _indice([_linha(1, "MTGO Challenge 64", "03/10/26", online=True)], paginas=3)
    p2 = _indice([_linha(2, "MTGO Challenge 32", "02/10/26", online=True)])
    p3 = _indice([_linha(3, "Regional Championship", "20/09/26", loja="X")])
    rede = Rede({1: p1, 2: p2, 3: p3},
                {1: _pagina_evento(1, 64, 1), 2: _pagina_evento(2, 64, 1),
                 3: _pagina_evento(3, 500, 1, nome="Modern event - Regional Championship")})
    con = base()
    _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=2, max_decks_per_event=1))
    assert 3 in rede.eventos_pedidos(), rede.eventos_pedidos()
    assert [c for c, _ in rede.pedidos].count("/format") == 3
    # E não se pedem páginas que a página 1 não declara.
    rede2 = Rede({1: _indice([_linha(9, "Win-A-Box", "03/10/26", loja="L")])},
                 {9: _pagina_evento(9, 70, 1)})
    con2 = base()
    _com_rede(rede2, lambda: mtgtop8.harvest(
        con2, "modern", max_events=2, max_decks_per_event=1, paginas=3))
    assert [c for c, _ in rede2.pedidos].count("/format") == 1, rede2.pedidos
    print("o índice lê 3 páginas — e só as que existem")


def caso_a_pergunta_do_torneio_grande_vive_num_sitio_so():
    """Os padrões saíram da base dele (medidos a 04/10) e a pergunta é UMA
    (`e_grande`): o filtro da recolha, o tecto de listas e o aviso do daily
    respondem-lhe todos pelo mesmo sítio. Dois sítios discordavam em silêncio —
    é a lição do `event_tier`, do `e_foil` e do `precos.sql()`."""
    for nome in ("Modern event - Regional Championship",
                 "Regional Championship",
                 "Modern event - Magic Spotlight: The Hobbit",
                 "Premodern event - Czech Nationals 2026",
                 "Standard event - Champions Cup Premium Qualifier",
                 "Modern event - MTGO RC Qualifier",
                 "Legacy event - RC Hangzhou Side Event",
                 "Modern event - $uper $unday ReCQ 10:00am",
                 "Premodern event - European Championship 2026",
                 "Pro Tour Aetherdrift", "Grand Prix Lisbon",
                 "Eternal Weekend Europe", "The Last Sun 2026"):
        assert mtgtop8.e_grande(nome), nome
    for nome in ("MTGO League", "MTGO Challenge 64", "Win-A-Box",
                 "4ª Etapa CLM", "Mont Weekly Event", "Monsters",
                 "Arcanis Cup", "Circuit de Lyon", "Marché aux Cartes",
                 "3City League (FRA) #1", ""):
        assert not mtgtop8.e_grande(nome), nome
    # Os curtos são REGEX por isto: «Arc», «Circuit» e «Marché» têm «rc» dentro.
    assert not mtgtop8.padroes_estragados, mtgtop8.padroes_estragados
    # E um padrão que não compile não mata a recolha: vale como texto literal.
    assert mtgtop8.e_grande("qualquer [coisa", cfg={"mtgtop8": {
        "grandes": {"padroes": ["[coisa"]}}})
    assert "[coisa" in mtgtop8.padroes_estragados
    mtgtop8.padroes_estragados.clear()
    print("a pergunta «é um torneio grande?» vive num sítio só, com os padrões medidos")


def caso_sem_padroes_a_recolha_volta_ao_que_era():
    """Esvaziar `grandes.padroes` é o interruptor — como o `venda.mostrar` e o
    `cartas_vigiadas`. Sem padrões, nenhum evento salta a fila no índice.

    ACTUALIZADO A 2026-10-04 AO FIM DO DIA: desde que o tecto passou a depender
    também do TAMANHO DO CAMPO (`mtgtop8.ESCALA_TECTO`), são **duas** regras e
    **dois** interruptores — e é melhor que o teste o diga do que esconder-se numa
    asserção que já não vale. Esvaziar os padrões desliga a fila do índice e o ramo
    do nome; para o tecto voltar aos 16 fixos é preciso esvaziar também a
    `escala_jogadores`. É o que o `_mtgtop8_escala` do config explica."""
    cfg = {"mtgtop8": {"paginas_indice": 1, "grandes": {"padroes": []}}}
    linhas = [_linha(1, "MTGO Challenge 64", "03/10/26", online=True),
              _linha(2, "Regional Championship", "12/09/26", loja="X")]
    cand, _ = mtgtop8.candidatos_do_indice(
        mtgtop8.parse_event_rows(_indice(linhas)), "modern", 1, cfg)
    assert [li["id"] for li in cand] == [1], cand
    nome = "Modern event - Regional Championship"
    assert mtgtop8.e_grande(nome, cfg) is False
    # Sem padrões, o ramo do NOME desliga-se — mas a escala pelo campo fica.
    assert mtgtop8.tecto_do_evento(False, 5000, 16, cfg, nome=nome) == 64
    # Com as DUAS chaves vazias, o tecto é o de sempre: 16, aconteça o que
    # acontecer. É este o interruptor completo.
    cfg0 = {"mtgtop8": {"paginas_indice": 1,
                        "grandes": {"padroes": [], "escala_jogadores": {}}}}
    assert mtgtop8.escala_do_tecto(5000, nome, cfg0) == 0
    # O `grande` sai sempre do `e_grande` (nunca se passa à mão), e com os padrões
    # vazios ele é falso — é por aí que o ramo do nome se desliga.
    assert mtgtop8.e_grande(nome, cfg0) is False
    assert mtgtop8.tecto_do_evento(
        mtgtop8.e_grande(nome, cfg0), 5000, 16, cfg0, nome=nome) == 16
    # Com os padrões de sempre, o mesmo nome dá 64 — é esta a diferença.
    assert mtgtop8.tecto_do_evento(mtgtop8.e_grande(nome), 5000, 16) == 64
    print("sem padrões o nome desliga-se; com as duas chaves vazias o tecto é o de sempre")


# ===========================================================================
# 4. A MEMÓRIA
# ===========================================================================
def caso_a_tabela_da_memoria_esta_nos_tres_sitios():
    """Coluna/tabela nova = `schema.sql` + `db._migrate()` + quem a escreve. E o
    ÍNDICE nasce no `_migrate`, nunca no `schema.sql` — esse corre inteiro antes
    e numa base já criada a coluna ainda não existe (a armadilha de 2026-09-09)."""
    con = base()
    cols = {r["name"] for r in con.execute("PRAGMA table_info(mtgtop8_eventos)")}
    assert cols == {"event_id", "format", "event_name", "event_date", "grande",
                    "players", "na_pagina", "tecto", "completo", "visto_em"}, cols
    # Numa base a que se APAGUE a tabela (é a base dele antes desta ordem), o
    # `_migrate` volta a criá-la e o `db.init` não rebenta.
    con.execute("DROP TABLE mtgtop8_eventos")
    con.commit()
    db.init(con)
    assert _linhas_mem(con) == []
    esquema = (RAIZ / "mtgvault" / "schema.sql").read_text(encoding="utf-8")
    assert "mtgtop8_eventos" in esquema, "falta no schema.sql"
    assert "mtgtop8_eventos" in (RAIZ / "mtgvault" / "db.py").read_text(
        encoding="utf-8"), "falta no db._migrate"
    print("a memória está nos três sítios e o índice no _migrate")


def caso_um_evento_ja_processado_nao_se_pede_outra_vez():
    """Sem isto, descer no índice custava um pedido por evento já feito, todas as
    noites — e era o que tornava caro ler 58 eventos em vez de 20."""
    linhas = [_linha(1, "MTGO Challenge 64", "03/10/26", online=True),
              _linha(2, "Win-A-Box", "02/10/26", loja="L")]
    eventos = {1: _pagina_evento(1, 64, 2), 2: _pagina_evento(2, 70, 2)}
    con = base()
    rede = Rede({1: _indice(linhas)}, eventos)
    _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=2, max_decks_per_event=2, paginas=1))
    assert sorted(rede.eventos_pedidos()) == [1, 2], rede.eventos_pedidos()
    # Segunda corrida: o índice pede-se (é como se sabe o que há de novo), as
    # páginas dos eventos NÃO.
    rede2 = Rede({1: _indice(linhas)}, eventos)
    _com_rede(rede2, lambda: mtgtop8.harvest(
        con, "modern", max_events=2, max_decks_per_event=2, paginas=1))
    assert rede2.eventos_pedidos() == [], rede2.eventos_pedidos()
    assert rede2.decs_pedidos() == 0, rede2.decs_pedidos()
    assert [c for c, _ in rede2.pedidos] == ["/format"], rede2.pedidos
    print("segunda corrida: 1 pedido (o índice) em vez de 1 + 2 + 4")


def caso_um_evento_todo_deduplicado_fica_na_mesma_na_memoria():
    """A razão por que a memória é uma TABELA e não a `decklists`.

    O mtgtop8 re-hospeda o mtgo.com, e o `store_decklist` descarta a cópia (o
    `mtgo` tem prioridade). Um evento cujas listas são TODAS deduplicadas não
    deixa uma única linha na `decklists` — logo não há donde o deduzir, nem a
    semente o apanha —, e sem a tabela era esse precisamente o evento que se
    voltava a pedir todas as noites. É o mesmo raciocínio do `arquetipo_fonte_de`
    (02/10) a dar outra resposta por os dados serem outros.
    """
    con = base()
    # A MESMA lista, já na base pelo mtgo.com: mesmo formato, dia, jogador e
    # cartas — é a definição de duplicado do `store_decklist`.
    assert sources.store_decklist(
        con, source="mtgo", source_key="m-1", fmt="modern",
        cards=[("main", "Griselbrand", 4), ("main", "Force of Will", 2),
               ("main", "Carta 5001", 1)],
        event_name="Modern Challenge 64", event_date="2026-09-12",
        player="J 5-1") is not None
    linhas = [_linha(5, "MTGO Challenge 64", "12/09/26", online=True)]
    eventos = {5: _pagina_evento(5, 64, 1)}
    rede = Rede({1: _indice(linhas)}, eventos)
    novas = _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=1, paginas=1))
    assert novas == 0, f"a lista devia ter sido deduplicada, e deu {novas} novas"
    assert con.execute("SELECT COUNT(*) c FROM decklists WHERE source='mtgtop8'"
                       ).fetchone()["c"] == 0, "nao ficou linha nenhuma na decklists"
    # ... e ainda assim o evento está lembrado.
    assert 5 in mtgtop8.memoria_dos_eventos(con, "modern")
    rede2 = Rede({1: _indice(linhas)}, eventos)
    _com_rede(rede2, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=1, paginas=1))
    assert rede2.eventos_pedidos() == [], rede2.eventos_pedidos()
    print("um evento todo deduplicado fica lembrado — não deixa linha na decklists")


def caso_um_dec_que_falha_nao_marca_o_evento_como_feito():
    """A regressão que a memória quase introduziu, e que o código antigo não tinha.

    O antigo não lembrava nada e por isso voltava a pedir, na corrida seguinte, os
    `.dec` que faltassem (o crivo é por deck, contra a `decklists`). Registar o
    evento ANTES do ciclo dos `.dec` fazia com que uma falha de rede num único
    `.dec` deixasse essa lista a faltar **para sempre**. Um evento meio lido não
    se marca.

    O EVENTO TEM 30 JOGADORES DE PROPÓSITO (mudado de 70 a 2026-10-04 ao fim do
    dia). Com 70 passou a haver DOIS mecanismos a recuperá-lo — a não-marcação,
    que é o que este caso tranca, e a escala pelo tamanho do campo, que desde esse
    dia dá 32 de tecto a um evento de 64+ jogadores e o põe na fila de revisitas.
    Com dois caminhos, o caso passava mesmo com a não-marcação desligada e deixava
    de trancar nada (apanhado pelo `_chumba_papel semente_vazia`). Abaixo dos 64 a
    escala não se aplica, e o caso volta a medir uma coisa só."""
    import requests
    linhas = [_linha(7, "Win-A-Box", "03/10/26", loja="L")]
    eventos = {7: _pagina_evento(7, 30, 3)}

    class SoUmDec(Rede):
        def __init__(self, *a, mau):
            super().__init__(*a)
            self.mau = mau

        def get(self, path, **params):
            if path == "/dec" and int(params["d"]) == self.mau:
                self.pedidos.append((path, params))
                raise requests.RequestException("o .dec nao veio")
            return super().get(path, **params)

    con = base()
    rede = SoUmDec({1: _indice(linhas)}, eventos, mau=7002)
    novas = _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=3, paginas=1))
    assert novas == 2, novas
    assert _linhas_mem(con) == [], \
        "o evento NAO pode ficar marcado com uma lista a faltar"
    # A corrida seguinte, com a rede boa, traz a que faltou.
    rede2 = Rede({1: _indice(linhas)}, eventos)
    novas2 = _com_rede(rede2, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=3, paginas=1))
    assert novas2 == 1, novas2
    assert rede2.decs_pedidos() == 1, "so se volta a pedir o que faltava"
    assert _linhas_mem(con)[0]["completo"] == 1
    print("um .dec que falha não marca o evento — a corrida seguinte traz a lista")


def caso_um_evento_que_falha_nao_se_marca_como_feito():
    """Perder um RC para sempre por uma falha de rede de um segundo era o preço de
    simplificar aqui — é a regra do `backfill_archetype_names`."""
    import requests
    linhas = [_linha(1, "Regional Championship", "12/09/26", loja="X")]

    class RedeMa(Rede):
        def get(self, path, **params):
            if path == "/event":
                self.pedidos.append((path, params))
                raise requests.RequestException("rede em baixo")
            return super().get(path, **params)

    con = base()
    rede = RedeMa({1: _indice(linhas)}, {})
    _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=2, paginas=1))
    assert _linhas_mem(con) == []
    # A corrida seguinte volta a tentar.
    rede2 = Rede({1: _indice(linhas)},
                 {1: _pagina_evento(1, 1486, 3,
                                    nome="Modern event - Regional Championship")})
    _com_rede(rede2, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=2, paginas=1))
    assert rede2.eventos_pedidos() == [1], rede2.eventos_pedidos()
    print("um evento que falha não se marca — e volta a ser tentado")


# ===========================================================================
# 5. O TECTO DE LISTAS
# ===========================================================================
def caso_o_tecto_de_listas_e_maior_num_torneio_grande():
    """**64 não é um número à sorte: é o que a página serve.** Medido a 04/10 — o
    RC de Modern (1 486 jogadores) tem 64 links de deck e a base dele tinha 16."""
    linhas = [_linha(1, "Regional Championship", "12/09/26", loja="Ghent")]
    rede = Rede({1: _indice(linhas)},
                {1: _pagina_evento(1, 1486, 64,
                                   nome="Modern event - Regional Championship")})
    con = base()
    novas = _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=16, paginas=1))
    assert novas == 64, f"o tecto cortou em {novas} (eram 16 antes de 04/10)"
    linha = _linhas_mem(con)[0]
    assert linha["tecto"] == 64 and linha["na_pagina"] == 64
    assert linha["completo"] == 1 and linha["grande"] == 1
    assert linha["players"] == 1486
    print("o torneio grande dá 64 listas e não 16")


def caso_o_tecto_alto_exige_que_a_pagina_confirme_o_tamanho():
    """O tecto pendurado só no NOME punha 64 pedidos `.dec` num «Store
    Championship» de 25 jogadores — e um presencial com menos de 64 jogadores nem
    conta para o metagame. O nº de jogadores vem da página do evento, que já foi
    pedida ANTES do primeiro `.dec`: a decisão não custa um pedido.

    ASSERÇÃO CORRIGIDA A 2026-10-04 AO FIM DO DIA, e não mascarada. Escrita de
    manhã, esta função afirmava que um evento que o NOME não reconhece fica com 16
    listas, mesmo com 1 486 jogadores — e era isso que estava mal: dos 9 eventos
    truncados da base com 64+ jogadores, 4 têm nomes que nenhum padrão reconhece.
    Hoje o tecto é o MÁXIMO do tecto normal, da escala pelo tamanho do campo e do
    ramo do nome (ver `mtgtop8.ESCALA_TECTO`). O que esta função continua a
    trancar, e é o que ela existe para trancar, é a outra metade: **um nome grande
    com o campo pequeno não sobe de tecto**."""
    assert mtgtop8.tecto_do_evento(True, 1486, 16) == 64
    assert mtgtop8.tecto_do_evento(True, 64, 16) == 64
    assert mtgtop8.tecto_do_evento(True, 25, 16) == 16, "um store de 25 nao e grande"
    assert mtgtop8.tecto_do_evento(True, None, 16) == 16, "sem contagem nao se assume"
    # Sem nome reconhecido, manda o TAMANHO DO CAMPO (regra de 04/10 ao fim do
    # dia): 1 486 jogadores valem 64 listas, 70 valem 32, 25 ficam nos 16.
    assert mtgtop8.tecto_do_evento(False, 1486, 16) == 64
    assert mtgtop8.tecto_do_evento(False, 70, 16) == 32
    assert mtgtop8.tecto_do_evento(False, 25, 16) == 16
    # Pela rede, com um evento de nome grande e 25 jogadores: 16 listas.
    linhas = [_linha(1, "Store Championship", "12/09/26", loja="Loja")]
    rede = Rede({1: _indice(linhas)},
                {1: _pagina_evento(1, 25, 40,
                                   nome="Modern event - Store Championship")})
    con = base()
    novas = _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=1, max_decks_per_event=16, paginas=1))
    assert novas == 16, novas
    assert rede.decs_pedidos() == 16, rede.decs_pedidos()
    print("o tecto alto só com a página a confirmar: 25 jogadores dão 16 listas")


def caso_um_grande_pequeno_nao_se_revisita_para_sempre():
    """O defeito que a primeira versão tinha: `por_fazer` decidia com o tecto
    OPTIMISTA (64, por o nome ser grande) e gravava o tecto REAL (16, por os
    jogadores serem poucos), logo `16 < 64` e o evento era pedido **todas as
    noites, para sempre**. Decide-se com os jogadores LEMBRADOS."""
    linhas = [_linha(1, "Store Championship", "12/09/26", loja="Loja")]
    eventos = {1: _pagina_evento(1, 25, 40, nome="Modern event - Store Championship")}
    con = base()
    for volta in (1, 2, 3):
        rede = Rede({1: _indice(linhas)}, eventos)
        _com_rede(rede, lambda: mtgtop8.harvest(
            con, "modern", max_events=1, max_decks_per_event=16, paginas=1))
        esperado = [1] if volta == 1 else []
        assert rede.eventos_pedidos() == esperado, (volta, rede.eventos_pedidos())
    # E a função directamente, que é onde a regra vive.
    assert mtgtop8.por_fazer(None, True, 16) is True
    assert mtgtop8.por_fazer({"completo": 1, "tecto": 16, "players": 1486},
                             True, 16) is False
    assert mtgtop8.por_fazer({"completo": 0, "tecto": 16, "players": 25},
                             True, 16) is False, "o pequeno nao se revisita"
    assert mtgtop8.por_fazer({"completo": 0, "tecto": 16, "players": 1486},
                             True, 16) is True, "o grande revisita-se uma vez"
    print("um «grande» pequeno não se revisita; um grande a sério revisita uma vez")


def caso_um_grande_fora_do_indice_e_recuperado():
    """O defeito que o ENSAIO de ponta a ponta apanhou, e o mais consequente.

    O `Modern event - Regional Championship` é de **12/09** e o índice de hoje
    cobre **20/09 a 03/10**: o evento que mais interessa recuperar **já não está no
    índice**. Com as revisitas escolhidas entre os candidatos do índice, as 48
    listas que lhe faltam nunca vinham — a primeira versão tinha-o escrito como se
    viessem. As revisitas lêem-se da MEMÓRIA.
    """
    con = base()
    # Semeado pela SEMENTE a sério: um RC de 12/09 com 2 das suas 64 listas na
    # base, como a recolha antiga as deixou.
    for d in (1, 2):
        sources.store_decklist(
            con, source="mtgtop8", source_key=str(90762_00 + d), fmt="modern",
            cards=[("main", f"Carta {d}", 1)],
            event_name="Modern event - Regional Championship",
            event_date="2026-09-12", player=f"j{d}", event_players=1486,
            url=f"{mtgtop8.BASE}/event?e=90762&d={90762_00 + d}&f=MO")
    assert mtgtop8.semear_memoria(con) == 1
    # O índice de HOJE não o traz — só eventos de Outubro.
    linhas = [_linha(91582, "Win-A-Box", "03/10/26", loja="L")]
    eventos = {91582: _pagina_evento(91582, 70, 2),
               90762: _pagina_evento(90762, 1486, 64,
                                     nome="Modern event - Regional Championship")}
    assert 90762 not in [li["id"] for li in
                         mtgtop8.parse_event_rows(_indice(linhas))]
    pend = mtgtop8.revisitas_pendentes(con, "modern", 16)
    assert [r["event_id"] for r in pend] == [90762], pend
    rede = Rede({1: _indice(linhas)}, eventos)
    _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=6, max_decks_per_event=16, paginas=1))
    assert 90762 in rede.eventos_pedidos(), rede.eventos_pedidos()
    assert con.execute(
        "SELECT COUNT(*) c FROM decklists WHERE event_name LIKE '%Regional%'"
    ).fetchone()["c"] == 66, "as 2 que ja ca estavam + as 64 da pagina"
    # Fica completo e não se volta lá.
    linha = [r for r in _linhas_mem(con) if r["event_id"] == 90762][0]
    assert linha["tecto"] == 64 and linha["completo"] == 1, linha
    assert mtgtop8.revisitas_pendentes(con, "modern", 16) == []
    print("um torneio grande FORA do índice é recuperado pela memória")


def caso_as_revisitas_tem_travao_por_corrida():
    """Semeada a base dele (401 eventos de mtgtop8), são **11** os que valem uma
    revisita — e fazê-los de uma vez eram **até 564 pedidos `.dec` numa noite**,
    num site pequeno e gratuito. Um por formato e por corrida, **pela ordem do nº
    de jogadores**: o RC de 1 486 entra na primeira noite, que é o que interessa
    para Ghent, e o backlog esgota-se sozinho. Os eventos NOVOS não levam travão —
    esses são o trabalho de sempre."""
    con = base()
    grandes = [(1, "Regional Championship", 1486), (2, "Magic Spotlight", 921),
               (3, "$uper $unday ReCQ", 344)]
    for eid, nome, jog in grandes:
        mtgtop8._registar_evento(con, eid, "modern",
                                 nome=f"Modern event - {nome}", data="2026-09-12",
                                 grande=True, players=jog, na_pagina=64,
                                 tecto=mtgtop8.TECTO_ANTIGO)
    con.commit()
    linhas = [_linha(eid, nome, "12/09/26", loja="X") for eid, nome, _ in grandes]
    # ... e um evento NOVO, que não conta para o travão.
    linhas.append(_linha(9, "Win-A-Box", "03/10/26", loja="L"))
    eventos = {eid: _pagina_evento(eid, jog, 64, nome=f"Modern event - {nome}")
               for eid, nome, jog in grandes}
    eventos[9] = _pagina_evento(9, 70, 2)
    for volta, esperado in ((1, [9, 1]), (2, [2]), (3, [3]), (4, [])):
        rede = Rede({1: _indice(linhas)}, eventos)
        _com_rede(rede, lambda: mtgtop8.harvest(
            con, "modern", max_events=4, max_decks_per_event=16, paginas=1))
        assert rede.eventos_pedidos() == esperado, (volta, rede.eventos_pedidos())
    # E o travão é configurável: a 3 faz os três de uma vez.
    con2 = base()
    for eid, nome, jog in grandes:
        mtgtop8._registar_evento(con2, eid, "modern",
                                 nome=f"Modern event - {nome}", data="2026-09-12",
                                 grande=True, players=jog, na_pagina=64,
                                 tecto=mtgtop8.TECTO_ANTIGO)
    con2.commit()
    rede = Rede({1: _indice(linhas)}, eventos)
    _com_rede(rede, lambda: mtgtop8.harvest(
        con2, "modern", max_events=4, max_decks_per_event=16, paginas=1,
        cfg={"mtgtop8": {"paginas_indice": 1, "revisitas_por_corrida": 3}}))
    assert rede.eventos_pedidos() == [9, 1, 2, 3], rede.eventos_pedidos()
    print("as revisitas são 1 por corrida, o maior primeiro — e o travão é config")


def caso_a_semente_recupera_as_listas_que_faltam_a_um_grande():
    """O RC de 1 486 jogadores está na base dele com 16 listas e a página tem 64.
    A semente marca-o com o TECTO ANTIGO e `completo = 0`, e por isso a primeira
    corrida volta lá **uma vez** e traz as 48 que faltavam — sem um passo à mão."""
    con = base()
    # Como se a recolha antiga tivesse passado: 2 listas de um evento grande.
    for d in (1, 2):
        sources.store_decklist(
            con, source="mtgtop8", source_key=str(1000 + d), fmt="modern",
            cards=[("main", "Force of Will", 1)],
            event_name="Modern event - Regional Championship",
            event_date="2026-09-12", player=f"j{d}", event_players=1486,
            url=f"{mtgtop8.BASE}/event?e=777&d={1000 + d}&f=MO")
    # ... e uma Challenge normal, que NÃO se deve revisitar.
    sources.store_decklist(
        con, source="mtgtop8", source_key="2001", fmt="modern",
        cards=[("main", "Force of Will", 1)],
        event_name="Modern event - MTGO Challenge 64", event_date="2026-09-12",
        player="jx", event_players=None,
        url=f"{mtgtop8.BASE}/event?e=778&d=2001&f=MO")
    n = mtgtop8.semear_memoria(con)
    assert n == 2, n
    assert mtgtop8.semear_memoria(con) == 0, "a semente corre uma vez só"
    mem = mtgtop8.memoria_dos_eventos(con, "modern")
    assert mem[777]["grande"] == 1 and mem[777]["tecto"] == mtgtop8.TECTO_ANTIGO
    assert mem[777]["players"] == 1486 and mem[777]["completo"] == 0
    assert mem[778]["grande"] == 0
    assert mtgtop8.por_fazer(mem[777], True, 16) is True, "o RC tem de ser revisitado"
    assert mtgtop8.por_fazer(mem[778], False, 16) is False, "a Challenge nao"
    # E pela rede: o RC volta a ser pedido, a Challenge não.
    linhas = [_linha(777, "Regional Championship", "12/09/26", loja="Ghent"),
              _linha(778, "MTGO Challenge 64", "12/09/26", online=True)]
    rede = Rede({1: _indice(linhas)},
                {777: _pagina_evento(777, 1486, 64,
                                     nome="Modern event - Regional Championship")})
    _com_rede(rede, lambda: mtgtop8.harvest(
        con, "modern", max_events=2, max_decks_per_event=16, paginas=1))
    assert rede.eventos_pedidos() == [777], rede.eventos_pedidos()
    total = con.execute(
        "SELECT COUNT(*) c FROM decklists WHERE event_name LIKE '%Regional%'"
    ).fetchone()["c"]
    assert total == 66, f"as 2 que ja ca estavam + 64 da pagina, dao {total}"
    # E não volta lá na corrida seguinte.
    rede2 = Rede({1: _indice(linhas)}, {})
    _com_rede(rede2, lambda: mtgtop8.harvest(
        con, "modern", max_events=2, max_decks_per_event=16, paginas=1))
    assert rede2.eventos_pedidos() == [], rede2.eventos_pedidos()
    print("a semente traz as 48 listas que faltavam ao RC, uma vez só")


# ===========================================================================
# 6. O AVISO
# ===========================================================================
def caso_o_aviso_dispara_uma_vez_e_diz_o_que_aconteceu():
    """Não se criou tarefa agendada nenhuma (ele pediu a 15/09 menos vigilância):
    é o toast que já existia (2026-09-26) e a linha do resumo diário. Um aviso por
    DIA e não um por formato — por isso lê-se da base, no fim dos seis harvest."""
    import daily
    con = base()
    hoje = "2026-10-04"
    assert mtgtop8.grandes_de_hoje(con, hoje) == []
    chamadas = []

    def falso_toast(titulo, texto):
        chamadas.append((titulo, texto))
        return "toast (balloon)"

    resumo = daily._papel_grande(con, toast=falso_toast, hoje=hoje)
    assert "nenhum" in resumo and not chamadas, resumo
    # Dois grandes de verdade e um «grande» pequeno, que não é notícia.
    for eid, nome, jog in ((1, "Modern event - Regional Championship", 1486),
                           (2, "Modern event - Magic Spotlight", 921),
                           (3, "Modern event - Store Championship", 25)):
        mtgtop8._registar_evento(con, eid, "modern", nome=nome, data="2026-09-12",
                                 grande=True, players=jog, na_pagina=64, tecto=64)
    con.commit()
    con.execute("UPDATE mtgtop8_eventos SET visto_em = ?", (hoje,))
    con.commit()
    novos = mtgtop8.grandes_de_hoje(con, hoje)
    assert [e["players"] for e in novos] == [1486, 921], novos
    resumo = daily._papel_grande(con, toast=falso_toast, hoje=hoje)
    assert len(chamadas) == 1, chamadas
    assert "Regional Championship" in chamadas[0][1]
    assert "Store Championship" not in chamadas[0][1]
    assert "toast (balloon)" in resumo and "2 novos" in resumo, resumo
    # Noutro dia não há notícia — o aviso não se repete.
    assert mtgtop8.grandes_de_hoje(con, "2026-10-05") == []
    print("o aviso dispara uma vez, só para os grandes a sério, e diz o que fez")


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
