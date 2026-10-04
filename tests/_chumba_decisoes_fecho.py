"""Prova que o `test_decisoes_1004_fecho.py` CHUMBA sem o trabalho feito.

Corre-se a mao: `py tests\\_chumba_decisoes_fecho.py`.

UM PROCESSO POR PAR, de proposito (a licao do `_chumba_prazo` de 01/10): cada
alvo desliga uma peca, e varios deles envenenavam os seguintes no mesmo
processo (o `test_decisoes_1004_fecho` fixa o MTGVAULT_CONFIG no import). Cada
par corre isolado e tem de dar NAO-ZERO.

Os tres grupos sao as tres decisoes de 04/10/2026 ao fim do dia: a trava manual,
a razao do duel-commander escrita, e o Whipflare nonfoil com a vigia do foil.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# (alvo, o que se desliga, codigo que o neutraliza antes de correr o caso)
ALVOS = [
    # ---------------------------------------------------- 1) A TRAVA MANUAL
    ("trava_volta_a_ser_a_data",
     "a trava volta a ser `hoje < congelado_ate` (o codigo de ontem)",
     """
from datetime import date
from mtgvault import fases
def por_data(cfg=None, hoje=None):
    ate = fases.congelado_ate(cfg)
    return bool(ate) and (hoje or date.today().isoformat()) < ate
fases.venda_congelada = por_data
fases.congelada = lambda cfg=None: por_data(cfg)
T.caso_a_venda_continua_travada_e_o_409_aparece_sem_a_data()
"""),
    ("trava_sem_interruptor",
     "a chave `venda.congelada` nao se le: a saida de venda abre-se",
     """
from mtgvault import fases
fases.congelada = lambda cfg=None: False
T.caso_a_venda_continua_travada_e_o_409_aparece_sem_a_data()
"""),
    ("trava_nao_se_levanta",
     "o interruptor deixa de mandar: travada para sempre, nem ele a abre",
     """
from mtgvault import fases
fases.congelada = lambda cfg=None: True
T.caso_levantar_o_interruptor_destranca_e_baixar_volta_a_travar()
"""),
    ("recusa_sem_dizer_como_se_abre",
     "o 409 recusa e NAO diz o comando que destranca (ele fica a procurar)",
     """
from mtgvault import fases
fases.motivo_congelado = lambda ate="", hoje="": "a venda esta congelada."
T.caso_a_venda_continua_travada_e_o_409_aparece_sem_a_data()
"""),
    ("config_ainda_tem_a_data",
     "a data de 12/10 fica no bloco `venda`: volta a levantar-se sozinha",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['venda']['congelado_ate'] = '2026-10-12'
T.CFG_REAL = cfg
T.caso_o_config_a_serio_trava_a_venda_sem_a_data_de_12_10()
"""),
    ("historico_apagado",
     "a data antiga e o texto dela foram APAGADOS em vez de arquivados",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['venda'].pop('_congelado_ate_historico', None)
T.CFG_REAL = cfg
T.caso_o_config_a_serio_trava_a_venda_sem_a_data_de_12_10()
"""),
    ("gravar_reformata_o_config",
     "o `gravar_congelada` escreve com json.dump(indent=2) — o commit ac1f776",
     """
import json
from mtgvault import fases, sources
def bruto(travar, path=None):
    cfg = json.loads(Path(path).read_text(encoding='utf-8'))
    cfg.setdefault('venda', {})['congelada'] = bool(travar)
    Path(path).write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                          encoding='utf-8')
    sources._CFG_CACHE.clear()
    return {'antes': not travar, 'congelada': bool(travar)}
