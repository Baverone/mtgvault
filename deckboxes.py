"""Gera deckboxes.html — "Deckboxes": os decks montados em simultâneo, e a venda.

O André (2026-09-07): *"Vamos começar a reorganizar os decks e a colecção, para
preparar para montar os decks (em deckboxes) para estarem sempre prontos para ir
jogar, e começar a vender o que está em excesso."*

E, no mesmo dia, o que esta versão traz:

  * *"Os decks gostava que fizesses algo como fizeste para o riftvault — no
    botão, cada deck tem uma aba própria."* → a página deixou de ser uma lista
    de cartões todos abertos e passou a ter **uma vista por caixa**, com a % e a
    cor do estado. Clicar abre só aquela caixa. Há duas vistas a mais:
    **Todas** (a vista de conjunto, um cartão por caixa) e **Arrumar**.
    Desde 2026-09-24 essas vistas escolhem-se num **índice vertical** à esquerda
    do conteúdo (no telemóvel, um `<select>`) e não numa fila horizontal com
    scroll: eram 27 botões a correr para o lado, e foi isso que ele mandou
    acabar (*"ter que andar a correr os botões para os lados"*). Cada vista tem
    **URL** (`deckboxes.html#comprar`), que é por onde a barra lateral do site
    entra nas secções *Decks* e *Compras e venda*;
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

import hashlib
import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import (collection, encomendas, feira, fotocaixa, fotosite,  # noqa: E402
                      loadout, paginas, precos, revalidacao, venda)
from mtgvault import site_shell as shell  # noqa: E402


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

    Desde 2026-09-21 o Pioneer JÁ NÃO os mostra (André: *"Pioneer apenas
    Greasefang e jeskai control"*): sai do `metagame.formatos_top()` por
    `colecao_config.json → formatos_decididos`, e as duas caixas dele ficam
    sem o bloco «o que estás mais perto de concluir» e sem «vou montar este».
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
                "lang": (m["lang"] or "").upper(), "copy_id": m["copy_id"],
                # AS CARTAS EM IMAGEM (André, 2026-09-20): a impressão EXACTA da
                # cópia que ele vai tirar da gaveta — não a primeira do nome.
                "sid": m.get("sid"),
                # LINHA INCOMPLETA (2026-09-08): a caixa pede 4 e ele só tem 2.
                # As 2 tiram-se na mesma, e a linha diz porque é que vem a menos
                # («2 de 4 — as outras 2 em Comprar»). O texto vem do Python
                # (`loadout.nota_parcial`) pela razão de sempre: quem sabe partir
                # a falta em comprar/ir buscar é a alocação, não o browser.
                "parcial": bool(m.get("parcial")), "nota": m.get("nota") or ""}

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
    # «JÁ A TENHO» (André, 2026-09-08): as cópias que ele declarou ter em casa e
    # que já estão dentro da caixa. Não há checkbox nenhuma nelas — já lá estão —
    # mas levam o «📷 edição por confirmar» até a foto chegar.
    confirmar = [linha(m) for m in plano["por_confirmar"]]
    return {"slot": plano["slot"], "caixa": plano["caixa"],
            "por_confirmar": sorted(confirmar, key=por_cor),
            "copias_por_confirmar": plano["copias_por_confirmar"],
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


def _edicoes_das_faltas(con, rep):
    """`{slot: {carta: [edições candidatas]}}` para o selector do «já a tenho».

    É o que a linha de compra oferece quando ele diz que já tem a carta: as
    impressões que cumprem a regra DAQUELA caixa, com o palpite à cabeça. As
    regras são por caixa mas o catálogo não muda entre elas, e por isso a cache
    é por (carta, regra) — a mesma Swords to Plowshares aparece na wantlist de
    seis caixas de Premodern e é uma consulta só.
    """
    cache: dict = {}
    out: dict[str, dict] = {}
    for s in rep["slots"]:
        faltas = {m["nm"] for m in s["missing"] if m["comprar"] > 0}
        out[s["slot"]] = {nm: loadout.impressoes_da_falta(con, s, nm, cache)
                          for nm in sorted(faltas)}
    return out


def _rev_caixa(prog, slot):
    """A REVALIDAÇÃO desta caixa (2026-09-20): a lista «Na caixa» com o estado
    de cada cópia (📷 por fotografar / ✓ validada / ⚠ corrigida pela foto), os
    totais para a barra «validadas N/M», e por CARTA quantas faltam — é o que a
    miniatura da grelha mostra. Tudo do `revalidacao.progresso`, a mesma conta
    da aba «📷 Revalidação»."""
    g = next((c for c in (prog or {}).get("caixas") or [] if c["slot"] == slot), None)
    if g is None:
        return None, {}
    por_carta: dict[str, dict] = {}
    for l in g["linhas"]:
        d = por_carta.setdefault(l["nm"], {"foto": 0, "ok": 0, "corr": 0})
        d["foto" if l["estado"] == "foto" else "ok"] += l["q"]
        if l["estado"] == "corr":
            d["corr"] += l["q"]
    rev = {"q": g["q"], "validadas": g["validadas"],
           "por_revalidar": g["por_revalidar"], "corrigidas": g["corrigidas"],
           "pct": round(100 * g["validadas"] / g["q"]) if g["q"] else 0,
           "alvo": bool((prog or {}).get("alvo")
                        and prog["alvo"]["tipo"] == "caixa"
                        and prog["alvo"]["slot"] == slot),
           "activa": bool((prog or {}).get("activa")),
           "linhas": g["linhas"],
           # AS FOTOS TIRADAS NO SITE para esta caixa (2026-09-21), ainda em
           # `pendentes/` à espera do `mtg-fotos-novas` — é o que a aba mostra
           # a seguir ao «Tirar fotos», para ele saber que entraram.
           "site": [e for e in ((prog or {}).get("site") or {}).get("enviadas") or []
                    if e["origem"] and e["origem"]["tipo"] == "caixa"
                    and e["origem"]["slot"] == slot]}
    return rev, por_carta


def _sid_da_falta(con, m, imgs, cache):
    """A imagem de uma linha que FALTA: a impressão mais barata no acabamento
    que a compra usa (`price_finish`), a mesma do `card_price` — e, sem preço na
    base, a impressão de sempre do nome. Sem `con` (testes sem catálogo) fica a
    do nome."""
    if con is not None:
        sid = loadout.impressao_mais_barata(con, m["nm"], m.get("price_finish")
                                            or "nonfoil", cache=cache)
        if sid:
            return sid
    return imgs.get(m["nm"])


def _caixa_payload(s, imgs, cfs, rep=None, col=None, tipos=None, cores=None,
                   edicoes=None, prog=None, con=None, baratas=None):
    rev, rev_carta = _rev_caixa(prog, s["slot"])
    baratas = {} if baratas is None else baratas
    cartas = []
    for m in s["have"] + s["missing"]:
        est = _estado_carta(m)
        # AS CARTAS EM IMAGEM (André, 2026-09-20: *"cada deck poderia ter as
        # cartas visualmente ao invés de só o nome?"*). A imagem é a da cópia
        # que a alocação deu a ESTA caixa (a primeira do lote), e não a primeira
        # do nome que ele tenha algures; numa linha que falta é a da impressão
        # mais barata — a que o preço da compra já usa.
        lotes = [{"local": g["local"], "q": g["q"], "fin": g["finish"],
                  "lang": g["lang"], "set": (g["set_code"] or "").upper(),
                  "foil": loadout.e_foil(g["finish"]), "sid": g.get("sid"),
                  "copy_id": g.get("id")}
                 for g in m["lotes"]]
        sid = next((l["sid"] for l in lotes if l["sid"]), None) or (
            _sid_da_falta(con, m, imgs, baratas) if est == "miss" else imgs.get(m["nm"]))
        cartas.append({
            "nm": m["nm"], "board": m["board"], "need": m["need"], "got": m["got"],
            "est": est, "sid": sid,
            "basica": bool(m.get("basica")),
            # REVALIDAÇÃO (2026-09-20): quantas cópias desta carta, nesta
            # caixa, ainda não têm foto da campanha (`foto`) e quantas têm.
            "rev": rev_carta.get(m["nm"]) or {"foto": 0, "ok": 0, "corr": 0},
            "missing": m["missing"], "comprar": m["comprar"],
            # O que o TECTO DE PLAYSET não deixa comprar (André, 2026-09-08). Vem
            # na carta e não só no resumo: é ali que ele está quando pergunta
            # "porque é que isto não está na lista de compras?".
            "bloq": m.get("playset_bloqueado", 0),
            # ... e a frase inteira (*"não se compra (limite de 4 no total;
            # está no UW Replenish)"*), composta no Python (2026-09-19).
            "bloq_txt": (loadout.texto_playset(m, loadout.playset_maximo(s))
                         if m.get("playset_bloqueado") else ""),
            "noutra": m["noutra"], "alt": m["alt"], "alt_onde": m["alt_onde"],
            # CADA CAIXA COM AS SUAS CARTAS (André, 2026-09-19). A cópia que
            # está noutra caixa já não é fonte nem desconto — é uma NOTA para
            # ele saber que a tem: *"tens 2 no Blue Farm"* (`loadout.nota_onde`).
            "nota": loadout.nota_onde(m),
            # «SÓ FOIL» SÓ QUANDO EXISTE EM FOIL (2026-09-19): a carta nunca saiu
            # em foil. Numa caixa de foil é o que explica uma nonfoil a fechar o
            # slot, e uma compra a pedir nonfoil.
            "sfoil": not m.get("foil_existe", True),
            # ONDE A CARTA ESTÁ vs A QUEM ESTÁ DESTINADA (André, 2026-09-08: *"o
            # resto ainda nada está em deckbox — e ainda estás a assumir que há
            # cartas que já estão nas deckboxes dos decks"*). A frase vem pronta
            # do Python (`loadout.onde_esta`): a página não volta a compor "em
            # X" a partir do `noutra`, que é a caixa DESTINO e não o sítio.
            "onde": loadout.onde_esta(m),
            "nmont": sum(m["noutra_montada"].values()),
            "nres": sum(m["noutra_reservada"].values()),
            "cost": m["cost"], "unit": m["unit"],
            # ENCOMENDAS (2026-09-19): o que desta linha já vem a caminho ou
            # chegou e espera foto. O `title` da miniatura di-lo.
            "acam": m.get("a_caminho", 0), "pfoto": m.get("pendente_foto", 0),
            "cf": m["nm"] in cfs,
            # O TIPO (para agrupar a lista como ele a arruma) e as cópias que tem
            # na COLECÇÃO INTEIRA. Este segundo número é a única coisa que a
            # página *Decks permanentes* dizia e esta não; entra como informação
            # secundária, porque o número que manda é o da alocação — duas
            # respostas para a mesma pergunta era o defeito a corrigir.
            "tipo": (tipos or {}).get(m["nm"], "Other"),
            "col": (col or {}).get(m["nm"], 0),
            "so_de": s["so_de_variante"].get(m["nm"]) or [],
            "lotes": lotes,
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
                            "q": m["playset_bloqueado"],
                            "txt": loadout.texto_playset(m, loadout.playset_maximo(s))}
                           for m in s.get("playset_faltas") or []],
        # CADA CAIXA COM AS SUAS CARTAS (2026-09-19): as faltas de que ele TEM
        # cópias noutra caixa, só como nota. Nunca desconta.
        "notas_onde": [{"nm": m["nm"], "nota": loadout.nota_onde(m)}
                       for m in s.get("noutra_notas") or []],
        "estado": s.get("estado"), "notas": s.get("nota_config") or "",
        "permanente": s["permanente"], "montado": bool(s.get("montado")),
        # A FOTO DA DECKBOX FÍSICA (André, 2026-09-21: *"quero poder tirar foto
        # à deckbox onde vai ficar cada deck, para ser referência também"*):
        # `{em, url}` da versão reduzida em `assets/deckboxes/`, ou `None`. Fica
        # no índice (é o cartão da fila que a mostra primeiro).
        "foto": fotocaixa.info(s),
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
        # O dia em que ela ficou com este conteúdo — o *"montada em <data>"* da
        # vista «Decks montados». Vazio quando o vault não sabe o que lá está
        # (o Stiflenought): a vista diz isso, em vez de inventar um dia.
        "arrumada_em": s.get("arrumada_em") or "",
        "por_confirmar": bool(s.get("por_confirmar")), "vazio": s["vazio"],
        "nota": s["nota"], "fonte": s.get("fonte"), "ref": s.get("ref"),
        # LISTA PADRÃO (André, 2026-09-20): a caixa tem uma lista FIXA, com a
        # data e a origem — a página di-lo e, no modo edição, deixa acrescentar
        # e tirar cartas e «voltar ao consenso». `None` = segue a fonte.
        "padrao": s.get("padrao"),
        # A RESERVA (2026-09-20): as cartas «que poderão entrar», com as cópias
        # que ele tem, onde estão e se servem. Fora da venda; só informação
        # para a caixa.
        "reserva": [{"nm": r["nm"], "q": r["q"], "na_lista": r["na_lista"],
                     "serve": r["serve"],
                     # A imagem da cópia que ele tem (a primeira), senão a do nome.
                     "sid": next((l.get("sid") for l in r["lotes"] if l.get("sid")),
                                 None) or imgs.get(r["nm"]),
                     "lotes": [{"onde": l["onde"], "local": l["local"], "q": l["q"],
                                "set": (l["set_code"] or "").upper(),
                                "lang": (l["lang"] or "").upper(), "fin": l["finish"],
                                "foil": l["foil"], "serve": l["serve"],
                                "sid": l.get("sid"), "copy_id": l.get("copy_id"),
                                "porque": l["porque"]} for l in r["lotes"]]}
                    for r in s.get("reserva_linhas") or []],
        "reserva_nomes": list(s.get("reserva") or []),
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
        # `eds` são as edições que o selector do «já a tenho» oferece: é o que
        # transforma uma linha de compra num check que grava (André, 2026-09-08:
        # *"para dizer que já as tenho e já coloquei no deck"*). Só existe no
        # modo edição — no site publicado não há endpoint para gravar.
        # E, desde 2026-09-19, a linha FICA na wantlist enquanto tiver alguma
        # coisa encomendada (`q` pode ser 0): é aqui que vivem o `−` e o «Chegou»
        # dela, e uma linha que desaparecesse ao `+` não tinha por onde voltar
        # atrás. O texto copiado salta as que têm `q` 0.
        "wantlist": sorted(({"nm": m["nm"], "q": m["comprar"], "cost": m["cost"],
                             "board": m["board"],
                             "eds": (edicoes or {}).get(m["nm"]) or [],
                             "mat": m.get("marca_compra") or "",
                             # A regra PARA ESTA CARTA (2026-09-19): numa que
                             # nunca saiu em foil diz "nonfoil — nunca saiu em
                             # foil" em vez do `req` da caixa.
                             "req": m.get("req_compra") or "",
                             "sfoil": not m.get("foil_existe", True),
                             "nota": loadout.nota_onde(m),
                             "acam": m.get("a_caminho", 0),
                             "pfoto": m.get("pendente_foto", 0),
                             # A impressão mais barata no acabamento da compra:
                             # é a que o preço ao lado já usa (2026-09-20).
                             "sid": _sid_da_falta(con, m, imgs, baratas),
                             "unit": m.get("unit")}
                            for m in s["missing"]
                            if m["comprar"] > 0 or m.get("encomendado", 0) > 0),
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
        # REGISTOS QUE NÃO PODEM ESTAR CERTOS (2026-09-09): linhas da
        # `copy_allocation` desta caixa que a regra de material DELA recusa. Não
        # é uma falta nem um substituto — é o vault a dizer que uma coisa que ele
        # próprio escreveu não bate certo, e a caixa deixou de contar com ela.
        "contradicoes": [{"nm": c["nm"], "q": c["q"], "porque": c["porque"],
                          "onde": c["onde"], "foil": c["foil"],
                          "lang": c["lang"], "set_code": c["set_code"]}
                         for c in s.get("contradicoes") or []],
        # REVALIDAÇÃO POR FOTO (André, 2026-09-20): a lista «Na caixa» com o
        # estado de cada cópia e a barra «validadas N/M». `None` sem campanha
        # ligada no config — aí a página não desenha nada disto.
        "rev": rev if rev and rev["activa"] else None,
    }


def _premodern_payload(rep, imgs):
    """As CAIXAS CANDIDATAS de Premodern: o que ele pode montar com o que sobra.

    André, 2026-09-08: *"se o deck for top-10 de representação ou top-5 decks
    combo do formato, sugere a lista para montar o deck caso eu tenha pelo menos
    50 % das cartas."* A aba **Sugestões** é isto — e vive aqui, ao lado das
    caixas, porque é aqui que ele decide: a alternativa era mandá-lo à página do
    Metagame para voltar com a resposta.

    A percentagem que DECIDE era a de *"como se fosse o principal"*
    (`pct_principal`, André 2026-09-08), quando as caixas de Premodern
    partilhavam cartas. Desde 2026-09-19 (*"cada deck deverá ter as suas
    próprias cartas dentro"*) nenhuma caixa empresta, e as duas percentagens
    são a mesma — o que está LIVRE. O payload leva as duas chaves por forma; a
    página mostra uma.
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


def _encomendas_payload(con, rep, imgs, baratas=None):
    """A aba **📦 Encomendas** (André, 2026-09-19): o que comprou e ainda não
    fotografou, à imagem do separador do riftvault — tiles com a imagem da
    carta, `+`/`−`, «Chegou (N)».

    Quatro blocos, por esta ordem: (a) **pendentes de foto** — o que chegou e
    espera foto, por caixa, mais as cópias da base sem foto («na base, sem
    foto»: as que entraram por CSV à mão ou pelo «já a tenho» antigo); (b) **a
    caminho**, por caixa e origem, com o preço da caixa; (c) **falta
    encomendar**, por caixa = o «a comprar» DEPOIS do desconto; (d) os totais.
    Os números de (c) são os mesmos das caixas (`s["comprar"]`/`s["custo"]`):
    não há uma segunda conta.
    """
    from mtgvault import scryfall                          # noqa: PLC0415

    abertas = encomendas.listar(con)
    sem_foto = collection.copias_sem_foto(con)
    slots = {s["slot"]: s for s in rep["slots"]}
    # O preço por cópia é o da LINHA da caixa (o mesmo `card_price`, no
    # acabamento que a caixa usa); sem linha, o preço no acabamento da encomenda.
    unit_cache: dict = {}

    def unit(r):
        chave = (r["slot"], r["nm"], r["finish"])
        if chave in unit_cache:
            return unit_cache[chave]
        s = slots.get(r["slot"])
        u = None
        if s is not None:
            u = next((m["unit"] for m in s["missing"] + s["have"]
                      if m["nm"] == r["nm"] and m.get("unit")), None)
        if u is None:
            u, _f = loadout.card_price(con, r["nm"],
                                       "foil" if loadout.e_foil(r["finish"]) else "nonfoil")
        unit_cache[chave] = u
        return u

    def sid_de(r):
        if r.get("set_code"):
            row = scryfall.find_printing(con, r["nm"], r["set_code"],
                                         r.get("collector_number"))
            if row is not None:
                return row["scryfall_id"]
        return imgs.get(r["nm"])

    pede = {(a["slot"], a["nm"]): a["porque"] for a in rep.get("encomendas_avisos") or []}

    def tile(r, q):
        u = unit(r)
        return {"id": r["id"], "nm": r["nm"], "sid": sid_de(r), "q": q,
                "slot": r["slot"], "caixa": r["caixa"],
                "set": (r["set_code"] or "").upper(), "num": r["collector_number"] or "",
                "lang": (r["lang"] or "").upper(), "fin": r["finish"],
                "foil": loadout.e_foil(r["finish"]), "impressao": r["impressao"],
                "origem": r["origem"] or "", "preco": r["preco_unit"],
                "unit": u, "total": round((u or 0) * q, 2),
                "aviso": r["aviso"] or pede.get((r["slot"], r["nm"]), ""),
                "na_base": False}

    pendentes = [tile(r, r["qty_pendente_foto"]) for r in abertas
                 if (r["qty_pendente_foto"] or 0) > 0]
    nomes_caixas = loadout.nomes_das_caixas()
    for c in sem_foto:
        pendentes.append({
            "copy_id": c["id"], "nm": c["nm"], "sid": c["sid"], "q": c["q"],
            "slot": c["slot"], "caixa": nomes_caixas.get(c["slot"]) or "",
            "set": (c["set_code"] or "").upper(), "num": c["collector_number"] or "",
            "lang": (c["lang"] or "").upper(), "fin": c["finish"],
            "foil": loadout.e_foil(c["finish"]), "impressao": c["impressao"],
            "por_confirmar": c["por_confirmar"], "na_base": True})
    a_caminho = [tile(r, r["qty_a_caminho"]) for r in abertas
                 if (r["qty_a_caminho"] or 0) > 0]
    falta = []
    for s in rep["slots"]:
        linhas = [{"nm": m["nm"], "q": m["comprar"], "board": m["board"],
                   "unit": m["unit"], "cost": m["cost"],
                   "mat": m.get("marca_compra") or "",
                   "sid": _sid_da_falta(con, m, imgs, baratas if baratas is not None else {}),
                   "acam": m.get("a_caminho", 0), "pfoto": m.get("pendente_foto", 0)}
                  for m in s["missing"] if m["comprar"] > 0]
        if not linhas:
            continue
        falta.append({"slot": s["slot"], "caixa": s["nome"], "comprar": s["comprar"],
                      "custo": s["custo"], "req": loadout.requisito_material(s),
                      "marca": loadout.marca_wantlist(s),
                      "linhas": sorted(linhas, key=lambda x: (x["board"] != "main", x["nm"]))})
    return {
        "pendentes": pendentes, "a_caminho": a_caminho, "falta": falta,
        "avisos": rep.get("encomendas_avisos") or [],
        "totais": {
            "a_caminho": sum(t["q"] for t in a_caminho),
            "pendente_foto": sum(t["q"] for t in pendentes if not t["na_base"]),
            "na_base_sem_foto": sum(t["q"] for t in pendentes if t["na_base"]),
            "valor_a_caminho": round(sum(t["total"] for t in a_caminho), 2),
            "pago": round(sum((t["preco"] or 0) * t["q"] for t in a_caminho), 2),
            "sem_preco": sum(t["q"] for t in a_caminho if not t["unit"]),
            "falta_comprar": rep["comprar_total"], "custo_falta": rep["custo_total"],
        },
    }


def _venda_payload(con, rep, venda_bloco):
    """O bloco `venda` do payload — ou `None` (André, 2026-09-25: *"para já tira
    o «vender»"*).

    Vive numa função e não dentro do literal do `payload` porque a decisão é uma
    só e tem de se ver: ou sai tudo (as sete saídas E a saída para o Cardmarket)
    ou não sai nada. Meia venda — os blocos sem a saída, ou a saída sem os
    blocos — era deixar-lhe o número à vista e tirar-lhe a maneira de agir sobre
    ele, que é pior do que qualquer das duas.

    O `venda.relatorio` nem chega a correr com o interruptor desligado: é a
    parte cara (o CSV, a estante, o formato lido do disco) e ninguém a lê.
    """
    if not venda.mostrar():
        return None
    return {
        "normal": venda_bloco("venda", "copias", "total"),
        "rl": venda_bloco("venda_rl", "copias_rl", "total_rl"),
        "guardar": venda_bloco("guardar", "copias_guardar", "total_guardar"),
        # RESERVADAS por uma sugestão de Premodern por decidir: não são
        # excedente, são cartas de um deck que ele ainda não disse se quer.
        # Ficam num bloco próprio — e sem botão «vendida», porque a decisão que
        # as liberta é o «não quero este».
        "reservadas": venda_bloco("reservadas", "copias_reservadas",
                                  "total_reservado"),
        # RESERVED LIST QUE VALORIZOU e RL que o vault ainda não sabe medir
        # (André, 2026-09-08: *"cartas de RL só vão para venda se não tiverem
        # subido 5 % de valor nos últimos 3 meses"*). Dois blocos e não um:
        # "subiu" é uma decisão tomada, "não sei" é uma decisão por tomar.
        "rl_segurar": venda_bloco("rl_segurar", "copias_rl_segurar",
                                  "total_rl_segurar"),
        "rl_sem_historico": venda_bloco("rl_sem_historico",
                                        "copias_rl_sem_historico",
                                        "total_rl_sem_historico"),
        "retidos": venda_bloco("retidos", "copias_retidas", "total_retido"),
        # A SAÍDA (2026-09-18): o CSV de stock, a lista da estante e o que fica
        # de fora, tudo do `mtgvault.venda` — a página não recompõe nada disto
        # em JavaScript. Sem as `linhas`: já vão dentro da estante, agrupadas, e
        # o CSV é a outra vista delas.
        "saida": {k: v for k, v in venda.relatorio(con, rep).items()
                  if k != "linhas"},
    }


def payload(con, rep, editable=False, token="", ligacao=None):
    nomes = {c["nm"] for c in rep["conflitos"]}
    for s in rep["slots"]:
        nomes |= {n for _b, n, _q in s["cards"]}
        nomes |= set(s.get("reserva") or [])
    for k in ("venda", "venda_rl", "guardar", "retidos", "reservadas"):
        nomes |= {r["nm"] for r in rep[k]}
    nomes |= {m["nm"] for m in rep["arrumacao"]["movimentos"]}
    nomes |= {r["nm"] for r in encomendas.listar(con)}
    # As cartas das SUGESTÕES de Premodern também (2026-09-20): ficavam sem
    # imagem — um quadrado preto — porque nunca entraram aqui.
    for c in (rep.get("premodern") or {}).get("elegiveis") or []:
        nomes |= {m["nm"] for m in c["linhas"]}
    imgs = _img_map(con, sorted(nomes))
    cfs = {c["nm"] for c in rep["conflitos"]}
    # A impressão mais barata por (carta, acabamento), UMA consulta por par: a
    # mesma Swords to Plowshares falta a seis caixas (2026-09-20).
    baratas: dict = {}
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
                                           "mat": "", "partilhada": 0,
                                           "acam": 0, "pfoto": 0,
                                           # (2026-09-19) nunca saiu em foil, e
                                           # a nota "tens N no X" (só informação).
                                           "sfoil": not m.get("foil_existe", True),
                                           "nota": "",
                                           # A imagem: a impressão mais barata
                                           # no acabamento da compra (2026-09-20).
                                           "sid": _sid_da_falta(con, m, imgs, baratas)})
            g["q"] += m["comprar"]
            if loadout.nota_onde(m) and loadout.nota_onde(m) not in g["nota"]:
                g["nota"] = (g["nota"] + " · " if g["nota"] else "") + loadout.nota_onde(m)
            g["cost"] = round(g["cost"] + (m["cost"] or 0), 2)
            # O que já vem a caminho / espera foto (2026-09-19), para a linha
            # dizer «· 1 a caminho» ao lado do que ainda é compra.
            g["acam"] += m.get("a_caminho", 0)
            g["pfoto"] += m.get("pendente_foto", 0)
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

    # REVALIDAÇÃO POR FOTO (André, 2026-09-20): o progresso por caixa / venda /
    # RL / resto, e o estado de cada cópia para a aba Vender. A conta é UMA
    # (`revalidacao.progresso`) e não muda nada na alocação nem na venda.
    prog = revalidacao.progresso(con, rep) if revalidacao.activa() else None
    estado_rev = revalidacao.estado_das_copias(con) if prog else {}
    if prog is not None:
        # AS FOTOS TIRADAS NO SITE (André, 2026-09-21): o que está na raiz de
        # `pendentes/` à espera do `mtg-fotos-novas`, o que ficou por resolver
        # e onde está o «processar agora». Só leitura da pasta e da inbox —
        # nada da alocação. Vai nos dois modos (é a pasta do PC que gerou a
        # página); os BOTÕES só existem no 8771.
        prog["site"] = fotosite.estado(fotosite.pasta_pendentes())

    def venda_bloco(chave, copias, total):
        linhas = rep[chave]
        fotos = [revalidacao.foto_da_linha(estado_rev, r.get("copias")) for r in linhas]
        return {"validadas": sum(f["ok"] for f in fotos),
                "por_revalidar": sum(f["falta"] for f in fotos),
                "linhas": [{"nm": r["nm"], "q": r["q"], "local": r["local"],
                            # A foto desta campanha, por linha: `ok` cópias com
                            # ela, `falta` sem — a linha diz 📷/✓ e o filtro
                            # «só validadas» lê daqui.
                            "foto": f,
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
                            "reason": r["reason"],
                            # A impressão exacta da cópia à venda (2026-09-20).
                            "sid": r.get("sid") or imgs.get(r["nm"]),
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
                           for r, f in zip(linhas, fotos)],
                "copias": rep[copias], "total": rep[total]}

    arr = rep["arrumacao"]
    # As regras de cada caixa, por NOME: é assim que o `conflitos` identifica
    # quem disputa a carta. A aba Partilhadas precisa delas para dizer que uma
    # partilha respeita as regras de quem vai buscar — o Enchantress vai buscar
    # a Swords to Plowshares PT ao UW Replenish, nunca a foil do Cloud.
    reqs = {s["nome"]: loadout.requisito_material(s) for s in rep["slots"]}
    # As edições candidatas do «já a tenho», só no modo edição: no site
    # publicado não há onde gravar, e um selector que não grava é ruído — a mesma
    # razão por que os botões e a barra de montagem só lá existem. (E é uma
    # consulta ao catálogo por carta em falta, que a página publicada não paga.)
    eds = _edicoes_das_faltas(con, rep) if editable else {}
    # A FEIRA: as linhas de «trazer» são compras (a impressão mais barata); as
    # de «levar» já trazem a impressão exacta do `venda.linhas_export`.
    fr = feira.projeccao(con, rep)
    for g in ((fr.get("trazer") or {}).get("linhas") or []):
        g.setdefault("sid", loadout.impressao_mais_barata(
            con, g["nm"], "foil" if "foil" in (g.get("mat") or "").lower()
            and "nonfoil" not in (g.get("mat") or "").lower() else "nonfoil",
            cache=baratas) or imgs.get(g["nm"]))
    for g in ((fr.get("levar") or {}).get("linhas") or []):
        g.setdefault("sid", imgs.get(g["nm"]))
    return {
        "gerado": con.execute("SELECT MAX(date) d FROM price_latest").fetchone()["d"] or "",
        "hoje": date.today().isoformat(),
        "editable": bool(editable),
        # AS CARTAS EM IMAGEM (André, 2026-09-20): a vista por omissão —
        # `imagens` ou `lista` — vem do config (`deckboxes.vista`); no modo
        # edição o interruptor grava-a lá, no site publicado fica no aparelho.
        "vista": vista_config(),
        # O MODO DE PREÇO (André, 2026-09-25). Vai no índice porque a página
        # tem de DIZER por que régua é que os euros que mostra foram medidos —
        # um total sem o modo ao lado é um número que muda sozinho de um dia
        # para o outro. O interruptor só aparece em modo edição.
        # A FONTE é uma CADEIA desde 2026-09-25 (`fontes`), e a página tem de a
        # dizer inteira: com o CardTrader à frente e o Cardmarket atrás, o total
        # é medido com duas réguas e quem o lê tem de saber quantas cópias vieram
        # de cada uma. O `desde` é o da RÉGUA (modo ∪ fonte) — é ele que trava a
        # regra dos 5 % da Reserved List.
        "preco": {"modo": precos.modo(), "fonte": precos.fonte(),
                  "fontes": list(precos.fontes()),
                  "rotulo": precos.ROTULOS[precos.modo()],
                  "desde": precos.regua_desde()},
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
        "caixas": [_caixa_payload(s, imgs, cfs, rep, col, tipos, cores,
                                  eds.get(s["slot"]), prog, con, baratas)
                   for s in rep["slots"]],
        # A ORDEM por que montar as caixas (aba Plano) — permanentes por
        # prioridade, depois as que estão mais perto de fechar.
        "montagem": rep.get("montagem") or [],
        # O top-N por caixa por escolher (Standard/Pioneer/Legacy) — o "vou
        # montar este" também mora aqui, não só no metagame.html.
        "candidatos": _candidatos(con, rep),
        # «N montados · M para montar»: os dois botões que ele pediu a
        # 2026-09-08 são estas duas contas, e o cabeçalho dá-as antes de ele
        # carregar em nada. A soma é sempre o total de caixas — uma caixa está
        # montada ou está por montar, não há terceiro sítio onde se esconder.
        "resumo": {"montados": sum(1 for s in rep["slots"] if s.get("montado")),
                   "por_montar": sum(1 for s in rep["slots"]
                                     if not s.get("montado")),
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
                   # ENCOMENDAS (2026-09-19): já descontadas do `comprar`.
                   "a_caminho": rep.get("a_caminho_total", 0),
                   "pendente_foto": rep.get("pendente_foto_total", 0),
                   "custo": rep["custo_total"],
                   # Os dois totais da venda: só o chip do cabeçalho os lê, e
                   # com o interruptor de 2026-09-25 desligado vão a `None` em
                   # vez de irem a zero. O `deckboxes.json` é PÚBLICO (GitHub
                   # Pages) e um número que ninguém desenha continua a ser um
                   # número que ele lá pode ir buscar — e zero era pior: dizia
                   # que não há nada para vender, o que é falso.
                   "venda": rep["total"] if venda.mostrar() else None,
                   "venda_rl": rep["total_rl"] if venda.mostrar() else None,
                   # TERRENOS BÁSICOS a comprar (as Snow-Covered, que a pilha de
                   # Unhinged não cobre). À parte do `comprar`/`custo`: são *a
                   # confirmar*, e somá-las mexia no número por que ele decide.
                   "basicas": rep.get("basicas_comprar_total", 0),
                   "basicas_custo": rep.get("basicas_custo_total", 0.0),
                   "arrumar": arr["copias"]},
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
        # «PARA JÁ TIRA O VENDER» (André, 2026-09-25): `None` com
        # `venda.mostrar` a `false`. Não é um dicionário vazio de propósito —
        # é a mesma forma que a `revalidacao` desligada usa, e é o que o
        # JavaScript testa para não desenhar a aba, o chip do cabeçalho, o
        # bloco do Plano, o grupo da Revalidação nem um único botão «vendida».
        # O motor por baixo não muda: as sete saídas continuam no `rep`.
        "venda": _venda_payload(con, rep, venda_bloco),
        # Quanto é que a regra dos 5 % segurou ao todo, e com que parâmetros.
        # A janela é um MÁXIMO desde 2026-09-08: a efectiva é a que cada carta
        # dá, e o limiar acompanha-a. Os três números vão para a página porque
        # são os três que explicam uma linha — "subiu 2 % e ficou" só se percebe
        # com a janela ao lado. Só a aba Vender o lê, por isso vai a `None` com
        # o interruptor de 2026-09-25 desligado — a REGRA continua a correr no
        # `loadout.sell_list` e a segurar exactamente as mesmas cópias.
        "rl_regra": ({"copias": rep["copias_rl_retidas"],
                      "total": rep["total_rl_retido"],
                      "pct": loadout.rl_subida_minima(),
                      "dias": loadout.rl_janela_dias(),
                      "minima": loadout.rl_janela_minima(),
                      "fixo": loadout.rl_limiar_fixo()}
                     if venda.mostrar() else None),
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
        # «SE NÃO MARQUEI, É PORQUE NÃO A TENHO» (André, 2026-09-09): as cópias
        # que ele procurou e não encontrou. Estão fora da colecção para todos os
        # efeitos e é AQUI que se vêem — com a foto de origem, que é a única
        # prova de que a carta existiu. A lista é a mesma no site publicado (ele
        # tem de a poder consultar fora de casa); o que só existe no modo edição
        # é o botão «afinal encontrei» e a miniatura (a foto vive no PC).
        "nao_encontradas": loadout.nao_encontradas(con),
        # ENCOMENDAS (André, 2026-09-19): o que comprou e ainda não fotografou.
        # Vive numa parte própria (`data/paginas/deckboxes/encomendas.json`); o
        # índice fica só com os `totais`, que é o que a fila de abas mostra.
        "encomendas": _encomendas_payload(con, rep, imgs, baratas),
        # REVALIDAÇÃO POR FOTO (André, 2026-09-20): o progresso total, o alvo
        # que ele está a fotografar, o que entrou hoje, as discrepâncias
        # corrigidas e as cópias novas nesta campanha. Parte própria
        # (`deckboxes/revalidacao.json`); o índice fica com os totais. `None`
        # com a campanha desligada — a aba não aparece.
        "revalidacao": prog,
        # A FEIRA (André, 2026-09-20): a moeda de troca (a venda, com as taxas
        # dele) contra o que quer trazer (o «a comprar» das caixas + a wantlist
        # manual + os vendors). Parte própria (`deckboxes/feira.json`); o
        # índice fica com os totais e o saldo. Tudo do `mtgvault.feira`.
        "feira": fr,
    }


# A VISTA POR OMISSÃO (André, 2026-09-20: *"gosto de ter em imagem da carta e
# não apenas texto, faz algo visualmente apelativo"*): `imagens`, salvo se o
# config disser `lista` (`colecao_config.json -> deckboxes.vista`). É o que o
# interruptor «Imagens / Lista» do modo edição grava (`/api/vista`).
VISTAS = ("imagens", "lista")


def vista_config(cfg: dict | None = None) -> str:
    from mtgvault import sources                               # noqa: PLC0415
    d = (cfg if cfg is not None else sources.config()).get("deckboxes")
    v = (d or {}).get("vista") if isinstance(d, dict) else None
    return v if v in VISTAS else "imagens"


# ---------------------------------------------------------------------------
# OS DADOS À PARTE (André, 2026-09-15). A página eram 700 KB, dos quais 670 KB
# eram o payload dentro do `<script id="dados">` — e o telemóvel dele, na rede
# de casa, esperava por tudo antes de desenhar o menu. Agora o HTML é a CASCA e
# os dados partem-se em: o ÍNDICE (`data/paginas/deckboxes.json`: o resumo, as
# abas, cada caixa sem a grelha) e as PARTES (`data/paginas/deckboxes/*.json`),
# que o JavaScript vai buscar quando ele abre a aba: uma por caixa, e uma por
# cada aba pesada (arrumar, venda, compras, premodern). O `html_page` continua
# a saber embutir tudo (é o que os testes e o harness de `node` lêem).
# ---------------------------------------------------------------------------
# O que sai de uma caixa no índice: as listas grandes. O `montar` fica só com
# os números (`dentro`, `marcar_q`) — é o que o crachá «N de M na caixa» lê no
# cartão compacto, antes de a caixa ser aberta.
CAIXA_PESADO = ("cartas", "wantlist", "subs", "buscar", "lista", "montar", "eds",
                "notas_onde", "rev", "reserva")
# As abas pesadas, e o que cada ficheiro leva.
PARTES_ABAS = {"arrumar": ("arrumar",), "venda": ("venda",),
               "premodern": ("premodern",),
               "encomendas": ("encomendas",),
               # REVALIDAÇÃO (2026-09-20): as listas por cor da Colecção
               # inteira vivem aqui; o índice leva os totais e o alvo.
               "revalidacao": ("revalidacao",),
               # A FEIRA (2026-09-20): as linhas de levar e de trazer vivem
               # aqui; o índice leva os totais e o saldo (o subtítulo da aba).
               "feira": ("feira",),
               "compras": ("compras", "partilhadas", "basicas")}
# O que sai da `venda.saida` no índice (ver `partir`).
SAIDA_PESADO = ("csv", "texto_estante", "csv_validadas",
                "texto_estante_validadas")
# O que sai da `feira` no índice: os dois textos para o telemóvel são strings
# (escalares para o `_so_escalares`) e são o que a parte tem de maior.
FEIRA_PESADO = ("texto_levar", "texto_trazer", "texto_cardmarket")


def _so_escalares(d):
    """A cópia de um dicionário sem as listas — os totais ficam, as linhas vão
    para a parte. É o que o Plano e a fila de abas lêem sem abrir a aba."""
    return {k: (_so_escalares(v) if isinstance(v, dict) else v)
            for k, v in d.items() if not isinstance(v, list)}


def _caixa_leve(c):
    leve = {k: v for k, v in c.items() if k not in CAIXA_PESADO}
    leve["montar"] = _so_escalares(c.get("montar") or {})
    # Os totais da revalidação ficam (o cartão compacto diz «validadas N/M»);
    # a lista de cópias vai na parte da caixa. `None` continua `None`.
    leve["rev"] = _so_escalares(c["rev"]) if c.get("rev") else None
    leve["parte"] = "caixa-" + paginas.slug(c["slot"])
    return leve


def partir(dados):
    """`(indice, {parte: obj})` — o payload repartido pelos ficheiros."""
    partes = {}
    idx = dict(dados)
    idx["caixas"] = [_caixa_leve(c) for c in dados["caixas"]]
    for c in dados["caixas"]:
        partes["caixa-" + paginas.slug(c["slot"])] = c
    for nome, chaves in PARTES_ABAS.items():
        if len(chaves) == 1:
            partes[nome] = dados[chaves[0]]
            # Uma aba que hoje não existe (a revalidação com a campanha
            # desligada) é `None` nos dois lados, não um dicionário vazio.
            idx[chaves[0]] = (_so_escalares(dados[chaves[0]])
                              if dados[chaves[0]] is not None else None)
            # O CSV e o texto da estante são strings — escalares para o
            # `_so_escalares` — mas são os dois textos mais compridos da página
            # e o índice não os precisa: ficam só na parte `venda`.
            # `idx["venda"]` é `None` com o interruptor de 2026-09-25 desligado
            # — a mesma forma da revalidação sem campanha.
            if chaves[0] == "venda" and idx["venda"] and "saida" in idx["venda"]:
                idx["venda"]["saida"] = {k: v for k, v in idx["venda"]["saida"].items()
                                         if k not in SAIDA_PESADO}
            if chaves[0] == "feira" and idx["feira"]:
                idx["feira"] = {k: v for k, v in idx["feira"].items()
                                if k not in FEIRA_PESADO}
        else:
            partes[nome] = {k: dados[k] for k in chaves}
            for k in chaves:
                idx.pop(k, None)
    # A fila de abas diz «N cartas» nas Partilhadas sem carregar a parte.
    idx["n_partilhadas"] = len(dados["partilhadas"])
    idx["n_compras"] = len(dados["compras"])
    return idx, partes


def juntar(idx, partes):
    """O inverso do `partir`: o payload inteiro, como o `html_page` o embute."""
    dados = {k: v for k, v in idx.items()
             if k not in ("n_partilhadas", "n_compras", "_gerado_em", "_partes")}
    dados["caixas"] = [partes[c["parte"]] for c in idx["caixas"]]
    for nome, chaves in PARTES_ABAS.items():
        if len(chaves) == 1:
            dados[chaves[0]] = partes[nome]
        else:
            dados.update(partes[nome])
    return dados


def ler_dados(out_path):
    """O payload inteiro lido dos ficheiros que o `build` escreveu."""
    return juntar(*paginas.ler_dados(Path(out_path), "deckboxes"))


def js_texto() -> str:
    """O JavaScript inteiro da página — o que vai para `deckboxes.js` e o que o
    `html_page` embute. Uma função, para as duas saídas nunca divergirem."""
    return (JS.replace("%JS_DADOS%", paginas.JS_DADOS)
              .replace("%JS_ICONES%", shell.js_icones()))


def js_versao(texto: str | None = None) -> str:
    """O `?v=` do `<script src>`: um hash curto do CONTEÚDO. Uma alteração ao
    JavaScript muda o URL e o browser vai buscar o novo; sem alteração, o que
    tem em cache serve — é o que permite dizer-lhe `immutable`."""
    return hashlib.sha1((texto if texto is not None else js_texto())
                        .encode("utf-8")).hexdigest()[:12]


NOME_JS = "deckboxes.js"


def casca():
    """A página SEM dados: o que o site e o modo edição servem.

    Leva o JavaScript por REFERÊNCIA (`deckboxes.js?v=<hash>`), não embutido —
    ver `JS`. Quem a serve tem de servir também o ficheiro: o `build` escreve-o
    ao lado, o `webapp.py` dá-o da memória."""
    return _html(None, js_externo=True)


def build(con, out_path=None, editable=False, rep=None):
    out = Path(out_path) if out_path else (ROOT / "deckboxes.html")
    rep = rep if rep is not None else loadout.report(con)
    idx, partes = partir(payload(con, rep, editable=editable))
    paginas.escrever_dados(out, "deckboxes", idx, partes)
    # O JavaScript primeiro: se a escrita da casca falhar a meio, o ficheiro
    # antigo continua a apontar para um `.js` que existe.
    out.with_name(NOME_JS).write_text(js_texto(), encoding="utf-8")
    out.write_text(casca(), encoding="utf-8")
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
            f'<style>body{{background:#07080d;color:#eef0f6;font:15px/1.6 '
            f'system-ui,sans-serif;margin:0;display:flex;min-height:100vh;'
            f'align-items:center;justify-content:center;text-align:center;'
            f'padding:24px}}a{{color:#f5c451}}</style>'
            f'<div><h1>🧰 Mudou de sítio</h1><p>Os decks e as deckboxes passaram '
            f'a ser <b>a mesma página</b>: cada deck é uma caixa, com a lista, o '
            f'que falta comprar e o que tirar da coleção para o montar.</p>'
            f'<p><a href="{destino}">Ir para as Deckboxes →</a></p></div>')


