"""Disposable genuine retained-partial model; no authority or source overrides.

Actual canonical trace install and new partial factories/workers run unchanged.
Only historical clock, passive discovery, device syscalls and owned capture are
modeled. Requires independently bound dependency literals and actual wrapper
sources; this helper does not invent missing production acquisition provenance.
"""
import ctypes
import json
import os
from pathlib import Path
from types import SimpleNamespace


def _write(path, value):
    path.write_bytes(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n')
    return path


def model_capture(tmp, *, wrapper, adapter, campaign, config, usb, calls,
                  epoch, kind, status, terminal=False):
    """Explicitly modeled lifecycle/BOT; never evidence of a real owned process."""
    from tools import fm1_partial_nor_prefix as prefix
    run=tmp;run.mkdir(mode=0o700)
    adapter=Path(adapter).absolute();wrapper=Path(wrapper).absolute()
    stage=adapter.parent.parent
    sources={'tools/'+p.name:prefix.digest(p.read_bytes()) for p in adapter.parent.glob('fm1_*.py')}
    packet=_write(run/'packet.json',dict(schema=1,kind=kind,campaign_path=str(campaign),
        campaign_sha256=prefix.digest(campaign.read_bytes()),adapter_path=str(adapter),
        adapter_sha256=prefix.digest(adapter.read_bytes()),source_pins=sources,usb_binding=usb))
    csha=prefix.digest(campaign.read_bytes());asha=prefix.digest(adapter.read_bytes())
    _write(run/'wrapper-attempt.json',dict(schema=1,kind=kind,time=epoch-2,campaign_sha256=csha,adapter_sha256=asha,retry=False))
    _write(run/'capture-open.json',dict(schema=1,time=epoch-1,timeout_pid=5001,cat_pid=5002,process_group=5001,open_capture_fd=True))
    _write(run/'execution-exit.json',dict(schema=1,time=epoch+2,child_started_at=epoch-.5,child_finished_at=epoch+1,
        exit_status=status,campaign_sha256=csha,adapter_sha256=asha,capture_alive_after_child=True,retry=False))
    _write(run/'capture-stop.json',dict(schema=1,time=epoch+3,process_group=5001,returncode=-15,owned_processes_only=True))
    (run/'execution.stdout').write_bytes(b'Explicitly modeled child; no process/device claim.\n')
    (run/'usbmon1.stderr').write_bytes(b'')
    lines=[];tick=0
    def pair(direction,size,data=b'',failed=False):
        nonlocal tick
        token=f'{tick:016x}';endpoint=f"{direction}:{usb['busnum']}:{int(usb['devnum']):03d}:1"
        def line(action,code,length,body):
            nonlocal tick
            suffix=(' = '+body[:32].hex()) if body else ''
            lines.append(f'{token} {tick} {action} {endpoint} {code} {length}{suffix}\n');tick+=1
        line('S',-115,size,data if direction=='Bo' else b'')
        line('C',-5 if failed else 0,0 if failed else size,b'' if failed or direction=='Bo' else data)
    for i,call in enumerate(calls):
        op,address,payload=call['op'],call['address'],call['payload']
        cdb,payload,size=prefix.wire(op,address if op!=0xFC0A else 0,payload)
        tag=(i+1).to_bytes(4,'little')
        cbw=b'USBC'+tag+(len(payload)or size).to_bytes(4,'little')+bytes((0 if payload else 128,0,16))+cdb
        pair('Bo',31,cbw)
        failed=terminal and i==len(calls)-1
        pair('Bo' if payload else 'Bi',len(payload)or size,payload if payload else call['response'],failed)
        if not failed:pair('Bi',13,b'USBS'+tag+bytes(5))
    (run/'usbmon1.txt').write_text(''.join(lines))
    return dict(wrapper_path=str(wrapper),packet_path=str(packet),run=str(run))


def genuine_partial_recovery(actual,tmp_path,monkeypatch,fault):
    """Caught actual INSTALL -> no-upload dual reads -> real partial->stock."""
    assert os.environ.get('LUNAR_REHEARSAL_DISPOSABLE')=='1'
    from test_sdk_rehearsal import SGModel,rehearsal
    import fm1_sdk_trace_install as install
    from tools import fm1_retained_partial_recovery as partial
    prefix_path=Path(partial.__file__).with_name('fm1_partial_nor_prefix.py')
    install_wrapper=Path(os.environ['LUNAR_PARTIAL_INSTALL_CAPTURE'])
    acquire_wrapper=Path(os.environ['LUNAR_PARTIAL_ACQUIRE_CAPTURE'])
    assert partial.PREFIX_SHA==partial.digest(prefix_path.read_bytes()), 'Reviewed prefix literal must be bound, never patched'
    assert partial.digest(Path(partial.__file__).read_bytes())=='40918ea61c2c59a13a792a801b978bb93892982459f778855cc4cc01a4174034', 'Exact reviewed successor source required, never patched'
    assert partial.INSTALL_CAPTURE_SHA=='7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b', 'Historical capture literal remains unchanged'
    assert partial.INSTALL_CAPTURE_SUCCESSOR_SHA=='59b8e8c23f494f0ac6c89585786f72a9b408d5692e2a5fbf66c2c0376945c52d'==partial.digest(install_wrapper.read_bytes()), 'Exact reviewed successor wrapper bytes required'
    assert partial.ACQUIRE_CAPTURE_SHA==partial.digest(acquire_wrapper.read_bytes())
    native=Path(os.environ['LUNAR_TRACE_NATIVE']);target=Path(os.environ['LUNAR_TRACE_TARGET']).read_bytes()
    policy=install.policy_module();policy.require_candidate_pins()
    inputs=dict(actual.inputs);inputs.update(directory=tmp_path/'partial-original-transaction',app_path=native/'lunar-sdk-diagnostic.app.bin',
        elf_path=native/'lunar-sdk-diagnostic.elf',audit_path=native/'sdk-image-audit.json',build_manifest_path=native/'build-manifest.json',
        trace_review_path=Path(os.environ['LUNAR_TRACE_REVIEW']))
    policy.prepare_transaction(inputs['directory'],actual.baseline,actual.baseline,target,json.loads(inputs['identity_path'].read_bytes()),
        [[a,a+4096] for a in range(0x4000,0x22000,4096)])
    manifest=json.loads(inputs['manifest_path'].read_bytes());backup=inputs['backup_log_path'].read_bytes()
    epoch=json.loads(backup.splitlines()[-1])['time']+10
    monkeypatch.setattr(install.time,'time',lambda:epoch)
    receipt=Path(actual.config['receipt_path']).with_name('retained-partial-'+tmp_path.name)
    config=dict(schema=1,kind=install.KIND,adapter_sha256=install.digest(Path(install.__file__).read_bytes()),policy_sha256=install.POLICY_SHA,
        policy_inputs={k:str(v) for k,v in inputs.items()},backup_exit_status=0,backup_commands_sha256=install.digest(backup),
        active_session_state=install.STATE,sg_binding=manifest['sg_binding'],receipt_path=str(receipt))
    campaign=_write(tmp_path/'install.json',config);prepared=install.prepare_campaign(campaign)
    class Model(SGModel):
        faulted=False
        def ioctl(self,fd,code,h):
            value=super().ioctl(fd,code,h)
            self.calls[-1]['response']=ctypes.string_at(h.data,h.data_len) if h.direction==-3 else b''
            if not self.faulted and self.calls[-1]['op']==(0xFB01 if fault=='erase' else 0xFB04):
                self.faulted=True
                raise OSError('Modeled syscall after physical mutation, no completion')
            return value
    model=Model(monkeypatch,config['sg_binding'],actual.baseline)
    monkeypatch.setattr(prepared.bridge,'discover_sg',model.discover)
    try:install.run_campaign(prepared)
    except OSError:pass
    else:raise AssertionError('Actual installer must catch injected mutation stop')
    assert model.faulted and prepared.marker.read_text()==prepared.campaign_sha256
    assert len(model.opened)==len(model.closed)==1 and not (receipt/'result.json').exists()
    stopped_bytes=bytes(model.flash);original_calls=tuple(model.calls)
    owned=model_capture(tmp_path/'install-capture',wrapper=install_wrapper,adapter=install.__file__,campaign=campaign,config=config,
        usb=manifest['usb_binding'],calls=original_calls,epoch=epoch,kind='fm1-sdk-trace-install-one-shot',status=1,terminal=True)
    stopped=_write(tmp_path/'stopped.json',dict(schema=1,kind='fm1-retained-fixed-loader-caught-partial',adapter_sha256=partial.digest(Path(partial.__file__).read_bytes()),
        direction='install',original_campaign_path=str(campaign),original_campaign_sha256=prepared.campaign_sha256,
        commands_sha256=partial.digest((receipt/'commands.jsonl').read_bytes()),journal_sha256=partial.digest((inputs['directory']/'journal.json').read_bytes()),
        capture=owned,quiet_state='caught-child-stopped-same-fixed-loader-no-later-commands'))
    lineage=partial.validate_stopped(stopped)
    assert lineage.prefix.initial_verified and lineage.prefix.uncertainty and not lineage.prefix.final_verified
    partial_source=partial.digest(Path(partial.__file__).read_bytes())
    def current_witness(name):
        return _write(tmp_path/name,dict(schema=1,kind='fm1-current-retained-fixed-loader',observed_at=epoch,
            usb_binding=manifest['usb_binding'],sg_binding=manifest['sg_binding'],original_campaign_sha256=prepared.campaign_sha256,
            quiet_state='same-original-fixed-loader-no-later-commands'))
    witness=current_witness('acquire-witness.json')
    acquisition_campaign=_write(tmp_path/'acquire.json',dict(schema=1,kind='fm1-retained-partial-dual-read',adapter_sha256=partial_source,
        stopped_path=str(stopped),stopped_sha256=partial.digest(stopped.read_bytes()),witness_path=str(witness),witness_sha256=partial.digest(witness.read_bytes()),
        receipt_path=str(receipt.parent/'partial-acquire')))
    acq=partial.prepare_acquisition(acquisition_campaign);monkeypatch.setattr(acq.bridge,'discover_sg',model.discover)
    start=len(model.calls);partial.run_acquisition(acq);acquire_calls=tuple(model.calls[start:])
    assert len(acquire_calls)==8707 and all(c['op'] in (0xFC0A,0xFD05) for c in acquire_calls)
    assert (acq.receipt/'dumpA.bin').read_bytes()==(acq.receipt/'dumpB.bin').read_bytes()==stopped_bytes
    acquired_capture=model_capture(tmp_path/'acquire-capture',wrapper=acquire_wrapper,adapter=partial.__file__,campaign=acquisition_campaign,config={},
        usb=manifest['usb_binding'],calls=acquire_calls,epoch=epoch,kind='fm1-retained-partial-acquire-one-shot',status=0)
    acquired=partial.validate_acquisition(acquisition_campaign,campaign_sha256=acq.campaign_sha256,
        manifest_sha256=partial.digest((acq.receipt/'manifest.json').read_bytes()),commands_sha256=partial.digest((acq.receipt/'commands.jsonl').read_bytes()),capture_inputs=acquired_capture)
    directory=tmp_path/'fresh-partial-to-stock';partial.create_restore_transaction(directory,acquired)
    witness=current_witness('restore-witness.json')
    restore_campaign=_write(tmp_path/'restore.json',dict(schema=1,kind='fm1-retained-partial-to-stock-only',adapter_sha256=partial_source,
        acquisition_campaign_path=str(acquisition_campaign),acquisition_campaign_sha256=acq.campaign_sha256,
        acquisition_manifest_sha256=partial.digest((acq.receipt/'manifest.json').read_bytes()),acquisition_commands_sha256=partial.digest((acq.receipt/'commands.jsonl').read_bytes()),
        acquisition_capture=acquired_capture,acquisition_receipt=str(acq.receipt),directory=str(directory),witness_path=str(witness),witness_sha256=partial.digest(witness.read_bytes()),
        receipt_path=str(acq.receipt/'partial-stock-restore')))
    restore=partial.prepare_restore(restore_campaign);monkeypatch.setattr(restore.bridge,'discover_sg',model.discover)
    start=len(model.calls);result=partial.run_restore(restore)
    assert bytes(model.flash)==actual.baseline and result['verified_sha256']==partial.STOCK_SHA
    restored=model.calls[start:];mutations=[c for c in restored if c['op'] in (0xFB01,0xFB04)]
    assert all(c['address']//4096*4096==0x5000 for c in mutations)
    assert len(model.opened)==len(model.closed)==3
    assert result['stock_baseline_restored'] and not result['physical_recovery_verified'] and not result['boot_observed']
    summary=dict(schema=1,fault=fault,actual_factories=True,authority_overrides=False,hardware_access=False,
        clock_syscalls_and_capture_modeled=True,original_commands=len(original_calls),acquired_commands=len(acquire_calls),
        stock_restore_commands=len(restored),uncertain_ranges=[list(x) for x in lineage.prefix.uncertainty],
        partial_sha256=partial.digest(stopped_bytes),final_stock_sha256=partial.digest(bytes(model.flash)),closed_handles=3)
    _write(tmp_path/'genuine-retained-partial-summary.json',summary)
    return SimpleNamespace(summary=summary,lineage=lineage,acquired=acquired,restore=restore,result=result,model=model,stopped=stopped)
