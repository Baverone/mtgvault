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

from . import loadout, scryfall as _scry, versoes


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
    unit = m.get("unit")
    # A IMAGEM É DA IMPRESSÃO QUE ELE VAI COMPRAR, não da que fez o preço. Numa
    # caixa de Premodern o preço pode vir de uma reimpressão de 2024 que ela
    # recusa (ver `loadout.preco_fora_da_regra`): mostrar essa arte era pôr-lhe no
    # ecrã uma carta que ele não pode levar. Onde nenhuma impressão que serve
    # está cotada, fica a que fez o preço — e a linha di-lo.
    regra = loadout.regra_da_carta(con, s, nm, cache)
    serve = loadout.mais_barata_que_serve(
        con, regra, nm, m.get("price_finish") or "nonfoil", cache)
    sid = serve["sid"] or loadout.impressao_mais_barata(
        con, nm, m.get("price_finish") or "nonfoil", cache=cache)
    # OS DOIS PREÇOS LADO A LADO, que é a disciplina do projecto («a somar» vs «a
    # rodar», 2026-10-04): o que o motor mostra e o da impressão que esta caixa
    # ACEITA. Medido a 2026-10-05, nas 121 cartas das seis caixas de Premodern,
    # **67** mostram o preço de uma reimpressão posterior ao Scourge e por isso o
    # subtotal estava sistematicamente ABAIXO do que ele vai pagar. Esconder o
    # segundo número era deixá-lo escolher onde caçar por uma conta errada.
    legal = serve["unit"] if serve["unit"] is not None else unit
    return {
        "nm": nm, "q": q, "unit": unit,
        "total": round((unit or 0) * q, 2),
        "unit_serve": serve["unit"], "total_serve": round((legal or 0) * q, 2),
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
        linhas.sort(key=lambda l: (-l["total"], l["nm"]))
        fmt = s.get("formato") or ""
        d = {
            "slot": s["slot"], "nome": s["nome"], "formato": fmt,
            "req": loadout.requisito_material(s),
            "cartas": len({l["nm"] for l in linhas}),
            "copias": sum(l["q"] for l in linhas),
            "valor": round(sum(l["total"] for l in linhas), 2),
            "valor_serve": round(sum(l["total_serve"] for l in linhas), 2),
            "sem_preco": sum(l["q"] for l in linhas if l["unit"] is None),
            "avisos": sum(1 for l in linhas
                          if (l["aviso"] or {}).get("grau") == "aviso"),
            "proposta": sem_deck_escolhido(fmt, cfg),
            "linhas": linhas,
        }
        (proposta if d["proposta"] else decks).append(d)
    decks.sort(key=lambda d: -d["valor"])
    proposta.sort(key=lambda d: -d["valor"])

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
                "sem_preco": sum(d["sem_preco"] for d in ds),
                "avisos": sum(d["avisos"] for d in ds)}

    fmts = sorted({d["formato"] for d in decks if d["formato"]})
    return {"decks": decks, "proposta": proposta, "formatos": fmts,
            "totais": soma(decks), "totais_proposta": soma(proposta)}


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
    t = v["totais"]
    print(f"\n{t['decks']} decks · {t['cartas']} cartas · {t['copias']} cópias · "
          f"{paginas.eur(t['valor'])}"
          + (f" · {t['sem_preco']} cóp. sem preço" if t["sem_preco"] else "")
          + (f" · {t['avisos']} linhas com o preço fora da regra" if t["avisos"] else ""))
    if v["proposta"]:
        p = v["totais_proposta"]
        print(f"PROPOSTA (fora do total): {p['cartas']} cartas, {p['copias']} cóp., "
              f"{paginas.eur(p['valor'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
