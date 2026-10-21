# Galeria — revisão de 2026-10-21

Estado: ALTERAÇÕES — código aprovado por leitura; validação conjunta por concluir. Não publicar: bateria vermelha e ensaio dos dois perfis bloqueado.

## Alterações

- A alternativa com nome em collection_gallery.py já estava implementada e foi considerada correcta pelo revisor: remove o link partido, preserva quantidade/foil, respeita hidden e escapa aspas.
- Confirmado nesta ronda com `git ls-files _tmp_validacao/`: nenhum ficheiro rastreado. `git status --short` estava limpo no início; `git diff main --stat` não contém remoções de logs. Não há remoções pendentes para o commit. A pasta e `_bateria-revisao.log` já estão ignorados.
- A remoção recursiva da pasta foi bloqueada pela política; os dois ficheiros foram removidos individualmente. Resta uma subpasta temporária inacessível, ignorada e não rastreada.

## Validação

- Correcção do resultado do orquestrador: a revisão comunicou **saída 1, FALHARAM: test_casca.py**, sem contagem. A anterior afirmação «saída 0, TUDO OK» era incorrecta.
- Nova corrida local: `py -X utf8 _bateria.py` na pasta `tests`, com `MTGVAULT_TESTE_TECTO_S=15` passado por um wrapper Python: 117 ficheiros, 8 OK, 108 ERRO, 1 PENDURA (`test_casca.py`), saída 1. Contagem confirmada por expressão regular sobre as linhas de resultado em `_bateria-revisao.log` (ignorado). Há erros de permissões nas pastas temporárias; esta corrida não substitui a validação do orquestrador. A tentativa anterior com o limite normal foi interrompida após os erros iniciais e a paragem em `test_casca.py`.
- `git diff --check`: saída 0.
- py -X utf8 tests/test_gallery_fallback.py: saída 0, 3 casos OK.
- py -X utf8 tests/ensaio_gallery_fallback.py: duas tentativas nesta sessão, ambas com saída 1 e PermissionError: [WinError 5] Acesso negado na criação do pipe do Playwright, antes de validar qualquer perfil.
- A corrida antiga com 8 OK e 109 ERRO era da sandbox; não representa o resultado posterior do orquestrador.

## Fecho pelo orquestrador

### Ronda actual do executor

- `py -X utf8 tests/test_gallery_fallback.py`: saída 0, **3 casos OK**. A implementação aprovada de `collection_gallery.py` foi preservada.
- `py -X utf8 tests/ensaio_gallery_fallback.py`: duas tentativas, ambas com saída 1, `PermissionError: [WinError 5] Acesso negado` na criação do pipe do Playwright. **Zero perfis validados**; não se chegou a abrir qualquer browser.
- `py -X utf8 tests/test_casca.py`, isolado na worktree: saída 1, após passar os primeiros 11 casos. Falhou `caso_nenhuma_pagina_tem_scroll_horizontal`: nas duas larguras, `Error: connect ECONNREFUSED 127.0.0.1:9334`. Não foi medida a página; isto não é prova de overflow. O processo terminou e a sessão foi recolhida.
- Bateria completa nesta ronda: `py -X utf8 _bateria.py > ../_bateria-revisao-atual.log 2>&1`, com cwd `tests`, sem alterar o limite da bateria: **saída 1; 119 ficheiros, 8 OK, 111 ERRO, 0 PENDURA**. Log preservado em `_tmp_validacao/bateria-ronda3.log` (UTF-16, ignorado). Contagem obtida por Python com expressões regulares `^ok  `, `^ERRO`, `^PENDURA` sobre o log. Ainda por verificar independentemente pelo orquestrador.
- A bateria correu enquanto o ensaio isolado ocupava a porta 8806: o erro da casca nessa bateria foi `WinError 10048`, não o resultado do ensaio isolado acima. Os restantes erros incluem recusas de escrita em pastas temporárias (`PermissionError`). Esta corrida não serve de aprovação.
- `git diff main -- tests/test_casca.py tests/medir_layout.py tests/medir_layout.js mtgvault/site_shell.py *.html`: vazio. Esses ficheiros são iguais ao `main` (`34ecc3f780a718a6f4261671be4d9481ba0c79bd`), mas **não foi executado o teste no main nem demonstrada uma falha anterior fora da sandbox**. Não se tocou na pasta viva.
- Pendente grave: repetir sequencialmente o teste isolado nesta worktree e numa cópia do main num executor com acesso aos browsers; depois correr a bateria sem concorrência pela porta e concluir a revisão conjunta. Não classificar a falha original como preexistente sem essa prova.

Correr py -X utf8 tests/ensaio_gallery_fallback.py fora da sandbox e exigir OK: 2 perfis; concluir a revisão conjunta e o e2e da mesa antes de publicar. Esta sessão tem aprovação desactivada e não pode executar fora da sandbox.

Não se tocou na pasta viva nem nas colecções. Sem instalação de dependências, commits, merge ou push; não foram chamados pedir.ps1/ciclo.ps1.
