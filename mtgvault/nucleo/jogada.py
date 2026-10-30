"""Onde uma carta se joga: nos decks dele e nos torneios.

Duas fontes, e cada uma responde a uma coisa diferente:

- **Os decks dele** — a versão atual de cada `n_deck` (a de maior `numero`).
  É o que ele joga hoje, por isso vem primeiro.
- **Os torneios** — `n_jogada`, o número de listas por (formato, mês, carta).
  A recolha só guarda 30 dias de decklists (`prune_decklists`), e «esta carta
  joga-se em Legacy» tem de continuar a saber-se passado esse mês: por isso o
  `registar` copia a contagem para `n_jogada`, que nunca se poda, antes de as
  listas desaparecerem.

Os nomes casam pela **face da frente**: as listas trazem «Wear» e o catálogo
«Wear // Tear». Está dos dois lados (ao gravar e ao perguntar), porque só num
deles bastava uma fonte nova com a convenção trocada para a carta deixar de
aparecer sem erro nenhum.

Só escreve em `n_jogada`.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from . import modelo, visual

# Janela dos torneios: de há 3 meses até ao mês de hoje, inclusive. Em meses
# inteiros (`mes` é 'AAAA-MM'): uma lista de 1 de julho conta em outubro.
JANELA_MESES = 3

_SEP = " // "

# A face da frente de `card_name`, em SQL: as listas de torneio trazem a frente
# (ou, de vez em quando, o nome inteiro) e `n_jogada` guarda sempre a frente.
_FRENTE_SQL = ("CASE WHEN instr(dc.card_name, ' // ') > 0"
               " THEN substr(dc.card_name, 1, instr(dc.card_name, ' // ') - 1)"
               " ELSE dc.card_name END")


def frente(nome: str) -> str:
    """A face da frente de uma carta de duas faces (ou o próprio nome)."""
    return nome.split(_SEP)[0].strip()


def registar(con: sqlite3.Connection) -> int:
    """Conta, por (formato, mês, carta), as listas distintas que a jogam e
    grava em `n_jogada`. Devolve as linhas escritas.

    Recalcula **todos os (formato, mês) que ainda têm listas** e só esses: um
    mês cujas listas a poda já apagou não aparece aqui e mantém o que lá ficou
    (é para isso que a tabela existe). Dentro de um mês que ainda tem listas
    apaga-se antes de escrever, para uma carta que deixou de aparecer nas listas
    sobreviventes não ficar com a contagem velha. Uma carta no main e no side da
    mesma lista conta uma vez (`COUNT(DISTINCT decklist_id)`).

    Tem de correr **antes** da poda das listas.
    """
    linhas = con.execute(
        f"SELECT d.format, strftime('%Y-%m', d.event_date) AS mes,"
        f" {_FRENTE_SQL} AS nome, COUNT(DISTINCT d.id) AS listas"
        " FROM decklists d JOIN decklist_cards dc ON dc.decklist_id = d.id"
        " WHERE d.event_date IS NOT NULL"
        " GROUP BY d.format, mes, nome").fetchall()
    meses = {(l[0], l[1]) for l in linhas}
    for formato, mes in sorted(meses):
        con.execute("DELETE FROM n_jogada WHERE formato = ? AND mes = ?",
                    (formato, mes))
    con.executemany(
        "INSERT OR REPLACE INTO n_jogada (formato, mes, nome, listas)"
        " VALUES (?,?,?,?)", [tuple(l) for l in linhas])
    con.commit()
    return len(linhas)


def _janela(hoje: str) -> tuple[str, str]:
    """('AAAA-MM' de há 3 meses, 'AAAA-MM' de hoje)."""
    ano, mes = int(hoje[:4]), int(hoje[5:7])
    i = ano * 12 + (mes - 1) - JANELA_MESES
    return f"{i // 12:04d}-{i % 12 + 1:02d}", hoje[:7]


def _decks_que_jogam(con: sqlite3.Connection, frente_nome: str) -> list[str]:
    """Os rótulos «deck <Nome>» dos decks cuja versão atual tem a carta, na
    ordem de `modelo.decks`, cada um uma vez (qualquer secção)."""
    slugs = {r[0] for r in con.execute(
        "SELECT v.slug, c.nome FROM n_versao v"
        " JOIN n_versao_carta c ON c.versao_id = v.id"
        " WHERE v.numero = (SELECT MAX(numero) FROM n_versao WHERE slug = v.slug)"
        ).fetchall() if frente(r[1]) == frente_nome}
    return [f"deck {d['nome']}" for d in modelo.decks(con) if d["slug"] in slugs]


def onde_joga(con: sqlite3.Connection, nome: str,
              hoje: str | None = None) -> list[str]:
    """Os rótulos de onde a carta se joga: primeiro os decks dele, depois os
    formatos com listas na janela (mais listas primeiro, empate pelo rótulo).
    Vazio = não joga em lado nenhum."""
    hoje = hoje or date.today().isoformat()
    alvo = frente(nome)
    rotulos = _decks_que_jogam(con, alvo)
    ini, fim = _janela(hoje)
    por_formato = con.execute(
        "SELECT formato, SUM(listas) FROM n_jogada"
        " WHERE nome = ? AND mes >= ? AND mes <= ? GROUP BY formato",
        (alvo, ini, fim)).fetchall()
    formatos = sorted(((visual.formato(f), n) for f, n in por_formato if n),
                      key=lambda x: (-x[1], x[0]))
    return rotulos + [f for f, _ in formatos]
