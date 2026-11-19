"""End-to-end test in headless Chrome/Chromium.

Starts the server, opens the dashboard with ?selftest=1 and reads the results of
web/js/selftest.js, which drives the real UI (clicks, wheel zoom, drag-pan, node
drag, tree navigation, inspector links, focus, filters, search) and checks it
against the ontology data. Skipped if no Chrome/Chromium is installed; set
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

import server  # noqa: E402
from owl_loader import find_ontologies  # noqa: E402

CHROME = os.environ.get("CHROME") or next(
    (shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(b)),
    None)


@unittest.skipUnless(CHROME, "Chrome/Chromium not found (set CHROME=...)")
class BrowserSelfTest(unittest.TestCase):
    def test_dashboard_in_headless_browser(self):
        for path in find_ontologies(server.resolve_owl_dir()):
            with self.subTest(file=path.name):
                print(f"\n  {path.name}")
                self.run_selftest(path.name)

    def run_selftest(self, file_name):
        httpd = server.make_server(port=0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}/?selftest=1&file={file_name}"
        profile = tempfile.mkdtemp(prefix="gui_selftest_chrome_")
        try:
            proc = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                 f"--user-data-dir={profile}", "--window-size=1500,950", "--virtual-time-budget=60000",
                 "--dump-dom", url],
                capture_output=True, text=True, timeout=180)
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
        self.assertGreaterEqual(result["passed"], 25)


if __name__ == "__main__":
    unittest.main()
