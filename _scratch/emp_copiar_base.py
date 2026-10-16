"""Copia (so leitura na origem) a vault.db do main para _scratch/vault.db.
A worktree nasceu sem data/vault.db (esta no .gitignore)."""
import sqlite3
from pathlib import Path

ORIG = Path(r"C:\Users\Catarina\Desktop\Servidor MTG Coleçao\Servidor MTG Coleçao\data\vault.db")
DEST = Path(__file__).resolve().parent / "vault.db"
src = sqlite3.connect(f"file:{ORIG.as_posix()}?mode=ro", uri=True)
dst = sqlite3.connect(DEST)
src.backup(dst)
print("copiada:", DEST, DEST.stat().st_size, "bytes;",
      dst.execute("PRAGMA integrity_check").fetchone()[0])
