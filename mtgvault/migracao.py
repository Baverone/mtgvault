"""Migração para o MODELO DE COLECÇÃO ÚNICA (André, 2026-09-07).

Palavras dele, à letra:

    *"Põe a colecção toda em uma coisa só, com excepção da RL, e assim vais
    buscar as cartas ao mesmo sítio, mas aplicando as regras."*

O que muda
----------
Até aqui uma cópia vivia num `sub_collection` que era ao mesmo tempo duas coisas
diferentes: uma **gaveta** (o `SPML`, o `Premodern (geral)`) e uma **deckbox** (o
`Blue Farm`, o `Cloud cEDH`). Misturar as duas fez o vault mentir mais do que uma
vez — a mais cara foi *"meti 4 fotos, estavam lá 4 Utrom Monitor, mas no deck
Pauper não aparecem como se eu tivesse a carta"*: estavam no `SPML` e a página do
Pauper só olhava para o balde do Pauper.

Depois desta migração há **duas gavetas** e nada mais:

  * `Colecção` — tudo o que não está numa deckbox;
  * `Caixa Reserved List` — que fica como está (e continua a ser duas na
    estante, as PT e as EN separadas: ver `loadout.balde_local`).

E a **deckbox deixa de ser um balde**: onde uma cópia está passa a ser a
ALOCAÇÃO do loadout, guardada em `copy_allocation` quando o André carrega no
"já arrumei". A gaveta de onde ela veio fica em `copies.balde_origem`, para a
aba *Arrumar* saber dizer de que prateleira a tirar hoje.

O que NÃO se toca
-----------------
  * a `Caixa Reserved List` — é a excepção que ele pediu;
  * a colecção de **colecionador** (`purpose='collector'`) — é avaliada, nunca
    alocada, e não tem nada que ver com deckboxes;
  * as `sub_collections` em si (os nomes ficam na tabela, vazios) — apagá-las
    era destruir a única pista do que existia antes.

Idempotente: correr duas vezes não faz nada na segunda. O `balde_origem` só se
escreve quando está a NULL, precisamente para a segunda corrida não gravar
`Colecção` por cima da gaveta verdadeira.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from . import loadout

# As gavetas que se fundem na `Colecção` (André, 2026-09-07). As seis primeiras
# são as que têm cartas hoje; as outras são baldes de decks de Premodern que
# ficaram vazios e entram na lista para a migração não deixar nada para trás se
# ele lá meter cartas antes de a correr.
BALDES_A_FUNDIR = (
    "SPML", "Premodern (geral)", "Jogar",
    "Blue Farm", "Cloud", "Cloud cEDH", "Pauper Affinity",
    "Stiflenought", "UW Replenish", "Elves", "Enchantress",
    "Oath of Druids", "Ill-Gotten Gains",
)


def _slot_por_balde(cfg_slots: list[dict] | None = None) -> dict[str, dict]:
    """`balde -> slot do loadout` para os baldes que SÃO a caixa de um deck.

    É por aqui que os decks que estão fisicamente montados continuam montados
    depois da migração: as cartas que viviam no balde `Blue Farm` passam a estar
    registadas dentro da caixa `Blue Farm`. Sem isto, a migração desmontava no
    papel quatro decks que estão na estante — as regras de material (o cEDH só
    aceita EN nonfoil) voltariam a aplicar-se a cartas já sleevadas.
    """
    coleccao = set(loadout.baldes_coleccao())
    slots = cfg_slots if cfg_slots is not None else loadout.config_slots()
    return {s["balde"]: s for s in slots
            if s.get("balde") and s["balde"] not in coleccao}


def backup(con, pasta: Path | None = None) -> Path | None:
    """Cópia da `vault.db` antes de mexer. Uma vez por dia, nunca por cima.

    Fica ao lado da própria base (`<vault.db>/../backups`), não ao lado do
    código: quem corre isto com `MTGVAULT_DB` a apontar para outro sítio quer o
    backup lá, não na pasta do repositório.
    """
    if pasta is None:
        alvo_db = next((r[2] for r in con.execute("PRAGMA database_list")
                        if r[1] == "main" and r[2]), None)
        base = Path(alvo_db).resolve().parent if alvo_db else Path.cwd()
        pasta = base / "backups"
    alvo = pasta / f"vault-antes-coleccao-unica-{date.today().isoformat()}.db"
    if alvo.exists():
        return alvo
    pasta.mkdir(parents=True, exist_ok=True)
    # VACUUM INTO em vez de copiar o ficheiro: dá uma cópia consistente do `main`
    # com a ligação aberta, e sem levar o catálogo anexado atrás. É o mesmo
    # mecanismo do backup da poda de ligas (daily._podar_ligas).
    con.execute("VACUUM main INTO ?", (str(alvo),))
    return alvo


def migrar(con, dry_run: bool = False, com_backup: bool = True,
           cfg_slots: list[dict] | None = None) -> dict:
    """Funde os baldes na `Colecção` e regista os decks montados como arrumados.

    Devolve um relatório com o que mexeu, para o CLI e os testes o lerem. Com
    `dry_run` não escreve nada — conta só o que faria.
    """
    alvos = {r["name"]: r["id"] for r in con.execute(
        "SELECT id, name FROM sub_collections")}
    por_balde = _slot_por_balde(cfg_slots)
    movidas: dict[str, int] = {}
    arrumadas: dict[str, int] = {}
    for balde in BALDES_A_FUNDIR:
        sid = alvos.get(balde)
        if sid is None:
            continue
        linhas = con.execute(
            "SELECT id, quantity FROM copies "
            "WHERE sub_collection_id = ? AND purpose = 'player'", (sid,)).fetchall()
        if not linhas:
            continue
        movidas[balde] = sum(r["quantity"] for r in linhas)
        slot = por_balde.get(balde)
        if slot:
            arrumadas[slot["slot"]] = movidas[balde]
    if dry_run:
        return {"movidas": movidas, "arrumadas": arrumadas, "backup": None,
                "total": sum(movidas.values()), "dry_run": True}

    guardado = backup(con) if com_backup else None
    destino = alvos.get(loadout.BALDE_COLECCAO)
    if destino is None:
        con.execute("INSERT INTO sub_collections (name, purpose) VALUES (?, 'player')",
                    (loadout.BALDE_COLECCAO,))
        destino = con.execute("SELECT id FROM sub_collections WHERE name = ?",
                              (loadout.BALDE_COLECCAO,)).fetchone()["id"]
    for balde in BALDES_A_FUNDIR:
        sid = alvos.get(balde)
        if sid is None or sid == destino:
            continue
        slot = por_balde.get(balde)
        if slot:
            # O deck está montado: as cartas ficam registadas DENTRO da caixa.
            # `INSERT OR IGNORE` para a segunda corrida não mexer numa arrumação
            # que ele entretanto tenha confirmado à mão.
            con.execute(
                """INSERT OR IGNORE INTO copy_allocation (copy_id, slot, quantity,
                                                          placed_at)
                   SELECT id, ?, quantity, datetime('now') FROM copies
                    WHERE sub_collection_id = ? AND purpose = 'player'""",
                (slot["slot"], sid))
        # Só quando está a NULL: na segunda corrida o balde já é a `Colecção` e
        # gravá-lo apagava a gaveta verdadeira.
        con.execute("UPDATE copies SET balde_origem = ? "
                    "WHERE sub_collection_id = ? AND purpose = 'player' "
                    "AND balde_origem IS NULL", (balde, sid))
        con.execute("UPDATE copies SET sub_collection_id = ? "
                    "WHERE sub_collection_id = ? AND purpose = 'player'",
                    (destino, sid))
    con.commit()
    return {"movidas": movidas, "arrumadas": arrumadas,
            "backup": str(guardado) if guardado else None,
            "total": sum(movidas.values()), "dry_run": False}


def estado(con) -> dict:
    """Onde estão as cópias hoje, por balde — para o CLI dizer o antes/depois."""
    return {r["b"]: r["q"] for r in con.execute(
        """SELECT COALESCE(s.name, '(sem balde)') b, SUM(cp.quantity) q
             FROM copies cp LEFT JOIN sub_collections s ON s.id = cp.sub_collection_id
            WHERE cp.purpose = 'player' GROUP BY b ORDER BY q DESC""")}
