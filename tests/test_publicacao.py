import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ferramentas"))

import publicar_release as publisher
from atualizacao.atualizador import APP_ID, UpdateError, sha256, write_json


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        write_json(self.root / "versao.json", {"app_id": APP_ID, "version": "7.1.0", "repository": "calavort/super-captura"})
        self.archive = self.root / "SuperCaptura-7.1.0.zip"
        self.archive.write_bytes(b"pacote de teste")
        self.checksum = self.archive.with_suffix(".zip.sha256")
        self.checksum.write_text(sha256(self.archive), encoding="ascii")
        self.calls = []

    def tearDown(self):
        self.temporary.cleanup()

    def api(self, token, url, method="GET", data=None, binary=False):
        self.calls.append((url, method, data))
        if url.endswith("/releases/latest"):
            raise urllib.error.HTTPError(url, 404, "not found", {}, None)
        if url.endswith("/releases") and method == "POST":
            return {"id": 123, "upload_url": "https://uploads.github.com/repos/calavort/super-captura/releases/123/assets{?name,label}"}
        if "uploads.github.com" in url:
            import hashlib
            return {"size": len(data), "digest": "sha256:" + hashlib.sha256(data).hexdigest()}
        if method == "PATCH":
            return {"html_url": "https://github.com/calavort/super-captura/releases/tag/v7.1.0"}
        return {"private": False, "default_branch": "main"}

    def test_release_published_only_after_both_verified_uploads(self):
        with patch.object(publisher, "github_token", return_value="test"), patch.object(publisher, "api", side_effect=self.api):
            url = publisher.publish_package(self.root, self.archive)
        self.assertTrue(url.endswith("v7.1.0"))
        creation = next(call for call in self.calls if call[1] == "POST" and call[0].endswith("/releases"))
        self.assertTrue(creation[2]["draft"])
        self.assertEqual(sum("uploads.github.com" in call[0] for call in self.calls), 2)
        self.assertEqual(self.calls[-1][1], "PATCH")
        self.assertFalse(self.calls[-1][2]["draft"])

    def test_failed_upload_is_never_published(self):
        def fail_upload(token, url, method="GET", data=None, binary=False):
            if "uploads.github.com" in url:
                raise OSError("upload interrompido")
            return self.api(token, url, method, data, binary)
        with patch.object(publisher, "github_token", return_value="test"), patch.object(publisher, "api", side_effect=fail_upload):
            with self.assertRaises(OSError):
                publisher.publish_package(self.root, self.archive)
        self.assertFalse(any(call[1] == "PATCH" for call in self.calls))

    def test_existing_or_older_version_is_not_republished(self):
        def latest(token, url, method="GET", data=None, binary=False):
            if url.endswith("/releases/latest"):
                return {"tag_name": "v7.1.0"}
            return self.api(token, url, method, data, binary)
        with patch.object(publisher, "github_token", return_value="test"), patch.object(publisher, "api", side_effect=latest):
            with self.assertRaises(UpdateError):
                publisher.publish_package(self.root, self.archive)
        self.assertFalse(any(call[1] == "POST" for call in self.calls))


if __name__ == "__main__":
    unittest.main()
