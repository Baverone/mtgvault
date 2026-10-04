"""Gera decks.html — A ABA DECKS (André, 2026-10-04, à letra).

    *"Fazemos como no riftvault, fazes uma aba ou botao para decks:
      Dentro dos decks, formato,
      Dentro do formato, o nome do deck
      ordena por tipo de carta"*

O motor está em `mtgvault/decks_vista.py` (o registo, a regra soma-vs-máximo, as
próprias e as partilhadas, os proxies) e em `mtgvault/marcas.py` (o `+` e o `−`).
Esta é a vista — **TRÊS NÍVEIS, CADA UM COM URL PRÓPRIA**, para ele poder guardar
qualquer um nos favoritos do telemóvel:

    decks.html                            os formatos
    decks.html#f=premodern                os decks desse formato, pela % que tem
    decks.html#f=premodern&d=caixa:...    as cartas, por tipo, com + e −

O QUE SE REAPROVEITOU DO RIFTVAULT (`Desktop\\Riftbound\\riftvault`), em vez de
inventar outro padrão — ele pediu *"como no riftvault"*:

  * **o tile** (`web/app.js: tileHTML`): `.art` com `aspect-ratio`, a `<img>` com
    `loading=lazy` e `decoding=async`, os crachás POR CIMA da imagem e os dois
    botões `−`/`+` por baixo, com 40 px de altura mínima (`web/style.css: .step`);
  * **a cor diz se ele tem** (`.tile.none .art img { filter: grayscale(1)
    brightness(.42) }`) — a mesma foto, sem uma segunda imagem e sem um segundo
    pedido ao CDN;
  * **a escrita é um DELTA com `request_id`** (`collection.adjust`), nunca um
    valor absoluto do cliente, com a soma dentro de uma transacção: cliques
    rápidos seguidos não se perdem e um retry de rede não conta a dobrar;
  * **o optimismo com contador em voo** (`app.js: adjust` + `state.pending`): o
    ecrã anda já e só a última resposta manda, senão uma resposta atrasada punha
    o contador para trás;
  * **um só `addEventListener` delegado** por contentor, e `body.readonly` a
    esconder os controlos de escrita no site publicado.

O que NÃO se copiou, e é decisão: no riftvault o tile de DECK **não tem** `+`/`−`
(revogados a 2026-10-01: *"no deck nao precisa + e - / ele ja indica se tem ou
nao tem"*). Aqui tem, porque é o que ele pediu em palavras para o mtgvault —
*"com + e - para eu marcar se tenho a carta"* — e porque aqui o `+`/`−` é a ÚNICA
porta da posse (no riftvault a posse vive na Coleção, que é outra página).

O PESO, que é metade do trabalho: casca leve e **dados à parte** (2026-09-15) —
o índice leva os formatos e a ficha de cada deck SEM as cartas; a lista de cada
deck é uma parte, ida buscar quando ele abre o deck. As imagens são REMOTAS
(`cards.scryfall.io`, pelo `paginas.art`), nunca embutidas nem descarregadas para
o repositório.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from mtgvault import decks_vista as dv
from mtgvault import marcas, paginas
from mtgvault import site_shell as shell

ROOT = Path(__file__).resolve().parent
PAGINA = "decks.html"
#: O rótulo da barra lateral. O `<h1>` tem de ser O MESMO (decisão da 2.ª
#: passagem de 2026-09-24, com teste).
TITULO = "Decks"
_LEAD = ("formato → deck → cartas. O `+` e o `−` de cada carta são a tua posse: "
         "o que vem do inventário está marcado como tal, e o que marcares ganha.")

#: O TECTO DE BYTES DA CASCA, e a justificação (a ordem exige as duas).
#:
#: **MEDIDA a 2026-10-04: 50 293 bytes** (a casca partilhada do `site_shell`,
#: mais o CSS e o JavaScript desta página). O tecto é **80 KB**, e o número
#: escolhe-se assim: fica ACIMA da medida com 60 % de folga (para o CSS e o JS
#: poderem crescer sem obrigar a mexer no tecto a cada ordem) e ABAIXO dos 74 KB
#: do `test_telemovel` **mais** o `deckboxes.js` — ou seja, esta página continua
#: a ser mais leve do que a Deckboxes de ponta a ponta, e é a Deckboxes que
#: define o que o telemóvel dele já aguenta pela rede de casa.
#:
#: O que este número defende é esse telemóvel, e o que o faz subir é JavaScript.
#: Se passar daqui, o passo seguinte é tirá-lo para um `decks.js` com hash no
#: `?v=`, como a Deckboxes fez a 2026-09-18 — com o custo de mais uma entrada
#: nas duas listas de `git add` e de o site ficar sem comportamento se faltar lá.
TECTO_CASCA = 80 * 1024

_CSS = """
 .fmts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:stretch}
 @media(max-width:860px){.fmts{grid-template-columns:repeat(2,minmax(0,1fr))}}
 @media(max-width:380px){.fmts{grid-template-columns:1fr}}
 .fcard{display:flex;flex-direction:column;gap:8px;text-align:left;background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:14px 15px;color:var(--ink);font:inherit;cursor:pointer}
 .fcard:hover{border-color:var(--line2)}
 .fcard .fn{font-family:var(--font-hd);font-size:16px;font-weight:700}
 .fcard .fl{font-size:12px;color:var(--muted);line-height:1.55}
 .fcard .fm{font-size:11px;color:var(--dim);margin-top:auto}
 .modo{display:inline-block;border-radius:999px;padding:2px 9px;font-size:10.5px;font-weight:700;letter-spacing:.3px;border:1px solid var(--line2);color:var(--muted)}
 .modo.rot{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 .modo.ded{border-color:#2f4a7a;background:var(--info-soft);color:var(--ob)}
 .migalha{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 16px;font-size:13px;color:var(--muted)}
 .migalha button{min-height:36px;padding:6px 13px;border-radius:999px;border:1px solid var(--line);background:var(--card2);color:var(--ink2);font:inherit;font-size:12.5px;cursor:pointer}
 .chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
 .chip{background:var(--card2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:12px;color:var(--muted)}
 .chip b{color:var(--ink)}
 .chip.gold{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 .chip.inv{border-color:#2f4a7a;background:var(--info-soft);color:var(--ob)}
 /* OS DOIS NÚMEROS LADO A LADO: é a diferença entre eles que diz o que custa. */
 .duo{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 16px}
 .duo .n{flex:1 1 180px;background:var(--card2);border:1px solid var(--line);border-radius:var(--r);padding:11px 14px}
 .duo .n.manda{border-color:var(--accent-line);background:var(--accent-soft)}
 .duo .n .et{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px}
 .duo .n .v{font-family:var(--font-hd);font-size:20px;font-weight:700;color:var(--ink)}
 .duo .n.manda .v{color:var(--accent)}
 .duo .n .sub{font-size:11.5px;color:var(--muted);margin-top:2px}
 .dlist{display:flex;flex-direction:column;gap:8px}
 .drow{display:flex;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:10px 13px}
 .drow.quero{border-color:var(--accent-line)}
 .drow .dn{flex:1;min-width:0}
 .drow .dnome{font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .drow .dsub{font-size:11.5px;color:var(--dim);line-height:1.5}
 .drow .dpct{font-family:var(--font-hd);font-size:15px;font-weight:700;min-width:46px;text-align:right}
 .drow .dpct.ok{color:var(--add)} .drow .dpct.mid{color:var(--accent)} .drow .dpct.lo{color:var(--muted)}
 .bar{height:4px;border-radius:3px;background:var(--line);overflow:hidden;margin-top:5px}
 .bar i{display:block;height:100%;background:var(--accent)}
 .bar i.ok{background:var(--add)}
 .qm{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted);cursor:pointer;min-height:40px;padding:0 4px}
 .qm input{width:20px;height:20px;accent-color:var(--accent)}
 .verd{min-height:40px;padding:7px 14px;border-radius:999px;border:1px solid var(--line);background:var(--card2);color:var(--ink2);font:inherit;font-size:12.5px;cursor:pointer}
 /* --- A GRELHA DE CARTAS: o tile do riftvault (web/app.js + web/style.css) --- */
 .typehdr{display:flex;align-items:baseline;gap:8px;margin:20px 0 9px;font-family:var(--font-hd);font-size:14px;font-weight:700;color:var(--ink)}
 .typehdr .nq{font-size:11px;color:var(--dim);font-weight:400}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:11px}
 @media(max-width:640px){.grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}}
 .tile{position:relative;display:flex;flex-direction:column;gap:5px}
 .art{position:relative;display:block;width:100%;aspect-ratio:.716;border-radius:8px;overflow:hidden;background:var(--card2);border:1px solid var(--line)}
 .art img{width:100%;height:100%;object-fit:cover;display:block;transition:filter .2s}
 /* Sem nenhuma: dessaturada e escurecida — o padrão do riftvault. */
 .tile.none .art img{filter:grayscale(1) brightness(.42)}
 .tile.none .art{border-color:#5a2b2b}
 .tile.done .art{border-color:rgba(79,208,138,.55)}
 .tile.parte .art{border-color:var(--accent-line)}
 .tile .nm{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:6px;font-size:10.5px;line-height:1.3;text-align:center;color:var(--muted)}
 .need{position:absolute;left:4px;top:4px;font-size:11px;font-weight:700;background:rgba(0,0,0,.78);color:#fff;border-radius:5px;padding:2px 6px}
 .badge{position:absolute;right:4px;bottom:4px;font-size:11px;font-weight:700;background:rgba(0,0,0,.78);color:#fff;border-radius:5px;padding:2px 6px}
 .badge.ok{background:rgba(79,208,138,.92);color:#07130c}
 .badge.no{background:rgba(255,123,123,.92);color:#210a0a}
 .sh{position:absolute;left:4px;bottom:4px;font-size:9.5px;font-weight:700;background:rgba(245,196,81,.92);color:var(--accent-ink);border-radius:5px;padding:1px 5px}
 .tname{font-size:11.5px;line-height:1.35;color:var(--ink2);overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
 .orig{font-size:10px;color:var(--dim)}
 .orig.mk{color:var(--accent)}
 .steppers{display:flex;gap:6px}
 .step{flex:1;min-height:40px;background:var(--card2);color:var(--ink);border:1px solid var(--line);border-radius:9px;font:inherit;font-size:18px;font-weight:700;line-height:1;cursor:pointer;touch-action:manipulation}
 .step:active{background:var(--accent);color:var(--accent-ink);transform:scale(.96)}
 .step.minus:disabled{opacity:.3;cursor:default}
 body.readonly .steppers{display:none}
 .sec{margin:26px 0 0;padding-top:18px;border-top:1px solid var(--line)}
 .sec h3{font-family:var(--font-hd);font-size:15px;margin:0 0 4px}
 .sec p{font-size:12.5px;color:var(--muted);line-height:1.6;margin:0 0 10px}
 .px{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 6px}
 .px span{background:var(--card2);border:1px solid var(--accent-line);color:var(--accent);border-radius:7px;padding:3px 9px;font-size:11.5px}
 .vazio{color:var(--muted);font-size:13px;padding:14px 0}
 #toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:60;max-width:92vw;background:var(--card3);border:1px solid var(--line2);color:var(--ink);border-radius:999px;padding:10px 18px;font-size:13px;box-shadow:var(--sombra)}
 #toast.err{border-color:var(--warn);color:var(--warn)}
"""

_RODAPE = """
<b>Como ler esta página.</b> São três níveis — formatos, decks, cartas — e cada
um tem URL própria (<code>decks.html#f=premodern</code>,
<code>decks.html#f=premodern&amp;d=…</code>), para guardares qualquer um nos
favoritos.
<br><b>O «tens X de Y».</b> Conta CÓPIAS e não nomes, e a posse de cada carta
trava no que o deck pede. O <b>sideboard conta à parte do main</b> e os dois
somam o total: tens de o montar à parte. Não há alocação aqui — quem reparte a
colecção entre as caixas montadas é a Deck boxes.
<br><b>A posse vem de dois sítios e eles nunca se confundem.</b> «do inventário»
é o que a colecção já registava; «marcaste tu» é o que tocaste com o
<code>+</code>/<code>−</code>, com a data, e <b>ganha sempre</b>. Nada se apaga:
a tua marca fica POR CIMA do registo, e o registo continua lá.
<br><b>«a somar» e «a rodar».</b> Mostram-se sempre os dois, mesmo o que a regra
do formato não usa, porque é a diferença entre eles que diz o que a decisão
custa. Nos formatos <i>rotativos</i> (Premodern, SPML) uma cópia verdadeira serve
todos os decks: a carta que entra em dois ou mais fica de fora, leva proxy, e a
verdadeira entra à hora de jogar — a necessidade é o MÁXIMO. Nos <i>dedicados</i>
(cEDH, Duel Commander, Pauper) cada deck tem as suas: a necessidade é a SOMA.
<br><b>Própria ou partilhada não é uma etiqueta da carta</b>: depende de quais
decks marcaste. Marcar mais um deck pode passar uma carta de própria a
partilhada, e desmarcar faz o caminho de volta.
<br><b>Os arquétipos meta</b> são identificados pelo <b>nome que o mtgtop8 dá</b>
a cada deck na página do evento, e nunca pela etiqueta do agrupamento. Quem
decide que listas contam é a regra de cada formato
(<code>metagame_fontes</code>); o registo vê todas as que contam e a lista de
cada um vem da janela do consenso — são duas perguntas.
"""

_JS = r"""
%JS_DADOS%
let D = null, PARTES = {}, FMT = '', DECK = '';
const el = i => document.getElementById(i);
const esc = escDados;
function toast(t, erro) {
  const z = el('toast'); if (!z) return;
  z.textContent = t; z.className = erro ? 'err' : ''; z.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { z.hidden = true; }, erro ? 7000 : 3000);
}
const EDIT = () => !!(D && D.editavel);
/* O nome da parte de um deck: o id sem os caracteres que a rota do 8771 não
   deixa passar (`[A-Za-z0-9_-]+`). Um `slot` nunca tem `:`, por isso trocar
   `:` por `-` não junta dois decks diferentes. A MESMA conta no Python
   (`decks.parte_do_deck`) — se as duas discordarem, o `fetch` dá 404 e a
   página di-lo em português em vez de ficar vazia. */
const parteDoDeck = id => String(id).replace(/[^A-Za-z0-9_-]+/g, '-');

async function parte(nome) {
  if (PARTES[nome]) return PARTES[nome];
  if (D && D.partes && D.partes[nome]) { PARTES[nome] = D.partes[nome]; return PARTES[nome]; }
  PARTES[nome] = await carregaDados('decks/' + nome + '.json');
  return PARTES[nome];
}

/* --------------------------------------------------------------- nível 1 */
function nivelFormatos() {
  const f = D.formatos;
  if (!f.length) return '<p class="vazio">Não há nenhum deck registado.</p>';
  const chips = `<div class="chips"><span class="chip inv">${esc(D.frase_marcas)}</span></div>`;
  return chips + '<div class="fmts">' + f.map(x => {
    const n = x.necessidade || {};
    return `<button class="fcard" data-f="${esc(x.formato)}">
      <span class="fn">${esc(x.formato)}</span>
      <span class="modo ${x.modo === 'rotativas' ? 'rot' : 'ded'}">${
        x.modo === 'rotativas' ? 'cartas rodam' : 'cartas dedicadas'}</span>
      <span class="fl"><b>${x.n_decks}</b> deck${x.n_decks === 1 ? '' : 's'} registado${
        x.n_decks === 1 ? '' : 's'} · <b>${x.n_marcados}</b> que queres montar</span>
      <span class="fl">a somar <b>${n.soma || 0}</b> · a rodar <b>${n.maximo || 0}</b>${
        n.cartas ? ` · ${n.cartas} cartas distintas` : ''}</span>
      <span class="fm">${esc(x.texto_modo)}</span>
    </button>`;
  }).join('') + '</div>';
}

/* --------------------------------------------------------------- nível 2 */
function nivelDecks(x) {
  const n = x.necessidade || {}, rot = x.modo === 'rotativas';
  const manda = k => (rot ? k === 'rodar' : k === 'somar') ? ' manda' : '';
  let out = `<div class="migalha"><button data-f="">◀ formatos</button>
    <span><b>${esc(x.formato)}</b> — ${esc(x.texto_modo)}</span></div>`;
  out += `<div class="duo">
    <div class="n${manda('somar')}"><span class="et">a somar</span>
      <div class="v">${n.soma || 0}</div>
      <div class="sub">cada deck as suas · faltam ${n.faltam_a_somar || 0}</div></div>
    <div class="n${manda('rodar')}"><span class="et">a rodar</span>
      <div class="v">${n.maximo || 0}</div>
      <div class="sub">uma cópia serve todos · faltam ${n.faltam_a_rodar || 0}</div></div>
  </div>`;
  if (x.sleeves && x.sleeves.decks) {
    const s = x.sleeves;
    out += `<div class="chips"><span class="chip">sleeves: <b>${s.total}</b> cartas nos ${
      s.decks} decks marcados</span><span class="chip">verdadeiras <b>${s.reais}</b></span>`
      + `<span class="chip gold">proxies <b>${s.proxies}</b></span></div>`;
  }
  if (x.meta_fora) {
    out += `<div class="chips"><span class="chip">o mtgtop8 tem <b>${x.meta_fora}</b>`
      + ` arquétipos neste formato e não se oferecem aqui: as cartas são dedicadas,`
      + ` e os decks deste formato são os teus</span></div>`;
  }
  out += '<div class="dlist">' + x.decks.map(d => {
    const cl = d.pct >= 95 ? 'ok' : d.pct >= 50 ? 'mid' : 'lo';
    const sub = [];
    if (d.fonte === 'caixa') sub.push('deck teu' + (d.estado ? ` · ${d.estado}` : ''));
    else sub.push('meta');
    if (d.nota) sub.push(d.nota);
    if (d.ja_e_caixa) sub.push('já é uma caixa tua');
    if (d.marcado_em) sub.push('marcado em ' + d.marcado_em);
    return `<div class="drow${d.quero ? ' quero' : ''}">
      <div class="dn">
        <div class="dnome">${esc(d.nome)}</div>
        <div class="dsub">${d.sem_lista ? 'sem lista — nada para contar'
          : `tens <b>${d.tem}</b> de <b>${d.total}</b> cartas` +
            (d.side && d.side.total ? ` (main ${d.main.tem}/${d.main.total} · side ${d.side.tem}/${d.side.total})` : '')}
          ${sub.length ? ' · ' + esc(sub.join(' · ')) : ''}</div>
        <div class="bar"><i class="${cl === 'ok' ? 'ok' : ''}" style="width:${d.pct}%"></i></div>
      </div>
      <div class="dpct ${cl}">${d.sem_lista ? '—' : d.pct + '%'}</div>
      <label class="qm"><input type="checkbox" data-quero="${esc(d.id)}"${
        d.quero ? ' checked' : ''}${EDIT() ? '' : ' disabled'}> quero montar</label>
      <button class="verd" data-d="${esc(d.id)}">ver ▶</button>
    </div>`;
  }).join('') + '</div>';
  return out;
}

/* --------------------------------------------------------------- nível 3 */
function tileHTML(c, rot) {
  const falta = Math.max(0, c.q - c.tenho);
  const cls = c.tenho <= 0 ? 'none' : (falta ? 'parte' : 'done');
  const src = c.sid ? ART(c.sid) : '';
  const marcado = c.origem === 'marcado';
  return `<div class="tile ${cls}" data-nm="${esc(c.nm)}">
    <div class="art">
      ${src ? `<img src="${src}" alt="${esc(c.nm)}" width="146" height="204"
        loading="lazy" decoding="async" onerror="this.remove()">`
        : `<span class="nm">${esc(c.nm)}</span>`}
      <span class="need">${c.q}&times;</span>
      <span class="badge ${falta ? (c.tenho ? '' : 'no') : 'ok'}">${c.tenho}/${c.q}</span>
      ${rot && c.partilhada ? '<span class="sh">proxy</span>' : ''}
    </div>
    <div class="tname" title="${esc(c.nm)}">${esc(c.nm)}</div>
    <div class="orig${marcado ? ' mk' : ''}">${marcado
      ? 'marcaste tu' + (c.em ? ' · ' + esc(c.em) : '') : 'do inventário'}</div>
    <div class="steppers">
      <button class="step minus" data-mais="-1" data-carta="${esc(c.nm)}"
        aria-label="menos uma de ${esc(c.nm)}"${c.tenho <= 0 ? ' disabled' : ''}>&minus;</button>
      <button class="step plus" data-mais="1" data-carta="${esc(c.nm)}"
        aria-label="mais uma de ${esc(c.nm)}">+</button>
    </div>
  </div>`;
}
const ART = sid => `https://cards.scryfall.io/small/front/${sid[0]}/${sid[1]}/${sid}.jpg`;

function blocos(gs, rot) {
  return gs.map(g => `<div class="typehdr">${esc(g.tipo)}<span class="nq">${g.q}</span></div>`
    + '<div class="grid">' + g.cartas.map(c => tileHTML(c, rot)).join('') + '</div>').join('');
}

function nivelDeck(p, fmt) {
  const rot = p.modo === 'rotativas', c = p.conta;
  let out = `<div class="migalha"><button data-f="">◀ formatos</button>
    <button data-f="${esc(fmt)}">◀ ${esc(fmt)}</button>
    <span><b>${esc(p.nome)}</b></span></div>`;
  const chips = [`<span class="chip">tens <b>${c.tem}</b> de <b>${c.total}</b> — <b>${c.pct}%</b></span>`];
  if (c.side.total) chips.push(`<span class="chip">main ${c.main.tem}/${c.main.total} · `
    + `side ${c.side.tem}/${c.side.total}</span>`);
  if (p.comandante) chips.push(`<span class="chip gold">comandante: ${esc(p.comandante)}</span>`);
  if (p.reparticao) chips.push(`<span class="chip">próprias <b>${p.reparticao.n_proprias}</b></span>`,
    `<span class="chip gold">partilhadas <b>${p.reparticao.n_partilhadas}</b> (levam proxy)</span>`);
  out += '<div class="chips">' + chips.join('') + '</div>';
  if (p.nota || p.link) {
    out += '<div class="chips">'
      + (p.nota ? `<span class="chip">${esc(p.nota)}</span>` : '')
      + (p.link ? `<a class="chip" href="${esc(p.link)}" target="_blank" rel="noopener">`
          + 'abrir a lista na fonte ↗</a>' : '') + '</div>';
  }
  if (!p.main.length && !p.side.length) {
    return out + '<p class="vazio">Este deck ainda não tem lista.</p>';
  }
  out += blocos(p.main, rot);
  /* O SIDEBOARD À PARTE, com os mesmos grupos por dentro: ele tem de o montar
     à parte, e misturá-lo com o main não lhe diz se já pode ir jogar. */
  if (p.side.length) {
    out += `<div class="sec"><h3>Sideboard</h3><p>${c.side.tem} de ${c.side.total} cartas`
      + ' — conta à parte do main.</p></div>' + blocos(p.side, rot);
  }
  if (p.reparticao && p.reparticao.proxies.length) {
    out += `<div class="sec"><h3>Proxies a imprimir (${p.reparticao.n_partilhadas})</h3>`
      + '<p>São exactamente as cartas partilhadas deste deck: ficam de fora, o deck leva'
      + ' o proxy, e a verdadeira entra à hora de jogar.</p><div class="px">'
      + p.reparticao.proxies.map(x => `<span>${x.q}&times; ${esc(x.nm)}</span>`).join('')
      + '</div></div>';
  }
  return out;
}

/* ----------------------------------------------------------------- render */
async function render() {
  const v = el('vista');
  try {
    if (FMT && DECK) {
      v.innerHTML = nivelDeck(await parte('deck-' + parteDoDeck(DECK)), FMT);
    } else if (FMT) {
      const fx = D.formatos.find(x => x.formato === FMT);
      if (!fx) { FMT = ''; v.innerHTML = nivelFormatos(); }
      else v.innerHTML = nivelDecks(fx);
    } else {
      v.innerHTML = nivelFormatos();
    }
  } catch (e) { erroDados(v, e); return; }
  const h = FMT ? ('#f=' + FMT + (DECK ? '&d=' + DECK : '')) : '#';
  try { history.replaceState(null, '', h); } catch (e) { /* file:// */ }
}

function doHash() {
  let h = '';
  try { h = (location.hash || '').replace(/^#/, ''); } catch (e) {}
  const q = new URLSearchParams(h.replace(/^&/, ''));
  FMT = q.get('f') || ''; DECK = q.get('d') || '';
}

/* A ESCRITA: um DELTA com `request_id`, como no riftvault. O ecrã anda já e só
   a última resposta manda — uma resposta atrasada punha o contador para trás. */
const EM_VOO = new Map();
async function mais(nome, delta, tile) {
  if (!EDIT()) { toast('esta página é só de leitura — abre o modo de edição', true); return; }
  const b = tile.querySelector('.badge'), st = tile.querySelectorAll('.step');
  const pede = Number((tile.querySelector('.need').textContent || '0').replace(/\D/g, ''));
  let tenho = Number((b.textContent || '0/0').split('/')[0]);
  if (delta < 0 && tenho <= 0) return;
  tenho = Math.max(0, tenho + delta);
  pinta(tile, tenho, pede);
  EM_VOO.set(nome, (EM_VOO.get(nome) || 0) + 1);
  const rid = (self.crypto && crypto.randomUUID) ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  try {
    const r = await fetch('/api/marca' + (TOKEN_URL ? '?t=' + encodeURIComponent(TOKEN_URL) : ''), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({nome: nome, delta: delta, request_id: rid}),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || ('HTTP ' + r.status));
    const resta = (EM_VOO.get(nome) || 1) - 1;
    EM_VOO.set(nome, resta);
    if (resta === 0) {
      /* Todos os tiles desta carta (ela pode estar em dois blocos). */
      for (const t of document.querySelectorAll(`.tile[data-nm="${CSS.escape(nome)}"]`)) {
        pinta(t, j.q, Number((t.querySelector('.need').textContent || '0').replace(/\D/g, '')));
        const o = t.querySelector('.orig');
        if (o) { o.className = 'orig mk'; o.textContent = 'marcaste tu' + (j.em ? ' · ' + j.em : ''); }
      }
    }
  } catch (e) {
    EM_VOO.set(nome, Math.max(0, (EM_VOO.get(nome) || 1) - 1));
    toast('não sei se gravou: ' + e.message, true);
  }
}
function pinta(tile, tenho, pede) {
  const b = tile.querySelector('.badge');
  b.textContent = tenho + '/' + pede;
  b.className = 'badge ' + (tenho >= pede ? 'ok' : (tenho ? '' : 'no'));
  tile.className = 'tile ' + (tenho <= 0 ? 'none' : (tenho < pede ? 'parte' : 'done'));
  const m = tile.querySelector('.step.minus');
  if (m) m.disabled = tenho <= 0;
}

async function quero(id, on, cx) {
  if (!EDIT()) { cx.checked = !on; return; }
  try {
    const r = await fetch('/api/deck-montar' + (TOKEN_URL ? '?t=' + encodeURIComponent(TOKEN_URL) : ''), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: id, quero: on}),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || ('HTTP ' + r.status));
    toast(j.msg || 'gravado');
    /* A marca muda a necessidade do formato E quem é própria/partilhada: o
       índice e as partes têm de vir de novo. */
    PARTES = {};
    D = await carregaDados('decks.json');
    await render();
  } catch (e) { cx.checked = !on; toast('não sei se gravou: ' + e.message, true); }
}

function ligar() {
  /* O harness de node (`tests/abrir_pagina.js`) desenha num DOM mínimo sem
     `addEventListener` — e ali o que se mede é o que o `render()` escreveu. */
  if (typeof document.addEventListener !== 'function') return;
  document.addEventListener('click', ev => {
    const f = ev.target.closest('[data-f]');
    if (f) { FMT = f.dataset.f; DECK = ''; render(); return; }
    const d = ev.target.closest('[data-d]');
    if (d) { DECK = d.dataset.d; render(); return; }
    const s = ev.target.closest('.step');
    if (s) { mais(s.dataset.carta, Number(s.dataset.mais), s.closest('.tile')); return; }
  });
  document.addEventListener('change', ev => {
    const c = ev.target.closest('[data-quero]');
    if (c) quero(c.dataset.quero, c.checked, c);
  });
  window.addEventListener('hashchange', () => { doHash(); render(); });
}

async function arranca() {
  try { D = await carregaDados('decks.json'); }
  catch (e) { erroDados(el('vista'), e); return; }
  if (!D.editavel) document.body.classList.add('readonly');
  doHash();
  ligar();
  await render();
}
arranca();
"""


def parte_do_deck(deck_id: str) -> str:
    """O nome do ficheiro da parte de um deck.

    A rota dos dados no 8771 só deixa passar `[A-Za-z0-9_-]+`, e um id de deck
    leva `:` (`meta:premodern:enchantress`). A MESMA conta está no JavaScript
    (`parteDoDeck`) — se as duas discordarem, o `fetch` dá 404 e a página di-lo
    em português em vez de ficar vazia. Um `slot` nunca tem `:`, por isso trocar
    `:` por `-` não junta dois decks diferentes.
    """
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(deck_id))


def dados(con, cfg=None, editavel: bool = False) -> tuple[dict, dict]:
    """`(índice, partes)`. O índice leva os formatos e a ficha de cada deck SEM
    as cartas; uma parte por deck leva a lista (decisão de 2026-09-15)."""
    rep = dv.relatorio(con, cfg)
    pos = rep["pos"]
    mks = dv.marcados(cfg)
    partes: dict[str, object] = {}
    # A cache PARTILHADA pelos 83 decks: sem ela cada um pagava uma varredura da
    # `copies` inteira no `img_map` (ver `decks_vista.cache_nova`).
    cache = dv.cache_nova()
    for fx in rep["formatos"]:
        fmt = fx["formato"]
        modo = fx["modo"]
        escolhidos = [rep["decks"][l["id"]] for l in fx["decks"] if l["id"] in mks]
        reparte = dv.reparticao(escolhidos) if modo == dv.ROTATIVAS else {}
        for linha in fx["decks"]:
            d = rep["decks"][linha["id"]]
            cmdr = dv.comandante_do_deck(con, d)
            linha["comandante"] = cmdr or ""
            partes["deck-" + parte_do_deck(d["id"])] = dv.deck_para_pagina(
                con, d, pos, modo, reparte, cmdr, cache=cache)
    idx = {
        "editavel": bool(editavel),
        "formatos": rep["formatos"],
        "marcas": rep["marcas"],
        "frase_marcas": rep["frase_marcas"],
    }
    return idx, partes


def _tmpl() -> str:
    """O molde é uma FUNÇÃO e não uma constante de módulo (decisão de
    2026-09-25): a barra lateral depende do config, e uma constante ficava com a
    resposta que o config deu a quem importasse o ficheiro primeiro."""
    titulo = shell.titulo_de(PAGINA) or TITULO
    return ("<!doctype html><html lang=pt><head>"
            + shell.head(titulo, _CSS + paginas.CSS_DADOS)
            + "</head><body>"
            + shell.abrir(PAGINA, titulo, _LEAD)
            + '<div id="toast" hidden></div>'
              '<div id="vista"><p class="carregando">a carregar…</p></div>'
            + shell.fechar(_RODAPE, scripts="<script>%JS%</script>")
            + "</body></html>")


def casca() -> str:
    """A página SEM dados — é o que o `webapp.py` serve no 8771."""
    return _tmpl().replace("%JS%", _JS.replace("%JS_DADOS%", paginas.JS_DADOS))


def build(con, out_path=None, cfg=None):
    out = Path(out_path) if out_path else (ROOT / PAGINA)
    idx, partes = dados(con, cfg)
    paginas.escrever_dados(out, "decks", idx, partes)
    out.write_text(casca(), encoding="utf-8")
    return out


def html_page(con, cfg=None, editavel: bool = False) -> str:
    """A página com os dados EMBUTIDOS — é o que os testes lêem de um ficheiro
    solto (a mesma saída do `deckboxes.html_page`)."""
    idx, partes = dados(con, cfg, editavel)
    idx = dict(idx, partes=partes)
    js = (_JS.replace("%JS_DADOS%", paginas.JS_DADOS)
          .replace("D = await carregaDados('decks.json')",
                   "D = " + json.dumps(idx, ensure_ascii=False)))
    return _tmpl().replace("%JS%", js)


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        p = build(con)
        print(f"{p}: {p.stat().st_size:,} bytes (tecto {TECTO_CASCA:,})")
