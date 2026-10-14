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
