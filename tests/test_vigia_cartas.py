"""A VIGIA DE CARTAS (André, 2026-09-26).

Ele comprou 4× «Kasmina, Enigma Sage» e 2× «Enter the Infinite» por causa de um
combo novo e quer saber quando aparecerem decklists com ele — *"vai conferindo"*.
A segunda peça, «Jace's Machinations», só sai a 02/10/2026: hoje não pode existir
uma lista com o combo, e o valor está em ele ser avisado no DIA em que a primeira
aparecer.

O que aqui se tranca — e as três primeiras são o pedido dele, à letra:
  1. uma decklist com a carta vigiada num evento de **LEAGUE** é apanhada pela
     vigia, e **continua a não contar para o metagame** (o filtro de tier de
     2026-09-07 fica ligado para todo o resto: a liga sem carta vigiada nem se
     guarda, e a vigiada não entra no `counting_sql`);
  2. o `prune_leagues` não apaga a lista vigiada — sem isto o passo da poda
     apagava-a na MESMA corrida em que ela entrou;
  3. uma lista **já vista não volta a avisar**, nem quando a deduplicação lhe
     muda o `decklist_id`;
  4. **sem cartas vigiadas nada muda**: o `store_decklist` recusa a liga como
     sempre, a poda apaga-a, o passo do daily diz que não tem nada a fazer e
     **não se escreve ficheiro de estado nenhum**;
  5. as faltas saem da BASE e a página di-lo (ele diz ter 4 Kasmina, a base tem
     0 — as cópias novas só entram com a foto);
  6. o bloco do `metagame.html` mostra as cartas vigiadas e o que apareceu.

Não toca na rede: as decklists são escritas à mão, como se tivessem vindo do
mtgo.com.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O config tem de estar em vigor ANTES de os módulos serem importados — é ele que
# diz o que está vigiado. Escreve-se um com as mesmas regras de metagame que vão
# no repositório, para o teste não passar a depender de ele não lhes mexer.
_TMP = Path(tempfile.mkdtemp())
REGRAS = {"metagame_fontes": {
    "_default": {"tiers": ["Challenge", "Showcase", "Presencial"],
                 "min_jogadores_presencial": 64, "ligas": False},
    "duel-commander": {"min_jogadores_presencial": 0, "ligas": True}}}
NOTA = "combo Jace/Kasmina, Reality Fracture sai 02/10/2026"
COM_VIGIA = dict(REGRAS, cartas_vigiadas=[
    {"carta": "Kasmina, Enigma Sage", "formatos": ["modern"], "nota": NOTA},
    {"carta": "Jace's Machinations", "formatos": ["modern"], "nota": NOTA}])
(_TMP / "com-vigia.json").write_text(json.dumps(COM_VIGIA), encoding="utf-8")
(_TMP / "sem-vigia.json").write_text(json.dumps(REGRAS), encoding="utf-8")

os.environ["MTGVAULT_CONFIG"] = str(_TMP / "com-vigia.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")     # ver tests/_bateria.py

from mtgvault import analysis, db, sources, vigia  # noqa: E402

KASMINA = "Kasmina, Enigma Sage"
JACE = "Jace's Machinations"

# A lista que ele está à espera. Duas cartas vigiadas na mesma lista, de
# propósito: são dois avistamentos e tem de ser UM toast.
COMBO = ([("main", KASMINA, 4), ("main", JACE, 4),
          ("main", "Enter the Infinite", 2), ("main", "Brainstorm", 4),
          ("main", "Island", 20)]
         + [("side", "Force of Negation", 3)])
# Uma liga qualquer, sem carta vigiada: esta continua a não se guardar.
BURN = [("main", "Lightning Bolt", 4), ("main", "Mountain", 20)]

LIGA = {"source": "mtgo", "fmt": "modern",
        "event_name": "Modern League 2026-10-03", "event_date": "2026-10-03"}
_ABERTAS = []


def com_config(nome):
    """Troca o `colecao_config.json` em vigor. O `sources` guarda-o em cache por
    caminho+mtime, por isso trocar de FICHEIRO basta."""
    os.environ["MTGVAULT_CONFIG"] = str(_TMP / nome)
    sources._CFG_CACHE.clear()


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
           set_code, set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, legalities, digital, reserved)
           VALUES ('id-kas','or-kas',?, 'stx','Strixhaven','60','en','rare',
                   'Legendary Planeswalker — Kasmina',4,'GU',?, '2021-04-23', ?, 0, 0)""",
        (KASMINA, json.dumps(["nonfoil", "foil"]), json.dumps({"modern": "legal"})))
    con.commit()
    return con


