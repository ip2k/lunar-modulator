"""Preparation-stop stock reset authority/syscall tests; no physical device access.

The completed-restore validator is explicitly injected for these syscall tests;
this suite does not establish genuine restore provenance. The exact previously reviewed reset/backup/SG dependencies are loaded.
"""
import ctypes as C
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm1_fixed_loader_backup as bridge
import fm1_sdk_prepare_stop_stock_reset as r
from test_fixed_loader_backup import mock_sg, USB


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    parent = tmp_path / 'returned-backup'
    parent.mkdir(mode=0o700)
    evidence = tmp_path / 'completed-restore.json'
    evidence.write_text('{"modeled":true}')
    proof = dict(usb_binding=USB,
        sg_binding=dict(node='/dev/sgMOCK', **{'class': '/sys/devices/mock/scsi_generic/sgMOCK'},
            node_identity=[1, 2, 3], usb_identity=[4, 5, 6]),
        returned_backup_receipt_path=str(parent), returned_backup_manifest_sha256='a' * 64,
        baseline_sha256=r.BASELINE_SHA, target_sha256=r.TARGET_SHA, sectors_written=30,
        sector_order=list(range(0x5000, 0x22000, 4096)) + [0x4000], _absent_paths=(), _proof=SimpleNamespace(check_pending=lambda: None))
    config = dict(schema=1, kind='fm1-sdk-preparation-stop-fixed-loader-stock-reset',
        adapter_sha256=r.digest(Path(r.__file__).read_bytes()), restore_campaign_path=str(evidence),
        restore_campaign_sha256=r.digest(evidence.read_bytes()), restore_commands_sha256='b' * 64,
        restore_result_sha256='c' * 64, restore_journal_sha256='d' * 64, restore_exit_status=0,
        active_session_state='preparation-stop-fixed-loader-stock-restored-no-later-commands',
        receipt_path=str(parent / 'stock-reset'))
    path = tmp_path / 'reset-campaign.json'
    path.write_text(json.dumps(config))
    restore_path = Path(r.__file__).with_name('fm1_sdk_prepare_stop_restore.py')
    monkeypatch.setattr(r, 'RESTORE_SOURCE_SHA', r.digest(restore_path.read_bytes()))
    real_load = r.load_source
    calls = []

    def validate(path, **kwargs):
        calls.append((path, {k: v for k, v in kwargs.items() if k != 'freeze'}))
        kwargs['freeze'](Path(path), kwargs['campaign_sha256'])
        return dict(proof)

    def load(path, expected, name):
        if name == '_prepare_stop_stock_reset_restore':
            assert r.digest(r.read_file(path)) == expected
            return SimpleNamespace(validate_completed_restore=validate)
        return real_load(path, expected, name)

    monkeypatch.setattr(r, 'load_source', load)
    return path, config, proof, evidence, calls


def save(campaign):
    campaign[0].write_text(json.dumps(campaign[1]))


def syscalls(prepared, monkeypatch, **kwargs):
    state = mock_sg(monkeypatch, **kwargs)
    monkeypatch.setattr(prepared.bridge, 'discover_sg',
        lambda usb: {**bridge.discover_sg(usb), 'class': '/sys/devices/mock/scsi_generic/sgMOCK'})
    monkeypatch.setattr(r.sys, 'platform', 'linux')
    return state


def test_unfrozen_restore_has_no_factory_authority(campaign, monkeypatch):
    monkeypatch.setattr(r, 'RESTORE_SOURCE_SHA', None)
    with pytest.raises(ValueError, match='has not frozen'):
        r.prepare_campaign(campaign[0])
    assert campaign[4] == []


def test_genuine_helper_contract_and_frozen_reset_mechanics(campaign):
    prepared = r.prepare_campaign(campaign[0])
    assert len(campaign[4]) == 1
    assert campaign[4][0] == (str(campaign[3]), dict(
        campaign_sha256=campaign[1]['restore_campaign_sha256'],
        commands_sha256='b' * 64, result_sha256='c' * 64, journal_sha256='d' * 64))
    assert C.sizeof(prepared.header_type) == 88
    assert prepared.reset.RESET_CDB == bytes.fromhex('fc0c00000001ffffffffffffffffffff')


