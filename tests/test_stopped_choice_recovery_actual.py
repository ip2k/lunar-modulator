"""MIT. Actual private lineage with modeled resumed read/capture, no devices."""
import json
from pathlib import Path
import shutil
import time

import pytest

import fm1_stopped_choice_recovery_evidence as evidence
from test_diagnostic_stage_resume import actual_tree, actual_prepared, model


def modeled_wire(operations,usb):
    lines=[];token=0
    def urb(direction,size,data=b''):
        nonlocal token
        token+=1
        address=f'{direction}:{usb["busnum"]}:{int(usb["devnum"]):03}:1'
        lines.append(f'{token} {token} S {address} -115 {size}'+(' = '+data.hex() if data else ''))
        lines.append(f'{token} {token} C {address} 0 {size}')
    for index,(cdb,payload,size) in enumerate(operations):
        assert not payload
        command=b'USBC'+(index+1).to_bytes(4,'little')+size.to_bytes(4,'little')+bytes([128,0,len(cdb)])+cdb+bytes(16-len(cdb))
        urb('Bo',31,command);urb('Bi',size);urb('Bi',13)
    return ('\n'.join(lines)+'\n').encode('ascii')


@pytest.mark.parametrize('outcome',['completed','stopped','consumed-empty','consumed-missing'])
def test_actual_lineage_resumed_receipt_and_owned_capture(actual_prepared,monkeypatch,outcome):
    m,stage,prepared,cp=actual_prepared;run=cp.parent;c=json.loads(cp.read_bytes())
    source=stage/'tools/fm1_stopped_choice_recovery_evidence.py';shutil.copyfile(evidence.__file__,source)
    module=evidence.load_source(source,evidence.digest(source.read_bytes()),'_actual_successor_evidence')
    module.STAGE_SOURCE_SHA=m.digest(Path(m.__file__).read_bytes())
    template=Path('/source/build/diagnostic-stage-resume-bench-template/execute-once.py').read_text()
    bound=template.replace('ADAPTER=None','ADAPTER='+repr(c['adapter_sha256'])).replace(
        'CAMPAIGN=None','CAMPAIGN='+repr(prepared.campaign_sha256)).replace('WITNESS=None','WITNESS='+repr(c['witness_sha256']))
    bound_path=run/'execute-once-bound.py';bound_path.write_text(bound)
    module.WRAPPER_SOURCE_SHA=evidence.digest(bound_path.read_bytes())
    # Only the new evidence helper's activation pins are substituted in this model.
    # All historical files/source literals and actual stage factory stay unchanged.
    start=time.time();status=0;result=None;operations=()
    if outcome in ('completed','stopped'):
        state,transport=model(m,prepared,fault=(lambda _,fields:fields.update(status=1)) if outcome=='stopped' else None)
        if outcome=='completed':result=m.run_campaign(prepared,lambda _:transport)
        else:
            with pytest.raises(OSError):m.run_campaign(prepared,lambda _:transport)
            status=1
        operations=state.calls
    else:
        receipt=Path(c['receipt_path']);receipt.mkdir(mode=0o700)
        marker=receipt.parent/('.diagnostic-stage-resume-'+m.BOOT_SHA+'.consumed');marker.write_text(prepared.campaign_sha256)
        if outcome=='consumed-empty':(receipt/'commands.jsonl').write_bytes(b'')
        status=1
    end=time.time();witness=json.loads(prepared.witness)
    t=witness['observed_at']
    records={
        'wrapper-attempt.json':dict(time=t,campaign_sha256=prepared.campaign_sha256,adapter_sha256=c['adapter_sha256'],witness_sha256=c['witness_sha256'],original_snapshot_refreshed=False,retry=False),
        'preflight.json':dict(time=start-0.002,factory_seconds=0.001,campaign_sha256=prepared.campaign_sha256,witness_sha256=c['witness_sha256'],hardware_access=False,original_rom_snapshot_sha256=m.SNAPSHOT_SHA,original_snapshot_refreshed=False),
        'capture-open.json':dict(time=start-0.001,timeout_pid=10,cat_pid=11,process_group=10,open_capture_fd=True),
        'execution-exit.json':dict(time=end,exit_status=status,campaign_sha256=prepared.campaign_sha256,capture_alive_after_child=True,retry=False,display_observed=False,physical_recovery_verified=False),
        'capture-stop.json':dict(time=end,process_group=10,returncode=-15,owned_processes_only=True)}
    for name,value in records.items():(run/name).write_bytes(m.canonical(value))
    (run/'execution.stdout').write_bytes(m.canonical(result) if result else b'')
    (run/'usbmon3.txt').write_bytes(modeled_wire(operations,witness['usb_binding']));(run/'usbmon3.stderr').write_bytes(b'')
    names={'execute-once-bound.py','wrapper-attempt.json','preflight.json','capture-open.json','capture-stop.json','execution-exit.json','execution.stdout','usbmon3.txt','usbmon3.stderr','campaign.json','witness.json'}
    envelope=dict(schema=1,kind='fm1-owned-resumed-stage-capture',campaign_sha256=prepared.campaign_sha256,adapter_sha256=c['adapter_sha256'],exit_status=status,retry=False,original_snapshot_refreshed=False,wrapper_files_sha256={n:m.digest((run/n).read_bytes()) for n in names})
    owned=run/'owned-capture.json';owned.write_bytes(m.canonical(envelope))
    path=run/'recovery-evidence.json';config=dict(schema=1,kind='fm1-actual-stopped-choice-post-read-evidence',adapter_sha256=module.digest(source.read_bytes()),choice_path=c['choice_path'],stage_campaign_path=str(cp),stage_campaign_sha256=prepared.campaign_sha256,owned_capture_path=str(owned),owned_capture_sha256=m.digest(owned.read_bytes()))
    path.write_bytes(module.canonical(config));proof=module.validate_returned_state(path);proof.check()
    expected={'completed':'completed-two-read','stopped':'stopped-read-only-inconclusive','consumed-empty':'consumed-pre-log-zero-request-stop','consumed-missing':'consumed-pre-log-zero-request-stop'}
    assert proof.probe_outcome==expected[outcome] and proof.snapshot==prepared.snapshot
    assert proof.historical.historical_admission_time==1791775862.0725162
    assert module.digest((stage/'target-reset-stage-v1/rom-snapshot.json').read_bytes())==m.SNAPSHOT_SHA
    assert proof.install_journal_sha256=='0d7973321b33335715335ce6413546c02bc16ad08f8b952ab6e3b223231e9db4'
    # Late negative evidence must be caught by the actual composed proof.
    late=run/'wrapper-cleanup-ambiguous.json';late.write_bytes(b'{}')
    with pytest.raises(ValueError):proof.check()
    late.unlink()
    with pytest.raises(ValueError,match='Evidence only'):module.prepare_campaign(path)


