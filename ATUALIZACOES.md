# Atualizacoes do Super Captura

## Versao 7.2.0

- Traco da caneta e do marca-texto sem serrilhado: a camada de desenho e
  rasterizada acima da resolucao da tela e reduzida pelo navegador, e os pontos
  do traco passam por uma suavizacao antes de virarem curva. Vale para o
  desenho na tela, para a copia e para a imagem exportada.
- Cada ferramenta guarda o seu proprio tamanho, e o campo da faixa muda de nome
  conforme a ferramenta: Fonte, Balao, Triangulo, Ponta (da seta) ou Raio (do
  festonado da nuvem).
- Nuvem de revisao com menu proprio ao lado da ferramenta, como a caneta e o
  marca-texto ja tinham: traco retangular ou a mao livre e raio do festonado.
  No modo a mao livre o traco vira nuvem, fechando sozinho quando termina perto
  de onde comecou.
- Balao e triangulo de revisao redimensionaveis por qualquer uma das oito
  alcas, sem piso fixo de tamanho, e com preenchimento independente entre eles.
- Numero do balao e da revisao avanca sozinho em numeros, letras e prefixos
  (1, 2, 3 / A, B, C / R1, R2 / Rev A, Rev B).
- Cota livre e cota de angulo com alcas nas pontas: comprimento e angulo mudam
  depois de desenhados. O afastamento das linhas de chamada tem alca propria e
  ja nasce com um valor util.
- Linha de chamada com ponta e "pe" proporcionais ao tamanho escolhido, e com
  o texto numa caixa de verdade: a frase quebra em linhas, a borda arrastada
  reflui o texto e a altura fixada a mao reduz a fonte ate caber - o mesmo
  comportamento da ferramenta Texto.
- Caixa de texto no comportamento do PowerPoint: enquanto a altura nao e
  ajustada a mao, a caixa cresce com o texto; ao arrastar a borda de cima ou de
  baixo, a caixa passa a mandar e o texto diminui sozinho ate caber.
- Alcas de selecao, tracejado e tolerancia do clique medidos em pixels de tela:
  mantem o mesmo tamanho aparente em qualquer zoom.
- Caixa "Opcoes de anotacao" agora abre tambem na guia Edicao, e reune os
  interruptores de balao, triangulo, nuvem livre e caixa de texto.
- Faixa de opcoes reorganizada para caber inteira na largura minima da janela:
  nenhuma guia depende de barra de rolagem horizontal.
- Desenho e movimento fluidos de novo. Tres caminhos rodavam a cada evento do
  mouse - centenas por segundo - e cresciam junto com o traco: a suavizacao do
  risco inteiro, a copia dos pontos e a busca da marcacao sob o cursor. Agora a
  suavizacao e feita ponto a ponto, o preview aponta para o traco em vez de
  copia-lo, a caixa dos tracos fica guardada e o cursor e recalculado uma vez
  por quadro. Riscar um traco longo ficou cerca de cinquenta vezes mais barato,
  e passar o mouse sobre a imagem, cerca de vinte e sete.

## Versao 7.1.3

- Abertura de varias janelas do programa na mesma pasta, com edicoes independentes.
- A instalacao pede para fechar as outras janelas e aguarda todas encerrarem
  antes de substituir os arquivos. Nenhuma janela de trabalho e fechada automaticamente.
- Preferencias gravadas de forma atomica para evitar arquivos incompletos
  quando duas janelas salvam configuracoes ao mesmo tempo.

## Versao 7.1.2

- Colunas da paleta ordenadas da cor mais clara para a mais escura.
- Primeira coluna com branco e tons de cinza distintos, sem brancos repetidos.

## Versao 7.1.1

- Caneta e marca-texto com curvas suaves, pontas arredondadas e coleta dos
  movimentos intermediarios do mouse. A suavidade se aplica tambem ao copiar
  e exportar a imagem.
- Menu de espessuras na pequena seta ao lado de cada ferramenta. As escolhas
  sao independentes e preservadas ao reabrir. Cor / Esp. aceita valores
  personalizados e altera tambem um traco selecionado.
