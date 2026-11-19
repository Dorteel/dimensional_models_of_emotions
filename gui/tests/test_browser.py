"""End-to-end test in headless Chrome/Chromium.

Starts the server, opens the dashboard with ?selftest=1 and reads the results of
web/js/selftest.js, which drives the real UI (clicks, wheel zoom, drag-pan, node
drag, tree navigation, inspector links, focus, filters, search, and the Domain
Models tab) and checks it against the ontology data. The domains the Domain Models
tab received (via /api/domains, i.e. SPARQL) are compared with an independent
ElementTree reading of the OWL file. Skipped if no Chrome/Chromium is installed; set
CHROME=/path/to/browser to choose one.
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))

sys.path.insert(0, str(Path(__file__).resolve().parent))

import independent as ind  # noqa: E402
import yaml  # noqa: E402
from model_builder.ods_reader import read_sheet  # noqa: E402
from test_model_builder import _floats as floats, tree_hashes  # noqa: E402
import server  # noqa: E402
from ontology_service import find_ontologies  # noqa: E402

CHROME = os.environ.get("CHROME") or next(
    (shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(b)),
    None)


@unittest.skipUnless(CHROME, "Chrome/Chromium not found (set CHROME=...)")
class BrowserSelfTest(unittest.TestCase):
    def test_dashboard_in_headless_browser(self):
        owl_dir = server.resolve_owl_dir()
        extraction = None
        for path in find_ontologies(owl_dir):
            with self.subTest(file=path.name):
                print(f"\n  {path.name}")
                extraction = self.run_selftest(path.name)
        # Domain Models tab: what the browser extracted must equal an independent reading of the OWL file.
        source = owl_dir / server.DOMAIN_SOURCE
        self.assertTrue(source.exists(), f"{source} not found")
        self.assertIsNotNone(extraction, "Domain Models self-test returned no extraction")
        expected = ind.et_domains(source)
        got = {d["id"]: d for d in extraction["domains"]}
        self.assertEqual(set(got), set(expected), "Domain individuals differ")
        for iri, exp in expected.items():
            with self.subTest(domain=exp["label"]):
                self.assertEqual(got[iri]["label"], exp["label"])
                self.assertEqual(got[iri]["dimensions"], exp["dimensions"])
                self.assertEqual(got[iri]["prototypes"], exp["prototypes"])
        n = sum(len(v) for d in expected.values() for v in d["prototypes"].values())
        print(f"\n  Domain extraction matches {source.name}: {len(expected)} domains, "
              f"{sum(len(d['prototypes']) for d in expected.values())} prototypes, {n} coordinate cells")

    def test_create_domain_model_tab(self):
        """Fill and save the Create Domain Model form in the browser; the server saves to a scratch folder."""
        domains = Path(tempfile.mkdtemp(prefix="gui_create_domains_"))
        real_before = tree_hashes(GUI.parent / "domains")
        try:
            result = self.run_selftest(server.DOMAIN_SOURCE, create=True, domains_dir=domains, full=True)
            created = result["created"]
            self.assertIsNotNone(created, "Create Domain Model self-test returned nothing")
            folder = domains / "gui_selftest_model"
            files = sorted(p.name for p in folder.iterdir())
            self.assertEqual(files, ["gui_selftest_model.ods", "gui_selftest_model.yaml"])
            saved = (folder / "gui_selftest_model.yaml").read_text(encoding="utf-8")
            self.assertEqual(saved, created["saved"]["yaml_text"])
            self.assertEqual(floats(yaml.safe_load(saved)), floats(created["expected"]))
            self.assertEqual(read_sheet(folder / "gui_selftest_model.ods", "DomainModel")[3][1], "GUI Selftest Model")
            self.assertEqual(sorted(p.name for p in domains.iterdir()), ["gui_selftest_model"])
        finally:
            shutil.rmtree(domains, ignore_errors=True)
        self.assertEqual(tree_hashes(GUI.parent / "domains"), real_before, "the repository's domains/ folder changed")

    def run_selftest(self, file_name, create=False, domains_dir=None, full=False):
        httpd = server.make_server(port=0, domains_dir=domains_dir)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}/?selftest=1&file={file_name}" + ("&create=1" if create else "")
        profile = tempfile.mkdtemp(prefix="gui_selftest_chrome_")
        try:
            proc = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                 f"--user-data-dir={profile}", "--window-size=1500,950", "--virtual-time-budget=180000",
                 "--dump-dom", url],
                capture_output=True, text=True, timeout=300)
        finally:
            httpd.shutdown()
            httpd.server_close()
            shutil.rmtree(profile, ignore_errors=True)
        match = re.search(r'<pre id="selftest-result"[^>]*>(.*?)</pre>', proc.stdout, re.S)
        self.assertIsNotNone(match, "self-test did not report (page failed to load?)\n" + proc.stderr[-2000:])
        result = json.loads(html.unescape(match.group(1)))
        for c in result["checks"]:
            print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['name']}" + (f" — {c['detail'][:120]}" if c["detail"] else ""))
        failed = [c for c in result["checks"] if not c["ok"]]
        self.assertFalse(failed, json.dumps(failed, indent=1))
        self.assertGreaterEqual(result["passed"], 50)
        return result if full else result.get("domainExtraction")


if __name__ == "__main__":
    unittest.main()
