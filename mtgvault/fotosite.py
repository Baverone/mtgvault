"""TIRAR AS FOTOS DAS CARTAS DIRECTAMENTE DO SITE, NO TELEMÓVEL (André,
2026-09-21, à letra):

    *"é possível ter o site preparado para eu abrir no telefone e tirar as
    fotos directamente do site?"*  — e, no mesmo dia — *"e guardares as fotos,
    claro"*

Até aqui o fluxo da REVALIDAÇÃO (`revalidacao.py`, 2026-09-20) era: carregar
em «Fotografar esta caixa», tirar as fotos com a app da câmara, e depois
levá-las à mão para `pendentes/` (app do GitHub, ou o PC). O botão dizia o que
fotografar e o `esperadas.md` dizia ao Claude das fotos o que esperar — mas
entre a caixa na mão e a pasta havia três passos que não eram do vault. Agora
a câmara abre a partir da PRÓPRIA PÁGINA (um `<input type="file"
accept="image/*" capture="environment" multiple>`, como o da foto da deckbox)
e a foto vai pelo `POST /api/foto` (com token, `multipart/form-data`, uma ou
várias) para a RAIZ de `pendentes/` — exactamente onde o `mtg-fotos-novas`
(`ai-pc/tasks/mtg-fotos-novas/run.py`, que NÃO se alterou) as vai buscar.

O QUE ESTE MÓDULO DECIDE
------------------------
  * **O NOME diz a origem**: `site-<slot>-<AAAAMMDD-HHMMSS>-<n>.jpg` para a
    caixa `<slot>`, `site-venda-…`, `site-rl-…`, `site-colecao-…` para os
    outros três alvos da revalidação; e, quando a foto foi pedida pelo 📷 de
    UMA carta, `…-c<copy_id>.jpg` com a cópia esperada. É por este nome que
    (a) o `PROCESSAR_FOTOS.md` dá ao Claude das fotos a pista de que caixa é,
    (b) o `import_csv` (passo (0) da revalidação) prefere as cópias dessa
    caixa — e essa cópia — sem depender do alvo global do config, e (c) a
    página diz «à espera» ao lado de cada foto que ele enviou. `origem()` é o
    inverso de `nome_ficheiro()`, e tem teste nos dois sentidos.
  * **A foto guarda-se TAL COMO VEIO, inteira** (`guardar`): é ela que fica
    ligada à cópia (`copies.photo_path`) e que vai para «fotos processadas»,
    e nunca se apaga nem se reduz — a regra de todas as fotos do vault
    (2026-09-08). Valida-se pelos PRIMEIROS BYTES (`fotocaixa.tipo_da_imagem`),
    nunca pelo nome; o que não é imagem recusa-se — e recusa-se o PEDIDO
    inteiro ANTES do primeiro ficheiro tocado, para «3 guardadas, 1 recusada»
    não obrigar a adivinhar qual. Escrita atómica (temporário + `os.replace`):
    o `mtg-fotos-novas` lista a pasta e não pode apanhar meia foto — e, de
    qualquer maneira, espera que a foto tenha mais de 2 minutos (`ESPERA_S`).
  * **«⚡ Processar agora»** (`pedir_processamento`) escreve uma ordem
    `command` na inbox do runner do ai-pc (`inbox/mtgvault-fotos-<data>.json`,
    atómica) que corre `py runner.py run mtg-fotos-novas` — o MESMO programa
    das 02:30, nem mais nem menos. Com `nao_antes` = a foto mais recente + 2
    minutos: sem isso o runner apanhava a ordem em 30 s, a tarefa dizia «fotos
    a chegar — espera» e não fazia nada, e ele ficava a olhar para uma página
    que prometia processar. No máximo UMA ordem por `INTERVALO_S` (5 min), e
    se já houver uma na inbox diz-se «já está a processar». Não se corre o
    Claude local de nenhuma outra forma a partir do 8771.
  * **O que ficou por resolver** (`por_resolver`): as linhas paradas dos
    `recat-<data>-resultado.csv` cuja foto ainda está em `pendentes/` — a
    foto que o import não conseguiu ligar/importar fica lá (é a regra do
    `arrumar_fotos`) e a página mostra-a com o motivo, para ele voltar a
    fotografar em vez de esperar por uma corrida que vai dar o mesmo.

Só no 8771: o site publicado é estático e não tem onde receber uma foto.
"""
from __future__ import annotations

