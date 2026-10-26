"""A pasta `_scratch/` e os 10 CSVs antigos da raiz ficam FORA do Git.

Ordem mtg-aprovadas-1026 (aprovada pelo Andre a 25/10/2026): ficam no disco,
saem do indice (`git rm --cached`) e entram no `.gitignore`. O `owned.csv` e o
`price_overrides.csv` NAO saem: `import_owned.py` e `refresh_collection.py` lem-nos.
"""
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CSVS = ["4_5c_control.csv", "affinity_kappa.csv", "blue_farm.csv", "cloud.csv",
        "enchantress.csv", "exemplo_colecao.csv", "grinding_emry.csv",
        "ill_gotten_gains.csv", "legacy.csv", "oath_of_druids.csv"]
FICAM = ["owned.csv", "price_overrides.csv"]


def _rastreados():
    if not shutil.which("git") or not (RAIZ / ".git").exists():
        return None
    p = subprocess.run(["git", "-C", str(RAIZ), "ls-files"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    return p.stdout.splitlines() if p.returncode == 0 else None


def caso_scratch_e_csvs_antigos_nao_estao_no_git():
    r = _rastreados()
    if r is None:
        print("sem git - saltado")
        return
    assert not [f for f in r if f.startswith("_scratch/")], "a _scratch/ voltou ao Git"
    voltaram = [c for c in CSVS if c in r]
    assert not voltaram, f"CSVs antigos de volta ao Git: {voltaram}"
    for c in FICAM:
        assert c in r, f"{c} e lido pelo codigo e tem de continuar no Git"


def caso_o_gitignore_cobre_a_scratch_e_os_csvs():
    ig = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "_scratch/" in ig
    for c in CSVS:
        assert "/" + c in ig, f"{c} nao esta no .gitignore"
    for c in FICAM:
        assert "/" + c not in ig and c not in ig, f"{c} nao pode ser ignorado"


def caso_nenhum_codigo_le_os_ficheiros_que_saem():
    """O portao de 15/10: antes de tirar ficheiros rastreados, confirmar que
    nenhum codigo nem teste os le (por nome)."""
    import re
    nomes = [c for c in CSVS]
    pad = re.compile("|".join(re.escape(n) for n in nomes))
    achados = []
    for f in list(RAIZ.glob("*.py")) + list((RAIZ / "mtgvault").glob("*.py")) \
            + list((RAIZ / "tests").glob("*.py")) + list((RAIZ / "scripts").glob("*.py")):
        if f.name == Path(__file__).name:
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        if pad.search(t):
            achados.append(f.name)
    assert not achados, f"codigo que menciona os CSVs que saem do Git: {achados}"


if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("caso_"):
            f()
            print("ok", n)