def _html(dados, js_externo: bool = False):
    # Com `dados` a página leva o payload EMBUTIDO (`<script id="dados">`); sem
    # eles é a casca, e o JavaScript vai buscá-los a `data/paginas/`.
    # O `</` escapado é o que impede um nome de carta com `</script>` de fechar
    # a etiqueta a meio do payload.
    script = ("" if dados is None else
              '<script id="dados" type="application/json">'
              + json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")
              + "</script>")
    js = js_texto()
    # O JavaScript: por referência na casca (cacheável, ver `JS`) ou embutido
    # (o `html_page`, que os testes lêem de um ficheiro solto sem servidor).
    codigo = (f'<script src="{NOME_JS}?v={js_versao(js)}"></script>' if js_externo
              else "<script>\n" + js + "</script>")
    return (_tmpl()
            .replace("%TEMA_DADOS%", paginas.CSS_DADOS)
            .replace("%DADOS_SCRIPT%", script)
            .replace("%SCRIPT%", codigo))


def html_page(con, editable=False, rep=None, token="", ligacao=None):
    """A página como texto — é o que o `webapp.py` serve sem escrever no disco.

    `token`/`ligacao` só vêm preenchidos quando o pedido já trazia o token: é o
    que autoriza os botões a gravar e o que desenha o QR para o telemóvel.
    """
    return _html(payload(con, rep if rep is not None else loadout.report(con),
                         editable=editable, token=token, ligacao=ligacao))


_CSS = r"""
 h2{font-size:13px;margin:22px 0 4px;color:var(--muted);text-transform:uppercase;
    letter-spacing:.09em;font-weight:700} h2 .n{color:var(--dim);font-weight:600}
 h3{font-size:14px;margin:16px 0 6px;font-weight:700}
 .lead{color:var(--muted);font-size:13px;margin:2px 0 12px} .lead b{color:var(--ink2)}
 .dim{color:var(--dim)}
 /* Os números do dia, em chips (ver `renderResumo`). */
 .pgsub .rsl{display:flex;flex-wrap:wrap;gap:8px 10px;margin-bottom:7px}
 .rs{display:inline-flex;flex-direction:column;gap:1px;padding:6px 12px;
   border-radius:10px;background:var(--card);border:1px solid var(--line);
   text-decoration:none;color:var(--ink);min-width:84px}
 .rs:hover{border-color:var(--accent)}
 .rs b{font-family:var(--font-hd);font-size:17px;font-weight:700;line-height:1.15;
   font-variant-numeric:tabular-nums}
 .rs small{color:var(--dim);font-size:10.5px;font-weight:600;white-space:nowrap}
 .pgsub .rsd{display:block;font-size:11.5px}
 /* O interruptor do MODO DE PREÇO (2026-09-25), no cabeçalho e só em modo
    edição. Os alvos seguem a régua do telemóvel de 18/09 (≥ 36 px) — ele está
    à frente da estante quando decide. */
 .pgsub .rsp{display:flex;align-items:center;gap:8px;margin-top:7px;flex-wrap:wrap}
 .pgsub .rsp .seg button{min-height:36px;padding:0 12px;font-size:12px}
 /* O ÍNDICE DAS CAIXAS E DAS VISTAS (reestruturação de 2026-09-24).
    Era a `.decktabs`: até 27 botões numa fila com `overflow-x:auto` — o
    *"andar a correr os botões para os lados"* do pedido dele. Agora é uma
    coluna à esquerda do conteúdo (≥900 px), com cabeçalhos de grupo; no
    telemóvel a coluna dá lugar a um `<select>` (`.vidxsel`), que abre a lista
    inteira de uma vez em vez de a fazer deslizar. As classes base (`.vidx`,
    `.comidx`, `.vidxsel`) são as da casca — aqui só o que é desta página. */
 #decktabs .dt{width:100%}
 .dt .pin{width:7px;height:7px;border-radius:50%;display:inline-block;flex:none;
   margin-right:2px}
 .pin.ok{background:var(--add)} .pin.mid{background:var(--gold)} .pin.low{background:var(--warn)}
 /* o ponto de uma caixa MONTADA: verde por estar montada, com anel para não se
    confundir com o verde de "90 % ou mais" da caixa que ainda falta montar */
 .pin.done{background:var(--add);box-shadow:0 0 0 2px #0f2a1c}
 .dt.cand .vtx{opacity:.92}
 .dtsep{display:block;padding:11px 10px 5px;font-size:10px;font-weight:700;
   letter-spacing:.11em;text-transform:uppercase;color:var(--dim)}
 /* cabeçalho de uma caixa */
 .box{background:var(--card);border:1px solid var(--line);border-radius:var(--r2);
   padding:15px}
 .box+.box{margin-top:12px}
 .btop{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
   flex-wrap:wrap}
 .btop b{font-size:17px;letter-spacing:-.01em}
 /* A FOTO DA DECKBOX FÍSICA (2026-09-21): a miniatura ao lado do nome (no
    cartão da fila e na aba Revalidação), a foto maior no cabeçalho da aba da
    caixa, o quadrado «sem foto» (que só no modo edição é botão — um `<label>`
    com o `<input type="file">` escondido) e o véu de ampliar. */
 .btit{display:inline-flex;align-items:center;gap:8px;min-width:0}
 .dbthumb{width:44px;height:44px;border-radius:8px;object-fit:cover;flex:none;
   background:#0a0d13;border:1px solid var(--line2);display:block}
 span.dbthumb{display:inline-flex;align-items:center;justify-content:center;
   font-size:18px;color:var(--dim);border-style:dashed}
 .dbfoto{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0}
 .dbfoto img{max-height:200px;max-width:100%;border-radius:10px;cursor:zoom-in;
   border:1px solid var(--line2);background:#0a0d13;display:block}
 .dbfoto .dbleg{display:flex;flex-direction:column;gap:6px;align-items:flex-start;
   font-size:12px;color:var(--muted)}
 .dbfoto .dbq{display:inline-flex;flex-direction:column;align-items:center;
   justify-content:center;gap:2px;min-width:150px;min-height:72px;padding:10px 14px;
   border:1px dashed var(--line2);border-radius:10px;background:#0f141c;
   color:var(--dim);font-size:12.5px;text-align:center}
 .dbfoto label.dbq{cursor:pointer;color:var(--ink2);border-color:#3f5478}
 .dbfoto label.dbq:hover{background:#151d29}
 .dbfoto label.dbq small{color:var(--dim);font-size:11px}
 .dbfoto label input{display:none}
 .dbfoto label.aenviar{opacity:.5;pointer-events:none}
 .lightbox{position:fixed;inset:0;background:#000d;z-index:20;display:flex;
   flex-direction:column;align-items:center;justify-content:center;gap:10px;
   cursor:zoom-out;padding:12px}
 .lightbox img{max-width:96vw;max-height:86vh;border-radius:8px;object-fit:contain}
 .lightbox span{color:#d8dee8;font-size:13px}
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
 /* REVALIDAÇÃO POR FOTO (2026-09-20): o selo 📷 no canto da miniatura, a barra
    «validadas N/M», as linhas por cópia com o estado, o alvo e o bloco. */
 .cd .rvb{position:absolute;top:2px;left:2px;background:#000d;color:#ffd27a;
   font-size:10px;font-weight:700;padding:0 4px;border-radius:5px;line-height:15px}
 .cd .rvb.corr{color:#ff9f6b}
 .rvbar{display:flex;flex-direction:column;gap:4px;margin:8px 0;font-size:12.5px;
   color:var(--muted)}
 .rvbar b{color:var(--ink)} .rvbar b.warn{color:#ffd27a}
 .rvbar .pg{display:block;position:relative;height:6px;background:#0a0d13;
   border-radius:999px;overflow:hidden;border:1px solid var(--line)}
 .rvbar .pg b{position:absolute;left:0;top:0;bottom:0;background:var(--add);
   border-radius:999px}
 .rvbar.mini{margin:6px 0 0;font-size:11.5px}
 .blk.rev{background:#131a22;border-color:#2a3b52}
 .blk.rev .flh{color:#ffd27a}
 .mv.rv{opacity:1;text-decoration:none}
 .mv.rv .to{white-space:nowrap}
 .mv.rv.foto .to{color:#ffd27a} .mv.rv.ok .to{color:var(--add)}
 .mv.rv.corr .to{color:#ff9f6b}
 .mv.rv.ok{opacity:.72}
 .rvalvo{margin:8px 0;padding:10px 12px;background:#1a1509;border:1px solid #4a3a12;
   border-radius:var(--r);font-size:12.5px;color:var(--muted)}
 .rvalvo>b{color:var(--gold)} .rvalvo .nota{margin:4px 0 8px}
 /* AS FOTOS DAS CARTAS, DO SITE (2026-09-21): o «Tirar fotos» é um <label>
    com o <input type="file"> escondido — tem de parecer botão e ter 40 px no
    telemóvel; o 📷 por cópia fica no rodapé do tile (`.tla`). */
 .fstirar{display:inline-flex;align-items:center;gap:6px;cursor:pointer}
 .fstirar input,.fscam input{display:none}
 label.aenviar{opacity:.5;pointer-events:none}
 .fscam{cursor:pointer;min-width:0;padding:0 8px}
 .fsite{margin:8px 0;padding:10px 12px;background:#101a14;border:1px solid #24402c;
   border-radius:var(--r);font-size:12.5px;color:var(--muted)}
 .fsite .flh{color:var(--add)}
 .fsl{margin:6px 0;padding-left:18px} .fsl li{margin:2px 0;word-break:break-all}
 .fsl code{font-size:11.5px;color:var(--ink)} .fsl ul{padding-left:16px;margin:2px 0}
 .rvcaixas{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
   gap:10px;margin:8px 0 14px}
 .rvc .mini{width:100%;text-align:left;padding:10px 12px}
 .rvc .mini b{color:var(--ink)}
 .rvc .seg{margin:6px 0 0}
 .vt td.rvok{color:var(--add);font-weight:700;text-align:center}
 .vt td.rvfoto{color:#ffd27a;font-weight:700;text-align:center;white-space:nowrap}
 .el.rvfoto .nm small{color:#ffd27a}
 details.vblk.rev summary .vtot{color:#ffd27a}
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
 /* LISTA PADRÃO e RESERVA (André, 2026-09-20) */
 .blk.padrao{background:#101a14;border-color:#254a33} .blk.padrao>b{color:#8fd9a8}
 .blk.reserva{background:#1a1810;border-color:#4a4325} .blk.reserva>b{color:var(--gold)}
 .blk.reserva li{padding:3px 0} .blk.reserva .rsv-ok{color:var(--add)}
 .blk.reserva .rsv-no{color:#ffd27a}
 /* A FEIRA (André, 2026-09-20): levar vs. trazer */
 .feira .num.sal b{font-size:19px} .feira .num.sal.pos b{color:var(--add)}
 .feira .num.sal.neg b{color:#ff9f8f}
 .feira .taxas{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;
   background:#1a1810;border:1px solid #4a4325;border-radius:10px;padding:8px 12px;
   margin:8px 0;font-size:12.5px}
 .feira .taxas label{display:flex;align-items:center;gap:6px}
 .feira .taxas input{width:64px;font:inherit;font-size:13px;padding:6px 8px;
   border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);
   min-height:40px;text-align:right}
 .feira .taxas .nota{flex:1 1 100%;margin:0}
 .feira table.vt tr.nao td{opacity:.45;text-decoration:line-through}
 .feira table.vt tr.nao td.act,.feira table.vt tr.nao td.act *{opacity:1;text-decoration:none}
 .feira table.vt td.act{white-space:nowrap}
 .feira .vend{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:10px;
   background:#101c2e;color:#7fa8ff;margin:1px 3px 1px 0;white-space:nowrap}
 .feira .org{font-size:10px;font-weight:800;padding:1px 5px;border-radius:5px;
   background:#14262a;color:#79c9c4;margin-left:5px;white-space:nowrap}
 .feira .org.man{background:#2c1b2e;color:#e0a8ea}
 .feira .pform input.px{width:74px}
 .feira .vendors li{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;
   padding:4px 0;border-bottom:1px solid #1a212c}
 .feira .vendors li small{color:var(--dim)}
 .feira .corhdr{margin-top:10px}
 .pform{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px}
 .pform input,.pform select{font:inherit;font-size:12.5px;padding:7px 10px;
   border-radius:8px;border:1px solid var(--line);background:var(--card);
   color:var(--ink);min-height:40px}
 .pform input.nm{flex:1 1 160px;min-width:0} .pform input.q{width:58px}
 .pform textarea{width:100%;min-height:120px;font:inherit;font-size:12px;
   border-radius:8px;border:1px solid var(--line);background:var(--card);
   color:var(--ink);padding:8px}
 .blk .btn.sm{margin-left:6px}
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
 /* vistas "Decks montados" / "Decks para montar": o cartão é o mesmo da vista
    Todas, e o que muda é a barra por baixo. O `.mini` continua a ser um botão
    inteiro (a navegação), e os botões de acção ficam FORA dele — um botão
    dentro de outro não é HTML válido nem sobrevive ao clique. */
 .mcard{display:flex;flex-direction:column}
 .mcard .mini{flex:1;border-bottom-left-radius:0;border-bottom-right-radius:0;
   border-bottom:0}
 .macts{display:flex;gap:8px;flex-wrap:wrap;align-items:center;
   background:var(--card);border:1px solid var(--line);border-top:1px dashed var(--line);
   border-radius:0 0 var(--r2) var(--r2);padding:9px 13px}
 .macts .quando{font-size:11.5px;color:var(--muted)}
 .macts .quando b{color:var(--ink2)}
 .macts .quando.aviso{color:var(--gold)}
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
 /* a saída da venda (2026-09-18): o CSV, a estante e o que fica de fora */
 .sfmt{font-size:12px;color:var(--muted);border:1px dashed var(--line);
   border-radius:8px;padding:7px 10px;margin:6px 0 10px;line-height:1.5}
 .sfmt.nao{border-color:#7a5a20;color:#e6c27a} .sfmt b{color:var(--ink2)}
 .est{margin:8px 0 4px} .estg{margin:10px 0 12px}
 .estg>h4{margin:0 0 4px;font-size:14px;display:flex;justify-content:space-between;
   gap:10px;flex-wrap:wrap;border-bottom:2px solid var(--line);padding-bottom:4px}
 .estg>h4 span{color:var(--gold);font-variant-numeric:tabular-nums;font-weight:800;
   font-size:13px}
 .el{display:flex;align-items:center;gap:8px;padding:5px 2px;
   border-bottom:1px solid #1a212c;font-size:13.5px;line-height:1.35}
 .el:last-child{border-bottom:0}
 .el .c{flex:0 0 auto;font-size:10px;font-weight:800;width:20px;height:20px;
   border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
   background:#1c2430;color:var(--muted)}
 .el .c.W{background:#efe6c4;color:#5a4a10} .el .c.U{background:#1f4c8f;color:#dbe8ff}
 .el .c.B{background:#3a3040;color:#e6d6f0} .el .c.R{background:#8f2a1f;color:#ffe0d6}
 .el .c.G{background:#1f6b3a;color:#dcffe6} .el .c.M{background:#7a5a20;color:#ffe9a8}
 .el .c.L{background:#5a4a3a;color:#f0e6d6}
 .el .q{color:var(--gold);font-weight:800;font-variant-numeric:tabular-nums;
   flex:0 0 auto;min-width:26px}
 .el .nm{flex:1 1 auto;min-width:0} .el .nm small{display:block;color:var(--muted);
   font-size:11.5px}
 .el .pz{flex:0 0 auto;color:var(--ink2);font-variant-numeric:tabular-nums;
   font-size:12.5px}
 .fora{margin-top:10px} .fora>details{margin:6px 0;border:1px solid var(--line);
   border-radius:8px;padding:7px 10px;background:#10151d}
 .fora summary{cursor:pointer;font-size:13px;font-weight:700;display:flex;
   justify-content:space-between;gap:8px;flex-wrap:wrap}
 .fora summary span{color:var(--muted);font-weight:600;font-variant-numeric:tabular-nums}
 .fora p{margin:5px 0 6px;font-size:12px;color:var(--muted)}
 .fora ul{margin:0;padding-left:18px;font-size:12.5px} .fora li{margin:2px 0}
 .fora li i{color:var(--muted)}
 @media print{
   .vidx,.vidxsel,.seg,.flh,.cpbtn,button,textarea.cmk,#barra,.lig{display:none!important}
   body{background:#fff;color:#000} .wrap{padding:0;max-width:none}
   .comidx{display:block}
   details.vblk{border:0;padding:0;break-inside:avoid} details.vblk>summary{color:#000}
   .estg>h4{border-bottom:1px solid #000} .estg>h4 span,.el .q{color:#000}
   .el{border-bottom:1px solid #ddd;font-size:12px} .el .nm small,.el .pz{color:#333}
   .el .c{border:1px solid #999;background:#fff!important;color:#000!important}
 }
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
 /* LINHA INCOMPLETA (2026-09-08): a caixa pede 4 e ele só tem 2. As 2 tiram-se
    na mesma — a moldura âmbar é a mesma do "está noutra caixa", porque a
    pergunta é a mesma: esta linha não fecha com o que está aqui. */
 .mv.parc{border-left:2px solid #e2a15b;padding-left:5px}
 .parcn{color:#e2a15b;font-weight:700}
 /* «JÁ A TENHO, ESTÁ NO DECK» (André, 2026-09-08): o check de uma linha de
    compra, e o bloco das cópias que ele já declarou. O verde é o mesmo do
    «na caixa»: são cartas que já estão na estante, ao contrário do âmbar das
    que estão noutra caixa. */
 .jat{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:4px}
 .jat label{display:flex;align-items:center;gap:6px;color:var(--add);
   font-size:11.5px;font-weight:600;cursor:pointer}
 .jat input{width:17px;height:17px;flex:0 0 17px;accent-color:var(--add);
   cursor:pointer}
 select.jed{font:inherit;font-size:11px;max-width:210px;padding:3px 5px;
   border-radius:6px;border:1px solid var(--line2);background:var(--card);
   color:var(--ink2)}
 .jnc{margin:10px 0 8px;background:#101a14;border:1px solid #23402c;
   border-radius:var(--r);padding:9px 11px}
 .jnc .flh{color:#6fbf8a}
 .jnc .mv{opacity:1;text-decoration:none;border-bottom-color:#1a2b20}
 .jnc .mv .to{color:#e2a15b}
 /* ENCOMENDAS (André, 2026-09-19): «só a foto cria cópias». Os `+`/`−` e o
    «Chegou» numa linha de compra, e o separador com tiles à imagem do
    riftvault. Azul tracejado = a caminho (não é uma cópia); verde = chegou e
    espera foto. Alvos de toque ≥ 40 px, como o resto (2026-09-18). */
 .encs{display:block;color:#7fa8ff;font-size:11px;line-height:1.35}
 .encs .pf{color:var(--add)}
 .stp{display:inline-flex;align-items:center;gap:4px;margin-left:6px;
   vertical-align:middle;flex-wrap:wrap}
 .stp .btn.sm{min-width:36px;padding:3px 8px;font-weight:800}
 .stp .btn.sm.chg{background:#123020;border-color:#2f6a45;color:var(--add)}
 ul.fl li.enc-l{border-left:2px dashed #7fa8ff;padding-left:6px}
 .enc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
   gap:9px;margin:10px 0}
 .enct{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
   padding:8px;display:flex;flex-direction:column;gap:5px;font-size:12px}
 .enct.caminho{border:1px dashed #7fa8ff}
 .enct.foto{border-color:#2f6a45}
 .enct.base{border-style:dotted}
 .enct.aviso{border-color:var(--warn)}
 .enct .cd{aspect-ratio:.716;border-radius:6px;overflow:hidden;background:#0c0f14}
 .enct .cd img{width:100%;height:100%;object-fit:cover;display:block}
 .enct .cd .cq{font-size:12px;padding:1px 6px}
 .enct .en{font-weight:700;font-size:12.5px;line-height:1.3;overflow-wrap:anywhere}
 .enct .ed{color:var(--muted);font-size:11px;line-height:1.35}
 .enct .ed b{color:var(--gold);font-variant-numeric:tabular-nums}
 .enct .ea{color:#ff9f8f;font-size:11px;line-height:1.35}
 .enct .stp{margin:0;justify-content:space-between}
 .enct .stp .btn.sm{flex:1 1 auto;text-align:center}
 .enct .btn.chg{width:100%;background:#123020;border-color:#2f6a45;color:var(--add)}
 .enc-h{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
   flex-wrap:wrap;margin:14px 0 2px;border-bottom:1px solid var(--line);
   padding-bottom:3px}
 .enc-h b{font-size:14px} .enc-h span{color:var(--muted);font-size:12px;
   font-variant-numeric:tabular-nums}
 .enc-nota{background:#101c2e;border:1px solid #25415e;border-radius:var(--r);
   padding:9px 12px;font-size:12.5px;color:#c9d8ff;margin:8px 0}
 .enc-nota code{background:#0f141c;padding:1px 5px;border-radius:4px}
 @media(max-width:640px){
   .enc-grid{grid-template-columns:repeat(auto-fill,minmax(132px,1fr))}
   .stp .btn.sm{min-height:40px;min-width:44px}
 }
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
 /* NÃO ENCONTRADAS (2026-09-09): a foto de origem à esquerda, porque é ela que
    responde à pergunta ("existiu? sumiu?"). A cinzento e não a vermelho — não é
    um erro, é uma carta que já não está lá. */
 .nenc{display:grid;gap:7px;margin:10px 0}
 .ne{display:flex;gap:10px;align-items:center;background:#12141a;
   border:1px solid var(--line2);border-radius:var(--r);padding:8px 10px}
 .ne .nei{flex:0 0 54px}
 .ne .nef{width:54px;border-radius:5px;display:block;filter:grayscale(.55)}
 .ne .nef.vazia{display:flex;align-items:center;justify-content:center;
   height:54px;background:#0d1017;border:1px dashed var(--line2);
   color:var(--dim);font-size:10px;text-align:center}
 .ne .neb{flex:1;min-width:0}
 .ne .neb b{display:block}
 .ne .neb small{display:block;color:var(--dim);font-size:11.5px}
 .ne .neb code{font-size:10.5px;color:var(--muted)}
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
 /* O RESUMO ANTES DE GRAVAR (2026-09-09): três saídas — registar e ir buscar o
    resto, registar e dizer que não tem o resto, ou cancelar. Um `confirm()` do
    browser só tem duas, e a do meio muda a colecção inteira. */
 .modal{position:fixed;inset:0;z-index:12;background:#000a;display:flex;
   align-items:center;justify-content:center;padding:16px}
 .modal .cx{background:#111823;border:1px solid var(--line2);border-radius:12px;
   padding:16px 18px;max-width:440px;box-shadow:0 12px 40px #000b}
 .modal .cx b{font-size:14px}
 .modal .cx p{margin:8px 0 0;font-size:13px}
 .modal .mb{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
 .modal .nota{color:var(--muted);font-size:11.5px}
 /* BARRA DE MONTAGEM (André, 2026-09-08): o «N de M» e o botão de registar
    sempre à mão, fixos no fundo do ecrã. O botão de hoje vive no fim do passo 1
    — 58 linhas abaixo — e à frente da estante, no telemóvel, ele não o achou. */
 .barra{position:fixed;left:0;right:0;bottom:0;z-index:36;
   background:rgba(14,16,24,.96);backdrop-filter:blur(10px);
   border-top:1px solid var(--line2);box-shadow:0 -8px 26px #0008;
   padding:9px clamp(14px,2.6vw,30px) calc(9px + env(safe-area-inset-bottom,0px))}
 .barra[hidden]{display:none}
 body.combarra .wrap{padding-bottom:118px}
 /* A barra alinha com o conteúdo: em ecrã largo a barra lateral come 258 px à
    esquerda, e uma barra centrada no ecrã inteiro ficava ao lado da coluna. */
 @media(min-width:900px){ .barra{left:var(--side)} }
 .barra .bi{max-width:var(--maxw);margin:0 auto;display:flex;gap:12px;
   align-items:center;flex-wrap:wrap}
 .barra .bt{flex:1 1 230px;min-width:0}
 .barra .bt b{font-size:13.5px;display:block;overflow:hidden;
   text-overflow:ellipsis;white-space:nowrap}
 .barra .bt small{color:var(--muted);font-size:11.5px;
   font-variant-numeric:tabular-nums}
 .barra .pg{height:7px;border-radius:6px;background:#1a212c;overflow:hidden;
   margin-top:5px}
 .barra .pg i{display:block;height:100%;background:var(--info);
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
 @media(max-width:640px){
   .cards{grid-template-columns:repeat(auto-fill,minmax(50px,1fr))}
   table.vt td.rz,table.vt th.rz{display:none}
   .num{min-width:calc(50% - 6px)}
 }
 /* AS CARTAS EM IMAGEM (André, 2026-09-20: «cada deck poderia ter as cartas
    visualmente ao invés de só o nome?»). UMA componente — `.tl` — para todas
    as secções: a imagem da impressão exacta, e por cima dela a quantidade, o
    estado (a cor da moldura e o chip), o material e, quando é compra, o preço.
    Os botões que a lista tinha ficam no rodapé do tile. Sem imagem (o
    catálogo não a tem, ou o `fetch` falhou) fica o NOME no quadrado — nunca
    um buraco. 3 colunas a 400 px, mais em ecrã largo; a checkbox tem 28 px. */
 .tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));
   gap:8px;margin:8px 0;padding:0;list-style:none;min-width:0}
 .tiles.big{grid-template-columns:repeat(auto-fill,minmax(170px,1fr))}
 .tl{display:flex;flex-direction:column;gap:3px;min-width:0;position:relative;
   background:var(--card);border:1px solid var(--line);border-radius:10px;
   padding:5px;font-size:11.5px;color:var(--ink2);margin:0;cursor:default}
 label.tl{cursor:pointer}
 .tl .tli{position:relative;display:block;aspect-ratio:.716;border-radius:7px;
   overflow:hidden;background:#0c0f14;cursor:pointer}
 .tl .tli img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;
   display:block;z-index:1}
 .tl .tlnm{position:absolute;inset:0;display:flex;align-items:center;
   justify-content:center;text-align:center;padding:8px;font-size:11px;
   font-weight:700;color:var(--muted);line-height:1.3;overflow-wrap:anywhere}
 .tl .tlq{position:absolute;left:4px;bottom:4px;z-index:2;background:#000d;
   color:#fff;font-weight:800;font-size:12px;padding:1px 6px;border-radius:6px;
   font-variant-numeric:tabular-nums}
 .tl .tlm{position:absolute;right:4px;bottom:4px;z-index:2;display:flex;gap:2px;
   flex-wrap:wrap;justify-content:flex-end;max-width:70%}
 .tl .tlm span{background:#000d;color:#ffd27a;font-size:9.5px;font-weight:800;
   padding:1px 4px;border-radius:5px;white-space:nowrap}
 .tl .tlr{position:absolute;left:4px;top:4px;z-index:2;background:#000d;
   color:#fff;font-size:9.5px;font-weight:800;padding:1px 5px;border-radius:5px;
   max-width:calc(100% - 8px);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .tl .tlt{font-weight:700;line-height:1.25;overflow-wrap:anywhere;display:-webkit-box;
   -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:var(--ink)}
 .tl .tlx{color:var(--muted);font-size:10.5px;line-height:1.3;overflow-wrap:anywhere}
 .tl .tlx b{color:var(--gold);font-variant-numeric:tabular-nums}
 .tl .tlx .parcn{color:#e2a15b}
 .tl .tla{display:flex;flex-wrap:wrap;gap:4px;margin-top:auto;align-items:center;
   min-width:0}
 .tl .tla .stp{margin:0;min-width:0} .tl .tla .jat{margin:0;min-width:0;max-width:100%}
 /* Um `<select>` tem a largura da opção mais comprida e não encolhe: numa
    coluna de 120 px empurrava a grelha para fora do ecrã (medido a 400 px).
    Com `width:100%` e `min-width:0` cabe na coluna e corta o texto. */
 .tl .tla select.jed,.tl .tla select.feira-vend{max-width:100%;min-width:0;width:100%}
 .tl .tla .btn.sm{min-width:0}
 .tl input.tlck{position:absolute;top:4px;right:4px;z-index:3;width:28px;height:28px;
   margin:0;accent-color:var(--add);cursor:pointer}
 .tl.feito .tli{opacity:.45} .tl.feito .tlt{text-decoration:line-through;opacity:.6}
 /* os estados: a moldura da imagem diz o mesmo que a grelha de sempre */
 .tl.have .tli,.tl.ok .tli{box-shadow:0 0 0 2px var(--add)} .tl.have .tlr,.tl.ok .tlr{color:var(--add)}
 .tl.miss .tli{box-shadow:0 0 0 2px var(--warn)} .tl.miss .tli img{filter:grayscale(.75) brightness(.55)}
 .tl.miss .tlr{color:#ff9f8f}
 .tl.sub .tli,.tl.rev .tli,.tl.res .tli{box-shadow:0 0 0 2px var(--gold)}
 .tl.sub .tli img{filter:grayscale(.35) brightness(.7)} .tl.sub .tlr,.tl.rev .tlr,.tl.res .tlr{color:var(--gold)}
 .tl.enc .tli{box-shadow:0 0 0 2px #7fa8ff} .tl.enc .tlr{color:#7fa8ff} .tl.enc{border-style:dashed}
 .tl.pfoto .tli{box-shadow:0 0 0 2px var(--add)} .tl.pfoto .tlr{color:var(--add)} .tl.pfoto{border-style:dashed}
 .tl.corr .tli{box-shadow:0 0 0 2px #ff9f6b} .tl.corr .tlr{color:#ff9f6b}
 .tl.base{border-style:dotted}
 .tl.nao .tli{opacity:.35} .tl.nao .tlt{text-decoration:line-through;opacity:.6}
 .tl.parc{border-left:3px solid #e2a15b}
 .tl.aviso{border-color:var(--warn)}
 .tl .rl{margin-left:3px}
 #v-compras ul.fl.tiles{column-width:auto}
 .seg .vista{margin-left:auto}
 @media(max-width:640px){
   /* `minmax(0,1fr)` e não `1fr`: um `1fr` nunca encolhe abaixo do conteúdo
      mínimo da coluna, e a grelha saía do ecrã (medido a 400 px). */
   .tiles{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
   .tiles.big{grid-template-columns:repeat(2,minmax(0,1fr))}
   .tl{padding:4px;font-size:11px}
   .tl input.tlck{width:32px;height:32px}
   .tl .tla .btn.sm{min-height:36px;flex:1 1 auto;text-align:center}
 }
 /* O `hidden` tem de ganhar ao `display:flex` das classes: sem o `!important`
    uma linha `.mv` escondida pela procura continuava à vista. */
 [hidden]{display:none!important}
 /* A PROCURA (2026-09-18) e a barra de filtros que fica no topo do ecrã. */
 .seg.topo{position:sticky;top:var(--sticky);z-index:25;background:var(--bg);
   padding:8px 0 6px;margin:0 0 8px;box-shadow:0 8px 12px -10px #000}
 .procura{display:flex;align-items:center;gap:6px;flex:1 1 220px;min-width:0}
 .procura input{flex:1 1 auto;min-width:0;font:inherit;font-size:14px;
   padding:8px 13px;border-radius:20px;border:1px solid var(--line2);
   background:var(--card);color:var(--ink)}
 .procura input:focus{outline:none;border-color:var(--accent)}
 #procura-n{font-size:11.5px;white-space:nowrap;font-variant-numeric:tabular-nums}
 .seg.topo .salto{flex:0 0 auto;padding:7px 11px;font-size:12px;
   background:var(--card2);color:var(--ink2)}
 /* Com o scroll a saltar para um bloco, o bloco não pode nascer debaixo da
    barra presa ao topo. */
 .montar,#passo2{scroll-margin-top:calc(var(--sticky) + 64px)}
 .cd{cursor:pointer}
 /* Um botão ARMADO (o primeiro dos dois toques do «vendida»): fica a dizer o
    que vai fazer, a vermelho, até ao segundo toque ou até desarmar. */
 .btn.armado{background:#3a1f1f;border-color:#ff9f8f;color:#ff9f8f;
   font-weight:800;white-space:nowrap}
 /* O TELEMÓVEL A 390 px (2026-09-18): alvos de toque ≥ 40 px (os `.btn.sm`
    tinham 22), linhas do passo 1 ≥ 44 px e o nome da carta a partir linha em
    vez de "Swords to Plow…", a aba Plano em duas linhas em vez de "Modern —
    UW O…", e as listas do passo 1 sem scroll próprio — um `overflow:auto` de
    60vh dentro da página é uma armadilha para o dedo. */
 @media(max-width:640px){
   .btn,.cpbtn,.seg button,.selc{min-height:40px}
   .btn.sm{min-height:36px;padding:6px 11px;font-size:12px}
   .mv{min-height:44px;padding:7px 4px}
   .mv input,.jat input{width:22px;height:22px;flex-basis:22px}
   .mv .nm{white-space:normal;overflow:visible;text-overflow:clip}
   .mv .to{max-width:34%;font-size:11px}
   .mvs{max-height:none}
   .pl{flex-wrap:wrap;gap:6px 11px}
   .pl .pb{flex:1 1 calc(100% - 35px)} .pl .pb b{white-space:normal}
   .pl .pn2{flex:1 1 auto;text-align:left;min-width:0;margin-left:35px}
   .pl .pn2 ~ .pn2{margin-left:0}
   body.combarra .wrap{padding-bottom:190px}
 }
%TEMA_DADOS%
"""

