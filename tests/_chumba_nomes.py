"""Corre UM caso do `test_nomes_arquetipo` com a funcionalidade desligada.

`py tests/_chumba_nomes.py <alvo> <nome_do_caso>` — sai a 0 se o caso PASSAR (o
que é mau: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o
`test_nomes_arquetipo` fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o
`MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  parser     — o nome deixa de ser lido da página do evento. É o estado em que o
               projecto esteve até hoje: *"a fonte não nos dá o nome do
               arquétipo"*, escrito no `meta_coverage` como se fosse verdade;
  recolha    — o parser existe mas o `harvest` não passa o nome ao
               `store_decklist`: a informação volta a morrer no sítio onde
               morria;
  voto       — o grupo deixa de herdar o nome das listas nomeadas, e as 3 894
               listas de `mtgo` que hoje têm nome voltam a não ter;
  inventa    — o inverso, e é o erro oposto: um grupo SEM nenhuma lista nomeada
               passa a dar-se por nomeado (devolve a etiqueta como se fosse nome
               da fonte), e a página deixa de marcar o nome como provisório;
  negacao    — o `assinatura_sem` é ignorado: a assinatura «Replenish» volta a
               apanhar as 186 listas, Enchantress incluída, e os dois decks
               voltam a fundir-se;
  marcador   — o backfill deixa de marcar `sem-nome` o deck que a página não
               nomeia: o progresso perde-se e o mesmo evento volta a ser pedido
               todas as noites, para sempre.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_nomes_arquetipo as T                              # noqa: E402
from mtgvault import mtgtop8, nomes, sources                  # noqa: E402

if alvo == "parser":
    mtgtop8.parse_deck_archetypes = lambda html: {}
elif alvo == "recolha":
    _store = sources.store_decklist

    def _sem_nome(con, **kw):
        kw.pop("arquetipo", None)
        kw.pop("arquetipo_de", None)
        return _store(con, **kw)

    sources.store_decklist = _sem_nome
    mtgtop8.sources.store_decklist = _sem_nome
elif alvo == "voto":
    nomes.nomes_por_cluster = lambda con, fmt=None: {}
    nomes.nome_das_listas = lambda con, ids: None
elif alvo == "inventa":
    def _inventa(con, aid, etiqueta="", gerado="", fmt=None, cache=None):
        return {"nome": gerado or etiqueta, "origem": nomes.ORIGEM_HERDADO,
                "provisorio": False, "etiqueta": etiqueta, "votos": 0,
                "nomeadas": 0, "listas": 0, "segundo": None}

    nomes.rotulo = _inventa
elif alvo == "negacao":
    _ids = sources.ids_por_assinatura
    sources.ids_por_assinatura = (
        lambda con, fmt, assinatura, todas=False, desde=None,
        so_que_contam=True, sem=None:
        _ids(con, fmt, assinatura, todas, desde, so_que_contam, None))
elif alvo == "marcador":
    # Sem o marcador `sem-nome`, só se escreve quando há nome — e o evento volta
    # a aparecer na fila do que falta recuperar.
    _bf = mtgtop8.backfill_archetype_names

    def _sem_marcador(con, max_events=None):
        por = mtgtop8.eventos_por_recuperar(con)
        if not por:
            return "nada por recuperar"
        alvos = list(por.items())[:max_events] if max_events else list(por.items())
        eventos = nomeadas = sem = 0
        for (eid, code), decks in alvos:
            achados = mtgtop8.parse_deck_archetypes(
                mtgtop8._get("/event", e=eid, f=code))
            eventos += 1
            for did in decks:
                nome = achados.get(did)
                if nome:
                    con.execute(
                        "UPDATE decklists SET arquetipo_fonte = ?, "
                        "arquetipo_fonte_de = 'recuperado' WHERE source = 'mtgtop8'"
                        " AND source_key = ?", (nome, str(did)))
                    nomeadas += 1
                else:
                    sem += 1
            con.commit()
        return (f"{eventos} eventos lidos, {nomeadas} listas com nome, "
                f"{sem} sem nome na pagina, 0 eventos a falhar, "
                f"{len(por) - eventos} por fazer")

    mtgtop8.backfill_archetype_names = _sem_marcador
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