import datetime as _dt
import email.parser
import email.policy
import json
import os
import re
import time
from pathlib import Path

from . import fotocaixa
from .fotocaixa import FotoInvalida, MAX_BYTES, tipo_da_imagem

PREFIXO = "site"
TIPOS = ("caixa", "venda", "rl", "coleccao")
# O que vai no nome para cada alvo que não é caixa (uma caixa vai pelo slot).
_NOME_TIPO = {"venda": "venda", "rl": "rl", "coleccao": "colecao"}
_TIPO_NOME = {v: k for k, v in _NOME_TIPO.items()}
# Quantas fotos num pedido, e quanto pode pesar o pedido inteiro (o telemóvel
# manda várias de 3–5 MB de uma vez).
MAX_FICHEIROS = 30
MAX_PEDIDO = 150 * 1024 * 1024
# O `mtg-fotos-novas` só pega numa foto com mais de 2 minutos (`run.py`: «fotos
# ainda a ser copiadas esperam pela próxima corrida»). A ordem «processar agora»
# marca-se para depois disso, com uma folga para o relógio.
ESPERA_S = 120
FOLGA_S = 15
# Uma ordem de processamento por 5 minutos, no máximo.
INTERVALO_S = 300
PREFIXO_ORDEM = "mtgvault-fotos-"
# O que a ordem corre — o mesmo que a tarefa das 02:30, no `cwd` do ai-pc.
TAREFA = "mtg-fotos-novas"
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

_NOME = re.compile(
    rf"^{PREFIXO}-(?P<origem>.+?)-(?P<data>\d{{8}}-\d{{6}})-(?P<n>\d+)"
    r"(?:-c(?P<copy>\d+))?\.(?P<ext>jpe?g|png|webp|heic|heif)$", re.IGNORECASE)
_ORDEM = re.compile(rf"^{re.escape(PREFIXO_ORDEM)}(\d{{8}}-\d{{6}})(?:-\d+)?\.json$")


def pasta_pendentes(raiz: Path | None = None) -> Path:
    """A RAIZ de `pendentes/` — onde o `mtg-fotos-novas` procura (a subpasta
    `deckboxes/` é outra coisa: a foto da caixa de plástico)."""
    return Path(raiz or fotocaixa.RAIZ) / "pendentes"


# Os testes apontam a inbox para uma pasta temporária (como o `fotocaixa.RAIZ`).
INBOX: Path | None = None


def pasta_inbox(raiz_aipc: Path | None = None) -> Path:
    """A inbox do runner do ai-pc: `AIPC_ROOT/inbox`, por omissão
    `~/Desktop/ai-pc/inbox` (é onde vive neste PC)."""
    if raiz_aipc is None and INBOX is not None:
        return Path(INBOX)
    base = Path(raiz_aipc or os.environ.get("AIPC_ROOT")
                or Path.home() / "Desktop" / "ai-pc")
    return base / "inbox"


