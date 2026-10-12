"""Offline baseline-reset evidence and syscall tests; no physical device."""
import ctypes as C
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_fixed_loader_backup as b
import fm1_fixed_loader_reset as r
import fm1_uboot_read as reader
from test_fixed_loader_backup import campaign as backup_campaign, mock_sg, USB


@pytest.fixture
def campaign(backup_campaign, monkeypatch):
    path, config, _ = backup_campaign
    prepared = b.prepare_campaign(path)
    monkeypatch.setattr(r, 'load_bridge', lambda _: (b, reader.SGHeader))
    monkeypatch.setattr(r, 'INVENTORY_SHA', prepared.request_inventory_sha256)
    receipt = Path(config['receipt_path']); receipt.mkdir(mode=0o700)
    mapping = dict(node='/dev/sgMOCK', node_identity=[1, 2, 3], usb_identity=[4, 5, 6])
    dump = bytes([92]) * b.FLASH_SIZE
    dumps = []
    for name in ('dumpA.bin', 'dumpB.bin'):
        (receipt / name).write_bytes(dump)
        dumps.append(dict(file=name, bytes=len(dump), sha256=b.digest(dump), complete=True))
    manifest = dict(schema=1, kind='fm1-fixed-loader-backup', loader_sha256=b.LOADER_SHA,
        original_loader_sha256=b.ORIGINAL_SHA, loader_profile_sha256=b.PROFILE_SHA,
        profile_source_sha256=b.PROFILE_SOURCE_SHA, adapter_sha256=r.BACKUP_SOURCE_SHA,
        dependency_sha256={'fm1_uboot_read.py': r.READER_SHA}, campaign_sha256=prepared.manifest_sha256,
        request_inventory_sha256=r.INVENTORY_SHA, entry_log_sha256=config['entry_log_sha256'],
        unit_identity='FM-1_092', usb_binding=USB, sg_binding=mapping, flash_bytes=b.FLASH_SIZE,
        dumps=dumps, identical=True, command_completions=True, commands=8757,
        flash_readback_only=True, physical_recovery_verified=False, kernel_exclusivity=False)
    # Synthetic backup campaign needs the literal adapter pin, as real receipts do.
    config['adapter_sha256'] = r.BACKUP_SOURCE_SHA
    path.write_text(json.dumps(config))
    manifest['campaign_sha256'] = b.digest(path.read_bytes())
    events = [dict(event='campaign_prepared', campaign_sha256=manifest['campaign_sha256'],
        adapter_sha256=r.BACKUP_SOURCE_SHA, loader_sha256=b.LOADER_SHA, profile_sha256=b.PROFILE_SHA,
        profile_source_sha256=b.PROFILE_SOURCE_SHA, reader_sha256=r.READER_SHA,
        entry_log_sha256=config['entry_log_sha256'], usb_binding=USB, commands=8757,
        request_inventory_sha256=r.INVENTORY_SHA, kernel_exclusivity=False, physical_recovery_verified=False)]
    for index, op in enumerate(prepared.operations):
        events.extend([dict(event='sg_submit_intent', index=index, phase=op.phase,
            cdb=op.cdb.hex(), label=op.label, payload_sha256=b.digest(op.payload) if op.payload else None,
            out_len=len(op.payload), in_len=op.read_size, retry=False),
            dict(event='sg_completion', index=index, status=0, masked=0, msg=0, host=0,
                driver=0, resid=0, info=0, sense_len=0, sense_hex='', retry=False)])
    events.append(dict(event='campaign_completed', identical=True, bytes_per_dump=b.FLASH_SIZE,
        physical_recovery_verified=False, retry=False))
    start = time.time() - 0.5
    for index, event in enumerate(events):
        event['time'] = start + index / 1000000
    commands = receipt / 'commands.jsonl'
    commands.write_text('\n'.join(json.dumps(e) for e in events))
    mp = receipt / 'manifest.json'; mp.write_text(json.dumps(manifest))
    reset = dict(schema=1, kind='fm1-fixed-loader-baseline-reset-campaign',
        adapter_sha256=b.digest(Path(r.__file__).read_bytes()), backup_adapter_path=str(Path(b.__file__)),
        backup_manifest_path=str(mp), backup_manifest_sha256=b.digest(mp.read_bytes()),
        backup_campaign_path=str(path), backup_campaign_sha256=b.digest(path.read_bytes()),
        backup_commands_sha256=b.digest(commands.read_bytes()), backup_exit_status=0,
        active_session_state='matching-backup-no-later-commands', usb_binding=USB,
        sg_binding=mapping, receipt_path=str(receipt / 'core-reset'))
    rp = receipt.parent / 'reset-campaign.json'; rp.write_text(json.dumps(reset))
    return rp, reset, manifest, events


def save(campaign):
    path, config, manifest, events = campaign
    mp = Path(config['backup_manifest_path']); mp.write_text(json.dumps(manifest))
    log = mp.parent / 'commands.jsonl'; log.write_text('\n'.join(json.dumps(e) for e in events))
    config['backup_manifest_sha256'] = b.digest(mp.read_bytes())
    config['backup_commands_sha256'] = b.digest(log.read_bytes())
    path.write_text(json.dumps(config))


