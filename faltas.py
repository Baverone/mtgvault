"""Gera faltas.html — A LISTA DE FALTAS, PARA PROCURAR EM GHENT (2026-10-05).

*"preciso tambem da lista de faltas desses decks para poder procurar em Ghent"*.
O motor está em `mtgvault/faltas.py`; esta é a vista.

O ALVO NÃO É O TELEMÓVEL EM GERAL: é o telemóvel **de pé, numa mão**, num
pavilhão, com a outra mão a segurar cartas. É isso que decide o desenho, e é por
isso que esta página não se parece com a aba Decks:

* **o NOME manda e a imagem é um apoio.** Ele diz o nome ao vendedor; a arte
  serve-lhe para confirmar que é a carta certa. Por isso o nome vai a 17 px, a
  negrito, e **nunca se corta** (`overflow-wrap:anywhere`) — uma «Swords to
  Plow…» ao balcão não é um nome. Na aba Decks é ao contrário, e também está
  certo: ali ele está sentado a ordenar cartas e o que procura é a arte;
* **SUBTOTAL POR DECK**, no cabeçalho de cada secção e no modo «por deck». É o
  número que lhe diz onde vale a pena gastar a volta ao pavilhão;
* **40 IMAGENS no primeiro ecrã, o resto ao rolar** (`IMG_LOTE`). Não é só
  `loading=lazy`: as linhas acima das 40 nascem com um lugar RESERVADO
  (`aspect-ratio`) e sem `<img>`, e um `IntersectionObserver` põe a imagem quando
  ela se aproxima. Sem o observador há um botão. Com 295 cópias em lista, pedir
  tudo de uma vez era mandar o pavilhão descarregar 295 imagens por uma rede de
  dados partilhada por mil pessoas;
* **alvos de 44 px** nos filtros e na ordenação, e **zero rolamento horizontal**:
  não há tabela nenhuma: é uma lista, e cada linha é uma grelha que encolhe.
"""
from __future__ import annotations

import json
from pathlib import Path

from mtgvault import faltas_vista as motor
from mtgvault import paginas
from mtgvault import site_shell as shell

ROOT = Path(__file__).resolve().parent
PAGINA = "faltas.html"
TITULO = "Faltas para procurar"

_LEAD = ("O que falta comprar, por deck, com o subtotal de cada um — para "
         "procurar nas bancas.")

# As imagens que o primeiro ecrã pede vivem no `paginas` — é a MESMA regra da
# Fase 3 da Arrumação, e duas constantes ao lado davam dois números para o mesmo
# orçamento.
IMG_LOTE = paginas.IMG_LOTE

