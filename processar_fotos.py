"""processar_fotos.py — cataloga cartas reconhecidas de fotos, num passo.

FLUXO para catalogar de qualquer lado (telemóvel incluído, sem PC):
 1. Largas fotos novas na pasta `pendentes/` (app do GitHub no telemóvel, ou no PC).
 2. Um Claude — esta sessão, OU o claude.ai/code aberto no telemóvel apontado ao
    repositório Baverone/mtgvault — OLHA para as fotos de `pendentes/`, reconhece
    as cartas (regras em PROCESSAR_FOTOS.md) e escreve um CSV.
 3. Corre:  py processar_fotos.py <csv>
    Este script: garante o catálogo (reconstrói da Scryfall se preciso), baixa o
    set_code para minúsculas, importa para o vault.db, remove as fotos já
    catalogadas de `pendentes/`, e faz commit + push. O site atualiza-se sozinho.

O RECONHECIMENTO é sempre um Claude a olhar para as fotos — o script só faz a
parte mecânica (importar + arrumar + push).
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
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _ensure_catalog(con):
    """O catálogo pode não vir num clone fresco (é grande de mais p/ o Git).
    Reconstrói-o do bulk da Scryfall, como o job diário."""
    if db.catalog_size(con) >= 1000:
        return "catálogo já existe"
    n = scryfall.load_bulk(con, scryfall.download_bulk())
    return f"catálogo reconstruído ({n:,} impressões)"


def _normalize(src):
    """Baixa o set_code para minúsculas (o catálogo é minúsculo). O
    collector_number fica como está (ex.: The List 'plst #UGL-84')."""
    with open(src, newline="", encoding="utf-8-sig") as fh:
        rows = list(_csv.DictReader(fh))
    if not rows:
        return src, 0
    for r in rows:
        if r.get("set_code"):
            r["set_code"] = r["set_code"].strip().lower()
    tmp = tempfile.NamedTemporaryFile("w", delete=False, newline="",
                                      suffix=".csv", encoding="utf-8")
    w = _csv.DictWriter(tmp, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    tmp.close()
    return tmp.name, len(rows)


def _git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, check=check)


def main(csv_path):
    with db.session() as con:
        print(_ensure_catalog(con))
        norm, n = _normalize(csv_path)
        ok, errs = collection.import_csv(con, norm)
        con.commit()
    print(f"{ok}/{n} linhas importadas.")
    for e in errs[:20]:
        print("  [erro]", e)

    # limpar as fotos já catalogadas de pendentes/ (mantém o repositório leve)
    fotos = [p for p in PEND.glob("*") if p.suffix.lower() in IMG_EXT] if PEND.exists() else []
    for p in fotos:
        rel = str(p.relative_to(ROOT))
        if _git("rm", "-q", rel, check=False).returncode != 0:
            p.unlink(missing_ok=True)

    # commit + push (o job diário/site atualizam sozinhos)
    _git("config", "user.name", "mtgvault fotos", check=False)
    _git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", check=False)
    _git("add", "-f", "data/vault.db")
    if _git("diff", "--cached", "--quiet", check=False).returncode != 0:
        _git("commit", "-m", f"fotos: +{ok} cartas ({len(fotos)} fotos processadas)")
        _git("push")
        print(f"commit + push feitos ({len(fotos)} fotos limpas de pendentes/).")
    else:
        print("sem alterações para gravar.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: py processar_fotos.py <csv>   (o CSV é o que o Claude escreveu das fotos)")
    main(sys.argv[1])
