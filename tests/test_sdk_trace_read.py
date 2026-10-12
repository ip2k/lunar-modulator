"""Exact trace reader models and actual ELF parsing; never device I/O.

Private registries below are populated explicitly for transport models only.
They do not exercise or assert acceptance of a real boot-lineage factory.
"""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import struct
import sys
from types import SimpleNamespace
import pytest

import fm1_sdk_trace_read as p


def trace(phase=5, seq=None, mailbox=None, **changes):
    seq = seq if seq is not None else {1: 2, 2: 4, 3: 6, 4: 8, 5: 10, 6: 12, 7: 12}[phase]
    mailbox = mailbox if mailbox is not None else int(phase >= 4)
    fields = dict(phase=phase, complement=phase ^ 0xffffffff, mailbox=mailbox,
        panel=0, elapsed=20000, heartbeat=1976, reason=0xffffffff,
        sys=360000000, lsb=60000000, sequence=seq)
    if phase == 1:
        fields.update(elapsed=0, heartbeat=0, sys=0, lsb=0)
    fields.update(changes)
    return struct.pack('<IHH16sIIIiIIIIII', 0x4c525431, 1, 64, p.NONCE, *fields.values())


def stage(value=6):
    return struct.pack('<I', value)


@pytest.mark.parametrize('phase,seq,mailbox,st', [(1,2,0,0), (1,2,0,0xff),
    (1,2,0,8), (2,4,0,6), (3,6,0,6), (4,8,1,6), (5,10,1,6),
    (6,12,1,6), (6,12,1,7), (7,8,0,6), (7,8,0,8), (7,10,1,8), (7,12,1,8)])
def test_native_progress_and_stage_store_gap(phase,seq,mailbox,st):
    result = p.interpret(trace(phase,seq,mailbox), stage(st))
    assert result['fields']['phase'] == phase
    assert result['stage_update_pending'] == (phase in (6,7) and st == 6)
    assert result['startup_reason'] == 'unavailable'
    assert all(result[n] is False for n in ('retention_verified', 'rom_handler_verified',
        'new_ranges_hardware_verified', 'native_packet_operand_semantics_verified',
        'device_mutation_free_verified', 'recovery_cause_verified', 'display_observed',
        'physical_recovery_verified', 'nonce_identifies_boot'))


@pytest.mark.parametrize('offset,fmt,value', [(0,'I',0), (4,'H',2), (6,'H',63),
    (8,'I',0), (24,'I',0), (24,'I',8), (28,'I',5), (32,'I',0), (32,'I',2),
    (36,'i',1), (36,'i',-5), (40,'I',19999), (48,'I',0), (52,'I',0),
    (56,'I',60000001), (60,'I',0), (60,'I',9), (60,'I',12)])
def test_stale_torn_unknown_and_contradictory_trace_rejected(offset,fmt,value):
    raw = bytearray(trace())
    struct.pack_into('<'+fmt, raw, offset, value)
    with pytest.raises(ValueError): p.interpret(bytes(raw), stage())


@pytest.mark.parametrize('st', [0,1,5,7,8,0xff,0xffffffff])
def test_phase5_contradictory_stage_rejected(st):
    with pytest.raises(ValueError): p.interpret(trace(), stage(st))


@pytest.mark.parametrize('field', ['panel','elapsed','heartbeat','sys','lsb'])
def test_initialization_cache_must_be_zero(field):
    with pytest.raises(ValueError): p.interpret(trace(1, **{field:1}), stage(1))


@pytest.mark.parametrize('panel,elapsed,heartbeat,sys,lsb', [
    (-1,20000,1976,0xffffffff,0), (-2,20000,1976,360000000,60000000),
    (-3,199,2000,360000000,60000000), (-4,19999,2000,360000000,60000000),
    (0,20000,0,360000000,60000000)])
def test_native_failed_probe_and_zero_heartbeat_are_not_fabricated_success(panel,elapsed,heartbeat,sys,lsb):
    result = p.interpret(trace(panel=panel,elapsed=elapsed,heartbeat=heartbeat,sys=sys,lsb=lsb),stage())
    assert result['fields']['panel_result']==panel


@pytest.mark.parametrize('changes', [dict(panel=-4,elapsed=20000,heartbeat=2000),
    dict(panel=-4,elapsed=19999,heartbeat=1999),dict(panel=-2,sys=0),dict(panel=0,lsb=0)])
def test_native_cache_failure_relationships(changes):
    with pytest.raises(ValueError): p.interpret(trace(**changes),stage())


