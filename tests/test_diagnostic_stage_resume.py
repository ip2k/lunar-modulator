"""MIT. Exact stopped-choice proof and modeled two-read transport; no hardware."""
import copy
import ctypes as C
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_diagnostic_stage_resume as p

RAW=bytes.fromhex('29a481cc4ec15deaeebef8a8290d47f481a9ebe3efc48a14dee6dd1cd0f8463b')
USB=dict(busnum='3',devnum='25',path='3-2',vid='4c4a',pid='8057')
NEW=dict(USB,devnum='26')


def wire():
    lines=[];seq=0
    def urb(direction,dev,size,data=b'',status=0,completed=None,returned=b''):
        nonlocal seq
        seq+=1;token=str(seq)
        for action,st,n,b in (('S',-115,size,data),('C',status,size if completed is None else completed,returned)):
            lines.append(f'{token} {seq} {action} {direction}:3:{dev:03}:1 {st} {n}'+(' = '+b.hex() if b else ''))
    def cbw(tag,cdb,length=0,dev=26,failed=0,response=b''):
        command=b'USBC'+tag.to_bytes(4,'little')+length.to_bytes(4,'little')+bytes([128 if length else 0,0,6])+cdb+bytes(16-len(cdb))
        urb('Bo',dev,31,command)
        if length:urb('Bi',dev,length,returned=response)
        urb('Bi',dev,13,returned=b'USBS'+tag.to_bytes(4,'little')+bytes(4)+bytes([failed]))
    reset=b'USBC'+bytes(4)+bytes.fromhex('10000000800010fc0c00000001ffffffffffffffffffff')
    urb('Bo',25,31,reset);urb('Bi',25,16,status=-108,completed=0)
    cbw(1,bytes.fromhex('120000002400'),36,response=bytes(32))
    cbw(2,bytes.fromhex('1e0000000100'),failed=1)
    cbw(3,bytes.fromhex('030000001200'),18,response=bytes.fromhex('700005000000000a00000000240000000000'))
    return ('\n'.join(lines)+'\n').encode('ascii')


def test_exact_paired_rejected_lock_is_evidence_only():
    result=p.verify_wire(wire(),USB,NEW)
    assert result['cbws']==4 and result['paired_records']==20
    assert result['kernel_compatible_rejected_lock'] is True
    assert result['process_origin_verified'] is result['reset_request_completed'] is False
    assert p.OPERATIONS[1][0]==bytes.fromhex('fd0701c033d80020ffffffffffffffff')
    assert all(c[0][0]!=0x1e for c in p.OPERATIONS)


@pytest.mark.parametrize('old,new',[
    ('1e0000000100','1e0000000000'),('1e0000000100','1e0000000200'),
    ('1e0000000100','1e0100000100'),('1e0000000100','fc1200000100'),
    ('700005000000000a00000000240000000000','700005000000000a00000000250000000000'),
    ('700005000000000a00000000240000000000','700000000000000a00000000240000000000'),
    ('55534253020000000000000001','55534253020000000000000000'),
    ('55534253020000000000000001','55534253090000000000000001'),
    ('55534253020000000000000001','55534253020000000100000001'),
    ('55534253030000000000000000','55534253030000000000000001'),
    ('Bi:3:025:1 -108 0','Bi:3:025:1 0 16'),
    ('Bo:3:026:1 0 31','Bo:3:026:1 -5 0'),
])
def test_historical_lock_geometry_status_sense_fail_closed(old,new):
    data=wire();assert old.encode() in data
    with pytest.raises(ValueError):p.verify_wire(data.replace(old.encode(),new.encode(),1),USB,NEW)


@pytest.mark.parametrize('fault',['missing','extra','wrong_endpoint','wrong_device','data_out','duplicate_lock'])
def test_wire_pairing_inventory_and_order(fault):
    lines=wire().decode().splitlines()
    if fault=='missing':lines.pop(1)
    elif fault=='extra':lines.append(lines[-1])
    elif fault=='wrong_endpoint':lines[1]=lines[1].replace(':1 ',':2 ')
    elif fault=='wrong_device':lines[8]=lines[8].replace('026','025')
    elif fault=='data_out':lines[9]+=' = 00'
    else:lines.extend(lines[10:14])
    with pytest.raises(ValueError):p.verify_wire(('\n'.join(lines)+'\n').encode(),USB,NEW)


