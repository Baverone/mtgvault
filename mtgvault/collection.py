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


# ---------------------------------------------------------------------------
# «SE NÃO MARQUEI, É PORQUE NÃO A TENHO» (André, 2026-09-09, à letra)
# ---------------------------------------------------------------------------
# *"No mtgvault, se eu não seleccionar no deck que meti a carta, com checkmark, é
# porque eu não a tenho e estás a fazer confusão. Por exemplo, no Cloud cEDH,
# dizes que tenho Chromatic Star mas eu não tenho, dizes que tenho Grinding
# Station, mas também não tenho."*
#
# Uma cópia fotografada há meses pode já não estar na estante. Enquanto o vault
# só soubesse contar o que a `copies` diz, ele ficava com a carta na coluna
# "tenho" para sempre, e a lista de compras a menos uma carta que ele precisa
# mesmo de comprar. O botão «Não encontrei estas» marca a cópia; a partir daí ela
# está FORA da colecção para todos os efeitos.
#
# ESTE FILTRO ESCREVE-SE NUM SÍTIO SÓ, e é este. Era `cp.purpose = 'player'`
# escrito à mão em catorze consultas — o padrão do `event_tier`: a primeira que
# se esquecesse da coluna nova voltava a dizer-lhe que tem a carta, sem um único
# erro. Há um teste que varre o código à procura do literal
# (`test_nao_encontrei.caso_o_filtro_vive_num_sitio_so`).
def jogaveis(alias: str = "cp") -> str:
    """O WHERE de *"esta cópia conta para a colecção"*.

    Duas condições, e as duas são regras de domínio: a coleção de colecionador é
    avaliada mas nunca jogada, e uma cópia que ele **não encontrou** não está lá.
    """
    return f"{alias}.purpose = 'player' AND {alias}.nao_encontrada_em IS NULL"


def na_estante(alias: str = "cp") -> str:
    """Só a segunda metade, para as vistas que mostram TAMBÉM o colecionador
    (a galeria, o valor da colecção, a Reserved List)."""
    return f"{alias}.nao_encontrada_em IS NULL"


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
    ate: str | None = None,
    finishes=None,
) -> int:
    """Adiciona exemplares. Devolve o id da linha criada.

    Sem `set_code` levanta `scryfall.EdicaoEmFalta` e **não** insere nada: uma
    edição em branco parava aqui e saía como Alpha. `adivinhar=True` aceita o
    palpite (a impressão mais recente e mais barata) e deixa-o dito na `notes`
    da cópia, para uma auditoria futura o poder encontrar.

    `ate`/`finishes` são as regras de material de quem pede — o *"já a tenho"*
    de uma caixa de Premodern não pode adivinhar uma reimpressão de 2024.
    """
    card = scryfall.find_printing(con, name, set_code, collector_number,
                                  adivinhar=adivinhar, ate=ate,
                                  finishes=finishes)
    if card is None:
        oracle = scryfall.resolve_name(con, name)
        if oracle:
            card = scryfall.find_printing(con, oracle, set_code,
                                          collector_number, adivinhar=adivinhar,
                                          ate=ate, finishes=finishes)
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


# ---------------------------------------------------------------------------
# «Já a tenho»: a foto que chega DEPOIS acerta a edição, não cria cópia nova
# ---------------------------------------------------------------------------
# André, 2026-09-08: *"Arranja forma de eu poder dar check nas cartas das faltas,
# para dizer que já as tenho e já coloquei no deck."* Esse check cria a cópia com
# a edição por adivinhar (ver `mtgvault.loadout.registar_falta`) e deixa-lhe a
# marca abaixo na `notes`. Quando a foto dessa carta chegar a `pendentes/`, a
# importação tem de ACERTAR essa cópia — criar uma segunda era ficar com o dobro
# das cartas na base por ele ter sido diligente, e a caixa passava a "ter" 8
# Swords to Plowshares que na estante são 4.
MARCA_POR_CONFIRMAR = "edicao por confirmar"


