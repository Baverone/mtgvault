"""Encomendas: o que o André comprou e ainda não fotografou (2026-09-19).

André, à letra: *"consegues, para o magic, criar algo igual ao que criaste para
o Riftbound, mas ao invés de "coleção" colocas para os decks? assim fica mais
fácil eu conseguir organizar-me; até porque assim até conseguia, ao invés de
atualizar sempre a coleção, dizia-te o que ia comprando, e tu só ias pedindo as
fotos das cartas; cada vez que eu adiciono que tenho a carta, fica pendente de
foto; quando coloco a foto, adicionas à coleção"*.

A REGRA: SÓ A FOTO CRIA CÓPIAS
------------------------------
O caminho de uma carta passa a ser:

    a comprar  →  `+`  a caminho  →  «Chegou»  pendente de foto
               →  a foto entra em `pendentes/`  →  o import cria a cópia,
                  fecha a encomenda e ALOCA a cópia à caixa da encomenda.

Nem o `+` nem o «Chegou» escrevem em `copies` nem em `copy_allocation`. Uma
encomenda **não é uma cópia**: não conta para o valor da colecção, para a
venda, para a galeria nem para nada que conte cartas. O que faz é DESCONTAR o
«a comprar» da caixa a que pertence (`descontar`, chamado pelo
`loadout.allocate`): o que está encomendado já não é para comprar, e por isso
sai do «comprar N», do «fechar tudo por X €» e das wantlists.

O «já a tenho, está no deck» do passo 2 passou a entrar aqui, directamente em
**pendente de foto** — é o *"cada vez que eu adiciono que tenho a carta, fica
pendente de foto"*. O motor antigo (`loadout.registar_falta`, que criava a cópia
com «edição por confirmar») fica no código como caminho antigo; as cópias que
ele criou e ainda esperam foto aparecem na lista de pendentes como *"na base,
sem foto"* (`collection.copias_sem_foto`).

O MATERIAL de uma encomenda é o da caixa (`loadout.material_da_caixa`:
Premodern → PT e impressão ≤ Scourge; SPML/Legacy → EN foil; cEDH → EN nonfoil;
Duel Commander → foil; Pauper → qualquer; básicas isentas). Sem `set_code`
quer dizer «qualquer impressão que cumpra a regra da caixa» — é a omissão do
selector, porque ele raramente sabe a edição antes de a carta chegar.

O RASTO é `data/encomendas.log` (fora do Git, como o `vendas.csv`), escrito
ANTES da base, uma linha por acção. É a contrapartida de um mecanismo que muda
o número por que ele decide («fechar tudo por X €») sem passar por uma foto.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import db, scryfall

A_CAMINHO = "a_caminho"
PENDENTE = "pendente_foto"
ESTADOS = (A_CAMINHO, PENDENTE)
# A origem que o «já a tenho» escreve: é como se distingue, na lista, o que ele
# comprou do que ele disse já ter em casa.
ORIGEM_JA_TENHO = "já a tenho"


# ---------------------------------------------------------------------------
# O rasto
# ---------------------------------------------------------------------------
def ficheiro_log() -> Path:
    """`data/encomendas.log` — ao lado da base, como o `vendas.csv` e pela mesma
    razão: a `vault.db` é descarregada e republicada inteira a cada corrida."""
    return db.pasta_dados() / "encomendas.log"


def _log(accao: str, nm: str, impressao: str, q, caixa, origem, detalhe: str = "",
         log_path: Path | None = None) -> Path:
    alvo = log_path or ficheiro_log()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    agora = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    campos = [agora, accao, nm, impressao, str(q), caixa or "colecção",
              origem or "", detalhe]
    with alvo.open("a", encoding="utf-8") as fh:
        fh.write("\t".join(str(c).replace("\t", " ").replace("\n", " ")
                           for c in campos) + "\n")
    return alvo


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _front(nm: str) -> str:
    return nm.split(" // ", 1)[0] if nm and " // " in nm else nm


def impressao(r) -> str:
    """`ODY #123 · pt · foil` — a impressão em texto, para o log e as listas.
    Aceita um `sqlite3.Row` (sem `.get`) ou um dicionário."""
    d = dict(r)
    partes = [((d.get("set_code") or "").upper()
               + (f" #{d['collector_number']}" if d.get("collector_number") else ""))
              or "qualquer edição", d.get("lang") or "", d.get("finish") or ""]
    return " · ".join(p for p in partes if p)


def _linha(r, nomes: dict[str, str] | None = None) -> dict:
    d = dict(r)
    d["nm"] = d["card_name"]
    d["q_aberta"] = (d["qty_a_caminho"] or 0) + (d["qty_pendente_foto"] or 0)
    d["aberta"] = d["q_aberta"] > 0
    d["caixa"] = (nomes or {}).get(d["slot"]) or d["slot"] or ""
    d["impressao"] = impressao(d)
    try:
        d["copy_ids"] = json.loads(d.get("copy_ids") or "[]")
    except ValueError:
        d["copy_ids"] = []
    return d


def _nomes(con) -> dict[str, str]:
    from . import loadout                                  # noqa: PLC0415
    return loadout.nomes_das_caixas()


def listar(con, slot: str | None = None, so_abertas: bool = True,
           nm: str | None = None) -> list[dict]:
    """As encomendas, abertas por omissão, com o nome da caixa."""
    q = "SELECT * FROM encomendas WHERE 1=1"
    args: list = []
    if so_abertas:
        q += " AND (qty_a_caminho > 0 OR qty_pendente_foto > 0)"
    if slot is not None:
        q += " AND slot = ?"
        args.append(slot)
    if nm:
        q += " AND card_name = ?"
        args.append(_front(nm))
    q += " ORDER BY COALESCE(slot, ''), card_name, id"
    nomes = _nomes(con)
    return [_linha(r, nomes) for r in con.execute(q, args)]


def por_id(con, ident: int) -> dict | None:
    r = con.execute("SELECT * FROM encomendas WHERE id = ?", (int(ident),)).fetchone()
    return _linha(r, _nomes(con)) if r else None


def abertas_por_caixa(con) -> dict[tuple[str | None, str], dict]:
    """`(slot, carta) -> {a_caminho, pendente, ids}` — o que o loadout desconta."""
    out: dict[tuple[str | None, str], dict] = {}
    for r in con.execute(
            "SELECT id, slot, card_name, qty_a_caminho, qty_pendente_foto "
            "FROM encomendas WHERE qty_a_caminho > 0 OR qty_pendente_foto > 0 "
            "ORDER BY id"):
        g = out.setdefault((r["slot"], r["card_name"]),
                           {"a_caminho": 0, "pendente": 0, "ids": []})
        g["a_caminho"] += r["qty_a_caminho"] or 0
        g["pendente"] += r["qty_pendente_foto"] or 0
        g["ids"].append(r["id"])
    return out


# ---------------------------------------------------------------------------
# Validação contra a caixa e o catálogo
# ---------------------------------------------------------------------------
def _slots(con, slots=None) -> list[dict]:
    from . import loadout                                  # noqa: PLC0415
    return slots if slots is not None else loadout.resolve_slots(con)


def slot_de(slots, slot_id: str | None) -> dict | None:
    if not slot_id:
        return None
    s = next((x for x in slots if x.get("slot") == slot_id), None)
    if s is None:
        raise KeyError(slot_id)
    return s


def cumpre_regra(con, s: dict | None, nm: str, set_code: str | None,
                 lang: str | None, finish: str | None) -> tuple[bool, str]:
    """`(cumpre, porquê não)` — a impressão/língua/acabamento serve a caixa?

    É a leitura em positivo das regras de material, a mesma do *"já a tenho"*
    (`impressoes_da_falta` para a edição, `finishes_aceites` para o acabamento,
    `lingua` para a língua). As básicas são isentas, como na alocação.
    """
    from . import loadout                                  # noqa: PLC0415
    if s is None or nm in loadout.BASICS:
        return True, ""
    req = loadout.requisito_material(s) or "sem regra"
    if s.get("lingua") and lang and lang.lower() != s["lingua"].lower():
        return False, f"{s['nome']} só usa {s['lingua'].upper()} ({req})"
    fa = loadout.finishes_aceites(s)
    if fa and finish and finish not in fa:
        return False, f"{s['nome']} só usa {'/'.join(fa)} ({req})"
    if set_code:
        validas = {e["set"] for e in loadout.impressoes_da_falta(con, s, nm, limite=999)}
        if set_code.lower() not in validas:
            return False, f"{set_code.upper()} não serve a caixa {s['nome']} ({req})"
    return True, ""


def validar(con, s: dict | None, nm: str, set_code: str | None = None,
            collector_number: str | None = None, lang: str | None = None,
            finish: str | None = None) -> dict:
    """O nome oracle, a impressão e o material de uma encomenda, validados.

    Recusa com `ValueError` e o motivo: uma carta que o catálogo não conhece,
    uma edição que não existe, ou material que a caixa não aceita — o mesmo
    409 do «já a tenho». Sem língua/acabamento vale o da caixa
    (`material_da_caixa`); sem caixa, `en`/`nonfoil`, como o CSV assume.
    """
    from . import loadout                                  # noqa: PLC0415
    nome = (nm or "").strip()
    if not nome:
        raise ValueError("sem carta")
    oracle = scryfall.resolve_name(con, nome)
    if not oracle:
        raise ValueError(f"{nome!r} não está no catálogo")
    nome = _front(oracle)
    set_code = (set_code or "").strip().lower() or None
    collector_number = (collector_number or "").strip() or None
    if s is not None:
        fin_c, lang_c = loadout.material_da_caixa(s)
        # O Pauper é "foil se houver, senão nonfoil": uma encomenda dele pode
        # ser qualquer um dos dois. `material_da_caixa` diz foil porque é o que
        # a caixa PREFERE; aqui fica o que ele disser, senão a preferência.
        finish = (finish or fin_c).lower()
        lang = (lang or lang_c).lower()
    else:
        finish = (finish or "nonfoil").lower()
        lang = (lang or "en").lower()
    if finish not in ("nonfoil", "foil", "etched"):
        raise ValueError(f"acabamento {finish!r} desconhecido (nonfoil|foil|etched)")
    if set_code and scryfall.find_printing(con, oracle, set_code,
                                           collector_number) is None:
        raise ValueError(f"{nome}: a impressão {set_code.upper()}"
                         f"{' #' + collector_number if collector_number else ''} "
                         f"não existe no catálogo")
    ok, porque = cumpre_regra(con, s, nome, set_code, lang, finish)
    if not ok:
        raise ValueError(porque)
    return {"nm": nome, "set_code": set_code, "collector_number": collector_number,
            "lang": lang, "finish": finish}


# ---------------------------------------------------------------------------
# Escritas: `+`, `−`, «Chegou», «desfazer»
# ---------------------------------------------------------------------------
def _toca(con, ident: int) -> None:
    con.execute("UPDATE encomendas SET actualizado_em = datetime('now') WHERE id = ?",
                (ident,))


def _acha(con, nm, slot, set_code, collector_number, lang, finish):
    return con.execute(
        """SELECT * FROM encomendas WHERE card_name = ? AND slot IS ?
             AND set_code IS ? AND collector_number IS ? AND lang = ? AND finish = ?
            ORDER BY id DESC LIMIT 1""",
        (nm, slot, set_code, collector_number, lang, finish)).fetchone()


def adicionar(con, slot: str | None, nm: str, qty: int = 1, *,
              set_code: str | None = None, collector_number: str | None = None,
              lang: str | None = None, finish: str | None = None,
              origem: str | None = None, preco: float | None = None,
              notas: str | None = None, estado: str = A_CAMINHO,
              slots=None, log_path: Path | None = None) -> dict:
    """O `+`: mais `qty` cópias encomendadas (ou, com `estado=PENDENTE`, o «já a
    tenho»: ficam logo pendentes de foto). Uma linha com a mesma chave (carta,
    impressão, língua, acabamento, caixa) soma; senão nasce uma.

    Não cria cópia nenhuma nem linha na `copy_allocation` — é a regra.
    """
    if estado not in ESTADOS:
        raise ValueError(f"estado {estado!r} desconhecido")
    slots = _slots(con, slots)
    s = slot_de(slots, slot)
    v = validar(con, s, nm, set_code, collector_number, lang, finish)
    q = max(1, int(qty))
    caixa = s["nome"] if s else None
    coluna = "qty_a_caminho" if estado == A_CAMINHO else "qty_pendente_foto"
    _log("+" if estado == A_CAMINHO else "pendente", v["nm"], impressao(v), q,
         caixa, origem, "", log_path)
    r = _acha(con, v["nm"], slot, v["set_code"], v["collector_number"],
              v["lang"], v["finish"])
    if r is None:
        cur = con.execute(
            f"""INSERT INTO encomendas (card_name, set_code, collector_number, lang,
                                        finish, slot, {coluna}, origem, preco_unit,
                                        notas)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (v["nm"], v["set_code"], v["collector_number"], v["lang"], v["finish"],
             slot, q, origem, preco, notas))
        ident = cur.lastrowid
    else:
        ident = r["id"]
        # O `+` numa linha que já teve um aviso limpa-o: ele acabou de dizer que
        # vem outra, e o aviso era sobre a foto anterior.
        con.execute(
            f"""UPDATE encomendas SET {coluna} = {coluna} + ?, aviso = NULL,
                   origem = COALESCE(?, origem), preco_unit = COALESCE(?, preco_unit),
                   notas = COALESCE(?, notas)
             WHERE id = ?""", (q, origem, preco, notas, ident))
    _toca(con, ident)
    con.commit()
    return por_id(con, ident)


