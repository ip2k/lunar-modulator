# SPDX-License-Identifier: MIT
"""Exercise the exact saved browser request through trusted backend preparation."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from prepare_demo_selection import prepare_selection
from prepare_image_profile import unique_object
from verify_image_profile import load_prepared_profile

REQUEST_SHA256 = 'ef4ce3b330162abe9d4487c5b81bd170defa2c30cf0f00bca21f143f62da55f0'
PARENT = 'replacement-showcase-candidate-event-horizon'
SET = 'replacement-showcase-event-horizon-companion-set'
REQUEST_PATH = os.environ.get('LUNAR_BROWSER_EXPORT_REQUEST')
STATE_TOOL = os.environ.get('FM1_STATE_TOOL')

pytestmark = pytest.mark.skipif(
    not REQUEST_PATH or not STATE_TOOL,
    reason='requires the retained browser-export request and a fresh FM1_STATE_TOOL')


def browser_request():
    raw = Path(REQUEST_PATH).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REQUEST_SHA256
    return raw, json.loads(raw, object_pairs_hook=unique_object)


def test_saved_browser_request_prepares_ordered_project_and_companion_set(tmp_path):
    raw, request = browser_request()
    output = tmp_path / 'prepared-selection'
    receipt = prepare_selection(ROOT, request, Path(STATE_TOOL), output)

    assert receipt['request_sha256'] == hashlib.sha256(
        (json.dumps(request, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()
    assert receipt['project_ids'] == [PARENT]
    assert receipt['startup_index'] == 0
    assert receipt['startup_project_id'] == PARENT
    assert receipt['set_ids'] == [SET]
    assert receipt['selected_content'] == [
        {'kind': 'project', 'id': PARENT},
        {'kind': 'set', 'id': SET, 'parent_project_id': PARENT},
    ]
    assert [(row['kind'], row['id']) for row in receipt['content']] == [
        ('project', PARENT), ('set', SET)]
    assert receipt['content'][0]['dependency_scan_complete'] is True
    assert receipt['content'][1]['dependency_scan_complete'] is False
    assert receipt['content'][1]['parent_project_id'] == PARENT
    assert all(receipt[key] is False for key in (
        'installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))

    prepared = load_prepared_profile(output / 'prepared', receipt['prepared_profile_sha256'])
    assert [row['kind'] for row in prepared.report['content']] == ['project', 'set']
    assert [row['source'] for row in prepared.report['content']] == [
        f'projects/{PARENT}.lunar', f'sets/{SET}.movy1']
    assert prepared.report['content'][1]['dependency_scan_complete'] is False
    assert prepared.packed_content[1].startswith(b'\x89Lunar\r\n')
    assert hashlib.sha256(raw).hexdigest() == REQUEST_SHA256


@pytest.mark.parametrize('mutation', ['different-parent', 'different-startup'])
def test_saved_browser_request_refuses_set_without_its_parent_as_startup(tmp_path, mutation):
    _, original = browser_request()
    request = json.loads(json.dumps(original))
    if mutation == 'different-parent':
        request['project_ids'] = ['legacy-example-afterglow-relay']
        request['startup_index'] = 0
    else:
        request['project_ids'] = [PARENT, 'legacy-example-afterglow-relay']
        request['startup_index'] = 1

    output = tmp_path / mutation
    with pytest.raises(ValueError, match='Companion SET parent must be the selected startup project'):
        prepare_selection(ROOT, request, Path(STATE_TOOL), output)
    assert not output.exists()