def _nota_confirmada(notes: str | None, hoje: str) -> str:
    """A `notes` de uma cópia cuja edição a foto acabou de confirmar.

    Guarda o *"registada a partir das faltas em X"* (é a história da cópia) e
    tira o *"edicao adivinhada"*: a auditoria de edições procura por essa marca,
    e deixá-la numa cópia já confirmada era mandá-la investigar o que já está
    resolvido.
    """
    partes = [p.strip() for p in (notes or "").split("|") if p.strip()]
    partes = [p for p in partes
              if MARCA_POR_CONFIRMAR not in p and "edicao adivinhada" not in p]
    partes.append(f"edicao confirmada em {hoje} pela foto")
    return " | ".join(partes)


def copias_por_confirmar(con: sqlite3.Connection,
                         name: str | None = None) -> list[sqlite3.Row]:
    """As cópias que estão à espera de que uma foto lhes diga a edição.

    O nome compara-se também pela FRENTE (`X // Y`): a lista do deck escreve a
    frente e o catálogo guarda o nome inteiro, e sem isto uma dupla-face nunca
    reencontrava a cópia que ela própria criou.
    """
    # Uma cópia que ele deu como NÃO ENCONTRADA sai daqui: a foto que chegar
    # depois é de uma carta que está em casa, e acertá-la era ressuscitar em
    # silêncio a cópia que ele disse que não tem. Essa foto entra como cópia
    # nova, que é a verdade.
    q = (f"""SELECT cp.*, c.name AS card_name FROM copies cp
              JOIN cards c ON c.scryfall_id = cp.scryfall_id
             WHERE cp.notes LIKE ? AND {na_estante()}""")
    args: list = [f"%{MARCA_POR_CONFIRMAR}%"]
    if name:
        q += " AND (c.name = ? OR c.name LIKE ? || ' //%')"
        args += [name, name]
    return con.execute(q + " ORDER BY cp.id", args).fetchall()


