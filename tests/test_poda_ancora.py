"""A poda do histórico de preços guarda a ÂNCORA do início da janela (2026-10-30).

O `price_history` só guarda MUDANÇAS, e o `nucleo.valor.preco(dia=…)` procura a
última linha com `date <= dia`. Uma carta que valia 5 € a D-40 e passou a 6 € a
D-10 ficava, depois da poda a 30 dias, SEM preço a D-30: a linha de D-40 ia-se
e a de D-10 é posterior. Medido na cópia da base de 30/10: 14 474 das 34 664
impressões do Cardmarket. A «variação num mês» do Painel e a série perdiam
exactamente as cartas que mexeram.

Nada aqui abre a base do André: cada caso constrói a sua (`db.session` em
temporárias).
"""
import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily  # noqa: E402
from mtgvault import db, prices  # noqa: E402
from mtgvault.nucleo import valor  # noqa: E402


def dia(n):
    return (date.today() - timedelta(days=n)).isoformat()


def sessao():
    tmp = Path(tempfile.mkdtemp())
    return db.session(tmp / "v.db", tmp / "c.db")


def carta(con, sid, nome, reserved=0):
    con.execute(
        """INSERT INTO catalog.cards (scryfall_id, oracle_id, name, set_code,
           set_name, collector_number, lang, rarity, type_line, cmc,
           color_identity, finishes, released_at, cardmarket_id, digital,
           set_type, reserved)
           VALUES (?,?,?,'tst','Test Set','1','en','rare','Artifact',0,'',?,
           '2020-01-01',1,0,'expansion',?)""",
        (sid, "or-" + sid, nome, json.dumps(["nonfoil", "foil"]), reserved))
    con.commit()


def cota(con, sid, d, trend, finish="nonfoil"):
    prices.write_prices(con, [(sid, "cardmarket", d, finish, trend, trend,
                               trend, None, "EUR")])


def caso_a_carta_que_mexeu_tem_preco_no_inicio_da_janela():
    """O exemplo da ordem: 5 € a D-40, 6 € a D-10 → a D-30 vale 5."""
    with sessao() as con:
        carta(con, "s-mexeu", "Mexeu")
        cota(con, "s-mexeu", dia(40), 5.0)
        cota(con, "s-mexeu", dia(10), 6.0)
        assert valor.preco(con, "s-mexeu", "nonfoil", dia(30)) == 5.0
        detalhe = daily._prune_prices(con, 30)
        p = valor.preco(con, "s-mexeu", "nonfoil", dia(30))
        assert p == 5.0, (
            f"depois da poda o preço a D-30 é {p!r}: a poda apagou a linha de "
            f"D-40, que era o preço em vigor quando a janela abre ({detalhe})")
        assert valor.preco(con, "s-mexeu", "nonfoil", dia(10)) == 6.0
        assert "âncora" in detalhe, detalhe
    print("a carta que mexeu continua a ter preço a D-30 depois da poda")


def caso_guarda_so_uma_ancora_por_chave():
    """O que se guarda a mais é UMA linha por (impressão, fonte, acabamento) com
    histórico antes do corte — nunca o histórico velho inteiro."""
    with sessao() as con:
        carta(con, "s-a", "A")
        carta(con, "s-b", "B")
        for i, n in enumerate((80, 70, 60, 50, 40)):         # cinco mudanças
            cota(con, "s-a", dia(n), 1.0 + i)
            cota(con, "s-a", dia(n), 2.0 + i, "foil")
        cota(con, "s-b", dia(5), 3.0)                         # só na janela
        daily._prune_prices(con, 30)
        velhas = con.execute(
            "SELECT scryfall_id, finish, date, trend FROM price_history"
            " WHERE date < ? ORDER BY scryfall_id, finish", (dia(30),)).fetchall()
        assert [tuple(r) for r in velhas] == [
            ("s-a", "foil", dia(40), 6.0), ("s-a", "nonfoil", dia(40), 5.0)], \
            [tuple(r) for r in velhas]
        assert valor.preco(con, "s-a", "foil", dia(30)) == 6.0
        assert valor.preco(con, "s-b", "nonfoil", dia(30)) is None, \
            "um preço que só começa dentro da janela continua sem preço antes"
    print("a poda guarda uma âncora por chave e apaga o resto do histórico velho")


def caso_a_reserved_list_e_o_catalogo_ficam_como_estavam():
    """A excepção da RL (guarda-se `fundo` dias) e o guarda do catálogo não
    mudam; a âncora só se soma a eles."""
    with sessao() as con:
        carta(con, "s-rl", "Drake", reserved=1)
        for n in (300, 200, 60, 40):
            cota(con, "s-rl", dia(n), float(n))
        fundo = int(daily._prune_prices(con, 30).split("guarda-se ")[1].split("d")[0])
        datas = [r[0] for r in con.execute(
            "SELECT date FROM price_history WHERE scryfall_id='s-rl' ORDER BY date")]
        esperadas = sorted(d for d in (dia(300), dia(200), dia(60), dia(40))
                           if d >= dia(fundo) or d == dia(40))
        assert datas == esperadas, (datas, esperadas, fundo)
        # catálogo vazio: não se apaga nada (o guarda de 2026-10-02)
        cota(con, "s-desconhecida", dia(90), 1.0)
        cota(con, "s-desconhecida", dia(80), 2.0)
        daily._prune_prices(con, 30)
        assert con.execute("SELECT COUNT(*) FROM price_history WHERE"
                           " scryfall_id='s-desconhecida'").fetchone()[0] == 2
    print("a RL e o guarda do catálogo ficam como estavam")


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("caso_"):
            f()
            print("ok", nome)
    print("TUDO OK")
