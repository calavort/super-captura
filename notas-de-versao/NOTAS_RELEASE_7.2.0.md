### Traços mais suaves e ferramentas de revisão com mais controle

**Caneta e marca-texto**

- Fim do serrilhado na borda do traço: a camada de desenho é rasterizada acima da resolução da tela e reduzida pelo navegador.
- Os pontos do traço passam por uma suavização antes de virar curva. O marca-texto, por ser largo, recebe um passe a mais.
- Vale igual no desenho, na cópia e na imagem exportada.

**Nuvem de revisão**

- Menu próprio na setinha ao lado da ferramenta, como a caneta e o marca-texto já tinham: **Retangular** ou **À mão livre**, e o raio do festonado com amostra de cada tamanho.
- No modo à mão livre, desenhe o contorno e ele vira nuvem. Terminando perto de onde começou, a nuvem fecha sozinha.

**Balão e triângulo de revisão**

- Redimensionáveis por qualquer uma das oito alças, sem piso fixo — dá para fazer marcações realmente pequenas.
- Preenchimento independente: balão cheio com triângulo vazado, o padrão de prancha.
- O número avança sozinho em números, letras e prefixos: 1, 2, 3 / A, B, C / R1, R2 / Rev A, Rev B.

**Cota livre, cota de ângulo e linha de chamada**

- Alças nas pontas: comprimento e ângulo mudam depois de desenhados.
- O afastamento das linhas de chamada da cota tem alça própria e já nasce com um valor útil.
- A ponta e o "pé" da linha de chamada acompanham o tamanho escolhido.
- O texto da linha de chamada agora vive numa caixa, com o mesmo comportamento da ferramenta Texto: a frase quebra em linhas em vez de sair reta pela imagem, arrastar a borda reflui o texto e fixar a altura reduz a fonte até caber.

**Caixa de texto**

- Comportamento do PowerPoint: enquanto a altura não é ajustada à mão, a caixa cresce com o texto.
- Ao arrastar a borda de cima ou de baixo, a caixa passa a mandar e o texto diminui sozinho até caber.
- O interruptor fica em **Opções de anotação**, ao lado do grupo Anotações.

**Fluidez**

- Riscar (caneta, círculo, qualquer ferramenta) e mover marcações voltaram a acompanhar o mouse.
- Três caminhos rodavam a cada evento do ponteiro — centenas por segundo — e ficavam mais caros conforme o traço crescia: refazer a suavização do risco inteiro, copiar todos os pontos para o preview e procurar a marcação sob o cursor percorrendo ponto a ponto.
- Agora a suavização é feita ponto a ponto conforme se desenha, o preview aponta para o traço em vez de copiá-lo, a caixa dos traços fica guardada e o cursor é recalculado uma vez por quadro.
- Medido no renderizador real: montar a marcação a cada movimento caiu de 136 µs para 2,5 µs num traço de 2000 pontos (e parou de crescer com o tamanho), e procurar a marcação sob o cursor caiu de 201 µs para 7 µs.

**Interface**

- O campo de tamanho da faixa muda de nome conforme a ferramenta: Fonte, Balão, Triângulo, Ponta ou Raio. Cada ferramenta guarda o seu próprio valor.
- Alças de seleção e tolerância do clique mantêm o mesmo tamanho aparente em qualquer zoom.
- A caixa **Opções de anotação** passou a abrir também na guia Edição.
- Faixa de opções reorganizada: no tamanho mínimo da janela nenhuma guia precisa de barra de rolagem horizontal.
