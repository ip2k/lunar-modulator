#!/usr/bin/env python3
"""Review linked pair artifacts without executing target code or using hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/jieli'))
from audit_link import Elf

ENGINES = ['macro', 'shapes', 'macro-heavy', 'sixop', 'dx7', 'sw-sophie',
           'drums', 'acid-bass', 'comet', 'crater', 'drawbar', 'trio', 'phase-bend']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze_build(build):
    verification = json.loads((build / 'verification.json').read_text())
    artifact = json.loads((build / 'artifact/artifact.json').read_text())
    engines = [r['id'] for r in verification['module_selection']['catalogue']
               if r['selected'] and r['kind'] == 'sound']
    if engines != ENGINES or artifact['layout_passed'] is not True:
        raise ValueError('missing production engine or failed artifact layout')
    if verification['catalogue_optimization_overrides'] != {
        'our/src/mi_sixop.o': '-Os', 'our/src/fx_hall.o': '-O2'}:
        raise ValueError('mismatched current optimization profile')
    if not verification['catalogue_hall_o2'] or not verification['hot_dsp_ram']['enabled']:
        raise ValueError('missing current hot-RAM/Hall profile')
    if verification['diagnostic_engine_render_profile']['schema'] != 7:
        raise ValueError('mismatched engine profile schema')
    if verification['project_save_service']['save_service_armed'] is not False:
        raise ValueError('SAVE must stay disarmed')
    if sha(build / 'artifact/app.bin') != artifact['app_sha256'] or sha(build / 'lunar-app-probe.elf') != artifact['elf_sha256']:
        raise ValueError('artifact hash mismatch')
    elf = Elf((build / 'lunar-app-probe.elf').read_bytes())
    sections = {s['name']: {'address': s['addr'], 'bytes': s['size']}
                for s in elf.sections if s['name'] in ['.text', '.ram_text', '.ram_dsp', '.data', '.bss', '.pool', '.noinit']}
    symbols = [s for s in elf.symbols if s['shndx'] and s['size'] and s['type'] == 2]
    ram_lines = (build / 'ram-dsp.txt').read_text().splitlines()
    instructions = []
    for line in ram_lines:
        match = re.match(r'\s*([0-9a-f]+):\s', line)
        if match:
            instructions.append((int(match[1], 16), line))

    def symbol_lines(symbol):
        return [line for address, line in instructions
                if symbol['value'] <= address < symbol['value'] + symbol['size']]

    def describe(symbol):
        lines = symbol_lines(symbol)
        calls = []
        for line in lines:
            if '\tcall ' in line:
                target = re.search(r'<.* : ([0-9a-f]+) >', line)
                calls.append({'instruction': line.strip(), 'address': int(target[1], 16) if target else None})
        return {'name': symbol['name'], 'address': symbol['value'], 'bytes': symbol['size'],
                'section': elf.sections[symbol['shndx']]['name'],
                'prologue': lines[:5], 'calls': calls}

    render = {}
    for engine in ['drums', 'sixop']:
        symbol = next(s for s in symbols if s['name'] == '_ZN3fm15' + engine + '8Instance6RenderEPfj')
        row = describe(symbol)
        callees = []
        for call in row['calls']:
            target = next((s for s in symbols if s['value'] == call['address']), None)
            if target and 'fm1_resampler_pop_ready_' in target['name']:
                callee = describe(target)
                nested = []
                for child in callee['calls']:
                    child_symbol = next((s for s in symbols if s['value'] == child['address']), None)
                    if child_symbol:
                        nested.append(describe(child_symbol))
                callee['nested_callees'] = nested
                callees.append(callee)
        if len(callees) != 1 or row['section'] != '.ram_dsp' or callees[0]['section'] != '.ram_dsp':
            raise ValueError('engine Render must call exactly one RAM ready-pop')
        row['resampler_callees'] = callees
        render[engine] = row
    rt = sections['.ram_text']; rd = sections['.ram_dsp']; pool = sections['.pool']
    return {'app_bytes': artifact['app_bytes'], 'app_budget_bytes': artifact['app_budget_bytes'],
        'app_slack_bytes': artifact['app_budget_bytes'] - artifact['app_bytes'],
        'app_sha256': artifact['app_sha256'], 'elf_sha256': artifact['elf_sha256'],
        'sections': sections, 'ram_code_slack_bytes': 0x01c06000 - (rd['address'] + rd['bytes']),
        'globals_pool_slack_bytes': 0x01c74000 - (pool['address'] + pool['bytes']),
        'ram_layout_fits': rd['address'] >= rt['address'] + rt['bytes'] and rd['address'] + rd['bytes'] <= 0x01c06000
                           and pool['address'] + pool['bytes'] <= 0x01c74000,
        'production_engines': engines, 'render': render,
        'intermediate_symbols': [describe(s) for s in symbols if 'fm1_resampler_intermediate_' in s['name']],
        'all_ready_pop_symbols': [describe(s) for s in symbols if 'fm1_resampler_pop_ready_' in s['name']],
        'physical_stack_high_water_verified': False, 'runtime_performance_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair-output', type=Path, required=True)
    args = parser.parse_args()
    output = args.pair_output
    pair = json.loads((output / 'pair-result.json').read_text())
    rows = {}
    receipts = {}
    for label in ['baseline', 'candidate']:
        receipt_path = output / label / 'frozen-build-input-receipt.json'
        if sha(receipt_path) != pair['results'][label]['receipt_sha256']:
            raise ValueError('build receipt changed')
        receipt = json.loads(receipt_path.read_text())
        receipts[label] = receipt
        if receipt['source_commit'] != pair[label + '_commit']:
            raise ValueError('receipt source mismatch')
        for relative, digest in receipt['outputs'].items():
            if sha(output / label / relative) != digest:
                raise ValueError('build output changed: ' + relative)
        rows[label] = analyze_build(output / label / 'writable-output/build')
    for field in ['docker_image_id', 'toolchain_snapshot_tree_manifest_sha256',
                  'headers_snapshot_tree_manifest_sha256', 'prepared_snapshot_tree_manifest_sha256',
                  'selection_sha256', 'prepared_profile_sha256', 'link_command', 'catalogue_container_policy']:
        if receipts['baseline'][field] != receipts['candidate'][field]:
            raise ValueError('matched pair input differs: ' + field)
    rows['matched_input_fields'] = ['docker_image_id', 'toolchain_snapshot_tree_manifest_sha256',
        'headers_snapshot_tree_manifest_sha256', 'prepared_snapshot_tree_manifest_sha256',
        'selection_sha256', 'prepared_profile_sha256', 'link_command', 'catalogue_container_policy']
    rows['delta'] = {key: rows['candidate'][key] - rows['baseline'][key]
        for key in ['app_bytes', 'app_slack_bytes', 'ram_code_slack_bytes', 'globals_pool_slack_bytes']}
    rows['delta']['sections'] = {name: rows['candidate']['sections'][name]['bytes'] - row['bytes']
        for name, row in rows['baseline']['sections'].items()}
    (output / 'linked-comparison.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(rows['delta'], indent=2))


if __name__ == '__main__':
    main()
