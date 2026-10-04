"""Corre UM caso do redesenho de 2026-10-04 com UMA peca neutralizada.

Noutro processo, como os outros `_chumba_*`: os modulos de teste fixam coisas no
import e metade do que aqui se desliga mexe em estado de modulo.

    py tests/_chumba_redesenho.py <alvo> <caso>

Sai 0 se o caso PASSOU (mau: a peca nao fazia falta) e != 0 se chumbou (bom).
Sem argumentos, corre os pares todos e resume.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))

# (alvo, modulo_de_teste, caso)
PARES = [
    # --- o publicador -------------------------------------------------------
    ("carimbo_nao_normalizado", "test_publicar",
     "caso_o_carimbo_sozinho_nao_e_uma_diferenca"),
    ("carimbo_nao_normalizado", "test_publicar",
     "caso_duas_passagens_seguidas_nao_dao_mudanca"),
    ("galeria_escreve", "test_publicar",
     "caso_publicar_nao_escreve_na_coleccao"),
    ("galeria_nao_grava", "test_publicar",
     "caso_a_galeria_do_daily_continua_a_gravar_o_historico"),
    ("falta_uma_pagina", "test_publicar", "caso_a_lista_e_a_mesma_do_daily"),
    ("vault_db_publicavel", "test_publicar",
     "caso_o_vault_db_nao_entra_nos_publicaveis"),
    ("sem_a_mais", "test_publicar", "caso_as_partes_que_sobram_sao_denunciadas"),
    # --- os tokens ----------------------------------------------------------
    ("token_fora_do_tema", "test_tokens",
     "caso_os_tokens_de_estado_vivem_na_casca"),
    ("var_inexistente", "test_tokens", "caso_todo_o_var_usado_esta_definido"),
    ("erro_com_cor_a_mao", "test_tokens",
     "caso_os_estados_de_erro_e_carregamento_nao_tem_cor_a_mao"),
    ("mais_uma_cor", "test_tokens", "caso_a_deriva_de_cores_nao_cresce"),
    ("sem_raios", "test_tokens", "caso_a_escala_nao_e_so_cor"),
    # --- a arvore -----------------------------------------------------------
    ("seccoes_antigas", "test_paginas",
     "caso_as_seccoes_do_menu_sao_as_que_ele_pediu"),
    ("geradores_a_mao", "test_paginas",
     "caso_todas_as_paginas_definem_as_variaveis_que_usam"),
]


def _todos() -> int:
    maus = []
    for alvo, mod, caso in PARES:
        r = subprocess.run([sys.executable, __file__, alvo, mod, caso],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        ok = r.returncode == 0
        print(f"  {'MAU (passou)' if ok else 'chumbou (bom)':<16} "
              f"{alvo} -> {mod}.{caso}")
        if ok:
            maus.append((alvo, mod, caso))
    print(f"\n{len(PARES) - len(maus)}/{len(PARES)} pares chumbam como devem")
    return 1 if maus else 0


if len(sys.argv) < 4:
    sys.exit(_todos())

alvo, modulo, nome = sys.argv[1], sys.argv[2], sys.argv[3]

from mtgvault import paginas, publicar                        # noqa: E402
from mtgvault import site_shell as shell                      # noqa: E402

# --- o publicador -----------------------------------------------------------
if alvo == "carimbo_nao_normalizado":
    # O vault de ontem: comparar sem tirar o `_gerado_em`. E o commit por
    # relogio a cada meia hora, para sempre.
    publicar.normalizar = lambda rel, texto: texto

elif alvo == "galeria_escreve":
    # A Galeria a gravar o ponto do dia tambem quando se publica: e a tarefa a
    # envenenar o proprio sossego.
    publicar.SO_LEITURA = {}

elif alvo == "galeria_nao_grava":
    # O outro lado: a Galeria a deixar de gravar o historico por omissao, e o
    # grafico da evolucao a parar sem ninguem dar por isso.
    import collection_gallery
    _real = collection_gallery.build

    def _sem(con, out_path, *, historico=False):              # noqa: ARG001
        return _real(con, out_path, historico=False)
    collection_gallery.build = _sem

elif alvo == "falta_uma_pagina":
    publicar.PAGINAS = [p for p in publicar.PAGINAS if p[1] != "decks.html"]

elif alvo == "vault_db_publicavel":
    publicar.PUBLICAVEIS = [*publicar.PUBLICAVEIS, "data/vault.db"]

elif alvo == "sem_a_mais":
    # A comparacao a nao dar pelas partes que deixaram de existir: uma caixa
    # que saiu do config fica a responder para sempre.
    _real_c = publicar.comparar

    def _cego(prova, real):
        d = _real_c(prova, real)
        d["a_mais"] = []
        return d
    publicar.comparar = _cego

# --- os tokens --------------------------------------------------------------
elif alvo == "token_fora_do_tema":
    shell.TEMA = shell.TEMA.replace("--ok-soft:#0f2a1c;", "")

elif alvo == "var_inexistente":
    # O `color:var(--text)` que viveu na Arrumacao sem ninguem dar por ele.
    import test_tokens as _t
    _real_txt = _t._texto

    def _com_text(f):
        t = _real_txt(f)
        return t + "\n .x{color:var(--token-que-nao-existe)}\n" if f == "arrumacao.py" else t
    _t._texto = _com_text

elif alvo == "erro_com_cor_a_mao":
    paginas.CSS_DADOS = paginas.CSS_DADOS.replace(
        "var(--bad-soft)", "#2a1618")

elif alvo == "mais_uma_cor":
    import test_tokens as _t
    _real_txt2 = _t._texto

    def _mais(f):
        t = _real_txt2(f)
        # tantas quantas o tecto, para passar do limite
        return t + "\n .y{color:#abcdef}" * 3 if f == "decks.py" else t
    _t._texto = _mais

elif alvo == "sem_raios":
    shell.TEMA = shell.TEMA.replace("--sombra:", "--xsombra:")

# --- a arvore ---------------------------------------------------------------
elif alvo == "seccoes_antigas":
    shell.SECCOES = [("", shell.SECCOES[0][1]),
                     ("Decks", shell.SECCOES[1][1]),
                     ("Coleção", shell.SECCOES[2][1]),
                     ("Metagame", shell.SECCOES[3][1]),
                     ("Compras e venda", shell.SECCOES[4][1])]

elif alvo == "geradores_a_mao":
    # A lista escrita a mao de 2026-09-24: sem a Arrumacao nem a aba Decks.
    import test_paginas as _p
    _p.GERADORES = ["inicio.py", "deckboxes.py", "metagame.py",
                    "meta_coverage.py", "showcase.py", "colecao_cor.py",
                    "caixarl.py", "reservedlist.py", "collection_gallery.py",
                    "comandantes.py"]
    # e o `var(--text)` de volta ao sitio onde viveu
    import pathlib
    _arr = pathlib.Path(__file__).resolve().parent.parent / "arrumacao.py"
    _txt = _arr.read_text(encoding="utf-8")
    _arr.write_text(_txt.replace("padding:8px 10px;color:var(--ink)}",
                                 "padding:8px 10px;color:var(--text)}"),
                    encoding="utf-8")
    import atexit
    atexit.register(lambda: _arr.write_text(_txt, encoding="utf-8"))

else:
    print(f"alvo desconhecido: {alvo}")
    sys.exit(2)

mod = __import__(modulo)
caso = getattr(mod, nome)
try:
    caso()
except AssertionError as e:
    print(f"chumbou como devia: {str(e)[:300]}")
    sys.exit(1)
except Exception as e:                                        # noqa: BLE001
    print(f"chumbou por EXCEPCAO ({type(e).__name__}): {str(e)[:300]}")
    sys.exit(1)
print("PASSOU — a peca nao fazia falta")
sys.exit(0)
