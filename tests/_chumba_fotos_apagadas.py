"""A prova de que o `test_fotos_apagadas.py` chumba sem o trabalho de 04/10/2026.

Um alvo por passagem, num processo próprio (como o `_chumba_prazo.py`): desliga-se
uma peça e exige-se VERMELHO. Corre-se à mão:

    py tests\\_chumba_fotos_apagadas.py

Os alvos:
  1. a base com os 723 `photo_path` de volta (é o backup de hoje) — os casos que
     lêem a base a sério têm de chumbar;
  2. o config com a campanha LIGADA — o caso do interruptor tem de chumbar;
  3. a pasta do arquivo com uma imagem dentro — o caso da pasta tem de chumbar;
  4. o CSV do registo apagado — o caso do registo tem de chumbar;
  5. o `confirmado.metades` a devolver só uma metade — o caso das metades tem de
     chumbar (é a asserção que impede meia verdade com cara de verdade).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[0]
TESTE = AQUI / "test_fotos_apagadas.py"

GUIAO = r"""
import sys, os
sys.path.insert(0, r'{raiz}')
sys.path.insert(0, r'{aqui}')
{preparo}
import test_fotos_apagadas as T
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
        print(r.stdout[-800:], r.stderr[-800:])
        return False
    maus = eval(linha[2:])                                    # noqa: S307
    faltam = [a for a in alvos if not any(m.startswith(a) for m in maus)]
    if faltam:
        print(f"  NAO CHUMBOU {nome} -> {faltam}")
        return False
    print(f"  chumba OK   {nome} ({len(maus)} casos vermelhos)")
    return True


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    ok = True

    # 1. a base de ANTES (o backup de hoje, com os 723 photo_path)
    backup = RAIZ / "data" / "backups" / "vault-2026-10-04-antes-de-apagar-fotos.db"
    if backup.exists():
        falso = tmp / "repo1"
        (falso / "data").mkdir(parents=True)
        shutil.copy2(backup, falso / "data" / "vault.db")
        shutil.copy2(RAIZ / "colecao_config.json", falso / "colecao_config.json")
        ok &= passagem(
            "a base com os 723 photo_path de volta",
            f"import test_fotos_apagadas as _p\nimport pathlib\n"
            f"_p.RAIZ = pathlib.Path(r'{falso}')",
            ["caso_a_base_a_serio_nao_tem_uma_unica_referencia_a_foto"])
    else:
        print("  -- sem backup: salta o alvo 1")

    # 2. o config com a campanha LIGADA
    falso2 = tmp / "repo2"
    falso2.mkdir(parents=True)
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    cfg["revalidacao"] = {"desde": "2026-09-20", "alvo": None,
                          "foto_manda": True}
    cfg.pop("_revalidacao_desligada", None)
    (falso2 / "colecao_config.json").write_text(
        json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (falso2 / "data").mkdir()
    ok &= passagem(
        "o config com a campanha ligada",
        f"import test_fotos_apagadas as _p\nimport pathlib\n"
        f"_p.RAIZ = pathlib.Path(r'{falso2}')",
        ["caso_a_campanha_esta_desligada_no_config_a_serio"])

    # 3. a pasta do arquivo com uma imagem dentro + 4. o CSV apagado
    falso3 = tmp / "repo3"
    (falso3 / "data" / "fotos" / "anteriores").mkdir(parents=True)
    (falso3 / "data" / "fotos" / "anteriores" / "sobrou.jpg").write_bytes(b"x")
    shutil.copy2(RAIZ / "data" / "vault.db", falso3 / "data" / "vault.db")
    shutil.copy2(RAIZ / "colecao_config.json", falso3 / "colecao_config.json")
    ok &= passagem(
        "uma imagem a sobrar no arquivo e o CSV sem estar lá",
        f"import test_fotos_apagadas as _p\nimport pathlib\n"
        f"_p.RAIZ = pathlib.Path(r'{falso3}')",
        ["caso_a_pasta_do_arquivo_ficou_vazia_mas_existe",
         "caso_o_csv_tem_uma_linha_por_copia_que_tinha_foto"])

    # 5. as metades a deixarem de somar
    ok &= passagem(
        "o confirmado.metades a esconder uma metade",
        "from mtgvault import confirmado as _cf\n"
        "_orig = _cf.metades\n"
        "_cf.metades = lambda c, t, **k: {'confirmado': c, 'declarado': 0,\n"
        "    'por_confirmar': 0, 'total': t, 'frase': 'x'}",
        ["caso_as_metades_continuam_a_somar_o_total"])

    print()
    print("TODOS OS ALVOS CHUMBAM" if ok else "ALGUM ALVO NAO CHUMBOU")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
