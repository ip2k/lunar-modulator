"""Genuine retained V7/V2 evidence with container-only SG; no physical authority."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
CASES = ('valid', 'expired', 'future', 'usb_changed', 'sg_changed', 'before_trace',
         'old_loader_before', 'later_chain_before', 'inquiry_error', 'upload_error',
         'read_error', 'late_loader', 'late_chain', 'source_changed', 'marker_reuse',
         'receipt_corrupt')


def exercise_completed_trace_backup(monkeypatch, tmp_path, case):
    if os.environ.get('LUNAR_PREPARATION_STOP_DISPOSABLE') != '1':
        pytest.skip('Private V7/V2 evidence in disposable Hera container required')
    root = Path(__file__).resolve().parents[1]
    assert root == Path('/tmp/packet-work') and sys.platform == 'linux'
    import fm1_prepare_stop_trace_return_admission as admission
    from test_returned_rom_actual import ReturnedSGModel
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    source = root / 'tools/fm1_completed_stop_trace_backup.py'
    template = source.read_text(); pin = sha(admission.__file__)
    assert template.count('PROOF_SOURCE_SHA = None') == 1
    proposal = template.replace('PROOF_SOURCE_SHA = None', 'PROOF_SOURCE_SHA = ' + repr(pin))
    assert proposal.replace('PROOF_SOURCE_SHA = ' + repr(pin), 'PROOF_SOURCE_SHA = None') == template
    source.write_text(proposal)
    import fm1_completed_stop_trace_backup as backup
    run = Path('/home/claude/fm1-stop-trace-capture-v2-20261012/run')
    completed = tmp_path / 'completed.json'
    completed.write_bytes(admission.canonical(dict(schema=1,
        kind='fm1-completed-stop-trace-returned-state', adapter_sha256=sha(admission.__file__),
        native_campaign_path=str(run / 'campaign.json'), native_campaign_sha256=sha(run / 'campaign.json'),
        owned_capture_path=str(run / 'owned-capture.json'), owned_capture_sha256=sha(run / 'owned-capture.json'))))
    proof = admission.validate_completed_stop_trace(completed)
    snapshot = json.loads(proof.stop.snapshot)
    policy = json.loads(proof.lineage.installed.config)['policy_inputs']
    assets = json.loads(Path(policy['campaign_path']).read_bytes())
    witness = dict(schema=1, kind='fm1-passive-sdk-completed-stop-trace-backup-connection',
        observed_at=time.time(), usb_binding=snapshot['usb_binding'], sg_binding=snapshot['sg_binding'],
        original_rom_snapshot_sha256=proof.stop.snapshot_sha256,
        completed_trace_sha256=sha(completed), quiet_state=backup.STATE)
    if case == 'expired': witness['observed_at'] -= 121
    if case == 'future': witness['observed_at'] += 3600
    if case == 'usb_changed': witness['usb_binding']['devnum'] = '11'
    if case == 'sg_changed': witness['sg_binding']['node_identity'][1] += 1
    if case == 'before_trace': witness['observed_at'] = proof.terminal_at - 1
    wp = tmp_path / 'witness.json'; wp.write_bytes(backup.canonical(witness))
    campaign = dict(schema=1, kind=backup.KIND, adapter_sha256=sha(source),
        completed_trace_path=str(completed), completed_trace_sha256=sha(completed),
        connection_witness_path=str(wp), connection_witness_sha256=sha(wp),
        active_session_state=backup.STATE,
        receipt_path=str(proof.lineage.parent / 'modeled-completed-trace-backup'),
        **{key:assets[key] for key in ('loader_path','profile_path','profile_source_path')})
    cp = tmp_path / 'backup.json'; cp.write_bytes(backup.canonical(campaign))
    boot_sha = proof.lineage.read_binding()['boot_campaign_sha256']
    old_marker = proof.lineage.parent / ('.sdk-preparation-stop-loader-' + boot_sha + '.consumed')
    late_chain = proof.stop.chain / '09-unexpected.intent.json'
    if case == 'old_loader_before': old_marker.write_text('later loader')
    if case == 'later_chain_before': late_chain.write_text('{}')
    if case in ('expired','future','usb_changed','sg_changed','before_trace','old_loader_before','later_chain_before'):
        with pytest.raises(ValueError): backup.prepare_campaign(cp)
        assert not Path(campaign['receipt_path']).exists()
        return
    prepared = backup.prepare_campaign(cp)
    target = (Path(policy['directory']) / 'target.bin').read_bytes()
    model = ReturnedSGModel(monkeypatch, snapshot['sg_binding'], target)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    original_ioctl = model.ioctl
    def ioctl(fd, code, header):
        next_index = len(model.calls)
        if ((case == 'inquiry_error' and next_index == 0) or
            (case == 'upload_error' and next_index == 1) or
            (case == 'read_error' and next_index == 60)):
            raise OSError('modeled transport interruption')
        result = original_ioctl(fd, code, header)
        if next_index == 0:
            if case == 'late_loader': old_marker.write_text('later loader')
            if case == 'late_chain': late_chain.write_text('{}')
            if case == 'source_changed': source.write_text(source.read_text()+'\n# changed\n')
        return result
    monkeypatch.setattr(backup.fcntl, 'ioctl', ioctl)
    receipt = Path(campaign['receipt_path'])
    if case in ('inquiry_error','upload_error','read_error','late_loader','late_chain','source_changed'):
        with pytest.raises((OSError,ValueError)): backup.run_campaign(prepared)
        assert not (receipt / 'manifest.json').exists()
        assert len(model.calls) <= 60
        calls = len(model.calls)
        with pytest.raises(ValueError): backup.prepare_campaign(cp)
        assert len(model.calls) == calls
    else:
        result = backup.run_campaign(prepared)
        assert len(model.calls) == 8757
        assert result['current_flash_sha256'] == backup.TARGET_SHA
        assert result['physical_recovery_verified'] is False
        assert (receipt / 'dumpA.bin').read_bytes() == (receipt / 'dumpB.bin').read_bytes() == target
        with pytest.raises(ValueError): backup.prepare_campaign(cp)
        def freeze(path, pin=None, limit=2*1048576):
            raw = backup.read_file(path,limit)
            if pin is not None and backup.digest(raw) != pin: raise ValueError('Changed receipt')
            return raw
        pins = dict(campaign_sha256=sha(cp),manifest_sha256=sha(receipt/'manifest.json'),
                    commands_sha256=sha(receipt/'commands.jsonl'))
        if case == 'receipt_corrupt':
            (receipt / 'commands.jsonl').write_bytes((receipt / 'commands.jsonl').read_bytes()+b'{}\n')
            with pytest.raises(ValueError): backup.validate_completed_backup(cp,freeze=freeze,**pins)
        else:
            evidence = backup.validate_completed_backup(cp,freeze=freeze,**pins)
            assert evidence['target_sha256'] == backup.TARGET_SHA
    assert all(call['op'] not in (0xFB01,0xFB04,0xFC0C) for call in model.calls)
    assert bytes(model.flash) == target
    return dict(backup=backup, proof=proof, model=model, campaign_path=cp,
                campaign=campaign, policy=policy, sha=sha, target=target)


@pytest.mark.parametrize('case', CASES)
def test_completed_trace_backup_actual(monkeypatch, tmp_path, case):
    exercise_completed_trace_backup(monkeypatch, tmp_path, case)
