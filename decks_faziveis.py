"""RETIRADO (2026-09-07) — fundido no `metagame.py`. Já NÃO corre no daily.

Esta página ("Decks fazíveis") mostrava os decks do top-10 que o André já tinha
a pelo menos X% (`decks_faziveis_min_pct`). A pergunta era a mesma que ele fez
nesse dia — *"dás-me só o top-3 decks que estou mais perto de concluir"* — e a
resposta era pior, por três razões que valem a pena ficar escritas:

  * contava **cartas distintas do main da lista mais recente**, não cópias nem a
    lista de consenso: um deck com 4 cópias de uma carta que ele tem 1 contava
    como tido;
  * **ignorava as regras de material** do loadout (foil menos Reserved List, PT
    no Premodern), por isso dava como tidas cartas que não podem entrar na caixa;
  * **não sabia onde está a carta** — uma cópia já alocada a outra caixa contava
    como livre, e não havia forma de distinguir "vou lá buscar" de "tenho de
    comprar".

O `metagame.html` responde agora à mesma pergunta com a alocação do loadout
atrás. O ficheiro fica como lápide (o `decksfaziveis.html` reencaminha para lá);
podem os dois ser apagados quando quiseres — não são importados por ninguém nem
entram no `daily.py`.
"""

AVISO = ("decks_faziveis foi retirado em 2026-09-07: a pergunta passou para o "
         "metagame.html (top-N que estás mais perto de concluir).")


def build(con, out_path=None):     # noqa: ARG001
    raise RuntimeError(AVISO)


if __name__ == "__main__":
    print(AVISO)
