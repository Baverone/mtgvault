"""MODO EDIÇÃO do mtgvault: servidor local que serve as páginas e ESCREVE.

    python webapp.py        →  http://localhost:8771/

**Porto 8771, não 8770** — o 8770 é do riftvault (`riftvault serve`). Os dois
correm no mesmo PC e ficariam a disputar o porto; quem perdesse morria no
arranque com um "address already in use" e não voltava a subir. Se mudares um,
muda a tarefa `ai-pc/tasks/mtgvault-serve/` também.

O que faz de diferente do site publicado
----------------------------------------
Serve a **mesma** página `deckboxes.html` — o mesmo ficheiro, o mesmo JavaScript,
os mesmos números — com um flag `editable: true` no payload. É esse flag que faz
aparecer os botões:

  * **Tornar permanente / Deixar de ser permanente** — *"os decks que eu estiver
    quase a concluir, tenho que ter uma opção que os marque como permanentes
    para começarem a receber alocação de cartas"* (André, 2026-09-07);
  * **Subir / Descer** — a prioridade DENTRO do grupo de formato;
  * **Sleevado e na caixa / Tirar da caixa** — regista que as cartas daquela
    caixa estão fisicamente lá dentro;
  * **Já arrumei tudo** (na aba Arrumar) — grava a alocação inteira.

Duas páginas diferentes divergem em silêncio: é a razão de o frontend ser um só
(a lição do riftvault, que serve o mesmo `app.js` nos dois modos).

Onde fica a verdade
-------------------
**No `colecao_config.json`.** Os botões escrevem lá — não numa tabela
`deck_meta` paralela. Razões, por ordem de peso:

  1. o `loadout` já vive lá e é ele que manda em toda a alocação. Uma segunda
     fonte para a mesma coisa é exactamente o padrão do `event_tier`: duas
     opiniões, nenhum erro, páginas erradas em silêncio;
  2. o config vai no Git, por isso "tornei o Legacy permanente" fica no
     histórico e viaja para o GitHub Actions. A `vault.db` não vai no Git (vive
     num Release) e uma escolha dele podia perder-se na próxima publicação;
  3. dá para editar à mão quando o servidor não está a correr, que é como
     sempre se fez.

O que vai para a base de dados é só o que é **físico**: a `copy_allocation` (que
cartas estão dentro de que caixa) e as cópias que ele vende (o botão *"vendida"*
tira-as da `copies` e escreve-as no `data/vendas.csv`). Isso não é uma
preferência, é o estado da estante — e não cabe num ficheiro de configuração.

NO TELEMÓVEL, EM CASA (André, 2026-09-08)
-----------------------------------------
*"Ele vai estar à frente da estante com o telemóvel."* Por isso o servidor pode
ouvir na rede local — `MTGVAULT_BIND=0.0.0.0` — e a página de arranque mostra um
**QR** com o link já com o token. A predefinição continua a ser `127.0.0.1`:
abrir um porto que escreve na base é uma decisão, não um efeito secundário de
actualizar o vault.

O **token** (`data/webapp.token`, fora do Git, gerado uma vez) é o que separa as
duas coisas:

  * **ler** funciona sempre — a página é a mesma do site publicado, sem botões;
  * **escrever** exige o token. Sem ele, `403`. O token viaja no link do QR
    (`?t=...`) e a página só o guarda dentro de si quando o pedido que a foi
    buscar já o trazia — senão bastava abri-la para o descobrir.

Os pedidos de `127.0.0.1` são de confiança sem token: quem está no PC já tem os
ficheiros à frente, e pedir-lhe uma senha não protege nada. Continua a não ser
para abrir no router.
"""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import caixas, configio, db, loadout, migracao, qr, sources  # noqa: E402

import deckboxes  # noqa: E402
import metagame  # noqa: E402

PORT = 8771          # o 8770 é do riftvault — ver o cabeçalho
# Onde ouvir. `127.0.0.1` por omissão: só este PC. `0.0.0.0` para o telemóvel
# chegar lá (é o que a tarefa `ai-pc/tasks/mtgvault-serve` define).
BIND = os.environ.get("MTGVAULT_BIND") or "127.0.0.1"
# Serializa TODAS as escritas (config + base de dados). Ver `do_POST`.
ESCRITA = threading.Lock()
CABECALHO_TOKEN = "X-Mtgvault-Token"


def config_path() -> Path:
    return configio.caminho()


