"""Production builder requests must resolve through the real Make catalogue."""
from pathlib import Path
import sys
import hashlib
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from export_image_catalogue import export_catalogue
from module_selection import resolve_modules


@pytest.mark.parametrize('case', range(30))
def test_exported_builder_requests(tmp_path, case):
    report = export_catalogue(ROOT, tmp_path / 'catalogue')
    groups = report['groups']
    assert {group: len(ids) for group, ids in groups.items()} == {
        'engines': 13, 'effects': 24, 'midi': 2, 'modulation': 16}
    assert not any(report[key] for key in (
        'installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))
    assert report['default_profile'] == dict(version=1, **groups, content=[])
    assert report['full_song_default'] == {
        'required': True, 'status': 'pending',
        'blockers': [
            'owner-approved full-song composition',
            'exact packed-content and module-dependency validation',
            'native full-song playback and save/reload acceptance',
        ],
    }
    assert not any(module.startswith('test-') for ids in groups.values() for module in ids)
    if case == 0:
        projects = report['projects']
        assert [p['id'] for p in projects] == [
            'legacy-example-afterglow-relay', 'legacy-example-event-horizon',
            'legacy-example-packet-bloom', 'legacy-example-neon-transit',
            'replacement-showcase-candidate-afterglow-relay',
            'replacement-showcase-candidate-event-horizon',
            'replacement-showcase-candidate-packet-bloom',
            'replacement-showcase-candidate-satellite-hearts']
        expected = [
            ('Afterglow Relay', 'afterglow-relay.lunar', 92, 76, 8, 'legacy-example', None),
            ('Event Horizon', 'event-horizon.lunar', 144, 116, 8, 'legacy-example', None),
            ('Packet Bloom', 'packet-bloom.lunar', 112, 88, 8, 'legacy-example', None),
            ('Neon Transit', 'neon-transit.lunar', 120, 104, 8, 'legacy-example', None),
            ('Afterglow Relay', 'replacement-showcases/afterglow-relay-showcase.lunar',
             104, 44, 4, 'replacement-showcase-candidate',
             '53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f'),
            ('Event Horizon', 'replacement-showcases/event-horizon-showcase.lunar',
             150, 68, 7, 'replacement-showcase-candidate',
             '22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f'),
            ('Packet Bloom', 'replacement-showcases/packet-bloom-showcase.lunar',
             82, 40, 5, 'replacement-showcase-candidate',
             '853be1d05bd206d9fce928e5d36944d932491a9b9c69cf79d96e6f78392700e7'),
            ('Satellite Hearts', 'replacement-showcases/satellite-hearts.lunar',
             124, 60, 6, 'replacement-showcase-candidate',
             '090996484a125f5bde3fe4fb0a6dc3284cf7a260d6c6603298206921e78ed5d6'),
        ]
        for project, (title, filename, bpm, bars, scenes, category, pinned_sha256) in zip(
                projects, expected):
            path = ROOT / 'engines/state/examples' / filename
            payload = path.read_bytes()
            assert project['title'] == title
            assert project['source_path'] == f'engines/state/examples/{filename}'
            assert project['source_sha256'] == hashlib.sha256(payload).hexdigest()
            if pinned_sha256 is not None:
                assert project['source_sha256'] == pinned_sha256
            assert json.loads(payload)['title'] == title
            assert project['category'] == category
            assert project['duration_estimate'] == {
                'basis': 'bars * 4 beats per bar * 60 / BPM; metadata estimate',
                'bpm': bpm, 'bars': bars, 'scenes': scenes,
                'nominal_seconds': round(bars * 4 * 60 / bpm, 6),
            }
            assert project['dependency_validation'] == {
                'status': 'pending-packed-backend-validation',
                'dependency_scan_complete': False,
                'validated_module_ids': [],
            }
            assert project['default_candidate'] is False
            if category == 'replacement-showcase-candidate':
                assert project['source_provenance'] == {
                    'commit': 'fb92cc0d4c312bbc77866c915d6fb8f159f5f92d',
                    'path': 'engines/state/examples/' +
                    filename.removeprefix('replacement-showcases/'),
                }
                adaptations = {
                    'replacement-showcases/event-horizon-showcase.lunar': {
                        'kind': 'scene-label-compatibility',
                        'original_sha256': '0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c',
                        'scene_label_map': [['Suspense', 'Tense'], ['OpenSky', 'Sky']],
                    },
                    'replacement-showcases/packet-bloom-showcase.lunar': {
                        'kind': 'scene-label-compatibility',
                        'original_sha256': 'eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731',
                        'scene_label_map': [['Packets', 'Packet'], ['Dissolve', 'Fade']],
                    },
                }
                if filename in adaptations:
                    assert project['source_adaptation'] == adaptations[filename]
                else:
                    assert 'source_adaptation' not in project
                assert 'owner musical acceptance pending' in project['owner_disposition']
            else:
                assert 'not approved' in project['owner_disposition']
    if case == 0:
        chosen = [module for ids in groups.values() for module in ids]
    else:
        chosen = [ids[(case - 1) % len(ids)] for ids in groups.values()]
    header, resolved = resolve_modules(ROOT, tmp_path / 'request', ','.join(chosen))
    assert set(resolved['selected']) == set(chosen)
    if case == 0:
        assert resolved['header_sha256'] == report['default_header_sha256']
    for module in chosen:
        assert f'#define FM1_WITH_{module.upper().replace("-", "_")} 1' in header.decode()
