# SPDX-License-Identifier: MIT
"""Safe conversion of exported project choices into profile-local inputs."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from export_image_catalogue import PRELOAD_PROJECTS, export_preload_projects
from prepare_image_profile import GROUPS
from stage_demo_profile import stage_profile


def fixture_catalogue(root, selected=(0, 1)):
    records = []
    payloads = {}
    for index in selected:
        spec = PRELOAD_PROJECTS[index]
        path = root / spec['source_path']
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'title': spec['title'], 'fixture': index}).encode()
        path.write_bytes(payload)
        payloads[spec['id']] = payload
        records.append({
            'id': spec['id'], 'title': spec['title'],
            'source_path': spec['source_path'],
            'source_sha256': hashlib.sha256(payload).hexdigest(),
        })
    return records, payloads


def module_profile():
    return {'version': 1, **{group: (['macro'] if group == 'engines' else [])
                            for group in GROUPS}}


def test_stages_exact_bytes_in_selection_order_and_retains_startup_index(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    records, payloads = fixture_catalogue(root)
    selected = [PRELOAD_PROJECTS[1]['id'], PRELOAD_PROJECTS[0]['id']]
    out = tmp_path / 'request'

    result = stage_profile(root, module_profile(), records, selected, out, startup_index=1)

    profile = json.loads((out / 'profile.json').read_text())
    assert profile['content'] == [f'projects/{project_id}.lunar' for project_id in selected]
    assert [(out / path).read_bytes() for path in profile['content']] == [
        payloads[project_id] for project_id in selected]
    selection = json.loads((out / 'selection.json').read_text())
    assert selection['project_ids'] == selected
    assert selection['startup_index'] == 1
    assert selection['startup_project_id'] == selected[1]
    assert result['project_ids'] == selected
    assert result['startup_project_id'] == selected[1]
    assert result['profile_path'] == out / 'profile.json'


def test_stages_a_current_exporter_catalogue_snapshot(tmp_path):
    projects = export_preload_projects(ROOT)
    selected = [projects[0]['id']]
    out = tmp_path / 'request'

    stage_profile(ROOT, module_profile(), projects, selected, out)

    content_path = json.loads((out / 'profile.json').read_text())['content'][0]
    source_path = ROOT / projects[0]['source_path']
    staged_path = out / content_path
    assert staged_path.read_bytes() == source_path.read_bytes()
    assert hashlib.sha256(staged_path.read_bytes()).hexdigest() == projects[0]['source_sha256']


@pytest.mark.parametrize('selection', [
    ['missing-demo'],
    [PRELOAD_PROJECTS[0]['id'], PRELOAD_PROJECTS[0]['id']],
])
def test_rejects_unknown_or_duplicate_selection_without_output(tmp_path, selection):
    root = tmp_path / 'repo'
    root.mkdir()
    records, _ = fixture_catalogue(root, selected=(0,))
    out = tmp_path / 'request'

    with pytest.raises(ValueError):
        stage_profile(root, module_profile(), records, selection, out)
    assert not out.exists()


def test_rejects_source_changed_after_catalogue_hash_was_exported(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    records, _ = fixture_catalogue(root, selected=(0,))
    source = root / records[0]['source_path']
    source.write_bytes(source.read_bytes() + b'changed')
    out = tmp_path / 'request'

    with pytest.raises(ValueError, match='SHA-256'):
        stage_profile(root, module_profile(), records, [records[0]['id']], out)
    assert not out.exists()


def test_rejects_symlink_escape_even_when_target_bytes_match_hash(tmp_path):
    root = tmp_path / 'repo'
    outside = tmp_path / 'outside.lunar'
    root.mkdir()
    records, payloads = fixture_catalogue(root, selected=(0,))
    source = root / records[0]['source_path']
    source.unlink()
    outside.write_bytes(payloads[records[0]['id']])
    source.symlink_to(outside)
    out = tmp_path / 'request'

    with pytest.raises(ValueError, match='symlink'):
        stage_profile(root, module_profile(), records, [records[0]['id']], out)
    assert not out.exists()


def test_refuses_existing_output_without_overwriting_it(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    records, _ = fixture_catalogue(root, selected=(0,))
    out = tmp_path / 'request'
    out.mkdir()
    sentinel = out / 'keep.txt'
    sentinel.write_text('keep')

    with pytest.raises(FileExistsError):
        stage_profile(root, module_profile(), records, [records[0]['id']], out)
    assert sentinel.read_text() == 'keep'
    assert not (out / 'profile.json').exists()


def test_failure_writing_staged_profile_removes_partial_output(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    records, _ = fixture_catalogue(root, selected=(0,))
    out = tmp_path / 'request'
    original_write_text = Path.write_text

    def fail_profile_write(path, *args, **kwargs):
        if path.name == 'profile.json':
            raise OSError('injected profile write failure')
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', fail_profile_write)
    with pytest.raises(OSError, match='injected'):
        stage_profile(root, module_profile(), records, [records[0]['id']], out)
    assert not out.exists()


def test_rejects_untrusted_catalogue_path_and_invalid_startup_index(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    records, _ = fixture_catalogue(root, selected=(0,))
    out = tmp_path / 'request'
    records[0]['source_path'] = '../outside.lunar'
    with pytest.raises(ValueError, match='fixed preload registry'):
        stage_profile(root, module_profile(), records, [records[0]['id']], out)
    assert not out.exists()

    records, _ = fixture_catalogue(root, selected=(0,))
    with pytest.raises(ValueError, match='Startup index'):
        stage_profile(root, module_profile(), records, [records[0]['id']], out, startup_index=1)
    assert not out.exists()
