"""Prova que o `test_decisoes_1004_noite.py` CHUMBA sem o trabalho feito.

Corre-se a mao: `py tests\\_chumba_decisoes_noite.py`.

UM PROCESSO POR PAR, de proposito (a licao do `_chumba_prazo` de 01/10): cada
alvo desliga uma peca — uns por patch em memoria, outros reescrevendo o config —
e meia dezena deles envenenava os seguintes no mesmo processo. Cada par corre
isolado e tem de dar NAO-ZERO.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# (alvo, o que se desliga, codigo que o neutraliza antes de correr o caso)
ALVOS = [
    ("sideboard_sem_aplicar",
     "o config volta a 4 Consign e zero Whipflare (a proposta nao aplicada)",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
m = cfg['listas_escolhidas']['modern']
m['cards'] = [c for c in m['cards'] if c[1] != 'Whipflare']
for c in m['cards']:
    if c[0] == 'side' and c[1] == 'Consign to Memory':
        c[2] = 4
m['proposta_sideboard']['estado'] = 'PROPOSTA NAO APLICADA'
T.CFG_REAL = cfg
T.caso_o_sideboard_do_modern_tem_3_consign_1_whipflare_e_soma_15()
"""),
    # O alvo neutraliza a PEÇA que le a chave e nao o ficheiro: cada caso do teste
    # escreve o seu proprio config (e e assim que fica independente), por isso
    # apagar lá a chave era desfeito pela primeira linha do caso.
    ("faltas_sem_urgencia",
     "a chave `compras_urgentes` nao se le: a falta nao sabe a data-limite",
     """
from mtgvault import loadout
loadout.compras_urgentes = lambda cfg=None: {}
T.caso_o_whipflare_aparece_nas_faltas_com_a_data_limite()
"""),
    ("urgencia_sem_dias",
     "o `dias` passa a ser escrito e nao calculado (devolve sempre None)",
     """
from mtgvault import loadout
_real = loadout.urgencia_da_compra
def sem_dias(s, nm, cfg=None, hoje=None, urgentes=None):
    u = _real(s, nm, cfg, hoje, urgentes)
    if u: u['dias'] = None; u['passou'] = False
    return u
loadout.urgencia_da_compra = sem_dias
T.caso_o_whipflare_aparece_nas_faltas_com_a_data_limite()
"""),
    ("excepcao_nao_sugere_nonfoil",
     "a excepcao de material nao se le: a compra volta a pedir foil a 20,20 EUR",
     """
from mtgvault import loadout
loadout._excepcao_de_material = lambda s, nm, cfg=None, urgentes=None: None
T.caso_a_excepcao_do_foil_fica_pendente_e_nao_decidida()
"""),
    ("excepcao_pendente_vale_na_alocacao",
     "a excepcao PENDENTE passa a valer na alocacao (decide por ele)",
     """
from mtgvault import loadout
_real = loadout.resolve_slots
def todas(con, cfg_slots=None, foil_cache=None):
    out = _real(con, cfg_slots, foil_cache)
    urg = loadout.compras_urgentes()
    for s in out:
        s['excepcoes_material'] = {
            k[1]: (x.get('material_pendente') or {}).get('sugerido_entretanto')
            for k, x in urg.items()
            if k[0] == s.get('slot') and (x.get('material_pendente') or {}).get('sugerido_entretanto')}
    return out
loadout.resolve_slots = todas
T.caso_a_excepcao_do_foil_fica_pendente_e_nao_decidida()
"""),
    ("pagina_nao_leva_a_urgencia",
     "o payload nao leva a ficha: o motor sabe a data-limite e a pagina cala-se",
     """
import deckboxes
_real = deckboxes.payload
def sem_urg(con, rep, editable=False, token=""):
    p = _real(con, rep, editable, token)
    for c in p["caixas"]:
        for w in c.get("wantlist") or []:
            w.pop("urg", None)
    for g in p.get("compras") or []:
        g["urg"] = None
    return p
deckboxes.payload = sem_urg
T.caso_a_pagina_mostra_a_data_limite()
"""),
    ("chip_definido_e_nao_chamado",
     "o `chipUrg` existe no JS e ninguem o chama (o mesmo que nao existir)",
     """
import deckboxes
_real = deckboxes.js_texto
deckboxes.js_texto = lambda *a, **k: _real(*a, **k).replace('+ chipUrg(m.urg)', '')
T.caso_a_pagina_mostra_a_data_limite()
"""),
    # O defeito MEU de 04/10: `in ("foil","prefere_foil")` em vez de `== "foil"`.
    ("prefere_foil_orcamenta_a_foil",
     "o preco da compra segue o `prefere_foil` e orcamenta a FOIL (+40,38 EUR)",
     """
from mtgvault import loadout
_real = loadout.card_price
def caro(con, nm, finish, *a, **k):
    return _real(con, nm, 'foil', *a, **k)
loadout.card_price = caro
T.caso_uma_caixa_prefere_foil_orcamenta_o_nonfoil()
"""),
    ("limiar_ainda_a_10",
     "o config continua com o limiar das staples a 10 %",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['reserva']['staples_premodern_pct'] = 10
T.CFG_REAL = cfg
T.caso_o_limiar_da_reserva_e_20()
"""),
    ("limiar_sem_razao",
     "o limiar muda e ninguem escreve porque (daqui a um mes nao se sabe)",
     """
import json
cfg = json.loads((RAIZ / 'colecao_config.json').read_text(encoding='utf-8'))
cfg['reserva'].pop('_staples_premodern_pct', None)
T.CFG_REAL = cfg
T.caso_o_limiar_da_reserva_e_20()
"""),
    ("staples_ignoram_o_corte",
     "o `staples_sideboard` deixa de respeitar o corte que lhe passam",
     """
from mtgvault import fases
_real = fases.staples_sideboard
fases.staples_sideboard = lambda con, fmt='premodern', corte=None, desde=None, cache=None: \\
    _real(con, fmt, 10, desde, cache)
T.caso_a_lista_de_candidatas_muda_com_o_limiar()
"""),
    ("sem_parser_do_arquetipo",
     "o `parse_archetype_rows` nao existe: a pagina do arquetipo nao se le",
     """
from mtgvault import mtgtop8
mtgtop8.parse_archetype_rows = lambda html: []
T.caso_o_parser_do_arquetipo_le_a_pagina_real()
"""),
    ("parser_sem_posicao",
     "o parser le tudo menos a COLOCACAO: nao ha como saber a melhor lista",
     """
from mtgvault import mtgtop8
_real = mtgtop8.parse_archetype_rows
def sem_pos(html):
    rows = _real(html)
    for r in rows: r['posicao'] = ''
    return rows
mtgtop8.parse_archetype_rows = sem_pos
T.caso_o_parser_do_arquetipo_le_a_pagina_real()
"""),
    ("vigia_inscrita_sem_verificador",
     "o kind novo entra na tabela e NAO tem quem o corra",
     """
from mtgvault import watchlist
watchlist.VERIFICADORES = {k: v for k, v in watchlist.VERIFICADORES.items()
                           if k != 'mtgtop8_archetype'}
T.caso_a_vigia_do_arquetipo_corre_a_serio()
"""),
    ("vigia_nao_ve_lista_nova",
     "a vigia guarda o snapshot mas nao compara: lista nova passa calada",
     """
from mtgvault import watchlist
_real = watchlist.check_mtgtop8_archetype
def cego(con, wid):
    r = _real(con, wid); r['novas'] = []; return r
watchlist.check_mtgtop8_archetype = cego
T.caso_a_vigia_do_arquetipo_corre_a_serio()
"""),
    ("vigia_nao_ve_a_melhor_mudar",
     "a vigia nao repara que a melhor classificada trocou",
     """
from mtgvault import watchlist
_real = watchlist.check_mtgtop8_archetype
def cego(con, wid):
    r = _real(con, wid); r['melhor_mudou'] = False; return r
watchlist.check_mtgtop8_archetype = cego
T.caso_a_vigia_do_arquetipo_corre_a_serio()
"""),
    ("kind_desconhecido_salta_calado",
     "o `check_all` volta a saltar em silencio o kind que nao conhece",
     """
from mtgvault import watchlist
def antigo(con):
    out = []
    for w in con.execute('SELECT * FROM watched WHERE active = 1 ORDER BY id'):
        if w['kind'] == 'mtgo_player':
            out.append(watchlist.check_mtgo_player(con, w['id']))
        elif w['kind'] == 'moxfield':
            out.append(watchlist.check_moxfield(con, w['id']))
    return out
watchlist.check_all = antigo
T.caso_um_kind_sem_verificador_nao_passa_calado()
"""),
    ("sem_migracao_da_watched",
     "a migracao do CHECK nao corre: o kind novo nao entra na base dele",
     """
from mtgvault import db
_real = db._migrate
def sem(con):
    _real(con)
    con.commit()
    con.execute('PRAGMA foreign_keys = OFF')
    con.executescript('''
        CREATE TABLE w2 (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('mtgo_player','moxfield','archetype')),
            key TEXT NOT NULL, label TEXT NOT NULL, format TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            last_checked TEXT, last_hash TEXT, notes TEXT,
            UNIQUE (kind, key, format));
        INSERT INTO w2 SELECT id,kind,key,label,format,active,last_checked,last_hash,notes FROM watched;
        DROP TABLE watched; ALTER TABLE w2 RENAME TO watched;''')
    con.commit()
    con.execute('PRAGMA foreign_keys = ON')
db._migrate = sem
T.caso_a_migracao_da_watched_nao_perde_o_historico()
"""),
    ("migracao_leva_o_historico",
     "a migracao faz DROP com as FK ligadas: o CASCADE apaga os snapshots",
     """
from mtgvault import db
_real = db._migrate
def cascata(con):
    sql = con.execute("SELECT sql FROM sqlite_master WHERE name='watched'").fetchone()
    if sql and 'mtgtop8_archetype' not in (sql['sql'] or ''):
        con.executescript('''
            CREATE TABLE w2 (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL CHECK (kind IN ('mtgo_player','moxfield','archetype','mtgtop8_archetype')),
                key TEXT NOT NULL, label TEXT NOT NULL, format TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                last_checked TEXT, last_hash TEXT, notes TEXT,
                UNIQUE (kind, key, format));
            INSERT INTO w2 SELECT id,kind,key,label,format,active,last_checked,last_hash,notes FROM watched;
            DROP TABLE watched; ALTER TABLE w2 RENAME TO watched;''')
        con.commit()
        return
    _real(con)
db._migrate = cascata
T.caso_a_migracao_da_watched_nao_perde_o_historico()
"""),
]

MOLDE = """
import sys
from pathlib import Path
RAIZ = Path(r"{raiz}")
sys.path.insert(0, str(RAIZ / "tests"))
sys.path.insert(0, str(RAIZ))
import test_decisoes_1004_noite as T
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
            linhas = [x for x in (p.stdout + p.stderr).strip().splitlines() if x.strip()]
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
