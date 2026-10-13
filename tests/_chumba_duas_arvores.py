"""Prova de que o `test_duas_arvores` CHUMBA com cada guarda desligada (um
processo por alvo — um alvo que apagasse a pasta errada não pode envenenar o
seguinte). Corre-se à mão: `py _chumba_duas_arvores.py`."""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

ALVOS = {
    # Sem a guarda das imagens: uma pasta de carta qualquer vai-se inteira.
    "apaga_com_imagens": (
        "import shutil; from mtgvault import fotos as F\n"
        "def _cega(p, b):\n"
        "    p = __import__('pathlib').Path(p)\n"
        "    if p.is_dir(): shutil.rmtree(p); return True\n"
        "    return False\n"
        "F.apagar_pasta_feita = _cega\n",
        "caso_uma_pasta_com_imagens_nunca_se_apaga"),
    # A prova conta cópias dadas como não encontradas: a pasta não volta.
    "nao_volta_na_correccao": (
        "from mtgvault import fotos as F, collection as C\n"
        "C.jogaveis = lambda *a, **k: \"cp.purpose = 'player'\"\n",
        "caso_o_gerador_cria_nao_ressuscita_e_devolve_numa_correccao"),
    # Sem devolver a foto que parou: fica em pendentes e a pasta não a tem.
    "nao_devolve": (
        "from mtgvault import collection as C\n"
        "C._devolver_a_pasta = lambda *a, **k: False\n",
        "caso_a_foto_que_parou_volta_a_pasta_com_o_mesmo_nome"),
    # Sem apagar a pasta da carta depois de a foto entrar.
    "nao_apaga_a_feita": (
        "from mtgvault import fotos as F\n"
        "F.apagar_pasta_feita = lambda *a, **k: False\n",
        "caso_a_foto_que_entrou_vai_para_processados_e_a_pasta_some"),
}


def main():
    falhas = 0
    for nome, (patch, caso) in ALVOS.items():
        codigo = ("import sys; sys.path.insert(0, r'%s')\n" % AQUI
                  + "import test_duas_arvores as T\n" + patch
                  + "T.%s()\n" % caso)
        p = subprocess.run([sys.executable, "-c", codigo], cwd=str(AQUI),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        chumbou = p.returncode != 0
        print(f"{'CHUMBA' if chumbou else 'PASSA!'}  {nome}  ({caso})")
        falhas += 0 if chumbou else 1
    print(f"\n{len(ALVOS) - falhas} de {len(ALVOS)} alvos chumbam")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
