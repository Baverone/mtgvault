"""Gera arrumacao.html — A ARRUMAÇÃO POR FASES (André, 2026-10-01).

Ele vai arrumar a colecção por fases e pediu *"organização"* e **um sítio que
diga sempre onde está e o que vem a seguir**. O motor está em
`mtgvault/fases.py` (é lá que estão as quatro protecções, os três estados de
cada deck, o limiar da reserva e a trava do RC Ghent). Esta página é a vista.

O ALVO É O TELEMÓVEL, pela rede de casa: é com o telemóvel na mão e as cartas
na mesa que ele trabalha. Por isso segue as decisões que já estavam tomadas:

* a **casca** vai no HTML e os **dados à parte** (2026-09-15) — o índice leva a
  Fase 1 inteira (é o primeiro ecrã: não pode esperar por nada) e as filas de
  fotos, que são grandes, vão numa parte cada, idas buscar quando ele abre a
  fase;
* um `fetch` que falhe **diz-lho em português** (`paginas.erroDados`), nunca um
  ecrã vazio;
* os botões só existem no **modo edição** (porto 8771) — no site publicado não
  há endpoint que grave, e um botão que não grava é pior do que botão nenhum;
* **nada aqui mexe em alocações nem na base**: lê a colecção e escreve o estado
  do deck e a reserva no `colecao_config.json` (com o `configio.escrever`, que
  preserva a forma do ficheiro).

AS QUATRO FASES, e a via paralela:

    Fase 1  FECHAR OS DECKS      decidir montado/guardado/dissolvido, e ver o
                                 que cada decisão liberta + a RESERVA proposta
    Fase 2  FOTOS DOS DECKS      antes de Ghent: confirmar que cada deck que
                                 fica montado está fisicamente completo
    Fase 3  CANDIDATOS           sai sozinha da Fase 1, com as quatro
                                 protecções aplicadas e o motivo à vista
    Fase 4  FOTOS DOS CANDIDATOS depois de Ghent: fila POR CARTA, da mais cara
                                 para a mais barata, em lotes de 50
    paralela INVENTÁRIO          fotos da RL, das shocklands e das fetchlands —
                                 nunca bloqueia nenhuma fase
"""
from __future__ import annotations

import json
from pathlib import Path

from mtgvault import fases, paginas
from mtgvault import site_shell as shell

ROOT = Path(__file__).resolve().parent
PAGINA = "arrumacao.html"
# O rótulo da barra lateral. O `<h1>` tem de ser O MESMO (decisão da 2.ª
# passagem de 2026-09-24: clicar num item e aterrar numa página com outro nome é
# a página a discordar do menu que lá levou). Tem teste.
TITULO = "Arrumação por fases"

