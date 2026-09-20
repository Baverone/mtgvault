"""A SAÍDA da lista de venda: o ficheiro para carregar stock e a lista da estante.

O objectivo do André, nas palavras dele: *"montar os decks nas deckboxes, comprar
as faltas e livrar-me dos excessos"*. A parte de comprar já sai da aba Comprar
(wantlist Cardmarket). A de VENDER ficava a meio (até 2026-09-18): a aba Vender
mostrava a lista e tinha o «vendida» por linha, mas nada tirava aquela lista do
ecrã para o sítio onde as cartas se vendem — 230 cópias em `venda` e 55 em
`venda_rl`, cerca de 4 300 € parados numa página que só se podia ler.

Três coisas saem daqui, e as três lêem o MESMO `loadout.report` que a página
mostra (uma segunda contagem era uma segunda opinião):

  1. **o CSV de stock** (`csv_stock`) — uma linha por cópia/lote com nome em
     inglês, edição (código), número, língua, acabamento, estado, quantidade,
     preço de referência e um comentário. O FORMATO tem dois caminhos:
       * o **predefinido** (`COLUNAS_PREDEFINIDAS`), que **NÃO foi confirmado
         contra uma conta real do Cardmarket** — é o que se escreve quando não
         há mais nada, e diz-se que não foi confirmado, em vez de o dar por
         certo;
       * o **aprendido**: se existir `data/cardmarket-stock-exemplo.csv` (uma
         exportação de stock que ele descarregue uma vez da conta dele), lê-se
         o cabeçalho, o delimitador e, havendo linhas, o VOCABULÁRIO das
         colunas (foil como `1`/`0` ou `Yes`/`No`, língua por nome ou por
         código, decimal com vírgula), e a exportação sai exactamente nessa
         forma — as colunas que se sabem preenchidas, as outras vazias. É o
         ficheiro dele que manda, não a memória de ninguém (`formato_exemplo`);
  2. **a lista da estante** (`lista_estante`/`texto_estante`) — agrupada por
     ONDE a cópia está (caixa, Colecção, Caixa RL PT/EN), por cor dentro de cada
     grupo (é como o binder está arrumado), com o total de cópias e de euros
     por grupo. É a que ele usa de telemóvel à frente da estante;
  3. **o que fica de fora, e porquê** (`fora_da_exportacao`) — as saídas que
     NÃO se vendem (`rl_segurar`, `rl_sem_historico`, `guardar`, `reservadas`,
     `retidos`) não entram no CSV e aparecem numa secção à parte com o motivo
     por linha (a percentagem e a janela, no caso da RL), para ele ver que a
     decisão foi tomada e não esquecida.

O `exportar` escreve as duas primeiras em `data/` (fora do Git: levam preços
por cópia, a mesma regra do `vendas.csv`), a partir do `daily` e do botão
«gravar em data/» do modo edição.
"""
from __future__ import annotations

import csv
import io
import os
from datetime import date
from pathlib import Path

from . import loadout, paginas

# ---------------------------------------------------------------------------
# O formato PREDEFINIDO. NÃO FOI CONFIRMADO CONTRA UMA CONTA REAL DO CARDMARKET
# (2026-09-18): não se conseguiu ver de fora o formato exacto que o site aceita
# hoje para carregar stock. É o mínimo que uma pessoa precisa para listar uma
# carta, com nomes de coluna em inglês e sem nenhuma pretensão de bater com o
# que o site exporta. Quem tem o formato certo é o ficheiro dele — ver
# `formato_exemplo`.
# ---------------------------------------------------------------------------
CHAVES = ("nm", "set", "num", "lang", "foil", "cond", "q", "price", "comment",
          "foto")
# `Foto` (2026-09-20): `validada <data>` / `por revalidar` — o que ele vender
# vai com foto desta campanha, e a coluna diz-lhe qual ainda não tem. No formato
# APRENDIDO do ficheiro dele não se acrescenta coluna nenhuma (o site tem de o
# aceitar tal e qual): aí a informação vai no comentário.
COLUNAS_PREDEFINIDAS = ("Name", "Set", "Number", "Language", "Foil", "Condition",
                        "Quantity", "Price", "Comment", "Foto")
