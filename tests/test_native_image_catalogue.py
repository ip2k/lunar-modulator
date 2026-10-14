"""Production builder requests must resolve through the real Make catalogue."""
from pathlib import Path
import sys

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
    assert not any(module.startswith('test-') for ids in groups.values() for module in ids)
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
