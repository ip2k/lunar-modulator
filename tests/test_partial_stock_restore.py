"""MIT. Explicit synthetic partial-image constraint/wire/transaction models only."""
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fm1_partial_stock_restore as m

@pytest.fixture
def model(tmp_path,monkeypatch):
    stock=bytearray(b'\xff'*m.FLASH_BYTES)
    stock[0x4000:0x4100]=b'Q'*256;stock[0x5000:0x5100]=b'R'*256
    stock=bytes(stock);monkeypatch.setattr(m,'STOCK_SHA',m.digest(stock))
    partial=bytearray(stock);partial[0x4000:0x4100]=b'\x00'*256;partial[0x5000:0x5100]=b'\x7f'*256
    partial=bytes(partial)
    identity=dict(unit_id='explicit-partial-model',flash_size=1048576,sector_size=4096,page_size=256,jedec=0x856014,simulated=False)
    directory=tmp_path/'transaction';m.prepare_transaction(directory,partial,partial,stock,identity,(0x4000,0x5000))
    tx=m.transaction_module();plan,journal,a,b=tx.load_transaction(directory)
    binding=dict(phase='loader',loader_sha256=m.LOADER_SHA,session_id='explicit-model-only',identity=identity)
    source=tmp_path/'evidence';source.write_bytes(b'explicit-model')
    p=m.Prepared(directory,tmp_path/'receipt',tmp_path/'.partial-stock.consumed','a'*64,tx.encoded(plan),partial,stock,
        tx.encoded(binding),((source,b'explicit-model',64),),(tmp_path/'absent',))
    m._AUTHORIZED.add(p);p.check()
    class Transport:
        def __init__(self):self.flash=bytearray(partial);self.calls=[];self.closed=0;self.fail=None;self.opened=0
        def binding(self):return binding
        def exchange(self,cdb,payload,in_size):
            op=int.from_bytes(cdb[:2],'big');a=int.from_bytes(cdb[2:6],'big');self.calls.append((op,a,payload))
            if self.fail:raise self.fail('modeled syscall ambiguity')
            if op==0xfc0a:return b'\xfc\x0a\x03\x00'+(0x856014).to_bytes(4,'little')+b'\0'*8
            if op==0xfd05:return bytes(self.flash[a:a+256])
            if op==0xfb01:self.flash[a:a+4096]=b'\xff'*4096;return b'\xfb\x01'+b'\0'*14
            if op==0xfb04:self.flash[a:a+256]=payload;return b''
            pytest.fail('nonallowlisted wire')
        def close(self):self.closed+=1
    t=Transport()
    return p,t,source,tx,stock,partial

@pytest.mark.parametrize('pin',[None,'a'*64])
def test_production_acquisition_always_closed_before_io(monkeypatch,pin):
    monkeypatch.setattr(m,'ACQUISITION_SOURCE_SHA',pin)
    monkeypatch.setattr(m,'read_file',lambda *a,**k:pytest.fail('closed factory IO'))
    with pytest.raises(ValueError):m.prepare_campaign('/not/read')

@pytest.mark.parametrize('kind',['symlink','fifo','directory','relative','oversize'])
def test_bounded_direct_evidence_reader(tmp_path,kind):
    p=tmp_path/'p'
    if kind=='symlink':p.symlink_to(__file__)
    elif kind=='fifo':os.mkfifo(p)
    elif kind=='directory':p.mkdir()
    elif kind=='relative':p=Path('relative')
    else:p.write_bytes(b'12345')
    with pytest.raises((ValueError,OSError)):m.read_file(p,4)

def test_fdopen_failure_closes(tmp_path,monkeypatch):
    p=tmp_path/'p';p.write_bytes(b'x');opened=[];closed=[];op=os.open;cl=os.close
    def opening(*a,**k):fd=op(*a,**k);opened.append(fd);return fd
    def closing(fd):closed.append(fd);cl(fd)
    monkeypatch.setattr(m.os,'open',opening);monkeypatch.setattr(m.os,'close',closing)
    monkeypatch.setattr(m.os,'fdopen',lambda *a,**k:(_ for _ in ()).throw(OSError('fdopen')))
    with pytest.raises(OSError):m.read_file(p)
    assert opened==closed and len(opened)==1

@pytest.mark.parametrize('defect',['mismatch','short','stock','outside','spl','cfg','unsorted','duplicate','unaligned','boolean','protected_sector'])
def test_geometry_rejects_unsealed_preimages(model,defect):
    p,t,source,tx,stock,partial=model;a=partial;b=partial;allowed=(0x4000,0x5000)
    if defect=='mismatch':b=stock
    elif defect=='short':a=a[:-1]
    elif defect=='stock':stock=b'\0'*1048576
    elif defect in ['outside','spl','cfg']:
        x=bytearray(a);x[{'outside':0x6000,'spl':0,'cfg':0xACF40}[defect]]^=1;a=b=bytes(x)
    elif defect=='unsorted':allowed=(0x5000,0x4000)
    elif defect=='duplicate':allowed=(0x4000,0x4000)
    elif defect=='unaligned':allowed=(0x4001,)
    elif defect=='boolean':allowed=(False,)
    else:allowed=(0x4000,0xAD000)
    with pytest.raises(ValueError):m.geometry(a,b,stock,allowed)

def test_geometry_derives_dirty_subset_directory_last_without_parsing(model):
    p,t,s,tx,stock,partial=model;r=m.geometry(partial,partial,stock,(0x4000,0x5000,0x6000))
    assert r['dirty_sectors']==[0x4000,0x5000] and r['sector_order']==[0x5000,0x4000]
    assert r['purpose']=='stock_restore' and r['internal_action']=='install' and not r['acquisition_verified']

