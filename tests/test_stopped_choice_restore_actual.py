"""MIT. Genuine successor factories with container-only NOR; no devices.

Exact physical RAM lineage and production successor source pins are admitted
unchanged. Only SG syscalls are modeled. All SDK, stock/target, original sources
and original journal guards remain real.
"""
import json
import os
from pathlib import Path
import shutil
import sys
import time

import pytest

import fm1_stopped_choice_backup as backup_source
import fm1_stopped_choice_stock_restore as restore_source
import fm1_stopped_choice_recovery_evidence as evidence
import fm1_sdk_rehearsal as rehearsal
from test_diagnostic_stage_resume import actual_tree
from test_stopped_choice_recovery_actual import test_actual_physical_read_files_admit_without_transport as admit_physical
from test_returned_rom_actual import ReturnedSGModel


@pytest.fixture
def successor_factory(actual_tree,monkeypatch):
    m,stage=actual_tree
    # Exact private imports must not inherit ambient first-party module cache.
    for name in rehearsal.SOURCES:
        monkeypatch.delitem(sys.modules,Path(name).stem,raising=False)
    admit_physical(actual_tree,monkeypatch)
    run=stage/'diagnostic-stage-resume-v1';admission=run/'recovery-evidence.json'
    source=stage/'tools/fm1_stopped_choice_recovery_evidence.py'
    proof_module=evidence.load_source(source,evidence.digest(source.read_bytes()),'_restore_actual_read_proof')
    proof=proof_module.validate_returned_state(admission)
    assert proof.probe_outcome=='completed-two-read'
    for original in (backup_source,restore_source):shutil.copyfile(original.__file__,stage/'tools'/Path(original.__file__).name)
    bp=stage/'tools/fm1_stopped_choice_backup.py';rp=stage/'tools/fm1_stopped_choice_stock_restore.py'
    backup=evidence.load_source(bp,evidence.digest(bp.read_bytes()),'_actual_stopped_choice_backup')
    restore=evidence.load_source(rp,evidence.digest(rp.read_bytes()),'_actual_stopped_choice_restore')
    assert backup.PROOF_SOURCE_SHA==evidence.digest(source.read_bytes())
    assert restore.BACKUP_SOURCE_SHA==evidence.digest(bp.read_bytes())
    snapshot=json.loads(proof.snapshot);inputs=json.loads(proof.original_inputs)
    witness=dict(schema=1,kind='fm1-passive-stopped-choice-backup-connection',observed_at=time.time(),
        usb_binding=snapshot['usb_binding'],sg_binding=snapshot['sg_binding'],
        original_rom_snapshot_sha256=backup.SNAPSHOT_SHA,returned_admission_sha256=evidence.digest(admission.read_bytes()),quiet_state=backup.STATE)
    wp=run/'successor-connection.json';wp.write_bytes(backup.canonical(witness))
    c=dict(schema=1,kind=backup.KIND,adapter_sha256=evidence.digest(bp.read_bytes()),
        returned_admission_path=str(admission),returned_admission_sha256=evidence.digest(admission.read_bytes()),
        connection_witness_path=str(wp),connection_witness_sha256=evidence.digest(wp.read_bytes()),
        loader_path=inputs['loader_path'],profile_path=inputs['profile_path'],
        profile_source_path=str(stage/'tools/jieli/loader_config_profile.py'),active_session_state=backup.STATE,
        receipt_path=str(stage.parent/'stopped-choice-target-backup'))
    cp=run/'successor-backup.json';cp.write_bytes(backup.canonical(c))
    prepared=backup.prepare_campaign(cp)
    return backup,restore,prepared,cp,proof,stage


def test_actual_successor_factories_preflight_without_device(successor_factory):
    backup,restore,prepared,cp,proof,stage=successor_factory
    assert len(prepared.operations)==8757 and prepared.provenance.probe_outcome=='completed-two-read'
    assert proof.install_journal_sha256=='0d7973321b33335715335ce6413546c02bc16ad08f8b952ab6e3b223231e9db4'
    assert proof.historical.historical_admission_time==1791775862.0725162
    assert not Path(json.loads(prepared.campaign)['receipt_path']).exists()
    assert not backup.marker_path(stage.parent,json.loads(prepared.campaign)).exists()


