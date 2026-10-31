"""QUEM ENTRA NO MODO DE EDIÇÃO: o nome, a password e a sessão (2026-10-31).

Até este dia o modo de edição tinha duas fechaduras: o loopback era de
confiança e da rede de casa exigia-se o token (`data/webapp.token`). O túnel da
Cloudflare liga-se ao 8771 PELO LOOPBACK, por isso quem chegava de fora por
`editar-mtg.baverone.com` caía na primeira — e o Cloudflare Access à frente era
a única coisa a fechar a porta. Agora quem vem de fora entra com o nome e a
password do COFRE DE CONTAS partilhado com o riftvault (o pacote `contas`, só
stdlib, que vive FORA deste repositório, em `Desktop/Claude/01-Projetos/contas`).

O que mora AQUI é pouco, de propósito:

  * ONDE está o cofre (`pasta_contas`, `caminho_cofre`) e como se importa;
  * as SESSÕES deste site (`data/sessoes.db`, ao lado da base). O cofre não
    guarda sessões de ninguém: cada site guarda as suas e pergunta ao cofre,
    a cada pedido, se a conta ainda existe, ainda tem acesso ao `mtg` e ainda
    está na mesma «geração» da password;
  * as duas páginas da conta (a caixa de entrada e o «entraste como»).

Nenhuma password passa por aqui a não ser na `entrar`, durante o pedido, e
nenhuma fica guardada. Do `sid` guarda-se só o SHA-256; o CSRF fica em claro
porque tem de se comparar com o que a página manda (é o que o riftvault faz).

O IMPORT DO COFRE É PREGUIÇOSO, e é de propósito: o `daily` e a geração das
páginas importam o `webapp` (e por ele este módulo) e não podem passar a precisar
do cofre para fazer o trabalho deles. O `contas` só entra quando uma entrada ou
uma sessão precisa dele (`modulo()`).
"""
from __future__ import annotations

import contextlib
import hashlib
import html
import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import db

#: O nome do cookie da sessão. Sem `Domain`: vale só para o endereço do modo de
#: edição, e o site publicado (`mtg.baverone.com`) nunca o recebe.
COOKIE = "mtgvault_sessao"
#: O site deste repositório, no cofre (`contas.cofre.SITES`).
SITE = "mtg"
#: Quanto dura uma sessão sem se usar. Desliza: cada uso adia o fim (`sessao`).
SESSAO_DIAS = 30
#: Só se adia a expiração se a última vez foi há mais do que isto. Uma página
#: do modo de edição são dezenas de pedidos (o índice, as partes, as imagens) e
#: escrever na base a cada um só para adiar uma data a 30 dias não vale nada.
TOCAR_CADA_S = 3600

#: A raiz deste repositório (a do `webapp.py`). Não se pede ao `webapp.ROOT`
#: porque os testes o trocam por uma pasta temporária, e o cofre não mora lá.
_RAIZ = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Onde está o cofre
# ---------------------------------------------------------------------------
def pasta_contas() -> Path:
    """A pasta do projecto `contas` (a que tem `contas/__init__.py` dentro).

    `CONTAS_DIR` manda. Sem ela sobe-se pelos antepassados da raiz deste
    repositório e fica o primeiro `A/contas` ou `A/01-Projetos/contas` que seja
    mesmo o pacote: o checkout principal (`01-Projetos/Servidor MTG Coleçao/
    Servidor MTG Coleçao`) e o worktree ao lado dele encontram-no subindo até ao
    `01-Projetos`. É a mesma regra do `riftvault/cofre.py`.
    """
    escrita = os.environ.get("CONTAS_DIR", "").strip()
    if escrita:
        p = Path(escrita)
        if not (p / "contas" / "__init__.py").is_file():
            raise RuntimeError(
                f"o CONTAS_DIR aponta para {p}, mas lá não está o pacote "
                f"`contas` (falta {p / 'contas' / '__init__.py'}).")
        return p
    for antepassado in (_RAIZ, *_RAIZ.parents):
        for candidato in (antepassado / "contas",
                          antepassado / "01-Projetos" / "contas"):
            if (candidato / "contas" / "__init__.py").is_file():
                return candidato
    raise RuntimeError(
        "não encontrei o cofre de contas (o pacote `contas`) a subir a partir "
        f"de {_RAIZ}: define CONTAS_DIR com a pasta dele.")


