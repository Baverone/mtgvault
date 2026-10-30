"""PUBLICAR O SITE SEM ESPERAR PELAS 03:30 (2026-10-04).

O furo que isto fecha, e não é cosmético: o André edita a colecção no **modo
edição** (`webapp.py`, porto 8771) — marca cartas com o `+`/`−` da aba Decks,
arruma uma caixa, diz que já tem uma carta. O `webapp.regenerar` reescreve as
páginas em disco **no instante** em que ele carrega no botão… e **ninguém as
commita**. Ficam na árvore de trabalho até à corrida do `mtgvault-daily` das
03:30, por isso <https://mtg.baverone.com/> podia estar **até um dia inteiro**
atrasado em relação ao que ele acabou de marcar.

É exactamente a avaria de 08/09/2026 no riftvault — *"129 alterações ficaram no
PC o dia inteiro"* —, que lá foi fechada com a tarefa `riftvault-publicar` e
**nunca foi fechada aqui**: a 04/10/2026 havia `riftvault-publicar` e
`baiakvault-publicar` de 30 em 30 minutos, e nenhuma `mtgvault-publicar`.

O QUE ISTO FAZ

  `estado(con)` gera as páginas para uma pasta de PROVA, compara-as com as que
  estão em disco **ignorando o carimbo de geração**, e diz o que mudou de
  verdade. `publicar(con)` escreve-as (só se mudou) e devolve a lista de
  caminhos a commitar. Quem commita e faz o push é a tarefa `mtgvault-publicar`
  do ai-pc — este módulo não toca no git nem na colecção.

PORQUE É QUE A COMPARAÇÃO IGNORA O CARIMBO

  Medido a 04/10/2026 (`_revisao/medir_estabilidade.py`): duas passagens
  seguidas sobre a MESMA base dão **todo o HTML byte a byte igual** e **7
  ficheiros de índice diferentes — só no `_gerado_em`**. Sem a normalização, o
  relógio sozinho dava um commit e uma build do Pages **a cada meia hora, para
  sempre**. É a mesma razão do `--se-mudou` do riftvault.

AS DUAS DIFERENÇAS FACE AO RIFTVAULT, e as duas são deliberadas

  1. **O `data/vault.db` NÃO se commita.** No riftvault a base vai no Git; aqui
     está no `.gitignore` desde 2026-08 e vive no Release `data` (são **99,5
     MB** — medidos). Commitá-la de 30 em 30 minutos era empurrar ~5 GB por dia
     para o repositório. O que faz o site publicado mostrar as marcas dele são
     as PÁGINAS, e são essas que vão. Quem republica a base no Release continua
     a ser o `mtgvault-daily` das 03:30.
  2. **Gera-se tudo, não só o que ele tocou.** São 13 páginas em ~22 s (medido),
     e todas lêem a colecção por algum caminho. Escolher um subconjunto era
     assinar a lista das que «não dependem da colecção» — e a primeira que
     dependesse ficava desactualizada em silêncio, que é o padrão do
     `event_tier`. Gerar tudo e comparar é auto-corrigível: o que não mudou não
     se escreve.

A LISTA DAS PÁGINAS É A MESMA DO `daily.yml`, de propósito. Uma segunda lista
ao lado era a segunda oportunidade de discordarem — foi assim que o
`deckboxes.html` esteve semanas sem ser publicado. O teste
`test_publicar.caso_a_lista_e_a_mesma_do_daily` lê o workflow e exige que
batam.

O INTERRUPTOR DO NÚCLEO (2026-10-28). Com `nucleo.ligado` o site é o do núcleo
novo — Painel, Decks e Vender (`PAGINAS_NUCLEO`) — e é essa a lista do
`daily.yml`. Sem ele volta a das catorze (`PAGINAS_ANTIGAS`). Quem pergunta é o
`paginas()`/`publicaveis()`, à chamada; os nomes `PAGINAS`/`PUBLICAVEIS`
continuam a ler-se do módulo e dão a resposta de hoje.
"""
from __future__ import annotations

import importlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (módulo, ficheiro, precisa do `rep`). A ordem é a do `daily.py`: o que é mais
# barato primeiro, para um erro aparecer depressa. São as páginas do site
# ANTIGO: valem com o `nucleo.ligado` desligado (ver `paginas()`).
PAGINAS_ANTIGAS: list[tuple[str, str, bool]] = [
    ("inicio", "index.html", True),
    ("decks", "decks.html", False),
    ("deckboxes", "deckboxes.html", True),
    ("arrumacao", "arrumacao.html", True),
    # A LISTA DE FALTAS (2026-10-05): *"preciso tambem da lista de faltas desses
    # decks para poder procurar em Ghent"*. Leva o `rep` pela razão das outras
    # três: as faltas são o `comprar` da alocação, e um segundo relatório dava um
    # número diferente do que a aba Comprar mostra.
    ("faltas", "faltas.html", True),
    ("meusdecks", "meusdecks.html", False),
    ("caixarl", "caixarl.html", False),
    ("showcase", "showcase.html", False),
    ("meta_coverage", "cobertura.html", False),
    ("colecao_cor", "colecao_cor.html", False),
    ("collection_gallery", "colecao.html", False),
    ("comandantes", "comandantes.html", False),
    ("metagame", "metagame.html", False),
    ("reservedlist", "reservedlist.html", False),
]

