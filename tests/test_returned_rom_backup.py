"""MIT. New-ROM exact inventory authority; every SG syscall is modeled."""
from dataclasses import replace
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

import fm1_returned_rom_backup as r
import fm1_fixed_loader_backup as b
import fm1_uboot_read as reader
from test_fixed_loader_backup import campaign, mock_sg, USB


@pytest.fixture
def prepared(campaign):
    old=b.prepare_campaign(campaign[0])
    parent=campaign[0].parent
    c=dict(receipt_path=str(parent/'returned'),adapter_sha256=r.digest(Path(r.__file__).read_bytes()),
        target_boot_campaign_sha256='a'*64,rom_snapshot_sha256='b'*64,
        optional_stage_probe=None,returned_state_campaign_sha256='c'*64,provenance_mode='successful',
        probe_capture_path=None,connection_witness_sha256='d'*64,probe_admission_sha256=None)
    snapshot=dict(observed_at=time.time(),usb_binding=USB,
        sg_binding=dict(node='/dev/sgMOCK',node_identity=[1,2,3],usb_identity=[4,5,6]))
    p=r.Prepared(r.canonical(c),'model-campaign',r.canonical(snapshot),(),(),b,reader.SGHeader,
        old.operations,old.request_inventory_sha256,'original-model-manifest',parent)
    r._AUTHORIZED.add(p)
    return p


@pytest.mark.parametrize('field',['campaign','campaign_sha256','snapshot','evidence','policies',
    'bridge','header_type','operations','request_inventory_sha256','original_manifest_sha256','parent'])
def test_copied_authority_rejected_without_discovery(prepared,monkeypatch,field):
    copied=replace(prepared,**{field:getattr(prepared,field)})
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('hardware discovery'))
    with pytest.raises(ValueError):r.FixedSG(copied,lambda *a,**k:None)
    with pytest.raises(ValueError):r.run_campaign(copied)


def test_old_softkey_campaign_not_admitted(campaign,monkeypatch):
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('hardware discovery'))
    with pytest.raises(ValueError):r.prepare_campaign(campaign[0])


def test_fake_authority_not_admitted():
    with pytest.raises(ValueError):r.run_campaign(SimpleNamespace(check=lambda:None))


def test_complete_exact_target_backup_and_marker(prepared,monkeypatch):
    state=mock_sg(monkeypatch)
    target=b''.join(bytes([i%256])*256 for i in range(4096))
    monkeypatch.setattr(r,'TARGET_SHA',r.digest(target))
    result=r.run_campaign(prepared)
    c=json.loads(prepared.campaign);receipt=Path(c['receipt_path'])
    assert (receipt/'dumpA.bin').read_bytes()==(receipt/'dumpB.bin').read_bytes()==target
    assert result['kind']=='fm1-returned-rom-fixed-loader-target-backup'
    assert result['historical_unit_identity']=='FM-1_092' and 'unit_identity' not in result
    assert result['commands']==8757 and result['current_flash_sha256']==r.digest(target)
    assert all(result[k] is False for k in ('physical_recovery_verified','boot_observed','display_observed','kernel_exclusivity'))
    events=[json.loads(line) for line in (receipt/'commands.jsonl').read_text().splitlines()]
    assert len(events)==17516 and events[-1]['event']=='returned_backup_completed'
    completions=[e for e in events if e['event']=='sg_completion']
    assert len(completions)==8757
    for op,e in zip(prepared.operations,completions):
        if op.label in ('dumpA.bin','dumpB.bin'):
            address=int.from_bytes(op.cdb[2:6],'big')
            assert e['response_sha256']==r.digest(target[address:address+256])
    assert state.closed==[888] and len(state.calls)==8757
    assert r.validate_read_receipt((receipt/'commands.jsonl').read_bytes(),result,c,
        prepared.operations,target,target)[1]>=events[0]['time']
    page_event=next(e for e in events if e['event']=='sg_completion' and e['index']==52)
    page_event['response_sha256']='f'*64
    with pytest.raises(ValueError):r.validate_read_receipt(
        ('\n'.join(json.dumps(e) for e in events)).encode(),result,c,prepared.operations,target,target)
    c['receipt_path']+='-other'
    other=r.Prepared(r.canonical(c),'model-two',prepared.snapshot,(),(),b,reader.SGHeader,
        prepared.operations,prepared.request_inventory_sha256,'model',prepared.parent)
    r._AUTHORIZED.add(other)
    with pytest.raises(FileExistsError):r.run_campaign(other)
    assert len(state.calls)==8757