CONFIG = config_path()
UMA_LINHA = configio.UMA_LINHA
# As páginas que o modo edição GERA em vez de servir do disco: são as que têm
# botões, e o `editable` é o que os faz aparecer. Servir o ficheiro estático a
# partir daqui dava uma página sem botões e sem explicação nenhuma.
PAGINAS_EDITAVEIS = {"/": deckboxes, "/index.html": deckboxes,
                     "/deckboxes.html": deckboxes, "/metagame.html": metagame}


# ---------------------------------------------------------------------------
# Config: ler, mexer, gravar sem estragar a formatação (ver `mtgvault.configio`)
# ---------------------------------------------------------------------------
def ler_config(path: Path | None = None) -> dict:
    """O config, sempre já no formato **v6** (`caixas`).

    Migra em memória quando encontra um ficheiro da v5, para o primeiro clique
    dele não rebentar num config que ninguém converteu — e, como toda a escrita
    passa por aqui, esse clique também deixa o ficheiro no formato novo. É o que
    faz o *"o webapp escreve só no formato novo"* ser verdade sem exigir que a
    migração corra primeiro.
    """
    return caixas.migrar_config(configio.ler(path))[0]


def escrever_config(cfg: dict, path: Path | None = None) -> None:
    """Grava o config e **esquece a cache** de quem o lê.

    O `sources.config()` guarda o ficheiro em cache pelo mtime, e o Windows dá
    mtimes com pouca resolução: gravar e voltar a ler no mesmo instante podia
    devolver a versão de antes do clique. Aqui, a seguir a cada escrita, corre
    logo a alocação — e ela tem de ver o que ele acabou de mudar.
    """
    configio.escrever(cfg, path)
    sources._CFG_CACHE.clear()


# ---------------------------------------------------------------------------
# Token: quem pode escrever
# ---------------------------------------------------------------------------
def ficheiro_token() -> Path:
    """`data/webapp.token` — ao lado da base, e não no repositório: é um segredo
    desta máquina e não uma preferência que viaje no Git."""
    return Path(db.ROOT) / "webapp.token"


def token(criar: bool = True) -> str:
    """O token deste PC. Gera-se uma vez e fica — muda-se apagando o ficheiro."""
    p = ficheiro_token()
    if p.exists():
        t = p.read_text(encoding="utf-8").strip()
        if t:
            return t
    if not criar:
        return ""
    t = secrets.token_hex(16)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t + "\n", encoding="utf-8")
    return t


def token_valido(dado: str | None) -> bool:
    esperado = token(criar=False)
    return bool(dado) and bool(esperado) and secrets.compare_digest(dado, esperado)


def _peers(con, cfg, slot_id):
    """Os slots que o `prioridade` deste ordena — os do mesmo grupo, com o mesmo
    estado de permanente e de vigiado, pela ordem real da alocação.

    Fora deste conjunto o `prioridade` não decide nada: quem manda é o grupo de
    formato, o "permanente" e o "é deck vigiado", por essa ordem. Subir um slot
    de Premodern acima de um permanente de cEDH não é um número — é mudar o
    `regras_por_formato`, e o botão diz isso em vez de fingir que fez algo.
    """
    resolvidos = loadout.resolve_slots(con, caixas.do_config(cfg))
    alvo = next((s for s in resolvidos if s["slot"] == slot_id), None)
    if alvo is None:
        return None, []
    chave = (alvo["permanente"], alvo["grupo_ordem"], alvo["vigiado"])
    return alvo, [s for s in resolvidos
                  if (s["permanente"], s["grupo_ordem"], s["vigiado"]) == chave]


def mover(con, cfg, slot_id, delta) -> str:
    """Sobe (-1) ou desce (+1) um slot dentro do grupo. Devolve uma frase."""
    alvo, pares = _peers(con, cfg, slot_id)
    if alvo is None:
        return "esse slot não existe"
    if len(pares) < 2:
        return f"{alvo['nome']} é o único do grupo — não há por onde mexer"
    i = [s["slot"] for s in pares].index(slot_id)
    j = i + delta
    if not 0 <= j < len(pares):
        return (f"{alvo['nome']} já é o {'primeiro' if delta < 0 else 'último'} "
                f"do grupo {alvo['grupo']}")
    ordem = [s["slot"] for s in pares]
    ordem[i], ordem[j] = ordem[j], ordem[i]
    # Renumera o grupo de 1 a n: com números repetidos ou saltados no config, um
    # swap simples não mexia em nada. É a mesma armadilha dos catorze números à
    # mão que a ordem por grupo veio resolver.
    posicao = {s: n for n, s in enumerate(ordem, 1)}
    for s in cfg["caixas"]:
        if s["slot"] in posicao:
            s["prioridade"] = posicao[s["slot"]]
    return f"{alvo['nome']} {'subiu' if delta < 0 else 'desceu'} no grupo {alvo['grupo']}"


