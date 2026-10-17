# SPDX-License-Identifier: MIT
"""Real production init choices survive codec, selection and service admission."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from export_image_catalogue import export_catalogue
from prepare_demo_selection import prepare_selection
from verify_image_profile import load_prepared_profile
from tools.installer_service.api import BuildRequest, FakeJobAdapter, canonical_request, create_app
from tools.installer_service.catalogue import load_trusted_catalogue
from test_installer_service import TEMPLATE

CASES = [
    (['trio'], ['init-starter-trio']),
    (['macro'], ['init-starter-macro']),
    (['shapes'], ['init-starter-shapes']),
    (['macro', 'shapes'], ['init-starter-macro', 'init-starter-shapes']),
]


@pytest.fixture(scope='module')
def catalogue(tmp_path_factory):
    return export_catalogue(ROOT, tmp_path_factory.mktemp('init-catalogue'))


def test_init_sources_are_real_patches_without_song_or_hidden_dependencies(catalogue, tmp_path):
    state = Path(os.environ['FM1_STATE_TOOL'])
    for engine in ('trio', 'macro', 'shapes'):
        row = next(p for p in catalogue['projects'] if p['id'] == 'init-starter-' + engine)
        source = ROOT / row['source_path']
        payload = source.read_bytes()
        assert row['source_sha256'] == hashlib.sha256(payload).hexdigest()
        assert row['category'] == 'init-starter'
        assert row['default_candidate'] is False
        assert row['duration_estimate'] is None
        assert 'no sequence or full song' in row['owner_disposition']
        assert row['source_module_dependencies'] == {
            'engines': [engine], 'effects': [], 'midi': [], 'modulation': []}
        doc = json.loads(payload)
        assert doc['sounds'][0]['engine'] == engine
        assert doc['sounds'][1:] == [None, None, None]
        assert doc['master'] == [None, None]
        assert not doc.get('set') and not doc.get('mod')
        packed = tmp_path / (engine + '.lunarb')
        subprocess.run([str(state), 'pack', str(source), '-o', str(packed)], check=True)
        unpacked = subprocess.run([str(state), 'unpack', str(packed)], check=True, capture_output=True).stdout
        assert unpacked == payload  # canonical first-party source, not a parser loophole
        records = [json.loads(line) for line in subprocess.run(
            [str(state), 'records', str(packed)], check=True, capture_output=True).stdout.splitlines()]
        assert {r.get('engine') for r in records if r['rec'] == 'unit'} - {''} == {engine}
        assert not any(r['rec'] in ('line', 'module') for r in records)
    assert catalogue['full_song_default']['project_id'] == 'replacement-showcase-candidate-event-horizon'
    assert catalogue['sets'][0]['parent_project_id'] == catalogue['full_song_default']['project_id']


@pytest.mark.parametrize('engines,project_ids', CASES)
def test_real_init_selection_and_service_accept_exact_sound_subsets(catalogue, tmp_path, engines, project_ids):
    request = dict(version=1, engines=engines, effects=[], midi=[], modulation=[],
                   project_ids=project_ids, startup_index=len(project_ids) - 1,
                   flash_layout='expanded-d7000', runtime_mode='continuous')
    model = BuildRequest.model_validate(request)
    assert json.loads(canonical_request(model)) == request
    output = tmp_path / 'selection'
    receipt = prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    checked = load_prepared_profile(output / 'prepared', receipt['prepared_profile_sha256'])
    assert receipt['project_ids'] == project_ids
    assert receipt['startup_project_id'] == project_ids[-1]
    assert checked.report['module_selection']['selected'] == engines
    assert receipt['selected_content'] == [{'kind': 'project', 'id': id} for id in project_ids]
    assert [p['id'] for p in receipt['content']] == project_ids
    assert [row['dependencies'] for row in checked.report['content']] == [
        [id.removeprefix('init-starter-')] for id in project_ids]
    assert receipt['set_ids'] == []
    assert all(receipt[key] is False for key in (
        'installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))
    adapter = FakeJobAdapter(1)
    kinds, known_ids, set_parents = load_trusted_catalogue(include_sets=True)
    with TestClient(create_app(adapter=adapter, template=TEMPLATE, module_kinds=kinds,
                               project_ids=known_ids, set_parents=set_parents)) as client:
        response = client.post('/api/v1/builds', json=request)
        assert response.status_code == 202, response.text
        assert json.loads(adapter.submissions[response.json()['id']][0]) == request


def test_expanded_inventory_preserves_eight_project_api_limit(catalogue):
    request = dict(version=1, engines=catalogue['groups']['engines'], effects=[], midi=[], modulation=[],
                   project_ids=[p['id'] for p in catalogue['projects']][:9], startup_index=0,
                   flash_layout='expanded-d7000', runtime_mode='continuous')
    with pytest.raises(ValueError):
        BuildRequest.model_validate(request)
