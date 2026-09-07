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
cartas estão dentro de que caixa). Isso não é uma preferência, é o estado da
estante — e não cabe num ficheiro de configuração.

Sem palavra-passe: quem chegar ao URL pode escrever. Não abras o porto no router.
"""
from __future__ import annotations

import io
import json
import os
import re
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import db, loadout, migracao, sources  # noqa: E402

import deckboxes  # noqa: E402

PORT = 8771          # o 8770 é do riftvault — ver o cabeçalho
CONFIG = Path(os.environ.get("MTGVAULT_CONFIG") or ROOT / "colecao_config.json")
# As chaves cujo conteúdo se escreve com um elemento por linha. São listas de
# objectos curtos que se lêem melhor assim — e é como o ficheiro está hoje, à
# mão. Reformatá-las com `indent=2` dava um diff de 200 linhas por cada clique.
UMA_LINHA = ("loadout", "regras_por_formato", "baldes_coleccao",
             "decks_vigiados", "premodern_arquetipos_alvo", "formatos_metagame",
             "so_jogadores_vigiados", "premodern_decks_completos",
             "decks_montados", "reserved_vender_ignorar_formatos")


# ---------------------------------------------------------------------------
# Config: ler, mexer, gravar sem estragar a formatação
# ---------------------------------------------------------------------------
def ler_config(path: Path | None = None) -> dict:
    return json.loads((path or CONFIG).read_text(encoding="utf-8"))


def escrever_config(cfg: dict, path: Path | None = None) -> None:
    """Grava o config mantendo a forma com que está escrito à mão.

    Um `json.dump(indent=2)` cru rebentava as catorze linhas do `loadout` em
    duzentas, e o ficheiro é para ser lido por uma pessoa — é lá que estão as
    explicações em português de cada regra.
    """
    partes = []
    for k, v in cfg.items():
        chave = json.dumps(k, ensure_ascii=False)
        if k in UMA_LINHA and isinstance(v, list):
            itens = ",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in v)
            corpo = f"[\n{itens}\n  ]" if v else "[]"
        else:
            corpo = json.dumps(v, ensure_ascii=False, indent=2)
            corpo = corpo.replace("\n", "\n  ")
        partes.append(f"  {chave}: {corpo}")
    (path or CONFIG).write_text("{\n" + ",\n".join(partes) + "\n}\n", encoding="utf-8")


def _peers(con, cfg, slot_id):
    """Os slots que o `prioridade` deste ordena — os do mesmo grupo, com o mesmo
    estado de permanente e de vigiado, pela ordem real da alocação.

    Fora deste conjunto o `prioridade` não decide nada: quem manda é o grupo de
    formato, o "permanente" e o "é deck vigiado", por essa ordem. Subir um slot
    de Premodern acima de um permanente de cEDH não é um número — é mudar o
    `regras_por_formato`, e o botão diz isso em vez de fingir que fez algo.
    """
    resolvidos = loadout.resolve_slots(con, cfg.get("loadout") or [])
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
    for s in cfg["loadout"]:
        if s["slot"] in posicao:
            s["prioridade"] = posicao[s["slot"]]
    return f"{alvo['nome']} {'subiu' if delta < 0 else 'desceu'} no grupo {alvo['grupo']}"


def alternar(cfg, slot_id, chave, default=True) -> tuple[bool, str]:
    for s in cfg.get("loadout") or []:
        if s["slot"] == slot_id:
            novo = not bool(s.get(chave, default))
            s[chave] = novo
            return novo, s.get("nome") or slot_id
    raise KeyError(slot_id)


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
    """Reescreve o `deckboxes.html` estático, para o site publicado acompanhar.

    Sem isto, o modo edição e o GitHub Pages diziam coisas diferentes até à
    corrida seguinte do `daily.py` — e a diferença aparecia no telemóvel dele,
    fora de casa, sem explicação nenhuma.
    """
    deckboxes.build(con, ROOT / "deckboxes.html")


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

    def do_GET(self):                                  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho in ("/", "/index.html", "/deckboxes.html"):
            with db.session() as con:
                self._envia(deckboxes.html_page(con, editable=True))
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
        except Exception as e:                          # noqa: BLE001
            self._json({"erro": repr(e)}, 500)
            return
        self._json({"erro": "endpoint desconhecido"}, 404)

    def _caixa(self, dados):
        act, slot_id = dados.get("act"), dados.get("slot")
        cfg = ler_config()
        with db.session() as con:
            if act == "permanente":
                novo, nome = alternar(cfg, slot_id, "permanente", True)
                escrever_config(cfg)
                msg = f"{nome} passou a {'permanente' if novo else 'candidato'}"
            elif act in ("subir", "descer"):
                msg = mover(con, cfg, slot_id, -1 if act == "subir" else 1)
                escrever_config(cfg)
            elif act == "montado":
                novo, nome = alternar(cfg, slot_id, "montado", False)
                escrever_config(cfg)
                n = marcar_na_caixa(con, slot_id, novo)
                msg = (f"{nome}: {n} cópias registadas na caixa" if novo
                       else f"{nome}: caixa esvaziada ({n} linhas)")
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


def qr_ascii(url: str) -> str:
    try:
        import qrcode
    except ImportError:
        return "  (instala `qrcode` para veres o QR aqui: py -m pip install qrcode)"
    try:
        qr = qrcode.QRCode(border=2)
        qr.add_data(url)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        out = buf.getvalue()
        out.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return out
    except Exception:                                   # noqa: BLE001
        return "  (a consola não mostra o QR; usa o URL acima)"


def main(port: int = PORT, host: str = "0.0.0.0"):
    ips = lan_ips()
    lan = f"http://{ips[0]}:{port}/"
    print("=" * 62)
    print("  mtgvault — MODO EDIÇÃO (escreve no colecao_config.json e no vault.db)")
    print("=" * 62)
    print(f"  Neste PC:          http://localhost:{port}/")
    print(f"  Telemóvel (casa):  {lan}")
    for extra in ips[1:]:
        print(f"     ou:             http://{extra}:{port}/")
    if len(ips) > 1:
        print("     (redes diferentes — usa a que o telemóvel alcança)")
    print(f"\n  Porto {port} — o 8770 é do riftvault, não lhe toques.\n")
    print(qr_ascii(lan))
    print("  Sem palavra-passe: quem chegar ao URL pode escrever.")
    print("  Não abras este porto no router.  Ctrl+C para parar.")
    print("=" * 62)
    srv = ThreadingHTTPServer((host, port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main(int(os.environ.get("MTGVAULT_PORT") or PORT))
