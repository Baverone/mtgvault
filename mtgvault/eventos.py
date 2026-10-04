"""A LISTA DE UM DECK É UMA LISTA QUE ALGUÉM JOGOU (André, 2026-10-04, ao fim do
dia, à letra).

    *"as listas especificas e que quero fixas"*
    *"as outras quero que esquecas as decklists e vamos focar nas decklists
    baseadas em eventos reais"*

Acaba o CONSENSO como lista de deck. Uma lista de consenso é a média de muitas
listas — **ninguém jogou aquele deck**. O caso que o provou foi o do Cloud, no
mesmo dia: as 40 listas de Duel Commander que a assinatura apanhava eram **dois
decks diferentes**, e a média dava um terceiro que não fazia nenhuma das duas
coisas. Ele generalizou a lição.

**O motor do consenso NÃO se apaga** (regra dele de 2026-09-09): continua a medir
o metagame, a dar os nomes, a alimentar a reserva da venda e a servir de termo de
comparação. O que muda é **qual a lista que a caixa mostra**.

O QUE ESTE MÓDULO É
-------------------
A pergunta *"qual é a melhor lista real deste deck?"* **num sítio só**. São três
superfícies a fazê-la — a caixa (`loadout._slot_cards`), o arquétipo meta da aba
Decks (`decks_vista`) e a CLI — e dois selectores ao lado discordam um dia
qualquer, em silêncio: é a lição do `event_tier`, do `e_foil`, do `precos.sql()`
e do `nomes.nome_das_listas`.

A REGRA DE ESCOLHA VIVE NO CONFIG, não aqui
-------------------------------------------
`colecao_config.json -> listas_de_evento.regra` tem os critérios **pela ordem** e
a razão de cada um, em português. Está lá e não no código para não ser *a minha
opinião de hoje*: daqui a um mês ele lê o ficheiro e sabe porque é que a caixa
ficou com aquela lista. Este módulo lê-a; `REGRA_OMISSAO` é o que vale quando a
chave não existe (uma base nova, os testes).

A PROVENIÊNCIA GRAVA-SE, NÃO SE RECALCULA
-----------------------------------------
E isto é a decisão que torna o resto possível. O `daily.prune_decklists(30)`
apaga as decklists ao fim de um mês: uma caixa que fosse um PONTEIRO para um
`decklist_id` ficava **vazia em Novembro**, sem um único passo a falhar — o
padrão do `event_tier` aplicado à lista por que ele vai sleevar. Por isso as
cartas **e** a proveniência são lidas da base no momento de fixar e gravadas no
`colecao_config.json`, que é exactamente o que o mecanismo da LISTA PADRÃO
(2026-09-20) já faz e é a prova de que esse é o sítio certo. É a mesma razão por
que a VIGIA DE CARTAS guarda a decklist inteira em cada avistamento.

O `decklist_id` guarda-se ao lado, para se poder **conferir** enquanto a lista
existir na base — nunca para a ler em tempo de página.
"""
from __future__ import annotations

import json
from datetime import date

from . import padrao, scryfall, sources

