# SPDX-License-Identifier: MIT
"""Ordered catalogue demo preparation through the real packed-state codec."""
import json
import hashlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
from export_image_catalogue import default_build_request, export_catalogue
import export_image_catalogue
import prepare_demo_selection as selection_module
from prepare_demo_selection import prepare_selection
from prepare_image_profile import sha
from verify_image_profile import load_prepared_profile
import build_demo_image


def selection(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue')
    ids = [project['id'] for project in catalogue['projects'] if project['category'] != 'init-starter']
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


def default_catalogue_and_request(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'default-catalogue')
    request = default_build_request(catalogue)
    assert catalogue['default_build_request'] == request
    assert catalogue['default_profile']['content'] == []
    assert sum(len(catalogue['groups'][group]) for group in
               ('engines', 'effects', 'midi', 'modulation')) == 55
    assert request['project_ids'] == ['replacement-showcase-candidate-event-horizon']
    assert request['startup_index'] == 0
    assert request['set_ids'] == ['replacement-showcase-event-horizon-companion-set']
    assert request['flash_layout'] == 'expanded-d7000'
    assert request['runtime_mode'] == 'continuous'
    return catalogue, request


def test_default_build_request_matches_continuous_service_contract(tmp_path):
    _, request = default_catalogue_and_request(tmp_path)
    # Keep the exporter independent of the service package while exercising
    # the same strict service model and standalone worker policy in this test.
    from tools.installer_service.api import BuildRequest, canonical_request
    from tools.installer_service.catalogue import load_trusted_catalogue
    from tools.installer_service.continuous_profile import validate_request
    module_kinds, project_ids, set_parents = load_trusted_catalogue(include_sets=True)
    BuildRequest.model_validate(request)
    assert json.loads(canonical_request(request)) == request
    validate_request(request, module_kinds, project_ids, set_parents)


def test_catalogue_cli_emits_canonical_default_build_request(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['export_image_catalogue.py', '--default-build-request'])
    export_image_catalogue.main()
    request = json.loads(capsys.readouterr().out)
    assert request['project_ids'] == ['replacement-showcase-candidate-event-horizon']
    assert request['startup_index'] == 0
    assert request['set_ids'] == ['replacement-showcase-event-horizon-companion-set']
    assert request['flash_layout'] == 'expanded-d7000'
    assert request['runtime_mode'] == 'continuous'
    assert sum(len(request[group]) for group in
               ('engines', 'effects', 'midi', 'modulation')) == 55


@pytest.mark.skipif(not os.environ.get('FM1_STATE_TOOL'),
                    reason='requires an existing pinned FM1_STATE_TOOL; no local compile in this task')
def test_default_build_request_prepares_all55_event_horizon_and_companion_set(tmp_path):
    _, request = default_catalogue_and_request(tmp_path)
    output = tmp_path / 'default-selection'
    receipt = prepare_selection(ROOT, request, Path(os.environ['FM1_STATE_TOOL']), output)
    assert receipt == json.loads((output / 'selection.json').read_text())
    assert receipt['project_ids'] == request['project_ids']
    assert receipt['startup_index'] == 0
    assert receipt['startup_project_id'] == request['project_ids'][0]
    assert receipt['set_ids'] == request['set_ids']
    assert receipt['selected_content'] == [
        {'kind': 'project', 'id': request['project_ids'][0]},
        {'kind': 'set', 'id': request['set_ids'][0],
         'parent_project_id': request['project_ids'][0]},
    ]
    checked = load_prepared_profile(output / 'prepared', receipt['prepared_profile_sha256'])
    assert [asset['id'] for asset in receipt['content']] == request['project_ids'] + request['set_ids']
    assert [asset['kind'] for asset in receipt['content']] == ['project', 'set']
    assert receipt['content'][0]['dependency_scan_complete'] is True
    assert receipt['content'][1]['dependency_scan_complete'] is False
    assert receipt['content'][1]['parent_project_id'] == request['project_ids'][0]
    assert len(checked.report['module_selection']['selected']) == 55
    assert checked.report['content'][0]['dependency_scan_complete'] is True
    assert checked.report['content'][1]['dependency_scan_complete'] is False
    assert checked.packed_content[1].startswith(b'\x89Lunar\r\n')
    assert receipt['packed_content_bytes'] == sum(map(len, checked.packed_content))
    for asset, packed in zip(receipt['content'], checked.packed_content):
        assert asset['packed_sha256'] == sha(packed)
        assert asset['bytes'] == len(packed)
    assert all(receipt[key] is False for key in
               ('installable', 'native_link_verified', 'native_ram_verified', 'hardware_tested'))


@pytest.mark.parametrize('mutation', [
    'missing-set', 'wrong-set-parent', 'missing-default-project', 'unapproved-song',
    'test-module', 'duplicate-module',
])
def test_default_build_request_requires_trusted_full_song_companion(mutation, tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / ('catalogue-' + mutation))
    if mutation == 'missing-set':
        catalogue['sets'] = []
    elif mutation == 'wrong-set-parent':
        catalogue['sets'][0]['parent_project_id'] = 'legacy-example-afterglow-relay'
    else:
        if mutation == 'missing-default-project':
            catalogue['full_song_default']['project_id'] = 'legacy-example-afterglow-relay'
        elif mutation == 'unapproved-song':
            catalogue['full_song_default']['musical_choice_approved'] = False
        elif mutation == 'test-module':
            catalogue['groups']['engines'][0] = 'test-not-production'
        else:
            catalogue['groups']['effects'][0] = catalogue['groups']['engines'][0]
    match = ('module groups' if mutation == 'test-module' else
             'all 55' if mutation == 'duplicate-module' else
             'full-song project and companion SET')
    with pytest.raises(ValueError, match=match):
        default_build_request(catalogue)


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


def d7000_selection(tmp_path):
    catalogue = export_catalogue(ROOT, tmp_path / 'catalogue-d7000')
    engines = sorted(set(catalogue['groups']['engines']) | {'macro', 'shapes', 'sixop', 'drums'})
    effects = sorted(set(catalogue['groups']['effects']) | {'hall'})
    return dict(version=1, **{**catalogue['groups'], 'engines': engines, 'effects': effects},
                project_ids=['replacement-showcase-candidate-event-horizon'],
                startup_index=0, flash_layout='expanded-d7000',
                runtime_mode='song-diagnostic')


@pytest.mark.parametrize('mutation', ['missing-profile', 'wrong-layout'])
def test_continuous_profile_keeps_layout_and_module_guards(tmp_path, mutation):
    request = d7000_selection(tmp_path)
    request['runtime_mode'] = 'continuous'
    if mutation == 'missing-profile':
        del request['runtime_mode']
        del request['flash_layout']
    elif mutation == 'wrong-layout':
        request['flash_layout'] = 'expanded-d9000'
    elif mutation == 'missing-fixed-module':
        request['engines'].remove('sixop')
    else:
        request['engines'].remove('sixop')
        request['effects'].append('sixop')
    output = tmp_path / 'rejected-continuous'
    with pytest.raises(ValueError):
        build_demo_image.build_selection(
            request, tmp_path / 'unused-state-tool', tmp_path / 'unused-toolchain',
            tmp_path / 'unused-catalogue', output, runtime_mode='continuous',
            flash_layout='expanded-d7000',
            wavetable_profile=build_demo_image.SHAPES8_WAVETABLE_PROFILE)
    assert not output.exists()


@pytest.mark.parametrize('mutation', [
    'wrong-runtime', 'missing-runtime', 'missing-layout', 'missing-fixed-module',
    'misgrouped-fixed-module', 'unknown-key',
])
def test_prepare_selection_rejects_unbound_or_invalid_profile_before_output(tmp_path, mutation):
    request = d7000_selection(tmp_path)
    if mutation == 'wrong-runtime':
        request['runtime_mode'] = 'diagnostic'
    elif mutation == 'missing-runtime':
        del request['runtime_mode']
    elif mutation == 'missing-layout':
        del request['flash_layout']
    elif mutation == 'missing-fixed-module':
        request['engines'] = ['trio']
    elif mutation == 'misgrouped-fixed-module':
        request['engines'].remove('sixop')
        request['effects'].append('sixop')
    else:
        request['unknown'] = True
    output = tmp_path / 'rejected-selection'
    with pytest.raises(ValueError):
        prepare_selection(ROOT, request, tmp_path / 'unused-state-tool', output)
    assert not output.exists()


@pytest.mark.parametrize('runtime_mode', ['song-diagnostic', 'continuous'])
def test_build_selection_reaches_native_link_with_original_d7000_request_digest(
        tmp_path, monkeypatch, runtime_mode):
    request = d7000_selection(tmp_path)
    request['runtime_mode'] = runtime_mode
    output = tmp_path / 'build'
    reports = {}

    def fake_prepare(profile_path, _state_tool, prepared_dir, *, recompress_content=False):
        assert recompress_content is True
        selection = json.loads(profile_path.with_name('selection.json').read_text())
        content = []
        for source in selection['sources']:
            content.append({
                'source': source['staged_path'],
                'source_sha256': source['source_sha256'],
                'kind': source['kind'],
                'dependency_scan_complete': True,
                'bytes': 1,
                'packed_sha256': sha(source['id'].encode()),
            })
        report = {'content': content, 'packed_content_bytes': len(content),
                  'state_tool_sha256': sha(b'stub-state-tool')}
        prepared_dir.mkdir()
        (prepared_dir / 'profile.json').write_text('{"prepared":true}\n')
        reports['report'] = report
        return report

    def fake_load_prepared(_directory, _expected_sha256):
        return SimpleNamespace(report=reports['report'], packed_content=[b'x'])

    class ReachedNativeLink(RuntimeError):
        pass

    def intercept_native_link(command, *, check):
        assert check is True
        assert '--flash-layout' in command
        assert command[command.index('--flash-layout') + 1] == 'expanded-d7000'
        assert '--runtime-mode' in command
        assert command[command.index('--runtime-mode') + 1] == runtime_mode
        assert '--shapes-voices' in command
        assert command[command.index('--shapes-voices') + 1] == '8'
        assert '--compressed-wavetables' in command
        assert '--flash-plaits-wavetables' not in command
        raise ReachedNativeLink

    monkeypatch.setattr(selection_module, 'prepare', fake_prepare)
    monkeypatch.setattr(selection_module, 'load_prepared_profile', fake_load_prepared)
    monkeypatch.setattr(build_demo_image.subprocess, 'run', intercept_native_link)
    with pytest.raises(ReachedNativeLink):
        build_demo_image.build_selection(
            request, tmp_path / 'unused-state-tool', tmp_path / 'unused-toolchain',
            tmp_path / 'unused-catalogue', output, runtime_mode=runtime_mode,
            flash_layout='expanded-d7000',
            wavetable_profile=build_demo_image.SHAPES8_WAVETABLE_PROFILE)

    saved_request = (output / 'selection/request.json').read_bytes()
    selection_receipt = json.loads((output / 'selection/selection.json').read_text())
    assert json.loads(saved_request) == request
    assert selection_receipt['request_sha256'] == hashlib.sha256(saved_request).hexdigest()
    assert selection_receipt['request_sha256'] == hashlib.sha256(
        (json.dumps(request, sort_keys=True, separators=(',', ':')) + '\n').encode()).hexdigest()


@pytest.mark.parametrize('runtime_mode', ['song-diagnostic', 'continuous'])
def test_build_selection_rejects_link_profile_mismatch_before_creating_output(tmp_path, runtime_mode):
    request = d7000_selection(tmp_path)
    request['runtime_mode'] = runtime_mode
    output = tmp_path / 'mismatched-build'
    with pytest.raises(ValueError, match='Build flags differ'):
        build_demo_image.build_selection(
            request, tmp_path / 'unused-state-tool', tmp_path / 'unused-toolchain',
            tmp_path / 'unused-catalogue', output, runtime_mode='diagnostic',
            flash_layout='expanded-d7000',
            wavetable_profile=build_demo_image.SHAPES8_WAVETABLE_PROFILE)
    assert not output.exists()


@pytest.mark.parametrize('runtime_mode', ['song-diagnostic', 'continuous'])
def test_build_selection_rejects_d7000_with_default_d9000_wavetable_profile(tmp_path, runtime_mode):
    request = d7000_selection(tmp_path)
    request['runtime_mode'] = runtime_mode
    output = tmp_path / 'mismatched-wavetable-build'
    with pytest.raises(ValueError, match='Wavetable profile differs'):
        build_demo_image.build_selection(
            request, tmp_path / 'unused-state-tool', tmp_path / 'unused-toolchain',
            tmp_path / 'unused-catalogue', output, runtime_mode=runtime_mode,
            flash_layout='expanded-d7000')
    assert not output.exists()


def test_build_selection_rejects_explicit_d9000_with_shapes8_profile(tmp_path):
    request = d7000_selection(tmp_path)
    request['flash_layout'] = 'expanded-d9000'
    request['runtime_mode'] = 'diagnostic'
    output = tmp_path / 'mismatched-d9000-wavetable-build'
    with pytest.raises(ValueError, match='Wavetable profile differs'):
        build_demo_image.build_selection(
            request, tmp_path / 'unused-state-tool', tmp_path / 'unused-toolchain',
            tmp_path / 'unused-catalogue', output,
            runtime_mode='diagnostic', flash_layout='expanded-d9000',
            wavetable_profile=build_demo_image.SHAPES8_WAVETABLE_PROFILE)
    assert not output.exists()


def test_legacy_unprofiled_request_keeps_wavetable_profile_flexibility():
    request = {'version': 1, 'engines': ['macro', 'shapes'], 'effects': [],
               'midi': [], 'modulation': [], 'project_ids': ['project'],
               'startup_index': 0}
    build_demo_image.validate_build_profile(
        request, 'expanded-d9000', 'diagnostic',
        build_demo_image.SHAPES8_WAVETABLE_PROFILE)