_RODAPE = """
<b>Cada deck é uma caixa.</b> Esta é a página dos decks: a lista, o que falta comprar
e o que tirar da coleção para o montar%SOBRA%. Uma cópia física entra
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
%CONFIRMAR%Atualiza diariamente."""


def _rodape() -> str:
    """O rodapé, com as duas frases da venda só quando ela está à vista
    (André, 2026-09-25). Um rodapé a explicar «a lista para vender» numa página
    onde essa lista não existe é a página a prometer o que não dá."""
    if venda.mostrar():
        return (_RODAPE.replace("%SOBRA%", " e o que sobra para vender")
                .replace("%CONFIRMAR%",
                         "A lista para vender é uma <b>sugestão a confirmar</b>. "))
    return _RODAPE.replace("%SOBRA%", "").replace("%CONFIRMAR%", "")


def _tmpl() -> str:
    """O molde da página.

    É uma FUNÇÃO e não uma constante de módulo desde 2026-09-25: a barra
    lateral e o rodapé passaram a depender do `venda.mostrar`, e uma constante
    congelava-os no instante do `import` — o molde ficava com a resposta que o
    config dava ao primeiro que importasse o módulo. Não se guarda em cache: é
    concatenação de strings, corre uma vez por página gerada.
    """
    return ("""<!doctype html><html lang="pt-PT"><head>"""
            + shell.head("Deck boxes", _CSS) + """</head><body>"""
            + shell.abrir("deckboxes.html", "Deck boxes", "", "", id_sub="resumo") + r"""
<div class="wrap">
<div class="comidx">
<div>
<label class="vidxsel"><span class="vlbl">Vista</span>
<select class="selc" id="decksel" aria-label="Caixa ou vista"></select></label>
<nav class="vidx" id="decktabs" role="tablist" aria-label="Caixas e vistas"></nav>
</div>
<div id="vista" role="tabpanel" tabindex="-1" aria-live="polite"></div>
</div>
</div>
<div class="barra" id="barra" hidden aria-live="polite"></div>
""" + shell.fechar(_rodape(), """
%DADOS_SCRIPT%
%SCRIPT%""") + """
</body></html>""")


