### Setas empurram a figura selecionada

Com uma marcação selecionada — ou uma imagem, na guia Edição — as setas do
teclado a movem. É o ajuste fino que faltava para encostar um balão exatamente
num detalhe do desenho.

O passo é de um pixel da imagem. Com o zoom bem reduzido, um pixel da imagem não
chega a um pixel na tela e a marcação parecia não sair do lugar, então o passo
nunca é menor que um pixel de tela. Segurando **Shift** ela anda dez vezes mais,
para atravessar a folha sem segurar a tecla. A barra de estado mostra a posição a
cada passo.

Uma sequência de setas vira um único desfazer, e a marcação continua sem sair da
área útil.

### Arquivo de diagnóstico

O programa passou a gravar um **diagnostico.log** na própria pasta, com o rastro
do que aconteceu antes de um problema: versão, sistema, falhas internas e erros
da interface com a pilha inteira. São no máximo quatro arquivos de 512 KB, que
rodam entre si — dá para anexar num e-mail. Se a pasta do programa não aceitar
escrita, o arquivo vai para %LOCALAPPDATA%\SuperCaptura.

Junto com ele, dois pontos cegos foram fechados:

- Um erro de JavaScript no meio de um traçado apenas congelava a tela, sem aviso
  e sem rastro em lugar nenhum. Agora ele é registrado com a pilha e a barra de
  estado avisa onde o detalhe ficou.
- Oito trechos que seguiam em frente engolindo o motivo da falha — o botão que
  simplesmente não fazia nada — agora registram por quê. O comportamento do
  programa é o mesmo; o motivo é que deixou de se perder.

Ao relatar um problema, mande esse arquivo junto.

### Correção: alinhamento e sequência automática não eram salvos

O alinhamento do texto e o interruptor "Sequência automática" (do balão e do
triângulo de revisão) eram gravados pela interface, mas descartados na hora de
escrever o arquivo de configuração: as duas escolhas voltavam ao padrão toda vez
que o programa era fechado. Agora ficam.