def caminho_cofre() -> Path:
    """A base do cofre: `CONTAS_DB`, senão `<pasta do contas>/data/contas.db`.

    **Nunca se tira do `MTGVAULT_DB`/`MTGVAULT_HOME`**: o cofre não é uma base
    do mtgvault, é a de toda a gente (o riftvault lê a mesma). Um teste que se
    esqueça do `CONTAS_DB` cai no cofre a sério — e é por isso que a bateria o
    põe numa pasta temporária para todos os filhos.
    """
    escrito = os.environ.get("CONTAS_DB", "").strip()
    if escrito:
        return Path(escrito)
    return pasta_contas() / "data" / "contas.db"


def modulo():
    """O `contas.cofre`, importado à primeira chamada.

    A pasta entra no FIM do `sys.path` (não tapa nada deste repositório) e
    confirma-se que o `contas` que entrou é o dessa pasta: com ela no fim, um
    outro `contas` mais à frente ganhava em silêncio — e um cofre trocado é o
    pior sítio para uma surpresa.
    """
    pasta = pasta_contas()
    if str(pasta) not in sys.path:
        sys.path.append(str(pasta))
    import contas                                           # noqa: PLC0415
    import contas.cofre                                     # noqa: PLC0415
    origem = Path(contas.__file__).resolve().parent.parent
    if origem != pasta.resolve():
        raise RuntimeError(
            f"o pacote `contas` importado vem de {origem}, não de {pasta}. "
            "Define CONTAS_DIR, ou tira o outro do caminho.")
    return contas.cofre


@contextlib.contextmanager
def _no_cofre():
    """(o `contas.cofre`, uma ligação ao cofre), fechada à saída."""
    m = modulo()
    con = m.abrir(caminho_cofre())
    try:
        yield m, con
    finally:
        con.close()


def linha_de_arranque() -> str:
    """Uma linha para o arranque do `webapp`: que cofre, e quantas contas entram.

    Diz QUANTAS contas têm acesso ao `mtg`, nunca quais: o nome de cada um não
    tem nada que fazer num log. **Não cria o cofre** (o `abrir` do `contas`
    criava): um cofre que falta é um aviso a ler — ninguém entra pelo túnel —,
    não uma base vazia a nascer em silêncio no sítio errado. Abre-se só para
    ler.
    """
    try:
        p = caminho_cofre()
    except RuntimeError as e:
        return f"  Cofre de contas: não o encontrei ({e})."
    if not p.is_file():
        return (f"  Cofre de contas: {p} NÃO EXISTE — ninguém entra pelo túnel "
                "até ele existir (não o criei agora).")
    try:
        con = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
        try:
            n = con.execute(
                "SELECT COUNT(DISTINCT a.conta_id) FROM acessos a "
                "JOIN contas c ON c.id = a.conta_id WHERE a.site = ?",
                (SITE,)).fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error as e:
        return f"  Cofre de contas: {p} (não o consegui ler: {e})."
    contas = "1 conta" if n == 1 else f"{n} contas"
    return f"  Cofre de contas: {p} · {contas} com acesso ao {SITE}."


def mensagem_temporaria() -> str:
    """A resposta a quem entra com uma temporária (ver `webapp._conta_entrar`):
    a caixa mostra-a e pede a password nova."""
    return ("essa password é temporária e só serve para escolheres a tua. "
            "Escreve a password nova duas vezes e carrega em «Gravar e entrar».")


