"""MIT. Modeled exact trace-read protocol/prefix evidence, no physical access."""
import copy
import json
import struct

import pytest
from tools import fm1_sdk_trace_read_wire as w

USB = dict(busnum='1', devnum='4', path='1-2')
MAPPING = dict(node_identity=[1,2,3])


def events(rows):
    return b'\n'.join(w.canonical(row) for row in rows)


def native_fixture(count=5):
    outer = [dict(time=1,event='read_prepared')]
    native = [dict(time=2,event='native_open_intent',advisory_lock=True,commands=5),
              dict(time=3,event='native_opened',fd_identity=[1,2,3])]
    for i,(cdb,size) in enumerate(w.OPERATIONS[:count]):
        outer.append(dict(time=4+3*i,event='submit_intent',index=i,cdb=cdb.hex(),in_len=size,out_len=0,retry=False))
        native.append(dict(time=5+3*i,event='native_ioctl_intent',index=i,cdb=cdb.hex(),in_len=size,out_len=0,retry=False))
        outer.append(dict(time=6+3*i,event='completion',index=i))
    outer.append(dict(time=30,event='coherent_capture_completed' if count == 5 else 'capture_stopped_ambiguous'))
    return native,outer


def native_check(native,outer,outcome='completed'):
    return w.verify_native_receipt(events(native),events(outer),MAPPING,outcome=outcome)


def test_native_exact_five_has_bounded_claims():
    n,o=native_fixture()
    r=native_check(n,o)
    assert r['ioctl_intents']==5 and r['opened'] and not r['native_completion_proven']


@pytest.mark.parametrize('count',range(5))
def test_native_stopped_prefix(count):
    n,o=native_fixture(count)
    assert native_check(n,o,'stopped-ambiguous')['ioctl_intents']==count


@pytest.mark.parametrize('fault',['index','cdb','in_len','retry','before-intent','after-completion',
    'fd','double-open','unknown-event','successful-close','bool-time','future-close',
    'without-outer','missing-native','missing-open','extra-ioctl'])
def test_native_adversarial_exact_source_grammar(fault):
    n,o=native_fixture()
    if fault in ('index','cdb','in_len','retry'):
        n[2][fault]={'index':True,'cdb':'fc12','in_len':4,'retry':True}[fault]
    elif fault=='before-intent':n[2]['time']=3.5
    elif fault=='after-completion':n[2]['time']=6.5
    elif fault=='fd':n[1]['fd_identity']=[4,5,6]
    elif fault=='double-open':n.insert(2,copy.deepcopy(n[1]))
    elif fault=='unknown-event':n[1]['event']='native_retry'
    elif fault=='successful-close':n.append(dict(time=25,event='native_closed'))
    elif fault=='bool-time':n[0]['time']=True
    elif fault=='future-close':n.append(dict(time=31,event='native_close_failed',error='OSError',errno=5))
    elif fault=='without-outer':o.pop(1)
    elif fault=='missing-native':n=[]
    elif fault=='missing-open':n.pop(1)
    else:n.append(dict(n[-1],time=25,index=5))
    with pytest.raises(ValueError):native_check(n,o)


@pytest.mark.parametrize('event', ['native_ioctl_exception','native_binding_failed','native_close_failed'])
def test_native_failure_requires_stopped_outcome_and_no_later_ioctl(event):
    n,o=native_fixture(1)
    fields=dict(time=7,event=event,error='OSError')
    if event!='native_binding_failed':fields['errno']=5
    if event=='native_ioctl_exception':
        fields.update(index=0,completion_valid=False,retry=False);o.pop(2)
    n.append(fields)
    assert native_check(n,o,'stopped-ambiguous')['native_failure_recorded']
    with pytest.raises(ValueError):native_check(n,o)
    cdb,size=w.OPERATIONS[1]
    n.append(dict(time=9,event='native_ioctl_intent',index=1,cdb=cdb.hex(),in_len=size,out_len=0,retry=False))
    with pytest.raises(ValueError):native_check(n,o,'stopped-ambiguous')


def test_native_consumed_pretransport_empty_only():
    raw=b''
    assert w.verify_native_receipt(raw,b'',MAPPING,outcome='consumed-pretransport-zero-cbw')['ioctl_intents']==0
    with pytest.raises(ValueError):w.verify_native_receipt(raw,b'{}',MAPPING,outcome='consumed-pretransport-zero-cbw')


