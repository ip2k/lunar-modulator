"""MIT. Distinct successor authority; synthetic SG plus actual private file gate."""
import ctypes as C
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_stopped_choice_backup as n
import fm1_fixed_loader_backup as bridge
import fm1_uboot_read as reader
import fm1_sdk_rehearsal as rehearsal
from test_diagnostic_stage_resume import actual_tree


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    tmp_path.chmod(0o700);root=tmp_path/'tools';root.mkdir()
    for name in ('fm1_stopped_choice_backup.py','fm1_returned_rom_backup.py','fm1_sdk_rehearsal.py',
                 'fm1_stopped_choice_recovery_evidence.py','fm1_fixed_loader_backup.py','fm1_uboot_read.py'):
        shutil.copyfile(Path(n.__file__).with_name(name),root/name)
    monkeypatch.setattr(n,'__file__',str(root/'fm1_stopped_choice_backup.py'))
    # This is a synthetic factory test, so bind its copied rehearsal source to
    # its exact local bytes. The production adapter keeps its immutable pin.
    monkeypatch.setattr(n, 'REHEARSAL_SHA', n.digest((root/'fm1_sdk_rehearsal.py').read_bytes()))
    loader=bytes((i*7)%256 for i in range(bridge.LOADER_SIZE));lp=tmp_path/'loader';lp.write_bytes(loader)
    monkeypatch.setattr(bridge,'LOADER_SHA',n.digest(loader))
    inventory=[]
    for i,offset in enumerate(range(0,len(loader),512)):
        cdb,_,size=reader.request(0xfb06,'rom',address=bridge.RAM+offset,payload=loader[offset:offset+512])
        inventory.append(dict(index=i,address=bridge.RAM+offset,bytes=512,cdb_sha256=n.digest(cdb),payload_sha256=n.digest(loader[offset:offset+512]),read_size=size))
    profile=dict(upload_inventory=inventory,patched_encrypted_sha256=bridge.LOADER_SHA,original_encrypted_sha256=bridge.ORIGINAL_SHA)
    pp=tmp_path/'profile';pp.write_bytes(n.canonical(profile));monkeypatch.setattr(bridge,'PROFILE_SHA',n.digest(pp.read_bytes()))
    ps=tmp_path/'profile-source';ps.write_bytes(b'MIT synthetic profile source');monkeypatch.setattr(bridge,'PROFILE_SOURCE_SHA',n.digest(ps.read_bytes()))
    usb=dict(path='3-2',busnum='3',devnum='26',vid='4c4a',pid='8057')
    mapping=dict(node='/dev/sgMOCK',node_identity=[1,2,3],usb_identity=[4,5,6])
    now=time.time();snapshot=dict(observed_at=now-10,usb_binding=usb,sg_binding=mapping)
    late=tmp_path/'forbidden-late'
    proof=SimpleNamespace(snapshot=n.canonical(snapshot),original_inputs=b'{}',manifest_sha256='a'*64,
        private_parent=str(tmp_path),policies=(),evidence=(),terminal_at=now-3,
        original_rehearsal_campaign_sha256='b'*64,install_journal_sha256='c'*64,
        probe_outcome='completed-two-read',absent=(late,))
    def check():
        if os.path.lexists(late):raise ValueError('late absent evidence')
    proof.check=check
    original=n.load_source
    def load(path,pin,name):
        if Path(path).name=='fm1_stopped_choice_recovery_evidence.py':
            return SimpleNamespace(validate_returned_state=lambda *a,**k:proof)
        if Path(path).name=='fm1_sdk_rehearsal.py':
            return SimpleNamespace(SOURCES={},imports=lambda:{'fm1_fixed_loader_backup':bridge,'fm1_uboot_read':reader})
        return original(path,pin,name)
    monkeypatch.setattr(n,'load_source',load)
    admission=tmp_path/'admission';admission.write_bytes(b'actual proof separately tested')
    witness=dict(schema=1,kind='fm1-passive-stopped-choice-backup-connection',observed_at=now-1,
        usb_binding=usb,sg_binding=mapping,original_rom_snapshot_sha256=n.SNAPSHOT_SHA,
        returned_admission_sha256=n.digest(admission.read_bytes()),quiet_state=n.STATE)
    wp=tmp_path/'witness';wp.write_bytes(n.canonical(witness))
    c=dict(schema=1,kind=n.KIND,adapter_sha256=n.digest(Path(n.__file__).read_bytes()),
        returned_admission_path=str(admission),returned_admission_sha256=n.digest(admission.read_bytes()),
        connection_witness_path=str(wp),connection_witness_sha256=n.digest(wp.read_bytes()),
        loader_path=str(lp),profile_path=str(pp),profile_source_path=str(ps),active_session_state=n.STATE,
        receipt_path=str(tmp_path/'receipt'))
    cp=tmp_path/'campaign';cp.write_bytes(n.canonical(c));p=n.prepare_campaign(cp)
    return p,cp,c,proof