# ---------------------------------------------------------------------------
# O nome diz a origem
# ---------------------------------------------------------------------------
def nome_ficheiro(tipo: str, slot: str | None, quando: _dt.datetime, n: int,
                  ext: str, copy_id: int | None = None) -> str:
    """`site-<slot|venda|rl|colecao>-<AAAAMMDD-HHMMSS>-<n>[-c<copy_id>].<ext>`."""
    if tipo not in TIPOS:
        raise FotoInvalida(f"alvo {tipo!r} desconhecido ({'/'.join(TIPOS)})")
    if tipo == "caixa":
        if not slot or not re.fullmatch(r"[A-Za-z0-9_-]+", slot):
            raise FotoInvalida("uma foto de caixa precisa do slot")
        if slot in _TIPO_NOME:
            raise FotoInvalida(f"o slot {slot!r} confunde-se com um alvo da revalidação")
        origem = slot
    else:
        origem = _NOME_TIPO[tipo]
    return (f"{PREFIXO}-{origem}-{quando:%Y%m%d-%H%M%S}-{n}"
            + (f"-c{int(copy_id)}" if copy_id else "") + f".{ext}")


def origem(nome: str) -> dict | None:
    """O inverso: `{tipo, slot, quando, n, copy_id}` — ou `None` para uma foto
    que não veio do site (largada à mão em `pendentes/`)."""
    m = _NOME.match(Path(str(nome or "")).name)
    if not m:
        return None
    o = m.group("origem")
    tipo = _TIPO_NOME.get(o, "caixa")
    try:
        quando = _dt.datetime.strptime(m.group("data"), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return {"tipo": tipo, "slot": o if tipo == "caixa" else None,
            "quando": quando.isoformat(sep=" "), "n": int(m.group("n")),
            "copy_id": int(m.group("copy")) if m.group("copy") else None}


# ---------------------------------------------------------------------------
# O corpo do pedido: multipart/form-data
# ---------------------------------------------------------------------------
def ler_multipart(content_type: str, corpo: bytes) -> list[dict]:
    """As partes com ficheiro de um `multipart/form-data`: `[{campo, nome,
    dados}]`. Pelo `email` da biblioteca-padrão — o `cgi` saiu do Python e uma
    dependência nova para ler um formulário paga-se todos os dias."""
    ct = (content_type or "").strip()
    if not ct.lower().startswith("multipart/form-data"):
        raise FotoInvalida("o pedido tem de ser multipart/form-data (o formulário "
                           "da página) — veio " + (ct.split(";")[0] or "sem tipo"))
    msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
        b"Content-Type: " + ct.encode("latin-1", "replace") + b"\r\n"
        b"MIME-Version: 1.0\r\n\r\n" + corpo)
    if not msg.is_multipart():
        raise FotoInvalida("o multipart veio sem partes (fronteira em falta?)")
    out = []
    for parte in msg.iter_parts():
        nome = parte.get_filename()
        if nome is None:
            continue                       # um campo de texto, não um ficheiro
        dados = parte.get_payload(decode=True) or b""
        out.append({"campo": parte.get_param("name", header="content-disposition") or "",
                    "nome": Path(str(nome)).name, "dados": dados})
    return out


# ---------------------------------------------------------------------------
# Guardar: tal como veio, inteira, na raiz de pendentes/
# ---------------------------------------------------------------------------
def _escrever(destino: Path, dados: bytes) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(dados)
    os.replace(tmp, destino)


