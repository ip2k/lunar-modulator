"""MIT. Closed successor receipt/capture admission, no hardware or opener."""
from dataclasses import replace
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

import fm1_stopped_choice_recovery_evidence as evidence
import fm1_diagnostic_stage_resume as stage
import fm1_diagnostic_detached_probe as helper


def log_bytes(events):
    return b''.join(evidence.canonical(event) + b'\n' for event in events)


@pytest.fixture
def receipt_case(tmp_path):
    stamp = time.time() - 100
    campaign = dict(receipt_path=str(tmp_path), witness_sha256='1'*64)
    campaign_sha = '2'*64
    first = dict(event='resumed_stage_probe_prepared', campaign_sha256=campaign_sha,
        original_rom_snapshot_sha256=stage.SNAPSHOT_SHA,
        choice_stop_sha256=stage.CHOICE_PINS['chooser-stopped-ambiguous.json'],
        current_witness_sha256=campaign['witness_sha256'], original_snapshot_refreshed=False,
        commands=2, upload_operations=0, flash_operations=0, reset_operations=0,
        kernel_exclusivity=False)
    raw = bytes(32); decoded = helper.decode_stage(raw); inquiry_sha = '3'*64
    result = dict(campaign_sha256=campaign_sha, raw_sha256=evidence.digest(raw),
        decoded_sha256=evidence.digest(decoded), inquiry_sha256=inquiry_sha,
        current_witness_sha256=campaign['witness_sha256'], original_rom_snapshot_sha256=stage.SNAPSHOT_SHA,
        choice_stop_sha256=stage.CHOICE_PINS['chooser-stopped-ambiguous.json'],
        original_snapshot_refreshed=False, target_reset_outcome='transmitted-detached-not-completed',
        reset_request_completed=False, **helper.interpret_stage(decoded))
    events = [first]
    for index, (cdb, _, size) in enumerate(stage.OPERATIONS):
        events.extend((dict(event='sg_submit_intent',index=index,cdb=cdb.hex(),out_len=0,in_len=size,retry=False),
            dict(event='sg_completion',index=index,status=0,masked=0,msg=0,host=0,driver=0,resid=0,
                info=0,sense_len=0,sense_hex='',response_sha256=inquiry_sha if index==0 else evidence.digest(raw),retry=False)))
    events.append(dict(event='stage_capture_completed',**result,retry=False))
    for index, event in enumerate(events): event['time'] = stamp + index
    files = {'raw.bin':raw,'decoded.bin':decoded,'result.json':evidence.canonical(result)}
    def freeze(path, expected=None, limit=2*1048576):
        data = files[Path(path).name]
        assert len(data) <= limit
        if expected is not None: assert evidence.digest(data) == expected
        return data
    def verify(events=events, absent=None):
        return evidence.verify_receipt(log_bytes(events),campaign,campaign_sha,stage,helper,freeze,
            [] if absent is None else absent)
    return SimpleNamespace(events=events, files=files, verify=verify, stamp=stamp, campaign=campaign)


def stop_event(stamp):
    return dict(event='stage_probe_stopped_ambiguous',error='OSError',retry=False,
        classification='inconclusive',display_observed=False,physical_recovery_verified=False,time=stamp)


def test_complete_exact_read_is_evidence_only(receipt_case):
    proof = receipt_case.verify()
    assert proof['outcome'] == 'completed-two-read' and proof['intents'] == 2
    assert proof['result']['reset_request_completed'] is False


@pytest.mark.parametrize('cut', [1,2,3,4,5,6])
def test_every_caught_read_prefix_is_inconclusive(receipt_case, cut):
    events = copy.deepcopy(receipt_case.events[:cut]); events.append(stop_event(receipt_case.stamp+10))
    absent = []; proof = receipt_case.verify(events, absent)
    assert proof['outcome'] == 'stopped-read-only-inconclusive'
    assert absent == [Path(receipt_case.campaign['receipt_path'])/'result.json']


@pytest.mark.parametrize('field', ['status','masked','msg','host','driver','resid','info','sense_len'])
def test_failed_completion_is_terminal_and_cannot_continue(receipt_case, field):
    events = copy.deepcopy(receipt_case.events[:3]); events[2][field] = 1
    if field == 'sense_len': events[2]['sense_hex'] = '00'
    events.append(stop_event(receipt_case.stamp+10))
    assert receipt_case.verify(events)['outcome'] == 'stopped-read-only-inconclusive'
    events.insert(3, copy.deepcopy(receipt_case.events[3]))
    with pytest.raises(ValueError): receipt_case.verify(events)


