### Atualização deixa de travar a organização das pastas

Mudança interna, sem efeito visível no uso do programa.

- O pacote passou a declarar a própria lista de arquivos no manifesto, em vez
  de precisar bater com uma lista fixa gravada na versão instalada. Cada
  caminho continua conferido — por forma e por SHA-256 — mas agora uma versão
  nova pode renomear, criar, mover ou remover arquivos.
- `versao.json` passou a dizer onde fica o programa, e o instalador reabre por
  esse caminho depois de atualizar.
- A instalação registra o que gravou, para a seguinte apagar o que saiu do
  pacote em vez de deixar o arquivo duplicado em duas pastas.

Esta versão mantém exatamente os mesmos arquivos da 7.2.1, de propósito: é o
que permite instalá-la normalmente e, só então, reorganizar as pastas.
