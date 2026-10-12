"""MIT. Offline transcript/SG gates; no tests access a physical device."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_fixed_rehearsal_reset as r
import fm1_fixed_loader_backup as b
from fm1_uboot_read import SGHeader
from test_fixed_loader_backup import mock_sg, USB
from test_sdk_rehearsal import actual, SGModel
import fm1_sdk_rehearsal as rehearsal


@pytest.fixture
def prepared(tmp_path):
    parent=tmp_path/'backup'; parent.mkdir(mode=0o700)
    config=dict(receipt_path=str(parent/'post-reset'), usb_binding=USB,
        sg_binding=dict(node='/dev/sgMOCK',node_identity=[1,2,3],usb_identity=[4,5,6]),
        adapter_sha256='unit-model-only',rehearsal_campaign_sha256='model-only',
        rehearsal_commands_sha256='model-only')
    evidence=tmp_path/'frozen'; evidence.write_bytes(b'checked')
    p=r.Prepared(r.canonical(config),'model-only','model-only',r.canonical(config['sg_binding']),
                 b,SGHeader,((evidence,b'checked',100),),())
    r._AUTHORIZED.add(p)
    return p


@pytest.mark.parametrize('field', ['campaign','campaign_sha256','backup_manifest_sha256',
    'expected_mapping','bridge','header_type','evidence','policies'])
def test_copied_authority_rejected_before_open(prepared, monkeypatch, field):
    p=replace(prepared,**{field:None})
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('device discovery'))
    with pytest.raises(ValueError): r.ResetSG(p,lambda *a,**kw:None)
    with pytest.raises(ValueError): r.run_campaign(p)


def test_fake_factory_object_rejected():
    fake=SimpleNamespace(check=lambda:None)
    with pytest.raises(ValueError): r.ResetSG(fake,lambda *a,**kw:None)
    with pytest.raises(ValueError): r.run_campaign(fake)


def test_one_reset_and_durable_parent_marker(prepared,monkeypatch):
    state=mock_sg(monkeypatch)
    result=r.run_campaign(prepared)
    assert state.calls==[r.reset.RESET_CDB] and state.closed==[888]
    assert result==dict(request_completion=True,core_reset_observed=False,boot_observed=False)
    config=json.loads(prepared.campaign)
    events=[json.loads(line) for line in (Path(config['receipt_path'])/'commands.jsonl').read_text().splitlines()]
    assert [e['event'] for e in events]==['post_rehearsal_reset_prepared','reset_submit_intent',
                                         'reset_sg_completion','reset_request_completed']
    assert all(e['boot_observed'] is False for e in events)
    config['receipt_path']+='-renamed'
    again=r.Prepared(r.canonical(config),'model-2','model-only',prepared.expected_mapping,
        b,SGHeader,prepared.evidence,())
    r._AUTHORIZED.add(again)
    with pytest.raises(FileExistsError): r.run_campaign(again)
    assert state.calls==[r.reset.RESET_CDB]


@pytest.mark.parametrize('fault',['status','masked','msg','host','driver','resid','info','sense_len','echo','ioctl'])
def test_reset_ambiguity_latches_without_retry(prepared,monkeypatch,fault):
    def inject(h,data,op,state):
        if fault=='ioctl': raise OSError('lost reply')
        if fault=='echo': data[:2]=b'xx'
        else: setattr(h,fault,1)
    state=mock_sg(monkeypatch,fault=inject)
    sg=r.ResetSG(prepared,lambda *a,**kw:None)
    with pytest.raises(OSError):sg.request_reset()
    with pytest.raises(ValueError):sg.request_reset()
    assert sg.consumed and sg.failed and sg.fd is None
    assert state.calls==[r.reset.RESET_CDB] and state.closed==[888]


@pytest.mark.parametrize('when',['open','pre','post','stale','drift'])
def test_live_binding_and_frozen_files(prepared,monkeypatch,when):
    threshold={'open':1,'pre':3,'post':4}.get(when)
    def binding_fault(state):
        if threshold and state.discoveries>=threshold:raise OSError('new enumeration')
    state=mock_sg(monkeypatch,binding_fault=binding_fault)
    if when=='open':
        with pytest.raises(OSError):r.ResetSG(prepared,lambda *a,**kw:None)
    else:
        sg=r.ResetSG(prepared,lambda *a,**kw:None)
        if when=='stale':sg.started-=11
        if when=='drift':prepared.evidence[0][0].write_bytes(b'changed')
        with pytest.raises((ValueError,OSError)):sg.request_reset()
        assert sg.failed and sg.fd is None
    assert len(state.calls)==(1 if when=='post' else 0)


def test_failed_intent_persistence_never_submits(prepared,monkeypatch):
    state=mock_sg(monkeypatch)
    sg=r.ResetSG(prepared,lambda *a,**kw:(_ for _ in ()).throw(OSError('sync failed')))
    with pytest.raises(OSError):sg.request_reset()
    assert sg.consumed and sg.failed and state.calls==[] and state.closed==[888]


@pytest.fixture(scope='module')
def transcript():
    baseline=b'\x66'*1048576
    target=baseline[:0x4000]+b'\x99'*8192+baseline[0x6000:]
    order=[0x5000,0x4000]
    campaign=dict(sg_binding={'model':True})
    events=[]
    def event(name,**fields):events.append(dict(time=1,event=name,**fields))
    event('rehearsal_prepared',campaign_sha256='campaign',adapter_sha256=r.REHEARSAL_SOURCE_SHA,
        source_sha256={},sg_binding=campaign['sg_binding'],kernel_exclusivity=False,
        boot_observed=False,physical_recovery_verified=False)
    directions=[];current=baseline
    for direction,desired in [('install',target),('restore',baseline)]:
        index=0
        def command(op,address=0,payload=b'',response=None):
            nonlocal index
            cdb,payload,size=r.wire(op,address,payload)
            event('sg_submit_intent',index=index,direction=direction,cdb=cdb.hex(),out_len=len(payload),
                in_len=size,payload_sha256=r.digest(payload) if payload else None,retry=False)
            event('sg_completion',index=index,direction=direction,status=0,masked=0,msg=0,host=0,
                driver=0,resid=0,info=0,sense_len=0,sense_hex='',retry=False,
                response_sha256=r.digest(response) if response is not None else 'a'*64 if size else None)
            index+=1
        def read(image,address,size):
            for page in range(address,address+size,256):
                if page==address:command(0xFC0A) # legal timer probe at read start
                command(0xFD05,page,response=image[page:page+256])
        command(0xFC0A);read(current,0,1048576)
        for address in order:
            read(current,address,4096)
            event('durable_intent',operation='erase',address=address)
            command(0xFC0A);command(0xFB01,address)
            event('operation_returned',operation='erase',address=address)
            blank=current[:address]+b'\xff'*4096+current[address+4096:]
            read(blank,address,4096)
            for page in range(address,address+4096,256):
                event('durable_intent',operation='program',address=page)
                command(0xFC0A);command(0xFB04,page,desired[page:page+256])
                event('operation_returned',operation='program',address=page)
            current=current[:address]+desired[address:address+4096]+current[address+4096:]
            read(current,address,4096);event('sector_verified',address=address)
        read(current,0,1048576)
        accepted=dict(direction=direction,verified_sha256=r.digest(desired),full_flash_readback_verified=True,
            sectors_written=2,boot_observed=False,kernel_exclusivity=False)
        event('direction_verified',**accepted);directions.append(accepted)
    event('rehearsal_completed',directions=directions,stock_baseline_restored=True,
          boot_observed=False,physical_recovery_verified=False)
    result=dict(campaign_sha256='campaign',directions=directions,stock_baseline_restored=True,
                boot_observed=False,physical_recovery_verified=False)
    return events,result,campaign,baseline,target,order


def verify(t):
    events,result,campaign,baseline,target,order=t
    raw=b'\n'.join(r.canonical(e) for e in events)
    return r.verify_rehearsal(raw,result,campaign,'campaign',{},baseline,target,order)


def test_exact_transcript_full_actual_page_hashes(transcript):
    assert verify(transcript)==1


@pytest.mark.parametrize('fault',['last_read_hash','initial_read_hash','erase_blank_hash','sector_read_hash',
    'missing_read','wrong_crc','wrong_payload','wrong_padding','wrong_response_size','missing_intent',
    'intent_address','missing_return','wrong_index','status','sense','wrong_direction','commit_order',
    'stop_after_complete','extra_reset','result_false','result_direction','nan','future','missing_completed',
    'extra_online','bool_status'])
def test_transcript_rejects_ambiguity_and_forged_success(transcript,fault):
    t=copy.deepcopy(transcript);events,result,campaign,baseline,target,order=t
    reads=[i for i,e in enumerate(events) if e.get('cdb','').startswith('fd05')]
    programs=[i for i,e in enumerate(events) if e.get('cdb','').startswith('fb04')]
    if fault.endswith('read_hash') or fault=='erase_blank_hash':
        index={'last_read_hash':reads[-1],'initial_read_hash':reads[0],
               'sector_read_hash':reads[4096+16+16],'erase_blank_hash':reads[4096+16]}[fault]
        events[index+1]['response_sha256']='0'*64
    elif fault=='missing_read':del events[reads[-1]:reads[-1]+2]
    elif fault in ('wrong_crc','wrong_padding'):
        index=programs[0];cdb=bytearray.fromhex(events[index]['cdb']);cdb[9 if fault=='wrong_crc' else 15]^=1
        events[index]['cdb']=cdb.hex()
    elif fault=='wrong_payload':events[programs[0]]['payload_sha256']='0'*64
    elif fault=='wrong_response_size':events[reads[0]]['in_len']=16
    elif fault in ('missing_intent','intent_address','missing_return'):
        kind='operation_returned' if fault=='missing_return' else 'durable_intent'
        index=next(i for i,e in enumerate(events) if e['event']==kind)
        if fault=='intent_address':events[index]['address']=0x3000
        else:del events[index]
    elif fault=='wrong_index':events[2]['index']=7
    elif fault in ('status','sense','bool_status'):
        events[2]['status' if fault!='sense' else 'sense_len']=False if fault=='bool_status' else 1
    elif fault=='wrong_direction':events[1]['direction']='restore'
    elif fault=='commit_order':order.reverse()
    elif fault in ('stop_after_complete','extra_reset','extra_online'):
        if fault=='extra_online':events[1:1]=copy.deepcopy(events[1:3])
        else:events.append(dict(time=1,event='rehearsal_stopped_ambiguous' if fault=='stop_after_complete' else 'sg_submit_intent',cdb=r.reset.RESET_CDB.hex()))
    elif fault=='result_false':result['stock_baseline_restored']=False
    elif fault=='result_direction':result['directions'].reverse()
    elif fault=='nan':events[-1]['time']=float('nan')
    elif fault=='future':events[-1]['time']=time.time()+10
    elif fault=='missing_completed':events.pop()
    with pytest.raises(ValueError):verify(t)


def post_config(actual):
    receipt=Path(actual.config['receipt_path'])
    manifest=json.loads(actual.inputs['manifest_path'].read_bytes())
    return dict(schema=1,kind='fm1-fixed-loader-post-rehearsal-stock-reset',
        adapter_sha256=r.digest(Path(r.__file__).read_bytes()),
        rehearsal_adapter_path=str(Path(rehearsal.__file__).absolute()),
        rehearsal_campaign_path=str(actual.path),rehearsal_campaign_sha256=r.digest(actual.path.read_bytes()),
        rehearsal_commands_sha256=r.digest((receipt/'commands.jsonl').read_bytes()),
        rehearsal_result_sha256=r.digest((receipt/'result.json').read_bytes()),rehearsal_exit_status=0,
        journal_sha256=r.digest((actual.inputs['directory']/'journal.json').read_bytes()),
        active_session_state='same-fixed-loader-restored-rehearsal-no-later-commands',
        usb_binding=manifest['usb_binding'],sg_binding=manifest['sg_binding'],receipt_path=str(receipt.parent/'test-post-reset'))


def test_actual_private_images_modeled_rehearsal_then_real_factory(actual,monkeypatch,tmp_path):
    p=rehearsal.prepare_campaign(actual.path)
    model=SGModel(monkeypatch,json.loads(p.mapping),actual.baseline)
    monkeypatch.setattr(p.bridge,'discover_sg',model.discover)
    rehearsal.run_campaign(p)
    config=post_config(actual);path=tmp_path/'post-campaign.json';path.write_bytes(r.canonical(config))
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('factory discovered hardware'))
    post=r.prepare_campaign(path)
    assert post.campaign_sha256==r.digest(path.read_bytes())
    assert post.backup_manifest_sha256==r.digest(actual.inputs['manifest_path'].read_bytes())
    assert not Path(config['receipt_path']).exists()
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
        (out/'post-reset-factory-accepted.json').write_bytes(r.canonical(dict(
            campaign_sha256=post.campaign_sha256,commands_sha256=config['rehearsal_commands_sha256'],
            journal_sha256=config['journal_sha256'],actual_private_inputs=True,sg_mocked=True,hardware_access=False)))
    # Re-hash the forged result: semantic transcript/result rejection must still win.
    saved=json.loads((Path(actual.config['receipt_path'])/'result.json').read_bytes())
    saved['stock_baseline_restored']=False
    (Path(actual.config['receipt_path'])/'result.json').write_bytes(r.canonical(saved))
    config['rehearsal_result_sha256']=r.digest((Path(actual.config['receipt_path'])/'result.json').read_bytes())
    path.write_bytes(r.canonical(config))
    with pytest.raises(ValueError):r.prepare_campaign(path)


@pytest.mark.parametrize('fault',['symlink','fifo','oversized','relative'])
def test_bounded_evidence_preopen(fault,tmp_path):
    path=tmp_path/'evidence';path.write_bytes(b'x')
    if fault=='symlink':
        link=tmp_path/'link';link.symlink_to(path);path=link
    elif fault=='fifo':path.unlink();os.mkfifo(path)
    elif fault=='oversized':path.write_bytes(b'x'*101)
    elif fault=='relative':path=Path('relative')
    with pytest.raises((ValueError,OSError)):r.read_file(path,100)


def test_durable_intent_artifact_drift_closes_before_ioctl(prepared,monkeypatch):
    state=mock_sg(monkeypatch)
    def log(event,**fields):
        if event=='reset_submit_intent':prepared.evidence[0][0].write_bytes(b'changed during intent')
    sg=r.ResetSG(prepared,log)
    with pytest.raises(ValueError):sg.request_reset()
    assert sg.consumed and sg.failed and sg.fd is None
    assert not state.calls and state.closed==[888]
    with pytest.raises(ValueError):sg.request_reset()
    assert not state.calls
