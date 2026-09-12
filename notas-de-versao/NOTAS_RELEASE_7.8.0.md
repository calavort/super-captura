### O programa ficou quatro vezes mais rápido

O desenho era feito pelo processador, não pela placa de vídeo. Medido nesta
máquina: **66,6 ms por quadro — 15 quadros por segundo** — assim que qualquer
coisa aparecia na tela, igual para a folha vazia, para um traço longo e para
três fotos grandes. Não era custo de desenho, era um teto.

Com a aceleração por vídeo ligada, **16,7 ms — 60 quadros por segundo**. É isso
que fazia o traço da caneta parecer atrasado e o arraste das imagens pesar: a
resposta demorava quatro quadros em vez de um.

Se a tela apresentar falhas de desenho na sua máquina, dá para voltar atrás:
troque `"software_render": false` por `true` no configuracoes.json. O modo em uso
aparece na primeira linha do diagnostico.log.

### Imagens mais nítidas na tela

A captura em si já estava certa — ela sempre foi feita na resolução real da tela,
e o PNG salvo sempre saiu 1:1. A perda era só na exibição, e vinha de três
lugares:

- A área de desenho guardava menos pixels do que a própria captura tem. Uma
  imagem de 2560 px exibida em 1141 perdia 11% do detalhe **antes** de a tela
  reduzir o resto.
- A cópia reduzida da imagem só era preparada quando ela encolhia mais da
  metade; entre 55% e 100% a redução era feita do jeito rápido, a cada quadro.
- As fotos coladas na guia Edição passavam por duas reduções seguidas em vez de
  uma.

Medindo o erro contra a renderização ideal, em níveis de cinza: **4,2 antes,
2,8 depois** — um terço a menos.

### Ferramenta nova: Transparência

Deixa uma marcação — ou uma imagem colada — mais apagada, para não tampar o que
está embaixo. A setinha ao lado do botão abre o controle; com algo selecionado,
o ajuste vale para ele, e sem seleção vale para a próxima marcação.

### Ferramenta nova: Rotacionar

Gira qualquer marcação ou imagem. O menu tem o ângulo exato e dois botões de um
quarto de volta. A moldura de seleção e as alças giram junto, e o clique continua
pegando onde o desenho está.

### Botão direito

Clicando com o botão direito sobre uma marcação ou uma imagem, as duas
ferramentas aparecem ali mesmo, junto com Remover — e, nas imagens, junto com
Cortar e Restaurar.
