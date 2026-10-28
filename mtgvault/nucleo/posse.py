"""A posse do núcleo: o que ele tem de cada carta e o que cada versão pede.

Por agora só existe o gancho que o `listas.gravar_versao` chama, dentro da mesma
transação, depois de gravar uma versão nova. A Task 3 enche-o (a posse que se
herda, as escolhas de edição que ficam por decidir); até lá não faz nada, e o
`listas` já chama a assinatura final.
"""
from __future__ import annotations

import sqlite3


def depois_de_versao(con: sqlite3.Connection, slug: str, antes: list,
                     depois: list, versao_id: int, origem: str) -> None:
    """Chamado por `listas.gravar_versao` na MESMA transação que grava a versão.

    `antes` e `depois` são as listas (`Linha`) normalizadas da versão anterior
    (vazia se for a primeira) e da nova. Se levantar, a versão não fica gravada.
    """
    return None