def _linhas_de(con, ident=None, slot=None, nm=None, so: str | None = None
               ) -> list[sqlite3.Row]:
    """As linhas a que um gesto se aplica: por `id`, ou todas as de (caixa, carta).
    `so` limita às que têm quantidade num dos estados."""
    if ident is not None:
        rows = con.execute("SELECT * FROM encomendas WHERE id = ?",
                           (int(ident),)).fetchall()
    else:
        if not nm:
            raise ValueError("sem carta nem id")
        rows = con.execute(
            "SELECT * FROM encomendas WHERE card_name = ? AND slot IS ? "
            "ORDER BY id DESC", (_front(nm), slot or None)).fetchall()
    if so == A_CAMINHO:
        rows = [r for r in rows if (r["qty_a_caminho"] or 0) > 0]
    elif so == PENDENTE:
        rows = [r for r in rows if (r["qty_pendente_foto"] or 0) > 0]
    return rows


def remover(con, ident=None, *, slot=None, nm=None, qty: int = 1,
            estado: str | None = None, log_path: Path | None = None) -> dict:
    """O `−`: menos `qty` cópias, nunca abaixo de zero. Tira primeiro do que está
    a caminho e só depois do pendente de foto (`estado` força um dos dois). Uma
    linha que fique a zero sem nunca ter fechado nada apaga-se.
    """
    rows = _linhas_de(con, ident, slot, nm)
    resta, tirado, apagadas, nomes = max(1, int(qty)), 0, [], _nomes(con)
    for r in rows:
        if resta <= 0:
            break
        ac, pf = r["qty_a_caminho"] or 0, r["qty_pendente_foto"] or 0
        d_ac = min(ac, resta) if estado in (None, A_CAMINHO) else 0
        resta -= d_ac
        d_pf = min(pf, resta) if estado in (None, PENDENTE) else 0
        resta -= d_pf
        if not (d_ac or d_pf):
            continue
        tirado += d_ac + d_pf
        _log("-", r["card_name"], impressao(r), d_ac + d_pf,
             nomes.get(r["slot"]) or r["slot"], r["origem"],
             f"a caminho -{d_ac}, pendente -{d_pf}", log_path)
        con.execute("UPDATE encomendas SET qty_a_caminho = ?, qty_pendente_foto = ? "
                    "WHERE id = ?", (ac - d_ac, pf - d_pf, r["id"]))
        _toca(con, r["id"])
        if ac - d_ac == 0 and pf - d_pf == 0 and not (r["qty_fechada"] or 0):
            con.execute("DELETE FROM encomendas WHERE id = ?", (r["id"],))
            apagadas.append(r["id"])
    con.commit()
    return {"tirado": tirado, "apagadas": apagadas,
            "nm": rows[0]["card_name"] if rows else _front(nm or "")}


