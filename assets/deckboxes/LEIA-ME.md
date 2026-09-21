# assets/deckboxes — a foto da deckbox física de cada caixa

Uma imagem por caixa (`<slot>.jpg`), reduzida (≤ 800 px, JPEG, ~100 KB),
escrita pelo `mtgvault/fotocaixa.py` a partir da foto que o André tira à
deckbox — pelo botão «📦 Foto da deckbox» do modo edição (8771) ou por um
ficheiro largado em `pendentes/deckboxes/<slot>.jpg`, que o `daily` recolhe.

**Vai no Git de propósito** (é a excepção consciente ao «não guardar imagens»
do CLAUDE.md, que é uma regra para a base de dados): é o que o site publicado
mostra. O original, em tamanho real, fica em `data/deckboxes/` — fora do Git —
e a anterior em `data/deckboxes/anteriores/`. Nada se apaga.

Não editar à mão: a data de cada foto está em `colecao_config.json →
caixas[].foto`, e é o `fotocaixa.guardar` que mantém as três coisas juntas.
