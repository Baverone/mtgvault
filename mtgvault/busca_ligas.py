"""A LIGA É FONTE DE BUSCA, NUNCA DE CONTAGEM (André, 2026-10-13, à letra).

*"as ligas servem apenas para procurar listas de decks novos, como a Kasmina, ou
se a amostra de decks que procuramos e baixa"*.

Até aqui o `metagame_fontes.<fmt>.ligas` era um interruptor de DUAS posições:
`false` (a liga nem se guarda) ou `true` (a liga guarda-se E conta para a
percentagem do formato). Ele descreveu uma TERCEIRA coisa, e é esta: com
`"ligas": "busca"` a liga **nunca** entra na contagem — o aviso de 05/10 continua
certo, um 5-0 de liga não tem classificação nem tamanho de campo e somá-lo a uma
Challenge estraga a percentagem —, mas **colhe-se e guarda-se quando há um ALVO
NOMEADO que a justifique**. Dois casos, e só dois:

  (a) uma carta NOVA que ele nomeou — é a VIGIA DE CARTAS de 2026-09-26
      (`cartas_vigiadas`), que já abria as três portas para as listas com a
      carta. Não se fez uma segunda: a Kasmina É esse caso;
  (b) um deck que ele SEGUE e cuja amostra fora das ligas é BAIXA na janela do
      consenso (`ligas_busca.amostra_baixa_max`). É o que este módulo responde.

E um terceiro, que não é novo mas tinha de continuar vivo: um JOGADOR vigiado
(`watched`, `kind='mtgo_player'`) num formato de busca. O CesarMerjan joga em
ligas e a vigia dele (06/10) só funciona porque as ligas de Modern se guardavam;
com a busca, a lista dele é um alvo nomeado pelo nome, e passa.

**O DECK SEGUIDO, e porque é por deck e não pelo universo.** Medido a 13/10: a
mediana do tamanho de um arquétipo é **2 listas** em todos os formatos (modern
183 arquétipos / 2 151 listas, pioneer 84/485, legacy 121/849, premodern 81/549)
— um limiar sobre todos os arquétipos disparava para quase todos e não
discriminava nada. Os decks seguidos são os que o config NOMEIA, e a identidade
de cada um é a de sempre — CARTAS, nunca a etiqueta do clustering (a regra de
ouro de 02/10): as caixas vivas do formato (`assinatura`/`reserva_assinatura`,
com o `todas` e o `sem`), as versões vivas do `decks_por_formato`
(`meta.cartas`, em conjunção) e a carta-chave do formato (`criterio.carta`).

**A amostra conta pelo `sources.counting_sql`**, a mesma régua de todo o site:
num formato de busca a liga já não está nos tiers, por isso "fora das ligas" é
exactamente "o que conta". Uma segunda regra ao lado era o `event_tier` outra
vez.

**Nada disto apaga nada.** O `analysis.prune_leagues` deixa de podar as ligas de
um formato de busca: o que lá está guardado é material de busca e o
`prune_decklists(30)` envelhece-o como envelhece tudo — apagar 500 listas de
Modern no dia em que a regra entrou era o contrário de *nada se apaga*.
"""
from __future__ import annotations

import sqlite3
import time

from . import scryfall, sources

#: O valor do `metagame_fontes.<fmt>.ligas` que quer dizer «busca».
BUSCA = "busca"

#: Abaixo (ou igual) disto, a amostra de um deck seguido é BAIXA — conta-se em
#: listas que CONTAM, na janela do consenso. Medido a 13/10: o Grinding Station
#: tinha 7 fora das ligas e o Mox Opal de Modern 159; entre os decks seguidos de
#: hoje, os que ficam abaixo e acima estão em `ligas_busca._medido`.
LIMIAR_OMISSAO = 10

#: Quanto tempo (s) se guarda a resposta «que alvos tem este formato?» durante
#: uma colheita. O `store_decklist` é chamado uma vez por lista (centenas por
#: página de liga) e a pergunta faz uma consulta por deck seguido; uma colheita
#: dura minutos e um deck não cruza o limiar a meio dela por causa de uma liga
#: (as ligas não contam para a amostra). O `esquecer()` limpa-a.
TTL_S = 600

