"""MIT. Every SG/sysfs/FD syscall is modeled; no test opens physical hardware."""
import copy
import ctypes as C
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_diagnostic_stage_sg as n
import fm1_diagnostic_stage_probe as p
import fm1_uboot_read as reader
import fm1_sdk_install as install
import fm1_fixed_target_reset as target_reset
from test_diagnostic_stage_probe import prepared as probe_prepared, RAW, boot_events, snapshot
from test_sdk_rehearsal import actual, SGModel
from test_sdk_install import envelope
from test_fixed_target_reset import target_config


@pytest.fixture
def prepared(probe_prepared):
    bridge=SimpleNamespace(discover_sg=lambda _:pytest.fail('unmocked discovery'))
    obj=n.Prepared(b'{}','modeled-native',probe_prepared,p,bridge,reader.SGHeader,probe_prepared.evidence)
    n._AUTHORIZED.add(obj)
    return obj


def mock_sg(prepared,monkeypatch,*,fault=None,binding_fault=None,close_error=None):
    monkeypatch.setattr(n.sys,'platform','linux')
    mapping=json.loads(prepared.probe.snapshot)['sg_binding']
    usb=json.loads(prepared.probe.snapshot)['usb_binding']
    state=SimpleNamespace(calls=[],closed=[],discoveries=0,opens=[],locks=[],fstats=0)
    real_open,real_close,real_fstat,real_flock=n.os.open,n.os.close,n.os.fstat,n.fcntl.flock
    def discover(actual):
        assert actual==usb;state.discoveries+=1
        result=copy.deepcopy(mapping)
        if binding_fault:binding_fault(state,result)
        return result
    prepared.bridge.discover_sg=discover
    def opened(path,flags,*a):
        if str(path)==mapping['node']:
            state.opens.append(flags);return 888
        return real_open(path,flags,*a)
    monkeypatch.setattr(n.os,'open',opened)
    def fstat(fd):
        if fd!=888:return real_fstat(fd)
        state.fstats+=1
        return SimpleNamespace(st_mode=stat.S_IFCHR,st_dev=mapping['node_identity'][0],
            st_ino=mapping['node_identity'][1],st_rdev=mapping['node_identity'][2])
    monkeypatch.setattr(n.os,'fstat',fstat)
    def close(fd):
        if fd!=888:return real_close(fd)
        state.closed.append(fd)
        if close_error:raise close_error
    monkeypatch.setattr(n.os,'close',close)
    def flock(fd,flags):
        if fd!=888:return real_flock(fd,flags)
        state.locks.append(flags)
    monkeypatch.setattr(n.fcntl,'flock',flock)
    def ioctl(fd,number,h):
        assert fd==888 and number==0x2285 and h.interface_id==ord('S')
        assert h.direction==-3 and h.sense_max==32 and h.timeout==3000
        assert h.flags==h.iovec_count==h.pack_id==0
        cdb=C.string_at(h.cmd,h.cmd_len)
        assert (cdb,b'',h.data_len)==n.OPERATIONS[len(state.calls)]
        state.calls.append((cdb,b'',h.data_len))
        data=bytearray(b'\0'*8+b'WL82    '+b'UBOOT1.00       '+b'1.00') if cdb==p.INQUIRY else bytearray(RAW)
        if fault:fault(h,data,state)
        C.memmove(h.data,bytes(data),len(data))
    monkeypatch.setattr(n.fcntl,'ioctl',ioctl)
    return state


def open_transport(prepared):
    # Unit models explicitly authorize the private runner-only opener. Production
    # ordinary API callers can only obtain it after the durable probe intent.
    permit=n._OpenPermit(prepared);n._OPENING.add(permit)
    return n.NativeSG(prepared,permit)


def test_exact_native_campaign_two_requests_receipt_and_one_handle(prepared,monkeypatch):
    state=mock_sg(prepared,monkeypatch)
    result=n.run_campaign(prepared)
    assert state.calls==list(n.OPERATIONS)==list(p.OPERATIONS)
    assert state.closed==[888] and state.opens==[os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK]
    assert state.locks==[n.fcntl.LOCK_EX|n.fcntl.LOCK_NB]
    assert result['classification']=='conditional-diagnostic-execution-evidence'
    with pytest.raises(FileExistsError):n.run_campaign(prepared)
    assert state.calls==list(n.OPERATIONS)


