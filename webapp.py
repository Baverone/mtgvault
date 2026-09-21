"""MODO EDIÇÃO do mtgvault: servidor local que serve as páginas e ESCREVE.

    python webapp.py        →  http://localhost:8771/

**Porto 8771, não 8770** — o 8770 é do riftvault (`riftvault serve`). Os dois
correm no mesmo PC e ficariam a disputar o porto; quem perdesse morria no
arranque com um "address already in use" e não voltava a subir. Se mudares um,
muda a tarefa `ai-pc/tasks/mtgvault-serve/` também.

O que faz de diferente do site publicado
----------------------------------------
Serve a **mesma** página `deckboxes.html` — o mesmo ficheiro, o mesmo JavaScript,
os mesmos números — com um flag `editable: true` no payload. É esse flag que faz
aparecer os botões:

  * **Tornar permanente / Deixar de ser permanente** — *"os decks que eu estiver
    quase a concluir, tenho que ter uma opção que os marque como permanentes
    para começarem a receber alocação de cartas"* (André, 2026-09-07);
  * **Subir / Descer** — a prioridade DENTRO do grupo de formato;
  * **Sleevado e na caixa / Tirar da caixa** — regista que as cartas daquela
    caixa estão fisicamente lá dentro;
  * **Já arrumei tudo** (na aba Arrumar) — grava a alocação inteira.

Duas páginas diferentes divergem em silêncio: é a razão de o frontend ser um só
(a lição do riftvault, que serve o mesmo `app.js` nos dois modos).

Onde fica a verdade
-------------------
**No `colecao_config.json`.** Os botões escrevem lá — não numa tabela
`deck_meta` paralela. Razões, por ordem de peso:

  1. o `loadout` já vive lá e é ele que manda em toda a alocação. Uma segunda
     fonte para a mesma coisa é exactamente o padrão do `event_tier`: duas
     opiniões, nenhum erro, páginas erradas em silêncio;
  2. o config vai no Git, por isso "tornei o Legacy permanente" fica no
     histórico e viaja para o GitHub Actions. A `vault.db` não vai no Git (vive
     num Release) e uma escolha dele podia perder-se na próxima publicação;
  3. dá para editar à mão quando o servidor não está a correr, que é como
     sempre se fez.

O que vai para a base de dados é só o que é **físico**: a `copy_allocation` (que
cartas estão dentro de que caixa) e as cópias que ele vende (o botão *"vendida"*
tira-as da `copies` e escreve-as no `data/vendas.csv`). Isso não é uma
preferência, é o estado da estante — e não cabe num ficheiro de configuração.

NO TELEMÓVEL, EM CASA (André, 2026-09-08)
-----------------------------------------
*"Ele vai estar à frente da estante com o telemóvel."* Por isso o servidor pode
ouvir na rede local — `MTGVAULT_BIND=0.0.0.0` — e a página de arranque mostra um
**QR** com o link já com o token. A predefinição continua a ser `127.0.0.1`:
abrir um porto que escreve na base é uma decisão, não um efeito secundário de
actualizar o vault.

O **token** (`data/webapp.token`, fora do Git, gerado uma vez) é o que separa as
duas coisas:

  * **ler** funciona sempre — a página é a mesma do site publicado, sem botões;
  * **escrever** exige o token. Sem ele, `403`. O token viaja no link do QR
    (`?t=...`) e a página só o guarda dentro de si quando o pedido que a foi
    buscar já o trazia — senão bastava abri-la para o descobrir.

Os pedidos de `127.0.0.1` são de confiança sem token: quem está no PC já tem os
ficheiros à frente, e pedir-lhe uma senha não protege nada. Continua a não ser
para abrir no router.
"""
from __future__ import annotations

import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time as _time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MTGVAULT_HOME", str(ROOT / "data"))

from mtgvault import (caixas, configio, db, encomendas, feira, fotocaixa,  # noqa: E402
                      fotosite, loadout, migracao, qr, sources, venda)
from mtgvault import padrao as padrao_mod  # noqa: E402

import deckboxes  # noqa: E402
import metagame  # noqa: E402

PORT = 8771          # o 8770 é do riftvault — ver o cabeçalho
# Onde ouvir. `127.0.0.1` por omissão: só este PC. `0.0.0.0` para o telemóvel
# chegar lá (é o que a tarefa `ai-pc/tasks/mtgvault-serve` define).
BIND = os.environ.get("MTGVAULT_BIND") or "127.0.0.1"
# Serializa TODAS as escritas (config + base de dados). Ver `do_POST`.
ESCRITA = threading.Lock()
CABECALHO_TOKEN = "X-Mtgvault-Token"
# O *anular* do registo automático (André, 2026-09-08). A fotografia da
# `copy_allocation` de ANTES de cada registo, por caixa — é ela que o botão
# repõe. Fica em memória de propósito: um anular é o desfazer de um gesto que
# acabou de acontecer, não um histórico. Se o servidor for reiniciado no meio,
# perde-se — e aí o que há é o *Desmontar*, que é o gesto grande, com backup.
_ULTIMO_REGISTO: dict[str, dict] = {}
# O *anular* do «já a tenho» (André, 2026-09-08). `copy_id -> quando`: é a única
# janela em que a cópia que ele acabou de declarar ainda se pode apagar. Passada
# ela, é uma cópia como as outras — e o que a tira é o «vendida». Em memória
# pela mesma razão do registo: um anular é o desfazer de um gesto que acabou de
# acontecer, não um histórico.
_ULTIMA_FALTA: dict[int, float] = {}
# Quanto tempo o servidor ainda aceita o *anular*. É maior do que os segundos em
# que o botão está à vista (`loadout.montar_anular_segundos`): um clique ao
# segundo 5,9 num telemóvel na rede de casa não pode falhar por causa da latência.
ANULAR_JANELA = 120.0
# As fotos das cópias NÃO ENCONTRADAS (2026-09-09). São as extensões que o
# `collection.IMG_EXT` aceita; o `.heic` do iPhone vai com o tipo dele — o
# browser pode não o saber desenhar, e nesse caso é melhor um ícone partido do
# que um JPEG que não é JPEG.
TIPOS_FOTO = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif"}


def config_path() -> Path:
    return configio.caminho()


CONFIG = config_path()
UMA_LINHA = configio.UMA_LINHA
# As páginas que o modo edição GERA em vez de servir do disco: são as que têm
# botões, e o `editable` é o que os faz aparecer. Servir o ficheiro estático a
# partir daqui dava uma página sem botões e sem explicação nenhuma.
# O `/index.html` NÃO está aqui de propósito (2026-09-09): estava, e apontava
# para o `deckboxes` — a aba **🏠 Início** do menu levava-o à página onde ele já
# estava. O índice é escrito à mão e serve-se do disco, como todas as outras.
# O `/` fica: é a porta de entrada do modo edição, e a Deckboxes é a página dos
# decks.
PAGINAS_EDITAVEIS = {"/": deckboxes,
                     "/deckboxes.html": deckboxes, "/metagame.html": metagame}

# Os links do menu que o modo edição tem de reescrever para levarem o token.
_LINK_HTML = re.compile(r'href="([a-z_]+\.html)"')
# Os dados da Deckboxes: o índice e as partes (ver `deckboxes.partir`).
_DADOS_DECKBOXES = re.compile(r"^/data/paginas/deckboxes(?:/([A-Za-z0-9_-]+))?\.json$")
# A versão reduzida da foto de cada deckbox (2026-09-21, `mtgvault.fotocaixa`).
_FOTO_CAIXA = re.compile(r"^/assets/deckboxes/([A-Za-z0-9_-]+)\.jpg$")


def com_token(corpo: str, tok: str) -> str:
    """Põe o `?t=` nos links internos de uma página servida em modo edição.

    Sem isto, no telemóvel, **um toque no menu apagava o modo edição**: os links
    do `paginas.nav` são `href="metagame.html"` sem query nenhuma, e o servidor
    só confia em quem traz o token. Ele ia à Coleção, voltava à Deckboxes e os
    botões tinham desaparecido — sem erro nenhum e sem uma linha a dizer porquê.
    (No PC não se notava: o loopback é de confiança sem token, e por isso isto
    ficou meses assim.)

    Reescreve-se no servidor, e não no `paginas.nav`, porque metade destas
    páginas é ESTÁTICA — vem do disco, escrita pela corrida do `daily` que não
    sabe nada de tokens. Num sítio só, e vale para as geradas e para as outras.
    """
    if not tok:
        return corpo
    return _LINK_HTML.sub(lambda m: f'href="{m.group(1)}?t={tok}"', corpo)


# ---------------------------------------------------------------------------
# Config: ler, mexer, gravar sem estragar a formatação (ver `mtgvault.configio`)
# ---------------------------------------------------------------------------
def ler_config(path: Path | None = None) -> dict:
    """O config, sempre já no formato **v6** (`caixas`).

    Migra em memória quando encontra um ficheiro da v5, para o primeiro clique
    dele não rebentar num config que ninguém converteu — e, como toda a escrita
    passa por aqui, esse clique também deixa o ficheiro no formato novo. É o que
    faz o *"o webapp escreve só no formato novo"* ser verdade sem exigir que a
    migração corra primeiro.
    """
    return caixas.migrar_config(configio.ler(path))[0]


def escrever_config(cfg: dict, path: Path | None = None) -> None:
    """Grava o config e **esquece a cache** de quem o lê.

    O `sources.config()` guarda o ficheiro em cache pelo mtime, e o Windows dá
    mtimes com pouca resolução: gravar e voltar a ler no mesmo instante podia
    devolver a versão de antes do clique. Aqui, a seguir a cada escrita, corre
    logo a alocação — e ela tem de ver o que ele acabou de mudar.
    """
    configio.escrever(cfg, path)
    sources._CFG_CACHE.clear()


def gravar_vista(dados: dict, path: Path | None = None) -> dict:
    """«Imagens / Lista» (André, 2026-09-20): `colecao_config.json →
    deckboxes.vista`. Um valor fora de `deckboxes.VISTAS` é 409 — a página só
    manda estes dois, e um terceiro seria um erro dela."""
    v = str(dados.get("vista") or "").strip().lower()
    if v not in deckboxes.VISTAS:
        raise ValueError(f"vista {v!r} — usa imagens ou lista")
    cfg = ler_config(path)
    bloco = cfg.get("deckboxes")
    if not isinstance(bloco, dict):
        bloco = cfg["deckboxes"] = {}
    bloco["vista"] = v
    escrever_config(cfg, path)
    _CACHE.clear()
    return {"ok": True, "vista": v,
            "msg": "a mostrar as cartas em imagem" if v == "imagens"
                   else "a mostrar as cartas em lista"}


# ---------------------------------------------------------------------------
# Token: quem pode escrever
# ---------------------------------------------------------------------------
def ficheiro_token() -> Path:
    """`data/webapp.token` — ao lado da base, e não no repositório: é um segredo
    desta máquina e não uma preferência que viaje no Git."""
    return Path(db.ROOT) / "webapp.token"


def token(criar: bool = True) -> str:
    """O token deste PC. Gera-se uma vez e fica — muda-se apagando o ficheiro."""
    p = ficheiro_token()
    if p.exists():
        t = p.read_text(encoding="utf-8").strip()
        if t:
            return t
    if not criar:
        return ""
    t = secrets.token_hex(16)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(t + "\n", encoding="utf-8")
    return t


def token_valido(dado: str | None) -> bool:
    esperado = token(criar=False)
    return bool(dado) and bool(esperado) and secrets.compare_digest(dado, esperado)


