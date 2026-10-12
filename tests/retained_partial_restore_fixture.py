"""MIT. Genuine admitted RESTORE interruption; device/process evidence modeled.

The canonical completed install/boot/read/admission/target backup is genuine
source execution. Only clock, passive discovery, device syscalls and capture
are modeled. No source pin, factory, registry or completion is replaced.
"""
import ctypes
import fcntl
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

from retained_partial_fixture import _write, model_capture
from sdk_trace_admitted_fixture import genuine_recovery_ready, genuine_restore_ready


def genuine_caught_restore(actual, tmp_path, monkeypatch, fault):
    from tools import fm1_retained_partial_recovery as partial
    if os.environ.get('LUNAR_REHEARSAL_DISPOSABLE') != '1':
        raise ValueError('Explicit disposable model required')
    if fault not in ('erase', 'program'):
        raise ValueError('Bounded admitted restore fault required')
    wrappers = {name: Path(os.environ['LUNAR_PARTIAL_'+name+'_CAPTURE'])
                for name in ('INSTALL', 'RESTORE', 'ACQUIRE')}
    for name, path in wrappers.items():
        assert getattr(partial, name+'_CAPTURE_SHA') == partial.digest(path.read_bytes())
    assert partial.PREFIX_SHA == partial.digest(Path(partial.__file__).with_name('fm1_partial_nor_prefix.py').read_bytes())
    g = genuine_recovery_ready(actual, tmp_path, monkeypatch)
    r = genuine_restore_ready(g)
    restore, model = g.deps.restore, g.model
    assert partial.RESTORE_SHA == partial.digest(Path(restore.__file__).read_bytes())
    assert partial.BACKUP_SHA == partial.digest(Path(g.deps.backup.__file__).read_bytes())
    # Keep the device-aware dispatcher: ordinary journal FDs delegate through
    # model.real_flock, while the modeled SG fd must never reach real flock.
    monkeypatch.setattr(fcntl, 'flock', model.flock)
    monkeypatch.setattr(r.prepared.bridge, 'discover_sg', model.discover)
    state = SimpleNamespace(op=0xFB01 if fault == 'erase' else 0xFB04, faulted=False, enabled=True)
    base_ioctl = model.ioctl

    def ioctl(fd, code, h):
        value = base_ioctl(fd, code, h)
        call = model.calls[-1]
        call['response'] = ctypes.string_at(h.data, h.data_len) if h.direction == -3 else b''
        if state.enabled and not state.faulted and call['op'] == state.op:
            state.faulted = True
            raise OSError('Modeled syscall after physical mutation, no completion')
        return value

    # ReturnedSGModel installed a bound callable in fcntl at construction.
    # Replace that syscall surface, not a factory or authority method.
    monkeypatch.setattr(fcntl, 'ioctl', ioctl)
    start = len(model.calls)
    try:
        restore.run_campaign(r.prepared)
    except OSError as exc:
        _write(tmp_path/'caught-original-restore-error.json', dict(schema=1,
            error=type(exc).__name__, errno=exc.errno, detail=str(exc),
            intended_fault_reached=state.faulted, commands_since_restore_start=len(model.calls)-start))
        if not state.faulted:
            raise  # Preserve an unexpected pre-mutation failure and traceback.
    else:
        raise AssertionError('Actual admitted restore must catch mutation stop')
    assert state.faulted
    state.enabled = False
    original_calls = tuple(model.calls[start:])
    partial_bytes = bytes(model.flash)
    preserved = r.receipt/'journal-before-restore.json'
    assert preserved.read_bytes() == g.original_journal
    assert json.loads(g.original_journal)['state'] == 'complete'
    assert json.loads(g.original_journal)['direction'] == 'install'
    parent = r.backup_receipt
    marker = parent/'.sdk-trace-admitted-stock-restore.consumed'
    assert marker.read_text() == partial.digest(r.path.read_bytes())
    assert not (r.receipt/'result.json').exists()
    assert len(model.opened) == len(model.closed) == 2
    snapshot = json.loads(g.proof.snapshot)
    epoch = g.q.f.clock.value
    owned = model_capture(tmp_path/'restore-capture', wrapper=wrappers['RESTORE'],
        adapter=restore.__file__, campaign=r.path, config=r.campaign,
        usb=snapshot['usb_binding'], calls=original_calls, epoch=epoch,
        kind='fm1-sdk-trace-restore-one-shot', status=1, terminal=True)
    inputs = json.loads(g.proof.original_inputs)
    directory = Path(inputs['directory'])
    stopped = _write(tmp_path/'stopped-restore.json', dict(schema=1,
        kind='fm1-retained-fixed-loader-caught-partial',
        adapter_sha256=partial.digest(Path(partial.__file__).read_bytes()), direction='restore',
        original_campaign_path=str(r.path), original_campaign_sha256=partial.digest(r.path.read_bytes()),
        commands_sha256=partial.digest((r.receipt/'commands.jsonl').read_bytes()),
        journal_sha256=partial.digest((directory/'journal.json').read_bytes()), capture=owned,
        quiet_state='caught-child-stopped-same-fixed-loader-no-later-commands'))
    lineage = partial.validate_stopped(stopped)
    assert lineage.direction == 'restore' and lineage.prefix.initial_verified
    assert lineage.prefix.uncertainty and not lineage.prefix.final_verified
    assert preserved.read_bytes() == g.original_journal
    assert partial_bytes[:0x5000] == g.prepared.policies[0].target[:0x5000]
    assert partial_bytes[0x6000:] == g.prepared.policies[0].target[0x6000:]
    counts = len(model.calls), len(model.opened), len(model.closed)
    with pytest.raises((ValueError, FileExistsError)):
        restore.run_campaign(r.prepared)
    assert counts == (len(model.calls), len(model.opened), len(model.closed))
    return SimpleNamespace(partial=partial, g=g, r=r, model=model, state=state,
        lineage=lineage, stopped=stopped, inputs=inputs, wrappers=wrappers,
        original_calls=original_calls, partial_bytes=partial_bytes, ioctl=ioctl,
        tmp=tmp_path, fault=fault)