DELIMITADOR_PREDEFINIDO = ","
FICHEIRO_EXEMPLO = "cardmarket-stock-exemplo.csv"
FICHEIRO_STOCK = "venda-stock.csv"
FICHEIRO_ESTANTE = "venda-estante.txt"

# Os nomes das línguas por extenso, e os IDs numéricos da API do Cardmarket
# (documentação da API v2: 1 English … 11 Traditional Chinese). Só se usam
# quando o ficheiro de exemplo dele mostra que é assim que a coluna vem —
# sem exemplo, escreve-se o nome por extenso, que qualquer pessoa lê.
LINGUAS = {"en": "English", "fr": "French", "de": "German", "es": "Spanish",
           "it": "Italian", "zhs": "S-Chinese", "ja": "Japanese",
           "pt": "Portuguese", "ru": "Russian", "ko": "Korean",
           "zht": "T-Chinese"}
LINGUAS_ID = {"en": 1, "fr": 2, "de": 3, "es": 4, "it": 5, "zhs": 6, "ja": 7,
              "pt": 8, "ru": 9, "ko": 10, "zht": 11}

# O que cada saída que NÃO se exporta quer dizer, para a secção "fica de fora".
# A ordem é a da página: a RL primeiro (é onde está o dinheiro), depois os
# substitutos, as reservadas e os retidos.
FORA = (
    ("rl_segurar", "RL a segurar — valorizou",
     "Reserved List que subiu o suficiente na janela em que foi medida: pela "
     "tua regra não se vende."),
    ("rl_sem_historico", "RL sem histórico suficiente",
     "Reserved List que o vault ainda não consegue medir: sem saber se subiu, "
     "não se vende."),
    ("guardar", "Guardar — servem um deck do loadout, ou estão na reserva de uma caixa",
     "Substitutos (servem uma caixa e só falham no material) e a RESERVA de "
     "cada caixa (2026-09-20: «cartas que poderão entrar»). Vendê-las era "
     "comprá-las outra vez."),
    ("reservadas", "Reservadas — decks por decidir",
     "Cartas de uma sugestão de Premodern ou da RL que o Legacy usaria: a "
     "decisão ainda não foi tomada."),
    ("retidos", "Retidos — extras dos decks vigiados",
     "Guardados sem prazo (2026-09-15): só saem com o «vendida», carta a carta."),
)


# ---------------------------------------------------------------------------
# As linhas: uma por CÓPIA (lote da `copies`), e não por linha da página
# ---------------------------------------------------------------------------
def _detalhe_copias(con, ids: list[int]) -> dict[int, dict]:
    """`copy_id -> {cond, num, cm_id, set, set_name}`, da base e do catálogo.

    A linha da lista de venda junta lotes iguais (`_fecha`), e o estado (NM/EX…)
    é da CÓPIA: dois lotes da mesma impressão em estados diferentes são duas
    linhas de stock. O número de coleccionador e o `cardmarket_id` vêm do
    catálogo pela impressão de cada cópia.
    """
    out: dict[int, dict] = {}
    ids = [int(i) for i in dict.fromkeys(ids)]
    for i in range(0, len(ids), 300):
        ch = ids[i:i + 300]
        marks = ",".join("?" * len(ch))
        for r in con.execute(
                f"""SELECT cp.id, cp.condition cond, c.collector_number num,
                           c.cardmarket_id cm_id, c.set_code, c.set_name,
                           cp.validado_em validado
                      FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                     WHERE cp.id IN ({marks})""", ch):
            out[r["id"]] = {"cond": (r["cond"] or "NM").upper(),
                            "num": r["num"] or "", "cm_id": r["cm_id"],
                            "set": (r["set_code"] or "").upper(),
                            "set_name": r["set_name"] or "",
                            "validado": r["validado"] or ""}
    return out


