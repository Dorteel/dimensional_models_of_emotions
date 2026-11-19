"""Open dimension tables in real LibreOffice and verify every displayed value."""

import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from test_dimension_tables import read_ods


@unittest.skipUnless(shutil.which("soffice") and importlib.util.find_spec("uno"),
                     "LibreOffice and Python UNO required")
class DimensionTablesLibreOffice(unittest.TestCase):
    def test_both_spreadsheets_open_with_exact_values_and_only_one_sheet(self):
        sys.path.insert(0, str(ROOT / "domains"))
        import ods_export

        with ods_export.office() as session:
            for filename in ("dimension_catalogue.ods", "dimension_dictionary.ods"):
                with self.subTest(file=filename):
                    path = ROOT / "dimensions" / filename
                    before = hashlib.sha256(path.read_bytes()).digest()
                    expected = read_ods(path)
                    document = ods_export.load(session, path, ReadOnly=True)
                    self.assertIsNotNone(document)
                    try:
                        self.assertEqual(tuple(document.Sheets.getElementNames()), tuple(expected))
                        for name, rows in expected.items():
                            sheet = document.Sheets.getByName(name)
                            actual = sheet.getCellRangeByPosition(0, 0, len(rows[0]) - 1, len(rows) - 1).getDataArray()
                            self.assertEqual(actual, tuple(tuple(row) for row in rows))
                    finally:
                        document.close(True)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), before)


if __name__ == "__main__":
    unittest.main()