def acquire_and_prepare_stock(q, monkeypatch):
    p, lineage, model = q.partial, q.lineage, q.model
    epoch = q.g.q.f.clock.value
    def witness(name):
        return _write(q.tmp/name, dict(schema=1, kind='fm1-current-retained-fixed-loader',
            observed_at=epoch, usb_binding=json.loads(lineage.usb), sg_binding=json.loads(lineage.mapping),
            original_campaign_sha256=lineage.campaign_sha256,
            quiet_state='same-original-fixed-loader-no-later-commands'))
    w = witness('acquire-witness.json')
    acquisition = _write(q.tmp/'acquire.json', dict(schema=1, kind='fm1-retained-partial-dual-read',
        adapter_sha256=p.digest(Path(p.__file__).read_bytes()), stopped_path=str(q.stopped),
        stopped_sha256=p.digest(q.stopped.read_bytes()), witness_path=str(w), witness_sha256=p.digest(w.read_bytes()),
        receipt_path=str(q.r.backup_receipt/'restore-partial-acquire')))
    prepared = p.prepare_acquisition(acquisition)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    start = len(model.calls)
    p.run_acquisition(prepared)
    calls = tuple(model.calls[start:])
    assert len(calls) == 8707 and all(c['op'] in (0xFC0A, 0xFD05) for c in calls)
    assert (prepared.receipt/'dumpA.bin').read_bytes() == (prepared.receipt/'dumpB.bin').read_bytes() == q.partial_bytes
    capture = model_capture(q.tmp/'acquire-capture', wrapper=q.wrappers['ACQUIRE'], adapter=p.__file__,
        campaign=acquisition, config={}, usb=json.loads(lineage.usb), calls=calls, epoch=epoch,
        kind='fm1-retained-partial-acquire-one-shot', status=0)
    manifest_sha = p.digest((prepared.receipt/'manifest.json').read_bytes())
    commands_sha = p.digest((prepared.receipt/'commands.jsonl').read_bytes())
    acquired = p.validate_acquisition(acquisition, campaign_sha256=prepared.campaign_sha256,
        manifest_sha256=manifest_sha, commands_sha256=commands_sha, capture_inputs=capture)
    directory = q.tmp/'fresh-restore-partial-to-stock'
    p.create_restore_transaction(directory, acquired)
    w = witness('stock-witness.json')
    campaign = _write(q.tmp/'fresh-stock-restore.json', dict(schema=1, kind='fm1-retained-partial-to-stock-only',
        adapter_sha256=p.digest(Path(p.__file__).read_bytes()), acquisition_campaign_path=str(acquisition),
        acquisition_campaign_sha256=prepared.campaign_sha256, acquisition_manifest_sha256=manifest_sha,
        acquisition_commands_sha256=commands_sha, acquisition_capture=capture,
        acquisition_receipt=str(prepared.receipt), directory=str(directory), witness_path=str(w),
        witness_sha256=p.digest(w.read_bytes()), receipt_path=str(prepared.receipt/'partial-stock-restore')))
    stock = p.prepare_restore(campaign)
    monkeypatch.setattr(stock.bridge, 'discover_sg', model.discover)
    return SimpleNamespace(prepared=stock, campaign=campaign, acquired=acquired,
        acquisition=prepared, calls=calls, directory=directory)


