"""Dimension vocabulary coverage, provenance, identity, and reproducibility."""

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dimensions import build_dimension_tables as builder


def paragraph_text(element):
    text = element.text or ""
    for child in element:
        if child.tag == builder.tag("text", "s"):
            text += " " * int(child.get(builder.tag("text", "c"), "1"))
        elif child.tag == builder.tag("text", "tab"):
            text += "\t"
        elif child.tag == builder.tag("text", "line-break"):
            text += "\n"
        else:
            text += paragraph_text(child)
        text += child.tail or ""
    return text


def read_ods(path):
    with ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise AssertionError("Corrupt ODS archive")
        document = ET.fromstring(archive.read("content.xml"))
    return {
        sheet.get(builder.tag("table", "name")): [
            ["\n".join(paragraph_text(p) for p in cell.findall(builder.tag("text", "p")))
             for cell in row.findall(builder.tag("table", "table-cell"))]
            for row in sheet.findall(builder.tag("table", "table-row"))
        ]
        for sheet in document.findall(f".//{builder.tag('table', 'table')}")
    }


class DimensionTables(unittest.TestCase):
    def test_official_inventory_and_alphabetical_order(self):
        catalogue = read_ods(ROOT / "dimensions/dimension_catalogue.ods")
        self.assertEqual(list(catalogue), ["Catalogue"])
        rows = catalogue["Catalogue"]
        self.assertEqual(rows[0], ["Dimension", "Dimension ID"])
        self.assertEqual(rows[1:], [[name, name] for name in
                                   ("arousal", "dominance", "intensity", "pleasure", "valence")])
        self.assertEqual({path.as_posix() for path, _ in builder.read_models()}, {
            f"domains/{name}/{name}.yaml" for name in ("circumplex", "pad", "plutchik_model", "vector_model")
        })

    def test_every_research_occurrence_and_its_exact_provenance_is_present(self):
        dictionary = read_ods(ROOT / "dimensions/dimension_dictionary.ods")
        self.assertEqual(list(dictionary), ["Dictionary"])
        rows = dictionary["Dictionary"]
        catalogue = read_ods(ROOT / "dimensions/dimension_catalogue.ods")["Catalogue"]
        self.assertEqual([r[0] for r in rows], [r[0] for r in catalogue])
        self.assertEqual(len(rows[0]), 9)  # Dimension + four model-specific pairs.
        occurrences = 0
        for source in sorted((ROOT / "domains").glob("*/*.yaml")):
            if source.parent.name == "examples":
                continue
            model = yaml.safe_load(source.read_text(encoding="utf-8"))
            column = rows[0].index(f"{model['id']} definition")
            self.assertEqual(rows[0][column + 1], f"{model['id']} source")
            for dimension in model["dimensions"]:
                occurrences += 1
                row_index = next(i for i, r in enumerate(catalogue) if r[1] == dimension["id"])
                definition, provenance = rows[row_index][column:column + 2]
                self.assertEqual(definition, "")  # All current research definitions are 'undefined'.
                self.assertIn(source.relative_to(ROOT).as_posix(), provenance)
                self.assertIn(f"Domain Model: {model['name']} (id: {model['id']})", provenance)
                self.assertIn(f"Dimension: {dimension['name']} (id: {dimension['id']})", provenance)
                self.assertIn("Dimension notes:\n" + dimension["notes"], provenance)
                self.assertIn("Domain Model notes:\n" + model["notes"], provenance)
        self.assertEqual(occurrences, 8)
        # Absent dimensions have empty definition AND source cells.
        for row in rows[1:]:
            self.assertTrue(all(row[i] == "" for i in range(1, len(row), 2)))
            self.assertEqual(sum(bool(row[i]) for i in range(2, len(row), 2)),
                             {"arousal": 3, "dominance": 1, "intensity": 1, "pleasure": 1, "valence": 2}[row[0]])

    def test_recursion_includes_incomplete_models_and_excludes_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("drafts/nested/incomplete.yml", "examples/example.yaml", "testingmodel.yaml"):
                path = root / "domains" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(yaml.safe_dump({
                    "schema_version": "1.0", "id": "incomplete", "name": "Incomplete",
                    "dimensions": [{"id": "unmeasured", "name": "Unmeasured", "definition": "undefined"}],
                    "emotions": [],
                }), encoding="utf-8")
            models = builder.read_models(root)
            self.assertEqual([path.as_posix() for path, _ in models], ["domains/drafts/nested/incomplete.yml"])
            self.assertEqual(builder.table_rows(models)[0][1:], [["Unmeasured", "unmeasured"]])

    def test_only_matching_ids_merge_and_different_definitions_are_retained(self):
        models = [
            (Path("domains/a/a.yaml"), {"id": "a", "name": "A", "dimensions": [
                {"id": "shared", "name": "First name", "definition": "  Exact definition\nwith\ttabs  ",
                 "notes": "  Source A\nDOI: example\tcontinued  "},
                {"id": "distinct_a", "name": "Same name", "definition": "First interpretation"},
            ]}),
            (Path("domains/b/b.yaml"), {"id": "b", "name": "B", "dimensions": [
                {"id": "shared", "name": "Alternative name", "definition": "Different interpretation",
                 "source": "Source B"},
                {"id": "distinct_b", "name": "Same name", "definition": "Second interpretation"},
            ]}),
        ]
        catalogue, dictionary = builder.table_rows(models)
        self.assertEqual({row[1] for row in catalogue[1:]}, {"shared", "distinct_a", "distinct_b"})
        self.assertEqual(sum(row[0] == "Same name" for row in catalogue[1:]), 2)
        row = dictionary[1]
        self.assertEqual(row[1], models[0][1]["dimensions"][0]["definition"])
        self.assertEqual(row[3], "Different interpretation")
        self.assertIn("Alternative name", row[4])
        self.assertIn("Source B", row[4])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dictionary.ods"
            builder.write_ods(ROOT / "emotions/emotion_dictionary.ods", "Dictionary", dictionary, output)
            self.assertEqual(read_ods(output)["Dictionary"], dictionary)

    def test_missing_definition_markers_become_blank(self):
        for value in (None, "", "   ", "undefined", " UNDEFINED ", "no known definitions"):
            with self.subTest(value=value):
                self.assertEqual(builder.definition_text({"definition": value}), "")
        self.assertEqual(builder.definition_text({"definition": "  A real definition.  "}), "  A real definition.  ")

    def test_rebuild_is_reproducible_and_does_not_modify_inputs(self):
        inputs = [*(ROOT / "domains").rglob("*.yaml"), *(ROOT / "domains").rglob("*.yml"),
                  *(ROOT / "domains").rglob("*.ods"), *(ROOT / "emotions").glob("*.ods")]
        before = {p: hashlib.sha256(p.read_bytes()).digest() for p in inputs}
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            builder.build(output=first)
            builder.build(output=second)
            for filename in ("dimension_catalogue.ods", "dimension_dictionary.ods"):
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
                self.assertEqual((first / filename).read_bytes(), (ROOT / "dimensions" / filename).read_bytes())
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).digest() for p in inputs})


if __name__ == "__main__":
    unittest.main()
