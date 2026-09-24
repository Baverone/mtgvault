"""Serve o site, mede o LAYOUT num Chrome a sério e (opcionalmente) fotografa.

    py tests/medir_layout.py <pasta-do-site> <pasta-de-capturas|-> [largura ...]

Mede, nas duas larguras do pedido do André (1440 e 390): **scroll horizontal**
do corpo — e quem o causa —, alvos de toque abaixo de 36 px, links internos
partidos e páginas que ficaram vazias ou com a mensagem de *«não consegui
carregar os dados»*.

Vive em `tests/` e não num scratch porque é dele que o
`test_casca.caso_nenhuma_pagina_tem_scroll_horizontal` depende: um teste que
chamasse uma ferramenta fora do repositório passava na máquina de quem a
escreveu e saltava em todas as outras.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
NODE = shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
PORTO, CDP = 8806, 9334
VISTAS = {1440: "desktop", 390: "telemovel"}
PAGINAS = ["index.html", "deckboxes.html", "metagame.html", "showcase.html",
           "colecao_cor.html", "caixarl.html", "cobertura.html",
           "reservedlist.html", "colecao.html"]


class Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except ConnectionError:
            self.close_connection = True


def main():
    site = Path(sys.argv[1]).resolve()
    capturas = sys.argv[2] if len(sys.argv) > 2 else "-"
    larguras = [int(x) for x in sys.argv[3:]] or list(VISTAS)
    h = functools.partial(Silencioso, directory=str(site))
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", PORTO), h)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    perfil = Path(__import__("tempfile").gettempdir()) / "mtgvault-perfil-cdp"
    ch = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
         "--no-default-browser-check", "--disable-extensions",
         f"--user-data-dir={perfil}",
         f"--remote-debugging-port={CDP}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    maus = 0
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{CDP}/json/version", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        existe = {f.name for f in site.glob("*.html")}
        for larg in larguras:
            dest = (str(Path(capturas).resolve() / VISTAS.get(larg, str(larg)))
                    if capturas != "-" else "-")
            p = subprocess.run(
                [NODE, str(AQUI / "medir_layout.js"), f"http://127.0.0.1:{PORTO}",
                 ",".join(PAGINAS), str(larg), dest],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", env={**os.environ, "CDP": str(CDP)}, timeout=900)
            if p.returncode:
                print(f"== {larg}px: ERRO\n{p.stderr[-2500:]}")
                maus += 1
                continue
            print(f"\n===== {larg} px =====")
            for pag, d in json.loads(p.stdout).items():
                partidos = sorted({l.split("#")[0].split("?")[0] for l in d["links"]}
                                  - existe)
                mal = (d["overflow"] > 0 or partidos or d["erroDados"]
                       or d["vazio"] < 400)
                maus += bool(mal)
                print(f"{'MAU ' if mal else 'OK  '}{pag:20s} "
                      f"largura={d['scrollW']} (+{d['overflow']}) "
                      f"altura={d['altura']} texto={d['vazio']}"
                      + (f"  LINKS PARTIDOS {partidos}" if partidos else "")
                      + (f"  ERRO-DADOS ×{d['erroDados']}" if d["erroDados"] else ""))
                for c in d["culpados"]:
                    print(f"       ↳ {c['q']:48s} {c['esq']}..{c['dir']}  «{c['txt']}»")
                if d["pequenos"]:
                    print("       alvos <36px: " + ", ".join(
                        f"{k}×{v}" for k, v in sorted(d["pequenos"].items(),
                                                      key=lambda x: -x[1])[:7]))
    finally:
        ch.terminate()
        srv.shutdown()
    print("\n" + ("TUDO OK" if not maus else f"{maus} páginas com problemas"))
    return 1 if maus else 0


if __name__ == "__main__":
    sys.exit(main())
