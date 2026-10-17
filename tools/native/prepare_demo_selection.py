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

from export_image_catalogue import export_preload_projects, export_preload_sets
from prepare_image_profile import GROUPS, bounded_read, prepare, sha, unique_object
from stage_demo_profile import stage_profile
from verify_image_profile import load_prepared_profile
if __package__:
    from .diagnostic_profile_contract import validate_hall_o2_stage7_modules
else:  # Direct script execution keeps tools/native on sys.path.
    from diagnostic_profile_contract import validate_hall_o2_stage7_modules

ROOT = Path(__file__).resolve().parents[2]
_SELECTION_KEYS = {'version', *GROUPS, 'project_ids', 'startup_index'}
_PROFILE_KEYS = {'flash_layout', 'runtime_mode'}


def _validate_selection_request(request):
    """Validate the digest-bound request while keeping profile keys out of modules."""
    keys = set(request) if isinstance(request, dict) else set()
    if (not isinstance(request, dict) or type(request.get('version')) is not int
            or request['version'] != 1
            or keys not in (_SELECTION_KEYS, _SELECTION_KEYS | {'set_ids'},
                            _SELECTION_KEYS | _PROFILE_KEYS,
                            _SELECTION_KEYS | _PROFILE_KEYS | {'set_ids'})):
        raise ValueError('Expected a version-1 demo selection request')
    if keys & _PROFILE_KEYS:
        layout = request['flash_layout']
        runtime = request['runtime_mode']
        if (layout, runtime) not in (
                ('expanded-d9000', 'diagnostic'),
                ('expanded-d7000', 'song-diagnostic'),
                ('expanded-d7000', 'continuous')):
            raise ValueError('Unsupported flash layout/runtime profile pair')
        if layout == 'expanded-d7000':
            if any(not isinstance(request[group], list)
                   or any(not isinstance(module, str) for module in request[group])
                   for group in GROUPS):
                raise ValueError('Invalid module groups for expanded-d7000 profile')
            validate_hall_o2_stage7_modules(request)


def validate_build_profile(request, flash_layout, runtime_mode, wavetable_profile):
    """Require all explicit profile choices to agree before preparing a build."""
    _validate_selection_request(request)
    explicit_profile = _PROFILE_KEYS.issubset(request)
    if flash_layout == 'expanded-d7000' and not explicit_profile:
        raise ValueError('expanded-d7000 requires an explicit request profile binding')
    if explicit_profile and (request['flash_layout'], request['runtime_mode']) != (
            flash_layout, runtime_mode):
        raise ValueError('Build flags differ from digest-bound request profile')
    if explicit_profile:
        expected_wavetable_profile = {
            'expanded-d9000': 'compressed-required-banks-flash-plaits-v1',
            'expanded-d7000': 'compressed-required-banks-ram-plaits-braids-shapes8-v1',
        }[flash_layout]
        if wavetable_profile != expected_wavetable_profile:
            raise ValueError('Wavetable profile differs from digest-bound build profile')


def prepare_selection(root: Path, request: dict, state_tool: Path, output: Path,
                      *, recompress_content=False):
    if type(recompress_content) is not bool:
        raise ValueError('Recompression option must be boolean')
    request_bytes = (json.dumps(request, sort_keys=True, separators=(',', ':')) + '\n').encode()
    # Snapshot request values before invoking the exporter or external codec.
    request = json.loads(request_bytes)
    _validate_selection_request(request)
    modules = {key: request[key] for key in ('version', *GROUPS)}
    projects = export_preload_projects(root)
    sets = export_preload_sets(root, projects)
    set_ids = request.get('set_ids', [])
    output = Path(output)
    # Refuse reuse, including a dangling symlink. Never clean up someone else's
    # directory after a failed request.
    output.mkdir(exist_ok=False)
    try:
        staged = stage_profile(root, modules, projects, request['project_ids'],
                               output / 'staged', request['startup_index'], sets, set_ids)
        selection = json.loads(bounded_read(staged['selection_path'], 1048576),
                               object_pairs_hook=unique_object)
        report = prepare(staged['profile_path'], state_tool, output / 'prepared',
                         recompress_content=recompress_content)
        manifest_bytes = bounded_read(output / 'prepared/profile.json', 1048576)
        manifest_sha = sha(manifest_bytes)
        checked = load_prepared_profile(output / 'prepared', manifest_sha)
        if checked.report != report:
            raise ValueError('Prepared report changed during verification')
        assets = checked.report['content']
        if len(assets) != len(selection['sources']):
            raise ValueError('Prepared content count differs from selected content')
        content = []
        for source, asset in zip(selection['sources'], assets):
            if (asset['source'] != source['staged_path']
                    or asset['source_sha256'] != source['source_sha256']
                    or asset['kind'] != source['kind']):
                raise ValueError('Prepared content identity differs from selected catalogue row')
            if source['kind'] == 'project' and asset['dependency_scan_complete'] is not True:
                raise ValueError('Prepared project dependency scan is incomplete')
            if source['kind'] == 'set' and (asset['dependency_scan_complete'] is not False
                    or source.get('dependency_scan_complete') is not False
                    or source.get('parent_project_id') != selection['startup_project_id']):
                raise ValueError('Companion SET is not bound to selected startup project')
            content.append(dict(id=source['id'], **({'parent_project_id': source['parent_project_id']}
                                                   if source['kind'] == 'set' else {}), **asset))
        receipt = dict(version=1, status='prepared-build-inputs',
                       request_sha256=sha(request_bytes),
                       prepared_profile_sha256=manifest_sha,
                       project_ids=selection['project_ids'],
                       startup_index=selection['startup_index'],
                       startup_project_id=selection['startup_project_id'],
                       set_ids=selection['set_ids'],
                       selected_content=[dict(kind=row['kind'], id=row['id'], **(
                           {'parent_project_id': row['parent_project_id']} if row['kind'] == 'set' else {}))
                           for row in selection['sources']],
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
    parser.add_argument('--recompress-content', action='store_true')
    args = parser.parse_args()
    try:
        request = json.loads(bounded_read(args.request, 65536), object_pairs_hook=unique_object)
        receipt = prepare_selection(ROOT, request, args.state_tool.resolve(), args.out,
                                    recompress_content=args.recompress_content)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
