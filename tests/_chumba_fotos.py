"""Corre UM caso do `test_fotos_ate_4` com uma peça da regra das fotos desligada.

`py tests/_chumba_fotos.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o
`test_fotos_ate_4` fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o `MTGVAULT_DB`
no import, e partilhá-los com outro teste era pôr um a mexer no ambiente do
outro.

Cada `alvo` é o mtgvault de ONTEM numa peça só:

  ate4       — o tecto das 4 cartas desaparece: uma foto volta a levar o que lhe
               caia, que é o monte de 33 cartas das antigas, e a trava do import
               deixa de recusar;
  por_tipo   — deixa de se agrupar por tipo: as fotos atravessam tipos, que é
               exactamente o contrário de *"organiza por tipo de carta"*;
  resolver   — o resolvedor volta a ser `ROOT / photo_path`, que é o de ontem:
               com os `photo_path` dele (nomes simples) devolvia `None` a TODAS
               as 723 linhas com foto, e não encontrava nada no arquivo;
  perdidas   — a foto perdida deixa de se marcar: as 33 cópias sem prova nenhuma
               voltam a ser cópias como as outras;
  por_deck   — as fotos novas voltam ao saco único por mês, em vez de
               `data/fotos/<slot>/`;
  conversao  — a ordem de trabalho desaparece: os decks «de conversão» voltam a
               poder vir à frente dos de lista única;
  nao_pisa   — o arquivo volta a pisar um ficheiro com o mesmo nome (e a perder
               a prova que lá estava).
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_fotos_ate_4 as T                                 # noqa: E402
from mtgvault import collection, fases, fotos                # noqa: E402

if alvo == "ate4":
    _ag = fotos.agrupar
    fotos.agrupar = lambda linhas, **kw: _ag(
        linhas, **{**kw, "max_cartas": 10 ** 6})
    _sempre = lambda cartas, max_cartas=fotos.MAX_CARTAS: int(cartas or 0) > 0  # noqa: E731
    fotos.valida = _sempre
    # O `revalidacao` importa o `valida` por nome no topo (`foto_valida`), por
    # isso tem de se desligar também lá — senão o `fotos_que_nao_validam`
    # continuava a aplicar o tecto e o caso passava sem a funcionalidade.
    from mtgvault import revalidacao as _rv                  # noqa: E402

    _rv.foto_valida = _sempre
elif alvo == "por_tipo":
    _ag = fotos.agrupar
    fotos.agrupar = lambda linhas, **kw: _ag(
        linhas, **{**kw, "por_tipo": False})
elif alvo == "resolver":
    # O resolvedor de ontem, à letra.
    def _antigo(photo_path):
        if not photo_path:
            return None
        p = Path(str(photo_path))
        if not p.is_absolute():
            p = collection.ROOT / p
        return p if p.is_file() else None

    fotos.resolver = _antigo
    fotos.perdidas = lambda paths: {x for x in paths if x and _antigo(x) is None}
    fotos.copias_sem_foto_no_disco = lambda con: {}
elif alvo == "perdidas":
    fotos.copias_sem_foto_no_disco = lambda con: {}
elif alvo == "por_deck":
    # O saco único por mês, debaixo de `pendentes/`.
    def _saco(nome, alvo_cfg, raiz, fotos_mod):
        return collection.PENDENTES / f"fotos processadas/{dt.date.today():%Y-%m}"

    collection._destino_da_foto = _saco
    _pd = collection._pasta_dados
    collection._pasta_dados = lambda: collection.PENDENTES
elif alvo == "conversao":
    fases.de_conversao = lambda res, cfg=None: {}
elif alvo == "nao_pisa":
    import shutil

    _arq = fotos.arquivar

    def _pisa(pendentes=None, destino=None):
        origem = (Path(pendentes) / "fotos processadas" if pendentes
                  else collection.FOTOS_PROCESSADAS)
        alvo_ = Path(destino) if destino else fotos.pasta_arquivo()
        alvo_.mkdir(parents=True, exist_ok=True)
        movidas, outros = [], []
        for f in sorted(x for x in origem.rglob("*") if x.is_file()):
            if f.suffix.lower() not in fotos.EXT:
                outros.append(f.name)
                continue
            shutil.move(str(f), str(alvo_ / f.name))     # PISA
            movidas.append(f.name)
        fotos._CACHE.clear()
        return {"movidas": len(movidas), "ja_la": 0, "outros": len(outros),
                "bytes": 1, "destino": str(alvo_), "lista": movidas,
                "lista_ja_la": []}

    fotos.arquivar = _pisa
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