def linhas_export(con, rep: dict, so_validadas: bool = False) -> list[dict]:
    """O que ENTRA na exportação: `venda` + `venda_rl`, uma linha por cópia.

    Só estas duas saídas são compras a listar; as outras cinco são decisões
    tomadas (ou por tomar) e ficam em `fora_da_exportacao`. A `copias` de cada
    linha da página diz que exemplares são e quantos de cada um — é por aí que
    se parte, para o estado de cada cópia ir certo.

    `so_validadas` (2026-09-20): só as cópias com foto desta campanha — *"o que
    eu for vender também vai com foto"*. Cada linha traz `validada` (a data ou
    `""`) e `foto` (o texto da coluna) de qualquer maneira.
    """
    ids = [int(c) for k in ("venda", "venda_rl") for r in rep[k]
           for c, _q in (r.get("copias") or [])]
    det = _detalhe_copias(con, ids)
    out = []
    for chave in ("venda", "venda_rl"):
        for r in rep[chave]:
            for cid, q in (r.get("copias") or []):
                d = det.get(int(cid), {})
                if int(q) <= 0:
                    continue
                validada = d.get("validado") or ""
                if so_validadas and not validada:
                    continue
                out.append({
                    "validada": validada,
                    "foto": f"validada {validada}" if validada else "por revalidar",
                    "copy_id": int(cid), "nm": r["nm"],
                    "set": d.get("set") or (r["set_code"] or "").upper(),
                    "set_name": d.get("set_name") or r.get("set_name") or "",
                    "num": d.get("num", ""), "cm_id": d.get("cm_id"),
                    "lang": (r["lang"] or "en").lower(),
                    "foil": loadout.e_foil(r["finish"]), "finish": r["finish"],
                    "cond": d.get("cond", "NM"), "q": int(q),
                    "unit": r.get("unit"),
                    "total": round((r.get("unit") or 0) * int(q), 2),
                    "rl": bool(r.get("rl")), "local": r["local"],
                    "reason": r.get("reason") or "", "saida": chave,
                    # O comentário: de onde saiu e que cópia é. É o que permite
                    # ligar um artigo vendido à cópia da base. NB: no Cardmarket
                    # o comentário de um artigo é PÚBLICO — se não o quiser à
                    # vista, apaga a coluna antes de carregar. No formato
                    # aprendido é aqui que vai o estado da foto (não há coluna).
                    "comment": f"mtgvault #{int(cid)} · {r['local']}",
                })
    return _ordenadas(out)


def _ordenadas(out: list[dict]) -> list[dict]:
    out.sort(key=lambda l: (-(l["total"] or 0), l["nm"], l["copy_id"]))
    return out


# ---------------------------------------------------------------------------
# O formato APRENDIDO do ficheiro dele
# ---------------------------------------------------------------------------
# Como se reconhece cada coluna pelo nome (minúsculas, sem acentos). A ORDEM
# das regras conta: "set name"/"expansion" tem de bater antes de "set".
_MAPA = (
    (("idproduct", "product id", "cardmarket id", "cm id"), "cm_id"),
    (("set name", "expansion", "edition name", "edicao (nome)"), "set_name"),
    (("set", "edition", "edicao", "edição", "exp"), "set"),
    (("collector", "number", "numero", "número", "nr", "#"), "num"),
    (("language", "lang", "idioma", "lingua", "língua"), "lang"),
    (("foil", "isfoil", "finish", "acabamento"), "foil"),
    (("condition", "cond", "estado"), "cond"),
    (("quantity", "qty", "amount", "count", "quantidade", "qtd"), "q"),
    (("price", "preco", "preço"), "price"),
    (("comment", "comments", "comentario", "comentário", "note", "notes"), "comment"),
    (("name", "card", "nome", "carta"), "nm"),
)


def mapear_coluna(nome: str) -> str | None:
    """A chave interna de uma coluna do ficheiro dele, ou `None` (fica vazia)."""
    n = (nome or "").strip().lstrip("﻿").lower()
    if not n:
        return None
    for palavras, chave in _MAPA:
        if any(p == n or p in n for p in palavras):
            return chave
    return None


