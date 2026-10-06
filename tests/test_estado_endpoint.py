"""`POST /api/estado` por HTTP: a correcção à mão TEM de chegar à base.

Porque é que este ficheiro existe (2026-10-02)
----------------------------------------------
O endpoint entrou a 2026-10-03 com o estado das cartas, e o que foi medido
contra o 8771 nesse dia foram **as cinco recusas** (`Mint+`, `9.5`, vazio, texto
livre e um pedido sem `copy_id`): todas dão 409 e nenhuma deixa backup. Isso
estava certo e continua a estar — mas as cinco **voltam para trás antes** da
linha que grava. O caminho FELIZ, um escalão válido, nunca passou por HTTP.

E estava partido: o `webapp._estado` chamava `migracao.backup(etiqueta="estado")`
e o `migracao.backup` tem a assinatura `(con, pasta)` — sem `etiqueta` e com o
`con` obrigatório. Resultado: **500 em todos os pedidos válidos**, a correcção
dele nunca era escrita, e todo o ciclo que APRENDE («a correcção dele ganha
sempre») estava morto do lado da página. Os 27 casos do `test_estado_versos.py`
passavam, porque chamam o `estado.corrigir` directamente.

A lição, e é a que este ficheiro tranca: **um teste que só exercita a recusa não
prova o endpoint**. Aqui pede-se pelos dois lados, com um servidor a sério.

Não toca na rede: o servidor é local, num porto livre, e o `webapp.ROOT` aponta
para uma pasta temporária — senão a regeneração reescrevia o `deckboxes.html` e
o `metagame.html` publicados, dentro da árvore de trabalho.
"""
import json
import os
import socket
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
CFG = {
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "caixas": [{"slot": "a", "nome": "A", "formato": "legacy", "fonte": "deck",
                "ref": "A", "balde": "Colecção", "estado": "permanente",
                "prioridade": 7}],
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py
# E O CATÁLOGO (2026-10-06). Faltava, e era este ficheiro o escritor do `sid-0`
# — um **Tundra de Revised FALSO** — dentro do `data/catalog.db` do André, uma
# linha em CADA corrida da bateria (medido: `cards` 112 754 → 112 755). O
# `MTGVAULT_HOME` não salva: a omissão do `db.DEFAULT_CATALOG` é `ROOT/catalog.db`
# mas neste PC o `MTGVAULT_CATALOG` está no AMBIENTE, e o ambiente ganha. A
# `base()` aqui abaixo escreve em `catalog.cards`, por isso as duas variáveis
# andam juntas — e ANTES do import, que é onde o `db` as lê.
os.environ["MTGVAULT_CATALOG"] = str(_TMP / "catalog.db")

from mtgvault import db, estado  # noqa: E402

import webapp  # noqa: E402

# A REGENERAÇÃO ESCREVE PÁGINAS, e as páginas são ficheiros do repositório
# (`deckboxes.html`, `metagame.html`, `deckboxes.js` vão no `git add` do
# `daily.yml`). Sem isto, correr este teste deixava a árvore de trabalho suja
# com HTML gerado por uma base de brincar.
webapp.ROOT = _TMP


def base():
    con = db.connect()
    db.init(con)
    con.execute(
        """INSERT OR REPLACE INTO catalog.cards
           (scryfall_id, oracle_id, name, set_code, set_name, collector_number,
            lang, rarity, type_line, cmc, color_identity, finishes, released_at,
            legalities, digital, reserved, set_type)
           VALUES ('sid-0','oid-0','Tundra','3ed','Revised','288','en','rare',
                   'Land',0,'[]','["nonfoil"]','1994-04-11','{}',0,1,'core')""")
    con.execute("INSERT OR IGNORE INTO sub_collections (name, purpose) "
                "VALUES ('Colecção', 'player')")
    bal = con.execute("SELECT id FROM sub_collections WHERE name = 'Colecção'"
                      ).fetchone()["id"]
    con.execute(
        """INSERT INTO copies (scryfall_id, quantity, finish, language,
           condition, purpose, sub_collection_id)
           VALUES ('sid-0', 1, 'nonfoil', 'en', 'NM', 'player', ?)""", (bal,))
    con.commit()
    cid = con.execute("SELECT id FROM copies").fetchone()["id"]
    con.close()
    return cid


COPIA = base()

PORTO = 0
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    PORTO = s.getsockname()[1]
SRV = webapp.ThreadingHTTPServer(("127.0.0.1", PORTO), webapp.Handler)
threading.Thread(target=SRV.serve_forever, daemon=True).start()


def postar(caminho, corpo, prazo=120):
    """`(código, dicionário)`. Nunca levanta por um código de erro."""
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORTO}{caminho}",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=prazo) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(bruto)
        except ValueError:
            return e.code, {"corpo": bruto}