@pytest.mark.parametrize('fault', ['extra','wrong-index','wrong-cdb','upload','retry','outbound',
    'size','first-snapshot','first-refreshed','first-upload','completion-hash','completion-type',
    'sense-size','time-order','time-nan','time-bool','time-future','raw','decoded','result','stop-success'])
def test_receipt_adversarial_drift_rejected(receipt_case, fault):
    events = copy.deepcopy(receipt_case.events)
    if fault == 'extra': events.append(copy.deepcopy(events[-1]))
    elif fault == 'wrong-index': events[1]['index'] = True
    elif fault == 'wrong-cdb': events[1]['cdb'] = '00'*6
    elif fault == 'upload': events[1]['cdb'] = 'fb06'+'00'*14
    elif fault == 'retry': events[1]['retry'] = True
    elif fault == 'outbound': events[1]['out_len'] = 1
    elif fault == 'size': events[1]['in_len'] = 37
    elif fault == 'first-snapshot': events[0]['original_rom_snapshot_sha256'] = '0'*64
    elif fault == 'first-refreshed': events[0]['original_snapshot_refreshed'] = True
    elif fault == 'first-upload': events[0]['upload_operations'] = 1
    elif fault == 'completion-hash': events[4]['response_sha256'] = '0'*64
    elif fault == 'completion-type': events[2]['host'] = False
    elif fault == 'sense-size': events[2]['sense_len'] = 1
    elif fault == 'time-order': events[3]['time'] = receipt_case.stamp-1
    elif fault == 'time-nan': events[2]['time'] = float('nan')
    elif fault == 'time-bool': events[2]['time'] = False
    elif fault == 'time-future': events[-1]['time'] = time.time()+100
    elif fault == 'raw': receipt_case.files['raw.bin'] = bytes(31)
    elif fault == 'decoded': receipt_case.files['decoded.bin'] = bytes(31)
    elif fault == 'result': receipt_case.files['result.json'] = b'{}'
    elif fault == 'stop-success':
        events.append(stop_event(receipt_case.stamp+10)); events[-1]['display_observed'] = True
    with pytest.raises((ValueError, AssertionError)): receipt_case.verify(events)


def test_published_result_cannot_be_relabelled_stopped(receipt_case):
    (Path(receipt_case.campaign['receipt_path'])/'result.json').write_text('{}')
    with pytest.raises(ValueError):
        receipt_case.verify(receipt_case.events + [stop_event(receipt_case.stamp+10)])


@pytest.fixture
def capture_case(receipt_case):
    stamp = receipt_case.stamp
    campaign = receipt_case.campaign; campaign_sha = '2'*64; stage_sha = '4'*64
    witness = dict(observed_at=stamp-5, original_rom_snapshot_sha256=stage.SNAPSHOT_SHA)
    envelope = dict(schema=1,kind='fm1-owned-resumed-stage-capture',campaign_sha256=campaign_sha,
        adapter_sha256=stage_sha,exit_status=0,retry=False,original_snapshot_refreshed=False,wrapper_files_sha256={})
    records = {'wrapper-attempt.json':dict(time=stamp-4,campaign_sha256=campaign_sha,adapter_sha256=stage_sha,
            witness_sha256=campaign['witness_sha256'],original_snapshot_refreshed=False,retry=False),
        'preflight.json':dict(time=stamp-3,factory_seconds=1,campaign_sha256=campaign_sha,
            witness_sha256=campaign['witness_sha256'],hardware_access=False,
            original_rom_snapshot_sha256=stage.SNAPSHOT_SHA,original_snapshot_refreshed=False),
        'capture-open.json':dict(time=stamp-2,timeout_pid=10,cat_pid=11,process_group=10,open_capture_fd=True),
        'capture-stop.json':dict(time=stamp+8,process_group=10,returncode=-15,owned_processes_only=True),
        'execution-exit.json':dict(time=stamp+7,exit_status=0,campaign_sha256=campaign_sha,
            capture_alive_after_child=True,retry=False,display_observed=False,physical_recovery_verified=False)}
    files = {name:evidence.canonical(record) for name,record in records.items()}
    files.update({'usbmon3.stderr':b'','usbmon3.txt':b'',
        'execution.stdout':evidence.canonical(receipt_case.verify()['result'])})
    calls = []
    transport = SimpleNamespace(verify_probe_readonly_wire=lambda *args,**kwargs:calls.append((args,kwargs)))
    def verify():
        current = {name:evidence.canonical(record) for name,record in records.items()}; current.update(
            {'usbmon3.stderr':files['usbmon3.stderr'],'usbmon3.txt':files['usbmon3.txt'],
             'execution.stdout':files['execution.stdout']})
        evidence.verify_capture(envelope,current,campaign,campaign_sha,stage_sha,witness,
            receipt_case.verify(),transport,{'busnum':'3','devnum':'26'})
    return SimpleNamespace(verify=verify,records=records,files=files,witness=witness,envelope=envelope,calls=calls)