# A ordem dos critérios. Vive no config (`listas_de_evento.regra`); isto é o que
# vale sem ele. Cada entrada é `(chave, razão)` — a razão viaja para o config e
# para a página, porque um critério sem razão ao lado é uma opinião.
REGRA_OMISSAO = [
    ["janela",
     "a janela do consenso primeiro, como FILTRO: nos formatos que não estão em "
     "`consenso.excepcoes`, uma lista anterior ao Reality Fracture (29/09) não "
     "descreve o deck que se joga hoje. O premodern está excepcionado e usa a "
     "história toda."],
    ["tier",
     "a IMPORTÂNCIA do evento, e o primeiro degrau dela é o dele: **presenciais "
     "antes de online** — papel é o que ele joga. Depois, entre os online, um RC "
     "(Super) Qualifier antes de "
     "uma Challenge, e uma Challenge antes de uma liga. Sem este critério o vault "
     "preferia a Challenge à qualificação, e por uma razão de DADOS e não de "
     "mérito: o `Modern RC Super Qualifier` vem do mtgo.com, que não serve "
     "classificação nem contagem de jogadores (medido a 04/10: 31 listas, zero de "
     "cada), enquanto a mesma Challenge re-hospedada pelo mtgtop8 traz `100 "
     "jogadores` e `3-4`. Comparar os dois pelo campo medido era deixar a FONTE "
     "decidir o que devia ser decidido pelo torneio. É também a hierarquia que ele "
     "já tinha dado a 2026-09-07 e o evento que lhe interessa: quem joga um RC "
     "Qualifier está a tentar qualificar-se para o mesmo Regional Championship "
     "que ele vai jogar. **É UM CRITÉRIO SÓ e não dois**: houve uma passagem em "
     "que o «presencial» era um critério à parte, à frente deste — e nunca mudava "
     "nada, porque `Presencial` já é o primeiro degrau do tier. Uma regra escrita "
     "que não tem efeito é a armadilha do `playset_maximo` e do `dedicado: "
     "false`; o `tests/_chumba_listas_eventos.py` apanhou-a a tentar prová-la."],
    ["campo",
     "entre presenciais, campo maior primeiro: um 5-8 de 218 jogadores vale mais "
     "do que um 1.º lugar de 16."],
    ["repetida",
     "se o MESMO piloto venceu mais do que uma vez com a MESMA lista (o "
     "`content_hash` igual), essa ganha a um resultado único melhor — foi o que "
     "provou a lista do Cloud, três primeiros lugares sem mudar uma vírgula. "
     "Conta como repetição só a aparição que É um resultado (presencial, ou com "
     "classificação registada): um 5-0 de Challenge do MTGO não tem "
     "classificação e não é «ter ganhado»."],
    ["classificacao",
     "depois, a melhor classificação."],
    ["data",
     "depois, a mais recente."],
    ["jogador",
     "e por fim o nome do jogador, por ordem alfabética. É só um desempate, mas "
     "tem de ser DETERMINISTA e não a ordem por que as linhas saem da base: um "
     "deck que mudasse de lista de um dia para o outro sem nada ter mudado é o "
     "defeito que isto vem corrigir (foi o que aconteceu ao «Dimir Psychatog» a "
     "2026-10-02)."],
]

# Quanto vale cada classificação, menor é melhor. O mtgtop8 escreve `1`, `2`,
# `3-4`, `5-8`, `9-16`, `17-32`; as Challenges do mtgo.com não trazem nenhuma.
SEM_CLASSIFICACAO = 10_000

# A IMPORTÂNCIA de um evento, menor é melhor. São os `event_tier` que o
# `sources.event_tier` escreve e os únicos quatro em uso na base (medido a
# 04/10: Challenge 5 799, Presencial 1 767, Qualifier 155, League 130).
PESO_TIER = {"Presencial": 0, "Qualifier": 1, "Challenge": 2, "outro": 3,
             "League": 4}
PESO_TIER_DESCONHECIDO = 3


def regra() -> list[list]:
    """A regra de escolha em vigor, pela ordem. Do config, senão a de omissão."""
    v = (sources.config().get("listas_de_evento") or {}).get("regra")
    if isinstance(v, list) and v:
        out = []
        for item in v:
            if isinstance(item, (list, tuple)) and item:
                out.append([str(item[0]), str(item[1]) if len(item) > 1 else ""])
            elif isinstance(item, dict) and item.get("criterio"):
                out.append([str(item["criterio"]), str(item.get("razao") or "")])
        if out:
            return out
    return [list(x) for x in REGRA_OMISSAO]


def criterios() -> list[str]:
    return [c for c, _r in regra()]


def valor_classificacao(placement) -> int:
    """`3-4` -> 3, `1` -> 1, vazio -> SEM_CLASSIFICACAO (pior do que qualquer uma).

    Uma lista sem classificação **não** é a melhor nem a pior por acidente: é
    explicitamente a pior, porque não se pode afirmar nada sobre ela.
    """
    s = str(placement or "").strip()
    if not s:
        return SEM_CLASSIFICACAO
    cab = s.split("-", 1)[0].strip()
    try:
        return int(cab)
    except ValueError:
        return SEM_CLASSIFICACAO


