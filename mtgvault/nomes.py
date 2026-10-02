"""O NOME DE UM ARQUÉTIPO VEM DA FONTE, NÃO DO CLUSTERING (André, 2026-10-02).

À letra: *"procura no mtgtop8, lá tem os nomes, e a partir daí já tens ideia do
que são as listas"*. Tinha razão, e o nome estava a ser deitado fora **na
recolha**: a página do evento do mtgtop8 traz o nome ao lado de cada deck
(*"#2 Landstill - Vittorio Piatti"*, e o link `<a …>Landstill</a>`), e o único
ficheiro que a recolha abria por deck era o `.dec`, que só tem cartas. Havia
2 635 listas de `mtgtop8` na base e **nenhuma coluna** onde esse nome estivesse.
É a MESMA falha do comandante, fechada a 2026-10-01 — e o `meta_coverage` tinha-a
até escrita como se fosse um facto do mundo: *"a fonte não nos dá o nome do
arquétipo"*.

O que havia em vez disso era o `archetypes.label`, o agrupamento automático, que
se chama *"Solitary Confinement / Argothian Enchantress / Sterling Grove"* e tem
centenas de etiquetas parecidas e vazias (medido a 2026-10-02: 7 493 etiquetas,
6 844 sem uma única lista). O agrupamento **funciona** — esse cluster de 108
listas É a Enchantress — mas não tem nome, e isso custou três erros numa semana.

A REGRA, em duas metades:
  1. **o nome da FONTE ganha sempre** (`decklists.arquetipo_fonte`);
  2. **onde não houver, o grupo HERDA** o nome mais votado entre as listas dele
     que TENHAM nome. É isto que dá nome às 5 173 listas de `mtgo`, que não
     trazem nenhum: uma lista de MTGO que caia no grupo da Enchantress passa a
     chamar-se Enchantress.

Sem nenhuma das duas, o nome é o GERADO de sempre (`meta_coverage._name_for`:
cores + carta-chave) e vai marcado **provisório**, com a etiqueta ao lado como
até aqui. Um nome gerado é verdade sobre as cartas, mas não é o nome do deck.

NÃO SE GRAVA O NOME HERDADO, e é de propósito — ao contrário do `commander`, que
o André mandou gravar. Aqui o herdado é uma CONTA sobre o que a fonte disse: no
dia em que entrar uma lista nomeada a mais, ou o agrupamento mudar, a conta
acerta-se sozinha. Gravá-lo era criar uma segunda verdade que envelhece em
silêncio — e o que a fonte disse, que é o dado, esse está gravado.

A PERGUNTA VIVE NUM SÍTIO SÓ, e são três os sítios que a fazem: o nome de um
cluster da tabela `archetypes` (metagame, cobertura, sugestões, deckboxes), o nome
de um cluster do `showcase` (que tem clustering próprio) e o nome do arquétipo de
uma CAIXA (a arrumação por fases). As três reduzem-se a **uma votação sobre um
conjunto de ids de listas** — `nome_das_listas`. Dois contadores ao lado
discordariam um dia qualquer, em silêncio: é a lição do `event_tier`, do `e_foil`
e do `precos.sql()`.
"""
from __future__ import annotations

import sqlite3
from collections import Counter

# Como se chegou ao nome. Vai no payload das páginas para elas poderem dizê-lo.
ORIGEM_FONTE = "fonte"        # a própria lista traz o nome (mtgtop8, manual)
ORIGEM_HERDADO = "herdado"    # o grupo herdou-o das listas nomeadas que tem
ORIGEM_GERADO = "gerado"      # ninguém o nomeou: cores + carta-chave (provisório)


