"""Corre UM caso do `test_so_cardtrader` com UMA peca neutralizada.

Noutro processo, como o `_chumba_preco_ref.py` e pela mesma razao: o modulo de
teste fixa o `MTGVAULT_CONFIG` e o `MTGVAULT_DB` no import.

    py tests/_chumba_so_cardtrader.py <alvo> <caso>

Sai 0 se o caso PASSOU (mau: a peca nao fazia falta) e != 0 se chumbou (bom).
Sem argumentos, corre os pares todos e resume.
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))

# (alvo, caso) — o que se desliga e o caso que tem de chumbar por causa disso.
PARES = [
    ("cadeia_com_recurso", "caso_sem_cotacao_no_cardtrader_e_sem_preco_e_nao_zero"),
    ("cadeia_com_recurso", "caso_o_preco_da_copia_nao_cai_calado_para_outra_fonte"),
    ("config_antigo", "caso_o_config_a_serio_esta_numa_fonte_so"),
    ("sem_preco_e_zero", "caso_sem_cotacao_no_cardtrader_e_sem_preco_e_nao_zero"),
    ("paginas_antigas", "caso_nenhuma_pagina_gerada_diz_cardmarket_no_texto_visivel"),
    ("serie_calada", "caso_a_reserved_list_diz_que_a_serie_e_nova_em_vez_de_deixar_a_coluna_vazia"),
    ("serie_no_cardmarket", "caso_a_serie_segue_a_cadeia_e_nao_fica_no_cardmarket"),
    ("vendor_cardmarket", "caso_o_vendor_passou_a_loja_e_a_forma_antiga_continua_a_ler_se"),
    ("recurso_ignorado", "caso_o_cli_aceita_esvaziar_a_cadeia_e_carimba_a_regua"),
]


def _todos() -> int:
    maus = []
    for alvo, caso in PARES:
        r = subprocess.run([sys.executable, __file__, alvo, caso],
                           capture_output=True, text=True, encoding="utf-8")
        ok = r.returncode == 0
        print(f"  {'MAU (passou)' if ok else 'chumbou (bom)':<16} {alvo} -> {caso}")
        if ok:
            maus.append((alvo, caso))
    print(f"\n{len(PARES) - len(maus)}/{len(PARES)} pares chumbam como devem")
    return 1 if maus else 0


if len(sys.argv) < 3:
    sys.exit(_todos())

alvo, nome = sys.argv[1], sys.argv[2]

import test_so_cardtrader as T                               # noqa: E402
from mtgvault import collection, feira, precos               # noqa: E402

if alvo == "cadeia_com_recurso":
    # O vault de ontem: o Cardmarket atras, calado, a tapar o buraco.
    _real = precos.fontes
    precos.fontes = lambda cfg=None: ("cardtrader", "cardmarket")

elif alvo == "config_antigo":
    # O config como estava a 2026-10-03.
    #
    # GUARDA-SE E REPOE-SE O **TEXTO**, nao o JSON (corrigido a 2026-10-04, no
    # mesmo dia em que isto foi escrito). A primeira versao fazia
    # `json.loads` -> `json.dumps` e repunha o conteudo CERTO com a FORMA
    # destruida: o `colecao_config.json` — 657 linhas, uma por objecto, com a
    # explicacao em portugues ao lado — ficou numa linha so, e o diff dava
    # «1 insercao, 657 remocoes». E exactamente o commit `ac1f776`, disparado
    # pela ferramenta que devia ser inofensiva. Um ficheiro que se restaura
    # byte a byte nao tem forma para perder.
    import atexit
    import json
    _p = T.RAIZ / "colecao_config.json"
    _texto = _p.read_text(encoding="utf-8")
    atexit.register(lambda: _p.write_text(_texto, encoding="utf-8"))
    from mtgvault import configio
    _alt = json.loads(_texto)
    _alt["precos"]["fonte_recurso"] = ["cardmarket"]
    _alt["precos"]["fonte_desde"] = "2026-09-25"
    _alt["precos"].pop("fonte_serie", None)
    configio.escrever(_alt, _p)        # preserva a forma tambem a meio do teste

elif alvo == "sem_preco_e_zero":
    # «Sem preco» a valer 0 EUR — a mentira mais cara que uma pagina de precos
    # pode contar, e a que a regra dele de 25/09 proibe.
    _real_det = collection.preco_impressao_detalhe

    def _zero(mapa, sid, finish, cenario=None):
        d = _real_det(mapa, sid, finish, cenario)
        if d["preco"] is None:
            d = dict(d, preco=0.0, fonte=precos.fonte())
        return d
    collection.preco_impressao_detalhe = _zero

elif alvo == "paginas_antigas":
    # Uma pagina com a legenda de ontem, escrita na arvore e desfeita no fim.
    _p = T.RAIZ / "_chumba_pagina.html"
    _p.write_text("<html><body><p>imagens e precos via Scryfall/Cardmarket"
                  "</p></body></html>", encoding="utf-8")
    import atexit
    atexit.register(lambda: _p.unlink(missing_ok=True))

elif alvo == "serie_calada":
    # A pagina a deixar a coluna vazia sem dizer porque, como antes de hoje.
    import reservedlist
    reservedlist.frase_serie = lambda con: ""

elif alvo == "serie_no_cardmarket":
    # A serie fixa no price guide, em vez de seguir a cadeia.
    precos.fonte_serie = lambda cfg=None: "cardmarket"

elif alvo == "vendor_cardmarket":
    # O campo do vendor como estava: `cardmarket`, e so ele.
    def _velhos(cfg=None):
        out = []
        for v in feira.bloco(cfg)["vendors"]:
            if isinstance(v, dict) and (v.get("nome") or "").strip():
                out.append({"nome": v["nome"].strip(),
                            "notas": v.get("notas") or "",
                            "cardmarket": v.get("cardmarket") or "",
                            "site": v.get("site") or ""})
        return out
    feira.vendors = _velhos

elif alvo == "recurso_ignorado":
    # Um `gravar_fonte` que ignora uma lista de recurso VAZIA — o bug classico
    # do `if recurso:` em vez de `if recurso is not None:`.
    _real_grav = precos.gravar_fonte

    def _ignora(nova, recurso=None, path=None, hoje=None):
        return _real_grav(nova, recurso or None, path=path, hoje=hoje)
    precos.gravar_fonte = _ignora

else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

getattr(T, nome)()
print("PASSOU (mau)")
