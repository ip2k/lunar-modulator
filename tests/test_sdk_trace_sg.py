"""MIT. New native trace wrapper models; every device syscall is replaced.

Private registries/permits below are explicitly manufactured model authority.
No real boot factory, SG opener or physical read is accepted by these tests.
"""
import copy
import ctypes as C
from dataclasses import replace
import errno
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import pytest

import fm1_sdk_trace_sg as n
import fm1_sdk_trace_read as p
import fm1_uboot_read as header
from test_sdk_trace_read import prepared as read_prepared, native, trace, stage


@pytest.fixture
def prepared(read_prepared):
    obj = n.Prepared(b'{}', read_prepared, p, SimpleNamespace(discover_sg=None), header.SGHeader, ())
    n._AUTHORIZED.add(obj)
    return obj


def mock_sg(prepared, monkeypatch, fault=None):
    monkeypatch.setattr(n.sys, 'platform', 'linux')
    mapping=json.loads(prepared.read.snapshot)['sg_binding'];usb=json.loads(prepared.read.snapshot)['usb_binding']
    state=SimpleNamespace(calls=[],opens=[],closes=[],locks=[],discoveries=0,fd=888)
    real_open,real_close,real_fstat=n.os.open,n.os.close,n.os.fstat
    def discover(actual):
        assert actual==usb;state.discoveries+=1
        result=copy.deepcopy(mapping)
        if fault=='initialmap' or (fault=='postmap' and state.calls):result['usb_identity']=[0,0,0]
        return result
    prepared.bridge.discover_sg=discover
    def opened(path,flags,*args):
        if str(path)==mapping['node']:
            state.opens.append(flags)
            assert (prepared.read.receipt/'commands.jsonl').exists()
            assert prepared.read.marker.exists()
            if fault=='open':raise OSError(errno.EACCES,'modeled open')
            return state.fd
        return real_open(path,flags,*args)
    monkeypatch.setattr(n.os,'open',opened)
    def fstat(fd):
        if fd!=state.fd:return real_fstat(fd)
        ids=mapping['node_identity']
        return SimpleNamespace(st_mode=stat.S_IFREG if fault=='regular' else stat.S_IFCHR,
                              st_dev=ids[0],st_ino=ids[1]+int(fault=='fdidentity'),st_rdev=ids[2])
    monkeypatch.setattr(n.os,'fstat',fstat)
    def close(fd):
        if fd!=state.fd:return real_close(fd)
        state.closes.append(fd)
        if fault=='close':raise OSError(errno.EIO,'modeled close')
    monkeypatch.setattr(n.os,'close',close)
    def lock(fd,flags):
        assert fd==state.fd;state.locks.append(flags)
        if fault=='lock':raise BlockingIOError(errno.EWOULDBLOCK,'modeled lock')
    monkeypatch.setattr(n.fcntl,'flock',lock)
    def ioctl(fd,number,h):
        assert fd==state.fd and number==0x2285
        assert h.interface_id==ord('S') and h.direction==-3 and h.timeout==3000
        assert h.sense_max==32 and h.flags==h.iovec_count==h.pack_id==0 and h.user is None
        cdb=C.string_at(h.cmd,h.cmd_len)
        op=(cdb,b'',h.data_len)
        assert op==n.OPERATIONS[len(state.calls)]
        events=[json.loads(l) for l in (prepared.read.receipt/'commands.jsonl').read_text().splitlines()]
        assert events[-1]['event']=='submit_intent' and events[-1]['cdb']==cdb.hex()
        native_events=[json.loads(l) for l in (prepared.read.receipt/'native.jsonl').read_text().splitlines()]
        assert native_events[-1]['event']=='native_ioctl_intent'
        state.calls.append(op)
        if fault=='ioctl':raise OSError(errno.EIO,'modeled ioctl')
        raw=(b'\0'*8+b'WL82'.ljust(8)+b'UBOOT1.00'.ljust(16)+b'1.00') if len(state.calls)==1 else p.decode_transfer(trace() if h.data_len==64 else stage(),h.data_len)
        if fault=='changed' and len(state.calls)==4:raw=p.decode_transfer(trace(4),64)
        C.memmove(h.data,raw,len(raw))
        if fault in ('status','masked','msg','host','driver','resid','info','sense_len'):setattr(h,fault,1)
        if fault=='negative_resid':h.resid=-1
        if fault=='oversize_resid':h.resid=h.data_len+1
        if fault=='sense':h.sense_len=2;C.memmove(h.sense,b'\x70\x05',2)
        if fault=='long_sense':h.sense_len=255;C.memmove(h.sense,b'\x70'*32,32)
    monkeypatch.setattr(n.fcntl,'ioctl',ioctl)
    return state