def test_owned_capture_binds_exact_child_and_private_lifecycle(capture_case):
    capture_case.verify(); assert capture_case.calls[0][1] == {'zero_commands':False}


@pytest.mark.parametrize('fault',['pid','group','returncode','stderr','exit','alive','retry','refresh',
    'age','time','factory','hardware','snapshot','after-close','display','stdout'])
def test_owned_capture_ambiguities_rejected(capture_case,fault):
    case = capture_case
    if fault == 'pid': case.records['capture-open.json']['cat_pid'] = 10
    elif fault == 'group': case.records['capture-stop.json']['process_group'] = 12
    elif fault == 'returncode': case.records['capture-stop.json']['returncode'] = 0
    elif fault == 'stderr': case.files['usbmon3.stderr'] = b'error'
    elif fault == 'exit': case.records['execution-exit.json']['exit_status'] = 1
    elif fault == 'alive': case.records['execution-exit.json']['capture_alive_after_child'] = False
    elif fault == 'retry': case.records['wrapper-attempt.json']['retry'] = True
    elif fault == 'refresh': case.records['preflight.json']['original_snapshot_refreshed'] = True
    elif fault == 'age': case.witness['observed_at'] -= 120
    elif fault == 'time': case.records['capture-stop.json']['time'] = False
    elif fault == 'factory': case.records['preflight.json']['factory_seconds'] = float('inf')
    elif fault == 'hardware': case.records['preflight.json']['hardware_access'] = True
    elif fault == 'snapshot': case.records['preflight.json']['original_rom_snapshot_sha256'] = '0'*64
    elif fault == 'after-close': case.records['execution-exit.json']['time'] += 100
    elif fault == 'display': case.records['execution-exit.json']['display_observed'] = True
    elif fault == 'stdout': case.files['execution.stdout'] = b'{}'
    with pytest.raises(ValueError): case.verify()


def test_closed_factory_opens_no_file_or_device(monkeypatch):
    monkeypatch.setattr(evidence,'read_file',lambda *args,**kwargs:pytest.fail('Closed factory read'))
    with pytest.raises(ValueError,match='Closed'): evidence.validate_returned_state('/nonexistent')
    with pytest.raises(ValueError,match='Evidence only'): evidence.prepare_campaign('/nonexistent')


def test_registered_proof_preserves_negative_evidence_and_rejects_copy(tmp_path):
    path = tmp_path/'frozen'; path.write_bytes(b'proof'); absent = tmp_path/'result.json'
    historical = SimpleNamespace(check=lambda:None)
    proof = evidence.ReturnedProof(historical,((path,b'proof',16),),(absent,),'stopped-read-only-inconclusive',1)
    evidence._PROOFS.add(proof); proof.check()
    with pytest.raises(ValueError,match='Exact'): replace(proof).check()
    absent.symlink_to(tmp_path/'missing')
    with pytest.raises(ValueError,match='negative'): proof.check()


def test_registered_positive_source_drift_rejected(tmp_path):
    path=tmp_path/'frozen';path.write_bytes(b'proof')
    proof=evidence.ReturnedProof(SimpleNamespace(check=lambda:None),((path,b'proof',16),),(),'completed-two-read',1)
    evidence._PROOFS.add(proof);path.write_bytes(b'drift')
    with pytest.raises(ValueError,match='drift'):proof.check()


@pytest.mark.parametrize('kind',['symlink','fifo','directory','oversize','relative'])
def test_single_bounded_nofollow_reader_rejects_bad_evidence(tmp_path,kind):
    import os
    path=tmp_path/'bad'
    if kind=='symlink':
        target=tmp_path/'target';target.write_bytes(b'proof');path.symlink_to(target)
    elif kind=='fifo':os.mkfifo(path)
    elif kind=='directory':path.mkdir()
    elif kind=='oversize':path.write_bytes(b'01234')
    elif kind=='relative':path=Path('relative')
    with pytest.raises((ValueError,OSError)):evidence.read_file(path,4)
