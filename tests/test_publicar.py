"""PUBLICAR O SITE SEM ESPERAR PELAS 03:30 (André, 2026-10-04).

O furo que isto fecha: o `webapp.regenerar` reescreve as páginas em disco a
cada botão do modo edição e **ninguém as commitava** até à corrida das 03:30 —
por isso <https://mtg.baverone.com/> podia estar até um dia inteiro atrasado em
relação ao que ele acabou de marcar com o `+`/`−` da aba Decks. É a avaria de
08/09/2026 no riftvault, que lá foi fechada com o `riftvault-publicar` e aqui
nunca tinha sido.

Os casos trancam as três propriedades sem as quais a tarefa não serve:

  1. **o relógio sozinho não é um commit** — duas passagens seguidas sobre a
     mesma base não podem dar diferença. Sem isto, a tarefa de 30 em 30 minutos
     dava um commit e uma build do Pages **para sempre**;
  2. **publicar não escreve na colecção** — *"não escreve na colecção, só a
     publica"*. E não é higiene: o sossego da tarefa é «o `vault.db` foi escrito
     há menos de 10 min?», por isso uma escrita dela envenenava-a a si própria
     (publicava uma vez e dizia «ele está a editar» para sempre);
  3. **a lista de páginas é a MESMA do `daily.yml`** — duas listas era a segunda
     oportunidade de discordarem, e foi assim que o `deckboxes.html` esteve
     semanas sem ser publicado.
"""
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from mtgvault import db, publicar  # noqa: E402


def caso_o_carimbo_sozinho_nao_e_uma_diferenca():
    """Duas gerações seguidas da MESMA base só diferem no `_gerado_em`.

    Medido a 2026-10-04 (`_revisao/medir_estabilidade.py`): todo o HTML fica
    byte a byte igual e **7 ficheiros de índice** mudam — só no carimbo. É por
    isso que a comparação o normaliza.
    """
    a = '{"x":1,"_gerado_em":"2026-10-04T21:37:36","_partes":["p"]}'
    b = '{"x":1,"_gerado_em":"2026-10-04T23:59:01","_partes":["p"]}'
    assert publicar.normalizar("d.json", a) == publicar.normalizar("d.json", b)
    # e uma diferença A SÉRIO continua a ser uma diferença
    c = '{"x":2,"_gerado_em":"2026-10-04T21:37:36","_partes":["p"]}'
    assert publicar.normalizar("d.json", a) != publicar.normalizar("d.json", c)
    # no HTML não se normaliza nada: é determinista, e normalizá-lo às cegas
    # era arriscar esconder uma mudança a sério.
    assert publicar.normalizar("p.html", a) == a
    print("o carimbo de geracao sozinho nao conta como mudanca")


def caso_duas_passagens_seguidas_nao_dao_mudanca():
    """Ponta a ponta na base a sério: gerar duas vezes não produz diferença.

    É a asserção que impede o commit por relógio. Corre o `estado()` duas vezes
    seguidas sobre a mesma base; a segunda tem de dizer «nada mudou», porque a
    primeira acabou de pôr o site em dia.
    """
    with db.session() as con:
        rep = None
        primeiro = publicar.estado(con, RAIZ, rep=rep)
        if primeiro["mudou"]:
            # o site estava atrasado: põe-se em dia primeiro (é o que a tarefa
            # faz) e mede-se a seguir
            publicar.publicar(con, RAIZ, se_mudou=False)
        segundo = publicar.estado(con, RAIZ)
    assert not segundo["mudou"], (
        "duas passagens seguidas deram diferenca — a tarefa de 30 em 30 min "
        "vai commitar para sempre", segundo["mudaram"][:8], segundo["novos"][:8])
    print("duas geracoes seguidas da mesma base nao dao diferenca nenhuma")


def caso_publicar_nao_escreve_na_coleccao():
    """A Galeria era o ÚNICO dos treze geradores a escrever (o ponto do dia no
    `value_history`). O `publicar` chama-a com `historico=False`.

    Mede-se pelo `-wal` a crescer, que é o que denuncia uma escrita em modo WAL
    — o mtime do `vault.db` só muda quando a última ligação fecha, e por isso
    uma medição com a ligação aberta dava um falso «ninguém escreve».
    """
    assert publicar.SO_LEITURA.get("collection_gallery") == {"historico": False}, (
        "a Galeria deixou de ser chamada em modo so-leitura")
    base = Path(db.DEFAULT_DB)
    wal = base.with_name(base.name + "-wal")

    def tam():
        try:
            return wal.stat().st_size
        except OSError:
            return 0

    with tempfile.TemporaryDirectory() as tmp:
        with db.session() as con:
            antes = tam()
            publicar.gerar(con, Path(tmp))
            depois = tam()
    assert depois <= antes, (
        f"o publicar.gerar escreveu na base (-wal {antes} -> {depois})")
    print("publicar.gerar nao escreve uma linha na coleccao")


