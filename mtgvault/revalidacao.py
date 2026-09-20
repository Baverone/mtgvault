"""REVALIDAÇÃO POR FOTO de toda a colecção (André, 2026-09-20).

À letra: *"quero que quando se clique, ele mostre as cartas, como está a fazer,
e que depois peça a foto das cartas. Quero revalidar todas as fotos agora que
vamos colocar tudo em decks para que nada falhe ou escape; assim o que eu for
vender também vai com foto e vamos pouco a pouco arrumando tudo no devido lugar
e bem feito."*

É uma CAMPANHA: a partir de `colecao_config.json → revalidacao.desde` NENHUMA
cópia está validada até uma foto NOVA (tirada nesta campanha) lhe ser ligada.
Ele vai caixa a caixa — abre a caixa na Deckboxes, vê as cartas, carrega em
«Fotografar esta caixa» (o ALVO fica no config e o `pendentes/esperadas.md`
diz ao Claude das fotos o que esperar), fotografa, larga em `pendentes/`, e a
corrida das 02:30 (`mtg-fotos-novas`, que não se altera) importa: cada foto
**liga-se à cópia que já existe** em vez de criar outra. O mesmo para o que
vai vender e, no fim, para a Caixa RL e a Colecção.

O ESTADO vive em duas colunas da `copies` (`validado_em`, `foto_anterior`) e
NÃO muda um único número da alocação, da venda ou do «fechar tudo» — é só o
📷/✓/⚠ que a página mostra e o progresso. A conciliação é o passo (0) do
`collection.import_csv`, à frente das quatro regras de 2026-09-19:

  (0)  a linha casa com uma cópia POR REVALIDAR da mesma impressão exacta
       (nome + edição + número + língua + acabamento) → `revalidar`: liga a
       foto (`photo_path` novo, `foto_anterior`, `validado_em`), não cria
       cópia; prefere as cópias do ALVO, depois qualquer;
  (0b) DISCREPÂNCIA — não há cópia igual à foto, mas o alvo tem uma cópia por
       revalidar da MESMA CARTA noutra edição/acabamento/língua → `corrigir`:
       é uma correcção, não uma carta nova. A cópia passa a ser o que a foto
       prova, com linha em `data/revalidacao.log`; se depois disso deixar de
       cumprir a regra de material da caixa, sai da `copy_allocation` (nunca
       se lava a regra com um registo — ponto 5 do CLAUDE.md);
  (i)–(iv) como antes; o que entrar por (iv) fica «nova nesta campanha».

A decisão dele de 09/09 mantém-se: NADA se apaga. Uma cópia que nunca receba
foto continua por revalidar e visível — é para isso que serve a lista.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from collections import defaultdict
from pathlib import Path

from . import db, scryfall, sources

MARCA_CORRIGIDA = "corrigida pela foto"
MARCA_NOVA = "nova nesta campanha"
MARCA_SAIU = "saiu da caixa"
TIPOS = ("caixa", "venda", "rl", "coleccao")
BALDE_RL = "Caixa Reserved List"
TITULO = {"venda": "Venda", "rl": "Caixa Reserved List",
          "coleccao": "Colecção (o resto)"}


# ---------------------------------------------------------------------------
# Config: a campanha e o alvo
# ---------------------------------------------------------------------------
def config() -> dict:
    v = sources.config().get("revalidacao")
    return v if isinstance(v, dict) else {}


def desde() -> str | None:
    """A data em que a campanha começou (`revalidacao.desde`); `None` = desligada."""
    d = config().get("desde")
    return str(d) if d else None


def hoje() -> str:
    return dt.date.today().isoformat()


def activa(quando: str | None = None) -> bool:
    d = desde()
    return bool(d) and (quando or hoje()) >= d


def marca_validada(photo_path: str | None, quando: str | None = None) -> str | None:
    """O `validado_em` a escrever numa cópia que ganha uma foto AGORA: a data,
    se a campanha estiver ligada e houver foto; senão nada."""
    if not photo_path or not activa(quando):
        return None
    return quando or hoje()


def extra_validada(photo_path: str | None) -> dict:
    """O `extra` do `collection._partir_copia` para uma cópia que uma foto
    acaba de confirmar/ligar: `{validado_em}` com a campanha ligada, `{}` sem."""
    m = marca_validada(photo_path)
    return {"validado_em": m} if m else {}


def nota_nova(notes: str | None) -> str | None:
    """As `notes` de uma cópia que ENTRA de novo durante a campanha: leva a
    marca «nova nesta campanha (<data>)» — é a lista do que apareceu nas fotos
    sem cópia na base, a resposta a *"o que escapou?"*."""
    if not activa():
        return notes
    marca = f"{MARCA_NOVA} ({hoje()})"
    return f"{notes} | {marca}" if notes else marca


def alvo() -> dict | None:
    """O que ele está a fotografar AGORA (`revalidacao.alvo`): `{tipo, slot, em}`.

    Vive no config porque é uma preferência, como as `caixas`: o `daily` das
    08:00 e o `webapp.py` têm de escrever o mesmo `esperadas.md`, e o import
    das 02:30 tem de saber a que caixa dar preferência — três processos, um
    ficheiro só.
    """
    a = config().get("alvo")
    if not isinstance(a, dict) or a.get("tipo") not in TIPOS:
        return None
    if a["tipo"] == "caixa" and not a.get("slot"):
        return None
    return dict(a)


def definir_alvo(cfg: dict, tipo: str, slot: str | None = None) -> dict:
    """Escreve o alvo no `cfg` (em memória; quem grava é quem chama)."""
    if tipo not in TIPOS:
        raise ValueError(f"alvo {tipo!r} desconhecido ({'/'.join(TIPOS)})")
    if tipo == "caixa" and not slot:
        raise ValueError("um alvo de caixa precisa do slot")
    r = cfg.get("revalidacao")
    if not isinstance(r, dict):
        r = cfg["revalidacao"] = {}
    r.setdefault("desde", hoje())
    r["alvo"] = {"tipo": tipo, "slot": slot if tipo == "caixa" else None,
                 "em": hoje()}
    return r["alvo"]


def limpar_alvo(cfg: dict) -> bool:
    r = cfg.get("revalidacao")
    if isinstance(r, dict) and r.get("alvo"):
        r["alvo"] = None
        return True
    return False


# ---------------------------------------------------------------------------
# O rasto
# ---------------------------------------------------------------------------
def ficheiro_log() -> Path:
    """`data/revalidacao.log` — ao lado da base, como o `encomendas.log`."""
    return db.pasta_dados() / "revalidacao.log"


def _log(accao: str, detalhe: str, log_path: Path | None = None) -> Path:
    alvo_ = log_path or ficheiro_log()
    alvo_.parent.mkdir(parents=True, exist_ok=True)
    agora = dt.datetime.now().replace(microsecond=0).isoformat(sep=" ")
    with alvo_.open("a", encoding="utf-8") as fh:
        fh.write("\t".join(c.replace("\t", " ").replace("\n", " ")
                           for c in (agora, accao, detalhe)) + "\n")
    return alvo_


def impressao(r) -> str:
    """`NEM #17 nonfoil en` — a impressão de uma cópia, para o log e as listas."""
    d = dict(r)
    sc = (d.get("set_code") or "").upper()
    num = d.get("collector_number") or d.get("num") or ""
    return " ".join(p for p in (sc + (f" #{num}" if num else ""),
                                d.get("finish") or d.get("fin") or "",
                                d.get("language") or d.get("lang") or "") if p)


# ---------------------------------------------------------------------------
# (0) a foto de uma cópia por revalidar
# ---------------------------------------------------------------------------
def _sel_copias(con, where: str, args: tuple) -> list[sqlite3.Row]:
    from . import collection                               # noqa: PLC0415
    return con.execute(
        f"""SELECT cp.*, c.name card_name, c.set_code, c.collector_number
              FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
             WHERE {collection.na_estante()} AND cp.validado_em IS NULL
               AND (cp.notes IS NULL OR cp.notes NOT LIKE ?)
               AND {where} ORDER BY cp.id""",
        (f"%{collection.MARCA_POR_CONFIRMAR}%", *args)).fetchall()


def copias_por_revalidar(con, name: str | None = None) -> list[sqlite3.Row]:
    """As cópias na estante sem foto desta campanha (as «edição por confirmar»
    ficam de fora: são do `acertar_edicao`, que também as valida)."""
    if name:
        return _sel_copias(con, "(c.name = ? OR c.name LIKE ? || ' //%')",
                           (name, name))
    return _sel_copias(con, "1=1", ())


def _ordem(preferir, qtd):
    pref = set(preferir or ())
    return lambda r: (r["id"] not in pref, (r["quantity"] or 0) != qtd,
                      (r["quantity"] or 0) > qtd, -(r["quantity"] or 0), r["id"])


def revalidar(con, name: str, set_code: str, *, collector_number: str | None = None,
              language: str = "en", finish: str = "nonfoil", quantity: int = 1,
              photo_path: str | None = None, preferir=None,
              quando: str | None = None) -> dict | None:
    """Liga a foto NOVA a cópias por revalidar da MESMA impressão exacta.

    Prefere as do alvo (`preferir`), depois a cópia com a mesma quantidade da
    foto, depois as menores (gastam-se inteiras) e só então uma maior, que se
    parte. Devolve `{copy_id, copias, ligadas, restante}` ou `None`.
    """
    if not photo_path or not set_code:
        return None
    from . import collection                               # noqa: PLC0415
    num = collector_number or ""
    rows = _sel_copias(
        con, "(c.name = ? OR c.name LIKE ? || ' //%') AND lower(c.set_code) = lower(?)"
             " AND (? = '' OR c.collector_number = ?) AND cp.language = ? AND cp.finish = ?",
        (name, name, set_code, num, num, language, finish))
    if not rows:
        return None
    qtd = max(int(quantity), 0)
    rows = sorted(rows, key=_ordem(preferir, qtd))
    dia = quando or hoje()
    resta, tocadas = qtd, []
    for p in rows:
        if resta <= 0:
            break
        leva = min(resta, p["quantity"] or 0)
        if leva <= 0:
            continue
        resta -= leva
        tocadas.append(collection._partir_copia(
            con, p, leva, extra={"photo_path": photo_path,
                                 "foto_anterior": p["photo_path"],
                                 "validado_em": dia}))
    if not tocadas:
        return None
    con.commit()
    return {"copy_id": tocadas[0], "copias": tocadas,
            "ligadas": qtd - resta, "restante": resta}


# ---------------------------------------------------------------------------
# (0b) a discrepância: a cópia do alvo é esta carta, mas não esta impressão
# ---------------------------------------------------------------------------
def corrigir(con, name: str, set_code: str, *, collector_number: str | None = None,
             language: str = "en", finish: str = "nonfoil", quantity: int = 1,
             photo_path: str | None = None, alvo: dict | None = None,
             cache: dict | None = None, log_path: Path | None = None,
             quando: str | None = None) -> dict | None:
    """A foto traz `name` numa edição/acabamento/língua que o ALVO não tem —
    mas o alvo tem essa carta por revalidar noutra. É uma CORRECÇÃO da cópia
    da caixa (o que ele fotografou é o que lá está), não uma carta nova.

    Escreve a linha no `revalidacao.log` («cópia 123: NEM 17 nonfoil en → NEM
    17 foil en, foto X») ANTES de mexer, e depois pergunta à alocação se a
    cópia corrigida ainda pode estar na caixa onde está registada
    (`loadout.lots(..., ids=)` → `contradiz`): se não, sai da
    `copy_allocation` com o porquê nas `notes` — a página mostra-o.
    Devolve `{copias, corrigidas, restante, motivos}` ou `None`.
    """
    if not photo_path or not set_code or not alvo or not alvo.get("copias"):
        return None
    from . import collection, loadout                      # noqa: PLC0415
    ids = sorted(int(i) for i in alvo["copias"])
    if not ids:
        return None
    card = scryfall.find_printing(con, name, set_code, collector_number)
    if card is None:
        oracle = scryfall.resolve_name(con, name)
        card = (scryfall.find_printing(con, oracle, set_code, collector_number)
                if oracle else None)
    if card is None:
        return None                        # o catálogo decide: entra como sempre
    marks = ",".join("?" * len(ids))
    rows = _sel_copias(
        con, f"(c.name = ? OR c.name LIKE ? || ' //%') AND cp.id IN ({marks})",
        (name, name, *ids))
    # Só as que NÃO são a impressão da foto: essas eram do passo (0).
    rows = [r for r in rows
            if not (r["scryfall_id"] == card["scryfall_id"]
                    and r["language"] == language and r["finish"] == finish)]
    if not rows:
        return None
    qtd = max(int(quantity), 0)
    rows = sorted(rows, key=_ordem(None, qtd))
    dia = quando or hoje()
    depois = impressao({"set_code": card["set_code"],
                        "collector_number": card["collector_number"],
                        "finish": finish, "language": language})
    resta, tocadas, motivos = qtd, [], []
    for p in rows:
        if resta <= 0:
            break
        leva = min(resta, p["quantity"] or 0)
        if leva <= 0:
            continue
        antes = impressao(p)
        _log("corrigida", f"cópia {p['id']}: {antes} → {depois}, foto "
                          f"{Path(photo_path).name} ({leva}× {p['card_name']})",
             log_path)
        nota = f"{MARCA_CORRIGIDA} em {dia}: {antes} → {depois}"
        notas = f"{p['notes']} | {nota}" if p["notes"] else nota
        novo = collection._partir_copia(
            con, p, leva, scryfall_id=card["scryfall_id"], notes=notas,
            extra={"finish": finish, "language": language,
                   "photo_path": photo_path, "foto_anterior": p["photo_path"],
                   "validado_em": dia})
        resta -= leva
        tocadas.append(novo)
        motivos.append(f"{leva} corrigida{'s' if leva > 1 else ''} pela foto: "
                       f"{antes} → {depois}")
        saiu = _sai_da_caixa_se_nao_cumpre(con, novo, dia, log_path)
        if saiu:
            motivos.append(saiu)
    if not tocadas:
        return None
    con.commit()
    return {"copias": tocadas, "corrigidas": qtd - resta, "restante": resta,
            "motivos": motivos}


def _sai_da_caixa_se_nao_cumpre(con, copy_id: int, dia: str,
                                log_path: Path | None) -> str:
    """Depois de uma correcção, a cópia ainda pode estar na caixa onde está
    registada? Quem responde é o mesmo `contradiz_a_caixa` da alocação (via
    `loadout.lots`, só para esta cópia). Se não pode, sai da `copy_allocation`
    e fica dito nas `notes` — nunca se lava a regra com um registo."""
    from . import loadout                                  # noqa: PLC0415
    for e in (lote for ls in loadout.lots(con, ids=[copy_id]).values() for lote in ls):
        if not e.get("caixa_registada") or not e.get("contradiz"):
            continue
        slot, nome = e["caixa_registada"], e.get("caixa_registada_nome") or e["caixa_registada"]
        con.execute("DELETE FROM copy_allocation WHERE copy_id = ? AND slot = ?",
                    (copy_id, slot))
        nota = f"{MARCA_SAIU} {nome} em {dia}: {e['contradiz']}"
        con.execute("UPDATE copies SET notes = COALESCE(notes || ' | ', '') || ? "
                    "WHERE id = ?", (nota, copy_id))
        _log("saiu-da-caixa", f"cópia {copy_id}: {nome} — {e['contradiz']}", log_path)
        return f"saiu da caixa {nome}: {e['contradiz']}"
    return ""


# ---------------------------------------------------------------------------
# Onde cada cópia está, para o progresso e para o alvo
# ---------------------------------------------------------------------------
def _copias(con) -> list[dict]:
    """Todas as cópias NA ESTANTE (jogador e colecionador), com o estado."""
    from . import collection, loadout                      # noqa: PLC0415
    out = []
    for r in con.execute(
            f"""SELECT cp.id, cp.quantity q, cp.finish, cp.language lang,
                       cp.purpose, cp.photo_path foto, cp.validado_em, cp.foto_anterior,
                       cp.notes notas, COALESCE(cp.condition, 'NM') cond,
                       s.name sub, c.name nm, c.scryfall_id sid, c.set_code,
                       c.collector_number num, COALESCE(c.reserved, 0) rl
                  FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                  LEFT JOIN sub_collections s ON s.id = cp.sub_collection_id
                 WHERE {collection.na_estante()} ORDER BY c.name, cp.id"""):
        d = dict(r)
        d["nm"] = d["nm"].split(" // ", 1)[0] if " // " in (d["nm"] or "") else d["nm"]
        d["sub"] = d["sub"] or "(sem balde)"
        n = d["notas"] or ""
        d["corrigida"] = MARCA_CORRIGIDA in n
        d["nova"] = MARCA_NOVA in n
        d["saiu"] = MARCA_SAIU in n
        d["validada"] = bool(d["validado_em"])
        d["estado"] = ("corr" if d["corrigida"] else "ok") if d["validada"] else "foto"
        d["foil"] = loadout.e_foil(d["finish"])
        d["nota"] = next((p.strip() for p in n.split("|")
                          if MARCA_CORRIGIDA in p or MARCA_SAIU in p), "")
        d["por_confirmar"] = collection.MARCA_POR_CONFIRMAR in n
        out.append(d)
    return out


def particao(con, rep: dict | None) -> dict[int, list[tuple]]:
    """`copy_id -> [(grupo, quantas)]`, com os grupos `("caixa", slot)`,
    `("venda",)`, `("rl",)`, `("resto",)` — a soma é a quantidade da cópia.

    A caixa vem da ALOCAÇÃO do relatório (o que a caixa tem e o que ela ainda
    vai tirar da gaveta — é isso que ele fotografa quando a monta) e da
    `copy_allocation` (o que está registado lá dentro, mesmo preso). A venda
    são as linhas `venda` + `venda_rl` do relatório. O resto parte-se pela
    gaveta: Caixa RL ou Colecção. Sem relatório só há caixas registadas.
    """
    from . import loadout                                  # noqa: PLC0415
    nomes = loadout.nomes_das_caixas()
    por_nome = {v: k for k, v in nomes.items()}
    caixa: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for cid, sl in loadout.alocacao_confirmada(con).items():
        for slot, q in sl.items():
            if slot in nomes:
                caixa[cid][slot] = max(caixa[cid][slot], q)
    if rep is not None:
        for ls in (rep.get("pool") or {}).values():
            for e in ls:
                for nome, n in (e.get("alocado") or {}).items():
                    slot = por_nome.get(nome)
                    if slot and n > 0:
                        caixa[e["id"]][slot] = max(caixa[e["id"]][slot], n)
                if e.get("caixa") and e["caixa"] in nomes:
                    caixa[e["id"]][e["caixa"]] = max(caixa[e["id"]][e["caixa"]], e["q"])
    venda: dict[int, int] = defaultdict(int)
    if rep is not None:
        for k in ("venda", "venda_rl"):
            for r in rep.get(k) or []:
                for cid, q in (r.get("copias") or []):
                    venda[int(cid)] += int(q)
    out: dict[int, list[tuple]] = {}
    for d in _copias(con):
        resta, partes = d["q"], []
        for slot, n in sorted(caixa.get(d["id"], {}).items()):
            leva = min(resta, n)
            if leva > 0:
                partes.append((("caixa", slot), leva))
                resta -= leva
        leva = min(resta, venda.get(d["id"], 0))
        if leva > 0:
            partes.append((("venda",), leva))
            resta -= leva
        if resta > 0:
            partes.append((("rl",) if d["sub"] == BALDE_RL else ("resto",), resta))
        out[d["id"]] = partes
    return out


def _chave(alvo_: dict) -> tuple:
    return ("caixa", alvo_["slot"]) if alvo_["tipo"] == "caixa" else (alvo_["tipo"],)


def copias_do_alvo(con, alvo_: dict, rep: dict | None) -> set[int]:
    chave = _chave(alvo_)
    return {cid for cid, partes in particao(con, rep).items()
            if any(g == chave for g, _q in partes)}


def alvo_da_importacao(con, cache: dict | None = None) -> dict | None:
    """O alvo com as cópias dele, para o `import_csv`: `{tipo, slot, nome,
    copias}`. Calcula o relatório UMA vez (fica na `cache`)."""
    a = alvo()
    if a is None:
        return None
    from . import loadout                                  # noqa: PLC0415
    if cache is not None and "rep" in cache:
        rep = cache["rep"]
    else:
        try:
            rep = loadout.report(con)
        except Exception:                                  # noqa: BLE001
            rep = None                     # sem config de caixas: só o registado
        if cache is not None:
            cache["rep"] = rep
    a["copias"] = copias_do_alvo(con, a, rep)
    a["nome"] = titulo(a)
    return a


def titulo(alvo_: dict) -> str:
    from . import loadout                                  # noqa: PLC0415
    if alvo_["tipo"] == "caixa":
        return "Caixa " + (loadout.nomes_das_caixas().get(alvo_["slot"]) or alvo_["slot"])
    return TITULO.get(alvo_["tipo"], alvo_["tipo"])


# ---------------------------------------------------------------------------
# O progresso: por caixa, venda, RL, resto
# ---------------------------------------------------------------------------
def _linha(d: dict, q: int, cores: dict, local: str) -> dict:
    from . import paginas                                  # noqa: PLC0415
    cor = cores.get(d["nm"], "C")
    return {"copy_id": d["id"], "nm": d["nm"], "q": q, "set": (d["set_code"] or "").upper(),
            "num": d["num"] or "", "lang": (d["lang"] or "").upper(), "fin": d["finish"],
            "foil": d["foil"], "sid": d["sid"], "estado": d["estado"],
            "validado_em": d["validado_em"] or "", "nota": d["nota"],
            "foto": bool(d["foto"]), "local": local, "cor": cor,
            "cor_nome": paginas.COR_NOME.get(cor, cor), "rl": bool(d["rl"]),
            "por_confirmar": d["por_confirmar"]}


def _grupo_vazio(chave, nome):
    return {"chave": list(chave), "nome": nome, "q": 0, "validadas": 0,
            "por_revalidar": 0, "corrigidas": 0, "linhas": []}


def progresso(con, rep: dict | None = None, dia: str | None = None) -> dict:
    """Tudo o que a aba «📷 Revalidação» e as caixas mostram.

    `caixas` (uma por caixa do config, com as LINHAS — é a lista «Na caixa»
    da aba de cada uma), `venda`, `rl`, `resto` (com as linhas por cor, para
    o botão «Fotografar» de cada um), `total`, o que entrou `hoje`, as
    `corrigidas` e as `novas` nesta campanha. As linhas vêm ordenadas por
    COR e nome — é como o binder está arrumado (a mesma lição do painel
    Montar).
    """
    from . import loadout, paginas                         # noqa: PLC0415
    dia = dia or hoje()
    copias = {d["id"]: d for d in _copias(con)}
    partes = particao(con, rep)
    nomes = loadout.nomes_das_caixas()
    meta = paginas._meta_cartas(con, sorted({d["nm"] for d in copias.values()}))
    cores = {n: paginas.cor_de(tl, ci) for n, (tl, ci) in meta.items()}
    ordem = paginas.COR_ORDEM
    grupos: dict[tuple, dict] = {("caixa", s): _grupo_vazio(("caixa", s), n)
                                 for s, n in nomes.items()}
    for k in ("venda", "rl", "coleccao"):
        grupos[(k if k != "coleccao" else "resto",)] = _grupo_vazio(
            (k if k != "coleccao" else "resto",), TITULO[k])
    for cid, ps in partes.items():
        d = copias[cid]
        for g, q in ps:
            grp = grupos.get(g)
            if grp is None:
                continue
            grp["q"] += q
            if d["validada"]:
                grp["validadas"] += q
            else:
                grp["por_revalidar"] += q
            if d["corrigida"]:
                grp["corrigidas"] += q
            local = (nomes.get(g[1]) if g[0] == "caixa"
                     else (BALDE_RL if d["sub"] == BALDE_RL else d["sub"]))
            grp["linhas"].append(_linha(d, q, cores, local))
    for grp in grupos.values():
        grp["linhas"].sort(key=lambda l: (ordem.get(l["cor"], 9), l["nm"],
                                          l["set"], l["copy_id"]))
    total = {"q": sum(d["q"] for d in copias.values()),
             "validadas": sum(d["q"] for d in copias.values() if d["validada"]),
             "por_revalidar": sum(d["q"] for d in copias.values() if not d["validada"]),
             "corrigidas": sum(d["q"] for d in copias.values() if d["corrigida"]),
             "novas": sum(d["q"] for d in copias.values() if d["nova"])}
    total["pct"] = round(100 * total["validadas"] / total["q"]) if total["q"] else 0

    def local_de(cid):
        ps = partes.get(cid) or []
        return " · ".join(dict.fromkeys(
            (nomes.get(g[1]) if g[0] == "caixa" else
             {"venda": "venda", "rl": BALDE_RL, "resto": "Colecção"}[g[0]])
            for g, _q in ps)) or copias[cid]["sub"]

    lista = lambda cond: sorted(                                  # noqa: E731
        (_linha(d, d["q"], cores, local_de(d["id"])) for d in copias.values() if cond(d)),
        key=lambda l: (ordem.get(l["cor"], 9), l["nm"], l["copy_id"]))
    a = alvo()
    return {
        "desde": desde(), "activa": activa(dia), "hoje": dia,
        "alvo": ({**a, "nome": titulo(a),
                  "por_revalidar": grupos[_chave(a)]["por_revalidar"]
                  if _chave(a) in grupos else 0} if a else None),
        "total": total,
        "caixas": [dict(grupos[("caixa", s)], slot=s) for s in nomes],
        "venda": grupos[("venda",)], "rl": grupos[("rl",)], "resto": grupos[("resto",)],
        "hoje_entradas": lista(lambda d: d["validado_em"] == dia),
        "corrigidas": lista(lambda d: d["corrigida"]),
        "novas": lista(lambda d: d["nova"]),
    }


def estado_das_copias(con) -> dict[int, dict]:
    """`copy_id -> {validada, corrigida, estado}` — para a aba Vender e a
    exportação marcarem cada linha sem refazer o progresso inteiro."""
    return {d["id"]: {"validada": d["validada"], "corrigida": d["corrigida"],
                      "estado": d["estado"], "validado_em": d["validado_em"] or ""}
            for d in _copias(con)}


def foto_da_linha(estado: dict[int, dict], copias) -> dict:
    """`{ok, falta}` de uma linha de venda (`copias: [[copy_id, q]]`)."""
    ok = falta = 0
    for cid, q in (copias or []):
        e = estado.get(int(cid))
        if e and e["validada"]:
            ok += int(q)
        else:
            falta += int(q)
    return {"ok": ok, "falta": falta}


# ---------------------------------------------------------------------------
# `pendentes/esperadas.md`: a secção da revalidação
# ---------------------------------------------------------------------------
def seccao_esperadas(con, rep: dict | None = None) -> list[str]:
    """As linhas do `esperadas.md` para o ALVO: o que está por revalidar nele,
    com a impressão esperada e a quantidade. Vazio sem alvo ou sem nada por
    revalidar. Quem cola isto no ficheiro é o `encomendas.esperadas_md`."""
    a = alvo()
    if a is None:
        return []
    if rep is None:
        from . import loadout                              # noqa: PLC0415
        try:
            rep = loadout.report(con)
        except Exception:                                  # noqa: BLE001
            rep = None                     # sem caixas no config: só o registado
    prog = progresso(con, rep)
    grp = (next((c for c in prog["caixas"] if c["slot"] == a["slot"]), None)
           if a["tipo"] == "caixa" else prog[{"venda": "venda", "rl": "rl",
                                              "coleccao": "resto"}[a["tipo"]]])
    if not grp:
        return []
    por = [l for l in grp["linhas"] if l["estado"] == "foto"]
    if not por:
        return []
    out = [f"## {titulo(a)} — por revalidar ({sum(l['q'] for l in por)} cópias)",
           "O André está a REVALIDAR estas cópias por foto (campanha de "
           f"{prog['desde']}): fotografa-as e escreve a impressão que VÊS na foto "
           "(edição, número, língua, acabamento), não a que aqui está. Se o que "
           "vês for diferente do esperado, escreve o que vês na mesma e diz em "
           "`notes` o que esperavas (ex.: «esperava NEM nonfoil, é foil») — o "
           "import corrige a cópia da caixa, não cria outra. Uma foto pode ter "
           "várias cartas; a `quantity` é o que está NA FOTO."]
    junto: dict[tuple, dict] = {}
    for l in por:
        k = (l["nm"], l["set"], l["num"], l["lang"], l["fin"])
        g = junto.setdefault(k, {"q": 0, "ids": []})
        g["q"] += l["q"]
        g["ids"].append(l["copy_id"])
    for (nm, sc, num, lang, fin), g in junto.items():
        out.append(f"- {g['q']}× **{nm}** — {sc}{' #' + num if num else ''} · "
                   f"{lang.lower()} · {fin} · cópia"
                   f"{'s' if len(g['ids']) > 1 else ''} #"
                   + ", #".join(str(i) for i in g["ids"]))
    out.append("")
    return out
