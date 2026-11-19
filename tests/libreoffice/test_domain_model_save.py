"""Run the workbook's real Basic save action in LibreOffice, in scratch folders.

Only message-box answers (and one injected filesystem failure) are automated in
scratch workbook copies. The production macros and reference files stay intact.
Run: python3 -m unittest discover -s tests/libreoffice -v
"""
import hashlib
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODULE = 'Basic/Standard/Module1.xml'
TEST_GLOBALS = '''
Global SaveTestReview As Integer
Global SaveTestOverwrite As Integer
Global SaveTestFailCommit As Boolean
Global SaveTestLog As String
'''
TEST_HELPERS = '''
Function SaveTestMessage(prompt As String, Optional buttons As Variant, Optional title As Variant) As Integer
    SaveTestLog = SaveTestLog & CStr(title) & ": " & prompt & Chr(10)
    If CStr(title) = "Review DomainModel before saving" Then
        SaveTestMessage = SaveTestReview
    ElseIf CStr(title) = "Confirm overwrite" Then
        SaveTestMessage = SaveTestOverwrite
    Else
        SaveTestMessage = 1
    End If
End Function

Function SaveTestRun(review As Integer, overwrite As Integer, failCommit As Boolean) As String
    SaveTestReview = review
    SaveTestOverwrite = overwrite
    SaveTestFailCommit = failCommit
    SaveTestLog = ""
    SaveDomainModel
    SaveTestRun = SaveTestLog
End Function

Function SaveTestLegacy() As String
    SaveTestLog = ""
    ExportYAML
    SaveTestLegacy = SaveTestLog
End Function
'''


def safe_id(label):
    return ''.join(ch if ch in 'abcdefghijklmnopqrstuvwxyz0123456789_' else '_' if ch in ' -' else ''
                   for ch in label.strip(' ').lower())