# O JAVASCRIPT DA PÁGINA, à parte do HTML (2026-09-18). A casca tinha 150 KB, e
# 123 KB eram isto — baixados outra vez a cada toque no menu do telemóvel,
# porque o `webapp.py` serve tudo com `no-store`. Agora o `build` escreve-o em
# `deckboxes.js` e a casca referencia-o com um HASH do conteúdo no `?v=`: o
# browser guarda-o para sempre, e quando o texto muda o URL muda com ele. O
# `html_page` (os testes e o harness de node) continua a EMBUTIR este mesmo
# texto — é uma string só, escrita em dois sítios, e não duas versões.
JS = r"""%JS_DADOS%
/* OS ÍCONES: o MESMO conjunto da casca (`site_shell._SVG`), injectado aqui pelo
   `js_texto()`. Um segundo conjunto escrito à mão em JavaScript era a segunda
   oportunidade de os dois discordarem — a lição do `e_foil` e do `vistoId`. */
%JS_ICONES%
/* OS DADOS (2026-09-15): `D` é o ÍNDICE — o resumo, as caixas sem a grelha, os
   totais das abas. Cada aba pesada e cada caixa têm uma PARTE em
   `data/paginas/deckboxes/`, que o `render()` vai buscar na primeira vez que
   ele a abre (`carregaParte`). Com o payload EMBUTIDO (o `script#dados` que o
   `html_page` gera e o harness de `node` lê) está tudo já cá e não há um
   único `fetch`. */
let D = null;
const PARTES = {};
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
/* `8 426,34 €` e não `8426,34 €`: é o número por que ele decide, e sem o
   separador dos milhares um `4619,24` lê-se mal ao lado de um `461,92`. O
   agrupamento é o mesmo do Python (`mtgvault.paginas.eur`). */
const eur = v => v
  ? v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d),)/g, ' ') + ' €'
  : '—';
const art = sid => sid
  ? `https://cards.scryfall.io/small/front/${sid[0]}/${sid[1]}/${sid}.jpg` : '';
/* «1 cópias» aparecia em três blocos ao mesmo tempo — o "ir buscar a outra
   caixa", o "na gaveta" e o "mais N estão noutra caixa" — e nenhum deles é raro:
   uma caixa costuma ter UMA carta noutro sítio. Um número e um plural fixo é
   uma frase que ele lê todos os dias em português macarrónico. */
const pl = n => (n === 1 ? '' : 's');
const cop = n => `${n} cópia${pl(n)}`;
const car = n => `${n} carta${pl(n)}`;
const cor = p => p >= 90 ? 'var(--add)' : p >= 60 ? 'var(--gold)' : 'var(--warn)';
const pin = p => p >= 90 ? 'ok' : p >= 60 ? 'mid' : 'low';
/* Acima disto (por cópia) a compra é uma decisão à parte, não uma ida ao
   Cardmarket: a Mishra's Workshop sozinha vale mais do que o resto da lista
   toda junta. A aba Comprar separa os dois totais em vez de os somar. */
const CARA = 100;
/* O motivo da venda nova ("Premodern: não usada por nenhum deck"), vindo do
   Python (`loadout.RAZAO_PREMODERN`). Escrito à mão aqui, bastava mudar uma
   vírgula do lado de lá para o parágrafo desaparecer sem erro nenhum. */
let PM_RAZAO = '';

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

function toast(txt, ms) {
  const d = document.createElement('div');
  d.className = 'toast'; d.textContent = txt;
  document.body.appendChild(d);
  setTimeout(() => d.remove(), ms || 2600);
}
/* Um ERRO fica mais tempo (2026-09-18). "✓ copiado" lê-se em 2,6 s; *"a caixa
   'x' já não existe no colecao_config.json — recarrega a página"* não — e no
   telemóvel, com o Wi-Fi a hesitar, o erro é a única pista do que aconteceu. */
function erro(txt) { toast(txt, 7000); }

/* O QUE O `title` DIZIA, ao toque (2026-09-18). As miniaturas da grelha levam
   em `title` o que importa — "tens 2/4", "em UW Replenish", "2× Caixa RL (PT)",
   "na colecção inteira: 6" — e no telemóvel NÃO HÁ hover: essa informação não
   existia lá. Um toque na miniatura mostra-a num toast de 5 s. Só leitura, e
   por isso existe também na página publicada. */
function tocarCarta(el) {
  const t = el.getAttribute ? el.getAttribute('title') : el.title;
  if (t) toast(t, 5000);
}

/* ------------------------------------------------ AS CARTAS EM IMAGEM
   André, 2026-09-20, à letra: *"cada deck poderia ter as cartas visualmente ao
   invés de só o nome?"* — e a regra geral dele, de 16/09: *"gosto de ter em
   imagem da carta e não apenas texto, faz algo visualmente apelativo"*.

   UMA componente (`tileHTML`) para todas as secções que até aqui eram texto:
   o passo 1 do painel Montar, as básicas, as destinadas a outra caixa, a
   wantlist e a aba Comprar, a Reserva, a Revalidação, as Encomendas, a aba
   Vender (e a estante), a Feira e o Arrumar. A imagem é a da IMPRESSÃO EXACTA
   que ele tem (`sid` da cópia, do Python); para o que falta, a da impressão
   mais barata — a que o preço ao lado já usa. A informação vai EM CIMA da
   imagem, não escondida no `title`: quantidade, estado (moldura + chip),
   material (✨, PT, edição) e o preço quando é compra. Os botões que a lista
   tinha (`+`/`−`, «Chegou», a checkbox do passo 1, «levo», «vendida») ficam no
   rodapé do tile com os MESMOS `data-*` — o `ligar()` não sabe se está a olhar
   para uma linha ou para um tile. Toque na imagem = os detalhes (`tocarCarta`).

   Sem imagem (o catálogo não a tem, ou o `fetch` falhou — `onerror` tira o
   `<img>`) fica o NOME no quadrado. Nunca um buraco.

   O interruptor «Imagens / Lista» fica no aparelho (`P.imagens`); sem ele
   escrito vale o config (`D.vista`, `colecao_config.json → deckboxes.vista`),
   que é o que o modo edição grava (`api/vista`). Em «Lista» cada secção
   desenha exactamente o que desenhava antes de 20/09. */
let imagens = (P.imagens === undefined || P.imagens === null) ? null : !!P.imagens;
const comImagens = () => (imagens === null ? (D.vista !== 'lista') : imagens);

/* O `<img>` de um tile: `small` do Scryfall (146×204), `lazy` e com o tamanho
   escrito para a grelha não saltar enquanto carrega. `alt` vazio de propósito
   — o nome está por baixo, e o leitor de ecrã lia-o duas vezes. */
function tileImg(sid) {
  return sid ? `<img loading="lazy" decoding="async" src="${art(sid)}" alt="" `
    + `width="146" height="204" onerror="this.remove()">` : '';
}

/* `t`: {nm, sid, q, est, rot, mat[], pz, nota, tit, check{id,feito}, acts,
   attrs, cls, tag, rl, chips}. Com `check` o tile é um `<label>` com a
   checkbox (28 px, canto superior direito) e leva `data-id` — é o que o
   `ligar()` procura, tal como numa linha `.mv`. */
function tileHTML(t) {
  const tag = t.check ? 'label' : (t.tag || 'div');
  const cls = ['tl', t.est || '', t.cls || '', t.check && t.check.feito ? 'feito' : '']
    .filter(Boolean).join(' ');
  const tit = t.tit || t.nm;
  const toque = t.check ? '' : ` onclick="tocarCarta(this)" tabindex="0"`;
  return `<${tag} class="${cls}" data-nm="${esc(t.nm)}"`
    + (t.check ? ` data-id="${esc(t.check.id)}"` : '')
    + (t.attrs ? ' ' + t.attrs : '') + `>`
    + `<span class="tli" title="${esc(tit)}"${toque}>`
    + tileImg(t.sid) + `<b class="tlnm">${esc(t.nm)}</b>`
    + (t.rot ? `<span class="tlr">${t.rot}</span>` : '')
    + (t.q ? `<span class="tlq">${esc(t.q)}</span>` : '')
    + ((t.mat || []).filter(Boolean).length
       ? `<span class="tlm">${t.mat.filter(Boolean).map(m => `<span>${esc(m)}</span>`).join('')}</span>` : '')
    + (t.check ? `<input class="tlck" type="checkbox"${t.check.feito ? ' checked' : ''}>` : '')
    + `</span>`
    + `<span class="tlt">${esc(t.nm)}${t.rl ? ' <span class="rl">RL</span>' : ''}${t.chips || ''}</span>`
    + (t.nota || t.pz ? `<span class="tlx">${t.nota || ''}${t.nota && t.pz ? ' · ' : ''}`
       + (t.pz ? `<b>${esc(t.pz)}</b>` : '') + `</span>` : '')
    + (t.acts ? `<span class="tla">${t.acts}</span>` : '')
    + `</${tag}>`;
}

/* A mesma informação numa LINHA (o modo «Lista» das secções que antes de
   20/09 já eram imagem: a grelha da caixa, as Encomendas, as Sugestões). */
function linhaHTML(t) {
  const tag = t.check ? 'label' : 'div';
  return `<${tag} class="mv ${t.est || ''}${t.check && t.check.feito ? ' feito' : ''}${t.cls ? ' ' + t.cls : ''}"`
    + ` data-nm="${esc(t.nm)}"${t.check ? ` data-id="${esc(t.check.id)}"` : ''}`
    + (t.attrs ? ' ' + t.attrs : '') + `>`
    + (t.check ? `<input type="checkbox"${t.check.feito ? ' checked' : ''}>` : '')
    + (t.q ? `<span class="q">${esc(t.q)}</span>` : '')
    + `<span class="nm">${esc(t.nm)}${t.rl ? ' <span class="rl">RL</span>' : ''}${t.chips || ''}`
    + `<small>${(t.mat || []).filter(Boolean).map(esc).join(' ')}${t.nota ? ' · ' + t.nota : ''}`
    + (t.pz ? ` · <b>${esc(t.pz)}</b>` : '') + `</small></span>`
    + (t.rot ? `<span class="to">${t.rot}</span>` : '')
    + (t.acts ? `<span class="to">${t.acts}</span>` : '')
    + `</${tag}>`;
}

/* Uma grelha de tiles — ou, em «Lista», as linhas. `tag` é o elemento do
   contentor (`ul` para a wantlist, que o `encAjustar` procura pelo `li`). */
function grelhaHTML(itens, opts) {
  const o = opts || {};
  if (!itens.length) return '';
  if (!comImagens()) {
    return `<div class="mvs${o.cls ? ' ' + o.cls : ''}">${itens.map(linhaHTML).join('')}</div>`;
  }
  const tag = o.tag || 'div';
  /* AS GRELHAS GRANDES VÊM AOS POUCOS (2026-09-20): a lista de venda são 300+
     cópias e a Colecção por revalidar 600+ — 300 KB de HTML de uma vez é o que
     faz um telemóvel hesitar. Acima de `max` desenham-se as primeiras e um
     botão «mostrar as outras N» (`data-mais`), que abre ESTA grelha. Só nas
     abas sem procura: na aba da caixa a procura filtra o que está desenhado,
     e um tile por desenhar era uma carta que ela não achava. */
  const chave = `${aba}|${grelhaN++}`;
  const mostra = (o.max && itens.length > o.max && !GRELHAS_ABERTAS.has(chave))
    ? itens.slice(0, o.max) : itens;
  return `<${tag} class="tiles${grande ? ' big' : ''}${o.cls ? ' ' + o.cls : ''}">`
    + mostra.map(tileHTML).join('') + `</${tag}>` + maisHTML(chave, itens.length - mostra.length);
}
const maisHTML = (chave, resto) => !resto ? '' :
  `<div class="seg"><button class="btn" data-mais="${esc(chave)}">⬇ mostrar as outras `
  + `${car(resto)}</button></div>`;
let grelhaN = 0;                        /* reposto a zero em cada `render()` */
const GRELHAS_ABERTAS = new Set();
const MAX_TILES = 60;                   /* por grelha (ou por lista de cores) */

/* Por COR, como o binder (o passo 1, a revalidação): um cabeçalho e uma
   grelha por cor. `f` transforma cada linha num `t`. */
function grelhaPorCor(linhas, f, opts) {
  /* O tecto (`max`) é sobre a LISTA inteira e não por cor: a estante da venda
     são 20 grupos pequenos que juntos passam de 300 tiles. Um botão só, no fim. */
  const max = (opts || {}).max;
  const chave = `${aba}|${grelhaN++}`;
  const mostra = (max && comImagens() && linhas.length > max && !GRELHAS_ABERTAS.has(chave))
    ? linhas.slice(0, max) : linhas;
  let h = '', cor = null, grupo = [];
  const fecha = () => { if (grupo.length) h += grelhaHTML(grupo); grupo = []; };
  for (const l of mostra) {
    if (l.cor !== cor) {
      fecha(); cor = l.cor;
      h += `<div class="corhdr">${esc(l.cor_nome)}</div>`;
    }
    grupo.push(f(l));
  }
  fecha();
  return h + maisHTML(chave, linhas.length - mostra.length);
}

/* O material de uma cópia em chips curtos: edição, ✨ se foil, língua. */
const matDe = (m) => [m.set || '', m.foil ? '✨' : '', m.lang || ''];

/* O interruptor «Imagens / Lista». Fica no topo de cada aba que tem cartas.
   Grava no aparelho e, no modo edição, no config (`api/vista`) — é uma
   preferência dele, e no telemóvel e no PC tem de ser a mesma. */
function vistaSwitchHTML() {
  const im = comImagens();
  return `<div class="seg" role="group" aria-label="Como mostrar as cartas">`
    + `<button class="${im ? 'on' : ''}" data-vista="imagens" aria-pressed="${im}">🖼️ Imagens</button>`
    + `<button class="${im ? '' : 'on'}" data-vista="lista" aria-pressed="${!im}">☰ Lista</button></div>`;
}

async function mudarVista(v) {
  imagens = v === 'imagens';
  P.imagens = imagens; save();
  render();
  if (!D.editable) return;
  try {
    const r = await gravar('api/vista', { vista: v });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    D.vista = v;
  } catch (e) { erro('A vista ficou neste aparelho, mas não gravei no config: ' + e.message); }
}

/* «PARA JÁ TIRA O VENDER» (André, 2026-09-25). O Python manda `D.venda = null`
   quando `colecao_config.json → venda.mostrar` está a `false`, e esta é a
   ÚNICA pergunta que o JavaScript faz sobre isso — a mesma lição do `e_foil` e
   do `vistoId`: um segundo teste escrito à mão noutro sítio era a primeira
   oportunidade de ficar um botão «vendida» órfão a chamar um endpoint que hoje
   responde 409. Com o interruptor ligado, tudo volta exactamente como estava. */
const VENDA_ON = () => !!D.venda;

/* As VISTAS fixas da página, num sítio só. A `vender` sai da lista quando o
   interruptor está desligado: é ela que decide o que um `#vender` de um
   favorito antigo faz (nada — fica na vista de sempre) e o que acontece a uma
   aba `vender` guardada ontem no `localStorage` (volta ao Plano). */
function abasFixas() {
  const f = ['plano', 'todas', 'montados', 'pormontar', 'arrumar', 'partilhadas',
             'comprar', 'encomendas', 'feira', 'revalidacao', 'sugestoes', 'naoenc'];
  if (VENDA_ON()) f.push('vender');
  return f;
}

/* ---------------------------------------------------------------- cabeçalho */
function renderResumo() {
  const r = D.resumo;
  /* Os números do dia, no cabeçalho da página. Eram UMA frase de cinco linhas
     («5 montados · 10 para montar · 15 caixas (13 permanentes · 2 candidatas) ·
     comprar 239 cópias por 7 017,06 € · ir buscar…»), e à frente da estante,
     no telemóvel, isso é um parágrafo para ler, não um número para ver. Desde a
     reestruturação de 2026-09-24 são CHIPS: um número por chip, com o rótulo
     por baixo, e cada um leva à vista que o explica.
     Os dois primeiros são os de 2026-09-08 (*"quero decks montados num botão
     específico, e um botão a dizer decks para montar"*) e vêm do Python
     (`resumo.montados`/`por_montar`) — o cabeçalho e as vistas nunca podem
     discordar. */
  const chip = (v, lbl, cor, aba_) =>
    `<a class="rs" href="#${aba_}" data-aba="${aba_}">`
    + `<b${cor ? ` style="color:${cor}"` : ''}>${v}</b>`
    + `<small>${esc(lbl)}</small></a>`;
  const ir_ = r.nmont + r.nres + r.nfut;
  let h = chip(r.montados, 'montados', 'var(--add)', 'montados')
    + chip(r.por_montar, 'para montar', '', 'pormontar')
    + chip(r.comprar, 'a comprar', 'var(--warn)', 'comprar')
    + chip(eur(r.custo), 'fechar tudo', 'var(--gold)', 'plano')
    + chip(r.arrumar, 'a arrumar', '', 'arrumar');
  /* «PARA JÁ TIRA O VENDER» (André, 2026-09-25): sem o interruptor não há chip
     nenhum com o valor da venda — era o número dela no sítio mais visível da
     página, e a levar a uma aba que já não existe. */
  if (VENDA_ON()) h += chip(eur(r.venda), 'a vender', 'var(--gold)', 'vender');
  if (ir_) h += chip(r.nmont, 'ir buscar a outra caixa', 'var(--ob)', 'todas');
  $('#resumo').innerHTML =
    `<span class="rsl">${h}</span>`
    + `<span class="dim rsd">${D.caixas.length} caixas — ${r.permanentes} `
    + `permanentes, ${r.candidatos} candidatas · dados de ${esc(D.gerado)}`
    + (D.editable ? ' · <b style="color:var(--add)">modo edição</b>' : '')
    + `</span>`
    + precoModoHTML();
  for (const a of $('#resumo').querySelectorAll('.rs')) {
    a.onclick = (e) => { e.preventDefault(); ir(a.dataset.aba); };
  }
  for (const bt of $('#resumo').querySelectorAll('[data-preco-modo]')) {
    bt.onclick = () => mudarPrecoModo(bt.dataset.precoModo);
  }
}

/* O MODO DE PREÇO (André, 2026-09-25): *"o preço da coleção pode ser pelo
   market value do cardtrader, ou o best value, ou a média dos 2"*.
   Fica no CABEÇALHO e não numa aba porque não é a preferência de uma vista —
   muda TODOS os números da página ao mesmo tempo: o valor, o que falta comprar,
   a venda e o chip «cara». Só no modo edição: no site publicado não há
   endpoint que grave, e um botão que não grava é pior do que botão nenhum. */
function precoModoHTML() {
  if (!D.editable || !D.preco) return '';
  const m = D.preco.modo;
  const b = (v, t) => `<button class="${m === v ? 'on' : ''}" `
    + `data-preco-modo="${v}" aria-pressed="${m === v}">${t}</button>`;
  return `<span class="rsp"><small class="dim">preço</small>`
    + `<span class="seg" role="group" aria-label="Modo de preço">`
    + b('market', 'market') + b('best', 'best') + b('media', 'média')
    + `</span><small class="dim">${esc(fontesTxt())}</small></span>`;
}

/* A FONTE é uma CADEIA desde 2026-09-25 (`precos.fontes`): «cardtrader →
   cardmarket» quer dizer *"o preço é o do CardTrader; o que ele não tem à venda
   vem do Cardmarket"*. Dizer só a primeira era esconder que um terço das cópias
   foi avaliado com outra régua. */
function fontesTxt() {
  return ((D.preco && D.preco.fontes) || [D.preco.fonte]).join(' → ');
}

async function mudarPrecoModo(v) {
  if (!D.preco || D.preco.modo === v) return;
  try {
    const r = await gravar('api/preco-modo', { modo: v });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    /* Recarrega em vez de mudar o rótulo: TODOS os números que estão no ecrã
       acabaram de mudar, e deixar a página com os de antes e o botão no modo
       novo era mostrar-lhe dois modos ao mesmo tempo. */
    toast(j.msg || 'preço trocado', 9000);
    await recarregar();
  } catch (e) { erro('Não troquei o modo de preço: ' + e.message); }
}

/* O NOME de cada vista que NÃO é uma caixa. Existe num sítio só porque desde a
   2.ª passagem (2026-09-24) o índice interno já não as lista — quem lá chega
   vem da barra lateral do site — e mesmo assim é preciso dizer, no `<select>`
   do telemóvel, em que vista ele está. */
const VISTAS = {
  plano: 'Plano de montagem', todas: 'Todas as caixas',
  montados: 'Decks montados', pormontar: 'Decks para montar',
  arrumar: 'Arrumar cartas', comprar: 'Comprar', encomendas: 'Encomendas',
  vender: 'Vender', feira: 'Feira', revalidacao: 'Revalidação por foto',
  sugestoes: 'Sugestões de Premodern', partilhadas: 'Cartas partilhadas',
  naoenc: 'Não encontradas',
};

/* O ÍNDICE DAS CAIXAS (2.ª passagem, 2026-09-24).
   Era uma fila de até 27 botões com scroll lateral; a 1.ª passagem fez dela uma
   COLUNA agrupada («Geral», «Fluxo», «Compras e venda», e depois as caixas) — e
   a revisão apanhou o defeito que sobrou: essa coluna repetia, palavra por
   palavra, a barra lateral do site que estava mesmo ao lado dela. **Dois menus
   iguais lado a lado**, e o conteúdo espremido entre os dois.
   Agora o índice interno é só o que a barra lateral NÃO tem: **as caixas**, nos
   dois grupos de 2026-09-08 (*"decks montados num botão específico, e um botão
   a dizer «decks para montar»"*), com a percentagem, mais «Todas as caixas» à
   cabeça e — em «Mais vistas» — as três vistas CONDICIONAIS (Sugestões,
   Partilhadas, Não encontradas), que aparecem e desaparecem conforme os dados e
   por isso não podem viver numa barra lateral escrita em Python, igual em todas
   as páginas. Tirá-las daqui sem as pôr em lado nenhum era perdê-las.
   No telemóvel é o mesmo `<select>`, com os mesmos `<optgroup>` — as duas saem
   desta lista, que duas listas era a segunda oportunidade de discordarem. */
function _filaDeAbas() {
  const geral = [['todas', 'todas', 'Todas as caixas',
                  D.caixas.length + ' caixas']];
  /* As três CONDICIONAIS. Ficam no fim, num grupo próprio: não são caixas, mas
     também não estão na barra lateral. */
  const mais = [];
  /* SUGESTÕES: só existe quando há Premodern configurado. Uma vista vazia é
     ruído — e sem caixas de Premodern não há pergunta nenhuma. */
  if (D.premodern && D.premodern.activo) {
    mais.push(['sugestoes', 'sugestoes', 'Sugestões',
               D.premodern.sugestoes + ' por decidir']);
  }
  /* PARTILHADAS: desde 2026-09-19 nenhuma caixa partilha cartas ("cada deck
     deverá ter as suas próprias cartas dentro, não repetindo com outros
     decks!") e a lista é vazia por regra. Só aparece se um dia voltar a ter
     linhas. */
  const nPart = D.partilhadas ? D.partilhadas.length : (D.n_partilhadas || 0);
  if (nPart) {
    mais.push(['partilhadas', 'partilhadas', 'Partilhadas', nPart + ' cartas']);
  }
  /* NÃO ENCONTRADAS: pela mesma razão, só quando há alguma — enquanto ele não
     carregar no botão, não há pergunta nenhuma para responder aqui. */
  if ((D.nao_encontradas || []).length) {
    mais.push(['naoenc', 'procurar', 'Não encontradas',
               D.nao_encontradas.reduce((s, m) => s + m.q, 0) + ' cópias']);
  }
  /* As caixas ficam AGRUPADAS: montadas primeiro (ponto verde), depois as que
     faltam montar (André, 2026-09-08: *"para poder separar as coisas"*). Antes
     vinham pela ordem da alocação, e a caixa que está na estante aparecia no
     meio das que ainda não existem. O ponto de uma caixa montada é verde por
     ESTAR montada, não pela percentagem — a percentagem continua no subtítulo,
     que é onde ela ainda quer dizer alguma coisa. */
  const daCaixa = c => [c.slot,
    `<i class="pin ${c.montado ? 'done' : c.vazio ? 'low' : pin(c.pct)}"></i>`,
    c.nome,
    (c.vazio ? 'sem deck escolhido' : `${c.pct}% · ${c.tenho}/${c.precisa}`),
    (c.permanente ? '' : ' cand')];
  const montadas = D.caixas.filter(c => c.montado).map(daCaixa);
  const faltam = D.caixas.filter(c => !c.montado).map(daCaixa);
  const grupos = [['', geral]];
  if (montadas.length) grupos.push(['Decks montados', montadas]);
  if (faltam.length) grupos.push(['Decks para montar', faltam]);
  if (mais.length) grupos.push(['Mais vistas', mais]);
  return grupos;
}

function renderTabs() {
  const nav = $('#decktabs'), sel = $('#decksel');
  const grupos = _filaDeAbas();
  /* `role=tab` + `aria-selected` para o leitor de ecrã dizer qual está aberta,
     e `tabindex=-1` nas outras: num índice de 27 itens, o Tab passava por todos
     antes de chegar ao conteúdo. Andar entre eles é com as setas (ver abaixo),
     que é o que o padrão de tablist manda. */
  let h = '', ops = '', achou = false;
  for (const [titulo, itens] of grupos) {
    if (!itens.length) continue;
    if (titulo) h += `<div class="vgh dtsep">${esc(titulo)}</div>`;
    ops += `<optgroup label="${esc(titulo || 'Caixas')}">`;
    for (const [id, ic, lbl, sub, extra] of itens) {
      const on = aba === id;
      if (on) achou = true;
      h += `<button class="dt${on ? ' on' : ''}${extra || ''}" role="tab"`
        + ` aria-selected="${on}" tabindex="${on ? 0 : -1}"`
        + ` data-aba="${esc(id)}">`
        + (ic.charAt(0) === '<' ? ic : `<span class="ic">${ico(ic)}</span>`)
        + `<span class="vtx">${esc(lbl)}`
        + (sub ? `<small>${esc(sub)}</small>` : '') + `</span></button>`;
      ops += `<option value="${esc(id)}"${on ? ' selected' : ''}>`
        + `${esc(lbl)}${sub ? ' — ' + esc(sub) : ''}</option>`;
    }
    ops += '</optgroup>';
  }
  nav.innerHTML = h;
  /* Estando ele numa VISTA (Comprar, Vender, …), nenhuma caixa está marcada — e
     um `<select>` sem nada seleccionado mostrava a primeira opção, a mentir
     sobre onde ele está. Uma opção desactivada à cabeça diz a verdade. */
  if (sel) {
    if (!achou) {
      ops = `<option value="" selected disabled>`
        + `${esc(VISTAS[aba] || 'Vista aberta')}</option>` + ops;
    }
    sel.innerHTML = ops;
    sel.onchange = () => { if (sel.value) ir(sel.value); };
  }
  const botoes = [...nav.querySelectorAll('.dt')];
  botoes.forEach((b, i) => {
    b.onclick = () => ir(b.dataset.aba);
    b.onkeydown = (e) => {
      const d = { ArrowDown: 1, ArrowUp: -1, Home: -i, End: botoes.length - 1 - i };
      if (!(e.key in d)) return;
      e.preventDefault();
      ir(botoes[(i + d[e.key] + botoes.length) % botoes.length].dataset.aba);
      const novo = nav.querySelector('.dt.on');
      if (novo) novo.focus();
    };
  });
  const on = nav.querySelector('.dt.on');
  if (on) on.scrollIntoView({ block: 'nearest' });
}

function ir(id, doHash) {
  if (id !== aba) procura = '';        /* a procura é da caixa, não da página */
  aba = id; P.aba = id; save();
  /* A VISTA VAI PARA O URL (`deckboxes.html#comprar`). É o que torna possível a
     secção «Compras e venda» da barra lateral apontar para dentro desta página,
     e o que ele partilha/marca nos favoritos. `replaceState` e não um salto: o
     `#` a sério fazia o browser procurar um elemento com esse id e rolar. */
  if (doHash !== false) {
    try { history.replaceState(null, '', '#' + id); } catch (e) {}
    if (window.marcaSubVista) window.marcaSubVista();
  }
  renderTabs(); render();
}

/* A aba que o `#` do URL pede, se existir. Uma âncora que não seja vista nenhuma
   (um `#` velho de um favorito) não muda nada — vale a de sempre. */
function abaDoHash() {
  let h = '';
  try { h = (location.hash || '').replace('#', ''); } catch (e) {}
  if (!h) return '';
  if (abasFixas().indexOf(h) >= 0) return h;
  return (D.caixas || []).some(c => c.slot === h) ? h : '';
}

/* O subtítulo da aba Encomendas: «2 a caminho · 1 p/ foto», ou o que falta
   encomendar quando não há nada em curso. */
function encSub() {
  const t = (D.encomendas && D.encomendas.totais) || {};
  const p = [];
  if (t.a_caminho) p.push(`${t.a_caminho} a caminho`);
  if (t.pendente_foto) p.push(`${t.pendente_foto} p/ foto`);
  if (!p.length) return `${t.falta_comprar || 0} por encomendar`;
  return p.join(' · ');
}

/* O subtítulo da aba Feira: o saldo em troca («troca +120 €»), que é a
   resposta curta a "dá para trazer o que quero?". Vem do índice. */
function feiraSub() {
  const F = D.feira || {};
  const s = F.saldo || {};
  const lv = F.levar || {}, tz = F.trazer || {};
  /* Sem a metade «levar» (2026-09-25) o saldo seria `−<tudo o que falta>`, a
     fingir que não há moeda de troca. O subtítulo passa a dizer o que resta:
     quanto custa trazer o que falta. */
  if (lv.desligado) return `trazer ${eur(tz.minimo)}`;
  if (!lv.copias && !tz.copias) return 'nada a levar nem a trazer';
  const v = s.troca || 0;
  return `troca ${v >= 0 ? '+' : '−'}${eur(Math.abs(v))}`;
}

/* «1 a caminho · 1 pendente de foto» de uma linha, ou nada. */
function encTexto(m) {
  const p = [];
  if (m.acam) p.push(`${m.acam} a caminho`);
  if (m.pfoto) p.push(`<b class="pf">${m.pfoto} pendente${pl(m.pfoto)} de foto</b>`);
  return p.length ? `<small class="encs">📦 ${p.join(' · ')}</small>` : '';
}

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
    /* CADA CAIXA COM AS SUAS CARTAS (2026-09-19): a nota "tens 2 no Blue Farm"
       é só informação — esta caixa compra as suas. Vem pronta do Python. */
    c.nota || '',
    Object.entries(c.alt).map(([k, v]) => `${v}× ${k}`).join('; '),
    c.comprar ? `comprar ${c.comprar}` : '',
    c.acam ? `${c.acam} a caminho` : '',
    c.pfoto ? `${c.pfoto} pendente${pl(c.pfoto)} de foto` : '',
    c.bloq ? (c.bloq_txt || `limite de playset: falta ${c.bloq} que não se compra`) : '',
    c.sfoil ? 'nunca saiu em foil — a nonfoil serve' : '',
    /* REVALIDAÇÃO (2026-09-20): quantas cópias desta carta, nesta caixa,
       ainda não têm foto da campanha. */
    c.rev && c.rev.foto ? `📷 ${c.rev.foto} por fotografar` : '',
    c.rev && c.rev.corr ? `⚠ ${c.rev.corr} corrigida${pl(c.rev.corr)} pela foto` : '',
    c.lotes.map(l => `${l.q}× ${l.local}`).join(' · '),
    /* "quantas tenho ao todo" — a informação secundária que vinha da página dos
       decks. Secundária de propósito: o número que manda nesta caixa é o da
       alocação, e é ele que está no canto do cartão. */
    c.col ? `na coleção inteira: ${c.col}` : '',
    c.so_de.length ? 'só da variante ' + c.so_de.join('/') : ''
  ].filter(Boolean).join(' — ');
  /* AS CARTAS EM IMAGEM (2026-09-20): o mesmo tile de todas as secções. O
     estado vai no chip de cima (na caixa / tens, não aqui / comprar N), a
     quantidade em baixo à esquerda, o material da cópia que a alocação deu a
     esta caixa em baixo à direita, e o preço quando é compra. Em «Lista» é
     uma linha por carta. `data-nm` é o que a procura lê. */
  const lote = c.lotes[0] || {};
  const enc = [c.acam ? `${c.acam} a caminho` : '',
               c.pfoto ? `${c.pfoto} p/ foto` : ''].filter(Boolean).join(' · ');
  const rot = c.est === 'have' ? (c.rev && c.rev.foto ? `📷 ${c.rev.foto} por fotografar` : '✓ tens')
    : c.est === 'sub' ? (selo || 'tens, não serve')
    : c.comprar ? `🛒 comprar ${c.comprar}`
    : c.bloq ? '🔒 não se compra'
    /* toda encomendada (2026-09-19): não é compra, é a caminho / p/ foto */
    : c.pfoto ? '📷 pendente de foto' : c.acam ? '🚚 a caminho' : 'falta';
  const t = {
    nm: c.nm, sid: c.sid, est: c.est, tit,
    q: c.need > 1 || c.est !== 'have' ? `${c.got}/${c.need}` : '',
    rot: esc(rot),
    mat: c.est === 'miss' ? [] : matDe({ set: lote.set, foil: lote.foil,
                                         lang: (lote.lang || '').toUpperCase() }),
    pz: c.est === 'miss' && c.cost ? eur(c.cost) : '',
    nota: [c.board === 'side' ? '<span class="sb">SB</span>' : '',
           enc ? `📦 ${esc(enc)}` : '',
           c.nota ? esc(c.nota) : '',
           c.rev && c.rev.corr ? '⚠ corrigida pela foto' : ''].filter(Boolean).join(' · '),
    chips: (c.cf ? ' <span class="cf" style="position:static;display:inline-block">⚔</span>' : ''),
  };
  return comImagens() ? tileHTML(t) : linhaHTML(t);
}

/* ------------------------------------------------ REVALIDAÇÃO POR FOTO
   André, 2026-09-20, à letra: *"quero que quando se clique, ele mostre as
   cartas, como está a fazer, e que depois peça a foto das cartas. Quero
   revalidar todas as fotos agora que vamos colocar tudo em decks para que
   nada falhe ou escape; assim o que eu for vender também vai com foto."*

   Tudo vem do Python (`revalidacao.progresso`): a página desenha o estado de
   cada cópia — 📷 por fotografar / ✓ validada <data> / ⚠ corrigida pela foto —
   e o botão «Fotografar» (só no modo edição) que fixa o ALVO no config e
   escreve o `pendentes/esperadas.md`. Nada aqui muda um número da caixa. */
const REV_ESTADO = {
  foto: ['📷', 'por fotografar'], ok: ['✓', 'validada'], corr: ['⚠', 'corrigida pela foto'],
};

/* A barra «validadas N/M», a mesma no cartão da caixa, na aba dela e na aba
   da revalidação. `g` é um grupo do `progresso` ({q, validadas, ...}). */
function revBarra(g, compacta) {
  if (!g || !g.q) return compacta ? '' : `<p class="ok2">Nada para fotografar aqui.</p>`;
  const pct = Math.round(100 * g.validadas / g.q);
  return `<div class="rvbar${compacta ? ' mini' : ''}" title="validadas ${g.validadas} de ${g.q}">`
    + `<span>📷 validadas <b>${g.validadas}/${g.q}</b>`
    + (g.por_revalidar ? ` · <b class="warn">${g.por_revalidar}</b> por fotografar` : ' · ✓ tudo')
    + (g.corrigidas ? ` · ⚠ ${g.corrigidas} corrigida${pl(g.corrigidas)}` : '')
    + `</span><i class="pg"><b style="width:${pct}%"></b></i></div>`;
}

/* Uma cópia por linha, por cor (como o binder), com o estado. É a lista «Na
   caixa» que ele pediu: o que já mostra, mais o que falta fotografar.
   `origem` ({tipo, slot}) liga o 📷 de CADA cópia por fotografar à câmara
   (2026-09-21, só no modo edição): a foto vai com `-c<copy_id>` no nome. */
function revLinhas(linhas, semLocal, max, origem) {
  const ls = linhas;
  if (!ls.length) return '';
  const cam = l => (D.editable && origem && l.estado === 'foto')
    ? `<label class="btn sm fscam" title="Tirar a foto desta cópia">📷${fotoSiteInputHTML(origem.tipo, origem.slot, l.copy_id, false)}</label>`
    : '';
  /* EM IMAGEM (2026-09-20): um tile por cópia, por cor — a impressão exacta
     que a foto tem de mostrar, com o estado no chip (📷 por fotografar / ✓
     validada / ⚠ corrigida) e o `#copy_id` por baixo. */
  if (comImagens()) {
    return grelhaPorCor(ls, l => {
      const [ico, txt] = REV_ESTADO[l.estado] || REV_ESTADO.foto;
      return {
        nm: l.nm, sid: l.sid, q: `×${l.q}`, rl: !!l.rl,
        est: l.estado === 'foto' ? 'rev' : l.estado === 'corr' ? 'corr' : 'ok',
        rot: `${ico} ${esc(txt)}${l.estado !== 'foto' && l.validado_em ? ' ' + esc(l.validado_em) : ''}`,
        mat: [`${l.set}${l.num ? ' #' + l.num : ''}`, l.foil ? '✨' : '', l.lang],
        nota: `#${l.copy_id}${l.local && !semLocal ? ' · ' + esc(l.local) : ''}`
          + (l.nota ? ` · <span class="parcn">${esc(l.nota)}</span>` : ''),
        attrs: `data-copy="${l.copy_id}"`,
        acts: cam(l),
        tit: `${l.nm} — ${l.q}× ${l.set}${l.num ? ' #' + l.num : ''} ${l.lang}${l.foil ? ' foil' : ''}`
          + ` · #${l.copy_id}${l.local && !semLocal ? ' · ' + l.local : ''} — ${ico} ${txt}`
          + (l.validado_em ? ' ' + l.validado_em : '') + (l.nota ? ` — ${l.nota}` : ''),
      };
    }, { max });
  }
  let h = '<div class="mvs">', cor = null;
  for (const l of ls) {
    if (l.cor !== cor) { cor = l.cor; h += `<div class="corhdr">${esc(l.cor_nome)}</div>`; }
    const [ico, txt] = REV_ESTADO[l.estado] || REV_ESTADO.foto;
    h += `<div class="mv rv ${l.estado}" data-nm="${esc(l.nm)}" data-copy="${l.copy_id}">`
      + `<span class="q">${l.q}×</span><span class="nm">${esc(l.nm)}`
      + (l.rl ? ' <span class="rl">RL</span>' : '')
      + `<small>${esc(l.set)}${l.num ? ' #' + esc(l.num) : ''}${l.foil ? ' ✨' : ''} `
      + `${esc(l.lang)} · #${l.copy_id}${l.local && !semLocal ? ' · ' + esc(l.local) : ''}`
      + (l.nota ? ` · <b class="parcn">${esc(l.nota)}</b>` : '') + `</small></span>`
      + `<span class="to">${ico} ${txt}${l.estado !== 'foto' && l.validado_em
          ? ' ' + esc(l.validado_em) : ''}${cam(l)}</span></div>`;
  }
  return h + '</div>';
}

/* O botão «Fotografar» e a instrução. `tipo` é caixa/venda/rl/coleccao; o
   `slot` só nas caixas. Só no modo edição — no site publicado não há onde
   gravar o alvo, e um botão que não faz nada é pior do que nenhum.
   Desde 2026-09-21 ao lado dele está o «📷 Tirar fotos» — a CÂMARA a partir
   da página (`tirarFotosHTML`), nos dois estados (com e sem alvo fixado). */
function revBotao(tipo, slot, nome, g) {
  if (!D.editable || !g || !g.por_revalidar) return '';
  const R = D.revalidacao || {};
  const alvo = R.alvo && R.alvo.tipo === tipo && (tipo !== 'caixa' || R.alvo.slot === slot);
  if (alvo) {
    return `<div class="rvalvo">📷 <b>A fotografar ${esc(nome)}</b> (desde ${esc(R.alvo.em || '')})`
      + `<p class="nota">${revInstrucao(g)}</p><div class="seg">${tirarFotosHTML(tipo, slot, g)}`
      + `<button class="btn sm" data-rev-parar="1">✕ parar</button></div></div>`;
  }
  /* O «Fotografar …» de 20/09 fica com o nome de sempre (fixa o ALVO e escreve
     o `esperadas.md`); o «Tirar fotos» à frente é a câmara. */
  return `<div class="seg">${tirarFotosHTML(tipo, slot, g)}<button class="btn" data-rev="${esc(tipo)}" `
    + `data-slot="${esc(slot || '')}" data-nome="${esc(nome)}" title="Fixa esta como a caixa `
    + `que estás a fotografar (o esperadas.md passa a dizê-lo)">📷 Fotografar `
    + `${tipo === 'caixa' ? 'esta caixa' : esc(nome)}</button></div>`;
}

function revInstrucao(g) {
  return `Tira fotos às <b>${cop(g.por_revalidar)}</b> por fotografar (várias `
    + `cartas por foto serve) — com <b>📷 Tirar fotos</b> aqui mesmo, ou larga-as em `
    + `<code>pendentes\\</code>. Entram na corrida das 02:30 ou com «⚡ Processar agora». `
    + `Cada foto liga-se à cópia que já existe, não cria outra; se a carta estiver `
    + `noutra edição/acabamento, a cópia é corrigida e fica dito aqui.`;
}

/* ------------------------------------------ FOTOS DAS CARTAS, DO SITE
   André, 2026-09-21, à letra: *"é possível ter o site preparado para eu
   abrir no telefone e tirar as fotos directamente do site?"* — e *"e
   guardares as fotos, claro"*. O botão é um `<input type="file"
   accept="image/*" capture="environment" multiple>` (no telemóvel abre a
   câmara, várias seguidas; no PC o selector), como o da foto da deckbox. A
   foto vai INTEIRA, tal como veio, para a raiz de `pendentes\` pelo
   `POST /api/foto` (multipart, com token), com o nome a dizer a origem —
   `site-<slot>-<data>-<n>[-c<copy_id>].jpg` — e é o `mtg-fotos-novas` das
   02:30 (ou o «⚡ Processar agora») que a lê e liga à cópia. Nada disto
   existe no site publicado: não há onde a mandar. */
function fotoSiteInputHTML(tipo, slot, copy, varias) {
  return `<input type="file" accept="image/*" capture="environment"${varias ? ' multiple' : ''} `
    + `data-foto-site="${esc(tipo)}" data-slot="${esc(slot || '')}"`
    + (copy ? ` data-copy="${copy}"` : '')
    + ` aria-label="Tirar foto${varias ? 's' : ''}" hidden>`;
}

function tirarFotosHTML(tipo, slot, g) {
  if (!D.editable || !g || !g.por_revalidar) return '';
  return `<label class="btn pri fstirar">📷 Tirar fotos${fotoSiteInputHTML(tipo, slot, null, true)}</label>`;
}

const kbs = n => n >= 1e6 ? `${(n / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
const ORIGEM_NOME = { venda: 'Venda', rl: 'Caixa RL', coleccao: 'Coleção' };
function origemFoto(o) {
  if (!o) return 'largada à mão';
  if (o.tipo !== 'caixa') return ORIGEM_NOME[o.tipo] || o.tipo;
  const c = D.caixas.find(x => x.slot === o.slot);
  return c ? c.nome : o.slot;
}

/* As fotos que ele mandou do site e AINDA estão em pendentes\ — «à espera das
   02:30 ou de Processar agora» — mais o botão. `comOrigem` (aba Revalidação)
   diz de que caixa é cada uma; na aba da caixa já se sabe. */
function fotosSiteHTML(fotos, comOrigem) {
  const S = (D.revalidacao || {}).site || {};
  if (!fotos || !fotos.length) return '';
  const min = Math.round((S.espera_s || 120) / 60);
  return `<div class="fsite"><div class="flh">${ico('revalidacao')} Fotos enviadas, à espera`
    + `<span class="dim">${cop(fotos.length)}</span></div>`
    + `<p class="nota">Estão em <code>pendentes\\</code>, à espera da corrida das 02:30 `
    + `ou de <b>⚡ Processar agora</b>. A tarefa (<code>mtg-fotos-novas</code>) só pega numa `
    + `foto com mais de ${min} min; o Claude local lê-a e liga-a à cópia — demora uns minutos. `
    + `Recarrega depois: a cópia passa a ✓ validada.</p><ul class="fsl">`
    + fotos.map(f => `<li><code>${esc(f.nome)}</code> <span class="dim">${kbs(f.bytes)} · `
      + `${esc((f.em || '').slice(11, 16))}${comOrigem ? ' · ' + esc(origemFoto(f.origem)) : ''}`
      + `${f.origem && f.origem.copy_id ? ' · cópia #' + f.origem.copy_id : ''}`
      + `${f.pronta ? '' : ' · <i>a chegar (menos de ' + min + ' min)</i>'}</span></li>`).join('')
    + `</ul>` + processarHTML(S) + `</div>`;
}

/* «⚡ Processar agora»: escreve uma ordem na inbox do runner do ai-pc, que
   corre o `mtg-fotos-novas` — o mesmo das 02:30. Com uma ordem já na inbox
   diz-se isso em vez do botão (e no site publicado não há botão). */
function processarHTML(S) {
  const P = (S || {}).processar || {};
  if (P.pendente) {
    return `<p class="rvalvo">⚡ <b>Já está a processar</b>: a ordem <code>${esc(P.pendente.nome)}</code> `
      + `está na inbox do runner${P.pendente.nao_antes ? ` (corre a partir das ${esc(String(P.pendente.nao_antes).slice(11, 16))})` : ''}. `
      + `Recarrega daqui a uns minutos.</p>`;
  }
  if (!D.editable) return '';
  return `<div class="seg"><button class="btn" data-processar="1">⚡ Processar agora</button>`
    + (P.ultima ? `<span class="dim">última ordem: ${esc(String(P.ultima.em).slice(0, 16))}</span>` : '')
    + `</div>`;
}

/* As fotos que o import NÃO conseguiu resolver (linhas paradas do
   `recat-…-resultado.csv`, foto ainda em pendentes\): o motivo por linha, para
   ele voltar a fotografar em vez de esperar por uma corrida que dá o mesmo. */
function porResolverHTML(lista) {
  if (!lista || !lista.length) return '';
  return `<details class="vblk rev" open><summary><span>${ico('aviso')} Fotos por resolver</span>`
    + `<span class="vtot">${cop(lista.length)}</span></summary>`
    + `<p class="lead">O import passou por estas fotos e não conseguiu ligar ou importar `
    + `todas as linhas — ficaram em <code>pendentes\\</code> com o motivo. Volta a fotografar `
    + `a carta (com a edição legível) ou confirma o nome; a foto antiga não se apaga.</p>`
    + `<ul class="fsl">` + lista.map(f => `<li><code>${esc(f.foto)}</code> `
      + `<span class="dim">${esc(f.resultado)}</span><ul>`
      + f.linhas.map(l => `<li><b>${esc(l.name)}</b>${l.set_code ? ' ' + esc(l.set_code.toUpperCase()) : ''}`
        + ` — <span class="warn">${esc(l.motivo || 'sem motivo')}</span></li>`).join('')
      + `</ul></li>`).join('') + `</ul></details>`;
}

/* O bloco «📷 Na caixa» da aba de uma caixa. */
function revCaixaHTML(c) {
  const g = c.rev;
  if (!g) return '';
  const falta = (g.linhas || []).filter(l => l.estado === 'foto')
    .reduce((s, l) => s + l.q, 0);
  return `<div class="blk rev" id="rev"><div class="flh">${ico('revalidacao')} Na caixa — fotografar`
    + `<span class="dim">${cop(g.q)}</span></div>` + revBarra(g)
    + revBotao('caixa', c.slot, c.nome, g)
    + fotosSiteHTML(g.site, false)
    + (g.linhas && g.linhas.length
       ? `<details${falta ? ' open' : ''}><summary>as cópias, por cor `
         + `<span class="dim">(${cop(falta)} por fotografar)</span></summary>`
         + revLinhas(g.linhas, true, null, { tipo: 'caixa', slot: c.slot }) + `</details>` : '')
    + `</div>`;
}

/* A aba «📷 Revalidação»: o progresso total, o alvo, cada caixa, a venda, a
   Caixa RL e o resto da Colecção (por cor, com o botão), o que entrou hoje,
   as discrepâncias corrigidas e as cópias novas nesta campanha. */
function vistaRevalidacao() {
  const R = D.revalidacao;
  if (!R) return `<h2>${ico('revalidacao')} Revalidação</h2><p class="empty">A campanha não está ligada `
    + `(<code>revalidacao.desde</code> no <code>colecao_config.json</code>).</p>`;
  const T = R.total || {};
  let h = `<h2>${ico('revalidacao')} Revalidação por foto</h2>`
    + `<p class="lead">Desde <b>${esc(R.desde)}</b> nenhuma cópia está validada até uma `
    + `foto NOVA lhe ser ligada. Vai caixa a caixa: carrega em <b>Fotografar</b>, tira `
    + `as fotos, larga-as em <code>pendentes\\</code>. A corrida das 02:30 liga cada foto `
    + `à cópia que já existe — não cria outra —, e uma carta que apareça noutra `
    + `edição/acabamento corrige a cópia (fica dito abaixo). Nada se apaga: o que `
    + `nunca receber foto continua por revalidar, à vista.</p>`
    + `<div class="nums"><div class="num">validadas<b>${T.validadas || 0}/${T.q || 0}</b>`
    + `<span class="dim">${T.pct || 0}%</span></div>`
    + `<div class="num buy">por fotografar<b>${T.por_revalidar || 0}</b></div>`
    + `<div class="num">corrigidas pela foto<b>${T.corrigidas || 0}</b></div>`
    + `<div class="num">novas nesta campanha<b>${T.novas || 0}</b></div></div>`;
  if (R.alvo) {
    h += `<div class="rvalvo">📷 <b>A fotografar: ${esc(R.alvo.nome)}</b> `
      + `(desde ${esc(R.alvo.em || '')}) · ${cop(R.alvo.por_revalidar || 0)} por fotografar`
      + `<p class="nota">${revInstrucao({ por_revalidar: R.alvo.por_revalidar || 0 })}</p>`
      + `<div class="seg">${tirarFotosHTML(R.alvo.tipo, R.alvo.slot, { por_revalidar: R.alvo.por_revalidar || 0 })}`
      + (D.editable ? `<button class="btn sm" data-rev-parar="1">✕ parar</button>` : '')
      + `</div></div>`;
  }
  /* AS FOTOS TIRADAS NO SITE (2026-09-21): as que estão à espera em pendentes\
     (de todas as caixas, com a origem) e as que o import deixou por resolver. */
  const S = R.site || {};
  h += fotosSiteHTML(S.enviadas || [], true) + porResolverHTML(S.por_resolver || []);
  /* Por caixa: a barra e o botão; a lista vive na aba da caixa. */
  h += `<h3>Por caixa</h3><div class="rvcaixas">`;
  for (const g of (R.caixas || [])) {
    if (!g.q) continue;
    /* A FOTO DA DECKBOX (2026-09-21) ao lado do progresso: é a caixa que ele
       tem na mão quando fotografa as cartas dela. */
    const cx = D.caixas.find(c => c.slot === g.slot);
    h += `<div class="rvc"><button class="mini" data-slot="${esc(g.slot)}">`
      + `<span class="btit">${cx ? fotoThumbHTML(cx) : ''}<b>${esc(g.nome)}</b></span>`
      + `${revBarra(g, true)}</button>`
      + revBotao('caixa', g.slot, g.nome, g) + `</div>`;
  }
  h += `</div>`;
  const grupo = (tipo, g, tit, lead) => !g || !g.q ? '' :
    `<details class="vblk rev"${g.por_revalidar && R.alvo && R.alvo.tipo === tipo ? ' open' : ''}>`
    + `<summary><span>${tit}</span><span class="vtot">${g.validadas}/${g.q} validadas</span></summary>`
    + `<p class="lead">${lead}</p>` + revBarra(g) + revBotao(tipo, null, g.nome, g)
    + revLinhas(g.linhas || [], false, MAX_TILES, { tipo, slot: null }) + `</details>`;
  /* O grupo «Venda» desaparece sozinho com o interruptor de 2026-09-25: quem
     o esvazia é o `revalidacao.particao`, que nesse caso põe essas cópias no
     sítio onde ELAS ESTÃO (Caixa RL ou Coleção) em vez de as esconder — e o
     `grupo()` não desenha um grupo a zero. Um segundo teste aqui era a mesma
     decisão escrita em dois sítios. */
  h += grupo('venda', R.venda, ico('vender') + ' Venda',
             'O que vai vender vai com foto: estas são as '
      + 'cópias da lista de venda de hoje (aba <b>Vender</b>, que também as marca).')
    /* Os dois textos dizem de que grupos estas cópias NÃO são, e um deles é a
       venda. Com o interruptor desligado a frase encurta em vez de nomear uma
       vista que ele já não vê. */
    + grupo('rl', R.rl, ico('caixarl') + ' Caixa Reserved List',
            VENDA_ON() ? 'A Caixa RL, fora das caixas de deck e da venda.'
                       : 'A Caixa RL, fora das caixas de deck.')
    + grupo('coleccao', R.resto, ico('colecao') + ' Coleção (o resto)',
            VENDA_ON()
              ? 'Tudo o que não está numa caixa, na venda nem na Caixa RL'
                + ' — no fim, quando as caixas estiverem feitas.'
              : 'Tudo o que não está numa caixa nem na Caixa RL'
                + ' — no fim, quando as caixas estiverem feitas.');
  const lista = (tit, ls, vazio) => `<details class="vblk rev"><summary><span>${tit}</span>`
    + `<span class="vtot">${cop(ls.reduce((s, l) => s + l.q, 0))}</span></summary>`
    + (ls.length ? revLinhas(ls, false, MAX_TILES) : `<p class="ok2">${vazio}</p>`) + `</details>`;
  h += lista(ico('arrumar') + ' Entrou hoje', R.hoje_entradas || [],
             'Nada validado hoje.')
    + lista(ico('aviso') + ' Corrigidas pela foto', R.corrigidas || [],
            'Nenhuma discrepância até agora.')
    + lista(ico('sugestoes') + ' Novas nesta campanha', R.novas || [],
            'Nenhuma carta apareceu nas fotos sem cópia na base.');
  return h + `<p class="nota">O registo de cada correção fica em `
    + `<code>data\\revalidacao.log</code>; a foto antiga de cada cópia revalidada fica `
    + `em <code>pendentes\\fotos processadas\\</code> e no <code>aplicado.csv</code>.</p>`;
}

/* «Fotografar»: fixa o ALVO no config (é uma preferência, vai no Git) e o
   servidor reescreve o `pendentes/esperadas.md`. A resposta traz a instrução. */
async function fotografar(btn) {
  btn.disabled = true;
  try {
    const r = await gravar('api/revalidacao', { act: 'alvo', tipo: btn.dataset.rev,
                                                slot: btn.dataset.slot || null });
    if (!r.ok && r.status !== 403 && r.status !== 409) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'A fotografar.', 6000);
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' +e.message); }
}

async function pararRevalidacao(btn) {
  btn.disabled = true;
  try {
    const r = await gravar('api/revalidacao', { act: 'parar' });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Parado.');
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' +e.message); }
}

/* O ESTADO da caixa numa palavra (v6): candidata < permanente < montada <
   congelada. Era três bandeiras soltas — e nada impedia "montado mas candidato",
   que não quer dizer nada: um deck sleevado na estante não é um candidato. */
const ESTADO = {
  candidata: ['cand', 'candidata — recebe o que sobrar'],
  /* "escolhe as cartas primeiro" lia-se como uma ORDEM ("escolhe tu as cartas
     primeiro") numa caixa que já tem deck e 95 % das cartas. É uma afirmação
     sobre a caixa: é ela que fica com as cópias antes das outras. */
  permanente: ['perm', '★ permanente — fica com as cartas primeiro'],
  montada: ['ok', '✅ montada'],
  congelada: ['ok', '🧊 montada e congelada — só mexe para atualizar'],
};

function badges(c) {
  const [cls, txt] = ESTADO[c.estado] || ESTADO.permanente;
  let h = `<span class="bdg ${cls}">${esc(txt)}</span>`;
  if (c.vazio) h += '<span class="bdg wt">❓ deck por escolher</span>';
  else if (!c.montado) h += '<span class="bdg">🔧 a montar</span>';
  /* «N de M na caixa» (André, 2026-09-08). Uma caixa registada A MEIO não é uma
     caixa montada nem uma caixa por montar, e dizer só "🔧 a montar" apagava o
     trabalho já feito — que é exactamente o que o registo parcial veio guardar. */
  /* E também numa caixa que se DIZ montada e ainda tem cópias por lá meter
     (2026-09-09). «Montada» é o que ele escreveu; «N de M» é o que a
     `copy_allocation` sabe, e as duas podem discordar — o Cloud cEDH diz-se
     montado e tem duas cartas que a caixa deixou de contar. Sem o número, a
     caixa parecia fechada e o painel Montar por baixo dizia o contrário. */
  if (c.montar && ((!c.montado && c.montar.dentro)
                   || (c.montado && c.montar.marcar_q))) {
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
      + `primeiro. A percentagem é a da coleção inteira, antes de alocar`
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
                        : 'Tirar da coleção'}</b>`
    + `<span class="dim">${cop(total)}${gav ? ' · ' + gav : ''}</span></div>`
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
      + `caixa já está lá dentro${M.ja ? ` (${cop(M.ja)})` : ''}.</p>`;
    h += jaNaCaixaHTML(M);
    h += basicasHTML(M);
  } else {
    /* DOIS BLOCOS: main e sideboard (André, 2026-09-08 — "para ficar separado
       dentro da mesma caixa"). Quem os parte é o Python (`blocos_de_board`), e
       dentro de cada um a ordem é a do binder: cor e depois nome. A carta que
       joga nos dois vem nos dois — são duas pilhas, não uma linha repetida. */
    for (const b of (M.blocos || [])) {
      h += `<div class="bhdr">${esc(b.titulo)}`
        + `<span>${b.q}${b.de ? ' de ' + b.de : ''}</span></div>`;
      /* EM IMAGEM (2026-09-20): um tile por cópia a tirar, com a checkbox
         grande no canto — o mesmo `data-id` (`vistoId`) da linha, por isso a
         barra conta na mesma. Em «Lista» é a linha de sempre. */
      if (comImagens()) {
        h += grelhaPorCor(b.movs, m => ({
          nm: m.nm, sid: m.sid, est: 'have', q: `×${m.q}`,
          rot: m.parcial ? `<span class="parcn">${esc(m.nota)}</span>` : 'tirar',
          mat: matDe(m), nota: `de ${esc(m.de)}`,
          cls: m.parcial ? 'parc' : '',
          check: { id: vistoId('mt', c.slot, m), feito: !!P.feitos[vistoId('mt', c.slot, m)] },
          tit: `${m.nm} — ${m.q}× ${m.set} ${m.lang}${m.foil ? ' foil' : ''} — de ${m.de}`
            + (m.nota ? ` — ${m.nota}` : ''),
        }));
        continue;
      }
      let cor = null;
      h += `<div class="mvs">`;
      for (const m of b.movs) {
        if (m.cor !== cor) {
          cor = m.cor;
          h += `<div class="corhdr">${esc(m.cor_nome)}</div>`;
        }
        const id = vistoId('mt', c.slot, m);
        const feito = !!P.feitos[id];
        h += `<label class="mv${feito ? ' feito' : ''}${m.parcial ? ' parc' : ''}"`
          + ` data-id="${esc(id)}" data-nm="${esc(m.nm)}">`
          + `<input type="checkbox"${feito ? ' checked' : ''}>`
          + `<span class="q">${m.q}×</span>`
          + `<span class="nm">${esc(m.nm)}`
          + `<small>${esc(m.set)}${m.foil ? ' ✨' : ''} ${esc(m.lang)}`
          + (m.nota ? ` · <b class="parcn">${esc(m.nota)}</b>` : '')
          + `</small></span>`
          + `<span class="to">de ${esc(m.de)}</span></label>`;
      }
      h += `</div>`;
    }
    h += jaNaCaixaHTML(M);
    h += basicasHTML(M);
    h += deOutraHTML(M);
    /* O botão só se DESENHA no modo edição: no site publicado o endpoint não
       existe, e um botão que não faz nada é pior do que não haver botão.
       E é o MESMO gesto da barra (`data-reg`, não `data-act`): desde 2026-09-09
       um registo grava as cópias MARCADAS, e este botão gravava a alocação
       calculada — dois caminhos, e o segundo era o que metia na caixa cartas
       que ele nunca marcou. */
    h += D.editable
      ? `<div class="seg"><button class="btn pri" data-reg="${esc(c.slot)}">`
        + (c.confirmar ? '✅ Sim, está montada com estas'
                       : '📦 Sleevado e na caixa') + `</button></div>`
      : `<p class="nota">Quando estiver tudo sleevado na caixa, regista-o no `
        + `modo edição (<code>python webapp.py</code> no PC, ou o QR da aba `
        + `<b>Plano</b> no telemóvel) — é o que faz o vault parar de te mandar `
        + `procurar estas cartas.</p>`;
  }
  if (M.devolver.length) {
    h += `<p class="nota">🔄 E <b>${M.devolver.reduce((s, m) => s + m.q, 0)}</b> `
      + `cópias que estão na caixa e a lista de hoje já não pede — vê a aba `
      + `<b>Arrumar</b>, secção «atualizar decks montados».</p>`;
  }
  h += `</div>`;
  /* passo 2 -------------------------------------------------------------- */
  h += `<div class="passo" id="passo2"><div class="ph"><span class="pn">2</span>`
    + `<b>Comprar o que falta</b><span class="dim">${cop(c.comprar)} · `
    + `${eur(c.custo)}${c.req ? ' · ' + esc(c.req) : ''}`
    + (M.basicas_comprar ? ` · + ${M.basicas_comprar} básicas (${eur(M.basicas_custo)})`
                         : '') + `</span></div>`
    + (c.wantlist.length || M.basicas_comprar
       ? wantlistHTML(c.wantlist, c.marca, '', false, M.basicas, M.edicao,
                      c.slot)
       : `<p class="ok2">✓ Nada a comprar para esta caixa.</p>`)
    + (D.editable && c.wantlist.length
       ? `<p class="nota">Já tens alguma destas em casa? Confirma a edição e dá `
         + `check em <b>«já a tenho, está no deck»</b>: a cópia entra na `
         + `coleção e nesta caixa, e a linha passa para o passo 1. Se a edição `
         + `for palpite, a próxima foto dessa carta acerta-a — não cria outra.</p>`
       : '')
    + (c.noutra ? `<p class="nota">📦 Mais <b>${c.noutra}</b> cópia${pl(c.noutra)} está${pl(c.noutra)} noutra `
        + `caixa: essas vão-se buscar, não se compram.</p>` : '')
    + (c.bloqueado ? `<p class="nota">🔒 E <b>${c.bloqueado}</b> em falta que o limite de `
        + `playset (${c.playset} por carta em ${esc(c.grupo || 'todo o grupo')}, no total) `
        + `não deixa comprar — estão noutra caixa do grupo; vê a secção «limite de playset» acima.</p>` : '')
    + ((c.notas_onde || []).length ? `<p class="nota">ℹ️ De <b>${c.notas_onde.length}</b> `
        + `destas tens cópias noutra caixa (vê «tens noutra caixa» acima) — cada deck tem as `
        + `suas próprias cartas, por isso compram-se na mesma.</p>` : '')
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
  /* «SE NÃO MARQUEI, É PORQUE NÃO A TENHO» (André, 2026-09-09). O botão só
     aparece enquanto SOBRAM linhas por marcar: com tudo marcado não há nada que
     ele não tenha encontrado, e um botão que aí não faz nada era ruído no fundo
     do ecrã. As linhas de COMPRAR nunca entram — não têm cópia nenhuma na base,
     e é isso mesmo que ele quer dizer com «não a tenho». */
  const faltam = e.total - e.n;
  return `<div class="bi" data-estado="${grau}"><div class="bt">`
    + `<b>${e.completo ? '✅' : '🧱'} ${c.confirmar ? 'Confirmar' : 'Montar'} `
    + `${esc(c.nome)}</b>`
    + `<small>${e.n} de ${cop(e.total)} marcadas`
    + (e.completo ? ' · tudo marcado' : '')
    + (fora ? ` · +${fora} de outra caixa` : '') + `</small>`
    + `<div class="pg"><i style="width:${pct}%"></i></div></div>`
    + `<div class="ba">`
    + `<button class="btn sm" id="b-tudo">marcar tudo</button>`
    + `<button class="btn sm" id="b-limpar">limpar</button>`
    + (e.completo ? ''
       : `<button class="btn sm warn" id="b-nenc" data-slot="${esc(c.slot)}">`
         + `🔍 Não encontrei ${faltam === e.total ? 'estas' : `estas ${faltam}`}`
         + `</button>`)
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
  const t = $('#b-tudo'), l = $('#b-limpar'), r = $('#b-reg'), n = $('#b-nenc');
  if (n) n.onclick = () => naoEncontrei(c, n);
  /* «Marcar tudo» NÃO dispara o registo automático, mesmo com tudo marcado: é
     um atalho para depois desmarcar duas ou três, não uma afirmação de que a
     caixa está montada. O botão fica verde ao lado, a um toque. */
  if (t) t.onclick = () => {
    for (const i of montarItens(c)) P.feitos[i.id] = 1;
    save(); render();
  };
  /* «limpar» pergunta (2026-09-18): está a um dedo do «marcar tudo» e do «não
     encontrei», e deitava fora 58 marcas sem dizer nada. */
  if (l) l.onclick = () => {
    const n = montarEstado(c).n;
    if (n && !confirm(`Desmarcar as ${cop(n)} marcadas em ${c.nome}?`)) return;
    limparFeitos(c.slot); render();
  };
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
  /* Só se dispara com TUDO marcado, e por isso nunca traz o resumo por baixo:
     com zero por marcar não há a pergunta do que lhes fazer. */
  registar(c, $('#b-reg'), 'auto');
}

/* O RESUMO ANTES DE GRAVAR (2026-09-09). Um registo a meio deixa duas listas na
   estante: as que ele meteu na caixa e as que não encontrou. Gravar as primeiras
   e ficar calado sobre as segundas era o vault a continuar a contar com cartas
   que ele acabou de não achar — e é essa contagem que lhe enche a caixa de
   cartas que não tem. Por isso a pergunta é a dele, com as duas respostas ao
   lado; a terceira, `cancelar`, não escreve nada.

   Devolve `'registar'`, `'nao-encontrei'` ou `null`. Um `confirm()` não chega:
   são três saídas, e a do meio muda a colecção inteira. */
function perguntaRegisto(c, e, faltam) {
  return new Promise(res => {
    const q = faltam.reduce((s, i) => s + i.q, 0);
    const d = document.createElement('div');
    d.className = 'modal';
    d.innerHTML = `<div class="cx"><b>Registar ${cop(e.n)} em ${esc(c.nome)}</b>`
      + `<p>Ficam <b>${cop(q)}</b> por marcar nesta caixa. O que lhes faço?</p>`
      + `<div class="mb">`
      + `<button class="btn pri" id="m-so">Deixá-las por ir buscar</button>`
      + `<button class="btn warn" id="m-ne">Não as tenho — tirar da coleção`
      + `</button>`
      + `<button class="btn" id="m-nao">Cancelar</button></div>`
      + `<p class="nota">«Não as tenho» tira ${cop(q)} da coleção (deixam de `
      + `contar em lado nenhum) e estas cartas voltam a ser compra. Fica na aba `
      + `«Não encontradas», com a foto, e há «afinal encontrei». A base é `
      + `copiada antes.</p></div>`;
    document.body.appendChild(d);
    const sai = v => { d.remove(); res(v); };
    d.querySelector('#m-so').onclick = () => sai('registar');
    d.querySelector('#m-ne').onclick = () => sai('nao-encontrei');
    d.querySelector('#m-nao').onclick = () => sai(null);
    d.onclick = ev => { if (ev.target === d) sai(null); };
  });
}

async function registar(c, btn, origem) {
  const e = montarEstado(c);
  if (!e.n) return;
  /* O que ficou por marcar. Com a regra dele — «se não seleccionei, é porque não
     a tenho» — isto não pode passar em silêncio: ou ele diz que as vai buscar
     depois, ou diz que não as tem. */
  const faltam = e.itens.filter(i => !P.feitos[i.id]);
  let tambem = false;
  if (faltam.length) {
    const escolha = await perguntaRegisto(c, e, faltam);
    if (!escolha) return;
    tambem = escolha === 'nao-encontrei';
  }
  if (btn) btn.disabled = true;
  try {
    const r = await gravar('api/caixa', { act: 'registar', slot: c.slot,
                                          copias: e.copias, origem: origem || 'manual',
                                          de_outra: deOutraMarcadas(c) });
    if (!r.ok && r.status !== 400 && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    const vistos = limparFeitos(c.slot);
    if (tambem) {
      /* O registo primeiro: as marcadas entram na caixa e deixam de estar «por
         encontrar», e o servidor recalcula o relatório antes de tirar nada. */
      await naoEncontrei(c, null, [...new Set(faltam.map(i => i.copy))], true);
      return;
    }
    avisoRegisto(c, e.completo
      ? `✅ ${c.nome} registada como montada`
      : (j.msg || `${c.nome}: ${cop(e.n)} registadas`), vistos);
  } catch (err) {
    if (btn) btn.disabled = false;
    erro('Não deu: ' +err.message);
  }
}

/* O aviso com o ANULAR. Um `toast()` normal desaparece sozinho e não tem onde
   carregar; este fica os segundos que o config disser (`montar.anular_segundos`)
   e leva o botão que desfaz. Só DEPOIS é que a página recarrega — recarregar já
   era deitar fora a única oportunidade de voltar atrás.

   Serve os dois gestos que escrevem na base a partir de um toque: o registo da
   caixa e o «já a tenho» das faltas. O que muda entre eles é o `desfazer`, e
   mais nada — dois avisos com dois temporizadores era a segunda oportunidade de
   um deles ficar sem botão. */
function aviso(texto, desfazer) {
  const seg = Number(D.anular_segundos || 0);
  if (!seg || !desfazer) { toast(texto); recarregar(); return; }
  const d = document.createElement('div');
  d.className = 'toast aviso';
  d.innerHTML = `<span>${esc(texto)}</span>`
    + `<button class="btn sm" id="b-anular">anular</button>`;
  document.body.appendChild(d);
  let fechado = false;
  const b = d.querySelector('#b-anular') || $('#b-anular');
  if (b) b.onclick = () => { fechado = true; d.remove(); desfazer(); };
  setTimeout(() => { if (!fechado) { d.remove(); recarregar(); } }, seg * 1000);
}

function avisoRegisto(c, texto, vistos) {
  aviso(texto, () => anularRegisto(c, vistos));
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
  } catch (e) { erro('Não deu anular: ' +e.message); }
  recarregar();
}

/* ------------------------------------- «NÃO ENCONTREI ESTAS» (2026-09-09)
   André, à letra: *"se eu não seleccionar no deck que meti a carta, com
   checkmark, é porque eu não a tenho e estás a fazer confusão. Por exemplo, no
   Cloud cEDH, dizes que tenho Chromatic Star mas eu não tenho."*

   O inverso do «já a tenho, está no deck»: aquele cria uma cópia, este tira uma
   de circulação. As cópias saem da colecção para todos os efeitos e a carta
   volta a ser COMPRA — nesta caixa e nas outras que a pediam.

   Pergunta-se antes, como no «vendida» e no «desmontar»: é reversível (há a aba
   «Não encontradas» e o «afinal encontrei»), mas muda o que a colecção inteira
   conta, e um toque enganado no telemóvel não pode fazer isso em silêncio. */
async function naoEncontrei(c, btn, ids, jaPerguntado) {
  let copias = ids;
  if (!copias) {
    const e = montarEstado(c);
    const porMarcar = e.itens.filter(i => !P.feitos[i.id]);
    if (!porMarcar.length) return;
    const q = porMarcar.reduce((s, i) => s + i.q, 0);
    if (!jaPerguntado && !confirm(`Marcar ${cop(q)} como NÃO ENCONTRADAS?\n\n`
        + `Saem da coleção (deixam de contar em lado nenhum) e estas cartas `
        + `voltam a ser compra. Ficam na aba «Não encontradas», com a foto, e há `
        + `«afinal encontrei». A base é copiada antes.`)) return;
    copias = [...new Set(porMarcar.map(i => i.copy))];
  }
  if (!copias.length) return;
  if (btn) btn.disabled = true;
  try {
    const r = await gravar('api/caixa', { act: 'nao-encontrei', slot: c.slot,
                                          copias });
    if (!r.ok && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    /* O «anular» do aviso é o MESMO gesto do «afinal encontrei» da lista, e por
       isso o mesmo endpoint: dois caminhos para desfazer eram duas
       oportunidades de discordarem. Os ids são os das cópias que ficaram
       marcadas — um lote partido dá um id novo, e é esse que se devolve. */
    aviso(j.msg || 'Fora da coleção.',
          (j.copias || []).length ? () => encontrei(j.copias) : null);
  } catch (err) {
    if (btn) btn.disabled = false;
    erro('Não deu: ' +err.message);
  }
}

async function encontrei(copias, btn) {
  if (btn) btn.disabled = true;
  try {
    const r = await gravar('api/caixa', { act: 'encontrei', copias });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'De volta à coleção.');
  } catch (e) {
    if (btn) btn.disabled = false;
    erro('Não deu: ' +e.message);
  }
  recarregar();
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
  let h = `<div class="dout"><div class="flh">${ico('aviso')} Destinadas a outra caixa`
    + `<span class="dim">${cop(M.copias_de_outra)} · por marcar</span></div>`
    + `<p class="nota">Estas cópias estão na gaveta, como todas as outras — a `
    + `alocação prometeu-as a outra caixa por prioridade, mas essa caixa ainda `
    + `não está montada. <b>Podes tirá-las já.</b> O que marcares fica `
    + `registado nesta caixa, e a outra passa a dizer «em ${esc(M.caixa || 'esta caixa')}».</p>`;
  for (const b of bs) {
    if (bs.length > 1) {
      h += `<div class="bhdr">${esc(b.titulo)}<span>${b.q}</span></div>`;
    }
    if (comImagens()) {
      h += grelhaHTML(b.movs.map(m => ({
        nm: m.nm, sid: m.sid, est: 'sub', q: `×${m.q}`, rot: `era p/ ${esc(m.destino)}`,
        mat: matDe(m), nota: `de ${esc(m.de)}`,
        attrs: `data-copy="${m.copy_id}" data-q="${m.q}"`,
        check: { id: vistoId('mo', M.slot, m), feito: !!P.feitos[vistoId('mo', M.slot, m)] },
        tit: `${m.nm} — ${m.q}× ${m.set} ${m.lang} — de ${m.de} · destinada a ${m.destino}`,
      })));
      continue;
    }
    h += `<div class="mvs">`;
    for (const m of b.movs) {
      const id = vistoId('mo', M.slot, m);
      const feito = !!P.feitos[id];
      h += `<label class="mv${feito ? ' feito' : ''}" data-id="${esc(id)}" `
        + `data-nm="${esc(m.nm)}" data-copy="${m.copy_id}" data-q="${m.q}">`
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

/* ------------------------------------------- «JÁ A TENHO»: JÁ NA CAIXA ✓
   A linha que ele deu como tendo em casa sai do passo 2 (comprar) e entra aqui:
   está dentro da caixa, e é isso que ele disse. Não tem checkbox — não há nada
   para tirar da gaveta —, mas leva o «📷 edição por confirmar» enquanto a edição
   for palpite. Sem este bloco o palpite virava facto por ninguém voltar a olhar
   para ele, que é o padrão do `event_tier` outra vez. */
function jaNaCaixaHTML(M) {
  const ms = M.por_confirmar || [];
  if (!ms.length) return '';
  let h = `<div class="jnc"><div class="flh">${ico('montado')} Já na caixa (disseste que tinhas)`
    + `<span class="dim">${cop(M.copias_por_confirmar)} · edição por `
    + `confirmar</span></div>`;
  if (comImagens()) {
    h += grelhaHTML(ms.map(m => ({
      nm: m.nm, sid: m.sid, est: 'have', q: `×${m.q}`, rot: '📷 edição por confirmar',
      mat: matDe(m), cls: 'feito',
      tit: `${m.nm} — ${m.q}× ${m.set} ${m.lang} — na caixa, edição por confirmar`,
    })));
  } else {
    h += `<div class="mvs">`;
    for (const m of ms) {
      h += `<div class="mv feito" data-nm="${esc(m.nm)}"><span class="q">${m.q}×</span>`
        + `<span class="nm">${esc(m.nm)}<small>${esc(m.set)}`
        + `${m.foil ? ' ✨' : ''} ${esc(m.lang)}</small></span>`
        + `<span class="to">📷 edição por confirmar</span></div>`;
    }
    h += `</div>`;
  }
  return h + `<p class="nota">A próxima foto destas cartas em `
    + `<code>pendentes\\</code> acerta a edição desta mesma cópia — não cria `
    + `outra.</p></div>`;
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
  let h = `<div class="bas"><div class="flh">${ico('binders')} Terrenos básicos`
    + `<span class="dim">${cop(M.basicas_copias)}</span></div><ul class="bl">`;
  for (const b of M.basicas) {
    const det = [];
    /* EM IMAGEM (2026-09-20): as cópias registadas a tirar são tiles com a
       checkbox — o mesmo `vistoId('bs', …)`; as linhas de texto (já na caixa,
       a granel, a comprar) ficam por baixo, porque não têm cópia para mostrar. */
    if (comImagens() && b.tirar.length) {
      det.push(grelhaHTML(b.tirar.map(m => ({
        nm: b.nm, sid: m.sid, est: 'have', q: `×${m.q}`, rot: 'tirar',
        mat: matDe(m), nota: `de ${esc(m.de)}`,
        check: { id: vistoId('bs', M.slot, m, b.nm),
                 feito: !!P.feitos[vistoId('bs', M.slot, m, b.nm)] },
        tit: `${b.nm} — ${m.q}× ${m.set} ${m.lang}${m.foil ? ' foil' : ''} — de ${m.de}`,
      }))));
    } else {
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
    }
    if (b.ja > 0) det.push(`<span class="bt ok2">✓ ${b.ja} já na caixa</span>`);
    if (b.granel) det.push(`<span class="bt">${b.granel}× das tuas básicas `
      + `(${esc(M.edicao)}) — não estão registadas, não contam para a %</span>`);
    if (b.comprar) det.push(`<span class="bt warn">🛒 ${b.comprar}× a comprar `
      + `${esc(b.req)} (${eur(b.cost)}) — confirma se já tens</span>`);
    h += `<li data-nm="${esc(b.nm)}"><b>${b.need}×</b> <span class="wn">${esc(b.nm)}`
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

/* ------------------------------------------- «JÁ A TENHO, ESTÁ NO DECK»
   André, 2026-09-08, à letra: *"Arranja forma de eu poder dar check nas cartas
   das faltas, para dizer que já as tenho e já coloquei no deck."* Ele está à
   frente da estante com o passo 2 aberto e metade da lista de compras é coisa
   que ele já tem em casa, fora do que o vault catalogou.

   Um check grava DUAS coisas: a cópia (na colecção) e o lugar dela (nesta
   caixa). A EDIÇÃO é a parte que ele não sabe de cabeça — o selector traz as
   impressões que a caixa aceita, com o palpite escolhido, e a cópia fica
   marcada «edição por confirmar» até a foto chegar. Só existe no modo edição:
   no site publicado não há endpoint, e um check que não grava mente. */
function jaTenhoHTML(m, slot) {
  const eds = m.eds || [];
  /* Sem uma única edição no catálogo não há cópia para criar (é o caso do
     «Ademi of the Silkchutes» na base de 2026-09-08: a carta não está lá). Um
     check que só pode falhar é pior do que check nenhum — e a linha continua a
     ser uma compra, que é a verdade. */
  if (!D.editable || !slot || !eds.length) return '';
  /* «QUALQUER EDIÇÃO» por omissão (2026-09-19): ele raramente sabe a edição
     antes de a carta chegar, e desde que só a foto cria cópias a edição já não
     é um palpite gravado — é a foto que a diz. O selector fica, para quando
     sabe (a encomenda guarda-a e a foto tem de a trazer igual). */
  const opts = `<option value="|" selected>qualquer edição</option>`
    + eds.map(e =>
    `<option value="${esc(e.set)}|${esc(e.num)}">`
    + `${esc((e.set || '').toUpperCase())} · ${esc(e.set_nome)}`
    + `${e.num ? ' #' + esc(e.num) : ''}</option>`).join('');
  return `<span class="jat">`
    + `<select class="jed" aria-label="Edição de ${esc(m.nm)}">${opts}</select>`
    + `<label><input type="checkbox" data-falta="1" data-slot="${esc(slot)}"`
    + ` data-nm="${esc(m.nm)}" data-board="${esc(m.board || '')}"`
    + ` data-q="${m.q}"> já a tenho, está no deck</label></span>`;
}

/* «JÁ A TENHO» (André, 2026-09-19: *"cada vez que eu adiciono que tenho a
   carta, fica pendente de foto"*). O check já NÃO cria uma cópia: abre uma
   encomenda directamente em «pendente de foto», e é a foto que a transforma em
   cópia e a mete na caixa. O «anular» é o `−` dessa encomenda. */
async function faltaCheck(cb) {
  if (!cb.checked) return;
  const sel = (cb.closest('.jat') || document).querySelector('select.jed');
  const par = ((sel && sel.value) || '|').split('|');
  cb.disabled = true;
  try {
    const r = await gravar('api/caixa', {
      act: 'falta', slot: cb.dataset.slot, nm: cb.dataset.nm,
      board: cb.dataset.board, q: Number(cb.dataset.q || 1),
      set: par[0] || '', num: par[1] || '' });
    if (!r.ok && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    aviso(j.msg || 'Pendente de foto.',
          j.id ? () => anularFalta(j.id, Number(cb.dataset.q || 1)) : null);
  } catch (e) {
    cb.checked = false; cb.disabled = false;
    erro('Não deu: ' +e.message);
  }
}

async function anularFalta(id, q) {
  try {
    const r = await gravar('api/caixa', { act: 'falta-anular', id, q: q || 1 });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Desfeito.');
  } catch (e) { erro('Não deu anular: ' +e.message); }
  recarregar();
}

/* ------------------------------------------------------------ ENCOMENDAS
   André, 2026-09-19, à letra: *"dizia-te o que ia comprando, e tu só ias
   pedindo as fotos das cartas; cada vez que eu adiciono que tenho a carta, fica
   pendente de foto; quando coloco a foto, adicionas à coleção."*

   Os três gestos, os mesmos na linha de compra de uma caixa e no tile do
   separador: `+`/`−` (a caminho), «Chegou (N)» (passa a pendente de foto) e
   «desfazer» (volta a a caminho). Nenhum deles cria uma cópia — só a foto. O
   `−` numa linha só de pendentes tira do pendente (é o «anular» do «já a
   tenho»). Só no modo edição: no site publicado não há endpoint que grave. */
function encBotoes(slot, nm, m, board) {
  if (!D.editable || !slot) return '';
  const a = `data-slot="${esc(slot)}" data-nm="${esc(nm)}" data-board="${esc(board || '')}"`;
  const total = (m.acam || 0) + (m.pfoto || 0);
  return `<span class="stp">`
    + `<button class="btn sm" data-enc="-1" ${a}${total ? '' : ' disabled'}`
    + ` aria-label="menos uma encomendada de ${esc(nm)}" title="menos uma">−</button>`
    + `<button class="btn sm" data-enc="1" ${a}`
    + ` aria-label="mais uma encomendada de ${esc(nm)}"`
    + ` title="comprei mais uma (fica a caminho)">+</button>`
    + (m.acam ? `<button class="btn sm chg" data-chegou="1" ${a}`
      + ` title="chegou: passa a pendente de foto">Chegou (${m.acam})</button>` : '')
    + `</span>`;
}

/* O `+`/`−` numa linha: grava e relê. A edição do `+` é a do selector da linha
   (se o houver), por omissão «qualquer edição». */
async function encAjustar(btn) {
  const delta = Number(btn.dataset.enc);
  const sel = (btn.closest('li') || btn.closest('.enct') || document)
    .querySelector('select.jed');
  const par = ((sel && sel.value) || '|').split('|');
  btn.disabled = true;
  try {
    const corpo = { delta, slot: btn.dataset.slot || null, nm: btn.dataset.nm,
                    id: btn.dataset.id ? Number(btn.dataset.id) : null,
                    set: delta > 0 ? (par[0] || '') : '',
                    num: delta > 0 ? (par[1] || '') : '' };
    const r = await gravar('api/encomenda', corpo);
    if (!r.ok && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Feito.');
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' + e.message); }
}

async function encChegou(btn, desfazer) {
  btn.disabled = true;
  try {
    const r = await gravar(desfazer ? 'api/encomenda-desfazer' : 'api/encomenda-chegou',
                           { slot: btn.dataset.slot || null, nm: btn.dataset.nm,
                             id: btn.dataset.id ? Number(btn.dataset.id) : null });
    if (!r.ok && r.status !== 403 && r.status !== 409) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Feito.');
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' + e.message); }
}

function wantlistHTML(itens, marca, id, detalhe, basicas, edicao, slot) {
  if (!itens.length && !(basicas || []).length) return '';
  const li = itens.map(m => {
    const cara = detalhe && (m.unit || 0) >= CARA;
    const compra = (m.para || []).filter(p => !p.serve);
    const serve = (m.para || []).filter(p => p.serve);
    /* A regra PARA ESTA CARTA (2026-09-19) — numa que nunca saiu em foil a
       linha diz "nonfoil — nunca saiu em foil" mesmo sem `detalhe`, senão a
       caixa de foil pedia um material que não existe. E a nota "tens 2 no
       Blue Farm": só informação, esta caixa compra as suas. */
    const sub = [detalhe ? (m.req || '') : (m.sfoil ? (m.req || '') : ''),
      m.nota || '',
      detalhe && compra.length ? 'para: ' + compra.map(p => `${p.caixa} ${p.q}×`).join(' · ') : '',
      detalhe && serve.length ? 'serve também: ' + serve.map(p => p.caixa).join(', ') : '']
      .filter(Boolean).join(' — ');
    /* ENCOMENDAS (2026-09-19): «a comprar 2 · 1 a caminho · 1 pendente de
       foto», com os `+`/`−`/«Chegou» quando a linha é de UMA caixa. Uma linha
       toda encomendada fica com `0×` — continua aqui para ele poder voltar
       atrás, e sai do texto copiado. */
    const enc = (m.acam || 0) + (m.pfoto || 0);
    /* EM IMAGEM (2026-09-20): um tile por compra — a impressão mais barata no
       acabamento pedido, o «comprar N» no chip, o material da caixa, o preço,
       e os botões de sempre (`já a tenho`, `+`/`−`/«Chegou») no rodapé. É um
       `<li>` na mesma: o `encAjustar` procura o selector de edição pelo `li`. */
    if (comImagens()) {
      const rot = m.q > 0 ? `🛒 comprar ${m.q}` : m.pfoto ? '📷 pendente de foto' : '🚚 a caminho';
      const est = m.q > 0 ? 'miss' : m.pfoto ? 'pfoto' : 'enc';
      return tileHTML({
        nm: m.nm, sid: m.sid, est, tag: 'li', q: `×${m.q}`, rot: esc(rot),
        cls: enc ? 'enc-l' : '',
        mat: [detalhe ? (m.req || '') : (m.sfoil ? (m.req || '') : (m.mat || ''))]
          .filter(Boolean).join(' ').split(' · '),
        pz: m.q > 0 ? eur(m.cost) + (m.unit && m.q > 1 ? ` (${eur(m.unit)}/un)` : '') : '',
        chips: (m.board === 'side' ? `<span class="sb">SB</span>` : '')
          + (cara ? `<span class="cara">💶 cara</span>` : '')
          + (m.partilhada ? `<span class="part">🔁 ${m.partilhada} caixas</span>` : ''),
        nota: [m.nota ? esc(m.nota) : '',
               detalhe && compra.length ? 'para: ' + esc(compra.map(p => `${p.caixa} ${p.q}×`).join(' · ')) : '',
               detalhe && serve.length ? 'serve também: ' + esc(serve.map(p => p.caixa).join(', ')) : '',
               enc ? encTexto(m) : ''].filter(Boolean).join(' · '),
        acts: (m.q > 0 ? jaTenhoHTML(m, slot) : '') + encBotoes(slot, m.nm, m, m.board),
        tit: [m.nm, `comprar ${m.q}`, m.req || m.mat || '', sub, enc ? encTexto(m).replace(/<[^>]+>/g, '') : '']
          .filter(Boolean).join(' — '),
      });
    }
    return `<li data-nm="${esc(m.nm)}"${enc ? ' class="enc-l"' : ''}>`
      + `<b>${m.q}×</b><span class="wn">${esc(m.nm)}`
      + (m.board === 'side' ? `<span class="sb">SB</span>` : '')
      + (cara ? `<span class="cara">💶 cara</span>` : '')
      + (m.partilhada ? `<span class="part">🔁 partilhada por `
        + `${m.partilhada} caixas</span>` : '')
      + (sub ? `<small>${esc(sub)}</small>` : '')
      + encTexto(m)
      + (m.q > 0 ? jaTenhoHTML(m, slot) : '')
      + encBotoes(slot, m.nm, m, m.board)
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
    if (!m.q) continue;                 /* toda encomendada: não é compra */
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
  const nComp = itens.filter(m => m.q > 0).length;
  const nEnc = itens.length - nComp;
  return `<div class="blk" id="${id || ''}"><div class="flh">${ico('comprar')} Comprar`
    + (marca ? ` <span class="mrk">${esc(marca)}</span>` : '')
    + `<span class="dim">${car(nComp)}${nEnc ? ` · ${nEnc} encomendada${pl(nEnc)}` : ''}</span>`
    + `<button class="cpbtn" onclick="copiar(this,'cm')" aria-label="Copiar as `
    + `${car(nComp)} no formato do Cardmarket">copiar p/ Cardmarket`
    + `</button>`
    + `<button class="cpbtn" onclick="copiar(this,'mat')" aria-label="Copiar as `
    + `${car(nComp)} com o material de cada uma">copiar com material`
    + `</button></div>`
    + `<ul class="fl${comImagens() ? ' tiles' + (grande ? ' big' : '') : ''}">${li}</ul>`
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
  return `<div class="blk cand-blk"><div class="flh">${ico('showcase')} O que estás mais perto de `
    + `concluir<span class="dim">${lista.length} arquétipos</span></div>`
    + `<ul class="fl">${li}</ul>`
    + `<p class="nota">A lista de cada um está na página `
    + `<a href="metagame.html#f-${esc(c.formato)}">Metagame</a>. `
    + (D.editable ? 'Escolher fixa a lista de consenso <b>com a data</b>: não muda '
        + 'debaixo dos pés se o metagame mudar amanhã.'
       : 'Para escolheres, corre <code>python webapp.py</code> no PC (porto 8771).')
    + `</p></div>`;
}

/* ------------------------------------------ A FOTO DA DECKBOX FÍSICA
   André, 2026-09-21, à letra: *"quero poder tirar foto à deckbox onde vai
   ficar cada deck, para ser referência também"*. Uma foto por caixa — a caixa
   de plástico na estante, não as cartas. `c.foto` é `{em, url}` (a versão
   reduzida em `assets/deckboxes/`, do Python: `fotocaixa.info`) ou `null`.

   Três sítios: a MINIATURA no cartão da fila (`fotoThumbHTML`, ao lado do
   nome, dentro do `<button class="mini">` — por isso é só uma `<img>`), o
   CABEÇALHO da aba da caixa (`fotoCaixaHTML`, maior, toque para ampliar) e a
   aba Revalidação ao lado do progresso de cada caixa. Sem foto, um quadrado
   «📦 sem foto da deckbox» — que só no modo edição é um botão: no site
   publicado não há onde a mandar, e um botão morto é pior do que nenhum. O
   botão é um `<input type="file" capture="environment">`: no telemóvel abre a
   câmara, no PC o selector de ficheiros. */
function fotoInputHTML(c) {
  return `<input type="file" accept="image/*" capture="environment" `
    + `data-foto-caixa="${esc(c.slot)}" aria-label="Foto da deckbox de ${esc(c.nome)}" hidden>`;
}

function fotoThumbHTML(c) {
  if (c.foto) {
    return `<img class="dbthumb" loading="lazy" decoding="async" src="${esc(c.foto.url)}" `
      + `alt="deckbox de ${esc(c.nome)}" width="44" height="44" `
      + `title="foto da deckbox${c.foto.em ? ' · ' + esc(c.foto.em) : ''}" onerror="this.remove()">`;
  }
  return `<span class="dbthumb vazia" title="sem foto da deckbox" aria-label="sem foto da deckbox">📦</span>`;
}

function fotoCaixaHTML(c) {
  if (c.foto) {
    return `<div class="dbfoto"><img loading="lazy" decoding="async" src="${esc(c.foto.url)}" `
      + `alt="deckbox de ${esc(c.nome)}" data-ampliar="${esc(c.foto.url)}" data-nome="${esc(c.nome)}" `
      + `title="toca para ampliar">`
      + `<span class="dbleg">📦 a deckbox desta caixa`
      + (c.foto.em ? ` <span class="dim">· foto de ${esc(c.foto.em)}</span>` : '')
      + (D.editable ? `<label class="btn sm">📷 trocar a foto${fotoInputHTML(c)}</label>` : '')
      + `</span></div>`;
  }
  if (!D.editable) {
    return `<div class="dbfoto vazia"><div class="dbq">📦 sem foto da deckbox</div></div>`;
  }
  return `<div class="dbfoto vazia"><label class="dbq btn">📦 sem foto da deckbox`
    + `<small>toca para fotografar a caixa</small>${fotoInputHTML(c)}</label></div>`;
}

/* Ampliar: um véu por cima da página com a foto inteira; toque em qualquer
   sítio (ou Esc) fecha. Só leitura — existe também no site publicado. */
function ampliarFoto(url, nome) {
  const v = document.createElement('div');
  v.className = 'lightbox';
  v.innerHTML = `<img src="${esc(url)}" alt="deckbox de ${esc(nome)}">`
    + `<span>${esc(nome)} · toca para fechar</span>`;
  v.onclick = () => v.remove();
  v.tabIndex = 0;
  v.onkeydown = e => { if (e.key === 'Escape') v.remove(); };
  document.body.appendChild(v);
  if (v.focus) v.focus();
}

/* Enviar: o ficheiro vai tal e qual no corpo do `POST /api/foto-caixa?slot=…`
   (com o token no cabeçalho, como toda a escrita). O servidor valida pelos
   primeiros bytes, guarda o original em `data/deckboxes/`, a anterior em
   `anteriores/`, escreve a reduzida em `assets/deckboxes/` e a data no config
   — e a resposta diz o que fez, com os tamanhos. */
async function enviarFotoCaixa(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  const slot = input.dataset.fotoCaixa;
  const lbl = input.closest ? input.closest('label') : null;
  if (lbl) lbl.classList.add('aenviar');
  toast(`A enviar a foto (${Math.max(1, Math.round(f.size / 1024))} KB)…`, 4000);
  try {
    const r = await gravar(`api/foto-caixa?slot=${encodeURIComponent(slot)}`, null, f);
    if (!r.ok && r.status !== 403 && r.status !== 409 && r.status !== 413) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Foto guardada.', 6000);
    recarregar();
  } catch (e) {
    if (lbl) lbl.classList.remove('aenviar');
    input.value = '';
    erro('Não deu: ' + e.message);
  }
}

/* AS FOTOS DAS CARTAS (2026-09-21): todas as que o `<input multiple>` trouxe
   vão num só `POST /api/foto?tipo=…&slot=…[&copy=…]` (multipart, com o
   token). O servidor valida cada uma pelos primeiros bytes, guarda-as INTEIRAS
   em pendentes\ com o nome a dizer a origem, e a resposta diz quantas e para
   onde; a seguir a página recarrega e a lista «à espera» mostra-as. Um pedido
   com um ficheiro que não é imagem é recusado inteiro (409) — sem metade
   das fotos já na pasta. */
async function enviarFotosSite(input) {
  const fs = input.files ? Array.from(input.files) : [];
  if (!fs.length) return;
  const tipo = input.dataset.fotoSite, slot = input.dataset.slot || '';
  const copy = input.dataset.copy || '';
  const lbl = input.closest ? input.closest('label') : null;
  if (lbl) lbl.classList.add('aenviar');
  const fd = new FormData();
  let bytes = 0;
  for (const f of fs) { fd.append('foto', f, f.name || 'foto.jpg'); bytes += f.size || 0; }
  fd._bytes = bytes;
  toast(`A enviar ${cop(fs.length)}… (${kbs(bytes)})`, 6000);
  try {
    const q = `tipo=${encodeURIComponent(tipo)}&slot=${encodeURIComponent(slot)}`
      + (copy ? `&copy=${encodeURIComponent(copy)}` : '');
    const r = await gravar(`api/foto?${q}`, null, fd);
    if (!r.ok && r.status !== 403 && r.status !== 409 && r.status !== 413) {
      throw new Error('HTTP ' + r.status);
    }
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Fotos guardadas.', 9000);
    recarregar();
  } catch (e) {
    if (lbl) lbl.classList.remove('aenviar');
    input.value = '';
    erro('Não deu: ' + e.message);
  }
}

/* «⚡ Processar agora»: o servidor escreve a ordem para o runner (ou diz que
   já há uma, ou que a última foi há menos de 5 min) — a mensagem é a dele. */
async function processarAgora(btn) {
  btn.disabled = true;
  try {
    const r = await gravar('api/processar-fotos', {});
    if (!r.ok && r.status !== 403 && r.status !== 409) throw new Error('HTTP ' + r.status);
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Pedido.', 9000);
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' + e.message); }
}

function caixaHTML(c, compacta) {
  if (c.vazio) {
    return `<div class="box"><div class="btop"><span class="btit">${fotoThumbHTML(c)}`
      + `<b>${esc(c.nome)}</b></span>`
      + `<span class="pct dim">—</span></div><div class="badges">${badges(c)}</div>`
      + (compacta ? '' : fotoCaixaHTML(c))
      + `<div class="nota">${esc(c.nota)}</div>`
      + `<div class="vaziomsg">Caixa por atribuir — não escolhi por ti. `
      + `Escolhe aqui em baixo, ou vê a lista de cada um na página `
      + `<a href="metagame.html">Metagame</a>.</div>`
      + (compacta ? '' : candidatosHTML(c) + padraoHTML(c) + reservaHTML(c))
      + (D.editable ? acoesHTML(c) : '') + `</div>`;
  }
  let h = `<div class="box"><div class="btop"><span class="btit">${fotoThumbHTML(c)}`
    + `<b>${esc(c.nome)}</b></span>`
    + `<span class="pct" style="color:${cor(c.pct)}">${c.pct}%</span></div>`
    + `<div class="bar"><i style="width:${Math.max(c.pct, 2)}%;background:${cor(c.pct)}"></i></div>`
    + `<div class="badges">${badges(c)}</div>`
    /* A FOTO DA DECKBOX (2026-09-21), maior, só na aba da caixa — no cartão
       compacto da fila fica a miniatura ao lado do nome. */
    + (compacta ? '' : fotoCaixaHTML(c))
    + `<div class="nums">`
    + `<div class="num">na caixa<b>${c.tenho}/${c.precisa}</b></div>`
    + `<div class="num buy">comprar<b>${c.comprar}</b></div>`
    /* DOIS números, não um (André, 2026-09-08): "ir buscar a outra caixa" só
       vale para o que está MESMO dentro de outra caixa. O resto está na gaveta,
       destinado a uma caixa por montar — tira-se do mesmo sítio que tudo o
       resto, e chamar-lhe "ir buscar" mandava-o a uma caixa vazia.
       A ZERO não se mostram, como o "por comprar" já fazia: num ecrã de 390 px
       cinco quadrados por caixa, três deles a dizer 0, empurram a grelha das
       cartas para fora do ecrã — e um zero não responde a pergunta nenhuma. */
    + (c.nmont ? `<div class="num get">ir buscar<b>${c.nmont}</b>`
        + `<span class="dim">a outra caixa (montada)</span></div>` : '')
    + (c.nres ? `<div class="num get2">na gaveta<b>${c.nres}</b>`
        + `<span class="dim">destinadas a outra caixa</span></div>` : '')
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
  /* REVALIDAÇÃO (2026-09-20): «validadas N/M» também no cartão da fila. */
  if (c.rev) h += revBarra(c.rev, true);
  if (compacta) return h + `</div>`;

  const cartas = c.cartas.filter(x => filtro === 'tudo' || x.est !== 'have');
  /* A lista agrupada POR TIPO (criaturas primeiro, terras no fim) e com a
     imagem grande à escolha: as duas coisas vinham da página dos decks, e são o
     que faz esta lista servir para conferir a caixa carta a carta. */
  const grelha = l => (comImagens()
    ? `<div class="tiles${grande ? ' big' : ''}">` + l.map(cardTile).join('') + `</div>`
    : `<div class="mvs">` + l.map(cardTile).join('') + `</div>`);
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
  /* REVALIDAÇÃO POR FOTO (2026-09-20): a lista «Na caixa» com o estado de
     cada cópia e o botão «Fotografar esta caixa». Logo a seguir à grelha —
     é o que ele vê ao clicar, e é daí que pede as fotos. */
  h += revCaixaHTML(c);
  /* A lista em texto, para levar para outro sítio. */
  h += `<div class="blk"><div class="flh">🃏 A lista`
    + `<span class="dim">${cop(c.precisa)}</span>`
    + `<button class="cpbtn" onclick="copiar(this,'lista')" `
    + `aria-label="Copiar a lista completa desta caixa">copiar a lista</button>`
    + `</div><textarea class="cmk" data-cmk="lista" readonly>${esc(c.lista)}`
    + `</textarea></div>`;
  /* LISTA PADRÃO (André, 2026-09-20): a lista fixa, com data e origem, e — no
     modo edição — acrescentar/tirar e «voltar ao consenso». Logo a seguir à
     lista, porque é dela que fala. */
  h += padraoHTML(c);
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
       'Estão na coleção, como todas as outras: a alocação prometeu-as a outra '
       + 'caixa por prioridade, mas essa caixa ainda não está montada. Podes '
       + 'tirá-las já no passo 1 — a outra passa a vir buscá-las aqui.'],
      ['futura', c.nfut, '🛒 outra caixa vai comprá-las',
       'Ainda não existem em casa: são uma compra partilhada de outra caixa.']]) {
    const rows = c.buscar[qual] || [];
    if (!rows.length) continue;
    const li = rows.map(m => `<li>${esc(m.nm)} — ${esc(m.onde.join('; '))}`
      + (m.comprar ? ` <span class="dim">(comprar mais ${m.comprar})</span>` : '')
      + `</li>`).join('');
    h += `<div class="blk onde"><b>${tit} — ${cop(n)}</b>`
      + `<p class="nota">${esc(ajuda)}</p><ul>${li}</ul></div>`;
  }
  /* O TECTO DE PLAYSET (André, 2026-09-08: "no Premodern, afinal só vou ter até
     playset de cada carta"). Uma falta que ele decidiu não tapar não é o mesmo
     que uma falta tapada — se saísse só da conta das compras, a caixa dizia-se
     à espera de uma carta que ninguém vai comprar. */
  if (c.playset_faltas.length) {
    /* Desde 2026-09-19 a frase vem inteira do Python (`loadout.texto_playset`):
       "não se compra (limite de 4 no total; está no UW Replenish)" — é onde as
       duas regras dele se tocam (cada caixa compra as suas, mas o Premodern não
       passa de um playset no total), e a caixa tem de dizer ONDE estão. */
    const li = c.playset_faltas.map(m => `<li>${esc(m.nm)}`
      + (m.board === 'side' ? ' <span class="dim">(sideboard)</span>' : '')
      + ` — <b>em falta</b>: ${esc(m.txt || `${m.q} não se compra (limite de playset)`)}</li>`).join('');
    h += `<div class="blk lim"><b>${ico('sideboard')} limite de playset — ${c.bloqueado} `
      + `cópia${pl(c.bloqueado)} em falta que não se ${c.bloqueado === 1 ? 'compra' : 'compram'}</b>`
      + `<p class="nota">Pediste no máximo <b>${cop(c.playset)}</b> de cada `
      + `carta para ${esc(c.grupo || 'este grupo')}, somando todas as caixas. `
      + `Estas passam disso: ficam em falta nesta caixa, fora do «fechar tudo», `
      + `e as cópias que existem estão na caixa indicada.</p>`
      + `<ul>${li}</ul></div>`;
  }
  /* CADA CAIXA COM AS SUAS CARTAS (André, 2026-09-19): as cartas em falta de
     que ele TEM cópias noutra caixa. Só informação — esta caixa compra as suas;
     nada aqui desconta da lista de compras. */
  if ((c.notas_onde || []).length) {
    const li = c.notas_onde.map(m => `<li>${esc(m.nm)} — ${esc(m.nota)}`
      + `<span class="dim"> (compra-se na mesma: cada caixa tem as suas cartas)</span></li>`).join('');
    h += `<div class="blk onde"><b>${ico('local')} tens noutra caixa — ${cop(c.notas_onde.length)}</b>`
      + `<p class="nota">Cada deck tem as suas próprias cartas, sem repetir com `
      + `outros decks (2026-09-19): estas ficam onde estão, e esta caixa compra as dela.</p>`
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
  h += contradicoesHTML(c);
  /* A RESERVA (André, 2026-09-20): as cartas «que poderão entrar», com onde
     cada cópia está e se serve — e a garantia de que não vão à venda. */
  h += reservaHTML(c);
  h += montarHTML(c);
  h += candidatosHTML(c);
  if (D.editable) h += acoesHTML(c);
  return h + `</div>`;
}

/* LISTA PADRÃO (André, 2026-09-20: *"preciso urgentemente de estabelecer uma
   lista padrão para completar"*). Uma caixa com lista padrão segue uma lista
   FIXA, com data e origem, em vez da que a fonte (o McWinSauce, o consenso)
   recalcula todos os dias. O bloco di-lo sempre; no modo edição deixa
   acrescentar e tirar cartas (`api/padrao`) e «voltar ao consenso». Sem lista
   padrão, no modo edição, oferece o formulário para fixar uma — a partir da
   lista actual ou de texto colado. */
function padraoHTML(c) {
  const p = c.padrao;
  const S = esc(c.slot);
  if (!p) {
    if (!D.editable) return '';
    return `<div class="blk padrao"><b>${ico('plano')} Lista padrão</b>`
      + `<p class="nota">Esta caixa segue a fonte (${esc(c.fonte || '?')}: `
      + `${esc(c.ref || '—')}) e a lista pode mudar de um dia para o outro. Fixar `
      + `uma lista padrão congela-a com a data — só muda quando lhe mexeres.</p>`
      + `<details><summary class="dim">fixar uma lista padrão…</summary>`
      + `<div class="pform"><textarea id="padrao-txt-${S}" placeholder="1 Nome da carta\n`
      + `1 Outra carta\n// Sideboard\n1 …" aria-label="A lista, uma carta por linha">`
      + `${c.vazio ? '' : esc(c.lista)}</textarea>`
      + `<input id="padrao-origem-${S}" placeholder="origem (ex.: 83 listas mono-brancas, mtgtop8)" `
      + `aria-label="De onde veio a lista">`
      + `<button class="btn pri" data-padrao="fixar" data-slot="${S}">📌 Fixar como padrão`
      + `</button></div></details></div>`;
  }
  const cabec = `<b>📌 Lista padrão desde ${esc(p.desde || '?')}</b>`
    + `<p class="nota">Lista fixa — ${esc(p.origem || 'fixada à mão')}. Não muda com o `
    + `metagame nem com o daily: só quando lhe mexeres.</p>`;
  if (!D.editable) return `<div class="blk padrao">${cabec}</div>`;
  const li = (c.cartas || []).filter(x => !x.basica).map(x =>
    `<li>${x.need}× ${esc(x.nm)}${x.board === 'side' ? ' <span class="dim">(side)</span>' : ''}`
    + `<button class="btn sm" data-padrao="tirar" data-slot="${S}" data-nome="${esc(x.nm)}" `
    + `data-board="${esc(x.board || 'main')}" aria-label="Tirar ${esc(x.nm)} da lista padrão">`
    + `✕ tirar</button></li>`).join('');
  return `<div class="blk padrao">${cabec}`
    + `<div class="pform"><input class="nm" id="padrao-nome-${S}" placeholder="carta a acrescentar" `
    + `aria-label="Nome da carta a acrescentar à lista padrão">`
    + `<input class="q" id="padrao-q-${S}" type="number" min="1" value="1" aria-label="Quantas">`
    + `<select id="padrao-board-${S}" aria-label="Main ou sideboard"><option value="main">main`
    + `</option><option value="side">side</option></select>`
    + `<button class="btn pri" data-padrao="add" data-slot="${S}">+ acrescentar</button>`
    + `<button class="btn warn" data-padrao="voltar" data-slot="${S}">↩ voltar ao consenso</button>`
    + `</div><details><summary class="dim">tirar uma carta da lista…</summary><ul>${li}</ul>`
    + `</details></div>`;
}

/* A RESERVA (André, 2026-09-20: *"ver algumas cartas que poderão ser possível
   entrar; não quero ter que vender cartas que depois me poderão fazer
   falta"*). Por carta: quantas tem, onde cada cópia está (gaveta ou caixa) e se
   serve esta caixa tal como está — o porquê vem do Python (`_porque_nao`), a
   mesma régua da alocação. Estas cópias ficam FORA da venda e da exportação
   (saída «guardar», motivo "reserva da caixa X"). */
function reservaHTML(c) {
  const rows = c.reserva || [];
  const S = esc(c.slot);
  if (!rows.length && !D.editable) return '';
  const li = rows.map(r => {
    const lotes = r.lotes.length
      ? r.lotes.map(l => `${l.q}× ${esc(l.set)} ${esc(l.lang)}${l.foil ? ' ✨' : ''} `
          + `<span class="dim">em ${esc(l.onde)}</span>`
          + (l.serve ? ` <span class="rsv-ok">serve</span>`
                     : ` <span class="rsv-no">não serve: ${esc(l.porque)}</span>`)).join('; ')
      : '<span class="dim">não tens nenhuma</span>';
    return `<li><b>${esc(r.nm)}</b>${r.na_lista ? ' <span class="chosen">na lista</span>' : ''}`
      + ` — ${lotes}`
      + (D.editable ? `<button class="btn sm" data-reserva="tirar" data-slot="${S}" `
          + `data-nome="${esc(r.nm)}" aria-label="Tirar ${esc(r.nm)} da reserva">✕</button>` : '')
      + `</li>`;
  }).join('');
  const n = rows.reduce((a, r) => a + r.q, 0);
  /* EM IMAGEM (2026-09-20): um tile por carta reservada — a cópia que ele tem
     (verde se serve, âmbar se tem mas não serve, vermelho se não tem), com
     onde cada cópia está por baixo e o ✕ no rodapé. */
  const tiles = !rows.length ? '' : grelhaHTML(rows.map(r => ({
    nm: r.nm, sid: r.sid, est: r.serve ? 'have' : r.q ? 'sub' : 'miss',
    q: r.q ? `×${r.q}` : '', rot: r.serve ? '🛡️ reserva · serve' : r.q ? '🛡️ reserva · não serve' : '🛡️ reserva · não tens',
    chips: r.na_lista ? ' <span class="chosen">na lista</span>' : '',
    nota: r.lotes.length
      ? r.lotes.map(l => `${l.q}× ${esc(l.set)} ${esc(l.lang)}${l.foil ? ' ✨' : ''} em ${esc(l.onde)}`
          + (l.serve ? '' : ` <span class="rsv-no">(${esc(l.porque)})</span>`)).join(' · ')
      : 'não tens nenhuma',
    acts: D.editable ? `<button class="btn sm" data-reserva="tirar" data-slot="${S}" `
      + `data-nome="${esc(r.nm)}" aria-label="Tirar ${esc(r.nm)} da reserva">✕ tirar</button>` : '',
    tit: `${r.nm} — reserva — ` + (r.lotes.length
      ? r.lotes.map(l => `${l.q}× ${l.set} ${l.lang}${l.foil ? ' foil' : ''} em ${l.onde}`
          + (l.serve ? ' (serve)' : ` (não serve: ${l.porque})`)).join('; ')
      : 'não tens nenhuma'),
  })));
  return `<div class="blk reserva"><b>${ico('sideboard')} Reserva (${rows.length}) — ${cop(n)} guardada${n === 1 ? '' : 's'}</b>`
    /* A reserva é, literalmente, «não te desfaças disto». Com a venda fora de
       vista (2026-09-25) a promessa é a mesma, sem nomear a lista que ele já
       não vê: as cópias ficam guardadas. */
    + `<p class="nota">Cartas que poderão entrar nesta caixa. As cópias ficam `
    + (VENDA_ON()
       ? `fora da lista de venda e da exportação (bloco «guardar»), sirvam ou `
         + `não a regra de material — para não vender o que depois faz falta.`
       : `<b>guardadas</b> (bloco «guardar»), sirvam ou não a regra de `
         + `material — para não te desfazeres do que depois faz falta.`) + `</p>`
    + (rows.length ? (comImagens() ? tiles : `<ul>${li}</ul>`) : '')
    + (D.editable ? `<div class="pform"><input class="nm" id="reserva-nome-${S}" `
        + `placeholder="carta a reservar" aria-label="Nome da carta a pôr na reserva">`
        + `<button class="btn pri" data-reserva="add" data-slot="${S}">+ reservar</button></div>` : '')
    + `</div>`;
}

/* REGISTOS QUE NÃO PODEM ESTAR CERTOS (André, 2026-09-09: *"dizes que tenho
   Chromatic Star mas eu não tenho"*). A caixa tinha estas cópias registadas lá
   dentro e a regra de material DELA recusa-as — as duas do Cloud cEDH estavam
   na base como nonfoil quando ele registou a caixa, e o acabamento foi
   corrigido para foil depois. O vault deixou de contar com elas; o bloco diz
   quais e porquê, senão a percentagem descia sozinha e sem explicação. */
function contradicoesHTML(c) {
  const rows = c.contradicoes || [];
  if (!rows.length) return '';
  const li = rows.map(m => `<li><b>${esc(m.nm)}</b>`
    + `<span class="dim"> ${esc((m.set_code || '').toUpperCase())} `
    + `${esc(m.lang || '')}${m.foil ? ' ✨foil' : ''}</span>`
    + ` × ${m.q} — ${esc(m.porque)}. Tratada como estando em `
    + `<b>${esc(m.onde)}</b>.</li>`).join('');
  return `<div class="blk onde"><b>${ico('aviso')} registada nesta caixa e não pode lá estar `
    + `— ${cop(rows.reduce((a, m) => a + m.q, 0))}</b>`
    + `<p class="nota">Esta caixa tinha estas cópias registadas lá dentro, mas `
    + `elas não cumprem a regra de material dela. A caixa deixou de contar com `
    + `elas e as cartas voltaram a ser compra. Se estiverem mesmo na caixa, `
    + `tira-as; se o registo é que estava errado, o «já arrumei tudo» deita-o `
    + `fora sozinho.</p><ul>${li}</ul></div>`;
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

/* ------------------------------------ montados / para montar (André, 2026-09-08)
   *"Quero decks montados num botão específico, e um botão a dizer «decks para
   montar», para poder separar as coisas."* São duas perguntas diferentes e ele
   está à frente da estante quando faz cada uma: num caso já tem a caixa na mão
   (o que lá está, e desmontá-la); no outro ainda a vai montar (o que tirar, o
   que comprar). A vista *Todas* junta-as por prioridade, que é a resposta a
   outra pergunta.

   O cartão é o MESMO da vista Todas (`caixaHTML(c, true)`) — a caixa não pode
   dizer 61 % num sítio e outra coisa no do lado. O que muda é o que vem por
   baixo dele. E os botões ficam FORA do `<button class="mini">` de propósito:
   um botão dentro de outro não é HTML válido, e o clique de dentro disparava
   também a navegação de fora. */
function cartaoCaixa(c, extra) {
  return `<div class="mcard">`
    + `<button class="mini${c.permanente ? '' : ' cand'}" `
    + `data-slot="${esc(c.slot)}">${caixaHTML(c, true)}</button>`
    + (extra || '') + `</div>`;
}

function vistaMontados() {
  const montadas = D.caixas.filter(c => c.montado);
  let h = `<h2>${ico('montado')} Decks montados <span class="n">${montadas.length}</span></h2>`;
  if (!montadas.length) {
    return h + `<p class="empty">Ainda não há nenhum deck montado. Vê a aba `
      + `<b>🔧 Decks para montar</b> — ou o <b>🗺️ Plano</b>, que diz por onde `
      + `começar.</p>`;
  }
  h += `<p class="lead">Estes estão sleevados e na caixa, prontos para ir jogar. `
    + `Clica num para ver a lista carta a carta. As <b>congeladas</b> só mexem `
    + `para atualizar — o que trocar está na aba <b>Arrumar</b>.</p>`
    + `<div class="grid">`;
  for (const c of montadas) {
    /* A DATA é a da `copy_allocation` (`loadout.datas_de_arrumacao`). Uma caixa
       que ele diz montada e de que o vault não sabe o conteúdo não tem data —
       e dizer "montada em hoje" era assinar por ele uma confirmação que ele
       nunca fez. Diz-se o que se sabe: que falta confirmar o que lá está. */
    const quando = c.arrumada_em
      ? `<span class="quando">📅 montada em <b>${esc(c.arrumada_em)}</b></span>`
      : `<span class="quando aviso">❓ montada, mas ainda não me disseste o que `
        + `lá está — abre a caixa e confirma</span>`;
    h += cartaoCaixa(c, `<div class="macts">${quando}`
      + (D.editable
         ? `<button class="btn warn" data-act="desmontar" `
           + `data-slot="${esc(c.slot)}">🧹 Desmontar</button>`
         : '')
      + `</div>`);
  }
  return h + `</div>`;
}

function vistaPorMontar() {
  /* A ORDEM é a do Plano (`loadout.ordem_de_montagem`): permanentes por ordem
     de alocação, depois as candidatas pela percentagem que já têm. Reordená-la
     aqui dava duas respostas a "por onde começo?". As caixas SEM deck escolhido
     não estão no `montagem` (não há nada para montar até ele escolher): vêm no
     fim, no grupo delas. */
  const ordem = {}, plano = {};
  D.montagem.forEach((m, i) => { ordem[m.slot] = i; plano[m.slot] = m; });
  const falta = D.caixas.filter(c => !c.montado);
  const naOrdem = l => l.slice().sort((a, b) =>
    (ordem[a.slot] === undefined ? 1e6 : ordem[a.slot])
    - (ordem[b.slot] === undefined ? 1e6 : ordem[b.slot]));
  const perm = naOrdem(falta.filter(c => c.permanente && !c.vazio));
  const cand = naOrdem(falta.filter(c => !c.permanente && !c.vazio));
  const vazias = falta.filter(c => c.vazio);
  let h = `<h2>${ico('montar')} Decks para montar <span class="n">${falta.length}</span></h2>`;
  if (!falta.length) {
    return h + `<p class="empty">Está tudo montado. 🎉</p>`;
  }
  h += `<p class="lead">Por esta ordem: primeiro os <b>permanentes</b> (são eles `
    + `que ficaram com as cartas), depois as <b>candidatas</b>, que só recebem o `
    + `que sobra. <b>Montar</b> abre o passo a passo da caixa: o que tirar da `
    + `coleção, e só depois o que comprar.</p>`;
  const bloco = (titulo, lista, lead) => {
    if (!lista.length) return '';
    let b = `<h3>${titulo} <span class="n">${lista.length}</span></h3>`
      + (lead ? `<p class="lead">${lead}</p>` : '') + `<div class="grid">`;
    for (const c of lista) {
      b += cartaoCaixa(c, `<div class="macts">`
        + (c.vazio ? `<span class="quando">Escolhe primeiro o deck — abre a `
                     + `caixa, ou vê a página <b>Metagame</b>.</span>`
                   : `<button class="btn pri" data-montar="${esc(c.slot)}">`
                     + `🧱 Montar</button>`
                     /* «tirar» é o do PLANO (`ordem_de_montagem`), o mesmo
                        número do painel Montar da caixa — o `tenho` do cartão
                        é outra coisa (o que a alocação lhe deu, esteja já lá
                        dentro ou não). */
                     + `<span class="quando">tirar `
                     + `<b>${(plano[c.slot] || {}).tirar || 0}</b> · comprar `
                     + `<b>${c.comprar}</b> · ${eur(c.custo)}</span>`)
        + `</div>`);
    }
    return b + `</div>`;
  };
  return h
    + bloco('★ Permanentes', perm, '')
    + bloco('Candidatas', cand,
        'Recebem o que sobrar dos permanentes. Para uma começar a escolher '
        + 'cartas primeiro, torna-a permanente na aba dela.')
    + bloco('Por escolher', vazias,
        'Caixas sem deck escolhido: não há o que montar até dizeres qual é.');
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
  const lado = (movs, verbo, seta) => comImagens()
    ? grelhaHTML(movs.map(m => ({
        nm: m.nm, sid: m.sid, est: verbo === 'tirar' ? 'sub' : 'have', q: `×${m.q}`,
        rot: `${verbo} ${seta} ${esc(verbo === 'tirar' ? m.para : m.de)}`,
        mat: [(m.set_code || '').toUpperCase(), m.foil ? '✨' : '', (m.lang || '').toUpperCase()],
        chips: bloco(m),
        tit: `${m.nm} — ${m.q}× — ${verbo} ${seta} ${verbo === 'tirar' ? m.para : m.de}`,
      })))
    : movs.map(m =>
    `<div class="mv"><span class="q">${m.q}×</span>`
    + `<span class="nm">${esc(m.nm)}${edicao(m)}${bloco(m)}</span>`
    + `<span class="to">${verbo} ${seta} ${esc(verbo === 'tirar' ? m.para : m.de)}`
    + `</span></div>`).join('');
  return `<h2>${ico('atualizar')} Atualizar decks montados <span class="n">${acts.length}</span></h2>`
    + `<p class="lead">Caixas <b>dedicadas e montadas</b>: a lista mudou, o deck `
    + `não. Ficam como estão até seres tu a abri-las — o <b>já arrumei tudo</b> `
    + `não lhes toca. Quando as atualizares, `
    + (D.editable ? 'carrega em <b>atualizei</b> nessa caixa.'
                  : 'diz-me (ou usa o modo edição, <code>python webapp.py</code>).')
    + `</p>`
    + acts.map(a => `<div class="arr"><div class="arrh"><b>${esc(a.caixa)}</b>`
        + `<span>${cop(a.copias)} · tirar ${a.sai.length} · meter `
        + `${a.entra.length}</span></div>`
        + lado(a.sai, 'tirar', '→') + lado(a.entra, 'meter', '←')
        + (D.editable ? `<div class="acts"><button class="btn pri" `
            + `data-act="actualizar" data-slot="${esc(a.slot)}">🔄 Atualizei o `
            + `${esc(a.caixa)}</button></div>` : '')
        + `</div>`).join('');
}

function vistaArrumar() {
  const a = D.arrumar;
  if (!a.linhas) {
    return actualizarHTML()
      + `<h2>${ico('arrumar')} Arrumar</h2><p class="empty">Nada a arrumar: a estante já está `
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
        + `<span>${cop(bs.reduce((s, b) => s + b.q, 0))} · ${n} linhas`
        + `</span></div>`;
      for (const b of bs) {
        if (bs.length > 1) {
          h += `<div class="bhdr">${esc(b.titulo)}<span>${cop(b.q)}</span></div>`;
        }
        /* EM IMAGEM (2026-09-20): um tile por movimento com a checkbox — o
           mesmo `data-id` da linha, por isso os vistos são os mesmos. */
        h += comImagens()
          ? grelhaHTML(b.movs.map(m => {
              const id = `${m.copy_id}|${m.de}|${m.para}|${m.nm}`;
              return {
                nm: m.nm, sid: m.sid, est: lado === 'origem' ? 'sub' : 'have', q: `×${m.q}`,
                rot: lado === 'origem' ? `→ ${esc(m.para)}` : `← ${esc(m.de)}`,
                mat: [(m.set_code || '').toUpperCase(), m.foil ? '✨' : '', (m.lang || '').toUpperCase()],
                chips: bloco(m), check: { id, feito: !!P.feitos[id] },
                tit: `${m.nm} — ${m.q}× ${(m.set_code || '').toUpperCase()} — de ${m.de} para ${m.para}`,
              };
            }), { max: MAX_TILES })
          : b.movs.map(m => linha(m, lado)).join('');
      }
      h += `</div>`;
    }
    return h;
  };
  return actualizarHTML()
    + `<h2>${ico('arrumar')} Arrumar — ${cop(a.copias)}</h2>`
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
    /* Desde 2026-09-19 é SEMPRE vazia — "cada deck deverá ter as suas próprias
       cartas dentro, não repetindo com outros decks!" — e a aba nem aparece na
       fila (ver `abas()`). Fica o texto para quem chegar aqui por um link. */
    return `<h2>${ico('partilhadas')} Cartas partilhadas</h2><p class="empty">Nenhuma caixa partilha `
      + `cartas com outra: desde 19/09/2026 cada deck tem as suas próprias cartas, `
      + `e a caixa que pede uma carta que está noutra caixa compra a dela. O `
      + `«tens N no X» de cada carta está na aba da caixa.</p>`;
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
  return `<h2>${ico('partilhadas')} Cartas partilhadas entre caixas <span class="n">`
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
    + `${esc(t)}${n == null ? '' : ` — ${car(n)}`}</option>`;
  const selector = `<div class="seg"><select class="selc" id="compra-caixa">`
    + opt('todas', 'todas as caixas', D.compras.length)
    + comCompras.map(c => opt(c.slot, c.nome,
        D.compras.filter(m => compraDe(m, c.slot)).length)).join('')
    + `</select></div>`;
  return `<h2>${ico('comprar')} Comprar — ${esc(nome)}</h2>`
    + `<p class="lead">Só o que <b>não existe</b> na coleção, ou existe mas não serve `
    + `na língua/acabamento que a caixa exige. <b>Cada deck tem as suas próprias `
    + `cartas</b> (19/09/2026): uma carta que está noutra caixa compra-se na mesma `
    + `para esta — a linha diz «tens N no X» só para saberes que a tens. São `
    + `<b>${D.resumo.comprar}</b> cópia${pl(D.resumo.comprar)} a comprar. Debaixo de cada nome está `
    + `<b>para que caixa</b> é a compra e <b>em que material</b> — comprar a versão `
    + `errada é comprar duas vezes; numa carta que <b>nunca saiu em foil</b> a linha `
    + `di-lo e pede nonfoil.</p>`
    + (D.resumo.poupado ? `<p class="lead">🔁 <b>Uma cópia serve as caixas todas.</b> `
        + `Quando duas caixas querem a mesma carta no mesmo material, compra-se `
        + `<b>uma vez</b> e as outras vão lá buscá-la — como já fazes com as que tens. `
        + `São <b>${D.resumo.poupado}</b> cópia${pl(D.resumo.poupado)} que a lista deixou de pedir. Se `
        + `quiseres uma caixa fechada sem trocas, marca-a com `
        + `<code>compras_dedicadas</code> no <code>colecao_config.json</code>.</p>` : '')
    + selector
    + (!itens.length ? `<p class="empty">Não falta comprar nada aqui. Está tudo em casa.</p>`
       : `<div class="nums">`
         + `<div class="num buy">cópias<b>${itens.reduce((s, m) => s + m.q, 0)}</b></div>`
         + `<div class="num eur">💶 caras (≥ ${CARA} €/cópia)<b>${eur(soma(caras))}</b>`
         + `<span class="dim"> ${car(caras.length)}</span></div>`
         + `<div class="num eur">resto<b>${eur(soma(resto))}</b>`
         + `<span class="dim"> ${car(resto.length)}</span></div></div>`
       + (caras.length ? `<p class="lead">As <b>💶 caras</b> decidem-se uma a uma: `
         + `só elas valem ${eur(soma(caras))} dos ${eur(soma(itens))} da lista.</p>` : '')
       + (D.resumo.sem_preco ? `<p class="lead">⚠️ <b>${D.resumo.sem_preco}</b> `
         + `cópias desta lista não têm preço na base (contam como 0 €). `
         + `O total é um <b>mínimo</b>, não a conta fechada.</p>` : '')
       /* Com UMA caixa escolhida no selector a linha é dessa caixa e leva os
          `+`/`−`/«Chegou» (2026-09-19); com todas, a linha junta várias caixas
          e não há a quem encomendar — fica só o «N a caminho». */
       + wantlistHTML(itens, '', 'v-compras', true, null, '',
                      sel === 'todas' ? '' : sel))
    + basicasComprarHTML(sel);
}

/* ------------------------------------------------------------ ENCOMENDAS
   O separador (André, 2026-09-19), à imagem do do riftvault: tiles com a
   imagem da carta. (a) pendentes de foto — o que chegou e espera foto, mais as
   cópias da base sem foto; (b) a caminho, por caixa e origem; (c) falta
   encomendar, por caixa, com o «copiar»; (d) os totais. Os botões só no modo
   edição; a informação é a mesma no site publicado. */
function encTile(t) {
  const a = `data-id="${t.id || ''}" data-slot="${esc(t.slot || '')}" data-nm="${esc(t.nm)}"`;
  let acts = '';
  if (D.editable && !t.na_base) {
    if (t.acaminho) {
      acts = `<span class="stp"><button class="btn sm" data-enc="-1" ${a}`
        + ` aria-label="menos uma de ${esc(t.nm)}">−</button>`
        + `<button class="btn sm" data-enc="1" ${a} aria-label="mais uma de ${esc(t.nm)}">+</button></span>`
        + `<button class="btn sm chg" data-chegou="1" ${a}>Chegou (${t.q})</button>`;
    } else {
      acts = `<span class="stp"><button class="btn sm" data-desfazer="1" ${a}`
        + ` title="voltar a «a caminho»">↩ desfazer</button>`
        + `<button class="btn sm" data-enc="-1" ${a} title="tirar uma (afinal não tenho)">−</button></span>`;
    }
  }
  /* O MESMO tile de todas as secções (2026-09-20): azul tracejado = a caminho
     (não é uma cópia), verde tracejado = chegou e espera foto, pontilhado =
     já na base, sem foto. */
  const est = t.na_base ? 'base' : t.acaminho ? 'enc' : 'pfoto';
  const rot = t.na_base ? (t.por_confirmar ? '📷 edição por confirmar' : 'na base, sem foto')
    : t.acaminho ? '🚚 a caminho' : '📷 pendente de foto';
  const dest = t.caixa ? `→ <b>${esc(t.caixa)}</b>` : '→ coleção';
  const tile = {
    nm: t.nm, sid: t.sid, est, q: `×${t.q}`, rot, cls: t.aviso ? 'aviso' : '',
    mat: [t.set, t.foil ? '✨' : '', t.lang],
    pz: !t.na_base && t.unit != null ? `${eur(t.unit)}/un` : '',
    nota: `${esc(t.impressao)} · ${dest}` + (t.origem ? ` · ${esc(t.origem)}` : '')
      + (t.aviso ? ` · <span class="ea">⚠️ ${esc(t.aviso)}</span>` : ''),
    acts,
    tit: `${t.nm} — ${t.q}× ${t.impressao} — ${rot} — ${t.caixa || 'coleção'}`
      + (t.origem ? ` — ${t.origem}` : '') + (t.aviso ? ` — ⚠️ ${t.aviso}` : ''),
  };
  return tile;
}

/* O contentor dos tiles das encomendas — ou as linhas, em «Lista». */
function encGrelha(lista) {
  return grelhaHTML(lista.map(encTile), { max: MAX_TILES });
}

function vistaEncomendas() {
  const E = D.encomendas || { pendentes: [], a_caminho: [], falta: [], avisos: [], totais: {} };
  const t = E.totais || {};
  const porCaixa = (lista) => {
    const g = new Map();
    for (const x of lista) {
      const k = x.caixa || 'Coleção';
      if (!g.has(k)) g.set(k, []);
      g.get(k).push(x);
    }
    return [...g.entries()];
  };
  let h = `<h2>${ico('encomendas')} Encomendas <span class="n">${esc(encSub())}</span></h2>`
    + `<p class="lead"><b>Só a foto cria cópias.</b> O que compras marca-se aqui com o `
    + `<b>+</b> (fica <b>a caminho</b>); quando chega, <b>Chegou</b> (fica `
    + `<b>pendente de foto</b>); quando lhe tiras a foto e a largas em `
    + `<code>pendentes\\</code>, entra na coleção <b>e na caixa</b> a que a `
    + `encomenda pertencia. Nada disto conta como carta tida — mas já saiu do `
    + `«a comprar» das caixas.</p>`
    + `<div class="nums">`
    + `<div class="num get">a caminho<b>${t.a_caminho || 0}</b>`
    + (t.valor_a_caminho ? `<span class="dim">${eur(t.valor_a_caminho)} ao preço de hoje`
      + (t.pago ? ` · pagaste ${eur(t.pago)}` : '') + `</span>` : '') + `</div>`
    + `<div class="num"><span style="color:var(--add)">pendentes de foto</span><b>${t.pendente_foto || 0}</b>`
    + (t.na_base_sem_foto ? `<span class="dim">+ ${t.na_base_sem_foto} na base sem foto</span>` : '')
    + `</div>`
    + `<div class="num buy">falta encomendar<b>${t.falta_comprar || 0}</b></div>`
    + `<div class="num eur">por<b>${eur(t.custo_falta)}</b></div></div>`;
  /* (a) pendentes de foto ------------------------------------------------ */
  const pend = E.pendentes || [];
  h += `<div class="enc-h"><b>${ico('revalidacao')} Pendentes de foto</b>`
    + `<span>${cop(pend.reduce((s, x) => s + x.q, 0))}</span></div>`;
  if (!pend.length) {
    h += `<p class="ok2">✓ Nada à espera de foto.</p>`;
  } else {
    h += `<div class="enc-nota">Tira a foto a estas cartas e larga-a em `
      + `<code>pendentes\\</code> (ou pela app do GitHub, repo <b>mtg-fotos-novas</b>): `
      + `entram na coleção na corrida das 02:30 (<code>mtg-fotos-novas</code>) — e `
      + `cada uma vai para a caixa da encomenda. As «na base, sem foto» já são `
      + `cópias: a foto liga-se a elas, não cria outra.</div>`;
    for (const [caixa, lista] of porCaixa(pend)) {
      h += `<div class="enc-h"><span>${esc(caixa)}</span>`
        + `<span>${cop(lista.reduce((s, x) => s + x.q, 0))}</span></div>`
        + encGrelha(lista);
    }
  }
  /* (b) a caminho -------------------------------------------------------- */
  const cam = (E.a_caminho || []).map(x => Object.assign({}, x, { acaminho: true }));
  h += `<div class="enc-h"><b>${ico('encomendas')} A caminho</b>`
    + `<span>${cop(cam.reduce((s, x) => s + x.q, 0))}`
    + (t.valor_a_caminho ? ` · ${eur(t.valor_a_caminho)}` : '')
    + (t.sem_preco ? ` · ${t.sem_preco} sem preço` : '') + `</span></div>`;
  if (!cam.length) {
    h += `<p class="ok2">✓ Nada a caminho.</p>`;
  } else {
    for (const [caixa, lista] of porCaixa(cam)) {
      const origens = [...new Set(lista.map(x => x.origem).filter(Boolean))];
      h += `<div class="enc-h"><span>${esc(caixa)}</span><span>`
        + `${cop(lista.reduce((s, x) => s + x.q, 0))} · ${eur(lista.reduce((s, x) => s + (x.total || 0), 0))}`
        + (origens.length ? ` · ${esc(origens.join(', '))}` : '') + `</span></div>`
        + encGrelha(lista);
    }
  }
  /* (c) falta encomendar ------------------------------------------------- */
  const falta = E.falta || [];
  h += `<div class="enc-h"><b>${ico('comprar')} Falta encomendar</b>`
    + `<span>${cop(t.falta_comprar || 0)} · ${eur(t.custo_falta)}</span></div>`
    + `<p class="nota">O «a comprar» de cada caixa <b>depois</b> de descontar o que já `
    + `vem a caminho. É a mesma lista da aba <b>Comprar</b>; aqui está por caixa, `
    + `com o <b>+</b> ao lado de cada carta para marcares o que compraste.</p>`;
  if (!falta.length) {
    h += `<p class="ok2">✓ Não falta encomendar nada. 🎉</p>`;
  } else {
    for (const f of falta) {
      h += `<div class="box"><div class="btop"><b>${esc(f.caixa)}</b>`
        + `<span class="pct" style="font-size:15px">${cop(f.comprar)} · ${eur(f.custo)}</span></div>`
        + wantlistHTML(f.linhas, f.marca, '', false, null, '', f.slot) + `</div>`;
    }
  }
  /* avisos ------------------------------------------------------------- */
  const av = E.avisos || [];
  if (av.length) {
    h += `<div class="blk onde"><b>${ico('aviso')} encomendas que a caixa já não pede — ${cop(av.reduce((s, a) => s + a.q, 0))}</b>`
      + `<p class="nota">A lista vigiada mudou, a carta veio de outro lado, ou a caixa `
      + `saiu do config. Ficam à vista e <b>não descontam noutra caixa</b>: decide `
      + `tu (o <b>−</b> tira-as).</p><ul>`
      + av.map(a => `<li><b>${a.q}× ${esc(a.nm)}</b> → ${esc(a.caixa)} — ${esc(a.porque)}</li>`).join('')
      + `</ul></div>`;
  }
  return h + `<p class="nota">Cada <b>+</b>, <b>−</b>, «Chegou», «desfazer» e cada `
    + `foto→cópia fica registado em <code>data\\encomendas.log</code>, ao lado da `
    + `base. Pelo terminal: <code>py -m mtgvault.cli encomendas</code>.</p>`;
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
  return `<div class="blk"><div class="flh">${ico('binders')} Terrenos básicos`
    + `<span class="dim">${cop(bs.reduce((s, b) => s + b.q, 0))} · `
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
  /* O mesmo tile das caixas (2026-09-20); em «Lista», uma linha por carta. */
  const grelha = grelhaHTML(c.cartas.map(m => ({
    nm: m.nm, sid: m.sid, est: m.est, q: `${m.got}/${m.need}`,
    rot: m.est === 'have' ? '✓ tens' : m.est === 'sub' ? 'tens, noutra caixa' : `falta ${m.need - m.got}`,
    tit: `${m.nm} — tens ${m.got}/${m.need}`,
  })), { max: MAX_TILES });
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
  /* A percentagem grande era a de COMO PRINCIPAL (2026-09-08, quando as caixas
     de Premodern partilhavam). Desde 2026-09-19 nenhuma caixa empresta — "cada
     deck deverá ter as suas próprias cartas dentro" — e as duas percentagens
     são a MESMA: o que está livre. Mostra-se uma só; a "como principal" fica
     no payload por forma (é igual). */
  const p = c.pct_principal;
  return `<div class="box"><div class="btop"><b>${esc(c.nome)}</b>`
    + `<span class="pct" style="color:${cor(p)}">${p}%</span></div>`
    + `<div class="bar"><i style="width:${Math.max(p, 2)}%;`
    + `background:${cor(p)}"></i></div>`
    + `<div class="badges">${chips}</div>`
    + `<div class="nums">`
    + `<div class="num get">com o que está livre<b>${c.got}/${c.need}</b></div>`
    + `<div class="num buy">comprar<b>${c.comprar}</b></div>`
    + `<div class="num eur">fechar por<b>${eur(c.custo)}</b></div></div>`
    + `<div class="nota">${esc(c.subtitulo)}</div>`
    + grelha + `${acts}</div>`;
}

function vistaSugestoes() {
  const P2 = D.premodern;
  const ordem = { sugerida: 0, abaixo: 1, recusada: 2, caixa: 3 };
  const lista = P2.candidatos.slice().sort((a, b) =>
    (ordem[a.estado] - ordem[b.estado]) || (b.pct_principal - a.pct_principal));
  const sug = lista.filter(c => c.estado === 'sugerida');
  let h = `<h2>${ico('sugestoes')} Sugestões de Premodern</h2>`
    + `<p class="lead">O <b>top-10</b> do formato e os <b>melhores combo</b>, `
    + `pelas listas que contam. A percentagem é a do que está <b>livre</b>: as `
    + `cópias PT (≤SCG) que nenhuma caixa levou. Desde 19/09/2026 <b>cada deck tem `
    + `as suas próprias cartas</b> — nenhuma caixa empresta, por isso o que está `
    + `dentro das outras caixas de Premodern não conta para um deck novo. A partir de `
    + `<b>${P2.limiar}%</b> vira sugestão.</p>`;
  h += sug.length
    ? `<p class="lead">Enquanto forem sugestões, as cartas delas <b>não vão para `
      + `a venda</b> — ficam no bloco <b>reservadas</b> da aba Vender. `
      + (D.editable ? `<b>✔ vou montar este</b> abre-lhe uma caixa e mete-a na `
          + `alocação; <b>✕ não quero este</b> liberta as cartas para a venda.`
         : `Para decidires, corre <code>python webapp.py</code> no PC (porto 8771).`)
      + `</p>`
    : `<p class="lead">Nenhum candidato chega aos ${P2.limiar}% com o que está `
      + `livre (as outras caixas de Premodern não emprestam: cada deck tem as `
      + `suas cartas). O que sobra vai para a venda com `
      + `o motivo <i>"não usada por nenhum deck"</i>. Se quiseres ver mais `
      + `opções, baixa o <code>sugerir_a_partir_de_pct</code> no `
      + `<code>colecao_config.json</code>.</p>`;
  return h + `<div class="grid">` + lista.map(sugestaoHTML).join('') + `</div>`;
}

/* O filtro «só validadas» da aba Vender (2026-09-20): o que ele vender vai
   com foto desta campanha. Fica no aparelho, como os outros filtros. */
let soValidadas = !!P.soValidadas;
const REV_ON = () => !!(D.revalidacao && D.revalidacao.activa);
/* A célula 📷/✓ de uma linha de venda, a partir do `foto` que o Python deu
   ({ok, falta}); uma linha junta lotes, e pode estar a meio. */
function fotoCelula(r) {
  if (!REV_ON() || !r.foto) return '';
  const f = r.foto;
  if (!f.falta) return `<td class="rvok" title="validada${pl(f.ok)}">✓</td>`;
  if (!f.ok) return `<td class="rvfoto" title="por fotografar">📷</td>`;
  return `<td class="rvfoto" title="${f.ok} validada${pl(f.ok)}, ${f.falta} por fotografar">`
    + `📷 ${f.ok}/${f.ok + f.falta}</td>`;
}

function vistaVender() {
  const ordena = l => l.slice().sort((x, y) => x.nm.localeCompare(y.nm));
  const rev = REV_ON();
  /* Com o filtro ligado, ficam só as linhas com alguma cópia validada — o
     CSV e a estante da saída trocam para a versão «validadas» (por cópia). */
  const filtra = b => !rev || !soValidadas ? b
    : { ...b, linhas: b.linhas.filter(r => r.foto && r.foto.ok > 0) };
  /* Duas listas para copiar, porque servem duas coisas: a do Cardmarket é só
     `N Nome`, e a de conferir leva a edição, a língua e o acabamento — vender a
     versão errada é anunciar uma carta que não se tem. */
  const so = l => ordena(l).map(r => `${r.q} ${r.nm}`).join('\n');
  const detalhe = l => ordena(l).map(r => `${r.q} ${r.nm} [${r.set}`
    + `${r.foil ? ' foil' : ' nonfoil'} ${(r.lang || '').toUpperCase()}]`).join('\n');
  /* EM IMAGEM (2026-09-20): um tile por linha de venda — a impressão exacta
     da cópia, o total no chip, o estado da foto na moldura (✓ verde / 📷
     âmbar), o material, onde está e o porquê por baixo, e o «vendida» (dois
     toques) no rodapé. Em «Lista» é a tabela de sempre. */
  const tilesVenda = (linhas, semBotao) => grelhaHTML(linhas.map(r => {
    const f = r.foto || null;
    const est = !rev || !f ? 'venda' : !f.falta ? 'ok' : 'rev';
    const foto = !rev || !f ? '' : !f.falta ? '✓ ' : !f.ok ? '📷 ' : `📷 ${f.ok}/${f.ok + f.falta} `;
    return {
      nm: r.nm, sid: r.sid, est, q: `×${r.q}`, rl: r.rl,
      rot: `${foto}${esc(eur(r.total))}`,
      mat: matDe({ set: r.set, foil: r.foil, lang: (r.lang || '').toUpperCase() }),
      pz: r.q > 1 ? `${eur(r.unit)}/un` : '',
      nota: `${esc(r.local)} · ${esc(r.reason)}`
        + (r.rl_nota ? ` <b>${esc(r.rl_nota)}</b>` : '')
        + (r.porque ? ` <i>(ia por: ${esc(r.porque)})</i>` : ''),
      acts: D.editable && !semBotao
        ? `<button class="btn sm" data-vend="${esc(r.chave)}" data-q="${r.q}" data-nm="${esc(r.nm)}" `
          + `aria-label="Marcar ${r.q} ${esc(r.nm)} como vendida (dois toques)">vendida</button>` : '',
      tit: `${r.nm} — ${r.q}× ${r.set} ${(r.lang || '').toUpperCase()}${r.foil ? ' foil' : ''} — ${r.local}`
        + ` — ${eur(r.unit)}/un · ${eur(r.total)} — ${r.reason}${r.rl_nota ? ' ' + r.rl_nota : ''}`
        + (r.porque ? ` (ia por: ${r.porque})` : '')
        + (f && rev ? (f.falta ? ` — 📷 ${f.falta} por fotografar` : ' — ✓ validada') : ''),
    };
  }), { max: MAX_TILES });
  const bloco = (id, titulo, lead, b0, aberto, rotulo, semBotao) => {
   const b = filtra(b0);
   return !b.linhas.length ? '' :
    `<details class="vblk" id="${id}"${aberto ? ' open' : ''}>`
    + `<summary><span>${titulo}</span><span class="vtot">${cop(b.copias)} · `
    + `${eur(b.total)}`
    /* REVALIDAÇÃO (2026-09-20): quantas destas já têm foto da campanha. */
    + (rev ? ` · 📷 ${b0.validadas || 0}/${(b0.validadas || 0) + (b0.por_revalidar || 0)} validadas` : '')
    + `</span></summary><p class="lead">${lead}</p>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this,'cm')" `
    + `aria-label="Copiar a lista: ${esc(rotulo)}">copiar lista Cardmarket`
    + `</button><button class="cpbtn" onclick="copiar(this,'mat')" `
    + `aria-label="Copiar a lista com edição, língua e acabamento: ${esc(rotulo)}">`
    + `copiar com edição/língua/acabamento</button></div>`
    + `<textarea class="cmk" data-cmk="cm" readonly>${esc(so(b.linhas))}</textarea>`
    + `<textarea class="cmk" data-cmk="mat" readonly>${esc(detalhe(b.linhas))}`
    + `</textarea>`
    + (comImagens() ? tilesVenda(b.linhas, semBotao) + `</details>` :
      `<table class="vt"><thead><tr><th></th>${rev ? '<th title="foto desta campanha">📷</th>' : ''}`
    + `<th>carta</th><th>onde está</th>`
    + `<th>edição</th><th>un.</th><th>total</th><th class="rz">porquê</th>`
    + (D.editable && !semBotao ? `<th></th>` : '') + `</tr></thead>`
    + `<tbody>` + b.linhas.map(r => `<tr><td class="q">${r.q}×</td>` + fotoCelula(r)
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
           + `data-q="${r.q}" data-nm="${esc(r.nm)}" `
           + `aria-label="Marcar ${r.q} ${esc(r.nm)} como vendida (dois toques)">`
           + `vendida</button></td>` : '')
      + `</tr>`).join('')
    + `</tbody></table></details>`);
  };
  const V = D.venda, R = D.rl_regra;
  /* O filtro «só validadas» (2026-09-20), à cabeça: é a pergunta *"o que já
     posso listar com foto?"*. Muda a tabela e a saída; a conta é a mesma. */
  const filtroRev = !rev ? '' :
    `<div class="seg" role="group" aria-label="Filtrar pela foto">`
    + `<button class="${soValidadas ? '' : 'on'}" data-sov="0" aria-pressed="${!soValidadas}">`
    + `Tudo</button><button class="${soValidadas ? 'on' : ''}" data-sov="1" `
    + `aria-pressed="${soValidadas}">📷 Só validadas</button>`
    + `<span class="dim">${V.normal.validadas + V.rl.validadas} de `
    + `${V.normal.validadas + V.rl.validadas + V.normal.por_revalidar + V.rl.por_revalidar} `
    + `cópias da venda têm foto desta campanha</span></div>`;
  /* Quanto da lista entra pelo motivo novo. Conta-se das LINHAS e não de um
     total à parte: o que a tabela mostra e o que o parágrafo diz têm de vir do
     mesmo sítio. */
  const pmVenda = [...V.normal.linhas, ...V.rl.linhas]
    .filter(r => r.reason === PM_RAZAO)
    .reduce((a, r) => ({ copias: a.copias + r.q, total: a.total + (r.total || 0) }),
            { copias: 0, total: 0 });
  return `<h2>${ico('vender')} Para vender</h2>`
    + `<p class="lead"><b>Sugestão a confirmar.</b> Nada sai da coleção sem tu dizeres. `
    + `É o que sobra depois de encher todas as caixas e de guardar o backup: `
    + `<b>4 por carta</b> na coleção (playset, a somar a Coleção e a Caixa RL — não 4 `
    + `por balde) e <b>1 por deck</b> nas caixas de Commander. <b>Básicas nunca.</b></p>`
    /* PREMODERN NÃO USADO (André, 2026-09-08). É um motivo à parte dentro das
       mesmas listas: uma PT da era está trancada ao Premodern, e se nenhuma
       caixa a aloca não serve mais nada. Dizê-lo aqui em cima porque muda o
       tamanho da lista — e porque a saída dela é uma decisão dele, não um
       excedente. */
    + (pmVenda.copias ? `<p class="lead">🕰 <b>${cop(pmVenda.copias)} `
        + `(${eur(pmVenda.total)}) entram por não estarem em nenhum deck de `
        + `Premodern.</b> São PT de edições até ao Scourge: essas ficam trancadas `
        + `ao Premodern (<i>"não entram para outros formatos"</i>), por isso uma `
        + `cópia que nenhuma caixa usa não serve mais nada. Se houver um deck que `
        + `queiras montar com elas, marca-o na aba <b>Sugestões</b> primeiro — as `
        + `cartas dele saem desta lista.</p>` : '')
    /* O total que a regra dos 5% segurou. Em cima, e não só dentro dos blocos,
       porque muda o tamanho da lista da RL — que é onde está quase todo o
       dinheiro — e ele tem de o ver antes de decidir seja o que for. */
    + (R.copias ? `<p class="lead">🔒 <b>${cop(R.copias)} Reserved List `
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
    + filtroRev
    + saidaHTML(V.saida, rev && soValidadas)
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
    + bloco('v-retidos', '📦 Retidos — extras dos decks vigiados', 'Baldes com '
        + '<code>reter_extras</code> (Blue Farm, Cloud, Cloud cEDH, Pauper Affinity): '
        + 'as cartas que a lista do deck já não usa ficam <b>guardadas sem prazo</b> '
        + '(decisão de 2026-09-15 — deixou de haver um prazo de 6 meses). Só saem '
        + 'daqui quando tu o disseres, carta a carta, com <b>vendida</b>.', V.retidos,
        false, 'retidos')
    + (V.normal.linhas.length || V.rl.linhas.length ? '' :
       `<p class="empty">Não há nada a mais para vender.</p>`);
}

/* A SAÍDA DA VENDA (2026-09-18): o que tira a lista do ecrã para o sítio onde
   as cartas se vendem. Três blocos, todos calculados no Python
   (`mtgvault.venda`) — a página só os desenha:
     1. o CSV de stock, para copiar, descarregar ou (modo edição) gravar em
        `data/`. O formato é o do ficheiro de exemplo dele se existir; senão o
        predefinido, DITO como não confirmado — não se dá por certo um formato
        que ninguém viu;
     2. a lista para ir buscar as cartas à ESTANTE, por onde a cópia está e por
        cor dentro de cada sítio, com totais por grupo. Legível no telemóvel
        (uma linha por cópia, sem tabela) e imprimível (`@media print`);
     3. o que NÃO entra, com o motivo por linha — para ele ver que a decisão foi
        tomada, não esquecida. */
function saidaHTML(S, so) {
  if (!S) return '';
  const F = S.formato || {};
  /* «Só validadas» (2026-09-20): o CSV e a estante trocam para a versão por
     cópia com foto desta campanha — calculada no Python, como a outra. */
  const csv = so ? (S.csv_validadas || '') : S.csv;
  const nomeCsv = so ? (S.nome_csv_validadas || S.nome_csv) : S.nome_csv;
  const txt = so ? (S.texto_estante_validadas || '') : S.texto_estante;
  const est = (so ? S.estante_validadas : S.estante) || { grupos: [] };
  const copias = so ? (S.copias_validadas || 0) : S.copias;
  const rev = REV_ON();
  /* EM IMAGEM (2026-09-20): a estante por sítio e por cor, em tiles — é a
     lista para ir buscar as cartas, e a imagem é a da cópia exacta. */
  const grupoHTML = g => `<div class="estg"><h4>${ico('local')} ${esc(g.local)}`
    + `<span>${cop(g.copias)} · ${eur(g.total)}</span></h4>`
    + (comImagens() ? grelhaPorCor(g.linhas, l => ({
        nm: l.nm, sid: l.sid, q: `×${l.q}`, rl: !!l.rl,
        est: !rev ? 'venda' : l.validada ? 'ok' : 'rev',
        rot: rev ? (l.validada ? `✓ ${esc(l.validada)}` : '📷 por fotografar') : esc(l.cond),
        mat: [l.set, l.foil ? '✨' : '', (l.lang || '').toUpperCase(), l.cond],
        pz: eur(l.unit),
        tit: `${l.nm} — ${l.q}× ${l.set} ${(l.lang || '').toUpperCase()} ${l.foil ? 'foil' : 'nonfoil'} ${l.cond}`
          + ` — ${eur(l.unit)}` + (rev ? (l.validada ? ` — ✓ ${l.validada}` : ' — 📷 por fotografar') : ''),
      }), { max: MAX_TILES }) :
    g.linhas.map(l => `<div class="el${rev && !l.validada ? ' rvfoto' : ''}">`
      + `<span class="c ${esc(l.cor)}" `
      + `title="${esc(l.cor_nome)}">${esc(l.cor)}</span>`
      + `<span class="q">${l.q}×</span><span class="nm">${esc(l.nm)}`
      + (l.rl ? ' <span class="rl">RL</span>' : '')
      + `<small>${esc(l.set)} ${esc((l.lang || '').toUpperCase())} `
      + `${l.foil ? '✨ foil' : 'nonfoil'} · ${esc(l.cond)}`
      + (rev ? (l.validada ? ` · ✓ ${esc(l.validada)}` : ' · 📷 por fotografar') : '')
      + `</small></span>`
      + `<span class="pz">${eur(l.unit)}</span></div>`).join('')) + `</div>`;
  const foraHTML = f => !f.copias ? '' :
    `<details><summary>${esc(f.titulo)}<span>${cop(f.copias)} · ${eur(f.total)}`
    + `</span></summary><p>${esc(f.porque)}</p><ul>`
    + f.linhas.map(l => `<li><b>${l.q}× ${esc(l.nm)}</b>`
      + (l.rl ? ' <span class="rl">RL</span>' : '') + ` <i>(${esc(l.local)})</i>`
      + ` — ${esc(l.motivo)}</li>`).join('') + `</ul></details>`;
  const foraTot = (S.fora || []).reduce((a, f) => a + f.copias, 0);
  const foraEur = (S.fora || []).reduce((a, f) => a + (f.total || 0), 0);
  return `<details class="vblk" id="v-saida" open><summary><span>${ico('saida')} Saída: para o `
    + `Cardmarket e para a estante${so ? ' — só validadas' : ''}</span><span class="vtot">`
    + `${cop(copias)}${so ? '' : ' · ' + eur(S.total)}</span></summary>`
    + `<p class="lead">O que entra: o <b>excedente normal</b> e a <b>Reserved List `
    + `que passou a tua regra</b> — ${cop(copias)} em ${est.grupos.length} `
    + `sítio${pl(est.grupos.length)} da estante. Uma linha por cópia, com o `
    + `estado de cada uma`
    + (rev ? `, e a coluna <b>Foto</b> (validada / por revalidar)${so
        ? ' — <b>só as que têm foto desta campanha</b>' : ''}` : '') + `.</p>`
    /* 1. O FICHEIRO */
    + `<h3>1. O ficheiro para carregar stock</h3>`
    + `<div class="sfmt${F.confirmado ? '' : ' nao'}">`
    + (F.confirmado
       ? `✅ <b>Formato aprendido do teu ficheiro</b> (<code>data/${esc(F.ficheiro)}</code>): `
         + `${F.colunas.length} colunas, delimitador <code>${esc(F.delimitador === '\t' ? 'TAB' : F.delimitador)}</code>`
         + (F.vazias && F.vazias.length
            ? ` — deixei vazias: <b>${esc(F.vazias.join(', '))}</b>.` : '.')
       : `⚠️ <b>Formato predefinido, NÃO confirmado</b> contra uma conta real do `
         + `Cardmarket (${F.colunas.length} colunas: <code>${esc(F.colunas.join(', '))}</code>). `
         + `Para o ficheiro sair na forma certa, descarrega uma vez o teu stock da `
         + `conta e guarda-o como <code>data/cardmarket-stock-exemplo.csv</code>: `
         + `o exportador lê o cabeçalho e o delimitador e passa a escrever assim.`)
    + `</div>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this,'csv')" `
    + `aria-label="Copiar o CSV de stock">copiar CSV</button>`
    + `<button class="cpbtn" id="saida-csv" data-nome="${esc(nomeCsv)}">⬇ ${esc(nomeCsv)}</button>`
    + (D.editable
       ? `<button class="btn sm" data-saida="gravar" aria-label="Gravar os ficheiros em data/">`
         + `💾 gravar em data/${so ? ' (só validadas)' : ''}</button>` : '')
    + `</div>`
    + `<textarea class="cmk" data-cmk="csv" readonly>${esc(csv)}</textarea>`
    /* 2. A ESTANTE */
    + `<h3>2. Ir buscar à estante</h3>`
    + `<p class="lead">Por <b>onde a cópia está</b>, e por cor dentro de cada sítio `
    + `(como no binder). Imprime esta aba ou copia o texto.</p>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this,'est')" `
    + `aria-label="Copiar a lista da estante">copiar lista</button>`
    + `<button class="cpbtn" id="saida-txt">⬇ ${esc(S.nome_estante)}</button></div>`
    + `<textarea class="cmk" data-cmk="est" readonly>${esc(txt)}</textarea>`
    + `<div class="est">` + est.grupos.map(grupoHTML).join('') + `</div>`
    /* 3. O QUE FICA DE FORA */
    + `<h3>3. Fica de fora: ${cop(foraTot)} · ${eur(foraEur)}</h3>`
    + `<p class="lead">Não entram no ficheiro nem na lista — a decisão está tomada `
    + `(ou por tomar) e cada linha diz porquê. Os blocos completos estão mais abaixo.</p>`
    + `<div class="fora">` + (S.fora || []).map(foraHTML).join('')
    + (foraTot ? '' : `<p class="ok2">✓ Nada ficou de fora.</p>`) + `</div>`
    + `</details>`;
}

/* Descarregar um texto como ficheiro — o mesmo gesto do CSV da arrumação. */
function baixarTexto(texto, nome, tipo) {
  const b = new Blob([texto], { type: tipo || 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b);
  a.download = nome;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast(`${nome} descarregado.`);
}

/* «Gravar em data/»: o servidor RECALCULA a lista e escreve os dois ficheiros
   (`venda-stock.csv` + `venda-estante.txt`) ao lado da base — os mesmos que o
   `daily` escreve todas as manhãs. Só no modo edição, pela razão de sempre. */
async function gravarSaida(btn, soValid) {
  btn.disabled = true;
  try {
    const r = await gravar('api/venda-export', { so_validadas: !!soValid });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Gravado.');
    btn.textContent = '✓ gravado'; btn.classList.add('done');
  } catch (e) { btn.disabled = false; erro('Não deu: ' +e.message); }
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

/* --------------------------------------------------- NÃO ENCONTRADAS
   As cópias que ele procurou e não achou. Estão fora da colecção para todos os
   efeitos — não contam para nenhuma caixa, para a cobertura, para a venda nem
   para o valor —, mas **não foram apagadas**: é aqui que se vêem.

   A MINIATURA DA FOTO não é enfeite. As duas cópias que motivaram isto (a
   Chromatic Star e a Grinding Station do Cloud cEDH) entraram por foto há meses;
   sem ela a linha é um nome sem prova nenhuma, e ele não tem como saber se a
   carta existiu e se sumiu, ou se nunca lá esteve. A foto vive no PC: no site
   publicado a lista aparece na mesma, com o nome do ficheiro em vez da imagem. */
function vistaNaoEncontradas() {
  const ms = D.nao_encontradas || [];
  const q = ms.reduce((s, m) => s + m.q, 0);
  const val = ms.reduce((s, m) => s + (m.total || 0), 0);
  let h = `<h2>${ico('procurar')} Não encontradas</h2>`
    + `<p class="lead">Cartas que o vault tinha como tuas e que <b>não estavam `
    + `na estante</b> quando as foste buscar. Estão fora da coleção — não `
    + `contam para nenhuma caixa${VENDA_ON() ? ' nem para a venda' : ''} — e `
    + `voltaram a ser compra. `
    + `<b>Nada foi apagado</b>: se aparecerem, o «afinal encontrei» põe tudo `
    + `como estava.</p>`
    + `<p class="tot"><b>${cop(q)}</b> em <b>${ms.length}</b> linha${pl(ms.length)}`
    + (val ? ` · ${eur(val)} de valor fora da coleção` : '') + `</p>`;
  if (!ms.length) {
    return h + `<p class="ok2">✓ Nada por encontrar.</p>`;
  }
  h += `<div class="nenc">`;
  for (const m of ms) {
    const foto = m.tem_foto && D.editable
      ? `<img class="nef" src="foto?copy=${m.copy_id}`
        + `${D.token ? '&t=' + encodeURIComponent(D.token) : ''}" alt="" `
        + `loading="lazy">`
      : (m.img ? `<img class="nef" src="${esc(m.img)}" alt="" loading="lazy">`
               : `<span class="nef vazia">sem foto</span>`);
    h += `<div class="ne"><div class="nei">${foto}</div>`
      + `<div class="neb"><b>${m.q}× ${esc(m.nm)}</b>`
      + `<small>${esc(m.set_code)}${m.foil ? ' ✨' : ''} ${esc(m.lang)}`
      + ` · estava em ${esc(m.balde)}`
      + (m.unit ? ` · ${eur(m.unit)}/cópia` : '') + `</small>`
      + `<small>faltou a <b>${esc(m.caixa || '—')}</b> em ${esc(m.quando)}`
      + (m.foto ? ` · 📷 <code>${esc(m.foto)}</code>` : ' · sem foto de origem')
      + `</small></div>`
      /* O botão só no modo edição, como todos os outros: no site publicado não
         há endpoint que grave, e um botão que não grava mente. */
      /* `data-encontrei`, e não `data-enc` (2026-09-20): esse é o `+`/`−` das
         encomendas, e os dois `onclick` no mesmo atributo faziam o segundo
         ganhar — o `+` de uma encomenda chamava o «afinal encontrei». */
      + (D.editable
         ? `<button class="btn sm" data-encontrei="${m.copy_id}">✓ Afinal encontrei`
           + `</button>`
         : '')
      + `</div>`;
  }
  return h + `</div><p class="nota">O registo de cada marca (e de cada volta) `
    + `fica em <code>data\\nao-encontradas.csv</code>, ao lado da base — como o `
    + `<code>vendas.csv</code>.</p>`;
}

/* ------------------------------------------------------------ A FEIRA
   André, 2026-09-20, à letra: *"como vou ter um objetivo de ir ao RC "trocar"
   cartas nas bancas, fazemos logo uma projeção do que vou levar como moeda de
   troca para o que quero trazer; indico-te a wantlist e prováveis vendors que
   lá estarão, que poderão ter os preços das cartas no market, e avaliamos;
   será sobretudo cartas que eu preciso para completar decks."*

   Tudo vem do Python (`mtgvault.feira`): a página desenha LEVAR (a venda, com
   a marca «levo/não levo» e o 📷), TRAZER (o «a comprar» das caixas + a
   wantlist manual + os vendors) e o SALDO nas duas taxas. As taxas, as marcas,
   a wantlist e os vendors vivem no config — os botões só no modo edição. */
const pct = v => `${Math.round((v || 0) * 100)} %`;

function feiraTaxasHTML(F) {
  const nota = `<p class="nota">As taxas são <b>estimativas tuas</b>, não dados: o que `
    + `uma banca costuma dar pelo Trend, em dinheiro e em crédito de troca. Afina-as `
    + `depois da primeira feira (<code>feira.taxa_dinheiro</code> / `
    + `<code>feira.taxa_troca</code> no <code>colecao_config.json</code>).</p>`;
  if (!D.editable) {
    return `<div class="taxas"><span>💶 dinheiro <b>${pct(F.taxa_dinheiro)}</b> do Trend</span>`
      + `<span>🔁 troca <b>${pct(F.taxa_troca)}</b> do Trend</span>${nota}</div>`;
  }
  return `<div class="taxas"><label>💶 dinheiro <input id="feira-tdin" type="number" `
    + `min="0" max="100" step="1" value="${Math.round(F.taxa_dinheiro * 100)}" `
    + `aria-label="Taxa em dinheiro, por cento do Trend"> %</label>`
    + `<label>🔁 troca <input id="feira-ttroca" type="number" min="0" max="100" step="1" `
    + `value="${Math.round(F.taxa_troca * 100)}" aria-label="Taxa em troca, por cento do Trend"> %</label>`
    + `<button class="btn sm" data-feira="taxas">guardar as taxas</button>${nota}</div>`;
}

function feiraLevarHTML(F) {
  const L = F.levar || { linhas: [] };
  /* «PARA JÁ TIRA O VENDER» (André, 2026-09-25). A metade «levar» É a lista de
     venda, com preço e carta a carta — deixá-la aqui era tirar a aba Vender e
     mantê-la nesta com outro nome. Quem decide é o Python (`feira.levar`, que
     devolve zeros e `desligado`), para o saldo e os textos virem já certos. */
  if (L.desligado) {
    return `<details class="vblk" id="f-levar" open><summary>`
      + `<span>1. Moeda de troca — desligada</span></summary>`
      + `<p class="lead">Esta metade está <b>desligada</b> em `
      + `<code>colecao_config.json → venda.mostrar</code> (25/09/2026). `
      + `O que ela mostrava continua a ser calculado todos os dias; volta `
      + `inteira quando puseres a chave a <code>true</code>.</p></details>`;
  }
  const rev = !!L.revalidacao;
  const so = !!L.so_validadas;
  const filtro = rev ? `<div class="seg" role="group" aria-label="Que cópias levar">`
    + (D.editable
       ? `<button class="${so ? 'on' : ''}" data-feira="filtro" data-v="1" aria-pressed="${so}">📷 Só validadas</button>`
         + `<button class="${so ? '' : 'on'}" data-feira="filtro" data-v="0" aria-pressed="${!so}">Tudo</button>`
       : `<span class="bdg ${so ? 'ok' : ''}">${so ? '📷 só validadas' : 'tudo, com ou sem foto'}</span>`)
    + `<span class="dim">${so ? `${L.fora_foto || 0} cópias ficam por não terem foto desta campanha (${eur(L.fora_foto_trend)})`
                              : 'a levar também o que ainda não tem foto'}</span></div>` : '';
  let h = `<details class="vblk" id="f-levar" open><summary><span>1. Levar — moeda de troca</span>`
    + `<span class="vtot">${cop(L.copias || 0)} · Trend ${eur(L.trend)} · troca ~${eur(L.troca)}</span></summary>`
    + `<p class="lead">A <b>lista de venda de hoje</b> (aba <b>Vender</b>: excedente normal + `
    + `Reserved List que passou a tua regra), com o Trend por cópia. `
    + (rev ? `Por omissão só vão as cópias <b>com foto desta campanha</b> — <i>"o que eu `
      + `for vender também vai com foto"</i>. ` : '')
    + `Marca <b>não levo</b> no que fica em casa; a marca fica no config, não neste aparelho.</p>`
    + filtro
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this,'lv')" aria-label="Copiar a lista `
    + `Levar">copiar lista Levar</button></div>`
    + `<textarea class="cmk" data-cmk="lv" readonly>${esc(F.texto_levar || '')}</textarea>`;
  if (!L.linhas.length) return h + `<p class="empty">Não há nada na lista de venda.</p></details>`;
  /* EM IMAGEM (2026-09-20): um tile por impressão e sítio, por cor — a cópia
     exacta, o que rende em troca no chip, o Trend e o «levo / não levo» no
     rodapé; o que fica em casa (não levo) aparece apagado. */
  const levoBtn = l => D.editable
    ? `<button class="btn sm" data-feira="${l.levo ? 'nao-levo' : 'levo'}" data-chave="${esc(l.chave)}" `
      + `aria-label="${l.levo ? 'Não levar' : 'Levar'} ${esc(l.nm)}">${l.levo ? '✕ não levo' : '✓ levo'}</button>` : '';
  if (comImagens()) {
    h += grelhaPorCor(L.linhas, l => ({
      nm: l.nm, sid: l.sid, rl: !!l.rl,
      q: l.leva_q !== l.q && l.levo ? `${l.leva_q}/${l.q}×` : `×${l.q}`,
      est: !l.levo ? 'nao' : !rev ? 'venda' : !l.por_revalidar ? 'ok' : !l.validadas ? 'rev' : 'rev',
      rot: !l.levo ? '✕ não levo'
        : (rev ? (!l.por_revalidar ? '✓ ' : !l.validadas ? '📷 ' : `📷 ${l.validadas}/${l.q} `) : '')
          + `🔁 ${esc(eur(l.troca))}`,
      mat: [l.set, l.foil ? '✨' : '', (l.lang || '').toUpperCase(), l.cond || ''],
      pz: `Trend ${eur(l.trend)}`,
      nota: `${esc(l.local)} · 💶 ${esc(eur(l.dinheiro))}`,
      acts: levoBtn(l), cls: l.levo ? '' : 'nao',
      tit: `${l.nm} — ${l.q}× ${l.set} ${(l.lang || '').toUpperCase()}${l.foil ? ' foil' : ''} — ${l.local}`
        + ` — Trend ${eur(l.unit)}/un · ${eur(l.trend)} — dinheiro ${eur(l.dinheiro)} · troca ${eur(l.troca)}`
        + (l.levo ? '' : ' — não levo'),
    }), { max: MAX_TILES });
    if (L.nao_levo) {
      h += `<p class="nota">Marcadas «não levo»: ${cop(L.nao_levo)} · ${eur(L.nao_levo_trend)} — ficam em casa.</p>`;
    }
    if (L.sem_preco) h += `<p class="nota">${cop(L.sem_preco)} sem preço na base: contam a zero.</p>`;
    return h + `</details>`;
  }
  h += `<table class="vt"><thead><tr><th></th>${rev ? '<th title="foto desta campanha">📷</th>' : ''}`
    + `<th>carta</th><th>edição</th><th>onde está</th><th>Trend/un</th><th>Trend</th>`
    + `<th>💶 ${pct(L.taxa_dinheiro)}</th><th>🔁 ${pct(L.taxa_troca)}</th>`
    + (D.editable ? '<th></th>' : '') + `</tr></thead><tbody>`;
  let cor = null;
  const ncol = 7 + (rev ? 1 : 0) + (D.editable ? 1 : 0);
  for (const l of L.linhas) {
    if (l.cor !== cor) {
      cor = l.cor;
      h += `<tr><td colspan="${ncol}"><div class="corhdr">${esc(l.cor_nome)}</div></td></tr>`;
    }
    const foto = !rev ? '' : !l.por_revalidar
      ? `<td class="rvok" title="validada${pl(l.validadas)}">✓</td>`
      : !l.validadas ? `<td class="rvfoto" title="por fotografar">📷</td>`
      : `<td class="rvfoto" title="${l.validadas} com foto, ${l.por_revalidar} sem">📷 ${l.validadas}/${l.q}</td>`;
    h += `<tr class="${l.levo ? '' : 'nao'}" data-nm="${esc(l.nm)}">`
      + `<td class="q">${l.leva_q !== l.q && l.levo ? `${l.leva_q}/${l.q}×` : `${l.q}×`}</td>` + foto
      + `<td>${esc(l.nm)}${l.rl ? ' <span class="rl">RL</span>' : ''}</td>`
      + `<td class="dim">${esc(l.set)} ${l.foil ? '✨' : ''} ${esc((l.lang || '').toUpperCase())}`
      + `${l.cond ? ' ' + esc(l.cond) : ''}</td>`
      + `<td class="dim">${esc(l.local)}</td>`
      + `<td class="pz">${eur(l.unit)}</td><td class="pz tot">${eur(l.trend)}</td>`
      + `<td class="pz">${eur(l.dinheiro)}</td><td class="pz">${eur(l.troca)}</td>`
      + (D.editable ? `<td class="act"><button class="btn sm" data-feira="${l.levo ? 'nao-levo' : 'levo'}" `
        + `data-chave="${esc(l.chave)}" aria-label="${l.levo ? 'Não levar' : 'Levar'} ${esc(l.nm)}">`
        + `${l.levo ? '✕ não levo' : '✓ levo'}</button></td>` : '')
      + `</tr>`;
  }
  h += `</tbody></table>`;
  if (L.nao_levo) {
    h += `<p class="nota">Marcadas «não levo»: ${cop(L.nao_levo)} · ${eur(L.nao_levo_trend)} — ficam em casa.</p>`;
  }
  if (L.sem_preco) h += `<p class="nota">${cop(L.sem_preco)} sem preço na base: contam a zero.</p>`;
  return h + `</details>`;
}

/* Os chips «X pode ter» de uma linha de Trazer (com o ✕ no modo edição). */
function vendChips(l) {
  return (l.vendors || []).map(v => `<span class="vend">${esc(v)} pode ter`
    + (D.editable ? ` <button class="btn sm" data-feira="pode-ter-nao" data-nome="${esc(l.nm)}" `
      + `data-vendor="${esc(v)}" aria-label="Tirar ${esc(v)} de ${esc(l.nm)}" `
      + `style="min-height:24px;padding:0 6px">✕</button>` : '') + `</span>`).join('');
}

function feiraTrazerHTML(F) {
  const T = F.trazer || { linhas: [], por_caixa: [], vendors: [] };
  const vends = T.vendors || [];
  const opcoes = sel => vends.map(v => `<option value="${esc(v.nome)}"${v.nome === sel ? ' selected' : ''}>`
    + `${esc(v.nome)}</option>`).join('');
  let h = `<details class="vblk" id="f-trazer" open><summary><span>2. Trazer — o que quero</span>`
    + `<span class="vtot">${cop(T.copias || 0)} · mínimo ${eur(T.minimo)}`
    + (T.com_maximo ? ` · com os teus máximos ${eur(T.maximo)}` : '') + `</span></summary>`
    + `<p class="lead"><b>Automático:</b> o «a comprar» de cada caixa <b>depois</b> das encomendas `
    + `(a mesma lista da aba <b>Comprar</b>, a lista padrão do Cloud incluída), com o preço `
    + `mínimo de hoje e o material que a caixa exige. <b>Manual:</b> o que acrescentares aqui `
    + `(<code>feira.wantlist</code>) — com preço máximo, notas e para que caixa; uma entrada `
    + `para a mesma carta e a mesma caixa <b>funde-se</b> na linha automática, não a duplica. `
    + `Os preços são os da base (Trend do Cardmarket via Scryfall): <b>nenhuma consulta ao `
    + `Cardmarket</b> parte daqui.</p>`
    + `<div class="flh"><button class="cpbtn" onclick="copiar(this,'tz')" aria-label="Copiar a lista `
    + `Trazer">copiar lista Trazer</button><button class="cpbtn" onclick="copiar(this,'tcm')" `
    + `aria-label="Copiar a wantlist para o Cardmarket">copiar p/ Cardmarket</button></div>`
    + `<textarea class="cmk" data-cmk="tz" readonly>${esc(F.texto_trazer || '')}</textarea>`
    + `<textarea class="cmk" data-cmk="tcm" readonly>${esc(F.texto_cardmarket || '')}</textarea>`;
  if (D.editable) {
    const caixas = D.caixas.map(c => `<option value="${esc(c.slot)}">${esc(c.nome)}</option>`).join('');
    h += `<div class="pform" role="group" aria-label="Acrescentar à wantlist">`
      + `<input class="nm" id="feira-wl-nome" placeholder="carta (nome em inglês)" autocomplete="off">`
      + `<input class="q" id="feira-wl-q" type="number" min="1" value="1" aria-label="quantas">`
      + `<select id="feira-wl-slot" aria-label="para que caixa"><option value="">— coleção —</option>${caixas}</select>`
      + `<select id="feira-wl-lang" aria-label="língua"><option value="">língua da caixa</option>`
      + `<option value="pt">PT</option><option value="en">EN</option></select>`
      + `<select id="feira-wl-finish" aria-label="acabamento"><option value="">acabamento da caixa</option>`
      + `<option value="nonfoil">nonfoil</option><option value="foil">foil</option></select>`
      + `<input class="px" id="feira-wl-max" type="number" min="0" step="0.01" placeholder="máx €" aria-label="preço máximo">`
      + `<input class="nm" id="feira-wl-notas" placeholder="notas" autocomplete="off">`
      + `<button class="btn sm" data-feira="wl-add">+ acrescentar</button></div>`;
  }
  if (!T.linhas.length) return h + `<p class="ok2">✓ Não falta nada às caixas e a wantlist está vazia.</p></details>`;
  /* EM IMAGEM (2026-09-20): por caixa, um tile por carta a trazer — a
     impressão mais barata, o mínimo no chip, o material, os vendors e as
     notas por baixo, e o selector de vendor / «máx €» / «tirar» no rodapé. */
  const actsTrazer = l => !D.editable ? '' :
    (vends.length ? `<select class="feira-vend" data-nome="${esc(l.nm)}" aria-label="Vendor que pode ter ${esc(l.nm)}">`
      + `<option value="">vendor…</option>${opcoes('')}</select>` : '')
    + `<button class="btn sm" data-feira="max" data-nome="${esc(l.nm)}" data-slot="${esc(l.slot || '')}" `
    + `data-q="${l.q}" data-lang="" data-finish="" aria-label="Fixar o preço máximo de ${esc(l.nm)}">máx €</button>`
    + (l.origem !== 'caixa' ? `<button class="btn sm" data-feira="wl-tirar" data-nome="${esc(l.nm)}" `
      + `data-slot="${esc(l.slot || '')}" aria-label="Tirar ${esc(l.nm)} da wantlist">✕ tirar</button>` : '');
  for (const c of T.por_caixa) {
    h += `<div class="box"><div class="btop"><b>${esc(c.caixa)}</b><span class="pct" style="font-size:15px">`
      + `${cop(c.copias)} · ${eur(c.minimo)}${c.maximo !== c.minimo ? ` · máx ${eur(c.maximo)}` : ''}`
      + (c.sem_preco ? ` · ${c.sem_preco} sem preço` : '') + `</span></div>`;
    if (comImagens()) {
      h += grelhaHTML(c.linhas.map(l => ({
        nm: l.nm, sid: l.sid, est: 'miss', q: `×${l.q}`,
        rot: `🛒 ${esc(eur(l.minimo))}`,
        mat: String(l.mat || l.req || '').split(' · ').filter(Boolean),
        pz: `${eur(l.unit)}/un` + (l.max != null ? ` · máx ${eur(l.max)}` : ''),
        chips: (l.cara ? '<span class="cara">cara</span>' : '')
          + (l.origem === 'caixa' ? '' : `<span class="org${l.origem === 'manual' ? ' man' : ''}">`
            + `${l.origem === 'manual' ? 'manual' : 'caixa + manual'}</span>`),
        nota: [l.sfoil ? 'nunca saiu em foil' : '',
               l.acam || l.pfoto ? `📦 ${l.acam ? l.acam + ' a caminho' : ''}${l.acam && l.pfoto ? ' · ' : ''}`
                 + `${l.pfoto ? l.pfoto + ' pendente de foto' : ''}` : '',
               l.nota ? esc(l.nota) : '', vendChips(l), l.notas ? esc(l.notas) : '']
          .filter(Boolean).join(' · '),
        acts: actsTrazer(l),
        tit: `${l.nm} — ${l.q}× ${l.mat || l.req || ''} — ${eur(l.unit)}/un · mínimo ${eur(l.minimo)}`
          + (l.max != null ? ` · máx ${eur(l.max)}/un` : '') + (l.notas ? ` — ${l.notas}` : '')
          + ((l.vendors || []).length ? ` — pode ter: ${l.vendors.join(', ')}` : ''),
      })), { max: MAX_TILES });
      h += `</div>`;
      continue;
    }
    h += `<table class="vt"><thead><tr><th></th><th>carta</th><th>material</th><th>mín/un</th>`
      + `<th>mínimo</th><th>máx</th><th class="rz">vendors · notas</th>${D.editable ? '<th></th>' : ''}</tr></thead><tbody>`;
    for (const l of c.linhas) {
      const org = l.origem === 'caixa' ? '' : `<span class="org${l.origem === 'manual' ? ' man' : ''}">`
        + `${l.origem === 'manual' ? 'manual' : 'caixa + manual'}</span>`;
      h += `<tr data-nm="${esc(l.nm)}"><td class="q">${l.q}×</td>`
        + `<td>${esc(l.nm)}${l.cara ? '<span class="cara">cara</span>' : ''}${org}`
        + (l.sfoil ? `<small class="dim"> nunca saiu em foil</small>` : '')
        + (l.acam || l.pfoto ? `<small class="encs">📦 ${l.acam ? l.acam + ' a caminho' : ''}`
          + `${l.acam && l.pfoto ? ' · ' : ''}${l.pfoto ? l.pfoto + ' pendente de foto' : ''}</small>` : '')
        + (l.nota ? `<small class="dim"> ${esc(l.nota)}</small>` : '') + `</td>`
        + `<td class="dim">${esc(l.mat || l.req || '')}</td>`
        + `<td class="pz">${eur(l.unit)}</td><td class="pz tot">${eur(l.minimo)}</td>`
        + `<td class="pz">${l.max != null ? eur(l.max) + '/un' : '<span class="dim">—</span>'}</td>`
        + `<td class="rz">${vendChips(l)}`
        + (l.notas ? `<small class="dim">${esc(l.notas)}</small>` : '') + `</td>`
        + (D.editable ? `<td class="act">`
          + (vends.length ? `<select class="feira-vend" data-nome="${esc(l.nm)}" aria-label="Vendor que pode ter ${esc(l.nm)}">`
            + `<option value="">vendor…</option>${opcoes('')}</select>` : '')
          + `<button class="btn sm" data-feira="max" data-nome="${esc(l.nm)}" data-slot="${esc(l.slot || '')}" `
          + `data-q="${l.q}" data-lang="" data-finish="" aria-label="Fixar o preço máximo de ${esc(l.nm)}">máx €</button>`
          + (l.origem !== 'caixa' ? `<button class="btn sm" data-feira="wl-tirar" data-nome="${esc(l.nm)}" `
            + `data-slot="${esc(l.slot || '')}" aria-label="Tirar ${esc(l.nm)} da wantlist">✕ tirar</button>` : '')
          + `</td>` : '')
        + `</tr>`;
    }
    h += `</tbody></table></div>`;
  }
  if (T.sem_preco) h += `<p class="nota">${cop(T.sem_preco)} sem preço na base: contam a zero no mínimo.</p>`;
  return h + `</details>`;
}

function feiraVendorsHTML(F) {
  const vends = (F.trazer && F.trazer.vendors) || [];
  let h = `<details class="vblk" id="f-vendors"${vends.length ? ' open' : ''}><summary><span>3. Vendors — quem lá vai estar</span>`
    + `<span class="vtot">${vends.length}</span></summary>`
    + `<p class="lead">Os que achas que lá estarão, com o utilizador do Cardmarket ou o site, para `
    + `veres os preços deles <b>tu</b> antes de ir — o vault não os consulta. Em cada carta de `
    + `<b>Trazer</b> podes marcar «o vendor X pode ter».</p>`;
  if (D.editable) {
    h += `<div class="pform" role="group" aria-label="Acrescentar um vendor">`
      + `<input class="nm" id="feira-v-nome" placeholder="nome do vendor" autocomplete="off">`
      + `<input class="nm" id="feira-v-cm" placeholder="utilizador Cardmarket" autocomplete="off">`
      + `<input class="nm" id="feira-v-site" placeholder="site" autocomplete="off">`
      + `<input class="nm" id="feira-v-notas" placeholder="notas" autocomplete="off">`
      + `<button class="btn sm" data-feira="vendor-add">+ vendor</button></div>`;
  }
  if (!vends.length) return h + `<p class="empty">Ainda sem vendors.</p></details>`;
  h += `<ul class="vendors fl">` + vends.map(v => `<li><b>${esc(v.nome)}</b>`
    + (v.cardmarket ? `<small>Cardmarket: ${esc(v.cardmarket)}</small>` : '')
    + (v.site ? `<small>${esc(v.site)}</small>` : '')
    + (v.notas ? `<small>${esc(v.notas)}</small>` : '')
    + (D.editable ? `<button class="btn sm" data-feira="vendor-tirar" data-vendor="${esc(v.nome)}" `
      + `aria-label="Tirar o vendor ${esc(v.nome)}">✕</button>` : '') + `</li>`).join('') + `</ul>`;
  return h + `</details>`;
}

function vistaFeira() {
  const F = D.feira;
  if (!F) return `<h2>${ico('feira')} Feira</h2><p class="empty">Sem dados da feira.</p>`;
  const L = F.levar || {}, T = F.trazer || {}, S = F.saldo || {};
  /* Com a metade «levar» desligada (2026-09-25) a página fica com o que ele
     quer TRAZER: os números da moeda de troca e o saldo seriam quatro zeros a
     dizer que não tem nada para trocar, o que não é verdade — é que não está à
     vista. A aba fica, o subtítulo passa a ser o que falta comprar. */
  const meia = !!L.desligado;
  const sal = (v, tit, sub) => `<div class="num sal ${v >= 0 ? 'pos' : 'neg'}">${tit}<b>`
    + `${v >= 0 ? '+' : '−'}${eur(Math.abs(v))}</b>${sub ? `<span class="dim">${sub}</span>` : ''}</div>`;
  let h = `<div class="feira"><h2>${ico('feira')} Feira: ${meia ? 'o que quero trazer'
      : 'moeda de troca vs. o que quero trazer'} <span class="n">${esc(feiraSub())}</span></h2>`
    + `<p class="lead"><i>"fazemos logo uma projeção do que vou levar como moeda de troca para o que `
    + `quero trazer"</i> (20/09/2026). ` + (meia
      ? `A metade de <b>levar</b> está desligada em <code>venda.mostrar</code> `
        + `(25/09/2026) — fica o <b>trazer</b>: o que falta às caixas mais a tua wantlist.`
      : `<b>Levar</b> é a lista de venda de hoje; <b>trazer</b> é o `
        + `que falta às caixas mais a tua wantlist. O saldo diz se a moeda chega, ao Trend e às `
        + `duas taxas de banca.`) + `</p>`
    + (meia ? '' : feiraTaxasHTML(F))
    + `<div class="nums">`
    + (meia ? '' :
       `<div class="num eur">levar · Trend<b>${eur(L.trend)}</b><span class="dim">${cop(L.copias || 0)}`
    + (L.rl_copias ? ` · RL ${L.rl_copias}` : '') + `</span></div>`
    + `<div class="num">em dinheiro<b>${eur(L.dinheiro)}</b><span class="dim">${pct(L.taxa_dinheiro)} do Trend</span></div>`
    + `<div class="num">em troca<b>${eur(L.troca)}</b><span class="dim">${pct(L.taxa_troca)} do Trend</span></div>`)
    + `<div class="num buy">trazer · mínimo<b>${eur(T.minimo)}</b><span class="dim">${cop(T.copias || 0)}`
    + (T.com_maximo ? ` · com máximos ${eur(T.maximo)}` : '') + `</span></div>`
    + (meia ? '' :
       sal(S.dinheiro, 'saldo em dinheiro', T.com_maximo ? `com máximos ${S.dinheiro_max >= 0 ? '+' : '−'}${eur(Math.abs(S.dinheiro_max))}` : '')
    + sal(S.troca, 'saldo em troca', T.com_maximo ? `com máximos ${S.troca_max >= 0 ? '+' : '−'}${eur(Math.abs(S.troca_max))}` : ''))
    + `</div>`;
  if (!meia && L.revalidacao && L.so_validadas && !L.copias && L.fora_foto) {
    h += `<p class="lead">⚠️ <b>Ainda não há nada validado para levar</b>: as ${cop(L.fora_foto)} da venda `
      + `(${eur(L.fora_foto_trend)}) estão por fotografar nesta campanha. Fotografa-as (aba `
      + `<b>📷 Revalidação</b>) ou passa o filtro a <b>Tudo</b>.</p>`;
  }
  h += feiraLevarHTML(F) + feiraTrazerHTML(F) + feiraVendorsHTML(F);
  /* Por caixa: quanto custa trazer o que falta a cada uma, e que fatia da
     moeda de troca isso é. */
  const pc = F.por_caixa || [];
  if (pc.length) {
    h += `<details class="vblk" id="f-caixas" open><summary><span>4. Por caixa</span>`
      + `<span class="vtot">${pc.length} caixa${pl(pc.length)}</span></summary>`
      /* As duas últimas colunas são sobre a moeda de troca: saem com ela. */
      + `<table class="vt"><thead><tr><th>caixa</th><th>cópias</th><th>mínimo</th><th>máx</th>`
      + (meia ? '' : `<th>saldo troca</th><th>% da troca</th>`) + `</tr></thead><tbody>`
      + pc.map(c => `<tr><td>${esc(c.caixa)}</td><td class="q">${c.copias}</td>`
        + `<td class="pz">${eur(c.minimo)}</td><td class="pz dim">${eur(c.maximo)}</td>`
        + (meia ? '' :
           `<td class="pz ${c.saldo_troca >= 0 ? 'tot' : ''}">${c.saldo_troca >= 0 ? '+' : '−'}${eur(Math.abs(c.saldo_troca))}</td>`
        + `<td class="pz dim">${c.pct_da_troca == null ? '—' : c.pct_da_troca + ' %'}</td>`) + `</tr>`).join('')
      + `</tbody></table></details>`;
  }
  return h + `<p class="nota">Pelo terminal: <code>py -m mtgvault.cli feira</code> (a projeção) e `
    + `<code>feira wantlist add|remover|listar</code>. Tudo o que aqui se marca fica no `
    + `<code>colecao_config.json → feira</code>.</p></div>`;
}

/* As escritas da feira, todas para `api/feira` (só config). O botão diz a
   acção em `data-feira`; os campos lêem-se ao lado. */
async function feiraAccao(btn) {
  const act = btn.dataset.feira;
  const campo = id => { const e = $('#' + id); return e ? String(e.value || '').trim() : ''; };
  const corpo = { act };
  if (act === 'taxas') {
    corpo.dinheiro = campo('feira-tdin'); corpo.troca = campo('feira-ttroca');
  } else if (act === 'filtro') {
    corpo.so_validadas = btn.dataset.v === '1';
  } else if (act === 'levo' || act === 'nao-levo') {
    corpo.chave = btn.dataset.chave;
  } else if (act === 'wl-add') {
    corpo.nome = campo('feira-wl-nome'); corpo.q = Number(campo('feira-wl-q') || 1);
    corpo.slot = campo('feira-wl-slot') || null; corpo.lang = campo('feira-wl-lang') || null;
    corpo.finish = campo('feira-wl-finish') || null; corpo.max = campo('feira-wl-max') || null;
    corpo.notas = campo('feira-wl-notas');
    if (!corpo.nome) { erro('Escreve o nome da carta.'); return; }
  } else if (act === 'wl-tirar') {
    corpo.nome = btn.dataset.nome; corpo.slot = btn.dataset.slot || null;
  } else if (act === 'max') {
    /* O preço máximo de uma linha: pergunta-se o número (um campo por linha
       era uma tabela ilegível no telemóvel). Vazio = tirar o máximo. */
    const v = prompt(`Preço máximo por cópia para ${btn.dataset.nome} (vazio = sem máximo):`);
    if (v === null) return;
    corpo.nome = btn.dataset.nome; corpo.slot = btn.dataset.slot || null;
    corpo.q = Number(btn.dataset.q || 1); corpo.max = String(v).trim() || null;
  } else if (act === 'vendor-add') {
    corpo.nome = campo('feira-v-nome'); corpo.cardmarket = campo('feira-v-cm');
    corpo.site = campo('feira-v-site'); corpo.notas = campo('feira-v-notas');
    if (!corpo.nome) { erro('Escreve o nome do vendor.'); return; }
  } else if (act === 'vendor-tirar') {
    if (!armar(btn, `✓ tirar ${btn.dataset.vendor}?`)) return;
    corpo.vendor = btn.dataset.vendor;
  } else if (act === 'pode-ter' || act === 'pode-ter-nao') {
    corpo.nome = btn.dataset.nome; corpo.vendor = btn.dataset.vendor;
  }
  btn.disabled = true;
  try {
    const r = await gravar('api/feira', corpo);
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Feito.');
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' + e.message); }
}

/* ------------------------------------------------------------------ render */
/* Que PARTES uma aba precisa. Uma caixa precisa da dela; as abas de resumo
   (Plano, Todas, montados, por montar) desenham-se só com o índice. */
function partesDe(id) {
  if (D._completo) return [];
  const c = D.caixas.find(x => x.slot === id);
  if (c) return c.vazio ? [] : [c.parte];
  return ({ arrumar: ['arrumar'], partilhadas: ['compras'], comprar: ['compras'],
            vender: VENDA_ON() ? ['venda'] : [], sugestoes: ['premodern'],
            encomendas: ['encomendas'], feira: ['feira'],
            revalidacao: D.revalidacao ? ['revalidacao'] : [] })[id] || [];
}
async function carregaParte(nome) {
  if (PARTES[nome]) return PARTES[nome];
  const p = await carregaDados('deckboxes/' + nome + '.json');
  if (nome.startsWith('caixa-')) {
    const c = D.caixas.find(x => x.parte === nome);
    if (c) Object.assign(c, p);
  } else if (nome === 'compras') { Object.assign(D, p); }
  else { D[nome] = p; }
  PARTES[nome] = p;
  return p;
}
let renderN = 0;
let manterScroll = null;     /* o scroll a repor depois de um `recarregar()` */
async function render() {
  const v = $('#vista');
  grelhaN = 0;
  const faltam = partesDe(aba).filter(p => !PARTES[p]);
  if (faltam.length) {
    /* Só aqui é que se espera: com tudo já cá (o payload embutido, ou uma aba
       já aberta) o resto corre de seguida, sem um `await` — e é isso que deixa
       o harness de `node` chamar `render()` e ler o `#vista` logo a seguir. */
    const n = ++renderN;
    v.innerHTML = '<p class="carregando">A carregar…</p>';
    try { await Promise.all(faltam.map(carregaParte)); }
    catch (e) { if (n === renderN) erroDados(v, e); return; }
    if (n !== renderN) return;    /* ele já mudou de aba entretanto */
  }
  const caixa = D.caixas.find(c => c.slot === aba);
  /* O interruptor «Imagens / Lista» (2026-09-20) no topo de cada aba que
     mostra cartas; na aba da caixa vive na barra de filtros (`filtroHTML`). */
  const sw = ['arrumar', 'comprar', 'vender', 'sugestoes', 'encomendas',
              'revalidacao', 'feira'].includes(aba) ? vistaSwitchHTML() : '';
  if (caixa) {
    v.innerHTML = filtroHTML() + caixaHTML(caixa, false);
  } else if (aba === 'plano') { v.innerHTML = ligacaoHTML() + vistaPlano(); }
  else if (aba === 'montados') { v.innerHTML = vistaMontados(); }
  else if (aba === 'pormontar') { v.innerHTML = vistaPorMontar(); }
  else if (aba === 'arrumar') { v.innerHTML = sw + vistaArrumar(); }
  else if (aba === 'partilhadas') { v.innerHTML = vistaPartilhadas(); }
  else if (aba === 'comprar') { v.innerHTML = sw + vistaComprar(); }
  /* Sem o interruptor (2026-09-25) não se desenha a aba Vender: a `abasFixas`
     já a tira do `#` e do que ficou guardado no aparelho, e este ramo é a
     terceira defesa — um `ir('vender')` de um botão velho cai nas caixas. */
  else if (aba === 'vender') {
    v.innerHTML = VENDA_ON() ? sw + vistaVender() : vistaTodas();
  }
  else if (aba === 'sugestoes') {
    v.innerHTML = D.premodern && D.premodern.activo ? sw + vistaSugestoes() : vistaTodas();
  }
  else if (aba === 'naoenc') { v.innerHTML = vistaNaoEncontradas(); }
  else if (aba === 'encomendas') { v.innerHTML = sw + vistaEncomendas(); }
  else if (aba === 'revalidacao') { v.innerHTML = sw + vistaRevalidacao(); }
  else if (aba === 'feira') { v.innerHTML = sw + vistaFeira(); }
  else { v.innerHTML = vistaTodas(); }
  ligar();
  renderBarra();
  aplicarProcura();
  window.scrollTo({ top: manterScroll == null ? 0 : manterScroll });
  manterScroll = null;
}

function filtroHTML() {
  /* `aria-pressed`: são botões que ficam carregados, não links. Sem isto o
     leitor de ecrã lia "Todas as cartas, botão" nos dois, sem dizer qual está
     activo — e a diferença é só a cor de fundo. */
  const b = (f, t) => `<button class="${filtro === f ? 'on' : ''}" data-f="${f}"`
    + ` aria-pressed="${filtro === f}">${t}</button>`;
  const g = (f, t) => `<button class="${grupo === f ? 'on' : ''}" data-g="${f}"`
    + ` aria-pressed="${grupo === f}">${t}</button>`;
  /* A PROCURA (2026-09-18): numa caixa de 75 cartas, à frente da estante, a
     pergunta é "onde está a Cabal Therapy?" — e a resposta era percorrer a
     grelha e as 75 linhas do passo 1. O campo filtra o que está desenhado
     (grelha, passo 1, básicas, compras) sem voltar a desenhar nada, sem
     acentos e sem maiúsculas (ver `casaProcura`). A barra é `sticky`: fica
     no topo do ecrã enquanto ele desce a lista. */
  /* Só a procura e os dois ATALHOS ficam presos ao topo — com os cinco filtros
     lá dentro a barra eram três linhas a 390 px, um terço do ecrã sempre
     tapado. Os atalhos são a resposta a "o painel Montar vive no fim da aba,
     três ecrãs abaixo": um toque e está lá. */
  const c = D.caixas.find(x => x.slot === aba);
  const saltos = c && c.montar
    ? `<button class="salto" data-salto=".montar" aria-label="Ir para o painel `
      + `Montar">⬇ Montar</button>`
      + `<button class="salto" data-salto="#passo2" aria-label="Ir para o que `
      + `falta comprar">⬇ Comprar</button>` : '';
  return `<div class="seg topo" role="search">`
    + `<span class="procura"><input type="search" id="procura" `
    + `placeholder="🔎 procurar carta…" autocomplete="off" autocapitalize="off" `
    + `spellcheck="false" value="${esc(procura)}" aria-label="Procurar uma carta `
    + `nesta caixa"><span id="procura-n" class="dim"></span></span>${saltos}</div>`
    + `<div class="seg" role="group" aria-label="Filtrar as cartas">`
    + b('tudo', 'Todas as cartas') + b('faltam', 'Só o que falta')
    + g('estado', 'por estado') + g('tipo', 'por tipo')
    + `<button class="${grande ? 'on' : ''}" data-big="1" `
    + `aria-pressed="${grande}">🔍 imagens grandes</button></div>`
    /* «Imagens / Lista» (2026-09-20): vale para a aba inteira — grelha, passo
       1, básicas, compras, reserva, revalidação. */
    + vistaSwitchHTML();
}

/* ------------------------------------------------------------- PROCURA
   O que ele escreve fica em `procura` enquanto a aba está aberta (mudar de
   caixa limpa-a — a procura é desta caixa). Um `render()` — mudar o filtro,
   voltar a ler os dados — volta a aplicá-la ao que desenhou. */
let procura = '';

/* Sem acentos, sem maiúsculas, sem ligaduras: "cabeca" acha "Cabeça", "aether"
   acha "Æther Vial", "elan" acha "Élan". Só se compara o que o catálogo TEM —
   o nome oracle, em inglês: o nome impresso em português não está na base
   (o Scryfall só o traz no bulk `all_cards`, que o vault não descarrega). */
function normProcura(s) {
  return String(s == null ? '' : s).toLowerCase()
    .replace(/æ/g, 'ae').replace(/œ/g, 'oe').replace(/ø/g, 'o').replace(/ß/g, 'ss')
    .replace(/['’]/g, '')            /* "senseis" acha "Sensei's" */
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ').trim();
}
/* Cada palavra da procura tem de estar no nome, por qualquer ordem: "plow
   swords" acha "Swords to Plowshares". */
function casaProcura(nome, q) {
  const n = normProcura(nome), termos = normProcura(q).split(' ').filter(Boolean);
  return !termos.length || termos.every(t => n.includes(t));
}

/* Aplica a procura ao que está desenhado: tudo o que tem `data-nm` (as
   miniaturas, as linhas do passo 1, as básicas, as linhas de compra) esconde-se
   ou mostra-se; os cabeçalhos de cor/tipo/bloco saem enquanto há procura, para
   a lista ficar plana. Sem `render()`: são 60+ elementos e um `hidden` cada. */
function aplicarProcura() {
  const alvo = $('#procura');
  if (!alvo) return;
  const q = procura;
  let vistos = 0, total = 0;
  for (const el of document.querySelectorAll('[data-nm]')) {
    const bate = casaProcura(el.dataset.nm, q);
    el.hidden = !bate;
    total++; if (bate) vistos++;
  }
  for (const el of document.querySelectorAll('.corhdr,.typehdr,.bhdr')) {
    el.hidden = !!normProcura(q);
  }
  const n = $('#procura-n');
  if (n) n.textContent = normProcura(q) ? `${vistos} de ${total}` : '';
  document.body.classList.toggle('comprocura', !!normProcura(q));
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
  let h = `<h2>${ico('plano')} Por onde começar</h2>`
    + `<p class="lead">Primeiro os <b>permanentes</b>, por ordem de alocação — são `
    + `eles que ficaram com as cartas. Depois as <b>candidatas</b>, pela `
    + `percentagem que já tens: começa-se pelo que está mais perto de fechar. `
    + `Clica numa para abrir o painel <b>Montar</b> dela.</p>`;
  if (porMontar.length) {
    h += `<div class="nums">`
      + `<div class="num">caixas por montar<b>${porMontar.length}</b></div>`
      + `<div class="num">tirar da coleção<b>${soma(porMontar, 'tirar')}</b></div>`
      /* As COMPRAS são de TODAS as caixas, não só das que faltam montar — é o
         que o "fechar tudo por" ao lado já somava (`M`) e o que a aba Comprar
         mostra. Somar só as `porMontar` dava 225 cópias ao lado de 8 426,34 €,
         que são 232: os 601,29 € do Blue Farm (montado, congelado, 7 cartas por
         comprar) entravam no preço e ficavam fora da contagem. Dois números
         lado a lado a responder a perguntas diferentes, sem um único erro. */
      + `<div class="num buy">comprar<b>${soma(M, 'comprar')}</b></div>`
      + `<div class="num eur">fechar tudo por<b>${eur(soma(M, 'custo'))}</b></div>`
      + `</div><div class="plano">`
      + porMontar.map((m, i) => linha(m, i + 1)).join('') + `</div>`;
  } else {
    h += `<p class="empty">Está tudo montado. 🎉</p>`;
  }
  if (montadas.length) {
    h += `<h2>${ico('montado')} Já montadas <span class="n">${montadas.length}</span></h2>`
      /* "Não há nada a fazer nestas hoje" era mentira quando uma delas ainda
         tem compras: o Blue Farm está montado e congelado e mostra 7 cartas por
         comprar, 601,29 €. Não há nada a TIRAR da gaveta — a caixa está feita —
         e é isso que se pode afirmar. */
      + `<p class="lead">Estão feitas: não há cartas para tirar da coleção. `
      + `Se alguma ainda mostrar <b>comprar</b>, é a lista de hoje a pedir mais `
      + `do que a caixa tem. As <b>congeladas</b> mostram na aba <b>Arrumar</b> `
      + `o que trocar quando a lista mudar.</p>`
      + `<div class="plano">` + montadas.map(m => linha(m, 0)).join('') + `</div>`;
  }
  /* A VENDA vem depois, e a ordem não é decoração: o excedente é o que sobra
     DEPOIS de encher as caixas. Uma cópia que serve uma caixa do loadout nunca
     entra na lista de venda — é a saída `guardar`.
     Com o interruptor de 2026-09-25 desligado o Plano acaba nas caixas: o
     resumo da venda era três euros e um botão para a aba que já não existe. */
  if (!VENDA_ON()) return h;
  const V = D.venda;
  h += `<h2>${ico('vender')} Depois de montar: vender o excesso</h2>`
    + `<p class="lead"><b>Primeiro montar, depois vender.</b> Esta lista é o que `
    + `sobra <b>depois</b> de todas as caixas terem as cartas que a alocação lhes `
    + `deu: uma cópia que serve uma caixa nunca aparece aqui, mesmo que passe o `
    + `limite de 4 (fica em <b>🔒 Guardar</b>). É uma <b>sugestão a confirmar</b> — `
    + `nada sai da coleção sem tu dizeres.</p>`
    + `<div class="nums">`
    + `<div class="num eur">excedente normal<b>${eur(V.normal.total)}</b>`
    + `<span class="dim"> ${cop(V.normal.copias)}</span></div>`
    + `<div class="num eur">Reserved List<b>${eur(V.rl.total)}</b>`
    + `<span class="dim"> ${cop(V.rl.copias)} · uma a uma</span></div>`
    + `<div class="num">guardar (servem uma caixa)<b>${V.guardar.copias}</b></div>`
    + `</div>`
    + `<div class="seg"><button class="btn pri" data-aba="vender">`
    + `Ver e confirmar a venda →</button></div>`;
  return h;
}

function ligar() {
  /* A procura: a cada tecla, sem `render()` — só o `hidden` de cada elemento
     (ver `aplicarProcura`). O `search` apanha o ✕ de limpar do teclado do
     telemóvel, que não dispara `input` em todos os browsers. */
  const pq = $('#procura');
  if (pq) {
    const muda = () => { procura = pq.value || ''; aplicarProcura(); };
    pq.oninput = muda; pq.onsearch = muda;
  }
  /* Os atalhos da barra presa ao topo: descer até ao painel Montar / ao passo
     2. Navegação, sem escrita — existem também na página publicada. */
  for (const b of document.querySelectorAll('[data-salto]')) {
    b.onclick = () => {
      const alvo = document.querySelector(b.dataset.salto);
      if (alvo && alvo.scrollIntoView) alvo.scrollIntoView({ block: 'start' });
    };
  }
  for (const b of document.querySelectorAll('[data-f]')) {
    b.onclick = () => { filtro = b.dataset.f; P.filtro = filtro; save(); render(); };
  }
  for (const b of document.querySelectorAll('[data-g]')) {
    b.onclick = () => { grupo = b.dataset.g; P.grupo = grupo; save(); render(); };
  }
  for (const b of document.querySelectorAll('[data-big]')) {
    b.onclick = () => { grande = !grande; P.grande = grande; save(); render(); };
  }
  /* «Imagens / Lista» (2026-09-20): no aparelho e, no modo edição, no config. */
  for (const b of document.querySelectorAll('[data-vista]')) {
    b.onclick = () => mudarVista(b.dataset.vista);
  }
  /* «mostrar as outras N» de uma grelha grande: abre-a e redesenha no sítio. */
  for (const b of document.querySelectorAll('[data-mais]')) {
    b.onclick = () => { GRELHAS_ABERTAS.add(b.dataset.mais);
                        manterScroll = window.scrollY || 0; render(); };
  }
  for (const b of document.querySelectorAll('.mini[data-slot],.pl[data-slot]')) {
    b.onclick = () => ir(b.dataset.slot);
  }
  for (const b of document.querySelectorAll('[data-aba]:not(.dt)')) {
    b.onclick = () => ir(b.dataset.aba);
  }
  /* «Montar» abre a aba da caixa E desce até ao painel — o `ir()` põe a página
     no topo, e o painel Montar vive no fim da aba. Sem isto o botão parecia não
     fazer nada: mudava de aba e deixava-o a olhar para a barra da percentagem,
     com o passo 1 três ecrãs abaixo. Não escreve nada: é navegação, e por isso
     existe também na página publicada. */
  for (const b of document.querySelectorAll('[data-montar]')) {
    b.onclick = () => {
      ir(b.dataset.montar);
      const p = document.querySelector('.montar');
      if (p && p.scrollIntoView) p.scrollIntoView({ block: 'start' });
    };
  }
  /* Todos os botões de escrita, estejam num `.acts` ou dentro da lista de
     candidatos — um selector demasiado apertado deixava o "vou montar este"
     desenhado e morto, que é o pior dos dois mundos. */
  for (const b of document.querySelectorAll('[data-act]')) {
    b.onclick = () => accao(b.dataset.act, b.dataset.slot, b, b.dataset.aid,
                            b.dataset.nome, b.dataset.id);
  }
  /* O botão de registo do painel Montar. Passa pelo MESMO `registar()` da barra
     (com o resumo e a pergunta do que fazer às que ficaram por marcar) — era
     aqui que morava o segundo caminho, o que gravava a alocação calculada. */
  for (const b of document.querySelectorAll('[data-reg]')) {
    const c = D.caixas.find(x => x.slot === b.dataset.reg);
    if (c) b.onclick = () => registar(c, b);
  }
  /* As checkboxes dos vistos: numa linha `.mv` ou num tile `.tl` (2026-09-20)
     — o `data-id` é o mesmo, e é por ele que a barra conta. Só as que TÊM
     `data-id`: o tile de uma compra tem uma checkbox própria («já a tenho»),
     que é outro gesto (`data-falta`). */
  for (const l of document.querySelectorAll('.mv[data-id],.tl[data-id]')) {
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
  /* «Já a tenho, está no deck»: o check das faltas. É um `change` e não um
     clique num botão porque é o que ele faz com a lista à frente — marca e
     segue. Grava logo (com o «anular» de alguns segundos ao lado). */
  for (const cb of document.querySelectorAll('[data-falta]')) {
    cb.onchange = () => faltaCheck(cb);
  }
  /* ENCOMENDAS (2026-09-19): `+`/`−`, «Chegou», «desfazer» — nas linhas de
     compra de uma caixa e nos tiles do separador. */
  for (const b of document.querySelectorAll('[data-enc]')) {
    b.onclick = () => encAjustar(b);
  }
  for (const b of document.querySelectorAll('[data-chegou]')) {
    b.onclick = () => encChegou(b, false);
  }
  for (const b of document.querySelectorAll('[data-desfazer]')) {
    b.onclick = () => encChegou(b, true);
  }
  /* LISTA PADRÃO e RESERVA (2026-09-20): fixar / acrescentar / tirar / voltar,
     e reservar / tirar da reserva. Um endpoint só (`api/padrao`). */
  for (const b of document.querySelectorAll('[data-padrao],[data-reserva]')) {
    b.onclick = () => padraoAccao(b);
  }
  /* A FEIRA (2026-09-20): taxas, «levo/não levo», wantlist, vendors e o
     «pode ter» (o selector de vendor de cada linha). Um endpoint (`api/feira`). */
  for (const b of document.querySelectorAll('[data-feira]')) {
    b.onclick = () => feiraAccao(b);
  }
  for (const s of document.querySelectorAll('select.feira-vend')) {
    s.onchange = () => {
      if (!s.value) return;
      feiraAccao({ dataset: { feira: 'pode-ter', nome: s.dataset.nome, vendor: s.value },
                   disabled: false });
    };
  }
  const cc = $('#compra-caixa');
  if (cc) cc.onchange = () => { P.compra = cc.value; save(); render(); };
  for (const b of document.querySelectorAll('[data-vend]')) {
    b.onclick = () => vendida(b);
  }
  /* «Afinal encontrei», da aba Não encontradas. Mesmo endpoint do «anular» do
     aviso — é o mesmo gesto, só que sem prazo. */
  for (const b of document.querySelectorAll('[data-encontrei]')) {
    b.onclick = () => encontrei([Number(b.dataset.encontrei)], b);
  }
  /* A saída da venda: descarregar o CSV / a lista da estante, e gravar em data/. */
  const scsv = $('#saida-csv'), stxt = $('#saida-txt');
  const S = D.venda && D.venda.saida;
  const so = REV_ON() && soValidadas;
  if (scsv && S) scsv.onclick = () => baixarTexto(
    so ? S.csv_validadas : S.csv, so ? S.nome_csv_validadas : S.nome_csv,
    'text/csv;charset=utf-8');
  if (stxt && S) stxt.onclick = () => baixarTexto(
    so ? S.texto_estante_validadas : S.texto_estante, S.nome_estante);
  for (const b of document.querySelectorAll('[data-saida]')) {
    b.onclick = () => gravarSaida(b, so);
  }
  /* REVALIDAÇÃO (2026-09-20): o filtro «só validadas» da venda, o
     «Fotografar» (fixa o alvo) e o «parar». */
  for (const b of document.querySelectorAll('[data-sov]')) {
    b.onclick = () => { soValidadas = b.dataset.sov === '1'; P.soValidadas = soValidadas;
                        save(); render(); };
  }
  for (const b of document.querySelectorAll('[data-rev]')) {
    b.onclick = () => fotografar(b);
  }
  for (const b of document.querySelectorAll('[data-rev-parar]')) {
    b.onclick = () => pararRevalidacao(b);
  }
  /* A FOTO DA DECKBOX (2026-09-21): ampliar (leitura, nos dois modos) e o
     `<input type="file">` do botão (só existe no modo edição). */
  for (const i of document.querySelectorAll('[data-ampliar]')) {
    i.onclick = () => ampliarFoto(i.dataset.ampliar, i.dataset.nome || '');
  }
  for (const i of document.querySelectorAll('input[data-foto-caixa]')) {
    i.onchange = () => enviarFotoCaixa(i);
  }
  /* AS FOTOS DAS CARTAS, DO SITE (2026-09-21): a câmara por alvo e por cópia,
     e o «processar agora». Só existem no modo edição. */
  for (const i of document.querySelectorAll('input[data-foto-site]')) {
    i.onchange = () => enviarFotosSite(i);
  }
  for (const b of document.querySelectorAll('[data-processar]')) {
    b.onclick = () => processarAgora(b);
  }
  const fim = $('#arr-fim'), csv = $('#arr-csv'), lim = $('#arr-limpar');
  if (csv) csv.onclick = baixarCSV;
  if (lim) lim.onclick = () => limparVistosArrumar();
  if (fim) fim.onclick = jaArrumei;
}

/* «Limpar os vistos» da aba Arrumar (2026-09-18). Fazia `P.feitos = {}` — o
   objecto INTEIRO, onde vivem também as marcas do passo 1 de todas as caixas
   (`mt|`, `bs|`, `mo|`). Ele marcava 40 cartas numa caixa, vinha a esta aba,
   carregava aqui a pensar na arrumação, e as 40 marcas iam-se. Sem pergunta e
   sem erro. Agora só saem os vistos DA ARRUMAÇÃO (os que não têm prefixo de
   caixa), e pergunta-se primeiro. `semPergunta` é para os testes. */
function limparVistosArrumar(semPergunta) {
  const deCaixa = k => /^(mt|bs|mo)\|/.test(k);
  const alvo = Object.keys(P.feitos).filter(k => !deCaixa(k));
  if (!alvo.length) { toast('Não há vistos da arrumação para limpar.'); return 0; }
  if (!semPergunta && !confirm(`Limpar os ${alvo.length} vistos da arrumação? `
      + `(As marcas do painel Montar de cada caixa ficam.)`)) return 0;
  for (const k of alvo) delete P.feitos[k];
  save(); render(); toast('Vistos da arrumação limpos.');
  return alvo.length;
}

/* DOIS TOQUES PARA UMA ACÇÃO QUE NÃO SE DESFAZ (2026-09-18). O «vendida» era
   um botão de 22 px numa coluna de 246, com um `confirm()` por defesa — que no
   telemóvel se fecha com "OK" por reflexo, sem dizer que carta. O primeiro
   toque ARMA o botão e escreve nele o que vai fazer («✓ vender 1× Lotus
   Petal»); o segundo, nos 5 s seguintes, faz. Passado isso desarma-se sozinho.
   Devolve `true` quando é para avançar. */
const ARMAR_MS = 5000;
function armar(btn, texto) {
  if (btn.dataset.armado) {
    clearTimeout(Number(btn.dataset.armado));
    delete btn.dataset.armado;
    btn.classList.remove('armado');
    btn.textContent = btn.dataset.texto || btn.textContent;
    return true;
  }
  btn.dataset.texto = btn.textContent;
  btn.textContent = texto;
  btn.classList.add('armado');
  btn.dataset.armado = String(setTimeout(() => {
    delete btn.dataset.armado;
    btn.classList.remove('armado');
    btn.textContent = btn.dataset.texto || btn.textContent;
  }, ARMAR_MS));
  return false;
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
  if (!confirm(`Gravar a arrumação de ${cop(D.arrumar.copias)}? `
      + `Faz backup da base antes.`)) return;
  try {
    const r = await gravar('api/arrumar');
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(`Arrumado: ${cop(j.copias)} registadas.`);
    P.feitos = {}; save();
    recarregar();
  } catch (e) { erro('Não deu: ' +e.message); }
}

/* Escolher um deck para uma caixa é outro endpoint (`api/escolher`): mexe na
   `listas_escolhidas` e refaz as DUAS páginas, não só esta. */
const ESCOLHA = { escolher: 1, desmarcar: 1,
                  'pm-montar': 1, 'pm-recusar': 1, 'pm-aceitar': 1 };

/* O token vai em cabeçalho em TODAS as escritas: sem ele o servidor responde
   403 e a página fica só de leitura. É o que permite ter o porto aberto na rede
   de casa sem dar a qualquer aparelho o direito de lhe desmontar os decks. */
/* Quanto tempo se espera por uma escrita antes de desistir (2026-09-18). Um
   `fetch` sem prazo deixava o botão `disabled` para sempre quando o Wi-Fi
   hesitava — sem mensagem nenhuma. 25 s cobre um `loadout.report` inteiro na
   base dele (≈5 s) com folga para a rede de casa. */
let GRAVAR_TIMEOUT_MS = 25000;   /* `let`: o teste encurta-o para não esperar */
/* Com `ficheiro` (a foto da deckbox, 2026-09-21) o corpo é o ficheiro tal e
   qual, com o tipo dele, e o prazo é maior: 8 MB pela rede de casa não cabem
   em 25 s. O resto — token, prazo, a mensagem em português — é o mesmo. */
const ENVIAR_FICHEIRO_TIMEOUT_MS = 90000;
/* Um `FormData` (as FOTOS DAS CARTAS, 2026-09-21: várias num pedido) vai sem
   `Content-Type` escrito à mão — é o browser que põe o `multipart/form-data`
   com a fronteira; escrevê-lo aqui dava um corpo que o servidor não sabia
   partir. O prazo é o dos ficheiros, e sobe com o tamanho: 5 fotos de 4 MB
   pela rede de casa não cabem em 90 s. */
const ENVIAR_MB_TIMEOUT_MS = 20000;              /* por MB, por cima do prazo base */
async function gravar(url, corpo, ficheiro) {
  const ctl = (typeof AbortController === 'function') ? new AbortController() : null;
  const multipart = !!(ficheiro && typeof FormData === 'function' && ficheiro instanceof FormData);
  let prazo = ficheiro ? ENVIAR_FICHEIRO_TIMEOUT_MS : GRAVAR_TIMEOUT_MS;
  if (ficheiro && ficheiro._bytes) prazo += Math.ceil(ficheiro._bytes / 1e6) * ENVIAR_MB_TIMEOUT_MS;
  const t = ctl ? setTimeout(() => ctl.abort(), prazo) : null;
  try {
    const headers = { 'X-Mtgvault-Token': D.token || '' };
    if (!multipart) {
      headers['Content-Type'] = ficheiro ? (ficheiro.type || 'application/octet-stream')
                                         : 'application/json';
    }
    return await fetch(url, {
      method: 'POST',
      headers,
      body: ficheiro ? ficheiro : JSON.stringify(corpo || {}),
      signal: ctl ? ctl.signal : undefined,
    });
  } catch (e) {
    /* O `fetch` só rejeita quando o pedido NÃO chegou a ter resposta (rede, DNS,
       timeout): o servidor pode ter gravado ou não, e a única coisa honesta a
       dizer é isso — em português, e não "Failed to fetch". */
    const porque = (e && e.name === 'AbortError')
      ? `sem resposta do servidor em ${prazo / 1000} s`
      : 'sem ligação ao servidor (porto 8771)';
    throw new Error(`${porque} — não sei se gravou. Vê a rede, recarrega a `
      + `página e confirma antes de repetir.`);
  } finally {
    if (t) clearTimeout(t);
  }
}

/* RECARREGAR SEM PERDER A PÁGINA (2026-09-18). Depois de cada escrita fazia-se
   `recarregar()`: se a rede caísse entre o POST e o reload, o browser
   mostrava a página de erro DELE e a Deckboxes desaparecia — com a escrita
   feita do lado do servidor. Agora vai-se buscar o índice outra vez (e as
   partes voltam a ser pedidas quando ele as abrir) e redesenha-se; se isso
   falhar, diz-se e a página fica onde está. Com o payload EMBUTIDO (testes)
   não há de onde recarregar: aí é o `reload` de sempre. */
async function recarregar() {
  if (!D || D._completo) { location.reload(); return; }
  try {
    const d = await carregaDados('deckboxes.json');
    for (const k of Object.keys(PARTES)) delete PARTES[k];
    /* Fica onde estava: um «vendida» a meio de 246 linhas não o manda para o
       topo da tabela. */
    manterScroll = window.scrollY || 0;
    iniciar(d);
  } catch (e) {
    erro('Gravou, mas não consegui voltar a ler os dados: ' + e.message
         + ' — recarrega a página quando a rede voltar.');
  }
}

async function accao(act, slot, btn, aid, nome, id) {
  /* DESMONTAR apaga o que ele CONFIRMOU à mão. Pergunta-se, como na venda: a
     base é copiada antes, mas um toque enganado no telemóvel manda-o procurar
     as cartas todas outra vez. */
  if (act === 'desmontar' && !confirm(
      'Desmontar esta caixa? As cartas voltam à coleção e o vault deixa de '
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
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' +e.message); }
}

/* LISTA PADRÃO e RESERVA (André, 2026-09-20). O botão diz a acção
   (`data-padrao` = fixar|add|tirar|voltar; `data-reserva` = add|tirar) e a
   caixa; o nome, a quantidade e o bloco lêem-se dos campos ao lado. O
   «voltar ao consenso» é em dois toques (`armar`): perde a lista fixada. */
async function padraoAccao(btn) {
  const slot = btn.dataset.slot;
  const S = slot.replace(/"/g, '');
  const reserva = 'reserva' in btn.dataset;
  const act = reserva ? 'reserva-' + btn.dataset.reserva : btn.dataset.padrao;
  const campo = id => { const e = $('#' + id); return e ? String(e.value || '').trim() : ''; };
  const corpo = { act, slot };
  if (act === 'fixar') {
    corpo.texto = campo(`padrao-txt-${S}`);
    corpo.origem = campo(`padrao-origem-${S}`);
    if (!corpo.texto) { erro('Cola a lista primeiro (uma carta por linha).'); return; }
  } else if (act === 'add') {
    corpo.nome = campo(`padrao-nome-${S}`);
    corpo.q = Number(campo(`padrao-q-${S}`) || 1);
    corpo.board = campo(`padrao-board-${S}`) || 'main';
    if (!corpo.nome) { erro('Escreve o nome da carta.'); return; }
  } else if (act === 'tirar') {
    corpo.nome = btn.dataset.nome; corpo.board = btn.dataset.board || null;
  } else if (act === 'voltar') {
    if (!armar(btn, '✓ voltar ao consenso e perder a lista fixada?')) return;
  } else if (act === 'reserva-add') {
    corpo.nome = campo(`reserva-nome-${S}`);
    if (!corpo.nome) { erro('Escreve o nome da carta a reservar.'); return; }
  } else if (act === 'reserva-tirar') {
    corpo.nome = btn.dataset.nome;
  }
  btn.disabled = true;
  try {
    const r = await gravar('api/padrao', corpo);
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Feito — a alocação foi refeita.');
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' + e.message); }
}

async function vendida(btn) {
  const q = Number(btn.dataset.q || 1);
  /* Dois toques, com o NOME no segundo (ver `armar`): sai da colecção e fica no
     `data/vendas.csv`, com a base copiada antes — e não se desfaz com botão. */
  if (!armar(btn, `✓ vender ${q}× ${btn.dataset.nm || ''}?`.trim())) return;
  btn.disabled = true;
  try {
    const r = await gravar('api/vender', { linha: btn.dataset.vend, q });
    const j = await r.json();
    if (j.erro) throw new Error(j.erro);
    toast(j.msg || 'Registado.');
    recarregar();
  } catch (e) { btn.disabled = false; erro('Não deu: ' +e.message); }
}

function iniciar(dados) {
  D = dados;
  PM_RAZAO = D.pm_razao || '';
  if (!D.caixas.some(c => c.slot === aba) && !abasFixas().includes(aba)) {
    aba = 'plano';
  }
  /* O `#` do URL GANHA à aba guardada no aparelho: é a única maneira de um link
     da barra lateral (`deckboxes.html#comprar`) abrir onde diz, e o que ele
     partilha do telemóvel para o PC. */
  const doHash = abaDoHash();
  if (doHash) aba = doHash;
  renderResumo(); renderTabs(); render();
  /* Voltar atrás no browser, ou tocar noutro item da barra lateral já nesta
     página, muda só o `#` — sem isto a página ficava na mesma vista. */
  if (window.addEventListener) window.addEventListener('hashchange', () => {
    const h = abaDoHash();
    if (h && h !== aba) ir(h, false);
  });
}
/* Embutido (testes, harness) ou à parte (o site e o modo edição). */
const embutido = document.getElementById('dados');
if (embutido) {
  const d = JSON.parse(embutido.textContent);
  d._completo = true;
  iniciar(d);
} else {
  $('#vista').innerHTML = '<p class="carregando">A carregar os dados…</p>';
  carregaDados('deckboxes.json').then(iniciar).catch(e => erroDados($('#vista'), e));
}
"""


def main():
    from mtgvault import db
    with db.session() as con:
        print("deckboxes.html:", build(con))


if __name__ == "__main__":
    main()
