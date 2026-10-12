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
        if not good:
            break
    all_good = len(completed) == 5 and all(
        all(type(row[k]) is int and row[k] == 0 for k in
            ('status','masked','msg','host','driver','resid','info','sense_len','actual_sense_bytes'))
        and row['sense_hex'] == '' and row['actual_response_bytes'] == operations[i][2]
        for i,row in enumerate(completed))
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
