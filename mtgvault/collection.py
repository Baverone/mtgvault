"""Coleção: entrada de cartas, sub-coleções, e o que tenho vs. o que falta."""
from __future__ import annotations

import csv
import datetime as dt
import shutil
import sqlite3
from pathlib import Path

from . import scryfall

ROOT = Path(__file__).resolve().parents[1]
PENDENTES = ROOT / "pendentes"
FOTOS_PROCESSADAS = PENDENTES / "fotos processadas"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def ensure_sub_collection(con, name: str, purpose: str = "player") -> int:
    con.execute(
        "INSERT OR IGNORE INTO sub_collections (name, purpose) VALUES (?,?)",
        (name, purpose),
    )
    con.commit()
    return con.execute(
        "SELECT id FROM sub_collections WHERE name = ?", (name,)
    ).fetchone()["id"]


def add_copy(
    con: sqlite3.Connection,
    name: str,
    *,
    set_code: str | None = None,
    collector_number: str | None = None,
    quantity: int = 1,
    finish: str = "nonfoil",
    language: str = "en",
    condition: str = "NM",
    purpose: str = "player",
    sub_collection: str | None = None,
    photo_path: str | None = None,
    acquired_price: float | None = None,
    notes: str | None = None,
    adivinhar: bool = False,
) -> int:
    """Adiciona exemplares. Devolve o id da linha criada.

    Sem `set_code` levanta `scryfall.EdicaoEmFalta` e **não** insere nada: uma
    edição em branco parava aqui e saía como Alpha. `adivinhar=True` aceita o
    palpite (a impressão mais recente e mais barata) e deixa-o dito na `notes`
    da cópia, para uma auditoria futura o poder encontrar.
    """
    card = scryfall.find_printing(con, name, set_code, collector_number,
                                  adivinhar=adivinhar)
    if card is None:
        oracle = scryfall.resolve_name(con, name)
        if oracle:
            card = scryfall.find_printing(con, oracle, set_code,
                                          collector_number, adivinhar=adivinhar)
    if card is None:
        raise LookupError(f"Carta não encontrada no catálogo: {name!r} ({set_code})")

    if not set_code:                       # só se chega aqui com adivinhar=True
        marca = (f"edicao adivinhada em {dt.date.today().isoformat()}: "
                 f"{card['set_code']} #{card['collector_number']}")
        notes = f"{notes} | {marca}" if notes else marca

    sub_id = (
        ensure_sub_collection(con, sub_collection, purpose) if sub_collection else None
    )
    cur = con.execute(
        """INSERT INTO copies (scryfall_id, quantity, finish, language, condition,
                               purpose, sub_collection_id, photo_path,
                               acquired_at, acquired_price, notes)
           VALUES (?,?,?,?,?,?,?,?,date('now'),?,?)""",
        (card["scryfall_id"], quantity, finish, language, condition, purpose,
         sub_id, photo_path, acquired_price, notes),
    )
    con.commit()
    return cur.lastrowid


# Colunas aceites no CSV de importação (as fotos entram por aqui:
# a coluna `photo_path` guarda o caminho do ficheiro no teu disco).
CSV_FIELDS = [
    "name", "set_code", "collector_number", "quantity", "finish", "language",
    "condition", "purpose", "sub_collection", "photo_path", "acquired_price", "notes",
]


# Uma linha do CSV de resultado: o que aconteceu a cada linha do CSV de
# entrada. É o que permite dizer "esta linha parou, e porquê" em vez de a
# contar como importada — e é por ele que se liga a foto à cópia criada.
RESULT_FIELDS = ["linha", "name", "set_code", "collector_number", "quantity",
                 "sub_collection", "photo_path", "resultado", "motivo", "copy_id"]


