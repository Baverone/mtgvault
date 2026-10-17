"""A LISTA DE FALTAS, PARA ELE PROCURAR EM GHENT (André, 2026-10-05, à letra).

(O motor. A VISTA é o `faltas.py` da raiz, que gera o `faltas.html` — o mesmo par
que o `decks.py` ↔ `mtgvault/decks_vista.py`. Os dois não se podem chamar
`faltas`: o `daily.py` importa o da raiz pelo nome.)

*"preciso tambem da lista de faltas desses decks para poder procurar em Ghent"*.
Ele joga o RC Ghent a 9-11/10 e vai andar **de pé, num pavilhão, com o telemóvel
numa mão** — a outra tem cartas. Isso é o que decide tudo o que está aqui:

* **uma linha por carta**, com o NOME grande e legível. É o nome que ele lê em voz
  alta ao balcão, e por isso é o nome que manda: a imagem é um APOIO (ele
  confirma a arte), nunca o conteúdo da linha. É exactamente ao contrário da aba
  Decks, onde a imagem é o conteúdo porque ali ele está sentado a ordenar cartas;
* **SUBTOTAL POR DECK**, que é o que lhe diz onde vale a pena gastar o tempo:
  trinta cartas de 0,30 € não pagam a volta ao pavilhão, uma de 150 € paga;
* **o que ele já tem não aparece.** Por construção: a falta é o `comprar` da
  alocação, que já desconta o que ele tem, o que está noutra caixa e o que já
  encomendou (2026-09-19). Nunca `missing` — somar `missing` era mandá-lo comprar
  o que está em casa (decisão de 2026-09-07).

O MOTOR NÃO É NOVO, e isso é deliberado: as faltas saem do `loadout.report`, que
é quem sabe as regras de material, o que está noutra caixa, as encomendas e o
tecto do playset. Uma segunda contagem ao lado dava um número diferente do que a
aba Comprar mostra, que é o defeito do `event_tier` aplicado à lista com que ele
vai gastar dinheiro.

O FORMATO POR ESCOLHER FICA À PARTE (ordem dele: *"se mostrares faltas de legacy,
e numa secao separada marcada como PROPOSTA e fora do total"*). Quem decide não é
uma lista de nomes escrita à mão: é o `sem_deck_escolhido`, que pergunta ao
modelo «um deck por formato» se aquele formato tem alguma versão escolhida. No dia
em que ele escolher o deck de Legacy, a secção desaparece sozinha.

E O PREÇO DIZ-SE PELO QUE É. O `loadout.preco_fora_da_regra` (2026-10-05) marca a
linha quando o preço não é do material que a caixa pede — ver o bloco grande
desse ficheiro. Aqui só se desenha o que ele respondeu.
"""
from __future__ import annotations

from . import arts, loadout, scryfall as _scry, versoes


def sem_deck_escolhido(fmt: str, cfg: dict | None = None) -> bool:
    """O formato entra no modelo «um deck por formato» e **não tem versão nenhuma**.

    Hoje é só o `legacy` (*"Legacy ainda nao sei"*). Não se pergunta pelo
    `por_decidir`: essa chave foi arquivada a 2026-10-05, quando o Legacy entrou
    no critério do Mox Opal — o formato deixou de estar «por decidir» para a
    PROTECÇÃO e continua sem deck escolhido para MONTAR. São duas perguntas, e
    confundi-las punha as faltas de Legacy a contar para o total no dia em que a
    primeira mudou.
    """
    return bool(versoes.do_formato(fmt, cfg)) and not versoes.versoes(fmt, cfg)


