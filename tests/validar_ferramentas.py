"""Valida as ferramentas de anotacao no renderizador Qt real, sem tocar nos dados do usuario.

Cobre o que a revisao 7.2.0 mudou: supersampling contra o serrilhado, suavizacao
do traco, tamanho proprio por ferramenta, nuvem a mao livre, balao e triangulo
de revisao redimensionaveis, cotas com alcas nas pontas, caixa de texto no
comportamento do PowerPoint e faixa de opcoes sem rolagem horizontal.
"""

import json
import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as capture
from atualizacao import atualizador_ui
from atualizacao.atualizador import APP_FILES
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def main():
    application = QApplication.instance() or QApplication([])
    temporary = tempfile.TemporaryDirectory(prefix="super-captura-ferramentas-")
    folder = Path(temporary.name)
    for name in APP_FILES:
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    capture.BASE_DIR = folder
    capture.HTML_PATH = folder / "interface" / "interface-super-captura.html"
    capture.SETTINGS_PATH = folder / "configuracoes.json"
    capture.DEFAULT_IMAGE_DIR = folder / "capturas"
    capture.DEFAULT_VIDEO_DIR = folder / "videos"
    capture.MainWindow._install_printscreen_hook = lambda self: None
    atualizador_ui.check_release = lambda info: None
    window = capture.MainWindow()
    window.show()

    def wait(predicate, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            application.processEvents()
            if predicate():
                return
            time.sleep(.01)
        raise AssertionError("Interface nao chegou ao estado esperado")

    def js(source):
        results = []
        window.web.page().runJavaScript(source, results.append)
        wait(lambda: bool(results))
        return results[0]

    def check(source):
        assert js(source), source

    try:
        wait(lambda: js("typeof pyBridge !== 'undefined' && Boolean(pyBridge)"))
        js("""
            scheduleClipboardSync = () => {};
            syncClipboardNow = () => {};
            window.sample = document.createElement('canvas');
            sample.width = 1000; sample.height = 600;
            const paint = sample.getContext('2d');
            paint.fillStyle = '#ffffff'; paint.fillRect(0, 0, 1000, 600);
            loadImageData(sample.toDataURL(), false, false);
            window.surface = () => {
                const element = document.createElement('canvas');
                element.width = 400; element.height = 400;
                return element.getContext('2d');
            };
        """)
        wait(lambda: js("Boolean(bgImage && bgImage.naturalWidth === 1000)"))
        QTest.qWait(300)

        # --- serrilhado: o canvas e rasterizado acima da resolucao da tela ---
        check("canvas.width / Math.max(1, canvas.clientWidth) >= 2")
        check("canvas.height / Math.max(1, canvas.clientHeight) >= 2")
        check("""(() => {
            const zigzag = Array.from({length: 21}, (_, i) => ({x: i * 5, y: 100 + (i % 2) * 6}));
            const smooth = smoothStrokePoints(zigzag, 1);
            const spread = list => list.reduce((total, point, index) =>
                index ? total + Math.abs(point.y - list[index - 1].y) : 0, 0);
            return smooth.length > 2 && spread(smooth) < spread(zigzag) * 0.75;
        })()""")
        print("OK: canvas com supersampling e traco suavizado")

        # --- opcoes de cada ferramenta acessiveis nas duas guias ---
        # A caixa "Opcoes de anotacao" saiu: cada ferramenta leva as suas no
        # proprio menu. O que antes se pedia da caixa, pede-se agora do menu.
        check("""(() => {
            const abre = (aba, indice) => {
                document.querySelector('.ribbon-tab[onclick*=' + aba + ']').click();
                const gatilhos = document.querySelectorAll(
                    '.tool-btn[data-tool="Balao"] + .stroke-menu-trigger');
                closeFormatPopover();
                gatilhos[indice].click();
                const menu = byId('tool-config-popover');
                const caixa = menu.getBoundingClientRect();
                const completo = menu.querySelector('.config-size')
                    && menu.querySelector('[data-fill]')
                    && menu.querySelector('.config-text-input')
                    && menu.querySelector('.config-seq')
                    && menu.querySelector('.config-extra');
                const ok = !menu.hidden && caixa.width > 0 && caixa.height > 0
                    && caixa.right <= innerWidth && caixa.bottom <= innerHeight && completo;
                closeFormatPopover();
                return ok;
            };
            const naInicial = abre('tab-home', 0);
            const naEdicao = abre('tab-edicao', 1);
            document.querySelector('.ribbon-tab[onclick*=tab-home]').click();
            // A caixa antiga e o gatilho dela nao existem mais na faixa.
            const semCaixa = document.querySelectorAll('.dialog-launcher').length === 0
                && byId('advanced-format-dialog').hidden
                && typeof toggleAdvancedFormat === 'undefined';
            return naInicial && naEdicao && semCaixa;
        })()""")
        print("OK: opcoes de cada ferramenta no menu dela, nas duas guias")

        # --- cada ferramenta com o seu tamanho e o seu rotulo ---
        # O rotulo saiu da faixa: quem o mostra agora e a secao do menu, e o
        # campo do menu e quem traz o valor guardado da ferramenta.
        def rotulo_e_valor(ferramenta):
            js(f"""closeFormatPopover();
                document.querySelector('.tool-btn[data-tool="{ferramenta}"] + .stroke-menu-trigger').click();""")
            return js("""JSON.stringify([
                byId('tool-config-popover').querySelector('.picker-label').textContent,
                byId('tool-config-popover').querySelector('.config-size').value
            ])""")

        assert json.loads(rotulo_e_valor("Nuvem"))[0].startswith("Raio")
        js("""(() => {
            const campo = byId('tool-config-popover').querySelector('.config-size');
            campo.value = 18; campo.dispatchEvent(new Event('input'));
        })()""")
        check("toolSizes.Nuvem === 18")
        assert json.loads(rotulo_e_valor("Balao"))[0].startswith("Balão")
        assert json.loads(rotulo_e_valor("Revisao"))[0].startswith("Triângulo")
        # Ao voltar para a nuvem o valor dela continua la, nao o do triangulo.
        assert json.loads(rotulo_e_valor("Nuvem"))[1] == "18"
        check("toolSizes.Nuvem === 18 && byId('cfg-fonte').value === '18'")
        js("closeFormatPopover()")
        print("OK: tamanho e rotulo proprios de cada ferramenta, preservados ao trocar")

        # --- nuvem: raio configuravel e traco a mao livre ---
        check("""(() => {
            const paint = radius => {
                const c = surface();
                drawShape(c, {type: 'Nuvem', x: 40, y: 40, w: 300, h: 200, color: '#000000', thick: 3, font: radius});
                let painted = 0;
                const data = c.getImageData(0, 0, 400, 400).data;
                for (let i = 3; i < data.length; i += 4) if (data[i] > 40) painted++;
                return painted;
            };
            return paint(6) > 0 && paint(24) > 0 && paint(6) !== paint(24);
        })()""")
        check("""(() => {
            const points = Array.from({length: 40}, (_, i) => {
                const angle = i / 40 * Math.PI * 2;
                return {x: 200 + Math.cos(angle) * 90, y: 200 + Math.sin(angle) * 90};
            });
            const shape = {type: 'Nuvem', free: true, points, x: 110, y: 110, w: 180, h: 180,
                           color: '#000000', thick: 3, font: 12};
            const c = surface();
            drawShape(c, shape);
            // O festonado estufa para fora do traco: o desenho passa do raio 90.
            const data = c.getImageData(0, 0, 400, 400).data;
            let alcance = 0;
            for (let y = 0; y < 400; y++) for (let x = 0; x < 400; x++) {
                if (data[(y * 400 + x) * 4 + 3] > 40) alcance = Math.max(alcance, Math.hypot(x - 200, y - 200));
            }
            const bounds = annotationBounds(shape);
            return isFreeCloud(shape) && alcance > 95 && bounds.w > 180
                && shapeHitsPoint(shape, 290, 200) && shapeHasSize(shape);
        })()""")
        js("""
            byId('cfg-nuvem-livre').checked = true;
            handleFormatControlChanged();
            selectTool('Nuvem');
            beginStroke({x: 100, y: 200});
            for (let i = 1; i < 30; i++) appendStrokePoint({x: 100 + i * 6, y: 200 + Math.sin(i / 3) * 20});
            window.nuvemLivre = freezeStrokePoints(createShape('Nuvem', {x: 100, y: 200}, {x: 280, y: 200}, getOptions()));
        """)
        check("cloudFreeMode === true && nuvemLivre.free === true && nuvemLivre.points.length > 5")
        js("byId('cfg-nuvem-livre').checked = false; handleFormatControlChanged(); clearStroke()")
        check("cloudFreeMode === false")
        print("OK: nuvem com raio ajustavel, modo a mao livre, limites e selecao")

        # --- balao e triangulo: tamanhos pequenos e alcas de escala ---
        check("balloonRadius({font: 12, text: '1'}) < balloonRadius({font: 40, text: '1'})")
        check("balloonRadius({font: 12, text: '1'}) < 14")
        check("reviewMarkerSize({font: 10}) < 26 && reviewMarkerSize({font: 60}) > 60")
        check("""(() => {
            annotations.length = 0;
            annotations.push({type: 'Balao', x: 300, y: 200, w: 0, h: 0, text: '7', font: 28,
                              color: '#000000', thick: 2, fillBalloon: true});
            selectedIndex = 0;
            const antes = annotations[0].font;
            resizeMarkerShape(annotations[0], {x: 300 + 60, y: 200});
            return annotations[0].font > antes && toolSizes.Balao === annotations[0].font
                && findResizeHandle(annotations[0], boxHandlePoints(annotations[0])[0].x, boxHandlePoints(annotations[0])[0].y).handle === 'marker-resize';
        })()""")
        check("""(() => {
            const vazado = {type: 'Revisao', x: 200, y: 200, text: 'A', font: 30, color: '#123456', thick: 2};
            const cheio = {...vazado, fillReview: true};
            const conta = shape => {
                const c = surface();
                drawShape(c, shape);
                const data = c.getImageData(180, 180, 60, 60).data;
                let painted = 0;
                for (let i = 3; i < data.length; i += 4) if (data[i] > 40) painted++;
                return painted;
            };
            return conta(cheio) > conta(vazado) * 1.5;
        })()""")
        print("OK: balao e triangulo pequenos, escalaveis pelas alcas e com preenchimento")

        # --- cotas: extensao padrao, alcas nas pontas e alca de afastamento ---
        check("""(() => {
            annotations.length = 0;
            clearStroke();
            const cota = createShape('CotaLivre', {x: 100, y: 300}, {x: 400, y: 300}, getOptions());
            const grips = dimensionGripPoints(cota);
            return cota.extension === DEFAULT_DIM_EXTENSION
                && Math.abs(grips[0].y - (300 + DEFAULT_DIM_EXTENSION)) < 1
                && lineResizeTools.has('CotaLivre') && lineResizeTools.has('CotaAngulo');
        })()""")
        check("""(() => {
            annotations.length = 0;
            annotations.push(createShape('CotaLivre', {x: 100, y: 300}, {x: 400, y: 300}, getOptions()));
            selectedIndex = 0;
            const cota = annotations[0];
            const ponta = lineEndpointPoints(cota)[1];
            const alca = findResizeHandle(cota, ponta.x, ponta.y);
            resizeLineShape(cota, 'end', {x: 500, y: 300});
            extendDimensionCallout(cota, {x: 250, y: 300 - 60});
            return alca && alca.handle === 'line-resize' && cota.w === 400 && Math.round(cota.extension) === -60;
        })()""")
        check("""(() => {
            const pequena = calloutLanding({font: 14});
            const grande = calloutLanding({font: 60});
            return grande > pequena && grande > 60;
        })()""")
        print("OK: cota livre com extensao propria, pontas ajustaveis e chamada proporcional")

        # --- numeracao sequencial de balao e revisao ---
        check("""['1','2','09','10','A','B','Z','AA','R1','R2','Rev A','Rev B']
            .every((_, i, list) => i % 2 === 1 || nextSequenceText(list[i]) === list[i + 1])""")
        print("OK: numeracao sequencial em numeros, letras e prefixos")

        # --- caixa de texto no comportamento do PowerPoint ---
        check("""(() => {
            const frase = 'Frase bem comprida para forcar varias linhas dentro da caixa de texto';
            const c = surface();
            const cresce = {type: 'Texto', x: 10, y: 10, w: 180, h: 0, text: frase, font: 24, color: '#000'};
            drawShape(c, cresce);
            const alturaLarga = (() => {
                const largo = {...cresce, w: 380, h: 0};
                drawShape(c, largo);
                return largo.h;
            })();
            // Autoajuste ligado: a caixa cresce com o texto e reflui na largura.
            if (!(cresce.h > 24 && alturaLarga < cresce.h)) return false;
            // Autoajuste desligado: a caixa manda e a fonte diminui para caber.
            const fixa = {...cresce, h: 60, autoHeight: false};
            const layout = textBoxLayout(c, fixa);
            return layout.size < fixa.font && layout.size >= fixa.font * 0.25;
        })()""")
        check("""(() => {
            annotations.length = 0;
            annotations.push({type: 'Texto', x: 20, y: 20, w: 240, h: 120,
                              text: 'Texto de teste para a caixa', font: 24, color: '#000'});
            selectedIndex = 0;
            interactionMode = 'box-resize';
            resizeCorner = 's';
            const alvo = annotations[0];
            if (/[ns]/.test(resizeCorner)) alvo.autoHeight = false;
            resizeBoxShape(alvo, resizeCorner, {x: 260, y: 60}, 12);
            drawShape(surface(), alvo);
            interactionMode = null;
            resizeCorner = null;
            return alvo.autoHeight === false && alvo.h < 120;
        })()""")
        print("OK: caixa de texto cresce com o texto e reduz o texto quando a caixa e fixada")

        # --- desenho de verdade com o mouse: nuvem a mao livre e caixa de texto ---
        js("annotations.length = 0; selectedIndex = -1; clearStroke(); fitToWorkspace()")

        def canvas_point(x, y):
            # A imagem inteira cabe na area de trabalho, entao todo ponto do
            # documento tem um ponto correspondente dentro da janela.
            area = json.loads(js("JSON.stringify(canvas.getBoundingClientRect().toJSON())"))
            escala = area["width"] / js("docWidth")
            return QPoint(round(area["x"] + x * escala), round(area["y"] + y * escala))

        alvo = window.web.focusProxy() or window.web

        def arrastar(pontos):
            QTest.mousePress(alvo, Qt.MouseButton.LeftButton, pos=pontos[0])
            for ponto in pontos[1:]:
                QTest.mouseMove(alvo, ponto, delay=4)
            QTest.mouseRelease(alvo, Qt.MouseButton.LeftButton, pos=pontos[-1])

        js("byId('cfg-nuvem-livre').checked = true; handleFormatControlChanged(); selectTool('Nuvem')")
        laco = [canvas_point(700 + math.cos(i / 28 * math.tau) * 110,
                             150 + math.sin(i / 28 * math.tau) * 70) for i in range(29)]
        arrastar(laco)
        wait(lambda: js("annotations.length === 1"))
        check("annotations[0].type === 'Nuvem' && annotations[0].free === true && annotations[0].points.length > 8")
        check("annotationBounds(annotations[0]).w > 200 && shapeHitsPoint(annotations[0], annotations[0].points[0].x, annotations[0].points[0].y)")
        js("byId('cfg-nuvem-livre').checked = false; handleFormatControlChanged()")
        print("OK: nuvem a mao livre desenhada com o mouse real")

        js("selectTool('Texto')")
        QTest.mouseClick(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(120, 250))
        wait(lambda: js("Boolean(activeTextEditor)"))
        js("""(() => {
            const editor = activeTextEditor.editor;
            editor.value = 'Frase comprida o bastante para ocupar varias linhas dentro da caixa';
            editor.dispatchEvent(new Event('input'));
            return true;
        })()""")
        QTest.qWait(120)
        js("finalizeTextEditor(true, true)")
        wait(lambda: js("annotations.length === 2"))
        check("annotations[1].type === 'Texto' && annotations[1].text.length > 20 && annotations[1].h > annotations[1].font")
        alto = js("annotations[1].h")
        js("selectedIndex = 1; redraw()")
        alca = json.loads(js("JSON.stringify(boxHandlePoints(annotations[1]).find(p => p.code === 's'))"))
        arrastar([canvas_point(alca["x"], alca["y"]), canvas_point(alca["x"], alca["y"] - 20),
                  canvas_point(alca["x"], alca["y"] - 40)])
        QTest.qWait(150)
        check("annotations[1].autoHeight === false")
        assert js("annotations[1].h") < alto, "a caixa de texto nao encolheu ao arrastar a borda"
        check("""(() => {
            const c = surface();
            return textBoxLayout(c, annotations[1]).size < annotations[1].font;
        })()""")
        print("OK: caixa de texto arrastada pela borda encolhe o texto, como no PowerPoint")

        # --- chamada desenhada e editada com o mouse real ---
        js("annotations.length = 0; selectedIndex = -1; clearStroke(); selectTool('Chamada')")
        arrastar([canvas_point(180, 430), canvas_point(300, 390), canvas_point(380, 370)])
        wait(lambda: js("Boolean(activeTextEditor)"))
        js("""(() => {
            const editor = activeTextEditor.editor;
            editor.value = 'Precisamos separar aula concluida de conteudo consolidado antes de liberar';
            editor.dispatchEvent(new Event('input'));
            return true;
        })()""")
        QTest.qWait(120)
        js("finalizeTextEditor(true, true)")
        wait(lambda: js("annotations.length === 1"))
        check("annotations[0].type === 'Chamada' && annotations[0].textW > 40")
        check("""(() => calloutTextLayout(surface(), annotations[0]).lines.length > 1)()""")
        js("selectedIndex = 0; redraw()")
        larguraAntes = js("calloutTextWidth(annotations[0])")
        alcaTexto = json.loads(js("JSON.stringify(rectHandlePoints(calloutTextRect(annotations[0])).find(p => p.code === 'e'))"))
        arrastar([canvas_point(alcaTexto["x"], alcaTexto["y"]),
                  canvas_point(alcaTexto["x"] - 40, alcaTexto["y"]),
                  canvas_point(alcaTexto["x"] - 80, alcaTexto["y"])])
        QTest.qWait(150)
        assert js("calloutTextWidth(annotations[0])") < larguraAntes, "a borda da chamada nao estreitou a caixa"
        check("""(() => calloutTextLayout(surface(), annotations[0]).lines.length > 1)()""")
        print("OK: chamada desenhada com o mouse, texto em caixa e borda arrastavel")

        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); redraw()")

        # --- texto da chamada em caixa, igual a ferramenta Texto ---
        check("""(() => {
            const frase = 'Precisamos separar aula concluida de conteudo consolidado, lendo a explicacao inteira antes';
            const c = surface();
            const larga = {type:'Chamada', x:100, y:200, w:180, h:-60, color:'#000', thick:2,
                           font:24, text:frase, textW:300, autoHeight:true};
            const estreita = {...larga, textW:150};
            const linhasLarga = calloutTextLayout(c, larga).lines.length;
            const linhasEstreita = calloutTextLayout(c, estreita).lines.length;
            // Reflui na largura da caixa: mais estreita, mais linhas.
            if (!(linhasLarga > 1 && linhasEstreita > linhasLarga)) return false;
            // Altura fixada a mao: a fonte diminui ate caber, como na Texto.
            const fixa = {...larga, textH: 50, autoHeight: false};
            const reduzida = calloutTextLayout(c, fixa);
            if (!(reduzida.size < fixa.font && reduzida.size >= fixa.font * 0.25)) return false;
            // A caixa fica encostada no fim do pe, dos dois lados.
            const paraEsquerda = {...larga, w: -180};
            const direita = calloutTextRect(larga);
            const esquerda = calloutTextRect(paraEsquerda);
            return direita.x > larga.x + larga.w && esquerda.x + esquerda.w < paraEsquerda.x + paraEsquerda.w
                && annotationBounds(larga).w > Math.abs(larga.w);
        })()""")
        check("""(() => {
            annotations.length = 0;
            annotations.push({type:'Chamada', x:100, y:300, w:180, h:-60, color:'#000', thick:2,
                              font:24, text:'Frase longa o bastante para quebrar em varias linhas na caixa',
                              textW:300, autoHeight:true});
            selectedIndex = 0;
            const alvo = annotations[0];
            const alcas = rectHandlePoints(calloutTextRect(alvo));
            const leste = alcas.find(p => p.code === 'e');
            const achou = findResizeHandle(alvo, leste.x, leste.y);
            if (!achou || achou.handle !== 'callout-text') return false;
            resizeCalloutText(alvo, 'e', {x: leste.x - 90, y: leste.y});
            const sul = rectHandlePoints(calloutTextRect(alvo)).find(p => p.code === 's');
            resizeCalloutText(alvo, 's', {x: sul.x, y: sul.y - 24});
            annotations.length = 0;
            selectedIndex = -1;
            return Math.round(alvo.textW) === 210 && alvo.autoHeight === false && alvo.textH > 16;
        })()""")
        print("OK: texto da linha de chamada reflui na caixa e a borda redimensiona")

        # --- menu proprio da nuvem, como no Notas de Engenharia ---
        check("""(() => {
            const nuvem = document.querySelector('.tool-btn[data-tool="Nuvem"] + .stroke-menu-trigger');
            if (!nuvem) return false;
            nuvem.click();
            const menu = byId('tool-config-popover');
            const caixa = menu.getBoundingClientRect();
            const opcoes = menu.querySelectorAll('[data-cloud]');
            // O raio e digitado, na faixa propria da nuvem (3 a 60).
            const campo = menu.querySelector('.config-size');
            if (menu.hidden || caixa.width === 0 || opcoes.length !== 2 || !campo) return false;
            if (campo.min !== '3' || campo.max !== '60') return false;
            if (caixa.right > innerWidth || caixa.bottom > innerHeight) return false;
            campo.value = 41; campo.dispatchEvent(new Event('input'));
            const raioDigitado = toolSizes.Nuvem === 41;
            menu.querySelector('[data-cloud=free]').click();
            const virouLivre = cloudFreeMode === true && byId('cfg-nuvem-livre').checked === true;
            byId('tool-config-popover').querySelector('[data-cloud=box]').click();
            const voltou = cloudFreeMode === false;
            closeFormatPopover();
            return raioDigitado && virouLivre && voltou && currentTool === 'Nuvem';
        })()""")
        print("OK: nuvem de revisao com raio digitado e escolha do traco")

        # --- fluidez: o custo por evento do mouse nao cresce com o traco ---
        check("""(() => {
            const cronometrar = (repeticoes, fn) => {
                for (let i = 0; i < 30; i++) fn();
                const t0 = performance.now();
                for (let i = 0; i < repeticoes; i++) fn();
                return (performance.now() - t0) / repeticoes * 1000;   // microssegundos
            };
            selectTool('Caneta');
            const montar = quantidade => {
                beginStroke({x: 20, y: 20});
                for (let i = 1; i < quantidade; i++) appendStrokePoint({x: 20 + i * 2, y: 20 + Math.sin(i / 9) * 30});
            };
            montar(300);
            const curto = cronometrar(400, () => createShape('Caneta', {x:20,y:20}, {x:80,y:20}, getOptions()));
            montar(3000);
            const longo = cronometrar(400, () => createShape('Caneta', {x:20,y:20}, {x:80,y:20}, getOptions()));
            clearStroke();
            // Montar a marcacao a cada movimento do mouse tem custo constante.
            if (!(longo < Math.max(30, curto * 3))) return false;

            annotations.length = 0;
            const onda = (y, n) => Array.from({length: n}, (_, i) => ({x: 30 + i * 1.5, y: y + Math.sin(i / 20) * 40}));
            annotations.push({type:'Caneta', color:'#c00', thick:4, points: onda(120, 2000), x:30, y:120, w:900, h:0});
            annotations.push({type:'MarcaTexto', color:'#fc0', thick:6, points: onda(260, 2000), x:30, y:260, w:900, h:0});
            selectedIndex = -1;
            const sobrevoo = cronometrar(300, () => findAnnotationAt(600, 500));
            annotations.length = 0;
            selectTool('Mover', false);
            // Procurar a marcacao sob o cursor descarta os tracos longe dele.
            return sobrevoo < 60;
        })()""")
        print("OK: custo por evento do mouse constante ao riscar e ao sobrevoar")

        # --- alcas mantem o tamanho aparente com o zoom ---
        check("""(() => {
            const antes = screenUnits(9);
            const zoomAntes = zoomLevel;
            zoomLevel = Math.min(3, zoomAntes * 2);
            applyZoom();
            const depois = screenUnits(9);
            zoomLevel = zoomAntes;
            applyZoom();
            return depois < antes * 0.75;
        })()""")
        print("OK: alcas e tolerancias medidas em pixels de tela")

        # --- faixa de opcoes cabe inteira no tamanho minimo ---
        window.resize(capture.RIBBON_MIN_WIDTH, 600)
        QTest.qWait(250)
        application.processEvents()
        largura = js("window.innerWidth")
        assert largura == capture.RIBBON_MIN_WIDTH, largura
        sobra = js("""(() => {
            const faltando = [];
            document.querySelectorAll('.ribbon-content').forEach(element => {
                const ativa = element.classList.contains('active');
                element.classList.add('active');
                if (element.scrollWidth > element.clientWidth) {
                    faltando.push(element.id + ' precisa de ' + element.scrollWidth + 'px');
                }
                if (!ativa) element.classList.remove('active');
            });
            return faltando.join('; ');
        })()""")
        assert sobra == "", f"faixa com rolagem horizontal no tamanho minimo: {sobra}"
        print(f"OK: nenhuma guia precisa de rolagem horizontal em {capture.RIBBON_MIN_WIDTH}px")

        js("annotations.length = 0; selectedIndex = -1; clearStroke(); redraw()")
        print("VALIDACAO DAS FERRAMENTAS CONCLUIDA")
    finally:
        window.close()
        window.deleteLater()
        application.processEvents()
        temporary.cleanup()


if __name__ == "__main__":
    main()
