"""Nonblocking Qt integration for the Super Captura updater."""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from atualizador import (UpdateError, check_release, download_release, prepare_installer,
                         read_version, start_installer, state_path, unpack_package, write_json)


class UpdateController(QObject):
    completed = Signal(str, object)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(self, window, root: Path):
        super().__init__(window)
        self.window = window
        self.root = root
        self.info = read_version(root)
        self.release = None
        self.archive = None
        self.busy = False
        self.installing = False
        self.started = False
        self.dialog = None
        self.message = "Aguardando verificacao."
        self.manual = False
        self.helper = None
        self._handshake_attempts = 0
        self.handshake_timer = QTimer(self)
        self.handshake_timer.setInterval(100)
        self.handshake_timer.timeout.connect(self._check_handshake)
        self.completed.connect(self._completed)
        self.failed.connect(self._failed)
        self.progress.connect(self._progress)

    def ui_ready(self):
        self._status(self.message)
        if self.started:
            return
        self.started = True
        self._restore_session()
        result = state_path(self.root) / "resultado.json"
        if result.exists():
            try:
                data = json.loads(result.read_text(encoding="utf-8"))
                self.window.bridge._emit_status(data["message"])
                result.replace(result.with_name("ultimo-resultado.json"))
            except (OSError, ValueError, KeyError):
                pass
        QTimer.singleShot(1800, lambda: self.check(False))

    def _status(self, message):
        self.message = message
        payload = {"version": self.info["version"], "message": message,
                   "busy": self.busy, "available": self.release is not None}
        self.window.web.page().runJavaScript(
            "if (typeof updateReleaseState === 'function') updateReleaseState("
            + json.dumps(payload) + ");"
        )

    def _worker(self, operation, callback):
        self.busy = True

        def run():
            try:
                value = callback()
                self.completed.emit(operation, value)
            except Exception as exc:
                try:
                    self.failed.emit(str(exc))
                except RuntimeError:
                    pass  # The user closed the window during a network request.

        threading.Thread(target=run, name="SuperCaptura-" + operation, daemon=True).start()

    def check(self, manual=True):
        if self.busy or self.installing:
            return
        self.manual = manual
        self._worker("check", lambda: check_release(self.info))
        self._status("Verificando atualizacoes...")

    def _capture_active(self):
        bridge = self.window.bridge
        return bool(bridge.video_recording or bridge.capture_pending() or bridge._pending_capture
                    or bridge.media_recorder is not None)

    def offer_install(self):
        if not self.release or self.busy or self.dialog:
            return
        if self._capture_active() or not self.window.isVisible():
            self._status("Atualizacao disponivel. Conclua a captura ou gravacao para instalar.")
            return
        self.dialog = QMessageBox(self.window)
        self.dialog.setWindowTitle("Atualizacao do Super Captura")
        self.dialog.setIcon(QMessageBox.Icon.Information)
        self.dialog.setText(f"A versao {self.release.version} esta disponivel.")
        self.dialog.setInformativeText("Baixar a atualizacao agora? Voce confirma a reinicializacao depois do download.")
        download = self.dialog.addButton("Baixar atualizacao", QMessageBox.ButtonRole.AcceptRole)
        later = self.dialog.addButton("Agora nao", QMessageBox.ButtonRole.RejectRole)
        self.dialog.setDefaultButton(later)

        def answered():
            accepted = self.dialog.clickedButton() == download
            self.dialog.deleteLater()
            self.dialog = None
            if accepted:
                self._download()

        self.dialog.finished.connect(answered)
        self.dialog.open()

    def _download(self):
        if self.archive and self.archive.exists():
            self._confirm_restart()
            return
        release = self.release

        def work():
            archive = download_release(release, self.root, self.progress.emit)
            try:
                with tempfile.TemporaryDirectory(prefix="validacao-", dir=state_path(self.root)) as temporary:
                    stage = Path(temporary)
                    unpack_package(archive, stage, release.version, release.repository)
                    if (stage / "requirements.txt").read_bytes() != (self.root / "requirements.txt").read_bytes():
                        raise UpdateError("Esta versao altera as bibliotecas. Instale o pacote manualmente.")
            except Exception:
                archive.unlink(missing_ok=True)
                raise
            return archive

        self._worker("download", work)
        self._status("Baixando atualizacao...")

    @Slot(str, object)
    def _completed(self, operation, value):
        self.busy = False
        if operation == "check":
            if self.release != value and self.archive:
                self.archive.unlink(missing_ok=True)
                self.archive = None
            self.release = value
            self._status(f"Versao {value.version} disponivel." if value else "Voce esta na versao mais recente.")
            if self.manual:
                self.window.bridge._emit_status(self.message)
            if value:
                self.offer_install()
        else:
            self.archive = value
            self._status("Download conferido. Pronto para instalar.")
            self._confirm_restart()

    @Slot(str)
    def _failed(self, message):
        if self.installing:
            try:
                self.acknowledge_session()
            except OSError:
                pass
        self.busy = False
        self.installing = False
        self.window.setEnabled(True)
        self._status(message)
        if self.manual or self.archive:
            self.window.bridge._emit_status(message)

    @Slot(int)
    def _progress(self, percent):
        self._status(f"Baixando atualizacao: {percent}%")

    def _confirm_restart(self):
        if self._capture_active() or not self.window.isVisible():
            self._status("Download pronto. Conclua a captura ou gravacao para instalar.")
            return
        self.dialog = QMessageBox(self.window)
        self.dialog.setWindowTitle("Instalar atualizacao")
        self.dialog.setText(f"Instalar a versao {self.release.version} e reiniciar?")
        self.dialog.setInformativeText("As imagens e anotacoes abertas serao recuperadas ao reiniciar.")
        install = self.dialog.addButton("Instalar e reiniciar", QMessageBox.ButtonRole.AcceptRole)
        later = self.dialog.addButton("Mais tarde", QMessageBox.ButtonRole.RejectRole)
        self.dialog.setDefaultButton(later)

        def answered():
            accepted = self.dialog.clickedButton() == install
            self.dialog.deleteLater()
            self.dialog = None
            if accepted:
                self._begin_install()

        self.dialog.finished.connect(answered)
        self.dialog.open()

    def _begin_install(self):
        if self._capture_active():
            self._status("Conclua a captura ou gravacao antes de instalar.")
            return
        # Development changes must be published, not replaced by an older build.
        if (self.root / ".git").exists():
            self._status("Pasta de desenvolvimento. Teste a instalacao na copia extraida do pacote ZIP.")
            self.window.bridge._emit_status(self.message)
            return
        self.installing = True
        self.window.setEnabled(False)
        self.window.web.page().runJavaScript("serializeUpdateSession()", self._session_saved)

    def _session_saved(self, payload):
        try:
            if not isinstance(payload, str):
                raise UpdateError("Nao foi possivel preservar a edicao. A instalacao foi adiada.")
            session = json.loads(payload)
            if session.get("error"):
                raise UpdateError(session["error"])
            write_json(state_path(self.root) / "sessao.json", session)
            self.window.bridge._persist()
            plan = prepare_installer(self.archive, self.root, self.release)
            self.helper = start_installer(plan)
            self._handshake_attempts = 0
            self.handshake_timer.start()
        except Exception as exc:
            self._failed(str(exc))

    def _check_handshake(self):
        self._handshake_attempts += 1
        if self.helper.poll() is not None:
            self.handshake_timer.stop()
            self._failed("O instalador nao iniciou. O programa foi mantido aberto.")
        elif (state_path(self.root) / "instalador-pronto").exists():
            self.handshake_timer.stop()
            self.window.close()
        elif self._handshake_attempts >= 100:
            self.handshake_timer.stop()
            self.helper.terminate()
            self._failed("O instalador nao respondeu. Tente novamente.")

    def _restore_session(self):
        path = state_path(self.root) / "sessao.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.window.web.page().runJavaScript("restoreUpdateSession(" + json.dumps(data) + ");")
        except (OSError, ValueError):
            self.window.bridge._emit_status("Nao foi possivel recuperar a edicao anterior. A copia foi preservada.")

    def acknowledge_session(self):
        path = state_path(self.root) / "sessao.json"
        if path.exists():
            path.replace(path.with_name("ultima-sessao.json"))