def _linha(con, s: dict, m: dict, cache: dict) -> dict:
    """Uma falta, com o que a página desenha e mais nada."""
    nm = m["nm"]
    q = m["comprar"]
    # DESDE 2026-10-17 o `unit` da linha JÁ É o da impressão que serve: o 1.º
    # anúncio de um vendedor profissional, na língua e no acabamento da regra
    # (`loadout.preco_pro`). O mínimo do motor (`card_price`, entre impressões e
    # sem o crivo da caixa) fica em `unit_motor` e é o terceiro total da página.
    unit = m.get("unit")
    unit_motor = m.get("unit_motor", unit)
    regra = loadout.regra_da_carta(con, s, nm, cache)
    fin = m.get("price_finish") or ("foil" if regra.get("acabamento") == "foil"
                                     else "nonfoil")
    pro = "sid_ref" in m          # a régua do vendedor profissional valeu
    if pro:
        # A IMAGEM É DA IMPRESSÃO QUE ELE VAI COMPRAR: a do anúncio que fez o
        # preço; sem anúncio, a mais barata do motor (e a linha diz porquê).
        sid = m.get("sid_ref") or loadout.impressao_mais_barata(con, nm, fin, cache=cache)
        legal = unit
    else:
        # Base sem a régua profissional (ainda não recolhida): o caminho de
        # 2026-10-05 — o motor ao lado da mais barata que a caixa ACEITA.
        serve = loadout.mais_barata_que_serve(con, regra, nm, fin, cache)
        sid = serve["sid"] or loadout.impressao_mais_barata(con, nm, fin, cache=cache)
        legal = serve["unit"] if serve["unit"] is not None else unit
    # A ART QUE ELE PROCURA (André, 2026-10-13): *"se for de uma carta que eu ja
    # tenho, a Art tem que ser a mesma"*. O preço de REFERÊNCIA da linha passa a
    # ser o da impressão que ele quer — a que escolheu em `Arts que procuro/`, ou
    # a que já tem — e só sem nenhuma das duas fica a regra genérica (a mais
    # barata que serve a caixa). A linha DIZ de qual veio (`origem_preco`): um
    # preço de outra art apresentado como se fosse o dele era o erro das duas
    # verdades. Quem decide é o `arts.preferida`, num sítio só.
    pref = arts.preferida(con, nm, cache)
    # A art que ele procura também vale pelo 1.º anúncio profissional (só essa
    # impressão, na língua da regra); sem anúncio dela, cai na regra e di-lo.
    if not pref.get("sid"):
        p_arte = None
    elif pro:
        p_arte = loadout.preco_pro(con, regra, nm, fin, cache, sid=pref["sid"])["unit"]
    else:
        p_arte = arts.preco(con, pref, fin, cache)
    if pref["origem"] in ("escolhida", "a_que_tens") and p_arte is not None:
        origem, ref, sid = pref["origem"], p_arte, pref["sid"]
    else:
        origem, ref = "regra", legal
    return {
        "nm": nm, "q": q, "unit": unit,
        # `total` é o MÍNIMO DO MOTOR (o terceiro número da página); o que se
        # paga é o `total_serve`/`total_ref`.
        "unit_motor": unit_motor,
        "total": round((unit_motor or 0) * q, 2),
        "cm_url": m.get("cm_url") or loadout.link_cardmarket(nm),
        "unit_serve": legal, "total_serve": round((legal or 0) * q, 2),
        "unit_ref": ref, "total_ref": round((ref or 0) * q, 2),
        "origem_preco": origem,
        "arte": {"origem": pref["origem"], "set": pref["set"], "num": pref["num"],
                 # A art que ele quer mas que não está cotada neste acabamento:
                 # cai na regra e a linha di-lo, em vez de somar o preço de outra.
                 "sem_preco": (pref["origem"] in ("escolhida", "a_que_tens")
                               and p_arte is None),
                 "opcoes": [f"{o['set'].upper()} #{o['num']}"
                            for o in pref["opcoes"]]
                 if pref["origem"] == "ambigua" else []},
        "sid": sid,
        "board": m.get("board") or "main",
        "req": m.get("req_compra") or loadout.requisito_material(s),
        "aviso": m.get("preco_aviso"),
        "urgencia": m.get("urgencia"),
    }