- Paleta de cores integrada no estilo Office: cores do tema, padrao, recentes
  e Mais cores, com espectro, matiz e codigo hexadecimal. Disponivel nas duas
  guias, com fechamento por Escape ou clique fora.


O programa consulta o GitHub Releases ao abrir, em segundo plano. Quando uma
versao nova estiver publicada, oferece o download e pede confirmacao para
instalar e reiniciar. Tambem ha os botoes Verificar e Atualizar na aba
Configuracao. Sem internet, o programa continua funcionando.

## Primeira instalacao no trabalho

1. Extraia `SuperCaptura-7.1.0.zip` em uma pasta gravavel pelo seu usuario.
2. Use Python 3.11 ou superior e execute `Instalar Bibliotecas.bat` uma vez.
3. Execute `iniciar_super_captura.bat`, ou crie o atalho pelo arquivo
   `Adicionar ao Menu Iniciar.bat`.

Se ja existe uma instalacao antiga, feche-a e extraia o primeiro pacote por
cima dela. O pacote nao inclui `configuracoes.json`, `capturas` ou `videos`.
Esse primeiro passo habilita o atualizador nas proximas versoes. Nao e
necessario instalar Git, o plugin ou o Codex no computador do trabalho.

## Publicar em casa

Repositorio de distribuicao configurado em `versao.json`:
`calavort/super-captura`. O repositorio precisa existir e ter um release
publicado com o ZIP; apenas salvar codigo no Git nao publica uma atualizacao.

A conexao do plugin GitHub nao autentica automaticamente o Git do Windows.
Para publicar pelo script, entre uma vez na sua conta, no computador de casa:

```powershell
git credential-manager github login --username calavort --browser
```

Primeiro release (cria o repositorio publico caso ainda nao exista):

```powershell
python publicar_release.py --publicar --criar-repositorio
```

Para as proximas alteracoes, aumente a versao:

```powershell
python publicar_release.py --versao 7.1.1 --publicar
```

Para gerar somente o ZIP local, sem publicar:

```powershell
python publicar_release.py --versao 7.1.1
```

O script gera os arquivos em `dist`, cria um release como rascunho, envia o
ZIP e o SHA-256 e so o torna publico depois de conferir os uploads. Caso um
upload falhe, o rascunho fica no GitHub para revisao; o script nao substitui
releases existentes. Credenciais sao obtidas do gerenciador do Git, `gh`
ou das variaveis `GH_TOKEN`/`GITHUB_TOKEN`, nunca incluidas no pacote.

## O que a instalacao preserva

Somente os arquivos explicitamente listados em `atualizador.APP_FILES` sao
distribuidos e substituidos. Capturas, videos e configuracoes ficam na pasta
de cada computador. O atualizador nao sincroniza esses dados pela internet.

As imagens e anotacoes das duas guias sao salvas localmente antes de reiniciar
e restauradas na nova versao. O historico de desfazer nao atravessa a
reinicializacao. Gravacoes e capturas em andamento impedem a instalacao.

O download exige HTTPS, SHA-256 e manifesto com hashes individuais. Antes de
trocar arquivos, o instalador aguarda a instancia anterior encerrar e cria
um backup em `.atualizacoes/backup-*`. Falhas durante a troca restauram os
arquivos anteriores. O resultado fica em `.atualizacoes/ultimo-resultado.json`.

A pasta de desenvolvimento, identificada por `.git`, verifica releases mas
nao instala por cima do codigo. Use uma copia extraida do ZIP para testar.
Atualizacoes que mudem `requirements.txt` exigem instalacao manual das
bibliotecas. Esta primeira versao distribui o programa em Python, nao um EXE
autossuficiente. Os pacotes publicos podem ser baixados por outras pessoas.

## Validacao

```powershell
python -m unittest discover -s tests -v
python tests/validar_interface.py
```

Referencia da API usada: [GitHub Releases](https://docs.github.com/en/rest/releases/releases#get-the-latest-release).
