SUPER CAPTURA - REV.7
=====================

Programa desktop em Python para captura, anotação e gravação de tela, com a
nova interface HTML integrada ao PySide6.

INSTALAÇÃO
----------
1. Execute "Instalar Bibliotecas.bat" uma vez.
2. Execute "iniciar_super_captura.bat" para iniciar o programa.
3. Opcional: execute "Adicionar ao Menu Iniciar.bat" para criar o atalho
   "Super Captura" no Menu Iniciar com o ícone do programa. O mesmo arquivo
   também limpa o cache de ícones do Windows, que é o que faz o Menu Iniciar
   insistir em mostrar uma versão antiga do ícone.

QUANDO ALGO DER ERRADO
----------------------
O programa grava um arquivo "diagnostico.log" na propria pasta, com o rastro do
que aconteceu antes do problema: versao, sistema, falhas internas e erros da
interface com a pilha inteira. Sao no maximo quatro arquivos de 512 KB, que
rodam entre si - da para anexar num e-mail. Se a pasta do programa nao aceitar
escrita, o arquivo vai para %LOCALAPPDATA%\SuperCaptura.

Ao relatar um problema, mande esse arquivo junto: e ele que diz o que houve na
sua maquina.

Se a tela apresentar falhas de desenho (partes que nao aparecem, cores erradas,
piscadas), o desenho pode voltar a ser feito pelo processador: abra o
configuracoes.json e troque "software_render": false por true, ou inicie o
programa com a variavel de ambiente SUPER_CAPTURA_SOFTWARE=1. Fica mais lento -
medido nesta janela, 15 quadros por segundo contra 60 - mas nao depende do
video da maquina. O modo em uso aparece na primeira linha do diagnostico.log.

RECURSOS
--------
- Atualizacoes por GitHub Releases: verificacao ao abrir e instalacao com
  confirmacao. Consulte notas-de-versao/ATUALIZACOES.md para instalar e publicar versoes.
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
  clicando fora ou pressionando ESC. A caixa se comporta como no PowerPoint:
  enquanto a altura não é ajustada à mão, ela cresce com o texto; ao arrastar a
  borda de cima ou de baixo, a caixa passa a mandar e o texto diminui sozinho
  até caber. O interruptor fica em "Opções de anotação".
- Anotações adicionais importadas da nova interface: linha de chamada, cota
  livre e cota de ângulo, todas com rótulo editável direto na área da imagem.
- Balão numerado e triângulo de revisão com preenchimento independente, sem
  tamanho mínimo fixo e redimensionáveis por qualquer uma das oito alças.
- O número do balão e da revisão avança sozinho em números, letras e prefixos:
  1, 2, 3 / A, B, C / R1, R2 / Rev A, Rev B.
- Duplo clique com a ferramenta Mover edita textos já inseridos em texto,
  cotas, chamadas e balões.
- Setas usam ponta fechada/preenchida; cotas livres usam extremidades
  perpendiculares e travam suavemente quando próximas de horizontal/vertical.
- Cota livre e cota de ângulo têm alças nas pontas: comprimento e ângulo mudam
  depois de desenhados. O afastamento das linhas de chamada da cota tem alça
  própria.
- Nuvem de revisão com menu próprio na setinha ao lado da ferramenta: traço
  retangular ou à mão livre e raio do festonado. À mão livre, o traço vira nuvem
  e fecha sozinho quando termina perto de onde começou.
- O texto da linha de chamada fica numa caixa como a da ferramenta Texto: a
  frase quebra em linhas, arrastar a borda reflui o texto e fixar a altura
  reduz a fonte até caber.
- O campo de tamanho da faixa muda de nome conforme a ferramenta - Fonte,
  Balão, Triângulo, Ponta (da seta) ou Raio (da nuvem) - e cada ferramenta
  guarda o seu próprio valor.
- Caneta e marca-texto sem serrilhado na borda: a camada de desenho é
  rasterizada acima da resolução da tela e os pontos passam por uma suavização
  antes de virar curva, no desenho, na cópia e na exportação.
- Seta, retângulo, círculo sempre proporcional, linha direta, balão numerado,
  desfoque, caneta, marca-texto, linha ortogonal por cliques e nuvem de revisão.
- Linha ortogonal contínua: clique para iniciar, clique para continuar em
  vertical/horizontal e finalize com ESC, botão direito ou "Interromper".