@pytest.mark.parametrize('field,value', [
    ('schema', True), ('schema', 2), ('kind', 'old-baseline-reset'),
    ('restore_exit_status', True), ('restore_exit_status', 1),
    ('active_session_state', 'unknown'), ('adapter_sha256', '0' * 64),
    ('extra', 0)])
def test_changed_campaign_rejects_before_helper(campaign, field, value):
    campaign[1][field] = value
    save(campaign)
    with pytest.raises(ValueError):
        r.prepare_campaign(campaign[0])
    assert not campaign[4]


@pytest.mark.parametrize('field,value', [
    ('baseline_sha256', '0' * 64), ('target_sha256', '0' * 64),
    ('sectors_written', True), ('sectors_written', 29),
    ('sector_order', [0x4000] + list(range(0x5000, 0x22000, 4096))),
    ('sector_order', list(range(0x5000, 0x22000, 4096)))])
def test_wrong_restore_plan_rejects_without_device_discovery(campaign, monkeypatch, field, value):
    campaign[2][field] = value
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('unexpected device discovery'))
    with pytest.raises(ValueError):
        r.prepare_campaign(campaign[0])


@pytest.mark.parametrize('fault', ['parent_mode', 'parent_symlink', 'receipt_exists', 'marker_exists', 'outside_parent', 'relative_receipt', 'sg_node', 'sg_class_relative', 'sg_class_name'])
def test_receipt_and_binding_constraints(campaign, fault):
    parent = Path(campaign[2]['returned_backup_receipt_path'])
    if fault == 'parent_mode':
        parent.chmod(0o755)
    elif fault == 'parent_symlink':
        original = parent.with_name('original-parent')
        parent.rename(original)
        parent.symlink_to(original, target_is_directory=True)
    elif fault == 'receipt_exists':
        Path(campaign[1]['receipt_path']).mkdir(mode=0o700)
    elif fault == 'marker_exists':
        (parent / '.preparation-stop-stock-core-reset.consumed').write_text('already-used')
    elif fault == 'outside_parent':
        campaign[1]['receipt_path'] = str(parent.parent / 'outside')
    elif fault == 'relative_receipt':
        campaign[1]['receipt_path'] = 'relative'
    elif fault == 'sg_node':
        campaign[2]['sg_binding']['node'] = '/dev/other'
    elif fault == 'sg_class_relative':
        campaign[2]['sg_binding']['class'] = 'scsi_generic/sgMOCK'
    elif fault == 'sg_class_name':
        campaign[2]['sg_binding']['class'] = '/sys/devices/mock/scsi_generic/other'
    save(campaign)
    with pytest.raises(ValueError):
        r.prepare_campaign(campaign[0])


def test_exact_one_reset_and_no_boot_claim(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0])
    state = syscalls(prepared, monkeypatch)
    result = r.run_campaign(prepared)
    assert result == dict(request_completion=True, core_reset_observed=False, boot_observed=False)
    assert state.calls == [prepared.reset.RESET_CDB] and state.closed == [888]
    receipt = Path(campaign[1]['receipt_path'])
    rows = [json.loads(x) for x in (receipt / 'commands.jsonl').read_text().splitlines()]
    assert [x['event'] for x in rows] == ['preparation_stop_stock_reset_prepared', 'reset_submit_intent',
                                       'reset_sg_completion', 'reset_request_completed']
    assert all(x['boot_observed'] is False for x in rows)
    assert rows[1]['in_len'] == 16 and rows[1]['out_len'] == 0
    assert (receipt.parent / '.preparation-stop-stock-core-reset.consumed').read_text() == prepared.campaign_sha256
    campaign[1]['receipt_path'] += '-renamed'
    save(campaign)
    with pytest.raises(ValueError, match='unused preparation-stop-stock'):
        r.prepare_campaign(campaign[0])
    assert state.calls == [prepared.reset.RESET_CDB]


