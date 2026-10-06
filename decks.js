

const DADOS_BASE = 'data/paginas/';
const TOKEN_URL = (() => { try { return new URLSearchParams(location.search).get('t') || ''; }
                            catch (e) { return ''; } })();
const escDados = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function carregaDados(caminho) {
  const url = DADOS_BASE + caminho + (TOKEN_URL ? '?t=' + encodeURIComponent(TOKEN_URL) : '');
  let r;
  try { r = await fetch(url); }
  catch (e) {
    throw new Error(`não consegui ir buscar ${caminho}: sem resposta do servidor`
      + (location.protocol === 'file:' ? ' — a página foi aberta do disco (file://) e assim não funciona; tem de ser servida por HTTP' : '')
      + ` (${e.message})`);
  }
  if (!r.ok) throw new Error(`não consegui ir buscar ${caminho}: o servidor respondeu ${r.status}`);
  try { return await r.json(); }
  catch (e) { throw new Error(`o ficheiro ${caminho} veio estragado (${e.message})`); }
}
function erroDados(el, e) {
  if (!el) return;
  el.innerHTML = `<div class="erro-dados" role="alert">⚠️ <b>Não consegui carregar os dados desta secção.</b>`
    + `<br>${escDados(e && e.message ? e.message : e)}`
    + `<span class="fine">Verifica a ligação e tenta outra vez. Se estás no modo edição, `
    + `confirma que o servidor (porto 8771) está de pé.</span>`
    + `<button type="button" onclick="location.reload()">recarregar</button></div>`;
}

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
/* Os euros em português, a MESMA forma da `faltas.html` e da `paginas.euros`:
   `1 234,56 €`. Escrito à mão com `toFixed(2)` dava `1234.56`, que é o ponto
   decimal de outra língua na página dele. */
