#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare selected catalogue demos and retain ordered startup identity.

Offline build controller: accepts IDs, not client-provided catalogue paths or
hashes. Packed bytes are verified build inputs; a native link and hardware
acceptance are separate gates before flashing.
"""
import argparse
import json
from pathlib import Path
import shutil

from export_image_catalogue import export_preload_projects
from prepare_image_profile import GROUPS, bounded_read, prepare, sha, unique_object
from stage_demo_profile import stage_profile
from verify_image_profile import load_prepared_profile

ROOT = Path(__file__).resolve().parents[2]


def prepare_selection(root: Path, request: dict, state_tool: Path, output: Path):
    request_bytes = (json.dumps(request, sort_keys=True, separators=(',', ':')) + '\n').encode()
    # Snapshot request values before invoking the exporter or external codec.
    request = json.loads(request_bytes)
    if (not isinstance(request, dict) or type(request.get('version')) is not int
            or request['version'] != 1
            or set(request) != {'version', *GROUPS, 'project_ids', 'startup_index'}):
        raise ValueError('Expected a version-1 demo selection request')
    modules = {key: request[key] for key in ('version', *GROUPS)}
    projects = export_preload_projects(root)
    output = Path(output)
    # Refuse reuse, including a dangling symlink. Never clean up someone else's
    # directory after a failed request.
    output.mkdir(exist_ok=False)
    try:
        staged = stage_profile(root, modules, projects, request['project_ids'],
                               output / 'staged', request['startup_index'])
        selection = json.loads(bounded_read(staged['selection_path'], 1048576),
                               object_pairs_hook=unique_object)
        report = prepare(staged['profile_path'], state_tool, output / 'prepared')
        manifest_bytes = bounded_read(output / 'prepared/profile.json', 1048576)
        manifest_sha = sha(manifest_bytes)
        checked = load_prepared_profile(output / 'prepared', manifest_sha)
        if checked.report != report:
            raise ValueError('Prepared report changed during verification')
        assets = checked.report['content']
        if len(assets) != len(selection['sources']):
            raise ValueError('Prepared content count differs from selected projects')
        content = []
        for source, asset in zip(selection['sources'], assets):
            if (asset['source'] != source['staged_path']
                    or asset['source_sha256'] != source['source_sha256']
                    or asset['kind'] != 'project'
                    or asset['dependency_scan_complete'] is not True):
                raise ValueError('Prepared content identity differs from selected project')
            content.append(dict(id=source['id'], **asset))
        receipt = dict(version=1, status='prepared-build-inputs',
                       request_sha256=sha(request_bytes),
                       prepared_profile_sha256=manifest_sha,
                       project_ids=selection['project_ids'],
                       startup_index=selection['startup_index'],
                       startup_project_id=selection['startup_project_id'],
                       content=content, packed_content_bytes=report['packed_content_bytes'],
                       state_tool_sha256=report['state_tool_sha256'],
                       installable=False, native_link_verified=False,
                       native_ram_verified=False, hardware_tested=False)
        (output / 'request.json').write_bytes(request_bytes)
        # This is the controller's success receipt. The downstream linker must
        # use its manifest digest and startup index together, not infer either.
        (output / 'selection.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--state-tool', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(bounded_read(args.request, 65536), object_pairs_hook=unique_object)
        receipt = prepare_selection(ROOT, request, args.state_tool.resolve(), args.out)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
