"""Gera comandantes.html — o CONSENSO POR COMANDANTE (André, 2026-10-01).

*"Quero consenso de Duel Commander do deck dele (comandante CLOUD) sempre
actualizado, da mesma forma que já tem para os arquétipos de Modern."*

O motor está em `mtgvault/consenso.py` (e é lá que está escrito porque é que a
identidade de um deck de Duel Commander é o COMANDANTE e nunca a etiqueta do
clustering). Esta página é só a vista:

* a CASCA vai no HTML e os DADOS à parte (decisão de 2026-09-15), em
  `data/paginas/comandantes.json` (o índice: a lista de comandantes com o número
  de listas) + `data/paginas/comandantes/<comandante>.json` (uma parte por
  comandante, ida buscar quando ele o escolhe). O Cloud vem no índice, porque é o
  que abre;
* o `fetch` que falhe diz-lho em português (`paginas.erroDados`), nunca um ecrã
  vazio;
* cada carta cruza-se com o que ele TEM (`paginas.posse_total`, a coleção
  inteira) e diz quantas faltam;
* as imagens têm `loading="lazy"` e o tamanho escrito, para a grelha não saltar.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from mtgvault import consenso, paginas, scryfall, sources
from mtgvault import site_shell as shell

ROOT = Path(__file__).resolve().parent
PAGINA = "comandantes.html"

_CSS = """
 .av{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:0 0 18px}
 .av label{color:var(--muted);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
 .av select{min-height:40px;padding:8px 12px;border-radius:10px;border:1px solid var(--line);background:var(--card2);color:var(--ink);font:inherit;font-size:14px;max-width:100%}
 .chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}
 .chip{background:var(--card2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:12px;color:var(--muted)}
 .chip b{color:var(--ink)}
 .chip.gold{border-color:var(--accent-line);background:var(--accent-soft);color:var(--accent)}
 .aviso{background:var(--card2);border:1px solid var(--accent-line);color:var(--accent);border-radius:var(--r);padding:11px 15px;font-size:13px;margin:0 0 18px}
 /* "em letra grande" é literal: a ordem de 2026-10-03 pede que isto NÃO se leia
    como uma nota de pé de página ao lado de percentagens bonitas. */
 .aviso.grande{font-family:var(--font-hd);font-size:16px;line-height:1.5;padding:16px 18px}
 .aviso.grande b{color:var(--ink)}
 .aviso.grande .pq{display:block;margin-top:6px;font-family:var(--font);font-size:12.5px;color:var(--muted)}
 h2{font-size:15px;margin:26px 0 4px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
 h2 .n{color:var(--muted);font-size:12px;font-weight:500}
 .papelsub{color:var(--muted);font-size:12px;margin:0 0 12px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:10px}
 .c{position:relative;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card2)}
 .c img{width:100%;aspect-ratio:.716;display:block;object-fit:cover;object-position:top;background:var(--bg)}
 .c .nmo{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:6px;font-size:11px;color:var(--muted)}
 .c .pc{position:absolute;top:5px;left:5px;background:rgba(7,8,13,.86);border-radius:999px;padding:2px 7px;font-size:11px;font-weight:700;color:var(--ink)}
 .c .ps{position:absolute;top:5px;right:5px;background:rgba(7,8,13,.86);border-radius:999px;padding:2px 7px;font-size:11px;font-weight:700}
 .c .ps.ok{color:var(--add)} .c .ps.falta{color:var(--warn)}
 .c .lg{padding:6px 7px;font-size:11.5px;line-height:1.3}
 .c .lg b{display:block;font-weight:600;color:var(--ink)}
 .c .lg span{color:var(--dim);font-size:10.5px}
 .cmd{display:flex;gap:14px;align-items:flex-start;background:var(--card2);border:1px solid var(--accent-line);border-radius:var(--r);padding:14px;margin:0 0 20px}
 .cmd img{width:92px;border-radius:8px;display:block;background:var(--bg)}
 .cmd .ct{font-family:var(--font-hd);font-size:17px;margin:0 0 4px}
 .cmd .cs{color:var(--muted);font-size:12.5px;line-height:1.6}
 @media (max-width:640px){ .grid{grid-template-columns:repeat(3,minmax(0,1fr))} .cmd img{width:70px} }
"""

_LEAD = ("O consenso de cada comandante, calculado todos os dias a partir das "
         "listas de torneio recolhidas. Cada carta diz em quantas listas aparece "
         "e quantas ele já tem.")

_RODAPE = (
    "<p><b>Como se agrupa.</b> Em Duel Commander a identidade de um deck é o "
    "<b>comandante</b>, e nunca a etiqueta do agrupamento automático: na base de "
    "1 de outubro de 2026 havia 870 etiquetas deste formato e 808 delas sem uma "
    "única lista. Por isso cada lista guarda o nome do comandante na própria "
    "base, lido do sideboard da fonte (é lá que o mtgtop8 e o mtgo.com o servem) "
    "e derivado pela ordem das cartas nas listas que já cá estavam.</p>"
    "<p><b>Que listas contam.</b> As mesmas que contam para o metagame deste "
    "formato — e aqui isso quer dizer <b>ligas incluídas e presenciais de "
    "qualquer dimensão</b>, porque a cena é pequena: medido a 1 de outubro, a "
    "regra do Modern (sem ligas, 64 ou mais jogadores) deixava 48 listas no "
    "formato inteiro e <b>zero</b> para o Cloud. Ajusta-se em "
    "<code>colecao_config.json → metagame_fontes</code>.</p>"
    "<p><b>Os papéis.</b> Núcleo é o que aparece em 90 % ou mais das listas, "
    "flex entre 40 % e 90 %, raro abaixo de 40 %. O formato é singleton, por isso "
    "o número de cópias é quase sempre 1 — o que separa uma carta obrigatória de "
    "uma opção é a percentagem, não a quantidade.</p>"
    "<p><b>O que ele tem</b> é a coleção inteira (sem contar o que já está "
    "dentro de uma deck box), a mesma conta da posse das outras páginas.</p>"
    "%JANELA%")

# A janela do consenso, se houver (`colecao_config.json → consenso.desde`). Vai
# no rodapé por substituição e não escrita à mão: a data vive no config, e uma
# página que diga uma data diferente da que o motor usou é uma página a mentir.
_RODAPE_JANELA = (
    "<p><b>A janela.</b> Esta página conta <b>só as listas de %DESDE% em "
    "diante</b> — %MOTIVO%. Foi o pedido dele a 3 de outubro de 2026: <i>«faz a "
    "pesquisa de decks só a partir do dia que reality fracture ficou "
    "disponível»</i>. Por isso o número de listas é muito menor do que o do mês "
    "inteiro, e um comandante com menos do que o mínimo aparece com o número de "
    "listas em vez de percentagens. Muda-se em "
    "<code>colecao_config.json → consenso.desde</code>; apagar a data devolve a "
    "janela ao mês inteiro.</p>")
_RODAPE_SEM_JANELA = (
    "<p><b>A janela</b> é a das listas guardadas, que são cerca de um mês.</p>")


def _rodape() -> str:
    """O rodapé com a janela já escrita — a data sai do config, nunca da mão."""
    desde = sources.consenso_desde(consenso.regras()["formato"])
    if not desde:
        return _RODAPE.replace("%JANELA%", _RODAPE_SEM_JANELA)
    motivo = (str(sources.regras_consenso().get("motivo") or "").strip()
              or "ver o colecao_config.json")
    return _RODAPE.replace(
        "%JANELA%", _RODAPE_JANELA.replace("%DESDE%", desde)
                                  .replace("%MOTIVO%", motivo))

_JS = r"""
%JS_DADOS%
let IDX = null;
const vista = () => document.getElementById('vista');
const PAPEIS = [
  ['nucleo', 'Núcleo', 'Em 90 % ou mais das listas — é o deck.'],
  ['flex', 'Flex', 'Entre 40 % e 90 % — escolha, não obrigação.'],
  ['raro', 'Raro', 'Abaixo de 40 % — apareceu em poucas listas.'],
];
function tile(c) {
  const img = c.sid
    ? `<img src="https://cards.scryfall.io/small/front/${c.sid[0]}/${c.sid[1]}/${c.sid}.jpg"`
      + ` alt="${escDados(c.nm)}" loading="lazy" decoding="async" width="146" height="204"`
      + ` onerror="this.remove()">`
    : `<div class="nmo">${escDados(c.nm)}</div>`;
  const posse = c.falta > 0
    ? `<span class="ps falta">falta ${c.falta}</span>`
    : `<span class="ps ok">tens ${c.tenho}</span>`;
  const q = c.copias > 1 ? `${c.copias}× · ` : '';
  // `pct` vem a NULL quando a amostra não chega ao mínimo (consenso.consenso):
  // mostra-se o número de listas, que é um facto, e nunca uma percentagem de
  // uma amostra de duas. Ver `sources.texto_amostra`.
  const temPct = c.pct !== null && c.pct !== undefined;
  const chip = temPct ? `${c.pct} %` : `${c.listas}×`;
  const ond = temPct ? `em ${c.pct} % das listas (${c.listas})`
                     : `em ${c.listas} listas (amostra insuficiente: sem percentagem)`;
  return `<div class="c" title="${escDados(c.nm)} — ${ond}`
    + ` · tens ${c.tenho}"><div style="position:relative">${img}`
    + `<span class="pc">${chip}</span>${posse}</div>`
    + `<div class="lg"><b>${escDados(c.nm)}</b><span>${q}${c.listas} listas</span></div></div>`;
}
function desenha(d) {
  if (!d.listas) {
    return `<div class="aviso">Ainda não há nenhuma lista de <b>${escDados(d.comandante)}</b>`
      + ` nas que estão guardadas. Nada se inventa: volta a ver quando o metagame trouxer listas dele.</div>`;
  }
  const cab = `<div class="cmd">`
    + (d.sid ? `<img src="https://cards.scryfall.io/normal/front/${d.sid[0]}/${d.sid[1]}/${d.sid}.jpg"`
        + ` alt="${escDados(d.comandante)}" loading="lazy" decoding="async" onerror="this.remove()">` : '')
    + `<div><p class="ct">${escDados(d.comandante)}</p><p class="cs">`
    + `<b>${d.listas}</b> listas guardadas${d.janela[0] ? ` · ${escDados(d.janela[0])} a ${escDados(d.janela[1])}` : ''}`
    + `<br>núcleo <b>${d.papeis.nucleo}</b> · flex <b>${d.papeis.flex}</b> · raro <b>${d.papeis.raro}</b>`
    + `<br>tens <b>${d.tenho_cmd}</b> ${d.tenho_cmd === 1 ? 'cópia' : 'cópias'} do comandante`
    + `</p></div></div>`;
  // AMOSTRA INSUFICIENTE: não dá para dizer, e diz-se em letra grande em vez de
  // se darem percentagens de duas listas (ordem dele, 2026-10-03). A frase vem
  // do Python (`sources.texto_amostra`), para ser a mesma em todo o vault.
  const pouco = d.suficiente ? '' :
    `<div class="aviso grande">Não dá para dizer — ${escDados(d.amostra || '')}.`
    + `<span class="pq">As cartas ficam à vista com o <b>número de listas</b> em que`
    + ` apareceram, e sem percentagem: com ${d.listas} listas uma carta aparece a`
    + ` 50 % ou a 100 % sem isso querer dizer nada.</span></div>`;
  let corpo = '';
  if (!d.suficiente) {
    // Sem papéis: núcleo/flex/raro são cortes por percentagem, e sem
    // percentagem fiável não há papel nenhum para atribuir.
    corpo = `<h2>As cartas que apareceram <span class="n">${d.cartas.length} cartas,`
      + ` por nº de listas</span></h2>`
      + `<div class="grid">${d.cartas.map(tile).join('')}</div>`;
    return cab + pouco + corpo;
  }
  for (const [k, rot, nota] of PAPEIS) {
    const cs = d.cartas.filter(c => c.papel === k);
    if (!cs.length) continue;
    corpo += `<h2>${rot} <span class="n">${cs.length} cartas</span></h2>`
      + `<p class="papelsub">${nota}</p>`
      + `<div class="grid">${cs.map(tile).join('')}</div>`;
  }
  return cab + pouco + corpo;
}
async function mostra(nome) {
  const el = vista();
  el.innerHTML = '<p class="carregando">a carregar o consenso…</p>';
  try {
    const d = (IDX.partes && IDX.partes[nome])
      ? IDX.partes[nome]
      : await carregaDados('comandantes/' + IDX.ficheiros[nome] + '.json');
    el.innerHTML = desenha(d);
  } catch (e) { erroDados(el, e); }
}
async function arranca() {
  const sel = document.getElementById('cmd');
  try { IDX = await carregaDados('comandantes.json'); }
  catch (e) { erroDados(vista(), e); return; }
  if (sel) {
    sel.innerHTML = IDX.comandantes.map(c =>
      `<option value="${escDados(c.nome)}">${escDados(c.nome)} — ${c.listas} listas</option>`).join('');
    sel.value = IDX.comandante;
    sel.onchange = () => mostra(sel.value);
  }
  const chips = document.getElementById('chips');
  if (chips) {
    chips.innerHTML =
      `<span class="chip gold"><b>${IDX.comandantes.length}</b> comandantes</span>`
      + `<span class="chip"><b>${IDX.listas}</b> listas que contam</span>`
      + (IDX.janela[0] ? `<span class="chip">${escDados(IDX.janela[0])} a ${escDados(IDX.janela[1])}</span>` : '')
      + (IDX.desde ? `<span class="chip gold">desde <b>${escDados(IDX.desde)}</b></span>` : '')
      + `<span class="chip">comandante lido do sideboard em <b>${IDX.fontes.sideboard}</b>`
      + ` · derivado em <b>${IDX.fontes.ordem}</b></span>`;
  }
  await mostra(IDX.comandante);
}
arranca();
"""


def _tmpl() -> str:
    """O molde é uma FUNÇÃO e não uma constante de módulo (decisão de
    2026-09-25): a barra lateral depende do config, e uma constante ficava com a
    resposta que o config deu a quem importasse o ficheiro primeiro."""
    titulo = shell.titulo_de(PAGINA) or "Consenso por comandante"
    return (
        "<!doctype html><html lang=pt><head>"
        + shell.head(titulo, _CSS + paginas.CSS_DADOS)
        + "</head><body>"
        + shell.abrir(PAGINA, titulo, _LEAD)
        + '<div class="av"><label for="cmd">Comandante</label>'
          '<select id="cmd" aria-label="Escolher o comandante"></select></div>'
          '<div class="chips" id="chips"></div>'
          '<div id="vista"><p class="carregando">a carregar…</p></div>'
        + shell.fechar(_rodape(), scripts="<script>%JS%</script>")
        + "</body></html>")


def _carta(nm, posse, sids, dados) -> dict:
    d = dict(dados)
    tenho = int(posse.get(scryfall.chave(nm), 0))
    d["tenho"] = tenho
    d["falta"] = max(0, int(d.get("copias") or 1) - tenho)
    d["sid"] = sids.get(scryfall.chave(nm))
    return d


def dados(con) -> tuple[dict, dict[str, object]]:
    """`(índice, partes)` — a forma que o `paginas.escrever_dados` leva ao disco.

    Uma parte por comandante. O que ABRE a página vai **também** no índice
    (`partes`), para o primeiro ecrã não precisar de um segundo pedido.
    """
    r = consenso.regras()
    fmt = r["formato"]
    lista = consenso.comandantes(con, fmt)[: int(r["max_comandantes"])]
    nomes = [c["nome"] for c in lista]
    # O que abre é SEMPRE o escolhido dele (`consenso_comandante.comandante`),
    # mesmo sem listas nenhumas — nesse caso a página diz *"ainda não há listas
    # deste"*, que é uma resposta. Abrir no mais jogado em vez dele era responder
    # a outra pergunta sem avisar.
    abre = r["comandante"]
    if abre not in nomes:
        nomes.insert(0, abre)
        lista.insert(0, {"nome": abre, "listas": 0})

    posse = paginas.posse_total(con)
    partes: dict[str, object] = {}
    ficheiros = {}
    for nome in nomes:
        c = consenso.consenso(con, nome, fmt)
        precisa = [x["nm"] for x in c["cartas"]] + [nome]
        sids = paginas.img_map(con, precisa)
        c["cartas"] = [_carta(x["nm"], posse, sids, x) for x in c["cartas"]]
        c["sid"] = sids.get(scryfall.chave(nome))
        c["tenho_cmd"] = int(posse.get(scryfall.chave(nome), 0))
        ficheiros[nome] = paginas.slug(nome)
        partes[paginas.slug(nome)] = c

    idx = {
        "formato": fmt, "comandante": abre, "comandantes": lista,
        "ficheiros": ficheiros,
        "listas": sum(c["listas"] for c in lista),
        "janela": (partes[paginas.slug(abre)]["janela"]
                   if nomes else ["", ""]),
        "fontes": consenso.fontes(con, fmt),
        "min_listas": r["min_listas"],
        # A janela do consenso viaja no payload: a página não a reconstrói nem
        # a escreve à mão (é a lição do `e_foil` e do `precos.sql()`).
        "desde": sources.consenso_desde(fmt),
        "janela_texto": sources.texto_janela_consenso(fmt),
        # Só o que abre vem embutido — as outras vão-se buscar ao toque.
        "partes": {abre: partes[paginas.slug(abre)]},
    }
    return idx, partes


def build(con, out_path=None):
    out = Path(out_path) if out_path else (ROOT / PAGINA)
    idx, partes = dados(con)
    paginas.escrever_dados(out, "comandantes", idx, partes)
    js = _JS.replace("%JS_DADOS%", paginas.JS_DADOS)
    out.write_text(_tmpl().replace("%JS%", js), encoding="utf-8")
    return out


def html_page(con) -> str:
    """A página com os dados EMBUTIDOS. Não é o que se publica — serve para quem
    quiser a página inteira num ficheiro só (a mesma saída do
    `deckboxes.html_page`)."""
    idx, partes = dados(con)
    idx = dict(idx)
    idx["partes"] = {n: partes[paginas.slug(n)] for n in idx["ficheiros"]}
    js = (_JS.replace("%JS_DADOS%", paginas.JS_DADOS)
          .replace("IDX = await carregaDados('comandantes.json')",
                   "IDX = " + json.dumps(idx, ensure_ascii=False)))
    return _tmpl().replace("%JS%", js)


if __name__ == "__main__":
    from mtgvault import db
    with db.session() as con:
        print("comandantes.html:", build(con))
