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
