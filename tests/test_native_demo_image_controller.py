# SPDX-License-Identifier: MIT
"""Reject target receipts that drift from ordered preload identity."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
from build_demo_image import checked_link_receipt
from prepare_image_profile import sha
from runtime_mode import runtime_configuration


def inputs(runtime_mode='diagnostic', project_count=2):
    assets = [dict(kind='project', bytes=2, packed_sha256=sha(b'ab')),
              dict(kind='project', bytes=3, packed_sha256=sha(b'cde'))][:project_count]
    project_ids = ['second', 'first'][:project_count]
    selection = dict(prepared_profile_sha256=sha(b'manifest'), request_sha256=sha(b'request'),
                     content=assets, packed_content_bytes=sum(a['bytes'] for a in assets),
                     project_ids=project_ids, startup_index=project_count - 1,
                     startup_project_id=project_ids[-1])
    prepared = SimpleNamespace(report={'module_selection': {'selected': ['trio'], 'header_sha256': sha(b'header')}})
    verification = dict(embedded_content=dict(prepared_sha256=selection['prepared_profile_sha256'],
                        assets=deepcopy(assets), asset_count=project_count,
                        packed_content_bytes=selection['packed_content_bytes'],
                        packed_sha256=[a['packed_sha256'] for a in assets]),
                        startup_project=dict(index=project_count - 1, runtime_hook_linked=project_count > 1),
                        module_selection=deepcopy(prepared.report['module_selection']),
                        installable=False, hardware_tested=False,
                        key_audit=dict(passed=True, n_pending=0, n_fail=0),
                        elf_sha256=sha(b'elf'), flash_layout='expanded-d9000',
                        app_budget_bytes=100, probe_return_to_rom_seconds=runtime_configuration(runtime_mode)['return_to_rom_seconds'],
                        runtime_configuration=runtime_configuration(runtime_mode), flash_write_range='empty')
    artifact = dict(installable=False, hardware_tested=False, hardware_admitted=False,
                    layout_passed=True, key_audit=dict(passed=True, n_pending=0, n_fail=0),
                    elf_sha256=sha(b'elf'), app_sha256=sha(b'app'), app_bytes=3,
                    flash_layout='expanded-d9000', app_budget_bytes=100)
    return selection, prepared, verification, artifact, b'app', b'elf'


def test_checked_link_keeps_order_startup_and_actual_output_identity():
    receipt = checked_link_receipt(*inputs())
    assert receipt['project_ids'] == ['second', 'first']
    assert receipt['startup_index'] == 1
    assert receipt['startup_project_id'] == 'first'
    assert receipt['app_sha256'] == sha(b'app')
    assert receipt['module_selection'] == inputs()[2]['module_selection']
    assert receipt['embedded_content'] == inputs()[2]['embedded_content']
    for flag in ('installable', 'hardware_admitted', 'hardware_tested', 'native_ram_verified',
                 'native_playback_verified', 'full_song_default_accepted'):
        assert receipt[flag] is False


def test_single_project_receipt_truthfully_records_selector_bypass():
    values = inputs(project_count=1)
    receipt = checked_link_receipt(*values)
    assert receipt['project_ids'] == ['second']
    assert values[2]['startup_project']['runtime_hook_linked'] is False
    values[2]['startup_project']['runtime_hook_linked'] = True
    with pytest.raises(ValueError, match='selected project'):
        checked_link_receipt(*values)


@pytest.mark.parametrize('fault', [
    'reorder', 'startup', 'bool-index', 'manifest', 'modules', 'payload', 'app', 'elf',
    'pending', 'fail', 'layout', 'admission', 'continuous', 'runtime-mismatch', 'write-range', 'budget',
])
def test_changed_link_is_refused(fault):
    selection, prepared, verification, artifact, app, elf = inputs()
    if fault == 'reorder': verification['embedded_content']['assets'].reverse()
    elif fault == 'startup': verification['startup_project']['index'] = 0
    elif fault == 'bool-index': verification['startup_project']['index'] = True
    elif fault == 'manifest': verification['embedded_content']['prepared_sha256'] = sha(b'other')
    elif fault == 'modules': verification['module_selection']['selected'].append('shapes')
    elif fault == 'payload': verification['embedded_content']['packed_sha256'][0] = sha(b'other')
    elif fault == 'app': app = b'changed'
    elif fault == 'elf': elf = b'changed'
    elif fault == 'pending': artifact['key_audit']['n_pending'] = 1
    elif fault == 'fail': verification['key_audit']['n_fail'] = 1
    elif fault == 'layout': artifact['layout_passed'] = False
    elif fault == 'admission': artifact['installable'] = True
    elif fault == 'continuous': verification['probe_return_to_rom_seconds'] = 0
    elif fault == 'runtime-mismatch': verification['runtime_configuration'] = runtime_configuration('song-diagnostic')
    elif fault == 'write-range': verification['flash_write_range'] = 'nonempty'
    elif fault == 'budget': artifact['app_budget_bytes'] = verification['app_budget_bytes'] = 2
    with pytest.raises(ValueError):
        checked_link_receipt(selection, prepared, verification, artifact, app, elf)


def test_song_diagnostic_requires_matching_explicit_runtime_and_remains_unadmitted():
    values = inputs('song-diagnostic')
    receipt = checked_link_receipt(*values, runtime_mode='song-diagnostic')
    assert receipt['runtime_configuration'] == runtime_configuration('song-diagnostic')
    assert receipt['installable'] is False
    assert receipt['hardware_admitted'] is False
    assert receipt['full_song_default_accepted'] is False
    with pytest.raises(ValueError, match='runtime'):
        checked_link_receipt(*values)
    values[2]['probe_return_to_rom_seconds'] = 20
    with pytest.raises(ValueError, match='runtime'):
        checked_link_receipt(*values, runtime_mode='song-diagnostic')
    with pytest.raises(ValueError, match='bounded'):
        checked_link_receipt(*inputs(), runtime_mode='continuous')


def test_new_build_requires_real_disarmed_save_service():
    values = list(inputs())
    with pytest.raises(ValueError, match='SAVE service'):
        checked_link_receipt(*values, require_save_service=True)
    values[2]['project_save_service'] = dict(linked=True,
        compile_definition='LUNAR_PROJECT_SAVE_SERVICE=1', storage_admitted=False,
        flash_io_bound=False, save_service_armed=False, runtime_verified=False, hardware_tested=False)
    values[2]['state_bin_codec'] = dict(mode='compact-writer',
        compile_definition='FM1_STATE_BIN_COMPACT_WRITER=1', replaced_exactly_one=True,
        cached_object='/cached/state_bin.o', fresh_object='/fresh/state_bin.o',
        fresh_object_sha256=sha(b'compact'))
    values[2]['linked_objects'] = [dict(path='/fresh/state_bin.o', sha256=sha(b'compact'))]
    checked_link_receipt(*values, require_save_service=True)
    values[2]['project_save_service']['flash_io_bound'] = True
    with pytest.raises(ValueError, match='SAVE service'):
        checked_link_receipt(*values, require_save_service=True)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'hash', 'cached', 'mode'])
def test_save_receipt_refuses_wrong_or_duplicate_codec(fault):
    values = list(inputs())
    values[2]['project_save_service'] = dict(linked=True,
        compile_definition='LUNAR_PROJECT_SAVE_SERVICE=1', storage_admitted=False,
        flash_io_bound=False, save_service_armed=False, runtime_verified=False, hardware_tested=False)
    values[2]['state_bin_codec'] = dict(mode='compact-writer',
        compile_definition='FM1_STATE_BIN_COMPACT_WRITER=1', replaced_exactly_one=True,
        cached_object='/cached/state_bin.o', fresh_object='/fresh/state_bin.o',
        fresh_object_sha256=sha(b'compact'))
    values[2]['linked_objects'] = [dict(path='/fresh/state_bin.o', sha256=sha(b'compact'))]
    if fault == 'missing': values[2]['linked_objects'].clear()
    elif fault == 'duplicate': values[2]['linked_objects'] *= 2
    elif fault == 'hash': values[2]['linked_objects'][0]['sha256'] = sha(b'wrong')
    elif fault == 'cached': values[2]['linked_objects'].append(dict(path='/cached/state_bin.o', sha256=sha(b'old')))
    elif fault == 'mode': values[2]['state_bin_codec']['mode'] = 'default'
    with pytest.raises(ValueError, match='SAVE codec'):
        checked_link_receipt(*values, require_save_service=True)
