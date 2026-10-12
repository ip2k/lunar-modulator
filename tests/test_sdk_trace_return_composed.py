"""MIT. Canonical factory composition, device and owned capture modeled.

Five expensive cases have independent real install/reset/read/admission paths.
Run in separate disposable Hera shards, never substitute activation constants.
"""
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from test_sdk_rehearsal import actual
from sdk_trace_read_fixture import digest, private_write
from sdk_trace_return_fixture import (MODES, admitted_dependencies, bind_template,
    genuine_return_ready, modeled_wire, publish_modeled_capture, run_genuine_read)


@pytest.mark.parametrize('mode', MODES)
def test_genuine_owned_return_admission(actual, tmp_path, monkeypatch, mode):
    q = genuine_return_ready(actual, tmp_path, monkeypatch, mode)
    a, f = q.a, q.f
    original_journal = f.g.journal.read_bytes()
    original_snapshot = Path(json.loads(f.native_campaign.read_bytes())['inputs']['snapshot_path']).read_bytes()
    state, result, caught = run_genuine_read(q, monkeypatch)
    campaign = publish_modeled_capture(q, state, result)
    f.clock.value += .3  # Actual chronology only; never rewrite the snapshot.
    proof = a.validate_returned_state(campaign, install_journal_path=q.journal)
    assert proof.read_outcome == ('completed' if mode == 'completed' else
        'consumed-pretransport-zero-cbw' if mode.endswith('-log') else 'stopped-ambiguous')
    assert proof.snapshot_sha256 == digest(original_snapshot)
    assert proof.install_journal_sha256 == digest(original_journal)
    assert proof.original_install_campaign_sha256 == f.installed.campaign_sha256
    assert q.journal.read_bytes() == f.g.journal.read_bytes() == original_journal
    assert proof.lineage.installed.policies
    proof.check()
    with pytest.raises(ValueError, match='Exact replay-created'):
        replace(proof).check()
    # Every positive file is actual admitted evidence, not a forged hash object.
    for path in (q.journal, f.lineage_path, q.run/'execute-once.py', q.run/'usbmon.txt',
            Path(json.loads(f.native_campaign.read_bytes())['inputs']['snapshot_path'])):
        saved = path.read_bytes()
        path.write_bytes(saved+b' ')
        try:
            with pytest.raises((ValueError, OSError)):
                proof.check()
        finally:
            path.write_bytes(saved)
        proof.check()
    # Negative publications/ambiguities survive genuine proof construction.
    negatives = [p for p in proof.absent if p.name in ('result.json','.result.json.pending',
        'trace-a.raw.bin','native.jsonl','wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json')]
    assert any(p.name == 'wrapper-stopped-ambiguous.json' for p in negatives)
    for path in negatives:
        private_write(path, b'late')
        try:
            with pytest.raises(ValueError, match='absent'):
                proof.check()
        finally:
            path.unlink()
        proof.check()
    calls_before = len(state.calls)
    with pytest.raises(FileExistsError):
        f.modules.native.run_campaign(f.prepared)
    assert len(state.calls) == calls_before
    assert len(f.g.model.calls) == 10653 and len(f.reset_calls) == 1
    assert f.g.journal.read_bytes() == original_journal
    assert Path(json.loads(f.native_campaign.read_bytes())['inputs']['snapshot_path']).read_bytes() == original_snapshot
    evidence = Path(os.environ.get('LUNAR_REHEARSAL_EVIDENCE', str(tmp_path)))
    evidence.mkdir(exist_ok=True)
    retained = evidence/('genuine-return-'+mode)
    retained.mkdir(mode=0o700)
    artifacts = {('owned-'+p.name):p for p in q.run.iterdir() if p.is_file()}
    artifacts.update({('reader-'+p.name):p for p in f.prepared.read.receipt.iterdir() if p.is_file()})
    artifacts.update(install_journal=f.g.journal, install_campaign=f.g.campaign,
        install_commands=f.g.commands, install_result=f.g.result_path,
        reader_marker=f.prepared.read.marker, boot_commands=f.reset.receipt/'commands.jsonl',
        boot_marker=f.reset.marker)
    summary = dict(schema=1, mode=mode, genuine_canonical_factories=True,
        source_pin_overrides=False, registry_overrides=False, fabricated_authority=False,
        actual_capture_supervisor_executed=False, owned_process_lifecycle_modeled=True,
        device_syscalls_clock_and_usbmon_modeled=True, hardware_access=False,
        physical_boot_proven=False, reset_cause_proven=False, recovery_verified=False,
        install_commands=len(f.g.model.calls), reset_commands=len(f.reset_calls),
        native_ioctls=len(state.calls)+(mode == 'ioctl-exception'), native_successful_returns=len(state.calls),
        read_outcome=proof.read_outcome, caught_error=caught, read_result=result,
        frozen_positive_files=len(proof.evidence), frozen_absent_paths=len(proof.absent),
        snapshot_sha256=proof.snapshot_sha256, install_journal_sha256=proof.install_journal_sha256,
        source_sha256={name:digest(Path(m.__file__).read_bytes()) for name,m in f.modules.modules.items()},
        admission_sha256=digest(Path(a.__file__).read_bytes()), artifacts={})
    for name, path in artifacts.items():
        raw = path.read_bytes()
        private_write(retained/name, raw)
        summary['artifacts'][name] = digest(raw)
    private_write(evidence/('genuine-return-'+mode+'-summary.json'), a.canonical(summary))


