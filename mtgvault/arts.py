"""AS ARTS QUE ELE PROCURA: qual é a IMPRESSÃO de uma carta que ele quer comprar.

André, 2026-10-13, à letra: *"as wantlists sao validas quando ja sabes as arts
que procuro, pede-me sempre que faltar as arts das cartas, se for de uma carta
que eu ja tenho, a Art tem que ser a mesma e ai nao me pedes qual e a Art,
assumes como a que eu ja tenho"*.

A PERGUNTA VIVE NUM SÍTIO SÓ (`preferida`), e a resposta tem cinco caras — a
ordem é a da regra dele, e é a ordem por que se pergunta:

1. **`basica`** — Forest, Island, Plains, Swamp, Mountain (e as Snow-Covered e o
   Wastes, a `loadout.BASICS` de sempre). Nunca se pede a art: são a pilha de
   Unhinged (02/10) e não se compram por art.
2. **`escolhida`** — ele pôs a imagem em `Arts que procuro/<carta>/` e a
   impressão (edição + número) ficou registada em `colecao_config.json →
   arts_procuradas`. Ganha a tudo, incluindo à que ele tem: é a afirmação mais
   explícita que ele pode fazer sobre a carta.
3. **`a_que_tens`** — ele TEM a carta numa impressão só: é essa, e não se lhe
   pergunta nada (*"assumes como a que eu ja tenho"*).
4. **`ambigua`** — ele tem a carta em DUAS ou mais impressões (edição + número
   diferentes). Não dá para assumir, e pergunta-se qual — com as que ele tem à
   frente, para a resposta ser um toque.
5. **`por_escolher`** — ele não tem nenhuma. É ESTA a lista que se lhe pede.

PORQUE É QUE A IMAGEM NÃO É A FONTE DOS NÚMEROS, E O CONFIG É
--------------------------------------------------------------
A imagem é o gesto dele; o que a página precisa é a IMPRESSÃO. Quem lê a imagem
e diz «é a MH2 #197» é o Claude (como na leitura das fotos das cartas), e o que
ele diz fica gravado no config — que vai no Git. Ler a pasta em tempo de página
punha o site do PC e o do GitHub a dizer coisas diferentes (as imagens não estão
no Git), e o `publicar` a commitar a diferença de meia em meia hora. A pasta
serve para o CLI dizer o que está À ESPERA de ser identificado
(`por_identificar`), e um ficheiro cujo NOME já diz a impressão (`MH2 197.jpg`)
regista-se com um comando, sem ninguém ter de olhar para ele (`ler_pasta`).

A pasta é irmã de `Colocar fotos da coleção aqui`, NUNCA filha: lá dentro o
`recolher_das_pastas` varre com `rglob` e uma art virava uma cópia fantasma na
colecção (ver o `LEIA-ME.txt` da pasta).
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from . import collection, configio, loadout, scryfall, sources

CHAVE = "arts_procuradas"
PASTA_NOME = "Arts que procuro"
IMAGENS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".gif"}

ORIGENS = ("basica", "escolhida", "a_que_tens", "ambigua", "por_escolher")

# A frase de cada origem, num sítio só — a lista de faltas e o CLI dizem o mesmo.
TEXTO = {
    "escolhida": "a impressão que escolheste (Arts que procuro)",
    "a_que_tens": "a impressão que já tens",
    "regra": "regra genérica: a mais barata que serve esta caixa",
    "ambigua": "tens esta carta em mais do que uma impressão — diz qual queres",
    "por_escolher": "ainda não disseste que art queres",
    "basica": "básica: não se pede art",
}


def pasta(raiz: Path | str | None = None) -> Path:
    """`Arts que procuro/`, na raiz do repositório (ao lado do config)."""
    if raiz:
        return Path(raiz)
    return configio.caminho().parent / PASTA_NOME


def e_basica(nome: str) -> bool:
    return scryfall.chave(nome) in loadout.BASICS


# ---------------------------------------------------------------------------
# O registo (colecao_config.json -> arts_procuradas)
# ---------------------------------------------------------------------------
def registadas(cfg: dict | None = None) -> dict[str, dict]:
    """`nome (a frente) -> {set, num, em, imagem}` — o que ele já escolheu."""
    cfg = sources.config() if cfg is None else cfg
    v = cfg.get(CHAVE)
    out: dict[str, dict] = {}
    for nome, e in (v.items() if isinstance(v, dict) else []):
        if str(nome).startswith("_") or not isinstance(e, dict):
            continue
        s, n = str(e.get("set") or "").strip().lower(), str(e.get("num") or "").strip()
        if s and n:
            out[scryfall.chave(str(nome))] = {**e, "set": s, "num": n}
    return out


def impressao(con, nome: str, set_code: str, num: str) -> dict | None:
    """A impressão (set, número) DESTA carta no catálogo, ou `None`.

    Confere o NOME: uma edição e um número que sejam de outra carta não passam —
    era trocar a art de uma carta pelo preço de outra, sem erro nenhum."""
    r = con.execute(
        f"""SELECT scryfall_id, name, set_code, collector_number, finishes
              FROM cards WHERE lower(set_code) = ? AND collector_number = ?
               AND {scryfall.sql_nome('name')}""",
        (set_code.lower(), str(num), *scryfall.params_nome(nome))).fetchone()
    if not r:
        return None
    return {"sid": r["scryfall_id"], "nome": r["name"], "set": r["set_code"],
            "num": r["collector_number"], "finishes": r["finishes"] or ""}


def registar(con, nome: str, set_code: str, num: str, *, imagem: str = "",
             hoje: str | None = None, path=None) -> dict:
    """Grava a impressão que ele quer desta carta. Valida no catálogo ANTES de
    escrever (um `ValueError` com o motivo em português), e escreve com o
    `configio.escrever` — nunca com `json.dump(indent=2)` (o commit `ac1f776`)."""
    imp = impressao(con, nome, set_code, num)
    if not imp:
        raise ValueError(f"{nome}: não há impressão {set_code.upper()} #{num} desta "
                         "carta no catálogo — confere a edição e o número")
    if e_basica(nome):
        raise ValueError(f"{nome} é uma básica: não se pede art de básicas")
    cfg = configio.ler(path)
    bloco = cfg.get(CHAVE) if isinstance(cfg.get(CHAVE), dict) else {}
    chave = scryfall.chave(imp["nome"])
    bloco[chave] = {"set": imp["set"], "num": imp["num"],
                    "em": hoje or date.today().isoformat(),
                    **({"imagem": imagem} if imagem else {})}
    cfg[CHAVE] = bloco
    configio.escrever(cfg, path)
    return {"carta": chave, **bloco[chave]}


def esquecer(nome: str, *, path=None) -> bool:
    """Tira a escolha (a carta volta à regra de quem a tem / por escolher)."""
    cfg = configio.ler(path)
    bloco = cfg.get(CHAVE) if isinstance(cfg.get(CHAVE), dict) else {}
    chave = scryfall.chave(nome)
    if chave not in bloco:
        return False
    del bloco[chave]
    cfg[CHAVE] = bloco
    configio.escrever(cfg, path)
    return True


# ---------------------------------------------------------------------------
# A pasta (só para o CLI — ver o docstring do módulo)
# ---------------------------------------------------------------------------
_NOME_IMPRESSAO = re.compile(r"^\s*([A-Za-z0-9]{2,6})[\s_#-]+([0-9]+[a-z★]?)\b",
                             re.IGNORECASE)


def imagens_na_pasta(raiz=None) -> dict[str, list[Path]]:
    """`pasta da carta -> [imagens]` — uma pasta por carta, como o LEIA-ME diz."""
    p = pasta(raiz)
    out: dict[str, list[Path]] = {}
    if not p.is_dir():
        return out
    for d in sorted(x for x in p.iterdir() if x.is_dir() and not x.name.startswith("_")):
        imgs = sorted(f for f in d.iterdir()
                      if f.is_file() and f.suffix.lower() in IMAGENS)
        if imgs:
            out[d.name] = imgs
    return out


def por_identificar(raiz=None, cfg: dict | None = None) -> list[dict]:
    """As cartas com imagem na pasta e SEM impressão registada — o que está à
    espera de alguém olhar para a imagem e dizer a edição e o número."""
    reg = registadas(cfg)
    return [{"carta": nome, "imagens": [i.name for i in imgs]}
            for nome, imgs in imagens_na_pasta(raiz).items()
            if scryfall.chave(nome) not in reg]


def ler_pasta(con, raiz=None, *, path=None, hoje: str | None = None) -> dict:
    """Regista as imagens cujo NOME DO FICHEIRO já diz a impressão (`MH2 197.jpg`,
    `som-179.png`), conferidas no catálogo. As outras ficam por identificar —
    nunca se adivinha uma edição a partir de uma imagem sem a ler."""
    feitas, ficam = [], []
    for item in por_identificar(raiz, configio.ler(path)):
        achou = None
        for nome_img in item["imagens"]:
            m = _NOME_IMPRESSAO.match(Path(nome_img).stem)
            if m and impressao(con, item["carta"], m.group(1), m.group(2)):
                achou = (m.group(1), m.group(2), nome_img)
                break
        if achou:
            feitas.append(registar(con, item["carta"], achou[0], achou[1],
                                   imagem=f"{item['carta']}/{achou[2]}",
                                   hoje=hoje, path=path))
        else:
            ficam.append(item)
    return {"registadas": feitas, "por_identificar": ficam}


# ---------------------------------------------------------------------------
# O que ele tem (as impressões das cópias dele)
# ---------------------------------------------------------------------------
def impressoes_que_tens(con) -> dict[str, list[dict]]:
    """`nome (a frente) -> [{sid, set, num, q, linguas, acabamentos}]`, uma linha
    por IMPRESSÃO (edição + número). Língua e acabamento não fazem duas
    impressões: a art é a mesma, e é da art que ele está a falar."""
    por: dict[str, dict[tuple, dict]] = {}
    for r in con.execute(
            f"""SELECT c.name nm, c.set_code s, c.collector_number n,
                       min(c.scryfall_id) sid, sum(cp.quantity) q,
                       group_concat(DISTINCT cp.language) li,
                       group_concat(DISTINCT cp.finish) fi
                  FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                 WHERE {collection.jogaveis('cp')}
                 GROUP BY c.name, c.set_code, c.collector_number"""):
        nm = scryfall.chave(r["nm"])
        por.setdefault(nm, {})[(r["s"], r["n"])] = {
            "sid": r["sid"], "set": r["s"], "num": r["n"], "q": int(r["q"] or 0),
            "linguas": sorted(set((r["li"] or "").split(",")) - {""}),
            "acabamentos": sorted(set((r["fi"] or "").split(",")) - {""})}
    return {nm: sorted(v.values(), key=lambda x: (-x["q"], x["set"], x["num"]))
            for nm, v in por.items()}


def preferida(con, nome: str, cache: dict | None = None,
              cfg: dict | None = None) -> dict:
    """A impressão que ele quer desta carta, e PORQUÊ — a regra toda, num sítio só.

    `{origem, sid, set, num, opcoes}`; `opcoes` são as impressões que ele tem
    (é o que se lhe põe à frente numa `ambigua`). `cache` partilha a leitura das
    cópias e do registo entre as linhas de uma página."""
    cache = {} if cache is None else cache
    nm = scryfall.chave(nome)
    if e_basica(nm):
        return {"origem": "basica", "sid": None, "set": None, "num": None, "opcoes": []}
    if "arts:reg" not in cache:
        cache["arts:reg"] = registadas(cfg)
    if "arts:tens" not in cache:
        cache["arts:tens"] = impressoes_que_tens(con)
    tens = cache["arts:tens"].get(nm) or []
    reg = cache["arts:reg"].get(nm)
    if reg:
        k = ("arts:imp", nm, reg["set"], reg["num"])
        if k not in cache:
            cache[k] = impressao(con, nm, reg["set"], reg["num"])
        imp = cache[k]
        if imp:
            return {"origem": "escolhida", "sid": imp["sid"], "set": imp["set"],
                    "num": imp["num"], "opcoes": tens}
        # Um registo que já não bate no catálogo não se usa calado: cai na regra
        # de quem a tem, e o `registo_invalido` diz porquê.
        out = preferida(con, nm, cache={**cache, "arts:reg": {}}, cfg=cfg)
        out["registo_invalido"] = f"{reg['set'].upper()} #{reg['num']}"
        return out
    if len(tens) == 1:
        t = tens[0]
        return {"origem": "a_que_tens", "sid": t["sid"], "set": t["set"],
                "num": t["num"], "opcoes": tens}
    if len(tens) > 1:
        return {"origem": "ambigua", "sid": None, "set": None, "num": None,
                "opcoes": tens}
    return {"origem": "por_escolher", "sid": None, "set": None, "num": None,
            "opcoes": []}


def mapa(con, cache: dict) -> dict:
    """O mapa de preços por impressão (o MESMO da conta única do valor), uma vez
    por página."""
    if "arts:mapa" not in cache:
        cache["arts:mapa"] = collection.mapa_precos(con)
    return cache["arts:mapa"]


def preco(con, pref: dict, finish: str | None, cache: dict) -> float | None:
    """O preço da impressão preferida, no acabamento EXACTO pedido — ou `None`.

    Exacto de propósito (a regra das linhas de venda de 2026-10-06): o preço do
    foil não é o preço do nonfoil daquela art, e um preço de outro acabamento
    calado era o defeito das «duas verdades»."""
    if not pref.get("sid"):
        return None
    d = collection.preco_impressao_detalhe(mapa(con, cache), pref["sid"],
                                           finish or "nonfoil", exacto=True)
    return d["preco"]


# ---------------------------------------------------------------------------
# A LISTA para o site: os nomes que os decks pedem, e a art de cada um
# ---------------------------------------------------------------------------
def decks_que_ficam(con, cfg: dict | None = None) -> list[dict]:
    """Os decks que ele GUARDA: as caixas, os decks dele e as versões com lista —
    menos os que saíram da escolha e as caixas desactivadas. O meta não entra
    (é consulta, e ninguém compra a art de um deck que não escolheu)."""
    from . import decks_vista, versoes                          # noqa: PLC0415
    cfg = sources.config() if cfg is None else cfg
    ds = (decks_vista.decks_das_caixas(con, cfg)
          + decks_vista.decks_de_evento(con, cfg)
          + decks_vista.decks_de_versoes(con, cfg))
    vistos, out = set(), []
    for d in ds:
        # Uma versão que saiu leva a marca no próprio deck (`saiu`); um deck dele
        # leva-a no config (`versoes.saiu`). As duas contam.
        if (d["id"] in vistos or d.get("desactivada") or d.get("saiu")
                or versoes.saiu(d["id"], cfg)):
            continue
        vistos.add(d["id"])
        out.append(d)
    return out


def relatorio(con, cfg: dict | None = None, cache: dict | None = None,
              a_comprar: set[str] | None = None) -> dict:
    """`{contagens, por_escolher, ambiguas, escolhidas}` — o que a página mostra.

    Os nomes são os que os decks que ele guarda pedem (`decks_que_ficam`), e a
    necessidade de cada um é o MÁXIMO entre decks (é por nome que se escolhe
    uma art, não por cópia). A posse é a da colecção inteira
    (`paginas.posse_total`): «tem algumas» quer dizer que a art se decide
    sozinha — é a dele.

    **A AMBIGUIDADE SÓ SE PERGUNTA ONDE HÁ COMPRA.** Medido a 2026-10-13: ele tem
    53 cartas destes decks em duas ou mais impressões (as fetchlands em EXP e
    ONS, a Cavern em três), e a 33 delas não falta nada — não se compra, logo a
    art não se escolhe. Pergunta-se quando falta na colecção inteira
    (`tem < precisa`: eram 3, Brain Freeze, Dark Ritual e Force of Will) **ou**
    quando a carta está na lista de compras de uma caixa (`a_comprar`, as linhas
    da faltas.html): cada caixa compra as suas (regra de 19/09), e uma Mox Opal
    que ele tem seis vezes falta na mesma às duas caixas de Legacy — mais 17."""
    from . import paginas                                       # noqa: PLC0415
    cfg = sources.config() if cfg is None else cfg
    cache = {} if cache is None else cache
    posse = paginas.posse_total(con)
    precisa: dict[str, int] = {}
    decks_de: dict[str, list[str]] = {}
    for d in decks_que_ficam(con, cfg):
        por: dict[str, int] = {}
        for _b, nm, q in d.get("cards") or []:
            k = scryfall.chave(nm)
            por[k] = por.get(k, 0) + int(q)
        for k, q in por.items():
            precisa[k] = max(precisa.get(k, 0), q)
            decks_de.setdefault(k, []).append(d["nome"])
    cont = {"nomes": 0, "basicas": 0, "completos": 0, "alguns": 0, "zero": 0,
            "escolhidas": 0, "por_escolher": 0, "ambiguas": 0,
            "ambiguas_sem_compra": 0, "decks": 0}
    cont["decks"] = len(decks_que_ficam(con, cfg))
    por_escolher, ambiguas, escolhidas = [], [], []
    for nm in sorted(precisa):
        if e_basica(nm):
            cont["basicas"] += 1
            continue
        cont["nomes"] += 1
        tem = int(posse.get(nm) or 0)
        cont["completos" if tem >= precisa[nm] else ("alguns" if tem else "zero")] += 1
        pref = preferida(con, nm, cache, cfg)
        linha = {"nm": nm, "q": precisa[nm], "tem": tem,
                 "decks": sorted(set(decks_de.get(nm) or []))}
        if pref["origem"] == "escolhida":
            cont["escolhidas"] += 1
            escolhidas.append({**linha, "set": pref["set"], "num": pref["num"],
                               "sid": pref["sid"]})
        elif pref["origem"] == "ambigua":
            if tem >= precisa[nm] and nm not in (a_comprar or set()):
                cont["ambiguas_sem_compra"] += 1
                continue
            cont["ambiguas"] += 1
            ambiguas.append({**linha, "opcoes": [
                {k: o[k] for k in ("set", "num", "q", "sid", "linguas", "acabamentos")}
                for o in pref["opcoes"]]})
        elif pref["origem"] == "por_escolher":
            cont["por_escolher"] += 1
            unit, _fin = loadout.card_price(con, nm, "nonfoil")
            sid = loadout.impressao_mais_barata(con, nm, "nonfoil", cache=cache)
            por_escolher.append({**linha, "unit": unit, "sid": sid,
                                 "valor": round((unit or 0) * precisa[nm], 2)})
    # POR VALOR, que é por onde ele começa: a art de uma carta de 150 € importa
    # mais do que a de trinta de 0,30 €. Sem preço vai para o fim, e diz-se.
    por_escolher.sort(key=lambda x: (x["unit"] is None, -x["valor"], x["nm"]))
    return {"contagens": cont, "por_escolher": por_escolher,
            "ambiguas": ambiguas, "escolhidas": escolhidas,
            "texto": TEXTO}
