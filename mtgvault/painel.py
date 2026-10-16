"""O PAINEL DAS ALTERAÇÕES NOS DECKS (André, 2026-10-16, à letra).

*"todos os dias quero que mostres aqui ao lado as alterações ocorridas nos
decks"*. O painel lê quatro ficheiros de `data/painel/`; três escrevem-se aqui,
no passo `painel` do `daily`, depois do `meus-decks`:

- `alteracoes.json` — uma linha por carta que mudou nas trocas de HOJE;
- `estado-decks.json` — uma linha por deck seguido;
- `avisos.json` — o que merece atenção, com gravidade;
- `historico/AAAA-MM-DD.json` — as alterações desse dia, para a série. Não se
  apagam: cada corrida só (re)escreve o ficheiro do próprio dia.

O `valencia.json` é dele e NÃO se escreve aqui.

**Tudo sai da BASE e nada de um estado guardado à parte**: as trocas estão em
`deck_lista_trocas` (escrita pelo `my_decks._store`, com as duas listas
inteiras), e por isso correr o passo duas vezes no mesmo dia dá os mesmos
ficheiros. A poda das `decklists` não afecta nada disto — o histórico guarda as
cartas, os `decklist_id` são só para conferir.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from mtgvault import db, sources

FICHEIROS = ("alteracoes.json", "estado-decks.json", "avisos.json")

CAMPOS = {
    "alteracoes.json": ["data", "deck", "formato", "carta", "board", "delta", "de",
                        "para", "id", "sinal", "abs"],
    "estado-decks.json": ["deck", "formato", "lista", "anterior", "mudou",
                          "cartas_trocadas", "main", "sideboard"],
    "avisos.json": ["id", "gravidade", "deck", "aviso", "detalhe"],
}

# Uma troca com mais cartas do que isto não é a lista a evoluir: é outro deck.
# 60 é a regra dele (16/10). Como cada carta conta nos dois sentidos (sai uma,
# entra outra), 60 cartas são ~30 trocas de lugar — metade de um main.
# **E desde 2026-10-16 (à tarde) é também a régua da RECUSA** (`my_decks.
# avaliar_troca`): uma troca acima disto não entra e o deck fica com a lista
# anterior até ele dizer. Medido nas 64 trocas reconstruídas do `job_runs`
# (18/09 a 16/10): as de dentro do mesmo deck vão até 50 cartas e as que mudam
# de variante começam nas 62 — não há nenhuma entre 51 e 61, e o 60 cai no buraco.
TROCA_DE_ARQUETIPO = 60
# A lista para a qual se trocou é quase igual a uma que já se deixou nos últimos
# DIAS_OSCILA dias: o emparelhador anda a saltar entre dois decks.
SOBREPOSICAO_OSCILA = 0.80
DIAS_OSCILA = 14
# Uma lista de referência mais velha do que isto já não é "a versão atual".
DIAS_LISTA_VELHA = 14

GRAVIDADES = ("alta", "media", "baixa")


def pasta(raiz: Path | None = None) -> Path:
    """`data/painel/`, ao lado da base — pelo `db.pasta_dados()`, como todos os
    ficheiros que acompanham a base (num teste, a pasta temporária dele)."""
    return Path(raiz) if raiz else db.pasta_dados() / "painel"


def rotulo(jogador: str | None, dia: str | None) -> str:
    """'jogador DD/MM', a forma que o painel mostra."""
    if not dia:
        return ""
    return f"{jogador or '?'} {dia[8:10]}/{dia[5:7]}"


def _contar(cartas: list) -> dict:
    tot: dict = {}
    for b, n, q in cartas or []:
        tot[(b, n)] = tot.get((b, n), 0) + int(q)
    return tot


def _sobreposicao(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    comum = sum(min(q, b.get(k, 0)) for k, q in a.items())
    return comum / max(sum(a.values()), sum(b.values()))


def diferencas(de: list, para: list) -> list[tuple[str, str, int]]:
    """[(board, carta, delta)] com delta ≠ 0, de `de` para `para`."""
    a, b = _contar(de), _contar(para)
    out = []
    for k in sorted(set(a) | set(b), key=lambda k: (k[0] != "main", k[1].lower(), k[0])):
        d = b.get(k, 0) - a.get(k, 0)
        if d:
            out.append((k[0], k[1], d))
    return out


def _trocas(con, onde: str = "", params: tuple = ()) -> list:
    return con.execute(f"SELECT * FROM deck_lista_trocas {onde} ORDER BY id",
                       params).fetchall()


def alteracoes(con, hoje: str) -> list[dict]:
    """As cartas que mudaram nas trocas de lista de `hoje`. Uma releitura (a
    mesma lista, relida) não é uma alteração do deck — é uma correcção da
    leitura, e vai para os avisos."""
    out = []
    for t in _trocas(con, "WHERE corrida = ? AND motivo = 'troca'", (hoje,)):
        for b, n, d in diferencas(json.loads(t["de_cartas"] or "[]"),
                                  json.loads(t["para_cartas"] or "[]")):
            out.append({"data": hoje, "deck": t["deck"], "formato": t["formato"],
                        "carta": n, "board": "main" if b == "main" else "sideboard",
                        "delta": d,
                        "de": rotulo(t["de_jogador"], t["de_data"]),
                        "para": rotulo(t["para_jogador"], t["para_data"]),
                        "sinal": "entra" if d > 0 else "sai", "abs": abs(d)})
    for i, a in enumerate(out):
        a["id"] = f"{i:03d}"
    return [{k: a[k] for k in CAMPOS["alteracoes.json"]} for a in out]


def _cartas_do_deck(con, nome, fmt) -> tuple[dict | None, dict]:
    deck = con.execute("SELECT id, notes FROM decks WHERE name = ? AND format = ?",
                       (nome, fmt)).fetchone()
    if not deck:
        return None, {}
    return deck, _contar([[r["board"], r["card_name"], r["quantity"]] for r in con.execute(
        "SELECT board, card_name, quantity FROM deck_cards WHERE deck_id = ?", (deck["id"],))])


def cartas_do_nome(deck: str, assinatura: list[str]) -> list[str]:
    """As cartas da assinatura que dão nome ao deck: «Grinding Station» no
    Grinding Station, «Kappa Cannoneer» no Izzet Affinity (Kappa Cannoneer),
    «Greasefang, Okiba Boss» no Greasefang (pela parte antes da vírgula)."""
    low = deck.lower()
    return [c for c in assinatura if c.split(",")[0].strip().lower() in low]


def construir(con, hoje: str | None = None) -> dict:
    """Os três ficheiros do dia, em memória: {nome: lista}."""
    import my_decks  # noqa: PLC0415  (vive na raiz, como os outros geradores)

    hoje = hoje or date.today().isoformat()
    alts = alteracoes(con, hoje)
    estado, avisos = [], []

    def avisar(grav, deck, aviso, detalhe):
        avisos.append({"gravidade": grav, "deck": deck, "aviso": aviso, "detalhe": detalhe})

    limite_oscila = (date.fromisoformat(hoje) - timedelta(days=DIAS_OSCILA)).isoformat()
    for s in my_decks.seguidos():
        nome, fmt = s["deck"], s["formato"]
        deck, cartas = _cartas_do_deck(con, nome, fmt)
        nota = my_decks.ler_nota(deck["notes"] if deck else None)
        lista = rotulo(nota.get("jogador"), nota.get("data"))
        main = sum(q for (b, _n), q in cartas.items() if b == "main")
        side = sum(q for (b, _n), q in cartas.items() if b == "side")
        hoje_trocas = [t for t in _trocas(con, "WHERE deck = ? AND formato = ? AND corrida = ?",
                                          (nome, fmt, hoje))]
        trocas = [t for t in hoje_trocas if t["motivo"] == "troca"]
        n_troc = sum(a["abs"] for a in alts if a["deck"] == nome and a["formato"] == fmt)
        anterior = rotulo(trocas[0]["de_jogador"], trocas[0]["de_data"]) if trocas else lista
        estado.append({"deck": nome, "formato": fmt, "lista": lista or "sem lista",
                       "anterior": anterior or "sem lista", "mudou": "sim" if trocas else "nao",
                       "cartas_trocadas": n_troc, "main": main, "sideboard": side})

        # --- sem lista hoje -------------------------------------------------
        cand = s["procura"](con)
        if cand is None:
            tem = f"; fica a de {lista}" if lista else ""
            avisar("media", nome, s["falta"],
                   f"nenhuma lista que conte serve hoje este deck{tem}. Se se repetir "
                   "todos os dias, a assinatura ou o jogador já não existem no metagame.")
        # --- troca recusada, à espera dele -----------------------------------
        # Diz-se TODOS os dias enquanto a lista mais recente for a recusada e o
        # deck continuar na anterior: uma recusa dita uma vez e esquecida era o
        # deck parado sem ninguém saber porquê.
        elif deck and nota.get("decklist_id") != cand["id"]:
            rec = con.execute(
                "SELECT * FROM deck_lista_trocas WHERE deck = ? AND formato = ? "
                "AND motivo = 'recusada' AND para_decklist_id = ? ORDER BY id DESC LIMIT 1",
                (nome, fmt, cand["id"])).fetchone()
            if rec:
                porque = my_decks.avaliar_troca(json.loads(rec["de_cartas"] or "[]"),
                                                json.loads(rec["para_cartas"] or "[]"),
                                                cartas_do_nome(nome, s["assinatura"]))
                avisar("alta", nome, f"troca recusada: {porque or 'recusada'}",
                       f"a lista mais recente ({rotulo(rec['para_jogador'], rec['para_data'])}, "
                       f"#{rec['para_decklist_id']}) nao entrou e o deck fica com a de {lista}. "
                       f"Se for mesmo a evolucao do deck: py my_decks.py aceitar \"{nome}\"")
        # --- troca de arquétipo ---------------------------------------------
        if n_troc > TROCA_DE_ARQUETIPO:
            avisar("alta", nome, f"{n_troc} cartas trocadas de uma vez",
                   f"de {anterior} para {lista}: nao e a lista a evoluir, e outro deck — "
                   "o emparelhador trocou de arquetipo. Ver se a assinatura ainda separa o deck.")
        # --- oscilação: voltou a uma lista que já tinha deixado --------------
        for t in trocas:
            para = _contar(json.loads(t["para_cartas"] or "[]"))
            for velha in _trocas(con, "WHERE deck = ? AND formato = ? AND corrida >= ? "
                                      "AND corrida < ? AND motivo = 'troca'",
                                 (nome, fmt, limite_oscila, hoje)):
                if _sobreposicao(para, _contar(json.loads(velha["de_cartas"] or "[]"))) \
                        >= SOBREPOSICAO_OSCILA:
                    avisar("media", nome,
                           f"voltou a uma lista como a de {rotulo(velha['de_jogador'], velha['de_data'])}",
                           f"deixada a {velha['corrida'][8:10]}/{velha['corrida'][5:7]}: o deck anda "
                           "a saltar entre dois arquetipos que a assinatura nao separa.")
                    break
        # --- a carta que lhe dá o nome --------------------------------------
        if cartas:
            for c in cartas_do_nome(nome, s["assinatura"]):
                agora = sum(q for (_b, n), q in cartas.items() if n == c)
                if agora == 0:
                    avisar("alta", nome, f"a lista deixou de jogar {c}",
                           f"um deck chamado {nome} que nao joga {c} nao e o deck.")
                    continue
                for t in trocas:
                    antes = sum(q for (_b, n), q in
                                _contar(json.loads(t["de_cartas"] or "[]")).items() if n == c)
                    if antes > agora:
                        avisar("media", nome, f"{c}: {antes} -> {agora}",
                               "a carta que da nome ao deck desceu de copias nesta troca.")
        # --- lista incompleta -----------------------------------------------
        if cartas:
            if fmt in sources.COMMANDER_FORMATS:
                if main != 100:
                    avisar("media", nome, f"{main} cartas, nao 100",
                           "a lista de referencia foi lida incompleta.")
            else:
                if main < 60:
                    avisar("media", nome, f"main com {main} cartas, nao 60",
                           "a lista de referencia foi lida incompleta, ou a fonte publicou-a assim.")
                if side < 15:
                    avisar("media", nome, f"sideboard com {side} cartas, nao 15",
                           "a lista de referencia foi lida incompleta, ou a fonte publicou-a assim.")
        # --- lista velha ----------------------------------------------------
        if nota.get("data"):
            dias = (date.fromisoformat(hoje) - date.fromisoformat(nota["data"])).days
            if dias > DIAS_LISTA_VELHA:
                avisar("baixa", nome, f"lista de referencia com {dias} dias",
                       f"a mais recente que serve este deck e de {lista}.")
        # --- releitura ------------------------------------------------------
        for t in hoje_trocas:
            if t["motivo"] != "releitura":
                continue
            d = diferencas(json.loads(t["de_cartas"] or "[]"), json.loads(t["para_cartas"] or "[]"))
            ganho = sum(x for _b, _n, x in d)
            avisar("baixa", nome, f"lista relida: {ganho:+d} cartas",
                   "a mesma lista, relida da fonte — a leitura antiga perdia as copias de uma "
                   "carta partida em varias entradas: " + ", ".join(
                       f"{n} {x:+d}" for _b, n, x in d))

    avisos.sort(key=lambda a: (GRAVIDADES.index(a["gravidade"]), a["deck"], a["aviso"]))
    for i, a in enumerate(avisos):
        a["id"] = f"{i:03d}"
    avisos = [{k: a[k] for k in CAMPOS["avisos.json"]} for a in avisos]
    return {"alteracoes.json": alts, "estado-decks.json": estado, "avisos.json": avisos}


def _escrever_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=".tmp-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, caminho)


def escrever(con, raiz: Path | None = None, hoje: str | None = None) -> dict:
    """Escreve os três ficheiros do dia e o `historico/<hoje>.json`. Devolve as
    contagens, para o `daily` dizer o que ficou escrito."""
    hoje = hoje or date.today().isoformat()
    p = pasta(raiz)
    dados = construir(con, hoje)
    for nome, linhas in dados.items():
        _escrever_json(p / nome, linhas)
    _escrever_json(p / "historico" / f"{hoje}.json", dados["alteracoes.json"])
    av = dados["avisos.json"]
    return {"pasta": str(p), "alteracoes": len(dados["alteracoes.json"]),
            "decks_alterados": len({(a["deck"], a["formato"]) for a in dados["alteracoes.json"]}),
            "decks": len(dados["estado-decks.json"]),
            "mudaram": sum(1 for e in dados["estado-decks.json"] if e["mudou"] == "sim"),
            "avisos": {g: sum(1 for a in av if a["gravidade"] == g) for g in GRAVIDADES}}


def texto(r: dict) -> str:
    a = r["avisos"]
    return (f"{r['alteracoes']} linhas de alteracao em {r['decks_alterados']} decks "
            f"({r['mudaram']} dos {r['decks']} seguidos trocaram de lista); "
            f"avisos {a['alta']} alta / {a['media']} media / {a['baixa']} baixa -> {r['pasta']}")