@pytest.mark.parametrize('fault',['status','masked','msg','host','driver','resid','info','sense_len','ioctl','inquiry'])
def test_ambiguity_consumes_closes_and_never_retries(prepared,monkeypatch,fault):
    def inject(h,data,op,state):
        if fault=='ioctl':raise OSError('lost reply')
        if fault=='inquiry':data[8:16]=b'NOTWL82 '
        else:setattr(h,fault,1)
    state=mock_sg(monkeypatch,fault=inject)
    sg=r.FixedSG(prepared,lambda *a,**k:None)
    with pytest.raises((OSError,ValueError)):sg.exchange_next()
    with pytest.raises(ValueError):sg.exchange_next()
    assert sg.failed and sg.fd is None and sg.next==1 and state.closed==[888]
    assert len(state.calls)==1


@pytest.mark.parametrize('when',['open','pre','post','intent_file_drift','stale_snapshot'])
def test_binding_drift_and_durable_intent_boundary(prepared,monkeypatch,tmp_path,when):
    threshold={'open':1,'pre':3,'post':4}.get(when)
    def changed(state):
        if threshold and state.discoveries>=threshold:raise ValueError('changed mapping')
    state=mock_sg(monkeypatch,binding_fault=changed)
    p=prepared
    if when=='stale_snapshot':
        snapshot=json.loads(p.snapshot);snapshot['observed_at']-=121
        p=r.Prepared(p.campaign,p.campaign_sha256,r.canonical(snapshot),(),(),b,p.header_type,
            p.operations,p.request_inventory_sha256,p.original_manifest_sha256,p.parent)
        r._AUTHORIZED.add(p)
    evidence=tmp_path/'frozen';evidence.write_bytes(b'checked')
    if when=='intent_file_drift':
        p=r.Prepared(p.campaign,p.campaign_sha256,p.snapshot,((evidence,b'checked',100),),(),b,p.header_type,
            p.operations,p.request_inventory_sha256,p.original_manifest_sha256,p.parent)
        r._AUTHORIZED.add(p)
    def log(event,**kw):
        if when=='intent_file_drift' and event=='sg_submit_intent':evidence.write_bytes(b'changed')
    with pytest.raises(ValueError):
        sg=r.FixedSG(p,log);sg.exchange_next()
    assert len(state.calls)==(1 if when=='post' else 0)


def test_dump_target_mismatch_leaves_no_success(prepared,monkeypatch):
    state=mock_sg(monkeypatch)
    with pytest.raises(ValueError,match='exact target'):r.run_campaign(prepared)
    receipt=Path(json.loads(prepared.campaign)['receipt_path'])
    assert not (receipt/'manifest.json').exists()
    assert 'returned_backup_stopped_ambiguous' in (receipt/'commands.jsonl').read_text()
    assert state.closed==[888]
    assert (prepared.parent/('.returned-rom-'+'a'*64+'.consumed')).exists()


@pytest.mark.parametrize('kind',['fifo','symlink','directory','oversize'])
def test_nonregular_or_unbounded_inputs_refused(tmp_path,kind):
    p=tmp_path/'input'
    if kind=='fifo':os.mkfifo(p)
    elif kind=='directory':p.mkdir()
    elif kind=='symlink':p.symlink_to(__file__)
    else:p.write_bytes(b'x'*(2*1048576+1))
    with pytest.raises((OSError,ValueError)):r.read_file(p)


