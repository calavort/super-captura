### Todos os botões auditados

Os botões das três guias foram verificados um a um, de duas formas: conferindo
que cada um tem uma ação ligada a ele, e **clicando em 84 deles de verdade** na
janela real, para garantir que nenhum falha em silêncio. Nenhum quebrou.

Junto com isso entrou uma verificação permanente da conversa entre a interface e
o programa. A interface chama o programa **por nome**, em tempo de execução — um
nome errado não quebra nada visível, o botão simplesmente deixa de funcionar, e
isso só aparece quando alguém reclama. Agora os dois lados são comparados
automaticamente a cada alteração.

### O aviso de erro aponta o arquivo certo

Quando acontece um erro interno, a barra de estado informa onde o detalhe foi
gravado. A mensagem dizia "na pasta do programa" — mas, se essa pasta não aceitar
escrita, o registro vai para %LOCALAPPDATA%, e você procuraria no lugar errado.
Agora a mensagem traz o caminho real do arquivo.
