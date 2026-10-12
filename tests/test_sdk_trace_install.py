"""MIT. Distinct trace policy/worker authority and device-free acceptance.

Synthetic unit authority is explicit. The optional actual case uses unchanged
production factories and exact private files, with only time and SG modeled.
"""
from dataclasses import replace
import copy
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from test_sdk_rehearsal import actual, unit, SGModel, wire, rehearsal
import fm1_bound_sdk_trace as policy
import fm1_sdk_trace_install as install


@pytest.mark.parametrize('module', [policy, install])
@pytest.mark.parametrize('kind', ['symlink', 'fifo', 'directory', 'oversize', 'relative'])
def test_bootstrap_reader_rejects_non_direct_bounded_inputs(tmp_path, module, kind):
    path=tmp_path/'evidence'
    if kind=='symlink': path.symlink_to(__file__)
    elif kind=='fifo': os.mkfifo(path)
    elif kind=='directory': path.mkdir()
    else: path.write_bytes(b'12345')
    if kind=='relative': path=Path('relative')
    with pytest.raises((ValueError,OSError)): module.read_file(path,4)


@pytest.mark.parametrize('module', [policy,install])
def test_fdopen_failure_closes_bootstrap_descriptor(tmp_path,monkeypatch,module):
    path=tmp_path/'evidence';path.write_bytes(b'x')
    opened=[];closed=[];real_open=os.open;real_close=os.close
    def open_file(*a,**k):
        fd=real_open(*a,**k);opened.append(fd);return fd
    def close_file(fd): closed.append(fd);real_close(fd)
    monkeypatch.setattr(module.os,'open',open_file)
    monkeypatch.setattr(module.os,'close',close_file)
    monkeypatch.setattr(module.os,'fdopen',lambda *a,**k: (_ for _ in ()).throw(OSError('fdopen')))
    with pytest.raises(OSError): module.read_file(path)
    assert opened==closed and len(opened)==1


@pytest.mark.parametrize('name',['TARGET_SHA','BUILD_MANIFEST_SHA','TRACE_REVIEW_SHA'])
def test_explicit_unbound_candidate_gate_closed(monkeypatch,name):
    for key in ('TARGET_SHA','BUILD_MANIFEST_SHA','TRACE_REVIEW_SHA'): monkeypatch.setattr(policy,key,'a'*64)
    monkeypatch.setattr(policy,name,None)
    with pytest.raises(ValueError,match='acceptance'): policy.require_candidate_pins()


def test_install_unbound_policy_gate_closed(monkeypatch):
    monkeypatch.setattr(install,'POLICY_SHA',None)
    monkeypatch.setattr(install,'read_file',lambda *a,**k: pytest.fail('closed gate read source'))
    with pytest.raises(ValueError,match='activation is closed'): install.policy_module()


@pytest.mark.parametrize('kind',['corrupt','symlink','fifo','directory','oversize'])
def test_policy_bootstrap_refuses_before_exec(tmp_path,monkeypatch,kind):
    path=tmp_path/'fm1_bound_sdk_trace.py'
    if kind=='symlink':path.symlink_to(policy.__file__)
    elif kind=='fifo':os.mkfifo(path)
    elif kind=='directory':path.mkdir()
    else:path.write_bytes(b'x'*(2*1048576+1) if kind=='oversize' else b'raise AssertionError("executed")')
    monkeypatch.setattr(install,'POLICY_SHA','a'*64)
    monkeypatch.setattr(install,'__file__',str(tmp_path/'fm1_sdk_trace_install.py'))
    with pytest.raises((ValueError,OSError)):install.policy_module()


