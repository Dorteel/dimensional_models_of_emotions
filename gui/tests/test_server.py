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
from ontology_service import find_ontologies  # noqa: E402


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

    def test_ontology_folder_and_domain_source(self):
        status, _, body = get(self.base, "/api/ontologies")
        data = json.loads(body)
        owl_dir = server.resolve_owl_dir()
        # ontology/ is preferred; owl/ is used only while ontology/ has no .owl files.
        expected = next(c for c in server.OWL_DIR_CANDIDATES if find_ontologies(c)) \
            if any(find_ontologies(c) for c in server.OWL_DIR_CANDIDATES) else server.OWL_DIR_CANDIDATES[0]
        self.assertEqual(owl_dir, expected)
        self.assertEqual(Path(data["directory"]), owl_dir)
        self.assertEqual(data["fallback"], owl_dir != server.OWL_DIR_CANDIDATES[0])
        self.assertEqual(data["domain_source"], "emotional_ontology_populated.owl")
        self.assertIn(data["domain_source"], [f["name"] for f in data["files"]])

    def test_domains_endpoint_uses_sparql_on_the_populated_file(self):
        status, _, body = get(self.base, "/api/domains")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["meta"]["file"], server.DOMAIN_SOURCE)
        self.assertTrue(data["meta"]["parser"].startswith("rdflib"))
        self.assertTrue(all(q in server.QUERIES.names() for q in data["meta"]["queries"]))
        self.assertEqual(len(data["domains"]), 4)

    def test_named_queries_are_listed_and_runnable(self):
        status, _, body = get(self.base, "/api/queries")
        listed = json.loads(body)["queries"]
        self.assertEqual(status, 200)
        self.assertEqual([q["name"] for q in listed], server.QUERIES.names())
        self.assertTrue(all(q["text"] and q["description"] for q in listed))
        status, _, body = get(self.base, "/api/sparql/domains/coordinates")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["columns"], ["prototype", "point", "coordinate", "dimension", "lexical", "datatype"])
        self.assertEqual(len(data["rows"]), 80)

    def test_no_user_supplied_sparql(self):
        for path in ("/api/sparql/SELECT%20%3Fs%20WHERE%20%7B%3Fs%20%3Fp%20%3Fo%7D", "/api/sparql/../server",
                     "/api/sparql/nonexistent", "/api/sparql?query=SELECT%20*%20WHERE%20%7B%3Fs%20%3Fp%20%3Fo%7D"):
            self.assertEqual(get(self.base, path)[0], 404, path)

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
