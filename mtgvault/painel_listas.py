"""AS LISTAS DE REFERÊNCIA E OS RESULTADOS, TODOS OS DIAS (André, 2026-10-17).

*"todos os dias dá-me as decklists atualizadas e resultados que tiveram"*. Duas
secções novas no painel «Alterações dos decks», dois ficheiros em `data/painel/`
escritos pelo passo `painel-listas` do `daily`:

- `listas.json` — uma linha por carta da lista que cada deck dele usa HOJE;
- `resultados.json` — uma linha por lista de um dos decks dele num evento dos
  últimos `DIAS_RESULTADOS` dias, com o deck a que corresponde e se conta;
- `historico/AAAA-MM-DD-resultados.json` e `historico/AAAA-MM-DD-listas.json`,
  que não se apagam. As listas também, porque a `deck_lista_trocas` só guarda
  as trocas dos decks SEGUIDOS (`my_decks._store`): o consenso das caixas de
  Premodern recalcula-se todas as noites e não ficava escrito em lado nenhum.

**QUAIS SÃO OS DECKS DELE não se decide aqui** (`decks_dele`): são as mesmas
fontes que a aba Decks já junta (`decks_vista.registo`), sem o meta e sem o que
saiu — as CAIXAS (`decks_vista.decks_das_caixas`, a lista pelo despacho único
`loadout._slot_cards`), as VERSÕES com lista própria, os decks do registo que
ficam (o brew) — mais os decks que o `meus-decks` SEGUE (`my_decks.seguidos`, a
lista na tabela `decks`). Uma segunda regra ao lado discordava da página num dia
qualquer, em silêncio.

**A QUE DECK PERTENCE UMA LISTA também não se inventa** (`identidades`): é a
identidade que o vault já usa para escolher listas — a carta-assinatura da caixa
(`assinatura`/`reserva_assinatura`, com `_todas` e `_sem`, regra de 2026-10-02),
as cartas do meta de uma versão (`versoes.cartas_do_meta`), as cartas do
`my_decks.FOLLOWED` com os `!` de exclusão, o COMANDANTE em Duel Commander
(`decklists.commander`, 2026-10-01) e o JOGADOR dos decks seguidos por jogador.
Quem escolhe os ids é o `sources.ids_por_assinatura`, num sítio só.
Uma identidade cujas cartas NÃO estão na lista do próprio deck é recusada e dita
(é a caixa `modern`, cuja identidade de reserva é o Oswald e a lista é a Izzet).
"""
from __future__ import annotations

import html
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote

from mtgvault import caixas, decks_vista, eventos, painel, sources, versoes

DIAS_RESULTADOS = 7

CAMPOS = {
    "listas.json": ["id", "deck", "formato", "origem", "board", "carta", "qtd"],
    "resultados.json": ["id", "data", "formato", "evento", "jogadores", "tier", "lugar",
                        "jogador", "deck", "via", "conta", "url"],
}
FICHEIROS = tuple(CAMPOS)

# Quem ganha quando uma lista casa com mais do que um deck: a identidade mais
# ESPECÍFICA (mais cartas exigidas), e entre iguais a caixa antes da versão,
# antes do registo, antes do deck seguido. O jogador é a mais específica de
# todas: uma lista do Luffy é «a lista de referência que ele segue».
ORDEM_TIPO = {"caixa": 0, "versao": 1, "registo": 2, "seguido": 3}
PESO_JOGADOR = 100
PESO_COMANDANTE = 5

RE_PREFIXO_EVENTO = re.compile(r"^.{1,40}? event - ", re.I)
RE_PERCENT = re.compile(r"%[0-9A-Fa-f]{2}")


def decodificar_jogador(p: str | None) -> str:
    """Os nomes do mtgtop8 vêm URL-encoded em cp1252 e, por cima, com entidades
    HTML (`Jind%26%23345%3Bich` = «Jindřich»; `%8A` é «Š» em cp1252 e um
    carácter de controlo em latin-1). Um nome sem `%XX` fica como está."""
    p = p or ""
    if RE_PERCENT.search(p):
        p = unquote(p, encoding="cp1252", errors="replace")
    return html.unescape(p).strip()


def evento_curto(nome: str | None) -> str:
    """«Legacy event - Championship» → «Championship»."""
    return RE_PREFIXO_EVENTO.sub("", nome or "").strip()


def _board(b: str) -> str:
    return "main" if b == "main" else "sideboard"


def _agrupar(cards) -> list[tuple[str, str, int]]:
    tot: dict = {}
    for b, n, q in cards or []:
        k = (_board(b), n)
        tot[k] = tot.get(k, 0) + int(q)
    return sorted(((b, n, q) for (b, n), q in tot.items() if q),
                  key=lambda x: (x[0] != "main", x[1].lower()))