def peso_tier(tier) -> int:
    """A importância de um evento, menor é melhor. Um tier que não se conhece
    não é o melhor nem o pior por acidente: fica no meio, com o `outro`."""
    return PESO_TIER.get(str(tier or ""), PESO_TIER_DESCONHECIDO)


def e_resultado(row) -> bool:
    """Esta aparição É um resultado? (presencial, ou com classificação.)

    É o que distingue *"ganhou três vezes com a mesma lista"* — o caso do Cloud,
    três presenciais com o 1.º lugar — de *"jogou a mesma lista em três
    Challenges do MTGO"*, que não traz classificação nenhuma e por isso não
    prova resultado. Sem esta distinção, a regra da lista repetida dava a
    `premodern-igg` a um 5-0 de 08/09 em vez da lista mais recente do mesmo
    piloto, que é a que ele escolheu.
    """
    return (row["event_tier"] == "Presencial"
            or valor_classificacao(row["placement"]) < SEM_CLASSIFICACAO)


def _linhas(con, ids):
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    return list(con.execute(
        "SELECT id, source, format, event_name, event_date, player, placement, "
        "url, content_hash, event_tier, event_players "
        "FROM decklists WHERE id IN (%s)" % ph, list(ids)))


def _repeticoes(con, linhas) -> dict[str, int]:
    """`content_hash -> quantas vezes essa MESMA lista foi um resultado`.

    **Conta na BASE e não só entre as candidatas**, e isso é deliberado: a
    proveniência (`_prov_de`) já contava assim, e duas contagens da mesma coisa
    discordam um dia qualquer — uma lista podia ganhar o desempate com «1
    resultado» e a ficha ao lado dizer «3 resultados», no mesmo ecrã. É a lição
    do `event_tier` aplicada a um número que a página mostra.
    """
    return _conta_hash(con, linhas, e_resultado)


def _vitorias(con, linhas) -> dict[str, int]:
    """`content_hash -> quantas vezes essa MESMA lista VENCEU`.

    É esta — e não a contagem de resultados — que decide o desempate, e a razão
    está nas palavras dele: *"se o MESMO piloto **ganhou** mais de uma vez com a
    MESMA lista, essa ganha a um resultado único melhor"*. **Ganhar é vencer.**

    Medido a 2026-10-04: com a contagem de RESULTADOS, três 9-16 do mesmo
    jogador ganhavam a um 5-8 — e no Esper Blink isso afastava a escolha da
    dele, que foi o 5-8 (*"Challenge 16 de 29/09, 5-8 de 45, meanfannypack"*).
    Três nonos lugares não são três vitórias. Com vitórias, o caso que originou
    a regra continua a valer ao exemplar: a lista do Cloud tem **três primeiros
    lugares presenciais** sem mudar uma vírgula.

    A contagem de resultados fica — é ela que a ficha mostra (*"a MESMA lista 3
    vezes"*), que é informação honesta sobre a lista.
    """
    return _conta_hash(con, linhas, lambda r: valor_classificacao(r["placement"]) == 1)


def _conta_hash(con, linhas, conta) -> dict[str, int]:
    hs = {r["content_hash"] for r in linhas if r["content_hash"]}
    fmts = {r["format"] for r in linhas}
    if not hs or not fmts:
        return {}
    ph, pf = ",".join("?" * len(hs)), ",".join("?" * len(fmts))
    out: dict[str, int] = {}
    for r in con.execute(
            "SELECT content_hash h, placement, event_tier FROM decklists "
            "WHERE content_hash IN (%s) AND format IN (%s)" % (ph, pf),
            [*hs, *fmts]):
        if conta(r):
            out[r["h"]] = out.get(r["h"], 0) + 1
    return out


