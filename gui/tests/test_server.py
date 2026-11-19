"""Tests for gui/server.py: static files, the read-only API and path restrictions."""

import hashlib
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
REPO = GUI.parent
sys.path.insert(0, str(GUI))

import server  # noqa: E402
from owl_loader import find_ontologies  # noqa: E402


def get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(port=0)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.files = find_ontologies(server.resolve_owl_dir())
        cls.hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.files}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_dashboard_is_served(self):
        status, ctype, body = get(self.base, "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b'src="js/main.js"', body)
        for asset in ("/js/main.js", "/css/style.css", "/js/components/graph-view.js"):
            self.assertEqual(get(self.base, asset)[0], 200, asset)

    def test_lists_ontology_files_from_disk(self):
        status, _, body = get(self.base, "/api/ontologies")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([f["name"] for f in data["files"]], [p.name for p in self.files])
        self.assertIn(data["default"], [p.name for p in self.files])

    def test_ontology_endpoint_reads_the_file(self):
        for p in self.files:
            status, _, body = get(self.base, f"/api/ontology?file={p.name}")
            data = json.loads(body)
            self.assertEqual(status, 200)
            self.assertEqual(data["meta"]["sha256"], self.hashes[p])
            self.assertTrue(data["entities"])

    def test_only_listed_files_are_reachable(self):
        for bad in ("../README.md", "/etc/passwd", "nonexistent.owl", ""):
            status, _, body = get(self.base, f"/api/ontology?file={bad}")
            self.assertEqual(status, 404, bad)
            self.assertIn("error", json.loads(body))
        status, _, _ = get(self.base, "/../server.py")
        self.assertEqual(status, 404)

    def test_ontology_files_unchanged(self):
        get(self.base, "/api/ontology?file=" + self.files[0].name)
        for p, h in self.hashes.items():
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), h)


if __name__ == "__main__":
    unittest.main()
