SUPER CAPTURA - REV.7
=====================

Programa desktop em Python para captura, anotação e gravação de tela, com a
nova interface HTML integrada ao PySide6.

INSTALAÇÃO
----------
1. Execute "Instalar Bibliotecas.bat" uma vez.
2. Execute "Abrir Super Captura.bat" para iniciar o programa.
3. Opcional: execute "Adicionar ao Menu Iniciar.bat" para criar o atalho
   "Super Captura" no Menu Iniciar com o ícone do programa. O mesmo arquivo
   também limpa o cache de ícones do Windows, que é o que faz o Menu Iniciar
   insistir em mostrar uma versão antiga do ícone.

RECURSOS
--------
- Captura de uma área ou da tela inteira.
- Captura otimizada para uso prático: menor espera para esconder a janela,
  exibição imediata sempre que possível e uso de arquivo temporário apenas
  como fallback para imagens muito grandes.
- ESC cancela a captura a qualquer momento: durante a contagem regressiva do
  atraso e durante a seleção da área na tela (o botão direito também cancela).
- Cópia automática ativa nas capturas: após capturar, a imagem já fica pronta
  para colar em outro programa.
- Abertura e edição de imagens existentes.
- "Salvar como..." abre na última pasta usada e já sugere o mesmo formato
  (PNG ou JPG) da vez anterior.
- Gravação de vídeo em MP4, MKV ou AVI, a 30 ou 60 FPS.
- Áudio do microfone e suporte ao áudio do sistema quando o dispositivo
  "Mixagem Estéreo/Stereo Mix" estiver habilitado no Windows.
- Texto em caixa editável no canvas: clique, digite, ajuste a área e conclua
  clicando fora ou pressionando ESC.
- Anotações adicionais importadas da nova interface: linha de chamada, cota
  livre e cota de ângulo, todas com rótulo editável direto na área da imagem.
- Balão numerado com opções avançadas de preenchimento e linha de chamada.
- Duplo clique com a ferramenta Mover edita textos já inseridos em texto,
  cotas, chamadas e balões.
- Setas usam ponta fechada/preenchida; cotas livres usam extremidades
  perpendiculares e travam suavemente quando próximas de horizontal/vertical.
- Seta, retângulo, círculo sempre proporcional, linha direta, balão numerado,
  desfoque, caneta, marca-texto, linha ortogonal por cliques e nuvem de revisão.
- Linha ortogonal contínua: clique para iniciar, clique para continuar em
  vertical/horizontal e finalize com ESC, botão direito ou "Interromper".
- Movimento e redimensionamento das marcações.
- Ctrl+scroll e botões de zoom atuam apenas na imagem, sem ampliar/reduzir a
  interface do programa.
- Zoom visual sem reduzir a resolução original da imagem/exportação.
- Atraso de captura, cópia automática e salvamento automático.
- Cadastro de usuário, pastas configuráveis e preferências persistentes.
- Pastas salvas são validadas ao abrir; caminhos antigos de outro usuário,
  OneDrive ou máquina são corrigidos automaticamente para pastas locais.
- Cópia para a área de transferência e salvamento em PNG/JPG.

SELEÇÃO DE MARCAÇÕES SOBREPOSTAS
--------------------------------
Cada ferramenta é selecionada pelo desenho em si, não pela caixa que a envolve.
Assim uma seta deixa de "cobrir" o texto que passa por baixo dela: clicando no
texto vem o texto, clicando na linha da seta vem a seta.

Quando dois elementos ocupam exatamente o mesmo ponto, clique de novo no mesmo
lugar para descer um nível e alcançar o que está embaixo.

DESFAZER, COPIAR E COLAR
------------------------
- Ctrl+Z desfaz a última operação, e não apenas a última marcação inserida:
  vale para inserir, apagar, mover, redimensionar, editar texto, alterar cor
  ou espessura, cortar, limpar, adicionar/remover imagens na guia Edição e
  substituir a imagem por uma nova captura.