def _chave_ordem(r, reps: dict[str, int], usar: set[str]):
    """A chave de ordenação de uma candidata — menor é melhor.

    Os critérios entram **apenas se estiverem na regra em vigor**: tirar um
    critério do config tem de o tirar da decisão, senão a regra escrita no
    ficheiro deixava de descrever o que o código faz.
    """
    k = []
    if "tier" in usar:
        k.append(peso_tier(r["event_tier"]))
    if "campo" in usar:
        k.append(-(r["event_players"] or 0))
    if "repetida" in usar:
        k.append(-reps.get(r["content_hash"] or "", 0))
    if "classificacao" in usar:
        k.append(valor_classificacao(r["placement"]))
    if "data" in usar:
        # A data mais recente primeiro: as datas são `AAAA-MM-DD`, por isso a
        # ordem de texto é a ordem cronológica, e inverte-se negando a
        # comparação — não há `-` para uma cadeia de caracteres.
        k.append(_data_inversa(r["event_date"]))
    if "jogador" in usar:
        k.append((r["player"] or "").strip().lower())
    k.append(int(r["id"] or 0))     # último recurso: sempre determinista
    return tuple(k)


def _data_inversa(d) -> str:
    """Uma chave de texto que ordena as datas da mais recente para a mais antiga."""
    s = str(d or "")
    # complemento dígito a dígito: '9'-x. Mantém a ordem lexicográfica invertida
    # sem precisar de converter para número (as datas podem vir incompletas).
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in s)


def proveniencia(con, decklist_id: int) -> dict | None:
    """O que a página mostra SEMPRE, à vista: jogador, evento, data, jogadores,
    classificação e o URL da fonte. Lido da base **uma vez**, para ser gravado.

    Ele vai sleevar a partir disto e tem de poder ver de onde veio.
    """
    r = con.execute(
        "SELECT id, source, format, event_name, event_date, player, placement, "
        "url, content_hash, event_tier, event_players "
        "FROM decklists WHERE id = ?", (int(decklist_id),)).fetchone()
    if r is None:
        return None
    return _prov_de(r, con)


def _prov_de(r, con=None) -> dict:
    prov = {
        "decklist_id": r["id"],
        "jogador": _limpo(r["player"]),
        "evento": _limpo(r["event_name"]),
        "data": r["event_date"],
        "jogadores": r["event_players"] or None,
        "tier": r["event_tier"],
        "classificacao": (str(r["placement"]).strip() or None) if r["placement"] else None,
        "url": r["url"] or None,
        "fonte": r["source"],
        "content_hash": r["content_hash"],
    }
    # O NOME DO ARQUÉTIPO NÃO ENTRA NA PROVENIÊNCIA, de propósito. A coluna
    # `decklists.arquetipo_fonte` tem UM leitor em todo o vault — o
    # `mtgvault.nomes`, que faz a VOTAÇÃO — e há um teste que varre o código à
    # procura de um segundo (`test_nomes_arquetipo.
    # caso_a_pergunta_do_nome_vive_num_sitio_so`). Esse teste apanhou-me aqui: ler
    # o nome que a fonte deu a UMA lista e mostrá-lo ao lado do deck era um
    # segundo nome a discordar do votado num dia qualquer. O nome do deck vem do
    # `decks_de_evento` do config, que o preencheu pela votação.
    if con is not None and r["content_hash"]:
        # Quantas vezes esta MESMA lista foi um resultado, em qualquer evento do
        # formato — é a prova da regra da «repetida», e grava-se porque a base
        # poda as decklists aos 30 dias.
        iguais = list(con.execute(
            "SELECT event_name, event_date, player, placement, event_tier, "
            "event_players FROM decklists WHERE content_hash = ? AND format = ?",
            (r["content_hash"], r["format"])))
        res = [x for x in iguais if e_resultado(x)]
        prov["repetida"] = len(res)
        # As VITÓRIAS à parte dos resultados: é a contagem que DECIDE o
        # desempate (`_vitorias`), e a ficha mostra as duas porque dizem coisas
        # diferentes — «a mesma lista em 3 resultados» e «venceu 3 vezes» não é
        # a mesma afirmação, e foi a confusão entre elas que, medida a 04/10,
        # punha três 9-16 à frente de um 5-8.
        prov["vitorias"] = sum(
            1 for x in iguais if valor_classificacao(x["placement"]) == 1)
        if len(res) > 1:
            prov["repeticoes"] = [
                {"evento": _limpo(x["event_name"]), "data": x["event_date"],
                 "jogador": _limpo(x["player"]),
                 "classificacao": (str(x["placement"]).strip() or None)
                                  if x["placement"] else None,
                 "jogadores": x["event_players"] or None}
                for x in sorted(res, key=lambda x: str(x["event_date"] or ""))]
    return prov


