"""MIT. Genuine SDK-trace restore-to-reset admission, with modeled device only.

Source pins, completed proof factories and instance registries stay unchanged.
This establishes admission and refusal boundaries, never physical recovery.
"""
import json
from pathlib import Path

import pytest

import fm1_sdk_trace_stock_reset as reset
from test_sdk_rehearsal import actual
from sdk_trace_read_fixture import digest, private_write
from sdk_trace_admitted_fixture import genuine_recovery_ready, genuine_restore_ready


def test_genuine_completed_restore_admits_reset_and_refuses_late_evidence(actual, tmp_path, monkeypatch):
    g = genuine_recovery_ready(actual, tmp_path, monkeypatch)
    r = genuine_restore_ready(g)
    result = g.deps.restore.run_campaign(r.prepared)
    assert result['stock_baseline_restored']
    assert bytes(g.model.flash) == r.prepared.policies[0].baseline
    assert reset.RESTORE_SOURCE_SHA == digest(Path(g.deps.restore.__file__).read_bytes())
    campaign = dict(schema=1, kind='fm1-sdk-trace-fixed-loader-stock-reset',
        adapter_sha256=digest(Path(reset.__file__).read_bytes()),
        restore_campaign_path=str(r.path), restore_campaign_sha256=digest(r.path.read_bytes()),
        restore_commands_sha256=digest((r.receipt/'commands.jsonl').read_bytes()),
        restore_result_sha256=digest((r.receipt/'result.json').read_bytes()),
        restore_journal_sha256=digest((r.prepared.policies[0].directory/'journal.json').read_bytes()),
        restore_exit_status=0,
        active_session_state='admitted-trace-fixed-loader-stock-restored-no-later-commands',
        receipt_path=str(r.backup_receipt/'stock-reset'))
    path = private_write(g.q.run/'stock-reset-campaign.json', reset.canonical(campaign))
    prepared = reset.prepare_campaign(path)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', g.model.discover)
    assert prepared.absent_paths
    late = prepared.absent_paths[0]
    original_sync = prepared.bridge.sync_dir
    appeared = []

    def synced(directory):
        original_sync(directory)
        log = Path(campaign['receipt_path'])/'commands.jsonl'
        if not appeared and log.exists() and b'"event": "reset_submit_intent"' in log.read_bytes():
            private_write(late, b'late negative evidence after durable reset intent')
            appeared.append(late)

    monkeypatch.setattr(prepared.bridge, 'sync_dir', synced)
    before = len(g.model.calls)
    closed = len(g.model.closed)
    with pytest.raises(ValueError, match='absent|appeared'):
        reset.run_campaign(prepared)
    assert appeared == [late] and len(g.model.calls) == before
    assert g.model.closed[closed:] == [g.model.FD]
    assert (r.backup_receipt/'.trace-stock-core-reset.consumed').read_text() == prepared.campaign_sha256
    rows = [json.loads(line) for line in (Path(campaign['receipt_path'])/'commands.jsonl').read_bytes().splitlines()]
    assert sum(row['event'] == 'reset_submit_intent' for row in rows) == 1
    assert rows[-1]['event'] == 'reset_stopped_ambiguous'
    with pytest.raises(ValueError):
        reset.prepare_campaign(path)
    assert len(g.model.calls) == before