def _vocabulario(linhas: list[dict], colunas: dict[str, str]) -> dict:
    """O que as LINHAS do exemplo ensinam: como ele escreve o foil, a língua e o
    decimal. Sem linhas fica o predefinido de cada um."""
    voc = {"foil": "foil", "lang": "nome", "decimal": "."}
    if not linhas:
        return voc

    def valores(chave):
        col = next((c for c, k in colunas.items() if k == chave), None)
        return {str(l.get(col, "")).strip() for l in linhas if col} - {""}

    f = {v.lower() for v in valores("foil")}
    if f and f <= {"0", "1"}:
        voc["foil"] = "01"
    elif f and f <= {"yes", "no", "y", "n"}:
        voc["foil"] = "yesno"
    elif f and f <= {"true", "false"}:
        voc["foil"] = "truefalse"
    elif f and f <= {"x"}:
        voc["foil"] = "x"
    ln = valores("lang")
    if ln and all(v.isdigit() for v in ln):
        voc["lang"] = "id"
    elif ln and all(len(v) <= 3 for v in ln):
        voc["lang"] = "codigo"
    pr = valores("price")
    if pr and any("," in v and "." not in v for v in pr):
        voc["decimal"] = ","
    return voc


def formato_exemplo(caminho: Path | None = None) -> dict | None:
    """O formato lido de `data/cardmarket-stock-exemplo.csv`, ou `None`.

    Devolve `{colunas: [nome, …], mapa: {nome: chave|None}, delimitador,
    bom, fim_de_linha, vocabulario, ficheiro}`. Não se inventa nada: o que o
    cabeçalho não tiver não se escreve, e o que tiver e não se reconheça fica
    uma coluna vazia — com o nome dele, na posição dele.
    """
    alvo = caminho or (_pasta() / FICHEIRO_EXEMPLO)
    try:
        bruto = Path(alvo).read_bytes()
    except OSError:
        return None
    bom = bruto.startswith(b"\xef\xbb\xbf")
    texto = bruto.decode("utf-8-sig", errors="replace")
    primeira = texto.splitlines()[0] if texto.strip() else ""
    if not primeira.strip():
        return None
    # O delimitador: o `Sniffer` acerta na maioria; quando não tem por onde
    # (uma linha só), decide-se pelo que o cabeçalho tem — `;` é o que o Excel
    # europeu escreve, `\t` o que um "copiar da tabela" traz.
    try:
        delim = csv.Sniffer().sniff(primeira, delimiters=";,\t|").delimiter
    except csv.Error:
        delim = next((d for d in (";", "\t", "|", ",") if d in primeira), ",")
    rows = list(csv.reader(io.StringIO(texto), delimiter=delim))
    colunas = [c.strip() for c in rows[0]]
    mapa = {c: mapear_coluna(c) for c in colunas}
    dados = [dict(zip(colunas, r)) for r in rows[1:] if any(x.strip() for x in r)]
    return {"colunas": colunas, "mapa": mapa, "delimitador": delim, "bom": bom,
            "fim_de_linha": "\r\n" if "\r\n" in texto else "\n",
            "vocabulario": _vocabulario(dados, mapa), "linhas_exemplo": len(dados),
            "ficheiro": str(alvo)}


def _valor(l: dict, chave: str | None, voc: dict) -> str:
    """O texto de uma célula, no vocabulário do ficheiro."""
    if chave is None:
        return ""
    if chave == "foil":
        f = l["foil"]
        return {"01": "1" if f else "0", "yesno": "Yes" if f else "No",
                "truefalse": "true" if f else "false", "x": "X" if f else ""
                }.get(voc.get("foil"), "foil" if f else "nonfoil")
    if chave == "lang":
        modo = voc.get("lang")
        if modo == "id":
            return str(LINGUAS_ID.get(l["lang"], ""))
        if modo == "codigo":
            return l["lang"]
        return LINGUAS.get(l["lang"], l["lang"])
    if chave == "price":
        if l.get("unit") in (None, ""):
            return ""
        return f'{l["unit"]:.2f}'.replace(".", voc.get("decimal", "."))
    if chave == "cm_id":
        return "" if l.get("cm_id") in (None, "") else str(l["cm_id"])
    if chave == "q":
        return str(l["q"])
    if chave == "comment" and voc.get("foto_no_comentario"):
        # O formato aprendido não tem coluna para a foto: vai no comentário.
        return f"{l.get('comment') or ''} · foto {l.get('foto') or ''}".strip(" ·")
    return str(l.get(chave, "") or "")


