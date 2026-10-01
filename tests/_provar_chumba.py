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

# ---------------------------------------------------------------------------
# A VIGIA DE CARTAS (André, 2026-09-26: *"vai conferindo"*). Noutro processo,
# pela razão de cima.
# ---------------------------------------------------------------------------
for alvo, casos in (
    ("nomes_na_lista", ["caso_a_vigia_apanha_um_5_0_de_league",
                        "caso_a_poda_de_ligas_nao_apaga_a_lista_vigiada",
                        "caso_o_bloco_do_metagame_mostra_a_vigia"]),
    ("achados", ["caso_a_poda_de_ligas_nao_apaga_a_lista_vigiada",
                 "caso_o_bloco_do_metagame_mostra_a_vigia"]),
    ("chave", ["caso_uma_lista_ja_vista_nao_volta_a_avisar"]),
    ("nota_faltas", ["caso_as_faltas_saem_da_base_e_dizem_no"]),
):
    for caso in casos:
        p = subprocess.run(
            [sys.executable, str(AQUI / "_chumba_vigia.py"), alvo, caso],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=AQUI)
        ok = p.returncode != 0
        bom &= ok
        motivo = (p.stdout or p.stderr or "").strip().splitlines()
        print(f"  {'ok  ' if ok else 'FAIL'} chumba sem «{alvo}» "
              f"({caso}): {motivo[-1][:90] if motivo else ''}")

# ---------------------------------------------------------------------------
# AS QUATRO PROTECÇÕES E AS FASES (André, 2026-10-01). Noutro processo, pela
# razão de cima.
# ---------------------------------------------------------------------------
for alvo, casos in (
    ("terras", ["caso_uma_shockland_extra_fora_de_qualquer_deck_nunca_e_candidata",
                "caso_todas_as_copias_de_uma_shock_fetch_ficam_protegidas",
                "caso_as_proteccoes_valem_tambem_no_motor_da_venda"]),
    ("rl_joga", ["caso_uma_rl_que_ele_joga_nunca_e_candidata"]),
    ("decisoes", ["caso_uma_copia_num_deck_guardado_nunca_e_candidata",
                  "caso_um_deck_sem_decisao_nao_manda_nada_para_a_venda"]),
    # A OMISSÃO: é a que mais dinheiro custava se estivesse ao contrário.
    ("omissao", ["caso_um_deck_sem_decisao_conta_como_montado",
                 "caso_um_deck_sem_decisao_nao_manda_nada_para_a_venda"]),
    ("reservas", ["caso_uma_carta_da_reserva_acima_do_limiar_nunca_e_candidata",
                  "caso_a_reserva_manual_fica_mesmo_sem_consenso"]),
    ("limiar", ["caso_abaixo_do_limiar_a_carta_volta_a_ser_candidata"]),
    ("min_listas", ["caso_a_reserva_nao_se_enche_sem_amostra"]),
    ("congelado", ["caso_a_saida_de_venda_recusa_se_antes_de_doze_de_outubro"]),
    # A regra ERRADA de 2026-10-01 (uma linha por cópia física) e o tecto.
    ("explode", ["caso_um_playset_e_UMA_foto_e_nunca_quatro",
                 "caso_a_fila_dos_decks_conta_fotos_cartas_e_valor"]),
    ("ate4", ["caso_uma_foto_leva_no_maximo_quatro_cartas"]),
    ("por_tipo", ["caso_a_fila_dos_decks_conta_fotos_cartas_e_valor"]),
    ("ordem_fila", ["caso_a_fila_de_candidatos_sai_por_valor_decrescente"]),
):
    for caso in casos:
        p = subprocess.run(
            [sys.executable, str(AQUI / "_chumba_fases.py"), alvo, caso],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=AQUI)
        ok = p.returncode != 0
        bom &= ok
        motivo = (p.stdout or p.stderr or "").strip().splitlines()
        print(f"  {'ok  ' if ok else 'FAIL'} chumba sem «{alvo}» "
              f"({caso}): {motivo[-1][:90] if motivo else ''}")

