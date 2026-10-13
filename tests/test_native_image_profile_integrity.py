"""Prepared content must survive the handoff to a later build worker intact."""
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from prepare_image_profile import prepare, sha
from verify_image_profile import load_prepared_profile


@pytest.mark.parametrize('case', [
    'empty', 'project', 'set', 'both', 'manifest', 'wrong-digest', 'header',
    'source', 'packed', 'missing', 'promotion', 'asset-path', 'symlink',
    'manifest-bound', 'duplicate-key', 'invalid-digest',
])
def test_prepared_inputs_integrity(tmp_path, case):
    content = [] if case == 'empty' else ['first-orbit.lunar']
    if case == 'set': content = ['orbit.set.movy1']
    if case == 'both': content.append('orbit.set.movy1')
    for name in content:
        shutil.copy(ROOT / 'tests/fixtures/state/1.0' / name, tmp_path / name)
    profile = tmp_path / 'input.json'
    profile.write_text(json.dumps(dict(version=1,
        engines=['trio', 'drums', 'shapes', 'macro', 'dx7'],
        effects=['filter', 'drive', 'echo', 'hall', 'limit'], midi=['arp'],
        modulation=['lfo', 'env', 'chance'], content=content)))
    out = tmp_path / 'prepared'
    report = prepare(profile, Path(os.environ['FM1_STATE_TOOL']), out)
    manifest = out / 'profile.json'
    digest = sha(manifest.read_bytes())
    if case in ('empty', 'project', 'set', 'both'):
        result = load_prepared_profile(out, digest)
        assert result.report == report
        assert result.module_header == (out / 'fm1_modules.h').read_bytes()
        assert result.packed_content == tuple((out / a['packed']).read_bytes()
                                             for a in report['content'])
        # Checked bytes remain usable after worker files are removed/replaced.
        shutil.rmtree(out)
        assert sum(map(len, result.packed_content)) == report['packed_content_bytes']
        return
    messages = dict(manifest='manifest digest', **{'wrong-digest': 'manifest digest'},
        header='header digest', source='source digest', packed='digest or length',
        missing='regular non-symlink', promotion='must not claim firmware',
        **{'asset-path': 'Noncanonical', 'manifest-bound': 'byte bound',
           'duplicate-key': 'Duplicate profile key', 'invalid-digest': 'lowercase SHA256'},
        symlink='regular non-symlink')
    if case == 'manifest': manifest.write_bytes(manifest.read_bytes() + b' ')
    if case == 'wrong-digest': digest = '0' * 64
    if case in ('header', 'source', 'packed'):
        name = {'header': 'fm1_modules.h', 'source': 'content-00.source',
                'packed': 'content-00.bin'}[case]
        path = out / name
        path.write_bytes(path.read_bytes() + b'x')
    if case == 'missing': (out / 'content-00.bin').unlink()
    if case in ('promotion', 'asset-path'):
        if case == 'promotion': report['installable'] = True
        else: report['content'][0]['packed'] = '../input.json'
        manifest.write_text(json.dumps(report))
        # Even a controller-provided digest cannot promote this input format.
        digest = sha(manifest.read_bytes())
    if case == 'symlink':
        header = out / 'fm1_modules.h'
        outside = tmp_path / 'header.h'
        header.rename(outside)
        header.symlink_to(outside)
    if case == 'manifest-bound': manifest.write_bytes(b'x' * 1048577)
    if case == 'duplicate-key':
        manifest.write_text('{"version":1,"version":1}')
        digest = sha(manifest.read_bytes())
    if case == 'invalid-digest': digest = 'not a SHA256'
    with pytest.raises(ValueError, match=messages[case]):
        load_prepared_profile(out, digest)