_CACHE: dict = {}


def esquecer() -> None:
    """Limpa a cache dos alvos — os testes chamam-no entre casos."""
    _CACHE.clear()


def modo(fmt: str | None) -> str:
    """`"conta"`, `"busca"` ou `"fora"` — o que o config diz das ligas."""
    fmt = (fmt or "").lower()
    sec = sources.config().get("metagame_fontes") or {}
    v = sources.DEFAULT_METAGAME_RULES.get("ligas")
    v = (sources.DEFAULT_METAGAME_BY_FORMAT.get(fmt) or {}).get("ligas", v)
    v = (sec.get("_default") or {}).get("ligas", v)
    v = (sec.get(fmt) or {}).get("ligas", v)
    if v == BUSCA:
        return "busca"
    return "conta" if v is True else "fora"


def e_busca(fmt: str | None) -> bool:
    return modo(fmt) == "busca"


def limiar(cfg: dict | None = None) -> int:
    cfg = sources.config() if cfg is None else cfg
    try:
        return int((cfg.get("ligas_busca") or {}).get("amostra_baixa_max",
                                                      LIMIAR_OMISSAO))
    except (TypeError, ValueError):
        return LIMIAR_OMISSAO


def _lista(x) -> list[str]:
    if isinstance(x, str):
        x = [x]
    return [str(v) for v in (x or []) if str(v).strip()]


def seguidos(fmt: str, cfg: dict | None = None) -> list[dict]:
    """Os decks que ele SEGUE neste formato, cada um com a identidade em cartas.

    `{id, nome, origem, cartas, todas, sem}`. Duas entradas com a mesma
    identidade são uma só (a caixa `pioneer` e a versão Abzan apontam as duas
    para o Greasefang — contar a mesma pergunta duas vezes não a torna maior).
    """
    from . import caixas as _caixas, versoes as _versoes     # noqa: PLC0415
    cfg = sources.config() if cfg is None else cfg
    fmt = (fmt or "").lower()
    out: list[dict] = []
    vistos: set = set()

    def junta(id_, nome, origem, cartas, todas, sem):
        cartas = _lista(cartas)
        if not cartas:
            return
        # Com UMA carta, «todas» e «basta uma» são a mesma pergunta.
        chave = (tuple(sorted(c.lower() for c in cartas)),
                 bool(todas) and len(cartas) > 1,
                 tuple(sorted(c.lower() for c in _lista(sem))))
        if chave in vistos:
            return
        vistos.add(chave)
        out.append({"id": id_, "nome": nome, "origem": origem,
                    "cartas": cartas, "todas": bool(todas), "sem": _lista(sem)})

    # As VERSÕES primeiro: quando uma caixa e uma versão têm a mesma identidade,
    # fica o nome da versão — a caixa `modern` chama-se «Pinnacle Affinity» e a
    # identidade de reserva dela é o Oswald, e um «Pinnacle Affinity (0 listas)»
    # numa linha de busca dizia o contrário do que se está a procurar.
    for v in _versoes.versoes(fmt, cfg):
        junta(v.get("id"), v.get("nome") or v.get("id"), "versao",
              _versoes.cartas_do_meta(v), True, None)
    for c in _caixas.do_config(cfg):
        if (c.get("formato") or "").lower() != fmt:
            continue
        if c.get("assinatura"):
            junta(f"caixa:{c.get('slot')}", c.get("nome") or c.get("slot"),
                  "caixa", c.get("assinatura"), c.get("assinatura_todas"),
                  c.get("assinatura_sem"))
        elif c.get("reserva_assinatura"):
            junta(f"caixa:{c.get('slot')}", c.get("nome") or c.get("slot"),
                  "caixa", c.get("reserva_assinatura"),
                  c.get("reserva_assinatura_todas", c.get("assinatura_todas")),
                  c.get("reserva_assinatura_sem"))
    crit = ((cfg.get("decks_por_formato") or {}).get(fmt) or {}).get("criterio")
    if isinstance(crit, dict) and crit.get("carta"):
        junta(f"criterio:{fmt}", f"joga {crit['carta']}", "criterio",
              [crit["carta"]], False, None)
    return out