def guardar(pasta: Path, tipo: str, ficheiros: list[dict], *, slot: str | None = None,
            copy_id: int | None = None, quando: _dt.datetime | None = None) -> list[dict]:
    """Grava cada foto de `ficheiros` (`[{nome, dados}]`) em `pasta` com o nome
    de `nome_ficheiro`. Valida TUDO antes de escrever o primeiro: um pedido
    com um ficheiro que não é imagem recusa-se inteiro (409 na página), sem
    metade das fotos já na pasta. Devolve `[{nome, bytes, ext, original}]`."""
    if not ficheiros:
        raise FotoInvalida("o pedido não trouxe nenhuma foto")
    if len(ficheiros) > MAX_FICHEIROS:
        raise FotoInvalida(f"{len(ficheiros)} fotos num pedido — o máximo é {MAX_FICHEIROS}; "
                           f"manda em duas vezes")
    validas = []
    for f in ficheiros:
        dados = f.get("dados") or b""
        nome = f.get("nome") or "?"
        if not dados:
            raise FotoInvalida(f"{nome}: veio vazio")
        if len(dados) > MAX_BYTES:
            raise FotoInvalida(f"{nome}: {len(dados) / 1e6:.1f} MB — o máximo por foto é "
                               f"{MAX_BYTES // (1024 * 1024)} MB")
        ext = tipo_da_imagem(dados)
        if ext is None:
            raise FotoInvalida(f"{nome}: isto não é uma imagem (JPEG, PNG, WebP ou HEIC)")
        validas.append((nome, dados, ext))
    quando = quando or _dt.datetime.now().replace(microsecond=0)
    # O `n` salta o que já lá está com o mesmo segundo — dois pedidos no mesmo
    # segundo (o telemóvel manda várias) não se pisam.
    nome_ficheiro(tipo, slot, quando, 1, "jpg", copy_id)        # valida tipo/slot antes de escrever
    existentes = {p.stem for p in pasta.glob(f"{PREFIXO}-*")} if pasta.is_dir() else set()
    out, n = [], 0
    for nome, dados, ext in validas:
        while True:
            n += 1
            novo = nome_ficheiro(tipo, slot, quando, n, ext, copy_id)
            if Path(novo).stem not in existentes:
                break
        _escrever(pasta / novo, dados)
        existentes.add(Path(novo).stem)
        out.append({"nome": novo, "bytes": len(dados), "ext": ext, "original": nome})
    return out


# ---------------------------------------------------------------------------
# O que está à espera, e o que ficou por resolver
# ---------------------------------------------------------------------------
def _fotos(pasta: Path) -> list[Path]:
    if not pasta.is_dir():
        return []
    return sorted((p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXTS),
                  key=lambda p: (-p.stat().st_mtime, p.name))


def enviadas(pasta: Path, agora: float | None = None) -> list[dict]:
    """As fotos na raiz de `pendentes/` (do site e as largadas à mão), da mais
    recente para a mais antiga: `{nome, bytes, em, idade_s, pronta, origem}`.
    `pronta` = o `mtg-fotos-novas` já lhe pega (mais de `ESPERA_S`)."""
    agora = time.time() if agora is None else agora
    out = []
    for p in _fotos(pasta):
        st = p.stat()
        idade = max(0, int(agora - st.st_mtime))
        out.append({"nome": p.name, "bytes": st.st_size,
                    "em": _dt.datetime.fromtimestamp(st.st_mtime).isoformat(sep=" ", timespec="seconds"),
                    "idade_s": idade, "pronta": idade > ESPERA_S, "origem": origem(p.name)})
    return out


def por_resolver(pasta: Path) -> list[dict]:
    """As linhas paradas (`resultado != importada`) dos `recat-*-resultado.csv`
    cuja foto AINDA está em `pendentes/` — para cada foto, o resultado mais
    recente que a nomeia. `[{foto, resultado, linhas: [{name, set_code,
    motivo}]}]`. Uma foto que já não está na pasta resolveu-se (ou foi-se) e
    não se lista."""
    import csv                                             # noqa: PLC0415
    if not pasta.is_dir():
        return []
    presentes = {p.name for p in _fotos(pasta)}
    por_foto: dict[str, dict] = {}
    for f in sorted(pasta.glob("recat-*-resultado.csv")):     # o mais recente ganha
        try:
            with f.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except (OSError, csv.Error):
            continue
        for r in rows:
            foto = Path((r.get("photo_path") or "").strip()).name
            if not foto or foto not in presentes:
                continue
            g = por_foto.setdefault(foto, {"foto": foto, "resultado": f.name, "linhas": []})
            if g["resultado"] != f.name:
                g["resultado"], g["linhas"] = f.name, []
            if (r.get("resultado") or "") != "importada":
                g["linhas"].append({"name": r.get("name") or "", "set_code": r.get("set_code") or "",
                                    "motivo": r.get("motivo") or ""})
    return [g for g in por_foto.values() if g["linhas"]]


