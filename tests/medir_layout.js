// Abre cada página num Chrome a sério (CDP), MEDE o layout e tira a CAPTURA.
//
//     node cdp.js <base-url> <pag[,pag]> <largura> <pasta-saida|-> [alturaMax]
//
// Porquê CDP e não `chrome --headless --screenshot --window-size=390,…`: no
// Windows a JANELA tem largura mínima (~500 px) e o `--window-size` é
// silenciosamente ignorado abaixo disso — a captura saía com 390 px de uma
// página desenhada a 500 e o conteúdo aparecia CORTADO à direita, como se
// houvesse scroll horizontal que não existia. Com `Emulation.setDeviceMetrics
// Override` a largura é a que se pede, e é a mesma que o telemóvel dele tem.
//
// E mede-se no mesmo sítio onde se fotografa: o que se está a verificar é
// LAYOUT, e num DOM de mentira não há layout nenhum.
const fs = require('fs');
const http = require('http');
const path = require('path');

const base = process.argv[2];
const paginas = process.argv[3].split(',');
const largura = Number(process.argv[4]);
const saida = process.argv[5];
const alturaMax = Number(process.argv[6] || 3200);
const PORTO = Number(process.env.CDP || 9333);

const pedirJSON = (url) => new Promise((res, rej) => {
  http.get(url, r => { let b = ''; r.on('data', c => b += c);
    r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(e); } }); })
    .on('error', rej);
});

const MEDIR = `(() => {
  const de = document.documentElement, W = de.clientWidth;
  const nome = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + (el.className && el.className.baseVal === undefined
       ? '.' + String(el.className).trim().split(/\\s+/).slice(0,3).join('.') : '');
  const maus = [], vistos = new Set();
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if ((r.width === 0 && r.height === 0) || r.right <= W + 1.5) continue;
    if (getComputedStyle(el).position === 'fixed') continue;
    /* O painel de navegação está FORA do ecrã de propósito (translateX) até ele
       tocar no menu; e quem estiver dentro dele vai atrás. */
    if (el.closest('.side') || el.closest('.salta')) continue;
    const q = nome(el);
    if (vistos.has(q)) continue;
    vistos.add(q);
    maus.push({ q, esq: Math.round(r.left), dir: Math.round(r.right),
                txt: (el.textContent || '').trim().slice(0, 40) });
  }
  const contaP = {};
  for (const el of document.querySelectorAll('a,button,select,input')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (el.closest('.pgft') || el.closest('.sidept')) continue;
    if (r.height < 36) { const q = nome(el).split('.').slice(0,2).join('.');
                         contaP[q] = (contaP[q] || 0) + 1; }
  }
  const links = [...document.querySelectorAll('a[href]')]
    .map(a => a.getAttribute('href')).filter(h => /^[a-z_]+\\.html/.test(h));
  return { scrollW: de.scrollWidth, clientW: W, altura: de.scrollHeight,
           overflow: Math.max(0, de.scrollWidth - W), culpados: maus.slice(0, 10),
           pequenos: contaP, links: [...new Set(links)],
           erroDados: document.querySelectorAll('.erro-dados').length,
           vazio: (document.body.textContent || '').trim().length };
})()`;

(async () => {
  const lista = await pedirJSON(`http://127.0.0.1:${PORTO}/json/list`);
  const alvo = lista.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
  if (!alvo) { console.error('sem página no Chrome de depuração'); process.exit(2); }
  const ws = new WebSocket(alvo.webSocketDebuggerUrl);
  let id = 0; const pend = new Map(); const eventos = new Map();
  const cmd = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id; pend.set(i, { res, rej });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) {
      const p = pend.get(m.id); pend.delete(m.id);
      m.error ? p.rej(new Error(m.error.message)) : p.res(m.result);
    } else if (m.method) { const h = eventos.get(m.method); if (h) h(m.params); }
  });
  await new Promise(r => ws.addEventListener('open', r));
  await cmd('Page.enable');

  const rel = {};
  for (const pag of paginas) {
    await cmd('Emulation.setDeviceMetricsOverride',
      { width: largura, height: 900, deviceScaleFactor: 1, mobile: largura < 700 });
    const pronto = new Promise(r => {
      const t = setTimeout(r, 15000);
      eventos.set('Page.loadEventFired', () => { clearTimeout(t); setTimeout(r, 2800); });
    });
    await cmd('Page.navigate', { url: `${base}/${pag}` });
    await pronto;
    const { result } = await cmd('Runtime.evaluate',
      { expression: MEDIR, returnByValue: true });
    rel[pag] = result.value;
    if (saida && saida !== '-') {
      const alt = Math.min(result.value.altura, alturaMax);
      await cmd('Emulation.setDeviceMetricsOverride',
        { width: largura, height: alt, deviceScaleFactor: 1, mobile: largura < 700 });
      await new Promise(r => setTimeout(r, 700));
      const shot = await cmd('Page.captureScreenshot', { format: 'png' });
      const f = path.join(saida, pag.replace('.html', '') + '.png');
      fs.mkdirSync(saida, { recursive: true });
      fs.writeFileSync(f, Buffer.from(shot.data, 'base64'));
    }
  }
  console.log(JSON.stringify(rel, null, 1));
  ws.close();
})().catch(e => { console.error(e.stack || e); process.exit(1); });