def test_transfer_seed_restarts_and_repeat_equality_is_required():
    a,b = trace(),stage()
    raw_a,raw_b = p.decode_transfer(a,64),p.decode_transfer(b,4)
    assert raw_a[:4] == p.decode_transfer(a[:4],4)
    assert p.interpret_repeated(raw_a,raw_b,raw_a,raw_b)['progress']=='final-start-intent'
    with pytest.raises(ValueError):
        p.interpret_repeated(raw_a,raw_b,p.decode_transfer(trace(4),64),raw_b)
    with pytest.raises(ValueError):
        p.interpret_repeated(raw_a,raw_b,raw_a,p.decode_transfer(stage(7),4))


@pytest.mark.parametrize('count', [0,3,5,32,65,True])
def test_codec_rejects_arbitrary_range_lengths(count):
    with pytest.raises(ValueError): p.decode_transfer(bytes(int(count)),count)


@pytest.fixture
def native():
    root = Path(os.environ['LUNAR_TRACE_NATIVE'])
    return tuple((root/n).read_bytes() for n in
        ('lunar-sdk-diagnostic.elf','lunar-sdk-diagnostic.app.bin','build-manifest.json'))


def test_actual_native_elf_derived_exact_plan(native):
    plan = p.derive_plan(*native)
    plan.check()
    assert plan.ranges == ((0x01c02880,64),(0x01c03418,4))
    assert [(c.hex(),n) for c,_,n in plan.operations] == [
        ('120000002400',36),('fd0701c028800040ffffffffffffffff',64),
        ('fd0701c034180004ffffffffffffffff',4),
        ('fd0701c028800040ffffffffffffffff',64),('fd0701c034180004ffffffffffffffff',4)]
    with pytest.raises(ValueError): replace(plan).check()


@pytest.mark.parametrize('index', [0,1,2])
def test_actual_candidate_byte_pin_changed_rejected(native,index):
    bad = list(native)
    bad[index] = bad[index][:-1] + bytes([bad[index][-1]^1])
    with pytest.raises(ValueError): p.derive_plan(*bad)


@pytest.mark.parametrize('field,value', [('size',63),('address',0x01c02881),
    ('binding',0x21),('section_flags',7),('section_type',1)])
def test_elf_symbol_geometry_is_checked_independently_of_outer_digest(native,field,value):
    from jieli.audit_link import Elf
    raw = bytearray(native[0]); elf = Elf(bytes(raw))
    shoff,=struct.unpack_from('<I',raw,0x20)
    shentsize,=struct.unpack_from('<H',raw,0x2e)
    symbol=next(s for s in elf.symbols if s['name']=='lunar_sdk_recovery_trace_record')
    if field.startswith('section_'):
        offset=shoff+symbol['shndx']*shentsize+(8 if field=='section_flags' else 4)
        struct.pack_into('<I',raw,offset,value)
    else:
        section=next(s for s in elf.sections if s['type']==2)
        index=elf.symbols.index(symbol)
        offset=section['offset']+index*16
        if field=='binding':struct.pack_into('<B',raw,offset+12,value)
        else:struct.pack_into('<I',raw,offset+(8 if field=='size' else 4),value)
    with pytest.raises(ValueError):p._geometry(bytes(raw))


def bindings():
    usb=dict(path='3-2',busnum='3',devnum='31',vid='4c4a',pid='8057')
    sg=dict(node='/dev/sg0',**{'class':'/sys/class/scsi_generic/sg0'},
        device='/sys/devices/sg0',usb='/sys/devices/3-2',node_identity=[1,2,3],
        class_identity=[4,5,6],device_identity=[7,8,9],usb_identity=[10,11,12])
    return usb,sg


def snapshot_lineage():
    usb,sg=bindings()
    lineage=dict(boot_campaign_sha256='a'*64,boot_completed_at=100,
        app_sha256=p.APP_SHA,elf_sha256=p.ELF_SHA,nonce_hex=p.NONCE.hex(),
        usb_binding=dict(usb,devnum='30'),sg_binding=dict(sg,node_identity=[9,9,9],usb_identity=[8,8,8]))
    snapshot=dict(schema=1,kind='fm1-passive-post-trace-boot-rom',observed_at=101,
        usb_binding=usb,sg_binding=sg,target_boot_campaign_sha256='a'*64,
        quiet_state='initial-rom-no-later-commands-no-loader-upload')
    return snapshot,lineage


def test_offline_fresh_binding_and_preupload_assertion():
    s,l=snapshot_lineage()
    assert p.verify_snapshot(p.canonical(s),l,102)==p.canonical(s)


@pytest.mark.parametrize('fault', ['stale','future','beforeboot','foreignboot','uploaded',
    'schema_bool','sameusb','samefd','samesysfs','otherport','pid','usbmap','nonce','app','elf'])
