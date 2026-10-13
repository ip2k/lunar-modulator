"""Actual completed-trace restore admission; SG reset and boot remain modeled."""
import ctypes as C
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location('completed_trace_restore_helper',
    Path(__file__).with_name('test_completed_stop_trace_restore_actual.py'))
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)

CASES = ('valid', 'late_after_intent', 'late_before_open', 'disconnect',
         'campaign_pin', 'commands_pin', 'result_pin', 'journal_pin', 'source_pin',
         'exit_status', 'state', 'kind', 'existing_receipt', 'marker_exists',
         'unfrozen', 'replay')


@pytest.mark.parametrize('case', CASES)
def test_completed_trace_stock_reset_actual(monkeypatch, tmp_path, case):
    ctx = _helper.exercise_completed_trace_restore(monkeypatch, tmp_path)
    restore, model, sha = (ctx[n] for n in ('restore', 'model', 'sha'))
    source = Path(restore.__file__).with_name('fm1_completed_stop_trace_stock_reset.py')
    template = source.read_text()
    pin = sha(restore.__file__)
    assert template.count('RESTORE_SOURCE_SHA = None') == 1
    proposal = template.replace('RESTORE_SOURCE_SHA = None', 'RESTORE_SOURCE_SHA = ' + repr(pin))
    assert proposal.replace('RESTORE_SOURCE_SHA = ' + repr(pin), 'RESTORE_SOURCE_SHA = None') == template
    if case != 'unfrozen': source.write_text(proposal)
    spec = importlib.util.spec_from_file_location('_actual_completed_trace_reset', source)
    reset = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reset
    spec.loader.exec_module(reset)
    parent = Path(ctx['campaign']['receipt_path'])
    receipt = parent / 'stock-reset'
    campaign = dict(schema=1, kind='fm1-sdk-completed-stop-trace-fixed-loader-stock-reset',
        adapter_sha256=sha(source), restore_campaign_path=str(ctx['restore_campaign_path']),
        restore_campaign_sha256=sha(ctx['restore_campaign_path']),
        restore_commands_sha256=sha(ctx['restore_receipt']/'commands.jsonl'),
        restore_result_sha256=sha(ctx['restore_receipt']/'result.json'),
        restore_journal_sha256=sha(ctx['journal']), restore_exit_status=0,
        active_session_state='completed-stop-trace-fixed-loader-stock-restored-no-later-commands',
        receipt_path=str(receipt))
    fields = dict(campaign_pin='restore_campaign_sha256', commands_pin='restore_commands_sha256',
        result_pin='restore_result_sha256', journal_pin='restore_journal_sha256', source_pin='adapter_sha256')
    if case in fields: campaign[fields[case]] = '0'*64
    if case == 'exit_status': campaign['restore_exit_status'] = 1
    if case == 'state': campaign['active_session_state'] = 'other'
    if case == 'kind': campaign['kind'] = 'other'
    marker = parent / '.completed-stop-trace-stock-core-reset.consumed'
    if case == 'existing_receipt': receipt.mkdir(mode=0o700)
    if case == 'marker_exists': marker.write_text('consumed')
    path = tmp_path / 'reset.json'; path.write_bytes(reset.canonical(campaign))
    before = len(model.calls)
    if case in (*fields, 'exit_status', 'state', 'kind', 'existing_receipt', 'marker_exists', 'unfrozen'):
        with pytest.raises(ValueError): reset.prepare_campaign(path)
        assert len(model.calls) == before
        return
    prepared = reset.prepare_campaign(path)
    assert len(model.calls) == before and prepared.absent_paths
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    late = prepared.absent_paths[0]
    if case == 'late_before_open': late.write_text('late evidence')
    if case == 'late_after_intent':
        original_sync = prepared.bridge.sync_dir
        def synced(directory):
            original_sync(directory)
            log = receipt/'commands.jsonl'
            if not late.exists() and log.exists() and b'"event": "reset_submit_intent"' in log.read_bytes():
                late.write_text('late evidence after durable intent')
        monkeypatch.setattr(prepared.bridge, 'sync_dir', synced)
    original_ioctl = model.ioctl
    def ioctl(fd, code, h):
        cdb = C.string_at(h.cmd, h.cmd_len)
        if cdb[:2] != b'\xfc\x0c': return original_ioctl(fd, code, h)
        assert cdb == bytes.fromhex('fc0c00000001ffffffffffffffffffff')
        assert fd == model.FD and code == 0x2285 and h.direction == -3 and h.data_len == 16
        model.calls.append(dict(op=0xFC0C, cdb=cdb.hex()))
        if case == 'disconnect': raise OSError('modeled accepted reset disconnect')
        C.memmove(h.data, b'\xfc\x0c'+b'\x00'*14, 16)
        return 0
    monkeypatch.setattr(reset.fcntl, 'ioctl', ioctl)
    if case in ('late_before_open', 'late_after_intent', 'disconnect'):
        with pytest.raises((ValueError, OSError)): reset.run_campaign(prepared)
    else:
        result = reset.run_campaign(prepared)
        assert result == dict(request_completion=True, core_reset_observed=False, boot_observed=False)
    calls = model.calls[before:]
    assert len(calls) == (0 if case.startswith('late_') else 1)
    if case != 'late_before_open': assert marker.read_text() == prepared.campaign_sha256
    stopped = len(model.calls)
    with pytest.raises((ValueError, FileExistsError)): reset.run_campaign(prepared)
    with pytest.raises(ValueError): reset.prepare_campaign(path)
    assert len(model.calls) == stopped
    assert reset.digest(model.flash) == reset.BASELINE_SHA