# ---------------------------------------------------------------------------
# AS FOTOS DE ATÉ 4 CARTAS (André, 2026-10-01). Noutro processo, pela razão de
# cima — e é aqui que se prova que a regra CERTA está a ser medida, depois de
# duas regras erradas terem passado por este ficheiro no mesmo dia.
# ---------------------------------------------------------------------------
for alvo, casos in (
    # O `caso_um_playset_e_uma_foto_de_quatro_cartas` fica de fora deste alvo de
    # propósito: um playset cabe em 4 e cabe em infinito, logo tirar o TECTO não
    # o parte. Quem o parte é o `explode` (acima), e é lá que ele está.
    ("ate4", ["caso_nenhuma_foto_passa_de_quatro_cartas",
              "caso_a_barra_mede_fotos_e_diz_as_cartas_e_as_linhas",
              "caso_uma_foto_nova_com_mais_de_quatro_cartas_e_recusada_inteira",
              "caso_uma_carta_nova_numa_foto_grande_entra_mas_nao_fica_validada",
              "caso_uma_foto_antiga_com_mais_de_quatro_nao_conta_como_validacao"]),
    ("por_tipo", ["caso_quatro_cartas_diferentes_na_mesma_foto_agrupadas_por_tipo"]),
    ("resolver", ["caso_uma_foto_no_arquivo_continua_a_ser_encontrada",
                  "caso_as_fotos_perdidas_ficam_marcadas_e_a_cabeca"]),
    ("perdidas", ["caso_as_fotos_perdidas_ficam_marcadas_e_a_cabeca"]),
    ("por_deck", ["caso_as_fotos_novas_arrumam_se_por_deck"]),
    ("conversao", ["caso_os_decks_de_lista_unica_vem_primeiro"]),
    ("nao_pisa", ["caso_arquivar_move_e_nunca_apaga_nem_pisa"]),
):
    for caso in casos:
        p = subprocess.run(
            [sys.executable, str(AQUI / "_chumba_fotos.py"), alvo, caso],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=AQUI)
        ok = p.returncode != 0
        bom &= ok
        motivo = (p.stdout or p.stderr or "").strip().splitlines()
        print(f"  {'ok  ' if ok else 'FAIL'} chumba sem «{alvo}» "
              f"({caso}): {motivo[-1][:90] if motivo else ''}")

# ---------------------------------------------------------------------------
# A PASTA POR DECK VALE COMO ALVO (André, 2026-10-01, à tarde: «o melhor é criar
# pasta»). Noutro processo, pela razão de cima.
# ---------------------------------------------------------------------------
for alvo, casos in (
    ("mapa", ["caso_uma_foto_na_pasta_do_deck_e_reconhecida",
              "caso_a_subpasta_de_lote_conta_para_o_mesmo_deck",
              "caso_a_recolha_move_a_foto_com_o_nome_do_alvo"]),
    ("escrito", ["caso_renomear_a_caixa_muda_a_pasta_sem_tocar_em_codigo"]),
    ("primeira", ["caso_a_subpasta_de_lote_conta_para_o_mesmo_deck"]),
    ("grupo", ["caso_as_pastas_de_grupo_nao_valem_como_alvo"]),
    ("recolhe", ["caso_a_recolha_move_a_foto_com_o_nome_do_alvo"]),
    ("sossego", ["caso_uma_foto_ainda_a_ser_copiada_nao_se_mexe"]),
    ("planos", ["caso_o_plano_manda_largar_as_fotos_NESTA_pasta"]),
    ("vazios", ["caso_uma_caixa_vazia_nao_rebenta_a_geracao"]),
    ("ip", ["caso_o_endereco_do_modo_de_edicao_e_o_nome_e_nunca_o_ip"]),
):
    for caso in casos:
        p = subprocess.run(
            [sys.executable, str(AQUI / "_chumba_pasta.py"), alvo, caso],
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
