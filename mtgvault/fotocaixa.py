"""A FOTO DA DECKBOX FÍSICA de cada caixa (André, 2026-09-21, à letra):

    *"quero poder tirar foto à deckbox onde vai ficar cada deck, para ser
    referência também"*

Uma foto por caixa (`slot`): a caixa de plástico/cartão onde o deck vive na
estante, não as cartas — para ele reconhecer de que caixa a página está a
falar quando está à frente da prateleira com o telemóvel.

ONDE FICA, E PORQUÊ EM DOIS SÍTIOS
----------------------------------
  * o ORIGINAL em `data/deckboxes/<slot>.<ext>` — fora do Git, como tudo o que
    está em `data/` (uma foto de telemóvel são 3–8 MB; quinze delas no
    repositório eram 100 MB de histórico por cada vez que ele as trocasse).
    Substituir a foto **guarda a anterior** em `data/deckboxes/anteriores/`
    com a data no nome. Nunca se apaga nada — é a regra de todas as fotos do
    vault (2026-09-08).
  * a VERSÃO REDUZIDA (≤ `LADO_MAX` px, JPEG, ~100 KB) em
    `assets/deckboxes/<slot>.jpg`, **dentro do repositório**: é o que o site
    publicado mostra. É a EXCEPÇÃO CONSCIENTE à regra «não guardar imagens»
    do CLAUDE.md — essa regra é para a BASE DE DADOS; treze ficheiros de
    100 KB no Git são aceitáveis, e sem eles o site publicado (que só vê o
    Git) não tinha a foto.
  * a DATA em `colecao_config.json → caixas[].foto` (`{"em", "ficheiro"}`):
    é uma preferência da caixa, viaja no Git com as outras, e é por ela que
    a página diz «foto de 2026-09-21» e o cartão sabe que há foto sem ir ao
    disco.

DOIS CAMINHOS DE ENTRADA, UM SÓ DESTINO
---------------------------------------
  (a) no 8771, na aba da caixa, o botão «📦 Foto da deckbox» — um
      `<input type="file" capture="environment">`, que no telemóvel abre a
      câmara — manda o ficheiro em `POST /api/foto-caixa?slot=…` (com token);
  (b) largar `pendentes/deckboxes/<slot>.jpg`: o `daily` e o modo edição
      recolhem-na (`recolher`). É uma SUBPASTA de `pendentes/` de propósito:
      o `mtg-fotos-novas` (`PEND.iterdir()` + `is_file()`) e o
      `collection.arrumar_fotos` (`pend / nome`) só olham para ficheiros na
      RAIZ de `pendentes/` — uma foto de uma caixa de plástico nunca pode ir
      parar ao Claude que cataloga cartas. Tem teste.

Os dois acabam em `guardar`, que é a única função que escreve.

A REDUÇÃO precisa do Pillow. Sem ele (`SemPillow`) o original copia-se tal e
qual para `assets/` e a resposta di-lo — é pior para o Git, mas é a verdade;
inventar uma redução que não se fez era o padrão do `event_tier`.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import os
import shutil
from pathlib import Path

from . import db

# A raiz do repositório: onde vivem `assets/` e `pendentes/`. Os testes
# apontam-na para uma pasta temporária (como o `webapp.ROOT`).
RAIZ = Path(__file__).resolve().parents[1]
# Onde fica a versão reduzida (no Git) e a original (fora dele).
ASSETS_REL = Path("assets") / "deckboxes"
PENDENTES_REL = Path("pendentes") / "deckboxes"
ANTERIORES = "anteriores"
# O lado maior da versão reduzida, e o tamanho a que se tenta chegar.
LADO_MAX = 800
ALVO_BYTES = 110_000
# O que se aceita. O `.heic` do iPhone entra como original (é a foto dele),
# mas só se reduz se o Pillow o souber abrir — ver `reduzir`.
TIPOS = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
         "heic": "image/heic"}
# Uma foto de telemóvel são 3–8 MB; acima disto não é uma foto, é um engano.
MAX_BYTES = 25 * 1024 * 1024


class FotoInvalida(ValueError):
    """O ficheiro não é uma imagem que se aceite (ou a caixa não existe)."""


class SemPillow(RuntimeError):
    """Não há Pillow para reduzir a imagem."""


def pasta_originais(pasta_dados: Path | None = None) -> Path:
    """`data/deckboxes/` — ao lado da base (`db.pasta_dados()`), como o
    `arquetipos.json`: neste PC o `MTGVAULT_HOME` não está definido e pelo
    `ROOT` isto ia parar a `~/mtgvault`, fora do repositório."""
    return Path(pasta_dados) if pasta_dados else Path(db.pasta_dados()) / "deckboxes"


def pasta_assets(raiz: Path | None = None) -> Path:
    return Path(raiz or RAIZ) / ASSETS_REL


def pasta_pendentes(raiz: Path | None = None) -> Path:
    return Path(raiz or RAIZ) / PENDENTES_REL


def tipo_da_imagem(dados: bytes) -> str | None:
    """A extensão pelos PRIMEIROS BYTES, nunca pelo nome: um `.jpg` que é um
    `.txt` renomeado não é uma foto. `None` = não é imagem que se aceite."""
    if dados[:3] == b"\xff\xd8\xff":
        return "jpg"
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "webp"
    if len(dados) > 12 and dados[4:8] == b"ftyp" and dados[8:12] in (
            b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heif"):
        return "heic"
    return None


def reduzir(dados: bytes, lado_max: int = LADO_MAX,
            alvo: int = ALVO_BYTES) -> bytes:
    """A versão para o site: JPEG, lado maior ≤ `lado_max`, qualidade a
    descer até caber em ~`alvo` bytes (nunca abaixo de 60 — a partir daí a
    foto deixa de servir de referência). Respeita a orientação EXIF: as fotos
    de telemóvel vêm deitadas com a etiqueta a dizer «roda-me», e sem isto a
    deckbox aparecia de lado no site."""
    try:
        from PIL import Image, ImageOps                    # noqa: PLC0415
    except ImportError as e:                               # pragma: no cover
        raise SemPillow("o Pillow não está instalado (pip install Pillow)") from e
    try:
        im = Image.open(io.BytesIO(dados))
        im.load()
    except Exception as e:                                 # noqa: BLE001
        raise FotoInvalida(f"não consegui ler a imagem ({type(e).__name__}: {e}) "
                           f"— grava-a em JPEG e tenta outra vez") from e
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((lado_max, lado_max))
    for q in (85, 78, 70, 62, 60):
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= alvo:
            break
    return buf.getvalue()


def _caixa(cfg: dict, slot: str) -> dict:
    for c in cfg.get("caixas") or []:
        if c.get("slot") == slot:
            return c
    raise FotoInvalida(f"a caixa {slot!r} não existe no colecao_config.json")


def _escrever(destino: Path, dados: bytes) -> None:
    """Atómico (temporário + `os.replace`): o `daily` e o 8771 podem escrever
    o mesmo ficheiro, e o site não pode servir meia imagem."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_name(destino.name + ".tmp")
    tmp.write_bytes(dados)
    os.replace(tmp, destino)


