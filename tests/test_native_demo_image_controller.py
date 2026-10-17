# SPDX-License-Identifier: MIT
"""Reject target receipts that drift from ordered preload identity."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
from build_demo_image import (checked_link_receipt, checked_wavetable_profile,
                              SHAPES8_TABLES, SHAPES8_WAVETABLE_PROFILE,
                              WAVETABLE_PROFILE, wavetable_build_flags)
from prepare_image_profile import sha
from runtime_mode import runtime_configuration
from firmware_identity import identity_configuration
from flash_layout import app_budget
from build_demo_image import build_selection
from build_application_probe import native_midi_input_configuration


def inputs(runtime_mode='diagnostic', project_count=2, include_set=False):
    assets = [dict(kind='project', bytes=2, packed_sha256=sha(b'ab')),
              dict(kind='project', bytes=3, packed_sha256=sha(b'cde'))][:project_count]
    project_ids = ['second', 'first'][:project_count]
    set_ids = ['orbit-set'] if include_set else []
    if include_set:
        assets.append(dict(kind='set', bytes=4, packed_sha256=sha(b'set!')))
    startup_project_id = project_ids[-1]
    selected_content = ([dict(kind='project', id=project_id) for project_id in project_ids]
                        + [dict(kind='set', id=set_id, parent_project_id=startup_project_id)
                           for set_id in set_ids])
    selection = dict(prepared_profile_sha256=sha(b'manifest'), request_sha256=sha(b'request'),
                     content=assets, packed_content_bytes=sum(a['bytes'] for a in assets),
                     project_ids=project_ids, startup_index=project_count - 1,
                     startup_project_id=startup_project_id, set_ids=set_ids,
                     selected_content=selected_content)
    prepared = SimpleNamespace(report={'module_selection': {'selected': ['trio'], 'header_sha256': sha(b'header')}})
    verification = dict(embedded_content=dict(prepared_sha256=selection['prepared_profile_sha256'],
                        assets=deepcopy(assets), asset_count=len(assets),
                        packed_content_bytes=selection['packed_content_bytes'],
                        packed_sha256=[a['packed_sha256'] for a in assets]),
                        startup_project=dict(index=project_count - 1, runtime_hook_linked=project_count > 1),
                        module_selection=deepcopy(prepared.report['module_selection']),
                        installable=False, hardware_tested=False,
                        compressed_wave_tables=[], indexed_tft=True,
                        flash_plaits_wavetables=True, shapes_voices=12,
                        instance_pool_bytes=249088,
                        target_app_storage=dict(rgb565_bytes=220832, indexed_bytes=163744,
                                                pool_credit_bytes=57088),
                        key_audit=dict(passed=True, n_pending=0, n_fail=0),
                        elf_sha256=sha(b'elf'), flash_layout='expanded-d9000',
                        app_budget_bytes=100, probe_return_to_rom_seconds=runtime_configuration(runtime_mode)['return_to_rom_seconds'],
                        runtime_configuration=runtime_configuration(runtime_mode), flash_write_range='empty')
    artifact = dict(installable=False, hardware_tested=False, hardware_admitted=False,
                    layout_passed=True, key_audit=dict(passed=True, n_pending=0, n_fail=0),
                    elf_sha256=sha(b'elf'), app_sha256=sha(b'app'), app_bytes=3,
                    flash_layout='expanded-d9000', app_budget_bytes=100)
    if runtime_mode == 'continuous':
        verification['native_midi_input'] = native_midi_input_configuration(True)
        verification['linked_objects'] = [
            dict(path='/output/link/' + name, sha256=sha(name.encode()))
            for name in ('midi_uart_stream.o', 'midi_stream.o')]
        verification['target_app_storage'] = dict(rgb565_bytes=220848, indexed_bytes=163760,
                                                   pool_credit_bytes=57088)
    return selection, prepared, verification, artifact, b'app', b'elf'


def test_checked_link_keeps_order_startup_and_actual_output_identity():
    receipt = checked_link_receipt(*inputs())
    assert receipt['firmware_identity'] == identity_configuration(None)
    assert receipt['selected_content'] == [
        {'kind': 'project', 'id': 'second'},
        {'kind': 'project', 'id': 'first'},
    ]
    assert receipt['project_ids'] == ['second', 'first']
    assert receipt['startup_index'] == 1
    assert receipt['startup_project_id'] == 'first'
    assert receipt['app_sha256'] == sha(b'app')
    assert receipt['module_selection'] == inputs()[2]['module_selection']
    assert receipt['embedded_content'] == inputs()[2]['embedded_content']
    assert receipt['wavetable_profile'] == 'compressed-required-banks-flash-plaits-v1'
    assert receipt['compressed_wave_tables'] == []
    assert receipt['instance_pool_bytes'] == 249088
    assert receipt['target_app_storage']['pool_credit_bytes'] == 57088
    assert receipt['runtime_hook_linked'] is True
    for flag in ('installable', 'hardware_admitted', 'hardware_tested', 'native_ram_verified',
                 'native_playback_verified', 'full_song_default_accepted'):
        assert receipt[flag] is False


def test_explicit_identity_and_layout_must_match_actual_link_policy():
    values = inputs()
    verification, artifact = values[2:4]
    verification['firmware_identity'] = identity_configuration('FM-1_500')
    for report in (verification, artifact):
        report['flash_layout'] = 'expanded-d7000'
        report['app_budget_bytes'] = app_budget('expanded-d7000')
    receipt = checked_link_receipt(*values, firmware_identity='FM-1_500',
                                   flash_layout='expanded-d7000')
    assert receipt['firmware_identity'] == identity_configuration('FM-1_500')
    assert receipt['selected_content'] == values[0]['selected_content']
    assert receipt['installable'] is False
    with pytest.raises(ValueError, match='firmware identity'):
        checked_link_receipt(*values, firmware_identity='FM-1_501')
    with pytest.raises(ValueError, match='flash layout'):
        checked_link_receipt(*values, firmware_identity='FM-1_500',
                             flash_layout='expanded-d9000')
    verification['firmware_identity']['updater_acceptance_verified'] = True
    with pytest.raises(ValueError, match='firmware identity'):
        checked_link_receipt(*values, firmware_identity='FM-1_500')


@pytest.mark.parametrize('policy', [dict(firmware_identity='FM-1_092'),
                                  dict(flash_layout='unbounded')])
def test_invalid_operator_policy_rejected_before_creating_build_output(tmp_path, policy):
    out = tmp_path / 'output'
    with pytest.raises(ValueError):
        build_selection({}, tmp_path / 'missing-state-tool', tmp_path / 'missing-toolchain',
                        tmp_path / 'missing-catalogue', out, **policy)
    assert not out.exists()


def test_checked_link_binds_companion_set_identity_and_selected_parent():
    values = inputs(include_set=True)
    receipt = checked_link_receipt(*values)
    assert receipt['project_ids'] == ['second', 'first']
    assert receipt['set_ids'] == ['orbit-set']
    assert receipt['set_parents'] == {'orbit-set': 'first'}
    assert receipt['selected_content'] == [
        {'kind': 'project', 'id': 'second'},
        {'kind': 'project', 'id': 'first'},
        {'kind': 'set', 'id': 'orbit-set', 'parent_project_id': 'first'},
    ]
    assert receipt['embedded_content']['asset_count'] == 3

@pytest.mark.parametrize('mutation', [
    'project-id', 'project-order', 'set-id', 'set-order', 'set-parent', 'startup-parent',
])
def test_checked_link_rejects_changed_project_or_set_selection_identity(mutation):
    values = list(inputs(include_set=True))
    selection = values[0]
    if mutation == 'project-id':
        selection['selected_content'][0]['id'] = 'substituted-project'
    elif mutation == 'project-order':
        selection['selected_content'][:2] = reversed(selection['selected_content'][:2])
    elif mutation == 'set-id':
        selection['selected_content'][2]['id'] = 'substituted-set'
    elif mutation == 'set-order':
        selection['selected_content'].reverse()
    elif mutation == 'set-parent':
        selection['selected_content'][2]['parent_project_id'] = 'second'
    else:
        selection['startup_project_id'] = 'second'
    with pytest.raises(ValueError, match='Selected content identities'):
        checked_link_receipt(*values)

def test_single_project_receipt_truthfully_records_selector_bypass():
    values = inputs(project_count=1)
    receipt = checked_link_receipt(*values)
    assert receipt['project_ids'] == ['second']
    assert receipt['runtime_hook_linked'] is False
    assert values[2]['startup_project']['runtime_hook_linked'] is False
    values[2]['startup_project']['runtime_hook_linked'] = True
    with pytest.raises(ValueError, match='selected project'):
        checked_link_receipt(*values)


@pytest.mark.parametrize('fault', [
    'reorder', 'startup', 'bool-index', 'manifest', 'modules', 'payload', 'app', 'elf',
    'pending', 'fail', 'layout', 'admission', 'continuous', 'runtime-mismatch', 'write-range', 'budget',
    'wave-profile', 'wave-indexed', 'wave-voices', 'wave-pool', 'wave-storage', 'wave-namespace', 'wave-bool-width',
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
    elif fault == 'wave-profile': verification['flash_plaits_wavetables'] = False
    elif fault == 'wave-indexed': verification['indexed_tft'] = False
    elif fault == 'wave-voices': verification['shapes_voices'] = True
    elif fault == 'wave-pool': verification['instance_pool_bytes'] += 1
    elif fault == 'wave-storage': verification['target_app_storage']['indexed_bytes'] += 1
    elif fault == 'wave-namespace': verification['compressed_wave_tables'] = [{'namespace': 'plaits'}]
    elif fault == 'wave-bool-width':
        prepared.report['module_selection']['selected'].append('shapes')
        verification['module_selection']['selected'].append('shapes')
        verification['compressed_wave_tables'] = [dict(
            namespace='braids', symbol='wt_waves', width=True, raw_bytes=33024,
            raw_sha256='c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634',
            packed_bytes=24159, packed_sha256=sha(b'packed'), fnv32=3119621762,
            generated_source_sha256=sha(b'generated'))]
        verification['instance_pool_bytes'] = 216064
    with pytest.raises(ValueError):
        checked_link_receipt(selection, prepared, verification, artifact, app, elf)


def test_shapes_receipt_contains_only_current_braids_bank():
    values = list(inputs())
    selected = ['trio', 'shapes']
    values[1].report['module_selection']['selected'] = selected
    values[2]['module_selection']['selected'] = selected
    values[2]['compressed_wave_tables'] = [dict(
        namespace='braids', symbol='wt_waves', width=1, raw_bytes=33024,
        raw_sha256='c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634',
        packed_bytes=24159, packed_sha256=sha(b'packed'), fnv32=3119621762,
        generated_source_sha256=sha(b'generated'))]
    values[2]['instance_pool_bytes'] = 216064
    receipt = checked_link_receipt(*values)
    assert [row['namespace'] for row in receipt['compressed_wave_tables']] == ['braids']
    assert receipt['instance_pool_bytes'] == 216064


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'raw-size', 'raw-hash', 'packed-digest', 'extra-field'])
def test_builder_rejects_stale_compressed_bank_receipt(fault):
    values = list(inputs())
    selected = ['trio', 'shapes']
    values[1].report['module_selection']['selected'] = selected
    values[2]['module_selection']['selected'] = selected
    row = dict(namespace='braids', symbol='wt_waves', width=1, raw_bytes=33024,
               raw_sha256='c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634',
               packed_bytes=24159, packed_sha256=sha(b'packed'), fnv32=3119621762,
               generated_source_sha256=sha(b'generated'))
    values[2]['compressed_wave_tables'] = [row]
    values[2]['instance_pool_bytes'] = 216064
    if fault == 'missing': values[2]['compressed_wave_tables'] = []
    elif fault == 'duplicate': values[2]['compressed_wave_tables'].append(dict(row))
    elif fault == 'raw-size': row['raw_bytes'] += 1
    elif fault == 'raw-hash': row['raw_sha256'] = sha(b'other raw table')
    elif fault == 'packed-digest': row['packed_sha256'] = 'bad'
    elif fault == 'extra-field': row['other'] = 'unexpected'
    with pytest.raises(ValueError):
        checked_link_receipt(*values)




def test_build_flags_keep_legacy_default_and_select_shapes8_compressed_ram():
    assert wavetable_build_flags(WAVETABLE_PROFILE) == [
        '--shapes-voices', '12', '--indexed-tft', '--compressed-wavetables',
        '--flash-plaits-wavetables']
    assert wavetable_build_flags(SHAPES8_WAVETABLE_PROFILE) == [
        '--shapes-voices', '8', '--indexed-tft', '--compressed-wavetables']
    with pytest.raises(ValueError, match='Unsupported named'):
        wavetable_build_flags('caller-invented-profile')


def shapes8_inputs():
    values = list(inputs('song-diagnostic', project_count=1))
    selected = ['macro', 'shapes']
    values[1].report['module_selection']['selected'] = selected
    values[2]['module_selection']['selected'] = selected
    values[2].update(shapes_voices=8, flash_plaits_wavetables=False,
                     compressed_wave_tables=[dict(row) for row in SHAPES8_TABLES],
                     instance_pool_bytes=165376)
    return values


def test_checked_link_accepts_named_shapes8_compressed_ram_profile():
    values = shapes8_inputs()
    receipt = checked_link_receipt(*values, runtime_mode='song-diagnostic')
    assert receipt['wavetable_profile'] == SHAPES8_WAVETABLE_PROFILE
    assert receipt['shapes_voices'] == 8
    assert receipt['flash_plaits_wavetables'] is False
    assert [row['namespace'] for row in receipt['compressed_wave_tables']] == ['plaits', 'braids']
    assert receipt['instance_pool_bytes'] == 165376
    for flag in ('installable', 'hardware_admitted', 'hardware_tested',
                 'native_ram_verified', 'native_playback_verified',
                 'full_song_default_accepted'):
        assert receipt[flag] is False


def continuous_inputs():
    values = shapes8_inputs()
    values[2]['runtime_configuration'] = runtime_configuration('continuous')
    values[2]['probe_return_to_rom_seconds'] = None
    values[2]['native_midi_input'] = native_midi_input_configuration(True)
    values[2]['linked_objects'] = inputs('continuous')[2]['linked_objects']
    values[2]['target_app_storage'] = dict(rgb565_bytes=220848, indexed_bytes=163760,
                                          pool_credit_bytes=57088)
    return values


def test_continuous_receipt_accepts_exact_current_target_abi_without_admission():
    receipt = checked_link_receipt(*continuous_inputs(), runtime_mode='continuous')
    assert receipt['target_app_storage'] == dict(rgb565_bytes=220848, indexed_bytes=163760,
                                               pool_credit_bytes=57088)
    assert receipt['instance_pool_bytes'] == 165376
    assert receipt['native_midi_input'] == native_midi_input_configuration(True)
    for flag in ('installable', 'hardware_admitted', 'hardware_tested',
                 'native_ram_verified', 'native_playback_verified',
                 'full_song_default_accepted'):
        assert receipt[flag] is False


@pytest.mark.parametrize('fault', ['old-abi', 'rgb565', 'indexed', 'credit', 'pool'])
def test_continuous_receipt_refuses_stale_or_changed_target_abi(fault):
    values = continuous_inputs()
    if fault == 'old-abi':
        values[2]['target_app_storage'].update(rgb565_bytes=220832, indexed_bytes=163744)
    elif fault == 'pool':
        values[2]['instance_pool_bytes'] += 1
    else:
        key = {'rgb565': 'rgb565_bytes', 'indexed': 'indexed_bytes',
               'credit': 'pool_credit_bytes'}[fault]
        values[2]['target_app_storage'][key] += 1
    with pytest.raises(ValueError, match='storage profile|instance pool'):
        checked_link_receipt(*values, runtime_mode='continuous')


@pytest.mark.parametrize('fault', [
    'voices', 'flash-policy', 'missing-module', 'wrong-namespace', 'changed-content',
    'wrong-pool', 'wrong-runtime',
])
def test_shapes8_profile_refuses_inconsistent_link_metadata(fault):
    values = shapes8_inputs()
    if fault == 'voices':
        values[2]['shapes_voices'] = 12
    elif fault == 'flash-policy':
        values[2]['flash_plaits_wavetables'] = True
    elif fault == 'missing-module':
        values[1].report['module_selection']['selected'] = ['shapes']
        values[2]['module_selection']['selected'] = ['shapes']
    elif fault == 'wrong-namespace':
        values[2]['compressed_wave_tables'][0]['namespace'] = 'braids'
    elif fault == 'changed-content':
        values[2]['compressed_wave_tables'][0]['packed_sha256'] = sha(b'fabricated')
    elif fault == 'wrong-pool':
        values[2]['instance_pool_bytes'] += 1
    elif fault == 'wrong-runtime':
        values[2]['runtime_configuration'] = runtime_configuration('diagnostic')
    with pytest.raises(ValueError):
        checked_link_receipt(*values, runtime_mode='song-diagnostic')


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
    with pytest.raises(ValueError, match='runtime'):
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


@pytest.mark.parametrize('fault', [
    'missing', 'disabled', 'ring', 'poll', 'usb', 'hardware', 'bool-as-int',
    'missing-object', 'duplicate-object', 'bad-object-hash',
])
def test_continuous_image_refuses_disabled_or_unbound_trs_midi(fault):
    values = continuous_inputs()
    verification = values[2]
    if fault == 'missing':
        verification.pop('native_midi_input')
    elif fault == 'disabled':
        verification['native_midi_input'] = native_midi_input_configuration(False)
    elif fault in ('missing-object', 'duplicate-object', 'bad-object-hash'):
        rows = verification['linked_objects']
        if fault == 'missing-object':
            rows.pop()
        elif fault == 'duplicate-object':
            rows.append(dict(rows[0]))
        else:
            rows[0]['sha256'] = 'not-a-digest'
    else:
        key, value = {
            'ring': ('ring_bytes', 512), 'poll': ('bytes_per_poll', 64),
            'usb': ('usb_midi_preserved', False),
            'hardware': ('hardware_tested', True), 'bool-as-int': ('enabled', 1),
        }[fault]
        verification['native_midi_input'][key] = value
    with pytest.raises(ValueError, match='TRS MIDI'):
        checked_link_receipt(*values, runtime_mode='continuous')


@pytest.mark.parametrize('runtime_mode', ['continuous', 'diagnostic', 'song-diagnostic'])
def test_actual_lower_builder_command_enables_trs_for_continuous_only(
        monkeypatch, tmp_path, runtime_mode):
    import build_demo_image as builder
    monkeypatch.setattr(builder, 'validate_build_profile', lambda *args: None)
    monkeypatch.setattr(builder, 'prepare_selection', lambda *args, **kwargs: {
        'prepared_profile_sha256': sha(b'prepared'), 'startup_index': 0})
    commands = []

    def stop_at_compiler(command, **kwargs):
        commands.append(command)
        raise RuntimeError('captured lower builder')

    monkeypatch.setattr(builder.subprocess, 'run', stop_at_compiler)
    with pytest.raises(RuntimeError, match='captured lower builder'):
        builder.build_selection({}, tmp_path / 'codec', tmp_path / 'toolchain',
                                tmp_path / 'catalogue', tmp_path / 'out',
                                runtime_mode=runtime_mode)
    assert len(commands) == 1
    assert commands[0].count('--enable-trs-midi') == (runtime_mode == 'continuous')
    assert '--diagnostic-telemetry' not in commands[0]