def guarda_combo(con, **kw):
    dados = dict(LIGA, source_key="liga-combo", cards=COMBO, player="jacespike",
                 placement="5-0",
                 url="https://www.mtgo.com/decklist/modern-league-2026-10-0399")
    dados.update(kw)
    return sources.store_decklist(con, **dados)


class Toast:
    """Um toast de mentira: conta as vezes que foi chamado e guarda o texto. É
    assim que se prova que o segundo dia não avisa outra vez, sem abrir uma
    janela no PC dele."""

    def __init__(self):
        self.chamadas = []

    def __call__(self, titulo, texto):
        self.chamadas.append((titulo, texto))
        return "toast (falso)"


# ---------------------------------------------------------------------------
def caso_a_vigia_apanha_um_5_0_de_league():
    """O pedido, à letra: *"um 5-0 de league É o sinal que ele quer"*.

    E a outra metade, que é a que se pode estragar sem ninguém ver: o filtro de
    tier continua ligado para TODO o resto — a liga sem carta vigiada não se
    guarda, e a vigiada não passa a contar para o metagame.
    """
    com_config("com-vigia.json")
    con = base()
    did = guarda_combo(con)
    assert did is not None, "a liga COM carta vigiada tem de entrar na base"

    nada = sources.store_decklist(con, **dict(
        LIGA, source_key="liga-burn", cards=BURN, player="outro"))
    assert nada is None, "a liga SEM carta vigiada continua a não se guardar"

    linha = con.execute("SELECT * FROM decklists WHERE id = ?", (did,)).fetchone()
    assert linha["event_tier"] == "League", linha["event_tier"]
    assert not sources.lista_conta(linha, "modern"), \
        "a liga vigiada nao pode passar a contar para o metagame"
    sql, params = sources.counting_sql("modern", "d")
    assert not con.execute(
        f"SELECT 1 FROM decklists d WHERE d.id = ? AND {sql}",
        (did, *params)).fetchone(), "o counting_sql tem de continuar a recusa-la"

    toast = Toast()
    res = vigia.verificar(con, pasta=_TMP / "e1", toast=toast)
    assert res["vigiadas"] == 2, res["vigiadas"]
    cartas = {a["carta"] for a in res["novos"]}
    assert cartas == {KASMINA, JACE}, cartas
    assert len(toast.chamadas) == 1, "um toast por corrida, nao um por carta"
    assert KASMINA in toast.chamadas[0][1] or JACE in toast.chamadas[0][1]
    assert "e mais 1" in toast.chamadas[0][1], toast.chamadas[0][1]

    # O avistamento traz tudo o que ele precisa para ir ver a lista.
    a = next(x for x in res["novos"] if x["carta"] == KASMINA)
    assert a["formato"] == "modern" and a["tier"] == "League"
    assert a["evento"] == LIGA["event_name"] and a["data"] == "2026-10-03"
    assert a["jogador"] == "jacespike" and a["colocacao"] == "5-0"
    assert a["link"].startswith("https://www.mtgo.com/"), a["link"]
    assert a["copias"] == 4 and a["board"] == "main"
    assert len(a["lista"]) == len(COMBO), "a lista fica guardada no estado"

    # O log do daily diz o que apareceu, com o link e o que falta para montar.
    texto = "\n".join(res["linhas"])
    assert "[NOVA]" in texto and "falta comprar" in texto, texto
    assert res["resumo"].startswith("2 LISTA(S) NOVA(S)"), res["resumo"]

    # E o ficheiro de estado tem as sete coisas que ele pediu.
    estado = json.loads((_TMP / "e1" / vigia.FICHEIRO).read_text(encoding="utf-8"))
    guardado = list(estado["achados"].values())[0]
    for campo in ("carta", "formato", "evento", "data", "jogador", "colocacao",
                  "link"):
        assert guardado.get(campo), f"o estado nao guarda o {campo}"
    print("liga com carta vigiada: apanhada, avisada uma vez, e continua fora do metagame")


