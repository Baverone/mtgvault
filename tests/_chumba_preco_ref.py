"""Corre UM caso do `test_preco_referencia` com UMA peça neutralizada.

Noutro processo, como o `_chumba_venda.py` e pela mesma razão: o módulo de teste
fixa o `MTGVAULT_CONFIG` e o `MTGVAULT_DB` no import, e importá-lo ao lado de
outro punha os dois a partilhar o mesmo ambiente.

    py tests/_chumba_preco_ref.py <alvo> <caso>

Sai 0 se o caso PASSOU (mau: a peça não fazia falta) e != 0 se chumbou (bom).
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))

alvo, nome = sys.argv[1], sys.argv[2]

import test_preco_referencia as T                            # noqa: E402
from mtgvault import collection, loadout, precos             # noqa: E402

if alvo == "preco_da_copia":
    # O mtgvault de ontem: uma cópia valia o MÍNIMO ENTRE IMPRESSÕES.
    def _minimo(con, sid, finish, nome_carta, cache=None):
        u, pf = loadout.card_price(con, nome_carta, finish)
        return {"unit": u, "price_finish": pf, "fonte": None,
                "origem": precos.ORIGEM_MIN_IMPRESSOES}
    loadout.preco_da_copia = _minimo

elif alvo == "regua_desde":
    # Só o carimbo do MODO, como ontem: trocar de fonte não travava nada.
    precos.regua_desde = precos.modo_desde

elif alvo == "fontes":
    # Uma fonte só, sem recurso: quem ela não cota fica sem preço.
    def _so_a_principal(cfg=None):
        b = precos.bloco(cfg)
        return (precos._fonte_limpa(b.get("fonte")) or "cardmarket",)
    precos.fontes = _so_a_principal

elif alvo == "cadeia_ordem":
    # A cadeia como um MIN entre fontes — o defeito que ela existe para evitar.
    _mapa = collection.mapa_precos

    def _min_entre_fontes(con, source=None):
        out = {c: {} for c in collection.CENARIOS}
        out["_fonte"] = {}
        for f in (precos.fontes() if source is None else (source,)):
            parte = _mapa(con, f)
            for c in collection.CENARIOS:
                for k, v in parte[c].items():
                    if out[c].get(k) is None or v < out[c][k]:
                        out[c][k] = v
                        out["_fonte"][k] = (f, None)
        return out
    collection.mapa_precos = _min_entre_fontes

elif alvo == "prune_marketplace":
    import daily
    daily._prune_marketplace = lambda con: 0

else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

try:
    getattr(T, nome)()
except AssertionError as e:
    print((str(e).splitlines() or ["(sem mensagem)"])[0][:110])
    sys.exit(1)
except Exception as e:                                       # noqa: BLE001
    print(f"{type(e).__name__}: {e}")
    sys.exit(1)
print("PASSOU sem a peca")
sys.exit(0)