# ---------------------------------------------------------------------------
# "Vou montar este": escolher o deck de uma caixa a partir do top-N
# ---------------------------------------------------------------------------
# As chaves da caixa que a escolha mexe — e por isso as que o `desmarcar` repõe.
CHAVES_DA_ESCOLHA = ("fonte", "ref", "nome", "estado")

_slot_do_cfg = caixas.caixa_do_cfg


def escolher_lista(con, cfg, slot_id: str, aid: int) -> str:
    """*"Vou montar este"*: fixa na caixa a lista de consenso de um arquétipo.

    André, 2026-09-07 (19:00): ele vê o top-3 que está mais perto de concluir e
    marca qual vai montar. A lista fica **congelada com a data** em
    `colecao_config.json → listas_escolhidas` — se o consenso do arquétipo mudar
    amanhã, a caixa que ele mandou montar não muda debaixo dos pés, nem a lista
    de compras dela. E a caixa passa a **permanente**: é o que a põe a receber
    cartas na alocação.

    O que estava lá antes (o Greasefang do Pioneer, por exemplo) fica guardado em
    `_antes` — a chave começa por `_`, por isso o motor não a vê
    (`loadout.config_slots`) e o *"já não vou montar este"* pode desfazer.
    """
    import meta_coverage as mc

    from mtgvault import stock

    sl = stock.stock_list(con, aid)
    cards = [[b, c["card_name"], c["quantity"]]
             for b in ("main", "side") for c in sl.get(b, [])]
    if not cards:
        return "esse arquétipo não tem lista de consenso"
    fmt = con.execute("SELECT format FROM archetypes WHERE id = ?",
                      (aid,)).fetchone()["format"]
    df, tcache = mc._format_df(con, fmt), {}
    nome = mc._name_for(con, aid, df, tcache)
    s = _slot_do_cfg(cfg, slot_id)
    cfg.setdefault("listas_escolhidas", {})[slot_id] = {
        "nome": nome,
        "subtitulo": mc._distinctive_name(con, aid, df, tcache),
        "formato": fmt,
        "archetype_id": aid,
        "n_listas": mc._n_lists(con, aid),
        "escolhido_em": date.today().isoformat(),
        "cards": cards,
    }
    # Só as chaves que EXISTIAM, para o desmarcar saber distinguir "estava a
    # `null`" de "não estava lá" — o `ref` do slot por confirmar é literalmente
    # `null`, e apagá-lo em vez de o repor deixava a caixa sem a chave.
    s.setdefault("_antes", {k: s[k] for k in CHAVES_DA_ESCOLHA if k in s})
    s["fonte"] = "escolhido"
    s["ref"] = slot_id
    s["nome"] = f'{(s.get("nome") or slot_id).split(" — ")[0]} — {nome}'
    # Escolher um deck para a caixa é pô-la a receber cartas: é isso que
    # `permanente` quer dizer. Uma caixa montada não perde esse estado por se
    # escolher outra lista para ela (é o que o «actualizar» existe para fazer).
    if caixas.estado_de(s) == caixas.CANDIDATA:
        s["estado"] = caixas.PERMANENTE
    return f"{nome} escolhido para a caixa {s['nome']}"


def desmarcar_lista(cfg, slot_id: str) -> str:
    """*"Já não vou montar este"*: devolve a caixa ao que era antes da escolha."""
    s = _slot_do_cfg(cfg, slot_id)
    antes = s.pop("_antes", None)
    (cfg.get("listas_escolhidas") or {}).pop(slot_id, None)
    if not cfg.get("listas_escolhidas"):
        cfg.pop("listas_escolhidas", None)
    if antes is None:
        return f'{s.get("nome") or slot_id} não tinha escolha para desmarcar'
    for k in CHAVES_DA_ESCOLHA:
        if k in antes:
            s[k] = antes[k]
        else:
            s.pop(k, None)
    return f'{s.get("nome") or slot_id}: escolha desfeita'