_CSS = """
 .fasebar{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 20px}
 .fasebar button{min-height:40px;padding:8px 14px;border-radius:999px;border:1px solid var(--line);background:var(--card2);color:var(--muted);font:inherit;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:7px}
 .fasebar button.cur{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 .fasebar button .nq{background:var(--card);border-radius:999px;padding:1px 7px;font-size:11px;color:var(--dim)}
 .fasebar button.par{border-style:dashed}
 .trava{background:var(--card2);border:1px solid var(--accent-line);color:var(--accent);border-radius:var(--r);padding:12px 15px;font-size:13px;line-height:1.6;margin:0 0 18px}
 .chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
 .chip{background:var(--card2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:12px;color:var(--muted)}
 .chip b{color:var(--ink)}
 .chip.gold{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 h2{font-size:15px;margin:24px 0 4px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
 h2 .n{color:var(--muted);font-size:12px;font-weight:500}
 .sub{color:var(--muted);font-size:12.5px;line-height:1.6;margin:0 0 14px}
 .deck{border:1px solid var(--line);border-radius:var(--r);background:var(--card2);padding:14px;margin:0 0 12px}
 .deck .dh{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
 .deck .dn{font-family:var(--font-hd);font-size:15.5px}
 .deck .dm{color:var(--dim);font-size:12px}
 .seg{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 0}
 .seg button{min-height:40px;padding:8px 13px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--muted);font:inherit;font-size:13px;font-weight:600;cursor:pointer}
 .seg button.on{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 .seg button.ro{cursor:default}
 .lib{color:var(--muted);font-size:12.5px;margin:10px 0 0;line-height:1.6}
 .lib b{color:var(--ink)}
 .pordecidir{color:var(--warn);font-size:12px;font-weight:600}
 .bar{height:7px;border-radius:999px;background:var(--card);overflow:hidden;margin:10px 0 6px}
 .bar i{display:block;height:100%;background:var(--accent)}
 .barl{color:var(--muted);font-size:12px}
 details.res{margin:12px 0 0;border-top:1px solid var(--line);padding-top:10px}
 details.res summary{cursor:pointer;color:var(--muted);font-size:12.5px;font-weight:600}
 .rl{list-style:none;padding:0;margin:10px 0 0;display:grid;gap:4px}
 .rl li{display:flex;align-items:center;gap:9px;font-size:13px;padding:3px 0}
 .rl .pc{min-width:52px;color:var(--accent);font-size:12px;font-weight:700;text-align:right}
 .rl .tm{color:var(--dim);font-size:11.5px;min-width:56px}
 .rl .mn{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:1px 7px;font-size:10.5px;color:var(--dim)}
 .rl button{min-height:36px;min-width:36px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--muted);cursor:pointer;font:inherit}
 .addres{display:flex;gap:7px;margin:10px 0 0;flex-wrap:wrap}
 .addres input{flex:1 1 180px;min-height:40px;padding:8px 11px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit;font-size:13px}
 .addres button{min-height:40px;padding:8px 14px;border-radius:10px;border:1px solid var(--accent-line);background:var(--accent-soft);color:var(--accent);font:inherit;font-weight:700;cursor:pointer}
 table.cd{width:100%;border-collapse:collapse;font-size:13px}
 table.cd th{text-align:left;color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;padding:6px 8px;border-bottom:1px solid var(--line);font-weight:700}
 table.cd td{padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
 table.cd td.v{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
 table.cd tr:hover td{background:var(--card2)}
 .mot{color:var(--dim);font-size:11.5px;line-height:1.5}
 .prot{display:inline-block;background:var(--card);border:1px solid var(--line);border-radius:999px;padding:1px 8px;font-size:10.5px;color:var(--muted);white-space:nowrap}
 .lote{border:1px solid var(--line);border-radius:var(--r);background:var(--card2);margin:0 0 12px}
 .lote>summary{cursor:pointer;padding:12px 14px;font-size:13.5px;font-weight:600;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
 .lote>summary .lm{color:var(--muted);font-weight:500;font-size:12px}
 .lote .lb{padding:0 14px 14px}
 .fl{list-style:none;padding:0;margin:0;display:grid;gap:3px}
 .fl li{display:flex;align-items:center;gap:9px;font-size:13px;padding:4px 0;border-bottom:1px solid var(--line)}
 .fl .q{min-width:68px;color:var(--muted);font-size:11.5px;text-align:right;font-variant-numeric:tabular-nums}
 .fl .wh{color:var(--dim);font-size:11.5px}
 .fl .ok{color:var(--add);font-size:11.5px}
 .vazio{color:var(--muted);font-size:13px;padding:16px 0}
 @media (max-width:640px){
   table.cd th:nth-child(3),table.cd td:nth-child(3){display:none}
   .deck{padding:12px}
 }
"""

_LEAD = ("Onde estás na arrumação da coleção e o que vem a seguir. As quatro "
         "regras de 1 de outubro de 2026 valem em todas as fases, e cada cópia "
         "que fica de fora da venda diz por que regra ficou.")