def caso_a_galeria_do_daily_continua_a_gravar_o_historico():
    """O outro lado: o ponto do dia não se perdeu, só mudou de dono.

    Quem o grava é o `daily`; se a Galeria deixasse de o gravar com
    `historico=True`, o gráfico da evolução do valor parava sem ninguém dar por
    isso — o padrão do `event_tier`.
    """
    import collection_gallery                                  # noqa: PLC0415
    import inspect                                             # noqa: PLC0415
    sig = inspect.signature(collection_gallery.build)
    assert sig.parameters["historico"].default is True, (
        "a omissao da Galeria tem de continuar a GRAVAR — o daily conta com ela")
    src = inspect.getsource(collection_gallery.build)
    assert "_record_value" in src and "if historico:" in src, src[:300]
    print("a Galeria do daily continua a gravar o ponto do dia")


def caso_a_lista_e_a_mesma_do_daily():
    """As páginas que o `publicar` gera são as que o `daily.yml` publica.

    Duas listas ao lado era a segunda oportunidade de discordarem — e foi assim
    que o `deckboxes.html` esteve semanas só numa delas e nunca era publicado.
    """
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    linha = next(l for l in yml.splitlines() if l.strip().startswith("git add "))
    do_yml = set(re.findall(r"[a-z_]+\.html", linha))
    do_publicar = {f for _m, f, _r in publicar.PAGINAS}
    assert do_publicar == do_yml, (
        "a lista do publicar e a do daily.yml discordam",
        {"so no publicar": sorted(do_publicar - do_yml),
         "so no yml": sorted(do_yml - do_publicar)})
    # e os publicáveis levam também o que não é HTML mas o site precisa
    assert "deckboxes.js" in publicar.PUBLICAVEIS
    assert "data/paginas" in publicar.PUBLICAVEIS
    print(f"as {len(do_publicar)} paginas do publicar sao as do git add do daily")


def caso_o_vault_db_nao_entra_nos_publicaveis():
    """A diferença deliberada face ao riftvault: a base **não** se commita.

    Está no `.gitignore` desde 2026-08 e vive no Release `data` — são 99,5 MB, e
    commitá-la de 30 em 30 minutos era empurrar ~5 GB por dia para o
    repositório. Quem a republica é o `mtgvault-daily` das 03:30.
    """
    for p in publicar.PUBLICAVEIS:
        assert "vault.db" not in p, (p, "a base nao se publica no Git")
    ignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert "data/vault.db" in ignore, (
        "o vault.db saiu do .gitignore — reve esta decisao antes de a mudar")
    print("o vault.db fica fora do Git, como esta desde 2026-08")


def caso_as_partes_que_sobram_sao_denunciadas():
    """Uma parte de uma caixa que saiu do config não pode ficar a responder
    para sempre — o `escrever_dados` apaga-a, e a comparação dá por ela."""
    with tempfile.TemporaryDirectory() as tmp:
        prova, real = Path(tmp) / "p", Path(tmp) / "r"
        for d in (prova, real):
            (d / "data" / "paginas" / "deckboxes").mkdir(parents=True)
        (prova / "index.html").write_text("a", encoding="utf-8")
        (real / "index.html").write_text("a", encoding="utf-8")
        # uma parte que a geração já não produz
        (real / "data" / "paginas" / "deckboxes" / "caixa-velha.json").write_text(
            "{}", encoding="utf-8")
        d = publicar.comparar(prova, real)
        assert d["a_mais"] == ["data/paginas/deckboxes/caixa-velha.json"], d
        assert not d["mudaram"] and not d["novos"], d
    print("uma parte que deixou de existir aparece em «a mais»")


def caso_o_json_da_tarefa_tem_o_que_ela_precisa():
    """O `run.py` do ai-pc lê a lista de publicáveis DESTE módulo, para não
    haver uma terceira lista escrita à mão numa tarefa."""
    with db.session() as con:
        r = publicar.publicar(con, RAIZ, se_mudou=True)
    for k in ("escreveu", "mudaram", "novos", "a_mais", "paginas", "publicaveis"):
        assert k in r, (k, sorted(r))
    assert r["paginas"] == len(publicar.PAGINAS)
    assert json.dumps(r)                       # tem de ser serializável
    print("o relatorio do publicar traz o que a tarefa do ai-pc precisa")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for c in CASOS:
        c()
    print("\nTUDO OK")
