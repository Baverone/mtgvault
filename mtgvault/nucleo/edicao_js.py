"""O MODO DE EDIÇÃO das três páginas do núcleo (Task 8, 2026-10-28): o
JavaScript e o CSS que as páginas levam quando são servidas com
`editable=True` pelo `webapp.py` (o porto 8771, no telemóvel dele à frente da
estante, ou em editar-mtg.baverone.com).

O que faz, e as decisões que valem a pena saber:

- **Tocar numa carta abre a folha da carta** (o esboço aprovado,
  «rotativo-edicao»): a imagem grande, de onde é a carta («partilhada ·
  Affinity (4) e Welder Cam (2) → precisas de 4»), o interruptor Normal/Foil
  só com os acabamentos que EXISTEM na edição escolhida, as edições lado a
  lado com a imagem e o trend do Cardmarket, e «− 1» / «Tenho + 1». É uma
  folha de baixo (no PC, uma caixa ao centro) com botão de fechar, Esc e o
  foco preso lá dentro enquanto está aberta.
- **O `request_id` é um por toque, e o retry reutiliza-o.** No telemóvel, em
  http na rede de casa, o `crypto.randomUUID` NÃO existe (só existe em
  contexto seguro); o `crypto.getRandomValues` existe, e é dele que sai o id.
  Só a marca repete sozinha (sem rede, ou 503 de «a gravar outra coisa»): é a
  única escrita idempotente por id.
- **Nada otimista.** Depois de cada POST bom a página vai buscar o seu próprio
  HTML de novo (o mesmo URL, com o token) e troca o conteúdo do `<main>`; o
  `#slug` da página dos decks fica onde estava (o evento `nuc:atualizada` diz
  ao JavaScript da página para voltar a mostrar a secção certa). Um número no
  ecrã é sempre um número que o servidor disse.
- **O token nunca vai escrito na página**: lê-se do `?t=` do URL e vai no
  cabeçalho `X-Mtgvault-Token`, como na Deckboxes e na aba Decks. Do loopback
  (o PC, e o túnel do Cloudflare) escreve-se sem ele.
- **Os textos das cartas entram por `textContent`**, nunca por `innerHTML`: um
  nome de carta (ou uma fonte colada) não é HTML.
- **Nenhum pedido fica pendurado** (I6, 2026-10-29): 25 s e o `AbortController`
  corta-o. Num POST a página diz «não sei se gravou — confirma na página» (o
  servidor pode ter gravado: só a marca repete sozinha, com o MESMO
  `request_id`, que conta uma vez). É o prazo que a Deckboxes já tinha.
- **A busca de Vender sobrevive à troca do `<main>`** (T8): o texto fica e a
  busca volta a correr, para ele acrescentar a seguinte sem escrever outra vez.
- As cores são as da casca (`var(--…)`); este ficheiro não escreve um hex.
"""
from __future__ import annotations

# O que os testes procuram para saber que o JavaScript da edição foi injetado.
MARCA = "nucleo-edicao-v1"

CSS = r"""
 html.ed-preso{overflow:hidden}
 body[data-editavel] figure.ct[data-deck]{cursor:pointer}
 body[data-editavel] figure.ct[data-deck]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
 .btn.ed-b{min-height:44px;font-size:14px;padding:8px 14px}
 .ed-acoes{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
 .ed-veu{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.62)}
 .ed-folha{position:fixed;z-index:81;left:0;right:0;bottom:0;max-height:92vh;max-height:92dvh;
   overflow:auto;overscroll-behavior:contain;background:var(--card);color:var(--ink);
   border:1px solid var(--line2);border-bottom:0;border-radius:var(--r2) var(--r2) 0 0;
   padding:14px 14px calc(14px + env(safe-area-inset-bottom));box-shadow:var(--sombra)}
 @media (min-width:720px){ .ed-folha{left:50%;right:auto;top:50%;bottom:auto;transform:translate(-50%,-50%);
   width:min(680px,94vw);max-height:88vh;border-radius:var(--r2);border-bottom:1px solid var(--line2)} }
 .ed-folha[hidden],.ed-veu[hidden],.ed-aviso[hidden]{display:none!important}
 .ed-folha:focus{outline:none}
 .ed-fecha{float:right;width:44px;height:44px;margin:-4px -4px 4px 10px;border-radius:50%;
   border:1px solid var(--line2);background:var(--card2);color:var(--ink);font:400 26px/1 var(--font);
   cursor:pointer}
 .ed-fecha:hover{border-color:var(--accent)}
 .ed-folha h2{margin:0 0 2px;font:700 19px/1.2 var(--font-hd);overflow-wrap:anywhere}
 .ed-top{display:flex;gap:12px;align-items:flex-start}
 .ed-big{flex:none;width:118px;aspect-ratio:488/680;border-radius:5%/3.6%;overflow:hidden;background:var(--sunken)}
 @media (min-width:720px){ .ed-big{width:160px} }
 .ed-big img{display:block;width:100%;height:100%;object-fit:cover}
 .ed-big .ed-semimg{display:flex;height:100%;align-items:center;justify-content:center;padding:8px;
   text-align:center;color:var(--muted);font-size:12px}
 .ed-info{min-width:0;flex:1}
 .ed-amb{color:var(--muted);font-size:12.5px;margin:3px 0 8px;line-height:1.45}
 .ed-amb b{color:var(--ink2)}
 .ed-seg button{min-height:44px;min-width:74px;font-size:13.5px}
 .ed-seg button[disabled]{cursor:default}
 .ed-tens{font-size:13.5px;margin:10px 0 0;color:var(--ink2);line-height:1.45}
 .ed-tens b{color:var(--ok);font-size:17px;font-variant-numeric:tabular-nums}
 .ed-rot{font-size:12px;color:var(--muted);margin:16px 0 6px}
 .ed-eds{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
 @media (min-width:600px){ .ed-eds{grid-template-columns:repeat(5,minmax(0,1fr))} }
 button.ed-ed{appearance:none;font:inherit;color:var(--ink2);background:var(--card2);
   border:1px solid var(--line);border-radius:var(--r);padding:4px;display:flex;flex-direction:column;
   align-items:stretch;gap:2px;cursor:pointer;min-height:44px;text-align:center;min-width:0}
 button.ed-ed img{display:block;width:100%;aspect-ratio:146/204;height:auto;border-radius:4px;
   object-fit:cover;background:var(--sunken)}
 button.ed-ed .ed-set{font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 button.ed-ed b{font-size:12px;color:var(--accent);font-variant-numeric:tabular-nums;white-space:nowrap}
 button.ed-ed b.sp{color:var(--dim);font-weight:500}
 button.ed-ed small{font-size:9.5px;color:var(--muted)}
 button.ed-ed.on{border-color:var(--accent);background:var(--accent-soft);color:var(--ink)}
 button.ed-ed:hover{border-color:var(--accent-line)}
 button.ed-ed[disabled]{opacity:.55;cursor:default}
 .ed-row{display:flex;gap:8px;margin-top:14px}
 .ed-row .btn{flex:1}
 .ed-fixa{position:sticky;bottom:-14px;background:var(--card);padding:10px 0 4px;margin-bottom:-4px;
   border-top:1px solid var(--line);z-index:1}
 .ed-qtd{display:flex;align-items:center;gap:8px;margin-top:10px}
 .ed-qtd output{min-width:2.4em;text-align:center;font:700 18px var(--font-hd);font-variant-numeric:tabular-nums}
 .ed-qtd .btn{min-width:48px}
 .ed-msg{min-height:1.3em;margin:10px 0 0;font-size:13px;color:var(--muted);line-height:1.45}
 .ed-msg.mau{color:var(--bad-ink)}
 .ed-conf{background:var(--warn-soft);border:1px solid var(--warn-line);border-radius:var(--r);
   padding:10px 12px;margin:12px 0 0;font-size:13.5px;line-height:1.45;color:var(--ink)}
 .ed-conf .ed-row{margin-top:10px}
 .ed-form label{display:block;font-size:13px;font-weight:600;color:var(--ink2);margin:12px 0 5px}
 .ed-form textarea,.ed-form input,.ed-proc input{width:100%;box-sizing:border-box;font:16px/1.4 var(--font);
   background:var(--sunken);color:var(--ink);border:1px solid var(--line2);border-radius:var(--r);padding:10px 12px}
 .ed-form textarea{min-height:12em;font-size:15px;resize:vertical}
 .ed-form input,.ed-proc input{min-height:46px}
 .ed-form textarea:focus,.ed-form input:focus,.ed-proc input:focus{outline:2px solid var(--accent-line);border-color:var(--accent)}
 .ed-form input[aria-invalid="true"]{border-color:var(--bad)}
 .ed-dica{font-size:12px;color:var(--dim);margin:5px 0 0}
 .ed-lista{margin:6px 0 0;padding-left:20px;font-size:13.5px;line-height:1.5}
 .ed-lista li{overflow-wrap:anywhere}
 .ed-mal{background:var(--bad-soft);border:1px solid var(--bad-line);color:var(--bad-ink);
   border-radius:var(--r);padding:10px 12px;margin-top:12px;font-size:13.5px}
 .ed-mal .ed-lista{color:var(--ink)}
 .ed-proc{margin-top:22px;background:var(--card);border:1px solid var(--line);border-radius:var(--r2);padding:12px 14px}
 .ed-proc h2.gt{margin-top:0}
 .ed-proc label{display:block;font-size:13px;color:var(--ink2);margin-bottom:6px}
 .ed-res{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-direction:column;gap:6px}
 .ed-res .btn{width:100%;justify-content:flex-start;text-align:left;min-height:44px;font-size:14px}
 .ed-res .vazio{padding:10px 12px}
 li.vl .ed-lin{grid-column:1/-1;display:flex;gap:8px;flex-wrap:wrap}
 li.vl .ed-lin .btn{flex:1 1 140px}
 .ed-aviso{position:fixed;left:50%;bottom:calc(16px + env(safe-area-inset-bottom));transform:translateX(-50%);
   z-index:90;width:max-content;max-width:min(560px,92vw);background:var(--card3);border:1px solid var(--line2);
   color:var(--ink);padding:10px 14px;border-radius:var(--r);box-shadow:var(--sombra);font-size:14px;line-height:1.4}
 .ed-aviso.mau{border-color:var(--bad-line);color:var(--bad-ink)}
 /* as coleções: botões por baixo de cada carta, com alvos de toque de 44 px */
 .btn.cbt{min-height:44px;padding:6px 8px;font-size:13px}
 .ccb{display:flex;flex-direction:column;gap:6px;margin-top:8px}
 .ccb .ed-lin{display:flex;gap:6px}
 .ccb .ed-lin .btn{flex:1 1 0;min-width:0}
 .cjb{margin:4px 0 12px}
 .ed-proc[hidden]{display:none}
"""

