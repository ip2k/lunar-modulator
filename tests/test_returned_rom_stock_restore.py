"""MIT. Injected new-binding restore gate tests; no device access."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import fm1_returned_rom_stock_restore as r
import fm1_sdk_rehearsal as rehearsal
import fm1_fixed_loader_backup as b
import fm1_uboot_read as reader
from test_fixed_loader_backup import mock_sg, USB


@pytest.fixture
def prepared(tmp_path):
    tmp_path.chmod(0o700)
    target=b''.join(bytes([i%256])*256 for i in range(4096))
    baseline=bytes([0xA5])*1048576
    journal=dict(state='running',direction='restore',intent=dict(operation='erase',address=0x4000))
    original=SimpleNamespace(directory=tmp_path,direction='restore',
        plan_bytes=r.canonical(dict(identity=dict(identity='FM-1_092'))),
        baseline=baseline,target=target,sectors=(0x4000,),receipt_bytes=b'{}',check_files=lambda:dict(journal))
    binding=dict(usb_binding=USB,returned_backup_manifest_sha256='m',returned_backup_campaign_sha256='c')
    policy=r.Policy(original,r.canonical(binding),(),None);r._POLICIES.add(policy)
    config=dict(receipt_path=str(tmp_path/'restore'),adapter_sha256=r.digest(Path(r.__file__).read_bytes()),
        returned_backup_campaign_sha256='c',returned_backup_manifest_sha256='m')
    mapping=dict(node='/dev/sgMOCK',node_identity=[1,2,3],usb_identity=[4,5,6])
    p=r.Prepared(r.canonical(config),'model-restore',(policy,),r.canonical(mapping),b,reader.SGHeader,
        rehearsal,b'{"state":"complete","direction":"install"}',tmp_path)
    r._AUTHORIZED.add(p)
    return p,journal


@pytest.mark.parametrize('field',['config','campaign_sha256','policies','mapping','bridge',
    'header_type','rehearsal','initial_journal','parent'])
def test_copied_factory_authority_rejected(prepared,monkeypatch,field):
    p,_=prepared;other=replace(p,**{field:getattr(p,field)})
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('device discovery'))
    with pytest.raises(ValueError):r.transport_type(other)
    with pytest.raises(ValueError):r.run_campaign(other)


def test_copied_policy_rejected(prepared):
    p,_=prepared;copy=replace(p.policies[0])
    with pytest.raises(ValueError):copy.check_files()
    with pytest.raises(ValueError):copy.bind(None)


def test_unfrozen_dependency_fails_without_open(tmp_path,monkeypatch):
    path=tmp_path/'campaign.json';path.write_text('{}')
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('device discovery'))
    with pytest.raises(ValueError):r.prepare_campaign(path)
    with pytest.raises(ValueError):r.load_source(Path(r.__file__).absolute(),None,'unfrozen')


def read_page(sg,address):
    return sg.exchange((b'\xfd\x05'+address.to_bytes(4,'big')+b'\x01\x00').ljust(16,b'\xff'),b'',256)


@pytest.mark.parametrize('position',[0,1,2048,4095])
def test_no_erase_until_every_exact_target_page(prepared,monkeypatch,position):
    p,_=prepared;state=mock_sg(monkeypatch);sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    for index in range(position):assert read_page(sg,index*256)==p.policies[0].target[index*256:index*256+256]
    with pytest.raises(ValueError,match='No mutation'):
        sg.exchange(b'\xfb\x01\x00\x00\x40\x00'+b'\xff'*10,b'',16)
    assert sg.failed and sg.fd is None and len(state.calls)==position
    assert not any(int.from_bytes(c[:2],'big') in (0xFB01,0xFB04) for c in state.calls)


@pytest.mark.parametrize('position',[0,4095])
def test_wrong_target_page_latches_before_writes(prepared,monkeypatch,position):
    p,_=prepared
    def corrupt(h,data,op,state):
        if op==0xFD05 and len(state.calls)==position+1:data[0]^=1
    state=mock_sg(monkeypatch,fault=corrupt);sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    for index in range(position):read_page(sg,index*256)
    with pytest.raises(ValueError,match='Initial actual NOR'):read_page(sg,position*256)
    with pytest.raises(ValueError):read_page(sg,position*256)
    assert sg.failed and sg.fd is None and not sg.initial_verified and len(state.calls)==position+1


def test_initial_order_requires_full_nonoverlapping_pages(prepared,monkeypatch):
    p,_=prepared;state=mock_sg(monkeypatch);sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    with pytest.raises(ValueError,match='ordered'):read_page(sg,256)
    assert not state.calls and sg.failed


def test_initial_full_target_gate_then_exact_restore_wire(prepared,monkeypatch):
    p,journal=prepared;state=mock_sg(monkeypatch);sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    for index in range(4096):read_page(sg,index*256)
    assert sg.initial_verified and sg.initial_pages==4096
    sg.exchange(b'\xfb\x01\x00\x00\x40\x00'+b'\xff'*10,b'',16)
    assert len(state.calls)==4097
    journal['intent']=dict(operation='program',address=0x4000)
    payload=p.policies[0].baseline[0x4000:0x4100]
    import binascii
    cdb=(b'\xfb\x04\x00\x00\x40\x00\x01\x00\x00'+binascii.crc_hqx(payload,0).to_bytes(2,'little')).ljust(16,b'\xff')
    sg.exchange(cdb,payload,0)
    assert len(state.calls)==4098
    sg.close()


@pytest.fixture(scope='module')
def restore_transcript():
    """Independent modeled durable wire transcript, with no SG/open/syscalls."""
    import fm1_fixed_target_reset as replay
    baseline=b'\xa5'*1048576
    target=bytearray(baseline)
    order=list(range(0x5000,0x22000,4096))+[0x4000]
    for address in order:target[address:address+4096]=b'\x5a'*4096
    target=bytes(target);rows=[];index=0
    c=dict(adapter_sha256='adapter',returned_backup_campaign_sha256='backup',
        returned_backup_manifest_sha256='manifest',install_journal_sha256='journal')
    mapping=dict(node='/dev/sgMODELED')
    def event(name,**fields):rows.append(dict(time=1+len(rows)*0.001,event=name,**fields))
    def command(op,address=0,payload=b'',response=None):
        nonlocal index
        cdb,payload,size=replay.wire(op,address,payload)
        event('sg_submit_intent',index=index,direction='restore',cdb=cdb.hex(),
            out_len=len(payload),in_len=size,payload_sha256=r.digest(payload) if payload else None,retry=False)
        event('sg_completion',index=index,direction='restore',status=0,masked=0,msg=0,
            host=0,driver=0,resid=0,info=0,sense_len=0,sense_hex='',retry=False,
            response_sha256=r.digest(response if response is not None else b'\x00'*size) if size else None)
        index+=1
    def read(image,address,size):
        for page in range(address,address+size,256):command(0xFD05,page,response=image[page:page+256])
    event('returned_restore_prepared',campaign_sha256='campaign',**c,sg_binding=mapping,
        initial_journal_sha256=c['install_journal_sha256'],target_sha256=r.digest(target),
        baseline_sha256=r.digest(baseline),direction='restore',boot_observed=False,
        physical_recovery_verified=False,kernel_exclusivity=False)
    # Prepared header names the journal only once under its emitted field.
    rows[0].pop('install_journal_sha256')
    command(0xFC0A);read(target,0,1048576);current=target
    for address in order:
        read(current,address,4096)
        event('durable_intent',operation='erase',address=address)
        command(0xFC0A);command(0xFB01,address)
        event('operation_returned',operation='erase',address=address)
        blank=current[:address]+b'\xff'*4096+current[address+4096:]
        read(blank,address,4096)
        for page in range(address,address+4096,256):
            event('durable_intent',operation='program',address=page)
            command(0xFC0A);command(0xFB04,page,baseline[page:page+256])
            event('operation_returned',operation='program',address=page)
        current=current[:address]+baseline[address:address+4096]+current[address+4096:]
        read(current,address,4096);event('sector_verified',address=address)
    read(baseline,0,1048576)
    result=dict(campaign_sha256='campaign',direction='restore',initial_full_target_readback_verified=True,
        verified_sha256=r.digest(baseline),full_flash_readback_verified=True,sectors_written=30,
        stock_baseline_restored=True,boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
    event('returned_restore_completed',**result)
    return rows,result,c,mapping,baseline,target,order,replay.Replay


def check_transcript(fixture,monkeypatch,rows=None,result=None):
    original,expected,c,mapping,baseline,target,order,replay=fixture
    monkeypatch.setattr(r,'BASELINE_SHA',r.digest(baseline));monkeypatch.setattr(r,'TARGET_SHA',r.digest(target))
    raw=b'\n'.join(r.canonical(row) for row in (original if rows is None else rows))+b'\n'
    return r.verify_restore_receipt(raw,expected if result is None else result,c,'campaign',mapping,
        baseline,target,order,replay)


def test_complete_restore_receipt_proves_initial_target_and_final_stock(restore_transcript,monkeypatch):
    start,end=check_transcript(restore_transcript,monkeypatch)
    assert start==1 and end>start


@pytest.mark.parametrize('fault',['missing','extra','reorder','initial-page','final-page','status',
    'sense','residue','retry','erase-address','program-payload','program-crc','intent-address',
    'sector-order','direction','index','future','nonfinite','stopped','boot-claim','result-only',
    'partial-target','partial-stock'])
def test_restore_receipt_rejects_corrupt_or_incomplete_evidence(restore_transcript,monkeypatch,fault):
    import copy,time
    rows,result,c,mapping,baseline,target,order,replay=restore_transcript
    rows=copy.deepcopy(rows);result=copy.deepcopy(result)
    intents=[i for i,e in enumerate(rows) if e['event']=='sg_submit_intent']
    reads=[i for i in intents if rows[i]['cdb'].startswith('fd05')]
    erase=next(i for i in intents if rows[i]['cdb'].startswith('fb01'))
    program=next(i for i in intents if rows[i]['cdb'].startswith('fb04'))
    durable=next(i for i,e in enumerate(rows) if e['event']=='durable_intent')
    if fault=='missing':rows.pop(3)
    elif fault=='extra':rows.insert(4,copy.deepcopy(rows[3]))
    elif fault=='reorder':rows[3],rows[4]=rows[4],rows[3]
    elif fault=='initial-page':rows[reads[0]+1]['response_sha256']='0'*64
    elif fault=='final-page':rows[reads[-1]+1]['response_sha256']='0'*64
    elif fault in ('status','sense','residue'):
        rows[3+1][dict(status='status',sense='sense_len',residue='resid')[fault]]=1
    elif fault=='retry':rows[erase]['retry']=True
    elif fault=='erase-address':rows[erase]['cdb']=(b'\xfb\x01'+b'\x00'*4+b'\xff'*10).hex()
    elif fault=='program-payload':rows[program]['payload_sha256']='0'*64
    elif fault=='program-crc':rows[program]['cdb']=rows[program]['cdb'][:18]+'0000'+rows[program]['cdb'][22:]
    elif fault=='intent-address':rows[durable]['address']=0
    elif fault=='sector-order':next(e for e in rows if e['event']=='sector_verified')['address']=0x4000
    elif fault=='direction':rows[erase]['direction']='install'
    elif fault=='index':rows[program]['index']+=1
    elif fault=='future':rows[-1]['time']=time.time()+1
    elif fault=='nonfinite':rows[0]['time']=float('nan')
    elif fault=='stopped':rows.append(dict(time=rows[-1]['time'],event='returned_restore_stopped_ambiguous'))
    elif fault=='boot-claim':rows[-1]['boot_observed']=True
    elif fault=='result-only':result['stock_baseline_restored']=False
    elif fault=='partial-target':restore_transcript=(*restore_transcript[:5],target[:-1],*restore_transcript[6:])
    elif fault=='partial-stock':restore_transcript=(*restore_transcript[:4],baseline[:-1],*restore_transcript[5:])
    with pytest.raises(ValueError):check_transcript(restore_transcript,monkeypatch,rows,result)