def _limpo(s) -> str:
    """O mtgtop8 serve nomes com escapes de HTML/URL por dentro
    (`Jind%3Fich Pol%E1k`, `Wiaczas%26%23322%3Baw`). Não se inventa o nome certo
    — mostra-se o que a fonte deu, sem o lixo que dá para tirar com segurança."""
    t = str(s or "").strip()
    return t


def texto_prov(prov: dict | None) -> str:
    """A proveniência numa linha, para a nota da caixa e para o CLI."""
    if not prov:
        return ""
    p = []
    if prov.get("jogador"):
        p.append(prov["jogador"])
    cl = prov.get("classificacao")
    if cl:
        p.append(f"{cl}.º" if cl.isdigit() else cl)
    ev = prov.get("evento") or ""
    if ev:
        p.append(ev)
    if prov.get("data"):
        p.append(prov["data"])
    if prov.get("jogadores"):
        p.append(f"{prov['jogadores']} jogadores")
    rep = prov.get("repetida") or 0
    if rep > 1:
        p.append(f"a MESMA lista {rep}x")
    return " · ".join(p)


def candidatas(con, fmt: str, ids) -> list[dict]:
    """As candidatas de um deck, da melhor para a pior, com a proveniência.

    Não filtra nada: é a lista por onde se CONFERE a escolha.
    """
    linhas = _linhas(con, ids)
    reps = _vitorias(con, linhas)
    usar = set(criterios())
    linhas.sort(key=lambda r: _chave_ordem(r, reps, usar))
    return [dict(_prov_de(r), _row=r) for r in linhas]


def dentro_da_janela(fmt: str, linhas) -> tuple[list, list, str | None]:
    """Parte as candidatas pela janela do consenso. `(dentro, fora, desde)`.

    Quem responde *"há janela neste formato?"* é o `sources.consenso_desde`, que
    é o MESMO sítio que o resto do vault usa desde 2026-10-03 — incluindo a
    excepção do premodern (`consenso.excepcoes`), que joga sets de 2003 e para
    quem o Reality Fracture não quer dizer nada.
    """
    desde = sources.consenso_desde(fmt)
    if not desde:
        return list(linhas), [], None
    dentro = [r for r in linhas if (r["event_date"] or "") >= desde]
    fora = [r for r in linhas if (r["event_date"] or "") < desde]
    return dentro, fora, desde


