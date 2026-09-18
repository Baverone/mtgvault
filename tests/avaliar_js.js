// Corre o JavaScript do `deckboxes.html` no mesmo DOM de mentira do
// `render_deckboxes.js` e depois corre um SEGUNDO script (o do teste) nesse
// contexto, com acesso a tudo o que a página definiu (`casaProcura`, `gravar`,
// `recarregar`, `armar`, `P`, `D`, …). O que esse script deixar em `resultado`
// (valor ou Promise) sai em JSON no stdout.
//
//     node avaliar_js.js <pagina.html> <teste.js>
//
// Porque é que existe (2026-09-18): as funções que tornam a página utilizável
// no telemóvel — a procura sem acentos, o `gravar` que diz em português que
// ficou sem rede, o `recarregar` que não perde a página, o «vendida» em dois
// toques — não desenham nada, e por isso o dump de HTML do `render_deckboxes.js`
// não as vê. Um teste que só leia o HTML deixava-as partir em silêncio.
//
// Ao contrário do `render_deckboxes.js`, os temporizadores são A SÉRIO (o
// `armar` e o timeout do `gravar` dependem deles) e o `fetch` é o que o teste
// puser — por omissão responde `{}`.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const caminho = process.argv[2];
const testeJs = fs.readFileSync(process.argv[3], 'utf8');
const html = fs.readFileSync(caminho, 'utf8');
const scripts = [...html.matchAll(
  /<script(?![^>]*type="application\/json")([^>]*)>([\s\S]*?)<\/script>/g)].map(m => {
    const src = (m[1].match(/\bsrc="([^"?]+)/) || [])[1];
    if (!src) return m[2];
    for (const base of [path.dirname(caminho), path.join(__dirname, '..')]) {
      const f = path.join(base, src);
      if (fs.existsSync(f)) return fs.readFileSync(f, 'utf8');
    }
    console.error(`nao encontrei o script ${src}`);
    process.exit(1);
  });
const dados = (html.match(
  /<script id="dados" type="application\/json">([\s\S]*?)<\/script>/) || [])[1];

function el() {
  const e = {
    textContent: '', className: '', dataset: {}, hidden: false,
    style: {}, value: '', onclick: null, onchange: null, disabled: false,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    querySelector: () => null, querySelectorAll: () => [],
    appendChild() {}, remove() {}, scrollIntoView() {}, click() {}, select() {},
    getAttribute: () => null, setAttribute() {},
  };
  let h = '';
  Object.defineProperty(e, 'innerHTML', { get: () => h, set: (v) => { h = String(v); } });
  return e;
}
const cache = {};
const um = (sel) => (cache[sel] = cache[sel] || el());
const guardados = {};
const toasts = [];
const ctx = {
  console, JSON, Math, Object, Array, String, Number, Boolean, Date, RegExp, Error,
  TypeError, Promise, Set, Map, setTimeout, clearTimeout, AbortController,
  encodeURIComponent, decodeURIComponent, URLSearchParams,
  localStorage: {
    getItem: (k) => (k in guardados ? guardados[k] : null),
    setItem: (k, v) => { guardados[k] = v; }, removeItem: (k) => { delete guardados[k]; },
  },
  navigator: {}, location: { search: '', protocol: 'http:', reload() { ctx.__reloads++; } },
  __reloads: 0, __toasts: toasts,
  window: { scrollTo() {}, scrollY: 0 },
  fetch: async () => ({ ok: true, status: 200, json: async () => ({}) }),
  URL: { createObjectURL: () => 'blob:', revokeObjectURL() {} },
  Blob: function () {}, confirm: () => true,
  document: {
    getElementById: (id) => (id === 'dados' ? (dados == null ? null : { textContent: dados })
                                            : um('#' + id)),
    querySelector: (sel) => um(sel), querySelectorAll: () => [],
    createElement: () => el(),
    // O que a página "mostra" em toasts e avisos: o `textContent` de cada
    // elemento que pendura no body, para o teste poder ler as mensagens.
    body: Object.assign(el(), { appendChild: (d) => toasts.push(d.textContent || d.innerHTML) }),
  },
};
ctx.globalThis = ctx;
ctx.window.document = ctx.document;
vm.createContext(ctx);
for (const s of scripts) vm.runInContext(s, ctx, { filename: 'deckboxes.js' });

(async () => {
  const r = vm.runInContext(testeJs + '\n;resultado', ctx, { filename: 'teste.js' });
  const v = await r;
  process.stdout.write(JSON.stringify(v === undefined ? null : v));
  process.exit(0);
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