@pytest.mark.parametrize('which', ['wrapper', 'child'])
@pytest.mark.parametrize('fault', ['body','extra','pin','path','missing','duplicate','expression','count'])
def test_exact_tracked_owned_derivative_rejects_drift(which, fault):
    from tools import fm1_sdk_trace_return_admission as a
    root = Path(a.__file__).parent
    name = 'fm1_sdk_trace_capture.py' if which == 'wrapper' else 'fm1_sdk_trace_capture_child.py'
    raw = (root/name).read_bytes()
    fields = a._WRAPPER_FIELDS if which == 'wrapper' else a._CHILD_FIELDS
    values = {name:'0'*64 for name in fields}
    values.update(STAGE=Path('/stage'), RUN=Path('/stage/run'))
    if which == 'wrapper': values['PACKET_MEMBERS'] = 7
    actual = bind_template(raw, values)
    a.verify_derivative(raw, actual, values)
    if fault == 'body': actual = actual.replace(b'raise ValueError', b'raise RuntimeError', 1)
    elif fault == 'extra': actual += b'\nprint("unreviewed")\n'
    elif fault == 'pin': actual = actual.replace(b'0'*64, b'1'*64, 1)
    elif fault == 'path': actual = actual.replace(b'/stage/run', b'/foreign/run', 1)
    elif fault == 'missing': values = dict(values); values.pop('RUN')
    elif fault == 'duplicate': actual += b"\nRUN = Path('/stage/run')\n"
    elif fault == 'expression': actual = actual.replace(b"Path('/stage/run')", b"Path('/stage') / 'run'", 1)
    else:
        actual = actual.replace(b'PACKET_MEMBERS = 7', b'PACKET_MEMBERS = 8') if which == 'wrapper' else actual+b'\nPACKET_MEMBERS = 8\n'
    with pytest.raises(ValueError): a.verify_derivative(raw, actual, values)


@pytest.mark.parametrize('index', range(5))
def test_modeled_wire_uses_actual_reply_prefix(index):
    from tools import fm1_sdk_trace_read_wire as wire
    usb = dict(busnum='1', devnum='4')
    replies = [b'\0'*8+b'WL82'.ljust(8)+b'UBOOT1.00'.ljust(16)+b'1.00',
        b'a'*64, b'b'*4, b'c'*64, b'd'*4]
    operations = [(cdb,b'',size) for cdb,size in wire.OPERATIONS]
    raw = modeled_wire(usb, operations, replies)
    wire.verify_read_wire(raw, usb, ioctl_intents=5, outcome='completed',
        raw_replies={i:r for i,r in enumerate(replies)})
    replies[index] = b'x'*len(replies[index])
    with pytest.raises(ValueError):
        wire.verify_read_wire(raw, usb, ioctl_intents=5, outcome='completed',
            raw_replies={i:r for i,r in enumerate(replies)})


@pytest.mark.parametrize('which', ['boot','reader','native','wire'])
def test_pending_admission_is_rejected_before_genuine_install(which, monkeypatch):
    import importlib
    a = importlib.import_module('fm1_sdk_trace_return_admission')
    # This closure regression exercises pending values only; it never permits a
    # genuine branch or creates a registry entry through test substitutions.
    monkeypatch.setattr(a, which.upper()+'_SHA', None)
    with pytest.raises(ValueError, match='Closed'):
        admitted_dependencies()
