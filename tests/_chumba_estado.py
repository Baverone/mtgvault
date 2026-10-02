"""Corre UM caso do `test_estado_versos` com uma peça da funcionalidade desligada.

`py tests/_chumba_estado.py <alvo> <nome_do_caso>` — sai a 0 se o caso passar (o
que é MAU: passa sem a funcionalidade) e ≠ 0 se chumbar (o que é bom). Está num
processo próprio porque o `test_estado_versos` fixa o `MTGVAULT_CONFIG`, o
`MTGVAULT_HOME` e o `MTGVAULT_DB` no import.

Cada `alvo` é o mtgvault de ANTES desta ordem numa peça só:

  factor     — o preço deixa de ter em conta o estado: é a cadeia de preços sem
               dimensão de estado nenhuma, que é o que ela era até 2026-10-03 —
               uma dual de Revised de 1994 vale o preço de uma impecável;
  medido     — o `NM` por omissão volta a passar por medido: a colecção inteira
               diz-se avaliada sem ninguém ter olhado para uma carta;
  verso      — deixa de se exigir verso: um escalão grava-se a partir da frente,
               que é exactamente o *"inventar"* que a ordem proíbe;
  par        — o emparelhamento frente/verso desaparece: a recolha da pasta do
               deck deixa de marcar o verso e nenhum par se faz;
  ganha      — a correcção dele deixa de ganhar: um juízo meu posterior
               sobrepõe-na, que é o contrário da ordem dele;
  aprende    — o ciclo que aprende desaparece: os exemplos rotulados e os erros
               repetidos deixam de existir e o critério deixa de crescer;
  curta      — a lista curta dos extras desaparece: ele volta a ter de decidir
               verso-ou-não com a carta na mão, 400 vezes;
  aproximado — o PL deixa de dizer que é interpolado: um número aproximado passa
               a ter cara de número medido;
  criterio   — o critério deixa de viver em ficheiro: volta a viver na cabeça de
               quem corre a tarefa.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

alvo, caso = sys.argv[1], sys.argv[2]

import test_estado_versos as T                                # noqa: E402
from mtgvault import collection, estado, fotos, loadout        # noqa: E402

if alvo == "factor":
    # O preço volta a ignorar o estado: é o `_com_estado` a não fazer nada, que é
    # o mtgvault de ontem — a `price_latest` tem low/trend/avg30 e mais nada.
    loadout._com_estado = lambda d, lot: d
    estado.aplicar = lambda unit, grade, **kw: {
        "unit": unit, "unit_nm": unit, "desconto": 0.0, "factor": 1.0,
        "grade": estado.normalizar(grade), "banda": 0, "banda_nome": "",
        "aproximado": False, "nota": "",
        "origem_estado": kw.get("origem") or estado.ORIGEM_OMISSAO,
        "medido": estado.medido(kw.get("origem"))}
elif alvo == "medido":
    estado.medido = lambda origem: True
elif alvo == "verso":
    # Deixa de se exigir verso: o escalão da frente grava-se. É o *"inventar"*.
    _reg = estado.registar

    def _sem_verso(con, ids, *, grade, motivos="", foto=None, verso=None,
                   verso_ok=None, dia=None, log_path=None):
        g = estado.normalizar(grade)
        fora = {"grade": g, "aplicado": [], "recusado": [], "porque": "",
                "verso": verso}
        for cid in [int(c) for c in dict.fromkeys(ids or ()) if c]:
            if g is None:
                continue
            r = _reg(con, cid, g, origem=estado.ORIGEM_FOTO, motivos=motivos,
                     photo_path=foto, dia=dia, log_path=log_path)
            (fora["aplicado"] if r["aplicado"] else fora["recusado"]).append(cid)
        con.commit()
        return fora

    estado.da_foto = _sem_verso
elif alvo == "par":
    # A recolha volta a não emparelhar: cada foto é uma frente, como até 02/10.
    import mtgvault.fotosite as fs
    fs.nome_do_verso = lambda nome: None
    fs.par_da_frente = lambda nome: None
    fs.e_verso = lambda nome: False
    _rec = fotos.recolher_das_pastas

    def _sem_pares(cfg=None, **kw):
        r = _rec(cfg, **kw)
        r["pares"] = 0
        r["sem_verso"] = []
        for x in r["recolhidas"]:
            x["verso"] = False
        return r

    fotos.recolher_das_pastas = _sem_pares
elif alvo == "ganha":
    # A correcção dele deixa de ganhar: um juízo meu posterior sobrepõe-na.
    def _sempre(con, copy_id, grade, *, origem, motivos="", photo_path=None,
                autor=None, dia=None, log_path=None):
        g = estado.normalizar(grade)
        if g is None:
            raise estado.EstadoInvalido(str(grade))
        antes = estado.actual(con, copy_id)
        con.execute(
            "UPDATE copies SET condition = ?, condition_origem = ?, "
            "condition_em = ?, condition_motivos = ? WHERE id = ?",
            (g, origem, estado._hoje(dia), motivos or None, int(copy_id)))
        con.execute(
            """INSERT INTO condition_log (copy_id, at, grade, antes,
                   antes_origem, origem, autor, photo_path, motivos, aplicado)
               VALUES (?,datetime('now'),?,?,?,?,?,?,?,1)""",
            (int(copy_id), g, antes["grade"], antes["origem"], origem,
             autor or "claude", photo_path, motivos or None))
        con.commit()
        return {"aplicado": True, "antes": antes["grade"], "grade": g,
                "origem": origem, "porque": ""}

    estado.registar = _sempre
elif alvo == "aprende":
    estado.exemplos = lambda con, limite=12: []
    estado.padroes = lambda con: []
    estado.acerto = lambda con: {"propostos": 0, "corrigidos": 0, "aceites": 0,
                                 "pct": None, "por_escalao": {}}
    estado.escrever_aprendido = lambda con, path=None: None
elif alvo == "curta":
    estado.lista_curta = lambda con, **kw: {
        "fotos": [], "linhas": [], "cartas": 0, "valor": 0.0, "cortadas": 0,
        "inclui_venda": False, "barra": {}, "porque": "", "nota": ""}
elif alvo == "aproximado":
    estado.APROXIMADOS = {}
    estado.nota_do_factor = lambda cfg=None: "preço por estado"
elif alvo == "criterio":
    estado.criterio = lambda: ""
    estado.ficheiro_criterio = lambda: Path(__file__).with_name("nao-existe.md")
else:                                                          # pragma: no cover
    print(f"alvo desconhecido: {alvo}")
    sys.exit(3)

fn = getattr(T, caso)
try:
    fn()
except AssertionError as e:
    print(f"  CHUMBOU (bom): {e}")
    sys.exit(1)
except Exception as e:                                         # noqa: BLE001
    print(f"  ERRO (conta como chumbar): {type(e).__name__}: {e}")
    sys.exit(1)
print("  PASSOU SEM A FUNCIONALIDADE (mau)")
sys.exit(0)