def entrar(nome: str, password: str, chave: str | None) -> dict:
    """O nome e a password -> a conta (`conta_id`, `slug`, `nome`, `temporaria`,
    `geracao`). Decide-o o cofre, com `site="mtg"`.

    Levanta os erros do cofre tal como vêm (`TemDeEsperar`, `ServidorOcupado`,
    `SenhaErrada`…): quem responde ao pedido é que os traduz em 429/503/401. Uma
    conta sem acesso ao `mtg` falha EXACTAMENTE como uma password errada — é o
    cofre que o garante, para a caixa de entrada não dizer que nomes existem.
    """
    with _no_cofre() as (m, con):
        return m.entrar(con, str(nome or ""), str(password or ""), site=SITE,
                        chave=chave)


def trocar_temporaria(nome: str, temporaria: str, nova: str,
                      chave: str | None) -> dict:
    """O nome, a temporária e a password nova -> a conta, já com a nova.

    É o cofre que decide tudo (`trocar_temporaria`, com `site="mtg"`): o
    travão, o acesso, o prazo de 24 horas e as regras da password nova. A
    sessão só nasce depois, da password nova — nunca da temporária.
    """
    with _no_cofre() as (m, con):
        return m.trocar_temporaria(con, str(nome or ""), str(temporaria or ""),
                                   str(nova or ""), site=SITE, chave=chave)


# ---------------------------------------------------------------------------
# As sessões deste site
# ---------------------------------------------------------------------------
#: A `geracao` é a da password no cofre NO MOMENTO em que se entrou — a que o
#: `entrar` leu junto com o hash que verificou. O `slug` vai com o `conta_id`
#: porque apagar uma conta e criar outra com o mesmo número põe a geração a
#: zero outra vez: sem o slug, a sessão da conta apagada valia para a nova.
_ESQUEMA = """
CREATE TABLE IF NOT EXISTS sessoes (
    sid_hash  TEXT PRIMARY KEY,
    conta_id  INTEGER NOT NULL,
    slug      TEXT NOT NULL,
    geracao   INTEGER NOT NULL,
    csrf      TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    visto_em  TEXT NOT NULL,
    expira_em TEXT NOT NULL,
    agente    TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessoes_expira ON sessoes(expira_em);
"""


def caminho_sessoes() -> Path:
    """`data/sessoes.db`, ao lado da base e do token — fora do Git (ver o
    `.gitignore`): é o rasto de quem entrou, e leva o CSRF de cada sessão."""
    return Path(db.ROOT) / "sessoes.db"


def _abrir() -> sqlite3.Connection:
    destino = caminho_sessoes()
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(destino), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 10000")
    con.executescript(_ESQUEMA)
    return con


@contextlib.contextmanager
def _sessoes():
    con = _abrir()
    try:
        yield con
    finally:
        con.close()


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _instante(texto: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat(texto or "")
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _hash(valor: str) -> str:
    return hashlib.sha256(str(valor).encode("utf-8")).hexdigest()


def criar_sessao(conta: dict, agente: str | None) -> dict:
    """Uma sessão nova para a conta que o `entrar` devolveu. Devolve `sid` e
    `csrf` EM CLARO — é a única vez que o `sid` existe; na base fica o SHA-256.

    A `geracao` é a que vem na `conta` (a lida com o hash verificado), nunca uma
    lida agora: uma reposição da password a meio da entrada dava a quem entrou
    com a password velha a geração nova, e a sessão sobrevivia à reposição feita
    para a matar.
    """
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    agora = _agora()
    with _sessoes() as con:
        # Uma entrada é rara e é quando a tabela cresce: varre-se aqui o que já
        # passou do prazo e ninguém voltou a tocar (o telemóvel trocado, o
        # portátil do trabalho), senão ficava lá para sempre.
        con.execute("DELETE FROM sessoes WHERE expira_em < ?", (_iso(agora),))
        con.execute(
            "INSERT INTO sessoes (sid_hash, conta_id, slug, geracao, csrf, "
            "criado_em, visto_em, expira_em, agente) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_hash(sid), int(conta["conta_id"]), str(conta["slug"]),
             int(conta["geracao"]), csrf, _iso(agora), _iso(agora),
             _iso(agora + timedelta(days=SESSAO_DIAS)), (agente or "")[:200]))
        con.commit()
    return {"sid": sid, "csrf": csrf}