def alternar_permanente(cfg, slot_id) -> tuple[str, str]:
    """`candidata` <-> `permanente`. Devolve (estado novo, nome).

    Uma caixa **montada** não passa a candidata por aqui: está sleevada na
    estante, e desfazer isso é o botão *"tirar da caixa"* (que também apaga a
    `copy_allocation`). Dois caminhos para o mesmo estado é o que a escala de
    estados da v6 veio evitar.
    """
    s = caixas.caixa_do_cfg(cfg, slot_id)
    nome = s.get("nome") or slot_id
    actual = caixas.estado_de(s)
    if actual == caixas.MONTADA:
        return actual, nome
    s["estado"] = (caixas.CANDIDATA if actual == caixas.PERMANENTE
                   else caixas.PERMANENTE)
    return s["estado"], nome


def alternar_montada(cfg, slot_id) -> tuple[bool, str]:
    """`montada` <-> `permanente` — o *"sleevado e na caixa"* / *"tirar da caixa"*."""
    s = caixas.caixa_do_cfg(cfg, slot_id)
    montada = caixas.estado_de(s) != caixas.MONTADA
    s["estado"] = caixas.MONTADA if montada else caixas.PERMANENTE
    return montada, (s.get("nome") or slot_id)


# ---------------------------------------------------------------------------
# Escritas na base de dados (o que é FÍSICO)
# ---------------------------------------------------------------------------
def marcar_na_caixa(con, slot_id: str, dentro: bool) -> int:
    """"Sleevado e na caixa": regista as cartas desta caixa como estando lá.

    É o mesmo mecanismo do "já arrumei tudo", limitado a uma caixa. Substituiu a
    versão antiga, que reservava as cartas do BALDE do deck
    (`copies.reserved_deck_id`): no modelo de colecção única a caixa já não é um
    balde, e as cartas de uma caixa podem vir de vários sítios — os quatro Utrom
    Monitor do Pauper vêm do SPML.
    """
    if not dentro:
        n = con.execute("DELETE FROM copy_allocation WHERE slot = ?",
                        (slot_id,)).rowcount
        con.commit()
        return n
    rep = loadout.report(con)
    alvo = next((s for s in rep["slots"] if s["slot"] == slot_id), None)
    if alvo is None:
        return 0
    con.execute("DELETE FROM copy_allocation WHERE slot = ?", (slot_id,))
    linhas: dict[int, int] = {}
    for m in alvo["have"]:
        for g in m["lotes"]:
            linhas[g["id"]] = linhas.get(g["id"], 0) + g["q"]
    con.executemany(
        "INSERT INTO copy_allocation (copy_id, slot, quantity, placed_at) "
        "VALUES (?,?,?,datetime('now'))",
        [(cid, slot_id, q) for cid, q in sorted(linhas.items())])
    con.commit()
    return sum(linhas.values())


