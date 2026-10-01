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
                                 fica montado está fisicamente completo. O
                                 BOTÃO DO ALVO DA REVALIDAÇÃO está aqui
                                 (2026-10-01): a fila estava nesta página e o
                                 botão só na Deckboxes, e ele perguntou onde é
                                 que punha as fotos — ver `alvo_actual`
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
 .fl li.ft{align-items:flex-start;gap:10px}
 .fl li.ft.ok .fn{color:var(--add)}
 .fl .fn{min-width:34px;color:var(--muted);font-size:11.5px;font-weight:700;font-variant-numeric:tabular-nums}
 .fl .fi{flex:1;display:flex;flex-direction:column;gap:2px}
 .fl .it{font-size:13px}
 .tph{margin:14px 0 4px;color:var(--accent);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
 .tph .wh{color:var(--dim);font-size:11px;font-weight:500;text-transform:none;letter-spacing:0}
 .vazio{color:var(--muted);font-size:13px;padding:16px 0}
 .alvo{border:1px solid var(--line);border-radius:var(--r);background:var(--card2);padding:13px 15px;margin:0 0 16px}
 .alvo p{margin:0 0 8px;font-size:13px;line-height:1.6}
 .alvo p:last-child{margin:0}
 .alvo .on{color:var(--accent);font-weight:600}
 .alvo .off{color:var(--warn);font-weight:600}
 .alvo .onde{color:var(--muted);font-size:12.5px}
 .alvo code{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:1px 5px;font-size:11.5px}
 .alvo button{min-height:40px;padding:8px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--muted);font:inherit;font-size:13px;font-weight:600;cursor:pointer;margin:4px 6px 0 0}
 .alvob{min-height:40px;padding:8px 14px;border-radius:10px;border:1px solid var(--accent-line);background:var(--accent-soft);color:var(--accent);font:inherit;font-size:13px;font-weight:700;cursor:pointer;margin:10px 0 0}
 .alvob.ja{border-color:var(--line);background:var(--card);color:var(--muted);cursor:default}
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
    "<p><b>Uma foto leva no máximo quatro cartas.</b> As tuas palavras: "
    "<i>«organiza o Blue farm e CDEH por tipo de carta e até 4 cartas por "
    "foto»</i> e <i>«se são 4 fotos, é 1 foto com as 4 cartas»</i>. As cópias da "
    "<b>mesma carta</b> vão sempre juntas na mesma foto — quatro Mox Opal são "
    "<b>uma</b> foto, não quatro; num deck singleton juntam-se até quatro cartas "
    "<b>diferentes</b>, agrupadas por tipo. Uma linha da coleção não se parte "
    "entre duas fotos, a não ser que sozinha passe das quatro (as vinte e nove "
    "Snow-Covered Plains), e aí a foto di-lo. <b>A barra de progresso conta "
    "FOTOS</b>, com as cartas e as linhas ao lado: é a foto que é o gesto. E uma "
    "foto com mais de quatro cartas <b>não conta como validação</b> — nas antigas "
    "(média de quase cinco cartas, até trinta e três num monte) não se consegue "
    "julgar o estado de cada uma.</p>"
    "<p><b>A ordem de trabalho: primeiro os decks de lista única.</b> Os dois de "
    "cEDH têm cartas dedicadas e uma lista cada, e é por aí que se começa. As "
    "caixas de um grupo com <b>tecto de playset sobre o grupo inteiro</b> — hoje "
    "a família de Premodern — partilham o mesmo conjunto de cartas e montam-se "
    "por conversão de uma noutra: ficam para depois, e a fila di-lo em cada "
    "uma.</p>"
    "<p><b>As fotos perdidas vêm primeiro.</b> Algumas cópias têm foto registada "
    "e o ficheiro já não está no disco. Não se inventa a foto nem se limpa o "
    "campo: são as únicas cópias sem prova nenhuma, e por isso abrem a Fase 2. "
    "<b>Nada se apaga</b> — as fotos antigas foram <b>arquivadas</b>, não "
    "apagadas, e continuam a responder por todas as outras.</p>"
    "<p><b>Onde largar as fotos — há duas portas, e as duas dão ao mesmo.</b> "
    "(a) <b>Pela página</b>, no botão «Tirar fotos» (abre a câmara do "
    "telemóvel): a foto guarda-se sozinha, não há pasta nenhuma. (b) <b>Com a "
    "app da câmara</b>, largando-as na <b>pasta do deck</b> — "
    "<code>Colocar fotos da coleção aqui\\&lt;nome do deck&gt;\\</code> —, onde o "
    "<code>_plano.txt</code> diz o que tirar; o vault reconhece a pasta como o "
    "deck (é o mesmo alvo do botão «Fotografar») e trata-as como se tivessem "
    "sido tiradas aqui. Subpastas de lote (<code>lote1</code>) contam para o "
    "mesmo deck. O que não é de um deck (a venda, o inventário) vai solto na "
    "raiz de <code>pendentes\\</code>, com o alvo fixado no botão. Nunca para "
    "<code>pendentes\\deckboxes\\</code> — essa é a foto "
    "da caixa de plástico. Estas cópias <b>já estão no inventário</b>: o que a "
    "foto faz é <b>ligar-se à cópia que já existe</b> em vez de criar outra.</p>"
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