def ordens(inbox: Path) -> list[dict]:
    """As ordens `mtgvault-fotos-*.json` do runner: as pendentes (na inbox) e
    as já corridas (`inbox/done/`), com a data do nome."""
    out = []
    for pasta, estado in ((inbox, "pendente"), (inbox / "done", "feita"),
                          (inbox / "cancelados", "cancelada")):
        if not pasta.is_dir():
            continue
        for p in pasta.glob(f"{PREFIXO_ORDEM}*.json"):
            m = _ORDEM.match(p.name)
            if not m:
                continue
            try:
                quando = _dt.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
            except ValueError:
                continue
            nao_antes = None
            if estado == "pendente":
                try:
                    nao_antes = json.loads(p.read_text(encoding="utf-8")).get("nao_antes")
                except (OSError, ValueError):
                    pass
            out.append({"nome": p.name, "estado": estado, "em": quando.isoformat(sep=" "),
                        "nao_antes": nao_antes})
    return sorted(out, key=lambda o: o["em"], reverse=True)


def estado(pasta: Path, inbox: Path | None = None, agora: float | None = None) -> dict:
    """Tudo o que a aba «📷 Revalidação» mostra sobre as fotos do site: as
    fotos à espera, as por resolver, e onde está o «processar agora»."""
    agora = time.time() if agora is None else agora
    env = enviadas(pasta, agora)
    ords = ordens(inbox if inbox is not None else pasta_inbox())
    pend = next((o for o in ords if o["estado"] == "pendente"), None)
    ultima = next((o for o in ords if o["estado"] != "pendente"), None)
    return {"enviadas": env, "n": sum(1 for e in env), "prontas": sum(1 for e in env if e["pronta"]),
            "por_resolver": por_resolver(pasta), "espera_s": ESPERA_S, "intervalo_s": INTERVALO_S,
            "processar": {"pendente": pend, "ultima": ultima}}


