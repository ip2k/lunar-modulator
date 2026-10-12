"""MIT. Injected-only stage probe; modeled SG, no physical device access."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import struct
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_diagnostic_stage_probe as p
import fm1_fixed_target_reset as target_reset
import fm1_sdk_install as install
import fm1_sdk_rehearsal as rehearsal
from test_sdk_install import envelope
from test_sdk_rehearsal import actual, SGModel
from test_fixed_target_reset import target_config

PLAIN=bytes.fromhex('0600000000000000001c4e0e00879303822d0002204e00006300000000000000')
# Independent bit-at-a-time CRC16 calculation, cross-checking pinned source magic
# GB2312 bytes c3cf... and seed FFFFFFFF. Never derived via the tested decoder.
RAW=bytes.fromhex('29a481cc4ec15deaeebef8a8290d47f481a9ebe3efc48a14dee6dd1cd0f8463b')
USB=dict(path='3-2',busnum='3',devnum='29',vid='4c4a',pid='8057')
MAPPING=dict(node='/dev/sgMOCK',**{'class':'/sys/mock/sg','device':'/sys/mock/device','usb':'/sys/mock/usb'},
    node_identity=[1,2,3],class_identity=[4,5,6],device_identity=[7,8,9],usb_identity=[10,11,12])


def snapshot(boot_sha, usb=USB, mapping=MAPPING):
    return dict(schema=1,kind='fm1-passive-post-target-boot-rom',observed_at=time.time(),
        usb_binding=usb,sg_binding=mapping,target_boot_campaign_sha256=boot_sha,
        quiet_state='initial-rom-no-later-commands-no-loader-upload')


@pytest.fixture
def prepared(tmp_path):
    tmp_path.chmod(0o700)
    frozen=tmp_path/'frozen';frozen.write_bytes(b'checked')
    c=dict(receipt_path=str(tmp_path/'receipt'),target_boot_campaign_sha256='a'*64,
        rom_snapshot_sha256='model-only')
    obj=p.Prepared(p.canonical(c),'model-only',p.canonical(snapshot('a'*64)),
        ((frozen,b'checked',100),),())
    p._AUTHORIZED.add(obj)
    return obj


class Model:
    def __init__(self,prepared, *, fault=None, binding_fault=None, close_error=None):
        self.prepared=prepared;self.fault=fault;self.binding_fault=binding_fault
        self.close_error=close_error;self.calls=[];self.closed=0;self.bindings=0

    def binding(self):
        self.bindings+=1
        snap=json.loads(self.prepared.snapshot)
        result=dict(usb_binding=snap['usb_binding'],sg_binding=snap['sg_binding'],
            fd_identity=snap['sg_binding']['node_identity'],fd_mode=stat.S_IFCHR)
        if self.binding_fault:self.binding_fault(self,result)
        return result

    def exchange(self,cdb,out,in_len):
        assert out==b'';self.calls.append((cdb,out,in_len))
        if cdb==p.INQUIRY:
            data=b'\x00'*8+b'WL82    '+b'UBOOT1.00       '+b'1.00'
        elif cdb==p.READ_STAGE:data=RAW
        else:pytest.fail('unexpected vendor request')
        reply=p.Completion(data)
        return self.fault(self,reply) if self.fault else reply

    def close(self):
        self.closed+=1
        if self.close_error:raise self.close_error


def test_fixed_codec_independent_vector_and_involution():
    assert p.decode_stage(RAW)==PLAIN and p.decode_stage(PLAIN)==RAW
    result=p.interpret_stage(PLAIN)
    assert result['classification']=='conditional-diagnostic-execution-evidence'
    assert result['fields']['raw_write']==0x02002d82
    assert not result['display_observed'] and not result['retention_verified']


@pytest.mark.parametrize('data',[b'',b'0'*31,b'0'*33,bytearray(32),None])
def test_decoder_requires_fixed_bytes(data):
    with pytest.raises(ValueError):p.decode_stage(data)
    with pytest.raises(ValueError):p.interpret_stage(data)


@pytest.mark.parametrize('index,value',[(0,0),(0,5),(0,8),(0,255),(1,-1),(1,-4),
    (2,23999999),(2,480000001),(3,0),(3,60000001),(4,0),(4,0x02002d84),
    (5,19999),(6,0),(7,1),(7,-1)])
def test_incoherent_values_never_claim_execution(index,value):
    fields=list(struct.unpack('<IiiiIIIi',PLAIN));fields[index]=value
    assert p.interpret_stage(struct.pack('<IiiiIIIi',*fields))['classification']=='inconclusive'


def test_returned_reset_stage7_requires_one():
    fields=list(struct.unpack('<IiiiIIIi',PLAIN));fields[0]=7
    assert p.interpret_stage(struct.pack('<IiiiIIIi',*fields))['classification']=='inconclusive'
    fields[7]=1
    assert p.interpret_stage(struct.pack('<IiiiIIIi',*fields))['classification']=='conditional-diagnostic-execution-evidence'


def test_one_fixed_read_durable_marker_and_receipt(prepared):
    model=Model(prepared);result=p.run_campaign(prepared,lambda _:model)
    assert model.calls==list(p.OPERATIONS) and model.closed==1 and model.bindings==5
    c=json.loads(prepared.campaign);receipt=Path(c['receipt_path'])
    assert (receipt/'raw.bin').read_bytes()==RAW and (receipt/'decoded.bin').read_bytes()==PLAIN
    assert json.loads((receipt/'result.json').read_bytes())==result
    assert (receipt.parent/('.diagnostic-stage-'+c['target_boot_campaign_sha256']+'.consumed')).read_bytes()==b'model-only'
    events=[json.loads(x) for x in (receipt/'commands.jsonl').read_text().splitlines()]
    assert [x['event'] for x in events]==['stage_probe_prepared','sg_submit_intent','sg_completion',
        'sg_submit_intent','sg_completion','stage_capture_completed']
    assert events[4]['response_sha256']==p.digest(RAW)
    # A new receipt name cannot reuse the same target-boot session.
    c['receipt_path']+='-renamed';q=p.Prepared(p.canonical(c),'model-2',prepared.snapshot,prepared.evidence,())
    p._AUTHORIZED.add(q)
    with pytest.raises(FileExistsError):p.run_campaign(q,lambda _:pytest.fail('opened transport'))


@pytest.mark.parametrize('field',['campaign','campaign_sha256','snapshot','evidence','policies'])
def test_copied_prepared_refused(prepared,field):
    q=replace(prepared,**{field:None})
    with pytest.raises(ValueError):p.run_campaign(q,lambda _:pytest.fail('transport'))
    with pytest.raises(ValueError):p.ProbeSession(q,Model(q),lambda *a,**kw:None)


@pytest.mark.parametrize('index',range(16))
def test_every_changed_cdb_byte_forbidden(prepared,index):
    model=Model(prepared);s=p.ProbeSession(prepared,model,lambda *a,**kw:None)
    s.exchange(p.INQUIRY,in_len=36)
    wrong=bytearray(p.READ_STAGE);wrong[index]^=1
    with pytest.raises(ValueError):s.exchange(bytes(wrong),in_len=32)
    assert model.calls==[p.OPERATIONS[0]] and s.failed and model.closed==1
    with pytest.raises(ValueError):s.exchange(p.READ_STAGE,in_len=32)


@pytest.mark.parametrize('cdb,out,n',[(p.READ_STAGE,b'',36),(p.READ_STAGE,b'x',32),
    (p.READ_STAGE,b'',31),(p.READ_STAGE,b'',True),(bytes.fromhex('fc12')+b'\xff'*14,b'',32),
    (bytes.fromhex('fb06')+b'\xff'*14,b'0'*512,0),(p.INQUIRY,b'',32),
    (bytearray(p.INQUIRY),b'',36)])
def test_wrong_order_lengths_data_commands_fail_before_exchange(prepared,cdb,out,n):
    model=Model(prepared);s=p.ProbeSession(prepared,model,lambda *a,**kw:None)
    with pytest.raises(ValueError):s.exchange(cdb,out,n)
    assert model.calls==[] and model.closed==1


@pytest.mark.parametrize('field',['status','masked','msg','host','driver','resid','info','sense_len'])
@pytest.mark.parametrize('which',[1,2])
def test_sg_failure_each_field_no_retry(prepared,field,which):
    def fault(m,reply):return replace(reply,**{field:1}) if len(m.calls)==which else reply
    model=Model(prepared,fault=fault)
    with pytest.raises(OSError):p.run_campaign(prepared,lambda _:model)
    assert len(model.calls)==which and model.closed==1
    assert not (Path(json.loads(prepared.campaign)['receipt_path'])/'result.json').exists()


@pytest.mark.parametrize('fault',['short','sense','bool','ioctl','inquiry','unstructured'])
def test_invalid_completion_latches_and_closes(prepared,fault):
    def inject(m,r):
        if fault=='ioctl':raise OSError('lost reply')
        if fault=='short':return replace(r,data=r.data[:-1])
        if fault=='sense':return replace(r,sense=b'x')
        if fault=='bool':return replace(r,status=False)
        if fault=='inquiry':return replace(r,data=b'0'*36)
        return SimpleNamespace(data=r.data)
    model=Model(prepared,fault=inject)
    with pytest.raises((ValueError,OSError)):p.run_campaign(prepared,lambda _:model)
    assert len(model.calls)==1 and model.closed==1


@pytest.mark.parametrize('when',[1,2,3,4,5])
@pytest.mark.parametrize('field',['usb_binding','sg_binding','fd_identity','fd_mode'])
def test_pre_post_binding_and_fd_identity(prepared,when,field):
    def fault(m,v):
        if m.bindings==when:
            v[field]=stat.S_IFREG if field=='fd_mode' else None
    model=Model(prepared,binding_fault=fault)
    with pytest.raises((ValueError,TypeError)):p.run_campaign(prepared,lambda _:model)
    assert len(model.calls)=={1:0,2:0,3:1,4:1,5:2}[when] and model.closed==1


@pytest.mark.parametrize('fault',['stale','snapshot_stale','drift','intent','intent_drift'])
def test_window_drift_durable_intent_gate(prepared,fault):
    model=Model(prepared)
    def log(event,**fields):
        if event=='sg_submit_intent':
            if fault=='intent':raise OSError('sync failed')
            if fault=='intent_drift':prepared.evidence[0][0].write_bytes(b'changed')
    s=p.ProbeSession(prepared,model,log)
    if fault=='stale':s.started-=11
    if fault=='snapshot_stale':
        snap=json.loads(prepared.snapshot);snap['observed_at']-=121
        object.__setattr__(prepared,'snapshot',p.canonical(snap))  # Trusted Python adversary in model.
    if fault=='drift':prepared.evidence[0][0].write_bytes(b'changed')
    with pytest.raises((ValueError,OSError)):s.exchange(p.INQUIRY,in_len=36)
    assert s.failed and model.calls==[] and model.closed==1


def test_factory_to_constructor_evidence_drift_closes_transport(prepared):
    model=Model(prepared)
    def factory(_):
        prepared.evidence[0][0].write_bytes(b'changed')
        return model
    with pytest.raises(ValueError):p.run_campaign(prepared,factory)
    assert model.calls==[] and model.closed==1


@pytest.mark.parametrize('error',[OSError('close failed'),KeyboardInterrupt()])
def test_close_failure_after_capture_prevents_success(prepared,error):
    model=Model(prepared,close_error=error)
    with pytest.raises(type(error)):p.run_campaign(prepared,lambda _:model)
    assert model.calls==list(p.OPERATIONS) and model.closed==1
    assert not (Path(json.loads(prepared.campaign)['receipt_path'])/'result.json').exists()


@pytest.mark.parametrize('fault',['marker_sync','intent_sync','publication_link','final_sync'])
def test_durability_failure_prevents_result(prepared,monkeypatch,fault):
    model=Model(prepared);original=p.sync_dir;calls=[]
    def sync(path):
        calls.append(str(path))
        if fault=='marker_sync' and len(calls)==2:raise OSError('marker parent fsync')
        if fault=='intent_sync' and len(calls)==4:raise OSError('intent fsync')
        if fault=='final_sync' and (Path(path)/'result.json').exists():raise OSError('result fsync')
        original(path)
    monkeypatch.setattr(p,'sync_dir',sync)
    if fault=='publication_link':monkeypatch.setattr(p.os,'link',lambda *a,**kw:(_ for _ in ()).throw(OSError('link failed')))
    with pytest.raises(OSError):p.run_campaign(prepared,lambda _:model)
    assert not (Path(json.loads(prepared.campaign)['receipt_path'])/'result.json').exists()
    assert len(model.calls)==(2 if fault in ('publication_link','final_sync') else 0)


@pytest.mark.parametrize('fault',['symlink','fifo','oversized','relative'])
def test_bounded_input_file(fault,tmp_path):
    path=tmp_path/'evidence';path.write_bytes(b'x')
    if fault=='symlink':
        link=tmp_path/'link';link.symlink_to(path);path=link
    if fault=='fifo':path.unlink();os.mkfifo(path)
    if fault=='oversized':path.write_bytes(b'x'*101)
    if fault=='relative':path=Path('relative')
    with pytest.raises((ValueError,OSError)):p.read_file(path,100)


def boot_events(c,boot_sha,manifest_sha):
    now=time.time()
    events=[dict(event='target_reset_prepared',campaign_sha256=boot_sha,
        install_campaign_sha256=c['install_campaign_sha256'],install_commands_sha256=c['install_commands_sha256'],
        target_sha256=p.TARGET_SHA,target_boot_authorization='exact-sdk-display-diagnostic',
        backup_manifest_sha256=manifest_sha,adapter_sha256=p.TARGET_RESET_SHA,commands=1,
        flash_operations=0,upload_operations=0,kernel_exclusivity=False,boot_observed=False,
        display_observed=False,physical_recovery_verified=False),
        dict(event='reset_submit_intent',phase='installed-fixed-loader',cdb='fc0c00000001ffffffffffffffffffff',
            in_len=16,out_len=0,retry=False,boot_observed=False),
        dict(event='reset_sg_completion',status=0,masked=0,msg=0,host=0,driver=0,resid=0,info=0,
            sense_len=0,sense_hex='',retry=False,boot_observed=False),
        dict(event='reset_request_completed',request_completion=True,core_reset_observed=False,
            boot_observed=False,retry=False,display_observed=False,physical_recovery_verified=False)]
    return [dict(time=now,event=e.pop('event'),**e) for e in events]


@pytest.fixture
def boot_model(tmp_path):
    c=dict(install_campaign_sha256='install-sha',install_commands_sha256='commands-sha')
    events=boot_events(c,'boot-sha','manifest-sha')
    return events,c


@pytest.mark.parametrize('fault',['order','extra','missing','bool_status','status','sense','cdb',
    'out_len','in_len','claim','target','future','nan','early'])
def test_exact_boot_transcript_rejects_drift(boot_model,fault):
    events,c=copy.deepcopy(boot_model)
    if fault=='order':events.reverse()
    elif fault=='extra':events.append(events[-1])
    elif fault=='missing':events.pop()
    elif fault=='bool_status':events[2]['status']=False
    elif fault=='status':events[2]['status']=1
    elif fault=='sense':events[2]['sense_len']=1
    elif fault=='cdb':events[1]['cdb']='00'*16
    elif fault in ('out_len','in_len'):events[1][fault]=1
    elif fault=='claim':events[-1]['boot_observed']=True
    elif fault=='target':events[0]['target_sha256']=rehearsal.BASELINE_SHA
    elif fault=='future':events[-1]['time']=time.time()+10
    elif fault=='nan':events[-1]['time']=float('nan')
    elif fault=='early':events[0]['time']=0
    raw=b'\n'.join(json.dumps(x).encode() for x in events)
    with pytest.raises(ValueError):p.verify_boot(raw,c,'boot-sha','manifest-sha',1)


def test_actual_private_elf_install_boot_receipt_probe_factory_and_capture(actual,monkeypatch,tmp_path):
    """Real private native/backup/transaction gates; reset and SG are modeled."""
    install_path=tmp_path/'install.json';envelope(install_path,actual.path,actual.config['receipt_path'])
    accepted=install.prepare_campaign(install_path)
    model=SGModel(monkeypatch,json.loads(accepted.mapping),actual.baseline)
    monkeypatch.setattr(accepted.bridge,'discover_sg',model.discover)
    install.run_campaign(accepted)
    assert bytes(model.flash)==actual.target
    bc=target_config(actual,install_path);bc['receipt_path']=str(Path(actual.config['receipt_path']).parent/'modeled-target-boot')
    boot_path=tmp_path/'boot.json';boot_path.write_bytes(p.canonical(bc))
    # Incumbent factory validates actual install before modeled target boot.
    target_prepared=target_reset.prepare_campaign(boot_path)
    boot_sha=p.digest(boot_path.read_bytes());parent=Path(bc['receipt_path']).parent
    receipt=Path(bc['receipt_path']);receipt.mkdir(mode=0o700)
    (parent/'.target-core-reset.consumed').write_text(boot_sha)
    events=boot_events(bc,boot_sha,target_prepared.backup_manifest_sha256)
    commands=receipt/'commands.jsonl';commands.write_bytes(b'\n'.join(p.canonical(e) for e in events))
    oldusb=bc['usb_binding'];usb=dict(oldusb,devnum=str(int(oldusb['devnum'])+1))
    mapping=copy.deepcopy(bc['sg_binding']);mapping['usb_identity'][1]+=1;mapping['node_identity'][1]+=1
    sp=tmp_path/'rom-snapshot.json';sp.write_bytes(p.canonical(snapshot(boot_sha,usb,mapping)))
    config=dict(schema=1,kind='fm1-exact-diagnostic-stage-probe',adapter_sha256=p.digest(Path(p.__file__).read_bytes()),
        target_boot_campaign_path=str(boot_path),target_boot_campaign_sha256=boot_sha,
        target_boot_commands_sha256=p.digest(commands.read_bytes()),target_boot_exit_status=0,
        rom_snapshot_path=str(sp),rom_snapshot_sha256=p.digest(sp.read_bytes()),
        active_session_state='post-target-boot-rom-no-later-commands-no-loader-upload',receipt_path=str(parent/'modeled-stage-probe'))
    path=tmp_path/'probe.json';path.write_bytes(p.canonical(config))
    obj=p.prepare_campaign(path)
    # Caller-selected receipts are strict; semantic changes cannot be rescued
    # by merely recomputing the outer JSON/file hashes.
    for key,value in [('schema',True),('kind','arbitrary-ram'),('target_boot_exit_status',False),
        ('active_session_state','loader-uploaded'),('receipt_path',str(tmp_path/'wrong-parent'))]:
        bad=dict(config);bad[key]=value;path.write_bytes(p.canonical(bad))
        with pytest.raises(ValueError):p.prepare_campaign(path)
    path.write_bytes(p.canonical(config))
    original=sp.read_bytes()
    for key,value in [('observed_at',time.time()-121),('quiet_state','loader-uploaded'),
        ('usb_binding',oldusb),('sg_binding',bc['sg_binding']),('schema',True)]:
        bad=json.loads(original);bad[key]=value;sp.write_bytes(p.canonical(bad))
        altered=dict(config,rom_snapshot_sha256=p.digest(sp.read_bytes()));path.write_bytes(p.canonical(altered))
        with pytest.raises(ValueError):p.prepare_campaign(path)
    sp.write_bytes(original);path.write_bytes(p.canonical(config))
    obj.check();transport=Model(obj);result=p.run_campaign(obj,lambda _:transport)
    assert result['classification']=='conditional-diagnostic-execution-evidence'
    assert transport.calls==list(p.OPERATIONS) and bytes(model.flash)==actual.target
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
        (out/'stage-probe-modeled-result.json').write_bytes(p.canonical(result))
        (out/'stage-probe-modeled-summary.json').write_bytes(p.canonical(dict(
            actual_private_native_inputs=True,app_sha256=p.APP_SHA,elf_sha256=p.ELF_SHA,
            target_sha256=p.TARGET_SHA,boot_receipt_modeled=True,sg_mocked=True,
            hardware_access=False,commands=[x[0].hex() for x in transport.calls])))
