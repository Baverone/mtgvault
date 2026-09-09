"""O Showcase dobra cada arquétipo num `<details>` (2026-09-09).

O defeito: 30 arquétipos por formato, cada um com main + sideboard + opções, tudo
numa parede aberta. Na base do André isso são **4 320 `<img>` e 1,2 MB** de HTML
numa página só, e no telemóvel dele a página levava segundos a assentar para
mostrar um 30.º arquétipo de Modern para que ninguém olha.

O que aqui se tranca:

  1. cada arquétipo vai num `<details>`, e o `<summary>` continua a ter TUDO o
     que se lê a passar os olhos (nome, `tem/total · %`, selos, barra) — dobrar
     o cabeçalho seria esconder a página, não aliviá-la;
  2. **um aberto por formato**, o primeiro (o de mais peso). Zero abertos deixava
     o André a olhar para uma lista de títulos;
  3. **as `<img>` continuam a ter `src` a sério.** É a metade que se perde
     facilmente: um `data-src` preenchido por JavaScript dava o mesmo ganho e
     deixava a página vazia com o JS desligado. Uma `<img loading="lazy">` dentro
     de um `<details>` fechado já não é descarregada pelo browser — o ganho vem
     daí, sem uma linha de JavaScript;
  4. as imagens que o browser tem mesmo de tratar (as que estão FORA de um
     `<details>` fechado) são só as do arquétipo aberto de cada formato.

Não toca na rede nem na `vault.db` a sério.
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_TMP = Path(tempfile.mkdtemp())
(_TMP / "cfg.json").write_text(json.dumps({
    "loadout": [], "decks_vigiados": [], "premodern_arquetipos_alvo": [],
    "regras_colecao": {}, "spml_formatos": {},
}, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(_TMP / "cfg.json")
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import db  # noqa: E402

import showcase  # noqa: E402

_ABERTAS = []

# Dois arquétipos por formato, bem separados (Jaccard 0 entre eles), com listas
# que cheguem para passar o `MIN_ARCH_WT`.
ARQUETIPOS = {
    "modern": [["Cranial Plating", "Frogmite", "Thoughtcast", "Springleaf Drum"],
               ["Living End", "Grief", "Violent Outburst", "Shardless Agent"]],
    "legacy": [["Doomsday", "Thassa's Oracle", "Brainstorm", "Ponder"],
               ["Sneak Attack", "Show and Tell", "Emrakul", "Lotus Petal"]],
}
CARTAS = sorted({c for v in ARQUETIPOS.values() for l in v for c in l})


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, nm in enumerate(CARTAS):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,'mrd','S',?,'en','rare','Artifact',2,'U',?,
                       '2003-10-02',?,0,0)""",
            (f"id-{i}", f"or-{i}", nm, str(i), json.dumps(["nonfoil"]),
             json.dumps({"modern": "legal", "legacy": "legal"})))
    n = 0
    for fmt, listas in ARQUETIPOS.items():
        for cartas in listas:
            for _ in range(4):          # 4 Challenges por arquétipo: peso 4 >= 3
                n += 1
                con.execute(
                    """INSERT INTO decklists (source, source_key, format, player,
                       event_name, event_date, event_tier, placement)
                       VALUES ('mtgo', ?, ?, 'jogador', 'Challenge', '2026-09-01',
                               'Challenge', '')""", (f"k{n}", fmt))
                did = con.execute("SELECT id FROM decklists WHERE source_key = ?",
                                  (f"k{n}",)).fetchone()["id"]
                for c in cartas:
                    con.execute("""INSERT INTO decklist_cards (decklist_id, card_name,
                                   quantity, board) VALUES (?,?,4,'main')""", (did, c))
    con.commit()
    return con


def pagina():
    out = Path(tempfile.mkdtemp()) / "showcase.html"
    showcase.build(base(), out)
    return out.read_text(encoding="utf-8")


def _blocos(txt):
    """[(atributos, conteúdo)] de cada `<details>` de arquétipo."""
    return re.findall(r"<details class=\"dk\"([^>]*)>(.*?)</details>", txt, re.S)


def caso_cada_arquetipo_vai_dobrado():
    txt = pagina()
    blocos = _blocos(txt)
    assert len(blocos) == 4, ("dois arquétipos em cada um dos dois formatos",
                              len(blocos))
    for attrs, corpo in blocos:
        cab, _sep, resto = corpo.partition("</summary>")
        assert cab.startswith("<summary>"), corpo[:120]
        # O cabeçalho fica de fora do que se dobra: é por ele que ele decide se
        # vale a pena abrir.
        for pedaco in ('class="dtop"', 'class="pct"', 'class="badges"',
                       'class="bar"'):
            assert pedaco in cab, (pedaco, cab[:300])
        assert "class=\"cards\"" in resto, "a grelha de cartas tem de ser o que dobra"
    print("cada arquetipo vai num <details>, com o cabecalho no <summary>")


def caso_um_aberto_por_formato():
    txt = pagina()
    abertos = [a for a, _c in _blocos(txt) if " open" in a]
    assert len(abertos) == 2, ("um aberto por formato (Modern e Legacy)", abertos)
    # E é o PRIMEIRO de cada painel: quem entra na aba vê logo alguma coisa.
    for painel in re.findall(r'<section class="fpanel[^"]*"[^>]*>(.*?)</section>',
                             txt, re.S):
        blocos = _blocos(painel)
        assert blocos, painel[:200]
        assert " open" in blocos[0][0], "o primeiro do painel tem de vir aberto"
        assert all(" open" not in a for a, _c in blocos[1:]), "só o primeiro"
    print("um arquetipo aberto por formato, e e o primeiro")


def caso_as_imagens_continuam_a_ter_src():
    """A página tem de funcionar com o JavaScript desligado. Um `data-src` dava o
    mesmo ganho e deixava-a com 4 000 quadrados vazios."""
    txt = pagina()
    assert "data-src" not in txt, "as imagens não podem depender de JavaScript"
    imgs = re.findall(r"<img [^>]*>", txt)
    assert imgs, "a página tem de ter imagens"
    for i in imgs:
        assert 'src="http' in i and 'loading="lazy"' in i, i
    print("as imagens mantem src a serio e loading=lazy: funciona sem JavaScript")


def caso_o_browser_so_trata_as_imagens_abertas():
    """O número que interessa: quantas `<img>` estão FORA de um `<details>`
    fechado. Antes eram todas."""
    txt = pagina()
    total = len(re.findall(r"<img ", txt))
    fechadas = sum(len(re.findall(r"<img ", c))
                   for a, c in _blocos(txt) if " open" not in a)
    fora = total - fechadas
    assert 0 < fora < total, (fora, total)
    # Com dois arquétipos por formato e um aberto, é metade.
    assert fora * 2 == total, (fora, total)
    print(f"o browser trata {fora} de {total} imagens ao abrir a pagina")


def run():
    for fn in (caso_cada_arquetipo_vai_dobrado, caso_um_aberto_por_formato,
               caso_as_imagens_continuam_a_ter_src,
               caso_o_browser_so_trata_as_imagens_abertas):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
