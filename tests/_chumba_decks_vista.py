"""A prova de que o `test_decks_vista.py` chumba sem o trabalho de 04/10/2026.

Um alvo por passagem, num processo próprio (como o `_chumba_prazo.py`):
desliga-se uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_decks_vista.py

Um processo por alvo de propósito: metade do que aqui se desliga é um módulo
inteiro em memória (`marcas.posse`, `dv.partilha_do_formato`), e num processo só
o primeiro alvo envenenava os seguintes em silêncio.

Os alvos:
  1. a MARCA a deixar de ganhar ao inventário (o `posse` a ignorar a tabela);
  2. a marca a deixar de ser DISTINGUÍVEL (toda a origem a dizer `inventario`);
  3. o `request_id` ignorado — um retry volta a contar a dobrar;
  4. a regra do formato fixa em `dedicadas` (como se o `cartas_partilhadas` não
     existisse): os formatos rotativos voltam a somar;
  5. a regra fixa em `rotativas`: os dedicados deixam de somar;
  6. a `necessidade` a devolver só um dos dois números;
  7. a `reparticao` a dar tudo como próprio: nunca há partilhadas nem proxies;
  8. o `conta_do_deck` a juntar main e sideboard num total só;
  9. a PRECEDÊNCIA pela ordem de apresentação (a Artifact Land volta a cair em
     Artifact, que é o defeito que ele mandou corrigir);
 10. o grupo do COMANDANTE desligado;
 11. a ordem dos grupos por ordem alfabética;
 12. o `foto_manda` LIGADO: a colecção volta a ler-se como vazia;
 13. a casca a embutir uma imagem em base64;
 14. o índice dos dados a levar as cartas (adeus dados à parte).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[0]

GUIAO = r"""
import sys
sys.path.insert(0, r'{raiz}')
sys.path.insert(0, r'{aqui}')
import test_decks_vista as T
{preparo}
maus = []
for c in T.CASOS:
    if c.__name__ not in {alvos}:
        continue
    try:
        c()
    except BaseException as e:
        maus.append(c.__name__ + ': ' + type(e).__name__)
