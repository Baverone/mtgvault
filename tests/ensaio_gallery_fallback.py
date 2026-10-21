"""Galeria numa cópia temporária, sem colecções nem pedidos à rede.

Requer os browsers Playwright já usados pelo e2e da mesa.
"""
import base64
import os
from pathlib import Path
import sys
import tempfile
import uuid

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
# Pasta de ensaio com as permissões herdadas do directório temporário.
_TMP = Path(tempfile.gettempdir()) / ("mtg-gallery-" + uuid.uuid4().hex)
_TMP.mkdir()
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "config.json")

from playwright.sync_api import sync_playwright, expect
import collection_gallery as gallery

NAME = 'Teste "aspas" & <nome> d\'água'
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")


def run():
    cards = [dict(name=name, img=img, set="TST", cn="1", qty=2,
                  foil=True, collector=False, eur=1.25)
             for name, img in [(NAME, "/missing.png"),
                               ("Sem imagem", ""),
                               ("Imagem válida", "/valid.png")]]
    target = _TMP / "colecao.html"
    gallery._write_html(target, [dict(sub="Teste", value=7.5, qty=6, cards=cards)],
                        6, 7.5, "2026-10-21", [])
    with sync_playwright() as p:
        for profile, engine, options in [
            ("Chrome desktop", p.chromium, {"viewport": {"width": 1440, "height": 900}}),
            ("iPhone 15", p.webkit, p.devices["iPhone 15"]),
        ]:
            browser = engine.launch(headless=True)
            context = browser.new_context(**options)
            requests_404 = []

            def serve(route):
                url = route.request.url
                if url.endswith("/colecao.html"):
                    route.fulfill(status=200, content_type="text/html", path=str(target))
                elif url.endswith("/valid.png"):
                    route.fulfill(status=200, content_type="image/png", body=PNG)
                else:
                    if url.endswith("/missing.png"):
                        requests_404.append(url)
                    route.fulfill(status=404, body="Imagem indisponível")

            context.route("**/*", serve)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://gallery.test/colecao.html")
            first = page.locator(".c").nth(0)
            expect(first.locator(".noimg")).to_be_visible()
            expect(first.locator(".noimg")).to_have_text(NAME)
            expect(first.locator("a, img")).to_have_count(0)
            expect(first.locator(".qty")).to_have_text("2x")
            expect(first.locator(".foil")).to_have_text("foil")
            expect(page.locator(".c").nth(1).locator(".noimg")).to_be_visible()
            good = page.locator(".c").nth(2)
            good.scroll_into_view_if_needed()
            expect(good.locator("img")).to_be_visible()
            page.wait_for_function("document.querySelectorAll('.c img')[0].naturalWidth > 0")
            expect(good.locator(".noimg")).to_be_hidden()
            expect(good.locator("a")).to_have_attribute("href", "/valid.png")
            page.locator("#q").fill('"aspas"')
            expect(page.locator(".c")).to_have_count(1)
            expect(page.locator(".noimg")).to_be_visible()
            expect(page.locator(".noimg")).to_have_text(NAME)
            assert requests_404, "O ensaio não provocou nenhum 404"
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "overflow horizontal"
            browser.close()
            print(f"OK {profile}: 404, sem URL, imagem válida, etiquetas e procura")
    print("OK: 2 perfis")


if __name__ == "__main__":
    run()