def amostra(con: sqlite3.Connection, fmt: str, deck: dict) -> int:
    """Quantas listas QUE CONTAM (fora das ligas, na janela) jogam este deck."""
    return len(sources.ids_por_assinatura(
        con, fmt, deck["cartas"], todas=deck["todas"], sem=deck["sem"],
        so_que_contam=True))


def jogadores_vigiados(con: sqlite3.Connection, fmt: str) -> set[str]:
    try:
        return {(r[0] or "").strip().lower() for r in con.execute(
            "SELECT key FROM watched WHERE active = 1 AND kind = 'mtgo_player' "
            "AND lower(format) = ?", ((fmt or "").lower(),))}
    except sqlite3.OperationalError:
        return set()


def alvos(con: sqlite3.Connection, fmt: str, cfg: dict | None = None,
          fresco: bool = False) -> dict:
    """O retrato da busca num formato: os decks seguidos com a amostra de cada
    um, quais estão BAIXOS e os jogadores vigiados. `{}`-vazio fora da busca."""
    fmt = (fmt or "").lower()
    if not e_busca(fmt):
        return {"formato": fmt, "busca": False, "decks": [], "baixos": [],
                "jogadores": [], "limiar": limiar(cfg)}
    chave = (id(con), fmt)
    agora = time.time()
    if not fresco and chave in _CACHE and agora - _CACHE[chave][0] < TTL_S:
        return _CACHE[chave][1]
    lim = limiar(cfg)
    decks = []
    for d in seguidos(fmt, cfg):
        n = amostra(con, fmt, d)
        decks.append({**d, "listas": n, "baixa": n <= lim})
    res = {"formato": fmt, "busca": True, "limiar": lim, "decks": decks,
           "baixos": [d for d in decks if d["baixa"]],
           "jogadores": sorted(jogadores_vigiados(con, fmt))}
    _CACHE[chave] = (agora, res)
    return res


def ha_alvo(con: sqlite3.Connection, fmt: str) -> bool:
    """Vale a pena abrir uma página de liga deste formato? (a parte (b) e os
    jogadores; a parte (a) é a `vigia.ha_vigia`, que o `harvest` já pergunta)."""
    a = alvos(con, fmt)
    return bool(a["baixos"] or a["jogadores"])


def _casa(deck: dict, nomes: set[str]) -> bool:
    cartas = [scryfall.chave(c).lower() for c in deck["cartas"]]
    sem = [scryfall.chave(c).lower() for c in deck["sem"]]
    if any(s in nomes for s in sem):
        return False
    if deck["todas"]:
        return all(c in nomes for c in cartas)
    return any(c in nomes for c in cartas)


def alvos_na_lista(con: sqlite3.Connection, fmt: str, cards,
                   player: str | None = None) -> list[str]:
    """Os alvos NOMEADOS que justificam guardar esta lista de liga.

    É a pergunta que o `store_decklist` faz, e vive aqui num sítio só. Devolve
    os nomes (`"Grinding Station"`, `"jogador CesarMerjan"`) — vazio quer dizer
    que a liga não tem nada a ver com o que ele procura e não se guarda.
    """
    a = alvos(con, fmt)
    if not a["busca"]:
        return []
    out = []
    jog = (player or "").strip().lower()
    if jog and jog in a["jogadores"]:
        out.append(f"jogador {player}")
    if a["baixos"]:
        nomes = {scryfall.chave(str(c[1] if len(c) >= 2 else "")).lower()
                 for c in (cards or [])}
        out += [d["nome"] for d in a["baixos"] if _casa(d, nomes)]
    return out


def texto(con: sqlite3.Connection, fmt: str) -> str:
    """Uma linha para o `daily` e o CLI — a busca diz o que está a procurar."""
    a = alvos(con, fmt, fresco=True)
    if not a["busca"]:
        return f"{fmt}: ligas {modo(fmt)}"
    bx = ", ".join(f"{d['nome']} ({d['listas']})" for d in a["baixos"]) or "nenhum"
    return (f"{fmt}: ligas só para busca — amostra baixa (≤{a['limiar']}): {bx}; "
            f"jogadores vigiados: {', '.join(a['jogadores']) or 'nenhum'}")
