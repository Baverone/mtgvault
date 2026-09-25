"""Prova que os casos novos CHUMBAM sem a funcionalidade (régua do ai-pc).

Desliga, um de cada vez, o que foi acrescentado hoje, e exige que o caso
correspondente falhe. Um teste que passa com a funcionalidade desligada não
está a testar nada.

Não entra na bateria — corre-se à mão: `py tests/_provar_chumba.py`.
"""
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

print("TODOS OS CASOS CHUMBAM SEM A FUNCIONALIDADE" if bom
      else "HA CASOS QUE PASSAM SEM A FUNCIONALIDADE")
sys.exit(0 if bom else 1)
