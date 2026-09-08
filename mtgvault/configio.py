"""Ler e gravar o `colecao_config.json` sem lhe estragar a forma.

Estava dentro do `webapp.py`, onde só o servidor lhe chegava. A migração para as
`caixas` (v6) também precisa de escrever o ficheiro, e uma segunda cópia da
função de formatação era garantia de os dois divergirem — o ficheiro é para ser
lido por uma pessoa, é lá que estão as explicações em português de cada regra.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# As chaves cujo conteúdo se escreve com um elemento por linha. São listas de
# objectos curtos que se lêem melhor assim — e é como o ficheiro está hoje, à
# mão. Reformatá-las com `indent=2` dava um diff de 200 linhas por cada clique.
UMA_LINHA = ("caixas", "loadout", "regras_por_formato", "baldes_coleccao",
             "decks_vigiados", "premodern_arquetipos_alvo", "formatos_metagame",
             "so_jogadores_vigiados", "premodern_decks_completos",
             "decks_montados", "reserved_vender_ignorar_formatos")


def caminho(path: Path | str | None = None) -> Path:
    """O `colecao_config.json` que o motor está a ler NESTE momento.

    Lê-se a cada chamada (e não uma vez no import) porque tem de ser o MESMO
    ficheiro que o `sources.config()` lê: escrever num e ler do outro dava um
    botão que "não faz nada" sem erro nenhum — o padrão que este vault já pagou.
    """
    if path:
        return Path(path)
    return Path(os.environ.get("MTGVAULT_CONFIG")
                or Path(__file__).resolve().parents[1] / "colecao_config.json")


def ler(path: Path | str | None = None) -> dict:
    return json.loads(caminho(path).read_text(encoding="utf-8"))


def escrever(cfg: dict, path: Path | str | None = None) -> None:
    """Grava o config mantendo a forma com que está escrito à mão.

    Um `json.dump(indent=2)` cru rebentava as catorze linhas das caixas em
    duzentas.

    Escreve-se **atomicamente** (ficheiro temporário ao lado + `os.replace`):
    o `write_text` normal trunca o ficheiro antes de escrever, e um erro a meio
    — ou dois pedidos ao mesmo tempo, que o `ThreadingHTTPServer` permite — dava
    um `colecao_config.json` truncado. Perder esse ficheiro é perder as caixas,
    as regras de material e as listas escolhidas de uma vez.
    """
    partes = []
    for k, v in cfg.items():
        chave = json.dumps(k, ensure_ascii=False)
        if k in UMA_LINHA and isinstance(v, list):
            itens = ",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in v)
            corpo = f"[\n{itens}\n  ]" if v else "[]"
        else:
            corpo = json.dumps(v, ensure_ascii=False, indent=2)
            corpo = corpo.replace("\n", "\n  ")
        partes.append(f"  {chave}: {corpo}")
    destino = caminho(path)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_text("{\n" + ",\n".join(partes) + "\n}\n", encoding="utf-8")
    os.replace(tmp, destino)
