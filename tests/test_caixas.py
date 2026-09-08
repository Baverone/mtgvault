"""A UNIFICAÇÃO: uma só noção de deck (a caixa) e a migração do config.

André, 2026-09-08: *"No mtgvault já começamos a ter informação duplicada. Temos
decks vigiados e deckbox que é a mesma coisa."*

O que aqui se tranca:

  1. **a migração não muda nada.** Um config da v5 (`loadout`) e o mesmo config
     migrado (`caixas`) dão exactamente as mesmas caixas, as mesmas fontes, as
     mesmas regras e a mesma ordem de alocação. É o compromisso da v6: unificar
     o vocabulário sem mexer num número;
  2. **é idempotente** — correr duas vezes não faz nada da segunda, e um config
     que já é v6 passa incólume;
  3. **a escala de estados**: `montada` implica permanente, `congelada` é
     calculada (montada + dedicada + o vault sabe o que lá está) e nunca se
     grava como uma quinta verdade;
  4. **o motor aceita as duas formas** — é o que faz um config por migrar
     continuar a funcionar em vez de rebentar no arranque do dia.

Não toca na rede.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
os.environ.setdefault("MTGVAULT_HOME", str(_TMP))

from mtgvault import caixas, configio, loadout  # noqa: E402

V5 = {
    "_ajuda": "isto é uma chave de ajuda e tem de sobreviver",
    "loadout": [
        {"slot": "pauper", "nome": "Pauper (Luffy)", "formato": "pauper",
         "fonte": "vigiado", "ref": "Luffy — Pauper", "balde": "Pauper Affinity",
         "prioridade": 1, "montado": True, "permanente": True},
        {"slot": "premodern-replenish", "nome": "UW Replenish",
         "formato": "premodern", "fonte": "deck", "ref": "UW Replenish (consenso)",
         "balde": "Premodern (geral)", "prioridade": 6, "permanente": True},
        {"slot": "legacy", "nome": "Legacy", "formato": "legacy", "fonte": "deck",
         "ref": None, "balde": "SPML", "prioridade": 14, "por_confirmar": True,
         "permanente": False},
        {"slot": "modern", "nome": "Modern", "formato": "modern", "fonte": "deck",
         "ref": "UW Oswald", "balde": "SPML", "prioridade": 12,
         "acabamento": "foil", "lingua": "en"},          # sem `permanente`
    ],
    "_loadout": "a ajuda antiga, que é substituída pela nova",
    "regras_por_formato": [
        {"grupo": "premodern", "formatos": ["premodern"], "dedicado": True,
         "lingua": "pt", "edicoes": "premodern", "estrita": True},
        {"grupo": "pauper", "formatos": ["pauper"], "dedicado": True,
         "acabamento": "prefere_foil"},
        {"grupo": "spml", "formatos": ["standard", "pioneer", "modern", "legacy"],
         "lingua": "en", "acabamento": "foil"},
    ],
    "regras_colecao": {"Pauper Affinity": {"reter_extras_meses": 6}},
}

# O que interessa comparar de um slot resolvido: quem é, de onde vem a lista, com
# que regras e em que ordem aloca.
CHAVES = ("slot", "nome", "formato", "fonte", "ref", "balde", "prioridade",
          "permanente", "montado", "por_confirmar", "vazio", "dedicado",
          "lingua", "acabamento", "edicoes", "estrita", "grupo", "grupo_ordem",
          "vigiado")


def _resolvidos(cfg_slots):
    """Resolve sem base de dados: as listas ficam vazias, o resto é igual."""
    class SemLinhas(list):
        def fetchone(self):
            return None

    class SemBase:
        def execute(self, *_a):
            return SemLinhas()
    return [{k: s.get(k) for k in CHAVES}
            for s in loadout.resolve_slots(SemBase(), cfg_slots)]


def caso_a_migracao_nao_muda_as_caixas():
    novo, mudou = caixas.migrar_config(json.loads(json.dumps(V5)))
    assert mudou
    antes = _resolvidos(V5["loadout"])
    depois = _resolvidos(novo["caixas"])
    assert antes == depois, [
        (a, b) for a, b in zip(antes, depois, strict=True) if a != b]
    print(f"config v5 -> v6: {len(depois)} caixas, mesmas fontes e mesmas regras")


def caso_a_chave_nova_fica_no_lugar_da_antiga():
    novo, _ = caixas.migrar_config(json.loads(json.dumps(V5)))
    assert "loadout" not in novo and "_loadout" not in novo, list(novo)
    assert list(novo).index("caixas") == list(V5).index("loadout"), list(novo)
    assert novo["_ajuda"] == V5["_ajuda"], "as outras chaves não se tocam"
    assert novo["_caixas"].startswith("AS CAIXAS"), "a ajuda nova tem de lá estar"
    print("a `caixas` fica no lugar do `loadout`, e o resto do config nao muda")


def caso_e_idempotente():
    novo, _ = caixas.migrar_config(json.loads(json.dumps(V5)))
    outra, mudou = caixas.migrar_config(json.loads(json.dumps(novo)))
    assert mudou is False and outra == novo
    print("migrar duas vezes: a segunda nao faz nada")


def caso_o_motor_aceita_as_duas_formas():
    """Um config por migrar tem de continuar a funcionar — senão a v6 partia o
    job diário de quem não corresse a migração primeiro."""
    velho = _resolvidos(V5["loadout"])
    novo = _resolvidos(caixas.do_config({"loadout": V5["loadout"]}))
    assert velho == novo
    print("o motor le o `loadout` da v5 e as `caixas` da v6 da mesma maneira")


def caso_a_escala_de_estados():
    e = caixas.estado_de
    assert e({"estado": "montada"}) == "montada"
    assert e({"montado": True, "permanente": False}) == "montada", \
        "montada implica permanente — um deck sleevado nao e um candidato"
    assert e({"permanente": False}) == "candidata"
    assert e({}) == "permanente", "sem chave, e permanente (era o default da v5)"
    # `congelada` no config vale `montada`: quem decide se está congelada é o
    # motor (dedicada + o vault sabe o que lá está), e não uma quinta verdade.
    assert e({"estado": "congelada"}) == "montada"
    s = caixas.para_slot({"estado": "congelada", "slot": "x"})
    assert s["montado"] is True and s["permanente"] is True and "congelada" not in (
        s.get("estado"),)
    print("estados: candidata < permanente < montada; congelada calcula-se")


def caso_por_confirmar_deixa_de_ser_uma_chave():
    """Era escrita à mão e ficava a mentir sempre que ele escolhia um deck."""
    assert caixas.para_slot({"slot": "x", "fonte": "deck", "ref": None})[
        "por_confirmar"] is True
    assert caixas.para_slot({"slot": "x", "fonte": "deck", "ref": "A"})[
        "por_confirmar"] is False
    # Uma caixa de consenso não tem `ref` e não está por confirmar.
    assert caixas.para_slot({"slot": "x", "fonte": "consenso",
                             "assinatura": ["Oath of Druids"]})[
        "por_confirmar"] is False
    print("`por_confirmar` calcula-se da propria caixa, nao se escreve")


def caso_migrar_o_ficheiro_faz_backup():
    p = _TMP / "cfg-migrar.json"
    configio.escrever(json.loads(json.dumps(V5)), p)
    r = caixas.migrar_ficheiro(p, dry_run=True)
    assert r["mudou"] and r["caixas"] == 4 and r["backup"] is None
    assert "loadout" in json.loads(p.read_text(encoding="utf-8")), "dry-run escreveu"
    r = caixas.migrar_ficheiro(p)
    assert Path(r["backup"]).exists(), r
    assert json.loads(Path(r["backup"]).read_text(encoding="utf-8"))["loadout"], \
        "o backup tem de guardar o `loadout` de antes"
    novo = json.loads(p.read_text(encoding="utf-8"))
    assert "loadout" not in novo and len(novo["caixas"]) == 4
    # E as caixas continuam a ser uma linha cada — o ficheiro é para se ler.
    texto = p.read_text(encoding="utf-8")
    assert texto.count('{"slot"') == 4, texto[:400]
    print("migrar-caixas: backup do JSON ao lado, e uma linha por caixa")


def caso_o_config_a_serio_ja_esta_na_forma_nova():
    """O do André tem de estar migrado no repositório — senão a primeira coisa
    que o job diário faz é ler um formato que ninguém converteu."""
    cfg = json.loads((RAIZ / "colecao_config.json").read_text(encoding="utf-8"))
    assert cfg.get("caixas"), "o colecao_config.json ainda tem `loadout`"
    assert "loadout" not in cfg
    estados = {c["slot"]: c["estado"] for c in cfg["caixas"]}
    assert set(estados.values()) <= set(caixas.ESTADOS), estados
    assert estados["standard"] == "candidata" and estados["legacy"] == "candidata"
    assert estados["pauper"] == "montada"
    print(f"colecao_config.json: {len(cfg['caixas'])} caixas, estados {sorted(set(estados.values()))}")


def run():
    for fn in (caso_a_migracao_nao_muda_as_caixas,
               caso_a_chave_nova_fica_no_lugar_da_antiga, caso_e_idempotente,
               caso_o_motor_aceita_as_duas_formas, caso_a_escala_de_estados,
               caso_por_confirmar_deixa_de_ser_uma_chave,
               caso_migrar_o_ficheiro_faz_backup,
               caso_o_config_a_serio_ja_esta_na_forma_nova):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
