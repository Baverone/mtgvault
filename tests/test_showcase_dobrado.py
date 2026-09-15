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
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

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


_PAGINA = None


def pagina():
    """`(casca, {fmt: html do painel como o browser o compõe}, {parte: obj})`.

    Desde 2026-09-15 a página é uma CASCA e os arquétipos vivem em
    `data/paginas/showcase/` — o painel de cada formato só existe depois do
    `fetch`. O que aqui se lê é o HTML que o JavaScript compõe
    (`showcase.html_de_formato`, o mesmo `juntar_arquetipo` do Python)."""
    global _PAGINA
    if _PAGINA is None:
        out = Path(tempfile.mkdtemp()) / "showcase.html"
        showcase.build(base(), out)
        idx, partes = showcase.ler_dados(out)
        paineis = {f["f"]: showcase.html_de_formato(out, f["f"])
                   for f in idx["formatos"]}
        _PAGINA = (out.read_text(encoding="utf-8"), paineis, partes)
    return _PAGINA


def _blocos(txt):
    """[(atributos, conteúdo)] de cada `<details>` de arquétipo."""
    return re.findall(r"<details class=\"dk\"([^>]*)>(.*?)</details>", txt, re.S)


def caso_cada_arquetipo_vai_dobrado():
    _casca, paineis, partes = pagina()
    txt = "".join(paineis.values())
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
        # A grelha de cartas é o que dobra: vem dentro do aberto, e num ficheiro
        # próprio (`data-parte`) nos fechados — que só se vai buscar ao abrir.
        parte = re.search(r'data-parte="([^"]+)"', attrs).group(1)
        assert 'class="cards"' in partes[parte]["corpo"], parte
        if " open" in attrs:
            assert 'class="cards"' in resto, "o aberto leva a grelha já dentro"
        else:
            assert 'class="cards"' not in resto, "o fechado não traz a grelha"
    print("cada arquetipo vai num <details>, com o cabecalho no <summary>")


def caso_um_aberto_por_formato():
    _casca, paineis, _partes = pagina()
    abertos = [a for p in paineis.values() for a, _c in _blocos(p) if " open" in a]
    assert len(abertos) == 2, ("um aberto por formato (Modern e Legacy)", abertos)
    # E é o PRIMEIRO de cada painel: quem entra na aba vê logo alguma coisa.
    for painel in paineis.values():
        blocos = _blocos(painel)
        assert blocos, painel[:200]
        assert " open" in blocos[0][0], "o primeiro do painel tem de vir aberto"
        assert all(" open" not in a for a, _c in blocos[1:]), "só o primeiro"
    print("um arquetipo aberto por formato, e e o primeiro")


def caso_as_imagens_continuam_a_ter_src():
    """As imagens levam `src` a sério (um `data-src` deixava 4 000 quadrados
    vazios), `loading="lazy"`, `decoding="async"` e as medidas — sem
    `width`/`height` a grelha saltava a cada imagem que chegava (2026-09-15)."""
    _casca, paineis, partes = pagina()
    txt = "".join(paineis.values()) + "".join(
        p["corpo"] for p in partes.values() if "corpo" in p)
    assert "data-src" not in txt, "as imagens não podem depender de JavaScript"
    imgs = re.findall(r"<img [^>]*>", txt)
    assert imgs, "a página tem de ter imagens"
    for i in imgs:
        assert 'src="http' in i and 'loading="lazy"' in i, i
        assert 'decoding="async"' in i and 'width="52"' in i and 'height="73"' in i, i
    print("as imagens mantem src a serio, lazy, async e com medidas")


def caso_o_browser_so_trata_as_imagens_abertas():
    """O número que interessa: quantas `<img>` o browser recebe ao abrir a
    página. Antes eram todas; desde 2026-09-15 só as do arquétipo aberto de
    cada formato — as outras vivem em ficheiros que só se vão buscar ao abrir."""
    _casca, paineis, partes = pagina()
    txt = "".join(paineis.values())
    recebidas = len(re.findall(r"<img ", txt))
    total = sum(len(re.findall(r"<img ", p["corpo"]))
                for p in partes.values() if "corpo" in p)
    assert 0 < recebidas < total, (recebidas, total)
    # Com dois arquétipos por formato e um aberto, é metade.
    assert recebidas * 2 == total, (recebidas, total)
    # E o JSON de cada formato só leva o corpo do aberto.
    for f, p in partes.items():
        if "arquetipos" in p:
            assert [bool(a.get("corpo")) for a in p["arquetipos"]] == [True, False], f
    print(f"o browser recebe {recebidas} de {total} imagens ao abrir a pagina")


def run():
    for fn in (caso_cada_arquetipo_vai_dobrado, caso_um_aberto_por_formato,
               caso_as_imagens_continuam_a_ter_src,
               caso_o_browser_so_trata_as_imagens_abertas):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