# ------------------------------------------------------------- os decks dele

def _origem_caixa(d: dict, s: dict, cfg: dict) -> str:
    fonte = (s.get("fonte") or "").lower()
    nota = d.get("nota") or ""
    rec = eventos.registo_de_evento(cfg, s.get("slot")) if fonte == "escolhido" else None
    if rec:
        return "lista de evento: " + eventos.texto_prov(rec.get("evento"))
    if fonte == "escolhido":
        o = (cfg.get("listas_escolhidas") or {}).get(s.get("ref") or "", {}).get("origem")
        return "lista fixada: " + str(o or nota)
    if fonte == "deck" and nota.startswith("consenso de "):
        return "consenso: " + re.split(r" — | \(janela", nota[len("consenso de "):])[0]
    if fonte == "consenso":
        return "consenso: " + re.split(r" \(janela", nota.replace("consenso de ", "", 1))[0]
    if fonte == "vigiado":
        return f"vigiado: {s.get('ref')} — {nota}"
    return f"{fonte}: {nota}" if nota else fonte


def _ident_caixa(con, d: dict, s: dict, cfg: dict) -> list[dict]:
    if s.get("assinatura"):
        return [{"cartas": list(s["assinatura"]), "todas": bool(s.get("assinatura_todas")),
                 "sem": list(s.get("assinatura_sem") or [])}]
    if s.get("reserva_assinatura"):
        return [{"cartas": list(s["reserva_assinatura"]),
                 "todas": bool(s.get("reserva_assinatura_todas", s.get("assinatura_todas"))),
                 "sem": list(s.get("reserva_assinatura_sem") or [])}]
    if d["formato"] in sources.COMMANDER_FORMATS:
        cmd = decks_vista.comandante_do_deck(con, d)
        if not cmd:
            escolhido = ((cfg.get("consenso_comandante") or {}).get("comandante") or "").strip()
            if (escolhido and (cfg.get("consenso_comandante") or {}).get("formato",
                                                                          d["formato"]) == d["formato"]
                    and escolhido in {n for _b, n, _q in d["cards"]}):
                cmd = escolhido
        if cmd:
            return [{"comandante": cmd}]
    return []