def guardar(cfg: dict, slot: str, dados: bytes, *, origem: str = "",
            quando: _dt.datetime | None = None, raiz: Path | None = None,
            pasta_dados: Path | None = None) -> dict:
    """A ÚNICA escrita: valida, arquiva a anterior, grava o original e a
    reduzida, e escreve a data na caixa do `cfg` (quem chama grava o config).

    Devolve `{slot, nome, ext, original, reduzida, bytes_original,
    bytes_reduzida, anterior, aviso}`. Levanta `FotoInvalida` (a página dá
    409) sem ter escrito nada: a validação e a redução vêm ANTES do primeiro
    ficheiro tocado.
    """
    if not dados:
        raise FotoInvalida("o ficheiro veio vazio")
    if len(dados) > MAX_BYTES:
        raise FotoInvalida(f"o ficheiro tem {len(dados) / 1e6:.1f} MB — o máximo "
                           f"é {MAX_BYTES // (1024 * 1024)} MB")
    ext = tipo_da_imagem(dados)
    if ext is None:
        raise FotoInvalida("isto não é uma imagem (JPEG, PNG, WebP ou HEIC)"
                           + (f" — {origem}" if origem else ""))
    caixa = _caixa(cfg, slot)
    aviso = ""
    try:
        pequena = reduzir(dados)
    except SemPillow as e:
        # Sem Pillow não se reduz; fica o original e diz-se. Um HEIC sem
        # Pillow ia para o site tal e qual, que os browsers não abrem —
        # nesse caso é mesmo recusa.
        if ext == "heic":
            raise FotoInvalida("HEIC precisa do Pillow para se converter — grava "
                               "a foto em JPEG") from e
        pequena, aviso = dados, f"sem Pillow: a versão do site é o original ({len(dados) // 1024} KB)"

    quando = quando or _dt.datetime.now().replace(microsecond=0)
    orig_dir = pasta_originais(pasta_dados)
    orig = orig_dir / f"{slot}.{ext}"
    # A anterior guarda-se com a data em que foi SUBSTITUÍDA (é o que se sabe
    # de certeza); o original pode ter outra extensão do que o novo.
    anterior = None
    for velho in orig_dir.glob(f"{slot}.*"):
        if velho.suffix.lower().lstrip(".") in TIPOS or velho.suffix.lower() == ".jpeg":
            dest = orig_dir / ANTERIORES / f"{slot}-{quando:%Y%m%d-%H%M%S}{velho.suffix}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(velho), str(dest))
            anterior = dest
    _escrever(orig, dados)
    red = pasta_assets(raiz) / f"{slot}.jpg"
    _escrever(red, pequena)
    caixa["foto"] = {"em": quando.isoformat(timespec="seconds"), "ficheiro": orig.name}
    return {"slot": slot, "nome": caixa.get("nome") or slot, "ext": ext,
            "original": str(orig), "reduzida": str(red),
            "bytes_original": len(dados), "bytes_reduzida": len(pequena),
            "anterior": str(anterior) if anterior else None, "aviso": aviso}


