### A imagem capturada agora sai nítida

A 7.8.0 melhorou a nitidez, mas não foi na raiz. Medindo o que aparece na tela
contra a renderização ideal, em níveis de cinza:

| zoom | erro |
|------|------|
| 91%  | 3,2  |
| 100% | 8,0  |
| 60%  | 4,6  |

O pior caso era justamente o **zoom de 100%**, onde a imagem deveria sair pixel a
pixel.

A causa: a área de desenho era criada com o dobro da resolução da tela — essa
sobra existe para tirar o serrilhado das **marcações**. Só que, com a imagem
sendo exibida menor do que ela é, isso **ampliava a captura ao dobro** para a
tela reduzi-la de volta. Duas reamostragens para chegar ao tamanho de origem, e o
embaçamento vinha daí.

Agora, quando a imagem é exibida menor que ela mesma, a área de desenho tem
exatamente a resolução dela: a captura é desenhada 1:1 e quem reduz é a tela, uma
vez só. **Erro medido depois: zero**, em 91%, 100% e 60%.

Acima de 100% a ampliação é o que você pediu, e aí a sobra volta a valer para
deixar as marcações lisas.

### Faixa cinza sob a barra de título

Havia uma tira cinza entre a barra verde e as guias que não separava nada. As
guias passaram a encostar na barra.
