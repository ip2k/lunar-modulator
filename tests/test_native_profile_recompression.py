# SPDX-License-Identifier: MIT
"""Real codec admission of recompressed catalogue content; no target fit claim."""
import os
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools/native'))
from export_image_catalogue import export_catalogue
from prepare_demo_selection import prepare_selection
from prepare_image_profile import command, prepare, sha
from verify_image_profile import load_prepared_profile


def request(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue')
    return dict(version=1, **catalogue['groups'],
                project_ids=[p['id'] for p in catalogue['projects']][::-1],
                startup_index=2)


def test_all_demo_encodings_preserve_native_records_and_selection(tmp_path):
    selection = request(tmp_path)
    tool = Path(os.environ['FM1_STATE_TOOL'])
    original = prepare_selection(ROOT, selection, tool, tmp_path / 'original')
    compressed = prepare_selection(ROOT, selection, tool, tmp_path / 'compressed',
                                   recompress_content=True)
    assert compressed['project_ids'] == selection['project_ids']
    assert compressed['startup_project_id'] == original['startup_project_id']
    assert compressed['request_sha256'] == original['request_sha256']
    assert compressed['packed_content_bytes'] <= original['packed_content_bytes']
    checked = load_prepared_profile(tmp_path / 'compressed/prepared',
                                   compressed['prepared_profile_sha256'])
    for index, (before, after) in enumerate(zip(original['content'], compressed['content'])):
        assert before['source_sha256'] == after['source_sha256']
        assert before['dependencies'] == after['dependencies']
        assert command(tool, 'records', tmp_path / 'original/prepared' / before['packed']) == command(
            tool, 'records', tmp_path / 'compressed/prepared' / after['packed'])
        encoding = after['compression']
        assert encoding['encoder'] == 'host-zlib-raw-4k'
        assert encoding['input_sha256'] == before['packed_sha256']
        assert encoding['output_sha256'] == after['packed_sha256']
        assert encoding['output_bytes'] == len(checked.packed_content[index])
        assert encoding['records_equal'] is True
        assert sha(checked.packed_content[index]) == after['packed_sha256']
        assert not after['sequence_semantics_verified']
    assert all(compressed[k] is False for k in
               ('installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))


def test_changed_native_records_refuse_and_remove_new_selection(tmp_path, monkeypatch):
    import recompress_project
    from tools import lunar_state
    selection = request(tmp_path)
    selection['project_ids'] = selection['project_ids'][:1]
    selection['startup_index'] = 0

    def change_record(data):
        records, _ = lunar_state.read_bin(data)
        head = next(record for record in records if record['rec'] == 'info' and record.get('key') == 'name')
        head['text'] = 'CHANGED DEMO'
        return lunar_state.write_bin(records), {}

    monkeypatch.setattr(recompress_project, 'recompress', change_record)
    output = tmp_path / 'refused'
    with pytest.raises(ValueError, match='Native records changed'):
        prepare_selection(ROOT, selection, Path(os.environ['FM1_STATE_TOOL']), output,
                          recompress_content=True)
    assert not output.exists()


def test_invalid_option_is_refused_before_output(tmp_path):
    with pytest.raises(ValueError, match='boolean'):
        prepare_selection(ROOT, {}, tmp_path / 'unused', tmp_path / 'absent',
                          recompress_content='yes')
    assert not (tmp_path / 'absent').exists()


def test_project_and_set_profile_recompression_preserves_native_records(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue')
    names = ['first-orbit.lunar', 'orbit.set.movy1']
    for name in names:
        shutil.copy(ROOT / 'tests/fixtures/state/1.0' / name, tmp_path / name)
    profile = tmp_path / 'profile.json'
    profile.write_text(json.dumps(dict(version=1, **catalogue['groups'], content=names)))
    tool = Path(os.environ['FM1_STATE_TOOL'])
    original = prepare(profile, tool, tmp_path / 'original')
    compressed = prepare(profile, tool, tmp_path / 'compressed', recompress_content=True)
    assert [a['kind'] for a in compressed['content']] == ['project', 'set']
    for before, after in zip(original['content'], compressed['content']):
        assert command(tool, 'records', tmp_path / 'original' / before['packed']) == command(
            tool, 'records', tmp_path / 'compressed' / after['packed'])
        assert after['bytes'] <= before['bytes']
    assert compressed['content'][1]['dependency_scan_complete'] is False
