"""A FEIRA: moeda de troca vs. o que quero trazer (André, 2026-09-20, à letra).

*"como vou ter um objetivo de ir ao RC "trocar" cartas nas bancas, fazemos logo
uma projeção do que vou levar como moeda de troca para o que quero trazer;
indico-te a wantlist e prováveis vendors que lá estarão, que poderão ter os
preços das cartas no market, e avaliamos; será sobretudo cartas que eu preciso
para completar decks."*

Três perguntas, e as três respondem-se com o que a base JÁ sabe — nem uma
consulta ao Cardmarket a partir daqui (os preços são os do `card_price`, o
mesmo `price_latest.trend` de todas as páginas):

LEVAR (a moeda de troca)
------------------------
A lista de venda de hoje (`rep["venda"]` + `rep["venda_rl"]`, as duas saídas
que se VENDEM — as outras cinco são decisões tomadas ou por tomar, ver
`venda.FORA`), uma linha por impressão e sítio, com o Trend por cópia e o
estado 📷 da revalidação. Dois totais a duas TAXAS:

  * `feira.taxa_dinheiro` (omissão **0,55**) — o que uma banca costuma pagar em
    dinheiro, em fracção do Trend;
  * `feira.taxa_troca` (omissão **0,70**) — o que dá em crédito de troca.

**As taxas são ESTIMATIVAS dele, não dados**: nenhuma banca publicou nada, e
os números por omissão são um ponto de partida para ele afinar no 8771 depois
da primeira feira. A página di-lo ao lado dos campos.

Cada linha tem uma marca **«levo» / «não levo»** — persistida no CONFIG
(`feira.nao_levo`, uma lista de chaves de impressão), não no browser: ele
decide no PC e leva a decisão no telemóvel. Por omissão leva-se tudo o que
está na venda, e **só as cópias com foto desta campanha** (`feira.so_validadas`,
omissão `true`): *"o que eu for vender também vai com foto"* (revalidação,
2026-09-20). Sem campanha ligada o filtro não corta nada.

TRAZER (o que quero)
--------------------
  (a) **automático** — tudo o que as caixas têm «a comprar» DEPOIS das
      encomendas (`s["missing"][].comprar`, a lista padrão do Cloud incluída),
      por caixa, com o preço mínimo (`m["unit"]`, o mesmo da aba Comprar) e o
      material exigido (`req_compra`/`marca_compra`);
  (b) **manual** — `feira.wantlist`: nome, quantidade, língua/acabamento,
      preço máximo, para que caixa, notas. Uma entrada manual para a MESMA
      carta e a MESMA caixa de uma linha automática **funde-se** nela (não há
      duas linhas para a mesma compra): a quantidade é o máximo das duas, e o
      preço máximo, as notas e os vendors vêm da manual. Uma manual sem caixa
      é uma compra para a colecção e fica na sua linha;
  (c) **vendors** — `feira.vendors` (nome, notas, utilizador Cardmarket, site)
      e, por CARTA, a marca *"o vendor X pode ter"* (`feira.pode_ter`:
      `{nome da carta: [vendor, …]}`). É manual: só ele sabe quem vai estar.

PROJECÇÃO
---------
Total a levar (Trend, dinheiro, troca), total a trazer (mínimo, e o "dele" —
com o preço máximo onde o escreveu), o saldo nas duas taxas, e o mesmo por
caixa. E as duas listas para o telemóvel: «Levar» por COR (como o binder,
com preço e 📷) e «Trazer» por caixa (com material e preço).

Tudo o que aqui se escreve é config (`configio.escrever`); nada toca na base.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from . import loadout, paginas, venda

# As omissões. As taxas são ESTIMATIVAS (ver o cabeçalho): quem as afina é ele.
TAXA_DINHEIRO = 0.55
TAXA_TROCA = 0.70
SO_VALIDADAS = True
LINGUAS = ("pt", "en")
ACABAMENTOS = ("nonfoil", "foil")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def bloco(cfg: dict | None = None) -> dict:
    """O `feira` do config, com as omissões preenchidas (não escreve)."""
    if cfg is None:
        from . import sources                     # noqa: PLC0415
        cfg = sources.config()
    f = dict(cfg.get("feira") or {})
    f.setdefault("taxa_dinheiro", TAXA_DINHEIRO)
    f.setdefault("taxa_troca", TAXA_TROCA)
    f.setdefault("so_validadas", SO_VALIDADAS)
    f.setdefault("nao_levo", [])
    f.setdefault("wantlist", [])
    f.setdefault("vendors", [])
    f.setdefault("pode_ter", {})
    return f


def _taxa(v, nome: str) -> float:
    """Uma taxa é uma fracção entre 0 e 1 (`0.55`), ou uma percentagem (`55`)
    que se converte — é o que uma pessoa escreve num campo. Fora disso é erro."""
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"a {nome} tem de ser um número (ex.: 0.55 ou 55)")
    if x > 1.0:
        x = x / 100.0
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"a {nome} tem de estar entre 0 e 1 (ou 0 e 100 %)")
    return round(x, 4)


def taxas(cfg: dict | None = None) -> tuple[float, float]:
    f = bloco(cfg)
    return _taxa(f["taxa_dinheiro"], "taxa de dinheiro"), _taxa(f["taxa_troca"], "taxa de troca")


def definir_taxas(cfg: dict, dinheiro=None, troca=None) -> dict:
    """Escreve as duas taxas (as que vierem) no config. Devolve o bloco."""
    f = cfg.setdefault("feira", {})
    if dinheiro is not None:
        f["taxa_dinheiro"] = _taxa(dinheiro, "taxa de dinheiro")
    if troca is not None:
        f["taxa_troca"] = _taxa(troca, "taxa de troca")
    return f


def definir_so_validadas(cfg: dict, valor: bool) -> dict:
    f = cfg.setdefault("feira", {})
    f["so_validadas"] = bool(valor)
    return f


# ---------------------------------------------------------------------------
# Levar
# ---------------------------------------------------------------------------
def chave(l: dict) -> str:
    """A identidade de uma IMPRESSÃO na lista de levar: nome, edição, língua e
    acabamento. É por ela que a marca «não levo» se guarda — uma decisão sobre
    a carta que ele tem na mão, não sobre o lote ou a gaveta de onde saiu (a
    `chave_venda` leva o sítio e o motivo, que mudam de um dia para o outro e
    apagavam a marca sem ninguém lhe tocar)."""
    return "|".join([l["nm"], (l.get("set") or "").upper(),
                     (l.get("lang") or "en").lower(),
                     "foil" if l.get("foil") else "nonfoil"])


def marcar(cfg: dict, ch: str, levo: bool) -> list[str]:
    """«levo» / «não levo» de uma impressão. Devolve a lista `nao_levo`."""
    ch = (ch or "").strip()
    if not ch or ch.count("|") != 3:
        raise ValueError("chave inválida — é nome|EDIÇÃO|língua|acabamento")
    f = cfg.setdefault("feira", {})
    lista = [str(x) for x in (f.get("nao_levo") or [])]
    if levo:
        lista = [x for x in lista if x != ch]
    elif ch not in lista:
        lista.append(ch)
    if lista:
        f["nao_levo"] = sorted(lista)
    else:
        f.pop("nao_levo", None)
    return lista


def levar(con, rep: dict, cfg: dict | None = None) -> dict:
    """A moeda de troca: a lista de venda, por impressão e sítio, com a marca,
    o Trend e as duas taxas. Lê as MESMAS linhas por cópia da exportação
    (`venda.linhas_export`) — o estado 📷 e o preço são os da aba Vender, não
    uma segunda conta."""
    from . import revalidacao                     # noqa: PLC0415

    f = bloco(cfg)
    t_din, t_troca = taxas(cfg)
    rev = revalidacao.activa()
    so_v = bool(f["so_validadas"]) and rev
    nao = set(str(x) for x in f["nao_levo"])
    copias = venda.linhas_export(con, rep)
    meta = paginas._meta_cartas(con, sorted({l["nm"] for l in copias}))
    cores = {n: paginas.cor_de(tl, ci) for n, (tl, ci) in meta.items()}
    grupos: dict[tuple, dict] = {}
    for l in copias:
        ch = chave(l)
        k = (ch, l["local"])
        g = grupos.get(k)
        if g is None:
            cor = cores.get(l["nm"], "C")
            g = grupos[k] = {
                "chave": ch, "nm": l["nm"], "set": l["set"],
                "set_name": l.get("set_name") or "", "lang": l["lang"],
                "foil": bool(l["foil"]), "rl": bool(l["rl"]), "local": l["local"],
                "reason": l.get("reason") or "", "saida": l.get("saida") or "venda",
                "cor": cor, "cor_nome": paginas.COR_NOME.get(cor, cor),
                "unit": l.get("unit"), "q": 0, "validadas": 0, "por_revalidar": 0,
                "copias": [], "cond": [],
            }
        g["q"] += l["q"]
        if l.get("validada"):
            g["validadas"] += l["q"]
        else:
            g["por_revalidar"] += l["q"]
        g["copias"].append([l["copy_id"], l["q"]])
        if l.get("cond") and l["cond"] not in g["cond"]:
            g["cond"].append(l["cond"])
    linhas = []
    for g in grupos.values():
        g["levo"] = g["chave"] not in nao
        # Quantas vão: nenhuma se ele disse «não levo»; só as com foto se o
        # filtro está ligado (e a campanha também); senão todas.
        g["leva_q"] = 0 if not g["levo"] else (g["validadas"] if so_v else g["q"])
        # O que o filtro da foto deixa de fora, para se ver que não se perdeu.
        g["fora_foto"] = (g["q"] - g["validadas"]) if (g["levo"] and so_v) else 0
        u = g["unit"] or 0.0
        g["trend"] = round(u * g["leva_q"], 2)
        g["dinheiro"] = round(u * t_din * g["leva_q"], 2)
        g["troca"] = round(u * t_troca * g["leva_q"], 2)
        g["sem_preco"] = g["unit"] is None
        g["cond"] = "/".join(g["cond"])
        linhas.append(g)
    ordem = paginas.COR_ORDEM
    linhas.sort(key=lambda g: (ordem.get(g["cor"], 9), g["nm"], g["set"], g["local"]))
    vao = [g for g in linhas if g["leva_q"]]
    return {
        "linhas": linhas,
        "taxa_dinheiro": t_din, "taxa_troca": t_troca,
        "so_validadas": bool(f["so_validadas"]), "revalidacao": rev,
        "copias": sum(g["leva_q"] for g in vao),
        "trend": round(sum(g["trend"] for g in vao), 2),
        "dinheiro": round(sum(g["dinheiro"] for g in vao), 2),
        "troca": round(sum(g["troca"] for g in vao), 2),
        "rl_copias": sum(g["leva_q"] for g in vao if g["rl"]),
        "rl_trend": round(sum(g["trend"] for g in vao if g["rl"]), 2),
        "sem_preco": sum(g["leva_q"] for g in vao if g["sem_preco"]),
        "nao_levo": sum(g["q"] for g in linhas if not g["levo"]),
        "nao_levo_trend": round(sum((g["unit"] or 0) * g["q"] for g in linhas
                                    if not g["levo"]), 2),
        "fora_foto": sum(g["fora_foto"] for g in linhas),
        "fora_foto_trend": round(sum((g["unit"] or 0) * g["fora_foto"]
                                     for g in linhas), 2),
        "na_venda": sum(g["q"] for g in linhas),
        "na_venda_trend": round(sum((g["unit"] or 0) * g["q"] for g in linhas), 2),
    }


# ---------------------------------------------------------------------------
# Trazer
# ---------------------------------------------------------------------------
def _front(nome: str) -> str:
    return (nome or "").split(" // ")[0].strip()


def _k(nome: str, slot) -> tuple[str, str]:
    return (_front(nome).lower(), slot or "")


def wantlist(cfg: dict | None = None) -> list[dict]:
    """As entradas manuais, normalizadas (sem escrever)."""
    out = []
    for e in bloco(cfg)["wantlist"]:
        if not isinstance(e, dict) or not (e.get("nome") or "").strip():
            continue
        out.append({"nome": _front(e["nome"]), "q": max(1, int(e.get("q") or 1)),
                    "lang": (e.get("lang") or "").lower() or None,
                    "finish": (e.get("finish") or "").lower() or None,
                    "max": (None if e.get("max") in (None, "") else float(e["max"])),
                    "slot": e.get("slot") or None, "notas": e.get("notas") or ""})
    return out


def wantlist_add(cfg: dict, nome: str, q: int = 1, lang: str | None = None,
                 finish: str | None = None, maximo=None, slot: str | None = None,
                 notas: str = "") -> dict:
    """Mete (ou substitui) uma entrada manual, por (carta, caixa). Devolve-a.

    Substitui em vez de somar: uma wantlist é o que ele QUER, não um saco de
    pedidos; escrever «2 Brainstorm» duas vezes quer dizer 2, não 4.
    """
    nome = _front(nome)
    if not nome:
        raise ValueError("sem nome de carta")
    try:
        q = int(q) if q not in (None, "") else 1
    except (TypeError, ValueError):
        raise ValueError("a quantidade tem de ser um número inteiro")
    if q <= 0:
        raise ValueError("quantidade tem de ser 1 ou mais")
    lang = (lang or "").lower() or None
    if lang and lang not in LINGUAS:
        raise ValueError(f"língua {lang!r} — usa pt ou en")
    finish = (finish or "").lower() or None
    if finish and finish not in ACABAMENTOS:
        raise ValueError(f"acabamento {finish!r} — usa foil ou nonfoil")
    if maximo not in (None, ""):
        try:
            maximo = round(float(str(maximo).replace(",", ".")), 2)
        except ValueError:
            raise ValueError("o preço máximo tem de ser um número (ex.: 3.50)")
        if maximo < 0:
            raise ValueError("o preço máximo não pode ser negativo")
    else:
        maximo = None
    if slot:
        from . import caixas                      # noqa: PLC0415
        caixas.caixa_do_cfg(cfg, slot)            # KeyError se não existe
    ent = {"nome": nome, "q": q}
    if lang:
        ent["lang"] = lang
    if finish:
        ent["finish"] = finish
    if maximo is not None:
        ent["max"] = maximo
    if slot:
        ent["slot"] = slot
    if (notas or "").strip():
        ent["notas"] = notas.strip()
    f = cfg.setdefault("feira", {})
    lista = [e for e in (f.get("wantlist") or [])
             if isinstance(e, dict) and _k(e.get("nome", ""), e.get("slot")) != _k(nome, slot)]
    lista.append(ent)
    f["wantlist"] = sorted(lista, key=lambda e: (e.get("slot") or "", e["nome"].lower()))
    return ent


def wantlist_remover(cfg: dict, nome: str, slot: str | None = None) -> int:
    """Tira a entrada (carta, caixa). Devolve quantas ficaram."""
    f = cfg.setdefault("feira", {})
    lista = [e for e in (f.get("wantlist") or []) if isinstance(e, dict)]
    novo = [e for e in lista if _k(e.get("nome", ""), e.get("slot")) != _k(nome, slot)]
    if len(novo) == len(lista):
        raise ValueError(f"{nome!r}" + (f" para {slot!r}" if slot else "")
                         + " não está na wantlist da feira")
    if novo:
        f["wantlist"] = novo
    else:
        f.pop("wantlist", None)
    return len(novo)


def vendors(cfg: dict | None = None) -> list[dict]:
    out = []
    for v in bloco(cfg)["vendors"]:
        if isinstance(v, dict) and (v.get("nome") or "").strip():
            out.append({"nome": v["nome"].strip(), "notas": v.get("notas") or "",
                        "cardmarket": v.get("cardmarket") or "", "site": v.get("site") or ""})
        elif isinstance(v, str) and v.strip():
            out.append({"nome": v.strip(), "notas": "", "cardmarket": "", "site": ""})
    return out


def vendor_add(cfg: dict, nome: str, notas: str = "", cardmarket: str = "",
               site: str = "") -> dict:
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("sem nome de vendor")
    v = {"nome": nome}
    for k, val in (("notas", notas), ("cardmarket", cardmarket), ("site", site)):
        if (val or "").strip():
            v[k] = val.strip()
    f = cfg.setdefault("feira", {})
    lista = [x for x in (f.get("vendors") or [])
             if (x.get("nome") if isinstance(x, dict) else x).strip().lower() != nome.lower()]
    lista.append(v)
    f["vendors"] = sorted(lista, key=lambda x: x["nome"].lower())
    return v


def vendor_remover(cfg: dict, nome: str) -> int:
    f = cfg.setdefault("feira", {})
    lista = list(f.get("vendors") or [])
    novo = [x for x in lista
            if (x.get("nome") if isinstance(x, dict) else x).strip().lower() != (nome or "").lower()]
    if len(novo) == len(lista):
        raise ValueError(f"{nome!r} não está nos vendors")
    if novo:
        f["vendors"] = novo
    else:
        f.pop("vendors", None)
    # As marcas «pode ter» desse vendor vão com ele.
    pt = f.get("pode_ter") or {}
    for carta in list(pt):
        pt[carta] = [v for v in pt[carta] if v.lower() != (nome or "").lower()]
        if not pt[carta]:
            pt.pop(carta)
    if not pt:
        f.pop("pode_ter", None)
    return len(novo)


def pode_ter(cfg: dict, carta: str, vendor: str, sim: bool = True) -> list[str]:
    """«O vendor X pode ter esta carta» — por CARTA (vale para a linha
    automática e para a manual). Devolve os vendors dessa carta."""
    carta, vendor = _front(carta), (vendor or "").strip()
    if not carta or not vendor:
        raise ValueError("preciso da carta e do vendor")
    if vendor.lower() not in {v["nome"].lower() for v in vendors(cfg)}:
        raise ValueError(f"{vendor!r} não está nos vendors — acrescenta-o primeiro")
    f = cfg.setdefault("feira", {})
    pt = f.setdefault("pode_ter", {})
    # A chave é o nome como está escrito nas listas; procura-se sem maiúsculas.
    chave_c = next((c for c in pt if c.lower() == carta.lower()), carta)
    lista = [v for v in (pt.get(chave_c) or []) if v.lower() != vendor.lower()]
    if sim:
        lista.append(vendor)
    if lista:
        pt[chave_c] = sorted(lista, key=str.lower)
    else:
        pt.pop(chave_c, None)
    if not pt:
        f.pop("pode_ter", None)
    return lista


def _vendors_de(f: dict) -> dict[str, list[str]]:
    return {c.lower(): [str(v) for v in vs] for c, vs in (f.get("pode_ter") or {}).items()
            if isinstance(vs, list)}


def trazer(con, rep: dict, cfg: dict | None = None) -> dict:
    """O que quer trazer: as compras das caixas (depois das encomendas) mais a
    wantlist manual, fundidas por (carta, caixa)."""
    f = bloco(cfg)
    nomes = loadout.nomes_das_caixas()
    pt = _vendors_de(f)
    linhas: dict[tuple, dict] = {}
    for s in rep["slots"]:
        for m in s["missing"]:
            if not m.get("comprar"):
                continue
            k = _k(m["nm"], s["slot"])
            g = linhas.get(k)
            if g is None:
                g = linhas[k] = {
                    "nm": m["nm"], "slot": s["slot"], "caixa": s["nome"], "q": 0,
                    "unit": m.get("unit"), "req": m.get("req_compra") or loadout.requisito_material(s),
                    "mat": m.get("marca_compra") or loadout.marca_wantlist(s),
                    "origem": "caixa", "max": None, "notas": "", "manual_q": 0,
                    "acam": 0, "pfoto": 0, "sfoil": not m.get("foil_existe", True),
                    "nota": loadout.nota_onde(m) or "",
                }
            # Main + side da mesma caixa somam: estão na mesa ao mesmo tempo.
            g["q"] += int(m["comprar"])
            g["acam"] += int(m.get("a_caminho", 0) or 0)
            g["pfoto"] += int(m.get("pendente_foto", 0) or 0)
            if m.get("unit") and (g["unit"] is None or m["unit"] > g["unit"]):
                g["unit"] = m["unit"]
    for e in wantlist(cfg):
        k = _k(e["nome"], e["slot"])
        g = linhas.get(k)
        if g is not None:
            # A MESMA compra: uma linha, com o que a manual acrescenta.
            g["origem"] = "caixa+manual"
            g["manual_q"] = e["q"]
            g["q"] = max(g["q"], e["q"])
            g["max"] = e["max"]
            g["notas"] = e["notas"]
            continue
        s = None
        if e["slot"]:
            s = next((x for x in rep["slots"] if x["slot"] == e["slot"]), None)
        finish, lang = e["finish"], e["lang"]
        if s is not None:
            fin_c, lang_c = loadout.material_da_caixa(s)
            finish, lang = finish or fin_c, lang or lang_c
        unit, _pf = loadout.card_price(con, e["nome"], finish or "nonfoil")
        mat = " ".join(x for x in ((lang or "").upper(), finish or "") if x)
        linhas[k] = {
            "nm": e["nome"], "slot": e["slot"],
            "caixa": nomes.get(e["slot"], e["slot"]) if e["slot"] else "Colecção",
            "q": e["q"], "unit": unit,
            "req": (loadout.requisito_material(s) if s is not None else mat),
            "mat": mat, "origem": "manual", "max": e["max"], "notas": e["notas"],
            "manual_q": e["q"], "acam": 0, "pfoto": 0, "sfoil": False, "nota": "",
        }
    out = []
    for g in linhas.values():
        u = g["unit"] or 0.0
        g["minimo"] = round(u * g["q"], 2)
        # O "dele": o preço máximo que escreveu, senão o mínimo de hoje.
        g["maximo"] = round((g["max"] if g["max"] is not None else u) * g["q"], 2)
        g["sem_preco"] = g["unit"] is None
        g["cara"] = bool(g["unit"] and g["unit"] >= 100)
        g["vendors"] = pt.get(g["nm"].lower(), [])
        out.append(g)
    # Pela ordem das caixas (a da alocação), depois a colecção; nome dentro.
    ordem = {s["slot"]: i for i, s in enumerate(rep["slots"])}
    out.sort(key=lambda g: (ordem.get(g["slot"], 999), g["nm"]))
    por_caixa: dict[str, dict] = {}
    for g in out:
        c = por_caixa.setdefault(g["slot"] or "", {
            "slot": g["slot"], "caixa": g["caixa"], "copias": 0, "minimo": 0.0,
            "maximo": 0.0, "sem_preco": 0, "linhas": []})
        c["copias"] += g["q"]
        c["minimo"] = round(c["minimo"] + g["minimo"], 2)
        c["maximo"] = round(c["maximo"] + g["maximo"], 2)
        c["sem_preco"] += g["q"] if g["sem_preco"] else 0
        c["linhas"].append(g)
    return {
        "linhas": out, "por_caixa": list(por_caixa.values()),
        "copias": sum(g["q"] for g in out),
        "minimo": round(sum(g["minimo"] for g in out), 2),
        "maximo": round(sum(g["maximo"] for g in out), 2),
        "com_maximo": sum(1 for g in out if g["max"] is not None),
        "sem_preco": sum(g["q"] for g in out if g["sem_preco"]),
        "manuais": sum(1 for g in out if g["origem"] != "caixa"),
        "vendors": vendors(cfg),
    }


# ---------------------------------------------------------------------------
# A projecção
# ---------------------------------------------------------------------------
def projeccao(con, rep: dict, cfg: dict | None = None, hoje: str | None = None) -> dict:
    """Tudo junto: levar, trazer, o saldo nas duas taxas, e os textos."""
    hoje = hoje or date.today().isoformat()
    lv = levar(con, rep, cfg)
    tz = trazer(con, rep, cfg)
    saldo = {
        "dinheiro": round(lv["dinheiro"] - tz["minimo"], 2),
        "troca": round(lv["troca"] - tz["minimo"], 2),
        "dinheiro_max": round(lv["dinheiro"] - tz["maximo"], 2),
        "troca_max": round(lv["troca"] - tz["maximo"], 2),
        "trend": round(lv["trend"] - tz["minimo"], 2),
    }
    # Por caixa: o que a caixa custa a trazer, e a fatia da moeda de troca que
    # isso é (em troca, que é o que uma banca dá numa feira).
    por_caixa = []
    for c in tz["por_caixa"]:
        por_caixa.append(dict({k: v for k, v in c.items() if k != "linhas"},
                              saldo_troca=round(lv["troca"] - c["minimo"], 2),
                              saldo_dinheiro=round(lv["dinheiro"] - c["minimo"], 2),
                              pct_da_troca=(round(100 * c["minimo"] / lv["troca"], 1)
                                            if lv["troca"] else None)))
    p = {"hoje": hoje, "levar": lv, "trazer": tz, "saldo": saldo,
         "por_caixa": por_caixa, "vendors": tz["vendors"],
         "taxa_dinheiro": lv["taxa_dinheiro"], "taxa_troca": lv["taxa_troca"]}
    p["texto_levar"] = texto_levar(p)
    p["texto_trazer"] = texto_trazer(p)
    p["texto_cardmarket"] = texto_cardmarket(p)
    return p


def _eur(v) -> str:
    return "?" if v in (None, "") else f"{v:.2f} €"


def _cop(n: int) -> str:
    return f"{n} cópia" + ("" if n == 1 else "s")


def texto_levar(p: dict) -> str:
    """«Levar» para o telemóvel: por cor, uma linha por impressão/sítio, com
    o Trend por cópia, o sítio e o 📷. Só o que VAI (`leva_q`)."""
    lv = p["levar"]
    out = [f"FEIRA — LEVAR ({p['hoje']})",
           f"{_cop(lv['copias'])} · Trend {_eur(lv['trend'])} · dinheiro ~{_eur(lv['dinheiro'])}"
           f" ({lv['taxa_dinheiro']:.0%}) · troca ~{_eur(lv['troca'])} ({lv['taxa_troca']:.0%})"
           + (f" · RL: {lv['rl_copias']} / {_eur(lv['rl_trend'])} — confirmar uma a uma"
              if lv["rl_copias"] else "")]
    if lv["fora_foto"]:
        out.append(f"(fora por não terem foto desta campanha: {_cop(lv['fora_foto'])} · "
                   f"{_eur(lv['fora_foto_trend'])})")
    if lv["nao_levo"]:
        out.append(f"(marcadas «não levo»: {_cop(lv['nao_levo'])} · {_eur(lv['nao_levo_trend'])})")
    out.append("")
    cor = None
    for l in lv["linhas"]:
        if not l["leva_q"]:
            continue
        if l["cor"] != cor:
            cor = l["cor"]
            out.append(f"■ {l['cor_nome']}")
        out.append(f"  {l['leva_q']}× {l['nm']}" + (" (RL)" if l["rl"] else "")
                   + f" · {l['set']} {l['lang'].upper()} {'foil' if l['foil'] else 'nonfoil'}"
                   + (f" {l['cond']}" if l["cond"] else "")
                   + f" · {_eur(l['unit'])}/un · {l['local']}"
                   + ("" if not lv["revalidacao"] else
                      (" · ✓ foto" if l["validadas"] >= l["leva_q"] else " · 📷 por revalidar")))
    return "\n".join(out).rstrip() + "\n"


def texto_trazer(p: dict) -> str:
    """«Trazer» para o telemóvel: por caixa, com o material, o preço mínimo e
    o máximo dele, os vendors que podem ter, e as notas."""
    tz = p["trazer"]
    out = [f"FEIRA — TRAZER ({p['hoje']})",
           f"{_cop(tz['copias'])} · mínimo {_eur(tz['minimo'])}"
           + (f" · com os teus máximos {_eur(tz['maximo'])}" if tz["com_maximo"] else "")
           + (f" · {tz['sem_preco']} sem preço" if tz["sem_preco"] else ""), ""]
    for c in tz["por_caixa"]:
        out.append(f"■ {c['caixa']} — {_cop(c['copias'])} · {_eur(c['minimo'])}")
        for l in c["linhas"]:
            out.append(f"  {l['q']}× {l['nm']}" + (f" [{l['mat']}]" if l["mat"] else "")
                       + f" · {_eur(l['unit'])}/un"
                       + (f" · máx {_eur(l['max'])}" if l["max"] is not None else "")
                       + (" · CARA" if l["cara"] else "")
                       + (f" · {', '.join(l['vendors'])} pode ter" if l["vendors"] else "")
                       + (f" · {l['notas']}" if l["notas"] else "")
                       + (f" · {l['nota']}" if l["nota"] else ""))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def texto_cardmarket(p: dict) -> str:
    """A wantlist inteira em `N Nome`, para colar no Cardmarket (só o que se
    compra; `// caixa` entre blocos, que o site ignora)."""
    out = []
    for c in p["trazer"]["por_caixa"]:
        out.append(f"// {c['caixa']}")
        out.extend(f"{l['q']} {l['nm']}" for l in c["linhas"])
    return "\n".join(out)


def resumo(p: dict) -> str:
    """Uma linha, para a CLI e para o relatório."""
    lv, tz, s = p["levar"], p["trazer"], p["saldo"]
    return (f"levar {lv['copias']}c / Trend {lv['trend']:.2f} € "
            f"(dinheiro {lv['dinheiro']:.2f} € @ {lv['taxa_dinheiro']:.0%} · "
            f"troca {lv['troca']:.2f} € @ {lv['taxa_troca']:.0%}) · "
            f"trazer {tz['copias']}c / {tz['minimo']:.2f} €"
            + (f" (máx {tz['maximo']:.2f} €)" if tz["com_maximo"] else "")
            + f" · saldo dinheiro {s['dinheiro']:+.2f} € · troca {s['troca']:+.2f} €")
