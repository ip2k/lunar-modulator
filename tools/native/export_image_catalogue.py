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

# These restored projects are selectable source choices. Duration is an
# arrangement estimate (bars * four beats / BPM), not a runtime receipt,
# musical approval, or device acceptance. Keep profile content empty until a
# owner-approved musical choice clears the separate release gates.
PRELOAD_PROJECTS = (
    dict(id='legacy-example-afterglow-relay', title='Afterglow Relay',
         source_path='engines/state/examples/afterglow-relay.lunar', bpm=92, bars=76, scenes=8),
    dict(id='legacy-example-event-horizon', title='Event Horizon',
         source_path='engines/state/examples/event-horizon.lunar', bpm=144, bars=116, scenes=8),
    dict(id='legacy-example-packet-bloom', title='Packet Bloom',
         source_path='engines/state/examples/packet-bloom.lunar', bpm=112, bars=88, scenes=8),
    dict(id='legacy-example-neon-transit', title='Neon Transit',
         source_path='engines/state/examples/neon-transit.lunar', bpm=120, bars=104, scenes=8),
    dict(id='replacement-showcase-candidate-afterglow-relay', title='Afterglow Relay',
         source_path='engines/state/examples/replacement-showcases/afterglow-relay-showcase.lunar',
         bpm=104, bars=44, scenes=4, category='replacement-showcase-candidate',
         owner_disposition='replacement showcase candidate; owner musical acceptance pending',
         source_commit='fb92cc0d4c312bbc77866c915d6fb8f159f5f92d',
         source_asset_path='engines/state/examples/afterglow-relay-showcase.lunar',
         source_sha256='53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f'),
    dict(id='replacement-showcase-candidate-event-horizon', title='Event Horizon',
         source_path='engines/state/examples/replacement-showcases/event-horizon-showcase.lunar',
         bpm=150, bars=68, scenes=7, category='replacement-showcase-candidate',
         owner_disposition='owner-approved musical full-song default; native playback and release admission pending',
         source_commit='fb92cc0d4c312bbc77866c915d6fb8f159f5f92d',
         source_asset_path='engines/state/examples/event-horizon-showcase.lunar',
         source_sha256='22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f',
         original_sha256='0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c',
         adaptation_kind='scene-label-compatibility',
         scene_label_map=[['Suspense', 'Tense'], ['OpenSky', 'Sky']]),
    dict(id='replacement-showcase-candidate-packet-bloom', title='Packet Bloom',
         source_path='engines/state/examples/replacement-showcases/packet-bloom-showcase.lunar',
         bpm=82, bars=40, scenes=5, category='replacement-showcase-candidate',
         owner_disposition='replacement showcase candidate; owner musical acceptance pending',
         source_commit='fb92cc0d4c312bbc77866c915d6fb8f159f5f92d',
         source_asset_path='engines/state/examples/packet-bloom-showcase.lunar',
         source_sha256='853be1d05bd206d9fce928e5d36944d932491a9b9c69cf79d96e6f78392700e7',
         original_sha256='eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731',
         adaptation_kind='scene-label-compatibility',
         scene_label_map=[['Packets', 'Packet'], ['Dissolve', 'Fade']]),
    dict(id='replacement-showcase-candidate-satellite-hearts', title='Satellite Hearts',
         source_path='engines/state/examples/replacement-showcases/satellite-hearts.lunar',
         bpm=124, bars=60, scenes=6, category='replacement-showcase-candidate',
         owner_disposition='replacement showcase candidate; owner musical acceptance pending',
         source_commit='fb92cc0d4c312bbc77866c915d6fb8f159f5f92d',
         source_asset_path='engines/state/examples/satellite-hearts.lunar',
         source_sha256='090996484a125f5bde3fe4fb0a6dc3284cf7a260d6c6603298206921e78ed5d6'),
)