_RODAPE = (
    "<p><b>As quatro proteções.</b> <b>P1</b> — todas as cópias das shocklands "
    "e das fetchlands ficam protegidas: todos os acabamentos, todas as línguas, "
    "todas as repetidas, estejam ou não num deck. As duas listas são "
    "<b>derivadas do catálogo</b> pelo texto da carta e pelos tipos, nunca "
    "escritas à mão, e a conta tem de dar dez de cada — se não der, a página "
    "diz e para. <b>P2</b> — a Reserved List que jogas (alocada a um deck ou no "
    "consenso de um formato que jogas); o resto da Reserved List continua a "
    "passar pela regra dos 5 % de 8 de setembro. <b>P3</b> — nada do que está "
    "num deck que decidiste manter montado ou guardar. <b>P4</b> — a reserva de "
    "cada deck.</p>"
    "<p><b>A reserva («maybe»).</b> Enche-se sozinha a partir do consenso do "
    "arquétipo — a banda flex e o resto do sideboard que não estão nas 75 de "
    "hoje — mais o que acrescentares à mão. Tem um <b>limiar</b>: só entra o que "
    "aparece em pelo menos essa percentagem das listas. Sem limiar não sobrava "
    "nada para vender, porque um arquétipo tem dezenas de cartas distintas "
    "entre o main e o sideboard. Abaixo de oito listas não se chama consenso a "
    "nada e a reserva automática fica vazia. A reserva protege só o que tens; o "
    "que não tens alimenta a lista de compras.</p>"
    "<p><b>Os três estados.</b> <i>Montado</i> fica montado e as cartas ficam "
    "protegidas; <i>guardado</i> desmonta-se e as cartas continuam protegidas; "
    "<i>dissolvido</i> desmonta-se e as cartas passam a candidatas, menos as que "
    "P1, P2 ou P4 apanhem. <b>Um deck sem decisão conta como montado</b> — nunca "
    "o contrário: um deck novo não manda uma única carta para a venda. Mudar de "
    "estado é reversível e não apaga nada.</p>"
    "<p><b>A fila de fotos conta cópias físicas, não nomes.</b> Se jogas quatro "
    "da mesma carta, são quatro fotos — e por isso a barra de progresso e os "
    "totais são em cópias. As fotos entram pelo caminho de sempre: largas-as em "
    "<code>pendentes/</code> (ou tiras-as do telemóvel na Deck boxes) e a corrida "
    "da noite liga cada uma à sua cópia.</p>"
    "<p><b>O inventário é paralelo.</b> As fotos da Reserved List e das "
    "shock/fetchlands não são um passo da venda e nunca bloqueiam nenhuma fase.</p>")

