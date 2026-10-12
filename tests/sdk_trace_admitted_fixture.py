"""MIT. Canonical returned proof to exact new recovery factories; device modeled.

Dependency closure is checked before an expensive install. No activation source,
factory, registry or Prepared authority is replaced by this fixture.
"""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

from sdk_trace_return_fixture import (admitted_dependencies, genuine_return_ready,
    publish_modeled_capture, run_genuine_read)
from sdk_trace_read_fixture import digest, private_write
from test_returned_rom_actual import ReturnedSGModel

POLICY_SHA = '54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835'


def recovery_dependencies():
    admission, stage, modules = admitted_dependencies()
    backup = importlib.import_module('fm1_sdk_trace_admitted_backup')
    restore = importlib.import_module('fm1_sdk_trace_admitted_stock_restore')
    for module in (backup, restore):
        expected = stage/'tools'/(module.__name__+'.py')
        if Path(module.__file__).absolute() != expected:
            raise ValueError('Exact canonical admitted recovery source required')
    if (backup.PROOF_SOURCE_SHA is None or restore.BACKUP_SOURCE_SHA is None
            or restore.POLICY_SOURCE_SHA is None):
        raise ValueError('Reviewed literal admitted recovery successors remain closed')
    if (backup.PROOF_SOURCE_SHA != digest(Path(admission.__file__).read_bytes())
            or restore.BACKUP_SOURCE_SHA != digest(Path(backup.__file__).read_bytes())
            or restore.POLICY_SOURCE_SHA != POLICY_SHA
            or digest((stage/'tools/fm1_bound_sdk_trace.py').read_bytes()) != POLICY_SHA):
        raise ValueError('Exact reviewed admitted recovery dependencies differ')
    return SimpleNamespace(admission=admission, stage=stage, modules=modules,
        backup=backup, restore=restore)


def genuine_recovery_ready(actual, tmp_path, monkeypatch):
    deps = recovery_dependencies()  # No hardware or factory authority override.
    q = genuine_return_ready(actual, tmp_path, monkeypatch, 'completed')
    state, read_result, caught = run_genuine_read(q, monkeypatch)
    assert caught is None and read_result is not None
    admission_path = publish_modeled_capture(q, state, read_result)
    q.f.clock.value += .3
    proof = deps.admission.validate_returned_state(admission_path)
    proof.check()
    original_journal = q.f.g.journal.read_bytes()
    original_snapshot = Path(json.loads(q.f.native_campaign.read_bytes())['inputs']['snapshot_path']).read_bytes()
    assert proof.install_journal_sha256 == digest(original_journal)
    assert proof.snapshot_sha256 == digest(original_snapshot)
    snapshot = json.loads(proof.snapshot)
    inputs = json.loads(proof.original_inputs)
    witness = dict(schema=1, kind='fm1-passive-sdk-trace-admitted-backup-connection',
        observed_at=q.f.clock.value, usb_binding=snapshot['usb_binding'],
        sg_binding=snapshot['sg_binding'], original_rom_snapshot_sha256=proof.snapshot_sha256,
        returned_admission_sha256=digest(admission_path.read_bytes()), quiet_state=deps.backup.STATE)
    witness_path = private_write(q.run/'recovery-connection.json', deps.backup.canonical(witness))
    envelope = dict(schema=1, kind=deps.backup.KIND,
        adapter_sha256=digest(Path(deps.backup.__file__).read_bytes()),
        returned_admission_path=str(admission_path), returned_admission_sha256=digest(admission_path.read_bytes()),
        connection_witness_path=str(witness_path), connection_witness_sha256=digest(witness_path.read_bytes()),
        loader_path=inputs['loader_path'], profile_path=inputs['profile_path'],
        profile_source_path=str(deps.stage/'tools/jieli/loader_config_profile.py'),
        active_session_state=deps.backup.STATE,
        receipt_path=str(Path(proof.private_parent)/('admitted-target-backup-'+tmp_path.name)))
    backup_path = private_write(q.run/'backup-campaign.json', deps.backup.canonical(envelope))
    prepared = deps.backup.prepare_campaign(backup_path)
    assert prepared.provenance.lineage.installed.campaign_sha256 == q.f.installed.campaign_sha256
    model = ReturnedSGModel(monkeypatch, snapshot['sg_binding'], prepared.policies[0].target)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    return SimpleNamespace(deps=deps, q=q, proof=proof, admission_path=admission_path,
        backup_path=backup_path, prepared=prepared, model=model,
        original_journal=original_journal, original_snapshot=original_snapshot)


def genuine_restore_ready(fixture):
    g = fixture
    backup, restore = g.deps.backup, g.deps.restore
    result = backup.run_campaign(g.prepared)
    receipt = Path(json.loads(g.prepared.campaign)['receipt_path'])
    target = g.prepared.policies[0].target
    assert len(g.model.calls) == 8757
    assert (receipt/'dumpA.bin').read_bytes() == (receipt/'dumpB.bin').read_bytes() == target
    assert len(g.model.opened) == len(g.model.closed) == 1
    campaign = dict(schema=1, kind='fm1-sdk-trace-admitted-stock-restore-only',
        adapter_sha256=digest(Path(restore.__file__).read_bytes()),
        returned_backup_campaign_path=str(g.backup_path),
        returned_backup_campaign_sha256=digest(g.backup_path.read_bytes()),
        returned_backup_manifest_sha256=digest((receipt/'manifest.json').read_bytes()),
        returned_backup_commands_sha256=digest((receipt/'commands.jsonl').read_bytes()),
        returned_backup_exit_status=0,
        original_install_campaign_path=str(g.q.f.g.campaign),
        original_install_campaign_sha256=g.proof.original_install_campaign_sha256,
        install_journal_sha256=g.proof.install_journal_sha256,
        active_session_state='admitted-trace-fixed-loader-dual-target-backup-no-later-commands',
        receipt_path=str(receipt/'stock-restore'))
    path = private_write(g.q.run/'restore-campaign.json', restore.canonical(campaign))
    prepared = restore.prepare_campaign(path)
    assert prepared.initial_journal == g.original_journal
    return SimpleNamespace(g=g, campaign=campaign, path=path, prepared=prepared,
        backup_result=result, backup_receipt=receipt, receipt=Path(campaign['receipt_path']))