- Movimento e redimensionamento das marcações.
- Tipo de linha na linha direta e na ortogonal, pela setinha ao lado da
  ferramenta: contínua, tracejada (peça invisível), linha de centro e
  pontilhada. O padrão acompanha a espessura do traço, e a espessura pode ser
  digitada no próprio menu - é o mesmo valor do campo Cor / Esp. da faixa.
- Moldura: é um COMANDO, não um modo de desenho. Selecione a imagem (ou várias,
  com Ctrl+clique) e clique no botão: o contorno aparece na hora, encostado na
  borda de cada uma. A cor e a espessura são as da seção Formatação (Cor / Esp.);
  clicar de novo com outros valores troca a moldura que já está lá, em vez de
  empilhar uma segunda. A seleção continua de pé e a ferramenta em uso não muda.
  Na Edição a moldura é PARTE da imagem, não uma marcação por cima dela: ela
  anda, escala, gira, é recortada, copiada, exportada e desfeita junto com a
  imagem, e clicar nela pega a imagem. Para tirá-la, botão direito na imagem ->
  "Remover moldura" (ou Ctrl+Z).
  Sem nada selecionado não sai moldura nenhuma: a folha branca é o fundo do
  programa, não uma imagem. Na Página Inicial não há o que selecionar (existe uma
  captura só, e a folha é ela), então lá o contorno é dela.
  Para desenhar um retângulo à mão em volta de algo, a ferramenta é o Retângulo.
- Na guia Edição, Ctrl+clique junta imagens na seleção. Arrastar, empurrar com
  as setas, Delete e o botão direito valem para o grupo inteiro; a alça de
  redimensionar fica só na última clicada.
- Ctrl+C e Ctrl+V duplicam as imagens selecionadas na Edição, cada cópia
  independente das outras - e o botão "Colar" da faixa segue o mesmo caminho.
- Copiadas para FORA do programa, as imagens selecionadas também chegam
  separadas: com duas ou mais, o Ctrl+C põe na área de transferência uma lista
  de ARQUIVOS (um PNG por imagem, na resolução original), e não um mosaico. O
  Word, o Outlook e o Explorer colam cada uma por conta própria. Com uma imagem
  só, vai a imagem mesmo, como todo programa espera.
  Isso é diferente do "Copiar" da faixa (Exportar), que achata a folha inteira
  numa imagem só; sem nada selecionado, o Ctrl+C cai nessa cópia achatada e a
  barra de estado avisa, para a colagem seguinte não surpreender.
- Cortar especial, na setinha ao lado da ferramenta Cortar (e no botão direito
  de uma imagem da Edição). Uma barra de passos conduz as três etapas, com botão
  para avançar - Enter faz o mesmo:
    1. clique nas imagens; a nº 1 é a referência;
    2. recorte a imagem nº 1 pelas alças;
    3. arraste o quadro vermelho que apareceu em cada uma das outras.
  O ajuste nas demais imagens é "mesmo tamanho" ou "mesma proporção", e o corte
  inteiro entra como um único desfazer.
- Os menus flutuantes têm uma taxinha ao lado do X: presos, deixam de fechar ao
  clicar fora ou com ESC, e continuam arrastáveis pelo título.
- Ctrl+scroll e botões de zoom atuam apenas na imagem, sem ampliar/reduzir a
  interface do programa. As alças de seleção mantêm o mesmo tamanho aparente em
  qualquer zoom.
- A faixa de opções cabe inteira na largura mínima da janela: nenhuma guia
  depende de barra de rolagem horizontal.
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

ORGANIZACAO DA PASTA
--------------------
app.py                 o programa; os atalhos do Menu Iniciar apontam para ele
atualizacao/           verificacao, download e instalacao das versoes
interface/             pagina, script, fontes e icone
notas-de-versao/       ATUALIZACOES.md e as notas de cada versao
ferramentas/           publicar_release.py, usado so para publicar
tests/                 testes
capturas/ e videos/    o que o programa salva
versao.json            versao instalada e onde fica o programa
configuracoes.json     suas preferencias

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
O arquivo "interface/super_captura.ico" é desenhado tamanho a tamanho (16, 20, 24, 32,
40, 48, 64, 96, 128 e 256 pixels), com as barras alinhadas ao pixel, para não
aparecer borrado no Menu Iniciar.

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