# O SITE DO NÚCLEO (2026-10-28): com `nucleo.ligado`, publica-se isto e mais
# nada — Painel, Decks, Coleção e Vender (a Coleção entrou a 2026-10-30). Nenhuma das quatro lê o `loadout.report`, e por
# isso o `gerar` deixa de o calcular. Os geradores antigos ficam no disco e
# importáveis; só deixam de ser chamados.
PAGINAS_NUCLEO: list[tuple[str, str, bool]] = [
    ("nucleo_painel", "index.html", False),
    ("nucleo_decks", "deck.html", False),
    ("nucleo_colecoes", "colecoes.html", False),
    ("nucleo_vender", "vender.html", False),
]

# Os RECORTES das fotos das cartas dele (2026-10-30): `assets/cartas/<foto>-<n>.jpg`,
# escritos pela CLI do núcleo (não pelo `publicar`) e mostrados pela Coleção. Têm
# de ir no Git junto com a página, ou o site publicado mostra imagens partidas.
PASTA_RECORTES = "assets/cartas"

# O que a tarefa pode commitar. Mais nada: o código é dele (e do Claude, noutro
# ramo), e um `git add -A` de 30 em 30 minutos acabava por levar trabalho a meio
# para o `main`.
PUBLICAVEIS_ANTIGOS: list[str] = [f for _m, f, _r in PAGINAS_ANTIGAS] + [
    "deckboxes.js",
    # O JavaScript da aba Decks saiu da casca a 2026-10-05, pelo mesmo caminho
    # do `deckboxes.js` (ver `decks.NOME_JS`). Sem ele aqui, a casca publicada
    # aponta para um ficheiro que o commit não leva e a página abre vazia.
    "decks.js",
    "data/paginas",
]


def _ligado() -> bool:
    """O `nucleo.ligado`, lido À CHAMADA: o `webapp` e os testes importam este
    módulo antes de o config mudar."""
    from .nucleo import modelo                                 # noqa: PLC0415
    return modelo.ligado()


def paginas() -> list[tuple[str, str, bool]]:
    """As páginas que se geram e publicam HOJE: as do núcleo com o
    `nucleo.ligado`, as antigas sem ele. É a MESMA lista do `git add` do
    `daily.yml` com o núcleo ligado (o `test_publicar` confere-o)."""
    return list(PAGINAS_NUCLEO if _ligado() else PAGINAS_ANTIGAS)


def publicaveis() -> list[str]:
    """O que a tarefa `mtgvault-publicar` pode commitar HOJE. Com o núcleo são
    as quatro páginas e a pasta dos recortes (que o `publicar` não gera: é
    escrita pela CLI das fotos, e só é commitada aqui); o `data/paginas` e os
    `.js` são das páginas antigas."""
    if _ligado():
        return [f for _m, f, _r in PAGINAS_NUCLEO] + [PASTA_RECORTES]
    return list(PUBLICAVEIS_ANTIGOS)


def __getattr__(nome: str):
    # `PAGINAS` e `PUBLICAVEIS` eram listas fixas do módulo; passaram a
    # depender do interruptor e calculam-se a cada leitura. Os nomes continuam
    # a valer para quem os lia (o `run.py` da tarefa, os testes).
    if nome == "PAGINAS":
        return paginas()
    if nome == "PUBLICAVEIS":
        return publicaveis()
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")

# PUBLICAR NÃO ESCREVE NA COLECÇÃO (medido, não assumido). Dos treze
# geradores, **um** escrevia: a Galeria grava o ponto do dia no `value_history`
# (`INSERT OR REPLACE`, 8 272 bytes no `-wal`, medido em
# `_revisao/medir_quem_escreve.py`). Isso fazia esta tarefa mexer no mtime do
# `vault.db` — e como o SOSSEGO dela é *"o `vault.db` foi escrito há menos de 10
# min?"*, ela envenenava-se a si própria: publicava uma vez e depois dizia «ele
# está a editar» para sempre, sem uma única carta ter mudado. O ponto do dia é
# do `daily`, não de quem desenha a página 48 vezes por dia.
#
# A primeira medição disto deu «ninguém escreve» e era FALSA: segurava uma
# ligação aberta durante os treze builds, e em WAL a escrita só chega ao
# ficheiro principal quando a última ligação fecha. O que denuncia a escrita é o
# `-wal` a crescer.
SO_LEITURA: dict[str, dict] = {"collection_gallery": {"historico": False}}