def sessao(sid: str | None) -> dict | None:
    """A sessão daquele cookie, ou `None`. Mede-se a CADA pedido:

      * expirada -> apaga-se;
      * a conta já não existe no cofre, ou existe com outro slug -> apaga-se;
      * a conta já não tem acesso ao `mtg` -> apaga-se;
      * a geração do cofre já não é a da sessão (a password mudou — aqui, no
        riftvault, ou reposta pelo André) -> apaga-se.

    É isto que dá sentido a «mudei a password porque ma viram» e a «tirei o
    acesso ao Rui»: as sessões vão-se no pedido seguinte, sem esperar 30 dias.

    Viva, adia o fim (no máximo uma escrita por hora, ver `TOCAR_CADA_S`) e
    devolve `{conta_id, slug, nome, csrf, expira_em, tocada}` — o `tocada` diz
    se o prazo andou, para quem responde renovar o cookie.
    """
    if not sid:
        return None
    with _sessoes() as con:
        row = con.execute("SELECT * FROM sessoes WHERE sid_hash = ?",
                          (_hash(sid),)).fetchone()
        if row is None:
            return None
        agora = _agora()
        fim = _instante(row["expira_em"])
        viva = fim is not None and fim > agora
        quem = None
        if viva:
            with _no_cofre() as (m, cc):
                quem = m.por_id(cc, int(row["conta_id"]))
                viva = (quem is not None
                        and quem["slug"] == row["slug"]
                        and m.tem_acesso(cc, int(row["conta_id"]), SITE)
                        and m.geracao(cc, int(row["conta_id"])) == int(row["geracao"]))
        if not viva:
            con.execute("DELETE FROM sessoes WHERE sid_hash = ?", (row["sid_hash"],))
            con.commit()
            return None
        expira = row["expira_em"]
        visto = _instante(row["visto_em"])
        tocada = visto is None or (agora - visto).total_seconds() >= TOCAR_CADA_S
        if tocada:
            expira = _iso(agora + timedelta(days=SESSAO_DIAS))
            con.execute("UPDATE sessoes SET visto_em = ?, expira_em = ? "
                        "WHERE sid_hash = ?", (_iso(agora), expira, row["sid_hash"]))
            con.commit()
    return {"conta_id": int(row["conta_id"]), "slug": row["slug"],
            "nome": quem.get("nome") or row["slug"], "csrf": row["csrf"],
            "expira_em": expira, "tocada": tocada}


def terminar(sid: str | None) -> None:
    """Sai: a linha da sessão vai-se. Um `sid` que não existe não é erro."""
    if not sid:
        return
    with _sessoes() as con:
        con.execute("DELETE FROM sessoes WHERE sid_hash = ?", (_hash(sid),))
        con.commit()


