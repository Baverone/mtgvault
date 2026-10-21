# Galeria — revisão de 2026-10-21

Estado: código aprovado por leitura; validação conjunta ainda bloqueada pelo ensaio de browser. Não publicar até obter OK: 2 perfis.

## Alterações

- A alternativa com nome em collection_gallery.py já estava implementada e foi considerada correcta pelo revisor: remove o link partido, preserva quantidade/foil, respeita hidden e escapa aspas.
- Removidos os dois logs rastreados de _tmp_validacao/ (3574 linhas). As remoções ficam no diff para o commit do orquestrador. .gitignore passa a excluir essa pasta e _bateria-revisao.log.
- A remoção recursiva da pasta foi bloqueada pela política; os dois ficheiros foram removidos individualmente. Resta uma subpasta temporária inacessível, ignorada e não rastreada.

## Validação

- Resultado do orquestrador, comunicado na revisão: na pasta `tests`, `py -X utf8 _bateria.py`, saída 0, TUDO OK. A revisão não forneceu contagem; não foi novamente confirmado fora da sandbox nesta sessão.
- Nova corrida local: `py -X utf8 _bateria.py` na pasta `tests`, com `MTGVAULT_TESTE_TECTO_S=15` passado por um wrapper Python: 117 ficheiros, 8 OK, 108 ERRO, 1 PENDURA (`test_casca.py`), saída 1. Contagem confirmada por expressão regular sobre as linhas de resultado em `_bateria-revisao.log` (ignorado). Há erros de permissões nas pastas temporárias; esta corrida não substitui a validação do orquestrador. A tentativa anterior com o limite normal foi interrompida após os erros iniciais e a paragem em `test_casca.py`.
- `git diff --check`: saída 0.
- py -X utf8 tests/test_gallery_fallback.py: saída 0, 3 casos OK.
- py -X utf8 tests/ensaio_gallery_fallback.py: duas tentativas nesta sessão, ambas com saída 1 e PermissionError: [WinError 5] Acesso negado na criação do pipe do Playwright, antes de validar qualquer perfil.
- A corrida antiga com 8 OK e 109 ERRO era da sandbox; não representa o resultado posterior do orquestrador.

## Fecho pelo orquestrador

Correr py -X utf8 tests/ensaio_gallery_fallback.py fora da sandbox e exigir OK: 2 perfis; concluir a revisão conjunta e o e2e da mesa antes de publicar. Esta sessão tem aprovação desactivada e não pode executar fora da sandbox.

Não se tocou na pasta viva nem nas colecções. Sem instalação de dependências, commits, merge ou push; não foram chamados pedir.ps1/ciclo.ps1.