def _peers(con, cfg, slot_id):
    """Os slots que o `prioridade` deste ordena — os do mesmo grupo, com o mesmo
    estado de permanente e de vigiado, pela ordem real da alocação.

    Fora deste conjunto o `prioridade` não decide nada: quem manda é o grupo de
    formato, o "permanente" e o "é deck vigiado", por essa ordem. Subir um slot
    de Premodern acima de um permanente de cEDH não é um número — é mudar o
    `regras_por_formato`, e o botão diz isso em vez de fingir que fez algo.
    """
    resolvidos = loadout.resolve_slots(con, caixas.do_config(cfg))
    alvo = next((s for s in resolvidos if s["slot"] == slot_id), None)
    if alvo is None:
        return None, []
    chave = (alvo["permanente"], alvo["grupo_ordem"], alvo["vigiado"])
    return alvo, [s for s in resolvidos
                  if (s["permanente"], s["grupo_ordem"], s["vigiado"]) == chave]


def mover(con, cfg, slot_id, delta) -> str:
    """Sobe (-1) ou desce (+1) um slot dentro do grupo. Devolve uma frase.

    Num grupo de PRIORIDADE AUTOMÁTICA não mexe (André, 2026-09-08: *"para já a
    prioridade vem por ordem de % completo"*). Escrever o número na mesma era o
    pior dos dois mundos: o config mudava, a ordem não, e o botão respondia "X
    subiu" a uma caixa que ficou onde estava.
    """
    alvo, pares = _peers(con, cfg, slot_id)
    if alvo is None:
        return "esse slot não existe"
    if alvo.get("prioridade_por") == "pct":
        return (f"{alvo['nome']} está num grupo de ordem automática "
                f"({alvo['grupo']}): a prioridade vem da percentagem que cada "
                f"caixa já tem — é #{alvo.get('posicao_grupo')} com "
                f"{alvo.get('pct_coleccao')}%. Para ordenares à mão, tira o "
                f"`prioridade_por` desse grupo no colecao_config.json")
    if len(pares) < 2:
        return f"{alvo['nome']} é o único do grupo — não há por onde mexer"
    i = [s["slot"] for s in pares].index(slot_id)
    j = i + delta
    if not 0 <= j < len(pares):
        return (f"{alvo['nome']} já é o {'primeiro' if delta < 0 else 'último'} "
                f"do grupo {alvo['grupo']}")
    ordem = [s["slot"] for s in pares]
    ordem[i], ordem[j] = ordem[j], ordem[i]
    # Renumera o grupo de 1 a n: com números repetidos ou saltados no config, um
    # swap simples não mexia em nada. É a mesma armadilha dos catorze números à
    # mão que a ordem por grupo veio resolver.
    posicao = {s: n for n, s in enumerate(ordem, 1)}
    for s in cfg["caixas"]:
        if s["slot"] in posicao:
            s["prioridade"] = posicao[s["slot"]]
    return f"{alvo['nome']} {'subiu' if delta < 0 else 'desceu'} no grupo {alvo['grupo']}"


# ---------------------------------------------------------------------------
# "Vou montar este": escolher o deck de uma caixa a partir do top-N
# ---------------------------------------------------------------------------
# As chaves da caixa que a escolha mexe — e por isso as que o `desmarcar` repõe.
# As chaves que uma escolha substitui e o desfazer repõe. Vivem no
# `mtgvault.padrao` desde 2026-09-20, porque a LISTA PADRÃO faz o mesmo gesto
# (fixar/voltar) e as duas listas não podem divergir.
CHAVES_DA_ESCOLHA = padrao_mod.CHAVES_DA_ESCOLHA

_slot_do_cfg = caixas.caixa_do_cfg


def _cartas_do_arquetipo(con, aid: int) -> set:
    """As cartas da lista de consenso — a mesma que o `guardar_escolha` congela."""
    from mtgvault import stock                           # noqa: PLC0415

    sl = stock.stock_list(con, aid)
    return {c["card_name"] for b in ("main", "side") for c in sl.get(b, [])}


def identidade_do_arquetipo(con, aid: int, fmt: str) -> str:
    """O `id` estável de um arquétipo qualquer, e regista-o.

    O ranking de Premodern já traz o `id` feito; as secções de top-N (Standard,
    Pioneer, Legacy) não passam pelo `mtgvault.premodern`, e sem isto a escolha
    dele ficava guardada só com o `archetype_id` do clustering — que muda na
    corrida seguinte.
    """
    import meta_coverage as mc                          # noqa: PLC0415

    from mtgvault import arquetipos                     # noqa: PLC0415

    df, tcache = mc._format_df(con, fmt), {}
    # A lista do arquétipo entra como `resto`, pela mesma razão do `premodern`:
    # a distintividade dá às vezes duas ou três cartas, e duas cartas não são uma
    # identidade.
    nuc = arquetipos.nucleo(mc._distinctivas(con, aid, df, tcache),
                            resto=sorted(_cartas_do_arquetipo(con, aid)))
    if not nuc:
        return ""
    reg = arquetipos.Registo.carregar()
    r = reg.resolver(fmt, nuc, mc._name_for(con, aid, df, tcache))
    reg.gravar()
    return r["id"]


def guardar_escolha(con, cfg, slot_id: str, aid: int,
                    nome: str | None = None, ident: str | None = None) -> str:
    """Congela em `listas_escolhidas[slot]` a lista de consenso de um arquétipo.

    A lista fica **congelada com a data**: se o consenso do arquétipo mudar
    amanhã, a caixa que ele mandou montar não muda debaixo dos pés, nem a lista
    de compras dela. Devolve o nome legível, ou `""` quando o arquétipo não tem
    lista nenhuma para fixar.

    `nome` permite ao chamador impor o nome que ELE já mostrou na página. É o
    caso do ranking de Premodern, onde o nome sai da regra de combo: o
    `_name_for` chama *"Replenish"* tanto à Enchantress como ao UW Replenish, e
    guardar aqui um nome diferente do que está no botão fazia a caixa deixar de
    se reconhecer como sendo aquela sugestão.

    `ident` é o `id` ESTÁVEL do arquétipo (`mtgvault.arquetipos`) e é a chave a
    sério: o `archetype_id` que fica ao lado é o do clustering e muda quando o
    `rebuild_archetypes` corre, e o `nome` pode mudar de rótulo entre corridas.
    Sem ele, a caixa deixava de se reconhecer como sendo aquela sugestão e a
    sugestão reaparecia ao lado da caixa que ela própria criou.
    """
    import meta_coverage as mc

    from mtgvault import stock

    sl = stock.stock_list(con, aid)
    cards = [[b, c["card_name"], c["quantity"]]
             for b in ("main", "side") for c in sl.get(b, [])]
    if not cards:
        return ""
    fmt = con.execute("SELECT format FROM archetypes WHERE id = ?",
                      (aid,)).fetchone()["format"]
    df, tcache = mc._format_df(con, fmt), {}
    cfg.setdefault("listas_escolhidas", {})[slot_id] = {
        "nome": nome or mc._name_for(con, aid, df, tcache),
        "subtitulo": mc._distinctive_name(con, aid, df, tcache),
        "formato": fmt,
        "id": ident or identidade_do_arquetipo(con, aid, fmt),
        "archetype_id": aid,
        "n_listas": mc._n_lists(con, aid),
        "escolhido_em": date.today().isoformat(),
        "cards": cards,
    }
    return cfg["listas_escolhidas"][slot_id]["nome"]


def escolher_lista(con, cfg, slot_id: str, aid: int) -> str:
    """*"Vou montar este"*: fixa na caixa a lista de consenso de um arquétipo.

    André, 2026-09-07 (19:00): ele vê o top-3 que está mais perto de concluir e
    marca qual vai montar. E a caixa passa a **permanente**: é o que a põe a
    receber cartas na alocação.

    O que estava lá antes (o Greasefang do Pioneer, por exemplo) fica guardado em
    `_antes` — a chave começa por `_`, por isso o motor não a vê
    (`loadout.config_slots`) e o *"já não vou montar este"* pode desfazer.
    """
    nome = guardar_escolha(con, cfg, slot_id, aid)
    if not nome:
        return "esse arquétipo não tem lista de consenso"
    s = _slot_do_cfg(cfg, slot_id)
    # Só as chaves que EXISTIAM, para o desmarcar saber distinguir "estava a
    # `null`" de "não estava lá" — o `ref` do slot por confirmar é literalmente
    # `null`, e apagá-lo em vez de o repor deixava a caixa sem a chave.
    s.setdefault("_antes", {k: s[k] for k in CHAVES_DA_ESCOLHA if k in s})
    s["fonte"] = "escolhido"
    s["ref"] = slot_id
    s["nome"] = f'{(s.get("nome") or slot_id).split(" — ")[0]} — {nome}'
    # Escolher um deck para a caixa é pô-la a receber cartas: é isso que
    # `permanente` quer dizer. Uma caixa montada não perde esse estado por se
    # escolher outra lista para ela (é o que o «actualizar» existe para fazer).
    if caixas.estado_de(s) == caixas.CANDIDATA:
        s["estado"] = caixas.PERMANENTE
    return f"{nome} escolhido para a caixa {s['nome']}"


def caixa_para_sugestao(cfg, nome: str, fmt: str = "premodern") -> dict:
    """A caixa NOVA de uma sugestão de Premodern — cria-a se ainda não existir.

    A diferença para o *"vou montar este"* do top-N: ali a caixa já existe e está
    vazia (o Standard, o Legacy), e o que ele escolhe é o que lá vai dentro. Aqui
    a caixa é que não existe — o que ele está a dizer é *"quero mais um deck de
    Premodern"*. Criá-la é a única maneira de o deck entrar na alocação, que é o
    que faz a sugestão deixar de ser papel.

    O `balde` copia-se de uma caixa do mesmo formato: é a gaveta de onde as
    cartas de Premodern saem, e inventar aqui um nome novo era criar um balde que
    não existe na estante. A `prioridade` é a última do config e não decide nada
    (o grupo do Premodern ordena-se por % completo) — mas escreve-se, para o dia
    em que ele tirar o `prioridade_por`.
    """
    from mtgvault import premodern as pm                 # noqa: PLC0415

    slot_id = pm.slug(nome)
    caixas_do_cfg = cfg.setdefault("caixas", [])
    for c in caixas_do_cfg:
        if c.get("slot") == slot_id:
            return c
    irmas = [c for c in caixas_do_cfg if c.get("formato") == fmt]
    nova = {"slot": slot_id, "nome": nome, "formato": fmt, "fonte": "deck",
            "ref": None,
            "balde": (irmas[0].get("balde") if irmas else "Colecção"),
            "estado": caixas.CANDIDATA,
            "prioridade": 1 + max([c.get("prioridade") or 0
                                   for c in caixas_do_cfg] or [0]),
            "notas": f"caixa aberta a partir de uma sugestão de {fmt}"}
    caixas_do_cfg.append(nova)
    return nova