def chegou(con, ident=None, *, slot=None, nm=None, qty: int | None = None,
           log_path: Path | None = None) -> dict:
    """«Chegou (N)»: a caminho → pendente de foto. Continua a não ser cópia."""
    rows = _linhas_de(con, ident, slot, nm, so=A_CAMINHO)
    resta = None if qty is None else max(1, int(qty))
    movido, nomes = 0, _nomes(con)
    for r in rows:
        if resta is not None and resta <= 0:
            break
        ac = r["qty_a_caminho"] or 0
        d = ac if resta is None else min(ac, resta)
        if d <= 0:
            continue
        if resta is not None:
            resta -= d
        movido += d
        _log("chegou", r["card_name"], impressao(r), d,
             nomes.get(r["slot"]) or r["slot"], r["origem"], "", log_path)
        con.execute("UPDATE encomendas SET qty_a_caminho = qty_a_caminho - ?, "
                    "qty_pendente_foto = qty_pendente_foto + ? WHERE id = ?",
                    (d, d, r["id"]))
        _toca(con, r["id"])
    con.commit()
    return {"movido": movido, "nm": rows[0]["card_name"] if rows else _front(nm or "")}


def desfazer_chegou(con, ident=None, *, slot=None, nm=None, qty: int | None = None,
                    log_path: Path | None = None) -> dict:
    """O inverso do «Chegou»: pendente de foto → a caminho."""
    rows = _linhas_de(con, ident, slot, nm, so=PENDENTE)
    resta = None if qty is None else max(1, int(qty))
    movido, nomes = 0, _nomes(con)
    for r in rows:
        if resta is not None and resta <= 0:
            break
        pf = r["qty_pendente_foto"] or 0
        d = pf if resta is None else min(pf, resta)
        if d <= 0:
            continue
        if resta is not None:
            resta -= d
        movido += d
        _log("desfazer", r["card_name"], impressao(r), d,
             nomes.get(r["slot"]) or r["slot"], r["origem"], "", log_path)
        con.execute("UPDATE encomendas SET qty_a_caminho = qty_a_caminho + ?, "
                    "qty_pendente_foto = qty_pendente_foto - ? WHERE id = ?",
                    (d, d, r["id"]))
        _toca(con, r["id"])
    con.commit()
    return {"movido": movido, "nm": rows[0]["card_name"] if rows else _front(nm or "")}


