"""MIT. Closed successor injected transport mechanics; no genuine new authority."""
from dataclasses import replace
from pathlib import Path
import ast

import pytest

import fm1_sdk_trace_admitted_stock_restore as r
import fm1_returned_rom_stock_restore as kernel
from test_returned_rom_stock_restore import prepared as legacy_prepared, read_page
from test_fixed_loader_backup import mock_sg


@pytest.fixture
def prepared(legacy_prepared):
    # Explicit model registry entries exercise wrappers only, not new factories.
    legacy,journal=legacy_prepared
    p=r.Prepared(legacy,kernel);r._AUTHORIZED.add(p)
    return p,journal


@pytest.mark.parametrize('entry', ['prepare','completed'])
@pytest.mark.parametrize('pending', ['BACKUP_SOURCE_SHA','POLICY_SOURCE_SHA'])
def test_each_closed_dependency_before_evidence(monkeypatch, entry, pending):
    for name in ('BACKUP_SOURCE_SHA','POLICY_SOURCE_SHA'):
        monkeypatch.setattr(r,name,None if name==pending else '0'*64)
    monkeypatch.setattr(r,'read_file',lambda *a,**k:pytest.fail('closed read'))
    with pytest.raises(ValueError,match='not frozen'):
        if entry=='prepare':r.prepare_campaign('/never-read')
        else:r.validate_completed_restore('/never-read',campaign_sha256='c',commands_sha256='l',
            result_sha256='r',journal_sha256='j',freeze=lambda *a,**k:pytest.fail('closed freeze'))


@pytest.mark.parametrize('field', ['legacy','kernel'])
def test_copy_rejected_before_any_discovery(prepared,monkeypatch,field):
    p,_=prepared;copy=replace(p,**{field:getattr(p,field)})
    monkeypatch.setattr(p.bridge,'discover_sg',lambda _:pytest.fail('discovery'))
    for fn in (r.require_prepared,r.transport_type,r.run_campaign):
        with pytest.raises(ValueError):fn(copy)


def test_legacy_instance_has_no_new_restore_authority(prepared):
    with pytest.raises(ValueError):r.require_prepared(prepared[0].legacy)


@pytest.mark.parametrize('position',[0,1,2048,4095])
def test_no_mutation_before_entire_current_target_is_read(prepared,monkeypatch,position):
    p,_=prepared;state=mock_sg(monkeypatch)
    sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    for index in range(position):read_page(sg,index*256)
    with pytest.raises(ValueError,match='No mutation'):
        sg.exchange(b'\xfb\x01\x00\x00\x40\x00'+b'\xff'*10,b'',16)
    assert sg.failed and sg.fd is None and len(state.calls)==position
    assert all(c[:2]==b'\xfd\x05' for c in state.calls)


@pytest.mark.parametrize('position',[0,4095])
def test_current_target_mismatch_closes_and_latches_no_retry(prepared,monkeypatch,position):
    p,_=prepared
    def corrupt(h,data,op,state):
        if op==0xFD05 and len(state.calls)==position+1:data[0]^=1
    state=mock_sg(monkeypatch,fault=corrupt)
    sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    for index in range(position):read_page(sg,index*256)
    with pytest.raises(ValueError,match='Initial actual NOR'):read_page(sg,position*256)
    with pytest.raises(ValueError):read_page(sg,position*256)
    assert sg.failed and sg.fd is None and not sg.initial_verified
    assert len(state.calls)==position+1


@pytest.mark.parametrize('boundary',['binding','request'])
def test_own_registry_rechecked_at_live_boundary(prepared,monkeypatch,boundary):
    p,_=prepared;state=mock_sg(monkeypatch)
    sg=r.transport_type(p)(p.policies[0],lambda *a,**k:None)
    r._AUTHORIZED.discard(p)
    try:
        with pytest.raises(ValueError):
            if boundary=='binding':sg.binding()
            else:read_page(sg,0)
        assert not state.calls
    finally:sg.close()


@pytest.mark.parametrize('boundary',['before-first-read','after-durable-intent'])
def test_absence_drift_blocks_ioctl_and_closes(prepared,monkeypatch,tmp_path,boundary):
    p,_=prepared;late=tmp_path/'late-reader-result.json'
    policy=replace(p.policies[0],absent_paths=(late,));kernel._POLICIES.add(policy)
    legacy=replace(p.legacy,policies=(policy,));kernel._AUTHORIZED.add(legacy)
    p=r.Prepared(legacy,kernel);r._AUTHORIZED.add(p)
    def log(event,**kw):
        if boundary=='after-durable-intent' and event=='sg_submit_intent':late.write_bytes(b'late')
    state=mock_sg(monkeypatch);sg=r.transport_type(p)(policy,log)
    if boundary=='before-first-read':late.write_bytes(b'late')
    with pytest.raises(ValueError,match='absent evidence'):read_page(sg,0)
    assert not state.calls and sg.failed and sg.fd is None and state.closed==[888]
    with pytest.raises(ValueError):read_page(sg,0)
    assert not state.calls


@pytest.mark.parametrize('expected',[None,'bad','0'*64])
def test_source_pin_mismatch_never_executes(tmp_path,expected):
    p=tmp_path/'source';p.write_text('raise RuntimeError("must not execute")')
    with pytest.raises(ValueError):r.load_source(p,expected,'_untrusted_admitted_restore')


def test_separate_schema_marker_replay_and_preserved_proof_contract():
    source=Path(r.__file__).read_text();tree=ast.parse(source)
    assignments={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
        and isinstance(n.value,ast.Constant)}
    assert assignments['BACKUP_SOURCE_SHA']=='1694733ce448a6f368938f251c4d5b4f639a37004dd6623035379953de9b775b'
    assert assignments['POLICY_SOURCE_SHA']=='54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835'
    assert r.digest((Path(r.__file__).parent/'fm1_sdk_trace_admitted_backup.py').read_bytes())==assignments['BACKUP_SOURCE_SHA']
    assert r.digest((Path(r.__file__).parent/'fm1_bound_sdk_trace.py').read_bytes())==assignments['POLICY_SOURCE_SHA']
    assert assignments['KERNEL_SOURCE_SHA']=='f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33'
    assert 'fm1_sdk_trace_admitted_backup.py' in source
    assert 'fm1-sdk-trace-admitted-stock-restore-only' in source
    assert '.sdk-trace-admitted-stock-restore.consumed' in source
    assert 'trace_admitted_stock_restore_completed' in source
    assert "_proof=proof['_proof']" in source
    assert "list(range(0x5000, 0x22000, 4096)) + [0x4000]" in source
