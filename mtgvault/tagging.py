"""Arquétipos por regra (carta definidora), com etiqueta dupla.

O `analysis.rebuild_archetypes` agrupa por semelhança (Jaccard) e gera rótulos
feios — e junta decks que só partilham o esqueleto de artefactos (Mox Opal,
Urza's Saga, Mishra's Bauble), misturando planos de jogo diferentes. Isto
complementa-o: nomeia arquétipos por REGRA — a carta que define o plano — e deixa
um deck pertencer a MAIS DO QUE UM (etiqueta dupla), que é o mais honesto para os
híbridos (ex.: um deck que é ao mesmo tempo "Oswald Toolbox" e "Jeskai Ascendancy").

As regras vivem em `archetype_rules.json` (na raiz do projeto), editáveis à mão
sem tocar em código. Cada regra: `all` (tem de ter todas as cartas) e/ou `any`
(basta uma). Sobrevive ao `analyse` diário: chama-se `tag_all()` no daily.py
DEPOIS do rebuild, e as etiquetas são reescritas a partir das regras — o
clustering automático nunca as desfaz.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

RULES_FILE = Path(__file__).resolve().parents[1] / "archetype_rules.json"

DDL = """CREATE TABLE IF NOT EXISTS decklist_tags (
    decklist_id INTEGER NOT NULL REFERENCES decklists(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    PRIMARY KEY (decklist_id, name)
)"""


def load_rules() -> dict:
    if not RULES_FILE.exists():
        return {}
    data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    # ignora chaves de comentário (começadas por "_")
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _matches(cards: set[str], rule: dict) -> bool:
    if rule.get("all") and not all(c in cards for c in rule["all"]):
        return False
    if rule.get("any") and not any(c in cards for c in rule["any"]):
        return False
    return bool(rule.get("all") or rule.get("any"))


def tag_format(con: sqlite3.Connection, fmt: str) -> int:
    """(Re)aplica as regras de um formato. Devolve nº de etiquetas escritas."""
    con.execute(DDL)
    fmt = fmt.lower()
    rules = load_rules().get(fmt, [])
    # apaga as etiquetas antigas deste formato antes de reescrever
    con.execute(
        "DELETE FROM decklist_tags WHERE decklist_id IN "
        "(SELECT id FROM decklists WHERE format = ?)", (fmt,))
    if not rules:
        con.commit()
        return 0
    n = 0
    for d in con.execute("SELECT id FROM decklists WHERE format = ?", (fmt,)).fetchall():
        cards = {r["card_name"] for r in con.execute(
            "SELECT card_name FROM decklist_cards WHERE decklist_id = ?", (d["id"],))}
        for rule in rules:
            if _matches(cards, rule):
                con.execute("INSERT OR IGNORE INTO decklist_tags (decklist_id, name) "
                            "VALUES (?, ?)", (d["id"], rule["name"]))
                n += 1
    con.commit()
    return n


def tag_all(con: sqlite3.Connection) -> int:
    """Aplica as regras de todos os formatos definidos em archetype_rules.json."""
    return sum(tag_format(con, fmt) for fmt in load_rules())


def summary(con: sqlite3.Connection, fmt: str) -> list[dict]:
    """Nº de decks por arquétipo nomeado (com sobreposição), para o formato."""
    con.execute(DDL)
    rows = con.execute(
        """SELECT t.name, COUNT(*) AS n FROM decklist_tags t
             JOIN decklists d ON d.id = t.decklist_id
            WHERE d.format = ? GROUP BY t.name ORDER BY n DESC""", (fmt.lower(),))
    return [dict(r) for r in rows]