@pytest.fixture
def read_receipt(prepared,monkeypatch):
    """Pure transcript model: no SG, disk fsync or opener registration."""
    target=b''.join(bytes([i%256])*256 for i in range(4096))
    monkeypatch.setattr(r,'TARGET_SHA',r.digest(target))
    c=json.loads(prepared.campaign);now=time.time()-1
    manifest=dict(campaign_sha256=prepared.campaign_sha256,
        original_manifest_sha256=prepared.original_manifest_sha256,usb_binding=USB,
        request_inventory_sha256=prepared.request_inventory_sha256,loader_sha256=b.LOADER_SHA,
        loader_profile_sha256=b.PROFILE_SHA,current_flash_sha256=r.TARGET_SHA,
        identical=True,command_completions=True,commands=8757,flash_bytes=1048576,
        flash_readback_only=True,historical_unit_identity='FM-1_092',
        physical_recovery_verified=False,boot_observed=False,display_observed=False,kernel_exclusivity=False,
        dumps=[dict(file=name,bytes=1048576,sha256=r.TARGET_SHA,complete=True)
            for name in ('dumpA.bin','dumpB.bin')])
    rows=[dict(time=now,event='returned_backup_prepared',campaign_sha256=prepared.campaign_sha256,
        adapter_sha256=c['adapter_sha256'],target_boot_campaign_sha256=c['target_boot_campaign_sha256'],
        rom_snapshot_sha256=c['rom_snapshot_sha256'],original_manifest_sha256=prepared.original_manifest_sha256,
        usb_binding=USB,commands=8757,request_inventory_sha256=prepared.request_inventory_sha256,
        loader_sha256=b.LOADER_SHA,profile_sha256=b.PROFILE_SHA,
        kernel_exclusivity=False,physical_recovery_verified=False)]
    for i,op in enumerate(prepared.operations):
        response='0'*64 if op.read_size else None
        if op.label in ('dumpA.bin','dumpB.bin'):
            address=int.from_bytes(op.cdb[2:6],'big');response=r.digest(target[address:address+256])
        rows.extend([dict(time=now,event='sg_submit_intent',index=i,phase=op.phase,label=op.label,
            cdb=op.cdb.hex(),payload_sha256=r.digest(op.payload) if op.payload else None,
            out_len=len(op.payload),in_len=op.read_size,retry=False),
            dict(time=now,event='sg_completion',index=i,status=0,masked=0,msg=0,host=0,
                driver=0,resid=0,info=0,sense_len=0,sense_hex='',response_sha256=response,retry=False)])
    rows.append(dict(time=now,event='returned_backup_completed',identical=True,bytes_per_dump=1048576,
        target_sha256=r.TARGET_SHA,physical_recovery_verified=False,retry=False))
    return prepared,c,manifest,rows,target


def replay_receipt(fixture):
    p,c,manifest,rows,target=fixture
    return r.validate_read_receipt(b'\n'.join(r.canonical(e) for e in rows),
        manifest,c,p.operations,target,target)


def test_read_replay_is_evidence_only_and_complete(read_receipt,monkeypatch):
    monkeypatch.setattr(b,'discover_sg',lambda _:pytest.fail('evidence opened hardware'))
    assert replay_receipt(read_receipt)[0]==read_receipt[3][0]['time']


@pytest.mark.parametrize('fault',['missing','extra','reordered','wrong_phase','wrong_cdb',
    'wrong_payload','wrong_length','wrong_index','first_page_hash','last_page_hash',
    'status','sense','residue','retry','flag','stopped','nonfinite','future','partial_dump'])
def test_independent_read_replay_rejects_edited_receipts(read_receipt,fault):
    p,c,manifest,rows,target=read_receipt
    if fault=='missing':rows.pop(106)
    elif fault=='extra':rows.insert(106,dict(rows[106]))
    elif fault=='reordered':rows[105],rows[107]=rows[107],rows[105]
    elif fault=='wrong_phase':rows[105]['phase']='rom'
    elif fault=='wrong_cdb':rows[105]['cdb']='fc12'+'ff'*14
    elif fault=='wrong_payload':rows[3]['payload_sha256']='f'*64
    elif fault=='wrong_length':rows[105]['in_len']=512
    elif fault=='wrong_index':rows[106]['index']=53
    elif fault=='first_page_hash':rows[106]['response_sha256']='f'*64
    elif fault=='last_page_hash':rows[-4]['response_sha256']='f'*64
    elif fault=='status':rows[106]['status']=2
    elif fault=='sense':rows[106]['sense_len']=1;rows[106]['sense_hex']='00'
    elif fault=='residue':rows[106]['resid']=1
    elif fault=='retry':rows[105]['retry']=True
    elif fault=='flag':manifest['physical_recovery_verified']=True
    elif fault=='stopped':rows[-1]['event']='returned_backup_stopped_ambiguous'
    elif fault=='nonfinite':rows[0]['time']=float('inf')
    elif fault=='future':rows[-1]['time']=time.time()+1000
    elif fault=='partial_dump':manifest['dumps'][1]['bytes']=1048320
    with pytest.raises(ValueError):replay_receipt(read_receipt)