const eur = v => (v == null ? '—' : Number(v).toLocaleString('pt-PT',
  {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €');
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
      <span class="modo ${x.n_sempre ? 'sm' : x.modo === 'rotativas' ? 'rot' : 'ded'}">${
        x.n_sempre ? 'sempre montados'
        : x.modo === 'rotativas' ? 'cartas rodam' : 'cartas dedicadas'}</span>
      <span class="fl"><b>${x.n_decks}</b> deck${x.n_decks === 1 ? '' : 's'} registado${
        x.n_decks === 1 ? '' : 's'} · <b>${x.n_marcados}</b> que queres montar${
        x.n_desactivadas ? ` · ${x.n_desactivadas} desactivada${
          x.n_desactivadas === 1 ? '' : 's'}` : ''}</span>
      <span class="fl">a somar <b>${n.soma || 0}</b> · a rodar <b>${n.maximo || 0}</b>${
        n.cartas ? ` · ${n.cartas} cartas distintas` : ''}${
        x.sleeves && x.sleeves.proxies
          ? ` · <b>${x.sleeves.proxies}</b> proxies a imprimir` : ''}</span>
      <span class="fm">${esc(x.n_sempre ? x.texto_sempre : x.texto_modo)}</span>
    </button>`;
  }).join('') + '</div>';
}

/* AS LIGAS CONTAM-SE À PARTE (2026-10-05, à letra: *"procura todos os torneios !
   incluindo ligas, torneios presenciais"*). As ligas entraram no Modern, e uma
   liga é um 5-0 publicado SEM classificação e SEM tamanho de campo. Somada a uma
   Challenge, a percentagem do formato passa a medir duas coisas ao mesmo tempo e
   o número fica PIOR, não melhor — por isso mostram-se as DUAS contas, como o
   *«a somar»* vs *«a rodar»* de 04/10 e a `curva_staples`. Sem isto, ele olhava
   para uma percentagem que pode ter mexido só porque a fonte mudou. */
function ligasHTML(p) {
  const l = p && p.ligas, s = p && p.sem_ligas;
  if (!l || !s || !l.conta) return '';            /* formato sem ligas: nada */
  const sobe = l.pct > s.pct;
  return `<p class="pq dois"><b>Com as ligas e sem elas:</b>`
    + ` <span class="n2">sem ligas <b>${s.listas}</b> de <b>${s.total}</b>`
    + ` (<b>${s.pct} %</b>)</span>`
    + ` <span class="n2">só as ligas <b>${l.listas}</b> de <b>${l.total}</b>`
    + ` (<b>${l.pct} %</b>)</span>`
    + ` — uma liga é um 5-0 sem classificação e sem tamanho de campo, por isso`
    + ` não é o mesmo dado que uma Challenge. ${sobe
      ? `Aqui as ligas <b>puxam a percentagem para cima</b>: parte da subida é`
        + ` a fonte nova, não o deck a jogar-se mais.`
      : `Aqui as ligas <b>diluem</b> a percentagem — jogam este deck`
        + ` <b>menos</b> do que os torneios, por isso o número de cima é mais`
        + ` baixo do que o de antes delas entrarem.`}</p>`;
}

/* AS FALTAS DOS DECKS DE UM JOGADOR QUE ELE SEGUE (2026-10-06, à letra:
   *"Separa na pagina o que e so do Grinding Station … do que e so do Song of
   Creation, porque ele pode querer um e nao o outro"*).

   TRÊS SACOS E NÃO DOIS: há cartas que faltam aos dois decks (2 Endurance e 1
   Haywire Mite, medido a 06/10). Metê-las num dos lados respondia mal à
   pergunta dele — se quiser só o Song of Creation, continua a precisar delas.
   Por isso cada deck leva o que é só dele, as partilhadas vão à parte, e cada
   um diz quanto custa **se for o único que ele montar**.

   OS DOIS PREÇOS lado a lado (a disciplina do «a somar» vs «a rodar»): o grupo
   `spml`, onde a caixa de Modern vive, pede EN foil — mas estes decks não são
   caixas e nada os obriga ao foil. São 58,59 € de diferença em 16 cópias; é
   decisão dele e esconder uma das contas era decidir por ele. */
function faltasJogadorHTML(u) {
  const js = u.faltas_jogador || [];
  if (!js.length) return '';
  const linha = l => `<div class="flr">
      <span class="flq">${l.falta}×</span>
      <span class="flnm">${esc(l.nm)}</span>
      <span class="flp">${l.unit == null
        ? '<b class="zero">sem preço</b>'
        : `<b>${eur(l.unit * l.falta)}</b>`}${
        l.unit != null && l.price_finish !== 'foil'
          ? ` <span class="tag q" title="o CardTrader não cota esta carta em foil`
            + ` — este preço é do nonfoil">nonfoil</span>` : ''}</span>
      <span class="flt">${l.tem ? `tens ${l.tem} de ${l.pede}` : ''}</span>
    </div>`;
  const soma = (s, rot) => `<span class="n2">${rot} <b>${s.cartas}</b> cartas · `
    + `<b>${s.copias}</b> cópias · <b>${eur(s.eur)}</b>${
      s.sem_preco ? ` <span class="tag q">${s.sem_preco} sem preço</span>` : ''}`
    + `</span>`;
  let out = '';
  js.forEach(j => {
    const t = j.totais, p = j.partilhadas;
    out += `<details class="fjg" open><summary><b>Faltas dos decks do `
      + `${esc(j.jogador)}</b> — ${t.cartas} cartas, ${t.copias} cópias, `
      + `${eur(t.eur)}${t.sem_preco ? ` (${t.sem_preco} sem preço)` : ''}`
      + `</summary>`
      + `<p class="stpn">A falta é <b>o que a lista pede menos o que tens</b> —`
      + ` não é o «a comprar» da alocação da <a href="faltas.html">lista para`
      + ` Ghent</a>, que desconta o que está noutra caixa e o que já`
      + ` encomendaste: estes decks não são caixas e não passam pela alocação.`
      + ` O preço é <b>foil</b>, que é o que o grupo desta caixa pede, e o`
      + ` <b>nonfoil ao lado</b> porque estes decks não são caixas e nada os`
      + ` obriga ao foil: <b>${eur(t.eur)}</b> em foil contra`
      + ` <b>${eur(t.eur_nonfoil)}</b> em nonfoil.</p>`;
    j.versoes.forEach(v => {
      out += `<div class="fjd"><div class="fjh"><b>${esc(v.nome)}</b>`
        + `<span class="fq">tens ${v.tem} de ${v.total} · ${v.pct} %</span></div>`
        /* O segundo número só sai HAVENDO partilhadas: sem elas é igual ao
           primeiro, e dois números iguais lado a lado leem-se como um erro. */
        + `<p class="pq dois">${soma(v.so, 'só deste deck:')}`
        + `${p.cartas ? soma(v.so_este, 'se montares só este:') : ''}</p>`
        + (v.linhas.length ? v.linhas.map(linha).join('')
           : `<p class="stpn">Não falta nada que seja só deste deck.</p>`)
        + `</div>`;
    });
    if (p.cartas) {
      out += `<div class="fjd part"><div class="fjh"><b>Falta aos dois</b>`
        + `<span class="fq">${p.cartas} cartas · ${p.copias} cópias · `
        + `${eur(p.eur)}</span></div>`
        + `<p class="stpn">Precisas destas <b>seja qual for o deck que`
        + ` escolheres</b> — é por isso que não estão somadas a nenhum dos`
        + ` dois.</p>`
        + p.linhas.map(linha).join('') + `</div>`;
    }
    out += `</details>`;
  });
  return out;
}

/* --------------------------------------------------------------- nível 2 */
/* UM DECK POR FORMATO, COM VERSÕES POR DENTRO (2026-10-04, à noite).
   *"quero ficar com 1 deck e versoes do deck (como opcoes)"*. O selector é de
   VERSÃO e não de deck: as versões são opções do mesmo deck, e por isso todas
   ficam protegidas da venda — o que a escolha muda é qual delas ele monta. */
function deckUnicoHTML(u) {
  if (!u) return '';
  let out = `<div class="unico"><div class="uh"><h3>${esc(u.nome)}</h3>`
    + `<span class="chip gold">o deck deste formato</span></div>`;
  if (u.porque) out += `<p class="pq">${esc(u.porque)}</p>`;
  if (u.por_decidir) {
    out += `<div class="ficha media"><h4>Por decidir</h4><p class="pq">Ainda não`
      + ` escolheste o deck deste formato, e por isso <b>não se libertou nada</b>`
      + ` dele para venda: uma carta que se jogue aqui fica retida (regra RLG).`
      + `</p></div>`;
  }
  /* MONTAR vs PROTEGER (2026-10-05, à letra: *"assim ficamos com uma lista de
     cartas que eu gostaria de nao vender, tudo o resto e «seguro» vender"*).
     As duas perguntas lado a lado, porque confundi-las custa caro nos dois
     sentidos: ou monta decks que não quer, ou vende cartas que quer. */
  if (u.protege) {
    /* Num formato DERIVADO (o Modern, desde 05/10) o critério é UM SÓ: quem
       joga a carta-chave é versão e está protegido. O que continua a ser
       distinto é o gesto — montar é escolher UMA; proteger são todas. */
    out += `<div class="ficha media"><h4>${u.derivado
        ? 'Um critério só: joga ' + esc(u.protege.carta)
        : 'Proteger ≠ montar'}</h4><p class="pq">`
      + (u.derivado
        ? `<b>${u.protege.listas}</b> das <b>${u.protege.total}</b> listas deste `
          + `formato na janela jogam ${esc(u.protege.carta)} `
          + `(<b>${u.protege.pct} %</b>), de qualquer arquétipo — e <b>todas</b> `
          + `contam, para as duas coisas: são elas as versões deste deck aqui em `
          + `baixo, e uma carta que apareça em ${u.limiar} ou mais delas <b>não `
          + `vai à venda</b> (regra RP). Montar continua a ser escolher <b>uma</b> `
          + `versão; proteger são <b>todas</b>.`
        : `<b>Montar:</b> a versão que escolheres, aqui em baixo. `
          + `<b>Proteger:</b> todas as <b>${u.protege.listas}</b> listas deste `
          + `formato que jogam ${esc(u.protege.carta)} — ${u.protege.listas} de `
          + `${u.protege.total} na janela (<b>${u.protege.pct} %</b>), de qualquer `
          + `arquétipo. Uma carta que apareça em ${u.limiar} ou mais dessas listas `
          + `<b>não vai à venda</b> (regra RP). Os «outros decks» aqui em baixo `
          + `<b>também protegem</b>, mesmo não sendo versões.`)
      + `</p>${ligasHTML(u.protege)}</div>`;
  }
  /* A ANOTAÇÃO QUE PERDEU O CLUSTER (2026-10-05). Vai em DESTAQUE e não num
     rodapé: o que isto apanha é o deck PRINCIPAL a aparecer morto, e foi o que
     esteve a um passo de acontecer ao deck do RC de Ghent. Ver
     `versoes._orfas`. Sem órfãs não se desenha nada — um aviso permanente
     é um aviso que se deixa de ler. */
  (u.orfas || []).forEach(o => {
    out += `<div class="ficha aviso"><h4>⚠ ${esc(o.nome)}: o agrupamento mudou`
      + ` de baixo dela</h4><p class="pq">Esta versão está marcada como `
      + (o.principal ? '<b>o deck principal</b>' : '<b>a escolhida</b>')
      + ` e o arquétipo que ela aponta (<code>${o.arquetipo_id}</code>) ficou `
      + `<b>sem uma única lista na janela</b>. O <code>archetype_id</code> é `
      + `refeito todas as noites e muda quando a composição de um grupo muda, `
      + `por isso o deck pode ter passado para outro.`
      + (o.candidato
        ? ` O maior grupo sem anotação é agora <code>${o.candidato.arquetipo_id}</code>`
          + ` — <b>${esc(o.candidato.nome)}</b>, ${o.candidato.listas} lista`
          + `${o.candidato.listas === 1 ? '' : 's'}: é o candidato a pôr no`
          + ` <code>arquetipo_id</code> desta anotação.`
        : ` Não há nenhum grupo sem anotação para onde ele possa ter ido.`)
      + ` Enquanto isto estiver aqui, o nome e a marca desta versão podem estar`
      + ` a descrever um deck que já não se joga.</p></div>`;
  });
  if (u.versoes && u.versoes.length) {
    /* O CONJUNTO DAS VERSÕES VEM DA BASE (2026-10-05, à letra: *"no Modern, a
       unica coisa e que quero os decks que joguem Mox Opal, seja affinity, seja
       grinding station, seja outra coisa qualquer"*). Dois grupos, e a
       diferença entre eles é toda a honestidade desta lista: o que se joga
       AGORA, e o que é conhecido e hoje não tem listas na janela. O Grinding
       Station é do segundo grupo — não se inventa como actual nem se esconde. */
    const vrow = v => {
      const cl = v.pct >= 95 ? 'ok' : v.pct >= 50 ? 'mid' : 'lo';
      return `<div class="vrow${v.escolhida ? ' sel' : ''}${v.na_janela ? '' : ' fora'}">
        <label class="vq"><input type="radio" name="versao-${esc(u.formato)}"
          data-versao="${esc(u.formato)}|${esc(v.id)}"${v.escolhida ? ' checked' : ''}${
          EDIT() ? '' : ' disabled'}></label>
        <div class="vn"><div class="vnome">${esc(v.nome)}${
          v.principal ? ' <span class="chip gold">principal</span>' : ''}${
          v.escolhida ? ' <span class="tag">a montar</span>' : ''}${
          /* A MARCA DO JOGADOR (2026-10-06, à letra: *"Marca-os como «do
             CesarMerjan» para ele os distinguir dos outros"*). Vai no NOME e
             não no subtítulo: é por ela que ele distingue as duas listas de um
             jogador que segue das oito que o agrupamento trouxe. */
          v.jogador ? ` <span class="chip jog">do ${esc(v.jogador)}</span>` : ''}${
          v.origem_nome === 'etiqueta'
            ? ' <span class="tag q" title="a fonte ainda não dá nome a este deck'
              + ' — isto é a etiqueta das cartas distintivas">etiqueta</span>' : ''}</div>
          <div class="dsub">${v.sem_lista ? 'sem lista'
            : `tens <b>${v.tem}</b> de <b>${v.total}</b>`}${
            /* UMA VERSÃO FIXA NÃO TEM «N listas na janela», e dizer-lhe «zero»
               era mentir por vocabulário: ela É uma lista, jogada num dia. O
               que se diz é a data — e, estando antes da janela, que está. */
            v.fixa
              ? (v.data
                  ? ` · lista de <b>${esc(v.data)}</b>${v.na_janela ? ''
                      : ' <b class="zero">(antes da janela)</b>'}`
                  : '')
              : v.na_janela
                ? ` · <b>${v.listas}</b> lista${v.listas === 1 ? '' : 's'} na janela`
                : ` · <b class="zero">zero listas na janela</b>${
                    v.listas_total ? ` · ${v.listas_total} antes dela` : ''}`}${
            v.nota ? ' · ' + esc(v.nota) : ''}</div>
          <div class="bar"><i class="${cl === 'ok' ? 'ok' : ''}" style="width:${v.pct}%"></i></div>
        </div>
        <div class="dpct ${cl}">${v.sem_lista ? '—' : v.pct + '%'}</div>
        ${v.deck ? `<button class="verd" data-d="${esc(v.deck)}">ver ▶</button>` : ''}
      </div>`;
    };
    const agora = u.versoes.filter(v => v.na_janela);
    const fora = u.versoes.filter(v => !v.na_janela);
    out += `<div class="vsel"><div class="vt">Versões — escolhe a que vais montar`
      + `${u.derivado ? ` <span class="tag">todas as que jogam ${
        esc(u.carta_chave)}</span>` : ''}</div>`;
    if (u.derivado) {
      out += `<p class="stpn">O conjunto sai da <b>base</b>, não de uma lista`
        + ` escrita à mão: é versão todo o arquétipo que jogue`
        + ` <b>${esc(u.carta_chave)}</b>${u.desde ? `, desde ${esc(u.desde)}` : ''}`
        + ` — Affinity ou não. Um arquétipo novo com a carta <b>entra`
        + ` sozinho</b>.</p>`;
    }
    /* AS SEIS FAMÍLIAS (2026-10-06, à letra: *"O MOX OPAL DE MODERN TEM SEIS
       FAMILIAS, nao uma. Mostra-as … Seis familias numa lista plana nao se
       le"*). Agrupa-se o que se joga AGORA pela família, com a contagem de cada
       uma ao lado; sem `familias` no config a lista fica plana como estava. A
       família sai das CARTAS e nunca do cluster — ver `versoes.familias`. */
    const fams = u.familias || [];
    if (u.derivado && fams.length && agora.length) {
      out += `<div class="vgt">A jogar-se agora — ${agora.length}, em `
        + `${fams.length} famílias</div>`
        + `<p class="stpn">A família sai das <b>cartas</b> de cada lista e não do`
        + ` agrupamento: o <code>archetype_id</code> é refeito todas as noites e`
        + ` muda, uma carta como <b>${esc(fams[0].nome)}</b> não. É por isso que`
        + ` este agrupamento não se desfaz de um dia para o outro.</p>`;
      fams.forEach(f => {
        const dela = agora.filter(v => (v.familia || 'Outra') === f.nome);
        if (!dela.length) return;
        out += `<div class="fgt"><b>${esc(f.nome)}</b>`
          + `<span class="fq">${dela.length} ${
            dela.length === 1 ? 'versão' : 'versões'}`
          + `${f.listas ? ` · ${f.listas} lista${f.listas === 1 ? '' : 's'}` : ''}`
          + `</span></div>` + dela.map(vrow).join('');
      });
      /* Uma versão cuja família o config não cobre não desaparece: cai em
         «Outra» e diz-se. Esconder era perder um deck de Mox Opal — que é
         exactamente o que o critério inclusivo de 05/10 veio impedir. */
      const soltas = agora.filter(v => !fams.some(f => f.nome === (v.familia || 'Outra')));
      if (soltas.length) {
        out += `<div class="fgt"><b>Outra</b><span class="fq">${soltas.length}`
          + ` — joga ${esc(u.carta_chave)} e não cai em nenhuma das famílias`
          + `</span></div>` + soltas.map(vrow).join('');
      }
    } else {
      out += (u.derivado && fora.length
        ? `<div class="vgt">A jogar-se agora — ${agora.length}</div>` : '')
        + agora.map(vrow).join('');
    }
    if (fora.length) {
      out += `<div class="vgt">Conhecidas, sem listas na janela — ${fora.length}</div>`
        + `<p class="stpn">Não aparecem em listas desde`
        + `${u.desde ? ' ' + esc(u.desde) : ' o início da janela'}. Ficam à vista`
        + ` com o zero dito: nem se escondem, nem contam como atuais.</p>`
        + fora.map(vrow).join('');
    }
    out += '</div>';
    if (u.derivado) {
      const sc = u.sem_cluster, fj = u.fora_da_janela || {}, nms = u.sem_cluster_nomes || [];
      const p = [];
      if (sc) p.push(`<b>${sc}</b> lista${sc === 1 ? '' : 's'} que o agrupamento`
        + ` ainda não identificou${nms.length ? ` (a fonte: «${
          nms.map(esc).join('», «')}»)` : ''} — não viram versão, porque uma`
        + ` versão precisa de identidade estável`);
      if (fj.clusters) p.push(`<b>${fj.clusters}</b> arquétipos (${fj.listas}`
        + ` listas) jogaram ${esc(u.carta_chave)} <b>antes</b> da janela — um que`
        + ` volte a aparecer entra sozinho`);
      if (p.length) out += `<p class="pq">Mais: ${p.join('; ')}.</p>`;
    }
  }
  out += faltasJogadorHTML(u);
  if (u.nota) out += `<p class="pq">${esc(u.nota)}</p>`;
  /* OS OUTROS QUE JOGAM A CARTA-CHAVE — derivados da base a cada corrida, nunca
     escritos à mão. *"NAO decidas por ele incluir nem excluir definitivamente"*:
     ficam à vista, com o teste do critério ao lado, para ele poder incluir um. */
  const o = (u.outros || []).filter(z => !z.sem_cluster);
  const sc = (u.outros || []).find(z => z.sem_cluster);
  if (o.length || sc) {
    const passam = o.filter(z => z.passa_criterio).length;
    out += `<details class="stp"><summary><b>Outros decks que jogam ${
      esc(u.carta_chave)}</b> — ${o.length}${passam ? `, ${passam} que passam o critério` : ''}`
      + `</summary><p class="stpn">Não são versões deste deck: jogam a carta e são`
      + ` outros decks. Ficam aqui para decidires — nenhum entrou nem saiu`
      + ` definitivamente.${u.protege ? ' <b>As cartas deles estão protegidas da'
        + ' venda na mesma</b>: proteger é todas as listas que jogam a carta,'
        + ' montar é só a versão que escolheres.' : ''}</p><div class="stpl">`
      + o.map(z => `<div class="stpr">
          <span class="sq">${z.listas}</span>
          <span class="snm">${esc(z.nome || z.label || ('arquétipo ' + z.arquetipo_id))}</span>
          <span class="sd">${(z.exige || []).map(e =>
            `${esc(e.carta)} ${e.pct.toFixed(0)}%`).join(' · ')}</span>
          <span class="st${z.passa_criterio ? '' : ' falta'}">${
            z.passa_criterio ? 'passa o critério' : 'não é versão'}${
            u.protege ? ' · protege' : ''}</span>
        </div>`).join('')
      + (sc ? `<div class="stpr"><span class="sq">${sc.listas}</span>
          <span class="snm">listas sem arquétipo</span>
          <span class="sd">o agrupamento ainda não lhes deu identidade</span>
          <span class="st falta">não é versão</span></div>` : '')
      + '</div></details>';
  }
  if (u.saidos && u.saidos.length) {
    out += `<details class="stp"><summary><b>Decks que saíram da escolha</b> — ${
      u.saidos.length}</summary><p class="stpn">Não se apagaram: continuam com a`
      + ` lista e a proveniência, aqui em baixo, marcados «${esc('meta, não escolhido')}».`
      + `</p></details>`;
  }
  return out + '</div>';
}

function nivelDecks(x) {
  const n = x.necessidade || {}, rot = x.modo === 'rotativas';
  const sm = !!x.n_sempre;
  const manda = k => (rot ? k === 'rodar' : k === 'somar') ? ' manda' : '';
  let out = `<div class="migalha"><button data-f="">◀ formatos</button>
    <span><b>${esc(x.formato)}</b> — ${esc(sm ? x.texto_sempre : x.texto_modo)}</span></div>`;
  /* O MODO DO FORMATO NÃO SE APAGOU, E A PÁGINA DIZ QUAL ERA (2026-10-05).
     Ele pode voltar atrás: desmarcar «principal» devolve o formato ao
     `cartas_partilhadas` do grupo. Sem esta linha, um Premodern que o config diz
     `rotativas` e que a página conta pela SOMA parecia o config a ter mudado. */
  if (x.modo_trocado) {
    out += `<div class="ficha media"><h4>Sempre montados</h4><p class="pq">`
      + `<b>${x.n_sempre}</b> dos decks que vais montar são <b>principais</b>:`
      + ` ficam montados em permanência e o que falta leva <b>proxy</b>. Por isso`
      + ` a necessidade deste formato conta pela <b>soma</b> e já não pelo`
      + ` <b>${esc(x.modo_formato === 'rotativas' ? 'máximo' : 'soma')}</b> que a`
      + ` regra do grupo pede (<code>cartas_partilhadas:`
      + ` ${esc(x.modo_formato)}</code>). A regra do grupo não se apagou — tira a`
      + ` marca «principal» a um deck e ele volta a rodar.</p></div>`;
  }
  out += deckUnicoHTML(x.deck_unico);
  out += `<div class="duo">
    <div class="n${manda('somar')}"><span class="et">a somar</span>
      <div class="v">${n.soma || 0}</div>
      <div class="sub">cada deck as suas · faltam ${n.faltam_a_somar || 0}</div></div>
    <div class="n${manda('rodar')}"><span class="et">a rodar</span>
      <div class="v">${n.maximo || 0}</div>
      <div class="sub">uma cópia serve todos · faltam ${n.faltam_a_rodar || 0}</div></div>
  </div>`;
  /* A SEQUÊNCIA DELE, pela ordem que ele deu (2026-10-04 ao fim do dia):
     *"falta escolher decks, falta depois eu organizar os decks, guardar as que
     sao staples"*. Num formato rotativo sem nada marcado, a página dizia os dois
     números a zero e mais nada — não dizia que o primeiro passo é marcar. */
  /* Num formato do modelo de versões não há nada a marcar: a escolha é a VERSÃO,
     logo acima. Mostrar-lhe «marca os decks que vais montar» era mandá-lo fazer
     um gesto que já não existe. */
  if (rot && !x.n_marcados && !x.deck_unico) {
    out += `<div class="passos"><b>Por onde começar</b><ol>`
      + `<li>marca <b>«quero montar»</b> nos decks que vais montar, aqui em baixo`
      + ` (estão ordenados pelos que já tens mais completos);</li>`
      + `<li>aparecem aqui as cartas <b>próprias</b> de cada deck e as`
      + ` <b>partilhadas</b>;</li>`
      + `<li>as partilhadas são as <b>staples</b>: ficam de fora dos decks,`
      + ` guardadas juntas, e cada deck leva um proxy.</li></ol></div>`;
  }
  if (x.sleeves && x.sleeves.decks) {
    const s = x.sleeves;
    out += `<div class="chips"><span class="chip">sleeves: <b>${s.total}</b> cartas nos ${
      s.decks} decks ${sm ? 'montados' : 'marcados'}</span>`
      + `<span class="chip">verdadeiras <b>${s.reais}</b></span>`
      /* PROXIES A IMPRIMIR = um por carta diferente em cada deck, que é a conta
         DELE (medida: 147 em Modern contra os 149 do papel dele; por cópias
         dava 334). As cópias vão ao lado com etiqueta — são o que de facto vai
         em proxy —, pela regra dos «dois números» de 2026-10-04 à tarde. */
      + `<span class="chip gold">proxies a imprimir <b>${s.proxies}</b></span>`
      + (s.proxies_copias != null && s.proxies_copias !== s.proxies
          ? `<span class="chip">${s.proxies_copias} cópias ${
              sm ? 'vão em proxy' : 'saem dos decks'}</span>` : '')
      + '</div>';
  }
  /* PIONEER NÃO TEM STAPLES, E ISSO DIZ-SE (ordem dele: *"Mostra isso
     explicitamente em vez de uma tabela vazia, que uma tabela vazia parece uma
     avaria"*). Medido: o Greasefang e o Flow State não partilham uma única
     carta. */
  if (rot && !sm && x.n_marcados && !(x.staples || []).length) {
    out += `<div class="ficha media"><h4>Sem staples neste formato</h4>`
      + `<p class="pq">Os ${x.n_marcados} decks marcados <b>não partilham uma`
      + ` única carta</b>: não há nada para guardar à parte e não há proxies para`
      + ` imprimir. Ficam os dois inteiramente sleevados com cartas verdadeiras.`
      + `</p></div>`;
  }
  /* AS CARTAS DISPUTADAS: num formato SEMPRE MONTADO não há pilha à parte — cada
     deck tem a carta dentro, verdadeira num e proxy nos outros. A pergunta «em
     quantos decks entra esta carta» continua a valer, e é aqui que ele vê QUAL
     deck fica com as verdadeiras (ordem dele: 2026-10-05). */
  if (sm && (x.disputadas || []).length) {
    out += `<details class="stp" open><summary><b>Cartas em mais do que um deck</b>`
      + ` — ${x.disputadas.length} carta${x.disputadas.length === 1 ? '' : 's'}`
      + `</summary>`
      + `<p class="stpn">Cada deck fica com a carta <b>dentro</b>. Quem leva as`
      + ` verdadeiras é o deck de maior prioridade; os outros levam proxy.</p>`
      + '<div class="stpl">'
      + x.disputadas.map(s => `<div class="stpr dsp">
          <span class="sq">${s.pede}&times;</span>
          <span class="snm">${esc(s.nm)}</span>
          <span class="sd">em ${s.n_decks} decks · tens ${s.tenho}</span>
          <span class="st${s.proxies ? ' falta' : ''}">${
            s.proxies ? `${s.verdadeiras} verdadeira${s.verdadeiras === 1 ? '' : 's'}`
                        + ` · ${s.proxies} proxy${s.proxies === 1 ? '' : 's'}`
                      : 'todas verdadeiras'}</span>
          <span class="dspq">${s.decks.map(k =>
            `<span class="${k.proxies ? 'pxc' : 'vd'}">${esc(k.nome)}: ${
              k.verdadeiras ? k.verdadeiras + ' real' + (k.verdadeiras === 1 ? '' : 'is') : ''
            }${k.verdadeiras && k.proxies ? ' + ' : ''}${
              k.proxies ? k.proxies + ' proxy' + (k.proxies === 1 ? '' : 's') : ''
            }</span>`).join('')}</span>
        </div>`).join('') + '</div></details>';
  }
  if (sm && x.n_sempre && !(x.disputadas || []).length) {
    out += `<div class="ficha media"><h4>Nenhuma carta em dois decks</h4>`
      + `<p class="pq">Os ${x.n_sempre} decks sempre montados <b>não partilham`
      + ` uma única carta</b>: nenhuma cópia verdadeira está a ser disputada.</p>`
      + `</div>`;
  }
  /* AS STAPLES DO FORMATO: as partilhadas, agregadas. Deck a deck ele já as via
     (no nível 3); isto é a PILHA que ele guarda à parte. */
  if (x.staples && x.staples.length) {
    out += `<details class="stp" open><summary><b>Staples a guardar à parte</b>`
      + ` — ${x.staples.length} carta${x.staples.length === 1 ? '' : 's'} em 2 ou`
      + ` mais dos decks marcados</summary>`
      + `<p class="stpn">Ficam fora dos decks, numa pilha só. Cada deck leva um`
      + ` proxy; a verdadeira entra à hora de jogar.</p><div class="stpl">`
      + x.staples.map(s => `<div class="stpr">
          <span class="sq">${s.precisa}&times;</span>
          <span class="snm">${esc(s.nm)}</span>
          <span class="sd">em ${s.n_decks} decks</span>
          <span class="st${s.falta ? ' falta' : ''}">${
            s.falta ? `tens ${s.tenho} — faltam ${s.falta}` : `tens ${s.tenho}`}</span>
        </div>`).join('') + '</div></details>';
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
    else if (d.fonte === 'dele') sub.push('deck teu');
    else sub.push('meta');
    /* COM LISTA DE EVENTO, o subtítulo é QUEM a jogou e ONDE — é o que ele lê
       para decidir por onde começa, sem ter de abrir os onze decks. Sem ela fica
       a nota de sempre. */
    if (d.evento) {
      const e = d.evento, t = [];
      if (e.jogador) t.push(e.jogador);
      if (e.classificacao) t.push(/^\d+$/.test(e.classificacao)
        ? e.classificacao + '.º' : e.classificacao);
      if (e.jogadores) t.push('de ' + e.jogadores);
      if (e.data) t.push(e.data);
      sub.push(t.join(' · '));
    } else if (d.nota) sub.push(d.nota);
    if (d.ja_e_caixa) sub.push('já é uma caixa tua');
    if (d.marcado_em && !x.deck_unico) sub.push('marcado em ' + d.marcado_em);
    /* QUEM SAIU DA ESCOLHA diz quando e porquê, e não desaparece. */
    if (d.saiu) sub.push(`saiu em ${d.saiu.em} — ${d.saiu.porque}`);
    if (d.e_versao) sub.push('é uma versão do deck deste formato');
    /* UMA CAIXA DESACTIVADA NÃO É UM DECK DE 0 % (2026-10-04 ao fim do dia).
       Fica na lista — no fim, e com o rótulo à vista — em vez de desaparecer:
       o `caixas[].\_antes` do config repõe-na, e uma caixa que sumisse da página
       deixava-o sem por onde a reaver. O que ela não tem é a caixa «quero
       montar»: marcar um deck sem lista não quer dizer nada. */
    return `<div class="drow${d.quero ? ' quero' : ''}${d.desactivada ? ' off' : ''}">
      <div class="dn">
        <div class="dnome">${esc(d.nome)}${d.rotulo_estado
          ? ` <span class="tag">${esc(d.rotulo_estado)}</span>` : ''}</div>
        <div class="dsub">${d.sem_lista ? 'sem lista — nada para contar'
          : `tens <b>${d.tem}</b> de <b>${d.total}</b> cartas` +
            (d.side && d.side.total ? ` (main ${d.main.tem}/${d.main.total} · side ${d.side.tem}/${d.side.total})` : '')}
          ${sub.length ? ' · ' + esc(sub.join(' · ')) : ''}</div>
        <div class="bar"><i class="${cl === 'ok' ? 'ok' : ''}" style="width:${d.pct}%"></i></div>
      </div>
      <div class="dpct ${cl}">${d.sem_lista ? '—' : d.pct + '%'}</div>
      ${d.desactivada ? '<span class="qm off">desactivada</span>'
        : x.deck_unico ? `<span class="qm off">${d.e_versao ? 'versão deste deck'
            : d.saiu ? 'não escolhido' : 'meta'}</span>`
        : d.sempre_montado ? `<span class="qm off" title="é um deck principal: fica sempre montado">sempre montado</span>`
        : `<label class="qm"><input type="checkbox" data-quero="${esc(d.id)}"${
        d.quero ? ' checked' : ''}${EDIT() ? '' : ' disabled'}> quero montar</label>`}
      ${principalHTML(d)}
      <button class="verd" data-d="${esc(d.id)}">ver ▶</button>
    </div>`;
  }).join('') + '</div>';
  return out;
}

/* A MARCA «principal», EDITÁVEL (2026-10-05). Quais são os decks principais foi
   INTERPRETAÇÃO minha — ele disse *"esses"* depois de eu lhe listar as 12 caixas
   com lista —, e por isso tem de se poder corrigir num toque em vez de esperar
   por uma ordem. Só nas CAIXAS: `principal` é uma chave de `caixas[]`, e um
   arquétipo do meta ou uma versão não tem onde a guardar. */
function principalHTML(d) {
  if (!d.e_caixa || d.desactivada) return '';
  if (!EDIT()) {
    return d.principal
      ? `<span class="pr on" title="deck principal — sempre montado">★ principal</span>`
      : '';
  }
  return `<label class="pr${d.principal ? ' on' : ''}" title="${
    d.principal ? 'deck principal: fica sempre montado, com proxy no que falta'
                : 'marcar como deck principal (fica sempre montado)'}">`
    + `<input type="checkbox" data-principal="${esc(d.slot)}"${
        d.principal ? ' checked' : ''}> ★ principal</label>`;
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
      ${/* NUM DECK SEMPRE MONTADO o selo diz QUANTAS vão em proxy e não só
            «proxy»: num playset de 4 com 1 cópia a sério são 1 verdadeira + 3
            proxies, e um selo a seco mentia nas duas. */
        c.em_proxy ? `<span class="sh spx">${c.proxies}&times; proxy</span>`
        : rot && c.partilhada ? '<span class="sh">proxy</span>' : ''}
      ${c.desconhecida ? '<span class="unk">?</span>' : ''}
    </div>
    <div class="tname" title="${esc(c.nm)}">${esc(c.nm)}</div>
    <div class="orig${marcado ? ' mk' : c.desconhecida ? ' unkt' : c.pilha ? ' pl' : ''}">${
      c.desconhecida ? 'DESCONHECIDA — o catálogo não tem esta carta'
      /* UMA BÁSICA VEM DA PILHA DE UNHINGED e nunca de uma linha da `copies`:
         conta por contagem declarada (2026-10-02), não é falta e não leva
         proxy. Dizer «do inventário» num Island que a base não tem era a
         página a contradizer-se a si própria. */
      : c.pilha ? 'da pilha de básicas' + (c.na_base ? ` · ${c.na_base} na base` : '')
      : marcado ? 'marcaste tu' + (c.em ? ' · ' + esc(c.em) : '')
      : 'do inventário'}</div>
    ${c.pilha ? '' : `<div class="steppers">
      <button class="step minus" data-mais="-1" data-carta="${esc(c.nm)}"
        aria-label="menos uma de ${esc(c.nm)}"${c.tenho <= 0 ? ' disabled' : ''}>&minus;</button>
      <button class="step plus" data-mais="1" data-carta="${esc(c.nm)}"
        aria-label="mais uma de ${esc(c.nm)}">+</button>
    </div>`}
  </div>`;
}
const ART = sid => `https://cards.scryfall.io/small/front/${sid[0]}/${sid[1]}/${sid}.jpg`;

function blocos(gs, rot) {
  return gs.map(g => `<div class="typehdr">${esc(g.tipo)}<span class="nq">${g.q}</span></div>`
    + '<div class="grid">' + g.cartas.map(c => tileHTML(c, rot)).join('') + '</div>').join('');
}

/* A FICHA DA LISTA: de onde veio a lista por que ele vai sleevar.
   André, 2026-10-04 ao fim do dia: *"as outras quero que esquecas as decklists e
   vamos focar nas decklists baseadas em eventos reais"* — e, por isso mesmo,
   *"na pagina de cada deck fica SEMPRE, a vista: jogador, evento, data, numero
   de jogadores, classificacao e o URL da fonte"*. Uma lista errada custa-lhe uma
   tarde de sleeves; esta ficha é o que lhe permite conferir antes de começar. */
function linhaProv(e) {
  const L = [];
  if (e.jogador) L.push(['jogador', esc(e.jogador)]);
  if (e.classificacao) L.push(['classificação',
    /^\d+$/.test(e.classificacao) ? esc(e.classificacao) + '.º lugar' : esc(e.classificacao)]);
  if (e.evento) L.push(['evento', esc(e.evento)]);
  if (e.data) L.push(['data', esc(e.data)]);
  /* Um evento sem contagem de jogadores DIZ que não a tem, em vez de deixar a
     linha de fora: as listas do mtgo.com não trazem `event_players`, e uma ficha
     em que a linha desaparece parece uma ficha incompleta por acidente. */
  L.push(['jogadores', e.jogadores ? '<b>' + e.jogadores + '</b>'
    : '<span class="pq">a fonte não publica a contagem</span>']);
  if (e.tier) L.push(['tipo de evento', esc(e.tier)]);
  if (e.repetida > 1) L.push(['a mesma lista',
    '<b>' + e.repetida + ' resultados</b> — sem mudar uma carta']);
  if (e.url) L.push(['fonte', `<a href="${esc(e.url)}" target="_blank" rel="noopener">`
    + esc(e.url.replace(/^https?:\/\//, '').slice(0, 54)) + ' ↗</a>']);
  return L.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('');
}

function fichaHTML(p) {
  let out = '';
  /* A AMOSTRA FINA vem ANTES da lista e não escondida num rodapé: o Hammer Time
     entra porque ele o pediu, mas não pode aparecer com o mesmo peso dos outros
     nove — isso era mentir-lhe por omissão. */
  if (p.amostra_fina) {
    out += `<div class="aviso"><b>Atenção à amostra.</b> ${esc(p.amostra_fina)}</div>`;
  }
  if (p.por_confirmar) {
    out += '<div class="aviso"><b>Falta o teu OK.</b> Este é o melhor candidato ao '
      + 'deck que pediste'
      + (p.carta_chave ? `, pela carta <b>${esc(p.carta_chave)}</b>` : '')
      + (p.arquetipo_fonte ? ` (o mtgtop8 chama-lhe «${esc(p.arquetipo_fonte)}»)` : '')
      + '. Não foi marcado como deck a montar: confirma que é este e marca-o.</div>';
  }
  if (p.evento) {
    out += '<div class="ficha"><h4>A lista é esta, e foi jogada aqui</h4><dl>'
      + linhaProv(p.evento) + '</dl>'
      + (p.porque ? `<p class="pq">${esc(p.porque)}</p>` : '')
      + (p.escolhida_por ? `<p class="pq">escolhida por: ${esc(p.escolhida_por)}</p>` : '')
      + '</div>';
    /* A ALTERNATIVA fora da janela (regra 5 dele, à letra): *"NÃO a escondas e
       NÃO a descartes: mostra-a com a data bem visível e uma frase a dizer que é
       anterior ao Reality Fracture, e põe ao lado a melhor lista DENTRO da
       janela, para ele escolher."* Mostrar as duas é honesto. */
    if (p.alternativa) {
      out += '<div class="ficha media"><h4>A outra lista que podes querer ver</h4><dl>'
        + linhaProv(p.alternativa) + '</dl>'
        + `<p class="pq">${esc(p.alternativa.porque || '')}</p></div>`;
    }
  } else if (p.e_consenso) {
    out += '<div class="ficha media"><h4>Isto é um consenso, não uma lista jogada</h4>'
      + '<p class="pq">É a <b>média</b> de várias listas: ninguém jogou este deck '
      + 'exactamente assim. Serve para consulta e para comparar — não para sleevar. '
      + (p.nota ? esc(p.nota) : '') + '</p></div>';
  }
  return out;
}

function nivelDeck(p, fmt) {
  const rot = p.modo === 'rotativas', c = p.conta;
  let out = `<div class="migalha"><button data-f="">◀ formatos</button>
    <button data-f="${esc(fmt)}">◀ ${esc(fmt)}</button>
    <span><b>${esc(p.nome)}</b></span></div>`;
  const chips = [`<span class="chip">tens <b>${c.tem}</b> de <b>${c.total}</b> — <b>${c.pct}%</b></span>`];
  /* Uma carta que o catálogo não conhece não pode passar por «não tenho»: o
     número di-lo, senão ela ia para a lista de compras sem ninguém saber. */
  if (c.desconhecidas) chips.push(`<span class="chip warn">`
    + `<b>${c.desconhecidas}</b> desconhecida${c.desconhecidas > 1 ? 's' : ''}`
    + ` — o catálogo não tem o nome</span>`);
  if (c.side.total) chips.push(`<span class="chip">main ${c.main.tem}/${c.main.total} · `
    + `side ${c.side.tem}/${c.side.total}</span>`);
  if (p.comandante) chips.push(`<span class="chip gold">comandante: ${esc(p.comandante)}</span>`);
  if (p.principal) chips.push(`<span class="chip gold">★ deck principal</span>`);
  /* AS DUAS METADES, SEMPRE AS DUAS, e somam o total do deck — num deck sempre
     montado são «verdadeiras» e «em proxy»; num deck a rodar são «próprias» e
     «partilhadas». A disciplina é a do `confirmado.metades`. */
  if (p.reparticao && p.reparticao.sempre_montado) {
    chips.push(`<span class="chip">verdadeiras <b>${p.reparticao.n_verdadeiras}</b></span>`,
      `<span class="chip gold">em proxy <b>${p.reparticao.n_proxies}</b></span>`);
  } else if (p.reparticao) {
    chips.push(`<span class="chip">próprias <b>${p.reparticao.n_proprias}</b></span>`,
      `<span class="chip gold">partilhadas <b>${p.reparticao.n_partilhadas}</b> (levam proxy)</span>`);
  }
  out += '<div class="chips">' + chips.join('') + '</div>';
  out += fichaHTML(p);
  if (!p.evento && (p.nota || p.link)) {
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
  /* A LISTA DE PROXIES A IMPRIMIR — é isto que ele manda para a impressora.
     Num deck SEMPRE MONTADO é a lista de FALTAS dele (2026-10-05); num deck a
     rodar são as partilhadas (2026-10-04). Quem decide é o Python
     (`decks_vista.proxies_do_deck`): a página não refaz a conta. */
  if (p.reparticao && p.reparticao.proxies.length) {
    const r = p.reparticao, smd = !!r.sempre_montado;
    out += `<div class="sec"><h3>Proxies a imprimir (${
        smd ? r.proxies_imprimir + ' cartas · ' + r.n_proxies + ' cópias'
            : r.n_partilhadas})</h3>`
      + '<p>' + (smd
        ? 'É a lista de <b>faltas</b> deste deck: o deck fica montado em'
          + ' permanência, e cada carta que não tens entra em proxy.'
        : 'São exactamente as cartas partilhadas deste deck: ficam de fora, o deck'
          + ' leva o proxy, e a verdadeira entra à hora de jogar.')
      + '</p><div class="px">'
      + r.proxies.map(x => `<span>${x.q}&times; ${esc(x.nm)}${
          smd && x.tenho ? ` <i>(tens ${x.tenho} de ${x.pede})</i>` : ''}</span>`).join('')
      + '</div>'
      + (smd ? `<div class="cpl"><button class="cp" data-cp="px">copiar a lista`
          + `</button></div><textarea id="pxtxt" hidden>`
          + r.proxies.map(x => `${x.q} ${x.nm}`).join('\n') + `</textarea>` : '')
      + '</div>';
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

/* A MARCA «principal» (2026-10-05). Muda a REGRA do deck — passa a sempre
   montado, a necessidade dele passa a soma e os proxies passam a ser as faltas —,
   por isso o índice e as partes vêm de novo, como no «quero montar». */
async function principal(slot, on, cx) {
  if (!EDIT()) { cx.checked = !on; return; }
  try {
    const r = await fetch('/api/deck-principal' + (TOKEN_URL ? '?t=' + encodeURIComponent(TOKEN_URL) : ''), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({slot: slot, principal: on}),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || ('HTTP ' + r.status));
    toast(j.msg || 'gravado');
    PARTES = {};
    D = await carregaDados('decks.json');
    await render();
  } catch (e) { cx.checked = !on; toast('não sei se gravou: ' + e.message, true); }
}

/* ESCOLHER A VERSÃO. Muda o que ele monta, logo a necessidade do formato e as
   próprias/partilhadas: o índice e as partes vêm de novo, como no «quero
   montar». O que NÃO muda é a protecção — as outras versões continuam
   guardadas, porque são opções do mesmo deck. */
async function escolheVersao(chave, radio) {
  if (!EDIT()) { toast('esta página é só de leitura — abre o modo de edição', true); return; }
  const i = chave.indexOf('|');
  const fmt = chave.slice(0, i), vid = chave.slice(i + 1);
  try {
    const r = await fetch('/api/versao' + (TOKEN_URL ? '?t=' + encodeURIComponent(TOKEN_URL) : ''), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({formato: fmt, versao: vid}),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.erro || ('HTTP ' + r.status));
    toast(j.msg || 'gravado');
    PARTES = {};
    D = await carregaDados('decks.json');
    await render();
  } catch (e) { toast('não sei se gravou: ' + e.message, true); }
}

/* COPIAR A LISTA DE PROXIES. O `textarea` já tem o texto escrito pelo Python —
   a página não o volta a compor —, e o `select()`+`execCommand` é o caminho que
   funciona no browser do telemóvel dele sem pedir permissões. */
function copia(qual, bt) {
  const t = el(qual === 'px' ? 'pxtxt' : qual);
  if (!t) return;
  t.hidden = false; t.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  if (!ok && navigator.clipboard) {
    navigator.clipboard.writeText(t.value).then(() => toast('copiado'),
      () => toast('não consegui copiar', true));
  } else { toast(ok ? 'copiado' : 'não consegui copiar', !ok); }
  t.hidden = true;
  if (bt) bt.blur();
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
    const cp = ev.target.closest('[data-cp]');
    if (cp) { copia(cp.dataset.cp, cp); return; }
  });
  document.addEventListener('change', ev => {
    const c = ev.target.closest('[data-quero]');
    if (c) { quero(c.dataset.quero, c.checked, c); return; }
    const pr = ev.target.closest('[data-principal]');
    if (pr) { principal(pr.dataset.principal, pr.checked, pr); return; }
    const v = ev.target.closest('[data-versao]');
    if (v) escolheVersao(v.dataset.versao, v);
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