def test_real_dependency_pins_and_layout():
    bridge, header = r.load_bridge(Path(b.__file__).absolute())
    assert bridge.LOADER_SHA == 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'
    assert C.sizeof(header) == 88
    assert r.RESET_CDB == bytes.fromhex('fc0c00000001ffffffffffffffffffff')


def test_single_reset_reply_never_claims_boot(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)
    result = r.run_campaign(prepared)
    assert state.calls == [r.RESET_CDB] and state.closed == [888]
    assert result == dict(request_completion=True, core_reset_observed=False, boot_observed=False)
    events = [json.loads(x) for x in (Path(campaign[1]['receipt_path']) / 'commands.jsonl').read_text().splitlines()]
    assert [e['event'] for e in events] == ['reset_campaign_prepared', 'reset_submit_intent',
                                         'reset_sg_completion', 'reset_request_completed']
    assert all(e['boot_observed'] is False for e in events)
    # Same backup cannot be reused by changing campaign/receipt name.
    campaign[1]['receipt_path'] += '-again'; save(campaign)
    with pytest.raises(FileExistsError):
        r.run_campaign(r.prepare_campaign(campaign[0]))
    assert len(state.calls) == 1


@pytest.mark.parametrize('field', ['adapter_sha256', 'backup_manifest_sha256',
    'backup_campaign_sha256', 'backup_commands_sha256', 'backup_exit_status', 'active_session_state'])
def test_unsealed_policy_never_discovers_device(campaign, monkeypatch, field):
    config = campaign[1]
    config[field] = 1 if field == 'backup_exit_status' else '0' * 64
    campaign[0].write_text(json.dumps(config))
    monkeypatch.setattr(b, 'discover_sg', lambda _: pytest.fail('device discovery'))
    with pytest.raises(ValueError):
        r.prepare_campaign(campaign[0])


@pytest.mark.parametrize('mutation', ['dump_short', 'dump_changed', 'wrong_loader', 'wrong_usb',
    'missing_completion', 'duplicate_index', 'sense', 'wrong_request', 'stop', 'nan', 'future', 'false_complete'])
def test_backup_evidence_failures_are_closed(campaign, monkeypatch, mutation):
    _, config, manifest, events = campaign
    mp = Path(config['backup_manifest_path'])
    if mutation.startswith('dump_'):
        (mp.parent / 'dumpA.bin').write_bytes(b'x' * (1 if mutation == 'dump_short' else b.FLASH_SIZE))
    elif mutation == 'wrong_loader':
        manifest['loader_sha256'] = '0' * 64
    elif mutation == 'wrong_usb':
        manifest['usb_binding'] = {**USB, 'devnum': '29'}
    elif mutation == 'missing_completion':
        events.pop(2)
    elif mutation == 'duplicate_index':
        events[4]['index'] = 0
    elif mutation == 'sense':
        events[2]['sense_len'] = 1
    elif mutation == 'wrong_request':
        events[3]['cdb'] = r.RESET_CDB.hex()
    elif mutation == 'stop':
        events[-1]['event'] = 'campaign_stopped_ambiguous'
    elif mutation == 'nan':
        events[-1]['time'] = float('nan')
    elif mutation == 'future':
        events[-1]['time'] = time.time() + 100
    else:
        manifest['dumps'][0]['complete'] = False
    save(campaign)
    monkeypatch.setattr(b, 'discover_sg', lambda _: pytest.fail('device discovery'))
    with pytest.raises(ValueError):
        r.prepare_campaign(campaign[0])


@pytest.mark.parametrize('fault', ['status', 'masked', 'msg', 'host', 'driver', 'resid', 'info', 'sense_len', 'echo', 'ioctl'])
def test_ambiguous_request_is_consumed_and_closed(campaign, monkeypatch, fault):
    prepared = r.prepare_campaign(campaign[0])
    def inject(h, data, op, state):
        if fault == 'ioctl':
            raise OSError('lost reply')
        if fault == 'echo':
            data[:2] = b'xx'
        else:
            setattr(h, fault, 1)
    state = mock_sg(monkeypatch, fault=inject)
    log = []
    sg = r.ResetSG(prepared, lambda e, **kw: log.append((e, kw)))
    with pytest.raises(OSError):
        sg.request_reset()
    with pytest.raises(ValueError):
        sg.request_reset()
    assert state.calls == [r.RESET_CDB] and state.closed == [888]
    assert sg.failed and sg.consumed and sg.ioctl_attempts == 1
    assert all(fields['boot_observed'] is False for _, fields in log)


@pytest.mark.parametrize('when', ['open', 'pre', 'post', 'stale'])
def test_live_binding_and_detach_never_mean_boot(campaign, monkeypatch, when):
    prepared = r.prepare_campaign(campaign[0])
    threshold = {'open': 1, 'pre': 3, 'post': 4}.get(when)
    def binding_fault(state):
        if threshold and state.discoveries >= threshold:
            raise OSError('reenumerated')
    state = mock_sg(monkeypatch, binding_fault=binding_fault)
    if when == 'open':
        with pytest.raises(OSError):
            r.ResetSG(prepared, lambda *a, **kw: None)
    else:
        sg = r.ResetSG(prepared, lambda *a, **kw: None)
        if when == 'stale':
            sg.started -= 11
        with pytest.raises((OSError, ValueError)):
            sg.request_reset()
        assert sg.failed and sg.fd is None
    assert len(state.calls) == (1 if when == 'post' else 0)


