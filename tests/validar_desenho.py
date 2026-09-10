"""Validate drawing and Office-style palettes in the real Qt renderer, isolated."""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app as capture
import atualizador_ui
from atualizador import APP_FILES
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def main():
    application = QApplication.instance() or QApplication([])
    temporary = tempfile.TemporaryDirectory(prefix="super-captura-drawing-")
    folder = Path(temporary.name)
    for name in APP_FILES:
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    capture.BASE_DIR = folder
    capture.HTML_PATH = folder / "NOVA INTERFACE INTERFACE - SUPER CAPRURA.html"
    capture.SETTINGS_PATH = folder / "configuracoes.json"
    capture.DEFAULT_IMAGE_DIR = folder / "capturas"
    capture.DEFAULT_VIDEO_DIR = folder / "videos"
    capture.MainWindow._install_printscreen_hook = lambda self: None
    atualizador_ui.check_release = lambda info: None
    window = capture.MainWindow()
    window.show()

    def wait(predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            application.processEvents()
            if predicate():
                return
            time.sleep(.01)
        raise AssertionError("Interface did not reach expected state")

    def js(source):
        results = []
        window.web.page().runJavaScript(source, results.append)
        wait(lambda: bool(results))
        return results[0]

    def check(source):
        assert js(source), source

    def screenshot(name):
        QTest.qWait(180)
        output = ROOT / "dist" / name
        output.parent.mkdir(exist_ok=True)
        assert window.grab().save(str(output))

    try:
        wait(lambda: js("typeof pyBridge !== 'undefined' && Boolean(pyBridge)"))
        js("""
            scheduleClipboardSync = () => {};
            syncClipboardNow = () => {};
            window.sample = document.createElement('canvas');
            sample.width = 1000; sample.height = 600;
            const c = sample.getContext('2d');
            c.fillStyle = '#ffffff'; c.fillRect(0,0,1000,600);
            loadImageData(sample.toDataURL(), false, false);
        """)
        wait(lambda: js("Boolean(bgImage && bgImage.naturalWidth === 1000)"))
        QTest.qWait(400)
        js("document.querySelector('[data-color-picker]').click()")
        check("!byId('drawing-color-popover').hidden && document.querySelectorAll('input[type=color]').length === 0")
        check("byId('drawing-color-popover').getBoundingClientRect().right <= innerWidth")
        screenshot("validacao-cores-office.png")
        js("document.querySelector('[data-palette=standard] button:nth-child(2)').click()")
        check("getOptions().color === '#FF0000' && byId('ed-cfg-cor').value === '#FF0000'")
        js("document.querySelector('[data-color-picker]').click(); document.querySelector('.picker-custom').open = true; byId('custom-color-hex').value = '#nope'; byId('apply-custom-color').click()")
        screenshot("validacao-cores-personalizadas.png")
        check("byId('custom-color-error').textContent.length > 0 && getOptions().color === '#FF0000'")
        js("byId('custom-color-hex').value = '#2456ab'; byId('apply-custom-color').click()")
        check("getOptions().color === '#2456AB' && recentColors[0] === '#2456AB'")
        js("document.querySelector('[data-color-picker]').click(); window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
        check("byId('drawing-color-popover').hidden")
        print("OK: theme, standard, custom colors, validation, recent colors, Escape")

        js("document.querySelector('.stroke-menu-trigger').click()")
        check("currentTool === 'Caneta' && !byId('stroke-width-popover').hidden")
        js("document.querySelector('.stroke-choice[aria-label=\"6 pixels\"]').click()")
        check("getOptions().thick === 6")
        # Native Qt input verifies mouse -> pointermove routing in Chromium.
        geometry = json.loads(js("JSON.stringify(canvas.getBoundingClientRect().toJSON())"))
        points = [QPoint(round(geometry['x'] + 100 + i * 10), round(geometry['y'] + 100 + (i % 3) * 5)) for i in range(24)]
        target = window.web.focusProxy() or window.web
        QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=points[0])
        for point in points[1:]:
            QTest.mouseMove(target, point, delay=3)
        QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=points[-1])
        wait(lambda: js("annotations.length === 1"))
        check("annotations[0].points.length > 4 && annotations[0].thick === 6")
        check("annotations[0].points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y))")
        print("OK: real Qt mouse stroke, smooth drawing points and width")

        js("selectTool('MarcaTexto'); document.querySelectorAll('.stroke-menu-trigger')[1].click()")
        screenshot("validacao-espessura.png")
        js("document.querySelector('.stroke-choice[aria-label=\"24 pixels\"]').click(); selectTool('Caneta')")
        check("getOptions().thick === 6")
        js("selectTool('MarcaTexto')")
        check("getOptions().thick === 6 && byId('cfg-espessura').value === '24'")
        # Validate visible width and opacity of exported geometry, including dots.
        check("""(() => {
            const surface = document.createElement('canvas'); surface.width=200; surface.height=150;
            const c=surface.getContext('2d');
            drawShape(c,{type:'MarcaTexto',points:[{x:30,y:60},{x:80,y:60},{x:160,y:60}],color:'#ff0000',thick:6});
            const pixel=y=>c.getImageData(80,y,1,1).data[3];
            return pixel(60)>90 && pixel(60)<105 && pixel(49)>90 && pixel(46)===0;
        })()""")
        js("selectTool('Mover'); selectedIndex=0; syncFormatControlsFromSelection(annotations[0]); byId('cfg-espessura').value=3; handleFormatControlChanged()")
        check("annotations[0].thick === 3")
        js("undoAnnotation()")
        check("annotations[0].thick === 6")
        print("OK: independent tool widths, highlighter opacity and actual pixel width, edit and undo")

        # Verify smooth curve exports differ from the old jagged polyline.
        check("""(() => {
            const surface=document.createElement('canvas'); surface.width=160;surface.height=160;
            const c=surface.getContext('2d');
            drawShape(c,{type:'Caneta',color:'#000000',thick:4,points:[{x:20,y:120},{x:80,y:20},{x:140,y:120}]});
            return c.getImageData(80,20,1,1).data[3]===0 && c.getImageData(20,120,1,1).data[3]>0 && c.getImageData(140,120,1,1).data[3]>0;
        })()""")
        js("document.querySelector('.ribbon-tab[onclick*=tab-edicao]').click()")
        check("workspaceMode === 'edition'")
        check("document.querySelectorAll('.stroke-menu-trigger').length === 4")
        js("document.querySelectorAll('[data-color-picker]')[1].click()")
        check("!byId('drawing-color-popover').hidden")
        for width, height in ((1100, 720), (1600, 900)):
            window.resize(width, height)
            QTest.qWait(120)
            js("document.querySelectorAll('[data-color-picker]')[1].scrollIntoView(); document.querySelectorAll('[data-color-picker]')[1].click()")
            check("byId('drawing-color-popover').getBoundingClientRect().right <= innerWidth && byId('drawing-color-popover').getBoundingClientRect().bottom <= innerHeight")
            screenshot(f"validacao-cores-edicao-{width}.png")
            js("closeFormatPopover()")
        js("setDrawingColor('#107C41'); persistPreferences()")
        QTest.qWait(650)
        saved = json.loads((folder / "configuracoes.json").read_text(encoding="utf-8"))
        assert saved['pen_thickness'] == 3 and saved['highlighter_thickness'] == 24, saved
        assert '#107C41' in saved['recent_colors']
        screenshot("validacao-desenho.png")
        print("OK: curve endpoints, edition palette and saved preferences")
    finally:
        window.close()
        window.deleteLater()
        application.processEvents()
        temporary.cleanup()


if __name__ == '__main__':
    main()
