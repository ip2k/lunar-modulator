"""MIT. Detached reset proof tests; all SG, wire and reset evidence modeled."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_diagnostic_detached_probe as p
import fm1_diagnostic_detached_sg as n
import fm1_sdk_install as install
import fm1_fixed_target_reset as target_reset
import fm1_uboot_read as reader
from test_diagnostic_stage_probe import RAW, PLAIN, USB, MAPPING, snapshot, boot_events, Model
from test_diagnostic_stage_sg import mock_sg
from test_sdk_rehearsal import actual, SGModel
from test_sdk_install import envelope
from test_fixed_target_reset import target_config


def wire(usb=USB,new=None):
    # Complete 31-byte BOT OUT CBW then a 16-byte IN disconnected without reply.
    cbw=b'USBC'+bytes.fromhex('f9820000')+bytes.fromhex('10000000800010fc0c00000001ffffffffffffffffffff')
    addr=f"{usb['busnum']}:{int(usb['devnum']):03}:1"
    return (f'a 10 S Bo:{addr} -115 31 = {cbw.hex()}\n'
            f'a 11 C Bo:{addr} 0 31 >\n'
            f'b 12 S Bi:{addr} -115 16 <\n'
            f'b 13 C Bi:{addr} -108 0\n').encode()


def detached_events(c,sha,manifest):
    events=boot_events(c,sha,manifest)[:2]
    events.append(dict(time=time.time(),event='reset_stopped_ambiguous',error='ValueError',
        detail='Exactly one SG device on pinned topology required',retry=False,
        core_reset_observed=False,boot_observed=False,display_observed=False,physical_recovery_verified=False))
    return events


def test_exact_transmitted_disconnected_wire_not_completion():
    result=p.verify_wire(wire(),USB,dict(USB,devnum='30'))
    assert result['reset_cbw_transmitted'] and not result['reset_request_completed']
    assert not result['reset_core_observed']


@pytest.mark.parametrize('fault',['duplicate','nooutack','noin','success','csw','outlen','inlen',
    'wrongarg','wrongaddr','wrongendpoint','payload','latevendor','malformed','empty'])
def test_wire_rejects_other_outcomes(fault):
    raw=wire()
    if fault=='duplicate':raw+=raw
    elif fault=='nooutack':raw=b'\n'.join(raw.splitlines()[0:1]+raw.splitlines()[2:])
    elif fault=='noin':raw=b'\n'.join(raw.splitlines()[:2])
    elif fault=='success':raw=raw.replace(b'-108 0',b'0 16')
    elif fault=='csw':raw+=b'b 14 C Bi:3:029:1 0 13 = 55534253000000000000000000\n'
    elif fault=='outlen':raw=raw.replace(b'0 31 >',b'0 30 >')
    elif fault=='inlen':raw=raw.replace(b'-115 16 <',b'-115 15 <')
    elif fault=='wrongarg':raw=raw.replace(b'fc0c00000001',b'fc0c00000000')
    elif fault=='wrongaddr':raw=raw.replace(b':029:',b':031:')
    elif fault=='wrongendpoint':raw=raw.replace(b':029:1',b':029:2')
    elif fault=='payload':raw+=b'x 20 S Bo:3:029:1 -115 4 = 00000000\n'
    elif fault=='latevendor':raw+=raw.splitlines()[0]+b'\n'
    elif fault=='malformed':raw=raw.replace(b'55534243',b'zz534243')
    else:raw=b''
    with pytest.raises(ValueError):p.verify_wire(raw,USB,dict(USB,devnum='30'))


@pytest.mark.parametrize('index',range(16))
def test_every_reset_cdb_byte_changed_rejected(index):
    raw=wire();old=bytes.fromhex('fc0c00000001ffffffffffffffffffff');new=bytearray(old);new[index]^=1
    with pytest.raises(ValueError):p.verify_wire(raw.replace(old.hex().encode(),new.hex().encode()),USB,dict(USB,devnum='30'))


def test_standard_kernel_tur_is_permitted_before_but_not_after_reset():
    cbw=b'USBC'+bytes(4)+bytes(6)+b'\x06'+bytes(16)
    tur=f'x 1 S Bo:3:029:1 -115 31 = {cbw.hex()}\n'.encode()
    p.verify_wire(tur+wire(),USB,dict(USB,devnum='30'))
    with pytest.raises(ValueError):p.verify_wire(wire()+tur,USB,dict(USB,devnum='30'))


@pytest.mark.parametrize('field,value',[('error','OSError'),('detail','other error'),('retry',True),
    ('boot_observed',True),('core_reset_observed',True),('event','reset_request_completed'),('time',float('nan'))])
def test_detached_event_predicates_are_exact(field,value):
    c=dict(install_campaign_sha256='install',install_commands_sha256='commands')
    e=detached_events(c,'boot','manifest');e[-1][field]=value
    with pytest.raises(ValueError):p.verify_detached_boot(b'\n'.join(json.dumps(x).encode() for x in e),c,'boot','manifest',1)


@pytest.fixture
def prepared(tmp_path):
    tmp_path.chmod(0o700);frozen=tmp_path/'checked';frozen.write_bytes(b'yes')
    c=dict(receipt_path=str(tmp_path/'probe'),target_boot_campaign_sha256=p.BOOT_CAMPAIGN_SHA,rom_snapshot_sha256='model')
    q=p.Prepared(p.canonical(c),'model',p.canonical(snapshot(p.BOOT_CAMPAIGN_SHA)),((frozen,b'yes',100),),())
    p._AUTHORIZED.add(q);return q


def test_fixed_two_read_mechanics_preserve_detached_claim(prepared):
    model=Model(prepared)
    # Model from incumbent emits incumbent Completion; use own type explicitly.
    old=model.exchange
    def exchange(*args):return p.Completion(old(*args).data)
    model.exchange=exchange
    result=p.run_campaign(prepared,lambda _:model)
    assert model.calls==list(p.OPERATIONS) and model.closed==1
    assert result['target_reset_outcome']=='transmitted-detached-not-completed'
    assert result['reset_request_completed'] is False and result['display_observed'] is False


@pytest.mark.parametrize('field',['campaign','campaign_sha256','snapshot','evidence','policies'])
def test_copied_prepared_never_opens(prepared,field):
    with pytest.raises(ValueError):p.run_campaign(replace(prepared,**{field:None}),lambda _:pytest.fail('opened'))


def test_native_exact_two_mocked_ioctls_and_no_reopen(prepared,monkeypatch):
    obj=n.Prepared(b'{}','native-model',prepared,p,SimpleNamespace(),reader.SGHeader,prepared.evidence)
    n._AUTHORIZED.add(obj);state=mock_sg(obj,monkeypatch)
    result=n.run_campaign(obj)
    assert state.calls==list(n.OPERATIONS) and state.closed==[888]
    assert result['reset_request_completed'] is False
    with pytest.raises(FileExistsError):n.run_campaign(obj)
    assert state.calls==list(n.OPERATIONS)


def test_actual_private_completed_install_detached_proof_factory(actual,monkeypatch,tmp_path):
    """Actual APP/ELF/backup, modeled reset/wrapper/wire; no physical proof."""
    ip=tmp_path/'install.json';envelope(ip,actual.path,actual.config['receipt_path'])
    accepted=install.prepare_campaign(ip);model=SGModel(monkeypatch,json.loads(accepted.mapping),actual.baseline)
    monkeypatch.setattr(accepted.bridge,'discover_sg',model.discover);install.run_campaign(accepted)
    bc=target_config(actual,ip);parent=Path(actual.config['receipt_path']).parent
    bc['receipt_path']=str(parent/'modeled-target-reset');run=tmp_path/'target-reset-run';run.mkdir(mode=0o700)
    bp=run/'campaign.json';bp.write_bytes(p.canonical(bc));boot=target_reset.prepare_campaign(bp)
    sha=p.digest(bp.read_bytes());monkeypatch.setattr(p,'BOOT_CAMPAIGN_SHA',sha)
    receipt=Path(bc['receipt_path']);receipt.mkdir(mode=0o700);(parent/'.target-core-reset.consumed').write_text(sha)
    opened=time.time();events=detached_events(bc,sha,boot.backup_manifest_sha256)
    commands=receipt/'commands.jsonl';commands.write_bytes(b'\n'.join(p.canonical(e) for e in events))
    exited=time.time();usb=dict(bc['usb_binding'],devnum=str(int(bc['usb_binding']['devnum'])+1))
    mapping=copy.deepcopy(bc['sg_binding']);mapping['usb_identity'][1]+=1;mapping['node_identity'][1]+=1
    sp=run/'rom-snapshot.json';sp.write_bytes(p.canonical(snapshot(sha,usb,mapping)));snap=json.loads(sp.read_bytes());now=time.time()
    fake_wrapper=b'modeled-not-physical-wrapper';monkeypatch.setattr(p,'BOOT_WRAPPER_SHA',p.digest(fake_wrapper))
    files={'execute-once.py':fake_wrapper,'wrapper-attempt.json':p.canonical(dict(time=opened,campaign_sha256=sha,adapter_sha256=p.TARGET_RESET_SHA,retry=False)),
        'capture-open.json':p.canonical(dict(time=opened,timeout_pid=10,cat_pid=11,process_group=10,open_capture_fd=True)),
        'execution-exit.json':p.canonical(dict(time=exited,exit_status=1,campaign_sha256=sha,capture_alive_after_child=True,retry=False)),
        'capture-stop.json':p.canonical(dict(time=now,process_group=10,returncode=-15,owned_processes_only=True)),
        'rom-observations.json':p.canonical(dict(time=now,found=True,observations=[dict(time=snap['observed_at'],usb_binding=usb)],passive_sysfs_only=True,no_later_device_commands=True)),
        'execution.stdout':b'modeled stopped discovery','usbmon3.stderr':b'','usbmon3.txt':wire(bc['usb_binding'],usb)}
    for name,data in files.items():(run/name).write_bytes(data)
    config=dict(schema=1,kind='fm1-exact-detached-diagnostic-stage-probe',adapter_sha256=p.digest(Path(p.__file__).read_bytes()),
        target_boot_campaign_path=str(bp),target_boot_campaign_sha256=sha,target_boot_commands_sha256=p.digest(commands.read_bytes()),target_boot_exit_status=1,
        rom_snapshot_path=str(sp),rom_snapshot_sha256=p.digest(sp.read_bytes()),active_session_state='post-target-boot-rom-no-later-commands-no-loader-upload',
        receipt_path=str(parent/'detached-stage-probe'),reset_outcome='transmitted-detached-not-completed',wrapper_files_sha256={k:p.digest(v) for k,v in files.items()})
    cp=tmp_path/'probe.json';cp.write_bytes(p.canonical(config));obj=p.prepare_campaign(cp)
    proof=p.validate_returned_state(cp,evaluated_at=now)
    assert json.loads(proof.original_inputs)==actual.config['policy_inputs'] and proof.private_parent==str(parent)
    assert not isinstance(proof,p.Prepared)
    absent_marker=parent/('.diagnostic-stage-'+sha+'.consumed');absent_marker.write_text('changed')
    with pytest.raises(ValueError):proof.check()
    absent_marker.unlink()  # Counterfactual fixture only.
    with pytest.raises(ValueError):p.run_campaign(proof,lambda _:pytest.fail('opened'))
    # Real native factory executes the exact new local source. Only experiment
    # reset/wrapper pins are replaced inside this modeled evidence fixture.
    native_path=tmp_path/'native-campaign.json'
    native=dict(schema=1,kind='fm1-exact-native-detached-diagnostic-stage-probe',
        adapter_sha256=p.digest(Path(n.__file__).read_bytes()),probe_campaign_path=str(cp),probe_campaign_sha256=p.digest(cp.read_bytes()))
    native_path.write_bytes(p.canonical(native))
    original_load=n.load_source
    def load_modeled(path,expected,name):
        module=original_load(path,expected,name)
        if Path(path)==Path(p.__file__):
            module.BOOT_CAMPAIGN_SHA=sha;module.BOOT_WRAPPER_SHA=p.digest(fake_wrapper)
        return module
    monkeypatch.setattr(n,'load_source',load_modeled)
    started=time.perf_counter();native_obj=n.prepare_campaign(native_path);factory_seconds=time.perf_counter()-started
    assert native_obj.module.digest(Path(native_obj.module.__file__).read_bytes())==n.PROBE_SHA
    for key in ('adapter_sha256','probe_campaign_sha256'):
        wrong=dict(native);wrong[key]='0'*64;native_path.write_bytes(p.canonical(wrong))
        with pytest.raises(ValueError):n.prepare_campaign(native_path)
    native_path.write_bytes(p.canonical(native))
    # Distinct successful historical schema uses unchanged ff593 source. No
    # detached error is relabeled successful; this is an independent modeled
    # counterfactual for the public helper's other reset branch.
    saved_commands=commands.read_bytes()
    successful_events=boot_events(bc,sha,boot.backup_manifest_sha256)
    for index,event in enumerate(successful_events):event['time']=opened+(snap['observed_at']-opened)*(index+1)/5
    commands.write_bytes(b'\n'.join(p.canonical(e) for e in successful_events))
    successful=dict(config);successful.pop('reset_outcome');successful.pop('wrapper_files_sha256')
    successful.update(kind='fm1-exact-diagnostic-stage-probe',adapter_sha256=p.SUCCESSFUL_PROBE_SHA,
        target_boot_exit_status=0,target_boot_commands_sha256=p.digest(commands.read_bytes()))
    success_run=tmp_path/'successful-history-run';success_run.mkdir(mode=0o700)
    success_path=success_run/'successful-history.json';success_path.write_bytes(p.canonical(successful))
    success=p.validate_returned_state(success_path,evaluated_at=now,provenance_mode='successful')
    assert success.probe_outcome=='not-attempted'
    # Separate modeled successful-reset probe uses the unchanged incumbent
    # injected factory/runner, real private install inputs and own original
    # Completion type. Its failed receipt is never relabeled detached.
    import fm1_diagnostic_stage_probe as incumbent
    successful['receipt_path']=str(parent/'successful-stage-probe-model')
    success_path.write_bytes(p.canonical(successful))
    success_prepared=incumbent.prepare_campaign(success_path)
    success_model=Model(success_prepared,fault=lambda m,reply:incumbent.Completion(reply.data,status=1))
    with pytest.raises(OSError):incumbent.run_campaign(success_prepared,lambda _:success_model)
    success_receipt=Path(successful['receipt_path'])
    success_log=[json.loads(x) for x in (success_receipt/'commands.jsonl').read_bytes().splitlines()]
    success_capture,success_wrapper=owned_capture(tmp_path,dict(successful,snapshot_for_model=obj.snapshot.decode()),
        success_path,success_log,probe_wire(usb,1),mode='successful')
    success_stopped=p.validate_returned_state(success_path,evaluated_at=now,completed_probe=success_path,
        probe_capture=success_capture,probe_wrapper_sha256=success_wrapper,provenance_mode='successful')
    assert success_stopped.probe_outcome=='stopped-read-only-probe-inconclusive';success_stopped.check()
    (success_receipt/'commands.jsonl').unlink()
    success_capture,success_wrapper=owned_capture(tmp_path,dict(successful,snapshot_for_model=obj.snapshot.decode()),
        success_path,[],b'',mode='successful')
    success_zero=p.validate_returned_state(success_path,evaluated_at=now,completed_probe=success_path,
        probe_capture=success_capture,probe_wrapper_sha256=success_wrapper,provenance_mode='successful')
    assert success_zero.probe_outcome=='pre-open-zero-command-stop';success_zero.check()
    # Remove only this counterfactual fixture before constructing the distinct
    # detached branch below; production consumed markers are never removed.
    for artifact in success_receipt.iterdir():artifact.unlink()
    success_receipt.rmdir();(parent/('.diagnostic-stage-'+sha+'.consumed')).unlink()
    commands.write_bytes(saved_commands)
    # First independent modeled probe branch stops on a recorded bad SG field.
    def bad_status(h,data,state):h.status=1
    state=mock_sg(native_obj,monkeypatch,fault=bad_status)
    with pytest.raises(OSError):n.run_campaign(native_obj)
    assert state.calls==[n.OPERATIONS[0]]
    probe_receipt=Path(config['receipt_path']);stopped_events=[json.loads(x) for x in (probe_receipt/'commands.jsonl').read_bytes().splitlines()]
    ep,wp=owned_capture(tmp_path,dict(config,snapshot_for_model=obj.snapshot.decode()),cp,stopped_events,probe_wire(usb,1))
    stopped=p.validate_returned_state(cp,evaluated_at=now,completed_probe=cp,probe_capture=ep,probe_wrapper_sha256=wp)
    assert stopped.probe_outcome=='stopped-read-only-probe-inconclusive';stopped.check()
    with pytest.raises(ValueError):p.prepare_campaign(cp)
    # Definite pre-open counterfactual: original marker stays, source runner
    # has no log and owned capture has no outbound request. No retry occurs.
    saved_log=(probe_receipt/'commands.jsonl').read_bytes();(probe_receipt/'commands.jsonl').unlink()
    ep,wp=owned_capture(tmp_path,dict(config,snapshot_for_model=obj.snapshot.decode()),cp,[],b'')
    zero=p.validate_returned_state(cp,evaluated_at=now,completed_probe=cp,probe_capture=ep,probe_wrapper_sha256=wp)
    assert zero.probe_outcome=='pre-open-zero-command-stop';zero.check()
    (probe_receipt/'commands.jsonl').write_bytes(saved_log)
    with pytest.raises(ValueError):zero.check()
    # A separately isolated modeled branch completes. Removal below is fixture
    # counterfactual construction only; production markers are never removed.
    for artifact in probe_receipt.iterdir():
        assert artifact.is_file()
        artifact.unlink()
    probe_receipt.rmdir()
    (parent/('.diagnostic-stage-'+sha+'.consumed')).unlink()
    native_path.write_bytes(p.canonical(native));native_obj=n.prepare_campaign(native_path)
    state=mock_sg(native_obj,monkeypatch);result=n.run_campaign(native_obj)
    assert state.calls==list(n.OPERATIONS)
    with pytest.raises(ValueError):p.validate_returned_state(cp,evaluated_at=now)
    historical=p.validate_returned_state(cp,evaluated_at=now,completed_probe=cp);historical.check()
    with pytest.raises(ValueError):p.prepare_campaign(cp)
    # Preserve real completed install journal bytes; genuine restore validation
    # is the recovery adapter's job. This models its final valid journal state.
    journal_path=Path(actual.config['policy_inputs']['directory'])/'journal.json'
    preserved=tmp_path/'preserved-install-journal.json';preserved.write_bytes(journal_path.read_bytes())
    transaction=__import__('fm1_flash_transaction');journal=json.loads(journal_path.read_bytes())
    journal.update(direction='restore',verified_sha256=p.digest(actual.baseline))
    transaction.save_journal(journal_path.parent,journal)
    retained=p.validate_returned_state(cp,evaluated_at=now,completed_probe=cp,install_journal_path=preserved)
    assert retained.install_journal_sha256==bc['journal_sha256']
    assert retained.original_rehearsal_campaign_sha256==json.loads(ip.read_bytes())['rehearsal_campaign_sha256']
    retained.check();preserved.write_bytes(b'changed')
    with pytest.raises(ValueError):retained.check()
    if __import__('os').environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        out=Path(__import__('os').environ['LUNAR_REHEARSAL_EVIDENCE']);(out/'detached-modeled-summary.json').write_bytes(p.canonical(dict(
            actual_private_native_inputs=True,app_sha256=p.APP_SHA,elf_sha256=p.ELF_SHA,target_sha256=p.TARGET_SHA,
            literal_experiment_pins_modeled=True,boot_wire_and_wrapper_modeled=True,hardware_access=False,native_factory_actual_source=True,factory_seconds=factory_seconds,
            failed_probe_recovery=True,pre_open_recovery=True,historical_successful_branch=True,
            successful_failed_probe_recovery=True,successful_pre_open_recovery=True,preserved_journal_checked=True,
            commands=[x[0].hex() for x in state.calls],result=result)))


def probe_wire(usb,intents):
    out=b''
    for i,(cdb,_,length) in enumerate(p.OPERATIONS[:intents]):
        cbw=b'USBC'+(i+1).to_bytes(4,'little')+length.to_bytes(4,'little')+bytes((128,0,len(cdb)))+cdb.ljust(16,b'\0')
        out+=f'q{i} 40 S Bo:{usb["busnum"]}:{int(usb["devnum"]):03}:1 -115 31 = {cbw.hex()}\n'.encode()
    return out


def owned_capture(tmp_path,config,probe_path,events,wire_bytes,*,no_log=False,mode='detached'):
    """Modeled owned wrapper envelope. No actual capture or hardware access."""
    run=probe_path.parent;native_path=run/'native-campaign.json'
    native=dict(schema=1,kind='fm1-exact-native-detached-diagnostic-stage-probe' if mode=='detached' else 'fm1-exact-native-diagnostic-stage-probe',
        adapter_sha256=p.digest(Path(n.__file__).read_bytes()) if mode=='detached' else p.SUCCESSFUL_NATIVE_SHA,probe_campaign_path=str(probe_path),
        probe_campaign_sha256=p.digest(probe_path.read_bytes()))
    native_path.write_bytes(p.canonical(native));sha=p.digest(native_path.read_bytes())
    snap=json.loads(config['snapshot_for_model']);now=time.time()
    first=events[0]['time'] if events else now;last=events[-1]['time'] if events else now
    t=snap['observed_at']
    wrapper=b'modeled private wrapper; no executable hardware test'
    attempt=dict(time=t,target_boot_campaign_sha256=config['target_boot_campaign_sha256'],
        adapter_sha256=native['adapter_sha256'],probe_sha256=config['adapter_sha256'],retry=False)
    attempt['transmitted_detached_only' if mode=='detached' else 'successful_reset_only']=True
    files={'execute-once.py':wrapper,'wrapper-attempt.json':p.canonical(attempt),
        'preflight.json':p.canonical(dict(time=t,factory_seconds=0.1,campaign_sha256=sha,
            rom_snapshot_sha256=config['rom_snapshot_sha256'],snapshot_age_seconds=0,hardware_access=False)),
        'capture-open.json':p.canonical(dict(time=t,timeout_pid=21,cat_pid=22,process_group=21,open_capture_fd=True)),
        'capture-stop.json':p.canonical(dict(time=now,process_group=21,returncode=-15,owned_processes_only=True)),
        'execution-exit.json':p.canonical(dict(time=last,exit_status=1,campaign_sha256=sha,capture_alive_after_child=True,
            retry=False,display_observed=False,physical_recovery_verified=False)),
        'execution.stdout':b'modeled failed SG','usbmon3.stderr':b'','usbmon3.txt':wire_bytes}
    for name,data in files.items():(run/name).write_bytes(data)
    ep=run/'stopped-capture.json';ep.write_bytes(p.canonical(dict(schema=1,kind='fm1-owned-stopped-stage-probe-capture',
        native_campaign_path=str(native_path),native_campaign_sha256=sha,wrapper_files_sha256={k:p.digest(v) for k,v in files.items()})))
    return ep,p.digest(wrapper)


@pytest.fixture
def failed_evidence(tmp_path,prepared):
    c=json.loads(prepared.campaign);c.update(adapter_sha256=p.digest(Path(p.__file__).read_bytes()),snapshot_for_model=prepared.snapshot.decode())
    # Direct bounded helper tests use a modeled campaign. The actual factory
    # test below validates the full real native/SDK/install dependencies.
    run=tmp_path/'modeled-probe-run';run.mkdir();cp=run/'probe-campaign.json';cp.write_bytes(p.canonical(c))
    obj=p.Prepared(p.canonical(c),p.digest(cp.read_bytes()),prepared.snapshot,prepared.evidence,())
    p._AUTHORIZED.add(obj)
    model=Model(obj);old=model.exchange
    def exchange(*args):
        return p.Completion(old(*args).data,status=1)
    model.exchange=exchange
    with pytest.raises(OSError):p.run_campaign(obj,lambda _:model)
    receipt=Path(c['receipt_path']);events=[json.loads(x) for x in (receipt/'commands.jsonl').read_bytes().splitlines()]
    ep,wp=owned_capture(tmp_path,c,cp,events,probe_wire(json.loads(obj.snapshot)['usb_binding'],1))
    return SimpleNamespace(c=c,cp=cp,obj=obj,receipt=receipt,events=events,ep=ep,wp=wp,parent=receipt.parent)


def check_failed(e,mode='detached'):
    def freeze(path,expected=None,limit=2*1048576):
        raw=p.read_file(path,limit)
        if expected is not None and p.digest(raw)!=expected:raise ValueError('pin differs')
        return raw
    return p.verify_stopped_probe(e.cp,e.c,json.loads(e.obj.snapshot),e.parent,freeze,e.ep,mode,e.wp)


def test_exact_failed_status_capture_preserves_stop(failed_evidence):
    assert check_failed(failed_evidence)=='stopped-read-only-probe-inconclusive'
    assert failed_evidence.events[-1]['classification']=='inconclusive'


@pytest.mark.parametrize('zero_commands',[False,True])
def test_successful_reset_failed_probe_capture_retains_exact_original_mode(failed_evidence,zero_commands):
    e=failed_evidence;e.c['adapter_sha256']=p.SUCCESSFUL_PROBE_SHA
    e.cp.write_bytes(p.canonical(e.c));sha=p.digest(e.cp.read_bytes())
    (e.parent/('.diagnostic-stage-'+e.c['target_boot_campaign_sha256']+'.consumed')).write_text(sha)
    e.events[0]['campaign_sha256']=sha
    if zero_commands:
        (e.receipt/'commands.jsonl').unlink();events=[]
    else:
        events=e.events;(e.receipt/'commands.jsonl').write_bytes(b'\n'.join(p.canonical(x) for x in events))
    e.ep,e.wp=owned_capture(e.parent,e.c,e.cp,events,probe_wire(json.loads(e.obj.snapshot)['usb_binding'],0 if zero_commands else 1),mode='successful')
    assert check_failed(e,'successful')==('pre-open-zero-command-stop' if zero_commands else 'stopped-read-only-probe-inconclusive')
    attempt=e.ep.parent/'wrapper-attempt.json';obj=json.loads(attempt.read_bytes());obj.pop('successful_reset_only');attempt.write_bytes(p.canonical(obj))
    envelope=json.loads(e.ep.read_bytes());envelope['wrapper_files_sha256']['wrapper-attempt.json']=p.digest(attempt.read_bytes());e.ep.write_bytes(p.canonical(envelope))
    with pytest.raises(ValueError,match='attempt'):check_failed(e,'successful')


@pytest.mark.parametrize('different_response_hash',[False,True])
def test_unpublished_completed_capture_binds_second_response(failed_evidence,different_response_hash):
    e=failed_evidence;t=e.events[-1]['time']
    first=dict(e.events[2],status=0)
    second=dict(first,time=t,index=1,response_sha256='0'*64 if different_response_hash else p.digest(RAW))
    intent=dict(time=t,event='sg_submit_intent',index=1,cdb=p.READ_STAGE.hex(),out_len=0,in_len=32,retry=False)
    result=dict(campaign_sha256=p.digest(e.cp.read_bytes()),raw_sha256=p.digest(RAW),decoded_sha256=p.digest(PLAIN),
        inquiry_sha256=first['response_sha256'],target_reset_outcome='transmitted-detached-not-completed',
        reset_request_completed=False,**p.interpret_stage(PLAIN))
    events=[*e.events[:2],first,intent,second,dict(time=t,event='stage_capture_completed',**result,retry=False),e.events[-1]]
    (e.receipt/'commands.jsonl').write_bytes(b'\n'.join(p.canonical(x) for x in events))
    (e.receipt/'raw.bin').write_bytes(RAW);(e.receipt/'decoded.bin').write_bytes(PLAIN)
    e.ep,e.wp=owned_capture(e.parent,e.c,e.cp,events,probe_wire(json.loads(e.obj.snapshot)['usb_binding'],2))
    if different_response_hash:
        with pytest.raises(ValueError,match='Unpublished decoded'):check_failed(e)
    else:assert check_failed(e)=='stopped-read-only-probe-inconclusive'


@pytest.mark.parametrize('fault',['marker','campaign','extra_intent','next_after_bad','result','error','retry','time','response_hash',
    'wrong_wrapper','missing_capture','out_payload','fd07_without_intent','repeat_fd07','reset','upload','write','sense','short_capture'])
def test_stopped_evidence_rejects_drift_retry_and_forbidden_wire(failed_evidence,fault):
    e=failed_evidence
    if fault=='marker':(e.parent/('.diagnostic-stage-'+e.c['target_boot_campaign_sha256']+'.consumed')).write_text('different')
    elif fault=='campaign':e.cp.write_bytes(b'{}')
    elif fault in ('extra_intent','next_after_bad'):
        e.events.insert(-1,dict(time=e.events[-1]['time'],event='sg_submit_intent',index=1,cdb=p.READ_STAGE.hex(),out_len=0,in_len=32,retry=False))
    elif fault=='result':(e.receipt/'result.json').write_bytes(b'{}')
    elif fault in ('error','retry','time'):e.events[-1][fault]=False if fault=='error' else (True if fault=='retry' else float('nan'))
    elif fault=='response_hash':e.events[2]['response_sha256']='bad'
    elif fault=='sense':e.events[2]['sense_len']=1
    elif fault=='wrong_wrapper':e.wp='0'*64
    elif fault=='missing_capture':(e.ep.parent/'usbmon3.txt').unlink()
    else:
        wire_bytes=probe_wire(json.loads(e.obj.snapshot)['usb_binding'],2)
        if fault=='out_payload':wire_bytes+=f'x 40 S Bo:3:{int(json.loads(e.obj.snapshot)["usb_binding"]["devnum"]):03}:1 -115 4 = 00000000\n'.encode()
        if fault in ('fd07_without_intent','repeat_fd07'):pass
        if fault=='repeat_fd07':wire_bytes+=wire_bytes.splitlines()[-1]+b'\n'
        if fault in ('reset','upload','write'):
            wire_bytes=wire_bytes.replace(p.READ_STAGE.hex().encode(),{'reset':'fc0c00000001ffffffffffffffffffff','upload':'fd0601c033d80020ffffffffffffffff','write':'fb06000040000020ffffffffffffffff'}[fault].encode())
        if fault=='short_capture':wire_bytes=wire_bytes.replace(b' -115 31',b' -115 30')
        ep,wp=owned_capture(e.parent,e.c,e.cp,e.events,wire_bytes);e.ep,e.wp=ep,wp
    (e.receipt/'commands.jsonl').write_bytes(b'\n'.join(p.canonical(x) if fault!='time' else json.dumps(x).encode() for x in e.events))
    with pytest.raises((ValueError,FileNotFoundError)):check_failed(e)


@pytest.mark.parametrize('log_present',[True,False])
def test_definite_pre_open_no_log_requires_zero_capture_commands(failed_evidence,log_present):
    e=failed_evidence
    if log_present:(e.receipt/'commands.jsonl').write_bytes(b'')
    else:(e.receipt/'commands.jsonl').unlink()
    e.ep,e.wp=owned_capture(e.parent,e.c,e.cp,[],b'')
    assert check_failed(e)=='pre-open-zero-command-stop'
    e.ep,e.wp=owned_capture(e.parent,e.c,e.cp,[],probe_wire(json.loads(e.obj.snapshot)['usb_binding'],1))
    with pytest.raises(ValueError):check_failed(e)


@pytest.mark.parametrize('field,value',[('status',1),('masked',1),('msg',1),('host',1),('driver',1),('resid',1),('resid',-1),('info',1),('sense_len',1),('sense_len',33)])
@pytest.mark.parametrize('which',[1,2])
def test_detached_native_failed_fields_logged_no_second_request(prepared,monkeypatch,field,value,which):
    obj=n.Prepared(b'{}','native-model',prepared,p,SimpleNamespace(),reader.SGHeader,prepared.evidence);n._AUTHORIZED.add(obj)
    def fault(h,data,state):
        if len(state.calls)==which:setattr(h,field,value)
    state=mock_sg(obj,monkeypatch,fault=fault)
    with pytest.raises(OSError):n.run_campaign(obj)
    events=[json.loads(x) for x in (Path(json.loads(prepared.campaign)['receipt_path'])/'commands.jsonl').read_bytes().splitlines()]
    assert len(state.calls)==which and [e for e in events if e['event']=='sg_completion'][-1][field]==value
    assert events[-1]['event']=='stage_probe_stopped_ambiguous'


@pytest.mark.parametrize('field',['campaign','campaign_sha256','probe','module','bridge','header_type','evidence'])
def test_detached_native_copied_authority_rejected_before_open(prepared,monkeypatch,field):
    obj=n.Prepared(b'{}','native-model',prepared,p,SimpleNamespace(),reader.SGHeader,prepared.evidence);n._AUTHORIZED.add(obj)
    state=mock_sg(obj,monkeypatch)
    with pytest.raises(ValueError):n.run_campaign(replace(obj,**{field:None}))
    assert state.opens==state.calls==[]


def test_detached_native_frozen_drift_prevents_open(prepared,monkeypatch):
    obj=n.Prepared(b'{}','native-model',prepared,p,SimpleNamespace(),reader.SGHeader,prepared.evidence);n._AUTHORIZED.add(obj)
    state=mock_sg(obj,monkeypatch);prepared.evidence[0][0].write_bytes(b'changed')
    with pytest.raises(ValueError):n.run_campaign(obj)
    assert state.opens==state.calls==[]