# ---------------------------------------------------------------------------
# O DESCONTO no loadout
# ---------------------------------------------------------------------------
def descontar(con, slots: list[dict]) -> list[dict]:
    """`a comprar = falta − a caminho − pendente de foto`, linha a linha.

    Corre no `loadout.allocate` DEPOIS da partilha de compras (a encomenda é de
    uma caixa concreta; se essa caixa era quem comprava numa partilha, é a ela
    que se desconta, e as outras continuam a dizer «depois de X comprar» — que
    é verdade: X encomendou-a). A alocação (`copy_allocation`, `got`, `pct`)
    NÃO mexe: uma encomenda não é uma cópia.

    Devolve os AVISOS: encomendas para uma caixa que já não pede a carta (a
    lista vigiada mudou, a carta veio de outro lado, ou a caixa saiu do
    config). Ficam visíveis e não descontam noutra caixa — simples, sem regra
    de redistribuição.
    """
    abertas = abertas_por_caixa(con)
    if not abertas:
        return []
    nomes = {s["slot"]: s["nome"] for s in slots}
    avisos = []
    for (slot, nm), g in abertas.items():
        s = next((x for x in slots if x["slot"] == slot), None) if slot else None
        if slot and s is None:
            avisos.append({"slot": slot, "caixa": slot, "nm": nm,
                           "q": g["a_caminho"] + g["pendente"], "ids": g["ids"],
                           "porque": "a caixa já não existe no config"})
            continue
        if s is None:
            continue                       # para a colecção: não desconta caixa
        resta_ac, resta_pf = g["a_caminho"], g["pendente"]
        for m in sorted((m for m in s["missing"] if m["nm"] == nm),
                        key=lambda m: (m["board"] != "main", m["nm"])):
            if resta_ac + resta_pf <= 0:
                break
            take = min(m["comprar"], resta_ac + resta_pf)
            if take <= 0:
                continue
            d_pf = min(resta_pf, take)
            d_ac = take - d_pf
            resta_pf -= d_pf
            resta_ac -= d_ac
            m["pendente_foto"] = m.get("pendente_foto", 0) + d_pf
            m["a_caminho"] = m.get("a_caminho", 0) + d_ac
            m["encomendado"] = m.get("encomendado", 0) + take
            m["comprar"] -= take
            m["cost"] = round((m["unit"] or 0) * m["comprar"], 2)
        sobra = resta_ac + resta_pf
        if sobra > 0:
            pede = any(m["nm"] == nm for m in s["missing"] + s["have"])
            avisos.append({"slot": slot, "caixa": nomes.get(slot) or slot, "nm": nm,
                           "q": sobra, "ids": g["ids"],
                           "porque": (f"a mais do que a caixa pede ({sobra})"
                                      if pede else "a caixa já não a pede")})
    return sorted(avisos, key=lambda a: (a["caixa"], a["nm"]))