def escolher(con, fmt: str, ids) -> dict:
    """A melhor lista real deste deck, e a alternativa quando ela faz falta.

    Devolve `{escolhida, alternativa, aviso, porque, n_candidatas, n_na_janela}`.
    `escolhida` é `None` quando não há candidata nenhuma — e isso é uma resposta,
    não um buraco.

    A ALTERNATIVA é a regra 5 dele, à letra: *"se a melhor presencial for
    ANTERIOR à janela, NÃO a escondas e NÃO a descartes: mostra-a com a data bem
    visível e uma frase a dizer que é anterior ao Reality Fracture, e põe ao lado
    a melhor lista DENTRO da janela, para ele escolher."* Mostrar as duas é
    honesto; escolher por ele às escuras não é.
    """
    linhas = _linhas(con, ids)
    if not linhas:
        return {"escolhida": None, "alternativa": None, "aviso": "",
                "porque": "não há uma única lista desta identidade na base",
                "n_candidatas": 0, "n_na_janela": 0}
    usar = set(criterios())
    reps = _vitorias(con, linhas)
    com_janela = "janela" in usar
    dentro, fora, desde = (dentro_da_janela(fmt, linhas) if com_janela
                           else (list(linhas), [], None))

    universo, aviso = dentro, ""
    if not dentro:
        universo = linhas
        if desde:
            aviso = (f"nenhuma lista desde {desde} (a janela do consenso) — "
                     f"a escolha é da história toda")
    universo = sorted(universo, key=lambda r: _chave_ordem(r, reps, usar))
    melhor = universo[0]

    alt = None
    if fora:
        fora_ord = sorted(fora, key=lambda r: _chave_ordem(r, reps, usar))
        cand = fora_ord[0]
        # Só vale como alternativa se for MELHOR pela mesma régua — senão é só
        # uma lista velha, e ao lado da escolhida não acrescentava nada.
        if (_chave_ordem(cand, reps, usar) < _chave_ordem(melhor, reps, usar)
                and cand["id"] != melhor["id"]):
            alt = dict(_prov_de(cand, con))
            alt["porque"] = (
                f"é a melhor lista do deck em papel, mas é de {cand['event_date']} "
                f"— ANTERIOR ao Reality Fracture (a janela começa em {desde}). "
                "Fica ao lado para ele escolher: a escolhida é a melhor DENTRO "
                "da janela.")

    porque = _porque(melhor, reps, usar, desde, len(dentro), len(linhas))
    return {"escolhida": dict(_prov_de(melhor, con)), "alternativa": alt,
            "aviso": aviso, "porque": porque,
            "n_candidatas": len(linhas), "n_na_janela": len(dentro)}


def _porque(r, reps, usar, desde, n_dentro, n_total) -> str:
    """Porque é que esta lista ganhou — em português, para a página."""
    p = []
    if r["event_tier"] == "Presencial":
        p.append("presencial")
    else:
        p.append(f"o online mais importante ({r['event_tier'] or 'sem tier'})"
                 " — sem presencial elegível")
    if r["event_players"]:
        p.append(f"o maior campo ({r['event_players']} jogadores)")
    vit = reps.get(r["content_hash"] or "", 0)
    if vit > 1:
        p.append(f"a MESMA lista venceu {vit} vezes")
    cl = valor_classificacao(r["placement"])
    if cl < SEM_CLASSIFICACAO:
        p.append(f"a melhor classificação ({r['placement']})")
    else:
        p.append("a mais recente (as Challenges não trazem classificação)")
    cauda = f"{n_dentro} de {n_total} candidatas"
    if desde:
        cauda += f" desde {desde}"
    return "escolhida por: " + ", ".join(p) + f" — {cauda}"


def cartas(con, decklist_id: int) -> list[list]:
    """As cartas de uma decklist, DA BASE — nunca de memória.

    Devolve `[[board, nome, q], ...]` na forma que o `padrao`/`loadout` já leem,
    com o nome canonizado pelo `scryfall.chave` (a frente de uma dupla face),
    que é a chave por que a posse e os preços indexam desde 2026-10-04.
    """
    rows = list(con.execute(
        "SELECT card_name nm, board b, SUM(quantity) q FROM decklist_cards "
        "WHERE decklist_id = ? GROUP BY card_name, board", (int(decklist_id),)))
    return padrao.juntar([["side" if r["b"] == "side" else "main",
                           scryfall.chave(r["nm"]), int(r["q"])] for r in rows])


# ---------------------------------------------------------------------------
# Escrever
# ---------------------------------------------------------------------------
def registo_de_evento(cfg: dict, chave: str) -> dict | None:
    """O registo de lista-de-evento desta caixa/deck, ou None.

    Vive em `listas_escolhidas` — o MESMO sítio da lista padrão de 2026-09-20 —
    e distingue-se por ter o bloco `evento`. Uma chave nova ao lado era um
    segundo sítio a responder *"qual é a lista que ele fixou"*.
    """
    rec = (cfg.get("listas_escolhidas") or {}).get(chave)
    return rec if rec and rec.get("evento") else None


