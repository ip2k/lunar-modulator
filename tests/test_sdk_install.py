"""MIT. Install-only factory and device-free inherited transport acceptance.

The frozen rehearsal tests supply their SG model and private actual-file
fixture. Unit authority is explicitly injected; actual factory gates are real.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from test_sdk_rehearsal import actual, unit, SGModel, wire, rehearsal
import fm1_sdk_install as install


@pytest.mark.parametrize('kind', ['symlink', 'fifo', 'directory', 'oversize', 'corrupt'])
def test_bootstrap_source_refused_before_import(tmp_path, monkeypatch, kind):
    path = tmp_path/'fm1_sdk_rehearsal.py'
    if kind == 'symlink':
        path.symlink_to(rehearsal.__file__)
    elif kind == 'fifo':
        os.mkfifo(path)
    elif kind == 'directory':
        path.mkdir()
    elif kind == 'oversize':
        path.write_bytes(b'x' * (2 * 1024 * 1024 + 1))
    else:
        path.write_bytes(b'corrupt')
    monkeypatch.setattr(install, '__file__', str(tmp_path/'fm1_sdk_install.py'))
    def forbidden(*args, **kwargs):
        pytest.fail('Source rejection must precede import')
    monkeypatch.setattr(install.importlib, 'import_module', forbidden)
    with pytest.raises((OSError, ValueError)):
        install.rehearsal_module()


def test_bootstrap_fdopen_failure_closes_raw_descriptor(tmp_path, monkeypatch):
    path = tmp_path/'source.py'
    path.write_bytes(b'source')
    opened, closed = [], []
    real_open, real_close = os.open, os.close
    def open_file(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        return fd
    def close_file(fd):
        closed.append(fd)
        real_close(fd)
    def fdopen(*args, **kwargs):
        raise OSError('Mock fdopen failure')
    monkeypatch.setattr(install.os, 'open', open_file)
    monkeypatch.setattr(install.os, 'close', close_file)
    monkeypatch.setattr(install.os, 'fdopen', fdopen)
    with pytest.raises(OSError, match='Mock fdopen'):
        install.read_source(path)
    assert opened == closed and len(opened) == 1


def envelope(path, underlying_path, receipt):
    value = dict(schema=1, kind='fm1-exact-sdk-install-only',
                 adapter_sha256=rehearsal.digest(Path(install.__file__).read_bytes()),
                 rehearsal_campaign_path=str(underlying_path),
                 rehearsal_campaign_sha256=rehearsal.digest(underlying_path.read_bytes()),
                 receipt_path=str(receipt))
    path.write_bytes(rehearsal.canonical(value))
    return value


@pytest.fixture
def install_unit(unit, tmp_path, monkeypatch):
    # The fixture exercises synthetic install authority. Bind its dependency
    # to the exact checkout bytes; production's reviewed pin remains unchanged.
    monkeypatch.setattr(install, 'REHEARSAL_SHA', rehearsal.digest(
        Path(rehearsal.__file__).read_bytes()))
    old = tmp_path/'underlying.json'
    old.write_bytes(unit.prepared.config)
    path = tmp_path/'install.json'
    config = envelope(path, old, json.loads(unit.prepared.config)['receipt_path'])
    prepared = install.Prepared(rehearsal.canonical(config), rehearsal.digest(path.read_bytes()),
        path, old, rehearsal.digest(old.read_bytes()), config['adapter_sha256'],
        unit.prepared, rehearsal)
    install._AUTHORIZED.add(prepared)  # Explicit synthetic test-only authority.
    prepared.check()
    return SimpleNamespace(unit=unit, prepared=prepared, path=path, old=old)


@pytest.mark.parametrize('field', ['config', 'campaign_sha256', 'campaign_path', 'rehearsal_path',
    'rehearsal_sha256', 'adapter_sha256', 'underlying', 'runtime'])
def test_copied_install_prepared_refused_before_open(install_unit, field):
    p = install_unit.prepared
    changed = replace(p, **{field: getattr(p, field)})
    with pytest.raises(ValueError, match='Exact prepared'):
        install.run_campaign(changed)
    assert not install_unit.unit.model.opened


@pytest.mark.parametrize('field', ['campaign_path', 'rehearsal_path', 'adapter', 'rehearsal'])
def test_frozen_install_input_drift_prevents_mutation(install_unit, monkeypatch, tmp_path, field):
    p = install_unit.prepared
    transport = rehearsal.RehearsalSG(p, p.policies[0], install_unit.unit.model.log)
    if field in ('campaign_path', 'rehearsal_path'):
        getattr(p, field).write_bytes(b'corrupt')
    else:
        changed = tmp_path/'changed-source.py'
        changed.write_bytes(b'corrupt')
        monkeypatch.setattr(install if field=='adapter' else rehearsal, '__file__', str(changed))
    with pytest.raises(ValueError, match='Frozen install'):
        transport.exchange(*wire(0xFB01, 0x4000))
    assert not install_unit.unit.model.calls


def test_restore_policy_is_not_exposed_or_bindable(install_unit):
    p = install_unit.prepared
    assert len(p.policies)==1 and p.policies[0].direction=='install'
    with pytest.raises(ValueError, match='Exact prepared direction'):
        rehearsal.RehearsalSG(p, p.underlying.policies[1], install_unit.unit.model.log)
    assert not install_unit.unit.model.opened


def worker(install_unit, monkeypatch, fault=None):
    p = install_unit.prepared
    directions = []
    def bind(transport):
        def run(checkpoint):
            directions.append(transport.policy.direction)
            if fault: raise fault('Mock install failure')
            return dict(verified_sha256=rehearsal.TARGET_SHA, sectors_written=30)
        return SimpleNamespace(run=run)
    monkeypatch.setattr(p.policies[0], 'bind', bind, raising=False)
    return directions


def test_only_install_worker_runs_and_receipt_does_not_claim_boot_or_restore(install_unit, monkeypatch):
    directions = worker(install_unit, monkeypatch)
    result = install.run_campaign(install_unit.prepared)
    assert directions==['install']
    assert result['verified_sha256']==rehearsal.TARGET_SHA
    assert result['full_flash_readback_verified'] and result['stock_restore_preflighted']
    assert not any(result[k] for k in ('boot_observed','stock_baseline_restored','physical_recovery_verified'))
    assert install_unit.unit.model.closed==[SGModel.FD]


@pytest.mark.parametrize('fault', [OSError, KeyboardInterrupt])
def test_install_worker_failure_never_runs_restore(install_unit, monkeypatch, fault):
    directions = worker(install_unit, monkeypatch, fault)
    with pytest.raises(fault): install.run_campaign(install_unit.prepared)
    assert directions==['install']
    receipt = Path(json.loads(install_unit.prepared.config)['receipt_path'])
    assert not (receipt/'result.json').exists()
    assert json.loads((receipt/'commands.jsonl').read_text().splitlines()[-1])['event']=='install_stopped_ambiguous'


def test_existing_rehearsal_marker_blocks_install_without_transport(install_unit):
    marker = install_unit.unit.parent/'.sdk-rehearsal.consumed'
    marker.write_text('other campaign')
    with pytest.raises(FileExistsError): install.run_campaign(install_unit.prepared)
    assert marker.read_text()=='other campaign' and not install_unit.unit.model.opened


@pytest.mark.parametrize('fault', ['close', 'close_interrupt', 'receipt_write', 'receipt_sync', 'final_log'])
def test_install_finalization_failure_has_no_success_receipt(install_unit, monkeypatch, fault):
    worker(install_unit, monkeypatch)
    p=install_unit.prepared
    if fault in ('close','close_interrupt'):
        real = install_unit.unit.model.close
        def close(fd):
            real(fd)
            if fd==SGModel.FD:
                raise (KeyboardInterrupt if fault=='close_interrupt' else OSError)('Mock close failure')
        monkeypatch.setattr(rehearsal.os,'close',close)
    elif fault=='receipt_write':
        def dump(value, fp, **kw):
            fp.write('{"partial":')
            raise OSError('Mock receipt write failure')
        monkeypatch.setattr(install.json,'dump',dump)
    elif fault=='receipt_sync':
        real = p.bridge.sync_dir
        def sync(path):
            if (Path(path)/'result.json').exists(): raise OSError('Mock receipt sync failure')
            real(path)
        monkeypatch.setattr(p.bridge,'sync_dir',sync)
    else:
        real = p.bridge.private_file
        class LogFault:
            def __init__(self, fp): self.fp=fp
            def __enter__(self): return self
            def __exit__(self,*args): return self.fp.__exit__(*args)
            def write(self,value):
                if '"event": "install_completed"' in value: raise OSError('Mock final log failure')
                return self.fp.write(value)
            def flush(self): return self.fp.flush()
            def fileno(self): return self.fp.fileno()
        def private(path,mode='wb'):
            fp=real(path,mode)
            return LogFault(fp) if Path(path).name=='commands.jsonl' else fp
        monkeypatch.setattr(p.bridge,'private_file',private)
    with pytest.raises((OSError,KeyboardInterrupt)): install.run_campaign(p)
    receipt=Path(json.loads(p.config)['receipt_path'])
    assert not (receipt/'result.json').exists()
    assert json.loads((receipt/'commands.jsonl').read_text().splitlines()[-1])['event']=='install_stopped_ambiguous'
    assert len(install_unit.unit.model.opened)==1


@pytest.fixture
def actual_install(actual, tmp_path):
    path=tmp_path/'install-only.json'
    config=envelope(path, actual.path, actual.config['receipt_path'])
    return SimpleNamespace(actual=actual,path=path,config=config)


def test_actual_install_factory_without_transport(actual_install, monkeypatch):
    monkeypatch.setattr(rehearsal,'RehearsalSG',lambda *a:pytest.fail('Factory opened transport'))
    p=install.prepare_campaign(actual_install.path)
    assert len(p.policies)==1 and p.policies[0].direction=='install'
    assert p.underlying.policies[1].direction=='restore'
    assert p.rehearsal_sha256==rehearsal.digest(actual_install.actual.path.read_bytes())


@pytest.mark.parametrize('field', ['schema','kind','adapter_sha256','rehearsal_campaign_path',
    'rehearsal_campaign_sha256','receipt_path','extra'])
def test_actual_install_schema_fail_closed(actual_install, field):
    config=dict(actual_install.config)
    bad=dict(schema=True, kind='fm1-exact-sdk-install-restore-rehearsal', adapter_sha256='0'*64,
        rehearsal_campaign_path='relative', rehearsal_campaign_sha256='0'*64,
        receipt_path='/wrong/receipt',extra=1)
    config[field]=bad[field]
    actual_install.path.write_bytes(rehearsal.canonical(config))
    with pytest.raises(ValueError): install.prepare_campaign(actual_install.path)


def test_actual_install_complete_readback_leaves_target_and_never_restores(actual_install, monkeypatch):
    p=install.prepare_campaign(actual_install.path)
    a=actual_install.actual
    model=SGModel(monkeypatch,json.loads(p.mapping),a.baseline)
    monkeypatch.setattr(p.bridge,'discover_sg',model.discover)
    result=install.run_campaign(p)
    assert bytes(model.flash)==a.target and result['verified_sha256']==rehearsal.TARGET_SHA
    assert bytes(model.flash[:0x4000])==a.baseline[:0x4000]
    assert bytes(model.flash[0x22000:])==a.baseline[0x22000:]
    assert [c['address'] for c in model.calls if c['op']==0xFB01]==list(range(0x5000,0x22000,4096))+[0x4000]
    assert len(model.opened)==1 and model.closed==[SGModel.FD]
    receipt=Path(actual_install.config['receipt_path'])
    events=[json.loads(l) for l in (receipt/'commands.jsonl').read_text().splitlines()]
    assert not any(e.get('direction')=='restore' for e in events)
    assert all(c['op'] in (0xFC0A,0xFD05,0xFB01,0xFB04) for c in model.calls)
    assert not result['boot_observed'] and not result['stock_baseline_restored']
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        evidence=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
        for name in ('result.json','commands.jsonl'):
            shutil.copyfile(receipt/name,evidence/('actual-install-'+name))
        (evidence/'actual-install-summary.json').write_bytes(rehearsal.canonical(dict(
            hardware_access=False,mocked_sg=True,factory_source_checks_mocked=False,
            target_sha256=rehearsal.digest(bytes(model.flash)),command_count=len(model.calls),
            erases=[c['address'] for c in model.calls if c['op']==0xFB01],
            result_sha256=rehearsal.digest((receipt/'result.json').read_bytes()),
            log_sha256=rehearsal.digest((receipt/'commands.jsonl').read_bytes()))))