def events(prepared,name='commands.jsonl'):
    return [json.loads(l) for l in (prepared.read.receipt/name).read_text().splitlines()]


def test_exact_five_pointer_requests_one_handle_durable_receipt_and_replay_stop(prepared,monkeypatch):
    state=mock_sg(prepared,monkeypatch)
    result=n.run_campaign(prepared)
    assert state.calls==list(n.OPERATIONS)==list(prepared.read.plan.operations)
    assert state.opens==[os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK]
    assert state.locks==[n.fcntl.LOCK_EX|n.fcntl.LOCK_NB] and state.closes==[888]
    assert result['progress']=='final-start-intent' and result['new_ranges_hardware_verified'] is False
    assert [e['event'] for e in events(prepared,'native.jsonl')]==['native_open_intent','native_opened',*['native_ioctl_intent']*5]
    with pytest.raises(FileExistsError):n.run_campaign(prepared)
    assert len(state.calls)==5


@pytest.mark.parametrize('fault',['status','masked','msg','host','driver','resid','info','sense_len',
    'negative_resid','oversize_resid','sense','long_sense','postmap','ioctl','close','changed'])
def test_actual_failure_fields_preserved_no_result_no_retry(prepared,monkeypatch,fault):
    state=mock_sg(prepared,monkeypatch,fault)
    with pytest.raises((ValueError,OSError)):n.run_campaign(prepared)
    assert state.closes==[888] and prepared.read.marker.exists()
    assert not (prepared.read.receipt/'result.json').exists()
    assert len(state.calls)==(5 if fault in ('close','changed') else 1)
    journal=events(prepared)
    assert journal[-1]['event']=='capture_stopped_ambiguous'
    completions=[e for e in journal if e['event']=='completion']
    if fault=='ioctl':
        assert not completions
        actual=[e for e in events(prepared,'native.jsonl') if e['event']=='native_ioctl_exception'][0]
        assert actual['errno']==errno.EIO and actual['completion_valid'] is False
    else:
        assert completions
        first=completions[0]
        if fault in ('status','masked','msg','host','driver','resid','info','sense_len'):assert first[fault]==1
        if fault=='resid':assert first['actual_response_bytes']==35
        if fault=='negative_resid':assert first['resid']==-1
        if fault=='oversize_resid':assert first['resid']==37
        if fault=='sense':assert first['sense_hex']=='7005'
        if fault=='long_sense':assert first['sense_len']==255 and first['actual_sense_bytes']==32
    with pytest.raises(FileExistsError):n.run_campaign(prepared)


@pytest.mark.parametrize('fault',['initialmap','open','lock','regular','fdidentity'])
def test_open_mapping_lock_and_fd_failure_before_ioctl_consumes(prepared,monkeypatch,fault):
    state=mock_sg(prepared,monkeypatch,fault)
    with pytest.raises((ValueError,OSError)):n.run_campaign(prepared)
    assert not state.calls and prepared.read.marker.exists()
    assert state.closes==([] if fault in ('initialmap','open') else [888])
    assert not (prepared.read.receipt/'result.json').exists()


@pytest.mark.parametrize('fault',['copy','nopermit','foreignpermit','nonlinux'])
def test_invalid_authority_never_discovers_or_opens(prepared,monkeypatch,fault):
    state=mock_sg(prepared,monkeypatch)
    permit=None;obj=prepared
    if fault=='copy':
        obj=replace(prepared);permit=n._OpenPermit(obj);n._OPENING.add(permit)
    elif fault=='foreignpermit':permit=n._OpenPermit(replace(prepared));n._OPENING.add(permit)
    elif fault=='nonlinux':monkeypatch.setattr(n.sys,'platform','darwin')
    with pytest.raises(ValueError):n.NativeSG(obj,permit)
    assert not state.opens and not state.discoveries


@pytest.mark.parametrize('fault',['wrongaddress','upload','reset','nor','out','boolcount','reorder'])
def test_native_transport_rejects_nonfixed_operation_sticky(prepared,monkeypatch,fault):
    state=mock_sg(prepared,monkeypatch)
    prepared.read.receipt.mkdir();prepared.read.marker.write_text('modeled');(prepared.read.receipt/'commands.jsonl').write_text('')
    permit=n._OpenPermit(prepared);n._OPENING.add(permit);bus=n.NativeSG(prepared,permit)
    op=n.OPERATIONS[0]
    if fault=='wrongaddress':op=(bytes.fromhex('fd0701c020000040ffffffffffffffff'),b'',64)
    elif fault=='upload':op=(b'\xfb\x06'+b'\xff'*14,b'',512)
    elif fault=='reset':op=(b'\xfc\x0c'+b'\xff'*14,b'',0)
    elif fault=='nor':op=(b'\xfd\x05'+b'\xff'*14,b'',256)
    elif fault=='out':op=(op[0],b'x',36)
    elif fault=='boolcount':op=(op[0],b'',True)
    else:op=n.OPERATIONS[1]
    with pytest.raises(ValueError):bus.exchange(*op)
    assert not state.calls and state.closes==[888] and bus.failed
    with pytest.raises(ValueError):bus.exchange(*n.OPERATIONS[0])