def test_snapshot_rejects_stale_replay_foreign_lineage_and_binding(fault):
    s,l=snapshot_lineage()
    now=102
    if fault=='stale':now=222
    elif fault=='future':s['observed_at']=103
    elif fault=='beforeboot':s['observed_at']=99
    elif fault=='foreignboot':s['target_boot_campaign_sha256']='b'*64
    elif fault=='uploaded':s['quiet_state']='loader-uploaded'
    elif fault=='schema_bool':s['schema']=True
    elif fault=='sameusb':s['usb_binding']=l['usb_binding']
    elif fault=='samefd':s['sg_binding']['node_identity']=l['sg_binding']['node_identity']
    elif fault=='samesysfs':s['sg_binding']['usb_identity']=l['sg_binding']['usb_identity']
    elif fault=='otherport':s['usb_binding']['path']='3-3'
    elif fault=='pid':s['usb_binding']['pid']='c755'
    elif fault=='usbmap':s['sg_binding']['usb']='/sys/devices/3-3'
    else:l[{'nonce':'nonce_hex','app':'app_sha256','elf':'elf_sha256'}[fault]]='0'*64
    with pytest.raises(ValueError):p.verify_snapshot(p.canonical(s),l,now)


def test_real_factory_stays_closed_without_reviewed_boot_successor(tmp_path):
    with pytest.raises(ValueError,match='successor not accepted'):
        p.prepare(None,tmp_path/'snapshot',None,tmp_path/'receipt')


@pytest.fixture
def prepared(tmp_path,native,monkeypatch):
    s,l=snapshot_lineage()
    l['boot_completed_at']=p.time.time()-2;s['observed_at']=p.time.time()-1
    class Lineage:
        def check(self): pass
        def read_binding(self):return l
    snapshot=p.canonical(s);path=tmp_path/'snapshot.json';path.write_bytes(snapshot)
    plan=p.derive_plan(*native)
    seal=p.canonical(dict(schema=1,plan_sha256=p.digest(plan.seal),snapshot_sha256=p.digest(snapshot),
        lineage=l,receipt_path=str(tmp_path/'receipt')))
    result=p.Prepared(plan,snapshot,seal,((path,snapshot,65536),),Lineage(),tmp_path/'receipt',tmp_path/'consumed')
    p._PREPARED.add(result)
    return result


class Bus:
    def __init__(self,prepared,fault=None):
        self.prepared,self.fault=prepared,fault;self.sent=[];self.closed=False;self.binds=0
    def binding(self):
        self.binds+=1;s=json.loads(self.prepared.snapshot)
        actual=dict(usb_binding=s['usb_binding'],sg_binding=s['sg_binding'],
            fd_identity=s['sg_binding']['node_identity'],fd_mode=stat.S_IFCHR|0o600)
        if self.fault=='binding' and self.binds>=3:actual['fd_identity']=[0,0,0]
        return actual
    def exchange(self,cdb,out,count):
        self.sent.append((cdb,out,count));index=len(self.sent)-1
        inquiry=b'\0'*8+b'WL82'.ljust(8)+b'UBOOT1.00'.ljust(16)+b'\0'*4
        data=inquiry if index==0 else p.decode_transfer(trace() if count==64 else stage(),count)
        if self.fault=='short':data=data[:-1]
        if self.fault=='changed' and index==3:data=p.decode_transfer(trace(4),64)
        return p.Completion(data,sense=b'\x70\x05' if self.fault=='sense' else b'',**({self.fault:1} if self.fault in
            ('status','masked','msg','host','driver','resid','info','sense_len') else {}))
    def close(self):
        self.closed=True
        if self.fault=='close':raise OSError('close failed')


def test_durable_single_use_capture_and_result(prepared):
    bus=Bus(prepared)
    result=p.run(prepared,lambda _:bus)
    assert bus.sent==list(prepared.plan.operations) and bus.closed
    assert result['progress']=='final-start-intent'
    assert prepared.marker.is_file() and (prepared.receipt/'result.json').is_file()
    events=[json.loads(line) for line in (prepared.receipt/'commands.jsonl').read_text().splitlines()]
    assert [e['event'] for e in events]==['read_prepared',*(['submit_intent','completion']*5),'coherent_capture_completed']
    assert all(e.get('retry') is False for e in events if 'retry' in e)
    with pytest.raises((ValueError,FileExistsError)):p.run(prepared,lambda _:bus)
    with pytest.raises(ValueError):p.Session(prepared,Bus(prepared),lambda *a,**k:None)


@pytest.mark.parametrize('fault', ['status','masked','msg','host','driver','resid','info','sense_len',
    'short','binding','changed','close','sense'])