@pytest.mark.parametrize('forgery', ['clone', 'permit', 'direct_open'])
def test_in_memory_authority_cannot_be_copied_or_opened_directly(campaign, monkeypatch, forgery):
    prepared = r.prepare_campaign(campaign[0])
    state = syscalls(prepared, monkeypatch)
    with pytest.raises(ValueError):
        if forgery == 'clone':
            r.run_campaign(replace(prepared))
        else:
            permit = r._OpenPermit(prepared) if forgery == 'permit' else None
            r.transport_type(prepared)(prepared, lambda *a, **k: None, permit)
    assert state.discoveries == 0 and not state.calls


def test_frozen_restore_evidence_changes_before_run(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0])
    state = syscalls(prepared, monkeypatch)
    campaign[3].write_text('{"modeled":false}')
    with pytest.raises(ValueError, match='evidence changed'):
        r.run_campaign(prepared)
    assert state.discoveries == 0 and not state.calls


@pytest.mark.parametrize('paths', [[], ('relative',), (Path('relative'),)])
def test_absent_evidence_contract_rejects_invalid_paths(campaign, paths):
    campaign[2]['_absent_paths'] = paths
    with pytest.raises(ValueError, match='absolute absent evidence'):
        r.prepare_campaign(campaign[0])


@pytest.mark.parametrize('kind', ['file', 'directory', 'broken_symlink'])
@pytest.mark.parametrize('when', ['factory', 'run', 'binding'])
def test_absent_evidence_remains_absent_before_reset(campaign, monkeypatch, kind, when):
    path = campaign[0].parent / 'must-remain-absent'
    campaign[2]['_absent_paths'] = (path,)

    def appear():
        if kind == 'file':
            path.write_text('later evidence')
        elif kind == 'directory':
            path.mkdir()
        else:
            path.symlink_to(path.with_name('missing-target'))

    if when == 'factory':
        appear()
        with pytest.raises(ValueError, match='absent.*appeared'):
            r.prepare_campaign(campaign[0])
        return
    prepared = r.prepare_campaign(campaign[0])
    state = syscalls(prepared, monkeypatch)
    if when == 'run':
        appear()
    else:
        discover = prepared.bridge.discover_sg
        def changed(usb):
            mapping = discover(usb)
            appear()
            return mapping
        monkeypatch.setattr(prepared.bridge, 'discover_sg', changed)
    with pytest.raises(ValueError, match='absent.*appeared'):
        r.run_campaign(prepared)
    assert not state.calls
    assert state.discoveries == (0 if when == 'run' else 1)
    assert state.closed == ([] if when == 'run' else [888])


@pytest.mark.parametrize('fault', ['status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len', 'echo', 'ioctl'])
def test_uncertain_reply_stays_consumed(campaign, monkeypatch, fault):
    prepared = r.prepare_campaign(campaign[0])
    def inject(header, data, op, state):
        if fault == 'ioctl':
            raise OSError('reply lost')
        elif fault == 'echo':
            data[:2] = b'xx'
        else:
            setattr(header, fault, 1)
    state = syscalls(prepared, monkeypatch, fault=inject)
    with pytest.raises(OSError):
        r.run_campaign(prepared)
    rows = [json.loads(x) for x in (Path(campaign[1]['receipt_path']) / 'commands.jsonl').read_text().splitlines()]
    assert rows[-1]['event'] == 'reset_stopped_ambiguous'
    assert rows[-1]['core_reset_observed'] is False and rows[-1]['boot_observed'] is False
    assert state.calls == [prepared.reset.RESET_CDB] and state.closed == [888]
    assert (Path(campaign[1]['receipt_path']).parent / '.preparation-stop-stock-core-reset.consumed').is_file()
    with pytest.raises(FileExistsError):
        r.run_campaign(prepared)
    assert len(state.calls) == 1