def caso_a_poda_de_ligas_nao_apaga_a_lista_vigiada():
    """Sem isto, as outras duas portas não valiam nada: a liga entrava às 03:30 e
    o passo `podar-ligas` apagava-a minutos depois, na mesma corrida."""
    com_config("com-vigia.json")
    con = base()
    did = guarda_combo(con)
    # Uma liga sem carta vigiada, metida à mão (a recolha já não a guardaria).
    con.execute("""INSERT INTO decklists (source, source_key, format, event_name,
                                          event_date, player, event_tier)
                   VALUES ('mtgo','liga-velha','modern','Modern League',
                           '2026-10-03','z','League')""")
    outra = con.execute("SELECT id FROM decklists WHERE source_key='liga-velha'"
                        ).fetchone()["id"]
    con.executemany("INSERT INTO decklist_cards (decklist_id, card_name, quantity,"
                    " board) VALUES (?,?,?,'main')",
                    [(outra, n, q) for _b, n, q in BURN])
    con.commit()

    assert analysis.prune_leagues(con) == 1, "so a liga sem carta vigiada e apagada"
    ficam = {r["id"] for r in con.execute("SELECT id FROM decklists")}
    assert did in ficam, "a lista com a carta vigiada foi apagada pela poda"
    assert outra not in ficam
    # As cartas dela também ficam — é de lá que saem as faltas.
    assert con.execute("SELECT COUNT(*) c FROM decklist_cards WHERE decklist_id = ?",
                       (did,)).fetchone()["c"] == len(COMBO)
    assert analysis.prune_leagues(con) == 0, "idempotente"
    print("prune_leagues poupa a lista vigiada e apaga a outra")


def caso_uma_lista_ja_vista_nao_volta_a_avisar():
    """O toast é para o que é NOVO. E a chave de um avistamento não é o
    `decklist_id`: a deduplicação entre fontes apaga e reinsere a mesma lista, e
    com o id na chave o aviso repetia-se sem nada ter acontecido."""
    com_config("com-vigia.json")
    con = base()
    did = guarda_combo(con)
    pasta = _TMP / "e2"

    t1 = Toast()
    r1 = vigia.verificar(con, pasta=pasta, toast=t1)
    assert len(r1["novos"]) == 2 and len(t1.chamadas) == 1

    t2 = Toast()
    r2 = vigia.verificar(con, pasta=pasta, toast=t2)
    assert r2["novos"] == [], "a mesma lista nao pode voltar a ser nova"
    assert t2.chamadas == [], "e nao pode voltar a avisar"
    assert len(r2["todos"]) == 2, "mas continua a aparecer no que ja se viu"
    assert "0 novos" in r2["resumo"], r2["resumo"]

    # A mesma lista com outro id (é o que a deduplicação faz): continua a não ser
    # nova.
    con.execute("PRAGMA defer_foreign_keys = ON")   # as duas linhas andam juntas
    con.execute("UPDATE decklist_cards SET decklist_id = 9999 WHERE decklist_id = ?",
                (did,))
    con.execute("UPDATE decklists SET id = 9999 WHERE id = ?", (did,))
    con.commit()
    t3 = Toast()
    r3 = vigia.verificar(con, pasta=pasta, toast=t3)
    assert r3["novos"] == [], "o id mudou, o avistamento e o mesmo"
    assert t3.chamadas == []
    assert all(a["decklist_id"] == 9999 for a in r3["todos"]), \
        "o estado tem de acertar o id novo"
    print("lista ja vista: sem toast, mesmo depois de a deduplicacao lhe mudar o id")


def caso_sem_cartas_vigiadas_nada_muda():
    """A garantia de que ligar isto não mexe no daily de quem não vigia nada."""
    com_config("sem-vigia.json")
    con = base()
    assert vigia.cartas() == []
    assert not vigia.ha_vigia("modern") and not vigia.ha_vigia()
    assert vigia.nomes_na_lista("modern", COMBO) == []

    assert guarda_combo(con) is None, \
        "sem cartas vigiadas a liga volta a ser recusada a entrada"

    con.execute("""INSERT INTO decklists (source, source_key, format, event_name,
                                          event_date, player, event_tier)
                   VALUES ('mtgo','liga','modern','Modern League','2026-10-03',
                           'z','League')""")
    con.commit()
    assert analysis.prune_leagues(con) == 1, "a poda volta a apagar tudo"

    pasta = _TMP / "e3"
    res = vigia.verificar(con, pasta=pasta)
    assert res["vigiadas"] == 0 and res["novos"] == []
    assert "sem cartas vigiadas" in res["resumo"], res["resumo"]
    assert not (pasta / vigia.FICHEIRO).exists(), \
        "sem cartas vigiadas nao se escreve ficheiro de estado nenhum"
    assert vigia.painel(con) == {"vigiadas": [], "achados": [], "total": 0,
                                "nota": vigia.NOTA_FALTAS}

    # E o passo do daily diz que não tem nada a fazer, em vez de saltar calado.
    import daily                                              # noqa: PLC0415
    assert "sem cartas vigiadas" in daily._vigia_cartas(con)
    print("sem cartas vigiadas: recolha, poda, estado e passo do daily iguais aos de ontem")