def capture(count=5, standards=False):
    rows=[];token=clock=0;tag=0
    inquiry=bytearray(36);inquiry[8:16]=b'WL82    ';inquiry[16:32]=b'UBOOT1.00       '
    replies={0:bytes(inquiry),1:b'a'*64,2:b'b'*4,3:b'a'*64,4:b'b'*4}
    def transfer(direction,length,data=b''):
        nonlocal token,clock
        token+=1
        rows.append(f'{token:x} {clock} S {direction}:1:004:1 -115 {length}'+(' = '+data.hex() if direction=='Bo' else ' <'))
        rows.append(f'{token:x} {clock+1} C {direction}:1:004:1 0 {length}'+(' = '+data[:32].hex() if direction=='Bi' else ' >'))
        clock+=2
    def command(cdb,size,reply=b'',status=0):
        nonlocal tag
        tag+=1;vendor=len(cdb)==16 and cdb[:2]==b'\xfd\x07'
        padded=cdb if len(cdb)==16 else cdb+bytes(10)
        cbw=b'USBC'+struct.pack('<II',tag,size)+bytes((128 if size else 0,0,16 if vendor else 6))+padded
        transfer('Bo',31,cbw)
        if size:transfer('Bi',size,reply)
        transfer('Bi',13,b'USBS'+struct.pack('<II',tag,0)+bytes([status]))
    if standards:
        command(w.TUR,0,status=1);command(w.SENSE,18,w.NOT_READY)
        command(w.PREVENT,0,status=1);command(w.SENSE,18,w.ILLEGAL_FIELD)
    for i,(cdb,size) in enumerate(w.OPERATIONS[:count]):command(cdb,size,replies[i])
    return rows,replies


def wire_check(rows,**kwargs):
    return w.verify_read_wire(('\n'.join(rows)+'\n').encode(),USB,**kwargs)


@pytest.mark.parametrize('standards',[False,True])
def test_exact_five_wire_prefixes_and_claims(standards):
    rows,replies=capture(standards=standards)
    r=wire_check(rows,ioctl_intents=5,outcome='completed',raw_replies=replies)
    assert r['fd07_requests']==4 and not r['terminal_transfer_ambiguous']
    assert not any(r[k] for k in ('full_trace_bytes_verified','process_origin_verified',
        'cpu_boot_observed','reset_cause_proven','returned_proof_granted'))


@pytest.mark.parametrize('end',range(1,30))
def test_each_terminal_transfer_prefix_is_bounded_ambiguity(end):
    rows,_=capture()
    # Native intent count is the command whose current transfer can be partial.
    count=(end-1)//6+1
    result=wire_check(rows[:end],ioctl_intents=count,outcome='stopped-ambiguous')
    assert result['fd07_requests']<=max(0,count-1)
    with pytest.raises(ValueError):wire_check(rows[:end],ioctl_intents=count,outcome='completed')


@pytest.mark.parametrize('byte,value',[(8,0),(12,0),(13,1),(14,6),(17,0),(20,0)])
def test_vendor_cbw_geometry_address_closed(byte,value):
    rows,_=capture();head,data=rows[6].split(' = ');cbw=bytearray.fromhex(data);cbw[byte]=value
    rows[6]=head+' = '+cbw.hex()
    with pytest.raises(ValueError):wire_check(rows,ioctl_intents=5,outcome='completed')


@pytest.mark.parametrize('fault',['endpoint','token','action','submit-status','length','display-length',
    'csw-tag','csw-residue','csw-status','extra-vendor','reordered','outpayload','inquiry',
    'unknown-standard','unknown-marker','timestamp','raw-prefix','no-native-intent'])
def test_wire_adversarial_geometry_and_inventory(fault):
    rows,replies=capture()
    if fault=='endpoint':rows[6]=rows[6].replace(':1 ',':2 ')
    elif fault=='token':rows[7]='other '+rows[7].split(' ',1)[1]
    elif fault=='action':rows[6]=rows[6].replace(' S ',' E ')
    elif fault=='submit-status':rows[6]=rows[6].replace('-115','0')
    elif fault=='length':rows[9]=rows[9].replace(' 0 64 ',' 0 63 ')
    elif fault=='display-length':rows[9]=rows[9][:-2]
    elif fault.startswith('csw-'):
        head,data=rows[11].split(' = ');v=bytearray.fromhex(data)
        v[{'csw-tag':4,'csw-residue':8,'csw-status':12}[fault]]=9;rows[11]=head+' = '+v.hex()
    elif fault=='extra-vendor':rows.extend(rows[6:12])
    elif fault=='reordered':rows[6:12],rows[12:18]=rows[12:18],rows[6:12]
    elif fault=='outpayload':rows[8]=rows[8].replace('Bi:','Bo:')
    elif fault=='inquiry':rows[3]=rows[3].replace('574c3832','574c3833')
    elif fault=='unknown-standard':rows[0]=rows[0].replace('120000002400','fc1200002400')
    elif fault=='unknown-marker':rows[8]=rows[8].replace(' <',' >')
    elif fault=='timestamp':rows[6]=rows[6].replace(' 6 S ',' -1 S ')
    elif fault=='raw-prefix':replies[1]=b'x'*64
    else:
        with pytest.raises(ValueError):wire_check(rows,ioctl_intents=4,outcome='completed')
        return
    with pytest.raises(ValueError):wire_check(rows,ioctl_intents=5,outcome='completed',raw_replies=replies)


