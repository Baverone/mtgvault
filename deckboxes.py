"""Gera deckboxes.html — "Deckboxes": os decks montados em simultâneo, e a venda.

O André (2026-09-07): *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."*

E, no mesmo dia, o que esta versão traz:

  * *"Os decks gostava que fizesses algo como fizeste para o riftvault — no
    botão, cada deck tem uma aba própria."* → a página deixou de ser uma lista
    de cartões todos abertos e passou a ser **uma fila de abas**, uma por caixa,
    com a % e a cor do estado. Clicar abre só aquela caixa. Há duas abas a mais:
    **Todas** (a vista de conjunto, um cartão por caixa) e **Arrumar**;
  * *"Quero que me ajudem a ser mais organizado com as cartas."* → a aba
    **Arrumar** traduz a alocação em instruções para a gaveta: por caixa de
    ORIGEM o que se tira e para onde vai, por caixa de DESTINO o que entra, com
    checkboxes que ficam no browser e um CSV para levar para a mesa;
  * *"Os decks que eu pedi para serem permanentes são a minha prioridade
    máxima!"* → cada caixa diz se é **permanente** ou **candidata**, e no modo
    edição (`python webapp.py`, porto 8771) os botões mudam isso, reordenam e
    marcam "sleevado e na caixa".

E, desde a v6 (2026-09-08), esta é **a página dos decks**: a *Decks
permanentes* (`meusdecks.html`) foi fundida aqui, porque *"decks vigiados e
deckbox é a mesma coisa"*. O que ela tinha e esta não — a lista por tipo com
imagens grandes, o texto da lista para copiar, e "quantas tenho na colecção
inteira" — entrou na aba de cada caixa; o ficheiro dela ficou como
reencaminhamento. Aqui juntou-se o **fluxo de montar**: o painel *Montar* (tirar
da colecção → comprar → fotografar o que chegar), a aba **Plano** (por onde
começar) e o botão *"vendida"*, que tira mesmo a cópia da colecção.

O que a página continua a ser: o LOADOUT, ou seja a colecção REPARTIDA. Uma
cópia física entra numa caixa e só numa — quem conta é a alocação, não a
colecção inteira. Três estados por carta: **verde** = está nesta caixa · **âmbar** = tens
mas não aqui (está noutra caixa, e diz qual, ou não serve na língua/acabamento)
· **vermelho** = não tens nenhuma, é compra.

O mesmo ficheiro serve os dois modos. No GitHub Pages `editable` é `false` e os
botões de escrita nem existem no HTML; no `webapp.py` é `true`. O frontend é o
mesmo — é a lição do riftvault: duas páginas diferentes divergem em silêncio.

Reutiliza `mtgvault.loadout` para as contas. Não inventa nada.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import loadout, paginas  # noqa: E402

TABS = paginas.nav("deckboxes.html")


def _art(sid):
    return f"https://cards.scryfall.io/small/front/{sid[0]}/{sid[1]}/{sid}.jpg" if sid else ""


# `nome -> scryfall_id`: vive no `paginas` desde a revisão de 2026-09-07 (19:00).
# Estava copiado à letra aqui e no `metagame.py`.
_img_map = paginas.img_map


# ---------------------------------------------------------------------------
# Payload: tudo o que a página mostra, em JSON. O HTML é uma casca.
# ---------------------------------------------------------------------------
def _estado_carta(m):
    """Os três estados. Âmbar é para as DUAS maneiras de "tens, mas não aqui" —
    está noutra caixa, ou está e não serve. Vermelho fica só para o que não
    existe em lado nenhum, que é o que é mesmo compra."""
    if not m["missing"]:
        return "have"
    if m["noutra_q"] or m["alt"]:
        return "sub"
    return "miss"


def _candidatos(con, rep):
    """`slot -> top-N de arquétipos que ele está mais perto de concluir`.

    André, 2026-09-07 (19:00): *"quero ver os top-3 mais perto de concluir e
    marcar qual vou montar"* — e não só na página do Metagame: também na aba da
    caixa, que é onde ele está quando decide. *"A caixa Pioneer já é Greasefang
    mas mostra também os 3 candidatos."*

    O cálculo é o do `metagame.candidatos` e mais nenhum: duas respostas
    diferentes à mesma pergunta é o padrão que este vault já pagou caro.
    """
    import metagame

    out = {}
    for fmt in metagame.formatos_top():
        s = metagame.slot_do_formato(rep["slots"], fmt)
        if s is None:
            continue
        out[s["slot"]] = [
            {"nome": c["nome"], "subtitulo": c["subtitulo"],
             "archetype_id": c["archetype_id"], "n_lists": c["n_lists"],
             "pct": round(100 * (sum(m["got"] for m in c["linhas"] if not m["basica"])
                                 + sum(m["noutra_q"] for m in c["linhas"]))
                          / max(1, sum(m["need"] for m in c["linhas"]
                                       if not m["basica"]))),
             "comprar": sum(m["comprar"] for m in c["linhas"]),
             "custo": round(sum(m["cost"] or 0 for m in c["linhas"]), 2),
             "escolhido": c["escolhido"], "escolhido_em": c["escolhido_em"]}
            for c in metagame.candidatos(con, fmt, rep)]
    return out


def _montar_payload(rep, s, cores):
    """O passo 1 do painel **Montar**: a lista exacta de cópias a tirar.

    Ordenada por **cor** e depois por nome — a ordem por que as cartas estão
    arrumadas na `Colecção` (ver `colecao_cor.html`: cor → CMC). Ordená-la por
    nome, como a arrumação geral faz, obrigava-o a percorrer o binder de trás
    para a frente por cada carta.

    E partida em **dois blocos**, main e sideboard (André, 2026-09-08: *"preciso
    também de saber o que é sideboard nos decks, para ficar separado dentro da
    mesma caixa"*). Quem parte é o `loadout.blocos_de_board`, o mesmo que o CLI
    usa: dois sítios a decidir o que é sideboard eram duas oportunidades de
    discordarem. A carta que joga nos dois vem em duas linhas — são duas cópias
    físicas, em duas pilhas.
    """
    plano = loadout.plano_montar(rep, s["slot"])
    if not plano:
        return None
    ordem = paginas.COR_ORDEM

    def linha(m):
        cor = (cores or {}).get(m["nm"], "C")
        return {"nm": m["nm"], "q": m["q"], "de": m["de"], "cor": cor,
                "cor_nome": paginas.COR_NOME.get(cor, cor),
                "board": m.get("board") or "",
                "set": (m["set_code"] or "").upper(),
                "fin": m["finish"], "foil": loadout.e_foil(m["finish"]),
                "lang": (m["lang"] or "").upper(), "copy_id": m["copy_id"]}

    por_cor = lambda x: (ordem.get(x["cor"], 9), x["nm"], x["set"])  # noqa: E731
    tirar = sorted((linha(m) for m in plano["tirar"]), key=por_cor)
    devolver = sorted((linha(m) for m in plano["devolver"]), key=por_cor)
    # MONTAR FORA DE ORDEM (André, 2026-09-08): se ele abre a Enchantress antes
    # do UW Replenish, as cartas que o Replenish há-de levar estão na mesma
    # gaveta, ali à mão. Vêm num bloco PRÓPRIO e por marcar — tirá-las tem
    # consequência (a outra caixa passa a vir buscá-las aqui), e por isso é uma
    # decisão dele e não algo que acontece por abrir a aba.
    de_outra = sorted(({**linha(m), "destino": m["destino"]}
                       for m in plano["de_outra"]), key=por_cor)
    # TERRENOS BÁSICOS (André, 2026-09-08): *"faltou marcares, para completar o
    # deck, os terrenos básicos necessários!"* Vêm num bloco à parte, DEPOIS do
    # main e do sideboard: a pilha de básicas não está arrumada no binder por
    # cor, e metade delas nem sequer está registada na base — não têm `copy_id`
    # para marcar. Não se partem por board pela mesma razão: uma básica é uma
    # pilha, e "12 Island no main + 2 no side" é a mesma ida à gaveta.
    basicas = [{"nm": b["nm"], "need": b["need"], "granel": b["granel"],
                "comprar": b["comprar"], "req": b["req"], "cost": b["cost"],
                "unit": b["unit"], "ja": b["ja"], "da_base": b["da_base"],
                "tirar": [linha(m) for m in b["tirar"]]}
               for b in plano["basicas"]]
    return {"slot": plano["slot"], "caixa": plano["caixa"],
            "tirar": tirar, "devolver": devolver, "copias": plano["copias"],
            "de_outra": de_outra, "copias_de_outra": plano["copias_de_outra"],
            "ja": plano["ja"], "por_gaveta": plano["por_gaveta"],
            "totais": plano["totais"],
            "blocos": [{"board": b["board"], "titulo": b["titulo"],
                        "movs": b["movs"], "q": b["q"], "de": b["de"]}
                       for b in loadout.blocos_de_board(tirar, plano["totais"])],
            "blocos_de_outra": [{"board": b["board"], "titulo": b["titulo"],
                                 "movs": b["movs"], "q": b["q"], "de": 0}
                                for b in loadout.blocos_de_board(de_outra)],
            # O "N de M" da barra de montagem e o "N de M na caixa" do cabeçalho.
            # Vêm do Python porque é o Python que decide o que se marca — a
            # página conta as checkboxes que desenhou, e as duas contas têm de
            # dar o mesmo número (tem teste).
            "marcar_q": plano["marcar_q"], "dentro": plano["dentro"],
            "basicas": basicas, "basicas_copias": plano["basicas_copias"],
            "basicas_comprar": plano["basicas_comprar"],
            "basicas_custo": plano["basicas_custo"],
            "edicao": plano["basicas_edicao"]}


def _por_blocos(mapa):
    """`{gaveta/caixa: [blocos main/side]}` — a aba *Arrumar* pelos dois lados.

    A ordem dentro de cada bloco é a que o `plano_arrumacao` já deu (por caixa e
    por nome); o que isto faz é só separar as duas pilhas.
    """
    return {nome: loadout.blocos_de_board(movs) for nome, movs in mapa.items()}


def _basicas_geral(rep):
    """As básicas a COMPRAR de todas as caixas, juntas por nome + material.

    São só as que a pilha de Unhinged não cobre — hoje as Snow-Covered do Duel
    Commander. Vão para a aba *Comprar* num bloco próprio, marcado *confirma se
    já tens*: pode ser que ele as tenha e não as tenha registado, e uma linha a
    confirmar é mais barata do que um deck que não se monta à hora de sair.
    """
    out: dict[tuple, dict] = {}
    for s in rep["slots"]:
        for b in s.get("basicas") or []:
            if not b["comprar"]:
                continue
            g = out.setdefault((b["nm"], b["req"]), {
                "nm": b["nm"], "req": b["req"], "q": 0, "cost": 0.0,
                "unit": b["unit"], "para": []})
            g["q"] += b["comprar"]
            g["cost"] = round(g["cost"] + b["cost"], 2)
            g["para"].append({"caixa": s["nome"], "q": b["comprar"]})
    return sorted(out.values(), key=lambda g: (-g["cost"], g["nm"]))


def _lista_texto(s):
    """A lista da caixa em texto (`4 Swords to Plowshares`), main e sideboard.

    Era o que a página *Decks permanentes* tinha e esta não: copiar a lista para
    a levar para outro sítio (Moxfield, um proxy, uma mensagem). Aqui sai da
    MESMA lista que a caixa usa para contar, e não de uma segunda leitura.
    """
    def bloco(board):
        return "\n".join(f"{q} {nm}" for b, nm, q in
                         sorted(s["cards"], key=lambda c: c[1]) if b == board)
    main, side = bloco("main"), bloco("side")
    return main + (f"\n\nSideboard\n{side}" if side else "")


def _caixa_payload(s, imgs, cfs, rep=None, col=None, tipos=None, cores=None):
    cartas = []
    for m in s["have"] + s["missing"]:
        cartas.append({
            "nm": m["nm"], "board": m["board"], "need": m["need"], "got": m["got"],
            "est": _estado_carta(m), "sid": imgs.get(m["nm"]),
            "basica": bool(m.get("basica")),
            "missing": m["missing"], "comprar": m["comprar"],
            # O que o TECTO DE PLAYSET não deixa comprar (André, 2026-09-08). Vem
            # na carta e não só no resumo: é ali que ele está quando pergunta
            # "porque é que isto não está na lista de compras?".
            "bloq": m.get("playset_bloqueado", 0),
            "noutra": m["noutra"], "alt": m["alt"], "alt_onde": m["alt_onde"],
            # ONDE A CARTA ESTÁ vs A QUEM ESTÁ DESTINADA (André, 2026-09-08: *"o
            # resto ainda nada está em deckbox — e ainda estás a assumir que há
            # cartas que já estão nas deckboxes dos decks"*). A frase vem pronta
            # do Python (`loadout.onde_esta`): a página não volta a compor "em
            # X" a partir do `noutra`, que é a caixa DESTINO e não o sítio.
            "onde": loadout.onde_esta(m),
            "nmont": sum(m["noutra_montada"].values()),
            "nres": sum(m["noutra_reservada"].values()),
            "cost": m["cost"], "unit": m["unit"],
            "cf": m["nm"] in cfs,
            # O TIPO (para agrupar a lista como ele a arruma) e as cópias que tem
            # na COLECÇÃO INTEIRA. Este segundo número é a única coisa que a
            # página *Decks permanentes* dizia e esta não; entra como informação
            # secundária, porque o número que manda é o da alocação — duas
            # respostas para a mesma pergunta era o defeito a corrigir.
            "tipo": (tipos or {}).get(m["nm"], "Other"),
            "col": (col or {}).get(m["nm"], 0),
            "so_de": s["so_de_variante"].get(m["nm"]) or [],
            "lotes": [{"local": g["local"], "q": g["q"], "fin": g["finish"],
                       "lang": g["lang"], "set": (g["set_code"] or "").upper()}
                      for g in m["lotes"]],
        })
    cartas.sort(key=lambda c: (c["board"] != "main",
                               {"have": 0, "sub": 1, "miss": 2}[c["est"]], c["nm"]))
    return {
        "slot": s["slot"], "nome": s["nome"], "formato": s["formato"],
        "grupo": s.get("grupo"), "prioridade": s["prioridade"],
        # PRIORIDADE AUTOMÁTICA (André, 2026-09-08: *"para já a prioridade vem
        # por ordem de % completo"*). A página tem de dizer de onde veio a ordem
        # — e o modo edição tem de desactivar o subir/descer, senão o botão
        # mexia num número que já não decide nada.
        "prioridade_por": s.get("prioridade_por") or "",
        "posicao_grupo": s.get("posicao_grupo") or 0,
        "pct_coleccao": s.get("pct_coleccao"),
        # O TECTO DE PLAYSET do grupo, e quantas cópias ele não deixa comprar.
        "playset": loadout.playset_maximo(s) or 0,
        "bloqueado": s.get("playset_bloqueado", 0),
        "playset_faltas": [{"nm": m["nm"], "board": m["board"],
                            "q": m["playset_bloqueado"]}
                           for m in s.get("playset_faltas") or []],
        "estado": s.get("estado"), "notas": s.get("nota_config") or "",
        "permanente": s["permanente"], "montado": bool(s.get("montado")),
        # MONTAR (v6): as cópias a tirar das gavetas, por cor e depois por nome —
        # é assim que se procura numa caixa de colecção. Mais a lista da caixa em
        # texto, para ele a copiar.
        "montar": _montar_payload(rep, s, cores) if rep is not None else None,
        "lista": _lista_texto(s),
        # Caixa DEDICADA (2026-09-07, 19:00): não empresta nem vai buscar. A
        # página tem de o dizer — é o que explica porque é que uma carta que ele
        # TEM aparece na lista de compras desta caixa.
        "dedicado": bool(s.get("dedicado")),
        "congelada": bool(s.get("congelada")),
        # Diz-se montada e o vault não sabe o que lá está dentro (o Stiflenought
        # na base de 2026-09-07: `montado: true` e zero linhas na
        # `copy_allocation`, porque a migração só semeou as caixas que eram um
        # balde). Aí o painel Montar pergunta o que é mesmo a pergunta —
        # *confirmas que está montada com estas cartas?* — em vez de mandar
        # montar de novo um deck que está na estante.
        "confirmar": bool(s.get("montado_por_confirmar")),
        # Tem conteúdo confirmado na `copy_allocation`: é o que decide se há
        # alguma coisa para DESMONTAR. Não é o mesmo que `montado` — as quatro
        # caixas de 2026-09-08 tinham alocação herdada da migração sem estarem
        # montadas em lado nenhum, e era a essas que ele precisava do botão.
        "arrumada": bool(s.get("arrumada")),
        "por_confirmar": bool(s.get("por_confirmar")), "vazio": s["vazio"],
        "nota": s["nota"], "fonte": s.get("fonte"), "ref": s.get("ref"),
        "pct": s["pct"], "tenho": s["tenho"], "precisa": s["precisa"],
        "comprar": s["comprar"], "noutra": s["noutra"], "faltam": s["faltam"],
        # As três parcelas do "destinadas a outra caixa" (André, 2026-09-08).
        # O cabeçalho da caixa mostra-as separadas: só a primeira é uma ida a
        # outra caixa, e hoje ela é ZERO em todas menos no Stiflenought.
        "nmont": s["noutra_montada"], "nres": s["noutra_reservada"],
        "nfut": s["noutra_futura"],
        "custo": s["custo"], "origens": s["origens"],
        # Quantas cópias a comprar não têm preço na base: o "fechar por" é um
        # MÍNIMO, e a página tem de o dizer em vez de o dar como a conta toda.
        "sem_preco": s["sem_preco"],
        # (ícone, texto, classe) — a classe vem do loadout, não de um teste de
        # substring na página (ver `loadout.rotulo_material`).
        "regras": [[i, t, c] for i, t, c in loadout.rotulo_material(s)],
        "req": loadout.requisito_material(s),
        "marca": loadout.marca_wantlist(s),
        "variantes": list(s.get("variantes") or []),
        "cartas": cartas,
        # `mat` é o material que vai DENTRO da linha copiada (`2 Swords [PT]`).
        # Vem da linha e não da caixa porque uma compra partilhada obedece ao
        # material do POOL, que pode ser mais exigente do que o desta caixa.
        # A wantlist da caixa também vem separada por bloco: a carta que falta no
        # main e no side são duas linhas, e o texto copiado leva `// Sideboard`
        # entre elas (o Cardmarket ignora a linha de comentário sem erro).
        "wantlist": sorted(({"nm": m["nm"], "q": m["comprar"], "cost": m["cost"],
                             "board": m["board"],
                             "mat": m.get("marca_compra") or ""}
                            for m in s["missing"] if m["comprar"] > 0),
                           key=lambda x: (x["board"] != "main", x["nm"])),
        # O "ir buscar" em TRÊS blocos, porque são três sítios diferentes
        # (André, 2026-09-08). Quem parte é o Python (`buscar_montada` /
        # `buscar_reservada` / `buscar_futura`) e quem escreve a frase é o
        # `loadout.onde_esta` — a página juntava as três num "em <caixa>" só, e
        # mandava-o abrir caixas que ainda não existem na estante.
        "buscar": {qual: [{"nm": m["nm"], "comprar": m["comprar"],
                           "onde": loadout.onde_esta(m, qual)}
                          for m in s[f"buscar_{qual}"]]
                   for qual in ("montada", "reservada", "futura")},
        "subs": [{"nm": m["nm"], "missing": m["missing"], "alt": m["alt"],
                  "onde": m["alt_onde"]} for m in s["subs"]],
    }


def _premodern_payload(rep, imgs):
    """As CAIXAS CANDIDATAS de Premodern: o que ele pode montar com o que sobra.

    André, 2026-09-08: *"se o deck for top-10 de representação ou top-5 decks
    combo do formato, sugere a lista para montar o deck caso eu tenha pelo menos
    50 % das cartas."* A aba **Sugestões** é isto — e vive aqui, ao lado das
    caixas, porque é aqui que ele decide: a alternativa era mandá-lo à página do
    Metagame para voltar com a resposta.

    A percentagem que DECIDE é a de *"como se fosse o principal"*
    (`pct_principal`, André 2026-09-08): as caixas de Premodern partilham cartas
    entre si, por isso um deck que escolhesse primeiro ficaria com as cópias que
    hoje estão nas outras. A do que SOBRA (`pct`) vai a seguir, porque a
    diferença entre as duas é quantas cartas viriam emprestadas — que é a
    pergunta seguinte, e a razão de a primeira ser tão maior.
    """
    pm = rep.get("premodern") or {}
    if not pm.get("activo"):
        return {"activo": False, "candidatos": [], "sugestoes": 0, "limiar": 0}

    def linha(c):
        return {"nome": c["nome"], "subtitulo": c["subtitulo"],
                # O `id` estável do arquétipo: é ele que vai nos botões e a chave
                # por que a recusa/escolha se guarda. O nome é apresentação.
                "id": c["id"],
                "archetype_id": c["archetype_id"], "n_lists": c["n_lists"],
                "pct": c["pct"], "pct_total": c["pct_total"],
                "pct_principal": c["pct_principal"],
                "tenho_principal": c["tenho_principal"],
                "combo": c["combo"], "grau": c["grau"],
                "top": c["top"], "top_combo": c["top_combo"],
                "estado": c["estado"], "caixa": c.get("caixa_nome"),
                "recusada_em": c.get("recusada_em"),
                "comprar": c["comprar"], "custo": c["custo"],
                "need": c["need"], "got": c["got"],
                "cartas": [{"nm": m["nm"], "sid": imgs.get(m["nm"]),
                            "need": m["need"], "got": m["got"],
                            "est": ("have" if m["got"] >= m["need"]
                                    else "sub" if m["noutra_q"] else "miss"),
                            "noutra": m["noutra"]}
                           for m in c["linhas"] if not m.get("basica")]}

    return {"activo": True, "limiar": pm["limiar"],
            "candidatos": [linha(c) for c in pm["elegiveis"]],
            "sugestoes": len(pm["sugestoes"])}


def payload(con, rep, editable=False, token="", ligacao=None):
    nomes = {c["nm"] for c in rep["conflitos"]}
    for s in rep["slots"]:
        nomes |= {n for _b, n, _q in s["cards"]}
    for k in ("venda", "venda_rl", "guardar", "retidos", "reservadas"):
        nomes |= {r["nm"] for r in rep[k]}
    nomes |= {m["nm"] for m in rep["arrumacao"]["movimentos"]}
    imgs = _img_map(con, sorted(nomes))
    cfs = {c["nm"] for c in rep["conflitos"]}
    # Tipo, cor e "quantas tenho ao todo" — as três coisas que a página dos decks
    # tinha e que passaram para a aba da caixa (ver `mtgvault.paginas`).
    meta = paginas._meta_cartas(con, sorted(nomes))
    tipos = {n: paginas.tipo_de(tl) for n, (tl, _ci) in meta.items()}
    cores = {n: paginas.cor_de(tl, ci) for n, (tl, ci) in meta.items()}
    col = paginas.posse_total(con)

    # A LISTA DE COMPRAS, com a atribuição a caixas. Só `{nm, q, cost}` não
    # chegava: uma compra sem dizer PARA QUE CAIXA e EM QUE LÍNGUA/ACABAMENTO é
    # meio caminho para comprar a versão errada — 4 Swords to Plowshares EN não
    # servem a caixa de Premodern, que as quer PT e até ao Scourge.
    # E, desde 2026-09-07, com a PARTILHA: `q` é o que se compra mesmo (o máximo
    # de uma caixa, não a soma) e o `para` mostra também as caixas que a compra
    # serve sem pagar — `serve: true`. Ver `loadout.partilhar_compras`.
    servidas: dict[str, list[dict]] = {}
    # Quantas caixas partilham a compra desta carta. NÃO é `len(para)`: a mesma
    # carta pode ser comprada em dois materiais e só um deles ser partilhado — o
    # Lion's Eye Diamond compra-se 2 em PT (Premodern, sozinho) e 1 em EN nonfoil
    # para as duas caixas de cEDH. Aí o chip diz 2 caixas, não 3.
    n_partilha: dict[str, int] = {}
    for p in rep.get("partilhas") or []:
        servidas[p["nm"]] = [
            {"caixa": c["caixa"], "slot": c["slot"], "q": c["pediu"], "cost": 0.0,
             "unit": None, "req": p["req"], "mat": p["marca"], "serve": True}
            for c in p["caixas"] if not c["compra"]]
        n_partilha[p["nm"]] = max(n_partilha.get(p["nm"], 0), len(p["caixas"]))
    geral: dict[str, dict] = {}
    for s in rep["slots"]:
        for m in s["missing"]:
            if not m["comprar"]:
                continue
            g = geral.setdefault(m["nm"], {"nm": m["nm"], "q": 0, "cost": 0.0,
                                           "unit": None, "para": [], "req": "",
                                           "mat": "", "partilhada": 0})
            g["q"] += m["comprar"]
            g["cost"] = round(g["cost"] + (m["cost"] or 0), 2)
            # O preço por cópia é o mais alto das caixas que a pedem — é o que
            # decide se a carta entra no bolo das "caras", e por baixo era pior.
            if m["unit"] and (g["unit"] is None or m["unit"] > g["unit"]):
                g["unit"] = m["unit"]
            g["para"].append({"caixa": s["nome"], "slot": s["slot"],
                              "q": m["comprar"], "cost": m["cost"],
                              "unit": m["unit"],
                              # O material vem da LINHA: numa compra partilhada
                              # é o do pool (o mais exigente das caixas), não o
                              # desta caixa. Comprar uma foil PT porque o Duel
                              # Commander não exige língua deixava o Modern sem
                              # a carta na mesma.
                              "req": m.get("req_compra") or "",
                              "mat": m.get("marca_compra") or ""})
    for nm, extra in servidas.items():
        if nm in geral:
            geral[nm]["para"].extend(extra)
    for g in geral.values():
        # Duas caixas podem querer a mesma carta em material diferente; nesse
        # caso são duas compras e a linha di-lo, em vez de escolher uma.
        g["req"] = " / ".join(r for r in dict.fromkeys(p["req"] for p in g["para"]) if r)
        g["mat"] = " / ".join(r for r in dict.fromkeys(p["mat"] for p in g["para"]) if r)
        g["partilhada"] = n_partilha.get(g["nm"], 0)
        g["para"].sort(key=lambda p: (bool(p.get("serve")), -p["q"], p["caixa"]))

    def venda_bloco(chave, copias, total):
        return {"linhas": [{"nm": r["nm"], "q": r["q"], "local": r["local"],
                            # A identidade da linha, para o botão "vendida" do
                            # modo edição. Vem do `loadout` (`chave_venda`) e não
                            # da página: se cada lado inventasse a sua, um clique
                            # tirava da colecção a cópia errada.
                            "chave": loadout.chave_venda(r),
                            "set": (r["set_code"] or "").upper(), "fin": r["finish"],
                            # Quem decide se é foil é o Python (`FOIL_FINISHES`).
                            # A página fazia `/foil|etched/.test(fin)` e punha ✨
                            # em cópias `nonfoil`, que contém "foil".
                            "foil": loadout.e_foil(r["finish"]),
                            "lang": r["lang"], "unit": r["unit"],
                            "total": r["total"], "rl": bool(r["rl"]),
                            "reason": r["reason"], "sid": imgs.get(r["nm"]),
                            # Só nos blocos da RL retida: o motivo por que a
                            # cópia ia à venda antes de a regra dos 5 % a
                            # segurar. Sem ele a linha diz "subiu 7 %" e perde-se
                            # a pergunta a que isso responde.
                            "porque": r.get("porque_venderia", ""),
                            # A JANELA em que a subida foi medida, por cópia
                            # (2026-09-08). Com a janela a crescer todos os dias,
                            # "+1,8 %" sozinho não diz se foi medido em 27 dias
                            # ou em 90 — e é a diferença entre uma carta parada e
                            # uma que está a subir depressa.
                            "rl_nota": r.get("rl_nota", "")}
                           for r in rep[chave]],
                "copias": rep[copias], "total": rep[total]}

    arr = rep["arrumacao"]
    # As regras de cada caixa, por NOME: é assim que o `conflitos` identifica
    # quem disputa a carta. A aba Partilhadas precisa delas para dizer que uma
    # partilha respeita as regras de quem vai buscar — o Enchantress vai buscar
    # a Swords to Plowshares PT ao UW Replenish, nunca a foil do Cloud.
    reqs = {s["nome"]: loadout.requisito_material(s) for s in rep["slots"]}
    return {
        "gerado": con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or "",
        "hoje": date.today().isoformat(),
        "editable": bool(editable),
        # O token de escrita e o link/QR do telemóvel só existem em modo edição —
        # o ficheiro publicado no GitHub Pages não pode levar nem um nem outro.
        "token": token if editable else "",
        "ligacao": ligacao if editable else None,
        # A BARRA DE MONTAGEM (André, 2026-09-08): marcar a última cópia regista
        # a caixa sozinha, com um *anular* de alguns segundos ao lado. Os dois
        # números vêm do config (`colecao_config.json -> montar`) — a página não
        # decide sozinha que vai escrever na base.
        "auto_registar": loadout.montar_auto_registar(),
        "anular_segundos": loadout.montar_anular_segundos(),
        "caixas": [_caixa_payload(s, imgs, cfs, rep, col, tipos, cores)
                   for s in rep["slots"]],
        # A ORDEM por que montar as caixas (aba Plano) — permanentes por
        # prioridade, depois as que estão mais perto de fechar.
        "montagem": rep.get("montagem") or [],
        # O top-N por caixa por escolher (Standard/Pioneer/Legacy) — o "vou
        # montar este" também mora aqui, não só no metagame.html.
        "candidatos": _candidatos(con, rep),
        "resumo": {"montados": sum(1 for s in rep["slots"] if s.get("montado")),
                   "permanentes": sum(1 for s in rep["slots"] if s["permanente"]),
                   "candidatos": sum(1 for s in rep["slots"] if not s["permanente"]),
                   "comprar": rep["comprar_total"], "noutra": rep["noutra_total"],
                   # As três parcelas do "destinadas a outra caixa". O cabeçalho
                   # diz as três: a 2026-09-08 a primeira era ZERO e a página
                   # continuava a chamar "ir buscar a outra caixa" às 70.
                   "nmont": rep["noutra_montada_total"],
                   "nres": rep["noutra_reservada_total"],
                   "nfut": rep["noutra_futura_total"],
                   # Cópias que a partilha poupou (o que a soma caixa a caixa
                   # pedia a mais). Mostrado na aba Comprar.
                   "poupado": rep.get("poupado_total", 0),
                   "sem_preco": rep.get("sem_preco_total", 0),
                   "custo": rep["custo_total"], "venda": rep["total"],
                   # TERRENOS BÁSICOS a comprar (as Snow-Covered, que a pilha de
                   # Unhinged não cobre). À parte do `comprar`/`custo`: são *a
                   # confirmar*, e somá-las mexia no número por que ele decide.
                   "basicas": rep.get("basicas_comprar_total", 0),
                   "basicas_custo": rep.get("basicas_custo_total", 0.0),
                   "venda_rl": rep["total_rl"], "arrumar": arr["copias"]},
        "compras": sorted(geral.values(), key=lambda g: -g["cost"]),
        # As básicas a comprar, juntas por nome+material, com a caixa que as pede.
        "basicas": _basicas_geral(rep),
        "basicas_edicao": loadout.basicas_edicao(),
        "partilhadas": [{"nm": c["nm"], "pedido": c["pedido"], "tenho": c["tenho"],
                         "sid": imgs.get(c["nm"]),
                         "por_slot": [dict(q, req=reqs.get(q["slot"], ""))
                                      for q in c["por_slot"]],
                         "ficam_com": c["ficam_com"], "ficam_sem": c["ficam_sem"]}
                        for c in rep["conflitos"]],
        "venda": {"normal": venda_bloco("venda", "copias", "total"),
                  "rl": venda_bloco("venda_rl", "copias_rl", "total_rl"),
                  "guardar": venda_bloco("guardar", "copias_guardar", "total_guardar"),
                  # RESERVADAS por uma sugestão de Premodern por decidir: não são
                  # excedente, são cartas de um deck que ele ainda não disse se
                  # quer. Ficam num bloco próprio — e sem botão «vendida», porque
                  # a decisão que as liberta é o «não quero este».
                  "reservadas": venda_bloco("reservadas", "copias_reservadas",
                                            "total_reservado"),
                  # RESERVED LIST QUE VALORIZOU e RL que o vault ainda não sabe
                  # medir (André, 2026-09-08: *"cartas de RL só vão para venda se
                  # não tiverem subido 5 % de valor nos últimos 3 meses"*). Dois
                  # blocos e não um: "subiu" é uma decisão tomada, "não sei" é
                  # uma decisão por tomar.
                  "rl_segurar": venda_bloco("rl_segurar", "copias_rl_segurar",
                                            "total_rl_segurar"),
                  "rl_sem_historico": venda_bloco("rl_sem_historico",
                                                  "copias_rl_sem_historico",
                                                  "total_rl_sem_historico"),
                  "retidos": venda_bloco("retidos", "copias_retidas", "total_retido")},
        # Quanto é que a regra dos 5 % segurou ao todo, e com que parâmetros.
        # A janela é um MÁXIMO desde 2026-09-08: a efectiva é a que cada carta
        # dá, e o limiar acompanha-a. Os três números vão para a página porque
        # são os três que explicam uma linha — "subiu 2 % e ficou" só se percebe
        # com a janela ao lado.
        "rl_regra": {"copias": rep["copias_rl_retidas"],
                     "total": rep["total_rl_retido"],
                     "pct": loadout.rl_subida_minima(),
                     "dias": loadout.rl_janela_dias(),
                     "minima": loadout.rl_janela_minima(),
                     "fixo": loadout.rl_limiar_fixo()},
        # PREMODERN (André, 2026-09-08): o que montar a seguir com o que sobra.
        # A conta é a do `mtgvault.premodern`, a mesma que o metagame.html mostra.
        "premodern": _premodern_payload(rep, imgs),
        # O motivo da venda nova, para a página reconhecer as linhas dele. Vem do
        # Python e não escrito à mão no JavaScript: um texto igual em dois sítios
        # é um texto que fica diferente na primeira vez que alguém lhe mexe.
        "pm_razao": loadout.RAZAO_PREMODERN,
        # Cada gaveta e cada caixa partidas em MAIN e SIDEBOARD, do lado do
        # Python (`loadout.blocos_de_board`) — a página não volta a decidir o que
        # é sideboard, como não decide o que é foil. O CSV e os totais continuam
        # a sair da lista corrida: o que muda é só a apresentação.
        "arrumar": {"por_origem": _por_blocos(arr["por_origem"]),
                    "por_destino": _por_blocos(arr["por_destino"]),
                    "copias": arr["copias"], "linhas": arr["linhas"],
                    # As caixas CONGELADAS não se arrumam, actualizam-se: o
                    # "já arrumei tudo" geral não lhes toca e cada uma tem o seu
                    # botão "actualizei" (André, 2026-09-07: *"apenas mexer para
                    # actualizar"*).
                    "actualizacoes": list(arr["actualizacoes"].values()),
                    "copias_actualizar": arr["copias_actualizar"],
                    "csv": loadout.csv_arrumacao(arr)},
    }


def build(con, out_path=None, editable=False, rep=None):
    out = Path(out_path) if out_path else (ROOT / "deckboxes.html")
    rep = rep if rep is not None else loadout.report(con)
    dados = payload(con, rep, editable=editable)
    out.write_text(_html(dados), encoding="utf-8")
    return out


def redireccionamento(destino="deckboxes.html", titulo="Decks permanentes") -> str:
    """A página que ficou no lugar de uma que foi fundida noutra.

    A *Decks permanentes* (`meusdecks.html`) desapareceu na v6 — a Deckboxes é a
    página dos decks. O ficheiro continua a ser gerado como reencaminhamento
    porque o telemóvel dele tem o link no histórico e o site publicado tem-no em
    páginas antigas: um 404 não explica nada, e "mudou de sítio" explica.
    """
    return (f'<!doctype html><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={destino}">'
            f'<title>{titulo} → Deckboxes</title>'
            f'<link rel="canonical" href="{destino}">'
            f'<style>body{{background:#0d1017;color:#eef2f7;font:15px/1.6 '
            f'system-ui,sans-serif;margin:0;display:flex;min-height:100vh;'
            f'align-items:center;justify-content:center;text-align:center;'
            f'padding:24px}}a{{color:#5b8cff}}</style>'
            f'<div><h1>🧰 Mudou de sítio</h1><p>Os decks e as deckboxes passaram '
            f'a ser <b>a mesma página</b>: cada deck é uma caixa, com a lista, o '
            f'que falta comprar e o que tirar da colecção para o montar.</p>'
            f'<p><a href="{destino}">Ir para as Deckboxes →</a></p></div>')


def _html(dados):
    return (_TMPL.replace("%META%", paginas.META)
            .replace("%TEMA%", paginas.TEMA)
            .replace("%TABS%", TABS)
            # O `</` escapado é o que impede um nome de carta com `</script>` de
            # fechar a etiqueta a meio do payload.
            .replace("%DADOS%", json.dumps(dados, ensure_ascii=False)
                     .replace("</", "<\\/")))


def html_page(con, editable=False, rep=None, token="", ligacao=None):
    """A página como texto — é o que o `webapp.py` serve sem escrever no disco.

    `token`/`ligacao` só vêm preenchidos quando o pedido já trazia o token: é o
    que autoriza os botões a gravar e o que desenha o QR para o telemóvel.
    """
    return _html(payload(con, rep if rep is not None else loadout.report(con),
                         editable=editable, token=token, ligacao=ligacao))


_TMPL = r"""<!doctype html><html lang="pt-PT"><head>%META%
<title>Deckboxes</title><style>
%TEMA%
 :root{--r:12px;--r2:16px}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);
      font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      padding-bottom:env(safe-area-inset-bottom)}
 .wrap{max-width:1180px;margin:0 auto;padding:18px 14px 70px}
 a{color:var(--accent)}
 h1{margin:0;font-size:22px;font-weight:800;letter-spacing:-.02em}
 h2{font-size:13px;margin:22px 0 4px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.07em;font-weight:700} h2 .n{color:var(--dim);font-weight:600}
 h3{font-size:14px;margin:16px 0 6px;font-weight:700}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px} .lead b{color:var(--ink2)}
 .dim{color:var(--dim)}
 /* navegação entre páginas */
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
 .tabs a{flex:1 1 118px;text-align:center;padding:11px 8px;border-radius:var(--r);
   background:var(--card);border:1px solid var(--line);color:var(--ink);
   text-decoration:none;font-weight:600;font-size:14px;transition:.15s}
 .tabs a:hover{border-color:var(--accent)}
 .tabs a.cur{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent)}
 /* fila de abas: uma por deck (a ideia do riftvault) */
 .decktabs{display:flex;gap:6px;overflow-x:auto;padding:4px 0 8px;margin:6px -14px 10px;
   padding-inline:14px;scrollbar-width:thin;-webkit-overflow-scrolling:touch}
 .dt{flex:0 0 auto;display:flex;flex-direction:column;gap:1px;align-items:flex-start;
   padding:8px 12px;border-radius:var(--r);background:var(--card);
   border:1px solid var(--line);color:var(--ink2);cursor:pointer;font:inherit;
   font-size:13px;font-weight:600;line-height:1.25;white-space:nowrap;transition:.12s}
 .dt:hover{border-color:var(--line2)}
 .dt small{font-size:11px;font-weight:600;color:var(--muted);
   font-variant-numeric:tabular-nums}
 .dt.on{background:linear-gradient(180deg,#26406f,#1b2c4d);border-color:var(--accent);color:#fff}
 .dt.on small{color:#c9d8ff}
 .dt .pin{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:5px;
   vertical-align:middle}
 .pin.ok{background:var(--add)} .pin.mid{background:var(--gold)} .pin.low{background:var(--warn)}
 .dt.cand{border-style:dashed;opacity:.9}
 /* cabeçalho de uma caixa */
 .box{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:15px}
 .box+.box{margin-top:12px}
 .btop{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
   flex-wrap:wrap}
 .btop b{font-size:17px;letter-spacing:-.01em}
 .pct{font-weight:800;font-size:19px;font-variant-numeric:tabular-nums}
 .pct.dim{color:var(--muted)}
 .bar{position:relative;height:8px;background:#0a0d13;border-radius:999px;
   overflow:hidden;margin:9px 0}
 .bar i{position:absolute;left:0;top:0;bottom:0;border-radius:999px;
   transition:width .3s}
 .badges{display:flex;align-items:flex-start;gap:6px;flex-wrap:wrap;margin:8px 0}
 /* `white-space:normal` de propósito: com `nowrap`, a etiqueta das fontes
    ("fontes: Colecção + Caixa RL (PT)") transbordava o cartão no desktop em vez
    de partir a linha. Um chip nunca pode ser mais largo do que a caixa. */
 .bdg{font-size:11px;padding:3px 9px;border-radius:20px;background:#1e2531;
   color:var(--muted);white-space:normal;max-width:100%;overflow-wrap:anywhere}
 .bdg.ok{background:#123020;color:var(--add)} .bdg.wt{background:#241a10;color:var(--gold)}
 .bdg.pt{background:#101c2e;color:#7fa8ff} .bdg.fo{background:#2a2410;color:var(--gold)}
 .bdg.ded{background:#2c1b2e;color:#e0a8ea}
 .bdg.perm{background:#1b2c4d;color:#9dbcff;font-weight:700}
 .bdg.cand{background:#241a10;color:var(--gold);font-weight:700}
 .bdg.auto{background:#14262a;color:#79c9c4}
 .nums{display:flex;flex-wrap:wrap;gap:6px 10px;margin:8px 0}
 .num{background:var(--card2);border:1px solid var(--line);border-radius:10px;
   padding:6px 10px;font-size:12px;color:var(--muted);flex:1 1 auto;min-width:112px}
 .num b{display:block;font-size:16px;color:var(--ink);font-weight:800;
   font-variant-numeric:tabular-nums}
 .num.buy b{color:var(--warn)} .num.get b{color:#7fa8ff} .num.eur b{color:var(--gold)}
 /* "na gaveta, destinadas a outra caixa": âmbar e não azul — não é uma ida a
    outra caixa, é a mesma gaveta de sempre (André, 2026-09-08). */
 .num.get2 b{color:var(--gold)}
 .num .dim{display:block;font-size:10.5px;line-height:1.25}
 .nota{color:var(--dim);font-size:11.5px;margin:4px 0 0}
 .orig{color:var(--muted);font-size:12px;margin:6px 0 0}
 .orig b{color:var(--ink);font-variant-numeric:tabular-nums}
 .vaziomsg{background:#241a10;border:1px solid #6a4f2f;border-radius:10px;
   padding:10px 12px;margin-top:10px;font-size:13px;color:#f0dcc0}
 /* grelha de cartas */
 .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(58px,1fr));
   gap:5px;margin-top:10px}
 .cd{position:relative;border-radius:6px;aspect-ratio:.716;background:#0c0f14;
   overflow:hidden}
 .cd img{width:100%;height:100%;object-fit:cover;display:block}
 .cd.have{box-shadow:0 0 0 2px var(--add)}
 .cd.miss{box-shadow:0 0 0 2px var(--warn)} .cd.miss img{filter:grayscale(.75) brightness(.5)}
 .cd.sub{box-shadow:0 0 0 2px var(--gold)} .cd.sub img{filter:grayscale(.35) brightness(.68)}
 .cd .cq{position:absolute;bottom:2px;left:2px;background:#000d;color:#fff;
   font-size:10px;font-weight:700;padding:0 4px;border-radius:5px;
   font-variant-numeric:tabular-nums}
 .cd .cf{position:absolute;top:2px;right:2px;background:var(--warn);color:#160a06;
   font-size:9px;font-weight:800;width:15px;height:15px;line-height:15px;
   text-align:center;border-radius:4px}
 .cd .onde{position:absolute;left:0;right:0;bottom:0;background:#000000cc;
   color:var(--gold);font-size:9px;line-height:1.25;padding:2px 3px;
   text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 /* blocos de detalhe */
 .blk{margin-top:11px;background:var(--card2);border:1px solid var(--line);
   border-radius:var(--r);padding:10px 12px;font-size:12.5px;color:var(--muted)}
 .blk>b{color:var(--gold);display:block;margin-bottom:5px;font-size:12px}
 .blk ul{margin:0;padding-left:17px} .blk li{padding:1.5px 0}
 .blk li b{color:var(--ink)}
 .blk.onde{background:#0e1620;border-color:#25415e} .blk.onde>b{color:#7fa8ff}
 .blk.onde li b{color:#7fa8ff}
 .blk.lim{background:#1d1622;border-color:#4a3355} .blk.lim>b{color:#e0a8ea}
 .blk.lim li b{color:#e0a8ea}
 .flh{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:700;
   color:#e2795b;flex-wrap:wrap} .flh .dim{font-weight:400} .flh .cpbtn{margin-left:auto}
 .mrk{font-size:10px;font-weight:800;padding:1px 6px;border-radius:5px;
   background:#2a2410;color:var(--gold)}
 ul.fl{list-style:none;margin:7px 0 0;padding:0;font-size:12.5px}
 ul.fl li{display:flex;gap:7px;padding:2px 0} ul.fl b{color:var(--gold);
   font-variant-numeric:tabular-nums;flex:0 0 auto}
 ul.fl .wn{flex:1 1 auto;min-width:0}
 ul.fl .wn{min-width:0} ul.fl .wn small{display:block;color:var(--dim);font-size:11px;line-height:1.35;overflow-wrap:anywhere}
 ul.fl .pz{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums;
   flex:0 0 auto}
 .cara{font-size:9px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#3a1f1f;color:#ff9f8f;margin-left:5px;white-space:nowrap}
 .part{font-size:9px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#101c2e;color:#7fa8ff;margin-left:5px;white-space:nowrap}
 .chosen{font-size:9px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#123020;color:var(--add);margin-left:5px;white-space:nowrap}
 .cand-blk .flh{color:#7fa8ff}
 .cand-blk ul.fl li{align-items:flex-start;padding:5px 0;
   border-bottom:1px solid #1a212c}
 .cand-blk ul.fl li:last-child{border-bottom:0}
 .cand-blk ul.fl b{color:var(--ink);min-width:38px}
 .cand-blk .pz{display:flex;align-items:center;gap:8px}
 .cand-blk .nota{margin-top:8px}
 #v-compras ul.fl{column-width:280px;column-gap:22px} #v-compras ul.fl li{break-inside:avoid}
 .selc{font:inherit;font-size:12.5px;font-weight:600;padding:7px 12px;
   border-radius:20px;border:1px solid var(--line);background:var(--card);
   color:var(--ink);cursor:pointer;max-width:100%}
 .btn,.cpbtn{font:inherit;font-size:12px;font-weight:700;padding:7px 13px;
   border-radius:20px;border:1px solid var(--line);background:#1a2230;
   color:var(--ink2);cursor:pointer;transition:.12s}
 .btn:hover,.cpbtn:hover{border-color:var(--accent);color:#fff}
 .btn.pri{background:var(--accent);border-color:var(--accent);color:#fff}
 .btn.warn{background:#2a1a12;border-color:#6a4f2f;color:var(--gold)}
 .cpbtn.done{background:#123020;border-color:#2f6a45;color:var(--add)}
 .acts{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px;
   border-top:1px solid var(--line);padding-top:11px}
 .cmk{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
 /* vista "Todas" */
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:11px}
 .mini{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:13px;cursor:pointer;transition:.12s;text-align:left;font:inherit;color:inherit}
 .mini:hover{border-color:var(--line2);transform:translateY(-1px)}
 .mini.cand{border-style:dashed}
 /* partilhadas */
 .cfgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px}
 .cfrow{display:flex;gap:10px;background:var(--card);border:1px solid var(--line);
   border-radius:var(--r);padding:10px}
 .cfrow .cd{width:52px;flex:0 0 52px}
 .cfb{min-width:0;display:flex;flex-direction:column;gap:3px}
 .cfb b{font-size:13.5px} .cfb .dim{font-size:11.5px}
 .csl{display:flex;flex-wrap:wrap;gap:3px;margin-top:2px}
 .cs{font-size:10.5px;padding:2px 7px;border-radius:5px;font-variant-numeric:tabular-nums}
 .cs.ok{background:#0f2418;color:var(--add)} .cs.no{background:#2a1414;color:#ff8f8f}
 .cfb .creq{font-size:11px;color:var(--dim);line-height:1.4;margin-top:1px}
 .cfb .creq b{color:var(--muted);font-weight:700}
 /* venda */
 details.vblk{background:var(--card);border:1px solid var(--line);
   border-radius:var(--r);padding:11px 13px;margin-bottom:10px}
 details.vblk>summary{cursor:pointer;font-weight:700;font-size:14px;color:var(--ink);
   display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
 .vtot{color:var(--gold);font-variant-numeric:tabular-nums;font-weight:800}
 table.vt{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:9px}
 table.vt th{text-align:left;color:var(--dim);font-weight:600;font-size:10.5px;
   text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);
   padding:5px 6px}
 table.vt td{padding:4px 6px;border-bottom:1px solid #1a212c}
 table.vt tr:hover td{background:#141a24}
 table.vt td.q{color:var(--gold);font-weight:700;text-align:right;
   font-variant-numeric:tabular-nums}
 table.vt td.dim{color:var(--muted)}
 table.vt td.pz{text-align:right;font-variant-numeric:tabular-nums}
 table.vt td.tot{color:var(--gold);font-weight:700}
 .rl{font-size:9px;font-weight:800;padding:1px 4px;border-radius:4px;
   background:#3a1f1f;color:#ff9f8f;vertical-align:middle}
 /* arrumar */
 .arr{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:13px;margin-bottom:11px}
 .arrh{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
   flex-wrap:wrap;margin-bottom:7px}
 .arrh b{font-size:15px} .arrh span{color:var(--muted);font-size:12px}
 .mv{display:flex;align-items:center;gap:9px;padding:6px 4px;
   border-bottom:1px solid #1a212c;font-size:13px}
 .mv:last-child{border-bottom:0}
 .mv input{width:19px;height:19px;flex:0 0 19px;accent-color:var(--add);cursor:pointer}
 .mv.feito{opacity:.4;text-decoration:line-through}
 .mv .q{color:var(--gold);font-weight:800;font-variant-numeric:tabular-nums;
   flex:0 0 auto;min-width:26px}
 .mv .nm{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
   white-space:nowrap}
 .mv .to{color:var(--muted);font-size:12px;flex:0 0 auto;max-width:45%;
   overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .seg{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}
 .seg button{font:inherit;font-size:12.5px;font-weight:600;padding:7px 14px;
   border-radius:20px;border:1px solid var(--line);background:var(--card);
   color:var(--muted);cursor:pointer}
 .seg button.on{background:#1b2c4d;border-color:var(--accent);color:#fff}
 .empty{color:var(--muted);font-size:13.5px;background:var(--card2);
   border:1px dashed var(--line2);border-radius:var(--r);padding:18px;text-align:center}
 /* painel MONTAR (v6): os três passos do gesto */
 .montar{margin-top:12px;border:1px solid var(--line2);border-radius:var(--r2);
   background:var(--card2);padding:12px}
 .montar .mh{display:flex;justify-content:space-between;align-items:baseline;
   gap:10px;flex-wrap:wrap;margin-bottom:8px}
 .montar .mh b{font-size:15px}
 .montar .mh .dim{font-size:12px}
 .passo{border-top:1px solid var(--line);padding:10px 0 4px}
 .passo:first-of-type{border-top:0;padding-top:0}
 .ph{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}
 .ph b{font-size:13.5px} .ph .dim{font-size:12px}
 .pn{flex:0 0 20px;width:20px;height:20px;line-height:20px;text-align:center;
   border-radius:50%;background:var(--accent);color:#fff;font-size:11px;
   font-weight:800}
 .ok2{color:var(--add);font-size:12.5px;margin:4px 0}
 .mvs{max-height:60vh;overflow:auto;margin:2px 0 8px}
 .corhdr{margin:9px 0 2px;font-size:10.5px;font-weight:700;color:var(--muted);
   text-transform:uppercase;letter-spacing:.06em}
 /* cabeçalho de BLOCO (main / sideboard): mais forte do que o da cor, que vive
    lá dentro — a caixa tem duas pilhas e a lista tem de as separar à vista */
 .bhdr{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
   margin:10px 0 2px;padding-bottom:3px;border-bottom:1px solid var(--line);
   font-size:12px;font-weight:800;color:var(--ink2)}
 .bhdr span{color:var(--muted);font-size:11px;font-weight:600;
   font-variant-numeric:tabular-nums}
 .sb{color:var(--muted);font-size:10.5px;font-weight:700;margin-left:5px}
 .mv .nm small{display:block;color:var(--dim);font-size:10.5px;line-height:1.3}
 /* TERRENOS BÁSICOS: bloco próprio depois das cores (André, 2026-09-08) */
 .bas{margin:10px 0 8px;background:#101a14;border:1px solid #23402c;
   border-radius:var(--r);padding:9px 11px}
 .bas .flh{color:#6fbf8a}
 ul.bl{list-style:none;margin:6px 0 0;padding:0}
 ul.bl li{padding:5px 0;border-bottom:1px solid #1a2b20;font-size:13px}
 ul.bl li:last-child{border-bottom:0}
 ul.bl b{color:var(--gold);font-variant-numeric:tabular-nums}
 ul.bl .wn small{color:var(--dim);font-size:11px}
 .bd{margin-top:2px} .bd .mv{border-bottom:0;padding:3px 4px}
 .bt{display:block;color:var(--dim);font-size:11.5px;padding:2px 0 2px 28px}
 .bt.warn{color:#e2a15b}
 /* DESTINADAS A OUTRA CAIXA (2026-09-08): âmbar, como o terceiro estado das
    cartas — "tens, mas não é bem para aqui". Vêm por marcar de propósito. */
 .dout{margin:10px 0 8px;background:#1a1509;border:1px solid #4a3a12;
   border-radius:var(--r);padding:9px 11px}
 .dout .flh{color:var(--gold)}
 .dout .nota{margin:4px 0 6px}
 .typehdr{margin:10px 0 2px;font-size:10.5px;font-weight:700;color:var(--muted);
   text-transform:uppercase;letter-spacing:.06em}
 .typehdr .dim{color:var(--dim)}
 .cards.big{grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:7px}
 /* aba PLANO: a ordem por que montar */
 .plano{display:flex;flex-direction:column;gap:7px}
 .pl{display:flex;align-items:center;gap:11px;width:100%;text-align:left;
   font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);
   border-radius:var(--r);padding:10px 12px;cursor:pointer;transition:.12s}
 .pl:hover{border-color:var(--accent)}
 .pl .pi{flex:0 0 24px;width:24px;height:24px;line-height:24px;text-align:center;
   border-radius:50%;background:#1b2c4d;color:#9dbcff;font-size:12px;font-weight:800}
 .pl .pb{flex:1 1 auto;min-width:0}
 .pl .pb b{display:block;font-size:14px;overflow:hidden;text-overflow:ellipsis;
   white-space:nowrap}
 .pl .pb small,.pl .pn2 small{display:block;color:var(--dim);font-size:11px}
 .pl .pn2{flex:0 0 auto;text-align:right;min-width:66px;
   font-variant-numeric:tabular-nums}
 .pl .pn2 b{font-size:15px;font-weight:800} .pl .pn2 b.buy{color:var(--warn)}
 /* link/QR do telemóvel (modo edição) */
 .lig{display:flex;gap:14px;align-items:flex-start;background:var(--card);
   border:1px solid var(--line2);border-radius:var(--r2);padding:13px;
   margin-bottom:14px;flex-wrap:wrap}
 .lig img{border-radius:8px;background:#fff;flex:0 0 auto}
 .lig>div{flex:1 1 240px;min-width:0}
 .lig code{background:#0f141c;padding:1px 5px;border-radius:4px;
   overflow-wrap:anywhere}
 .btn.sm{padding:3px 9px;font-size:11px}
 .toast{position:fixed;left:50%;transform:translateX(-50%);bottom:22px;z-index:9;
   background:#1b2c4d;border:1px solid var(--accent);color:#fff;font-size:13px;
   padding:10px 16px;border-radius:22px;box-shadow:0 8px 26px #0009}
 /* o aviso do registo automático fica com o «anular» dentro dele, e por isso
    tem de subir acima da barra fixa — senão nascia por baixo dela */
 .toast.aviso{display:flex;align-items:center;gap:12px;bottom:96px;z-index:11;
   background:#123020;border-color:#2f6a45}
 .toast.aviso .btn{margin:0}
 /* BARRA DE MONTAGEM (André, 2026-09-08): o «N de M» e o botão de registar
    sempre à mão, fixos no fundo do ecrã. O botão de hoje vive no fim do passo 1
    — 58 linhas abaixo — e à frente da estante, no telemóvel, ele não o achou. */
 .barra{position:fixed;left:0;right:0;bottom:0;z-index:10;
   background:#0e141ef2;border-top:1px solid var(--line2);
   box-shadow:0 -8px 26px #0008;
   padding:9px 14px calc(9px + env(safe-area-inset-bottom,0px))}
 .barra[hidden]{display:none}
 body.combarra .wrap{padding-bottom:118px}
 .barra .bi{max-width:1180px;margin:0 auto;display:flex;gap:12px;
   align-items:center;flex-wrap:wrap}
 .barra .bt{flex:1 1 230px;min-width:0}
 .barra .bt b{font-size:13.5px;display:block;overflow:hidden;
   text-overflow:ellipsis;white-space:nowrap}
 .barra .bt small{color:var(--muted);font-size:11.5px;
   font-variant-numeric:tabular-nums}
 .barra .pg{height:7px;border-radius:6px;background:#1a212c;overflow:hidden;
   margin-top:5px}
 .barra .pg i{display:block;height:100%;background:var(--accent);
   transition:width .18s}
 .barra .ba{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
 .barra.cheia{border-top-color:var(--add);background:#0d1a12f2}
 .barra.cheia .pg i{background:var(--add)}
 .barra.cheia .btn.pri{background:#1d7a48;border-color:#2f9c5e}
 @media(max-width:640px){
   .barra .bt{flex:1 1 100%} .barra .ba{width:100%}
   .barra .ba .btn.pri{flex:1 1 auto;text-align:center}
   body.combarra .wrap{padding-bottom:150px}
 }
 footer{margin-top:28px;color:var(--muted);font-size:12.5px;
   border-top:1px solid var(--line);padding-top:14px}
 @media(max-width:640px){
   .wrap{padding:14px 11px 60px} h1{font-size:20px}
   .tabs a{flex:1 1 calc(50% - 8px);font-size:13px;padding:10px 6px}
   .cards{grid-template-columns:repeat(auto-fill,minmax(50px,1fr))}
   table.vt td.rz,table.vt th.rz{display:none}
   .num{min-width:calc(50% - 6px)}
 }
</style></head><body><div class="wrap">
<header><h1>🧰 Deckboxes</h1>
<div class="lead" id="resumo"></div>
%TABS%
</header>
<nav class="decktabs" id="decktabs" role="tablist" aria-label="Caixas e vistas"></nav>
<main id="vista" role="tabpanel" tabindex="-1" aria-live="polite"></main>
<footer>
<b>Cada deck é uma caixa.</b> Esta é a página dos decks: a lista, o que falta comprar,
o que tirar da coleção para o montar e o que sobra para vender. Uma cópia física entra
numa caixa e <b>só numa</b> — quem conta é a alocação, não a coleção inteira (essa
aparece como informação secundária em cada carta).
<b style="color:var(--add)">Verde</b> = está nesta caixa ·
<b style="color:var(--gold)">âmbar</b> = tens a carta mas não está aqui ·
<b style="color:var(--warn)">vermelho</b> = não tens nenhuma, é compra ·
<b>⚔</b> = partilhada com outra caixa.
Dentro do âmbar há <b>duas coisas diferentes</b>, e a página diz sempre qual:
<b>📦 em &lt;caixa&gt;</b> — a cópia está mesmo sleevada lá dentro, vais àquela caixa
buscá-la — e <b>🗂️ na Colecção, destinada a &lt;caixa&gt;</b> — está na gaveta de
sempre, só prometida por prioridade a uma caixa que ainda não está montada; essa
podes tirá-la já, no passo 1 do painel <b>Montar</b>. Nenhuma das duas se compra.
Os <b>permanentes</b> escolhem as cartas primeiro; uma <b>candidata</b> fica com o que
sobrar. Quem manda é o <code>colecao_config.json → caixas</code>; para mexer nele com
botões, corre <code>python webapp.py</code> no PC (porto 8771) — e aí a aba
<b>Plano</b> dá-te um QR para abrires isto no telemóvel, à frente da estante.
A lista para vender é uma <b>sugestão a confirmar</b>. Atualiza diariamente.
</footer>
</div>
<div class="barra" id="barra" hidden aria-live="polite"></div>
<script id="dados" type="application/json">%DADOS%</script>
<script>
const D = JSON.parse(document.getElementById('dados').textContent);
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const eur = v => v ? (v.toFixed(2).replace('.', ',') + ' €') : '—';
const art = sid => sid
  ? `https://cards.scryfall.io/small/front/${sid[0]}/${sid[1]}/${sid}.jpg` : '';
const cor = p => p >= 90 ? 'var(--add)' : p >= 60 ? 'var(--gold)' : 'var(--warn)';
const pin = p => p >= 90 ? 'ok' : p >= 60 ? 'mid' : 'low';
/* Acima disto (por cópia) a compra é uma decisão à parte, não uma ida ao
   Cardmarket: a Mishra's Workshop sozinha vale mais do que o resto da lista
   toda junta. A aba Comprar separa os dois totais em vez de os somar. */
const CARA = 100;
/* O motivo da venda nova ("Premodern: não usada por nenhum deck"), vindo do
   Python (`loadout.RAZAO_PREMODERN`). Escrito à mão aqui, bastava mudar uma
   vírgula do lado de lá para o parágrafo desaparecer sem erro nenhum. */
const PM_RAZAO = D.pm_razao || '';

/* Estado no browser: a aba aberta, o filtro e o que já foi arrumado. É a mesma
   ideia do checkmark "atualizado" do meusdecks — o que é do André fica no
   aparelho dele, não na base de dados. */
const KEY = 'deckboxes.v2';
let P = {};
try { P = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { P = {}; }
P.feitos = P.feitos || {};
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(P)); } catch (e) {} };
let aba = P.aba || 'plano';
let filtro = P.filtro || 'tudo';
let grupo = P.grupo || 'estado';     /* estado | tipo — como agrupar a grelha */
let grande = !!P.grande;             /* imagens maiores, para conferir a caixa */
/* A ordem dos tipos é a que ele pediu (2026-08-31): criaturas primeiro, terras
   no fim. Vem do `mtgvault.paginas` do lado do Python — aqui é só a etiqueta. */
const TIPOS = ['Creature', 'Planeswalker', 'Sorcery', 'Instant', 'Artifact',
               'Enchantment', 'Land', 'Other'];
const TIPO_PT = { Creature: 'Criaturas', Planeswalker: 'Planeswalkers',
  Sorcery: 'Feitiços', Instant: 'Instantâneos', Artifact: 'Artefactos',
  Enchantment: 'Encantamentos', Land: 'Terras', Other: 'Outros' };

function toast(txt) {
  const d = document.createElement('div');
  d.className = 'toast'; d.textContent = txt;
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 2600);
}

/* ---------------------------------------------------------------- cabeçalho */
function renderResumo() {
  const r = D.resumo;
  $('#resumo').innerHTML =
    `${D.caixas.length} caixas (<b>${r.permanentes}</b> permanentes · `
    + `${r.candidatos} candidatas) · comprar <b>${r.comprar}</b> cópias por `
    + `<b>${eur(r.custo)}</b> · ir buscar a outra caixa <b>${r.nmont}</b> `
    + `(mais <b>${r.nres}</b> na gaveta destinadas a outra caixa`
    + (r.nfut ? ` e <b>${r.nfut}</b> por comprar` : '') + `) · `
    + `arrumar <b>${r.arrumar}</b> · vender <b>${eur(r.venda)}</b>`
    + (D.editable ? ' · <b style="color:var(--add)">modo edição</b>' : '')
    + `<br><span class="dim">dados de ${esc(D.gerado)}</span>`;
}

function renderTabs() {
  const nav = $('#decktabs');
  const arr = D.arrumar.copias + ' cópias'
    + (D.arrumar.copias_actualizar ? ` · ${D.arrumar.copias_actualizar} a actualizar`
                                   : '');
  /* O PLANO à cabeça: é a pergunta dele de 2026-09-08 — "por onde começo?" —
     e a resposta é uma ordem, não uma lista de caixas por ordem alfabética. */
  const porMontar = D.montagem.filter(m => !m.montado).length;
  const fixas = [['plano', '🗺️ Plano', porMontar + ' por montar'],
                 ['todas', '▦ Todas', ''], ['arrumar', '📥 Arrumar', arr],
                 ['partilhadas', '🔁 Partilhadas', D.partilhadas.length + ' cartas'],
                 ['comprar', '🛒 Comprar', D.resumo.comprar + ' cópias'],
                 ['vender', '💰 Vender', eur(D.resumo.venda)]];
  /* SUGESTÕES: só existe quando há Premodern configurado. Uma aba vazia numa
     fila de vinte é ruído — e sem caixas de Premodern não há pergunta nenhuma. */
  if (D.premodern && D.premodern.activo) {
    fixas.push(['sugestoes', '💡 Sugestões',
                D.premodern.sugestoes + ' por decidir']);
  }
  let h = '';
  /* `role=tab` + `aria-selected` para o leitor de ecrã dizer qual está aberta,
     e `tabindex=-1` nas outras: numa fila de 19 abas, o Tab passava por todas
     antes de chegar ao conteúdo. Andar entre elas é com as setas (ver abaixo),
     que é o que o padrão de tablist manda. */
  const tab = (id, dentro, extra) =>
    `<button class="dt${aba === id ? ' on' : ''}${extra || ''}" role="tab"`
    + ` aria-selected="${aba === id}" tabindex="${aba === id ? 0 : -1}"`
    + ` data-aba="${esc(id)}">${dentro}</button>`;
  for (const [id, lbl, sub] of fixas) {
    h += tab(id, lbl + (sub ? `<small>${esc(sub)}</small>` : ''));
  }
  for (const c of D.caixas) {
    const p = c.vazio ? '—' : c.pct + '%';
    h += tab(c.slot,
      `<span><i class="pin ${c.vazio ? 'low' : pin(c.pct)}"></i>${esc(c.nome)}</span>`
      + `<small>${p}${c.vazio ? '' : ` · ${c.tenho}/${c.precisa}`}</small>`,
      c.permanente ? '' : ' cand');
  }
  nav.innerHTML = h;
  const botoes = [...nav.querySelectorAll('.dt')];
  botoes.forEach((b, i) => {
    b.onclick = () => ir(b.dataset.aba);
    b.onkeydown = (e) => {
      const d = { ArrowRight: 1, ArrowLeft: -1, Home: -i, End: botoes.length - 1 - i };
      if (!(e.key in d)) return;
      e.preventDefault();
      ir(botoes[(i + d[e.key] + botoes.length) % botoes.length].dataset.aba);
      const novo = nav.querySelector('.dt.on');
      if (novo) novo.focus();
    };
  });
  const on = nav.querySelector('.dt.on');
  if (on) on.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}

function ir(id) { aba = id; P.aba = id; save(); renderTabs(); render(); }

/* ------------------------------------------------------------------ caixa */
function cardTile(c) {
  /* ONDE A CARTA ESTÁ (André, 2026-09-08). A frase vem pronta do Python
     (`loadout.onde_esta`): "em UW Replenish" só quando a cópia está MESMO lá
     dentro, e "na Colecção — destinada ao UW Replenish" enquanto a caixa não
     está montada. Compô-la aqui a partir do `c.noutra` era o que mandava o
     André à estante procurar uma carta dentro de uma caixa que não existe.
     O selo curto do canto usa a mesma repartição: 📦 quando é uma ida a outra
     caixa, 🗂️ quando é a gaveta de sempre. */
  const onde = c.est === 'sub' ? (c.onde || []).join(' · ') : '';
  const selo = !onde ? '' : c.nmont ? `📦 ${c.nmont}×` : `🗂️ ${c.nres}×`;
  const tit = [c.nm, c.est === 'have' ? `tens ${c.got}/${c.need}`
    : `falta ${c.missing}`,
    onde,
    Object.entries(c.alt).map(([k, v]) => `${v}× ${k}`).join('; '),
    c.comprar ? `comprar ${c.comprar}` : '',
    c.bloq ? `limite de playset: falta ${c.bloq} que não se compra` : '',
    c.lotes.map(l => `${l.q}× ${l.local}`).join(' · '),
    /* "quantas tenho ao todo" — a informação secundária que vinha da página dos
       decks. Secundária de propósito: o número que manda nesta caixa é o da
       alocação, e é ele que está no canto do cartão. */
    c.col ? `na colecção inteira: ${c.col}` : '',
    c.so_de.length ? 'só da variante ' + c.so_de.join('/') : ''
  ].filter(Boolean).join(' — ');
  const q = c.need > 1 || c.est !== 'have'
    ? `<span class="cq">${c.got}/${c.need}</span>` : '';
  return `<div class="cd ${c.est}" title="${esc(tit)}">`
    + (c.sid ? `<img loading="lazy" src="${art(c.sid)}" alt="${esc(c.nm)}">` : '')
    + q + (c.cf ? '<span class="cf">⚔</span>' : '')
    + (selo ? `<span class="onde">${esc(selo)}</span>` : '') + '</div>';
}

/* O ESTADO da caixa numa palavra (v6): candidata < permanente < montada <
   congelada. Era três bandeiras soltas — e nada impedia "montado mas candidato",
   que não quer dizer nada: um deck sleevado na estante não é um candidato. */
const ESTADO = {
  candidata: ['cand', 'candidata — recebe o que sobrar'],
  permanente: ['perm', '★ permanente — escolhe as cartas primeiro'],
  montada: ['ok', '✅ montada'],
  congelada: ['ok', '🧊 montada e congelada — só mexe para actualizar'],
};

function badges(c) {
  const [cls, txt] = ESTADO[c.estado] || ESTADO.permanente;
  let h = `<span class="bdg ${cls}">${esc(txt)}</span>`;
  if (c.vazio) h += '<span class="bdg wt">❓ deck por escolher</span>';
  else if (!c.montado) h += '<span class="bdg">🔧 a montar</span>';
  /* «N de M na caixa» (André, 2026-09-08). Uma caixa registada A MEIO não é uma
     caixa montada nem uma caixa por montar, e dizer só "🔧 a montar" apagava o
     trabalho já feito — que é exactamente o que o registo parcial veio guardar. */
  if (!c.montado && c.montar && c.montar.dentro) {
    h += `<span class="bdg cand">📦 ${c.montar.dentro} de `
      + `${c.montar.dentro + c.montar.marcar_q} na caixa</span>`;
  }
  /* A classe vem no payload (`loadout.rotulo_material`). Decidi-la aqui com
     /foil/ pintava de dourado o chip "só nonfoil" do cEDH — "nonfoil" contém
     "foil", e um teste de substring nunca serve para isto. */
  for (const [ico, txt, cls] of c.regras) {
    h += `<span class="bdg ${cls || ''}">${ico} ${esc(txt)}</span>`;
  }
  if (c.variantes.length) h += `<span class="bdg">⇄ ${c.variantes.length} variantes</span>`;
  h += `<span class="bdg">#${c.prioridade} na alocação</span>`;
  /* De ONDE veio a ordem. Quando é automática (André, 2026-09-08: "para já a
     prioridade vem por ordem de % completo") a página tem de o dizer: sem isto
     o "#4 na alocação" parecia um número que ele tinha escolhido, e não era. */
  if (c.prioridade_por === 'pct' && c.posicao_grupo) {
    h += `<span class="bdg auto" title="Ordem automática dentro do grupo `
      + `${esc(c.grupo || '')}: a caixa mais perto de fechar escolhe as cartas `
      + `primeiro. A percentagem é a da colecção inteira, antes de alocar`
      + (c.pct_coleccao === null ? '' : ` — ${c.pct_coleccao}%`) + `.">`
      + `#${c.posicao_grupo} por % completo</span>`;
  }
  return h;
}

/* `detalhe` acrescenta, por baixo do nome, o requisito de material e as caixas
   que pedem a carta — é o que a aba Comprar precisa e o cartão de uma caixa
   não (ali a caixa e o material já estão no cabeçalho). A mesma função para as
   duas: o botão "copiar" copia sempre exactamente a lista que está à vista. */
/* --------------------------------------------------------------- MONTAR
   O fluxo que ele pediu a 2026-09-08, por esta ordem: (1) tirar da Colecção,
   (2) comprar o que falta, (3) quando as compras chegarem, fotografar. Os três
   passos ficam juntos na aba da caixa, porque é um gesto só — montar o deck. */
/* O ID de um "visto", num sítio só. A grelha desenha-o, a BARRA conta por ele e
   o registo manda os `copy_id` que ele traz. Escrito à mão em três sítios (como
   estava), bastava mudar uma barra vertical num deles para a barra passar a
   dizer "0 de 58" sem um único erro — o padrão do `event_tier`, do lado do
   browser. Os três prefixos: `mt` a grelha, `bs` as básicas, `mo` as destinadas
   a outra caixa. As básicas não levam bloco (uma básica é uma pilha só). */
function vistoId(tipo, slot, m, nm) {
  const base = `${tipo}|${slot}|${m.copy_id}|${nm == null ? m.nm : nm}`;
  return tipo === 'bs' ? base : `${base}|${m.board}`;
}

/* Tudo o que há para MARCAR no passo 1 de uma caixa: main, sideboard e as
   básicas que estão REGISTADAS na base. É a lista por que a barra conta e por
   que o registo escolhe as cópias — a MESMA que desenhou as checkboxes.

   Fora dela, de propósito: as básicas a granel (não têm cópia registada, não
   têm nada para marcar — e contá-las fazia a caixa nunca fechar por causa de 17
   Island que ele tem numa pilha em casa) e o bloco «destinadas a outra caixa»
   (são de outra caixa; esperá-las era impedir esta de ficar completa). */
function montarItens(c) {
  const M = c.montar;
  if (!M) return [];
  const out = [];
  for (const b of (M.blocos || [])) {
    for (const m of b.movs) {
      out.push({ id: vistoId('mt', c.slot, m), q: m.q, copy: m.copy_id });
    }
  }
  for (const b of (M.basicas || [])) {
    for (const m of b.tirar) {
      out.push({ id: vistoId('bs', c.slot, m, b.nm), q: m.q, copy: m.copy_id });
    }
  }
  return out;
}

/* Quanto já está marcado nesta caixa, e que cópias são. `completo` é por ITEM e
   não por quantidade: duas linhas do mesmo `copy_id` (a mesma carta no main e
   no side) são duas idas à gaveta e contam as duas. */
function montarEstado(c) {
  const itens = montarItens(c);
  const marcados = itens.filter(i => P.feitos[i.id]);
  return { itens, total: itens.reduce((s, i) => s + i.q, 0),
           n: marcados.reduce((s, i) => s + i.q, 0),
           copias: [...new Set(marcados.map(i => i.copy))],
           completo: itens.length > 0 && marcados.length === itens.length };
}

/* As cópias marcadas no bloco «destinadas a outra caixa». Lê o MESMO `P.feitos`
   que as outras — antes isto era uma consulta ao DOM, e uma consulta ao DOM não
   funciona a partir da barra (ela vive fora da vista). */
function deOutraMarcadas(c) {
  const M = c && c.montar;
  if (!M) return [];
  const out = [];
  for (const b of (M.blocos_de_outra || [])) {
    for (const m of b.movs) {
      if (P.feitos[vistoId('mo', c.slot, m)]) out.push(m.copy_id);
    }
  }
  return out;
}

function montarHTML(c) {
  const M = c.montar;
  if (!M) return '';
  const total = M.tirar.reduce((s, m) => s + m.q, 0);
  const gav = Object.entries(M.por_gaveta)
    .map(([k, v]) => `${esc(k)} <b>${v}</b>`).join(' · ');
  /* Uma caixa que ele diz montada e de que o vault não sabe o conteúdo não se
     monta: CONFIRMA-SE. Apresentar-lhe a lista inteira como "tirar da colecção"
     era mandá-lo desmontar um deck que está na estante para o montar outra vez. */
  let h = `<div class="montar"><div class="mh"><b>${c.confirmar ? '✅ Confirmar'
      : '🧱 Montar'} ${esc(c.nome)}</b>`
    + `<span class="dim">${c.confirmar
        ? 'dizes que está montada, mas ainda não me disseste o que lá está'
        : c.montado ? 'já montada — isto é o que falta ajustar'
                    : 'passo a passo'}</span></div>`;
  /* passo 1 -------------------------------------------------------------- */
  h += `<div class="passo"><div class="ph"><span class="pn">1</span>`
    + `<b>${c.confirmar ? 'Confirmar que está montada com estas cartas'
                        : 'Tirar da colecção'}</b>`
    + `<span class="dim">${total} cópias${gav ? ' · ' + gav : ''}</span></div>`
    + (c.confirmar ? `<p class="nota">São as cópias que a alocação dá a esta `
        + `caixa. Se é isto que está lá dentro, um clique regista — e o vault `
        + `pára de te mandar procurá-las.</p>` : '');
  /* As básicas contam para "há alguma coisa a tirar?": uma caixa em que só
     faltem as 23 Snow-Covered Plains não pode dizer "não falta tirar nada" e
     mostrar 23 terras por baixo. */
  const basTirar = (M.basicas || []).some(b => b.tirar.length);
  /* O bloco «destinadas a outra caixa» conta para "há alguma coisa a tirar?":
     uma caixa a que a alocação não dá nada, mas cujas cartas estão todas na
     gaveta à espera de outra caixa por montar, tem MUITO para tirar — e sem
     isto dizia "não falta tirar nada" com 20 cartas listadas por baixo. */
  if (!M.tirar.length && !basTirar && !(M.de_outra || []).length) {
    h += `<p class="ok2">✓ Não falta tirar nada: tudo o que a alocação dá a esta `
      + `caixa já está lá dentro${M.ja ? ` (${M.ja} cópias)` : ''}.</p>`;
    h += basicasHTML(M);
  } else {
    /* DOIS BLOCOS: main e sideboard (André, 2026-09-08 — "para ficar separado
       dentro da mesma caixa"). Quem os parte é o Python (`blocos_de_board`), e
       dentro de cada um a ordem é a do binder: cor e depois nome. A carta que
       joga nos dois vem nos dois — são duas pilhas, não uma linha repetida. */
    for (const b of (M.blocos || [])) {
      let cor = null;
      h += `<div class="bhdr">${esc(b.titulo)}`
        + `<span>${b.q}${b.de ? ' de ' + b.de : ''}</span></div><div class="mvs">`;
      for (const m of b.movs) {
        if (m.cor !== cor) {
          cor = m.cor;
          h += `<div class="corhdr">${esc(m.cor_nome)}</div>`;
        }
        const id = vistoId('mt', c.slot, m);
        const feito = !!P.feitos[id];
        h += `<label class="mv${feito ? ' feito' : ''}" data-id="${esc(id)}">`
          + `<input type="checkbox"${feito ? ' checked' : ''}>`
          + `<span class="q">${m.q}×</span>`
          + `<span class="nm">${esc(m.nm)}`
          + `<small>${esc(m.set)}${m.foil ? ' ✨' : ''} ${esc(m.lang)}</small></span>`
          + `<span class="to">de ${esc(m.de)}</span></label>`;
      }
      h += `</div>`;
    }
    h += basicasHTML(M);
    h += deOutraHTML(M);
    /* O botão só se DESENHA no modo edição: no site publicado o endpoint não
       existe, e um botão que não faz nada é pior do que não haver botão. */
    h += D.editable
      ? `<div class="seg"><button class="btn pri" data-act="${c.confirmar
            ? 'confirmar' : 'montado'}" data-slot="${esc(c.slot)}">`
        + (c.confirmar ? '✅ Sim, está montada assim'
                       : '📦 Sleevado e na caixa') + `</button></div>`
      : `<p class="nota">Quando estiver tudo sleevado na caixa, regista-o no `
        + `modo edição (<code>python webapp.py</code> no PC, ou o QR da aba `
        + `<b>Plano</b> no telemóvel) — é o que faz o vault parar de te mandar `
        + `procurar estas cartas.</p>`;
  }
  if (M.devolver.length) {
    h += `<p class="nota">🔄 E <b>${M.devolver.reduce((s, m) => s + m.q, 0)}</b> `
      + `cópias que estão na caixa e a lista de hoje já não pede — vê a aba `
      + `<b>Arrumar</b>, secção «actualizar decks montados».</p>`;
  }
  h += `</div>`;
  /* passo 2 -------------------------------------------------------------- */
  h += `<div class="passo"><div class="ph"><span class="pn">2</span>`
    + `<b>Comprar o que falta</b><span class="dim">${c.comprar} cópias · `
    + `${eur(c.custo)}${c.req ? ' · ' + esc(c.req) : ''}`
    + (M.basicas_comprar ? ` · + ${M.basicas_comprar} básicas (${eur(M.basicas_custo)})`
                         : '') + `</span></div>`
    + (c.wantlist.length || M.basicas_comprar
       ? wantlistHTML(c.wantlist, c.marca, '', false, M.basicas, M.edicao)
       : `<p class="ok2">✓ Nada a comprar para esta caixa.</p>`)
    + (c.noutra ? `<p class="nota">📦 Mais <b>${c.noutra}</b> cópias estão noutra `
        + `caixa: essas vão-se buscar, não se compram.</p>` : '')
    + (c.bloqueado ? `<p class="nota">🔒 E <b>${c.bloqueado}</b> que o limite de `
        + `playset (${c.playset} por carta em ${esc(c.grupo || 'todo o grupo')}) `
        + `não deixa comprar — vê a secção «limite de playset» acima.</p>` : '')
    + `</div>`;
  /* passo 3 -------------------------------------------------------------- */
  h += `<div class="passo"><div class="ph"><span class="pn">3</span>`
    + `<b>Quando as compras chegarem</b></div>`
    + `<p class="nota">Tira foto às cartas novas e deita-as em `
    + `<code>pendentes\\</code> (ou manda-as pela app do GitHub para o repo `
    + `<b>mtg-fotos-novas</b>). O vault importa-as, e esta caixa recalcula-se `
    + `sozinha na corrida seguinte — não há nada para marcar à mão.</p></div>`;
  return h + `</div>`;
}

/* ------------------------------------------------------- BARRA DE MONTAGEM
   André, 2026-09-08, à letra: *"Não é mais fácil confirmares que eu seleccionei
   todas as cartas do deck, e assim eu confirmo que montei o deck?"* Ele estava à
   frente da estante, no telemóvel, a marcar cartas — e não encontrou o «Sim,
   está montada assim», que fica no fim de 58 linhas.

   A barra é fixa no fundo do ecrã enquanto a aba de uma caixa está aberta: o
   «N de M», a barra de progresso e o botão de registar SEMPRE à mão. Só no modo
   edição: no site publicado o endpoint não existe, e uma barra que conta cópias
   e não regista nada seria pior do que barra nenhuma. */

/* Que acção regista. O gesto de hoje continua a ser o mesmo — «sleevado e na
   caixa» / «sim, está montada assim» — e não se inventa um segundo caminho para
   ele. O `registar` novo é o que faltava: o registo A MEIO.
   Uma caixa que JÁ se diz montada nunca usa o `montado`: esse ALTERNA, e
   alterná-lo aqui desmontava-a — que é o contrário do que o botão diz. */
function actoDeRegisto(c, completo) {
  if (!completo) return 'registar';
  if (c.confirmar) return 'confirmar';
  return c.montado ? 'registar' : 'montado';
}

function barraHTML(c) {
  const e = montarEstado(c);
  const pct = e.total ? Math.round(e.n * 100 / e.total) : 0;
  const fora = deOutraMarcadas(c).length;
  const rot = e.completo
    ? (c.confirmar ? '✅ Sim, está montada assim' : '✅ Registar como montada')
    : `Registar as ${e.n} marcadas`;
  /* Com zero marcadas não há registo nenhum a fazer: o botão fica desactivado
     em vez de desaparecer, para a barra não mudar de forma a cada clique.
     O `data-estado` diz em palavras o que a cor diz em verde: a barra tem de
     ser legível por quem não vê a cor — e é por ele que o teste a lê. */
  const grau = e.completo ? 'cheia' : (e.n ? 'meio' : 'vazio');
  return `<div class="bi" data-estado="${grau}"><div class="bt">`
    + `<b>${e.completo ? '✅' : '🧱'} ${c.confirmar ? 'Confirmar' : 'Montar'} `
    + `${esc(c.nome)}</b>`
    + `<small>${e.n} de ${e.total} cópias marcadas`
    + (e.completo ? ' · tudo marcado' : '')
    + (fora ? ` · +${fora} de outra caixa` : '') + `</small>`
    + `<div class="pg"><i style="width:${pct}%"></i></div></div>`
    + `<div class="ba">`
    + `<button class="btn sm" id="b-tudo">marcar tudo</button>`
    + `<button class="btn sm" id="b-limpar">limpar</button>`
    + `<button class="btn pri" id="b-reg" data-slot="${esc(c.slot)}"`
    + `${e.n ? '' : ' disabled'}>${rot}</button></div></div>`;
}

function renderBarra() {
  const b = $('#barra');
  if (!b) return;
  const c = D.caixas.find(x => x.slot === aba);
  const mostra = !!(D.editable && c && c.montar && montarItens(c).length);
  b.hidden = !mostra;
  document.body.classList.toggle('combarra', mostra);
  b.className = 'barra' + (mostra && montarEstado(c).completo ? ' cheia' : '');
  b.innerHTML = mostra ? barraHTML(c) : '';
  if (mostra) ligarBarra(c);
}

function ligarBarra(c) {
  const t = $('#b-tudo'), l = $('#b-limpar'), r = $('#b-reg');
  /* «Marcar tudo» NÃO dispara o registo automático, mesmo com tudo marcado: é
     um atalho para depois desmarcar duas ou três, não uma afirmação de que a
     caixa está montada. O botão fica verde ao lado, a um toque. */
  if (t) t.onclick = () => {
    for (const i of montarItens(c)) P.feitos[i.id] = 1;
    save(); render();
  };
  if (l) l.onclick = () => { limparFeitos(c.slot); render(); };
  if (r) r.onclick = () => registar(c, r);
}

/* Os vistos desta caixa saem do aparelho quando o registo entra na base: a
   partir daí quem diz o que está lá dentro é a `copy_allocation`, e deixar as
   checkboxes marcadas era ter duas respostas para a mesma pergunta. Devolve o
   que tirou, para o «anular» o poder repor — desfazer o registo e ficar com a
   grelha por marcar era pedir-lhe que voltasse a marcar 58 cartas. */
function limparFeitos(slot) {
  const pref = ['mt|', 'bs|', 'mo|'].map(t => t + slot + '|');
  const tirados = {};
  for (const k of Object.keys(P.feitos)) {
    if (pref.some(p => k.startsWith(p))) {
      tirados[k] = P.feitos[k];
      delete P.feitos[k];
    }
  }
  save();
  return tirados;
}

/* MARCAR A ÚLTIMA = MONTADA. Só quando ele ACABA de marcar uma cópia — abrir a
   aba com tudo já marcado de ontem não regista nada, senão a página escrevia na
   base por ela ser aberta, que é o contrário de um gesto. */
function autoRegistar() {
  if (!D.editable || !D.auto_registar) return;
  const c = D.caixas.find(x => x.slot === aba);
  if (!c || !c.montar) return;
  if (!montarEstado(c).completo) return;
  registar(c, $('#b-reg'));
}

async function registar(c, btn) {
  const e = montarEstado(c);
  if (!e.n) return;
  if (btn) btn.disabled = true;
  const act = actoDeRegisto(c, e.completo);
  try {
    const r = await gravar('api/caixa', { act, slot: c.slot, copias: e.copias,
                                          de_outra: deOutraMarcadas(c) });
    if (!r.ok && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    const vistos = limparFeitos(c.slot);
    avisoRegisto(c, e.completo
      ? `✅ ${c.nome} registada como montada`
      : (j.msg || `${c.nome}: ${e.n} cópias registadas`), vistos);
  } catch (err) {
    if (btn) btn.disabled = false;
    toast('Não deu: ' + err.message);
  }
}

/* O aviso com o ANULAR. Um `toast()` normal desaparece sozinho e não tem onde
   carregar; este fica os segundos que o config disser (`montar.anular_segundos`)
   e leva o botão que desfaz. Só DEPOIS é que a página recarrega — recarregar já
   era deitar fora a única oportunidade de voltar atrás. */
function avisoRegisto(c, texto, vistos) {
  const seg = Number(D.anular_segundos || 0);
  if (!seg) { toast(texto); location.reload(); return; }
  const d = document.createElement('div');
  d.className = 'toast aviso';
  d.innerHTML = `<span>${esc(texto)}</span>`
    + `<button class="btn sm" id="b-anular">anular</button>`;
  document.body.appendChild(d);
  let fechado = false;
  const b = d.querySelector('#b-anular') || $('#b-anular');
  if (b) b.onclick = () => { fechado = true; d.remove(); anularRegisto(c, vistos); };
  setTimeout(() => { if (!fechado) { d.remove(); location.reload(); } }, seg * 1000);
}

async function anularRegisto(c, vistos) {
  try {
    const r = await gravar('api/caixa', { act: 'anular', slot: c.slot });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    /* Os vistos voltam com a alocação: o que ele desfez foi o registo, não o
       trabalho de ter marcado as cartas uma a uma. */
    Object.assign(P.feitos, vistos || {});
    save();
    toast(j.msg || 'Registo anulado.');
  } catch (e) { toast('Não deu anular: ' + e.message); }
  location.reload();
}

/* --------------------------------------- DESTINADAS A OUTRA CAIXA (montar
   fora de ordem). André, 2026-09-08: *"De todas as cartas, só o Stiflenought
   está em deckbox; o resto ainda nada está em deckbox."* Se ele abrir a
   Enchantress antes do UW Replenish, as cartas que o Replenish há-de levar
   estão na mesma gaveta, ao lado das outras. A alocação é um plano; a estante
   é a realidade — e quem manda é a estante.

   Vêm POR MARCAR, ao contrário do bloco de cima: tirá-las é uma decisão (a
   outra caixa passa a vir buscá-las aqui) e não uma consequência de abrir a
   aba. O «sleevado e na caixa» só regista as que estiverem marcadas. */
function deOutraHTML(M) {
  const bs = M.blocos_de_outra || [];
  if (!bs.length) return '';
  let h = `<div class="dout"><div class="flh">⚠️ Destinadas a outra caixa`
    + `<span class="dim">${M.copias_de_outra} cópias · por marcar</span></div>`
    + `<p class="nota">Estas cópias estão na gaveta, como todas as outras — a `
    + `alocação prometeu-as a outra caixa por prioridade, mas essa caixa ainda `
    + `não está montada. <b>Podes tirá-las já.</b> O que marcares fica `
    + `registado nesta caixa, e a outra passa a dizer «em ${esc(M.caixa || 'esta caixa')}».</p>`;
  for (const b of bs) {
    if (bs.length > 1) {
      h += `<div class="bhdr">${esc(b.titulo)}<span>${b.q}</span></div>`;
    }
    h += `<div class="mvs">`;
    for (const m of b.movs) {
      const id = vistoId('mo', M.slot, m);
      const feito = !!P.feitos[id];
      h += `<label class="mv${feito ? ' feito' : ''}" data-id="${esc(id)}" `
        + `data-copy="${m.copy_id}" data-q="${m.q}">`
        + `<input type="checkbox"${feito ? ' checked' : ''}>`
        + `<span class="q">${m.q}×</span>`
        + `<span class="nm">${esc(m.nm)}`
        + `<small>${esc(m.set)}${m.foil ? ' ✨' : ''} ${esc(m.lang)}</small></span>`
        + `<span class="to">de ${esc(m.de)} · era p/ ${esc(m.destino)}</span></label>`;
    }
    h += `</div>`;
  }
  return h + `</div>`;
}

/* ------------------------------------------------------- TERRENOS BÁSICOS
   "Faltou marcares, para completar o deck, os terrenos básicos necessários!"
   (André, 2026-09-08). Vem DEPOIS do bloco de cores porque é outra gaveta: as
   básicas dele são todas de Unhinged e vivem numa pilha, não no binder por cor.
   Três estados por linha: as que a colecção tem e ainda não estão na caixa
   (com checkbox, como as outras), as que já lá estão, e as que vêm da pilha —
   estas últimas não têm cópia registada, por isso não têm nada para marcar. */
function basicasHTML(M) {
  if (!M.basicas || !M.basicas.length) return '';
  let h = `<div class="bas"><div class="flh">🌱 Terrenos básicos`
    + `<span class="dim">${M.basicas_copias} cópias</span></div><ul class="bl">`;
  for (const b of M.basicas) {
    const det = [];
    for (const m of b.tirar) {
      const id = vistoId('bs', M.slot, m, b.nm);
      const feito = !!P.feitos[id];
      det.push(`<label class="mv${feito ? ' feito' : ''}" data-id="${esc(id)}">`
        + `<input type="checkbox"${feito ? ' checked' : ''}>`
        + `<span class="q">${m.q}×</span>`
        + `<span class="nm">${esc(b.nm)}<small>${esc(m.set)}`
        + `${m.foil ? ' ✨' : ''} ${esc(m.lang)}</small></span>`
        + `<span class="to">de ${esc(m.de)}</span></label>`);
    }
    if (b.ja > 0) det.push(`<span class="bt ok2">✓ ${b.ja} já na caixa</span>`);
    if (b.granel) det.push(`<span class="bt">${b.granel}× das tuas básicas `
      + `(${esc(M.edicao)}) — não estão registadas, não contam para a %</span>`);
    if (b.comprar) det.push(`<span class="bt warn">🛒 ${b.comprar}× a comprar `
      + `${esc(b.req)} (${eur(b.cost)}) — confirma se já tens</span>`);
    h += `<li><b>${b.need}×</b> <span class="wn">${esc(b.nm)}`
      + (b.req ? ` <small>${esc(b.req)}</small>` : '')
      + `</span><div class="bd">${det.join('')}</div></li>`;
  }
  return h + `</ul></div>`;
}

/* O bloco de básicas no TEXTO copiado. Vai comentado com `//`, que o Cardmarket
   ignora: são terras que ele já tem e que não se compram — mandá-las para o
   carrinho como linhas a sério era comprar 17 Island por engano. O que é MESMO
   compra (as Snow-Covered, que não existem em Unhinged) vai em linha normal. */
function basicasTexto(bs, edicao) {
  if (!bs || !bs.length) return '';
  const linhas = ['', '// Basicas'];
  for (const b of bs) {
    if (b.comprar) linhas.push(`${b.comprar} ${b.nm}`
      + (b.req ? ` [${b.req}]` : '') + '   // confirma se ja tens');
    if (b.da_base) linhas.push(`// ${b.da_base} ${b.nm} (na coleccao)`);
    if (b.granel) linhas.push(`// ${b.granel} ${b.nm} (${edicao || 'as tuas'})`);
  }
  return linhas.join('\n');
}

function wantlistHTML(itens, marca, id, detalhe, basicas, edicao) {
  if (!itens.length && !(basicas || []).length) return '';
  const li = itens.map(m => {
    const cara = detalhe && (m.unit || 0) >= CARA;
    const compra = (m.para || []).filter(p => !p.serve);
    const serve = (m.para || []).filter(p => p.serve);
    const sub = !detalhe ? '' : [m.req || '',
      compra.length ? 'para: ' + compra.map(p => `${p.caixa} ${p.q}×`).join(' · ') : '',
      serve.length ? 'serve também: ' + serve.map(p => p.caixa).join(', ') : '']
      .filter(Boolean).join(' — ');
    return `<li><b>${m.q}×</b><span class="wn">${esc(m.nm)}`
      + (m.board === 'side' ? `<span class="sb">SB</span>` : '')
      + (cara ? `<span class="cara">💶 cara</span>` : '')
      + (m.partilhada ? `<span class="part">🔁 partilhada por `
        + `${m.partilhada} caixas</span>` : '')
      + (sub ? `<small>${esc(sub)}</small>` : '')
      + `</span><span class="pz">${eur(m.cost)}</span></li>`;
  }).join('');
  /* DOIS formatos, porque servem dois sítios (André, 2026-09-08):
       · «Cardmarket» — só `N Nome`, que é o que a caixa de importação dele
         aceita. Quando a mesma carta se compra em dois materiais, vai UMA LINHA
         POR VERSÃO: somar as duas dava uma quantidade que nenhuma das versões
         precisa;
       · «com material» — `N Nome [PT]`, para conferir a oferta antes de pagar.
         Comprar a versão errada é comprar duas vezes. */
  const porVersao = [];
  for (const m of itens) {
    const mats = [...new Set((m.para || []).filter(p => !p.serve)
      .map(p => p.mat || ''))];
    if (mats.length > 1) {
      for (const mt of mats) {
        const q = (m.para || []).filter(p => !p.serve && (p.mat || '') === mt)
          .reduce((s, p) => s + p.q, 0);
        if (q) porVersao.push({ q, nm: m.nm, mat: mt, board: m.board });
      }
    } else {
      porVersao.push({ q: m.q, nm: m.nm, mat: m.mat || mats[0] || '',
                      board: m.board });
    }
  }
  /* O SIDEBOARD separa-se também no texto copiado, com `// Sideboard` — que o
     Cardmarket ignora sem dar erro. Sem separador, a lista colada era 75 linhas
     seguidas e ele voltava a ter de descobrir onde acabava o main. Só aparece
     quando a lista TEM sideboard: um cabeçalho para um bloco vazio é ruído.
     (A aba Comprar junta as compras de várias caixas: aí a linha não tem bloco
     — `board` vem indefinido — e o texto sai como sempre saiu.)
     As BÁSICAS vêm a seguir ao sideboard, num `// Basicas` (2026-09-08). */
  const bt = basicasTexto(basicas, edicao);
  const texto = (fn) => {
    const main = porVersao.filter(m => m.board !== 'side');
    const side = porVersao.filter(m => m.board === 'side');
    const linhas = main.map(fn);
    if (side.length) linhas.push('// Sideboard', ...side.map(fn));
    return linhas.join('\n') + bt;
  };
  const so = texto(m => `${m.q} ${m.nm}`);
  const comMat = texto(m => `${m.q} ${m.nm}` + (m.mat ? ` [${m.mat}]` : ''));
  return `<div class="blk" id="${id || ''}"><div class="flh">🛒 Comprar`
    + (marca ? ` <span class="mrk">${esc(marca)}</span>` : '')
    + `<span class="dim">${itens.length} cartas</span>`
    + `<button class="cpbtn" onclick="copiar(this,'cm')" aria-label="Copiar as `
    + `${itens.length} cartas no formato do Cardmarket">copiar p/ Cardmarket`
    + `</button>`
    + `<button class="cpbtn" onclick="copiar(this,'mat')" aria-label="Copiar as `
    + `${itens.length} cartas com o material de cada uma">copiar com material`
    + `</button></div>`
    + `<ul class="fl">${li}</ul>`
    + `<textarea class="cmk" data-cmk="cm" readonly>${esc(so)}</textarea>`
    + `<textarea class="cmk" data-cmk="mat" readonly>${esc(comMat)}</textarea></div>`;
}

/* O top-N que ele está mais perto de concluir, para as caixas por escolher
   (Standard, Pioneer, Legacy). "Vou montar este" fixa a lista de consenso desse
   arquétipo nesta caixa, congelada com a data — no site publicado é só a lista
   com o crachá de quem já foi escolhido. */
function candidatosHTML(c) {
  const lista = (D.candidatos || {})[c.slot] || [];
  if (!lista.length) return '';
  const escolhido = lista.some(x => x.escolhido);
  const li = lista.map(x => `<li><b>${x.pct}%</b><span class="wn">${esc(x.nome)}`
    + (x.escolhido ? `<span class="chosen">✔ escolhido em `
        + `${esc(x.escolhido_em || '?')}</span>`
       : escolhido ? `<span class="part">alternativa</span>` : '')
    + `<small>${esc(x.subtitulo)} · ${x.n_lists} listas · comprar ${x.comprar}`
    + `</small></span><span class="pz">${eur(x.custo)}`
    + (D.editable ? (x.escolhido
        ? `<button class="btn" data-act="desmarcar" data-slot="${esc(c.slot)}" `
          + `aria-label="Deixar de montar ${esc(x.nome)}">✕ já não</button>`
        : `<button class="btn pri" data-act="escolher" data-slot="${esc(c.slot)}" `
          + `data-aid="${x.archetype_id}" `
          + `aria-label="Vou montar ${esc(x.nome)} nesta caixa">✔ vou montar este`
          + `</button>`) : '')
    + `</span></li>`).join('');
  return `<div class="blk cand-blk"><div class="flh">🎯 O que estás mais perto de `
    + `concluir<span class="dim">${lista.length} arquétipos</span></div>`
    + `<ul class="fl">${li}</ul>`
    + `<p class="nota">A lista de cada um está na página `
    + `<a href="metagame.html#f-${esc(c.formato)}">Metagame</a>. `
    + (D.editable ? 'Escolher fixa a lista de consenso <b>com a data</b>: não muda '
        + 'debaixo dos pés se o metagame mudar amanhã.'
       : 'Para escolheres, corre <code>python webapp.py</code> no PC (porto 8771).')
    + `</p></div>`;
}

function caixaHTML(c, compacta) {
  if (c.vazio) {
    return `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
      + `<span class="pct dim">—</span></div><div class="badges">${badges(c)}</div>`
      + `<div class="nota">${esc(c.nota)}</div>`
      + `<div class="vaziomsg">Caixa por atribuir — não escolhi por ti. `
      + `Escolhe aqui em baixo, ou vê a lista de cada um na página `
      + `<a href="metagame.html">Metagame</a>.</div>`
      + (compacta ? '' : candidatosHTML(c))
      + (D.editable ? acoesHTML(c) : '') + `</div>`;
  }
  let h = `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
    + `<span class="pct" style="color:${cor(c.pct)}">${c.pct}%</span></div>`
    + `<div class="bar"><i style="width:${Math.max(c.pct, 2)}%;background:${cor(c.pct)}"></i></div>`
    + `<div class="badges">${badges(c)}</div>`
    + `<div class="nums">`
    + `<div class="num">na caixa<b>${c.tenho}/${c.precisa}</b></div>`
    + `<div class="num buy">comprar<b>${c.comprar}</b></div>`
    /* DOIS números, não um (André, 2026-09-08): "ir buscar a outra caixa" só
       vale para o que está MESMO dentro de outra caixa. O resto está na gaveta,
       destinado a uma caixa por montar — tira-se do mesmo sítio que tudo o
       resto, e chamar-lhe "ir buscar" mandava-o a uma caixa vazia. */
    + `<div class="num get">ir buscar<b>${c.nmont}</b>`
    + `<span class="dim">a outra caixa (montada)</span></div>`
    + `<div class="num get2">na gaveta<b>${c.nres}</b>`
    + `<span class="dim">destinadas a outra caixa</span></div>`
    + (c.nfut ? `<div class="num get2">por comprar<b>${c.nfut}</b>`
        + `<span class="dim">outra caixa compra-as</span></div>` : '')
    + `<div class="num eur">fechar por<b>${eur(c.custo)}</b>`
    + (c.sem_preco ? `<span class="dim"> no mínimo — ${c.sem_preco} sem preço`
                     + ` na base</span>` : '') + `</div></div>`
    + `<div class="nota">${esc(c.nota)}</div>`;
  const orig = Object.entries(c.origens);
  if (orig.length) {
    h += `<div class="orig">🗂️ tirar de: `
      + orig.map(([k, v]) => `${esc(k)} <b>${v}</b>`).join(' · ') + `</div>`;
  }
  if (c.notas) h += `<div class="nota">📝 ${esc(c.notas)}</div>`;
  if (compacta) return h + `</div>`;

  const cartas = c.cartas.filter(x => filtro === 'tudo' || x.est !== 'have');
  /* A lista agrupada POR TIPO (criaturas primeiro, terras no fim) e com a
     imagem grande à escolha: as duas coisas vinham da página dos decks, e são o
     que faz esta lista servir para conferir a caixa carta a carta. */
  const grelha = l => `<div class="cards${grande ? ' big' : ''}">`
    + l.map(cardTile).join('') + `</div>`;
  if (grupo === 'tipo') {
    for (const t of TIPOS) {
      const b = cartas.filter(x => x.tipo === t);
      if (!b.length) continue;
      h += `<div class="typehdr">${esc(TIPO_PT[t] || t)} <span class="dim">`
        + `${b.reduce((s, y) => s + y.need, 0)}</span></div>` + grelha(b);
    }
  } else {
    h += grelha(cartas);
  }
  if (!cartas.length) {
    h += `<p class="empty">Nada em falta nesta caixa — está completa.</p>`;
  }
  /* A lista em texto, para levar para outro sítio. */
  h += `<div class="blk"><div class="flh">🃏 A lista`
    + `<span class="dim">${c.precisa} cópias</span>`
    + `<button class="cpbtn" onclick="copiar(this,'lista')" `
    + `aria-label="Copiar a lista completa desta caixa">copiar a lista</button>`
    + `</div><textarea class="cmk" data-cmk="lista" readonly>${esc(c.lista)}`
    + `</textarea></div>`;
  /* TRÊS blocos, não um (André, 2026-09-08: *"só o Stiflenought está em
     deckbox; o resto ainda nada está em deckbox"*). São três sítios diferentes:
     dentro de outra caixa (vais lá), na gaveta de sempre (tiras já) e uma
     compra que outra caixa ainda vai fazer (não existe em casa). Um bloco só
     mandava-o abrir caixas vazias — e hoje o primeiro é o único que costuma
     estar a zero. Quem parte é o Python; aqui só se desenha. */
  for (const [qual, n, tit, ajuda] of [
      ['montada', c.nmont, '📦 ir buscar a outra caixa',
       'Estas cópias estão sleevadas dentro de outra deckbox — vais lá buscá-las.'],
      ['reservada', c.nres, '🗂️ na gaveta, destinadas a outra caixa',
       'Estão na colecção, como todas as outras: a alocação prometeu-as a outra '
       + 'caixa por prioridade, mas essa caixa ainda não está montada. Podes '
       + 'tirá-las já no passo 1 — a outra passa a vir buscá-las aqui.'],
      ['futura', c.nfut, '🛒 outra caixa vai comprá-las',
       'Ainda não existem em casa: são uma compra partilhada de outra caixa.']]) {
    const rows = c.buscar[qual] || [];
    if (!rows.length) continue;
    const li = rows.map(m => `<li>${esc(m.nm)} — ${esc(m.onde.join('; '))}`
      + (m.comprar ? ` <span class="dim">(comprar mais ${m.comprar})</span>` : '')
      + `</li>`).join('');
    h += `<div class="blk onde"><b>${tit} — ${n} cópias</b>`
      + `<p class="nota">${esc(ajuda)}</p><ul>${li}</ul></div>`;
  }
  /* O TECTO DE PLAYSET (André, 2026-09-08: "no Premodern, afinal só vou ter até
     playset de cada carta"). Uma falta que ele decidiu não tapar não é o mesmo
     que uma falta tapada — se saísse só da conta das compras, a caixa dizia-se
     à espera de uma carta que ninguém vai comprar. */
  if (c.playset_faltas.length) {
    const li = c.playset_faltas.map(m => `<li>${esc(m.nm)}`
      + (m.board === 'side' ? ' <span class="dim">(sideboard)</span>' : '')
      + ` — <b>falta ${m.q}</b> que não se compra</li>`).join('');
    h += `<div class="blk lim"><b>🔒 limite de playset — ${c.bloqueado} `
      + `${c.bloqueado === 1 ? 'cópia' : 'cópias'}</b>`
      + `<p class="nota">Pediste no máximo <b>${c.playset} cópias</b> de cada `
      + `carta para ${esc(c.grupo || 'este grupo')}, somando todas as caixas e o `
      + `que já tens. Estas passam disso: a caixa fica sem elas de propósito.</p>`
      + `<ul>${li}</ul></div>`;
  }
  if (c.subs.length) {
    const li = c.subs.map(m => `<li>${esc(m.nm)} — falta ${m.missing}: `
      + Object.entries(m.alt).map(([k, v]) => `tens <b>${v}</b> que ${esc(k)}`).join('; ')
      + (Object.keys(m.onde).length ? ` <span class="dim">(em `
        + esc(Object.entries(m.onde).map(([k, v]) => `${k}: ${v}`).join(', ')) + `)</span>` : '')
      + `</li>`).join('');
    h += `<div class="blk"><b>↻ tens a carta, não serve a caixa</b><ul>${li}</ul></div>`;
  }
  h += montarHTML(c);
  h += candidatosHTML(c);
  if (D.editable) h += acoesHTML(c);
  return h + `</div>`;
}

/* Os botões só se DESENHAM no modo edição. No site publicado os endpoints de
   escrita não existem, e um botão que não faz nada é pior do que não haver
   botão nenhum. O `render_deckboxes.js` (na bateria) confirma que a página
   publicada não desenha nenhum. */
function acoesHTML(c) {
  const i = D.caixas.findIndex(x => x.slot === c.slot);
  /* PRIORIDADE AUTOMÁTICA (André, 2026-09-08): num grupo ordenado por %
     completo o `prioridade` do config já não decide nada, e um botão que mexe
     num número que ninguém lê é pior do que botão nenhum — mexia-o em silêncio
     e a ordem ficava na mesma. Fica desactivado E diz porquê. */
  const auto = c.prioridade_por === 'pct';
  const porque = auto ? ` title="A ordem deste grupo é automática: vem da `
    + `percentagem que cada caixa já tem. Para a mudares, muda o `
    + `prioridade_por do grupo no colecao_config.json."` : '';
  /* O «sleevado e na caixa» NÃO está aqui: vive no fim do passo 1 do painel
     Montar, que é onde ele está quando acaba de a montar. Aqui fica o que muda
     o ESTADO da caixa e a ordem da alocação. */
  /* DESMONTAR (André, 2026-09-08): o inverso do «sleevado e na caixa» — as
     cartas voltam à gaveta, a `copy_allocation` desta caixa esvazia-se (com
     backup e registo no `data/desmontar.log`) e a caixa volta a `permanente`.
     Aparece também numa caixa que NÃO se diz montada mas tem cartas registadas
     lá dentro: era o caso das quatro que herdaram alocação da migração, e é
     precisamente esse o botão que faltava — sem ele isto fazia-se em SQL. */
  const desmontavel = c.montado || c.arrumada;
  return `<div class="acts">`
    + (desmontavel
       ? `<button class="btn warn" data-act="desmontar" data-slot="${esc(c.slot)}">`
         + `🧹 Desmontar</button>`
       : `<button class="btn ${c.permanente ? '' : 'pri'}" data-act="permanente" `
         + `data-slot="${esc(c.slot)}">`
         + (c.permanente ? 'Deixar de ser permanente' : '★ Tornar permanente')
         + `</button>`)
    + `<button class="btn" data-act="subir" data-slot="${esc(c.slot)}"${porque}`
    + `${auto || i === 0 ? ' disabled' : ''}>↑ Subir</button>`
    + `<button class="btn" data-act="descer" data-slot="${esc(c.slot)}"${porque}`
    + `${auto || i === D.caixas.length - 1 ? ' disabled' : ''}>↓ Descer</button>`
    + (auto ? `<span class="dim">ordem automática: #${c.posicao_grupo} por % `
        + `completo</span>` : '')
    + `</div>`;
}

/* ------------------------------------------------------------- vistas */
function vistaTodas() {
  const bloco = (titulo, lista, lead) => !lista.length ? '' :
    `<h2>${titulo} <span class="n">${lista.length}</span></h2>`
    + `<p class="lead">${lead}</p><div class="grid">`
    + lista.map(c => `<button class="mini${c.permanente ? '' : ' cand'}" `
        + `data-slot="${esc(c.slot)}">${caixaHTML(c, true)}</button>`).join('')
    + `</div>`;
  const perm = D.caixas.filter(c => c.permanente);
  const cand = D.caixas.filter(c => !c.permanente);
  return bloco('★ Permanentes', perm,
      'Escolhem as cartas primeiro, por esta ordem. É a tua prioridade máxima.')
    + bloco('Candidatos', cand,
      'Só recebem o que sobrar dos permanentes. Para um começar a receber cartas, '
      + 'marca-o como permanente (no modo edição, <code>python webapp.py</code>).');
}

/* A edição, num movimento de arrumação. Sem ela, dois lotes do mesmo nome
   (impressões diferentes) apareciam como duas linhas iguais uma a seguir à
   outra — e não são a mesma pilha. */
const edicao = m => m.set_code
  ? ` <span class="dim">[${esc(m.set_code.toUpperCase())}]</span>` : '';

/* Em que BLOCO da caixa entra a cópia (André, 2026-09-08: "para ficar separado
   dentro da mesma caixa"). Vem do movimento, que o traz da linha da alocação: a
   mesma carta pode entrar no main E no side, e são duas pilhas. */
const bloco = m => m.board === 'side' ? ` <span class="sb">SB</span>` : '';

/* As caixas CONGELADAS (dedicadas e montadas) não se arrumam — actualizam-se.
   O "já arrumei tudo" geral não lhes toca de propósito: abrir um deck que está
   sleevado é outro gesto, e é ele que decide quando o faz. */
function actualizarHTML() {
  const acts = D.arrumar.actualizacoes || [];
  if (!acts.length) return '';
  const lado = (movs, verbo, seta) => movs.map(m =>
    `<div class="mv"><span class="q">${m.q}×</span>`
    + `<span class="nm">${esc(m.nm)}${edicao(m)}${bloco(m)}</span>`
    + `<span class="to">${verbo} ${seta} ${esc(verbo === 'tirar' ? m.para : m.de)}`
    + `</span></div>`).join('');
  return `<h2>🔄 Actualizar decks montados <span class="n">${acts.length}</span></h2>`
    + `<p class="lead">Caixas <b>dedicadas e montadas</b>: a lista mudou, o deck `
    + `não. Ficam como estão até seres tu a abri-las — o <b>já arrumei tudo</b> `
    + `não lhes toca. Quando as actualizares, `
    + (D.editable ? 'carrega em <b>actualizei</b> nessa caixa.'
                  : 'diz-me (ou usa o modo edição, <code>python webapp.py</code>).')
    + `</p>`
    + acts.map(a => `<div class="arr"><div class="arrh"><b>${esc(a.caixa)}</b>`
        + `<span>${a.copias} cópias · tirar ${a.sai.length} · meter `
        + `${a.entra.length}</span></div>`
        + lado(a.sai, 'tirar', '→') + lado(a.entra, 'meter', '←')
        + (D.editable ? `<div class="acts"><button class="btn pri" `
            + `data-act="actualizar" data-slot="${esc(a.slot)}">🔄 Actualizei o `
            + `${esc(a.caixa)}</button></div>` : '')
        + `</div>`).join('');
}

function vistaArrumar() {
  const a = D.arrumar;
  if (!a.linhas) {
    return actualizarHTML()
      + `<h2>📥 Arrumar</h2><p class="empty">Nada a arrumar: a estante já está `
      + `igual à alocação. Quando comprares cartas novas (fotos em `
      + `<code>pendentes/</code>) ou mudares uma caixa, isto volta a encher-se.</p>`;
  }
  const linha = (m, lado) => {
    const id = `${m.copy_id}|${m.de}|${m.para}|${m.nm}`;
    const feito = !!P.feitos[id];
    return `<label class="mv${feito ? ' feito' : ''}" data-id="${esc(id)}">`
      + `<input type="checkbox"${feito ? ' checked' : ''}>`
      + `<span class="q">${m.q}×</span>`
      + `<span class="nm">${esc(m.nm)}${edicao(m)}${bloco(m)}</span>`
      + `<span class="to">${lado === 'origem' ? '→ ' + esc(m.para) : '← ' + esc(m.de)}`
      + `</span></label>`;
  };
  /* Cada gaveta e cada caixa vêm partidas em MAIN e SIDEBOARD — é a lista com
     que ele está à frente da estante, e a caixa fica separada por dentro. Quem
     parte é o Python (`loadout.blocos_de_board`), o mesmo que o painel Montar e
     o CLI usam. O que SAI de uma caixa não tem bloco (vem do lote, não da
     lista): fica no bloco do fim, com o nome que o Python lhe dá. */
  const secao = (mapa, lado, titulo, lead) => {
    let h = `<h2>${titulo}</h2><p class="lead">${lead}</p>`;
    for (const [nome, bs] of Object.entries(mapa)) {
      const n = bs.reduce((s, b) => s + b.movs.length, 0);
      h += `<div class="arr"><div class="arrh"><b>${esc(nome)}</b>`
        + `<span>${bs.reduce((s, b) => s + b.q, 0)} cópias · ${n} linhas`
        + `</span></div>`;
      for (const b of bs) {
        if (bs.length > 1) {
          h += `<div class="bhdr">${esc(b.titulo)}<span>${b.q} cópias</span></div>`;
        }
        h += b.movs.map(m => linha(m, lado)).join('');
      }
      h += `</div>`;
    }
    return h;
  };
  return actualizarHTML()
    + `<h2>📥 Arrumar — ${a.copias} cópias</h2>`
    + `<p class="lead">A diferença entre <b>onde as cartas estão</b> e <b>onde a `
    + `alocação diz que deviam estar</b>. Vai marcando à medida que moves; os `
    + `visto ficam guardados neste aparelho. No fim, <b>já arrumei tudo</b>`
    + (D.editable ? ' grava a arrumação na base de dados (com backup).'
                  : ' descarrega o CSV para me dares.') + `</p>`
    + `<div class="seg"><button class="btn pri" id="arr-fim">✅ Já arrumei tudo</button>`
    + `<button class="btn" id="arr-csv">⬇ CSV (moves-${D.hoje}.csv)</button>`
    + `<button class="btn" id="arr-limpar">Limpar os vistos</button></div>`
    + secao(a.por_origem, 'origem', '🗂️ De cada gaveta (o que se tira)',
        'Abre esta gaveta uma vez e tira tudo o que está aqui.')
    + secao(a.por_destino, 'destino', '📦 Para cada caixa (o que entra)',
        'A mesma lista pelo outro lado: o que cada deckbox recebe.');
}

function vistaPartilhadas() {
  if (!D.partilhadas.length) {
    return `<h2>🔁 Cartas partilhadas</h2><p class="empty">Nenhuma caixa está a `
      + `disputar cartas com outra.</p>`;
  }
  const rows = D.partilhadas.map(c => {
    const det = c.por_slot.map(q => `<span class="cs ${q.levou >= q.pediu ? 'ok' : 'no'}"`
      + `${q.req ? ` title="${esc(q.slot)}: só cópias ${esc(q.req)}"` : ''}>`
      + `${esc(q.slot)} ${q.levou}/${q.pediu}</span>`).join('');
    /* Uma caixa só vai buscar o que cumpre as REGRAS dela — dizê-lo aqui evita
       a leitura errada de que qualquer cópia serve qualquer caixa. */
    const regras = c.por_slot.filter(q => q.req).map(q =>
      `${esc(q.slot)}: só cópias <b>${esc(q.req)}</b>`).join(' · ');
    const tem = c.ficam_com.join(', ') || 'ninguém';
    const vai = c.ficam_sem.filter(x => c.ficam_com.length && !c.ficam_com.includes(x))
      .join(', ');
    return `<div class="cfrow"><div class="cd sub">`
      + (c.sid ? `<img loading="lazy" src="${art(c.sid)}" alt="">` : '')
      + `</div><div class="cfb"><b>${esc(c.nm)}</b>`
      + `<span class="dim">tens ${c.tenho} para ${c.pedido} pedidas · está em `
      + `<b>${esc(tem)}</b>${vai ? ' · vai buscar: ' + esc(vai) : ''}</span>`
      + `<div class="csl">${det}</div>`
      + (regras ? `<span class="dim creq">${regras}</span>` : '')
      + `</div></div>`;
  }).join('');
  return `<h2>🔁 Cartas partilhadas entre caixas <span class="n">`
    + `${D.partilhadas.length}</span></h2>`
    + `<p class="lead"><b>Só se partilham cópias que cumprem as regras da caixa que `
    + `vai buscar.</b> `
    + `Cartas que duas ou mais caixas querem e não chegam para todas. `
    + `<b>Não são compras.</b> A cópia fica na caixa que aloca primeiro (permanentes, `
    + `depois o grupo de formato) e as outras vão lá buscá-la quando forem jogar — é `
    + `por isso que aparecem a âmbar com <b>“em &lt;caixa&gt;”</b> e não somam ao `
    + `custo. Se quiseres os decks todos prontos ao mesmo tempo sem trocas, aí sim: `
    + `compram-se cópias dedicadas.</p><div class="cfgrid">${rows}</div>`;
}

/* A linha de compra vista pelos olhos de UMA caixa: a quantidade, o custo e o
   material passam a ser os dela. Sem isto o filtro mostrava a linha inteira e o
   "copiar" dava-lhe a lista das outras caixas por cima. */
/* Uma caixa SERVIDA por uma compra partilhada não aparece na lista dela: a
   compra é de outra caixa, e pô-la aqui era comprá-la duas vezes — que é
   exactamente o defeito que a partilha veio corrigir. */
function soDaCaixa(m, slot) {
  const p = (m.para || []).find(x => x.slot === slot && !x.serve);
  if (!p) return null;
  return Object.assign({}, m, { q: p.q, cost: p.cost, unit: p.unit,
                                req: p.req, mat: p.mat, para: [p],
                                partilhada: 0 });
}

function vistaComprar() {
  const sel = P.compra || 'todas';
  const itens = (sel === 'todas' ? D.compras.slice()
                 : D.compras.map(m => soDaCaixa(m, sel)).filter(Boolean))
    .sort((a, b) => (b.cost || 0) - (a.cost || 0));
  const caras = itens.filter(m => (m.unit || 0) >= CARA);
  const resto = itens.filter(m => (m.unit || 0) < CARA);
  const soma = l => l.reduce((s, m) => s + (m.cost || 0), 0);
  const nome = sel === 'todas' ? 'todas as caixas'
    : ((D.caixas.find(c => c.slot === sel) || {}).nome || sel);
  /* O selector reaproveita as caixas que já são abas — só as que têm mesmo
     alguma coisa a comprar entram na lista (uma caixa SERVIDA por outra não
     compra nada). */
  const compraDe = (m, slot) => (m.para || []).some(p => p.slot === slot && !p.serve);
  const comCompras = D.caixas.filter(c => D.compras.some(m => compraDe(m, c.slot)));
  const opt = (v, t, n) => `<option value="${esc(v)}"${sel === v ? ' selected' : ''}>`
    + `${esc(t)}${n == null ? '' : ` — ${n} cartas`}</option>`;
  const selector = `<div class="seg"><select class="selc" id="compra-caixa">`
    + opt('todas', 'todas as caixas', D.compras.length)
    + comCompras.map(c => opt(c.slot, c.nome,
        D.compras.filter(m => compraDe(m, c.slot)).length)).join('')
    + `</select></div>`;
  return `<h2>🛒 Comprar — ${esc(nome)}</h2>`
    + `<p class="lead">Só o que <b>não existe</b> na coleção, ou existe mas não serve `
    + `na língua/acabamento que a caixa exige. As cartas que estão noutra caixa `
    + `<b>não estão aqui</b>: vão-se buscar. São <b>${D.resumo.noutra}</b> cópias a ir `
    + `buscar contra <b>${D.resumo.comprar}</b> a comprar. Debaixo de cada nome está `
    + `<b>para que caixa</b> é a compra e <b>em que material</b> — comprar a versão `
    + `errada é comprar duas vezes.</p>`
    + (D.resumo.poupado ? `<p class="lead">🔁 <b>Uma cópia serve as caixas todas.</b> `
        + `Quando duas caixas querem a mesma carta no mesmo material, compra-se `
        + `<b>uma vez</b> e as outras vão lá buscá-la — como já fazes com as que tens. `
        + `São <b>${D.resumo.poupado}</b> cópias que a lista deixou de pedir. Se `
        + `quiseres uma caixa fechada sem trocas, marca-a com `
        + `<code>compras_dedicadas</code> no <code>colecao_config.json</code>.</p>` : '')
    + selector
    + (!itens.length ? `<p class="empty">Não falta comprar nada aqui. Está tudo em casa.</p>`
       : `<div class="nums">`
         + `<div class="num buy">cópias<b>${itens.reduce((s, m) => s + m.q, 0)}</b></div>`
         + `<div class="num eur">💶 caras (≥ ${CARA} €/cópia)<b>${eur(soma(caras))}</b>`
         + `<span class="dim"> ${caras.length} cartas</span></div>`
         + `<div class="num eur">resto<b>${eur(soma(resto))}</b>`
         + `<span class="dim"> ${resto.length} cartas</span></div></div>`
       + (caras.length ? `<p class="lead">As <b>💶 caras</b> decidem-se uma a uma: `
         + `só elas valem ${eur(soma(caras))} dos ${eur(soma(itens))} da lista.</p>` : '')
       + (D.resumo.sem_preco ? `<p class="lead">⚠️ <b>${D.resumo.sem_preco}</b> `
         + `cópias desta lista não têm preço na base (contam como 0 €). `
         + `O total é um <b>mínimo</b>, não a conta fechada.</p>` : '')
       + wantlistHTML(itens, '', 'v-compras', true))
    + basicasComprarHTML(sel);
}

/* As básicas que a pilha de Unhinged NÃO cobre — hoje as Snow-Covered do Duel
   Commander. Bloco à parte e não uma linha da lista: não contam para o total (é
   a regra dele — as básicas não entram nas compras nem na %) e são *a
   confirmar*, porque ele pode tê-las em casa sem as ter registado. */
function basicasComprarHTML(sel) {
  const bs = (D.basicas || []).filter(b => sel === 'todas'
    || (b.para || []).some(p => p.caixa === (D.caixas.find(c => c.slot === sel) || {}).nome));
  if (!bs.length) return '';
  const li = bs.map(b => `<li><b>${b.q}×</b><span class="wn">${esc(b.nm)}`
    + `<span class="cara">confirma se já tens</span>`
    + `<small>${esc(b.req)} — para: `
    + (b.para || []).map(p => `${esc(p.caixa)} ${p.q}×`).join(' · ')
    + `</small></span><span class="pz">${eur(b.cost)}</span></li>`).join('');
  const txt = bs.map(b => `${b.q} ${b.nm}` + (b.req ? ` [${b.req}]` : '')).join('\n');
  return `<div class="blk"><div class="flh">🌱 Terrenos básicos`
    + `<span class="dim">${bs.reduce((s, b) => s + b.q, 0)} cópias · `
    + `${eur(bs.reduce((s, b) => s + (b.cost || 0), 0))}</span>`
    + `<button class="cpbtn" onclick="copiar(this,'cm')" aria-label="Copiar as `
    + `básicas a comprar">copiar p/ Cardmarket</button></div>`
    + `<p class="nota">As tuas básicas são todas de <b>${esc(D.basicas_edicao)}</b>, `
    + `e essas nunca se compram. Estas não existem lá — <b>não somam</b> ao total `
    + `de compras acima nem à percentagem de nenhuma caixa.</p>`
    + `<ul class="fl">${li}</ul>`
    + `<textarea class="cmk" data-cmk="cm" readonly>${esc(txt)}</textarea></div>`;
}

/* ------------------------------------------------------------- sugestões
   "Se o deck for top-10 de representação ou top-5 decks combo do formato,
   sugere a lista para montar o deck caso eu tenha pelo menos 50% das cartas"
   (André, 2026-09-08). A percentagem é a do que SOBRA depois de as caixas
   estarem servidas — é com essas cartas que se monta mais um deck. */
const PM_ESTADO = {
  caixa: ['ok', '🧰 já é uma caixa tua'],
  sugerida: ['ok', '💡 sugerido — montar?'],
  recusada: ['', '✕ recusado'],
  abaixo: ['', 'abaixo do limiar'],
};

function sugestaoHTML(c) {
  const [cls, txt] = PM_ESTADO[c.estado] || ['', c.estado];
  const rot = c.estado === 'caixa' && c.caixa ? '🧰 ' + esc(c.caixa)
    : c.estado === 'recusada' ? '✕ recusado em ' + esc(c.recusada_em || '?') : txt;
  const chips = [`<span class="bdg ${cls}">${rot}</span>`,
    c.combo ? `<span class="bdg fo">🧩 ${esc(c.grau)}</span>` : '',
    `<span class="bdg">${c.top ? '🔟 top de representação' : '🎯 top de combo'}`
      + `</span>`,
    `<span class="bdg">${c.n_lists} listas que contam</span>`].join('');
  const grelha = c.cartas.map(m => `<div class="cd ${m.est}" title="${esc(m.nm)} — `
    + `tens ${m.got}/${m.need}">`
    + (m.sid ? `<img loading="lazy" src="${art(m.sid)}" alt="${esc(m.nm)}">` : '')
    + `<span class="cq">${m.got}/${m.need}</span></div>`).join('');
  /* Os botões só no modo edição, como em todo o resto da página: no site
     publicado o endpoint não existe e um botão morto é pior que botão nenhum. */
  const acts = !D.editable || c.estado === 'caixa' ? '' :
    c.estado === 'recusada'
      ? `<div class="acts"><button class="btn" data-act="pm-aceitar" `
        + `data-nome="${esc(c.nome)}" data-id="${esc(c.id)}">`
        + `↩ Voltar a considerar</button></div>`
      /* O `data-id` é o id ESTÁVEL do arquétipo: é por ele que a recusa e a
         escolha se guardam, porque o nome do clustering muda entre corridas. */
      : `<div class="acts"><button class="btn pri" data-act="pm-montar" `
        + `data-nome="${esc(c.nome)}" data-aid="${c.archetype_id}" `
        + `data-id="${esc(c.id)}">`
        + `✔ Vou montar este</button>`
        + `<button class="btn" data-act="pm-recusar" data-nome="${esc(c.nome)}" `
        + `data-id="${esc(c.id)}">`
        + `✕ Não quero este</button></div>`;
  /* A percentagem grande é a de COMO PRINCIPAL — é a que decide o limiar desde
     2026-09-08, porque as caixas de Premodern partilham cartas. A do que sobra
     vem logo a seguir: a diferença entre as duas é quantas cartas viriam
     emprestadas das outras caixas, e sem ela os 81% pareciam cartas em casa. */
  const p = c.pct_principal;
  return `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
    + `<span class="pct" style="color:${cor(p)}">${p}%</span></div>`
    + `<div class="bar"><i style="width:${Math.max(p, 2)}%;`
    + `background:${cor(p)}"></i></div>`
    + `<div class="badges">${chips}</div>`
    + `<div class="nums">`
    + `<div class="num get">como principal<b>${c.tenho_principal}/${c.need}</b></div>`
    + `<div class="num">com o que sobra<b>${c.pct}%</b> (${c.got}/${c.need})</div>`
    + `<div class="num buy">comprar<b>${c.comprar}</b></div>`
    + `<div class="num eur">fechar por<b>${eur(c.custo)}</b></div></div>`
    + `<div class="nota">${esc(c.subtitulo)}</div>`
    + `<div class="cards">${grelha}</div>${acts}</div>`;
}

function vistaSugestoes() {
  const P2 = D.premodern;
  const ordem = { sugerida: 0, abaixo: 1, recusada: 2, caixa: 3 };
  const lista = P2.candidatos.slice().sort((a, b) =>
    (ordem[a.estado] - ordem[b.estado]) || (b.pct_principal - a.pct_principal));
  const sug = lista.filter(c => c.estado === 'sugerida');
  let h = `<h2>💡 Sugestões de Premodern</h2>`
    + `<p class="lead">O <b>top-10</b> do formato e os <b>melhores combo</b>, `
    + `pelas listas que contam. A percentagem grande é a de <b>como principal</b>: `
    + `as caixas de Premodern <b>partilham</b> cartas, por isso conta-se o que `
    + `este deck teria se fosse ele a escolher primeiro — as cópias PT (≤SCG) `
    + `livres <b>mais</b> as que estão nas outras caixas de Premodern. A segunda `
    + `é a do que <b>sobra</b> sem tocar em nada, e a diferença entre as duas é `
    + `quantas cartas irias buscar às outras caixas. A partir de `
    + `<b>${P2.limiar}%</b> vira sugestão.</p>`;
  h += sug.length
    ? `<p class="lead">Enquanto forem sugestões, as cartas delas <b>não vão para `
      + `a venda</b> — ficam no bloco <b>reservadas</b> da aba Vender. `
      + (D.editable ? `<b>✔ vou montar este</b> abre-lhe uma caixa e mete-a na `
          + `alocação; <b>✕ não quero este</b> liberta as cartas para a venda.`
         : `Para decidires, corre <code>python webapp.py</code> no PC (porto 8771).`)
      + `</p>`
    : `<p class="lead">Nenhum candidato chega aos ${P2.limiar}% nem sequer como `
      + `principal: mesmo com as cartas emprestadas pelas outras caixas de `
      + `Premodern faltava-lhes mais de metade. O que sobra vai para a venda com `
      + `o motivo <i>"não usada por nenhum deck"</i>. Se quiseres ver mais `
      + `opções, baixa o <code>sugerir_a_partir_de_pct</code> no `
      + `<code>colecao_config.json</code>.</p>`;
  return h + `<div class="grid">` + lista.map(sugestaoHTML).join('') + `</div>`;
}

function vistaVender() {
  const ordena = l => l.slice().sort((x, y) => x.nm.localeCompare(y.nm));
  /* Duas listas para copiar, porque servem duas coisas: a do Cardmarket é só
     `N Nome`, e a de conferir leva a edição, a língua e o acabamento — vender a
     versão errada é anunciar uma carta que não se tem. */
  const so = l => ordena(l).map(r => `${r.q} ${r.nm}`).join('\n');
  const detalhe = l => ordena(l).map(r => `${r.q} ${r.nm} [${r.set}`
    + `${r.foil ? ' foil' : ' nonfoil'} ${(r.lang || '').toUpperCase()}]`).join('\n');
  const bloco = (id, titulo, lead, b, aberto, rotulo, semBotao) => !b.linhas.length ? '' :
    `<details class="vblk" id="${id}"${aberto ? ' open' : ''}>`
    + `<summary><span>${titulo}</span><span class="vtot">${b.copias} cópias · `
    + `${eur(b.total)}</span></summary><p class="lead">${lead}</p>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this,'cm')" `
    + `aria-label="Copiar a lista: ${esc(rotulo)}">copiar lista Cardmarket`
    + `</button><button class="cpbtn" onclick="copiar(this,'mat')" `
    + `aria-label="Copiar a lista com edição, língua e acabamento: ${esc(rotulo)}">`
    + `copiar com edição/língua/acabamento</button></div>`
    + `<textarea class="cmk" data-cmk="cm" readonly>${esc(so(b.linhas))}</textarea>`
    + `<textarea class="cmk" data-cmk="mat" readonly>${esc(detalhe(b.linhas))}`
    + `</textarea>`
    + `<table class="vt"><thead><tr><th></th><th>carta</th><th>onde está</th>`
    + `<th>edição</th><th>un.</th><th>total</th><th class="rz">porquê</th>`
    + (D.editable && !semBotao ? `<th></th>` : '') + `</tr></thead>`
    + `<tbody>` + b.linhas.map(r => `<tr><td class="q">${r.q}×</td>`
      + `<td>${esc(r.nm)}${r.rl ? ' <span class="rl">RL</span>' : ''}</td>`
      + `<td class="dim">${esc(r.local)}</td>`
      // `r.foil` vem do Python (`loadout.e_foil`). Este teste era
      // `/foil|etched/.test(r.fin)` e marcava com ✨ as cópias `nonfoil` — a
      // palavra "nonfoil" contém "foil". Aparecia em Lotus Petal e Mirri's
      // Guile, que são nonfoil, e mandava-o listá-las como foil.
      + `<td class="dim">${esc(r.set)} ${r.foil ? '✨' : ''} `
      + `${esc((r.lang || '').toUpperCase())}</td>`
      + `<td class="pz">${eur(r.unit)}</td><td class="pz tot">${eur(r.total)}</td>`
      /* Nos blocos da RL retida a linha leva DOIS motivos: porque é que a regra
         a segurou e porque é que ela ia à venda. Sem o segundo, "subiu 7%" é
         uma resposta sem pergunta. */
      + `<td class="dim rz">${esc(r.reason)}`
      /* A janela em que a subida foi medida. Vai em TODAS as linhas de RL — nas
         que se vendem também —, porque "não subiu" medido em 27 dias e medido
         em 90 não são a mesma afirmação. */
      + (r.rl_nota ? ` <b>${esc(r.rl_nota)}</b>` : '')
      + (r.porque ? ` <i>(ia por: ${esc(r.porque)})</i>` : '') + `</td>`
      /* «vendida»: tira as cópias da base e escreve-as no `data/vendas.csv`.
         Sem isto a lista repetia todos os dias as cartas que ele já vendeu — e
         a única maneira de a calar era editar a base à mão. */
      + (D.editable && !semBotao
         ? `<td><button class="btn sm" data-vend="${esc(r.chave)}" `
           + `data-q="${r.q}" aria-label="Marcar ${r.q} ${esc(r.nm)} como vendida">`
           + `vendida</button></td>` : '')
      + `</tr>`).join('')
    + `</tbody></table></details>`;
  const V = D.venda, R = D.rl_regra;
  /* Quanto da lista entra pelo motivo novo. Conta-se das LINHAS e não de um
     total à parte: o que a tabela mostra e o que o parágrafo diz têm de vir do
     mesmo sítio. */
  const pmVenda = [...V.normal.linhas, ...V.rl.linhas]
    .filter(r => r.reason === PM_RAZAO)
    .reduce((a, r) => ({ copias: a.copias + r.q, total: a.total + (r.total || 0) }),
            { copias: 0, total: 0 });
  return `<h2>💰 Para vender</h2>`
    + `<p class="lead"><b>Sugestão a confirmar.</b> Nada sai da coleção sem tu dizeres. `
    + `É o que sobra depois de encher todas as caixas e de guardar o backup: `
    + `<b>4 por carta</b> na coleção (playset, a somar a Coleção e a Caixa RL — não 4 `
    + `por balde) e <b>1 por deck</b> nas caixas de Commander. <b>Básicas nunca.</b></p>`
    /* PREMODERN NÃO USADO (André, 2026-09-08). É um motivo à parte dentro das
       mesmas listas: uma PT da era está trancada ao Premodern, e se nenhuma
       caixa a aloca não serve mais nada. Dizê-lo aqui em cima porque muda o
       tamanho da lista — e porque a saída dela é uma decisão dele, não um
       excedente. */
    + (pmVenda.copias ? `<p class="lead">🕰 <b>${pmVenda.copias} cópias `
        + `(${eur(pmVenda.total)}) entram por não estarem em nenhum deck de `
        + `Premodern.</b> São PT de edições até ao Scourge: essas ficam trancadas `
        + `ao Premodern (<i>"não entram para outros formatos"</i>), por isso uma `
        + `cópia que nenhuma caixa usa não serve mais nada. Se houver um deck que `
        + `queiras montar com elas, marca-o na aba <b>Sugestões</b> primeiro — as `
        + `cartas dele saem desta lista.</p>` : '')
    /* O total que a regra dos 5% segurou. Em cima, e não só dentro dos blocos,
       porque muda o tamanho da lista da RL — que é onde está quase todo o
       dinheiro — e ele tem de o ver antes de decidir seja o que for. */
    + (R.copias ? `<p class="lead">🔒 <b>${R.copias} cópias Reserved List `
        + `(${eur(R.total)}) NÃO entram na venda</b> pela tua regra: só se vende `
        + `RL que não tenha subido <b>${R.pct}%</b> em <b>${R.dias} dias</b>. `
        /* A JANELA CRESCE SOZINHA (2026-09-08). Dizê-lo aqui, e não só no
           relatório, porque muda o que a página mostra todos os dias: hoje
           mede-se em ~27 dias e em Novembro em 90, sem ninguém mexer em nada. */
        + `A janela é um <b>máximo</b>: cada carta é medida no histórico que o `
        + `vault tem dela (mínimo ${R.minima} dias), e a subida exigida `
        + (R.fixo ? `são os ${R.pct}% à letra em qualquer janela `
                    + `(<code>venda.rl_limiar_fixo</code>).`
                  : `acompanha a janela — ${R.pct}% em ${R.dias} dias, `
                    + `~${(R.pct * R.minima / R.dias).toFixed(1)}% em ${R.minima}. `
                    + `Cada linha diz em que janela foi medida.`)
        + ` Estão nos dois blocos de baixo — as que valorizaram e as que `
        + `o vault ainda não consegue medir.</p>` : '')
    + bloco('v-normal', 'Excedente normal', 'Cópias a mais de cartas que não são '
        + 'Reserved List. É por aqui que se começa: o risco é baixo e o dinheiro é '
        + 'real.', V.normal, true, 'excedente normal')
    + bloco('v-rl', '⚠️ Reserved List — confirmar uma a uma', 'Cartas que nunca mais '
        + 'são impressas. A regra dá-as como excedente, mas a decisão não se desfaz — '
        + 'e os preços de cartas antigas na base não são de confiança (ver '
        + '<code>doubts.md</code>). Confere cada uma antes de listar.', V.rl, false,
        'Reserved List')
    /* RESERVED LIST QUE VALORIZOU (André, 2026-09-08). Vem logo a seguir à lista
       da RL porque é a metade dela que NÃO se vende hoje — e o total em € é o que
       ele quer ver: é dinheiro que fica na estante de propósito. */
    + bloco('v-rl-segurar', '🔒 RL a segurar — valorizou', 'Reserved List que '
        + 'subiu o suficiente na janela em que foi medida: não entra na venda. A '
        + 'regra é tua (<i>"cartas de RL só vão para venda se não tiverem subido '
        + '5% de valor nos últimos 3 meses"</i>) e afina-se em '
        + '<code>venda.rl_subida_minima_pct</code> / '
        + `<code>venda.rl_janela_dias</code>. Cada linha diz a subida e a janela `
        + `(<b>+2.1 % em 27 d ≈ +7.0 %/${R.dias} d</b>).`, V.rl_segurar, false,
        'RL a segurar', true)
    + bloco('v-rl-semhist', '❔ RL sem histórico suficiente', 'O vault tem menos '
        + `de <b>${R.minima} dias</b> de preços para estas — o \`price_history\` `
        + 'só guarda mudanças e começou em Agosto de 2026. Sem saber se subiram, '
        + '<b>não vão para a venda</b>. Esta lista encolhe sozinha à medida que o '
        + 'histórico cresce; para a forçar, baixa o '
        + '<code>venda.rl_janela_minima_dias</code>.',
        V.rl_sem_historico, false, 'RL sem histórico', true)
    + bloco('v-guardar', '🔒 Guardar — servem um deck do loadout', 'Passariam o limite '
        + 'de 4, mas são substitutos de cartas que faltam a uma caixa: servem o deck e '
        + 'só não fecham o slot por causa da língua ou do acabamento. Vendê-las era '
        + 'comprá-las outra vez.', V.guardar, false, 'guardar')
    + bloco('v-reservadas', '💡 Reservadas — decks por decidir',
        'Cartas de um deck que ainda não disseste se queres. Não são excedente. '
        + 'Duas origens: as <b>sugestões de Premodern</b> (aba <b>Sugestões</b>) '
        + '— carrega em <b>não quero este</b> e elas passam para a lista de cima '
        + 'no mesmo dia — e a <b>Reserved List que o Legacy usaria</b>, desde que '
        + 'as RL em PT passaram a servir esse formato (2026-09-08): enquanto a '
        + 'caixa de Legacy não tiver deck escolhido, quem as segura é o top-N do '
        + '<b>Metagame</b>. Escolhe lá o deck e a reserva encolhe para a lista dele.',
        V.reservadas, false, 'reservadas', true)
    + bloco('v-retidos', '⏳ Retidos — extras de decks montados', 'Baldes com '
        + '<code>reter_extras_meses</code>: guardam-se até 6 meses depois da última '
        + 'utilização. Ainda não há registo de "última utilização", por isso ficam '
        + 'todos — não se vende nada por uma regra que ainda não corre.', V.retidos,
        false, 'retidos')
    + (V.normal.linhas.length || V.rl.linhas.length ? '' :
       `<p class="empty">Não há nada a mais para vender.</p>`);
}

/* O LINK E O QR para o telemóvel — só no modo edição, e só quando o pedido já
   trazia o token (senão a página estaria a dar-lho a quem não o tem). É o que
   ele aponta com o telemóvel para ir à frente da estante com os botões. */
function ligacaoHTML() {
  if (!D.editable || !D.ligacao) return '';
  /* O `?t=` na imagem não é decoração: o QR É o link com o token lá dentro, e o
     servidor recusa-o (403) a quem não o traga — senão bastava pedir a imagem
     para receber o token pela porta do lado. */
  return `<div class="lig"><img src="qr.svg?t=${encodeURIComponent(D.token)}" `
    + `alt="QR do link do modo edição" width="150" height="150">`
    + `<div><b>📱 Abrir no telemóvel</b>`
    + `<p class="lead">Aponta a câmara ao QR, ou escreve `
    + `<code>${esc(D.ligacao.url)}</code>. O link leva o token: <b>sem ele a `
    + `página é só de leitura</b>. Estás na mesma rede de casa.</p>`
    + `<p class="nota">Se não abrir, o porto ${D.ligacao.porto} pode estar `
    + `fechado na firewall da rede privada — o comando está no arranque do `
    + `<code>python webapp.py</code>.</p></div></div>`;
}

/* ------------------------------------------------------------------ render */
function render() {
  const v = $('#vista');
  const caixa = D.caixas.find(c => c.slot === aba);
  if (caixa) {
    v.innerHTML = filtroHTML() + caixaHTML(caixa, false);
  } else if (aba === 'plano') { v.innerHTML = ligacaoHTML() + vistaPlano(); }
  else if (aba === 'arrumar') { v.innerHTML = vistaArrumar(); }
  else if (aba === 'partilhadas') { v.innerHTML = vistaPartilhadas(); }
  else if (aba === 'comprar') { v.innerHTML = vistaComprar(); }
  else if (aba === 'vender') { v.innerHTML = vistaVender(); }
  else if (aba === 'sugestoes') {
    v.innerHTML = D.premodern && D.premodern.activo ? vistaSugestoes() : vistaTodas();
  }
  else { v.innerHTML = vistaTodas(); }
  ligar();
  renderBarra();
  window.scrollTo({ top: 0 });
}

function filtroHTML() {
  /* `aria-pressed`: são botões que ficam carregados, não links. Sem isto o
     leitor de ecrã lia "Todas as cartas, botão" nos dois, sem dizer qual está
     activo — e a diferença é só a cor de fundo. */
  const b = (f, t) => `<button class="${filtro === f ? 'on' : ''}" data-f="${f}"`
    + ` aria-pressed="${filtro === f}">${t}</button>`;
  const g = (f, t) => `<button class="${grupo === f ? 'on' : ''}" data-g="${f}"`
    + ` aria-pressed="${grupo === f}">${t}</button>`;
  return `<div class="seg" role="group" aria-label="Filtrar as cartas">`
    + b('tudo', 'Todas as cartas') + b('faltam', 'Só o que falta')
    + g('estado', 'por estado') + g('tipo', 'por tipo')
    + `<button class="${grande ? 'on' : ''}" data-big="1" `
    + `aria-pressed="${grande}">🔍 imagens grandes</button></div>`;
}

/* ------------------------------------------------------------------ plano
   "Espero começar a montar os decks em deckbox o mais cedo possível para começar
   a comprar as faltas e livrar-me dos excessos de cartas" (André, 2026-09-08).
   Esta aba é a resposta a "por onde começo": a ordem, e o que cada caixa custa. */
function vistaPlano() {
  const M = D.montagem;
  const porMontar = M.filter(m => !m.montado);
  const montadas = M.filter(m => m.montado);
  const soma = (l, k) => l.reduce((s, m) => s + (m[k] || 0), 0);
  const linha = (m, n) => `<button class="pl" data-slot="${esc(m.slot)}">`
    + `<span class="pi">${n || '✓'}</span>`
    + `<span class="pb"><b>${esc(m.caixa)}</b>`
    + `<small>${esc((ESTADO[m.estado] || ['', m.estado])[1])}`
    + `${m.req ? ' · ' + esc(m.req) : ''}</small></span>`
    + `<span class="pn2"><b style="color:${cor(m.pct)}">${m.pct}%</b>`
    + `<small>${m.tenho}/${m.precisa}</small></span>`
    + `<span class="pn2"><b>${m.tirar}</b><small>tirar`
    + `${m.gavetas > 1 ? ` · ${m.gavetas} gavetas` : ''}</small></span>`
    + `<span class="pn2"><b class="buy">${m.comprar}</b>`
    + `<small>comprar ${eur(m.custo)}</small></span></button>`;
  let h = `<h2>🗺️ Por onde começar</h2>`
    + `<p class="lead">Primeiro os <b>permanentes</b>, por ordem de alocação — são `
    + `eles que ficaram com as cartas. Depois as <b>candidatas</b>, pela `
    + `percentagem que já tens: começa-se pelo que está mais perto de fechar. `
    + `Clica numa para abrir o painel <b>Montar</b> dela.</p>`;
  if (porMontar.length) {
    h += `<div class="nums">`
      + `<div class="num">caixas por montar<b>${porMontar.length}</b></div>`
      + `<div class="num">tirar da colecção<b>${soma(porMontar, 'tirar')}</b></div>`
      + `<div class="num buy">comprar<b>${soma(porMontar, 'comprar')}</b></div>`
      + `<div class="num eur">fechar tudo por<b>${eur(soma(M, 'custo'))}</b></div>`
      + `</div><div class="plano">`
      + porMontar.map((m, i) => linha(m, i + 1)).join('') + `</div>`;
  } else {
    h += `<p class="empty">Está tudo montado. 🎉</p>`;
  }
  if (montadas.length) {
    h += `<h2>✅ Já montadas <span class="n">${montadas.length}</span></h2>`
      + `<p class="lead">Não há nada a fazer nestas hoje. As <b>congeladas</b> `
      + `mostram na aba <b>Arrumar</b> o que trocar quando a lista mudar.</p>`
      + `<div class="plano">` + montadas.map(m => linha(m, 0)).join('') + `</div>`;
  }
  /* A VENDA vem depois, e a ordem não é decoração: o excedente é o que sobra
     DEPOIS de encher as caixas. Uma cópia que serve uma caixa do loadout nunca
     entra na lista de venda — é a saída `guardar`. */
  const V = D.venda;
  h += `<h2>💰 Depois de montar: vender o excesso</h2>`
    + `<p class="lead"><b>Primeiro montar, depois vender.</b> Esta lista é o que `
    + `sobra <b>depois</b> de todas as caixas terem as cartas que a alocação lhes `
    + `deu: uma cópia que serve uma caixa nunca aparece aqui, mesmo que passe o `
    + `limite de 4 (fica em <b>🔒 Guardar</b>). É uma <b>sugestão a confirmar</b> — `
    + `nada sai da coleção sem tu dizeres.</p>`
    + `<div class="nums">`
    + `<div class="num eur">excedente normal<b>${eur(V.normal.total)}</b>`
    + `<span class="dim"> ${V.normal.copias} cópias</span></div>`
    + `<div class="num eur">Reserved List<b>${eur(V.rl.total)}</b>`
    + `<span class="dim"> ${V.rl.copias} cópias · uma a uma</span></div>`
    + `<div class="num">guardar (servem uma caixa)<b>${V.guardar.copias}</b></div>`
    + `</div>`
    + `<div class="seg"><button class="btn pri" data-aba="vender">`
    + `Ver e confirmar a venda →</button></div>`;
  return h;
}

function ligar() {
  for (const b of document.querySelectorAll('[data-f]')) {
    b.onclick = () => { filtro = b.dataset.f; P.filtro = filtro; save(); render(); };
  }
  for (const b of document.querySelectorAll('[data-g]')) {
    b.onclick = () => { grupo = b.dataset.g; P.grupo = grupo; save(); render(); };
  }
  for (const b of document.querySelectorAll('[data-big]')) {
    b.onclick = () => { grande = !grande; P.grande = grande; save(); render(); };
  }
  for (const b of document.querySelectorAll('.mini[data-slot],.pl[data-slot]')) {
    b.onclick = () => ir(b.dataset.slot);
  }
  for (const b of document.querySelectorAll('[data-aba]:not(.dt)')) {
    b.onclick = () => ir(b.dataset.aba);
  }
  /* Todos os botões de escrita, estejam num `.acts` ou dentro da lista de
     candidatos — um selector demasiado apertado deixava o "vou montar este"
     desenhado e morto, que é o pior dos dois mundos. */
  for (const b of document.querySelectorAll('[data-act]')) {
    b.onclick = () => accao(b.dataset.act, b.dataset.slot, b, b.dataset.aid,
                            b.dataset.nome, b.dataset.id);
  }
  for (const l of document.querySelectorAll('.mv')) {
    const cb = l.querySelector('input');
    if (!cb) continue;  /* .mv da seccao Actualizar nao tem checkbox */
    cb.onchange = () => {
      if (cb.checked) P.feitos[l.dataset.id] = 1; else delete P.feitos[l.dataset.id];
      l.classList.toggle('feito', cb.checked);
      save();
      renderBarra();
      if (cb.checked) autoRegistar();
    };
  }
  const cc = $('#compra-caixa');
  if (cc) cc.onchange = () => { P.compra = cc.value; save(); render(); };
  for (const b of document.querySelectorAll('[data-vend]')) {
    b.onclick = () => vendida(b);
  }
  const fim = $('#arr-fim'), csv = $('#arr-csv'), lim = $('#arr-limpar');
  if (csv) csv.onclick = baixarCSV;
  if (lim) lim.onclick = () => { P.feitos = {}; save(); render(); toast('Vistos limpos.'); };
  if (fim) fim.onclick = jaArrumei;
}

function copiar(btn, qual) {
  const c = btn.closest('.blk') || btn.closest('.vblk') || btn.closest('.montar');
  /* Cada bloco tem mais do que uma versão do texto (só nomes / com material /
     com edição): o botão diz qual quer, em vez de apanhar a primeira textarea. */
  const t = c && (c.querySelector(`textarea.cmk[data-cmk="${qual || 'cm'}"]`)
                  || c.querySelector('textarea.cmk'));
  if (!t) return;
  const feito = () => { btn.textContent = '✓ copiado'; btn.classList.add('done'); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t.value).then(feito)
      .catch(() => { t.select(); document.execCommand('copy'); feito(); });
  } else { t.select(); try { document.execCommand('copy'); feito(); } catch (e) {} }
}

function baixarCSV() {
  const b = new Blob([D.arrumar.csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = `moves-${D.hoje}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast('CSV descarregado.');
}

/* No site publicado, "já arrumei tudo" só pode dar-te o ficheiro; quem escreve
   na base é o modo edição. Dizê-lo é melhor do que ter um botão que não faz
   nada — foi a lição do banner de só-leitura do riftvault. */
async function jaArrumei() {
  if (!D.editable) {
    baixarCSV();
    toast('Guardado o CSV — dá-mo e eu aplico. (Para aplicar aqui: python webapp.py)');
    return;
  }
  if (!confirm(`Gravar a arrumação de ${D.arrumar.copias} cópias? `
      + `Faz backup da base antes.`)) return;
  try {
    const r = await gravar('api/arrumar');
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(`Arrumado: ${j.copias} cópias registadas.`);
    P.feitos = {}; save();
    location.reload();
  } catch (e) { toast('Não deu: ' + e.message); }
}

/* Escolher um deck para uma caixa é outro endpoint (`api/escolher`): mexe na
   `listas_escolhidas` e refaz as DUAS páginas, não só esta. */
const ESCOLHA = { escolher: 1, desmarcar: 1,
                  'pm-montar': 1, 'pm-recusar': 1, 'pm-aceitar': 1 };

/* O token vai em cabeçalho em TODAS as escritas: sem ele o servidor responde
   403 e a página fica só de leitura. É o que permite ter o porto aberto na rede
   de casa sem dar a qualquer aparelho o direito de lhe desmontar os decks. */
function gravar(url, corpo) {
  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
               'X-Mtgvault-Token': D.token || '' },
    body: JSON.stringify(corpo || {}),
  });
}

async function accao(act, slot, btn, aid, nome, id) {
  /* DESMONTAR apaga o que ele CONFIRMOU à mão. Pergunta-se, como na venda: a
     base é copiada antes, mas um toque enganado no telemóvel manda-o procurar
     as cartas todas outra vez. */
  if (act === 'desmontar' && !confirm(
      'Desmontar esta caixa? As cartas voltam à colecção e o vault deixa de '
      + 'saber o que está lá dentro (a base é copiada antes).')) return;
  btn.disabled = true;
  try {
    /* MONTAR FORA DE ORDEM: as cópias que ele MARCOU no bloco «destinadas a
       outra caixa» vão no pedido. Só essas — o resto do painel é a alocação
       desta caixa, que o servidor já sabe de cor; estas são uma decisão dele
       que o vault não tem como adivinhar. Sai do `P.feitos` e já não do DOM: a
       barra vive fora da vista e não alcançava as checkboxes por selector. */
    const deOutra = deOutraMarcadas(D.caixas.find(x => x.slot === slot));
    const r = await gravar(ESCOLHA[act] ? 'api/escolher' : 'api/caixa',
                           { act, slot, nome: nome || null, id: id || null,
                             de_outra: deOutra,
                             aid: aid ? Number(aid) : null });
    if (!r.ok && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Feito — a alocação foi refeita.');
    location.reload();
  } catch (e) { btn.disabled = false; toast('Não deu: ' + e.message); }
}

async function vendida(btn) {
  const q = Number(btn.dataset.q || 1);
  if (!confirm(`Marcar ${q} cópia(s) como VENDIDA? Sai da coleção e fica `
      + `registada no data/vendas.csv (a base é copiada antes).`)) return;
  btn.disabled = true;
  try {
    const r = await gravar('api/vender', { linha: btn.dataset.vend, q });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Registado.');
    location.reload();
  } catch (e) { btn.disabled = false; toast('Não deu: ' + e.message); }
}

if (!D.caixas.some(c => c.slot === aba)
    && !['plano', 'todas', 'arrumar', 'partilhadas', 'comprar', 'vender']
        .includes(aba)) {
  aba = 'plano';
}
renderResumo(); renderTabs(); render();
</script>
</body></html>"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("deckboxes.html:", build(con))


if __name__ == "__main__":
    main()