@pytest.fixture
def trace_unit(unit,tmp_path):
    path=tmp_path/'campaign.json';path.write_bytes(b'{"unit":"explicit mock only"}')
    cfg=json.loads(unit.prepared.config)
    p=SimpleNamespace(__file__=policy.__file__,TARGET_SHA=rehearsal.TARGET_SHA,
        BASELINE_SHA=rehearsal.BASELINE_SHA,TRACE_NONCE=policy.TRACE_NONCE,
        TRACE_ADDRESS=policy.TRACE_ADDRESS,TRACE_BYTES=64,REHEARSAL_SHA=policy.REHEARSAL_SHA)
    for bound in unit.prepared.policies:
        bound.plan_bytes=rehearsal.canonical(dict(identity=dict(unit_id='mock-only'),sector_order=[0x5000,0x4000]))
    prepared=install.Prepared(rehearsal.canonical(cfg),path,install.digest(path.read_bytes()),
        install.digest(Path(install.__file__).read_bytes()),'explicit unit mock only',
        unit.prepared.policies,unit.prepared.mapping,unit.prepared.bridge,unit.prepared.header_type,
        rehearsal,p,rehearsal.time.time(),Path(install.__file__).read_bytes(),Path(policy.__file__).read_bytes(),
        Path(cfg['receipt_path']),unit.parent/'.sdk-rehearsal.consumed')
    install._AUTHORIZED.add(prepared)
    prepared.check()
    return SimpleNamespace(prepared=prepared,unit=unit,path=path)


@pytest.mark.parametrize('field',['config','policies','runtime','bridge','mapping','header_type','marker','policy_module'])
def test_copied_prepared_has_no_transport_authority(trace_unit,field):
    p=trace_unit.prepared;copy=replace(p,**{field:getattr(p,field)})
    with pytest.raises(ValueError,match='Exact new prepared'):install.run_campaign(copy)
    assert not trace_unit.unit.model.opened


@pytest.mark.parametrize('boundary',['campaign','marker','receipt'])
def test_frozen_input_or_consumption_drift_prevents_open(trace_unit,boundary):
    p=trace_unit.prepared
    if boundary=='campaign':trace_unit.path.write_bytes(b'{}')
    elif boundary=='marker':p.marker.symlink_to(trace_unit.path)
    else:p.receipt.mkdir()
    with pytest.raises((ValueError,OSError)):install.run_campaign(p)
    assert not trace_unit.unit.model.opened


def worker(trace_unit,monkeypatch,fault=None):
    directions=[]
    class Session:
        def __init__(self,p,t):self.p,self.t=p,t
        def run(self,checkpoint):
            directions.append(self.p.direction)
            self.t.exchange(*wire(0xFC0A))
            if fault:raise fault('modeled terminal interruption')
            return dict(verified_sha256=rehearsal.TARGET_SHA,sectors_written=30)
    for p in trace_unit.prepared.policies:
        p.bind=lambda t,p=p:Session(p,t)
    return directions


def test_worker_install_only_durable_completion_and_no_boot(trace_unit,monkeypatch):
    directions=worker(trace_unit,monkeypatch)
    result=install.run_campaign(trace_unit.prepared)
    assert directions==['install'] and result['verified_sha256']==rehearsal.TARGET_SHA
    assert result['trace_nonce']==policy.TRACE_NONCE and result['trace_bytes']==64
    assert result['sector_order']==[0x5000,0x4000]
    assert all(result[k] is False for k in ('boot_observed','display_observed','physical_recovery_verified','stock_baseline_restored','kernel_exclusivity'))
    assert result['stock_restore_preflighted'] and result['full_flash_readback_verified']
    assert trace_unit.unit.model.closed==[SGModel.FD]
    log=[json.loads(line) for line in (trace_unit.prepared.receipt/'commands.jsonl').read_text().splitlines()]
    assert log[0]['event']=='trace_install_prepared' and log[-1]['event']=='trace_install_completed'
    assert json.loads((trace_unit.prepared.receipt/'result.json').read_bytes())==result
    assert trace_unit.prepared.marker.read_text()==trace_unit.prepared.campaign_sha256
    before=list(trace_unit.unit.model.opened)
    with pytest.raises(FileExistsError):install.run_campaign(trace_unit.prepared)
    assert trace_unit.unit.model.opened==before


@pytest.mark.parametrize('fault',[OSError,KeyboardInterrupt])
def test_ambiguous_worker_keeps_consumed_and_never_restores(trace_unit,monkeypatch,fault):
    directions=worker(trace_unit,monkeypatch,fault)
    with pytest.raises(fault):install.run_campaign(trace_unit.prepared)
    assert directions==['install'] and trace_unit.prepared.marker.exists()
    assert not (trace_unit.prepared.receipt/'result.json').exists()
    events=[json.loads(l) for l in (trace_unit.prepared.receipt/'commands.jsonl').read_text().splitlines()]
    assert events[-1]['event']=='trace_install_stopped_ambiguous' and events[-1]['retry'] is False
    assert trace_unit.unit.model.closed==[SGModel.FD]