# ---------------------------------------------------------------------------
# As páginas da conta
# ---------------------------------------------------------------------------
# AUTÓNOMAS, SEM A CASCA DO SITE, e é de propósito: a caixa de entrada é o que
# quem vem de fora vê em TODOS os caminhos (incluindo o `.css` e o `.js` que a
# casca pediria), por isso não pode depender de nada do servidor — tudo inline,
# nenhum script de fora. E pensadas para o telemóvel, que é onde ele as abre.
_CSS = """
:root{--fundo:#f4f1ea;--caixa:#fff;--tinta:#1f1d1a;--fraco:#6b665d;--linha:#d9d3c7;
--marca:#2f5d50;--marca2:#24493f;--erro:#a3302a;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--fundo:#16181a;--caixa:#202326;
--tinta:#ece8e1;--fraco:#a29d94;--linha:#3a3e42;--marca:#5fa58f;--marca2:#4c8b77;
--erro:#e0756d}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:var(--fundo);color:var(--tinta);padding:16px;
font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{width:100%;max-width:360px;background:var(--caixa);border:1px solid var(--linha);
border-radius:14px;padding:24px 20px}
h1{font-size:20px;margin:0 0 4px}
p{margin:0 0 16px;color:var(--fraco);font-size:14px}
label{display:block;font-size:14px;margin:12px 0 4px}
input{width:100%;font:inherit;padding:11px 12px;border:1px solid var(--linha);
border-radius:9px;background:transparent;color:inherit}
input:focus{outline:2px solid var(--marca);outline-offset:1px}
button{width:100%;margin-top:18px;font:inherit;font-weight:600;padding:12px;border:0;
border-radius:9px;background:var(--marca);color:#fff;cursor:pointer}
button:hover{background:var(--marca2)} button:disabled{opacity:.6;cursor:wait}
.erro{color:var(--erro);font-size:14px;margin:12px 0 0;min-height:1.2em}
a{color:var(--marca)}
"""


def volta_segura(volta: str | None) -> str:
    """Para onde se volta depois de entrar: SÓ um caminho deste site.

    Começa por `/` e não por `//` (que o browser lê como outro servidor), e
    sem `\\` nem caracteres de controlo (o browser troca `/\\` por `//`). O
    resto vira `/` — uma caixa de entrada que mandasse para onde o URL dissesse
    era um redireccionamento aberto com o nome do site dele por cima.
    """
    v = str(volta or "")
    if (not v.startswith("/") or v.startswith("//") or "\\" in v
            or any(ord(c) < 32 or ord(c) == 127 for c in v)):
        return "/"
    return v