print('@@' + repr(maus))
"""


def passagem(nome: str, preparo: str, alvos: list[str]) -> bool:
    guiao = GUIAO.format(raiz=RAIZ, aqui=AQUI, preparo=preparo,
                         alvos=repr(set(alvos)))
    r = subprocess.run([sys.executable, "-c", guiao], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=AQUI)
    linha = next((l for l in r.stdout.splitlines() if l.startswith("@@")), None)
    if linha is None:
        print(f"  ?? {nome}: a passagem nem correu")
        print((r.stdout or "")[-900:], (r.stderr or "")[-900:])
        return False
    maus = eval(linha[2:])                                    # noqa: S307
    faltam = [a for a in alvos if not any(m.startswith(a) for m in maus)]
    if faltam:
        print(f"  NAO CHUMBOU {nome} -> {faltam}")
        return False
    print(f"  chumba OK   {nome} ({len(maus)} casos vermelhos)")
    return True


ALVOS = [
    # 1. a marca deixa de ganhar
    ("a marca a deixar de ganhar ao inventario",
     "from mtgvault import marcas\n"
     "marcas.posse = lambda con, inv=None, mks=None: "
     "{nm: {'q': q, 'origem': marcas.INVENTARIO, 'em': None} "
     " for nm, q in marcas.inventario(con).items()}",
     ["caso_a_marca_dele_ganha_ao_inventario",
      "caso_as_marcas_sobrevivem_ao_daily"]),
    # 2. a marca deixa de ser distinguivel
    ("a marca a deixar de se distinguir do inventario",
     "from mtgvault import marcas\n"
     "_p = marcas.posse\n"
     "marcas.posse = lambda *a, **k: {nm: dict(x, origem=marcas.INVENTARIO) "
     " for nm, x in _p(*a, **k).items()}",
     ["caso_as_marcas_sobrevivem_ao_daily"]),
    # 3. o request_id ignorado
    ("o request_id ignorado (um retry conta a dobrar)",
     "from mtgvault import marcas\n"
     "_a = marcas.ajustar\n"
     "marcas.ajustar = lambda con, nome, delta, request_id=None, origem='cli': "
     " _a(con, nome, delta, request_id=None, origem=origem)",
     ["caso_um_retry_nao_conta_a_dobrar"]),
    # 4. a regra fixa em dedicadas
    ("a regra do formato fixa em 'dedicadas' (sem cartas_partilhadas)",
     "from mtgvault import decks_vista as dv\n"
     "dv.partilha_do_formato = lambda fmt, regras=None: dv.DEDICADAS\n"
     "dv.e_rotativo = lambda fmt, regras=None: False",
     # O `caso_propria_passa_a_partilhada` NÃO entra aqui de propósito: ele
     # exercita a `reparticao`/`e_partilhada` directamente, sem passar pela
     # regra do formato — são duas peças e cada uma tem o seu alvo (a 7).
     ["caso_rotativas_a_mesma_carta_em_dois_decks_pede_uma",
      "caso_os_sleeves_contam_as_verdadeiras_e_os_proxies"]),
    # 5. a regra fixa em rotativas
    ("a regra do formato fixa em 'rotativas'",
     "from mtgvault import decks_vista as dv\n"
     "dv.partilha_do_formato = lambda fmt, regras=None: dv.ROTATIVAS\n"
     "dv.e_rotativo = lambda fmt, regras=None: True",
     ["caso_dedicadas_a_mesma_carta_em_dois_decks_pede_duas",
      "caso_os_sleeves_contam_as_verdadeiras_e_os_proxies"]),
    # 6. a necessidade com um numero so
    ("a necessidade a devolver so um dos dois numeros",
     "from mtgvault import decks_vista as dv\n"
     "_t = dv.totais_da_necessidade\n"
     "dv.totais_da_necessidade = lambda nec, pos: "
     " {k: v for k, v in _t(nec, pos).items() if k not in ('maximo', 'faltam_a_rodar')}",
     ["caso_os_dois_numeros_mostram_se_sempre_os_dois"]),
    # 7. tudo proprio: nunca ha partilhadas
    ("a reparticao a dar tudo como proprio (sem proxies)",
     "from mtgvault import decks_vista as dv\n"
     "dv.e_partilhada = lambda nm, rep: False",
     ["caso_propria_passa_a_partilhada_quando_marca_o_segundo_deck",
      "caso_os_sleeves_contam_as_verdadeiras_e_os_proxies"]),
    # 8. main e side juntos
    ("o conta_do_deck a juntar o main e o sideboard",
     "from mtgvault import decks_vista as dv\n"
     "_c = dv.conta_do_deck\n"
     "def _junta(d, pos):\n"
     "    r = _c(d, pos)\n"
     "    r['main'] = {'total': r['total'], 'tem': r['tem']}\n"
     "    r['side'] = {'total': 0, 'tem': 0}\n"
     "    return r\n"
     "dv.conta_do_deck = _junta",
     ["caso_o_sideboard_conta_a_parte_do_main"]),
    # 9. a precedencia pela ordem de apresentacao
    ("a precedencia pela ORDEM DE APRESENTACAO (Artifact antes de Land)",
     "from mtgvault import decks_vista as dv\n"
     "import re\n"
     "def _t(tl, comandante=False):\n"
     "    if comandante: return dv.COMANDANTE\n"
     "    s = (tl or '').split(' // ')[0]\n"
     "    for x in dv.ORDEM_TIPOS:\n"
     "        if x not in (dv.COMANDANTE, 'Outras') and re.search(r'\\b'+x+r'\\b', s):\n"
     "            return x\n"
     "    return 'Outras'\n"
     "dv.tipo_da_carta = _t",
     ["caso_artifact_creature_cai_em_creature_e_artifact_land_em_land",
      "caso_as_cartas_a_serio_caem_no_grupo_certo"]),
    # 10. sem grupo de comandante
    ("o grupo do COMANDANTE desligado",
     "from mtgvault import decks_vista as dv\n"
     "_t = dv.tipo_da_carta\n"
     "dv.tipo_da_carta = lambda tl, comandante=False: _t(tl)",
     ["caso_o_comandante_aparece_acima_dos_creature"]),
    # 11. ordem alfabetica
    ("a ordem dos grupos por ordem alfabetica",
     "from mtgvault import decks_vista as dv\n"
     "dv.ordenar_grupos = lambda g: sorted(set(g))",
     ["caso_a_ordem_dos_grupos_e_a_dele",
      "caso_o_comandante_aparece_acima_dos_creature"]),
    # 12. o foto_manda ligado
    ("o foto_manda LIGADO (a coleccao volta a ler-se como vazia)",
     "T.CFG['revalidacao'] = {'desde': '2026-09-20', 'alvo': None, "
     " 'foto_manda': True}",
     ["caso_a_regra_das_fotos_esta_desligada_e_a_coleccao_nao_e_vazia"]),
    # 13. a casca a embutir uma imagem
    ("a casca a embutir uma imagem em base64",
     "import decks as dp\n"
     "_c = dp.casca\n"
     "dp.casca = lambda: _c().replace('<body>', "
     " '<body><img src=\"data:image/gif;base64,R0lGODlhAQABAAAAACw=\">')",
     ["caso_a_pagina_nao_embebe_imagens_e_cabe_no_tecto"]),
    # 14. o indice a levar as cartas
    ("o indice dos dados a levar as cartas (adeus dados a parte)",
     "import decks as dp\n"
     "_d = dp.dados\n"
     "def _gordo(con, cfg=None, editavel=False):\n"
     "    i, p = _d(con, cfg, editavel)\n"
     "    i['tudo'] = p\n"
     "    return i, p\n"
     "dp.dados = _gordo",
     ["caso_cada_deck_vai_numa_parte_e_o_indice_nao_leva_cartas"]),
]


def main() -> int:
    ok = True
    for nome, preparo, alvos in ALVOS:
        ok &= passagem(nome, preparo, alvos)
    print("\n" + ("TODOS CHUMBAM, como tem de ser" if ok
                  else "HÁ ALVOS QUE NÃO CHUMBAM — o teste não está a trancar"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
