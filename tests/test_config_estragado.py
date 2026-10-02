"""Um `colecao_config.json` ilegível não pode passar por um config vazio.

É o ficheiro que o André EDITA À MÃO — o CLAUDE.md di-lo à letra: *"é um
ficheiro para ser LIDO por uma pessoa: cada regra tem a explicação em português
ao lado"*. Uma vírgula a mais e o `json.loads` levanta; o `sources._config`
apanhava-o e devolvia `{}`, **sem uma linha de aviso em lado nenhum**.

MEDIDO no config a sério a 2026-10-02, com uma vírgula a mais no fim:

    caixas            17  ->  0        (o loadout inteiro desaparece)
    venda congelada   até 12/10 -> NÃO (a trava do RC Ghent levanta-se)
    cadeia de preços  cardtrader->cardmarket  ->  só cardmarket
    revalidacao.foto_manda  True -> None      («se não tiver foto, não tem carta» desliga)

Nenhum erro, nenhum passo vermelho, nenhuma página a dizer nada. É o padrão do
`event_tier` sobre o ficheiro que guarda TODAS as decisões dele.

O que este ficheiro tranca:
  1. um config que deixa de fazer parse **não apaga o que já estava lido**: o
     processo fica com o último bom, e por isso nada muda debaixo dos pés;
  2. **diz-se**, com o caminho e o erro do JSON — e uma vez por alteração do
     ficheiro, não mil vezes por relatório;
  3. corrigir o ficheiro volta a pegar, e o aviso desaparece;
  4. um config AUSENTE continua a ser `{}` calado (é o caso normal de um
     checkout limpo e dos testes), e trocar de ficheiro continua a trocar.

Não toca na rede.
"""
import io
import json
import os
import sys
import tempfile
import time
from contextlib import redirect_stderr
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

_TMP = Path(tempfile.mkdtemp())
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py
P = _TMP / "cfg.json"
os.environ["MTGVAULT_CONFIG"] = str(P)

from mtgvault import sources  # noqa: E402

BOM = {"caixas": [{"slot": "a", "nome": "A", "formato": "legacy"}],
       "venda": {"congelado_ate": "2026-10-12"},
       "precos": {"fonte": "cardtrader", "fonte_recurso": ["cardmarket"]}}


def escreve(texto):
    """Escreve e garante que o `mtime` muda — o `_config` só relê quando muda,
    e num ficheiro pequeno duas escritas caem no mesmo tique do relógio."""
    P.write_text(texto, encoding="utf-8")
    novo = P.stat().st_mtime + 2
    os.utime(P, (novo, novo))
    time.sleep(0.01)


def ler():
    """Lê o config e devolve `(cfg, o que foi dito no stderr)`."""
    saida = io.StringIO()
    with redirect_stderr(saida):
        cfg = sources.config()
    return cfg, saida.getvalue()


# ---------------------------------------------------------------------------
def caso_um_config_estragado_nao_apaga_o_que_ja_estava_lido():
    """O ficheiro parte-se e o processo fica com o último bom."""
    escreve(json.dumps(BOM, ensure_ascii=False))
    cfg, _ = ler()
    assert len(cfg.get("caixas") or []) == 1, cfg
    assert not sources.config_estragado(), sources.config_estragado()

    escreve(json.dumps(BOM, ensure_ascii=False)[:-1] + ",}")   # vírgula a mais
    cfg, disse = ler()
    assert len(cfg.get("caixas") or []) == 1, (
        "o config estragado apagou as caixas: 17 decks, a trava da venda e a "
        "cadeia de preços desapareciam por causa de uma vírgula")
    assert (cfg.get("venda") or {}).get("congelado_ate") == "2026-10-12", cfg
    print("um config que deixou de fazer parse não apaga o que já estava lido")

    # 2. E DIZ-SE, com o caminho e o erro do JSON.
    assert "colecao_config" in disse or str(P) in disse, disse
    assert "linha" in disse.lower() or "line" in disse.lower(), disse
    mau = sources.config_estragado()
    assert mau and str(P) == mau["caminho"], mau
    print("e diz-se, no stderr e no `config_estragado()`:",
          disse.strip().splitlines()[0][:100])


def caso_o_aviso_nao_se_repete_a_cada_leitura():
    """O `_config()` é chamado milhares de vezes por relatório (o `precos.modo`,
    o `estado.factor`, todos por cópia). Um aviso por chamada era um log
    ilegível — e um log ilegível é um log que se deixa de ler."""
    _, primeira = ler()
    _, segunda = ler()
    _, terceira = ler()
    assert primeira == "" and segunda == "" and terceira == "", \
        (primeira, segunda, terceira)
    assert sources.config_estragado(), "mas continua a saber-se que está mau"
    print("o aviso sai uma vez por alteração do ficheiro, não por leitura")


def caso_corrigir_o_ficheiro_volta_a_pegar():
    novo = dict(BOM, caixas=BOM["caixas"] + [
        {"slot": "b", "nome": "B", "formato": "legacy"}])
    escreve(json.dumps(novo, ensure_ascii=False))
    cfg, disse = ler()
    assert len(cfg["caixas"]) == 2, cfg
    assert not sources.config_estragado(), sources.config_estragado()
    assert disse == "", disse
    print("corrigir o ficheiro volta a pegar e o aviso desaparece")


def caso_um_config_ausente_continua_a_ser_vazio_e_calado():
    """O caso normal de um checkout limpo (e de metade dos testes). Não é um
    erro: é um vault sem config."""
    falta = _TMP / "nao-existe.json"
    os.environ["MTGVAULT_CONFIG"] = str(falta)
    sources._CFG_CACHE.clear()
    try:
        cfg, disse = ler()
        assert cfg == {}, cfg
        assert disse == "", disse
        assert not sources.config_estragado(), sources.config_estragado()
    finally:
        os.environ["MTGVAULT_CONFIG"] = str(P)
        sources._CFG_CACHE.clear()
    print("um config ausente é `{}`, calado — não é uma avaria")


def caso_trocar_de_ficheiro_nao_herda_o_anterior():
    """O «último bom» é DESTE ficheiro. Apontar o `MTGVAULT_CONFIG` para outro
    que está estragado não pode devolver o conteúdo do primeiro — era um teste
    a passar por causa do config de outro teste."""
    outro = _TMP / "outro.json"
    outro.write_text("{nao sou json", encoding="utf-8")
    os.environ["MTGVAULT_CONFIG"] = str(outro)
    try:
        cfg, _ = ler()
        assert cfg == {}, ("herdou o config do ficheiro anterior", cfg)
    finally:
        os.environ["MTGVAULT_CONFIG"] = str(P)
        sources._CFG_CACHE.clear()
    print("trocar de ficheiro não herda o «último bom» do anterior")


def run():
    for fn in (caso_um_config_estragado_nao_apaga_o_que_ja_estava_lido,
               caso_o_aviso_nao_se_repete_a_cada_leitura,
               caso_corrigir_o_ficheiro_volta_a_pegar,
               caso_um_config_ausente_continua_a_ser_vazio_e_calado,
               caso_trocar_de_ficheiro_nao_herda_o_anterior):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