JS = r"""
(function(){
  'use strict';
  /* nucleo-edicao-v1 */
  var B = document.body;
  if (!B || B.getAttribute('data-editavel') !== '1') return;
  var TOKEN = '';
  try { TOKEN = new URLSearchParams(location.search).get('t') || ''; } catch (e) {}
  var ACABS = ['nonfoil', 'foil'], NOME_ACAB = {nonfoil: 'Normal', foil: 'Foil'};
  var REDE_POST = 'Sem ligação ao modo de edição: não sei se gravou. Recarrega a página para ver o número certo.';
  var REDE_GET = 'Sem ligação ao modo de edição. Tenta outra vez daqui a pouco.';
  // (I6) o prazo de cada pedido, e o que se diz quando ele se esgota num POST
  var PRAZO_MS = 25000;
  var PRAZO_POST = 'Passaram 25 s sem resposta: não sei se gravou — confirma na página.';
  function falhaPost(e){ return e && e.message === 'prazo' ? PRAZO_POST : REDE_POST; }

  // ---------------------------------------------------------------- pedidos
  // Um id por toque. Em http na rede de casa o randomUUID não existe
  // (contexto inseguro) e o getRandomValues existe: é dele que sai o id.
  function idPedido(){
    var c = window.crypto;
    if (c && typeof c.randomUUID === 'function') { try { return c.randomUUID(); } catch (e) {} }
    if (c && typeof c.getRandomValues === 'function') {
      var a = new Uint8Array(16), h = [], i;
      c.getRandomValues(a);
      a[6] = (a[6] & 15) | 64; a[8] = (a[8] & 63) | 128;
      for (i = 0; i < 16; i++) h.push((a[i] + 256).toString(16).slice(1));
      return h.slice(0, 4).join('') + '-' + h.slice(4, 6).join('') + '-' + h.slice(6, 8).join('')
        + '-' + h.slice(8, 10).join('') + '-' + h.slice(10).join('');
    }
    return 'r' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  }
  function espera(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function cab(json){
    var h = {};
    if (TOKEN) h['X-Mtgvault-Token'] = TOKEN;
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }
  // {ok, status, dados}. Sem rede rejeita. `repete` só para o que é
  // idempotente (a marca, pelo request_id): o MESMO corpo, o MESMO id.
  // Sem resposta em PRAZO_MS rejeita com Error('prazo') (o AbortController
  // corta o pedido); sem rede, com Error('rede').
  function pede(metodo, url, corpo, repete){
    repete = repete || 0;
    var op = {method: metodo, headers: cab(corpo !== undefined), cache: 'no-store',
              credentials: 'same-origin'};
    if (corpo !== undefined) op.body = JSON.stringify(corpo);
    var ctl = typeof AbortController === 'function' ? new AbortController() : null, t = 0, cortado = false;
    if (ctl) {
      op.signal = ctl.signal;
      t = setTimeout(function(){ cortado = true; ctl.abort(); }, PRAZO_MS);
    }
    function falhou(){
      clearTimeout(t);
      if (repete > 0)
        return espera(800).then(function(){ return pede(metodo, url, corpo, repete - 1); });
      throw new Error(cortado ? 'prazo' : 'rede');
    }
    return fetch(url, op).then(function(r){
      if (r.status === 503 && repete > 0) {
        clearTimeout(t);
        return espera(1500).then(function(){ return pede(metodo, url, corpo, repete - 1); });
      }
      return r.text().then(function(txt){
        clearTimeout(t);
        var d = null;
        try { d = JSON.parse(txt); } catch (e) {}
        if (d === null) d = {erro: 'O servidor respondeu ' + r.status + ' sem explicação.'};
        return {ok: r.ok, status: r.status, dados: d};
      }, falhou);
    }, falhou);
  }
  function api(caminho, params){
    var q = [];
    for (var k in params) if (params[k] !== undefined && params[k] !== null)
      q.push(encodeURIComponent(k) + '=' + encodeURIComponent(params[k]));
    return caminho + (q.length ? '?' + q.join('&') : '');
  }

  // ---------------------------------------------------- recarregar a página
  // Depois de cada POST bom: o HTML da própria página outra vez, e troca-se o
  // <main>. Dois POST seguidos dão um recarregar a seguir ao outro, nunca
  // dois ao mesmo tempo (o mais velho podia chegar depois).
  var emCurso = false, deNovo = false;
  // um botão desativado perde o foco (o Chrome tira-lho): quem o desativa diz
  // aqui a que botão o foco volta depois de trocar o <main>
  var focoDepois = null;
  function recarrega(){
    if (emCurso) { deNovo = true; return; }
    emCurso = true;
    fetch(location.pathname + location.search, {headers: cab(false), cache: 'no-store',
                                                 credentials: 'same-origin'})
      .then(function(r){ if (!r.ok) throw new Error('http'); return r.text(); })
      .then(function(t){
        var doc = new DOMParser().parseFromString(t, 'text/html');
        var novo = doc.getElementById('conteudo'), velho = document.getElementById('conteudo');
        if (!novo || !velho) throw new Error('sem main');
        var y = window.pageYOffset, at = document.activeElement;
        // o botão da linha que ele tocou é substituído: o foco volta ao novo
        var k = at && velho.contains(at) ? chaveDe(at) : focoDepois;
        focoDepois = null;
        // (T8) a busca de Vender vive dentro do <main>: guarda-se o texto
        var qv = document.getElementById('ed-q'), q = qv ? qv.value : '', qFoco = at === qv;
        velho.innerHTML = novo.innerHTML;
        if (q) {
          var nq = document.getElementById('ed-q');
          if (nq) {
            nq.value = q; procura(nq);
            // a busca de «juntar carta» começa escondida: não a esconder a quem está a escrever
            var cx = nq.closest ? nq.closest('.ed-proc') : null;
            if (cx) cx.hidden = false;
            if (qFoco) nq.focus({preventScroll: true});
          }
        }
        document.dispatchEvent(new CustomEvent('nuc:atualizada'));
        window.scrollTo(0, y);
        if (k) {
          var alvo = null;
          try { alvo = velho.querySelector(k); } catch (e) {}
          if (alvo && alvo.focus) alvo.focus({preventScroll: true});
        }
      })
      .catch(function(){ aviso('Gravei, mas não consegui atualizar a página. Recarrega-a.', true); })
      .then(function(){
        emCurso = false;
        if (deNovo) { deNovo = false; recarrega(); }
      });
  }

  // ------------------------------------------------------------ ajudantes
  function el(tag, cls, txt){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined && txt !== null) e.textContent = txt;
    return e;
  }
  function botao(txt, cls, k){
    var b = el('button', 'btn ed-b' + (cls ? ' ' + cls : ''), txt);
    b.type = 'button';
    if (k) b.setAttribute('data-k', k);
    return b;
  }
  function eur(v){
    var s = v.toFixed(2).split('.');
    return s[0].replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') + ',' + s[1] + '\u00a0€';
  }
  function juntaE(xs){
    if (xs.length < 2) return xs.join('');
    return xs.slice(0, -1).join(', ') + ' e ' + xs[xs.length - 1];
  }
  function plural(n, um, varios){ return n + ' ' + (n === 1 ? um : varios); }
  function temAcab(e){ return e.finishes.indexOf('nonfoil') >= 0 || e.finishes.indexOf('foil') >= 0; }
  function acabsDe(e){ return ACABS.filter(function(a){ return e.finishes.indexOf(a) >= 0; }); }
  function acabPara(e, quero){ var fs = acabsDe(e); return fs.indexOf(quero) >= 0 ? quero : fs[0]; }
  function precoDe(e, acab){ return acab === 'foil' ? e.preco_foil : e.preco_nonfoil; }

  var avisoEl = null, avisoT = 0;
  function aviso(txt, mau){
    if (!avisoEl) {
      avisoEl = el('div', 'ed-aviso');
      avisoEl.setAttribute('role', 'status');
      avisoEl.setAttribute('aria-live', 'polite');
      document.body.appendChild(avisoEl);
    }
    avisoEl.textContent = txt;
    avisoEl.className = 'ed-aviso' + (mau ? ' mau' : '');
    avisoEl.hidden = false;
    clearTimeout(avisoT);
    avisoT = setTimeout(function(){ avisoEl.hidden = true; }, mau ? 9000 : 4000);
  }

  // ----------------------------------------------------------------- folha
  var veu = null, folha = null, corpoF = null, msgF = null, origem = null, chaveOrigem = null;
  var est = null;
  function montaFolha(){
    if (folha) return;
    veu = el('div', 'ed-veu'); veu.hidden = true;
    veu.addEventListener('click', fecha);
    folha = el('div', 'ed-folha'); folha.hidden = true; folha.tabIndex = -1;
    folha.setAttribute('role', 'dialog');
    folha.setAttribute('aria-modal', 'true');
    folha.setAttribute('aria-labelledby', 'ed-tit');
    var x = el('button', 'ed-fecha', '\u00d7');
    x.type = 'button'; x.setAttribute('aria-label', 'Fechar');
    x.addEventListener('click', fecha);
    corpoF = el('div', 'ed-corpo');
    msgF = el('p', 'ed-msg');
    msgF.setAttribute('role', 'status'); msgF.setAttribute('aria-live', 'polite');
    folha.appendChild(x); folha.appendChild(corpoF); folha.appendChild(msgF);
    document.body.appendChild(veu); document.body.appendChild(folha);
  }
  function chaveDe(e){
    if (!e || !e.getAttribute) return null;
    // numa carta do deck, a edição muda com a folha aberta: só o deck e o nome
    var ks = e.tagName === 'FIGURE' ? ['data-deck', 'data-nome']
      : ['data-acao', 'data-deck', 'data-nome', 'data-saida', 'data-destino', 'data-sid', 'data-acab', 'data-delta', 'data-carta', 'data-colecao'], s = '';
    for (var i = 0; i < ks.length; i++) {
      var v = e.getAttribute(ks[i]);
      if (v !== null) s += '[' + ks[i] + '="' + v.replace(/["\\]/g, '\\$&') + '"]';
    }
    return s ? e.tagName.toLowerCase() + s : null;
  }
  function abre(de, novoEst){
    montaFolha();
    origem = de || document.activeElement;
    chaveOrigem = chaveDe(origem);
    est = novoEst;
    corpoF.innerHTML = '';
    diz('');
    veu.hidden = false; folha.hidden = false;
    folha.scrollTop = 0;
    document.documentElement.classList.add('ed-preso');
    folha.querySelector('.ed-fecha').focus();
  }
  function fecha(){
    if (!folha || folha.hidden) return;
    folha.hidden = true; veu.hidden = true;
    document.documentElement.classList.remove('ed-preso');
    est = null;
    var alvo = origem;
    if (!alvo || !document.body.contains(alvo)) {
      alvo = null;
      try { if (chaveOrigem) alvo = document.querySelector(chaveOrigem); } catch (e) {}
    }
    if (alvo && alvo.focus) alvo.focus();
  }
  function aberta(){ return folha && !folha.hidden; }
  function diz(txt, mau){
    if (!msgF) return;
    msgF.textContent = txt || '';
    msgF.className = 'ed-msg' + (mau ? ' mau' : '');
  }
  function titulo(txt){ var h = el('h2', '', txt); h.id = 'ed-tit'; return h; }
  function focaveis(){
    return Array.prototype.filter.call(
      folha.querySelectorAll('button, input, textarea, select, a[href], [tabindex]'),
      function(e){ return !e.disabled && e.tabIndex >= 0 && e.offsetParent !== null; });
  }
  // Redesenha guardando o foco no botão equivalente (o teclado não salta
  // para o início da folha a cada toque).
  // Enquanto grava, o botão tocado fica desativado: o foco espera na folha e
  // volta ao mesmo botão quando ele voltar a estar ativo (`focoPendente`).
  var focoPendente = null;
  function redesenha(fn){
    var at = document.activeElement;
    var k = at && at.getAttribute ? at.getAttribute('data-k') : null;
    if (!k && at === folha) k = focoPendente;
    fn();
    focoPendente = null;
    if (k) {
      var alvo = folha.querySelector('[data-k="' + k + '"]');
      if (alvo && !alvo.disabled) alvo.focus();
      else { focoPendente = k; folha.focus(); }
    }
  }
  // Uma pergunta dentro da folha (sem `confirm()`, que no telemóvel tapa tudo).
  function confirma(txt, sim, fazer){
    var velha = corpoF.querySelector('.ed-conf');
    if (velha) velha.parentNode.removeChild(velha);
    var c = el('div', 'ed-conf');
    c.setAttribute('role', 'alertdialog');
    c.setAttribute('aria-label', 'Confirmar');
    c.appendChild(el('p', '', txt)).style.margin = '0';
    var row = el('div', 'ed-row');
    var bs = botao(sim, 'pri'), bn = botao('Cancelar');
    bs.addEventListener('click', function(){ c.parentNode.removeChild(c); fazer(); });
    bn.addEventListener('click', function(){ c.parentNode.removeChild(c); folha.querySelector('.ed-fecha').focus(); });
    row.appendChild(bs); row.appendChild(bn); c.appendChild(row);
    corpoF.insertBefore(c, corpoF.firstChild);
    folha.scrollTop = 0;
    bs.focus();
  }

  // ---------------------------------------------------- a folha da carta
  function abreCarta(fig){
    var e0 = {tipo: 'carta', deck: fig.getAttribute('data-deck'), nome: fig.getAttribute('data-nome'),
              carta: null, eds: null, ocupado: false};
    abre(fig, e0);
    corpoF.appendChild(titulo(e0.nome));
    diz('A carregar as edições…');
    carregaCarta(e0);
  }
  function carregaCarta(e0){
    return Promise.all([
      pede('GET', api('/api/n/carta', {deck: e0.deck, nome: e0.nome})),
      pede('GET', api('/api/n/edicoes', {deck: e0.deck, nome: e0.nome}))
    ]).then(function(rs){
      if (est !== e0) return;
      for (var i = 0; i < 2; i++) if (!rs[i].ok) { diz(rs[i].dados.erro, true); return; }
      e0.carta = rs[0].dados;
      e0.eds = rs[1].dados.filter(temAcab);
      redesenha(desenhaCarta);
      diz('');
    }, function(){ if (est === e0) diz(REDE_GET, true); });
  }
  function ambitoTexto(c){
    if (c.partilhada) {
      var us = c.usos.map(function(u){ return u.nome + ' (' + u.qtd + ')'; });
      return 'partilhada · ' + juntaE(us) + ' → precisas de ' + c.precisa;
    }
    if (c.modo === 'rotativo') return 'fixa deste deck · vive na caixa dele · o deck pede ' + c.pede;
    return 'o deck pede ' + c.pede;
  }
  function imgEdicao(e, grande, alt){
    var im = document.createElement('img');
    im.src = grande ? e.imagem_normal : e.imagem;
    im.alt = alt || '';
    im.loading = 'lazy'; im.decoding = 'async';
    im.width = grande ? 488 : 146; im.height = grande ? 680 : 204;
    return im;
  }
  function desenhaCarta(){
    var e0 = est, c = e0.carta, eds = e0.eds, esc = null, i;
    for (i = 0; i < eds.length; i++) if (eds[i].scryfall_id === c.scryfall_id) esc = eds[i];
    corpoF.innerHTML = '';
    var top = el('div', 'ed-top'), big = el('div', 'ed-big'), info = el('div', 'ed-info');
    if (esc) big.appendChild(imgEdicao(esc, true, c.nome + ', ' + esc.set_name));
    else big.appendChild(el('span', 'ed-semimg', c.nome));
    top.appendChild(big);
    info.appendChild(titulo(c.nome));
    info.appendChild(el('p', 'ed-amb', ambitoTexto(c)));
    if (esc) {
      var fins = acabsDe(esc), seg = el('div', 'seg ed-seg');
      seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Acabamento');
      fins.forEach(function(a){
        var b = el('button', a === c.acabamento ? 'on' : '', NOME_ACAB[a]);
        b.type = 'button'; b.setAttribute('data-k', 'acab-' + a);
        b.setAttribute('aria-pressed', a === c.acabamento ? 'true' : 'false');
        if (fins.length < 2) { b.disabled = true; b.title = 'Esta edição só existe em ' + NOME_ACAB[a].toLowerCase(); }
        else if (e0.ocupado) b.disabled = true;
        b.addEventListener('click', function(){ troca(esc, a); });
        seg.appendChild(b);
      });
      info.appendChild(seg);
    }
    var tens = el('p', 'ed-tens');
    tens.appendChild(document.createTextNode('Tens '));
    tens.appendChild(el('b', '', String(c.tenho)));
    tens.appendChild(document.createTextNode(esc ? ' desta edição (' + esc.set_code.toUpperCase() + ', '
      + NOME_ACAB[c.acabamento].toLowerCase() + ')' : ''));
    info.appendChild(tens);
    // (M2) a primeira marca fixa a edição da omissão: sem preço, diz-se antes
    if (c.omissao_sem_preco)
      info.appendChild(el('p', 'ed-dica', 'Atenção: a edição por omissão não tem preço — escolhe a tua.'));
    top.appendChild(info);
    corpoF.appendChild(top);

    corpoF.appendChild(el('p', 'ed-rot', 'Escolhe a edição — trend do Cardmarket'
      + (eds.length > 1 ? ' · ' + eds.length + ' edições' : '')));
    var grade = el('div', 'ed-eds');
    eds.forEach(function(e){
      var on = e.scryfall_id === c.scryfall_id, acab = acabPara(e, c.acabamento), p = precoDe(e, acab);
      var b = el('button', 'ed-ed' + (on ? ' on' : ''));
      b.type = 'button'; b.setAttribute('data-k', 'ed-' + e.scryfall_id);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.title = e.set_name + ' #' + e.collector_number;
      b.appendChild(imgEdicao(e, false, ''));
      b.appendChild(el('span', 'ed-set', e.set_code.toUpperCase() + ' · ' + e.collector_number));
      b.appendChild(el('b', p === null ? 'sp' : '', p === null ? 'sem preço' : eur(p)));
      if (acab !== c.acabamento) b.appendChild(el('small', '', 'só ' + NOME_ACAB[acab].toLowerCase()));
      b.setAttribute('aria-label', e.set_name + ' número ' + e.collector_number + ', '
        + (p === null ? 'sem preço' : eur(p)) + (acab !== c.acabamento ? ', só ' + NOME_ACAB[acab].toLowerCase() : ''));
      if (e0.ocupado) b.disabled = true;
      b.addEventListener('click', function(){ troca(e, acab); });
      grade.appendChild(b);
    });
    if (!eds.length) grade.appendChild(el('p', 'vazio', 'O catálogo não tem nenhuma impressão em papel desta carta.'));
    corpoF.appendChild(grade);

    var row = el('div', 'ed-row ed-fixa');
    var menos = botao('− 1', '', 'menos'), mais = botao('Tenho + 1', 'pri', 'mais');
    menos.setAttribute('aria-label', 'Tenho menos uma');
    menos.disabled = e0.ocupado || c.tenho <= 0 || !esc;
    mais.disabled = e0.ocupado || !esc;
    menos.addEventListener('click', function(){ marca(-1); });
    mais.addEventListener('click', function(){ marca(1); });
    row.appendChild(menos); row.appendChild(mais);
    corpoF.appendChild(row);
  }
  function marca(delta){
    var e0 = est;
    if (!e0 || e0.ocupado) return;
    var id = idPedido();                              // um por toque; o retry reutiliza-o
    e0.ocupado = true; redesenha(desenhaCarta); diz('A gravar…');
    pede('POST', '/api/n/marca', {deck: e0.deck, nome: e0.nome, delta: delta, request_id: id}, 2)
      .then(function(r){
        e0.ocupado = false;
        if (r.ok) recarrega();
        if (est !== e0) return;
        if (!r.ok) { redesenha(desenhaCarta); diz(r.dados.erro || 'Não gravei.', true); return; }
        e0.carta.tenho = r.dados.qtd;
        redesenha(desenhaCarta);
        diz('Gravado: tens ' + r.dados.qtd + '.');
      }, function(err){
        e0.ocupado = false;
        if (est === e0) { redesenha(desenhaCarta); diz(falhaPost(err), true); }
      });
  }
  function troca(e, acab){
    var e0 = est, c = e0 && e0.carta;
    if (!c || e0.ocupado) return;
    if (e.scryfall_id === c.scryfall_id && acab === c.acabamento) return;
    function vai(){
      e0.ocupado = true; redesenha(desenhaCarta); diz('A gravar…');
      pede('POST', '/api/n/edicao', {deck: e0.deck, nome: e0.nome, scryfall_id: e.scryfall_id, acabamento: acab})
        .then(function(r){
          e0.ocupado = false;
          if (r.ok) recarrega();
          if (est !== e0) return;
          if (!r.ok) { redesenha(desenhaCarta); diz(r.dados.erro || 'Não gravei.', true); return; }
          diz('Passou a ' + e.set_code.toUpperCase() + ', ' + NOME_ACAB[acab].toLowerCase() + '.');
          carregaCarta(e0).then(function(){
            if (est === e0) diz('Passou a ' + e.set_code.toUpperCase() + ', ' + NOME_ACAB[acab].toLowerCase() + '.');
          });
        }, function(err){
          e0.ocupado = false;
          if (est === e0) { redesenha(desenhaCarta); diz(falhaPost(err), true); }
        });
    }
    if (c.tenho > 0)
      confirma('Tens ' + plural(c.tenho, 'cópia marcada', 'cópias marcadas') + ' na edição de agora. '
        + 'Ao trocar, passam para Vender, em «Trocaste de edição», para decidires o que lhes fazer.',
        'Trocar', vai);
    else vai();
  }

  // ------------------------------------------------------- colar uma lista
  function abreColar(btn){
    var e0 = {tipo: 'colar', deck: btn.getAttribute('data-deck')};
    abre(btn, e0);
    corpoF.appendChild(titulo('Colar lista nova · ' + (btn.getAttribute('data-nome-deck') || e0.deck)));
    var f = el('form', 'ed-form'); f.noValidate = true;
    var l1 = el('label', '', 'A lista'); l1.htmlFor = 'ed-txt';
    var ta = el('textarea'); ta.id = 'ed-txt'; ta.rows = 12;
    ta.setAttribute('spellcheck', 'false'); ta.setAttribute('autocapitalize', 'off');
    ta.setAttribute('autocomplete', 'off');
    ta.placeholder = '4 Thought Monitor\n4 Frogmite\n…\n\nSideboard\n2 Haywire Mite';
    var d1 = el('p', 'ed-dica', 'Uma carta por linha («4 Nome»). «Sideboard» (ou uma linha vazia) separa o side; o export do Moxfield e do MTGO também serve.');
    var l2 = el('label', '', 'De onde veio?'); l2.htmlFor = 'ed-fonte';
    var fo = el('input'); fo.id = 'ed-fonte'; fo.type = 'text'; fo.required = true;
    fo.setAttribute('autocomplete', 'off'); fo.setAttribute('aria-describedby', 'ed-fonte-d');
    fo.placeholder = 'link, conta do Twitter, torneio…';
    var d2 = el('p', 'ed-dica', 'Obrigatório: é o que diz, daqui a um mês, de onde veio esta versão.'); d2.id = 'ed-fonte-d';
    var row = el('div', 'ed-row');
    var bg = botao('Gravar versão nova', 'pri'); bg.type = 'submit';
    var bc = botao('Cancelar'); bc.addEventListener('click', fecha);
    row.appendChild(bg); row.appendChild(bc);
    var res = el('div', 'ed-res-lista');
    [l1, ta, d1, l2, fo, d2, row, res].forEach(function(x){ f.appendChild(x); });
    corpoF.appendChild(f);
    f.addEventListener('submit', function(ev){
      ev.preventDefault();
      if (e0.ocupado) return;
      res.innerHTML = '';
      fo.removeAttribute('aria-invalid');
      if (!ta.value.trim()) { diz('Cola a lista primeiro.', true); ta.focus(); return; }
      if (!fo.value.trim()) {
        fo.setAttribute('aria-invalid', 'true');
        diz('Diz de onde veio a lista (um link, a conta do Twitter, o torneio…).', true);
        fo.focus(); return;
      }
      e0.ocupado = true; bg.disabled = true;
      diz('A gravar… (com nomes por corrigir pode demorar uns segundos)');
      pede('POST', '/api/n/lista', {deck: e0.deck, texto: ta.value, fonte: fo.value})
        .then(function(r){
          e0.ocupado = false; bg.disabled = false;
          if (r.ok && !r.dados.igual) recarrega();
          if (est !== e0) return;
          if (r.status === 422 && r.dados.nomes) {
            var m = el('div', 'ed-mal');
            m.setAttribute('role', 'alert');
            m.appendChild(el('p', '', 'Não conheço ' + (r.dados.nomes.length === 1 ? 'esta carta' : 'estas ' + r.dados.nomes.length + ' cartas')
              + ' — corrige a grafia e grava outra vez (não gravei nada):')).style.margin = '0';
            var ul = el('ul', 'ed-lista');
            r.dados.nomes.forEach(function(n){ ul.appendChild(el('li', '', n)); });
            m.appendChild(ul); res.appendChild(m);
            diz('');
            ta.focus();
            return;
          }
          if (!r.ok) { diz(r.dados.erro || 'Não gravei.', true); return; }
          if (r.dados.igual) { diz('A lista é igual à atual — não criei versão nova.'); return; }
          corpoF.innerHTML = '';
          corpoF.appendChild(titulo('Gravei a v' + r.dados.numero));
          var p = el('p', 'ed-amb');
          var ent = r.dados.entrou.map(function(x){ return '+' + x[1] + ' ' + x[0]; });
          var sai = r.dados.saiu.map(function(x){ return '−' + x[1] + ' ' + x[0]; });
          p.textContent = (ent.length || sai.length) ? ent.concat(sai).join(' · ')
            : (r.dados.numero === 1 ? 'Primeira lista deste deck.' : 'Só mudou de secção.');
          corpoF.appendChild(p);
          if (sai.length) corpoF.appendChild(el('p', 'ed-dica', 'O que saiu e estava marcado passou para Vender, em «Saíram dos decks».'));
          var ok = el('div', 'ed-row'), bf = botao('Fechar', 'pri');
          bf.addEventListener('click', fecha); ok.appendChild(bf); corpoF.appendChild(ok);
          diz('');
          bf.focus();
        }, function(err){
          e0.ocupado = false; bg.disabled = false;
          if (est === e0) diz(falhaPost(err), true);
        });
    });
    ta.focus();
  }

  // --------------------------------------------------------- montar um deck
  function abreMontar(btn){
    var e0 = {tipo: 'montar', deck: btn.getAttribute('data-deck'),
              nome: btn.getAttribute('data-nome-deck') || btn.getAttribute('data-deck')};
    abre(btn, e0);
    corpoF.appendChild(titulo('Montar o ' + e0.nome));
    diz('A ver o que trazer…');
    pede('GET', api('/api/n/movimentos', {deck: e0.deck})).then(function(r){
      if (est !== e0) return;
      if (!r.ok) { diz(r.dados.erro, true); return; }
      diz('');
      var d = r.dados, movs = d.movimentos;
      if (!d.montado_agora) corpoF.appendChild(el('p', 'ed-amb', 'Nenhum deck rotativo está montado agora: não há nada a trazer de outra caixa.'));
      else if (!movs.length) corpoF.appendChild(el('p', 'ed-amb', 'Montado agora: ' + d.montado_agora + '. Não há partilhadas marcadas para trazer.'));
      else {
        var de = {};
        movs.forEach(function(m){ (de[m.de_nome] = de[m.de_nome] || []).push(m); });
        for (var k in de) {
          corpoF.appendChild(el('p', 'ed-amb', 'Traz da caixa do ' + k + ' (o monte das partilhadas):'));
          var ul = el('ul', 'ed-lista');
          de[k].forEach(function(m){ ul.appendChild(el('li', '', m.qtd + ' ' + m.nome)); });
          corpoF.appendChild(ul);
        }
      }
      corpoF.appendChild(el('p', 'ed-dica', 'Depois disto o ' + e0.nome + ' fica o deck montado — só um rotativo de cada vez.'));
      var row = el('div', 'ed-row'), bm = botao('Montar', 'pri'), bc = botao('Cancelar');
      bc.addEventListener('click', fecha);
      bm.addEventListener('click', function(){
        if (e0.ocupado) return;
        e0.ocupado = true; bm.disabled = true; diz('A gravar…');
        pede('POST', '/api/n/montar', {deck: e0.deck}).then(function(r2){
          e0.ocupado = false; bm.disabled = false;
          if (r2.ok) recarrega();
          if (est !== e0) return;
          if (!r2.ok) { diz(r2.dados.erro || 'Não gravei.', true); return; }
          fecha();
          aviso('O ' + e0.nome + ' é agora o deck montado.');
        }, function(err){
          e0.ocupado = false; bm.disabled = false;
          if (est === e0) diz(falhaPost(err), true);
        });
      });
      row.appendChild(bm); row.appendChild(bc); corpoF.appendChild(row);
      bm.focus();
    }, function(){ if (est === e0) diz(REDE_GET, true); });
  }

  // ------------------------------------------------- Vender: procurar e +
  var procT = 0, procN = 0;
  function procura(inp){
    clearTimeout(procT);
    procT = setTimeout(function(){
      var q = inp.value.trim(), lista = document.getElementById('ed-res'), n = ++procN;
      if (!lista) return;
      if (q.length < 2) { lista.innerHTML = ''; return; }
      pede('GET', api('/api/n/procurar', {q: q})).then(function(r){
        if (n !== procN) return;
        lista.innerHTML = '';
        if (!r.ok) { lista.appendChild(el('li', 'vazio', r.dados.erro)); return; }
        if (!r.dados.length) { lista.appendChild(el('li', 'vazio', 'Nenhuma carta em papel com «' + q + '».')); return; }
        // em Vender o resultado abre «Tenho a mais»; na coleção aberta, «juntar»
        var acaoRes = lista.getAttribute('data-res') || 'novo', colRes = lista.getAttribute('data-colecao');
        r.dados.forEach(function(nome){
          var li = el('li'), b = botao(nome);
          b.setAttribute('data-acao', acaoRes); b.setAttribute('data-nome', nome);
          if (colRes) b.setAttribute('data-colecao', colRes);
          li.appendChild(b); lista.appendChild(li);
        });
      }, function(){ if (n === procN) { lista.innerHTML = ''; lista.appendChild(el('li', 'vazio', REDE_GET)); } });
    }, 250);
  }
  function abreAMais(btn){
    var col = btn.getAttribute('data-colecao');
    var e0 = {tipo: col ? 'juntar' : 'amais', colecao: col, nome: btn.getAttribute('data-nome'),
              eds: null, sel: null, acab: null, qtd: 1, ocupado: false};
    abre(btn, e0);
    corpoF.appendChild(titulo(e0.nome));
    diz('A carregar as edições…');
    pede('GET', api('/api/n/edicoes', {nome: e0.nome})).then(function(r){
      if (est !== e0) return;
      if (!r.ok) { diz(r.dados.erro, true); return; }
      e0.eds = r.dados.filter(temAcab);
      // nenhuma pré-escolhida: a primeira da lista é a mais recente (muitas
      // vezes uma Secret Lair), e acrescentar a edição errada é pior do que um
      // toque a mais
      e0.sel = e0.eds.length === 1 ? e0.eds[0] : null;
      e0.acab = e0.sel ? acabsDe(e0.sel)[0] : null;
      diz('');
      redesenha(desenhaAMais);
    }, function(){ if (est === e0) diz(REDE_GET, true); });
  }
  function desenhaAMais(){
    var e0 = est, s = e0.sel;
    corpoF.innerHTML = '';
    var top = el('div', 'ed-top'), big = el('div', 'ed-big'), info = el('div', 'ed-info');
    if (s) big.appendChild(imgEdicao(s, true, e0.nome + ', ' + s.set_name));
    else big.appendChild(el('span', 'ed-semimg', e0.nome));
    top.appendChild(big);
    info.appendChild(titulo(e0.nome));
    info.appendChild(el('p', 'ed-amb', e0.tipo === 'juntar'
      ? 'Juntar à coleção, na edição e no acabamento que tens (em inglês).'
      : 'Acrescentar a «Tenho a mais», na edição e no acabamento que tens.'));
    if (s) {
      var seg = el('div', 'seg ed-seg'), fins = acabsDe(s);
      seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Acabamento');
      fins.forEach(function(a){
        var b = el('button', a === e0.acab ? 'on' : '', NOME_ACAB[a]);
        b.type = 'button'; b.setAttribute('data-k', 'acab-' + a);
        b.setAttribute('aria-pressed', a === e0.acab ? 'true' : 'false');
        if (fins.length < 2) b.disabled = true;
        b.addEventListener('click', function(){ e0.acab = a; redesenha(desenhaAMais); });
        seg.appendChild(b);
      });
      info.appendChild(seg);
    } else info.appendChild(el('p', 'ed-tens', 'Escolhe a edição em baixo.'));
    if (e0.tipo !== 'juntar') {                          // juntar à coleção é uma carta
      var q = el('div', 'ed-qtd'), bm = botao('−', '', 'q-menos'), out = el('output', '', String(e0.qtd)), bp = botao('+', '', 'q-mais');
      bm.setAttribute('aria-label', 'Menos uma'); bp.setAttribute('aria-label', 'Mais uma');
      out.setAttribute('aria-live', 'polite'); out.setAttribute('aria-label', 'Quantidade');
      bm.disabled = e0.qtd <= 1;
      bm.addEventListener('click', function(){ if (e0.qtd > 1) { e0.qtd--; redesenha(desenhaAMais); } });
      bp.addEventListener('click', function(){ e0.qtd++; redesenha(desenhaAMais); });
      q.appendChild(bm); q.appendChild(out); q.appendChild(bp);
      info.appendChild(q);
    }
    top.appendChild(info);
    corpoF.appendChild(top);
    corpoF.appendChild(el('p', 'ed-rot', 'Que edição? — trend do Cardmarket' + (e0.eds.length > 1 ? ' · ' + e0.eds.length + ' edições' : '')));
    var grade = el('div', 'ed-eds');
    e0.eds.forEach(function(e){
      var on = s && e.scryfall_id === s.scryfall_id, acab = acabPara(e, e0.acab || 'nonfoil'), p = precoDe(e, acab);
      var b = el('button', 'ed-ed' + (on ? ' on' : ''));
      b.type = 'button'; b.setAttribute('data-k', 'ed-' + e.scryfall_id);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.title = e.set_name + ' #' + e.collector_number;
      b.appendChild(imgEdicao(e, false, ''));
      b.appendChild(el('span', 'ed-set', e.set_code.toUpperCase() + ' · ' + e.collector_number));
      b.appendChild(el('b', p === null ? 'sp' : '', p === null ? 'sem preço' : eur(p)));
      b.setAttribute('aria-label', e.set_name + ' número ' + e.collector_number + ', ' + (p === null ? 'sem preço' : eur(p)));
      b.addEventListener('click', function(){ e0.sel = e; e0.acab = acab; redesenha(desenhaAMais); });
      grade.appendChild(b);
    });
    if (!e0.eds.length) grade.appendChild(el('p', 'vazio', 'O catálogo não tem nenhuma impressão em papel desta carta.'));
    corpoF.appendChild(grade);
    var row = el('div', 'ed-row ed-fixa');
    var ba = botao(!s ? 'Escolhe a edição' : e0.tipo === 'juntar' ? 'Juntar à coleção'
                   : 'Acrescentar ' + e0.qtd + ' a Tenho a mais', 'pri', 'acrescentar'),
        bc = botao('Cancelar');
    ba.disabled = !s || e0.ocupado;
    bc.addEventListener('click', fecha);
    ba.addEventListener('click', function(){
      if (e0.ocupado || !e0.sel) return;
      e0.ocupado = true; ba.disabled = true; diz('A gravar…');
      var sel = e0.sel, acab = e0.acab, qtd = e0.qtd, juntar = e0.tipo === 'juntar';
      pede('POST', juntar ? '/api/n/colecao/juntar' : '/api/n/a_mais',
           juntar ? {colecao: e0.colecao, scryfall_id: sel.scryfall_id, acabamento: acab, lingua: 'en'}
                  : {scryfall_id: sel.scryfall_id, acabamento: acab, delta: qtd})
        .then(function(r){
          e0.ocupado = false;
          if (r.ok && juntar) {                          // a busca recomeça vazia
            var qi = document.getElementById('ed-q');
            if (qi) qi.value = '';
          }
          if (r.ok) recarrega();
          if (est !== e0) return;
          if (!r.ok) { ba.disabled = false; diz(r.dados.erro || 'Não gravei.', true); return; }
          fecha();
          aviso(juntar ? e0.nome + ' (' + sel.set_code.toUpperCase() + ', ' + NOME_ACAB[acab].toLowerCase()
                         + '): juntei à coleção.'
            : e0.nome + ' (' + sel.set_code.toUpperCase() + ', ' + NOME_ACAB[acab].toLowerCase()
              + '): tens agora ' + r.dados.qtd + ' a mais.');
        }, function(err){
          e0.ocupado = false;
          if (est === e0) { ba.disabled = false; diz(falhaPost(err), true); }
        });
    });
    row.appendChild(ba); row.appendChild(bc);
    corpoF.appendChild(row);
  }

  // ------------------------------------------------ Vender: as linhas
  function linha(b, url, corpo, ok, repete){
    if (b.disabled) return;
    focoDepois = chaveDe(b);
    b.disabled = true;
    pede('POST', url, corpo, repete).then(function(r){
      b.disabled = false;
      if (!r.ok) { aviso(r.dados.erro || 'Não gravei.', true); return; }
      aviso(ok(r.dados));
      recarrega();
    }, function(err){ b.disabled = false; aviso(falhaPost(err), true); });
  }
  function linhaAMais(b){
    var d = parseInt(b.getAttribute('data-delta'), 10);
    linha(b, '/api/n/a_mais', {scryfall_id: b.getAttribute('data-sid'), acabamento: b.getAttribute('data-acab'), delta: d},
          function(r){ return (b.getAttribute('data-nome') || 'Carta') + ': tens ' + r.qtd + ' a mais.'; });
  }
  function linhaSaida(b){
    var destino = b.getAttribute('data-destino'), id = parseInt(b.getAttribute('data-saida'), 10),
        nome = b.getAttribute('data-nome') || 'esta carta', qtd = b.getAttribute('data-qtd') || '';
    if (destino === 'a_mais') {
      linha(b, '/api/n/saida', {id: id, destino: destino},
            function(){ return nome + ': passou para Tenho a mais.'; });
      return;
    }
    if (destino === 'devolver') {                        // (M5)
      linha(b, '/api/n/saida', {id: id, destino: 'devolver'},
            function(){ return nome + ': voltou ao deck.'; });
      return;
    }
    var e0 = {tipo: 'saida'};
    abre(b, e0);
    corpoF.appendChild(titulo('Já trataste de ' + nome + '?'));
    corpoF.appendChild(el('p', 'ed-amb', (qtd ? qtd + ' × ' : '') + nome + ' sai de Vender e deixa de contar no valor — '
      + 'é para quando já a vendeste, a deste ou se foi.'));
    var row = el('div', 'ed-row'), bs = botao('Já tratei', 'pri'), bn = botao('Cancelar');
    bn.addEventListener('click', fecha);
    bs.addEventListener('click', function(){
      bs.disabled = true; diz('A gravar…');
      pede('POST', '/api/n/saida', {id: id, destino: 'descartar'}).then(function(r){
        bs.disabled = false;
        if (r.ok) recarrega();
        if (est !== e0) return;
        if (!r.ok) { diz(r.dados.erro || 'Não gravei.', true); return; }
        fecha(); aviso(nome + ': tratado.');
      }, function(err){ bs.disabled = false; if (est === e0) diz(falhaPost(err), true); });
    });
    row.appendChild(bs); row.appendChild(bn); corpoF.appendChild(row);
    bs.focus();
  }

  // ------------------------------------------------------ as coleções
  // Botões por baixo de cada carta de `colecoes.html` (e o «não vender» das
  // linhas de Vender): um toque, um POST, e `recarrega()` a seguir. O número
  // que fica no ecrã é sempre o que o servidor disse.
  function idCarta(b){ return parseInt(b.getAttribute('data-carta'), 10); }
  function nomeDaCarta(b){
    var f = b.closest ? b.closest('.cc, li.vl') : null, t = f ? f.querySelector('figure, .vi b, img') : null;
    if (!t) return 'a carta';
    return t.getAttribute('title') || t.getAttribute('alt') || t.textContent || 'a carta';
  }
  function colMarca(b){
    var d = parseInt(b.getAttribute('data-delta'), 10), nome = nomeDaCarta(b);
    // um request_id por toque: se a rede falhar a meio e o pedido repetir, conta uma vez
    linha(b, '/api/n/colecao/marca', {carta: idCarta(b), delta: d, request_id: idPedido()},
          function(r){ return nome + ': tens ' + r.tenho + '.'; }, 2);
  }
  function colVender(b){
    var v = b.getAttribute('data-vender') === '1', nome = nomeDaCarta(b);
    linha(b, '/api/n/colecao/vender', {carta: idCarta(b), vender: v},
          function(){ return nome + (v ? ': marcada para vender.' : ': já não está para vender.'); });
  }
  function colMeta(b){
    var e0 = {tipo: 'meta', ocupado: false}, nome = nomeDaCarta(b);
    abre(b, e0);
    corpoF.appendChild(titulo('Meta · ' + nome));
    var f = el('form', 'ed-form'); f.noValidate = true;
    var l1 = el('label', '', 'Quantas queres ter?'); l1.htmlFor = 'ed-meta';
    var inp = el('input'); inp.id = 'ed-meta'; inp.type = 'number'; inp.min = '0'; inp.step = '1';
    inp.setAttribute('inputmode', 'numeric'); inp.value = b.getAttribute('data-meta') || '4';
    var dica = el('p', 'ed-dica', 'A meta conta para «tenho X de Y» e para quanto falta; 0 tira a carta do progresso.');
    var row = el('div', 'ed-row'), bg = botao('Gravar meta', 'pri'), bc = botao('Cancelar');
    bg.type = 'submit'; bc.addEventListener('click', fecha);
    row.appendChild(bg); row.appendChild(bc);
    [l1, inp, dica, row].forEach(function(x){ f.appendChild(x); });
    corpoF.appendChild(f);
    f.addEventListener('submit', function(ev){
      ev.preventDefault();
      if (e0.ocupado) return;
      var v = inp.value.trim();
      if (!/^\d{1,3}$/.test(v)) { diz('A meta é um número inteiro, 0 ou mais.', true); inp.focus(); return; }
      e0.ocupado = true; bg.disabled = true; diz('A gravar…');
      pede('POST', '/api/n/colecao/meta', {carta: idCarta(b), meta: parseInt(v, 10)}).then(function(r){
        e0.ocupado = false; bg.disabled = false;
        if (r.ok) recarrega();
        if (est !== e0) return;
        if (!r.ok) { diz(r.dados.erro || 'Não gravei.', true); return; }
        fecha(); aviso(nome + ': meta ' + v + '.');
      }, function(err){
        e0.ocupado = false; bg.disabled = false;
        if (est === e0) diz(falhaPost(err), true);
      });
    });
    inp.focus(); inp.select();
  }
  // O botão «Juntar carta» mostra a busca (a de Vender); um resultado dela é
  // outro `cjuntar`, com o nome, e abre a escolha da edição.
  function colJuntar(b){
    if (b.getAttribute('data-nome')) { abreAMais(b); return; }
    var inp = document.getElementById('ed-q');
    if (!inp) return;
    var caixa = inp.closest ? inp.closest('.ed-proc') : null;
    if (caixa) { caixa.hidden = false; if (caixa.scrollIntoView) caixa.scrollIntoView({block: 'center'}); }
    inp.focus({preventScroll: true});
  }
  // A foto dele <-> a imagem oficial (o `data-oficial` da carta com recorte).
  function colOficial(fig){
    var im = fig ? fig.querySelector('img') : null, of = fig ? fig.getAttribute('data-oficial') : null;
    if (!im || !of) return;
    var oficial = fig.getAttribute('data-vendo') === 'oficial';
    if (oficial) { im.src = fig.getAttribute('data-foto'); fig.removeAttribute('data-vendo'); }
    else {
      fig.setAttribute('data-foto', im.getAttribute('src'));
      im.removeAttribute('srcset'); im.src = of; fig.setAttribute('data-vendo', 'oficial');
    }
    var cc = fig.closest('.cc'), bt = cc ? cc.querySelector('[data-acao="coficial"]') : null;
    if (bt) {
      bt.textContent = oficial ? 'ver oficial' : 'ver a minha';
      bt.setAttribute('aria-pressed', oficial ? 'false' : 'true');
    }
  }

  // ------------------------------------------------------------ eventos
  // Delegados no documento: sobrevivem à troca do <main> depois de cada POST.
  document.addEventListener('click', function(ev){
    var t = ev.target;
    if (!t || !t.closest || (folha && folha.contains(t))) return;
    var b = t.closest('[data-acao]');
    if (b) {
      var a = b.getAttribute('data-acao');
      ev.preventDefault();
      if (a === 'colar') abreColar(b);
      else if (a === 'montar') abreMontar(b);
      else if (a === 'amais') linhaAMais(b);
      else if (a === 'saida') linhaSaida(b);
      else if (a === 'novo') abreAMais(b);
      else if (a === 'cmarca') colMarca(b);
      else if (a === 'cmeta') colMeta(b);
      else if (a === 'cvender') colVender(b);
      else if (a === 'cjuntar') colJuntar(b);
      else if (a === 'coficial') {
        var cc = b.closest('.cc');
        colOficial(cc ? cc.querySelector('figure[data-oficial]') : null);
      }
      return;
    }
    // uma carta de coleção com recorte: o toque mostra a oficial (e outra vez a dele)
    var of = t.closest('figure.ct[data-oficial]');
    if (of && !of.hasAttribute('data-deck')) { colOficial(of); return; }
    var c = t.closest('figure.ct[data-deck]');
    if (c) abreCarta(c);
  });
  document.addEventListener('input', function(ev){
    if (ev.target && ev.target.id === 'ed-q') procura(ev.target);
  });
  document.addEventListener('keydown', function(ev){
    if (aberta()) {
      if (ev.key === 'Escape') { ev.preventDefault(); fecha(); return; }
      if (ev.key === 'Tab') {
        var f = focaveis();
        if (!f.length) return;
        var a = f[0], z = f[f.length - 1], at = document.activeElement;
        if (!folha.contains(at)) { ev.preventDefault(); a.focus(); }
        else if (ev.shiftKey && at === a) { ev.preventDefault(); z.focus(); }
        else if (!ev.shiftKey && at === z) { ev.preventDefault(); a.focus(); }
      }
      return;
    }
    var t = ev.target;
    if ((ev.key === 'Enter' || ev.key === ' ') && t && t.matches && t.matches('figure.ct[data-deck]')) {
      ev.preventDefault();
      abreCarta(t);
    }
  });
})();
"""


def css(editable: bool) -> str:
    """O CSS que vai a seguir ao `visual.CSS` no `<head>` (nada sem edição)."""
    return CSS if editable else ""


def script(editable: bool) -> str:
    """O `<script>` da edição, a pôr no fim da página (nada sem edição)."""
    return f"<script>{JS}</script>" if editable else ""
