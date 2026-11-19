"""Domain discovery and document-relative YAML export; no LibreOffice process needed."""
import contextlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ontology import populate_ontology as population


class DomainDiscovery(unittest.TestCase):
    def test_nested_models_and_legacy_root_yaml_are_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename, identifier in [('custom/custom.yaml', 'custom'), ('other/other.yml', 'other'),
                                         ('legacy.yaml', 'legacy'), ('examples/example/example.yaml', 'example'),
                                         ('drafts/research/research.yaml', 'draft')]:
                path = root / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(yaml.safe_dump({'name': identifier, 'dimensions': [], 'emotions': []}))
            with patch.object(population, 'DOMAINS_DIR', root):
                self.assertEqual({data['name'] for _, data in population.read_domains()}, {'custom', 'other', 'legacy'})
                # Named selection uses only the standard <name>/<name>.yaml layout.
                self.assertEqual(population.discover_domains(), {'custom': root / 'custom/custom.yaml'})
                # Drafts remain available by explicit choice, without promoting their status.
                self.assertEqual(population.read_domains([root / 'drafts/research/research.yaml'])[0][1]['name'], 'draft')

    def test_repository_models_and_examples_remain_distinct(self):
        models = population.read_domains()
        self.assertEqual({data['id'] for _, data in models}, {'circumplex', 'pad', 'plutchik_model', 'vector_model'})
        for path, data in models:
            self.assertEqual(path.parent.name, data['id'])
            self.assertTrue(path.with_suffix('.ods').is_file())
        examples = ROOT / 'domains/examples/yourdomainmodel'
        with self.assertRaisesRegex(ValueError, 'duplicate model identifier'):
            population.read_domains(sorted(examples.glob('*.yaml')))


@unittest.skipUnless(importlib.util.find_spec('uno'), 'LibreOffice Python UNO is required to import the exporter')
class ExportPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'domains'))
        import ods_export
        cls.exporter = ods_export

    def test_python_export_writes_beside_ods(self):
        exporter = self.exporter
        with tempfile.TemporaryDirectory(prefix='domain paths ') as directory:
            ods = Path(directory) / 'custom' / 'custom.ods'
            ods.parent.mkdir()
            ods.write_bytes(b'unchanged workbook')
            text = 'id: "custom"\n'  # Sentinel: this test checks destination and byte preservation only.
            macro = unittest.mock.Mock(side_effect=lambda function, name: 'custom')
            with patch.object(exporter, 'office', return_value=contextlib.nullcontext(object())), \
                 patch.object(exporter, 'MacroFunctions', return_value=macro), \
                 patch.object(exporter, 'export_yaml', return_value=(text, [])), \
                 patch.object(exporter, 'load_name', return_value='Custom'):
                exporter.export_only(ods)
            self.assertEqual((ods.parent / 'custom.yaml').read_text(), text)
            self.assertEqual(ods.read_bytes(), b'unchanged workbook')

    def test_failed_export_leaves_existing_yaml_unchanged(self):
        exporter = self.exporter
        with tempfile.TemporaryDirectory() as directory:
            ods = Path(directory) / 'custom.ods'
            output = ods.with_suffix('.yaml')
            output.write_text('existing data')
            with patch.object(exporter, 'office', return_value=contextlib.nullcontext(object())), \
                 patch.object(exporter, 'MacroFunctions'), \
                 patch.object(exporter, 'export_yaml', return_value=(None, ['invalid coordinate'])):
                with self.assertRaises(SystemExit):
                    exporter.export_only(ods)
            self.assertEqual(output.read_text(), 'existing data')

    def test_current_templates_exist_and_macro_uses_document_location(self):
        self.assertTrue(self.exporter.TEMPLATE.is_file())
        self.assertTrue(self.exporter.MACRO_DOC.is_file())
        with ZipFile(self.exporter.MACRO_DOC) as archive:
            code = ''.join(ET.fromstring(archive.read('Basic/Standard/Module1.xml')).itertext())
            content = archive.read('content.xml').decode()
        self.assertIn('Sub SaveDomainModel(Optional event)', code)
        self.assertIn('baseUrl = DomainModelParentURL(sourceDoc.URL)', code)
        self.assertIn('CopyDomainModelValues(d, target)', code)
        self.assertNotIn('FilePicker', code)
        self.assertIn('form:label="SAVE DOMAIN MODEL"', content)
        self.assertIn('Standard.Module1.SaveDomainModel?language=Basic', content)
        for entry in ('SaveModel', 'AddDimension', 'AddPrototype', 'ExportYAML'):
            self.assertIn(f'Sub {entry}(Optional event)', code)


if __name__ == '__main__':
    unittest.main()
