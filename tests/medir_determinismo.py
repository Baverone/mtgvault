"""TODAS as páginas saem iguais em DOIS PROCESSOS diferentes?

É a pergunta que decide se o `mtgvault-publicar` commita para sempre. Dentro do
mesmo processo a geração é estável; o que muda entre processos é a **ordem de
iteração de um `set`** — o Python aleatoriza o hash das strings a cada arranque.
Foi assim que o `data/paginas/cobertura/prints.json` saiu com as mesmas chaves e
o mesmo conteúdo noutra ordem, e por isso o `git` dava-o como alterado em cada
corrida sem um único dado ter mudado.

Vive em `tests/` e não num scratch porque é dele que o
`test_publicar.caso_as_paginas_sao_iguais_em_dois_processos` depende: um teste
que chamasse uma ferramenta fora do repositório passava na máquina de quem a
escreveu e **saltava em todas as outras** (é a nota do `medir_layout.py`).

    py tests/medir_determinismo.py            compara dois subprocessos
    py tests/medir_determinismo.py gerar <pasta>     (uso interno)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))


def _gerar(dest: Path) -> None:
    from mtgvault import db, publicar                          # noqa: PLC0415
    with db.session() as con:
        publicar.gerar(con, dest)


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "gerar":
        _gerar(Path(sys.argv[2]))
        return 0

    from mtgvault import publicar                              # noqa: PLC0415

    tmp = Path(tempfile.mkdtemp(prefix="mtg-determinismo-"))
    try:
        a, b = tmp / "a", tmp / "b"
        for d in (a, b):
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "gerar", str(d)], cwd=str(RAIZ),
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=900)
            if r.returncode != 0:
                print("a geracao falhou:", ((r.stdout or "") + (r.stderr or ""))[-800:])
                return 2

        maus, total = [], 0
        for pa in sorted(a.rglob("*")):
            if not pa.is_file():
                continue
            rel = pa.relative_to(a).as_posix()
            pb = b / rel
            total += 1
            if not pb.exists():
                maus.append((rel, "so existe numa das passagens"))
                continue
            ta = publicar.normalizar(
                rel, pa.read_text(encoding="utf-8", errors="replace"))
            tb = publicar.normalizar(
                rel, pb.read_text(encoding="utf-8", errors="replace"))
            if ta == tb:
                continue
            nota = f"{len(ta)} vs {len(tb)} bytes"
            if rel.endswith(".json"):
                try:
                    if (json.dumps(json.loads(ta), sort_keys=True)
                            == json.dumps(json.loads(tb), sort_keys=True)):
                        nota += (" — MESMO conteudo por outra ORDEM "
                                 "(um `set` pelo meio: ordena-o)")
                except ValueError:
                    pass
            maus.append((rel, nota))

        print(f"{total} ficheiros comparados entre dois processos")
        if maus:
            print(f"\n{len(maus)} NAO DETERMINISTAS:")
            for rel, nota in maus:
                print(f"  {rel}: {nota}")
            return 1
        print("todos iguais — a tarefa nao commita pela ordem de um set")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
