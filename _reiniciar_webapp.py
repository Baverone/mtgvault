"""Mata o `webapp.py` que está de pé no porto 8771, para o vigia o relançar.

O modo edição fica de pé o dia todo (tarefa `ai-pc/tasks/mtgvault-serve`), e por
isso continua a correr o CÓDIGO com que arrancou: depois de mexer no `webapp.py`
ou no `deckboxes.py`, o que está no porto é a versão antiga. O vigia só relança
quando o porto está em baixo — por isso é preciso matá-lo primeiro.

Uso: `py _reiniciar_webapp.py` (na raiz do mtgvault). Só o 8771: o 8770 é do
`riftvault serve` e o 8773 do Treinador — matar por porto e não por nome de
processo é o que garante que não se leva um deles à frente.
"""
import socket
import subprocess
import sys
import time

PORTO = 8771


def pids_no_porto(porto=PORTO):
    """Os PIDs a OUVIR no porto (IPv4 `0.0.0.0:8771` ou IPv6 `[::]:8771`, tanto
    faz: o `endswith` apanha os dois). Só as linhas LISTENING — uma ligação de um
    cliente ao mesmo porto tem outro PID e não é o webapp."""
    saida = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace").stdout
    out = set()
    for linha in saida.splitlines():
        campos = linha.split()
        if len(campos) >= 5 and campos[0] == "TCP" and "LISTENING" in linha:
            if campos[1].endswith(f":{porto}"):
                out.add(campos[-1])
    return out


def vivo(porto=PORTO):
    s = socket.socket()
    s.settimeout(2)
    try:
        return s.connect_ex(("127.0.0.1", porto)) == 0
    finally:
        s.close()


def main():
    pids = pids_no_porto()
    if not pids:
        print(f"nada a ouvir no {PORTO}")
        return 0
    print("a matar:", ", ".join(sorted(pids)))
    for pid in pids:
        r = subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        print(" ", (r.stdout or r.stderr).strip())
    for _ in range(15):
        if not vivo():
            print(f"porto {PORTO} livre — o vigia `mtgvault-serve` relança em <=5 min "
                  f"(ou: py C:\\Users\\Catarina\\Desktop\\ai-pc\\runner.py run mtgvault-serve)")
            return 0
        time.sleep(1)
    print(f"o porto {PORTO} continua ocupado")
    return 1


if __name__ == "__main__":
    sys.exit(main())
