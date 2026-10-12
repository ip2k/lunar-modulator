"""MIT. Device-free reset authority and exact trace-install replay boundaries."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_sdk_trace_boot as boot
import fm1_fixed_loader_backup as bridge
from fm1_uboot_read import SGHeader
from test_fixed_loader_backup import mock_sg, USB


@pytest.fixture
def prepared(tmp_path):
    parent = tmp_path / 'backup'; parent.mkdir(mode=0o700)
    evidence = parent / 'evidence'; evidence.write_bytes(b'explicit unit model')
    mapping = dict(node='/dev/sgMOCK', node_identity=[1, 2, 3], usb_identity=[4, 5, 6])
    installed = boot.CompletedInstall(b'{}', 'a' * 64, 1.0, parent, 'b' * 64,
        boot.canonical(USB), boot.canonical(mapping), bridge, SGHeader,
        ((evidence, evidence.read_bytes(), 100),), ())
    boot._INSTALLS.add(installed)
    campaign = dict(receipt_path=str(parent / 'reset'), usb_binding=USB,
        sg_binding=mapping, adapter_sha256='explicit unit model',
        install_campaign_sha256='a' * 64, install_commands_sha256='c' * 64)
    source = parent / 'campaign.json'; source.write_bytes(boot.canonical(campaign))
    obj = boot.Prepared(source.read_bytes(), source, boot.digest(source.read_bytes()), installed,
        installed.mapping, bridge, SGHeader, ((source, source.read_bytes(), 65536),),
        parent / 'reset', parent / '.target-core-reset.consumed')
    boot._PREPARED.add(obj); obj.check(); return obj


@pytest.mark.parametrize('field', ['campaign', 'campaign_path', 'campaign_sha256', 'install',
    'expected_mapping', 'bridge', 'header_type', 'evidence', 'receipt', 'marker'])
def test_copied_authority_rejected_before_discovery(prepared, monkeypatch, field):
    obj = replace(prepared, **{field: getattr(prepared, field)})
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('device discovery'))
    with pytest.raises(ValueError): boot.run_campaign(obj)
    with pytest.raises(ValueError): boot.ResetSG(obj, lambda *a, **kw: None)


def test_fake_object_rejected():
    fake = SimpleNamespace(check=lambda: None)
    with pytest.raises(ValueError): boot.require_prepared(fake)
    with pytest.raises(ValueError): boot.require_read_lineage(fake)


def test_direct_open_requires_durable_consumption(prepared, monkeypatch):
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('device discovery'))
    with pytest.raises(ValueError, match='durable'): boot.ResetSG(prepared, lambda *a, **kw: None)


def test_single_reset_and_permanent_parent_marker(prepared, monkeypatch):
    state = mock_sg(monkeypatch)
    result = boot.run_campaign(prepared)
    assert state.calls == [boot.legacy.reset.RESET_CDB] and state.closed == [888]
    assert result == dict(request_completion=True, core_reset_observed=False, boot_observed=False)
    assert prepared.marker.read_text() == prepared.campaign_sha256
    events = [json.loads(line) for line in (prepared.receipt / 'commands.jsonl').read_text().splitlines()]
    assert [e['event'] for e in events] == ['trace_target_reset_prepared', 'reset_submit_intent',
        'reset_sg_completion', 'reset_request_completed']
    assert all(e['boot_observed'] is False for e in events)
    with pytest.raises(FileExistsError): boot.run_campaign(prepared)
    assert len(state.calls) == 1


@pytest.mark.parametrize('fault', ['status', 'masked', 'msg', 'host', 'driver', 'resid',
                                  'info', 'sense_len', 'echo', 'ioctl'])
def test_ambiguous_reset_never_retries(prepared, monkeypatch, fault):
    def inject(header, data, op, state):
        if fault == 'ioctl': raise OSError('lost reply')
        if fault == 'echo': data[:2] = b'xx'
        else: setattr(header, fault, 1)
    state = mock_sg(monkeypatch, fault=inject)
    with pytest.raises(OSError): boot.run_campaign(prepared)
    assert state.calls == [boot.legacy.reset.RESET_CDB] and state.closed == [888]
    assert prepared.marker.exists()
    events = [json.loads(line) for line in (prepared.receipt / 'commands.jsonl').read_text().splitlines()]
    assert events[-1]['event'] == 'reset_stopped_ambiguous' and events[-1]['retry'] is False
    with pytest.raises(FileExistsError): boot.run_campaign(prepared)
    assert len(state.calls) == 1


@pytest.mark.parametrize('boundary', ['original-evidence', 'campaign', 'marker', 'receipt'])
def test_drift_before_open_stops(prepared, monkeypatch, boundary):
    if boundary == 'original-evidence': prepared.install.evidence[0][0].write_bytes(b'drift')
    elif boundary == 'campaign': prepared.campaign_path.write_bytes(b'{}')
    elif boundary == 'marker': prepared.marker.symlink_to(prepared.campaign_path)
    else: prepared.receipt.mkdir()
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('device discovery'))
    with pytest.raises((ValueError, OSError)): boot.run_campaign(prepared)


def test_post_intent_marker_drift_stops_before_ioctl(prepared, monkeypatch):
    state = mock_sg(monkeypatch)
    sync = bridge.sync_dir
    def corrupt(path):
        sync(path)
        log = prepared.receipt / 'commands.jsonl'
        if log.exists() and 'reset_submit_intent' in log.read_text():
            prepared.marker.write_text('drift')
    monkeypatch.setattr(bridge, 'sync_dir', corrupt)
    with pytest.raises(ValueError): boot.run_campaign(prepared)
    assert state.calls == [] and state.closed == [888]
    assert prepared.marker.exists()


@pytest.mark.parametrize('pin_name', ['INSTALL_SHA', 'POLICY_SHA'])
def test_unaccepted_install_factory_closed_before_evidence(monkeypatch, pin_name):
    monkeypatch.setattr(boot, pin_name, None)
    with pytest.raises(ValueError, match='activation is closed'):
        boot.validate_completed_install('/missing', campaign_sha256='a' * 64,
            commands_sha256='b' * 64, result_sha256='c' * 64, journal_sha256='d' * 64)


def test_unaccepted_wire_lineage_closed_before_evidence(monkeypatch):
    monkeypatch.setattr(boot, 'WIRE_VERIFIER_SHA', None)
    with pytest.raises(ValueError, match='activation is closed'): boot.prepare_read_lineage('/missing')


@pytest.mark.parametrize('kind', ['relative', 'symlink', 'fifo', 'directory', 'oversize'])
def test_input_reader_bounds(tmp_path, kind):
    import os
    path = tmp_path / 'input'
    if kind == 'relative': path = Path('relative')
    elif kind == 'symlink': path.symlink_to(__file__)
    elif kind == 'fifo': os.mkfifo(path)
    elif kind == 'directory': path.mkdir()
    else: path.write_bytes(b'xxxxx')
    with pytest.raises((ValueError, OSError)): boot.read_file(path, 4)


@pytest.mark.parametrize('raw', [b'', b'{}', b'{"time":true}', b'{"time":NaN}',
                               b'{"time":2}\n{"time":1}', b'[]'])
def test_invalid_transcript_chronology_rejected(raw):
    with pytest.raises(ValueError): boot.events_from(raw)


def test_copied_completed_install_or_lineage_rejected(prepared):
    with pytest.raises(ValueError): replace(prepared.install).check()
    lineage = boot.ReadLineage(b'{}', prepared.receipt.parent, prepared.install, ())
    with pytest.raises(ValueError): lineage.check()
    boot._LINEAGES.add(lineage)
    lineage.check()
    with pytest.raises(ValueError): boot.require_read_lineage(replace(lineage))
