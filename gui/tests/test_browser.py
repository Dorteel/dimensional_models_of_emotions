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
import xml.etree.ElementTree as ET
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
        expected = independent_domains(source)
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
        self.assertGreaterEqual(result["passed"], 50)
        return result.get("domainExtraction")


def independent_domains(path):
    """Domains, dimensions and raw coordinate strings read with ElementTree (no gui code involved)."""
    rdf = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
    root = ET.parse(path).getroot()
    base = root.get("{http://www.w3.org/XML/1998/namespace}base", "")
    full = lambda ref: base + ref if ref.startswith("#") else ref  # noqa: E731
    local = lambda tag: re.split(r"[#/}]", tag)[-1]  # noqa: E731
    nodes = {}
    for node in root:
        about = node.get(rdf + "about")
        if about is None:
            continue
        entry = nodes.setdefault(full(about), {"types": set(), "props": {}})
        for prop in node:
            res = prop.get(rdf + "resource")
            value = full(res) if res is not None else (prop.text or "")
            if prop.tag == rdf + "type":
                entry["types"].add(local(value))
            else:
                entry["props"].setdefault(local(prop.tag), []).append(value)
    get = lambda iri, p: nodes.get(iri, {"props": {}})["props"].get(p, [])  # noqa: E731
    domains = {}
    for iri, n in nodes.items():
        if "Domain" not in n["types"]:
            continue
        dims = list(dict.fromkeys(get(iri, "hasQualityDimension")))
        protos = list(dict.fromkeys(get(iri, "hasDomainPrototype") +
                                    [s for s in nodes if iri in get(s, "belongsToDomain")]))
        table = {}
        for p in protos:
            found = {}
            for point in get(p, "hasPoint"):
                for c in get(point, "hasCoordinate"):
                    for dim in get(c, "onQualityDimension"):
                        found.setdefault(dim, []).extend(get(c, "numericValue"))
            table[p] = {dim: (found[dim][0] if len(found.get(dim, [])) == 1 else
                              " | ".join(found[dim]) if found.get(dim) else None) for dim in dims}
        domains[iri] = {"label": (get(iri, "label") or [iri])[0], "dimensions": dims, "prototypes": table}
    return domains


if __name__ == "__main__":
    unittest.main()
