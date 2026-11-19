#!/usr/bin/env python3
"""Verify, download and image-test curated Ollama VLMs. No work runs on import.

Model weights stay in the existing Ollama service's standard storage. Uses only
Python's standard library; see --help for selection and verification commands.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).with_name('model_results.json')
DICTIONARY = ROOT / 'extraction_pipeline/model_dictionary.ods'
REGISTRY = 'https://registry.ollama.ai/v2/library'
PROMPT = 'Describe what is visible in this image in one or two sentences.'
# Candidates, not availability claims: verify each manifest AND configuration.
MODELS = {
    'qwen3_vl_2b': {'name': 'Qwen3-VL 2B Instruct', 'family': 'Qwen3-VL', 'variants': {
        'q4': 'qwen3-vl:2b-instruct-q4_K_M', 'q8': 'qwen3-vl:2b-instruct-q8_0'}},
    'qwen3_vl_4b': {'name': 'Qwen3-VL 4B Instruct', 'family': 'Qwen3-VL', 'variants': {
        'q4': 'qwen3-vl:4b-instruct-q4_K_M', 'q8': 'qwen3-vl:4b-instruct-q8_0'}},
    'gemma3_4b': {'name': 'Gemma 3 4B', 'family': 'Gemma 3', 'variants': {
        'q4': 'gemma3:4b-it-q4_K_M', 'q8': 'gemma3:4b-it-q8_0'}},
    'granite_vision_2b': {'name': 'Granite Vision 3.2 2B', 'family': 'Granite Vision 3.2', 'variants': {
        'q4': 'granite3.2-vision:2b-q4_K_M', 'q8': 'granite3.2-vision:2b-q8_0'}},
    'llava_phi3_3_8b': {'name': 'LLaVA-Phi3', 'family': 'LLaVA', 'variants': {
        'q4': 'llava-phi3:3.8b-mini-q4_0'}},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def request(url, payload=None, timeout=60):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'HTTP {exc.code}: {exc.read().decode(errors="replace")}') from exc


def get_json(url, payload=None, timeout=60):
    with request(url, payload, timeout) as response:
        result = json.load(response)
    if isinstance(result, dict) and result.get('error'):
        raise RuntimeError(result['error'])
    return result


def expected_quantization(tag):
    # Legacy tags can disagree with the config's precise Q4 subtype. Verify the
    # requested bit family here, then record the actual /api/show subtype.
    return tag.rsplit('-', 1)[1].split('_', 1)[0].upper()


def verify_registry(tag):
    family, variant = tag.split(':', 1)
    url = f'{REGISTRY}/{family}/manifests/{variant}'
    manifest = get_json(url)
    config = get_json(f"{REGISTRY}/{family}/blobs/{manifest['config']['digest']}")
    if not config.get('file_type', '').upper().startswith(expected_quantization(tag) + '_'):
        raise RuntimeError(f"Registry quantization mismatch: {tag}: {config.get('file_type')}")
    if not any(layer['mediaType'] == 'application/vnd.ollama.image.projector' for layer in manifest['layers']):
        raise RuntimeError(f'No vision projector in manifest: {tag}')
    return {'checked_at': now(), 'manifest_url': url, 'config': config, 'manifest': manifest,
            'tag_page': f'https://ollama.com/library/{tag}'}


class Ollama:
    def __init__(self, host):
        self.host = host.rstrip('/')

    def api(self, path, payload=None, timeout=60):
        return get_json(self.host + '/api/' + path, payload, timeout)

    def installed(self):
        return {m['name']: m for m in self.api('tags')['models']}

    def pull(self, tag):
        last, progress = None, {}
        with request(self.host + '/api/pull', {'model': tag, 'stream': True}, timeout=180) as response:
            for line in response:
                event = json.loads(line)
                if event.get('error'):
                    raise RuntimeError(event['error'])
                last = event.get('status')
                digest = event.get('digest', '')
                total, completed = event.get('total', 0), event.get('completed', 0)
                bucket = int(10 * completed / total) if total else -1
                if progress.get(digest) != (last, bucket):
                    print(f'  {tag}: {last}' + (f' {completed / total:.0%}' if total else ''), flush=True)
                    progress[digest] = (last, bucket)
        if last != 'success':
            raise RuntimeError(f'Pull ended without success: {last}')

    def unload(self, tag):
        self.api('generate', {'model': tag, 'keep_alive': 0, 'stream': False})
        for _ in range(40):
            if not any(m['name'] == tag for m in self.api('ps')['models']):
                return
            time.sleep(0.25)
        raise RuntimeError(f'Model did not unload: {tag}')


def gpu_snapshot():
    try:
        result = subprocess.run([
            'nvidia-smi', '--query-gpu=name,memory.total,memory.used,driver_version', '--format=csv,noheader,nounits',
        ], capture_output=True, text=True, timeout=10, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return f'Unavailable: {exc}'


def test_image(client, tag, image, timeout, context=4096, prompt=PROMPT):
    """Try automatic placement, then CPU on failure. Unload after each attempt."""
    foreign = [m['name'] for m in client.api('ps')['models'] if m['name'] != tag]
    if foreign:
        raise RuntimeError(f'Other models are loaded; refusing to evict them: {foreign}')
    encoded = base64.b64encode(image.read_bytes()).decode('ascii')
    attempts = []
    for mode in ('auto', 'cpu'):
        options = {'num_ctx': context, 'num_predict': 96, 'num_batch': 64, 'temperature': 0}
        if mode == 'cpu':
            options['num_gpu'] = 0
        attempt = {'mode': mode, 'started_at': now(), 'options': options}
        start = time.monotonic()
        print(f'TEST {tag}: image={image.name}, placement={mode}', flush=True)
        try:
            response = client.api('chat', {
                'model': tag, 'messages': [{'role': 'user', 'content': prompt, 'images': [encoded]}],
                'stream': False, 'options': options, 'keep_alive': '2m',
            }, timeout=timeout)
            attempt.update(response=response, running_models=client.api('ps')['models'], gpu_snapshot=gpu_snapshot())
            if not response.get('done') or not response.get('message', {}).get('content', '').strip():
                raise RuntimeError('Image request produced no completed, nonempty response')
            attempt['success'] = True
        except (OSError, ValueError, RuntimeError) as exc:
            attempt.update(success=False, error=str(exc))
        finally:
            attempt['seconds'] = round(time.monotonic() - start, 3)
            try:
                client.unload(tag)
                attempt['unloaded'] = True
            except (OSError, ValueError, RuntimeError) as exc:
                attempt.update(unloaded=False, unload_error=str(exc))
            attempts.append(attempt)
        print(f"  {'PASS' if attempt['success'] else 'FAIL'} {tag}: {attempt['seconds']}s"
              + (f" — {attempt['error']}" if attempt.get('error') else ''), flush=True)
        if attempt['success'] or not attempt['unloaded']:
            break
    return {'success': any(a['success'] for a in attempts),
            'image': str(image.relative_to(ROOT)) if image.is_relative_to(ROOT) else str(image),
            'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(), 'prompt': prompt, 'attempts': attempts}


def notes(record):
    lines = [f"Registry: {record.get('registry', {}).get('tag_page', '')}"]
    if record.get('error'):
        lines.append(record['error'])
    for error in record.get('error_history', []):
        lines.append('Previous setup failure: ' + error)
    if record.get('size_bytes') is not None:
        lines.append(f"Registered artifact: {record['size_bytes']} bytes (decimal GB; shared layers may be deduplicated).")
    lines.append('Model label is the advertised size; Parameters uses the GGUF model parameter count when available, otherwise Ollama\'s rounded count.')
    registry_quant = record.get('registry', {}).get('config', {}).get('file_type')
    if registry_quant and registry_quant.upper() != record.get('tag', '').rsplit('-', 1)[-1].upper():
        lines.append(f'Tag suffix differs from registry quantization ({registry_quant}); Quantization uses installed metadata.')
    for previous in record.get('inference_history', []):
        for attempt in previous['attempts']:
            lines.append(f"Previous {attempt['mode']} test (context {attempt['options']['num_ctx']}): "
                         + ('passed' if attempt['success'] else attempt.get('error', 'failed')))
            if attempt.get('response'):
                lines.append('Previous image response: ' + attempt['response']['message']['content'])
    test = record.get('inference')
    if not test:
        return '\n'.join(lines + ['Image inference not tested.'])
    lines.append(f"Image: {test['image']}; SHA256: {test['image_sha256']}")
    lines.append('Image question: ' + test['prompt'])
    if any(a.get('response', {}).get('message', {}).get('content', '').strip().casefold().rstrip('.') == 'unanswerable'
           for a in test['attempts'] if a['success']):
        lines.append("LIMITATION: The image request executed, but the model returned 'unanswerable'. A useful description was not demonstrated.")
    for attempt in test['attempts']:
        lines.append(f"{attempt['mode']}: {'passed' if attempt['success'] else 'failed'}, {attempt['seconds']}s; "
                     f"options={json.dumps(attempt['options'], sort_keys=True)}")
        for running in attempt.get('running_models', []):
            if running['name'] == record['tag']:
                lines.append(f"Ollama allocation: size={running.get('size')} bytes; GPU={running.get('size_vram')} bytes; "
                             f"context={running.get('context_length')}. Snapshot, not measured peak.")
                size, vram = running.get('size', 0), running.get('size_vram', 0)
                placement = 'CPU' if vram == 0 else 'GPU' if vram >= size else 'mixed CPU/GPU offloading'
                lines.append('Observed placement: ' + placement + '; larger images or contexts can change memory requirements.')
        if attempt.get('gpu_snapshot'):
            lines.append('GPU (name, total MiB, used MiB, driver): ' + attempt['gpu_snapshot'])
        for key in ('error', 'unload_error'):
            if attempt.get(key):
                lines.append(key + ': ' + attempt[key])
        if attempt.get('response'):
            lines.append('Image response: ' + attempt['response']['message']['content'])
    return '\n'.join(lines)


def write_dictionary(state, destination=DICTIONARY):
    """Write a single-sheet ODS without introducing a spreadsheet dependency."""
    ns = {
        'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
        'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
        'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
        'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
        'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
    }
    def tag(prefix, name):
        return f'{{{ns[prefix]}}}{name}'
    document = ET.Element(tag('office', 'document-content'), {tag('office', 'version'): '1.2'})
    styles = ET.SubElement(document, tag('office', 'automatic-styles'))
    for name, width in (('normal', '4cm'), ('wide', '10cm')):
        style = ET.SubElement(styles, tag('style', 'style'), {tag('style', 'name'): name, tag('style', 'family'): 'table-column'})
        ET.SubElement(style, tag('style', 'table-column-properties'), {tag('style', 'column-width'): width})
    for name in ('body', 'head'):
        style = ET.SubElement(styles, tag('style', 'style'), {tag('style', 'name'): name, tag('style', 'family'): 'table-cell'})
        ET.SubElement(style, tag('style', 'table-cell-properties'), {tag('fo', 'wrap-option'): 'wrap', tag('style', 'vertical-align'): 'top'})
        if name == 'head':
            ET.SubElement(style, tag('style', 'text-properties'), {tag('fo', 'font-weight'): 'bold'})
    sheet = ET.SubElement(ET.SubElement(ET.SubElement(document, tag('office', 'body')), tag('office', 'spreadsheet')),
                          tag('table', 'table'), {tag('table', 'name'): 'Dictionary'})
    for index in range(10):
        ET.SubElement(sheet, tag('table', 'table-column'), {tag('table', 'style-name'): 'wide' if index in (4, 9) else 'normal'})
    rows = [['Model', 'Family', 'Parameters', 'Quantization', 'Ollama tag', 'Download size (GB)',
             'Execution', 'Runtime', 'Status', 'Notes']]
    for item in MODELS.values():
        for model_tag in item['variants'].values():
            rec = state['models'].get(model_tag, {})
            rows.append([item['name'], item['family'], rec.get('parameters', ''), rec.get('quantization', ''), model_tag,
                         rec['size_bytes'] / 1e9 if rec.get('size_bytes') is not None else '',
                         'Local', 'Ollama', rec.get('status', ''), notes(rec)])
    for index, values in enumerate(rows):
        row = ET.SubElement(sheet, tag('table', 'table-row'))
        for value in values:
            attrs = {tag('table', 'style-name'): 'head' if index == 0 else 'body',
                     tag('office', 'value-type'): 'float' if isinstance(value, (int, float)) else 'string'}
            if isinstance(value, (int, float)):
                attrs[tag('office', 'value')] = str(value)
            cell = ET.SubElement(row, tag('table', 'table-cell'), attrs)
            for line in str(value).split('\n'):
                ET.SubElement(cell, tag('text', 'p')).text = line
    mns = 'urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'
    manifest = ET.Element(f'{{{mns}}}manifest', {f'{{{mns}}}version': '1.2'})
    for path, media in (('/', 'application/vnd.oasis.opendocument.spreadsheet'), ('content.xml', 'text/xml')):
        ET.SubElement(manifest, f'{{{mns}}}file-entry', {f'{{{mns}}}full-path': path, f'{{{mns}}}media-type': media})
    temporary = destination.with_suffix('.ods.tmp')
    with ZipFile(temporary, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('mimetype', 'application/vnd.oasis.opendocument.spreadsheet', compress_type=ZIP_STORED)
        archive.writestr('content.xml', ET.tostring(document, encoding='utf-8', xml_declaration=True))
        archive.writestr('META-INF/manifest.xml', ET.tostring(manifest, encoding='utf-8', xml_declaration=True))
    temporary.replace(destination)


def save(state):
    state['updated_at'] = now()
    temporary = RESULTS.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(RESULTS)
    write_dictionary(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--list', action='store_true', help='verify/list official registry variants; no download')
    action.add_argument('--pull', nargs='+', choices=MODELS, help='download named families (Q4 by default)')
    action.add_argument('--all', action='store_true', help='download all nine variants unless filtered by --quant')
    parser.add_argument('--quant', nargs='+', choices=('q4', 'q8'), help='filter selected quantizations')
    parser.add_argument('--test-image', type=Path, help='test each selected model with an actual image')
    parser.add_argument('--test-only', action='store_true', help='test installed selections; never download')
    parser.add_argument('--timeout', type=int, default=600, help='image request timeout in seconds')
    parser.add_argument('--context', type=int, default=4096, help='image-test context size in tokens')
    parser.add_argument('--prompt', default=PROMPT, help='simple image-verification question')
    parser.add_argument('--host', default=os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'))
    args = parser.parse_args(argv)
    if args.context <= 0 or args.timeout <= 0:
        parser.error('--context and --timeout must be positive')
    if args.test_only and not args.test_image:
        parser.error('--test-only requires --test-image')
    if args.test_image and not args.test_image.is_file():
        parser.error(f'Image not found: {args.test_image}')
    keys = list(MODELS) if args.all or args.list else args.pull
    quants = args.quant or (['q4', 'q8'] if args.all or args.list else ['q4'])
    selected = [(MODELS[key], quant, tag) for key in dict.fromkeys(keys)
                for quant, tag in MODELS[key]['variants'].items() if quant in quants]
    if not selected:
        parser.error('No requested variants exist in the catalogue (LLaVA-Phi3 has only Q4)')
    if args.list:
        failed = False
        for item, quant, model_tag in selected:
            try:
                registry = verify_registry(model_tag)
                config = registry['config']
                key = next(key for key, candidate in MODELS.items() if candidate is item)
                print(f"AVAILABLE {key}: {model_tag}: {config['model_type']}, {config['file_type']}; {registry['tag_page']}")
            except (OSError, ValueError, RuntimeError) as exc:
                print(f'UNVERIFIED {model_tag}: {exc}')
                failed = True
        return int(failed)
    client = Ollama(args.host if '://' in args.host else 'http://' + args.host)
    before = client.installed()
    state = json.loads(RESULTS.read_text(encoding='utf-8')) if RESULTS.exists() else {'models': {}, 'runs': []}
    run = {'started_at': now(), 'command': shlex.join([sys.executable, *sys.argv]),
           'host': client.host,
           'ollama_version': client.api('version'), 'gpu': gpu_snapshot(),
           'installed_before': before, 'selected_tags': [tag for _, _, tag in selected]}
    state['runs'].append(run)
    failed = []
    for item, quant, model_tag in selected:
        record = state['models'].setdefault(model_tag, {})
        record.update(tag=model_tag, name=item['name'], family=item['family'])
        previous_error = record.pop('error', None)
        if previous_error:
            record.setdefault('error_history', []).append(previous_error)
        stage = 'registry'
        try:
            record['registry'] = verify_registry(model_tag)
            config = record['registry']['config']
            record.update(parameters=config['model_type'], quantization=config['file_type'])
            stage = 'download'
            if model_tag in client.installed():
                print(f'SKIP {model_tag}: already downloaded', flush=True)
            else:
                for key in ('size_bytes', 'digest', 'inference', 'local_metadata'):
                    record.pop(key, None)
                if args.test_only:
                    raise RuntimeError('Not installed; --test-only does not download')
                print(f"PULL {model_tag}: verified {config['file_type']}", flush=True)
                client.pull(model_tag)
            installed = client.installed()[model_tag]
            show = client.api('show', {'model': model_tag})
            record['local_metadata'] = show
            if record.get('digest') != installed['digest']:
                record.pop('inference', None)
            count = show.get('model_info', {}).get('general.parameter_count')
            record.update(size_bytes=installed['size'], digest=installed['digest'],
                          parameters=f'{count:,}' if isinstance(count, int) else show['details']['parameter_size'],
                          quantization=show['details']['quantization_level'])
            record['status'] = ('Tested' if record.get('inference', {}).get('success') else
                                'Failed' if record.get('inference') else 'Downloaded')
            if not record['quantization'].upper().startswith(expected_quantization(model_tag) + '_'):
                raise RuntimeError('Installed quantization differs from the requested variant')
            if 'vision' not in show.get('capabilities', []):
                raise RuntimeError('Installed model does not advertise image-input capability')
            save(state)
            if args.test_image:
                stage = 'inference'
                if record.get('inference'):
                    record.setdefault('inference_history', []).append(record['inference'])
                record['inference'] = test_image(client, model_tag, args.test_image.resolve(), args.timeout, args.context, args.prompt)
                record['status'] = 'Tested' if record['inference']['success'] else 'Failed'
                if not record['inference']['success']:
                    failed.append(model_tag)
            print(f"{record['status'].upper()} {model_tag}: {record['size_bytes']} bytes, {record['quantization']}", flush=True)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            unavailable = stage == 'registry' and isinstance(exc.__cause__, urllib.error.HTTPError) and exc.__cause__.code == 404
            record.update(status='Unavailable' if unavailable else 'Failed', error=f'{stage}: {exc}')
            print(f"{record['status'].upper()} {model_tag}: {exc}", file=sys.stderr, flush=True)
            failed.append(model_tag)
        save(state)
    after = client.installed()
    selected_tags = set(run['selected_tags'])
    run['unrelated_models_unchanged'] = all(
        tag in after and after[tag]['digest'] == metadata['digest'] for tag, metadata in before.items() if tag not in selected_tags)
    run.update(finished_at=now(), failed_tags=failed, installed_after=after)
    save(state)
    print(f"Completed: {len(selected) - len(failed)}/{len(selected)} selections; unrelated models unchanged: "
          f"{run['unrelated_models_unchanged']}. Results: {RESULTS}; dictionary: {DICTIONARY}")
    return int(bool(failed) or not run['unrelated_models_unchanged'])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