/* ------------------------------------------------- O ALVO DA REVALIDAÇÃO */
/* A fila das fotos está NESTA página e o botão que diz «é esta caixa que estou
   a fotografar» vivia só na Deckboxes — ele perguntou onde é que punha as
   fotos, que é o sinal de que o caminho não estava à vista de onde ele
   trabalha. Fecha-se a volta aqui, com o MESMO endpoint (`/api/revalidacao`) e
   o mesmo motor (`revalidacao.definir_alvo`): um segundo caminho ao lado
   discordava do primeiro um dia qualquer, em silêncio. */
const ONDE = 'Duas portas: <b>«Tirar fotos»</b> aqui na página (a foto '
  + 'guarda-se sozinha, não há pasta), ou a app da câmara e largá-las na '
  + '<b>pasta do deck</b> — <code>Colocar fotos da coleção aqui\\&lt;nome do '
  + 'deck&gt;\\</code>, onde está o <code>_plano.txt</code>. A pasta <b>vale '
  + 'como alvo</b>: o vault reconhece-a pelo nome do deck. O que não é de um '
  + 'deck (a venda, o inventário) vai <b>solto na raiz de '
  + '<code>pendentes\\</code></b>, com o alvo fixado no botão. Nunca para '
  + '<code>pendentes\\deckboxes\\</code> (essa é a foto da caixa de plástico). '
  + 'A corrida da noite <b>liga cada foto à cópia que já existe</b> em vez de '
  + 'criar outra.';

function alvoHTML() {
  const r = D.revalidacao || {};
  if (!r.activa) {
    return `<div class="alvo"><p>A campanha de revalidação por foto está `
      + `desligada (<code>revalidacao.desde</code>), por isso não há alvo para `
      + `fixar. As fotos destas cópias passam por lá.</p></div>`;
  }
  const a = r.alvo;
  // O alvo ACTUAL em destaque, sempre: sem ele, fotografa-se uma caixa a pensar
  // que se está a fotografar outra, e a corrida da noite liga as fotos às
  // cópias erradas. O número por fotografar sai do MESMO `revalidacao.progresso`
  // que a Deckboxes mostra.
  const cab = a
    ? `<p class="on">📷 Estás a fotografar <b>${escDados(a.nome)}</b> — `
      + `<b>${cop(a.por_revalidar)}</b> por fotografar`
      + (a.em ? ` · alvo fixado em ${escDados(a.em)}` : '') + `.</p>`
    : `<p class="off">📷 <b>Não há alvo de revalidação.</b> Antes de fotografares, `
      + `escolhe no botão de cada fila o deck que tens na mão.</p>`;
  let bot = '';
  if (D.editavel && a) {
    bot = `<button type="button" data-alvo-parar="1">parar de fotografar</button>`;
  }
  return `<div class="alvo">${cab}<p class="onde">${ONDE}</p>${bot}</div>`;
}
function alvoBotao(tipo, slot, rotulo) {
  if (!D.editavel) return '';
  const a = (D.revalidacao || {}).alvo;
  const ja = a && a.tipo === tipo && (a.slot || null) === (slot || null);
  if (ja) {
    return `<button type="button" class="alvob ja" disabled>📷 é este que estás `
      + `a fotografar</button>`;
  }
  return `<button type="button" class="alvob" data-alvo-tipo="${escDados(tipo)}"`
    + (slot ? ` data-alvo-slot="${escDados(slot)}"` : '')
    + `>📷 ${escDados(rotulo)}</button>`;
}