_JS = r"""
%JS_DADOS%
let D = null, ABA = 'f1';
const PARTES = {};
const el = id => document.getElementById(id);
const eur = v => (v == null ? '—' : Number(v).toLocaleString('pt-PT',
  {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €');
const cop = n => n + (n === 1 ? ' cópia' : ' cópias');
const ESTADOS = [['montado', 'Montado'], ['guardado', 'Guardado'],
                 ['dissolvido', 'Dissolvido']];
const ABAS = [
  ['f1', 'Fase 1 · Fechar os decks'],
  ['f2', 'Fase 2 · Fotos dos decks'],
  ['f3', 'Fase 3 · Candidatos'],
  ['f4', 'Fase 4 · Fotos dos candidatos'],
  ['inv', 'Inventário (paralelo)'],
];

/* ---------------------------------------------------------------- gravar */
async function grava(corpo, botao) {
  if (!D.editavel) return;
  const antes = botao ? botao.textContent : '';
  if (botao) { botao.disabled = true; botao.textContent = '…'; }
  let r;
  try {
    const ctl = new AbortController();
    const prazo = setTimeout(() => ctl.abort(), 25000);
    r = await fetch(corpo.url + (TOKEN_URL ? '?t=' + encodeURIComponent(TOKEN_URL) : ''),
      {method: 'POST', headers: {'Content-Type': 'application/json'},
       body: JSON.stringify(corpo.dados), signal: ctl.signal});
    clearTimeout(prazo);
  } catch (e) {
    if (botao) { botao.disabled = false; botao.textContent = antes; }
    toast('não sei se gravou — a rede não respondeu em 25 s. Recarrega para ver.', true);
    return;
  }
  let j = {};
  try { j = await r.json(); } catch (e) { j = {}; }
  if (!r.ok) {
    if (botao) { botao.disabled = false; botao.textContent = antes; }
    toast(j.erro || ('o servidor respondeu ' + r.status), true);
    return;
  }
  await recarrega();
}
async function recarrega() {
  try {
    D = await carregaDados('arrumacao.json');
    for (const k of Object.keys(PARTES)) delete PARTES[k];
    render();
  } catch (e) { erroDados(el('vista'), e); }
}
let _t = null;
function toast(msg, erro) {
  const t = el('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'trava' + (erro ? ' err' : '');
  t.hidden = false;
  clearTimeout(_t);
  _t = setTimeout(() => { t.hidden = true; }, erro ? 7000 : 4000);
}

/* ------------------------------------------------------------- FASE 1 */
function reservaHTML(d) {
  const r = d.reserva || {};
  const ls = r.final || [];
  let corpo = ls.length
    ? `<ul class="rl">` + ls.map(x =>
        `<li><span class="pc">${x.pct == null ? '—' : x.pct + ' %'}</span>`
        + `<span class="tm">${x.tem ? 'tens ' + x.tem : 'não tens'}</span>`
        + `<span style="flex:1">${escDados(x.nm)}</span>`
        + (x.manual ? `<span class="mn">à mão</span>` : '')
        + (D.editavel ? `<button type="button" data-res-fora="${escDados(d.slot)}"`
            + ` data-carta="${escDados(x.nm)}" title="tirar da reserva">✕</button>` : '')
        + `</li>`).join('') + `</ul>`
    : `<p class="vazio">Sem reserva. ${escDados(r.nota || '')}</p>`;
  if (D.editavel) {
    corpo += `<div class="addres"><input type="text" id="novares-${escDados(d.slot)}"`
      + ` placeholder="acrescentar uma carta à mão (nome em inglês)">`
      + `<button type="button" data-res-add="${escDados(d.slot)}">acrescentar</button></div>`;
  }
  return `<details class="res"><summary>Reserva («maybe»): `
    + `<b>${ls.length}</b> cartas · ${r.tem || 0} que tens`
    + `, ${r.sem || 0} que não tens · limiar ${r.limiar} %</summary>`
    + `<p class="sub" style="margin:8px 0 0">${escDados(r.nota || '')}</p>`
    + corpo + `</details>`;
}
function deckHTML(d) {
  const seg = ESTADOS.map(([k, rot]) =>
    `<button type="button" class="${d.decisao === k ? 'on' : ''}${D.editavel ? '' : ' ro'}"`
    + (D.editavel ? ` data-dec="${escDados(d.slot)}" data-valor="${k}"` : '')
    + `>${rot}</button>`).join('');
  const lib = d.decisao === 'dissolvido'
    ? `Dissolvido: <b>${cop(d.liberta.copias)}</b> · <b>${eur(d.liberta.valor)}</b> já estão a contar como candidatas.`
    : `Dissolver este deck libertava <b>${cop(d.liberta.copias)}</b> · <b>${eur(d.liberta.valor)}</b>`
      + ` (o resto fica protegido por P1 ou P2).`;
  return `<div class="deck"><div class="dh"><div>`
    + `<div class="dn">${escDados(d.nome)}</div>`
    + `<div class="dm">${escDados(d.formato || '')} · ${cop(d.na_caixa)} na caixa`
    + (d.montada_em ? ` · montada em ${escDados(d.montada_em)}` : '')
    + `</div></div><div class="dm" style="text-align:right">${eur(d.valor)}`
    + (d.decisao_explicita ? '' : `<br><span class="pordecidir">por decidir`
        + ` (conta como montado)</span>`)
    + `</div></div>`
    + `<div class="seg">${seg}</div>`
    + `<p class="lib">${lib}</p>`
    + reservaHTML(d) + `</div>`;
}
function fase1() {
  const ds = D.decks || [];
  const n = {montado: 0, guardado: 0, dissolvido: 0};
  for (const d of ds) n[d.decisao]++;
  return `<h2>Fase 1 · Fechar os decks <span class="n">${ds.length} decks</span></h2>`
    + `<p class="sub">Para cada deck: fica montado, guarda-se (desmonta-se mas as `
    + `cartas continuam protegidas) ou dissolve-se. <b>Um deck sem decisão conta `
    + `como montado.</b> Mudar de estado é reversível e não apaga nada.</p>`
    + `<div class="chips"><span class="chip gold"><b>${n.montado}</b> montados</span>`
    + `<span class="chip"><b>${n.guardado}</b> guardados</span>`
    + `<span class="chip"><b>${n.dissolvido}</b> dissolvidos</span>`
    + `<span class="chip"><b>${D.por_decidir}</b> por decidir</span></div>`
    + ds.map(deckHTML).join('');
}

/* ------------------------------------------------------- FASE 2 e FASE 4 */
function barraHTML(b) {
  return `<div class="bar"><i style="width:${b.pct}%"></i></div>`
    + `<p class="barl"><b>${b.feitas}</b> de <b>${b.copias}</b> cópias `
    + `(${b.pct} %) · feito ${eur(b.feitas_valor)} · falta ${eur(b.falta_valor)}</p>`;
}
function filaLinha(l) {
  return `<li><span style="flex:1">${escDados(l.nm)}</span>`
    + `<span class="wh">${escDados(l.set)} ${escDados((l.lang || '').toUpperCase())}`
    + `${l.foil ? ' ✨' : ''} ${escDados(l.cond || '')}</span>`
    + `<span class="wh">${escDados(l.local || '')}</span>`
    + `<span class="q">${eur(l.total)}</span>`
    + (l.validado ? `<span class="ok">✓ ${escDados(l.validado)}</span>`
                  : `<span class="wh">📷</span>`) + `</li>`;
}
function lotesHTML(lotes, aberto) {
  if (!lotes.length) return `<p class="vazio">Nada nesta fila.</p>`;
  return lotes.map((lo, i) =>
    `<details class="lote"${i < aberto ? ' open' : ''}><summary>`
    + `<span>Lote ${lo.n} · cópias ${lo.de}–${lo.ate}</span>`
    + `<span class="lm">${lo.feitas} de ${lo.copias} feitas · ${eur(lo.valor)}</span>`
    + `</summary><div class="lb"><ul class="fl">`
    + lo.linhas.map(filaLinha).join('') + `</ul></div></details>`).join('');
}
function fase2(p) {
  if (!p.filas.length) {
    return `<h2>Fase 2 · Fotos dos decks</h2><p class="vazio">Nenhum deck está `
      + `montado com cartas lá dentro, por isso não há nada para confirmar.</p>`;
  }
  return `<h2>Fase 2 · Fotos dos decks <span class="n">${p.decks} decks, `
    + `${p.barra.copias} cópias</span></h2>`
    + `<p class="sub">As cartas dos decks que ficam <b>montados</b>, para `
    + `confirmares que cada deck está fisicamente completo antes de 10/10. `
    + `A fila conta <b>cópias</b>: um playset são quatro fotos.</p>`
    + barraHTML(p.barra)
    + p.filas.map(f => `<h2>${escDados(f.nome)} <span class="n">`
        + `${f.barra.copias} cópias · ${eur(f.barra.valor)}</span></h2>`
        + barraHTML(f.barra) + lotesHTML(f.lotes, 1)).join('');
}
function fase4(p) {
  return `<h2>Fase 4 · Fotos dos candidatos <span class="n">`
    + `${p.barra.copias} cópias em ${p.lotes.length} lotes</span></h2>`
    + `<p class="sub">Depois de Ghent. A fila é <b>por carta, da mais cara para `
    + `a mais barata</b> — foi o que pediste —, em lotes de ${p.lote} cópias, e `
    + `cada linha diz onde a cópia está guardada para a ires buscar.</p>`
    + barraHTML(p.barra) + lotesHTML(p.lotes, 1);
}
function inventario(p) {
  return `<h2>Inventário <span class="n">${p.barra.copias} cópias · `
    + `${eur(p.barra.valor)}</span></h2>`
    + `<p class="sub">${escDados(p.nota)} São as fotos da Reserved List e das `
    + `shock/fetchlands, para teres registo do que vale mais.</p>`
    + p.grupos.map(g => `<h2>${escDados(g.titulo)} <span class="n">`
        + `${g.barra.copias} cópias · ${eur(g.barra.valor)}</span></h2>`
        + barraHTML(g.barra) + lotesHTML(g.lotes, 0)).join('');
}

/* ------------------------------------------------------------- FASE 3 */
function fase3(p) {
  const c = p.candidatos;
  const linhas = c.linhas.map(l =>
    `<tr><td>${escDados(l.nm)}${l.rl ? ' <span class="prot">RL</span>' : ''}</td>`
    + `<td class="mot">${escDados(l.set)} ${escDados((l.lang || '').toUpperCase())}`
    + `${l.foil ? ' ✨' : ''} · ${escDados(l.cond || '')}</td>`
    + `<td class="mot">${escDados(l.local || '')}</td>`
    + `<td class="v">${l.q}</td><td class="v">${eur(l.total)}</td></tr>`).join('');
  const prot = c.protegidas.map(l =>
    `<tr><td>${escDados(l.nm)}</td>`
    + `<td class="mot">${escDados(l.set)} ${escDados((l.lang || '').toUpperCase())}`
    + `${l.foil ? ' ✨' : ''}</td>`
    + `<td class="mot">${escDados(l.motivo)}</td>`
    + `<td class="v">${l.q}</td><td class="v">${eur(l.total)}</td></tr>`).join('');
  const porp = Object.entries(c.por_proteccao).map(([, v]) =>
    `<span class="chip"><b>${v.copias}</b> ${escDados(v.rotulo)} · ${eur(v.valor)}</span>`
    ).join('');
  return `<h2>Fase 3 · Candidatos <span class="n">${c.copias} cópias, `
    + `${c.cartas} cartas</span></h2>`
    + `<p class="sub">Sai sozinha das decisões da Fase 1, com as quatro `
    + `proteções aplicadas. <b>Só leitura</b> — aqui não se vende nada.</p>`
    + `<div class="chips"><span class="chip gold"><b>${eur(c.valor)}</b> candidato`
    + `</span>${porp}</div>`
    + `<table class="cd"><thead><tr><th>Carta</th><th>Versão</th><th>Onde está`
    + `</th><th class="v">Cóp.</th><th class="v">Valor</th></tr></thead>`
    + `<tbody>${linhas || '<tr><td colspan=5 class="vazio">Nada candidato.</td></tr>'}`
    + `</tbody></table>`
    + `<h2>Protegidas <span class="n">${c.protegidas_copias} cópias · `
    + `${eur(c.protegidas_valor)}</span></h2>`
    + `<p class="sub">Cada linha diz <b>qual</b> das quatro regras a apanhou e `
    + `<b>porquê</b>. Sem motivo não há exclusão silenciosa.</p>`
    + `<table class="cd"><thead><tr><th>Carta</th><th>Versão</th><th>Porque está `
    + `protegida</th><th class="v">Cóp.</th><th class="v">Valor</th></tr></thead>`
    + `<tbody>${prot}</tbody></table>`;
}

/* ---------------------------------------------------------------- render */
async function parte(nome) {
  if (D.partes && D.partes[nome]) return D.partes[nome];
  if (PARTES[nome]) return PARTES[nome];
  PARTES[nome] = await carregaDados('arrumacao/' + nome + '.json');
  return PARTES[nome];
}
function barra() {
  const b = el('fasebar');
  if (!b) return;
  const nq = {f1: D.decks.length, f2: D.totais.fase2_copias,
              f3: D.totais.candidatos_copias, f4: D.totais.fase4_copias,
              inv: D.totais.inventario_copias};
  b.innerHTML = ABAS.map(([k, rot]) =>
    `<button type="button" data-aba="${k}" class="${ABA === k ? 'cur' : ''}`
    + `${k === 'inv' ? ' par' : ''}">${escDados(rot)}`
    + `<span class="nq">${nq[k]}</span></button>`).join('');
}
async function render() {
  const v = el('vista');
  barra();
  const t = el('trava');
  if (t) {
    t.hidden = !D.congelada;
    if (D.congelada) t.textContent = '🔒 ' + D.motivo_congelado;
  }
  try {
    if (ABA === 'f1') v.innerHTML = fase1();
    else {
      v.innerHTML = '<p class="carregando">a carregar…</p>';
      if (ABA === 'f2') v.innerHTML = fase2(await parte('fase2'));
      else if (ABA === 'f3') v.innerHTML = fase3(await parte('candidatos'));
      else if (ABA === 'f4') v.innerHTML = fase4(await parte('fase4'));
      else v.innerHTML = inventario(await parte('inventario'));
    }
  } catch (e) { erroDados(v, e); return; }
  try { history.replaceState(null, '', '#' + ABA); } catch (e) { /* file:// */ }
}
function ligar() {
  // O harness de node (`tests/abrir_pagina.js`) desenha o HTML num DOM mínimo
  // que não tem `addEventListener` — e não faz falta: ali o que se mede é o que
  // o `render()` escreveu, não o que acontece a um toque. Sem esta guarda a
  // página rebentava no arranque e o teste de ponta a ponta nunca via a Fase 1.
  if (typeof document.addEventListener !== 'function') return;
  document.addEventListener('click', ev => {
    const b = ev.target.closest('button');
    if (!b) return;
    if (b.dataset.aba) { ABA = b.dataset.aba; render(); return; }
    if (b.dataset.dec) {
      grava({url: '/api/fase-decisao',
             dados: {slot: b.dataset.dec, decisao: b.dataset.valor}}, b);
      return;
    }
    if (b.dataset.resFora) {
      grava({url: '/api/fase-reserva',
             dados: {slot: b.dataset.resFora, act: 'remover',
                     carta: b.dataset.carta}}, b);
      return;
    }
    if (b.dataset.resAdd) {
      const i = el('novares-' + b.dataset.resAdd);
      const nm = (i && i.value || '').trim();
      if (!nm) { toast('escreve o nome da carta primeiro', true); return; }
      grava({url: '/api/fase-reserva',
             dados: {slot: b.dataset.resAdd, act: 'add', carta: nm}}, b);
    }
  });
}
async function arranca() {
  try { D = await carregaDados('arrumacao.json'); }
  catch (e) { erroDados(el('vista'), e); return; }
  const h = (location.hash || '').replace('#', '');
  if (ABAS.some(([k]) => k === h)) ABA = h;
  ligar();
  await render();
}
arranca();
"""


