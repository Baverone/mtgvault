"""`_reiniciar_webapp.py`: mata só quem OUVE no 8771, e nunca o 8770/8773.

Sem rede e sem processos: o `netstat` e o `taskkill` são substituídos por
funções que devolvem um trecho real de `netstat -ano` e registam os PIDs que
seriam mortos. O que se tranca é o que já correu mal uma vez noutro sítio — os
portos são fixos (8770 riftvault, 8771 mtgvault, 8773 Treinador) e um `endswith`
mal feito (`"8771" in linha`) apanhava uma ligação de cliente com porto remoto
8771 ou um porto local 18771.
"""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
# O script não toca na base, mas a regra da bateria é para todos: quem fixa o
# `MTGVAULT_HOME` fixa o `MTGVAULT_DB`, e nunca para dentro do repositório.
_TMP = Path(tempfile.mkdtemp(prefix="mtgvault-reiniciar-"))
os.environ["MTGVAULT_HOME"] = str(_TMP)
os.environ["MTGVAULT_DB"] = str(_TMP / "vault.db")   # ver tests/_bateria.py

import _reiniciar_webapp as rw  # noqa: E402

NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1234
  TCP    0.0.0.0:8770           0.0.0.0:0              LISTENING       4001
  TCP    0.0.0.0:8771           0.0.0.0:0              LISTENING       4002
  TCP    0.0.0.0:18771          0.0.0.0:0              LISTENING       4003
  TCP    127.0.0.1:8771         127.0.0.1:53422        ESTABLISHED     4002
  TCP    127.0.0.1:53422        127.0.0.1:8771         ESTABLISHED     4004
  TCP    [::]:8771              [::]:0                 LISTENING       4005
  TCP    [::]:8773              [::]:0                 LISTENING       4006
  UDP    0.0.0.0:8771           *:*                                    4007
"""


class _Saida:
    def __init__(self, stdout="", stderr=""):
        self.stdout, self.stderr = stdout, stderr


def caso_so_quem_ouve_no_8771():
    chamadas = []

    def run_falso(cmd, **kw):
        chamadas.append(cmd)
        if cmd[0] == "netstat":
            return _Saida(NETSTAT)
        return _Saida("SUCCESS: The process with PID %s has been terminated." % cmd[-1])

    rw.subprocess.run = run_falso
    pids = rw.pids_no_porto()
    # 4002 (IPv4) e 4005 (IPv6) ouvem no 8771. Ficam de fora: o riftvault (8770),
    # o Treinador (8773), o 18771, o cliente ligado AO 8771 (4004), a ligação
    # estabelecida (não é LISTENING) e o UDP.
    assert pids == {"4002", "4005"}, pids
    print("ouvem no 8771:", sorted(pids))


def caso_mata_e_espera_pelo_porto():
    mortos = []
    estado = {"vivo": True}

    def run_falso(cmd, **kw):
        if cmd[0] == "netstat":
            return _Saida(NETSTAT)
        assert cmd[:3] == ["taskkill", "/F", "/PID"], cmd
        mortos.append(cmd[3])
        estado["vivo"] = False
        return _Saida("SUCCESS")

    rw.subprocess.run = run_falso
    rw.vivo = lambda porto=rw.PORTO: estado["vivo"]
    rw.time.sleep = lambda s: None
    assert rw.main() == 0
    assert sorted(mortos) == ["4002", "4005"], mortos
    print("matou", sorted(mortos), "e o porto ficou livre")


def caso_sem_nada_a_ouvir_nao_mata():
    mortos = []

    def run_falso(cmd, **kw):
        if cmd[0] == "netstat":
            return _Saida(NETSTAT.replace(":8771 ", ":9999 "))
        mortos.append(cmd)
        return _Saida("")

    rw.subprocess.run = run_falso
    assert rw.main() == 0 and not mortos, mortos
    print("sem webapp de pe: nao mata ninguem")


def run():
    for fn in (caso_so_quem_ouve_no_8771, caso_mata_e_espera_pelo_porto,
               caso_sem_nada_a_ouvir_nao_mata):
        fn()
    print("\nTUDO OK")


if __name__ == "__main__":
    run()