def _js(valor) -> str:
    """Um valor para dentro de um `<script>`: JSON, sem `<` (um `</script>` no
    texto fechava o bloco) nem os separadores de linha que o JavaScript recusa."""
    return (json.dumps(valor, ensure_ascii=False).replace("<", "\\u003c")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _pagina(titulo: str, corpo: str, script: str) -> str:
    return ('<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex">'
            f'<title>{html.escape(titulo)}</title><style>{_CSS}</style></head>'
            f'<body><main>{corpo}</main><script>{script}</script></body></html>')


def pagina_entrar(volta: str, erro: str = "") -> str:
    """A CAIXA DE ENTRADA: utilizador, password e «Entrar».

    Manda JSON por `fetch` para `/api/conta/entrar` (o servidor só aceita
    `application/json`: é o que impede outro site de fazer entrar o browser
    dele na conta de um estranho com um formulário escondido) e, em caso de
    sucesso, volta a `volta` — que só pode ser um caminho deste site.

    **A TEMPORÁRIA** (2026-10-31): se o servidor responder `trocar`, a mesma
    caixa mostra «Password nova» e «Repete a password nova», e o segundo envio
    leva o nome, a temporária e a nova. A confirmação das duas é só aqui no
    browser; as regras da password são do cofre.
    """
    destino = volta_segura(volta)
    corpo = ('<h1>mtgvault · modo de edição</h1>'
             '<p id="dica">Entra com o teu nome e a tua password.</p>'
             '<form id="entrar" autocomplete="on" novalidate>'
             '<label for="nome">Utilizador</label>'
             '<input id="nome" name="username" autocomplete="username" '
             'autocapitalize="none" autocorrect="off" spellcheck="false" required>'
             '<label for="senha">Password</label>'
             '<input id="senha" name="password" type="password" '
             'autocomplete="current-password" required>'
             '<div id="passo-nova" hidden>'
             '<label for="nova">Password nova</label>'
             '<input id="nova" name="new-password" type="password" '
             'autocomplete="new-password">'
             '<label for="repete">Repete a password nova</label>'
             '<input id="repete" name="new-password-2" type="password" '
             'autocomplete="new-password">'
             '</div>'
             '<button type="submit">Entrar</button>'
             f'<p class="erro" id="erro" role="alert">{html.escape(erro)}</p>'
             '</form>')
    script = f"""
const VOLTA = {_js(destino)};
const f = document.getElementById('entrar'), e = document.getElementById('erro');
const passo = document.getElementById('passo-nova'), dica = document.getElementById('dica');
let trocar = false;
function pedirNova(msg) {{
  trocar = true;
  passo.hidden = false;
  f.nome.readOnly = true; f.senha.readOnly = true;
  f.querySelector('button').textContent = 'Gravar e entrar';
  dica.textContent = msg;
  f.nova.focus();
}}
f.addEventListener('submit', async (ev) => {{
  ev.preventDefault();
  const b = f.querySelector('button');
  e.textContent = '';
  const corpo = {{nome: f.nome.value.trim(), senha: f.senha.value}};
  if (trocar) {{
    if (!f.nova.value) {{ e.textContent = 'escreve a password nova.'; return; }}
    if (f.nova.value !== f.repete.value) {{
      e.textContent = 'as duas passwords novas não são iguais.'; return; }}
    corpo.nova = f.nova.value;
  }}
  b.disabled = true;
  try {{
    const r = await fetch('/api/conta/entrar', {{
      method: 'POST', credentials: 'same-origin',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(corpo)}});
    let j = {{}};
    try {{ j = await r.json(); }} catch (_) {{}}
    if (r.ok && j.ok) {{ location.replace(VOLTA); return; }}
    if (j.trocar && !trocar) {{ pedirNova(j.erro); b.disabled = false; return; }}
    e.textContent = j.erro || ('não consegui entrar (erro ' + r.status + ').');
  }} catch (_) {{
    e.textContent = 'não consegui falar com o servidor. Tenta outra vez.';
  }}
  b.disabled = false;
}});
"""
    return _pagina("Entrar · mtgvault", corpo, script)


def pagina_conta(conta: dict, csrf: str) -> str:
    """«Entraste como X» e o botão «Sair».

    O «Sair» é um POST com o CSRF no `X-Mtgvault-Token`, como toda a escrita
    deste site: um link que terminasse a sessão por GET deixava qualquer página
    de fora pôr alguém na rua com uma `<img>`.
    """
    nome = conta.get("nome") or conta.get("slug") or "?"
    corpo = ('<h1>A tua conta</h1>'
             f'<p>Entraste como <b>{html.escape(str(nome))}</b>.</p>'
             '<p><a href="/">Voltar ao modo de edição</a></p>'
             '<button id="sair" type="button">Sair</button>'
             '<p class="erro" id="erro" role="alert"></p>')
    script = f"""
const CSRF = {_js(csrf)};
const b = document.getElementById('sair'), e = document.getElementById('erro');
b.addEventListener('click', async () => {{
  b.disabled = true; e.textContent = '';
  try {{
    const r = await fetch('/api/conta/sair', {{
      method: 'POST', credentials: 'same-origin',
      headers: {{'Content-Type': 'application/json', 'X-Mtgvault-Token': CSRF}},
      body: '{{}}'}});
    if (r.ok) {{ location.replace('/'); return; }}
    let j = {{}};
    try {{ j = await r.json(); }} catch (_) {{}}
    e.textContent = j.erro || ('não consegui sair (erro ' + r.status + ').');
  }} catch (_) {{
    e.textContent = 'não consegui falar com o servidor. Tenta outra vez.';
  }}
  b.disabled = false;
}});
"""
    return _pagina("A tua conta · mtgvault", corpo, script)