def regenerar(con) -> None:
    """Reescreve as páginas estáticas, para o site publicado acompanhar.

    Sem isto, o modo edição e o GitHub Pages diziam coisas diferentes até à
    corrida seguinte do `daily.py` — e a diferença aparecia no telemóvel dele,
    fora de casa, sem explicação nenhuma.

    São as DUAS: qualquer botão desta página muda a alocação, e a alocação é o
    que o `metagame.html` mostra (a posse do top-N e o crachá "escolhido em").
    Refazer só uma deixava a outra a dizer o contrário. Custam ~0,3 s cada.
    """
    deckboxes.build(con, ROOT / "deckboxes.html")
    metagame.build(con, ROOT / "metagame.html")


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "mtgvault"

    def _envia(self, corpo, code=200, tipo="text/html; charset=utf-8"):
        b = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        self.send_response(code)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(b)))
        # O telemóvel guardava o HTML antigo em cache e a página parecia partida
        # depois de qualquer alteração — sem erro nenhum à vista. É a mesma nota
        # que está no `riftvault/server.py`.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(b)

    def _json(self, obj, code=200):
        self._envia(json.dumps(obj, ensure_ascii=False), code,
                    "application/json; charset=utf-8")

    # -- quem pode escrever ------------------------------------------------
    def _token_do_pedido(self) -> str | None:
        u = urlparse(self.path)
        q = parse_qs(u.query).get("t")
        return self.headers.get(CABECALHO_TOKEN) or (q[0] if q else None)

    def _pode_escrever(self) -> bool:
        """Loopback é de confiança; da rede exige-se o token (ver o cabeçalho)."""
        ip = (self.client_address[0] if self.client_address else "")
        return ip in ("127.0.0.1", "::1") or token_valido(self._token_do_pedido())

    def do_GET(self):                                  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho in ("/qr.svg", "/qr"):
            # O QR do link COMPLETO (com token) da rede local. É o que ele aponta
            # com o telemóvel; escrever o URL à mão num teclado de telemóvel é
            # exactamente o atrito que faz não se usar a ferramenta.
            #
            # E por isso esta imagem TAMBÉM exige o token: um QR é um URL
            # legível: servi-lo a quem não o tem era dar-lhe o token pela porta
            # do lado, e o 403 dos `POST` deixava de valer nada. A página pede-a
            # com o `?t=` (ver `ligacaoHTML` no `deckboxes.py`).
            if not self._pode_escrever():
                self._envia("<h1>403</h1><p>o QR leva o token — não se serve a "
                            "quem não o tem.</p>", 403)
                return
            self._envia(qr.svg(url_edicao()), tipo="image/svg+xml; charset=utf-8")
            return
        modulo = PAGINAS_EDITAVEIS.get(caminho)
        if modulo is not None:
            # A página só leva o token DENTRO dela quando o pedido já o trazia —
            # senão bastava abri-la de qualquer telemóvel da rede para o
            # descobrir, e o token não protegia nada.
            editavel = self._pode_escrever()
            with db.session() as con:
                self._envia(modulo.html_page(
                    con, editable=editavel,
                    token=(token() if editavel else ""),
                    ligacao=(ligacao_local() if editavel else None)))
            return
        nome = caminho.lstrip("/")
        alvo = (ROOT / nome).resolve()
        if (nome.endswith((".html", ".css", ".js")) and alvo.is_file()
                and str(alvo).startswith(str(ROOT))):
            self._envia(alvo.read_text(encoding="utf-8"))
            return
        self._envia("<h1>404</h1><p><a href='/'>Deckboxes</a></p>", 404)

    def do_POST(self):                                 # noqa: N802
        caminho = urlparse(self.path).path
        tam = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tam).decode("utf-8") if tam else "{}"
        try:
            dados = json.loads(corpo or "{}")
        except json.JSONDecodeError:
            dados = {}
        if not self._pode_escrever():
            # Ler é livre, escrever não. Sem isto, pôr o porto na rede local
            # (MTGVAULT_BIND=0.0.0.0) dava a qualquer aparelho de casa — ou a
            # qualquer visita no Wi-Fi — o direito de lhe desmontar os decks.
            self._json({"erro": "sem token: este link é só de leitura. Abre o "
                                "link do QR (tem o ?t=) para poderes gravar."}, 403)
            return
        # UMA escrita de cada vez. O `ThreadingHTTPServer` atende os pedidos em
        # paralelo, e cada botão é um ler-mexer-gravar do `colecao_config.json`:
        # dois cliques ao mesmo tempo (ou um duplo-toque no telemóvel) faziam o
        # segundo gravar por cima do primeiro, e a alteração desaparecia sem
        # erro nenhum. O mesmo vale para a `copy_allocation`, que se apaga e
        # reescreve inteira.
        with ESCRITA:
            try:
                if caminho == "/api/arrumar":
                    with db.session() as con:
                        migracao.backup(con)
                        n = loadout.guardar_arrumacao(con, loadout.report(con))
                        regenerar(con)
                    self._json({"ok": True, "copias": n})
                    return
                if caminho == "/api/caixa":
                    self._json(self._caixa(dados))
                    return
                if caminho == "/api/escolher":
                    self._json(self._escolher(dados))
                    return
                if caminho == "/api/vender":
                    self._json(self._vender(dados))
                    return
            except KeyError as e:
                # O caso normal: um `slot` que já não existe no config (a página
                # aberta no telemóvel é de antes de ele o mudar). `repr` dava
                # `KeyError('legacy')`, que não diz nada a quem está a olhar.
                self._json({"erro": f"a caixa {e.args[0]!r} já não existe no "
                                    f"colecao_config.json — recarrega a página"}, 409)
                return
            except Exception as e:                      # noqa: BLE001
                self._json({"erro": f"{type(e).__name__}: {e}"}, 500)
                return
        self._json({"erro": "endpoint desconhecido"}, 404)

    def _caixa(self, dados):
        act, slot_id = dados.get("act"), dados.get("slot")
        cfg = ler_config()
        with db.session() as con:
            if act == "permanente":
                novo, nome = alternar_permanente(cfg, slot_id)
                if novo == caixas.MONTADA:
                    return {"erro": f"{nome} está montada — usa «tirar da caixa»"}
                escrever_config(cfg)
                msg = f"{nome} passou a {novo}"
            elif act in ("subir", "descer"):
                msg = mover(con, cfg, slot_id, -1 if act == "subir" else 1)
                escrever_config(cfg)
            elif act == "montado":
                novo, nome = alternar_montada(cfg, slot_id)
                escrever_config(cfg)
                n = marcar_na_caixa(con, slot_id, novo)
                msg = (f"{nome}: {n} cópias registadas na caixa" if novo
                       else f"{nome}: caixa esvaziada ({n} linhas)")
            elif act == "confirmar":
                # A caixa JÁ se diz montada (`estado: montada`) e o vault não
                # sabe o que lá está: o que falta é registá-lo. Não mexe no
                # config — o estado já está certo, o que faltava era a estante.
                nome = caixas.caixa_do_cfg(cfg, slot_id).get("nome") or slot_id
                n = marcar_na_caixa(con, slot_id, True)
                msg = f"{nome}: {n} cópias confirmadas dentro da caixa"
            elif act == "actualizar":
                # "Actualizei": aplica o delta de UMA caixa congelada. Não passa
                # pelo config — o que muda é físico (que cartas estão na caixa),
                # e isso vive na `copy_allocation`.
                migracao.backup(con)
                rep = loadout.report(con)
                nome = next((s["nome"] for s in rep["slots"]
                             if s["slot"] == slot_id), slot_id)
                n = loadout.actualizar_caixa(con, rep, slot_id)
                msg = f"{nome} actualizado: {n} cópias na caixa"
            else:
                return {"erro": f"acção {act!r} desconhecida"}
            sources._CFG_CACHE.clear()     # relê já, sem esperar pelo mtime
            regenerar(con)
        return {"ok": True, "msg": msg}

    def _vender(self, dados):
        """"Vendida": a cópia sai da colecção e fica registada no `vendas.csv`.

        A linha vem da própria página (é a que ele está a ver), e por isso o
        servidor **recalcula-a** antes de tirar nada: uma página aberta há duas
        horas podia mandar tirar uma cópia que a alocação já deu a uma caixa.
        """
        chave, q = dados.get("linha"), dados.get("q")
        if not chave:
            return {"erro": "sem linha"}
        with db.session() as con:
            migracao.backup(con)
            rep = loadout.report(con)
            alvo = next((r for k in ("venda", "venda_rl", "retidos")
                         for r in rep[k]
                         if loadout.chave_venda(r) == chave), None)
            if alvo is None:
                return {"erro": "essa linha já não está na lista de venda — "
                                "recarrega a página"}
            res = loadout.registar_venda(con, alvo, q)
            regenerar(con)
        return {"ok": True, "msg": f'{res["copias"]}× {alvo["nm"]} fora da '
                                   f'colecção e no vendas.csv'}

    def _escolher(self, dados):
        """"Vou montar este" / "já não vou montar este", do `metagame.html`."""
        act, slot_id, aid = dados.get("act"), dados.get("slot"), dados.get("aid")
        cfg = ler_config()
        with db.session() as con:
            if act == "escolher":
                if not aid:
                    return {"erro": "sem arquétipo"}
                msg = escolher_lista(con, cfg, slot_id, int(aid))
            elif act == "desmarcar":
                msg = desmarcar_lista(cfg, slot_id)
            else:
                return {"erro": f"acção {act!r} desconhecida"}
            escrever_config(cfg)
            sources._CFG_CACHE.clear()
            regenerar(con)
        return {"ok": True, "msg": msg}

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------------------
# Arranque (o mesmo do riftvault: URL da rede local + QR)
# ---------------------------------------------------------------------------
def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def lan_ips() -> list[str]:
    """TODOS os endereços locais, o da rota por omissão primeiro.

    Mostrar só um engana quando a máquina tem Ethernet e Wi-Fi em sub-redes
    diferentes: o `lan_ip()` devolve o da Ethernet, mas o telemóvel está no
    Wi-Fi e não chega lá. É a mesma nota (e o mesmo código) do riftvault, onde o
    caso aconteceu a sério.
    """
    principal = lan_ip()
    todos = {principal}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            todos.add(info[4][0])
    except OSError:
        pass
    cmd = (["ipconfig"] if sys.platform == "win32"
           else ["ip", "-4", "-o", "addr", "show"])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                             errors="replace").stdout
        for m in re.finditer(r"(\d{1,3}(?:\.\d{1,3}){3})", out):
            todos.add(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass

    def util(ip: str) -> bool:
        p = ip.split(".")
        if p[0] == "127" or ip.startswith("169.254.") or p[-1] in ("0", "255"):
            return False
        return (p[0] == "10" or (p[0] == "172" and 16 <= int(p[1]) <= 31)
                or (p[0] == "192" and p[1] == "168"))

    return [principal] + sorted(x for x in todos if x != principal and util(x))


def ligacao_local(port: int | None = None) -> dict:
    """O link de escrita da rede local: `{url, ip, ips, porto, token}`.

    É o que vai no QR e o que a página mostra. O token vai no URL de propósito:
    escrever 32 dígitos hexadecimais num teclado de telemóvel é o atrito que faz
    não se usar a ferramenta.
    """
    p = port or int(os.environ.get("MTGVAULT_PORT") or PORT)
    ips = lan_ips()
    t = token()
    return {"ip": ips[0], "ips": ips, "porto": p, "token": t,
            "url": f"http://{ips[0]}:{p}/?t={t}"}


def url_edicao(port: int | None = None) -> str:
    return ligacao_local(port)["url"]


def qr_ascii(url: str) -> str:
    """O QR na consola. O nosso desenhador (`mtgvault.qr`) primeiro; a biblioteca
    `qrcode`, se estiver instalada, fica como alternativa para o caso de a
    consola não conseguir com os blocos de meia-altura."""
    try:
        arte = qr.ascii_arte(url)
        arte.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return arte
    except (UnicodeEncodeError, LookupError, ValueError):
        pass
    try:
        import qrcode                                   # noqa: PLC0415
        q = qrcode.QRCode(border=2)
        q.add_data(url)
        q.make(fit=True)
        buf = io.StringIO()
        q.print_ascii(out=buf, invert=True)
        out = buf.getvalue()
        out.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return out
    except Exception:                                   # noqa: BLE001
        return "  (a consola não mostra o QR; abre /qr.svg no browser)"


def regra_firewall(port: int) -> str:
    """O comando que abre o porto na rede PRIVADA do Windows.

    Não se corre sozinho: `netsh advfirewall` precisa de consola elevada, e um
    programa que abre portos na primeira execução sem avisar não é um programa
    de confiança. Imprime-se para ele copiar uma vez.
    """
    return (f'netsh advfirewall firewall add rule name="mtgvault {port}" '
            f'dir=in action=allow protocol=TCP localport={port} profile=private')


def main(port: int = PORT, host: str | None = None):
    host = host or BIND
    lig = ligacao_local(port)
    aberto = host not in ("127.0.0.1", "localhost", "::1")
    print("=" * 62)
    print("  mtgvault — MODO EDIÇÃO (escreve no colecao_config.json e no vault.db)")
    print("=" * 62)
    print(f"  Neste PC:          http://localhost:{port}/")
    if aberto:
        print(f"  Telemóvel (casa):  {lig['url']}")
        for extra in lig["ips"][1:]:
            print(f"     ou:             http://{extra}:{port}/?t={lig['token']}")
        if len(lig["ips"]) > 1:
            print("     (redes diferentes — usa a que o telemóvel alcança)")
    else:
        print("  Telemóvel:         DESLIGADO — corre com MTGVAULT_BIND=0.0.0.0")
    print(f"\n  Porto {port} — o 8770 é do riftvault, não lhe toques.\n")
    if aberto:
        print(qr_ascii(lig["url"]))
        print(f"  Token em {ficheiro_token()} (apaga-o para gerar outro).")
        print("  Sem o ?t= do link, a página é só de leitura.")
        print("  Se o telemóvel não chegar, abre o porto na rede privada:")
        print("    " + regra_firewall(port))
    print("  Não abras este porto no router.  Ctrl+C para parar.")
    print("=" * 62)
    srv = ThreadingHTTPServer((host, port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main(int(os.environ.get("MTGVAULT_PORT") or PORT))