fases.gravar_congelada = bruto
T.caso_o_cli_destranca_e_escreve_pelo_configio()
"""),
    # ------------------------------------- 2) A RAZAO DO DUEL COMMANDER
    ("razao_do_dc_nao_escrita",
     "a razao sai do config: volta a funcionar por acidente de configuracao",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['venda'].pop('_reservar_rl_formatos', None)
T.CFG_REAL = cfg
T.caso_a_razao_do_duel_commander_esta_escrita_no_config()
"""),
    ("duel_commander_reserva_rl",
     "o duel-commander entra no `reservar_rl_formatos`: segura RL de decks que ele nao joga",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['venda']['reservar_rl_formatos'] = ['legacy', 'duel-commander']
T.CFG_REAL = cfg
T.caso_a_razao_do_duel_commander_esta_escrita_no_config()
"""),
    ("um_dos_sete_entra_na_lista",
     "um dos 7 nomes passa a estar na lista do deck dele: a decisao estava errada",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['listas_escolhidas']['duel-commander']['cards'].append(['main', 'Time Spiral', 1])
T.CFG_REAL = cfg
T.caso_nenhum_dos_sete_entra_na_lista_do_deck_de_duel_commander()
"""),
    # ------------------------------------------------- 3) O WHIPFLARE
    ("excepcao_volta_a_pendente",
     "o `aplicado` volta a false: o nonfoil nao fecha o slot e a lista nunca fica satisfeita",
     """
from mtgvault import loadout
_real = loadout.urgencia_da_compra
def pendente(s, nm, cfg=None, hoje=None, urgentes=None):
    u = _real(s, nm, cfg, hoje, urgentes)
    if u and u.get('material_pendente'):
        u['material_pendente']['aplicado'] = False
        u['pendente'] = True
    return u
loadout.urgencia_da_compra = pendente
T.caso_o_whipflare_nonfoil_satisfaz_a_lista_de_compras()
"""),
    ("excepcao_sem_marca_provisoria",
     "a excepcao fica decidida mas NAO marcada provisoria: a troca cai no esquecimento",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
for x in cfg['compras_urgentes']:
    (x.get('material_pendente') or {}).pop('provisoria', None)
T.CFG_REAL = cfg
T.caso_a_excepcao_do_whipflare_esta_decidida_e_nao_pendente()
"""),
    ("excepcao_ainda_diz_pendente",
     "o config continua a dizer PENDENTE DE DECISAO depois de ele ter decidido",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
for x in cfg['compras_urgentes']:
    mp = x.get('material_pendente') or {}
    if mp: mp['estado'] = 'PENDENTE DE DECISAO DO ANDRE'
T.CFG_REAL = cfg
T.caso_a_excepcao_do_whipflare_esta_decidida_e_nao_pendente()
"""),
    ("vigia_sem_verificador",
     "o kind entra na tabela e NAO tem quem o corra (a vigia que nao vigia)",
     """
from mtgvault import watchlist
watchlist.VERIFICADORES = {k: v for k, v in watchlist.VERIFICADORES.items()
                           if k != 'preco_impressao'}
T.caso_a_vigia_do_foil_esta_inscrita_e_corre()
"""),
    ("vigia_nao_avisa_no_alvo",
     "a vigia le o preco e NUNCA avisa: ele nunca sabe que pode trocar",
     """
from mtgvault import watchlist
_real = watchlist.check_preco_impressao
def cega(con, wid):
    r = _real(con, wid); r['avisar'] = False; return r
watchlist.check_preco_impressao = cega
T.caso_a_vigia_do_foil_esta_inscrita_e_corre()
"""),
    ("vigia_sem_preco_avisa_a_zero",
     "sem cotacao o preco vale 0 EUR: a vigia dispara o aviso mais alto possivel",
     """
from mtgvault import watchlist
_real = watchlist.check_preco_impressao
def zero(con, wid):
    r = _real(con, wid)
    if r.get('preco') is None:
        r['preco'] = 0.0; r['avisar'] = True; r.pop('error', None)
        r['found'] = True
    return r
watchlist.check_preco_impressao = zero
T.caso_a_vigia_do_foil_esta_inscrita_e_corre()
"""),
    ("vigia_segue_a_cadeia_em_vigor",
     "a vigia le pela cadeia (so cardtrader) em vez da fonte inscrita: nunca tem preco",
     """
from mtgvault import precos, watchlist
_real = watchlist._vigia_preco_notas
watchlist._vigia_preco_notas = lambda w: {
    **_real(w), 'fonte': (precos.fontes() or ('cardtrader',))[0]}
precos.fontes = lambda cfg=None: ('cardtrader',)
T.caso_a_vigia_do_foil_esta_inscrita_e_corre()
"""),
    ("vigia_inscreve_o_que_nao_existe",
     "inscreve-se uma vigia sobre uma impressao que nao existe naquele acabamento",
     """
from mtgvault import watchlist
_add = watchlist.add
def sem_crivo(con, nome, set_code, finish, alvo_eur, fmt, fonte='cardmarket',
              porque='', collector_number=None):
    r = con.execute('SELECT scryfall_id FROM cards WHERE name = ? AND set_code = ?',
                    (nome, set_code.lower())).fetchone()
    wid = _add(con, 'preco_impressao',
               watchlist.chave_preco(r['scryfall_id'], finish), nome, fmt, '{}')
    return {'id': wid, 'scryfall_id': r['scryfall_id'], 'rotulo': nome,
            'alvo_eur': alvo_eur, 'fonte': fonte}
watchlist.vigiar_preco = sem_crivo
T.caso_a_vigia_nao_se_inscreve_sobre_uma_impressao_que_nao_existe()
"""),
    ("kind_fora_do_check",
     "o kind novo nao entra no CHECK: o `watchlist.add` da IntegrityError",
     """
from mtgvault import db
db.KINDS_VIGIA = ('mtgo_player', 'moxfield', 'archetype', 'mtgtop8_archetype')
T.caso_o_kind_novo_entra_no_check_e_nao_perde_as_vigias_antigas()
"""),
    ("migracao_so_olha_para_o_ultimo_kind",
     "a condicao volta a ser «falta o mtgtop8_archetype»: numa base que ja o tenha, o kind novo fica fora",
     """
from mtgvault import db
_real = db._migrate
def so_o_ultimo(con):
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name='watched'").fetchone()
    if sql and 'mtgtop8_archetype' in (sql['sql'] or ''):
        return          # ja tem o ultimo kind: nao reconstroi (o defeito)
    _real(con)
db._migrate = so_o_ultimo
T.caso_o_kind_novo_entra_no_check_e_nao_perde_as_vigias_antigas()
"""),
]

MOLDE = """
import sys
from pathlib import Path
RAIZ = Path(r"{raiz}")
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ))
import test_decisoes_1004_fecho as T
{corpo}
print("PASSOU — e nao devia")
"""


def main() -> int:
    maus = []
    for nome, o_que, corpo in ALVOS:
        src = MOLDE.format(raiz=RAIZ, corpo=corpo)
        p = subprocess.run([sys.executable, "-c", src], capture_output=True,
                           text=True, cwd=RAIZ, encoding="utf-8", errors="replace")
        ok = p.returncode != 0
        print(f"[{'chumba' if ok else 'PASSA!'}] {nome}: {o_que}")
        if not ok:
            maus.append(nome)
        else:
            linhas = [x for x in (p.stdout + p.stderr).strip().splitlines()
                      if x.strip()]
            if linhas:
                print(f"           -> {linhas[-1][:150]}")
    print()
    if maus:
        print(f"{len(maus)} de {len(ALVOS)} NAO chumbaram: {', '.join(maus)}")
        return 1
    print(f"os {len(ALVOS)} alvos chumbam sem o trabalho feito")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
