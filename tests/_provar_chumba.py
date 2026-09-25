"""Prova que os casos novos CHUMBAM sem a funcionalidade (régua do ai-pc).

Desliga, um de cada vez, o que foi acrescentado hoje, e exige que o caso
correspondente falhe. Um teste que passa com a funcionalidade desligada não
está a testar nada.

Não entra na bateria — corre-se à mão: `py tests/_provar_chumba.py`.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_preco_modo as T                                # noqa: E402
from mtgvault import loadout, precos, prices               # noqa: E402


def exige_falha(nome, caso):
    try:
        caso()
    except AssertionError as e:
        motivo = (str(e).splitlines() or ["(sem mensagem)"])[0][:90]
        print(f"  ok   chumba sem «{nome}»: {motivo}")
        return True
    print(f"  FAIL passou sem «{nome}» — o teste nao esta a testar nada")
    return False


bom = True

# 1. sem o travao do `modo_desde`
_orig = precos.modo_desde
precos.modo_desde = lambda cfg=None: None
bom &= exige_falha("precos.modo_desde",
                   T.caso_trocar_de_modo_nao_manda_nenhuma_rl_para_a_venda)
precos.modo_desde = _orig

# 2. sem o filtro por receita no historico
_hist = loadout._historico


def _sem_receita(con, name, finish, source=None, receita=None):
    return _hist(con, name, finish, source,
                 receita=precos.receita_em_vigor(con, source or precos.fonte()))


def _todas(con, name, finish, source=None, receita=None):
    source = source or precos.fonte()
    expr = precos.sql(alias="h")
    fins = (loadout.FOIL_FINISHES if finish in loadout.FOIL_FINISHES
            else ("nonfoil",))
    marks = ",".join("?" * len(fins))
    return con.execute(
        f"""SELECT h.scryfall_id sid, h.finish fin, h.date d, {expr} t
              FROM price_history h JOIN cards c ON c.scryfall_id = h.scryfall_id
             WHERE c.name = ? AND h.source = ? AND h.finish IN ({marks})
                   AND {expr} IS NOT NULL ORDER BY h.date""",
        (name, source, *fins)).fetchall()


loadout._historico = _todas
bom &= exige_falha("o filtro por receita",
                   T.caso_a_receita_nova_nao_se_compara_com_a_antiga)
loadout._historico = _hist

# 3. sem os DOIS valores do CardTrader (o codigo antigo: min nas duas colunas)
_dois = precos.dois_valores
precos.dois_valores = lambda ofertas: {
    "low": round(min(o["price_cents"] / 100 for o in ofertas), 2),
    "trend": round(min(o["price_cents"] / 100 for o in ofertas), 2),
    "copias": len(ofertas), "n": len(ofertas)}
bom &= exige_falha("os dois valores do CardTrader",
                   T.caso_o_cardtrader_guarda_os_dois_valores)
precos.dois_valores = _dois

# 4. sem o filtro de ofertas
_ut = precos.oferta_utilizavel
precos.oferta_utilizavel = lambda o, aceites=None: True
bom &= exige_falha("o filtro de ofertas",
                   T.caso_as_ofertas_improprias_nao_fazem_preco)
precos.oferta_utilizavel = _ut

# 5. sem o modo a mandar no preco (tudo `trend`, como antes)
_sql = precos.sql
precos.sql = lambda qual=None, alias="p": f"{alias}.trend" if alias else "trend"
bom &= exige_falha("o modo a mandar no preco",
                   T.caso_os_tres_modos_dao_tres_precos_e_todas_as_paginas_concordam)
precos.sql = _sql

# 6. sem a receita na comparacao do write_prices
_wp = prices.write_prices


def _sem_receita_wp(con, rows):
    linhas = [tuple(r)[:9] + (None,) for r in rows]
    rows.clear()
    rows.extend(linhas)
    return _wp(con, rows)


prices.write_prices = _sem_receita_wp
bom &= exige_falha("a receita na comparacao",
                   T.caso_a_receita_entra_na_comparacao_do_write_prices)
prices.write_prices = _wp

# ---------------------------------------------------------------------------
# O INTERRUPTOR DA VENDA (André, 2026-09-25: *"para já tira o «vender»"*)
#
# Corre-se NOUTRO PROCESSO: o `test_venda_interruptor` fixa o `MTGVAULT_CONFIG`
# e o `MTGVAULT_DB` no import, e importá-lo aqui dentro punha-o a partilhar o
# ambiente do ficheiro de cima. O `--neutralizar` faz o interruptor responder
# sempre «à vista» — que é exactamente o que o mtgvault era ontem.
# ---------------------------------------------------------------------------
AQUI = Path(__file__).resolve().parent
for alvo, casos in (
    ("mostrar", ["caso_desligado_nao_sobra_venda_no_que_ele_ve",
                 "caso_os_endpoints_de_escrita_recusam_se_em_condicoes",
                 "caso_a_revalidacao_nao_perde_as_copias_da_venda",
                 "caso_o_daily_salta_o_passo_e_diz_porque"]),
    ("seccoes", ["caso_desligado_nao_sobra_venda_no_que_ele_ve"]),
):
    for caso in casos:
        p = subprocess.run(
            [sys.executable, str(AQUI / "_chumba_venda.py"), alvo, caso],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=AQUI)
        ok = p.returncode != 0
        bom &= ok
        motivo = (p.stdout or p.stderr or "").strip().splitlines()
        print(f"  {'ok  ' if ok else 'FAIL'} chumba sem «{alvo}» "
              f"({caso}): {motivo[-1][:90] if motivo else ''}")

# ---------------------------------------------------------------------------
# O PREÇO DE REFERÊNCIA (André, 2026-09-25: *"para Market Price ou Best Deal,
# ao invés de MÍNIMO"*). Noutro processo, pela razão de cima.
# ---------------------------------------------------------------------------
for alvo, casos in (
    # O `caso_sem_cotacao_...` fica de fora de propósito: o que ele descreve é o
    # ÚLTIMO RECURSO, que é exactamente o comportamento de ontem. Não prova a
    # funcionalidade, prova que o caminho antigo continua lá e marcado.
    ("preco_da_copia", ["caso_o_preco_de_uma_copia_e_o_da_impressao_dela",
                        "caso_a_regra_da_rl_compara_a_impressao_dela_nas_duas_pontas"]),
    ("regua_desde", ["caso_trocar_de_fonte_nao_manda_nenhuma_rl_para_a_venda"]),
    ("fontes", ["caso_a_cadeia_usa_a_principal_e_cai_na_de_recurso",
                "caso_o_preco_de_hoje_e_o_historico_tem_de_ser_da_mesma_fonte"]),
    ("cadeia_ordem", ["caso_a_cadeia_nao_e_um_minimo_entre_fontes"]),
    ("prune_marketplace", ["caso_o_historico_do_marketplace_sem_consumidor_e_podado"]),
):
    for caso in casos:
        p = subprocess.run(
            [sys.executable, str(AQUI / "_chumba_preco_ref.py"), alvo, caso],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=AQUI)
        ok = p.returncode != 0
        bom &= ok
        motivo = (p.stdout or p.stderr or "").strip().splitlines()
        print(f"  {'ok  ' if ok else 'FAIL'} chumba sem «{alvo}» "
              f"({caso}): {motivo[-1][:90] if motivo else ''}")

print("TODOS OS CASOS CHUMBAM SEM A FUNCIONALIDADE" if bom
      else "HA CASOS QUE PASSAM SEM A FUNCIONALIDADE")
sys.exit(0 if bom else 1)
