# -*- coding: utf-8 -*-
"""Super Captura - captura, anotação e gravação de tela."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from atualizador import InstanceLock, read_version, recover_transaction

os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --disable-gpu-compositing --disable-features=CalculateNativeWinOcclusion",
)

from PySide6.QtCore import QEvent, QObject, QRect, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaRecorder,
    QScreenCapture,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QRubberBand, QWidget

from atualizador_ui import UpdateController


APP_NAME = "Super Captura"
APP_REV = "Rev.7"
# Identidade do app no Windows: sem ela a barra de tarefas mostra o icone do
# Python (o processo real e o pythonw.exe) em vez do icone do Super Captura.
APP_USER_MODEL_ID = "Calavort.SuperCaptura"
BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "NOVA INTERFACE INTERFACE - SUPER CAPRURA.html"
SETTINGS_PATH = BASE_DIR / "configuracoes.json"
ICON_PATH = BASE_DIR / "super_captura.ico"
DEFAULT_IMAGE_DIR = BASE_DIR / "capturas"
DEFAULT_VIDEO_DIR = BASE_DIR / "videos"
CAPTURE_HIDE_DELAY_MS = 80
CAPTURE_DELIVERY_DELAY_MS = 0
DIRECT_PREVIEW_MAX_PIXELS = 10_000_000

RESIZE_EDGES = {
    "top": Qt.Edge.TopEdge,
    "bottom": Qt.Edge.BottomEdge,
    "left": Qt.Edge.LeftEdge,
    "right": Qt.Edge.RightEdge,
    "top-left": Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
    "top-right": Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    "bottom-left": Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
    "bottom-right": Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
}

# Suporte a janela nativa sem moldura no Windows (Aero Snap, Snap Layouts, sombra).
_IS_WINDOWS = sys.platform.startswith("win")
if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    WM_NCCALCSIZE = 0x0083
    VK_SNAPSHOT = 0x2C  # tecla PrintScreen
    VK_ESCAPE = 0x1B
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104
    SM_CXFRAME = 32
    SM_CYFRAME = 33
    SM_CXPADDEDBORDER = 92

    class _NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    _HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def default_settings() -> dict:
    return {
        "user": {"name": "Calavort", "email": ""},
        "delay": 0,
        "auto_copy": True,
        "auto_save": False,
        "video_format": "mp4",
        "video_fps": 30,
        "video_audio": "none",
        "color": "#107C41",
        "thickness": 4,
        "font_size": 28,
        "number": 1,
        "balloon_fill": True,
        "balloon_line": False,
        "bold": False,
        "italic": False,
        "underline": False,
        "image_folder": str(DEFAULT_IMAGE_DIR),
        "video_folder": str(DEFAULT_VIDEO_DIR),
        "last_save_dir": "",
        "last_save_format": "png",
        "shortcuts": {
            "area": "Alt+P",
            "copy": "Ctrl+C",
            "save": "Ctrl+S",
            "undo": "Ctrl+Z",
        },
    }


def _resolve_app_path(value: object, fallback: Path) -> Path:
    """Converte caminho salvo em caminho utilizável pelo programa.

    Caminhos relativos ficam dentro da pasta do Super Captura. Caminhos antigos
    de outro usuário/máquina serão validados em _ensure_writable_dir.
    """
    raw = str(value or "").strip()
    if not raw:
        return fallback
    folder = Path(raw).expanduser()
    if not folder.is_absolute():
        folder = BASE_DIR / folder
    return folder


def _ensure_writable_dir(value: object, fallback: Path) -> Path:
    """Garante uma pasta gravável, caindo para pasta local se o caminho salvo falhar."""
    preferred = _resolve_app_path(value, fallback)
    for candidate in (preferred, fallback, Path(tempfile.gettempdir()) / APP_NAME.replace(" ", "_")):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".teste_super_captura"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return candidate
        except OSError:
            continue
    return Path(tempfile.gettempdir())


def _normalise_saved_folders(settings: dict) -> bool:
    """Corrige pastas salvas que pertencem a outro usuário/OneDrive ou sem permissão."""
    changed = False
    for key, fallback in (("image_folder", DEFAULT_IMAGE_DIR), ("video_folder", DEFAULT_VIDEO_DIR)):
        current = settings.get(key)
        valid = _ensure_writable_dir(current, fallback)
        resolved_current = _resolve_app_path(current, fallback)
        if valid != resolved_current:
            settings[key] = str(valid)
            changed = True
    return changed


def load_settings() -> dict:
    settings = default_settings()
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            for key, value in saved.items():
                if key in {"user", "shortcuts"} and isinstance(value, dict):
                    settings[key].update(value)
                elif key in settings:
                    settings[key] = value
    except (OSError, ValueError, TypeError):
        pass
    if _normalise_saved_folders(settings):
        try:
            save_settings(settings)
        except OSError:
            pass
    return settings


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class CaptureOverlay(QWidget):
    """Janela transparente usada para recortar uma região do desktop."""

    def __init__(self, virtual_geometry: QRect, desktop_pixmap: QPixmap, callback: Callable, parent=None):
        super().__init__(parent)
        self.desktop_pixmap = desktop_pixmap
        self.callback = callback
        self.origin = None
        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(virtual_geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        # Foco forte + captura do teclado: garante que o ESC chegue aqui mesmo
        # quando outra janela estava ativa no momento da captura.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._finished = False

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.grabKeyboard()

    def cancel(self):
        """Cancela a seleção (ESC ou botão direito)."""
        self._finish(None)

    def _finish(self, result):
        if self._finished:
            return
        self._finished = True
        self.releaseKeyboard()
        self.callback(result)
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.desktop_pixmap)
        painter.setOpacity(0.18)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        painter.setOpacity(1.0)
        painter.setPen(QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.DashLine))
        painter.drawText(24, 34, "Arraste para selecionar a área | ESC ou botão direito cancela")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            self.cancel()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber.setGeometry(QRect(self.origin, self.origin).normalized())
            self.rubber.show()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancel()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.rubber.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.origin is None:
            return
        rect = self.rubber.geometry().normalized()
        self.rubber.hide()
        self.origin = None
        result = self.desktop_pixmap.copy(rect) if rect.width() >= 4 and rect.height() >= 4 else None
        self._finish(result)

    def closeEvent(self, event):
        # Fechada por qualquer outro caminho: avisa quem espera o recorte.
        self.releaseKeyboard()
        if not self._finished:
            self._finished = True
            self.callback(None)
        super().closeEvent(event)


class SuperWebView(QWebEngineView):
    """WebView que impede o zoom do Chromium e usa Ctrl+scroll só na imagem."""

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                step = 0.1 if delta > 0 else -0.1
                pos = event.position()
                self.page().runJavaScript(
                    "if (typeof handleCtrlWheelZoom === 'function') "
                    f"handleCtrlWheelZoom({step}, {pos.x():.2f}, {pos.y():.2f});"
                )
            self.setZoomFactor(1.0)
            event.accept()
            return
        super().wheelEvent(event)


class Bridge(QObject):
    # A interface é avisada por runJavaScript (ver _emit_status e companhia).

    def __init__(self, window: "MainWindow", settings: dict):
        super().__init__()
        self.window = window
        self.settings = settings
        self.overlay: Optional[CaptureOverlay] = None
        self._capture_timer = QTimer(self)
        self._capture_timer.setInterval(1000)
        self._capture_timer.timeout.connect(self._capture_countdown_tick)
        self._capture_remaining = 0
        self._pending_capture: Optional[tuple[str, bool, bool]] = None
        self._temp_capture_path: Optional[Path] = None

        self.capture_session: Optional[QMediaCaptureSession] = None
        self.screen_capture: Optional[QScreenCapture] = None
        self.media_recorder: Optional[QMediaRecorder] = None
        self.audio_input: Optional[QAudioInput] = None
        self.video_recording = False
        self.video_file: Optional[Path] = None

    def _emit_status(self, text: str) -> None:
        script = f"if (typeof setStatus === 'function') setStatus({json.dumps(text, ensure_ascii=False)});"
        self.window.web.page().runJavaScript(script)

    def _persist(self) -> None:
        try:
            save_settings(self.settings)
        except OSError as exc:
            self._emit_status(f"Não foi possível salvar as configurações: {exc}")

    def _emit_settings(self) -> None:
        payload = json.dumps(self.settings, ensure_ascii=False)
        self.window.web.page().runJavaScript(
            f"if (typeof applySettings === 'function') applySettings({payload});"
        )

    @staticmethod
    def _pixmap_to_data_url(pixmap: QPixmap) -> str:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice

        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not pixmap.save(buffer, "PNG"):
            return ""
        return "data:image/png;base64," + bytes(byte_array.toBase64()).decode("ascii")

    def _emit_pixmap(self, pixmap: QPixmap, auto_copy: bool, auto_save: bool) -> None:
        """Entrega a captura diretamente quando o tamanho permite.

        Capturas comuns seguem em memória para aparecerem mais rápido. O PNG
        temporário fica apenas como fallback para imagens muito grandes ou
        quando a conversão em memória falhar.
        """
        try:
            if self._temp_capture_path:
                self._temp_capture_path.unlink(missing_ok=True)
                self._temp_capture_path = None
        except OSError:
            pass

        pixel_count = pixmap.width() * pixmap.height()
        source = ""
        if pixel_count <= DIRECT_PREVIEW_MAX_PIXELS:
            try:
                source = self._pixmap_to_data_url(pixmap)
            except Exception:
                source = ""

        if not source:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            self._temp_capture_path = Path(tempfile.gettempdir()) / f"super_captura_atual_{os.getpid()}_{stamp}.png"
            if pixmap.save(str(self._temp_capture_path), "PNG"):
                source = QUrl.fromLocalFile(str(self._temp_capture_path)).toString()
            else:
                source = self._pixmap_to_data_url(pixmap)
        self._send_image_source(source, auto_copy, auto_save)

    def _send_image_source(self, source: str, auto_copy: bool, auto_save: bool) -> None:
        script = (
            "if (typeof loadImageData === 'function') loadImageData("
            f"{json.dumps(source)}, {str(bool(auto_copy)).lower()}, {str(bool(auto_save)).lower()});"
        )
        self.window.web.page().runJavaScript(script)

    @staticmethod
    def _data_url_to_image(data_url: str) -> QImage:
        payload = data_url.split(",", 1)[1] if "," in data_url else data_url
        image = QImage()
        try:
            image.loadFromData(base64.b64decode(payload))
        except (ValueError, TypeError):
            pass
        return image

    @staticmethod
    def _desktop_pixmap() -> tuple[QPixmap, QRect]:
        screens = QGuiApplication.screens()
        if not screens:
            raise RuntimeError("Nenhuma tela encontrada.")
        if len(screens) == 1:
            screen = screens[0]
            return screen.grabWindow(0), screen.geometry()

        virtual_geometry = screens[0].geometry()
        for screen in screens[1:]:
            virtual_geometry = virtual_geometry.united(screen.geometry())

        image = QImage(virtual_geometry.size(), QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.black)
        painter = QPainter(image)
        for screen in screens:
            geometry = screen.geometry()
            painter.drawPixmap(
                geometry.x() - virtual_geometry.x(),
                geometry.y() - virtual_geometry.y(),
                screen.grabWindow(0),
            )
        painter.end()
        return QPixmap.fromImage(image), virtual_geometry

    @Slot()
    def requestSettings(self):
        self._emit_settings()
        self.window.updater.ui_ready()

    @Slot()
    def checkUpdates(self):
        self.window.updater.check()

    @Slot()
    def installUpdate(self):
        self.window.updater.offer_install()

    @Slot()
    def acknowledgeUpdateSession(self):
        self.window.updater.acknowledge_session()

    @Slot()
    def cancelCapture(self):
        """Cancela a captura pendente: contagem regressiva ou seleção de área."""
        cancelled = False
        if self._capture_timer.isActive():
            self._capture_timer.stop()
            self._capture_remaining = 0
            self._pending_capture = None
            cancelled = True
        overlay = self.overlay
        self.overlay = None
        if overlay is not None:
            try:
                if overlay.isVisible():
                    overlay.cancel()
                    cancelled = True
            except RuntimeError:  # sobreposição já destruída
                pass
        if cancelled:
            if not self.window.isVisible():
                self.window.show()
                self.window.activateWindow()
            self._emit_status("Captura cancelada.")
        return cancelled

    def capture_pending(self) -> bool:
        """Há captura em andamento (contagem ou seleção de área na tela)?"""
        overlay = self.overlay
        try:
            overlay_active = overlay is not None and overlay.isVisible()
        except RuntimeError:
            overlay_active = False
        return bool(self._capture_timer.isActive() or overlay_active)

    @Slot(int, bool, bool)
    def captureArea(self, delay: int = 0, auto_copy: bool = False, auto_save: bool = False):
        self._schedule_capture("area", delay, auto_copy, auto_save)

    @Slot(int, bool, bool)
    def captureScreen(self, delay: int = 0, auto_copy: bool = False, auto_save: bool = False):
        self._schedule_capture("screen", delay, auto_copy, auto_save)

    def _schedule_capture(self, kind: str, delay: int, auto_copy: bool, auto_save: bool) -> None:
        if self.window.updater.installing:
            return
        self._capture_timer.stop()
        self._capture_remaining = max(0, min(int(delay), 60))
        self._pending_capture = (kind, bool(auto_copy), bool(auto_save))
        if self._capture_remaining:
            self._emit_status(f"Captura em {self._capture_remaining} segundo(s)...")
            self._capture_timer.start()
        else:
            self._begin_pending_capture()

    def _capture_countdown_tick(self) -> None:
        self._capture_remaining -= 1
        if self._capture_remaining <= 0:
            self._capture_timer.stop()
            self._begin_pending_capture()
        else:
            self._emit_status(f"Captura em {self._capture_remaining} segundo(s)...")

    def _begin_pending_capture(self) -> None:
        if not self._pending_capture:
            return
        kind = self._pending_capture[0]
        self.window.hide()
        QApplication.processEvents()
        QTimer.singleShot(CAPTURE_HIDE_DELAY_MS, self._start_area_capture if kind == "area" else self._take_full_capture)

    def _start_area_capture(self) -> None:
        try:
            pixmap, virtual_geometry = self._desktop_pixmap()
            self.overlay = CaptureOverlay(virtual_geometry, pixmap, self._finish_area_capture)
            self.overlay.show()
            self.overlay.activateWindow()
            self.overlay.raise_()
            self._emit_status("Selecione a área desejada na tela.")
        except Exception as exc:
            self.window.show()
            self._emit_status(f"Erro ao iniciar captura: {exc}")

    def _finish_area_capture(self, pixmap: Optional[QPixmap]) -> None:
        self.overlay = None
        self.window.show()
        self.window.activateWindow()
        QApplication.processEvents()
        if pixmap is None:
            self._pending_capture = None
            QTimer.singleShot(CAPTURE_DELIVERY_DELAY_MS, lambda: self._emit_status("Captura cancelada."))
        else:
            _, auto_copy, auto_save = self._pending_capture or ("area", False, False)
            QTimer.singleShot(
                CAPTURE_DELIVERY_DELAY_MS,
                lambda image=pixmap, copy=auto_copy, save=auto_save: self._deliver_capture(
                    image, copy, save, "Área"
                ),
            )
            self._pending_capture = None

    def _take_full_capture(self) -> None:
        try:
            pixmap, _ = self._desktop_pixmap()
            self.window.show()
            self.window.activateWindow()
            QApplication.processEvents()
            _, auto_copy, auto_save = self._pending_capture or ("screen", False, False)
            QTimer.singleShot(
                CAPTURE_DELIVERY_DELAY_MS,
                lambda image=pixmap, copy=auto_copy, save=auto_save: self._deliver_capture(
                    image, copy, save, "Tela"
                ),
            )
        except Exception as exc:
            self._emit_status(f"Erro ao capturar tela: {exc}")
        finally:
            self._pending_capture = None
            if not self.window.isVisible():
                self.window.show()
                self.window.activateWindow()

    def _deliver_capture(self, pixmap: QPixmap, auto_copy: bool, auto_save: bool, label: str) -> None:
        self._emit_pixmap(pixmap, auto_copy, auto_save)
        self._emit_status(f"{label} capturada: {pixmap.width()} x {pixmap.height()} px.")

    @Slot()
    def openImage(self):
        filename, _ = QFileDialog.getOpenFileName(
            self.window,
            "Abrir imagem",
            str(Path.home()),
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp);;Todos os arquivos (*.*)",
        )
        if not filename:
            return
        image = QImage(filename)
        if image.isNull():
            self._emit_status("Não foi possível abrir a imagem.")
            return
        self._send_image_source(QUrl.fromLocalFile(filename).toString(), False, False)
        self._emit_status(f"Imagem aberta: {Path(filename).name}")

    def _image_dir(self) -> Path:
        folder = _ensure_writable_dir(self.settings.get("image_folder"), DEFAULT_IMAGE_DIR)
        if folder != _resolve_app_path(self.settings.get("image_folder"), DEFAULT_IMAGE_DIR):
            self.settings["image_folder"] = str(folder)
            self._persist()
            self._emit_settings()
            self._emit_status(f"Pasta de imagens inválida; usando: {folder}")
        return folder

    def _video_dir(self) -> Path:
        folder = _ensure_writable_dir(self.settings.get("video_folder"), DEFAULT_VIDEO_DIR)
        if folder != _resolve_app_path(self.settings.get("video_folder"), DEFAULT_VIDEO_DIR):
            self.settings["video_folder"] = str(folder)
            self._persist()
            self._emit_settings()
            self._emit_status(f"Pasta de vídeos inválida; usando: {folder}")
        return folder

    @Slot(str, str)
    def saveImage(self, data_url: str, fmt: str = "png"):
        image = self._data_url_to_image(data_url)
        if image.isNull():
            self._emit_status("Nenhuma imagem válida para salvar.")
            return
        extension = "jpg" if str(fmt).lower() in {"jpg", "jpeg"} else "png"
        filename = self._image_dir() / f"Super_Captura_{datetime.now():%Y%m%d_%H%M%S}.{extension}"
        ok = image.save(str(filename), "JPG" if extension == "jpg" else "PNG", 95)
        self._emit_status(f"Imagem salva: {filename.name}" if ok else "Falha ao salvar imagem.")

    def _last_save_dir(self) -> Path:
        """Pasta sugerida em "Salvar como": a última usada, se ainda existir."""
        raw = str(self.settings.get("last_save_dir") or "").strip()
        if raw:
            folder = Path(raw)
            if folder.is_dir():
                return folder
        return self._image_dir()

    def _remember_save_location(self, path: Path, extension: str) -> None:
        self.settings["last_save_dir"] = str(path.parent)
        self.settings["last_save_format"] = extension
        self._persist()

    @Slot(str, str)
    def saveImageAs(self, data_url: str, fmt: str = "png"):
        last_format = str(self.settings.get("last_save_format") or "png").lower()
        extension = "jpg" if last_format in {"jpg", "jpeg"} else "png"
        default_name = self._last_save_dir() / f"Super_Captura_{datetime.now():%Y%m%d_%H%M%S}.{extension}"
        preferred_filter = "JPG (*.jpg *.jpeg)" if extension == "jpg" else "PNG (*.png)"
        filename, selected_filter = QFileDialog.getSaveFileName(
            self.window,
            "Salvar imagem como",
            str(default_name),
            "PNG (*.png);;JPG (*.jpg *.jpeg)",
            preferred_filter,
        )
        if not filename:
            return
        image = self._data_url_to_image(data_url)
        if image.isNull():
            self._emit_status("Nenhuma imagem válida para salvar.")
            return
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".jpg" if "JPG" in selected_filter else ".png")
        output_format = "JPG" if path.suffix.lower() in {".jpg", ".jpeg"} else "PNG"
        ok = image.save(str(path), output_format, 95)
        if ok:
            self._remember_save_location(path, "jpg" if output_format == "JPG" else "png")
            self._emit_status(f"Imagem salva como: {path.name} (em {path.parent})")
        else:
            self._emit_status("Falha ao salvar imagem.")

    @Slot(str)
    @Slot(str, bool)
    def copyImage(self, data_url: str, notify: bool = True):
        image = self._data_url_to_image(data_url)
        if image.isNull():
            if notify:
                self._emit_status("Nenhuma imagem válida para copiar.")
            return
        QApplication.clipboard().setImage(image)
        if notify:
            self._emit_status("Imagem copiada. Use Ctrl+V para colar.")

    @Slot()
    def pasteClipboardImageToEdition(self):
        image = QApplication.clipboard().image()
        if image.isNull():
            self._emit_status("Não há imagem na área de transferência.")
            return
        data_url = self._pixmap_to_data_url(QPixmap.fromImage(image))
        if not data_url:
            self._emit_status("Não foi possível ler a imagem da área de transferência.")
            return
        self.window.web.page().runJavaScript(
            "if (typeof addEditionImage === 'function') addEditionImage("
            f"{json.dumps(data_url)}, 'Imagem colada');"
        )
        self._emit_status("Imagem colada na guia Edição.")

    @Slot()
    def openCapturesFolder(self):
        self._open_folder(self._image_dir())
        self._emit_status("Pasta de capturas aberta.")

    @staticmethod
    def _open_folder(folder: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.spawnlp(os.P_NOWAIT, "open", "open", str(folder))
        else:
            os.spawnlp(os.P_NOWAIT, "xdg-open", "xdg-open", str(folder))

    @Slot(str, str)
    def saveUser(self, name: str, email: str):
        name = str(name).strip()
        email = str(email).strip()
        if not name:
            self._emit_status("Informe o nome do usuário.")
            return
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            self._emit_status("Informe um e-mail válido.")
            return
        self.settings["user"] = {"name": name, "email": email}
        self._persist()
        self._emit_settings()
        self._emit_status("Cadastro do usuário salvo.")

    @Slot(str)
    def savePreferences(self, payload: str):
        try:
            incoming = json.loads(payload)
        except (ValueError, TypeError):
            return
        allowed = {
            "delay", "auto_copy", "auto_save", "video_format", "video_fps", "video_audio",
            "color", "thickness", "font_size", "number", "balloon_fill", "balloon_line",
            "bold", "italic", "underline",
            "pen_thickness", "highlighter_thickness", "recent_colors",
        }
        if isinstance(incoming, dict):
            for key in allowed:
                if key in incoming:
                    self.settings[key] = incoming[key]
            self._persist()

    @Slot(str, str, str, str)
    def updateShortcuts(self, area: str, copy: str, save: str, undo: str):
        shortcuts = {"area": area.strip(), "copy": copy.strip(), "save": save.strip(), "undo": undo.strip()}
        error = self.window.apply_shortcuts(shortcuts)
        if error:
            self._emit_status(error)
            return
        self.settings["shortcuts"] = shortcuts
        self._persist()
        self._emit_settings()
        self._emit_status("Teclas de atalho atualizadas.")

    @Slot()
    def selectImageFolder(self):
        folder = QFileDialog.getExistingDirectory(self.window, "Pasta das imagens", str(self._image_dir()))
        if folder:
            self.settings["image_folder"] = folder
            self._persist()
            self._emit_settings()
            self._emit_status("Pasta de imagens atualizada.")

    @staticmethod
    def _plain_audio_name(text: str) -> str:
        return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()

    def _find_system_audio_input(self):
        terms = (
            "stereo mix",
            "mixagem stereo",
            "mixagem estereo",
            "what u hear",
            "wave out mix",
            "loopback",
        )
        for device in QMediaDevices.audioInputs():
            name = self._plain_audio_name(device.description())
            if any(term in name for term in terms):
                return device
        return None

    def _audio_input_names(self) -> str:
        names = [device.description() for device in QMediaDevices.audioInputs()]
        return ", ".join(names) if names else "nenhuma entrada de áudio"

    @Slot()
    def openSoundPanel(self):
        try:
            subprocess.Popen("control mmsys.cpl,,1", shell=True)
            self._emit_status("Abra a aba Gravação, habilite Mixagem Estéreo/Stereo Mix e tente novamente.")
        except OSError as exc:
            self._emit_status(f"Não foi possível abrir o painel de som: {exc}")

    @Slot()
    def selectVideoFolder(self):
        folder = QFileDialog.getExistingDirectory(self.window, "Pasta dos vídeos", str(self._video_dir()))
        if folder:
            self.settings["video_folder"] = folder
            self._persist()
            self._emit_settings()
            self._emit_status("Pasta de vídeos atualizada.")

    @Slot(str, int, str)
    def startVideoRecording(self, file_format: str = "mp4", fps: int = 30, audio_mode: str = "none"):
        if self.window.updater.installing:
            return
        if self.video_recording:
            self.stopVideoRecording()
            return
        try:
            system_audio_device = self._find_system_audio_input() if audio_mode == "sys" else None
            if audio_mode == "sys" and system_audio_device is None:
                self._emit_video_state(False, "")
                self._emit_status(
                    "Som do sistema indisponível: não é autorização do programa. "
                    "O Windows precisa expor Mixagem Estéreo/Stereo Mix/What U Hear como entrada de gravação. "
                    f"Entradas detectadas: {self._audio_input_names()}."
                )
                return

            screen = QGuiApplication.primaryScreen()
            if screen is None:
                raise RuntimeError("Nenhuma tela disponível para gravação.")

            file_format = file_format if file_format in {"mp4", "mkv", "avi"} else "mp4"
            fps = 60 if int(fps) >= 60 else 30
            self.video_file = self._video_dir() / f"Super_Gravacao_{datetime.now():%Y%m%d_%H%M%S}.{file_format}"

            self.capture_session = QMediaCaptureSession(self)
            self.screen_capture = QScreenCapture(self)
            self.screen_capture.setScreen(screen)
            self.capture_session.setScreenCapture(self.screen_capture)

            self.media_recorder = QMediaRecorder(self)
            self.capture_session.setRecorder(self.media_recorder)
            media_format = QMediaFormat()
            format_map = {
                "mp4": QMediaFormat.FileFormat.MPEG4,
                "mkv": QMediaFormat.FileFormat.Matroska,
                "avi": QMediaFormat.FileFormat.AVI,
            }
            codec_map = {
                "mp4": QMediaFormat.VideoCodec.H264,
                "mkv": QMediaFormat.VideoCodec.H264,
                "avi": QMediaFormat.VideoCodec.MotionJPEG,
            }
            media_format.setFileFormat(format_map[file_format])
            media_format.setVideoCodec(codec_map[file_format])
            self.media_recorder.setMediaFormat(media_format)
            self.media_recorder.setVideoFrameRate(float(fps))
            self.media_recorder.setVideoResolution(screen.size())
            self.media_recorder.setQuality(QMediaRecorder.Quality.HighQuality)
            self.media_recorder.setOutputLocation(QUrl.fromLocalFile(str(self.video_file)))

            audio_note = ""
            if audio_mode == "mic":
                self.audio_input = QAudioInput(self)
                self.capture_session.setAudioInput(self.audio_input)
                audio_note = " Áudio do microfone ativado."
            elif audio_mode == "sys":
                if system_audio_device:
                    self.audio_input = QAudioInput(system_audio_device, self)
                    self.capture_session.setAudioInput(self.audio_input)
                    audio_note = f" Áudio do sistema ativado por: {system_audio_device.description()}."

            self.media_recorder.errorOccurred.connect(self._on_video_error)
            self.screen_capture.errorOccurred.connect(lambda error, text: self._on_video_error(error, text))
            self.screen_capture.start()
            self.media_recorder.record()
            self.video_recording = True
            self._emit_video_state(True, self.video_file.name)
            self._emit_status(f"Gravação iniciada: {self.video_file.name}.{audio_note}")
        except Exception as exc:
            self._cleanup_video()
            self._emit_status(f"Não foi possível iniciar a gravação: {exc}")

    @Slot()
    def stopVideoRecording(self):
        if not self.video_recording:
            return
        self.video_recording = False
        if self.media_recorder:
            self.media_recorder.stop()
        QTimer.singleShot(700, self._finish_video_stop)

    def _finish_video_stop(self) -> None:
        filename = self.video_file.name if self.video_file else "vídeo"
        if self.screen_capture:
            self.screen_capture.stop()
        self._emit_video_state(False, filename)
        self._emit_status(f"Gravação concluída: {filename}")
        self._cleanup_video()

    def _on_video_error(self, error, error_text: str) -> None:
        if not error_text:
            return
        was_recording = self.video_recording
        self.video_recording = False
        if self.media_recorder and was_recording:
            self.media_recorder.stop()
        if self.screen_capture:
            self.screen_capture.stop()
        self._emit_video_state(False, "")
        self._emit_status(f"Erro na gravação: {error_text}")
        self._cleanup_video()

    def _cleanup_video(self) -> None:
        for obj in (self.audio_input, self.media_recorder, self.screen_capture, self.capture_session):
            if obj:
                obj.deleteLater()
        self.audio_input = None
        self.media_recorder = None
        self.screen_capture = None
        self.capture_session = None

    def _emit_video_state(self, active: bool, detail: str) -> None:
        self.window.web.page().runJavaScript(
            "if (typeof updateVideoState === 'function') updateVideoState("
            f"{str(bool(active)).lower()}, {json.dumps(detail, ensure_ascii=False)});"
        )

    def cleanup(self) -> None:
        try:
            if self._temp_capture_path:
                self._temp_capture_path.unlink(missing_ok=True)
        except OSError:
            pass

    @Slot()
    def minimizeWindow(self):
        self.window.showMinimized()

    @Slot()
    def maximizeWindow(self):
        self.window.show_resize_cover(900)
        QApplication.processEvents()
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

        # A troca de estado da janela também dispara MainWindow.changeEvent, que
        # sincroniza o ícone (cobre inclusive o maximizar via Aero Snap).
        self.window.web.setUpdatesEnabled(True)
        self.window.web.repaint()
        QTimer.singleShot(30, self.window.web.update)
        QTimer.singleShot(240, self.window.web.update)

    def _emit_maximize_state(self, maximized: bool) -> None:
        self.window.web.page().runJavaScript(
            "if (typeof updateMaximizeIcon === 'function') updateMaximizeIcon("
            f"{str(bool(maximized)).lower()});"
        )

    @Slot()
    def closeWindow(self):
        self.window.close()

    @Slot()
    def startWindowDrag(self):
        handle = self.window.windowHandle()
        if handle:
            handle.startSystemMove()

    @Slot(str)
    def startWindowResize(self, edge: str):
        edges = RESIZE_EDGES.get(edge)
        handle = self.window.windowHandle()
        if handle and edges is not None and not self.window.isMaximized():
            handle.startSystemResize(edges)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        for key, fallback in (("image_folder", DEFAULT_IMAGE_DIR), ("video_folder", DEFAULT_VIDEO_DIR)):
            folder = _ensure_writable_dir(self.settings.get(key), fallback)
            if folder != _resolve_app_path(self.settings.get(key), fallback):
                self.settings[key] = str(folder)

        self.setWindowTitle(f"{APP_NAME} - {APP_REV} - v{read_version(BASE_DIR)['version']}")
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        # No Windows a janela permanece nativa (Aero Snap / Snap Layouts / maximizar
        # arrastando ao topo); a moldura é removida no nativeEvent (WM_NCCALCSIZE).
        # Em outros sistemas mantém-se o comportamento sem moldura do Qt.
        if not _IS_WINDOWS:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QMainWindow { background: #E1DFDD; } QWebEngineView { background: #E1DFDD; }")
        # Largura mínima suficiente para a faixa "Página Inicial" (a mais larga)
        # caber sem barra de rolagem horizontal (conteúdo mede ~1204px).
        self.resize(1240, 720)
        self.setMinimumSize(1224, 600)

        self.web = SuperWebView(self)
        self.web.setStyleSheet("background: #E1DFDD;")
        self.setCentralWidget(self.web)
        self._resize_cover = QWidget(self)
        self._resize_cover.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._resize_cover.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._resize_cover.setStyleSheet("background: #E1DFDD;")
        self._resize_cover.hide()
        self.web.setZoomFactor(1.0)
        self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        try:
            self.web.page().setBackgroundColor(QColor("#E1DFDD"))
        except AttributeError:
            pass

        self.bridge = Bridge(self, self.settings)
        self.updater = UpdateController(self, BASE_DIR)
        self.channel = QWebChannel(self.web.page())
        self.channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(self.channel)
        self.web.setUrl(QUrl.fromLocalFile(str(HTML_PATH)))

        self.shortcuts: dict[str, QShortcut] = {}
        shortcut_error = self.apply_shortcuts(self.settings.get("shortcuts", {}))
        if shortcut_error:
            self.apply_shortcuts(default_settings()["shortcuts"])

        exit_action = QAction("Sair", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        self.addAction(exit_action)

    def showEvent(self, event):
        super().showEvent(event)
        if _IS_WINDOWS and not getattr(self, "_transitions_disabled", False):
            self._transitions_disabled = True
            self._disable_dwm_transitions()
            self._install_printscreen_hook()

    def _install_printscreen_hook(self) -> None:
        """Intercepta a tecla PrintScreen para abrir a captura de área.

        Usa hook de teclado de baixo nível (WH_KEYBOARD_LL) porque no Windows 11
        o sistema consome o PrintScreen antes do RegisterHotKey (a tecla nunca
        gera WM_HOTKEY). O hook roda antes e consome a tecla, impedindo que a
        Ferramenta de Captura do Windows abra. Alt/Ctrl/Shift+PrintScreen são
        repassados ao sistema (Alt+PrtScn continua copiando a janela ativa).
        """
        user32 = ctypes.windll.user32
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
        user32.CallNextHookEx.restype = ctypes.c_longlong
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]

        def handler(n_code, w_param, l_param):
            if n_code == 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                kb = _KBDLLHOOKSTRUCT.from_address(l_param)
                if kb.vkCode == VK_ESCAPE and self.bridge.capture_pending():
                    QTimer.singleShot(0, self.bridge.cancelCapture)
                    return 1  # consome: o ESC serve só para cancelar a captura
                if kb.vkCode == VK_SNAPSHOT:
                    modifiers = any(
                        user32.GetAsyncKeyState(vk) & 0x8000
                        for vk in (0x10, 0x11, 0x12, 0x5B, 0x5C)  # Shift/Ctrl/Alt/Win
                    )
                    if not modifiers:
                        QTimer.singleShot(0, self._trigger_printscreen_capture)
                        return 1  # consome: a Ferramenta de Captura não abre
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._kb_hook_proc = _HOOKPROC(handler)  # referência viva: evita GC do callback
        self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_hook_proc, None, 0)
        if os.environ.get("SUPERCAP_DEBUG"):
            print(f"[hotkey] hook LL instalado: {bool(self._kb_hook)}", file=sys.stderr, flush=True)

    def _trigger_printscreen_capture(self) -> None:
        if os.environ.get("SUPERCAP_DEBUG"):
            print("[hotkey] PrintScreen interceptado -> captura de area", file=sys.stderr, flush=True)
        if os.environ.get("SUPERCAP_HOTKEY_DRYRUN"):
            return
        self.web.page().runJavaScript(
            "if (typeof requestCapture === 'function') requestCapture('area');"
        )

    def _disable_dwm_transitions(self) -> None:
        """Desliga a animação de fade do DWM ao ocultar/mostrar a janela.

        Sem isto, ao capturar a tela o hide() da janela ainda está no meio da
        animação de desaparecimento (semitransparente) e a janela acaba entrando
        na própria captura. Com as transições desativadas o hide() é imediato.
        """
        try:
            hwnd = int(self.winId())
            value = ctypes.c_int(1)  # DWMWA_TRANSITIONS_FORCEDISABLED = 3
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 3, ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception:
            pass

    def show_resize_cover(self, duration_ms: int = 700) -> None:
        self._resize_cover.setGeometry(self.rect())
        self._resize_cover.raise_()
        self._resize_cover.show()
        QTimer.singleShot(max(120, duration_ms), self._resize_cover.hide)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_resize_cover") and self._resize_cover.isVisible():
            self._resize_cover.setGeometry(self.rect())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "bridge"):
            self.bridge._emit_maximize_state(self.isMaximized())

    def nativeEvent(self, event_type, message):
        """Remove a moldura nativa no Windows sem abrir mão do Aero Snap.

        Ao responder WM_NCCALCSIZE com a área toda como cliente, a janela fica
        sem borda visível mas continua sendo uma janela comum do Windows, então
        arrastar a barra de título até uma borda aciona o encaixe (Snap). Quando
        maximizada, recolhe-se a moldura para não invadir a barra de tarefas.
        """
        if _IS_WINDOWS and event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCCALCSIZE and msg.wParam:
                if self.isMaximized():
                    params = _NCCALCSIZE_PARAMS.from_address(msg.lParam)
                    rect = params.rgrc[0]
                    metrics = ctypes.windll.user32.GetSystemMetrics
                    padded = metrics(SM_CXPADDEDBORDER)
                    frame_x = metrics(SM_CXFRAME) + padded
                    frame_y = metrics(SM_CYFRAME) + padded
                    rect.left += frame_x
                    rect.top += frame_y
                    rect.right -= frame_x
                    rect.bottom -= frame_y
                return True, 0
        return super().nativeEvent(event_type, message)

    def apply_shortcuts(self, shortcuts: dict) -> Optional[str]:
        required = {"area", "copy", "save", "undo"}
        if set(shortcuts) != required:
            return "Configuração de atalhos incompleta."
        normalized = {}
        for action, text in shortcuts.items():
            sequence = QKeySequence(str(text))
            if sequence.isEmpty():
                return f"Atalho inválido: {text or '(vazio)'}."
            portable = sequence.toString(QKeySequence.SequenceFormat.PortableText).lower()
            if portable in normalized:
                return "Cada ação precisa usar uma tecla de atalho diferente."
            normalized[portable] = action

        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self.shortcuts.clear()

        scripts = {
            "area": "requestCapture('area')",
            "copy": "copyFinalImage()",
            "save": "savePng()",
            "undo": "undoAnnotation()",
        }
        for action, text in shortcuts.items():
            shortcut = QShortcut(QKeySequence(text), self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(lambda script=scripts[action]: self.web.page().runJavaScript(script))
            self.shortcuts[action] = shortcut
        return None

    def closeEvent(self, event):
        if _IS_WINDOWS and getattr(self, "_kb_hook", None):
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self._kb_hook)
                self._kb_hook = None
            except Exception:
                pass
        if self.bridge.video_recording:
            self.bridge.stopVideoRecording()
        self.bridge.cleanup()
        super().closeEvent(event)


def _apply_windows_app_identity() -> None:
    """Faz o Windows tratar o processo como "Super Captura".

    Sem isto o botão da barra de tarefas herda a identidade do pythonw.exe e
    mostra o ícone do Python; com o AppUserModelID explícito a barra de
    tarefas e o Menu Iniciar usam o ícone da própria janela.
    """
    if not _IS_WINDOWS:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def main() -> None:
    _apply_windows_app_identity()
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Edflávio Calavort")
    app.setDesktopFileName(APP_NAME)
    lock = InstanceLock(BASE_DIR)
    if not lock.acquire():
        QMessageBox.information(None, APP_NAME, "O Super Captura ja esta aberto ou sendo atualizado nesta pasta.")
        return
    try:
        recover_transaction(BASE_DIR)
    except Exception as exc:
        QMessageBox.critical(None, APP_NAME, f"Nao foi possivel recuperar a atualizacao: {exc}")
        lock.release()
        return
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = MainWindow()
    window.show()
    try:
        result = app.exec()
    finally:
        lock.release()
    sys.exit(result)


if __name__ == "__main__":
    main()
