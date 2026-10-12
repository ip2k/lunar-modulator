"""MIT. Real private factories with container-only NOR/SG and reset evidence.

The private SDK/ELF/stock/artifact/source checks are unmodified. The original
fixed experiment boot-campaign literal is explicitly modeled for disposable
paths; reset transmission, enumeration and connection witness are modeled.
Nothing in this file establishes physical boot, display or recovery.
"""
import copy
import ctypes as C
import json
import os
from pathlib import Path
import time

import pytest

import fm1_returned_rom_backup as backup
import fm1_returned_rom_stock_restore as restore
import fm1_diagnostic_detached_probe as proof_module
import fm1_fixed_target_reset as target_reset
import fm1_sdk_install as install
import fm1_returned_stock_reset as stock_reset
from test_sdk_rehearsal import actual, SGModel
from test_sdk_install import envelope
from test_fixed_target_reset import target_config
from test_diagnostic_stage_probe import snapshot, boot_events, Model
from test_diagnostic_detached_probe import detached_events, wire, probe_wire, owned_capture


class ReturnedSGModel(SGModel):
    """Exact read-only ROM inventory followed by inherited modeled NOR writes."""
    def open(self,path,flags,*args,**kwargs):
        if str(path)==self.mapping['node']:flags&=~os.O_NONBLOCK
        return super().open(path,flags,*args,**kwargs)

    def ioctl(self, fd, code, h):
        cdb=C.string_at(h.cmd,h.cmd_len)
        op=int.from_bytes(cdb[:2],'big')
        if h.cmd_len==16 and op in (0xFC0A,0xFD05,0xFB01,0xFB04):
            return super().ioctl(fd,code,h)
        assert fd==self.FD and code==0x2285 and h.timeout==3000
        assert h.sense_max==32 and h.iovec_count==h.flags==h.pack_id==0
        if cdb==bytes.fromhex('120000002400'):
            assert h.direction==-3 and h.data_len==36
            answer=b'\x00'*8+b'WL82    '+b'UBOOT1.00       '+b'1.00'
        elif op==0xFB06:
            assert h.direction==-2 and h.data_len==512
            address=int.from_bytes(cdb[2:6],'big')
            assert 0x1c02000<=address<0x1c07e00 and address%512==0
            answer=b''
        elif op==0xFB08:
            assert h.direction==-3 and h.data_len==16
            assert int.from_bytes(cdb[2:6],'big')==0x1c02000
            answer=cdb[:2]+b'\x00'*14
        elif op==0xFC14:
            assert h.direction==-3 and h.data_len==16
            answer=cdb[:2]+(4096).to_bytes(4,'big')+b'\x00'*10
        else:pytest.fail('Nonallowlisted modeled ROM command')
        self.calls.append(dict(op=op,address=int.from_bytes(cdb[2:6],'big') if h.cmd_len==16 else 0,
            payload=C.string_at(h.data,h.data_len) if h.direction==-2 else b'',direction=h.direction,data_len=h.data_len))
        if answer:C.memmove(h.data,answer,len(answer))
        return 0