def run_genuine_restore_recovery(actual, tmp_path, monkeypatch, fault, nested=False):
    q = genuine_caught_restore(actual, tmp_path, monkeypatch, fault)
    s = acquire_and_prepare_stock(q, monkeypatch)
    before = len(q.model.calls)
    original_journal = Path(q.inputs['directory'])/'journal.json'
    original_journal_bytes = original_journal.read_bytes()
    if nested:
        # A second caught failure is real new-worker execution, not invented
        # completion. Its campaign is outside the deliberately narrow original
        # admitted-RESTORE admission; no nested retry authority is manufactured.
        q.state.op, q.state.enabled, q.state.faulted = 0xFB04, True, False
        with pytest.raises(OSError):
            q.partial.run_restore(s.prepared)
        assert q.state.faulted and not (s.prepared.receipt/'result.json').exists()
        assert s.prepared.marker.read_text() == s.prepared.campaign_sha256
        assert json.loads((s.directory/'journal.json').read_bytes())['state'] == 'recovery_required'
        rejected = _write(tmp_path/'unsupported-nested-stopped.json', dict(schema=1,
            kind='fm1-retained-fixed-loader-caught-partial',
            adapter_sha256=q.partial.digest(Path(q.partial.__file__).read_bytes()), direction='restore',
            original_campaign_path=str(s.campaign), original_campaign_sha256=s.prepared.campaign_sha256,
            commands_sha256=q.partial.digest((s.prepared.receipt/'commands.jsonl').read_bytes()),
            journal_sha256=q.partial.digest((s.directory/'journal.json').read_bytes()),
            capture=json.loads(q.stopped.read_bytes())['capture'],
            quiet_state='caught-child-stopped-same-fixed-loader-no-later-commands'))
        counts = len(q.model.calls), len(q.model.opened), len(q.model.closed)
        with pytest.raises(ValueError, match='Actual admitted restore campaign schema required'):
            q.partial.validate_stopped(rejected)
        with pytest.raises((ValueError, FileExistsError)):
            q.partial.run_restore(s.prepared)
        assert counts == (len(q.model.calls), len(q.model.opened), len(q.model.closed))
        assert original_journal.read_bytes() == original_journal_bytes
        assert len(q.model.opened) == len(q.model.closed) == 4
        summary = dict(schema=1, fault=fault, nested=True, nested_failed_recovery_refused=True,
            nested_capture_admitted=False, stock_baseline_restored=False,
            failed_partial_sha256=q.partial.digest(bytes(q.model.flash)))
    else:
        result = q.partial.run_restore(s.prepared)
        assert bytes(q.model.flash) == actual.baseline
        assert result['stock_baseline_restored'] and result['verified_sha256'] == q.partial.STOCK_SHA
        assert not result['physical_recovery_verified'] and not result['boot_observed']
        assert original_journal.read_bytes() == original_journal_bytes
        assert (q.r.receipt/'journal-before-restore.json').read_bytes() == q.g.original_journal
        assert len(q.model.opened) == len(q.model.closed) == 4
        summary = dict(schema=1, fault=fault, nested=False, stock_baseline_restored=True,
            final_stock_sha256=q.partial.digest(bytes(q.model.flash)))
    summary.update(actual_factories=True, authority_overrides=False, hardware_access=False,
        clock_syscalls_and_capture_modeled=True, original_commands=len(q.original_calls),
        acquired_commands=len(s.calls), stock_restore_commands=len(q.model.calls)-before,
        uncertain_ranges=[list(x) for x in q.lineage.prefix.uncertainty],
        partial_sha256=q.partial.digest(q.partial_bytes), closed_handles=4,
        original_stopped_journal_preserved=True, original_completed_install_journal_preserved=True)
    _write(tmp_path/'genuine-retained-restore-summary.json', summary)
    return SimpleNamespace(q=q, s=s, summary=summary)