def fixar(cfg: dict, con, chave: str, decklist_id: int, *,
          nome: str | None = None, formato: str | None = None,
          alternativa: dict | None = None, porque: str = "",
          consenso_antes: list | None = None, consenso_nota: str = "",
          quando: str | None = None,
          nota: str | None = None, arquetipo: str | None = None,
          caixa: bool = True) -> dict:
    """Fixa a lista de evento real de uma caixa (ou de um deck do meta).

    Para uma CAIXA reutiliza o `padrao.fixar` — a caixa passa a
    `fonte: "escolhido"` com o que tinha em `_antes` — porque esse caminho já
    está testado e já é lido pelo motor, pela página e pelo CLI. Escrever um
    quinto `fonte` ao lado era abrir um segundo despacho para a mesma pergunta.

    `consenso_antes` é a lista de consenso que a caixa mostrava até aqui: guarda-se
    com a data e a razão da troca (**nada se apaga**, regra dele de 2026-09-09),
    para ele poder comparar a lista real com a média.
    """
    cs = cartas(con, decklist_id)
    if not cs:
        raise ValueError(f"a decklist {decklist_id} não tem cartas na base")
    prov = proveniencia(con, decklist_id)
    if prov is None:
        raise ValueError(f"a decklist {decklist_id} não existe")
    quando = quando or date.today().isoformat()
    origem = texto_prov(prov) + (f" · {prov['url']}" if prov.get("url") else "")

    # O CONSENSO GUARDADO SOBREVIVE A UMA SEGUNDA PASSAGEM, e isto custou duas.
    # O `padrao.fixar` **substitui o registo inteiro** por um dicionário novo (é
    # ele que decide a forma de uma lista padrão), por isso um `_consenso_anterior`
    # escrito na primeira passagem desaparecia na segunda — e era recriado com a
    # lista de evento que a primeira acabara de fixar. A média que ele quer poder
    # comparar com a lista real ficava substituída por uma cópia dela.
    antigo = (cfg.get("listas_escolhidas") or {}).get(chave) or {}
    guardado = antigo.get("_consenso_anterior")

    if caixa:
        rec = padrao.fixar(cfg, chave, cs, origem, quando=quando, nome=nome)
    else:
        rec = {"nome": nome or chave, "padrao": True, "origem": origem,
               "formato": formato, "escolhido_em": quando, "cards": padrao.juntar(cs)}
        cfg.setdefault("listas_escolhidas", {})[chave] = rec
    rec["evento"] = prov
    rec["fonte_decklist"] = prov["decklist_id"]
    if formato:
        rec["formato"] = formato
    if arquetipo:
        rec["arquetipo"] = arquetipo
    if porque:
        rec["porque"] = porque
    if alternativa:
        rec["alternativa"] = alternativa
    if nota:
        rec["nota"] = nota
    # `consenso_antes = []` é diferente de `None`: o primeiro quer dizer *"não
    # havia consenso nenhum"* (a `premodern-igg`, que estava trancada por ter 4
    # listas e um mínimo de 5) e tem de ficar GRAVADO como tal — senão a passagem
    # seguinte lia o bloco como ausente e gravava lá a lista já trocada.
    if guardado:
        rec["_consenso_anterior"] = guardado
    elif consenso_antes is not None:
        rec["_consenso_anterior"] = {
            "em": quando,
            "razao": ("a lista desta caixa era o CONSENSO de muitas listas. O André "
                      "decidiu a 2026-10-04 ao fim do dia: *\"as outras quero que "
                      "esquecas as decklists e vamos focar nas decklists baseadas em "
                      "eventos reais\"*. Fica aqui para ele poder comparar a lista "
                      "real com a media — nada se apaga."),
            "cards": [list(x) for x in consenso_antes],
            # A nota vive DENTRO do bloco (e não solta ao lado) por causa da
            # idempotência: um campo solto era reescrito a cada passagem e ficava
            # a dizer *"lista padrão fixada em …"* — a nota da lista NOVA — em vez
            # da do consenso que ele quer poder comparar.
            "nota": consenso_nota,
        }
    return rec


def json_compacto(x) -> str:
    return json.dumps(x, ensure_ascii=False)
