#!/usr/bin/env python3
"""MIT. Closed evidence-only trace-read recovery admission.

The pure transcript kernel grants no authority. Actual boot, wire, owned-capture
and reader pins must be independently accepted before validate_returned_state
can admit historical evidence. No opener, USB operation or marker modification.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from weakref import WeakSet

BOOT_SOURCE_SHA = None
READ_SOURCE_SHA = None
WIRE_SOURCE_SHA = None
CAPTURE_SOURCE_SHA = None
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
_NAMES = ('inquiry', 'trace-a', 'stage-a', 'trace-b', 'stage-b')
_AUTHORIZED = WeakSet()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Direct regular evidence required')
        fp = os.fdopen(fd, 'rb'); fd = None
        with fp:
            raw = fp.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Evidence exceeds bound')
        return raw
    finally:
        if fd is not None:
            os.close(fd)


def verify_read_receipt(raw, seal, plan, operations, raw_files, *, interpret,
                        result_raw=None, pending_raw=None, evaluated_at):
    """Pure exact reader transcript/publication check, never execution proof.

    Missing/empty log requires a distinct owned zero-CBW capture gate and is
    deliberately excluded here. Failed prefixes retain ambiguity. Files may
    appear only after all five successful completions and their hashes must
    match each recorded reply; a decoded capture requires all five files.
    """
    if type(evaluated_at) not in (int, float) or not math.isfinite(evaluated_at):
        raise ValueError('Finite historical evaluation required')
    rows = [json.loads(line) for line in raw.splitlines()]
    if (not rows or len(rows) > 13 or any(type(row) is not dict for row in rows)
            or len(operations) != 5 or set(raw_files) - set(_NAMES)):
        raise ValueError('Bounded exact five-read transcript required')
    times = [row.get('time') for row in rows]
    if (not all(type(t) in (int, float) and math.isfinite(t) for t in times)
            or times != sorted(times) or times[-1] > evaluated_at):
        raise ValueError('Finite chronological original timestamps required')
    position = 0
    def event(expected):
        nonlocal position
        if position >= len(rows) or canonical({k:v for k,v in rows[position].items() if k != 'time'}) != canonical(expected):
            raise ValueError('Exact ordered reader event required')
        position += 1
    event(dict(event='read_prepared', campaign_sha256=digest(seal), plan_sha256=digest(plan),
               commands=5, upload_operations=0, reset_operations=0, flash_operations=0))
    completed = []
    good_completions = []
    for index, (cdb, out, count) in enumerate(operations):
        if position == len(rows) or rows[position].get('event') != 'submit_intent':
            break
        if out or type(cdb) is not bytes or type(count) is not int:
            raise ValueError('Read-only exact operations required')
        event(dict(event='submit_intent', index=index, cdb=cdb.hex(), in_len=count, out_len=0, retry=False))
        if position == len(rows) or rows[position].get('event') != 'completion':
            break
        row = rows[position]
        keys = {'time','event','index','status','masked','msg','host','driver','resid','info',
                'sense_len','sense_hex','actual_sense_bytes','actual_response_bytes','response_sha256','retry'}
        if (set(row) != keys or type(row['index']) is not int or row['index'] != index
                or row['retry'] is not False):
            raise ValueError('Exact recorded completion required')
        position += 1
        good = (all(type(row[k]) is int and row[k] == 0 for k in
                    ('status','masked','msg','host','driver','resid','info','sense_len','actual_sense_bytes'))
                and row['sense_hex'] == '' and type(row['actual_response_bytes']) is int
                and row['actual_response_bytes'] == count
                and isinstance(row['response_sha256'],str) and len(row['response_sha256']) == 64
                and all(c in '0123456789abcdef' for c in row['response_sha256']))
        completed.append(row)
        good_completions.append(good)
        if not good:
            break
    all_good = len(completed) == 5 and all(good_completions)
    if raw_files and not all_good:
        raise ValueError('Raw publication before five good completions')
    for index,name in enumerate(_NAMES):
        if name in raw_files and (type(raw_files[name]) is not bytes
                or len(raw_files[name]) != operations[index][2]
                or digest(raw_files[name]) != completed[index]['response_sha256']):
            raise ValueError('Raw publication differs from actual reply hash')
    expected = None
    if position < len(rows) and rows[position].get('event') == 'coherent_capture_completed':
        if not all_good or set(raw_files) != set(_NAMES):
            raise ValueError('Complete five reply publications required')
        inquiry = raw_files['inquiry']
        if inquiry[8:16].strip() != b'WL82' or inquiry[16:32].strip() != b'UBOOT1.00':
            raise ValueError('Original ROM inquiry required')
        expected = interpret(*(raw_files[name] for name in _NAMES[1:]))
        expected = dict(expected, campaign_sha256=digest(seal), plan_sha256=digest(plan),
                        raw_sha256=[digest(raw_files[name]) for name in _NAMES])
        event(dict(event='coherent_capture_completed', **expected, retry=False))
    if position < len(rows):
        row = rows[position]
        if (set(row) != {'time','event','error','retry','classification'}
                or row['event'] != 'capture_stopped_ambiguous' or row['retry'] is not False
                or row['classification'] != 'inconclusive' or not isinstance(row['error'],str)
                or not row['error']):
            raise ValueError('Exact terminal ambiguity required')
        position += 1
        outcome = 'stopped-ambiguous'
        if result_raw is not None:
            raise ValueError('Stopped receipt cannot publish success result')
        if pending_raw is not None and (expected is None or pending_raw != canonical(expected)):
            raise ValueError('Unexplained pending result publication')
    else:
        outcome = 'completed'
        if expected is None or result_raw != canonical(expected) or pending_raw is not None:
            raise ValueError('Exact completed result and pending absence required')
    if position != len(rows):
        raise ValueError('Later commands or transcript rows prohibited')
    return dict(outcome=outcome, started_at=times[0], terminal_at=times[-1],
                successful_completions=5 if all_good else 0, result=expected)


_CAPTURE_FILES = ('execute-once.py', 'execute-child.py', 'preflight.json',
    'wrapper-attempt.json', 'capture-open.json', 'capture-stop.json',
    'execution.stdout', 'execution-exit.json', 'usbmon.txt', 'usbmon.stderr')


def verify_capture_lifecycle(envelope_raw, files, expected, *, read_outcome,
                             read_started=None, read_terminal=None):
    """Pure exact owned lifecycle shape/hash check; no wire or opener proof.

    A future factory must freeze these actual files, their absent ambiguity
    artifacts and exact source/packet inputs, then independently replay native
    commands and the USBmon CBW prefix. Bare JSON and this value check do not
    grant returned proof membership or refresh historical snapshot timestamps.
    """
    keys = {'wrapper_sha256', 'child_sha256', 'native_campaign_path',
        'native_campaign_sha256', 'boot_lineage_path', 'boot_lineage_sha256',
        'native_sha256', 'reader_sha256', 'boot_sha256', 'usb_binding'}
    if type(expected) is not dict or set(expected) != keys or set(files) != set(_CAPTURE_FILES):
        raise ValueError('Exact owned capture input inventory required')
    for name, pin in expected.items():
        if name.endswith('sha256') and (type(pin) is not str or len(pin) != 64
                or any(c not in '0123456789abcdef' for c in pin)):
            raise ValueError('Exact accepted source/input digest required')
    for name in ('native_campaign_path', 'boot_lineage_path'):
        if type(expected[name]) is not str or not Path(expected[name]).is_absolute():
            raise ValueError('Original absolute capture input required')
    if any(type(v) is not bytes for v in files.values()):
        raise ValueError('Exact captured bytes required')
    envelope = json.loads(envelope_raw)
    wanted = dict(schema=1, kind='fm1-owned-sdk-trace-read-capture',
        native_campaign_path=expected['native_campaign_path'],
        native_campaign_sha256=expected['native_campaign_sha256'],
        boot_lineage_path=expected['boot_lineage_path'],
        boot_lineage_sha256=expected['boot_lineage_sha256'],
        wrapper_files_sha256={name:digest(value) for name,value in files.items()})
    if (canonical(envelope) != canonical(wanted)
            or digest(files['execute-once.py']) != expected['wrapper_sha256']
            or digest(files['execute-child.py']) != expected['child_sha256']
            or files['usbmon.stderr']):
        raise ValueError('Exact owned capture envelope/source/hash required')
    attempt, opened, stopped, exited = [json.loads(files[name]) for name in
        ('wrapper-attempt.json', 'capture-open.json', 'capture-stop.json', 'execution-exit.json')]
    if any(type(record) is not dict for record in (attempt,opened,stopped,exited)):
        raise ValueError('Owned capture records must be objects')
    attempt_expected = dict(campaign_sha256=expected['native_campaign_sha256'],
        lineage_sha256=expected['boot_lineage_sha256'], native_sha256=expected['native_sha256'],
        reader_sha256=expected['reader_sha256'], boot_sha256=expected['boot_sha256'],
        usb_binding=expected['usb_binding'], retry=False, commands=5,
        upload_operations=0, reset_operations=0, flash_operations=0)
    if canonical({k:v for k,v in attempt.items() if k!='time'}) != canonical(attempt_expected):
        raise ValueError('Exact original wrapper attempt required')
    if (set(opened) != {'time','timeout_pid','cat_pid','process_group','open_capture_fd'}
            or set(stopped) != {'time','process_group','returncode','owned_processes_only'}
            or set(exited) != {'time','exit_status','campaign_sha256','capture_alive_after_child',
                'retry','read_completion_attested','recovery_proven','boot_cause_proven'}):
        raise ValueError('Exact owned capture/exit receipt shape required')
    if (any(type(opened[k]) is not int or opened[k] <= 0 for k in ('timeout_pid','cat_pid','process_group'))
            or opened['timeout_pid'] != opened['process_group'] or opened['cat_pid'] == opened['timeout_pid']
            or opened['open_capture_fd'] is not True or type(stopped['process_group']) is not int
            or stopped['process_group'] != opened['process_group'] or type(stopped['returncode']) is not int
            or stopped['returncode'] != -15 or stopped['owned_processes_only'] is not True
            or type(exited['exit_status']) is not int or not -64 <= exited['exit_status'] <= 255
            or exited['campaign_sha256'] != expected['native_campaign_sha256']
            or exited['capture_alive_after_child'] is not True
            or any(exited[k] is not False for k in ('retry','read_completion_attested','recovery_proven','boot_cause_proven'))):
        raise ValueError('Exact owned process/terminal identity required')
    times = [r.get('time') for r in (attempt, opened, exited, stopped)]
    if (any(type(t) not in (int,float) or not math.isfinite(t) for t in times)
            or times != sorted(times)):
        raise ValueError('Original finite capture chronology required')
    if read_outcome not in ('completed','stopped-ambiguous','consumed-pretransport-zero-cbw'):
        raise ValueError('Exact read outcome classification required')
    if (read_outcome == 'completed' and exited['exit_status'] != 0
            or read_outcome != 'completed' and exited['exit_status'] == 0):
        raise ValueError('Read outcome and preserved child exit differ')
    if read_started is None or read_terminal is None:
        if (read_outcome != 'consumed-pretransport-zero-cbw'
                or read_started is not None or read_terminal is not None):
            raise ValueError('Zero-CBW branch cannot invent reader timestamps')
    elif read_outcome == 'consumed-pretransport-zero-cbw':
        raise ValueError('Zero-CBW branch cannot invent reader timestamps')
    elif (any(type(t) not in (int,float) or not math.isfinite(t) for t in (read_started,read_terminal))
            or not opened['time'] <= read_started <= read_terminal <= exited['time']):
        raise ValueError('Reader must be within original owned live capture')
    return dict(exit_status=exited['exit_status'], started_at=times[0], terminal_at=times[-1],
                envelope_sha256=digest(envelope_raw), wire_inventory_verified=False,
                returned_proof_granted=False)


@dataclass(frozen=True, eq=False)
class ReturnedProof:
    snapshot: bytes
    snapshot_sha256: str
    original_inputs: bytes
    manifest_sha256: str
    private_parent: str
    evidence: tuple
    policies: tuple
    original_install_campaign_sha256: str
    install_journal_sha256: str
    terminal_at: float
    read_outcome: str
    absent: tuple
    lineage: object

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact evidence-created returned proof required')
        self.lineage.check()
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen returned trace evidence changed')
        for policy in self.policies:
            policy.check_files()
        if any(os.path.lexists(path) for path in self.absent):
            raise ValueError('Frozen absent returned evidence appeared')


def validate_returned_state(path, *, install_journal_path=None):
    """Closed until actual owned capture and boot/read validators are reviewed.

    Preserved journal is historical evidence only; it must never authorize a new
    read or alter original admission/snapshot timestamps. This WIP grants none.
    """
    if any(pin is None for pin in (BOOT_SOURCE_SHA, READ_SOURCE_SHA, WIRE_SOURCE_SHA, CAPTURE_SOURCE_SHA)):
        raise ValueError('Closed: independently accepted boot/read/capture evidence required')
    raise ValueError('Closed: exact owned read capture admission not implemented')