# ---------------------------------------------------------------------------
# A CONCILIAÇÃO PELA FOTO (chamada pelo `collection.import_csv`)
# ---------------------------------------------------------------------------
def _prioridade(con, cache: dict | None) -> dict[str, int]:
    """`slot -> prioridade` da alocação, uma vez por importação."""
    if cache is not None and "prioridade" in cache:
        return cache["prioridade"]
    from . import loadout                                  # noqa: PLC0415
    try:
        slots = loadout.resolve_slots(con)
    except Exception:                                      # noqa: BLE001
        slots = []                          # sem config: nada a alocar
    pri = {s["slot"]: s["prioridade"] for s in slots}
    if cache is not None:
        cache["prioridade"] = pri
        cache["slots"] = slots
    return pri


def conciliar(con, *, nm: str, set_code: str, collector_number: str | None,
              lang: str, finish: str, qty: int, photo_path: str | None = None,
              sub_collection: str | None = None, condition: str = "NM",
              acquired_price: float | None = None, notes: str | None = None,
              cache: dict | None = None, log_path: Path | None = None
              ) -> dict | None:
    """Uma linha de foto fecha as encomendas PENDENTES DE FOTO da mesma carta.

    Por ordem: mesma carta + língua + acabamento (+ edição, se a encomenda a
    tiver), a caixa de maior prioridade primeiro. Para cada uma: cria a cópia
    (com `photo_path`), baixa o pendente, guarda o `copy_id` na encomenda e
    ALOCA a cópia à caixa — só se a impressão cumprir a regra de material
    dela. Se não cumprir, não se toca na encomenda (fica aberta, com o aviso
    *"a foto trouxe X, que não cumpre a regra da caixa"*) e a linha segue o
    caminho normal: a cópia entra na Colecção, sem caixa. Nunca se lava a
    regra com um registo (ponto 5 do CLAUDE.md).

    Devolve `None` sem nenhuma pendente desta carta; senão `{copias, fechadas,
    restante, linhas, avisos}` — o `restante` é o que a foto trouxe a mais e
    entra como sempre.
    """
    from . import collection, loadout                      # noqa: PLC0415
    oracle = scryfall.resolve_name(con, nm) or nm
    frente = _front(oracle)
    set_code = (set_code or "").lower()
    rows = con.execute(
        """SELECT * FROM encomendas
            WHERE qty_pendente_foto > 0 AND card_name = ? AND lang = ? AND finish = ?
              AND (set_code IS NULL OR set_code = ?)
              AND (collector_number IS NULL OR collector_number = ?)""",
        (frente, (lang or "en").lower(), (finish or "nonfoil").lower(), set_code,
         collector_number or "")).fetchall()
    if not rows:
        return None
    pri = _prioridade(con, cache)
    slots = (cache or {}).get("slots") or []
    nomes = {s["slot"]: s["nome"] for s in slots}
    rows.sort(key=lambda r: (r["slot"] is None, pri.get(r["slot"], 999), r["id"]))
    resta, linhas, avisos, ids = max(int(qty), 0), [], [], []
    for r in rows:
        if resta <= 0:
            break
        # Uma caixa que saiu do config dá `s = None`: a cópia entra na Colecção,
        # sem caixa, e a encomenda fecha na mesma — ninguém a pode alocar, e o
        # relatório já a mostrava com «a caixa já não existe».
        s = next((x for x in slots if x["slot"] == r["slot"]), None) if r["slot"] else None
        ok, porque = cumpre_regra(con, s, frente, set_code, lang, finish)
        if not ok:
            aviso = (f"a foto trouxe {set_code.upper()} {lang} {finish}, que não "
                     f"cumpre a regra da caixa: {porque}")
            con.execute("UPDATE encomendas SET aviso = ? WHERE id = ?",
                        (aviso, r["id"]))
            _toca(con, r["id"])
            avisos.append({"id": r["id"], "nm": frente, "aviso": aviso})
            _log("foto-recusada", frente, impressao(r), 0,
                 nomes.get(r["slot"]) or r["slot"], r["origem"], aviso, log_path)
            continue
        take = min(resta, r["qty_pendente_foto"] or 0)
        if take <= 0:
            continue
        nota = f"encomenda #{r['id']}" + (f" ({r['origem']})" if r["origem"] else "")
        copy_id = collection.add_copy(
            con, oracle, set_code=set_code, collector_number=collector_number,
            quantity=take, finish=finish, language=lang, condition=condition,
            sub_collection=sub_collection or loadout.BALDE_COLECCAO,
            photo_path=photo_path,
            acquired_price=(acquired_price if acquired_price is not None
                            else r["preco_unit"]),
            notes=(f"{notes} | {nota}" if notes else nota))
        _log("foto->copia", frente, f"{set_code.upper()}"
             f"{' #' + collector_number if collector_number else ''} · {lang} · {finish}",
             take, nomes.get(r["slot"]) or r["slot"], r["origem"],
             f"copy_id {copy_id}" + (" · alocada à caixa" if s else ""), log_path)
        ja = json.loads(r["copy_ids"] or "[]")
        con.execute(
            """UPDATE encomendas SET qty_pendente_foto = qty_pendente_foto - ?,
                      qty_fechada = qty_fechada + ?, copy_ids = ?, aviso = NULL
                WHERE id = ?""",
            (take, take, json.dumps(ja + [copy_id]), r["id"]))
        _toca(con, r["id"])
        if s is not None:
            con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity, "
                        "placed_at) VALUES (?,?,?,datetime('now'))",
                        (copy_id, r["slot"], take))
        resta -= take
        ids.append(copy_id)
        linhas.append({"id": r["id"], "slot": r["slot"],
                       "caixa": nomes.get(r["slot"]) or r["slot"] or "",
                       "q": take, "copy_id": copy_id, "alocada": s is not None})
    con.commit()
    if not linhas and not avisos:
        return None
    return {"copias": ids, "fechadas": int(qty) - resta, "restante": resta,
            "linhas": linhas, "avisos": avisos}