def import_csv(con: sqlite3.Connection, path: str | Path, *,
               adivinhar: bool = False,
               resultados: list[dict] | None = None) -> tuple[int, list[str]]:
    """Importa um CSV. Devolve (n_importadas, erros).

    `resultados`, se dado, é preenchido com uma linha por linha do CSV
    (`RESULT_FIELDS`) — inclui o `copy_id` de cada cópia criada, que é a ponte
    foto ↔ cópia do `arrumar_fotos`.

    Uma linha sem `set_code` **para** com `motivo: edicao em falta`; as outras
    continuam. `adivinhar=True` aceita o palpite (ver `add_copy`).
    """
    ok, errors = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            row = {k: (v.strip() if isinstance(v, str) else v)
                   for k, v in row.items() if k in CSV_FIELDS}
            if not row.get("name"):
                continue
            res = {"linha": i, "name": row.get("name"),
                   "set_code": row.get("set_code") or "",
                   "collector_number": row.get("collector_number") or "",
                   "quantity": row.get("quantity") or "1",
                   "sub_collection": row.get("sub_collection") or "",
                   "photo_path": row.get("photo_path") or "",
                   "resultado": "", "motivo": "", "copy_id": ""}
            try:
                res["copy_id"] = add_copy(
                    con,
                    row.pop("name"),
                    set_code=row.get("set_code") or None,
                    collector_number=row.get("collector_number") or None,
                    quantity=int(row.get("quantity") or 1),
                    finish=row.get("finish") or "nonfoil",
                    language=row.get("language") or "en",
                    condition=row.get("condition") or "NM",
                    purpose=row.get("purpose") or "player",
                    sub_collection=row.get("sub_collection") or None,
                    photo_path=row.get("photo_path") or None,
                    acquired_price=float(row["acquired_price"])
                    if row.get("acquired_price") else None,
                    notes=row.get("notes") or None,
                    adivinhar=adivinhar,
                )
                res["resultado"] = "importada"
                ok += 1
            except Exception as e:                       # noqa: BLE001
                res["resultado"] = "erro"
                res["motivo"] = str(e)
                errors.append(f"linha {i}: {res['name']} — motivo: {e}")
            if resultados is not None:
                resultados.append(res)
    return ok, errors


