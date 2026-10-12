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
        target_boot_campaign_sha256='a'*64,rom_snapshot_sha256='b'*64)
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
