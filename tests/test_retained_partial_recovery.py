"""Device-free pure/source boundaries; no production authority pin substitution."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from tools import fm1_partial_nor_prefix as prefix
from tools import fm1_retained_partial_recovery as recovery


def events(*rows):
    return b''.join(json.dumps(dict(time=i+1,**row)).encode()+b'\n' for i,row in enumerate(rows))

def first(): return dict(event='prepared',source='actual-adapter-fields')
def final(): return dict(event='completed',full=True)
def stopped():return dict(event='trace_install_stopped_ambiguous',error='OSError',detail='modeled syscall',retry=False,stock_baseline_restored=False,boot_observed=False)
def replay(rows):
    return prefix.verify(events(first(),*rows,stopped()),bytes(prefix.FLASH),bytes(prefix.FLASH),direction='install',prepared_fields=first(),completed_fields=final(),stop_event='trace_install_stopped_ambiguous')

def intent(index,op,address=0,payload=b''):
    cdb,payload,size=prefix.wire(op,address,payload)
    return dict(event='sg_submit_intent',index=index,direction='install',cdb=cdb.hex(),out_len=len(payload),in_len=size,payload_sha256=prefix.digest(payload)if payload else None,retry=False)

def completion(index,response,status=0):
    return dict(event='sg_completion',index=index,direction='install',status=status,masked=0,msg=0,host=0,driver=0,resid=0,info=0,sense_len=0,sense_hex='',retry=False,response_sha256=prefix.digest(response)if response else None)


def test_reviewed_dependency_literals_and_actual_source_bytes():
    # Public source contract only; exact owned wrappers are separately sealed.
    pins = {
        'PREFIX_SHA': ('fm1_partial_nor_prefix.py', '37794ff6caf9992fb6809cdd179a858d1b500b18aa26187e4cb8888b1479f056'),
        'RESTORE_SHA': ('fm1_sdk_trace_admitted_stock_restore.py', '683275d73a846dd4c3d5edbb6695fe853832c4c7e4f7921ac9504293a8531e4e'),
        'BACKUP_SHA': ('fm1_sdk_trace_admitted_backup.py', '7e9dbf156c92e7cdcc2dcd01fbbdd19ad8e06eef9fcd8772f72870afaebf738f'),
    }
    for name, (file, pin) in pins.items():
        assert getattr(recovery, name) == pin
        assert hashlib.sha256(Path(recovery.__file__).with_name(file).read_bytes()).hexdigest() == pin
    assert recovery.INSTALL_CAPTURE_SHA == '7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b'
    assert recovery.ACQUIRE_CAPTURE_SHA == '9d69134b11552f63a245c0a6870230e47bda4e6d80006b0bd61a47b938b22c34'
    assert recovery.RESTORE_CAPTURE_SHA == 'aa640c486bd22fdf10076f6e3edfb607b3b4dbf83a93358bdbc540c5977886a8'


@pytest.mark.parametrize('factory,pin', [
    ('validate_stopped', 'PREFIX_SHA'),
    ('prepare_acquisition', 'PREFIX_SHA'),
    ('prepare_restore', 'ACQUIRE_CAPTURE_SHA'),
])
def test_missing_dependency_closes_before_io(tmp_path, monkeypatch, factory, pin):
    # Deactivation-only negative test. This never constructs or grants authority.
    monkeypatch.setattr(recovery, pin, None)
    monkeypatch.setattr(recovery, 'read_file', lambda *a, **k: pytest.fail('closed factory attempted evidence IO'))
    with pytest.raises(ValueError, match='closed|binding'):
        getattr(recovery, factory)(tmp_path/'missing.json')


def test_read_inventory_exact_no_upload_or_write():
    ops=recovery.acquisition_operations(prefix)
    assert len(ops)==8707
    assert sum(x[1][:2]==b'\xfd\x05' for x in ops)==8192
    assert sum(x[1][:2]==b'\xfc\x0a' for x in ops)==515
    assert all(not x[2] for x in ops)
    for name in ('dumpA.bin','dumpB.bin'):
        assert [int.from_bytes(x[1][2:6],'big')for x in ops if x[0]==name]==list(range(0,prefix.FLASH,256))


def test_caught_pretransport_registered_prefix():
    p=replay([])
    assert not p.requests and not p.uncertainty and not p.initial_verified
    prefix.check_dumps(p,bytes(prefix.FLASH),bytes(prefix.FLASH),bytes(prefix.FLASH))
    with pytest.raises(ValueError,match='Exact replay'):prefix.check_dumps(replace(p),bytes(prefix.FLASH),bytes(prefix.FLASH),bytes(prefix.FLASH))

@pytest.mark.parametrize('field,value',[('retry',True),('error',''),('boot_observed',True),('extra',0)])
def test_stop_envelope_rejects(field,value):
    s=stopped();s[field]=value
    with pytest.raises(ValueError):prefix.verify(events(first(),s),bytes(prefix.FLASH),bytes(prefix.FLASH),direction='install',prepared_fields=first(),completed_fields=final(),stop_event='trace_install_stopped_ambiguous')

@pytest.mark.parametrize('kind',['erase','program'])
def test_attempted_mutation_uncertain_until_matching_page(kind):
    # Cursor is a pure implementation kernel, not a production Prepared token.
    address=0x5000;op=0xFB01 if kind=='erase' else 0xFB04;payload=b'x'*256 if kind=='program' else b''
    rows=[dict(time=1,**intent(0,op,address,payload)),dict(time=2,**completion(0,b'\xfb\x01'+bytes(14)if kind=='erase'else b'')),dict(time=3,event='operation_returned',operation=kind,address=address)]
    c=prefix._Cursor(rows,b'x'*prefix.FLASH,bytes(prefix.FLASH),'install')
    c.command(op,address,payload);c.event('operation_returned',operation=kind,address=address)
    assert c.uncertainty==((address,address+(4096 if kind=='erase'else 256)),)
    c.verified_page(address)
    assert c.uncertainty==(((address+256,address+4096),)if kind=='erase'else())


def test_uncertain_union_keeps_all_pages():
    c=prefix._Cursor([],bytes(prefix.FLASH),bytes(prefix.FLASH),'install')
    c.add_uncertainty(0x5000,0x5100);c.add_uncertainty(0x5200,0x5300);c.add_uncertainty(0x5100,0x5200)
    assert c.uncertainty==((0x5000,0x5300),)
    c.verified_page(0x5100);assert c.uncertainty==((0x5000,0x5100),(0x5200,0x5300))

@pytest.mark.parametrize('address',[0,0x3000,0x22000,prefix.FLASH-256])
def test_protected_or_unexplained_partial_rejects(address):
    p=replay([]);dump=bytearray(prefix.FLASH);dump[address]=1
    with pytest.raises(ValueError):prefix.check_dumps(p,bytes(dump),bytes(dump),bytes(prefix.FLASH))


def test_second_dump_mismatch_rejects():
    p=replay([])
    with pytest.raises(ValueError):prefix.check_dumps(p,bytes(prefix.FLASH),b'X'*prefix.FLASH,bytes(prefix.FLASH))


def record(token,action,direction,length,data=b'',status=None):
    return SimpleNamespace(token=token,action=action,direction=direction,length=length,data=data,status=(-115 if action=='S'else 0)if status is None else status)
def pair(token,direction,length,data=b'',status=0):
    return [record(token,'S',direction,length,data if direction=='Bo'else b''),record(token,'C',direction,length,b''if direction=='Bo'else data,status)]
def bot(cdb,payload,size,response=b'',terminal=None):
    tag=b'\x01\x00\x00\x00';cbw=b'USBC'+tag+(len(payload)or size).to_bytes(4,'little')+bytes((0 if payload else 128,0,16))+cdb
    rows=pair('a','Bo',31,cbw)
    if terminal=='cbw':rows[-1].status=-5;rows[-1].length=0;return rows
    rows+=pair('b','Bo'if payload else'Bi',len(payload)or size,payload if payload else response)
    if terminal=='data':rows[-1].status=-5;rows[-1].length=0;rows[-1].data=b'';return rows
    rows+=pair('c','Bi',13,b'USBS'+tag+bytes(5));return rows


def test_paired_exact_online_and_page():
    online=prefix.wire(0xFC0A);page=prefix.wire(0xFD05,0)
    response=b'\xfc\x0a\x03\x00'+(0x856014).to_bytes(4,'little')+bytes(8)
    rows=bot(*online,response=response)+bot(*page,response=bytes(32))
    p=prefix.verify_wire(rows,((online[0],b'',16,None),(page[0],b'',256,bytes(256))),stopped=False)
    assert p['vendor_commands']==2 and not p['full_payload_wire_verified']

@pytest.mark.parametrize('op',[b'\xfc\x12',b'\xfc\x0c',b'\xfb\x04',b'\xfd\x07'])
def test_terminal_failed_unallowlisted_cbw_rejected(op):
    online=prefix.wire(0xFC0A)
    rows=bot((op+b'\xff'*14),b'',16,terminal='cbw')
    with pytest.raises(ValueError):prefix.verify_wire(rows,((online[0],b'',16,None),),stopped=True)

@pytest.mark.parametrize('phase',['cbw','data'])
def test_exact_terminal_transfer_preserves_uncertainty(phase):
    online=prefix.wire(0xFC0A)
    result=prefix.verify_wire(bot(*online,terminal=phase),((online[0],b'',16,None),),stopped=True)
    assert result['terminal_transfer_ambiguous']
    with pytest.raises(ValueError):prefix.verify_wire(bot(*online,terminal=phase),((online[0],b'',16,None),),stopped=False)


def test_captured_wrong_online_geometry_rejected():
    online=prefix.wire(0xFC0A)
    with pytest.raises(ValueError):prefix.verify_wire(bot(*online,response=bytes(16)),((online[0],b'',16,None),),stopped=False)

@pytest.mark.parametrize('kind',['symlink','fifo','directory','oversize'])
def test_bounded_regular_reader(tmp_path,kind):
    p=tmp_path/'input';target=tmp_path/'target';target.write_bytes(b'ok')
    if kind=='symlink':p.symlink_to(target)
    elif kind=='fifo':__import__('os').mkfifo(p)
    elif kind=='directory':p.mkdir()
    else:p.write_bytes(bytes(9))
    with pytest.raises((OSError,ValueError)):recovery.read_file(p,8)


def test_negative_artifact_appearance(tmp_path):
    f=recovery._Frozen();p=tmp_path/'unexpected';f.missing(p);p.write_bytes(b'')
    with pytest.raises(ValueError,match='appeared'):f.check(False)


def test_positive_source_drift_every_binding(tmp_path):
    f=recovery._Frozen();p=tmp_path/'source.py';p.write_bytes(b'x'*70000);f.freeze(p);p.write_bytes(b'y'*70000)
    with pytest.raises(ValueError,match='changed'):f.check(False)


def test_journal_requires_source_possible_intent():
    p=replay([]);plan={'x':1};j=dict(state='prepared',direction=None,intent=None,sector_order=list(prefix.ORDER),plan_sha256=prefix.digest(prefix.canonical(plan)))
    recovery._journal(j,p,plan,'install')
    j['intent']={'operation':'erase','address':0x5000}
    with pytest.raises(ValueError):recovery._journal(j,p,plan,'install')