_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _marca(f: Path) -> tuple:
    st = f.stat()
    return (st.st_size, st.st_mtime_ns)


def pendentes(raiz: Path | None = None, ignorar: dict | None = None) -> list[Path]:
    """Os ficheiros de imagem em `pendentes/deckboxes/`, menos os que
    `ignorar` (`{nome: (tamanho, mtime)}`) já viu tal e qual."""
    p = pasta_pendentes(raiz)
    if not p.is_dir():
        return []
    out = []
    for f in sorted(p.iterdir()):
        if not f.is_file() or f.suffix.lower() not in _EXTS:
            continue
        if ignorar is not None and ignorar.get(f.name) == _marca(f):
            continue
        out.append(f)
    return out


def ha_pendentes(raiz: Path | None = None, ignorar: dict | None = None) -> bool:
    """Há alguma coisa por recolher? Barato — é o que o 8771 pergunta a cada
    pedido do índice antes de pegar no lock de escrita."""
    return bool(pendentes(raiz, ignorar))


def recolher(cfg: dict, *, raiz: Path | None = None,
             pasta_dados: Path | None = None, ignorar: dict | None = None) -> dict:
    """O caminho (b): `pendentes/deckboxes/<slot>.<ext>` → `guardar`. O
    ficheiro recolhido MOVE-SE (é o próprio original que fica em
    `data/deckboxes/`); um nome que não é um `slot` fica onde está e vem em
    `ignorados`, com o porquê — não se adivinha a caixa pelo nome. Devolve
    `{recolhidas: [..], ignorados: [{ficheiro, porque}]}`; quem chama grava o
    config se `recolhidas` não vier vazio. `ignorar` (opcional) é o memo de
    quem chama: os ignorados ficam lá escritos e não se voltam a tentar
    enquanto o ficheiro não mudar.
    """
    out: dict = {"recolhidas": [], "ignorados": []}
    slots = {c.get("slot") for c in cfg.get("caixas") or []}
    for f in pendentes(raiz, ignorar):
        if f.stem not in slots:
            porque = f"{f.stem!r} não é o slot de nenhuma caixa"
        else:
            try:
                r = guardar(cfg, f.stem, f.read_bytes(), origem=f.name,
                            raiz=raiz, pasta_dados=pasta_dados)
            except FotoInvalida as e:
                porque = str(e)
            else:
                f.unlink()               # o original já está em `data/deckboxes/`
                out["recolhidas"].append(r)
                continue
        out["ignorados"].append({"ficheiro": f.name, "porque": porque})
        if ignorar is not None:
            ignorar[f.name] = _marca(f)
    return out


def versao(caminho: Path) -> str:
    """Um hash curto do conteúdo, para o `?v=` da imagem: o URL muda quando a
    foto muda, e o browser (e o GitHub Pages) podem guardá-la à vontade."""
    return hashlib.sha1(caminho.read_bytes()).hexdigest()[:10]


def info(caixa: dict, raiz: Path | None = None) -> dict | None:
    """O que a página precisa: `{em, url}` — ou `None` sem foto. A verdade é o
    FICHEIRO em `assets/`: uma data no config sem ficheiro (um clone novo
    antes do commit chegar) é «sem foto», e um ficheiro sem data mostra-se na
    mesma, sem data."""
    slot = caixa.get("slot") or ""
    f = pasta_assets(raiz) / f"{slot}.jpg"
    if not slot or not f.is_file():
        return None
    meta = caixa.get("foto") if isinstance(caixa.get("foto"), dict) else {}
    return {"em": (meta.get("em") or "")[:10],
            "url": f"{ASSETS_REL.as_posix()}/{slot}.jpg?v={versao(f)}"}