@pytest.mark.parametrize('mode,outcome',[('successful','none'),('successful','failed'),('successful','zero'),('detached','failed'),('detached','zero'),('successful','intent-drift')])
def test_actual_private_returned_backup_restore_and_completed_helper(actual,monkeypatch,tmp_path,mode,outcome):
    assert backup.PROVENANCE_SOURCE_SHA is not None, 'Final helper pin required for actual factory gate'
    assert restore.BACKUP_SOURCE_SHA==backup.digest(Path(backup.__file__).read_bytes())
    ip=tmp_path/'install.json';envelope(ip,actual.path,actual.config['receipt_path'])
    accepted=install.prepare_campaign(ip)
    model=ReturnedSGModel(monkeypatch,json.loads(accepted.mapping),actual.baseline)
    monkeypatch.setattr(accepted.bridge,'discover_sg',model.discover)
    install.run_campaign(accepted)
    assert bytes(model.flash)==actual.target
    parent=Path(actual.config['receipt_path']).parent
    bc=target_config(actual,ip);bc['receipt_path']=str(parent/'modeled-return-boot')
    boot_run=tmp_path/'boot-run';boot_run.mkdir(mode=0o700)
    bp=boot_run/'campaign.json';bp.write_bytes(backup.canonical(bc))
    boot=target_reset.prepare_campaign(bp)
    boot_sha=backup.digest(bp.read_bytes());br=Path(bc['receipt_path']);br.mkdir(mode=0o700)
    (parent/'.target-core-reset.consumed').write_text(boot_sha)
    reset_opened=time.time()
    events=(detached_events if mode=='detached' else boot_events)(bc,boot_sha,boot.backup_manifest_sha256)
    commands=br/'commands.jsonl';commands.write_bytes(b'\n'.join(backup.canonical(e) for e in events))
    reset_exited=time.time()
    usb=dict(bc['usb_binding'],devnum=str(int(bc['usb_binding']['devnum'])+1))
    mapping=copy.deepcopy(bc['sg_binding']);mapping['usb_identity'][1]+=1;mapping['node_identity'][1]+=1
    sp=boot_run/'original-rom.json';sp.write_bytes(backup.canonical(snapshot(boot_sha,usb,mapping)))
    state=dict(schema=1,kind='fm1-exact-diagnostic-stage-probe',adapter_sha256=proof_module.SUCCESSFUL_PROBE_SHA,
        target_boot_campaign_path=str(bp),target_boot_campaign_sha256=boot_sha,
        target_boot_commands_sha256=backup.digest(commands.read_bytes()),target_boot_exit_status=0,
        rom_snapshot_path=str(sp),rom_snapshot_sha256=backup.digest(sp.read_bytes()),
        active_session_state='post-target-boot-rom-no-later-commands-no-loader-upload',
        receipt_path=str(parent/'unattempted-return-stage'))
    wrappers=Path(os.environ['LUNAR_RETURNED_WRAPPERS'])
    if mode=='detached':
        snap=json.loads(sp.read_bytes());now=time.time()
        files={'execute-once.py':(wrappers/'target-reset.py').read_bytes(),
            'wrapper-attempt.json':backup.canonical(dict(time=reset_opened,campaign_sha256=boot_sha,adapter_sha256=proof_module.TARGET_RESET_SHA,retry=False)),
            'capture-open.json':backup.canonical(dict(time=reset_opened,timeout_pid=10,cat_pid=11,process_group=10,open_capture_fd=True)),
            'execution-exit.json':backup.canonical(dict(time=reset_exited,exit_status=1,campaign_sha256=boot_sha,capture_alive_after_child=True,retry=False)),
            'capture-stop.json':backup.canonical(dict(time=now,process_group=10,returncode=-15,owned_processes_only=True)),
            'rom-observations.json':backup.canonical(dict(time=now,found=True,observations=[dict(time=snap['observed_at'],usb_binding=usb)],passive_sysfs_only=True,no_later_device_commands=True)),
            'execution.stdout':b'modeled terminal stop','usbmon3.stderr':b'','usbmon3.txt':wire(bc['usb_binding'],usb)}
        assert backup.digest(files['execute-once.py'])==proof_module.BOOT_WRAPPER_SHA
        for name,data in files.items():(boot_run/name).write_bytes(data)
        state.update(kind='fm1-exact-detached-diagnostic-stage-probe',adapter_sha256=backup.PROVENANCE_SOURCE_SHA,
            target_boot_exit_status=1,reset_outcome='transmitted-detached-not-completed',
            wrapper_files_sha256={k:backup.digest(v) for k,v in files.items()})
    probe_run=tmp_path/'probe-run';probe_run.mkdir(mode=0o700)
    state_path=probe_run/'state.json';state_path.write_bytes(backup.canonical(state))
    optional_probe=capture=admission_path=admission_sha=None
    if outcome not in ('none','intent-drift'):
        import fm1_diagnostic_stage_probe as incumbent
        module=proof_module if mode=='detached' else incumbent
        if mode=='detached':monkeypatch.setattr(module,'BOOT_CAMPAIGN_SHA',boot_sha)
        probe=module.prepare_campaign(state_path)
        probe_receipt=Path(state['receipt_path'])
        if outcome=='failed':
            probe_model=Model(probe,fault=lambda m,reply:module.Completion(reply.data,status=1))
            with pytest.raises(OSError):module.run_campaign(probe,lambda _:probe_model)
            assert len(probe_model.calls)==1
            probe_events=[json.loads(x) for x in (probe_receipt/'commands.jsonl').read_bytes().splitlines()]
        else:
            probe_receipt.mkdir(mode=0o700)
            (parent/('.diagnostic-stage-'+boot_sha+'.consumed')).write_text(backup.digest(state_path.read_bytes()))
            probe_events=[]
        capture,_=owned_capture(tmp_path,dict(state,snapshot_for_model=probe.snapshot.decode()),
            state_path,probe_events,probe_wire(usb,1) if outcome=='failed' else b'',mode=mode)
        wrapper_bytes=(wrappers/(mode+'-probe.py')).read_bytes()
        assert backup.digest(wrapper_bytes)==backup.PROBE_WRAPPER_SHAS[mode]
        (probe_run/'execute-once.py').write_bytes(wrapper_bytes)
        captured=json.loads(capture.read_bytes());captured['wrapper_files_sha256']['execute-once.py']=backup.digest(wrapper_bytes)
        capture.write_bytes(backup.canonical(captured))
        optional_probe=str(state_path);capture=str(capture)
        admission_path=str(probe_run/'preflight.json');admission_sha=backup.digest(Path(admission_path).read_bytes())
    witness=dict(schema=1,kind='fm1-passive-returned-rom-backup-connection',observed_at=time.time(),
        usb_binding=usb,sg_binding=mapping,rom_snapshot_sha256=state['rom_snapshot_sha256'],
        quiet_state='returned-rom-after-read-only-probe-no-loader-upload')
    wp=tmp_path/'connection.json';wp.write_bytes(backup.canonical(witness))
    config=dict(schema=1,kind='fm1-exact-target-returned-rom-backup',
        adapter_sha256=backup.digest(Path(backup.__file__).read_bytes()),
        **{key:state[key] for key in ('target_boot_campaign_path','target_boot_campaign_sha256',
            'target_boot_commands_sha256','target_boot_exit_status','rom_snapshot_path','rom_snapshot_sha256')},
        loader_path=str(actual.inputs['loader_path']),profile_path=str(actual.inputs['profile_path']),
        profile_source_path=str(Path(backup.__file__).parent/'jieli/loader_config_profile.py'),
        optional_stage_probe=optional_probe,active_session_state='returned-rom-no-later-commands-no-loader-upload',
        receipt_path=str(parent/'returned-target-backup'),returned_state_campaign_path=str(state_path),
        returned_state_campaign_sha256=backup.digest(state_path.read_bytes()),provenance_mode=mode,
        probe_capture_path=capture,probe_admission_path=admission_path,probe_admission_sha256=admission_sha,
        connection_witness_path=str(wp),connection_witness_sha256=backup.digest(wp.read_bytes()))
    cp=tmp_path/'backup.json';cp.write_bytes(backup.canonical(config))
    # Real pinned dependency loader executes actual source; only the fixed boot
    # experiment literal is replaced for this explicitly disposable model.
    def modeled_loader(original):
        def load(path,expected,name):
            module=original(path,expected,name)
            if Path(path)==Path(proof_module.__file__):module.BOOT_CAMPAIGN_SHA=boot_sha
            if Path(path) in (Path(backup.__file__),Path(restore.__file__)):module.load_source=modeled_loader(module.load_source)
            return module
        return load
    monkeypatch.setattr(backup,'load_source',modeled_loader(backup.load_source))
    monkeypatch.setattr(restore,'load_source',modeled_loader(restore.load_source))
    prepared=backup.prepare_campaign(cp)
    model.mapping=copy.deepcopy(mapping);model.node_identity=tuple(mapping['node_identity'])
    monkeypatch.setattr(prepared.bridge,'discover_sg',model.discover)
    before=len(model.calls);manifest=backup.run_campaign(prepared)
    assert len(model.calls)-before==8757
    rr=Path(config['receipt_path'])
    assert (rr/'dumpA.bin').read_bytes()==(rr/'dumpB.bin').read_bytes()==actual.target
    restore_config=dict(schema=1,kind='fm1-returned-rom-stock-restore-only',
        adapter_sha256=restore.digest(Path(restore.__file__).read_bytes()),
        returned_backup_campaign_path=str(cp),returned_backup_campaign_sha256=backup.digest(cp.read_bytes()),
        returned_backup_manifest_sha256=backup.digest((rr/'manifest.json').read_bytes()),
        returned_backup_commands_sha256=backup.digest((rr/'commands.jsonl').read_bytes()),returned_backup_exit_status=0,
        original_rehearsal_campaign_path=str(actual.path),original_rehearsal_campaign_sha256=backup.digest(actual.path.read_bytes()),
        install_journal_sha256=backup.digest((actual.inputs['directory']/'journal.json').read_bytes()),
        active_session_state='returned-fixed-loader-dual-target-backup-no-later-commands',receipt_path=str(rr/'stock-restore'))
    rp=tmp_path/'restore.json';rp.write_bytes(backup.canonical(restore_config))
    restored=restore.prepare_campaign(rp);monkeypatch.setattr(restored.bridge,'discover_sg',model.discover)
    before=len(model.calls)
    if outcome=='intent-drift':
        absent=restored.policies[0].absent_paths[0]
        restore_receipt=Path(restore_config['receipt_path'])
        original_sync=restored.bridge.sync_dir
        closed_before=len(model.closed)
        appeared=[]
        def synced_then_appeared(path):
            original_sync(path)
            log_path=restore_receipt/'commands.jsonl'
            if not appeared and log_path.exists() and b'"event": "sg_submit_intent"' in log_path.read_bytes():
                absent.write_text('late evidence after real durable intent sync')
                appeared.append(absent)
        monkeypatch.setattr(restored.bridge,'sync_dir',synced_then_appeared)
        with pytest.raises(ValueError,match='absent evidence'):restore.run_campaign(restored)
        assert appeared==[absent] and len(model.calls)==before
        assert model.closed[closed_before:]==[model.FD]
        assert (parent/'.returned-stock-restore.consumed').exists()
        assert not (restore_receipt/'result.json').exists()
        rows=[json.loads(x) for x in (restore_receipt/'commands.jsonl').read_bytes().splitlines()]
        assert sum(x['event']=='sg_submit_intent' for x in rows)==1
        assert rows[-1]['event']=='returned_restore_stopped_ambiguous'
        with pytest.raises(ValueError):restore.prepare_campaign(rp)
        if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
            out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
            (out/('returned-actual-'+mode+'-'+outcome+'-summary.json')).write_bytes(backup.canonical(dict(
                actual_private_inputs=True,actual_pinned_sources=True,sg_mocked=True,hardware_access=False,
                post_durable_intent_absence_drift=True,restore_ioctl_count=0,close_count=1,
                marker_preserved=True,retry=False,stock_baseline_restored=False,
                boot_observed=False,display_observed=False,physical_recovery_verified=False)))
        return
    result=restore.run_campaign(restored)
    assert bytes(model.flash)==actual.baseline and result['stock_baseline_restored']
    erases=[x['address'] for x in model.calls[before:] if x['op']==0xFB01]
    assert erases==list(range(0x5000,0x22000,4096))+[0x4000]
    restore_receipt=Path(restore_config['receipt_path']);frozen=[]
    def freeze(path,expected=None,limit=2*1048576):
        data=restore.read_file(path,limit)
        if expected is not None and restore.digest(data)!=expected:raise ValueError('actual pin')
        frozen.append((Path(path),data,limit));return data
    proof=restore.validate_completed_restore(rp,campaign_sha256=restore.digest(rp.read_bytes()),
        commands_sha256=restore.digest((restore_receipt/'commands.jsonl').read_bytes()),
        result_sha256=restore.digest((restore_receipt/'result.json').read_bytes()),
        journal_sha256=restore.digest((actual.inputs['directory']/'journal.json').read_bytes()),freeze=freeze)
    assert proof['usb_binding']==usb and proof['sg_binding']==mapping and proof['sectors_written']==30
    assert len(proof['_absent_paths'])==(2 if outcome=='none' else 3 if outcome=='failed' else 4)
    assert all(type(x) is type(Path('/')) for x in proof['_absent_paths'])
    genuine_reset_factory=False
    if mode=='successful' and outcome=='none':
        monkeypatch.setattr(stock_reset,'RESTORE_SOURCE_SHA',restore.digest(Path(restore.__file__).read_bytes()))
        monkeypatch.setattr(stock_reset,'load_source',modeled_loader(stock_reset.load_source))
        rc=dict(schema=1,kind='fm1-returned-fixed-loader-stock-reset',
            adapter_sha256=stock_reset.digest(Path(stock_reset.__file__).read_bytes()),
            restore_campaign_path=str(rp),restore_campaign_sha256=restore.digest(rp.read_bytes()),
            restore_commands_sha256=restore.digest((restore_receipt/'commands.jsonl').read_bytes()),
            restore_result_sha256=restore.digest((restore_receipt/'result.json').read_bytes()),
            restore_journal_sha256=restore.digest((actual.inputs['directory']/'journal.json').read_bytes()),
            restore_exit_status=0,active_session_state='returned-fixed-loader-stock-restored-no-later-commands',
            receipt_path=str(rr/'stock-reset-drift'))
        rcp=tmp_path/'stock-reset.json';rcp.write_bytes(backup.canonical(rc))
        reset_prepared=stock_reset.prepare_campaign(rcp)
        monkeypatch.setattr(reset_prepared.bridge,'discover_sg',model.discover)
        absent=reset_prepared.absent_paths[0];reset_receipt=Path(rc['receipt_path'])
        original_sync=reset_prepared.bridge.sync_dir;appeared=[]
        def reset_synced_then_appeared(path):
            original_sync(path)
            log_path=reset_receipt/'commands.jsonl'
            if not appeared and log_path.exists() and b'"event": "reset_submit_intent"' in log_path.read_bytes():
                absent.write_text('late negative evidence after durable reset intent sync')
                appeared.append(absent)
        monkeypatch.setattr(reset_prepared.bridge,'sync_dir',reset_synced_then_appeared)
        reset_calls,reset_closes=len(model.calls),len(model.closed)
        with pytest.raises(ValueError,match='absent'):stock_reset.run_campaign(reset_prepared)
        assert appeared==[absent] and len(model.calls)==reset_calls
        assert model.closed[reset_closes:]==[model.FD]
        assert (rr/'.returned-stock-core-reset.consumed').exists()
        rows=[json.loads(x) for x in (reset_receipt/'commands.jsonl').read_bytes().splitlines()]
        assert sum(x['event']=='reset_submit_intent' for x in rows)==1
        assert rows[-1]['event']=='reset_stopped_ambiguous'
        with pytest.raises(ValueError):stock_reset.prepare_campaign(rcp)
        genuine_reset_factory=True
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
        (out/('returned-actual-'+mode+'-'+outcome+'-summary.json')).write_bytes(backup.canonical(dict(
            provenance_mode=mode,probe_outcome=outcome,actual_private_inputs=True,actual_pinned_sources=True,boot_campaign_literal_modeled=True,
            usb_and_reset_evidence_modeled=True,sg_mocked=True,hardware_access=False,
            dual_target_readback=True,initial_full_target_gate=True,directory_last_stock_restore=True,
            completed_restore_helper=True,genuine_reset_factory=genuine_reset_factory,
            post_durable_reset_intent_drift=genuine_reset_factory,reset_ioctl_count=0 if genuine_reset_factory else None,freeze_files=len(frozen),baseline_sha256=restore.BASELINE_SHA,
            target_sha256=backup.TARGET_SHA,returned_commands=8757,restore_commands=len(model.calls)-before,
            boot_observed=False,display_observed=False,physical_recovery_verified=False)))
