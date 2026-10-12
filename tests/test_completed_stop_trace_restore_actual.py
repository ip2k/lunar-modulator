"""Container-only genuine completed-trace backup/restore composition and faults."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_helper_spec = importlib.util.spec_from_file_location(
    "completed_trace_backup_helper", Path(__file__).with_name("test_completed_stop_trace_backup_actual.py"))
_helper = importlib.util.module_from_spec(_helper_spec)
_helper_spec.loader.exec_module(_helper)
exercise_completed_trace_backup = _helper.exercise_completed_trace_backup

CASES = ('valid','interrupted_program','corrupted_readback','later_chain_before_erase',
         'backup_pin','manifest_pin','commands_pin','exit_status','journal_pin',
         'state','kind','install_pin','source_pin','existing_receipt','unregistered','replay')


@pytest.mark.parametrize('case', CASES)
def test_completed_trace_restore_actual(monkeypatch,tmp_path,case):
    ctx = exercise_completed_trace_backup(monkeypatch,tmp_path,'valid')
    backup,proof,model,sha = (ctx[n] for n in ('backup','proof','model','sha'))
    root = Path(backup.__file__).parent
    source = root / 'fm1_completed_stop_trace_restore.py'
    template = source.read_text(); pin = sha(backup.__file__)
    assert template.count('BACKUP_SOURCE_SHA = None') == 1
    proposal = template.replace('BACKUP_SOURCE_SHA = None','BACKUP_SOURCE_SHA = '+repr(pin))
    assert proposal.replace('BACKUP_SOURCE_SHA = '+repr(pin),'BACKUP_SOURCE_SHA = None') == template
    source.write_text(proposal)
    import fm1_completed_stop_trace_restore as restore
    receipt = Path(ctx['campaign']['receipt_path'])
    original = json.loads(proof.lineage.installed.config)
    # Read the actual boot configuration from frozen canonical evidence.
    boot_sha = proof.lineage.read_binding()['boot_campaign_sha256']
    boot = json.loads(next(raw for path,raw,limit in proof.lineage.evidence if sha(path)==boot_sha))
    cp = tmp_path / 'restore.json'
    c = dict(schema=1,kind='fm1-sdk-completed-stop-trace-stock-restore-only',adapter_sha256=sha(source),
        returned_backup_campaign_path=str(ctx['campaign_path']),returned_backup_campaign_sha256=sha(ctx['campaign_path']),
        returned_backup_manifest_sha256=sha(receipt/'manifest.json'),returned_backup_commands_sha256=sha(receipt/'commands.jsonl'),
        returned_backup_exit_status=0,original_install_campaign_path=boot['install_campaign_path'],
        original_install_campaign_sha256=sha(boot['install_campaign_path']),install_journal_sha256=boot['journal_sha256'],
        active_session_state='completed-stop-trace-fixed-loader-dual-target-backup-no-later-commands',
        receipt_path=str(receipt/'stock-restore'))
    pins={'backup_pin':'returned_backup_campaign_sha256','manifest_pin':'returned_backup_manifest_sha256',
          'commands_pin':'returned_backup_commands_sha256','journal_pin':'install_journal_sha256',
          'install_pin':'original_install_campaign_sha256','source_pin':'adapter_sha256'}
    if case in pins:c[pins[case]]='0'*64
    if case=='exit_status':c['returned_backup_exit_status']=1
    if case=='state':c['active_session_state']='other'
    if case=='kind':c['kind']='other'
    if case=='existing_receipt':Path(c['receipt_path']).mkdir(mode=0o700)
    cp.write_bytes(restore.canonical(c))
    before=len(model.calls)
    if case in (*pins,'exit_status','state','kind','existing_receipt'):
        with pytest.raises(ValueError):restore.prepare_campaign(cp)
        assert len(model.calls)==before and bytes(model.flash)==ctx['target']
        return
    prepared=restore.prepare_campaign(cp)
    if case=='unregistered':
        with pytest.raises(ValueError):restore.require_prepared(restore.Prepared(None,None,None))
        assert len(model.calls)==before
        return
    injected=[]
    def after_ioctl():
        command=model.calls[-1]
        if case=='interrupted_program' and command['op']==0xFB04 and not injected:
            injected.append(True);raise OSError('modeled disconnect after accepted program')
        if case=='corrupted_readback' and command['op']==0xFB04 and not injected:
            injected.append(True);model.flash[command['address']]^=1
        if case=='later_chain_before_erase' and command['op']==0xFD05 and not injected:
            injected.append(True);(proof.stop.chain/'09-unexpected.intent.json').write_text('{}')
    model.after_ioctl=after_ioctl
    if case in ('interrupted_program','corrupted_readback','later_chain_before_erase'):
        with pytest.raises((ValueError,OSError)):restore.run_campaign(prepared)
        assert injected and not (Path(c['receipt_path'])/'result.json').exists()
        stopped=len(model.calls)
        with pytest.raises((ValueError,FileExistsError)):restore.run_campaign(prepared)
        with pytest.raises(ValueError):restore.prepare_campaign(cp)
        assert len(model.calls)==stopped
        assert all(call['op']!=0xFC0C for call in model.calls[before:])
        if case=='later_chain_before_erase':
            assert bytes(model.flash)==ctx['target']
            assert all(call['op'] not in (0xFB01,0xFB04) for call in model.calls[before:])
        else:assert hashlib.sha256(model.flash).hexdigest()!=restore.BASELINE_SHA
        return
    result=restore.run_campaign(prepared)
    assert result['full_flash_readback_verified'] is True and result['sectors_written']==30
    assert result['boot_observed'] is result['physical_recovery_verified'] is False
    assert hashlib.sha256(model.flash).hexdigest()==restore.BASELINE_SHA
    assert [call['address'] for call in model.calls if call['op']==0xFB01]==list(range(0x5000,0x22000,4096))+[0x4000]
    r=Path(c['receipt_path']);journal=Path(ctx['policy']['directory'])/'journal.json'
    def freeze(path,pin=None,limit=2*1048576):
        raw=restore.read_file(path,limit)
        if pin is not None and restore.digest(raw)!=pin:raise ValueError('changed evidence')
        return raw
    stopped=len(model.calls)
    evidence=restore.validate_completed_restore(cp,campaign_sha256=sha(cp),commands_sha256=sha(r/'commands.jsonl'),
        result_sha256=sha(r/'result.json'),journal_sha256=sha(journal),freeze=freeze)
    assert evidence['baseline_sha256']==restore.BASELINE_SHA and len(model.calls)==stopped
    with pytest.raises((ValueError,FileExistsError)):restore.run_campaign(prepared)
    with pytest.raises(ValueError):restore.prepare_campaign(cp)
    assert len(model.calls)==stopped
