"""A VIGIA DE CARTAS: avisar no dia em que uma carta aparece numa decklist.

André, 2026-09-26, à letra: ele comprou **4× «Kasmina, Enigma Sage»** e **2×
«Enter the Infinite»** por causa de um combo novo e quer saber quando aparecerem
decklists com esse combo — *"vai conferindo"*. A segunda peça é **«Jace's
Machinations»**, do *Reality Fracture*, que só sai a **02/10/2026**: hoje não
pode existir uma única lista de torneio com o combo, e é precisamente por isso
que isto existe. O valor não está em responder hoje — está em ele ser avisado no
dia em que a primeira aparecer, sem ter de pedir a ninguém.

Isto vive no mtgvault porque é aqui que as listas já entram: o `daily` recolhe
todas as noites (na base de 2026-09-26, **7 970** listas no último mês, **2 279**
de Modern). Uma vigia noutro sítio era uma segunda recolha.

O FILTRO DE TIER TINHA DE SER ABERTO — E SÓ PARA AS CARTAS VIGIADAS
-------------------------------------------------------------------
É a parte que, sem ela, estragava tudo em silêncio. A regra dele de 2026-09-07
(*"não quero listas de league; quero challenge, showcase, e presenciais com 64 ou
mais jogadores"*) está certa para o **metagame** — e é exactamente ao contrário
do que serve aqui: **a primeira aparição de um combo novo é um 5-0 de league ou
um torneio de 20 pessoas**. Com o filtro ligado, a lista que ele quer ver era
recusada à entrada (`sources.store_decklist` devolve `None` a uma liga) e, se
tivesse escapado, o `analysis.prune_leagues` apagava-a na mesma corrida. O aviso
nunca chegava e **nenhum passo dava erro** — o padrão do `event_tier`, sobre a
única pergunta que ele fez.

Por isso há três portas abertas, e **só** para as listas que TÊM uma carta
vigiada:
  1. `sources.harvest_mtgo` deixa de saltar as páginas de liga dos formatos
     vigiados (sem descarregar a página não se sabe o que ela tem lá dentro);
  2. `sources.store_decklist` guarda uma liga — ou a lista de um jogador não
     vigiado, nos formatos de `so_jogadores_vigiados` — quando ela traz uma
     carta vigiada;
  3. `analysis.prune_leagues` não a apaga.
Para todo o resto o filtro fica **exactamente como estava**: uma liga sem carta
vigiada continua a não se guardar, e o metagame, a cobertura, o clustering e o
showcase não vêem uma lista a mais.

O ESTADO É CUMULATIVO, E É ELE A MEMÓRIA
----------------------------------------
`data/vigia-cartas.json` (ao lado da base, por `db.pasta_dados()` — a lição de
2026-09-08) guarda uma linha por AVISTAMENTO: carta, formato, evento, data,
jogador, colocação, link, tier e fonte. Duas razões, as duas necessárias:
  * **o toast só dispara no que é NOVO.** A chave de um avistamento é
    `formato|carta|data|jogador|evento` e não o `decklist_id` — o id muda quando
    a mesma lista volta a entrar por outra fonte (a deduplicação apaga e
    reinsere), e com ele o aviso repetia-se sem nada de novo ter acontecido;
  * **o `prune_decklists(30)` apaga as listas ao fim de um mês.** Sem o estado, o
    combo aparecia em Outubro e desaparecia da página em Novembro. Por isso
    guarda-se também a **lista de cartas** de cada avistamento — é o que ele quer
    montar, e sem ela o *"o que me falta"* morria com a poda.
O que NÃO se guarda é a lista de faltas: essa calcula-se sempre da base, porque
ele vai fotografar as cartas e uma falta congelada passava a mentir no dia
seguinte.

O ficheiro vai no `git add` do `daily.yml` e no `EXTRA_COMMIT` da tarefa
`mtgvault-daily`, pela razão do `arquetipos.json`: as duas corridas têm de
concordar sobre o que já foi visto.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from mtgvault import aviso, db, sources

CHAVE = "cartas_vigiadas"
FICHEIRO = "vigia-cartas.json"
VERSAO = 1

TITULO_AVISO = "mtgvault — vigia de cartas"

# A nota que acompanha SEMPRE o relatório de faltas. André, 2026-09-26: ele diz
# ter 4× Kasmina e 2× Enter the Infinite, e a base tem **0** de cada — as cópias
# novas só entram quando ele as fotografar (é o «só a foto cria cópias» de
# 19/09). Dizer que ele as tem era inventar colecção; calar que a base pode estar
# atrasada era deixá-lo a comprar outra vez.
NOTA_FALTAS = ("As faltas saem da BASE, não do que ele diz ter: uma cópia só "
               "entra quando a foto chega (pendentes/). Se acabou de comprar e "
               "ainda não fotografou, aparece aqui como falta.")


# ---------------------------------------------------------------------------
# O que está vigiado (colecao_config.json → cartas_vigiadas)
# ---------------------------------------------------------------------------
def _entradas(cfg=None) -> list[dict]:
    """As linhas do config, normalizadas. Aceita três formas de escrever:
    `{"carta": …, "formatos": […], "nota": …}`, `{"carta": …, "formato": "modern"}`
    e o nome sozinho (`"Kasmina, Enigma Sage"` = vigiada em todos os formatos)."""
    cfg = sources.config() if cfg is None else cfg
    linhas = cfg.get(CHAVE)
    if not isinstance(linhas, list):
        return []
    out = []
    for item in linhas:
        if not isinstance(item, dict):
            nome = str(item or "").strip()
            if nome:
                out.append({"carta": nome, "formatos": [], "nota": ""})
            continue
        nome = str(item.get("carta") or item.get("nome") or "").strip()
        if not nome:
            continue
        fmts = item.get("formatos", item.get("formato")) or []
        if isinstance(fmts, str):
            fmts = [fmts]
        out.append({
            "carta": nome,
            "formatos": sorted({str(f).strip().lower() for f in fmts
                                if str(f).strip()}),
            "nota": str(item.get("nota") or item.get("comentario") or "").strip()})
    return out


def cartas(cfg=None) -> list[dict]:
    """As cartas vigiadas, uma por nome. Sem `formatos` = todos os formatos.

    O mesmo nome escrito duas vezes junta os formatos em vez de dar duas
    entradas: duas linhas para a mesma carta eram dois avisos para o mesmo
    avistamento.
    """
    por_nome: dict[str, dict] = {}
    ordem: list[str] = []
    for e in _entradas(cfg):
        k = e["carta"].lower()
        if k in por_nome:
            a = por_nome[k]
            # Um `formatos` vazio quer dizer "todos" — e "todos" absorve a lista.
            a["formatos"] = ([] if not a["formatos"] or not e["formatos"]
                             else sorted(set(a["formatos"]) | set(e["formatos"])))
            a["nota"] = a["nota"] or e["nota"]
            continue
        por_nome[k] = dict(e)
        ordem.append(k)
    return [por_nome[k] for k in ordem]


def nomes_vigiados(fmt: str | None = None, cfg=None) -> set[str]:
    """Os nomes vigiados (em minúsculas) — num formato, ou em todos."""
    f = (fmt or "").strip().lower()
    return {e["carta"].lower() for e in cartas(cfg)
            if not f or not e["formatos"] or f in e["formatos"]}


def ha_vigia(fmt: str | None = None, cfg=None) -> bool:
    """Há alguma carta vigiada (neste formato, ou em qualquer um)?

    É esta pergunta que o `harvest_mtgo` faz antes de saltar uma página de liga:
    sem cartas vigiadas o daily fica **exactamente** como estava.
    """
    return bool(nomes_vigiados(fmt, cfg))


def formatos_vigiados(cfg=None) -> list[str]:
    fora: set[str] = set()
    for e in cartas(cfg):
        fora |= set(e["formatos"])
    return sorted(fora)


def _frente(nome: str) -> str:
    """O nome da frente. As listas trazem `A // B` nas cartas de duas faces."""
    return str(nome or "").split(" // ")[0].strip()


def nomes_na_lista(fmt: str | None, cards) -> list[str]:
    """As cartas VIGIADAS que esta lista tem. `cards` = [(board, nome, qty), …].

    É a chave que abre as três portas do filtro de tier. Fica aqui, e num sítio
    só, porque a pergunta é a mesma na recolha (`store_decklist`) e na poda
    (`prune_leagues`) — a segunda a respondê-la por si própria voltava a apagar
    a lista que a primeira acabou de guardar.
    """
    alvo = nomes_vigiados(fmt)
    if not alvo:
        return []
    achou: dict[str, str] = {}
    for c in cards or []:
        nome = _frente(c[1] if len(c) >= 2 else "")
        if nome.lower() in alvo:
            achou[nome.lower()] = nome
    return [achou[k] for k in sorted(achou)]


# ---------------------------------------------------------------------------
# O ficheiro de estado
# ---------------------------------------------------------------------------
def caminho_estado(pasta=None) -> Path:
    """`data/vigia-cartas.json` — ao lado da BASE (`db.pasta_dados()`).

    Não é o `ROOT`: neste PC só o `MTGVAULT_DB` está definido, e pelo `ROOT` o
    ficheiro ia parar a `~/mtgvault`, fora do repositório — o `git add` não
    encontrava nada e o estado nunca era publicado (a lição do
    `arquetipos.json`, 2026-09-08).
    """
    return (Path(pasta) / FICHEIRO) if pasta else (db.pasta_dados() / FICHEIRO)


def _vazio() -> dict:
    return {"versao": VERSAO, "cartas": {}, "achados": {}, "verificado_em": None}


def ler_estado(pasta=None) -> dict:
    """O estado, ou um vazio. Um ficheiro ilegível **não pára o daily** — é a
    mesma decisão do `arquetipos.carregar`; a corrida seguinte reescreve-o."""
    try:
        d = json.loads(caminho_estado(pasta).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _vazio()
    if not isinstance(d, dict):
        return _vazio()
    base = _vazio()
    base.update(d)
    for k in ("cartas", "achados"):
        if not isinstance(base.get(k), dict):
            base[k] = {}
    return base


def escrever_estado(estado: dict, pasta=None) -> Path:
    """Grava o estado ATOMICAMENTE (temporário + `os.replace`).

    A atomicidade não é higiene: o `daily` das 03:30 e o `webapp.py`, que fica de
    pé o dia todo, podem estar os dois a olhar para isto — e um `write_text` cru
    deixa o ficheiro truncado entre o `open` e o `write`. Foi assim que 24
    arquétipos passaram a 7 numa tarde (2026-09-08).
    """
    destino = caminho_estado(pasta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, destino)
    return destino


def chave(a: dict) -> str:
    """A identidade de um avistamento.

    NÃO é o `decklist_id`: a deduplicação entre fontes apaga e reinsere a mesma
    lista (`sources.store_decklist`), e com o id na chave o toast repetia-se sem
    nada de novo ter aparecido.
    """
    return "|".join([str(a.get("formato") or "").lower(),
                     str(a.get("carta") or "").lower(),
                     str(a.get("data") or ""),
                     str(a.get("jogador") or "").lower().strip(),
                     str(a.get("evento") or "")])


# ---------------------------------------------------------------------------
# A pergunta à base: que listas têm uma carta vigiada
# ---------------------------------------------------------------------------
def achados(con) -> list[dict]:
    """As listas na base com uma carta vigiada. **Sem filtro de tier nenhum.**

    Não passa pelo `sources.lista_conta`, e é de propósito: a regra do metagame é
    a resposta a outra pergunta (*"que decks valem para o ranking"*), e aqui a
    resposta certa é *"qualquer lista, incluindo um 5-0 de league"*.
    """
    out = []
    for e in cartas():
        nome = e["carta"]
        onde = ["(lower(dc.card_name) = ? OR lower(dc.card_name) LIKE ?)"]
        params: list = [nome.lower(), nome.lower() + " // %"]
        if e["formatos"]:
            onde.append("lower(d.format) IN (%s)"
                        % ",".join("?" * len(e["formatos"])))
            params += e["formatos"]
        for r in con.execute(
                f"""SELECT d.id did, d.format fmt, d.event_name ev,
                           d.event_date dia, d.player jog, d.placement pos,
                           d.url url, d.event_tier tier, d.source fonte,
                           d.event_players jogadores, dc.card_name nm,
                           dc.quantity q, dc.board board
                      FROM decklists d
                      JOIN decklist_cards dc ON dc.decklist_id = d.id
                     WHERE {" AND ".join(onde)}
                     ORDER BY d.event_date DESC, d.id DESC""", params):
            out.append({
                "carta": e["carta"], "nota": e["nota"], "formato": r["fmt"],
                "decklist_id": r["did"], "evento": r["ev"], "data": r["dia"],
                "jogador": r["jog"] or "", "colocacao": r["pos"] or "",
                "link": r["url"] or "", "tier": r["tier"] or "",
                "fonte": r["fonte"] or "", "jogadores": r["jogadores"],
                "copias": r["q"], "board": r["board"] or "main"})
    return out


def lista_da_decklist(con, did: int) -> list[list]:
    """A decklist inteira, `[[board, nome, qty], …]` — a fotografia que fica no
    estado para o *"o que me falta"* sobreviver ao `prune_decklists`."""
    return [[r["board"] or "main", r["card_name"], r["quantity"]]
            for r in con.execute(
                """SELECT board, card_name, quantity FROM decklist_cards
                    WHERE decklist_id = ? ORDER BY board DESC, card_name""",
                (did,))]


# ---------------------------------------------------------------------------
# O que falta para montar a lista
# ---------------------------------------------------------------------------
def faltas(con, lista, *, posse=None) -> dict:
    """O que falta para montar esta lista, contado na BASE.

    A posse é a da **colecção inteira** (`paginas.posse_total`, o mesmo número
    que a Deckboxes mostra como informação secundária de cada carta) e **sem
    regra de material**: uma lista de metagame não é uma caixa — não tem grupo de
    formato, não tem língua nem acabamento exigidos, e aplicar-lhe a regra do
    SPML (*tudo foil e inglês*) era inventar uma exigência que ele não pôs a um
    deck que ainda não decidiu montar. Diz-se na página.
    """
    from mtgvault import loadout, paginas                     # noqa: PLC0415
    posse = paginas.posse_total(con) if posse is None else posse
    precisa: dict[str, int] = {}
    for board, nm, q in lista or []:
        del board                     # main + side somam: é a mesma ida à gaveta
        precisa[_frente(nm)] = precisa.get(_frente(nm), 0) + int(q or 0)
    linhas = []
    for nm in sorted(precisa):
        tem = int(posse.get(nm) or 0)
        linhas.append({"nm": nm, "precisa": precisa[nm], "tem": tem,
                       "falta": max(0, precisa[nm] - tem),
                       "basica": nm in loadout.BASICS})
    nb = [m for m in linhas if not m["basica"]]
    return {"linhas": linhas,
            "falta_total": sum(m["falta"] for m in nb),
            "cartas_em_falta": sum(1 for m in nb if m["falta"]),
            "precisa_total": sum(m["precisa"] for m in nb),
            "tem_total": sum(min(m["tem"], m["precisa"]) for m in nb),
            "nota": NOTA_FALTAS}


# ---------------------------------------------------------------------------
# A verificação diária
# ---------------------------------------------------------------------------
def _resumo_achado(a: dict) -> str:
    partes = [f'{a["carta"]} em {a["formato"]}']
    if a.get("evento"):
        partes.append(a["evento"])
    if a.get("jogador"):
        partes.append(a["jogador"])
    if a.get("colocacao"):
        partes.append(str(a["colocacao"]))
    if a.get("data"):
        partes.append(a["data"])
    return " · ".join(partes)


def verificar(con, *, escrever: bool = True, avisar: bool = True,
             hoje: str | None = None, pasta=None, toast=None) -> dict:
    """Corre a vigia: procura, actualiza o estado e avisa **só o que é novo**.

    `toast` é injectável para o teste poder provar que o segundo dia não volta a
    avisar sem abrir uma janela no PC dele.
    """
    vig = cartas()
    if not vig:
        # SEM CARTAS VIGIADAS NÃO SE ESCREVE NADA. É o que garante que ligar isto
        # não muda um único ficheiro no dia em que ele não estiver a vigiar carta
        # nenhuma — nem o ficheiro de estado, nem um commit por causa dele.
        return {"vigiadas": 0, "novos": [], "todos": [], "linhas": [],
                "estado": None, "escrito": None, "avisos": [],
                "resumo": ("sem cartas vigiadas — nada a fazer "
                           "(colecao_config.json -> cartas_vigiadas)")}
    hoje = hoje or date.today().isoformat()
    estado = ler_estado(pasta)
    estado["versao"] = VERSAO
    estado["verificado_em"] = hoje
    estado.setdefault("desde", hoje)

    # As cartas que ele vigia, como estão no config HOJE. Reescreve-se sempre:
    # o config é a fonte, e uma carta que ele tirou de lá não pode continuar a
    # aparecer na página como se estivesse a ser vigiada.
    estado["cartas"] = {
        e["carta"].lower(): {"carta": e["carta"], "formatos": e["formatos"],
                             "nota": e["nota"], "achados": 0,
                             "primeira": None, "ultima": None}
        for e in vig}

    novos = []
    for a in achados(con):
        k = chave(a)
        antigo = estado["achados"].get(k)
        if antigo is None:
            linha = dict(a)
            linha["visto_em"] = hoje
            linha["avisado"] = False
            linha["lista"] = lista_da_decklist(con, a["decklist_id"])
            estado["achados"][k] = linha
            novos.append(linha)
        else:
            # Uma lista já conhecida acerta os dados que podem ter mudado (o id
            # muda com a deduplicação, o link e a contagem de jogadores chegam
            # depois pelo `backfill`) — mas nunca o `visto_em` nem o `avisado`.
            for campo in ("decklist_id", "link", "tier", "fonte", "jogadores",
                          "colocacao", "copias", "board", "nota"):
                if a.get(campo) not in (None, ""):
                    antigo[campo] = a[campo]
            if not antigo.get("lista"):
                antigo["lista"] = lista_da_decklist(con, a["decklist_id"])

    # Contagens por carta, do estado inteiro (inclui o que a poda já apagou da
    # base) — é o que a página mostra ao lado de cada carta vigiada.
    for linha in estado["achados"].values():
        c = estado["cartas"].get(str(linha.get("carta") or "").lower())
        if not c:
            continue                  # avistamento de uma carta que saiu do config
        c["achados"] += 1
        dia = linha.get("data") or ""
        c["primeira"] = min(c["primeira"] or dia, dia) if dia else c["primeira"]
        c["ultima"] = max(c["ultima"] or dia, dia) if dia else c["ultima"]

    avisos = []
    if novos and avisar:
        texto = _resumo_achado(novos[0])
        if len(novos) > 1:
            texto += f" (e mais {len(novos) - 1})"
        res = (toast or aviso.toast)(TITULO_AVISO, texto)
        avisos.append(res)
        for linha in novos:
            linha["avisado"] = True
            linha["aviso"] = res
    elif novos:
        for linha in novos:
            linha["avisado"] = True
            linha["aviso"] = "aviso desligado nesta corrida"

    escrito = escrever_estado(estado, pasta) if escrever else None
    todos = sorted(estado["achados"].values(),
                   key=lambda x: (str(x.get("data") or ""), str(x.get("carta"))),
                   reverse=True)
    return {"vigiadas": len(vig), "novos": novos, "todos": todos,
            "estado": estado, "escrito": escrito, "avisos": avisos,
            "linhas": linhas_para_o_log(con, vig, novos, todos),
            "resumo": _resumo(vig, novos, todos, avisos)}


def _resumo(vig, novos, todos, avisos) -> str:
    """A linha que fica no `job_runs` e no stdout do daily."""
    if novos:
        return (f"{len(novos)} LISTA(S) NOVA(S) com carta vigiada: "
                + "; ".join(_resumo_achado(a) for a in novos[:3])
                + (f" (+{len(novos) - 3})" if len(novos) > 3 else "")
                + (" · " + "; ".join(avisos) if avisos else ""))
    return (f"{len(vig)} carta(s) vigiada(s), {len(todos)} avistamento(s) "
            f"conhecido(s), 0 novos")


def linhas_para_o_log(con, vig, novos, todos) -> list[str]:
    """O que o passo do daily IMPRIME. Uma carta vigiada por linha, e o que
    apareceu de novo em destaque com o que lhe falta para a montar — um aviso que
    obriga a abrir uma página não avisa."""
    out = []
    for e in vig:
        onde = ", ".join(e["formatos"]) or "todos os formatos"
        n = sum(1 for a in todos if a.get("carta") == e["carta"])
        out.append(f"    [{' !! ' if n else 'nada'}] {e['carta']} ({onde})"
                   + (f": {n} lista(s)" if n else ": ainda sem listas")
                   + (f" — {e['nota']}" if e["nota"] else ""))
    for a in novos:
        out.append(f"    [NOVA]  {_resumo_achado(a)}")
        if a.get("link"):
            out.append(f"            {a['link']}")
        f = faltas(con, a.get("lista") or [])
        out.append(f"            falta comprar {f['falta_total']} cópia(s) de "
                   f"{f['cartas_em_falta']} carta(s) para montar "
                   f"(tens {f['tem_total']}/{f['precisa_total']})")
    return out


# ---------------------------------------------------------------------------
# O que a página do Metagame mostra (SÓ LEITURA)
# ---------------------------------------------------------------------------
def painel(con, *, pasta=None) -> dict:
    """As cartas vigiadas e o que apareceu, para a página.

    **Não escreve nada**, e isso é a metade que importa: o `metagame.html` é
    gerado pelo `daily` E servido pelo `webapp.py` a cada pedido. Se a página
    chamasse o `verificar`, o primeiro pedido do dia consumia os «novos» e o
    passo do daily já não tinha nada para avisar — o toast desaparecia sem
    ninguém mexer em nada.

    Junta os dois lados: o estado (que sobrevive ao `prune_decklists`) e a base
    (que traz o que apareceu hoje, antes de o passo correr).
    """
    vig = cartas()
    if not vig:
        return {"vigiadas": [], "achados": [], "total": 0, "nota": NOTA_FALTAS}
    estado = ler_estado(pasta)
    por_chave: dict[str, dict] = {}
    for linha in (estado.get("achados") or {}).values():
        if isinstance(linha, dict):
            por_chave[chave(linha)] = dict(linha)
    for a in achados(con):
        k = chave(a)
        if k in por_chave:
            por_chave[k].update({x: y for x, y in a.items() if y not in (None, "")})
        else:
            # Apareceu na base e o passo do daily ainda não correu: mostra-se já,
            # marcado, em vez de esperar pelas 03:30 de amanhã.
            linha = dict(a)
            linha["lista"] = lista_da_decklist(con, a["decklist_id"])
            linha["avisado"] = False
            por_chave[k] = linha

    nomes = {e["carta"].lower() for e in vig}
    lista = [a for k, a in por_chave.items()
             if str(a.get("carta") or "").lower() in nomes]
    for a in lista:
        a["faltas"] = faltas(con, a.get("lista") or [])
    lista.sort(key=lambda x: (str(x.get("data") or ""), str(x.get("carta"))),
               reverse=True)

    vigiadas = []
    for e in vig:
        minhas = [a for a in lista if str(a.get("carta") or "").lower()
                  == e["carta"].lower()]
        vigiadas.append({**e, "achados": len(minhas),
                         "ultima": minhas[0]["data"] if minhas else None})
    return {"vigiadas": vigiadas, "achados": lista, "total": len(lista),
            "desde": estado.get("desde"),
            "verificado_em": estado.get("verificado_em"),
            "nota": NOTA_FALTAS}