def _tmpl() -> str:
    """O molde é uma FUNÇÃO e não uma constante de módulo (decisão de
    2026-09-25): a barra lateral depende do config, e uma constante ficava com a
    resposta que o config deu a quem importasse o ficheiro primeiro."""
    titulo = shell.titulo_de(PAGINA) or TITULO
    return (
        "<!doctype html><html lang=pt><head>"
        + shell.head(titulo, _CSS + paginas.CSS_DADOS)
        + "</head><body>"
        + shell.abrir(PAGINA, titulo, _LEAD)
        + '<div class="trava" id="trava" hidden></div>'
          '<div class="trava" id="toast" hidden></div>'
          '<div class="fasebar" id="fasebar"></div>'
          '<div id="vista"><p class="carregando">a carregar…</p></div>'
        + shell.fechar(_RODAPE, scripts="<script>%JS%</script>")
        + "</body></html>")


# Os campos que a TABELA da Fase 3 mostra, e só esses. A linha de candidato traz
# o `set_name`, o `sid`, a fonte e a origem do preço e a caixa — nada disso se
# desenha, e com eles a parte saía em 293 KB para uma página que é para abrir no
# telemóvel. É a disciplina dos dados à parte de 2026-09-15.
_CAMPOS_TABELA = ("nm", "set", "lang", "foil", "cond", "local", "q", "total",
                  "rl", "proteccao", "motivo")


