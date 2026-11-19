"""Keeps the GUI modular: generic components must not depend on the ontology code."""

import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web" / "js"
IMPORT = re.compile(r"""^\s*import\s.*?from\s+["']([^"']+)["']""", re.M)


def imports(path):
    return IMPORT.findall(path.read_text(encoding="utf-8"))


class Architecture(unittest.TestCase):
    def test_components_are_independent_of_ontology_and_api(self):
        for f in (WEB / "components").glob("*.js"):
            with self.subTest(file=f.name):
                for target in imports(f):
                    self.assertTrue(target.startswith("./"), f"{f.name} imports {target}")
                code = re.sub(r"//[^\n]*|/\*.*?\*/", "", f.read_text(encoding="utf-8"), flags=re.S)
                self.assertIsNone(re.search(r"\b(owl|rdfs?|ontology|subclass|individual)\b", code, re.I), f.name)

    def test_adapters_are_pure(self):
        for f in (WEB / "ontology").glob("*.js"):   # adapter.js (ontology tab), domains.js (domain tab)
            with self.subTest(file=f.name):
                text = f.read_text(encoding="utf-8")
                self.assertEqual(imports(f), [])
                self.assertNotIn("document.", text)
                self.assertNotIn("fetch(", text)

    def test_tabs_use_adapters_not_raw_ontology_json(self):
        # Tabs get ontology meaning only through the adapters (no OWL vocabulary in tab code).
        for f in (WEB / "tabs").glob("*.js"):
            with self.subTest(file=f.name):
                code = re.sub(r"//[^\n]*", "", f.read_text(encoding="utf-8"))
                self.assertIsNone(re.search(r"hasCoordinate|numericValue|hasQualityDimension|rdfs:|owl:", code), f.name)

    def test_only_api_module_fetches_data(self):
        for f in WEB.rglob("*.js"):
            if f.name == "api.js" or f.name.startswith("selftest"):   # self-tests fetch to cross-check the UI
                continue
            with self.subTest(file=f.name):
                self.assertFalse("fetch(" in f.read_text(encoding="utf-8"), f"{f.name} fetches data directly")

    def test_no_external_resources(self):
        for f in list((WEB.parent).rglob("*.html")) + list((WEB.parent).rglob("*.css")) + list(WEB.rglob("*.js")):
            with self.subTest(file=f.name):
                self.assertIsNone(re.search(r"""(src|href)=["']https?://|url\(["']?https?://|import\s.*https?://""",
                                            f.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