def csv_stock(linhas: list[dict], formato: dict | None = None) -> str:
    """O CSV de stock: no formato aprendido, se houver, senão no predefinido."""
    if formato:
        colunas = list(formato["colunas"])
        chaves = [formato["mapa"].get(c) for c in colunas]
        delim = formato["delimitador"]
        voc = dict(formato.get("vocabulario") or {}, foto_no_comentario=True)
        fim = formato.get("fim_de_linha") or "\n"
        bom = "﻿" if formato.get("bom") else ""
    else:
        colunas, chaves = list(COLUNAS_PREDEFINIDAS), list(CHAVES)
        delim, voc, fim, bom = DELIMITADOR_PREDEFINIDO, {}, "\n", ""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator=fim,
                   quoting=csv.QUOTE_MINIMAL)
    w.writerow(colunas)
    for l in linhas:
        w.writerow([_valor(l, k, voc) for k in chaves])
    return bom + buf.getvalue()


def descricao_formato(formato: dict | None) -> dict:
    """O que a página e o CLI dizem sobre o formato usado — a verdade sobre de
    onde ele veio, e não uma afirmação de que está certo."""
    if not formato:
        return {"origem": "predefinido", "confirmado": False,
                "colunas": list(COLUNAS_PREDEFINIDAS),
                "delimitador": DELIMITADOR_PREDEFINIDO,
                "nota": ("Formato predefinido, NÃO confirmado contra uma conta "
                         "real do Cardmarket. Para o ficheiro sair na forma "
                         "certa, descarrega uma vez o teu stock da conta e "
                         f"guarda-o como data/{FICHEIRO_EXEMPLO}.")}
    sabidas = [c for c in formato["colunas"] if formato["mapa"].get(c)]
    vazias = [c for c in formato["colunas"] if not formato["mapa"].get(c)]
    return {"origem": "exemplo", "confirmado": True,
            "ficheiro": Path(formato["ficheiro"]).name,
            "colunas": list(formato["colunas"]),
            "delimitador": formato["delimitador"], "preenchidas": sabidas,
            "vazias": vazias, "linhas_exemplo": formato.get("linhas_exemplo", 0),
            "nota": (f"Formato aprendido de data/{Path(formato['ficheiro']).name}: "
                     f"{len(formato['colunas'])} colunas, "
                     f"{len(sabidas)} preenchidas"
                     + (f", {len(vazias)} deixadas vazias ("
                        + ", ".join(vazias) + ")" if vazias else "") + ".")}


# ---------------------------------------------------------------------------
# A lista da ESTANTE: por onde a cópia está
# ---------------------------------------------------------------------------
def lista_estante(con, rep: dict, linhas: list[dict] | None = None) -> dict:
    """`{grupos: [{local, copias, total, linhas}], copias, total, rl_copias,
    rl_total}` — as linhas de venda agrupadas por ONDE a cópia está fisicamente
    e, dentro de cada sítio, por COR e nome (é como o binder está: cor → CMC —
    ordená-las por nome obrigava-o a percorrer o binder de trás para a frente
    por cada carta, a mesma lição do painel Montar)."""
    linhas = linhas_export(con, rep) if linhas is None else linhas
    meta = paginas._meta_cartas(con, sorted({l["nm"] for l in linhas}))
    cores = {n: paginas.cor_de(tl, ci) for n, (tl, ci) in meta.items()}
    ordem = paginas.COR_ORDEM
    grupos: dict[str, list[dict]] = {}
    for l in linhas:
        cor = cores.get(l["nm"], "C")
        grupos.setdefault(l["local"], []).append(
            dict(l, cor=cor, cor_nome=paginas.COR_NOME.get(cor, cor)))
    saida = []
    for local, ls in grupos.items():
        ls.sort(key=lambda x: (ordem.get(x["cor"], 9), x["nm"], x["set"],
                               x["copy_id"]))
        saida.append({"local": local, "copias": sum(x["q"] for x in ls),
                      "total": round(sum(x["total"] or 0 for x in ls), 2),
                      "linhas": ls})
    # Os grupos maiores primeiro — é por aí que ele começa; empate pelo nome.
    saida.sort(key=lambda g: (-g["copias"], g["local"]))
    rl = [l for l in linhas if l["rl"]]
    return {"grupos": saida, "copias": sum(l["q"] for l in linhas),
            "total": round(sum(l["total"] or 0 for l in linhas), 2),
            "rl_copias": sum(l["q"] for l in rl),
            "rl_total": round(sum(l["total"] or 0 for l in rl), 2)}