@unittest.skipUnless(shutil.which('soffice') and importlib.util.find_spec('uno'), 'LibreOffice and Python UNO required')
class SaveDomainModel(unittest.TestCase):
    maxDiff = None
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'domains'))
        import ods_export
        cls.exporter = ods_export
        cls.office = ods_export.office()
        cls.session = cls.office.__enter__()
        cls.original_hashes = {p: hashlib.sha256(p.read_bytes()).digest() for p in (ods_export.MACRO_DOC, ods_export.TEMPLATE)}

    @classmethod
    def tearDownClass(cls):
        cls.office.__exit__(None, None, None)
        for path, digest in cls.original_hashes.items():
            assert hashlib.sha256(path.read_bytes()).digest() == digest, path

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='save model é ', dir=self.session.work))
        self.domains = self.work / 'domains'
        self.domains.mkdir()
        self.source = self.domains / 'create_custom_domain_model.ods'
        self.template = self.domains / 'domain_model_template.ods'
        shutil.copy2(self.exporter.MACRO_DOC, self.source)
        shutil.copy2(self.exporter.TEMPLATE, self.template)
        with ZipFile(self.source) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        raw = next(data.decode() for info, data in entries if info.filename == MODULE)
        code = ''.join(ET.fromstring(raw).itertext())
        code = code.replace('Option Explicit', 'Option Explicit\n' + TEST_GLOBALS, 1)
        code = code.replace('MsgBox', 'SaveTestMessage')
        marker = '    fileAccess.move(stageYaml, fileUrl)'
        self.assertEqual(code.count(marker), 1)
        code = code.replace(marker, '    If SaveTestFailCommit Then Err.Raise 1001, "Test", "Injected commit failure"\n' + marker)
        code += TEST_HELPERS
        start = raw.index('>', raw.index('<script:module')) + 1
        updated = (raw[:start] + escape(code) + raw[raw.rindex('</script:module>'):]).encode()
        with ZipFile(self.source, 'w') as archive:
            for info, data in entries:
                archive.writestr(info, updated if info.filename == MODULE else data)
        self.doc = self.exporter.load(self.session, self.source, MacroExecutionMode=4)
        self.provider = self.doc.getScriptProvider()
        self.sheet = self.doc.Sheets.getByName('DomainModel')
        self.fixture()

    def tearDown(self):
        self.doc.close(True)
        shutil.rmtree(self.work)

    def macro(self, name, *args):
        script = self.provider.getScript(f'vnd.sun.star.script:Standard.Module1.{name}?language=Basic&location=document')
        return script.invoke(args, (), ())[0]

    def fixture(self, name='Save Study', prototypes=True):
        self.model = {
            'schema_version': '1.0', 'id': safe_id(name), 'name': name,
            'description': 'A complete model: "quoted", café, and \\ paths.\tAligned\nSecond line.',
            'notes': '  Model source\nDOI: example\toptional notes  ',
            'dimensions': [
                {'id': 'valence', 'name': 'Valence', 'definition': 'Pleasantness: "low" to high.\nDefinition\tcontinued.',
                 'notes': 'Dimension source é', 'min': -1, 'max': 1, 'circular': False},
                {'id': 'angle', 'name': 'Angle', 'definition': 'A circular quality dimension.',
                 'notes': '  Notes with a tab\tand spaces  ', 'min': 0, 'max': 360, 'circular': True},
            ],
            'emotions': [
                {'id': 'joy', 'name': 'Joy', 'definition': 'A "joyful" state.\nMore\tdetail.',
                 'notes': 'Prototype source é', 'coordinates': {'valence': 0.123456789012345, 'angle': 1e-200}},
                {'id': 'sadness', 'name': 'Sadness', 'definition': 'A second definition.',
                 'notes': '  A second source\ncontinued\tnote  ', 'coordinates': {'valence': -1, 'angle': 0}},
            ] if prototypes else [],
        }
        sh = self.sheet
        for address in ('A10:M29', 'D32:L32', 'A34:M63'):
            sh.getCellRangeByName(address).clearContents(23)
        sh.getCellRangeByName('B4').String = '  ' + name + '  '
        sh.getCellRangeByName('B5').String = self.model['description']
        sh.getCellRangeByName('B6').String = self.model['notes']
        for i, dim in enumerate(self.model['dimensions']):
            for c, key in enumerate(('id', 'name', 'definition')):
                sh.getCellByPosition(c, 9 + i).String = '  ' + dim[key] + '  '
            sh.getCellByPosition(3, 9 + i).Value = dim['min']
            sh.getCellByPosition(4, 9 + i).Value = dim['max']
            sh.getCellByPosition(5, 9 + i).String = 'Yes' if dim['circular'] else 'No'
            sh.getCellByPosition(6, 9 + i).String = dim['notes']
            sh.getCellByPosition(3 + i, 31).String = dim['name']
        for j, emotion in enumerate(self.model['emotions']):
            for c, key in enumerate(('id', 'name', 'definition')):
                sh.getCellByPosition(c, 33 + j).String = '  ' + emotion[key] + '  '
            sh.getCellByPosition(12, 33 + j).String = emotion['notes']
            for i, dim in enumerate(self.model['dimensions']):
                sh.getCellByPosition(3 + i, 33 + j).Value = emotion['coordinates'][dim['id']]
        self.folder = self.domains / self.model['id']
        self.yaml = self.folder / (self.model['id'] + '.yaml')
        self.ods = self.folder / (self.model['id'] + '.ods')

    def save(self, review=6, overwrite=6, fail_commit=False):
        before = {name: self.doc.Sheets.getByName(name).getCellRangeByName('A1:M64').getDataArray()
                  for name in ('Main', 'DomainModel')}
        result = self.macro('SaveTestRun', review, overwrite, fail_commit)
        self.assertEqual(tuple(self.doc.Sheets.getElementNames()), ('Main', 'DomainModel'))
        for name, values in before.items():
            self.assertEqual(self.doc.Sheets.getByName(name).getCellRangeByName('A1:M64').getDataArray(), values)
        self.assertEqual(self.doc.CurrentController.ActiveSheet.Name, 'DomainModel')
        return result

    def assert_pair(self):
        self.assertTrue(self.folder.is_dir())
        self.assertEqual(yaml.safe_load(self.yaml.read_text()), self.model)
        with ZipFile(self.ods) as archive:
            self.assertIsNone(archive.testzip())
            self.assertFalse(any(name.startswith('Basic/') for name in archive.namelist()))
        loaded = self.exporter.load(self.session, self.ods, ReadOnly=True)
        try:
            self.assertEqual(tuple(loaded.Sheets.getElementNames()), ('DomainModel',))
            sh = loaded.Sheets.getByName('DomainModel')
            read = {'schema_version': '1.0', 'id': safe_id(sh.getCellRangeByName('B4').String),
                    'name': sh.getCellRangeByName('B4').String, 'description': sh.getCellRangeByName('B5').String,
                    'notes': sh.getCellRangeByName('B6').String, 'dimensions': [], 'emotions': []}
            for row in range(9, 29):
                if not sh.getCellByPosition(1, row).String:
                    break
                read['dimensions'].append({
                    'id': sh.getCellByPosition(0, row).String, 'name': sh.getCellByPosition(1, row).String,
                    'definition': sh.getCellByPosition(2, row).String, 'min': sh.getCellByPosition(3, row).Value,
                    'max': sh.getCellByPosition(4, row).Value, 'circular': sh.getCellByPosition(5, row).String == 'yes',
                    'notes': sh.getCellByPosition(6, row).String})
            for row in range(33, 63):
                if not sh.getCellByPosition(1, row).String:
                    break
                read['emotions'].append({
                    'id': sh.getCellByPosition(0, row).String, 'name': sh.getCellByPosition(1, row).String,
                    'definition': sh.getCellByPosition(2, row).String, 'notes': sh.getCellByPosition(12, row).String,
                    'coordinates': {dim['id']: sh.getCellByPosition(3 + i, row).Value
                                    for i, dim in enumerate(read['dimensions'])}})
            self.assertEqual(read, self.model)
        finally:
            loaded.close(True)
        # Re-export the reopened single-sheet ODS using the independent Python port.
        text, errors = self.exporter.export_yaml(self.session, self.macro, self.ods)
        self.assertEqual(errors, [])
        self.assertEqual(text, self.yaml.read_text())
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [self.ods.name, self.yaml.name])

    def test_create_folder_save_and_reopen_matching_pair(self):
        self.assertFalse(self.folder.exists())
        log = self.save()
        self.assertIn('Review DomainModel before saving', log)
        self.assertIn('Save complete', log)
        self.assertNotIn('Confirm overwrite', log)
        self.assert_pair()

    def test_review_can_cancel_without_writing(self):
        self.assertNotIn('Save complete', self.save(review=7))
        self.assertFalse(self.folder.exists())

    def test_overwrite_requires_confirmation_for_either_file(self):
        self.folder.mkdir()
        self.yaml.write_text('existing YAML')
        self.ods.write_bytes(b'existing ODS')
        log = self.save(overwrite=7)
        self.assertIn('Confirm overwrite', log)
        self.assertEqual(self.yaml.read_text(), 'existing YAML')
        self.assertEqual(self.ods.read_bytes(), b'existing ODS')
        self.ods.unlink()
        self.assertIn('Confirm overwrite', self.save(overwrite=7))
        self.assertFalse(self.ods.exists())

    def test_confirmed_overwrite_replaces_both_files_without_trailing_yaml(self):
        self.assertIn('Save complete', self.save())
        self.model['description'] = 'Short'
        self.model['notes'] = ''
        self.sheet.getCellRangeByName('B5').String = 'Short'
        self.sheet.getCellRangeByName('B6').String = ''
        log = self.save()
        self.assertIn('Confirm overwrite', log)
        self.assertIn('Save complete', log)
        self.assert_pair()

    def test_validation_rejects_invalid_or_unexported_data(self):
        for kind in ('definition', 'coordinate', 'gap', 'extra_coordinate', 'precision'):
            with self.subTest(kind=kind):
                self.fixture()
                if kind == 'definition':
                    self.sheet.getCellByPosition(2, 9).String = ''
                elif kind == 'coordinate':
                    self.sheet.getCellByPosition(3, 33).Value = 100
                elif kind == 'gap':
                    self.sheet.getCellByPosition(1, 34).String = ''
                elif kind == 'extra_coordinate':
                    self.sheet.getCellByPosition(5, 33).Value = 0.5
                else:
                    self.sheet.getCellByPosition(3, 33).Value = 0.12345678901234566
                self.assertNotIn('Save complete', self.save())
                self.assertFalse(self.folder.exists())

    def test_missing_template_leaves_existing_files_unchanged(self):
        self.folder.mkdir()
        self.yaml.write_text('existing YAML')
        self.ods.write_bytes(b'existing ODS')
        self.template.unlink()
        self.assertIn('Missing template', self.save())
        self.assertEqual(self.yaml.read_text(), 'existing YAML')
        self.assertEqual(self.ods.read_bytes(), b'existing ODS')

    def test_failed_pair_commit_restores_previous_files(self):
        self.assertIn('Save complete', self.save())
        previous = (self.yaml.read_bytes(), self.ods.read_bytes())
        self.sheet.getCellRangeByName('B5').String = 'Changed data'
        log = self.save(fail_commit=True)
        self.assertIn('Save error', log)
        self.assertEqual((self.yaml.read_bytes(), self.ods.read_bytes()), previous)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [self.ods.name, self.yaml.name])

    def test_zero_prototypes_and_legacy_entry_point(self):
        self.fixture('No prototypes', prototypes=False)
        self.assertIn('Save complete', self.save())
        self.assert_pair()
        self.assertIn('Save complete', self.macro('SaveTestLegacy'))
        self.assert_pair()


if __name__ == '__main__':
    unittest.main()
