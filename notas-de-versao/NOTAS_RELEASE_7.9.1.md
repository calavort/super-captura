### O ícone de Transparência e o de Rotacionar abrem o ajuste

Os dois tinham uma setinha ao lado, como as ferramentas de desenho — só que eles
não são modos de desenho: não há nada para "ligar" no botão. Clicar no ícone
parecia não fazer nada, e só a seta abria o controle.

Agora o próprio ícone abre o ajuste, e a seta saiu.

### Fim da tela cinza ao maximizar

Maximizar ou restaurar a janela deixava a tela cinza por um bom tempo. Medindo:
**496 ms ao maximizar e 624 ms ao restaurar**, sempre terminando por volta dos
900 ms.

O motivo: havia um retângulo cinza posto de propósito por cima da janela durante
900 ms, para tapar a troca de tamanho. O cinza não era a falha — era a correção
antiga dela, de quando o desenho ainda era feito pelo processador.

Medindo com esse retângulo desligado: **0 ms**. O problema que ele resolvia
deixou de existir.

A proteção continua, mas agora ela tapa a transição com **uma foto do que estava
na tela**, e sai assim que a página avisa que já desenhou no tamanho novo —
menos de 50 ms. Vale também para restaurar a janela depois de minimizar.