def _source_module_dependencies(project, module_groups):
    """Read source IDs for chooser preflight; packed validation stays backend-only."""
    if not isinstance(project, dict):
        raise ValueError("Preload project root must be an object")
    dependencies = {group: set() for group in GROUPS}

    def rows(value, label, *, nullable=False):
        if not isinstance(value, list) or any(
                not isinstance(row, dict) and not (nullable and row is None) for row in value):
            raise ValueError("Invalid preload project " + label)
        return value

    for sound in rows(project.get("sounds", []), "sounds"):
        engine = sound.get("engine")
        if engine:
            if not isinstance(engine, str):
                raise ValueError("Invalid sound engine identifier")
            dependencies["engines"].add(engine)
        for field, group in (("inserts", "effects"), ("midi_fx", "midi")):
            for effect in rows(sound.get(field, []), "sounds." + field, nullable=True):
                if effect is None:
                    continue
                identifier = effect.get("engine")
                if identifier:
                    if not isinstance(identifier, str):
                        raise ValueError("Invalid " + field + " identifier")
                    dependencies[group].add(identifier)
    for effect in rows(project.get("master", []), "master"):
        identifier = effect.get("engine")
        if identifier:
            if not isinstance(identifier, str):
                raise ValueError("Invalid master effect identifier")
            dependencies["effects"].add(identifier)
    mod = project.get("mod", {})
    if not isinstance(mod, dict):
        raise ValueError("Invalid preload project modulation section")
    for source in rows(mod.get("rack", []), "mod.rack"):
        identifier = source.get("kind")
        if identifier:
            if not isinstance(identifier, str):
                raise ValueError("Invalid modulation identifier")
            dependencies["modulation"].add(identifier)
    result = {group: sorted(values) for group, values in dependencies.items()}
    if module_groups is not None:
        for group, identifiers in result.items():
            if any(identifier not in module_groups[group] for identifier in identifiers):
                raise ValueError("Source dependency is absent from canonical " + group + " catalogue")
    return result


def export_preload_projects(root: Path, module_groups=None):
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
        source_sha256 = hashlib.sha256(payload).hexdigest()
        if spec.get('source_sha256') and source_sha256 != spec['source_sha256']:
            raise ValueError('Preload source differs from pinned asset: ' + spec['source_path'])
        projects.append({
            'id': spec['id'],
            'title': spec['title'],
            'category': spec.get('category', 'legacy-example'),
            # This path is relative to the exporter repository root. A profile
            # producer must copy the hashed bytes into its own staging directory
            # and reference that staged relative path in prepare_image_profile.
            'source_path': spec['source_path'],
            'source_sha256': source_sha256,
            **({'source_provenance': {
                'commit': spec['source_commit'], 'path': spec['source_asset_path'],
            }} if spec.get('source_commit') else {}),
            **({'source_adaptation': {
                'kind': spec['adaptation_kind'],
                'original_sha256': spec['original_sha256'],
                'scene_label_map': spec['scene_label_map'],
            }} if spec.get('adaptation_kind') else {}),
            'duration_estimate': {
                'basis': 'bars * 4 beats per bar * 60 / BPM; metadata estimate',
                'bpm': spec['bpm'],
                'bars': spec['bars'],
                'scenes': spec['scenes'],
                'nominal_seconds': round(spec['bars'] * 4 * 60 / spec['bpm'], 6),
            },
            # Hash-bound chooser feedback only; packed records remain authoritative.
            'source_module_dependencies': _source_module_dependencies(project, module_groups),
            'source_dependency_scan_complete': True,
            'dependency_validation': {
                'status': 'pending-packed-backend-validation',
                'dependency_scan_complete': False,
                'validated_module_ids': [],
            },
            'owner_disposition': spec.get(
                'owner_disposition', 'legacy example; not approved as a showcase or default'),
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
    return dict(version=1, groups=groups, projects=export_preload_projects(root, groups),
                full_song_default={
                    'required': True,
                    'status': 'owner-approved',
                    'project_id': 'replacement-showcase-candidate-event-horizon',
                    'musical_choice_approved': True,
                    'blockers': [
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
