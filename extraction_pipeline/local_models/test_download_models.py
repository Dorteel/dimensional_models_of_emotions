"""Offline downloader tests: no Ollama service, weights, or network required."""
import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import download_models as downloader


class RegistryVerification(unittest.TestCase):
    def registry(self, quant='Q4_K_M', vision=True):
        return [
            {'config': {'digest': 'sha256:test'}, 'layers': [
                {'mediaType': 'application/vnd.ollama.image.projector'}] if vision else []},
            {'file_type': quant, 'model_type': 'test-count'},
        ]

    def test_legacy_llava_tag_records_actual_registry_quantization(self):
        with patch.object(downloader, 'get_json', side_effect=self.registry()):
            result = downloader.verify_registry('llava-phi3:3.8b-mini-q4_0')
        self.assertEqual(result['config']['file_type'], 'Q4_K_M')

    def test_wrong_quantization_and_nonvision_manifests_are_rejected(self):
        for quant, vision in (('Q8_0', True), ('Q4_K_M', False)):
            with self.subTest(quant=quant, vision=vision):
                with patch.object(downloader, 'get_json', side_effect=self.registry(quant, vision)):
                    with self.assertRaises(RuntimeError):
                        downloader.verify_registry('qwen3-vl:2b-instruct-q4_K_M')


class ImageVerification(unittest.TestCase):
    def test_image_bytes_are_sent_and_cpu_retry_is_recorded(self):
        client = Mock()
        calls = []
        def api(path, payload=None, timeout=60):
            if path == 'ps':
                return {'models': []}
            calls.append(payload)
            if payload['options'].get('num_gpu') != 0:
                raise RuntimeError('simulated GPU memory failure')
            return {'done': True, 'message': {'content': 'An image description.'}}
        client.api.side_effect = api
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'image.jpg'
            image.write_bytes(b'test image bytes')
            with patch.object(downloader, 'gpu_snapshot', return_value='test GPU'), contextlib.redirect_stdout(io.StringIO()):
                result = downloader.test_image(client, 'model:tag', image, 30, context=8192, prompt='What is visible?')
        self.assertTrue(result['success'])
        self.assertEqual([a['success'] for a in result['attempts']], [False, True])
        self.assertEqual(base64.b64decode(calls[0]['messages'][0]['images'][0]), b'test image bytes')
        self.assertEqual(calls[1]['options']['num_gpu'], 0)
        self.assertEqual(calls[0]['options']['num_ctx'], 8192)
        self.assertEqual(calls[0]['messages'][0]['content'], 'What is visible?')
        self.assertEqual(client.unload.call_count, 2)

    def test_unrelated_running_models_are_not_evicted(self):
        client = Mock()
        client.api.return_value = {'models': [{'name': 'unrelated:latest'}]}
        with self.assertRaisesRegex(RuntimeError, 'refusing to evict'):
            downloader.test_image(client, 'selected:tag', Path('not-read.jpg'), 30)
        client.unload.assert_not_called()
        self.assertEqual(client.api.call_count, 1)

    def test_empty_response_is_a_failure_even_when_request_completes(self):
        client = Mock()
        client.api.side_effect = lambda path, *args, **kwargs: (
            {'models': []} if path == 'ps' else {'done': True, 'message': {'content': ''}})
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'image.jpg'
            image.write_bytes(b'test')
            with patch.object(downloader, 'gpu_snapshot', return_value='test GPU'), contextlib.redirect_stdout(io.StringIO()):
                result = downloader.test_image(client, 'selected:tag', image, 30)
        self.assertFalse(result['success'])
        self.assertEqual(len(result['attempts']), 2)