@pytest.fixture(scope='session')
def actual_tree():
    path=os.environ.get('LUNAR_STAGE_RESUME_ACTUAL')
    if not path:
        if os.environ.get('LUNAR_REQUIRE_PRIVATE_FIXTURES')=='1':pytest.fail('Strict actual files required')
        pytest.skip('Private actual bench tree unavailable')
    source=Path(path);base=Path('/home/claude/fm1-diagnostic-boot-20261011')
    assert os.environ.get('LUNAR_STAGE_RESUME_DISPOSABLE')=='1' and not base.exists()
    shutil.copytree(source/'fm1-diagnostic-boot-20261011',base)
    stage=base/'continued-backup-v1/attempt-001/install-stage-v1';stage.parent.chmod(0o700);stage.chmod(0o700)
    fixed=Path('/home/claude/fm1-fixed-backups-20261011/stage');assert not fixed.exists();fixed.mkdir(parents=True)
    # The private pinned archive is installed only in a disposable no-device container.
    with tarfile.open(source/'fixed.tar.gz') as t:t.extractall(fixed)
    new=stage/'tools/fm1_diagnostic_stage_resume.py';shutil.copyfile(Path(p.__file__),new)
    spec=importlib.util.spec_from_file_location('actual_resume',new);m=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=m;spec.loader.exec_module(m)
    return m,stage


@pytest.fixture
def actual_prepared(actual_tree):
    m,stage=actual_tree;run=stage/'diagnostic-stage-resume-v1'
    if run.exists():shutil.rmtree(run)
    run.mkdir(mode=0o700)
    dest=stage.parent/'diagnostic-stage-resume-001';marker=dest.parent/('.diagnostic-stage-resume-'+m.BOOT_SHA+'.consumed')
    if dest.exists():shutil.rmtree(dest)
    marker.unlink(missing_ok=True)
    snap=json.loads((stage/'target-reset-stage-v1/rom-snapshot.json').read_bytes())
    witness=dict(schema=1,kind='fm1-passive-current-same-rom-after-stopped-choice',observed_at=time.time(),
        usb_binding=snap['usb_binding'],sg_binding=snap['sg_binding'],original_rom_snapshot_sha256=m.SNAPSHOT_SHA,
        choice_stop_sha256=m.CHOICE_PINS['chooser-stopped-ambiguous.json'],quiet_state='no-later-device-commands-no-loader-upload')
    wp=run/'witness.json';wp.write_bytes(m.canonical(witness))
    c=dict(schema=1,kind='fm1-actual-stopped-choice-stage-read',adapter_sha256=m.digest(Path(m.__file__).read_bytes()),
        choice_path=str(stage/'diagnostic-probe-choice-v1'),witness_path=str(wp),witness_sha256=m.digest(wp.read_bytes()),receipt_path=str(dest))
    cp=run/'campaign.json';cp.write_bytes(m.canonical(c))
    prepared=m.prepare_campaign(cp)
    yield m,stage,prepared,cp
    if dest.exists():shutil.rmtree(dest)
    marker.unlink(missing_ok=True)


def model(m,prepared,*,fault=None,binding_fault=None,close_error=None):
    snap=json.loads(prepared.snapshot)
    state=SimpleNamespace(calls=[],closed=0)
    class Transport:
        def binding(self):
            value=dict(usb_binding=copy.deepcopy(snap['usb_binding']),sg_binding=copy.deepcopy(snap['sg_binding']),
                fd_identity=snap['sg_binding']['node_identity'],fd_mode=stat.S_IFCHR)
            if binding_fault:binding_fault(state,value)
            return value
        def exchange(self,cdb,payload,in_len):
            state.calls.append((cdb,payload,in_len))
            data=b'\0'*8+b'WL82    '+b'UBOOT1.00       '+b'1.00' if in_len==36 else RAW
            fields=dict(data=data)
            if fault:fault(state,fields)
            return m.helper.Completion(**fields) if hasattr(m,'helper') else prepared.helper.Completion(**fields)
        def close(self):
            state.closed+=1
            if close_error:raise close_error
    return state,Transport()