def test_direct_open_without_runner_permit_never_discovers(prepared):
    with pytest.raises(ValueError):n.NativeSG(prepared)


@pytest.mark.parametrize('field',['campaign','campaign_sha256','probe','module','bridge','header_type','evidence'])
def test_copied_native_authority_never_opens(prepared,field):
    obj=replace(prepared,**{field:None})
    with pytest.raises(ValueError):n.run_campaign(obj)
    with pytest.raises(ValueError):open_transport(obj)


@pytest.mark.parametrize('index',range(16))
def test_changed_fd07_byte_never_reaches_ioctl(prepared,monkeypatch,index):
    state=mock_sg(prepared,monkeypatch);sg=open_transport(prepared)
    sg.exchange(p.INQUIRY,in_len=36)
    wrong=bytearray(p.READ_STAGE);wrong[index]^=1
    with pytest.raises(ValueError):sg.exchange(bytes(wrong),in_len=32)
    assert state.calls==[n.OPERATIONS[0]] and state.closed==[888]
    with pytest.raises(ValueError):sg.exchange(p.READ_STAGE,in_len=32)


@pytest.mark.parametrize('cdb,out,size',[(p.READ_STAGE,b'',32),(p.INQUIRY,b'x',36),
    (p.INQUIRY,b'',32),(p.INQUIRY,b'',True),(bytearray(p.INQUIRY),b'',36),
    (b'\xfc\x12'+b'\xff'*14,b'',16),(b'\xfb\x06'+b'\xff'*14,b'x'*512,0)])
def test_wrong_order_payload_length_opcode_type_never_ioctl(prepared,monkeypatch,cdb,out,size):
    state=mock_sg(prepared,monkeypatch);sg=open_transport(prepared)
    with pytest.raises(ValueError):sg.exchange(cdb,out,size)
    assert state.calls==[] and state.closed==[888]


@pytest.mark.parametrize('field,value',[('status',1),('masked',1),('msg',1),('host',1),
    ('driver',1),('resid',1),('resid',-1),('info',1),('sense_len',1),('sense_len',33)])
@pytest.mark.parametrize('which',[1,2])
def test_every_failed_sg_completion_closes_no_retry(prepared,monkeypatch,field,value,which):
    def fault(h,data,state):
        if len(state.calls)==which:setattr(h,field,value)
    state=mock_sg(prepared,monkeypatch,fault=fault)
    with pytest.raises(OSError):n.run_campaign(prepared)
    assert len(state.calls)==which and state.closed==[888]
    receipt=Path(json.loads(prepared.probe.campaign)['receipt_path'])
    assert not (receipt/'result.json').exists()
    events=[json.loads(line) for line in (receipt/'commands.jsonl').read_text().splitlines()]
    replies=[e for e in events if e['event']=='sg_completion']
    assert len(replies)==which and replies[-1][field]==value
    assert events[-1]['event']=='stage_probe_stopped_ambiguous'


@pytest.mark.parametrize('fault',['ioctl','inquiry','post_read'])
def test_syscall_semantic_or_post_binding_ambiguity_no_retry(prepared,monkeypatch,fault):
    def inject(h,data,state):
        if fault=='ioctl':raise TimeoutError('modeled lost reply')
        if fault=='inquiry':data[8:16]=b'OTHER   '
        if fault=='post_read' and len(state.calls)==2:
            prepared.probe.evidence[0][0].write_bytes(b'changed')
    state=mock_sg(prepared,monkeypatch,fault=inject)
    with pytest.raises((ValueError,TimeoutError)):n.run_campaign(prepared)
    assert len(state.calls)==(2 if fault=='post_read' else 1) and state.closed==[888]


@pytest.mark.parametrize('when',[1,2,3,4,5,6])
def test_constructor_and_direct_pre_post_mapping_checks(prepared,monkeypatch,when):
    def changed(state,mapping):
        if state.discoveries==when:mapping['usb_identity'][1]+=1
    state=mock_sg(prepared,monkeypatch,binding_fault=changed)
    with pytest.raises(ValueError):
        sg=open_transport(prepared)
        sg.exchange(p.INQUIRY,in_len=36);sg.exchange(p.READ_STAGE,in_len=32)
    assert len(state.calls)=={1:0,2:0,3:0,4:1,5:1,6:2}[when]
    assert state.closed==([] if when==1 else [888])