def montar_sugestao(con, cfg, nome: str, aid: int, ident: str | None = None) -> str:
    """*"Vou montar este"* numa sugestão do ranking de Premodern.

    O `nome` da caixa é o do arquétipo e mais nada — ao contrário do
    `escolher_lista`, que junta o nome da caixa ao do deck ("Legacy — Doomsday")
    porque ali a caixa já existia e tem identidade própria. Aqui a caixa NASCE do
    arquétipo.

    Quem a faz reconhecer-se como sendo aquela sugestão na corrida seguinte é o
    `id` estável (`premodern._caixa_de`), guardado na `listas_escolhidas`. Era o
    nome, e o nome do clustering muda entre corridas: a caixa nascia com um
    rótulo e no dia seguinte a sugestão reaparecia ao lado dela.
    """
    from mtgvault import premodern as pm                 # noqa: PLC0415

    s = caixa_para_sugestao(cfg, nome)
    legivel = guardar_escolha(con, cfg, s["slot"], aid, nome=nome, ident=ident)
    if not legivel:
        cfg["caixas"].remove(s)          # não se deixa uma caixa vazia por trás
        return "esse arquétipo não tem lista de consenso"
    s["fonte"] = "escolhido"
    s["ref"] = s["slot"]
    # Escolher um deck é pô-lo a receber cartas — mas uma caixa já MONTADA não
    # volta a candidata por se lhe escolher outra lista (é o «actualizar» que
    # existe para isso). A mesma regra do `escolher_lista`.
    if caixas.estado_de(s) == caixas.CANDIDATA:
        s["estado"] = caixas.PERMANENTE
    # Escolher também apaga a recusa: se ele já tinha dito que não e mudou de
    # ideias, deixar a recusa escrita punha o crachá "recusado" numa caixa que
    # ele acabou de mandar montar.
    pm.aceitar(cfg, nome, ident)
    return (f'{nome}: caixa aberta ({s["slot"]}) com a lista de consenso '
            f'congelada em {date.today().isoformat()}')


def desmarcar_lista(cfg, slot_id: str) -> str:
    """*"Já não vou montar este"*: devolve a caixa ao que era antes da escolha."""
    s = _slot_do_cfg(cfg, slot_id)
    antes = s.pop("_antes", None)
    (cfg.get("listas_escolhidas") or {}).pop(slot_id, None)
    if not cfg.get("listas_escolhidas"):
        cfg.pop("listas_escolhidas", None)
    if antes is None:
        return f'{s.get("nome") or slot_id} não tinha escolha para desmarcar'
    for k in CHAVES_DA_ESCOLHA:
        if k in antes:
            s[k] = antes[k]
        else:
            s.pop(k, None)
    return f'{s.get("nome") or slot_id}: escolha desfeita'


def alternar_permanente(cfg, slot_id) -> tuple[str, str]:
    """`candidata` <-> `permanente`. Devolve (estado novo, nome).

    Uma caixa **montada** não passa a candidata por aqui: está sleevada na
    estante, e desfazer isso é o botão *"tirar da caixa"* (que também apaga a
    `copy_allocation`). Dois caminhos para o mesmo estado é o que a escala de
    estados da v6 veio evitar.
    """
    s = caixas.caixa_do_cfg(cfg, slot_id)
    nome = s.get("nome") or slot_id
    actual = caixas.estado_de(s)
    if actual == caixas.MONTADA:
        return actual, nome
    s["estado"] = (caixas.CANDIDATA if actual == caixas.PERMANENTE
                   else caixas.PERMANENTE)
    return s["estado"], nome


def alternar_montada(cfg, slot_id) -> tuple[bool, str]:
    """`montada` <-> `permanente` — o *"sleevado e na caixa"* / *"tirar da caixa"*."""
    s = caixas.caixa_do_cfg(cfg, slot_id)
    montada = caixas.estado_de(s) != caixas.MONTADA
    s["estado"] = caixas.MONTADA if montada else caixas.PERMANENTE
    return montada, (s.get("nome") or slot_id)


def despromover(cfg, slot_id) -> str:
    """Uma caixa que se desmonta deixa de estar `montada` — volta a `permanente`.

    Só desce de `montada`: uma **candidata** com cartas registadas lá dentro
    (o caso das quatro caixas de 2026-09-08, que herdaram alocação da migração)
    fica candidata. Promovê-la aqui era mudar-lhe a ordem da alocação com um
    botão que ele carregou para arrumar cartas, não para escolher prioridades.
    """
    s = caixas.caixa_do_cfg(cfg, slot_id)
    if caixas.estado_de(s) == caixas.MONTADA:
        s["estado"] = caixas.PERMANENTE
    return s.get("nome") or slot_id


# ---------------------------------------------------------------------------
# Escritas na base de dados (o que é FÍSICO)
# ---------------------------------------------------------------------------
def desmontar(con, slot_id: str, nome: str | None = None) -> dict:
    """"Desmontar": esvazia a `copy_allocation` desta caixa, com backup e registo.

    O motor é o `loadout.desmontar_caixa` — aqui só se lhe dá o nome da caixa
    para o registo dizer qual foi. A 2026-09-08 isto fez-se à mão em SQL nas
    quatro caixas que não estavam montadas; um gesto que ele precisa de fazer e
    que só existe no SQL acaba por ser feito no SQL, sem backup e sem rasto.
    """
    return loadout.desmontar_caixa(con, slot_id, nome)



class SemLista(ValueError):
    """Um pedido de registo que não traz a lista de cópias marcadas.

    André, 2026-09-09, à letra: *"se eu não seleccionar no deck que meti a carta,
    com checkmark, é porque eu não a tenho e estás a fazer confusão."* Até aqui o
    *"sleevado e na caixa"* gravava a alocação CALCULADA — e foi assim que 65
    linhas entraram no Cloud cEDH às 10:39 de 09/09, duas delas de cartas que ele
    não tem. Um pedido sem lista deixou de ser um registo de tudo: é um **400**
    com a razão, para uma página velha no telemóvel falhar alto em vez de
    escrever na estante uma afirmação que ninguém fez.
    """


def _marcadas_do_pedido(dados: dict, act: str) -> list[int]:
    """Os `copy_id` que o browser diz que ele marcou. Sem eles não se grava.

    A diferença entre *"não mandou lista"* e *"mandou uma lista vazia"* não
    interessa aqui: as duas querem dizer que não há nada confirmado, e as duas
    têm de ser recusadas. O que interessa é a mensagem dizer o que fazer.
    """
    lista = dados.get("copias")
    if not isinstance(lista, list) or not lista:
        raise SemLista(
            f"o registo ({act}) só grava as cópias que marcaste, e este pedido "
            f"não trouxe nenhuma. Marca as cartas que meteste na caixa e "
            f"carrega outra vez (se a página é de antes de hoje, recarrega-a).")
    return [int(c) for c in lista]


def registar_parcial(con, cfg, slot_id: str, marcadas, de_outra=(),
                     origem: str = "manual") -> dict:
    """Regista as cópias MARCADAS de uma caixa, e ajusta-lhe o estado.

    André, 2026-09-08, à letra: *"Não é mais fácil confirmares que eu seleccionei
    todas as cartas do deck, e assim eu confirmo que montei o deck?"* A barra de
    montagem chama isto a cada registo — completo ou a meio.

    Duas metades, uma em cada sítio: o que é FÍSICO (que cópias estão dentro da
    caixa) vai para a `copy_allocation`, pelo `loadout.registar_marcadas`; o
    ESTADO vai para o config. Quem decide se a caixa está completa é a base
    (`falta == 0`) e nunca a contagem que o browser mandou — o `feitos` está
    guardado no aparelho e pode ser de uma alocação de ontem.

    A caixa **sobe**, nunca desce: uma `candidata` a meio de ser montada passa a
    `permanente` (está a ficar com as cartas, e é isso que `permanente` quer
    dizer), uma `permanente` completa passa a `montada`, e uma que já se diz
    montada continua montada — registar-lhe um delta não é desmontá-la.

    É o ÚNICO caminho que mete cartas numa caixa a partir da página (2026-09-09).
    O *"sleevado e na caixa"* e o *"sim, está montada assim"* eram um segundo, e
    esse gravava a alocação calculada em vez do que ele marcou.
    """
    rep = loadout.report(con)
    s = caixas.caixa_do_cfg(cfg, slot_id)
    antes = caixas.estado_de(s)
    r = loadout.registar_marcadas(con, rep, slot_id, marcadas, de_outra,
                                  origem=origem)
    if r["completa"]:
        novo = caixas.MONTADA
    elif antes == caixas.CANDIDATA:
        novo = caixas.PERMANENTE
    else:
        novo = antes
    s["estado"] = novo
    _ULTIMO_REGISTO[slot_id] = {"quando": _time.time(), "estado": antes,
                                "linhas": r["antes"], "nome": r["caixa"]}
    return {**r, "estado": novo, "estado_antes": antes,
            "nome": s.get("nome") or r["caixa"] or slot_id}


def anular_registo(con, cfg, slot_id: str) -> str:
    """*"Anular"*: desfaz o último registo desta caixa, tal como estava.

    Repõe a `copy_allocation` da fotografia e devolve o `estado` ao que era. Não
    faz backup nem escreve no `desmontar.log`, e é de propósito: isto não apaga
    nada — é o inverso exacto de uma escrita que aconteceu há segundos, e o que
    ele carregou foi *"enganei-me"*, não *"desmonta a caixa"*.
    """
    reg = _ULTIMO_REGISTO.get(slot_id)
    if reg is None:
        return ""
    if _time.time() - reg["quando"] > ANULAR_JANELA:
        _ULTIMO_REGISTO.pop(slot_id, None)
        return ""
    n = loadout.restaurar_alocacao(con, slot_id, reg["linhas"])
    caixas.caixa_do_cfg(cfg, slot_id)["estado"] = reg["estado"]
    _ULTIMO_REGISTO.pop(slot_id, None)
    nome = reg["nome"] or slot_id
    return (f"{nome}: registo anulado — a caixa voltou a {reg['estado']}"
            + (f" com {n} cópias" if n else " e vazia"))


def registar_falta(con, dados: dict) -> dict:
    """*"Já a tenho, está no deck"*: o check de uma linha da lista de compras.

    André, 2026-09-08, à letra: *"Arranja forma de eu poder dar check nas cartas
    das faltas, para dizer que já as tenho e já coloquei no deck."*

    **Desde 2026-09-19 não cria cópia nenhuma** (André: *"cada vez que eu
    adiciono que tenho a carta, fica pendente de foto; quando coloco a foto,
    adicionas à coleção"*): abre uma ENCOMENDA directamente em *pendente de
    foto*, e é a foto que a transforma em cópia e a mete na caixa
    (`encomendas.conciliar`, no import). O motor antigo
    (`loadout.registar_falta`, cópia com «edição por confirmar» + linha na
    `copy_allocation`) fica no código como caminho antigo, sem botão.
    """
    slot_id = dados.get("slot")
    nm = (dados.get("nm") or "").strip()
    if not nm:
        raise ValueError("sem carta")
    r = encomendas.adicionar(
        con, slot_id, nm, int(dados.get("q") or 1),
        set_code=((dados.get("set") or "").strip().lower() or None),
        collector_number=((dados.get("num") or "").strip() or None),
        origem=encomendas.ORIGEM_JA_TENHO, estado=encomendas.PENDENTE)
    return {**r, "q": int(dados.get("q") or 1),
            "msg": (f'{dados.get("q") or 1}× {r["nm"]} pendente de foto para '
                    f'{r["caixa"] or "a colecção"} ({r["impressao"]}) — tira-lhe a '
                    f'foto e larga-a em pendentes/: é a foto que a mete na '
                    f'colecção e na caixa')}


