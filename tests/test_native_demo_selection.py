# SPDX-License-Identifier: MIT
"""Ordered catalogue demo preparation through the real packed-state codec."""
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from export_image_catalogue import export_catalogue
from prepare_demo_selection import prepare_selection
from prepare_image_profile import sha
from verify_image_profile import load_prepared_profile


def selection(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue')
    ids = [project['id'] for project in catalogue['projects']]
    assert catalogue['sets'][0]['parent_project_id'] == 'replacement-showcase-candidate-event-horizon'
    assert catalogue['sets'][0]['dependency_scan_complete'] is False
    return dict(version=1, **catalogue['groups'], project_ids=ids[::-1], startup_index=2)


def test_prepares_original_demos_with_exact_order_hashes_and_startup(tmp_path):
    request = selection(tmp_path)
    output = tmp_path / 'selection'
    receipt = prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    assert receipt == json.loads((output / 'selection.json').read_text())
    assert receipt['project_ids'] == request['project_ids']
    assert receipt['startup_project_id'] == request['project_ids'][2]
    checked = load_prepared_profile(output / 'prepared', receipt['prepared_profile_sha256'])
    assert [asset['id'] for asset in receipt['content']] == request['project_ids']
    assert receipt['packed_content_bytes'] == sum(map(len, checked.packed_content))
    for index, asset in enumerate(receipt['content']):
        assert asset['packed_sha256'] == sha(checked.packed_content[index])
        assert asset['kind'] == 'project'
        assert asset['dependency_scan_complete'] is True
        assert asset['bytes'] > 0
    assert all(receipt[key] is False for key in
               ('installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))
    with pytest.raises(FileExistsError):
        prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    assert receipt == json.loads((output / 'selection.json').read_text())



def test_hash_pinned_companion_set_packs_after_required_project(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue')
    parent = 'replacement-showcase-candidate-event-horizon'
    set_id = 'replacement-showcase-event-horizon-companion-set'
    request = dict(version=1, **catalogue['groups'], project_ids=[parent], startup_index=0,
                   set_ids=[set_id])
    output = tmp_path / 'selection'
    receipt = prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    checked = load_prepared_profile(output / 'prepared', receipt['prepared_profile_sha256'])
    assert receipt['project_ids'] == [parent]
    assert receipt['startup_project_id'] == parent
    assert receipt['set_ids'] == [set_id]
    assert receipt['selected_content'] == [
        {'kind': 'project', 'id': parent},
        {'kind': 'set', 'id': set_id, 'parent_project_id': parent},
    ]
    assert [row['kind'] for row in receipt['content']] == ['project', 'set']
    assert receipt['content'][1]['dependency_scan_complete'] is False
    assert receipt['content'][1]['parent_project_id'] == parent
    assert [row['kind'] for row in checked.report['content']] == ['project', 'set']
    assert checked.report['content'][0]['dependency_scan_complete'] is True
    assert checked.report['content'][1]['dependency_scan_complete'] is False
    assert checked.packed_content[1].startswith(b'\x89Lunar\r\n')
    assert all(receipt[key] is False for key in
               ('installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))


@pytest.mark.parametrize('project_ids,startup_index,set_ids', [
    (['legacy-example-afterglow-relay'], 0, ['replacement-showcase-event-horizon-companion-set']),
    (['replacement-showcase-candidate-event-horizon',
      'legacy-example-afterglow-relay'], 1,
     ['replacement-showcase-event-horizon-companion-set']),
    (['replacement-showcase-candidate-event-horizon'], 0, ['not-registered']),
])
def test_companion_set_refuses_missing_or_nonstartup_parent(tmp_path, project_ids, startup_index, set_ids):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue')
    request = dict(version=1, **catalogue['groups'], project_ids=project_ids,
                   startup_index=startup_index, set_ids=set_ids)
    output = tmp_path / 'selection'
    with pytest.raises(ValueError):
        prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    assert not output.exists()

def test_omitted_project_dependency_leaves_no_success_receipt(tmp_path):
    request = selection(tmp_path)
    request['engines'] = ['trio']
    request['effects'] = []
    request['midi'] = []
    request['modulation'] = []
    output = tmp_path / 'selection'
    with pytest.raises(ValueError, match='omitted modules'):
        prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    assert not output.exists()


def test_client_catalogue_override_is_refused_before_output(tmp_path):
    output = tmp_path / 'selection'
    request = dict(version=1, engines=['trio'], effects=[], midi=[], modulation=[],
                   project_ids=['legacy-example-afterglow-relay'], startup_index=0,
                   projects=[{'source_path': '/etc/passwd'}])
    with pytest.raises(ValueError, match='selection request'):
        prepare_selection(ROOT, request, tmp_path / 'unused-tool', output)
    assert not output.exists()