@pytest.mark.parametrize('fault',['fstat_mode','fstat_identity','flock','open','stale','source'])
def test_fd_lock_window_source_fail_closed(prepared,monkeypatch,fault):
    state=mock_sg(prepared,monkeypatch)
    if fault.startswith('fstat'):
        original=n.os.fstat
        def changed(fd):
            value=original(fd)
            if fd==888:setattr(value,'st_mode' if fault=='fstat_mode' else 'st_ino',stat.S_IFREG if fault=='fstat_mode' else 99)
            return value
        monkeypatch.setattr(n.os,'fstat',changed)
    if fault=='flock':
        original=n.fcntl.flock
        def lock(fd,flags):
            if fd==888:raise BlockingIOError('competing handle')
            return original(fd,flags)
        monkeypatch.setattr(n.fcntl,'flock',lock)
    if fault=='open':
        original=n.os.open
        def opened(path,flags,*a):
            if str(path)==json.loads(prepared.probe.snapshot)['sg_binding']['node']:raise PermissionError('no access')
            return original(path,flags,*a)
        monkeypatch.setattr(n.os,'open',opened)
    with pytest.raises((ValueError,OSError)):
        sg=open_transport(prepared)
        if fault=='stale':sg.started-=11
        if fault=='source':prepared.evidence[0][0].write_bytes(b'changed')
        sg.exchange(p.INQUIRY,in_len=36)
    assert state.calls==[] and state.closed==([] if fault=='open' else [888])


@pytest.mark.parametrize('error',[OSError('close failed'),KeyboardInterrupt()])
def test_sticky_close_after_two_commands_prevents_result(prepared,monkeypatch,error):
    state=mock_sg(prepared,monkeypatch,close_error=error)
    with pytest.raises(type(error)):n.run_campaign(prepared)
    assert state.calls==list(n.OPERATIONS) and state.closed==[888]
    assert not (Path(json.loads(prepared.probe.campaign)['receipt_path'])/'result.json').exists()


def test_consumed_open_permit_cannot_reopen(prepared,monkeypatch):
    state=mock_sg(prepared,monkeypatch);permit=n._OpenPermit(prepared);n._OPENING.add(permit)
    sg=n.NativeSG(prepared,permit);sg.close()
    with pytest.raises(ValueError):n.NativeSG(prepared,permit)
    assert len(state.opens)==1


@pytest.mark.parametrize('fault',['symlink','fifo','directory','oversized','wrong_hash','fdopen'])
def test_source_bootstrap_bounded_before_execution(tmp_path,monkeypatch,fault):
    path=tmp_path/'source.py';path.write_bytes(b'raise AssertionError("executed")')
    wanted=n.digest(path.read_bytes())
    if fault=='symlink':link=tmp_path/'link';link.symlink_to(path);path=link
    elif fault=='fifo':path.unlink();os.mkfifo(path)
    elif fault=='directory':path.unlink();path.mkdir()
    elif fault=='oversized':path.write_bytes(b'x'*(2*1048576+1))
    elif fault=='wrong_hash':wanted='0'*64
    else:
        closed=[];original=n.os.close
        monkeypatch.setattr(n.os,'fdopen',lambda *a,**kw:(_ for _ in ()).throw(OSError('fdopen failure')))
        def close(fd):closed.append(fd);return original(fd)
        monkeypatch.setattr(n.os,'close',close)
    with pytest.raises((ValueError,OSError)):n.load_source(path,wanted,'_native_test_bad_source')
    if fault=='fdopen':assert len(closed)==1


def test_linux_only_cli_and_exact_campaign_argument(monkeypatch):
    monkeypatch.setattr(n.sys,'argv',['stage-sg','--campaign','/private/reviewed.json'])
    monkeypatch.setattr(n.sys,'platform','darwin')
    monkeypatch.setattr(n,'prepare_campaign',lambda _:pytest.fail('factory after wrong OS'))
    with pytest.raises(SystemExit,match='Linux'):n.main()


def test_original_reader_still_refuses_ram_and_efuse():
    assert n.digest(Path(reader.__file__).read_bytes())==n.READER_SHA
    for phase in ('rom','loader'):
        for op in (0xfd07,0xfc12,0xa1):
            with pytest.raises(ValueError):reader.request(op,phase,address=0x01c033d8)