_CSS = """
 .barrafl{display:flex;flex-direction:column;gap:10px;margin:0 0 18px}
 .grp{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .grp .rot{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em;flex:0 0 100%}
 .grp button{min-height:44px;padding:10px 16px;border-radius:999px;border:1px solid var(--line);background:var(--card2);color:var(--muted);font:inherit;font-size:14px;font-weight:600;cursor:pointer}
 .grp button.cur{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 .chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
 .dsec{margin:0 0 26px}
 .dhd{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 10px;padding:10px 0 8px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:2}
 .dhd h2{margin:0;font-size:17px}
 .dhd .fmt{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:2px 8px}
 .dhd .sub{margin:0;font-size:12.5px;color:var(--muted)}
 .dhd .tot{margin-left:auto;font-weight:800;color:var(--accent);font-size:16px;white-space:nowrap}
 .fl{list-style:none;margin:0;padding:0}
 .fr{display:grid;grid-template-columns:52px 1fr auto;gap:10px 12px;align-items:start;padding:12px 0;border-bottom:1px solid var(--line)}
 .fr .ca{grid-row:span 2;width:52px}
 .fr .nm{font-size:17px;font-weight:700;line-height:1.3;overflow-wrap:anywhere;color:var(--ink)}
 .fr .nm .q{display:inline-block;min-width:28px;margin-right:6px;padding:1px 6px;border-radius:6px;background:var(--accent-soft);border:1px solid var(--accent-line);color:var(--accent);font-size:14px;text-align:center}
 .fr .meta{grid-column:2;font-size:12.5px;color:var(--muted);line-height:1.5}
 .fr .meta .pt{color:var(--dim)}
 .fr .pr{text-align:right;white-space:nowrap}
 .fr .pr b{display:block;font-size:16px;color:var(--ink)}
 .fr .pr span{font-size:12px;color:var(--dim)}
 .fr .sp{color:var(--warn)}
 .fr .av{grid-column:2/-1;margin:4px 0 0;font-size:12px;line-height:1.5;border-radius:8px;padding:7px 10px}
 .fr .av.aviso{background:var(--warn-soft);border:1px solid var(--warn-line);color:var(--ink)}
 .fr .av.aviso b{color:var(--warn)}
 .fr .av.nota{background:var(--sunken);border:1px solid var(--line);color:var(--dim)}
 .fr .urg{grid-column:2/-1;margin:4px 0 0;font-size:12px;font-weight:700;color:var(--bad)}
 .maisimg{min-height:44px;width:100%;margin:14px 0;padding:11px 16px;border-radius:10px;border:1px dashed var(--line);background:var(--card2);color:var(--muted);font:inherit;font-weight:600;cursor:pointer}
 .prop{margin:30px 0 0;padding:14px 16px;border:1px dashed var(--accent-line);border-radius:var(--r);background:var(--card2)}
 .prop h2{margin:0 0 6px;font-size:16px;color:var(--accent)}
 .prop .sub{margin:0 0 4px;font-size:13px;line-height:1.6;color:var(--muted)}
 .vazio{color:var(--dim);font-size:13px;padding:20px 0}
 .cpw{display:flex;gap:8px;align-items:center;margin:0 0 16px}
 .cpw button{min-height:44px;padding:10px 16px;border-radius:999px;border:1px solid var(--line);background:var(--card2);color:var(--muted);font:inherit;font-weight:600;cursor:pointer}
 .cpw textarea{position:absolute;left:-9999px;width:1px;height:1px}
 @media (max-width:640px){
  .fr{grid-template-columns:48px 1fr;gap:8px 10px}
  .fr .ca{width:48px}
  .fr .pr{grid-column:2;text-align:left}
  .fr .pr b{display:inline;margin-right:8px}
  .dhd .tot{margin-left:0;flex:0 0 100%}
 }
"""

_RODAPE = (
    "<b>Como ler esta página.</b> Uma linha por carta que FALTA — o que já tens "
    "não aparece, porque a falta é o «comprar» da alocação e esse já desconta o "
    "que tens, o que está noutra caixa e o que já encomendaste. O subtotal de "
    "cada deck é o que te diz onde vale a pena a volta ao pavilhão. "
    "<b>O preço é de referência, não é uma cotação.</b> Onde a linha leva um "
    "aviso, o preço vem de uma impressão que aquela caixa não aceita (uma "
    "reimpressão posterior, no Premodern) e ao lado está o da mais barata que "
    "serve. Onde leva uma nota, a caixa pede uma língua e o preço não tem "
    "língua nenhuma: a base guarda o preço por impressão, e a impressão é "
    "inglesa. As imagens são da impressão que podes comprar; chegam às "
    "quarenta e as outras entram ao rolar."
)