def copia():
    con = db.connect()
    r = con.execute("SELECT condition, condition_origem, condition_motivos "
                    "FROM copies WHERE id = ?", (COPIA,)).fetchone()
    con.close()
    return dict(r)


def backups():
    p = _TMP / "backups"
    return sorted(x.name for x in p.glob("*.db")) if p.exists() else []


# ---------------------------------------------------------------------------
def caso_um_escalao_valido_grava_e_responde_200():
    """O caminho feliz: 200, a coluna muda, e a origem fica `mao`.

    Chumba em cima do `webapp.py` de 2026-10-03: `migracao.backup(etiqueta=...)`
    levanta `TypeError` e o pedido dá **500** sem escrever nada.
    """
    antes = copia()
    # Quem responde a «este juízo conta?» é o `estado.origem_de`, num sítio só:
    # uma linha nova nasce com a coluna a NULL e isso VALE `omissao` (o `UPDATE`
    # do `db._migrate` só passa no `init` seguinte).
    assert antes["condition"] == "NM", antes
    assert estado.origem_de(antes) == estado.ORIGEM_OMISSAO, antes
    assert not estado.medido(estado.origem_de(antes)), antes

    code, r = postar("/api/estado", {
        "copy_id": COPIA, "grade": "EX",
        "motivos": "branco no canto inferior esquerdo",
        "escapou": "estava optimista com as bordas"})
    assert code == 200, (code, r)
    assert r.get("ok") is True, r

    d = copia()
    assert d["condition"] == "EX", d
    # A ORIGEM é o que faz a correcção dele ganhar sempre: uma avaliação minha
    # posterior é recusada contra `mao` (`estado.registar`). Sem ela gravada,
    # o ciclo que aprende não tem como saber que isto veio dele.
    assert estado.medido(d["condition_origem"]), d
    assert d["condition_origem"] == "mao", d
    assert "branco no canto" in (d["condition_motivos"] or ""), d
    print("POST /api/estado com um escalão válido: 200, grava `EX` e a origem "
          "fica `mao`")


def caso_um_escalao_valido_deixa_backup():
    """Uma coluna que muda o VALOR de uma cópia não se escreve sem rede.

    É a mesma regra do «vendida» e do «Desmontar». O caso anterior já gravou,
    por isso aqui confirma-se o que ele deixou atrás.
    """
    assert backups(), ("nenhum backup em data/backups depois de uma correcção "
                       "que mudou o valor de uma cópia")
    print("e deixa backup da base:", ", ".join(backups()))


def caso_um_escalao_invalido_e_409_e_nao_deixa_backup_novo():
    """A garantia de 2026-10-03, que continua de pé: 409 em português, zero
    backups novos. Um `.db` deste vault são ~96 MB e uma página aberta ontem no
    telemóvel pode mandar um escalão que já não existe."""
    tinha = backups()
    for mau in ("Mint+", "9.5", "", "muito bem conservada"):
        code, r = postar("/api/estado", {"copy_id": COPIA, "grade": mau})
        assert code == 409, (mau, code, r)
        texto = json.dumps(r, ensure_ascii=False)
        assert "escala do Cardmarket" in texto, (mau, r)
    code, r = postar("/api/estado", {"grade": "EX"})
    assert code == 409, (code, r)
    assert "copy_id" in json.dumps(r, ensure_ascii=False), r
    assert backups() == tinha, (backups(), tinha)
    # E não mexeu na cópia que o primeiro caso deixou em EX.
    assert copia()["condition"] == "EX", copia()
    print("cinco pedidos recusados: 409 em português, zero backups novos, "
          "e a cópia fica como estava")


def run():
    for fn in (caso_um_escalao_valido_grava_e_responde_200,
               caso_um_escalao_valido_deixa_backup,
               caso_um_escalao_invalido_e_409_e_nao_deixa_backup_novo):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    try:
        run()
    finally:
        SRV.shutdown()