def test_expired_opening_window_consumes_without_open(trace_unit,monkeypatch):
    worker(trace_unit,monkeypatch)
    monkeypatch.setattr(install.time,'time',lambda:trace_unit.prepared.admission_time+11)
    with pytest.raises(ValueError,match='window expired'):install.run_campaign(trace_unit.prepared)
    assert trace_unit.prepared.marker.exists() and not trace_unit.unit.model.opened


def test_durable_submit_marker_drift_prevents_ioctl(trace_unit,monkeypatch):
    worker(trace_unit,monkeypatch)
    real_sync=trace_unit.prepared.bridge.sync_dir
    def sync(path):
        real_sync(path)
        log=trace_unit.prepared.receipt/'commands.jsonl'
        if log.exists() and 'sg_submit_intent' in log.read_text():
            trace_unit.prepared.marker.write_text('changed')
    trace_unit.prepared.bridge.sync_dir=sync
    with pytest.raises(ValueError,match='marker changed'):install.run_campaign(trace_unit.prepared)
    assert not trace_unit.unit.model.calls and trace_unit.unit.model.closed==[SGModel.FD]
    assert trace_unit.prepared.marker.exists()


def test_actual_private_trace_factory_full_install(actual,tmp_path,monkeypatch):
    """Exact trace bytes; historical stock evidence, mocked wall-clock/live SG only."""
    native=Path(os.environ['LUNAR_TRACE_NATIVE'])
    target_path=Path(os.environ['LUNAR_TRACE_TARGET'])
    review=Path(os.environ['LUNAR_TRACE_REVIEW'])
    p=install.policy_module();p.require_candidate_pins()
    inputs=dict(actual.inputs)
    inputs.update(directory=tmp_path/'trace-transaction',app_path=native/'lunar-sdk-diagnostic.app.bin',
        elf_path=native/'lunar-sdk-diagnostic.elf',audit_path=native/'sdk-image-audit.json',
        build_manifest_path=native/'build-manifest.json',trace_review_path=review)
    target=target_path.read_bytes();assert install.digest(target)==p.TARGET_SHA
    ranges=[[a,a+4096] for a in range(0x4000,0x22000,4096)]
    p.prepare_transaction(inputs['directory'],actual.baseline,actual.baseline,target,
        json.loads(inputs['identity_path'].read_bytes()),ranges)
    manifest=json.loads(inputs['manifest_path'].read_bytes())
    log=inputs['backup_log_path'].read_bytes();ended=json.loads(log.splitlines()[-1])['time']
    monkeypatch.setattr(install.time,'time',lambda:ended+1)
    config=dict(schema=1,kind=install.KIND,adapter_sha256=install.digest(Path(install.__file__).read_bytes()),
        policy_sha256=install.POLICY_SHA,policy_inputs={k:str(v) for k,v in inputs.items()},
        backup_exit_status=0,backup_commands_sha256=install.digest(log),active_session_state=install.STATE,
        sg_binding=manifest['sg_binding'],receipt_path=str(Path(actual.config['receipt_path']).with_name('test-trace-'+tmp_path.name)))
    path=tmp_path/'trace-campaign.json';path.write_bytes(rehearsal.canonical(config))
    prepared=install.prepare_campaign(path)
    assert [q.direction for q in prepared.policies]==['install','restore']
    assert prepared.policy_module.APP_SHA==policy.APP_SHA and prepared.policy_module.ELF_SHA==policy.ELF_SHA
    assert prepared.runtime.TARGET_SHA!=p.TARGET_SHA  # frozen old constant stays unchanged
    for current in prepared.policies:
        with pytest.raises(ValueError,match='instance required'):
            copy.copy(current).check_files()
    original=inputs['identity_path'].read_bytes()
    inputs['identity_path'].write_bytes(original+b' ')
    with pytest.raises(ValueError): prepared.check()
    inputs['identity_path'].write_bytes(original)
    prepared.check()
    model=SGModel(monkeypatch,config['sg_binding'],actual.baseline)
    monkeypatch.setattr(prepared.bridge,'discover_sg',model.discover)
    result=install.run_campaign(prepared)
    assert bytes(model.flash)==target and result['verified_sha256']==p.TARGET_SHA
    erases=[c['address'] for c in model.calls if c['op']==0xfb01]
    assert erases==list(range(0x5000,0x22000,4096))+[0x4000]
    assert len([c for c in model.calls if c['op']==0xfb04])==480
    assert len(model.opened)==len(model.closed)==1 and not result['boot_observed']
    full=[c for c in model.calls if c['op']==0xfd05]
    assert len(full)>=8192
    out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
    (out/'actual-trace-summary.json').write_text(json.dumps(dict(factory_unmodified=True,
        historical_backup_time_modeled=True,actual_transport_mocked=True,target_sha256=p.TARGET_SHA,
        baseline_sha256=p.BASELINE_SHA,commands=len(model.calls),erases=erases,pages_written=480,
        handle_count=len(model.opened),handle_close_count=len(model.closed),boot_observed=False,
        display_observed=False,physical_recovery_verified=False,source_sha256={
            'policy':install.digest(Path(policy.__file__).read_bytes()),
            'adapter':install.digest(Path(install.__file__).read_bytes())}),indent=2)+'\n')
    shutil.copyfile(prepared.receipt/'commands.jsonl',out/'actual-trace-commands.jsonl')
    shutil.copyfile(prepared.receipt/'result.json',out/'actual-trace-result.json')


