"""AS DUAS ÁRVORES (André, 2026-10-13, à letra).

*"o melhor e esvaziar tudo!"* e *"nao podes esquecer-te de apagar as pastas de
onde as fotos foram movidas, para me dar a entender que ja nao as estas a
pedir"*.

`Decks Por Processar/<deck>/<carta (N)>/` é onde ele larga as fotos;
`Decks Processados/<deck>/<carta (N)>/` é para onde o `arrumar_fotos` as MOVE,
e é lá que o `photo_path` aponta. O que este ficheiro tranca:

  1. uma pasta com IMAGENS nunca se apaga — a qualquer profundidade, com
     qualquer caixa de extensão —, nem a pasta de um deck, nem a pasta-mãe;
  2. a foto que ENTROU vai para a mesma pasta em «Processados», o
     `photo_path` aponta para lá e a pasta da carta em «Por Processar» some;
  3. a foto que PAROU volta à pasta da carta, com o MESMO nome e o motivo ao
     lado, não volta a ser lida até haver foto nova (ou se apagar o motivo) —
     e quando volta, volta com o mesmo nome;
  4. o gerador das pastas de carta é idempotente: cria as que faltam, não
     ressuscita as provadas, e devolve a pasta quando a carta deixa de estar
     provada (uma correcção);
  5. nenhuma foto fica sem alvo em silêncio: a solta na pasta-mãe e a da pasta
     antiga dizem-se, com a frase que a tarefa das 02:30 trata como erro.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())

CAIXAS = [
    {"slot": "cedh-blue-farm", "nome": "Blue Farm", "formato": "cedh",
     "fonte": "deck", "ref": "BF", "balde": "Colecção", "estado": "montada",
     "prioridade": 1},
]
CFG = {
    "venda": {"mostrar": False},
    "regras_colecao": {},
    "baldes_coleccao": ["Colecção", "Caixa Reserved List"],
    "decks_vigiados": [],
    "premodern_arquetipos_alvo": [],
    "regras_por_formato": [
        {"grupo": "cedh", "formatos": ["cedh"], "lingua": "en",
         "acabamento": "nonfoil"},
    ],
    "caixas": CAIXAS,
    "revalidacao": {"desde": None, "alvo": None},
    "reserva": {"limiar_pct": 20},
}
CAMINHO = _TMP / "cfg.json"
CAMINHO.write_text(json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
os.environ["MTGVAULT_CONFIG"] = str(CAMINHO)
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

from mtgvault import collection, db, fotocaixa, fotos, fotosite, loadout  # noqa: E402

SITE = _TMP / "site"
SITE.mkdir(exist_ok=True)
fotocaixa.RAIZ = SITE
PEND = fotosite.pasta_pendentes(SITE)
POR = fotos.pasta_novas(SITE)
FEITOS = fotos.pasta_processados(SITE)
CARTA = "Swords to Plowshares (4)"

CATALOGO = [
    ("Swords to Plowshares", "4ed", "1995-04-01", "Instant"),
    ("Birds of Paradise", "4ed", "1995-04-01", "Creature"),
]
_ABERTAS = []


def base():
    d = Path(tempfile.mkdtemp())
    cm = db.session(d / "v.db", d / "c.db")
    _ABERTAS.append(cm)
    con = cm.__enter__()
    for i, (nm, sc, rel, tipo) in enumerate(CATALOGO):
        con.execute(
            """INSERT OR REPLACE INTO catalog.cards (scryfall_id, oracle_id, name,
               set_code, set_name, collector_number, lang, rarity, type_line, cmc,
               color_identity, finishes, released_at, legalities, digital, reserved)
               VALUES (?,?,?,?,?,?,'en','rare',?,1,'W','["nonfoil"]',?,'{}',0,0)""",
            (f"id-{i}", f"or-{nm}", nm, sc, sc.upper(), str(i), tipo, rel))
    con.execute("INSERT INTO decks (name, format) VALUES ('BF', 'cedh')")
    did = con.execute("SELECT id FROM decks WHERE name = 'BF'").fetchone()["id"]
    for nm, q in (("Swords to Plowshares", 4), ("Birds of Paradise", 1)):
        con.execute("INSERT INTO deck_cards (deck_id, card_name, quantity, board) "
                    "VALUES (?,?,?, 'main')", (did, nm, q))
    con.commit()
    dbs = con.execute("PRAGMA database_list").fetchall()
    db.DEFAULT_DB = Path(dbs[0]["file"])
    db.DEFAULT_CATALOG = Path(dbs[1]["file"])
    return con


def foto(p: Path, mtime: float = 1_700_000_000) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 64)
    os.utime(p, (mtime, mtime))
    return p


def limpar():
    import shutil
    for d in (POR, FEITOS, PEND):
        if d.exists():
            shutil.rmtree(d)
    fotos._CACHE.clear()


# ===========================================================================
# 1. UMA PASTA COM IMAGENS NUNCA SE APAGA
# ===========================================================================
def caso_uma_pasta_com_imagens_nunca_se_apaga():
    """A guarda mais importante do dia. Falha se uma única destas pastas se for:
    imagem à vista, imagem numa subpasta, extensão em maiúsculas, HEIC; e falha
    se a pasta de um DECK ou a pasta-mãe puderem ser apagadas (mesmo vazias)."""
    limpar()
    casos = {
        "a": "x.jpg", "b": "lote/y.jpeg", "c": "Z.JPG", "d": "w.HEIC",
        "e": "v.webp", "f": "u.png",
    }
    for k, rel in casos.items():
        foto(POR / "Blue Farm" / f"carta {k} (1)" / rel)
    for k in casos:
        d = POR / "Blue Farm" / f"carta {k} (1)"
        assert not fotos.apagar_pasta_feita(d, POR), d
        assert d.is_dir() and fotos.tem_imagens(d), d
    # Um ficheiro que não é nosso também a segura.
    (POR / "Blue Farm" / "carta g (1)").mkdir(parents=True)
    (POR / "Blue Farm" / "carta g (1)" / "nota.txt").write_text("minha")
    assert not fotos.apagar_pasta_feita(POR / "Blue Farm" / "carta g (1)", POR)
    # A pasta do deck e a pasta-mãe, nunca — nem vazias.
    (POR / "Vazio").mkdir()
    assert not fotos.apagar_pasta_feita(POR / "Vazio", POR)
    assert not fotos.apagar_pasta_feita(POR, POR)
    assert (POR / "Vazio").is_dir() and POR.is_dir()
    # Vazia (com o lixo nosso), apaga-se.
    v = POR / "Blue Farm" / "carta h (1)"
    v.mkdir()
    (v / ".gitkeep").write_text("")
    (v / fotos.MOTIVO_PAROU).write_text("parou")
    assert fotos.apagar_pasta_feita(v, POR)
    assert not v.exists()
    print("nenhuma pasta com imagens se apaga; a de deck e a mae nunca; a vazia sim")


# ===========================================================================
# 2. A FOTO QUE ENTROU: VAI PARA «PROCESSADOS» E A PASTA DA CARTA SOME
# ===========================================================================
def _recolher_e_importar(con, resultado="importada"):
    f = foto(POR / "Blue Farm" / CARTA / "IMG_0001.jpg")
    r = fotos.recolher_das_pastas(raiz=SITE, agora=time.time())
    assert len(r["recolhidas"]) == 1, r
    nome = r["recolhidas"][0]["para"]
    assert not f.exists()
    origens = fotos.ler_origens(PEND)
    assert origens[nome]["rel"] == f"Blue Farm/{CARTA}", origens
    cid = None
    if resultado == "importada":
        cid = collection.add_copy(con, "Swords to Plowshares", set_code="4ed",
                                  quantity=4, sub_collection="Colecção")
        con.commit()
    linha = {"photo_path": nome, "resultado": resultado, "copy_id": cid,
             "name": "Swords to Plowshares", "set_code": "4ed",
             "collector_number": "0", "quantity": 4,
             "motivo": None if resultado == "importada" else "edicao em falta"}
    a = collection.arrumar_fotos(con, [linha], pendentes=PEND)
    return nome, cid, a


def caso_a_foto_que_entrou_vai_para_processados_e_a_pasta_some():
    limpar()
    con = base()
    nome, cid, a = _recolher_e_importar(con)
    destino = FEITOS / "Blue Farm" / CARTA / nome
    assert destino.is_file(), (destino, a)
    pp = con.execute("SELECT photo_path FROM copies WHERE id = ?",
                     (cid,)).fetchone()["photo_path"]
    assert pp == f"{fotos.PASTA_PROCESSADAS}/Blue Farm/{CARTA}/{nome}", pp
    assert fotos.resolver(pp) is not None, pp
    # A pasta da carta foi-se; a do deck fica.
    assert not (POR / "Blue Farm" / CARTA).exists(), a
    assert (POR / "Blue Farm").is_dir()
    assert a["pastas_apagadas"] == [f"Blue Farm/{CARTA}"], a
    assert fotos.ler_origens(PEND) == {}, "o registo de origens não se limpou"
    print("a foto que entrou foi para Decks Processados e a pasta da carta apagou-se")


# ===========================================================================
# 3. A FOTO QUE PAROU: VOLTA À PASTA DA CARTA, COM O MESMO NOME
# ===========================================================================
def caso_a_foto_que_parou_volta_a_pasta_com_o_mesmo_nome():
    limpar()
    con = base()
    nome, _, a = _recolher_e_importar(con, resultado="parada")
    d = POR / "Blue Farm" / CARTA
    assert (d / nome).is_file(), (a, list(d.iterdir()) if d.exists() else None)
    assert (d / fotos.MOTIVO_PAROU).is_file()
    assert "edicao em falta" in (d / fotos.MOTIVO_PAROU).read_text(encoding="utf-8")
    assert not (PEND / nome).exists()
    assert not (FEITOS / "Blue Farm" / CARTA / nome).exists()
    assert fotos.ler_origens(PEND) == {}
    # A corrida seguinte NÃO a volta a ler (é mais velha do que o motivo)…
    r = fotos.recolher_das_pastas(raiz=SITE, agora=time.time())
    assert not r["recolhidas"], r
    assert [x["ficheiro"] for x in r.get("paradas") or []] == [nome], r
    # …e quando ele apaga o motivo, volta — COM O MESMO NOME (é por ele que as
    # linhas que já tinham entrado se reconhecem como `repetida`).
    (d / fotos.MOTIVO_PAROU).unlink()
    r = fotos.recolher_das_pastas(raiz=SITE, agora=time.time())
    assert [x["para"] for x in r["recolhidas"]] == [nome], r
    print("a foto que parou voltou à pasta da carta, ficou quieta, e voltou com o mesmo nome")


def caso_uma_foto_nova_ao_lado_da_parada_segue():
    limpar()
    con = base()
    nome, _, _ = _recolher_e_importar(con, resultado="parada")
    d = POR / "Blue Farm" / CARTA
    agora = time.time()
    os.utime(d / fotos.MOTIVO_PAROU, (agora - 3600, agora - 3600))
    foto(d / "IMG_0002.jpg", mtime=agora - 120)
    r = fotos.recolher_das_pastas(raiz=SITE, agora=agora)
    assert len(r["recolhidas"]) == 1 and r["recolhidas"][0]["de"] == "IMG_0002.jpg", r
    assert [x["ficheiro"] for x in r.get("paradas") or []] == [nome], r
    print("uma foto nova numa pasta parada segue; a antiga fica dita")


# ===========================================================================
# 4. O GERADOR DAS PASTAS DE CARTA É IDEMPOTENTE
# ===========================================================================
def caso_o_gerador_cria_nao_ressuscita_e_devolve_numa_correccao():
    limpar()
    con = base()
    rep = loadout.report(con)
    POR.mkdir(parents=True, exist_ok=True)
    fotos.garantir_pastas(rep, SITE)
    r1 = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert sorted(r1["criadas"]) == ["Blue Farm/Birds of Paradise (1)",
                                     f"Blue Farm/{CARTA}"], r1
    r2 = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r2["criadas"] == [] and r2["apagadas"] == [], r2
    # A carta passa a estar PROVADA naquele deck: a pasta (vazia) vai-se…
    cid = collection.add_copy(con, "Swords to Plowshares", set_code="4ed",
                              quantity=4, sub_collection="Colecção")
    con.execute("UPDATE copies SET photo_path = ? WHERE id = ?",
                (f"{fotos.PASTA_PROCESSADAS}/Blue Farm/{CARTA}/f.jpg", cid))
    con.commit()
    r3 = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r3["apagadas"] == [f"Blue Farm/{CARTA}"], r3
    # …e NÃO ressuscita.
    r4 = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r4["criadas"] == [] and not (POR / "Blue Farm" / CARTA).exists(), r4
    # Uma CORRECÇÃO tira a prova (a cópia não estava lá): a pasta VOLTA.
    con.execute("UPDATE copies SET nao_encontrada_em = '2026-10-13' WHERE id = ?",
                (cid,))
    con.commit()
    r5 = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r5["criadas"] == [f"Blue Farm/{CARTA}"], r5
    print("o gerador cria as que faltam, não ressuscita as provadas, devolve-as numa correcção")


def caso_o_gerador_nao_apaga_uma_pasta_provada_com_fotos_dentro():
    limpar()
    con = base()
    rep = loadout.report(con)
    POR.mkdir(parents=True, exist_ok=True)
    fotos.garantir_pastas(rep, SITE)
    fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    foto(POR / "Blue Farm" / CARTA / "outra.jpg")
    cid = collection.add_copy(con, "Swords to Plowshares", set_code="4ed",
                              quantity=4, sub_collection="Colecção")
    con.execute("UPDATE copies SET photo_path = ? WHERE id = ?",
                (f"{fotos.PASTA_PROCESSADAS}/Blue Farm/{CARTA}/f.jpg", cid))
    con.commit()
    r = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r["apagadas"] == [] and r["ficam_com_fotos"] == [f"Blue Farm/{CARTA}"], r
    assert (POR / "Blue Farm" / CARTA / "outra.jpg").is_file()
    print("uma pasta provada com fotos dentro fica")


def caso_o_gerador_apaga_as_vazias_fora_da_lista_e_nunca_as_com_fotos():
    """André, 2026-10-16, à letra: *"como ainda nao fotografei nada, altera as
    pastas que tens que alterar"*. Uma pasta de carta VAZIA que nenhuma lista
    pede apaga-se, e a do `(N)` velho passa ao de hoje — sem corredor de espera
    (o `_fora do plano\\` de 16/10 de manhã). Mas a partir da primeira foto
    nada lhe toca: é a tranca disso, com imagens à vista, numa subpasta e em
    maiúsculas, nos dois ramos (fora da lista e com o `(N)` errado)."""
    limpar()
    con = base()
    rep = loadout.report(con)
    POR.mkdir(parents=True, exist_ok=True)
    fotos.garantir_pastas(rep, SITE)
    bf = POR / "Blue Farm"
    (bf / "Lotus Petal (2)").mkdir(parents=True)                 # vazia, fora
    (bf / "Lotus Petal (2)" / ".gitkeep").write_text("")
    (bf / "Birds of Paradise (3)").mkdir()                       # (N) velho
    foto(bf / "Mox Diamond (1)" / "IMG_1.jpg")                   # fora, COM foto
    foto(bf / "Chrome Mox (1)" / "lote" / "IMG_2.JPG")           # fora, foto funda
    foto(bf / "Swords to Plowshares (2)" / "IMG_3.heic")         # (N) velho, COM foto
    (bf / "lote1").mkdir()                                       # não é pasta de carta
    r = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r["apagadas_fora"] == ["Blue Farm/Lotus Petal (2)"], r
    assert r["renomeadas"] == ["Blue Farm/Birds of Paradise (3) -> "
                               "Birds of Paradise (1)"], r
    assert not (bf / "Lotus Petal (2)").exists()
    assert (bf / "Birds of Paradise (1)").is_dir()
    for p in ("Mox Diamond (1)/IMG_1.jpg", "Chrome Mox (1)/lote/IMG_2.JPG",
              "Swords to Plowshares (2)/IMG_3.heic"):
        assert (bf / p).is_file(), p
    assert sorted(r["ficam_com_fotos"]) == [
        "Blue Farm/Chrome Mox (1)", "Blue Farm/Mox Diamond (1)",
        "Blue Farm/Swords to Plowshares (2)"], r
    assert (bf / "lote1").is_dir()
    # A da Swords com o (N) velho tem a foto à espera: não nasce uma segunda
    # pasta a pedir a mesma carta ao lado dela.
    assert not (bf / CARTA).exists()
    # Idempotente: a segunda passagem não mexe em nada.
    r2 = fotos.sincronizar_pastas_de_cartas(con, rep, raiz=SITE)
    assert r2["apagadas_fora"] == [] and r2["renomeadas"] == [] \
        and r2["criadas"] == [], r2
    print("as vazias fora da lista apagam-se, o (N) acerta-se, as com fotos ficam")


def caso_so_o_apagar_pasta_feita_apaga_pastas():
    """A única porta para apagar uma pasta de fotos é o `apagar_pasta_feita`
    (que recusa imagens). Um `rmtree` no `fotos.py` era uma segunda porta sem
    a guarda — e a regra de 16/10 só vale para pastas vazias."""
    txt = (Path(fotos.__file__)).read_text(encoding="utf-8")
    assert "rmtree" not in txt, "o fotos.py ganhou um rmtree"
    assert txt.count(".rmdir(") == 2, "um rmdir novo no fotos.py: passa pela guarda?"
    print("só o apagar_pasta_feita apaga pastas de carta")


# ===========================================================================
# 5. NENHUMA FOTO FICA SEM ALVO EM SILÊNCIO
# ===========================================================================
def caso_a_foto_solta_e_a_da_pasta_antiga_dizem_se():
    limpar()
    foto(POR / "solta.jpg")
    foto(SITE / fotos.PASTA_NOVAS_ANTIGA / "Blue Farm" / "velha.jpg")
    try:
        r = fotos.recolher_das_pastas(raiz=SITE, agora=time.time())
        assert not r["recolhidas"], r
        ign = {x["ficheiro"]: x["porque"] for x in r["ignorados"]}
        assert set(ign) == {"solta.jpg", "velha.jpg"}, r
        # É a frase que a tarefa `mtg-fotos-novas` trata como ERRO.
        assert all("caixa do config" in p for p in ign.values()), ign
        assert (POR / "solta.jpg").is_file()
    finally:
        import shutil
        shutil.rmtree(SITE / fotos.PASTA_NOVAS_ANTIGA, ignore_errors=True)
    print("a foto solta e a da pasta antiga não se processam e dizem-se")


CASOS = (caso_uma_pasta_com_imagens_nunca_se_apaga,
         caso_a_foto_que_entrou_vai_para_processados_e_a_pasta_some,
         caso_a_foto_que_parou_volta_a_pasta_com_o_mesmo_nome,
         caso_uma_foto_nova_ao_lado_da_parada_segue,
         caso_o_gerador_cria_nao_ressuscita_e_devolve_numa_correccao,
         caso_o_gerador_nao_apaga_uma_pasta_provada_com_fotos_dentro,
         caso_o_gerador_apaga_as_vazias_fora_da_lista_e_nunca_as_com_fotos,
         caso_so_o_apagar_pasta_feita_apaga_pastas,
         caso_a_foto_solta_e_a_da_pasta_antiga_dizem_se)


def main():
    for c in CASOS:
        c()
    for cm in _ABERTAS:
        try:
            cm.__exit__(None, None, None)
        except Exception:                                    # noqa: BLE001
            pass
    print(f"\nOK — {len(CASOS)} casos (as duas árvores)")


if __name__ == "__main__":
    main()
