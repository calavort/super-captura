"""Download the real public release and restart the real app in a disposable copy."""

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atualizacao.atualizador import (APP_FILES, InstanceLock, check_release, download_release, prepare_installer,
                         read_version, sha256, start_installer, state_path, write_json)
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True)
    parser.add_argument("--node-modules", required=True)
    args = parser.parse_args()
    # Keep the diagnostic copy intact on failure, including files of a live app.
    folder = Path(tempfile.mkdtemp(prefix="super-captura-online-"))
    print("Copia de teste:", folder, flush=True)
    for name in APP_FILES:
        destination = folder / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    info = read_version(folder)
    info["version"] = "7.0.0"
    write_json(folder / "versao.json", info)
    config = {"user": {"name": "Teste local", "email": ""}, "image_folder": "capturas", "video_folder": "videos", "auto_copy": False}
    write_json(folder / "configuracoes.json", config)
    personal = [folder / "configuracoes.json"]
    for directory in ("capturas", "videos"):
        (folder / directory).mkdir()
        target = folder / directory / "arquivo-preservado.txt"
        target.write_text("Dado local do teste", encoding="utf-8")
        personal.append(target)
    hashes = {path: sha256(path) for path in personal}
    release = check_release(info)
    expected_version = read_version(ROOT)["version"]
    assert release and release.version == expected_version
    archive = download_release(release, folder)
    print("OK: release publico detectado e ZIP real conferido por SHA-256", flush=True)

    bitmap = QImage(120, 80, QImage.Format.Format_RGB32)
    bitmap.fill(QColor("#247d4b"))
    binary = QByteArray()
    buffer = QBuffer(binary)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert bitmap.save(buffer, "PNG")
    source = "data:image/png;base64," + base64.b64encode(bytes(binary)).decode("ascii")
    state = state_path(folder)
    write_json(state / "sessao.json", {
        "schema": 1, "workspaceMode": "home", "bgImage": source,
        "homeAnnotations": [{"type": "Texto", "x": 3, "y": 3, "w": 100, "h": 30, "text": "Teste de reinicio real", "font": 10, "color": "#ffffff"}],
        "editionAnnotations": [], "editionCanvasSize": {"width": 1600, "height": 1000},
        "editionItems": [{"type": "Imagem", "source": source, "name": "Teste", "x": 10, "y": 10, "w": 120, "h": 80}],
    })
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = f"127.0.0.1:{port}"
    lock = InstanceLock(folder)
    assert lock.acquire()
    helper = start_installer(prepare_installer(archive, folder, release))
    deadline = time.monotonic() + 10
    while not (state / "instalador-pronto").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert (state / "instalador-pronto").exists()
    assert read_version(folder)["version"] == "7.0.0"
    lock.release()
    assert helper.wait(timeout=20) == 0
    result = json.loads((state / "resultado.json").read_text(encoding="utf-8"))
    assert result["ok"], result
    assert read_version(folder)["version"] == expected_version
    print("OK: arquivos atualizados, backup criado e reinicio solicitado", flush=True)
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    environment = dict(os.environ, NODE_PATH=args.node_modules)
    validation = subprocess.run([
        args.node, str(ROOT / "tests" / "verificar_reinicio.cjs"),
        f"http://127.0.0.1:{port}", str(folder), str(output / "validacao-reinicio-online.png"), expected_version
    ], env=environment, capture_output=True, text=True, timeout=45)
    print(validation.stdout, flush=True)
    if validation.returncode:
        print(validation.stderr, flush=True)
        raise RuntimeError("Falha ao validar o aplicativo reiniciado; copia preservada em " + str(folder))
    for path, digest in hashes.items():
        assert sha256(path) == digest, path
    assert (state / "ultima-sessao.json").exists()
    assert not (state / "sessao.json").exists()
    write_json(output / "validacao-release-online.json", {
        "release": release.version, "repository": release.repository, "sha256": release.digest,
        "upgrade_from": "7.0.0 (copia de teste)", "personal_files_preserved": True,
        "real_app_restarted": True, "session_restored": True,
    })
    print("OK: configuracoes, capturas e videos identicos; sessao recuperada no app real", flush=True)
    # Wait until Qt releases its profile files after closeWindow().
    for attempt in range(30):
        try:
            assert folder.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
            assert folder.name.startswith("super-captura-online-")
            shutil.rmtree(folder)
            break
        except PermissionError:
            time.sleep(0.1)
    print("TESTE ONLINE CONCLUIDO", flush=True)


if __name__ == "__main__":
    main()
