import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ferramentas"))

import atualizador as updater
from publicar_release import build_package


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="super-captura-test-")
        self.base = Path(self.temporary.name)
        self.source = self.base / "fonte"
        self.target = self.base / "instalacao"
        for root in (self.source, self.target):
            root.mkdir()
            for name in updater.APP_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"# arquivo de teste\n" if name.endswith(".py") else b"conteudo\n")
            updater.write_json(root / "versao.json", {
                "app_id": updater.APP_ID, "version": "7.1.0", "repository": "calavort/super-captura"})
        self.personal = {
            "configuracoes.json": b'{"user":"local"}',
            "capturas/captura.png": b"imagem-pessoal",
            "videos/video.mp4": b"video-pessoal",
            "outro-arquivo.txt": b"nao deve ser alterado",
        }
        for relative, content in self.personal.items():
            for root in (self.source, self.target):
                path = root / relative
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(content)

    def tearDown(self):
        self.temporary.cleanup()

    def package(self):
        (self.source / "app.py").write_text("# nova versao\n", encoding="utf-8")
        return build_package(self.source, "7.1.1")

    def release_data(self, archive):
        return {
            "tag_name": "v7.1.1", "draft": False, "prerelease": False,
            "assets": [{"name": archive.name, "size": archive.stat().st_size,
                        "browser_download_url": f"https://github.com/calavort/super-captura/releases/download/v7.1.1/{archive.name}",
                        "digest": "sha256:" + updater.sha256(archive)}],
        }

    def assert_personal_unchanged(self):
        for relative, content in self.personal.items():
            self.assertEqual((self.target / relative).read_bytes(), content)

    def test_numeric_versions_and_no_downgrade(self):
        self.assertGreater(updater.version_tuple("7.10.0"), updater.version_tuple("v7.9.9"))
        for invalid in ("7.1", "7.1.1-beta", "../7.1.1", "07.1.0"):
            with self.assertRaises(updater.UpdateError):
                updater.version_tuple(invalid)
        data = self.release_data(self.package())
        current = updater.read_version(self.target)
        current["version"] = "7.1.2"
        self.assertIsNone(updater.release_from_json(data, current))
        data["prerelease"] = True
        self.assertIsNone(updater.release_from_json(data, current))

    def test_package_excludes_personal_files_and_installs(self):
        archive = self.package()
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(set(package.namelist()), set(updater.APP_FILES) | {updater.MANIFEST})
        old_app = (self.target / "app.py").read_bytes()
        backup = updater.install_package(archive, self.target, "7.1.1", "calavort/super-captura")
        self.assertEqual(updater.read_version(self.target)["version"], "7.1.1")
        self.assertEqual((backup / "app.py").read_bytes(), old_app)
        self.assertEqual((self.target / "app.py").read_bytes(), (self.source / "app.py").read_bytes())
        self.assert_personal_unchanged()

    def test_release_must_include_matching_asset_and_digest(self):
        archive = self.package()
        current = updater.read_version(self.target)
        data = self.release_data(archive)
        release = updater.release_from_json(data, current)
        self.assertEqual(release.digest, updater.sha256(archive))
        data["assets"][0]["browser_download_url"] = "https://example.com/other.zip"
        with self.assertRaises(updater.UpdateError):
            updater.release_from_json(data, current)
        data = self.release_data(archive)
        data["assets"][0]["digest"] = None
        with self.assertRaises(updater.UpdateError):
            updater.release_from_json(data, current)

    def test_offline_and_unpublished_messages(self):
        current = updater.read_version(self.target)
        cases = [
            (urllib.error.URLError("offline"), "Sem conexao"),
            (urllib.error.HTTPError("url", 404, "missing", {}, None), "ainda nao publicado"),
            (urllib.error.HTTPError("url", 403, "limit", {}, None), "limite"),
        ]
        for error, message in cases:
            with patch.object(updater, "get_bytes", side_effect=error):
                with self.assertRaisesRegex(updater.UpdateError, message):
                    updater.check_release(current)

    def test_download_checksum_and_short_download(self):
        import io
        archive = self.package()
        release = updater.release_from_json(self.release_data(archive), updater.read_version(self.target))
        data = archive.read_bytes()
        with patch.object(updater, "open_url", return_value=io.BytesIO(data)):
            downloaded = updater.download_release(release, self.target)
        self.assertEqual(downloaded.read_bytes(), data)
        for corrupt in (data[:-1], b"x" * len(data), data + b"x"):
            with patch.object(updater, "open_url", return_value=io.BytesIO(corrupt)):
                with self.assertRaises(updater.UpdateError):
                    updater.download_release(release, self.target)
        self.assertEqual(len(list(updater.state_path(self.target).glob("download-*.zip"))), 1)

    def test_refuses_path_traversal_and_duplicate_names(self):
        for name in ("../escape.txt", "configuracoes.json", "APP.PY"):
            archive = self.package()
            with zipfile.ZipFile(archive, "a") as package:
                package.writestr(name, b"malicious")
            with self.assertRaises(updater.UpdateError):
                updater.install_package(archive, self.target, "7.1.1", "calavort/super-captura")
            self.assert_personal_unchanged()
            self.assertEqual(updater.read_version(self.target)["version"], "7.1.0")

    def test_refuses_file_hash_corruption(self):
        archive = self.package()
        modified = self.base / "corrompido.zip"
        with zipfile.ZipFile(archive) as source, zipfile.ZipFile(modified, "w") as target:
            for name in source.namelist():
                target.writestr(name, b"# alterado" if name == "app.py" else source.read(name))
        with self.assertRaises(updater.UpdateError):
            updater.install_package(modified, self.target, "7.1.1", "calavort/super-captura")
        self.assert_personal_unchanged()

    def test_changed_dependencies_require_manual_install(self):
        (self.source / "requirements.txt").write_text("PySide6>=99\n", encoding="utf-8")
        with self.assertRaisesRegex(updater.UpdateError, "bibliotecas"):
            updater.install_package(self.package(), self.target, "7.1.1", "calavort/super-captura")
        self.assertEqual(updater.read_version(self.target)["version"], "7.1.0")

    def test_failed_replacement_rolls_back_every_file(self):
        archive = self.package()
        originals = {name: (self.target / name).read_bytes() for name in updater.APP_FILES}
        replace = os.replace

        def fail_one(source, destination):
            if Path(destination) == self.target / "atualizador_ui.py":
                raise PermissionError("arquivo bloqueado")
            return replace(source, destination)

        with patch.object(updater.os, "replace", side_effect=fail_one):
            with self.assertRaises(PermissionError):
                updater.install_package(archive, self.target, "7.1.1", "calavort/super-captura")
        for name, data in originals.items():
            self.assertEqual((self.target / name).read_bytes(), data)
        self.assertFalse((updater.state_path(self.target) / "transacao.json").exists())
        self.assert_personal_unchanged()

    @unittest.skipUnless(sys.platform == "win32", "Windows process locking")
    def test_multiple_apps_and_exclusive_update_reservation(self):
        first = updater.AppInstance(self.target)
        second = updater.AppInstance(self.target)
        third = updater.AppInstance(self.target)
        installer = updater.InstanceLock(self.target)
        try:
            self.assertTrue(first.acquire())
            self.assertTrue(second.acquire())
            self.assertEqual(updater.running_instances(self.target), 2)
            self.assertFalse(installer.acquire())
            self.assertFalse(first.reserve_update())
            second.release()
            self.assertFalse(installer.acquire())
            self.assertTrue(first.reserve_update())
            self.assertFalse(third.acquire())
            first.cancel_update()
            self.assertTrue(third.acquire())
            first.release()
            third.release()
            self.assertTrue(installer.acquire())
            self.assertFalse(second.acquire())
        finally:
            for lock in (first, second, third, installer):
                lock.release()

    @unittest.skipUnless(sys.platform == "win32", "Windows process locking")
    def test_crashed_app_does_not_leave_a_false_live_instance(self):
        script = (
            "import sys; from pathlib import Path; from atualizador import AppInstance; "
            "instance=AppInstance(Path(sys.argv[1])); assert instance.acquire(); "
            "print('ready',flush=True); sys.stdin.read()"
        )
        process = subprocess.Popen([sys.executable, "-c", script, str(self.target)],
                                   cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            self.assertEqual(process.stdout.readline().strip(), b"ready")
            self.assertEqual(updater.running_instances(self.target), 1)
            process.terminate()
            process.wait(timeout=10)
            self.assertEqual(updater.running_instances(self.target), 0)
            installer = updater.InstanceLock(self.target)
            self.assertTrue(installer.acquire())
            installer.release()
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            process.stdin.close()
            process.stdout.close()

    @unittest.skipUnless(sys.platform == "win32", "Windows process locking")
    def test_real_helper_waits_for_app_and_restarts_new_version(self):
        import shutil
        # A harmless app stub records the restarted version instead of opening a window.
        (self.source / "app.py").write_text(
            "from pathlib import Path\n"
            "root = Path(__file__).resolve().parent\n"
            "(root / 'reiniciado.txt').write_text('7.1.1')\n", encoding="utf-8")
        archive = build_package(self.source, "7.1.1")
        state = updater.state_path(self.target)
        local_archive = state / "download-teste.zip"
        shutil.copy2(archive, local_archive)
        shutil.copy2(ROOT / "atualizador.py", self.target / "atualizador.py")
        release = updater.Release("7.1.1", "calavort/super-captura", "", updater.sha256(local_archive), local_archive.stat().st_size)
        lock = updater.AppInstance(self.target)
        self.assertTrue(lock.acquire())
        second_lock = updater.AppInstance(self.target)
        self.assertTrue(second_lock.acquire())
        process = updater.start_installer(updater.prepare_installer(local_archive, self.target, release))
        try:
            deadline = time.monotonic() + 10
            while not (state / "instalador-pronto").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue((state / "instalador-pronto").exists())
            self.assertEqual(updater.read_version(self.target)["version"], "7.1.0")
            lock.release()
            time.sleep(.3)
            self.assertIsNone(process.poll())
            self.assertEqual(updater.read_version(self.target)["version"], "7.1.0")
            second_lock.release()
            self.assertEqual(process.wait(timeout=20), 0)
            deadline = time.monotonic() + 10
            while not (self.target / "reiniciado.txt").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual((self.target / "reiniciado.txt").read_text(), "7.1.1")
            self.assertTrue(json.loads((state / "resultado.json").read_text())["ok"])
            self.assert_personal_unchanged()
        finally:
            lock.release()
            second_lock.release()
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