def test_actual_private_factory_and_two_reads(actual_prepared):
    m,stage,prepared,cp=actual_prepared
    assert prepared.proof.historical_admission_time==1791775862.0725162
    snapshot=stage/'target-reset-stage-v1/rom-snapshot.json';before=snapshot.read_bytes()
    state,transport=model(m,prepared)
    result=m.run_campaign(prepared,lambda _:transport)
    assert state.calls==list(m.OPERATIONS) and state.closed==1
    assert snapshot.read_bytes()==before and result['original_snapshot_refreshed'] is False
    assert result['classification']=='conditional-diagnostic-execution-evidence'
    assert result['reset_request_completed'] is False
    with pytest.raises((ValueError,FileExistsError)):m.run_campaign(prepared,lambda _:pytest.fail('retry'))


@pytest.mark.parametrize('field',['campaign','campaign_sha256','snapshot','proof','witness','evidence','helper','native','bridge','header_type'])
def test_copied_prepared_and_proof_have_no_authority(actual_prepared,field):
    m,_,prepared,_=actual_prepared
    copied=replace(prepared,**{field:None})
    with pytest.raises(ValueError):m.run_campaign(copied,lambda _:pytest.fail('open'))
    with pytest.raises(ValueError):replace(prepared.proof).check()


@pytest.mark.parametrize('fault',['stale','future','nan','usb','node','snapshot','stop','extra'])
def test_current_witness_is_separate_exact_fresh_binding(actual_prepared,fault):
    m,_,prepared,cp=actual_prepared;c=json.loads(cp.read_bytes());wp=Path(c['witness_path']);w=json.loads(wp.read_bytes())
    if fault=='stale':w['observed_at']=time.time()-121
    elif fault=='future':w['observed_at']=time.time()+3600
    elif fault=='nan':w['observed_at']=float('nan')
    elif fault=='usb':w['usb_binding']['devnum']='27'
    elif fault=='node':w['sg_binding']['node_identity'][1]+=1
    elif fault=='snapshot':w['original_rom_snapshot_sha256']='0'*64
    elif fault=='stop':w['choice_stop_sha256']='0'*64
    else:w['extra']=1
    old=wp.read_bytes();oldc=cp.read_bytes()
    try:
        wp.write_bytes(json.dumps(w).encode());c['witness_sha256']=m.digest(wp.read_bytes());cp.write_bytes(m.canonical(c))
        with pytest.raises(ValueError):m.prepare_campaign(cp)
    finally:wp.write_bytes(old);cp.write_bytes(oldc)


@pytest.mark.parametrize('field,value',[('status',1),('masked',1),('msg',1),('host',1),('driver',1),('resid',1),('resid',-1),('info',1),('sense_len',1),('sense',b'\0')])
def test_failed_structured_completion_is_logged_no_second_read(actual_prepared,field,value):
    m,_,prepared,_=actual_prepared
    state,transport=model(m,prepared,fault=lambda _,f:f.update({field:value}))
    with pytest.raises(OSError):m.run_campaign(prepared,lambda _:transport)
    assert state.calls==[m.OPERATIONS[0]] and state.closed==1
    dest=Path(json.loads(prepared.campaign)['receipt_path'])
    events=[json.loads(line) for line in (dest/'commands.jsonl').read_bytes().splitlines()]
    assert events[2]['event']=='sg_completion' and events[2][field if field!='sense' else 'sense_hex']==(value if field!='sense' else '00')
    assert events[-1]['event']=='stage_probe_stopped_ambiguous' and not (dest/'result.json').exists()


@pytest.mark.parametrize('error',[OSError('close'),KeyboardInterrupt('close')])
def test_close_failure_invalidates_publication(actual_prepared,error):
    m,_,prepared,_=actual_prepared;state,transport=model(m,prepared,close_error=error)
    with pytest.raises(type(error)):m.run_campaign(prepared,lambda _:transport)
    assert state.calls==list(m.OPERATIONS) and state.closed==1
    assert not (Path(json.loads(prepared.campaign)['receipt_path'])/'result.json').exists()