def decks_dele(con, cfg: dict | None = None) -> tuple[list[dict], list[str]]:
    """Os decks que ele monta ou segue, cada um com a lista de hoje e as
    identidades. Devolve `(decks, notas)` — as notas dizem o que ficou de fora
    e porquê, para o `daily` o imprimir."""
    import my_decks  # noqa: PLC0415  (vive na raiz, como os outros geradores)

    cfg = sources.config() if cfg is None else cfg
    notas: list[str] = []
    out: list[dict] = []
    por_chave: dict[str, dict] = {}
    slots = {s.get("slot"): s for s in caixas.slots(cfg)}

    for d in decks_vista.decks_das_caixas(con, cfg):
        if d.get("desactivada") or not d["cards"]:
            notas.append(f"caixa {d['slot']} fora: {d.get('rotulo_estado') or d.get('nota') or 'sem lista'}")
            continue
        s = slots.get(d["slot"]) or {}
        x = {"chave": d["id"], "deck": d["nome"], "formato": d["formato"], "tipo": "caixa",
             "origem": _origem_caixa(d, s, cfg), "cartas": _agrupar(d["cards"]),
             "identidades": _ident_caixa(con, d, s, cfg)}
        out.append(x)
        por_chave[x["chave"]] = x

    # AS VERSÕES. Uma versão cuja lista vive numa caixa dá-lhe mais uma
    # identidade (o Abzan Greasefang é a caixa `pioneer`); as outras são um deck.
    for fmt in versoes.formatos(cfg):
        nome_fmt = (versoes.do_formato(fmt, cfg) or {}).get("nome") or fmt
        for v in versoes.versoes(fmt, cfg):
            alvo = versoes.deck_da_versao(v)
            ident = ([{"cartas": versoes.cartas_do_meta(v), "todas": True, "sem": []}]
                     if versoes.cartas_do_meta(v) else [])
            if alvo in por_chave:
                por_chave[alvo]["identidades"] += ident
                continue
            rec = (cfg.get("listas_escolhidas") or {}).get(alvo) or {}
            if not rec.get("cards"):
                notas.append(f"versao {v.get('id')} fora: sem lista fixada ({alvo})")
                continue
            prov = rec.get("evento")
            x = {"chave": alvo, "deck": f"{nome_fmt} · {v.get('nome') or v.get('id')}",
                 "formato": fmt, "tipo": "versao",
                 "origem": ("lista de evento: " + eventos.texto_prov(prov)) if prov
                 else "lista fixada: " + str(rec.get("origem") or ""),
                 "cartas": _agrupar(rec["cards"]), "identidades": ident}
            out.append(x)
            por_chave[alvo] = x

    # OS DECKS DO REGISTO QUE FICAM (o brew da Kasmina). O que saiu (`_saiu`) e
    # o que espera o OK dele (`por_confirmar`, o Flow State) não são decks dele.
    for d in decks_vista.decks_de_evento(con, cfg):
        if d["id"] in por_chave:
            continue
        if versoes.saiu(d["id"], cfg):
            continue
        if d.get("por_confirmar"):
            notas.append(f"{d['nome']} fora: à espera do teu OK")
            continue
        if not d["cards"]:
            continue
        x = {"chave": d["id"], "deck": d["nome"], "formato": d["formato"], "tipo": "registo",
             "origem": ("brew: " + d["brew"]) if d.get("brew") else d.get("nota") or "registo",
             "cartas": _agrupar(d["cards"]), "identidades": []}
        out.append(x)
        por_chave[x["chave"]] = x

    # OS DECKS QUE O `meus-decks` SEGUE, com a lista da tabela `decks`.
    excl = {n: c for n, _f, c in my_decks.FOLLOWED}
    jog = {n: p for n, _f, p in my_decks.FOLLOWED_PLAYERS}
    jog_cmd = {n: (p, c) for n, _f, p, c in my_decks.FOLLOWED_PLAYER_DECK}
    nomes = {(x["deck"], x["formato"]) for x in out}
    for s in my_decks.seguidos():
        row = con.execute("SELECT id, notes FROM decks WHERE name = ? AND format = ?",
                          (s["deck"], s["formato"])).fetchone()
        cartas = [] if row is None else _agrupar(
            (r["board"], r["card_name"], r["quantity"]) for r in con.execute(
                "SELECT board, card_name, quantity FROM deck_cards WHERE deck_id = ?", (row["id"],)))
        if not cartas:
            notas.append(f"seguido {s['deck']} fora: sem lista na tabela decks")
            continue
        nome = s["deck"]
        if (nome, s["formato"]) in nomes:
            nome = f"{nome} (seguido)"
        if s["deck"] in excl:
            c = excl[s["deck"]]
            ident = [{"cartas": [x for x in c if not x.startswith("!")], "todas": True,
                      "sem": [x[1:] for x in c if x.startswith("!")]}]
        elif s["deck"] in jog_cmd:
            p, c = jog_cmd[s["deck"]]
            ident = [{"jogador": p, "comandante": c[0]}]
        else:
            ident = [{"jogador": jog.get(s["deck"])}]
        notes = row["notes"] or ""
        x = {"chave": str(row["id"]), "deck": nome, "formato": s["formato"], "tipo": "seguido",
             "origem": "seguido: " + notes[len("auto: "):] if notes.startswith("auto: ") else notes,
             "cartas": cartas, "identidades": ident}
        out.append(x)
        nomes.add((nome, s["formato"]))

    # UMA IDENTIDADE TEM DE ESTAR NA LISTA DO PRÓPRIO DECK. Sem isto a caixa
    # `modern` (lista Izzet, identidade de reserva Oswald) ficava com as listas
    # do Oswald — o aviso de 02/10, ainda de pé.
    for x in out:
        tem = {n for _b, n, _q in x["cartas"]}
        boas = []
        for i in x["identidades"]:
            cs = i.get("cartas") or []
            ok = (all(c in tem for c in cs) if i.get("todas") else any(c in tem for c in cs)) \
                if cs else True
            if i.get("comandante") and i["comandante"] not in tem:
                ok = False
            if ok:
                boas.append(i)
            else:
                notas.append(f"{x['deck']}: identidade recusada ({texto_via(i)} nao esta na lista do deck)")
        x["identidades"] = boas
        if not boas:
            notas.append(f"{x['deck']}: sem identidade — nao recebe resultados")
    out.sort(key=lambda x: (x["formato"], ORDEM_TIPO[x["tipo"]], x["deck"].lower()))
    return out, notas


def texto_via(i: dict) -> str:
    p = []
    if i.get("jogador"):
        p.append(f"jogador {i['jogador']}")
    if i.get("comandante"):
        p.append(f"comandante {i['comandante']}")
    if i.get("cartas"):
        p.append("assinatura " + sources.texto_assinatura(i["cartas"], i.get("todas"), i.get("sem")))
    return " + ".join(p)


def _peso(i: dict) -> int:
    if i.get("jogador"):
        return PESO_JOGADOR
    if i.get("comandante"):
        return PESO_COMANDANTE
    cs = i.get("cartas") or []
    return (len(cs) if i.get("todas") else 1) + len(i.get("sem") or [])