# ---------------------------------------------------------------------------
# `pendentes/esperadas.md`: o que o Claude das fotos deve esperar
# ---------------------------------------------------------------------------
def esperadas_md(con, slots=None) -> str:
    """O texto: o que está pendente de foto, por caixa, com o material esperado.
    Vazio quando não há nada — e aí o ficheiro apaga-se (`escrever_esperadas`)."""
    from . import collection, loadout                      # noqa: PLC0415
    slots = _slots(con, slots)
    nomes = {s["slot"]: s["nome"] for s in slots}
    pend = [r for r in listar(con) if (r["qty_pendente_foto"] or 0) > 0]
    sem_foto = collection.copias_sem_foto(con)
    if not pend and not sem_foto:
        return ""
    out = ["# Fotos esperadas (gerado pelo mtgvault — não editar)", "",
           "Estas cartas estão **pendentes de foto**: o André disse que as tem "
           "(ou que chegaram) e ainda não as fotografou. Quando uma foto de uma "
           "destas aparecer, escreve a linha com a MESMA língua e acabamento "
           "que aqui está — é por eles que o import a liga à encomenda e a mete "
           "na caixa. A edição, se aqui disser «qualquer», é a que a foto "
           "mostrar; confirma-a no catálogo como sempre.", ""]
    por_caixa: dict[str, list[dict]] = {}
    for r in pend:
        por_caixa.setdefault(nomes.get(r["slot"]) or r["slot"] or "Colecção", []).append(r)
    for caixa, rs in sorted(por_caixa.items()):
        s = next((x for x in slots if x.get("nome") == caixa), None)
        req = loadout.requisito_material(s) if s else ""
        out.append(f"## {caixa}" + (f" — {req}" if req else ""))
        for r in rs:
            out.append(f"- {r['qty_pendente_foto']}× **{r['nm']}** — "
                       f"{r['impressao']}"
                       + (f" · {r['origem']}" if r["origem"] else "")
                       + (f" · ⚠️ {r['aviso']}" if r["aviso"] else ""))
        out.append("")
    if sem_foto:
        out.append("## Na base, sem foto")
        out.append("Cópias que já existem na base (foram registadas sem foto, ou "
                   "com a edição por confirmar). Uma foto destas ACERTA/LIGA-SE à "
                   "cópia que já existe — não cria outra.")
        for c in sem_foto:
            out.append(f"- {c['q']}× **{c['nm']}** — {c['impressao']}"
                       + (" · edição por confirmar" if c["por_confirmar"] else "")
                       + (f" · em {c['caixa']}" if c.get("caixa") else ""))
        out.append("")
    return "\n".join(out)


def escrever_esperadas(con, pasta: Path | str, slots=None) -> Path | None:
    """Escreve `<pasta>/esperadas.md`; apaga-o quando não há nada pendente, para o
    Claude das fotos não ler uma lista de ontem. Devolve o caminho ou `None`."""
    pasta = Path(pasta)
    alvo = pasta / "esperadas.md"
    texto = esperadas_md(con, slots)
    if not texto:
        if alvo.exists():
            alvo.unlink()
        return None
    pasta.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_name(alvo.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    tmp.replace(alvo)
    return alvo
