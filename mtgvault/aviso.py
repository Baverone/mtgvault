"""Um AVISO DO WINDOWS, para o que ele tem de saber sem ir procurar.

Nasceu para a VIGIA DE CARTAS (2026-09-26): o valor dela é ele ser avisado **no
dia** em que a primeira decklist com o combo aparece, e uma linha no stdout de um
job que corre às 03:30 não avisa ninguém.

O PADRÃO É O QUE O `ai-pc` DESCREVE, e teve de ser escrito
-----------------------------------------------------------
O `ai-pc/prompts/baiakidle-coach.md` descreve-o à letra — *"um toast do Windows
(`powershell` BurntToast se existir; senão `msg`/balloon stdlib)"* — mas a tarefa
que o faria (`baiak-relogio`) **não existe** em `ai-pc/tasks/`: varrido o
repositório a 2026-09-26, não há uma única linha de código que emita um toast.
Por isso reaproveita-se a RECEITA e não código que não há, e fica aqui: o
`mtgvault` é quem tem hoje uma pergunta cuja resposta vale um aviso.

TRÊS DECISÕES QUE VALEM ESTAR ESCRITAS
- **`-EncodedCommand`, não `-Command`.** O texto leva nomes de cartas com
  apóstrofos (*"It'll Quench Ya!"*) e acentos, e o `-Command` obriga a escapar à
  mão e passa pelo code page da consola. O base64 em UTF-16LE é o que o próprio
  PowerShell usa para não ter de escapar nada.
- **NUNCA LEVANTA.** Um aviso que rebenta apaga o passo do daily que o disparou —
  e o passo é que é o trabalho; o toast é o mensageiro. Devolve sempre uma
  string a DIZER o que aconteceu (`"toast (balloon)"`, `"sem toast: …"`), e é essa
  string que vai para o registo: um toast que não apareceu tem de se distinguir
  de um toast que ninguém viu.
- **O `correr` é injectável.** É assim que o teste prova que o toast dispara uma
  vez e não duas, sem abrir uma janela no PC dele.
"""
from __future__ import annotations

import base64
import shutil
import subprocess

# Quanto tempo o balão fica no ecrã, e quanto tempo se espera pelo PowerShell.
# O balão do `NotifyIcon` morre com o processo que o criou — daí o `Start-Sleep`
# lá dentro, e daí o prazo aqui ter de ser maior do que ele.
TEMPO_MS = 20000
ESPERA_S = 8
PRAZO_S = 30

# As duas marcas que o script imprime. É por elas que se sabe qual dos dois
# caminhos correu — «funcionou» e «funcionou pelo caminho B» não são a mesma
# informação no dia em que ele disser que não viu nada.
MARCAS = ("burnttoast", "balloon")


def _script(titulo: str, texto: str) -> str:
    """O PowerShell que mostra o aviso e imprime por que caminho o fez."""
    t = titulo.replace("'", "''")
    x = texto.replace("'", "''")
    return f"""
$ErrorActionPreference = 'Stop'
if (Get-Module -ListAvailable -Name BurntToast) {{
  Import-Module BurntToast
  New-BurntToastNotification -Text '{t}', '{x}' | Out-Null
  'burnttoast'
}} else {{
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  $n = New-Object System.Windows.Forms.NotifyIcon
  $n.Icon = [System.Drawing.SystemIcons]::Information
  $n.Visible = $true
  $n.ShowBalloonTip({TEMPO_MS}, '{t}', '{x}', [System.Windows.Forms.ToolTipIcon]::Info)
  Start-Sleep -Seconds {ESPERA_S}
  $n.Dispose()
  'balloon'
}}
"""


def _correr(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=PRAZO_S)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def toast(titulo: str, texto: str, *, correr=None, exe=None) -> str:
    """Mostra um aviso do Windows. Devolve o que aconteceu, em português.

    Nunca levanta: quem chama isto está a meio de um passo do daily.
    """
    prog = exe or shutil.which("powershell") or shutil.which("pwsh")
    if not prog:
        return "sem toast: nao encontrei o powershell no PATH"
    codificado = base64.b64encode(
        _script(titulo, texto).encode("utf-16-le")).decode("ascii")
    try:
        code, out, err = (correr or _correr)(
            [prog, "-NoProfile", "-NonInteractive", "-EncodedCommand", codificado])
    except Exception as e:                                        # noqa: BLE001
        return f"sem toast: {e!r}"
    marca = (out.splitlines() or [""])[-1].strip().lower()
    if code == 0 and marca in MARCAS:
        return f"toast ({marca})"
    return f"sem toast: {(err or out or f'codigo {code}').strip()[:200]}"