- Ctrl+Y (ou Ctrl+Shift+Z) refaz.
- Com uma marcação ou imagem selecionada, Ctrl+C copia esse elemento e Ctrl+V
  cola uma cópia deslocada; colagens seguidas ficam em escada. Sem nada
  selecionado, Ctrl+C continua copiando a imagem inteira, e o botão "Copiar"
  da faixa sempre copia a imagem inteira.
- Na guia Edição, Ctrl+V cola a imagem da área de transferência do Windows
  quando não há nenhum elemento copiado dentro do programa.

ATALHOS PADRÃO
--------------
- Alt+P  : capturar área
- Ctrl+C : copiar (elemento selecionado, ou a imagem final)
- Ctrl+V : colar (elemento copiado, ou imagem da área de transferência)
- Ctrl+S : salvar PNG
- Ctrl+Z : desfazer
- Ctrl+Y : refazer
- Delete : remover a marcação selecionada
- ESC    : interromper/concluir comando ativo e cancelar a captura

Os atalhos de captura, copiar, salvar e desfazer podem ser alterados na aba
"Configuração". As preferências são salvas automaticamente em
"configuracoes.json".

QUALIDADE DO TRAÇO
------------------
Antes, o desenho era feito sempre na resolução da imagem e depois esticado ou
encolhido pelo navegador para caber no zoom da tela. Era daí que vinha o
serrilhado das bordas com o zoom reduzido e o borrão com o zoom ampliado.

Agora o canvas é criado no tamanho em que o desenho realmente aparece (já
considerando a escala de tela do Windows, se estiver em 125%/150%), e cada
traço é desenhado direto nesse tamanho. As marcações continuam guardadas nas
coordenadas da imagem, então nada muda para quem usa o programa - só a nitidez.

O que é salvo ou copiado sai sempre na resolução original da imagem, em um
canvas próprio, independente do zoom em que a tela estava.

Com zoom bem reduzido a imagem de fundo passa por uma redução em etapas de 2x,
que preserva melhor o texto fino da captura do que encolher tudo de uma vez.

Duas coisas foram testadas e descartadas por não melhorarem nada: desenhar em
2x/3x e reduzir (supersampling) - a suavização do canvas já é analítica e o
resultado medido foi igual ou pior - e a reamostragem "high", que custa caro
sem ganho visível aqui.

DESEMPENHO
----------
A janela do programa compõe tudo por software (sem aceleração de vídeo), então
algumas operações do canvas custam caro. Duas foram reescritas por causa disso:

- "Cobrir": o borrão é montado numa miniatura da região e ampliado de volta,
  em vez de aplicar um filtro gaussiano e um retângulo translúcido sobre a
  imagem inteira. Medido: ~84 ms por quadro antes, ~2 ms depois.
- Guia Edição: cada foto guarda uma cópia já reduzida ao tamanho em que
  aparece na página, e o desenho usa reamostragem simples. Medido com três
  fotos de 3600x2400: ~1580 ms por quadro antes, ~3 ms depois. A qualidade do
  que é salvo e copiado continua a mesma.

ÍCONE E BARRA DE TAREFAS
------------------------
O arquivo "super_captura.ico" é desenhado tamanho a tamanho (16, 20, 24, 32,
40, 48, 64, 96, 128 e 256 pixels), com as barras alinhadas ao pixel, para não
aparecer borrado no Menu Iniciar. A versão anterior está guardada em
"super_captura_backup_rev6.ico" e pode ser apagada.

O programa também declara sua identidade no Windows (AppUserModelID), o que faz
a barra de tarefas mostrar o ícone do Super Captura em vez do ícone do Python
- o processo real é o pythonw.exe.

OBSERVAÇÃO SOBRE ÁUDIO DO SISTEMA
---------------------------------
Para gravar o som reproduzido pelo computador, habilite o dispositivo de
entrada "Mixagem Estéreo" (ou "Stereo Mix") nas configurações de som do
Windows. Se ele não estiver disponível, o vídeo será gravado sem áudio e o
programa bloqueará a gravação em modo "Som do sistema" e exibirá um aviso na
barra de status com as entradas detectadas. O botão "Painel Som" abre a tela
do Windows onde a Mixagem Estéreo pode ser habilitada quando o driver oferece
essa opção.

Programa desenvolvido por Edflávio Calavort - 2026