def vista(con, rep: dict, cfg: dict | None = None) -> dict:
    """`{decks, proposta, formatos, totais}` — tudo o que a página desenha.

    `rep` é o `loadout.report` e passa-se de fora de propósito: a página das
    faltas é a quarta a lê-lo na mesma corrida (Início, Deckboxes, Arrumação), e
    é a decisão de 2026-09-24 — *"dois relatórios eram duas respostas à mesma
    pergunta"*.
    """
    cache: dict = {}
    decks, proposta = [], []
    for s in rep["slots"]:
        ms = [m for m in s["missing"] if m.get("comprar", 0) > 0]
        if not ms:
            continue
        linhas = [_linha(con, s, m, cache) for m in ms]
        linhas.sort(key=lambda l: (-l["total_ref"], l["nm"]))
        fmt = s.get("formato") or ""
        d = {
            "slot": s["slot"], "nome": s["nome"], "formato": fmt,
            "req": loadout.requisito_material(s),
            "cartas": len({l["nm"] for l in linhas}),
            "copias": sum(l["q"] for l in linhas),
            "valor": round(sum(l["total"] for l in linhas), 2),
            "valor_serve": round(sum(l["total_serve"] for l in linhas), 2),
            "valor_ref": round(sum(l["total_ref"] for l in linhas), 2),
            "sem_preco": sum(l["q"] for l in linhas if l["unit"] is None),
            "avisos": sum(1 for l in linhas
                          if (l["aviso"] or {}).get("grau") == "aviso"),
            "proposta": sem_deck_escolhido(fmt, cfg),
            "linhas": linhas,
        }
        (proposta if d["proposta"] else decks).append(d)
    decks.sort(key=lambda d: -d["valor_ref"])
    proposta.sort(key=lambda d: -d["valor_ref"])

    def soma(ds):
        # As CARTAS contam-se por NOME e sem repetir entre decks: a mesma Swords
        # to Plowshares a faltar em três caixas é UMA carta para procurar e TRÊS
        # cópias para comprar. Somar os `cartas` dos decks dava o número de
        # linhas, que é outra coisa — e era o que não batia com a contagem dele.
        nms = {l["nm"] for d in ds for l in d["linhas"]}
        return {"decks": len(ds), "cartas": len(nms),
                "linhas": sum(len(d["linhas"]) for d in ds),
                "copias": sum(d["copias"] for d in ds),
                "valor": round(sum(d["valor"] for d in ds), 2),
                "valor_serve": round(sum(d["valor_serve"] for d in ds), 2),
                "valor_ref": round(sum(d["valor_ref"] for d in ds), 2),
                "sem_preco": sum(d["sem_preco"] for d in ds),
                "avisos": sum(d["avisos"] for d in ds),
                "regua": rep.get("regua_faltas") or "motor",
                "por_origem": {o: sum(1 for d in ds for l in d["linhas"]
                                      if l["origem_preco"] == o)
                               for o in ("escolhida", "a_que_tens", "regra")}}

    fmts = sorted({d["formato"] for d in decks if d["formato"]})
    return {"decks": decks, "proposta": proposta, "formatos": fmts,
            "totais": soma(decks), "totais_proposta": soma(proposta),
            "staples": staples(con, rep),
            # A LISTA DAS ARTS POR ESCOLHER (2026-10-13): *"pede-me sempre que
            # faltar as arts das cartas"*. Vive nesta página porque é a página das
            # compras, e uma art só importa a quem a vai comprar.
            "arts": arts.relatorio(con, cfg, cache, a_comprar={
                l["nm"] for d in decks + proposta for l in d["linhas"]})}


def staples(con, rep: dict) -> dict:
    """A COLECÇÃO DE STAPLES DE PREMODERN (André, 2026-10-17): *"quero ter o
    máximo de staples possível"*. As que lhe faltam entram nas faltas numa
    secção PRÓPRIA, com o subtotal dela e FORA do total dos decks — o total dos
    decks é o «fechar tudo», e uma colecção que se vai enchendo não é um deck
    por fechar.

    A CONTA (b) desde 2026-10-17 à noite (*"as cartas do deck servem apenas para
    o deck"*): todas as staples, com cópias PRÓPRIAS — uma que também está no
    Stiflenought ou no UW Replenish entra aqui por inteiro, e o que ele tem só
    desconta a parte que sobra depois dos decks (`copias_para_staples`). A (a)
    fica ao lado, em números."""
    from . import premodern                                    # noqa: PLC0415
    if not premodern.caixas_do_formato(rep):
        return {"linhas": [], "cartas": 0, "copias": 0, "valor": 0.0,
                "sem_preco": 0, "contas": None, "alvos": []}
    o = premodern.outros(con, rep)
    valores = premodern.valores_outros(con, rep, o)
    tem = premodern.copias_para_staples(con, rep)
    nos = o.get("nos_decks") or {}
    linhas = []
    for nm, e in o["cartas"].items():
        q = max(0, e["q"] - tem.get(_scry.chave(nm), 0))
        if not q:
            continue
        v = valores.get(nm) or {}
        u = v.get("unit")
        linhas.append({"nm": nm, "q": q, "unit": u, "unit_ref": u,
                       "total": round((u or 0) * q, 2),
                       "total_ref": round((u or 0) * q, 2),
                       "total_serve": round((u or 0) * q, 2),
                       "sid": v.get("sid"), "set": v.get("set"),
                       "arquetipos": e["arquetipos"], "pct": e["pct"],
                       "no_deck": nos.get(nm),
                       "req": "PT · ≤SCG", "board": "main",
                       "cm_url": v.get("cm_url") or loadout.link_cardmarket(nm),
                       "aviso": ({"grau": "aviso", "motivos": ["sem_pro"],
                                  "frase": v.get("motivo")} if u is None else None),
                       "origem_preco": "regra", "rl": bool(v.get("rl")),
                       "arte": {"origem": "regra", "set": None, "num": None,
                                "sem_preco": False, "opcoes": []}})
    linhas.sort(key=lambda l: (-l["total_ref"], l["nm"]))
    return {"linhas": linhas, "cartas": len(linhas),
            "copias": sum(l["q"] for l in linhas),
            "valor": round(sum(l["total_ref"] for l in linhas), 2),
            "sem_preco": sum(l["q"] for l in linhas if l["unit"] is None),
            "contas": premodern.contas_staples(o, valores),
            "regra": o.get("regra") or "a",
            "alvos": [a["nome"] for a in o["alvos"]], "top": o.get("top")}