def _eur(v) -> str:
    return "?" if v in (None, "") else f"{v:.2f} €"


def _cop(n: int) -> str:
    return f"{n} cópia" + ("" if n == 1 else "s")


def texto_estante(estante: dict, hoje: str | None = None) -> str:
    """A lista da estante em texto simples — para copiar, imprimir e ler no
    telemóvel. Uma linha por cópia, curta: `[cor] N× Nome · ED LN foil NM · un.`."""
    hoje = hoje or date.today().isoformat()
    out = [f"VENDA — ir buscar à estante ({hoje})",
           f"{_cop(estante['copias'])} · {_eur(estante['total'])}"
           + (f" (das quais Reserved List: {estante['rl_copias']} · "
              f"{_eur(estante['rl_total'])} — confirmar uma a uma)"
              if estante["rl_copias"] else ""), ""]
    for g in estante["grupos"]:
        out.append(f"■ {g['local']} — {_cop(g['copias'])} · {_eur(g['total'])}")
        for l in g["linhas"]:
            out.append(f"  [{l['cor']}] {l['q']}× {l['nm']}"
                       + (" (RL)" if l["rl"] else "")
                       + f" · {l['set']} {l['lang'].upper()}"
                       f" {'foil' if l['foil'] else 'nonfoil'} {l['cond']}"
                       f" · {_eur(l['unit'])}"
                       # A foto desta campanha (2026-09-20): o que vai vender
                       # sem ela está por fotografar — di-lo na lista da estante,
                       # que é a que ele leva à frente das cartas.
                       + ("" if l.get("validada") else " · 📷 por revalidar"))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# O que fica de fora, e porquê
# ---------------------------------------------------------------------------
def fora_da_exportacao(rep: dict) -> list[dict]:
    """As cinco saídas que NÃO entram no CSV, cada uma com o motivo por linha.

    Nas RL retidas o motivo traz a percentagem e a janela (`rl_nota`, ex.:
    *"+4.9 % em 27 d ≈ +16.3 %/90 d"*) e o motivo por que iriam à venda
    (`porque_venderia`) — sem isto ele via a lista mais curta e não sabia se a
    decisão foi tomada ou se a carta se perdeu.
    """
    out = []
    for chave, titulo, porque in FORA:
        ls = rep.get(chave) or []
        out.append({
            "chave": chave, "titulo": titulo, "porque": porque,
            "copias": sum(r["q"] for r in ls),
            "total": round(sum(r["total"] or 0 for r in ls), 2),
            "linhas": [{"nm": r["nm"], "q": r["q"], "local": r["local"],
                        "set": (r["set_code"] or "").upper(), "rl": bool(r["rl"]),
                        "total": r["total"],
                        "motivo": " ".join(x for x in (
                            r.get("reason") or "", r.get("rl_nota") or "",
                            (f"(ia por: {r['porque_venderia']})"
                             if r.get("porque_venderia") else "")) if x)}
                       for r in ls]})
    return out


# ---------------------------------------------------------------------------
# Tudo junto: o que a página, o CLI e o daily usam
# ---------------------------------------------------------------------------
def _pasta() -> Path:
    """`data/` — a pasta da base, como o `vendas.csv` (ver `loadout.ficheiro_vendas`)."""
    from . import db                      # noqa: PLC0415
    return db.pasta_dados()


