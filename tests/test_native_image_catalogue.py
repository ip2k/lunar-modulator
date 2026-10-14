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
            'legacy-example-packet-bloom', 'legacy-example-neon-transit']
        expected = [
            ('Afterglow Relay', 'afterglow-relay.lunar', 92, 76, 8),
            ('Event Horizon', 'event-horizon.lunar', 144, 116, 8),
            ('Packet Bloom', 'packet-bloom.lunar', 112, 88, 8),
            ('Neon Transit', 'neon-transit.lunar', 120, 104, 8),
        ]
        for project, (title, filename, bpm, bars, scenes) in zip(projects, expected):
            path = ROOT / 'engines/state/examples' / filename
            payload = path.read_bytes()
            assert project['title'] == title
            assert project['source_path'] == f'engines/state/examples/{filename}'
            assert project['source_sha256'] == hashlib.sha256(payload).hexdigest()
            assert json.loads(payload)['title'] == title
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