@pytest.mark.parametrize('count',range(6))
def test_zero_capture_and_missing_completed_inventory(count):
    rows,_=capture(count)
    if count==0:
        assert wire_check([],ioctl_intents=0,outcome='consumed-pretransport-zero-cbw')['fd07_requests']==0
    else:
        with pytest.raises(ValueError):wire_check(rows,ioctl_intents=0,outcome='consumed-pretransport-zero-cbw')
    if count<5:
        with pytest.raises(ValueError):wire_check(rows,ioctl_intents=5,outcome='completed')


@pytest.mark.parametrize('value',[True,-1,6,None])
def test_unreplayed_native_prefix_cannot_claim_wire(value):
    rows,_=capture()
    with pytest.raises(ValueError):wire_check(rows,ioctl_intents=value,outcome='completed')


@pytest.mark.parametrize('fault', ['initial-map','open','lock','regular-fd','changed-fd'])
def test_actual_native_constructor_durable_failure_grammar(tmp_path,monkeypatch,fault):
    """Actual frozen constructor/journal; fabricated permit, only syscalls modelled.

    binding closes the journal before the constructor catches its error. The
    attempted later open_failed log is suppressed, not durable evidence.
    """
    import hashlib
    import os
    from pathlib import Path
    import stat
    import time
    from types import SimpleNamespace
    from tools import fm1_sdk_trace_sg as n
    assert hashlib.sha256(Path(n.__file__).read_bytes()).hexdigest()==\
        'ac63fed2919f97649a508a5c3ae14760b330841451b2f78b5714daf1be92b9c6'
    mapping=dict(node='/dev/sg-test-only',node_identity=[1,2,3])
    read=SimpleNamespace(snapshot=json.dumps(dict(usb_binding=USB,sg_binding=mapping)).encode(),
        receipt=tmp_path,plan=SimpleNamespace(operations=n.OPERATIONS),check=lambda:None)
    bridge=SimpleNamespace(discover_sg=lambda usb: dict(mapping,node_identity=[9,9,9])
        if fault=='initial-map' else mapping)
    prepared=n.Prepared(b'{}',read,None,bridge,None,())
    n._AUTHORIZED.add(prepared)
    permit=n._OpenPermit(prepared);n._OPENING.add(permit)
    real_open,real_close,real_fstat=n.os.open,n.os.close,n.os.fstat
    closed=[];fd=88888
    def opened(path,flags,*args):
        if str(path)==mapping['node']:
            if fault=='open':raise OSError(13,'modeled open')
            return fd
        return real_open(path,flags,*args)
    def close(actual):
        if actual==fd:closed.append(actual)
        else:real_close(actual)
    def fstat(actual):
        if actual!=fd:return real_fstat(actual)
        return SimpleNamespace(st_mode=stat.S_IFREG if fault=='regular-fd' else stat.S_IFCHR,
            st_dev=1,st_ino=9 if fault=='changed-fd' else 2,st_rdev=3)
    def lock(actual,flags):
        assert actual==fd
        if fault=='lock':raise BlockingIOError(11,'modeled lock')
    monkeypatch.setattr(n.sys,'platform','linux')
    monkeypatch.setattr(n.os,'open',opened);monkeypatch.setattr(n.os,'close',close)
    monkeypatch.setattr(n.os,'fstat',fstat);monkeypatch.setattr(n.fcntl,'flock',lock)
    def ioctl(*args):raise AssertionError('Constructor failure must issue zero ioctl')
    monkeypatch.setattr(n.fcntl,'ioctl',ioctl)
    started=time.time()
    with pytest.raises((ValueError,OSError)):n.NativeSG(prepared,permit)
    raw=(tmp_path/'native.jsonl').read_bytes();native_rows=[json.loads(l) for l in raw.splitlines()]
    terminal='native_binding_failed' if fault in ('regular-fd','changed-fd') else 'native_open_failed'
    assert [r['event'] for r in native_rows]==['native_open_intent',terminal]
    assert closed==([] if fault in ('initial-map','open') else [fd])
    outer=events([dict(time=started,event='read_prepared'),
        dict(time=time.time(),event='capture_stopped_ambiguous')])
    result=w.verify_native_receipt(raw,outer,mapping,outcome='stopped-ambiguous')
    assert result['ioctl_intents']==0 and result['native_failure_recorded']
    assert not result['opened'] and not result['native_completion_proven']
    with pytest.raises(ValueError):w.verify_native_receipt(raw,outer,mapping,outcome='completed')
