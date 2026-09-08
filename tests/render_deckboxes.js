// Corre o JavaScript do `deckboxes.html` num DOM de mentira e manda desenhar
// TODAS as abas, nos dois filtros.
//
// Com um segundo argumento, escreve nesse ficheiro o HTML que cada aba DESENHOU
// (`{aba: html}`), para o teste de Python poder ler o que o browser mostraria —
// é assim que se tranca que a tabela de venda não põe ✨ numa cópia `nonfoil`.
//
// Porque é que isto existe: a página nova é JSON + JavaScript, e um erro de
// render numa aba que não é a inicial só aparece ao CLICAR nela — a página fica
// em branco e o gerador não deu erro nenhum. É o mesmo padrão do `event_tier`,
// mas do lado do browser.
//
// Chamado pelo `test_paginas_loadout.py`, que salta em silêncio se não houver
// `node` (a bateria tem de correr num PC sem ele).
const fs = require('fs');
const vm = require('vm');

const caminho = process.argv[2];
const html = fs.readFileSync(caminho, 'utf8');
const scripts = [...html.matchAll(
  /<script(?![^>]*type="application\/json")[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const dados = html.match(
  /<script id="dados" type="application\/json">([\s\S]*?)<\/script>/)[1];
if (!scripts.length) { console.error('sem <script> na pagina'); process.exit(1); }

// Tudo o que a página chegou a DESENHAR, para se poder verificar o que lá está
// (e o que não pode lá estar: os botões de escrita no modo publicado).
const desenhado = [];

function el() {
  const e = {
    textContent: '', className: '', dataset: {}, hidden: false,
    style: {}, value: '', onclick: null, onchange: null,
    classList: { add() {}, remove() {}, toggle() {} },
    querySelector: () => null, querySelectorAll: () => [],
    appendChild() {}, remove() {}, scrollIntoView() {}, click() {}, select() {},
  };
  let html = '';
  Object.defineProperty(e, 'innerHTML', {
    get: () => html,
    set: (v) => { html = String(v); desenhado.push(html); },
  });
  return e;
}
const guardados = {};
const ctx = {
  console, JSON, Math, Object, Array, String, Number, Boolean, Date, RegExp, Error,
  setTimeout: (f) => { if (f) f(); },
  localStorage: {
    getItem: (k) => (k in guardados ? guardados[k] : null),
    setItem: (k, v) => { guardados[k] = v; },
  },
  navigator: {}, location: { reload() {} }, window: { scrollTo() {} },
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  URL: { createObjectURL: () => 'blob:', revokeObjectURL() {} },
  Blob: function () {}, confirm: () => false,
  document: {
    getElementById: (id) => (id === 'dados' ? { textContent: dados } : el()),
    querySelector: () => el(),
    querySelectorAll: () => [],
    createElement: () => el(),
    body: el(),
  },
};
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const s of scripts) vm.runInContext(s, ctx, { filename: 'deckboxes.js' });

// O `const D` do script é uma ligação lexica, não uma propriedade do global.
const slots = vm.runInContext('D.caixas.map(c => c.slot)', ctx);
const abas = ['plano', 'todas', 'arrumar', 'partilhadas', 'comprar', 'vender',
              // A aba das sugestões de Premodern só existe quando há caixas
              // desse formato (ver `renderTabs`); pedi-la sem elas cai na vista
              // Todas, que também tem de desenhar sem erro.
              'sugestoes', ...slots];
let n = 0;
for (const filtro of ['tudo', 'faltam']) {
  vm.runInContext(`filtro = ${JSON.stringify(filtro)};`, ctx);
  for (const a of abas) {
    vm.runInContext(`aba = ${JSON.stringify(a)}; renderTabs(); render();`, ctx);
    n++;
  }
}
// O HTML de cada aba, para quem chamou poder verificá-lo. O `render()` põe a
// vista no fim, por isso a última coisa desenhada é sempre a aba pedida.
if (process.argv[3]) {
  const dump = {};
  vm.runInContext('filtro = "tudo";', ctx);
  for (const a of abas) {
    vm.runInContext(`aba = ${JSON.stringify(a)}; renderTabs(); render();`, ctx);
    dump[a] = desenhado[desenhado.length - 1] || '';
  }
  fs.writeFileSync(process.argv[3], JSON.stringify(dump), 'utf8');
}

// O site publicado não pode DESENHAR um botão de escrita: os endpoints não
// existem lá, e um botão que não faz nada é pior do que não haver botão.
const editavel = vm.runInContext('D.editable', ctx);
const escrita = desenhado.filter(h => h.includes('data-act=')).length;
if (!editavel && escrita) {
  console.error(`ERRO: ${escrita} blocos com botoes de escrita numa pagina publicada`);
  process.exit(1);
}
console.log(`${abas.length} abas, ${n} renders sem erro`
  + `, ${escrita} blocos de escrita (editavel=${editavel})`);