def relatorio(con, rep: dict, exemplo: Path | None = None,
              hoje: str | None = None) -> dict:
    """O pacote inteiro: o CSV, o formato, a estante, o que ficou de fora.

    Desde 2026-09-20 vem em DUAS versões — tudo, e só as cópias com foto desta
    campanha (`csv_validadas`/`texto_estante_validadas`) — e com a contagem de
    cada lado (`copias_validadas`/`copias_por_revalidar`). O filtro «só
    validadas» da página troca entre as duas; a conta é a mesma.
    """
    hoje = hoje or date.today().isoformat()
    linhas = linhas_export(con, rep)
    fmt = formato_exemplo(exemplo)
    est = lista_estante(con, rep, linhas)
    validadas = [l for l in linhas if l["validada"]]
    est_v = lista_estante(con, rep, validadas)
    return {"hoje": hoje, "linhas": linhas, "copias": sum(l["q"] for l in linhas),
            "total": round(sum(l["total"] or 0 for l in linhas), 2),
            "csv": csv_stock(linhas, fmt), "formato": descricao_formato(fmt),
            "nome_csv": f"venda-stock-{hoje}.csv",
            "estante": est, "texto_estante": texto_estante(est, hoje),
            "nome_estante": f"venda-estante-{hoje}.txt",
            "copias_validadas": sum(l["q"] for l in validadas),
            "copias_por_revalidar": sum(l["q"] for l in linhas if not l["validada"]),
            "csv_validadas": csv_stock(validadas, fmt),
            "nome_csv_validadas": f"venda-stock-{hoje}-validadas.csv",
            "estante_validadas": est_v,
            "texto_estante_validadas": texto_estante(est_v, hoje),
            "fora": fora_da_exportacao(rep)}


def _escrever(destino: Path, texto: str) -> None:
    """Atómico (temporário + `os.replace`): o `daily` e o `webapp.py` escrevem os
    dois este ficheiro, e um CSV truncado a meio carregava metade do stock."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8", newline="")
    os.replace(tmp, destino)


def exportar(con, rep: dict | None = None, pasta: Path | None = None,
             exemplo: Path | None = None, so_validadas: bool = False) -> dict:
    """Escreve `data/venda-stock.csv` e `data/venda-estante.txt`.

    Sem data no nome de propósito: são "a lista de HOJE", reescrita a cada
    corrida, e um ficheiro por dia era um `data/` cheio de listas velhas que
    ninguém apagava. O histórico do que ele VENDEU é outro ficheiro
    (`vendas.csv`) e esse, sim, só cresce.

    `so_validadas` (2026-09-20): só as cópias com foto desta campanha — o
    botão «só validadas» da página e o `vender --exportar --so-validadas`.
    """
    rep = rep if rep is not None else loadout.report(con)
    pasta = Path(pasta) if pasta else _pasta()
    r = relatorio(con, rep, exemplo=exemplo)
    stock, estante = pasta / FICHEIRO_STOCK, pasta / FICHEIRO_ESTANTE
    if so_validadas:
        linhas = [l for l in r["linhas"] if l["validada"]]
        _escrever(stock, r["csv_validadas"])
        _escrever(estante, r["texto_estante_validadas"])
    else:
        linhas = r["linhas"]
        _escrever(stock, r["csv"])
        _escrever(estante, r["texto_estante"])
    copias, total = sum(l["q"] for l in linhas), round(sum(l["total"] or 0 for l in linhas), 2)
    fora = sum(f["copias"] for f in r["fora"])
    return {"csv": str(stock), "estante": str(estante), "copias": copias,
            "total": total, "linhas": len(linhas),
            "formato": r["formato"]["origem"], "fora": fora,
            "so_validadas": so_validadas,
            "copias_por_revalidar": r["copias_por_revalidar"],
            "resumo": (f"{copias} cópias / {total:.2f}€ em "
                       f"{len(linhas)} linhas → {stock.name} + "
                       f"{estante.name} (formato {r['formato']['origem']}; "
                       f"{fora} cópias ficam de fora"
                       + (f"; só validadas — {r['copias_por_revalidar']} por "
                          f"revalidar fora" if so_validadas
                          else f"; {r['copias_por_revalidar']} por revalidar")
                       + ")")}
