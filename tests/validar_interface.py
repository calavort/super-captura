"""Exercise the actual Qt/WebChannel UI in an isolated copy, without user data."""

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
from atualizador import APP_FILES, AppInstance, Release, read_version, version_tuple
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


def main():
    application = QApplication.instance() or QApplication([])
    temporary = tempfile.TemporaryDirectory(prefix="super-captura-ui-")
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
    checks = []

    def initial_check(info):
        checks.append(info["version"])
        time.sleep(0.25)
        return None

    atualizador_ui.check_release = initial_check
    window = capture.MainWindow()
    window.show()

    def wait_until(predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            application.processEvents()
            if predicate():
                return
            time.sleep(0.01)
        raise AssertionError("Timeout aguardando a interface")

    def javascript(source):
        result = []
        window.web.page().runJavaScript(source, result.append)
        wait_until(lambda: bool(result))
        return result[0]

    def until_javascript(source):
        wait_until(lambda: bool(javascript(source)))

    try:
        until_javascript("typeof pyBridge !== 'undefined' && pyBridge !== null")
        wait_until(lambda: checks and not window.updater.busy)
        version = read_version(folder)["version"]
        assert javascript("document.getElementById('update-version').textContent") == "Versao " + version
        assert javascript("document.getElementById('update-status').textContent") == "Voce esta na versao mais recente."
        print("OK: verificacao automatica ao abrir e conexao WebChannel")

        ticks = []
        timer = QTimer()
        timer.setInterval(25)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        javascript("document.getElementById('btn-check-update').click()")
        wait_until(lambda: len(checks) >= 2 and not window.updater.busy)
        timer.stop()
        assert len(ticks) >= 4, ticks
        print("OK: botao Verificar e interface responsiva durante consulta")

        major, minor, patch = version_tuple(version)
        next_release = Release(f"{major}.{minor}.{patch + 1}", "calavort/super-captura", "", "0" * 64, 1)
        atualizador_ui.check_release = lambda info: next_release
        window.updater.check(False)
        wait_until(lambda: window.updater.dialog is not None)
        dialog = window.updater.dialog
        later = next(button for button in dialog.buttons() if button.text() == "Agora nao")
        QTest.mouseClick(later, Qt.MouseButton.LeftButton)
        wait_until(lambda: window.updater.dialog is None)
        assert not window.updater.installing and window.updater.archive is None
        assert not javascript("document.getElementById('btn-install-update').disabled")
        print("OK: aviso automatico, adiar atualizacao e botao Atualizar")

        window.bridge.video_recording = True
        window.updater.offer_install()
        assert window.updater.dialog is None
        assert "gravacao" in window.updater.message
        window.updater._begin_install()
        assert not window.updater.installing
        window.bridge.video_recording = False
        print("OK: instalacao bloqueada durante gravacao")

        first = AppInstance(folder)
        second = AppInstance(folder)
        assert first.acquire() and second.acquire()
        window.app_instance = first
        try:
            window.updater._begin_install()
            assert not window.updater.installing and window.isEnabled()
            assert "outras janelas" in window.updater.message
            assert not (folder / ".atualizacoes" / "sessao.json").exists()
        finally:
            first.release()
            second.release()
            window.app_instance = None
        print("OK: atualizacao pede fechar outras janelas sem encerrar trabalhos")

        # Synthetic images exercise preservation without touching the OS clipboard.
        javascript("""
            scheduleClipboardSync = () => {};
            syncClipboardNow = () => {};
            window.testBuffer = document.createElement('canvas');
            testBuffer.width = 120; testBuffer.height = 80;
            window.testContext = testBuffer.getContext('2d');
            testContext.fillStyle = '#28a745'; testContext.fillRect(0, 0, 120, 80);
            testContext.fillStyle = '#d62040'; testContext.fillRect(0, 0, 60, 80);
            window.testImage = testBuffer.toDataURL('image/png');
            loadImageData(testImage, false, false);
        """)
        until_javascript("Boolean(bgImage && bgImage.naturalWidth === 120)")
        javascript("""
            annotations.push({type:'Texto', x:4, y:4, w:90, h:28, text:'Teste salvo', font:12, color:'#ffffff'});
            addEditionImage(testImage, 'Imagem de teste');
        """)
        until_javascript("editionItems.length === 1 && editionItems[0].image.complete")
        javascript("annotations.push({type:'Retangulo', x:5,y:5,w:30,h:20,color:'#123456',thick:2})")
        payload = javascript("serializeUpdateSession()")
        session = json.loads(payload)
        assert len(session["homeAnnotations"]) == 1
        assert len(session["editionAnnotations"]) == 1
        assert session["bgImage"].startswith("data:image/png;base64,")
        assert session["editionItems"][0]["source"].startswith("data:image/png;base64,")
        javascript("editionItems=[]; annotations=[]; homeAnnotations=[]; homeBgImage=null; bgImage=null")
        javascript("restoreUpdateSession(" + payload + ")")
        until_javascript("editionItems.length === 1 && homeBgImage !== null && homeAnnotations.length === 1")
        assert javascript("homeAnnotations[0].text") == "Teste salvo"
        assert javascript("editionItems[0].image.naturalWidth") == 120
        assert javascript("editionAnnotations.length") == 1
        print("OK: imagens e anotacoes das duas guias preservadas e recuperadas")

        (folder / ".git").mkdir()
        window.updater._begin_install()
        assert not window.updater.installing and "desenvolvimento" in window.updater.message
        print("OK: pasta de desenvolvimento protegida")

        javascript("document.querySelector(\".ribbon-tab[onclick*=\" + '\"tab-config\"' + \"]\").click()")
        window.updater._status("Versao 7.1.1 disponivel.")
        wait_until(lambda: javascript("document.getElementById('tab-config').classList.contains('active')"))
        for width, height in ((1240, 720), (1600, 900)):
            window.resize(width, height)
            QTest.qWait(350)
            geometry = json.loads(javascript("""JSON.stringify(['btn-check-update','btn-install-update','update-status'].map(id => {
                const e=document.getElementById(id),r=e.getBoundingClientRect();
                return {id,x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};
            }))"""))
            assert all(item["width"] > 0 and item["height"] > 0 and item["right"] < width for item in geometry)
            assert geometry[0]["right"] <= geometry[1]["x"]
            image = window.grab().toImage()
            samples = {image.pixelColor(x, y).name() for x in range(10, image.width(), 50) for y in range(10, image.height(), 40)}
            assert len(samples) > 5, samples
            output = ROOT / "dist" / f"validacao-interface-{width}.png"
            output.parent.mkdir(exist_ok=True)
            assert image.save(str(output))
            print("OK: interface renderizada", width, height, "cores:", len(samples))
        print("VALIDACAO DA INTERFACE CONCLUIDA")
    finally:
        window.bridge.video_recording = False
        window.close()
        window.deleteLater()
        application.processEvents()
        temporary.cleanup()


if __name__ == "__main__":
    main()