def test_actual_physical_read_files_admit_without_transport(actual_tree,monkeypatch):
    import os
    m,stage=actual_tree
    exported=Path(os.environ['LUNAR_STAGE_READ_ACTUAL'])
    parent=stage.parent
    for source in exported.iterdir():
        destination=parent/source.name
        if source.is_dir():shutil.copytree(source,destination,dirs_exist_ok=True)
        else:shutil.copyfile(source,destination)
    (stage/'diagnostic-stage-resume-v1').chmod(0o700)
    (parent/'diagnostic-stage-resume-001').chmod(0o700)
    source=stage/'tools/fm1_stopped_choice_recovery_evidence.py';shutil.copyfile(evidence.__file__,source)
    module=evidence.load_source(source,evidence.digest(source.read_bytes()),'_actual_physical_read_evidence')
    run=stage/'diagnostic-stage-resume-v1';cp=run/'campaign.json';owned=run/'owned-capture.json';c=json.loads(cp.read_bytes())
    assert c['adapter_sha256']==module.STAGE_SOURCE_SHA
    assert module.digest((run/'execute-once-bound.py').read_bytes())==module.WRAPPER_SOURCE_SHA
    envelope=dict(schema=1,kind='fm1-actual-stopped-choice-post-read-evidence',adapter_sha256=module.digest(source.read_bytes()),choice_path=c['choice_path'],stage_campaign_path=str(cp),stage_campaign_sha256=module.digest(cp.read_bytes()),owned_capture_path=str(owned),owned_capture_sha256=module.digest(owned.read_bytes()))
    path=run/'recovery-evidence.json';path.write_bytes(module.canonical(envelope))
    proof=module.validate_returned_state(path);proof.check()
    assert proof.probe_outcome=='completed-two-read'
    assert proof.historical.historical_admission_time==1791775862.0725162
    assert proof.install_journal_sha256=='0d7973321b33335715335ce6413546c02bc16ad08f8b952ab6e3b223231e9db4'
    assert module.digest((stage/'target-reset-stage-v1/rom-snapshot.json').read_bytes())==m.SNAPSHOT_SHA
    # Factory has no device discovery or transport API to invoke.
    with pytest.raises(ValueError,match='Evidence only'):module.prepare_campaign(path)
    out=Path(os.environ['LUNAR_ADMISSION_EVIDENCE']);out.mkdir(exist_ok=True)
    (out/'actual-admission.json').write_bytes(module.canonical(dict(source_sha256=module.digest(source.read_bytes()),stage_sha256=module.STAGE_SOURCE_SHA,wrapper_sha256=module.WRAPPER_SOURCE_SHA,campaign_sha256=module.digest(cp.read_bytes()),owned_capture_sha256=module.digest(owned.read_bytes()),probe_outcome=proof.probe_outcome,frozen_files=len(proof.evidence),negative_paths=len(proof.absent),hardware_access=False,private_actual_files_verified=True,transport_opened=False,original_snapshot_refreshed=False)))
