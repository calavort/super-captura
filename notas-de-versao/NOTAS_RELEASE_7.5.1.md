### Encostar na borda não solta mais a ferramenta

Correção de um efeito colateral do limite da área útil, que entrou na 7.5.0.

Como o ponteiro passou a ser preso à folha, encostar na borda virou o mesmo que
sair da área de desenho — e sair dela concluía o comando. Na prática, o
retângulo era finalizado no meio do traçado, com o botão do mouse ainda
pressionado.

Agora o movimento continua sendo seguido mesmo com o ponteiro fora da folha: o
desenho encosta na borda e segue acompanhando o mouse no sentido que ainda tem
espaço. Voltando para dentro, ele volta a obedecer. O comando só termina quando
você solta o botão — vale para todas as ferramentas de arrasto, e também para
mover e redimensionar o que já está desenhado.