def texto_totais(t: dict) -> str:
    """A linha dos totais, a MESMA no daily e no CLI (2026-10-16).

    O número à cabeça é o `valor_ref` — o preço da impressão que ele vai mesmo
    procurar (a art dele, ou a mais barata que a caixa ACEITA). Até 16/10 era o
    `valor`, o `card_price` do motor: o mínimo entre impressões, sem o crivo de
    edição da caixa. Medido nesse dia: 70 210,89 € contra 74 362,66 € — as 100
    linhas com aviso (99 de Premodern, a mostrar reimpressões de 2020-2024 que a
    caixa recusa) valiam 1 791,23 € no motor e 5 943,00 € a sério. A página já
    usava o `valor_ref`; era a linha do daily que ele lia que estava 4 151,77 €
    abaixo. O mínimo do motor fica ao lado, com o nome que tem.
    """
    if t.get("regua") == "vendedor-profissional":
        # [2026-10-17] O preço é o 1.º anúncio de um vendedor profissional, na
        # língua e na edição da regra; as linhas com aviso são as SEM ANÚNCIO —
        # sem preço, não «preço errado».
        s = (f"{t['decks']} decks, {t['cartas']} cartas, {t['copias']} cópias, "
             f"{t['valor_ref']:.2f} EUR pelo 1.º anúncio de vendedor profissional "
             f"(«fechar tudo» {t['valor_serve']:.2f}, a diferença é a art que "
             f"procuras; mínimo do motor, sem o crivo: {t['valor']:.2f})")
        if t.get("sem_preco"):
            s += (f", {t['sem_preco']} cóp. sem preço ({t.get('avisos', 0)} linhas "
                  f"sem anúncio profissional na língua pedida)")
        return s
    s = (f"{t['decks']} decks, {t['cartas']} cartas, {t['copias']} cópias, "
         f"{t['valor_ref']:.2f} EUR pela impressão que serve "
         f"(mínimo do motor, sem o crivo de edição: {t['valor']:.2f}; a régua "
         f"do vendedor profissional ainda não foi recolhida nesta base)")
    if t.get("sem_preco"):
        s += f", {t['sem_preco']} cóp. sem preço"
    if t.get("avisos"):
        s += (f", {t['avisos']} linhas com o preço do motor fora da regra "
              f"(+{t['valor_serve'] - t['valor']:.2f} EUR)")
    return s


def texto(v: dict) -> str:
    """A mesma lista em texto, para o CLI e para o telemóvel dele copiar.

    O formato é o de sempre (`N Nome`, com `// <deck>` entre blocos): o Cardmarket
    ignora as linhas com `//`, e é por isso que o cabeçalho de cada deck pode ir
    no meio da lista sem a estragar.
    """
    from . import paginas                                      # noqa: PLC0415
    out = []
    for grupo, titulo in ((v["decks"], None),
                          (v["proposta"], "PROPOSTA — formato sem deck escolhido")):
        if titulo and grupo:
            out.append(f"// {titulo} (fora do total)")
        for d in grupo:
            out.append(f"// {d['nome']} — {d['copias']} cóp., "
                       f"{paginas.eur(d['valor'])}")
            out += [f"{l['q']} {l['nm']}" for l in d["linhas"]]
    t = v["totais"]
    out.append(f"// TOTAL: {t['cartas']} cartas, {t['copias']} cópias, "
               f"{paginas.eur(t['valor'])}")
    st = v.get("staples") or {}
    if st.get("linhas"):
        out.append(f"// STAPLES DE PREMODERN (colecção, fora do total) — "
                   f"{st['copias']} cóp., {paginas.eur(st['valor'])}")
        out += [f"{l['q']} {l['nm']}" for l in st["linhas"]]
    return "\n".join(out)


def main(argv=None) -> int:
    """`py -m mtgvault.faltas_vista [--json]` — a lista de faltas na consola."""
    import argparse                                            # noqa: PLC0415
    import json                                                # noqa: PLC0415

    from . import db, paginas                                   # noqa: PLC0415

    ap = argparse.ArgumentParser(description="O que falta comprar, por deck.")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    with db.session() as con:
        v = vista(con, loadout.report(con))
    if a.json:
        print(json.dumps(v, ensure_ascii=False, indent=1))
        return 0
    print(texto(v))
    print("\n" + texto_totais(v["totais"]))
    if v["proposta"]:
        p = v["totais_proposta"]
        print(f"PROPOSTA (fora do total): {p['cartas']} cartas, {p['copias']} cóp., "
              f"{paginas.eur(p['valor'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