@pytest.mark.parametrize('when', ['open', 'pre', 'post'])
def test_connection_replacement_closes_without_retry(campaign, monkeypatch, when):
    prepared = r.prepare_campaign(campaign[0])
    threshold = {'open': 1, 'pre': 3, 'post': 4}[when]
    def failure(state):
        if state.discoveries >= threshold:
            raise OSError('connection replaced')
    state = syscalls(prepared, monkeypatch, binding_fault=failure)
    with pytest.raises(OSError):
        r.run_campaign(prepared)
    assert len(state.calls) == (1 if when == 'post' else 0)
    assert len(state.closed) == (0 if when == 'open' else 1)
    assert (Path(campaign[1]['receipt_path']).parent / '.preparation-stop-stock-core-reset.consumed').is_file()


@pytest.mark.parametrize('failure_point', ['marker', 'marker_sync', 'durable_intent'])
def test_storage_failure_cannot_issue_reset(campaign, monkeypatch, failure_point):
    prepared = r.prepare_campaign(campaign[0])
    state = syscalls(prepared, monkeypatch)
    if failure_point == 'marker':
        original = prepared.bridge.private_file
        def private(path, mode='wb'):
            if Path(path).name == '.preparation-stop-stock-core-reset.consumed':
                raise OSError('marker write failed')
            return original(path, mode)
        monkeypatch.setattr(prepared.bridge, 'private_file', private)
    elif failure_point == 'marker_sync':
        original = prepared.bridge.sync_dir
        def sync(path):
            if (Path(campaign[1]['receipt_path']).parent / '.preparation-stop-stock-core-reset.consumed').exists():
                raise OSError('marker sync failed')
            return original(path)
        monkeypatch.setattr(prepared.bridge, 'sync_dir', sync)
    else:
        original = prepared.bridge.sync_dir
        def sync(path):
            log = Path(campaign[1]['receipt_path']) / 'commands.jsonl'
            if log.exists() and 'reset_submit_intent' in log.read_text():
                raise OSError('intent sync failed')
            return original(path)
        monkeypatch.setattr(prepared.bridge, 'sync_dir', sync)
    with pytest.raises(OSError):
        r.run_campaign(prepared)
    assert not state.calls


@pytest.mark.parametrize('which', ['receipt', 'marker'])
def test_broken_symlink_reserves_one_use_destination(campaign, monkeypatch, which):
    parent = Path(campaign[2]['returned_backup_receipt_path'])
    path = Path(campaign[1]['receipt_path']) if which == 'receipt' else parent / '.preparation-stop-stock-core-reset.consumed'
    path.symlink_to(parent / 'nonexistent')
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('unexpected discovery'))
    with pytest.raises(ValueError, match='unused preparation-stop-stock'):
        r.prepare_campaign(campaign[0])


@pytest.mark.parametrize('which', ['envelope', 'state', 'target'])
def test_historical_diagnostic_cannot_authorize_trace_reset(campaign, monkeypatch, which):
    if which == 'envelope':
        campaign[1]['kind'] = 'fm1-returned-fixed-loader-stock-reset'
    elif which == 'state':
        campaign[1]['active_session_state'] = 'returned-fixed-loader-stock-restored-no-later-commands'
    else:
        campaign[2]['target_sha256'] = 'df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db'
    save(campaign)
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('unexpected discovery'))
    with pytest.raises(ValueError):
        r.prepare_campaign(campaign[0])


def test_pending_chain_changes_after_durable_intent_prevent_reset(campaign, monkeypatch):
    refused = []
    def check_pending():
        if refused:
            raise ValueError('Later automatic-chain publication')
    campaign[2]['_proof'] = SimpleNamespace(check_pending=check_pending)
    prepared = r.prepare_campaign(campaign[0])
    state = syscalls(prepared, monkeypatch)
    real_sync = prepared.bridge.sync_dir
    receipt = Path(campaign[1]['receipt_path'])
    def synced(directory):
        real_sync(directory)
        log = receipt / 'commands.jsonl'
        if log.exists() and b'"event": "reset_submit_intent"' in log.read_bytes():
            refused.append(True)
    monkeypatch.setattr(prepared.bridge, 'sync_dir', synced)
    with pytest.raises(ValueError, match='Later automatic-chain'):
        r.run_campaign(prepared)
    assert refused and state.calls == [] and state.closed == [888]
    assert (receipt.parent / '.preparation-stop-stock-core-reset.consumed').exists()
