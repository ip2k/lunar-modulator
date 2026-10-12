#!/usr/bin/env python3
"""MIT. Closed evidence admission after the actual chooser and resumed RAM read.

No device discovery, opener, command, upload, flash operation or reset authority.
Private Python callback adaptation is evidence-only, not a security sandbox.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import types
from weakref import WeakSet

STAGE_SOURCE_SHA = None  # Final independent source/runtime freeze is required.
WRAPPER_SOURCE_SHA = None  # Exact bound owned-capture wrapper, never a template.
_PROOFS = WeakSet()


def digest(data): return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute(): raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try: fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd); raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode): raise ValueError('Regular evidence required')
        raw = fp.read(limit + 1)
    if len(raw) > limit: raise ValueError('Evidence exceeds bound')
    return raw


def load_source(path, pin, name):
    raw = read_file(path)
    if digest(raw) != pin: raise ValueError('Frozen source differs')
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def direct_private(path):
    path = Path(path)
    if (not path.is_absolute() or not stat.S_ISDIR(path.lstat().st_mode) or
            stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise ValueError('Direct private directory required')


def without_time(event):
    result = dict(event); result.pop('time', None); return result


def verify_receipt(raw, campaign, campaign_sha, stage, helper, freeze, absent):
    """Exact resumed-read prefix; an ambiguous read never becomes a success."""
    receipt = Path(campaign['receipt_path'])
    events = [json.loads(line) for line in raw.splitlines()]
    if not events: raise ValueError('Consumed read requires its actual terminal log')
    times = [event.get('time') for event in events]
    if (not all(finite(value) for value in times) or times != sorted(times) or times[-1] > time.time()):
        raise ValueError('Actual resumed-read chronology required')
    first = dict(event='resumed_stage_probe_prepared', campaign_sha256=campaign_sha,
        original_rom_snapshot_sha256=stage.SNAPSHOT_SHA,
        choice_stop_sha256=stage.CHOICE_PINS['chooser-stopped-ambiguous.json'],
        current_witness_sha256=campaign['witness_sha256'], original_snapshot_refreshed=False,
        commands=2, upload_operations=0, flash_operations=0, reset_operations=0,
        kernel_exclusivity=False)
    if canonical(without_time(events[0])) != canonical(first):
        raise ValueError('Exact distinct resumed-read envelope required')
    stopped = events[-1].get('event') == 'stage_probe_stopped_ambiguous'
    if stopped:
        terminal = without_time(events[-1])
        if (set(terminal) != {'event','error','retry','classification','display_observed','physical_recovery_verified'} or
                type(terminal['error']) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}', terminal['error']) or
                terminal['retry'] is not False or terminal['classification'] != 'inconclusive' or
                terminal['display_observed'] is not False or terminal['physical_recovery_verified'] is not False):
            raise ValueError('Exact terminal inconclusive read stop required')
        absent.append(receipt / 'result.json')
        if os.path.lexists(receipt / 'result.json'): raise ValueError('Stopped read published a result')
        body = events[1:-1]
    else:
        if events[-1].get('event') != 'stage_capture_completed':
            raise ValueError('Exact completed or caught stopped read required')
        body = events[1:]
    position = 0; intents = 0; hashes = []; good = True
    for index, (cdb, _, size) in enumerate(stage.OPERATIONS):
        if position == len(body): break
        intent = dict(event='sg_submit_intent', index=index, cdb=cdb.hex(), out_len=0,
            in_len=size, retry=False)
        if canonical(without_time(body[position])) != canonical(intent) or not good:
            raise ValueError('Exact two-read prefix and no later request after failure required')
        position += 1; intents += 1
        if position == len(body): break
        completion = without_time(body[position])
        keys = {'event','index','status','masked','msg','host','driver','resid','info',
            'sense_len','sense_hex','response_sha256','retry'}
        if (set(completion) != keys or completion['event'] != 'sg_completion' or
                type(completion['index']) is not int or completion['index'] != index or
                completion['retry'] is not False or any(type(completion[key]) is not int or
                not -2**31 <= completion[key] < 2**32 for key in ('status','masked','msg','host','driver','resid','info')) or
                type(completion['sense_len']) is not int or not 0 <= completion['sense_len'] <= 255 or
                type(completion['sense_hex']) is not str or not re.fullmatch(r'[0-9a-f]*', completion['sense_hex']) or
                len(completion['sense_hex']) != 2 * min(completion['sense_len'], 32) or
                type(completion['response_sha256']) is not str or
                not re.fullmatch(r'[0-9a-f]{64}', completion['response_sha256'])):
            raise ValueError('Actual structured read completion required')
        good = all(completion[key] == 0 for key in
            ('status','masked','msg','host','driver','resid','info','sense_len')) and completion['sense_hex'] == ''
        position += 1; hashes.append(completion['response_sha256'])
        if not good and position != len(body): raise ValueError('No later event after failed read completion')
    result = None
    if position < len(body):
        if position != 4 or not good: raise ValueError('Extra resumed-read event')
        data = freeze(receipt / 'raw.bin', limit=32); decoded = freeze(receipt / 'decoded.bin', limit=32)
        if len(data) != 32 or len(decoded) != 32 or helper.decode_stage(data) != decoded or hashes[1] != digest(data):
            raise ValueError('Actual encoded RAM evidence differs')
        result = dict(campaign_sha256=campaign_sha, raw_sha256=digest(data), decoded_sha256=digest(decoded),
            inquiry_sha256=hashes[0], current_witness_sha256=campaign['witness_sha256'],
            original_rom_snapshot_sha256=stage.SNAPSHOT_SHA,
            choice_stop_sha256=stage.CHOICE_PINS['chooser-stopped-ambiguous.json'],
            original_snapshot_refreshed=False, target_reset_outcome='transmitted-detached-not-completed',
            reset_request_completed=False, **helper.interpret_stage(decoded))
        if canonical(without_time(body[position])) != canonical(dict(event='stage_capture_completed', **result, retry=False)):
            raise ValueError('Exact decoded result envelope required')
        position += 1
    if position != len(body) or (not stopped and result is None):
        raise ValueError('Complete two-read receipt or bounded caught stop required')
    if not stopped and canonical(json.loads(freeze(receipt / 'result.json', limit=65536))) != canonical(result):
        raise ValueError('Durable completed read result differs')
    return dict(outcome='stopped-read-only-inconclusive' if stopped else 'completed-two-read',
        intents=intents, started=times[0], ended=times[-1], result=result)


def verify_capture(envelope, files, campaign, campaign_sha, stage_sha, witness, receipt, helper, usb):
    """Owned lifecycle plus bounded inventory; process origin is not inferred."""
    if (set(envelope) != {'schema','kind','campaign_sha256','adapter_sha256','exit_status','retry',
            'original_snapshot_refreshed','wrapper_files_sha256'} or type(envelope['schema']) is not int or
            envelope['schema'] != 1 or envelope['kind'] != 'fm1-owned-resumed-stage-capture' or
            envelope['campaign_sha256'] != campaign_sha or envelope['adapter_sha256'] != stage_sha or
            type(envelope['exit_status']) is not int or envelope['retry'] is not False or
            envelope['original_snapshot_refreshed'] is not False):
        raise ValueError('Exact owned resumed capture required')
    attempt = json.loads(files['wrapper-attempt.json']); pre = json.loads(files['preflight.json'])
    opened = json.loads(files['capture-open.json']); stopped = json.loads(files['capture-stop.json'])
    exited = json.loads(files['execution-exit.json'])
    if canonical(without_time(attempt)) != canonical(dict(campaign_sha256=campaign_sha,
            adapter_sha256=stage_sha, witness_sha256=campaign['witness_sha256'], original_snapshot_refreshed=False, retry=False)):
        raise ValueError('Actual wrapper attempt differs')
    if (set(pre) != {'time','factory_seconds','campaign_sha256','witness_sha256','hardware_access',
            'original_rom_snapshot_sha256','original_snapshot_refreshed'} or not finite(pre['factory_seconds']) or
            pre['campaign_sha256'] != campaign_sha or pre['witness_sha256'] != campaign['witness_sha256'] or
            pre['hardware_access'] is not False or pre['original_rom_snapshot_sha256'] != witness['original_rom_snapshot_sha256'] or
            pre['original_snapshot_refreshed'] is not False or not finite(pre['time']) or
            not 0 <= pre['time'] - witness['observed_at'] <= 120):
        raise ValueError('Historical separate passive witness admission required')
    if (set(opened) != {'time','timeout_pid','cat_pid','process_group','open_capture_fd'} or
            any(type(opened[key]) is not int or opened[key] <= 0 for key in ('timeout_pid','cat_pid','process_group')) or
            opened['timeout_pid'] != opened['process_group'] or opened['cat_pid'] == opened['timeout_pid'] or
            opened['open_capture_fd'] is not True or
            set(stopped) != {'time','process_group','returncode','owned_processes_only'} or
            stopped['process_group'] != opened['process_group'] or type(stopped['returncode']) is not int or
            stopped['returncode'] != -15 or stopped['owned_processes_only'] is not True or
            set(exited) != {'time','exit_status','campaign_sha256','capture_alive_after_child','retry','display_observed','physical_recovery_verified'} or
            type(exited['exit_status']) is not int or exited['exit_status'] != envelope['exit_status'] or
            exited['campaign_sha256'] != campaign_sha or exited['capture_alive_after_child'] is not True or
            any(exited[key] is not False for key in ('retry','display_observed','physical_recovery_verified')) or
            files['usbmon3.stderr']):
        raise ValueError('Unambiguous owned capture lifecycle required')
    times = [attempt.get('time'), pre.get('time'), opened.get('time'), exited.get('time'), stopped.get('time')]
    if not all(finite(value) for value in times) or times != sorted(times) or times[-1] > time.time():
        raise ValueError('Owned capture chronology differs')
    complete = receipt['outcome'] == 'completed-two-read'
    if (complete != (exited['exit_status'] == 0) or
            (receipt['started'] is not None and not opened['time'] <= receipt['started'] <= receipt['ended'] <= exited['time'])):
        raise ValueError('Child exit/actual read transcript differ')
    if complete and canonical(json.loads(files['execution.stdout'])) != canonical(receipt['result']):
        raise ValueError('Completed child stdout differs from durable result')
    helper.verify_probe_readonly_wire(files['usbmon3.txt'], usb, receipt['intents'],
        zero_commands=receipt['started'] is None)


@dataclass(frozen=True, eq=False)
class ReturnedProof:
    historical: object
    evidence: tuple
    absent: tuple
    probe_outcome: str
    terminal_at: float

    def check(self):
        if self not in _PROOFS: raise ValueError('Exact successor evidence proof required')
        self.historical.check()
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw: raise ValueError('Successor evidence drift')
        if any(os.path.lexists(path) for path in self.absent):
            raise ValueError('Successor negative evidence appeared')

    @property
    def snapshot(self): return self.historical.snapshot
    @property
    def original_inputs(self): return self.historical.original_inputs
    @property
    def private_parent(self): return self.historical.private_parent
    @property
    def manifest_sha256(self): return self.historical.manifest_sha256
    @property
    def policies(self): return self.historical.policies
    @property
    def original_rehearsal_campaign_sha256(self): return self.historical.historical.original_rehearsal_campaign_sha256
    @property
    def install_journal_sha256(self): return self.historical.historical.install_journal_sha256


def validate_returned_state(path, *, install_journal_path=None):
    """Evidence only; original admission is historical, never a fresh opener."""
    if any(type(pin) is not str or not re.fullmatch(r'[0-9a-f]{64}', pin)
            for pin in (STAGE_SOURCE_SHA, WRAPPER_SOURCE_SHA)):
        raise ValueError('Closed: final independently reviewed stage/wrapper pins required')
    evidence = []; absent = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path); raw = read_file(path, limit)
        if expected is not None and digest(raw) != expected: raise ValueError('Pinned successor evidence differs')
        evidence.append((path, raw, limit)); return raw
    raw = freeze(path, limit=65536); c = json.loads(raw)
    keys = {'schema','kind','adapter_sha256','choice_path','stage_campaign_path','stage_campaign_sha256',
        'owned_capture_path','owned_capture_sha256'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-actual-stopped-choice-post-read-evidence'):
        raise ValueError('Distinct post-read recovery evidence envelope required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    stage_path = root / 'fm1_diagnostic_stage_resume.py'; freeze(stage_path, STAGE_SOURCE_SHA)
    stage = load_source(stage_path, STAGE_SOURCE_SHA, '_fm1_successor_stage_evidence')
    if install_journal_path is not None:
        # Only the evidence callback is adapted, never prepare or its registry.
        original_loader = stage.load_source
        def load_historical(source, pin, name):
            module = original_loader(source, pin, name)
            if Path(source) == root / 'fm1_diagnostic_detached_probe.py':
                if pin != stage.HELPER_SHA: raise ValueError('Exact historical helper required')
                validate = module.validate_returned_state
                def preserved(*args, **kwargs):
                    if 'install_journal_path' in kwargs: raise ValueError('One explicit preserved journal boundary required')
                    return validate(*args, **kwargs, install_journal_path=install_journal_path)
                module.validate_returned_state = preserved
            return module
        stage.load_source = load_historical
    historical = stage.validate_returned_state(c['choice_path'])
    for p, b, n in historical.evidence + historical.historical.evidence: freeze(p, digest(b), n)
    for policy in historical.policies:
        for p, b, n in policy.evidence: freeze(p, digest(b), n)
        policy.check_files()
    helper_path = root / 'fm1_diagnostic_detached_probe.py'; freeze(helper_path, stage.HELPER_SHA)
    helper = load_source(helper_path, stage.HELPER_SHA, '_fm1_successor_read_replay')
    campaign_raw = freeze(c['stage_campaign_path'], c['stage_campaign_sha256'], 65536)
    campaign = json.loads(campaign_raw); run = Path(c['stage_campaign_path']).parent
    expected = {'schema','kind','adapter_sha256','choice_path','witness_path','witness_sha256','receipt_path'}
    if (set(campaign) != expected or type(campaign['schema']) is not int or campaign['schema'] != 1 or
            campaign['kind'] != 'fm1-actual-stopped-choice-stage-read' or campaign['adapter_sha256'] != STAGE_SOURCE_SHA or
            campaign['choice_path'] != c['choice_path'] or run != Path(c['choice_path']).parent / 'diagnostic-stage-resume-v1'):
        raise ValueError('Exact actual resumed-read campaign required')
    snapshot = json.loads(historical.snapshot)
    witness_raw = freeze(campaign['witness_path'], campaign['witness_sha256'], 65536); witness = json.loads(witness_raw)
    if (Path(campaign['witness_path']) != run / 'witness.json' or
            set(witness) != {'schema','kind','observed_at','usb_binding','sg_binding','original_rom_snapshot_sha256','choice_stop_sha256','quiet_state'} or
            type(witness['schema']) is not int or witness['schema'] != 1 or
            witness['kind'] != 'fm1-passive-current-same-rom-after-stopped-choice' or not finite(witness['observed_at']) or
            witness['observed_at'] < 1791775865.1165452 or
            witness['quiet_state'] != 'no-later-device-commands-no-loader-upload' or
            witness['original_rom_snapshot_sha256'] != stage.SNAPSHOT_SHA or
            witness['choice_stop_sha256'] != stage.CHOICE_PINS['chooser-stopped-ambiguous.json'] or
            canonical(witness['usb_binding']) != canonical(snapshot['usb_binding']) or
            canonical(witness['sg_binding']) != canonical(snapshot['sg_binding'])):
        raise ValueError('Original historical separate passive binding required')
    receipt = Path(campaign['receipt_path']); parent = Path(historical.private_parent)
    if receipt != parent / 'diagnostic-stage-resume-001': raise ValueError('Exact distinct read receipt required')
    direct_private(parent); direct_private(run)
    marker = parent / ('.diagnostic-stage-resume-' + stage.BOOT_SHA + '.consumed')
    absent.extend(historical.absent)
    if os.path.lexists(receipt) or os.path.lexists(marker):
        direct_private(receipt)
        if freeze(marker, limit=256) != c['stage_campaign_sha256'].encode('ascii'):
            raise ValueError('Exact consumed read marker required')
        read = verify_receipt(freeze(receipt / 'commands.jsonl', limit=65536), campaign,
            c['stage_campaign_sha256'], stage, helper, freeze, absent)
    else:
        absent.extend((receipt, marker))
        read = dict(outcome='pre-open-zero-request-stop', intents=0, started=None, ended=None, result=None)
    if Path(c['owned_capture_path']) != run / 'owned-capture.json': raise ValueError('Direct owned capture envelope required')
    envelope = json.loads(freeze(c['owned_capture_path'], c['owned_capture_sha256'], 65536))
    names = {'execute-once-bound.py','wrapper-attempt.json','preflight.json','capture-open.json',
        'capture-stop.json','execution-exit.json','execution.stdout','usbmon3.txt','usbmon3.stderr','campaign.json','witness.json'}
    pins = envelope.get('wrapper_files_sha256')
    if type(pins) is not dict or set(pins) != names or pins['execute-once-bound.py'] != WRAPPER_SOURCE_SHA:
        raise ValueError('Exact independently pinned owned wrapper files required')
    files = {name: freeze(run / name, pin, 32*1048576 if name == 'usbmon3.txt' else 2*1048576)
        for name, pin in pins.items()}
    if files['campaign.json'] != campaign_raw or files['witness.json'] != witness_raw:
        raise ValueError('Owned capture campaign/witness bytes differ')
    absent.extend(run / name for name in ('wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'))
    verify_capture(envelope, files, campaign, c['stage_campaign_sha256'], STAGE_SOURCE_SHA,
        witness, read, helper, snapshot['usb_binding'])
    proof = ReturnedProof(historical, tuple(evidence), tuple(absent), read['outcome'],
        json.loads(files['capture-stop.json'])['time'])
    _PROOFS.add(proof); proof.check(); return proof


def prepare_campaign(*args, **kwargs):
    raise ValueError('Evidence only: no transport or execution authority')
