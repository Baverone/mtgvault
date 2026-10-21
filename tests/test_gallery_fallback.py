"""Regressão da alternativa com nome; o ensaio de browser fica separado."""
from pathlib import Path
import subprocess


def run():
    source = (Path(__file__).resolve().parents[1] / "collection_gallery.py").read_text(encoding="utf-8")
    js = source[source.index("const esc="):source.index("let ACTIVE=")]
    js += r'''
const assert = require('node:assert/strict');
const card = {name: 'Carta " & <teste>', img: '/404.png', set: 'TST', qty: 2, foil: true};
const html = cardHtml(card);
assert(html.includes('&quot;'));
assert(html.includes('&amp;'));
assert(html.includes('&lt;teste&gt;'));
const handler = html.match(/onerror="([^"]*)"/)[1];
const fallback = {hidden: true};
let removed = false;
const link = {nextElementSibling: fallback, remove(){removed = true;}};
new Function(handler).call({parentNode: link});
assert.equal(fallback.hidden, false);
assert.equal(removed, true);
const noUrl = cardHtml({...card, img: ''});
assert(!noUrl.includes('<img'));
assert(noUrl.includes('<div class="noimg">Carta &quot; &amp; &lt;teste&gt;</div>'));
console.log('OK: escape de nomes, alternativa apos erro, alternativa sem URL (3 casos)');
'''
    subprocess.run(["node", "-e", js], check=True, timeout=15)


if __name__ == "__main__":
    run()
