#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export native builder choices and the production default; no device I/O.

The Make catalogue owns module IDs and kinds. Test modules remain available to
developer builds, but are not choices in the production image builder. This
document describes requests, not approved or installable firmware artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from module_selection import resolve_modules
from prepare_image_profile import GROUPS

ROOT = Path(__file__).resolve().parents[2]

# These restored examples are selectable source choices. Their duration is an
# arrangement estimate (bars * four beats / BPM), not musical or device
# acceptance. Keep profile content empty until a full-song default clears the
# separate release gates.
PRELOAD_PROJECTS = (
    dict(id='legacy-example-afterglow-relay', title='Afterglow Relay',
         source_path='engines/state/examples/afterglow-relay.lunar', bpm=92, bars=76, scenes=8),
    dict(id='legacy-example-event-horizon', title='Event Horizon',
         source_path='engines/state/examples/event-horizon.lunar', bpm=144, bars=116, scenes=8),
    dict(id='legacy-example-packet-bloom', title='Packet Bloom',
         source_path='engines/state/examples/packet-bloom.lunar', bpm=112, bars=88, scenes=8),
    dict(id='legacy-example-neon-transit', title='Neon Transit',
         source_path='engines/state/examples/neon-transit.lunar', bpm=120, bars=104, scenes=8),
)


def export_preload_projects(root: Path):
    projects = []
    for spec in PRELOAD_PROJECTS:
        source_path = root / spec['source_path']
        if not source_path.is_file() or source_path.is_symlink():
            raise ValueError('Missing regular preload source: ' + spec['source_path'])
        payload = source_path.read_bytes()
        try:
            project = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError('Invalid preload project: ' + spec['source_path']) from error
        if project.get('title') != spec['title']:
            raise ValueError('Unexpected preload project title: ' + spec['source_path'])
        projects.append({
            'id': spec['id'],
            'title': spec['title'],
            'category': 'legacy-example',
            # This path is relative to the exporter repository root. A profile
            # producer must copy the hashed bytes into its own staging directory
            # and reference that staged relative path in prepare_image_profile.
            'source_path': spec['source_path'],
            'source_sha256': hashlib.sha256(payload).hexdigest(),
            'duration_estimate': {
                'basis': 'bars * 4 beats per bar * 60 / BPM; metadata estimate',
                'bpm': spec['bpm'],
                'bars': spec['bars'],
                'scenes': spec['scenes'],
                'nominal_seconds': round(spec['bars'] * 4 * 60 / spec['bpm'], 6),
            },
            'dependency_validation': {
                'status': 'pending-packed-backend-validation',
                'dependency_scan_complete': False,
                'validated_module_ids': [],
            },
            'owner_disposition': 'legacy example; not approved as a showcase or default',
            'default_candidate': False,
        })
    return projects


def export_catalogue(root: Path, build: Path):
    catalogue_path = root / 'engines/modules/catalogue.mk'
    before = catalogue_path.read_bytes()
    _, all_modules = resolve_modules(root, build / 'all', 'all')
    groups = {group: [] for group in GROUPS}
    by_kind = {kind: group for group, kind in GROUPS.items()}
    seen = set()
    for row in all_modules['catalogue']:
        module = row['id']
        if module in seen or row['kind'] not in by_kind:
            raise ValueError('Duplicate module or unsupported catalogue kind')
        seen.add(module)
        if not module.startswith('test-'):
            groups[by_kind[row['kind']]].append(module)
    if any(not ids for ids in groups.values()):
        raise ValueError('Production catalogue has an empty module group')
    profile = dict(version=1, **groups, content=[])
    selected = [module for ids in groups.values() for module in ids]
    _, default = resolve_modules(root, build / 'default', ','.join(selected))
    if set(default['selected']) != set(selected):
        raise ValueError('Production default does not match requested catalogue')
    if catalogue_path.read_bytes() != before:
        raise ValueError('Module catalogue changed during export')
    return dict(version=1, groups=groups, projects=export_preload_projects(root),
                full_song_default={
                    'required': True,
                    'status': 'pending',
                    'blockers': [
                        'owner-approved full-song composition',
                        'exact packed-content and module-dependency validation',
                        'native full-song playback and save/reload acceptance',
                    ],
                },
                default_profile=profile,
                catalogue_sha256=hashlib.sha256(before).hexdigest(),
                default_header_sha256=default['header_sha256'],
                installable=False, native_link_verified=False,
                native_ram_verified=False, hardware_tested=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix='lunar-image-catalogue-') as scratch:
            report = export_catalogue(ROOT, Path(scratch))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