# ---------------------------------------------------------------------------
# «⚡ Processar agora»: uma ordem na inbox do runner
# ---------------------------------------------------------------------------
def pedir_processamento(pasta: Path, inbox: Path, *, agora: _dt.datetime | None = None,
                        raiz_aipc: Path | None = None) -> dict:
    """Escreve `inbox/mtgvault-fotos-<AAAAMMDD-HHMMSS>.json` com a ordem
    `command` que corre o `mtg-fotos-novas` — atomicamente (tmp + rename; o
    runner lê a inbox de 30 em 30 s). Devolve `{escrita, ordem, nao_antes,
    msg}`; `escrita=False` quando não se escreveu, com o porquê no `msg`:
    sem fotos, uma ordem já pendente, ou menos de `INTERVALO_S` desde a
    última."""
    agora = agora or _dt.datetime.now().replace(microsecond=0)
    fotos = enviadas(pasta, agora.timestamp())
    if not fotos:
        return {"escrita": False, "ordem": None, "nao_antes": None,
                "msg": "Não há fotos em pendentes\\ por processar."}
    ords = ordens(inbox)
    pend = next((o for o in ords if o["estado"] == "pendente"), None)
    if pend:
        return {"escrita": False, "ordem": pend["nome"], "nao_antes": pend["nao_antes"],
                "msg": "Já está a processar: a ordem " + pend["nome"] + " está na inbox do runner"
                       + (f" (corre a partir das {pend['nao_antes'][11:16]})"
                          if pend["nao_antes"] else "") + "."}
    ultima = next((o for o in ords if o["estado"] != "pendente"), None)
    if ultima:
        passou = (agora - _dt.datetime.fromisoformat(ultima["em"])).total_seconds()
        if passou < INTERVALO_S:
            falta = int(INTERVALO_S - passou)
            return {"escrita": False, "ordem": ultima["nome"], "nao_antes": None,
                    "msg": f"A última ordem foi há {int(passou // 60)} min — no máximo uma por "
                           f"{INTERVALO_S // 60} min; tenta daqui a {max(1, (falta + 59) // 60)} min."}
    # A tarefa só pega em fotos com mais de 2 min: a ordem espera pela mais nova.
    mais_nova = max(_dt.datetime.fromisoformat(f["em"]) for f in fotos)
    nao_antes = max(agora, mais_nova + _dt.timedelta(seconds=ESPERA_S + FOLGA_S))
    cwd = str(Path(raiz_aipc) if raiz_aipc else inbox.parent)
    ordem = {"kind": "command", "command": ["py", "runner.py", "run", TAREFA], "cwd": cwd,
             "timeout": 1800, "nao_antes": nao_antes.isoformat(sep=" "),
             "origem": "mtgvault 8771: «Processar agora» na Deckboxes",
             "fotos": [f["nome"] for f in fotos]}
    inbox.mkdir(parents=True, exist_ok=True)
    nome = f"{PREFIXO_ORDEM}{agora:%Y%m%d-%H%M%S}.json"
    destino = inbox / nome
    k = 1
    while destino.exists():
        k += 1
        destino = inbox / f"{PREFIXO_ORDEM}{agora:%Y%m%d-%H%M%S}-{k}.json"
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text(json.dumps(ordem, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, destino)
    espera = int((nao_antes - agora).total_seconds())
    return {"escrita": True, "ordem": destino.name, "nao_antes": ordem["nao_antes"],
            "msg": (f"Ordem escrita: o runner corre o {TAREFA} "
                    + (f"às {nao_antes:%H:%M} (a foto mais recente tem de ter mais de "
                       f"{ESPERA_S // 60} min)" if espera > 5 else "dentro de ~30 s")
                    + f" — {len(fotos)} foto{'s' if len(fotos) != 1 else ''}. O Claude local lê as "
                    f"fotos e importa; demora uns minutos. Recarrega depois.")}


# ---------------------------------------------------------------------------
# `pendentes/esperadas.md`: a secção das fotos do site
# ---------------------------------------------------------------------------
def seccao_esperadas(con, pasta: Path) -> list[str]:
    """As linhas do `esperadas.md` para as fotos que vieram do site: cada nome
    com a caixa que o prefixo indica e, com `c<copy_id>`, a cópia esperada
    (nome + impressão). Vazio sem fotos do site."""
    fotos = [e for e in enviadas(pasta) if e["origem"]]
    if not fotos:
        return []
    from . import loadout, revalidacao                     # noqa: PLC0415
    nomes = loadout.nomes_das_caixas()
    out = [f"## Fotos tiradas no site ({len(fotos)})",
           "Estas fotos foram tiradas na Deckboxes, no telemóvel, e o NOME diz de onde: "
           f"`{PREFIXO}-<caixa>-…` é a caixa que ele estava a fotografar (ou `venda`/`rl`/"
           "`colecao`), e `-c<copy_id>` é a CÓPIA esperada nessa foto. É uma pista, não uma "
           "resposta: escreve o que VÊS na foto, com o `photo_path` — o import prefere as "
           "cópias dessa caixa (e essa cópia) ao ligar a foto."]
    for e in fotos:
        o = e["origem"]
        if o["tipo"] == "caixa":
            onde = "caixa " + (nomes.get(o["slot"]) or o["slot"])
        else:
            onde = revalidacao.TITULO.get(o["tipo"], o["tipo"])
        linha = f"- `{e['nome']}` — {onde}"
        if o["copy_id"]:
            r = con.execute(
                """SELECT c.name, c.set_code, c.collector_number, cp.finish, cp.language, cp.quantity
                     FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                    WHERE cp.id = ?""", (o["copy_id"],)).fetchone()
            linha += (f" · cópia #{o['copy_id']}: {r['quantity']}× **{r['name']}** — "
                      f"{revalidacao.impressao(r)}" if r else f" · cópia #{o['copy_id']} (já não existe)")
        out.append(linha)
    out.append("")
    return out
