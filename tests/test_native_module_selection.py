"""Canonical native catalogue choices and hostile external selections."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from module_selection import resolve_modules, wavetable_namespaces


@pytest.mark.parametrize('selected,expected', [
    ([], []), (['trio'], []), (['drums'], []), (['plate'], []),
    (['macro'], ['plaits']), (['macro-heavy'], ['plaits']),
    (['macro', 'macro-heavy'], ['plaits']), (['shapes'], ['braids']),
    (['macro', 'shapes'], ['plaits', 'braids']),
    (['macro-heavy', 'shapes'], ['plaits', 'braids']),
    (['macro', 'macro-heavy', 'shapes'], ['plaits', 'braids']),
    (['trio', 'drums', 'echo'], []), (['trio', 'shapes'], ['braids']),
    (['trio', 'macro', 'drums'], ['plaits']),
    (['shapes', 'macro', 'macro-heavy'], ['plaits', 'braids']),
    (['lfo', 'env', 'arp'], []),
])
def test_wavetable_selection(selected, expected):
    assert wavetable_namespaces(selected) == expected


@pytest.mark.parametrize('specification', [
    'all', 'trio', 'trio,plate', 'trio,echo,arp', 'trio,lfo,env',
    'trio,macro,shapes', 'trio,comet,crater,drawbar', 'trio,acid-gen,acid-bass',
])
def test_native_module_selection(tmp_path, specification):
    header, report = resolve_modules(ROOT, tmp_path / 'modules', specification)
    selected = set(report['selected'])
    if specification != 'all':
        assert selected == set(specification.split(','))
    else:
        assert len([r for r in report['catalogue'] if r['kind'] == 'sound']) == 14
    text = header.decode()
    for row in report['catalogue']:
        macro = row['id'].upper().replace('-', '_')
        assert f'#define FM1_WITH_{macro} {int(row["selected"])}' in text
        if not row['selected']:
            assert f'{{ "{row["id"]}", "{row["kind"]}", "list", 0 }}' in text
    # Every selected module's shared objects are in the union of its dependencies.
    if 'macro' in selected and 'shapes' in selected:
        rows = {r['id']: r for r in report['catalogue']}
        assert set(rows['macro']['objects']) & set(rows['shapes']['objects'])


@pytest.mark.parametrize('specification', [
    '', 'trio,trio', 'trio,no-such-engine', 'plate,echo', 'trio,$(shell touch /tmp/unsafe)',
    'trio\nplate', '/tmp/custom.list', 'trio,',
])
def test_native_module_selection_refuses(tmp_path, specification):
    with pytest.raises(ValueError):
        resolve_modules(ROOT, tmp_path / 'modules', specification)