def save(cp,c):cp.write_bytes(n.canonical(c))


def sg_mock(p,monkeypatch,*,fault=None,binding_fault=None,close_fault=None,target=None):
    monkeypatch.setattr(n.sys,'platform','linux');snap=json.loads(p.snapshot)
    state=SimpleNamespace(calls=[],closed=0,discoveries=0)
    def discover(usb):
        assert usb==snap['usb_binding'];state.discoveries+=1
        if binding_fault:binding_fault(state)
        return json.loads(n.canonical(snap['sg_binding']))
    monkeypatch.setattr(p.bridge,'discover_sg',discover)
    opened,fs,closed,flock=os.open,os.fstat,os.close,n.fcntl.flock
    monkeypatch.setattr(os,'open',lambda path,flags,*a:888 if str(path)==snap['sg_binding']['node'] else opened(path,flags,*a))
    ids=snap['sg_binding']['node_identity']
    monkeypatch.setattr(os,'fstat',lambda fd:SimpleNamespace(st_mode=stat.S_IFCHR,st_dev=ids[0],st_ino=ids[1],st_rdev=ids[2]) if fd==888 else fs(fd))
    def close(fd):
        if fd!=888:return closed(fd)
        state.closed+=1
        if close_fault:raise close_fault
    monkeypatch.setattr(os,'close',close)
    monkeypatch.setattr(n.fcntl,'flock',lambda fd,flags:None if fd==888 else flock(fd,flags))
    def ioctl(fd,num,h):
        assert fd==888 and num==0x2285
        cdb=C.string_at(h.cmd,h.cmd_len);state.calls.append(cdb)
        op=0x12 if len(cdb)==6 else int.from_bytes(cdb[:2],'big');data=bytearray(h.data_len)
        if op==0x12:data[8:16]=b'WL82    ';data[16:32]=b'UBOOT1.00       '
        elif op==0xfd05:
            offset=int.from_bytes(cdb[2:6],'big');data[:]=target[offset:offset+256] if target is not None else bytes([offset//256%256])*256
        elif op!=0xfb06:
            data[:2]=cdb[:2]
            if op==0xfc14:data[2:6]=(256).to_bytes(4,'big')
            if op==0xfc0a:data[2]=3;data[4:8]=(0x856014).to_bytes(4,'little')
        if fault:fault(h,data,op,state)
        if op!=0xfb06:C.memmove(h.data,bytes(data),len(data))
    monkeypatch.setattr(n.fcntl,'ioctl',ioctl);return state


def test_exact_new_inventory(prepared):
    p,_,_,_=prepared
    assert len(p.operations)==8757
    assert sum(op.label=='upload' for op in p.operations)==47
    assert {op.cdb[:2] for op in p.operations if len(op.cdb)==16}=={b'\xfb\x06',b'\xfb\x08',b'\xfc\x14',b'\xfc\x0a',b'\xfd\x05'}
    for label in ('dumpA.bin','dumpB.bin'):
        assert [int.from_bytes(op.cdb[2:6],'big') for op in p.operations if op.label==label]==list(range(0,1048576,256))


@pytest.mark.parametrize('field',['campaign','campaign_sha256','snapshot','evidence','policies','operations','provenance','connection_witness','native'])
def test_copied_authority_rejected(prepared,monkeypatch,field):
    p,*_=prepared;clone=replace(p,**{field:getattr(p,field)})
    monkeypatch.setattr(p.bridge,'discover_sg',lambda _:pytest.fail('discovered'))
    for call in (lambda:n.require_prepared(clone),lambda:n.FixedSG(clone,lambda *a,**k:None),lambda:n.run_campaign(clone)):
        with pytest.raises(ValueError):call()


@pytest.mark.parametrize('field',['adapter_sha256','returned_admission_sha256','connection_witness_sha256','loader_path','profile_path','profile_source_path','kind','active_session_state','receipt_path','schema'])
def test_factory_exact_envelope(prepared,field):
    p,cp,c,_=prepared;c[field]=False if field=='schema' else 'bad';save(cp,c)
    with pytest.raises((ValueError,OSError)):n.prepare_campaign(cp)


@pytest.mark.parametrize('fault',['stale','future','before_terminal','usb','sg','original_hash','admission_hash','extra','nonfinite'])
def test_separate_witness_no_snapshot_refresh(prepared,fault):
    p,cp,c,proof=prepared;wp=Path(c['connection_witness_path']);w=json.loads(wp.read_bytes())
    if fault=='stale':w['observed_at']-=121
    elif fault=='future':w['observed_at']=time.time()+1
    elif fault=='before_terminal':w['observed_at']=proof.terminal_at-1
    elif fault=='usb':w['usb_binding']['devnum']='27'
    elif fault=='sg':w['sg_binding']['node_identity'][0]+=1
    elif fault=='original_hash':w['original_rom_snapshot_sha256']='0'*64
    elif fault=='admission_hash':w['returned_admission_sha256']='0'*64
    elif fault=='extra':w['arbitrary']=1
    else:w['observed_at']=float('nan')
    wp.write_text(json.dumps(w));c['connection_witness_sha256']=n.digest(wp.read_bytes());save(cp,c)
    with pytest.raises(ValueError):n.prepare_campaign(cp)


@pytest.mark.parametrize('field,value',[('status',1),('masked',1),('msg',1),('host',1),('driver',1),('resid',1),('resid',-1),('info',1),('sense_len',1),('sense_len',33)])
def test_every_completion_failure_logged_and_no_retry(prepared,monkeypatch,field,value):
    p,*_=prepared;events=[];state=sg_mock(p,monkeypatch,fault=lambda h,*_:setattr(h,field,value))
    t=n.FixedSG(p,lambda event,**fields:events.append(dict(event=event,**fields)))
    with pytest.raises(OSError):t.exchange_next()
    assert events[-1]['event']=='sg_completion' and events[-1][field]==value
    with pytest.raises(ValueError):t.exchange_next()
    assert len(state.calls)==1 and state.closed==1 and t.next==1


@pytest.mark.parametrize('when,count',[(3,0),(4,1)])
def test_pre_post_binding_no_retry(prepared,monkeypatch,when,count):
    p,*_=prepared
    def fault(s):
        if s.discoveries>=when:raise ValueError('reconnect')
    state=sg_mock(p,monkeypatch,binding_fault=fault);t=n.FixedSG(p,lambda *a,**k:None)
    with pytest.raises(ValueError):t.exchange_next()
    assert len(state.calls)==count and state.closed==1


@pytest.mark.parametrize('change',['source','proof','absence','admission','profile'])
def test_drift_after_durable_intent_blocks_ioctl(prepared,monkeypatch,change):
    p,_,c,proof=prepared;state=sg_mock(p,monkeypatch)
    def log(event,**fields):
        if change=='absence':proof.absent[0].symlink_to('/missing')
        else:
            path={'source':n.__file__,'proof':str(Path(n.__file__).with_name('fm1_stopped_choice_recovery_evidence.py')),
                  'admission':c['returned_admission_path'],'profile':c['profile_path']}[change]
            with open(path,'ab') as fp:fp.write(b' ')
    t=n.FixedSG(p,log)
    with pytest.raises(ValueError):t.exchange_next()
    assert not state.calls and state.closed==1


@pytest.mark.parametrize('artifact',['destination','marker'])
def test_lexists_dangling_attempt_blocks_factory(prepared,artifact):
    p,cp,c,_=prepared;path=Path(c['receipt_path']) if artifact=='destination' else n.marker_path(p.parent,c)
    path.symlink_to('/missing')
    with pytest.raises(ValueError):n.prepare_campaign(cp)


def freeze(path,expected=None,limit=2*1048576):
    data=n.read_file(path,limit)
    if expected is not None:assert n.digest(data)==expected
    return data


def test_complete_model_worker_and_completed_evidence_only(prepared,monkeypatch):
    p,cp,c,_=prepared;target=b''.join(bytes([i%256])*256 for i in range(4096));monkeypatch.setattr(n,'TARGET_SHA',n.digest(target))
    state=sg_mock(p,monkeypatch,target=target);result=n.run_campaign(p)
    receipt=Path(c['receipt_path']);assert len(state.calls)==8757 and state.closed==1
    assert (receipt/'dumpA.bin').read_bytes()==target==(receipt/'dumpB.bin').read_bytes()
    assert not result['physical_recovery_verified'] and result['flash_readback_only']
    proof=n.validate_completed_backup(cp,campaign_sha256=p.campaign_sha256,manifest_sha256=n.digest((receipt/'manifest.json').read_bytes()),commands_sha256=n.digest((receipt/'commands.jsonl').read_bytes()),freeze=freeze)
    assert proof['dumps']==(target,target) and proof['policy_inputs']=={}
    assert proof['_absent_paths']==p.provenance.absent
    with pytest.raises(ValueError):n.prepare_campaign(cp)


@pytest.mark.parametrize('failure',['first','partial','wrong_target','close','manifest'])
def test_failure_no_manifest_no_retry_keeps_marker(prepared,monkeypatch,failure):
    p,_,c,_=prepared;target=b''.join(bytes([i%256])*256 for i in range(4096));monkeypatch.setattr(n,'TARGET_SHA',n.digest(target))
    def fault(h,data,op,state):
        if failure=='first' or failure=='partial' and len(state.calls)==100:raise TimeoutError('ambiguous')
        if failure=='wrong_target' and op==0xfd05:data[0]^=1
    state=sg_mock(p,monkeypatch,fault=fault,target=target,close_fault=OSError('close') if failure=='close' else None)
    original=p.bridge.private_file
    if failure=='manifest':
        def pf(path,*a,**k):
            if Path(path).name=='manifest.json':raise OSError('publication')
            return original(path,*a,**k)
        monkeypatch.setattr(p.bridge,'private_file',pf)
    with pytest.raises((OSError,ValueError)):n.run_campaign(p)
    assert not (Path(c['receipt_path'])/'manifest.json').exists()
    assert n.marker_path(p.parent,c).read_bytes()==p.campaign_sha256.encode()
    before=len(state.calls)
    with pytest.raises(ValueError):n.prepare_campaign(Path(p.evidence[0][0]))
    assert len(state.calls)==before


def test_actual_private_factory_dual_target_read_and_completed_helper(actual_tree,monkeypatch):
    from test_stopped_choice_recovery_actual import test_actual_physical_read_files_admit_without_transport
    m,stage=actual_tree
    # Exact private imports reject ambient modules; isolate the modeled fixture's
    # existing first-party module cache before the genuine factory.
    for name in rehearsal.SOURCES:
        monkeypatch.delitem(sys.modules,Path(name).stem,raising=False)
    test_actual_physical_read_files_admit_without_transport(actual_tree,monkeypatch)
    source=stage/'tools/fm1_stopped_choice_backup.py';shutil.copyfile(n.__file__,source)
    module=n.load_source(source,n.digest(source.read_bytes()),'_actual_stopped_choice_backup')
    admission=stage/'diagnostic-stage-resume-v1/recovery-evidence.json';a=json.loads(admission.read_bytes())
    proof_module=module.load_source(stage/'tools/fm1_stopped_choice_recovery_evidence.py',module.PROOF_SOURCE_SHA,'_actual_backup_proof')
    proof=proof_module.validate_returned_state(admission)
    snapshot=json.loads(proof.snapshot);run=stage/'stopped-choice-backup-model';run.mkdir(mode=0o700)
    witness=dict(schema=1,kind='fm1-passive-stopped-choice-backup-connection',observed_at=time.time(),
        usb_binding=snapshot['usb_binding'],sg_binding=snapshot['sg_binding'],original_rom_snapshot_sha256=module.SNAPSHOT_SHA,
        returned_admission_sha256=module.digest(admission.read_bytes()),quiet_state=module.STATE)
    wp=run/'witness.json';wp.write_bytes(module.canonical(witness))
    inputs=json.loads(proof.original_inputs)
    c=dict(schema=1,kind=module.KIND,adapter_sha256=module.digest(source.read_bytes()),returned_admission_path=str(admission),
        returned_admission_sha256=module.digest(admission.read_bytes()),connection_witness_path=str(wp),connection_witness_sha256=module.digest(wp.read_bytes()),
        loader_path=inputs['loader_path'],profile_path=inputs['profile_path'],profile_source_path=str(stage/'tools/jieli/loader_config_profile.py'),
        active_session_state=module.STATE,receipt_path=str(stage.parent/'stopped-choice-backup-model-001'))
    cp=run/'campaign.json';cp.write_bytes(module.canonical(c));started=time.monotonic();p=module.prepare_campaign(cp);seconds=time.monotonic()-started
    target=(p.policies[0].directory/'target.bin').read_bytes();assert module.digest(target)==module.TARGET_SHA
    state=sg_mock(p,monkeypatch,target=target);result=module.run_campaign(p);receipt=Path(c['receipt_path'])
    checked=module.validate_completed_backup(cp,campaign_sha256=p.campaign_sha256,
        manifest_sha256=module.digest((receipt/'manifest.json').read_bytes()),commands_sha256=module.digest((receipt/'commands.jsonl').read_bytes()),freeze=freeze)
    assert checked['install_journal_sha256']==proof.install_journal_sha256 and checked['dumps']==(target,target)
    assert len(state.calls)==8757 and not result['physical_recovery_verified']
    out=Path(os.environ['LUNAR_ADMISSION_EVIDENCE'])
    (out/'actual-backup-model.json').write_bytes(module.canonical(dict(factory_seconds=seconds,commands=len(state.calls),
        adapter_sha256=module.digest(source.read_bytes()),proof_sha256=module.PROOF_SOURCE_SHA,campaign_sha256=p.campaign_sha256,
        manifest_sha256=module.digest((receipt/'manifest.json').read_bytes()),commands_sha256=module.digest((receipt/'commands.jsonl').read_bytes()),
        target_sha256=module.TARGET_SHA,original_snapshot_refreshed=False,actual_file_factory=True,sg_syscalls_mocked=True,hardware_access=False)))


@pytest.fixture
def read_receipt(prepared,monkeypatch):
    p,*_=prepared;target=b''.join(bytes([i%256])*256 for i in range(4096));monkeypatch.setattr(n,'TARGET_SHA',n.digest(target))
    now=time.time()-1;rows=[dict(time=now,**n.first_event(p))]
    for i,op in enumerate(p.operations):
        rows.append(dict(time=now,event='sg_submit_intent',index=i,phase=op.phase,label=op.label,cdb=op.cdb.hex(),
            payload_sha256=n.digest(op.payload) if op.payload else None,out_len=len(op.payload),in_len=op.read_size,retry=False))
        if op.label in ('dumpA.bin','dumpB.bin'):
            address=int.from_bytes(op.cdb[2:6],'big');response=n.digest(target[address:address+256])
        else:response='a'*64 if op.read_size else None
        rows.append(dict(time=now,event='sg_completion',index=i,status=0,masked=0,msg=0,host=0,driver=0,resid=0,
            info=0,sense_len=0,sense_hex='',response_sha256=response,retry=False))
    rows.append(dict(time=now,event='stopped_choice_backup_completed',identical=True,bytes_per_dump=1048576,
        target_sha256=n.TARGET_SHA,physical_recovery_verified=False,retry=False))
    return p,target,rows


@pytest.mark.parametrize('fault',['missing','duplicate','phase','opcode','payload','length','retry','status','sense',
    'page_hash','index','terminal','first','future','duration','out_of_order','different_dump','short_dump'])
def test_completed_replay_rejects_corruption(read_receipt,fault):
    p,target,rows=read_receipt;other=target
    first_page=next(i for i,o in enumerate(p.operations) if o.label=='dumpA.bin')
    if fault=='missing':rows.pop(2)
    elif fault=='duplicate':rows.insert(2,dict(rows[2]))
    elif fault=='phase':rows[1]['phase']='loader'
    elif fault=='opcode':rows[1]['cdb']='fc12'+rows[1]['cdb'][4:]
    elif fault=='payload':rows[3]['payload_sha256']='0'*64
    elif fault=='length':rows[1]['in_len']+=1
    elif fault=='retry':rows[1]['retry']=True
    elif fault=='status':rows[2]['host']=1
    elif fault=='sense':rows[2]['sense_hex']='00'
    elif fault=='page_hash':rows[2+first_page*2]['response_sha256']='0'*64
    elif fault=='index':rows[2]['index']+=1
    elif fault=='terminal':rows[-1]['physical_recovery_verified']=True
    elif fault=='first':rows[0]['returned_admission_sha256']='0'*64
    elif fault=='future':rows[-1]['time']=time.time()+100
    elif fault=='duration':rows[0]['time']-=901
    elif fault=='out_of_order':rows[2]['time']-=1
    elif fault=='different_dump':other=target[:-1]+bytes([target[-1]^1])
    else:other=target[:-1]
    raw=b'\n'.join(n.canonical(row) for row in rows)
    with pytest.raises(ValueError):n.validate_read_receipt(raw,p,target,other)


@pytest.mark.parametrize('exception',[OSError('sticky close'),KeyboardInterrupt('sticky close')])
def test_close_base_exception_never_certifies(prepared,monkeypatch,exception):
    p,*_=prepared;state=sg_mock(p,monkeypatch,close_fault=exception);t=n.FixedSG(p,lambda *a,**k:None)
    with pytest.raises(type(exception)):t.close()
    with pytest.raises(type(exception)):t.close()
    assert state.closed==1 and t.failed


def test_closed_pin_fails_before_open(monkeypatch):
    monkeypatch.setattr(n,'PROOF_SOURCE_SHA',None)
    monkeypatch.setattr(n,'read_file',lambda *a:pytest.fail('opened evidence'))
    with pytest.raises(ValueError,match='Closed'):n.prepare_campaign(Path('/missing'))
