"""MIT. Offline original-file lineage, with explicitly modeled upstream authority.

The focused fixture registers a unit CompletedInstall to exercise the downstream
file/wire boundary. The separate private-fixture composition test runs the real
install factory and worker; neither fixture provides physical acceptance.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_sdk_trace_boot import boot, bridge, SGHeader
from test_reset_wire import capture, envelope
from test_sdk_rehearsal import actual
from sdk_trace_fixture import genuine_completed_trace_install


def mapping(usb, generation):
    return dict(node='/dev/sgMOCK', **{'class': '/sys/class/scsi_generic/sgMOCK'},
                device='/sys/devices/mock/sgMOCK', usb='/sys/devices/mock/'+usb['path'],
                node_identity=[1, generation, 3], class_identity=[1, generation+1, 0],
                device_identity=[1, generation+2, 0], usb_identity=[1, generation+3, 0])


def config(parent, old, sg):
    return dict(schema=1, kind='fm1-fixed-loader-sdk-trace-target-reset',
        adapter_sha256=boot.IMPORTED_SOURCE_SHA256,
        install_campaign_path=str(parent/'install.json'), install_campaign_sha256='a'*64,
        install_commands_sha256='b'*64, install_result_sha256='c'*64,
        install_exit_status=0, journal_sha256='d'*64,
        active_session_state='same-fixed-loader-installed-trace-target-no-later-commands',
        usb_binding=old, sg_binding=sg, receipt_path=str(parent/'reset'),
        target_sha256=boot.TARGET_SHA, target_boot_authorization='exact-sdk-recovery-trace-diagnostic')


def lifecycle(campaign_sha):
    opened=dict(time=9, timeout_pid=100, cat_pid=101, process_group=100, open_capture_fd=True)
    stopped=dict(time=14, process_group=100, returncode=-15, owned_processes_only=True)
    exited=dict(time=11.5, campaign_sha256=campaign_sha, exit_status=1,
                capture_alive_after_child=True, retry=False,
                reset_completed_attested=False, boot_cause_proven=False)
    return opened, stopped, exited


@pytest.fixture
def lineage_files(tmp_path, monkeypatch):
    parent=tmp_path/'private'; parent.mkdir(mode=0o700)
    _, events, old, fresh=envelope()
    sg=mapping(old, 10)
    c=config(parent, old, sg); raw=boot.canonical(c); campaign_sha=boot.digest(raw)
    campaign=parent/'boot.json'; campaign.write_bytes(raw)
    receipt=parent/'reset'; receipt.mkdir(mode=0o700)
    installed_evidence=parent/'installed-evidence'; installed_evidence.write_bytes(b'unit-upstream')
    installed=boot.CompletedInstall(b'{}', 'a'*64, 8, parent, 'f'*64,
        boot.canonical(old), boot.canonical(sg), bridge, SGHeader,
        ((installed_evidence, installed_evidence.read_bytes(), 100),), ())
    boot._INSTALLS.add(installed)
    # Upstream is explicitly modeled here; downstream wire/file parsers are real.
    monkeypatch.setattr(boot, 'validate_completed_install', lambda *a, **kw: installed)
    monkeypatch.setattr(boot, 'INSTALL_SHA', '1'*64)
    monkeypatch.setattr(boot, 'POLICY_SHA', '2'*64)
    wire_path=Path(boot.__file__).with_name('fm1_reset_wire.py')
    monkeypatch.setattr(boot, 'WIRE_VERIFIER_SHA', boot.digest(wire_path.read_bytes()))
    monkeypatch.setattr(bridge, 'discover_sg', lambda _: pytest.fail('device discovery'))
    for key in ('adapter_sha256','install_campaign_sha256','install_commands_sha256',
                'target_sha256','usb_binding','sg_binding'):
        events[0][key]=c[key]
    events[0].update(campaign_sha256=campaign_sha, trace_nonce=boot.NONCE,
                     backup_manifest_sha256=installed.manifest_sha256)
    commands=receipt/'commands.jsonl'
    commands.write_bytes(b''.join(boot.canonical(e)+b'\n' for e in events))
    marker=parent/'.target-core-reset.consumed'; marker.write_text(campaign_sha)
    snapshot=dict(schema=1, kind='fm1-passive-post-trace-boot-rom', observed_at=12,
        usb_binding=fresh['usb_binding'], sg_binding=mapping(fresh['usb_binding'], 20),
        target_boot_campaign_sha256=campaign_sha,
        quiet_state='initial-rom-no-later-commands-no-loader-upload')
    opened, stopped, exited=lifecycle(campaign_sha)
    contents=dict(capture=('\n'.join(capture())+'\n').encode(),
        capture_open=boot.canonical(opened), capture_stop=boot.canonical(stopped),
        boot_exit=boot.canonical(exited), rom_snapshot=boot.canonical(snapshot))
    lineage=dict(schema=1, kind='fm1-exact-sdk-trace-boot-read-lineage',
        adapter_sha256=boot.IMPORTED_SOURCE_SHA256, boot_campaign_path=str(campaign),
        boot_campaign_sha256=campaign_sha, boot_commands_sha256=boot.digest(commands.read_bytes()),
        wire_verifier_sha256=boot.WIRE_VERIFIER_SHA)
    for name, data in contents.items():
        path=parent/(name+'.bin'); path.write_bytes(data)
        lineage[name+'_path']=str(path); lineage[name+'_sha256']=boot.digest(data)
    lineage_path=parent/'lineage.json'; lineage_path.write_bytes(boot.canonical(lineage))
    return SimpleNamespace(parent=parent, installed=installed, config=c, campaign=campaign,
        commands=commands, events=events, snapshot=snapshot, opened=opened, stopped=stopped,
        exited=exited, lineage=lineage, path=lineage_path, marker=marker)


def save_lineage(f):
    f.path.write_bytes(boot.canonical(f.lineage))


def update_original(f, name, value):
    data=value if type(value) is bytes else boot.canonical(value)
    Path(f.lineage[name+'_path']).write_bytes(data)
    f.lineage[name+'_sha256']=boot.digest(data); save_lineage(f)


def test_real_wire_and_frozen_original_files_create_only_offline_lineage(lineage_files):
    f=lineage_files; obj=boot.prepare_read_lineage(f.path)
    binding=obj.read_binding()
    assert binding['nonce_hex']==boot.NONCE and binding['boot_completed_at']==11
    assert binding['usb_binding']==f.config['usb_binding']
    assert obj.read_receipt_parent()==f.parent
    assert set(binding)=={'boot_campaign_sha256','boot_completed_at','usb_binding','sg_binding',
                         'app_sha256','elf_sha256','nonce_hex'}
    assert not hasattr(obj, 'open')
    with pytest.raises(ValueError): replace(obj).check()


@pytest.mark.parametrize('field', ['capture','capture_open','capture_stop','boot_exit','rom_snapshot'])
def test_every_original_file_stays_frozen_after_lineage_preparation(lineage_files, field):
    f=lineage_files; obj=boot.prepare_read_lineage(f.path)
    Path(f.lineage[field+'_path']).write_bytes(b'drift')
    with pytest.raises(ValueError): obj.check()


@pytest.mark.parametrize('mutation', ['consumed-marker','boot-campaign','boot-commands',
    'lineage-campaign','upstream-evidence','copied-authority'])
def test_original_authority_and_campaign_drift_rejected(lineage_files, mutation):
    f=lineage_files; obj=boot.prepare_read_lineage(f.path)
    if mutation=='consumed-marker': f.marker.write_text('0'*64)
    elif mutation=='boot-campaign': f.campaign.write_bytes(b'{}')
    elif mutation=='boot-commands': f.commands.write_bytes(b'{}')
    elif mutation=='lineage-campaign': f.path.write_bytes(b'{}')
    elif mutation=='upstream-evidence': f.installed.evidence[0][0].write_bytes(b'drift')
    else: obj=replace(obj)
    with pytest.raises(ValueError): obj.check()


@pytest.mark.parametrize('mutation', ['missing-marker','wrong-marker','receipt-mode',
    'wrong-nonce','wrong-manifest','before-install','empty-wire','second-reset','wrong-exit'])
def test_rehashed_invalid_originals_do_not_grant_lineage(lineage_files, mutation):
    f=lineage_files
    if mutation=='missing-marker': f.marker.unlink()
    elif mutation=='wrong-marker': f.marker.write_text('0'*64)
    elif mutation=='receipt-mode': Path(f.config['receipt_path']).chmod(0o755)
    elif mutation in ('wrong-nonce','wrong-manifest','before-install'):
        key={'wrong-nonce':'trace_nonce','wrong-manifest':'backup_manifest_sha256',
             'before-install':'time'}[mutation]
        f.events[0][key]=0 if key=='time' else '0'*len(f.events[0][key])
        f.commands.write_bytes(b''.join(boot.canonical(e)+b'\n' for e in f.events))
        f.lineage['boot_commands_sha256']=boot.digest(f.commands.read_bytes()); save_lineage(f)
    elif mutation=='empty-wire': update_original(f, 'capture', b'')
    elif mutation=='second-reset':
        rows=capture()+capture()
        for i in range(4,8):
            fields=rows[i].split(); fields[1]=str(108+i); rows[i]=' '.join(fields)
        update_original(f, 'capture', ('\n'.join(rows)+'\n').encode())
    else:
        f.exited['exit_status']=0; update_original(f, 'boot_exit', f.exited)
    with pytest.raises((ValueError,OSError)): boot.prepare_read_lineage(f.path)


@pytest.mark.parametrize('record,key,value', [
    ('opened','timeout_pid',True), ('opened','cat_pid',100), ('opened','process_group',102),
    ('opened','open_capture_fd',False), ('opened','time',10), ('opened','time',float('nan')),
    ('stopped','process_group',102), ('stopped','returncode',0),
    ('stopped','owned_processes_only',False), ('stopped','time',11),
    ('exited','capture_alive_after_child',False), ('exited','exit_status',True),
    ('exited','campaign_sha256','0'*64), ('exited','retry',True),
    ('exited','reset_completed_attested',True), ('exited','boot_cause_proven',True),
    ('exited','time',11), ('exited','time',13),
])
def test_owned_capture_lifecycle_rejects_false_or_unbracketed_receipts(lineage_files,record,key,value):
    f=lineage_files; opened,stopped,exited=deepcopy((f.opened,f.stopped,f.exited))
    {'opened':opened,'stopped':stopped,'exited':exited}[record][key]=value
    with pytest.raises(ValueError):
        boot.verify_capture_lifecycle(opened,stopped,exited,[10,10.1,11],f.snapshot,
                                      boot.digest(f.campaign.read_bytes()))


@pytest.mark.parametrize('mutation', ['schema-bool','old-time','future-time','quiet-state',
    'wrong-boot','wrong-port','wrong-pid','same-address','bus-mismatch','sg-missing',
    'relative-sg','bool-identity','same-node','same-usb'])
def test_original_rom_snapshot_requires_changed_full_passive_mapping(lineage_files,mutation):
    f=lineage_files; snapshot=deepcopy(f.snapshot)
    binding=dict(boot_completed_at=11,boot_campaign_sha256=boot.digest(f.campaign.read_bytes()),
                 usb_binding=f.config['usb_binding'],sg_binding=f.config['sg_binding'])
    if mutation=='schema-bool': snapshot['schema']=True
    elif mutation=='old-time': snapshot['observed_at']=10
    elif mutation=='future-time': snapshot['observed_at']=1e100
    elif mutation=='quiet-state': snapshot['quiet_state']='loader-uploaded'
    elif mutation=='wrong-boot': snapshot['target_boot_campaign_sha256']='0'*64
    elif mutation=='wrong-port': snapshot['usb_binding']['path']='3-4'
    elif mutation=='wrong-pid': snapshot['usb_binding']['pid']='c755'
    elif mutation=='same-address': snapshot['usb_binding']['devnum']='25'
    elif mutation=='bus-mismatch': snapshot['usb_binding']['busnum']='4'
    elif mutation=='sg-missing': del snapshot['sg_binding']['class']
    elif mutation=='relative-sg': snapshot['sg_binding']['node']='relative'
    elif mutation=='bool-identity': snapshot['sg_binding']['node_identity'][0]=True
    elif mutation=='same-node': snapshot['sg_binding']['node_identity']=f.config['sg_binding']['node_identity']
    else: snapshot['sg_binding']['usb_identity']=f.config['sg_binding']['usb_identity']
    with pytest.raises(ValueError): boot.verify_rom_snapshot(snapshot,binding)


@pytest.mark.parametrize('mutation', ['schema-bool','record-hash','plan-hash','order','intent',
                                      'direction','state','target'])
def test_preserved_install_journal_requires_exact_complete_sealed_record(mutation):
    from tools import fm1_flash_transaction as transaction
    plan=dict(sector_order=[0x5000,0x4000]); encoded=transaction.encoded
    journal=dict(schema=1,plan_sha256=boot.digest(encoded(plan)),sector_order=plan['sector_order'],
                 state='complete',direction='install',intent=None,verified_sha256=boot.TARGET_SHA)
    journal['record_sha256']=boot.digest(encoded(journal))
    boot.verify_install_journal(journal,plan,transaction)
    if mutation=='schema-bool': journal['schema']=True
    elif mutation=='record-hash': journal['record_sha256']='0'*64
    elif mutation=='plan-hash': journal['plan_sha256']='0'*64
    elif mutation=='order': journal['sector_order']=[0x4000,0x5000]
    elif mutation=='intent': journal['intent']={'operation':'erase','address':0x4000}
    elif mutation=='direction': journal['direction']='restore'
    elif mutation=='state': journal['state']='running'
    else: journal['verified_sha256']=boot.BASELINE_SHA
    if mutation!='record-hash':
        journal['record_sha256']=boot.digest(encoded({k:v for k,v in journal.items() if k!='record_sha256'}))
    with pytest.raises(ValueError): boot.verify_install_journal(journal,plan,transaction)


def test_genuine_install_reset_and_historical_read_lineage(actual, tmp_path, monkeypatch):
    """Production factories, private real images; modeled SG/clock/capture only."""
    import ctypes as C
    import os
    import shutil
    from tools import fm1_flash_transaction as transaction

    g=genuine_completed_trace_install(actual,tmp_path,monkeypatch)
    installed=boot.validate_completed_install(g.campaign,**g.pins)
    old=json.loads(installed.usb); sg=json.loads(installed.mapping)
    parent=installed.parent
    c=config(parent,old,sg)
    c.update(install_campaign_path=str(g.campaign),
        install_campaign_sha256=g.pins['campaign_sha256'],
        install_commands_sha256=g.pins['commands_sha256'],
        install_result_sha256=g.pins['result_sha256'],
        journal_sha256=g.pins['journal_sha256'])
    campaign=tmp_path/'genuine-boot.json'; campaign.write_bytes(boot.canonical(c))
    clock=installed.completed_at+1
    monkeypatch.setattr(boot.time,'time',lambda:clock)
    prepared=boot.prepare_campaign(campaign)
    monkeypatch.setattr(prepared.bridge,'discover_sg',g.model.discover)
    reset_calls=[]
    def reset_ioctl(fd,code,h):
        assert fd==g.model.FD and code==0x2285
        assert h.interface_id==ord('S') and h.cmd_len==16 and h.sense_max==32
        assert h.direction==-3 and h.data_len==16 and h.timeout==3000
        assert h.iovec_count==h.flags==h.pack_id==0
        command=C.string_at(h.cmd,h.cmd_len)
        assert command==boot.legacy.reset.RESET_CDB
        reset_calls.append(command.hex())
        C.memmove(h.data,command,16)
        return 0
    monkeypatch.setattr(boot.fcntl,'ioctl',reset_ioctl)
    result=boot.run_campaign(prepared)
    assert result==dict(request_completion=True,core_reset_observed=False,boot_observed=False)
    assert reset_calls==[boot.legacy.reset.RESET_CDB.hex()]
    assert len(g.model.opened)==len(g.model.closed)==2
    with pytest.raises(FileExistsError): boot.run_campaign(prepared)
    assert len(reset_calls)==1

    # This USBmon transcript and passive mapping are modeled. Production parsers
    # receive them as original files; no physical boot/RAM claim follows.
    fresh=dict(old,devnum=str(int(old['devnum'])+1))
    new_sg=deepcopy(sg)
    for key in ('node_identity','class_identity','device_identity','usb_identity'):
        new_sg[key][1]+=100
    snapshot=dict(schema=1,kind='fm1-passive-post-trace-boot-rom',observed_at=clock+0.2,
        usb_binding=fresh,sg_binding=new_sg,target_boot_campaign_sha256=prepared.campaign_sha256,
        quiet_state='initial-rom-no-later-commands-no-loader-upload')
    opened=dict(time=clock-0.1,timeout_pid=100,cat_pid=101,process_group=100,open_capture_fd=True)
    stopped=dict(time=clock+0.3,process_group=100,returncode=-15,owned_processes_only=True)
    exited=dict(time=clock+0.1,campaign_sha256=prepared.campaign_sha256,exit_status=0,
        capture_alive_after_child=True,retry=False,reset_completed_attested=False,boot_cause_proven=False)
    rows=[row.replace(':3:025:',':'+old['busnum']+':'+old['devnum'].zfill(3)+':')
          for row in capture('reply')]
    originals=dict(capture=('\n'.join(rows)+'\n').encode(),capture_open=boot.canonical(opened),
        capture_stop=boot.canonical(stopped),boot_exit=boot.canonical(exited),
        rom_snapshot=boot.canonical(snapshot))
    lineage=dict(schema=1,kind='fm1-exact-sdk-trace-boot-read-lineage',
        adapter_sha256=boot.IMPORTED_SOURCE_SHA256,boot_campaign_path=str(campaign),
        boot_campaign_sha256=prepared.campaign_sha256,
        boot_commands_sha256=boot.digest((prepared.receipt/'commands.jsonl').read_bytes()),
        wire_verifier_sha256=boot.WIRE_VERIFIER_SHA)
    for name,raw in originals.items():
        path=parent/('genuine-'+name+'.bin'); path.write_bytes(raw); path.chmod(0o600)
        lineage[name+'_path']=str(path); lineage[name+'_sha256']=boot.digest(raw)
    lineage_path=parent/'genuine-lineage.json'; lineage_path.write_bytes(boot.canonical(lineage))
    preserved=parent/'preserved-install-journal.json'
    preserved.write_bytes(g.journal.read_bytes()); preserved.chmod(0o600)
    saved=dict(install_campaign=g.campaign,install_commands=g.commands,
        install_result=g.result_path,install_marker=g.marker,
        install_journal=preserved,current_restore_journal=g.journal,
        sealed_plan=g.journal.parent/'plan.json',boot_campaign=campaign,
        boot_commands=prepared.receipt/'commands.jsonl',boot_marker=prepared.marker,
        lineage_campaign=lineage_path,**{n:Path(lineage[n+'_path']) for n in originals})
    saved_sha256={n:boot.digest(p.read_bytes()) for n,p in saved.items()}
    out=None
    if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
        out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])/'genuine-boot-model'
        out.mkdir(mode=0o700)
        for name,path in saved.items():
            destination=out/(name+'.bin'); shutil.copyfile(path,destination); destination.chmod(0o600)
        (out/'pre-lineage.json').write_bytes(boot.canonical(dict(
            schema=1,stage='before-production-read-lineage-validation',hardware_access=False,
            clock_sg_usbmon_and_passive_snapshot_modeled=True,
            saved_sha256=saved_sha256)))
    monkeypatch.setattr(boot.time,'time',lambda:clock+1)
    first=boot.prepare_read_lineage(lineage_path)
    assert first.read_binding()['boot_campaign_sha256']==prepared.campaign_sha256
    assert first.read_receipt_parent()==parent
    with pytest.raises(ValueError): replace(first).check()
    journal=json.loads(g.journal.read_bytes())
    journal.update(state='complete',direction='restore',intent=None,verified_sha256=boot.BASELINE_SHA)
    transaction.save_journal(g.journal.parent,journal)
    with pytest.raises(ValueError): first.check()
    with pytest.raises(ValueError): boot.prepare_read_lineage(lineage_path)
    historical=boot.prepare_read_lineage(lineage_path,install_journal_path=preserved)
    assert historical.read_binding()==json.loads(first.binding)
    assert len(reset_calls)==1 and len(g.model.opened)==len(g.model.closed)==2
    with pytest.raises(ValueError): replace(historical).check()
    if out is not None:
        assert {n:boot.digest((out/(n+'.bin')).read_bytes()) for n in saved}==saved_sha256
        restored=out/'post-restore-journal.json'
        shutil.copyfile(g.journal,restored); restored.chmod(0o600)
        summary=dict(schema=1,production_install_prepare_and_worker=True,
            production_boot_prepare_and_worker=True,production_read_lineage_factory=True,
            historical_read_lineage_after_current_restore=True,
            fabricated_authority=False,source_pin_overrides=False,
            clock_sg_usbmon_and_passive_snapshot_modeled=True,hardware_access=False,
            install=g.summary,reset_commands=reset_calls,
            boot_source_sha256=boot.IMPORTED_SOURCE_SHA256,
            install_source_sha256=boot.INSTALL_SHA,policy_source_sha256=boot.POLICY_SHA,
            wire_source_sha256=boot.WIRE_VERIFIER_SHA,
            boot_campaign_sha256=prepared.campaign_sha256,
            read_binding=historical.read_binding(),
            saved_sha256=saved_sha256,
            post_restore_journal_sha256=boot.digest(restored.read_bytes()))
        (out/'summary.json').write_bytes(boot.canonical(summary))
