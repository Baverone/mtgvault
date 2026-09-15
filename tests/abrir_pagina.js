// Abre uma página SERVIDA POR HTTP como o browser a abriria: vai buscar o HTML,
// corre o JavaScript dela num DOM de mentira, deixa os `fetch` dos dados
// (`data/paginas/...`) irem MESMO ao servidor, e escreve num ficheiro o HTML
// que cada contentor ficou a mostrar depois de tudo assentar.
//
//     node abrir_pagina.js <url> <saida.json>
//
// Porque é que isto existe (2026-09-15): as páginas pesadas passaram a ser uma
// casca + JSON à parte. A casca sozinha está sempre certa — o que pode falhar
// em silêncio é o `fetch` (um caminho errado, um ficheiro que o `git add` não
// levou, um JSON truncado) e aí a página fica em branco sem um único erro no
// gerador. É o `render_deckboxes.js` com um servidor a sério do outro lado.
//
// O DOM de mentira é o mínimo que os scripts das quatro páginas pedem: um
// elemento por selector (`#vista`, `.fpanel[data-f="modern"]`, …) e, para as
// páginas que se desenham por secções (`section.ed`, `section.fmt`), as
// secções lidas do HTML com o seu `data-parte` e o seu `.grid`.
const fs = require('fs');
const vm = require('vm');

const url = process.argv[2];
const saida = process.argv[3];

function el(nome) {
  const e = {
    nome, textContent: '', className: '', dataset: {}, hidden: false, open: false,
    style: {}, value: '', onclick: null, onchange: null, tagName: 'DIV',
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    querySelector: (sel) => (e.filhos && e.filhos[sel]) || null,
    querySelectorAll: () => [],
    appendChild() {}, remove() {}, scrollIntoView() {}, click() {}, select() {},
    addEventListener() {}, setAttribute() {}, getAttribute: () => null,
  };
  let html = '';
  Object.defineProperty(e, 'innerHTML', {
    get: () => html, set: (v) => { html = String(v); },
  });
  return e;
}

(async () => {
  const r = await fetch(url);
  if (!r.ok) { console.error(`GET ${url} -> ${r.status}`); process.exit(2); }
  const html = await r.text();
  const scripts = [...html.matchAll(
    /<script(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  if (!scripts.length) { console.error('sem <script> na pagina'); process.exit(1); }

  const cache = {};
  const um = (sel) => (cache[sel] = cache[sel] || el(sel));
  // As secções por `data-parte` (Reserved List: `section.ed`; Cobertura:
  // `section.fmt`), cada uma com o seu `.grid`.
  const seccoes = (cls) => [...html.matchAll(
    new RegExp(`<section class="${cls}" data-parte="([^"]+)"`, 'g'))].map(m => {
      const s = um(`section.${cls}[data-parte="${m[1]}"]`);
      s.dataset.parte = m[1];
      s.filhos = { '.grid': um(`grid:${cls}:${m[1]}`) };
      return s;
    });
  const base = new URL(url);
  const ctx = {
    console, JSON, Math, Object, Array, String, Number, Boolean, Date, RegExp, Error,
    Promise, URLSearchParams, encodeURIComponent, decodeURIComponent,
    setTimeout: (f) => { if (f) f(); }, clearTimeout: () => {},
    // O `fetch` a sério, com os caminhos relativos resolvidos como o browser faz.
    fetch: (u, o) => fetch(new URL(u, base).href, o),
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    navigator: {}, window: { scrollTo() {} },
    location: { search: base.search, protocol: base.protocol, reload() {} },
    URL: { createObjectURL: () => 'blob:', revokeObjectURL() {} },
    Blob: function () {}, confirm: () => false,
    document: {
      // A casca NÃO tem `script#dados`: como no browser, é `null`.
      getElementById: (id) => (id === 'dados' ? null : um('#' + id)),
      querySelector: (sel) => um(sel),
      querySelectorAll: (sel) => (sel === 'section.ed' ? seccoes('ed')
                                  : sel === 'section.fmt' ? seccoes('fmt') : []),
      createElement: () => el('novo'),
      body: el('body'),
    },
  };
  ctx.globalThis = ctx;
  ctx.window.document = ctx.document;
  vm.createContext(ctx);
  for (const s of scripts) vm.runInContext(s, ctx, { filename: 'pagina.js' });
  // Deixar os `fetch` e os `then` assentarem: cada volta do ciclo de eventos
  // até nada mudar durante 300 ms (as páginas encadeiam 2–3 pedidos).
  let antes = '';
  for (let i = 0; i < 40; i++) {
    await new Promise(res => setTimeout(res, 300));
    const agora = JSON.stringify(Object.keys(cache).map(k => cache[k].innerHTML));
    if (agora === antes) break;
    antes = agora;
  }
  const dump = {};
  for (const k of Object.keys(cache)) dump[k] = cache[k].innerHTML;
  fs.writeFileSync(saida, JSON.stringify(dump), 'utf8');
  console.log(`${url}: ${Object.keys(dump).length} contentores`);
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
