"""O interruptor `nucleo.ligado` para os testes (2026-10-28).

O `colecao_config.json` do repositório tem o núcleo LIGADO. Os testes que
guardam o comportamento do site antigo (o menu de cinco secções, as catorze
páginas, o `daily` comprido) continuam a valer com ele DESLIGADO — é o que
acontece no dia em que o André o desligar —, e por isso correm sobre uma CÓPIA
temporária do config com `nucleo.ligado` posto à mão. O ficheiro dele nunca se
toca.

A cópia escreve-se com o `configio.escrever` (a forma de sempre) e o
`sources.esquecer_config()` limpa a cache, para o interruptor morder logo.
Tudo o que depende dele lê-o à CHAMADA (`site_shell.seccoes`, `publicar.PAGINAS`,
`daily.main`), por isso pode trocar-se a meio de um ficheiro de teste.
"""
from __future__ import annotations

import os
import shlex
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mtgvault import configio, sources  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def linha_antiga_do_yml() -> list[str]:
    """O que o `git add` do `daily.yml` levava ANTES do núcleo, tal como ficou
    escrito no comentário do workflow para quem desligar o interruptor.

    O `git add` a sério é hoje o das três páginas do núcleo; os testes do site
    antigo, que exigiam que uma página ou uma pasta fosse a esse `git add`,
    passam a exigir que vá a esta linha — a que se repõe com o interruptor
    desligado — e à lista do `publicar` desligado (a da tarefa de 30 min).
    """
    yml = (RAIZ / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    for l in yml.splitlines():
        s = l.strip()
        if s.startswith("#") and s.lstrip("# ").startswith("git add "):
            return shlex.split(s.lstrip("# "))[2:]
    raise AssertionError("o daily.yml perdeu a linha antiga do `git add`")


def config_com(ligado: bool) -> Path:
    """Uma cópia do config que está a ser lido agora, com `nucleo.ligado`."""
    try:
        cfg = configio.ler()
    except FileNotFoundError:
        cfg = {}
    bloco = dict(cfg.get("nucleo") or {})
    bloco["ligado"] = bool(ligado)
    cfg["nucleo"] = bloco
    p = Path(tempfile.mkdtemp(prefix="mtg-interruptor-")) / "colecao_config.json"
    configio.escrever(cfg, p)
    return p


def fixar(ligado: bool) -> Path:
    """Fixa o interruptor para o resto do processo (um ficheiro de teste
    inteiro). Herda-o também quem o teste lançar em subprocesso."""
    p = config_com(ligado)
    os.environ["MTGVAULT_CONFIG"] = str(p)
    sources.esquecer_config()
    return p


@contextmanager
def interruptor(ligado: bool):
    """O interruptor só dentro do `with`; à saída volta o config de antes."""
    antes = os.environ.get("MTGVAULT_CONFIG")
    os.environ["MTGVAULT_CONFIG"] = str(config_com(ligado))
    sources.esquecer_config()
    try:
        yield
    finally:
        if antes is None:
            os.environ.pop("MTGVAULT_CONFIG", None)
        else:
            os.environ["MTGVAULT_CONFIG"] = antes
        sources.esquecer_config()