def test_changed_backup_mapping_rejects_before_open(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)
    prepared = replace(prepared, expected_mapping=r.canonical({'node': '/dev/other'}))
    with pytest.raises(ValueError):
        r.ResetSG(prepared, lambda *a, **kw: None)
    assert not state.calls and not state.closed


def test_failed_durable_intent_prevents_syscall(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)
    def log(*a, **kw):
        raise OSError('storage')
    sg = r.ResetSG(prepared, log)
    with pytest.raises(OSError):
        sg.request_reset()
    assert sg.consumed and not state.calls and state.closed == [888]


def test_reset_uncertain_receipt_is_durable(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0])
    def inject(*a):
        raise OSError('timeout')
    state = mock_sg(monkeypatch, fault=inject)
    with pytest.raises(OSError):
        r.run_campaign(prepared)
    receipt = Path(campaign[1]['receipt_path'])
    events = [json.loads(x) for x in (receipt / 'commands.jsonl').read_text().splitlines()]
    assert events[-1]['event'] == 'reset_stopped_ambiguous'
    assert events[-1]['boot_observed'] is False
    assert (receipt.parent / '.baseline-core-reset.consumed').is_file()
    assert state.calls == [r.RESET_CDB]


def test_historical_backup_is_checked_at_completion(campaign):
    _, config, manifest, events = campaign
    entry = Path(json.loads(Path(config['backup_campaign_path']).read_bytes())['entry_log_path'])
    rows = [json.loads(line) for line in entry.read_text().splitlines()]
    for e in rows + events:
        e['time'] -= 86400
    entry.write_text('\n'.join(json.dumps(e) for e in rows))
    backup_path = Path(config['backup_campaign_path']); backup = json.loads(backup_path.read_bytes())
    backup['entry_log_sha256'] = manifest['entry_log_sha256'] = b.digest(entry.read_bytes())
    events[0]['entry_log_sha256'] = manifest['entry_log_sha256']
    backup_path.write_text(json.dumps(backup))
    config['backup_campaign_sha256'] = manifest['campaign_sha256'] = b.digest(backup_path.read_bytes())
    events[0]['campaign_sha256'] = manifest['campaign_sha256']
    save(campaign)
    assert r.prepare_campaign(campaign[0]).token is r._PREPARED


def test_symlink_campaign_rejected(campaign):
    link = campaign[0].with_name('link.json'); link.symlink_to(campaign[0])
    with pytest.raises(OSError):
        r.prepare_campaign(link)


def test_unprepared_object_never_opens(monkeypatch):
    monkeypatch.setattr(os, 'open', lambda *a, **kw: pytest.fail('open'))
    with pytest.raises(ValueError):
        r.ResetSG(object(), lambda *a, **kw: None)


def test_close_failure_latches_ambiguity(campaign, monkeypatch):
    prepared = r.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)
    sg = r.ResetSG(prepared, lambda *a, **kw: None)
    real_close = os.close
    def close(fd):
        if fd == 888:
            raise OSError('close failed')
        real_close(fd)
    monkeypatch.setattr(os, 'close', close)
    with pytest.raises(OSError):
        sg.request_reset()
    assert sg.failed and sg.fd is None and sg.consumed
    with pytest.raises(ValueError):
        sg.request_reset()
    assert state.calls == [r.RESET_CDB]


@pytest.mark.parametrize('entry', ['transport', 'campaign'])
@pytest.mark.parametrize('copy_kind', ['replace', 'copy', 'constructor'])
def test_copied_factory_object_rejected_before_any_io(campaign, monkeypatch, entry, copy_kind):
    import copy
    prepared = r.prepare_campaign(campaign[0])
    if copy_kind == 'replace':
        copied = replace(prepared, expected_mapping=b'{}')
    elif copy_kind == 'copy':
        copied = copy.copy(prepared)
    else:
        copied = r.PreparedReset(**prepared.__dict__)
    monkeypatch.setattr(os, 'open', lambda *a, **kw: pytest.fail('file or device open'))
    monkeypatch.setattr(b, 'discover_sg', lambda _: pytest.fail('device discovery'))
    with pytest.raises(ValueError, match='Prepared baseline reset required'):
        if entry == 'transport':
            r.ResetSG(copied, lambda *a, **kw: None)
        else:
            r.run_campaign(copied)


def test_fifo_evidence_nonblocking_regular_file_rejection(tmp_path, monkeypatch):
    fifo = tmp_path / 'fifo'; os.mkfifo(fifo)
    original = os.open
    def checked_open(path, flags):
        assert flags & os.O_NONBLOCK
        return original(path, flags)
    monkeypatch.setattr(os, 'open', checked_open)
    with pytest.raises(ValueError, match='Regular file required'):
        r.bounded_file(fifo, 64)