def test_failed_capture_consumed_closed_no_result_no_retry(prepared,fault):
    bus=Bus(prepared,fault)
    with pytest.raises((ValueError,OSError)):p.run(prepared,lambda _:bus)
    assert bus.closed and prepared.marker.exists()
    assert not (prepared.receipt/'result.json').exists()
    assert len(bus.sent) <= (5 if fault in ('changed','close') else 1)
    events=[json.loads(line) for line in (prepared.receipt/'commands.jsonl').read_text().splitlines()]
    completions=[e for e in events if e['event']=='completion']
    assert completions
    first=completions[0]
    assert first['actual_response_bytes']==(35 if fault=='short' else 36)
    assert first['sense_hex']==('7005' if fault=='sense' else '')
    if fault in ('status','masked','msg','host','driver','resid','info','sense_len'):
        assert first[fault]==1
    assert events[-1]['event']=='capture_stopped_ambiguous'


@pytest.mark.parametrize('fault',['extra','wrongaddress','upload','outpayload','countbool','reorder'])
def test_session_rejects_arbitrary_or_reordered_commands_sticky(prepared,fault):
    bus=Bus(prepared);session=p.Session(prepared,bus,lambda *a,**k:None)
    op=prepared.plan.operations[0]
    if fault=='extra':
        for op in prepared.plan.operations:session.exchange(*op)
    elif fault=='wrongaddress':op=(bytes.fromhex('fd0701c020000040ffffffffffffffff'),b'',64)
    elif fault=='upload':op=(b'\xfb\x06'+b'\xff'*14,b'',512)
    elif fault=='outpayload':op=(op[0],b'x',op[2])
    elif fault=='countbool':op=(op[0],b'',True)
    elif fault=='reorder':op=prepared.plan.operations[1]
    before=len(bus.sent)
    with pytest.raises(ValueError):session.exchange(*op)
    assert len(bus.sent)==before and session.failed and bus.closed
    with pytest.raises(ValueError):session.exchange(*prepared.plan.operations[0])


def test_copy_and_evidence_drift_rejected_before_transport(prepared):
    with pytest.raises(ValueError):p.Session(replace(prepared),Bus(prepared),lambda *a,**k:None)
    prepared.evidence[0][0].write_bytes(b'changed')
    bus=Bus(prepared)
    with pytest.raises(ValueError):p.Session(prepared,bus,lambda *a,**k:None)
    assert not bus.sent and bus.closed


def test_source_drift_between_durable_intent_and_exchange_stops(prepared):
    bus=Bus(prepared)
    def log(event,**fields):
        if event=='submit_intent':prepared.evidence[0][0].write_bytes(b'changed')
    session=p.Session(prepared,bus,log)
    with pytest.raises(ValueError):session.exchange(*prepared.plan.operations[0])
    assert not bus.sent and bus.closed


def test_monotonic_timeout_is_sticky(prepared,monkeypatch):
    bus=Bus(prepared);session=p.Session(prepared,bus,lambda *a,**k:None)
    monkeypatch.setattr(p.time,'monotonic',lambda:session.started+11)
    with pytest.raises(ValueError):session.exchange(*prepared.plan.operations[0])
    assert not bus.sent and bus.closed


@pytest.mark.parametrize('which',['exclusive','journal'])
def test_fdopen_failure_closes_raw_descriptor_and_never_opens_transport(prepared,monkeypatch,which):
    original=p.os.fdopen; leaked=[]; opened=[]
    def fail(fd,mode,*args,**kwargs):
        if mode==('wb' if which=='exclusive' else 'w'):
            leaked.append(fd)
            raise OSError('fdopen fault')
        return original(fd,mode,*args,**kwargs)
    monkeypatch.setattr(p.os,'fdopen',fail)
    with pytest.raises(OSError,match='fdopen fault'):
        p.run(prepared,lambda _:opened.append(True))
    assert len(leaked)==1 and not opened
    with pytest.raises(OSError):os.fstat(leaked[0])


@pytest.mark.parametrize('fault',['cached','foreign','unrecorded'])
def test_boot_module_must_be_canonical_and_imported_from_pinned_source(monkeypatch,fault):
    source=b'pinned boot source'; source_path=Path(p.__file__).absolute().parent/'fm1_sdk_trace_boot.py'
    sha=p.digest(source)
    module=SimpleNamespace(__file__=str(source_path),IMPORTED_SOURCE_SHA256=sha)
    if fault=='cached':module.IMPORTED_SOURCE_SHA256='0'*64
    elif fault=='foreign':module.__file__='/foreign/fm1_sdk_trace_boot.py'
    else:del module.IMPORTED_SOURCE_SHA256
    monkeypatch.setattr(p,'BOOT_POLICY_SHA',sha)
    monkeypatch.setattr(p,'read_file',lambda path,*args:source)
    monkeypatch.setitem(sys.modules,'fm1_sdk_trace_boot',module)
    with pytest.raises(ValueError,match='Canonical pinned'):
        p.prepare(None,None,None,None)
