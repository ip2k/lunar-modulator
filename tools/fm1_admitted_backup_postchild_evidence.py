"""MIT. Evidence-only classifier for the exact V8 post-child SG comparison stop.

This does not prepare a campaign, open a transport, refresh a connection, or
turn a failed wrapper into a successful one. The caller must separately use
the canonical completed-backup validator and a newly reviewed restore factory.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat

WRAPPER_SHA = '37ffe80fe92055bf60dfde0abcbf23959399e2e96882297bd50cc3e4ad04123c'
ADAPTER_SHA = '420288e39757d417f65778d0cb9e802035242466a5ac0a4b1c41b2014ff16b14'


def read(path, limit):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute retained evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('Direct private regular evidence required')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Retained evidence exceeds bound')
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate evidence key')
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError('Nonfinite evidence constant')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    if type(value) is not dict or type(value.get('schema')) is not int or value['schema'] != 1:
        raise ValueError('Exact schema-one evidence required')
    return value


def validate(run, wrapper, campaign_sha, usb_binding):
    """Classify retained lifecycle only; no current-state or backup-data claim."""
    run = Path(run)
    info = run.lstat()
    if not run.is_absolute() or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Direct private runner directory required')
    if digest(read(wrapper, 2 * 1048576)) != WRAPPER_SHA:
        raise ValueError('Exact failed wrapper source required')
    for name in ('wrapper-cleanup-ambiguous.json', 'passive-snapshot.json'):
        if os.path.lexists(run / name):
            raise ValueError('Different failure or cleanup lifecycle')
    names = ('wrapper-attempt.json', 'capture-open.json', 'execution-exit.json',
             'wrapper-stopped-ambiguous.json', 'capture-stop.json')
    raw = {name: read(run / name, 65536) for name in names}
    attempt, opened, ended, failed, stopped = [strict_json(raw[name]) for name in names]
    if (attempt.get('kind') != 'fm1-sdk-trace-admitted-backup-one-shot' or
            attempt.get('campaign_sha256') != campaign_sha or
            attempt.get('adapter_sha256') != ADAPTER_SHA or attempt.get('retry') is not False or
            attempt.get('usb_binding') != usb_binding):
        raise ValueError('Exact backup attempt binding required')
    group = opened.get('process_group')
    if (type(group) is not int or group <= 0 or opened.get('timeout_pid') != group or
            type(opened.get('cat_pid')) is not int or opened['cat_pid'] <= 0 or
            opened['cat_pid'] == group or opened.get('open_capture_fd') is not True):
        raise ValueError('Owned capture open identity required')
    if (ended.get('campaign_sha256') != campaign_sha or ended.get('adapter_sha256') != ADAPTER_SHA or
            type(ended.get('exit_status')) is not int or ended['exit_status'] != 0 or
            ended.get('retry') is not False or ended.get('capture_alive_after_child') is not True):
        raise ValueError('Successful child under live owned capture required')
    if (failed.get('error') != 'ValueError' or failed.get('detail') != 'passive SG mapping changed during campaign' or
            failed.get('retry') is not False):
        raise ValueError('Exact post-child comparison failure required')
    if (type(stopped.get('process_group')) is not int or stopped['process_group'] != group or
            type(stopped.get('returncode')) is not int or stopped['returncode'] != -15 or
            stopped.get('owned_processes_only') is not True):
        raise ValueError('Verified owned capture cleanup required')
    times = [attempt.get('time'), opened.get('time'), ended.get('child_started_at'),
             ended.get('child_finished_at'), ended.get('time'), failed.get('time'), stopped.get('time')]
    if (any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or
            times != sorted(times)):
        raise ValueError('Ordered finite lifecycle times required')
    for name, limit in (('usbmon1.txt', 16 * 1048576), ('usbmon1.stderr', 2 * 1048576),
                        ('execution.stdout', 2 * 1048576)):
        payload = read(run / name, limit)
        raw[name] = payload
        if name == 'usbmon1.txt' and not payload:
            raise ValueError('Retained capture payload required')
    return dict(schema=1, kind='fm1-admitted-backup-postchild-evidence-only',
        campaign_sha256=campaign_sha, wrapper_sha256=WRAPPER_SHA,
        retained_sha256={name: digest(data) for name, data in raw.items()},
        child_exit_status=0, wrapper_succeeded=False, capture_cleanup_verified=True,
        device_io=False, restore_authorized=False, current_connection_verified=False)