def _magra(c: dict) -> dict:
    """O pacote dos candidatos sem os campos que a página não desenha."""
    def corta(ls):
        return [{k: l[k] for k in _CAMPOS_TABELA if k in l} for l in ls]
    return dict(c, linhas=corta(c["linhas"]), protegidas=corta(c["protegidas"]))


def dados(con, rep=None, editavel: bool = False) -> tuple[dict, dict]:
    """`(índice, partes)` — a forma que o `paginas.escrever_dados` leva ao disco.

    **A Fase 1 vai INTEIRA no índice**, de propósito: é o primeiro ecrã e é a
    única fase em que ele decide — fazê-la esperar por um segundo pedido era
    pôr a decisão atrás de uma barra de progresso. As filas de fotos e a lista
    de candidatos, que são as grandes, vão numa parte cada.
    """
    from mtgvault import loadout
    rep = rep if rep is not None else loadout.report(con)
    r = fases.relatorio(con, rep)
    partes = {"fase2": r["fase2"], "candidatos": _magra(r["candidatos"]),
              "fase4": r["fase4"], "inventario": r["inventario"]}
    idx = {
        "hoje": r["hoje"], "editavel": bool(editavel),
        "congelada": r["congelada"], "congelado_ate": r["congelado_ate"],
        "motivo_congelado": r["motivo_congelado"],
        "limiar": r["limiar"],
        "terras": {k: {"n": v["n"], "nomes": v["nomes"], "regra": v["regra"]}
                   for k, v in r["terras"].items()},
        "decisoes": r["decisoes"],
        "decks": r["decks"],
        "por_decidir": sum(1 for d in r["decks"] if not d["decisao_explicita"]),
        "totais": {
            "fase2_copias": r["fase2"]["barra"]["copias"],
            "fase2_feitas": r["fase2"]["barra"]["feitas"],
            "candidatos_copias": r["candidatos"]["copias"],
            "candidatos_valor": r["candidatos"]["valor"],
            "protegidas_copias": r["candidatos"]["protegidas_copias"],
            "protegidas_valor": r["candidatos"]["protegidas_valor"],
            "fase4_copias": r["fase4"]["barra"]["copias"],
            "inventario_copias": r["inventario"]["barra"]["copias"],
        },
    }
    return idx, partes


