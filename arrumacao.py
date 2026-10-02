"""Gera arrumacao.html — A ARRUMAÇÃO POR FASES (André, 2026-10-01 e 2026-10-02).

Ele vai arrumar a colecção por fases e pediu *"organização"* e **um sítio que
diga sempre onde está e o que vem a seguir**. O motor está em
`mtgvault/fases.py` (é lá que estão as regras R1–R5b, a leitura do `estado` de
cada caixa e a trava do RC Ghent). Esta página é a vista.

O ALVO É O TELEMÓVEL, pela rede de casa: é com o telemóvel na mão e as cartas
na mesa que ele trabalha. Por isso segue as decisões que já estavam tomadas:

* a **casca** vai no HTML e os **dados à parte** (2026-09-15) — o índice leva a
  Fase 1 (é o primeiro ecrã: não pode esperar por nada) e as filas de fotos, que
  são grandes, vão numa parte cada, idas buscar quando ele abre a fase. **A
  LISTA DE CARTAS de cada reserva saiu do índice a 2026-10-02**: sem o limiar, as
  16 reservas somavam 112 KB dos 167 — e vivem dentro de um `<details>`
  FECHADO. O resumo (quantas, quantas tens, quantas dispensaste) fica no índice,
  que é o que se lê de fora; a lista chega ao primeiro toque;
* um `fetch` que falhe **diz-lho em português** (`paginas.erroDados`), nunca um
  ecrã vazio;
* os botões só existem no **modo edição** (porto 8771) — no site publicado não
  há endpoint que grave, e um botão que não grava é pior do que botão nenhum;
* **nada aqui mexe em alocações nem na base**: lê a colecção e escreve só a
  reserva no `colecao_config.json` (com o `configio.escrever`, que preserva a
  forma do ficheiro). **O ESTADO da caixa muda-se na Deckboxes** (2026-10-02),
  que é onde esse gesto já vive e onde ele tem a caixa na mão: dois caminhos
  para o mesmo gesto discordam um dia qualquer, em silêncio.

AS QUATRO FASES, e a via paralela:

    Fase 1  OS DECKS QUE FICAM   os 16 decks, a CARTA-ASSINATURA de cada um, o
                                 ESTADO da caixa (que é quem decide se as
                                 cópias estão protegidas), a RESERVA dos 30
                                 dias com o botão «não é necessária», e as duas
                                 listas das duais (vender / comprar)
    Fase 2  FOTOS DOS DECKS      antes de Ghent: confirmar que cada deck que
                                 fica montado está fisicamente completo. O
                                 BOTÃO DO ALVO DA REVALIDAÇÃO está aqui
                                 (2026-10-01): a fila estava nesta página e o
                                 botão só na Deckboxes, e ele perguntou onde é
                                 que punha as fotos — ver `alvo_actual`
    Fase 3  VENDER               sai sozinha da Fase 1, com as regras aplicadas
                                 e o motivo de cada exclusão à vista
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
 .est{color:var(--accent);font-size:12px;font-weight:600}
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

_LEAD = ("Onde estás na arrumação da coleção e o que vem a seguir. As regras de "
         "2 de outubro de 2026 valem em todas as fases, e cada cópia que fica "
         "de fora da venda diz por que regra ficou.")

_RODAPE = (
    "<p><b>A identidade de um deck é uma carta-assinatura.</b> Nunca a etiqueta "
    "do clustering: essas chamam-se «Rotlung Reanimator / Priest of Gix / Oath "
    "of Druids», mudam de corrida para corrida e há dezenas vazias com o mesmo "
    "nome. Uma carta só apanha todas as variantes do deck — é o que serve o "
    "«Greasefang, as várias versões» —, e quando uma carta sozinha apanha "
    "decks diferentes exigem-se duas <b>em conjunção</b>, como no Engineer "
    "Welder Cam de Legacy. Um deck a quem ainda não disseste a carta fica "
    "marcado <b>à espera da carta-assinatura</b> e não recebe consenso nenhum: "
    "não se inventa a identidade de um deck.</p>"
    "<p><b>As regras das cartas.</b> <b>R1</b> — as dez <b>duais originais</b>: "
    "queres ter quatro de cada <i>fora</i> dos decks, e o que passar disso "
    "vende-se ou troca-se. As duais são Reserved List e <b>aqui manda a R1</b>, "
    "que é mais específica: a quinta cópia vai à venda apesar de ser RL. "
    "<b>R2</b> e <b>R3</b> — todas as cópias das <b>shocklands</b> e das "
    "<b>fetchlands</b> ficam protegidas: todos os acabamentos, todas as "
    "línguas, todas as repetidas, estejam ou não num deck. <b>R4</b> — a "
    "Reserved List que <i>jogas</i> (está num deck que fica, na lista de uma "
    "caixa, ou no consenso de um deck teu); o resto da Reserved List continua a "
    "passar pela regra dos 5 % de 8 de setembro. <b>R5</b> — tudo o que foi "
    "<b>jogado no último mês</b> no arquétipo de um destes decks, main ou side, "
    "mesmo que hoje esteja fora da lista. <b>R5b</b>, só no Premodern — as "
    "<b>staples de sideboard</b> do formato, pela presença nos sideboards do "
    "último mês, com o corte no config. E tudo o que não se enquadrar nestas "
    "regras vai para uma lista única: <b>VENDER</b>.</p>"
    "<p><b>As três listas de terras são derivadas do catálogo</b>, pelo texto da "
    "carta e pelos tipos, nunca escritas à mão — e a conta tem de dar dez de "
    "cada. Se não der, a página diz e para: uma proteção que fica vazia em "
    "silêncio manda shocklands para a venda sem um único erro.</p>"
    "<p><b>A reserva («maybe»).</b> Enche-se sozinha com tudo o que foi jogado "
    "no arquétipo nos últimos 30 dias, mais o que acrescentares à mão. "
    "<b>Não há limiar</b> — o travão é a janela, e a base só guarda um mês de "
    "listas. Abaixo de oito listas não se chama consenso a nada e a reserva "
    "automática fica vazia (é o caso do Ill-Gotten Gains, com três). A reserva "
    "protege só o que tens; o que não tens alimenta a lista de compras. Cada "
    "carta tem o botão <b>«não é necessária»</b>: sai da reserva daquele deck e "
    "passa a candidata a venda, fica <b>gravado com a data</b> (sobrevive à "
    "corrida da noite) e desfaz-se no <b>«voltar a pôr»</b>.</p>"
    "<p><b>Quem decide é o estado da caixa.</b> <i>Montada</i>, <i>congelada</i> "
    "e <i>permanente</i> protegem as cópias lá dentro; <i>candidata</i> não "
    "protege por si. <b>Um deck sem estado escrito vale permanente — e por isso "
    "protege</b>: nunca o contrário, porque um deck novo não pode mandar uma "
    "única carta para a venda. O estado muda-se na <b>Deckboxes</b>, que é onde "
    "tens a caixa na mão; aqui só se lê, para não haver dois caminhos para o "
    "mesmo gesto.</p>"
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
/* As listas de cartas das reservas (a parte `reservas`), e quais os
   `<details>` que ele abriu — sem isto o re-render fechava-os todos. */
let RESERVAS = null;
const ABERTAS = {};
const el = id => document.getElementById(id);
const eur = v => (v == null ? '—' : Number(v).toLocaleString('pt-PT',
  {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €');
const cop = n => n + (n === 1 ? ' cópia' : ' cópias');
const ABAS = [
  ['f1', 'Fase 1 · Os decks que ficam'],
  ['f2', 'Fase 2 · Fotos dos decks'],
  ['f3', 'Fase 3 · VENDER'],
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
    // As reservas também: um «não é necessária» muda-as, e servir a lista de
    // antes do clique era a página a discordar do que ele acabou de fazer.
    if (RESERVAS) { RESERVAS = await parte('reservas'); }
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
/* O BOTÃO «NÃO É NECESSÁRIA» (André, 2026-10-02): tira a carta da reserva
   daquele deck e passa-a a candidata a venda. Escreve `caixas[].reserva_fora`
   no config com a DATA (logo sobrevive à corrida do daily) e tem o inverso ao
   lado («voltar a pôr»), que é o `devolver` do mesmo endpoint. */
function reservaHTML(d) {
  const r = d.reserva || {};
  /* A LISTA DE CARTAS vive numa PARTE (`arrumacao/reservas.json`) e não no
     índice: sem limiar, as 16 reservas somavam 112 KB dos 167 do índice, e o
     índice é o primeiro ecrã no telemóvel (decisão de 2026-09-15). O resumo —
     quantas, quantas tens, quantas dispensaste — vai no índice, que é o que se
     lê com o `<details>` fechado; a lista chega ao primeiro toque. */
  const carregada = RESERVAS && RESERVAS[d.slot];
  const ls = carregada || [];
  let corpo = !carregada
    ? `<p class="carregando">a carregar a lista…</p>`
    : ls.length
    ? `<ul class="rl">` + ls.map(x =>
        `<li><span class="pc">${x.pct == null ? '—' : x.pct + ' %'}</span>`
        + `<span class="tm">${x.tem ? 'tens ' + x.tem : 'não tens'}</span>`
        + `<span style="flex:1">${escDados(x.nm)}</span>`
        + (x.manual ? `<span class="mn">à mão</span>` : '')
        + (D.editavel ? `<button type="button" data-res-fora="${escDados(d.slot)}"`
            + ` data-carta="${escDados(x.nm)}"`
            + ` title="não é necessária — sai da reserva e passa a candidata a venda"`
            + `>não é necessária</button>` : '')
        + `</li>`).join('') + `</ul>`
    : `<p class="vazio">Sem reserva. ${escDados(r.nota || '')}</p>`;
  const fora = r.retiradas || [];
  if (fora.length) {
    corpo += `<p class="sub" style="margin:12px 0 4px"><b>Disseste que não são `
      + `necessárias</b> (${fora.length}) — ficam de fora mesmo que as listas as `
      + `voltem a mostrar:</p><ul class="rl">`
      + fora.map(x =>
          `<li><span class="tm">${escDados(x.em || 'sem data')}</span>`
          + `<span style="flex:1">${escDados(x.nm)}</span>`
          + (D.editavel ? `<button type="button" data-res-volta="${escDados(d.slot)}"`
              + ` data-carta="${escDados(x.nm)}" title="voltar a pôr na reserva"`
              + `>voltar a pôr</button>` : '')
          + `</li>`).join('') + `</ul>`;
  }
  if (D.editavel) {
    corpo += `<div class="addres"><input type="text" id="novares-${escDados(d.slot)}"`
      + ` placeholder="acrescentar uma carta à mão (nome em inglês)">`
      + `<button type="button" data-res-add="${escDados(d.slot)}">acrescentar</button></div>`;
  }
  return `<details class="res"${ABERTAS[d.slot] ? ' open' : ''}>`
    + `<summary data-res-abrir="${escDados(d.slot)}">Reserva («maybe»): `
    + `<b>${r.n_final}</b> cartas · ${r.tem || 0} que tens`
    + `, ${r.sem || 0} que não tens`
    + (fora.length ? ` · ${fora.length} que dispensaste` : '') + `</summary>`
    + `<p class="sub" style="margin:8px 0 0">${escDados(r.nota || '')}</p>`
    + corpo + `</details>`;
}
function deckHTML(d) {
  const lib = d.protege
    ? `As cópias deste deck estão protegidas. Passá-lo a <i>candidata</i> na `
      + `Deckboxes libertava <b>${cop(d.liberta.copias)}</b> · `
      + `<b>${eur(d.liberta.valor)}</b> (o resto fica protegido pelas regras das `
      + `terras e da Reserved List).`
    : `É <b>candidata</b>: as cópias que lhe forem alocadas <b>não</b> ficam `
      + `protegidas por estarem aqui.`;
  const COMO = {carta: 'carta-assinatura', comandante: 'comandante',
                lista: 'lista fixa'};
  const ass = d.identidade
    ? `<span class="chip gold">${COMO[d.identidade_tipo] || 'identidade'}: `
      + `<b>${escDados(d.identidade)}</b></span>`
    : `<span class="chip">⚠ à espera da carta-assinatura</span>`;
  // COMO É QUE A FONTE CHAMA A ESTE DECK (2026-10-02). A identidade continua a
  // ser a carta-assinatura; isto é a CONFERÊNCIA dela — se o mtgtop8 chama dois
  // nomes às listas que ela apanhou, ela está a juntar dois decks (foi o que
  // aconteceu ao «Replenish», que apanhava 186 listas, 124 delas Enchantress).
  const nf = d.nome_fonte
    ? `<span class="chip">mtgtop8: <b>${escDados(d.nome_fonte)}</b>`
      + ` <span class="dm">(${escDados(d.nome_votos)} listas`
      + (d.nome_segundo ? `, a seguir «${escDados(d.nome_segundo)}»` : '')
      + `)</span></span>`
    : '';
  return `<div class="deck"><div class="dh"><div>`
    + `<div class="dn">${escDados(d.nome)}</div>`
    + `<div class="dm">${escDados(d.formato || '')} · ${cop(d.na_caixa)} na caixa`
    + (d.montada_em ? ` · montada em ${escDados(d.montada_em)}` : '')
    + ` · lista ${d.lista.main}+${d.lista.side}`
    + `</div></div><div class="dm" style="text-align:right">${eur(d.valor)}`
    + `<br><span class="${d.protege ? 'est' : 'pordecidir'}">${escDados(d.estado)}`
    + (d.estado_explicito ? '' : ' (por omissão)') + `</span>`
    + `</div></div>`
    + `<div class="chips" style="margin:12px 0 0">${ass}${nf}`
    + `<span class="chip">${d.protege ? '🛡 protege' : 'não protege'}</span>`
    + `<span class="chip">${escDados(d.reserva.listas)} listas de 30 d</span></div>`
    + `<p class="lib">${lib}</p>`
    + `<p class="lib"><span class="dm">${escDados(d.texto_estado || '')}</span></p>`
    + reservaHTML(d) + `</div>`;
}
function fase1() {
  const ds = D.decks || [];
  const prot = ds.filter(d => d.protege).length;
  const semass = ds.filter(d => !d.assinatura).length;
  return `<h2>Fase 1 · Os decks que ficam <span class="n">${ds.length} decks`
    + `</span></h2>`
    + `<p class="sub">A identidade de cada deck é uma <b>carta-assinatura</b>, `
    + `nunca a etiqueta do clustering — é por ela que saem as listas do último `
    + `mês que enchem a reserva. Quem decide se as cópias de um deck estão `
    + `protegidas é o <b>estado da caixa</b>: <i>montada</i>, <i>congelada</i> e `
    + `<i>permanente</i> protegem, <i>candidata</i> não. <b>Um deck sem estado `
    + `escrito vale permanente — e por isso protege.</b> O estado muda-se na `
    + `<a href="deckboxes.html">Deckboxes</a>, que é onde tens a caixa na mão; `
    + `aqui só se lê, para não haver dois caminhos para o mesmo gesto.</p>`
    + `<div class="chips"><span class="chip gold"><b>${prot}</b> protegem</span>`
    + `<span class="chip"><b>${ds.length - prot}</b> candidatas</span>`
    + `<span class="chip"><b>${D.sem_estado}</b> sem estado escrito</span>`
    + (semass ? `<span class="chip"><b>${semass}</b> sem carta-assinatura</span>` : '')
    + `</div>`
    + duaisHTML()
    + ds.map(deckHTML).join('');
}

/* ------------------------------------------- R1: AS DUAIS, AS DUAS LISTAS */
/* *"Quer ter 4 de cada em colecção FORA dos decks; o que passar disso vende-se
   ou troca-se."* As duais são Reserved List, e a R1 manda sobre a R4 — é mais
   específica. Daí saírem DUAS listas, e as duas vão à vista: o que sobra e o
   que falta. */
function duaisHTML() {
  const d = D.duais;
  if (!d) return '';
  const t = d.totais;
  const linhas = (d.linhas || []).map(x =>
    `<tr><td>${escDados(x.nm)}</td><td class="v">${x.copias}</td>`
    + `<td class="v">${x.em_decks}</td><td class="v">${x.fora}</td>`
    + `<td class="v">${x.protegidas}</td>`
    + `<td class="v">${x.vender ? '<b>' + x.vender + '</b>' : '—'}</td>`
    + `<td class="v">${x.comprar ? '<b>' + x.comprar + '</b>' : '—'}</td></tr>`
    ).join('');
  return `<details class="lote" open><summary>`
    + `<span>R1 · as ${(d.nomes || []).length} duais originais — `
    + `${d.alvo_fora} de cada fora dos decks</span>`
    + `<span class="lm">vender ${t.vender} (${eur(t.valor_vender)}) · `
    + `comprar ${t.comprar} (${eur(t.custo_comprar)})</span></summary>`
    + `<div class="lb"><p class="sub">Derivadas do catálogo, não de uma lista `
    + `escrita à mão: ${escDados(d.regra)}. As duais são Reserved List, e aqui `
    + `<b>manda a R1</b> — é mais específica: a quinta cópia fora dos decks vai `
    + `à venda apesar de ser RL.</p>`
    + `<table class="cd"><thead><tr><th>Dual</th><th class="v">Tens</th>`
    + `<th class="v">Em decks</th><th class="v">Fora</th>`
    + `<th class="v">Protegidas</th><th class="v">VENDER</th>`
    + `<th class="v">COMPRAR</th></tr></thead><tbody>${linhas}</tbody></table>`
    + `<p class="sub" style="margin-top:12px"><b>Vender:</b> `
    + ((d.vender || []).map(x => `${x.q}× ${escDados(x.nm)} (${escDados(x.set)}, `
        + `${escDados(x.local)}) ${eur(x.total)}`).join(' · ') || '—') + `</p>`
    + `<p class="sub"><b>Comprar:</b> `
    + ((d.comprar || []).map(x => `${x.q}× ${escDados(x.nm)} `
        + `(${eur((x.unit || 0) * x.q)})`).join(' · ') || '—') + `</p>`
    + `</div></details>`;
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
  const porp = Object.entries(c.por_proteccao)
    .filter(([, v]) => v.copias)
    .map(([, v]) =>
      `<span class="chip"><b>${v.copias}</b> ${escDados(v.rotulo)} · ${eur(v.valor)}</span>`
    ).join('');
  return `<h2>Fase 3 · VENDER <span class="n">${c.copias} cópias, `
    + `${c.cartas} cartas</span></h2>`
    + `<p class="sub"><b>Tudo o que não se enquadrou nas regras.</b> Sai sozinha `
    + `dos estados da Fase 1 e das regras das cartas: duais (4 fora dos decks), `
    + `shocklands, fetchlands, Reserved List que jogas, o que foi jogado nos `
    + `últimos ${c.janela_dias} dias, e as staples de sideboard de Premodern `
    + `acima de ${c.staples_corte} %. <b>Só leitura</b> — aqui não se vende nada, `
    + `e a saída continua congelada.</p>`
    + `<div class="chips"><span class="chip gold"><b>${eur(c.valor)}</b> em VENDER`
    + `</span>${porp}</div>`
    + `<table class="cd"><thead><tr><th>Carta</th><th>Versão</th><th>Onde está`
    + `</th><th class="v">Cóp.</th><th class="v">Valor</th></tr></thead>`
    + `<tbody>${linhas || '<tr><td colspan=5 class="vazio">Nada candidato.</td></tr>'}`
    + `</tbody></table>`
    + `<h2>Protegidas <span class="n">${c.protegidas_copias} cópias · `
    + `${eur(c.protegidas_valor)}</span></h2>`
    + `<p class="sub">Cada linha diz <b>qual</b> das regras a apanhou e `
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
    // A LISTA DA RESERVA vem a pedido: o primeiro toque num `<details>` traz a
    // parte `reservas` e redesenha. Guarda-se quais ele abriu para o redesenho
    // não lhe fechar o que estava aberto.
    const sm = ev.target.closest('summary');
    if (sm && sm.dataset.resAbrir) {
      const s = sm.dataset.resAbrir;
      ABERTAS[s] = !ABERTAS[s];
      if (ABERTAS[s] && !RESERVAS) {
        parte('reservas').then(p => { RESERVAS = p; render(); })
          .catch(() => { RESERVAS = {}; toast('não consegui ir buscar as reservas', true); });
      }
      return;
    }
    const b = ev.target.closest('button');
    if (!b) return;
    if (b.dataset.aba) { ABA = b.dataset.aba; render(); return; }
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
    if (b.dataset.resVolta) {
      grava({url: '/api/fase-reserva',
             dados: {slot: b.dataset.resVolta, act: 'devolver',
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

    **A Fase 1 vai no índice**, de propósito: é o primeiro ecrã — fazê-la
    esperar por um segundo pedido era pôr a decisão atrás de uma barra de
    progresso. As filas de fotos, a lista VENDER e a lista de cartas das
    reservas, que são as grandes, vão numa parte cada.
    """
    from mtgvault import loadout
    rep = rep if rep is not None else loadout.report(con)
    r = fases.relatorio(con, rep)
    # A LISTA DE CARTAS DE CADA RESERVA sai do índice para uma parte própria.
    # Sem o limiar de 2026-10-01 a reserva passou a ser tudo o que foi jogado no
    # mês: medido a 2026-10-02, 112 KB dos 167 do índice, para listas que vivem
    # dentro de um `<details>` FECHADO. O resumo (quantas, quantas tens, quantas
    # dispensaste) fica no índice, que é o que se lê de fora.
    reservas = {}
    decks = []
    for d in r["decks"]:
        rv = dict(d["reserva"])
        reservas[d["slot"]] = rv.pop("final")
        rv["n_final"] = len(reservas[d["slot"]])
        # A `automatica` é a matéria-prima (o consenso cru, com board e cópias)
        # e a página NÃO a desenha — quem ela desenha é a `final`. Eram 50 dos
        # 71 KB dos decks no índice.
        rv["n_automatica"] = len(rv.pop("automatica", []))
        decks.append(dict(d, reserva=rv))
    partes = {"fase2": r["fase2"], "candidatos": _magra(r["candidatos"]),
              "fase4": r["fase4"], "inventario": r["inventario"],
              "reservas": reservas}
    idx = {
        "hoje": r["hoje"], "editavel": bool(editavel),
        "congelada": r["congelada"], "congelado_ate": r["congelado_ate"],
        "motivo_congelado": r["motivo_congelado"],
        "janela_dias": r["janela_dias"], "desde": r["desde"],
        "terras": {k: {"n": v["n"], "nomes": v["nomes"], "regra": v["regra"]}
                   for k, v in r["terras"].items()},
        # A R1 vai no ÍNDICE: são as duas listas (vender / comprar) que ele
        # pediu, dez linhas, e abrem a Fase 1. O `por_sublote` fica de fora —
        # é o mapa interno da quota, não se desenha (e tem chaves em tuplo, que
        # não são JSON).
        "duais": {k: v for k, v in r["duais"].items() if k != "por_sublote"},
        "staples": {k: v for k, v in r["staples"].items() if k != "todas"},
        "estados": r["estados"], "regras": r["regras"],
        # O alvo da revalidação (2026-10-01): a Fase 2 é a fila das fotos e o
        # botão que fixa o alvo estava noutra página. Ver `alvo_actual`.
        "revalidacao": alvo_actual(con, rep),
        "decks": decks,
        "sem_estado": sum(1 for d in r["decks"] if not d["estado_explicito"]),
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
