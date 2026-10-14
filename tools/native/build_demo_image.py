#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Connect ordered demo selection to an audited private diagnostic image.

Operator-owned compiler/catalogue paths never come from the browser request.
This controller produces build evidence, not a package or permission to flash.
"""
import argparse
import json
import re
from pathlib import Path
import subprocess
import sys

from prepare_demo_selection import prepare_selection
from prepare_image_profile import bounded_read, sha, unique_object
from verify_image_profile import load_prepared_profile
from runtime_mode import runtime_configuration
from module_selection import wavetable_namespaces

ROOT = Path(__file__).resolve().parents[2]
WAVETABLE_PROFILE = 'compressed-required-banks-flash-plaits-v1'
SHAPES8_WAVETABLE_PROFILE = 'compressed-required-banks-ram-plaits-braids-shapes8-v1'
BRAIDS_TABLE = dict(namespace='braids', symbol='wt_waves', width=1, raw_bytes=33024,
                    raw_sha256='c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634')
SHAPES8_TABLES = (
    dict(namespace='plaits', symbol='wav_integrated_waves', width=2, raw_bytes=50688,
         raw_sha256='bd1d04177e240247de3224ef8e6f52afd907d8ae1a9971e0ce4ba68258e7ecea',
         packed_bytes=32513, packed_sha256='2cbdd706ef8cd7b97e705b139eab7a328ff4cb03257326faf34c396ac5b21255',
         fnv32=2231692768, generated_source_sha256='b5dacba5b7df4af0c5966f5bd8906bd2c30486ccf8ef156db02248e6d469787c'),
    dict(namespace='braids', symbol='wt_waves', width=1, raw_bytes=33024,
         raw_sha256='c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634',
         packed_bytes=24159, packed_sha256='d05f3f0b852719327983c82418a1b6b9e4c2414430078267653a77feb2ed1952',
         fnv32=3119621762, generated_source_sha256='c3c20d193d012125c53b2d2cba811c33c559462c070fed2702dc896727f2b82e'),
)
TARGET_STORAGE = dict(rgb565_bytes=220832, indexed_bytes=163744, pool_credit_bytes=57088)
BASE_INSTANCE_POOL_BYTES = 192000
SHAPES_VOICES = 12


def checked_wavetable_profile(verification, selected):
    """Validate one of the two explicitly reviewed linked storage profiles."""
    voices = verification.get('shapes_voices')
    flash_plaits = verification.get('flash_plaits_wavetables')
    if type(voices) is not int or type(flash_plaits) is not bool:
        raise ValueError('Linked image wavetable profile differs from fixed policy/module selection')

    if voices == SHAPES_VOICES and flash_plaits is True:
        profile = WAVETABLE_PROFILE
        expected_namespaces = wavetable_namespaces(selected, flash_plaits=True)
        fixed_rows = None
        indexed = True
    elif voices == 8 and flash_plaits is False:
        if not {'macro', 'shapes'}.issubset(set(selected)):
            raise ValueError('Shapes8 compressed-RAM profile requires Macro and Shapes modules')
        profile = SHAPES8_WAVETABLE_PROFILE
        expected_namespaces = ['plaits', 'braids']
        fixed_rows = {row['namespace']: row for row in SHAPES8_TABLES}
        indexed = True
    else:
        raise ValueError('Linked image wavetable profile differs from fixed policy/module selection')

    rows = verification.get('compressed_wave_tables')
    if (verification.get('indexed_tft') is not indexed
            or not isinstance(rows, list)
            or [row.get('namespace') if isinstance(row, dict) else None for row in rows]
               != expected_namespaces):
        raise ValueError('Linked image wavetable profile differs from fixed policy/module selection')
    checked_rows = []
    expected_raw_bytes = 0
    for row, namespace in zip(rows, expected_namespaces):
        if not isinstance(row, dict):
            raise ValueError('Linked compressed wavetable source identity is stale')
        if fixed_rows is not None:
            expected = fixed_rows[namespace]
            if set(row) != set(expected) or row != expected:
                raise ValueError('Linked Shapes8 compressed wavetable identity is stale')
        else:
            if namespace != BRAIDS_TABLE['namespace']:
                raise ValueError('Unsupported compressed wavetable namespace')
            if (set(row) != {'namespace', 'symbol', 'width', 'raw_bytes', 'packed_bytes',
                             'raw_sha256', 'packed_sha256', 'fnv32', 'generated_source_sha256'}
                    or any(row.get(key) != value for key, value in BRAIDS_TABLE.items())
                    or type(row.get('width')) is not int
                    or type(row.get('raw_bytes')) is not int):
                raise ValueError('Linked compressed wavetable source identity is stale')
            if (type(row.get('packed_bytes')) is not int
                    or not 0 < row['packed_bytes'] <= BRAIDS_TABLE['raw_bytes']
                    or not isinstance(row.get('packed_sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', row['packed_sha256'])
                    or not isinstance(row.get('generated_source_sha256'), str)
                    or not re.fullmatch(r'[0-9a-f]{64}', row['generated_source_sha256'])
                    or type(row.get('fnv32')) is not int or not 0 <= row['fnv32'] <= 0xffffffff):
                raise ValueError('Linked compressed wavetable metadata is malformed')
        checked_rows.append(dict(row))
        expected_raw_bytes += row['raw_bytes']
    storage = verification.get('target_app_storage')
    if (not isinstance(storage, dict) or storage != TARGET_STORAGE
            or any(type(storage.get(key)) is not int for key in TARGET_STORAGE)):
        raise ValueError('Linked target storage profile differs from fixed layout')
    expected_pool = BASE_INSTANCE_POOL_BYTES + TARGET_STORAGE['pool_credit_bytes'] - expected_raw_bytes
    if (type(verification.get('instance_pool_bytes')) is not int
            or verification['instance_pool_bytes'] != expected_pool):
        raise ValueError('Linked instance pool does not match selected wavetable profile')
    return dict(wavetable_profile=profile, compressed_wave_tables=checked_rows,
                indexed_tft=True, flash_plaits_wavetables=flash_plaits, shapes_voices=voices,
                instance_pool_bytes=expected_pool, target_app_storage=dict(TARGET_STORAGE))



def checked_link_receipt(selection, prepared, verification, artifact, app, elf, *,
                         runtime_mode='diagnostic', require_save_service=False):
    """Bind ordered choices and actual output bytes to one completed link."""
    if runtime_mode not in ('diagnostic', 'song-diagnostic'):
        raise ValueError('Only bounded diagnostic runtime modes are supported')
    expected_runtime = runtime_configuration(runtime_mode)
    if (verification.get('runtime_configuration') != expected_runtime
            or verification.get('probe_return_to_rom_seconds') != expected_runtime['return_to_rom_seconds']):
        raise ValueError('runtime configuration mismatch')
    expected_assets = [dict(kind=a['kind'], bytes=a['bytes'],
                           packed_sha256=a['packed_sha256'])
                       for a in selection['content']]
    embedded = verification.get('embedded_content', {})
    startup = verification.get('startup_project', {})
    if (embedded.get('prepared_sha256') != selection['prepared_profile_sha256']
            or embedded.get('assets') != expected_assets
            or embedded.get('asset_count') != len(expected_assets)
            or embedded.get('packed_content_bytes') != selection['packed_content_bytes']
            or embedded.get('packed_sha256') != [a['packed_sha256'] for a in expected_assets]
            or type(startup.get('index')) is not int
            or startup['index'] != selection['startup_index']
            or startup.get('runtime_hook_linked') is not (len(selection['project_ids']) > 1)
            or verification.get('module_selection') != prepared.report['module_selection']):
        raise ValueError('Linked image differs from selected project/profile identity')
    wavetable = checked_wavetable_profile(
        verification, prepared.report['module_selection']['selected'])
    for report in (verification, artifact):
        for key in ('installable', 'hardware_tested'):
            if report.get(key) is not False:
                raise ValueError('Private build must not claim admission: ' + key)
        audit = report.get('key_audit', {})
        if audit.get('passed') is not True or audit.get('n_pending') != 0 or audit.get('n_fail') != 0:
            raise ValueError('Linked image requires a complete key audit')
    if (artifact.get('hardware_admitted') is not False
            or artifact.get('layout_passed') is not True
            or artifact.get('elf_sha256') != sha(elf)
            or verification.get('elf_sha256') != sha(elf)
            or artifact.get('app_sha256') != sha(app)
            or artifact.get('app_bytes') != len(app)
            or artifact.get('flash_layout') != verification.get('flash_layout')
            or artifact.get('app_budget_bytes') != verification.get('app_budget_bytes')
            or type(artifact.get('app_budget_bytes')) is not int
            or not 0 < len(app) <= artifact['app_budget_bytes']
            or verification.get('runtime_configuration') != expected_runtime
            or verification.get('probe_return_to_rom_seconds') != expected_runtime['return_to_rom_seconds']
            or verification.get('flash_write_range') != 'empty'):
        raise ValueError('Private diagnostic artifact identity/layout/policy mismatch')
    if require_save_service:
        service = verification.get('project_save_service', {})
        if (service.get('linked') is not True
                or service.get('compile_definition') != 'LUNAR_PROJECT_SAVE_SERVICE=1'
                or any(service.get(key) is not False for key in
                       ('storage_admitted', 'flash_io_bound', 'save_service_armed',
                        'runtime_verified', 'hardware_tested'))):
            raise ValueError('Production SAVE service must be linked and disarmed')
        codec = verification.get('state_bin_codec', {})
        linked = verification.get('linked_objects', [])
        if (codec.get('mode') != 'compact-writer'
                or codec.get('compile_definition') != 'FM1_STATE_BIN_COMPACT_WRITER=1'
                or codec.get('replaced_exactly_one') is not True
                or not codec.get('fresh_object') or not codec.get('fresh_object_sha256')
                or not codec.get('cached_object')
                or sum(row == dict(path=codec['fresh_object'],
                                   sha256=codec['fresh_object_sha256']) for row in linked) != 1
                or sum(row.get('path') == codec['fresh_object'] for row in linked) != 1
                or any(row.get('path') == codec['cached_object'] for row in linked)):
            raise ValueError('Production SAVE codec must replace exactly one cached object')
    return dict(version=1, status='linked-private-diagnostic',
                request_sha256=selection['request_sha256'],
                prepared_profile_sha256=selection['prepared_profile_sha256'],
                project_ids=selection['project_ids'], startup_index=selection['startup_index'],
                startup_project_id=selection['startup_project_id'],
                runtime_hook_linked=startup['runtime_hook_linked'],
                module_selection=prepared.report['module_selection'],
                **wavetable,
                embedded_content=embedded,
                content=expected_assets, runtime_configuration=expected_runtime,
                app_sha256=sha(app), elf_sha256=sha(elf),
                app_bytes=len(app), app_budget_bytes=artifact['app_budget_bytes'],
                installable=False, hardware_admitted=False, hardware_tested=False,
                native_ram_verified=False, native_playback_verified=False,
                full_song_default_accepted=False)


def wavetable_build_flags(profile):
    if profile == WAVETABLE_PROFILE:
        return ['--shapes-voices', str(SHAPES_VOICES), '--indexed-tft',
                '--compressed-wavetables', '--flash-plaits-wavetables']
    if profile == SHAPES8_WAVETABLE_PROFILE:
        return ['--shapes-voices', '8', '--indexed-tft', '--compressed-wavetables']
    raise ValueError('Unsupported named wavetable profile')


def read_report(path):
    return json.loads(bounded_read(path, 16 * 1048576), object_pairs_hook=unique_object)


def build_selection(request, state_tool, toolchain, catalogue, output, *,
                    runtime_mode='diagnostic', wavetable_profile=WAVETABLE_PROFILE):
    if runtime_mode not in ('diagnostic', 'song-diagnostic'):
        raise ValueError('Only bounded diagnostic runtime modes are supported')
    profile_flags = wavetable_build_flags(wavetable_profile)
    output = Path(output)
    output.mkdir(exist_ok=False)
    # Failed builds retain their diagnostic files, but never a success receipt.
    selection = prepare_selection(ROOT, request, Path(state_tool).resolve(),
                                  output / 'selection', recompress_content=True)
    prepared_dir = output / 'selection/prepared'
    manifest_sha = selection['prepared_profile_sha256']
    subprocess.run([sys.executable, str(ROOT / 'tools/native/build_application_probe.py'),
                    '--toolchain', str(Path(toolchain).resolve()),
                    '--catalogue', str(Path(catalogue).resolve()),
                    '--build', str(output / 'link'), '--runtime-mode', runtime_mode,
                    '--stack-watermark', '--flash-layout', 'expanded-d9000',
                    *profile_flags, '--prepared-profile', str(prepared_dir),
                    '--expected-profile-sha256', manifest_sha, '--link-project-loader',
                    '--link-project-save-service',
                    '--startup-project-index', str(selection['startup_index'])], check=True)
    # Recheck the prepared inputs after linking, against the retained digest.
    prepared = load_prepared_profile(prepared_dir, manifest_sha)
    receipt = checked_link_receipt(selection, prepared,
                                  read_report(output / 'link/verification.json'),
                                  read_report(output / 'link/artifact/artifact.json'),
                                  bounded_read(output / 'link/artifact/app.bin', 1048576),
                                  bounded_read(output / 'link/lunar-app-probe.elf', 16 * 1048576),
                                  runtime_mode=runtime_mode, require_save_service=True)
    receipt['project_save_service'] = read_report(output / 'link/verification.json')['project_save_service']
    receipt['state_bin_codec'] = read_report(output / 'link/verification.json')['state_bin_codec']
    receipt['verification_sha256'] = sha(bounded_read(output / 'link/verification.json', 16 * 1048576))
    receipt['artifact_receipt_sha256'] = sha(bounded_read(output / 'link/artifact/artifact.json', 16 * 1048576))
    (output / 'image.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('request', 'state-tool', 'toolchain', 'catalogue', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--runtime-mode', choices=('diagnostic', 'song-diagnostic'),
                        default='diagnostic', help='Bounded ROM-return deadline; never an admission')
    parser.add_argument('--wavetable-profile',
                        choices=(WAVETABLE_PROFILE, SHAPES8_WAVETABLE_PROFILE),
                        default=WAVETABLE_PROFILE, help='Named reviewed memory profile')
    args = parser.parse_args()
    try:
        request = json.loads(bounded_read(args.request, 65536), object_pairs_hook=unique_object)
        result = build_selection(request, args.state_tool, args.toolchain, args.catalogue,
                                 args.out, runtime_mode=args.runtime_mode,
                                 wavetable_profile=args.wavetable_profile)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