def test_actual_private_native_factory_and_mocked_ioctl_capture(actual,monkeypatch,tmp_path):
    install_path=tmp_path/'install.json';envelope(install_path,actual.path,actual.config['receipt_path'])
    accepted=install.prepare_campaign(install_path)
    flash=SGModel(monkeypatch,json.loads(accepted.mapping),actual.baseline)
    monkeypatch.setattr(accepted.bridge,'discover_sg',flash.discover)
    install.run_campaign(accepted)
    assert bytes(flash.flash)==actual.target
    bc=target_config(actual,install_path);bc['receipt_path']=str(Path(actual.config['receipt_path']).parent/'modeled-native-target-boot')
    boot_path=tmp_path/'boot.json';boot_path.write_bytes(p.canonical(bc))
    target_prepared=target_reset.prepare_campaign(boot_path)
    boot_sha=p.digest(boot_path.read_bytes());parent=Path(bc['receipt_path']).parent
    receipt=Path(bc['receipt_path']);receipt.mkdir(mode=0o700)
    (parent/'.target-core-reset.consumed').write_text(boot_sha)
    commands=receipt/'commands.jsonl';commands.write_bytes(b'\n'.join(p.canonical(e) for e in
        boot_events(bc,boot_sha,target_prepared.backup_manifest_sha256)))
    usb=dict(bc['usb_binding'],devnum=str(int(bc['usb_binding']['devnum'])+1))
    mapping=copy.deepcopy(bc['sg_binding']);mapping['usb_identity'][1]+=1;mapping['node_identity'][1]+=1
    sp=tmp_path/'snapshot.json';sp.write_bytes(p.canonical(snapshot(boot_sha,usb,mapping)))
    config=dict(schema=1,kind='fm1-exact-diagnostic-stage-probe',adapter_sha256=n.PROBE_SHA,
        target_boot_campaign_path=str(boot_path),target_boot_campaign_sha256=boot_sha,
        target_boot_commands_sha256=p.digest(commands.read_bytes()),target_boot_exit_status=0,
        rom_snapshot_path=str(sp),rom_snapshot_sha256=p.digest(sp.read_bytes()),
        active_session_state='post-target-boot-rom-no-later-commands-no-loader-upload',
        receipt_path=str(parent/'modeled-native-stage-probe'))
    probe_path=tmp_path/'probe.json';probe_path.write_bytes(p.canonical(config))
    campaign=dict(schema=1,kind='fm1-exact-native-diagnostic-stage-probe',
        adapter_sha256=n.digest(Path(n.__file__).read_bytes()),probe_campaign_path=str(probe_path),
        probe_campaign_sha256=n.digest(probe_path.read_bytes()))
    path=tmp_path/'native.json';path.write_bytes(n.canonical(campaign))
    factory_start=time.perf_counter();obj=n.prepare_campaign(path)
    factory_seconds=time.perf_counter()-factory_start
    for field,value in [('schema',True),('kind','arbitrary-ram'),('adapter_sha256','0'*64),
        ('probe_campaign_sha256','0'*64),('probe_campaign_path',str(tmp_path/'absent'))]:
        bad=dict(campaign);bad[field]=value;path.write_bytes(n.canonical(bad))
        with pytest.raises((ValueError,OSError)):n.prepare_campaign(path)
    path.write_bytes(n.canonical(campaign));obj.check()
    state=mock_sg(obj,monkeypatch)
    result=n.run_campaign(obj)
    assert state.calls==list(n.OPERATIONS) and state.closed==[888]
    assert result['classification']=='conditional-diagnostic-execution-evidence'
    assert bytes(flash.flash)==actual.target
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
        (out/'native-stage-modeled-result.json').write_bytes(n.canonical(result))
        (out/'native-stage-modeled-summary.json').write_bytes(n.canonical(dict(
            actual_private_native_inputs=True,factory_seconds=factory_seconds,app_sha256=p.APP_SHA,elf_sha256=p.ELF_SHA,
            target_sha256=p.TARGET_SHA,boot_receipt_modeled=True,sg_ioctl_mocked=True,
            hardware_access=False,commands=[cdb.hex() for cdb,_,_ in state.calls],
            handles_closed=len(state.closed))))