def _encomenda(con, dados: dict) -> str:
    """`POST /api/encomenda`: o `+` (delta > 0) e o `−` (delta < 0).

    Por `id` (um tile do separador) ou por (`slot`, `nm`) (uma linha de compra
    de uma caixa). O `+` valida contra a regra de material da caixa e o
    catálogo (`encomendas.validar`); o `−` nunca vai abaixo de zero.
    """
    delta = int(dados.get("delta") or 0)
    if not delta:
        raise ValueError("sem delta")
    ident = dados.get("id") or None
    slot, nm = dados.get("slot") or None, (dados.get("nm") or "").strip()
    if delta > 0:
        if ident and not nm:
            r = encomendas.por_id(con, ident)
            if r is None:
                raise ValueError("essa encomenda já não existe — recarrega a página")
            slot, nm = r["slot"], r["nm"]
            dados = {**dados, "set": r["set_code"] or "", "num": r["collector_number"] or ""}
        r = encomendas.adicionar(
            con, slot, nm, delta,
            set_code=((dados.get("set") or "").strip().lower() or None),
            collector_number=((dados.get("num") or "").strip() or None),
            origem=(dados.get("origem") or "").strip() or None,
            preco=(float(dados["preco"]) if dados.get("preco") else None))
        return (f'{r["qty_a_caminho"]}× {r["nm"]} a caminho para '
                f'{r["caixa"] or "a colecção"} ({r["impressao"]})')
    r = encomendas.remover(con, ident, slot=slot, nm=nm, qty=-delta)
    if not r["tirado"]:
        raise ValueError(f"{r['nm'] or nm}: não há nada encomendado para tirar")
    return f'{r["tirado"]}× {r["nm"]} a menos na encomenda'


def _encomenda_chegou(con, dados: dict, desfazer: bool = False) -> str:
    ident = dados.get("id") or None
    slot, nm = dados.get("slot") or None, (dados.get("nm") or "").strip()
    q = int(dados["q"]) if dados.get("q") else None
    if desfazer:
        r = encomendas.desfazer_chegou(con, ident, slot=slot, nm=nm, qty=q)
        if not r["movido"]:
            raise ValueError(f"{r['nm'] or nm}: não há nada pendente de foto para desfazer")
        return f'{r["movido"]}× {r["nm"]} de volta a «a caminho»'
    r = encomendas.chegou(con, ident, slot=slot, nm=nm, qty=q)
    if not r["movido"]:
        raise ValueError(f"{r['nm'] or nm}: não há nada a caminho para dar como chegado")
    return (f'{r["movido"]}× {r["nm"]} chegou — pendente de foto: tira-lhe a foto '
            f'e larga-a em pendentes/')


def marcar_nao_encontradas(con, slot_id: str, copias) -> dict:
    """*"Não encontrei estas"*: as cópias por marcar saem da colecção.

    André, 2026-09-09, à letra: *"se eu não seleccionar no deck que meti a carta,
    com checkmark, é porque eu não a tenho e estás a fazer confusão."*

    O relatório recalcula-se AQUI, como no *"vendida"* e no *"já a tenho"*: a
    página pode estar aberta há duas horas e mandar tirar de circulação uma
    cópia que entretanto já está dentro de uma caixa. Quem valida que cada
    `copy_id` era mesmo desta caixa é o `loadout.marcar_nao_encontradas`.
    """
    r = loadout.marcar_nao_encontradas(con, loadout.report(con), slot_id,
                                       [int(c) for c in (copias or [])])
    nomes = ", ".join(f'{m["q"]}× {m["nm"]}' for m in r["linhas"][:4])
    resto = len(r["linhas"]) - 4
    return {**r, "ids": [m["copy_id"] for m in r["linhas"]],
            "porque": (r["saltadas"][0]["porque"] if r["saltadas"]
                       else "não havia nada por marcar nesta caixa"),
            "msg": (f'{r["caixa"]}: {r["copias"]} cópia(s) fora da colecção — '
                    f'{nomes}' + (f" e mais {resto}" if resto > 0 else "")
                    + ". Voltam a ser compra.")}


def anular_falta(con, dados: dict) -> str:
    """O desfazer do check: o `−` da encomenda pendente que ele acabou de abrir.

    Desde 2026-09-19 não há janela (`_ULTIMA_FALTA` ficou do caminho antigo):
    o check já não cria cópia nenhuma, e tirar uma encomenda pendente é um
    gesto sem custo, com rasto no `encomendas.log`. Aceita o `copy_id` de uma
    página antiga só para responder com uma frase em vez de um 500.
    """
    ident = dados.get("id")
    if not ident:
        return ""
    r = encomendas.remover(con, ident, qty=int(dados.get("q") or 1),
                           estado=encomendas.PENDENTE)
    if not r["tirado"]:
        return ""
    return f'{r["tirado"]}× {r["nm"]}: desfeito — voltou a ser compra'


def recolher_fotos_de_caixas() -> dict | None:
    """O caminho (b) da FOTO DA DECKBOX (2026-09-21): `pendentes/deckboxes/
    <slot>.jpg` → `fotocaixa.recolher`. Só pega no lock de escrita quando há
    mesmo alguma coisa lá — corre a cada pedido do índice. Os ignorados (um
    nome que não é slot, um ficheiro que não é imagem) ficam onde estão e
    saem no `webapp.log` via `print`; nada se apaga."""
    if not fotocaixa.ha_pendentes(ROOT, ignorar=_FOTOS_IGNORADAS):
        return None
    with ESCRITA:
        if not fotocaixa.ha_pendentes(ROOT, ignorar=_FOTOS_IGNORADAS):
            return None                             # outro pedido já as levou
        cfg = ler_config()
        r = fotocaixa.recolher(cfg, raiz=ROOT, ignorar=_FOTOS_IGNORADAS)
        if r["recolhidas"]:
            escrever_config(cfg)
            sources._CFG_CACHE.clear()
            _CACHE.clear()
        for ig in r["ignorados"]:
            # Fica memorizado (nome + tamanho + mtime): um ficheiro que não é
            # slot nem imagem não se volta a ler a cada pedido do índice, e a
            # linha sai UMA vez no `webapp.log`. Mudá-lo (ou renomeá-lo) volta
            # a tentar.
            print(f"[foto-caixa] ignorado pendentes/deckboxes/{ig['ficheiro']}: {ig['porque']}")
        return r


# O que já se viu em `pendentes/deckboxes/` e não serve: `{nome: (tamanho, mtime)}`.
_FOTOS_IGNORADAS: dict[str, tuple] = {}


def regenerar(con) -> None:
    """Reescreve as páginas estáticas, para o site publicado acompanhar.

    Sem isto, o modo edição e o GitHub Pages diziam coisas diferentes até à
    corrida seguinte do `daily.py` — e a diferença aparecia no telemóvel dele,
    fora de casa, sem explicação nenhuma.

    São as DUAS: qualquer botão desta página muda a alocação, e a alocação é o
    que o `metagame.html` mostra (a posse do top-N e o crachá "escolhido em").
    Refazer só uma deixava a outra a dizer o contrário. Custam ~0,3 s cada.
    """
    # O relatório calcula-se UMA vez (2026-09-20): a Deckboxes, o
    # `esperadas.md` (que desde a revalidação precisa da alocação para saber
    # que cópias são da caixa que ele está a fotografar) lêem o mesmo.
    rep = loadout.report(con)
    deckboxes.build(con, ROOT / "deckboxes.html", rep=rep)
    metagame.build(con, ROOT / "metagame.html")
    # O que está pendente de foto, para o Claude que cataloga as fotos
    # (2026-09-19). Ao lado das fotos, e apaga-se quando não há nada.
    encomendas.escrever_esperadas(con, ROOT / "pendentes", rep=rep)
    _CACHE.clear()


# REGENERAR EM FUNDO (2026-09-21). Medido no 8771 a sério, no dia em que as
# fotos passaram a vir do telemóvel: um `POST /api/foto` que regenerava antes
# de responder demorava **109–112 s** (o `loadout.report` + as duas páginas +
# o `esperadas.md`, neste PC e nesse dia) — mais do que o prazo do `gravar()`
# da página, que dizia *"não sei se gravou"* com a foto já em `pendentes/`.
# A foto está guardada no instante em que o ficheiro fecha; o que a
# regeneração acrescenta (a secção do `esperadas.md`, as páginas estáticas)
# pode vir a seguir. Uma thread por pedido, a pegar no MESMO lock de escrita
# (`ESCRITA`) — nunca duas regenerações ao mesmo tempo, nunca por cima de um
# botão. `esperar_fundo()` é para os testes (e para quem precise da
# regeneração feita antes de ler o ficheiro).
_FUNDO: list[threading.Thread] = []


def regenerar_em_fundo(motivo: str = "") -> threading.Thread:
    def corre():
        with ESCRITA:
            try:
                with db.session() as con:
                    regenerar(con)
            except Exception as e:                          # noqa: BLE001
                print(f"[regenerar em fundo{' — ' + motivo if motivo else ''}] "
                      f"falhou: {type(e).__name__}: {e}")
    t = threading.Thread(target=corre, name=f"regenerar-{motivo or 'fundo'}", daemon=True)
    _FUNDO[:] = [x for x in _FUNDO if x.is_alive()]
    _FUNDO.append(t)
    t.start()
    return t


def esperar_fundo(timeout: float | None = None) -> None:
    for t in list(_FUNDO):
        t.join(timeout)


# ---------------------------------------------------------------------------
# A CACHE do que custa caro (2026-09-15)
# ---------------------------------------------------------------------------
# Medido antes disto: um `GET /` demorava **4,4–5 s** do próprio PC (e mais de
# 10 s do telemóvel, com a ligação a ficar em CLOSE_WAIT), porque cada pedido
# corria o `loadout.report` inteiro + o payload da Deckboxes (745 KB) do zero —
# e a sonda da tarefa `mtgvault-serve` fazia-o de 5 em 5 min. O `metagame.html`
# custava 1,6 s pela mesma razão.
#
# Agora: (1) a página é a CASCA (estática, ~40 KB) e sai na hora; (2) os DADOS
# (`/data/paginas/deckboxes.json` + as partes) calculam-se uma vez e ficam em
# memória até a base, o config ou o registo de arquétipos mudarem — a VERSÃO
# é o mtime desses ficheiros, e um POST limpa a cache de qualquer maneira
# (`regenerar`). O `metagame.html` fica na mesma cache, pela mesma chave.
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()


