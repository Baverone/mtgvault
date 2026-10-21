# Galeria — execução de 2026-10-21

Estado: implementado; validação conjunta PENDENTE. Não publicar.

- `collection_gallery.py`: uma imagem que falhe é substituída pelo nome; remove o link quebrado, preserva quantidade/foil e escapa aspas nos atributos.
- `tests/test_gallery_fallback.py`: regressão em Node, sem bases nem rede.
- `tests/ensaio_gallery_fallback.py`: gera cópia temporária com dados sintéticos e intercepta todos os pedidos; ensaia 404, ausência de URL, imagem válida, procura e etiquetas em Chromium desktop e iPhone 15/WebKit. Não integra a bateria para não impor Playwright aos testes unitários.

## Comandos e resultados observados

Na pasta `tests`:

- `py test_gallery_fallback.py`: 3 casos passaram, saída 0.
- `py ensaio_gallery_fallback.py`: saída 1, `PermissionError: [WinError 5] Acesso negado` na criação do pipe do Playwright. Nenhum dos dois perfis foi validado.
- `py _bateria.py`, com `MTGVAULT_TESTE_TECTO_S=15`: 117 ficheiros, 8 OK, 109 ERRO, 0 PENDURA, saída 1. Contagem repetida por leitura do log `_tmp_validacao/bateria-final.log`. A primeira tentativa com o tecto normal foi interrompida após erros de permissões e ausência de progresso; o tecto reduzido não foi atingido na corrida final.
- `git diff --check`: saída 0.

A bateria apresenta `PermissionError` nas pastas temporárias, `unable to open database file` e falhas de asserção; não se atribuem todas as falhas à alteração da galeria. O teste novo passou também dentro da bateria.

As contagens são observadas localmente; falta a verificação independente do orquestrador/Claude exigida pela mesa. Repetir a bateria no ambiente de revisão, correr o ensaio nos dois perfis e concluir a revisão conjunta. O e2e público da mesa também fica pendente para o fecho; não valida este código ainda não publicado.

Não houve acesso à pasta viva, alterações nas colecções, instalação de dependências, commit, merge ou push. Não foram chamados pedir.ps1/ciclo.ps1.
