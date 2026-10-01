"""Prova que os casos do `test_webapp_prazo` CHUMBAM sem a funcionalidade.

Desliga, um de cada vez, o que entrou a 2026-10-01 (a avaria do 502 no
telemovel) e exige que o caso correspondente falhe.

UM PROCESSO POR CASO, de proposito. Metade do que aqui se desliga faz o pedido
PENDURAR — e um pedido pendurado e exactamente o defeito que se esta a provar:
o `em_cache` antigo segura o lock da cache durante o calculo e, com o relatorio
partilhado a pedir a cache de dentro do calculo, prende-o para sempre. Num
processo so, o primeiro caso que pendura envenenava todos os seguintes (foi o
que aconteceu a primeira vez: parou depois do quarto, calado). Por isso:
cada caso corre sozinho, com prazo, e um ESTOURO DE PRAZO conta como chumba —
com o motivo a dizer que pendurou.

Corre-se a mao: `py tests/_chumba_prazo.py`.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PRAZO = 180

# (etiqueta, nome do caso) — a ordem e a da ordem do Andre.
CASOS = [
    ("o intervalo de prefixo (era LIKE, SCAN cards)",
     "caso_a_frente_de_dupla_face_nao_varre_o_catalogo"),
    ("o foil_cache partilhado pelas duas passagens do lots()",
     "caso_o_catalogo_responde_uma_vez_por_nome"),
    ("o PRAGMA busy_timeout",
     "caso_a_base_espera_por_quem_esta_a_escrever"),
    ("o tecto do pedido (503 explicado)",
     "caso_a_geracao_travada_da_um_erro_explicado_em_vez_de_pendurar"),
    ("o tecto do pedido, na Arrumacao",
     "caso_o_503_tambem_vale_para_a_arrumacao_e_para_o_metagame"),
    ("o lock da cache largado durante o calculo",
     "caso_uma_vista_lenta_nao_tranca_outra"),
    ("o prazo no lock de escrita",
     "caso_um_botao_nao_fica_pendurado_atras_de_uma_escrita"),
    ("o relatorio partilhado",
     "caso_a_geracao_corre_uma_vez_para_o_indice_e_as_partes"),
    ("o -wal vazio fora da versao",
     "caso_abrir_e_fechar_a_base_nao_atira_a_cache_fora"),
]


def um_caso(nome: str) -> int:
    """Corre UM caso com a funcionalidade desligada. 0 = chumbou (bom)."""
    sys.path.insert(0, str(AQUI))
    import test_webapp_prazo as T                            # noqa: PLC0415
    from mtgvault import db, loadout, scryfall                # noqa: PLC0415
    import threading                                         # noqa: PLC0415
    import webapp                                            # noqa: PLC0415

    # --- desligar o que o caso testa ---------------------------------------
    if nome == "caso_a_frente_de_dupla_face_nao_varre_o_catalogo":
        scryfall.frente_de_dupla_face = \
            lambda coluna="name": f"{coluna} LIKE ? || ' // %'"
        scryfall.limites_dupla_face = lambda name: (name,)
    elif nome == "caso_o_catalogo_responde_uma_vez_por_nome":
        _pcts = loadout._pcts_da_coleccao
        loadout._pcts_da_coleccao = \
            lambda con, slots, foil_cache=None: _pcts(con, slots)
    elif nome == "caso_a_base_espera_por_quem_esta_a_escrever":
        _c = db.connect

        def _sem_busy(path=None, catalog=None):
            con = _c(path, catalog)
            con.execute("PRAGMA busy_timeout = 0")
            return con
        db.connect = _sem_busy
    elif nome == "caso_um_botao_nao_fica_pendurado_atras_de_uma_escrita":
        class _SemPrazo:
            def __enter__(self):
                webapp.ESCRITA.acquire()

            def __exit__(self, *a):
                webapp.ESCRITA.release()
        webapp.escrita = lambda espera=None: _SemPrazo()
    elif nome == "caso_abrir_e_fechar_a_base_nao_atira_a_cache_fora":
        # O `-wal` vazio a contar outra vez, como antes.
        from pathlib import Path as _P                         # noqa: PLC0415

        def _com_wal():
            base = _P(db.DEFAULT_DB)
            out = []
            for f in [base, base.with_name(base.name + "-wal"), webapp.CONFIG,
                      _P(db.pasta_dados()) / "arquetipos.json",
                      webapp.ROOT / "pendentes"]:
                try:
                    st = f.stat()
                    out.append((str(f), st.st_mtime_ns, st.st_size))
                except OSError:
                    out.append((str(f), None, None))
            return tuple(out)
        webapp._versao = _com_wal
    elif nome == "caso_a_geracao_corre_uma_vez_para_o_indice_e_as_partes":
        # Cada vista com o SEU relatorio, como antes de 2026-10-01.
        def _proprio():
            with db.session() as con:
                return loadout.report(con)
        webapp.relatorio = _proprio
    else:
        # O `em_cache` de ANTES: calcula o que for preciso, sem prazo, com o
        # lock da cache na mao. O `RLock` e para o aninhamento nao bloquear o
        # processo inteiro — sem ele nem se chegava a ver o caso falhar.
        velho_lock = threading.RLock()

        def _antigo(chave, calcular, etiqueta="", espera=None):
            v = webapp._versao()
            with velho_lock:
                hit = webapp._CACHE.get(chave)
                if hit and hit[0] == v:
                    return hit[1]
                valor = calcular()
                webapp._CACHE[chave] = (v, valor)
                return valor
        webapp.em_cache = _antigo

    # --- e exigir que o caso falhe -----------------------------------------
    try:
        getattr(T, nome)()
    except AssertionError as e:
        print("CHUMBOU " + (str(e).splitlines() or ["(sem mensagem)"])[0][:110])
        return 0
    except Exception as e:                                    # noqa: BLE001
        print(f"CHUMBOU {type(e).__name__}: {e}"[:120])
        return 0
    print("PASSOU — o teste nao esta a testar nada")
    return 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(um_caso(sys.argv[1]))
    bom = True
    for etiqueta, nome in CASOS:
        try:
            p = subprocess.run([sys.executable, "-u", __file__, nome], cwd=AQUI,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=PRAZO)
        except subprocess.TimeoutExpired:
            # Pendurou. E o defeito, à letra: era assim que o pedido do
            # telemóvel dele acabava num 502 sem explicação nenhuma.
            print(f"  ok   chumba sem «{etiqueta}»: PENDUROU (sem resposta em "
                  f"{PRAZO} s) — e exactamente o defeito")
            continue
        saida = [l for l in (p.stdout or "").splitlines()
                 if l.startswith(("CHUMBOU", "PASSOU"))]
        motivo = saida[-1] if saida else "(sem saida)"
        if p.returncode == 0 and motivo.startswith("CHUMBOU"):
            print(f"  ok   chumba sem «{etiqueta}»: {motivo[8:]}")
        else:
            bom = False
            print(f"  FAIL «{etiqueta}»: {motivo} (codigo {p.returncode})")
            print((p.stderr or "")[-600:])
    print("\n" + ("TODOS OS CASOS CHUMBAM SEM A FUNCIONALIDADE" if bom else
                  "HA CASOS QUE PASSAM SEM A FUNCIONALIDADE"))
    sys.exit(0 if bom else 1)
