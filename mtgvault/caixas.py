"""As CAIXAS: a única noção de deck do vault (André, 2026-09-08).

Palavras dele: *"No mtgvault já começamos a ter informação duplicada. Temos
decks vigiados e deckbox que é a mesma coisa. Tenta revisar isso e implementar
melhorias."*

O que havia até aqui eram **duas** estruturas para o mesmo objecto:

  * a `watchlist` (tabela `watched` + `decks_vigiados` no config), que alimentava
    a página *Decks permanentes* (`meusdecks.html`) — onde cada deck contava a
    **colecção inteira**;
  * o `loadout` (config), que alimenta a *Deckboxes* — onde a colecção é
    **repartida** e uma cópia só serve uma caixa.

Duas páginas, dois números para a mesma pergunta ("quanto tenho deste deck?"), e
a diferença explicada em rodapé. É o mesmo padrão que já custou caro no
`event_tier` e no filtro de listas: duas opiniões, nenhum erro, páginas
diferentes em silêncio.

Desde a v6 há **uma** estrutura: `colecao_config.json → caixas`. Cada caixa é um
deck e um deck é uma caixa. A `watchlist` não desapareceu — deixou de ser um
conceito paralelo e passou a ser **a fonte de uma caixa**: o `watch-check` do
daily continua a seguir a lista do Luffy e do Blue Farm, e o que ele traz é a
lista da caixa (o delta *"actualizar deck"* é o resultado disso).

A CAIXA
-------
    {"slot": "pauper", "nome": "Pauper (Luffy)", "formato": "pauper",
     "fonte": "vigiado", "ref": "Luffy — Pauper", "balde": "Pauper Affinity",
     "estado": "montada", "prioridade": 1, "notas": ""}

  `fonte` — de onde vem a lista:
      `vigiado`   a etiqueta de um `watched` (jogador do MTGO ou deck do
                  Moxfield): a lista é o último snapshot que o `watch-check`
                  trouxe. É o URL/jogador que já estava na watchlist;
      `deck`      um nome na tabela `decks` (o que o `my_decks`/`commander_decks`/
                  `premodern_decks` mantêm actualizado);
      `consenso`  calculado das listas que contam, identificado por `assinatura`;
      `escolhido` o *"vou montar este"*: um arquétipo escolhido por ele, com a
                  lista CONGELADA e datada em `listas_escolhidas[slot]`;
      `manual`    a lista escrita à mão na própria caixa (`cards`).
  `estado` — uma escala, não quatro bandeiras soltas:
      `candidata` só recebe o que sobrar dos permanentes, e para o resto diz
                  *"em <caixa>"* em vez de mandar comprar;
      `permanente` aloca antes de qualquer candidata (*"os decks que eu pedi
                  para serem permanentes são a minha prioridade máxima!"*);
      `montada`   está fisicamente sleevada na deckbox (implica permanente: uma
                  caixa que está montada na estante não é uma candidata);
      `congelada` montada + dedicada: as cópias lá dentro não saem nem são
                  realocadas, e a diferença para a lista de hoje sai como delta
                  de actualização.
  As **regras de material** herdam-se do grupo de formato (`regras_por_formato`)
  e escrevem-se aqui só para abrir excepção — `lingua`, `acabamento`, `edicoes`,
  `baldes`, `estrita`, `dedicado`, `compras_dedicadas`.
  `notas` — texto livre, mostrado no cartão da caixa.

PORQUE É QUE O `congelada` NÃO SE GRAVA
---------------------------------------
Ele é o único dos quatro que se **calcula**: uma caixa está congelada quando é
`montada`, é `dedicado`, e o vault sabe o que lá está dentro (tem linhas na
`copy_allocation`). Guardá-lo seria a terceira cópia da mesma verdade. Escrever
`"estado": "congelada"` no config é legítimo e vale exactamente `montada` — o
motor recalcula o resto.

COMPATIBILIDADE
---------------
`para_slot` aceita as duas formas e devolve sempre a interna (com `permanente` e
`montado` em booleano), por isso o motor de alocação por baixo não mudou uma
linha — é o que garante o compromisso da v6: **nenhum número da alocação muda**.
Uma base ou um config da v5 continuam a funcionar; a migração
(`python -m mtgvault.cli migrar-caixas`) é uma reescrita do ficheiro, com backup.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from . import configio, sources

# A escala de estados, do menos para o mais comprometido. A ordem importa:
# `montada` implica permanente, e `congelada` implica montada.
CANDIDATA, PERMANENTE, MONTADA, CONGELADA = ("candidata", "permanente",
                                             "montada", "congelada")
ESTADOS = (CANDIDATA, PERMANENTE, MONTADA, CONGELADA)
# As fontes de lista que uma caixa pode ter (ver o cabeçalho).
FONTES = ("vigiado", "deck", "consenso", "escolhido", "manual")

# A ordem por que as chaves se escrevem no config — é um ficheiro para se ler.
ORDEM = ("slot", "nome", "formato", "fonte", "ref", "assinatura", "cards",
         "balde", "estado", "prioridade", "variantes", "notas",
         "lingua", "acabamento", "edicoes", "baldes", "estrita", "dedicado",
         "compras_dedicadas")


def estado_de(d: dict) -> str:
    """O `estado` de uma caixa, venha ela na forma v6 ou v5.

    Na v5 eram três chaves independentes (`permanente`, `montado`,
    `por_confirmar`) e nada impedia a combinação sem sentido "montado mas
    candidato" — um deck que está sleevado na estante não é um candidato a nada.
    """
    e = (d.get("estado") or "").strip().lower()
    if e in ESTADOS:
        return MONTADA if e == CONGELADA else e
    if d.get("montado"):
        return MONTADA
    # Sem a chave `permanente`, a caixa é permanente: era o que as catorze do
    # loadout eram antes de a distinção existir, e um default a `False` esvaziava
    # a alocação de quem não a escrevesse.
    return PERMANENTE if bool(d.get("permanente", True)) else CANDIDATA


def para_slot(d: dict) -> dict:
    """Uma caixa (v6 ou v5) na forma INTERNA que o motor de alocação consome.

    Uma função só, e idempotente: é ela que faz o `loadout` inteiro continuar a
    ver os mesmos campos de sempre, e por isso a unificação não mexe num único
    número da alocação.
    """
    s = {k: v for k, v in d.items() if not str(k).startswith("_")}
    estado = estado_de(d)
    s["estado"] = estado
    s["permanente"] = estado != CANDIDATA
    s["montado"] = estado == MONTADA
    # `por_confirmar` deixou de ser uma chave: é uma caixa sem lista escolhida, e
    # isso lê-se na própria caixa. Tê-lo escrito à mão deixava-o a mentir sempre
    # que ele escolhia um deck e ninguém apagava a bandeira.
    s["por_confirmar"] = not s.get("ref") and (s.get("fonte") or "") != "consenso"
    s.pop("notas", None)
    s["nota_config"] = (d.get("notas") or "").strip()
    return s


def de_slot_v5(d: dict) -> dict:
    """Uma linha do `loadout` da v5 na forma de CAIXA da v6 (a migração)."""
    caixa = {k: v for k, v in d.items()
             if k not in ("permanente", "montado", "por_confirmar", "estado")}
    caixa["estado"] = estado_de(d)
    caixa.setdefault("notas", "")
    return {k: caixa[k] for k in ORDEM if k in caixa} | {
        k: v for k, v in caixa.items() if k not in ORDEM}


def migrar_config(cfg: dict) -> tuple[dict, bool]:
    """`loadout` -> `caixas` dentro de um config já lido. Devolve (cfg, mudou).

    Não apaga o `loadout` por apagar: reescreve o ficheiro com a chave nova no
    lugar da antiga, e a antiga sai. Uma corrida em cima de um config já
    migrado não faz nada (é idempotente), que é o que permite chamá-la sem medo
    à cabeça de qualquer leitura.
    """
    if cfg.get("caixas"):
        return cfg, False
    velhas = cfg.get("loadout")
    if not isinstance(velhas, list) or not velhas:
        return cfg, False
    novo: dict = {}
    for k, v in cfg.items():
        if k == "loadout":
            novo["caixas"] = [de_slot_v5(s) for s in velhas]
            novo["_caixas"] = AJUDA
        elif k == "_loadout":
            continue                      # a ajuda antiga é substituída pela nova
        else:
            novo[k] = v
    if "caixas" not in novo:              # config sem `loadout` mas com `_loadout`
        novo["caixas"] = [de_slot_v5(s) for s in velhas]
        novo["_caixas"] = AJUDA
    return novo, True


AJUDA = (
    "AS CAIXAS: a única noção de deck do vault (André, 2026-09-08: 'temos decks "
    "vigiados e deckbox que é a mesma coisa'). Substitui o `loadout` da v5 e a "
    "lista `decks_vigiados` como definição de deck. Um deck é uma caixa. "
    "Campos: 'slot' = o id (não mudar, é a chave da copy_allocation); 'nome' = "
    "como aparece nas páginas; 'formato' = decide as regras de material e a "
    "ordem da alocação (regras_por_formato); 'fonte' = de onde vem a lista — "
    "'vigiado' (etiqueta da tabela `watched`, o jogador/URL que o watch-check "
    "segue), 'deck' (nome na tabela `decks`), 'consenso' (calculado das listas "
    "que contam, identificado por 'assinatura'), 'escolhido' (o «vou montar "
    "este»: lista congelada e datada em `listas_escolhidas`) ou 'manual' "
    "(lista escrita à mão em 'cards'); 'ref' = o nome nessa fonte (null = caixa "
    "por escolher, fica vazia de propósito — não se escolhe por ele); 'balde' = "
    "a gaveta de onde as cartas saem; 'estado' = candidata | permanente | "
    "montada | congelada (escala: montada implica permanente; congelada = "
    "montada + dedicada e é CALCULADA, escrevê-la vale montada); 'prioridade' = "
    "desempate DENTRO do grupo de formato; 'variantes' = outros decks que "
    "partilham a caixa; 'notas' = texto livre mostrado no cartão. As regras de "
    "material ('lingua', 'acabamento', 'edicoes', 'baldes', 'estrita', "
    "'dedicado', 'compras_dedicadas') herdam-se do grupo de formato e só se "
    "escrevem aqui para abrir excepção. Marca-se tudo isto no MODO EDIÇÃO "
    "(python webapp.py, porto 8771 — no telemóvel com o QR)."
)


def do_config(cfg: dict | None = None) -> list[dict]:
    """As caixas do config, já na forma v6 (migra em memória se for preciso)."""
    cfg = cfg if cfg is not None else sources.config()
    if cfg.get("caixas"):
        return [{k: c[k] for k in c if not str(k).startswith("_")}
                for c in cfg["caixas"]]
    return [de_slot_v5(s) for s in (cfg.get("loadout") or [])]


def slots(cfg: dict | None = None) -> list[dict]:
    """As caixas na forma interna — é o que o `loadout.config_slots` devolve."""
    return [para_slot(c) for c in do_config(cfg)]


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------
def caixa_do_cfg(cfg: dict, slot_id: str) -> dict:
    """A caixa `slot_id` DENTRO do config (o objecto, para se lhe mexer)."""
    for c in cfg.get("caixas") or []:
        if c.get("slot") == slot_id:
            return c
    raise KeyError(slot_id)


def por_estado(cfg: dict, slot_id: str, estado: str) -> str:
    """Põe a caixa num estado. Devolve uma frase para o toast."""
    if estado not in ESTADOS:
        raise ValueError(estado)
    c = caixa_do_cfg(cfg, slot_id)
    c["estado"] = MONTADA if estado == CONGELADA else estado
    return c.get("nome") or slot_id


def migrar_ficheiro(path: Path | str | None = None, dry_run: bool = False) -> dict:
    """Reescreve o `colecao_config.json` no formato v6, com BACKUP do JSON.

    O backup é ao lado (`colecao_config-v5-<data>.json`) e não em `data/`: este
    ficheiro vai no Git e é o único sítio onde vivem as regras todas — perdê-lo
    é perder as caixas, as regras de material e as listas escolhidas de uma vez.
    """
    p = configio.caminho(path)
    cfg = json.loads(p.read_text(encoding="utf-8"))
    novo, mudou = migrar_config(cfg)
    res = {"path": str(p), "mudou": mudou, "caixas": len(novo.get("caixas") or []),
           "backup": None}
    if not mudou or dry_run:
        return res
    marca = datetime.now().strftime("%Y-%m-%d")
    bkp = p.with_name(f"{p.stem}-v5-{marca}{p.suffix}")
    if not bkp.exists():
        shutil.copyfile(p, bkp)
    res["backup"] = str(bkp)
    configio.escrever(novo, p)
    sources._CFG_CACHE.clear()
    return res