def casca() -> str:
    """A página SEM dados — é o que o `webapp.py` serve no 8771.

    Os dados vêm a seguir, por `fetch`, de `/data/paginas/arrumacao.json`, e é o
    `?t=` desse pedido que decide se o índice leva `editavel: true` (e logo os
    botões). A mesma decisão da Deckboxes de 2026-09-15: um `GET /` que corria o
    `loadout.report` inteiro demorava segundos, e a sonda da `mtgvault-serve`
    fazia-o de 5 em 5 minutos.
    """
    return _tmpl().replace("%JS%", _JS.replace("%JS_DADOS%", paginas.JS_DADOS))


def build(con, out_path=None, rep=None):
    out = Path(out_path) if out_path else (ROOT / PAGINA)
    idx, partes = dados(con, rep)
    paginas.escrever_dados(out, "arrumacao", idx, partes)
    js = _JS.replace("%JS_DADOS%", paginas.JS_DADOS)
    out.write_text(_tmpl().replace("%JS%", js), encoding="utf-8")
    return out


def html_page(con, rep=None, editavel: bool = False) -> str:
    """A página com os dados EMBUTIDOS — é o que os testes lêem de um ficheiro
    solto (a mesma saída do `deckboxes.html_page`)."""
    idx, partes = dados(con, rep, editavel)
    idx = dict(idx, partes=partes)
    js = (_JS.replace("%JS_DADOS%", paginas.JS_DADOS)
          .replace("D = await carregaDados('arrumacao.json')",
                   "D = " + json.dumps(idx, ensure_ascii=False)))
    return _tmpl().replace("%JS%", js)


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print("arrumacao.html:", build(con))