def test_native_monotonic_timeout_consumes_without_ioctl(prepared,monkeypatch):
    state=mock_sg(prepared,monkeypatch)
    real=n.time.monotonic;calls=0
    def clock():
        nonlocal calls;calls+=1
        return real()+ (11 if calls>=4 else 0)
    monkeypatch.setattr(n.time,'monotonic',clock)
    with pytest.raises(ValueError):n.run_campaign(prepared)
    assert not state.calls and state.closes==[888]


def test_source_evidence_drift_between_native_intent_and_ioctl(prepared,monkeypatch,tmp_path):
    state=mock_sg(prepared,monkeypatch)
    path=tmp_path/'source';path.write_bytes(b'frozen')
    obj=n.Prepared(prepared.campaign,prepared.read,prepared.module,prepared.bridge,prepared.header_type,((path,b'frozen',65536),))
    n._AUTHORIZED.add(obj)
    original=n.NativeSG.log
    def log(self,event,**fields):
        original(self,event,**fields)
        if event=='native_ioctl_intent':path.write_bytes(b'changed')
    monkeypatch.setattr(n.NativeSG,'log',log)
    with pytest.raises(ValueError):n.run_campaign(obj)
    assert not state.calls and state.closes==[888]


def test_native_journal_fdopen_failure_closes_raw_fd_without_opening_device(prepared,monkeypatch):
    state=mock_sg(prepared,monkeypatch);original=n.os.fdopen;leaked=[]
    def fail(fd,mode,*args,**kwargs):
        # The outer command journal opens first; fail only native wrapper journal.
        target=os.readlink('/proc/self/fd/'+str(fd))
        if target.endswith('/native.jsonl'):
            leaked.append(fd);raise OSError('modeled native fdopen')
        return original(fd,mode,*args,**kwargs)
    monkeypatch.setattr(n.os,'fdopen',fail)
    with pytest.raises(OSError,match='native fdopen'):n.run_campaign(prepared)
    assert not state.opens and not state.calls and len(leaked)==1
    with pytest.raises(OSError):os.fstat(leaked[0])


def test_factory_activation_closed_before_any_discovery_or_open(monkeypatch,tmp_path):
    monkeypatch.setattr(n.os,'open',lambda *a,**k:pytest.fail('opened while closed'))
    with pytest.raises(ValueError,match='activation closed'):n.prepare_campaign(tmp_path/'campaign',None)


def test_exact_byte_loading_rejects_different_source(tmp_path):
    path=tmp_path/'source.py';path.write_text('raise AssertionError("executed")')
    with pytest.raises(ValueError,match='source differs'):n.load_source(path,'0'*64,'_test_bad_trace_source')


def test_private_exact_parser_defeats_foreign_cache_without_replacing_it(native,monkeypatch):
    root=Path(n.__file__).absolute().parent
    parser=n.load_source(root/'jieli/audit_link.py',n.AUDIT_SHA,'_test_trace_exact_parser')
    foreign=SimpleNamespace(Elf=lambda *a:pytest.fail('ambient foreign parser executed'))
    monkeypatch.setitem(sys.modules,'jieli.audit_link',foreign)
    reader_path=root/'fm1_sdk_trace_read.py'
    reader=n.load_source(reader_path,n.digest(reader_path.read_bytes()),'_test_trace_exact_reader',elf_parser=parser)
    plan=reader.derive_plan(*native)
    assert plan.ranges==((0x01c02880,64),(0x01c03418,4))
    assert sys.modules['jieli.audit_link'] is foreign
    assert reader.__dict__['__builtins__'] is not vars(n.builtins)


@pytest.mark.parametrize('statement',['import jieli.audit_link','from jieli.audit_link import audit'])
def test_private_parser_import_surface_is_bounded(tmp_path,statement):
    path=tmp_path/'source.py';path.write_text(statement)
    with pytest.raises(ValueError,match='private Elf dependency'):
        n.load_source(path,n.digest(path.read_bytes()),'_test_trace_bad_parser_import',elf_parser=SimpleNamespace(Elf=object))
