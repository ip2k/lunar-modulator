#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Connect ordered demo selection to an audited private diagnostic image.

Operator-owned compiler/catalogue paths never come from the browser request.
This controller produces build evidence, not a package or permission to flash.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from prepare_demo_selection import prepare_selection
from prepare_image_profile import bounded_read, sha, unique_object
from verify_image_profile import load_prepared_profile

ROOT = Path(__file__).resolve().parents[2]


def checked_link_receipt(selection, prepared, verification, artifact, app, elf, *, require_save_service=False):
    """Bind ordered choices and actual output bytes to one completed link."""
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
            or startup.get('runtime_hook_linked') is not True
            or verification.get('module_selection') != prepared.report['module_selection']):
        raise ValueError('Linked image differs from selected project/profile identity')
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
            or verification.get('probe_return_to_rom_seconds') != 20
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
                module_selection=prepared.report['module_selection'],
                embedded_content=embedded,
                content=expected_assets, app_sha256=sha(app), elf_sha256=sha(elf),
                app_bytes=len(app), app_budget_bytes=artifact['app_budget_bytes'],
                installable=False, hardware_admitted=False, hardware_tested=False,
                native_ram_verified=False, native_playback_verified=False,
                full_song_default_accepted=False)


def read_report(path):
    return json.loads(bounded_read(path, 16 * 1048576), object_pairs_hook=unique_object)


def build_selection(request, state_tool, toolchain, catalogue, output):
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
                    '--build', str(output / 'link'), '--runtime-mode', 'diagnostic',
                    '--stack-watermark', '--flash-layout', 'expanded-d9000',
                    '--shapes-voices', '12', '--indexed-tft', '--compressed-wavetables',
                    '--flash-plaits-wavetables', '--prepared-profile', str(prepared_dir),
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
                                  require_save_service=True)
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
    args = parser.parse_args()
    try:
        request = json.loads(bounded_read(args.request, 65536), object_pairs_hook=unique_object)
        result = build_selection(request, args.state_tool, args.toolchain, args.catalogue, args.out)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
