"""Corre UM caso do `test_pasta_por_deck` com uma peça da funcionalidade desligada.

`py tests/_chumba_pasta.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Quem o
chama é o `_provar_chumba.py`; está num processo próprio porque o
`test_pasta_por_deck` fixa o `MTGVAULT_CONFIG`, o `MTGVAULT_HOME` e o
`MTGVAULT_DB` no import, e partilhá-los com outro teste era pôr um a mexer no
ambiente do outro.

Cada `alvo` é o mtgvault de ANTES desta ordem numa peça só:

  mapa       — não há mapa pasta → slot: a pasta do deck deixa de valer como
               alvo e a foto fica lá para sempre, como até hoje;
  escrito    — o mapa volta a ser uma LISTA ESCRITA À MÃO (o nome de hoje de
               cada deck): funciona até ele renomear um deck, e aí falha calado;
  primeira   — o slot sai da pasta IMEDIATA da foto em vez da primeira abaixo da
               pasta-mãe: as subpastas de lote («lote1») deixam de contar;
  grupo      — as pastas de grupo passam a ser tratadas como um deck qualquer
               (e a adivinhar-se o deck pelo nome da pasta);
  recolhe    — a recolha deixa de MOVER com o nome do alvo: a foto ia para
               `pendentes/` com o nome original e perdia-se o deck;
  sossego    — o sossego desaparece: uma foto ainda a ser copiada mexe-se a meio;
  planos     — o `_plano.txt` volta a mandar largar as fotos em `pendentes\\` e
               a dizer que esta pasta não serve (a instrução da manhã de hoje);
  vazios     — a pasta de um deck sem cartas fica com o plano velho a prometer
               fotos que não existem;
  ip         — o endereço volta a ser o `http://<ip da rede local>:8771/`, que é
               exactamente o que ele pediu para não lhe ser dado.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_pasta_por_deck as T                               # noqa: E402
from mtgvault import fotos                                    # noqa: E402

if alvo == "mapa":
    fotos.mapa_pastas = lambda cfg=None: {}
elif alvo == "escrito":
    # A lista à mão, com os nomes de HOJE. É o que parece inofensivo e falha no
    # dia em que ele renomear um deck.
    _MAO = {"blue farm": "cedh-blue-farm", "elves survival": "premodern-elves",
            "modern uw oswald": "modern"}
    fotos.mapa_pastas = lambda cfg=None: dict(_MAO)
elif alvo == "primeira":
    # O slot pela pasta IMEDIATA da foto: «lote1» deixa de ser um deck.
    def _imediata(caminho, cfg=None):
        p = Path(str(caminho))
        return fotos.mapa_pastas(cfg).get(fotos._norm(p.parent.name))

    fotos.slot_da_pasta = _imediata
elif alvo == "grupo":
    # Toda a pasta passa a valer como um deck: o que a pasta não souber dizer
    # ADIVINHA-SE (cai no primeiro deck). É exactamente o que o `fotocaixa` já
    # tinha aprendido a não fazer — «não se adivinha a caixa pelo nome» —, e sem
    # esta defesa uma foto largada no `Vender\` entrava num deck.
    fotos.PASTAS_DE_GRUPO = ()
    _slot = fotos.slot_da_pasta
    fotos.slot_da_pasta = (lambda caminho, cfg=None:
                           _slot(caminho, cfg) or "cedh-blue-farm")
    _fnp = fotos.fotos_nas_pastas
    fotos.fotos_nas_pastas = (
        lambda cfg=None, raiz=None: [{**i, "slot": i["slot"] or "cedh-blue-farm",
                                      "grupo": False}
                                     for i in _fnp(cfg, raiz)])
elif alvo == "recolhe":
    # Mover sem renomear: a foto chega a `pendentes/` sem dizer o deck.
    import shutil

    def _sem_nome(cfg=None, *, raiz=None, agora=None, sossego_s=0):
        from mtgvault import fotosite
        pend = fotosite.pasta_pendentes(raiz)
        pend.mkdir(parents=True, exist_ok=True)
        out = {"recolhidas": [], "ignorados": [], "a_chegar": [], "pastas": 0,
               "destino": str(pend)}
        for i in _fnp2(cfg, raiz):
            if not i["slot"]:
                continue
            shutil.move(str(i["ficheiro"]), str(pend / i["ficheiro"].name))
            out["recolhidas"].append({"de": i["ficheiro"].name, "pasta": i["pasta"],
                                      "slot": i["slot"], "para": i["ficheiro"].name})
        out["pastas"] = len({x["pasta"] for x in out["recolhidas"]})
        return out

    _fnp2 = fotos.fotos_nas_pastas
    fotos.recolher_das_pastas = _sem_nome
elif alvo == "sossego":
    _rec = fotos.recolher_das_pastas
    fotos.recolher_das_pastas = (lambda cfg=None, **kw:
                                 _rec(cfg, **{**kw, "sossego_s": 0}))
elif alvo == "planos":
    # A instrução da MANHÃ de hoje: largar em `pendentes\` e «nada processa esta
    # pasta». O plano continua certo nas cartas — o que muda é para onde ele é
    # mandado, que é a decisão da tarde.
    _td = fotos.texto_do_plano

    def _antigo(nome, slot, fotos_, *, conversao=False, nota=""):
        t = _td(nome, slot, fotos_, conversao=conversao, nota=nota)
        velho = ("ONDE LARGAR AS FOTOS: soltas na RAIZ de  pendentes\\\n"
                 "NAO as largues nesta pasta: NADA a processa.\n")
        corte = t.index("=" * 70)
        return t[:t.index("ONDE LARGAR")] + velho + "\n" + t[corte:]

    fotos.texto_do_plano = _antigo
elif alvo == "vazios":
    _ep = fotos.escrever_planos

    def _sem_vazios(con, res, cfg=None, raiz=None):
        r = _ep(con, {**res, "slots": []}, cfg, raiz)
        r["vazios"] = []
        return r

    fotos.escrever_planos = _sem_vazios
elif alvo == "ip":
    import webapp

    webapp.ligacao_local = lambda port=None: {
        "ip": "192.168.1.70", "ips": ["192.168.1.70"],
        "porto": webapp.PORT, "token": webapp.token(),
        "url": f"http://192.168.1.70:{webapp.PORT}/?t={webapp.token()}"}
else:
    raise SystemExit(f"alvo {alvo!r} desconhecido")

getattr(T, caso)()
print(f"PASSOU sem «{alvo}» — o caso {caso} não está a testar nada")
