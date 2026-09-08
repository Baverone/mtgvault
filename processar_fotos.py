"""processar_fotos.py — cataloga cartas reconhecidas de fotos, num passo.

FLUXO para catalogar de qualquer lado (telemóvel incluído, sem PC):
 1. Largas fotos novas na pasta `pendentes/` (app do GitHub no telemóvel, ou no PC).
 2. Um Claude — esta sessão, OU o claude.ai/code aberto no telemóvel apontado ao
    repositório Baverone/mtgvault — OLHA para as fotos de `pendentes/`, reconhece
    as cartas (regras em PROCESSAR_FOTOS.md) e escreve um CSV.
 3. Corre:  py processar_fotos.py <csv>
    Este script: garante o catálogo, PUXA a BD mais recente do Release (para não
    perder o harvest/preços do job diário), importa para o vault.db, PUBLICA a BD
    de volta no Release (db_push), e arruma SÓ as fotos deste CSV para
    `pendentes/fotos processadas/<AAAA-MM>/`. O site atualiza-se no próximo job
    diário (regenera as páginas com a BD nova).

O RECONHECIMENTO é sempre um Claude a olhar para as fotos — o script só faz a
parte mecânica (importar + publicar a BD + arrumar as fotos).

AS FOTOS NUNCA SE APAGAM (2026-09-08). Movem-se sempre, com o nome original,
para uma pasta por mês, e cada uma fica ligada à cópia que criou — na
`copies.photo_path` e no `aplicado.csv` ao lado das fotos. Sem essa ligação,
156 cópias (10 042 €) deixaram de ser auditáveis quando apareceu a primeira
suspeita de edição errada. Uma foto cujas linhas não entraram todas FICA em
`pendentes/`: ainda há trabalho nela.

UMA LINHA SEM EDIÇÃO PARA (2026-09-08). `set_code` em branco já não devolve a
impressão mais antiga em silêncio — que para as básicas era sempre Alpha. A
linha sai no CSV de resultado (ao lado do CSV de entrada) com
`motivo: edicao em falta`, e a foto fica em `pendentes/` para ser recatalogada.

NOTA (2026-09-06): a `vault.db` vive num GitHub Release (tag `data`), NUNCA no
Git. Por isso este script usa `scripts/db_pull.sh` + `scripts/db_push.sh` e
**não** faz `git add` da BD. Puxar antes de importar é obrigatório: o job diário
junta harvest/preços na cloud, e um push sem pull apagaria esse trabalho.
"""
from __future__ import annotations

import csv as _csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import collection, db, scryfall  # noqa: E402

PEND = ROOT / "pendentes"


def _ensure_catalog(con):
    """O catálogo pode não vir num clone fresco (é grande de mais p/ o Git).
    Reconstrói-o do bulk da Scryfall, como o job diário."""
    if db.catalog_size(con) >= 1000:
        return "catálogo já existe"
    n = scryfall.load_bulk(con, scryfall.download_bulk())
    return f"catálogo reconstruído ({n:,} impressões)"


def _normalize(src):
    """Baixa o set_code para minúsculas (o catálogo é minúsculo); o
    collector_number fica como está (ex.: The List 'plst #UGL-84'). Devolve
    (caminho_do_csv_normalizado, rows)."""
    with open(src, newline="", encoding="utf-8-sig") as fh:
        rows = list(_csv.DictReader(fh))
    if not rows:
        return src, []
    for r in rows:
        if r.get("set_code"):
            r["set_code"] = r["set_code"].strip().lower()
    tmp = tempfile.NamedTemporaryFile("w", delete=False, newline="",
                                      suffix=".csv", encoding="utf-8")
    w = _csv.DictWriter(tmp, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    tmp.close()
    return tmp.name, rows


def _sh(script_name):
    """Corre um script de scripts/ (db_pull.sh / db_push.sh) com o bash do Git."""
    return subprocess.run(["bash", str(ROOT / "scripts" / script_name)], cwd=ROOT)


def main(csv_path):
    # 1. Puxar a BD mais recente do Release ANTES de importar (não perder o
    #    harvest/preços que o job diário já juntou). Sem isto, o db_push a seguir
    #    (last-write-wins) apagaria esse trabalho.
    print("A puxar a BD mais recente do Release...")
    if _sh("db_pull.sh").returncode != 0:
        sys.exit("db_pull falhou — abortado (não mexo na BD sem a versão atual).")

    # 2. Importar as cartas do CSV para o vault.db, e arrumar as fotos JÁ — as
    #    fotos e a ligação foto↔cópia não podem depender de o db_push correr
    #    bem: a alternativa é perder a única evidência do que foi importado.
    resultados = []
    with db.session() as con:
        print(_ensure_catalog(con))
        norm, rows = _normalize(csv_path)
        ok, errs = collection.import_csv(con, norm, resultados=resultados)
        con.commit()
        fotos = collection.arrumar_fotos(con, resultados, pendentes=PEND)
    total = len(rows)
    print(f"{ok}/{total} linhas importadas.")
    for e in errs[:20]:
        print("  [erro]", e)
    saida = Path(csv_path).with_name(Path(csv_path).stem + "-resultado.csv")
    print("resultado linha a linha:", collection.gravar_resultado(resultados, saida))
    if not ok:
        sys.exit("nada importado — não publico a BD.")

    # 3. Publicar a BD no Release (NUNCA git add da BD — vive no Release).
    print("A publicar a BD no Release...")
    if _sh("db_push.sh").returncode != 0:
        sys.exit("db_push falhou — as cartas estão na BD local mas não foram "
                 "publicadas. Corre scripts/db_push.sh à mão quando puderes.")

    print(f"Feito: {ok} cartas importadas, BD publicada no Release, "
          f"{fotos['movidas']} fotos arrumadas para "
          f"'pendentes/{fotos['destino']}' ({fotos['ligadas']} ligações "
          f"foto↔cópia registadas).")
    if fotos["ficaram"]:
        print("Ficam em pendentes/ (têm linhas por resolver): "
              + ", ".join(fotos["ficaram"]))
    print("O site atualiza no próximo job diário (regenera as páginas com a BD nova).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: py processar_fotos.py <csv>   (o CSV é o que o Claude escreveu das fotos)")
    main(sys.argv[1])