@pytest.mark.parametrize('defect', ['nonce','app','elf','size','sdk','flashable',
    'device_operations','startup_reason','symbol_address','symbol_size',
    'undefined_symbol','duplicate_symbol','section_name','section_flags',
    'section_extent','overlapping_section'])
def test_trace_manifest_and_allocated_record_reject_incoherence(monkeypatch,defect):
    import hashlib
    manifest=dict(application_sha256=policy.APP_SHA,elf_sha256=policy.ELF_SHA,
        application_bytes=120688,sdk_commit='e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d',
        device_operations_performed=False,flashable=False,recovery_trace=dict(enabled=True,
        schema=1,nonce_hex=policy.TRACE_NONCE,record_bytes=64,startup_reason='unavailable_sentinel'))
    symbol=dict(name='lunar_sdk_recovery_trace_record',value=policy.TRACE_ADDRESS,size=64,shndx=1)
    section=dict(name='.ram0_bss',flags=2,addr=policy.TRACE_ADDRESS,size=64)
    symbols=[symbol];sections=[section]
    if defect=='nonce':manifest['recovery_trace']['nonce_hex']='0'*32
    elif defect=='app':manifest['application_sha256']='a'*64
    elif defect=='elf':manifest['elf_sha256']='a'*64
    elif defect=='size':manifest['application_bytes']+=1
    elif defect=='sdk':manifest['sdk_commit']='a'*40
    elif defect=='flashable':manifest['flashable']=True
    elif defect=='device_operations':manifest['device_operations_performed']=True
    elif defect=='startup_reason':manifest['recovery_trace']['startup_reason']='invented'
    elif defect=='symbol_address':symbol['value']+=4
    elif defect=='symbol_size':symbol['size']-=4
    elif defect=='undefined_symbol':symbol['shndx']=0
    elif defect=='duplicate_symbol':symbols.append(dict(symbol))
    elif defect=='section_name':section['name']='.text'
    elif defect=='section_flags':section['flags']=0
    elif defect=='section_extent':section['size']-=4
    elif defect=='overlapping_section':sections.append(dict(section))
    data=json.dumps(manifest).encode();monkeypatch.setattr(policy,'BUILD_MANIFEST_SHA',hashlib.sha256(data).hexdigest())
    modules={'audit_link':SimpleNamespace(Elf=lambda _:SimpleNamespace(symbols=symbols,sections=sections))}
    with pytest.raises(ValueError):policy.check_trace_manifest(data,b'modeled ELF',modules)