@pytest.fixture
def connection_witness():
    snapshot=dict(observed_at=100,usb_binding=USB,sg_binding=dict(node='/dev/sgMOCK'))
    witness=dict(schema=1,kind='fm1-passive-returned-rom-backup-connection',observed_at=300,
        usb_binding=USB,sg_binding=snapshot['sg_binding'],rom_snapshot_sha256='a'*64,
        quiet_state='returned-rom-after-read-only-probe-no-loader-upload')
    return snapshot,witness


def test_old_admission_can_have_fresh_unchanged_connection(connection_witness):
    snapshot,witness=connection_witness
    r.validate_connection_witness(witness,snapshot,'a'*64,305)


@pytest.mark.parametrize('fault',['age','future','before_original','usb','sg','pin','kind','bool','extra'])
def test_passive_connection_witness_fails_closed(connection_witness,fault):
    snapshot,witness=connection_witness
    if fault=='age':witness['observed_at']=184
    elif fault=='future':witness['observed_at']=306
    elif fault=='before_original':witness['observed_at']=99
    elif fault=='usb':witness['usb_binding']=dict(USB,devnum='999')
    elif fault=='sg':witness['sg_binding']=dict(node='/dev/sgOTHER')
    elif fault=='pin':witness['rom_snapshot_sha256']='b'*64
    elif fault=='kind':witness['kind']='fm1-passive-post-target-boot-rom'
    elif fault=='bool':witness['schema']=True
    else:witness['unreviewed']=True
    with pytest.raises(ValueError):r.validate_connection_witness(witness,snapshot,'a'*64,305)


def test_completed_probe_uses_preserved_original_admission(tmp_path):
    path=tmp_path/'probe.json';commands=tmp_path/'receipt'/'commands.jsonl'
    commands.parent.mkdir();commands.write_bytes(r.canonical(dict(time=100,event='stage_probe_prepared')))
    config=dict(optional_stage_probe=str(path),returned_state_campaign_path=str(path),probe_capture_path=None,
        probe_admission_path=str(commands),probe_admission_sha256=r.digest(commands.read_bytes()))
    def freeze(p,expected=None,limit=1048576):
        data=r.read_file(p,limit)
        if expected is not None and r.digest(data)!=expected:raise ValueError('pin')
        return data
    assert r.historical_probe_admission(config,dict(receipt_path=str(commands.parent)),freeze,300)==100
    commands.write_bytes(r.canonical(dict(time=299,event='stage_probe_prepared')))
    with pytest.raises(ValueError):r.historical_probe_admission(config,dict(receipt_path=str(commands.parent)),freeze,300)


def test_stopped_probe_original_preflight_is_exact_native_path(tmp_path):
    path=tmp_path/'probe.json';native=tmp_path/'native.json';preflight=tmp_path/'preflight.json'
    native.write_bytes(r.canonical(dict(probe_campaign_path=str(path))))
    preflight.write_bytes(r.canonical(dict(time=100)))
    capture=tmp_path/'capture.json';capture.write_bytes(r.canonical(dict(native_campaign_path=str(native),
        native_campaign_sha256=r.digest(native.read_bytes()))))
    config=dict(optional_stage_probe=str(path),returned_state_campaign_path=str(path),probe_capture_path=str(capture),
        probe_admission_path=str(preflight),probe_admission_sha256=r.digest(preflight.read_bytes()))
    def freeze(p,expected=None,limit=1048576):
        data=r.read_file(p,limit)
        if expected is not None and r.digest(data)!=expected:raise ValueError('pin')
        return data
    assert r.historical_probe_admission(config,{},freeze,300)==100
    other=tmp_path/'invented.json';other.write_bytes(preflight.read_bytes())
    config['probe_admission_path']=str(other)
    with pytest.raises(ValueError):r.historical_probe_admission(config,{},freeze,300)


def test_no_probe_cannot_invent_historical_admission():
    config=dict(optional_stage_probe=None,probe_capture_path=None,probe_admission_path='invented',probe_admission_sha256='a'*64)
    with pytest.raises(ValueError):r.historical_probe_admission(config,{},lambda *a,**k:pytest.fail('read'),300)
