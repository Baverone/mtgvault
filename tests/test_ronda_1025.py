"""Os quatro defeitos da ronda de 2026-10-25 (só bugs).

  1. **o `daily` podava DEPOIS de gerar as páginas** — a 24/10 apagou 190
     decklists que já tinha publicado, e o `mtgvault-publicar` das 04:xx vinha
     acertar o site todos os dias. As podas passam a correr antes da primeira
     página, e depois da `vigia-cartas` (que é quem diz que liga não se apaga);
  2. **partir um lote perdia o estado e o verso** — o `reserve_for_deck` e o
     `marcar_nao_encontradas` tinham o INSERT à mão, e a metade nova nascia sem
     `condition_origem`/`condition_em`/`condition_motivos`/`verso_path`/
     `validado_em`. Hoje passam os dois pelo `collection.nova_metade`;
  3. **o `publicar` abria a base em escrita** — `db.session()` corre o `init` e,
     ao fechar, despeja o `-wal` no `vault.db`; o mtime mudou a meio do publicar
     das 04:15 de 24/10 e a tarefa ficou vermelha. Agora é `mode=ro` sem `init`,
     e o daily faz o checkpoint ele próprio no fim;
  4. **a percentagem da Galeria ficava «sem variação» para sempre** — o primeiro
     ponto depois do esvaziamento vale 0 €, e era essa a base.

Cada caso foi corrido contra o `main` de 25/10 e chumba lá. Não toca na rede nem
nas bases do André: tudo em pastas temporárias.
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil", "dedicado": False},
    ],
    "caixas": [
        {"slot": "cedh", "nome": "Cloud cEDH", "formato": "cedh",
         "fonte": "deck", "ref": "CLOUD", "balde": "Colecção",
         "estado": "permanente", "prioridade": 1},
    ],
}
(_TMP / "cfg.json").write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")          # ver tests/_bateria.py
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

from mtgvault import collection, db, loadout, publicar  # noqa: E402

import collection_gallery as cg  # noqa: E402

# O estado que uma foto deixa numa cópia, e que a metade nova tem de levar.
ESTADO = {"condition": "EX", "condition_origem": "foto",
          "condition_em": "2026-10-20", "condition_motivos": "canto gasto",
          "verso_path": "pendentes/verso.jpg", "validado_em": "2026-10-20"}


def _base(d: Path):
    cm = db.session(d / "v.db", d / "c.db")
    con = cm.__enter__()
    con.execute(
        """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
           set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, legalities, digital, reserved)
           VALUES ('id-0','or-0','Chromatic Star','5dn','5DN set','1','en','rare',
                   'Artifact',1,'','["nonfoil"]','2004-06-04',?,0,0)""",
        (json.dumps({"cedh": "legal"}),))
    con.commit()
    return cm, con


def _com_estado(con, cid):
    con.execute("UPDATE copies SET " + ", ".join(f"{k} = ?" for k in ESTADO)
                + " WHERE id = ?", (*ESTADO.values(), cid))
    con.commit()


def _estado_de(con, cid):
    r = con.execute("SELECT " + ", ".join(ESTADO) + " FROM copies WHERE id = ?",
                    (cid,)).fetchone()
    return dict(zip(ESTADO, tuple(r)))


# ---------------------------------------------------------------------- 1
def _passos():
    src = (RAIZ / "daily.py").read_text(encoding="utf-8")
    corpo = src[src.index("def main():"):]
    return re.findall(r'_step\(con,\s*f?"([^"{]+)', corpo)


def caso_o_daily_poda_antes_de_gerar_as_paginas():
    """A primeira página do daily não pode sair antes do `prune`.

    No `main` de 25/10 as três podas eram os três últimos passos, depois do
    `inicio`."""
    p = _passos()
    for k in ("podar-precos", "podar-ligas", "prune", "vigia-cartas",
              "consenso-comandante", "core-decks", "painel", "inicio"):
        assert k in p, (k, p)
    paginas = [i for i, n in enumerate(p) if n in (
        "painel", "painel-listas", "consenso-comandante", "core-decks",
        "galeria-colecao", "colecao-cor", "cobertura-metagame", "deckboxes",
        "decks", "faltas", "metagame-pagina", "showcase-challenger", "inicio")]
    for poda in ("podar-precos", "podar-ligas", "prune"):
        assert p.index(poda) < min(paginas), (
            f"o passo {poda} corre depois de uma página — o site sai com listas "
            f"que a base apaga minutos depois", p)
    # E as duas ordens que já estavam registadas não se perdem.
    assert p.index("vigia-cartas") < p.index("podar-ligas") < p.index("prune"), p
    assert p.index("watch-check") < p.index("prune"), p
    assert p[-1] == "checkpoint", ("o checkpoint tem de ser o último passo", p[-3:])
    print("o daily poda antes da primeira pagina, e o checkpoint e o ultimo passo")


# ---------------------------------------------------------------------- 2
def caso_reservar_parte_o_lote_com_o_estado():
    d = Path(tempfile.mkdtemp())
    cm, con = _base(d)
    try:
        collection.add_copy(con, "Chromatic Star", set_code="5dn", quantity=3)
        cid = con.execute("SELECT id FROM copies").fetchone()["id"]
        _com_estado(con, cid)
        con.execute("INSERT INTO decks (name, format) VALUES ('X','cedh')")
        did = con.execute("SELECT id FROM decks").fetchone()["id"]
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, 'Chromatic Star', 1, 'main')", (did,))
        con.commit()
        r = collection.reserve_for_deck(con, did)
        assert r["reserved"] == {"Chromatic Star": 1}, r
        ids = [x["id"] for x in con.execute("SELECT id FROM copies ORDER BY id")]
        assert len(ids) == 2, ids
        nova = ids[1]
        assert con.execute("SELECT reserved_deck_id, quantity FROM copies "
                           "WHERE id = ?", (nova,)).fetchone()[:] == (did, 1)
        assert _estado_de(con, nova) == ESTADO, (
            "a metade reservada perdeu o estado da foto", _estado_de(con, nova))
        assert _estado_de(con, cid) == ESTADO
    finally:
        cm.__exit__(None, None, None)
    print("reservar parte o lote e a metade nova leva o estado e o verso")


def caso_nao_encontrei_parte_o_lote_com_o_estado():
    d = Path(tempfile.mkdtemp())
    cm, con = _base(d)
    try:
        con.execute("INSERT INTO decks (name, format) VALUES ('CLOUD','cedh')")
        did = con.execute("SELECT id FROM decks").fetchone()["id"]
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?, 'Chromatic Star', 2, 'main')", (did,))
        con.execute("""CREATE TABLE IF NOT EXISTS deck_collection (
                         watched_id INTEGER, sub_collection TEXT)""")
        collection.add_copy(con, "Chromatic Star", set_code="5dn", quantity=2,
                            sub_collection="Colecção")
        cid = con.execute("SELECT id FROM copies").fetchone()["id"]
        _com_estado(con, cid)
        # Uma das duas já está dentro da caixa: marcar parte o lote.
        con.execute("INSERT INTO copy_allocation (copy_id, slot, quantity, "
                    "placed_at) VALUES (?, 'cedh', 1, datetime('now'))", (cid,))
        con.commit()
        rep = loadout.report(con)
        r = loadout.marcar_nao_encontradas(con, rep, "cedh", [cid],
                                           csv_path=d / "ne.csv",
                                           com_backup=False)
        assert r["copias"] == 1, r
        nova = next(x["id"] for x in con.execute("SELECT id FROM copies")
                    if x["id"] != cid)
        assert con.execute("SELECT nao_encontrada_slot FROM copies WHERE id = ?",
                           (nova,)).fetchone()[0] == "cedh"
        assert _estado_de(con, nova) == ESTADO, (
            "a metade não encontrada perdeu o estado da foto", _estado_de(con, nova))
    finally:
        cm.__exit__(None, None, None)
    print("nao encontrei parte o lote e a metade nova leva o estado e o verso")


# ---------------------------------------------------------------------- 3
def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _tam(p: Path):
    """O tamanho do `-wal`; o fecho da última ligação APAGA-O, e isso conta."""
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _wal_por_despejar(base: Path, cat: Path):
    """Uma base em WAL com uma escrita AINDA no `-wal` e nenhuma ligação aberta
    — é o que o daily deixa quando o modo de edição está de pé."""
    with db.session(base, cat) as con:
        con.execute("PRAGMA journal_mode = WAL")
    c = sqlite3.connect(base)
    c.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    c.execute("PRAGMA wal_autocheckpoint = 0")
    c.execute("INSERT INTO job_runs (job, started, finished, status, detail) "
              "VALUES ('prune', datetime('now'), datetime('now'), 'ok', '')")
    c.commit()
    c.close()
    wal = base.with_name(base.name + "-wal")
    assert wal.exists() and wal.stat().st_size > 0, "o cenário não se montou"
    return wal


def caso_o_publicar_nao_mexe_no_ficheiro_da_base():
    """O que a tarefa corre (`py -m mtgvault.publicar`) não muda o `vault.db`.

    No `main` de 25/10 o `db.session()` fazia o `init` e, ao fechar, o
    checkpoint: o ficheiro principal mudava de sha256 e de mtime."""
    base, cat = Path(db.DEFAULT_DB), Path(db.DEFAULT_CATALOG)
    wal = _wal_por_despejar(base, cat)
    antes = (_sha(base), base.stat().st_mtime_ns, _tam(wal))
    leu = {}
    orig = publicar.estado

    def estado(con, *a, **kw):           # sem gerar páginas: só uma leitura
        leu["n"] = con.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
        return {"mudou": False}
    publicar.estado = estado
    try:
        assert publicar.main(["--ver"]) == 0
    finally:
        publicar.estado = orig
    depois = (_sha(base), base.stat().st_mtime_ns, _tam(wal))
    assert leu["n"] >= 1, "a leitura não viu o que está no -wal"
    assert depois == antes, ("o publicar escreveu no vault.db", antes, depois)
    # E quem despeja o -wal é o daily, no fim.
    import daily                                              # noqa: PLC0415
    with db.session(base, cat) as con:
        out = daily._checkpoint(con)
        # com a ligação AINDA aberta: o fecho da última ligação também o faria,
        # e é precisamente esse fecho que não se pode esperar.
        assert _tam(wal) == 0, (out, _tam(wal))
    print("o publicar abre so-leitura; o checkpoint e do daily:", out)


def caso_a_ligacao_do_publicar_recusa_escritas():
    d = Path(tempfile.mkdtemp())
    with db.session(d / "v.db", d / "c.db"):
        pass
    with publicar.abrir(d / "v.db", d / "c.db") as con:
        try:
            con.execute("INSERT INTO job_runs (job, started, status) "
                        "VALUES ('x', datetime('now'), 'ok')")
        except sqlite3.OperationalError as e:
            assert "readonly" in str(e), e
        else:
            raise AssertionError("a ligação do publicar deixou escrever")
    print("a ligacao do publicar recusa escritas")


# ---------------------------------------------------------------------- 4
def caso_a_percentagem_da_galeria_comeca_no_primeiro_valor():
    """A série real de 25/10: zeros de 14 a 20/10 e a colecção nova a partir de
    21/10. A base é o 21/10 (152,67 €), não o zero do dia 14."""
    serie = [("2026-10-12", 132858.30), (cg.ESVAZIAMENTO, 133496.67),
             ("2026-10-14", 0.0), ("2026-10-20", 0.0),
             ("2026-10-21", 152.67), ("2026-10-25", 141.66)]
    ind = re.search(r'<span class="evo-ind[^"]*">(.*?)</span></div>',
                    cg._evo_block(serie)).group(1)
    assert "sem variação" not in ind, ind
    assert "−7,2 %" in ind and "desde 2026-10-21" in ind, ind
    # Só zeros depois do corte continua a não dar percentagem, e diz porquê.
    so_zeros = re.search(r'<span class="evo-ind[^"]*">(.*?)</span></div>',
                         cg._evo_block(serie[:4])).group(1)
    assert "valia 0 €" in so_zeros and "%" not in so_zeros, so_zeros
    print("a galeria mede a variacao desde o primeiro dia com valor")


CASOS = [v for k, v in sorted(globals().items()) if k.startswith("caso_")]

if __name__ == "__main__":
    for c in CASOS:
        c()
    print("\nTUDO OK")
