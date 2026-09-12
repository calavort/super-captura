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
        # Quando o teste devolve um motivo em vez de false, ele aparece junto:
        # "nao girou" diz muito mais do que a expressao inteira repetida.
        if js(source):
            return
        motivo = js(source.replace(" === true", "")) if " === true" in source else ""
        raise AssertionError(f"{source}{chr(10)}---> motivo: {motivo!r}")

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

        # --- alinhamento do texto: esquerda, centralizado e direita ---
        js("""
            window.medirTinta = (shape, rect) => {
                const c = surface();
                drawShape(c, shape);
                const dados = c.getImageData(0, 0, 400, 400).data;
                let soma = 0, peso = 0, min = 1e9, max = -1;
                const x0 = Math.max(0, Math.floor(rect.x)), x1 = Math.min(400, Math.ceil(rect.x + rect.w));
                const y0 = Math.max(0, Math.floor(rect.y)), y1 = Math.min(400, Math.ceil(rect.y + rect.h));
                for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
                    const alfa = dados[(y * 400 + x) * 4 + 3];
                    if (alfa > 40) { soma += x * alfa; peso += alfa; min = Math.min(min, x); max = Math.max(max, x); }
                }
                return {centro: peso ? soma / peso : 0, min, max, peso};
            };
        """)
        # Na caixa de Texto o alinhamento e literal: as linhas andam dentro dela.
        check("""(() => {
            const base = {type: 'Texto', x: 10, y: 10, w: 300, h: 0, font: 22, color: '#000',
                          text: ['Uma linha bem mais comprida que a outra', 'ok'].join(String.fromCharCode(10))};
            const caixa = {x: 10, y: 10, w: 300, h: 200};
            const medidas = ['left', 'center', 'right'].map(align => medirTinta({...base, align}, caixa));
            if (medidas.some(m => m.peso === 0)) return false;
            const [esq, meio, dir] = medidas;
            // O bloco inteiro anda: a esquerda de cada alinhamento e a propria ordem.
            return esq.centro < meio.centro && meio.centro < dir.centro
                && esq.min < meio.min && meio.min < dir.min
                && esq.max < dir.max;
        })()""")
        # Na chamada o alinhamento vale dentro do bloco: a linha mais larga fica
        # encostada no pe da seta nos tres casos, e so as curtas se mexem.
        check("""(() => {
            const base = {type: 'Chamada', x: 40, y: 40, w: 60, h: 60, font: 18, thick: 3, color: '#000',
                          text: ['Uma linha bem mais comprida que a outra', 'ok'].join(String.fromCharCode(10)), textW: 150};
            const medidas = ['left', 'center', 'right'].map(align => {
                const shape = {...base, align};
                return medirTinta(shape, calloutTextRect(shape));
            });
            if (medidas.some(m => m.peso === 0)) return false;
            const [esq, meio, dir] = medidas;
            if (!(esq.centro < meio.centro && meio.centro < dir.centro)) return false;
            // Bloco ancorado: a caixa de tinta fica no lugar (a folga de alguns
            // pixels e do antisserrilhado). Alinhar dentro da caixa larga, e nao
            // dentro do bloco, jogaria o texto dezenas de pixels para o lado.
            return Math.abs(esq.min - dir.min) <= 3 && Math.abs(esq.max - dir.max) <= 3;
        })()""")
        print("OK: alinhamento move as linhas no texto e mantem a chamada colada no pe da seta")

        # --- os botoes da faixa: exclusivos, espelhados nas duas guias e aplicados ---
        check("""(() => {
            annotations.length = 0;
            selectedIndex = -1;
            selectTool('Texto', false);
            const clicar = align => byId('btn-align-' + align).click();
            const marcados = () => ['left', 'center', 'right']
                .filter(a => byId('btn-align-' + a).classList.contains('active'));
            clicar('center');
            // Um marcado por vez, e a guia Edicao mostra o mesmo.
            if (marcados().join() !== 'center') return false;
            if (!byId('ed-btn-align-center').classList.contains('active')) return false;
            if (byId('btn-align-center').getAttribute('aria-pressed') !== 'true') return false;
            if (currentTextAlign() !== 'center' || getOptions().align !== 'center') return false;
            // Clicar na guia Edicao volta o estado para a guia Inicio.
            byId('ed-btn-align-right').click();
            if (marcados().join() !== 'right' || currentTextAlign() !== 'right') return false;
            // A escolha chega na marcacao selecionada.
            annotations.push({type: 'Texto', x: 20, y: 20, w: 200, h: 60, text: 'abc', font: 20, color: '#000'});
            selectedIndex = 0;
            byId('btn-align-center').click();
            if (annotations[0].align !== 'center') return false;
            // E e lida de volta ao selecionar outra marcacao.
            annotations.push({type: 'Chamada', x: 10, y: 10, w: 60, h: 40, text: 'x', font: 18, thick: 3, color: '#000', align: 'right'});
            syncFormatControlsFromSelection(annotations[1]);
            if (currentTextAlign() !== 'right') return false;
            // Cota, balao e triangulo guardam um valor so: os botoes apagam neles.
            selectedIndex = -1;
            selectTool('Balao', false);
            if (!byId('btn-align-left').disabled || !byId('ed-btn-align-left').disabled) return false;
            selectTool('Texto', false);
            if (byId('btn-align-left').disabled) return false;
            annotations.length = 0;
            selectTool('Mover', false);
            return true;
        })()""")
        print("OK: botoes de alinhamento exclusivos, espelhados nas duas guias e aplicados a selecao")

        # --- o alinhamento sobrevive ao salvar e reabrir as preferencias ---
        check("""(() => {
            const original = appSettings;
            try {
                setTextAlign('center');
                if (readPreferences().text_align !== 'center') return false;
                applySettings({...original, ...readPreferences(), text_align: 'right'});
                if (currentTextAlign() !== 'right') return false;
                // Valor estranho no arquivo nao pode deixar a faixa sem marcado nenhum.
                applySettings({...original, ...readPreferences(), text_align: 'justificado'});
                return currentTextAlign() === 'left';
            } finally {
                applySettings(original);
            }
        })()""")
        print("OK: alinhamento gravado nas preferencias e restaurado na abertura")

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
        js("finalizeTextEditor(true)")
        wait(lambda: js("annotations.length === 2"))
        check("annotations[1].type === 'Texto' && annotations[1].text.length > 20 && annotations[1].h > annotations[1].font")
        alto = js("annotations[1].h")
        js("selectTool('Mover', false); selectedIndex = 1; redraw()")
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
        js("finalizeTextEditor(true)")
        wait(lambda: js("annotations.length === 1"))
        check("annotations[0].type === 'Chamada' && annotations[0].textW > 40")
        check("""(() => calloutTextLayout(surface(), annotations[0]).lines.length > 1)()""")
        js("selectTool('Mover', false); selectedIndex = 0; redraw()")
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
            // A caixa fica encostada no fim do pe, dos dois lados. As duas
            // chamadas cabem inteiras na folha, que e o que o desenho garante.
            const paraEsquerda = {...larga, x: 700, w: -180};
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

        # --- a ferramenta usada continua ativa ---
        js("annotations.length = 0; selectedIndex = -1; clearStroke(); fitToWorkspace()")
        for ferramenta in ("Retangulo", "Circulo", "Seta", "Caneta", "Balao", "Revisao"):
            js(f"annotations.length = 0; selectedIndex = -1; selectTool('{ferramenta}', false)")
            arrastar([canvas_point(120, 120), canvas_point(230, 200), canvas_point(300, 250)])
            QTest.qWait(120)
            assert js("currentTool") == ferramenta, f"{ferramenta} saiu para {js('currentTool')}"
            assert js("annotations.length") == 1, ferramenta
        # As de texto passam pelo editor flutuante e eram as que voltavam ao Mover.
        for ferramenta in ("Texto", "Chamada", "CotaLivre", "CotaAngulo"):
            js(f"annotations.length = 0; selectedIndex = -1; selectTool('{ferramenta}', false)")
            if ferramenta == "Texto":
                QTest.mouseClick(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(150, 300))
            else:
                arrastar([canvas_point(120, 120), canvas_point(260, 200)])
            wait(lambda: js("Boolean(activeTextEditor)"))
            js("activeTextEditor.editor.value = 'ok'; finalizeTextEditor(true)")
            QTest.qWait(120)
            assert js("currentTool") == ferramenta, f"{ferramenta} saiu para {js('currentTool')}"
            assert js("annotations.length") == 1, ferramenta
        # Interromper continua sendo o caminho de volta para o Mover.
        js("selectTool('Retangulo', false); interruptCommand()")
        check("currentTool === 'Mover'")
        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); redraw()")
        print("OK: a ferramenta usada continua ativa; so o Interromper volta para o Mover")

        # --- nada e desenhado fora da folha ---
        js("annotations.length = 0; selectedIndex = -1; clearStroke(); fitToWorkspace()")
        moldura = json.loads(js("JSON.stringify(canvas.getBoundingClientRect().toJSON())"))

        def fora(dx, dy):
            return QPoint(round(moldura["x"] + moldura["width"] + dx),
                          round(moldura["y"] + moldura["height"] + dy))

        for ferramenta in ("Retangulo", "Circulo", "Seta", "Linha", "Caneta", "Nuvem", "Balao", "Revisao"):
            js(f"annotations.length = 0; selectedIndex = -1; selectTool('{ferramenta}', false)")
            arrastar([canvas_point(940, 560), fora(60, 40), fora(180, 120)])
            QTest.qWait(120)
            dentro = js("""(() => {
                const s = annotations[0];
                if (!s) return 'sem marcacao';
                const b = annotationBounds(s);
                return (b.x >= -1 && b.y >= -1 && b.x + b.w <= docWidth + 1 && b.y + b.h <= docHeight + 1)
                    ? '' : JSON.stringify(b) + ' fora de ' + docWidth + 'x' + docHeight;
            })()""")
            assert dentro == "", f"{ferramenta}: {dentro}"
        # O editor de texto tambem nasce dentro, mesmo clicado na quina.
        js("annotations.length = 0; selectedIndex = -1; selectTool('Texto', false)")
        QTest.mouseClick(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(985, 585))
        wait(lambda: js("Boolean(activeTextEditor)"))
        check("""(() => {
            const r = activeTextEditor.editor.getBoundingClientRect();
            const c = canvas.getBoundingClientRect();
            return r.left >= c.left - 2 && r.top >= c.top - 2
                && r.right <= c.right + 2 && r.bottom <= c.bottom + 2;
        })()""")
        js("activeTextEditor.editor.value = 'texto na quina'; finalizeTextEditor(true)")
        QTest.qWait(120)
        check("""(() => {
            const b = annotationBounds(annotations[0]);
            return b.x >= -1 && b.y >= -1 && b.x + b.w <= docWidth + 1 && b.y + b.h <= docHeight + 1;
        })()""")
        # A caixa da chamada espelha para o lado que cabe, sem mexer na ponta.
        check("""(() => {
            const base = {type: 'Chamada', color: '#000', thick: 3, font: 20, textW: 300,
                          text: 'Texto da chamada perto da borda', autoHeight: true};
            const folgado = {...base, x: 200, y: 300, w: 150, h: -40};
            const naBorda = {...base, x: docWidth - 320, y: 300, w: 300, h: -40};
            const r1 = calloutTextRect(folgado), r2 = calloutTextRect(naBorda);
            // No meio da folha a caixa sai para a direita, como sempre saiu.
            if (!(r1.dir === 1 && r1.x > folgado.x + folgado.w)) return false;
            // Encostada na borda ela vai para o outro lado do pe, e cabe.
            return r2.dir === -1 && r2.x >= 0 && r2.x + r2.w <= docWidth
                && r2.x + r2.w < naBorda.x + naBorda.w;
        })()""")
        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); redraw()")
        print("OK: marcacao, caixa de digitacao e caixa da chamada nao passam da folha")

        # --- encostar na borda nao solta a ferramenta ---
        js("annotations.length = 0; selectedIndex = -1; clearStroke(); selectTool('Retangulo', false)")
        QTest.mousePress(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(300, 300))
        QTest.mouseMove(alvo, canvas_point(500, 400), delay=5)
        # Bem para fora do canvas, com o botao ainda pressionado.
        QTest.mouseMove(alvo, fora(200, 150), delay=5)
        QTest.qWait(120)
        application.processEvents()
        check("""(() => {
            // O comando continua vivo: nada foi gravado e o desenho esta preso
            // a borda, nao solto do lado de fora.
            if (!isDrawing || !preview || annotations.length !== 0) return false;
            return Math.abs(preview.x + preview.w - docWidth) < 1
                && Math.abs(preview.y + preview.h - docHeight) < 1;
        })()""")
        # Voltando para dentro, o retangulo volta a obedecer.
        QTest.mouseMove(alvo, canvas_point(600, 420), delay=5)
        QTest.qWait(120)
        application.processEvents()
        check("""(() => preview && Math.abs(preview.x + preview.w - 600) < 6
                  && Math.abs(preview.y + preview.h - 420) < 6)()""")
        QTest.mouseRelease(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(600, 420))
        QTest.qWait(150)
        application.processEvents()
        check("""(() => {
            const s = annotations[0];
            return annotations.length === 1 && s.type === 'Retangulo'
                && Math.abs(s.x + s.w - 600) < 6 && Math.abs(s.y + s.h - 420) < 6;
        })()""")
        # Soltando de fato do lado de fora, a marcacao fica na borda.
        js("annotations.length = 0; selectedIndex = -1; selectTool('Circulo', false)")
        QTest.mousePress(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(700, 300))
        QTest.mouseMove(alvo, fora(150, 120), delay=5)
        QTest.mouseRelease(alvo, Qt.MouseButton.LeftButton, pos=fora(150, 120))
        QTest.qWait(150)
        application.processEvents()
        check("""(() => {
            const b = annotations[0] && annotationBounds(annotations[0]);
            return annotations.length === 1 && !isDrawing && !preview
                && b.x >= -1 && b.y >= -1 && b.x + b.w <= docWidth + 1 && b.y + b.h <= docHeight + 1;
        })()""")
        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); redraw()")
        print("OK: o comando segue vivo com o ponteiro fora do canvas e so termina ao soltar")

        # --- setas empurram a figura selecionada ---
        js("""
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: 300, y: 200, w: 160, h: 120,
                              color: '#107C41', thick: 4});
            selectedIndex = 0;
            selectTool('Mover', false);
            selectedIndex = 0;
            redraw();
        """)
        passo = js("nudgeStep(false)")
        passo_largo = js("nudgeStep(true)")
        # Calibragem: nunca menor que um pixel da folha nem que um pixel de tela,
        # e o Shift anda dez vezes mais.
        assert passo >= 1, passo
        assert abs(passo_largo - passo * 10) < 1e-6, (passo, passo_largo)
        assert passo >= js("screenUnits(1)") - 1e-6, (passo, js("screenUnits(1)"))

        antes = json.loads(js("JSON.stringify({x: annotations[0].x, y: annotations[0].y})"))
        QTest.keyClick(alvo, Qt.Key.Key_Right)
        QTest.qWait(60)
        application.processEvents()
        depois = json.loads(js("JSON.stringify({x: annotations[0].x, y: annotations[0].y})"))
        assert abs(depois["x"] - antes["x"] - passo) < 1e-6, (antes, depois, passo)
        assert abs(depois["y"] - antes["y"]) < 1e-6, (antes, depois)

        QTest.keyClick(alvo, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
        QTest.qWait(60)
        application.processEvents()
        largo = json.loads(js("JSON.stringify({x: annotations[0].x, y: annotations[0].y})"))
        assert abs(largo["y"] - depois["y"] - passo_largo) < 1e-6, (depois, largo, passo_largo)

        # Uma rajada de setas vira um unico desfazer. Antes, deixa a rajada
        # anterior fechar: teclas separadas por menos de meio segundo sao a
        # mesma rajada, e e isso que o teste abaixo vai conferir.
        QTest.qWait(600)
        application.processEvents()
        js("historyStack.length = 0; redoStack.length = 0")
        partida = js("annotations[0].x")
        for _ in range(6):
            QTest.keyClick(alvo, Qt.Key.Key_Right)
        QTest.qWait(120)
        application.processEvents()
        andou = js("annotations[0].x")
        assert abs(andou - partida - passo * 6) < 1e-6, (partida, andou)
        # A transacao so fecha quando as teclas param.
        QTest.qWait(600)
        application.processEvents()
        assert js("historyStack.length") == 1, js("historyStack.length")
        js("undoAnnotation()")
        QTest.qWait(120)
        assert abs(js("annotations[0].x") - partida) < 1e-6, (js("annotations[0].x"), partida)
        print("OK: setas empurram a marcacao, Shift anda dez vezes mais e a rajada e um so desfazer")

        # --- a seta tambem respeita a borda da folha ---
        js("""
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: docWidth - 60, y: 40, w: 50, h: 40,
                              color: '#107C41', thick: 4});
            selectedIndex = 0;
            redraw();
        """)
        for _ in range(12):
            QTest.keyClick(alvo, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        QTest.qWait(700)
        application.processEvents()
        check("""(() => {
            const b = annotationBounds(annotations[0]);
            return b.x + b.w <= docWidth + 1 && b.x >= -1;
        })()""")

        # --- com o editor de texto aberto a seta e do texto, nao da marcacao ---
        js("annotations.length = 0; selectedIndex = -1; selectTool('Texto', false)")
        QTest.mouseClick(alvo, Qt.MouseButton.LeftButton, pos=canvas_point(200, 200))
        wait(lambda: js("Boolean(activeTextEditor)"))
        js("annotations.push({type: 'Retangulo', x: 300, y: 300, w: 80, h: 60, color: '#000', thick: 2});"
           " selectedIndex = annotations.length - 1")
        alvoX = js("annotations[selectedIndex].x")
        QTest.keyClick(alvo, Qt.Key.Key_Right)
        QTest.qWait(80)
        application.processEvents()
        assert js("annotations[selectedIndex].x") == alvoX, "a seta mexeu na marcacao enquanto digitava"
        js("finalizeTextEditor(false)")
        QTest.qWait(120)
        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); redraw()")
        print("OK: a seta para na borda e nao rouba a digitacao do editor de texto")

        # --- imagens da guia Edicao encaixam umas nas outras ---
        check("""(() => {
            const modoAntes = workspaceMode, itensAntes = editionItems;
            const larguraAntes = docWidth, alturaAntes = docHeight;
            try {
                workspaceMode = 'edition';
                docWidth = 1600; docHeight = 1000;
                editionItems = [{x: 200, y: 200, w: 300, h: 200},
                                {x: 800, y: 600, w: 240, h: 160}];
                const movel = editionItems[1];
                const tolerancia = editionSnapTolerance();
                if (!(tolerancia > 0)) return false;

                // Topo quase alinhado com o topo do outro: encaixa exato.
                moveEditionItem(movel, 800, 200 + tolerancia * 0.5);
                if (movel.y !== 200) return false;
                if (!editionGuides.some(g => !g.vertical && g.at === 200)) return false;

                // Base do movel quase na base do outro (200 + 200 = 400).
                moveEditionItem(movel, 800, 400 - movel.h + tolerancia * 0.5);
                if (movel.y !== 400 - movel.h) return false;

                // Base do movel encostando no TOPO do outro: tambem encaixa.
                moveEditionItem(movel, 800, 200 - movel.h - tolerancia * 0.5);
                if (movel.y !== 200 - movel.h) return false;

                // Centros alinhados na vertical (200 + 150 = 350 = meio do fixo).
                moveEditionItem(movel, 350 - movel.w / 2 + tolerancia * 0.5, 700);
                if (movel.x !== 350 - movel.w / 2) return false;

                // Longe de tudo nao encaixa nem desenha linha.
                moveEditionItem(movel, 900, 700);
                if (movel.x !== 900 || movel.y !== 700 || editionGuides.length) return false;

                // Redimensionar tambem encaixa: a borda direita procura a do
                // outro, que fica em 200 + 300 = 500.
                movel.x = 300; movel.y = 600; movel.w = 240; movel.h = 160;
                resizeEditionItem(movel, {x: 500 + tolerancia * 0.5, y: 0});
                if (Math.abs(movel.x + movel.w - 500) > 0.001) return false;

                // A seta empurra a imagem selecionada tambem, e sem encaixe:
                // ela e o ajuste fino, travar de tres em tres seria o contrario.
                movel.x = 900; movel.y = 700;
                selectedEditionItemIndex = 1;
                const passo = nudgeStep(false);
                nudgeSelection(passo, 0);
                nudgeSelection(0, -passo);
                if (Math.abs(movel.x - (900 + passo)) > 1e-6) return false;
                if (Math.abs(movel.y - (700 - passo)) > 1e-6) return false;
                endNudgeBurst();
                selectedEditionItemIndex = -1;

                // Concluir o arrasto apaga as linhas de referencia.
                moveEditionItem(movel, 800, 200);
                finalizeEditionItemTransform(movel);
                return editionGuides.length === 0;
            } finally {
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                docWidth = larguraAntes; docHeight = alturaAntes;
                editionGuides = [];
            }
        })()""")
        print("OK: imagens da guia Edicao encaixam em borda e centro, com linha de referencia")

        # --- vao igual entre imagens, como no PowerPoint ---
        # A folha e as posicoes sao escolhidas para nenhum alvo de ALINHAMENTO
        # cair perto dos alvos de espacamento: senao o alinhamento venceria e o
        # teste passaria pelo motivo errado.
        check("""(() => {
            const modoAntes = workspaceMode, itensAntes = editionItems;
            const larguraAntes = docWidth, alturaAntes = docHeight;
            try {
                workspaceMode = 'edition';
                docWidth = 2000; docHeight = 1100;
                // Duas fixas com 100 px de vao entre elas (700..800).
                editionItems = [{x: 500, y: 300, w: 200, h: 150},
                                {x: 800, y: 300, w: 200, h: 150},
                                {x: 1500, y: 700, w: 200, h: 150}];
                const movel = editionItems[2];
                const t = editionSnapTolerance();

                // Repetindo o vao depois da segunda: 1000 + 100 = 1100.
                moveEditionItem(movel, 1100 + t * 0.5, 700);
                if (Math.abs(movel.x - 1100) > 1e-6) return 'depois de B: ' + movel.x;
                const marcas = editionGuides.filter(g => g.vao && g.eixo === 'x');
                // Duas marcas: o vao que ja existia e o que acabou de casar.
                if (marcas.length !== 2) return 'marcas: ' + JSON.stringify(editionGuides);
                const larguras = marcas.map(m => Math.round(m.ate - m.de)).sort();
                if (larguras[0] !== 100 || larguras[1] !== 100) return 'larguras: ' + larguras;
                // A marca sai na altura do meio da imagem arrastada.
                if (Math.abs(marcas[0].em - (movel.y + movel.h / 2)) > 1e-6) return 'altura da marca';

                // Repetindo o vao antes da primeira: 500 - 100 - 200 = 200.
                moveEditionItem(movel, 200 - t * 0.5, 700);
                if (Math.abs(movel.x - 200) > 1e-6) return 'antes de A: ' + movel.x;
                if (editionGuides.filter(g => g.vao).length !== 2) return 'marcas antes de A';

                // No meio de um vao largo, com as duas folgas iguais.
                editionItems = [{x: 500, y: 300, w: 200, h: 150},
                                {x: 1200, y: 300, w: 200, h: 150},
                                {x: 1700, y: 700, w: 200, h: 150}];
                const meio = editionItems[2];
                // Vao de 700 a 1200 para uma imagem de 200: sobra 250 de cada
                // lado, entao ela comeca em 850.
                moveEditionItem(meio, 850 + t * 0.5, 700);
                if (Math.abs(meio.x - 850) > 1e-6) return 'meio: ' + meio.x;
                if (editionGuides.filter(g => g.vao).length !== 2) return 'marcas do meio';

                // Longe de qualquer repeticao nao inventa marca nenhuma.
                moveEditionItem(meio, 1020, 700);
                if (editionGuides.length) return 'inventou: ' + JSON.stringify(editionGuides);

                // Alinhar tem preferencia: com uma borda ao alcance, e ela que
                // manda, e a marca que aparece e a linha, nao o vao.
                editionItems = [{x: 500, y: 300, w: 200, h: 150},
                                {x: 800, y: 300, w: 200, h: 150},
                                {x: 1500, y: 700, w: 200, h: 150}];
                const disputa = editionItems[2];
                moveEditionItem(disputa, 800 + t * 0.3, 700);
                if (Math.abs(disputa.x - 800) > 1e-6) return 'alinhamento: ' + disputa.x;
                if (!editionGuides.some(g => !g.vao && g.vertical)) return 'faltou a linha';
                return editionGuides.some(g => g.vao) ? 'vao junto com linha' : true;
            } finally {
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                docWidth = larguraAntes; docHeight = alturaAntes;
                editionGuides = [];
            }
        })() === true""")
        print("OK: imagens repetem o vao das vizinhas e a marca do espaco aparece")

        # --- corte de uma imagem da guia Edicao ---
        js("""
            window.imagemDeTeste = (() => {
                const c = document.createElement('canvas');
                c.width = 400; c.height = 300;
                const p = c.getContext('2d');
                p.fillStyle = '#107C41'; p.fillRect(0, 0, 400, 300);
                p.fillStyle = '#C00000'; p.fillRect(0, 0, 200, 150);
                const img = new Image();
                img.src = c.toDataURL();
                return img;
            })();
        """)
        wait(lambda: js("Boolean(imagemDeTeste.naturalWidth)"))
        check("""(() => {
            const modoAntes = workspaceMode, itensAntes = editionItems;
            const larguraAntes = docWidth, alturaAntes = docHeight;
            const anotacoesAntes = annotations;
            try {
                workspaceMode = 'edition';
                docWidth = 1600; docHeight = 1000;
                annotations = [];
                editionItems = [{x: 200, y: 200, w: 400, h: 300, image: imagemDeTeste}];
                selectedEditionItemIndex = 0;
                historyStack.length = 0; redoStack.length = 0;

                if (itemIsCropped(editionItems[0])) return false;
                if (!beginEditionCrop(0)) return false;
                const item = editionItems[0];

                // A alca da direita puxa a borda para dentro: fica a metade
                // esquerda da imagem, e o resto continua guardado.
                resizeEditionCrop(item, 'e', {x: 400, y: 0});
                if (Math.abs(item.w - 200) > 1e-6) return false;
                if (Math.abs(itemCrop(item).w - 0.5) > 1e-6) return false;
                if (Math.abs(itemCrop(item).x) > 1e-6) return false;
                // A imagem inteira continua ocupando o mesmo lugar de antes.
                const quadro = itemFullFrame(item);
                if (Math.abs(quadro.x - 200) > 1e-6 || Math.abs(quadro.w - 400) > 1e-6) return false;

                // A alca de cima apara por cima.
                resizeEditionCrop(item, 'n', {x: 0, y: 350});
                if (Math.abs(item.y - 350) > 1e-6) return false;
                if (Math.abs(itemCrop(item).y - 0.5) > 1e-6) return false;
                if (Math.abs(itemCrop(item).h - 0.5) > 1e-6) return false;

                // A alca nao passa da imagem inteira nem some com o pedaco.
                resizeEditionCrop(item, 'e', {x: 5000, y: 0});
                if (item.x + item.w > quadro.x + quadro.w + 1e-6) return false;
                resizeEditionCrop(item, 'e', {x: -5000, y: 0});
                if (item.w < CROP_MIN - 1e-6) return false;

                // O pedaco desenhado sai da parte certa da imagem.
                resizeEditionCrop(item, 'e', {x: 400, y: 0});
                const origem = cropSourceRect(item, imagemDeTeste);
                if (Math.abs(origem.sw - 200) > 1e-6) return false;
                if (Math.abs(origem.sy - 150) > 1e-6) return false;

                // Sair do modo fecha uma transacao so, nao uma por alca.
                endEditionCrop(true);
                if (editionCropIndex !== -1) return false;
                if (historyStack.length !== 1) return false;
                if (!itemIsCropped(editionItems[0])) return false;

                // Desfazer devolve a imagem inteira.
                undoAnnotation();
                if (itemIsCropped(editionItems[0])) return false;

                // ESC no meio do corte volta ao enquadramento de antes e nao
                // deixa entulho no historico.
                historyStack.length = 0; redoStack.length = 0;
                beginEditionCrop(0);
                resizeEditionCrop(editionItems[0], 'e', {x: 380, y: 0});
                endEditionCrop(false);
                if (itemIsCropped(editionItems[0])) return false;
                if (historyStack.length !== 0) return false;

                // E Restaurar devolve a imagem inteira no lugar dela.
                beginEditionCrop(0);
                resizeEditionCrop(editionItems[0], 'e', {x: 400, y: 0});
                endEditionCrop(true);
                if (!itemIsCropped(editionItems[0])) return false;
                resetEditionCrop(0);
                const voltou = editionItems[0];
                return !itemIsCropped(voltou) && Math.abs(voltou.x - 200) < 1e-6
                    && Math.abs(voltou.w - 400) < 1e-6 && Math.abs(voltou.h - 300) < 1e-6;
            } finally {
                editionCropIndex = -1;
                editionCropBefore = null;
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                annotations = anotacoesAntes;
                selectedEditionItemIndex = -1;
                docWidth = larguraAntes; docHeight = alturaAntes;
            }
        })()""")
        print("OK: corte por imagem apara, guarda o resto, e um desfazer so e volta com Restaurar")

        # --- o menu do botao direito abre sobre a imagem ---
        check("""(() => {
            const modoAntes = workspaceMode, itensAntes = editionItems;
            try {
                workspaceMode = 'edition';
                editionItems = [{x: 200, y: 200, w: 400, h: 300, image: imagemDeTeste}];
                const itensDoMenu = () => [...document.querySelectorAll('.image-menu button')]
                    .map(b => b.textContent.trim());
                showEditionImageMenu(0, 120, 120);
                if (!document.querySelector('.image-menu')) return false;
                const semCorte = itensDoMenu();
                // Sem corte ainda, "Restaurar" nao faz sentido e nao aparece.
                if (semCorte.some(t => t.includes('Restaurar'))) return false;
                if (!semCorte.some(t => t.includes('Cortar imagem'))) return false;
                if (!semCorte.some(t => t.includes('Transparência'))) return false;
                if (!semCorte.some(t => t.includes('Rotacionar'))) return false;
                if (!semCorte.some(t => t.includes('Remover imagem'))) return false;
                editionItems[0].crop = {x: 0, y: 0, w: 0.5, h: 1};
                showEditionImageMenu(0, 120, 120);
                const comCorte = itensDoMenu();
                // Um menu por vez: abrir o segundo fecha o primeiro.
                if (document.querySelectorAll('.image-menu').length !== 1) return false;
                if (comCorte.length !== semCorte.length + 1) return false;
                if (!comCorte.some(t => t.includes('Restaurar'))) return false;
                closeEditionImageMenu();
                return !document.querySelector('.image-menu');
            } finally {
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                closeEditionImageMenu();
            }
        })()""")
        print("OK: menu do botao direito com Cortar, Restaurar (so quando cortada) e Remover")

        # --- com zoom alto a rolagem alcanca os quatro lados ---
        js("fitToWorkspace()")
        QTest.qWait(150)
        js("zoomLevel = 3; applyZoom()")
        QTest.qWait(250)
        application.processEvents()
        check("""(() => {
            const w = byId('workspace'), c = byId('canvas-container');
            w.scrollLeft = 0; w.scrollTop = 0;
            const wr = w.getBoundingClientRect(), cr = c.getBoundingClientRect();
            // Rolagem no inicio: a quina de cima e da esquerda tem de estar
            // visivel. Com justify-content:center ela ficava em offset negativo,
            // fora do alcance da barra de rolagem.
            return cr.left - wr.left >= -1 && cr.top - wr.top >= -1
                && w.scrollWidth > w.clientWidth && w.scrollHeight > w.clientHeight;
        })()""")
        js("fitToWorkspace()")
        QTest.qWait(150)
        print("OK: com zoom alem da janela a rolagem alcanca a quina de cima e da esquerda")

        # --- o buffer guarda a captura inteira, sem jogar detalhe fora ---
        js("""
            window.grande = document.createElement('canvas');
            grande.width = 2560; grande.height = 1440;
            const p = grande.getContext('2d');
            p.fillStyle = '#ffffff'; p.fillRect(0, 0, 2560, 1440);
            p.fillStyle = '#111';
            for (let y = 24; y < 1440; y += 20) {
                p.font = '14px Segoe UI';
                p.fillText('texto miudo de teste ' + y + ' iiii llll 0123456789', 24, y);
            }
            window.imagemGrande = grande;
            loadImageData(grande.toDataURL(), false, false);
        """)
        wait(lambda: js("Boolean(bgImage && bgImage.naturalWidth === 2560)"))
        QTest.qWait(400)
        js("fitToWorkspace()")
        QTest.qWait(400)
        application.processEvents()
        check("""(() => {
            // Com a folha inteira na janela, o buffer tem de cobrir a resolucao
            // da propria captura: era ai que 11% do detalhe se perdia antes de a
            // tela reduzir o resto.
            if (canvas.width < bgImage.naturalWidth - 2) return false;
            // E a copia preparada do fundo passa a valer para qualquer reducao.
            if (backgroundRenderSource(0.9) === bgImage) return false;
            // Sem reducao nenhuma ela nao e feita: desenhar 1:1 ja e o melhor.
            return backgroundRenderSource(1) === bgImage;
        })()""")
        # O teto de memoria continua mandando: imagem enorme com zoom alto nao
        # pode estourar o buffer so para nao perder detalhe.
        check("""(() => {
            const zoomAntes = zoomLevel;
            zoomLevel = 3;
            applyZoom();
            const pixels = canvas.width * canvas.height;
            zoomLevel = zoomAntes;
            applyZoom();
            return pixels <= MAX_RENDER_PIXELS * 1.02;
        })()""")
        # A foto da guia Edicao tambem: a copia e feita na resolucao da TELA.
        check("""(() => {
            const modoAntes = workspaceMode, itensAntes = editionItems;
            const larguraAntes = docWidth, alturaAntes = docHeight;
            try {
                workspaceMode = 'edition';
                docWidth = 1600; docHeight = 1000;
                editionItems = [{x: 0, y: 0, w: 400, h: 225, image: imagemGrande}];
                const item = editionItems[0];
                const fonte = editionRenderSource(item);
                // Sem a escala de desenho a copia sairia com 400 px de largura e
                // seria reduzida de novo na hora de desenhar: duas reducoes.
                const esperado = Math.round(400 * Math.max(1, renderScale()));
                return fonte !== item.image && Math.abs(item.proxyWidth - esperado) <= 1;
            } finally {
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                docWidth = larguraAntes; docHeight = alturaAntes;
            }
        })()""")
        # Volta para a folha de sempre.
        js("loadImageData(sample.toDataURL(), false, false)")
        wait(lambda: js("Boolean(bgImage && bgImage.naturalWidth === 1000)"))
        QTest.qWait(300)
        js("annotations.length = 0; selectedIndex = -1; fitToWorkspace()")
        QTest.qWait(200)
        print("OK: buffer cobre a resolucao da imagem, com teto de memoria e sem reducao dupla")

        # --- transparencia e giro ---
        js("annotations.length = 0; selectedIndex = -1; clearStroke(); selectTool('Mover', false); fitToWorkspace()")
        QTest.qWait(200)
        check("""(() => {
            // Transparencia: a tinta some proporcionalmente, e o valor e preso
            // antes do zero - marcacao invisivel nao da para selecionar de volta.
            const contar = shape => {
                const c = surface();
                drawShape(c, shape);
                const d = c.getImageData(0, 0, 400, 400).data;
                let soma = 0;
                for (let i = 3; i < d.length; i += 4) soma += d[i];
                return soma;
            };
            const base = {type: 'Retangulo', x: 40, y: 40, w: 300, h: 200, color: '#000', thick: 10};
            const cheio = contar(base);
            const meio = contar({...base, opacity: 0.5});
            const quase = contar({...base, opacity: 0});
            if (!(cheio > 0)) return 'nao desenhou';
            if (Math.abs(meio / cheio - 0.5) > 0.05) return 'meia tinta: ' + (meio / cheio);
            if (!(quase > 0 && quase < cheio * 0.15)) return 'piso: ' + (quase / cheio);
            if (shapeOpacity({opacity: 0}) < 0.05) return 'piso abaixo do minimo';
            return true;
        })() === true""")
        check("""(() => {
            // Giro: o desenho gira em torno do centro, e o centro fica onde esta.
            const base = {type: 'Retangulo', x: 100, y: 150, w: 200, h: 60, color: '#000', thick: 6};
            const caixaDe = shape => {
                const c = surface();
                drawShape(c, shape);
                const d = c.getImageData(0, 0, 400, 400).data;
                let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
                for (let y = 0; y < 400; y++) for (let x = 0; x < 400; x++) {
                    if (d[(y*400 + x)*4 + 3] > 40) {
                        x0 = Math.min(x0, x); x1 = Math.max(x1, x);
                        y0 = Math.min(y0, y); y1 = Math.max(y1, y);
                    }
                }
                return {x: x0, y: y0, w: x1 - x0, h: y1 - y0};
            };
            const reto = caixaDe(base);
            const girado = caixaDe({...base, angle: 90});
            // Em pe, a caixa desenhada troca de lados.
            if (Math.abs(girado.w - reto.h) > 3 || Math.abs(girado.h - reto.w) > 3) {
                return 'nao trocou de lados: ' + JSON.stringify([reto, girado]);
            }
            // E continua centrada no mesmo ponto.
            const centroReto = [reto.x + reto.w/2, reto.y + reto.h/2];
            const centroGirado = [girado.x + girado.w/2, girado.y + girado.h/2];
            if (Math.abs(centroReto[0] - centroGirado[0]) > 2) return 'centro andou em x';
            if (Math.abs(centroReto[1] - centroGirado[1]) > 2) return 'centro andou em y';
            // A caixa no mundo acompanha o giro; a da marcacao em si, nao.
            const mundo = rotatedBounds({...base, angle: 90});
            if (Math.abs(mundo.w - 60) > 1 || Math.abs(mundo.h - 200) > 1) {
                return 'rotatedBounds: ' + JSON.stringify(mundo);
            }
            if (Math.abs(annotationBounds({...base, angle: 90}).w - 200) > 1) return 'bounds locais mudaram';
            return true;
        })() === true""")
        check("""(() => {
            // O clique segue o desenho: num retangulo em pe, o ponto que agora e
            // dele responde, e o que deixou de ser, nao.
            // O retangulo e so contorno: os pontos ficam EM CIMA do traco.
            // Deitado ele vai de x 100 a 300, y 180 a 220, centrado em (200,200);
            // em pe, de x 180 a 220, y 100 a 300.
            const shape = {type: 'Retangulo', x: 100, y: 180, w: 200, h: 40, color: '#000', thick: 4};
            const noTracoDeitado = {x: 300, y: 200};
            const noTracoEmPe = {x: 200, y: 300};
            if (!shapeHitsPoint(shape, noTracoDeitado.x, noTracoDeitado.y)) return 'deitado nao pegou';
            if (shapeHitsPoint(shape, noTracoEmPe.x, noTracoEmPe.y)) return 'deitado pegou onde nao devia';
            const emPe = {...shape, angle: 90};
            if (!shapeHitsPoint(emPe, noTracoEmPe.x, noTracoEmPe.y)) return 'em pe nao pegou';
            if (shapeHitsPoint(emPe, noTracoDeitado.x, noTracoDeitado.y)) return 'em pe pegou onde nao devia';
            return true;
        })() === true""")
        check("""(() => {
            // Aplicar pelo menu: com marcacao selecionada mexe nela; sem
            // selecao, fica guardado para a proxima.
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: 100, y: 100, w: 120, h: 80, color: '#000', thick: 4});
            selectedIndex = 0;
            historyStack.length = 0;
            if (!applyOpacity(0.4)) return 'nao aplicou na selecao';
            if (Math.abs(annotations[0].opacity - 0.4) > 1e-6) return 'opacidade';
            if (!applyAngle(90)) return 'nao girou a selecao';
            if (annotations[0].angle !== 90) return 'angulo: ' + annotations[0].angle;
            // Relativo soma ao que ja esta.
            applyAngle(90, true);
            if (annotations[0].angle !== 180) return 'relativo: ' + annotations[0].angle;
            applyAngle(-360, true);
            if (annotations[0].angle !== 180) return 'volta inteira mudou o angulo';
            if (historyStack.length !== 4) return 'desfazer: ' + historyStack.length;
            // Sem selecao e sem captura por perto (guia Edicao), os valores
            // ficam guardados e nascem na proxima marcacao.
            const modoAntes = workspaceMode;
            workspaceMode = 'edition';
            selectedIndex = -1;
            selectedEditionItemIndex = -1;
            applyOpacity(0.6);
            applyAngle(45);
            const opcoes = getOptions();
            workspaceMode = modoAntes;
            if (Math.abs(opcoes.opacity - 0.6) > 1e-6) return 'guardado: ' + opcoes.opacity;
            return opcoes.angle === 45 ? true : 'angulo guardado: ' + opcoes.angle;
        })() === true""")
        check("""(() => {
            // As duas ferramentas selecionam, como o Mover, e trocar entre elas
            // nao perde o que esta selecionado.
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: 100, y: 100, w: 120, h: 80, color: '#000', thick: 4});
            selectTool('Mover', false);
            selectedIndex = 0;
            const botao = t => document.querySelector(
                ".ribbon-content.active .tool-btn[data-tool='" + t + "']");
            botao('Transparencia').click();
            if (currentTool !== 'Transparencia') return 'nao trocou de ferramenta';
            if (selectedIndex !== 0) return 'perdeu a selecao ao ir para a Transparencia';
            botao('Rotacionar').click();
            if (currentTool !== 'Rotacionar' || selectedIndex !== 0) return 'perdeu ao ir para o Rotacionar';
            // Ir para uma ferramenta de desenho limpa, como sempre foi.
            botao('Retangulo').click();
            if (selectedIndex !== -1) return 'o Retangulo manteve a selecao';
            selectTool('Mover', false);
            annotations.length = 0;
            return true;
        })() === true""")
        # O menu flutuante das duas, com a barra e os botoes de um quarto de volta.
        check("""(() => {
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: 100, y: 100, w: 120, h: 80, color: '#000', thick: 4});
            selectTool('Mover', false);
            selectedIndex = 0;
            abrirMenuDaFerramenta('Transparencia');
            const popover = byId('tool-config-popover');
            if (popover.hidden) return 'menu da transparencia nao abriu';
            if (selectedIndex !== 0) return 'abrir o menu perdeu a selecao';
            const barra = popover.querySelector('.config-range');
            if (!barra) return 'sem barra';
            barra.value = 60;
            barra.dispatchEvent(new Event('input'));
            if (Math.abs(annotations[0].opacity - 0.4) > 1e-6) return 'a barra nao aplicou';

            abrirMenuDaFerramenta('Rotacionar');
            const direita = popover.querySelector("[data-girar='90']");
            if (!direita) return 'sem o botao de um quarto de volta';
            direita.click();
            if (annotations[0].angle !== 90) return 'quarto de volta: ' + annotations[0].angle;
            direita.click();
            if (annotations[0].angle !== 180) return 'segundo quarto: ' + annotations[0].angle;
            const campo = popover.querySelector('.config-angulo');
            campo.value = 30;
            campo.dispatchEvent(new Event('input'));
            if (annotations[0].angle !== 30) return 'campo de angulo: ' + annotations[0].angle;
            closeFormatPopover();
            annotations.length = 0;
            selectedIndex = -1;
            return true;
        })() === true""")
        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); redraw()")
        # --- na Pagina Inicial os ajustes caem na propria captura ---
        js("annotations.length = 0; selectedIndex = -1; selectTool('Mover', false); fitToWorkspace()")
        QTest.qWait(200)
        check("""(() => {
            if (workspaceMode !== 'home' || !bgImage) return 'sem captura para testar';
            const larguraAntes = docWidth, alturaAntes = docHeight;
            annotations.length = 0;
            selectedIndex = -1;
            historyStack.length = 0; redoStack.length = 0;

            // Sem selecao, o alvo e a imagem - e o menu diz isso.
            if (!backgroundIsTarget()) return 'a captura nao virou alvo';
            if (!alvoDoAjuste().includes('imagem capturada')) return 'o aviso nao mudou';
            if (Math.abs(currentOpacity() - 1) > 1e-6) return 'comecou apagada';

            // Transparencia: vai para a imagem, nao para a proxima marcacao.
            if (!applyOpacity(0.4)) return 'nao aplicou na imagem';
            if (Math.abs(bgOpacity - 0.4) > 1e-6) return 'bgOpacity: ' + bgOpacity;
            if (Math.abs(getOptions().opacity - 0.4) < 1e-6) return 'foi parar na proxima marcacao';

            // E some da imagem exportada tambem, nao so da tela. A captura da
            // suite e branca, e branco apagado sobre branco continua branco:
            // por isso o teste troca por uma imagem com cor antes de comparar.
            const imagemAntes = bgImage;
            const pintada = document.createElement('canvas');
            pintada.width = docWidth; pintada.height = docHeight;
            const pincel = pintada.getContext('2d');
            pincel.fillStyle = '#003366';
            pincel.fillRect(0, 0, docWidth, docHeight);
            bgImage = pintada;
            bgProxySource = null;
            const clarinho = exportDataUrl('image/png');
            bgOpacity = 1;
            const cheio = exportDataUrl('image/png');
            bgImage = imagemAntes;
            bgProxySource = null;
            if (clarinho === cheio) return 'a exportacao ignorou a transparencia';
            bgOpacity = 0.4;

            // Giro: so de 90 em 90.
            if (applyAngle(45)) return 'aceitou 45 graus na imagem';
            if (docWidth !== larguraAntes) return 'girou mesmo recusando';
            // Uma marcacao junto, para conferir que ela vira com a imagem.
            annotations.push({type: 'Retangulo', x: 20, y: 20, w: 100, h: 60,
                              color: '#000', thick: 4});
            const centroAntes = shapeCenter(annotations[0]);
            if (!applyAngle(90)) return 'nao girou a imagem';
            if (docWidth !== alturaAntes || docHeight !== larguraAntes) {
                return 'a folha nao trocou de lados: ' + docWidth + 'x' + docHeight;
            }
            // Um quarto de volta a direita leva (x, y) para (H - y, x).
            const centroDepois = shapeCenter(annotations[0]);
            if (Math.abs(centroDepois.x - (alturaAntes - centroAntes.y)) > 1) {
                return 'a marcacao nao acompanhou em x: ' + centroDepois.x;
            }
            if (Math.abs(centroDepois.y - centroAntes.x) > 1) {
                return 'a marcacao nao acompanhou em y: ' + centroDepois.y;
            }
            if (shapeAngle(annotations[0]) !== 90) return 'a marcacao nao girou junto';
            // A transparencia escolhida sobrevive ao giro.
            if (Math.abs(bgOpacity - 0.4) > 1e-6) return 'o giro zerou a transparencia';

            // Desfazer devolve tudo: lados da folha, marcacao e transparencia.
            undoAnnotation();
            if (docWidth !== larguraAntes || docHeight !== alturaAntes) return 'desfazer nao voltou a folha';
            undoAnnotation();
            if (Math.abs(bgOpacity - 1) > 1e-6) return 'desfazer nao voltou a transparencia';

            bgOpacity = 1;
            annotations.length = 0;
            fitToWorkspace();
            return true;
        })() === true""")
        # O menu de girar esconde o campo de angulo livre quando o alvo e a imagem.
        check("""(() => {
            annotations.length = 0;
            selectedIndex = -1;
            selectTool('Mover', false);
            abrirMenuDaFerramenta('Rotacionar');
            const popover = byId('tool-config-popover');
            const semCampo = !popover.querySelector('.config-angulo');
            const temQuartos = popover.querySelectorAll("[data-girar='90']").length === 1;
            // Com uma marcacao selecionada o campo volta.
            annotations.push({type: 'Retangulo', x: 100, y: 100, w: 80, h: 60, color: '#000', thick: 4});
            selectedIndex = 0;
            renderToolConfigMenu(popover, 'Rotacionar');
            const comCampo = Boolean(popover.querySelector('.config-angulo'));
            closeFormatPopover();
            annotations.length = 0;
            selectedIndex = -1;
            if (!semCampo) return 'o campo de angulo livre ficou na imagem';
            if (!temQuartos) return 'faltaram os quartos de volta';
            return comCampo ? true : 'o campo nao voltou com a marcacao selecionada';
        })() === true""")
        # E o botao direito no vazio alcanca a captura.
        check("""(() => {
            annotations.length = 0;
            selectedIndex = -1;
            showBackgroundMenu(200, 200);
            const itens = [...document.querySelectorAll('.image-menu button')].map(b => b.textContent.trim());
            closeEditionImageMenu();
            return itens.length === 3
                && itens[0].includes('Transparência da imagem')
                && itens[1].includes('esquerda') && itens[2].includes('direita');
        })()""")
        print("OK: na Pagina Inicial a captura recebe transparencia e gira de 90 em 90")

        print("OK: transparencia e giro no desenho, no clique, no menu e na selecao")

        # --- a imagem da Edicao gira e fica transparente do mesmo jeito ---
        check("""(() => {
            const modoAntes = workspaceMode, itensAntes = editionItems;
            const larguraAntes = docWidth, alturaAntes = docHeight;
            try {
                workspaceMode = 'edition';
                docWidth = 1600; docHeight = 1000;
                editionItems = [{x: 200, y: 300, w: 400, h: 200, image: imagemDeTeste}];
                const item = editionItems[0];
                selectedEditionItemIndex = 0;
                selectedIndex = -1;
                // O menu enxerga a imagem como alvo.
                if (selectedElement() !== item) return 'alvo errado';
                applyAngle(90);
                if (item.angle !== 90) return 'nao girou';
                // Girada, ela responde onde aparece: a caixa no mundo fica em pe.
                const caixa = rotatedBounds(itemAsShape(item));
                if (Math.abs(caixa.w - 200) > 1 || Math.abs(caixa.h - 400) > 1) {
                    return 'caixa girada: ' + JSON.stringify(caixa);
                }
                // Um ponto que so pertence a ela depois de girada.
                const centro = {x: item.x + item.w / 2, y: item.y + item.h / 2};
                if (findEditionItemAt(centro.x, centro.y + 150).index !== 0) return 'nao pegou em pe';
                if (findEditionItemAt(centro.x + 150, centro.y).index === 0) return 'pegou onde nao devia';
                applyOpacity(0.5);
                return Math.abs(item.opacity - 0.5) < 1e-6;
            } finally {
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                selectedEditionItemIndex = -1;
                docWidth = larguraAntes; docHeight = alturaAntes;
            }
        })() === true""")
        print("OK: imagem da Edicao gira, responde onde aparece e aceita transparencia")

        # --- menu do botao direito na marcacao ---
        check("""(() => {
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: 100, y: 100, w: 120, h: 80, color: '#000', thick: 4});
            showAnnotationMenu(0, 150, 150);
            const itens = [...document.querySelectorAll('.image-menu button')].map(b => b.textContent.trim());
            closeEditionImageMenu();
            annotations.length = 0;
            return itens.length === 3
                && itens[0].includes('Transparência')
                && itens[1].includes('Rotacionar')
                && itens[2].includes('Remover marcação');
        })()""")
        print("OK: botao direito na marcacao abre Transparencia, Rotacionar e Remover")

        # --- os menus flutuantes: sem selecao de texto e arrastaveis ---
        check("""(() => {
            annotations.length = 0;
            annotations.push({type: 'Retangulo', x: 100, y: 100, w: 120, h: 80, color: '#000', thick: 4});
            selectTool('Mover', false);
            selectedIndex = 0;
            abrirMenuDaFerramenta('Transparencia');
            const popover = byId('tool-config-popover');
            if (popover.hidden) return 'nao abriu';

            // 1) Titulo e rotulos nao sao conteudo: arrastar por cima nao deixa
            // o texto azul. Os campos continuam selecionaveis - a regra de
            // input/textarea tem !important e vence a do menu.
            const estilo = alvo => getComputedStyle(alvo).userSelect
                || getComputedStyle(alvo).webkitUserSelect;
            if (estilo(popover) !== 'none') return 'menu selecionavel: ' + estilo(popover);
            if (estilo(popover.querySelector('.picker-heading')) !== 'none') return 'titulo selecionavel';
            const campo = byId('cfg-espessura');
            if (estilo(campo) !== 'text') return 'campo da faixa deixou de ser selecionavel';

            // 2) O titulo e a alca: o menu anda com o mouse e NAO fecha.
            const titulo = popover.querySelector('.picker-heading');
            const antes = popover.getBoundingClientRect();
            const soltar = (tipo, x, y) => titulo.dispatchEvent(
                new MouseEvent(tipo, {clientX: x, clientY: y, bubbles: true, cancelable: true}));
            titulo.dispatchEvent(new MouseEvent('mousedown',
                {clientX: antes.left + 20, clientY: antes.top + 10, bubbles: true, cancelable: true}));
            window.dispatchEvent(new MouseEvent('mousemove',
                {clientX: antes.left + 20 + 140, clientY: antes.top + 10 + 90, bubbles: true}));
            window.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            const depois = popover.getBoundingClientRect();
            if (popover.hidden) return 'fechou ao arrastar';
            if (Math.abs(depois.left - (antes.left + 140)) > 2) return 'nao andou em x: ' + depois.left;
            if (Math.abs(depois.top - (antes.top + 90)) > 2) return 'nao andou em y: ' + depois.top;

            // 3) Mexer nos campos nao devolve o menu para junto do botao.
            const barra = popover.querySelector('.config-range');
            barra.value = 30;
            barra.dispatchEvent(new Event('input'));
            renderToolConfigMenu(popover, 'Transparencia');
            positionFormatPopover();
            const aindaLa = popover.getBoundingClientRect();
            if (Math.abs(aindaLa.left - depois.left) > 2) return 'voltou para o botao';

            // 4) Nem o menu sai da janela, por mais longe que se arraste.
            titulo.dispatchEvent(new MouseEvent('mousedown',
                {clientX: aindaLa.left + 20, clientY: aindaLa.top + 10, bubbles: true, cancelable: true}));
            window.dispatchEvent(new MouseEvent('mousemove',
                {clientX: innerWidth + 500, clientY: innerHeight + 500, bubbles: true}));
            window.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
            const preso = popover.getBoundingClientRect();
            if (preso.right > innerWidth - 10 || preso.bottom > innerHeight - 10) {
                return 'saiu da janela: ' + JSON.stringify(preso);
            }

            // 5) Fechar e reabrir devolve o menu para junto do botao.
            closeFormatPopover();
            abrirMenuDaFerramenta('Transparencia');
            // A transparencia e o giro nao tem setinha: o proprio botao e a
            // ancora do menu.
            const gatilho = document.querySelector(
                ".ribbon-content.active .tool-btn[data-tool='Transparencia']");
            if (document.querySelector(".stroke-menu-trigger[data-tool='Transparencia']")) {
                return 'a transparencia ainda tem setinha';
            }
            const novo = popover.getBoundingClientRect();
            if (Math.abs(novo.left - gatilho.getBoundingClientRect().left) > 14) {
                return 'nao voltou para o botao ao reabrir';
            }
            closeFormatPopover();
            annotations.length = 0;
            selectedIndex = -1;
            return true;
        })() === true""")
        print("OK: menu flutuante sem selecao de texto, arrastavel pelo titulo e preso a janela")

        # --- giro e transparencia sobrevivem a copiar, colar, salvar ---
        check("""(() => {
            annotations.length = 0;
            selectedIndex = -1;
            selectTool('Mover', false);
            annotations.push({type: 'Retangulo', x: 120, y: 120, w: 160, h: 100,
                              color: '#C00000', thick: 8, angle: 40, opacity: 0.45});

            // Ctrl+C / Ctrl+V: a copia nasce com o mesmo giro e a mesma
            // transparencia, so deslocada.
            selectedIndex = 0;
            if (!copySelectedElement()) return 'nao copiou';
            if (!pasteCopiedElement()) return 'nao colou';
            const copia = annotations[1];
            if (!copia) return 'a copia nao entrou';
            if (copia.angle !== 40) return 'giro perdido ao colar: ' + copia.angle;
            if (Math.abs(copia.opacity - 0.45) > 1e-6) return 'transparencia perdida: ' + copia.opacity;
            if (copia.x === annotations[0].x && copia.y === annotations[0].y) return 'colou em cima';
            // Colar de novo nao reaproveita o mesmo objeto.
            pasteCopiedElement();
            if (annotations[2] === annotations[1]) return 'as copias compartilham o objeto';
            annotations.length = 1;

            // Desfazer/refazer guardam os dois campos.
            historyStack.length = 0; redoStack.length = 0;
            pushHistory();
            annotations[0].angle = 0;
            annotations[0].opacity = 1;
            undoAnnotation();
            if (annotations[0].angle !== 40) return 'desfazer perdeu o giro';
            if (Math.abs(annotations[0].opacity - 0.45) > 1e-6) return 'desfazer perdeu a transparencia';

            // A imagem salva sai com os dois aplicados: girar e apagar mudam o
            // que e exportado, nao so o que aparece na tela.
            selectedIndex = -1;
            const comEfeito = exportDataUrl('image/png');
            const guardado = {angle: annotations[0].angle, opacity: annotations[0].opacity};
            annotations[0].angle = 0;
            annotations[0].opacity = 1;
            const semEfeito = exportDataUrl('image/png');
            annotations[0].angle = guardado.angle;
            annotations[0].opacity = guardado.opacity;
            if (comEfeito === semEfeito) return 'a imagem salva ignorou giro e transparencia';

            // E o mesmo para uma imagem da guia Edicao.
            const modoAntes = workspaceMode, itensAntes = editionItems;
            const larguraAntes = docWidth, alturaAntes = docHeight;
            const anotacoesAntes = annotations;
            try {
                workspaceMode = 'edition';
                docWidth = 1200; docHeight = 800;
                annotations = [];
                editionItems = [{x: 100, y: 100, w: 300, h: 200, image: imagemDeTeste,
                                 angle: 90, opacity: 0.5}];
                selectedEditionItemIndex = 0;
                selectedIndex = -1;
                if (!copySelectedElement()) return 'nao copiou a imagem';
                if (!pasteCopiedElement()) return 'nao colou a imagem';
                const foto = editionItems[1];
                if (!foto) return 'a foto colada nao entrou';
                if (foto.angle !== 90) return 'giro perdido na foto: ' + foto.angle;
                if (Math.abs(foto.opacity - 0.5) > 1e-6) return 'transparencia perdida na foto';
                if (foto.image !== imagemDeTeste) return 'a foto colada perdeu a imagem';

                selectedEditionItemIndex = -1;
                const fotoComEfeito = exportDataUrl('image/png');
                editionItems.forEach(item => { item.angle = 0; item.opacity = 1; });
                const fotoSemEfeito = exportDataUrl('image/png');
                return fotoComEfeito === fotoSemEfeito
                    ? 'a imagem salva da Edicao ignorou giro e transparencia' : true;
            } finally {
                workspaceMode = modoAntes;
                editionItems = itensAntes;
                annotations = anotacoesAntes;
                annotations.length = 0;
                selectedEditionItemIndex = -1;
                selectedIndex = -1;
                elementClipboard = null;
                docWidth = larguraAntes; docHeight = alturaAntes;
                fitToWorkspace();
            }
        })() === true""")
        print("OK: giro e transparencia sobrevivem a copiar, colar, desfazer e salvar")

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

        # --- as tres linhas da Formatacao terminam na mesma vertical ---
        check("""(() => {
            const conferir = prefixo => {
                const faixa = byId(prefixo + 'btn-align-left').closest('.ribbon-content');
                const ativa = faixa.classList.contains('active');
                faixa.classList.add('active');
                const fim = id => byId(prefixo + id).getBoundingClientRect().right;
                const topo = id => byId(prefixo + id).getBoundingClientRect().top;
                const resultado =
                    // Alinhar fica entre Estilo e Cor / Esp.
                    topo('btn-underline') < topo('btn-align-left')
                    && topo('btn-align-left') < topo('cfg-espessura')
                    // e as tres linhas acabam na mesma vertical.
                    && Math.abs(fim('btn-underline') - fim('btn-align-right')) <= 0.5
                    && Math.abs(fim('btn-underline') - fim('cfg-espessura')) <= 0.5;
                if (!ativa) faixa.classList.remove('active');
                return resultado;
            };
            return conferir('') && conferir('ed-');
        })()""")
        print("OK: Alinhar entre Estilo e Cor / Esp., com as tres linhas alinhadas a direita")

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
        # E nem vertical: a grade das ferramentas cresce em linhas, entao um
        # botao novo empurra para baixo em vez de para o lado.
        alto = js("""(() => {
            const faltando = [];
            document.querySelectorAll('.ribbon-content').forEach(element => {
                const ativa = element.classList.contains('active');
                element.classList.add('active');
                if (element.scrollHeight > element.clientHeight + 1) {
                    faltando.push(element.id + ' precisa de ' + element.scrollHeight + 'px de altura');
                }
                if (!ativa) element.classList.remove('active');
            });
            return faltando.join('; ');
        })()""")
        assert alto == "", f"faixa cortada na altura: {alto}"
        print(f"OK: nenhuma guia precisa de rolagem em {capture.RIBBON_MIN_WIDTH}px, nem na largura nem na altura")

        js("annotations.length = 0; selectedIndex = -1; clearStroke(); redraw()")
        print("VALIDACAO DAS FERRAMENTAS CONCLUIDA")
    finally:
        window.close()
        window.deleteLater()
        application.processEvents()
        temporary.cleanup()


if __name__ == "__main__":
    main()