def _tmpl() -> str:
    """O molde é uma FUNÇÃO e não uma constante (decisão de 2026-09-25): a barra
    lateral depende do config, e uma constante ficava com a resposta que o config
    deu a quem importasse o ficheiro primeiro."""
    titulo = shell.titulo_de(PAGINA) or TITULO
    return (
        "<!doctype html><html lang=pt><head>"
        + shell.head(titulo, _CSS + paginas.CSS_DADOS + paginas.CSS_IMAGENS)
        + "</head><body>"
        + shell.abrir(PAGINA, titulo, _LEAD)
        + '<div class="chips" id="chips"></div>'
          '<div class="barrafl" id="barra"></div>'
          '<div class="cpw"><button type="button" id="copiar">copiar lista</button>'
          '<textarea id="cmk" readonly></textarea></div>'
          '<div id="vista"><p class="carregando">a carregar…</p></div>'
        + shell.fechar(_RODAPE, scripts="<script>%JS%</script>")
        + "</body></html>")


_JS = r"""
%JS_DADOS%
%JS_IMAGENS%
let D = null;
let FMT = '';          /* o formato filtrado; '' = todos */
let ORD = 'valor';     /* 'valor' | 'deck' */
let MOSTRA = IMG_LOTE; /* quantas imagens esta vista já pede */
const el = id => document.getElementById(id);
const eur = v => (v == null ? '—' : Number(v).toLocaleString('pt-PT',
  {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €');

/* As linhas que o filtro deixa passar, já na ordem escolhida. Uma função só: o
   cabeçalho, a lista e o texto para copiar leem todos daqui, senão o total dos
   chips dizia uma coisa e a lista outra. */
function visiveis() {
  const out = [];
  for (const d of D.decks) {
    if (FMT && d.formato !== FMT) continue;
    for (const l of d.linhas) out.push({...l, deck: d.nome, formato: d.formato});
  }
  if (ORD === 'valor') out.sort((a, b) => b.total - a.total || a.nm.localeCompare(b.nm, 'pt'));
  else out.sort((a, b) => a.deck.localeCompare(b.deck, 'pt')
                          || b.total - a.total || a.nm.localeCompare(b.nm, 'pt'));
  return out;
}

function linhaHTML(l, comImagem, comDeck) {
  const a = l.aviso;
  return `<li class="fr">`
    + arteHTML(l.sid, l.nm, comImagem)
    + `<div class="nm"><span class="q">${l.q}&times;</span>${escDados(l.nm)}</div>`
    + `<div class="pr"><b${l.unit == null ? ' class="sp"' : ''}>`
    + `${l.unit == null ? 'sem preço' : eur(l.total)}</b>`
    + `<span>${l.unit == null ? '' : eur(l.unit) + '/cóp.'}</span></div>`
    + `<div class="meta">${comDeck ? `<b>${escDados(l.deck)}</b> · ` : ''}`
    + `<span class="pt">${escDados(l.req)}</span>`
    + `${l.board === 'side' ? ' · sideboard' : ''}</div>`
    + (l.urgencia ? `<p class="urg">⏳ ${escDados(l.urgencia.porque || '')}`
        + `${l.urgencia.ate ? ' — até ' + escDados(l.urgencia.ate) : ''}</p>` : '')
    + (a ? `<p class="av ${a.grau === 'aviso' ? 'aviso' : 'nota'}">`
        + `${a.grau === 'aviso' ? '⚠️ <b>o preço não é do material que esta caixa pede.</b> '
                                : 'ⁱ '}`
        + `${escDados(a.frase)}.</p>` : '')
    + `</li>`;
}

function chipsHTML() {
  const ls = visiveis();
  const t = {cartas: new Set(ls.map(l => l.nm)).size,
             copias: ls.reduce((s, l) => s + l.q, 0),
             valor: ls.reduce((s, l) => s + l.total, 0),
             serve: ls.reduce((s, l) => s + l.total_serve, 0),
             sp: ls.reduce((s, l) => s + (l.unit == null ? l.q : 0), 0),
             av: ls.filter(l => l.aviso && l.aviso.grau === 'aviso').length};
  /* OS DOIS TOTAIS LADO A LADO. O primeiro é o do motor (o mínimo entre
     impressões); o segundo usa a impressão que cada caixa ACEITA, e é o que ele
     vai pagar na banca. Com um só, o subtotal que decide onde ele vai caçar
     estava abaixo do real — medido: 67 das 121 cartas de Premodern. */
  return `<span class="chip gold"><b>${eur(t.valor)}</b> a comprar</span>`
    + (Math.round(t.serve * 100) !== Math.round(t.valor * 100)
      ? `<span class="chip warn"><b>${eur(t.serve)}</b> com a impressão que serve`
        + `</span>` : '')
    + `<span class="chip"><b>${t.cartas}</b> cartas · ${t.copias} cóp.</span>`
    + (t.sp ? `<span class="chip"><b>${t.sp}</b> cóp. sem preço</span>` : '')
    + (t.av ? `<span class="chip"><b>${t.av}</b> com o preço fora da regra</span>` : '');
}

function barraHTML() {
  const fs = [['', 'Todos']].concat(D.formatos.map(f => [f, f]));
  return `<div class="grp"><span class="rot">Formato</span>`
    + fs.map(([k, r]) => `<button type="button" data-fmt="${escDados(k)}"`
      + ` class="${FMT === k ? 'cur' : ''}">${escDados(r)}</button>`).join('')
    + `</div><div class="grp"><span class="rot">Ordenar</span>`
    + [['valor', 'por valor'], ['deck', 'por deck']].map(([k, r]) =>
      `<button type="button" data-ord="${k}" class="${ORD === k ? 'cur' : ''}">`
      + `${r}</button>`).join('')
    + `</div>`;
}

function propostaHTML() {
  if (!D.proposta.length) return '';
  const p = D.totais_proposta;
  return `<div class="prop"><h2>PROPOSTA — formato sem deck escolhido</h2>`
    + `<p class="sub">Ainda não escolheste o deck destes formatos, por isso estas `
    + `faltas <b>não contam para o total</b> acima. Ficam aqui para não `
    + `desaparecerem: ${p.cartas} cartas, ${p.copias} cópias, ${eur(p.valor)}.</p>`
    + D.proposta.map(d => `<div class="dsec"><div class="dhd">`
      + `<h2>${escDados(d.nome)}</h2><span class="fmt">${escDados(d.formato)}</span>`
      + `<span class="tot">${eur(d.valor)}</span></div>`
      + `<ul class="fl">${d.linhas.map(l => linhaHTML(l, false, false)).join('')}</ul>`
      + `</div>`).join('')
    + `</div>`;
}

function vistaHTML() {
  const ls = visiveis();
  if (!ls.length) return `<p class="vazio">Nada a comprar neste filtro.</p>`
    + propostaHTML();
  const img = contaArtes(MOSTRA);  /* o orçamento de imagens desta vista */
  let out = '';
  if (ORD === 'deck') {
    for (const d of D.decks) {
      if (FMT && d.formato !== FMT) continue;
      const mine = ls.filter(l => l.deck === d.nome);
      if (!mine.length) continue;
      out += `<div class="dsec"><div class="dhd"><h2>${escDados(d.nome)}</h2>`
        + `<span class="fmt">${escDados(d.formato)}</span>`
        + `<span class="tot">${eur(d.valor)}</span>`
        + `<p class="sub">${d.cartas} cartas · ${d.copias} cóp. · ${escDados(d.req)}`
        + `${d.sem_preco ? ' · ' + d.sem_preco + ' sem preço' : ''}`
        + (Math.round(d.valor_serve * 100) !== Math.round(d.valor * 100)
          ? ` · <b>${eur(d.valor_serve)}</b> com a impressão que esta caixa aceita`
          : '') + `</p></div>`
        + `<ul class="fl">${mine.map(l => linhaHTML(l, img(), false)).join('')}</ul>`
        + `</div>`;
    }
  } else {
    out += `<ul class="fl">${ls.map(l => linhaHTML(l, img(), true)).join('')}</ul>`;
  }
  const faltam = img.pedidas() - MOSTRA;
  if (faltam > 0) out += `<button type="button" class="maisimg" id="maisimg">`
    + `⬇ mostrar as imagens das outras ${faltam} linhas</button>`;
  return out + propostaHTML();
}

function render() {
  const c = el('chips'), b = el('barra'), v = el('vista');
  if (c) c.innerHTML = chipsHTML();
  if (b) b.innerHTML = barraHTML();
  if (v) v.innerHTML = vistaHTML();
  const t = el('cmk');
  if (t) t.value = visiveis().map(l => `${l.q} ${l.nm}`).join('\n');
  observaArtes(v);
  try { history.replaceState(null, '', FMT ? '#f=' + FMT : '#'); } catch (e) { /* file:// */ }
}

function ligar() {
  if (typeof document.addEventListener !== 'function') return;
  document.addEventListener('click', ev => {
    const b = ev.target.closest('button');
    if (!b) return;
    if (b.id === 'maisimg') { MOSTRA += IMG_LOTE * 4; render(); return; }
    if (b.id === 'copiar') {
      const t = el('cmk');
      try { t.select(); document.execCommand('copy'); b.textContent = 'copiado ✓'; }
      catch (e) { b.textContent = 'copia à mão'; }
      setTimeout(() => { b.textContent = 'copiar lista'; }, 2500);
      return;
    }
    if (b.dataset.fmt !== undefined) { FMT = b.dataset.fmt; MOSTRA = IMG_LOTE; render(); return; }
    if (b.dataset.ord) { ORD = b.dataset.ord; MOSTRA = IMG_LOTE; render(); }
  });
}

async function arranca() {
  try { D = await carregaDados('faltas.json'); }
  catch (e) { erroDados(el('vista'), e); return; }
  const h = (location.hash || '').replace('#', '');
  if (h.startsWith('f=')) {
    const f = decodeURIComponent(h.slice(2));
    if (D.formatos.indexOf(f) >= 0) FMT = f;
  }
  ligar();
  render();
}
arranca();
"""