def acertar_edicao(con: sqlite3.Connection, name: str, set_code: str, *,
                   collector_number: str | None = None, quantity: int = 1,
                   photo_path: str | None = None) -> dict | None:
    """Põe a edição certa nas cópias de `name` que estavam por confirmar.

    Devolve `{copy_id, acertadas, restante, copias}` ou `None` quando não havia
    nenhuma à espera (aí a importação segue o caminho normal e cria a cópia).

    Quando a foto traz MENOS cópias do que as que estavam por confirmar, a linha
    parte-se em duas: a que a foto confirmou fica com a edição e com o seu lugar
    dentro da caixa (`copy_allocation`), e o resto continua à espera da próxima
    foto. Actualizar a linha inteira era dar por confirmadas cópias que ninguém
    fotografou — a mesma mentira que a marca existe para evitar.
    """
    pendentes = copias_por_confirmar(con, name)
    if not pendentes:
        return None
    card = scryfall.find_printing(con, pendentes[0]["card_name"], set_code,
                                  collector_number)
    if card is None:
        return None                        # edição que o catálogo não conhece
    hoje = dt.date.today().isoformat()
    resta, tocadas = max(int(quantity), 0), []
    for p in pendentes:
        if resta <= 0:
            break
        leva = min(resta, p["quantity"] or 0)
        if leva <= 0:
            continue
        resta -= leva
        nota = _nota_confirmada(p["notes"], hoje)
        if leva >= (p["quantity"] or 0):
            con.execute(
                "UPDATE copies SET scryfall_id = ?, notes = ?, "
                "photo_path = COALESCE(?, photo_path) WHERE id = ?",
                (card["scryfall_id"], nota, photo_path, p["id"]))
            tocadas.append(p["id"])
            continue
        con.execute("UPDATE copies SET quantity = quantity - ? WHERE id = ?",
                    (leva, p["id"]))
        cur = con.execute(
            """INSERT INTO copies (scryfall_id, quantity, finish, language,
                                   condition, purpose, sub_collection_id,
                                   photo_path, acquired_at, acquired_price,
                                   notes, reserved_deck_id, balde_origem)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (card["scryfall_id"], leva, p["finish"], p["language"],
             p["condition"], p["purpose"], p["sub_collection_id"],
             photo_path or p["photo_path"], p["acquired_at"],
             p["acquired_price"], nota, p["reserved_deck_id"],
             p["balde_origem"]))
        novo = cur.lastrowid
        tocadas.append(novo)
        # O lugar dentro da caixa acompanha a cópia confirmada: era ela que lá
        # estava. Sem isto a caixa perdia a carta que ele acabou de fotografar e
        # mandava-o procurá-la outra vez.
        for a in con.execute("SELECT slot, quantity, placed_at FROM "
                             "copy_allocation WHERE copy_id = ?",
                             (p["id"],)).fetchall():
            passa = min(leva, a["quantity"] or 0)
            if passa <= 0:
                continue
            if passa >= (a["quantity"] or 0):
                con.execute("DELETE FROM copy_allocation WHERE copy_id = ? "
                            "AND slot = ?", (p["id"], a["slot"]))
            else:
                con.execute("UPDATE copy_allocation SET quantity = quantity - ? "
                            "WHERE copy_id = ? AND slot = ?",
                            (passa, p["id"], a["slot"]))
            con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity, "
                        "placed_at) VALUES (?,?,?,?)",
                        (novo, a["slot"], passa, a["placed_at"]))
            break                          # uma cópia vive numa caixa só
    if not tocadas:
        return None
    con.commit()
    return {"copy_id": tocadas[0], "copias": tocadas,
            "acertadas": int(quantity) - resta, "restante": resta,
            "set_code": card["set_code"],
            "collector_number": card["collector_number"]}


def import_csv(con: sqlite3.Connection, path: str | Path, *,
               adivinhar: bool = False, acertar: bool = True,
               resultados: list[dict] | None = None) -> tuple[int, list[str]]:
    """Importa um CSV. Devolve (n_importadas, erros).

    `resultados`, se dado, é preenchido com uma linha por linha do CSV
    (`RESULT_FIELDS`) — inclui o `copy_id` de cada cópia criada, que é a ponte
    foto ↔ cópia do `arrumar_fotos`.

    Uma linha sem `set_code` **para** com `motivo: edicao em falta`; as outras
    continuam. `adivinhar=True` aceita o palpite (ver `add_copy`).

    `acertar` (por omissão ligado) é a outra metade do *"já a tenho"*: se já
    existe uma cópia daquela carta à espera de edição, esta linha ACERTA-A em
    vez de criar uma segunda (ver `acertar_edicao`).
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
                qtd = int(row.get("quantity") or 1)
                ajuste = (acertar_edicao(
                    con, row["name"], row["set_code"],
                    collector_number=row.get("collector_number") or None,
                    quantity=qtd, photo_path=row.get("photo_path") or None)
                    if acertar and row.get("set_code") else None)
                if ajuste:
                    res["copy_id"] = ajuste["copy_id"]
                    res["resultado"] = "importada"
                    res["motivo"] = (f'{ajuste["acertadas"]} de «já a tenho»: '
                                     f'edição acertada')
                    ok += 1
                    if not ajuste["restante"]:
                        if resultados is not None:
                            resultados.append(res)
                        continue
                    # O que a foto trouxe a mais é uma cópia nova, como sempre.
                    # A LINHA já foi contada em cima: uma linha do CSV é uma
                    # importação, mesmo quando metade acerta uma cópia que já
                    # existia e metade entra de novo.
                    row["quantity"] = str(ajuste["restante"])
                    ok -= 1
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
    where = (jogaveis() +
             " AND (cp.reserved_deck_id IS NULL OR cp.reserved_deck_id = ?)")
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
            f"""SELECT cp.id, cp.quantity FROM copies cp
                 JOIN cards c ON c.scryfall_id = cp.scryfall_id
                WHERE c.name = ? AND {jogaveis()}
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
             FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
            WHERE """ + na_estante(),
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
