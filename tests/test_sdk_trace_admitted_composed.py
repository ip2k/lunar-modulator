"""MIT. Two independent genuine recovery branches; model device/process only.

Run each heavy case in its own disposable Hera chunk after exact literal-only
successors are reviewed. Source pins, registries and factories stay unchanged.
"""
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from test_sdk_rehearsal import actual
from sdk_trace_read_fixture import digest, private_write
from sdk_trace_admitted_fixture import genuine_recovery_ready, genuine_restore_ready


@pytest.mark.parametrize('outcome', ['complete', 'durable-intent-absence'])
def test_genuine_admitted_backup_restore_and_historical_helper(actual, tmp_path, monkeypatch, outcome):
    g = genuine_recovery_ready(actual, tmp_path, monkeypatch)
    r = genuine_restore_ready(g)
    backup, restore, model = g.deps.backup, g.deps.restore, g.model
    before = len(model.calls)
    target = r.prepared.policies[0].target
    baseline = r.prepared.policies[0].baseline
    late = next(p for p in g.proof.absent if p.name == 'wrapper-cleanup-ambiguous.json')
    with pytest.raises(ValueError):
        backup.run_campaign(replace(g.prepared))
    with pytest.raises(ValueError):
        restore.run_campaign(replace(r.prepared))
    with pytest.raises((ValueError, FileExistsError)):
        backup.run_campaign(g.prepared)
    assert len(model.calls) == before
    if outcome == 'durable-intent-absence':
        original_sync = r.prepared.bridge.sync_dir
        intents = []
        def synced(path):
            original_sync(path)
            log = r.receipt/'commands.jsonl'
            if log.exists():
                with log.open('rb') as fp:
                    fp.seek(0, 2)
                    size = fp.tell()
                    fp.seek(max(0, size-4096))
                    rows = fp.read().splitlines()
                if rows and json.loads(rows[-1]).get('event') == 'durable_intent' and not intents:
                    intents.append(json.loads(rows[-1]))
                    private_write(late, b'late provenance ambiguity')
        monkeypatch.setattr(r.prepared.bridge, 'sync_dir', synced)
        with pytest.raises(ValueError, match='absent|appeared'):
            restore.run_campaign(r.prepared)
        assert len(intents) == 1
        assert not any(call['op'] in (0xFB01, 0xFB04) for call in model.calls[before:])
        assert bytes(model.flash) == target
        assert (r.backup_receipt/'.sdk-trace-admitted-stock-restore.consumed').exists()
        assert not (r.receipt/'result.json').exists()
        count = len(model.calls)
        with pytest.raises((ValueError, FileExistsError)):
            restore.run_campaign(r.prepared)
        assert len(model.calls) == count
        assert (r.receipt/'journal-before-restore.json').read_bytes() == g.original_journal
        assert len(model.opened) == len(model.closed) == 2
        completed = None
    else:
        result = restore.run_campaign(r.prepared)
        assert bytes(model.flash) == baseline and result['stock_baseline_restored']
        assert model.calls[before]['op'] == 0xFC0A
        initial = model.calls[before+1:before+4097]
        assert [x['address'] for x in initial] == list(range(0, 1048576, 256))
        assert all(x['op'] == 0xFD05 for x in initial)
        order = list(range(0x5000, 0x22000, 4096))+[0x4000]
        assert [x['address'] for x in model.calls[before:] if x['op'] == 0xFB01] == order
        assert len([x for x in model.calls[before:] if x['op'] == 0xFB04]) == 480
        journal = r.prepared.policies[0].directory/'journal.json'
        assert json.loads(journal.read_bytes())['direction'] == 'restore'
        saved = []
        def freeze(path, expected=None, limit=2*1048576):
            path = Path(path)
            raw = restore.read_file(path, limit)
            if expected is not None and digest(raw) != expected:
                raise ValueError('Caller pin differs')
            saved.append((path, raw, limit))
            return raw
        def completed_proof():
            return restore.validate_completed_restore(r.path,
                campaign_sha256=digest(r.path.read_bytes()),
                commands_sha256=digest((r.receipt/'commands.jsonl').read_bytes()),
                result_sha256=digest((r.receipt/'result.json').read_bytes()),
                journal_sha256=digest(journal.read_bytes()), freeze=freeze)
        completed = completed_proof()
        proof = completed['_proof']
        proof.check()
        assert completed['sector_order'] == order and completed['sectors_written'] == 30
        assert completed['baseline_sha256'] == restore.BASELINE_SHA
        assert completed['target_sha256'] == restore.TARGET_SHA
        assert (r.receipt/'journal-before-restore.json').read_bytes() == g.original_journal
        assert proof.install_journal_sha256 == digest(g.original_journal)
        with pytest.raises(ValueError): replace(proof).check()
        # Caller hashes are recomputed, so rejection is source/lineage/replay.
        mutations = [(r.backup_receipt/'.sdk-trace-admitted-stock-restore.consumed', b'0'*64),
            (r.receipt/'journal-before-restore.json', b'{}'),
            (g.q.f.lineage_path, g.q.f.lineage_path.read_bytes()+b' '),
            (r.receipt/'result.json', restore.canonical(dict(result, direction='install')))]
        for path, raw in mutations:
            original = path.read_bytes()
            path.write_bytes(raw)
            try:
                with pytest.raises((OSError, ValueError, AssertionError)): completed_proof()
            finally: path.write_bytes(original)
        private_write(late, b'late')
        try:
            with pytest.raises(ValueError): proof.check()
            with pytest.raises(ValueError): completed_proof()
        finally: late.unlink()
        completed_proof()
        count = len(model.calls)
        with pytest.raises((ValueError, FileExistsError)): restore.run_campaign(r.prepared)
        assert len(model.calls) == count and len(model.opened) == len(model.closed) == 2
    snapshot_path = Path(json.loads(g.q.f.native_campaign.read_bytes())['inputs']['snapshot_path'])
    assert snapshot_path.read_bytes() == g.original_snapshot
    assert g.q.journal.read_bytes() == g.original_journal
    out = Path(os.environ.get('LUNAR_REHEARSAL_EVIDENCE', str(tmp_path)))
    retained = out/('genuine-admitted-recovery-'+outcome)
    retained.mkdir(mode=0o700)
    paths = {'backup-campaign.json': g.backup_path, 'restore-campaign.json': r.path,
        'original-snapshot.json': snapshot_path, 'original-journal.json': g.q.journal}
    for prefix, receipt in [('backup', r.backup_receipt), ('restore', r.receipt)]:
        paths.update({prefix+'-'+p.name: p for p in receipt.iterdir() if p.is_file()})
    pins = {}
    for name, path in paths.items():
        raw = path.read_bytes()
        private_write(retained/name, raw)
        pins[name] = digest(raw)
    summary = dict(schema=1, outcome=outcome, genuine_canonical_factories=True,
        source_pin_overrides=False, registry_overrides=False, hardware_access=False,
        actual_capture_supervisor_executed=False, device_and_process_lifecycle_modeled=True,
        physical_recovery_verified=False, boot_observed=False, reset_cause_proven=False,
        backup_commands=8757, total_modeled_recovery_commands=len(model.calls),
        handles_opened=len(model.opened), handles_closed=len(model.closed),
        completed_restore_helper_verified=completed is not None,
        original_snapshot_sha256=digest(g.original_snapshot),
        original_install_journal_sha256=digest(g.original_journal),
        target_sha256=restore.TARGET_SHA, baseline_sha256=restore.BASELINE_SHA,
        backup_source_sha256=digest(Path(backup.__file__).read_bytes()),
        restore_source_sha256=digest(Path(restore.__file__).read_bytes()), artifacts=pins)
    private_write(out/('genuine-admitted-recovery-'+outcome+'-summary.json'), restore.canonical(summary))