def dados(con, rep=None) -> tuple[dict, dict]:
    """`(índice, partes)`.

    **Vai tudo no índice, e é uma decisão.** A página ORDENA e FILTRA do lado do
    browser — por valor, por deck, por formato — e isso só funciona com a lista
    inteira em mãos; partir os decks em partes punha um toque no filtro à espera
    de um `fetch`, que num pavilhão é o pior sítio do mundo para esperar por rede.
    São 186 linhas (medido a 2026-10-05), não as 845 da Fase 3.
    """
    from mtgvault import loadout                               # noqa: PLC0415
    rep = rep if rep is not None else loadout.report(con)
    v = motor.vista(con, rep)
    return dict(v, img_lote=IMG_LOTE), {}


def casca() -> str:
    """A página SEM dados — é o que o `webapp.py` serve no 8771."""
    return _tmpl().replace("%JS%", _js())


def _js() -> str:
    return (_JS.replace("%JS_DADOS%", paginas.JS_DADOS)
            .replace("%JS_IMAGENS%", paginas.js_imagens()))


def build(con, out_path=None, rep=None):
    out = Path(out_path) if out_path else (ROOT / PAGINA)
    idx, partes = dados(con, rep)
    paginas.escrever_dados(out, "faltas", idx, partes)
    out.write_text(_tmpl().replace("%JS%", _js()), encoding="utf-8")
    return out


def html_page(con, rep=None) -> str:
    """A página com os dados EMBUTIDOS — é o que os testes lêem de um ficheiro
    solto (a mesma saída do `arrumacao.html_page`)."""
    idx, _partes = dados(con, rep)
    js = _js().replace("D = await carregaDados('faltas.json')",
                       "D = " + json.dumps(idx, ensure_ascii=False))
    return _tmpl().replace("%JS%", js)


if __name__ == "__main__":
    from mtgvault import db

    with db.session() as con:
        print(build(con))
