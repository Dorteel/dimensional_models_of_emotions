"""Create Domain Model backend: validation, catalogue reading, and saving with the builder macros.

Saving tests write only into temporary folders. The real domains/ folder, the builder workbook and the
template are checked to be unchanged. Saved pairs are checked independently: the YAML is parsed, the ODS is
read cell by cell (stored values), and the ODS is re-exported with the existing CLI
`python3 domains/ods_export.py --export`, which must reproduce the saved YAML byte for byte.
"""

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
REPO = GUI.parent
sys.path.insert(0, str(GUI))

import yaml  # noqa: E402

from model_builder import save as S  # noqa: E402
from model_builder.catalogue import CATALOGUE, DICTIONARY, load_catalogue  # noqa: E402
from model_builder.ods_reader import read_sheet, sheet_names  # noqa: E402
from model_builder.validation import representable, safe_id, validate  # noqa: E402

CAN_SAVE = S.uno_python() is not None and shutil.which("soffice") is not None


def tree_hashes(folder: Path) -> dict:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def form(**over):
    base = {
        "name": "Unit Test Model", "description": 'Quotes "q", backslash \\ and é.\nSecond line\twith tab.',
        "notes": "  leading/trailing spaces kept  ",
        "dimensions": [
            {"name": "Valence", "definition": "Pleasantness.", "notes": "dim note", "min": "-1", "max": "1", "circular": "no"},
            {"name": "Hue Angle", "definition": "A circular dimension.", "notes": "", "min": 0, "max": 360, "circular": "yes"},
        ],
        "emotions": [
            {"name": "Joy", "concept_id": "joy", "definition": "A joyful state.", "notes": "n",
             "coordinates": {"0": "0.123456789012345", "1": "1e-200"}},
            {"name": "Brand-New Feeling", "concept_id": "", "definition": "Defined here.", "notes": "",
             "coordinates": {"0": -1, "1": 360}},
        ],
    }
    base.update(over)
    return base


class Validation(unittest.TestCase):
    def fields(self, f):
        return {e["field"] for e in validate(f, {"joy"})["errors"]}

    def test_valid_model_normalises_to_the_yaml_schema(self):
        r = validate(form(), {"joy"})
        self.assertEqual(r["errors"], [])
        m = r["model"]
        self.assertEqual(list(m), ["schema_version", "id", "name", "description", "notes", "dimensions", "emotions"])
        self.assertEqual(m["id"], "unit_test_model")
        self.assertEqual([d["id"] for d in m["dimensions"]], ["valence", "hue_angle"])
        self.assertEqual([e["id"] for e in m["emotions"]], ["joy", "brand_new_feeling"])   # concept ID / SafeID
        self.assertEqual(m["emotions"][0]["coordinates"], {"valence": 0.123456789012345, "hue_angle": 1e-200})
        self.assertEqual(m["notes"], "  leading/trailing spaces kept  ")
        self.assertEqual([w["field"] for w in r["warnings"]], ["emotions.1.name"])         # new emotion

    def test_model_rules(self):
        self.assertIn("name", self.fields(form(name="   ")))
        self.assertIn("name", self.fields(form(name="!!!")))
        self.assertIn("dimensions", self.fields(form(dimensions=[], emotions=[])))
        self.assertIn("dimensions", self.fields(form(dimensions=[dict(form()["dimensions"][0], name=f"d{i}") for i in range(10)],
                                                     emotions=[])))

    def test_dimension_rules(self):
        d = form()["dimensions"]
        cases = {
            "dimensions.0.name": dict(d[0], name=""),
            "dimensions.0.definition": dict(d[0], definition="  "),
            "dimensions.0.min": dict(d[0], min="abc"),
            "dimensions.0.max": dict(d[0], min="1", max="1"),
            "dimensions.0.circular": dict(d[0], circular="maybe"),
        }
        for field, bad in cases.items():
            with self.subTest(field=field):
                self.assertIn(field, self.fields(form(dimensions=[bad, d[1]])))
        self.assertIn("dimensions.1.name", self.fields(form(dimensions=[d[0], dict(d[1], name="VALENCE")])))
        self.assertIn("dimensions.0.min", self.fields(form(dimensions=[dict(d[0], min=1 / 3), d[1]])))

    def test_emotion_rules(self):
        e = form()["emotions"]
        self.assertIn("emotions.0.definition", self.fields(form(emotions=[dict(e[0], definition="")])))
        self.assertIn("emotions.0.name", self.fields(form(emotions=[dict(e[0], concept_id="not_in_catalogue")])))
        self.assertIn("emotions.1.name", self.fields(form(emotions=[e[0], dict(e[0])])))
        self.assertIn("emotions.0.coordinates.0", self.fields(form(emotions=[dict(e[0], coordinates={"0": "2", "1": "1"})])))
        self.assertIn("emotions.0.coordinates.1", self.fields(form(emotions=[dict(e[0], coordinates={"0": "0"})])))
        self.assertIn("emotions.0.coordinates.0",
                      self.fields(form(emotions=[dict(e[0], coordinates={"0": "0.1234567890123456", "1": "1"})])))
        self.assertIn("emotions.0.coordinates", self.fields(form(emotions=[dict(e[0], coordinates={"0": 0, "1": 1, "5": 2})])))
        self.assertEqual(validate(form(emotions=[]), {"joy"})["errors"], [])               # prototypes are optional

    def test_safe_id_and_precision_mirrors(self):
        self.assertEqual(safe_id("  My Model-2 x "), "my_model_2_x")
        self.assertEqual(safe_id("Doubt/Confusion"), "doubtconfusion")
        self.assertEqual(safe_id("Émotion"), "motion")
        self.assertTrue(representable(0.123456789012345))
        self.assertFalse(representable(0.12345678901234566))
        self.assertTrue(representable(1e-200))


