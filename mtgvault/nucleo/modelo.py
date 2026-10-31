"""O MODELO DO NÚCLEO NOVO (2026-10-28): os 14 decks, o modo de cada formato e
o interruptor `nucleo.ligado`.

O núcleo é pequeno de propósito e vive ao lado do resto do mtgvault: lê o
catálogo e o config, e escreve **só** nas tabelas `n_*`. Nunca toca em `copies`,
`copy_allocation`, `posse_marcada`, `decks`, `deck_cards` nem `watched*`. Se o
André não gostar do resultado, apaga-se a pasta e refaz-se de raiz.

As tabelas estão no `schema.sql` e no `db._migrate()` (iguais nos dois).
"""
from __future__ import annotations

import sqlite3

from .. import configio

# Premodern, cEDH, Pauper e Duel Commander ficam sempre montados; os outros
# formatos rodam (só um deck montado de cada vez, no total). Um deck novo de um
# destes formatos herda o modo daqui — não se decide deck a deck.
MODO_DO_FORMATO = {
    "premodern": "sempre",
    "cedh": "sempre",
    "pauper": "sempre",
    "duel-commander": "sempre",
    "standard": "rotativo",
    "pioneer": "rotativo",
    "modern": "rotativo",
    "legacy": "rotativo",
}

# (29/10/2026) A ordem dos formatos nas páginas, a que o André pediu: primeiro
# os rotativos (partilham cartas, mostram-se lado a lado), depois os sempre
# montados, um formato por linha.
ORDEM_FORMATO = ("standard", "pioneer", "modern", "legacy",
                 "premodern", "pauper", "cedh", "duel-commander")


def _deck(slug, nome, formato, arte_nome, vigia=None):
    return {"slug": slug, "nome": nome, "formato": formato,
            "modo": MODO_DO_FORMATO[formato], "vigia": vigia,
            "arte_nome": arte_nome}


# Dentro de cada formato, a ordem é a da página (os formatos seguem
# `ORDEM_FORMATO`). Os slugs são fixos (`[a-z_]+`): as escolhas de edição
# e as versões ficam presas a eles. A `vigia` diz de onde se vai buscar a lista
# atual (`mtgo:<jogador>:<formato>` ou `moxfield:<id público>`); sem ela a lista
# é fixa e nasce vazia («à espera da tua lista»). O `arte_nome` é a carta cuja
# arte dá a cara ao deck — tem de ser um nome que o Scryfall conheça.
DECKS: tuple[dict, ...] = (
    _deck("pioneer_greasefang", "Greasefang", "pioneer",
          "Greasefang, Okiba Boss"),
    _deck("modern_affinity", "Affinity", "modern", "Thought Monitor"),
    _deck("modern_oswald", "Oswald", "modern", "Oswald Fiddlebender"),
    _deck("legacy_welder_cam", "Welder Cam", "legacy", "Goblin Welder"),
    _deck("premodern_stifflenough", "Stifflenough", "premodern", "Stifle",
          vigia="mtgo:LuffyDoChapeuDePalha:premodern"),
    _deck("premodern_replenish", "UW Replenish", "premodern", "Replenish"),
    _deck("premodern_enchantress", "Enchantress", "premodern",
          "Argothian Enchantress"),
    # (31/10/2026) o André: a lista dos Elves é a do jogador thekingslayer
    _deck("premodern_elves", "Elves", "premodern", "Llanowar Elves",
          vigia="mtgo:thekingslayer:premodern"),
    _deck("premodern_igg", "Ill-Gotten Gains", "premodern", "Ill-Gotten Gains"),
    _deck("premodern_oath", "Oath of Druids", "premodern", "Oath of Druids"),
    _deck("pauper_affinity", "Affinity", "pauper", "Myr Enforcer",
          vigia="mtgo:LuffyDoChapeuDePalha:pauper"),
    _deck("cedh_blue_farm", "Blue Farm", "cedh", "Kraum, Ludevic's Opus",
          vigia="moxfield:7O1sCuIti0igU6Us_Jhadg"),
    _deck("cedh_cloud", "Cloud", "cedh", "Cloud, Midgar Mercenary",
          vigia="moxfield:k6f2yED7oUGPtK2_rN_xwg"),
    _deck("dc_cloud", "Cloud", "duel-commander", "Cloud, Midgar Mercenary"),
)


def garantir_decks(con: sqlite3.Connection) -> int:
    """Insere os decks que faltam e devolve quantos inseriu.

    Não mexe nos existentes: o nome, a ordem ou a vigia que tenham sido
    mudados à mão (ou o estado da vigia) não se repõem a cada arranque.
    """
    n = 0
    for ordem, d in enumerate(DECKS, start=1):
        cur = con.execute(
            "INSERT OR IGNORE INTO n_deck (slug, nome, formato, modo, vigia,"
            " arte_nome, ordem) VALUES (?,?,?,?,?,?,?)",
            (d["slug"], d["nome"], d["formato"], d["modo"], d["vigia"],
             d["arte_nome"], ordem))
        n += cur.rowcount
    con.commit()
    return n


def decks(con: sqlite3.Connection, modo: str | None = None) -> list[sqlite3.Row]:
    """Os decks por formato (`ORDEM_FORMATO`) e, dentro dele, por `ordem`;
    todos ou só de um modo (`sempre` | `rotativo`). Um formato fora da lista
    vai para o fim."""
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    if modo is None:
        cur.execute("SELECT * FROM n_deck ORDER BY ordem")
    else:
        cur.execute("SELECT * FROM n_deck WHERE modo = ? ORDER BY ordem", (modo,))
    fim = len(ORDEM_FORMATO)
    return sorted(cur.fetchall(), key=lambda d: (
        ORDEM_FORMATO.index(d["formato"]) if d["formato"] in ORDEM_FORMATO
        else fim, d["ordem"]))


def ligado(cfg: dict | None = None) -> bool:
    """O interruptor `colecao_config.json → nucleo.ligado` (omissão: desligado).

    Só lê. Sem ficheiro, sem o bloco ou sem a chave, o núcleo está desligado: o
    site que ele já tem fica exatamente como estava.
    """
    if cfg is None:
        try:
            cfg = configio.ler()
        except FileNotFoundError:
            return False
    bloco = cfg.get("nucleo")
    return isinstance(bloco, dict) and bloco.get("ligado") is True
