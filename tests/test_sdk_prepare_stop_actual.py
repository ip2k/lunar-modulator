"""Genuine retained V7 evidence, disposable container SG model only.

The two closed successor literals are proposed in a disposable source copy.
Original evidence, canonical proof factories and receipt validators are unchanged.
This test grants no physical acceptance or hardware activation.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def test_actual_v7_preparation_stop_backup_restore(monkeypatch, tmp_path):
    if os.environ.get('LUNAR_PREPARATION_STOP_DISPOSABLE') != '1':
        pytest.skip('Requires retained private V7 files in a disposable container')
    assert Path('/tmp/packet-work') == Path(__file__).resolve().parents[1]
    assert sys.platform == 'linux'
    import fm1_sdk_trace_prepare_stop as stop
    from test_returned_rom_actual import ReturnedSGModel
    root = Path(__file__).resolve().parents[1]
    tools = root / 'tools'
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    # Exactly one literal changes per successor; no authority factory is patched.
    for filename, field, dependency in (
        ('fm1_sdk_prepare_stop_backup.py', 'PROOF_SOURCE_SHA', 'fm1_sdk_trace_prepare_stop.py'),
        ('fm1_sdk_prepare_stop_restore.py', 'BACKUP_SOURCE_SHA', 'fm1_sdk_prepare_stop_backup.py'),
    ):
        path = tools / filename; template = path.read_text()
        before = field + ' = None'
        assert template.count(before) == 1
        proposal = template.replace(before, field + ' = ' + repr(sha(tools / dependency)))
        assert proposal.replace(field + ' = ' + repr(sha(tools / dependency)), before) == template
        path.write_text(proposal)
    import fm1_sdk_prepare_stop_backup as backup
    import fm1_sdk_prepare_stop_restore as restore
    stage = Path('/home/claude/fm1-sdk-trace-campaign-20261012-v7')
    entry = Path('/home/claude/fm1-sdk-trace-entry-20261012-v7')
    lineage = stage / 'boot-lineage.json'
    accepted = stop.validate_preparation_stop(lineage, entry / 'automatic-trace-chain-v7')
    snapshot = json.loads(accepted.snapshot)
    boot_config = json.loads(Path(json.loads(lineage.read_bytes())['boot_campaign_path']).read_bytes())
    install_path = Path(boot_config['install_campaign_path'])
    original = json.loads(install_path.read_bytes())
    stop_path = tmp_path / 'preparation-stop.json'
    stop_path.write_bytes(backup.canonical(dict(schema=1, kind='fm1-native-preparation-stop-evidence',
        boot_lineage_path=str(lineage), boot_lineage_sha256=sha(lineage),
        chain_path=str(entry / 'automatic-trace-chain-v7'))))
    witness_path = tmp_path / 'witness.json'
    witness_path.write_bytes(backup.canonical(dict(schema=1,
        kind='fm1-passive-sdk-preparation-stop-backup-connection', observed_at=time.time(),
        usb_binding=snapshot['usb_binding'], sg_binding=snapshot['sg_binding'],
        original_rom_snapshot_sha256=accepted.snapshot_sha256,
        preparation_stop_sha256=sha(stop_path), quiet_state=backup.STATE)))
    policy_inputs = original['policy_inputs']
    # Loader paths are genuine original assets, never substituted model bytes.
    rehearsal_config = json.loads(Path(policy_inputs['campaign_path']).read_bytes())
    bp = tmp_path / 'backup.json'
    bc = dict(schema=1, kind=backup.KIND, adapter_sha256=sha(backup.__file__),
        preparation_stop_path=str(stop_path), preparation_stop_sha256=sha(stop_path),
        connection_witness_path=str(witness_path), connection_witness_sha256=sha(witness_path),
        active_session_state=backup.STATE, receipt_path=str(accepted.lineage.parent / 'modeled-preparation-stop-backup'))
    for key in ('loader_path', 'profile_path', 'profile_source_path'):
        bc[key] = rehearsal_config[key]
    bp.write_bytes(backup.canonical(bc))
    p = backup.prepare_campaign(bp)
    target = Path(policy_inputs['directory']) / 'target.bin'
    model = ReturnedSGModel(monkeypatch, snapshot['sg_binding'], target.read_bytes())
    monkeypatch.setattr(p.bridge, 'discover_sg', model.discover)
    result = backup.run_campaign(p)
    assert len(model.calls) == 8757
    assert not any(c['op'] in (0xFB01, 0xFB04, 0xFC0C) for c in model.calls)
    assert result['preparation_outcome'] == 'failed-before-native-worker'
    assert result['boot_observed'] is result['physical_recovery_verified'] is False
    receipt = Path(bc['receipt_path'])
    rc = dict(schema=1, kind='fm1-sdk-preparation-stop-stock-restore-only',
        adapter_sha256=sha(restore.__file__), returned_backup_campaign_path=str(bp),
        returned_backup_campaign_sha256=sha(bp), returned_backup_manifest_sha256=sha(receipt / 'manifest.json'),
        returned_backup_commands_sha256=sha(receipt / 'commands.jsonl'), returned_backup_exit_status=0,
        original_install_campaign_path=str(install_path), original_install_campaign_sha256=sha(install_path),
        install_journal_sha256=boot_config['journal_sha256'],
        active_session_state='preparation-stop-fixed-loader-dual-target-backup-no-later-commands',
        receipt_path=str(receipt / 'stock-restore'))
    rp = tmp_path / 'restore.json'; rp.write_bytes(restore.canonical(rc))
    prepared = restore.prepare_campaign(rp)
    restored = restore.run_campaign(prepared)
    assert hashlib.sha256(model.flash).hexdigest() == restore.BASELINE_SHA
    assert restored['full_flash_readback_verified'] is True
    assert restored['sectors_written'] == 30
    erases = [c['address'] for c in model.calls if c['op'] == 0xFB01]
    assert erases == list(range(0x5000, 0x22000, 4096)) + [0x4000]
    assert restored['boot_observed'] is restored['physical_recovery_verified'] is False