/* ------------------------------------------------------- FASE 2 e FASE 4 */
/* A UNIDADE É A FOTO, e uma foto leva no máximo 4 CARTAS (André, 2026-10-01:
   «organiza o Blue farm e CDEH por tipo de carta e ate 4 cartas por foto», «se
   sao 4 fotos, e 1 foto com as 4 cartas»). A barra conta FOTOS — é a foto que
   é o gesto — e diz ao lado quantas CARTAS e quantas LINHAS da coleção cada
   fila cobre, que é o que ele precisa de saber para ir à estante. Esteve aqui
   escrito o contrário («a fila conta cópias físicas: um playset são quatro
   fotos»), e era quatro vezes o trabalho. Quem agrupa é o `mtgvault/fotos.py`,
   num sítio só — a mesma régua que recusa uma foto com mais de quatro. */
function barraHTML(b) {
  return `<div class="bar"><i style="width:${b.pct}%"></i></div>`
    + `<p class="barl"><b>${b.feitas}</b> de <b>${b.fotos}</b> fotos `
    + `(${b.pct} %) · ${b.cartas} cartas em ${b.linhas} linhas · `
    + `feito ${eur(b.feitas_valor)} · falta ${eur(b.falta_valor)}`
    + (b.perdidas ? ` · <b>${b.perdidas}</b> sem foto no disco` : '') + `</p>`;
}
function itemHTML(i) {
  return `<span class="it">${i.q > 1 ? `<b>${i.q}×</b> ` : ''}`
    + `${escDados(i.nm)} <span class="wh">${escDados(i.set)} `
    + `${escDados((i.lang || '').toUpperCase())}${i.foil ? ' ✨' : ''}`
    + `${i.foto_perdida ? ' ⚠' : ''}</span></span>`;
}
function fotoHTML(f) {
  return `<li class="ft${f.feita ? ' ok' : ''}">`
    + `<span class="fn">${f.feita ? '✓' : '📷'} ${f.n}</span>`
    + `<span class="fi">${f.itens.map(itemHTML).join('')}</span>`
    + `<span class="q">${f.cartas} carta${f.cartas === 1 ? '' : 's'}`
    + `${f.linhas > 1 ? ` · ${f.linhas} linhas` : ''}`
    + `${f.partida ? ' · lote partido' : ''}</span>`
    + `<span class="q">${eur(f.valor)}</span></li>`;
}
function fotosHTML(fs) {
  if (!fs.length) return `<p class="vazio">Nada nesta fila.</p>`;
  /* Agrupadas por TIPO, com o cabeçalho — é a ordem em que ele dispõe as cartas
     na mesa, e as fotos nunca atravessam um tipo. Sem tipo (a Fase 4, que é por
     preço) sai uma lista só. */
  let out = '', tipo = null;
  for (const f of fs) {
    if (f.tipo && f.tipo !== tipo) {
      if (tipo !== null) out += `</ul>`;
      const n = fs.filter(x => x.tipo === f.tipo);
      out += `<div class="tph">${escDados(f.tipo_nome)} <span class="wh">`
        + `${n.length} foto${n.length === 1 ? '' : 's'} · `
        + `${n.reduce((a, x) => a + x.cartas, 0)} cartas</span></div><ul class="fl">`;
      tipo = f.tipo;
    } else if (tipo === null) {
      out += `<ul class="fl">`;
      tipo = f.tipo || '';
    }
    out += fotoHTML(f);
  }
  return out + `</ul>`;
}
function lotesHTML(lotes, aberto) {
  if (!lotes.length) return `<p class="vazio">Nada nesta fila.</p>`;
  return lotes.map((lo, i) =>
    `<details class="lote"${i < aberto ? ' open' : ''}><summary>`
    + `<span>Lote ${lo.n} · fotos ${lo.de}–${lo.ate}</span>`
    + `<span class="lm">${lo.feitas} de ${lo.fotos} feitas · ${lo.cartas} cartas `
    + `· ${eur(lo.valor)}</span>`
    + `</summary><div class="lb">` + fotosHTML(lo.linhas) + `</div></details>`).join('');
}
/* AS FOTOS PERDIDAS abrem a Fase 2: são as únicas cópias sem prova nenhuma. */
function perdidasHTML() {
  const p = D.perdidas || {};
  if (!p.n_fotos) return '';
  return `<details class="lote" open><summary>`
    + `<span>⚠ ${p.n_fotos} fotos perdidas · ${p.copias} cópias</span>`
    + `<span class="lm">${eur(p.valor)} — fotografa estas primeiro</span>`
    + `</summary><div class="lb"><p class="sub">${escDados(p.nota)}</p>`
    + `<ul class="fl">` + (p.linhas || []).map(l =>
        `<li><span style="flex:1">${l.q > 1 ? `<b>${l.q}×</b> ` : ''}`
        + `${escDados(l.nm)}</span>`
        + `<span class="wh">${escDados(l.set)} `
        + `${escDados((l.lang || '').toUpperCase())}${l.foil ? ' ✨' : ''}</span>`
        + `<span class="wh">${escDados(l.caixa || '—')}</span>`
        + `<span class="q">${eur(l.total)}</span></li>`).join('')
    + `</ul></div></details>`;
}
function fase2(p) {
  if (!p.filas.length) {
    return `<h2>Fase 2 · Fotos dos decks</h2><p class="vazio">Nenhum deck está `
      + `montado com cartas lá dentro, por isso não há nada para confirmar.</p>`;
  }
  return `<h2>Fase 2 · Fotos dos decks <span class="n">${p.decks} decks, `
    + `${p.barra.fotos} fotos, ${p.barra.cartas} cartas</span></h2>`
    + `<p class="sub">As cartas dos decks que ficam <b>montados</b>, para `
    + `confirmares que cada deck está fisicamente completo antes de 10/10. `
    + `Cada foto leva <b>até ${p.max_cartas} cartas</b>, agrupadas <b>por tipo</b>: `
    + `as cópias da mesma carta vão sempre juntas (quatro Mox Opal são uma foto) e `
    + `num deck singleton juntam-se até ${p.max_cartas} cartas diferentes do mesmo `
    + `tipo. <b>Primeiro os decks de lista única</b>; os que se montam por `
    + `conversão vêm no fim e dizem-no. `
    + `<b>Fotografar um deck não espera por 12/10</b> — a trava dessa data é para `
    + `a saída de venda, não para as fotos.</p>`
    + alvoHTML()
    + barraHTML(p.barra)
    + perdidasHTML()
    + p.filas.map(f => `<h2>${escDados(f.nome)} <span class="n">`
        + `${f.barra.fotos} fotos · ${f.barra.cartas} cartas · ${eur(f.barra.valor)}`
        + (f.conversao ? ' · ⏸ por conversão' : '') + `</span></h2>`
        + `<p class="sub">${escDados(f.nota)}</p>`
        + barraHTML(f.barra)
        + alvoBotao('caixa', f.slot, 'Fotografar este deck')
        + lotesHTML(f.lotes, 1)).join('');
}
function fase4(p) {
  // A Fase 4 usa a MESMA mecânica da Fase 2, com o alvo `venda` em vez de uma
  // caixa — o caminho está feito e abre-se SOZINHO na data da trava. Antes dela
  // não se mostra o botão: fotografar para vender antes de Ghent era começar o
  // passo que a trava existe para adiar.
  const pronto = !D.congelada
    ? alvoHTML() + alvoBotao('venda', null, 'Fotografar a venda')
    : `<div class="alvo"><p>A partir de <b>${escDados(D.congelado_ate)}</b> aparece `
      + `aqui o <b>mesmo botão da Fase 2</b>, com o alvo <b>venda</b>: a mecânica `
      + `das fotos é a mesma e o caminho já está feito. Até lá não se abre — antes `
      + `de Ghent não sai nada para venda.</p><p class="onde">${ONDE}</p></div>`;
  return `<h2>Fase 4 · Fotos dos candidatos <span class="n">`
    + `${p.barra.fotos} fotos (${p.barra.cartas} cartas) em ${p.lotes.length} `
    + `lotes</span></h2>`
    + `<p class="sub">Depois de Ghent. A fila é <b>por carta, da mais cara para `
    + `a mais barata</b> — foi o que pediste —, em fotos de até ${p.max_cartas} `
    + `cartas e lotes de ${p.lote} fotos. Aqui <b>não se agrupa por tipo</b>: a `
    + `ordem é o preço, e agrupar por tipo era trocar a ordem que pediste. As que `
    + `não têm foto no disco vêm à cabeça.</p>`
    + pronto
    + barraHTML(p.barra) + lotesHTML(p.lotes, 1);
}
function inventario(p) {
  return `<h2>Inventário <span class="n">${p.barra.fotos} fotos `
    + `(${p.barra.cartas} cartas) · ${eur(p.barra.valor)}</span></h2>`
    + `<p class="sub">${escDados(p.nota)} São as fotos da Reserved List e das `
    + `shock/fetchlands, para teres registo do que vale mais — em fotos de até `
    + `${p.max_cartas} cartas, como tudo o resto.</p>`
    + p.grupos.map(g => `<h2>${escDados(g.titulo)} <span class="n">`
        + `${g.barra.fotos} fotos · ${g.barra.cartas} cartas · `
        + `${eur(g.barra.valor)}</span></h2>`
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
  const nq = {f1: D.decks.length, f2: D.totais.fase2_fotos,
              f3: D.totais.candidatos_copias, f4: D.totais.fase4_fotos,
              inv: D.totais.inventario_fotos};
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
    if (b.dataset.alvoTipo) {
      // O MESMO endpoint do botão «Fotografar esta caixa» da Deckboxes: fixa
      // `revalidacao.alvo` no config e reescreve o `pendentes/esperadas.md`.
      grava({url: '/api/revalidacao',
             dados: {act: 'alvo', tipo: b.dataset.alvoTipo,
                     slot: b.dataset.alvoSlot || null}}, b);
      return;
    }
    if (b.dataset.alvoParar) {
      grava({url: '/api/revalidacao', dados: {act: 'parar'}}, b);
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


def alvo_actual(con, rep) -> dict:
    """O ALVO da revalidação, para a Fase 2 dizer sempre onde ele está.

    A revalidação de 2026-09-20 é o caminho destas fotos — a foto LIGA-SE à
    cópia que já existe em vez de criar outra —, mas o botão que fixa o alvo
    vivia só na Deckboxes. A fila está nesta página e ele perguntou onde é que
    punha as fotos: o botão tem de estar onde ele trabalha.

    O número por fotografar sai do **mesmo `revalidacao.progresso`** que a
    Deckboxes mostra, e não de uma contagem própria — duas contagens da mesma
    coisa discordam um dia em silêncio. Só se calcula **quando há alvo**: sem
    alvo não há número para mostrar, e o progresso percorre a colecção inteira.

    Nada aqui é travado pelo `venda.congelado_ate`: a trava é para a SAÍDA de
    venda, e as fotos dos decks são de ANTES de Ghent.
    """
    from mtgvault import revalidacao
    base = {"desde": revalidacao.desde(), "activa": revalidacao.activa(),
            "alvo": None}
    if revalidacao.alvo() is None:
        return base
    prog = revalidacao.progresso(con, rep)
    return {"desde": prog["desde"], "activa": prog["activa"],
            "alvo": prog["alvo"]}


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
        # O alvo da revalidação (2026-10-01): a Fase 2 é a fila das fotos e o
        # botão que fixa o alvo estava noutra página. Ver `alvo_actual`.
        "revalidacao": alvo_actual(con, rep),
        "decks": r["decks"],
        "por_decidir": sum(1 for d in r["decks"] if not d["decisao_explicita"]),
        # AS FOTOS PERDIDAS (2026-10-01) vão no ÍNDICE e não numa parte: são 33
        # fotos e abrem a Fase 2 — fazê-las esperar por um segundo pedido era
        # esconder a única coisa que não tem prova nenhuma.
        "perdidas": r["perdidas"],
        "max_cartas_foto": r["max_cartas_foto"],
        "totais": {
            # A unidade é a FOTO (as cartas e as linhas ao lado). Era `*_copias`
            # e contava cópias: um playset dizia «4 fotos».
            "fase2_fotos": r["fase2"]["barra"]["fotos"],
            "fase2_cartas": r["fase2"]["barra"]["cartas"],
            "fase2_feitas": r["fase2"]["barra"]["feitas"],
            "candidatos_copias": r["candidatos"]["copias"],
            "candidatos_valor": r["candidatos"]["valor"],
            "protegidas_copias": r["candidatos"]["protegidas_copias"],
            "protegidas_valor": r["candidatos"]["protegidas_valor"],
            "fase4_fotos": r["fase4"]["barra"]["fotos"],
            "fase4_cartas": r["fase4"]["barra"]["cartas"],
            "inventario_fotos": r["inventario"]["barra"]["fotos"],
            "inventario_cartas": r["inventario"]["barra"]["cartas"],
            "perdidas_fotos": r["perdidas"]["n_fotos"],
            "perdidas_copias": r["perdidas"]["copias"],
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