def caso_as_faltas_saem_da_base_e_dizem_no():
    """André diz ter 4× Kasmina; a base tem 0 — as cópias novas só entram quando
    ele as fotografar. Não se inventa que as tem, e diz-se de onde vem o número."""
    com_config("com-vigia.json")
    con = base()
    guarda_combo(con)
    f = vigia.faltas(con, [[b, n, q] for b, n, q in COMBO])
    por_nome = {m["nm"]: m for m in f["linhas"]}
    assert por_nome[KASMINA]["tem"] == 0 and por_nome[KASMINA]["falta"] == 4
    assert por_nome["Island"]["basica"] is True
    assert f["falta_total"] == 17, f["falta_total"]     # 4+4+2+4+3, sem as 20 Island
    assert "foto" in f["nota"].lower(), f["nota"]

    # Fotografadas duas: a falta desce, e o resto fica igual.
    con.execute("INSERT INTO sub_collections (name, purpose) VALUES ('Colecção','player')")
    sub = con.execute("SELECT id FROM sub_collections WHERE name='Colecção'"
                      ).fetchone()["id"]
    con.execute("""INSERT INTO copies (scryfall_id, quantity, finish, language,
                   purpose, sub_collection_id)
                   VALUES ('id-kas', 2, 'nonfoil', 'en', 'player', ?)""", (sub,))
    con.commit()
    f2 = vigia.faltas(con, [[b, n, q] for b, n, q in COMBO])
    k = next(m for m in f2["linhas"] if m["nm"] == KASMINA)
    assert k["tem"] == 2 and k["falta"] == 2, k
    assert f2["falta_total"] == 15, f2["falta_total"]
    print("faltas: contadas na base (0 Kasmina), com a nota a dizer porque")


def caso_o_bloco_do_metagame_mostra_a_vigia():
    """O aviso também tem de estar onde ele olha: a página do Metagame."""
    com_config("com-vigia.json")
    con = base()
    guarda_combo(con)
    import metagame                                           # noqa: PLC0415
    vigia.verificar(con, pasta=vigia.caminho_estado().parent, toast=Toast())
    h = metagame._vigia_html(con)
    assert "Vigia de cartas" in h
    for x in (KASMINA, "Jace&#x27;s Machinations", NOTA, "League",
              "jacespike", "Modern League 2026-10-03"):
        assert x in h, x
    assert "Para montares esta lista" in h and "4×" in h
    assert "foto" in h, "a pagina tem de dizer de onde vem o numero das faltas"
    assert 'href="https://www.mtgo.com/' in h, "o link da lista"

    # A página INTEIRA: o `%VIGIA%` tem de ser substituído. Um marcador que
    # sobrasse aparecia à vista na página e nenhum teste do bloco o apanhava.
    com_config("com-vigia.json")
    pagina = metagame.html_page(con)
    assert "%VIGIA%" in metagame._tmpl() and "%VIGIA%" not in pagina
    assert 'id="vigia"' in pagina and KASMINA in pagina

    com_config("sem-vigia.json")
    assert metagame._vigia_html(con) == "", \
        "sem cartas vigiadas a seccao nao existe"
    assert "%VIGIA%" not in metagame.html_page(con), \
        "sem vigia o marcador tem de sair da pagina de qualquer maneira"
    print("metagame.html: bloco com as cartas vigiadas, o que apareceu e as faltas")


def run():
    caso_a_vigia_apanha_um_5_0_de_league()
    caso_a_poda_de_ligas_nao_apaga_a_lista_vigiada()
    caso_uma_lista_ja_vista_nao_volta_a_avisar()
    caso_sem_cartas_vigiadas_nada_muda()
    caso_as_faltas_saem_da_base_e_dizem_no()
    caso_o_bloco_do_metagame_mostra_a_vigia()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