@pytest.mark.parametrize('when',['before','after_intent','after_inquiry'])
def test_source_or_witness_drift_before_mutation_stops_without_retry(actual_prepared,when):
    m,_,prepared,_=actual_prepared;path=Path(json.loads(prepared.campaign)['witness_path']);old=path.read_bytes()
    state,transport=model(m,prepared)
    real_fsync=m.os.fsync
    def synced(fd):
        real_fsync(fd)
        if when=='after_intent' and os.readlink('/proc/self/fd/'+str(fd)).endswith('commands.jsonl'):
            content=Path(os.readlink('/proc/self/fd/'+str(fd))).read_text()
            if 'sg_submit_intent' in content:path.write_bytes(old+b' ')
    try:
        if when=='before':path.write_bytes(old+b' ')
        if when=='after_inquiry':
            original=transport.exchange
            def exchange(*a):result=original(*a);path.write_bytes(old+b' ');return result
            transport.exchange=exchange
        if when=='after_intent':
            from unittest.mock import patch
            with patch.object(m.os,'fsync',synced),pytest.raises(ValueError):m.run_campaign(prepared,lambda _:transport)
        else:
            with pytest.raises(ValueError):m.run_campaign(prepared,lambda _:transport)
        assert len(state.calls)==(1 if when=='after_inquiry' else 0)
    finally:path.write_bytes(old)


def native_model(prepared,monkeypatch,*,fault=None,binding_fault=None,close_error=None):
    n=prepared.native;monkeypatch.setattr(n.sys,'platform','linux')
    snap=json.loads(prepared.snapshot);mapping=snap['sg_binding'];state=SimpleNamespace(calls=[],closed=[],opens=[],bindings=0)
    real_open,real_close,real_fstat,real_flock=n.os.open,n.os.close,n.os.fstat,n.fcntl.flock
    def discover(usb):
        assert usb==snap['usb_binding'];state.bindings+=1;value=copy.deepcopy(mapping)
        if binding_fault:binding_fault(state,value)
        return value
    prepared.bridge.discover_sg=discover
    monkeypatch.setattr(n.os,'open',lambda path,flags,*a: (state.opens.append(flags) or 888) if str(path)==mapping['node'] else real_open(path,flags,*a))
    monkeypatch.setattr(n.os,'fstat',lambda fd:SimpleNamespace(st_mode=stat.S_IFCHR,st_dev=mapping['node_identity'][0],st_ino=mapping['node_identity'][1],st_rdev=mapping['node_identity'][2]) if fd==888 else real_fstat(fd))
    def closed(fd):
        if fd!=888:return real_close(fd)
        state.closed.append(fd)
        if close_error:raise close_error
    monkeypatch.setattr(n.os,'close',closed)
    monkeypatch.setattr(n.fcntl,'flock',lambda fd,flags:None if fd==888 else real_flock(fd,flags))
    def ioctl(fd,number,h):
        assert fd==888 and number==0x2285 and h.interface_id==ord('S') and h.direction==-3 and h.timeout==3000
        cdb=C.string_at(h.cmd,h.cmd_len);assert (cdb,b'',h.data_len)==n.OPERATIONS[len(state.calls)]
        state.calls.append((cdb,b'',h.data_len))
        data=bytearray(b'\0'*8+b'WL82    '+b'UBOOT1.00       '+b'1.00') if h.data_len==36 else bytearray(RAW)
        if fault:fault(h,data,state)
        C.memmove(h.data,bytes(data),len(data))
    monkeypatch.setattr(n.fcntl,'ioctl',ioctl)
    return state


def test_actual_native_composition_uses_one_fd_and_two_exact_reads(actual_prepared,monkeypatch):
    m,_,prepared,_=actual_prepared;state=native_model(prepared,monkeypatch)
    result=m.run_campaign(prepared)
    assert state.calls==list(p.OPERATIONS) and state.closed==[888] and len(state.opens)==1
    assert result['raw_sha256']==p.digest(RAW) and result['original_snapshot_refreshed'] is False


@pytest.mark.parametrize('field,value',[('status',1),('masked',1),('host',1),('driver',1),('resid',1),('resid',-1),('info',1),('sense_len',1)])
def test_native_failed_status_logged_and_stops_before_fd07(actual_prepared,monkeypatch,field,value):
    m,_,prepared,_=actual_prepared
    state=native_model(prepared,monkeypatch,fault=lambda h,_,s:setattr(h,field,value))
    with pytest.raises(OSError):m.run_campaign(prepared)
    dest=Path(json.loads(prepared.campaign)['receipt_path'])
    events=[json.loads(v) for v in (dest/'commands.jsonl').read_bytes().splitlines()]
    assert events[2]['event']=='sg_completion' and events[2][field]==value
    assert state.calls==[p.OPERATIONS[0]] and state.closed==[888] and not (dest/'result.json').exists()