class SelectionAndCatalogue(unittest.TestCase):
    def installed(self):
        models = {'unrelated:latest': {'digest': 'unchanged'}}
        for index, item in enumerate(downloader.MODELS.values()):
            for tag in item['variants'].values():
                models[tag] = {'digest': tag, 'size': 1234567890 + index}
        return models

    def test_all_selects_nine_variants_skips_installed_and_preserves_unrelated(self):
        client = Mock()
        client.host = 'http://test.invalid'
        installed = self.installed()
        client.installed.return_value = installed
        def api(path, payload=None):
            if path == 'version':
                return {'version': 'test'}
            tag = payload['model']
            return {'details': {'parameter_size': 'actual count',
                                'quantization_level': downloader.expected_quantization(tag) + '_K_M'},
                    'capabilities': ['vision']}
        client.api.side_effect = api
        def registry(tag):
            return {'config': {'model_type': 'registry count', 'file_type': downloader.expected_quantization(tag) + '_K_M'}}
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / 'results.json'
            with patch.object(downloader, 'Ollama', return_value=client), \
                 patch.object(downloader, 'verify_registry', side_effect=registry), \
                 patch.object(downloader, 'gpu_snapshot', return_value='test GPU'), \
                 patch.object(downloader, 'RESULTS', results), \
                 patch.object(downloader, 'write_dictionary'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(downloader.main(['--all']), 0)
            state = json.loads(results.read_text())
        client.pull.assert_not_called()
        self.assertEqual(len(state['models']), 9)
        self.assertTrue(state['runs'][0]['unrelated_models_unchanged'])
        for tag, record in state['models'].items():
            self.assertEqual(record['status'], 'Downloaded')
            self.assertEqual(record['size_bytes'], installed[tag]['size'])
            self.assertEqual(record['parameters'], 'actual count')

    def test_failure_is_recorded_and_remaining_selection_continues(self):
        client = Mock()
        client.host = 'http://test.invalid'
        client.installed.return_value = {'unrelated:latest': {'digest': 'unchanged'}}
        client.api.return_value = {'version': 'test'}
        client.pull.side_effect = RuntimeError('simulated download failure')
        registry = {'config': {'model_type': 'test', 'file_type': 'Q4_K_M'}}
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / 'results.json'
            with patch.object(downloader, 'Ollama', return_value=client), \
                 patch.object(downloader, 'verify_registry', return_value=registry), \
                 patch.object(downloader, 'gpu_snapshot', return_value='test GPU'), \
                 patch.object(downloader, 'RESULTS', results), \
                 patch.object(downloader, 'write_dictionary'), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(downloader.main(['--pull', 'qwen3_vl_2b', '--quant', 'q4', 'q8']), 1)
            state = json.loads(results.read_text())
        self.assertEqual(client.pull.call_count, 2)
        self.assertEqual([r['status'] for r in state['models'].values()], ['Failed', 'Failed'])
        self.assertTrue(all('size_bytes' not in r for r in state['models'].values()))

    def test_retest_preserves_previous_failure_and_uses_requested_context(self):
        tag = downloader.MODELS['qwen3_vl_2b']['variants']['q4']
        installed = self.installed()
        previous = {'success': False, 'attempts': [{'error': 'Context too small'}]}
        client = Mock(host='http://test.invalid')
        client.installed.return_value = installed
        client.api.side_effect = lambda path, payload=None: ({'version': 'test'} if path == 'version' else {
            'details': {'parameter_size': 'actual', 'quantization_level': 'Q4_K_M'}, 'capabilities': ['vision']})
        registry = {'config': {'model_type': 'test', 'file_type': 'Q4_K_M'}}
        with tempfile.TemporaryDirectory() as directory:
            image, results = Path(directory) / 'test.jpg', Path(directory) / 'results.json'
            image.write_bytes(b'test image')
            results.write_text(json.dumps({'runs': [], 'models': {tag: {
                'digest': installed[tag]['digest'], 'inference': previous, 'error': 'Previous registry check failed'}}}))
            with patch.object(downloader, 'Ollama', return_value=client), \
                 patch.object(downloader, 'verify_registry', return_value=registry), \
                 patch.object(downloader, 'gpu_snapshot', return_value='test GPU'), \
                 patch.object(downloader, 'RESULTS', results), \
                 patch.object(downloader, 'write_dictionary'), \
                 patch.object(downloader, 'test_image', return_value={'success': True}) as test, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(downloader.main(['--pull', 'qwen3_vl_2b', '--test-only',
                                                 '--test-image', str(image), '--context', '8192']), 0)
            record = json.loads(results.read_text())['models'][tag]
            test.assert_called_once_with(client, tag, image.resolve(), 600, 8192, downloader.PROMPT)
        self.assertEqual(record['inference_history'], [previous])
        self.assertEqual(record['error_history'], ['Previous registry check failed'])
        self.assertEqual(record['status'], 'Tested')
        client.pull.assert_not_called()

    def test_dictionary_contains_all_variants_and_only_measured_sizes(self):
        tag = next(iter(downloader.MODELS.values()))['variants']['q4']
        state = {'models': {tag: {'tag': tag, 'status': 'Downloaded', 'size_bytes': 1234567890,
                                  'quantization': 'Q4_K_M', 'parameters': 'test'}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dictionary.ods'
            downloader.write_dictionary(state, path)
            with ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                document = ET.fromstring(archive.read('content.xml'))
        table_ns = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
        office_ns = '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'
        sheets = document.findall('.//' + table_ns + 'table')
        self.assertEqual(len(sheets), 1)
        rows = sheets[0].findall(table_ns + 'table-row')
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(len(row) == 10 for row in rows))
        sizes = [row[5].get(office_ns + 'value') for row in rows[1:]]
        self.assertEqual(sizes, ['1.23456789'] + [None] * 8)


if __name__ == '__main__':
    unittest.main()
