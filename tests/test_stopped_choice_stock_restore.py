"""MIT. Distinct closed restore authority with injected SG; no devices."""
from dataclasses import replace
from pathlib import Path

import pytest

import fm1_stopped_choice_stock_restore as r
import fm1_returned_rom_stock_restore as kernel
from test_returned_rom_stock_restore import prepared as legacy_prepared, read_page
from test_fixed_loader_backup import mock_sg


@pytest.fixture
def prepared(legacy_prepared):
    legacy,journal=legacy_prepared
    p=r.Prepared(legacy,kernel);r._AUTHORIZED.add(p)
    return p,journal


@pytest.mark.parametrize('entry',['prepare','completed'])
def test_unfrozen_backup_fails_before_any_evidence_open(monkeypatch,entry):
    monkeypatch.setattr(r,'read_file',lambda *a:pytest.fail('evidence opened'))
    with pytest.raises(ValueError,match='not frozen'):
        if entry=='prepare':r.prepare_campaign(Path('/absent'))
        else:r.validate_completed_restore(Path('/absent'),campaign_sha256='c',commands_sha256='x',
            result_sha256='r',journal_sha256='j',freeze=lambda *a,**k:pytest.fail('freeze called'))


@pytest.mark.parametrize('field',['legacy','kernel'])
def test_copied_new_authority_rejected_before_discovery(prepared,monkeypatch,field):
    p,_=prepared;other=replace(p,**{field:getattr(p,field)})
    monkeypatch.setattr(p.bridge,'discover_sg',lambda _:pytest.fail('discovery'))
    with pytest.raises(ValueError):r.require_prepared(other)
    with pytest.raises(ValueError):r.transport_type(other)
    with pytest.raises(ValueError):r.run_campaign(other)


def test_legacy_authority_does_not_authorize_successor(prepared):
    p,_=prepared
    with pytest.raises(ValueError):r.require_prepared(p.legacy)


@pytest.mark.parametrize('position',[0,1,2048,4095])
def test_mutation_requires_complete_target_before_successor_restore(prepared,monkeypatch,position):
    p,_=prepared;state=mock_sg(monkeypatch)
    sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    for index in range(position):read_page(sg,index*256)
    with pytest.raises(ValueError,match='No mutation'):
        sg.exchange(b'\xfb\x01\x00\x00\x40\x00'+b'\xff'*10,b'',16)
    assert sg.failed and sg.fd is None and len(state.calls)==position
    assert all(c[:2]==b'\xfd\x05' for c in state.calls)


@pytest.mark.parametrize('boundary',['binding','request'])
def test_new_authority_rechecked_on_bound_handle(prepared,monkeypatch,boundary):
    p,_=prepared;state=mock_sg(monkeypatch)
    sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    r._AUTHORIZED.discard(p)
    try:
        with pytest.raises(ValueError,match='factory instance'):
            if boundary=='binding':sg.binding()
            else:read_page(sg,0)
        assert not state.calls
    finally:sg.close()


def test_negative_provenance_appearance_blocks_first_request(prepared,monkeypatch,tmp_path):
    p,_=prepared;late=tmp_path/'result.json'
    policy=replace(p.policies[0],absent_paths=(late,));kernel._POLICIES.add(policy)
    legacy=replace(p.legacy,policies=(policy,));kernel._AUTHORIZED.add(legacy)
    p=r.Prepared(legacy,kernel);r._AUTHORIZED.add(p)
    state=mock_sg(monkeypatch);sg=r.transport_type(p)(policy,lambda *a,**k:None)
    late.write_bytes(b'{}')
    with pytest.raises(ValueError,match='absent evidence'):read_page(sg,0)
    assert not state.calls and sg.failed and sg.fd is None


@pytest.mark.parametrize('value',[None,'bad','0'*64])
def test_exact_kernel_source_required(tmp_path,value):
    path=tmp_path/'kernel.py';path.write_text('raise RuntimeError("should never execute")')
    with pytest.raises(ValueError):r.load_source(path,value,'_bad_stopped_restore_kernel')


def test_kernel_loader_rejects_symlink(tmp_path):
    target=tmp_path/'target.py';target.write_text('x=1')
    link=tmp_path/'linked.py';link.symlink_to(target)
    with pytest.raises(OSError):r.load_source(link,r.digest(target.read_bytes()),'_linked_restore')