@pytest.mark.parametrize('when',['initial','after_ioctl'])
def test_native_changed_mapping_before_or_after_ioctl_never_retries(actual_prepared,monkeypatch,when):
    m,_,prepared,_=actual_prepared
    def drift(state,value):
        if when=='initial' or state.calls:value['node_identity'][1]+=1
    state=native_model(prepared,monkeypatch,binding_fault=drift)
    with pytest.raises(ValueError):m.run_campaign(prepared)
    assert len(state.calls)==(0 if when=='initial' else 1)


def test_closed_wrapper_and_preparer_fail_before_file_or_device_access(monkeypatch):
    location=os.environ.get('LUNAR_STAGE_RESUME_TEMPLATE')
    if not location:pytest.skip('Private closed templates unavailable')
    for name in ('execute-once.py','prepare-file-only.py'):
        path=Path(location)/name;spec=importlib.util.spec_from_file_location('closed_'+name.replace('.','_'),path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with monkeypatch.context() as patcher:
            patcher.setattr(module.os,'open',lambda *a,**k:pytest.fail('closed file/device access'))
            with pytest.raises(ValueError,match='Closed'):module.main()


def test_actual_file_only_preparer_and_bound_wrapper_lifecycle(actual_prepared,monkeypatch):
    m,stage,prepared,_=actual_prepared;location=os.environ.get('LUNAR_STAGE_RESUME_TEMPLATE')
    if not location:pytest.fail('Private closed template fixture required')
    run=stage/'diagnostic-stage-resume-v1';shutil.rmtree(run);run.mkdir(mode=0o700)
    for name in ('execute-once.py','prepare-file-only.py'):shutil.copyfile(Path(location)/name,run/name)
    def module(path,name):
        spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
    preparer=module(run/'prepare-file-only.py','modeled_preparer')
    monkeypatch.setattr(preparer,'AUTHORIZATION','reviewed-pure-file-passive-preparation');monkeypatch.setattr(preparer.sys,'platform','linux')
    snap=json.loads(prepared.snapshot)
    original=m.load_source
    def source(path,pin,name):
        mod=original(path,pin,name)
        if str(path).endswith('fm1_fixed_loader_backup.py'):mod.discover_sg=lambda _:copy.deepcopy(snap['sg_binding'])
        return mod
    # The preparer creates an isolated exact source instance. Substitute only its
    # passive sysfs discovery in the disposable model, never its provenance checks.
    real_exec=__builtins__['exec'] if isinstance(__builtins__,dict) else __builtins__.exec
    import builtins
    def executed(code,g,l=None):
        real_exec(code,g,l)
        if g.get('__name__')=='_fm1_resume_preparer':g['load_source']=source
    with monkeypatch.context() as patcher:
        patcher.setattr(builtins,'exec',executed)
        assert preparer.main()==0
    summary=json.loads((run/'prepared-files.json').read_bytes())
    assert summary['hardware_access'] is False and summary['original_snapshot_refreshed'] is False
    wrapper=module(run/'execute-once-bound.py','modeled_wrapper')
    monkeypatch.setattr(wrapper.os,'geteuid',lambda:0);monkeypatch.setattr(wrapper.sys,'platform','linux')
    capture=SimpleNamespace(pid=123,returncode=None)
    capture.wait=lambda timeout:setattr(capture,'returncode',-15)
    monkeypatch.setattr(wrapper.subprocess,'Popen',lambda *a,**k:capture)
    monkeypatch.setattr(wrapper,'capture_alive',lambda _:dict(timeout_pid=123,cat_pid=124,process_group=123,open_capture_fd=True))
    monkeypatch.setattr(wrapper.os,'killpg',lambda pid,sig:None)
    calls=[]
    def child(argv,**kw):
        assert argv[:5]==['/usr/bin/python3','-B','-E','-s','-S'] and argv[-2]=='--campaign'
        calls.append(argv);return SimpleNamespace(returncode=1)
    monkeypatch.setattr(wrapper.subprocess,'run',child)
    assert wrapper.main()==1 and len(calls)==1
    owned=json.loads((run/'owned-capture.json').read_bytes())
    assert owned['exit_status']==1 and owned['retry'] is False and len(owned['wrapper_files_sha256'])==11
    with pytest.raises(ValueError):wrapper.main()
    assert len(calls)==1
