"""A IDENTIDADE de um arquétipo: pelo CONTEÚDO, não pelo rótulo.

O problema, medido: o *"Dimir Psychatog"* do ranking de Premodern passou a
*"Dimir Polluted Delta"* na corrida seguinte, e o *"Mono-Preto Graveborn Muse"* a
*"Mono-Preto Withered Wretch"*. Não é uma falha do clustering — o nome sai das
cartas mais distintivas do núcleo (`meta_coverage._name_for`), e o núcleo mexe um
bocadinho todos os dias porque a janela de 30 dias entra e sai listas.

Enquanto o nome era só um rótulo na página, isso era feio e mais nada. Deixou de
o ser em 2026-09-08, quando três decisões dele passaram a reconhecer-se **pelo
nome**:

  * uma **sugestão** de Premodern reconhece-se como já sendo uma caixa
    (`premodern._caixa_de`);
  * uma **recusa** (*"não quero este"*) fica escrita em
    `colecao_config.json → premodern.sugestoes_recusadas`;
  * uma **escolha** (*"vou montar este"*) congela a lista em `listas_escolhidas`.

Com o rótulo a mudar, a recusa de ontem deixa de bater hoje e a sugestão que ele
já disse que não queria volta — e as cartas dela saem outra vez da lista de
venda, sem ninguém ter carregado em nada. É o padrão do `event_tier`: nada dá
erro, só a resposta é que fica errada.

A REGRA
-------
O nome passa a ser **apresentação**. Quem liga as decisões ao arquétipo é um `id`
derivado do **núcleo de cartas**: as 8–12 mais distintivas do consenso,
ordenadas, com um hash curto por cima. Duas corridas que vejam o mesmo baralho
dão o mesmo `id` mesmo que lhe chamem coisas diferentes.

E porque o núcleo também mexe, o `id` **herda-se**: se o núcleo de hoje tem
≥ 70 % de cartas em comum com um arquétipo que este registo já conhece, é o mesmo
arquétipo — fica com o `id` e com o **nome** que já tinha. Sem esta segunda
metade, uma carta trocada num núcleo de doze gerava um hash novo e a identidade
mudava na mesma; o hash sozinho só resolveria o caso em que nada muda, que é
precisamente o caso que não dá problema.

O registo vive em `data/arquetipos.json` (ao lado da base, como o `vendas.csv`) e
o job diário actualiza-o. Vai para o Git de propósito: o `daily` corre no PC e
também no GitHub Actions, e um registo que só existisse num dos dois punha as
duas corridas a discordar sobre o nome — que é o defeito que isto vem corrigir.

Quem NOMEIA continua a ser quem já nomeava (as regras do
`premodern.combo_arquetipos`, o `meta_coverage.KNOWN`, o clustering). Este módulo
não inventa nomes: só decide quando dois núcleos são o mesmo arquétipo e, nesse
caso, faz o nome de ontem valer para hoje.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

# Quantas cartas fazem o núcleo. O mínimo existe para não dar identidade a um
# punhado de cartas (dois decks diferentes com 3 cartas em comum eram "o mesmo"),
# e o máximo para o núcleo não ser a lista inteira — uma lista inteira muda em
# todas as corridas e o `id` nunca estabilizava.
NUCLEO_MIN = 8
NUCLEO_MAX = 12

# A partir de que semelhança dois núcleos são o mesmo arquétipo. 0,70 sobre 12
# cartas quer dizer que até três podem trocar; uma carta trocada dá 0,92.
SEMELHANCA = 0.70

# Quanto tempo um arquétipo fica no registo depois de deixar de aparecer. É
# generoso de propósito: um arquétipo que sai do metagame um mês e volta tem de
# voltar com o mesmo nome. Os que estão referidos no config nunca se apagam.
DIAS_A_GUARDAR = 365

VERSAO = 1

# As básicas nunca entram no núcleo: estão em toda a gente e não distinguem nada.
BASICAS = {
    "Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
    "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes",
}


def ficheiro() -> Path:
    """`data/arquetipos.json`. Ao lado da base, não dentro dela: a `vault.db` é
    descarregada e republicada inteira a cada corrida.

    Quem sabe qual é essa pasta é o `db.pasta_dados()` — pelo `db.ROOT` este
    ficheiro ia parar fora do repositório neste PC, e o `git add` do `daily.yml`
    não encontrava nada.
    """
    from . import db                          # noqa: PLC0415  (ver loadout)
    return db.pasta_dados() / "arquetipos.json"


def nucleo(cartas, tecto: int = NUCLEO_MAX) -> list[str]:
    """O núcleo, a partir das cartas JÁ ORDENADAS por distintividade.

    Recebe-as ordenadas (é o que o `meta_coverage._distinctivas` devolve) e não
    as ordena por conta própria: quem sabe medir distintividade é quem tem o
    `card_roles` à frente. Aqui só se corta o topo, se tiram as básicas e se
    ordena por nome — a ordem alfabética é o que faz o hash não depender de uma
    heurística que muda de corrida para corrida.
    """
    vistas: list[str] = []
    for c in cartas:
        if c in BASICAS or c in vistas:
            continue
        vistas.append(c)
        if len(vistas) >= tecto:
            break
    return sorted(vistas)


def identidade(formato: str, nuc: list[str]) -> str:
    """O `id` estável: hash curto do (formato + núcleo ordenado).

    O formato entra no hash porque dois formatos podem ter o mesmo baralho — um
    Doomsday de Legacy e um de Premodern são decisões diferentes, e partilhar o
    `id` fazia a recusa de um apagar a sugestão do outro.
    """
    crua = formato + "\n" + "\n".join(nuc)
    return hashlib.sha1(crua.encode("utf-8")).hexdigest()[:10]


def semelhanca(a, b) -> float:
    """Quanto dois núcleos têm em comum, de 0 a 1.

    `|A ∩ B| / max(|A|, |B|)` e não Jaccard: o denominador é o maior dos dois,
    por isso um núcleo pequeno contido num grande não dá 100 % — dois decks de
    que um é meio do outro não são o mesmo deck.
    """
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa), len(sb))


class Registo:
    """`data/arquetipos.json`: id → nome, núcleo, primeira/última vez visto."""

    def __init__(self, dados: dict | None = None, caminho: Path | None = None):
        d = dados if isinstance(dados, dict) else {}
        self.caminho = caminho
        self.versao = d.get("versao", VERSAO)
        self.arquetipos: dict[str, dict] = {
            str(k): dict(v) for k, v in (d.get("arquetipos") or {}).items()
            if isinstance(v, dict)}
        self.mudou = False
        # Dentro de uma mesma passagem, dois clusters diferentes não podem herdar
        # o mesmo `id`: senão o segundo roubava a identidade do primeiro e as duas
        # linhas da página apareciam com o mesmo nome.
        self._usados: dict[str, tuple] = {}

    # -- ficheiro -----------------------------------------------------------
    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "Registo":
        p = Path(caminho) if caminho else ficheiro()
        try:
            return cls(json.loads(p.read_text(encoding="utf-8")), p)
        except (OSError, ValueError):
            # Sem ficheiro (ou com ele estragado) começa-se do zero: um registo
            # vazio dá nomes novos, não dá erro. Perder a estabilidade de um dia
            # é muito menos mau do que um `daily` que pára.
            return cls({}, p)

    def gravar(self, caminho: Path | None = None) -> Path | None:
        """Grava só se houve mudança. Devolve o caminho, ou `None` se não gravou."""
        p = Path(caminho) if caminho else (self.caminho or ficheiro())
        if not self.mudou:
            return None
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.dados(), ensure_ascii=False, indent=1,
                                    sort_keys=True) + "\n", encoding="utf-8")
        except OSError:
            # O registo é uma conveniência, não um dado da colecção: uma pasta
            # sem permissões não pode parar a corrida diária.
            return None
        self.mudou = False
        return p

    def dados(self) -> dict:
        return {"versao": self.versao,
                "arquetipos": {k: self.arquetipos[k]
                               for k in sorted(self.arquetipos)}}

    # -- identidade ---------------------------------------------------------
    def _parecido(self, formato: str, nuc: list[str]) -> str | None:
        """O arquétipo conhecido mais parecido com este núcleo, se passar o corte."""
        melhor, pontos = None, SEMELHANCA
        for aid, a in self.arquetipos.items():
            if a.get("formato") != formato or aid in self._usados:
                continue
            s = semelhanca(nuc, a.get("nucleo") or [])
            if s >= pontos:
                melhor, pontos = aid, s
        return melhor

    def resolver(self, formato: str, nuc: list[str], nome: str,
                 por_regra: bool = False, hoje: str | None = None) -> dict:
        """`{id, nome, novo, herdado, semelhanca}` para este núcleo.

        `por_regra` diz que o `nome` vem de uma REGRA (o `combo_arquetipos`, o
        `KNOWN`) e não do clustering. Nesse caso é ele que manda e fica escrito:
        uma regra é uma decisão dele, e um nome guardado de ontem não a pode
        contradizer. Sem regra, herda-se o nome que o registo já tinha — é isso
        que faz o *"Dimir Psychatog"* não passar a *"Dimir Polluted Delta"*.
        """
        hoje = hoje or date.today().isoformat()
        nuc = list(nuc)
        aid = identidade(formato, nuc)
        herdado, sem = False, 1.0
        if aid not in self.arquetipos:
            # O hash bate ao certo só quando NADA mudou — que é o caso que não dá
            # problema. É a herança por semelhança que resolve o caso real.
            outro = self._parecido(formato, nuc)
            if outro:
                aid, herdado = outro, True
                sem = semelhanca(nuc, self.arquetipos[outro].get("nucleo") or [])
        a = self.arquetipos.get(aid)
        novo = a is None
        if novo:
            a = {"formato": formato, "nome": nome, "nucleo": nuc,
                 "primeira": hoje, "ultima": hoje}
            self.arquetipos[aid] = a
            self.mudou = True
        else:
            if por_regra and nome and a.get("nome") != nome:
                a["nome"], self.mudou = nome, True
            elif not a.get("nome") and nome:
                a["nome"], self.mudou = nome, True
            if a.get("nucleo") != nuc:
                a["nucleo"], self.mudou = nuc, True
            if a.get("ultima") != hoje:
                a["ultima"], self.mudou = hoje, True
        self._usados[aid] = tuple(nuc)
        return {"id": aid, "nome": a["nome"], "novo": novo, "herdado": herdado,
                "semelhanca": round(sem, 3)}

    def nome_de(self, aid: str) -> str:
        return (self.arquetipos.get(aid) or {}).get("nome", "")

    # -- manutenção ---------------------------------------------------------
    def podar(self, dias: int = DIAS_A_GUARDAR, proteger=()) -> list[str]:
        """Esquece os arquétipos que não aparecem há muito tempo.

        Menos os que estão REFERIDOS no config (uma recusa, uma escolha, uma
        caixa): esses são decisões dele, e apagar a entrada fazia a decisão
        deixar de bater — que é exactamente o que este módulo existe para evitar.
        """
        limite = (date.today() - timedelta(days=max(0, dias))).isoformat()
        fora = [aid for aid, a in self.arquetipos.items()
                if aid not in set(proteger) and (a.get("ultima") or "") < limite]
        for aid in fora:
            del self.arquetipos[aid]
        self.mudou = self.mudou or bool(fora)
        return fora