def _versao() -> tuple:
    """O que, ao mudar, invalida tudo o que está em cache.

    A pasta `pendentes/` entra (2026-09-21) pelo mtime da PASTA: o NTFS
    actualiza-o quando um ficheiro entra ou sai dela, e é isso que a aba
    Revalidação mostra («fotos à espera») — uma foto que o telemóvel acabou
    de mandar, ou que o `mtg-fotos-novas` das 02:30 acabou de arrumar, sem
    ninguém carregar em nada.
    """
    base = Path(db.DEFAULT_DB)
    ficheiros = [base, base.with_name(base.name + "-wal"), CONFIG,
                 Path(db.pasta_dados()) / "arquetipos.json", ROOT / "pendentes"]
    out = []
    for f in ficheiros:
        try:
            st = f.stat()
            out.append((str(f), st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((str(f), None, None))
    return tuple(out)


def em_cache(chave, calcular):
    """`calcular()` uma vez por versão; os pedidos em paralelo esperam pelo
    primeiro em vez de calcularem todos a mesma coisa."""
    v = _versao()
    with _CACHE_LOCK:
        hit = _CACHE.get(chave)
        if hit and hit[0] == v:
            return hit[1]
        valor = calcular()
        _CACHE[chave] = (v, valor)
        return valor


def dados_deckboxes(editavel: bool, tok: str) -> tuple[dict, dict]:
    """`(indice, partes)` da Deckboxes para este modo, da cache."""
    def calcular():
        with db.session() as con:
            return deckboxes.partir(deckboxes.payload(
                con, loadout.report(con), editable=editavel, token=tok,
                ligacao=(ligacao_local() if editavel else None)))
    return em_cache(("deckboxes", editavel), calcular)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "mtgvault"

    def _envia(self, corpo, code=200, tipo="text/html; charset=utf-8",
               cache: bool = False):
        b = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        self.send_response(code)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(b)))
        # O telemóvel guardava o HTML antigo em cache e a página parecia partida
        # depois de qualquer alteração — sem erro nenhum à vista. É a mesma nota
        # que está no `riftvault/server.py`. A EXCEPÇÃO (`cache=True`) é o
        # `deckboxes.js` pedido com `?v=<hash do conteúdo>`: o URL muda quando o
        # texto muda, por isso o que o telemóvel guardou nunca fica velho — e
        # deixa de baixar 120 KB a cada toque no menu.
        self.send_header("Cache-Control",
                         "public, max-age=31536000, immutable" if cache
                         else "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(b)

    def _json(self, obj, code=200):
        self._envia(json.dumps(obj, ensure_ascii=False), code,
                    "application/json; charset=utf-8")

    # -- quem pode escrever ------------------------------------------------
    def _token_do_pedido(self) -> str | None:
        u = urlparse(self.path)
        q = parse_qs(u.query).get("t")
        return self.headers.get(CABECALHO_TOKEN) or (q[0] if q else None)

    def _pode_escrever(self) -> bool:
        """Loopback é de confiança; da rede exige-se o token (ver o cabeçalho)."""
        ip = (self.client_address[0] if self.client_address else "")
        return ip in ("127.0.0.1", "::1") or token_valido(self._token_do_pedido())

    def do_GET(self):                                  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho in ("/qr.svg", "/qr"):
            # O QR do link COMPLETO (com token) da rede local. É o que ele aponta
            # com o telemóvel; escrever o URL à mão num teclado de telemóvel é
            # exactamente o atrito que faz não se usar a ferramenta.
            #
            # E por isso esta imagem TAMBÉM exige o token: um QR é um URL
            # legível: servi-lo a quem não o tem era dar-lhe o token pela porta
            # do lado, e o 403 dos `POST` deixava de valer nada. A página pede-a
            # com o `?t=` (ver `ligacaoHTML` no `deckboxes.py`).
            if not self._pode_escrever():
                self._envia("<h1>403</h1><p>o QR leva o token — não se serve a "
                            "quem não o tem.</p>", 403)
                return
            self._envia(qr.svg(url_edicao()), tipo="image/svg+xml; charset=utf-8")
            return
        if caminho == "/foto":
            # A miniatura da foto de origem de uma cópia NÃO ENCONTRADA
            # (2026-09-09). É a única prova de que a carta existiu, e sem ela a
            # lista é um nome sem nada por trás.
            #
            # O caminho sai da BASE, pelo `copy_id`, e nunca do pedido: servir um
            # caminho que veio no URL era dar qualquer ficheiro do PC a quem está
            # na rede de casa. Exige token pela mesma razão que o `/qr.svg` — as
            # fotos são da colecção dele.
            if not self._pode_escrever():
                self._envia("<h1>403</h1>", 403)
                return
            cid = (parse_qs(urlparse(self.path).query).get("copy") or ["0"])[0]
            with db.session() as con:
                alvo = loadout.foto_da_copia(con, int(cid or 0))
            if alvo is None:
                self._envia("<h1>404</h1><p>essa cópia não tem foto no disco</p>", 404)
                return
            self._envia(alvo.read_bytes(),
                        tipo=TIPOS_FOTO.get(alvo.suffix.lower(), "image/jpeg"))
            return
        if caminho == "/" + deckboxes.NOME_JS:
            # O JavaScript da Deckboxes (2026-09-18), DA MEMÓRIA e não do disco:
            # a casca que este processo serve aponta para o hash do texto que
            # este processo tem, e o ficheiro em `ROOT` pode ser de uma corrida
            # antiga do `daily` — servi-lo era dar ao browser um `.js` velho com
            # um URL novo, guardado para sempre. Só é cacheável com o `?v=`.
            self._envia(deckboxes.js_texto(), tipo="text/javascript; charset=utf-8",
                        cache="v=" in urlparse(self.path).query)
            return
        modulo = PAGINAS_EDITAVEIS.get(caminho)
        if modulo is not None:
            # A página só leva o token DENTRO dela quando o pedido já o trazia —
            # senão bastava abri-la de qualquer telemóvel da rede para o
            # descobrir, e o token não protegia nada.
            editavel = self._pode_escrever()
            tok = token() if editavel else ""
            if modulo is deckboxes:
                # A CASCA: estática, sem dados. Os dados vêm a seguir, por
                # `fetch`, de `/data/paginas/deckboxes.json` (abaixo) — e é o
                # `?t=` desse pedido que decide se levam os botões.
                self._envia(com_token(deckboxes.casca(), tok))
                return

            def gerar():
                with db.session() as con:
                    return modulo.html_page(
                        con, editable=editavel, token=tok,
                        ligacao=(ligacao_local() if editavel else None))
            self._envia(com_token(em_cache((caminho, editavel), gerar), tok))
            return
        m = _DADOS_DECKBOXES.match(caminho)
        if m:
            # Os DADOS da Deckboxes, calculados (e guardados) para este modo.
            editavel = self._pode_escrever()
            if m.group(1) is None:
                # A FOTO DA DECKBOX largada em `pendentes/deckboxes/<slot>.jpg`
                # (2026-09-21): recolhe-se ao pedir o índice, para o modo edição
                # a mostrar sem esperar pelo daily. Barato quando não há nada.
                recolher_fotos_de_caixas()
            idx, partes = dados_deckboxes(editavel, token() if editavel else "")
            parte = m.group(1)
            if parte is None:
                self._json({**idx,
                            "_gerado_em": datetime.now().isoformat(timespec="seconds"),
                            "_partes": sorted(partes)})
            elif parte in partes:
                self._json(partes[parte])
            else:
                self._json({"erro": f"não há parte {parte!r} na Deckboxes de "
                                    f"hoje — recarrega a página"}, 404)
            return
        nome = caminho.lstrip("/")
        alvo = (ROOT / nome).resolve()
        mf = _FOTO_CAIXA.match(caminho)
        if mf:
            # A versão reduzida da FOTO DA DECKBOX (2026-09-21), do disco: é a
            # mesma que vai no Git para o site publicado. Leitura livre — é
            # pública de qualquer maneira. Com o `?v=<hash>` é cacheável
            # (`fotocaixa.versao`: o URL muda quando a foto muda).
            if not (alvo.is_file() and str(alvo).startswith(str(ROOT))):
                self._envia("<h1>404</h1><p>essa caixa não tem foto</p>", 404)
                return
            self._envia(alvo.read_bytes(), tipo="image/jpeg",
                        cache="v=" in urlparse(self.path).query)
            return
        # Os `.json` só de `data/paginas/` (os dados das outras páginas, escritos
        # pelo `daily`): o resto de `data/` são a base, o token e os registos.
        e_dados = nome.startswith("data/paginas/") and nome.endswith(".json")
        if ((nome.endswith((".html", ".css", ".js")) or e_dados) and alvo.is_file()
                and str(alvo).startswith(str(ROOT))):
            if e_dados:
                self._envia(alvo.read_bytes(), tipo="application/json; charset=utf-8")
                return
            corpo = alvo.read_text(encoding="utf-8")
            if nome.endswith(".html"):
                # O menu destas páginas foi escrito pela corrida do `daily`, sem
                # token nenhum: sem esta linha, sair da Deckboxes para a Coleção
                # e voltar deixava-o numa página só de leitura.
                corpo = com_token(corpo, token() if self._pode_escrever() else "")
            self._envia(corpo, tipo=("text/html; charset=utf-8"
                                     if nome.endswith(".html") else
                                     "text/css; charset=utf-8"
                                     if nome.endswith(".css") else
                                     "text/javascript; charset=utf-8"))
            return
        self._envia("<h1>404</h1><p><a href='/'>Deckboxes</a></p>", 404)

    def do_POST(self):                                 # noqa: N802
        caminho = urlparse(self.path).path
        tam = int(self.headers.get("Content-Length") or 0)
        # As FOTOS DAS CARTAS (2026-09-21) vêm várias num pedido: o tecto é o
        # do pedido inteiro (`fotosite.MAX_PEDIDO`); o resto continua a ser o
        # de UMA foto. Sem ler: uma "foto" de 40 MB não é uma foto, é um engano.
        tecto = fotosite.MAX_PEDIDO if caminho == "/api/foto" else fotocaixa.MAX_BYTES
        if tam > tecto:
            self._json({"erro": f"o corpo tem {tam / 1e6:.1f} MB — o máximo é "
                                f"{tecto // (1024 * 1024)} MB"}, 413)
            return
        bruto = self.rfile.read(tam) if tam else b""
        if not self._pode_escrever():
            # Ler é livre, escrever não. Sem isto, pôr o porto na rede local
            # (MTGVAULT_BIND=0.0.0.0) dava a qualquer aparelho de casa — ou a
            # qualquer visita no Wi-Fi — o direito de lhe desmontar os decks.
            self._json({"erro": "sem token: este link é só de leitura. Abre o "
                                "link do QR (tem o ?t=) para poderes gravar."}, 403)
            return
        if caminho == "/api/foto-caixa":
            # A FOTO DA DECKBOX (André, 2026-09-21): o corpo é o FICHEIRO tal e
            # qual, não JSON — fica em bytes e nunca se tenta decifrar como
            # texto. O `slot` vem no URL (`?slot=…`). Só config + ficheiros:
            # não toca na base, e regenera porque o índice mudou.
            with ESCRITA:
                try:
                    self._json(self._foto_caixa(bruto))
                except fotocaixa.FotoInvalida as e:
                    self._json({"erro": str(e)}, 409)
                except Exception as e:                  # noqa: BLE001
                    self._json({"erro": f"{type(e).__name__}: {e}"}, 500)
            return
        if caminho == "/api/foto":
            # AS FOTOS DAS CARTAS, TIRADAS DO SITE (André, 2026-09-21): o corpo
            # é um `multipart/form-data` com uma ou várias fotos, que vão TAL E
            # QUAL para a raiz de `pendentes/` com o nome a dizer a origem
            # (`fotosite`). Não toca na base: quem cria/liga cópias é o
            # `mtg-fotos-novas`, como sempre. Regenera-se pelo `esperadas.md`.
            with ESCRITA:
                try:
                    self._json(self._foto_site(bruto))
                except fotocaixa.FotoInvalida as e:
                    self._json({"erro": str(e)}, 409)
                except KeyError as e:
                    self._json({"erro": f"a caixa {e.args[0]!r} não existe no "
                                        f"colecao_config.json — recarrega a página"}, 409)
                except Exception as e:                  # noqa: BLE001
                    self._json({"erro": f"{type(e).__name__}: {e}"}, 500)
            return
        try:
            dados = json.loads(bruto.decode("utf-8") or "{}") if bruto else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            dados = {}
        # UMA escrita de cada vez. O `ThreadingHTTPServer` atende os pedidos em
        # paralelo, e cada botão é um ler-mexer-gravar do `colecao_config.json`:
        # dois cliques ao mesmo tempo (ou um duplo-toque no telemóvel) faziam o
        # segundo gravar por cima do primeiro, e a alteração desaparecia sem
        # erro nenhum. O mesmo vale para a `copy_allocation`, que se apaga e
        # reescreve inteira.
        with ESCRITA:
            try:
                if caminho == "/api/arrumar":
                    with db.session() as con:
                        migracao.backup(con)
                        n = loadout.guardar_arrumacao(con, loadout.report(con))
                        regenerar(con)
                    self._json({"ok": True, "copias": n})
                    return
                if caminho == "/api/caixa":
                    self._json(self._caixa(dados))
                    return
                if caminho == "/api/escolher":
                    self._json(self._escolher(dados))
                    return
                if caminho == "/api/padrao":
                    # LISTA PADRÃO e RESERVA (André, 2026-09-20). Só config —
                    # nada disto toca na base; regenera porque a lista da
                    # caixa (e logo a alocação e a venda) mudou.
                    self._json(self._padrao(dados))
                    return
                if caminho == "/api/vender":
                    self._json(self._vender(dados))
                    return
                if caminho == "/api/feira":
                    # A FEIRA (André, 2026-09-20): taxas, «levo/não levo»,
                    # wantlist e vendors. Só config — nada toca na base;
                    # regenera porque a aba (e o seu subtítulo) mudou.
                    self._json(self._feira(dados))
                    return
                if caminho == "/api/vista":
                    # AS CARTAS EM IMAGEM (André, 2026-09-20): o interruptor
                    # «Imagens / Lista» grava a preferência no config
                    # (`deckboxes.vista`) — no PC e no telemóvel tem de ser a
                    # mesma. Só config, e não regenera nada: o índice sai da
                    # cache, que o mtime do config já invalida.
                    self._json(gravar_vista(dados))
                    return
                if caminho in ("/api/encomenda", "/api/encomenda-chegou",
                               "/api/encomenda-desfazer"):
                    # ENCOMENDAS (André, 2026-09-19): «só a foto cria cópias».
                    # Nenhum destes três escreve em `copies` nem em
                    # `copy_allocation` — mexem na tabela `encomendas`, e por
                    # isso não há backup: nada se perde que uma foto não refaça.
                    # Regenera-se porque o «a comprar» de cada caixa mudou.
                    with db.session() as con:
                        if caminho == "/api/encomenda":
                            msg = _encomenda(con, dados)
                        else:
                            msg = _encomenda_chegou(
                                con, dados, desfazer=caminho.endswith("-desfazer"))
                        regenerar(con)
                    self._json({"ok": True, "msg": msg})
                    return
                if caminho == "/api/revalidacao":
                    # REVALIDAÇÃO POR FOTO (André, 2026-09-20): «Fotografar»
                    # fixa o ALVO no config (uma preferência — vai no Git, como
                    # as caixas) e reescreve o `pendentes/esperadas.md`; «parar»
                    # tira-o. Nada disto toca na base.
                    self._json(self._revalidacao(dados))
                    return
                if caminho == "/api/processar-fotos":
                    # «⚡ PROCESSAR AGORA» (2026-09-21): uma ordem na inbox do
                    # runner do ai-pc que corre o `mtg-fotos-novas` — o MESMO
                    # programa das 02:30. Não toca na base nem no config, e não
                    # corre o Claude local de nenhuma outra forma. Não regenera
                    # (nada da alocação mudou): limpa-se a cache para o índice
                    # passar a dizer «já está a processar» — a inbox não entra
                    # no `_versao`, só `pendentes/`.
                    r = fotosite.pedir_processamento(ROOT / "pendentes", fotosite.pasta_inbox())
                    _CACHE.clear()
                    self._json({"ok": True, **r})
                    return
                if caminho == "/api/venda-export":
                    # «Gravar em data/» (2026-09-18): os mesmos dois ficheiros
                    # que o `daily` escreve (`venda-stock.csv` +
                    # `venda-estante.txt`), com a lista RECALCULADA agora — a
                    # página pode estar aberta desde ontem. Não mexe na base
                    # nem no config, por isso não regenera nada. Com
                    # `so_validadas` (2026-09-20) só as cópias com foto.
                    with db.session() as con:
                        r = venda.exportar(con, so_validadas=bool(dados.get("so_validadas")))
                    self._json({"ok": True, "copias": r["copias"],
                                "linhas": r["linhas"], "csv": r["csv"],
                                "estante": r["estante"],
                                "msg": (f'{r["copias"]} cópias em {r["linhas"]} '
                                        f'linhas → {Path(r["csv"]).name} + '
                                        f'{Path(r["estante"]).name} '
                                        f'(formato {r["formato"]}'
                                        + ("; só validadas" if r.get("so_validadas") else "")
                                        + ")")})
                    return
            except KeyError as e:
                # O caso normal: um `slot` que já não existe no config (a página
                # aberta no telemóvel é de antes de ele o mudar). `repr` dava
                # `KeyError('legacy')`, que não diz nada a quem está a olhar.
                self._json({"erro": f"a caixa {e.args[0]!r} já não existe no "
                                    f"colecao_config.json — recarrega a página"}, 409)
                return
            except SemLista as e:
                # ANTES do `ValueError` (de que é subclasse): um registo sem
                # lista não é um pedido que deixou de bater com a base — é um
                # pedido malformado, e o 400 diz-lhe isso mesmo.
                self._json({"erro": str(e)}, 400)
                return
            except ValueError as e:
                # Um pedido que já não bate com a base: a linha das faltas que
                # ele carregou já não está em falta, ou a edição que veio no
                # pedido não serve a caixa. A mensagem é para ele ler, e por isso
                # vai sem o nome da excepção à frente.
                self._json({"erro": str(e)}, 409)
                return
            except Exception as e:                      # noqa: BLE001
                self._json({"erro": f"{type(e).__name__}: {e}"}, 500)
                return
        self._json({"erro": "endpoint desconhecido"}, 404)

    def _caixa(self, dados):
        act, slot_id = dados.get("act"), dados.get("slot")
        # As cópias que ele marcou no bloco «destinadas a outra caixa» do painel
        # Montar (2026-09-08). Só o `montado`/`confirmar` as usa.
        de_outra = [int(c) for c in (dados.get("de_outra") or [])]
        # O que a resposta leva além do `msg` — hoje só o `copy_id` do «já a
        # tenho», que é por onde o *anular* pega na cópia que acabou de nascer.
        extra: dict = {}
        cfg = ler_config()
        with db.session() as con:
            if act == "permanente":
                novo, nome = alternar_permanente(cfg, slot_id)
                if novo == caixas.MONTADA:
                    return {"erro": f"{nome} está montada — usa «tirar da caixa»"}
                escrever_config(cfg)
                msg = f"{nome} passou a {novo}"
            elif act in ("subir", "descer"):
                msg = mover(con, cfg, slot_id, -1 if act == "subir" else 1)
                escrever_config(cfg)
            elif act == "montado" and caixas.estado_de(
                    caixas.caixa_do_cfg(cfg, slot_id)) == caixas.MONTADA:
                # Só o sentido «tirar da caixa» é que ainda é um gesto próprio.
                # O sentido contrário — meter cartas na caixa — passou a ser o
                # `registar`, e por isso exige a lista do que ele marcou.
                novo, nome = alternar_montada(cfg, slot_id)
                assert novo is False                # já estava montada: desliga
                escrever_config(cfg)
                r = desmontar(con, slot_id, nome)
                msg = (f"{nome}: desmontada — {r['copias']} cópias voltam "
                       f"à colecção ({r['linhas']} linhas)")
            elif act == "desmontar":
                # O inverso do "sleevado e na caixa": as cartas voltam à gaveta.
                # Passa pelo mesmo motor do botão de cima (backup + registo no
                # `data/desmontar.log`) — dois caminhos para o mesmo gesto era o
                # que a escala de estados da v6 veio evitar.
                nome = despromover(cfg, slot_id)
                escrever_config(cfg)
                r = desmontar(con, slot_id, nome)
                msg = (f"{nome}: desmontada — {r['copias']} cópias voltam à "
                       f"colecção ({r['linhas']} linhas)"
                       + (f", backup em {Path(r['backup']).name}"
                          if r.get("backup") else ""))
            elif act in ("registar", "montado", "confirmar"):
                # UM SÓ CAMINHO PARA METER CARTAS NUMA CAIXA (2026-09-09). Os
                # três nomes chegam aqui — o `montado` e o `confirmar` são de
                # páginas antigas — e todos exigem a lista de cópias marcadas:
                # gravar a alocação calculada é o que pôs no Cloud cEDH duas
                # cartas que ele não tem. A `origem` diz se o clique foi dele
                # (`manual`) ou o auto-registo da última marca (`auto`).
                marcadas = _marcadas_do_pedido(dados, act)
                origem = "auto" if dados.get("origem") == "auto" else "manual"
                r = registar_parcial(con, cfg, slot_id, marcadas, de_outra,
                                     origem)
                escrever_config(cfg)
                msg = (f'{r["nome"]}: {r["copias"]} cópias na caixa'
                       + (" — montada ✅" if r["completa"]
                          else f' · faltam {r["falta"]} por tirar')
                       + (f' ({r["de_outra"]} eram de outra caixa — ela passa a '
                          f'vir buscá-las aqui)' if r["de_outra"] else ""))
            elif act == "falta":
                # «JÁ A TENHO, ESTÁ NO DECK» (André, 2026-09-08; desde
                # 2026-09-19 abre uma encomenda PENDENTE DE FOTO em vez de criar
                # a cópia — só a foto cria cópias). Não passa pelo config: vive
                # na tabela `encomendas`, e o `id` é por onde o «anular» pega.
                r = registar_falta(con, dados)
                msg, extra["id"] = r["msg"], r["id"]
            elif act == "falta-anular":
                msg = anular_falta(con, dados)
                if not msg:
                    return {"erro": "essa encomenda já não está pendente — "
                                    "recarrega a página (na aba Encomendas o «−» "
                                    "tira o que lá estiver)"}
            elif act == "nao-encontrei":
                # «SE NÃO MARQUEI, É PORQUE NÃO A TENHO» (André, 2026-09-09): o
                # inverso do «já a tenho». Não passa pelo config — o que muda é a
                # colecção, e isso vive na base. O relatório é recalculado aqui,
                # como no «vendida»: a página pode estar aberta há duas horas.
                r = marcar_nao_encontradas(con, slot_id, dados.get("copias"))
                if not r["copias"]:
                    return {"erro": r["porque"]}
                msg, extra["copias"] = r["msg"], r["ids"]
            elif act == "encontrei":
                # «Afinal encontrei»: a cópia volta a contar. Serve os dois
                # caminhos — o «anular» do aviso e o botão da lista — porque é o
                # mesmo gesto, e dois caminhos era a segunda oportunidade de
                # discordarem.
                r = loadout.devolver_a_coleccao(con, dados.get("copias") or [])
                if not r["copias"]:
                    return {"erro": "essas cópias já estão na colecção"}
                msg = (f'{r["copias"]} cópia(s) de volta à colecção: '
                       + ", ".join(m["nm"] for m in r["linhas"]))
            elif act == "anular":
                # O desfazer do registo automático, enquanto o aviso está à vista.
                msg = anular_registo(con, cfg, slot_id)
                if not msg:
                    return {"erro": "já não há registo para anular nesta caixa — "
                                    "para a esvaziar há o «Desmontar»"}
                escrever_config(cfg)
            elif act == "actualizar":
                # "Actualizei": aplica o delta de UMA caixa congelada. Não passa
                # pelo config — o que muda é físico (que cartas estão na caixa),
                # e isso vive na `copy_allocation`.
                migracao.backup(con)
                rep = loadout.report(con)
                nome = next((s["nome"] for s in rep["slots"]
                             if s["slot"] == slot_id), slot_id)
                n = loadout.actualizar_caixa(con, rep, slot_id)
                msg = f"{nome} actualizado: {n} cópias na caixa"
            else:
                return {"erro": f"acção {act!r} desconhecida"}
            sources._CFG_CACHE.clear()     # relê já, sem esperar pelo mtime
            regenerar(con)
        return {"ok": True, "msg": msg, **extra}

    def _vender(self, dados):
        """"Vendida": a cópia sai da colecção e fica registada no `vendas.csv`.

        A linha vem da própria página (é a que ele está a ver), e por isso o
        servidor **recalcula-a** antes de tirar nada: uma página aberta há duas
        horas podia mandar tirar uma cópia que a alocação já deu a uma caixa.
        """
        chave, q = dados.get("linha"), dados.get("q")
        if not chave:
            return {"erro": "sem linha"}
        with db.session() as con:
            migracao.backup(con)
            rep = loadout.report(con)
            alvo = next((r for k in ("venda", "venda_rl", "retidos")
                         for r in rep[k]
                         if loadout.chave_venda(r) == chave), None)
            if alvo is None:
                return {"erro": "essa linha já não está na lista de venda — "
                                "recarrega a página"}
            res = loadout.registar_venda(con, alvo, q)
            regenerar(con)
        return {"ok": True, "msg": f'{res["copias"]}× {alvo["nm"]} fora da '
                                   f'colecção e no vendas.csv'}

    def _foto_caixa(self, bruto: bytes) -> dict:
        """`POST /api/foto-caixa?slot=…` com a foto no corpo (André, 2026-09-21).

        Tudo o que decide vive no `mtgvault.fotocaixa.guardar`: o tipo pelos
        primeiros bytes, a anterior para `anteriores/`, o original em
        `data/deckboxes/`, a reduzida em `assets/deckboxes/` e a data na caixa.
        Aqui só se lê o `slot`, se grava o config e se regenera.
        """
        q = parse_qs(urlparse(self.path).query)
        slot = (q.get("slot") or [""])[0].strip()
        if not slot:
            raise fotocaixa.FotoInvalida("sem caixa (`?slot=`)")
        cfg = ler_config()
        r = fotocaixa.guardar(cfg, slot, bruto, origem="enviada pelo 8771", raiz=ROOT)
        escrever_config(cfg)
        sources._CFG_CACHE.clear()
        with db.session() as con:
            regenerar(con)
        kb = lambda n: f"{max(1, round(n / 1024))} KB"        # noqa: E731
        return {"ok": True, "slot": slot,
                "msg": (f"📦 Foto da deckbox «{r['nome']}» guardada: original "
                        f"{kb(r['bytes_original'])} em data/deckboxes/, versão do site "
                        f"{kb(r['bytes_reduzida'])} em assets/deckboxes/"
                        + (" (a anterior ficou em anteriores/)" if r["anterior"] else "")
                        + (f" — {r['aviso']}" if r["aviso"] else "")),
                "bytes_original": r["bytes_original"],
                "bytes_reduzida": r["bytes_reduzida"], "anterior": r["anterior"],
                "aviso": r["aviso"]}

    def _foto_site(self, bruto: bytes) -> dict:
        """`POST /api/foto?tipo=caixa&slot=…[&copy=<id>]` com as fotos no corpo
        (`multipart/form-data`, uma ou várias) — André, 2026-09-21: *"tirar as
        fotos directamente do site"*.

        Tudo o que decide vive no `mtgvault.fotosite`: o multipart, o tipo
        pelos primeiros bytes, o nome com a origem, a escrita atómica na RAIZ
        de `pendentes/` (a foto inteira, tal como veio). Aqui lê-se o alvo do
        URL, valida-se a caixa contra o config e a cópia contra a base, e
        responde-se LOGO — a regeneração (é o `regenerar` que reescreve o
        `esperadas.md`, e a secção das fotos do site tem de lá estar antes das
        02:30) corre em fundo (`regenerar_em_fundo`): medida a 109–112 s neste
        PC, não cabe no prazo da página, e a foto já está guardada.
        """
        q = parse_qs(urlparse(self.path).query)
        tipo = (q.get("tipo") or ["caixa"])[0].strip() or "caixa"
        slot = (q.get("slot") or [""])[0].strip() or None
        copy_raw = (q.get("copy") or [""])[0].strip()
        if tipo not in fotosite.TIPOS:
            raise fotocaixa.FotoInvalida(f"alvo {tipo!r} desconhecido "
                                         f"({'/'.join(fotosite.TIPOS)})")
        cfg = ler_config()
        if tipo == "caixa":
            if not slot:
                raise fotocaixa.FotoInvalida("uma foto de caixa precisa do slot (`?slot=`)")
            caixas.caixa_do_cfg(cfg, slot)                 # KeyError → 409
        else:
            slot = None
        copy_id = None
        with db.session() as con:
            if copy_raw:
                try:
                    copy_id = int(copy_raw)
                except ValueError:
                    raise fotocaixa.FotoInvalida(f"cópia {copy_raw!r} não é um número") from None
                if not con.execute("SELECT 1 FROM copies WHERE id = ?", (copy_id,)).fetchone():
                    raise fotocaixa.FotoInvalida(f"a cópia #{copy_id} já não existe na base — "
                                                 f"recarrega a página")
            ficheiros = fotosite.ler_multipart(self.headers.get("Content-Type") or "", bruto)
            guardadas = fotosite.guardar(ROOT / "pendentes", tipo, ficheiros,
                                         slot=slot, copy_id=copy_id)
        # O índice passa já a contar a foto (o mtime de `pendentes/` também o
        # faria); o `esperadas.md` e as páginas vêm a seguir, em fundo.
        _CACHE.clear()
        regenerar_em_fundo("foto")
        nome = (loadout.nomes_das_caixas().get(slot) if slot
                else {"venda": "a venda", "rl": "a Caixa RL",
                      "coleccao": "a Colecção"}.get(tipo, tipo))
        n = len(guardadas)
        mb = sum(g["bytes"] for g in guardadas) / 1e6
        return {"ok": True, "tipo": tipo, "slot": slot, "copy_id": copy_id,
                "ficheiros": [g["nome"] for g in guardadas],
                "espera_s": fotosite.ESPERA_S,
                "msg": (f"📷 {n} foto{'s' if n != 1 else ''} ({mb:.1f} MB) em pendentes\\ para "
                        f"{nome}" + (f" · cópia #{copy_id}" if copy_id else "")
                        + f" — entra{'m' if n != 1 else ''} na corrida das 02:30 ou com "
                        f"«⚡ Processar agora» (a foto tem de ter mais de "
                        f"{fotosite.ESPERA_S // 60} min).")}

    def _revalidacao(self, dados):
        """«Fotografar esta caixa» / «Fotografar a venda…» / «parar» (2026-09-20).

        `act: "alvo"` escreve `revalidacao.alvo` no config (tipo + slot) e liga
        a campanha se ainda não estivesse (`desde` = hoje); `act: "parar"`
        tira o alvo. Depois regenera — é o `regenerar` que reescreve o
        `pendentes/esperadas.md` com as cópias por revalidar desse alvo. A
        resposta traz a instrução para o telemóvel.
        """
        from mtgvault import revalidacao                   # noqa: PLC0415
        act = dados.get("act")
        cfg = ler_config()
        if act == "parar":
            havia = revalidacao.limpar_alvo(cfg)
            escrever_config(cfg)
            sources._CFG_CACHE.clear()
            with db.session() as con:
                regenerar(con)
            return {"ok": True, "msg": ("Parei: já não há alvo de revalidação."
                                        if havia else "Não havia alvo para parar.")}
        if act != "alvo":
            return {"erro": f"acção {act!r} desconhecida (alvo|parar)"}
        tipo, slot = dados.get("tipo"), dados.get("slot") or None
        if tipo == "caixa" and slot and not any(
                s.get("slot") == slot for s in cfg.get("caixas") or []):
            raise KeyError(slot)
        a = revalidacao.definir_alvo(cfg, tipo, slot)      # ValueError → 409
        escrever_config(cfg)
        sources._CFG_CACHE.clear()
        with db.session() as con:
            regenerar(con)
            prog = revalidacao.progresso(con, loadout.report(con))
        nome = revalidacao.titulo(a)
        n = (prog["alvo"] or {}).get("por_revalidar", 0)
        return {"ok": True, "alvo": a, "nome": nome, "por_revalidar": n,
                "msg": (f"📷 A fotografar {nome}: {n} cópia{'s' if n != 1 else ''} "
                        f"por fotografar. Tira as fotos com «📷 Tirar fotos» (ou larga-as "
                        f"em pendentes\\) — entram na corrida das 02:30 ou com «⚡ Processar "
                        f"agora»; o esperadas.md já diz o que esperar.")}

    def _padrao(self, dados):
        """LISTA PADRÃO e RESERVA de uma caixa (André, 2026-09-20).

        `act`: `fixar` (texto + origem), `add` (nome, q, board), `tirar` (nome,
        board), `voltar`, `reserva-add` (nome), `reserva-tirar` (nome). Os
        nomes VALIDAM-SE no catálogo antes de se escrever (um nome mal escrito
        na lista era uma falta que nunca fechava e uma compra que não existe);
        o que se guarda é o nome oracle, a frente. Erros de regra → 409.
        """
        padrao = padrao_mod
        act, slot_id = dados.get("act"), dados.get("slot")
        nome = (dados.get("nome") or "").strip()
        cfg = ler_config()
        caixas.caixa_do_cfg(cfg, slot_id)                  # KeyError → 409
        with db.session() as con:
            def canon(n):
                c = padrao.nome_no_catalogo(con, n)
                if c is None:
                    raise ValueError(f"o catálogo não conhece {n!r} — confirma o "
                                     f"nome em inglês (oracle)")
                return c

            if act == "fixar":
                cards = padrao.parse_lista(dados.get("texto") or "")
                if not cards:
                    raise ValueError("a lista veio vazia")
                cards = [[b, canon(n), q] for b, n, q in cards]
                rec = padrao.fixar(cfg, slot_id, cards, dados.get("origem") or "")
                msg = (f'{caixas.caixa_do_cfg(cfg, slot_id).get("nome")}: lista padrão '
                       f'fixada em {rec["escolhido_em"]} — {len(rec["cards"])} linhas, '
                       f'{sum(c[2] for c in rec["cards"])} cartas')
            elif act == "add":
                nome = canon(nome)
                rec = padrao.acrescentar(cfg, slot_id, nome, int(dados.get("q") or 1),
                                         dados.get("board") or "main")
                msg = f'{nome} na lista padrão ({sum(c[2] for c in rec["cards"])} cartas)'
            elif act == "tirar":
                rec = padrao.tirar(cfg, slot_id, nome, board=dados.get("board") or None)
                msg = f'{nome} fora da lista padrão ({sum(c[2] for c in rec["cards"])} cartas)'
            elif act == "voltar":
                msg = padrao.voltar(cfg, slot_id)
            elif act == "reserva-add":
                nome = canon(nome)
                lista = padrao.reserva_add(cfg, slot_id, nome)
                msg = f"{nome} na reserva ({len(lista)} cartas reservadas)"
            elif act == "reserva-tirar":
                lista = padrao.reserva_tirar(cfg, slot_id, nome)
                msg = f"{nome} fora da reserva ({len(lista)} cartas reservadas)"
            else:
                return {"erro": f"acção {act!r} desconhecida"}
            escrever_config(cfg)
            sources._CFG_CACHE.clear()
            regenerar(con)
        return {"ok": True, "msg": msg}

    def _feira(self, dados):
        """As escritas da FEIRA (André, 2026-09-20), todas no config.

        `act`: `taxas` (dinheiro, troca — em % ou fracção), `filtro`
        (so_validadas), `levo`/`nao-levo` (chave da impressão), `wl-add`
        (nome, q, slot, lang, finish, max, notas), `wl-tirar` (nome, slot),
        `max` (nome, slot, q, max — fixa o preço máximo: cria/actualiza a
        entrada manual dessa carta e caixa), `vendor-add` (nome, cardmarket,
        site, notas), `vendor-tirar` (vendor), `pode-ter`/`pode-ter-nao`
        (nome, vendor). Os nomes de carta VALIDAM-SE no catálogo, como na
        lista padrão; erros de regra → 409.
        """
        act = dados.get("act")
        cfg = ler_config()
        with db.session() as con:
            def canon(n):
                c = padrao_mod.nome_no_catalogo(con, n or "")
                if c is None:
                    raise ValueError(f"o catálogo não conhece {n!r} — confirma o "
                                     f"nome em inglês (oracle)")
                return c

            if act == "taxas":
                f = feira.definir_taxas(cfg, dados.get("dinheiro"), dados.get("troca"))
                d, t = feira.taxas(cfg)
                msg = f"taxas: dinheiro {d:.0%} · troca {t:.0%} do Trend"
                del f
            elif act == "filtro":
                feira.definir_so_validadas(cfg, bool(dados.get("so_validadas")))
                msg = ("a levar só as cópias com foto desta campanha"
                       if dados.get("so_validadas") else "a levar tudo, com ou sem foto")
            elif act in ("levo", "nao-levo"):
                feira.marcar(cfg, dados.get("chave") or "", act == "levo")
                nm = (dados.get("chave") or "").split("|")[0]
                msg = f"{nm}: {'levo' if act == 'levo' else 'não levo'}"
            elif act in ("wl-add", "max"):
                nome = canon(dados.get("nome"))
                slot = dados.get("slot") or None
                if slot:
                    caixas.caixa_do_cfg(cfg, slot)          # KeyError → 409
                maximo = dados.get("max")
                if act == "max" and maximo in (None, ""):
                    # Tirar o máximo: se a entrada manual só existia por causa
                    # dele (linha automática), vai-se embora; senão fica sem max.
                    ent = next((e for e in feira.wantlist(cfg)
                                if feira._k(e["nome"], e["slot"]) == feira._k(nome, slot)), None)
                    if ent is None:
                        msg = f"{nome}: sem preço máximo"
                    else:
                        feira.wantlist_add(cfg, nome, ent["q"], ent["lang"], ent["finish"],
                                           None, slot, ent["notas"])
                        msg = f"{nome}: preço máximo tirado"
                else:
                    antiga = next((e for e in feira.wantlist(cfg)
                                   if feira._k(e["nome"], e["slot"]) == feira._k(nome, slot)), None)
                    ent = feira.wantlist_add(
                        cfg, nome, dados.get("q") or (antiga or {}).get("q") or 1,
                        dados.get("lang") or (antiga or {}).get("lang"),
                        dados.get("finish") or (antiga or {}).get("finish"),
                        maximo, slot,
                        dados.get("notas") if dados.get("notas") is not None
                        else (antiga or {}).get("notas") or "")
                    msg = (f"{ent['q']}× {nome} na wantlist"
                           + (f" (máx {ent['max']:.2f} €)" if ent.get("max") is not None else "")
                           + (f" para {caixas.caixa_do_cfg(cfg, slot).get('nome')}" if slot else ""))
            elif act == "wl-tirar":
                n = feira.wantlist_remover(cfg, dados.get("nome") or "", dados.get("slot") or None)
                msg = f"{dados.get('nome')} fora da wantlist ({n} entradas)"
            elif act == "vendor-add":
                v = feira.vendor_add(cfg, dados.get("nome") or "", dados.get("notas") or "",
                                     dados.get("cardmarket") or "", dados.get("site") or "")
                msg = f"vendor {v['nome']} acrescentado"
            elif act == "vendor-tirar":
                n = feira.vendor_remover(cfg, dados.get("vendor") or "")
                msg = f"vendor {dados.get('vendor')} tirado ({n} ficam)"
            elif act in ("pode-ter", "pode-ter-nao"):
                nome = canon(dados.get("nome"))
                lista = feira.pode_ter(cfg, nome, dados.get("vendor") or "", act == "pode-ter")
                msg = (f"{nome}: " + (", ".join(lista) + " pode ter" if lista
                                      else "sem vendor marcado"))
            else:
                return {"erro": f"acção {act!r} desconhecida"}
            escrever_config(cfg)
            sources._CFG_CACHE.clear()
            regenerar(con)
        return {"ok": True, "msg": msg}

    def _escolher(self, dados):
        """"Vou montar este" / "já não vou montar este", do `metagame.html`.

        E, desde 2026-09-08, as três acções do ranking de Premodern: abrir uma
        caixa nova a partir de uma sugestão (`pm-montar`), recusá-la
        (`pm-recusar` — as cartas dela libertam-se para a venda) e voltar atrás
        (`pm-aceitar`).
        """
        from mtgvault import premodern as pm             # noqa: PLC0415

        act, slot_id, aid = dados.get("act"), dados.get("slot"), dados.get("aid")
        nome = (dados.get("nome") or "").strip()
        # O `id` estável do arquétipo, que a página manda no botão. É a chave por
        # que a recusa e a escolha se guardam — o `nome` vai a par só para ele
        # reconhecer a linha quando abrir o config à mão.
        ident = (dados.get("id") or "").strip() or None
        cfg = ler_config()
        with db.session() as con:
            if act == "escolher":
                if not aid:
                    return {"erro": "sem arquétipo"}
                # FORMATO DECIDIDO (André, 2026-09-21: *"Pioneer apenas
                # Greasefang e jeskai control"*): a página já não desenha o
                # botão, mas uma página aberta no telemóvel antes de hoje ainda
                # o tem — e escolher um top-N para uma caixa do Pioneer era
                # desfazer a decisão dele sem ninguém dar por isso.
                try:
                    fmt = (_slot_do_cfg(cfg, slot_id).get("formato") or "").lower()
                except KeyError:
                    return {"erro": f"caixa {slot_id!r} desconhecida"}
                if fmt in metagame.formatos_decididos():
                    return {"erro": f"o {fmt} está decidido (colecao_config.json → "
                                    f"formatos_decididos): não há top-N para escolher"}
                msg = escolher_lista(con, cfg, slot_id, int(aid))
            elif act == "desmarcar":
                msg = desmarcar_lista(cfg, slot_id)
            elif act in ("pm-montar", "pm-recusar", "pm-aceitar"):
                if not nome:
                    return {"erro": "sem arquétipo"}
                if act == "pm-montar":
                    if not aid:
                        return {"erro": "sem arquétipo"}
                    msg = montar_sugestao(con, cfg, nome, int(aid), ident)
                elif act == "pm-recusar":
                    msg = pm.recusar(cfg, nome, ident=ident)
                else:
                    msg = pm.aceitar(cfg, nome, ident)
            else:
                return {"erro": f"acção {act!r} desconhecida"}
            escrever_config(cfg)
            sources._CFG_CACHE.clear()
            regenerar(con)
        return {"ok": True, "msg": msg}

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------------------
# Arranque (o mesmo do riftvault: URL da rede local + QR)
# ---------------------------------------------------------------------------
def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def lan_ips() -> list[str]:
    """TODOS os endereços locais, o da rota por omissão primeiro.

    Mostrar só um engana quando a máquina tem Ethernet e Wi-Fi em sub-redes
    diferentes: o `lan_ip()` devolve o da Ethernet, mas o telemóvel está no
    Wi-Fi e não chega lá. É a mesma nota (e o mesmo código) do riftvault, onde o
    caso aconteceu a sério.
    """
    principal = lan_ip()
    todos = {principal}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            todos.add(info[4][0])
    except OSError:
        pass
    cmd = (["ipconfig"] if sys.platform == "win32"
           else ["ip", "-4", "-o", "addr", "show"])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                             errors="replace").stdout
        for m in re.finditer(r"(\d{1,3}(?:\.\d{1,3}){3})", out):
            todos.add(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass

    def util(ip: str) -> bool:
        p = ip.split(".")
        if p[0] == "127" or ip.startswith("169.254.") or p[-1] in ("0", "255"):
            return False
        return (p[0] == "10" or (p[0] == "172" and 16 <= int(p[1]) <= 31)
                or (p[0] == "192" and p[1] == "168"))

    return [principal] + sorted(x for x in todos if x != principal and util(x))


def ligacao_local(port: int | None = None) -> dict:
    """O link de escrita da rede local: `{url, ip, ips, porto, token}`.

    É o que vai no QR e o que a página mostra. O token vai no URL de propósito:
    escrever 32 dígitos hexadecimais num teclado de telemóvel é o atrito que faz
    não se usar a ferramenta.
    """
    p = port or int(os.environ.get("MTGVAULT_PORT") or PORT)
    ips = lan_ips()
    t = token()
    return {"ip": ips[0], "ips": ips, "porto": p, "token": t,
            "url": f"http://{ips[0]}:{p}/?t={t}"}


def url_edicao(port: int | None = None) -> str:
    return ligacao_local(port)["url"]


def qr_ascii(url: str) -> str:
    """O QR na consola. O nosso desenhador (`mtgvault.qr`) primeiro; a biblioteca
    `qrcode`, se estiver instalada, fica como alternativa para o caso de a
    consola não conseguir com os blocos de meia-altura."""
    try:
        arte = qr.ascii_arte(url)
        arte.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return arte
    except (UnicodeEncodeError, LookupError, ValueError):
        pass
    try:
        import qrcode                                   # noqa: PLC0415
        q = qrcode.QRCode(border=2)
        q.add_data(url)
        q.make(fit=True)
        buf = io.StringIO()
        q.print_ascii(out=buf, invert=True)
        out = buf.getvalue()
        out.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
        return out
    except Exception:                                   # noqa: BLE001
        return "  (a consola não mostra o QR; abre /qr.svg no browser)"


def regra_firewall(port: int) -> str:
    """O comando que abre o porto na rede PRIVADA do Windows.

    Não se corre sozinho: `netsh advfirewall` precisa de consola elevada, e um
    programa que abre portos na primeira execução sem avisar não é um programa
    de confiança. Imprime-se para ele copiar uma vez.
    """
    return (f'netsh advfirewall firewall add rule name="mtgvault {port}" '
            f'dir=in action=allow protocol=TCP localport={port} profile=private')


def main(port: int = PORT, host: str | None = None):
    host = host or BIND
    lig = ligacao_local(port)
    aberto = host not in ("127.0.0.1", "localhost", "::1")
    print("=" * 62)
    print("  mtgvault — MODO EDIÇÃO (escreve no colecao_config.json e no vault.db)")
    print("=" * 62)
    print(f"  Neste PC:          http://localhost:{port}/")
    if aberto:
        print(f"  Telemóvel (casa):  {lig['url']}")
        for extra in lig["ips"][1:]:
            print(f"     ou:             http://{extra}:{port}/?t={lig['token']}")
        if len(lig["ips"]) > 1:
            print("     (redes diferentes — usa a que o telemóvel alcança)")
    else:
        print("  Telemóvel:         DESLIGADO — corre com MTGVAULT_BIND=0.0.0.0")
    print(f"\n  Porto {port} — o 8770 é do riftvault, não lhe toques.\n")
    if aberto:
        print(qr_ascii(lig["url"]))
        print(f"  Token em {ficheiro_token()} (apaga-o para gerar outro).")
        print("  Sem o ?t= do link, a página é só de leitura.")
        print("  Se o telemóvel não chegar, abre o porto na rede privada:")
        print("    " + regra_firewall(port))
    print("  Não abras este porto no router.  Ctrl+C para parar.")
    print("=" * 62)
    srv = ThreadingHTTPServer((host, port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main(int(os.environ.get("MTGVAULT_PORT") or PORT))