def _ids(con, fmt: str, i: dict, desde: str) -> list[int]:
    if i.get("cartas"):
        return sources.ids_por_assinatura(con, fmt, i["cartas"], todas=bool(i.get("todas")),
                                          desde=desde, so_que_contam=False, sem=i.get("sem"))
    q, p = "SELECT id FROM decklists WHERE format = ? AND event_date >= ?", [fmt, desde]
    if i.get("jogador"):
        q += " AND lower(player) = lower(?)"
        p.append(i["jogador"])
    if i.get("comandante"):
        q += " AND commander = ?"
        p.append(i["comandante"])
    return [r[0] for r in con.execute(q, p)]


# -------------------------------------------------------------- os ficheiros

def listas(decks: list[dict]) -> list[dict]:
    out = []
    for x in decks:
        for b, n, q in x["cartas"]:
            out.append({"id": f"{x['chave']}|{b}|{n}", "deck": x["deck"],
                        "formato": x["formato"], "origem": x["origem"],
                        "board": b, "carta": n, "qtd": q})
    return out


def _ordem_lugar(p: str | None) -> int:
    m = re.match(r"\d+", str(p or ""))
    return int(m.group(0)) if m else 999


def resultados(con, decks: list[dict], hoje: str) -> list[dict]:
    desde = (date.fromisoformat(hoje) - timedelta(days=DIAS_RESULTADOS)).isoformat()
    melhor: dict[int, tuple] = {}
    for x in decks:
        for i in x["identidades"]:
            chave = (-_peso(i), ORDEM_TIPO[x["tipo"]], x["deck"].lower())
            for lid in _ids(con, x["formato"], i, desde):
                if lid not in melhor or chave < melhor[lid][0]:
                    melhor[lid] = (chave, x, i)
    out = []
    for lid, (_k, x, i) in melhor.items():
        r = con.execute("SELECT * FROM decklists WHERE id = ?", (lid,)).fetchone()
        if r is None or r["event_date"] > hoje:
            continue
        out.append({"id": str(lid), "data": r["event_date"], "formato": r["format"],
                    "evento": evento_curto(r["event_name"]), "jogadores": r["event_players"],
                    "tier": r["event_tier"], "lugar": r["placement"],
                    "jogador": decodificar_jogador(r["player"]), "deck": x["deck"],
                    "via": texto_via(i),
                    "conta": "sim" if sources.lista_conta(r, r["format"], consenso=False) else "nao",
                    "url": r["url"] or ""})
    # Mais recentes primeiro; dentro do dia, por formato, evento e lugar.
    out.sort(key=lambda a: (a["formato"], a["evento"], _ordem_lugar(a["lugar"]),
                            a["jogador"].lower()))
    out.sort(key=lambda a: a["data"], reverse=True)
    return out


def escrever(con, raiz: Path | None = None, hoje: str | None = None,
             cfg: dict | None = None) -> dict:
    hoje = hoje or date.today().isoformat()
    p = painel.pasta(raiz)
    decks, notas = decks_dele(con, cfg)
    dados = {"listas.json": listas(decks), "resultados.json": resultados(con, decks, hoje)}
    escritos = []
    for nome, linhas in dados.items():
        painel._escrever_json(p / nome, linhas)               # noqa: SLF001
        escritos.append(p / nome)
        h = p / "historico" / f"{hoje}-{nome.split('.')[0]}.json"
        painel._escrever_json(h, linhas)                      # noqa: SLF001
        escritos.append(h)
    res = dados["resultados.json"]
    por_deck: dict[str, int] = {}
    for a in res:
        por_deck[a["deck"]] = por_deck.get(a["deck"], 0) + 1
    return {"decks": [(x["deck"], x["formato"], x["tipo"]) for x in decks],
            "linhas_listas": len(dados["listas.json"]), "resultados": len(res),
            "contam": sum(1 for a in res if a["conta"] == "sim"),
            "por_deck": por_deck, "notas": notas,
            "ficheiros": [(str(f.resolve()), painel.hora_do_ficheiro(f)) for f in escritos]}


def texto(r: dict) -> str:
    pd = ", ".join(f"{d} {n}" for d, n in sorted(r["por_deck"].items(), key=lambda x: -x[1]))
    nt = (" | " + "; ".join(r["notas"])) if r["notas"] else ""
    return (f"{len(r['decks'])} decks, {r['linhas_listas']} linhas de listas; "
            f"{r['resultados']} resultados em {DIAS_RESULTADOS} dias ({r['contam']} contam): "
            f"{pd} | escritos: {painel.texto_ficheiros(r['ficheiros'])}{nt}")