# O carimbo que o `paginas.escrever_dados` põe em cada índice. É ruído do
# relógio: muda a cada geração sem uma única carta ter mudado.
RX_CARIMBO = re.compile(r'"_gerado_em"\s*:\s*"[^"]*"')
CARIMBO_NEUTRO = '"_gerado_em":"-"'


def normalizar(rel: str, texto: str) -> str:
    """O texto de um ficheiro sem o que o relógio sozinho muda.

    Só os `.json` levam carimbo; o HTML é determinista (medido). Normalizar o
    HTML às cegas era arriscar esconder uma mudança a sério.
    """
    if rel.endswith(".json"):
        return RX_CARIMBO.sub(CARIMBO_NEUTRO, texto)
    return texto


def _ler(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def gerar(con, destino: Path, rep=None) -> list[str]:
    """Gera as páginas para `destino`. Devolve os nomes dos ficheiros escritos.

    O `rep` (o `loadout.report`) calcula-se UMA vez e passa-se às quatro páginas
    que o pedem — é a decisão de 2026-09-24 (*"dois relatórios eram duas
    respostas à mesma pergunta"*).
    """
    destino.mkdir(parents=True, exist_ok=True)
    lista = paginas()
    # Só se calcula quando alguma página o pede: as do núcleo não o pedem, e o
    # relatório do loadout antigo custa segundos e lê as tabelas antigas.
    if rep is None and any(precisa for _m, _f, precisa in lista):
        from . import loadout                                 # noqa: PLC0415
        rep = loadout.report(con)
    feitos = []
    for mod, ficheiro, precisa in lista:
        m = importlib.import_module(mod)
        kw = dict(SO_LEITURA.get(mod, {}))
        if precisa:
            m.build(con, destino / ficheiro, rep=rep, **kw)
        else:
            m.build(con, destino / ficheiro, **kw)
        feitos.append(ficheiro)
    return feitos


def _ficheiros(base: Path) -> set[str]:
    """Os caminhos relativos (posix) de tudo o que interessa debaixo de `base`."""
    out = set()
    for p in base.rglob("*"):
        if p.is_file() and not p.name.endswith(".tmp"):
            out.add(p.relative_to(base).as_posix())
    return out


def comparar(prova: Path, real: Path) -> dict:
    """O que mudou DE VERDADE entre a pasta de prova e o site em disco.

    Devolve `{"mudaram": [...], "novos": [...], "a_mais": [...]}`. Os `a_mais`
    são ficheiros que existem em disco e a geração já não produz — uma parte de
    uma caixa que saiu do config não pode ficar a responder para sempre.
    """
    fp, fr = _ficheiros(prova), _ficheiros(real)
    mudaram, novos = [], []
    for rel in sorted(fp):
        tp = _ler(prova / rel)
        tr = _ler(real / rel) if (real / rel).exists() else None
        if tr is None:
            novos.append(rel)
        elif normalizar(rel, tp or "") != normalizar(rel, tr):
            mudaram.append(rel)
    # Só se conta «a mais» o que está DENTRO do que esta geração cobre: a pasta
    # `data/paginas` tem partes de todas as páginas, e `rglob` do site inteiro
    # trazia o repositório todo.
    a_mais = sorted(r for r in (fr - fp) if r.startswith("data/paginas/"))
    return {"mudaram": mudaram, "novos": novos, "a_mais": a_mais}


def _prova_de(raiz: Path) -> Path:
    return raiz / "_prova-publicar"


def estado(con, raiz: Path | None = None, rep=None) -> dict:
    """Gera para a pasta de prova e diz o que mudaria. **Não escreve no site.**"""
    raiz = Path(raiz) if raiz else ROOT
    prova = _prova_de(raiz)
    if prova.exists():
        shutil.rmtree(prova, ignore_errors=True)
    gerar(con, prova, rep=rep)
    dif = comparar(prova, raiz)
    # Com o núcleo ligado o `data/paginas` já não se publica (`publicaveis()`):
    # as partes antigas que lá ficaram não são «a mais» — senão cada passagem
    # dava «mudou» para sempre, e não há nada a commitar por causa delas.
    if "data/paginas" not in publicaveis():
        dif["a_mais"] = []
    dif["prova"] = str(prova)
    dif["mudou"] = bool(dif["mudaram"] or dif["novos"] or dif["a_mais"])
    return dif


def publicar(con, raiz: Path | None = None, *, se_mudou: bool = True,
             rep=None) -> dict:
    """Põe o site em dia no disco. Devolve o relatório para a tarefa commitar.

    Com `se_mudou` (a omissão), gera primeiro para a pasta de prova e **só
    escreve no site se houver uma diferença que não seja o carimbo**. É isso que
    impede um commit por relógio a cada meia hora.
    """
    raiz = Path(raiz) if raiz else ROOT
    r = {"at": datetime.now().replace(microsecond=0).isoformat(sep=" "),
         "escreveu": False, "mudaram": [], "novos": [], "a_mais": [],
         "paginas": len(paginas()), "publicaveis": publicaveis()}

    if se_mudou:
        dif = estado(con, raiz, rep=rep)
        r["mudaram"], r["novos"], r["a_mais"] = (dif["mudaram"], dif["novos"],
                                                 dif["a_mais"])
        shutil.rmtree(_prova_de(raiz), ignore_errors=True)
        if not dif["mudou"]:
            r["detalhe"] = ("o site em disco já diz o mesmo que a base — só o "
                            "carimbo de geração mudava, e isso não é um commit")
            return r
    # Para valer, e no sítio a sério.
    gerar(con, raiz, rep=rep)
    r["escreveu"] = True
    r["detalhe"] = (f"{len(r['mudaram'])} ficheiros mudaram, "
                    f"{len(r['novos'])} novos, {len(r['a_mais'])} a mais"
                    if se_mudou else f"{len(paginas())} páginas geradas")
    return r


def abrir(path=None, catalog=None, *, a_serio: bool = False):
    """A ligação com que se publica: SÓ LEITURA (2026-10-25).

    Era o `db.session()`, que corre o `init` (CREATE/INSERT/UPDATE) e, ao
    fechar, despeja o `-wal` no `vault.db` — e o mtime do `vault.db` é o
    sossego da tarefa `mtgvault-publicar`. Ver `db.ler`.
    """
    from . import db                                           # noqa: PLC0415
    return db.ler(path, catalog, a_serio=a_serio)


class BasePorMigrar(RuntimeError):
    """O núcleo está ligado e o `vault.db` ainda não tem as tabelas `n_*`."""


# (R21, 2026-10-30) O que as páginas do núcleo LEEM e só o `_migrate` cria. Não
# basta o `n_deck`: uma base do núcleo de 28/10 já o tem e não tem as tabelas da
# Coleção e fotos, e no dia do merge a tarefa `mtgvault-publicar` (30 em 30 min,
# só de leitura) rebentava com «no such table: n_colecao_carta» até o webapp ou
# o daily a migrarem. Uma tabela nova que uma página leia entra aqui.
TABELAS_DO_NUCLEO = ("n_deck", "n_colecao", "n_colecao_carta", "n_validacao",
                     "n_preco_pt", "n_preco_vigiado", "n_jogada")
COLUNAS_DO_NUCLEO = (("n_valor", "colecoes_eur"),)


def exige_base_do_nucleo(con) -> None:
    """(I4, 2026-10-29) Com o `nucleo.ligado`, a base tem de ter as tabelas do
    núcleo. O `publicar` abre-a SÓ DE LEITURA (não corre o `db.init`, que é
    quem as cria): no primeiro dia, com o `vault.db` a sério ainda por migrar,
    as três páginas rebentavam com «no such table» num traceback no log da
    tarefa. Quem migra é o arranque do webapp ou o daily."""
    if not _ligado():
        return
    tem = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    faltam = [t for t in TABELAS_DO_NUCLEO if t not in tem]
    for tabela, coluna in COLUNAS_DO_NUCLEO:
        if tabela in tem and coluna not in {
                r[1] for r in con.execute(f"PRAGMA table_info({tabela})")}:
            faltam.append(f"{tabela}.{coluna}")
        elif tabela not in tem:
            faltam.append(tabela)
    if faltam:
        raise BasePorMigrar("base por migrar: corre o webapp ou o daily uma vez"
                            " (o núcleo está ligado e o vault.db ainda não tem as"
                            " tabelas n_*: falta " + ", ".join(faltam) + ")")


def main(argv=None) -> int:
    """`py -m mtgvault.publicar [--ver|--se-mudou|--sempre]`."""
    import argparse                                           # noqa: PLC0415

    ap = argparse.ArgumentParser(description="Põe o site em dia e diz o que mudou.")
    ap.add_argument("--ver", action="store_true",
                    help="só diz o que mudaria; não escreve no site")
    ap.add_argument("--sempre", action="store_true",
                    help="escreve mesmo que nada tenha mudado (não usar na tarefa)")
    a = ap.parse_args(argv)
    import sys                                                # noqa: PLC0415
    with abrir() as con:
        try:
            exige_base_do_nucleo(con)
        except BasePorMigrar as e:
            print(f"mtgvault.publicar: {e}", file=sys.stderr)
            return 2
        r = estado(con) if a.ver else publicar(con, se_mudou=not a.sempre)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