def nome_das_listas(con: sqlite3.Connection, ids) -> dict | None:
    """O nome mais votado entre estas listas, ou `None` se nenhuma tiver nome.

    `{nome, votos, nomeadas, listas, segundo}` — `votos` é quantas votaram no
    nome que ganhou, `nomeadas` quantas tinham nome, `listas` o total, e
    `segundo` o nome em segundo lugar (ou `None`). Os quatro números vão para a
    página: *"Enchantress — 41 de 108 listas"* é uma afirmação que se pode
    conferir, e um empate contestado fica à vista em vez de escondido.

    O desempate é pelo NOME, por ordem alfabética, e não pela ordem em que as
    linhas saem da base: um nome que mude de um dia para o outro sem nada ter
    mudado é exactamente o defeito que isto veio corrigir (foi o que aconteceu ao
    *"Dimir Psychatog"*, que passou a *"Dimir Polluted Delta"* na corrida
    seguinte).
    """
    ids = [int(i) for i in (ids or [])]
    if not ids:
        return None
    votos: Counter = Counter()
    for i in range(0, len(ids), 900):          # o SQLite tem tecto de variáveis
        bloco = ids[i:i + 900]
        marcas = ",".join("?" for _ in bloco)
        for r in con.execute(
            f"""SELECT arquetipo_fonte nm, COUNT(*) n FROM decklists
                 WHERE id IN ({marcas}) AND arquetipo_fonte IS NOT NULL
                 GROUP BY arquetipo_fonte""", bloco):
            votos[r["nm"]] += r["n"]
    if not votos:
        return None
    ordenados = sorted(votos.items(), key=lambda kv: (-kv[1], kv[0]))
    nome, n = ordenados[0]
    return {"nome": nome, "votos": n, "nomeadas": sum(votos.values()),
            "listas": len(ids),
            "segundo": ordenados[1][0] if len(ordenados) > 1 else None}


def nomes_por_cluster(con: sqlite3.Connection, fmt: str | None = None) -> dict[int, dict]:
    """`{archetype_id: {nome, votos, nomeadas, listas, segundo}}` de um formato.

    Uma consulta por formato em vez de uma por arquétipo: as páginas do metagame
    nomeiam dezenas de clusters por corrida.

    Conta TODAS as listas que têm aquele `archetype_id`, e não só as que contam
    para o metagame. É deliberado e é outra pergunta: o filtro de eventos decide
    o que PESA num ranking, e aqui o que se quer é saber como é que o deck se
    chama — uma lista de uma liga nomeada *"Goblins"* pela fonte diz a verdade
    sobre o deck dela, conte ou não para o top-10.
    """
    por: dict[int, Counter] = {}
    total: Counter = Counter()
    onde, params = ("", [])
    if fmt:
        onde, params = " AND format = ?", [fmt]
    for r in con.execute(
        f"""SELECT archetype_id aid, arquetipo_fonte nm, COUNT(*) n
              FROM decklists
             WHERE archetype_id IS NOT NULL{onde}
             GROUP BY archetype_id, arquetipo_fonte""", params):
        total[r["aid"]] += r["n"]
        if r["nm"]:
            por.setdefault(r["aid"], Counter())[r["nm"]] += r["n"]
    out: dict[int, dict] = {}
    for aid, votos in por.items():
        ordenados = sorted(votos.items(), key=lambda kv: (-kv[1], kv[0]))
        nome, n = ordenados[0]
        out[aid] = {"nome": nome, "votos": n, "nomeadas": sum(votos.values()),
                    "listas": total[aid],
                    "segundo": ordenados[1][0] if len(ordenados) > 1 else None}
    return out


def _cache_do_formato(con, fmt: str, cache: dict | None) -> dict[int, dict]:
    if cache is None:
        return nomes_por_cluster(con, fmt)
    # O prefixo `#nomes:` é para este cache poder partilhar o saco com quem já
    # tinha um (o `meta_coverage._type_boost`, indexado por NOME DE CARTA): não há
    # carta nenhuma que comece por `#`.
    chave = f"#nomes:{fmt or ''}"
    if chave not in cache:
        cache[chave] = nomes_por_cluster(con, fmt)
    return cache[chave]


