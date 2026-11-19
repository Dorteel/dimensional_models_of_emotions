#!/usr/bin/env python3
"""Verify saved VLM results against Ollama and reopen the dictionary in LibreOffice.

Read-only with respect to installed models and the dictionary. Requires the
existing Ollama service and LibreOffice; CSV output/profile live in a temp dir.
"""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from download_models import DICTIONARY, MODELS, RESULTS, ROOT, Ollama


def main():
    state = json.loads(RESULTS.read_text(encoding='utf-8'))
    host = 'http://127.0.0.1:11434'
    # Reuse the host actually selected by the downloader when available.
    if state['runs'][-1].get('host'):
        host = state['runs'][-1]['host']
    client = Ollama(host)
    installed = client.installed()
    expected = [tag for item in MODELS.values() for tag in item['variants'].values()]
    unanswerable = []
    for tag in expected:
        record = state['models'][tag]
        assert record['status'] == 'Tested', f'{tag}: not image-tested'
        assert installed[tag]['digest'] == record['digest'], f'{tag}: model changed since testing'
        assert installed[tag]['size'] == record['size_bytes'], f'{tag}: recorded size differs'
        show = client.api('show', {'model': tag})
        count = show.get('model_info', {}).get('general.parameter_count')
        if isinstance(count, int):
            assert record['parameters'] == f'{count:,}', f'{tag}: parameter count differs'
        assert 'vision' in show['capabilities'], f'{tag}: no vision capability'
        assert show['details']['quantization_level'] == record['quantization'], f'{tag}: quantization differs'
        inference = record['inference']
        image = Path(inference['image'])
        if not image.is_absolute():
            image = ROOT / image
        assert hashlib.sha256(image.read_bytes()).hexdigest() == inference['image_sha256'], f'{tag}: test image changed'
        successes = [a for a in inference['attempts'] if a['success']]
        assert successes and all(a['unloaded'] for a in inference['attempts']), f'{tag}: test/unload failed'
        assert successes[-1]['response']['done'] and successes[-1]['response']['message']['content'].strip()
        if successes[-1]['response']['message']['content'].strip().casefold().rstrip('.') == 'unanswerable':
            unanswerable.append(tag)
        print(f"VERIFIED {tag}: {record['size_bytes']} bytes; {record['quantization']}; {successes[-1]['mode']}")
    for tag, original in state['runs'][0]['installed_before'].items():
        if tag not in expected:
            assert installed[tag]['digest'] == original['digest'], f'Unrelated model changed: {tag}'
    assert not any(m['name'] in expected for m in client.api('ps')['models']), 'A tested model remains loaded'
    before = hashlib.sha256(DICTIONARY.read_bytes()).digest()
    with tempfile.TemporaryDirectory(prefix='vlm_dictionary_') as directory:
        work = Path(directory)
        result = subprocess.run([
            'soffice', '-env:UserInstallation=' + (work / 'profile').as_uri(), '--headless', '--convert-to',
            'csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false',
            '--outdir', str(work), str(DICTIONARY),
        ], capture_output=True, text=True, timeout=60, check=True)
        output = work / 'model_dictionary.csv'
        assert output.is_file(), result.stdout + result.stderr
        with output.open(newline='', encoding='utf-8') as stream:
            rows = list(csv.reader(stream))
        assert len(rows) == 10 and all(len(row) == 10 for row in rows), 'Unexpected ODS layout'
        assert rows[0] == ['Model', 'Family', 'Parameters', 'Quantization', 'Ollama tag',
                           'Download size (GB)', 'Execution', 'Runtime', 'Status', 'Notes']
        for row, tag in zip(rows[1:], expected):
            record = state['models'][tag]
            assert row[:3] == [record['name'], record['family'], record['parameters']], f'{tag}: ODS identity/count differs'
            assert row[4] == tag and row[8] == 'Tested', f'{tag}: ODS row differs'
            assert row[6:8] == ['Local', 'Ollama'], f'{tag}: ODS execution/runtime differs'
            assert row[3] == record['quantization'], f'{tag}: ODS quantization differs'
            assert abs(float(row[5]) * 1e9 - record['size_bytes']) < 1, f'{tag}: ODS size differs'
            if tag in unanswerable:
                assert 'unanswerable' in row[9] and 'not demonstrated' in row[9], f'{tag}: ODS omits the description limitation'
    assert hashlib.sha256(DICTIONARY.read_bytes()).digest() == before, 'Dictionary was modified'
    print('9/9 installed model records verified; dictionary reopened in LibreOffice; unrelated models unchanged.')
    if unanswerable:
        print("Image requests executed but returned 'unanswerable' (useful descriptions not verified): " + ', '.join(unanswerable))


if __name__ == '__main__':
    main()