def gravar_resultado(resultados: list[dict], path: str | Path) -> Path:
    """Escreve o CSV de resultado da importação."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_FIELDS)
        w.writeheader()
        w.writerows(resultados)
    return path


# ---------------------------------------------------------------------------
# As fotos depois de importadas
# ---------------------------------------------------------------------------
# As fotos das cópias 1-156 (10 042 €) já não existem, e por isso essas cópias
# não são auditáveis: o fluxo antigo movia a foto para uma pasta única e nada
# guardava a que cópia ela deu origem. Agora a foto vai para uma pasta por mês
# — a pasta única já ia em milhares de ficheiros — e a ligação fica em DOIS
# sítios: `copies.photo_path` (o caminho novo, dentro da cópia) e o
# `aplicado.csv` ao lado das fotos. Nunca se apaga nada.
APLICADO = FOTOS_PROCESSADAS / "aplicado.csv"
APLICADO_FIELDS = ["at", "foto", "copy_id", "name", "set_code",
                   "collector_number", "quantity", "sub_collection"]


def arrumar_fotos(con: sqlite3.Connection, resultados: list[dict], *,
                  pendentes: str | Path | None = None) -> dict:
    """Arruma as fotos deste lote e regista a ligação foto ↔ cópia.

    Move `pendentes/<foto>` para `pendentes/fotos processadas/<AAAA-MM>/<foto>`,
    com o nome original, e actualiza a `copies.photo_path` das cópias criadas
    para o caminho novo (relativo à `pendentes/`).

    Uma foto cujas linhas **não** entraram todas fica onde está: a linha ainda
    está por catalogar, e arrumá-la escondia trabalho por fazer.
    """
    pend = Path(pendentes) if pendentes else PENDENTES
    destino_rel = f"fotos processadas/{dt.date.today():%Y-%m}"
    destino = pend / destino_rel

    por_foto: dict[str, list[dict]] = {}
    for r in resultados:
        nome = Path((r.get("photo_path") or "").strip()).name
        if nome:
            por_foto.setdefault(nome, []).append(r)

    movidas, ficaram, ligacoes = [], [], []
    for nome, linhas in por_foto.items():
        if any(r["resultado"] != "importada" for r in linhas):
            ficaram.append(nome)
            continue
        origem = pend / nome
        novo_rel = f"{destino_rel}/{nome}"
        if origem.suffix.lower() in IMG_EXT and origem.exists():
            destino.mkdir(parents=True, exist_ok=True)
            shutil.move(str(origem), str(destino / nome))
            movidas.append(novo_rel)
        elif not (destino / nome).exists():
            continue                       # foto que nunca chegou ao disco
        for r in linhas:
            if r["copy_id"]:
                con.execute("UPDATE copies SET photo_path = ? WHERE id = ?",
                            (novo_rel, r["copy_id"]))
            ligacoes.append(dict(r, foto=novo_rel))
    con.commit()

    if ligacoes:
        agora = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
        alvo = pend / "fotos processadas" / "aplicado.csv"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        novo = not alvo.exists()
        with alvo.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=APLICADO_FIELDS)
            if novo:
                w.writeheader()
            for r in ligacoes:
                w.writerow({"at": agora, "foto": r["foto"], "copy_id": r["copy_id"],
                            "name": r["name"], "set_code": r["set_code"],
                            "collector_number": r["collector_number"],
                            "quantity": r["quantity"],
                            "sub_collection": r.get("sub_collection", "")})
    return {"movidas": len(movidas), "destino": destino_rel,
            "ligadas": len(ligacoes), "ficaram": sorted(ficaram)}


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def owned_playable(con: sqlite3.Connection,
                   for_deck_id: int | None = None,
                   baldes: set[str] | None = None,
                   fora_das_caixas: bool = False) -> dict[str, int]:
    """Quantidade disponível para jogar, por nome de carta.

    Fica de fora:
      - a coleção de colecionador (purpose='collector')
      - exemplares reservados a OUTRO deck

    `for_deck_id` diz para que deck estamos a contar: as reservas desse deck
    contam, as dos outros não. Sem argumento, só conta o que está livre.

    `baldes`: se dado, conta só as cartas nesses sub_collections. Usa-se para
    contar apenas a COLEÇÃO — desde o modelo de colecção única (2026-09-07) isso
    é o balde `Colecção`; antes dele eram o `SPML` e o `Premodern (geral)`.

    `fora_das_caixas`: desconta as cópias que já estão DENTRO de uma deckbox
    (`copy_allocation`). É o gémeo do `baldes` no modelo novo — antes bastava
    não olhar para os baldes dos decks, porque cada deck tinha o seu; agora as
    cartas de um deck montado vivem no mesmo balde de todas as outras e o que as
    distingue é a arrumação. Sem isto, a colecção parecia ter as cartas que estão
    sleevadas em cima da mesa.

    Nomes de dupla-face (DFC/MDFC) são normalizados para a FRENTE (o que vem
    antes de " // "), porque é assim que as decklists as escrevem — senão a
    cobertura subcontava (ex.: "Aang, Swift Savior // ..." vs "Aang, Swift
    Savior"). Para nomes normais é um no-op.
    """
    join = "JOIN cards c ON c.scryfall_id = cp.scryfall_id"
    where = ("cp.purpose = 'player' "
             "AND (cp.reserved_deck_id IS NULL OR cp.reserved_deck_id = ?)")
    params: list = [for_deck_id]
    if baldes:
        join += " JOIN sub_collections s ON s.id = cp.sub_collection_id"
        where += " AND s.name IN (" + ",".join("?" * len(baldes)) + ")"
        params += list(baldes)
    qtd = "SUM(cp.quantity)"
    if fora_das_caixas:
        qtd = ("SUM(cp.quantity - COALESCE((SELECT SUM(a.quantity) "
               "FROM copy_allocation a WHERE a.copy_id = cp.id), 0))")
    rows = con.execute(
        f"""SELECT c.name AS name, {qtd} AS qty
              FROM copies cp {join}
             WHERE {where}
             GROUP BY c.name""",
        params,
    ).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        nm = r["name"]
        if nm and " // " in nm:
            nm = nm.split(" // ", 1)[0]
        out[nm] = out.get(nm, 0) + max(r["qty"] or 0, 0)
    return {k: v for k, v in out.items() if v > 0}


def reserve_for_deck(con: sqlite3.Connection, deck_id: int) -> dict:
    """Reserva ao deck os exemplares livres que ele precisa.

    Não toca em nada que já esteja reservado a outro deck, e não mexe na
    coleção de colecionador. Devolve o que reservou e o que não conseguiu.
    """
    need: dict[str, int] = {}
    for r in con.execute(
        "SELECT card_name, SUM(quantity) q FROM deck_cards "
        "WHERE deck_id = ? GROUP BY card_name", (deck_id,)
    ):
        need[r["card_name"]] = r["q"]

    reservado: dict[str, int] = {}
    for name, qty in need.items():
        falta = qty - (con.execute(
            """SELECT COALESCE(SUM(cp.quantity),0) q FROM copies cp
                 JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.reserved_deck_id = ?""",
            (name, deck_id)).fetchone()["q"])
        if falta <= 0:
            continue
        livres = con.execute(
            """SELECT cp.id, cp.quantity FROM copies cp
                 JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.purpose = 'player'
                  AND cp.reserved_deck_id IS NULL
                ORDER BY cp.quantity ASC""", (name,)).fetchall()
        for lote in livres:
            if falta <= 0:
                break
            if lote["quantity"] <= falta:
                con.execute("UPDATE copies SET reserved_deck_id = ? WHERE id = ?",
                            (deck_id, lote["id"]))
                reservado[name] = reservado.get(name, 0) + lote["quantity"]
                falta -= lote["quantity"]
            else:
                # partir o lote: parte fica reservada, parte fica livre
                con.execute("UPDATE copies SET quantity = quantity - ? WHERE id = ?",
                            (falta, lote["id"]))
                orig = con.execute("SELECT * FROM copies WHERE id = ?",
                                   (lote["id"],)).fetchone()
                con.execute(
                    """INSERT INTO copies (scryfall_id, quantity, finish, language,
                       condition, purpose, sub_collection_id, photo_path,
                       acquired_at, acquired_price, notes, reserved_deck_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (orig["scryfall_id"], falta, orig["finish"], orig["language"],
                     orig["condition"], orig["purpose"], orig["sub_collection_id"],
                     orig["photo_path"], orig["acquired_at"], orig["acquired_price"],
                     orig["notes"], deck_id))
                reservado[name] = reservado.get(name, 0) + falta
                falta = 0
    con.commit()

    # O que falta é sempre "o que o deck pede menos o que ESTÁ reservado a ele",
    # não "menos o que reservei agora": numa segunda passagem (o deck já tinha
    # cartas dedicadas de uma reserva anterior) só se reserva o delta, e contar
    # apenas esse delta inflacionava o que faltava.
    em_falta = {}
    for n, q in need.items():
        ja = con.execute(
            """SELECT COALESCE(SUM(cp.quantity),0) q FROM copies cp
                 JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND cp.reserved_deck_id = ?""",
            (n, deck_id)).fetchone()["q"]
        if q > ja:
            em_falta[n] = q - ja
    return {"reserved": reservado, "still_missing": em_falta}


def release_deck(con: sqlite3.Connection, deck_id: int) -> int:
    n = con.execute("SELECT COUNT(*) c FROM copies WHERE reserved_deck_id = ?",
                    (deck_id,)).fetchone()["c"]
    con.execute("UPDATE copies SET reserved_deck_id = NULL WHERE reserved_deck_id = ?",
                (deck_id,))
    con.commit()
    return n


def reservations(con: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in con.execute(
        """SELECT d.id AS deck_id, d.name AS deck, c.name AS card_name,
                  SUM(cp.quantity) AS quantity
             FROM copies cp
             JOIN decks d ON d.id = cp.reserved_deck_id
             JOIN cards c ON c.scryfall_id = cp.scryfall_id
            GROUP BY d.id, c.name ORDER BY d.name, c.name""")]


def deck_card_needs(con: sqlite3.Connection) -> dict[str, int]:
    """Quantas cópias de cada carta os decks pedem — o máximo que UM único deck
    usa (main+side). É o que precisa de ficar guardado para os decks."""
    needs: dict[str, int] = {}
    for r in con.execute("SELECT deck_id, card_name, SUM(quantity) q FROM deck_cards "
                         "GROUP BY deck_id, card_name"):
        needs[r["card_name"]] = max(needs.get(r["card_name"], 0), r["q"])
    return needs


def deck_extras(con: sqlite3.Connection) -> list[dict]:
    """Cópias a MAIS das cartas que estão em decks (owned − o que a decklist pede).

    Versão SIMPLES da regra "extras dos decks" — ver CLAUDE.md. A regra refinada
    (A AFINAR) mete um LIMITE por coleção/formato: construído = 4 por carta,
    Commander = 1 por deck; acima do limite o excedente é para VENDER. Esta função
    ainda não aplica esses limites — é só o bloco de base. Só conta 'player'.
    """
    needs = deck_card_needs(con)
    owned = owned_playable(con)
    out = []
    for name, need in needs.items():
        have = owned.get(name, 0)
        if have > need:
            out.append({"card_name": name, "owned": have, "deck_need": need,
                        "extra": have - need})
    return sorted(out, key=lambda x: -x["extra"])


def collection_value(con: sqlite3.Connection, source: str = "cardmarket") -> list[dict]:
    """Valor atual de cada lote, com o preço mais recente disponível."""
    rows = con.execute(
        """SELECT cp.id, c.name, c.set_code, cp.quantity, cp.finish, cp.purpose,
                  cp.acquired_price,
                  (SELECT trend FROM price_latest p
                    WHERE p.scryfall_id = cp.scryfall_id AND p.source = ?
                      AND p.finish = cp.finish) AS unit_price,
                  (SELECT date FROM price_latest p
                    WHERE p.scryfall_id = cp.scryfall_id AND p.source = ?
                      AND p.finish = cp.finish) AS price_date
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id""",
        (source, source),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["total"] = round((d["unit_price"] or 0) * d["quantity"], 2)
        out.append(d)
    return out


def movers(con: sqlite3.Connection, days: int = 7, source: str = "cardmarket",
           limit: int = 25) -> dict[str, list[dict]]:
    """Cartas da coleção que mais subiram e mais desceram na janela."""
    rows = con.execute(
        """WITH mine AS (
              SELECT DISTINCT scryfall_id, finish FROM copies
           )
           SELECT c.name, c.set_code, m.finish,
                  t.trend AS before, l.trend AS after,
                  (l.trend - t.trend) AS delta,
                  round(100.0 * (l.trend - t.trend) / t.trend, 1) AS pct
             FROM mine m
             JOIN price_latest l
               ON l.scryfall_id = m.scryfall_id AND l.finish = m.finish
              AND l.source = :src
             JOIN cards c ON c.scryfall_id = m.scryfall_id
             JOIN (SELECT m2.scryfall_id, m2.finish,
                    (SELECT h.trend FROM price_history h
                      WHERE h.scryfall_id = m2.scryfall_id AND h.finish = m2.finish
                        AND h.source = :src
                        AND h.date <= date('now', '-' || :days || ' days')
                      ORDER BY h.date DESC LIMIT 1) AS trend
                     FROM mine m2) t
               ON t.scryfall_id = m.scryfall_id AND t.finish = m.finish
            WHERE t.trend > 0.10 AND l.trend IS NOT NULL
            ORDER BY pct DESC""",
        {"src": source, "days": days},
    ).fetchall()
    rows = [dict(r) for r in rows]
    # As duas listas partem-se pelo SINAL da variação, não pelas pontas da
    # ordenação: com menos de `limit` cartas as duas pontas sobrepõem-se e as
    # que tinham SUBIDO apareciam também em "A DESCER" (com o pct positivo).
    subiram = [r for r in rows if (r["delta"] or 0) >= 0]
    desceram = [r for r in rows if (r["delta"] or 0) < 0]
    return {"up": subiram[:limit], "down": list(reversed(desceram))[:limit]}
