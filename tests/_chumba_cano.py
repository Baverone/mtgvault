"""Corre UM caso do `test_cano_fotos` com uma peça da funcionalidade desligada.

`py tests/_chumba_cano.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Está num
processo próprio porque o `test_cano_fotos` fixa o `MTGVAULT_CONFIG`, o
`MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ANTES desta ordem numa peça só:

  extras     — a pasta `Extras (fora dos decks)\\` volta a não estar ligada a
               nada: as fotos ficam lá para sempre e a tarefa diz «sem fotos
               novas», verde;
  chave      — o `_chave` volta a devolver `("coleccao",)` para o alvo da
               colecção, que é um grupo que a `particao` nunca produz: o alvo
               fica sem cópias e a correcção por discrepância (0b) não dispara;
  prova      — a trava da foto repetida desaparece: a mesma foto volta a poder
               ser prova de duas cartas físicas;
  nome       — a trava passa a comparar o `photo_path` INTEIRO em vez do nome do
               ficheiro: depois do `arrumar_fotos` o caminho leva a pasta do deck
               à frente (`fotos/<slot>/x.jpg`) e a comparação deixa de bater —
               é o erro fácil de cometer aqui;
  carta      — a trava passa a ser pela CARTA e não pela FOTO: trava a mais, e
               ele perde a segunda cópia a sério de uma carta que tem duas;
  pastas     — ninguém cria a pasta de um deck que não a tenha: 7 dos 17 decks
               ficam sem o caminho que ele escolheu;
  orfas      — o `_plano.txt` de uma pasta cujo deck morreu fica como estava, a
               mandá-lo largar fotos que ninguém vai catalogar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_cano_fotos as T                                   # noqa: E402
from mtgvault import fotos, revalidacao                       # noqa: E402

if alvo == "extras":
    fotos.PASTAS_FORA_DOS_DECKS = ()

    def _so_caixas(caminho, cfg=None):
        s = fotos.slot_da_pasta(caminho, cfg)
        return {"tipo": "caixa", "slot": s} if s else None

    fotos.alvo_da_pasta = _so_caixas
    _fnp = fotos.fotos_nas_pastas
    fotos.fotos_nas_pastas = (
        lambda cfg=None, raiz=None: [dict(i, tipo="caixa" if i["slot"] else None)
                                     for i in _fnp(cfg, raiz)])
elif alvo == "chave":
    revalidacao._chave = (lambda a: ("caixa", a["slot"]) if a["tipo"] == "caixa"
                          else (a["tipo"],))
elif alvo == "prova":
    fotos.ja_e_prova = lambda *a, **k: False
elif alvo == "nome":
    def _inteiro(con):
        """A chave pelo `photo_path` tal e qual, sem `Path(...).name`."""
        out: dict = {}
        for r in con.execute(
                """SELECT cp.photo_path, c.name, c.set_code, c.collector_number,
                          cp.language, cp.finish
                     FROM copies cp JOIN cards c ON c.scryfall_id = cp.scryfall_id
                    WHERE cp.photo_path IS NOT NULL AND cp.photo_path <> ''"""):
            out.setdefault(str(r["photo_path"]).casefold(), set()).add(
                fotos._chave_impressao(r["name"], r["set_code"],
                                       r["collector_number"], r["language"],
                                       r["finish"]))
        return out

    fotos.consumidas = _inteiro
    fotos.ja_e_prova = (lambda idx, pp, nm, sc, num, lang, fin:
                        bool(pp) and str(pp).casefold() in (idx or {}))
elif alvo == "carta":
    # Pela CARTA e não pela foto: qualquer cópia com foto daquela impressão
    # trava a linha. Parece mais seguro e perde cartas.
    def _por_carta(idx, pp, nm, sc, num, lang, fin):
        chave = fotos._chave_impressao(nm, sc, num, lang, fin)
        for impressoes in (idx or {}).values():
            for k in impressoes:
                if (k[0], k[1], k[3], k[4]) == (chave[0], chave[1], chave[3],
                                                chave[4]):
                    return True
        return False

    fotos.ja_e_prova = _por_carta
elif alvo == "pastas":
    fotos.garantir_pastas = lambda res, raiz=None: []
elif alvo == "orfas":
    _ep = fotos.escrever_planos

    def _sem_orfas(con, res, cfg=None, raiz=None):
        r = _ep(con, res, cfg, raiz)
        r["orfas"] = []
        return r

    # e, a sério, o texto não se troca: repõe-se o plano a mentir
    fotos.TEXTO_ORFA = "LARGA AS FOTOS NESTA PASTA\n"
    fotos.escrever_planos = _sem_orfas
else:
    raise SystemExit(f"alvo desconhecido: {alvo}")

getattr(T, caso)()
print("PASSOU SEM A FUNCIONALIDADE (mau)")