class Catalogue(unittest.TestCase):
    def test_reader_handles_repeats_and_whitespace(self):
        content = """<?xml version="1.0"?><office:document-content
          xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
          xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
          xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:spreadsheet>
          <table:table table:name="S"><table:table-row><table:table-cell><text:p>a<text:s text:c="2"/>b<text:tab/>c</text:p>
          <text:p>second</text:p></table:table-cell><table:table-cell table:number-columns-repeated="2"><text:p>x</text:p>
          </table:table-cell><table:table-cell office:value-type="float" office:value="0.123456789012345"><text:p>0.12</text:p>
          </table:table-cell><table:table-cell table:number-columns-repeated="1000"/></table:table-row>
          <table:table-row table:number-rows-repeated="2"><table:table-cell><text:p>r</text:p></table:table-cell></table:table-row>
          <table:table-row table:number-rows-repeated="100000"><table:table-cell/></table:table-row>
          </table:table></office:spreadsheet></office:body></office:document-content>"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.ods"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("content.xml", content)
            self.assertEqual(read_sheet(p, "S"), [["a  b\tc\nsecond", "x", "x", "0.12"], ["r"], ["r"]])
            self.assertEqual(read_sheet(p, "S", values=True)[0][3], "0.123456789012345")
            self.assertEqual(sheet_names(p), ["S"])

    def test_catalogue_matches_libreoffice_reading(self):
        data = load_catalogue()
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["soffice", f"-env:UserInstallation=file://{tmp}/p", "--headless", "--convert-to",
                            "csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,-1",
                            "--outdir", tmp, str(CATALOGUE), str(DICTIONARY)], capture_output=True, timeout=180, check=True)
            with open(Path(tmp) / f"{CATALOGUE.stem}-Catalogue.csv", encoding="utf-8", newline="") as h:
                cat = list(csv.reader(h))
            with open(Path(tmp) / f"{DICTIONARY.stem}-Dictionary.csv", encoding="utf-8", newline="") as h:
                dic = list(csv.reader(h))
        self.assertEqual([(e["name"], e["concept_id"]) for e in data["emotions"]], [tuple(r[:2]) for r in cat[1:]])
        by_name = {r[0]: r for r in dic[1:]}
        head = dic[0]
        for e in data["emotions"]:
            row = by_name.get(e["name"], [])
            expected = [(head[i][: -len(" definition")], row[i], row[i + 1]) for i in range(1, len(head) - 1, 2)
                        if row and row[i] != ""]
            self.assertEqual([(d["source"], d["text"], d["reference"]) for d in e["definitions"]], expected, e["name"])


@unittest.skipUnless(CAN_SAVE, "LibreOffice and a Python with the UNO bridge are required to save")
class Saving(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.protected_before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (S.BUILDER, S.TEMPLATE)}
        cls.domains_before = tree_hashes(REPO / "domains")

    @classmethod
    def tearDownClass(cls):
        for p, h in cls.protected_before.items():
            assert hashlib.sha256(p.read_bytes()).hexdigest() == h, p
        assert tree_hashes(REPO / "domains") == cls.domains_before, "the repository's domains/ folder changed"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="create_model_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def files(self, model_id="unit_test_model"):
        folder = self.tmp / model_id
        return folder, folder / f"{model_id}.yaml", folder / f"{model_id}.ods"

    def assert_equivalent_pair(self, expected, model_id="unit_test_model"):
        folder, y, o = self.files(model_id)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted([y.name, o.name]))
        loaded = yaml.safe_load(y.read_text(encoding="utf-8"))
        self.assertEqual(_floats(loaded), _floats(expected))
        # ODS: one DomainModel sheet, no macros, every field in the template's cells (numbers as stored values).
        self.assertEqual(sheet_names(o), ["DomainModel"])
        with zipfile.ZipFile(o) as z:
            self.assertFalse(any(n.startswith("Basic/") for n in z.namelist()))
        rows = read_sheet(o, "DomainModel", values=True)
        cell = lambda r, c: (rows[r] + [""] * 13)[c] if r < len(rows) else ""  # noqa: E731
        self.assertEqual((cell(3, 1), cell(4, 1), cell(5, 1)), (expected["name"], expected["description"], expected["notes"]))
        for i, d in enumerate(expected["dimensions"]):
            self.assertEqual([cell(9 + i, c) for c in range(7)],
                             [d["id"], d["name"], d["definition"], repr_num(d["min"]), repr_num(d["max"]),
                              "yes" if d["circular"] else "no", d["notes"]])
            self.assertEqual(cell(31, 3 + i), d["name"])
        for j, e in enumerate(expected["emotions"]):
            self.assertEqual([cell(33 + j, c) for c in range(3)] + [cell(33 + j, 12)],
                             [e["id"], e["name"], e["definition"], e["notes"]])
            self.assertEqual([float(cell(33 + j, 3 + i)) for i in range(len(expected["dimensions"]))],
                             [float(e["coordinates"][d["id"]]) for d in expected["dimensions"]])
        # Independent re-export with the existing exporter CLI must reproduce the YAML exactly.
        copy_dir = self.tmp / "_reexport"
        copy_dir.mkdir(exist_ok=True)
        copy = copy_dir / o.name
        shutil.copyfile(o, copy)
        proc = subprocess.run([S.uno_python(), str(REPO / "domains" / "ods_export.py"), "--export", str(copy)],
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual((copy_dir / y.name).read_text(encoding="utf-8"), y.read_text(encoding="utf-8"))
        shutil.rmtree(copy_dir)

    def test_save_creates_an_equivalent_yaml_ods_pair(self):
        out = S.save(form(), domains_dir=self.tmp)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["replaced"], [])
        expected = validate(form(), {"joy"})["model"]
        self.assertEqual(out["yaml_text"], self.files()[1].read_text(encoding="utf-8"))
        self.assert_equivalent_pair(expected)
        self.assertIn('"hue_angle": 1.0E-200', out["yaml_text"])          # the macro's YAMLNumber formatting

    def test_model_without_prototypes(self):
        out = S.save(form(emotions=[]), domains_dir=self.tmp)
        self.assertTrue(out["ok"], out)
        self.assertIn("emotions: []", out["yaml_text"])
        self.assert_equivalent_pair(validate(form(emotions=[]), {"joy"})["model"])

    def test_invalid_model_writes_nothing(self):
        out = S.save(form(name=""), domains_dir=self.tmp)
        self.assertFalse(out["ok"])
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_overwrite_needs_confirmation_and_replaces_both_files(self):
        self.assertTrue(S.save(form(), domains_dir=self.tmp)["ok"])
        _, y, o = self.files()
        before = (y.read_bytes(), o.read_bytes())
        changed = form(notes="second version")
        out = S.save(changed, domains_dir=self.tmp)
        self.assertTrue(out.get("needs_confirmation"))
        self.assertEqual((y.read_bytes(), o.read_bytes()), before)
        out = S.save(changed, overwrite=True, domains_dir=self.tmp)
        self.assertTrue(out["ok"], out)
        self.assertEqual(len(out["replaced"]), 2)
        self.assert_equivalent_pair(validate(changed, {"joy"})["model"])

    def test_failed_commit_restores_previous_pair(self):
        self.assertTrue(S.save(form(), domains_dir=self.tmp)["ok"])
        folder, y, o = self.files()
        before = (y.read_bytes(), o.read_bytes())
        out = S.save(form(notes="changed"), overwrite=True, domains_dir=self.tmp, _test_fail_commit=True)
        self.assertFalse(out["ok"])
        self.assertEqual((y.read_bytes(), o.read_bytes()), before)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted([y.name, o.name]))

    def test_failed_first_save_leaves_no_folder(self):
        out = S.save(form(), domains_dir=self.tmp, _test_fail_commit=True)
        self.assertFalse(out["ok"])
        self.assertFalse(self.files()[0].exists())

    def test_reserved_names_and_non_folder_conflicts_are_refused(self):
        for name in sorted(S.PROTECTED):
            with self.subTest(name=name):
                out = S.save(form(name=name), domains_dir=self.tmp)
                self.assertFalse(out["ok"])
                self.assertIn("name", {e["field"] for e in out["errors"]})
        (self.tmp / "unit_test_model").write_text("a file, not a folder")
        out = S.save(form(), overwrite=True, domains_dir=self.tmp)
        self.assertFalse(out["ok"])
        self.assertEqual((self.tmp / "unit_test_model").read_text(), "a file, not a folder")

    def test_only_the_model_folder_is_written(self):
        (self.tmp / "other").mkdir()
        (self.tmp / "other" / "other.yaml").write_text("untouched")
        before = tree_hashes(self.tmp)
        self.assertTrue(S.save(form(), domains_dir=self.tmp)["ok"])
        after = tree_hashes(self.tmp)
        self.assertEqual({k: v for k, v in after.items() if not k.startswith("unit_test_model/")}, before)


def repr_num(v):
    """ODS office:value text for a number as LibreOffice stores it."""
    v = float(v)
    return str(int(v)) if v.is_integer() else repr(v)


def _floats(x):
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict):
        return {k: _floats(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_floats(v) for v in x]
    return x


if __name__ == "__main__":
    unittest.main()