@pytest.mark.parametrize('outcome',['complete','intent-drift'])
def test_actual_successor_backup_restore_and_preserved_completed_helper(successor_factory,monkeypatch,outcome):
    backup,restore,prepared,cp,proof,stage=successor_factory
    policy=prepared.policies[0];target=policy.target;baseline=policy.baseline
    assert backup.digest(target)==backup.TARGET_SHA and restore.digest(baseline)==restore.BASELINE_SHA
    mapping=json.loads(prepared.snapshot)['sg_binding']
    model=ReturnedSGModel(monkeypatch,mapping,target)
    monkeypatch.setattr(prepared.bridge,'discover_sg',model.discover)
    manifest=backup.run_campaign(prepared)
    assert len(model.calls)==8757 and len(model.opened)==len(model.closed)==1
    receipt=Path(json.loads(prepared.campaign)['receipt_path'])
    assert (receipt/'dumpA.bin').read_bytes()==(receipt/'dumpB.bin').read_bytes()==target
    # Resolve only positively frozen historical files, never search arbitrary files.
    candidates=list({p for p,raw,_ in proof.evidence
        if backup.digest(raw)==proof.original_rehearsal_campaign_sha256})
    assert len(candidates)==1
    original_path=candidates[0]
    c=dict(schema=1,kind='fm1-stopped-choice-stock-restore-only',adapter_sha256=restore.digest(Path(restore.__file__).read_bytes()),
        returned_backup_campaign_path=str(cp),returned_backup_campaign_sha256=backup.digest(cp.read_bytes()),
        returned_backup_manifest_sha256=backup.digest((receipt/'manifest.json').read_bytes()),
        returned_backup_commands_sha256=backup.digest((receipt/'commands.jsonl').read_bytes()),returned_backup_exit_status=0,
        original_rehearsal_campaign_path=str(original_path),original_rehearsal_campaign_sha256=proof.original_rehearsal_campaign_sha256,
        install_journal_sha256=proof.install_journal_sha256,active_session_state='stopped-choice-fixed-loader-dual-target-backup-no-later-commands',receipt_path=str(receipt/'stock-restore'))
    rc=stage/'stopped-choice-restore.json';rc.write_bytes(restore.canonical(c));accepted=restore.prepare_campaign(rc)
    before=len(model.calls);late=stage/'diagnostic-stage-resume-v1/wrapper-cleanup-ambiguous.json'
    if outcome=='intent-drift':
        original_sync=accepted.bridge.sync_dir
        def sync(path):
            original_sync(path)
            log=Path(c['receipt_path'])/'commands.jsonl'
            if log.exists():
                # Inspect the durable last record, rather than rereading the growing log.
                with log.open('rb') as fp:
                    fp.seek(0,2);size=fp.tell();fp.seek(max(0,size-4096))
                    tail=fp.read().splitlines()
                if tail and json.loads(tail[-1]).get('event')=='durable_intent':
                    late.write_bytes(b'{}')
        monkeypatch.setattr(accepted.bridge,'sync_dir',sync)
        with pytest.raises(ValueError,match='absent|appeared'):restore.run_campaign(accepted)
        assert not any(call['op'] in (0xFB01,0xFB04) for call in model.calls[before:])
        assert (receipt/'.stopped-choice-stock-restore.consumed').exists()
        assert not (Path(c['receipt_path'])/'result.json').exists()
        assert bytes(model.flash)==target and len(model.opened)==len(model.closed)==2
        return
    result=restore.run_campaign(accepted)
    assert bytes(model.flash)==baseline and result['stock_baseline_restored']
    assert model.calls[before]['op']==0xFC0A
    initial=model.calls[before+1:before+4097]
    assert [call['address'] for call in initial]==list(range(0,1048576,256)) and all(call['op']==0xFD05 for call in initial)
    assert [call['address'] for call in model.calls[before:] if call['op']==0xFB01]==list(range(0x5000,0x22000,4096))+[0x4000]
    saved=[]
    def freeze(path,expected=None,limit=2*1048576):
        path=Path(path);data=restore.read_file(path,limit)
        if expected is not None:assert restore.digest(data)==expected
        saved.append((path,data,limit));return data
    rr=Path(c['receipt_path']);journal=accepted.policies[0].directory/'journal.json'
    completed=restore.validate_completed_restore(rc,campaign_sha256=restore.digest(rc.read_bytes()),
        commands_sha256=restore.digest((rr/'commands.jsonl').read_bytes()),result_sha256=restore.digest((rr/'result.json').read_bytes()),
        journal_sha256=restore.digest(journal.read_bytes()),freeze=freeze)
    assert completed['baseline_sha256']==restore.BASELINE_SHA and completed['target_sha256']==restore.TARGET_SHA
    assert (rr/'journal-before-restore.json').read_bytes()==accepted.initial_journal
    assert restore.digest(accepted.initial_journal)==proof.install_journal_sha256
    assert json.loads(journal.read_bytes())['direction']=='restore'
    assert tuple(completed['_absent_paths']) and len(model.opened)==len(model.closed)==2
    # Each corrupt receipt is caller-hash-consistent, so rejection must come from
    # the genuine lineage/replay gates rather than a stale supplied digest.
    def check_completed():
        return restore.validate_completed_restore(rc,campaign_sha256=restore.digest(rc.read_bytes()),
            commands_sha256=restore.digest((rr/'commands.jsonl').read_bytes()),
            result_sha256=restore.digest((rr/'result.json').read_bytes()),
            journal_sha256=restore.digest(journal.read_bytes()),freeze=freeze)
    mutations=[]
    changed=dict(c,kind='fm1-returned-rom-stock-restore-only');mutations.append((rc,restore.canonical(changed)))
    mutations.append((receipt/'.stopped-choice-stock-restore.consumed',b'0'*64))
    changed=dict(result,direction='install');mutations.append((rr/'result.json',restore.canonical(changed)))
    rows=(rr/'commands.jsonl').read_bytes().splitlines()
    row_index=next(i for i,row in enumerate(rows) if i and json.loads(row).get('event')=='sg_completion'
        and json.loads(rows[i-1]).get('cdb','').startswith('fd05'))
    row=json.loads(rows[row_index]);row['response_sha256']='0'*64;rows[row_index]=restore.canonical(row)
    mutations.append((rr/'commands.jsonl',b'\n'.join(rows)+b'\n'))
    mutations.append((rr/'journal-before-restore.json',b'{}'))
    changed=json.loads(journal.read_bytes());changed['direction']='install';mutations.append((journal,restore.canonical(changed)))
    mutations.append((Path(restore.__file__),Path(restore.__file__).read_bytes()+b'\n# drift\n'))
    for path,altered in mutations:
        original=path.read_bytes();path.write_bytes(altered)
        try:
            with pytest.raises((ValueError,OSError,AssertionError)):check_completed()
        finally:path.write_bytes(original)
    late.write_bytes(b'{}')
    try:
        with pytest.raises(ValueError):check_completed()
    finally:late.unlink()
    check_completed()
    out=Path(os.environ['LUNAR_ADMISSION_EVIDENCE']);out.mkdir(exist_ok=True)
    (out/'actual-successor-summary.json').write_bytes(restore.canonical(dict(
        actual_original_factories_verified=True,actual_physical_ram_receipt_admitted=True,
        successor_backup_sha256=backup.digest(Path(backup.__file__).read_bytes()),successor_restore_sha256=restore.digest(Path(restore.__file__).read_bytes()),
        backup_commands=8757,total_modeled_commands=len(model.calls),baseline_sha256=restore.BASELINE_SHA,target_sha256=restore.TARGET_SHA,
        completed_helper_verified=True,preserved_install_journal_sha256=proof.install_journal_sha256,
        frozen_files=len(saved),negative_paths=len(completed['_absent_paths']),hardware_access=False,
        actual_nor_restore_verified=False,boot_observed=False,physical_recovery_verified=False)))