def nome_do_cluster(con: sqlite3.Connection, aid: int, fmt: str | None = None,
                    cache: dict | None = None) -> dict | None:
    """O nome votado de um `archetypes.id`, ou `None` se nenhuma lista dele tem nome."""
    if aid is None:
        return None
    if fmt is None:
        r = con.execute("SELECT format FROM archetypes WHERE id = ?", (aid,)).fetchone()
        fmt = r["format"] if r else None
    return _cache_do_formato(con, fmt, cache).get(int(aid))


def nome_da_lista(con: sqlite3.Connection, did: int,
                  cache: dict | None = None) -> tuple[str | None, str]:
    """`(nome, origem)` de uma decklist. A da própria lista ganha à do grupo."""
    r = con.execute("SELECT format, archetype_id, arquetipo_fonte FROM decklists "
                    "WHERE id = ?", (did,)).fetchone()
    if not r:
        return None, ""
    if r["arquetipo_fonte"]:
        return r["arquetipo_fonte"], ORIGEM_FONTE
    v = nome_do_cluster(con, r["archetype_id"], r["format"], cache) if r["archetype_id"] else None
    return (v["nome"], ORIGEM_HERDADO) if v else (None, "")


def rotulo(con: sqlite3.Connection, aid: int, etiqueta: str = "",
           gerado: str = "", fmt: str | None = None,
           cache: dict | None = None) -> dict:
    """O que a página mostra para um arquétipo.

    `{nome, origem, provisorio, etiqueta, votos, nomeadas, listas, segundo}`.
    `gerado` é o nome que o `meta_coverage._name_for` sabe compor a partir das
    cartas (cores + carta-chave) e `etiqueta` o rótulo de três cartas do
    agrupamento — os dois continuam a servir, mas só quando a fonte não tem nada
    a dizer, e aí a página di-lo (`provisorio`). Mostrar um nome inventado com o
    mesmo aspecto de um nome verdadeiro é o que nos custou os três erros.
    """
    v = nome_do_cluster(con, aid, fmt, cache)
    if v:
        return {"nome": v["nome"], "origem": ORIGEM_HERDADO, "provisorio": False,
                "etiqueta": etiqueta, "votos": v["votos"],
                "nomeadas": v["nomeadas"], "listas": v["listas"],
                "segundo": v["segundo"]}
    return {"nome": gerado or etiqueta or (f"#{aid}" if aid else ""),
            "origem": ORIGEM_GERADO, "provisorio": True, "etiqueta": etiqueta,
            "votos": 0, "nomeadas": 0, "listas": 0, "segundo": None}


def cobertura(con: sqlite3.Connection, fmt: str | None = None) -> dict:
    """Quantas listas têm nome, e por que via. É o número do relatório e o que
    diz se isto está a funcionar: `{listas, da_fonte, herdado, sem_nome,
    sem_grupo, clusters, clusters_com_nome}`."""
    onde, params = ("", [])
    if fmt:
        onde, params = " WHERE format = ?", [fmt]
    nomeados = nomes_por_cluster(con, fmt)
    da_fonte = herdado = sem = sem_grupo = total = 0
    for r in con.execute(
            f"SELECT archetype_id aid, arquetipo_fonte nm FROM decklists{onde}", params):
        total += 1
        if r["nm"]:
            da_fonte += 1
        elif r["aid"] is None:
            sem_grupo += 1
            sem += 1
        elif r["aid"] in nomeados:
            herdado += 1
        else:
            sem += 1
    clusters = con.execute(
        f"SELECT COUNT(*) c FROM archetypes{' WHERE format = ?' if fmt else ''}",
        params).fetchone()["c"]
    return {"listas": total, "da_fonte": da_fonte, "herdado": herdado,
            "sem_nome": sem, "sem_grupo": sem_grupo, "clusters": clusters,
            "clusters_com_nome": len(nomeados)}
