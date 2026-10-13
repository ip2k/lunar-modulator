"""Build-input preparation against the real host state codec."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from prepare_image_profile import prepare


@pytest.mark.parametrize('case', [
    'empty-content', 'project', 'set', 'both', 'missing-engine', 'missing-effect',
    'wrong-group', 'duplicate-module', 'unknown-module', 'traversal', 'absolute',
    'symlink', 'duplicate-content', 'invalid-content', 'duplicate-key', 'oversized',
])
def test_image_profile(tmp_path, case):
    tool = Path(os.environ['FM1_STATE_TOOL'])
    doc = dict(version=1, engines=['trio', 'drums', 'shapes', 'macro', 'dx7'],
               effects=['filter', 'drive', 'echo', 'hall', 'limit'], midi=['arp'],
               modulation=['lfo', 'env', 'chance'], content=[])
    for name in ('first-orbit.lunar', 'orbit.set.movy1'):
        shutil.copy(ROOT / 'tests/fixtures/state/1.0' / name, tmp_path / name)
    if case in ('project', 'both', 'missing-engine', 'missing-effect'):
        doc['content'].append('first-orbit.lunar')
    if case in ('set', 'both'):
        doc['content'].append('orbit.set.movy1')
    if case == 'missing-engine': doc['engines'].remove('shapes')
    if case == 'missing-effect': doc['effects'].remove('filter')
    if case == 'wrong-group': doc['effects'].append('comet')
    if case == 'duplicate-module': doc['engines'].append('trio')
    if case == 'unknown-module': doc['engines'].append('absent')
    if case == 'traversal': doc['content'] = ['../outside.lunar']
    if case == 'absolute': doc['content'] = [str(tmp_path / 'first-orbit.lunar')]
    if case == 'symlink':
        (tmp_path / 'escape').symlink_to(tmp_path.parent / 'outside.lunar')
        doc['content'] = ['escape']
    if case == 'duplicate-content': doc['content'] = ['first-orbit.lunar'] * 2
    if case == 'invalid-content':
        (tmp_path / 'invalid').write_bytes(b'not a Lunar state')
        doc['content'] = ['invalid']
    if case == 'oversized':
        (tmp_path / 'large').write_bytes(b'x' * 1048577)
        doc['content'] = ['large']
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps(doc))
    if case == 'duplicate-key':
        profile.write_text('{"version":1,"version":1,"engines":["trio"]}')
    out = tmp_path / 'prepared'
    if case not in ('empty-content', 'project', 'set', 'both'):
        messages = {'missing-engine': 'omitted modules: shapes',
                    'missing-effect': 'omitted modules: filter',
                    'wrong-group': 'wrong group', 'duplicate-module': 'unique literal',
                    'unknown-module': 'catalogue rejected', 'traversal': 'remain within',
                    'absolute': 'remain within', 'symlink': 'remain within',
                    'duplicate-content': 'unique relative', 'invalid-content': 'State tool rejected',
                    'duplicate-key': 'Duplicate profile key', 'oversized': 'byte bound'}
        with pytest.raises(ValueError, match=messages[case]):
            prepare(profile, tool, out)
        assert not (out / 'profile.json').exists()
        return
    report = prepare(profile, tool, out)
    assert json.loads((out / 'profile.json').read_text()) == report
    assert len(report['content']) == len(doc['content'])
    assert not any(report[k] for k in ('installable', 'native_link_verified',
                                      'native_ram_verified', 'hardware_tested'))
    for asset in report['content']:
        payload = (out / asset['packed']).read_bytes()
        assert len(payload) == asset['bytes']
        assert hashlib.sha256(payload).hexdigest() == asset['packed_sha256']
        assert set(asset['dependencies']) <= set(report['module_selection']['selected'])
        assert not asset['sequence_semantics_verified']
        assert asset['dependency_scan_complete'] == (asset['kind'] == 'project')
    # Refuse reuse even after success, rather than leave stale accepted metadata.
    with pytest.raises(FileExistsError):
        prepare(profile, tool, out)