@pytest.mark.parametrize('field',['directory','receipt','marker','binding','plan_bytes','stock','preimage','evidence','absent'])
def test_copied_prepared_cannot_open(model,field):
    p,t,*_=model;q=replace(p,**{field:getattr(p,field)})
    with pytest.raises(ValueError):m.run_campaign(q,lambda:pytest.fail('copied authority opened'))
    assert not t.calls

@pytest.mark.parametrize('boundary',['marker_symlink','receipt_symlink','absent','evidence','backupA','backupB','target','plan','journal_fifo'])
def test_file_and_absence_drift_before_transport(model,boundary):
    p,t,source,*_=model
    if boundary=='marker_symlink':p.marker.symlink_to(source)
    elif boundary=='receipt_symlink':p.receipt.symlink_to(source)
    elif boundary=='absent':p.absent[0].symlink_to(source)
    elif boundary=='evidence':source.write_bytes(b'changed')
    elif boundary=='journal_fifo':(p.directory/'journal.json').unlink();os.mkfifo(p.directory/'journal.json')
    else:(p.directory/({'backupA':'backupA.bin','backupB':'backupB.bin','target':'target.bin','plan':'plan.json'}[boundary])).write_bytes(b'changed')
    with pytest.raises((ValueError,OSError)):m.run_campaign(p,lambda:pytest.fail('drift opened'))

def running(model,operation='erase',address=0x5000):
    p,t,s,tx,*_=model;plan,j,a,b=tx.load_transaction(p.directory)
    j.update(state='running',direction='install',intent=dict(operation=operation,address=address));tx.save_journal(p.directory,j)
    session=m.Session(p,t,lambda *a,**k:None);return session

@pytest.mark.parametrize('op',[0xfc0c,0xfc12,0xfb06,0xfb08,0xfd07,0xfb02])
def test_forbidden_wire_latches_no_request(model,op):
    session=running(model)
    with pytest.raises(ValueError):session.exchange(op.to_bytes(2,'big')+b'\xff'*14,b'',16)
    assert not model[1].calls and session.failed and model[1].closed==1

@pytest.mark.parametrize('kind',['intent','absence','binding'])
def test_post_durable_request_boundary_drift_zero_exchange(model,kind):
    p,t,s,tx,*_=model;session=running(model)
    def logger(*a,**k):
        if kind=='absence':p.absent[0].write_bytes(b'appeared')
        elif kind=='binding':t.binding=lambda:dict(phase='rom')
        else:
            plan,j,a,b=tx.load_transaction(p.directory);j['intent']['address']=0x4000;tx.save_journal(p.directory,j)
    session.log=logger
    with pytest.raises(ValueError):session.erase(0x5000)
    assert not t.calls and t.closed==1

@pytest.mark.parametrize('fault',[OSError,KeyboardInterrupt])
def test_mutation_ambiguity_retains_union_until_matching_read(model,fault):
    session=running(model);t=model[1];t.fail=fault
    with pytest.raises(fault):session.erase(0x5000)
    assert session.uncertain==set(range(0x5000,0x6000,256)) and len(t.calls)==1 and t.closed==1
    with pytest.raises(ValueError):session.read(0,256)
    assert len(t.calls)==1

def test_operation_return_does_not_clear_uncertainty(model):
    session=running(model);session.erase(0x5000)
    assert session.uncertain==set(range(0x5000,0x6000,256))
    session.read(0x5000,4096)
    assert session.uncertain=={0x5000}  # blank bytes match only FF desired stock pages
    p,t,s,tx,stock,_=model;plan,j,a,b=tx.load_transaction(p.directory)
    j['intent']=dict(operation='program',address=0x5000);tx.save_journal(p.directory,j)
    session.program(0x5000,stock[0x5000:0x5100]);assert session.uncertain=={0x5000}
    session.read(0x5000,256);assert not session.uncertain

def test_one_full_fresh_partial_to_stock_transaction(model):
    p,t,s,tx,stock,partial=model
    result=m.run_campaign(p,lambda:t)
    assert bytes(t.flash)==stock and result['purpose']=='stock_restore' and result['internal_action']=='install'
    assert [a for op,a,_ in t.calls if op==0xfb01]==[0x5000,0x4000]
    assert t.closed==1 and result['full_flash_readback_verified'] and not result['boot_observed']
    assert p.marker.read_text()==p.campaign_sha256
    assert tx.load_transaction(p.directory)[1]['state']=='complete'
    with pytest.raises(FileExistsError):m.run_campaign(p,lambda:pytest.fail('retry opened'))

def test_initial_full_flash_drift_no_mutation_consumed(model):
    p,t,*_=model;t.flash[0x7000]^=1
    with pytest.raises(ValueError):m.run_campaign(p,lambda:t)
    assert p.marker.exists() and not any(op in (0xfb01,0xfb04) for op,_,_ in t.calls)
    assert t.closed==1 and not (p.receipt/'result.json').exists()

@pytest.mark.parametrize('state',['running','recovery_required','complete'])
def test_existing_journal_cannot_grant_new_partial_authority(model,state):
    p,t,s,tx,*_=model;plan,j,a,b=tx.load_transaction(p.directory)
    j.update(state=state,direction='install');tx.save_journal(p.directory,j)
    with pytest.raises(ValueError):m.run_campaign(p,lambda:pytest.fail('old journal opener'))
    assert not p.marker.exists() and not t.calls
